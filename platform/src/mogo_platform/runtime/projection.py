#!/usr/bin/env python3
"""MOGO Automation Platform -- apply events to the derived index, idempotently.

AUTHORITY
    Automation Platform Constitution v1.0 (senior) -- sections 6, 7
    ADR-012 (accepted 2026-08-07)                  -- D-05 state is derived
    MOGO-009 Architecture, section 18.1
    MOGO-009 Contract Catalog, sections C and L
    MOGO-011 Step 1 plan, section 8.3

THE ONE-WAY RULE
    Events flow log -> index. Nothing flows back. This module is the only code
    that writes task state, and it writes it only in response to an event that
    is ALREADY durable in the log. Architecture section 18.1: "every transition
    is persisted as an event before the state is considered changed".

EXACTLY-ONCE WITHOUT BOOKKEEPING
    Every transition is a guarded UPDATE:

        UPDATE tasks SET state=:to, last_log_sequence=:seq
         WHERE task_id=:id AND state=:from AND last_log_sequence < :seq

    rowcount == 1  -> applied.
    rowcount == 0  -> re-read the row and decide:
        last_log_sequence >= seq  -> ALREADY APPLIED. A replay. Not an error.
        state != from             -> illegal or late. Nothing mutated.

    The guard lives in the WHERE clause, so replay-safety is a property of the
    statement rather than of the caller remembering to check something.
"""

import json

from ..contracts import task_states  # noqa: E402
from . import errors as runtime_errors  # noqa: E402
from . import schema as schema_module  # noqa: E402
from . import store  # noqa: E402

APPLIED = "applied"
ALREADY_APPLIED = "already_applied"
NO_TRANSITION = "no_transition"
ANOMALY = "anomaly"


class ApplyOutcome(object):
    __slots__ = ("status", "detail")

    def __init__(self, status, detail=None):
        self.status = status
        self.detail = detail

    def __repr__(self):
        return "ApplyOutcome(%s, %r)" % (self.status, self.detail)


# Event type -> (from_state, to_state). Every entry is one Catalog section L
# edge. An event type absent from this table carries no transition; it is
# indexed and nothing else.
TRANSITIONS = {
    "TaskRequested":            (None, "requested"),
    "TaskPolicyCheckRequested": ("requested", "policy_check"),
    "PolicyEvaluated":          ("policy_check", "queued"),
    "TaskClaimed":              ("queued", "claimed"),
    "TaskStarted":              ("claimed", "running"),
    "TaskSucceeded":            ("running", "succeeded"),
    "TaskFailed":               ("running", "failed"),
    "TaskReclaimed":            (None, "queued"),   # from claimed OR running
}

RECLAIMABLE_STATES = ("claimed", "running")
TERMINAL_FLAG = {state: 1 for state in task_states.TERMINAL_STATES}


def index_event(connection, record):
    """Insert one event into the derived index. Idempotent.

    Returns True when the row was new. A repeat is silently ignored -- an event
    replayed after a crash between the log append and this transaction must not
    be an error, because that gap is the normal, expected crash window.
    """
    event = record.event
    cursor = connection.execute(
        "INSERT OR IGNORE INTO event_index ("
        " log_sequence, event_id, event_type, event_version, workflow_id, task_id,"
        " correlation_id, causation_id, producer, occurred_at, recorded_at,"
        " sequence, payload_hash, byte_offset, byte_length"
        ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (record.log_sequence, event["eventId"], event["eventType"],
         event["eventVersion"], event["workflowId"], event.get("taskId"),
         event["correlationId"], event["causationId"], event["producer"],
         event["occurredAt"], event["recordedAt"], event["sequence"],
         event["payloadHash"], record.byte_offset, record.byte_length),
    )
    return cursor.rowcount == 1


def _record_anomaly(connection, record, from_state, to_state, reason):
    connection.execute(
        "INSERT INTO transition_anomalies "
        "(detected_at, log_sequence, task_id, from_state, to_state, reason) "
        "VALUES (?,?,?,?,?,?)",
        (record.event["recordedAt"], record.log_sequence,
         record.event.get("taskId") or "", from_state or "", to_state, reason),
    )


def apply_transition(connection, record, from_state, to_state):
    """Apply one task-state transition. The guarded UPDATE described above."""
    task_id = record.event.get("taskId")
    if not task_id:
        runtime_errors.fail(
            "event %s carries a transition but no taskId" % (record.event_id,),
            runtime_errors.ReplayDivergenceError,
        )

    row = connection.execute(
        "SELECT state, last_log_sequence, terminal FROM tasks WHERE task_id = ?",
        (task_id,)).fetchone()
    if row is None:
        runtime_errors.fail(
            "event %s transitions unknown task %s" % (record.event_id, task_id),
            runtime_errors.ReplayDivergenceError,
        )

    if row["last_log_sequence"] >= record.log_sequence:
        return ApplyOutcome(ALREADY_APPLIED,
                            "task %s already at log_sequence %d"
                            % (task_id, row["last_log_sequence"]))

    current = row["state"]

    # Catalog section C: a transition arriving at a terminal task is recorded as
    # an anomaly and NOT applied. Checked before legality, because a late event
    # is a different fact from an illegal one and must not be reported as one.
    if row["terminal"]:
        anomaly = task_states.classify_late_transition(current, to_state)
        _record_anomaly(connection, record, current, to_state,
                        str(anomaly) if anomaly else "late transition")
        return ApplyOutcome(ANOMALY, "late transition into terminal task %s" % task_id)

    effective_from = current if from_state is None else from_state
    if from_state is not None and current != from_state:
        _record_anomaly(connection, record, current, to_state,
                        "expected from-state %s, found %s" % (from_state, current))
        return ApplyOutcome(ANOMALY,
                            "task %s is %s, not %s" % (task_id, current, from_state))

    # Legality is decided by the MOGO-010 contract, never re-implemented here.
    task_states.assert_legal_transition(effective_from, to_state)

    cursor = connection.execute(
        "UPDATE tasks SET state = ?, terminal = ?, last_log_sequence = ? "
        " WHERE task_id = ? AND state = ? AND last_log_sequence < ?",
        (to_state, TERMINAL_FLAG.get(to_state, 0), record.log_sequence,
         task_id, effective_from, record.log_sequence),
    )
    if cursor.rowcount != 1:
        runtime_errors.fail(
            "guarded transition %s -> %s for task %s changed %d rows"
            % (effective_from, to_state, task_id, cursor.rowcount),
            runtime_errors.ReplayDivergenceError,
        )
    return ApplyOutcome(APPLIED, "%s -> %s" % (effective_from, to_state))


def _apply_command_accepted(connection, record):
    payload = record.event["payload"]
    connection.execute(
        "INSERT OR IGNORE INTO commands ("
        " command_id, command_type, command_version, workflow_id, correlation_id,"
        " idempotency_key, target_capability, issued_at, issued_by, payload_hash,"
        " payload_json, accepted_log_sequence, task_id"
        ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,NULL)",
        (payload["commandId"], payload["commandType"], payload["commandVersion"],
         record.event["workflowId"], record.event["correlationId"],
         payload["idempotencyKey"], payload["targetCapability"],
         payload["issuedAt"], payload["issuedBy"], payload["payloadHash"],
         json.dumps(payload["commandPayload"], sort_keys=True,
                    separators=(",", ":"), ensure_ascii=False),
         record.log_sequence),
    )


def _apply_task_requested(connection, record):
    """Create the task row. Returns True only when the row was actually new.

    On replay the INSERT OR IGNORE does nothing, and the caller must report
    ALREADY_APPLIED rather than APPLIED -- otherwise the divergence guard in
    apply_event() would (correctly) object that an already-indexed event had
    changed state a second time.
    """
    payload = record.event["payload"]
    task_id = record.event["taskId"]
    cursor = connection.execute(
        "INSERT OR IGNORE INTO tasks ("
        " task_id, workflow_id, correlation_id, command_id, capability_id,"
        " idempotency_key, state, attempt, created_log_sequence,"
        " last_log_sequence, terminal"
        ") VALUES (?,?,?,?,?,?,?,?,?,?,0)",
        (task_id, record.event["workflowId"], record.event["correlationId"],
         payload["commandId"], payload["capabilityId"], payload["idempotencyKey"],
         "requested", 0, record.log_sequence, record.log_sequence),
    )
    connection.execute(
        "UPDATE commands SET task_id = ? WHERE command_id = ? AND task_id IS NULL",
        (task_id, payload["commandId"]),
    )
    return cursor.rowcount == 1


def _apply_task_result(connection, record, to_state):
    payload = record.event["payload"]
    connection.execute(
        "UPDATE tasks SET result_hash = ?, error_class = ? WHERE task_id = ?",
        (payload.get("resultHash"), record.event.get("errorClass"),
         record.event["taskId"]),
    )


def apply_event(connection, record):
    """Index one event and apply whatever transition it carries.

    Called inside a BEGIN IMMEDIATE transaction opened by the caller, so that
    the index row and the state change commit together or not at all.
    """
    was_new = index_event(connection, record)
    event_type = record.event_type

    outcome = ApplyOutcome(NO_TRANSITION, "indexed only")

    if event_type == "CommandAccepted":
        _apply_command_accepted(connection, record)
    elif event_type == "TaskRequested":
        created = _apply_task_requested(connection, record)
        outcome = (ApplyOutcome(APPLIED, "created in requested") if created
                   else ApplyOutcome(ALREADY_APPLIED, "task already exists"))

    if event_type == "TaskReclaimed":
        task_id = record.event.get("taskId")
        row = connection.execute(
            "SELECT state FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        if row is not None and row["state"] in RECLAIMABLE_STATES:
            outcome = apply_transition(connection, record, row["state"], "queued")
        else:
            outcome = ApplyOutcome(ALREADY_APPLIED, "nothing to reclaim")
    elif event_type in TRANSITIONS:
        from_state, to_state = TRANSITIONS[event_type]
        outcome = apply_transition(connection, record, from_state, to_state)
        if outcome.status == APPLIED and event_type in ("TaskSucceeded", "TaskFailed"):
            _apply_task_result(connection, record, to_state)

    connection.execute(
        "UPDATE log_cursor SET last_log_sequence = ?, last_byte_offset = ?, "
        "last_event_id = ? WHERE id = 1 AND last_log_sequence < ?",
        (record.log_sequence, record.byte_offset + record.byte_length,
         record.event_id, record.log_sequence),
    )
    if not was_new and outcome.status == APPLIED:
        # An already-indexed event that still moved state would mean the index
        # and the task table disagree about what has been applied.
        runtime_errors.fail(
            "event %s was already indexed but still applied a transition"
            % (record.event_id,),
            runtime_errors.ReplayDivergenceError,
        )
    return outcome


def cursor_position(connection):
    row = connection.execute(
        "SELECT last_log_sequence, last_byte_offset, last_event_id "
        "FROM log_cursor WHERE id = 1").fetchone()
    if row is None:
        return (0, 0, None)
    return (row["last_log_sequence"], row["last_byte_offset"], row["last_event_id"])


def replay(connection, log, from_log_sequence=None):
    """Apply every log record beyond the cursor. Idempotent and resumable.

    This is the whole of crash recovery phase R3: whatever the database missed
    because the process died between the fsync and the transaction, it catches
    up here, and applying an event twice is a no-op by construction.
    """
    if from_log_sequence is None:
        from_log_sequence = cursor_position(connection)[0]
    applied = 0
    scanned = log.scan(verify=True)
    for record in scanned.records:
        if record.log_sequence <= from_log_sequence:
            continue
        with store.immediate_transaction(connection):
            outcome = apply_event(connection, record)
        if outcome.status == APPLIED:
            applied += 1
    return {"scanned": len(scanned.records), "applied": applied,
            "torn": scanned.torn_fragment is not None}


def rebuild(connection, log, now):
    """Drop every derived table and reconstruct it from the log alone.

    This is the executable proof of ADR-012 D-05: if the index can always be
    rebuilt from the log, then the log -- not the index -- is the truth. It is
    exposed to the operator as `reset --rebuild-index`.

    The append-only triggers are dropped and recreated around the rebuild,
    because rebuilding is not mutation of history: the history is the log, and
    it is not touched here.
    """
    with store.immediate_transaction(connection):
        for table in schema_module.APPEND_ONLY_TABLES:
            connection.execute("DROP TRIGGER IF EXISTS %s_no_update" % (table,))
            connection.execute("DROP TRIGGER IF EXISTS %s_no_delete" % (table,))
        for table in ("event_index", "tasks", "commands", "transition_anomalies"):
            connection.execute("DELETE FROM %s" % (table,))
        connection.execute(
            "UPDATE log_cursor SET last_log_sequence = 0, last_byte_offset = 0, "
            "last_event_id = NULL WHERE id = 1")
    result = replay(connection, log, from_log_sequence=0)
    with store.immediate_transaction(connection):
        for table in schema_module.APPEND_ONLY_TABLES:
            for statement in schema_module.append_only_trigger_statements(table):
                connection.execute(statement)
    return result

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

from ..contracts import command as command_contract  # noqa: E402
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
    # PolicyEvaluated is PAYLOAD-DEPENDENT: it carries policy_check -> queued on
    # a permit and policy_check -> blocked on a denial, both approved Catalog
    # section L edges under `policy_gate` authority. The entry below is the
    # PERMIT edge, which is also what every pre-Step-3 event in an existing log
    # means, so old logs replay unchanged. See _policy_target().
    "PolicyEvaluated":          ("policy_check", "queued"),
    # Catalog section L, `blocked -> awaiting_review`, authority orchestrator.
    "HumanReviewRequired":      ("blocked", "awaiting_review"),
    # Also payload-dependent: awaiting_review -> queued (approved) or
    # -> suppressed (rejected), both authority review_gate. The entry records
    # the approval edge; see _review_target().
    "HumanReviewCompleted":     ("awaiting_review", "queued"),
    "TaskClaimed":              ("queued", "claimed"),
    "TaskStarted":              ("claimed", "running"),
    "TaskSucceeded":            ("running", "succeeded"),
    "TaskFailed":               ("running", "failed"),
    "TaskRetryScheduled":       ("failed", "retry_scheduled"),
    "TaskRetryReleased":        ("retry_scheduled", "queued"),
    "TaskDeadLettered":         ("failed", "dead_lettered"),
    "TaskReclaimed":            (None, "queued"),   # from claimed OR running
}

RECLAIMABLE_STATES = ("claimed", "running")
TERMINAL_FLAG = {state: 1 for state in task_states.TERMINAL_STATES}

# Events whose destination state is decided by their own recorded payload
# rather than by a fixed edge. Both are approved Catalog section L transitions;
# what the payload selects is WHICH approved edge, never whether one applies.
#
#   PolicyEvaluated      permit / not_applicable -> queued
#                        deny                    -> blocked
#   HumanReviewCompleted approved -> queued
#                        rejected -> suppressed
#
# TaskReclaimed was already payload-dependent in Step 1, so this is an
# established shape rather than a new one.
POLICY_DECISION_TARGET = {"permit": "queued", "not_applicable": "queued",
                          "deny": "blocked"}
REVIEW_DECISION_TARGET = {"approved": "queued", "rejected": "suppressed"}


def _policy_target(record):
    """Which Catalog section L edge a PolicyEvaluated event carries.

    An unrecognised or absent decision resolves to `blocked`, never to
    `queued`: an event this build cannot interpret must not be able to release
    a task into execution. Constitution section 5.2 -- absence of a known
    permission is not permission.

    A pre-Step-3 event records `decision: "not_applicable"`, which maps to
    `queued`, so every existing log replays to exactly the state it produced
    before.
    """
    decision = record.event["payload"].get("decision")
    return POLICY_DECISION_TARGET.get(decision, "blocked")


def _review_target(record):
    """Which Catalog section L edge a HumanReviewCompleted event carries.

    An unrecognised decision resolves to `suppressed` -- terminal and visible.
    Releasing a task to `queued` on a decision this build cannot read would let
    an unreadable review record authorize execution.
    """
    decision = record.event["payload"].get("decision")
    return REVIEW_DECISION_TARGET.get(decision, "suppressed")

# Every column below is COPIED from an event payload, never computed while
# applying one. That single rule is what makes the whole index rebuildable:
# rebuild it a year later, with the clock advanced, and every row is
# byte-identical, because nothing on this path can ask what time it is.
#
# The two exceptions are increments, and both are deterministic by
# construction. `attempt = attempt + 1` rides inside the guarded UPDATE of the
# claimed -> running transition, so "increments exactly once per execution" and
# "replay does not increment" are the same property of one statement rather
# than two behaviours a caller must remember to coordinate. lease_generation is
# copied from the payload AND compare-and-set against its predecessor, so the
# increment and the record cannot silently diverge.

_LEASE_COLUMNS = ("lease_holder", "lease_generation", "lease_acquired_at",
                  "lease_expires_at", "lease_ttl_ms")


def _clear_lease():
    """Release the lease, PRESERVING the generation.

    The generation is never reset -- it only increases, which is what makes it
    a valid compare-and-set token across reclaims. Resetting it would let a
    stale execution's generation match a fresh lease and defeat the
    holder verification in Architecture section 24.
    """
    return [("lease_holder", None), ("lease_acquired_at", None),
            ("lease_expires_at", None), ("lease_ttl_ms", None)]


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


def apply_transition(connection, record, from_state, to_state,
                     assignments=None, expressions=None, guards=None):
    """Apply one task-state transition. The guarded UPDATE described above.

    `assignments`  -- (column, value) pairs bound as parameters. Every one is a
                      value COPIED from the event payload.
    `expressions`  -- (column, sql) pairs, for the two deterministic increments.
    `guards`       -- (column, value) pairs appended to the WHERE clause, which
                      is how Architecture section 18.1's compare-and-set on
                      (taskId, leaseGeneration) is expressed.

    All three ride INSIDE the one guarded statement rather than following it.
    That is the whole point: a separate UPDATE could be applied when the guard
    did not match, and then "applied exactly once" would be a convention rather
    than a property of the statement.
    """
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

    set_clauses = ["state = ?", "terminal = ?", "last_log_sequence = ?"]
    parameters = [to_state, TERMINAL_FLAG.get(to_state, 0), record.log_sequence]
    for column, value in (assignments or ()):
        set_clauses.append("%s = ?" % (column,))
        parameters.append(value)
    for column, expression in (expressions or ()):
        set_clauses.append("%s = %s" % (column, expression))

    where_clauses = ["task_id = ?", "state = ?", "last_log_sequence < ?"]
    where_parameters = [task_id, effective_from, record.log_sequence]
    for column, value in (guards or ()):
        where_clauses.append("%s = ?" % (column,))
        where_parameters.append(value)

    cursor = connection.execute(
        "UPDATE tasks SET %s WHERE %s"
        % (", ".join(set_clauses), " AND ".join(where_clauses)),
        tuple(parameters + where_parameters),
    )
    if cursor.rowcount != 1:
        runtime_errors.fail(
            "guarded transition %s -> %s for task %s changed %d rows"
            % (effective_from, to_state, task_id, cursor.rowcount),
            runtime_errors.ReplayDivergenceError,
        )
    return ApplyOutcome(APPLIED, "%s -> %s" % (effective_from, to_state))


def _default_attempt_limit():
    """The committed Catalog section A default, read rather than re-declared.

    A Step 1 CommandAccepted or TaskRequested event carries no attemptLimit,
    because the field did not exist when it was written. Falling back to the
    CONTRACT's default -- not to a literal 3 typed here -- is what keeps a v1
    log replaying into a v2 schema with the same value the contract would have
    given it, rather than with a number that merely happens to match today.
    """
    return command_contract.COMMAND_DEFAULTS["attemptLimit"]


def _apply_command_accepted(connection, record):
    payload = record.event["payload"]
    connection.execute(
        "INSERT OR IGNORE INTO commands ("
        " command_id, command_type, command_version, workflow_id, correlation_id,"
        " idempotency_key, target_capability, issued_at, issued_by, payload_hash,"
        " payload_json, accepted_log_sequence, task_id, attempt_limit,"
        " input_refs_json"
        ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,NULL,?,?)",
        (payload["commandId"], payload["commandType"], payload["commandVersion"],
         record.event["workflowId"], record.event["correlationId"],
         payload["idempotencyKey"], payload["targetCapability"],
         payload["issuedAt"], payload["issuedBy"], payload["payloadHash"],
         json.dumps(payload["commandPayload"], sort_keys=True,
                    separators=(",", ":"), ensure_ascii=False),
         record.log_sequence,
         payload.get("attemptLimit", _default_attempt_limit()),
         json.dumps(list(payload.get("inputRefs") or []), sort_keys=True,
                    separators=(",", ":"), ensure_ascii=False)),
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
        " last_log_sequence, terminal, attempt_limit, retry_policy,"
        " lease_generation"
        ") VALUES (?,?,?,?,?,?,?,?,?,?,0,?,?,0)",
        (task_id, record.event["workflowId"], record.event["correlationId"],
         payload["commandId"], payload["capabilityId"], payload["idempotencyKey"],
         "requested", 0, record.log_sequence, record.log_sequence,
         payload.get("attemptLimit", _default_attempt_limit()),
         # The policy RESOLVED at task creation, recorded so that a later change
         # to a capability's declared defaults cannot retroactively alter the
         # schedule of a task that is already running.
         json.dumps(payload.get("retryPolicy", {}), sort_keys=True,
                    separators=(",", ":"))),
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
    _record_attempt(connection, record, to_state)


def _record_attempt(connection, record, to_state):
    """One row per completed execution, inserted whole, exactly once.

    Every value is copied from the outcome event's payload or envelope. The
    start values travel IN the outcome payload rather than being looked up,
    which keeps the row a pure function of one durable event and keeps the
    UNIQUE (task_id, attempt) constraint meaningful: it can only ever be
    violated by an attempt genuinely being recorded twice.

    A Step 1 event carries none of these fields, so a v1 log replayed into a v2
    schema records no attempt history -- correct, because none existed. `audit`
    labels such tasks explicitly rather than reporting a misleading zero.
    """
    payload = record.event["payload"]
    attempt = payload.get("attempt")
    started_at = payload.get("startedAtUtc")
    started_sequence = payload.get("startedLogSequence")
    if attempt is None or started_at is None or started_sequence is None:
        return False
    connection.execute(
        "INSERT INTO task_attempts ("
        " task_id, attempt, lease_generation, started_log_sequence,"
        " finished_log_sequence, outcome, error_class, result_hash,"
        " started_at, finished_at"
        ") VALUES (?,?,?,?,?,?,?,?,?,?)",
        (record.event["taskId"], attempt, payload.get("leaseGeneration", 0),
         started_sequence, record.log_sequence,
         "succeeded" if to_state == "succeeded" else "failed",
         record.event.get("errorClass"), payload.get("resultHash"),
         started_at, record.event["recordedAt"]),
    )
    return True


def resolved_transition(record):
    """The edge an event ACTUALLY carries, payload included, or None.

    The static TRANSITIONS table cannot answer this for the payload-dependent
    events: PolicyEvaluated carries `policy_check -> blocked` on a denial, not
    the `-> queued` the table lists. Any reader that consulted the table alone
    would report the wrong edge -- which is the same class of defect as
    recording a decision that was never made, so the resolution lives here,
    beside the apply path, and every reader uses it.
    """
    event_type = record.event_type
    edge = TRANSITIONS.get(event_type)
    if edge is None:
        return None
    if event_type == "PolicyEvaluated":
        return ("policy_check", _policy_target(record))
    if event_type == "HumanReviewCompleted":
        return ("awaiting_review", _review_target(record))
    if event_type == "TaskReclaimed":
        # From claimed OR running; the payload records which.
        return (record.event["payload"].get("reclaimedFrom"), "queued")
    return edge


def _record_policy_decision(connection, record):
    """One derived row per gate decision, rebuilt from the log.

    Every value is copied from the event. This table exists so that an operator
    can answer "what was blocked, when, why, and under which policy version"
    without reading the log by hand -- Constitution section 13.
    """
    payload = record.event["payload"]
    operations = payload.get("requestedOperations")
    connection.execute(
        "INSERT OR IGNORE INTO policy_decisions ("
        " task_id, log_sequence, decided_at, decision, reason, operation_class,"
        " requested_operations, subject_source_id, authorization_id,"
        " policy_status, policy_version, record_hash"
        ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (record.event["taskId"], record.log_sequence,
         record.event["recordedAt"], payload.get("decision"),
         payload.get("reason"), payload.get("operationClass"),
         None if operations is None else json.dumps(list(operations),
                                                    sort_keys=True,
                                                    separators=(",", ":")),
         payload.get("subjectSourceId"), payload.get("authorizationId"),
         payload.get("policyStatus"), payload.get("policyVersion"),
         payload.get("authorizationRecordHash")),
    )


def _transition_effects(event_type, record):
    """The extra SET/WHERE clauses one event contributes to its own transition.

    Returns (assignments, expressions, guards). Everything here rides inside
    the single guarded UPDATE, so a state fact an event implies commits with
    that event or not at all -- there is no window in which a lease exists but
    its claim does not.
    """
    payload = record.event["payload"]

    if event_type == "TaskClaimed":
        generation = payload.get("leaseGeneration")
        if generation is None:                       # a Step 1 claim: no lease
            return ([], [], [])
        return (
            [("lease_holder", payload.get("leaseHolder")),
             ("lease_generation", generation),
             ("lease_acquired_at", payload.get("leaseAcquiredAt")),
             ("lease_expires_at", payload.get("leaseExpiresAt")),
             ("lease_ttl_ms", payload.get("leaseTtlMs"))],
            [],
            # Architecture section 18.1: compare-and-set on
            # (taskId, leaseGeneration). The claim applies only against the
            # generation it was minted from, so a lease cannot be granted twice
            # from one predecessor even if the state guard were somehow passed.
            [("lease_generation", generation - 1)],
        )

    if event_type == "TaskStarted":
        # The increment, and the ONLY statement in the runtime that touches
        # tasks.attempt. Applied once -> incremented once. Replayed ->
        # last_log_sequence guard fails -> not incremented. Late or illegal ->
        # state guard fails -> not incremented.
        return ([], [("attempt", "attempt + 1")], [])

    if event_type == "PolicyEvaluated":
        # Every value is copied from the payload. The gate's verdict is recorded
        # state, not a re-derivation: nothing here consults the licensing table,
        # the authorization store or a clock, so rebuilding the index replays
        # the decision that was made rather than making a new one.
        return ([("policy_decision", payload.get("decision")),
                 ("policy_reason", payload.get("reason")),
                 ("policy_status", payload.get("policyStatus")),
                 ("policy_version", payload.get("policyVersion")),
                 ("authorization_id", payload.get("authorizationId")),
                 ("operation_class", payload.get("operationClass")),
                 ("subject_source_id", payload.get("subjectSourceId"))], [], [])

    if event_type == "HumanReviewCompleted":
        assignments = [("review_decision", payload.get("decision")),
                       ("review_reason", payload.get("reason")),
                       ("reviewer_identity", payload.get("reviewerIdentity"))]
        # An APPROVAL carries the gate's re-evaluated decision, because a human
        # may un-block a task but only the gate may authorize the acquisition.
        # The permit that later allows dispatch is therefore the gate's,
        # recorded with its own authority and policy version -- copied here,
        # never derived.
        if payload.get("policyDecision") is not None:
            assignments += [
                ("policy_decision", payload.get("policyDecision")),
                ("policy_reason", payload.get("policyReason")),
                ("policy_status", payload.get("policyStatus")),
                ("policy_version", payload.get("reEvaluatedPolicyVersion")),
                ("authorization_id", payload.get("authorizationId"))]
        return (assignments, [], [])

    if event_type == "TaskRetryScheduled":
        return ([("retry_eligible_at", payload.get("eligibleAtUtc")),
                 ("backoff_ms", payload.get("backoffMs"))], [], [])

    if event_type == "TaskRetryReleased":
        return ([("retry_eligible_at", None), ("backoff_ms", None)], [], [])

    if event_type == "TaskDeadLettered":
        return ([("dead_letter_reason", payload.get("reason"))]
                + _clear_lease(), [], [])

    if event_type in ("TaskSucceeded", "TaskFailed"):
        return (_clear_lease(), [], [])

    return ([], [], [])


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
            outcome = apply_transition(connection, record, row["state"], "queued",
                                       assignments=_clear_lease())
        else:
            outcome = ApplyOutcome(ALREADY_APPLIED, "nothing to reclaim")
    elif event_type in TRANSITIONS:
        from_state, to_state = TRANSITIONS[event_type]
        # The two payload-dependent events choose between approved edges.
        if event_type == "PolicyEvaluated":
            to_state = _policy_target(record)
        elif event_type == "HumanReviewCompleted":
            from_state, to_state = "awaiting_review", _review_target(record)
        assignments, expressions, guards = _transition_effects(event_type, record)
        outcome = apply_transition(connection, record, from_state, to_state,
                                   assignments=assignments,
                                   expressions=expressions, guards=guards)
        if outcome.status == APPLIED and event_type in ("TaskSucceeded", "TaskFailed"):
            _apply_task_result(connection, record, to_state)
        if outcome.status == APPLIED and event_type == "PolicyEvaluated":
            _record_policy_decision(connection, record)

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
        # task_attempts joins the rebuildable set: every row in it is derived
        # from an outcome event and must be reconstructed, not preserved.
        # runs, capabilities, command_submissions, recovery_actions and
        # capability_violations are NOT deleted -- they are local observations,
        # and destroying them would lose history the log cannot restore.
        #
        # ORDER MATTERS: task_attempts references tasks, and tasks references
        # commands, so children are deleted before their parents. The pragmas
        # enable foreign keys, so getting this wrong is an IntegrityError
        # rather than a silent orphan -- which is the correct direction, and is
        # how this order was established.
        # policy_decisions joins the rebuildable set: every row is derived from
        # a PolicyEvaluated event. acquisition_authorizations does NOT -- it is
        # governance input, not platform history, and destroying it would lose
        # records the log cannot restore.
        for table in ("event_index", "task_attempts", "policy_decisions",
                      "tasks", "commands", "transition_anomalies"):
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

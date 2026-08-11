#!/usr/bin/env python3
"""MOGO Automation Platform -- the orchestrator: receipt, transitions, dispatch.

AUTHORITY
    Automation Platform Constitution v1.0 (senior) -- sections 4, 6, 7, 11
    ADR-012 (accepted 2026-08-07)                  -- D-02, D-05, D-16
    MOGO-009 Architecture, sections 10, 18.1, 24
    MOGO-009 Contract Catalog, sections A, B, L, O
    MOGO-011 Step 1 plan, sections 8.3, 9, 10, 13

THE ONLY WRITER OF STATE
    Constitution section 7. Every task-state change in the platform originates
    here, and every one of them is an event in the authoritative log before it
    is a row in the derived index.

THE WRITE PROTOCOL, IN ONE PLACE
    _emit() is the only method that appends. It performs, in this order:

        P1  append the complete event line, then fsync          (log = truth)
        P2  BEGIN IMMEDIATE -> index + transition -> COMMIT     (index = derived)
        P3  refresh the human-readable task projection          (cosmetic)

    A crash between P1 and P2 leaves the index behind the log, and replay
    converges. The reverse order could commit a state change with no event,
    which is unrecoverable and violates Constitution section 6.6. The order is
    therefore not a preference; it is the property that makes recovery possible.

ONE EVENT PER TRANSACTION
    Never a batch. Batching would let a torn tail split a logically atomic pair
    and would force batch fields into a committed MOGO-010 envelope. Instead
    every multi-event sequence is resumable, which is why recovery has a rule
    for each intermediate point rather than an all-or-nothing boundary.

MOGO-011 STEP 2 -- WHAT CHANGED, AND WHY EACH WAS A DEFECT RATHER THAN A DESIGN
    * _fail_task() stopped at `failed`, which is NOT terminal. Step 1 was
      explicit that retry and dead-letter were out of scope, but the result was
      a task that never reached a visible terminal outcome -- Constitution
      section 6.5. Step 2 closes it: every failure now resolves to
      retry_scheduled or dead_lettered.
    * recover() reclaimed EVERY task in claimed/running unconditionally, on the
      assumption that single-writer implies the previous holder is gone. The
      assumption is true, and Constitution section 11 requires recovery to
      resume from a VERIFIED checkpoint, "never from an assumed one". The lease
      predicate replaces the assumption with a check over recorded facts.
    * run_once() drove only requested/policy_check/queued. It now also drives
      `failed` and ELIGIBLE `retry_scheduled` -- and deliberately not ineligible
      retry_scheduled, or the loop would select the same task forever.

    The write protocol, the single append site, the guarded UPDATE, the
    log-is-authoritative rule and the worker boundary are all UNCHANGED. Step 2
    adds no new transaction shape; every new fact rides inside the existing
    transaction of the event that implies it.
"""

import json
import os
import uuid as _uuid

from ..contracts import command as command_contract  # noqa: E402
from ..contracts import errors as contract_errors  # noqa: E402
from ..contracts import ids  # noqa: E402
from ..contracts import task_states  # noqa: E402
from . import clock as clock_module  # noqa: E402
from . import errors as runtime_errors  # noqa: E402
from . import event_log as event_log_module  # noqa: E402
from . import lease as lease_module  # noqa: E402
from . import authorizations  # noqa: E402
from . import paths as paths_module  # noqa: E402
from . import policy  # noqa: E402
from . import projection  # noqa: E402
from . import registry  # noqa: E402
from . import retry as retry_module  # noqa: E402
from . import schema as schema_module  # noqa: E402
from . import store  # noqa: E402
from . import worker as worker_module  # noqa: E402
from .capabilities import echo as echo_capability  # noqa: E402
from .capabilities import fail_then_succeed as fail_then_succeed_capability  # noqa: E402
from .capabilities import policy_probe as policy_probe_capability
from .capabilities import ingest_local_artifact as ingest_local_artifact_capability
from .capabilities import acquire_approved_source_metadata as acquire_metadata_capability
from . import result_store as result_store_module  # noqa: E402

PRODUCER_ORCHESTRATOR = "orchestrator"
PRODUCER_POLICY_GATE = "policyGate"
# Catalog section B names `reviewGate` as an approved producer. The disposition
# of a blocked task is issued under that authority, never under the
# orchestrator's own, so the audit trail distinguishes a decision the platform
# made from one a human made.
PRODUCER_REVIEW_GATE = "reviewGate"
PRODUCER_VERSION = "1.0.0"
EVENT_VERSION = 1

CRASH_SIM_ENV = "MOGO_RUNTIME_ALLOW_CRASH_SIM"
CLOCK_OVERRIDE_ENV = "MOGO_RUNTIME_ALLOW_CLOCK_OVERRIDE"

# The capabilities this build registers at init. Two, deliberately: one pure
# capability that always succeeds and one that fails a declared retryable
# failure until a declared attempt. Both are effectClass `pure` -- registration
# of an effectful capability is mechanically refused (risk A-5, decision B-4).
BUILTIN_CAPABILITIES = (echo_capability.MANIFEST,
                        fail_then_succeed_capability.MANIFEST,
                        policy_probe_capability.MANIFEST,
                        # MOGO-014: the first EFFECTFUL capability. Registration
                        # is permitted because runtime/result_store.py satisfies
                        # every A-5 condition; it is still gated by the policy
                        # gate, which demands a real authorization record.
                        ingest_local_artifact_capability.MANIFEST,
                        # MOGO-015 Step 4: the first capability that can reach
                        # outside this machine. It names its connector, so the
                        # connector-scoped gate applies to it.
                        acquire_metadata_capability.MANIFEST)
CAPABILITY_CALLABLES = {
    echo_capability.CAPABILITY_ID: echo_capability.execute,
    fail_then_succeed_capability.CAPABILITY_ID: fail_then_succeed_capability.execute,
    policy_probe_capability.CAPABILITY_ID: policy_probe_capability.execute,
    ingest_local_artifact_capability.CAPABILITY_ID: ingest_local_artifact_capability.execute,
    acquire_metadata_capability.CAPABILITY_ID: acquire_metadata_capability.execute,
}

# `blocked` is drivable, and that is a crash-recovery requirement rather than a
# convenience. A denial emits AcquisitionDenied and then HumanReviewRequired as
# two events; a crash between them leaves the task in `blocked`, which is NOT
# terminal. Without `blocked` in the drivable set such a task has no route out
# at all -- it can neither be reviewed nor reach a terminal outcome, which is
# exactly the Constitution section 6.5 stranding defect Step 2 eliminated for
# failures. Driving it completes the approved `blocked -> awaiting_review` edge.
NON_TERMINAL_RESUMABLE = ("requested", "policy_check", "queued", "failed",
                          "blocked")

# Crash-simulation boundaries added by Step 2, all refused unless the crash-sim
# environment variable is set to 1, exactly as in Step 1.
STEP_2_CRASH_BOUNDARIES = (
    "after_failure_append", "inside_failure_transaction",
    "after_retry_schedule_append", "before_retry_projection",
    "after_retry_release_append", "after_lease_claim", "after_lease_expiry",
    "before_requeue", "during_retry_execution", "before_dead_letter_apply",
    "after_dead_letter_append",
)

# Crash-simulation boundaries added by Step 3, across the gate and the operator
# disposition path. Refused unless the crash-sim environment variable is set,
# exactly as in Steps 1 and 2.
STEP_3_CRASH_BOUNDARIES = (
    "after_policy_decision_append", "after_policy_denial",
    "after_review_required_append", "after_review_decision_append",
)


def producer_for(capability_id):
    """The producer string for a worker acting on behalf of one capability."""
    return "worker:" + capability_id


# Retained under its Step 1 name because the CLI and the demonstration command
# builder call it. It now delegates to the one module permitted to read a clock,
# so there is exactly one real clock read in platform/**.
def utc_now():
    """ISO-8601 UTC at millisecond precision -- the Catalog conventions format."""
    return clock_module.SystemClock().now_iso()


class _CallableClock(clock_module.Clock):
    """Adapts a Step 1 bare `clock()` callable to the Step 2 Clock protocol.

    Present so that a caller holding the older constructor contract keeps
    working rather than failing obscurely. now_ms() is derived from the same
    string the callable produced, so the two readings cannot disagree.
    """

    def __init__(self, callable_):
        self._callable = callable_

    def now_iso(self):
        return self._callable()

    def now_ms(self):
        return clock_module.parse_iso8601_ms(self.now_iso(), "now")


class SubmitOutcome(object):
    __slots__ = ("status", "command_id", "task_id", "workflow_id",
                 "idempotency_key", "reason")

    def __init__(self, status, command_id=None, task_id=None, workflow_id=None,
                 idempotency_key=None, reason=None):
        self.status = status
        self.command_id = command_id
        self.task_id = task_id
        self.workflow_id = workflow_id
        self.idempotency_key = idempotency_key
        self.reason = reason


class Orchestrator(object):
    """One-process, one-shot orchestration kernel."""

    def __init__(self, paths=None, clock=None, uuid_factory=None,
                 crash_at=None, create=True):
        self.paths = paths or paths_module.default_paths()
        if clock is None:
            self._clock = clock_module.SystemClock()
        elif isinstance(clock, clock_module.Clock):
            self._clock = clock
        else:
            self._clock = _CallableClock(clock)
        self._uuid_factory = uuid_factory or _uuid.uuid4
        self._crash_at = crash_at
        self._create = create
        self.log = event_log_module.EventLog(self.paths)
        self.connection = None
        self._lock = None
        self.trace = []
        # Minted once per run. Not a PID (reused, and meaningless after a
        # reboot) and not a hostname (single-host by construction). Recorded in
        # every TaskClaimed payload, so replay reproduces the holder exactly.
        self.run_id = ids.new_uuid4(uuid_factory=self._uuid_factory)
        self.lease_holder = lease_module.holder_for_run(self.run_id)
        self._floor = clock_module.MonotonicFloor()

    # -- lifecycle -----------------------------------------------------------

    def open(self, create=None):
        """Acquire the single-writer lock, open the index, ensure the schema.

        Idempotent: calling open() on an already-open runtime returns it
        unchanged rather than taking the process lock a second time. flock is
        per open-file-description, so a second acquire from the same process
        would deadlock against itself -- the lock is right, a double-open is not.
        """
        if self._lock is not None:
            return self
        create = self._create if create is None else create
        paths_module.ensure_state_root(self.paths)
        self._lock = store.ProcessLock(self.paths).acquire()          # R1
        self.connection = store.open_database(self.paths, create=create)
        schema_module.initialize(self.connection, self._clock.now_iso())
        self._load_monotonic_floor()                                  # R1b
        self._record_run_start()
        return self

    def _assert_clock_not_rolled_back(self, phase):
        """R1b -- refuse to ACT on a clock that has gone backwards.

        The append-time guard in _emit() is not sufficient on its own. Recovery
        and release both make DECISIONS from `now` before they append anything:
        with a rolled-back clock, `reclaim_reason` would find an expired lease
        live and simply decline to reclaim it, and the runtime would appear to
        work while silently reasoning from a time that never happened.

        So the clock is checked before either phase begins, and a refusal is
        recorded rather than merely raised -- Constitution section 6.6: a path
        that can end without a recorded outcome is a defect.
        """
        now = self._clock.now_iso()
        try:
            self._floor.check(now)
        except runtime_errors.ClockRollbackError as exc:
            # detected_at carries the value the clock ACTUALLY returned. It is
            # the wrong time, and that is precisely the fact being recorded;
            # substituting the floor here would be the runtime writing a
            # timestamp of its own invention into its own audit trail.
            with store.immediate_transaction(self.connection):
                self.connection.execute(
                    "INSERT INTO recovery_actions "
                    "(detected_at, action, subject, detail) VALUES (?,?,?,?)",
                    (now, "clock_rollback_refused", phase, str(exc)))
            raise
        return now

    def _load_monotonic_floor(self):
        """Raise the append-time floor to the highest timestamp already recorded.

        Read from the index rather than the log because the index is present
        before replay and the log is scanned later in recovery; R3 then observes
        every replayed event's recordedAt as well, so a torn or unindexed tail
        cannot leave the floor too low.
        """
        row = self.connection.execute(
            "SELECT MAX(recorded_at) AS highest FROM event_index").fetchone()
        if row is not None and row["highest"]:
            self._floor.observe(row["highest"])

    def _record_run_start(self):
        """Record this run in the `runs` table -- a LOCAL OBSERVATION.

        Which run held which lease is useful for audit and meaningless to
        replay, so it is stored here rather than derived from the log, and is
        named as non-replayable alongside command_submissions and
        transition_anomalies.
        """
        with store.immediate_transaction(self.connection):
            self.connection.execute(
                "INSERT OR REPLACE INTO runs (run_id, started_at, ended_at, pid) "
                "VALUES (?,?,NULL,?)",
                (self.run_id, self._clock.now_iso(), os.getpid()))

    def close(self):
        if self.connection is not None:
            try:
                with store.immediate_transaction(self.connection):
                    self.connection.execute(
                        "UPDATE runs SET ended_at = ? WHERE run_id = ?",
                        (self._clock.now_iso(), self.run_id))
            except Exception:  # noqa: BLE001 - closing must never fail the run
                # The run's work is already durable in the log. A failure to
                # stamp an audit-only end time must not turn a successful run
                # into a failed one.
                pass
            self.connection.close()
            self.connection = None
        if self._lock is not None:
            self._lock.release()
            self._lock = None

    def __enter__(self):
        return self.open(self._create)

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    def register_builtin_capabilities(self):
        outcomes = {}
        with store.immediate_transaction(self.connection):
            for manifest in BUILTIN_CAPABILITIES:
                outcomes[manifest["capabilityId"]] = registry.register(
                    self.connection, manifest, self._clock.now_iso())
        return outcomes

    # -- induced interruption (test-only) ------------------------------------

    def _crash_point(self, name):
        if self._crash_at != name:
            return
        if os.environ.get(CRASH_SIM_ENV) != "1":
            runtime_errors.fail(
                "crash simulation requested at %r but %s is not set to 1"
                % (name, CRASH_SIM_ENV),
                runtime_errors.RuntimeError_,
            )
        self._note("SIMULATED CRASH at %s" % (name,))
        # os._exit: no unwinding, no finally, no flush -- what a real kill does.
        os._exit(70)

    def _note(self, message):
        self.trace.append(message)

    # -- the write protocol --------------------------------------------------

    def _next_sequence(self, workflow_id):
        row = self.connection.execute(
            "SELECT MAX(sequence) AS highest FROM event_index WHERE workflow_id = ?",
            (workflow_id,)).fetchone()
        highest = row["highest"] if row and row["highest"] is not None else -1
        return highest + 1

    def _emit(self, event_type, workflow_id, correlation_id, causation_id,
              payload, task_id=None, producer=PRODUCER_ORCHESTRATOR,
              subject_refs=None, execution_result=None, error_class=None,
              policy_context=None, crash_after_append=None):
        """Append one event, then apply it. The only write path in the runtime."""
        now = self._clock.now_iso()
        # The monotonic guard, BEFORE the append. A clock that went backwards
        # aborts the operation with nothing written, rather than stamping an
        # event earlier than the one it follows. No skew tolerance and no
        # forward clamp: both would record a time the clock never produced.
        self._floor.accept(now)
        envelope = {
            "eventId": ids.new_uuid4(uuid_factory=self._uuid_factory),
            "eventType": event_type,
            "eventVersion": EVENT_VERSION,
            "workflowId": workflow_id,
            "correlationId": correlation_id,
            "causationId": causation_id,
            "producer": producer,
            "producerVersion": PRODUCER_VERSION,
            "occurredAt": now,
            "recordedAt": now,
            "subjectRefs": list(subject_refs or []),
            "payload": payload,
            "payloadHash": ids.content_hash_of(payload),
            "sequence": self._next_sequence(workflow_id),
        }
        if task_id is not None:
            envelope["taskId"] = task_id
        if execution_result is not None:
            envelope["executionResult"] = execution_result
        if error_class is not None:
            envelope["errorClass"] = error_class
        if policy_context is not None:
            envelope["policyContext"] = policy_context

        record = self.log.append(envelope)                       # P1: durable
        if crash_after_append:
            self._crash_point(crash_after_append)
        with store.immediate_transaction(self.connection):       # P2: derived
            outcome = projection.apply_event(self.connection, record)
        self._project_task(task_id)                              # P3: cosmetic
        self._note("%-26s seq=%d %s" % (event_type, record.log_sequence,
                                        outcome.detail or ""))
        return record

    def _project_task(self, task_id):
        """Human-readable filesystem view of task state (ADR-012 D-03).

        Derived and cosmetic: nothing reads it back for correctness. A failure
        here must never fail the run, because the truth is already durable.
        """
        if not task_id:
            return
        row = self.connection.execute(
            "SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        if row is None:
            return
        target = self.paths.task_projection_file(row["state"], task_id)
        self.paths.assert_inside_state_root(target, purpose="project task")
        os.makedirs(os.path.dirname(target), exist_ok=True)
        document = {key: row[key] for key in row.keys()}
        temporary = target + ".tmp"
        self.paths.assert_inside_state_root(temporary, purpose="project task")
        with open(temporary, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(document, indent=2, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        for state in task_states.TASK_STATES:
            if state == row["state"]:
                continue
            stale = self.paths.task_projection_file(state, task_id)
            if os.path.exists(stale):
                self.paths.assert_inside_state_root(stale, purpose="prune projection")
                os.remove(stale)

    # -- recovery ------------------------------------------------------------

    def recover(self):
        """Startup recovery, phases R2-R5 (R1 is the lock, taken in open()).

        Deterministic and idempotent: running it twice changes nothing the
        second time.
        """
        report = {"quarantined": None, "replayed": 0, "reclaimed": [],
                  "resumed_commands": [], "reclaim_reasons": {},
                  "live_leases_kept": []}

        # R1b -- the clock, before anything reasons from it.
        self._assert_clock_not_rolled_back("recover")

        # R2 -- torn tail. A fragment is not an event; quarantine then truncate.
        quarantined = self.log.repair_torn_tail(self._clock.now_iso())
        if quarantined:
            report["quarantined"] = quarantined
            self._record_recovery("torn_tail_quarantined", quarantined, None)
            self._note("RECOVERY quarantined torn append -> %s" % (quarantined,))

        # R3 -- replay everything the index missed.
        replayed = projection.replay(self.connection, self.log)
        report["replayed"] = replayed["applied"]
        if replayed["applied"]:
            self._note("RECOVERY replayed %d event(s) into the index"
                       % (replayed["applied"],))
        self._load_monotonic_floor()

        # R4 -- reclaim tasks stranded mid-flight, BY VERIFIED PREDICATE.
        #
        # Step 1 reclaimed every task in claimed/running unconditionally,
        # justified by "single-writer, so the previous holder is gone". That is
        # true, and it is an ASSUMPTION; Constitution section 11 requires
        # recovery to resume from a verified checkpoint, "never from an assumed
        # one". The lease turns it into a check over recorded facts, and a task
        # whose lease is genuinely live is LEFT ALONE rather than swept up.
        now_ms = self._clock.now_ms()
        stranded = self.connection.execute(
            "SELECT task_id, workflow_id, correlation_id, state, attempt,"
            "       lease_holder, lease_generation, lease_expires_at "
            "FROM tasks WHERE state IN (?, ?)",
            projection.RECLAIMABLE_STATES).fetchall()
        for row in stranded:
            expires_ms = (None if not row["lease_expires_at"]
                          else clock_module.parse_iso8601_ms(
                              row["lease_expires_at"], "leaseExpiresAt"))
            reason = lease_module.reclaim_reason(
                row["lease_holder"], expires_ms, now_ms, self.lease_holder)
            if reason is None:
                # Our own lease, still live. Refusing to reclaim it is the whole
                # point of the predicate -- this is the case Step 1 could not
                # express.
                report["live_leases_kept"].append(row["task_id"])
                self._record_recovery("live_lease_not_reclaimed", row["task_id"],
                                      row["lease_expires_at"])
                continue
            self._crash_point("after_lease_expiry")
            self._emit(
                "TaskReclaimed", row["workflow_id"], row["correlation_id"],
                row["task_id"],
                {"reclaimedFrom": row["state"],
                 "reason": reason,
                 "previousLeaseHolder": row["lease_holder"],
                 "previousLeaseGeneration": row["lease_generation"],
                 "leaseExpiresAt": row["lease_expires_at"],
                 "observedAtUtc": self._clock.now_iso(),
                 "attempt": row["attempt"]},
                task_id=row["task_id"], producer=PRODUCER_ORCHESTRATOR,
                crash_after_append="before_requeue",
            )
            report["reclaimed"].append(row["task_id"])
            report["reclaim_reasons"][row["task_id"]] = reason
            self._record_recovery("task_reclaimed", row["task_id"],
                                  "%s (%s)" % (row["state"], reason))

        # R5 -- resume command lifecycles interrupted before task creation.
        orphans = self.connection.execute(
            "SELECT command_id FROM commands WHERE task_id IS NULL").fetchall()
        for row in orphans:
            self._resume_command(row["command_id"])
            report["resumed_commands"].append(row["command_id"])
            self._record_recovery("command_resumed", row["command_id"], None)

        return report

    def _record_recovery(self, action, subject, detail):
        with store.immediate_transaction(self.connection):
            self.connection.execute(
                "INSERT INTO recovery_actions (detected_at, action, subject, detail) "
                "VALUES (?,?,?,?)",
                (self._clock.now_iso(), action, subject, detail))

    def _record_capability_violation(self, capability_id, task_id, violation,
                                     detail):
        """Constitution section 7: a worker may not emit what it has not declared.

        Recorded rather than raised: the task still reaches a terminal outcome,
        under a non-retryable class, and the violation is visible to an operator
        instead of being inferred from an odd error message.
        """
        with store.immediate_transaction(self.connection):
            self.connection.execute(
                "INSERT INTO capability_violations "
                "(detected_at, capability_id, task_id, violation, detail) "
                "VALUES (?,?,?,?,?)",
                (self._clock.now_iso(), capability_id, task_id, violation, detail))

    def _resume_command(self, command_id):
        """Crash boundary 3: a command was accepted but its task never created.

        A NEW taskId is minted, which is safe: no task existed, and the
        idempotency key is already claimed, so a re-submission still cannot
        create a second task.
        """
        row = self.connection.execute(
            "SELECT * FROM commands WHERE command_id = ?", (command_id,)).fetchone()
        if row is None or row["task_id"]:
            return None
        self._note("RECOVERY resuming command %s (no task was created)" % (command_id,))
        return self._create_task(row)

    # -- command receipt -----------------------------------------------------

    def submit(self, envelope, payload):
        """Validate and accept a command. Returns a SubmitOutcome.

        Fail-closed: an invalid command creates no task, appends a
        CommandRejected event, and records the attempt. A duplicate creates
        nothing and appends nothing -- the append-only submissions table carries
        the fact instead, because no approved event names a suppressed duplicate.
        """
        submitted_at = self._clock.now_iso()
        try:
            validated = command_contract.validate_command(envelope, payload=payload)
        except runtime_errors.PlatformError as exc:
            return self._reject(envelope, payload, submitted_at, str(exc),
                                type(exc).__name__)

        # Constitution section 11 requires retry to be BOUNDED. Catalog section
        # A validates attemptLimit >= 1 and sets no upper bound, so the ceiling
        # is enforced here (decision B-5) and the refusal is recorded rather
        # than silent -- a rejected command is still a visible fact.
        if "attemptLimit" in validated \
                and validated["attemptLimit"] > retry_module.MAX_ATTEMPT_LIMIT:
            return self._reject(
                envelope, payload, submitted_at,
                "attemptLimit %d exceeds the runtime ceiling of %d"
                % (validated["attemptLimit"], retry_module.MAX_ATTEMPT_LIMIT),
                "RetryPolicyError")

        # Resolve the attempt limit HERE, where it is still known whether the
        # command declared one or merely inherited the Catalog default. Once the
        # command is projected that distinction is gone, and a stored default
        # would silently outrank a capability's own declared limit.
        try:
            resolved_limit = self._resolve_attempt_limit(validated)
        except runtime_errors.PlatformError as exc:
            return self._reject(envelope, payload, submitted_at, str(exc),
                                type(exc).__name__)

        idempotency_key = validated["idempotencyKey"]
        existing = self.connection.execute(
            "SELECT command_id, task_id FROM commands WHERE idempotency_key = ?",
            (idempotency_key,)).fetchone()
        if existing is not None:
            with store.immediate_transaction(self.connection):
                self.connection.execute(
                    "INSERT INTO command_submissions "
                    "(submitted_at, idempotency_key, command_id, outcome, reason) "
                    "VALUES (?,?,?,?,?)",
                    (submitted_at, idempotency_key, existing["command_id"],
                     "duplicate_suppressed",
                     "identical idempotency key already accepted"))
            self._note("DUPLICATE SUPPRESSED -> command %s task %s"
                       % (existing["command_id"], existing["task_id"]))
            return SubmitOutcome("duplicate_suppressed",
                                 command_id=existing["command_id"],
                                 task_id=existing["task_id"],
                                 idempotency_key=idempotency_key)

        workflow_id = validated["workflowId"]
        correlation_id = validated["correlationId"]

        self._emit("WorkflowStarted", workflow_id, correlation_id,
                   validated["causationId"],
                   {"workflowType": "runtime.demonstration.v1",
                    "commandType": validated["commandType"]})

        accepted_payload = {
            "commandId": validated["commandId"],
            "commandType": validated["commandType"],
            "commandVersion": validated["commandVersion"],
            "idempotencyKey": idempotency_key,
            "targetCapability": validated["targetCapability"],
            "issuedAt": validated["issuedAt"],
            "issuedBy": validated["issuedBy"],
            "payloadHash": validated["payloadHash"],
            "commandPayload": ids.as_plain(payload),
            "attemptLimit": resolved_limit,
            # Identifiers only. The policy gate resolves an acquisition's
            # subject source from these, so they must be in the authoritative
            # log rather than only in the submitted envelope.
            "inputRefs": list(validated["inputRefs"]),
        }
        self._emit("CommandAccepted", workflow_id, correlation_id,
                   validated["commandId"], accepted_payload,
                   crash_after_append="after_command_append")
        with store.immediate_transaction(self.connection):
            self.connection.execute(
                "INSERT INTO command_submissions "
                "(submitted_at, idempotency_key, command_id, outcome, reason) "
                "VALUES (?,?,?,?,NULL)",
                (submitted_at, idempotency_key, validated["commandId"], "accepted"))

        self._crash_point("before_task_create")
        command_row = self.connection.execute(
            "SELECT * FROM commands WHERE command_id = ?",
            (validated["commandId"],)).fetchone()
        task_id = self._create_task(command_row)
        return SubmitOutcome("accepted", command_id=validated["commandId"],
                             task_id=task_id, workflow_id=workflow_id,
                             idempotency_key=idempotency_key)

    def _resolve_attempt_limit(self, validated):
        """Command override, else the capability's declared policy, else the
        committed Catalog default -- in that order, decided once.

        The command wins only when it actually declared a limit. A default that
        merely looks like a declaration would silently outrank a capability's
        own bound, which is the kind of precedence bug that is invisible until
        the two values differ.
        """
        capability_row = registry.lookup(self.connection,
                                         validated["targetCapability"])
        declared = (registry.declared_retry_policy(capability_row)
                    if capability_row is not None else None)
        override = validated["attemptLimit"] if "attemptLimit" in validated else None
        return retry_module.resolve_policy(
            declared or None, attempt_limit_override=override)["attemptLimit"]

    def _reject(self, envelope, payload, submitted_at, reason, rejection_class):
        """Record a rejection without echoing the rejected content into the log.

        The full human-readable reason goes to the append-only
        command_submissions table, which `audit` prints in full. The
        CommandRejected event carries only the rejection CLASS and the
        submission id.

        That split is deliberate and load-bearing. A validation message names
        the value that failed, and the value that failed may be exactly the
        thing the boundary forbids -- a command whose inputRefs point at a
        protected scientific path produces a message containing that path. Were
        the message copied into an event payload, the envelope validator would
        (correctly) refuse to record the rejection at all, and a refused command
        would vanish silently, which Constitution section 6.6 forbids. Keeping
        the detail in the derived table and the classification in the log keeps
        both rules satisfied at once, and loses no information.
        """
        key = envelope.get("idempotencyKey") if hasattr(envelope, "get") else None
        workflow_id = envelope.get("workflowId") if hasattr(envelope, "get") else None
        correlation_id = (envelope.get("correlationId")
                          if hasattr(envelope, "get") else None)

        with store.immediate_transaction(self.connection):
            cursor = self.connection.execute(
                "INSERT INTO command_submissions "
                "(submitted_at, idempotency_key, command_id, outcome, reason) "
                "VALUES (?,?,NULL,?,?)",
                (submitted_at, key if isinstance(key, str) else "<unvalidated>",
                 "rejected", reason))
            submission_id = cursor.lastrowid

        if ids.is_uuid4(workflow_id or "") and ids.is_uuid4(correlation_id or ""):
            self._emit("CommandRejected", workflow_id, correlation_id,
                       correlation_id,
                       {"rejectionClass": rejection_class,
                        "submissionId": submission_id,
                        "detailRecordedIn": "command_submissions"})
        self._note("REJECTED [%s] %s" % (rejection_class, reason))
        return SubmitOutcome("rejected", reason=reason)

    def _create_task(self, command_row):
        task_id = ids.new_uuid4(uuid_factory=self._uuid_factory)
        capability_row = registry.lookup(self.connection,
                                         command_row["target_capability"])
        capability_id = (capability_row["capability_id"] if capability_row is not None
                         else command_row["target_capability"])

        # Resolve the retry policy ONCE, here, and record it in the event.
        # Precedence: the command's attemptLimit, else the capability's declared
        # policy, else the committed contract default. Recording the RESOLVED
        # policy at task creation is what makes tasks.attempt_limit rebuildable
        # and what stops a later change to a capability's declared defaults from
        # retroactively altering the schedule of a task already in flight.
        declared = (registry.declared_retry_policy(capability_row)
                    if capability_row is not None else None)
        policy = retry_module.resolve_policy(
            declared or None,
            attempt_limit_override=command_row["attempt_limit"])

        self._emit(
            "TaskRequested", command_row["workflow_id"],
            command_row["correlation_id"], command_row["command_id"],
            {"commandId": command_row["command_id"],
             "capabilityId": capability_id,
             "idempotencyKey": command_row["idempotency_key"],
             "attemptLimit": policy["attemptLimit"],
             "retryPolicy": dict(policy)},
            task_id=task_id,
        )
        return task_id

    # -- execution -----------------------------------------------------------

    def run_once(self):
        """Drive every non-terminal task as far as it can go. Returns a report.

        R6 -- releasing retries whose backoff has elapsed -- lives HERE and not
        in recover(), deliberately. recover() repairs the past; run_once() makes
        forward progress. A release inside recovery would mean `submit`, which
        calls recover(), silently advanced retries -- a side effect the operator
        did not ask for.

        TERMINATION. The loop adds `failed` and ELIGIBLE `retry_scheduled` to
        the drivable set, and must not add ineligible retry_scheduled or it
        would select the same task forever. Every iteration either advances a
        task's state or removes it from the drivable set: a task that fails and
        reschedules with a non-zero backoff leaves immediately, and a task with
        a zero backoff re-enters but consumes an attempt each time. Termination
        is therefore bounded by MAX_ATTEMPT_LIMIT x tasks.
        """
        report = {"advanced": [], "succeeded": [], "failed": [], "retried": [],
                  "dead_lettered": [], "released": [], "abandoned": [],
                  "blocked": []}
        # A release decision is made from `now` before anything is appended, so
        # the clock is checked before the first one rather than at the append.
        self._assert_clock_not_rolled_back("run")
        # A task the dispatch guard refuses stays in `queued` -- it is a
        # corruption case, and moving it would be inventing a transition nobody
        # authorized. It must therefore be excluded from re-selection, or the
        # loop would offer the same task forever. Tracked in memory rather than
        # written, because the refusal is already recorded as an anomaly and the
        # exclusion lasts only for this run.
        refused = set()
        while True:
            report["released"].extend(self._release_eligible_retries())
            row = None
            for candidate in self.connection.execute(
                    "SELECT * FROM tasks WHERE terminal = 0 AND state IN (%s) "
                    "ORDER BY created_log_sequence"
                    % (",".join("?" * len(NON_TERMINAL_RESUMABLE)),),
                    NON_TERMINAL_RESUMABLE):
                if candidate["task_id"] not in refused:
                    row = candidate
                    break
            if row is None:
                break
            outcome = self._advance(row)
            report["advanced"].append(row["task_id"])
            if outcome == "succeeded":
                report["succeeded"].append(row["task_id"])
            elif outcome == "failed":
                report["failed"].append(row["task_id"])
            elif outcome == "retried":
                report["retried"].append(row["task_id"])
            elif outcome == "dead_lettered":
                report["dead_lettered"].append(row["task_id"])
            elif outcome == "abandoned":
                report["abandoned"].append(row["task_id"])
            elif outcome == "blocked":
                report["blocked"].append(row["task_id"])
            elif outcome == "unauthorized":
                report["abandoned"].append(row["task_id"])
                refused.add(row["task_id"])
        return report

    def _advance(self, task_row):
        task_id = task_row["task_id"]
        workflow_id = task_row["workflow_id"]
        correlation_id = task_row["correlation_id"]
        state = task_row["state"]

        if state == "requested":
            self._emit("TaskPolicyCheckRequested", workflow_id, correlation_id,
                       task_id, {"reason": "every task passes through policy_check"},
                       task_id=task_id)
            return "advanced"

        if state == "policy_check":
            return self._evaluate_policy(task_row)

        if state == "queued":
            return self._claim_and_execute(task_row)

        if state == "blocked":
            # Reached only after a crash between the denial and the request for
            # review. The decision itself is already durable and is NOT
            # re-made: this completes the transition the crash interrupted.
            return self._request_review(task_row)

        if state == "failed":
            return self._resolve_failed_task(task_row)

        return "advanced"

    # -- retry scheduling and release ----------------------------------------

    def _resolve_failed_task(self, task_row):
        """`failed` is not terminal. Resolve it to a retry or to a dead letter.

        The decision is made from RECORDED state -- error class, attempt,
        attempt limit -- so a crash between the failure and this decision
        changes nothing: recovery replays the failure and the decision is
        reached again, identically.
        """
        task_id = task_row["task_id"]
        error_class = task_row["error_class"]
        attempt = task_row["attempt"]
        attempt_limit = task_row["attempt_limit"]
        decision = retry_module.classify_failure(error_class, attempt,
                                                 attempt_limit)

        if decision.retry:
            return self._schedule_retry(task_row, decision)
        return self._dead_letter(task_row, decision)

    def _task_policy(self, task_row):
        """The retry policy RESOLVED at this task's creation, from its own row.

        Read from the task rather than from the capability, so that a change to
        a capability's declared defaults cannot alter the schedule of a task
        that is already in flight.
        """
        declared = json.loads(task_row["retry_policy"] or "{}")
        return retry_module.resolve_policy(
            declared or None, attempt_limit_override=task_row["attempt_limit"])

    def _schedule_retry(self, task_row, decision):
        task_id = task_row["task_id"]
        attempt = task_row["attempt"]
        policy = self._task_policy(task_row)
        delay_ms = retry_module.backoff_ms(attempt, policy)
        now_ms = self._clock.now_ms()
        eligible_ms = retry_module.next_eligible_at_ms(now_ms, delay_ms)

        self._emit(
            "TaskRetryScheduled", task_row["workflow_id"],
            task_row["correlation_id"], task_id,
            {"attempt": attempt,
             "attemptLimit": task_row["attempt_limit"],
             "errorClass": task_row["error_class"],
             "decisionReason": decision.reason,
             "backoffMs": delay_ms,
             # Computed ONCE, here, and copied from this payload forever after.
             # Recomputing it during projection would be a NEW deadline, which
             # would make a crash visible in the rebuilt state.
             "eligibleAtUtc": clock_module.format_ms(eligible_ms),
             "scheduledAtUtc": clock_module.format_ms(now_ms),
             # The policy in force, in full, so the schedule is verifiable from
             # the log alone without knowing which build produced it.
             "retryPolicy": {key: policy[key] for key in
                             ("backoffBaseMs", "backoffMultiplier",
                              "backoffCapMs", "jitterMs")}},
            task_id=task_id, producer=PRODUCER_ORCHESTRATOR,
            crash_after_append="after_retry_schedule_append",
        )
        self._crash_point("before_retry_projection")
        return "retried"

    def _release_eligible_retries(self):
        """Release every scheduled retry whose backoff has elapsed. R6.

        ISO-8601 UTC at fixed width and millisecond precision sorts and
        compares lexicographically in the same order as chronologically, so the
        SQL filter and the Python predicate cannot disagree -- and the predicate
        is re-applied anyway, because "cannot disagree" is a claim worth
        checking rather than trusting.
        """
        released = []
        now_iso = self._clock.now_iso()
        now_ms = self._clock.now_ms()
        rows = self.connection.execute(
            "SELECT * FROM tasks WHERE state = 'retry_scheduled' AND terminal = 0 "
            "AND retry_eligible_at IS NOT NULL AND retry_eligible_at <= ? "
            "ORDER BY retry_eligible_at, created_log_sequence", (now_iso,)
        ).fetchall()

        for row in rows:
            eligible_ms = clock_module.parse_iso8601_ms(row["retry_eligible_at"],
                                                        "retryEligibleAt")
            if not retry_module.is_eligible(eligible_ms, now_ms):
                continue
            backoff = row["backoff_ms"] or 0
            scheduled_ms = eligible_ms - backoff
            caused_by = self.connection.execute(
                "SELECT MAX(log_sequence) AS sequence FROM event_index "
                "WHERE task_id = ? AND event_type = 'TaskRetryScheduled'",
                (row["task_id"],)).fetchone()
            self._emit(
                "TaskRetryReleased", row["workflow_id"], row["correlation_id"],
                row["task_id"],
                {"attempt": row["attempt"],
                 "attemptLimit": row["attempt_limit"],
                 "scheduledEligibleAtUtc": row["retry_eligible_at"],
                 "observedAtUtc": now_iso,
                 "waitedMs": now_ms - scheduled_ms,
                 "scheduledBackoffMs": backoff,
                 # Points at the schedule that created the obligation, so the
                 # pair is checkable without matching on timestamps.
                 "causedByLogSequence": (caused_by["sequence"]
                                         if caused_by is not None else None)},
                task_id=row["task_id"], producer=PRODUCER_ORCHESTRATOR,
                crash_after_append="after_retry_release_append",
            )
            released.append(row["task_id"])
        return released

    # -- dead letter ---------------------------------------------------------

    def _attempt_history(self, task_id):
        """Every recorded failed attempt for one task, oldest first."""
        rows = self.connection.execute(
            "SELECT attempt, error_class, finished_at, finished_log_sequence,"
            "       lease_generation FROM task_attempts "
            "WHERE task_id = ? AND outcome = 'failed' ORDER BY attempt",
            (task_id,)).fetchall()
        return [{"attempt": row["attempt"],
                 "errorClass": row["error_class"],
                 "failedAtUtc": row["finished_at"],
                 "logSequence": row["finished_log_sequence"],
                 "leaseGeneration": row["lease_generation"]} for row in rows]

    def _dead_letter(self, task_row, decision):
        """Terminal, visible, and self-contained.

        One event answers "what failed, how often, why, and under which lease",
        so Constitution section 13 is satisfied without following references.
        The history is a SECOND copy of a fact, so a test re-derives it
        independently from the log and compares -- a second copy that is never
        compared is a place for drift to hide.
        """
        task_id = task_row["task_id"]
        observed_class = task_row["error_class"]
        # The ENVELOPE's errorClass is constrained to Catalog section K by the
        # committed contract, so a class the index somehow holds unrecognised
        # cannot go there. The payload's finalErrorClass is free-form and
        # records what was actually observed -- the envelope carries a valid
        # classification, the payload carries the truth, and neither is lost.
        envelope_class = (observed_class
                          if observed_class in contract_errors.ERROR_CLASS_NAMES
                          else worker_module.FALLBACK_ERROR_CLASS)
        self._crash_point("before_dead_letter_apply")
        self._emit(
            "TaskDeadLettered", task_row["workflow_id"],
            task_row["correlation_id"], task_id,
            {"reason": decision.reason,
             "finalErrorClass": observed_class,
             "attempts": task_row["attempt"],
             "attemptLimit": task_row["attempt_limit"],
             "capabilityId": task_row["capability_id"],
             "reviewGateRequired": (decision.reason
                                    == retry_module.REASON_REQUIRES_REVIEW_NO_GATE),
             "attemptHistory": self._attempt_history(task_id)},
            task_id=task_id, execution_result="failure",
            error_class=envelope_class,
            producer=PRODUCER_ORCHESTRATOR,
            crash_after_append="after_dead_letter_append",
        )
        self._emit("WorkflowFailed", task_row["workflow_id"],
                   task_row["correlation_id"], task_id,
                   {"taskId": task_id, "errorClass": observed_class,
                    "deadLetterReason": decision.reason})
        return "dead_lettered"

    def _subject_source(self, task_row):
        """The source an acquisition task concerns, from the command's inputRefs.

        Identifiers only -- Catalog section A: `inputRefs` carries references,
        "never inline payloads". The gate resolves an authorization for this
        source and for no other; a task that names none is denied, because an
        acquisition with no identified subject cannot be authorized.
        """
        row = self.connection.execute(
            "SELECT input_refs_json FROM commands WHERE command_id = ?",
            (task_row["command_id"],)).fetchone()
        if row is None or not row["input_refs_json"]:
            return None
        sources = [ref for ref in json.loads(row["input_refs_json"])
                   if isinstance(ref, str) and ref.startswith("SRC|")]
        # More than one subject is ambiguous, and ambiguity denies rather than
        # picking one: two sources under one authorization decision is a
        # conflict a machine must not resolve.
        return sources[0] if len(sources) == 1 else None

    def _evaluate_policy(self, task_row):
        """THE POLICY GATE. Constitution section 5.1, Architecture section 20.

        Every task passes through here, and the decision is recorded truthfully
        whichever way it goes. A permit reaches `queued`; a denial reaches
        `blocked` and is routed to human review, which is the only authority
        that can release it.

        WHAT THIS REPLACED, AND WHY. Before Step 3 this method recorded
        `decision: "not_applicable"` for an acquisition-class task -- the
        opposite of what happened -- with a null operation class, and then
        emitted TaskClaimed and TaskStarted for an execution that never
        occurred, in order to reach `running` so that a TaskFailed could be
        appended. The outcome was fail-closed; the record of it was a
        fabrication. Constitution section 4.20 requires every governed decision
        to be auditable -- who, what, when, why, under which policy version --
        and an audit trail that misstates the decision is worse than a missing
        one, because it will be believed.
        """
        capability = registry.lookup(self.connection, task_row["capability_id"])
        operation_class = (capability["operation_class"] if capability is not None
                           else None)
        operations = registry.declared_acquisition_operations(capability)

        subject_source = None
        authorization = None
        problem = None
        if operation_class != policy.OPERATION_CLASS_NON_ACQUISITION:
            subject_source = self._subject_source(task_row)
            authorization, problem = authorizations.resolve(self.connection,
                                                            subject_source)

        decision = policy.assert_decision_is_recognised(
            policy.evaluate(operation_class, operations, authorization,
                            self._clock.now_ms(), resolution_problem=problem))

        payload = {
            "decision": decision.decision,
            "reason": decision.reason,
            "operationClass": operation_class,
            "requestedOperations": list(operations),
            "subjectSourceId": subject_source,
            # Constitution section 5.6: the deciding authority and the policy
            # version in force are recorded, or the decision is not auditable.
            "authorizationId": (authorization or {}).get("authorizationId"),
            "policyStatus": (authorization or {}).get("policyStatus"),
            "policyVersion": (authorization or {}).get("policyVersion"),
            "decisionAuthority": (authorization or {}).get("decisionAuthority"),
            "permittedOperations": list(
                (authorization or {}).get("permittedOperations") or []),
            # The record's content hash AS IT STOOD when the decision was made.
            # A later edit is therefore detectable and inert: the decision stays
            # attributable to the bytes actually in force. Constitution section
            # 5.7 -- a policy change never retroactively legitimises a past
            # acquisition, and never silently invalidates one.
            "authorizationRecordHash": (authorization or {}).get("recordHash"),
        }
        policy_context = {
            "authorizationId": payload["authorizationId"],
            "policyVersion": payload["policyVersion"] or "0",
            "permittedOperations": payload["permittedOperations"],
        }

        self._emit("PolicyEvaluated", task_row["workflow_id"],
                   task_row["correlation_id"], task_row["task_id"], payload,
                   task_id=task_row["task_id"], producer=PRODUCER_POLICY_GATE,
                   policy_context=policy_context,
                   crash_after_append="after_policy_decision_append")

        if decision.permitted:
            if operation_class == policy.OPERATION_CLASS_ACQUISITION:
                self._emit("AcquisitionAuthorized", task_row["workflow_id"],
                           task_row["correlation_id"], task_row["task_id"],
                           dict(payload), task_id=task_row["task_id"],
                           producer=PRODUCER_POLICY_GATE,
                           policy_context=policy_context)
            return "advanced"

        # Every denial concerns acquisition-class or indeterminate work, because
        # non-acquisition work always permits. Constitution section 4.18:
        # rejections remain visible -- silence is a defect.
        self._emit("AcquisitionDenied", task_row["workflow_id"],
                   task_row["correlation_id"], task_row["task_id"], dict(payload),
                   task_id=task_row["task_id"], producer=PRODUCER_POLICY_GATE,
                   policy_context=policy_context)
        self._crash_point("after_policy_denial")
        return self._request_review(task_row, decision.reason, operation_class,
                                    subject_source, operations,
                                    payload["policyStatus"],
                                    payload["policyVersion"])

    def _request_review(self, task_row, reason=None, operation_class=None,
                        subject_source=None, operations=None,
                        policy_status=None, policy_version=None):
        """`blocked -> awaiting_review`. Catalog section L, authority orchestrator.

        Called both inline after a denial and, after a crash between the two
        events, from the drivable set. It RE-STATES a decision already durable
        in the log; it never re-makes one, which is why every field falls back
        to the recorded task row rather than being recomputed.
        """
        self._emit("HumanReviewRequired", task_row["workflow_id"],
                   task_row["correlation_id"], task_row["task_id"],
                   {"reviewType": "acquisition_policy",
                    "reason": reason or task_row["policy_reason"],
                    "operationClass": (operation_class
                                       or task_row["operation_class"]),
                    "subjectSourceId": (subject_source
                                        or task_row["subject_source_id"]),
                    "requestedOperations": list(operations or []),
                    "policyStatus": policy_status or task_row["policy_status"],
                    "policyVersion": policy_version or task_row["policy_version"],
                    "blockedAtUtc": self._clock.now_iso()},
                   task_id=task_row["task_id"], producer=PRODUCER_ORCHESTRATOR,
                   crash_after_append="after_review_required_append")
        return "blocked"

    def _refuse_unauthorized_dispatch(self, task_row, recorded_decision):
        """An acquisition-class task reached dispatch without a recorded permit.

        This is not reachable through the normal path -- policy_check is the
        only entry to `queued`, and it records its decision before the
        transition commits. It is reachable through index corruption or a future
        code path that forgot the gate, which is exactly what a defence-in-depth
        guard is for.

        Nothing executes, nothing is claimed, and the refusal is recorded rather
        than raised, because Constitution section 6.6 forbids a path that ends
        without a recorded outcome.
        """
        with store.immediate_transaction(self.connection):
            self.connection.execute(
                "INSERT INTO transition_anomalies "
                "(detected_at, log_sequence, task_id, from_state, to_state, reason) "
                "VALUES (?,?,?,?,?,?)",
                (self._clock.now_iso(), task_row["last_log_sequence"],
                 task_row["task_id"], "queued", "claimed",
                 "dispatch_without_policy_permit: acquisition-class task carries "
                 "recorded policy decision %r, not %r"
                 % (recorded_decision, policy.DECISION_PERMIT)))
        self._note("REFUSED dispatch of task %s -- no recorded policy permit"
                   % (task_row["task_id"],))
        return "unauthorized"

    # -- operator disposition of a blocked task ------------------------------

    def record_review_decision(self, task_id, decision, reason, reviewer_identity,
                               policy_version=None):
        """The audited operator decision that disposes of a blocked task.

        Governance decision C-1. This is NOT a review system: there is no queue,
        no assignment, no notification and no workflow. It is the one audited
        action that lets a human release or suppress a task the gate blocked,
        which is what keeps Constitution section 6.5 true -- every task reaches
        a visible terminal outcome, or is explicitly released.

        The committed contract fixes the path. `legal_successors("blocked")` is
        ('awaiting_review', 'cancelled'): there is no `blocked -> queued` and no
        `blocked -> suppressed` edge, so the decision acts on `awaiting_review`,
        under `review_gate` authority, exactly as Catalog section L assigns it.

        Constitution section 9 is enforced, not documented: reviewer identity,
        decision, REASON, timestamp and policy version are all required, and a
        bare approval is refused.
        """
        if decision not in projection.REVIEW_DECISION_TARGET:
            runtime_errors.fail(
                "review decision %r is not one of %s"
                % (decision, sorted(projection.REVIEW_DECISION_TARGET)),
                runtime_errors.ReviewDecisionError,
            )
        if not isinstance(reason, str) or not reason.strip():
            runtime_errors.fail(
                "a review decision requires a reason. Constitution section 9: "
                "'a decision without a reason is invalid' -- a bare approval is "
                "refused rather than recorded with an empty justification",
                runtime_errors.ReviewDecisionError,
            )
        self._assert_reviewer_is_human(reviewer_identity)

        row = self.connection.execute(
            "SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        if row is None:
            runtime_errors.fail("no such task %s" % (task_id,),
                                runtime_errors.ReviewDecisionError)
        if row["state"] != "awaiting_review":
            runtime_errors.fail(
                "task %s is %s, not awaiting_review; only a task awaiting review "
                "may be disposed of" % (task_id, row["state"]),
                runtime_errors.ReviewDecisionError,
            )

        payload = {"decision": decision,
                   "reason": reason,
                   "reviewerIdentity": reviewer_identity,
                   "decidedAtUtc": self._clock.now_iso(),
                   "policyVersion": policy_version or row["policy_version"] or "0",
                   "reviewType": "acquisition_policy",
                   "subjectSourceId": row["subject_source_id"],
                   "priorPolicyReason": row["policy_reason"]}

        if decision == "approved":
            # A HUMAN MAY UN-BLOCK A TASK. ONLY THE GATE MAY AUTHORIZE THE
            # ACQUISITION. Constitution section 5.1 admits no exception: no
            # fetch without an Acquisition Authorization Record, and a reviewer
            # is not a substitute for one.
            #
            # So an approval RE-EVALUATES the gate against whatever governance
            # has recorded since the block, and is refused outright if the
            # answer is still a denial. Releasing the task anyway would produce
            # a task that could never dispatch -- approval that cannot lead to
            # execution is not approval, it is a misleading state change.
            fresh = self._re_evaluate_for_review(row)
            if not fresh.permitted:
                runtime_errors.fail(
                    "task %s cannot be approved: the policy gate still denies it "
                    "(%s). A review decision releases a task; it does not "
                    "authorize an acquisition. Record the governance-supplied "
                    "authorization first, or reject the task."
                    % (task_id, fresh.reason),
                    runtime_errors.ReviewDecisionError,
                )
            payload.update(self._policy_payload_for(row, fresh))

        self._emit("HumanReviewCompleted", row["workflow_id"],
                   row["correlation_id"], task_id, payload,
                   task_id=task_id, producer=PRODUCER_REVIEW_GATE,
                   crash_after_append="after_review_decision_append")
        return decision

    def _re_evaluate_for_review(self, task_row):
        """Ask the gate again, with today's recorded authorizations.

        The second and last call site of the decision. It exists because an
        approval is only meaningful if the situation that caused the block has
        actually changed, and only the gate may say whether it has.
        """
        capability = registry.lookup(self.connection, task_row["capability_id"])
        operation_class = (capability["operation_class"] if capability is not None
                           else None)
        operations = registry.declared_acquisition_operations(capability)
        authorization, problem = authorizations.resolve(
            self.connection, task_row["subject_source_id"])
        return policy.assert_decision_is_recognised(
            policy.evaluate(operation_class, operations, authorization,
                            self._clock.now_ms(), resolution_problem=problem))

    def _policy_payload_for(self, task_row, decision):
        """The re-evaluated decision, in the same recorded shape the gate uses.

        Carried in the HumanReviewCompleted payload and copied into the task
        row, so the permit that allows dispatch is the gate's, recorded with its
        authority and policy version -- never the reviewer's say-so.
        """
        capability = registry.lookup(self.connection, task_row["capability_id"])
        operations = registry.declared_acquisition_operations(capability)
        authorization, _problem = authorizations.resolve(
            self.connection, task_row["subject_source_id"])
        authorization = authorization or {}
        return {
            "policyDecision": decision.decision,
            "policyReason": decision.reason,
            "policyStatus": authorization.get("policyStatus"),
            "reEvaluatedPolicyVersion": authorization.get("policyVersion"),
            "authorizationId": authorization.get("authorizationId"),
            "decisionAuthority": authorization.get("decisionAuthority"),
            "permittedOperations": list(
                authorization.get("permittedOperations") or []),
            "requestedOperations": list(operations),
            "authorizationRecordHash": authorization.get("recordHash"),
        }

    def _assert_reviewer_is_human(self, reviewer_identity):
        """Catalog section N: a reviewer is a human or a governance role, never
        a worker. Constitution section 7: no worker may approve its own governed
        output -- a capability that could release its own blocked task would
        make the gate ornamental."""
        if not isinstance(reviewer_identity, str) or not reviewer_identity.strip():
            runtime_errors.fail(
                "a review decision requires a reviewer identity "
                "(Constitution section 9)",
                runtime_errors.ReviewDecisionError,
            )
        for prefix in authorizations.PROHIBITED_AUTHORITY_PREFIXES:
            if reviewer_identity.startswith(prefix) or prefix in reviewer_identity:
                runtime_errors.fail(
                    "reviewer identity %r names automation. A review decision "
                    "may be made only by a human or a governance role -- no "
                    "worker may approve its own governed output (Constitution "
                    "section 7, Catalog section N)" % (reviewer_identity,),
                    runtime_errors.ReviewDecisionError,
                )
        if not any(reviewer_identity.startswith(prefix)
                   for prefix in authorizations.AUTHORITY_PREFIXES):
            runtime_errors.fail(
                "reviewer identity %r must begin with one of %s so that the "
                "deciding authority is unambiguous in the audit trail"
                % (reviewer_identity, list(authorizations.AUTHORITY_PREFIXES)),
                runtime_errors.ReviewDecisionError,
            )
        return reviewer_identity

    # -- governance input ----------------------------------------------------

    def record_authorization(self, record):
        """Store one governance-supplied Acquisition Authorization Record.

        The platform records and enforces decisions supplied by governance or
        legal review; it never makes one (Constitution section 5.9). This method
        is the only way a record enters the runtime, and it validates before it
        stores.
        """
        with store.immediate_transaction(self.connection):
            outcome = authorizations.register(self.connection, record,
                                              self._clock.now_iso())
        self._note("AUTHORIZATION %s %s for %s"
                   % (outcome, record.get("authorizationId"),
                      record.get("sourceId")))
        return outcome

    def _acquire_lease(self, task_row, capability_row):
        """Claim the task and take the lease in ONE guarded UPDATE.

        Not a read-then-write and not advisory locking -- the same primitive
        Step 1 proved, with additional SET clauses and a compare-and-set on the
        generation (Architecture section 18.1). The lease commits with the
        claim or not at all, so there is no window in which a lease exists but
        the claim does not.

        Returns the claimed generation, which the caller carries in memory for
        the whole execution. That is what makes the later holder check
        meaningful: it compares against the generation THIS execution claimed
        with, not merely against "some current generation", so a reclaim that
        bumped the generation mid-flight is detected.
        """
        limits = json.loads(capability_row["resource_limits"])
        ttl_ms = lease_module.lease_ttl_ms(limits.get("wallClockMs"))
        acquired_ms = self._clock.now_ms()
        expires_ms = lease_module.lease_expiry_ms(acquired_ms, ttl_ms)
        generation = task_row["lease_generation"] + 1

        self._emit(
            "TaskClaimed", task_row["workflow_id"], task_row["correlation_id"],
            task_row["task_id"],
            {"capabilityId": capability_row["capability_id"],
             "claimMode": "compare_and_set_lease",
             "leaseHolder": self.lease_holder,
             "leaseGeneration": generation,
             "leaseAcquiredAt": clock_module.format_ms(acquired_ms),
             "leaseExpiresAt": clock_module.format_ms(expires_ms),
             "leaseTtlMs": ttl_ms,
             # The value BEFORE the increment, so the payload states which
             # attempt this claim is for.
             "attempt": task_row["attempt"]},
            task_id=task_row["task_id"],
            producer=producer_for(capability_row["capability_id"]),
            crash_after_append="after_claim",
        )
        self._crash_point("after_lease_claim")
        return generation

    def _holds_lease(self, task_id, generation):
        """Architecture section 24, implemented rather than documented."""
        row = self.connection.execute(
            "SELECT lease_holder, lease_generation FROM tasks WHERE task_id = ?",
            (task_id,)).fetchone()
        if row is None:
            return False
        return lease_module.is_held_by(row["lease_holder"], row["lease_generation"],
                                       self.lease_holder, generation)

    def _refuse_result_without_lease(self, task_row, generation, outcome):
        """Discard a result the runtime cannot vouch for the authority of.

        No result event is appended. The anomaly is recorded and the task is
        left for recovery to reclaim. Constitution section 11's "never pick a
        winner", applied to authority rather than to output: recording a result
        under a lease we no longer hold would attribute work to an authority
        that had already been superseded.
        """
        with store.immediate_transaction(self.connection):
            self.connection.execute(
                "INSERT INTO transition_anomalies "
                "(detected_at, log_sequence, task_id, from_state, to_state, reason) "
                "VALUES (?,?,?,?,?,?)",
                (self._clock.now_iso(), task_row["last_log_sequence"],
                 task_row["task_id"], "running", outcome,
                 "result_written_without_lease: generation %d is no longer held "
                 "by %s" % (generation, self.lease_holder)))
        self._note("REFUSED %s for task %s -- lease generation %d no longer held"
                   % (outcome, task_row["task_id"], generation))
        return "abandoned"

    def _claim_and_execute(self, task_row):
        task_id = task_row["task_id"]
        workflow_id = task_row["workflow_id"]
        correlation_id = task_row["correlation_id"]

        command_row = self.connection.execute(
            "SELECT * FROM commands WHERE command_id = ?",
            (task_row["command_id"],)).fetchone()
        capability_row = registry.lookup(self.connection, task_row["capability_id"])
        try:
            registry.assert_dispatchable(
                capability_row, command_row["command_type"],
                command_row["command_version"], task_row["capability_id"])
        except runtime_errors.CapabilityNotDispatchableError as exc:
            return self._fail_task(task_row, "validation", str(exc))

        # THE DISPATCH GUARD. Defence in depth for Constitution section 5.5:
        # "No connector may bypass the policy gate, by configuration, flag,
        # argument, or code path." Reaching `queued` already requires a permit,
        # because policy_check is the only entry path -- but an acquisition-class
        # task is checked AGAIN against its own recorded decision immediately
        # before it is claimed, so even a hand-corrupted index row cannot
        # execute unauthorized acquisition.
        #
        # The guard applies to acquisition-class capabilities only. A
        # non-acquisition task's recorded decision is `not_applicable`, and a
        # task created before this schema version has no recorded decision at
        # all; requiring one of those to carry a permit would strand every
        # pre-existing task on upgrade without protecting anything.
        if capability_row["operation_class"] == policy.OPERATION_CLASS_ACQUISITION:
            recorded = task_row["policy_decision"]
            if recorded != policy.DECISION_PERMIT:
                return self._refuse_unauthorized_dispatch(task_row, recorded)

        generation = self._acquire_lease(task_row, capability_row)
        attempt = task_row["attempt"] + 1

        started = self._emit(
            "TaskStarted", workflow_id, correlation_id, task_id,
            {"capabilityId": capability_row["capability_id"],
             # The value AFTER the increment the guarded UPDATE performs.
             "attempt": attempt,
             "leaseGeneration": generation},
            task_id=task_id,
            producer=producer_for(capability_row["capability_id"]))
        execution = {"startedAtUtc": started.event["recordedAt"],
                     "startedLogSequence": started.log_sequence,
                     "attempt": attempt,
                     "leaseGeneration": generation}

        self._crash_point("mid_execution")
        self._crash_point("during_retry_execution")
        payload = json.loads(command_row["payload_json"])

        # ── MOGO-014 risk A-5: replay, do not repeat. ──
        # Crash boundary 8 is the interruption between performing an effect and
        # recording success. Looking the idempotency key up here is what makes
        # an EFFECTFUL capability safe to resume: a result already recorded is
        # returned rather than produced again. lookup() re-derives the hash of
        # the stored result, so a corrupted row is refused rather than replayed.
        idem_key = command_row["idempotency_key"]
        replayed, verification = result_store_module.lookup(
            self.connection, idem_key)
        if verification == "corrupt":
            return self._fail_task(
                task_row, "validation",
                "a recorded result for idempotency key %s failed re-hash "
                "verification; refusing to replay a corrupted result"
                % (idem_key,), state="running", execution=execution)
        if replayed is not None:
            self._emit(
                "TaskSucceeded", workflow_id, correlation_id, task_id,
                {"resultHash": replayed["contentHash"],
                 "byteLength": replayed["byteLength"],
                 "capabilityId": replayed["capabilityId"],
                 "capabilityVersion": replayed["capabilityVersion"],
                 "attempt": attempt,
                 "leaseGeneration": generation,
                 "idempotentReplay": True,
                 "startedAtUtc": execution["startedAtUtc"],
                 "startedLogSequence": execution["startedLogSequence"]},
                task_id=task_id, execution_result="success",
                crash_after_append="after_success_append")
            self._emit("WorkflowCompleted", workflow_id, correlation_id,
                       task_id, {"taskId": task_id, "outcome": "succeeded"})
            return "succeeded"
        callable_ = CAPABILITY_CALLABLES.get(capability_row["capability_id"])
        if callable_ is None:
            return self._fail_task(
                task_row, "validation",
                "capability %s is registered but this build provides no "
                "implementation" % (capability_row["capability_id"],),
                state="running", execution=execution)

        # The execution context is handed only to a capability that declared it
        # needs one, is not part of the command payload, and is therefore never
        # part of the idempotency key -- Constitution section 11: keys are never
        # derived from timestamps or attempt numbers.
        context = ({"attempt": attempt, "taskId": task_id,
                    "leaseGeneration": generation}
                   if capability_row["requires_execution_context"] else None)
        result = worker_module.execute_task(
            callable_, payload, context=context,
            declared_failure_classes=registry.declared_failure_classes(
                capability_row))
        self._crash_point("after_execution")

        if result.violation is not None:
            self._record_capability_violation(
                capability_row["capability_id"], task_id, result.violation[0],
                str(result.violation[1]))

        if not result.succeeded:
            if not self._holds_lease(task_id, generation):
                return self._refuse_result_without_lease(task_row, generation,
                                                         "failed")
            return self._fail_task(task_row, result.error_class,
                                   result.error_message, state="running",
                                   execution=execution,
                                   declared=result.declared_by_capability)

        if not self._holds_lease(task_id, generation):
            return self._refuse_result_without_lease(task_row, generation,
                                                     "succeeded")

        # Record BEFORE announcing success, so a crash between the two leaves a
        # recorded result to replay rather than an effect nobody remembers.
        try:
            result_store_module.record(self.connection, idem_key,
                                       capability_row["capability_id"],
                                       result.result, self._clock.now_iso())
        except Exception:                      # noqa: BLE001 - never lose a success
            pass

        self._crash_point("before_success_append")
        self._emit(
            "TaskSucceeded", workflow_id, correlation_id, task_id,
            {"resultHash": result.result["contentHash"],
             "byteLength": result.result["byteLength"],
             "capabilityId": result.result["capabilityId"],
             "capabilityVersion": result.result["capabilityVersion"],
             "attempt": attempt,
             "leaseGeneration": generation,
             "startedAtUtc": execution["startedAtUtc"],
             "startedLogSequence": execution["startedLogSequence"]},
            task_id=task_id, execution_result="success",
            crash_after_append="after_success_append",
        )
        self._emit("WorkflowCompleted", workflow_id, correlation_id, task_id,
                   {"taskId": task_id, "outcome": "succeeded"})
        return "succeeded"

    def _fail_task(self, task_row, error_class, message, state=None,
                   execution=None, declared=False):
        """Record a failure, and stop there.

        `failed` is NOT terminal, and this method deliberately does not resolve
        it: run_once() decides retry versus dead-letter on the next iteration,
        from recorded state. That separation is what makes crash boundary 12 --
        interrupted between the failure and the decision -- recover to the same
        answer rather than to a re-guessed one.
        """
        task_id = task_row["task_id"]

        # An error class that is not a Catalog section K name CANNOT be
        # recorded: the committed event contract restricts errorClass to that
        # vocabulary, so appending one would be refused by validate_event and
        # the failure would vanish -- which Constitution section 6.6 forbids.
        #
        # It is therefore normalized here, fail-closed, to the non-retryable
        # class, and the substitution is RECORDED rather than silent. The
        # worker already refuses an unknown class at its own boundary; this is
        # the second, independent guard, and it is the one that keeps the log
        # valid. `unknown_error_class` survives as a live branch in
        # classify_failure for the remaining case: a class that reached the
        # index some other way, for example through a corrupted row.
        if error_class not in contract_errors.ERROR_CLASS_NAMES:
            self._record_capability_violation(
                task_row["capability_id"], task_id,
                worker_module.UNDECLARED_FAILURE_CLASS,
                "error class %r is not a Contract Catalog section K class; "
                "recorded as %r, which is not retryable"
                % (error_class, worker_module.FALLBACK_ERROR_CLASS))
            message = ("%s (original error class %r is not an approved class)"
                       % (message, error_class))
            error_class = worker_module.FALLBACK_ERROR_CLASS

        current = state or task_row["state"]
        if current != "running":
            # TaskFailed is defined as running -> failed. Reach `running`
            # legitimately first rather than inventing an unapproved edge.
            if current == "policy_check":
                self._emit("PolicyEvaluated", task_row["workflow_id"],
                           task_row["correlation_id"], task_id,
                           {"decision": "not_applicable",
                            "operationClass": None,
                            "reason": "routed to failure"},
                           task_id=task_id, producer=PRODUCER_POLICY_GATE)
                current = "queued"
            if current == "queued":
                self._emit("TaskClaimed", task_row["workflow_id"],
                           task_row["correlation_id"], task_id,
                           {"capabilityId": task_row["capability_id"],
                            "claimMode": "compare_and_set_lease",
                            "leaseHolder": self.lease_holder,
                            "leaseGeneration": task_row["lease_generation"] + 1,
                            "leaseAcquiredAt": self._clock.now_iso(),
                            "leaseExpiresAt": clock_module.format_ms(
                                lease_module.lease_expiry_ms(
                                    self._clock.now_ms(),
                                    lease_module.LEASE_TTL_FLOOR_MS)),
                            "leaseTtlMs": lease_module.LEASE_TTL_FLOOR_MS,
                            "attempt": task_row["attempt"]},
                           task_id=task_id,
                           producer=producer_for(task_row["capability_id"]))
                current = "claimed"
            if current == "claimed":
                started = self._emit(
                    "TaskStarted", task_row["workflow_id"],
                    task_row["correlation_id"], task_id,
                    {"capabilityId": task_row["capability_id"],
                     "attempt": task_row["attempt"] + 1,
                     "leaseGeneration": task_row["lease_generation"] + 1},
                    task_id=task_id,
                    producer=producer_for(task_row["capability_id"]))
                execution = {"startedAtUtc": started.event["recordedAt"],
                             "startedLogSequence": started.log_sequence,
                             "attempt": task_row["attempt"] + 1,
                             "leaseGeneration": task_row["lease_generation"] + 1}

        execution = execution or {}
        self._emit("TaskFailed", task_row["workflow_id"], task_row["correlation_id"],
                   task_id,
                   {"reason": message,
                    "attempt": execution.get("attempt"),
                    "attemptLimit": task_row["attempt_limit"],
                    "leaseGeneration": execution.get("leaseGeneration"),
                    "capabilityId": task_row["capability_id"],
                    # Distinguishes a failure the capability DECLARED from one
                    # the worker classified because the capability escaped
                    # unclassified -- a distinction an operator needs and
                    # cannot otherwise see.
                    "declaredByCapability": bool(declared),
                    "startedAtUtc": execution.get("startedAtUtc"),
                    "startedLogSequence": execution.get("startedLogSequence")},
                   task_id=task_id, execution_result="failure",
                   error_class=error_class,
                   crash_after_append="after_failure_append")
        self._crash_point("inside_failure_transaction")
        return "failed"

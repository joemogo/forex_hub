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
"""

import os
import uuid as _uuid
from datetime import datetime, timezone

from ..contracts import command as command_contract  # noqa: E402
from ..contracts import ids  # noqa: E402
from ..contracts import task_states  # noqa: E402
from . import errors as runtime_errors  # noqa: E402
from . import event_log as event_log_module  # noqa: E402
from . import paths as paths_module  # noqa: E402
from . import projection  # noqa: E402
from . import registry  # noqa: E402
from . import schema as schema_module  # noqa: E402
from . import store  # noqa: E402
from . import worker as worker_module  # noqa: E402
from .capabilities import echo as echo_capability  # noqa: E402

PRODUCER_ORCHESTRATOR = "orchestrator"
PRODUCER_POLICY_GATE = "policyGate"
PRODUCER_WORKER = "worker:" + echo_capability.CAPABILITY_ID
PRODUCER_VERSION = "1.0.0"
EVENT_VERSION = 1

CRASH_SIM_ENV = "MOGO_RUNTIME_ALLOW_CRASH_SIM"

# The capabilities this build registers at init. One, deliberately.
BUILTIN_CAPABILITIES = (echo_capability.MANIFEST,)
CAPABILITY_CALLABLES = {echo_capability.CAPABILITY_ID: echo_capability.execute}

NON_TERMINAL_RESUMABLE = ("requested", "policy_check", "queued")


def utc_now():
    """ISO-8601 UTC at millisecond precision -- the Catalog conventions format."""
    moment = datetime.now(timezone.utc)
    return "%s.%03dZ" % (moment.strftime("%Y-%m-%dT%H:%M:%S"),
                         moment.microsecond // 1000)


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

    def __init__(self, paths=None, clock=utc_now, uuid_factory=None,
                 crash_at=None, create=True):
        self.paths = paths or paths_module.default_paths()
        self._clock = clock
        self._uuid_factory = uuid_factory or _uuid.uuid4
        self._crash_at = crash_at
        self._create = create
        self.log = event_log_module.EventLog(self.paths)
        self.connection = None
        self._lock = None
        self.trace = []

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
        self._lock = store.ProcessLock(self.paths).acquire()
        self.connection = store.open_database(self.paths, create=create)
        schema_module.initialize(self.connection, self._clock())
        return self

    def close(self):
        if self.connection is not None:
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
                    self.connection, manifest, self._clock())
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
        now = self._clock()
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
        import json
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
                  "resumed_commands": []}

        # R2 -- torn tail. A fragment is not an event; quarantine then truncate.
        quarantined = self.log.repair_torn_tail(self._clock())
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

        # R4 -- reclaim tasks stranded mid-flight. Single-writer means the
        # previous holder is gone, so there is nothing to wait for.
        stranded = self.connection.execute(
            "SELECT task_id, workflow_id, correlation_id, state FROM tasks "
            "WHERE state IN (?, ?)", projection.RECLAIMABLE_STATES).fetchall()
        for row in stranded:
            self._emit(
                "TaskReclaimed", row["workflow_id"], row["correlation_id"],
                row["task_id"],
                {"reclaimedFrom": row["state"],
                 "reason": "runtime restarted while the task was in flight"},
                task_id=row["task_id"], producer=PRODUCER_ORCHESTRATOR,
            )
            report["reclaimed"].append(row["task_id"])
            self._record_recovery("task_reclaimed", row["task_id"], row["state"])

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
                "VALUES (?,?,?,?)", (self._clock(), action, subject, detail))

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
        submitted_at = self._clock()
        try:
            validated = command_contract.validate_command(envelope, payload=payload)
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
        self._emit(
            "TaskRequested", command_row["workflow_id"],
            command_row["correlation_id"], command_row["command_id"],
            {"commandId": command_row["command_id"],
             "capabilityId": capability_id,
             "idempotencyKey": command_row["idempotency_key"]},
            task_id=task_id,
        )
        return task_id

    # -- execution -----------------------------------------------------------

    def run_once(self):
        """Drive every non-terminal task as far as it can go. Returns a report."""
        report = {"advanced": [], "succeeded": [], "failed": []}
        while True:
            row = self.connection.execute(
                "SELECT * FROM tasks WHERE terminal = 0 AND state IN (?,?,?) "
                "ORDER BY created_log_sequence LIMIT 1",
                NON_TERMINAL_RESUMABLE).fetchone()
            if row is None:
                break
            outcome = self._advance(row)
            report["advanced"].append(row["task_id"])
            if outcome == "succeeded":
                report["succeeded"].append(row["task_id"])
            elif outcome == "failed":
                report["failed"].append(row["task_id"])
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

        return "advanced"

    def _evaluate_policy(self, task_row):
        """Apply policy only to the extent authorized (plan section 10).

        A non-acquisition operation proceeds with a recorded no-op. An
        acquisition-class operation CANNOT be decided here, because no policy
        gate exists in Step 1, so it is refused rather than guessed. An
        indeterminate class is blocked -- the fail-closed default.
        """
        capability = registry.lookup(self.connection, task_row["capability_id"])
        operation_class = (capability["operation_class"] if capability is not None
                           else None)
        next_state, reason = task_states.classify_policy_check(operation_class)

        if next_state == "queued":
            self._emit(
                "PolicyEvaluated", task_row["workflow_id"],
                task_row["correlation_id"], task_row["task_id"],
                {"decision": "not_applicable", "operationClass": operation_class,
                 "reason": reason},
                task_id=task_row["task_id"], producer=PRODUCER_POLICY_GATE,
                policy_context={"authorizationId": None, "policyVersion": "0",
                                "permittedOperations": []},
            )
            return "advanced"

        detail = ("acquisition-class operations require the policy gate, which is "
                  "not implemented in Step 1"
                  if reason == task_states.REQUIRES_POLICY_GATE
                  else "operation class %r is indeterminate" % (operation_class,))
        return self._fail_task(task_row, "policy_blocked", detail)

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

        self._emit("TaskClaimed", workflow_id, correlation_id, task_id,
                   {"capabilityId": capability_row["capability_id"],
                    "claimMode": "compare_and_set_single_writer"},
                   task_id=task_id, producer=PRODUCER_WORKER,
                   crash_after_append="after_claim")

        self._emit("TaskStarted", workflow_id, correlation_id, task_id,
                   {"capabilityId": capability_row["capability_id"]},
                   task_id=task_id, producer=PRODUCER_WORKER)

        self._crash_point("mid_execution")
        import json
        payload = json.loads(command_row["payload_json"])
        callable_ = CAPABILITY_CALLABLES.get(capability_row["capability_id"])
        if callable_ is None:
            return self._fail_task(
                task_row, "validation",
                "capability %s is registered but this build provides no "
                "implementation" % (capability_row["capability_id"],))

        result = worker_module.execute_task(callable_, payload)
        self._crash_point("after_execution")

        if not result.succeeded:
            return self._fail_task(task_row, result.error_class,
                                   result.error_message, state="running")

        self._crash_point("before_success_append")
        self._emit(
            "TaskSucceeded", workflow_id, correlation_id, task_id,
            {"resultHash": result.result["contentHash"],
             "byteLength": result.result["byteLength"],
             "capabilityId": result.result["capabilityId"],
             "capabilityVersion": result.result["capabilityVersion"]},
            task_id=task_id, execution_result="success",
            crash_after_append="after_success_append",
        )
        self._emit("WorkflowCompleted", workflow_id, correlation_id, task_id,
                   {"taskId": task_id, "outcome": "succeeded"})
        return "succeeded"

    def _fail_task(self, task_row, error_class, message, state=None):
        """Record a failure. Retry and dead-letter are out of Step 1 scope.

        The task stops at `failed` and is reported. Constitution section 6.6:
        the path ends with an event, never silently.
        """
        task_id = task_row["task_id"]
        current = state or task_row["state"]
        if current != "running":
            # TaskFailed is defined as running -> failed. Reach `running`
            # legitimately first rather than inventing an unapproved edge.
            if current == "queued":
                self._emit("TaskClaimed", task_row["workflow_id"],
                           task_row["correlation_id"], task_id,
                           {"capabilityId": task_row["capability_id"],
                            "claimMode": "compare_and_set_single_writer"},
                           task_id=task_id, producer=PRODUCER_WORKER)
                current = "claimed"
            if current == "claimed":
                self._emit("TaskStarted", task_row["workflow_id"],
                           task_row["correlation_id"], task_id,
                           {"capabilityId": task_row["capability_id"]},
                           task_id=task_id, producer=PRODUCER_WORKER)
            elif current == "policy_check":
                self._emit("PolicyEvaluated", task_row["workflow_id"],
                           task_row["correlation_id"], task_id,
                           {"decision": "not_applicable",
                            "operationClass": None,
                            "reason": "routed to failure"},
                           task_id=task_id, producer=PRODUCER_POLICY_GATE)
                self._emit("TaskClaimed", task_row["workflow_id"],
                           task_row["correlation_id"], task_id,
                           {"capabilityId": task_row["capability_id"],
                            "claimMode": "compare_and_set_single_writer"},
                           task_id=task_id, producer=PRODUCER_WORKER)
                self._emit("TaskStarted", task_row["workflow_id"],
                           task_row["correlation_id"], task_id,
                           {"capabilityId": task_row["capability_id"]},
                           task_id=task_id, producer=PRODUCER_WORKER)

        self._emit("TaskFailed", task_row["workflow_id"], task_row["correlation_id"],
                   task_id, {"reason": message}, task_id=task_id,
                   execution_result="failure", error_class=error_class)
        self._emit("WorkflowFailed", task_row["workflow_id"],
                   task_row["correlation_id"], task_id,
                   {"taskId": task_id, "errorClass": error_class})
        return "failed"

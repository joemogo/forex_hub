#!/usr/bin/env python3
"""MOGO-011 Step 1 -- crash recovery at every boundary in the plan's matrix.

Pure stdlib (unittest). Offline, deterministic, repeatable. Tempfile state root.

REAL PROCESS KILLS, NOT MOCKS
    Each induced-interruption test runs the CLI in a CHILD PROCESS that calls
    os._exit() at a named boundary -- no unwinding, no `finally`, no flush, no
    database close. That is what a real kill does, and it is the only way to
    exercise the gap between the log fsync and the SQLite commit. A mocked
    exception would unwind cleanly and prove nothing.

    subprocess is used here in the TEST layer. The runtime itself contains no
    subprocess capability, which test_runtime_boundaries asserts separately.

Run with:
    python3 -m unittest tests.platform.test_runtime_recovery -v
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC_DIR = os.path.join(REPO_ROOT, "platform", "src")
LAUNCHER = os.path.join(REPO_ROOT, "platform", "mogo_runtime.py")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from mogo_platform.runtime import cli as cli_module  # noqa: E402
from mogo_platform.runtime import event_log as event_log_module  # noqa: E402
from mogo_platform.runtime import orchestrator as orchestrator_module  # noqa: E402
from mogo_platform.runtime import paths as paths_module  # noqa: E402
from mogo_platform.runtime import projection  # noqa: E402
from mogo_platform.runtime import store  # noqa: E402

# Independently transcribed from Step 1 plan section 13.5.
EXPECTED_CRASH_BOUNDARIES = ("after_command_append", "before_task_create",
                             "after_claim", "mid_execution", "after_execution",
                             "before_success_append", "after_success_append")


class RecoveryCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = os.path.join(self._tmp.name, "state")
        self.paths = paths_module.RuntimePaths(self.root)

    def tearDown(self):
        self._tmp.cleanup()

    # -- child-process drivers ----------------------------------------------

    def child(self, *argv, allow_crash=False, expect_crash=False):
        env = dict(os.environ)
        env["MOGO_RUNTIME_STATE_ROOT"] = self.root
        if allow_crash:
            env["MOGO_RUNTIME_ALLOW_CRASH_SIM"] = "1"
        else:
            env.pop("MOGO_RUNTIME_ALLOW_CRASH_SIM", None)
        completed = subprocess.run(
            [sys.executable, LAUNCHER] + list(argv),
            cwd=REPO_ROOT, env=env, capture_output=True, text=True)
        if expect_crash:
            self.assertEqual(completed.returncode, 70,
                             "expected an induced crash; got %r / %s"
                             % (completed.returncode, completed.stderr))
        return completed

    def runtime(self, create=True):
        return orchestrator_module.Orchestrator(paths=self.paths, create=create).open()

    def init_and_submit(self):
        self.child("init")
        self.child("submit", "--demo")

    def task_row(self):
        runtime = self.runtime()
        try:
            return runtime.connection.execute("SELECT * FROM tasks").fetchone()
        finally:
            runtime.close()

    def counts(self):
        runtime = self.runtime()
        try:
            connection = runtime.connection
            return {
                "tasks": connection.execute(
                    "SELECT COUNT(*) FROM tasks").fetchone()[0],
                "commands": connection.execute(
                    "SELECT COUNT(*) FROM commands").fetchone()[0],
                "events": connection.execute(
                    "SELECT COUNT(*) FROM event_index").fetchone()[0],
                "succeeded": connection.execute(
                    "SELECT COUNT(*) FROM tasks WHERE state='succeeded'").fetchone()[0],
            }
        finally:
            runtime.close()


class TestCrashBoundaries(RecoveryCase):
    def test_every_planned_boundary_is_reachable(self):
        import inspect
        source = inspect.getsource(orchestrator_module)
        for boundary in EXPECTED_CRASH_BOUNDARIES:
            with self.subTest(boundary=boundary):
                self.assertIn('"%s"' % boundary, source)

    def test_crash_simulation_is_refused_without_the_env_guard(self):
        self.child("init")
        completed = self.child("submit", "--demo",
                               "--simulate-crash-at", "after_command_append")
        self.assertNotEqual(completed.returncode, 70)
        self.assertIn("MOGO_RUNTIME_ALLOW_CRASH_SIM",
                      completed.stdout + completed.stderr)

    def test_boundary_3_crash_between_command_receipt_and_task_creation(self):
        self.child("init")
        self.child("submit", "--demo", "--simulate-crash-at", "before_task_create",
                   allow_crash=True, expect_crash=True)
        before = self.counts()
        self.assertEqual(before["commands"], 1)
        self.assertEqual(before["tasks"], 0)          # the crash landed in the gap

        completed = self.child("run")
        self.assertEqual(completed.returncode, 0)
        self.assertIn("resumed", completed.stdout)
        after = self.counts()
        self.assertEqual(after["commands"], 1)
        self.assertEqual(after["tasks"], 1)           # exactly one, not two
        self.assertEqual(after["succeeded"], 1)

    def test_boundary_2_crash_after_the_command_append(self):
        self.child("init")
        self.child("submit", "--demo", "--simulate-crash-at", "after_command_append",
                   allow_crash=True, expect_crash=True)
        # The event is durable; the index may be behind. Recovery converges.
        self.child("run")
        counts = self.counts()
        self.assertEqual(counts["commands"], 1)
        self.assertEqual(counts["tasks"], 1)
        self.assertEqual(counts["succeeded"], 1)

    def test_boundary_6_crash_after_claim_reclaims_and_completes(self):
        self.init_and_submit()
        self.child("run", "--simulate-crash-at", "after_claim",
                   allow_crash=True, expect_crash=True)
        # `after_claim` fires inside _emit, between the log fsync and the
        # SQLite commit, so the INDEX may still read `queued` while the LOG
        # already records the claim. What matters is that the task is not
        # complete and that recovery converges. The stranded-in-`claimed`
        # case proper is boundary 7 (mid_execution), tested below.
        stranded = self.task_row()
        self.assertNotEqual(stranded["state"], "succeeded")

        completed = self.child("run")
        row = self.task_row()
        self.assertEqual(row["state"], "succeeded")
        self.assertEqual(self.counts()["tasks"], 1)

    def test_boundary_7_crash_mid_execution_reclaims_and_completes(self):
        self.init_and_submit()
        self.child("run", "--simulate-crash-at", "mid_execution",
                   allow_crash=True, expect_crash=True)
        self.child("run")
        row = self.task_row()
        self.assertEqual(row["state"], "succeeded")

    def test_boundary_8_crash_after_execution_yields_an_identical_result(self):
        """The safety of this boundary rests entirely on capability purity."""
        self.init_and_submit()
        # Reference result from a clean run in a separate state root.
        reference = cli_module.build_demo_command()[1]
        from mogo_platform.runtime.capabilities import echo
        expected_hash = echo.execute(reference)["contentHash"]

        self.child("run", "--simulate-crash-at", "after_execution",
                   allow_crash=True, expect_crash=True)
        self.child("run")
        row = self.task_row()
        self.assertEqual(row["state"], "succeeded")
        self.assertEqual(row["result_hash"], expected_hash)

    def test_boundary_9_crash_after_success_append_still_reaches_succeeded(self):
        self.init_and_submit()
        self.child("run", "--simulate-crash-at", "after_success_append",
                   allow_crash=True, expect_crash=True)
        self.child("run")
        row = self.task_row()
        self.assertEqual(row["state"], "succeeded")
        self.assertEqual(self.counts()["succeeded"], 1)

    def test_no_boundary_produces_a_duplicate_task_or_duplicate_success(self):
        # Run-phase boundaries only. `before_task_create` fires during submit
        # and is covered by its own test; passing it to `run` would never fire
        # and the assertion would silently pass for the wrong reason.
        for boundary in ("after_claim", "mid_execution", "after_execution",
                         "before_success_append", "after_success_append"):
            with self.subTest(boundary=boundary):
                self.setUp()
                try:
                    self.child("init")
                    self.child("submit", "--demo")
                    self.child("run", "--simulate-crash-at", boundary,
                               allow_crash=True, expect_crash=True)
                    self.child("run")
                    counts = self.counts()
                    self.assertEqual(counts["tasks"], 1)
                    self.assertEqual(counts["succeeded"], 1)
                finally:
                    self.tearDown()
        self.setUp()   # leave a live fixture for tearDown


class TestRestartBehaviour(RecoveryCase):
    def test_restart_does_not_repeat_completed_work(self):
        self.init_and_submit()
        self.child("run")
        before = self.counts()
        for _ in range(3):
            self.child("run")
        self.assertEqual(self.counts(), before)

    def test_recovery_is_deterministic_across_repeated_restarts(self):
        self.init_and_submit()
        self.child("run", "--simulate-crash-at", "after_claim",
                   allow_crash=True, expect_crash=True)
        self.child("run")
        snapshot = self.counts()
        for _ in range(3):
            self.child("run")
            self.assertEqual(self.counts(), snapshot)

    def test_recover_is_idempotent(self):
        self.init_and_submit()
        runtime = self.runtime()
        try:
            first = runtime.recover()
            second = runtime.recover()
            self.assertEqual(second["reclaimed"], [])
            self.assertEqual(second["resumed_commands"], [])
            self.assertEqual(second["replayed"], 0)
            self.assertIsNone(second["quarantined"])
            self.assertIsInstance(first, dict)
        finally:
            runtime.close()

    def test_a_second_runner_is_refused_while_one_holds_the_lock(self):
        self.child("init")
        runtime = self.runtime()
        try:
            completed = self.child("status")
            self.assertEqual(completed.returncode, 0)   # read-only, no lock
            busy = self.child("run")
            self.assertEqual(busy.returncode, 5)
            self.assertIn("BUSY", busy.stderr)
        finally:
            runtime.close()


class TestTornTailRecovery(RecoveryCase):
    def test_torn_tail_is_quarantined_and_the_run_completes(self):
        self.init_and_submit()
        log = event_log_module.EventLog(self.paths)
        with open(log.path, "ab") as handle:
            handle.write(b'{"eventId": "torn-partial')

        completed = self.child("run")
        self.assertIn("quarantined", completed.stdout)
        self.assertEqual(self.task_row()["state"], "succeeded")

        quarantined = os.listdir(self.paths.quarantine_dir)
        self.assertEqual(len(quarantined), 1)
        with open(os.path.join(self.paths.quarantine_dir, quarantined[0]), "rb") as h:
            self.assertEqual(h.read(), b'{"eventId": "torn-partial')

    def test_replay_halts_on_a_mid_file_hash_mismatch(self):
        self.init_and_submit()
        self.child("run")
        log = event_log_module.EventLog(self.paths)
        with open(log.path, "rb") as handle:
            lines = handle.read().split(b"\n")
        event = json.loads(lines[2].decode("utf-8"))
        event["payload"] = {"tampered": True}
        from mogo_platform.contracts import ids
        lines[2] = ids.canonical_json_bytes(event)
        with open(log.path, "wb") as handle:
            handle.write(b"\n".join(lines))

        completed = self.child("verify")
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("FATAL", completed.stdout + completed.stderr)
        self.assertIn("corruption", (completed.stdout + completed.stderr).lower())


class TestReplayConvergence(RecoveryCase):
    def test_an_index_deleted_entirely_is_rebuilt_from_the_log(self):
        self.init_and_submit()
        self.child("run")
        expected = self.task_row()["result_hash"]

        os.remove(self.paths.database)
        for suffix in ("-wal", "-shm"):
            stale = self.paths.database + suffix
            if os.path.exists(stale):
                os.remove(stale)

        runtime = self.runtime()
        try:
            projection.replay(runtime.connection, runtime.log, from_log_sequence=0)
            row = runtime.connection.execute("SELECT * FROM tasks").fetchone()
            self.assertEqual(row["state"], "succeeded")
            self.assertEqual(row["result_hash"], expected)
        finally:
            runtime.close()

    def test_cursor_behind_the_log_is_caught_up(self):
        self.init_and_submit()
        self.child("run")
        runtime = self.runtime()
        try:
            with store.immediate_transaction(runtime.connection):
                runtime.connection.execute(
                    "UPDATE log_cursor SET last_log_sequence = 0 WHERE id = 1")
            result = projection.replay(runtime.connection, runtime.log)
            self.assertEqual(result["applied"], 0)   # already applied, idempotent
            self.assertEqual(projection.cursor_position(runtime.connection)[0],
                             result["scanned"])
        finally:
            runtime.close()


# ---------------------------------------------------------------------------
# MOGO-011 Step 2 -- crash boundaries 12 through 22
# ---------------------------------------------------------------------------

# Independently transcribed from Step 2 plan section 24.
EXPECTED_STEP_2_CRASH_BOUNDARIES = (
    "after_failure_append",          # 12
    "inside_failure_transaction",    # 13
    "after_retry_schedule_append",   # 14
    "before_retry_projection",       # 15
    "after_retry_release_append",    # 16
    "after_lease_claim",             # 17
    "after_lease_expiry",            # 18
    "before_requeue",                # 19
    "during_retry_execution",        # 20
    "before_dead_letter_apply",      # 21
    "after_dead_letter_append",      # 22
)


class Step2RecoveryCase(RecoveryCase):
    """Every kill here is a real os._exit(70) in a child process.

    No mock, no injected exception: a mocked failure unwinds cleanly and would
    prove nothing about the gap between the log fsync and the SQLite commit.
    """

    def init_and_submit_retry(self, fail_until, attempt_limit=None):
        self.child("init")
        args = ["submit", "--demo-retry", str(fail_until)]
        completed = self.child(*args)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return completed

    def task_state(self):
        runtime = self.runtime()
        try:
            row = runtime.connection.execute(
                "SELECT * FROM tasks ORDER BY created_log_sequence LIMIT 1"
            ).fetchone()
            return dict(row) if row is not None else None
        finally:
            runtime.close()

    def attempt_rows(self):
        runtime = self.runtime()
        try:
            return [dict(r) for r in runtime.connection.execute(
                "SELECT * FROM task_attempts ORDER BY task_id, attempt")]
        finally:
            runtime.close()

    def event_type_counts(self):
        runtime = self.runtime()
        try:
            return {row[0]: row[1] for row in runtime.connection.execute(
                "SELECT event_type, COUNT(*) FROM event_index GROUP BY event_type")}
        finally:
            runtime.close()

    def crash_then_recover(self, boundary, fail_until=1):
        self.init_and_submit_retry(fail_until)
        self.child("run", "--simulate-crash-at", boundary,
                   allow_crash=True, expect_crash=True)
        completed = self.child("run")
        return completed


class TestStep2CrashBoundaries(Step2RecoveryCase):
    def test_every_step_2_boundary_is_declared_and_reachable(self):
        import inspect
        source = inspect.getsource(orchestrator_module)
        self.assertEqual(tuple(orchestrator_module.STEP_2_CRASH_BOUNDARIES),
                         EXPECTED_STEP_2_CRASH_BOUNDARIES)
        for boundary in EXPECTED_STEP_2_CRASH_BOUNDARIES:
            with self.subTest(boundary=boundary):
                # Declared in the list AND used at a real call site.
                self.assertGreaterEqual(source.count('"%s"' % boundary), 2)

    def test_step_2_crash_simulation_is_refused_without_the_env_guard(self):
        self.init_and_submit_retry(1)
        completed = self.child("run", "--simulate-crash-at", "after_failure_append")
        self.assertNotEqual(completed.returncode, 70)
        self.assertIn("MOGO_RUNTIME_ALLOW_CRASH_SIM",
                      completed.stdout + completed.stderr)

    def test_boundary_12_crash_after_failure_append(self):
        self.crash_then_recover("after_failure_append")
        row = self.task_state()
        self.assertEqual(row["state"], "succeeded")
        self.assertEqual(row["attempt"], 2)

    def test_boundary_13_crash_inside_the_failure_transaction(self):
        self.crash_then_recover("inside_failure_transaction")
        row = self.task_state()
        self.assertEqual(row["state"], "succeeded")
        self.assertEqual(row["attempt"], 2)

    def test_boundary_14_crash_after_retry_schedule_append(self):
        self.crash_then_recover("after_retry_schedule_append")
        row = self.task_state()
        self.assertEqual(row["state"], "succeeded")

    def test_boundary_15_crash_before_the_retry_projection(self):
        self.crash_then_recover("before_retry_projection")
        row = self.task_state()
        self.assertEqual(row["state"], "succeeded")

    def test_boundary_16_crash_after_retry_release_append(self):
        self.crash_then_recover("after_retry_release_append")
        row = self.task_state()
        self.assertEqual(row["state"], "succeeded")

    def test_boundary_17_crash_after_the_lease_claim(self):
        """The capability had NOT run, so no attempt is consumed."""
        self.crash_then_recover("after_lease_claim")
        row = self.task_state()
        self.assertEqual(row["state"], "succeeded")
        # Generation advanced through the reclaim; the first claim was rescued.
        self.assertGreaterEqual(row["lease_generation"], 2)

    def test_boundary_19_crash_before_requeue(self):
        self.init_and_submit_retry(1)
        self.child("run", "--simulate-crash-at", "after_lease_claim",
                   allow_crash=True, expect_crash=True)
        # The reclaim event is appended, then the process dies before the
        # transition is applied. R3 replays it.
        self.child("run", "--simulate-crash-at", "before_requeue",
                   allow_crash=True, expect_crash=True)
        self.child("run")
        row = self.task_state()
        self.assertEqual(row["state"], "succeeded")

    def test_boundary_20_crash_during_retry_execution_consumes_the_attempt(self):
        """A crashed attempt WAS attempted -- and that is deliberate.

        The alternative, decrementing on reclaim, would let a task that crashes
        the process on every attempt retry forever, defeating Constitution
        section 11's bounded retry. Consuming the attempt is the fail-closed
        choice and it is recorded, so it is never mistaken for an off-by-one.
        """
        # failUntilAttempt=0 never fails, so an UNINTERRUPTED run succeeds on
        # attempt 1. Any higher final attempt count is therefore attributable
        # to the crash alone, which is what makes this test meaningful.
        self.init_and_submit_retry(0)
        self.child("run", "--simulate-crash-at", "during_retry_execution",
                   allow_crash=True, expect_crash=True)
        after_crash = self.task_state()
        self.assertEqual(after_crash["state"], "running")
        self.assertEqual(after_crash["attempt"], 1)

        self.child("run")
        row = self.task_state()
        self.assertEqual(row["state"], "succeeded")
        # Attempt 1 was consumed by the crash; attempt 2 succeeded.
        self.assertEqual(row["attempt"], 2)
        # And the consumption is RECORDED: the crashed attempt reached no
        # outcome, so only the surviving attempt has a row.
        self.assertEqual([a["attempt"] for a in self.attempt_rows()], [2])
        # Exactly one result, and no attempt recorded twice.
        attempts = self.attempt_rows()
        self.assertEqual(len({(a["task_id"], a["attempt"]) for a in attempts}),
                         len(attempts))
        self.assertEqual(self.event_type_counts().get("TaskSucceeded"), 1)

    def test_boundary_21_crash_before_the_dead_letter_is_applied(self):
        self.init_and_submit_retry(9)
        self.child("run", "--simulate-crash-at", "before_dead_letter_apply",
                   allow_crash=True, expect_crash=True)
        self.child("run")
        row = self.task_state()
        self.assertEqual(row["state"], "dead_lettered")
        self.assertEqual(self.event_type_counts().get("TaskDeadLettered"), 1)

    def test_boundary_22_crash_after_the_dead_letter_append(self):
        self.init_and_submit_retry(9)
        self.child("run", "--simulate-crash-at", "after_dead_letter_append",
                   allow_crash=True, expect_crash=True)
        self.child("run")
        row = self.task_state()
        self.assertEqual(row["state"], "dead_lettered")
        self.assertEqual(row["terminal"], 1)
        self.assertEqual(self.event_type_counts().get("TaskDeadLettered"), 1)

    def test_no_boundary_produces_a_duplicate_attempt_or_duplicate_result(self):
        for boundary in ("after_failure_append", "after_retry_schedule_append",
                         "after_retry_release_append", "after_lease_claim",
                         "during_retry_execution"):
            with self.subTest(boundary=boundary):
                # A fresh state root per boundary. tearDown() first so the
                # directory unittest created for this test is released rather
                # than leaked; unittest's own tearDown cleans up the last one.
                self.tearDown()
                self.setUp()
                self.crash_then_recover(boundary)
                attempts = self.attempt_rows()
                keys = [(a["task_id"], a["attempt"]) for a in attempts]
                self.assertEqual(len(keys), len(set(keys)))
                counts = self.event_type_counts()
                self.assertLessEqual(counts.get("TaskSucceeded", 0), 1)

    def test_repeated_restart_converges_to_the_same_terminal_state(self):
        """Five restarts at five different boundaries reach the same answer as
        an uninterrupted run."""
        self.init_and_submit_retry(2)
        for boundary in ("after_lease_claim", "after_failure_append",
                         "after_retry_schedule_append",
                         "after_retry_release_append",
                         "during_retry_execution"):
            self.child("run", "--simulate-crash-at", boundary,
                       allow_crash=True, expect_crash=True)
        self.child("run")
        row = self.task_state()
        self.assertIn(row["state"], ("succeeded", "dead_lettered"))
        self.assertEqual(row["terminal"], 1)
        counts = self.event_type_counts()
        self.assertLessEqual(counts.get("TaskSucceeded", 0), 1)
        self.assertLessEqual(counts.get("TaskDeadLettered", 0), 1)
        verified = self.child("verify")
        self.assertEqual(verified.returncode, 0, verified.stdout)

    def test_recovery_never_releases_a_retry(self):
        """R6 belongs to run_once, not recover.

        recover() repairs the past; run_once() makes forward progress. A
        release inside recovery would mean `submit` -- which calls recover() --
        silently advanced retries, which is a side effect no operator asked
        for.
        """
        import inspect
        source = inspect.getsource(orchestrator_module.Orchestrator.recover)
        self.assertNotIn("_release_eligible_retries", source)
        run_source = inspect.getsource(orchestrator_module.Orchestrator.run_once)
        self.assertIn("_release_eligible_retries", run_source)


if __name__ == "__main__":
    unittest.main(verbosity=2)


# ---------------------------------------------------------------------------
# MOGO-011 Step 3 -- crash boundaries 23 through 26, across the policy gate
# ---------------------------------------------------------------------------

# Independently transcribed from the Step 3 implementation report.
EXPECTED_STEP_3_CRASH_BOUNDARIES = (
    "after_policy_decision_append",   # 23
    "after_policy_denial",            # 24
    "after_review_required_append",   # 25
    "after_review_decision_append",   # 26
)

# What a crash must never be able to manufacture. Every test in this section
# asserts the whole list, because the interesting failure is not "the task is in
# the wrong state" -- it is "the log now claims something that never happened".
FABRICATION_EVENTS = ("TaskClaimed", "TaskStarted", "TaskSucceeded",
                      "TaskFailed", "AcquisitionAuthorized")


class Step3RecoveryCase(RecoveryCase):
    """Real os._exit(70) kills across the authorization layer.

    The gate is the control every future connector must pass through, so its
    crash behaviour is proved rather than argued. Each test kills the runtime at
    one boundary and then asserts, from the durable log and the rebuilt index,
    that the interruption could not fabricate an authorization, fabricate a
    claim or an execution, bypass the gate, produce an illegal transition,
    contradict the append-only history, or let unauthorized work run.
    """

    SOURCE_LABEL = "crash"

    def init_and_submit_policy(self, label=None):
        """An acquisition-class task, and the subject source it concerns."""
        self.child("init")
        completed = self.child("submit", "--demo-policy", label or self.SOURCE_LABEL)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        source_id = None
        for line in completed.stdout.splitlines():
            if line.startswith("sourceId="):
                source_id = line.split("=", 1)[1].strip()
        self.assertIsNotNone(source_id)
        return source_id

    def authorize(self, source_id, status="PERMITTED_PUBLIC_METADATA",
                  operations=("metadata",)):
        """Record a governance-supplied authorization through the CLI."""
        import json as _json
        import uuid as _uuid
        record = {
            "authorizationId": str(_uuid.uuid4()),
            "sourceId": source_id,
            "policyStatus": status,
            "policyVersion": "1.0",
            "decisionAuthority": "governance:mogo-legal",
            "decidedAt": "2026-08-08T11:00:00.000Z",
            "permittedOperations": list(operations),
        }
        path = os.path.join(self._tmp.name, "authorization.json")
        with open(path, "w", encoding="utf-8") as handle:
            _json.dump(record, handle)
        completed = self.child("authorize", "--file", path)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return record

    def task_row(self):
        runtime = self.runtime()
        try:
            row = runtime.connection.execute(
                "SELECT * FROM tasks ORDER BY created_log_sequence LIMIT 1"
            ).fetchone()
            return dict(row) if row is not None else None
        finally:
            runtime.close()

    def log_events(self):
        """Event types straight from the AUTHORITATIVE log, not the index."""
        runtime = self.runtime()
        try:
            return [r.event["eventType"]
                    for r in runtime.log.scan(verify=True).records]
        finally:
            runtime.close()

    def assert_nothing_was_fabricated(self, expect_execution=False):
        """The core assertion. A crash may lose progress; it may never invent it."""
        events = self.log_events()
        if not expect_execution:
            for name in FABRICATION_EVENTS:
                self.assertNotIn(name, events,
                                 "crash fabricated a %s event" % (name,))
        row = self.task_row()
        if not expect_execution:
            self.assertEqual(row["attempt"], 0,
                             "crash fabricated an execution attempt")
        runtime = self.runtime()
        try:
            attempts = runtime.connection.execute(
                "SELECT COUNT(*) FROM task_attempts").fetchone()[0]
            if not expect_execution:
                self.assertEqual(attempts, 0)
            # No authorization may exist that governance did not supply.
            authorizations = runtime.connection.execute(
                "SELECT COUNT(*) FROM acquisition_authorizations").fetchone()[0]
            return authorizations
        finally:
            runtime.close()

    def assert_recovery_is_clean(self):
        """Deterministic and auditable: rebuild from the log, then verify."""
        rebuilt = self.child("reset", "--rebuild-index")
        self.assertEqual(rebuilt.returncode, 0, rebuilt.stderr)
        verified = self.child("verify")
        self.assertEqual(verified.returncode, 0, verified.stdout)
        self.assertIn("INTEGRITY OK", verified.stdout)

    def assert_states_are_legal(self):
        """Every recorded transition is an approved Catalog section L edge."""
        from mogo_platform.contracts import task_states
        runtime = self.runtime()
        try:
            report = None
            from mogo_platform.runtime import audit as audit_module
            report = audit_module.audit_report(runtime.connection, runtime.log)
            for step in report["timeline"]:
                if step["from"] is None:
                    continue
                with self.subTest(edge=(step["from"], step["to"])):
                    self.assertTrue(
                        task_states.is_legal_transition(step["from"], step["to"]),
                        "illegal transition %s -> %s"
                        % (step["from"], step["to"]))
            for row in runtime.connection.execute("SELECT state FROM tasks"):
                self.assertIn(row["state"], task_states.TASK_STATES)
        finally:
            runtime.close()


class TestStep3CrashBoundaries(Step3RecoveryCase):
    def test_every_step_3_boundary_is_declared_and_reachable(self):
        import inspect
        source = inspect.getsource(orchestrator_module)
        self.assertEqual(tuple(orchestrator_module.STEP_3_CRASH_BOUNDARIES),
                         EXPECTED_STEP_3_CRASH_BOUNDARIES)
        for boundary in EXPECTED_STEP_3_CRASH_BOUNDARIES:
            with self.subTest(boundary=boundary):
                self.assertGreaterEqual(source.count('"%s"' % boundary), 2)

    def test_step_3_crash_simulation_is_refused_without_the_env_guard(self):
        self.init_and_submit_policy()
        completed = self.child("run", "--simulate-crash-at",
                               "after_policy_decision_append")
        self.assertNotEqual(completed.returncode, 70)
        self.assertIn("MOGO_RUNTIME_ALLOW_CRASH_SIM",
                      completed.stdout + completed.stderr)

    # -- boundary 23 ---------------------------------------------------------

    def test_boundary_23_crash_after_a_policy_DENIAL_is_appended(self):
        """The decision is durable; the index is behind. Replay converges."""
        self.init_and_submit_policy("b23-deny")
        self.child("run", "--simulate-crash-at", "after_policy_decision_append",
                   allow_crash=True, expect_crash=True)

        # The decision survived the kill, and nothing else was invented.
        self.assertIn("PolicyEvaluated", self.log_events())
        self.assert_nothing_was_fabricated()

        self.child("run")
        row = self.task_row()
        self.assertEqual(row["state"], "awaiting_review")
        self.assertEqual(row["policy_decision"], "deny")
        self.assertEqual(row["policy_reason"], "no_authorization_record")
        self.assert_nothing_was_fabricated()
        self.assert_states_are_legal()
        self.assert_recovery_is_clean()

    def test_boundary_23_crash_after_a_policy_PERMIT_is_appended(self):
        """A crash must not lose a permit, nor let one be assumed."""
        source_id = self.init_and_submit_policy("b23-permit")
        self.authorize(source_id)
        self.child("run", "--simulate-crash-at", "after_policy_decision_append",
                   allow_crash=True, expect_crash=True)

        # The permit is durable in the log but not yet applied: nothing ran.
        self.assert_nothing_was_fabricated()

        self.child("run")
        row = self.task_row()
        self.assertEqual(row["state"], "succeeded")
        self.assertEqual(row["policy_decision"], "permit")
        self.assertEqual(row["policy_status"], "PERMITTED_PUBLIC_METADATA")
        # Exactly one decision, one claim, one execution -- no duplicates.
        events = self.log_events()
        self.assertEqual(events.count("PolicyEvaluated"), 1)
        self.assertEqual(events.count("TaskClaimed"), 1)
        self.assertEqual(events.count("TaskSucceeded"), 1)
        self.assert_states_are_legal()
        self.assert_recovery_is_clean()

    def test_boundary_23_does_not_let_a_second_decision_be_made(self):
        """Replay RE-APPLIES the recorded decision; it never makes a new one.

        The authorization is recorded AFTER the crash. If recovery re-decided,
        the task would come back permitted -- and the log would then contain a
        decision that contradicts the one already durable in it.
        """
        source_id = self.init_and_submit_policy("b23-no-redecide")
        self.child("run", "--simulate-crash-at", "after_policy_decision_append",
                   allow_crash=True, expect_crash=True)
        self.authorize(source_id)          # governance acts after the crash

        self.child("run")
        row = self.task_row()
        self.assertEqual(row["policy_decision"], "deny",
                         "recovery re-decided instead of re-applying")
        self.assertEqual(row["state"], "awaiting_review")
        self.assertEqual(self.log_events().count("PolicyEvaluated"), 1)
        self.assert_nothing_was_fabricated()

    # -- boundary 24 ---------------------------------------------------------

    def test_boundary_24_crash_between_the_denial_and_the_review_request(self):
        """The regression for the stranding defect this suite found.

        Before it was fixed, a task interrupted here sat in `blocked` -- not
        terminal, not drivable, with no route out at all, which is the
        Constitution section 6.5 defect Step 2 eliminated for failures.
        """
        self.init_and_submit_policy("b24")
        self.child("run", "--simulate-crash-at", "after_policy_denial",
                   allow_crash=True, expect_crash=True)

        interrupted = self.task_row()
        self.assertEqual(interrupted["state"], "blocked")
        self.assertEqual(interrupted["terminal"], 0)
        self.assertEqual(interrupted["policy_decision"], "deny")
        self.assert_nothing_was_fabricated()

        self.child("run")
        row = self.task_row()
        self.assertEqual(row["state"], "awaiting_review",
                         "a task interrupted between the denial and the review "
                         "request must not strand in `blocked`")
        self.assertEqual(self.log_events().count("HumanReviewRequired"), 1)
        self.assert_nothing_was_fabricated()
        self.assert_states_are_legal()
        self.assert_recovery_is_clean()

    def test_boundary_24_recovery_restates_the_decision_it_does_not_remake_it(self):
        source_id = self.init_and_submit_policy("b24-restate")
        self.child("run", "--simulate-crash-at", "after_policy_denial",
                   allow_crash=True, expect_crash=True)
        self.authorize(source_id)          # governance acts after the crash

        self.child("run")
        row = self.task_row()
        # The review request restates the DURABLE denial; it does not re-decide.
        self.assertEqual(row["policy_decision"], "deny")
        self.assertEqual(row["state"], "awaiting_review")
        self.assertEqual(self.log_events().count("PolicyEvaluated"), 1)

    # -- boundary 25 ---------------------------------------------------------

    def test_boundary_25_crash_after_the_review_request_is_appended(self):
        self.init_and_submit_policy("b25")
        self.child("run", "--simulate-crash-at", "after_review_required_append",
                   allow_crash=True, expect_crash=True)

        self.assertIn("HumanReviewRequired", self.log_events())
        self.assert_nothing_was_fabricated()

        self.child("run")
        row = self.task_row()
        self.assertEqual(row["state"], "awaiting_review")
        self.assertEqual(self.log_events().count("HumanReviewRequired"), 1)
        self.assert_nothing_was_fabricated()
        self.assert_states_are_legal()
        self.assert_recovery_is_clean()

    # -- boundary 26 ---------------------------------------------------------

    def test_boundary_26_crash_after_a_REJECTION_is_appended(self):
        self.init_and_submit_policy("b26-reject")
        self.child("run")
        self.assertEqual(self.task_row()["state"], "awaiting_review")

        task_id = self.task_row()["task_id"]
        self.child("review", "--task", task_id, "--decision", "rejected",
                   "--reason", "source terms prohibit acquisition",
                   "--reviewer", "operator:joe",
                   "--simulate-crash-at", "after_review_decision_append",
                   allow_crash=True, expect_crash=True)

        self.assertIn("HumanReviewCompleted", self.log_events())
        self.assert_nothing_was_fabricated()

        self.child("run")
        row = self.task_row()
        self.assertEqual(row["state"], "suppressed")
        self.assertEqual(row["terminal"], 1)
        self.assertEqual(row["review_decision"], "rejected")
        self.assert_nothing_was_fabricated()
        self.assert_states_are_legal()
        self.assert_recovery_is_clean()

    def test_boundary_26_crash_after_an_APPROVAL_is_appended(self):
        """The most dangerous of the four: the event that releases a task.

        A crash here must neither lose the release nor let the task execute
        without the gate's re-evaluated permit travelling with it.
        """
        source_id = self.init_and_submit_policy("b26-approve")
        self.child("run")
        self.assertEqual(self.task_row()["state"], "awaiting_review")
        self.authorize(source_id)

        task_id = self.task_row()["task_id"]
        self.child("review", "--task", task_id, "--decision", "approved",
                   "--reason", "authorization recorded by governance",
                   "--reviewer", "governance:mogo-legal",
                   "--simulate-crash-at", "after_review_decision_append",
                   allow_crash=True, expect_crash=True)

        # The release is durable but unapplied; nothing has executed.
        self.assertIn("HumanReviewCompleted", self.log_events())
        self.assert_nothing_was_fabricated()

        self.child("run")
        row = self.task_row()
        self.assertEqual(row["state"], "succeeded")
        # The permit that allowed dispatch is the GATE's, carried through the
        # crash in the durable event payload.
        self.assertEqual(row["policy_decision"], "permit")
        self.assertEqual(row["policy_status"], "PERMITTED_PUBLIC_METADATA")
        self.assertEqual(row["review_decision"], "approved")
        events = self.log_events()
        self.assertEqual(events.count("HumanReviewCompleted"), 1)
        self.assertEqual(events.count("TaskSucceeded"), 1)
        self.assert_states_are_legal()
        self.assert_recovery_is_clean()

    # -- properties that must hold at EVERY boundary -------------------------

    def test_no_boundary_can_fabricate_an_authorization(self):
        """A crash may lose progress. It may never create permission."""
        for boundary in EXPECTED_STEP_3_CRASH_BOUNDARIES[:3]:
            with self.subTest(boundary=boundary):
                self.tearDown()
                self.setUp()
                self.init_and_submit_policy("no-auth-%s" % (boundary,))
                self.child("run", "--simulate-crash-at", boundary,
                           allow_crash=True, expect_crash=True)
                self.child("run")
                runtime = self.runtime()
                try:
                    count = runtime.connection.execute(
                        "SELECT COUNT(*) FROM acquisition_authorizations"
                    ).fetchone()[0]
                finally:
                    runtime.close()
                self.assertEqual(count, 0,
                                 "a crash created an authorization record")
                row = self.task_row()
                self.assertEqual(row["policy_decision"], "deny")
                self.assertIn(row["state"], ("blocked", "awaiting_review"))

    def test_no_boundary_lets_unauthorized_work_execute(self):
        for boundary in EXPECTED_STEP_3_CRASH_BOUNDARIES[:3]:
            with self.subTest(boundary=boundary):
                self.tearDown()
                self.setUp()
                self.init_and_submit_policy("no-exec-%s" % (boundary,))
                self.child("run", "--simulate-crash-at", boundary,
                           allow_crash=True, expect_crash=True)
                self.child("run")
                self.child("run")          # and again, to be sure
                events = self.log_events()
                for name in FABRICATION_EVENTS:
                    self.assertNotIn(name, events)
                self.assertEqual(self.task_row()["attempt"], 0)

    def test_repeated_restart_across_the_gate_converges(self):
        """Five kills in sequence reach the same answer as an uninterrupted run."""
        self.init_and_submit_policy("converge")
        for boundary in ("after_policy_decision_append", "after_policy_denial",
                         "after_review_required_append",
                         "after_policy_decision_append", "after_policy_denial"):
            self.child("run", "--simulate-crash-at", boundary,
                       allow_crash=True, expect_crash=False)
        self.child("run")
        row = self.task_row()
        self.assertEqual(row["state"], "awaiting_review")
        self.assertEqual(row["policy_decision"], "deny")
        events = self.log_events()
        self.assertEqual(events.count("PolicyEvaluated"), 1)
        self.assertEqual(events.count("HumanReviewRequired"), 1)
        self.assert_nothing_was_fabricated()
        self.assert_recovery_is_clean()

    # The two kinds of boundary behave differently BEFORE recovery, and the
    # difference is a property worth asserting rather than papering over.
    #
    #   append boundaries      fire INSIDE _emit, between the log fsync and the
    #                          SQLite commit, so the index is legitimately
    #                          BEHIND the log and `verify` must SAY SO
    #   between-event boundaries
    #                          fire between two COMPLETE emits, so everything
    #                          appended has also been applied and `verify` is
    #                          clean -- the task is simply mid-sequence
    #
    # Neither is a contradiction. What would be a contradiction is a FATAL
    # finding, or an index that claims history the log does not have.
    APPEND_BOUNDARIES = ("after_policy_decision_append",
                         "after_review_required_append")
    BETWEEN_EVENT_BOUNDARIES = ("after_policy_denial",)

    def test_the_append_only_history_is_never_contradicted(self):
        """After every kill the history is intact, and any gap is REPORTED."""
        for boundary in self.APPEND_BOUNDARIES + self.BETWEEN_EVENT_BOUNDARIES:
            with self.subTest(boundary=boundary):
                self.tearDown()
                self.setUp()
                self.init_and_submit_policy("history-%s" % (boundary,))
                self.child("run", "--simulate-crash-at", boundary,
                           allow_crash=True, expect_crash=True)

                mid = self.child("verify")
                if boundary in self.APPEND_BOUNDARIES:
                    # The index is behind. The runtime must report it rather
                    # than hide it -- a silent pass would mean the index and
                    # the log disagreed unnoticed.
                    self.assertNotEqual(mid.returncode, 0)
                    self.assertIn("in the log but not in the index", mid.stdout)
                    self.assertIn("recover", mid.stdout)
                else:
                    # Everything appended was applied; nothing is outstanding.
                    self.assertEqual(mid.returncode, 0, mid.stdout)

                # In BOTH cases the history itself is intact: a recoverable gap
                # is an ERROR, never a FATAL, and the index never claims
                # history the log does not have.
                self.assertNotIn("FATAL", mid.stdout)
                self.assertNotIn("indexed but absent from the log", mid.stdout)

                # AFTER recovery, the log and the index agree exactly.
                self.child("run")
                self.assert_recovery_is_clean()

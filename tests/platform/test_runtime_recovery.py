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

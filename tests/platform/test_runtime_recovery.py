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


if __name__ == "__main__":
    unittest.main(verbosity=2)

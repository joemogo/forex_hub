#!/usr/bin/env python3
"""MOGO-011 Step 1 -- the twelve non-negotiable milestone outcomes, end to end.

Pure stdlib (unittest). Offline, deterministic, repeatable. Tempfile state root.

This suite is the milestone acceptance test. Each method below maps to one
numbered outcome from the MOGO-011 tasking, so a reader can check the milestone
against the test names alone.

Run with:
    python3 -m unittest tests.platform.test_runtime_end_to_end -v
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

from mogo_platform.contracts import ids  # noqa: E402
from mogo_platform.runtime import audit as audit_module  # noqa: E402
from mogo_platform.runtime import cli as cli_module  # noqa: E402
from mogo_platform.runtime import event_log as event_log_module  # noqa: E402
from mogo_platform.runtime import orchestrator as orchestrator_module  # noqa: E402
from mogo_platform.runtime import paths as paths_module  # noqa: E402
from mogo_platform.runtime import store  # noqa: E402


class EndToEndCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = os.path.join(self._tmp.name, "state")
        self.paths = paths_module.RuntimePaths(self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def cli(self, *argv):
        env = dict(os.environ)
        env["MOGO_RUNTIME_STATE_ROOT"] = self.root
        env.pop("MOGO_RUNTIME_ALLOW_CRASH_SIM", None)
        return subprocess.run([sys.executable, LAUNCHER] + list(argv),
                              cwd=REPO_ROOT, env=env, capture_output=True, text=True)

    def full_run(self):
        self.assertEqual(self.cli("init").returncode, 0)
        submitted = self.cli("submit", "--demo")
        self.assertEqual(submitted.returncode, 0)
        ran = self.cli("run")
        self.assertEqual(ran.returncode, 0)
        return submitted, ran

    def read(self):
        connection = store.open_database(self.paths, create=False)
        log = event_log_module.EventLog(self.paths)
        return connection, log


class TestTwelveMilestoneOutcomes(EndToEndCase):
    def test_outcome_01_a_valid_command_is_submitted(self):
        self.cli("init")
        result = self.cli("submit", "--demo")
        self.assertIn("ACCEPTED", result.stdout)
        self.assertIn("idempotencyKey=", result.stdout)

    def test_outcome_02_command_is_validated_by_mogo010_contracts(self):
        envelope, payload = cli_module.build_demo_command()
        from mogo_platform.contracts import command as command_contract
        validated = command_contract.validate_command(envelope, payload=payload)
        self.assertEqual(validated["commandVersion"], 1)
        self.assertEqual(command_contract.COMMAND_SCHEMA_VERSION,
                         "mogo.platform.operational.command.v1")

    def test_outcome_03_a_durable_task_is_created(self):
        self.full_run()
        connection, _log = self.read()
        try:
            rows = connection.execute("SELECT * FROM tasks").fetchall()
            self.assertEqual(len(rows), 1)
        finally:
            connection.close()

    def test_outcome_04_policy_is_applied_only_as_authorized(self):
        self.full_run()
        connection, log = self.read()
        try:
            policy = [r for r in log.scan().records
                      if r.event["eventType"] == "PolicyEvaluated"]
            self.assertEqual(len(policy), 1)
            self.assertEqual(policy[0].event["payload"]["decision"], "not_applicable")
            self.assertEqual(policy[0].event["payload"]["operationClass"],
                             "non_acquisition")
            self.assertEqual(policy[0].event["producer"], "policyGate")
        finally:
            connection.close()

    def test_outcome_05_task_moves_through_approved_states(self):
        self.full_run()
        connection, log = self.read()
        try:
            report = audit_module.audit_report(connection, log)
            states = [step["to"] for step in report["timeline"]]
            self.assertEqual(states, ["requested", "policy_check", "queued",
                                      "claimed", "running", "succeeded"])
        finally:
            connection.close()

    def test_outcome_06_a_registered_capability_claims_the_task(self):
        self.full_run()
        connection, log = self.read()
        try:
            claimed = [r for r in log.scan().records
                       if r.event["eventType"] == "TaskClaimed"]
            self.assertEqual(len(claimed), 1)
            self.assertEqual(claimed[0].event["payload"]["capabilityId"],
                             "CAP|research|runtime-echo")
            row = connection.execute(
                "SELECT lifecycle_status, enabled_state FROM capabilities "
                "WHERE capability_id = ?", ("CAP|research|runtime-echo",)).fetchone()
            self.assertEqual(row["lifecycle_status"], "production")
            self.assertEqual(row["enabled_state"], 1)
        finally:
            connection.close()

    def test_outcome_07_the_capability_performs_a_deterministic_operation(self):
        self.full_run()
        connection, _log = self.read()
        try:
            result_hash = connection.execute(
                "SELECT result_hash FROM tasks").fetchone()[0]
        finally:
            connection.close()
        expected = ids.content_hash_of(cli_module.DEMO_PAYLOAD)
        self.assertEqual(result_hash, expected)

    def test_outcome_08_operational_events_are_recorded_durably(self):
        self.full_run()
        _connection, log = self.read()
        try:
            self.assertTrue(os.path.exists(log.path))
            self.assertGreater(log.size_bytes(), 0)
            self.assertEqual(len(log.scan().records), 9)
        finally:
            _connection.close()

    def test_outcome_09_the_task_reaches_a_terminal_state(self):
        self.full_run()
        connection, _log = self.read()
        try:
            row = connection.execute(
                "SELECT state, terminal FROM tasks").fetchone()
            self.assertEqual(row["state"], "succeeded")
            self.assertEqual(row["terminal"], 1)
        finally:
            connection.close()

    def test_outcome_10_rerunning_the_same_command_duplicates_nothing(self):
        self.full_run()
        connection, log = self.read()
        try:
            before_events = len(log.scan().records)
            before_tasks = connection.execute(
                "SELECT COUNT(*) FROM tasks").fetchone()[0]
        finally:
            connection.close()

        again = self.cli("submit", "--demo")
        self.assertIn("DUPLICATE SUPPRESSED", again.stdout)
        self.assertIn("tasks created=0 events appended=0", again.stdout)

        connection, log = self.read()
        try:
            self.assertEqual(len(log.scan().records), before_events)
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[0],
                before_tasks)
        finally:
            connection.close()

    def test_outcome_11_restart_after_interruption_resumes_safely(self):
        env = dict(os.environ)
        env["MOGO_RUNTIME_STATE_ROOT"] = self.root
        env["MOGO_RUNTIME_ALLOW_CRASH_SIM"] = "1"
        self.cli("init")
        self.cli("submit", "--demo")
        crashed = subprocess.run(
            [sys.executable, LAUNCHER, "run", "--simulate-crash-at", "mid_execution"],
            cwd=REPO_ROOT, env=env, capture_output=True, text=True)
        self.assertEqual(crashed.returncode, 70)

        resumed = self.cli("run")
        self.assertEqual(resumed.returncode, 0)
        connection, _log = self.read()
        try:
            rows = connection.execute("SELECT state, result_hash FROM tasks").fetchall()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["state"], "succeeded")
            self.assertEqual(rows[0]["result_hash"],
                             ids.content_hash_of(cli_module.DEMO_PAYLOAD))
        finally:
            connection.close()

    def test_outcome_12_activity_is_inspectable_through_an_audit_report(self):
        self.full_run()
        report = self.cli("audit")
        self.assertEqual(report.returncode, 0)
        for section in ("EVENTS", "STATE TIMELINE", "COMMAND SUBMISSIONS",
                        "TASKS", "INTEGRITY"):
            self.assertIn(section, report.stdout)
        self.assertIn("OK", report.stdout)


class TestCliSurface(EndToEndCase):
    def test_demo_sequence_completes(self):
        result = self.cli("demo")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("DUPLICATE SUPPRESSED", result.stdout)
        self.assertIn("INTEGRITY", result.stdout)

    def test_demo_is_reproducible(self):
        first = self.cli("demo")
        self.tearDown()
        self.setUp()
        second = self.cli("demo")
        self.assertEqual(first.returncode, second.returncode)
        # Identifiers and timestamps differ by design; the RESULT does not.
        expected = ids.content_hash_of(cli_module.DEMO_PAYLOAD)
        self.assertIn(expected, first.stdout)
        self.assertIn(expected, second.stdout)

    def test_status_reports_health(self):
        self.full_run()
        result = self.cli("status")
        self.assertEqual(result.returncode, 0)
        self.assertIn("succeeded=1", result.stdout)
        self.assertIn("CAP|research|runtime-echo", result.stdout)

    def test_verify_passes_on_a_clean_state(self):
        self.full_run()
        result = self.cli("verify")
        self.assertEqual(result.returncode, 0)
        self.assertIn("INTEGRITY OK", result.stdout)

    def test_verify_fails_on_a_tampered_log(self):
        self.full_run()
        log = event_log_module.EventLog(self.paths)
        with open(log.path, "rb") as handle:
            lines = handle.read().split(b"\n")
        event = json.loads(lines[0].decode("utf-8"))
        event["payload"] = {"tampered": True}
        lines[0] = ids.canonical_json_bytes(event)
        with open(log.path, "wb") as handle:
            handle.write(b"\n".join(lines))
        result = self.cli("verify")
        self.assertNotEqual(result.returncode, 0)

    def test_audit_json_output_is_machine_readable(self):
        self.full_run()
        result = self.cli("audit", "--json")
        self.assertEqual(result.returncode, 0)
        document = json.loads(result.stdout)
        self.assertEqual(len(document["events"]), 9)
        self.assertEqual(document["integrity"], [])

    def test_reset_restores_a_pristine_state(self):
        self.full_run()
        result = self.cli("reset", "--confirm")
        self.assertEqual(result.returncode, 0)
        self.assertFalse(os.path.exists(self.paths.database))
        self.assertFalse(os.path.exists(self.paths.event_log))
        self.assertEqual(self.cli("init").returncode, 0)

    def test_reset_refuses_without_confirmation(self):
        self.full_run()
        result = self.cli("reset")
        self.assertEqual(result.returncode, 2)
        self.assertTrue(os.path.exists(self.paths.database))

    def test_rebuild_index_proves_the_log_is_authoritative(self):
        self.full_run()
        result = self.cli("reset", "--rebuild-index")
        self.assertEqual(result.returncode, 0)
        self.assertIn("REBUILT index from the log alone", result.stdout)
        self.assertEqual(self.cli("verify").returncode, 0)
        connection, _log = self.read()
        try:
            row = connection.execute("SELECT state, result_hash FROM tasks").fetchone()
            self.assertEqual(row["state"], "succeeded")
            self.assertEqual(row["result_hash"],
                             ids.content_hash_of(cli_module.DEMO_PAYLOAD))
        finally:
            connection.close()

    def test_status_on_an_uninitialized_root_fails_closed(self):
        result = self.cli("status")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("run `init` first", result.stdout + result.stderr)


class TestRuntimeStateIsIsolated(EndToEndCase):
    def test_no_write_landed_outside_the_state_root(self):
        before = self._repo_snapshot()
        self.cli("demo")
        self.assertEqual(self._repo_snapshot(), before)

    def _repo_snapshot(self):
        """mtimes of every tracked-ish directory the runtime must never touch."""
        watched = ("evidence", "docs", "scripts", "tests", "index.html",
                   "regression-baseline.json")
        snapshot = {}
        for name in watched:
            target = os.path.join(REPO_ROOT, name)
            if os.path.exists(target):
                snapshot[name] = os.path.getmtime(target)
        return snapshot

    def test_projection_files_live_under_the_state_root(self):
        self.full_run()
        found = []
        for root, _dirs, files in os.walk(self.paths.tasks_dir):
            for name in files:
                found.append(os.path.join(root, name))
        self.assertEqual(len(found), 1)
        self.assertTrue(self.paths.is_inside_state_root(found[0]))
        with open(found[0], "r", encoding="utf-8") as handle:
            document = json.load(handle)
        self.assertEqual(document["state"], "succeeded")


if __name__ == "__main__":
    unittest.main(verbosity=2)

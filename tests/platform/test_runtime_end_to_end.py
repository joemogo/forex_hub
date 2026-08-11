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


# ---------------------------------------------------------------------------
# MOGO-011 Step 2 -- the fifteen Primary Outcomes, through the CLI
# ---------------------------------------------------------------------------


class Step2EndToEndCase(EndToEndCase):
    """Driven through the real CLI in child processes, as an operator would."""

    def full_step_2_run(self):
        self.assertEqual(self.cli("init").returncode, 0)
        self.assertEqual(self.cli("submit", "--demo-retry", "1").returncode, 0)
        self.assertEqual(self.cli("submit", "--demo-retry", "9").returncode, 0)
        ran = self.cli("run")
        # A dead-lettered task is a terminal failure and `run` reports one.
        self.assertEqual(ran.returncode, 3, ran.stdout)
        return ran

    def tasks(self):
        runtime = orchestrator_module.Orchestrator(paths=self.paths,
                                                   create=False).open()
        try:
            return [dict(r) for r in runtime.connection.execute(
                "SELECT * FROM tasks ORDER BY created_log_sequence")]
        finally:
            runtime.close()

    def log_records(self):
        return event_log_module.EventLog(self.paths).scan(verify=True).records


class TestStep2PrimaryOutcomes(Step2EndToEndCase):
    def test_primary_outcome_02_a_capability_fails_with_a_retryable_error(self):
        self.full_step_2_run()
        classes = {r.event.get("errorClass") for r in self.log_records()
                   if r.event["eventType"] == "TaskFailed"}
        self.assertEqual(classes, {"transient"})

    def test_primary_outcome_03_the_orchestrator_records_the_failure(self):
        self.full_step_2_run()
        failures = [r for r in self.log_records()
                    if r.event["eventType"] == "TaskFailed"]
        self.assertTrue(failures)
        for record in failures:
            payload = record.event["payload"]
            self.assertTrue(payload["declaredByCapability"])
            self.assertIsInstance(payload["attempt"], int)
            self.assertIsInstance(payload["leaseGeneration"], int)

    def test_primary_outcome_05_the_full_transition_sequence_occurs(self):
        self.full_step_2_run()
        succeeded = [t for t in self.tasks() if t["state"] == "succeeded"][0]
        types = [r.event["eventType"] for r in self.log_records()
                 if r.event.get("taskId") == succeeded["task_id"]]
        for expected in ("TaskFailed", "TaskRetryScheduled", "TaskRetryReleased",
                         "TaskClaimed", "TaskStarted", "TaskSucceeded"):
            self.assertIn(expected, types)

    def test_primary_outcome_06_no_release_precedes_its_eligibility(self):
        """Re-derived from the log alone, so it survives the deletion of every
        in-process assertion."""
        self.full_step_2_run()
        scheduled, releases = {}, 0
        for record in self.log_records():
            event = record.event
            task_id = event.get("taskId")
            if event["eventType"] == "TaskRetryScheduled":
                scheduled.setdefault(task_id, []).append(
                    event["payload"]["eligibleAtUtc"])
            elif event["eventType"] == "TaskRetryReleased":
                releases += 1
                payload = event["payload"]
                self.assertGreaterEqual(payload["observedAtUtc"],
                                        payload["scheduledEligibleAtUtc"])
                self.assertIn(payload["scheduledEligibleAtUtc"],
                              scheduled.get(task_id, []))
        self.assertGreater(releases, 0)

    def test_primary_outcome_07_each_claim_takes_a_fresh_lease(self):
        self.full_step_2_run()
        by_task = {}
        for record in self.log_records():
            if record.event["eventType"] != "TaskClaimed":
                continue
            payload = record.event["payload"]
            by_task.setdefault(record.event["taskId"], []).append(
                payload["leaseGeneration"])
            self.assertEqual(payload["claimMode"], "compare_and_set_lease")
        self.assertTrue(by_task)
        for task_id, generations in by_task.items():
            with self.subTest(task=task_id):
                self.assertEqual(generations, sorted(set(generations)))
                self.assertEqual(generations[0], 1)

    def test_primary_outcome_08_it_succeeds_on_a_later_attempt(self):
        self.full_step_2_run()
        succeeded = [t for t in self.tasks() if t["state"] == "succeeded"][0]
        self.assertEqual(succeeded["attempt"], 2)

    def test_primary_outcome_09_events_are_ordered_and_auditable(self):
        self.full_step_2_run()
        by_workflow = {}
        for record in self.log_records():
            by_workflow.setdefault(record.event["workflowId"], []).append(
                record.event["sequence"])
        for workflow_id, sequences in by_workflow.items():
            with self.subTest(workflow=workflow_id):
                self.assertEqual(sequences, list(range(len(sequences))))

    def test_primary_outcome_11_and_12_exhaustion_reaches_dead_letter(self):
        self.full_step_2_run()
        dead = [t for t in self.tasks() if t["state"] == "dead_lettered"]
        self.assertEqual(len(dead), 1)
        self.assertEqual(dead[0]["attempt"], 3)
        self.assertEqual(dead[0]["dead_letter_reason"], "attempts_exhausted")
        payload = [r.event["payload"] for r in self.log_records()
                   if r.event["eventType"] == "TaskDeadLettered"][0]
        self.assertEqual(len(payload["attemptHistory"]), 3)

    def test_primary_outcome_13_a_repeated_semantic_command_duplicates_nothing(self):
        self.full_step_2_run()
        before = len(self.tasks())
        repeated = self.cli("submit", "--demo-retry", "1")
        self.assertEqual(repeated.returncode, 0)
        self.assertIn("DUPLICATE SUPPRESSED", repeated.stdout)
        self.assertEqual(len(self.tasks()), before)

    def test_primary_outcome_14_the_index_is_rebuildable_from_the_log(self):
        self.full_step_2_run()
        before = self.tasks()
        rebuilt = self.cli("reset", "--rebuild-index")
        self.assertEqual(rebuilt.returncode, 0, rebuilt.stderr)
        self.assertEqual(self.tasks(), before)
        self.assertEqual(self.cli("verify").returncode, 0)

    def test_the_failures_view_answers_what_failed_when_and_why(self):
        self.full_step_2_run()
        failures = self.cli("failures")
        self.assertEqual(failures.returncode, 0, failures.stderr)
        for heading in ("FAILURES BY ERROR CLASS", "DEAD LETTERS",
                        "ATTEMPT HISTORY", "LEASES", "GATES"):
            self.assertIn(heading, failures.stdout)
        self.assertIn("transient", failures.stdout)
        self.assertIn("attempts_exhausted", failures.stdout)
        # MOGO-014 Step 2 opened the A-5 gate under explicit authorization, so
        # the failures view reports OPEN.
        self.assertIn("OPEN", failures.stdout)
        # MOGO-016 satisfied the last connector gate, so this view no longer has
        # an unmet gate to name. The property being protected is unchanged and
        # is what actually matters: the operator can still read the state of
        # every gate here WITHOUT READING CODE, and is told plainly that all
        # gates being met does not make authorization optional.
        self.assertIn("connector gates", failures.stdout)
        self.assertIn("0 UNMET", failures.stdout)
        self.assertIn("every declared connector gate is met", failures.stdout)
        self.assertIn("an unauthorized source is still denied", failures.stdout)

    def test_the_status_view_reports_the_step_2_signals(self):
        self.full_step_2_run()
        status = self.cli("status")
        self.assertEqual(status.returncode, 0, status.stderr)
        for line in ("attempts", "retries", "dead letters", "A-5 gate",
                     "connector gates"):
            self.assertIn(line, status.stdout)
        self.assertIn("schema version  : 3", status.stdout)
        for line in ("policy", "awaiting review", "authorizations"):
            self.assertIn(line, status.stdout)

    def test_verify_passes_every_step_2_invariant(self):
        self.full_step_2_run()
        verified = self.cli("verify")
        self.assertEqual(verified.returncode, 0, verified.stdout)
        self.assertIn("INTEGRITY OK", verified.stdout)

    def test_the_demo_runs_end_to_end_and_leaves_a_clean_state_root(self):
        demo = self.cli("demo")
        self.assertEqual(demo.returncode, 0, demo.stderr)
        self.assertIn("SCENARIO 1", demo.stdout)
        self.assertIn("SCENARIO 2", demo.stdout)
        self.assertIn("DUPLICATE SUPPRESSED", demo.stdout)
        self.assertIn("REBUILT", demo.stdout)
        self.assertIn("INTEGRITY OK", demo.stdout)
        # Nothing is left non-terminal.
        self.assertEqual([t for t in self.tasks() if not t["terminal"]], [])

    def test_a_pre_v2_state_root_is_refused_by_a_report_command_then_migrated(self):
        """The upgrade path, through the CLI, exactly as an operator meets it.

        A report command takes no process lock, so it must not migrate -- and
        it must not read v2 tables out of a v1 database either. It refuses,
        names the versions, and says which command does migrate. `init` then
        does, under the lock.
        """
        from mogo_platform.runtime import schema as schema_module
        from mogo_platform.runtime import store as store_module

        # A GENUINE v1 database: built by running the shipped v1 migration
        # exactly as it stands, not by removing pieces from a v2 one. A
        # hand-degraded v2 database would still carry the v2 COLUMNS and would
        # therefore test a state root that has never existed.
        paths_module.ensure_state_root(self.paths)
        connection = store_module.open_database(self.paths, create=True)
        try:
            with store_module.immediate_transaction(connection):
                schema_module._create_v1(connection)
                connection.execute(
                    "INSERT OR REPLACE INTO schema_meta (key, value) VALUES (?,?)",
                    ("schema_version", "1"))
                connection.execute(
                    "INSERT INTO commands (command_id, command_type,"
                    " command_version, workflow_id, correlation_id,"
                    " idempotency_key, target_capability, issued_at, issued_by,"
                    " payload_hash, payload_json, accepted_log_sequence) VALUES "
                    "('c1','NormalizeArtifact',1,'w','r','k',"
                    "'CAP|research|runtime-echo','2026-08-07T00:00:00.000Z',"
                    "'operator:x','h','{}',1)")
                connection.execute(
                    "INSERT INTO tasks (task_id, workflow_id, correlation_id,"
                    " command_id, capability_id, idempotency_key, state, attempt,"
                    " created_log_sequence, last_log_sequence, terminal) VALUES "
                    "('t1','w','r','c1','CAP|research|runtime-echo','k',"
                    "'succeeded',1,1,1,1)")
        finally:
            connection.close()

        refused = self.cli("status")
        self.assertNotEqual(refused.returncode, 0)
        combined = refused.stdout + refused.stderr
        self.assertIn("schema version 1", combined)
        self.assertIn("init", combined)

        migrated = self.cli("init")
        self.assertEqual(migrated.returncode, 0, migrated.stderr)
        self.assertIn("schema version         : %d" % schema_module.SCHEMA_VERSION,
                      migrated.stdout)
        self.assertEqual(self.cli("status").returncode, 0)
        self.assertEqual(self.cli("failures").returncode, 0)
        # The pre-existing v1 task survived the migration untouched, and gained
        # the restrictive defaults rather than being rewritten.
        tasks = self.tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["task_id"], "t1")
        self.assertEqual(tasks[0]["state"], "succeeded")
        self.assertEqual(tasks[0]["attempt"], 1)
        self.assertEqual(tasks[0]["attempt_limit"], 3)
        self.assertEqual(tasks[0]["lease_generation"], 0)
        self.assertIsNone(tasks[0]["lease_holder"])
        self.assertIsNone(tasks[0]["retry_eligible_at"])

    def test_a_clock_override_is_refused_without_its_env_guard(self):
        self.cli("init")
        refused = self.cli("run", "--now", "2026-08-08T12:00:00.000Z")
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("MOGO_RUNTIME_ALLOW_CLOCK_OVERRIDE",
                      refused.stdout + refused.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)

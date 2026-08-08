#!/usr/bin/env python3
"""MOGO-011 Step 1 -- command receipt, idempotency and the event sequence.

Pure stdlib (unittest). Offline, deterministic, repeatable. Tempfile state root.

Run with:
    python3 -m unittest tests.platform.test_runtime_orchestrator -v
"""

import os
import sys
import tempfile
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC_DIR = os.path.join(REPO_ROOT, "platform", "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from mogo_platform.contracts import ids  # noqa: E402
from mogo_platform.runtime import cli as cli_module  # noqa: E402
from mogo_platform.runtime import orchestrator as orchestrator_module  # noqa: E402
from mogo_platform.runtime import paths as paths_module  # noqa: E402

# Independently transcribed from Step 1 plan section 10: the happy path is nine
# events in this exact order.
EXPECTED_HAPPY_PATH = (
    "WorkflowStarted",
    "CommandAccepted",
    "TaskRequested",
    "TaskPolicyCheckRequested",
    "PolicyEvaluated",
    "TaskClaimed",
    "TaskStarted",
    "TaskSucceeded",
    "WorkflowCompleted",
)

EXPECTED_STATE_PATH = ("requested", "policy_check", "queued", "claimed",
                       "running", "succeeded")


class OrchestratorCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.paths = paths_module.RuntimePaths(os.path.join(self._tmp.name, "state"))
        self.runtime = orchestrator_module.Orchestrator(paths=self.paths).open()
        self.runtime.register_builtin_capabilities()

    def tearDown(self):
        self.runtime.close()
        self._tmp.cleanup()

    def submit_demo(self, payload=None):
        envelope, resolved = cli_module.build_demo_command(payload=payload)
        return self.runtime.submit(envelope, resolved)

    def event_types(self):
        return [r.event["eventType"] for r in self.runtime.log.scan().records]


class TestHappyPath(OrchestratorCase):
    def test_full_happy_path_reaches_succeeded(self):
        outcome = self.submit_demo()
        self.runtime.run_once()
        row = self.runtime.connection.execute(
            "SELECT state, terminal FROM tasks WHERE task_id = ?",
            (outcome.task_id,)).fetchone()
        self.assertEqual(row["state"], "succeeded")
        self.assertEqual(row["terminal"], 1)

    def test_nine_events_in_the_approved_order(self):
        self.submit_demo()
        self.runtime.run_once()
        self.assertEqual(tuple(self.event_types()), EXPECTED_HAPPY_PATH)

    def test_state_path_follows_catalog_section_l(self):
        outcome = self.submit_demo()
        self.runtime.run_once()
        from mogo_platform.runtime import projection
        states = []
        for record in self.runtime.log.scan().records:
            transition = projection.TRANSITIONS.get(record.event["eventType"])
            if transition and record.event.get("taskId") == outcome.task_id:
                states.append(transition[1])
        self.assertEqual(tuple(states), EXPECTED_STATE_PATH)

    def test_per_workflow_sequence_starts_at_zero_and_is_contiguous(self):
        self.submit_demo()
        self.runtime.run_once()
        sequences = [r.event["sequence"] for r in self.runtime.log.scan().records]
        self.assertEqual(sequences, list(range(len(sequences))))

    def test_producer_attribution_matches_the_transition_authority(self):
        self.submit_demo()
        self.runtime.run_once()
        producers = {r.event["eventType"]: r.event["producer"]
                     for r in self.runtime.log.scan().records}
        self.assertEqual(producers["PolicyEvaluated"], "policyGate")
        self.assertTrue(producers["TaskClaimed"].startswith("worker:"))
        self.assertTrue(producers["TaskStarted"].startswith("worker:"))
        self.assertEqual(producers["TaskRequested"], "orchestrator")
        self.assertEqual(producers["TaskSucceeded"], "orchestrator")

    def test_result_hash_is_recorded_on_the_task(self):
        outcome = self.submit_demo()
        self.runtime.run_once()
        row = self.runtime.connection.execute(
            "SELECT result_hash FROM tasks WHERE task_id = ?",
            (outcome.task_id,)).fetchone()
        self.assertTrue(ids.is_sha256_hex(row["result_hash"]))


class TestCommandValidation(OrchestratorCase):
    def _bad(self, **overrides):
        envelope, payload = cli_module.build_demo_command()
        envelope.update(overrides)
        return self.runtime.submit(envelope, payload)

    def test_command_validation_uses_the_mogo010_contract(self):
        outcome = self._bad(commandType="NotARealCommand")
        self.assertEqual(outcome.status, "rejected")

    def test_invalid_command_creates_no_task(self):
        self._bad(commandType="NotARealCommand")
        count = self.runtime.connection.execute(
            "SELECT COUNT(*) FROM tasks").fetchone()[0]
        self.assertEqual(count, 0)

    def test_unsupported_major_version_is_rejected(self):
        self.assertEqual(self._bad(commandVersion=99).status, "rejected")

    def test_malformed_identifier_is_rejected(self):
        self.assertEqual(self._bad(commandId="not-a-uuid").status, "rejected")

    def test_malformed_timestamp_is_rejected(self):
        self.assertEqual(self._bad(issuedAt="2026-08-07").status, "rejected")

    def test_payload_hash_mismatch_is_rejected(self):
        self.assertEqual(self._bad(payloadHash="c" * 64).status, "rejected")

    def test_prohibited_scientific_reference_is_rejected(self):
        self.assertEqual(
            self._bad(inputRefs=["evidence/C1-01-GBP_USD-HARVEST.json"]).status,
            "rejected")

    def test_non_json_shaped_payload_is_rejected(self):
        envelope, _payload = cli_module.build_demo_command()
        self.assertEqual(
            self.runtime.submit(envelope, {"bad": object()}).status, "rejected")

    def test_rejection_is_recorded_and_visible(self):
        self._bad(commandType="NotARealCommand")
        rows = self.runtime.connection.execute(
            "SELECT outcome, reason FROM command_submissions").fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["outcome"], "rejected")
        self.assertTrue(rows[0]["reason"])

    def test_rejection_appends_a_command_rejected_event(self):
        self._bad(commandType="NotARealCommand")
        self.assertIn("CommandRejected", self.event_types())


class TestIdempotency(OrchestratorCase):
    def test_duplicate_semantic_command_creates_no_second_task(self):
        first = self.submit_demo()
        second = self.submit_demo()
        self.assertEqual(second.status, "duplicate_suppressed")
        self.assertEqual(second.task_id, first.task_id)
        count = self.runtime.connection.execute(
            "SELECT COUNT(*) FROM tasks").fetchone()[0]
        self.assertEqual(count, 1)

    def test_duplicate_command_appends_no_event(self):
        self.submit_demo()
        before = len(self.runtime.log.scan().records)
        self.submit_demo()
        self.assertEqual(len(self.runtime.log.scan().records), before)

    def test_duplicate_attempt_is_recorded_and_permanently_visible(self):
        self.submit_demo()
        self.submit_demo()
        self.submit_demo()
        rows = self.runtime.connection.execute(
            "SELECT outcome FROM command_submissions ORDER BY submission_id"
        ).fetchall()
        self.assertEqual([r["outcome"] for r in rows],
                         ["accepted", "duplicate_suppressed", "duplicate_suppressed"])

    def test_idempotency_key_is_derived_from_the_payload_alone(self):
        first, _ = cli_module.build_demo_command()
        second, _ = cli_module.build_demo_command()
        self.assertEqual(first["idempotencyKey"], second["idempotencyKey"])
        self.assertNotEqual(first["commandId"], second["commandId"])

    def test_a_different_payload_is_not_a_duplicate(self):
        self.submit_demo()
        outcome = self.submit_demo(payload={"different": True})
        self.assertEqual(outcome.status, "accepted")
        count = self.runtime.connection.execute(
            "SELECT COUNT(*) FROM tasks").fetchone()[0]
        self.assertEqual(count, 2)

    def test_database_refuses_a_second_command_for_one_key(self):
        """Defence in depth beneath the application-level lookup.

        submit() checks for an existing idempotency key before accepting, so a
        duplicate is normally caught in Python. This asserts the SECOND line of
        defence: even if that check were removed, the database would refuse.
        A mutation run proved the constraint was previously untested.
        """
        import sqlite3
        self.submit_demo()
        row = self.runtime.connection.execute("SELECT * FROM commands").fetchone()
        with self.assertRaises(sqlite3.IntegrityError):
            self.runtime.connection.execute(
                "INSERT INTO commands (command_id, command_type, command_version,"
                " workflow_id, correlation_id, idempotency_key, target_capability,"
                " issued_at, issued_by, payload_hash, payload_json,"
                " accepted_log_sequence, task_id)"
                " VALUES ('other',?,?,?,?,?,?,?,?,?,?,?,NULL)",
                (row["command_type"], row["command_version"], row["workflow_id"],
                 row["correlation_id"], row["idempotency_key"],
                 row["target_capability"], row["issued_at"], row["issued_by"],
                 row["payload_hash"], row["payload_json"],
                 row["accepted_log_sequence"]))

    def test_database_refuses_a_second_task_for_one_key(self):
        import sqlite3
        outcome = self.submit_demo()
        row = self.runtime.connection.execute(
            "SELECT * FROM tasks WHERE task_id = ?", (outcome.task_id,)).fetchone()
        with self.assertRaises(sqlite3.IntegrityError):
            self.runtime.connection.execute(
                "INSERT INTO tasks (task_id, workflow_id, correlation_id, command_id,"
                " capability_id, idempotency_key, state, attempt,"
                " created_log_sequence, last_log_sequence, terminal)"
                " VALUES ('other',?,?,?,?,?,'requested',0,1,1,0)",
                (row["workflow_id"], row["correlation_id"], row["command_id"],
                 row["capability_id"], row["idempotency_key"]))


class TestOnlyOrchestratorWritesState(OrchestratorCase):
    def test_worker_module_receives_no_connection_or_log(self):
        import inspect
        from mogo_platform.runtime import worker as worker_module
        signature = inspect.signature(worker_module.execute_task)
        # The worker gained an execution context and the capability's DECLARED
        # failure classes. Neither is a connection and neither is a log: the
        # context is a plain mapping of recorded values, and the class list is
        # read-only data used to refuse a class the capability never declared.
        # The boundary is that nothing here can write; the parameter list is
        # asserted exactly so that a connection could not be added quietly.
        self.assertEqual(list(signature.parameters),
                         ["capability_callable", "payload", "context",
                          "declared_failure_classes"])
        # AST, not a substring scan: the module docstring legitimately contains
        # the word "connection" while explaining that it never holds one.
        import ast
        tree = ast.parse(inspect.getsource(worker_module))
        called = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute):
                    called.add(func.attr)
                elif isinstance(func, ast.Name):
                    called.add(func.id)
        for forbidden in ("execute", "commit", "append", "write", "open"):
            self.assertNotIn(forbidden, called)

    def test_worker_module_imports_nothing_that_can_write(self):
        import ast
        import inspect
        from mogo_platform.runtime import worker as worker_module
        tree = ast.parse(inspect.getsource(worker_module))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level:
                imported.update(alias.name for alias in node.names)
        self.assertEqual(imported, {"errors"})


if __name__ == "__main__":
    unittest.main(verbosity=2)

#!/usr/bin/env python3
"""MOGO-011 Step 1 -- projection tests: idempotent apply, guarded transitions.

Pure stdlib (unittest). Offline, deterministic, repeatable. Tempfile state root.

These tests hold the line on ADR-012 D-05: the index is DERIVED. The decisive
one is test_rebuild_from_log_reproduces_the_database -- if the index can always
be reconstructed from the log alone, the log is the truth.

Run with:
    python3 -m unittest tests.platform.test_runtime_projection -v
"""

import os
import sys
import tempfile
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC_DIR = os.path.join(REPO_ROOT, "platform", "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from mogo_platform.contracts import task_states  # noqa: E402
from mogo_platform.runtime import cli as cli_module  # noqa: E402
from mogo_platform.runtime import errors as runtime_errors  # noqa: E402
from mogo_platform.runtime import orchestrator as orchestrator_module  # noqa: E402
from mogo_platform.runtime import paths as paths_module  # noqa: E402
from mogo_platform.runtime import projection  # noqa: E402
from mogo_platform.runtime import store  # noqa: E402

# Independently transcribed: every entry must be a Catalog section L edge.
EXPECTED_TRANSITIONS = {
    "TaskRequested":            (None, "requested"),
    "TaskPolicyCheckRequested": ("requested", "policy_check"),
    "PolicyEvaluated":          ("policy_check", "queued"),
    "TaskClaimed":              ("queued", "claimed"),
    "TaskStarted":              ("claimed", "running"),
    "TaskSucceeded":            ("running", "succeeded"),
    "TaskFailed":               ("running", "failed"),
    "TaskReclaimed":            (None, "queued"),
}


class ProjectionCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.paths = paths_module.RuntimePaths(os.path.join(self._tmp.name, "state"))
        self.runtime = orchestrator_module.Orchestrator(paths=self.paths).open()
        self.runtime.register_builtin_capabilities()

    def tearDown(self):
        self.runtime.close()
        self._tmp.cleanup()

    def run_demo(self):
        envelope, payload = cli_module.build_demo_command()
        outcome = self.runtime.submit(envelope, payload)
        self.runtime.run_once()
        return outcome


class TestTransitionTable(ProjectionCase):
    def test_every_declared_transition_is_a_catalog_edge(self):
        self.assertEqual(dict(projection.TRANSITIONS), EXPECTED_TRANSITIONS)
        for event_type, (from_state, to_state) in EXPECTED_TRANSITIONS.items():
            with self.subTest(event=event_type):
                self.assertIn(to_state, task_states.TASK_STATES)
                if from_state is not None:
                    self.assertIn(from_state, task_states.TASK_STATES)
                    self.assertTrue(
                        task_states.is_legal_transition(from_state, to_state))

    def test_reclaimable_states_are_the_in_flight_ones(self):
        self.assertEqual(tuple(projection.RECLAIMABLE_STATES), ("claimed", "running"))
        for state in projection.RECLAIMABLE_STATES:
            self.assertTrue(task_states.is_legal_transition(state, "queued"))


class TestApplyAndReplay(ProjectionCase):
    def test_happy_path_reaches_succeeded(self):
        outcome = self.run_demo()
        row = self.runtime.connection.execute(
            "SELECT state, terminal, result_hash FROM tasks WHERE task_id = ?",
            (outcome.task_id,)).fetchone()
        self.assertEqual(row["state"], "succeeded")
        self.assertEqual(row["terminal"], 1)
        self.assertTrue(row["result_hash"])

    def test_apply_is_idempotent_under_replay(self):
        outcome = self.run_demo()
        before = self.runtime.connection.execute(
            "SELECT COUNT(*) FROM event_index").fetchone()[0]
        result = projection.replay(self.runtime.connection, self.runtime.log,
                                   from_log_sequence=0)
        after = self.runtime.connection.execute(
            "SELECT COUNT(*) FROM event_index").fetchone()[0]
        self.assertEqual(before, after)
        self.assertEqual(result["applied"], 0)
        row = self.runtime.connection.execute(
            "SELECT state FROM tasks WHERE task_id = ?", (outcome.task_id,)).fetchone()
        self.assertEqual(row["state"], "succeeded")

    def test_replay_from_zero_changes_nothing_repeatedly(self):
        self.run_demo()
        snapshot = self._snapshot()
        for _ in range(3):
            projection.replay(self.runtime.connection, self.runtime.log,
                              from_log_sequence=0)
        self.assertEqual(self._snapshot(), snapshot)

    def _snapshot(self):
        return {
            "events": self.runtime.connection.execute(
                "SELECT log_sequence, event_id FROM event_index "
                "ORDER BY log_sequence").fetchall(),
            "tasks": self.runtime.connection.execute(
                "SELECT task_id, state, terminal, last_log_sequence FROM tasks "
                "ORDER BY task_id").fetchall(),
        }

    def test_cursor_advances_with_the_log(self):
        self.run_demo()
        cursor_sequence, cursor_offset, event_id = projection.cursor_position(
            self.runtime.connection)
        highest = self.runtime.connection.execute(
            "SELECT MAX(log_sequence) FROM event_index").fetchone()[0]
        self.assertEqual(cursor_sequence, highest)
        self.assertEqual(cursor_offset, self.runtime.log.size_bytes())
        self.assertTrue(event_id)


class TestGuardedTransition(ProjectionCase):
    def test_illegal_transition_fails_without_mutation(self):
        outcome = self.run_demo()
        task_id = outcome.task_id
        before = self.runtime.connection.execute(
            "SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        with self.assertRaises(runtime_errors.IllegalTaskTransitionError):
            task_states.assert_legal_transition("succeeded", "running")
        after = self.runtime.connection.execute(
            "SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        self.assertEqual(dict(before), dict(after))

    def test_terminal_task_records_an_anomaly_and_does_not_transition(self):
        outcome = self.run_demo()
        task_id = outcome.task_id
        row = self.runtime.connection.execute(
            "SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        # Emit a late TaskStarted against the now-terminal task.
        self.runtime._emit(
            "TaskStarted", row["workflow_id"], row["correlation_id"], task_id,
            {"capabilityId": row["capability_id"]}, task_id=task_id)
        after = self.runtime.connection.execute(
            "SELECT state, terminal FROM tasks WHERE task_id = ?",
            (task_id,)).fetchone()
        self.assertEqual(after["state"], "succeeded")
        self.assertEqual(after["terminal"], 1)
        anomalies = self.runtime.connection.execute(
            "SELECT * FROM transition_anomalies").fetchall()
        self.assertEqual(len(anomalies), 1)
        self.assertEqual(anomalies[0]["task_id"], task_id)

    def test_late_event_is_still_recorded_in_the_log(self):
        outcome = self.run_demo()
        before = len(self.runtime.log.scan().records)
        row = self.runtime.connection.execute(
            "SELECT * FROM tasks WHERE task_id = ?", (outcome.task_id,)).fetchone()
        self.runtime._emit("TaskStarted", row["workflow_id"], row["correlation_id"],
                           outcome.task_id, {"capabilityId": row["capability_id"]},
                           task_id=outcome.task_id)
        # The event is a real fact and is kept; only its APPLICATION is refused.
        self.assertEqual(len(self.runtime.log.scan().records), before + 1)


class TestTerminalGuardDirectly(ProjectionCase):
    """The terminal check is defence in depth, and needs direct exercise.

    No from_state in the current transition table is a terminal state, so an
    ordinary late event is rejected by the from_state comparison before the
    terminal check is reached. That makes the terminal guard unreachable through
    normal traffic -- and therefore untested by it, as a mutation run proved.
    These tests call apply_transition() directly with from_state=None, which is
    the only shape that reaches the guard.
    """

    def test_from_state_none_on_a_terminal_task_records_an_anomaly(self):
        outcome = self.run_demo()
        records = self.runtime.log.scan().records
        last = records[-1]
        before = self.runtime.connection.execute(
            "SELECT state, terminal, last_log_sequence FROM tasks WHERE task_id = ?",
            (outcome.task_id,)).fetchone()

        class _Probe(object):
            log_sequence = last.log_sequence + 500
            byte_offset = 0
            byte_length = 0
            event = dict(last.event)
            event_id = "probe"

        _Probe.event["taskId"] = outcome.task_id
        with store.immediate_transaction(self.runtime.connection):
            result = projection.apply_transition(
                self.runtime.connection, _Probe, None, "queued")

        self.assertEqual(result.status, projection.ANOMALY)
        after = self.runtime.connection.execute(
            "SELECT state, terminal, last_log_sequence FROM tasks WHERE task_id = ?",
            (outcome.task_id,)).fetchone()
        self.assertEqual(dict(before), dict(after))     # nothing mutated
        anomalies = self.runtime.connection.execute(
            "SELECT * FROM transition_anomalies").fetchall()
        self.assertEqual(len(anomalies), 1)

    def test_terminal_states_are_exactly_the_catalog_four(self):
        self.assertEqual(sorted(projection.TERMINAL_FLAG),
                         ["cancelled", "dead_lettered", "succeeded", "suppressed"])


class TestIndexLogDivergenceIsDetected(ProjectionCase):
    """The invariant that makes the write order matter, tested directly.

    The log is written and fsynced BEFORE the index transaction, so the index
    may lag the log but must never lead it. An index entry with no log line
    would mean a state change was committed without a durable event -- the one
    failure the write order exists to prevent. This proves the detector fires.
    """

    def test_an_index_entry_with_no_log_line_is_reported_fatal(self):
        from mogo_platform.runtime import audit as audit_module
        self.run_demo()
        self.assertEqual(audit_module.verify_integrity(
            self.runtime.connection, self.runtime.log), [])

        self.runtime.connection.execute(
            "INSERT INTO event_index (log_sequence, event_id, event_type,"
            " event_version, workflow_id, task_id, correlation_id, causation_id,"
            " producer, occurred_at, recorded_at, sequence, payload_hash,"
            " byte_offset, byte_length) VALUES (9999,'ghost','TaskSucceeded',1,"
            "'w',NULL,'c','c','orchestrator','t','t',99,'h',0,0)")

        findings = audit_module.verify_integrity(
            self.runtime.connection, self.runtime.log)
        self.assertTrue(findings)
        self.assertEqual(findings[0]["severity"], "FATAL")
        self.assertIn("indexed but absent from the log", findings[0]["finding"])


class TestRebuildProvesTheLogIsAuthoritative(ProjectionCase):
    def test_rebuild_from_log_reproduces_the_database(self):
        outcome = self.run_demo()
        before_events = self.runtime.connection.execute(
            "SELECT log_sequence, event_id, event_type, workflow_id, task_id, "
            "sequence, payload_hash FROM event_index ORDER BY log_sequence").fetchall()
        before_tasks = self.runtime.connection.execute(
            "SELECT task_id, state, terminal, result_hash FROM tasks "
            "ORDER BY task_id").fetchall()

        projection.rebuild(self.runtime.connection, self.runtime.log,
                           self.paths.root)

        after_events = self.runtime.connection.execute(
            "SELECT log_sequence, event_id, event_type, workflow_id, task_id, "
            "sequence, payload_hash FROM event_index ORDER BY log_sequence").fetchall()
        after_tasks = self.runtime.connection.execute(
            "SELECT task_id, state, terminal, result_hash FROM tasks "
            "ORDER BY task_id").fetchall()

        self.assertEqual([tuple(r) for r in before_events],
                         [tuple(r) for r in after_events])
        self.assertEqual([tuple(r) for r in before_tasks],
                         [tuple(r) for r in after_tasks])
        self.assertEqual(outcome.status, "accepted")

    def test_rebuild_restores_the_append_only_triggers(self):
        import sqlite3
        self.run_demo()
        projection.rebuild(self.runtime.connection, self.runtime.log, self.paths.root)
        with self.assertRaises(sqlite3.IntegrityError):
            self.runtime.connection.execute("DELETE FROM event_index")

    def test_rebuild_does_not_touch_the_log(self):
        self.run_demo()
        with open(self.runtime.log.path, "rb") as handle:
            before = handle.read()
        projection.rebuild(self.runtime.connection, self.runtime.log, self.paths.root)
        with open(self.runtime.log.path, "rb") as handle:
            self.assertEqual(handle.read(), before)


class TestAtomicity(ProjectionCase):
    def test_event_and_task_write_commit_together(self):
        outcome = self.run_demo()
        indexed = self.runtime.connection.execute(
            "SELECT COUNT(*) FROM event_index WHERE task_id = ?",
            (outcome.task_id,)).fetchone()[0]
        self.assertGreater(indexed, 0)
        task = self.runtime.connection.execute(
            "SELECT last_log_sequence FROM tasks WHERE task_id = ?",
            (outcome.task_id,)).fetchone()
        highest = self.runtime.connection.execute(
            "SELECT MAX(log_sequence) FROM event_index WHERE task_id = ?",
            (outcome.task_id,)).fetchone()[0]
        self.assertEqual(task["last_log_sequence"], highest)

    def test_a_failing_transaction_leaves_no_partial_state(self):
        connection = self.runtime.connection
        before = connection.execute("SELECT COUNT(*) FROM recovery_actions").fetchone()[0]
        try:
            with store.immediate_transaction(connection):
                connection.execute(
                    "INSERT INTO recovery_actions (detected_at, action, subject, "
                    "detail) VALUES ('t','a','s','d')")
                raise ValueError("induced")
        except ValueError:
            pass
        after = connection.execute("SELECT COUNT(*) FROM recovery_actions").fetchone()[0]
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main(verbosity=2)

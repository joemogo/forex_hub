#!/usr/bin/env python3
"""MOGO-011 Step 2 -- dead-letter: exhaustion, absorption, history, replay.

Pure stdlib (unittest). Fully offline, deterministic, repeatable. Tempfile
state root.

THE GAP THIS CLOSES
    Step 1 stopped a failing task at `failed`, which is NOT terminal --
    Constitution section 6.5 requires every task to reach a VISIBLE terminal
    outcome. Every test here exists to prove that no failure path can leave a
    task stranded, whichever of the thirteen error classifications it carries.

THE HISTORY IS CHECKED, NOT TRUSTED
    TaskDeadLettered carries a self-contained attempt history so that one event
    answers "what failed, how often, why, and under which lease". A
    self-contained summary is a SECOND COPY of a fact, and a second copy that
    is never compared is a place for drift to hide -- so
    test_dead_letter_history_matches_the_history_re_derived_from_the_log
    rebuilds it independently from TaskFailed events and asserts equality.

Run with:
    python3 -m unittest tests.platform.test_runtime_dead_letter -v
"""

import json
import os
import sys
import tempfile
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC_DIR = os.path.join(REPO_ROOT, "platform", "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from mogo_platform.contracts import errors as contract_errors  # noqa: E402
from mogo_platform.contracts import task_states  # noqa: E402
from mogo_platform.runtime import clock as clock_module  # noqa: E402
from mogo_platform.runtime import cli as cli_module  # noqa: E402
from mogo_platform.runtime import orchestrator as orchestrator_module  # noqa: E402
from mogo_platform.runtime import paths as paths_module  # noqa: E402
from mogo_platform.runtime import projection  # noqa: E402
from mogo_platform.runtime import retry  # noqa: E402
from mogo_platform.runtime import store  # noqa: E402

EXPECTED_DEAD_LETTER_REASONS = (
    "attempts_exhausted", "non_retryable_error_class",
    "policy_denial_never_retried", "requires_review_no_gate",
    "unknown_error_class",
)


class DeadLetterCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.paths = paths_module.RuntimePaths(os.path.join(self._tmp.name, "state"))
        self.clock = clock_module.ManualClock("2026-08-08T12:00:00.000Z")
        self.runtime = orchestrator_module.Orchestrator(
            paths=self.paths, clock=self.clock).open()
        self.runtime.register_builtin_capabilities()

    def tearDown(self):
        self.runtime.close()
        self._tmp.cleanup()

    def submit(self, fail_until, note, attempt_limit=None):
        envelope, payload = cli_module.build_retry_demo_command(fail_until, note)
        if attempt_limit is not None:
            envelope["attemptLimit"] = attempt_limit
        return self.runtime.submit(envelope, payload)

    def task(self, task_id):
        return self.runtime.connection.execute(
            "SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()

    def records_for(self, task_id, event_type=None):
        return [record for record in self.runtime.log.scan(verify=True).records
                if record.event.get("taskId") == task_id
                and (event_type is None
                     or record.event["eventType"] == event_type)]

    def drive_with_error_class(self, error_class, attempt_limit=3):
        """Drive one task to failure carrying a chosen Catalog section K class.

        The class is injected at the WORKER boundary, which is the only place a
        class can legitimately enter, so the orchestrator's decision path is
        exercised exactly as it would be in production.
        """
        from mogo_platform.runtime import worker as worker_module
        outcome = self.submit(0, "class-%s" % (error_class,),
                              attempt_limit=attempt_limit)
        original = worker_module.execute_task

        def failing(*_args, **_kwargs):
            return worker_module.WorkerResult(
                False, error_class=error_class,
                error_message="injected %s" % (error_class,))

        worker_module.execute_task = failing
        try:
            self.runtime.run_once()
        finally:
            worker_module.execute_task = original
        return outcome.task_id


class TestExhaustion(DeadLetterCase):
    def test_an_exhausted_retryable_task_becomes_dead_lettered(self):
        task_id = self.submit(9, "exhaust").task_id
        self.runtime.run_once()
        row = self.task(task_id)
        self.assertEqual(row["state"], "dead_lettered")
        self.assertEqual(row["terminal"], 1)
        self.assertEqual(row["attempt"], 3)
        self.assertEqual(row["attempt_limit"], 3)
        self.assertEqual(row["dead_letter_reason"], "attempts_exhausted")

    def test_an_attempt_limit_of_one_dead_letters_with_no_retry_at_all(self):
        task_id = self.submit(9, "single", attempt_limit=1).task_id
        self.runtime.run_once()
        row = self.task(task_id)
        self.assertEqual(row["state"], "dead_lettered")
        self.assertEqual(row["attempt"], 1)
        types = [r.event["eventType"] for r in self.records_for(task_id)]
        self.assertNotIn("TaskRetryScheduled", types)
        self.assertNotIn("TaskRetryReleased", types)

    def test_the_dead_letter_transition_is_event_backed(self):
        task_id = self.submit(9, "event-backed").task_id
        self.runtime.run_once()
        events = self.records_for(task_id, "TaskDeadLettered")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event["executionResult"], "failure")
        self.assertEqual(events[0].event["errorClass"], "transient")
        self.assertEqual(events[0].event["producer"], "orchestrator")

    def test_the_dead_letter_event_is_self_contained(self):
        task_id = self.submit(9, "self-contained").task_id
        self.runtime.run_once()
        payload = self.records_for(task_id, "TaskDeadLettered")[0].event["payload"]
        for field in ("reason", "finalErrorClass", "attempts", "attemptLimit",
                      "capabilityId", "reviewGateRequired", "attemptHistory"):
            self.assertIn(field, payload)
        self.assertEqual(payload["attempts"], 3)
        self.assertEqual(len(payload["attemptHistory"]), 3)
        self.assertFalse(payload["reviewGateRequired"])

    def test_the_dead_letter_audit_contains_all_attempts_and_causes(self):
        task_id = self.submit(9, "audit-history").task_id
        self.runtime.run_once()
        rows = self.runtime.connection.execute(
            "SELECT attempt, lease_generation, outcome, error_class "
            "FROM task_attempts WHERE task_id = ? ORDER BY attempt",
            (task_id,)).fetchall()
        self.assertEqual([r["attempt"] for r in rows], [1, 2, 3])
        self.assertEqual([r["lease_generation"] for r in rows], [1, 2, 3])
        self.assertEqual({r["outcome"] for r in rows}, {"failed"})
        self.assertEqual({r["error_class"] for r in rows}, {"transient"})

    def test_dead_letter_history_matches_the_history_re_derived_from_the_log(self):
        """The payload is a second copy. Copies get compared, or they drift."""
        task_id = self.submit(9, "compare-history").task_id
        self.runtime.run_once()
        claimed = self.records_for(task_id, "TaskDeadLettered")[0]
        payload_history = claimed.event["payload"]["attemptHistory"]

        derived = []
        for record in self.records_for(task_id, "TaskFailed"):
            derived.append({
                "attempt": record.event["payload"]["attempt"],
                "errorClass": record.event["errorClass"],
                "failedAtUtc": record.event["recordedAt"],
                "logSequence": record.log_sequence,
                "leaseGeneration": record.event["payload"]["leaseGeneration"],
            })
        self.assertEqual(payload_history, derived)

    def test_a_workflow_failed_event_accompanies_only_the_dead_letter(self):
        """A workflow that failed and then succeeded has NOT failed.

        Step 1 emitted WorkflowFailed on every TaskFailed, which would mark a
        successfully retried workflow as failed. The event now accompanies the
        terminal outcome only.
        """
        retried = self.submit(1, "retried-then-succeeded").task_id
        exhausted = self.submit(9, "exhausted").task_id
        self.runtime.run_once()
        self.assertEqual(self.task(retried)["state"], "succeeded")
        self.assertEqual(self.task(exhausted)["state"], "dead_lettered")
        workflow_failures = [
            r.event for r in self.runtime.log.scan().records
            if r.event["eventType"] == "WorkflowFailed"]
        self.assertEqual(len(workflow_failures), 1)
        self.assertEqual(workflow_failures[0]["payload"]["deadLetterReason"],
                         "attempts_exhausted")


class TestEveryClassificationReachesATerminalState(DeadLetterCase):
    def test_the_five_dead_letter_reasons_are_each_reachable(self):
        """All five, and none unreachable.

        Four are reachable end to end through a real task. The fifth,
        `unknown_error_class`, is reachable only from a corrupted index --
        because the committed event contract will not let an unknown class into
        the log in the first place -- and is exercised separately by
        test_an_unknown_class_reaching_the_index_is_still_not_retried.
        """
        self.assertEqual(tuple(retry.DEAD_LETTER_REASONS),
                         EXPECTED_DEAD_LETTER_REASONS)
        reachable = set()
        for name in list(contract_errors.ERROR_CLASS_NAMES) + ["invented_class"]:
            reachable.add(retry.dead_letter_reason(name, 99, 3))
        reachable.add(retry.dead_letter_reason("transient", 3, 3))
        reachable.discard(None)
        self.assertEqual(reachable, set(EXPECTED_DEAD_LETTER_REASONS))

    def test_every_error_class_reaches_the_expected_terminal_state(self):
        """Thirteen cases, no gaps: the twelve Catalog section K classes plus
        an invented one, each driven to a real terminal outcome."""
        expected = {
            "transient": "attempts_exhausted",
            "rate_limited": "attempts_exhausted",
            "dependency_unavailable": "attempts_exhausted",
            "authentication": "non_retryable_error_class",
            "policy_blocked": "policy_denial_never_retried",
            "not_found": "non_retryable_error_class",
            "validation": "non_retryable_error_class",
            "deterministic_processing": "non_retryable_error_class",
            "corrupted_input": "non_retryable_error_class",
            "permanent": "non_retryable_error_class",
            "source_mutated": "requires_review_no_gate",
            "human_review_required": "requires_review_no_gate",
            # An unknown class cannot be RECORDED -- the committed event
            # contract restricts errorClass to Catalog section K -- so the
            # runtime normalizes it fail-closed to the non-retryable class and
            # records the substitution. See the two tests below.
            "invented_class": "non_retryable_error_class",
        }
        self.assertEqual(len(expected), 13)
        for error_class, reason in expected.items():
            with self.subTest(error_class=error_class):
                task_id = self.drive_with_error_class(error_class)
                row = self.task(task_id)
                self.assertEqual(row["state"], "dead_lettered")
                self.assertEqual(row["terminal"], 1)
                self.assertEqual(row["dead_letter_reason"], reason)

    def test_an_unknown_error_class_cannot_enter_the_log_at_all(self):
        """The committed contract makes it structurally impossible.

        `validate_event` restricts errorClass to the Catalog section K
        vocabulary, so an unknown class could not be appended even if the
        runtime tried. The runtime therefore normalizes it BEFORE the append,
        to the non-retryable class, and records the substitution as a
        capability violation rather than discarding the fact.
        """
        task_id = self.drive_with_error_class("invented_class")
        row = self.task(task_id)
        self.assertEqual(row["error_class"], "deterministic_processing")
        self.assertEqual(row["state"], "dead_lettered")
        violation = self.runtime.connection.execute(
            "SELECT violation, detail FROM capability_violations "
            "WHERE task_id = ? ORDER BY violation_id DESC LIMIT 1",
            (task_id,)).fetchone()
        self.assertIsNotNone(violation)
        self.assertIn("invented_class", violation["detail"])
        for record in self.records_for(task_id):
            error_class = record.event.get("errorClass")
            if error_class is not None:
                self.assertIn(error_class, contract_errors.ERROR_CLASS_NAMES)

    def test_an_unknown_class_reaching_the_index_is_still_not_retried(self):
        """The remaining path to `unknown_error_class`, exercised directly.

        A class can only reach `tasks.error_class` unrecognised through
        corruption of the derived index, since the log cannot carry one. The
        decision must still fail closed: dead-letter, never retry.
        """
        self.assertFalse(retry.classify_failure("wat", 1, 3).retry)
        self.assertEqual(retry.dead_letter_reason("wat", 1, 3),
                         "unknown_error_class")

        task_id = self.submit(9, "corrupt-index", attempt_limit=3).task_id
        self.runtime.run_once()          # drives it to dead_lettered normally
        # Rewind the index to `failed` carrying a class the Catalog does not
        # know, then let the runtime decide what to do with it.
        with self.runtime.connection:
            self.runtime.connection.execute(
                "UPDATE tasks SET state = 'failed', terminal = 0, "
                "error_class = 'wat', dead_letter_reason = NULL "
                "WHERE task_id = ?", (task_id,))
        self.runtime.run_once()
        row = self.task(task_id)
        self.assertEqual(row["state"], "dead_lettered")
        self.assertEqual(row["dead_letter_reason"], "unknown_error_class")

    def test_no_failure_path_leaves_a_task_in_a_non_terminal_state(self):
        """Constitution section 6.5, asserted over every classification."""
        for error_class in list(contract_errors.ERROR_CLASS_NAMES) + ["nonsense"]:
            with self.subTest(error_class=error_class):
                task_id = self.drive_with_error_class(error_class)
                state = self.task(task_id)["state"]
                self.assertIn(state, task_states.TERMINAL_STATES)

    def test_a_review_routing_failure_records_that_a_gate_was_required(self):
        for error_class in ("source_mutated", "human_review_required"):
            with self.subTest(error_class=error_class):
                task_id = self.drive_with_error_class(error_class)
                payload = self.records_for(
                    task_id, "TaskDeadLettered")[0].event["payload"]
                self.assertTrue(payload["reviewGateRequired"])
                self.assertEqual(payload["reason"], "requires_review_no_gate")


class TestTerminalAbsorption(DeadLetterCase):
    def test_no_transition_out_of_dead_lettered_is_legal(self):
        self.assertEqual(task_states.legal_successors("dead_lettered"), ())
        self.assertIn("dead_lettered", task_states.TERMINAL_STATES)

    def test_a_dead_lettered_task_is_never_dispatched_again(self):
        task_id = self.submit(9, "never-again").task_id
        self.runtime.run_once()
        before = self.runtime.connection.execute(
            "SELECT COUNT(*) FROM task_attempts WHERE task_id = ?",
            (task_id,)).fetchone()[0]
        size_before = self.runtime.log.size_bytes()

        report = self.runtime.run_once()

        after = self.runtime.connection.execute(
            "SELECT COUNT(*) FROM task_attempts WHERE task_id = ?",
            (task_id,)).fetchone()[0]
        self.assertEqual(after, before)
        self.assertEqual(self.runtime.log.size_bytes(), size_before)
        self.assertNotIn(task_id, report["advanced"])

    def test_a_late_success_after_dead_letter_is_an_anomaly_not_applied(self):
        task_id = self.submit(9, "late-success").task_id
        self.runtime.run_once()
        row = self.task(task_id)
        self.assertEqual(row["state"], "dead_lettered")

        # A late TaskSucceeded arrives for the already-terminal task.
        self.runtime._emit(
            "TaskSucceeded", row["workflow_id"], row["correlation_id"], task_id,
            {"resultHash": "a" * 64, "byteLength": 1,
             "capabilityId": row["capability_id"], "capabilityVersion": "1.0.0"},
            task_id=task_id, execution_result="success")

        self.assertEqual(self.task(task_id)["state"], "dead_lettered")
        self.assertIsNone(self.task(task_id)["result_hash"])
        anomalies = self.runtime.connection.execute(
            "SELECT to_state, reason FROM transition_anomalies WHERE task_id = ?",
            (task_id,)).fetchall()
        self.assertTrue(any(row["to_state"] == "succeeded" for row in anomalies))


class TestDeadLetterReplay(DeadLetterCase):
    def test_rebuild_reproduces_dead_letter_state_exactly(self):
        task_id = self.submit(9, "rebuild-me").task_id
        self.runtime.run_once()
        before = dict(self.task(task_id))

        projection.rebuild(self.runtime.connection, self.runtime.log,
                           self.runtime.paths.root)

        self.assertEqual(dict(self.task(task_id)), before)

    def test_rebuild_reproduces_every_step_2_column_exactly(self):
        """Whole-row equality, not a spot check.

        If any column were computed from a clock at projection time rather than
        copied from a payload, this test fails -- which is exactly why it
        compares every column of every row rather than the ones under
        suspicion.
        """
        self.submit(1, "succeeds-after-retry")
        self.submit(9, "exhausts")
        self.runtime.run_once()

        def snapshot():
            return {
                "tasks": [dict(r) for r in self.runtime.connection.execute(
                    "SELECT * FROM tasks ORDER BY created_log_sequence")],
                "commands": [dict(r) for r in self.runtime.connection.execute(
                    "SELECT * FROM commands ORDER BY accepted_log_sequence")],
                "attempts": [
                    {k: r[k] for k in r.keys() if k != "attempt_id"}
                    for r in self.runtime.connection.execute(
                        "SELECT * FROM task_attempts ORDER BY task_id, attempt")],
            }

        before = snapshot()
        self.assertTrue(before["attempts"])

        # Advance the clock by a year before rebuilding. A value derived at
        # projection time would change; a value copied from a payload cannot.
        self.clock.advance_ms(365 * 24 * 60 * 60 * 1000)
        projection.rebuild(self.runtime.connection, self.runtime.log,
                           self.runtime.paths.root)

        self.assertEqual(snapshot(), before)

    def test_replay_never_re_decides_it_re_applies(self):
        """The dead-letter DECISION was made once and recorded.

        Replay must not re-run classify_failure -- if it did, a change to the
        error table would silently rewrite history.
        """
        task_id = self.submit(9, "no-re-decision").task_id
        self.runtime.run_once()
        original = retry.classify_failure
        calls = []

        def spy(*args, **kwargs):
            calls.append(args)
            return original(*args, **kwargs)

        retry.classify_failure = spy
        try:
            projection.rebuild(self.runtime.connection, self.runtime.log,
                               self.runtime.paths.root)
        finally:
            retry.classify_failure = original
        self.assertEqual(calls, [])
        self.assertEqual(self.task(task_id)["state"], "dead_lettered")

    def test_the_attempt_history_survives_a_rebuild(self):
        task_id = self.submit(9, "history-survives").task_id
        self.runtime.run_once()
        before = [dict(r) for r in self.runtime.connection.execute(
            "SELECT task_id, attempt, outcome, error_class, started_at, finished_at "
            "FROM task_attempts WHERE task_id = ? ORDER BY attempt", (task_id,))]
        projection.rebuild(self.runtime.connection, self.runtime.log,
                           self.runtime.paths.root)
        after = [dict(r) for r in self.runtime.connection.execute(
            "SELECT task_id, attempt, outcome, error_class, started_at, finished_at "
            "FROM task_attempts WHERE task_id = ? ORDER BY attempt", (task_id,))]
        self.assertEqual(after, before)
        self.assertEqual(len(after), 3)


class TestAttemptRecordingGuards(DeadLetterCase):
    def test_task_attempts_rejects_a_duplicate_attempt_number(self):
        """The schema-level second guard against a double count.

        It is independent of every assertion in the runtime: even with every
        in-process check removed, recording one attempt twice raises here.
        """
        import sqlite3
        task_id = self.submit(9, "unique-guard").task_id
        self.runtime.run_once()
        with self.assertRaises(sqlite3.IntegrityError):
            with store.immediate_transaction(self.runtime.connection):
                self.runtime.connection.execute(
                    "INSERT INTO task_attempts ("
                    " task_id, attempt, lease_generation, started_log_sequence,"
                    " finished_log_sequence, outcome, started_at, finished_at"
                    ") VALUES (?,1,1,1,2,'failed','t','t')", (task_id,))

    def test_capability_violations_is_append_only(self):
        import sqlite3
        with store.immediate_transaction(self.runtime.connection):
            self.runtime.connection.execute(
                "INSERT INTO capability_violations "
                "(detected_at, capability_id, task_id, violation, detail) "
                "VALUES ('t','CAP|research|runtime-echo',NULL,'x','y')")
        for statement in ("UPDATE capability_violations SET violation = 'z'",
                          "DELETE FROM capability_violations"):
            with self.subTest(statement=statement):
                with self.assertRaises(sqlite3.IntegrityError):
                    with store.immediate_transaction(self.runtime.connection):
                        self.runtime.connection.execute(statement)


if __name__ == "__main__":
    unittest.main(verbosity=2)

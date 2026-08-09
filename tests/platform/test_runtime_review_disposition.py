#!/usr/bin/env python3
"""MOGO-011 Step 3 -- operator disposition of a policy-blocked task.

Pure stdlib (unittest). Fully offline, deterministic, repeatable. Tempfile state
root.

WHAT THIS IS, AND WHAT IT IS NOT
    Governance decision C-1. This is NOT a review system: there is no queue, no
    assignment, no notification, no workflow. It is the ONE audited action that
    lets a human release or suppress a task the policy gate blocked.

    Without it, a denied task would sit in `awaiting_review` forever -- exactly
    the Constitution section 6.5 defect that MOGO-011 Step 2 was built to
    eliminate for failures. `TestEveryBlockedTaskCanReachATerminalOutcome` is
    the test that keeps that promise.

THE COMMITTED CONTRACT FIXES THE PATH
    `legal_successors("blocked")` is ('awaiting_review', 'cancelled'). There is
    no `blocked -> queued` and no `blocked -> suppressed` edge, so the decision
    acts on `awaiting_review` under `review_gate` authority, exactly as Catalog
    section L assigns it. Taking a shortcut would mean inventing an edge no
    decision authorizes.

Run with:
    python3 -m unittest tests.platform.test_runtime_review_disposition -v
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
from mogo_platform.contracts import task_states  # noqa: E402
from mogo_platform.runtime import clock as clock_module  # noqa: E402
from mogo_platform.runtime import cli as cli_module  # noqa: E402
from mogo_platform.runtime import errors as runtime_errors  # noqa: E402
from mogo_platform.runtime import orchestrator as orchestrator_module  # noqa: E402
from mogo_platform.runtime import paths as paths_module  # noqa: E402
from mogo_platform.runtime import projection  # noqa: E402


class DispositionCase(unittest.TestCase):
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

    def source(self, label):
        return ids.make_source_id("example", "https://example.test/%s" % label)

    def authorize(self, source_id, status, operations):
        return self.runtime.record_authorization(
            {"authorizationId": ids.new_uuid4(), "sourceId": source_id,
             "policyStatus": status, "policyVersion": "1.0",
             "decisionAuthority": "governance:mogo-legal",
             "decidedAt": "2026-08-08T11:00:00.000Z",
             "permittedOperations": list(operations)})

    def blocked_task(self, label):
        """A task the gate denied, sitting in awaiting_review."""
        source = self.source(label)
        envelope, payload = cli_module.build_policy_demo_command(source, label)
        outcome = self.runtime.submit(envelope, payload)
        self.runtime.run_once()
        row = self.task(outcome.task_id)
        self.assertEqual(row["state"], "awaiting_review")
        return outcome.task_id, source

    def task(self, task_id):
        return self.runtime.connection.execute(
            "SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()

    def events(self, task_id):
        return [row[0] for row in self.runtime.connection.execute(
            "SELECT event_type FROM event_index WHERE task_id = ? "
            "ORDER BY log_sequence", (task_id,))]


class TestTheContractFixesThePath(DispositionCase):
    def test_blocked_has_no_shortcut_to_queued_or_suppressed(self):
        self.assertEqual(task_states.legal_successors("blocked"),
                         ("awaiting_review", "cancelled"))
        self.assertFalse(task_states.is_legal_transition("blocked", "queued"))
        self.assertFalse(task_states.is_legal_transition("blocked", "suppressed"))

    def test_the_disposition_edges_belong_to_the_review_gate(self):
        for target in ("queued", "suppressed"):
            with self.subTest(target=target):
                self.assertEqual(
                    task_states.transition_authority("awaiting_review", target),
                    "review_gate")

    def test_suppressed_is_terminal(self):
        self.assertIn("suppressed", task_states.TERMINAL_STATES)
        self.assertEqual(task_states.legal_successors("suppressed"), ())


class TestDisposition(DispositionCase):
    def test_rejection_suppresses_the_task_terminally(self):
        task_id, _source = self.blocked_task("reject")
        self.runtime.record_review_decision(
            task_id, "rejected", "source terms prohibit acquisition",
            "operator:joe", policy_version="1.0")
        row = self.task(task_id)
        self.assertEqual(row["state"], "suppressed")
        self.assertEqual(row["terminal"], 1)
        self.assertEqual(row["review_decision"], "rejected")
        self.assertEqual(row["reviewer_identity"], "operator:joe")
        self.assertIn("HumanReviewCompleted", self.events(task_id))

    def test_approval_releases_the_task_and_it_then_executes(self):
        task_id, source = self.blocked_task("approve")
        # Governance supplies the authorization out of band, then releases it.
        self.authorize(source, "PERMITTED_PUBLIC_METADATA", ["metadata"])
        self.runtime.record_review_decision(
            task_id, "approved", "authorization recorded after review",
            "governance:mogo-legal")
        self.assertEqual(self.task(task_id)["state"], "queued")
        self.runtime.run_once()
        row = self.task(task_id)
        self.assertEqual(row["state"], "succeeded")
        self.assertEqual(row["terminal"], 1)

    def test_approval_is_refused_while_the_gate_still_denies(self):
        """A human may un-block a task. Only the gate may authorize the
        acquisition.

        Constitution section 5.1 admits no exception: no fetch without an
        Acquisition Authorization Record, and a reviewer is not a substitute for
        one. Releasing the task anyway would produce a task that could never
        dispatch -- approval that cannot lead to execution is not approval, it
        is a misleading state change.
        """
        task_id, _source = self.blocked_task("approve-without-authorization")
        with self.assertRaises(runtime_errors.ReviewDecisionError) as caught:
            self.runtime.record_review_decision(
                task_id, "approved", "released pending authorization",
                "operator:joe")
        self.assertIn("no_authorization_record", str(caught.exception))
        # The task did not move, and nothing was recorded as approved.
        row = self.task(task_id)
        self.assertEqual(row["state"], "awaiting_review")
        self.assertIsNone(row["review_decision"])
        self.assertNotIn("HumanReviewCompleted", self.events(task_id))

    def test_an_approval_records_the_gates_permit_not_the_reviewers_say_so(self):
        task_id, source = self.blocked_task("permit-provenance")
        self.authorize(source, "PERMITTED_PUBLIC_METADATA", ["metadata"])
        self.runtime.record_review_decision(
            task_id, "approved", "authorization recorded", "operator:joe")
        row = self.task(task_id)
        # The permit is the GATE's, with the governance authority and version.
        self.assertEqual(row["policy_decision"], "permit")
        self.assertEqual(row["policy_reason"], "authorized")
        self.assertEqual(row["policy_status"], "PERMITTED_PUBLIC_METADATA")
        self.assertEqual(row["policy_version"], "1.0")
        self.assertIsNotNone(row["authorization_id"])
        payload = [r.event["payload"] for r in self.runtime.log.scan().records
                   if r.event.get("taskId") == task_id
                   and r.event["eventType"] == "HumanReviewCompleted"][0]
        self.assertEqual(payload["decisionAuthority"], "governance:mogo-legal")
        self.assertTrue(payload["authorizationRecordHash"])

    def test_every_required_review_field_is_recorded(self):
        """Constitution section 9, field by field."""
        task_id, _source = self.blocked_task("fields")
        self.runtime.record_review_decision(
            task_id, "rejected", "not licensed for automated collection",
            "legal:external-counsel", policy_version="2.1")
        payload = [r.event["payload"] for r in self.runtime.log.scan().records
                   if r.event.get("taskId") == task_id
                   and r.event["eventType"] == "HumanReviewCompleted"][0]
        for field in ("decision", "reason", "reviewerIdentity", "decidedAtUtc",
                      "policyVersion", "reviewType", "subjectSourceId"):
            self.assertIn(field, payload)
        self.assertEqual(payload["reviewerIdentity"], "legal:external-counsel")
        self.assertEqual(payload["policyVersion"], "2.1")
        self.assertTrue(payload["reason"].strip())

    def test_the_decision_is_produced_by_the_review_gate(self):
        task_id, _source = self.blocked_task("producer")
        self.runtime.record_review_decision(task_id, "rejected", "no", "operator:joe")
        producer = [r.event["producer"] for r in self.runtime.log.scan().records
                    if r.event.get("taskId") == task_id
                    and r.event["eventType"] == "HumanReviewCompleted"][0]
        self.assertEqual(producer, "reviewGate")


class TestDispositionIsRefusedWhenInvalid(DispositionCase):
    def test_a_bare_REJECTION_is_refused(self):
        """Constitution section 9: a decision without a reason is invalid.

        REJECTION is the decisive case, and it is tested first. A rejection
        does not re-evaluate the policy gate, so the reason requirement is the
        ONLY thing that can refuse it -- which makes this test prove the reason
        check on its own rather than borrowing another guard's refusal.

        (Found by the mutation protocol: an earlier version of this suite tested
        only bare APPROVAL, which the gate re-evaluation refused anyway. The
        test passed for the wrong reason and a removed reason check survived.)
        """
        task_id, _source = self.blocked_task("bare-reject")
        for reason in ("", "   ", None, 17):
            with self.subTest(reason=reason):
                with self.assertRaises(runtime_errors.ReviewDecisionError) as caught:
                    self.runtime.record_review_decision(
                        task_id, "rejected", reason, "operator:joe")
                self.assertIn("reason", str(caught.exception))
        row = self.task(task_id)
        self.assertEqual(row["state"], "awaiting_review")
        self.assertIsNone(row["review_decision"])
        self.assertNotIn("HumanReviewCompleted", self.events(task_id))

    def test_a_bare_approval_is_refused_even_when_the_gate_would_permit(self):
        """The reason requirement is independent of the gate's answer.

        The authorization is recorded first, so the gate WOULD permit. The only
        thing that can refuse is the missing reason.
        """
        task_id, source = self.blocked_task("bare-approve")
        self.authorize(source, "PERMITTED_PUBLIC_METADATA", ["metadata"])
        for reason in ("", "   ", None, 17):
            with self.subTest(reason=reason):
                with self.assertRaises(runtime_errors.ReviewDecisionError) as caught:
                    self.runtime.record_review_decision(
                        task_id, "approved", reason, "operator:joe")
                self.assertIn("reason", str(caught.exception))
        self.assertEqual(self.task(task_id)["state"], "awaiting_review")
        # And with a reason, the same call succeeds -- so the refusal above was
        # the reason check and nothing else.
        self.runtime.record_review_decision(
            task_id, "approved", "authorization recorded", "operator:joe")
        self.assertEqual(self.task(task_id)["state"], "queued")

    def test_a_worker_may_not_approve_its_own_governed_output(self):
        task_id, _source = self.blocked_task("self-approval")
        for reviewer in ("worker:CAP|research|policy-probe", "orchestrator",
                         "CAP|research|policy-probe", "policyGate", "reviewGate"):
            with self.subTest(reviewer=reviewer):
                with self.assertRaises(runtime_errors.ReviewDecisionError):
                    self.runtime.record_review_decision(
                        task_id, "approved", "looks fine", reviewer)
        self.assertEqual(self.task(task_id)["state"], "awaiting_review")

    def test_an_unattributable_reviewer_is_refused(self):
        task_id, _source = self.blocked_task("unattributable")
        for reviewer in ("joe", "", "   ", None):
            with self.subTest(reviewer=reviewer):
                with self.assertRaises(runtime_errors.ReviewDecisionError):
                    self.runtime.record_review_decision(
                        task_id, "approved", "fine", reviewer)

    def test_an_unrecognised_decision_is_refused(self):
        task_id, _source = self.blocked_task("bad-decision")
        for decision in ("maybe", "deferred", "escalated", "", None):
            with self.subTest(decision=decision):
                with self.assertRaises(runtime_errors.ReviewDecisionError):
                    self.runtime.record_review_decision(
                        task_id, decision, "reason", "operator:joe")

    def test_a_task_not_awaiting_review_cannot_be_disposed_of(self):
        envelope, payload = cli_module.build_demo_command()
        outcome = self.runtime.submit(envelope, payload)
        self.runtime.run_once()
        self.assertEqual(self.task(outcome.task_id)["state"], "succeeded")
        with self.assertRaises(runtime_errors.ReviewDecisionError):
            self.runtime.record_review_decision(
                outcome.task_id, "approved", "already done", "operator:joe")

    def test_an_unknown_task_is_refused(self):
        with self.assertRaises(runtime_errors.ReviewDecisionError):
            self.runtime.record_review_decision(
                ids.new_uuid4(), "approved", "reason", "operator:joe")

    def test_a_task_cannot_be_disposed_of_twice(self):
        task_id, _source = self.blocked_task("twice")
        self.runtime.record_review_decision(task_id, "rejected", "no", "operator:joe")
        with self.assertRaises(runtime_errors.ReviewDecisionError):
            self.runtime.record_review_decision(
                task_id, "approved", "changed my mind", "operator:joe")
        self.assertEqual(self.task(task_id)["state"], "suppressed")


class TestEveryBlockedTaskCanReachATerminalOutcome(DispositionCase):
    """Constitution section 6.5, for the policy path.

    Step 2 eliminated the stranding defect for failures. Step 3 must not
    reintroduce it for denials.
    """

    def test_a_denied_task_is_not_left_without_a_route_out(self):
        task_id, _source = self.blocked_task("route-out")
        row = self.task(task_id)
        self.assertEqual(row["state"], "awaiting_review")
        self.assertEqual(row["terminal"], 0)
        # A route out exists, and it is a legal one under an approved authority.
        successors = task_states.legal_successors(row["state"])
        self.assertIn("suppressed", successors)
        self.assertIn("queued", successors)

    def test_rejection_reaches_a_terminal_state(self):
        task_id, _source = self.blocked_task("terminal-reject")
        self.runtime.record_review_decision(task_id, "rejected", "denied",
                                            "governance:mogo-legal")
        self.assertIn(self.task(task_id)["state"], task_states.TERMINAL_STATES)

    def test_a_suppressed_task_remains_visible_and_queryable(self):
        """Constitution section 9 and Architecture section 22: rejected and
        suppressed items are never deleted and never hidden."""
        task_id, _source = self.blocked_task("visible")
        self.runtime.record_review_decision(
            task_id, "rejected", "prohibited by source terms", "operator:joe")
        from mogo_platform.runtime import audit as audit_module
        report = audit_module.policy_report(self.runtime.connection,
                                            self.runtime.log)
        disposed = {entry["taskId"] for entry in report["disposedTasks"]}
        self.assertIn(task_id, disposed)
        rendered = audit_module.render_policy(report)
        self.assertIn(task_id, rendered)
        self.assertIn("prohibited by source terms", rendered)


class TestDispositionReplay(DispositionCase):
    def test_rebuild_reproduces_the_disposition_exactly(self):
        rejected, _s1 = self.blocked_task("replay-reject")
        self.runtime.record_review_decision(rejected, "rejected", "no",
                                            "operator:joe")
        approved, source = self.blocked_task("replay-approve")
        self.authorize(source, "PERMITTED_PUBLIC_METADATA", ["metadata"])
        self.runtime.record_review_decision(approved, "approved", "authorized",
                                            "governance:mogo-legal")
        self.runtime.run_once()

        before = [dict(r) for r in self.runtime.connection.execute(
            "SELECT * FROM tasks ORDER BY created_log_sequence")]
        self.clock.advance_ms(365 * 24 * 60 * 60 * 1000)
        projection.rebuild(self.runtime.connection, self.runtime.log,
                           self.runtime.paths.root)
        after = [dict(r) for r in self.runtime.connection.execute(
            "SELECT * FROM tasks ORDER BY created_log_sequence")]
        self.assertEqual(after, before)

    def test_an_unreadable_review_decision_suppresses_rather_than_releases(self):
        """A decision this build cannot interpret must not release a task.

        Releasing to `queued` on an unreadable record would let an unreadable
        review authorize execution.
        """

        class _Record(object):
            event = {"payload": {"decision": "something_new"}}

        self.assertEqual(projection._review_target(_Record()), "suppressed")


if __name__ == "__main__":
    unittest.main(verbosity=2)

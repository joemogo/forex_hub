#!/usr/bin/env python3
"""MOGO-011 Step 3 -- the policy gate: the authorization decision.

Pure stdlib (unittest). Fully offline, deterministic, repeatable. Tempfile state
root. Nothing sleeps; expiry is reached by advancing an injected clock.

THE TWO THINGS THIS SUITE EXISTS TO PROVE

  1. NOTHING ACQUIRES WITHOUT AUTHORIZATION, and the gate cannot be bypassed.
     Constitution section 5.1 makes authorization a PRECONDITION, and section
     5.5 forbids bypass "by configuration, flag, argument, or code path".

  2. THE AUDIT TRAIL IS TRUE. Before Step 3 an acquisition-class task recorded
     `decision: "not_applicable"` -- the opposite of what happened -- with a
     null operation class, and then emitted TaskClaimed and TaskStarted for an
     execution that never occurred. The outcome was fail-closed; the record was
     a fabrication. `TestTheAuditTrailIsTrue` is the regression that keeps it
     from coming back.

Run with:
    python3 -m unittest tests.platform.test_runtime_policy_gate -v
"""

import ast
import json
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
from mogo_platform.contracts import vocabulary  # noqa: E402
from mogo_platform.runtime import authorizations  # noqa: E402
from mogo_platform.runtime import clock as clock_module  # noqa: E402
from mogo_platform.runtime import cli as cli_module  # noqa: E402
from mogo_platform.runtime import errors as runtime_errors  # noqa: E402
from mogo_platform.runtime import orchestrator as orchestrator_module  # noqa: E402
from mogo_platform.runtime import paths as paths_module  # noqa: E402
from mogo_platform.runtime import policy  # noqa: E402
from mogo_platform.runtime import projection  # noqa: E402

# Independently transcribed from Catalog section M -- NOT imported from the
# implementation. (metadata, transcript, artifact, permitsAcquisition).
CATALOG_SECTION_M = {
    "PERMITTED_PUBLIC_METADATA":   ("ALLOWED", "DENIED", "DENIED", True),
    "PERMITTED_PUBLIC_TRANSCRIPT": ("ALLOWED", "ALLOWED", "DENIED", True),
    "PERMITTED_PUBLIC_ARTIFACT":   ("ALLOWED", "ALLOWED", "ALLOWED", True),
    "PERMITTED_EXPLICIT_LICENSE":  ("AS_RECORDED", "AS_RECORDED", "AS_RECORDED", True),
    "PERMITTED_DOCUMENTED_POLICY": ("AS_RECORDED", "AS_RECORDED", "AS_RECORDED", True),
    "METADATA_ONLY":               ("ALLOWED", "DENIED", "DENIED", True),
    "LINK_ONLY":                   ("LOCATOR_ONLY", "DENIED", "DENIED", True),
    "HUMAN_REVIEW_REQUIRED":       ("ALREADY_GATHERED_ONLY", "DENIED", "DENIED", False),
    "AUTHENTICATION_REQUIRED":     ("DENIED", "DENIED", "DENIED", False),
    "RESTRICTED":                  ("DENIED", "DENIED", "DENIED", False),
    "PROHIBITED":                  ("DENIED", "DENIED", "DENIED", False),
    "UNKNOWN":                     ("DENIED", "DENIED", "DENIED", False),
}

# The four Catalog section F operations.
EXPECTED_OPERATIONS = ("discover", "metadata", "transcript", "artifact")

NOW = 1_800_000_000_000


def record(status, operations, **extra):
    """A minimal well-formed authorization, as the gate sees one."""
    base = {"authorizationId": "3f2504e0-4f89-41d3-9a0c-0305e82c3301",
            "sourceId": "SRC|example|0123456789ab",
            "policyStatus": status, "policyVersion": "1.0",
            "decisionAuthority": "governance:mogo-legal",
            "decidedAt": "2026-08-08T11:00:00.000Z",
            "permittedOperations": list(operations),
            "expiresAtMs": None, "supersededBy": None}
    base.update(extra)
    return base


class TestClassificationReadsOneTable(unittest.TestCase):
    def test_the_committed_table_matches_the_catalog(self):
        self.assertEqual(set(vocabulary.LICENSING_STATUSES), set(CATALOG_SECTION_M))
        for name, (meta, transcript, artifact, acquire) in CATALOG_SECTION_M.items():
            with self.subTest(status=name):
                entry = vocabulary.LICENSING_STATUSES[name]
                self.assertEqual(entry["metadata"], meta)
                self.assertEqual(entry["transcript"], transcript)
                self.assertEqual(entry["artifact"], artifact)
                self.assertEqual(entry["permitsAcquisition"], acquire)

    def test_permits_acquisition_agrees_with_the_catalog(self):
        for name, (_m, _t, _a, acquire) in CATALOG_SECTION_M.items():
            with self.subTest(status=name):
                self.assertEqual(policy.permits_acquisition(name), acquire)

    def test_an_unrecognised_status_never_permits(self):
        for bogus in ("", None, "permitted", "PERMITTED", "UNKNOWN ", 17):
            with self.subTest(status=bogus):
                self.assertFalse(policy.permits_acquisition(bogus))

    def test_no_status_name_is_hard_coded_as_a_permission(self):
        """The gate must consult the table, never restate it.

        UNKNOWN is the ONE permitted literal, because Constitution section 5.2
        states its rule in absolute terms and it therefore carries a second,
        independent guard.
        """
        import inspect
        source = inspect.getsource(policy)
        for name in CATALOG_SECTION_M:
            if name == "UNKNOWN":
                continue
            with self.subTest(status=name):
                self.assertNotIn('"%s"' % name, source)
                self.assertNotIn("'%s'" % name, source)

    def test_the_four_operations_match_the_catalog(self):
        self.assertEqual(tuple(policy.ACQUISITION_OPERATIONS), EXPECTED_OPERATIONS)


class TestUnknownIsProhibited(unittest.TestCase):
    """Constitution section 5.2, given two independent guards."""

    def test_unknown_and_prohibited_are_identical_in_the_table(self):
        self.assertEqual(dict(vocabulary.LICENSING_STATUSES["UNKNOWN"]),
                         dict(vocabulary.LICENSING_STATUSES["PROHIBITED"]))

    def test_unknown_and_prohibited_decide_identically_for_every_operation(self):
        for operation in EXPECTED_OPERATIONS:
            with self.subTest(operation=operation):
                unknown = policy.evaluate("acquisition", [operation],
                                          record("UNKNOWN", EXPECTED_OPERATIONS), NOW)
                prohibited = policy.evaluate("acquisition", [operation],
                                             record("PROHIBITED", EXPECTED_OPERATIONS),
                                             NOW)
                self.assertEqual(unknown, prohibited)
                self.assertFalse(unknown.permitted)

    def test_unknown_is_refused_even_if_the_table_says_it_permits(self):
        """Guard 2, proved independent of guard 1.

        The committed table is monkeypatched to claim UNKNOWN permits
        acquisition. The decision must STILL refuse, because UNKNOWN is checked
        before the table is consulted -- absence of a known permission is not
        permission, and one guard is not enough for a rule the Constitution
        states absolutely.
        """
        from types import MappingProxyType
        original = vocabulary.LICENSING_STATUSES
        patched = dict(original)
        patched["UNKNOWN"] = MappingProxyType(
            {"metadata": "ALLOWED", "transcript": "ALLOWED",
             "artifact": "ALLOWED", "permitsAcquisition": True})
        vocabulary.LICENSING_STATUSES = MappingProxyType(patched)
        try:
            self.assertFalse(policy.permits_acquisition("UNKNOWN"))
            decision = policy.evaluate("acquisition", ["metadata"],
                                       record("UNKNOWN", ["metadata"]), NOW)
            self.assertFalse(decision.permitted)
            self.assertEqual(decision.reason, "policy_status_denies_acquisition")
        finally:
            vocabulary.LICENSING_STATUSES = original
        self.assertIs(vocabulary.LICENSING_STATUSES, original)


class TestTheDecisionLadder(unittest.TestCase):
    def test_non_acquisition_work_is_not_applicable(self):
        decision = policy.evaluate("non_acquisition", [], None, NOW)
        self.assertTrue(decision.permitted)
        self.assertEqual(decision.decision, "not_applicable")

    def test_an_indeterminate_operation_class_is_blocked(self):
        for bogus in (None, "", "acquire", "ACQUISITION", "unknown", 3):
            with self.subTest(operation_class=bogus):
                decision = policy.evaluate(bogus, ["metadata"],
                                           record("PERMITTED_PUBLIC_ARTIFACT",
                                                  EXPECTED_OPERATIONS), NOW)
                self.assertFalse(decision.permitted)
                self.assertEqual(decision.reason, "operation_class_indeterminate")

    def test_no_authorization_record_denies(self):
        decision = policy.evaluate("acquisition", ["metadata"], None, NOW)
        self.assertFalse(decision.permitted)
        self.assertEqual(decision.reason, "no_authorization_record")

    def test_a_resolution_problem_denies_with_its_own_reason(self):
        for problem in policy.RESOLUTION_PROBLEMS:
            with self.subTest(problem=problem):
                decision = policy.evaluate("acquisition", ["metadata"], None, NOW,
                                           resolution_problem=problem)
                self.assertFalse(decision.permitted)
                self.assertEqual(decision.reason, problem)

    def test_an_unrecognised_resolution_problem_still_denies(self):
        decision = policy.evaluate("acquisition", ["metadata"], None, NOW,
                                   resolution_problem="something_new")
        self.assertFalse(decision.permitted)

    def test_an_acquisition_capability_declaring_no_operations_denies(self):
        decision = policy.evaluate("acquisition", [],
                                   record("PERMITTED_PUBLIC_ARTIFACT",
                                          EXPECTED_OPERATIONS), NOW)
        self.assertFalse(decision.permitted)
        self.assertEqual(decision.reason, "no_acquisition_operations_declared")

    def test_an_unrecognised_status_denies(self):
        decision = policy.evaluate("acquisition", ["metadata"],
                                   record("PERMITTED_MAYBE", ["metadata"]), NOW)
        self.assertFalse(decision.permitted)
        self.assertEqual(decision.reason, "unknown_policy_status")

    def test_an_expired_authorization_denies(self):
        entry = record("PERMITTED_PUBLIC_METADATA", ["metadata"],
                       expiresAtMs=NOW)
        self.assertFalse(policy.evaluate("acquisition", ["metadata"], entry,
                                         NOW).permitted)
        # One millisecond earlier it is still in force.
        self.assertTrue(policy.evaluate("acquisition", ["metadata"], entry,
                                        NOW - 1).permitted)

    def test_an_absent_expiry_does_not_expire(self):
        entry = record("PERMITTED_PUBLIC_METADATA", ["metadata"])
        self.assertTrue(policy.evaluate("acquisition", ["metadata"], entry,
                                        NOW + 10 ** 12).permitted)

    def test_a_superseded_authorization_denies(self):
        entry = record("PERMITTED_PUBLIC_METADATA", ["metadata"],
                       supersededBy="another")
        decision = policy.evaluate("acquisition", ["metadata"], entry, NOW)
        self.assertFalse(decision.permitted)
        self.assertEqual(decision.reason, "authorization_superseded")

    def test_an_operation_outside_the_record_denies(self):
        entry = record("PERMITTED_PUBLIC_ARTIFACT", ["metadata"])
        decision = policy.evaluate("acquisition", ["artifact"], entry, NOW)
        self.assertFalse(decision.permitted)
        self.assertEqual(decision.reason, "operation_not_permitted")

    def test_an_operation_the_status_denies_is_refused_even_if_granted(self):
        """The record's list and the status's column BOTH govern, and the
        narrower of the two wins. A grant cannot exceed the classification."""
        entry = record("METADATA_ONLY", ["metadata", "artifact"])
        decision = policy.evaluate("acquisition", ["artifact"], entry, NOW)
        self.assertFalse(decision.permitted)
        self.assertEqual(decision.reason, "operation_denied_by_status")

    def test_locator_only_permits_no_acquisition_operation(self):
        entry = record("LINK_ONLY", list(EXPECTED_OPERATIONS))
        for operation in EXPECTED_OPERATIONS:
            with self.subTest(operation=operation):
                self.assertFalse(policy.evaluate("acquisition", [operation],
                                                 entry, NOW).permitted)

    def test_human_review_required_permits_no_new_acquisition(self):
        entry = record("HUMAN_REVIEW_REQUIRED", list(EXPECTED_OPERATIONS))
        for operation in EXPECTED_OPERATIONS:
            with self.subTest(operation=operation):
                decision = policy.evaluate("acquisition", [operation], entry, NOW)
                self.assertFalse(decision.permitted)
                self.assertEqual(decision.reason,
                                 "policy_status_denies_acquisition")

    def test_as_recorded_is_not_an_allowance(self):
        """PERMITTED_EXPLICIT_LICENSE and PERMITTED_DOCUMENTED_POLICY mark every
        operation AS_RECORDED, which means "whatever the licence says". Treating
        it as permission would turn the two most nuanced statuses into the most
        permissive ones."""
        for status in ("PERMITTED_EXPLICIT_LICENSE", "PERMITTED_DOCUMENTED_POLICY"):
            with self.subTest(status=status):
                entry = record(status, ["metadata"])
                decision = policy.evaluate("acquisition", ["metadata"], entry, NOW)
                self.assertFalse(decision.permitted)
                self.assertEqual(decision.reason,
                                 "licence_does_not_state_operation")

    def test_as_recorded_permits_only_when_the_licence_is_referenced(self):
        entry = record("PERMITTED_EXPLICIT_LICENSE", ["metadata"],
                       sourceTermsSnapshotRef="terms/example-v3")
        self.assertTrue(policy.evaluate("acquisition", ["metadata"], entry,
                                        NOW).permitted)

    def test_discover_is_governed_exactly_as_metadata(self):
        """Architecture section 20.2: the minimum-metadata allowance expires the
        instant a classification is recorded. There is no laxer rule for
        discovery once an authorization exists -- that rule would be the
        drip-feed loophole section 20.2 closes."""
        self.assertEqual(policy.OPERATION_PERMISSION_COLUMN["discover"], "metadata")
        for status in CATALOG_SECTION_M:
            with self.subTest(status=status):
                entry = record(status, ["discover", "metadata"],
                               sourceTermsSnapshotRef="terms/x")
                discover = policy.evaluate("acquisition", ["discover"], entry, NOW)
                metadata = policy.evaluate("acquisition", ["metadata"], entry, NOW)
                self.assertEqual(discover.permitted, metadata.permitted)

    def test_a_permitted_operation_is_authorized(self):
        entry = record("PERMITTED_PUBLIC_ARTIFACT", list(EXPECTED_OPERATIONS))
        for operation in EXPECTED_OPERATIONS:
            with self.subTest(operation=operation):
                decision = policy.evaluate("acquisition", [operation], entry, NOW)
                self.assertTrue(decision.permitted)
                self.assertEqual(decision.reason, "authorized")

    def test_every_status_and_operation_pair_is_decided(self):
        """48 combinations, none undecided, none raising."""
        decided = 0
        for status in CATALOG_SECTION_M:
            for operation in EXPECTED_OPERATIONS:
                entry = record(status, list(EXPECTED_OPERATIONS))
                decision = policy.evaluate("acquisition", [operation], entry, NOW)
                self.assertIn(decision.decision, ("permit", "deny"))
                if not decision.permitted:
                    self.assertIn(decision.reason, policy.DENY_REASONS)
                decided += 1
        self.assertEqual(decided, 48)

    def test_the_decision_is_deterministic(self):
        entry = record("PERMITTED_PUBLIC_TRANSCRIPT", ["metadata", "transcript"])
        results = {policy.evaluate("acquisition", ["transcript"], entry, NOW)
                   for _ in range(1000)}
        self.assertEqual(len(results), 1)

    def test_the_policy_module_reads_no_clock_and_no_store(self):
        with open(os.path.join(SRC_DIR, "mogo_platform", "runtime", "policy.py"),
                  "r", encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = ([a.name for a in node.names]
                         if isinstance(node, ast.Import) else [node.module or ""])
                for name in names:
                    self.assertNotIn(name.split(".")[0],
                                     ("time", "datetime", "random", "secrets",
                                      "sqlite3", "os"))


class PolicyRuntimeCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.paths = paths_module.RuntimePaths(os.path.join(self._tmp.name, "state"))
        self.clock = clock_module.ManualClock("2026-08-08T12:00:00.000Z")
        self.runtime = orchestrator_module.Orchestrator(
            paths=self.paths, clock=self.clock).open()
        self.runtime.register_builtin_capabilities()
        self._counter = 0

    def tearDown(self):
        try:
            self.runtime.close()
        except Exception:  # noqa: BLE001 - a closed runtime is fine in teardown
            pass
        self._tmp.cleanup()

    def source(self, label):
        return ids.make_source_id("example", "https://example.test/%s" % label)

    def authorize(self, source_id, status, operations, **extra):
        entry = {"authorizationId": ids.new_uuid4(), "sourceId": source_id,
                 "policyStatus": status, "policyVersion": "1.0",
                 "decisionAuthority": "governance:mogo-legal",
                 "decidedAt": "2026-08-08T11:00:00.000Z",
                 "permittedOperations": list(operations)}
        entry.update(extra)
        return self.runtime.record_authorization(entry)

    def submit_acquisition(self, source_id, note=None):
        envelope, payload = cli_module.build_policy_demo_command(
            source_id, note or source_id)
        outcome = self.runtime.submit(envelope, payload)
        self.runtime.run_once()
        return outcome.task_id

    def task(self, task_id):
        return self.runtime.connection.execute(
            "SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()

    def events(self, task_id):
        return [row[0] for row in self.runtime.connection.execute(
            "SELECT event_type FROM event_index WHERE task_id = ? "
            "ORDER BY log_sequence", (task_id,))]

    def payloads(self, task_id, event_type):
        return [r.event["payload"] for r in self.runtime.log.scan(verify=True).records
                if r.event.get("taskId") == task_id
                and r.event["eventType"] == event_type]


class TestTheAuditTrailIsTrue(PolicyRuntimeCase):
    """The MOGO-011 Step 3 finding F-1, kept fixed.

    Before Step 3 an acquisition-class task produced a PolicyEvaluated event
    claiming the policy was "not applicable" with a null operation class, then
    TaskClaimed and TaskStarted for an execution that never happened. Each of
    these tests fails if any part of that returns.
    """

    def test_a_denied_task_records_the_denial_it_actually_made(self):
        source = self.source("denied")
        task_id = self.submit_acquisition(source)
        payload = self.payloads(task_id, "PolicyEvaluated")[0]
        self.assertEqual(payload["decision"], "deny")
        self.assertNotEqual(payload["decision"], "not_applicable")
        self.assertEqual(payload["operationClass"], "acquisition")
        self.assertIsNotNone(payload["operationClass"])
        self.assertEqual(payload["reason"], "no_authorization_record")
        self.assertEqual(payload["subjectSourceId"], source)

    def test_a_denied_task_emits_no_claim_and_no_start(self):
        """Nothing was claimed and nothing ran, so the log must not say they
        were. This is the single most important assertion in the suite."""
        task_id = self.submit_acquisition(self.source("no-fabrication"))
        types = self.events(task_id)
        self.assertNotIn("TaskClaimed", types)
        self.assertNotIn("TaskStarted", types)
        self.assertNotIn("TaskFailed", types)
        self.assertNotIn("TaskDeadLettered", types)
        self.assertEqual(types, ["TaskRequested", "TaskPolicyCheckRequested",
                                 "PolicyEvaluated", "AcquisitionDenied",
                                 "HumanReviewRequired"])

    def test_no_task_attempt_is_recorded_for_a_blocked_task(self):
        task_id = self.submit_acquisition(self.source("no-attempt"))
        count = self.runtime.connection.execute(
            "SELECT COUNT(*) FROM task_attempts WHERE task_id = ?",
            (task_id,)).fetchone()[0]
        self.assertEqual(count, 0)
        self.assertEqual(self.task(task_id)["attempt"], 0)

    def test_every_decision_records_who_what_when_why_and_policy_version(self):
        """Constitution section 4.20, field by field."""
        source = self.source("audit-fields")
        self.authorize(source, "PERMITTED_PUBLIC_METADATA", ["metadata"])
        task_id = self.submit_acquisition(source)
        payload = self.payloads(task_id, "PolicyEvaluated")[0]
        for field in ("decision", "reason", "operationClass", "requestedOperations",
                      "subjectSourceId", "authorizationId", "policyStatus",
                      "policyVersion", "decisionAuthority", "permittedOperations",
                      "authorizationRecordHash"):
            self.assertIn(field, payload)
        self.assertEqual(payload["decisionAuthority"], "governance:mogo-legal")
        self.assertEqual(payload["policyVersion"], "1.0")
        self.assertTrue(payload["authorizationRecordHash"])

    def test_the_decision_is_produced_by_the_policy_gate(self):
        task_id = self.submit_acquisition(self.source("producer"))
        producers = {r.event["producer"]
                     for r in self.runtime.log.scan().records
                     if r.event.get("taskId") == task_id
                     and r.event["eventType"] in ("PolicyEvaluated",
                                                  "AcquisitionDenied")}
        self.assertEqual(producers, {"policyGate"})


class TestGateIntegration(PolicyRuntimeCase):
    def test_a_permitted_acquisition_reaches_queued_and_executes(self):
        source = self.source("permitted")
        self.authorize(source, "PERMITTED_PUBLIC_METADATA", ["metadata"])
        task_id = self.submit_acquisition(source)
        row = self.task(task_id)
        self.assertEqual(row["state"], "succeeded")
        self.assertEqual(row["policy_decision"], "permit")
        self.assertEqual(row["policy_status"], "PERMITTED_PUBLIC_METADATA")
        self.assertIn("AcquisitionAuthorized", self.events(task_id))

    def test_a_denied_acquisition_reaches_blocked_then_awaiting_review(self):
        task_id = self.submit_acquisition(self.source("blocked-path"))
        row = self.task(task_id)
        self.assertEqual(row["state"], "awaiting_review")
        self.assertEqual(row["policy_decision"], "deny")
        self.assertEqual(row["terminal"], 0)

    def test_the_blocked_state_is_actually_visited(self):
        """`blocked` was an approved state no event had ever landed in.

        Re-derived from the log: the PolicyEvaluated denial carries
        policy_check -> blocked, and HumanReviewRequired carries
        blocked -> awaiting_review. Both are approved Catalog section L edges.
        """
        task_id = self.submit_acquisition(self.source("visits-blocked"))
        from mogo_platform.runtime import audit as audit_module
        report = audit_module.audit_report(self.runtime.connection,
                                           self.runtime.log, task_id=task_id)
        steps = [(step["from"], step["to"]) for step in report["timeline"]]
        self.assertIn(("policy_check", "blocked"), steps)
        self.assertIn(("blocked", "awaiting_review"), steps)

    def test_a_non_acquisition_task_is_a_recorded_no_op(self):
        envelope, payload = cli_module.build_demo_command()
        outcome = self.runtime.submit(envelope, payload)
        self.runtime.run_once()
        row = self.task(outcome.task_id)
        self.assertEqual(row["state"], "succeeded")
        self.assertEqual(row["policy_decision"], "not_applicable")
        self.assertEqual(row["operation_class"], "non_acquisition")
        self.assertNotIn("AcquisitionAuthorized", self.events(outcome.task_id))

    def test_every_task_passes_through_policy_check(self):
        """Catalog section L footnote 2: routing every task through one state is
        what makes "was this checked?" answerable from the log for ALL tasks."""
        envelope, payload = cli_module.build_demo_command()
        plain = self.runtime.submit(envelope, payload)
        acquisition = self.submit_acquisition(self.source("uniform"))
        self.runtime.run_once()
        for task_id in (plain.task_id, acquisition):
            with self.subTest(task=task_id):
                self.assertIn("PolicyEvaluated", self.events(task_id))
                self.assertIsNotNone(self.task(task_id)["policy_decision"])

    def test_an_unreadable_policy_decision_blocks_rather_than_releases(self):
        """A decision this build cannot interpret must never reach `queued`.

        Constitution section 5.2: absence of a known permission is not
        permission. An event whose decision string this build does not
        recognise -- a future value, a corrupted payload -- must resolve to
        `blocked`, because releasing on an unreadable record would let an
        unreadable decision authorize execution.
        """
        class _Record(object):
            def __init__(self, decision):
                self.event = {"payload": {} if decision is None
                              else {"decision": decision}}

        self.assertEqual(projection._policy_target(_Record("permit")), "queued")
        self.assertEqual(projection._policy_target(_Record("not_applicable")),
                         "queued")
        self.assertEqual(projection._policy_target(_Record("deny")), "blocked")
        for unreadable in ("allowed", "PERMIT", "", None, "authorized",
                           "something_new"):
            with self.subTest(decision=unreadable):
                self.assertEqual(projection._policy_target(_Record(unreadable)),
                                 "blocked")

    def test_a_task_with_no_subject_source_is_denied(self):
        envelope, payload = cli_module.build_policy_demo_command(
            self.source("no-subject"), "no-subject")
        envelope["inputRefs"] = []
        outcome = self.runtime.submit(envelope, payload)
        self.runtime.run_once()
        row = self.task(outcome.task_id)
        self.assertEqual(row["policy_decision"], "deny")
        self.assertEqual(row["policy_reason"], "no_subject_source")

    def test_expiry_denies_at_runtime(self):
        source = self.source("runtime-expiry")
        self.authorize(source, "PERMITTED_PUBLIC_METADATA", ["metadata"],
                       expiresAt="2026-08-08T11:30:00.000Z")
        task_id = self.submit_acquisition(source)
        self.assertEqual(self.task(task_id)["policy_reason"],
                         "authorization_expired")


class TestBypassIsImpossible(PolicyRuntimeCase):
    def test_requested_to_queued_is_not_a_legal_edge(self):
        """The projection would refuse the shortcut before any UPDATE."""
        self.assertFalse(task_states.is_legal_transition("requested", "queued"))
        self.assertEqual(task_states.legal_successors("requested"),
                         ("cancelled", "policy_check"))

    def test_policy_check_is_the_only_entry_to_queued(self):
        """Every other edge into `queued` belongs to a task that ALREADY passed
        the gate: a released retry, a reclaimed lease, or an approved review."""
        into_queued = {event: edge for event, edge in projection.TRANSITIONS.items()
                       if edge[1] == "queued"}
        self.assertEqual(sorted(into_queued),
                         ["HumanReviewCompleted", "PolicyEvaluated",
                          "TaskReclaimed", "TaskRetryReleased"])

    def test_the_gate_is_called_only_from_the_two_authorized_places(self):
        """The decision has exactly two call sites, and both are named.

        Asserting the NAMES rather than a count is what makes this an
        invariant: a future edit that consulted the gate from a dispatch path,
        a worker, or a CLI handler fails here even though the count would still
        look plausible.

          _evaluate_policy        the gate itself
          _re_evaluate_for_review an approval, which is only meaningful if the
                                  situation that caused the block has changed --
                                  and only the gate may say whether it has
        """
        source_path = os.path.join(SRC_DIR, "mogo_platform", "runtime",
                                   "orchestrator.py")
        with open(source_path, "r", encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        callers = set()
        for function in ast.walk(tree):
            if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for node in ast.walk(function):
                if (isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "evaluate"):
                    callers.add(function.name)
        self.assertEqual(sorted(callers),
                         ["_evaluate_policy", "_re_evaluate_for_review"])

    def test_no_other_runtime_module_consults_the_gate(self):
        """Only the orchestrator may authorize. A capability, the CLI or the
        audit layer reaching the gate would be a second authority."""
        runtime_dir = os.path.join(SRC_DIR, "mogo_platform", "runtime")
        offenders = []
        for root, _dirs, files in os.walk(runtime_dir):
            for name in sorted(files):
                if not name.endswith(".py") or name in ("orchestrator.py",
                                                        "policy.py"):
                    continue
                path = os.path.join(root, name)
                with open(path, "r", encoding="utf-8") as handle:
                    tree = ast.parse(handle.read(), filename=path)
                for node in ast.walk(tree):
                    if (isinstance(node, ast.Call)
                            and isinstance(node.func, ast.Attribute)
                            and node.func.attr == "evaluate"):
                        offenders.append((name, node.lineno))
        self.assertEqual(offenders, [])

    def test_the_gate_accepts_no_override_argument(self):
        import inspect
        signature = inspect.signature(policy.evaluate)
        self.assertEqual(list(signature.parameters),
                         ["operation_class", "requested_operations",
                          "authorization", "now_ms", "resolution_problem"])
        for name in ("force", "allow", "override", "bypass", "skip", "permit"):
            self.assertNotIn(name, signature.parameters)

    def test_no_environment_variable_can_permit(self):
        """Constitution section 5.5 names configuration and flags explicitly."""
        import inspect
        for module in (policy, authorizations):
            source = inspect.getsource(module)
            with self.subTest(module=module.__name__):
                self.assertNotIn("environ", source)
                self.assertNotIn("getenv", source)

    def test_dispatch_refuses_an_acquisition_task_without_a_recorded_permit(self):
        """Defence in depth: even a hand-corrupted index row cannot execute.

        The task is forced to `queued` with its recorded permit removed, which
        is not reachable through the normal path -- and dispatch still refuses.
        """
        source = self.source("corrupt-index")
        self.authorize(source, "PERMITTED_PUBLIC_METADATA", ["metadata"])
        envelope, payload = cli_module.build_policy_demo_command(source, "corrupt")
        outcome = self.runtime.submit(envelope, payload)
        with self.runtime.connection:
            self.runtime.connection.execute(
                "UPDATE tasks SET state = 'queued', policy_decision = NULL "
                "WHERE task_id = ?", (outcome.task_id,))
        report = self.runtime.run_once()

        row = self.task(outcome.task_id)
        self.assertEqual(row["state"], "queued")
        self.assertNotIn("TaskClaimed", self.events(outcome.task_id))
        self.assertIn(outcome.task_id, report["abandoned"])
        anomaly = self.runtime.connection.execute(
            "SELECT reason FROM transition_anomalies WHERE task_id = ? "
            "ORDER BY anomaly_id DESC LIMIT 1", (outcome.task_id,)).fetchone()
        self.assertIn("dispatch_without_policy_permit", anomaly["reason"])

    def test_a_refused_dispatch_does_not_spin_the_run_loop(self):
        source = self.source("no-spin")
        self.authorize(source, "PERMITTED_PUBLIC_METADATA", ["metadata"])
        envelope, payload = cli_module.build_policy_demo_command(source, "no-spin")
        outcome = self.runtime.submit(envelope, payload)
        with self.runtime.connection:
            self.runtime.connection.execute(
                "UPDATE tasks SET state = 'queued', policy_decision = 'deny' "
                "WHERE task_id = ?", (outcome.task_id,))
        report = self.runtime.run_once()          # must terminate
        self.assertIn(outcome.task_id, report["abandoned"])


class TestReplayNeverReDecides(PolicyRuntimeCase):
    def test_rebuild_does_not_call_the_gate(self):
        """Replay RE-APPLIES a recorded decision; it never makes a new one.

        If it re-derived, a change to an authorization record or to the
        licensing table would silently rewrite history.
        """
        source = self.source("replay")
        self.authorize(source, "PERMITTED_PUBLIC_METADATA", ["metadata"])
        self.submit_acquisition(source)
        self.submit_acquisition(self.source("replay-denied"))

        original = policy.evaluate
        calls = []

        def spy(*args, **kwargs):
            calls.append(args)
            return original(*args, **kwargs)

        policy.evaluate = spy
        try:
            projection.rebuild(self.runtime.connection, self.runtime.log,
                               self.runtime.paths.root)
        finally:
            policy.evaluate = original
        self.assertEqual(calls, [])

    def test_rebuild_reproduces_every_policy_column_exactly(self):
        source = self.source("rebuild-permit")
        self.authorize(source, "PERMITTED_PUBLIC_METADATA", ["metadata"])
        self.submit_acquisition(source)
        self.submit_acquisition(self.source("rebuild-deny"))

        def snapshot():
            return {
                "tasks": [dict(r) for r in self.runtime.connection.execute(
                    "SELECT * FROM tasks ORDER BY created_log_sequence")],
                "decisions": [
                    {k: r[k] for k in r.keys() if k != "decision_id"}
                    for r in self.runtime.connection.execute(
                        "SELECT * FROM policy_decisions "
                        "ORDER BY task_id, log_sequence")],
            }

        before = snapshot()
        self.assertTrue(before["decisions"])
        # Advance a year: a column derived at projection time would change.
        self.clock.advance_ms(365 * 24 * 60 * 60 * 1000)
        projection.rebuild(self.runtime.connection, self.runtime.log,
                           self.runtime.paths.root)
        self.assertEqual(snapshot(), before)

    def test_editing_an_authorization_cannot_rewrite_a_past_decision(self):
        """Constitution section 5.7, made mechanical.

        The decision carries the record's content hash as it stood at decision
        time. Recording a superseding authorization later changes nothing about
        what was already decided.
        """
        source = self.source("immutable-history")
        self.authorize(source, "PERMITTED_PUBLIC_METADATA", ["metadata"])
        task_id = self.submit_acquisition(source)
        before = dict(self.task(task_id))
        recorded_hash = self.payloads(task_id, "PolicyEvaluated")[0][
            "authorizationRecordHash"]

        first = self.runtime.connection.execute(
            "SELECT authorization_id FROM acquisition_authorizations "
            "WHERE source_id = ?", (source,)).fetchone()["authorization_id"]
        self.authorize(source, "PROHIBITED", [],
                       supersedesAuthorizationId=first)

        projection.rebuild(self.runtime.connection, self.runtime.log,
                           self.runtime.paths.root)
        self.assertEqual(dict(self.task(task_id)), before)
        self.assertEqual(
            self.payloads(task_id, "PolicyEvaluated")[0][
                "authorizationRecordHash"], recorded_hash)


if __name__ == "__main__":
    unittest.main(verbosity=2)

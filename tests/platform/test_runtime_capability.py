#!/usr/bin/env python3
"""MOGO-011 Step 1 -- capability registry, dispatch eligibility, determinism.

Pure stdlib (unittest). Offline, deterministic, repeatable. Tempfile state root.

Run with:
    python3 -m unittest tests.platform.test_runtime_capability -v
"""

import ast
import inspect
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
from mogo_platform.runtime import errors as runtime_errors  # noqa: E402
from mogo_platform.runtime import orchestrator as orchestrator_module  # noqa: E402
from mogo_platform.runtime import paths as paths_module  # noqa: E402
from mogo_platform.runtime import registry  # noqa: E402
from mogo_platform.runtime import store  # noqa: E402
from mogo_platform.runtime.capabilities import echo as echo_capability  # noqa: E402
from mogo_platform.runtime.capabilities import (  # noqa: E402
    fail_then_succeed as fail_then_succeed_capability)
from mogo_platform.runtime.capabilities import (  # noqa: E402
    policy_probe as policy_probe_capability)

# Independently transcribed from the Step 1 plan section 11.
EXPECTED_CAPABILITY_ID = "CAP|research|runtime-echo"
EXPECTED_CAPABILITY_NAME = "research.runtime.echo.v1"
EXPECTED_ACCEPTED_COMMANDS = ["NormalizeArtifact"]
EXPECTED_DISPATCHABLE_LIFECYCLE = ("approved", "production")

# Independently transcribed from the Step 2 plan section 16.
EXPECTED_RETRY_CAPABILITY_ID = "CAP|research|runtime-fail-then-succeed"
EXPECTED_RETRY_CAPABILITY_NAME = "research.runtime.fail-then-succeed.v1"
# Independently transcribed from the Step 3 plan section 4 / decision C-2.
EXPECTED_POLICY_CAPABILITY_ID = "CAP|research|policy-probe"
EXPECTED_POLICY_CAPABILITY_NAME = "research.policy.probe.v1"
EXPECTED_CAPABILITY_IDS = (EXPECTED_CAPABILITY_ID, EXPECTED_RETRY_CAPABILITY_ID,
                           EXPECTED_POLICY_CAPABILITY_ID,
    "CAP|research|ingest-local-artifact",
    "CAP|research|acquire-approved-source-metadata",
)


class CapabilityCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.paths = paths_module.RuntimePaths(os.path.join(self._tmp.name, "state"))
        self.runtime = orchestrator_module.Orchestrator(paths=self.paths).open()
        self.runtime.register_builtin_capabilities()

    def tearDown(self):
        self.runtime.close()
        self._tmp.cleanup()

    def row(self):
        return registry.lookup(self.runtime.connection, EXPECTED_CAPABILITY_ID)


class TestManifest(CapabilityCase):
    def test_manifest_matches_the_plan(self):
        manifest = echo_capability.MANIFEST
        self.assertEqual(manifest["capabilityId"], EXPECTED_CAPABILITY_ID)
        self.assertEqual(manifest["name"], EXPECTED_CAPABILITY_NAME)
        self.assertEqual(manifest["acceptedCommands"], EXPECTED_ACCEPTED_COMMANDS)
        self.assertEqual(manifest["lifecycleStatus"], "production")
        self.assertTrue(manifest["enabledState"])
        self.assertEqual(manifest["operationClass"], "non_acquisition")

    def test_manifest_declares_no_secret_and_no_connector(self):
        # ADR-012 D-09: no secrets in v1. The first capability needs none.
        self.assertEqual(echo_capability.MANIFEST["requiredSecretReferences"], [])
        self.assertEqual(echo_capability.MANIFEST["requiredConnectors"], [])

    def test_manifest_validates(self):
        self.assertIs(registry.validate_manifest(echo_capability.MANIFEST),
                      echo_capability.MANIFEST)

    def test_manifest_missing_a_required_field_is_refused(self):
        broken = dict(echo_capability.MANIFEST)
        del broken["compatibility"]
        with self.assertRaises(runtime_errors.ContractValidationError):
            registry.validate_manifest(broken)

    def test_unapproved_lifecycle_state_is_refused(self):
        broken = dict(echo_capability.MANIFEST)
        broken["lifecycleStatus"] = "blessed"
        with self.assertRaises(runtime_errors.ContractValidationError):
            registry.validate_manifest(broken)


class TestRegistration(CapabilityCase):
    def test_registration_is_idempotent(self):
        outcomes = self.runtime.register_builtin_capabilities()
        for capability_id in EXPECTED_CAPABILITY_IDS:
            self.assertEqual(outcomes[capability_id], "unchanged")
        count = self.runtime.connection.execute(
            "SELECT COUNT(*) FROM capabilities").fetchone()[0]
        self.assertEqual(count, len(EXPECTED_CAPABILITY_IDS))

    def test_manifest_hash_is_recorded(self):
        self.assertEqual(self.row()["manifest_hash"],
                         registry.manifest_hash(echo_capability.MANIFEST))

    def test_a_changed_manifest_under_the_same_id_is_refused(self):
        changed = dict(echo_capability.MANIFEST)
        changed["version"] = "2.0.0"
        with self.assertRaises(runtime_errors.CapabilityNotDispatchableError):
            with store.immediate_transaction(self.runtime.connection):
                registry.register(self.runtime.connection, changed, "t")

    def test_lookup_accepts_both_attested_reference_forms(self):
        by_id = registry.lookup(self.runtime.connection, EXPECTED_CAPABILITY_ID)
        by_name = registry.lookup(self.runtime.connection, EXPECTED_CAPABILITY_NAME)
        self.assertIsNotNone(by_id)
        self.assertEqual(by_id["capability_id"], by_name["capability_id"])

    def test_lookup_of_an_unknown_reference_is_none(self):
        self.assertIsNone(registry.lookup(self.runtime.connection, "CAP|no|such"))
        self.assertIsNone(registry.lookup(self.runtime.connection, None))


class TestDispatchEligibility(CapabilityCase):
    """The five Catalog section O conditions. Every failure is fail-closed."""

    def test_dispatchable_lifecycle_states_match_the_catalog(self):
        self.assertEqual(tuple(registry.DISPATCHABLE_LIFECYCLE_STATES),
                         EXPECTED_DISPATCHABLE_LIFECYCLE)

    def test_registered_enabled_compatible_capability_dispatches(self):
        self.assertIsNotNone(registry.assert_dispatchable(
            self.row(), "NormalizeArtifact", 1, EXPECTED_CAPABILITY_ID))

    def test_unknown_capability_fails_closed(self):
        with self.assertRaises(runtime_errors.CapabilityNotDispatchableError):
            registry.assert_dispatchable(None, "NormalizeArtifact", 1, "CAP|x|y")

    def test_disabled_capability_fails_closed(self):
        self.runtime.connection.execute(
            "UPDATE capabilities SET enabled_state = 0 WHERE capability_id = ?",
            (EXPECTED_CAPABILITY_ID,))
        with self.assertRaises(runtime_errors.CapabilityNotDispatchableError):
            registry.assert_dispatchable(self.row(), "NormalizeArtifact", 1,
                                         EXPECTED_CAPABILITY_ID)

    def test_non_dispatchable_lifecycle_fails_closed(self):
        for state in ("proposed", "experimental", "deprecated", "disabled", "retired"):
            with self.subTest(state=state):
                self.runtime.connection.execute(
                    "UPDATE capabilities SET lifecycle_status = ? "
                    "WHERE capability_id = ?", (state, EXPECTED_CAPABILITY_ID))
                with self.assertRaises(
                        runtime_errors.CapabilityNotDispatchableError):
                    registry.assert_dispatchable(self.row(), "NormalizeArtifact", 1,
                                                 EXPECTED_CAPABILITY_ID)

    def test_unaccepted_command_type_fails_closed(self):
        with self.assertRaises(runtime_errors.CapabilityNotDispatchableError):
            registry.assert_dispatchable(self.row(), "AcquireArtifact", 1,
                                         EXPECTED_CAPABILITY_ID)

    def test_incompatible_command_version_fails_closed(self):
        with self.assertRaises(runtime_errors.CapabilityNotDispatchableError):
            registry.assert_dispatchable(self.row(), "NormalizeArtifact", 2,
                                         EXPECTED_CAPABILITY_ID)

    def test_disabled_capability_produces_a_failed_task_not_an_execution(self):
        self.runtime.connection.execute(
            "UPDATE capabilities SET enabled_state = 0 WHERE capability_id = ?",
            (EXPECTED_CAPABILITY_ID,))
        envelope, payload = cli_module.build_demo_command()
        outcome = self.runtime.submit(envelope, payload)
        self.runtime.run_once()
        row = self.runtime.connection.execute(
            "SELECT state, error_class, result_hash, dead_letter_reason "
            "FROM tasks WHERE task_id = ?", (outcome.task_id,)).fetchone()
        # A disabled capability is a `validation` failure, which Catalog
        # section K marks non-retryable and terminal -- so the task
        # dead-letters rather than stranding in `failed`. Nothing executed.
        self.assertEqual(row["state"], "dead_lettered")
        self.assertEqual(row["error_class"], "validation")
        self.assertEqual(row["dead_letter_reason"], "non_retryable_error_class")
        self.assertIsNone(row["result_hash"])


class TestCapabilityDeterminism(CapabilityCase):
    PAYLOAD = {"b": [3, 2, 1], "a": {"deep": "é中文", "n": None, "t": True}}

    def _fresh_payload(self):
        """A STRUCTURALLY EQUAL but distinct object every call.

        Reusing one object made the test blind to nondeterminism derived from
        object identity: a mutation adding id(payload) to the result went
        undetected because id() is stable for a single object. Determinism must
        hold across equal VALUES, not across one shared reference.
        """
        return {"b": [3, 2, 1], "a": {"deep": "\u00e9\u4e2d\u6587",
                                      "n": None, "t": True}}

    def test_output_is_deterministic_across_100_runs(self):
        first = echo_capability.execute(self._fresh_payload())
        for _ in range(100):
            self.assertEqual(echo_capability.execute(self._fresh_payload()), first)

    def test_output_is_identical_for_distinct_but_equal_objects(self):
        a = echo_capability.execute(self._fresh_payload())
        b = echo_capability.execute(self._fresh_payload())
        self.assertEqual(a, b)
        self.assertEqual(a["byteLength"], b["byteLength"])

    def test_content_hash_is_key_order_independent(self):
        a = echo_capability.execute({"x": 1, "y": 2})
        b = echo_capability.execute({"y": 2, "x": 1})
        self.assertEqual(a["contentHash"], b["contentHash"])

    def test_content_hash_is_array_order_sensitive(self):
        a = echo_capability.execute({"v": [1, 2]})
        b = echo_capability.execute({"v": [2, 1]})
        self.assertNotEqual(a["contentHash"], b["contentHash"])

    def test_result_carries_capability_identity(self):
        result = echo_capability.execute(self.PAYLOAD)
        self.assertEqual(result["capabilityId"], EXPECTED_CAPABILITY_ID)
        self.assertEqual(result["capabilityVersion"],
                         echo_capability.CAPABILITY_VERSION)

    def test_hash_matches_the_canonical_form(self):
        result = echo_capability.execute(self.PAYLOAD)
        self.assertEqual(result["contentHash"], ids.content_hash_of(self.PAYLOAD))

    def test_non_json_shaped_payload_fails_closed(self):
        with self.assertRaises(runtime_errors.ContractValidationError):
            echo_capability.execute({"bad": object()})

    def test_oversized_payload_fails_closed(self):
        oversized = {"big": "x" * (echo_capability.MAX_PAYLOAD_BYTES + 10)}
        with self.assertRaises(runtime_errors.ContractValidationError):
            echo_capability.execute(oversized)

    def test_capability_module_performs_no_io(self):
        tree = ast.parse(inspect.getsource(echo_capability))
        called = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute):
                    called.add(func.attr)
                elif isinstance(func, ast.Name):
                    called.add(func.id)
        for forbidden in ("open", "write", "remove", "system", "popen", "now",
                          "time", "random", "uuid4"):
            self.assertNotIn(forbidden, called)

    def test_capability_module_imports_nothing_that_can_reach_the_world(self):
        tree = ast.parse(inspect.getsource(echo_capability))
        absolute = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                absolute.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and not node.level:
                absolute.add(node.module)
        self.assertEqual(absolute, set())


class TestOnlyTheRegisteredCapabilityExecutes(CapabilityCase):
    def test_exactly_the_approved_capabilities_are_registered(self):
        rows = registry.all_capabilities(self.runtime.connection)
        self.assertEqual([row["capability_id"] for row in rows],
                         sorted(EXPECTED_CAPABILITY_IDS))

    def test_exactly_the_approved_callables_are_wired(self):
        self.assertEqual(set(orchestrator_module.CAPABILITY_CALLABLES),
                         set(EXPECTED_CAPABILITY_IDS))
        self.assertIs(
            orchestrator_module.CAPABILITY_CALLABLES[EXPECTED_CAPABILITY_ID],
            echo_capability.execute)
        self.assertIs(
            orchestrator_module.CAPABILITY_CALLABLES[
                EXPECTED_RETRY_CAPABILITY_ID],
            fail_then_succeed_capability.execute)
        self.assertIs(
            orchestrator_module.CAPABILITY_CALLABLES[
                EXPECTED_POLICY_CAPABILITY_ID],
            policy_probe_capability.execute)

    def test_a_registered_capability_with_no_implementation_fails_closed(self):
        """No implementation is a `validation` failure, which is NOT retryable.

        Step 1 asserted this task stopped at `failed`. `failed` is not terminal,
        and Constitution section 6.5 requires every task to reach a visible
        terminal outcome -- so under Step 2 the same non-retryable failure now
        resolves to `dead_lettered`, with the reason recorded. The failure class
        is unchanged; what changed is that the task no longer strands.
        """
        manifest = dict(echo_capability.MANIFEST)
        manifest["capabilityId"] = "CAP|research|ghost"
        manifest["name"] = "research.runtime.ghost.v1"
        with store.immediate_transaction(self.runtime.connection):
            registry.register(self.runtime.connection, manifest, "t")
        envelope, payload = cli_module.build_demo_command()
        envelope["targetCapability"] = "CAP|research|ghost"
        outcome = self.runtime.submit(envelope, payload)
        self.runtime.run_once()
        row = self.runtime.connection.execute(
            "SELECT state, error_class, terminal, dead_letter_reason FROM tasks "
            "WHERE task_id = ?", (outcome.task_id,)).fetchone()
        self.assertEqual(row["state"], "dead_lettered")
        self.assertEqual(row["error_class"], "validation")
        self.assertEqual(row["terminal"], 1)
        self.assertEqual(row["dead_letter_reason"], "non_retryable_error_class")


class TestTheSecondCapability(CapabilityCase):
    """research.runtime.fail-then-succeed.v1 -- MOGO-011 Step 2."""

    def retry_row(self):
        return registry.lookup(self.runtime.connection,
                               EXPECTED_RETRY_CAPABILITY_ID)

    def test_the_second_capability_is_registered(self):
        row = self.retry_row()
        self.assertIsNotNone(row)
        self.assertEqual(row["name"], EXPECTED_RETRY_CAPABILITY_NAME)
        self.assertEqual(row["operation_class"], "non_acquisition")
        self.assertEqual(row["effect_class"], "pure")
        self.assertEqual(row["requires_execution_context"], 1)

    def test_it_exercises_the_second_dispatchable_lifecycle_state(self):
        """echo is `production`; this one is `approved`.

        Both are dispatchable, and Step 1 only ever exercised one of them.
        Declaring this capability honestly as approved-not-production gains the
        coverage for free.
        """
        self.assertEqual(self.retry_row()["lifecycle_status"], "approved")
        self.assertIn("approved", EXPECTED_DISPATCHABLE_LIFECYCLE)
        registry.assert_dispatchable(self.retry_row(), "NormalizeArtifact", 1,
                                     EXPECTED_RETRY_CAPABILITY_ID)

    def test_it_declares_exactly_the_failure_class_it_raises(self):
        self.assertEqual(registry.declared_failure_classes(self.retry_row()),
                         ("transient",))

    def test_its_failure_behaviour_is_deterministic(self):
        """100 invocations, identical outcome each time."""
        payload = {"note": "determinism", "failUntilAttempt": 3}
        for attempt in (1, 2, 3):
            for _ in range(100):
                with self.assertRaises(runtime_errors.CapabilityFailure) as caught:
                    fail_then_succeed_capability.execute(payload,
                                                         {"attempt": attempt})
                self.assertEqual(caught.exception.error_class, "transient")

    def test_its_success_behaviour_is_deterministic(self):
        payload = {"note": "determinism", "failUntilAttempt": 1}
        hashes = {fail_then_succeed_capability.execute(
            payload, {"attempt": 2})["contentHash"] for _ in range(100)}
        self.assertEqual(len(hashes), 1)

    def test_the_success_result_is_identical_for_every_attempt_that_succeeds(self):
        """The invariant the whole design rests on.

        The DECISION to fail depends on the attempt; the RESULT CONTENT does
        not. If it did, a crash between execution and recording success would
        become visible in the output and the crash-boundary-8 argument would
        collapse.
        """
        payload = {"note": "attempt-invariant", "failUntilAttempt": 1}
        results = [fail_then_succeed_capability.execute(payload, {"attempt": n})
                   for n in range(2, 11)]
        self.assertEqual(len({r["contentHash"] for r in results}), 1)
        self.assertEqual(len({r["byteLength"] for r in results}), 1)
        for result in results:
            self.assertNotIn("failUntilAttempt", result["normalizedPayload"])
            self.assertNotIn("attempt", result["normalizedPayload"])

    def test_the_threshold_is_validated_fail_closed(self):
        for bad in (-1, 1.5, "2", True, None):
            with self.subTest(failUntilAttempt=bad):
                with self.assertRaises(runtime_errors.ContractValidationError):
                    fail_then_succeed_capability.execute(
                        {"failUntilAttempt": bad}, {"attempt": 1})

    def test_a_pure_capability_remains_safe_at_crash_boundary_8(self):
        """Re-execution is indistinguishable from never having been interrupted.

        This is the property -- and the ONLY property -- that makes boundary 8
        safe. It belongs to the capability, not to the kernel, which is why
        risk A-5 stays open at severity High.
        """
        payload = {"note": "boundary-8", "failUntilAttempt": 0}
        first = fail_then_succeed_capability.execute(payload, {"attempt": 1})
        second = fail_then_succeed_capability.execute(payload, {"attempt": 1})
        self.assertEqual(first, second)


class TestEffectClassificationAndTheA5Gate(CapabilityCase):
    def test_every_a5_gate_precondition_is_satisfied_by_the_result_store(self):
        """The governance moment this test was written to force has arrived.

        Its previous form asserted every precondition was False, and its own
        docstring said: "A future step that builds the result store must flip a
        flag here, which fails this test -- forcing a conscious governance
        decision at exactly the moment the gate opens." MOGO-014 Step 2 built
        runtime/result_store.py, the flags flipped, this test failed, and the
        decision was taken deliberately under explicit authorization.

        The property worth having is preserved, inverted: the gate is still
        DATA, still four named conditions, and any future step that adds a
        FIFTH condition or un-satisfies one fails here just as loudly.
        """
        self.assertEqual(len(registry.A5_EFFECTFUL_GATE), 4)
        for name, satisfied in registry.A5_EFFECTFUL_GATE.items():
            with self.subTest(precondition=name):
                self.assertIs(satisfied, True)
        self.assertEqual(sorted(registry.A5_EFFECTFUL_GATE),
                         ["duplicateEffectPrevention",
                          "idempotencyKeyedResultStore",
                          "outputVerificationByRehash",
                          "postExecutionRecoveryRule"])
        self.assertEqual(registry.unmet_a5_preconditions(), ())

    def test_the_gate_table_is_read_only(self):
        with self.assertRaises(TypeError):
            registry.A5_EFFECTFUL_GATE["idempotencyKeyedResultStore"] = True

    def test_an_effectful_capability_is_still_refused_when_a_precondition_is_unmet(self):
        """The refusal machinery must remain live now that the gate is open.

        The original test proved refusal by relying on every precondition being
        unmet, which is no longer true. The INTENT -- an effectful capability
        whose preconditions are not satisfied is refused, by name -- is asserted
        here directly by un-satisfying one condition for the duration of the
        test. This is strictly stronger than the version it replaces: it proves
        the refusal path still works rather than proving the gate is shut.
        """
        from types import MappingProxyType
        manifest = dict(echo_capability.MANIFEST)
        manifest["capabilityId"] = "CAP|research|effectful-probe"
        manifest["name"] = "research.runtime.effectful-probe.v1"
        manifest["effectClass"] = "effectful"
        original = registry.A5_EFFECTFUL_GATE
        try:
            registry.A5_EFFECTFUL_GATE = MappingProxyType(
                dict(original, postExecutionRecoveryRule=False))
            with self.assertRaises(
                    runtime_errors.EffectClassRefusedError) as caught:
                registry.validate_manifest(manifest)
            self.assertIn("postExecutionRecoveryRule", str(caught.exception))
        finally:
            registry.A5_EFFECTFUL_GATE = original
        # And with every precondition satisfied it is permitted -- the gate
        # opens and closes, rather than only ever refusing.
        registry.validate_manifest(manifest)

    def test_a_connector_using_capability_still_needs_the_connector_gate(self):
        """Narrowing the gate must not have opened it for connectors.

        MOGO-014 made connector-scoped gates apply to connector-using
        capabilities only. A capability that names a connector, or declares a
        remote acquisition operation, must still be treated as connector-using.
        """
        self.assertTrue(registry.uses_connector({"requiredConnectors": ["yt"]}))
        self.assertTrue(registry.uses_connector(
            {"acquisitionOperations": ["transcript"]}))
        self.assertTrue(registry.uses_connector(
            {"acquisitionOperations": ["discover"]}))
        self.assertTrue(registry.uses_connector(None),
                        "an unreadable manifest must fail CLOSED")
        self.assertTrue(registry.uses_connector("nonsense"))
        # local artifact ingestion reaches nothing
        self.assertFalse(registry.uses_connector(
            {"requiredConnectors": [], "acquisitionOperations": ["artifact"]}))

    def test_effect_classification_is_enforced(self):
        manifest = dict(echo_capability.MANIFEST)
        manifest["capabilityId"] = "CAP|research|odd-effect"
        manifest["name"] = "research.runtime.odd-effect.v1"
        for value in ("PURE", "impure", "", None, 1, "side_effecting"):
            manifest["effectClass"] = value
            with self.subTest(effectClass=value):
                with self.assertRaises(runtime_errors.ContractValidationError):
                    registry.validate_manifest(manifest)

    def test_an_absent_effect_class_defaults_to_the_restrictive_value(self):
        """`pure` grants nothing; `effectful` is the permissive value and must
        be declared explicitly -- and is then refused."""
        manifest = dict(echo_capability.MANIFEST)
        self.assertNotIn("effectClass", manifest)
        registry.validate_manifest(manifest)
        self.assertEqual(registry.DEFAULT_EFFECT_CLASS, "pure")
        self.assertEqual(self.row()["effect_class"], "pure")

    def test_a_review_routing_failure_class_is_refused_at_registration(self):
        for name in ("source_mutated", "human_review_required"):
            manifest = dict(echo_capability.MANIFEST)
            manifest["capabilityId"] = "CAP|research|review-probe"
            manifest["name"] = "research.runtime.review-probe.v1"
            manifest["failureClasses"] = [name]
            with self.subTest(failure_class=name):
                with self.assertRaises(runtime_errors.ContractValidationError) as c:
                    registry.validate_manifest(manifest)
                self.assertIn("review", str(c.exception))

    def test_an_unapproved_failure_class_is_refused_at_registration(self):
        manifest = dict(echo_capability.MANIFEST)
        manifest["capabilityId"] = "CAP|research|bad-class"
        manifest["name"] = "research.runtime.bad-class.v1"
        manifest["failureClasses"] = ["flaky"]
        with self.assertRaises(runtime_errors.ContractValidationError):
            registry.validate_manifest(manifest)

    def test_an_unbounded_retry_policy_is_refused_at_registration(self):
        manifest = dict(echo_capability.MANIFEST)
        manifest["capabilityId"] = "CAP|research|unbounded"
        manifest["name"] = "research.runtime.unbounded.v1"
        manifest["retryPolicy"] = {"attemptLimit": 1000}
        with self.assertRaises(runtime_errors.RetryPolicyError):
            registry.validate_manifest(manifest)

    def test_the_connector_gates_are_declared_and_only_the_policy_gate_is_met(self):
        """Constitution section 13, applied to the gate itself.

        The most important thing an operator can know about this platform is
        what it is not yet allowed to do, and why -- so the gates are data, and
        `status` prints them.

        MOGO-011 Step 3 BUILT the policy gate, so its entry flips to satisfied.
        That is a claim, and it is asserted here by name rather than by count,
        so that a future step cannot quietly mark another gate met: three
        remain unmet, and they are exactly the three that still stand between
        this platform and its first acquisition.
        """
        self.assertEqual(len(registry.CONNECTOR_GATES), 4)
        by_name = {gate["gate"]: gate for gate in registry.CONNECTOR_GATES}
        self.assertIs(by_name["policy_gate"]["satisfied"], True)
        # MOGO-014 Step 2 built the result store, so its entry flips too. The
        # two that remain are exactly the two that still stand between this
        # platform and its first NETWORK acquisition.
        self.assertIs(by_name["a5_result_store"]["satisfied"], True)
        # MOGO-015 Step 4 registered a real, dispatchable, governed connector
        # and proved it end to end, so this flips too. One gate remains.
        self.assertIs(by_name["first_connector_authorization"]["satisfied"], True)
        for name in ("acquisition_authorization_record",):
            with self.subTest(gate=name):
                self.assertIs(by_name[name]["satisfied"], False)
        for gate in registry.CONNECTOR_GATES:
            with self.subTest(gate=gate["gate"]):
                self.assertTrue(gate["authority"].strip())
                self.assertTrue(gate["requires"].strip())


class TestTheFirstCapabilityIsUnchanged(CapabilityCase):
    """echo is pinned. A changed manifest would break registration on every
    existing Step 1 state root, because register() refuses a changed manifest
    under an unchanged capabilityId -- so it is caught here, not in the field."""

    ECHO_MANIFEST_HASH = (
        "55a298289a3daaca6d2370c5a006b534c8e4b90fe0440763161eb033971ef82b")
    ECHO_RESULT_HASH = (
        "4a45c52fd69e19841fe5f8b10be04cfbb85031fc516cff13308bab3b192dad5e")

    def test_the_echo_manifest_hash_is_unchanged(self):
        self.assertEqual(registry.manifest_hash(echo_capability.MANIFEST),
                         self.ECHO_MANIFEST_HASH)

    def test_the_echo_result_hash_is_unchanged(self):
        result = echo_capability.execute(cli_module.DEMO_PAYLOAD)
        self.assertEqual(result["contentHash"], self.ECHO_RESULT_HASH)

    def test_the_echo_manifest_declares_no_step_2_field(self):
        """Not one Step 2 field is required, which is what keeps this hash
        stable and every existing state root upgradable."""
        for field in ("effectClass", "failureClasses", "requiresExecutionContext",
                      "retryPolicy"):
            with self.subTest(field=field):
                self.assertNotIn(field, echo_capability.MANIFEST)

    def test_echo_takes_no_execution_context(self):
        import inspect
        self.assertEqual(list(inspect.signature(echo_capability.execute).parameters),
                         ["payload"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

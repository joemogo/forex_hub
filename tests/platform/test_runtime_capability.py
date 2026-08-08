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

# Independently transcribed from the Step 1 plan section 11.
EXPECTED_CAPABILITY_ID = "CAP|research|runtime-echo"
EXPECTED_CAPABILITY_NAME = "research.runtime.echo.v1"
EXPECTED_ACCEPTED_COMMANDS = ["NormalizeArtifact"]
EXPECTED_DISPATCHABLE_LIFECYCLE = ("approved", "production")


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
        self.assertEqual(outcomes[EXPECTED_CAPABILITY_ID], "unchanged")
        count = self.runtime.connection.execute(
            "SELECT COUNT(*) FROM capabilities").fetchone()[0]
        self.assertEqual(count, 1)

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
            "SELECT state, error_class, result_hash FROM tasks WHERE task_id = ?",
            (outcome.task_id,)).fetchone()
        self.assertEqual(row["state"], "failed")
        self.assertEqual(row["error_class"], "validation")
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
    def test_exactly_one_capability_is_registered(self):
        rows = registry.all_capabilities(self.runtime.connection)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["capability_id"], EXPECTED_CAPABILITY_ID)

    def test_exactly_one_callable_is_wired(self):
        self.assertEqual(set(orchestrator_module.CAPABILITY_CALLABLES),
                         {EXPECTED_CAPABILITY_ID})
        self.assertIs(
            orchestrator_module.CAPABILITY_CALLABLES[EXPECTED_CAPABILITY_ID],
            echo_capability.execute)

    def test_a_registered_capability_with_no_implementation_fails_closed(self):
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
            "SELECT state, error_class FROM tasks WHERE task_id = ?",
            (outcome.task_id,)).fetchone()
        self.assertEqual(row["state"], "failed")
        self.assertEqual(row["error_class"], "validation")


if __name__ == "__main__":
    unittest.main(verbosity=2)

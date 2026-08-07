#!/usr/bin/env python3
"""MOGO-010 Step 1 -- task-state contract tests.

Pure stdlib (unittest). Fully offline, deterministic, repeatable.

The state set, terminal set, transition table and per-edge authority below are
transcribed INDEPENDENTLY from MOGO-009 Contract Catalog section L, which the
Architecture specification designates authoritative where its section 18.1
diagram differs. Nothing here compares an implementation constant to itself.

Run with:
    python3 -m unittest tests.platform.test_platform_task_states -v
"""

import os
import sys
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
# The ONE path entry the suites add. platform/src holds the uniquely named
# package; platform/ itself never becomes importable, so stdlib `platform`
# is untouched. See platform/README.md.
SRC_DIR = os.path.join(REPO_ROOT, "platform", "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from mogo_platform.contracts import errors  # noqa: E402
from mogo_platform.contracts import task_states  # noqa: E402

# ---------------------------------------------------------------------------
# Independently transcribed -- Catalog section L / Architecture section 18.1
# ---------------------------------------------------------------------------

EXPECTED_STATES = (
    "requested", "policy_check", "blocked", "awaiting_review", "queued",
    "claimed", "running", "failed", "retry_scheduled", "succeeded",
    "dead_lettered", "suppressed", "cancelled",
)

EXPECTED_TERMINAL_STATES = ("succeeded", "dead_lettered", "suppressed", "cancelled")

EXPECTED_NON_TERMINAL_STATES = (
    "requested", "policy_check", "blocked", "awaiting_review", "queued",
    "claimed", "running", "failed", "retry_scheduled",
)

# The 16 explicit edges of Catalog section L, with the authority column.
EXPECTED_EXPLICIT_EDGES = {
    ("requested", "policy_check"): "orchestrator",
    ("policy_check", "queued"): "policy_gate",
    ("policy_check", "blocked"): "policy_gate",
    ("blocked", "awaiting_review"): "orchestrator",
    ("queued", "claimed"): "worker_runtime",
    ("claimed", "running"): "worker_runtime",
    ("claimed", "queued"): "orchestrator",
    ("running", "queued"): "orchestrator",
    ("running", "succeeded"): "orchestrator",
    ("running", "awaiting_review"): "orchestrator",
    ("running", "failed"): "orchestrator",
    ("failed", "retry_scheduled"): "orchestrator",
    ("failed", "dead_lettered"): "orchestrator",
    ("retry_scheduled", "queued"): "orchestrator",
    ("awaiting_review", "queued"): "review_gate",
    ("awaiting_review", "suppressed"): "review_gate",
}

# Catalog section L: any non-terminal state may be cancelled by an explicit,
# audited operator action. 9 further edges.
EXPECTED_CANCELLATION_EDGES = {
    (state, "cancelled"): "operator" for state in EXPECTED_NON_TERMINAL_STATES
}

EXPECTED_EDGES = dict(EXPECTED_EXPLICIT_EDGES)
EXPECTED_EDGES.update(EXPECTED_CANCELLATION_EDGES)

# Independently transcribed -- Contract Catalog section K (12 error classes),
# with the retryable / terminal / routes-to-review columns.
EXPECTED_ERROR_CLASSES = {
    "transient":                (True,  False, False),
    "rate_limited":             (True,  False, False),
    "dependency_unavailable":   (True,  False, False),
    "authentication":           (False, True,  True),
    "policy_blocked":           (False, True,  True),
    "not_found":                (False, True,  False),
    "source_mutated":           (False, False, True),
    "validation":               (False, True,  False),
    "deterministic_processing": (False, True,  True),
    "corrupted_input":          (False, True,  True),
    "human_review_required":    (False, False, True),
    "permanent":                (False, True,  False),
}


class TestTaskStateInventory(unittest.TestCase):
    def test_exactly_thirteen_states(self):
        self.assertEqual(tuple(task_states.TASK_STATES), EXPECTED_STATES)
        self.assertEqual(len(task_states.TASK_STATES), 13)

    def test_no_duplicate_state_names(self):
        self.assertEqual(len(set(task_states.TASK_STATES)), 13)

    def test_exactly_four_terminal_states(self):
        self.assertEqual(tuple(task_states.TERMINAL_STATES),
                         EXPECTED_TERMINAL_STATES)
        self.assertEqual(len(task_states.TERMINAL_STATES), 4)

    def test_exactly_nine_non_terminal_states(self):
        self.assertEqual(tuple(task_states.NON_TERMINAL_STATES),
                         EXPECTED_NON_TERMINAL_STATES)
        self.assertEqual(len(task_states.NON_TERMINAL_STATES), 9)

    def test_terminal_and_non_terminal_partition_the_state_set(self):
        self.assertEqual(
            set(task_states.TERMINAL_STATES) | set(task_states.NON_TERMINAL_STATES),
            set(EXPECTED_STATES),
        )
        self.assertEqual(
            set(task_states.TERMINAL_STATES) & set(task_states.NON_TERMINAL_STATES),
            set(),
        )

    def test_is_terminal_matches_the_catalog(self):
        for state in EXPECTED_STATES:
            with self.subTest(state=state):
                self.assertEqual(
                    task_states.is_terminal(state), state in EXPECTED_TERMINAL_STATES
                )

    def test_unknown_state_name_is_an_error_not_a_quiet_false(self):
        with self.assertRaises(errors.ContractValidationError):
            task_states.is_terminal("in_progress")

    def test_every_state_is_reachable_from_requested(self):
        reachable = {"requested"}
        frontier = ["requested"]
        while frontier:
            current = frontier.pop()
            for successor in task_states.legal_successors(current):
                if successor not in reachable:
                    reachable.add(successor)
                    frontier.append(successor)
        self.assertEqual(reachable, set(EXPECTED_STATES))


class TestLegalTransitions(unittest.TestCase):
    def test_transition_count_is_twenty_five(self):
        self.assertEqual(len(task_states.LEGAL_TRANSITIONS), 25)
        self.assertEqual(len(task_states.TRANSITION_AUTHORITY), 25)

    def test_transition_set_matches_the_catalog(self):
        self.assertEqual(
            set(task_states.TRANSITION_AUTHORITY.keys()), set(EXPECTED_EDGES.keys())
        )

    def test_all_sixteen_explicit_catalog_edges_are_legal(self):
        self.assertEqual(len(EXPECTED_EXPLICIT_EDGES), 16)
        for (frm, to) in EXPECTED_EXPLICIT_EDGES:
            with self.subTest(edge=(frm, to)):
                self.assertTrue(task_states.is_legal_transition(frm, to))

    def test_every_non_terminal_state_may_be_cancelled(self):
        self.assertEqual(len(EXPECTED_CANCELLATION_EDGES), 9)
        for state in EXPECTED_NON_TERMINAL_STATES:
            with self.subTest(state=state):
                self.assertTrue(task_states.is_legal_transition(state, "cancelled"))

    def test_authority_is_recorded_and_correct_for_every_edge(self):
        for edge, expected_authority in EXPECTED_EDGES.items():
            with self.subTest(edge=edge):
                self.assertEqual(
                    task_states.transition_authority(*edge), expected_authority
                )

    def test_every_authority_is_an_approved_authority(self):
        for authority in task_states.TRANSITION_AUTHORITY.values():
            self.assertIn(authority, task_states.TRANSITION_AUTHORITIES)

    def test_assert_legal_transition_returns_the_authority(self):
        self.assertEqual(
            task_states.assert_legal_transition("queued", "claimed"), "worker_runtime"
        )


class TestProhibitedTransitions(unittest.TestCase):
    def test_every_pair_not_in_the_table_is_rejected(self):
        # Exhaustive sweep: 13 x 13 = 169 ordered pairs.
        checked = 0
        for frm in EXPECTED_STATES:
            for to in EXPECTED_STATES:
                checked += 1
                legal = (frm, to) in EXPECTED_EDGES
                with self.subTest(edge=(frm, to)):
                    self.assertEqual(task_states.is_legal_transition(frm, to), legal)
                    if not legal:
                        with self.assertRaises(errors.IllegalTaskTransitionError):
                            task_states.assert_legal_transition(frm, to)
        self.assertEqual(checked, 169)

    def test_no_self_transition_is_legal(self):
        for state in EXPECTED_STATES:
            with self.subTest(state=state):
                self.assertFalse(task_states.is_legal_transition(state, state))

    def test_named_illegal_shortcuts_are_rejected(self):
        for frm, to in (("queued", "succeeded"), ("running", "dead_lettered"),
                        ("blocked", "queued"), ("succeeded", "failed"),
                        ("requested", "running"), ("policy_check", "claimed"),
                        ("failed", "succeeded")):
            with self.subTest(edge=(frm, to)):
                with self.assertRaises(errors.IllegalTaskTransitionError):
                    task_states.assert_legal_transition(frm, to)


class TestTerminalStateAbsorption(unittest.TestCase):
    def test_terminal_states_have_no_legal_successors(self):
        for state in EXPECTED_TERMINAL_STATES:
            with self.subTest(state=state):
                self.assertEqual(task_states.legal_successors(state), ())

    def test_non_terminal_states_all_have_successors(self):
        for state in EXPECTED_NON_TERMINAL_STATES:
            with self.subTest(state=state):
                self.assertGreater(len(task_states.legal_successors(state)), 0)

    def test_late_transition_into_a_terminal_task_is_classified_not_applied(self):
        for state in EXPECTED_TERMINAL_STATES:
            with self.subTest(state=state):
                anomaly = task_states.classify_late_transition(state, "queued")
                self.assertIsInstance(anomaly, errors.LateTransitionAnomaly)
                # Classified, never raised, and -- Step 1 -- never logged.
                self.assertIn("not applied", str(anomaly))

    def test_no_anomaly_for_a_non_terminal_current_state(self):
        for state in EXPECTED_NON_TERMINAL_STATES:
            with self.subTest(state=state):
                self.assertIsNone(
                    task_states.classify_late_transition(state, "cancelled")
                )


class TestPolicyCheckFailClosed(unittest.TestCase):
    def test_non_acquisition_proceeds_with_a_recorded_no_op(self):
        self.assertEqual(
            task_states.classify_policy_check("non_acquisition"),
            ("queued", "not_applicable"),
        )

    def test_indeterminate_operation_class_routes_to_blocked(self):
        for indeterminate in (None, "", "unknown", "maybe", 17, object()):
            with self.subTest(value=indeterminate):
                state, reason = task_states.classify_policy_check(indeterminate)
                self.assertEqual(state, "blocked")
                self.assertEqual(reason, "operation_class_indeterminate")

    def test_acquisition_is_not_decided_here(self):
        # Returning a state would be a simulated policy decision. The policy
        # gate is a later, separately approved step.
        state, reason = task_states.classify_policy_check("acquisition")
        self.assertIsNone(state)
        self.assertEqual(reason, "requires_policy_gate")


class TestErrorTaxonomy(unittest.TestCase):
    def test_twelve_error_classes_with_the_catalog_flags(self):
        self.assertEqual(set(errors.ERROR_CLASSES.keys()),
                         set(EXPECTED_ERROR_CLASSES.keys()))
        self.assertEqual(len(errors.ERROR_CLASSES), 12)
        for name, expected in EXPECTED_ERROR_CLASSES.items():
            with self.subTest(error_class=name):
                record = errors.ERROR_CLASSES[name]
                self.assertEqual(
                    (record["retryable"], record["terminal"],
                     record["routesToReview"]),
                    expected,
                )

    def test_policy_blocked_is_never_retryable(self):
        # Constitution section 11: retrying a policy denial launders it.
        self.assertFalse(errors.ERROR_CLASSES["policy_blocked"]["retryable"])

    def test_exactly_three_classes_are_retryable(self):
        retryable = sorted(
            name for name, record in errors.ERROR_CLASSES.items()
            if record["retryable"]
        )
        self.assertEqual(
            retryable, ["dependency_unavailable", "rate_limited", "transient"]
        )

    def test_error_class_table_is_read_only(self):
        with self.assertRaises(TypeError):
            errors.ERROR_CLASSES["transient"] = {}
        with self.assertRaises(TypeError):
            errors.ERROR_CLASSES["policy_blocked"]["retryable"] = True

    def test_hierarchy_shape(self):
        expected_parents = {
            errors.ContractValidationError: (errors.PlatformError, ValueError),
            errors.UnsupportedContractVersionError: (errors.PlatformError, ValueError),
            errors.IdentifierError: (errors.PlatformError, ValueError),
            errors.InvariantViolationError: (errors.PlatformError, RuntimeError),
            errors.ProtectedBoundaryViolationError: (errors.PlatformError,
                                                     RuntimeError),
            errors.ConfigurationError: (errors.PlatformError, RuntimeError),
            errors.InternalPlatformError: (errors.PlatformError, RuntimeError),
            errors.IllegalTaskTransitionError: (errors.PlatformError, ValueError),
            errors.LateTransitionAnomaly: (errors.PlatformError, RuntimeError),
        }
        for error_cls, parents in expected_parents.items():
            with self.subTest(error=error_cls.__name__):
                for parent in parents:
                    self.assertTrue(issubclass(error_cls, parent))

    def test_every_required_error_type_exists(self):
        for name in ("PlatformError", "ContractValidationError",
                     "UnsupportedContractVersionError", "IdentifierError",
                     "InvariantViolationError", "ProtectedBoundaryViolationError",
                     "ConfigurationError", "InternalPlatformError",
                     "IllegalTaskTransitionError", "LateTransitionAnomaly"):
            with self.subTest(name=name):
                self.assertTrue(hasattr(errors, name))


class TestNoExecutionMachineryExists(unittest.TestCase):
    """Step 1 defines contracts. Nothing may apply, store, queue or retry."""

    FORBIDDEN_NAME_FRAGMENTS = (
        "apply", "transition_to", "set_state", "store", "persist", "save",
        "enqueue", "dequeue", "claim", "lease", "retry", "backoff",
        "dead_letter", "deadletter", "orchestrat", "schedule", "dispatch",
        "execute", "run_task", "worker", "logger", "log_",
    )

    def test_no_task_mutation_or_execution_function_exists(self):
        offenders = []
        for name in dir(task_states):
            if name.startswith("_") or not callable(getattr(task_states, name)):
                continue
            lowered = name.lower()
            for fragment in self.FORBIDDEN_NAME_FRAGMENTS:
                if fragment in lowered:
                    offenders.append((name, fragment))
        self.assertEqual(offenders, [])

    def test_module_imports_no_logging_machinery(self):
        self.assertNotIn("logging", dir(task_states))

    def test_public_surface_is_exactly_the_declared_contract(self):
        expected_callables = {
            "is_terminal", "is_legal_transition", "assert_legal_transition",
            "transition_authority", "legal_successors", "classify_late_transition",
            "classify_policy_check",
        }
        actual = {
            name for name in dir(task_states)
            if not name.startswith("_")
            and callable(getattr(task_states, name))
            and getattr(getattr(task_states, name), "__module__", None)
            == "mogo_platform.contracts.task_states"
        }
        self.assertEqual(actual, expected_callables)

    def test_transition_table_is_read_only(self):
        with self.assertRaises(TypeError):
            task_states.TRANSITION_AUTHORITY[("succeeded", "queued")] = "operator"

    def test_state_tuples_are_immutable(self):
        for constant in (task_states.TASK_STATES, task_states.TERMINAL_STATES,
                         task_states.NON_TERMINAL_STATES,
                         task_states.LEGAL_TRANSITIONS):
            self.assertIsInstance(constant, tuple)


if __name__ == "__main__":
    unittest.main(verbosity=2)

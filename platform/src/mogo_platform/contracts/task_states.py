#!/usr/bin/env python3
"""MOGO Automation Platform -- Step 1 task-state contract (definitions only).

AUTHORITY
    Automation Platform Constitution v1.0 (senior)  -- section 7
    ADR-012 (accepted 2026-08-07)                   -- D-05, approval 7
    MOGO-009 Contract Catalog, section L -- task state transitions (AUTHORITATIVE)
    MOGO-009 Contract Catalog, section C -- terminal states, late transitions
    MOGO-009 Architecture, section 18.1  -- state machine diagram

WHICH SOURCE GOVERNS
    Architecture section 18.1 draws `cancelled` reachable from three states
    "for legibility" and says so; Catalog section L states the normative rule
    -- ANY non-terminal state may be cancelled by an explicit, audited
    operator action -- and declares itself authoritative where the two differ.
    This module implements Catalog section L: 16 explicit edges plus 9
    cancellation edges, 25 in total.

IMPLEMENTED NOW
    * The 13 approved states, the 4 terminal states, the 9 non-terminal states.
    * The 25 legal transitions and the authority for every one of them.
    * Legality predicates and a raising assertion.
    * Late-transition classification.
    * Fail-closed classification of an indeterminate operation class.

EXPLICITLY DEFERRED -- absent from Step 1 entirely, and NOT claimed
    * NO TASK STATE IS APPLIED OR STORED. This module answers "is this
      transition legal, and who may make it?". It cannot perform one. There is
      no task object, no state table, no persistence and no read model.
    * NO ORCHESTRATOR. Constitution section 7: "Only the orchestrator writes
      task state." No orchestrator exists, so nothing writes task state.
    * NO QUEUE, NO LEASE, NO CLAIM, NO RETRY ENGINE, NO BACKOFF, NO
      DEAD-LETTER EXECUTION.
    * NO LOGGER. Catalog section C requires a late transition to be "logged as
      an anomaly and NOT applied". Step 1 CLASSIFIES it; logging is deferred
      with the event log that would receive it.
    * NO POLICY GATE. classify_policy_check() can resolve the non-acquisition
      and indeterminate cases from the contract alone. It cannot resolve the
      acquisition case, because that requires the policy gate -- so it says so
      rather than guessing.
"""

from types import MappingProxyType

from . import errors  # noqa: E402

# ---------------------------------------------------------------------------
# Catalog section L -- states
# ---------------------------------------------------------------------------

TASK_STATES = (
    "requested",
    "policy_check",
    "blocked",
    "awaiting_review",
    "queued",
    "claimed",
    "running",
    "failed",
    "retry_scheduled",
    "succeeded",
    "dead_lettered",
    "suppressed",
    "cancelled",
)

# Catalog section C: terminal states accept no further transitions.
TERMINAL_STATES = (
    "succeeded",
    "dead_lettered",
    "suppressed",
    "cancelled",
)

NON_TERMINAL_STATES = tuple(
    state for state in TASK_STATES if state not in TERMINAL_STATES
)

# ---------------------------------------------------------------------------
# Transition authority -- Catalog section L
# ---------------------------------------------------------------------------

AUTHORITY_ORCHESTRATOR = "orchestrator"
AUTHORITY_POLICY_GATE = "policy_gate"
AUTHORITY_WORKER_RUNTIME = "worker_runtime"
AUTHORITY_REVIEW_GATE = "review_gate"
AUTHORITY_OPERATOR = "operator"

TRANSITION_AUTHORITIES = (
    AUTHORITY_ORCHESTRATOR,
    AUTHORITY_POLICY_GATE,
    AUTHORITY_WORKER_RUNTIME,
    AUTHORITY_REVIEW_GATE,
    AUTHORITY_OPERATOR,
)

# The 16 explicit edges of Catalog section L, in table order.
_EXPLICIT_TRANSITIONS = (
    ("requested",       "policy_check",    AUTHORITY_ORCHESTRATOR),
    ("policy_check",    "queued",          AUTHORITY_POLICY_GATE),
    ("policy_check",    "blocked",         AUTHORITY_POLICY_GATE),
    ("blocked",         "awaiting_review", AUTHORITY_ORCHESTRATOR),
    ("queued",          "claimed",         AUTHORITY_WORKER_RUNTIME),
    ("claimed",         "running",         AUTHORITY_WORKER_RUNTIME),
    ("claimed",         "queued",          AUTHORITY_ORCHESTRATOR),
    ("running",         "queued",          AUTHORITY_ORCHESTRATOR),
    ("running",         "succeeded",       AUTHORITY_ORCHESTRATOR),
    ("running",         "awaiting_review", AUTHORITY_ORCHESTRATOR),
    ("running",         "failed",          AUTHORITY_ORCHESTRATOR),
    ("failed",          "retry_scheduled", AUTHORITY_ORCHESTRATOR),
    ("failed",          "dead_lettered",   AUTHORITY_ORCHESTRATOR),
    ("retry_scheduled", "queued",          AUTHORITY_ORCHESTRATOR),
    ("awaiting_review", "queued",          AUTHORITY_REVIEW_GATE),
    ("awaiting_review", "suppressed",      AUTHORITY_REVIEW_GATE),
)

# Catalog section L: any non-terminal state may be cancelled by an explicit,
# audited operator action. 9 further edges.
_CANCELLATION_TRANSITIONS = tuple(
    (state, "cancelled", AUTHORITY_OPERATOR) for state in NON_TERMINAL_STATES
)

TRANSITION_AUTHORITY = MappingProxyType({
    (frm, to): authority
    for frm, to, authority in _EXPLICIT_TRANSITIONS + _CANCELLATION_TRANSITIONS
})

LEGAL_TRANSITIONS = tuple(sorted(TRANSITION_AUTHORITY.keys()))


# ---------------------------------------------------------------------------
# Predicates -- pure, over the constant table above
# ---------------------------------------------------------------------------


def _require_state(state, field):
    if state not in TASK_STATES:
        errors.fail(
            "%s %r is not an approved task state" % (field, state),
            errors.ContractValidationError,
        )
    return state


def is_terminal(state):
    """True if `state` is one of the four terminal states."""
    _require_state(state, "state")
    return state in TERMINAL_STATES


def is_legal_transition(from_state, to_state):
    """True if the transition appears in the approved table.

    Both states must be approved states; an unknown state name is an error,
    not a quiet False.
    """
    _require_state(from_state, "from_state")
    _require_state(to_state, "to_state")
    return (from_state, to_state) in TRANSITION_AUTHORITY


def assert_legal_transition(from_state, to_state):
    """Raise IllegalTaskTransitionError unless the transition is approved.

    Mutates nothing under any outcome -- there is nothing to mutate.
    Returns the transition's authority when legal.
    """
    if not is_legal_transition(from_state, to_state):
        errors.fail(
            "illegal task transition %s -> %s" % (from_state, to_state),
            errors.IllegalTaskTransitionError,
        )
    return TRANSITION_AUTHORITY[(from_state, to_state)]


def transition_authority(from_state, to_state):
    """The authority permitted to make a legal transition.

    Raises IllegalTaskTransitionError if the transition is not approved.
    """
    return assert_legal_transition(from_state, to_state)


def legal_successors(state):
    """Every state legally reachable in one step from `state`.

    Empty for all four terminal states.
    """
    _require_state(state, "state")
    return tuple(sorted(to for (frm, to) in TRANSITION_AUTHORITY if frm == state))


def classify_late_transition(current_state, attempted_state):
    """Classify a transition arriving at an already-terminal task.

    Returns a LateTransitionAnomaly INSTANCE when `current_state` is terminal
    -- classified, deliberately not raised and deliberately not logged, because
    Catalog section C requires such a transition to be recorded as an anomaly
    and NOT applied, and no log exists in Step 1 to record it in.

    Returns None when `current_state` is not terminal; use
    assert_legal_transition() for that case.
    """
    _require_state(current_state, "current_state")
    _require_state(attempted_state, "attempted_state")
    if current_state in TERMINAL_STATES:
        return errors.LateTransitionAnomaly(
            "late transition %s -> %s arrived at terminal state %s; not applied"
            % (current_state, attempted_state, current_state)
        )
    return None


# ---------------------------------------------------------------------------
# policy_check routing -- fail closed
# ---------------------------------------------------------------------------

OPERATION_CLASS_ACQUISITION = "acquisition"
OPERATION_CLASS_NON_ACQUISITION = "non_acquisition"

OPERATION_CLASSES = (OPERATION_CLASS_ACQUISITION, OPERATION_CLASS_NON_ACQUISITION)

# Returned when the contract alone cannot decide, because the policy gate does
# not exist in Step 1. This is a marker, not a state.
REQUIRES_POLICY_GATE = "requires_policy_gate"


def classify_policy_check(operation_class):
    """Classify the outcome of `policy_check` for a given operation class.

    Returns a (next_state, reason) pair:

      non_acquisition -> ("queued", "not_applicable")
          Catalog section L footnote 2: every task passes through
          policy_check, but the gate evaluates only acquisition-class
          operations; others proceed with a recorded no-op.

      anything else   -> ("blocked", "operation_class_indeterminate")
          FAIL CLOSED. An operation class that cannot be determined is treated
          as acquisition-class and blocked, matching the licensing default.

      acquisition     -> (None, "requires_policy_gate")
          The contract cannot resolve this case; only the policy gate can, and
          the policy gate is a later, separately approved step. Returning a
          state here would be a simulated policy decision.
    """
    if operation_class == OPERATION_CLASS_NON_ACQUISITION:
        return ("queued", "not_applicable")
    if operation_class == OPERATION_CLASS_ACQUISITION:
        return (None, REQUIRES_POLICY_GATE)
    return ("blocked", "operation_class_indeterminate")

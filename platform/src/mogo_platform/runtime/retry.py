#!/usr/bin/env python3
"""MOGO Automation Platform -- the retry decision. Pure functions only.

AUTHORITY
    Automation Platform Constitution v1.0 (senior) -- section 11
    MOGO-009 Contract Catalog, section K -- error classification (AUTHORITATIVE)
    MOGO-009 Contract Catalog, section L -- failed -> retry_scheduled | dead_lettered
    MOGO-009 Contract Catalog, section A -- attemptLimit, default 3
    MOGO-011 Step 2 plan, sections 7, 8, 9, 11

NOTHING HERE TOUCHES THE WORLD
    No connection, no log, no clock, no I/O. Every function is a pure function
    of recorded values, which is what lets the whole retry policy be
    unit-tested exhaustively without a database, a log or a process -- and
    mutation-tested precisely. Step 1 established the same split with
    task_states.py (pure) against projection.py (writes).

    `now_ms` is always an ARGUMENT. This module never asks what time it is.

ONE RETRYABILITY TABLE, NEVER A SECOND
    contracts.errors.ERROR_CLASSES is the Catalog section K transcription
    committed in MOGO-010. This module is its first consumer and it does not
    copy it: retryability is read from that mapping and from nowhere else.
    There is no second list of retryable class names in the runtime, and no
    class name appears here as a literal except the one the Constitution
    singles out by name below.

DETERMINISM IS THE POINT
    Integer arithmetic throughout -- no floating point anywhere in the backoff,
    so the result is bit-identical on every platform and every Python build,
    with no rounding mode to reason about. jitterMs is 0 by decision B-2
    (2026-08-08); the field is retained and governed, and `random`/`secrets`
    are structurally unimportable across platform/**.
"""

from ..contracts import command as command_contract  # noqa: E402
from ..contracts import errors as contract_errors  # noqa: E402
from . import errors as runtime_errors  # noqa: E402

RETRY_YES = True
RETRY_NO = False

# Constitution section 11: "Retrying a policy denial is an attempt to launder
# it." This is the ONE class checked before the table is consulted, so that a
# mutation flipping its row to retryable is still refused. Belt and braces is
# justified for exactly one class, and this is it.
NEVER_RETRYABLE = ("policy_blocked",)

# The five reasons a failed task leaves `failed` for `dead_lettered`
# (plan section 12.1). There is no sixth path out of `failed` other than an
# explicit operator cancellation.
REASON_ATTEMPTS_EXHAUSTED = "attempts_exhausted"
REASON_NON_RETRYABLE = "non_retryable_error_class"
REASON_POLICY_DENIAL = "policy_denial_never_retried"
REASON_REQUIRES_REVIEW_NO_GATE = "requires_review_no_gate"
REASON_UNKNOWN_CLASS = "unknown_error_class"

DEAD_LETTER_REASONS = (
    REASON_ATTEMPTS_EXHAUSTED,
    REASON_NON_RETRYABLE,
    REASON_POLICY_DENIAL,
    REASON_REQUIRES_REVIEW_NO_GATE,
    REASON_UNKNOWN_CLASS,
)

REASON_RETRYABLE_WITHIN_LIMIT = "retryable_within_attempt_limit"

# Constitution section 11 requires retry to be BOUNDED. Catalog section A sets
# no upper bound on attemptLimit, so an attemptLimit of a million would be
# contract-valid and unbounded in practice. Decision B-5 (2026-08-08) fixes a
# runtime ceiling. It does not contradict the Catalog, which is silent, and
# every refusal under it is recorded rather than silent.
MAX_ATTEMPT_LIMIT = 10

# Catalog section A's default, read from the committed contract rather than
# re-declared here. Two declarations of one default is one declaration too many.
DEFAULT_ATTEMPT_LIMIT = command_contract.COMMAND_DEFAULTS["attemptLimit"]

DEFAULT_RETRY_POLICY = {
    "attemptLimit": DEFAULT_ATTEMPT_LIMIT,
    "backoffBaseMs": 1000,
    "backoffMultiplier": 2,
    "backoffCapMs": 60000,
    "jitterMs": 0,
}

RETRY_POLICY_FIELDS = tuple(sorted(DEFAULT_RETRY_POLICY.keys()))


class Decision(object):
    """The retry verdict and the reason recorded for it.

    `reason` is carried into the event payload either way, so the audit trail
    states WHY a task retried or dead-lettered without an operator inferring it
    from surrounding events.
    """

    __slots__ = ("retry", "reason")

    def __init__(self, retry, reason):
        self.retry = retry
        self.reason = reason

    def __eq__(self, other):
        return (isinstance(other, Decision)
                and self.retry == other.retry and self.reason == other.reason)

    def __hash__(self):
        return hash((self.retry, self.reason))

    def __repr__(self):
        return "Decision(retry=%r, reason=%r)" % (self.retry, self.reason)


def is_retryable(error_class):
    """True only if Catalog section K says so. Unknown classes fail closed."""
    record = contract_errors.ERROR_CLASSES.get(error_class)
    return bool(record is not None and record["retryable"])


def routes_to_review(error_class):
    record = contract_errors.ERROR_CLASSES.get(error_class)
    return bool(record is not None and record["routesToReview"])


def requires_review_gate(error_class):
    """True for a class that must reach review and has nowhere legal to go.

    Catalog section K marks two classes retryable=False, terminal=False,
    routesToReview=True. Verified against the committed contract:

        legal_successors("failed") == ('cancelled', 'dead_lettered',
                                       'retry_scheduled')

    There is no `failed -> awaiting_review` edge, and `awaiting_review ->
    queued` would need review_gate authority, which no component holds. Such a
    task can neither retry nor reach review, and would sit in `failed` forever
    -- violating Constitution section 6.5, which requires every task to reach a
    visible terminal outcome.

    Decision B-3 (2026-08-08): prohibit both classes at registration, and
    dead-letter them fail-closed at runtime with a distinct reason, rather than
    invent an unapproved Catalog section L edge into a state with no gate
    behind it. Reversible by a future step that builds the review gate.
    """
    record = contract_errors.ERROR_CLASSES.get(error_class)
    if record is None:
        return False
    return bool(record["routesToReview"] and not record["terminal"])


def classify_failure(error_class, attempt, attempt_limit):
    """The single retry decision. Pure: no clock, no connection, no I/O.

    Order matters and is asserted by test. The policy-denial guard is FIRST and
    INDEPENDENT of the table, so a mutation that flips the table's row to
    retryable is still refused -- two independent tests fail, one on the table
    and one on the decision.
    """
    if error_class in NEVER_RETRYABLE:
        return Decision(RETRY_NO, REASON_POLICY_DENIAL)

    record = contract_errors.ERROR_CLASSES.get(error_class)
    if record is None:                                     # fail closed
        return Decision(RETRY_NO, REASON_UNKNOWN_CLASS)

    if record["routesToReview"] and not record["terminal"]:
        return Decision(RETRY_NO, REASON_REQUIRES_REVIEW_NO_GATE)

    if not record["retryable"]:
        return Decision(RETRY_NO, REASON_NON_RETRYABLE)

    # Catalog section L: `failed -> retry_scheduled` when "retryable AND
    # attempt < limit". attempt counts executions STARTED, and attemptLimit is
    # a TOTAL, not an addend -- attemptLimit 3 permits 3 executions, i.e. the
    # first attempt plus at most 2 retries. Stated because "3 retries" and
    # "3 attempts" differ by one, and the difference is a silent off-by-one in
    # every implementation that leaves it implicit.
    if attempt >= attempt_limit:
        return Decision(RETRY_NO, REASON_ATTEMPTS_EXHAUSTED)

    return Decision(RETRY_YES, REASON_RETRYABLE_WITHIN_LIMIT)


def dead_letter_reason(error_class, attempt, attempt_limit):
    """The recorded reason a task dead-letters, or None when it will retry."""
    decision = classify_failure(error_class, attempt, attempt_limit)
    return None if decision.retry else decision.reason


def _require_non_negative_int(value, field):
    if isinstance(value, bool) or not isinstance(value, int):
        runtime_errors.fail(
            "retryPolicy.%s must be an integer, got %s"
            % (field, type(value).__name__),
            runtime_errors.RetryPolicyError,
        )
    if value < 0:
        runtime_errors.fail(
            "retryPolicy.%s must not be negative, got %d" % (field, value),
            runtime_errors.RetryPolicyError,
        )
    return value


def validate_policy(policy):
    """Fail-closed validation of a resolved retry policy. Returns it unchanged.

    A float backoffMultiplier is refused rather than coerced: floating point is
    the one thing that could make the backoff table differ between platforms,
    and this is the place it would enter.
    """
    for field in ("backoffBaseMs", "backoffCapMs", "jitterMs"):
        _require_non_negative_int(policy[field], field)

    multiplier = policy["backoffMultiplier"]
    if isinstance(multiplier, bool) or not isinstance(multiplier, int):
        runtime_errors.fail(
            "retryPolicy.backoffMultiplier must be an integer, got %s; a "
            "floating-point multiplier would make the backoff schedule depend "
            "on the platform's rounding mode"
            % (type(multiplier).__name__,),
            runtime_errors.RetryPolicyError,
        )
    if multiplier < 1:
        runtime_errors.fail(
            "retryPolicy.backoffMultiplier must be >= 1, got %d; a multiplier "
            "below 1 shrinks the delay on every retry, which is not backoff"
            % (multiplier,),
            runtime_errors.RetryPolicyError,
        )

    limit = policy["attemptLimit"]
    if isinstance(limit, bool) or not isinstance(limit, int):
        runtime_errors.fail(
            "retryPolicy.attemptLimit must be an integer, got %s"
            % (type(limit).__name__,),
            runtime_errors.RetryPolicyError,
        )
    if limit < 1:
        runtime_errors.fail(
            "retryPolicy.attemptLimit must be >= 1, got %d" % (limit,),
            runtime_errors.RetryPolicyError,
        )
    if limit > MAX_ATTEMPT_LIMIT:
        runtime_errors.fail(
            "retryPolicy.attemptLimit %d exceeds the runtime ceiling of %d "
            "(decision B-5); Constitution section 11 requires retry to be "
            "bounded and Catalog section A sets no upper bound"
            % (limit, MAX_ATTEMPT_LIMIT),
            runtime_errors.RetryPolicyError,
        )

    if policy["jitterMs"] != 0:
        # Decision B-2: the field is retained and governed, and its Step 2
        # value is 0. A non-zero value is refused rather than honoured, because
        # honouring it would put an ungoverned delay into a replayable schedule.
        runtime_errors.fail(
            "retryPolicy.jitterMs is %d; Step 2 governs this field at 0 "
            "(decision B-2). Jitter decorrelates concurrent retriers and this "
            "runtime has one process with one task in flight. When a "
            "concurrent claimer exists, the approved extension is deterministic "
            "jitter derived from the task identifier, not randomness."
            % (policy["jitterMs"],),
            runtime_errors.RetryPolicyError,
        )
    return policy


def resolve_policy(declared, attempt_limit_override=None):
    """Merge a declared policy over the build defaults, then validate.

    `declared` is whatever a capability manifest carries (possibly nothing).
    `attempt_limit_override` is the command's attemptLimit when it supplied
    one -- a command may tighten or loosen its own limit within the ceiling,
    and the RESOLVED value is what gets recorded at task creation, so a later
    change to a capability's defaults cannot retroactively alter a task that
    is already running.
    """
    resolved = dict(DEFAULT_RETRY_POLICY)
    if declared:
        for field in RETRY_POLICY_FIELDS:
            if field in declared:
                resolved[field] = declared[field]
        unknown = sorted(set(declared) - set(RETRY_POLICY_FIELDS))
        if unknown:
            runtime_errors.fail(
                "retryPolicy declares unknown field(s) %s; the approved fields "
                "are %s" % (unknown, list(RETRY_POLICY_FIELDS)),
                runtime_errors.RetryPolicyError,
            )
    if attempt_limit_override is not None:
        resolved["attemptLimit"] = attempt_limit_override
    return validate_policy(resolved)


def backoff_ms(attempt, policy):
    """Delay before the next attempt, in whole milliseconds.

        min(base * multiplier ** (attempt - 1), cap) + jitter

    `attempt` is the attempt that JUST FAILED, 1-based. Every operand is an
    int, `**` on ints is exact and `min` on ints is exact, so there is no
    floating-point arithmetic anywhere in this computation and the result is
    bit-identical on every platform.
    """
    if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1:
        runtime_errors.fail(
            "backoff is computed for the attempt that just failed, which is "
            "1-based; got %r" % (attempt,),
            runtime_errors.RetryPolicyError,
        )
    growth = policy["backoffBaseMs"] * (policy["backoffMultiplier"] ** (attempt - 1))
    return min(growth, policy["backoffCapMs"]) + policy["jitterMs"]


def next_eligible_at_ms(now_ms, delay_ms):
    """When a retry scheduled at `now_ms` becomes eligible. Computed ONCE.

    The result is written into the TaskRetryScheduled payload and copied from
    there forever after. It is never recomputed during projection or replay --
    a recomputed eligibility would be a NEW deadline, which would make a crash
    visible in the rebuilt state and break ADR-012 D-05.
    """
    return now_ms + delay_ms


def is_eligible(eligible_at_ms, now_ms):
    """True when a scheduled retry may be released.

    `>=`, so a zero backoff releases at once and a retry released exactly at
    its eligibility instant is on time rather than early.
    """
    return now_ms >= eligible_at_ms

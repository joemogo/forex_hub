#!/usr/bin/env python3
"""MOGO Automation Platform -- local worker execution.

AUTHORITY
    Automation Platform Constitution v1.0 (senior) -- sections 4.4, 4.5, 7
    MOGO-009 Architecture, sections 6.4, 6.8
    MOGO-011 Step 1 plan, section 12

A WORKER REPORTS; IT DOES NOT TRANSITION
    Constitution section 7, verbatim: "A worker reports state; it does not
    transition state. Only the orchestrator writes task state." This module
    therefore returns a WorkerResult and touches nothing else. It opens no
    database connection, appends no event, and holds no reference to the log.
    That is not an accident of implementation -- it is the boundary, and it is
    enforced by the fact that nothing here is passed a connection or a log.

A WORKER NEVER CALLS A WORKER
    Constitution section 4.4 admits no exception, "including through shared
    libraries, adapters, or subprocess invocation". execute_task() invokes one
    capability callable and returns. There is no dispatch, no lookup and no
    recursion available to it.
"""

from ..contracts import errors as contract_errors  # noqa: E402
from . import errors as runtime_errors  # noqa: E402


class WorkerResult(object):
    """What the worker observed. The orchestrator decides what it means."""

    __slots__ = ("succeeded", "result", "error_class", "error_message",
                 "declared_by_capability", "violation")

    def __init__(self, succeeded, result=None, error_class=None, error_message=None,
                 declared_by_capability=False, violation=None):
        self.succeeded = succeeded
        self.result = result
        self.error_class = error_class
        self.error_message = error_message
        # Distinguishes a failure the capability DECLARED from one the worker
        # classified because the capability escaped unclassified. An operator
        # needs that distinction and cannot otherwise see it.
        self.declared_by_capability = declared_by_capability
        # Set when the capability broke its own contract. Recorded in
        # capability_violations by the orchestrator; the worker only observes.
        self.violation = violation

    def __repr__(self):
        return "WorkerResult(succeeded=%r, error_class=%r, declared=%r)" % (
            self.succeeded, self.error_class, self.declared_by_capability)


UNDECLARED_FAILURE_CLASS = "undeclared_failure_class"

# The class a failure is recorded as when the capability had no right to the one
# it asked for. Non-retryable by Catalog section K, which is the point.
FALLBACK_ERROR_CLASS = "deterministic_processing"


def execute_task(capability_callable, payload, context=None,
                 declared_failure_classes=()):
    """Run one capability against one payload and report the outcome.

    Every failure is classified into an approved Catalog section K error class,
    because Constitution section 6.6 forbids a path that ends without a
    recorded outcome, and an unclassified failure cannot be recorded usefully.

    A capability may report a DECLARED operational failure by raising
    CapabilityFailure with a Catalog section K class. The class is accepted only
    if it is a real section K name AND appears in the capability's manifest --
    Constitution section 7, "a worker may not emit an event it has not
    declared", applied to failure classes. An undeclared class is a VIOLATION,
    not a failure: it is recorded, and the task fails as
    `deterministic_processing`, which is non-retryable. Accepting an undeclared
    class would let a capability grant itself retryability it was never
    approved for.

    Everything else is classified as before: a validation-shaped failure is
    `validation`, anything else is `deterministic_processing`. Neither is
    retryable, because a pure function that failed once on an input will fail
    again on the same input.

    `context` is the EXECUTION CONTEXT -- attempt number and the like. It is
    passed only to a capability that declared it needs one, it is deliberately
    NOT part of the command payload, and it is therefore never part of the
    idempotency key (Constitution section 11: keys are never derived from
    timestamps or attempt numbers).
    """
    try:
        result = (capability_callable(payload, context) if context is not None
                  else capability_callable(payload))
    except runtime_errors.CapabilityFailure as exc:
        if exc.error_class not in contract_errors.ERROR_CLASS_NAMES:
            return WorkerResult(
                False, error_class=FALLBACK_ERROR_CLASS,
                error_message="capability reported error class %r, which is not "
                              "a Contract Catalog section K class: %s"
                              % (exc.error_class, exc.message),
                violation=(UNDECLARED_FAILURE_CLASS, exc.error_class))
        if exc.error_class not in declared_failure_classes:
            return WorkerResult(
                False, error_class=FALLBACK_ERROR_CLASS,
                error_message="capability reported error class %r, which it did "
                              "not declare in its manifest (declared: %s): %s"
                              % (exc.error_class, list(declared_failure_classes),
                                 exc.message),
                violation=(UNDECLARED_FAILURE_CLASS, exc.error_class))
        return WorkerResult(False, error_class=exc.error_class,
                            error_message=exc.message,
                            declared_by_capability=True)
    except runtime_errors.ContractValidationError as exc:
        return WorkerResult(False, error_class="validation", error_message=str(exc))
    except runtime_errors.PlatformError as exc:
        return WorkerResult(False, error_class=FALLBACK_ERROR_CLASS,
                            error_message=str(exc))
    except Exception as exc:  # noqa: BLE001 - a worker must never escape unclassified
        return WorkerResult(False, error_class=FALLBACK_ERROR_CLASS,
                            error_message="%s: %s" % (type(exc).__name__, exc))
    return WorkerResult(True, result=result)

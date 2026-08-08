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

from . import errors as runtime_errors  # noqa: E402


class WorkerResult(object):
    """What the worker observed. The orchestrator decides what it means."""

    __slots__ = ("succeeded", "result", "error_class", "error_message")

    def __init__(self, succeeded, result=None, error_class=None, error_message=None):
        self.succeeded = succeeded
        self.result = result
        self.error_class = error_class
        self.error_message = error_message

    def __repr__(self):
        return "WorkerResult(succeeded=%r, error_class=%r)" % (
            self.succeeded, self.error_class)


def execute_task(capability_callable, payload):
    """Run one capability against one payload and report the outcome.

    Every failure is classified into an approved Catalog section K error class,
    because Constitution section 6.6 forbids a path that ends without a
    recorded outcome, and an unclassified failure cannot be recorded usefully.

    A validation-shaped failure (bad payload, exceeded resource limit) is
    `validation`; anything else is `deterministic_processing`, which is the
    approved class for a failure that will recur identically on a retry. No
    failure here is classed retryable, because a pure function that failed once
    will fail again with the same input.
    """
    try:
        result = capability_callable(payload)
    except runtime_errors.ContractValidationError as exc:
        return WorkerResult(False, error_class="validation", error_message=str(exc))
    except runtime_errors.PlatformError as exc:
        return WorkerResult(False, error_class="deterministic_processing",
                            error_message=str(exc))
    except Exception as exc:  # noqa: BLE001 - a worker must never escape unclassified
        return WorkerResult(False, error_class="deterministic_processing",
                            error_message="%s: %s" % (type(exc).__name__, exc))
    return WorkerResult(True, result=result)

#!/usr/bin/env python3
"""MOGO Automation Platform -- runtime error taxonomy.

AUTHORITY
    Automation Platform Constitution v1.0 (senior) -- sections 11, 16
    MOGO-009 Contract Catalog, section K           -- operational error classes
    MOGO-011 Step 1 plan

WHY THIS MODULE EXISTS (deviation from the plan's file list, disclosed)
    The Step 1 plan placed RuntimeBusyError in store.py. Implementation showed
    the runtime needs a taxonomy, not one exception: path escape, log
    corruption, torn tail, replay divergence, capability ineligibility and
    schema-version refusal are distinct failure modes that callers must be able
    to tell apart. Scattering them across the modules that happen to raise them
    would be architectural debt, so they live together here -- exactly as the
    contracts layer keeps its taxonomy in contracts/errors.py.

    Every class descends from contracts.errors.PlatformError, so the runtime and
    contract hierarchies are one tree and a caller can catch PlatformError to
    mean "the platform refused".

FAIL-CLOSED
    Every error here is raised INSTEAD of proceeding. None is advisory, none is
    recoverable by retry inside Step 1, and none is raised after a partial
    mutation: the raise always precedes the write it would have guarded.
"""

from ..contracts import errors as contract_errors  # noqa: E402

# Re-exported so runtime callers need only one import to catch platform failures.
PlatformError = contract_errors.PlatformError
ContractValidationError = contract_errors.ContractValidationError
IdentifierError = contract_errors.IdentifierError
IllegalTaskTransitionError = contract_errors.IllegalTaskTransitionError
LateTransitionAnomaly = contract_errors.LateTransitionAnomaly


class RuntimeError_(PlatformError, RuntimeError):
    """Root of every failure raised by the runtime kernel."""


class PathEscapeError(RuntimeError_):
    """A write was attempted outside the runtime state root.

    The confinement rule of MOGO-011 Step 1: the runtime may write only inside
    its state root. Raised before the write, never after.
    """


class RuntimeBusyError(RuntimeError_):
    """Another runtime process holds the exclusive lock.

    Step 1 is single-writer by construction (plan section 12). A second runner
    fails here rather than contending, which is what removes the need for a
    time-based lease.
    """


class SchemaVersionError(RuntimeError_):
    """The stored schema version is not one this build can operate on.

    A stored version HIGHER than this build supports is refused outright: a
    downgrade could silently drop columns a newer build depends on.
    """


class LogCorruptionError(RuntimeError_):
    """The authoritative event log failed verification away from its tail.

    A payload-hash mismatch, an unparsable line, or a broken per-workflow
    sequence anywhere other than the final line is corruption of committed
    history. The runtime HALTS -- it does not repair, truncate or skip.
    """


class TornTailError(RuntimeError_):
    """The final log line is an incomplete append.

    Not corruption: an event is committed only when its complete
    newline-terminated line is durable, so a torn fragment never became an
    event. Handled by quarantine-then-truncate (plan section 13.2), never by
    deletion.
    """


class ReplayDivergenceError(RuntimeError_):
    """Replaying the log disagreed with the derived index.

    The log is authoritative; a disagreement means the index is wrong. Raised
    rather than silently preferring either side.
    """


class CapabilityNotDispatchableError(RuntimeError_):
    """A capability failed one of the Catalog section O dispatch conditions.

    Registered, enabled, lifecycle in {approved, production}, command type
    accepted, command version compatible. Any failure is fail-closed: nothing
    executes.
    """


class SimulatedCrash(BaseException):
    """Test-only induced interruption.

    Derives from BaseException, NOT Exception, so an `except Exception` in the
    runtime cannot accidentally swallow an induced crash and make a recovery
    test pass for the wrong reason. Only ever raised when
    MOGO_RUNTIME_ALLOW_CRASH_SIM=1 is set.
    """


def fail(message, error_cls=RuntimeError_):
    """Raise `error_cls` with `message`. The single raise site for the runtime."""
    raise error_cls(message)

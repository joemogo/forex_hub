#!/usr/bin/env python3
"""MOGO Automation Platform -- Step 1 error taxonomy and inert error-class table.

AUTHORITY
    Automation Platform Constitution v1.0 (senior)  -- sections 11, 16
    ADR-012 (accepted 2026-08-07)
    MOGO-009 Contract Catalog, section K            -- error classification

SCOPE -- MOGO-010 Step 1.

IMPLEMENTED NOW
    * The Step 1 exception hierarchy.
    * The canonical raisers used by every Step 1 validator. Routing every
      failure through these keeps the message format uniform and guarantees
      that a failure always names the field or invariant that failed.
    * ERROR_CLASSES: Contract Catalog section K transcribed as inert,
      read-only data.

STRUCTURALLY PREPARED
    * ERROR_CLASSES is shaped for the retry/dead-letter/review machinery of a
      later step. Nothing in Step 1 consumes it.

EXPLICITLY DEFERRED -- absent from Step 1 entirely
    * Retry scheduling, backoff, jitter, attempt counting.
    * Dead-letter handling.
    * Review routing.
    * Any consumer of ERROR_CLASSES. The Constitution (section 11) forbids
      retrying `policy_blocked`; that fact is recorded here as DATA ONLY. No
      code in Step 1 reads this table to make a decision, because no component
      exists that could act on one.

Validation-shaped failures derive additionally from ValueError and structural
failures from RuntimeError, matching the exception convention already used
throughout the Phase I pipeline (for example EvidenceValidationError(ValueError)
and IllegalTransitionError(ValueError)). The convention is adopted; the
pipeline itself is neither imported nor referenced by path -- see
boundaries.PROHIBITED_SOURCE_TREES.
"""

from types import MappingProxyType

# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


class PlatformError(Exception):
    """Root of every error raised by automation platform code."""


class ContractValidationError(PlatformError, ValueError):
    """A contract payload is structurally invalid.

    Raised for: a missing required field, a wrong type, a value outside a
    closed vocabulary, or a payload hash that does not match its payload.
    """


class UnsupportedContractVersionError(PlatformError, ValueError):
    """A contract declares a major version this build does not implement.

    Deliberately distinct from ContractValidationError so a caller can
    distinguish "I do not speak this version" from "this is malformed".
    """


class IdentifierError(PlatformError, ValueError):
    """An identifier is malformed, or an identifier invariant was broken.

    Covers: bad format, an illegal composite component, an unknown
    idempotency operation, a missing or undeclared idempotency part, and a
    duplicate opaque identifier reported by a supplied uniqueness source.
    """

    def __init__(self, message, routes_to_review=False):
        PlatformError.__init__(self, message)
        # Inert metadata only. Constitution section 9 makes identity conflict a
        # blocking human review; no review system exists in Step 1, so this
        # flag is recorded and never acted upon.
        self.routes_to_review = bool(routes_to_review)


class InvariantViolationError(PlatformError, RuntimeError):
    """A rule that must hold structurally does not.

    The canonical case is a content-derived identifier collision over
    differing bytes -- a corruption alarm, never a rename
    (MOGO-009 Architecture section 17).
    """


class ProtectedBoundaryViolationError(PlatformError, RuntimeError):
    """A prohibited cross-context reference or write target was detected.

    See MOGO-009 Architecture section 7 and platform_boundaries.
    """


class ConfigurationError(PlatformError, RuntimeError):
    """Platform configuration is absent, contradictory, or names an
    undeclared resource."""


class InternalPlatformError(PlatformError, RuntimeError):
    """A defect in the platform itself. Never raised for caller input."""


class IllegalTaskTransitionError(PlatformError, ValueError):
    """A task-state transition that is absent from the approved table.

    Mirrors the existing acquisition_common.IllegalTransitionError convention:
    raised without mutating anything.
    """


class LateTransitionAnomaly(PlatformError, RuntimeError):
    """A transition arriving at an already-terminal task.

    Contract Catalog section C: such transitions are "logged as anomalies and
    NOT applied". Step 1 classifies them. Logging is DEFERRED -- no log exists.
    """


# ---------------------------------------------------------------------------
# Canonical raisers
# ---------------------------------------------------------------------------


def fail(message, error_cls=ContractValidationError):
    """Raise `error_cls` with `message`. The single raise site for Step 1."""
    raise error_cls(message)


def require_mapping(value, field, error_cls=ContractValidationError):
    """Require a mapping. Returns the value unchanged."""
    # Accept only real mappings; a list or string must never be treated as an
    # envelope. `isinstance(value, dict)` is too narrow for MappingProxyType,
    # which is what this platform hands back from its validators.
    if not hasattr(value, "keys") or not hasattr(value, "__getitem__"):
        fail("%s must be a mapping, got %s" % (field, type(value).__name__), error_cls)
    return value


def require_present(mapping, field, error_cls=ContractValidationError):
    """Require `field` to be present and not None. Returns the value."""
    if field not in mapping:
        fail("required field %s is missing" % (field,), error_cls)
    value = mapping[field]
    if value is None:
        fail("required field %s must not be null" % (field,), error_cls)
    return value


def require_str(value, field, allow_empty=False, error_cls=ContractValidationError):
    """Require a string. Returns the value."""
    if not isinstance(value, str):
        fail("%s must be a string, got %s" % (field, type(value).__name__), error_cls)
    if not allow_empty and not value.strip():
        fail("%s must be a non-empty string" % (field,), error_cls)
    return value


def require_int(value, field, minimum=None, maximum=None,
                error_cls=ContractValidationError):
    """Require an int (bool is rejected -- it is an int subclass in Python)."""
    if isinstance(value, bool) or not isinstance(value, int):
        fail("%s must be an integer, got %s" % (field, type(value).__name__), error_cls)
    if minimum is not None and value < minimum:
        fail("%s must be >= %d, got %d" % (field, minimum, value), error_cls)
    if maximum is not None and value > maximum:
        fail("%s must be <= %d, got %d" % (field, maximum, value), error_cls)
    return value


def require_list(value, field, error_cls=ContractValidationError):
    """Require a list or tuple. Returns the value."""
    if not isinstance(value, (list, tuple)):
        fail("%s must be an array, got %s" % (field, type(value).__name__), error_cls)
    return value


def require_member(value, field, allowed, error_cls=ContractValidationError):
    """Require membership in a closed vocabulary. Returns the value."""
    if value not in allowed:
        fail("%s value %r is not in the approved vocabulary" % (field, value), error_cls)
    return value


# ---------------------------------------------------------------------------
# Contract Catalog section K -- inert operational error classification
# ---------------------------------------------------------------------------

def _class_record(retryable, terminal, routes_to_review):
    return MappingProxyType({
        "retryable": retryable,
        "terminal": terminal,
        "routesToReview": routes_to_review,
    })


ERROR_CLASSES = MappingProxyType({
    "transient":                _class_record(True,  False, False),
    "rate_limited":             _class_record(True,  False, False),
    "dependency_unavailable":   _class_record(True,  False, False),
    "authentication":           _class_record(False, True,  True),
    # Constitution section 11: retrying a policy denial is an attempt to
    # launder it. Never retryable, under any condition.
    "policy_blocked":           _class_record(False, True,  True),
    "not_found":                _class_record(False, True,  False),
    "source_mutated":           _class_record(False, False, True),
    "validation":               _class_record(False, True,  False),
    "deterministic_processing": _class_record(False, True,  True),
    "corrupted_input":          _class_record(False, True,  True),
    "human_review_required":    _class_record(False, False, True),
    "permanent":                _class_record(False, True,  False),
})

ERROR_CLASS_NAMES = tuple(ERROR_CLASSES.keys())

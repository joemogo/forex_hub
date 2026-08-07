#!/usr/bin/env python3
"""MOGO Automation Platform -- Step 1 operational event envelope contract.

AUTHORITY
    Automation Platform Constitution v1.0 (senior)  -- section 6, section 6.8
    ADR-012 (accepted 2026-08-07)                   -- D-04, approval 3
    MOGO-009 Architecture, section 11    -- event model
    MOGO-009 Contract Catalog, section B -- event contract (19 fields)

OPERATIONAL, NEVER SCIENTIFIC
    Constitution section 6.8 requires operational events to be stored
    separately from trading decision events and from every scientific ledger,
    "with their own namespace, store and identifier space". Step 1 establishes
    the namespace and the identifier space. There is no store yet, and this
    module can neither reach nor describe a scientific record: a prohibited
    reference anywhere in an envelope or its payload is rejected outright.

IMMUTABILITY
    A validated event is returned deeply read-only. Constitution section 6.1:
    events are "never updated, never deleted". This module therefore exposes
    NO mutator, updater, deleter, setter or patcher -- and a test asserts that
    no such function appears on its public surface.

IMPLEMENTED NOW
    * Structural construction and validation of an event envelope.
    * Full payload-hash verification. Unlike a command, an event carries its
      payload, so the digest is always recomputed and a mismatch is rejected.
    * Deep read-only return value.

STRUCTURALLY PREPARED
    * `sequence` is validated as a non-negative integer, ready for the ordering
      guarantee a later step will enforce.

EXPLICITLY DEFERRED -- NOT implemented, and NOT claimed
    * NOTHING IS PERSISTED, APPENDED OR EMITTED. No event store, no log, no
      index, no file. Building an envelope records nothing anywhere.
    * SEQUENCE MONOTONICITY IS NOT ENFORCED. Catalog section B requires
      `sequence` to be monotonic within a workflow. That is a property of a
      log, and no log exists; only the value's type and range are checked.
    * PER-SUBJECT CHAINING IS NOT VERIFIED. `priorEventId` is validated as a
      UUIDv4 when present; that it names the real previous event for the
      subject cannot be checked without a log.
    * DUPLICATE DETECTION AND CORRUPTION-CHAIN REPLAY are deferred with the
      log that would make them possible.
    * PAYLOAD SEMANTICS ARE NOT INTERPRETED. The Catalog defines no payload
      shape for any event type. The payload is canonically hashed and carried;
      its meaning is never inferred.
    * POLICY IS NOT EVALUATED. policyContext is structural only.
"""

import re
from types import MappingProxyType

from . import boundaries  # noqa: E402
from . import errors  # noqa: E402
from . import ids  # noqa: E402
from . import vocabulary  # noqa: E402

# Catalog section B declares no schemaVersion field on the envelope itself, so
# the operational namespace is carried by the contract's identity rather than
# by a field. Recorded here, and asserted by test, as the structural separator
# from every trading and scientific schema identifier.
EVENT_SCHEMA_VERSION = vocabulary.OPERATIONAL_NAMESPACE + ".event.v1"

# Contract Catalog section B. 14 required, 5 optional, 19 total.
EVENT_REQUIRED_FIELDS = (
    "eventId",
    "eventType",
    "eventVersion",
    "workflowId",
    "correlationId",
    "causationId",
    "producer",
    "producerVersion",
    "occurredAt",
    "recordedAt",
    "subjectRefs",
    "payload",
    "payloadHash",
    "sequence",
)

EVENT_OPTIONAL_FIELDS = (
    "taskId",
    "priorEventId",
    "policyContext",
    "executionResult",
    "errorClass",
)

EVENT_FIELDS = EVENT_REQUIRED_FIELDS + EVENT_OPTIONAL_FIELDS

SUPPORTED_EVENT_MAJORS = (1,)

# Catalog section B: `worker:<id>` | `orchestrator` | `policyGate` | `reviewGate`
PRODUCER_LITERALS = ("orchestrator", "policyGate", "reviewGate")
PRODUCER_PREFIXES = ("worker:",)

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def _validate_producer(value):
    errors.require_str(value, "producer")
    if value in PRODUCER_LITERALS:
        return value
    for prefix in PRODUCER_PREFIXES:
        if value.startswith(prefix) and value[len(prefix):].strip():
            return value
    errors.fail(
        "producer must be one of %s, or %s<id>; got %r"
        % (list(PRODUCER_LITERALS), PRODUCER_PREFIXES[0], value)
    )


def _validate_producer_version(value):
    errors.require_str(value, "producerVersion")
    if not SEMVER_RE.match(value):
        errors.fail("producerVersion must be semver major.minor.patch, got %r" % (value,))
    return value


def _validate_subject_refs(value):
    refs = errors.require_list(value, "subjectRefs")
    for index, ref in enumerate(refs):
        errors.require_str(ref, "subjectRefs[%d]" % (index,))
    return refs


def _validate_policy_context(value):
    """Structural only -- no authorization decision is made here."""
    errors.require_mapping(value, "policyContext")
    return value


def event_payload_hash(payload):
    """Canonical SHA-256 over an event payload.

    Unknown payload fields are hashed exactly as supplied, never stripped:
    dropping them would change this digest and break verification for a
    consumer running an older minor.
    """
    return ids.content_hash_of(payload)


def build_event(**fields):
    """Assemble and validate an operational event envelope.

    Records nothing anywhere. There is no store to record into.
    """
    return validate_event(dict(fields))


def validate_event(envelope):
    """Validate an operational event envelope. Never mutates caller input.

    Returns a deeply read-only normalized copy. Unknown fields are preserved
    verbatim and ignored for semantic purposes only.
    """
    errors.require_mapping(envelope, "event envelope")
    normalized = dict(envelope)

    for name in EVENT_REQUIRED_FIELDS:
        errors.require_present(normalized, name)

    version = errors.require_int(normalized["eventVersion"], "eventVersion", minimum=1)
    if version not in SUPPORTED_EVENT_MAJORS:
        errors.fail(
            "eventVersion %d is not supported by this build (supported: %s)"
            % (version, list(SUPPORTED_EVENT_MAJORS)),
            errors.UnsupportedContractVersionError,
        )

    # Admissibility before semantics -- see the equivalent note in command.py.
    # The event payload is a required field, so this single call covers the
    # envelope and its payload together.
    ids.require_json_shaped(normalized, "$event")

    ids.require_uuid4(normalized["eventId"], "eventId")
    ids.require_uuid4(normalized["workflowId"], "workflowId")
    ids.require_uuid4(normalized["correlationId"], "correlationId")
    ids.require_uuid4(normalized["causationId"], "causationId")
    if normalized.get("taskId") is not None:
        ids.require_uuid4(normalized["taskId"], "taskId")
    if normalized.get("priorEventId") is not None:
        ids.require_uuid4(normalized["priorEventId"], "priorEventId")

    errors.require_member(normalized["eventType"], "eventType", vocabulary.EVENT_TYPES)
    _validate_producer(normalized["producer"])
    _validate_producer_version(normalized["producerVersion"])
    ids.require_iso8601_utc_ms(normalized["occurredAt"], "occurredAt")
    ids.require_iso8601_utc_ms(normalized["recordedAt"], "recordedAt")
    _validate_subject_refs(normalized["subjectRefs"])
    errors.require_mapping(normalized["payload"], "payload")
    ids.require_sha256_hex(normalized["payloadHash"], "payloadHash")
    # DEFERRED: monotonicity within the workflow requires a log. Only the
    # value's type and range are checked here.
    errors.require_int(normalized["sequence"], "sequence", minimum=0)

    if normalized.get("policyContext") is not None:
        _validate_policy_context(normalized["policyContext"])

    execution_result = normalized.get("executionResult")
    if execution_result is not None:
        errors.require_member(execution_result, "executionResult",
                              vocabulary.EXECUTION_RESULTS)
    error_class = normalized.get("errorClass")
    if error_class is not None:
        errors.require_member(error_class, "errorClass", errors.ERROR_CLASS_NAMES)
    if execution_result == "failure" and error_class is None:
        errors.fail("errorClass is required when executionResult is 'failure'")

    found = boundaries.find_prohibited_references(normalized, "$event")
    if found:
        location, value, reason = found[0]
        errors.fail(
            "prohibited reference at %s (%r): %s" % (location, value, reason),
            errors.ProtectedBoundaryViolationError,
        )

    actual = event_payload_hash(normalized["payload"])
    if actual != normalized["payloadHash"]:
        errors.fail(
            "payloadHash mismatch: envelope declares %s, payload hashes to %s"
            % (normalized["payloadHash"], actual)
        )

    return ids.freeze(normalized)


# Re-exported for callers that need the plain form for serialization. This is
# the read direction only; there is deliberately no function anywhere in this
# module that changes a validated event.
as_plain = ids.as_plain

TRADING_AND_SCIENTIFIC_SEPARATION = MappingProxyType({
    "namespace": vocabulary.OPERATIONAL_NAMESPACE,
    "schemaVersion": EVENT_SCHEMA_VERSION,
    "note": (
        "Operational events share no store, schema registry or identifier "
        "space with trading decision events or scientific records "
        "(Constitution section 6.8)."
    ),
})

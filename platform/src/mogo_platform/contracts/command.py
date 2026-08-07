#!/usr/bin/env python3
"""MOGO Automation Platform -- Step 1 command envelope contract.

AUTHORITY
    Automation Platform Constitution v1.0 (senior)
    ADR-012 (accepted 2026-08-07)
    MOGO-009 Architecture, section 10    -- command model
    MOGO-009 Contract Catalog, section A -- command contract (18 fields)

IMPLEMENTED NOW
    * Structural construction and validation of a command envelope: field
      presence, types, identifier formats, timestamp format, closed-vocabulary
      membership, approved defaults, unknown-field preservation, and rejection
      of a prohibited reference.
    * Distinct rejection of an unsupported major version.
    * Payload-hash verification when the caller supplies the payload.

STRUCTURALLY PREPARED
    * targetCapability is required and syntactically validated, so the
      Capability Registry step has a validated value to resolve.

EXPLICITLY DEFERRED -- NOT implemented, and NOT claimed
    * CAPABILITY REGISTRATION IS NOT CHECKED. Contract Catalog section A notes
      that targetCapability "must exist in the worker registry". No registry
      exists in Step 1, and none is simulated, stubbed or hard-coded here.
      Validation confirms SYNTAX ONLY. Registration verification is deferred
      to the separately approved Capability Registry implementation step
      (ADR-012 D-16).
    * COMMAND REJECTION EVENTS ARE NOT EMITTED. Catalog section A states that
      a hash mismatch "is a rejection, and the rejection is an event". Step 1
      raises the typed error; emitting the event requires an event store,
      which does not exist.
    * PAYLOAD SEMANTICS ARE NOT INTERPRETED. The Catalog defines no payload
      shape for any command type. A supplied payload is canonically hashed and
      compared; its content is never interpreted or validated.
    * POLICY IS NOT EVALUATED. policyContext is validated structurally. No
      authorization decision is made, and no policy gate exists.
    * NO COMMAND IS DISPATCHED, ROUTED, QUEUED OR EXECUTED.

KNOWN CONTRACT AMBIGUITY, SURFACED RATHER THAN HIDDEN
    Catalog section A types targetCapability as "string" and does not fix its
    form. Two forms are attested in the approved documents: the dotted
    capability name in Architecture section 26 (for example the v1 acquisition
    capability) and the CAP|<domain>|<name> composite in Catalog section O.
    Step 1 accepts EITHER, validating each strictly, and invents no third
    form. Governance should fix a single canonical form before the Capability
    Registry step; until then this validator is deliberately permissive across
    exactly the two attested forms and strict within each.
"""

from types import MappingProxyType

from . import boundaries  # noqa: E402
from . import errors  # noqa: E402
from . import ids  # noqa: E402
from . import vocabulary  # noqa: E402

COMMAND_SCHEMA_VERSION = vocabulary.OPERATIONAL_NAMESPACE + ".command.v1"

# Contract Catalog section A. 13 required, 5 optional, 18 total.
COMMAND_REQUIRED_FIELDS = (
    "commandId",
    "commandType",
    "commandVersion",
    "workflowId",
    "correlationId",
    "causationId",
    "idempotencyKey",
    "issuedAt",
    "issuedBy",
    "targetCapability",
    "inputRefs",
    "policyContext",
    "payloadHash",
)

COMMAND_OPTIONAL_FIELDS = (
    "taskId",
    "priority",
    "attemptLimit",
    "timeoutMs",
    "approvalRequirements",
)

COMMAND_FIELDS = COMMAND_REQUIRED_FIELDS + COMMAND_OPTIONAL_FIELDS

# Catalog section A: priority default 5, attemptLimit default 3.
COMMAND_DEFAULTS = MappingProxyType({
    "priority": 5,
    "attemptLimit": 3,
})

# Additive-only within a major. A breaking change is a new type, never a new
# version of an old one (Architecture section 11).
SUPPORTED_COMMAND_MAJORS = (1,)

# Catalog section A: `operator:<id>` | `orchestrator` | `workflow:<type>`
ISSUED_BY_LITERAL = "orchestrator"
ISSUED_BY_PREFIXES = ("operator:", "workflow:")

POLICY_CONTEXT_FIELDS = ("authorizationId", "policyVersion", "permittedOperations")


def _validate_issued_by(value):
    errors.require_str(value, "issuedBy")
    if value == ISSUED_BY_LITERAL:
        return value
    for prefix in ISSUED_BY_PREFIXES:
        if value.startswith(prefix) and value[len(prefix):].strip():
            return value
    errors.fail(
        "issuedBy must be %r, or %s<id>, or %s<type>; got %r"
        % (ISSUED_BY_LITERAL, ISSUED_BY_PREFIXES[0], ISSUED_BY_PREFIXES[1], value)
    )


def _validate_target_capability(value):
    """Validate SYNTAX ONLY. Registration is not checked -- see module docstring."""
    errors.require_str(value, "targetCapability")
    if value.startswith("CAP" + ids.COMPOSITE_SEPARATOR):
        ids.require_composite_id(value, "CAP", "targetCapability")
        return value
    if not ids.COMPONENT_RE.match(value):
        errors.fail(
            "targetCapability must be a CAP composite identifier or a lowercase "
            "dotted capability name, got %r" % (value,)
        )
    return value


def _validate_policy_context(value):
    """Structural validation only. No authorization decision is made."""
    errors.require_mapping(value, "policyContext")
    for name in POLICY_CONTEXT_FIELDS:
        if name not in value:
            errors.fail("policyContext.%s is missing" % (name,))
    authorization_id = value["authorizationId"]
    if authorization_id is not None:
        errors.require_str(authorization_id, "policyContext.authorizationId")
    errors.require_str(value["policyVersion"], "policyContext.policyVersion")
    operations = errors.require_list(
        value["permittedOperations"], "policyContext.permittedOperations"
    )
    for index, operation in enumerate(operations):
        errors.require_str(
            operation, "policyContext.permittedOperations[%d]" % (index,)
        )
    return value


def _validate_refs(value, field):
    refs = errors.require_list(value, field)
    for index, ref in enumerate(refs):
        errors.require_str(ref, "%s[%d]" % (field, index))
    return refs


def command_payload_hash(payload):
    """Canonical SHA-256 over a command payload.

    Unknown payload fields are hashed exactly as supplied. They are never
    stripped, because dropping them would change this digest and break hash
    verification for a consumer running an older minor.
    """
    return ids.content_hash_of(payload)


def build_command(**fields):
    """Assemble and validate a command envelope from keyword fields.

    Applies the approved defaults, then validates. Returns the same read-only
    envelope validate_command() returns.
    """
    envelope = dict(fields)
    for name, default in COMMAND_DEFAULTS.items():
        if name not in envelope:
            envelope[name] = default
    return validate_command(envelope)


def validate_command(envelope, payload=None, verify_payload_hash=False):
    """Validate a command envelope. Never mutates the caller's input.

    Returns a deeply read-only normalized copy. Unknown fields are preserved
    verbatim; they are ignored for semantic purposes only.

    `payload` and `verify_payload_hash`: Catalog section A defines payloadHash
    as being "over the canonical payload" but declares NO payload field on the
    command envelope, so the envelope alone cannot verify its own hash. When a
    caller supplies the payload, the digest is recomputed and a mismatch is
    rejected. With no payload supplied, only the FORM of payloadHash is
    checked -- and this function does not claim otherwise.
    """
    errors.require_mapping(envelope, "command envelope")
    normalized = dict(envelope)

    for name in COMMAND_REQUIRED_FIELDS:
        errors.require_present(normalized, name)

    # Version first: an unsupported major must fail distinctly, before any
    # field is interpreted under rules that may not apply to it.
    version = errors.require_int(normalized["commandVersion"], "commandVersion",
                                 minimum=1)
    if version not in SUPPORTED_COMMAND_MAJORS:
        errors.fail(
            "commandVersion %d is not supported by this build (supported: %s)"
            % (version, list(SUPPORTED_COMMAND_MAJORS)),
            errors.UnsupportedContractVersionError,
        )

    # Admissibility before semantics: prove the WHOLE envelope is JSON-shaped
    # before any field is interpreted, before prohibited-reference scanning,
    # before hashing and before freezing. An unknown additive field carrying a
    # value with no JSON form is rejected here rather than surviving into a
    # record that cannot be serialized (MOGO-010 Step 1 correction I-2/3/4).
    ids.require_json_shaped(normalized, "$command")
    if payload is not None:
        ids.require_json_shaped(payload, "$payload")

    ids.require_uuid4(normalized["commandId"], "commandId")
    ids.require_uuid4(normalized["workflowId"], "workflowId")
    ids.require_uuid4(normalized["correlationId"], "correlationId")
    ids.require_uuid4(normalized["causationId"], "causationId")
    if normalized.get("taskId") is not None:
        ids.require_uuid4(normalized["taskId"], "taskId")

    errors.require_member(normalized["commandType"], "commandType",
                          vocabulary.COMMAND_TYPES)
    ids.require_sha256_hex(normalized["idempotencyKey"], "idempotencyKey")
    ids.require_sha256_hex(normalized["payloadHash"], "payloadHash")
    ids.require_iso8601_utc_ms(normalized["issuedAt"], "issuedAt")
    _validate_issued_by(normalized["issuedBy"])
    _validate_target_capability(normalized["targetCapability"])
    _validate_refs(normalized["inputRefs"], "inputRefs")
    _validate_policy_context(normalized["policyContext"])

    if "priority" in normalized:
        errors.require_int(normalized["priority"], "priority", minimum=0, maximum=9)
    if "attemptLimit" in normalized:
        errors.require_int(normalized["attemptLimit"], "attemptLimit", minimum=1)
    if "timeoutMs" in normalized:
        errors.require_int(normalized["timeoutMs"], "timeoutMs", minimum=1)
    if "approvalRequirements" in normalized:
        requirements = errors.require_list(
            normalized["approvalRequirements"], "approvalRequirements"
        )
        for index, requirement in enumerate(requirements):
            errors.require_str(requirement, "approvalRequirements[%d]" % (index,))

    _reject_prohibited_references(normalized, payload)

    if verify_payload_hash or payload is not None:
        if payload is None:
            errors.fail(
                "verify_payload_hash requires the payload, which was not supplied"
            )
        actual = command_payload_hash(payload)
        if actual != normalized["payloadHash"]:
            errors.fail(
                "payloadHash mismatch: envelope declares %s, payload hashes to %s"
                % (normalized["payloadHash"], actual)
            )

    return ids.freeze(normalized)


def _reject_prohibited_references(normalized, payload):
    """Reject any prohibited target or reference anywhere in the command.

    Uses the single detector in platform_boundaries so the rule has exactly
    one implementation.
    """
    subjects = [("envelope", normalized)]
    if payload is not None:
        subjects.append(("payload", payload))
    for label, subject in subjects:
        found = boundaries.find_prohibited_references(subject, "$" + label)
        if found:
            location, value, reason = found[0]
            errors.fail(
                "prohibited reference at %s (%r): %s" % (location, value, reason),
                errors.ProtectedBoundaryViolationError,
            )

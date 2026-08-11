#!/usr/bin/env python3
"""MOGO Automation Platform -- Step 1 identifier model and Catalog conventions.

AUTHORITY
    Automation Platform Constitution v1.0 (senior)  -- sections 10, 11
    ADR-012 (accepted 2026-08-07)                   -- D-07, D-11
    MOGO-009 Architecture, section 17               -- identifier model
    MOGO-009 Contract Catalog, conventions header   -- sha256 / uuid / iso8601
    MOGO-009 Contract Catalog, section H            -- identifier classes
    MOGO-009 Contract Catalog, section I            -- idempotency matrix

This module owns the Catalog's *conventions* block (the three shared value
formats: 64-char lowercase hex sha256, UUIDv4, and ISO-8601 UTC at millisecond
precision) together with sections H and I. They are co-located because the
Catalog defines them together and because every other Step 1 contract module
depends on all three; splitting them would duplicate validation logic across
modules, which the Step 1 authorization forbids.

CANONICALIZATION -- ADAPTED, NOT SHARED
    MOGO-009 Architecture section 17 records the verdict: the repository's
    SHA-256 canonicalization *discipline* is "adapted (same algorithm, new
    namespace)". Architecture section 6.7 permits access to the Phase I
    pipeline only through adapters, and no adapter exists in Step 1. The rule
    is therefore re-implemented here rather than imported. A contract test
    proves this module's output is byte-identical to the documented rule while
    asserting the pipeline module was never imported.

IMPLEMENTED NOW
    * Canonical JSON serialization for hashing, and SHA-256 over it.
    * Format predicates and raisers for sha256 / UUIDv4 / ISO-8601 UTC ms.
    * Composite identifier construction, parsing and validation (section H).
    * Idempotency key composition (section I).
    * Content-identity collision handling (Architecture section 17).

STRUCTURALLY PREPARED
    * new_uuid4() accepts an optional `seen` uniqueness source. When one is
      supplied a duplicate is a hard failure, which is how a later step will
      wire in the event log.

EXPLICITLY DEFERRED -- not implemented in Step 1
    * Uniqueness of opaque identifiers against the operational event log.
      Catalog section H requires that check; no event log exists in Step 1, so
      with no `seen` argument NO uniqueness check occurs. This is a real,
      declared gap, not a silent one.
    * Routing a composite identity conflict to human review. The conflict is
      surfaced through inert metadata (IdentifierError.routes_to_review); no
      review system exists to receive it.

GOVERNANCE-OWNED IDENTIFIERS
    hypothesisId, evidencePackageId and replayPackageId are owned by project
    governance. Catalog section H: "the platform never mints these." This
    module therefore exposes NO function that creates one, and no alias that
    indirectly creates one. They may be carried as references.
"""

import hashlib
import json
import math
import re
import uuid as _uuid
from datetime import datetime
from types import MappingProxyType

from . import errors  # noqa: E402  (package-relative; see platform/README.md)

# ---------------------------------------------------------------------------
# Catalog conventions block -- canonicalization and hashing
# ---------------------------------------------------------------------------


def canonical_json_bytes(obj):
    """Canonical serialization used ONLY for hashing.

    Object keys sorted recursively; arrays never reordered (order may carry
    meaning); compact separators; UTF-8; NaN and Infinity rejected.

    The value is routed through as_plain() first so that an ALREADY-VALIDATED
    envelope -- whose mappings are MappingProxyType and whose arrays are
    tuples -- can be hashed and therefore revalidated. as_plain() changes no
    JSON output, so no digest moves: this makes validation idempotent without
    altering payload-hash semantics (MOGO-010 Step 1 correction I-5).

    Raises ContractValidationError if the value is not JSON-serializable or
    contains a non-finite float, so a non-hashable payload fails closed rather
    than producing an unstable digest.
    """
    try:
        text = json.dumps(
            as_plain(obj),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except ValueError as exc:
        # json raises ValueError for NaN/Infinity when allow_nan=False.
        errors.fail("value is not canonically serializable: %s" % (exc,))
    except TypeError as exc:
        errors.fail("value is not JSON-serializable: %s" % (exc,))
    return text.encode("utf-8")


def sha256_hex(data_bytes):
    """SHA-256 of raw bytes, as 64 lowercase hex characters."""
    if not isinstance(data_bytes, (bytes, bytearray)):
        errors.fail("sha256_hex requires bytes, got %s" % (type(data_bytes).__name__,))
    return hashlib.sha256(bytes(data_bytes)).hexdigest()


def content_hash_of(obj):
    """SHA-256 over the canonical serialization of a JSON-shaped value."""
    return sha256_hex(canonical_json_bytes(obj))


# ---------------------------------------------------------------------------
# Canonical value representation -- the in-memory counterpart of the rules above
# ---------------------------------------------------------------------------
# freeze()/as_plain() live beside canonical_json_bytes() because they are the
# same concern: how a platform value is represented. Keeping them here gives
# the command and event contracts one shared implementation instead of two.


def freeze(value):
    """Return a deeply read-only view of a JSON-shaped value.

    Mappings become MappingProxyType and arrays become tuples, so a validated
    envelope cannot be mutated by its caller. Constitution section 6.1:
    operational events are "never updated, never deleted".
    """
    if isinstance(value, (list, tuple)):
        return tuple(freeze(item) for item in value)
    if hasattr(value, "keys"):
        return MappingProxyType({key: freeze(value[key]) for key in value.keys()})
    return value


def as_plain(value):
    """Inverse of freeze(): a mutable, JSON-serializable deep copy.

    Needed because json.dumps cannot serialize MappingProxyType, so hashing
    and round-trip serialization operate on the plain form.
    """
    if isinstance(value, (list, tuple)):
        return [as_plain(item) for item in value]
    if hasattr(value, "keys"):
        return {key: as_plain(value[key]) for key in value.keys()}
    return value


# ---------------------------------------------------------------------------
# JSON-shape validation -- the admissibility rule for every envelope value
# ---------------------------------------------------------------------------
# MOGO-010 Step 1 correction I-2 / I-3 / I-4. Contract Catalog section B
# requires consumers to ignore unknown fields and Architecture section 11
# requires additive evolution -- but neither says an unknown field must be
# REPRESENTABLE. Without that check an envelope could carry a value with no
# JSON form (an arbitrary object, a set, bytes), a value JSON cannot express
# (NaN, Infinity), or a key json.dumps would silently coerce (an int key
# becoming a string). Each breaks a property the platform claims: round-trip
# fidelity, durable-record compatibility, deterministic auditability.
#
# Accepted, exactly the JSON data model:
#     None | bool | int | finite float | str | mapping with string keys |
#     list | tuple
# Read-only mappings (MappingProxyType) and tuples are accepted so that an
# already-validated envelope can be revalidated -- see canonical_json_bytes().


def require_json_shaped(value, field="$"):
    """Prove that `value` is JSON-shaped and canonically serializable.

    Depth-first. Returns the value unchanged and mutates nothing. Raises
    ContractValidationError naming the precise JSON-style path of the first
    offending value, so a failure is actionable without a debugger.

    Recursion follows mappings, lists and tuples ONLY. Arbitrary object
    attributes are never traversed: an unrecognized type is rejected outright
    rather than inspected. Performs no I/O and no serialization.
    """
    _require_json_shaped(value, field)
    return value


def _require_json_shaped(value, path):
    if value is None or isinstance(value, (bool, int, str)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            errors.fail(
                "%s is the non-finite float %r; JSON has no representation for "
                "NaN or Infinity" % (path, value)
            )
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _require_json_shaped(item, "%s[%d]" % (path, index))
        return
    if hasattr(value, "keys") and hasattr(value, "__getitem__"):
        for key in value.keys():
            # bool is a subclass of int and neither is a str, so both are
            # rejected here. Keys are never coerced or stringified.
            if not isinstance(key, str):
                errors.fail(
                    "%s has the non-string key %r of type %s; JSON object keys "
                    "must be strings and are never coerced"
                    % (path, key, type(key).__name__)
                )
            _require_json_shaped(value[key], "%s.%s" % (path, key))
        return
    errors.fail(
        "%s is of type %s, which has no JSON representation"
        % (path, type(value).__name__)
    )


# ---------------------------------------------------------------------------
# Catalog conventions block -- value formats
# ---------------------------------------------------------------------------

SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")

# RFC 4122 version 4, canonical lowercase hyphenated form.
UUID4_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)

# Catalog conventions: iso8601 = UTC, millisecond precision.
ISO8601_UTC_MS_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$"
)


def is_sha256_hex(value):
    """True if `value` is exactly 64 lowercase hex characters."""
    return isinstance(value, str) and bool(SHA256_HEX_RE.match(value))


def require_sha256_hex(value, field):
    """Require a canonical sha256 hex digest. Returns the value."""
    if not is_sha256_hex(value):
        errors.fail(
            "%s must be 64 lowercase hex characters (sha256), got %r" % (field, value),
            errors.IdentifierError,
        )
    return value


def is_uuid4(value):
    """True if `value` is a canonical lowercase hyphenated UUIDv4 string."""
    return isinstance(value, str) and bool(UUID4_RE.match(value))


def require_uuid4(value, field):
    """Require a canonical UUIDv4 string. Returns the value."""
    if not is_uuid4(value):
        errors.fail(
            "%s must be a canonical lowercase UUIDv4, got %r" % (field, value),
            errors.IdentifierError,
        )
    return value


def is_iso8601_utc_ms(value):
    """True if `value` is ISO-8601 UTC at millisecond precision, e.g.
    '2026-08-07T12:00:00.000Z'. The calendar date must also be real."""
    if not isinstance(value, str) or not ISO8601_UTC_MS_RE.match(value):
        return False
    try:
        # The pattern already fixes the zone as UTC; strptime is used only to
        # reject an impossible calendar date or time such as 2026-02-30.
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError:
        return False
    return True


def require_iso8601_utc_ms(value, field):
    """Require an ISO-8601 UTC millisecond timestamp. Returns the value."""
    if not is_iso8601_utc_ms(value):
        errors.fail(
            "%s must be ISO-8601 UTC at millisecond precision "
            "(YYYY-MM-DDThh:mm:ss.sssZ), got %r" % (field, value)
        )
    return value


# ---------------------------------------------------------------------------
# Catalog section H -- opaque execution identifiers
# ---------------------------------------------------------------------------


def new_uuid4(uuid_factory=None, seen=None):
    """Mint an opaque execution identifier.

    `uuid_factory` is a test seam: a zero-argument callable returning a
    uuid.UUID. Whatever it returns is validated, so an injected factory can
    never produce a value that is not a real UUIDv4.

    `seen` is an optional uniqueness source: a callable taking the candidate
    string and returning True if it has been observed before. Supplying one
    makes a duplicate a hard IdentifierError.

    DEFERRED: with `seen` omitted -- which is every caller in Step 1 -- NO
    uniqueness check is performed. Catalog section H requires the check to run
    against the operational event log, and no event log exists yet.
    """
    factory = uuid_factory if uuid_factory is not None else _uuid.uuid4
    candidate = str(factory())
    if not is_uuid4(candidate):
        errors.fail(
            "uuid_factory produced %r, which is not a canonical UUIDv4" % (candidate,),
            errors.IdentifierError,
        )
    if seen is not None and seen(candidate):
        errors.fail(
            "opaque identifier %s is a duplicate" % (candidate,),
            errors.IdentifierError,
        )
    return candidate


# ---------------------------------------------------------------------------
# Catalog section H -- composite human-readable identifiers
# ---------------------------------------------------------------------------

COMPOSITE_SEPARATOR = "|"

# A component: lowercase alphanumeric, with '.', '_' and '-' permitted inside.
# NOTE ON AUTHORITY: Catalog section H specifies composite *structure*
# (the prefix and the ordered components); it does not specify a character
# set. This restriction is a MOGO-010 Step 1 structural decision, adopted from
# the repository's existing lowercase-identifier convention, and is recorded
# here as such rather than presented as a Catalog quotation. It admits the
# capability form used in the architecture (for example "research.acquire.v1")
# and rejects whitespace, emptiness, uppercase and an embedded separator.
COMPONENT_RE = re.compile(r"^[a-z0-9](?:[a-z0-9._-]*[a-z0-9])?$")
HASH12_RE = re.compile(r"^[0-9a-f]{12}$")

_COMPONENT = "component"
_HASH12 = "hash12"

# prefix -> (identifier name, ordered component names, ordered component kinds)
COMPOSITE_ID_SPECS = MappingProxyType({
    "SRC":  ("sourceId",         ("platform", "normalizedUrlHash12"),
             (_COMPONENT, _HASH12)),
    "EDU":  ("educatorId",       ("slug",),               (_COMPONENT,)),
    "CONN": ("connectorId",      ("sourceType", "name"),  (_COMPONENT, _COMPONENT)),
    "WRK":  ("workerId",         ("capability",),         (_COMPONENT,)),
    "XF":   ("transformationId", ("name",),               (_COMPONENT,)),
    "CAP":  ("capabilityId",     ("domain", "name"),      (_COMPONENT, _COMPONENT)),
    "RULE": ("canonicalRuleId",  ("educator", "slug"),    (_COMPONENT, _COMPONENT)),
})

COMPOSITE_PREFIXES = tuple(COMPOSITE_ID_SPECS.keys())


def _require_component(value, kind, prefix, name):
    if not isinstance(value, str):
        errors.fail(
            "%s component %s must be a string, got %s"
            % (prefix, name, type(value).__name__),
            errors.IdentifierError,
        )
    if COMPOSITE_SEPARATOR in value:
        errors.fail(
            "%s component %s must not contain the separator %r"
            % (prefix, name, COMPOSITE_SEPARATOR),
            errors.IdentifierError,
        )
    pattern = HASH12_RE if kind == _HASH12 else COMPONENT_RE
    if not pattern.match(value):
        errors.fail(
            "%s component %s is invalid: %r" % (prefix, name, value),
            errors.IdentifierError,
        )
    return value


def make_composite_id(prefix, components):
    """Build a composite identifier from its prefix and ordered components."""
    if prefix not in COMPOSITE_ID_SPECS:
        errors.fail("unknown composite prefix %r" % (prefix,), errors.IdentifierError)
    _name, names, kinds = COMPOSITE_ID_SPECS[prefix]
    components = tuple(components)
    if len(components) != len(names):
        errors.fail(
            "%s requires %d component(s) %s, got %d"
            % (prefix, len(names), list(names), len(components)),
            errors.IdentifierError,
        )
    for value, kind, name in zip(components, kinds, names):
        _require_component(value, kind, prefix, name)
    return COMPOSITE_SEPARATOR.join((prefix,) + components)


def parse_composite_id(value):
    """Split a composite identifier into (prefix, components tuple).

    Validates the prefix, the component count and every component, so
    make_composite_id(*parse_composite_id(x)) round-trips exactly.
    """
    if not isinstance(value, str):
        errors.fail(
            "composite identifier must be a string, got %s" % (type(value).__name__,),
            errors.IdentifierError,
        )
    parts = value.split(COMPOSITE_SEPARATOR)
    prefix, components = parts[0], tuple(parts[1:])
    if prefix not in COMPOSITE_ID_SPECS:
        errors.fail("unknown composite prefix %r" % (prefix,), errors.IdentifierError)
    _name, names, kinds = COMPOSITE_ID_SPECS[prefix]
    if len(components) != len(names):
        errors.fail(
            "%s requires %d component(s) %s, got %d"
            % (prefix, len(names), list(names), len(components)),
            errors.IdentifierError,
        )
    for component, kind, name in zip(components, kinds, names):
        _require_component(component, kind, prefix, name)
    return prefix, components


def require_composite_id(value, prefix, field):
    """Require a composite identifier carrying exactly `prefix`."""
    actual, _components = parse_composite_id(value)
    if actual != prefix:
        errors.fail(
            "%s must be a %s identifier, got prefix %r" % (field, prefix, actual),
            errors.IdentifierError,
        )
    return value


def make_source_id(platform_name, normalized_url):
    """SRC|<platform>|<normalizedUrlHash12> (Catalog section H).

    The hash component is the first 12 hex characters of the SHA-256 of the
    normalized URL, so the identifier is deterministic for a given input.
    """
    errors.require_str(normalized_url, "normalizedUrl")
    digest12 = sha256_hex(normalized_url.encode("utf-8"))[:12]
    return make_composite_id("SRC", (platform_name, digest12))


def make_educator_id(slug):
    """EDU|<slug>"""
    return make_composite_id("EDU", (slug,))


def make_connector_id(source_type, name):
    """CONN|<sourceType>|<name>"""
    return make_composite_id("CONN", (source_type, name))


def make_worker_id(capability):
    """WRK|<capability>"""
    return make_composite_id("WRK", (capability,))


def make_transformation_id(name):
    """XF|<name>"""
    return make_composite_id("XF", (name,))


def make_capability_id(domain, name):
    """CAP|<domain>|<name> (Catalog section O).

    Constructs the identifier form only. Registration, lifecycle and dispatch
    eligibility are DEFERRED to the Capability Registry step.
    """
    return make_composite_id("CAP", (domain, name))


def make_canonical_rule_id(educator, slug):
    """RULE|<educator>|<slug>"""
    return make_composite_id("RULE", (educator, slug))


# ---------------------------------------------------------------------------
# Governance-owned identifiers -- referenced, never minted
# ---------------------------------------------------------------------------

GOVERNANCE_OWNED_IDENTIFIER_FIELDS = (
    "hypothesisId",
    "evidencePackageId",
    "replayPackageId",
)


def is_governance_owned_identifier_field(field_name):
    """True if `field_name` names an identifier the platform must never mint.

    Catalog section H: these are "owned by governance; the platform never mints
    these". They may be carried as references, which is why this module offers
    a predicate and no constructor.
    """
    return field_name in GOVERNANCE_OWNED_IDENTIFIER_FIELDS


# ---------------------------------------------------------------------------
# Catalog section I -- idempotency key composition
# ---------------------------------------------------------------------------

# Operation -> exact ordered semantic parts. Constitution section 11: keys are
# "deterministic and derived from semantic inputs, never from timestamps or
# attempt numbers". No composition below contains a timestamp or an attempt
# number, and an undeclared part is rejected rather than ignored.
IDEMPOTENCY_KEY_COMPOSITION = MappingProxyType({
    "source_discovery":           ("connectorId", "query", "window"),
    "source_registration":        ("normalizedUrl", "educatorId"),
    "metadata_acquisition":       ("sourceId", "connectorVersion"),
    "artifact_acquisition":       ("sourceId", "locator", "connectorVersion"),
    # Catalog section I records transcript acquisition as "as artifact".
    "transcript_acquisition":     ("sourceId", "locator", "connectorVersion"),
    "raw_storage":                ("sha256",),
    # Catalog section I groups normalize / clean / segment / extract into one
    # row with one composition.
    "transformation":             ("inputHash", "transformationId",
                                   "transformationVersion"),
    "duplicate_analysis":         ("candidateSetHash", "algorithmVersion"),
    "evidence_candidate_creation": ("segmentId", "extractorVersion"),
    "review_request":             ("subjectId", "reviewType"),
})

IDEMPOTENCY_OPERATIONS = tuple(IDEMPOTENCY_KEY_COMPOSITION.keys())

# ---------------------------------------------------------------------------
# MOGO-016 -- declared EXTENSIONS, kept OUT of the Catalog transcription above
# ---------------------------------------------------------------------------
# The table above is a verbatim transcription of Catalog section I and must stay
# that way, so an operation the Catalog does not contain is declared HERE
# instead of being smuggled into it. The separation is the point: a reader can
# still diff the Catalog against the code, and every departure from it is in one
# short, named, justified list.
#
# WHY THIS ONE EXISTS. Catalog section I keys metadata acquisition on
# `(sourceId, connectorVersion)`. Both parts are constant for one approved
# source, so a SCHEDULED collector re-submitting that command produces the same
# key forever and is suppressed as a duplicate after its first run -- correct
# for section I's "return cached" duplicate rule, and useless as a recurring
# collector. The semantic input that distinguishes one scheduled collection from
# the next is the COLLECTION OCCASION.
#
# `collectionWindow` is a bounded window BUCKET, not an execution timestamp and
# not an attempt number, so Constitution section 11 is satisfied rather than
# worked around -- and the Catalog itself already treats a `window` as a
# legitimate semantic key part in `source_discovery`. Two runs inside one window
# are the same request by construction, which is exactly what collapses a
# post-wake catch-up into a single acquisition.
#
# `resourceId` is included because this composition addresses metadata for ONE
# RESOURCE. Section I's row addresses a source as a whole and therefore omits
# it; reusing that row for a resource-scoped fetch would make two different
# videos collide on one key.
IDEMPOTENCY_KEY_EXTENSIONS = MappingProxyType({
    "scheduled_metadata_acquisition": ("sourceId", "resourceId",
                                       "connectorVersion", "collectionWindow"),
})

ALL_IDEMPOTENCY_OPERATIONS = tuple(IDEMPOTENCY_OPERATIONS) + tuple(
    IDEMPOTENCY_KEY_EXTENSIONS.keys())


def _declared_parts(operation):
    """The parts for a Catalog operation or a declared extension, or None."""
    if operation in IDEMPOTENCY_KEY_COMPOSITION:
        return IDEMPOTENCY_KEY_COMPOSITION[operation]
    return IDEMPOTENCY_KEY_EXTENSIONS.get(operation)


def idempotency_key(operation, parts):
    """Compose a deterministic idempotency key.

    `parts` must be a mapping whose keys are exactly the declared parts for
    `operation` -- no more, no fewer. A missing part and an undeclared extra
    part are both errors, so a caller cannot quietly widen or narrow a key.

    The key is the SHA-256 of the canonical serialization of the operation
    together with its parts, making it stable across retries by construction.
    """
    declared = _declared_parts(operation)
    if declared is None:
        errors.fail(
            "unknown idempotency operation %r" % (operation,), errors.IdentifierError
        )
    errors.require_mapping(parts, "parts", errors.IdentifierError)
    supplied = set(parts.keys())
    missing = [name for name in declared if name not in supplied]
    if missing:
        errors.fail(
            "idempotency operation %s is missing part(s) %s" % (operation, missing),
            errors.IdentifierError,
        )
    extra = sorted(supplied - set(declared))
    if extra:
        errors.fail(
            "idempotency operation %s received undeclared part(s) %s"
            % (operation, extra),
            errors.IdentifierError,
        )
    for name in declared:
        value = parts[name]
        if value is None:
            errors.fail(
                "idempotency part %s.%s must not be null" % (operation, name),
                errors.IdentifierError,
            )
    ordered = {name: parts[name] for name in declared}
    return content_hash_of({"operation": operation, "parts": ordered})


# ---------------------------------------------------------------------------
# Architecture section 17 -- collision handling
# ---------------------------------------------------------------------------


def assert_content_identity(bytes_a, bytes_b):
    """Apply the content-derived collision rule to two byte strings.

    Identical bytes are the same object -- identity, not an error. An identical
    digest over differing bytes is a corruption alarm and raises
    InvariantViolationError; it is never resolved by renaming.

    Returns the shared digest when the two are identical.
    """
    digest_a = sha256_hex(bytes_a)
    digest_b = sha256_hex(bytes_b)
    if digest_a != digest_b:
        errors.fail(
            "content hashes differ: %s != %s" % (digest_a, digest_b),
            errors.IdentifierError,
        )
    if bytes(bytes_a) != bytes(bytes_b):
        errors.fail(
            "content hash %s produced by differing bytes -- corruption alarm"
            % (digest_a,),
            errors.InvariantViolationError,
        )
    return digest_a

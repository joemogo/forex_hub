#!/usr/bin/env python3
"""MOGO Automation Platform -- capability registry and the dispatch decision.

AUTHORITY
    Automation Platform Constitution v1.0 (senior) -- section 7, section 4.3
    ADR-012 (accepted 2026-08-07)                  -- D-16 Capability Registry
    MOGO-009 Contract Catalog, section O
    MOGO-009 Architecture, section 15b
    MOGO-011 Step 1 plan, section 11

THE REGISTRY IS THE ONLY SOURCE OF DISPATCH AUTHORITY
    Architecture section 15b: the orchestrator "may dispatch work only to an
    enabled capability whose declared compatibility admits the requested command
    version". Nothing is inferred from code, from a module name, or from the
    presence of a function. If a capability is not registered, enabled,
    lifecycle-eligible, command-accepting and version-compatible, it does not
    run -- and the refusal is recorded.

REGISTRATION CONFERS NO SCIENTIFIC AUTHORITY
    Catalog section O, restated because it is easy to forget: a registered,
    enabled, production capability still cannot approve a rule, promote a
    hypothesis, or write scientific evidence. That boundary comes from the
    dependency rules and the Constitution, never from registry state.

MANIFESTS ARE IMMUTABLE ONCE REGISTERED
    A manifest is stored with the SHA-256 of its canonical form. Re-registering
    an identical manifest is a no-op. Re-registering a CHANGED manifest under
    the same capabilityId is refused: a changed capability is a new version and
    needs a new identity, or the audit trail would silently describe work that
    was performed by different code.
"""

from ..contracts import ids  # noqa: E402
from . import errors as runtime_errors  # noqa: E402

DISPATCHABLE_LIFECYCLE_STATES = ("approved", "production")

_MANIFEST_REQUIRED_FIELDS = (
    "capabilityId", "name", "version", "owner", "acceptedCommands",
    "emittedEvents", "resourceLimits", "lifecycleStatus", "enabledState",
    "compatibility", "operationClass",
)


def manifest_hash(manifest):
    return ids.content_hash_of(manifest)


def _canonical(value):
    return ids.canonical_json_bytes(value).decode("utf-8")


def validate_manifest(manifest):
    """Structural validation of a Catalog section O record. Fail-closed."""
    for field in _MANIFEST_REQUIRED_FIELDS:
        if field not in manifest:
            runtime_errors.fail(
                "capability manifest is missing %s" % (field,),
                runtime_errors.ContractValidationError,
            )
    ids.require_composite_id(manifest["capabilityId"], "CAP", "capabilityId")
    ids.require_json_shaped(manifest, "$capabilityManifest")
    if manifest["lifecycleStatus"] not in (
            "proposed", "experimental", "approved", "production",
            "deprecated", "disabled", "retired"):
        runtime_errors.fail(
            "lifecycleStatus %r is not an approved Catalog section O state"
            % (manifest["lifecycleStatus"],),
            runtime_errors.ContractValidationError,
        )
    return manifest


def register(connection, manifest, now):
    """Register a capability. Idempotent for an identical manifest.

    Returns "registered", "unchanged". Raises when the same capabilityId is
    presented with different content -- see the module docstring.
    """
    validate_manifest(manifest)
    digest = manifest_hash(manifest)
    capability_id = manifest["capabilityId"]

    row = connection.execute(
        "SELECT manifest_hash FROM capabilities WHERE capability_id = ?",
        (capability_id,)).fetchone()
    if row is not None:
        if row["manifest_hash"] == digest:
            return "unchanged"
        runtime_errors.fail(
            "capability %s is already registered with a different manifest "
            "(%s != %s); a changed capability is a new version and needs a new "
            "capabilityId" % (capability_id, row["manifest_hash"], digest),
            runtime_errors.CapabilityNotDispatchableError,
        )

    connection.execute(
        "INSERT INTO capabilities ("
        " capability_id, name, version, owner, accepted_commands, emitted_events,"
        " lifecycle_status, enabled_state, compatibility, operation_class,"
        " resource_limits, manifest_hash, registered_at"
        ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (capability_id, manifest["name"], manifest["version"], manifest["owner"],
         _canonical(manifest["acceptedCommands"]),
         _canonical(manifest["emittedEvents"]),
         manifest["lifecycleStatus"], 1 if manifest["enabledState"] else 0,
         _canonical(manifest["compatibility"]), manifest["operationClass"],
         _canonical(manifest["resourceLimits"]), digest, now),
    )
    return "registered"


def lookup(connection, reference):
    """Resolve a targetCapability reference to a registry row, or None.

    Accepts both forms MOGO-010 admits and that Catalog section A leaves
    ambiguous: the CAP| composite identifier and the dotted capability name.
    Both map to one row. The canonical-form ambiguity is CARRIED, not resolved
    here -- resolving it is a governance decision, recorded as risk A-7.
    """
    if not isinstance(reference, str) or not reference:
        return None
    row = connection.execute(
        "SELECT * FROM capabilities WHERE capability_id = ?", (reference,)).fetchone()
    if row is not None:
        return row
    return connection.execute(
        "SELECT * FROM capabilities WHERE name = ?", (reference,)).fetchone()


def assert_dispatchable(row, command_type, command_version, reference):
    """The five Catalog section O dispatch conditions. Any failure is fatal.

    Raises CapabilityNotDispatchableError with a message naming the condition
    that failed, so an operator reading the audit report can tell "not
    registered" from "registered but disabled" from "wrong version" without
    reading code (Architecture section 23).
    """
    import json

    if row is None:
        runtime_errors.fail(
            "capability %r is not registered" % (reference,),
            runtime_errors.CapabilityNotDispatchableError,
        )
    if not row["enabled_state"]:
        runtime_errors.fail(
            "capability %s is registered but disabled" % (row["capability_id"],),
            runtime_errors.CapabilityNotDispatchableError,
        )
    if row["lifecycle_status"] not in DISPATCHABLE_LIFECYCLE_STATES:
        runtime_errors.fail(
            "capability %s is in lifecycle state %r; dispatch requires one of %s"
            % (row["capability_id"], row["lifecycle_status"],
               list(DISPATCHABLE_LIFECYCLE_STATES)),
            runtime_errors.CapabilityNotDispatchableError,
        )
    accepted = json.loads(row["accepted_commands"])
    if command_type not in accepted:
        runtime_errors.fail(
            "capability %s does not accept command type %r (accepts %s)"
            % (row["capability_id"], command_type, accepted),
            runtime_errors.CapabilityNotDispatchableError,
        )
    compatibility = json.loads(row["compatibility"])
    versions = compatibility.get(command_type, [])
    if command_version not in versions:
        runtime_errors.fail(
            "capability %s does not admit %s version %r (admits %s)"
            % (row["capability_id"], command_type, command_version, versions),
            runtime_errors.CapabilityNotDispatchableError,
        )
    return row


def all_capabilities(connection):
    return connection.execute(
        "SELECT * FROM capabilities ORDER BY capability_id").fetchall()

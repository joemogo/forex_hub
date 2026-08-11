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

from types import MappingProxyType

from ..contracts import errors as contract_errors  # noqa: E402
from ..contracts import ids  # noqa: E402
from . import errors as runtime_errors  # noqa: E402
from . import policy as policy_module  # noqa: E402
from . import retry as retry_module  # noqa: E402

DISPATCHABLE_LIFECYCLE_STATES = ("approved", "production")

_MANIFEST_REQUIRED_FIELDS = (
    "capabilityId", "name", "version", "owner", "acceptedCommands",
    "emittedEvents", "resourceLimits", "lifecycleStatus", "enabledState",
    "compatibility", "operationClass",
)

# ---------------------------------------------------------------------------
# Risk A-5 -- the gate that cannot be opened by accident
# ---------------------------------------------------------------------------
# Crash boundary 8 -- interrupted between execution and recording success -- is
# safe ONLY because every registered capability is pure. Re-execution after an
# interrupted run produces a byte-identical result, so it is indistinguishable
# from never having been interrupted. THAT IS A PROPERTY OF THE CAPABILITY, NOT
# OF THE KERNEL. The moment a capability performs an external effect, the
# argument fails, and an effectful capability therefore requires output
# verification and an idempotency-keyed result store BEFORE it may register.
#
# MOGO-011 Step 2 resolves A-5 as Option A (ratified 2026-08-08, decision B-4):
# pure capabilities only, effectful registration MECHANICALLY prohibited.
#
# The gate is a declared table of preconditions, not a comment and not a
# convention. All four are False, and a test asserts they are all False -- so a
# future step that builds the result store BREAKS A TEST NAMED AFTER THE GATE,
# forcing a conscious governance decision at exactly the moment the gate opens.
# That is the property worth having: the gate is closed by data, and opening it
# is loud.
#
# What this does NOT claim: Step 2 adds no output verification, no result store
# and no duplicate-effect prevention, because it registers nothing that needs
# them. A-5 is closed by PROHIBITION, not by construction, and the underlying
# hazard is unchanged.

# MOGO-014 Step 2 satisfied all four. Each is a CLAIM, so each names the thing
# that makes it true -- flipping a gate without an implementation behind it
# would be the most dangerous edit in this file.
A5_EFFECTFUL_GATE = MappingProxyType({
    # runtime/result_store.py: results recorded under the command's idempotency
    # key, which is UNIQUE in the schema, so a second insert is refused by the
    # database rather than by remembering to check.
    "idempotencyKeyedResultStore": True,    # Constitution s11, Catalog section I
    # result_store.lookup() RE-DERIVES the SHA-256 of the canonical form of the
    # stored result and refuses any row whose hash disagrees.
    "outputVerificationByRehash":  True,    # Constitution s11, Architecture s19
    # The orchestrator looks the key up BEFORE dispatch and replays the recorded
    # result instead of executing again; the capability additionally writes
    # content-addressed, so a repeat write is a no-op rather than a second
    # artifact. Two independent mechanisms, neither picking a winner.
    "duplicateEffectPrevention":   True,    # Constitution s11 "never pick a winner"
    # Boundary 8 -- interrupted between the effect and recording success -- is
    # now resolved by looking up the idempotency key, not by re-running and
    # hoping the capability happened to be idempotent.
    "postExecutionRecoveryRule":   True,    # the boundary-8 rule when effectful
})

EFFECT_CLASSES = ("pure", "effectful")
DEFAULT_EFFECT_CLASS = "pure"

# Architecture section 32 item 5: the policy gate precedes ANY connector.
# Declared as data and printed by `status` so an operator can see what stands
# between this platform and its first acquisition WITHOUT READING CODE
# (Constitution section 13, applied to the gate itself). The most important
# thing an operator can know about this platform is what it is not yet allowed
# to do, and why.
CONNECTOR_GATES = (
    # MOGO-011 Step 3 built this one. Classification is enforced from the
    # committed Catalog section M table, authorization records are validated,
    # stored append-only and resolved per source, and the enforcement tests
    # exist. Flipping it to True is a claim, so it is made only because all
    # three named requirements are delivered -- and the three gates below
    # remain unmet, which is what still stands between this platform and its
    # first acquisition.
    MappingProxyType({
        "gate": "policy_gate",
        "authority": "Architecture section 32 item 5 -- before any connector",
        "requires": "classification, authorization records, enforcement tests",
        "satisfied": True,
    }),
    MappingProxyType({
        "gate": "a5_result_store",
        "authority": "Constitution section 11; risk A-5",
        "requires": ("idempotency-keyed result store, output verification by "
                     "re-hash, duplicate-effect prevention, post-execution "
                     "recovery rule"),
        # MOGO-014 Step 2: satisfied by runtime/result_store.py. Results are
        # recorded under the command's idempotency key, the key is UNIQUE in the
        # schema, and lookup() RE-DERIVES the hash of the stored result and
        # refuses a row whose hash disagrees. Crash boundary 8 is now resolved
        # by looking the key up rather than by every capability being pure.
        "satisfied": True,
    }),
    MappingProxyType({
        "gate": "first_connector_authorization",
        "authority": "ADR-012 D-15 (approved in principle)",
        "requires": "implementation authorization, not yet granted",
        "satisfied": False,
    }),
    MappingProxyType({
        "gate": "acquisition_authorization_record",
        "authority": "Constitution section 5.1; Catalog section M",
        "requires": ("one governance-supplied authorization record per real "
                     "source; the mechanism exists, the records do not"),
        "satisfied": False,
    }),
)


# Gates that govern REACHING OUT of this machine. A capability that opens no
# socket and names no connector cannot be governed by a connector authorization,
# and requiring one of it protects nothing.
CONNECTOR_SCOPED_GATES = frozenset(("first_connector_authorization",))


def uses_connector(manifest):
    """Does this capability actually reach outside the machine?

    True when it names a connector, or declares any acquisition operation that
    is inherently remote. Deliberately conservative: an unreadable or absent
    manifest is treated as connector-using, because the fail-closed direction
    here is to demand MORE authorization, never less.
    """
    if manifest is None:
        return True
    if not isinstance(manifest, dict):
        return True
    if tuple(manifest.get("requiredConnectors") or ()):
        return True
    # `artifact` is deliberately absent: MOGO-014's first effectful capability
    # ingests an artifact already present in the governed local intake area and
    # performs no remote call. `discover`, `metadata` and `transcript` are
    # remote by nature in this architecture.
    remote_operations = {"discover", "metadata", "transcript"}
    declared = set(manifest.get("acquisitionOperations") or ())
    declared |= set(manifest.get("permittedOperations") or ())
    return bool(declared & remote_operations)


def unmet_a5_preconditions(manifest=None):
    """Every A-5 precondition that applies to THIS capability and is unmet.

    MOGO-014 Step 2 narrowed this from a global list to a capability-scoped one,
    and the narrowing is deliberate rather than convenient. The original rule
    refused every effectful capability while ANY of four gates was unsatisfied,
    including `first_connector_authorization` -- a gate about network connectors
    -- for a capability that opens no socket. That is the same over-generalisation
    platform/README.md records correcting once before, where a real constraint
    was broadened into a wrong rule and then enforced by a test.

    Connector-scoped gates are now applied to connector-using capabilities only.
    Every other gate still applies to every effectful capability, and a manifest
    that cannot be read is treated as connector-using.
    """
    connector = uses_connector(manifest)
    return tuple(
        name for name, satisfied in sorted(A5_EFFECTFUL_GATE.items())
        if not satisfied and (connector or name not in CONNECTOR_SCOPED_GATES))


def assert_effect_class_permitted(effect_class, capability_id, manifest=None):
    """Refuse an effectful capability, naming every missing precondition."""
    if effect_class == DEFAULT_EFFECT_CLASS:
        return effect_class
    missing = unmet_a5_preconditions(manifest)
    if not missing:
        return effect_class
    runtime_errors.fail(
        "capability %s declares effectClass=%r; risk A-5 requires %s before "
        "this capability may be registered. Crash boundary 8 is resolved by the "
        "idempotency-keyed result store; the gates named above are not."
        % (capability_id, effect_class, list(missing)),
        runtime_errors.EffectClassRefusedError,
    )


def _validate_failure_classes(manifest, capability_id):
    """Every declared failure class must be a Catalog section K name that the
    runtime can actually resolve to a terminal outcome.

    `source_mutated` and `human_review_required` are refused (decision B-3):
    both are retryable=False, terminal=False, routesToReview=True, and there is
    no `failed -> awaiting_review` edge in the committed contract -- so a task
    failing with either could neither retry nor reach review, and would strand
    in `failed` forever against Constitution section 6.5. A capability may not
    declare a failure the runtime has no legal way to resolve.
    """
    declared = manifest.get("failureClasses", [])
    if not isinstance(declared, (list, tuple)):
        runtime_errors.fail(
            "capability %s declares failureClasses as %s; an array is required"
            % (capability_id, type(declared).__name__),
            runtime_errors.ContractValidationError,
        )
    for name in declared:
        if name not in contract_errors.ERROR_CLASS_NAMES:
            runtime_errors.fail(
                "capability %s declares failure class %r, which is not a "
                "Contract Catalog section K class"
                % (capability_id, name),
                runtime_errors.ContractValidationError,
            )
        if retry_module.requires_review_gate(name):
            runtime_errors.fail(
                "capability %s declares failure class %r, which routes to human "
                "review and is not terminal. No `failed -> awaiting_review` "
                "transition exists in the committed contract and no review gate "
                "exists behind one, so the runtime could not resolve such a "
                "failure to a terminal outcome (Constitution section 6.5). "
                "Refused at registration rather than stranded at runtime."
                % (capability_id, name),
                runtime_errors.ContractValidationError,
            )
    return tuple(declared)


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

    # The four Step 2 fields are OPTIONAL with restrictive defaults, and that
    # is load-bearing rather than lenient. Making any of them required would
    # invalidate the committed echo manifest, change its hash, and break
    # registration on every existing Step 1 state root -- and `register()`
    # refuses a changed manifest under an unchanged capabilityId by design.
    #
    # Each default grants LESS, never more:
    #   effectClass absent              -> pure   (effectful is the permissive
    #                                              value and must be declared,
    #                                              and is then refused)
    #   failureClasses absent           -> ()     (no declared class, so any
    #                                              raised class is a violation)
    #   requiresExecutionContext absent -> False  (receives less information)
    #   retryPolicy absent              -> build defaults: bounded, capped
    capability_id = manifest["capabilityId"]
    effect_class = manifest.get("effectClass", DEFAULT_EFFECT_CLASS)
    if effect_class not in EFFECT_CLASSES:
        runtime_errors.fail(
            "capability %s declares effectClass=%r; the approved values are %s"
            % (capability_id, effect_class, list(EFFECT_CLASSES)),
            runtime_errors.ContractValidationError,
        )
    assert_effect_class_permitted(effect_class, capability_id, manifest)
    _validate_failure_classes(manifest, capability_id)
    _validate_operation_class(manifest, capability_id)
    resolve_retry_policy(manifest)
    return manifest


def _validate_operation_class(manifest, capability_id):
    """The operation class and its acquisition operations must agree.

    Catalog section L footnote 2 makes the operation class the input the policy
    gate routes on, so a manifest that declares it incoherently would produce a
    gate decision about something nobody meant. Refused at registration, and
    the gate ALSO fails closed on an unrecognised class -- two independent
    guards, because this value decides whether authorization is required at all.
    """
    operation_class = manifest.get("operationClass")
    if operation_class not in policy_module.OPERATION_CLASSES:
        runtime_errors.fail(
            "capability %s declares operationClass=%r; the approved classes are "
            "%s. An unrecognised class is treated as acquisition-class and "
            "blocked at the gate, so it is refused here rather than registered "
            "into a permanent denial"
            % (capability_id, operation_class,
               list(policy_module.OPERATION_CLASSES)),
            runtime_errors.ContractValidationError,
        )

    declared = manifest.get("acquisitionOperations", [])
    if not isinstance(declared, (list, tuple)):
        runtime_errors.fail(
            "capability %s declares acquisitionOperations as %s; an array is "
            "required" % (capability_id, type(declared).__name__),
            runtime_errors.ContractValidationError,
        )
    for operation in declared:
        if operation not in policy_module.ACQUISITION_OPERATIONS:
            runtime_errors.fail(
                "capability %s declares acquisition operation %r, which is not "
                "one of %s" % (capability_id, operation,
                               list(policy_module.ACQUISITION_OPERATIONS)),
                runtime_errors.ContractValidationError,
            )

    if operation_class == policy_module.OPERATION_CLASS_NON_ACQUISITION and declared:
        runtime_errors.fail(
            "capability %s declares operationClass=non_acquisition but also "
            "declares acquisition operations %s. A capability is one or the "
            "other; the contradiction is refused rather than resolved by "
            "guessing" % (capability_id, list(declared)),
            runtime_errors.ContractValidationError,
        )

    if operation_class == policy_module.OPERATION_CLASS_ACQUISITION and not declared:
        runtime_errors.fail(
            "capability %s declares operationClass=acquisition but no "
            "acquisitionOperations. Such a capability could never be authorized "
            "for anything, so it is refused at registration rather than blocked "
            "on every task" % (capability_id,),
            runtime_errors.ContractValidationError,
        )
    return tuple(declared)


def resolve_retry_policy(manifest):
    """The retry policy in force for a capability, validated and complete."""
    return retry_module.resolve_policy(manifest.get("retryPolicy"))


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
        " resource_limits, manifest_hash, registered_at,"
        " effect_class, failure_classes, requires_execution_context, retry_policy,"
        " acquisition_operations"
        ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (capability_id, manifest["name"], manifest["version"], manifest["owner"],
         _canonical(manifest["acceptedCommands"]),
         _canonical(manifest["emittedEvents"]),
         manifest["lifecycleStatus"], 1 if manifest["enabledState"] else 0,
         _canonical(manifest["compatibility"]), manifest["operationClass"],
         _canonical(manifest["resourceLimits"]), digest, now,
         manifest.get("effectClass", DEFAULT_EFFECT_CLASS),
         _canonical(list(manifest.get("failureClasses", []))),
         1 if manifest.get("requiresExecutionContext", False) else 0,
         _canonical(resolve_retry_policy(manifest)),
         _canonical(list(manifest.get("acquisitionOperations", [])))),
    )
    return "registered"


def declared_failure_classes(row):
    """The Catalog section K classes a registered capability may report."""
    import json
    return tuple(json.loads(row["failure_classes"]))


def declared_retry_policy(row):
    """The validated retry policy a registered capability declared."""
    import json
    return json.loads(row["retry_policy"])


def declared_acquisition_operations(row):
    """The acquisition operations a registered capability may be authorized for.

    Empty for every non-acquisition capability, which is what makes the gate a
    recorded no-op for them rather than a decision about nothing.
    """
    import json
    if row is None:
        return ()
    return tuple(json.loads(row["acquisition_operations"]))


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

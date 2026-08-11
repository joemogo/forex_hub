#!/usr/bin/env python3
"""MOGO Automation Platform -- the bounded scheduled collection adapter.

MOGO-016. The join between a HOST SCHEDULE and the governed runtime.

AUTHORITY
    MOGO-015 Step 4 -- the governed acquisition capability this invokes
    Constitution section 5.1 -- no acquisition without an authorization record
    Constitution section 11  -- idempotency keys derived from semantic inputs
    Catalog section I        -- idempotency composition (and its one extension)

WHAT THIS IS, AND WHAT IT DELIBERATELY IS NOT

    It is a COMMAND BUILDER. It reads a fixed, committed collection spec and
    turns it into exactly one governed command envelope. It opens no socket,
    writes no file, touches no clock of its own, and knows nothing about
    launchd. Everything downstream -- policy, authorization, lease, retry,
    connector gate, transport, ingestion, dedupe, audit -- already exists and is
    invoked unchanged.

    It is NOT a scheduler. There is no timer here, no queue of future work and
    no catch-up logic. The host schedule decides WHEN; this module decides only
    WHAT, and the answer is always the same one approved thing.

NO CALLER-CONTROLLED DESTINATION, AT ANY LAYER

    The spec names a SOURCE and a RESOURCE. It cannot name a URL, a host or a
    scheme, because no field exists for one -- an unknown field is refused
    rather than ignored. `validate_spec` additionally re-checks the source
    against the connector's own approved-destination registry and calls
    `derive_destination()` to prove the destination is derivable BEFORE any
    command is built. A spec naming an unapproved source therefore fails at
    build time, and would fail again at the gate even if it did not.

THE COLLECTION WINDOW -- why a recurring collector needs one

    Catalog section I keys metadata acquisition on `(sourceId, connectorVersion)`.
    Both are constant here, so re-submitting the identical command produces an
    identical idempotency key and is suppressed as a duplicate forever after the
    first run. That is section I working correctly ("duplicate -> return
    cached") and it is useless as a recurring collector.

    So the scheduled request identity is composed over a bounded COLLECTION
    WINDOW -- `ids.IDEMPOTENCY_KEY_EXTENSIONS["scheduled_metadata_acquisition"]`,
    declared as an extension rather than smuggled into the Catalog table. The
    window is a bucket index, not an execution timestamp:

        bucket = now_ms // (windowSeconds * 1000)

    Two invocations inside one window are THE SAME REQUEST by construction. That
    is what makes a post-sleep catch-up run, a duplicate launchd firing and an
    operator's manual kickstart all collapse into a single acquisition instead
    of hammering the source. The next window is a new request, so collection
    genuinely recurs.

    Request identity is still not content identity. Whether a research artifact
    is created remains decided by the SHA-256 of the bytes the source returned,
    in the ingestion capability, exactly as MOGO-015 proved.

`now_ms` IS ALWAYS AN ARGUMENT

    Same discipline as policy.py and retry.py: no clock is read in this module,
    so every function is a pure function of its arguments and the whole adapter
    is exhaustively testable without a process, a database or a wait.
"""

from ..contracts import ids  # noqa: E402
from . import connector_authorization as connector_gate  # noqa: E402
from . import errors as runtime_errors  # noqa: E402
from .capabilities import acquire_approved_source_metadata as acquire  # noqa: E402

SPEC_SCHEMA_VERSION = "mogo.scheduled-collection.v1"

IDEMPOTENCY_OPERATION = "scheduled_metadata_acquisition"

# Catalog section A permits `orchestrator`, `operator:<id>` and `workflow:<type>`.
# A scheduled submission is NOT an operator action and must not claim to be one:
# no human is present when it runs, and an audit trail that says `operator:` for
# unattended work is a small lie that a later reader would believe.
ISSUED_BY = "workflow:scheduled-research-collection"

SPEC_REQUIRED_FIELDS = (
    "schemaVersion", "capabilityId", "commandType", "commandVersion",
    "sourceId", "resourceId", "authorizationId", "operation",
    "connectorId", "connectorVersion", "policyVersion",
    "collectionWindowSeconds",
)

# `note` exists so the committed spec can explain itself to a human reading it.
# It is not used to build anything.
SPEC_OPTIONAL_FIELDS = ("note",)

SPEC_FIELDS = SPEC_REQUIRED_FIELDS + SPEC_OPTIONAL_FIELDS

# Bounds on the collection window, enforced here rather than trusted from a
# file. The floor is service etiquette: a window shorter than a minute would let
# a misconfigured schedule produce a distinct request identity every firing and
# turn a bounded collector into a polling loop. The ceiling keeps a stale spec
# from silently pinning one request identity for months.
MIN_COLLECTION_WINDOW_SECONDS = 60
MAX_COLLECTION_WINDOW_SECONDS = 7 * 24 * 60 * 60


def _refuse(message):
    runtime_errors.fail(message, runtime_errors.ContractValidationError)


def validate_spec(spec):
    """Fail-closed validation of the fixed approved collection spec.

    Returns the spec unchanged. Every refusal happens BEFORE a command exists,
    so an unapproved spec can never reach `submit`.
    """
    if not hasattr(spec, "keys"):
        _refuse("collection spec must be a mapping, got %s"
                % (type(spec).__name__,))

    missing = [name for name in SPEC_REQUIRED_FIELDS if name not in spec]
    if missing:
        _refuse("collection spec is missing required field(s) %s" % (missing,))

    unknown = sorted(set(spec) - set(SPEC_FIELDS))
    if unknown:
        # An unknown field is how a URL, a host or a second source would arrive.
        # Refusing it is what keeps this file incapable of naming a destination.
        _refuse("collection spec declares unknown field(s) %s; the approved "
                "fields are %s" % (unknown, list(SPEC_FIELDS)))

    if spec["schemaVersion"] != SPEC_SCHEMA_VERSION:
        _refuse("collection spec schemaVersion %r is not %r"
                % (spec["schemaVersion"], SPEC_SCHEMA_VERSION))

    # ONE capability. Not "an acquisition capability" -- this one, by identity.
    if spec["capabilityId"] != acquire.CAPABILITY_ID:
        _refuse("collection spec targets capability %r; the only capability "
                "approved for scheduled collection is %r"
                % (spec["capabilityId"], acquire.CAPABILITY_ID))

    accepted = tuple(acquire.MANIFEST["acceptedCommands"])
    if spec["commandType"] not in accepted:
        _refuse("collection spec commandType %r is not accepted by %s (accepts "
                "%s)" % (spec["commandType"], acquire.CAPABILITY_ID,
                         list(accepted)))
    admitted = tuple(acquire.MANIFEST["compatibility"].get(spec["commandType"],
                                                           ()))
    if spec["commandVersion"] not in admitted:
        _refuse("collection spec commandVersion %r is not admitted for %s "
                "(admits %s)" % (spec["commandVersion"], spec["commandType"],
                                 list(admitted)))

    if spec["connectorId"] != connector_gate.CONNECTOR_ID:
        _refuse("collection spec names connector %r; the approved connector is "
                "%r" % (spec["connectorId"], connector_gate.CONNECTOR_ID))
    if spec["connectorVersion"] != connector_gate.CONNECTOR_VERSION:
        _refuse("collection spec names connector version %r; the registered "
                "version is %r" % (spec["connectorVersion"],
                                   connector_gate.CONNECTOR_VERSION))

    if spec["operation"] != connector_gate.OPERATION_METADATA:
        _refuse("collection spec requests operation %r; scheduled collection is "
                "approved for %r only"
                % (spec["operation"], connector_gate.OPERATION_METADATA))

    source_id = spec["sourceId"]
    ids.require_composite_id(source_id, "SRC", "sourceId")
    if source_id not in connector_gate.APPROVED_DESTINATIONS:
        _refuse("collection spec names source %r, which is not in the connector "
                "approved-destination registry" % (source_id,))

    # Prove the destination is DERIVABLE before a command is built. This also
    # validates the resource identifier against the connector's pinned pattern,
    # using the connector's own function rather than a second copy of the rule.
    connector_gate.derive_destination(source_id, spec["resourceId"])

    ids.require_uuid4(spec["authorizationId"], "authorizationId")

    policy_version = spec["policyVersion"]
    if not isinstance(policy_version, str) or not policy_version.strip():
        _refuse("collection spec policyVersion must be a non-empty string")

    window = spec["collectionWindowSeconds"]
    if isinstance(window, bool) or not isinstance(window, int):
        _refuse("collectionWindowSeconds must be an integer, got %s"
                % (type(window).__name__,))
    if not (MIN_COLLECTION_WINDOW_SECONDS <= window
            <= MAX_COLLECTION_WINDOW_SECONDS):
        _refuse("collectionWindowSeconds %d is outside the approved range "
                "%d..%d" % (window, MIN_COLLECTION_WINDOW_SECONDS,
                            MAX_COLLECTION_WINDOW_SECONDS))
    return spec


def collection_window(now_ms, window_seconds):
    """The collection occasion `now_ms` belongs to. Pure.

    A bucket index and its width, never an instant. Every millisecond inside one
    window yields the same label, which is what makes two invocations in one
    window the same request.
    """
    if isinstance(now_ms, bool) or not isinstance(now_ms, int):
        _refuse("now_ms must be an integer millisecond value, got %s"
                % (type(now_ms).__name__,))
    if now_ms < 0:
        _refuse("now_ms must not be negative, got %d" % (now_ms,))
    if isinstance(window_seconds, bool) or not isinstance(window_seconds, int):
        _refuse("window_seconds must be an integer, got %s"
                % (type(window_seconds).__name__,))
    if not (MIN_COLLECTION_WINDOW_SECONDS <= window_seconds
            <= MAX_COLLECTION_WINDOW_SECONDS):
        _refuse("window_seconds %d is outside the approved range %d..%d"
                % (window_seconds, MIN_COLLECTION_WINDOW_SECONDS,
                   MAX_COLLECTION_WINDOW_SECONDS))
    return "W|%d|%d" % (window_seconds, now_ms // (window_seconds * 1000))


def scheduled_idempotency_key(spec, window):
    """The request identity of one scheduled collection occasion."""
    return ids.idempotency_key(IDEMPOTENCY_OPERATION, {
        "sourceId": spec["sourceId"],
        "resourceId": spec["resourceId"],
        "connectorVersion": spec["connectorVersion"],
        "collectionWindow": window,
    })


def build_command(spec, now_ms, issued_at, uuid_factory=None):
    """One governed command envelope for one collection occasion. Pure.

    Returns (envelope, payload, window). The caller submits it through the
    ordinary `submit` path -- there is no privileged route into the runtime.
    """
    validate_spec(spec)
    window = collection_window(now_ms, spec["collectionWindowSeconds"])

    def mint():
        return ids.new_uuid4(uuid_factory=uuid_factory)

    payload = {
        "sourceId": spec["sourceId"],
        "resourceId": spec["resourceId"],
        "authorizationId": spec["authorizationId"],
        "collectionWindow": window,
    }
    correlation_id = mint()
    envelope = {
        "commandId": mint(),
        "commandType": spec["commandType"],
        "commandVersion": spec["commandVersion"],
        "workflowId": mint(),
        "correlationId": correlation_id,
        "causationId": correlation_id,
        "idempotencyKey": scheduled_idempotency_key(spec, window),
        "issuedAt": issued_at,
        "issuedBy": ISSUED_BY,
        "targetCapability": spec["capabilityId"],
        # Catalog section A: references only. Exactly ONE SRC| ref, because
        # _subject_source() denies on zero and on two -- the policy gate must
        # resolve an authorization for one unambiguous source.
        "inputRefs": [spec["sourceId"]],
        "policyContext": {
            "authorizationId": spec["authorizationId"],
            "policyVersion": spec["policyVersion"],
            "permittedOperations": [spec["operation"]],
        },
        "payloadHash": ids.content_hash_of(payload),
    }
    return (envelope, payload, window)

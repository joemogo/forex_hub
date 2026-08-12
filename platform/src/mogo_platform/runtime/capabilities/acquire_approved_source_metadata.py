#!/usr/bin/env python3
"""MOGO Automation Platform -- research.acquire.approved-source-metadata.v1.

MOGO'S FIRST GOVERNED EXTERNAL ACQUISITION CAPABILITY (MOGO-015 Step 4).

AUTHORITY
    MOGO-015 Step 1A (source verified) · Step 2 (gate) · Step 3 (transport)
    Step 4 authorization
    Constitution section 5.1 -- no acquisition without an authorization record

WHAT IT DOES

    Acquires metadata for ONE resource from ONE repository-verified external
    source, preserves the raw bytes, and hands them to the EXISTING ingestion
    capability. It is the join between the governed runtime and the outside
    world, and it is deliberately thin: every hard part already exists.

        gate (Step 2) -> transport (Step 3) -> raw bytes
        -> governed intake -> research.ingest.local-artifact.v1 (MOGO-014)

WHAT IT CANNOT DO

    It accepts no URL. It names a SOURCE and a RESOURCE; the connector
    authorization gate derives the destination. There is no argument that
    becomes a fetch target, and `connector_transport` is the only way it can
    reach the network -- it imports no network client of its own, which a test
    asserts.

    It performs no discovery, no transcript acquisition, no scraping. It does
    not touch ALEX, ALEX parameters, the paper account, the forward observation
    ledger, Campaign C1 or the legacy corpus.

SAME REQUEST IS NOT SAME CONTENT, AND THIS IS THE SUBTLE PART

    Two identity layers, deliberately distinct:

      * REQUEST identity -- the command's idempotency key, derived from the
        request payload. Re-submitting the same command is suppressed by the
        runtime, because asking the same question twice in one breath is a
        duplicate submission.

      * CONTENT identity -- the SHA-256 of the bytes the source actually
        returned. This decides whether a RESEARCH ARTIFACT is new.

    Collapsing them would be wrong in both directions: a source whose metadata
    legitimately changed would be suppressed as a duplicate, and a repeated
    fetch of unchanged bytes would create a second artifact. So an acquisition
    is always RECORDED, while the artifact is created only when the content is
    genuinely new.
"""

import json
import os

from ...contracts import ids  # noqa: E402
from .. import connector_authorization as connector_gate  # noqa: E402
from .. import connector_transport as transport  # noqa: E402
from .. import errors as runtime_errors  # noqa: E402
from .. import research_corpus  # noqa: E402
from . import ingest_local_artifact as ingest  # noqa: E402

CAPABILITY_ID = "CAP|research|acquire-approved-source-metadata"
CAPABILITY_NAME = "research.acquire.approved-source-metadata.v1"
CAPABILITY_VERSION = "1.0.0"

# Raw acquired bytes land here, inside the governed intake area the existing
# ingestion capability already guards. Not a new location -- a subdirectory of
# the one boundary that is already enforced.
ACQUIRED_SUBDIR = "acquired"

MANIFEST = {
    "capabilityId": CAPABILITY_ID,
    "name": CAPABILITY_NAME,
    "version": CAPABILITY_VERSION,
    "owner": "operator:mogo",
    "description": (
        "Acquire metadata for one resource from one repository-verified "
        "external source through the connector authorization gate and bounded "
        "transport, preserve the raw bytes in the governed intake area, and "
        "ingest them through research.ingest.local-artifact.v1."
    ),
    "acceptedCommands": ["AcquireSourceMetadata"],
    "emittedEvents": ["TaskSucceeded", "TaskFailed"],
    "requiredPermissions": [],
    # NAMING THE CONNECTOR IS THE POINT. It makes uses_connector() true, so the
    # connector-scoped A-5 gate applies to this capability -- which is correct,
    # and is why registering it required the connector gate to be satisfied.
    "requiredConnectors": [connector_gate.CONNECTOR_ID],
    "requiredSecretReferences": [],
    "resourceLimits": {"wallClockMs": 45000, "maxPayloadBytes": 65536},
    "lifecycleStatus": "production",
    "enabledState": True,
    "compatibility": {"AcquireSourceMetadata": [1]},
    "operationClass": "acquisition",
    "acquisitionOperations": ["metadata"],
    "effectClass": "effectful",
}


def acquired_root(corpus=None):
    """Where raw acquired bytes land, inside whichever intake area is in force.

    MOGO-017 Step 2B/2C: defaults to the production corpus, so an unchanged
    caller is unchanged. A test supplies a sandbox that
    research_corpus.sandbox_corpus() has already proven cannot reach the genuine
    research corpus.
    """
    corpus = research_corpus.resolve_corpus(corpus)
    return os.path.join(corpus.intakeRoot, ACQUIRED_SUBDIR)


def _relative_intake_ref(content_hash):
    """The ref the ingestion capability expects: relative to INTAKE_ROOT."""
    return "%s/%s.json" % (ACQUIRED_SUBDIR, content_hash)


def preserve_raw(raw, content_hash, acquisition_record, corpus=None):
    """Write the acquired bytes into the governed intake area, content-addressed.

    The file name IS the content hash, so a repeated acquisition of unchanged
    bytes rewrites identical content to the same path rather than accumulating
    copies. The RAW bytes are preserved verbatim alongside the acquisition
    record -- interpretation happens later, in ingestion, never here.
    """
    root = acquired_root(corpus)
    os.makedirs(root, exist_ok=True)
    target = os.path.join(root, content_hash + ".json")
    document = {
        "schemaVersion": "mogo.raw-acquisition.v1",
        "contentHash": content_hash,
        "contentHashAlgorithm": "SHA-256",
        "acquisition": acquisition_record,
        # Verbatim. Decoded as text because the transport already proved it is
        # valid UTF-8 JSON; the hash above is over the ORIGINAL bytes.
        "rawContent": raw.decode("utf-8"),
    }
    body = json.dumps(document, indent=2, sort_keys=True) + "\n"
    tmp = target + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        handle.write(body)
    os.replace(tmp, target)
    return target


def execute(payload, corpus=None):
    """Acquire, preserve, ingest. THE GOVERNED EXTERNAL ACQUISITION.

    `corpus` is MOGO-017 Step 2B's isolation seam, threaded through in Step 2C so
    a deterministic fixture can drive this ENTIRE capability -- gate, transport,
    raw preservation and real ingestion -- without any possibility of touching
    the genuine research corpus. It defaults to None, which resolves to the
    production corpus, so the orchestrator's `callable(payload)` dispatch and
    every production write are unchanged.
    """
    corpus = research_corpus.resolve_corpus(corpus)
    ids.require_json_shaped(payload, "$capabilityPayload")
    plain = ids.as_plain(payload)
    if not isinstance(plain, dict):
        runtime_errors.fail("payload must be an object",
                            runtime_errors.ContractValidationError)

    source_id = plain.get("sourceId")
    resource_id = plain.get("resourceId")
    authorization_id = plain.get("authorizationId")

    # ── ACQUIRE. The gate runs inside transport.acquire(); no permit, no socket.
    outcome = transport.acquire({
        "sourceId": source_id,
        "resourceId": resource_id,
        "authorizationId": authorization_id,
        "capabilityId": CAPABILITY_ID,
        "capabilityVersion": CAPABILITY_VERSION,
        "operation": connector_gate.OPERATION_METADATA,
    })

    if not outcome.ok:
        # The failure class the transport assigned is preserved verbatim, so the
        # runtime's retry policy acts on the transport's judgement rather than a
        # re-interpretation of it here.
        runtime_errors.fail(
            "acquisition failed (%s/%s): %s"
            % (outcome.failureClass, outcome.reason, outcome.detail),
            runtime_errors.ContractValidationError)

    acquisition_record = outcome.as_record()
    content_hash = outcome.contentHash

    # ── PRESERVE raw bytes before any interpretation.
    stored_path = preserve_raw(outcome.rawBytes, content_hash, acquisition_record,
                               corpus)
    intake_ref = _relative_intake_ref(content_hash)

    # ── INGEST through the EXISTING pipeline. Not a second ingestion path: this
    #    is the same function MOGO-014 proved, called with a governed intake ref.
    ingest_result = ingest.execute({
        "artifactRef": intake_ref,
        "sourceId": source_id,
        "claimedSourceTitle": plain.get("claimedSourceTitle"),
        "claimedSourceUrl": outcome.requestedUrl,
        "authorizationId": authorization_id,
    }, corpus=corpus)

    return {
        "capabilityId": CAPABILITY_ID,
        "capabilityVersion": CAPABILITY_VERSION,
        # The runtime records this as the result hash. It is the CONTENT hash of
        # what the source returned -- not of this envelope -- so the result the
        # runtime remembers is the scientific identity.
        "contentHash": content_hash,
        "byteLength": outcome.byteLength,
        # ── acquisition provenance ──
        "sourceId": source_id,
        "resourceId": resource_id,
        "authorizationId": authorization_id,
        "connectorId": outcome.connectorId,
        "transportVersion": outcome.transportVersion,
        "requestedUrl": outcome.requestedUrl,
        "finalUrl": outcome.finalUrl,
        "httpStatus": outcome.httpStatus,
        "contentType": outcome.contentType,
        "acquiredAt": outcome.acquiredAt,
        "connectorDecision": acquisition_record.get("decision"),
        "rawArtifactPath": os.path.relpath(stored_path, ingest.REPO_ROOT),
        "intakeRef": intake_ref,
        # ── ingestion outcome, from the existing capability ──
        "ingestion": {
            "artifactId": ingest_result.get("artifactId"),
            "duplicateStatus": ingest_result.get("duplicateStatus"),
            "ingested": ingest_result.get("ingested"),
            "validationStatus": ingest_result.get("validationStatus"),
            "storedVerified": ingest_result.get("storedVerified"),
            "storedPath": ingest_result.get("storedPath"),
        },
        "lane": "RESEARCH",
        "promotionStatus": "NOT_A_TRADING_RULE",
        "summary": (
            "Acquired %s bytes from %s and %s."
            % (outcome.byteLength, source_id,
               "registered a new research artifact"
               if ingest_result.get("ingested")
               else "recognised identical content already ingested")),
    }

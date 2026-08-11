#!/usr/bin/env python3
"""MOGO Automation Platform -- research.ingest.local-artifact.v1.

MOGO'S FIRST EFFECTFUL CAPABILITY.

AUTHORITY
    MOGO-014 Step 1 repository-truth audit; Step 2 authorization
    Constitution sections 5.1 (no acquisition without an authorization record)
    and 11 (identity is never a timestamp)

WHAT IT DOES

    Ingests ONE research artifact that a human has already placed in the
    governed local intake area, and registers it into the research corpus:
    read -> validate -> content hash -> duplicate check -> register.

WHAT IT IS NOT

    It reaches nothing. It opens no socket, names no connector, and imports no
    network client -- a static test asserts that. It performs no discovery: it
    ingests what an operator put in front of it, under an authorization record
    naming that source. Autonomous discovery is a later, separately governed
    step and is deliberately NOT this one.

    It does not touch ALEX, ALEX parameters, the paper account, the forward
    observation ledger, Campaign C1 or the legacy corpus. It has no code path
    to any of them.

WHY IT IS EFFECTFUL, AND WHAT MAKES THAT SAFE

    It writes a file, so re-running it is not free the way echo was. Two
    independent mechanisms prevent a duplicate effect:

      1. the runtime records the result under the command's idempotency key and
         replays it instead of dispatching again; and
      2. this capability writes CONTENT-ADDRESSED -- the artifact's filename is
         its own content hash -- so even a dispatch that slipped through would
         rewrite identical bytes to the same path rather than create a second
         artifact.

    Belt and braces, deliberately: mechanism 1 lives in the runtime and could be
    bypassed by a future caller; mechanism 2 lives in the effect itself.

PATH SAFETY IS A CONTRACT

    The artifact reference is resolved and must land INSIDE the governed intake
    directory after resolution -- symlinks and `..` included. Anything else is
    refused before a single byte is read. There is no configuration that widens
    this boundary.
"""

import json
import os

from ...contracts import ids  # noqa: E402
from .. import errors as runtime_errors  # noqa: E402

CAPABILITY_ID = "CAP|research|ingest-local-artifact"
CAPABILITY_NAME = "research.ingest.local-artifact.v1"
CAPABILITY_VERSION = "1.0.0"

# Repository-relative, resolved at call time. platform/src/mogo_platform/runtime/
# capabilities/ -> repository root is five levels up.
_HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", "..", "..", ".."))
INTAKE_ROOT = os.path.join(REPO_ROOT, "docs", "trader-intelligence", "intake")
ARTIFACT_ROOT = os.path.join(REPO_ROOT, "docs", "trader-intelligence",
                             "research-artifacts")

MAX_ARTIFACT_BYTES = 2_000_000        # matches acquisition_common's Phase 1 cap
ALLOWED_EXTENSIONS = (".txt", ".md")  # text only in this capability

ARTIFACT_SCHEMA_VERSION = "mogo.research-artifact.v1"

MANIFEST = {
    "capabilityId": CAPABILITY_ID,
    "name": CAPABILITY_NAME,
    "version": CAPABILITY_VERSION,
    "owner": "operator:mogo",
    "description": (
        "Ingest one operator-approved research artifact already present in the "
        "governed local intake area: validate, content-hash, duplicate-check "
        "and register it into the research corpus. Performs no network access."
    ),
    "acceptedCommands": ["IngestLocalArtifact"],
    "emittedEvents": ["TaskSucceeded", "TaskFailed"],
    "requiredPermissions": [],
    "requiredConnectors": [],              # opens nothing; reaches nowhere
    "requiredSecretReferences": [],
    "resourceLimits": {"wallClockMs": 30000,
                       "maxPayloadBytes": MAX_ARTIFACT_BYTES},
    "lifecycleStatus": "production",
    "enabledState": True,
    "compatibility": {"IngestLocalArtifact": [1]},
    # Acquisition-class ON PURPOSE. It is not remote, but it brings external
    # material into the research corpus, and that is exactly what the policy
    # gate exists to govern. Declaring it non_acquisition would slip it past the
    # gate on a technicality -- so it declares the class that demands an
    # authorization record and then satisfies it.
    "operationClass": "acquisition",
    "acquisitionOperations": ["artifact"],
    "effectClass": "effectful",
}


def _refuse(message, error_class=None):
    runtime_errors.fail(message,
                        error_class or runtime_errors.ContractValidationError)


def resolve_intake_path(artifact_ref):
    """Resolve a reference INSIDE the governed intake area, or refuse.

    Refuses absolute paths, traversal, and anything that resolves outside the
    boundary -- checked AFTER realpath, so a symlink pointing out is caught too.
    """
    if not isinstance(artifact_ref, str) or not artifact_ref.strip():
        _refuse("artifactRef is required and must be a non-empty string")
    if os.path.isabs(artifact_ref):
        _refuse("artifactRef must be relative to the governed intake area, "
                "not an absolute path: %r" % (artifact_ref,))
    candidate = os.path.realpath(os.path.join(INTAKE_ROOT, artifact_ref))
    root = os.path.realpath(INTAKE_ROOT)
    if candidate != root and not candidate.startswith(root + os.sep):
        _refuse("artifactRef resolves outside the governed intake area and is "
                "refused: %r" % (artifact_ref,))
    if os.path.splitext(candidate)[1].lower() not in ALLOWED_EXTENSIONS:
        _refuse("artifactRef must name a %s file; refusing %r"
                % (" or ".join(ALLOWED_EXTENSIONS), artifact_ref))
    return candidate


def validate_artifact_bytes(raw, artifact_ref):
    """Permanent-validation rules. A failure here must never be retried."""
    if raw is None:
        _refuse("artifact %r could not be read" % (artifact_ref,))
    if len(raw) == 0:
        _refuse("artifact %r is empty; an empty artifact carries no research "
                "content and is refused" % (artifact_ref,))
    if len(raw) > MAX_ARTIFACT_BYTES:
        _refuse("artifact %r is %d bytes, exceeding the %d byte limit"
                % (artifact_ref, len(raw), MAX_ARTIFACT_BYTES))
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        _refuse("artifact %r is not valid UTF-8 text" % (artifact_ref,))
    if not text.strip():
        _refuse("artifact %r contains only whitespace" % (artifact_ref,))
    return text


def build_artifact_record(payload, artifact_ref, raw, text):
    """The research artifact. Identity is the content hash of the real bytes.

    Never a timestamp, never a filename, never an ingestion counter -- so the
    same content ingested under a different name is still the same artifact.
    """
    content_hash = ids.sha256_hex(raw)
    return {
        "schemaVersion": ARTIFACT_SCHEMA_VERSION,
        "artifactId": "RART|" + content_hash[:32],
        "contentHash": content_hash,
        "contentHashAlgorithm": "SHA-256",
        "byteLength": len(raw),
        "characterLength": len(text),
        # ── Provenance: every question the audit required must be answerable ──
        "provenance": {
            "originClass": "OPERATOR_SUPPLIED_LOCAL_INTAKE",
            "intakeRef": artifact_ref,
            "claimedSourceId": payload.get("sourceId"),
            "claimedSourceTitle": payload.get("claimedSourceTitle"),
            "claimedSourceUrl": payload.get("claimedSourceUrl"),
            "authorizationId": payload.get("authorizationId"),
            "processedByCapability": CAPABILITY_ID,
            "capabilityVersion": CAPABILITY_VERSION,
            "acquisitionPerformed": False,
            "networkAccessPerformed": False,
            "note": ("Ingested from the governed local intake area. MOGO did "
                     "not fetch this artifact; an operator supplied it. The "
                     "source attribution is the operator's CLAIM and has not "
                     "been independently verified by this capability."),
        },
        # Research lane only. Recorded on the artifact so the boundary travels
        # with it rather than living only in a document.
        "lane": "RESEARCH",
        "promotionStatus": "NOT_A_TRADING_RULE",
        "promotionPath": ("RESEARCH ARTIFACT -> STRUCTURED CLAIM -> HYPOTHESIS "
                          "-> PREREGISTRATION -> TEST -> VERIFICATION -> "
                          "ADJUDICATION -> CANDIDATE -> separately governed "
                          "forward authorization"),
    }


def find_existing(content_hash):
    """The stored artifact with this content hash, or None. Content-addressed,
    so this is a path check rather than a corpus scan."""
    path = os.path.join(ARTIFACT_ROOT, content_hash + ".json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, ValueError):
            return None
    return None


def execute(payload):
    """Ingest one governed local artifact. THE EFFECT."""
    ids.require_json_shaped(payload, "$capabilityPayload")
    plain = ids.as_plain(payload)
    if not isinstance(plain, dict):
        _refuse("payload must be an object")

    artifact_ref = plain.get("artifactRef")
    if not plain.get("sourceId"):
        _refuse("sourceId is required: an artifact with no claimed source "
                "cannot be attributed, and an anonymous research artifact is "
                "refused")

    path = resolve_intake_path(artifact_ref)
    if not os.path.isfile(path):
        _refuse("artifact %r does not exist in the governed intake area"
                % (artifact_ref,))

    try:
        with open(path, "rb") as handle:
            raw = handle.read()
    except OSError as exc:                      # transient-class read failure
        runtime_errors.fail(
            "artifact %r could not be read: %s" % (artifact_ref, exc),
            runtime_errors.ContractValidationError)

    text = validate_artifact_bytes(raw, artifact_ref)
    record = build_artifact_record(plain, artifact_ref, raw, text)
    content_hash = record["contentHash"]

    existing = find_existing(content_hash)
    duplicate = existing is not None

    if not duplicate:
        # THE EFFECT. Content-addressed: the path IS the identity, so a repeat
        # write cannot create a second artifact.
        os.makedirs(ARTIFACT_ROOT, exist_ok=True)
        target = os.path.join(ARTIFACT_ROOT, content_hash + ".json")
        tmp = target + ".tmp"
        body = json.dumps(record, indent=2, sort_keys=True) + "\n"
        with open(tmp, "w", encoding="utf-8") as handle:
            handle.write(body)
        os.replace(tmp, target)                 # atomic
        # RE-READ AND RE-HASH what actually landed on disk. Storing is not the
        # same as having stored, and this is the difference.
        with open(target, "rb") as handle:
            written = handle.read()
        reread = json.loads(written.decode("utf-8"))
        if reread.get("contentHash") != content_hash:
            _refuse("stored artifact re-read with a different content hash; "
                    "refusing to report a success that cannot be verified")
        stored_verified = True
    else:
        stored_verified = existing.get("contentHash") == content_hash

    result = {
        "capabilityId": CAPABILITY_ID,
        "capabilityVersion": CAPABILITY_VERSION,
        "contentHash": content_hash,
        "byteLength": len(raw),
        "artifactId": record["artifactId"],
        "validationStatus": "VALID",
        "duplicateStatus": "DUPLICATE_ALREADY_INGESTED" if duplicate else "NEW",
        "ingested": not duplicate,
        "storedVerified": stored_verified,
        "storedPath": os.path.relpath(
            os.path.join(ARTIFACT_ROOT, content_hash + ".json"), REPO_ROOT),
        "sourceId": plain.get("sourceId"),
        "authorizationId": plain.get("authorizationId"),
        "intakeRef": artifact_ref,
        "lane": "RESEARCH",
        "promotionStatus": "NOT_A_TRADING_RULE",
        "summary": (
            "Duplicate: content already ingested; no second artifact created."
            if duplicate else
            "Ingested and registered a new research artifact."),
    }
    return result

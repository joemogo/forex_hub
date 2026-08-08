#!/usr/bin/env python3
"""MOGO Automation Platform -- Step 1 closed vocabularies (inert data only).

AUTHORITY
    Automation Platform Constitution v1.0 (senior)  -- sections 5.2, 6.8
    ADR-012 (accepted 2026-08-07)                   -- approvals 3, 11, 12, 18
    MOGO-009 Contract Catalog, section J            -- command and event names
    MOGO-009 Contract Catalog, section M            -- licensing classification
    MOGO-009 Contract Catalog, section O            -- capability lifecycle

CATALOG SECTION J CAVEAT, PRESERVED VERBATIM IN SPIRIT
    Contract Catalog section J states: "Not finalized. Names and payloads are
    Step 3 work." The names below are transcribed EXACTLY from the current
    approved Catalog and are treated as the current Catalog v1 vocabulary:
    closed for Step 1 structural validation, additive-only within the current
    approved major, and NOT permanently finalized. Future governed additions
    may occur. No name here was invented or renamed.

    PAYLOAD SEMANTICS ARE NOT DEFINED. The Catalog specifies no payload shape
    for any command or event. Step 1 therefore validates that a payload is
    structurally present and canonically hashable; it does NOT interpret,
    validate or claim to understand payload content for any name below.

IMPLEMENTED NOW
    * The four closed vocabularies, as read-only mappings and tuples.

EXPLICITLY DEFERRED -- absent from Step 1 entirely
    * Dispatch, routing, execution and orchestration of any command.
    * Emission, persistence and ordering of any event.
    * Any evaluation of a licensing status. LICENSING_STATUSES is inert
      reference data: no policy engine, no authorization decision, no
      connector behaviour, no task routing, no retry behaviour. Nothing in
      Step 1 reads it to decide anything.
    * Capability registration, lifecycle transition and dispatch eligibility.
      CAPABILITY_LIFECYCLE_STATES is a name list only; no registry exists.
"""

from types import MappingProxyType

# ---------------------------------------------------------------------------
# Operational namespace -- Constitution section 6.8, ADR-012 approval 3
# ---------------------------------------------------------------------------
# Operational events never share a store, schema registry or identifier space
# with trading or scientific records. That separation begins with a distinct
# namespace, used by every platform schema version string.

OPERATIONAL_NAMESPACE = "mogo.platform.operational"

# ---------------------------------------------------------------------------
# Contract Catalog section J -- commands (17)
# ---------------------------------------------------------------------------

COMMAND_TYPES = (
    "RequestSourceDiscovery",
    "RegisterSource",
    "EvaluateSourcePolicy",
    "AcquireSourceMetadata",
    "AcquireArtifact",
    "AcquireTranscript",
    "NormalizeArtifact",
    "SegmentArtifact",
    "ExtractMetadata",
    "AnalyzeDuplicates",
    "CreateEvidenceCandidate",
    "RequestHumanReview",
    "RecordReviewDecision",
    "RetryTask",
    "CancelTask",
    "SuppressWorkflow",
    "ReclaimTask",
)

# ---------------------------------------------------------------------------
# Contract Catalog section J -- events (34) + MOGO-011 extensions (5 + 1) = 40
# ---------------------------------------------------------------------------

# MOGO-011 Step 1 additive extension, approved 2026-08-07. Five names were
# added because the MOGO-009 set could not express four approved task
# transitions or two command-lifecycle facts, and Constitution section 6.6 with
# Architecture section 18.1 require an event for every transition -- otherwise
# task state cannot be derived from the log as ADR-012 D-05 requires. Additive
# only: nothing was renamed, removed or repurposed (Architecture section 11).
#
#   CommandAccepted            command validated, idempotency key claimed
#   CommandRejected            command failed validation
#   TaskRequested              task created in `requested`
#   TaskPolicyCheckRequested   requested -> policy_check
#   TaskStarted                claimed -> running
#
# MOGO-011 Step 2 additive extension, approved 2026-08-08 (decision B-1). ONE
# name was added, for the same reason and under the same provision:
#
#   TaskRetryReleased          retry_scheduled -> queued
#
# Catalog section L declares that edge with authority `orchestrator` and
# condition "backoff elapsed"; Catalog section J names no event for it. The
# only other approved event landing in `queued` is TaskReclaimed, whose meaning
# is "an abandoned claim was recovered" -- overloading it would make a retry
# indistinguishable from an abandonment, which Constitution section 4.18
# forbids by requiring retries to remain visible. Modelling eligibility with no
# event at all was rejected outright: task state would then be a function of
# the wall clock rather than of the log, and rebuild() would produce different
# states at different times, breaking ADR-012 D-05.
#
# The name follows the section J past-participle convention. `TaskRequeued` was
# rejected as ambiguous with TaskReclaimed, which also results in `queued`.

EVENT_TYPES = (
    "CommandAccepted",
    "CommandRejected",
    "TaskRequested",
    "TaskPolicyCheckRequested",
    "TaskStarted",
    "TaskRetryReleased",
    "SourceDiscoveryRequested",
    "SourceDiscovered",
    "SourceRegistered",
    "PolicyEvaluated",
    "AcquisitionAuthorized",
    "AcquisitionDenied",
    "ArtifactAcquisitionRequested",
    "ArtifactAcquired",
    "ArtifactAcquisitionFailed",
    "TranscriptAcquired",
    "RawArtifactRegistered",
    "ArtifactNormalized",
    "ArtifactSegmented",
    "MetadataExtracted",
    "DuplicateCandidateDetected",
    "EvidenceCandidateCreated",
    "HumanReviewRequired",
    "HumanReviewCompleted",
    "SourceMutationDetected",
    "TaskClaimed",
    "TaskReclaimed",
    "TaskRetryScheduled",
    "TaskSucceeded",
    "TaskFailed",
    "TaskDeadLettered",
    "WorkflowStarted",
    "WorkflowCompleted",
    "WorkflowFailed",
    "WorkflowSuppressed",
    "CheckpointVerified",
    "CheckpointInvalidated",
    "PartialArtifactQuarantined",
    "RecoveryOverrideIssued",
    "SecretAccessed",
)

# ---------------------------------------------------------------------------
# Contract Catalog section B -- executionResult vocabulary
# ---------------------------------------------------------------------------

EXECUTION_RESULTS = ("success", "failure", "partial")

# ---------------------------------------------------------------------------
# Contract Catalog section M -- licensing / access classification (12)
# ---------------------------------------------------------------------------
# Per-operation permission values. A closed set, so a status can never carry a
# free-text permission.

ALLOWED = "ALLOWED"
DENIED = "DENIED"
AS_RECORDED = "AS_RECORDED"                       # "per licence" / "per policy"
LOCATOR_ONLY = "LOCATOR_ONLY"                     # store the locator, retrieve nothing
ALREADY_GATHERED_ONLY = "ALREADY_GATHERED_ONLY"   # no new acquisition of any kind

PERMISSION_VALUES = (
    ALLOWED, DENIED, AS_RECORDED, LOCATOR_ONLY, ALREADY_GATHERED_ONLY,
)


def _status(metadata, transcript, artifact, permits_acquisition):
    return MappingProxyType({
        "metadata": metadata,
        "transcript": transcript,
        "artifact": artifact,
        "permitsAcquisition": permits_acquisition,
    })


LICENSING_STATUSES = MappingProxyType({
    "PERMITTED_PUBLIC_METADATA":   _status(ALLOWED, DENIED, DENIED, True),
    "PERMITTED_PUBLIC_TRANSCRIPT": _status(ALLOWED, ALLOWED, DENIED, True),
    "PERMITTED_PUBLIC_ARTIFACT":   _status(ALLOWED, ALLOWED, ALLOWED, True),
    "PERMITTED_EXPLICIT_LICENSE":  _status(AS_RECORDED, AS_RECORDED, AS_RECORDED, True),
    "PERMITTED_DOCUMENTED_POLICY": _status(AS_RECORDED, AS_RECORDED, AS_RECORDED, True),
    "METADATA_ONLY":               _status(ALLOWED, DENIED, DENIED, True),
    "LINK_ONLY":                   _status(LOCATOR_ONLY, DENIED, DENIED, True),
    # Catalog section M footnote 1: the "minimum to evaluate" allowance covers
    # metadata ALREADY gathered before a classification existed. No new
    # acquisition of any kind occurs under this status.
    "HUMAN_REVIEW_REQUIRED":       _status(ALREADY_GATHERED_ONLY, DENIED, DENIED, False),
    "AUTHENTICATION_REQUIRED":     _status(DENIED, DENIED, DENIED, False),
    "RESTRICTED":                  _status(DENIED, DENIED, DENIED, False),
    "PROHIBITED":                  _status(DENIED, DENIED, DENIED, False),
    # Constitution section 5.2 and ADR-012 approval 12: UNKNOWN behaves
    # EXACTLY as PROHIBITED. Absence of a known permission is not permission.
    # The two records below are required to be identical, and a test asserts it.
    "UNKNOWN":                     _status(DENIED, DENIED, DENIED, False),
})

LICENSING_STATUS_NAMES = tuple(LICENSING_STATUSES.keys())

# ---------------------------------------------------------------------------
# Contract Catalog section O -- capability lifecycle states (7)
# ---------------------------------------------------------------------------
# Names only. No registry, no transition rules, no dispatch eligibility.
# See ADR-012 D-16: implementation is a later, separately approved step.

CAPABILITY_LIFECYCLE_STATES = (
    "proposed",
    "experimental",
    "approved",
    "production",
    "deprecated",
    "disabled",
    "retired",
)

"""Shared deterministic utilities for PROGRAM-006 Phase 1A (Evidence Intelligence
Engine, ADR-008).

Pure Python standard library. NO NETWORK ACCESS ANYWHERE IN THIS MODULE.

Reuses graph_common.py's canonical JSON / hashing / atomic-write utilities
rather than duplicating them, exactly like acquisition_common.py does.
"""
import glob as globmod
import json
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import graph_common as gc  # noqa: E402  (canonical_json_bytes, sha256_hex, content_hash_of, pretty_json, atomic_write_text)

# ---------------------------------------------------------------------------
# Controlled vocabularies (kept in sync with the JSON schemas by a dedicated test)
# ---------------------------------------------------------------------------

SOURCE_TYPES = [
    "transcript", "video", "audio", "article", "book", "note", "strategy_document",
    "paper_trade", "replay_observation", "screenshot", "live_trade_review", "journal_entry",
    "market_observation", "owner_observation", "generated_analysis", "other",
]
STORAGE_LOCATION_TYPES = ["repository", "external"]
PROVENANCE_STATUSES = ["unverified", "partially_verified", "verified"]
SOURCE_LIFECYCLE_STATUSES = ["registered", "under_review", "active", "superseded", "archived", "rejected"]

EVIDENCE_TYPES = [
    "explicit_statement", "demonstrated_behavior", "chart_example", "trade_example",
    "rule_statement", "exception_statement", "opinion", "intuition", "prediction",
    "post_trade_observation", "replay_result", "paper_trade_result", "market_context",
    "failure_observation", "success_observation", "risk_observation", "execution_observation",
    "unresolved_question", "other",
]
EVIDENCE_QUALITIES = ["unknown", "low", "medium", "high"]
EVIDENCE_STATUSES = ["active", "superseded", "retracted", "disputed"]
EXTRACTION_METHODS = ["manual_owner_entry", "manual_transcription", "derived_analysis", "other"]

CLAIM_TYPES = [
    "definition", "marketCondition", "setup_requirement", "entry_rule", "confirmation_rule",
    "invalidation_rule", "stop_rule", "target_rule", "risk_rule", "trade_management_rule",
    "session_rule", "timeframe_rule", "failure_condition", "success_condition", "exception",
    "causal_hypothesis", "performance_hypothesis", "behavioral_observation", "other",
]
CLAIM_STATUSES = ["active", "pending_review", "superseded", "retracted", "merged"]
CONFIDENCE_STATES = [
    "insufficient_evidence", "tentative", "emerging", "supported", "strongly_supported",
    "contested", "weakened", "contradicted", "unresolved",
]

RELATIONSHIP_TYPES = ["supports", "contradicts", "weakens", "contextualizes", "exemplifies", "qualifies", "supersedes", "unresolved"]
_SUPPORTING_RELATIONSHIPS = {"supports", "exemplifies"}
_CONTRADICTING_RELATIONSHIPS = {"contradicts"}
_WEAKENING_RELATIONSHIPS = {"weakens"}
_CONTEXTUAL_RELATIONSHIPS = {"contextualizes", "qualifies", "supersedes", "unresolved"}

# NOTE (MOGO-020 Step 1 audit finding, deliberately NOT repaired here):
# "INTAKE_MANIFEST" exists in this constant but has never been added to
# evidence-lifecycle-event.schema.json's entityType enum or eventId pattern.
# That pre-existing code/schema drift is reported, not fixed -- repairing it is
# outside MOGO-020's mandate and belongs to a separate operator decision.
# "EVIDENCE_QUESTION" (MOGO-020 Step 2) WAS added to both places together.
LIFECYCLE_ENTITY_TYPES = ["EVIDENCE_SOURCE", "EVIDENCE_ITEM", "CLAIM", "EVIDENCE_CLAIM_LINK", "CONTRADICTION_RECORD",
                          "INTAKE_MANIFEST", "EVIDENCE_QUESTION"]
LIFECYCLE_EVENT_TYPES = ["created", "status_changed", "confidence_recomputed", "superseded", "corrected", "linked", "unlinked", "reviewed", "other"]

CONTRADICTION_TYPES = ["DEFINITIONAL", "NUMERIC_THRESHOLD", "CONDITIONAL_SCOPE", "TEMPORAL_DRIFT", "DIRECTIONAL", "SCOPE_MISMATCH", "OTHER"]
CONTRADICTION_SEVERITIES = ["cosmetic", "minor", "material", "blocking"]
CONTRADICTION_STATUSES = ["open", "resolved_by_owner", "superseded", "accepted_as_context_dependent"]

INTEGRITY_SEVERITIES = ["INFO", "WARNING", "ERROR", "FATAL"]
INTEGRITY_RESOLUTION_STATUSES = ["open", "acknowledged", "resolved"]

SCHEMA_VERSION = 1
SYNTHETIC_MARKERS = ("SYNTHETIC TEST DATA", "NOT REAL TJR RESEARCH")

# ---------------------------------------------------------------------------
# PROGRAM-006 Phase 1B (ADR-009) -- explainability, directness, extraction
# certainty, and controlled TJR intake vocabularies.
# ---------------------------------------------------------------------------

# Evidence directness: how explicit/observed vs. inferred a piece of evidence
# is. Kept strictly separate from evidenceQuality (ADR-009 sec. 4/Deliverable 4).
DIRECTNESS_CLASSIFICATIONS = [
    "direct_explicit", "direct_demonstrated", "indirect_implied",
    "inferred_from_context", "derived_from_analysis", "owner_observation", "unresolved",
]

# Extraction certainty: confidence that a source was interpreted correctly.
# Never conflated with claim confidence, evidence quality, or profitability
# (ADR-009 sec. 10/Deliverable 5).
EXTRACTION_CERTAINTY_LEVELS = ["certain", "high", "moderate", "low", "ambiguous", "unresolved"]

# IntakeManifest lifecycle (Deliverable 6).
INTAKE_STATUSES = [
    "discovered", "registered", "validated", "ready_for_extraction",
    "extraction_in_progress", "extracted", "review_required", "approved", "rejected",
    "duplicate", "superseded", "blocked", "failed",
]
INTAKE_EXTRACTION_STATUSES = ["not_started", "in_progress", "completed", "failed"]
INTAKE_REVIEW_STATUSES = ["not_required", "pending", "in_review", "approved", "rejected"]
INTAKE_DUPLICATE_STATUSES = ["unknown", "unique", "duplicate", "possible_duplicate"]

# Transcript ingestion (Deliverable 7/8).
TRANSCRIPT_FORMATS = ["plain_text", "timestamped_text", "structured_json"]
SEGMENT_TYPES = [
    "narration", "instruction", "example", "question", "answer", "disclaimer",
    "promotion", "introduction", "conclusion", "chart_commentary", "trade_commentary", "other",
]

# Manual annotation (Deliverable 10).
ANNOTATION_REVIEW_STATUSES = ["draft", "submitted", "approved", "rejected", "applied"]

# EvidenceQuestion (Deliverable 13 -- named to avoid colliding with the
# pre-existing Wave-1 UNRESOLVED_QUESTION entity; see ADR-009 sec. 12).
QUESTION_TYPES = [
    "ambiguous_statement", "implied_requirement", "self_contradiction",
    "behavior_conflicts_with_instruction", "unclear_scope", "missing_timeframe",
    "missing_session", "missing_invalidation", "missing_stop_placement",
    "missing_target_logic", "discretionary_management", "unruled_exception",
    "example_mismatch", "insufficient_independent_support", "missing_replay_validation",
    "missing_paper_validation", "other",
]
QUESTION_PRIORITIES = ["low", "medium", "high", "critical"]
QUESTION_BLOCKING_STATUSES = ["non_blocking", "blocks_rule_candidate", "blocks_promotion"]
QUESTION_RESEARCH_STATUSES = ["open", "researching", "answered", "deferred"]
QUESTION_ANSWER_STATUSES = ["unanswered", "partially_answered", "answered"]

# Review queues (Deliverable 14).
REVIEW_QUEUE_TYPES = [
    "low_certainty_evidence", "ambiguous_evidence", "inferred_evidence",
    "duplicate_candidates", "contradiction_candidates", "contested_claims",
    "unresolved_questions", "rule_candidates", "incomplete_transcripts",
    "unresolved_licensing", "missing_provenance", "insufficient_independent_evidence",
    "supersession_review", "extraction_failures",
]
REVIEW_QUEUE_ENTITY_TYPES = [
    "EVIDENCE_SOURCE", "EVIDENCE_ITEM", "CLAIM", "CONTRADICTION_RECORD",
    "EVIDENCE_QUESTION", "RULE_CANDIDATE_PROPOSAL", "INTAKE_MANIFEST", "TRANSCRIPT_SEGMENT",
]
REVIEW_QUEUE_REVIEW_STATUSES = ["open", "in_review", "resolved", "dismissed"]

# RuleCandidateProposal (Deliverable 12 -- distinct from StrategyRule, see
# ADR-009 sec. 8).
RULE_CANDIDATE_ELIGIBLE_CLAIM_TYPES = [
    "setup_requirement", "entry_rule", "confirmation_rule", "invalidation_rule",
    "stop_rule", "target_rule", "risk_rule", "trade_management_rule", "session_rule",
    "timeframe_rule", "failure_condition", "exception",
]
RULE_CANDIDATE_STATUSES = ["proposed", "superseded", "withdrawn"]
RULE_CANDIDATE_CONTRADICTION_STATUSES = ["none", "open_contradiction", "resolved_contradiction"]
RULE_CANDIDATE_VALIDATION_STATUSES = ["not_available", "pending", "validated", "failed"]
RULE_CANDIDATE_OWNER_REVIEW_STATUSES = ["not_reviewed", "pending", "approved", "rejected"]

EXPLANATION_SCHEMA_VERSION = 1

# ---------------------------------------------------------------------------
# PROGRAM-007 Phase 7A (Knowledge Library vertical slice) vocabularies.
# ---------------------------------------------------------------------------

PROFILE_CONCEPT_STATUSES = ["confirmed", "inferred", "conflicting"]

BLUEPRINT_STATUSES = ["DRAFT_RESEARCH_ONLY", "SUPERSEDED"]
BLUEPRINT_STAGE_CLASSIFICATIONS = ["required", "preferred", "optional", "forbidden", "unknown"]
BLUEPRINT_RESEARCH_STATUSES = ["draft", "under_review", "reviewed"]
BLUEPRINT_VALIDATION_STATUSES = ["not_available", "pending", "in_progress", "validated", "failed"]

GAP_CATEGORIES = [
    "instrument", "session", "higher_timeframe_bias", "execution_timeframe", "setup_sequence",
    "entry_trigger", "confirmation", "invalidation", "stop_placement", "risk_percentage",
    "target_selection", "trade_management", "news_handling", "spread_handling",
    "volatility_handling", "no_trade_conditions", "exception_handling",
]
GAP_ANSWER_STATUSES = ["unanswered", "partially_answered", "answered"]
GAP_CONFIDENCE_LEVELS = ["none", "low", "moderate", "high"]

HYPOTHESIS_STATUSES = ["PROPOSED_UNVALIDATED", "UNDER_RESEARCH", "SUPPORTED", "REFUTED", "WITHDRAWN"]

# Deliverable 7: the 8 actions a reviewer may take on any Knowledge Library
# item awaiting review. Never auto-applied -- always an explicit human choice.
REVIEW_ACTIONS = [
    "approve_as_supported_claim", "approve_as_inferred_claim", "reject", "mark_contradictory",
    "request_more_evidence", "convert_to_research_question", "propose_hypothesis", "leave_unresolved",
]


# ---------------------------------------------------------------------------
# MOGO-020 (governed research answer intake) vocabularies.
#
# These are the HUMAN semantic decisions the machine records -- never the ones
# it makes. Deliberately three values, mapped onto the EvidenceQuestion statuses
# that already exist (QUESTION_ANSWER_STATUSES / QUESTION_RESEARCH_STATUSES);
# no new question status was invented for this milestone.
# ---------------------------------------------------------------------------

ADJUDICATION_DECISIONS = ["accepted", "rejected", "uncertain"]

# The rulings an operator may record on a ContradictionRecord. Every target is
# an EXISTING CONTRADICTION_STATUSES value; "leave_open" is a real recorded
# decision that deliberately changes no status at all.
CONTRADICTION_RULINGS = {
    "resolved": "resolved_by_owner",
    "scope_qualified": "accepted_as_context_dependent",
    "superseded": "superseded",
    "leave_open": "open",
}

# A ruling/adjudication must be attributable to a HUMAN. Machine actors used
# elsewhere in the pipeline ("pipeline", "ingest", ...) are bare names; a human
# decision is namespaced, matching the convention already used by
# docs/trader-intelligence/authorizations/*.json ("operator:joemogollon").
HUMAN_ACTOR_PATTERN = re.compile(r"^(operator|reviewer):[A-Za-z0-9_.@-]+$")


class EvidenceValidationError(ValueError):
    """Raised on a fatal creation error. Carries structured findings (dicts
    matching evidence-integrity-report.schema.json's finding shape) so a
    caller can report exactly what failed without re-deriving it from the
    exception message alone."""

    def __init__(self, message, findings=None):
        super().__init__(message)
        self.findings = findings or []


def require_human_actor(actor, field="actor"):
    """Fail closed unless `actor` is an explicitly namespaced human identity
    (MOGO-020). A missing, empty, non-string or machine actor is refused rather
    than defaulted -- an unattributed semantic decision is not a governed
    decision."""
    if not isinstance(actor, str) or not HUMAN_ACTOR_PATTERN.match(actor):
        raise EvidenceValidationError(
            "%s %r is not an explicit human identity; expected 'operator:<name>' or "
            "'reviewer:<name>'. A semantic decision must be attributable to a person."
            % (field, actor))
    return actor


# ---------------------------------------------------------------------------
# Deterministic identifiers
# ---------------------------------------------------------------------------

def _next_seq(existing_dir, pattern):
    max_seq = 0
    if os.path.isdir(existing_dir):
        for path in globmod.glob(os.path.join(existing_dir, "*.json")):
            base = os.path.splitext(os.path.basename(path))[0]
            m = pattern.match(base)
            if m:
                max_seq = max(max_seq, int(m.group(1)))
    return max_seq + 1


def source_id_to_filename(sourceId):
    return sourceId.replace("|", "_") + ".json"


def next_source_id(sources_dir, trader_id_or_unattributed, now):
    date_str = now.strftime("%Y%m%d")
    scope = trader_id_or_unattributed.upper()
    pattern = re.compile(r"^EVSRC_%s_%s_(\d{3,})$" % (re.escape(scope), re.escape(date_str)))
    seq = _next_seq(sources_dir, pattern)
    return "EVSRC|%s|%s|%03d" % (scope, date_str, seq)


def evidence_id_to_filename(evidenceId):
    return evidenceId.replace("|", "_") + ".json"


def next_evidence_id(items_dir, sourceId, now):
    prefix = ("EV_" + sourceId.replace("|", "_") + "_")
    pattern = re.compile(r"^%s(\d{3,})$" % re.escape(prefix))
    seq = _next_seq(items_dir, pattern)
    return "EV|%s|%03d" % (sourceId, seq)


def claim_id_to_filename(claimId):
    return claimId.replace("|", "_") + ".json"


def next_claim_id(claims_dir, scope, now):
    scope = (scope or "GENERIC").upper()
    date_str = now.strftime("%Y%m%d")
    pattern = re.compile(r"^CLAIM_%s_%s_(\d{3,})$" % (re.escape(scope), re.escape(date_str)))
    seq = _next_seq(claims_dir, pattern)
    return "CLAIM|%s|%s|%03d" % (scope, date_str, seq)


_LINK_ID_MAX_LEN = 200


def make_link_id(evidenceId, claimId):
    raw = "LINK|%s|%s" % (evidenceId, claimId)
    if len(raw) <= _LINK_ID_MAX_LEN:
        return raw
    digest = gc.sha256_hex(("%s|%s" % (evidenceId, claimId)).encode("utf-8"))[:12]
    return "LINK|%s|%s~%s" % (evidenceId[:60], claimId[:60], digest)


def link_id_to_filename(linkId):
    return gc.sha256_hex(linkId.encode("utf-8"))[:32] + ".json"


_LCEVT_SEQ_PATTERN = re.compile(r"\|(\d{3,})$")


def next_lifecycle_event_id(lifecycle_dir, entityType, entityId, now):
    """Lifecycle events are saved under hash-derived filenames (see
    lifecycle_event_id_to_filename below), so -- unlike sources/evidence/
    claims, whose filenames literally encode their id -- a filename-pattern
    scan can never find prior events for this entity. Sequencing must instead
    read each existing event's own recorded entityType/entityId/eventId."""
    max_seq = 0
    if os.path.isdir(lifecycle_dir):
        for path in globmod.glob(os.path.join(lifecycle_dir, "*.json")):
            with open(path, "r", encoding="utf-8") as f:
                existing = json.load(f)
            if existing.get("entityType") == entityType and existing.get("entityId") == entityId:
                m = _LCEVT_SEQ_PATTERN.search(existing.get("eventId", ""))
                if m:
                    max_seq = max(max_seq, int(m.group(1)))
    return "LCEVT|%s|%s|%03d" % (entityType, entityId, max_seq + 1)


def lifecycle_event_id_to_filename(eventId):
    return gc.sha256_hex(eventId.encode("utf-8"))[:32] + ".json"


def next_contradiction_id(contradictions_dir, now):
    date_str = now.strftime("%Y%m%d")
    pattern = re.compile(r"^XCONTRA_%s_(\d{3,})$" % re.escape(date_str))
    seq = _next_seq(contradictions_dir, pattern)
    return "XCONTRA|%s|%03d" % (date_str, seq)


def contradiction_id_to_filename(contradictionId):
    return contradictionId.replace("|", "_") + ".json"


def make_integrity_report_id(now, seq=1):
    return "EVIDENCE_INTEGRITY|%s|%03d" % (now.strftime("%Y%m%d"), seq)


# ---------------------------------------------------------------------------
# PROGRAM-006 Phase 1B (ADR-009) deterministic identifiers. All filenames here
# are literal (id.replace("|", "_") + ".json"), never hash-derived, so the
# straightforward filename-pattern sequencing below is safe -- it does not
# repeat the lifecycle-event hashed-filename bug fixed above.
# ---------------------------------------------------------------------------

def intake_id_to_filename(intakeId):
    return intakeId.replace("|", "_") + ".json"


def next_intake_id(intake_dir, trader_id_or_unattributed, now):
    date_str = now.strftime("%Y%m%d")
    scope = (trader_id_or_unattributed or "UNATTRIBUTED").upper()
    pattern = re.compile(r"^INTAKE_%s_%s_(\d{3,})$" % (re.escape(scope), re.escape(date_str)))
    seq = _next_seq(intake_dir, pattern)
    return "INTAKE|%s|%s|%03d" % (scope, date_str, seq)


def segment_id_to_filename(segmentId):
    return segmentId.replace("|", "_") + ".json"


def next_segment_id(segments_dir, intakeId, now):
    prefix = "TSEG_" + intakeId.replace("|", "_") + "_"
    pattern = re.compile(r"^%s(\d{3,})$" % re.escape(prefix))
    seq = _next_seq(segments_dir, pattern)
    return "TSEG|%s|%03d" % (intakeId, seq)


def annotation_id_to_filename(annotationId):
    return annotationId.replace("|", "_") + ".json"


def next_annotation_id(annotations_dir, intakeId, now):
    prefix = "ANNOT_" + intakeId.replace("|", "_") + "_"
    pattern = re.compile(r"^%s(\d{3,})$" % re.escape(prefix))
    seq = _next_seq(annotations_dir, pattern)
    return "ANNOT|%s|%03d" % (intakeId, seq)


def question_id_to_filename(questionId):
    return questionId.replace("|", "_") + ".json"


def next_question_id(questions_dir, now):
    date_str = now.strftime("%Y%m%d")
    pattern = re.compile(r"^EQ_%s_(\d{3,})$" % re.escape(date_str))
    seq = _next_seq(questions_dir, pattern)
    return "EQ|%s|%03d" % (date_str, seq)


def queue_entry_id_to_filename(queueEntryId):
    return queueEntryId.replace("|", "_") + ".json"


def next_queue_entry_id(queue_dir, queueType, now):
    date_str = now.strftime("%Y%m%d")
    scope = queueType.upper()
    pattern = re.compile(r"^RQ_%s_%s_(\d{3,})$" % (re.escape(scope), re.escape(date_str)))
    seq = _next_seq(queue_dir, pattern)
    return "RQ|%s|%s|%03d" % (scope, date_str, seq)


def proposal_id_to_filename(proposalId):
    return proposalId.replace("|", "_") + ".json"


def next_proposal_id(proposals_dir, now):
    date_str = now.strftime("%Y%m%d")
    pattern = re.compile(r"^RCPROP_%s_(\d{3,})$" % re.escape(date_str))
    seq = _next_seq(proposals_dir, pattern)
    return "RCPROP|%s|%03d" % (date_str, seq)


def text_sha256(text):
    return gc.sha256_hex((text or "").encode("utf-8"))


# ---------------------------------------------------------------------------
# PROGRAM-007 Phase 7A (Knowledge Library) deterministic identifiers. Literal
# filenames (id.replace("|", "_") + ".json"), matching the source/claim/
# proposal convention -- never hash-derived, so filename-pattern sequencing
# is safe here.
# ---------------------------------------------------------------------------

def profile_id_to_filename(profileId):
    return profileId.replace("|", "_") + ".json"


def next_profile_id(profiles_dir, trader_id, now):
    date_str = now.strftime("%Y%m%d")
    scope = trader_id.upper()
    pattern = re.compile(r"^PROFILE_%s_%s_(\d{3,})$" % (re.escape(scope), re.escape(date_str)))
    seq = _next_seq(profiles_dir, pattern)
    return "PROFILE|%s|%s|%03d" % (scope, date_str, seq)


def blueprint_id_to_filename(blueprintId):
    return blueprintId.replace("|", "_") + ".json"


def next_blueprint_id(blueprints_dir, trader_id, now):
    date_str = now.strftime("%Y%m%d")
    scope = trader_id.upper()
    pattern = re.compile(r"^BLUEPRINT_%s_%s_(\d{3,})$" % (re.escape(scope), re.escape(date_str)))
    seq = _next_seq(blueprints_dir, pattern)
    return "BLUEPRINT|%s|%s|%03d" % (scope, date_str, seq)


def gap_id_to_filename(gapId):
    return gapId.replace("|", "_") + ".json"


def next_gap_id(gaps_dir, now):
    date_str = now.strftime("%Y%m%d")
    pattern = re.compile(r"^GAP_%s_(\d{3,})$" % re.escape(date_str))
    seq = _next_seq(gaps_dir, pattern)
    return "GAP|%s|%03d" % (date_str, seq)


def observation_id_to_filename(observationId):
    return observationId.replace("|", "_") + ".json"


def next_observation_id(observations_dir, actor, now):
    """TOBS|<HUMAN|MOGO>|<date>|<seq>.

    The actor is IN the identifier because a trade observation is the one record
    type that carries both an operator's screenshot of a human trade and MOGO's own
    decision. Keeping the actor in the id means the two can never be silently
    conflated when they are compared against each other (MOGO-019 gap 2), and the
    sequence counters advance independently per actor.
    """
    if actor not in ("HUMAN", "MOGO"):
        raise EvidenceValidationError(
            "actor %r must be 'HUMAN' or 'MOGO'; a trade observation whose origin is "
            "unknown cannot be used in a human-vs-MOGO comparison." % (actor,))
    date_str = now.strftime("%Y%m%d")
    pattern = re.compile(r"^TOBS_%s_%s_(\d{3,})$"
                         % (re.escape(actor), re.escape(date_str)))
    seq = _next_seq(observations_dir, pattern)
    return "TOBS|%s|%s|%03d" % (actor, date_str, seq)


def hypothesis_id_to_filename(hypothesisId):
    return hypothesisId.replace("|", "_") + ".json"


def next_hypothesis_id(hypotheses_dir, now):
    date_str = now.strftime("%Y%m%d")
    pattern = re.compile(r"^HYP_%s_(\d{3,})$" % re.escape(date_str))
    seq = _next_seq(hypotheses_dir, pattern)
    return "HYP|%s|%03d" % (date_str, seq)


# ---------------------------------------------------------------------------
# Claim normalization / fingerprinting (Deliverable 6)
# ---------------------------------------------------------------------------

def normalize_claim_text(text):
    """Deterministic, offline text normalization: NFKC unicode normalization,
    lowercase, collapse whitespace, strip trailing punctuation. No NLP, no
    stemming -- intentionally simple and fully explainable."""
    text = unicodedata.normalize("NFKC", text or "")
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[.!?]+$", "", text)
    return text


def compute_claim_fingerprint(normalizedClaim, traderId=None, strategyFamilyId=None,
                               timeframe=None, session=None, marketCondition=None):
    """SHA-256 over the canonicalized (normalizedClaim, scope...) tuple. Two
    claims differing only in scope (timeframe/session/marketCondition/trader/
    family) must never fingerprint identically -- scope is part of the tuple,
    not discarded (this is the exact requirement Deliverable 6 calls out with
    its four-example scoped-variation case)."""
    tuple_obj = {
        "normalizedClaim": normalize_claim_text(normalizedClaim),
        "traderId": traderId, "strategyFamilyId": strategyFamilyId,
        "timeframe": timeframe, "session": session, "marketCondition": marketCondition,
    }
    return gc.content_hash_of(tuple_obj)


_NEAR_DUP_THRESHOLD = 0.85


def near_duplicate_ratio(text_a, text_b):
    import difflib
    return difflib.SequenceMatcher(None, normalize_claim_text(text_a), normalize_claim_text(text_b)).ratio()


def is_near_duplicate(text_a, text_b, threshold=_NEAR_DUP_THRESHOLD):
    return near_duplicate_ratio(text_a, text_b) >= threshold


# ---------------------------------------------------------------------------
# Lifecycle / audit helpers
# ---------------------------------------------------------------------------

def build_lifecycle_event(lifecycle_dir, entityType, entityId, eventType, actor, now,
                           priorStatus=None, newStatus=None, reason=None, metadata=None):
    if entityType not in LIFECYCLE_ENTITY_TYPES:
        raise EvidenceValidationError("Unknown entityType %r" % (entityType,))
    if eventType not in LIFECYCLE_EVENT_TYPES:
        raise EvidenceValidationError("Unknown eventType %r" % (eventType,))
    eventId = next_lifecycle_event_id(lifecycle_dir, entityType, entityId, now)
    return {
        "eventId": eventId, "entityType": entityType, "entityId": entityId,
        "eventType": eventType, "priorStatus": priorStatus, "newStatus": newStatus,
        "reason": reason, "actor": actor, "timestamp": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "metadata": metadata or {}, "schemaVersion": SCHEMA_VERSION,
    }


def write_lifecycle_event(lifecycle_dir, event):
    path = os.path.join(lifecycle_dir, lifecycle_event_id_to_filename(event["eventId"]))
    gc.atomic_write_text(path, gc.pretty_json(event))
    return path


def contains_synthetic_markers(text):
    if not text:
        return False
    upper = text.upper()
    return any(marker in upper for marker in SYNTHETIC_MARKERS)

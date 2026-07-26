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
    "paper_trade", "replay_observation", "live_trade_review", "journal_entry",
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
CLAIM_STATUSES = ["active", "superseded", "retracted", "merged"]
CONFIDENCE_STATES = [
    "insufficient_evidence", "tentative", "emerging", "supported", "strongly_supported",
    "contested", "weakened", "contradicted", "unresolved",
]

RELATIONSHIP_TYPES = ["supports", "contradicts", "weakens", "contextualizes", "exemplifies", "qualifies", "supersedes", "unresolved"]
_SUPPORTING_RELATIONSHIPS = {"supports", "exemplifies"}
_CONTRADICTING_RELATIONSHIPS = {"contradicts"}
_WEAKENING_RELATIONSHIPS = {"weakens"}
_CONTEXTUAL_RELATIONSHIPS = {"contextualizes", "qualifies", "supersedes", "unresolved"}

LIFECYCLE_ENTITY_TYPES = ["EVIDENCE_SOURCE", "EVIDENCE_ITEM", "CLAIM", "EVIDENCE_CLAIM_LINK", "CONTRADICTION_RECORD"]
LIFECYCLE_EVENT_TYPES = ["created", "status_changed", "confidence_recomputed", "superseded", "corrected", "linked", "unlinked", "reviewed", "other"]

CONTRADICTION_TYPES = ["DEFINITIONAL", "NUMERIC_THRESHOLD", "CONDITIONAL_SCOPE", "TEMPORAL_DRIFT", "DIRECTIONAL", "SCOPE_MISMATCH", "OTHER"]
CONTRADICTION_SEVERITIES = ["cosmetic", "minor", "material", "blocking"]
CONTRADICTION_STATUSES = ["open", "resolved_by_owner", "superseded", "accepted_as_context_dependent"]

INTEGRITY_SEVERITIES = ["INFO", "WARNING", "ERROR", "FATAL"]
INTEGRITY_RESOLUTION_STATUSES = ["open", "acknowledged", "resolved"]

SCHEMA_VERSION = 1
SYNTHETIC_MARKERS = ("SYNTHETIC TEST DATA", "NOT REAL TJR RESEARCH")


class EvidenceValidationError(ValueError):
    """Raised on a fatal creation error. Carries structured findings (dicts
    matching evidence-integrity-report.schema.json's finding shape) so a
    caller can report exactly what failed without re-deriving it from the
    exception message alone."""

    def __init__(self, message, findings=None):
        super().__init__(message)
        self.findings = findings or []


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

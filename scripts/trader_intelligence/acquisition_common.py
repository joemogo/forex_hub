"""Shared deterministic utilities for PROGRAM-004 Phase 1 (Research Acquisition
and Prioritization Engine).

Pure Python standard library. NO NETWORK ACCESS ANYWHERE IN THIS MODULE.

`urllib.parse` is used below for pure string parsing/reassembly of URLs (host,
path, query string). It performs no network I/O -- unlike `urllib.request`,
which this module never imports. Normalizing a URL never fetches it.

Reuses graph_common.py's canonical JSON / hashing / atomic-write utilities
rather than duplicating them.
"""
import glob as globmod
import os
import re
import sys
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import graph_common as gc  # noqa: E402  (reused: canonical_json_bytes, sha256_hex, content_hash_of, pretty_json, atomic_write_text)

# ---------------------------------------------------------------------------
# Controlled vocabularies (kept in sync with the JSON schemas by a dedicated test)
# ---------------------------------------------------------------------------

ACQUISITION_STATUSES = [
    "DISCOVERED", "REGISTERED", "METADATA_PENDING", "METADATA_VERIFIED",
    "DUPLICATE_REVIEW", "PRIORITIZED", "OWNER_REVIEW", "APPROVED_FOR_ACQUISITION",
    "ACQUISITION_IN_PROGRESS", "ACQUIRED", "ACQUISITION_FAILED",
    "APPROVED_FOR_EXTRACTION", "EXTRACTION_IN_PROGRESS", "EXTRACTED",
    "READY_FOR_RESEARCH_INTAKE", "APPROVED_FOR_RESEARCH_INTAKE", "REJECTED", "ARCHIVED",
]

# DISCOVERED never appears as a persisted status -- it is the in-memory,
# pre-validation moment before a candidate file is ever written. Every other
# state below is a real, persistable value.
ALLOWED_TRANSITIONS = {
    "DISCOVERED": {"REGISTERED"},
    "REGISTERED": {"METADATA_PENDING", "METADATA_VERIFIED", "REJECTED", "ARCHIVED"},
    "METADATA_PENDING": {"METADATA_VERIFIED", "REJECTED", "ARCHIVED"},
    "METADATA_VERIFIED": {"DUPLICATE_REVIEW", "REJECTED", "ARCHIVED"},
    "DUPLICATE_REVIEW": {"PRIORITIZED", "REJECTED", "ARCHIVED"},
    "PRIORITIZED": {"OWNER_REVIEW", "REJECTED", "ARCHIVED"},
    "OWNER_REVIEW": {"APPROVED_FOR_ACQUISITION", "REJECTED", "ARCHIVED"},
    "APPROVED_FOR_ACQUISITION": {"ACQUISITION_IN_PROGRESS", "REJECTED", "ARCHIVED"},
    "ACQUISITION_IN_PROGRESS": {"ACQUIRED", "ACQUISITION_FAILED", "ARCHIVED"},
    "ACQUISITION_FAILED": {"APPROVED_FOR_ACQUISITION", "ARCHIVED"},
    "ACQUIRED": {"APPROVED_FOR_EXTRACTION", "REJECTED", "ARCHIVED"},
    "APPROVED_FOR_EXTRACTION": {"EXTRACTION_IN_PROGRESS", "ARCHIVED"},
    "EXTRACTION_IN_PROGRESS": {"EXTRACTED", "ARCHIVED"},
    "EXTRACTED": {"READY_FOR_RESEARCH_INTAKE", "REJECTED", "ARCHIVED"},
    "READY_FOR_RESEARCH_INTAKE": {"APPROVED_FOR_RESEARCH_INTAKE", "REJECTED", "ARCHIVED"},
    "APPROVED_FOR_RESEARCH_INTAKE": {"ARCHIVED"},
    "REJECTED": {"ARCHIVED"},
    "ARCHIVED": set(),
}

# Transitions that MUST be backed by an active OwnerDecision (approvalScope
# "acquisition") referencing the candidate's candidateId in affectedEntityIds.
OWNER_DECISION_REQUIRED_TRANSITIONS = {
    ("OWNER_REVIEW", "APPROVED_FOR_ACQUISITION"),
    ("ACQUISITION_FAILED", "APPROVED_FOR_ACQUISITION"),
    ("READY_FOR_RESEARCH_INTAKE", "APPROVED_FOR_RESEARCH_INTAKE"),
}
# REJECTED from any state also requires an OwnerDecision (checked separately,
# since it applies uniformly rather than as one specific (from, to) pair).

DISCOVERY_METHODS = [
    "MANUAL_URL", "PLAYLIST_URL", "CHANNEL_URL", "SEARCH_RESULTS_URL", "ARTICLE_URL",
    "UPLOADED_TEXT", "PDF_REFERENCE", "OWNER_NOTE",
]
URL_REQUIRED_DISCOVERY_METHODS = {"MANUAL_URL", "PLAYLIST_URL", "CHANNEL_URL", "SEARCH_RESULTS_URL", "ARTICLE_URL"}

PLATFORMS = ["YOUTUBE", "ARTICLE_WEB", "PDF", "LOCAL_UPLOAD", "OWNER_NOTE", "UNKNOWN"]

AUTHENTICITY_STATUSES = [
    "VERIFIED_PRIMARY", "LIKELY_PRIMARY", "VERIFIED_SECONDARY", "LIKELY_SECONDARY",
    "UNVERIFIED", "MISATTRIBUTED", "REJECTED",
]
HEURISTIC_ALLOWED_AUTHENTICITY = {"LIKELY_PRIMARY", "LIKELY_SECONDARY", "UNVERIFIED"}
OWNER_ONLY_AUTHENTICITY = {"VERIFIED_PRIMARY", "VERIFIED_SECONDARY", "MISATTRIBUTED", "REJECTED"}

DUPLICATE_STATUSES = [
    "NONE", "EXACT_DUPLICATE", "POSSIBLE_NEAR_DUPLICATE", "DERIVATIVE",
    "EXCERPT", "UPDATED_VERSION", "RELATED_BUT_DISTINCT", "UNCERTAIN",
]
AUTOMATIC_ALLOWED_DUPLICATE_STATUSES = {"NONE", "EXACT_DUPLICATE", "POSSIBLE_NEAR_DUPLICATE"}

STORAGE_POLICIES = ["METADATA_ONLY", "REFERENCED_LOCAL_CONTENT", "COMMITTED_OWNER_CONTENT"]

TOPICS = [
    "OVERALL_STRATEGY", "MARKET_STRUCTURE", "LIQUIDITY", "SESSIONS", "ENTRIES", "EXITS",
    "STOP_PLACEMENT", "TARGETS", "RISK_MANAGEMENT", "TRADE_MANAGEMENT", "PSYCHOLOGY",
    "JOURNALING", "BACKTESTING", "REPLAY", "TRADE_FAILURE", "MISSED_TRADE",
    "FALSE_POSITIVE", "FALSE_NEGATIVE", "MISTAKES", "LIVE_TRADE", "TRADE_RECAP",
    "Q_AND_A", "BEGINNER_EDUCATION", "ADVANCED_EDUCATION", "PROMOTIONAL_CONTENT",
    "LIFESTYLE_CONTENT", "NON_STRATEGY_CONTENT",
]
CLASSIFIED_FROM_VALUES = [
    "URL_DERIVED", "TITLE_DERIVED", "DESCRIPTION_DERIVED",
    "TRANSCRIPT_DERIVED", "OWNER_PROVIDED", "OWNER_CONFIRMED",
]
TITLE_DERIVED_MAX_CONFIDENCE = "medium"
ONLY_CONFIRMED_SOURCE = "OWNER_CONFIRMED"

ALLOWED_UPLOAD_EXTENSIONS = {".txt", ".md", ".pdf"}
MAX_TEXT_SIZE_BYTES = 2_000_000  # 2 MB cap on pasted/uploaded plain text in Phase 1

_TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "fbclid", "gclid"}
_YOUTUBE_TRACKING_PARAMS = {"si", "feature", "ab_channel", "pp"}


# ---------------------------------------------------------------------------
# Deterministic identifiers
# ---------------------------------------------------------------------------

def candidate_id_to_filename(candidate_id):
    """Filesystem-safe mapping, used consistently everywhere a candidateId
    becomes a filename -- pipes are replaced with underscores. next_candidate_id
    below scans using this exact same mapping so the two can never diverge."""
    return candidate_id.replace("|", "_") + ".json"


def next_candidate_id(candidates_dir, now):
    """CAND|MOGO|{YYYYMMDD}|{seq}. Collision prevention: scans every existing
    candidate filename under candidates_dir (via candidate_id_to_filename's
    mapping) for today's date segment and takes max(seq)+1; starts at 1 if
    none exist for today. candidateId never depends on claimedTraderId/
    verifiedTraderId/title/creatorName/URL."""
    date_str = now.strftime("%Y%m%d")
    max_seq = 0
    pattern = re.compile(r"^CAND_MOGO_%s_(\d{3,})$" % re.escape(date_str))
    if os.path.isdir(candidates_dir):
        for path in globmod.glob(os.path.join(candidates_dir, "*.json")):
            base = os.path.splitext(os.path.basename(path))[0]
            m = pattern.match(base)
            if m:
                max_seq = max(max_seq, int(m.group(1)))
    return "CAND|MOGO|%s|%03d" % (date_str, max_seq + 1)


def make_score_id(candidate_id, seq):
    return "SCORE|%s|%03d" % (candidate_id, seq)


def make_duplicate_group_id(date_str, seq):
    return "DUPGROUP|%s|%03d" % (date_str, seq)


def make_queue_build_id(date_str, seq):
    return "QUEUE|%s|%03d" % (date_str, seq)


# ---------------------------------------------------------------------------
# URL normalization (no network access -- pure string parsing)
# ---------------------------------------------------------------------------

_YT_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}


def _strip_www_m(host):
    host = host.lower()
    if host.startswith("m."):
        host = host[2:]
    if host.startswith("www."):
        host = host[4:]
    return host


def _parse_timestamp_to_seconds(raw):
    """Accepts a bare integer ('90'), a trailing-'s' integer ('90s'), or
    YouTube's compact 'XhYmZs' form (any subset, e.g. '1h2m3s', '2m', '45s')."""
    if raw is None:
        return None
    if raw.isdigit():
        return int(raw)
    if raw.endswith("s") and raw[:-1].isdigit():
        return int(raw[:-1])
    m = re.match(r"^(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$", raw)
    if not m or not any(m.groups()):
        return None
    h, mi, s = (int(g) if g else 0 for g in m.groups())
    return h * 3600 + mi * 60 + s


def normalize_url(url):
    """Returns {normalizedUrl, platform, videoId, playlistId, channelId,
    timestampSeconds, sourceTypeHint}. Fully deterministic, zero network
    access -- string parsing only."""
    parts = urlsplit(url.strip())
    host = _strip_www_m(parts.netloc)
    query_pairs = parse_qsl(parts.query, keep_blank_values=True)
    query = dict(query_pairs)

    if host in _YT_HOSTS or parts.netloc.lower() in _YT_HOSTS:
        return _normalize_youtube(parts, host, query)

    # Generic web URL (article / PDF / other): strip known tracking params,
    # preserve every other query parameter and the full path untouched --
    # unknown parameters may be meaningful to the article's identity.
    kept = [(k, v) for k, v in query_pairs if k not in _TRACKING_PARAMS]
    new_query = urlencode(kept)
    normalized = urlunsplit((parts.scheme or "https", parts.netloc, parts.path, new_query, ""))
    source_hint = "PDF" if parts.path.lower().endswith(".pdf") else "ARTICLE_WEB"
    return {
        "normalizedUrl": normalized, "platform": source_hint if source_hint == "PDF" else "ARTICLE_WEB",
        "videoId": None, "playlistId": None, "channelId": None,
        "timestampSeconds": None, "sourceTypeHint": "ARTICLE" if source_hint == "ARTICLE_WEB" else "COURSE_MATERIAL",
    }


def _normalize_youtube(parts, host, query):
    path = parts.path.rstrip("/")
    timestamp_seconds = _parse_timestamp_to_seconds(query.get("t") or query.get("start"))
    playlist_id = query.get("list")

    if host == "youtu.be":
        video_id = path.lstrip("/")
        normalized = "https://www.youtube.com/watch?v=%s" % video_id
        return {
            "normalizedUrl": normalized, "platform": "YOUTUBE", "videoId": video_id,
            "playlistId": playlist_id, "channelId": None,
            "timestampSeconds": timestamp_seconds, "sourceTypeHint": "VIDEO",
        }

    if path == "/watch" and "v" in query:
        video_id = query["v"]
        normalized = "https://www.youtube.com/watch?v=%s" % video_id
        return {
            "normalizedUrl": normalized, "platform": "YOUTUBE", "videoId": video_id,
            "playlistId": playlist_id, "channelId": None,
            "timestampSeconds": timestamp_seconds, "sourceTypeHint": "VIDEO",
        }

    if path.startswith("/shorts/"):
        video_id = path[len("/shorts/"):]
        normalized = "https://www.youtube.com/shorts/%s" % video_id
        return {
            "normalizedUrl": normalized, "platform": "YOUTUBE", "videoId": video_id,
            "playlistId": playlist_id, "channelId": None,
            "timestampSeconds": timestamp_seconds, "sourceTypeHint": "SHORT_VIDEO",
        }

    if path == "/playlist" and "list" in query:
        normalized = "https://www.youtube.com/playlist?list=%s" % query["list"]
        return {
            "normalizedUrl": normalized, "platform": "YOUTUBE", "videoId": None,
            "playlistId": query["list"], "channelId": None,
            "timestampSeconds": None, "sourceTypeHint": "PLAYLIST",
        }

    if path.startswith("/channel/"):
        channel_id = path[len("/channel/"):]
        normalized = "https://www.youtube.com/channel/%s" % channel_id
        return {
            "normalizedUrl": normalized, "platform": "YOUTUBE", "videoId": None,
            "playlistId": None, "channelId": channel_id,
            "timestampSeconds": None, "sourceTypeHint": "CHANNEL",
        }

    if path.startswith("/@"):
        handle = path[2:].lower()
        normalized = "https://www.youtube.com/@%s" % handle
        return {
            "normalizedUrl": normalized, "platform": "YOUTUBE", "videoId": None,
            "playlistId": None, "channelId": "@" + handle,
            "timestampSeconds": None, "sourceTypeHint": "CHANNEL",
        }

    if path.startswith("/c/"):
        name = path[len("/c/"):].lower()
        normalized = "https://www.youtube.com/c/%s" % name
        return {
            "normalizedUrl": normalized, "platform": "YOUTUBE", "videoId": None,
            "playlistId": None, "channelId": "c/" + name,
            "timestampSeconds": None, "sourceTypeHint": "CHANNEL",
        }

    if path == "/results" and "search_query" in query:
        normalized_query = " ".join(query["search_query"].lower().split())
        normalized = "https://www.youtube.com/results?search_query=%s" % normalized_query.replace(" ", "+")
        return {
            "normalizedUrl": normalized, "platform": "YOUTUBE", "videoId": None,
            "playlistId": None, "channelId": None,
            "timestampSeconds": None, "sourceTypeHint": "SEARCH_RESULTS_PAGE",
        }

    # Unrecognized YouTube URL shape -- preserve as-is rather than guessing.
    normalized = urlunsplit(("https", "www.youtube.com", parts.path, parts.query, ""))
    return {
        "normalizedUrl": normalized, "platform": "YOUTUBE", "videoId": None,
        "playlistId": playlist_id, "channelId": None,
        "timestampSeconds": timestamp_seconds, "sourceTypeHint": "VIDEO",
    }


# ---------------------------------------------------------------------------
# Local-file safety
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Offline topic classification (simple keyword heuristic -- not NLP, always
# disclosed as such via classifiedFrom/confidence)
# ---------------------------------------------------------------------------

_TOPIC_KEYWORDS = {
    "ENTRIES": ["entry", "entries", "trigger"],
    "EXITS": ["exit", "exits"],
    "STOP_PLACEMENT": ["stop loss", "stop-loss", "stop placement"],
    "TARGETS": ["target", "take profit", "tp "],
    "RISK_MANAGEMENT": ["risk management", "position size", "risk per trade"],
    "TRADE_MANAGEMENT": ["trade management", "managing a trade"],
    "PSYCHOLOGY": ["psychology", "mindset", "discipline", "emotions"],
    "JOURNALING": ["journal", "journaling"],
    "BACKTESTING": ["backtest", "backtesting"],
    "REPLAY": ["replay"],
    "LIVE_TRADE": ["live trade", "live trading"],
    "TRADE_RECAP": ["recap", "trade recap", "review of my trades"],
    "Q_AND_A": ["q&a", "q & a", "questions and answers"],
    "MARKET_STRUCTURE": ["market structure", "break of structure", "bos"],
    "LIQUIDITY": ["liquidity", "liquidity sweep", "liquidity grab"],
    "SESSIONS": ["session", "london session", "new york session", "asian session"],
    "BEGINNER_EDUCATION": ["beginner", "for beginners", "getting started"],
    "ADVANCED_EDUCATION": ["advanced"],
    "PROMOTIONAL_CONTENT": ["sign up", "discount code", "affiliate", "join my", "my course", "enroll now"],
    "LIFESTYLE_CONTENT": ["vlog", "day in my life", "lifestyle", "morning routine"],
    "MISTAKES": ["mistake", "mistakes i made"],
    "TRADE_FAILURE": ["why i lost", "losing trade", "what went wrong"],
}


def classify_topics(title, description, text_content, now):
    """Simple, disclosed keyword heuristic -- never claims NLP-level understanding.
    Preference order for evidence: text_content (transcript/note) > description > title.
    TITLE_DERIVED is capped at 'medium' confidence; only an explicit owner
    confirmation (not implemented by this function) may use OWNER_CONFIRMED."""
    assessed_at = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    results = []
    seen_topics = set()

    def scan(text, classified_from, max_confidence):
        if not text:
            return
        lowered = text.lower()
        for topic, keywords in _TOPIC_KEYWORDS.items():
            if topic in seen_topics:
                continue
            for kw in keywords:
                if kw in lowered:
                    confidence = "high" if classified_from == "TRANSCRIPT_DERIVED" else max_confidence
                    results.append({
                        "topic": topic, "confidence": confidence, "classifiedFrom": classified_from,
                        "evidenceReference": kw, "assessedAt": assessed_at,
                    })
                    seen_topics.add(topic)
                    break

    scan(text_content, "TRANSCRIPT_DERIVED", "high")
    scan(description, "DESCRIPTION_DERIVED", "medium")
    scan(title, "TITLE_DERIVED", TITLE_DERIVED_MAX_CONFIDENCE)
    return results


# ---------------------------------------------------------------------------
# Offline authenticity heuristic (never produces an owner-only status)
# ---------------------------------------------------------------------------

def assess_authenticity_heuristic(creator_name, claimed_trader_id, ti_root):
    """Reads real TraderRecord aliases/displayName (read-only) to check whether
    creator_name plausibly matches a known trader. Returns one of
    HEURISTIC_ALLOWED_AUTHENTICITY only -- never an owner-only status."""
    if not creator_name:
        return "UNVERIFIED"
    creator_lower = creator_name.strip().lower()
    traders_dir = os.path.join(ti_root, "traders")
    if os.path.isdir(traders_dir):
        for profile_path in globmod.glob(os.path.join(traders_dir, "*", "profile.json")):
            import json
            with open(profile_path, "r", encoding="utf-8") as f:
                profile = json.load(f)
            candidates_for_match = [profile.get("displayName", "")] + profile.get("aliases", [])
            for name in candidates_for_match:
                if name and name.strip().lower() == creator_lower:
                    if claimed_trader_id and claimed_trader_id == profile.get("traderId"):
                        return "LIKELY_PRIMARY"
                    return "LIKELY_SECONDARY"
    return "LIKELY_SECONDARY" if claimed_trader_id else "UNVERIFIED"


class IllegalTransitionError(ValueError):
    pass


def advance_status(candidate, new_status, now, reason, owner_decision_id=None, actor=None):
    """Validates against ALLOWED_TRANSITIONS and OWNER_DECISION_REQUIRED_TRANSITIONS
    before mutating candidate['acquisitionStatus'] in place and appending a
    changeLog entry. Raises IllegalTransitionError and mutates nothing on any
    failure -- callers never need to roll back. Every changeLog entry records
    priorStatus/newStatus explicitly (PROGRAM-004 Correction 2) so the full
    status history -- including the very first DISCOVERED -> REGISTERED
    transition -- remains reconstructable from changeLog alone."""
    current = candidate["acquisitionStatus"]
    if new_status not in ACQUISITION_STATUSES:
        raise IllegalTransitionError("Unknown acquisitionStatus %r" % (new_status,))
    if new_status not in ALLOWED_TRANSITIONS.get(current, set()):
        raise IllegalTransitionError("Illegal transition %s -> %s" % (current, new_status))
    needs_decision = (current, new_status) in OWNER_DECISION_REQUIRED_TRANSITIONS or new_status == "REJECTED"
    if needs_decision and not owner_decision_id:
        raise IllegalTransitionError(
            "Transition %s -> %s requires an active OwnerDecision (approvalScope=acquisition)" % (current, new_status))
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    candidate["acquisitionStatus"] = new_status
    if owner_decision_id and owner_decision_id not in candidate.get("ownerDecisionIds", []):
        candidate.setdefault("ownerDecisionIds", []).append(owner_decision_id)
    candidate.setdefault("changeLog", []).append({
        "changedAt": now_iso, "changedFields": ["acquisitionStatus"], "reason": reason,
        "priorStatus": current, "newStatus": new_status,
        "discoveryMethod": candidate.get("discoveryMethod"), "actor": actor or candidate.get("submittedBy"),
    })
    candidate["updatedAt"] = now_iso
    return candidate


def validate_local_reference(path, allowed_root):
    """Raises ValueError on path traversal or an unsupported extension.
    Returns the resolved absolute path if safe."""
    ext = os.path.splitext(path)[1].lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        raise ValueError("Unsupported file extension %r (allowed: %s)" % (ext, sorted(ALLOWED_UPLOAD_EXTENSIONS)))
    resolved_root = os.path.realpath(allowed_root)
    candidate = os.path.realpath(os.path.join(allowed_root, path))
    if os.path.commonpath([resolved_root, candidate]) != resolved_root:
        raise ValueError("Path traversal rejected: %r escapes %r" % (path, allowed_root))
    return candidate

#!/usr/bin/env python3
"""MOGO-002.7 — machine-readable artifact generator (offline, read-only inputs).

Emits the JSON equivalents of the MOGO-002.7 Markdown deliverables:

  MOGO-002.7-blocking-gap-checklist.json
  MOGO-002.7-gap-states.json
  MOGO-002.7-kerev-a-stop-placement-evidence.json
  MOGO-002.7-source-coverage-report.json
  MOGO-002.7-acquisition-queue.json

Design constraints, matching MOGO-002.5/002.6:

  * Reads the evidence store; never writes to it. Counts are RECOMPUTED from
    docs/trader-intelligence/evidence/ rather than copied from the MOGO-002.6
    package, so a stale summary cannot propagate.
  * Deterministic: no clock, no randomness, no dict-iteration dependence.
    Re-running on an unchanged evidence store reproduces byte-identical output.
  * Writes only into docs/knowledge-engineering/ via atomic_write_text.
  * Never fabricates a source parameter. Where the educator did not state a
    value, the field is null and the reason is recorded.

Usage:  python3 scripts/knowledge_engineering/build_mogo_002_7_artifacts.py
"""
import glob
import json
import os
import re
import sys
from collections import Counter, defaultdict

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts", "trader_intelligence"))

import graph_common as gc  # noqa: E402

EVIDENCE_ROOT = os.path.join(REPO_ROOT, "docs", "trader-intelligence", "evidence")
KE_DIR = os.path.join(REPO_ROOT, "docs", "knowledge-engineering")

MILESTONE = "MOGO-002.7"
MODEL_VERSION = "mogo.source-acquisition.v1"

# The ten blocking domains named in the MOGO-002.7 brief, in brief order.
# Patterns are matched over exactExcerpt + normalizedObservation, lowercased.
BLOCKING_DOMAINS = [
    ("BG-01", "STOP_PLACEMENT", "RISK",
     [r"\bstop\b", r"\bstop[- ]loss", r"\bsl\b", r"\bstopped out\b"]),
    ("BG-02", "POSITION_SIZING", "RISK",
     [r"\brisk\b.*\b(percent|%)", r"\b1\s*%", r"\blot size", r"\bposition size",
      r"\bsizing\b", r"\bequity\b"]),
    ("BG-03", "TAKE_PROFIT", "EXIT",
     [r"\btake profit", r"\btp\b", r"\btarget\b", r"\brisk[- ]to[- ]reward",
      r"\brisk reward", r"\br:r\b", r"\b1:\d", r"\breward\b"]),
    ("BG-04", "TRADE_MANAGEMENT", "TRADE_MANAGEMENT",
     [r"\bmanage", r"\bset and forget", r"\bmove (my |the )?stop",
      r"\bonce (i'm |im |i am )?in\b"]),
    ("BG-05", "EXIT", "EXIT",
     [r"\bexit\b", r"\bclose (the |my |out)", r"\bclosing\b", r"\bget out\b",
      r"\bcut (the |my )?(trade|loss)"]),
    ("BG-06", "BREAK_EVEN", "TRADE_MANAGEMENT",
     [r"\bbreak[- ]?even\b"]),
    ("BG-07", "PARTIAL_PROFIT", "TRADE_MANAGEMENT",
     [r"\bpartial", r"\btake (some|half|profit off)", r"\bsecure (some )?profit"]),
    ("BG-08", "SCALING", "TRADE_MANAGEMENT",
     [r"\bscal(e|ing) (in|out)", r"\badd(ing)? to (the |my )?position", r"\bpyramid"]),
]

RULE_BEARING_CLAIM_TYPES = (
    "stop_rule", "risk_rule", "target_rule", "trade_management_rule",
    "invalidation_rule", "entry_rule", "setup_requirement", "confirmation_rule",
    "session_rule", "timeframe_rule",
)

# The provided source. Metadata was VERIFIED against the YouTube oEmbed endpoint;
# the transcript was supplied by the operator on 2026-07-29 and INGESTED.
PROVIDED_SOURCE = {
    "candidateId": "ACQCAND|ALEX_G|20260729|001",
    "sourceId": "EVSRC|ALEX_G|20260729|001",
    "intakeId": "INTAKE|ALEX_G|20260729|001",
    "title": "This Trading Strategy Made Me $26,000 in Just 12 Hours",
    "url": "https://www.youtube.com/watch?v=kg-rOo9_xjU",
    "platform": "youtube",
    "videoId": "kg-rOo9_xjU",
    "channelOrPublisher": "fxalexg",
    "channelUrl": "https://www.youtube.com/@fxalexg__",
    "claimedTraderId": "ALEX_G",
    "verifiedTraderId": "ALEX_G",
    "traderIdVerificationMethod": (
        "YouTube oEmbed author_url for kg-rOo9_xjU resolves to "
        "https://www.youtube.com/@fxalexg__, byte-identical to the author_url of "
        "already-registered EVSRC|ALEX_G|20260728|005 (VzMlFZbWA0Y). Same channel, "
        "therefore same educator lineage."
    ),
    "titleVerificationMethod": "YouTube oEmbed title field, exact match to the title supplied in the brief.",
    "metadataConfidence": "high",
    "authenticityStatus": "channel_verified",
    "acquisitionStatus": "acquired_operator_supplied",
    "processingStatus": "ingested",
    "durationSeconds": None,
    "publicationDate": None,
    "transcriptAvailable": True,
    "contentHash": "7f954e14ec5cb0a6b17de28fb0e6caed6910e6cc4f2ec72c8c6cc3b3441e58d2",
    "contentSizeBytes": 15232,
    "sourceLineCount": 92,
    "repositoryPath": ("docs/trader-intelligence/imports/alex-g/raw/"
                       "alexg-break-and-retest-26k-12-hours.raw.txt"),
    "normalizationProfile": "youtube_duration_label",
    "normalizationReversible": True,
    "segments": 13,
    "annotations": 36,
    "claimsCreated": 31,
    "licensingStatus": "restricted_third_party",
}

STOP_EVIDENCE_CLASSIFICATION = {
    # evidenceId -> (classification, why). Classification vocabulary is the one
    # the MOGO-002.7 brief Phase 6 requires.
    "EV|EVSRC|ALEX_G|20260727|001|020": (
        "INCOMPLETE",
        "Establishes that a wrong trend origin invalidates the stop-loss. Says nothing about where "
        "the stop is placed. Names the stop as one of five things affected, which confirms he treats "
        "stop placement as a definite decision -- without stating it.",
    ),
    "EV|EVSRC|ALEX_G|20260728|001|019": (
        "INCOMPLETE",
        "Establishes that the lower timeframe is used to judge how much ROOM the stop needs. This is "
        "the closest statement in the library to a placement rule and it still names no reference "
        "price and no buffer.",
    ),
    "EV|EVSRC|ALEX_G|20260728|002|010": (
        "NOT_A_STOP_STATEMENT",
        "Opinion on whether institutions deliberately target retail stops. Bears on the liquidity-sweep "
        "narrative, not on placement.",
    ),
    "EV|EVSRC|ALEX_G|20260728|002|011": (
        "NOT_A_STOP_STATEMENT",
        "Unsourced market-composition statistic (retail stops as 3% of the market). No placement content.",
    ),
    "EV|EVSRC|ALEX_G|20260728|005|033": (
        "LEXICAL_FALSE_POSITIVE",
        "The phrase is 'stop losing money' -- a beginner objective, not a stop-loss. Retained in the "
        "package so the Authority can see the matcher was not tuned to produce a convenient zero.",
    ),
    # ---- Added by the 2026-07-29 ingestion of EVSRC|ALEX_G|20260729|001 ----
    "EV|EVSRC|ALEX_G|20260729|001|023": (
        "EXAMPLE_DEMONSTRATED_PLACEMENT",
        "TRADE 1. The first ALEX_G evidence in nine sources that places a stop at all: 'you would have "
        "put your stop loss right under this point', spoken over the chart. States the RELATIONSHIP "
        "(immediately beyond the rejection structure) and leaves the ANCHOR deictic and the DISTANCE "
        "unstated.",
    ),
    "EV|EVSRC|ALEX_G|20260729|001|026": (
        "EXAMPLE_DEMONSTRATED_PLACEMENT",
        "TRADE 2. Second consistent demonstration, same construction. Corroborates the relationship "
        "within the same source; adds no parameter.",
    ),
    "EV|EVSRC|ALEX_G|20260729|001|028": (
        "EXPLICIT_RULE",
        "TRADE 3, and the decisive item. 'it's literally the same thing every single time your "
        "stop- loss is right under it' GENERALISES the two demonstrations into an invariant. This is "
        "the statement that converts stop placement from absent to partially supported: it is a "
        "rule_statement with directness direct_explicit, not a chart aside.",
    ),
    "EV|EVSRC|ALEX_G|20260729|001|027": (
        "TRADE_MANAGEMENT_NOT_PLACEMENT",
        "The stopped-out trade is accepted without intervention ('it is what it is it happens'). "
        "Evidence about what happens AFTER the stop is set, not about where it goes. Counted under "
        "KEGAP-006, not KEGAP-001.",
    ),
    "EV|EVSRC|ALEX_G|20260729|001|033": (
        "NOT_A_STOP_STATEMENT",
        "The 'set and forget' identification. Matched only because the domain patterns include "
        "'set and forget'. Relevant to KEGAP-006; contains no placement content.",
    ),
}

# Statements that would have to be invented to implement the stop rule as stated.
STOP_RESIDUAL_UNKNOWNS = [
    {
        "id": "STOP-UNK-1",
        "missing": "The buffer distance beyond the anchor",
        "detail": ("No unit of any kind is given -- not pips, not an ATR multiple, not a percentage, "
                   "and not an explicit 'flush against the structure'. Position size = risk / stop "
                   "distance, so the 13 sizing rules remain non-computable."),
        "severity": "BLOCKING",
        "openQuestion": "missing_stop_placement / critical / blocks_rule_candidate",
    },
    {
        "id": "STOP-UNK-2",
        "missing": "The identity of the anchor ('it' / 'this point')",
        "detail": ("Three readings are each consistent with the words and the chart narration: (a) the "
                   "low of the final rejection/engulfing candle, (b) the low of the whole Morning Star "
                   "formation, (c) the far boundary of the retested zone. They give materially "
                   "different stop distances on the same setup."),
        "severity": "BLOCKING",
        "openQuestion": "unclear_scope / high / blocks_rule_candidate",
    },
    {
        "id": "STOP-UNK-3",
        "missing": "The short-side mirror",
        "detail": ("All three demonstrations are longs and the phrasing is always 'right under'. The "
                   "symmetric 'right above' for a short is never spoken or shown, although the pattern "
                   "is stated to work in both directions."),
        "severity": "MATERIAL",
        "openQuestion": "unclear_scope / medium / blocks_rule_candidate",
    },
]


def _load_all(subdir):
    out = []
    for path in sorted(glob.glob(os.path.join(EVIDENCE_ROOT, subdir, "*.json"))):
        with open(path, encoding="utf-8") as fh:
            out.append(json.load(fh))
    return out


def load_store():
    return {
        "sources": {s["sourceId"]: s for s in _load_all("sources")},
        "items": _load_all("items"),
        "claims": {c["claimId"]: c for c in _load_all("claims")},
        "links": _load_all("links"),
        "annotations": {a["annotationId"]: a for a in _load_all("annotations")},
    }


def claim_type_census(claims):
    census = defaultdict(Counter)
    for c in claims.values():
        census[c["traderId"]][c["claimType"]] += 1
    return {trader: dict(sorted(counts.items())) for trader, counts in sorted(census.items())}


def evidence_for_domain(store, patterns, trader_prefix="EVSRC|ALEX_G"):
    ev_to_claims = defaultdict(list)
    for link in store["links"]:
        ev_to_claims[link["evidenceId"]].append(link["claimId"])

    matched = []
    for item in store["items"]:
        if not item["sourceId"].startswith(trader_prefix):
            continue
        blob = ((item.get("exactExcerpt") or "") + " " +
                (item.get("normalizedObservation") or "")).lower()
        if not any(re.search(p, blob) for p in patterns):
            continue
        claim_ids = sorted(ev_to_claims.get(item["evidenceId"], []))
        claim_types = sorted({store["claims"][cid]["claimType"]
                              for cid in claim_ids if cid in store["claims"]})
        annotation_id = (item.get("metadata") or {}).get("annotationId")
        annotation = store["annotations"].get(annotation_id or "", {})
        src = store["sources"].get(item["sourceId"], {})
        matched.append({
            "evidenceId": item["evidenceId"],
            "sourceId": item["sourceId"],
            "sourceTitle": src.get("title"),
            "canonicalReference": src.get("canonicalReference"),
            "startTimestamp": item.get("startTimestamp"),
            "endTimestamp": item.get("endTimestamp"),
            "exactExcerpt": item.get("exactExcerpt"),
            "normalizedObservation": item.get("normalizedObservation"),
            "evidenceType": item.get("evidenceType"),
            "directness": item.get("directness"),
            "extractionCertainty": item.get("extractionCertainty"),
            "evidenceQuality": item.get("evidenceQuality"),
            "claimIds": claim_ids,
            "claimTypes": claim_types,
            "recordedOpenQuestion": annotation.get("unresolvedQuestionText"),
            "annotationNotes": annotation.get("notes"),
        })
    matched.sort(key=lambda e: e["evidenceId"])
    return matched


def build_checklist(store):
    census = claim_type_census(store["claims"])
    rows = []
    for bg_id, domain, ke_domain, patterns in BLOCKING_DOMAINS:
        hits = evidence_for_domain(store, patterns)
        rows.append({
            "blockingGapId": bg_id,
            "domain": domain,
            "keDomain": ke_domain,
            "matchingEvidenceItemCount": len(hits),
            "matchingEvidenceIds": [h["evidenceId"] for h in hits],
            "ruleBearingClaimTypesPresent": sorted({
                t for h in hits for t in h["claimTypes"] if t in RULE_BEARING_CLAIM_TYPES
            }),
            "matchPatterns": patterns,
        })
    return {
        "generated": True,
        "generatorVersion": "1.0.0",
        "milestone": MILESTONE,
        "modelVersion": MODEL_VERSION,
        "narrativeArtifact": "docs/knowledge-engineering/MOGO-002.7-BLOCKING-GAP-ACQUISITION-CHECKLIST.md",
        "note": (
            "Counts are recomputed from the evidence store, not copied from MOGO-002.6. "
            "matchingEvidenceItemCount is a LEXICAL match count and is deliberately not a rule "
            "count -- see the narrative artifact, where each match is classified. A nonzero match "
            "count does not mean the domain contains a rule."
        ),
        "alexGClaimCount": sum(1 for c in store["claims"].values() if c["traderId"] == "ALEX_G"),
        "alexGEvidenceItemCount": sum(1 for i in store["items"]
                                      if i["sourceId"].startswith("EVSRC|ALEX_G")),
        "alexGSourceCount": sum(1 for s in store["sources"] if s.startswith("EVSRC|ALEX_G")),
        "claimTypeCensus": census,
        "alexGStopRuleClaimCount": census.get("ALEX_G", {}).get("stop_rule", 0),
        "rows": rows,
    }


def build_gap_states(store):
    """Phase 5 -- one terminal state per blocking gap, from the approved vocabulary."""
    gaps = [
        {
            "gapId": "KEGAP-001",
            "alsoKnownAs": ["GAP-RISK-001", "BG-01", "KEREV|058", "KEREV-A"],
            "domain": "RISK",
            "subject": "Stop-loss placement",
            "state": "PARTIALLY_SUPPORTED",
            "priorState": "ABSENT_FROM_REVIEWED_SOURCES",
            "stateChanged": True,
            "changedBy": "EVSRC|ALEX_G|20260729|001",
            "blocking": True,
            "priority": "CRITICAL",
            "evidenceBasis": (
                "ALEX_G stop_rule claims went 0 -> 2 with the ingestion of the 9th source. The decisive "
                "item is EV|EVSRC|ALEX_G|20260729|001|028 at 8:59: 'it's literally the same thing every "
                "single time your stop- loss is right under it' -- a rule_statement with directness "
                "direct_explicit that GENERALISES two prior chart demonstrations (items |023 at 7:52 and "
                "|026 at 8:25) into an invariant. The anchor is the rejection formation at the retest."
            ),
            "refinementThisMilestone": (
                "State advanced from ABSENT to PARTIALLY_SUPPORTED. The educator DOES state a stop rule. "
                "What is now missing is narrower and precisely enumerable: the buffer distance, the "
                "identity of the deictic anchor, and the short-side mirror (see STOP-UNK-1..3). "
                "Option B of KEREV-A -- 'accept stop placement as absent' -- is now factually unavailable."
            ),
            "closureRequires": (
                "A stated buffer distance in any unit, plus disambiguation of 'it'/'this point'. Both "
                "are recorded as authored open questions against the new claim."
            ),
            "notClosedBy": (
                "Choosing one of the three anchor readings, or importing MOGO's 0.25 ATR buffer. Either "
                "would be MOGO authoring a parameter and attributing it to the educator."
            ),
        },
        {
            "gapId": "KEGAP-002",
            "alsoKnownAs": ["GAP-TM-001", "BG-05"],
            "domain": "EXIT",
            "subject": "Exit methodology",
            "state": "PARTIALLY_SUPPORTED",
            "priorState": "ABSENT_FROM_REVIEWED_SOURCES",
            "stateChanged": True,
            "changedBy": "EVSRC|ALEX_G|20260729|001",
            "blocking": True,
            "priority": "CRITICAL",
            "evidenceBasis": (
                "Across three worked trades in the new source, every exit occurs at either the preset "
                "stop or the preset minimum-1:2 target. EV|EVSRC|ALEX_G|20260729|001|027 shows a losing "
                "trade allowed to reach its stop with no intervention ('it is what it is it happens'), "
                "and item |033 identifies the whole procedure as his 'set and forget' strategy."
            ),
            "refinementThisMilestone": (
                "Advanced from ABSENT to PARTIALLY_SUPPORTED, but deliberately NOT to "
                "SUPPORTED_BY_EXPLICIT_SOURCE. The exit mechanism is DEMONSTRATED (three trades, one "
                "source) and never STATED as an invariant the way the stop rule is. The pre-existing "
                "prohibition still stands alongside it: do not close on a dollar figure."
            ),
            "closureRequires": (
                "An explicit statement that a position is never closed other than at its stop or target, "
                "or a statement of any condition under which it is."
            ),
            "notClosedBy": (
                "The phrase 'set and forget' on its own, and not by three demonstrations in a single "
                "source -- same-educator repetition is not independent corroboration "
                "(DECISION|MOGO|20260727|006)."
            ),
        },
        {
            "gapId": "KEGAP-003",
            "alsoKnownAs": ["BG-09a"],
            "domain": "SESSION_RESTRICTIONS",
            "subject": "Session hours",
            "state": "UNREADABLE_OR_INSUFFICIENT_TRANSCRIPT",
            "priorState": "HIGH_BLOCKING_OPEN",
            "stateChanged": False,
            "blocking": True,
            "priority": "HIGH",
            "evidenceBasis": (
                "7 session_rule claims state the rule prescriptively; the windows are displayed on an "
                "on-screen map and never spoken. 7 of 7 SESSION_RESTRICTIONS rules are non-deterministic."
            ),
            "refinementThisMilestone": (
                "State assigned as UNREADABLE_OR_INSUFFICIENT_TRANSCRIPT rather than "
                "REQUIRES_MORE_SOURCE_ACQUISITION: the parameter exists in the source material as "
                "pixels, not words, so more transcripts of the same format cannot close it."
            ),
            "closureRequires": (
                "A source that reads the hours aloud, OR an Engineering Authority-approved method for "
                "reading parameters off the video frame -- which is not a transcript-acquisition task."
            ),
            "notClosedBy": "Further chart-annotation-style transcripts from the same channel.",
        },
        {
            "gapId": "KEGAP-004",
            "alsoKnownAs": ["BG-09b", "XCONTRA|20260729|001"],
            "domain": "MARKET_STRUCTURE",
            "subject": "Swing-point significance",
            "state": "CONTRADICTORY_SOURCE",
            "priorState": "HIGH_OPEN",
            "stateChanged": False,
            "blocking": False,
            "priority": "HIGH",
            "evidenceBasis": (
                "ALEX_G: any body close beyond a level counts, no minimum threshold. RAYNER_TEO: only "
                "major swing points. Two independent educators give contradictory guidance about a "
                "number neither supplies."
            ),
            "refinementThisMilestone": None,
            "closureRequires": "Replay sensitivity sweep (RC-29), which requires replay authorization.",
            "notClosedBy": "Source acquisition alone -- the contradiction is between stated positions, not a gap in them.",
        },
        {
            "gapId": "KEGAP-005",
            "alsoKnownAs": ["BG-03"],
            "domain": "EXIT",
            "subject": "Take-profit selection methodology",
            "state": "PARTIALLY_SUPPORTED",
            "priorState": None,
            "stateChanged": True,
            "newThisMilestone": True,
            "blocking": True,
            "priority": "HIGH",
            "evidenceBasis": (
                "target_rule claims went 4 -> 5. The new source states a FLOOR explicitly and twice: "
                "'your take profit would have been based off of a minimum of a 1 to two risk to reward' "
                "(|024, 7:52) and 'you have a minimum of a 1 to two risk to reward' (|029, 8:59), both "
                "rule_statement / direct_explicit. Pre-existing figures (80-100 pip average, 1:3, 1:4) "
                "remain recorded as illustrative."
            ),
            "refinementThisMilestone": (
                "Materially strengthened but still PARTIALLY_SUPPORTED. MOGO-002.6 recorded that no "
                "minimum R:R was stated anywhere; that is now superseded -- a 1:2 MINIMUM is explicit. "
                "What remains absent is the SELECTION PROCEDURE above the floor: the word 'minimum' "
                "implies discretion, and no rule says how a larger target is chosen. Now also "
                "contradicted -- see XCONTRA|20260729|004."
            ),
            "closureRequires": "A statement of how the target level is chosen when structure allows more than 1:2.",
            "notClosedBy": (
                "Reading the 1:2 floor as a fixed ratio. That is a DIFFERENT rule that merely coincides "
                "at the boundary, and it is how MOGO production implements minRR 2.0 -- see the KEREV-A "
                "package section on convergence."
            ),
        },
        {
            "gapId": "KEGAP-006",
            "alsoKnownAs": ["BG-04"],
            "domain": "TRADE_MANAGEMENT",
            "subject": "Post-entry trade management",
            "state": "PARTIALLY_SUPPORTED",
            "priorState": None,
            "stateChanged": True,
            "newThisMilestone": True,
            "blocking": False,
            "priority": "HIGH",
            "evidenceBasis": (
                "trade_management_rule claims went 4 -> 5. The new item |027 (8:25) is the first ALEX_G "
                "evidence of what happens to a position BETWEEN entry and exit: a losing trade is "
                "allowed to reach its stop, the loss is accepted as variance, and no adjustment, early "
                "exit or re-entry is described. Item |033 (9:57) identifies the demonstrated procedure "
                "as his 'set and forget' strategy."
            ),
            "refinementThisMilestone": (
                "Strengthened. MOGO-002.7 previously noted that 'set and forget' appeared only as a "
                "podcast-format label; in this source it is attached to a specific mechanical procedure "
                "(break-and-retest + engulfing confirmation + fixed stop + preset minimum-1:2 target), "
                "which is a materially stronger basis. Still PARTIALLY_SUPPORTED: no-intervention is "
                "demonstrated across three trades, never stated as a rule."
            ),
            "closureRequires": (
                "An explicit statement that the position is left untouched until stop or target is hit "
                "(closing this domain as a deliberate null), or any condition under which they move."
            ),
            "notClosedBy": (
                "The phrase 'set and forget' on its own. Even now that it names a procedure, it is a "
                "brand label; the no-intervention behaviour must be read from the demonstrations, and "
                "those are demonstrations rather than stated rules."
            ),
        },
        {
            "gapId": "KEGAP-007",
            "alsoKnownAs": ["BG-06"],
            "domain": "TRADE_MANAGEMENT",
            "subject": "Break-even logic",
            "state": "ABSENT_FROM_REVIEWED_SOURCES",
            "priorState": None,
            "stateChanged": True,
            "newThisMilestone": True,
            "blocking": False,
            "priority": "MEDIUM",
            "evidenceBasis": ("ZERO matching evidence items in 280 ALEX_G evidence items across 9 sources. Re-confirmed after the 2026-07-29 ingestion: the new source sets a stop and a target and never moves either, so the absence now sits alongside three worked trades in which a break-even move would have been the natural thing to mention."),
            "refinementThisMilestone": (
                "Separated from TRADE_MANAGEMENT because an absolute zero is a different acquisition "
                "problem from a thin domain. Note MOGO's replay engine documents 'never trailed or moved "
                "to break-even' as a MOGO choice, so a source statement would corroborate or contradict "
                "an existing MOGO-authored decision."
            ),
            "closureRequires": "Any statement either way.",
            "notClosedBy": "Inference from 'set and forget'.",
        },
        {
            "gapId": "KEGAP-008",
            "alsoKnownAs": ["BG-07"],
            "domain": "TRADE_MANAGEMENT",
            "subject": "Partial-profit logic",
            "state": "ABSENT_FROM_REVIEWED_SOURCES",
            "priorState": None,
            "stateChanged": True,
            "newThisMilestone": True,
            "blocking": False,
            "priority": "MEDIUM",
            "evidenceBasis": ("ZERO matching evidence items across 9 sources. No match for partial, take some off, take half, or secure profit. Re-confirmed after the 2026-07-29 ingestion, in which all three trades run to a single full-size outcome."),
            "refinementThisMilestone": None,
            "closureRequires": "Any statement either way.",
            "notClosedBy": "Inference from the fixed-percentage risk rule.",
        },
        {
            "gapId": "KEGAP-009",
            "alsoKnownAs": ["BG-08"],
            "domain": "TRADE_MANAGEMENT",
            "subject": "Scaling in or out",
            "state": "ABSENT_FROM_REVIEWED_SOURCES",
            "priorState": None,
            "stateChanged": True,
            "newThisMilestone": True,
            "blocking": False,
            "priority": "LOW",
            "evidenceBasis": (
                "ZERO matching evidence items. One near-match is explicitly not about position scaling: "
                "'what actually changed my approach to the market and was able to let me scale was risk "
                "management' -- scaling an ACCOUNT, not a position. Recorded so a future keyword pass "
                "does not mistake it for one."
            ),
            "refinementThisMilestone": (
                "Lowest priority of the management trio because the fixed-percentage rule makes "
                "single-entry the more probable default. This is a probability, NOT a finding, and is "
                "not recorded as one."
            ),
            "closureRequires": "Any statement either way.",
            "notClosedBy": "The probability argument above.",
        },
        {
            "gapId": "KEGAP-010",
            "alsoKnownAs": ["BG-10"],
            "domain": "CROSS_DOMAIN",
            "subject": "Open contradictions preventing a stable specification",
            "state": "ENGINEERING_AUTHORITY_DECISION_REQUIRED",
            "priorState": None,
            "stateChanged": True,
            "newThisMilestone": True,
            "blocking": True,
            "priority": "HIGH",
            "evidenceBasis": (
                "13 open contradictions after the 2026-07-29 ingestion (was 11): 1 blocking, 9 material, 3 minor. "
                "The two new ones are both within-educator: XCONTRA|20260729|003 (NUMERIC_THRESHOLD, minor) "
                "adds a third incompatible monthly-return range, 9-12%, against 8-10% and 7/12/15%; "
                "XCONTRA|20260729|004 (CONDITIONAL_SCOPE, material) is the consequential one -- a stated "
                "1:2 MINIMUM target versus source #8 naming a 1:4 cut to 1:2 as the core failure."
            ),
            "refinementThisMilestone": (
                "UPDATED. It remains true that NO contradiction obstructs KEGAP-001 -- stop placement is "
                "uncontested in all 9 sources. But KEGAP-005 (take-profit) is now contradicted: "
                "XCONTRA|20260729|004 asks whether 1:2 is a floor a trade may be SET at or a level a "
                "preset target must never be REVISED down to. That distinction governs whether a target "
                "may be changed after entry, so it bears on KEGAP-006 as well."
            ),
            "closureRequires": "KEREV-C decision. For the 10 marked replayCouldHelp, replay -- not authorized, not requested here.",
            "notClosedBy": "ALEX_G source acquisition, for the cross-educator subset.",
        },
    ]
    counts = Counter(g["state"] for g in gaps)
    return {
        "generated": True,
        "generatorVersion": "1.0.0",
        "milestone": MILESTONE,
        "modelVersion": MODEL_VERSION,
        "stateVocabulary": [
            "SUPPORTED_BY_EXPLICIT_SOURCE", "PARTIALLY_SUPPORTED", "DISCRETIONARY_BY_SOURCE",
            "CONTRADICTORY_SOURCE", "ABSENT_FROM_REVIEWED_SOURCES",
            "REQUIRES_MORE_SOURCE_ACQUISITION", "UNREADABLE_OR_INSUFFICIENT_TRANSCRIPT",
            "ENGINEERING_AUTHORITY_DECISION_REQUIRED",
        ],
        "absenceSemantics": (
            "ABSENT_FROM_REVIEWED_SOURCES means absent from the 8 reviewed ALEX_G sources. It is NOT a "
            "claim that the educator has never addressed the subject anywhere."
        ),
        "gapCount": len(gaps),
        "stateCounts": dict(sorted(counts.items())),
        "noGapReachedSupportedByExplicitSource": counts.get("SUPPORTED_BY_EXPLICIT_SOURCE", 0) == 0,
        "gaps": gaps,
    }


def build_kerev_a(store):
    stop_patterns = next(p for bg, d, _, p in BLOCKING_DOMAINS if bg == "BG-01")
    hits = evidence_for_domain(store, stop_patterns)
    for h in hits:
        cls, why = STOP_EVIDENCE_CLASSIFICATION.get(
            h["evidenceId"], ("UNCLASSIFIED", "Not classified by the MOGO-002.7 generator."))
        h["stopStatementClassification"] = cls
        h["classificationRationale"] = why

    by_class = Counter(h["stopStatementClassification"] for h in hits)
    return {
        "generated": True,
        "generatorVersion": "1.0.0",
        "milestone": MILESTONE,
        "modelVersion": MODEL_VERSION,
        "decisionId": "KEREV-A",
        "reviewQueueRecord": "KEREV|058",
        "relatedGapIds": ["KEGAP-001", "GAP-RISK-001"],
        "decisionStatus": "OPEN_AWAITING_ENGINEERING_AUTHORITY",
        "decidedByThisMilestone": False,
        "narrativeArtifact": "docs/knowledge-engineering/KEREV-A-STOP-PLACEMENT-EVIDENCE-PACKAGE.md",
        "alexGStopRuleClaimCount": sum(
            1 for c in store["claims"].values()
            if c["traderId"] == "ALEX_G" and c["claimType"] == "stop_rule"),
        "stopReferencingEvidenceItemCount": len(hits),
        "classificationCounts": dict(sorted(by_class.items())),
        "explicitStopPlacementRuleCount": by_class.get("EXPLICIT_RULE", 0),
        "demonstratedStopPlacementCount": by_class.get("EXAMPLE_DEMONSTRATED_PLACEMENT", 0),
        "residualUnknowns": STOP_RESIDUAL_UNKNOWNS,
        "decisionStatusAfterIngestion": "OPEN_BUT_NOW_DECIDABLE_ON_PRIMARY_SOURCE_EVIDENCE",
        "statements": hits,
        "mogoAuthoredStopLogic": {
            "extraImplementationRuleId": "ALEX_X_001",
            "title": "Entire stop-loss / take-profit / risk / R:R mechanism",
            "origin": "hub_standardization",
            "affectsTradingBehavior": True,
            "buyFormula": "stop = setup.zoneLow - stopATRBuffer * atrAtEntry",
            "sellFormula": "stop = setup.zoneHigh + stopATRBuffer * atrAtEntry",
            "stopATRBuffer": 0.25,
            "minRR": 2.0,
            "riskPercent": 1.0,
            "targetFormula": "target = entry +/- minRR * riskDistance",
            "sizeFormula": "riskAmount = balanceBefore * (riskPercent / 100)",
            "evaluators": ["alexGConstructLivePosition", "alexGComputeATRAtEntry"],
            "implementationReferences": [
                "index.html:3485 RULES_ALEXG.config.stopATRBuffer",
                "index.html:3487-3488 stop computation",
                "index.html:3494-3495 target computation",
                "index.html:3512 risk amount",
            ],
            "repositoryStatedProvenance": (
                "RULES_ALEXG.hubTestStandardizations records the stop/TP/risk/R:R mechanism as '100% "
                "unaddressed by the source'. The repository has always disclosed this."
            ),
            "whyNotAttributableToAlex": [
                "The specification field it lives in is hubTestStandardizations -- MOGO's own choices -- "
                "not originalAlexConcepts.",
                "DECISION|MOGO|20260727|004 states ALEX's constants describe what MOGO built, not what any "
                "trader teaches.",
                "traders/alex-g/profile.json states ALEX G's rules are fully specified by MOGO's own "
                "implementation, not derived from the educator's research.",
                "The 0.25 ATR buffer appears in no ALEX_G claim. No educator statement mentions ATR at all.",
                "MOGO-002.6 established that overlap between production and the educator draft is "
                "convergence, not derivation. Reading a structural resemblance as corroboration would be "
                "a lineage error.",
            ],
        },
        "authorityOptions": [
            {
                "optionId": "A",
                "option": "Acquire more ALEX_G material",
                "risks": [
                    "The provided source could not be ingested in this environment, so the option is "
                    "untested against its most promising candidate.",
                    "Eight sources already yielded zero stop rules; the base rate for this channel is poor.",
                    "KEGAP-003 shows some parameters exist only as on-screen pixels, so a further "
                    "transcript may reproduce the same failure.",
                ],
                "reversible": True,
                "costsNothingIrreversible": True,
            },
            {
                "optionId": "B",
                "option": "Accept stop placement as absent from the ALEX_G specification",
                "risks": [
                    "Permanently caps the educator draft: 13 risk rules stay non-implementable and no "
                    "ALEX_G claim becomes P&L-replayable.",
                    "Records a negative that later material could falsify, so it should be recorded as "
                    "'absent from reviewed sources', never as 'the educator does not teach it'.",
                ],
                "reversible": True,
                "costsNothingIrreversible": True,
            },
            {
                "optionId": "C",
                "option": "Define a clearly labelled MOGO-authored stop module",
                "risks": [
                    "This is what production already does; the risk is not the logic but the label.",
                    "If labelled inside a specification attributed to the educator, it fabricates lineage "
                    "-- the exact outcome KEREV|058 warns against.",
                    "Formalising 0.25 ATR would elevate a parameter that RULES_ALEXG itself flags as "
                    "EXPERIMENTAL and 'not tuned against outcomes'.",
                ],
                "reversible": True,
                "requiresExplicitLabelling": True,
            },
            {
                "optionId": "D",
                "option": "Use a separately attributed cross-educator module",
                "risks": [
                    "RAYNER_TEO states a complete stop rule (support low minus 1 ATR(20,SMA), never flush, "
                    "never tightened), so this is technically available.",
                    "Applying it to an ALEX_G setup attributes to Alex a rule he never stated -- prohibited "
                    "by governance rule 8 and by the standing note in REPLAY-CANDIDATES.md.",
                    "Would produce a hybrid strategy that is neither educator's, presented under one "
                    "educator's name.",
                ],
                "reversible": True,
                "prohibitedWithoutRelabelling": True,
            },
        ],
        "generatorRecommendation": {
            "recommendation": "A then B",
            "isDecision": False,
            "basis": (
                "Acquire against the one verified, unexhausted candidate first; if it also yields no stop "
                "rule, accept absence as a recorded property of the reviewed set. Both are reversible and "
                "neither fabricates attribution. C is acceptable only with explicit MOGO-authored "
                "labelling outside the educator specification. D should not be adopted under the ALEX_G name."
            ),
            "explicitlyNotRecommended": [
                "Deciding KEREV-A on the strength of the structural resemblance between MOGO's "
                "zone-boundary stop and the brief's description of the un-ingested video. The resemblance "
                "is real and is NOT evidence -- the transcript was never read.",
            ],
        },
    }


def build_source_coverage(store):
    """Phase 2 -- coverage report for the provided source. INGESTED 2026-07-29."""
    return {
        "generated": True,
        "generatorVersion": "2.0.0",
        "milestone": MILESTONE,
        "modelVersion": MODEL_VERSION,
        "narrativeArtifact": "docs/knowledge-engineering/MOGO-002.7-SOURCE-COVERAGE-REPORT.md",
        "source": PROVIDED_SOURCE,
        "ingested": True,
        "ingestionBlocked": False,
        "priorStopCondition": {
            "condition": "PROVIDED_TRANSCRIPT_CANNOT_BE_FOUND_OR_RECONSTRUCTED",
            "raisedAt": "MOGO-002.7 first pass",
            "resolvedBy": "Operator supplied the transcript verbatim on 2026-07-29.",
            "status": "RESOLVED",
        },
        "acceptanceClassification": "ACCEPTED_PRIMARY",
        "acceptanceRationale": (
            "Direct educator statements and three narrated chart demonstrations bearing on the blocking "
            "gaps; attribution verified to @fxalexg__; provenance complete (content hash, reversible "
            "normalization, 13 segments, every excerpt verbatim). Marketing content is heavy and is "
            "classified as such rather than discarded -- see marketingDisclosure."
        ),
        "evidenceItemsCreated": 36,
        "claimsCreated": 31,
        "supportingLinksToExistingClaims": 5,
        "candidateRulesCreated": 0,
        "candidateRulesNote": (
            "0, and this is the POLICY-001 gate working as designed: "
            "RuleCandidateProposal is created only for claims at `supported`, and every claim from this "
            "source is at `emerging` because a single source cannot corroborate itself."
        ),
        "contradictionsCreated": 2,
        "openQuestionsAuthored": 9,
        "openQuestionsAuto": 18,
        "confidenceMovement": {
            "claimsBefore": 310,
            "claimsAfter": 341,
            "statesBefore": {"emerging": 310},
            "statesAfter": {"emerging": 341},
            "maxScoreBefore": 25.62,
            "maxScoreAfter": 25.62,
            "stateChanges": 0,
            "interpretation": (
                "ZERO confidence movement, and it is not a defect. The independence group for this "
                "source is AUTHOR|ALEX_G, identical to the eight existing ALEX_G sources, so "
                "DECISION|MOGO|20260727|006 correctly refuses to count a ninth same-educator source as "
                "independent corroboration. This is the THIRD demonstration of the D2 blocker: the "
                "library can acquire a decisive new rule and still not be able to believe it."
            ),
        },
        "gapCoverage": {
            "KEGAP-001": "PARTIALLY_ADDRESSED -- anchor and invariance now stated; buffer, anchor identity and short side still absent",
            "KEGAP-002": "PARTIALLY_ADDRESSED -- exits demonstrated at preset stop or target only, across three trades",
            "KEGAP-003": "NOT_ADDRESSED -- this source says nothing about sessions or hours",
            "KEGAP-004": "NOT_CLOSED, REINFORCED -- 'minimum of one structure point' is quantified over an undefined unit",
            "KEGAP-005": "PARTIALLY_ADDRESSED -- a 1:2 MINIMUM is stated twice; selection above the floor still absent",
            "KEGAP-006": "PARTIALLY_ADDRESSED -- first evidence of no intervention between entry and exit",
            "KEGAP-007": "NOT_ADDRESSED -- break-even still zero mentions across 9 sources",
            "KEGAP-008": "NOT_ADDRESSED -- partials still zero mentions across 9 sources",
            "KEGAP-009": "NOT_ADDRESSED -- scaling still zero mentions across 9 sources",
            "KEGAP-010": "MADE_MORE_AMBIGUOUS -- two new within-educator contradictions, one material",
        },
        "gapsClosed": [],
        "gapsPartiallyAddressed": ["KEGAP-001", "KEGAP-002", "KEGAP-005", "KEGAP-006"],
        "gapsNotAddressed": ["KEGAP-003", "KEGAP-007", "KEGAP-008", "KEGAP-009"],
        "gapsMadeMoreAmbiguous": ["KEGAP-010", "KEGAP-005"],
        "noGapFullyClosed": True,
        "noGapFullyClosedNote": (
            "Deliberate. The brief warns not to claim a gap is closed because one example was shown. "
            "Three examples were shown and one invariant was stated, which moves four gaps to "
            "PARTIALLY_SUPPORTED and closes none."
        ),
        "briefDescribedContentVerification": {
            "note": (
                "The MOGO-002.7 brief predicted specific content. Now that the transcript has been read, "
                "each prediction is checked against it. This is recorded because the previous pass "
                "explicitly refused to rely on the description."
            ),
            "higherTimeframeBreakAndRetest": "CONFIRMED -- 4-hour/daily for continuation, stated at 3:29",
            "lowerTimeframeEntryConfirmation": "CONFIRMED -- 'the actual entry signal you have to go on the lower time frame', 6:47",
            "bullishBearishEngulfingConfirmation": (
                "PARTIALLY CONFIRMED -- bullish engulfing is stated as required at 7:28. BEARISH "
                "engulfing is mentioned only as a cross-reference to another video (5:33) and no "
                "short-side rule is stated or shown."
            ),
            "morningStarConfirmation": "CONFIRMED -- 'a series of bullish engulfing Morning Star formation', 7:52",
            "stopPlacementBelowOrAboveRejectionStructure": (
                "CONFIRMED FOR 'BELOW' ONLY -- 'your stop- loss is right under it', stated as invariant "
                "at 8:59. 'Above' for a short is never stated or demonstrated, so the brief's "
                "'below or above' overstates the source by one half."
            ),
            "minimum1to2RiskToReward": "CONFIRMED -- stated twice as a minimum, 8:09 and 8:59",
            "illustrative1PercentRiskExamples": (
                "CONFIRMED AS ILLUSTRATIVE -- 1% appears only inside worked arithmetic at 9:23, not as "
                "a restated risk rule. The explicit bands remain those of source #6."
            ),
        },
        "marketingDisclosure": {
            "assessment": "MARKETING_HEAVY_BUT_NOT_MARKETING_DOMINANT",
            "unverifiedMonetaryClaims": 5,
            "detail": (
                "$26,000/12h, millionaire, $37,000 live open profit, student income (lower bound "
                "unreadable), and 9-12%/month. Two funnel CTAs. Classified ACCEPTED_PRIMARY regardless "
                "because the mechanical content is genuine, specific and demonstrated -- but 6 of 31 "
                "claims are performance_hypothesis at evidenceQuality low, and none supports a rule."
            ),
        },
        "transcriptQualityNotes": [
            "Caption artifacts left uncorrected and recorded: 'breaking reetus' (break and retest), "
            "'set freet' (set and forget), 'one to2 rward', 'dogee' (doji), 'Inay' (unrecoverable).",
            "The student-income lower bound is corrupted to ',000' in both occurrences and is NOT "
            "reconstructed -- recorded as an unreadable figure.",
            "Chapter 1 heading is absent from the supplied paste; chapters 2-8 are present and were "
            "recorded as removed non-spoken lines.",
        ],
    }


def build_acquisition_queue():
    """Phase 3/4 -- ranked queue. Repository-derived target profiles plus verified candidates."""
    entries = [
        {
            "rank": 1,
            "candidateId": PROVIDED_SOURCE["candidateId"],
            "title": PROVIDED_SOURCE["title"],
            "url": PROVIDED_SOURCE["url"],
            "channelOrPublisher": PROVIDED_SOURCE["channelOrPublisher"],
            "verifiedTraderId": "ALEX_G",
            "acceptanceClassification": "ACCEPTED_PRIMARY",
            "acceptanceRationale": (
                "INGESTED 2026-07-29 as EVSRC|ALEX_G|20260729|001. Attribution verified, provenance "
                "complete, 36 verbatim excerpts, 31 claims. Contains the first ALEX_G stop-placement "
                "rule in nine sources. Upgraded from INCOMPLETE."
            ),
            "likelyTargetGaps": ["KEGAP-001", "KEGAP-005", "KEGAP-006"],
            "actualGapsAddressed": ["KEGAP-001", "KEGAP-002", "KEGAP-005", "KEGAP-006"],
            "expectedInformationValue": "VERY_HIGH",
            "realisedInformationValue": (
                "HIGH -- exceeded expectation on stop placement and take-profit, added an unexpected "
                "trade-management datum, and closed nothing outright."
            ),
            "confidence": "RESOLVED",
            "confidenceBasis": (
                "The prior MEDIUM rested on the brief's unverified description against a zero base rate "
                "over 8 sources. The description proved accurate on stop placement and 1:2 R:R, and "
                "overstated on 'below or above' -- only the long side is stated."
            ),
            "duplicationRisk": "LOW",
            "duplicationBasis": "Confirmed at ingestion: sha256 duplicate check returned 'none'.",
            "acquisitionPriority": "COMPLETE",
            "reasonSelected": "The only verified, unexhausted candidate that the brief indicated addresses stop placement.",
            "outcome": "Ingested. KEGAP-001 advanced ABSENT -> PARTIALLY_SUPPORTED. KEREV-A is now decidable but NOT resolved.",
        },
        {
            "rank": 2,
            "candidateId": "ACQTARGET|ALEX_G|COMPLETE-WALKTHROUGH",
            "title": "TARGET PROFILE -- any complete single-trade walkthrough, setup through close",
            "url": None,
            "channelOrPublisher": "https://www.youtube.com/@fxalexg__",
            "verifiedTraderId": "ALEX_G",
            "acceptanceClassification": "NOT_YET_ACQUIRED",
            "acceptanceRationale": "Target profile derived from repository knowledge, not a specific identified video.",
            "likelyTargetGaps": ["KEGAP-001", "KEGAP-002", "KEGAP-005", "KEGAP-006",
                                 "KEGAP-007", "KEGAP-008", "KEGAP-009"],
            "expectedInformationValue": "VERY_HIGH",
            "confidence": "MEDIUM_HIGH",
            "confidenceBasis": (
                "A narrated trade from setup to close must state or show the stop, the target and any "
                "post-entry action, because the trade cannot be described without them."
            ),
            "duplicationRisk": "MEDIUM",
            "duplicationBasis": "Source 006 ('Market break down learn and earn') is watchlist-style and partially overlaps.",
            "acquisitionPriority": "P0",
            "reasonSelected": (
                "Answers seven of the ten blocking rows in one artifact. A topical stop-loss video answers "
                "one. This is the highest-efficiency target in the library."
            ),
        },
        {
            "rank": 3,
            "candidateId": "ACQTARGET|ALEX_G|LIVE-SESSION-ORDER-ENTRY",
            "title": "TARGET PROFILE -- live session in which an order is actually placed",
            "url": None,
            "channelOrPublisher": "https://www.youtube.com/@fxalexg__",
            "verifiedTraderId": "ALEX_G",
            "acceptanceClassification": "NOT_YET_ACQUIRED",
            "acceptanceRationale": "Target profile; executes standing acquisition target A2-LIVE (BACKLOG-002, cycle 013).",
            "likelyTargetGaps": ["KEGAP-001", "KEGAP-005", "KEGAP-003"],
            "expectedInformationValue": "HIGH",
            "confidence": "MEDIUM_HIGH",
            "confidenceBasis": (
                "A stop price must be typed into an order ticket, so it cannot remain unstated if the "
                "order is shown being placed. Risk: it may be shown on screen and never spoken -- the "
                "KEGAP-003 failure mode."
            ),
            "duplicationRisk": "LOW",
            "acquisitionPriority": "P1",
            "reasonSelected": "Already the repository's standing recommendation A2-LIVE; independently reconfirmed here.",
        },
        {
            "rank": 4,
            "candidateId": "ACQTARGET|ALEX_G|SET-AND-FORGET-EXPLAINER",
            "title": "TARGET PROFILE -- a 'set and forget' methodology explainer",
            "url": None,
            "channelOrPublisher": "https://www.youtube.com/@fxalexg__",
            "verifiedTraderId": "ALEX_G",
            "acceptanceClassification": "NOT_YET_ACQUIRED",
            "acceptanceRationale": "Target profile.",
            "likelyTargetGaps": ["KEGAP-006", "KEGAP-007", "KEGAP-008", "KEGAP-002"],
            "expectedInformationValue": "HIGH",
            "confidence": "MEDIUM",
            "confidenceBasis": (
                "Source 007 self-identifies as episode three of a 'set and forget' podcast, so the format "
                "exists. The phrase presupposes a resting stop and target, which is exactly the "
                "break-even / partials / scaling trio."
            ),
            "duplicationRisk": "MEDIUM",
            "duplicationBasis": "Source 007 is already ingested and is one episode of this series.",
            "acquisitionPriority": "P1",
            "reasonSelected": "The only target likely to resolve three absolute-zero domains at once, possibly as deliberate nulls.",
        },
        {
            "rank": 5,
            "candidateId": "ACQTARGET|ALEX_G|COURSE-FORMAT-PARAMETERS-SPOKEN",
            "title": "TARGET PROFILE -- structured course-format material with parameters read aloud",
            "url": None,
            "channelOrPublisher": "https://www.youtube.com/@fxalexg__",
            "verifiedTraderId": "ALEX_G",
            "acceptanceClassification": "NOT_YET_ACQUIRED",
            "acceptanceRationale": "Target profile.",
            "likelyTargetGaps": ["KEGAP-003", "KEGAP-004"],
            "expectedInformationValue": "MEDIUM_HIGH",
            "confidence": "MEDIUM",
            "confidenceBasis": (
                "Direct precedent: the RAYNER_TEO course-format source read session hours, lot sizes and "
                "pip values aloud, where eight ALEX_G chart-annotation videos did not. Format, not "
                "educator, predicted parameter availability."
            ),
            "duplicationRisk": "LOW",
            "acquisitionPriority": "P2",
            "reasonSelected": "The only identified route to KEGAP-003 that does not require frame-reading approval.",
            "licensingNote": (
                "A paid course product exists for this educator. DECISION|MOGO|20260727|005 permits "
                "internal research on licensed material but any purchase is an owner decision, not an "
                "autonomous acquisition. Not pursued in this milestone."
            ),
        },
        {
            "rank": 6,
            "candidateId": "ACQCAND|THIRD-PARTY|20260729|001",
            "title": "Third-party reconstructions of the ALEX_G method (7 candidates identified, all REJECTED)",
            "url": None,
            "channelOrPublisher": "various third-party channels",
            "verifiedTraderId": None,
            "acceptanceClassification": "REJECTED",
            "acceptanceRationale": (
                "Channel ownership was verified for each via oEmbed. NONE is @fxalexg__. A third party's "
                "account of Alex's stop rule cannot establish Alex attribution, however accurate it may "
                "be -- governance rules 7 and 8. Rejected for lineage, not for quality."
            ),
            "identifiedCandidates": [
                {"videoId": "iXjrVyTAS6M", "channel": "SIR TREVOR TRADES",
                 "title": "Complete Guide Of Set And Forget Strategy by FXALEXG (Must Watch)",
                 "note": "Most likely of the seven to contain a stop rule; still cannot attribute it to Alex."},
                {"videoId": "N4ipW0VlGI8", "channel": "Nick's Trade",
                 "title": "The Set And Forget Forex Trading Strategy (By FX Alex G)"},
                {"videoId": "R4mNrUy_azU", "channel": "Vidollar",
                 "title": "I Tried FX Alex G Trading Strategy With $1000 Live Account"},
                {"videoId": "HzVSi9ux1NU", "channel": "Revelio Trading",
                 "title": "I Tried to Improve fxalexg's Trading Strategy"},
                {"videoId": "AFOp_jsm1Ak", "channel": "Chuck Index",
                 "title": "@FXALEXG Set and Forget Forex Course Review"},
                {"videoId": "kBWjkO1GCyk", "channel": "Alex Trading Reviews",
                 "title": "A Full Year With @FXALEXG's Forex Signals: RESULTS EXPOSED"},
                {"videoId": "rr1IBysoGYY", "channel": "MOBILE TRADING ACADEMY",
                 "title": "Where to Place Your Stop-Loss and Take-Profit Forex Tutorial",
                 "note": "Surfaced by a stop-loss query but unrelated to this educator entirely."},
            ],
            "likelyTargetGaps": [],
            "expectedInformationValue": "NONE_FOR_LINEAGE",
            "confidence": "HIGH",
            "duplicationRisk": "NOT_APPLICABLE",
            "acquisitionPriority": "REJECTED",
            "reasonSelected": (
                "Recorded rather than discarded because a future acquisition pass will surface these same "
                "results, and the rejection reasoning should not have to be rediscovered."
            ),
        },
        {
            "rank": 7,
            "candidateId": "ACQCAND|INTERVIEW|20260729|001",
            "title": "How This Young Trader Claims He Made $2M in 1 Year With This Simple Strategy w FxAlexG",
            "url": "https://www.youtube.com/watch?v=VMjbJCmFXMk",
            "channelOrPublisher": "Trading Nut",
            "verifiedTraderId": "ALEX_G",
            "acceptanceClassification": "ACCEPTED_SUPPORTING",
            "acceptanceRationale": (
                "A genuine edge case, recorded deliberately. The host channel is third-party, but the "
                "educator SPEAKS IN IT -- so his own statements are primary even though the publisher is "
                "not. Attribution would need to be scoped to his speech only, with the interviewer's "
                "words excluded, and the provenance record must show publisher != educator."
            ),
            "likelyTargetGaps": ["KEGAP-001", "KEGAP-005", "KEGAP-006"],
            "expectedInformationValue": "MEDIUM",
            "confidence": "LOW_MEDIUM",
            "confidenceBasis": (
                "Interview format is discursive and may never reach mechanics. Title is performance-claim "
                "framed, which correlates with MARKETING_DOMINANT content in this library."
            ),
            "duplicationRisk": "LOW",
            "acquisitionPriority": "P3",
            "reasonSelected": (
                "Interviews sometimes force explicit answers that instructional videos leave implicit, "
                "because an interviewer asks 'where do you put your stop?'."
            ),
            "governanceNote": (
                "Ingesting this would require a convention for 'educator speech on a third-party channel' "
                "that the evidence schema does not currently express. Flagged, not assumed.",
            ),
        },
    ]
    return {
        "generated": True,
        "generatorVersion": "1.0.0",
        "milestone": MILESTONE,
        "modelVersion": MODEL_VERSION,
        "narrativeArtifact": "docs/knowledge-engineering/MOGO-002.7-ACQUISITION-QUEUE.md",
        "acceptanceVocabulary": [
            "ACCEPTED_PRIMARY", "ACCEPTED_SUPPORTING", "DUPLICATIVE", "LOW_RULE_VALUE",
            "MARKETING_DOMINANT", "CONTRADICTORY", "INCOMPLETE", "REJECTED", "NOT_YET_ACQUIRED",
        ],
        "rankingBasis": (
            "Ranked by expected gap closure per artifact, never by popularity. Target profiles outrank "
            "topical videos because one complete walkthrough answers seven blocking rows."
        ),
        "entryCount": len(entries),
        "acceptedPrimaryCount": sum(1 for e in entries if e["acceptanceClassification"] == "ACCEPTED_PRIMARY"),
        "notAddedCategories": (
            "Motivational, lifestyle, challenge and marketing content was excluded unless it directly "
            "contains needed rules. Popularity was not used as a relevance signal at any point."
        ),
        "entries": entries,
    }


def main():
    store = load_store()
    artifacts = {
        "MOGO-002.7-blocking-gap-checklist.json": build_checklist(store),
        "MOGO-002.7-gap-states.json": build_gap_states(store),
        "MOGO-002.7-kerev-a-stop-placement-evidence.json": build_kerev_a(store),
        "MOGO-002.7-source-coverage-report.json": build_source_coverage(store),
        "MOGO-002.7-acquisition-queue.json": build_acquisition_queue(),
    }
    os.makedirs(KE_DIR, exist_ok=True)
    for name, obj in sorted(artifacts.items()):
        path = os.path.join(KE_DIR, name)
        gc.atomic_write_text(path, gc.pretty_json(obj))
        print(f"wrote {os.path.relpath(path, REPO_ROOT)}  "
              f"(contentHash {gc.content_hash_of(obj)[:16]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

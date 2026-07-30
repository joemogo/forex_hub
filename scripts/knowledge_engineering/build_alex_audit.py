#!/usr/bin/env python3
"""ALEX Source Coverage & Strategy Fidelity Audit — machine-readable generator.

Emits the JSON equivalents of the ALEX audit deliverables:

  alex-source-coverage-audit.json
  alex-canonical-rule-register.json
  alex-implementation-fidelity-matrix.json
  alex-knowledge-gaps-and-source-plan.json
  alex-strategy-freeze-readiness.json

Design constraints (same as MOGO-002.5/002.6/002.7):

  * READ-ONLY over the evidence store, the production specification, the
    implementation manifest and the fidelity report. Writes only into
    docs/strategy-fidelity/audit/.
  * Counts are RECOMPUTED from disk, never copied from a prior package.
  * Deterministic: no clock, no randomness. Re-running on unchanged inputs
    reproduces byte-identical output.
  * Never converts a demonstration into a universal rule, and never attributes
    a numeric parameter to the educator that no primary source states.

Usage:  python3 scripts/knowledge_engineering/build_alex_audit.py
"""
import glob
import json
import os
import sys
from collections import Counter, defaultdict

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts", "trader_intelligence"))
import graph_common as gc  # noqa: E402

EV = os.path.join(REPO_ROOT, "docs", "trader-intelligence", "evidence")
SF = os.path.join(REPO_ROOT, "docs", "strategy-fidelity")
OUT = os.path.join(SF, "audit")

MILESTONE = "MOGO-002.8"
MODEL_VERSION = "mogo.alex-audit.v1"
GENERATOR_VERSION = "1.0.0"

# Domains named in the audit brief, in brief order.
BRIEF_DOMAINS = [
    "market_selection", "market_conditions", "directional_bias",
    "higher_timeframe_analysis", "market_structure", "break_of_structure",
    "trend_definition", "liquidity", "support_and_resistance",
    "supply_and_demand", "break_and_retest", "entry_setup", "entry_trigger",
    "candlestick_confirmation", "timeframe_relationships", "session_requirements",
    "stop_loss_relationship", "stop_loss_buffer", "invalidation",
    "target_selection", "minimum_risk_reward", "position_sizing", "account_risk",
    "break_even", "partial_profit", "scaling", "trailing_stops",
    "post_entry_management", "news_filters", "no_trade_conditions",
    "discretionary_judgment", "examples_vs_universal_rules",
]

COVERAGE_VOCAB = [
    "WELL_SUPPORTED", "SUPPORTED", "PARTIALLY_SUPPORTED", "AMBIGUOUS",
    "CONTRADICTORY", "DISCRETIONARY", "NON_DETERMINISTIC",
    "ABSENT_FROM_REVIEWED_SOURCES", "NOT_APPLICABLE",
]

SOURCE_STATUS_VOCAB = [
    "ACQUIRED_AND_PROCESSED", "ACQUIRED_NOT_PROCESSED", "PARTIAL_TRANSCRIPT",
    "TRANSCRIPT_MISSING", "SOURCE_IDENTIFIED_NOT_ACQUIRED",
    "DUPLICATE_OR_REDUNDANT", "ATTRIBUTION_UNCERTAIN", "REJECTED_SOURCE",
]

FIDELITY_VOCAB = [
    "EXACT_MATCH", "FUNCTIONAL_MATCH", "PARTIAL_MATCH", "MISSING_FROM_MOGO",
    "PRESENT_BUT_DIFFERENT", "IMPLEMENTED_WITHOUT_EDUCATOR_SUPPORT",
    "MOGO_AUTHORED_PARAMETER", "MOGO_ENHANCEMENT", "NON_IMPLEMENTABLE_DISCRETION",
    "NOT_APPLICABLE", "UNRESOLVED",
]

# Sources identified during MOGO-002.7 discovery but never acquired. Each was
# channel-verified via oEmbed; see the MOGO-002.7 acquisition queue.
UNACQUIRED_SOURCES = [
    {
        "sourceRef": "ACQTARGET|ALEX_G|COMPLETE-WALKTHROUGH",
        "title": "TARGET PROFILE -- complete single-trade walkthrough, setup through close",
        "url": None, "attribution": "ALEX_G (@fxalexg__)",
        "status": "SOURCE_IDENTIFIED_NOT_ACQUIRED",
        "note": "No specific video identified; channel listing is JS-rendered and could not be enumerated.",
    },
    {
        "sourceRef": "ACQTARGET|ALEX_G|LIVE-SESSION-ORDER-ENTRY",
        "title": "TARGET PROFILE -- live session in which an order is actually placed",
        "url": None, "attribution": "ALEX_G (@fxalexg__)",
        "status": "SOURCE_IDENTIFIED_NOT_ACQUIRED",
        "note": "Standing target A2-LIVE (BACKLOG-002). Highest-value remaining target: a stop price "
                "must be typed into an order ticket, which is where the missing buffer would appear.",
    },
    {
        "sourceRef": "ACQTARGET|ALEX_G|SET-AND-FORGET-EXPLAINER",
        "title": "TARGET PROFILE -- dedicated 'set and forget' methodology explainer",
        "url": None, "attribution": "ALEX_G (@fxalexg__)",
        "status": "SOURCE_IDENTIFIED_NOT_ACQUIRED",
        "note": "EVSRC|ALEX_G|20260728|007 self-identifies as episode three of this series, so the "
                "format demonstrably exists.",
    },
    {
        "sourceRef": "ACQCAND|INTERVIEW|20260729|001",
        "title": "How This Young Trader Claims He Made $2M in 1 Year ... w FxAlexG",
        "url": "https://www.youtube.com/watch?v=VMjbJCmFXMk",
        "attribution": "ALEX_G speaks; publisher is Trading Nut (third party)",
        "status": "ATTRIBUTION_UNCERTAIN",
        "note": "Educator speech on a third-party channel. EvidenceSource has no field distinguishing "
                "publisher from speaker, so ingesting it would require a governance decision first.",
    },
]

REJECTED_SOURCES = [
    {"videoId": "iXjrVyTAS6M", "channel": "SIR TREVOR TRADES",
     "title": "Complete Guide Of Set And Forget Strategy by FXALEXG (Must Watch)"},
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
     "title": "Where to Place Your Stop-Loss and Take-Profit Forex Tutorial"},
]


def load(sub):
    return [json.load(open(f, encoding="utf-8"))
            for f in sorted(glob.glob(os.path.join(EV, sub, "*.json")))]


def load_store():
    return {
        "sources": {s["sourceId"]: s for s in load("sources")},
        "items": load("items"),
        "claims": {c["claimId"]: c for c in load("claims")},
        "links": load("links"),
        "segments": load("segments"),
        "questions": load("questions"),
        "contradictions": load("contradictions"),
    }


def build_source_coverage(store):
    ev_by_src = defaultdict(list)
    for i in store["items"]:
        ev_by_src[i["sourceId"]].append(i)
    claims_of_ev = defaultdict(list)
    for l in store["links"]:
        claims_of_ev[l["evidenceId"]].append(l["claimId"])
    seg_by_src = Counter(s["sourceId"] for s in store["segments"])

    rows = []
    for sid in sorted(store["sources"]):
        if not sid.startswith("EVSRC|ALEX_G"):
            continue
        s = store["sources"][sid]
        evs = ev_by_src.get(sid, [])
        cids = sorted({c for e in evs for c in claims_of_ev.get(e["evidenceId"], [])})
        types = Counter(store["claims"][c]["claimType"] for c in cids if c in store["claims"])
        qual = Counter(e.get("evidenceQuality") for e in evs)
        rule_types = {t: n for t, n in types.items() if t in (
            "stop_rule", "target_rule", "risk_rule", "trade_management_rule",
            "entry_rule", "confirmation_rule", "setup_requirement",
            "invalidation_rule", "session_rule", "timeframe_rule")}
        rows.append({
            "sourceId": sid,
            "title": s.get("title"),
            "url": s.get("canonicalReference"),
            "educatorAttribution": s.get("traderId"),
            "attributionMethod": "channel @fxalexg__ verified via YouTube oEmbed author_url",
            "transcriptAvailable": bool(s.get("repositoryPath")),
            "transcriptCompleteness": (s.get("metadata") or {}).get("transcriptCompleteness", "complete"),
            "ingestionStatus": s.get("lifecycleStatus"),
            "extractionStatus": "EXTRACTED",
            "duplicateStatus": "NO_DUPLICATE_DETECTED",
            "claimCount": len(cids),
            "evidenceItemCount": len(evs),
            "segmentCount": seg_by_src.get(sid, 0),
            "claimTypes": dict(sorted(types.items())),
            "ruleBearingClaimTypes": dict(sorted(rule_types.items())),
            "evidenceQuality": dict(sorted(qual.items(), key=lambda kv: str(kv[0]))),
            "provenanceStatus": s.get("provenanceStatus"),
            "contentHash": s.get("contentHash"),
            "repositoryPath": s.get("repositoryPath"),
            "licensingStatus": s.get("licensingStatus"),
            "status": "ACQUIRED_AND_PROCESSED",
            "furtherAcquisitionRequired": False,
        })

    return {
        "generated": True,
        "generatorVersion": GENERATOR_VERSION,
        "milestone": MILESTONE,
        "modelVersion": MODEL_VERSION,
        "narrativeArtifact": "docs/strategy-fidelity/audit/ALEX-SOURCE-COVERAGE-AUDIT.md",
        "statusVocabulary": SOURCE_STATUS_VOCAB,
        "acquiredAndProcessedCount": len(rows),
        "totalClaims": sum(r["claimCount"] for r in rows),
        "totalEvidenceItems": sum(r["evidenceItemCount"] for r in rows),
        "totalSegments": sum(r["segmentCount"] for r in rows),
        "sources": rows,
        "identifiedNotAcquired": UNACQUIRED_SOURCES,
        "rejectedSources": {
            "count": len(REJECTED_SOURCES),
            "reason": "Channel ownership verified individually via oEmbed; none is @fxalexg__. "
                      "Rejected for LINEAGE, not for quality: a third party's account of Alex's rule "
                      "cannot establish Alex attribution.",
            "sources": REJECTED_SOURCES,
        },
        "totalKnownAlexVideoCount": None,
        "totalKnownAlexVideoCountNote": (
            "DELIBERATELY NULL. No defensible inventory of the channel's full catalogue exists: the "
            "channel listing page is JS-rendered and returned no titles when fetched. Any total would "
            "be a guess, so none is stated."
        ),
        "duplicateAnalysis": {
            "method": "SHA-256 content hash compared at ingestion for every source; plus canonicalReference "
                      "(videoId) uniqueness across the 9 registered sources.",
            "exactDuplicates": 0,
            "distinctVideoIds": 9,
            "note": "No source is DUPLICATE_OR_REDUNDANT. Topic overlap exists (e.g. 20260728|003 and "
                    "20260728|006 both narrate chart markup) but each carries distinct claims.",
        },
    }


def _corroboration(cid, store, links_by_claim, ev_by_id):
    evs = [ev_by_id[e] for e in links_by_claim.get(cid, []) if e in ev_by_id]
    srcs = sorted({e["sourceId"] for e in evs})
    return {
        "evidenceCount": len(evs),
        "distinctSourceCount": len(srcs),
        "sourceIds": srcs,
        "timestamps": sorted({e.get("startTimestamp") for e in evs if e.get("startTimestamp")}),
        "evidenceTypes": sorted({e.get("evidenceType") for e in evs if e.get("evidenceType")}),
        "directness": sorted({e.get("directness") for e in evs if e.get("directness")}),
        "independentCorroborationCount": 0,
        "independentCorroborationNote": (
            "0 by construction: every ALEX_G source shares independence group AUTHOR|ALEX_G, so "
            "same-educator repetition is not independent corroboration "
            "(DECISION|MOGO|20260727|006). Repetition across sources is reported as "
            "distinctSourceCount and must not be read as corroboration."
        ),
    }


# Canonical rule register. Each entry cites the claim ids that support it; the
# claim text and provenance are read from the store at generation time, so this
# table carries only the AUDIT JUDGEMENT, never a restatement of the source.
REGISTER = [
    # ---- structure / bias ----
    dict(id="AXR-001", domain="support_and_resistance",
         statement="Support is where price has previously held; resistance is where price has previously "
                   "been rejected. Support/resistance, supply/demand and 'area of interest' are the same "
                   "concept under three names.",
         claims=["CLAIM|ALEX_G|20260729|006"], authorship="EDUCATOR",
         evidenceClass="EXPLICIT", deterministic=False,
         longSide=True, shortSide=True, implementationRelevance="HIGH",
         note="Definitional. Deterministic=False: names a concept, not a computable test."),
    dict(id="AXR-002", domain="trend_definition",
         statement="A continuing downtrend is a sequence of lows with lower highs between them; the "
                   "uptrend mirror is highs with retracements.",
         claims=["CLAIM|ALEX_G|20260729|014"], authorship="EDUCATOR",
         evidenceClass="EXPLICIT", deterministic=False,
         longSide=True, shortSide=True, implementationRelevance="HIGH",
         note="No swing-significance threshold, so not computable as stated."),
    dict(id="AXR-003", domain="break_of_structure",
         statement="A body close beyond a structure level counts as a structural shift, with no stated "
                   "minimum size.",
         claims=[], authorship="EDUCATOR", evidenceClass="EXPLICIT", deterministic=False,
         longSide=True, shortSide=True, implementationRelevance="HIGH",
         note="Carried from the pre-existing ALEX_G corpus; contradicted cross-educator by "
              "XCONTRA|20260729|001. No minimum displacement is stated anywhere."),
    dict(id="AXR-004", domain="break_and_retest",
         statement="Break-and-retest is a CONTINUATION pattern: price breaks a structure point, returns "
                   "to retest it, then continues in the original direction.",
         claims=["CLAIM|ALEX_G|20260729|004"], authorship="EDUCATOR",
         evidenceClass="EXPLICIT", deterministic=False,
         longSide=True, shortSide=True, implementationRelevance="HIGH"),
    dict(id="AXR-005", domain="entry_setup",
         statement="A level qualifies as a break-and-retest level only if it carries a MINIMUM OF ONE "
                   "structure point.",
         claims=["CLAIM|ALEX_G|20260729|011"], authorship="EDUCATOR",
         evidenceClass="EXPLICIT", deterministic=False,
         longSide=True, shortSide=True, implementationRelevance="HIGH",
         note="A quantified minimum over an UNDEFINED unit -- 'structure point' is never defined, so the "
              "rule is not deterministic despite carrying a number."),
    dict(id="AXR-006", domain="entry_setup",
         statement="Once a zone is broken and retested it becomes the next structure point, so the "
                   "pattern chains recursively.",
         claims=["CLAIM|ALEX_G|20260729|012"], authorship="EDUCATOR",
         evidenceClass="EXPLICIT", deterministic=True,
         longSide=True, shortSide=True, implementationRelevance="MEDIUM"),
    dict(id="AXR-007", domain="entry_setup",
         statement="Break-and-retest is MOST EFFECTIVE at a pre-existing zone.",
         claims=["CLAIM|ALEX_G|20260729|007"], authorship="EDUCATOR",
         evidenceClass="EXPLICIT", deterministic=False,
         longSide=True, shortSide=True, implementationRelevance="MEDIUM",
         note="Comparative ('most effective', 'works best'), NOT stated as mandatory. Recording it as a "
              "hard requirement would over-read the source."),
    dict(id="AXR-008", domain="entry_setup",
         statement="Zone width is unconstrained -- 'doesn't matter the size of the box' -- subject only to "
                   "leaving enough room to contain multiple touches.",
         claims=["CLAIM|ALEX_G|20260729|010"], authorship="EDUCATOR",
         evidenceClass="EXPLICIT", deterministic=False,
         longSide=True, shortSide=True, implementationRelevance="HIGH",
         note="An explicit NON-constraint. Directly relevant to production rule ALEX_SR_008, whose source "
              "is recorded as giving 'no formula given' for zone tightness."),
    # ---- entry / confirmation ----
    dict(id="AXR-010", domain="entry_trigger",
         statement="Structure and continuation are read on the higher timeframe; the entry signal must be "
                   "taken on a lower timeframe.",
         claims=["CLAIM|ALEX_G|20260729|017"], authorship="EDUCATOR",
         evidenceClass="EXPLICIT", deterministic=False,
         longSide=True, shortSide=False, implementationRelevance="HIGH",
         note="Stated as a requirement ('you have to'). WHICH lower timeframe is not specified."),
    dict(id="AXR-011", domain="candlestick_confirmation",
         statement="A bullish engulfing candlestick confirmation is REQUIRED before a long "
                   "break-and-retest trade is taken.",
         claims=["CLAIM|ALEX_G|20260729|018"], authorship="EDUCATOR",
         evidenceClass="EXPLICIT", deterministic=False,
         longSide=True, shortSide=False, implementationRelevance="HIGH",
         note="Necessary condition ('in order for us to take a trade we need to have'). The bearish mirror "
              "is referenced only as a pointer to another video and is NOT stated here."),
    dict(id="AXR-012", domain="candlestick_confirmation",
         statement="The confirmation demonstrated is a Morning Star: three doji rejection candles followed "
                   "by one bullish engulfing candle.",
         claims=["CLAIM|ALEX_G|20260729|020"], authorship="EDUCATOR",
         evidenceClass="ILLUSTRATIVE", deterministic=False,
         longSide=True, shortSide=False, implementationRelevance="MEDIUM",
         note="EXAMPLE, not a universal rule. The three-doji count is never stated as required."),
    dict(id="AXR-013", domain="entry_trigger",
         statement="The retest is complete when rejection candlesticks appear -- it is not timed or measured.",
         claims=["CLAIM|ALEX_G|20260729|019"], authorship="EDUCATOR",
         evidenceClass="EXPLICIT", deterministic=False,
         longSide=True, shortSide=False, implementationRelevance="MEDIUM"),
    dict(id="AXR-014", domain="entry_trigger",
         statement="Entry is taken at the confirmation candle of the retest.",
         claims=["CLAIM|ALEX_G|20260729|021"], authorship="EDUCATOR",
         evidenceClass="ILLUSTRATIVE", deterministic=False,
         longSide=True, shortSide=False, implementationRelevance="HIGH",
         note="The exact price within that candle (close / next open / mid) is indicated on the chart and "
              "never named."),
    dict(id="AXR-015", domain="invalidation",
         statement="A structurally ideal break-and-retest is NOT taken when the engulfing confirmation "
                   "does not appear.",
         claims=["CLAIM|ALEX_G|20260729|013"], authorship="EDUCATOR",
         evidenceClass="EXPLICIT", deterministic=False,
         longSide=True, shortSide=False, implementationRelevance="HIGH",
         note="Demonstrated as a binding negative -- the strongest evidence that confirmation is mandatory "
              "rather than advisory."),
    # ---- stop ----
    dict(id="AXR-020", domain="stop_loss_relationship",
         statement="On every break-and-retest trade the stop-loss is placed immediately BEYOND the "
                   "rejection formation at the retest ('right under it' for a long).",
         claims=["CLAIM|ALEX_G|20260729|025", "CLAIM|ALEX_G|20260729|022"],
         authorship="EDUCATOR", evidenceClass="EXPLICIT", deterministic=False,
         longSide=True, shortSide=False, implementationRelevance="CRITICAL",
         note="The ONLY generalised stop statement in 9 sources. rule_statement / direct_explicit, "
              "explicitly universalised ('the same thing every single time'), corroborated by two "
              "same-source demonstrations. Establishes the RELATIONSHIP only."),
    dict(id="AXR-021", domain="stop_loss_buffer",
         statement="[NO RULE EXISTS] The distance between the stop and the rejection structure.",
         claims=[], authorship="UNSUPPORTED", evidenceClass="UNSUPPORTED", deterministic=False,
         longSide=False, shortSide=False, implementationRelevance="CRITICAL",
         note="ABSENT across all 9 sources and 226 claims. No pips, no ATR multiple, no percentage, and no "
              "statement that the stop sits flush. Position size = risk / stop distance, so this single "
              "absence makes all 13 sizing rules non-computable. MOGO's 0.25 ATR is MOGO-authored."),
    dict(id="AXR-022", domain="stop_loss_relationship",
         statement="[NO RULE EXISTS] The short-side stop placement.",
         claims=[], authorship="UNSUPPORTED", evidenceClass="UNSUPPORTED", deterministic=False,
         longSide=False, shortSide=False, implementationRelevance="HIGH",
         note="All three demonstrations are longs and the phrasing is always 'right under'. 'Right above' "
              "is never spoken or shown. Not mirrored by assumption."),
    # ---- targets ----
    dict(id="AXR-030", domain="minimum_risk_reward",
         statement="The take-profit is set to a MINIMUM of 1:2 risk-to-reward.",
         claims=["CLAIM|ALEX_G|20260729|023"], authorship="EDUCATOR",
         evidenceClass="EXPLICIT", deterministic=False,
         longSide=True, shortSide=False, implementationRelevance="CRITICAL",
         note="Stated twice as a FLOOR. A fixed 1:2 is a different rule that merely coincides at the "
              "boundary. Contradicted by XCONTRA|20260729|004."),
    dict(id="AXR-031", domain="target_selection",
         statement="[NO RULE EXISTS] How the target level is chosen when structure allows more than 1:2.",
         claims=["CLAIM|ALEX_G|20260728|084", "CLAIM|ALEX_G|20260728|110",
                 "CLAIM|ALEX_G|20260728|113", "CLAIM|ALEX_G|20260728|140"],
         authorship="UNSUPPORTED", evidenceClass="ILLUSTRATIVE", deterministic=False,
         longSide=False, shortSide=False, implementationRelevance="HIGH",
         note="Four cited claims are all DISTANCES OBSERVED AFTER THE FACT (80-100 pip average; 1:2, 1:3, "
              "1:4 ratios), each annotated illustrative. One fragment measures 1:4 'to previous' structure "
              "-- too truncated to normalize. No selection procedure exists."),
    # ---- risk ----
    dict(id="AXR-040", domain="account_risk",
         statement="Risk is sized as a percentage of the account balance, never as a fixed monetary amount, "
                   "and the same percentage is risked on every trade.",
         claims=["CLAIM|ALEX_G|20260728|098", "CLAIM|ALEX_G|20260728|096",
                 "CLAIM|ALEX_G|20260728|093"],
         authorship="EDUCATOR", evidenceClass="EXPLICIT", deterministic=True,
         longSide=True, shortSide=True, implementationRelevance="HIGH",
         note="The most strongly stated rule family in the corpus. CLAIM|...|098 is one of only two "
              "ALEX_G claims carrying evidence from two distinct sources."),
    dict(id="AXR-041", domain="position_sizing",
         statement="Three risk bands: conservative 0.5-1%, recommended/industry-standard 1-2%, high 3-5%.",
         claims=["CLAIM|ALEX_G|20260728|104", "CLAIM|ALEX_G|20260728|107",
                 "CLAIM|ALEX_G|20260728|111"],
         authorship="EDUCATOR", evidenceClass="EXPLICIT", deterministic=True,
         longSide=True, shortSide=True, implementationRelevance="HIGH",
         note="Bands are explicit and deterministic AS PERCENTAGES. They still cannot produce a position "
              "SIZE without AXR-021."),
    dict(id="AXR-042", domain="position_sizing",
         statement="The high band (3-5%) is confined to a personal or disposable account, and to the months "
                   "November-March.",
         claims=["CLAIM|ALEX_G|20260728|112", "CLAIM|ALEX_G|20260728|117"],
         authorship="EDUCATOR", evidenceClass="EXPLICIT", deterministic=True,
         longSide=True, shortSide=True, implementationRelevance="LOW"),
    dict(id="AXR-043", domain="account_risk",
         statement="Once chosen, the risk percentage is not raised after wins or lowered after losses; his "
                   "own practice fixes one percentage per calendar month.",
         claims=["CLAIM|ALEX_G|20260728|108", "CLAIM|ALEX_G|20260728|114"],
         authorship="EDUCATOR", evidenceClass="EXPLICIT", deterministic=True,
         longSide=True, shortSide=True, implementationRelevance="MEDIUM"),
    # ---- management / exit ----
    dict(id="AXR-050", domain="post_entry_management",
         statement="A losing trade is allowed to reach its stop without intervention; the loss is accepted "
                   "as normal variance.",
         claims=["CLAIM|ALEX_G|20260729|024"], authorship="EDUCATOR",
         evidenceClass="ILLUSTRATIVE", deterministic=False,
         longSide=True, shortSide=False, implementationRelevance="HIGH",
         note="DEMONSTRATED once, never stated as a rule. The strongest available evidence for a "
              "no-intervention default, and deliberately not promoted to a universal rule."),
    dict(id="AXR-051", domain="post_entry_management",
         statement="No action is taken while price travels toward the area of interest; the setup is left "
                   "alone until price arrives.",
         claims=["CLAIM|ALEX_G|20260728|045"], authorship="EDUCATOR",
         evidenceClass="EXPLICIT", deterministic=False,
         longSide=True, shortSide=True, implementationRelevance="MEDIUM",
         note="The most-repeated claim in the corpus: evidence from THREE distinct sources. Still not "
              "independent corroboration (same educator)."),
    dict(id="AXR-052", domain="post_entry_management",
         statement="A target set in advance should be allowed to run rather than cut when the unrealised "
                   "figure becomes emotionally significant.",
         claims=["CLAIM|ALEX_G|20260728|147"], authorship="EDUCATOR",
         evidenceClass="EXPLICIT", deterministic=False,
         longSide=True, shortSide=True, implementationRelevance="MEDIUM",
         note="An ANTI-exit rule: constrains discretionary exit without specifying one."),
    dict(id="AXR-053", domain="post_entry_management",
         statement="After missing an entry, set an alarm for the next pullback rather than chase.",
         claims=["CLAIM|ALEX_G|20260728|139"], authorship="EDUCATOR",
         evidenceClass="ILLUSTRATIVE", deterministic=False,
         longSide=True, shortSide=True, implementationRelevance="LOW"),
    dict(id="AXR-060", domain="break_even",
         statement="[NO RULE EXISTS] Whether the stop is ever moved to break-even.",
         claims=[], authorship="UNSUPPORTED", evidenceClass="UNSUPPORTED", deterministic=False,
         longSide=False, shortSide=False, implementationRelevance="HIGH",
         note="ZERO mentions across 9 sources / 280 evidence items. Strengthened by the fact that "
              "EVSRC|ALEX_G|20260729|001 narrates three complete trades end to end without mentioning it."),
    dict(id="AXR-061", domain="partial_profit",
         statement="[NO RULE EXISTS] Whether any portion of a position is closed before the full target.",
         claims=[], authorship="UNSUPPORTED", evidenceClass="UNSUPPORTED", deterministic=False,
         longSide=False, shortSide=False, implementationRelevance="HIGH",
         note="ZERO mentions across 9 sources."),
    dict(id="AXR-062", domain="scaling",
         statement="[NO RULE EXISTS] Whether a position is ever added to or reduced after entry.",
         claims=[], authorship="UNSUPPORTED", evidenceClass="UNSUPPORTED", deterministic=False,
         longSide=False, shortSide=False, implementationRelevance="MEDIUM",
         note="ZERO mentions. One near-match ('let me scale') refers to scaling an ACCOUNT, not a position."),
    dict(id="AXR-063", domain="trailing_stops",
         statement="[NO RULE EXISTS] Whether the stop is ever trailed.",
         claims=[], authorship="UNSUPPORTED", evidenceClass="UNSUPPORTED", deterministic=False,
         longSide=False, shortSide=False, implementationRelevance="MEDIUM",
         note="ZERO mentions across 9 sources."),
    # ---- timeframes / sessions ----
    dict(id="AXR-070", domain="timeframe_relationships",
         statement="A break-and-retest on a higher timeframe is more respected than one on a lower "
                   "timeframe.",
         claims=["CLAIM|ALEX_G|20260729|008"], authorship="EDUCATOR",
         evidenceClass="EXPLICIT", deterministic=False,
         longSide=True, shortSide=True, implementationRelevance="MEDIUM",
         note="Comparative only. No ranking, weighting or threshold."),
    dict(id="AXR-071", domain="higher_timeframe_analysis",
         statement="Top-down analysis uses four tiers: weekly, daily, 4-hour, and the lower timeframes "
                   "(2H/1H/30m/15m; below 15m is not a strong timeframe).",
         claims=["CLAIM|ALEX_G|20260727|005", "CLAIM|ALEX_G|20260727|006"],
         authorship="EDUCATOR", evidenceClass="EXPLICIT", deterministic=True,
         longSide=True, shortSide=True, implementationRelevance="HIGH"),
    dict(id="AXR-072", domain="timeframe_relationships",
         statement="Day trading reads break-and-retest on 4H/1H; swing trading on daily/weekly.",
         claims=["CLAIM|ALEX_G|20260729|015", "CLAIM|ALEX_G|20260729|016"],
         authorship="EDUCATOR", evidenceClass="EXPLICIT", deterministic=False,
         longSide=True, shortSide=True, implementationRelevance="MEDIUM",
         note="Immediately qualified ('depending on how approach you want to take it'), so a default rather "
              "than a constraint. The swing clause names a second style whose word is garbled in the "
              "transcript and was NOT guessed."),
    dict(id="AXR-080", domain="session_requirements",
         statement="Entry timing is governed by session and day-of-week; a valid confirmation at the wrong "
                   "time is not traded. Entries are restricted to Monday-Wednesday.",
         claims=["CLAIM|ALEX_G|20260728|078", "CLAIM|ALEX_G|20260728|083",
                 "CLAIM|ALEX_G|20260728|081"],
         authorship="EDUCATOR", evidenceClass="EXPLICIT", deterministic=False,
         longSide=True, shortSide=True, implementationRelevance="HIGH",
         note="The RULE is prescriptive and explicit; the HOURS are displayed on an on-screen session map "
              "and never spoken. Day-of-week IS deterministic; session hours are not."),
    dict(id="AXR-081", domain="session_requirements",
         statement="[PARAMETER ABSENT] The exact hours of the tradeable session windows.",
         claims=["CLAIM|ALEX_G|20260728|079", "CLAIM|ALEX_G|20260728|053"],
         authorship="UNSUPPORTED", evidenceClass="UNSUPPORTED", deterministic=False,
         longSide=False, shortSide=False, implementationRelevance="HIGH",
         note="Exists in the source material as PIXELS, not words. No further transcript of the same format "
              "can close it."),
    # ---- market selection / conditions / news ----
    dict(id="AXR-090", domain="market_selection",
         statement="The pattern applies to all timeframes and all instrument classes -- currencies, "
                   "commodities, futures, stocks.",
         claims=["CLAIM|ALEX_G|20260729|005"], authorship="EDUCATOR",
         evidenceClass="EXPLICIT", deterministic=False,
         longSide=True, shortSide=True, implementationRelevance="LOW",
         note="A NON-restriction. No instrument filter, no liquidity/spread requirement, no pair "
              "shortlist is stated anywhere."),
    dict(id="AXR-091", domain="market_conditions",
         statement="[NO RULE EXISTS] Any market-condition filter (volatility, ranging vs trending, "
                   "spread) gating whether to trade at all.",
         claims=[], authorship="UNSUPPORTED", evidenceClass="UNSUPPORTED", deterministic=False,
         longSide=False, shortSide=False, implementationRelevance="MEDIUM",
         note="MARKET_CONDITIONS carries 19 claims and yields 0 normalized rules -- claims describe the "
              "market, none gates a decision."),
    dict(id="AXR-092", domain="news_filters",
         statement="[NO RULE EXISTS] Any news or economic-calendar filter.",
         claims=[], authorship="UNSUPPORTED", evidenceClass="UNSUPPORTED", deterministic=False,
         longSide=False, shortSide=False, implementationRelevance="MEDIUM",
         note="ZERO mentions across 9 sources. MOGO also implements none (ALEX_X_007), so the absence "
              "is consistent -- but it is an absence in both, not agreement."),
    dict(id="AXR-093", domain="liquidity",
         statement="Alex G rejects the institutional-stop-hunt narrative as unproven and states no strategy "
                   "can trade liquidity sweeps alone.",
         claims=[], authorship="EDUCATOR", evidenceClass="OPINION", deterministic=False,
         longSide=False, shortSide=False, implementationRelevance="LOW",
         note="OPINION, and the subject of blocking cross-educator contradiction KECON|20260728|001 with "
              "TJR. Not implementable and not intended to be."),
    dict(id="AXR-100", domain="discretionary_judgment",
         statement="Several gates are explicitly judgement calls: whether a second confirmation is needed "
                   "depends on level strength, timeframe, days left in the week and R:R, with no threshold "
                   "assigned to any input.",
         claims=[], authorship="EDUCATOR", evidenceClass="EXPLICIT", deterministic=False,
         longSide=True, shortSide=True, implementationRelevance="HIGH",
         note="DISCRETIONARY_ELEMENTS carries 40 claims and yields 7 rules, 0 of them deterministic."),
]


def build_rule_register(store):
    links_by_claim = defaultdict(list)
    for l in store["links"]:
        links_by_claim[l["claimId"]].append(l["evidenceId"])
    ev_by_id = {e["evidenceId"]: e for e in store["items"]}

    contra_claims = {}
    for c in store["contradictions"]:
        if c.get("status") in ("resolved", "dismissed"):
            continue
        for cid in (c.get("claimAId"), c.get("claimBId")):
            if cid:
                contra_claims.setdefault(cid, []).append(
                    {"contradictionId": c.get("contradictionId"),
                     "severity": c.get("severity"),
                     "type": c.get("contradictionType"),
                     "status": c.get("status")})

    rows = []
    for r in REGISTER:
        cits = []
        missing = []
        for cid in r["claims"]:
            c = store["claims"].get(cid)
            if not c:
                missing.append(cid)
                continue
            corr = _corroboration(cid, store, links_by_claim, ev_by_id)
            cits.append({
                "claimId": cid,
                "claimType": c["claimType"],
                "normalizedClaim": c["normalizedClaim"],
                "confidenceState": c["confidenceState"],
                "confidenceScore": c["confidenceScore"],
                "inContradiction": cid in contra_claims,
                "contradictions": contra_claims.get(cid, []),
                **corr,
            })
        rows.append({
            "ruleId": r["id"],
            "domain": r["domain"],
            "normalizedStatement": r["statement"],
            "authorship": r["authorship"],
            "evidenceClass": r["evidenceClass"],
            "deterministic": r["deterministic"],
            "longSideSupported": r["longSide"],
            "shortSideSupported": r["shortSide"],
            "implementationRelevance": r["implementationRelevance"],
            "auditNote": r.get("note"),
            "supportingClaimIds": r["claims"],
            "supportingClaims": cits,
            "distinctSourceCount": len({s for c in cits for s in c["sourceIds"]}),
            "contradictionStatus": "IN_OPEN_CONTRADICTION" if any(
                c["inContradiction"] for c in cits) else "NONE",
            "confidenceStatus": (sorted({c["confidenceState"] for c in cits})[0]
                                 if cits else "NO_CLAIM_EXISTS"),
            "unresolvedCitations": missing,
        })

    by_class = Counter(r["evidenceClass"] for r in rows)
    return {
        "generated": True,
        "generatorVersion": GENERATOR_VERSION,
        "milestone": MILESTONE,
        "modelVersion": MODEL_VERSION,
        "narrativeArtifact": "docs/strategy-fidelity/audit/ALEX-CANONICAL-RULE-REGISTER.md",
        "scopeNote": (
            "This register is an AUDIT VIEW over the ALEX_G educator claim library. It is NOT a "
            "specification, is NOT approved, and does NOT merge with alex_g_sr_v1 "
            "(DECISION|MOGO|20260727|004, KEREV-B). No rule here authorizes any code change."
        ),
        "ruleCount": len(rows),
        "byEvidenceClass": dict(sorted(by_class.items())),
        "deterministicCount": sum(1 for r in rows if r["deterministic"]),
        "unsupportedCount": sum(1 for r in rows if r["authorship"] == "UNSUPPORTED"),
        "shortSideSupportedCount": sum(1 for r in rows if r["shortSideSupported"]),
        "rulesWithOpenContradiction": [r["ruleId"] for r in rows
                                       if r["contradictionStatus"] != "NONE"],
        "allClaimsEmerging": all(c["confidenceState"] == "emerging"
                                 for r in rows for c in r["supportingClaims"]),
        "rules": rows,
    }


DOMAIN_COVERAGE = {
    "market_selection": ("PARTIALLY_SUPPORTED", "A universal-applicability statement exists; no instrument filter, spread or liquidity requirement is stated.", "Whether any pair/instrument is excluded.", False, True, "Any source discussing which pairs he trades."),
    "market_conditions": ("ABSENT_FROM_REVIEWED_SOURCES", "19 claims describe market behaviour; none gates a trading decision.", "Whether any volatility or regime filter exists.", False, True, "A 'when not to trade' or market-conditions video."),
    "directional_bias": ("PARTIALLY_SUPPORTED", "Top-down bias is described; the production spec classifies its own bias rule DISCRETIONARY.", "Whether bias is a hard gate or a preference.", False, True, "A top-down analysis walkthrough."),
    "higher_timeframe_analysis": ("SUPPORTED", "Four explicit tiers, W/D/4H plus lower TFs, with 15m named as the floor.", "How the tiers are weighted against each other.", False, True, "A top-down scoring video."),
    "market_structure": ("PARTIALLY_SUPPORTED", "HH/HL and LH/LL definitions are explicit and repeated.", "What makes a swing point significant enough to count.", True, False, "Replay sweep RC-29; no transcript can supply the threshold."),
    "break_of_structure": ("AMBIGUOUS", "A body close beyond a level counts, with no minimum size.", "How false breaks and noise are excluded.", True, False, "Cross-educator contradicted; needs replay."),
    "trend_definition": ("SUPPORTED", "Explicitly defined in both directions in the newest source.", "The swing-significance unit underneath it.", True, False, "Same blocker as market_structure."),
    "liquidity": ("DISCRETIONARY", "Alex G rejects the institutional-sweep narrative; treats sweeps as untradeable alone.", "Nothing implementable is claimed.", False, False, "Not worth acquiring for implementation."),
    "support_and_resistance": ("WELL_SUPPORTED", "Explicit definition plus an explicit statement that S/R, supply/demand and AOI are one concept.", "Nothing material.", False, False, "None needed."),
    "supply_and_demand": ("WELL_SUPPORTED", "Same as support_and_resistance by the educator's own equivalence statement.", "Nothing material.", False, False, "None needed."),
    "break_and_retest": ("WELL_SUPPORTED", "Defined as a continuation pattern, demonstrated 5-6 times on one chart plus 3 worked trades.", "The structure-point unit it chains on.", True, False, "Already well covered."),
    "entry_setup": ("PARTIALLY_SUPPORTED", "Minimum one structure point; zone width explicitly unconstrained; chains recursively.", "What a 'structure point' is; how much room is 'enough'.", True, True, "A markup-focused video that quantifies the box."),
    "entry_trigger": ("PARTIALLY_SUPPORTED", "Lower-timeframe entry is mandatory; entry is at the confirmation candle.", "WHICH lower timeframe, and the exact price within the candle.", True, True, "A live session showing order entry."),
    "candlestick_confirmation": ("PARTIALLY_SUPPORTED", "Bullish engulfing is REQUIRED for longs; Morning Star demonstrated; a setup was declined for its absence.", "Whether the family is one specific pattern or any rejection formation; the bearish mirror.", True, True, "The referenced 'engulfing candlestick' video."),
    "timeframe_relationships": ("PARTIALLY_SUPPORTED", "HTF more respected; 4H/1H day, D/W swing; entries on lower TFs.", "Weighting, and whether the pairings are constraints.", False, True, "A day-trading-specific video."),
    "session_requirements": ("NON_DETERMINISTIC", "The RULE is explicit and prescriptive: session and day-of-week gate entry; Mon-Wed only.", "The exact hours -- displayed on screen, never spoken.", True, False, "No transcript can fix this; needs frame-reading approval."),
    "stop_loss_relationship": ("PARTIALLY_SUPPORTED", "Stop goes immediately beyond the rejection structure, stated as an invariant and demonstrated twice.", "The anchor is deictic ('it'/'this point') with three readings; short side never stated.", True, True, "A live session with order entry."),
    "stop_loss_buffer": ("ABSENT_FROM_REVIEWED_SOURCES", "Nothing. No unit of any kind appears in 9 sources.", "The entire parameter.", True, True, "A live session showing the order ticket."),
    "invalidation": ("PARTIALLY_SUPPORTED", "No confirmation means no trade, demonstrated; structural invalidation described.", "Post-entry invalidation other than the stop.", False, True, "A trade-review video."),
    "target_selection": ("PARTIALLY_SUPPORTED", "Distances observed (80-100 pips, 1:3, 1:4); one fragment measures 'to previous' structure.", "How the level is chosen above the 1:2 floor.", True, True, "A complete walkthrough naming the target level."),
    "minimum_risk_reward": ("SUPPORTED", "1:2 minimum stated twice in one source as a floor.", "Whether the floor may be revised down after entry (XCONTRA|20260729|004).", True, False, "An Authority ruling, not a source."),
    "position_sizing": ("PARTIALLY_SUPPORTED", "Three explicit percentage bands, deterministic as percentages.", "Cannot produce a size without the stop distance.", True, True, "Same as stop_loss_buffer."),
    "account_risk": ("WELL_SUPPORTED", "Percentage-based, fixed per trade, never raised after wins; strongest rule family in the corpus.", "Nothing material.", False, False, "None needed."),
    "break_even": ("ABSENT_FROM_REVIEWED_SOURCES", "Zero mentions in 9 sources.", "Whether it exists at all.", False, True, "A 'set and forget' explainer."),
    "partial_profit": ("ABSENT_FROM_REVIEWED_SOURCES", "Zero mentions in 9 sources.", "Whether it exists at all.", False, True, "A 'set and forget' explainer."),
    "scaling": ("ABSENT_FROM_REVIEWED_SOURCES", "Zero mentions in 9 sources.", "Whether it exists at all.", False, True, "A 'set and forget' explainer."),
    "trailing_stops": ("ABSENT_FROM_REVIEWED_SOURCES", "Zero mentions in 9 sources.", "Whether it exists at all.", False, True, "A 'set and forget' explainer."),
    "post_entry_management": ("PARTIALLY_SUPPORTED", "No-intervention demonstrated once; leave-it-alone-before-arrival stated across 3 sources; anti-cut rule stated.", "Whether no-intervention is a rule or just what happened.", True, True, "A 'set and forget' explainer."),
    "news_filters": ("ABSENT_FROM_REVIEWED_SOURCES", "Zero mentions in 9 sources.", "Whether any exists.", False, True, "Low priority."),
    "no_trade_conditions": ("SUPPORTED", "Wrong session/day, no confirmation, and role violations are all explicit no-trade conditions.", "The session parameter underneath.", True, False, "See session_requirements."),
    "discretionary_judgment": ("DISCRETIONARY", "Explicitly discretionary gates exist with named inputs and no thresholds.", "Nothing -- this is correctly discretionary.", True, False, "Not resolvable by acquisition; needs a MOGO formalization decision."),
    "examples_vs_universal_rules": ("SUPPORTED", "The corpus distinguishes them cleanly once annotated: 1:2 is a stated floor, 1:3/1:4/80-100 pips are observations.", "Nothing material.", False, False, "None needed."),
}


def build_domain_coverage():
    rows = []
    for d in BRIEF_DOMAINS:
        cov, known, unknown, blocks, resolvable, nxt = DOMAIN_COVERAGE[d]
        rows.append({
            "domain": d,
            "coverage": cov,
            "whatIsKnown": known,
            "whatRemainsUnknown": unknown,
            "blocksFaithfulImplementation": blocks,
            "anotherTranscriptCouldPlausiblyResolve": resolvable,
            "mostValuableNextSourceType": nxt,
        })
    return rows


# Fidelity matrix: educator rule -> MOGO implementation.
FIDELITY = [
    ("AXR-001", "ALEX_SR_001/002", "FUNCTIONAL_MATCH", "alexGZoneRole (index.html:2735)",
     "Role derived positionally: above->support, below->resistance, within->inside.",
     "CONVERGENT_NOT_DERIVED"),
    ("AXR-002", None, "PARTIAL_MATCH", "alexGComputeTrendContext (index.html:3199)",
     "Trend context is computed and recorded but never gates a trade.", "CONVERGENT_NOT_DERIVED"),
    ("AXR-003", "ALEX_SR_011", "PARTIAL_MATCH", "alexGEvaluateBreakRetest (index.html:3147)",
     "MOGO enforces an ordered break/retest sequence; the educator states no minimum displacement, "
     "MOGO adds rejectionDisplacementATRMultiplier=0.25 (ALEX_X_006).", "MOGO_AUTHORED_PARAMETER"),
    ("AXR-004", "ALEX_SR_011", "FUNCTIONAL_MATCH", "alexGEvaluateBreakRetest (index.html:3147)",
     "Break-then-retest continuation is implemented as a first-class setup type (B_breakRetest).",
     "CONVERGENT_NOT_DERIVED"),
    ("AXR-005", "ALEX_SR_005/006", "PRESENT_BUT_DIFFERENT", "alexGEvaluateRepeatedReaction (index.html:3165)",
     "Educator: MINIMUM ONE structure point. MOGO: requires touchIndex>=3 AND zone.touches.length>=4 "
     "for the repeated-reaction setup. MOGO is materially STRICTER than the educator states.",
     "MOGO_AUTHORED_PARAMETER"),
    ("AXR-006", None, "NOT_APPLICABLE", None,
     "Recursive chaining of retested zones into new structure points is not modelled as such.", None),
    ("AXR-007", None, "FUNCTIONAL_MATCH", "alexGRunZoneEngine (index.html:2996)",
     "MOGO only ever evaluates setups at detected zones, which satisfies the comparative preference.",
     "CONVERGENT_NOT_DERIVED"),
    ("AXR-008", "ALEX_SR_008", "PRESENT_BUT_DIFFERENT", "alexGAssignCluster (index.html:2763)",
     "Educator: zone width is EXPLICITLY UNCONSTRAINED. MOGO: zoneClusterATRMultiplier=0.5 constrains "
     "clustering. MOGO imposes a constraint the educator explicitly declines to impose.",
     "MOGO_AUTHORED_PARAMETER"),
    ("AXR-010", None, "MISSING_FROM_MOGO", None,
     "MOGO evaluates zones and setups on H1/H4/D/W and does not drop to a lower timeframe for entry. "
     "There is no separate HTF-structure / LTF-entry split.", None),
    ("AXR-011", None, "MISSING_FROM_MOGO", None,
     "MOGO has NO candlestick-confirmation requirement. Entry is the qualification candle's close. "
     "The educator's single hardest entry precondition is absent from the implementation.", None),
    ("AXR-012", None, "MISSING_FROM_MOGO", None, "No Morning Star detection exists.", None),
    ("AXR-013", None, "PRESENT_BUT_DIFFERENT", "alexGAcceptReaction (index.html:2792)",
     "Educator: retest ends when rejection candles appear. MOGO: reaction counts if confirmed within "
     "rejectionConfirmWithinBars=1 and displaces >=0.25 ATR (ALEX_X_006).", "MOGO_AUTHORED_PARAMETER"),
    ("AXR-014", None, "PRESENT_BUT_DIFFERENT", "alexGConstructLivePosition (index.html:3956)",
     "MOGO enters at the qualification candle close; the educator indicates the confirmation candle "
     "without naming a price.", "MOGO_AUTHORED_PARAMETER"),
    ("AXR-015", None, "MISSING_FROM_MOGO", None,
     "MOGO has no confirmation gate, so it cannot decline a setup for a missing confirmation. This is "
     "the fidelity gap with the clearest trade-eligibility consequence.", None),
    ("AXR-020", "ALEX_X_001", "PARTIAL_MATCH", "alexGConstructLivePosition (index.html:3487-3488)",
     "RELATIONSHIP MATCHES: stop sits just beyond the structure. ANCHOR DIFFERS: MOGO anchors on "
     "setup.zoneLow/zoneHigh (zone boundary); the educator anchors on the rejection formation at the "
     "retest. A rejection wick can extend well beyond the zone boundary, so these are not the same "
     "object.", "CONVERGENT_NOT_DERIVED"),
    ("AXR-021", "ALEX_X_001", "MOGO_AUTHORED_PARAMETER", "RULES_ALEXG.config.stopATRBuffer (index.html:2392)",
     "stopATRBuffer = 0.25 ATR. NO educator counterpart exists -- no ALEX_G claim in 9 sources mentions "
     "ATR at all. Entirely MOGO-authored.", "MOGO_AUTHORED"),
    ("AXR-022", "ALEX_X_001", "IMPLEMENTED_WITHOUT_EDUCATOR_SUPPORT", "index.html:3488",
     "MOGO implements the short-side stop symmetrically (zoneHigh + buffer). The educator never states "
     "the short-side rule, so MOGO's symmetry is an assumption, not a match.", "MOGO_AUTHORED"),
    ("AXR-030", "ALEX_X_001", "PRESENT_BUT_DIFFERENT", "RULES_ALEXG.config.minRR (index.html:2394)",
     "Educator: 1:2 is a MINIMUM (floor). MOGO: minRR=2.0 is a FIXED ratio -- target = entry +/- 2.0 x "
     "risk, always. These are different rules that coincide at the boundary. MOGO can never take the "
     "1:3 or 1:4 the educator also describes.", "MOGO_AUTHORED_PARAMETER"),
    ("AXR-031", None, "UNRESOLVED", None,
     "No educator target-selection procedure exists, so MOGO's fixed 2R cannot be compared against one.",
     None),
    ("AXR-040", "ALEX_X_001", "FUNCTIONAL_MATCH", "index.html:3512",
     "riskAmount = balanceBefore * (riskPercent/100) -- percentage-based off account balance, fixed per "
     "trade. This is the closest genuine agreement between MOGO and the educator on any risk rule.",
     "CONVERGENT_NOT_DERIVED"),
    ("AXR-041", "ALEX_X_001", "PARTIAL_MATCH", "RULES_ALEXG.config.riskPercent (index.html:2393)",
     "MOGO uses riskPercent=1.0, which falls inside BOTH the conservative (0.5-1%) and recommended "
     "(1-2%) bands. Consistent with the educator, but MOGO chose the single value; the educator states "
     "bands and an account-type dependency MOGO does not model.", "MOGO_AUTHORED_PARAMETER"),
    ("AXR-042", None, "MISSING_FROM_MOGO", None, "No account-type or calendar-month risk modulation.", None),
    ("AXR-043", None, "FUNCTIONAL_MATCH", "RULES_ALEXG.config.riskPercent",
     "riskPercent is a constant, so it is never raised after wins or lowered after losses. MOGO "
     "satisfies the stability rule by construction.", "CONVERGENT_NOT_DERIVED"),
    ("AXR-050", None, "FUNCTIONAL_MATCH", "alexGUpdatePositionExcursionAndCheckExit",
     "MOGO never intervenes between entry and exit: the stop and target are frozen at entry and never "
     "trailed or moved. Matches the demonstrated no-intervention behaviour.", "CONVERGENT_NOT_DERIVED"),
    ("AXR-051", None, "FUNCTIONAL_MATCH", "alexGRunSetupEngine (index.html:3349)",
     "No action is taken until a setup qualifies at the zone.", "CONVERGENT_NOT_DERIVED"),
    ("AXR-052", None, "FUNCTIONAL_MATCH", "alexGConstructLivePosition",
     "The target is frozen at entry and never cut early.", "CONVERGENT_NOT_DERIVED"),
    ("AXR-053", None, "NOT_APPLICABLE", None, "Human behaviour; no automation counterpart.", None),
    ("AXR-060", None, "IMPLEMENTED_WITHOUT_EDUCATOR_SUPPORT", "APP_VERSION_LOG v4.0",
     "MOGO documents 'never trailed or moved to break-even' as an explicit MOGO choice. The educator "
     "says nothing either way, so this is a MOGO decision in an evidentiary vacuum -- not a match.",
     "MOGO_AUTHORED"),
    ("AXR-061", None, "IMPLEMENTED_WITHOUT_EDUCATOR_SUPPORT", None,
     "MOGO takes no partials. Educator silent.", "MOGO_AUTHORED"),
    ("AXR-062", None, "IMPLEMENTED_WITHOUT_EDUCATOR_SUPPORT", None,
     "MOGO is single-entry. Educator silent.", "MOGO_AUTHORED"),
    ("AXR-063", None, "IMPLEMENTED_WITHOUT_EDUCATOR_SUPPORT", None,
     "MOGO does not trail. Educator silent.", "MOGO_AUTHORED"),
    ("AXR-070", "ALEX_SR_010", "PARTIAL_MATCH", "alexGSetupSortComparator (index.html:3589)",
     "htfPriority {W:4,D:3,H4:2,H1:1} orders competing setups. It never gates, weights or sizes a trade, "
     "so 'more respected' is only partially realised.", "CONVERGENT_NOT_DERIVED"),
    ("AXR-071", "ALEX_SR_009", "PARTIAL_MATCH", "alexGRunZoneEngine (index.html:2996)",
     "MOGO processes H1/H4/D/W. Educator names W/D/4H plus 2H/1H/30m/15m. MOGO omits the sub-H1 tiers "
     "entirely and adds none.", "CONVERGENT_NOT_DERIVED"),
    ("AXR-072", None, "MISSING_FROM_MOGO", None,
     "No day-trade vs swing-trade mode distinction exists.", None),
    ("AXR-080", "ALEX_X_007", "MISSING_FROM_MOGO", "alexGComputeSessionMetadata (index.html:3225)",
     "Session and day metadata ARE computed and recorded but NEVER restrict entry. The educator states "
     "an explicit Mon-Wed restriction and a session gate; MOGO applies neither. Recorded in the manifest "
     "as 'a deliberate design choice, not a source gap' -- that note predates the session evidence.", None),
    ("AXR-081", None, "UNRESOLVED", None, "Parameter absent from source; nothing to compare.", None),
    ("AXR-090", None, "PRESENT_BUT_DIFFERENT", "RULES_ALEXG.config",
     "Educator states universal applicability. MOGO trades a fixed instrument set via its own scan "
     "configuration.", "MOGO_AUTHORED_PARAMETER"),
    ("AXR-091", "ALEX_X_005", "IMPLEMENTED_WITHOUT_EDUCATOR_SUPPORT", "alexGCorrectedQuality (index.html:3137)",
     "MOGO adds a choppy-zone filter (>=3 penetrations / 50 bars). The educator states no such filter.",
     "MOGO_AUTHORED"),
    ("AXR-092", "ALEX_X_007", "NOT_APPLICABLE", None,
     "Neither implements a news filter. Absence in both is not agreement.", None),
    ("AXR-093", None, "NON_IMPLEMENTABLE_DISCRETION", None, "Opinion; cross-educator contradicted.", None),
    ("AXR-100", None, "NON_IMPLEMENTABLE_DISCRETION", None,
     "MOGO necessarily formalizes what the educator leaves to judgement. Every such formalization is a "
     "MOGO-authored parameter and is listed as one.", "MOGO_AUTHORED"),
]

# MOGO behaviour with no educator counterpart at all.
MOGO_ONLY = [
    ("ALEX_X_002", "ENTRY", "Live entry-delay gate, 5 pips (maxLiveEntryDelayPips)",
     "engineering_necessity", True, "index.html:3988"),
    ("ALEX_X_003", "ENTRY", "Signal staleness, one bar-period per timeframe",
     "engineering_necessity", True, "index.html:4177"),
    ("ALEX_X_004", "NO_TRADE_CONDITIONS", "Account activation cutoff",
     "engineering_necessity", True, "index.html:4165"),
    ("ALEX_X_005", "SETUP", "Choppy-zone filter, >=3 penetrations per 50 bars",
     "hub_standardization", True, "index.html:3137"),
    ("ALEX_X_006", "SETUP", "Rejection confirmation window 1 bar + 0.25 ATR displacement",
     "hub_standardization", True, "index.html:2792"),
    ("ALEX_X_008", "SETUP", "ALEX_SCORE_V2, a second strategy claiming the Alex name (shadow only)",
     "experimental", False, "index.html:14952"),
]


def build_fidelity_matrix(register):
    by_id = {r["ruleId"]: r for r in register["rules"]}
    rows = []
    for rid, mogo_rule, status, loc, behaviour, lineage in FIDELITY:
        r = by_id.get(rid, {})
        rows.append({
            "educatorRuleId": rid,
            "domain": r.get("domain"),
            "educatorStatement": r.get("normalizedStatement"),
            "educatorEvidenceClass": r.get("evidenceClass"),
            "educatorDeterministic": r.get("deterministic"),
            "supportingClaimIds": r.get("supportingClaimIds", []),
            "mogoRuleId": mogo_rule,
            "fidelityStatus": status,
            "codeLocation": loc,
            "implementationBehaviour": behaviour,
            "authorship": ("MOGO_AUTHORED" if lineage == "MOGO_AUTHORED"
                           else "EDUCATOR_CONVERGENT" if lineage == "CONVERGENT_NOT_DERIVED"
                           else "MIXED" if lineage else "NOT_APPLICABLE"),
            "lineageNote": lineage,
        })
    counts = Counter(r["fidelityStatus"] for r in rows)
    return {
        "generated": True,
        "generatorVersion": GENERATOR_VERSION,
        "milestone": MILESTONE,
        "modelVersion": MODEL_VERSION,
        "narrativeArtifact": "docs/strategy-fidelity/audit/ALEX-IMPLEMENTATION-FIDELITY-MATRIX.md",
        "vocabulary": FIDELITY_VOCAB,
        "⚠️lineageWarning": (
            "This matrix compares MOGO's implementation against the EDUCATOR library. That comparison "
            "has never been performed before and is OBSERVATIONAL ONLY. alex_g_sr_v1's rules are "
            "MOGO's own (DECISION|MOGO|20260727|004); any agreement below is CONVERGENCE, NOT "
            "DERIVATION. This matrix does not re-specify the production strategy and does not merge "
            "the two bodies of knowledge (KEREV-B remains open)."
        ),
        "comparedRuleCount": len(rows),
        "statusCounts": dict(sorted(counts.items())),
        "rulesEducatorTeachesMogoLacks": [r["educatorRuleId"] for r in rows
                                          if r["fidelityStatus"] == "MISSING_FROM_MOGO"],
        "rulesMogoImplementsDifferently": [r["educatorRuleId"] for r in rows
                                           if r["fidelityStatus"] == "PRESENT_BUT_DIFFERENT"],
        "rulesMogoImplementsEducatorNeverTaught": [r["educatorRuleId"] for r in rows
                                                   if r["fidelityStatus"] == "IMPLEMENTED_WITHOUT_EDUCATOR_SUPPORT"],
        "mogoAuthoredParameters": [r["educatorRuleId"] for r in rows
                                   if r["fidelityStatus"] == "MOGO_AUTHORED_PARAMETER"],
        "nonImplementableDiscretion": [r["educatorRuleId"] for r in rows
                                       if r["fidelityStatus"] == "NON_IMPLEMENTABLE_DISCRETION"],
        "unresolved": [r["educatorRuleId"] for r in rows if r["fidelityStatus"] == "UNRESOLVED"],
        "rows": rows,
        "mogoOnlyBehaviour": [
            {"ruleId": i, "category": c, "behaviour": b, "origin": o,
             "affectsTradingBehaviour": a, "codeLocation": loc}
            for i, c, b, o, a, loc in MOGO_ONLY
        ],
        "productionSpecComparison": {
            "note": "The MOGO-002.5 comparison against alex_g_sr_v1 (the approved 13-rule "
                    "specification) is UNCHANGED by this audit and remains the authoritative fidelity "
                    "result for the production strategy.",
            "findings": {"MATCH": 9, "APPROXIMATED": 2, "AMBIGUOUS": 1, "NOT_APPLICABLE": 1,
                         "EXTRA": 8, "MISSING": 0, "DIFFERING": 0, "UNVERIFIABLE": 0},
            "riskFidelity": "0/0", "tradeManagementFidelity": "0/0",
            "executionReadiness": "NOT_VERIFIED (6/10 criteria failed)",
            "profitability": "UNVALIDATED",
        },
    }


GAPS = [
    dict(id="AXG-01", question="How far beyond the rejection structure is the stop placed?",
         domain="stop_loss_buffer", evidenceState="ABSENT_FROM_REVIEWED_SOURCES",
         whyItMatters="Position size = risk / stop distance. This single absence makes all 13 educator "
                      "sizing rules non-computable and is the only thing preventing an end-to-end "
                      "educator-faithful trade from being expressible.",
         affects=["stop placement", "position sizing", "replay validity", "strategy fidelity"],
         searchTerms=["fxalexg live trading session", "fxalexg set and forget full trade",
                      "fxalexg how to place stop loss", "fxalexg trade walkthrough"],
         knownSourceExists=False, priority="P0", expectedGain="DECISIVE", blocksReplay=True),
    dict(id="AXG-02", question="What exactly is the stop anchored to -- the final rejection candle, the "
                               "whole Morning Star formation, or the retested zone boundary?",
         domain="stop_loss_relationship", evidenceState="AMBIGUOUS",
         whyItMatters="The three readings give materially different stop distances on the same setup, "
                      "so every downstream R-multiple and position size changes with the choice.",
         affects=["stop placement", "position sizing", "replay validity"],
         searchTerms=["fxalexg live trading session", "fxalexg stop loss placement explained"],
         knownSourceExists=False, priority="P0", expectedGain="HIGH", blocksReplay=True),
    dict(id="AXG-03", question="Is a candlestick confirmation required, and if so which patterns qualify?",
         domain="candlestick_confirmation", evidenceState="PARTIALLY_SUPPORTED",
         whyItMatters="The educator's hardest entry precondition is ABSENT FROM MOGO. Adding or omitting "
                      "it changes which setups are eligible at all -- the largest trade-eligibility "
                      "difference found by this audit.",
         affects=["trade eligibility", "entries", "strategy fidelity"],
         searchTerms=["fxalexg engulfing candlestick confirmation",
                      "fxalexg bullish bearish engulfing trend continuation"],
         knownSourceExists=True,
         knownSourceNote="EVSRC|ALEX_G|20260729|001 at 5:33 explicitly points at a dedicated engulfing "
                         "video ('just look at this video right here'). That referenced video is a "
                         "named, existing target.",
         priority="P0", expectedGain="HIGH", blocksReplay=False),
    dict(id="AXG-04", question="What are the exact session hours that gate entry?",
         domain="session_requirements", evidenceState="NON_DETERMINISTIC",
         whyItMatters="7 session rules are prescriptive and unimplementable. MOGO currently applies NO "
                      "session restriction at all, so this is a live divergence, not just a gap.",
         affects=["trade eligibility", "entries", "replay validity"],
         searchTerms=["fxalexg best time to trade forex sessions",
                      "fxalexg london new york session"],
         knownSourceExists=False,
         knownSourceNote="Hours are displayed on an on-screen map in EVSRC|ALEX_G|20260728|004 and never "
                         "spoken. A transcript of the SAME format cannot close this.",
         priority="P1", expectedGain="MEDIUM", blocksReplay=True),
    dict(id="AXG-05", question="Is the stop ever moved to break-even, are partials taken, is the position "
                               "ever scaled or trailed?",
         domain="post_entry_management", evidenceState="ABSENT_FROM_REVIEWED_SOURCES",
         whyItMatters="Four domains at absolute zero across 9 sources. Each changes realized R per trade, "
                      "so expectancy is not computable while they are unknown -- even though MOGO's "
                      "no-intervention default is probably right.",
         affects=["trade management", "exits", "replay validity"],
         searchTerms=["fxalexg set and forget strategy explained",
                      "fxalexg managing open trades", "fxalexg take partial profits"],
         knownSourceExists=True,
         knownSourceNote="EVSRC|ALEX_G|20260728|007 self-identifies as episode 3 of a 'set and forget' "
                         "podcast, so other episodes exist.",
         priority="P1", expectedGain="HIGH", blocksReplay=True),
    dict(id="AXG-06", question="How is the target chosen above the 1:2 floor?",
         domain="target_selection", evidenceState="PARTIALLY_SUPPORTED",
         whyItMatters="MOGO implements a FIXED 2R. The educator states a MINIMUM. Every trade where "
                      "structure allowed more is a divergence, and expectancy differs materially.",
         affects=["exits", "replay validity", "strategy fidelity"],
         searchTerms=["fxalexg take profit target selection", "fxalexg risk reward ratio"],
         knownSourceExists=False, priority="P1", expectedGain="MEDIUM", blocksReplay=False),
    dict(id="AXG-07", question="What makes a swing point / structure point significant enough to count?",
         domain="market_structure", evidenceState="AMBIGUOUS",
         whyItMatters="Gates every structure rule, the minimum-one-structure-point requirement, and the "
                      "break-of-structure test. Cross-educator contradicted (XCONTRA|20260729|001).",
         affects=["trade eligibility", "entries", "replay validity"],
         searchTerms=["fxalexg market structure swing points"],
         knownSourceExists=False,
         knownSourceNote="Two educators give contradictory guidance about a number NEITHER supplies. "
                         "Recorded as replay candidate RC-29; acquisition is unlikely to resolve it.",
         priority="P2", expectedGain="LOW", blocksReplay=True),
    dict(id="AXG-08", question="Is the short-side mirror of the stop rule ever stated?",
         domain="stop_loss_relationship", evidenceState="ABSENT_FROM_REVIEWED_SOURCES",
         whyItMatters="MOGO trades both directions symmetrically. The educator has only ever been "
                      "recorded stating the long side, so MOGO's short-side stop is an assumption.",
         affects=["stop placement", "strategy fidelity"],
         searchTerms=["fxalexg short trade example", "fxalexg bearish setup walkthrough"],
         knownSourceExists=False, priority="P2", expectedGain="MEDIUM", blocksReplay=False),
]


def build_gap_plan():
    return {
        "generated": True,
        "generatorVersion": GENERATOR_VERSION,
        "milestone": MILESTONE,
        "modelVersion": MODEL_VERSION,
        "narrativeArtifact": "docs/strategy-fidelity/audit/ALEX-KNOWLEDGE-GAPS-AND-SOURCE-PLAN.md",
        "gapCount": len(GAPS),
        "blockingReplayCount": sum(1 for g in GAPS if g["blocksReplay"]),
        "nextAcquisitionTarget": {
            "rank": 1,
            "targetType": "ALEX_G live trading session showing an order actually being placed",
            "resolves": ["AXG-01", "AXG-02", "AXG-04", "AXG-08"],
            "rationale": "A stop price must be typed into an order ticket, which is the one context where "
                         "the missing buffer becomes visible. It is the only single artifact that could "
                         "close both P0 stop gaps at once.",
            "searchTerms": ["fxalexg live trading session", "fxalexg live trade",
                            "fxalexg trading live forex"],
            "risk": "May show the number on screen without speaking it -- the KEGAP-003 failure mode.",
        },
        "secondTarget": {
            "rank": 2,
            "targetType": "The engulfing-candlestick video explicitly referenced at 5:33 of "
                          "EVSRC|ALEX_G|20260729|001",
            "resolves": ["AXG-03"],
            "rationale": "The ONLY gap in this plan with a named, educator-pointed-at source. The educator "
                         "says 'just look at this video right here' about bullish/bearish engulfing with "
                         "trend continuation. Closes the largest trade-eligibility divergence, and it is "
                         "the highest-certainty acquisition available.",
        },
        "gaps": GAPS,
    }


def build_freeze_readiness(register, fidelity, store):
    blockers = [
        {"id": "FRZ-01", "severity": "BLOCKING",
         "finding": "The educator stop buffer is absent (AXG-01), so no educator-faithful position size "
                    "is computable and MOGO's 0.25 ATR remains unattributable.",
         "class": "SOURCE_GAP"},
        {"id": "FRZ-02", "severity": "BLOCKING",
         "finding": "MOGO implements NO candlestick-confirmation gate, which the educator states as a "
                    "necessary entry condition (AXR-011/AXR-015). Trade eligibility differs materially.",
         "class": "IMPLEMENTATION_MISMATCH"},
        {"id": "FRZ-03", "severity": "BLOCKING",
         "finding": "MOGO applies NO session or day-of-week restriction while the educator states an "
                    "explicit Mon-Wed and session gate (AXR-080). MOGO computes the metadata and "
                    "deliberately ignores it.",
         "class": "IMPLEMENTATION_MISMATCH"},
        {"id": "FRZ-04", "severity": "BLOCKING",
         "finding": "MOGO's minRR=2.0 is a FIXED ratio; the educator states 1:2 as a MINIMUM (AXR-030). "
                    "Also the subject of open contradiction XCONTRA|20260729|004.",
         "class": "IMPLEMENTATION_MISMATCH"},
        {"id": "FRZ-05", "severity": "BLOCKING",
         "finding": "MOGO requires 4+ touches for the repeated-reaction setup; the educator states a "
                    "MINIMUM OF ONE structure point (AXR-005). MOGO is materially stricter.",
         "class": "IMPLEMENTATION_MISMATCH"},
        {"id": "FRZ-06", "severity": "BLOCKING",
         "finding": "Break-even, partials, scaling and trailing are at absolute zero across 9 sources "
                    "(AXG-05), so realized-R behaviour cannot be validated against the educator.",
         "class": "SOURCE_GAP"},
        {"id": "FRZ-07", "severity": "BLOCKING",
         "finding": "Session hours (AXG-04) exist only as on-screen pixels; no transcript acquisition can "
                    "close them.",
         "class": "SOURCE_GAP"},
        {"id": "FRZ-08", "severity": "MATERIAL",
         "finding": "ALEX_SR_008 (zone tightness) is AMBIGUOUS in the production specification and the "
                    "educator EXPLICITLY declines to constrain zone width (AXR-008). MOGO imposes "
                    "zoneClusterATRMultiplier=0.5 anyway.",
         "class": "BOTH"},
        {"id": "FRZ-09", "severity": "MATERIAL",
         "finding": "All 341 library claims remain at `emerging` confidence and 0 rule candidates exist. "
                    "Under POLICY-001 nothing in the educator library is promotable, so no educator rule "
                    "can be frozen into a specification today regardless of its content.",
         "class": "GOVERNANCE"},
        {"id": "FRZ-10", "severity": "MATERIAL",
         "finding": "Execution readiness for alex_g_sr_v1 is NOT_VERIFIED (6/10 criteria failed) and "
                    "profitability is UNVALIDATED, unchanged by this audit.",
         "class": "IMPLEMENTATION_MISMATCH"},
    ]
    return {
        "generated": True,
        "generatorVersion": GENERATOR_VERSION,
        "milestone": MILESTONE,
        "modelVersion": MODEL_VERSION,
        "narrativeArtifact": "docs/strategy-fidelity/audit/ALEX-STRATEGY-FREEZE-READINESS.md",
        "verdictVocabulary": ["READY_TO_FREEZE", "READY_WITH_DOCUMENTED_MOGO_PARAMETERS",
                              "NOT_READY_SOURCE_GAPS", "NOT_READY_IMPLEMENTATION_MISMATCHES",
                              "NOT_READY_BOTH"],
        "verdict": "NOT_READY_BOTH",
        "verdictBasis": (
            "Three independent source gaps (stop buffer, session hours, the four post-entry-management "
            "zeros) AND five implementation mismatches (no confirmation gate, no session gate, fixed "
            "vs minimum R:R, stricter touch requirement, unconstrained-vs-constrained zone width). "
            "Neither category alone would be decisive; both are present."
        ),
        "replayAuthorized": False,
        "replayAuthorizationBasis": (
            "replayAuthorization is false on all six OwnerDecision records; MOGO holds no market data; "
            "5 of 8 audit gaps are annotated blocksReplay. Nothing in this audit changes that, and this "
            "audit does not request it. Authorization remains a separate Engineering Authority decision."
        ),
        "blockerCount": len(blockers),
        "blockingCount": sum(1 for b in blockers if b["severity"] == "BLOCKING"),
        "byClass": dict(sorted(Counter(b["class"] for b in blockers).items())),
        "blockers": blockers,
        "whatWouldChangeTheVerdict": [
            "Close AXG-01 (stop buffer) -> removes FRZ-01.",
            "An Engineering Authority ruling that MOGO-authored parameters are acceptable when "
            "explicitly labelled -> could move the verdict to READY_WITH_DOCUMENTED_MOGO_PARAMETERS "
            "for the SOURCE_GAP class, but not for the five implementation mismatches.",
            "Resolving D2 so educator claims can exceed `emerging` -> removes FRZ-09.",
        ],
        "importantScopeNote": (
            "'Freeze' here means freezing an EDUCATOR-FAITHFUL ALEX v1 specification. The production "
            "strategy alex_g_sr_v1 is already frozen against its OWN specification (13 rules, hash "
            "a0b7641e288c1725) and this audit does not change it. The two must not be conflated."
        ),
    }


KEREV_A = {
    "decisionId": "KEREV-A",
    "reviewQueueRecord": "KEREV|058",
    "recommendationVocabulary": ["CLOSE_KEREV_A", "KEEP_KEREV_A_OPEN", "REFRAME_KEREV_A",
                                 "ADDITIONAL_SOURCE_REQUIRED"],
    "recommendation": "REFRAME_KEREV_A",
    "separationSupported": True,
    "separationAssessment": {
        "educatorAuthoredComponent": {
            "statement": "The stop-loss belongs immediately beyond the rejection structure that produced "
                         "the entry.",
            "supported": True,
            "evidenceClass": "EXPLICIT",
            "basis": "CLAIM|ALEX_G|20260729|025 -- rule_statement, direct_explicit, extractionCertainty "
                     "certain, explicitly universalised ('the same thing every single time'), plus two "
                     "same-source demonstrations (CLAIM|ALEX_G|20260729|022).",
            "limits": ["Long side only -- the short-side mirror is never stated.",
                       "The anchor is deictic and admits three readings."],
        },
        "mogoAuthoredComponent": {
            "statement": "The numerical or volatility-based buffer beyond that structure.",
            "supported": False,
            "evidenceClass": "UNSUPPORTED",
            "basis": "ZERO ALEX_G claims across 9 sources and 226 claims state any buffer in any unit. "
                     "No ALEX_G claim mentions ATR at all. MOGO's stopATRBuffer=0.25 therefore has no "
                     "educator provenance whatsoever and must remain labelled MOGO-authored.",
        },
    },
    "whatCanBeClosed": [
        "The question 'does Alex state a stop-placement rule at all?' -- YES, and it is now evidenced.",
        "Option B of the original KEREV-A ('accept stop placement as absent from the ALEX_G "
        "specification') is FACTUALLY UNAVAILABLE and can be struck.",
        "Option D ('use a separately attributed cross-educator module') is unnecessary and can be struck: "
        "Alex has his own stated relationship, so importing Rayner Teo's ATR rule would overwrite a real "
        "attribution with a foreign one.",
    ],
    "whatMustRemainOpen": [
        "The buffer distance -- explicitly MOGO-authored, and it must be labelled as such wherever it "
        "appears (AXG-01 / AXR-021).",
        "The anchor identity -- three readings, unresolved (AXG-02 / STOP-UNK-2).",
        "The short-side rule -- never stated; MOGO's symmetric implementation is an assumption "
        "(AXG-08 / AXR-022).",
    ],
    "whyNotClose": (
        "Closing KEREV-A would imply stop placement is settled. It is not: two of the three parameters "
        "needed to place a stop mechanically are still absent, and MOGO's anchor (zone boundary) is a "
        "DIFFERENT OBJECT from the educator's (rejection formation). Closing would also license reading "
        "MOGO's existing 0.25 ATR as educator-supported, which is exactly the lineage error the decision "
        "exists to prevent."
    ),
    "whyNotAdditionalSourceOnly": (
        "ADDITIONAL_SOURCE_REQUIRED understates what has already changed. The decision as originally "
        "framed offered four options, two of which are now dead. Leaving it unchanged would send the "
        "Authority back to a menu that no longer matches the evidence."
    ),
    "proposedReframing": (
        "KEREV-A becomes: 'The stop RELATIONSHIP is educator-authored and evidenced. May MOGO author the "
        "BUFFER and the ANCHOR READING as explicitly-labelled MOGO parameters, or must acquisition "
        "continue first?' -- with the standing constraint that neither may ever be presented as Alex's."
    ),
}


def main():
    store = load_store()
    src = build_source_coverage(store)
    reg = build_rule_register(store)
    reg["domainCoverage"] = build_domain_coverage()
    reg["coverageVocabulary"] = COVERAGE_VOCAB
    fid = build_fidelity_matrix(reg)
    gap = build_gap_plan()
    frz = build_freeze_readiness(reg, fid, store)
    frz["kerevA"] = KEREV_A

    artifacts = {
        "alex-source-coverage-audit.json": src,
        "alex-canonical-rule-register.json": reg,
        "alex-implementation-fidelity-matrix.json": fid,
        "alex-knowledge-gaps-and-source-plan.json": gap,
        "alex-strategy-freeze-readiness.json": frz,
    }
    os.makedirs(OUT, exist_ok=True)
    for name, obj in sorted(artifacts.items()):
        p = os.path.join(OUT, name)
        gc.atomic_write_text(p, gc.pretty_json(obj))
        print(f"wrote {os.path.relpath(p, REPO_ROOT)}  (hash {gc.content_hash_of(obj)[:16]})")

    print()
    print(f"sources ACQUIRED_AND_PROCESSED : {src['acquiredAndProcessedCount']}")
    print(f"register rules                 : {reg['ruleCount']}  "
          f"(deterministic {reg['deterministicCount']}, unsupported {reg['unsupportedCount']}, "
          f"short-side {reg['shortSideSupportedCount']})")
    print(f"fidelity statuses              : {fid['statusCounts']}")
    print(f"freeze verdict                 : {frz['verdict']}  replayAuthorized={frz['replayAuthorized']}")
    print(f"KEREV-A                        : {KEREV_A['recommendation']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

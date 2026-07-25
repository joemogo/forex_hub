#!/usr/bin/env python3
"""PROGRAM-004 Phase 1 -- transparent, multi-dimension priority scoring.

Pure Python standard library. NO NETWORK ACCESS.

Every dimension is a disclosed heuristic over fields already present on the
candidate (topics, authenticityStatus, duplicateStatus, content presence) --
never a claim of deep content understanding. Unknown values stay null and are
excluded from the weighted average (never coerced to 0); scoringConfidence
reports exactly what fraction of positive dimensions were actually assessed.
Every re-score appends a new entry to priorityAssessments -- history is never
overwritten.
"""
import argparse
import glob as globmod
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import graph_common as gc          # noqa: E402
import acquisition_common as ac    # noqa: E402

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

_AUTHENTICITY_SCORE = {
    "VERIFIED_PRIMARY": 100, "LIKELY_PRIMARY": 70, "VERIFIED_SECONDARY": 50,
    "LIKELY_SECONDARY": 35, "UNVERIFIED": 15, "MISATTRIBUTED": 0, "REJECTED": 0,
}
_TACTICAL_TOPICS = {"ENTRIES", "EXITS", "STOP_PLACEMENT", "TARGETS", "RISK_MANAGEMENT", "MARKET_STRUCTURE", "LIQUIDITY"}
_FAILURE_TOPICS = {"TRADE_FAILURE", "MISTAKES", "MISSED_TRADE", "FALSE_POSITIVE", "FALSE_NEGATIVE"}
_REPLAY_TOPICS = {"REPLAY", "BACKTESTING"}
_PAPER_LEARNING_TOPICS = {"LIVE_TRADE", "TRADE_RECAP"}


def _topics_of(candidate):
    return {t["topic"] for t in candidate.get("topicCandidates", [])}


def _repository_gap_relevance(candidate, repo_root, ti_root, graph_root):
    """Queries the existing Knowledge Graph (read-only) for how many
    unresolved questions block the candidate's claimed/verified trader --
    counting both family-scoped BLOCKS edges (when a question already names a
    strategyFamilyId) and trader-scoped BLOCKS edges (today's real data: none
    of the 35 TJR UnresolvedQuestion records carry a strategyFamilyId yet, so
    they block the TRADER node directly -- see query_graph's own
    unresolved_questions_blocking_family uncertaintyNotes for the same fact).
    Returns None (not 0) if no trader is known or the graph query is
    unavailable for any reason -- absence of a computed value is never
    treated as 'no gap'."""
    trader_id = candidate.get("verifiedTraderId") or candidate.get("claimedTraderId")
    if not trader_id:
        return None
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import query_graph
        idx = query_graph.GraphIndex.load(repo_root, ti_root, graph_root)
        trader_node = idx.node_of(trader_id)
        if trader_node is None:
            return None
        family_ids = [n["entityId"] for n in idx.nodes
                      if n["nodeType"] == "STRATEGY_FAMILY" and n["traderId"] == trader_id]
        if not family_ids:
            return None
        total_blocking = 0
        for fam_id in family_ids:
            r = query_graph.unresolved_questions_blocking_family(idx, fam_id)
            total_blocking += r["resultCount"]
        trader_blocks = [e for e in idx.edges_to.get(trader_node["nodeId"], []) if e["edgeType"] == "BLOCKS"]
        total_blocking += len(trader_blocks)
        return min(100, total_blocking * 3)
    except Exception:
        return None


def compute_dimensions(candidate, weight_profile, repo_root, ti_root, graph_root):
    topics = _topics_of(candidate)
    has_content = candidate.get("storagePolicy") != "METADATA_ONLY" and candidate.get("contentHash")

    positive = {}
    positive["ruleExtractionPotential"] = (
        80 if has_content and (topics & _TACTICAL_TOPICS) else
        (30 if has_content else None)
    )
    positive["repositoryGapRelevance"] = _repository_gap_relevance(candidate, repo_root, ti_root, graph_root)
    positive["tradeFailureInsightPotential"] = 75 if (topics & _FAILURE_TOPICS) else None
    positive["creatorAuthenticity"] = _AUTHENTICITY_SCORE.get(candidate.get("authenticityStatus"))
    positive["replayModelingPotential"] = 70 if (topics & _REPLAY_TOPICS) else None
    positive["paperTradingLearningPotential"] = 60 if (topics & _PAPER_LEARNING_TOPICS) else None
    positive["chartExampleDensity"] = 80 if candidate.get("sourceType") == "CHART_SCREENSHOT" else None
    positive["riskManagementRelevance"] = 75 if "RISK_MANAGEMENT" in topics else None
    dup_status = candidate.get("duplicateStatus")
    positive["noveltyScore"] = {"NONE": 60, "POSSIBLE_NEAR_DUPLICATE": 30, "EXACT_DUPLICATE": 0}.get(dup_status)

    penalty = {}
    penalty["promotionalContentScore"] = 80 if "PROMOTIONAL_CONTENT" in topics else None
    penalty["lifestyleContentScore"] = 80 if "LIFESTYLE_CONTENT" in topics else None
    penalty["genericMotivationScore"] = None  # not assessed by this Phase 1 keyword heuristic
    penalty["duplicationPenalty"] = {"NONE": 0, "POSSIBLE_NEAR_DUPLICATE": 50, "EXACT_DUPLICATE": 100}.get(dup_status, 0)
    low_authority = candidate.get("authenticityStatus") in ("LIKELY_SECONDARY", "UNVERIFIED") and not has_content
    penalty["lowAuthoritySummaryPenalty"] = 60 if low_authority else (0 if candidate.get("authenticityStatus") in
                                                                        ("VERIFIED_PRIMARY", "LIKELY_PRIMARY") else None)
    return positive, penalty


def score_candidate(candidate, weight_profile, now, repo_root, ti_root, graph_root):
    positive, penalty = compute_dimensions(candidate, weight_profile, repo_root, ti_root, graph_root)
    all_dims = dict(positive)
    all_dims.update(penalty)
    missing = [k for k, v in all_dims.items() if v is None]

    weights = weight_profile["positiveDimensionWeights"]
    populated_weight_sum = sum(weights[d] for d in positive if positive[d] is not None and d in weights)
    if populated_weight_sum > 0:
        base = sum(positive[d] * weights[d] for d in positive if positive[d] is not None and d in weights) / populated_weight_sum
    else:
        base = None

    populated_penalties = [penalty[d] for d in weight_profile["penaltyDimensions"] if penalty.get(d) is not None]
    if populated_penalties:
        penalty_fraction = min(sum(populated_penalties) / len(populated_penalties) / 100.0,
                                weight_profile.get("maxPenaltyDiscount", 0.9))
    else:
        penalty_fraction = 0.0

    recommendation_score = round(base * (1 - penalty_fraction), 2) if base is not None else None
    scoring_confidence = round(
        sum(1 for d in positive if positive[d] is not None) / len(positive), 3
    ) if positive else 0.0

    populated_desc = ", ".join("%s=%s" % (k, v) for k, v in positive.items() if v is not None) or "none"
    penalty_desc = ", ".join("%s=%s" % (k, v) for k, v in penalty.items() if v is not None) or "none"
    explanation = "base=%s from populated positive dims [%s]; penaltyFraction=%.3f from [%s]; missing=%s" % (
        base, populated_desc, penalty_fraction, penalty_desc, missing)

    existing = candidate.get("priorityAssessments", [])
    assessment_id = ac.make_score_id(candidate["candidateId"], len(existing) + 1)
    return {
        "assessmentId": assessment_id,
        "weightProfileId": weight_profile["weightProfileId"],
        "weightProfileVersion": weight_profile["version"],
        "dimensions": all_dims,
        "missingDimensions": missing,
        "scoringConfidence": scoring_confidence,
        "recommendationScore": recommendation_score,
        "explanation": explanation,
        "computedAt": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def prioritize_all(candidates_dir, weights_dir, repo_root, ti_root, graph_root, now,
                    weight_profile_path=None):
    if weight_profile_path is None:
        weight_profile_path = os.path.join(weights_dir, "priority-profile-mogo-research-v1.json")
    with open(weight_profile_path, "r", encoding="utf-8") as f:
        weight_profile = json.load(f)

    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    scored = []
    for path in sorted(globmod.glob(os.path.join(candidates_dir, "*.json"))):
        with open(path, "r", encoding="utf-8") as f:
            candidate = json.load(f)
        assessment = score_candidate(candidate, weight_profile, now, repo_root, ti_root, graph_root)
        candidate["priorityAssessments"].append(assessment)
        candidate["changeLog"].append({
            "changedAt": now_iso, "changedFields": ["priorityAssessments"],
            "reason": "prioritize_sources.py re-score under %s" % weight_profile["weightProfileId"],
        })
        candidate["updatedAt"] = now_iso
        candidate["processingStatus"] = "prioritized"
        if candidate["acquisitionStatus"] == "DUPLICATE_REVIEW":
            ac.advance_status(candidate, "PRIORITIZED", now,
                               "prioritize_sources.py computed assessment %s" % assessment["assessmentId"])
        if candidate["acquisitionStatus"] == "PRIORITIZED":
            ac.advance_status(candidate, "OWNER_REVIEW", now,
                               "Candidate is scored and ready for owner review -- no further automatic step in Phase 1.")
            # ownerReviewStatus deliberately stays 'not_reviewed' here -- entering
            # the queue is not the same as the owner having actually looked at it.
        gc.atomic_write_text(path, gc.pretty_json(candidate))
        scored.append(candidate)
    return scored, weight_profile


def main():
    parser = argparse.ArgumentParser(description="Score every PROGRAM-004 candidate on transparent priority dimensions.")
    parser.add_argument("--candidates-dir", default=os.path.join(REPO_ROOT, "docs", "trader-intelligence", "acquisition", "candidates"))
    parser.add_argument("--weights-dir", default=os.path.join(REPO_ROOT, "docs", "trader-intelligence", "acquisition", "weights"))
    parser.add_argument("--repo-root", default=REPO_ROOT)
    parser.add_argument("--ti-root", default=os.path.join(REPO_ROOT, "docs", "trader-intelligence"))
    parser.add_argument("--graph-root", default=os.path.join(REPO_ROOT, "docs", "trader-intelligence", "graph"))
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    scored, profile = prioritize_all(args.candidates_dir, args.weights_dir, args.repo_root, args.ti_root, args.graph_root, now)
    print("Scored %d candidate(s) under %s" % (len(scored), profile["weightProfileId"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

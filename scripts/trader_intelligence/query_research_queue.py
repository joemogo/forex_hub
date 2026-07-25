#!/usr/bin/env python3
"""PROGRAM-004 Phase 1 -- deterministic, read-only research-queue queries.

Pure Python standard library. NO NETWORK ACCESS.

Same status discipline as query_graph.py: ok | empty | not_found | invalid_input
| not_implemented | blocked. Every query returns uncertaintyNotes and never
fabricates a relationship or metadata value that isn't actually present on a
candidate record.
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


class QueueIndex:
    def __init__(self, candidates, duplicate_groups, repo_root, ti_root, graph_root):
        self.candidates = candidates
        self.by_id = {c["candidateId"]: c for c in candidates}
        self.duplicate_groups = duplicate_groups
        self.repo_root = repo_root
        self.ti_root = ti_root
        self.graph_root = graph_root

    @classmethod
    def load(cls, candidates_dir, reports_dir, repo_root, ti_root, graph_root):
        candidates = []
        for path in sorted(globmod.glob(os.path.join(candidates_dir, "*.json"))):
            with open(path, "r", encoding="utf-8") as f:
                candidates.append(json.load(f))
        dup_report_path = os.path.join(reports_dir, "duplicate-report.json")
        groups = []
        if os.path.exists(dup_report_path):
            with open(dup_report_path, "r", encoding="utf-8") as f:
                groups = json.load(f).get("groups", [])
        return cls(candidates, groups, repo_root, ti_root, graph_root)

    def latest_assessment(self, candidate):
        a = candidate.get("priorityAssessments") or []
        return a[-1] if a else None

    def dimension(self, candidate, name):
        a = self.latest_assessment(candidate)
        return a["dimensions"].get(name) if a else None


def _result(query, inputs, status, results, uncertainty_notes=None):
    return {
        "query": query, "inputs": inputs, "status": status,
        "results": results, "resultCount": len(results),
        "uncertaintyNotes": uncertainty_notes or [],
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def _sort_by_score_desc(idx, candidates):
    def key(c):
        a = idx.latest_assessment(c)
        score = a["recommendationScore"] if a else None
        return (0 if score is not None else 1, -(score or 0), c["discoveredAt"], c["candidateId"])
    return sorted(candidates, key=key)


def _row(idx, c):
    a = idx.latest_assessment(c)
    return {
        "candidateId": c["candidateId"], "title": c.get("title"),
        "recommendationScore": a["recommendationScore"] if a else None,
        "acquisitionStatus": c["acquisitionStatus"], "duplicateStatus": c["duplicateStatus"],
    }


# 1
def highest_priority_overall(idx):
    rows = [_row(idx, c) for c in _sort_by_score_desc(idx, idx.candidates)]
    return _result("highest_priority_overall", {}, "ok" if rows else "empty", rows)


# 2
def highest_priority_for_trader(idx, trader_id):
    matches = [c for c in idx.candidates if c.get("claimedTraderId") == trader_id or c.get("verifiedTraderId") == trader_id]
    rows = [_row(idx, c) for c in _sort_by_score_desc(idx, matches)]
    return _result("highest_priority_for_trader", {"traderId": trader_id}, "ok" if rows else "empty", rows)


# 3
def likely_to_resolve_adr007(idx, threshold=30):
    if not os.path.exists(os.path.join(idx.graph_root, "build", "nodes.json")):
        return _result("likely_to_resolve_adr007", {"threshold": threshold}, "blocked", [],
                        ["Knowledge Graph has not been built yet (no nodes.json) -- run build_graph.py first."])
    matches = [c for c in idx.candidates if (idx.dimension(c, "repositoryGapRelevance") or 0) >= threshold]
    rows = [_row(idx, c) for c in _sort_by_score_desc(idx, matches)]
    notes = [] if rows else ["No candidate currently has a computed repositoryGapRelevance at or above the threshold; "
                              "this dimension requires a known claimedTraderId/verifiedTraderId and a built graph."]
    return _result("likely_to_resolve_adr007", {"threshold": threshold}, "ok" if rows else "empty", rows, notes)


# 4
def unreviewed_candidates(idx):
    matches = [c for c in idx.candidates if c["ownerReviewStatus"] == "not_reviewed"]
    rows = [_row(idx, c) for c in _sort_by_score_desc(idx, matches)]
    return _result("unreviewed_candidates", {}, "ok" if rows else "empty", rows)


# 5
def exact_duplicates(idx):
    matches = [c for c in idx.candidates if c["duplicateStatus"] == "EXACT_DUPLICATE"]
    rows = [_row(idx, c) for c in matches]
    return _result("exact_duplicates", {}, "ok" if rows else "empty", rows)


# 6
def possible_near_duplicates(idx):
    matches = [c for c in idx.candidates if c["duplicateStatus"] == "POSSIBLE_NEAR_DUPLICATE"]
    rows = [_row(idx, c) for c in matches]
    return _result("possible_near_duplicates", {}, "ok" if rows else "empty", rows)


# 7
def failed_acquisitions(idx):
    matches = [c for c in idx.candidates if c["acquisitionStatus"] == "ACQUISITION_FAILED"]
    return _result("failed_acquisitions", {}, "ok" if matches else "empty", [_row(idx, c) for c in matches])


# 8
def candidates_with_content(idx):
    matches = [c for c in idx.candidates if c["storagePolicy"] != "METADATA_ONLY" and c.get("contentHash")]
    return _result("candidates_with_content", {}, "ok" if matches else "empty", [_row(idx, c) for c in matches])


# 9
def candidates_without_content(idx):
    matches = [c for c in idx.candidates if not (c["storagePolicy"] != "METADATA_ONLY" and c.get("contentHash"))]
    return _result("candidates_without_content", {}, "ok" if matches else "empty", [_row(idx, c) for c in matches])


# 10
def by_topic(idx, topic):
    if topic not in ac.TOPICS:
        return _result("by_topic", {"topic": topic}, "invalid_input", [], ["%r is not a recognized topic" % topic])
    matches = [c for c in idx.candidates if topic in {t["topic"] for t in c.get("topicCandidates", [])}]
    rows = [_row(idx, c) for c in _sort_by_score_desc(idx, matches)]
    return _result("by_topic", {"topic": topic}, "ok" if rows else "empty", rows)


# 11
def by_strategy_family(idx, strategy_family_id):
    matches = [c for c in idx.candidates if strategy_family_id in c.get("strategyFamilyCandidates", [])]
    rows = [_row(idx, c) for c in matches]
    return _result("by_strategy_family", {"strategyFamilyId": strategy_family_id}, "ok" if rows else "empty", rows)


# 12
def primary_vs_secondary(idx):
    primary = [c["candidateId"] for c in idx.candidates if c["authenticityStatus"] in ("VERIFIED_PRIMARY", "LIKELY_PRIMARY")]
    secondary = [c["candidateId"] for c in idx.candidates if c["authenticityStatus"] in ("VERIFIED_SECONDARY", "LIKELY_SECONDARY")]
    other = [c["candidateId"] for c in idx.candidates if c["authenticityStatus"] not in
             ("VERIFIED_PRIMARY", "LIKELY_PRIMARY", "VERIFIED_SECONDARY", "LIKELY_SECONDARY")]
    results = [{"primary": primary, "secondary": secondary, "other": other}]
    status = "ok" if (primary or secondary or other) else "empty"
    return _result("primary_vs_secondary", {}, status, results)


# 13
def rejected_and_why(idx):
    matches = [c for c in idx.candidates if c["acquisitionStatus"] == "REJECTED" or c["ownerReviewStatus"] == "rejected"]
    rows = [{"candidateId": c["candidateId"], "title": c.get("title"), "rejectionReason": c.get("rejectionReason")} for c in matches]
    return _result("rejected_and_why", {}, "ok" if rows else "empty", rows)


# 14
def approved_but_not_acquired(idx):
    matches = [c for c in idx.candidates if c["acquisitionStatus"] in ("APPROVED_FOR_ACQUISITION", "ACQUISITION_IN_PROGRESS")]
    return _result("approved_but_not_acquired", {}, "ok" if matches else "empty", [_row(idx, c) for c in matches])


# 15
def acquired_but_not_extracted(idx):
    matches = [c for c in idx.candidates if c["acquisitionStatus"] in ("ACQUIRED", "APPROVED_FOR_EXTRACTION", "EXTRACTION_IN_PROGRESS")]
    return _result("acquired_but_not_extracted", {}, "ok" if matches else "empty", [_row(idx, c) for c in matches])


# 16
def ready_for_research_intake(idx):
    matches = [c for c in idx.candidates if c["acquisitionStatus"] == "READY_FOR_RESEARCH_INTAKE"]
    return _result("ready_for_research_intake", {}, "ok" if matches else "empty", [_row(idx, c) for c in matches])


# 17
def approved_for_research_intake(idx):
    matches = [c for c in idx.candidates if c["acquisitionStatus"] == "APPROVED_FOR_RESEARCH_INTAKE"]
    return _result("approved_for_research_intake", {}, "ok" if matches else "empty", [_row(idx, c) for c in matches])


# 18
def highest_novelty(idx):
    scored = [c for c in idx.candidates if idx.dimension(c, "noveltyScore") is not None]
    rows_sorted = sorted(scored, key=lambda c: (-idx.dimension(c, "noveltyScore"), c["candidateId"]))
    rows = [dict(_row(idx, c), noveltyScore=idx.dimension(c, "noveltyScore")) for c in rows_sorted]
    notes = [] if rows else ["No candidate has a computed noveltyScore yet -- run prioritize_sources.py."]
    return _result("highest_novelty", {}, "ok" if rows else "empty", rows, notes)


# 19
def largest_repository_gap(idx):
    scored = [c for c in idx.candidates if idx.dimension(c, "repositoryGapRelevance") is not None]
    rows_sorted = sorted(scored, key=lambda c: (-idx.dimension(c, "repositoryGapRelevance"), c["candidateId"]))
    rows = [dict(_row(idx, c), repositoryGapRelevance=idx.dimension(c, "repositoryGapRelevance")) for c in rows_sorted]
    notes = [] if rows else ["No candidate has a computed repositoryGapRelevance yet (requires a known trader and a built graph)."]
    return _result("largest_repository_gap", {}, "ok" if rows else "empty", rows, notes)


# 20
def conflicting_attribution(idx):
    matches = []
    for c in idx.candidates:
        claimed, verified = c.get("claimedTraderId"), c.get("verifiedTraderId")
        if claimed and verified and claimed != verified:
            matches.append(c)
    for group in idx.duplicate_groups:
        members = [idx.by_id[cid] for cid in group["memberCandidateIds"] if cid in idx.by_id]
        claimed_ids = {m.get("claimedTraderId") for m in members if m.get("claimedTraderId")}
        if len(claimed_ids) > 1:
            matches.extend(m for m in members if m not in matches)
    rows = [{"candidateId": c["candidateId"], "claimedTraderId": c.get("claimedTraderId"),
             "verifiedTraderId": c.get("verifiedTraderId")} for c in matches]
    return _result("conflicting_attribution", {}, "ok" if rows else "empty", rows)


# 21
def playlist_channel_expansion_status(idx):
    matches = [c for c in idx.candidates if c["discoveryMethod"] in ("PLAYLIST_URL", "CHANNEL_URL")]
    rows = [{"candidateId": c["candidateId"], "discoveryMethod": c["discoveryMethod"],
             "acquisitionStatus": c["acquisitionStatus"]} for c in matches]
    notes = ["All playlist/channel candidates remain register-only in Phase 1 -- per-item expansion requires a "
             "Phase 3 connector that does not exist yet."] if rows else []
    return _result("playlist_channel_expansion_status", {}, "ok" if rows else "empty", rows, notes)


# 22
def queue_history(idx):
    events = []
    for c in idx.candidates:
        for entry in c.get("changeLog", []):
            events.append({"candidateId": c["candidateId"], "changedAt": entry["changedAt"],
                            "changedFields": entry["changedFields"], "reason": entry.get("reason")})
    events.sort(key=lambda e: (e["changedAt"], e["candidateId"]))
    return _result("queue_history", {}, "ok" if events else "empty", events)


# 23
def owner_decisions_affecting_candidate(idx, candidate_id):
    c = idx.by_id.get(candidate_id)
    if c is None:
        return _result("owner_decisions_affecting_candidate", {"candidateId": candidate_id}, "not_found", [])
    decision_ids = c.get("ownerDecisionIds", [])
    rows = []
    decisions_dir = os.path.join(idx.graph_root, "decisions")
    for decision_id in decision_ids:
        found = None
        for path in globmod.glob(os.path.join(decisions_dir, "*.json")):
            with open(path, "r", encoding="utf-8") as f:
                d = json.load(f)
            if d.get("decisionId") == decision_id:
                found = d
                break
        rows.append({"decisionId": decision_id, "found": found is not None,
                      "question": found.get("question") if found else None})
    return _result("owner_decisions_affecting_candidate", {"candidateId": candidate_id}, "ok" if rows else "empty", rows)


# 24
def candidates_lacking_owner_attribution_confirmation(idx):
    matches = [c for c in idx.candidates if not c.get("verifiedTraderId")
               and c["acquisitionStatus"] not in ("REJECTED", "ARCHIVED")]
    rows = [{"candidateId": c["candidateId"], "claimedTraderId": c.get("claimedTraderId"),
             "authenticityStatus": c["authenticityStatus"]} for c in matches]
    return _result("candidates_lacking_owner_attribution_confirmation", {}, "ok" if rows else "empty", rows)


QUERIES = {
    "highest_priority_overall": highest_priority_overall,
    "highest_priority_for_trader": highest_priority_for_trader,
    "likely_to_resolve_adr007": likely_to_resolve_adr007,
    "unreviewed_candidates": unreviewed_candidates,
    "exact_duplicates": exact_duplicates,
    "possible_near_duplicates": possible_near_duplicates,
    "failed_acquisitions": failed_acquisitions,
    "candidates_with_content": candidates_with_content,
    "candidates_without_content": candidates_without_content,
    "by_topic": by_topic,
    "by_strategy_family": by_strategy_family,
    "primary_vs_secondary": primary_vs_secondary,
    "rejected_and_why": rejected_and_why,
    "approved_but_not_acquired": approved_but_not_acquired,
    "acquired_but_not_extracted": acquired_but_not_extracted,
    "ready_for_research_intake": ready_for_research_intake,
    "approved_for_research_intake": approved_for_research_intake,
    "highest_novelty": highest_novelty,
    "largest_repository_gap": largest_repository_gap,
    "conflicting_attribution": conflicting_attribution,
    "playlist_channel_expansion_status": playlist_channel_expansion_status,
    "queue_history": queue_history,
    "owner_decisions_affecting_candidate": owner_decisions_affecting_candidate,
    "candidates_lacking_owner_attribution_confirmation": candidates_lacking_owner_attribution_confirmation,
}


def main():
    parser = argparse.ArgumentParser(description="Run a read-only PROGRAM-004 research-queue query.")
    parser.add_argument("query", choices=sorted(QUERIES.keys()))
    parser.add_argument("args", nargs="*")
    parser.add_argument("--candidates-dir", default=os.path.join(REPO_ROOT, "docs", "trader-intelligence", "acquisition", "candidates"))
    parser.add_argument("--reports-dir", default=os.path.join(REPO_ROOT, "docs", "trader-intelligence", "acquisition", "reports"))
    parser.add_argument("--repo-root", default=REPO_ROOT)
    parser.add_argument("--ti-root", default=os.path.join(REPO_ROOT, "docs", "trader-intelligence"))
    parser.add_argument("--graph-root", default=os.path.join(REPO_ROOT, "docs", "trader-intelligence", "graph"))
    args = parser.parse_args()

    idx = QueueIndex.load(args.candidates_dir, args.reports_dir, args.repo_root, args.ti_root, args.graph_root)
    result = QUERIES[args.query](idx, *args.args)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

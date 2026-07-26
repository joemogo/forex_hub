#!/usr/bin/env python3
"""PROGRAM-006 Phase 1A -- deterministic, read-only Evidence Intelligence
queries (ADR-008, Deliverable 9).

Pure Python standard library. NO NETWORK ACCESS. Every query returns a
structured result and never mutates stored data. Works correctly against a
genuinely empty evidence corpus (confirmed by test).
"""
import argparse
import glob as globmod
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import evidence_common as evc      # noqa: E402
import evidence_dedup as dedup     # noqa: E402

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _load_dir(dir_path, id_field):
    out = {}
    if not os.path.isdir(dir_path):
        return out
    for path in sorted(globmod.glob(os.path.join(dir_path, "*.json"))):
        with open(path, "r", encoding="utf-8") as f:
            record = json.load(f)
        out[record[id_field]] = record
    return out


class EvidenceIndex:
    def __init__(self, sources, items, claims, links, contradictions, lifecycle_events):
        self.sources = sources
        self.items = items
        self.claims = claims
        self.links = links
        self.contradictions = contradictions
        self.lifecycle_events = lifecycle_events

    @classmethod
    def load(cls, evidence_root):
        sources = _load_dir(os.path.join(evidence_root, "sources"), "sourceId")
        items = _load_dir(os.path.join(evidence_root, "items"), "evidenceId")
        claims = _load_dir(os.path.join(evidence_root, "claims"), "claimId")
        links = _load_dir(os.path.join(evidence_root, "links"), "linkId")
        contradictions = _load_dir(os.path.join(evidence_root, "contradictions"), "contradictionId")
        lifecycle_events = _load_dir(os.path.join(evidence_root, "lifecycle"), "eventId")
        return cls(sources, items, claims, links, contradictions, lifecycle_events)

    def links_for_claim(self, claim_id):
        return [l for l in self.links.values() if l["claimId"] == claim_id]

    def links_for_evidence(self, evidence_id):
        return [l for l in self.links.values() if l["evidenceId"] == evidence_id]


def _result(query, inputs, status, results, uncertainty_notes=None):
    return {
        "query": query, "inputs": inputs, "status": status,
        "results": results, "resultCount": len(results),
        "uncertaintyNotes": uncertainty_notes or [],
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


# 1
def get_source_by_id(idx, source_id):
    s = idx.sources.get(source_id)
    return _result("get_source_by_id", {"sourceId": source_id}, "ok" if s else "not_found", [s] if s else [])


# 2
def list_evidence_by_source(idx, source_id):
    if source_id not in idx.sources:
        return _result("list_evidence_by_source", {"sourceId": source_id}, "not_found", [])
    matches = [e for e in idx.items.values() if e["sourceId"] == source_id]
    matches.sort(key=lambda e: e["evidenceId"])
    return _result("list_evidence_by_source", {"sourceId": source_id}, "ok" if matches else "empty", matches)


# 3
def get_evidence_by_id(idx, evidence_id):
    e = idx.items.get(evidence_id)
    return _result("get_evidence_by_id", {"evidenceId": evidence_id}, "ok" if e else "not_found", [e] if e else [])


# 4
def get_claim_by_id(idx, claim_id):
    c = idx.claims.get(claim_id)
    return _result("get_claim_by_id", {"claimId": claim_id}, "ok" if c else "not_found", [c] if c else [])


# 5
def list_evidence_supporting_claim(idx, claim_id):
    if claim_id not in idx.claims:
        return _result("list_evidence_supporting_claim", {"claimId": claim_id}, "not_found", [])
    links = [l for l in idx.links_for_claim(claim_id) if l["relationshipType"] in ("supports", "exemplifies")]
    results = [{"link": l, "evidence": idx.items.get(l["evidenceId"])} for l in links]
    return _result("list_evidence_supporting_claim", {"claimId": claim_id}, "ok" if results else "empty", results)


# 6
def list_evidence_contradicting_claim(idx, claim_id):
    if claim_id not in idx.claims:
        return _result("list_evidence_contradicting_claim", {"claimId": claim_id}, "not_found", [])
    links = [l for l in idx.links_for_claim(claim_id) if l["relationshipType"] == "contradicts"]
    results = [{"link": l, "evidence": idx.items.get(l["evidenceId"])} for l in links]
    return _result("list_evidence_contradicting_claim", {"claimId": claim_id}, "ok" if results else "empty", results)


# 7
def list_unresolved_claims(idx):
    matches = [c for c in idx.claims.values() if c["confidenceState"] == "unresolved"]
    matches.sort(key=lambda c: c["claimId"])
    return _result("list_unresolved_claims", {}, "ok" if matches else "empty", matches)


# 8
def list_contested_claims(idx):
    matches = [c for c in idx.claims.values() if c["confidenceState"] == "contested"]
    matches.sort(key=lambda c: c["claimId"])
    return _result("list_contested_claims", {}, "ok" if matches else "empty", matches)


def _claims_by(idx, field, value):
    matches = [c for c in idx.claims.values() if c.get(field) == value]
    matches.sort(key=lambda c: c["claimId"])
    return matches


# 9
def list_claims_by_trader(idx, trader_id):
    matches = _claims_by(idx, "traderId", trader_id)
    return _result("list_claims_by_trader", {"traderId": trader_id}, "ok" if matches else "empty", matches)


# 10
def list_claims_by_strategy_family(idx, strategy_family_id):
    matches = _claims_by(idx, "strategyFamilyId", strategy_family_id)
    return _result("list_claims_by_strategy_family", {"strategyFamilyId": strategy_family_id}, "ok" if matches else "empty", matches)


# 11
def list_claims_by_type(idx, claim_type):
    if claim_type not in evc.CLAIM_TYPES:
        return _result("list_claims_by_type", {"claimType": claim_type}, "invalid_input", [],
                        ["%r is not a recognized claimType" % claim_type])
    matches = _claims_by(idx, "claimType", claim_type)
    return _result("list_claims_by_type", {"claimType": claim_type}, "ok" if matches else "empty", matches)


# 12
def list_claims_by_timeframe(idx, timeframe):
    matches = _claims_by(idx, "timeframe", timeframe)
    return _result("list_claims_by_timeframe", {"timeframe": timeframe}, "ok" if matches else "empty", matches)


# 13
def list_claims_by_session(idx, session):
    matches = _claims_by(idx, "session", session)
    return _result("list_claims_by_session", {"session": session}, "ok" if matches else "empty", matches)


# 14
def list_claims_by_market_condition(idx, market_condition):
    matches = _claims_by(idx, "marketCondition", market_condition)
    return _result("list_claims_by_market_condition", {"marketCondition": market_condition}, "ok" if matches else "empty", matches)


# 15
def list_claims_with_insufficient_evidence(idx):
    matches = [c for c in idx.claims.values() if c["confidenceState"] == "insufficient_evidence"]
    matches.sort(key=lambda c: c["claimId"])
    return _result("list_claims_with_insufficient_evidence", {}, "ok" if matches else "empty", matches)


# 16
def list_contradiction_records(idx):
    matches = sorted(idx.contradictions.values(), key=lambda c: c["contradictionId"])
    return _result("list_contradiction_records", {}, "ok" if matches else "empty", matches)


# 17
def get_confidence_explanation(idx, claim_id):
    claim = idx.claims.get(claim_id)
    if claim is None:
        return _result("get_confidence_explanation", {"claimId": claim_id}, "not_found", [])
    events = [e for e in idx.lifecycle_events.values()
              if e["entityType"] == "CLAIM" and e["entityId"] == claim_id and e["eventType"] == "confidence_recomputed"]
    events.sort(key=lambda e: e["timestamp"])
    latest = events[-1] if events else None
    result = {
        "claimId": claim_id, "confidenceState": claim["confidenceState"],
        "confidenceScore": claim["confidenceScore"], "confidenceMethod": claim["confidenceMethod"],
        "counts": {k: claim[k] for k in ("evidenceCount", "supportingEvidenceCount", "contradictingEvidenceCount",
                                          "weakeningEvidenceCount", "contextualEvidenceCount")},
        "explanation": latest["reason"] if latest else None,
        "lastEvaluatedAt": claim["lastEvaluatedAt"],
    }
    notes = [] if latest else ["No confidence_recomputed lifecycle event found -- confidence may still be at its initial default."]
    return _result("get_confidence_explanation", {"claimId": claim_id}, "ok", [result], notes)


# 18
def trace_evidence_provenance(idx, evidence_id):
    evidence = idx.items.get(evidence_id)
    if evidence is None:
        return _result("trace_evidence_provenance", {"evidenceId": evidence_id}, "not_found", [])
    chain = [evidence]
    cursor = evidence
    while cursor.get("parentEvidenceId"):
        parent = idx.items.get(cursor["parentEvidenceId"])
        if parent is None or parent in chain:
            break
        chain.append(parent)
        cursor = parent
    source = idx.sources.get(evidence["sourceId"])
    events = sorted([e for e in idx.lifecycle_events.values()
                      if e["entityType"] == "EVIDENCE_ITEM" and e["entityId"] == evidence_id],
                     key=lambda e: e["timestamp"])
    result = {"evidence": evidence, "derivationChain": chain, "source": source, "lifecycleHistory": events}
    return _result("trace_evidence_provenance", {"evidenceId": evidence_id}, "ok", [result])


# 19
def trace_claim_to_source_provenance(idx, claim_id):
    claim = idx.claims.get(claim_id)
    if claim is None:
        return _result("trace_claim_to_source_provenance", {"claimId": claim_id}, "not_found", [])
    links = idx.links_for_claim(claim_id)
    trail = []
    for link in links:
        evidence = idx.items.get(link["evidenceId"])
        source = idx.sources.get(evidence["sourceId"]) if evidence else None
        trail.append({"link": link, "evidence": evidence, "source": source})
    return _result("trace_claim_to_source_provenance", {"claimId": claim_id}, "ok" if trail else "empty", trail)


# 20
def detect_orphaned_records(idx):
    orphans = []
    for evidence_id, e in idx.items.items():
        if e["sourceId"] not in idx.sources:
            orphans.append({"type": "EVIDENCE_ITEM", "id": evidence_id, "reason": "sourceId %r does not exist" % e["sourceId"]})
    for link_id, l in idx.links.items():
        if l["evidenceId"] not in idx.items:
            orphans.append({"type": "EVIDENCE_CLAIM_LINK", "id": link_id, "reason": "evidenceId %r does not exist" % l["evidenceId"]})
        if l["claimId"] not in idx.claims:
            orphans.append({"type": "EVIDENCE_CLAIM_LINK", "id": link_id, "reason": "claimId %r does not exist" % l["claimId"]})
    for claim_id, c in idx.claims.items():
        if not idx.links_for_claim(claim_id) and c["evidenceCount"] > 0:
            orphans.append({"type": "CLAIM", "id": claim_id, "reason": "evidenceCount>0 but no matching links found"})
    for cid, cr in idx.contradictions.items():
        if cr["claimAId"] not in idx.claims:
            orphans.append({"type": "CONTRADICTION_RECORD", "id": cid, "reason": "claimAId %r does not exist" % cr["claimAId"]})
        if cr["claimBId"] not in idx.claims:
            orphans.append({"type": "CONTRADICTION_RECORD", "id": cid, "reason": "claimBId %r does not exist" % cr["claimBId"]})
    return _result("detect_orphaned_records", {}, "ok" if orphans else "empty", orphans)


# 21
def detect_duplicate_candidates(idx):
    claims_list = list(idx.claims.values())
    exact = dedup.find_exact_duplicate_groups(claims_list)
    near = dedup.find_near_duplicate_candidates(claims_list)
    results = [{"type": "exact", "claimIds": g} for g in exact] + [{"type": "near", **c} for c in near]
    return _result("detect_duplicate_candidates", {}, "ok" if results else "empty", results)


# 22
def evidence_system_summary(idx):
    confidence_breakdown = {}
    for c in idx.claims.values():
        confidence_breakdown[c["confidenceState"]] = confidence_breakdown.get(c["confidenceState"], 0) + 1
    summary = {
        "sourceCount": len(idx.sources), "evidenceItemCount": len(idx.items),
        "claimCount": len(idx.claims), "linkCount": len(idx.links),
        "contradictionCount": len(idx.contradictions), "lifecycleEventCount": len(idx.lifecycle_events),
        "confidenceStateBreakdown": confidence_breakdown,
    }
    return _result("evidence_system_summary", {}, "ok", [summary])


QUERIES = {
    "get_source_by_id": get_source_by_id,
    "list_evidence_by_source": list_evidence_by_source,
    "get_evidence_by_id": get_evidence_by_id,
    "get_claim_by_id": get_claim_by_id,
    "list_evidence_supporting_claim": list_evidence_supporting_claim,
    "list_evidence_contradicting_claim": list_evidence_contradicting_claim,
    "list_unresolved_claims": list_unresolved_claims,
    "list_contested_claims": list_contested_claims,
    "list_claims_by_trader": list_claims_by_trader,
    "list_claims_by_strategy_family": list_claims_by_strategy_family,
    "list_claims_by_type": list_claims_by_type,
    "list_claims_by_timeframe": list_claims_by_timeframe,
    "list_claims_by_session": list_claims_by_session,
    "list_claims_by_market_condition": list_claims_by_market_condition,
    "list_claims_with_insufficient_evidence": list_claims_with_insufficient_evidence,
    "list_contradiction_records": list_contradiction_records,
    "get_confidence_explanation": get_confidence_explanation,
    "trace_evidence_provenance": trace_evidence_provenance,
    "trace_claim_to_source_provenance": trace_claim_to_source_provenance,
    "detect_orphaned_records": detect_orphaned_records,
    "detect_duplicate_candidates": detect_duplicate_candidates,
    "evidence_system_summary": evidence_system_summary,
}


def main():
    parser = argparse.ArgumentParser(description="Run a read-only PROGRAM-006 evidence query.")
    parser.add_argument("query", choices=sorted(QUERIES.keys()))
    parser.add_argument("args", nargs="*")
    parser.add_argument("--evidence-root", default=os.path.join(REPO_ROOT, "docs", "trader-intelligence", "evidence"))
    args = parser.parse_args()

    idx = EvidenceIndex.load(args.evidence_root)
    result = QUERIES[args.query](idx, *args.args)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

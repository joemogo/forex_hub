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
import evidence_explain as explain # noqa: E402
import tjr_report                  # noqa: E402

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
    def __init__(self, sources, items, claims, links, contradictions, lifecycle_events,
                 intakes=None, segments=None, annotations=None, questions=None,
                 proposals=None, queue_entries=None):
        self.sources = sources
        self.items = items
        self.claims = claims
        self.links = links
        self.contradictions = contradictions
        self.lifecycle_events = lifecycle_events
        # PROGRAM-006 Phase 1B (ADR-009) additions -- default to {} so any
        # code written against a Phase 1A-shaped EvidenceIndex keeps working.
        self.intakes = intakes or {}
        self.segments = segments or {}
        self.annotations = annotations or {}
        self.questions = questions or {}
        self.proposals = proposals or {}
        self.queue_entries = queue_entries or {}

    @classmethod
    def load(cls, evidence_root):
        sources = _load_dir(os.path.join(evidence_root, "sources"), "sourceId")
        items = _load_dir(os.path.join(evidence_root, "items"), "evidenceId")
        claims = _load_dir(os.path.join(evidence_root, "claims"), "claimId")
        links = _load_dir(os.path.join(evidence_root, "links"), "linkId")
        contradictions = _load_dir(os.path.join(evidence_root, "contradictions"), "contradictionId")
        lifecycle_events = _load_dir(os.path.join(evidence_root, "lifecycle"), "eventId")
        intakes = _load_dir(os.path.join(evidence_root, "intake"), "intakeId")
        segments = _load_dir(os.path.join(evidence_root, "segments"), "segmentId")
        annotations = _load_dir(os.path.join(evidence_root, "annotations"), "annotationId")
        questions = _load_dir(os.path.join(evidence_root, "questions"), "questionId")
        proposals = _load_dir(os.path.join(evidence_root, "proposals"), "proposalId")
        queue_entries = _load_dir(os.path.join(evidence_root, "review-queue"), "queueEntryId")
        return cls(sources, items, claims, links, contradictions, lifecycle_events,
                   intakes, segments, annotations, questions, proposals, queue_entries)

    def links_for_claim(self, claim_id):
        return [l for l in self.links.values() if l["claimId"] == claim_id]

    def links_for_evidence(self, evidence_id):
        return [l for l in self.links.values() if l["evidenceId"] == evidence_id]

    def segments_for_intake(self, intake_id):
        return sorted([s for s in self.segments.values() if s["intakeId"] == intake_id],
                      key=lambda s: s["sequenceNumber"])

    def items_for_source(self, source_id):
        return [i for i in self.items.values() if i["sourceId"] == source_id]

    def claims_for_source(self, source_id):
        item_ids = {i["evidenceId"] for i in self.items_for_source(source_id)}
        claim_ids = {l["claimId"] for l in self.links.values() if l["evidenceId"] in item_ids}
        return [self.claims[cid] for cid in claim_ids if cid in self.claims]


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


# ---------------------------------------------------------------------------
# PROGRAM-006 Phase 1B (ADR-009, Deliverable 16) -- explainability queries
# ---------------------------------------------------------------------------

# 23
def explain_claim_by_id(idx, claim_id):
    explanation = explain.explain_claim(idx, claim_id)
    return _result("explain_claim_by_id", {"claimId": claim_id}, "ok" if explanation else "not_found",
                    [explanation] if explanation else [])


# 24
def explain_claim_confidence(idx, claim_id):
    if claim_id not in idx.claims:
        return _result("explain_claim_confidence", {"claimId": claim_id}, "not_found", [])
    explanation = explain.explain_claim(idx, claim_id)
    result = {"claimId": claim_id, "confidenceState": explanation["confidenceState"],
              "confidenceScore": explanation["confidenceScore"],
              "confidenceFactorBreakdown": explanation["confidenceFactorBreakdown"]}
    return _result("explain_claim_confidence", {"claimId": claim_id}, "ok", [result])


# 25
def list_source_evidence_for_claim(idx, claim_id):
    if claim_id not in idx.claims:
        return _result("list_source_evidence_for_claim", {"claimId": claim_id}, "not_found", [])
    links = idx.links_for_claim(claim_id)
    source_ids = sorted({idx.items[l["evidenceId"]]["sourceId"] for l in links if l["evidenceId"] in idx.items})
    results = [idx.sources[sid] for sid in source_ids if sid in idx.sources]
    return _result("list_source_evidence_for_claim", {"claimId": claim_id}, "ok" if results else "empty", results)


# 26
def list_claims_from_source(idx, source_id):
    if source_id not in idx.sources:
        return _result("list_claims_from_source", {"sourceId": source_id}, "not_found", [])
    results = sorted(idx.claims_for_source(source_id), key=lambda c: c["claimId"])
    return _result("list_claims_from_source", {"sourceId": source_id}, "ok" if results else "empty", results)


def _claims_where_any_link_item_directness(idx, directness_values):
    matches = []
    for claim in idx.claims.values():
        links = idx.links_for_claim(claim["claimId"])
        if any(idx.items.get(l["evidenceId"], {}).get("directness") in directness_values for l in links):
            matches.append(claim)
    matches.sort(key=lambda c: c["claimId"])
    return matches


# 27
def list_inferred_claims(idx):
    results = _claims_where_any_link_item_directness(idx, ("inferred_from_context", "derived_from_analysis"))
    return _result("list_inferred_claims", {}, "ok" if results else "empty", results)


# 28
def list_explicit_claims(idx):
    results = _claims_where_any_link_item_directness(idx, ("direct_explicit", "direct_demonstrated"))
    return _result("list_explicit_claims", {}, "ok" if results else "empty", results)


# 29
def list_claims_awaiting_review(idx):
    results = sorted([c for c in idx.claims.values() if c["claimStatus"] == "pending_review"], key=lambda c: c["claimId"])
    return _result("list_claims_awaiting_review", {}, "ok" if results else "empty", results)


# 30
def list_claims_with_low_extraction_certainty(idx):
    matches = []
    for claim in idx.claims.values():
        links = idx.links_for_claim(claim["claimId"])
        if any(idx.items.get(l["evidenceId"], {}).get("extractionCertainty") in ("low", "ambiguous", "unresolved") for l in links):
            matches.append(claim)
    matches.sort(key=lambda c: c["claimId"])
    return _result("list_claims_with_low_extraction_certainty", {}, "ok" if matches else "empty", matches)


# 31
def list_claims_with_contradictory_demonstrated_behavior(idx):
    matches = []
    for claim in idx.claims.values():
        links = idx.links_for_claim(claim["claimId"])
        has_explicit_support = any(idx.items.get(l["evidenceId"], {}).get("directness") == "direct_explicit"
                                    and l["relationshipType"] in ("supports", "exemplifies") for l in links)
        has_demonstrated_contradiction = any(idx.items.get(l["evidenceId"], {}).get("directness") == "direct_demonstrated"
                                              and l["relationshipType"] == "contradicts" for l in links)
        if has_explicit_support and has_demonstrated_contradiction:
            matches.append(claim)
    matches.sort(key=lambda c: c["claimId"])
    return _result("list_claims_with_contradictory_demonstrated_behavior", {}, "ok" if matches else "empty", matches)


# 32
def list_unresolved_questions_by_source(idx, source_id):
    if source_id not in idx.sources:
        return _result("list_unresolved_questions_by_source", {"sourceId": source_id}, "not_found", [])
    claim_ids = {c["claimId"] for c in idx.claims_for_source(source_id)}
    matches = sorted([q for q in idx.questions.values()
                       if q.get("claimId") in claim_ids and q["researchStatus"] in ("open", "researching")],
                      key=lambda q: q["questionId"])
    return _result("list_unresolved_questions_by_source", {"sourceId": source_id}, "ok" if matches else "empty", matches)


# 33
def list_unresolved_questions_by_strategy_family(idx, strategy_family_id):
    claim_ids = {c["claimId"] for c in idx.claims.values() if c.get("strategyFamilyId") == strategy_family_id}
    matches = sorted([q for q in idx.questions.values()
                       if q.get("claimId") in claim_ids and q["researchStatus"] in ("open", "researching")],
                      key=lambda q: q["questionId"])
    return _result("list_unresolved_questions_by_strategy_family", {"strategyFamilyId": strategy_family_id},
                    "ok" if matches else "empty", matches)


# 34
def list_rule_candidates_by_source(idx, source_id):
    if source_id not in idx.sources:
        return _result("list_rule_candidates_by_source", {"sourceId": source_id}, "not_found", [])
    claim_ids = {c["claimId"] for c in idx.claims_for_source(source_id)}
    matches = sorted([p for p in idx.proposals.values() if claim_ids & set(p.get("originatingClaimIds", []))],
                      key=lambda p: p["proposalId"])
    return _result("list_rule_candidates_by_source", {"sourceId": source_id}, "ok" if matches else "empty", matches)


# 35
def list_rule_candidates_blocked_by_contradictions(idx):
    matches = sorted([p for p in idx.proposals.values() if p["contradictionStatus"] == "open_contradiction"],
                      key=lambda p: p["proposalId"])
    return _result("list_rule_candidates_blocked_by_contradictions", {}, "ok" if matches else "empty", matches)


# 36
def list_evidence_by_segment(idx, segment_id):
    if segment_id not in idx.segments:
        return _result("list_evidence_by_segment", {"segmentId": segment_id}, "not_found", [])
    matches = sorted([i for i in idx.items.values() if i.get("sourceLocator") == segment_id], key=lambda i: i["evidenceId"])
    return _result("list_evidence_by_segment", {"segmentId": segment_id}, "ok" if matches else "empty", matches)


# 37
def trace_segment_to_evidence(idx, segment_id):
    return list_evidence_by_segment(idx, segment_id)


# 38
def trace_segment_to_claim(idx, segment_id):
    if segment_id not in idx.segments:
        return _result("trace_segment_to_claim", {"segmentId": segment_id}, "not_found", [])
    item_ids = {i["evidenceId"] for i in idx.items.values() if i.get("sourceLocator") == segment_id}
    claim_ids = sorted({l["claimId"] for l in idx.links.values() if l["evidenceId"] in item_ids})
    results = [idx.claims[cid] for cid in claim_ids if cid in idx.claims]
    return _result("trace_segment_to_claim", {"segmentId": segment_id}, "ok" if results else "empty", results)


# 39
def trace_claim_to_rule_candidate(idx, claim_id):
    if claim_id not in idx.claims:
        return _result("trace_claim_to_rule_candidate", {"claimId": claim_id}, "not_found", [])
    results = sorted([p for p in idx.proposals.values() if claim_id in p.get("originatingClaimIds", [])],
                      key=lambda p: p["proposalId"])
    return _result("trace_claim_to_rule_candidate", {"claimId": claim_id}, "ok" if results else "empty", results)


# 40
def list_tjr_sources_by_intake_status(idx, intake_status):
    if intake_status not in evc.INTAKE_STATUSES:
        return _result("list_tjr_sources_by_intake_status", {"intakeStatus": intake_status}, "invalid_input", [],
                        ["%r is not a recognized intakeStatus" % intake_status])
    matches = sorted([m for m in idx.intakes.values() if m["intakeStatus"] == intake_status], key=lambda m: m["intakeId"])
    return _result("list_tjr_sources_by_intake_status", {"intakeStatus": intake_status}, "ok" if matches else "empty", matches)


# 41
def generate_tjr_source_intake_summary(idx, intake_id):
    intake = idx.intakes.get(intake_id)
    if intake is None:
        return _result("generate_tjr_source_intake_summary", {"intakeId": intake_id}, "not_found", [])
    segments = idx.segments_for_intake(intake_id)
    annotations = [a for a in idx.annotations.values() if a["intakeId"] == intake_id]
    summary = {
        "intakeId": intake_id, "intakeStatus": intake["intakeStatus"], "extractionStatus": intake["extractionStatus"],
        "reviewStatus": intake["reviewStatus"], "segmentCount": len(segments), "annotationCount": len(annotations),
        "sourceId": intake.get("sourceId"), "licensingStatus": intake.get("licensingStatus"),
        "transcriptCompleteness": intake.get("transcriptCompleteness"), "warnings": intake.get("warnings", []),
    }
    return _result("generate_tjr_source_intake_summary", {"intakeId": intake_id}, "ok", [summary])


# 42
def generate_complete_tjr_research_report(idx, intake_id):
    report = tjr_report.generate_tjr_research_report(idx, intake_id)
    return _result("generate_complete_tjr_research_report", {"intakeId": intake_id},
                    "ok" if report else "not_found", [report] if report else [])


# 43
def list_next_recommended_research_items(idx):
    """Deterministic recommendation list: intakes not yet approved/rejected,
    ordered by intakeId, each carrying its own recommendedNextSource note."""
    results = []
    for intake_id in sorted(idx.intakes.keys()):
        intake = idx.intakes[intake_id]
        if intake["intakeStatus"] in ("approved", "rejected", "duplicate", "superseded"):
            continue
        report = tjr_report.generate_tjr_research_report(idx, intake_id)
        results.append({"intakeId": intake_id, "intakeStatus": intake["intakeStatus"],
                         "recommendation": report["recommendedNextSource"] if report else None})
    if not results:
        results = [{"intakeId": None, "intakeStatus": None,
                     "recommendation": "No TJR intake exists yet -- see docs/EVIDENCE_INTELLIGENCE.md 'First Real TJR Intake' guide."}]
    return _result("list_next_recommended_research_items", {}, "ok", results)


# 44
def system_wide_explainability_summary(idx):
    directness_breakdown = {}
    certainty_breakdown = {}
    for item in idx.items.values():
        d = item.get("directness") or "unresolved"
        c = item.get("extractionCertainty") or "unresolved"
        directness_breakdown[d] = directness_breakdown.get(d, 0) + 1
        certainty_breakdown[c] = certainty_breakdown.get(c, 0) + 1
    summary = {
        "intakeCount": len(idx.intakes), "segmentCount": len(idx.segments), "annotationCount": len(idx.annotations),
        "questionCount": len(idx.questions), "openQuestionCount": len([q for q in idx.questions.values() if q["researchStatus"] == "open"]),
        "proposalCount": len(idx.proposals), "reviewQueueEntryCount": len(idx.queue_entries),
        "directnessBreakdown": directness_breakdown, "extractionCertaintyBreakdown": certainty_breakdown,
        "claimsAwaitingReview": len([c for c in idx.claims.values() if c["claimStatus"] == "pending_review"]),
    }
    return _result("system_wide_explainability_summary", {}, "ok", [summary])


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
    "explain_claim_by_id": explain_claim_by_id,
    "explain_claim_confidence": explain_claim_confidence,
    "list_source_evidence_for_claim": list_source_evidence_for_claim,
    "list_claims_from_source": list_claims_from_source,
    "list_inferred_claims": list_inferred_claims,
    "list_explicit_claims": list_explicit_claims,
    "list_claims_awaiting_review": list_claims_awaiting_review,
    "list_claims_with_low_extraction_certainty": list_claims_with_low_extraction_certainty,
    "list_claims_with_contradictory_demonstrated_behavior": list_claims_with_contradictory_demonstrated_behavior,
    "list_unresolved_questions_by_source": list_unresolved_questions_by_source,
    "list_unresolved_questions_by_strategy_family": list_unresolved_questions_by_strategy_family,
    "list_rule_candidates_by_source": list_rule_candidates_by_source,
    "list_rule_candidates_blocked_by_contradictions": list_rule_candidates_blocked_by_contradictions,
    "list_evidence_by_segment": list_evidence_by_segment,
    "trace_segment_to_evidence": trace_segment_to_evidence,
    "trace_segment_to_claim": trace_segment_to_claim,
    "trace_claim_to_rule_candidate": trace_claim_to_rule_candidate,
    "list_tjr_sources_by_intake_status": list_tjr_sources_by_intake_status,
    "generate_tjr_source_intake_summary": generate_tjr_source_intake_summary,
    "generate_complete_tjr_research_report": generate_complete_tjr_research_report,
    "list_next_recommended_research_items": list_next_recommended_research_items,
    "system_wide_explainability_summary": system_wide_explainability_summary,
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

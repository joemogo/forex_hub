#!/usr/bin/env python3
"""PROGRAM-006 Phase 1B (ADR-009, Deliverables 2-3) -- deterministic claim
explainability and traceability service.

Pure Python standard library. NO NETWORK ACCESS. NO LLM. Every field in the
returned explanation is read directly from a stored record; nothing here
composes free-form narrative that isn't a template fill of stored values
(ADR-009 sec. 5/7). Given the identical stored state, explain_claim always
returns a byte-identical result.
"""
import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import evidence_common as evc          # noqa: E402
import evidence_confidence as conf     # noqa: E402

_DIRECT_DIRECTNESS = ("direct_explicit", "direct_demonstrated")


def _evidence_line(item, link):
    return {
        "evidenceId": item["evidenceId"], "sourceId": item["sourceId"],
        "evidenceType": item["evidenceType"], "directness": item.get("directness"),
        "extractionCertainty": item.get("extractionCertainty"), "evidenceQuality": item.get("evidenceQuality"),
        "relationshipType": link["relationshipType"], "exactExcerpt": item.get("exactExcerpt"),
        "startTimestamp": item.get("startTimestamp"), "endTimestamp": item.get("endTimestamp"),
        "sourceLocator": item.get("sourceLocator"), "independenceGroup": link.get("independenceGroup"),
    }


def _source_provenance_line(source):
    return {
        "sourceId": source["sourceId"], "sourceType": source["sourceType"], "title": source.get("title"),
        "traderId": source.get("traderId"), "storageLocationType": source.get("storageLocationType"),
        "provenanceStatus": source.get("provenanceStatus"), "canonicalReference": source.get("canonicalReference"),
        "licensingStatus": source.get("licensingStatus"),
    }


def explain_claim(idx, claimId, now=None):
    """idx: a query_evidence.EvidenceIndex (or any object exposing the same
    .claims/.items/.sources/.contradictions/.links_for_claim attributes, plus
    optional .questions/.proposals dicts). Returns None if claimId is not
    found -- callers distinguish not_found the same way query_evidence does."""
    claim = idx.claims.get(claimId)
    if claim is None:
        return None
    now = now or datetime.now(timezone.utc)

    links = idx.links_for_claim(claimId)
    direct_support, indirect_support, contradicting, weakening, contextual, unresolved_rel = [], [], [], [], [], []
    for link in sorted(links, key=lambda l: l["evidenceId"]):
        item = idx.items.get(link["evidenceId"])
        if not item:
            continue
        line = _evidence_line(item, link)
        rel = link["relationshipType"]
        if rel in ("supports", "exemplifies"):
            (direct_support if item.get("directness") in _DIRECT_DIRECTNESS else indirect_support).append(line)
        elif rel == "contradicts":
            contradicting.append(line)
        elif rel == "weakens":
            weakening.append(line)
        elif rel in ("contextualizes", "qualifies", "supersedes"):
            contextual.append(line)
        elif rel == "unresolved":
            unresolved_rel.append(line)

    items_by_id = idx.items
    _, score, counts, explanation_text = conf.compute_confidence(
        [dict(l) for l in links], items_by_id)

    source_ids = sorted({items_by_id[l["evidenceId"]]["sourceId"] for l in links if l["evidenceId"] in items_by_id})
    independence_groups = {}
    for link in links:
        item = items_by_id.get(link["evidenceId"])
        if item:
            key = link.get("independenceGroup") or item["sourceId"]
            independence_groups.setdefault(key, []).append(item["evidenceId"])
    source_independence_analysis = {
        "independentGroupCount": len(independence_groups),
        "groups": {k: sorted(v) for k, v in sorted(independence_groups.items())},
    }

    contradiction_records = sorted(
        [cr for cr in idx.contradictions.values() if cr["claimAId"] == claimId or cr["claimBId"] == claimId],
        key=lambda c: c["contradictionId"])

    questions = sorted(
        [q for q in getattr(idx, "questions", {}).values() if q.get("claimId") == claimId],
        key=lambda q: q["questionId"])

    proposals = sorted(
        [p for p in getattr(idx, "proposals", {}).values() if claimId in p.get("originatingClaimIds", [])],
        key=lambda p: p["proposalId"])

    known_scope_limitations = []
    for field, label in (("timeframe", "timeframe"), ("session", "session"), ("marketCondition", "market condition")):
        if not claim.get(field):
            known_scope_limitations.append("No %s recorded for this claim." % label)
    symbols = sorted({items_by_id[l["evidenceId"]].get("marketSymbol") for l in links
                      if l["evidenceId"] in items_by_id and items_by_id[l["evidenceId"]].get("marketSymbol")})
    if symbols:
        known_scope_limitations.append("Only demonstrated on %s." % ", ".join(symbols))

    linked_evidence_types = {items_by_id[l["evidenceId"]]["evidenceType"] for l in links if l["evidenceId"] in items_by_id}
    missing_evidence_categories = []
    if not (direct_support or indirect_support):
        missing_evidence_categories.append("no_supporting_evidence")
    if "replay_result" not in linked_evidence_types:
        missing_evidence_categories.append("replay_result")
    if "paper_trade_result" not in linked_evidence_types:
        missing_evidence_categories.append("paper_trade_result")

    replay_status = "validated" if "replay_result" in linked_evidence_types else "not_available"
    paper_status = "validated" if "paper_trade_result" in linked_evidence_types else "not_available"
    owner_review_status = proposals[0]["ownerReviewStatus"] if proposals else None

    explanation = {
        "claimId": claimId, "normalizedClaim": claim["normalizedClaim"], "claimType": claim["claimType"],
        "subjectEntityType": claim.get("subjectEntityType"), "subjectEntityId": claim.get("subjectEntityId"),
        "traderId": claim.get("traderId"), "strategyFamilyId": claim.get("strategyFamilyId"),
        "timeframe": claim.get("timeframe"), "session": claim.get("session"),
        "marketCondition": claim.get("marketCondition"), "claimStatus": claim["claimStatus"],
        "confidenceState": claim["confidenceState"], "confidenceScore": claim["confidenceScore"],
        "confidenceFactorBreakdown": {"explanation": explanation_text, **counts},
        "evidenceCounts": {"total": len(links), "supporting": len(direct_support) + len(indirect_support),
                           "contradicting": len(contradicting), "weakening": len(weakening),
                           "contextual": len(contextual) + len(unresolved_rel)},
        "sourceCounts": {"distinctSources": len(source_ids)},
        "sourceIndependenceAnalysis": source_independence_analysis,
        "directSupportingEvidence": direct_support, "indirectSupportingEvidence": indirect_support,
        "contradictingEvidence": contradicting, "weakeningEvidence": weakening,
        "contextualEvidence": contextual, "unresolvedRelationshipEvidence": unresolved_rel,
        "contradictionRecords": contradiction_records, "supersessionStatus": None,
        "unresolvedQuestions": questions, "knownScopeLimitations": known_scope_limitations,
        "missingEvidenceCategories": missing_evidence_categories,
        "candidateRuleReferences": proposals, "replayValidationStatus": replay_status,
        "paperTradingValidationStatus": paper_status, "ownerReviewStatus": owner_review_status,
        "sourceProvenance": [_source_provenance_line(idx.sources[sid]) for sid in source_ids if sid in idx.sources],
        "generatedAt": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "explanationSchemaVersion": evc.EXPLANATION_SCHEMA_VERSION,
    }
    return explanation


def render_explanation_text(explanation):
    """Human-readable rendering. Every line is a template fill of a field
    already present in `explanation` -- no new facts are introduced here."""
    lines = []
    lines.append("Claim:")
    lines.append(explanation["normalizedClaim"])
    lines.append("")
    lines.append("Current assessment:")
    score_str = ("%.2f" % explanation["confidenceScore"]) if explanation["confidenceScore"] is not None else "n/a"
    lines.append("%s, confidence %s." % (explanation["confidenceState"], score_str))
    lines.append("")
    lines.append("Why:")
    lines.append(explanation["confidenceFactorBreakdown"].get("explanation", ""))
    lines.append("")

    if explanation["directSupportingEvidence"] or explanation["indirectSupportingEvidence"]:
        lines.append("Supporting evidence:")
        for e in explanation["directSupportingEvidence"] + explanation["indirectSupportingEvidence"]:
            loc = e.get("startTimestamp") or e.get("sourceLocator") or ""
            tag = "" if e["directness"] in _DIRECT_DIRECTNESS else " (inferred)"
            lines.append("- %s, %s, %s%s" % (e["sourceId"], loc, e["evidenceType"], tag))
        lines.append("")

    if explanation["contradictingEvidence"] or explanation["weakeningEvidence"]:
        lines.append("Contradicting or qualifying evidence:")
        for e in explanation["contradictingEvidence"] + explanation["weakeningEvidence"]:
            loc = e.get("startTimestamp") or e.get("sourceLocator") or ""
            lines.append("- %s, %s, %s" % (e["sourceId"], loc, e["evidenceType"]))
        lines.append("")

    if explanation["knownScopeLimitations"] or explanation["missingEvidenceCategories"]:
        lines.append("Scope limitations:")
        for s in explanation["knownScopeLimitations"]:
            lines.append("- %s" % s)
        if "replay_result" in explanation["missingEvidenceCategories"]:
            lines.append("- No replay validation.")
        if "paper_trade_result" in explanation["missingEvidenceCategories"]:
            lines.append("- No paper-trading validation.")
        lines.append("")

    if explanation["unresolvedQuestions"]:
        lines.append("Outstanding questions:")
        for q in explanation["unresolvedQuestions"]:
            lines.append("- %s" % q["questionText"])
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def trace_explanation_component(explanation, component):
    """Answers 'which evidence/algorithm produced this part of the
    explanation' (Deliverable 3) for a named top-level component, returning
    the record IDs it was derived from."""
    if component not in explanation:
        raise KeyError("Unknown explanation component %r" % (component,))
    value = explanation[component]
    if isinstance(value, list):
        ids = []
        for item in value:
            if isinstance(item, dict):
                ids.append(item.get("evidenceId") or item.get("contradictionId") or item.get("questionId") or item.get("proposalId"))
        return {"component": component, "derivedFromIds": [i for i in ids if i],
                "algorithmVersion": "evidence_confidence_v1" if component in
                ("confidenceState", "confidenceScore", "confidenceFactorBreakdown") else "evidence_explain_v1"}
    return {"component": component, "derivedFromIds": [], "algorithmVersion": "evidence_explain_v1"}

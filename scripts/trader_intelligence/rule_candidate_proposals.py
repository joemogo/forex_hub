#!/usr/bin/env python3
"""PROGRAM-006 Phase 1B (ADR-009 sec. 8, Deliverable 12) -- rule-candidate
proposal generation.

Pure Python standard library. NO NETWORK ACCESS. A RuleCandidateProposal is
never executable: it never marks a StrategyRule active, validated, or
promoted, never creates a paper trade, and never alters any runtime
behavior. It is a rationale document a human reviews separately.
"""
import glob as globmod
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import graph_common as gc      # noqa: E402
import evidence_common as evc  # noqa: E402

_CONFIDENCE_ORDER = [
    "contradicted", "insufficient_evidence", "contested", "weakened", "unresolved",
    "tentative", "emerging", "supported", "strongly_supported",
]


def _load_all(dir_path, id_field):
    out = {}
    if not os.path.isdir(dir_path):
        return out
    for path in sorted(globmod.glob(os.path.join(dir_path, "*.json"))):
        with open(path, "r", encoding="utf-8") as f:
            record = json.load(f)
        out[record[id_field]] = record
    return out


def _weakest_confidence_state(states):
    ranked = sorted(states, key=lambda s: _CONFIDENCE_ORDER.index(s) if s in _CONFIDENCE_ORDER else -1)
    return ranked[0]


def propose_rule_candidate(proposals_dir, claims_dir, links_dir, items_dir, contradictions_dir,
                            questions_dir, now, claimIds, actor, proposalRationale,
                            symbols=None, supersedesProposalId=None):
    if not claimIds:
        raise evc.EvidenceValidationError("propose_rule_candidate requires at least one claimId")
    claims = _load_all(claims_dir, "claimId")
    missing = [cid for cid in claimIds if cid not in claims]
    if missing:
        raise evc.EvidenceValidationError("propose_rule_candidate references nonexistent claimIds %r" % (missing,))

    selected = [claims[cid] for cid in claimIds]
    claim_types = {c["claimType"] for c in selected}
    if len(claim_types) > 1:
        raise evc.EvidenceValidationError(
            "All claims in one proposal must share the same claimType, got %r" % (sorted(claim_types),))
    claim_type = next(iter(claim_types))
    if claim_type not in evc.RULE_CANDIDATE_ELIGIBLE_CLAIM_TYPES:
        raise evc.EvidenceValidationError(
            "claimType %r is not eligible for rule-candidate proposal (eligible: %r)" % (
                claim_type, evc.RULE_CANDIDATE_ELIGIBLE_CLAIM_TYPES))

    scope_tuples = {(c.get("traderId"), c.get("strategyFamilyId"), c.get("timeframe")) for c in selected}
    if len(scope_tuples) > 1:
        raise evc.EvidenceValidationError(
            "All claims in one proposal must share (traderId, strategyFamilyId, timeframe); got %r" % (sorted(scope_tuples),))
    primary = selected[0]

    all_links = _load_all(links_dir, "linkId")
    items = _load_all(items_dir, "evidenceId")
    relevant_links = [l for l in all_links.values() if l["claimId"] in claimIds]
    evidence_ids = sorted({l["evidenceId"] for l in relevant_links})
    supporting_source_ids = sorted({items[eid]["sourceId"] for eid in evidence_ids
                                     if eid in items and any(l["evidenceId"] == eid and l["relationshipType"] in ("supports", "exemplifies")
                                                              for l in relevant_links)})
    contradicting_evidence_ids = sorted({l["evidenceId"] for l in relevant_links if l["relationshipType"] == "contradicts"})

    directness_distribution = {}
    certainty_distribution = {}
    for eid in evidence_ids:
        item = items.get(eid)
        if not item:
            continue
        d = item.get("directness") or "unresolved"
        c = item.get("extractionCertainty") or "unresolved"
        directness_distribution[d] = directness_distribution.get(d, 0) + 1
        certainty_distribution[c] = certainty_distribution.get(c, 0) + 1

    contradictions = _load_all(contradictions_dir, "contradictionId")
    touching = [cr for cr in contradictions.values() if cr["claimAId"] in claimIds or cr["claimBId"] in claimIds]
    if any(cr["status"] == "open" for cr in touching):
        contradiction_status = "open_contradiction"
    elif touching:
        contradiction_status = "resolved_contradiction"
    else:
        contradiction_status = "none"

    questions = _load_all(questions_dir, "questionId")
    unresolved_question_ids = sorted(q["questionId"] for q in questions.values() if q.get("claimId") in claimIds)

    confidence_state = _weakest_confidence_state([c["confidenceState"] for c in selected])

    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    proposalId = evc.next_proposal_id(proposals_dir, now)
    record = {
        "proposalId": proposalId, "originatingClaimIds": list(claimIds), "evidenceIds": evidence_ids,
        "supportingSourceIds": supporting_source_ids, "contradictingEvidenceIds": contradicting_evidence_ids,
        "claimType": claim_type, "confidenceState": confidence_state,
        "directnessDistribution": directness_distribution, "extractionCertaintyDistribution": certainty_distribution,
        "traderId": primary.get("traderId"), "strategyFamilyId": primary.get("strategyFamilyId"),
        "timeframe": primary.get("timeframe"), "session": primary.get("session"),
        "marketCondition": primary.get("marketCondition"), "symbols": symbols or [],
        "unresolvedQuestionIds": unresolved_question_ids, "contradictionStatus": contradiction_status,
        "replayStatus": "not_available", "paperTradingStatus": "not_available",
        "ownerReviewStatus": "not_reviewed", "proposalRationale": proposalRationale, "proposalVersion": 1,
        "status": "proposed", "supersedesProposalId": supersedesProposalId,
        "schemaVersion": evc.SCHEMA_VERSION, "createdAt": now_iso, "updatedAt": now_iso,
    }
    if supersedesProposalId:
        proposals = _load_all(proposals_dir, "proposalId")
        prior = proposals.get(supersedesProposalId)
        if prior is None:
            raise evc.EvidenceValidationError("supersedesProposalId %r does not exist" % (supersedesProposalId,))
        record["proposalVersion"] = prior["proposalVersion"] + 1
        prior["status"] = "superseded"
        prior["updatedAt"] = now_iso
        gc.atomic_write_text(os.path.join(proposals_dir, evc.proposal_id_to_filename(supersedesProposalId)), gc.pretty_json(prior))

    path = os.path.join(proposals_dir, evc.proposal_id_to_filename(proposalId))
    gc.atomic_write_text(path, gc.pretty_json(record))
    return record

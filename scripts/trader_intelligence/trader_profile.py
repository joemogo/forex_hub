#!/usr/bin/env python3
"""PROGRAM-007 Phase 7A (Knowledge Library vertical slice) -- deterministic
Trader Profile generation.

Pure Python standard library. NO NETWORK ACCESS. Builds a versioned summary
of everything the Evidence Intelligence Engine currently knows about one
trader, purely from approved claims/evidence already on disk. Never invents
a value: every concept list entry is a labeled statement carrying its own
evidenceIds, and its status (confirmed/inferred/conflicting) is derived
mechanically from the directness of the evidence backing it -- never
guessed. Absence stays absence (an empty list), not a fabricated default.
"""
import glob as globmod
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import graph_common as gc       # noqa: E402
import evidence_common as evc   # noqa: E402

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TI_ROOT = os.path.join(REPO_ROOT, "docs", "trader-intelligence")

_DIRECT_DIRECTNESS = ("direct_explicit", "direct_demonstrated")

_CLAIM_TYPE_TO_CONCEPT_FIELD = {
    "entry_rule": "entryConcepts", "setup_requirement": "primaryConcepts",
    "confirmation_rule": "confirmationConcepts", "invalidation_rule": "invalidationConcepts",
    "stop_rule": "stopLossConcepts", "target_rule": "targetConcepts",
    "trade_management_rule": "tradeManagementConcepts", "risk_rule": "riskConcepts",
    "definition": "primaryConcepts",
}


def _load_wave1_trader_record(trader_id):
    """Reads the existing Wave-1 TraderRecord (docs/trader-intelligence/
    traders/{id}/profile.json) if one exists -- read-only, never modified.
    Reused so a Phase 7A TraderProfile's canonicalName/markets/sessions stay
    consistent with the already-established repository identity instead of
    silently diverging into a second, conflicting canonical record."""
    path = os.path.join(TI_ROOT, "traders", trader_id.lower(), "profile.json")
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _links_for_claims(idx, claim_ids):
    return [l for l in idx.links.values() if l["claimId"] in claim_ids]


def _concept_status(idx, claim_ids):
    directness_values = set()
    has_contradiction = False
    for l in _links_for_claims(idx, claim_ids):
        item = idx.items.get(l["evidenceId"])
        if not item:
            continue
        if l["relationshipType"] == "contradicts":
            has_contradiction = True
        directness_values.add(item.get("directness"))
    if has_contradiction:
        return "conflicting"
    if directness_values & set(_DIRECT_DIRECTNESS):
        return "confirmed"
    return "inferred"


def _labeled_concept(idx, value, claim_ids):
    evidence_ids = sorted({l["evidenceId"] for l in _links_for_claims(idx, claim_ids)})
    return {"value": value, "status": _concept_status(idx, claim_ids), "evidenceIds": evidence_ids}


def _group_claims_by_field(claims, field):
    groups = {}
    for c in claims:
        v = c.get(field)
        if v:
            groups.setdefault(v, []).append(c["claimId"])
    return groups


def _labeled_concepts_by_field(idx, claims, field):
    groups = _group_claims_by_field(claims, field)
    return [_labeled_concept(idx, value, ids) for value, ids in sorted(groups.items())]


def _labeled_concepts_by_evidence_field(idx, claims, field):
    """Same idea, but the value lives on the linked EvidenceItem (e.g.
    marketSymbol) rather than on the Claim itself."""
    groups = {}
    for c in claims:
        for l in idx.links_for_claim(c["claimId"]):
            item = idx.items.get(l["evidenceId"])
            v = item.get(field) if item else None
            if v:
                groups.setdefault(v, []).append(c["claimId"])
    return [_labeled_concept(idx, value, sorted(set(ids))) for value, ids in sorted(groups.items())]


def build_trader_profile(idx, trader_id, actor="pipeline", now=None):
    """Deterministic given the same stored state. Returns None if the trader
    has zero claims (nothing to summarize) -- callers distinguish this the
    same way every other query in this system does (not_found/empty)."""
    now = now or datetime.now(timezone.utc)
    claims = idx.claims_for_trader(trader_id)

    wave1 = _load_wave1_trader_record(trader_id)
    canonical_name = (wave1 or {}).get("displayName") or trader_id
    aliases = list((wave1 or {}).get("aliases") or [])
    baseline_markets = list((wave1 or {}).get("markets") or [])
    baseline_sessions = list((wave1 or {}).get("sessions") or [])

    claim_ids_by_trader = {c["claimId"] for c in claims}
    source_ids = set()
    evidence_count = 0
    observation_count = 0
    for c in claims:
        for l in idx.links_for_claim(c["claimId"]):
            item = idx.items.get(l["evidenceId"])
            if not item:
                continue
            evidence_count += 1
            source_ids.add(item["sourceId"])
            if item.get("directness") in ("direct_demonstrated", "owner_observation"):
                observation_count += 1

    contradiction_count = len([cr for cr in idx.contradictions.values()
                                if cr["claimAId"] in claim_ids_by_trader or cr["claimBId"] in claim_ids_by_trader])
    unresolved_question_count = len([q for q in idx.questions.values()
                                      if q.get("claimId") in claim_ids_by_trader])
    hypothesis_count = len([h for h in idx.hypotheses.values()
                             if set(h.get("sourceClaimIds", [])) & claim_ids_by_trader])

    confidence_summary = {}
    for c in claims:
        confidence_summary[c["confidenceState"]] = confidence_summary.get(c["confidenceState"], 0) + 1

    markets_mentioned = [_labeled_concept(idx, m, []) for m in sorted(set(baseline_markets))]
    sessions_mentioned = [_labeled_concept(idx, s, []) for s in sorted(set(baseline_sessions))]
    for lc in markets_mentioned + sessions_mentioned:
        lc["status"] = "confirmed"  # already-established repository fact, not a claim-derived inference

    session_from_claims = _labeled_concepts_by_field(idx, claims, "session")
    for lc in session_from_claims:
        if lc["value"] not in {s["value"] for s in sessions_mentioned}:
            sessions_mentioned.append(lc)
    sessions_mentioned.sort(key=lambda x: x["value"])

    timeframes_mentioned = _labeled_concepts_by_field(idx, claims, "timeframe")
    instruments_mentioned = _labeled_concepts_by_evidence_field(idx, claims, "marketSymbol")
    strategy_types = _labeled_concepts_by_field(idx, claims, "strategyFamilyId")

    concept_fields = {v: [] for v in set(_CLAIM_TYPE_TO_CONCEPT_FIELD.values())}
    for claim_type, field_name in _CLAIM_TYPE_TO_CONCEPT_FIELD.items():
        matching = [c for c in claims if c["claimType"] == claim_type]
        for c in matching:
            concept_fields[field_name].append(_labeled_concept(idx, c["normalizedClaim"], [c["claimId"]]))

    market_conditions_preferred = []
    market_conditions_avoided = []
    for c in claims:
        mc = c.get("marketCondition")
        if not mc:
            continue
        lc = _labeled_concept(idx, mc, [c["claimId"]])
        if c["confidenceState"] == "contradicted" or c["claimType"] == "exception":
            market_conditions_avoided.append(lc)
        else:
            market_conditions_preferred.append(lc)

    limitations = []
    if not claims:
        limitations.append("No claims exist for this trader yet -- profile reflects zero evidence.")
    if unresolved_question_count > 0:
        limitations.append("%d unresolved question(s) remain open for this trader." % unresolved_question_count)
    if contradiction_count > 0:
        limitations.append("%d contradiction(s) remain unresolved for this trader." % contradiction_count)
    if any(c["claimStatus"] == "pending_review" for c in claims):
        limitations.append("One or more claims are still pending_review and have not been confirmed by a human.")

    profile = {
        "profileId": None,  # assigned by register_trader_profile()
        "traderId": trader_id,
        "canonicalName": canonical_name,
        "aliases": sorted(set(aliases)),
        "marketsMentioned": markets_mentioned,
        "instrumentsMentioned": instruments_mentioned,
        "sessionsMentioned": sessions_mentioned,
        "timeframesMentioned": timeframes_mentioned,
        "strategyTypes": strategy_types,
        "primaryConcepts": concept_fields.get("primaryConcepts", []),
        "entryConcepts": concept_fields.get("entryConcepts", []),
        "confirmationConcepts": concept_fields.get("confirmationConcepts", []),
        "invalidationConcepts": concept_fields.get("invalidationConcepts", []),
        "stopLossConcepts": concept_fields.get("stopLossConcepts", []),
        "targetConcepts": concept_fields.get("targetConcepts", []),
        "tradeManagementConcepts": concept_fields.get("tradeManagementConcepts", []),
        "riskConcepts": concept_fields.get("riskConcepts", []),
        "marketConditionsPreferred": market_conditions_preferred,
        "marketConditionsAvoided": market_conditions_avoided,
        "evidenceCount": evidence_count,
        "observationCount": observation_count,
        "claimCount": len(claims),
        "contradictionCount": contradiction_count,
        "unresolvedQuestionCount": unresolved_question_count,
        "hypothesisCount": hypothesis_count,
        "sourceCount": len(source_ids),
        "extractionStatus": "completed" if claims else "not_started",
        "reviewStatus": "pending" if any(c["claimStatus"] == "pending_review" for c in claims) else "not_required",
        "generatedAt": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sourceLineage": {"sourceIds": sorted(source_ids), "claimIds": sorted(claim_ids_by_trader)},
        "limitations": limitations,
        "confidenceSummary": confidence_summary,
        "schemaVersion": evc.SCHEMA_VERSION,
    }
    return profile


def register_trader_profile(profiles_dir, idx, trader_id, actor="pipeline", now=None):
    """Builds and persists a new, versioned TraderProfile snapshot. Never
    edits a prior snapshot in place -- each call creates a new profileId, so
    the full history of how MOGO's understanding of a trader evolved stays
    on disk (mirroring the immutability discipline already established for
    EvidenceItem)."""
    now = now or datetime.now(timezone.utc)
    profile = build_trader_profile(idx, trader_id, actor=actor, now=now)
    profile["profileId"] = evc.next_profile_id(profiles_dir, trader_id, now)
    path = os.path.join(profiles_dir, evc.profile_id_to_filename(profile["profileId"]))
    gc.atomic_write_text(path, gc.pretty_json(profile))
    return profile

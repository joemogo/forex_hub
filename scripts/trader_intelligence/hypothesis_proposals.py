#!/usr/bin/env python3
"""PROGRAM-007 Phase 7A (Knowledge Library vertical slice) -- deterministic
research hypothesis generation.

Pure Python standard library. NO NETWORK ACCESS. A Hypothesis is only ever
proposed when a real claim, contradiction, or knowledge gap already exists
to point at -- never invented from nothing. Every hypothesis always starts
PROPOSED_UNVALIDATED and never alters any Claim, EvidenceItem, or
StrategyRule.
"""
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import graph_common as gc       # noqa: E402
import evidence_common as evc   # noqa: E402

_NOT_YET_SETTLED_STATES = ("emerging", "contested", "weakened")

_CLAIM_TYPE_TEMPLATES = {
    "entry_rule": "{text} may be required before a valid entry.",
    "setup_requirement": "{text} may be required before a valid entry.",
    "confirmation_rule": "{text} may only be required on the execution timeframe.",
    "invalidation_rule": "{text} may serve as the primary invalidation condition.",
    "stop_rule": "{text} may be the preferred stop-placement approach, pending further evidence.",
    "target_rule": "{text} may be the preferred target-selection approach, pending further evidence.",
    "trade_management_rule": "{text} may apply only in certain trade-management contexts.",
    "risk_rule": "{text} may be the trader's default risk rule, pending further confirmation.",
}

_GAP_CATEGORY_TEMPLATES = {
    "session": "Session restrictions may materially affect this strategy's setup validity.",
    "volatility_handling": "Volatility conditions may materially affect this strategy's setup validity.",
    "news_handling": "High-impact news events may require this strategy's setup to be skipped or delayed.",
}


def _evidence_ids_for_claim(idx, claim_id):
    return sorted({l["evidenceId"] for l in idx.links_for_claim(claim_id)})


def _supporting_and_contradicting_evidence(idx, claim_id):
    supporting, contradicting = [], []
    for l in idx.links_for_claim(claim_id):
        if l["relationshipType"] in ("supports", "exemplifies"):
            supporting.append(l["evidenceId"])
        elif l["relationshipType"] == "contradicts":
            contradicting.append(l["evidenceId"])
    return sorted(set(supporting)), sorted(set(contradicting))


def _hypotheses_from_unsettled_claims(idx, claims):
    specs = []
    for c in claims:
        if c["confidenceState"] not in _NOT_YET_SETTLED_STATES:
            continue
        template = _CLAIM_TYPE_TEMPLATES.get(c["claimType"])
        if not template:
            continue
        supporting, contradicting = _supporting_and_contradicting_evidence(idx, c["claimId"])
        specs.append({
            "statement": template.format(text=c["normalizedClaim"].rstrip(".")),
            "sourceClaimIds": [c["claimId"]],
            "supportingEvidenceIds": supporting,
            "contradictingEvidenceIds": contradicting,
            "assumptions": ["The linked evidence accurately reflects the trader's actual practice."],
            "independentVariables": [c["claimType"]],
            "dependentVariables": ["setup validity"],
            "applicableMarketConditions": [c["marketCondition"]] if c.get("marketCondition") else [],
            "proposedReplayTest": "Replay historical price action with and without this condition and compare outcomes.",
            "proposedPaperTest": "Paper-trade both variants (with/without this condition) and compare results.",
            "confidence": c["confidenceState"],
            "limitations": ["Based on a single claim at confidenceState=%r -- not yet independently corroborated." % c["confidenceState"]],
        })
    return specs


def _hypotheses_from_contradictions(idx, claim_ids_by_trader):
    specs = []
    for cr in idx.contradictions.values():
        if cr["claimAId"] not in claim_ids_by_trader and cr["claimBId"] not in claim_ids_by_trader:
            continue
        claim_a = idx.claims.get(cr["claimAId"])
        claim_b = idx.claims.get(cr["claimBId"])
        if not claim_a or not claim_b:
            continue
        supporting_a, contradicting_a = _supporting_and_contradicting_evidence(idx, claim_a["claimId"])
        supporting_b, contradicting_b = _supporting_and_contradicting_evidence(idx, claim_b["claimId"])
        specs.append({
            "statement": "%s may be preferred rather than mandatory, given conflicting evidence from a "
                         "contradicting claim (%s)." % (claim_a["normalizedClaim"].rstrip("."), claim_b["claimId"]),
            "sourceClaimIds": sorted([claim_a["claimId"], claim_b["claimId"]]),
            "supportingEvidenceIds": sorted(set(supporting_a)),
            "contradictingEvidenceIds": sorted(set(supporting_b) | set(contradicting_a)),
            "assumptions": ["Exactly one of the two conflicting claims reflects the trader's primary rule."],
            "independentVariables": [claim_a["claimType"], claim_b["claimType"]],
            "dependentVariables": ["setup validity"],
            "applicableMarketConditions": [],
            "proposedReplayTest": "Replay historical price action under both interpretations and compare outcomes.",
            "proposedPaperTest": "Paper-trade both interpretations and compare results.",
            "confidence": "contested",
            "limitations": ["Derived from an unresolved ContradictionRecord (%s) -- requires owner review." % cr["contradictionId"]],
        })
    return specs


def _hypotheses_from_gaps(idx, gaps, claim_ids_by_trader, claims_by_type):
    specs = []
    for gap in gaps or []:
        template = _GAP_CATEGORY_TEMPLATES.get(gap["category"])
        if not template or gap["answerStatus"] != "unanswered":
            continue
        anchor_claims = claims_by_type.get("entry_rule", []) or claims_by_type.get("setup_requirement", [])
        if not anchor_claims:
            continue  # a hypothesis must always point at a real claim -- never proposed from nothing
        specs.append({
            "statement": template,
            "sourceClaimIds": sorted({c["claimId"] for c in anchor_claims}),
            "supportingEvidenceIds": [],
            "contradictingEvidenceIds": [],
            "assumptions": ["The knowledge gap (%s) reflects a real, not merely incidental, omission." % gap["gapId"]],
            "independentVariables": [gap["category"]],
            "dependentVariables": ["setup validity"],
            "applicableMarketConditions": [],
            "proposedReplayTest": "Replay historical price action segmented by %s and compare outcomes." % gap["category"],
            "proposedPaperTest": "Paper-trade across varying %s conditions and compare results." % gap["category"],
            "confidence": "insufficient_evidence",
            "limitations": ["Proposed from an unresolved knowledge gap (%s), not from direct evidence." % gap["gapId"]],
        })
    return specs


def generate_hypotheses(hypotheses_dir, idx, blueprint, gaps=None, actor="pipeline", now=None):
    """Generates and persists Hypothesis records for one trader's claim set.
    Only ever proposed from a real claim, contradiction, or gap -- never
    invented. Always starts PROPOSED_UNVALIDATED. Never mutates any Claim,
    EvidenceItem, ContradictionRecord, or StrategyRule."""
    now = now or datetime.now(timezone.utc)
    trader_id = blueprint["traderId"]
    claims = idx.claims_for_trader(trader_id)
    claims_by_type = {}
    for c in claims:
        claims_by_type.setdefault(c["claimType"], []).append(c)
    claim_ids_by_trader = {c["claimId"] for c in claims}

    specs = (_hypotheses_from_unsettled_claims(idx, claims) +
             _hypotheses_from_contradictions(idx, claim_ids_by_trader) +
             _hypotheses_from_gaps(idx, gaps, claim_ids_by_trader, claims_by_type))

    created = []
    seen_statements = set()
    for spec in specs:
        if spec["statement"] in seen_statements:
            continue  # avoid exact-duplicate hypotheses when multiple triggers agree
        seen_statements.add(spec["statement"])
        now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        hypothesis_id = evc.next_hypothesis_id(hypotheses_dir, now)
        record = {
            "hypothesisId": hypothesis_id, "statement": spec["statement"],
            "sourceClaimIds": spec["sourceClaimIds"], "supportingEvidenceIds": spec["supportingEvidenceIds"],
            "contradictingEvidenceIds": spec["contradictingEvidenceIds"], "assumptions": spec["assumptions"],
            "independentVariables": spec["independentVariables"], "dependentVariables": spec["dependentVariables"],
            "applicableMarketConditions": spec["applicableMarketConditions"],
            "proposedReplayTest": spec["proposedReplayTest"], "proposedPaperTest": spec["proposedPaperTest"],
            "status": "PROPOSED_UNVALIDATED", "confidence": spec["confidence"], "limitations": spec["limitations"],
            "schemaVersion": evc.SCHEMA_VERSION, "createdAt": now_iso, "updatedAt": now_iso,
        }
        path = os.path.join(hypotheses_dir, evc.hypothesis_id_to_filename(hypothesis_id))
        gc.atomic_write_text(path, gc.pretty_json(record))
        created.append(record)
    return created

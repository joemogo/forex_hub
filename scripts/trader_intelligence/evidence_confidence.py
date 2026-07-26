"""PROGRAM-006 Phase 1A -- deterministic, explainable claim-confidence engine
(ADR-008 sec. 7, Deliverable 5).

Pure Python standard library. NO NETWORK ACCESS. NO MACHINE LEARNING. NO LLM.

This is NOT a profitability score, NOT a production-readiness score, and NOT a
prediction that a claim is true. It is a deterministic, recomputable estimate
of how strongly the currently-stored evidence supports a claim, given only
the EvidenceClaimLink records attached to it. Confidence is always
recomputed from stored evidence -- never manually edited without a lifecycle
event recording the recomputation.

The formula deliberately avoids double-counting: multiple links whose
independenceGroup resolves to the same value (defaulting to the evidence
item's sourceId) are treated as one corroborating group, with only the
strongest item in that group counted at full weight -- additional items from
the same group count at a fixed, small discount, never as fully independent
confirmation.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import evidence_common as evc  # noqa: E402

# Evidence-quality weight: how strong this individual item is, taken alone.
QUALITY_WEIGHT = {"unknown": 0.25, "low": 0.4, "medium": 0.7, "high": 1.0}
DEFAULT_QUALITY_WEIGHT = 0.25

# Directness weight: explicit statement vs. inferred/opinion (Deliverable 5's
# "explicit statement versus inferred observation" factor).
DIRECTNESS_WEIGHT = {
    "explicit_statement": 1.0, "rule_statement": 1.0,
    "demonstrated_behavior": 0.85, "trade_example": 0.85, "chart_example": 0.8,
    "post_trade_observation": 0.9, "replay_result": 0.9, "paper_trade_result": 0.9,
    "success_observation": 0.8, "failure_observation": 0.8,
    "market_context": 0.7, "execution_observation": 0.7, "risk_observation": 0.7,
    "exception_statement": 0.6, "opinion": 0.4, "prediction": 0.35, "intuition": 0.3,
    "unresolved_question": 0.2, "other": 0.3,
}
DEFAULT_DIRECTNESS_WEIGHT = 0.5

SAME_GROUP_DISCOUNT = 0.25  # additional same-independence-group items count at this fraction

# Additive-then-clamp scoring constants (all in points, final score clamped [0,100]).
SUPPORT_GROUP_POINTS = 22.0       # per independent supporting group, up to a cap
SUPPORT_GROUP_CAP_GROUPS = 3      # independence groups beyond this stop adding full group points
SUPPORT_EXTRA_POINTS = 6.0        # per unit of "extra" weight beyond one-per-group
CONTRA_GROUP_POINTS = 28.0        # per independent contradicting group, up to a cap
CONTRA_GROUP_CAP_GROUPS = 2
CONTRA_EXTRA_POINTS = 6.0
WEAKEN_POINTS = 8.0

STRONGLY_SUPPORTED_SCORE = 75.0
STRONGLY_SUPPORTED_MIN_GROUPS = 2
SUPPORTED_SCORE = 45.0
EMERGING_SCORE = 20.0


def _item_weight(link, evidence_by_id):
    ev = evidence_by_id.get(link["evidenceId"], {})
    q = QUALITY_WEIGHT.get(ev.get("evidenceQuality"), DEFAULT_QUALITY_WEIGHT)
    d = DIRECTNESS_WEIGHT.get(ev.get("evidenceType"), DEFAULT_DIRECTNESS_WEIGHT)
    r = link.get("relevanceWeight", 1.0) if link.get("relevanceWeight") is not None else 1.0
    return round(q * d * r, 6)


def _independence_groups(links, evidence_by_id):
    """Returns {group_key: [weights...]} and annotates each link's
    independenceGroup in place (Deliverable 4's Link.independenceGroup,
    populated by the confidence engine per the schema description)."""
    groups = {}
    for link in links:
        ev = evidence_by_id.get(link["evidenceId"], {})
        key = link.get("independenceGroup") or ev.get("sourceId") or link["evidenceId"]
        link["independenceGroup"] = key
        groups.setdefault(key, []).append(_item_weight(link, evidence_by_id))
    return groups


def _group_score(groups):
    total = 0.0
    for weights in groups.values():
        weights = sorted(weights, reverse=True)
        total += weights[0] + sum(w * SAME_GROUP_DISCOUNT for w in weights[1:])
    return round(total, 6)


def compute_confidence(links, evidence_by_id):
    """links: list of EvidenceClaimLink dicts for one claim (mutated in place
    to set independenceGroup). evidence_by_id: {evidenceId: EvidenceItem dict}.

    Returns (confidenceState, confidence_score_or_None, counts_dict, explanation_str).
    confidenceScore is None only when there are zero links at all (nothing to
    score); when links exist but yield zero net support, the score is a real,
    known 0 -- not a missing value.
    """
    supporting = [l for l in links if l["relationshipType"] in ("supports", "exemplifies")]
    contradicting = [l for l in links if l["relationshipType"] == "contradicts"]
    weakening = [l for l in links if l["relationshipType"] == "weakens"]
    contextual = [l for l in links if l["relationshipType"] in ("contextualizes", "qualifies", "supersedes")]
    unresolved = [l for l in links if l["relationshipType"] == "unresolved"]

    counts = {
        "evidenceCount": len(links),
        "supportingEvidenceCount": len(supporting),
        "contradictingEvidenceCount": len(contradicting),
        "weakeningEvidenceCount": len(weakening),
        "contextualEvidenceCount": len(contextual) + len(unresolved),
    }

    if not links:
        return "insufficient_evidence", None, counts, "No evidence linked to this claim yet."

    if unresolved and not (supporting or contradicting or weakening):
        return "unresolved", 0.0, counts, "Only unresolved-relationship evidence exists; nothing yet supports, contradicts, or weakens this claim."

    support_groups = _independence_groups(supporting, evidence_by_id)
    contra_groups = _independence_groups(contradicting, evidence_by_id)
    for l in weakening + contextual + unresolved:
        ev = evidence_by_id.get(l["evidenceId"], {})
        l["independenceGroup"] = l.get("independenceGroup") or ev.get("sourceId") or l["evidenceId"]

    n_support_groups = len(support_groups)
    n_contra_groups = len(contra_groups)
    support_score = _group_score(support_groups)
    contra_score = _group_score(contra_groups)
    weaken_score = sum(_item_weight(l, evidence_by_id) for l in weakening)

    score = 0.0
    score += SUPPORT_GROUP_POINTS * min(n_support_groups, SUPPORT_GROUP_CAP_GROUPS)
    if support_score > n_support_groups:
        score += SUPPORT_EXTRA_POINTS * (support_score - n_support_groups)
    score -= CONTRA_GROUP_POINTS * min(n_contra_groups, CONTRA_GROUP_CAP_GROUPS)
    if contra_score > n_contra_groups:
        score -= CONTRA_EXTRA_POINTS * (contra_score - n_contra_groups)
    score -= WEAKEN_POINTS * weaken_score
    score = max(0.0, min(100.0, round(score, 2)))

    if n_contra_groups >= 1 and contra_score >= support_score:
        state = "contradicted"
    elif n_contra_groups >= 1 and contra_score > 0:
        state = "contested"
    elif weaken_score > 0 and support_score <= weaken_score:
        state = "weakened"
    elif score >= STRONGLY_SUPPORTED_SCORE and n_support_groups >= STRONGLY_SUPPORTED_MIN_GROUPS:
        state = "strongly_supported"
    elif score >= SUPPORTED_SCORE:
        state = "supported"
    elif score >= EMERGING_SCORE:
        state = "emerging"
    elif score > 0:
        state = "tentative"
    else:
        state = "insufficient_evidence"

    explanation = (
        "score=%.2f from %d independent supporting group(s) (support_score=%.2f) vs "
        "%d independent contradicting group(s) (contra_score=%.2f); weakening_score=%.2f "
        "from %d weakening item(s); contextual/unresolved=%d not scored directly. "
        "Same-source items beyond the first in a group are discounted to %.0f%% weight "
        "to avoid double-counting repeated excerpts as independent confirmation."
    ) % (score, n_support_groups, support_score, n_contra_groups, contra_score,
         weaken_score, len(weakening), len(contextual) + len(unresolved), SAME_GROUP_DISCOUNT * 100)

    return state, score, counts, explanation

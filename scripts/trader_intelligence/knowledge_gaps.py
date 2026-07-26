#!/usr/bin/env python3
"""PROGRAM-007 Phase 7A (Knowledge Library vertical slice) -- deterministic
Knowledge Gap detection for a generated StrategyBlueprint.

Pure Python standard library. NO NETWORK ACCESS. Every gap here is derived
from a fixed, structural condition on the blueprint/claims already on disk
(an empty scope list, a missing workflow stage, an absent claim type) --
never a free-form guess, and a gap's currentBestAnswer is only ever set to
something the evidence actually contains at reduced confidence, never
invented to fill a hole.
"""
import glob as globmod
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import graph_common as gc       # noqa: E402
import evidence_common as evc   # noqa: E402

_NEWS_MARKERS = ("news",)
_SPREAD_MARKERS = ("spread",)
_VOLATILITY_MARKERS = ("volatil",)
_NO_TRADE_MARKERS = ("no trade", "don't trade", "do not trade", "avoid trading", "skip the trade")


def _any_claim_matches(claims, markers):
    return any(any(m in c["normalizedClaim"].lower() for m in markers) for c in claims)


def _related_claims(claims_by_type, *claim_types):
    out = []
    for ct in claim_types:
        out.extend(claims_by_type.get(ct, []))
    return out


def _best_partial_answer(idx, related_claims):
    """Never fabricates: only returns text that is literally the normalized
    text of an existing claim, and only when that claim's own confidence is
    at least 'emerging' (i.e. there is some real, if weak, signal)."""
    candidates = [c for c in related_claims if c["confidenceState"] not in
                  ("insufficient_evidence", "tentative", "unresolved")]
    if not candidates:
        return None, "none"
    best = max(candidates, key=lambda c: c["evidenceCount"])
    confidence_map = {"emerging": "low", "supported": "moderate", "strongly_supported": "high",
                       "contested": "low", "weakened": "low", "contradicted": "none"}
    return best["normalizedClaim"], confidence_map.get(best["confidenceState"], "low")


def _category_spec(idx, blueprint, claims_by_type):
    """Returns a list of (category, is_missing, question, why, sections,
    priority, next_source, validation_method, search_claims, answer_claims)
    tuples -- pure function of blueprint + claims_by_type, easy to unit
    test. search_claims is the pool recorded as 'evidence we looked in'
    (fine to be broad); answer_claims is the pool _best_partial_answer() is
    allowed to draw a currentBestAnswer from -- left empty ([]) for every
    category where the gap fires precisely because no claim of a relevant
    type/field exists, so there is structurally nothing genuine to offer as
    a partial answer (an unrelated claim's text must never be presented as
    if it answered a different question)."""
    all_claims = [c for lst in claims_by_type.values() for c in lst]
    scope = blueprint["scope"]
    workflow_stage_names = {s["stageName"] for s in blueprint["workflow"]}

    return [
        ("instrument", not scope["instruments"],
         "Which specific instrument(s) does this strategy apply to?",
         "Without a named instrument, the strategy cannot be scoped to a specific market for replay or paper testing.",
         ["Scope"], "high", "additional transcript or direct question to trader", "direct question to trader",
         all_claims, []),

        ("session", not scope["sessions"],
         "Which trading session(s) does this strategy apply to?",
         "Session restrictions materially affect setup validity and volatility conditions.",
         ["Scope"], "medium", "additional transcript covering session discussion", "direct question to trader",
         all_claims, []),

        ("higher_timeframe_bias", not scope["higherTimeframes"],
         "Is a higher-timeframe bias required before taking this setup?",
         "A missing higher-timeframe bias rule means the strategy's context requirement is unknown.",
         ["Scope", "Setup Identification"], "high", "additional transcript on multi-timeframe analysis",
         "direct question to trader",
         _related_claims(claims_by_type, "setup_requirement", "definition"),
         _related_claims(claims_by_type, "setup_requirement", "definition")),

        ("execution_timeframe", not scope["executionTimeframes"],
         "What is the execution timeframe for entries?",
         "Without a stated execution timeframe, entry timing cannot be replayed or tested.",
         ["Scope", "Entry Trigger"], "critical", "additional transcript or direct question to trader",
         "direct question to trader",
         _related_claims(claims_by_type, "entry_rule"), _related_claims(claims_by_type, "entry_rule")),

        ("setup_sequence", "Setup Identification" not in workflow_stage_names,
         "What is the exact sequence of events that defines a valid setup?",
         "Without a defined setup sequence, entry/confirmation logic has nothing to anchor to.",
         ["Setup Identification"], "critical", "additional transcript walking through a full setup example",
         "replay test against historical price action",
         _related_claims(claims_by_type, "setup_requirement", "definition"),
         _related_claims(claims_by_type, "setup_requirement", "definition")),

        ("entry_trigger", not blueprint["entryLogic"]["requiredConditions"],
         "What exact condition triggers an entry?",
         "No entry condition currently reaches confident support -- the strategy cannot be entered mechanically.",
         ["Entry Trigger"], "critical", "additional transcript with explicit entry-rule statements",
         "replay test against historical price action",
         _related_claims(claims_by_type, "entry_rule"), _related_claims(claims_by_type, "entry_rule")),

        ("confirmation", "Confirmation" not in workflow_stage_names,
         "Is any confirmation required before entry, and if so what?",
         "Confirmation requirements directly affect entry timing and false-signal rate.",
         ["Confirmation"], "high", "additional transcript on confirmation criteria",
         "replay test comparing with/without confirmation",
         _related_claims(claims_by_type, "confirmation_rule"), _related_claims(claims_by_type, "confirmation_rule")),

        ("invalidation", not blueprint["exitLogic"]["setupInvalidation"],
         "What condition invalidates this setup before or after entry?",
         "Without invalidation logic, there is no defined way to know the setup thesis failed.",
         ["Invalidation"], "critical", "additional transcript on setup invalidation",
         "replay test",
         _related_claims(claims_by_type, "invalidation_rule"), _related_claims(claims_by_type, "invalidation_rule")),

        ("stop_placement", not blueprint["exitLogic"]["stopPlacement"],
         "Where exactly is the stop placed?",
         "Without a stated stop rule, risk per trade cannot be calculated or replayed.",
         ["Stop Placement"], "critical", "additional transcript with explicit stop-placement statements",
         "replay test against historical price action",
         _related_claims(claims_by_type, "stop_rule"), _related_claims(claims_by_type, "stop_rule")),

        ("risk_percentage", not (blueprint["riskLogic"]["statedRiskRules"] or blueprint["riskLogic"]["inferredRiskRules"]),
         "What percentage of account equity is risked per trade?",
         "Without a stated risk percentage, position sizing cannot be determined for paper or live testing.",
         ["Risk Sizing"], "critical", "direct question to trader", "direct question to trader",
         _related_claims(claims_by_type, "risk_rule"), _related_claims(claims_by_type, "risk_rule")),

        ("target_selection", not blueprint["exitLogic"]["profitTargets"],
         "How is the profit target selected?",
         "Without target logic, expectancy cannot be estimated or replayed.",
         ["Target Selection"], "high", "additional transcript on target selection",
         "replay test against historical price action",
         _related_claims(claims_by_type, "target_rule"), _related_claims(claims_by_type, "target_rule")),

        ("trade_management", "Trade Management" not in workflow_stage_names,
         "How is the trade managed after entry (partials, break-even, trailing)?",
         "Trade management materially affects realized outcomes even when entry/exit rules are fixed.",
         ["Trade Management"], "medium", "additional transcript on in-trade management",
         "paper-trading test",
         _related_claims(claims_by_type, "trade_management_rule"), _related_claims(claims_by_type, "trade_management_rule")),

        # The remaining categories fire precisely when NO claim anywhere
        # mentions the relevant keyword/type -- so there is, by construction,
        # nothing in the current evidence that could genuinely answer them.
        # search_claims records the (broad) pool actually searched; the
        # answer pool is deliberately empty so no unrelated claim is ever
        # misattributed as a partial answer to a different question.
        ("news_handling", not _any_claim_matches(all_claims, _NEWS_MARKERS),
         "How does this strategy handle high-impact news events?",
         "News events can invalidate technical setups; the absence of a stated rule leaves this ambiguous.",
         ["Entry Trigger", "Invalidation"], "medium", "additional transcript or direct question to trader",
         "direct question to trader", all_claims, []),

        ("spread_handling", not _any_claim_matches(all_claims, _SPREAD_MARKERS),
         "Does spread affect entry, stop, or target placement?",
         "Wide spreads can materially change realized risk/reward versus the stated setup.",
         ["Entry Trigger", "Stop Placement"], "low", "direct question to trader", "direct question to trader",
         all_claims, []),

        ("volatility_handling", not _any_claim_matches(all_claims, _VOLATILITY_MARKERS),
         "Does this strategy adjust for high or low volatility conditions?",
         "Volatility regime can change whether the same setup criteria remain valid.",
         ["Scope", "Entry Trigger"], "medium", "additional transcript or direct question to trader",
         "direct question to trader", all_claims, []),

        ("no_trade_conditions", not _any_claim_matches(all_claims, _NO_TRADE_MARKERS),
         "Are there explicit conditions under which no trade should be taken?",
         "Without stated no-trade conditions, the strategy may be applied in contexts the trader would avoid.",
         ["Scope", "Entry Trigger"], "medium", "additional transcript or direct question to trader",
         "direct question to trader", all_claims, []),

        ("exception_handling", not claims_by_type.get("exception"),
         "Are there known exceptions to the stated rules?",
         "Without documented exceptions, edge cases may be silently mishandled by any future automation.",
         ["Entry Trigger", "Invalidation"], "medium", "additional transcript or direct question to trader",
         "direct question to trader", all_claims, []),
    ]


def generate_knowledge_gaps(gaps_dir, idx, blueprint, actor="pipeline", now=None):
    """Generates and persists one KnowledgeGap per missing/ambiguous
    category detected for the given blueprint. Never invents an answer --
    currentBestAnswer is only ever a real claim's own text, and only when
    that claim carries genuine (if partial) confidence."""
    now = now or datetime.now(timezone.utc)
    trader_id = blueprint["traderId"]
    claims = idx.claims_for_trader(trader_id)
    claims_by_type = {}
    for c in claims:
        claims_by_type.setdefault(c["claimType"], []).append(c)

    created = []
    for (category, is_missing, question, why, sections, priority, next_source, validation_method,
         search_claims, answer_claims) in _category_spec(idx, blueprint, claims_by_type):
        if not is_missing:
            continue
        best_answer, confidence = _best_partial_answer(idx, answer_claims)
        answer_status = "unanswered" if best_answer is None else "partially_answered"
        evidence_searched = sorted({eid for c in search_claims for eid in
                                     {l["evidenceId"] for l in idx.links_for_claim(c["claimId"])}})
        related_claim_ids = sorted({c["claimId"] for c in answer_claims})

        now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        gap_id = evc.next_gap_id(gaps_dir, now)
        record = {
            "gapId": gap_id, "traderId": trader_id, "blueprintId": blueprint["blueprintId"],
            "category": category, "question": question, "whyItMatters": why,
            "affectedSections": sections, "evidenceSearched": evidence_searched,
            "currentBestAnswer": best_answer, "answerStatus": answer_status, "confidence": confidence,
            "researchPriority": priority, "recommendedNextSourceType": next_source,
            "proposedValidationMethod": validation_method,
            "provenance": {"evidenceQuestionId": None, "relatedClaimIds": related_claim_ids},
            "createdAt": now_iso, "resolvedAt": None, "schemaVersion": evc.SCHEMA_VERSION,
        }
        path = os.path.join(gaps_dir, evc.gap_id_to_filename(gap_id))
        gc.atomic_write_text(path, gc.pretty_json(record))
        created.append(record)
    return created

#!/usr/bin/env python3
"""PROGRAM-007 Phase 7A (Knowledge Library vertical slice) -- deterministic,
non-executable Draft Strategy Blueprint generation.

Pure Python standard library. NO NETWORK ACCESS. A StrategyBlueprint is
research output only: it never creates or updates a StrategyRule, is never
read by any scanner or execution path, and its status is structurally
restricted to DRAFT_RESEARCH_ONLY/SUPERSEDED -- there is no code path that
can ever mark one "active". Every rule-like statement keeps its evidenceIds
and confidence; required/preferred/optional/forbidden/unknown are always
kept as distinct classifications, never collapsed into one "rule" bucket.
"""
import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import graph_common as gc       # noqa: E402
import evidence_common as evc   # noqa: E402

_STAGE_ORDER = [
    ("setup_requirement", "Setup Identification"), ("definition", "Setup Identification"),
    ("entry_rule", "Entry Trigger"),
    ("confirmation_rule", "Confirmation"),
    ("invalidation_rule", "Invalidation"),
    ("stop_rule", "Stop Placement"),
    ("target_rule", "Target Selection"),
    ("trade_management_rule", "Trade Management"),
    ("risk_rule", "Risk Sizing"),
]
_REQUIRED_STATES = ("supported", "strongly_supported")
_UNKNOWN_STATES = ("insufficient_evidence", "tentative", "unresolved", "contested", "contradicted", "weakened")
_DISCRETIONARY_MARKERS = ("discretion", "it depends", "sometimes i", "up to you", "case by case", "use your judgment")

_PARTIAL_MARKERS = ("partial",)
_BREAKEVEN_MARKERS = ("break even", "break-even", "breakeven")
_TRAILING_MARKERS = ("trail",)
_TIME_EXIT_MARKERS = ("time-based", "time based", "end of session", "before close", "by end of day")


def _evidence_ids_for_claim(idx, claim_id):
    return sorted({l["evidenceId"] for l in idx.links_for_claim(claim_id)})


def _labeled_statement(idx, claim):
    return {"statement": claim["normalizedClaim"], "evidenceIds": _evidence_ids_for_claim(idx, claim["claimId"]),
            "confidence": claim["confidenceState"]}


def _classification_for_state(state):
    if state in _REQUIRED_STATES:
        return "required"
    if state == "emerging":
        return "preferred"
    return "unknown"


def _questions_for_claim(idx, claim_id):
    return sorted([q["questionText"] for q in idx.questions.values() if q.get("claimId") == claim_id])


def _build_scope(claims, items_by_evidence_id, idx):
    markets = set()
    instruments = set()
    sessions = set()
    execution_tfs = set()
    higher_tfs = set()
    confirmation_tfs = set()
    preferred_conditions = set()
    avoided_conditions = set()
    for c in claims:
        if c.get("session"):
            sessions.add(c["session"])
        if c.get("timeframe"):
            text = c["normalizedClaim"].lower()
            if "higher" in text or "htf" in text:
                higher_tfs.add(c["timeframe"])
            elif c["claimType"] == "confirmation_rule":
                confirmation_tfs.add(c["timeframe"])
            else:
                execution_tfs.add(c["timeframe"])
        for l in idx.links_for_claim(c["claimId"]):
            item = idx.items.get(l["evidenceId"])
            if item and item.get("marketSymbol"):
                instruments.add(item["marketSymbol"])
        mc = c.get("marketCondition")
        if mc:
            if c["confidenceState"] == "contradicted" or c["claimType"] == "exception":
                avoided_conditions.add(mc)
            else:
                preferred_conditions.add(mc)
    return {
        "markets": sorted(markets), "instruments": sorted(instruments), "sessions": sorted(sessions),
        "higherTimeframes": sorted(higher_tfs), "executionTimeframes": sorted(execution_tfs),
        "confirmationTimeframes": sorted(confirmation_tfs),
        "preferredMarketConditions": sorted(preferred_conditions),
        "prohibitedOrAvoidedConditions": sorted(avoided_conditions),
    }


def _build_workflow(idx, claims_by_type):
    stages = []
    stage_number = 1
    seen_stage_names = set()
    for claim_type, stage_name in _STAGE_ORDER:
        matching = claims_by_type.get(claim_type, [])
        if not matching:
            continue
        if stage_name in seen_stage_names:
            # setup_requirement and definition share one stage -- merge, don't duplicate.
            stages[-1]["evidenceLinks"] = sorted(set(stages[-1]["evidenceLinks"]) |
                                                  {eid for c in matching for eid in _evidence_ids_for_claim(idx, c["claimId"])})
            continue
        seen_stage_names.add(stage_name)
        primary = max(matching, key=lambda c: (c["confidenceState"] in _REQUIRED_STATES, c["evidenceCount"]))
        texts = sorted({c["normalizedClaim"] for c in matching})
        competing = [t for t in texts if t != primary["normalizedClaim"]]
        evidence_links = sorted({eid for c in matching for eid in _evidence_ids_for_claim(idx, c["claimId"])})
        unknowns = sorted({q for c in matching for q in _questions_for_claim(idx, c["claimId"])})
        stages.append({
            "stageNumber": stage_number, "stageName": stage_name, "description": primary["normalizedClaim"],
            "classification": _classification_for_state(primary["confidenceState"]),
            "confidence": primary["confidenceState"], "evidenceLinks": evidence_links,
            "competingInterpretations": competing, "unknowns": unknowns,
        })
        stage_number += 1
    return stages


def _build_entry_logic(idx, claims_by_type):
    entry_claims = claims_by_type.get("entry_rule", []) + claims_by_type.get("setup_requirement", []) + \
        claims_by_type.get("confirmation_rule", [])
    required, preferred, optional, forbidden, unresolved = [], [], [], [], []
    for c in entry_claims:
        stmt = _labeled_statement(idx, c)
        if c["confidenceState"] in _REQUIRED_STATES:
            required.append(stmt)
        elif c["confidenceState"] == "emerging":
            preferred.append(stmt)
        elif c["confidenceState"] == "weakened":
            optional.append(stmt)
        elif c["confidenceState"] in ("insufficient_evidence", "tentative", "unresolved"):
            unresolved.append(c["normalizedClaim"])
        # contested/contradicted entry claims fall through to unresolved, since
        # what to actually require can't be determined from conflicting evidence.
        elif c["confidenceState"] in ("contested", "contradicted"):
            unresolved.append(c["normalizedClaim"])
    for c in claims_by_type.get("exception", []):
        forbidden.append(_labeled_statement(idx, c))
    return {
        "requiredConditions": required, "preferredConditions": preferred, "optionalConditions": optional,
        "forbiddenConditions": forbidden, "unresolvedConditions": sorted(set(unresolved)),
    }


def _keyword_bucket(claims, idx, markers):
    matches = []
    for c in claims:
        if any(m in c["normalizedClaim"].lower() for m in markers):
            matches.append(_labeled_statement(idx, c))
    return matches


def _build_exit_logic(idx, claims_by_type):
    stop_claims = claims_by_type.get("stop_rule", [])
    invalidation_claims = claims_by_type.get("invalidation_rule", [])
    target_claims = claims_by_type.get("target_rule", [])
    mgmt_claims = claims_by_type.get("trade_management_rule", [])

    unknowns = []
    if not stop_claims:
        unknowns.append("No stop_rule claim exists in evidence -- stop placement is unknown.")
    if not invalidation_claims:
        unknowns.append("No invalidation_rule claim exists in evidence -- setup invalidation is unknown.")
    if not target_claims:
        unknowns.append("No target_rule claim exists in evidence -- profit target selection is unknown.")

    partials = _keyword_bucket(mgmt_claims, idx, _PARTIAL_MARKERS)
    break_even = _keyword_bucket(mgmt_claims, idx, _BREAKEVEN_MARKERS)
    trailing = _keyword_bucket(mgmt_claims, idx, _TRAILING_MARKERS)
    time_exit = _keyword_bucket(mgmt_claims, idx, _TIME_EXIT_MARKERS)
    if not partials:
        unknowns.append("No partial-profit-taking rule found in evidence.")
    if not break_even:
        unknowns.append("No break-even rule found in evidence.")
    if not trailing:
        unknowns.append("No trailing-stop rule found in evidence.")
    if not time_exit:
        unknowns.append("No time-based exit rule found in evidence.")

    return {
        "stopPlacement": [_labeled_statement(idx, c) for c in stop_claims],
        "setupInvalidation": [_labeled_statement(idx, c) for c in invalidation_claims],
        "profitTargets": [_labeled_statement(idx, c) for c in target_claims],
        "partials": partials, "breakEven": break_even, "trailing": trailing, "timeBasedExit": time_exit,
        "unknowns": unknowns,
    }


def _build_risk_logic(idx, claims_by_type):
    risk_claims = claims_by_type.get("risk_rule", [])
    stated, inferred = [], []
    for c in risk_claims:
        links = idx.links_for_claim(c["claimId"])
        direct = any(idx.items.get(l["evidenceId"], {}).get("directness") in ("direct_explicit", "direct_demonstrated")
                     for l in links)
        (stated if direct else inferred).append(_labeled_statement(idx, c))
    missing = [] if risk_claims else ["No risk_rule claim exists in evidence -- risk-per-trade sizing is unknown."]
    return {"statedRiskRules": stated, "inferredRiskRules": inferred, "missingRiskRules": missing}


def _build_contradictions(idx, claim_ids_by_trader):
    section_by_claim_type = {ct: name for ct, name in _STAGE_ORDER}
    results = []
    for cr in idx.contradictions.values():
        if cr["claimAId"] not in claim_ids_by_trader and cr["claimBId"] not in claim_ids_by_trader:
            continue
        affected = set()
        for cid in (cr["claimAId"], cr["claimBId"]):
            claim = idx.claims.get(cid)
            if claim:
                affected.add(section_by_claim_type.get(claim["claimType"], claim["claimType"]))
        results.append({
            "contradictionRecordId": cr["contradictionId"],
            "conflictingClaimIds": sorted([cr["claimAId"], cr["claimBId"]]),
            "affectedSections": sorted(affected),
            "currentHandling": "Unresolved -- requires owner review before any related rule is considered.",
        })
    return sorted(results, key=lambda r: r["contradictionRecordId"])


def build_strategy_blueprint(idx, trader_id, strategy_name=None, version=1, actor="pipeline", now=None):
    """Deterministic given identical stored state. Returns None if the
    trader has zero claims (nothing to draft a blueprint from)."""
    now = now or datetime.now(timezone.utc)
    claims = idx.claims_for_trader(trader_id)
    if not claims:
        return None

    claims_by_type = {}
    for c in claims:
        claims_by_type.setdefault(c["claimType"], []).append(c)

    claim_ids = {c["claimId"] for c in claims}
    scope = _build_scope(claims, idx.items, idx)
    workflow = _build_workflow(idx, claims_by_type)
    entry_logic = _build_entry_logic(idx, claims_by_type)
    exit_logic = _build_exit_logic(idx, claims_by_type)
    risk_logic = _build_risk_logic(idx, claims_by_type)
    contradictions = _build_contradictions(idx, claim_ids)

    source_ids, segment_ids, evidence_ids = set(), set(), set()
    discretionary_language = []
    insufficient_evidence = []
    ambiguous_definitions = []
    for c in claims:
        links = idx.links_for_claim(c["claimId"])
        for l in links:
            item = idx.items.get(l["evidenceId"])
            if not item:
                continue
            evidence_ids.add(item["evidenceId"])
            source_ids.add(item["sourceId"])
            locator = item.get("sourceLocator")
            if locator and locator.startswith("TSEG|"):
                segment_ids.add(locator)
            blob = ((item.get("exactExcerpt") or "") + " " + (item.get("normalizedObservation") or "")).lower()
            if any(m in blob for m in _DISCRETIONARY_MARKERS):
                discretionary_language.append("%s: %r" % (c["claimId"], item.get("exactExcerpt")))
        if c["confidenceState"] == "insufficient_evidence":
            insufficient_evidence.append(c["normalizedClaim"])
        if c["confidenceState"] in ("contested", "tentative"):
            ambiguous_definitions.append(c["normalizedClaim"])

    missing_information = []
    for claim_type, stage_name in _STAGE_ORDER:
        if claim_type in ("definition",):
            continue
        if claim_type not in claims_by_type:
            missing_information.append("No %s claim found -- %s is unknown." % (claim_type, stage_name.lower()))

    blueprint = {
        "blueprintId": None,  # assigned by register_strategy_blueprint()
        "traderId": trader_id,
        "strategyName": strategy_name or ("%s Trading Strategy (Draft)" % trader_id),
        "version": version,
        "status": "DRAFT_RESEARCH_ONLY",
        "supersedesBlueprintId": None,
        "generatedAt": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "scope": scope,
        "workflow": workflow,
        "entryLogic": entry_logic,
        "exitLogic": exit_logic,
        "riskLogic": risk_logic,
        "contradictions": contradictions,
        "validationStatus": {
            "researchStatus": "draft", "replayStatus": "not_available",
            "paperTradingStatus": "not_available", "productionStatus": "not_applicable",
        },
        "sourceLineage": {
            "sourceIds": sorted(source_ids), "segmentIds": sorted(segment_ids),
            "evidenceIds": sorted(evidence_ids), "claimIds": sorted(claim_ids),
        },
        "limitations": {
            "missingInformation": missing_information,
            "discretionaryLanguage": sorted(set(discretionary_language)),
            "ambiguousDefinitions": sorted(set(ambiguous_definitions)),
            "insufficientEvidence": sorted(set(insufficient_evidence)),
        },
        "schemaVersion": evc.SCHEMA_VERSION,
    }
    return blueprint


def register_strategy_blueprint(blueprints_dir, idx, trader_id, strategy_name=None, actor="pipeline", now=None):
    """Builds and persists a new StrategyBlueprint. Never edits a prior
    version in place -- pass supersedesBlueprintId explicitly (via a second
    call plus manual linkage) if a corrected version is needed later; this
    keeps every past draft fully inspectable, exactly like EvidenceItem."""
    now = now or datetime.now(timezone.utc)
    blueprint = build_strategy_blueprint(idx, trader_id, strategy_name=strategy_name, actor=actor, now=now)
    if blueprint is None:
        return None
    blueprint["blueprintId"] = evc.next_blueprint_id(blueprints_dir, trader_id, now)
    path = os.path.join(blueprints_dir, evc.blueprint_id_to_filename(blueprint["blueprintId"]))
    gc.atomic_write_text(path, gc.pretty_json(blueprint))
    return blueprint

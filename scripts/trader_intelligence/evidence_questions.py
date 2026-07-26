#!/usr/bin/env python3
"""PROGRAM-006 Phase 1B (ADR-009 sec. 12, Deliverable 13) -- deterministic
EvidenceQuestion generation.

Pure Python standard library. NO NETWORK ACCESS. NO LLM. Every question is
produced from a fixed, structural condition on stored records (missing
field, cross-claim gap, configured marker phrase) -- never a free-form
guess, and never auto-answered. Named EvidenceQuestion, not
UnresolvedQuestion, to avoid colliding with the pre-existing Wave-1 entity
of that name (see ADR-009 sec. 12).
"""
import glob as globmod
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import graph_common as gc      # noqa: E402
import evidence_common as evc  # noqa: E402

RULE_ELIGIBLE_CLAIM_TYPES = set(evc.RULE_CANDIDATE_ELIGIBLE_CLAIM_TYPES)
_SCOPE_SENSITIVE_TYPES = {"entry_rule", "confirmation_rule", "invalidation_rule", "stop_rule",
                          "target_rule", "timeframe_rule", "session_rule"}
_DISCRETIONARY_MARKERS = ("discretion", "it depends", "sometimes i", "up to you", "case by case", "use your judgment")


def _load_all(dir_path, id_field):
    out = {}
    if not os.path.isdir(dir_path):
        return out
    for path in sorted(globmod.glob(os.path.join(dir_path, "*.json"))):
        with open(path, "r", encoding="utf-8") as f:
            record = json.load(f)
        out[record[id_field]] = record
    return out


def create_question(questions_dir, now, questionType, questionText, priority, reason, blockingStatus,
                     claimId=None, evidenceIds=None, sourceIds=None):
    if questionType not in evc.QUESTION_TYPES:
        raise evc.EvidenceValidationError("Unknown questionType %r" % (questionType,))
    if priority not in evc.QUESTION_PRIORITIES:
        raise evc.EvidenceValidationError("Unknown priority %r" % (priority,))
    if blockingStatus not in evc.QUESTION_BLOCKING_STATUSES:
        raise evc.EvidenceValidationError("Unknown blockingStatus %r" % (blockingStatus,))
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    questionId = evc.next_question_id(questions_dir, now)
    record = {
        "questionId": questionId, "claimId": claimId, "evidenceIds": evidenceIds or [],
        "sourceIds": sourceIds or [], "questionType": questionType, "questionText": questionText,
        "priority": priority, "reason": reason, "blockingStatus": blockingStatus,
        "researchStatus": "open", "answerStatus": "unanswered", "answerEvidenceIds": [],
        "createdAt": now_iso, "resolvedAt": None, "schemaVersion": evc.SCHEMA_VERSION,
    }
    path = os.path.join(questions_dir, evc.question_id_to_filename(questionId))
    gc.atomic_write_text(path, gc.pretty_json(record))
    return record


def _scope_tuple(claim):
    return (claim.get("traderId"), claim.get("strategyFamilyId"), claim.get("timeframe"))


def detect_questions_for_claim(claim, links, items_by_id, all_claims):
    """Returns a deterministic list of question specs (dicts with questionType/
    questionText/priority/reason/blockingStatus/evidenceIds/sourceIds) -- does
    not persist anything. Pure function of its inputs so results are
    reproducible and testable without touching disk."""
    specs = []
    claim_id = claim["claimId"]
    claim_type = claim["claimType"]

    if claim_type in _SCOPE_SENSITIVE_TYPES and not claim.get("timeframe"):
        specs.append({"questionType": "missing_timeframe",
                       "questionText": "Claim %r has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?" % claim_id,
                       "priority": "medium", "blockingStatus": "blocks_rule_candidate",
                       "reason": "claimType=%r is timeframe-sensitive and claim.timeframe is null." % claim_type})

    if claim_type in ("entry_rule", "confirmation_rule", "session_rule") and not claim.get("session"):
        specs.append({"questionType": "missing_session",
                       "questionText": "Claim %r has no session recorded -- does this rule apply in every session or only specific ones?" % claim_id,
                       "priority": "medium", "blockingStatus": "blocks_rule_candidate",
                       "reason": "claimType=%r is session-sensitive and claim.session is null." % claim_type})

    if not any((claim.get("traderId"), claim.get("strategyFamilyId"), claim.get("timeframe"),
                claim.get("session"), claim.get("marketCondition"))):
        specs.append({"questionType": "unclear_scope",
                       "questionText": "Claim %r carries no scope at all (no trader, strategy family, timeframe, session, or market condition) -- what is this rule actually scoped to?" % claim_id,
                       "priority": "high", "blockingStatus": "blocks_rule_candidate",
                       "reason": "All five scope fields are null on this claim."})

    if claim_type == "entry_rule":
        has_invalidation_sibling = any(
            c["claimId"] != claim_id and c["claimType"] == "invalidation_rule" and _scope_tuple(c) == _scope_tuple(claim)
            for c in all_claims)
        if not has_invalidation_sibling:
            specs.append({"questionType": "missing_invalidation",
                           "questionText": "Entry rule %r has no companion invalidation_rule claim in the same scope -- what invalidates this setup?" % claim_id,
                           "priority": "high", "blockingStatus": "blocks_rule_candidate",
                           "reason": "No claimType='invalidation_rule' claim shares this claim's (trader, strategyFamily, timeframe) scope."})

    if claim_type == "stop_rule":
        direct_links = [l for l in links if l["relationshipType"] == "supports"
                         and items_by_id.get(l["evidenceId"], {}).get("directness") in ("direct_explicit", "direct_demonstrated")]
        if not direct_links:
            specs.append({"questionType": "missing_stop_placement",
                           "questionText": "Stop rule %r has no direct (explicit or demonstrated) supporting evidence -- is stop placement actually well-defined, or discretionary/ambiguous?" % claim_id,
                           "priority": "high", "blockingStatus": "blocks_rule_candidate",
                           "reason": "No supporting link has directness in {direct_explicit, direct_demonstrated}."})

    if claim_type == "trade_management_rule":
        for link in links:
            item = items_by_id.get(link["evidenceId"])
            if not item:
                continue
            blob = ((item.get("exactExcerpt") or "") + " " + (item.get("normalizedObservation") or "")).lower()
            if any(marker in blob for marker in _DISCRETIONARY_MARKERS):
                specs.append({"questionType": "discretionary_management",
                               "questionText": "Evidence for trade-management claim %r describes discretionary judgment rather than a fixed rule -- should this remain discretionary, or is there a more precise rule underneath it?" % claim_id,
                               "priority": "medium", "blockingStatus": "blocks_rule_candidate",
                               "reason": "Evidence text matched a configured discretionary-language marker.",
                               "evidenceIds": [item["evidenceId"]]})
                break

    supporting_sources = {items_by_id[l["evidenceId"]]["sourceId"] for l in links
                           if l["relationshipType"] in ("supports", "exemplifies") and l["evidenceId"] in items_by_id}
    contradicting_sources = {items_by_id[l["evidenceId"]]["sourceId"] for l in links
                              if l["relationshipType"] == "contradicts" and l["evidenceId"] in items_by_id}
    same_source_conflict = supporting_sources & contradicting_sources
    if same_source_conflict:
        specs.append({"questionType": "self_contradiction",
                       "questionText": "Claim %r has supporting and contradicting evidence from the same source (%s) -- did this source contradict itself, or state an exception?" % (
                           claim_id, ", ".join(sorted(same_source_conflict))),
                       "priority": "high", "blockingStatus": "blocks_rule_candidate",
                       "reason": "The same sourceId appears in both a supporting and a contradicting link for this claim.",
                       "sourceIds": sorted(same_source_conflict)})

    behavior_conflict_items = [
        (l, items_by_id.get(l["evidenceId"])) for l in links
        if l["relationshipType"] == "contradicts" and items_by_id.get(l["evidenceId"], {}).get("directness") == "direct_demonstrated"
    ]
    explicit_support_exists = any(
        items_by_id.get(l["evidenceId"], {}).get("directness") == "direct_explicit"
        for l in links if l["relationshipType"] in ("supports", "exemplifies")
    )
    if behavior_conflict_items and explicit_support_exists:
        conflict_ids = [item["evidenceId"] for _l, item in behavior_conflict_items if item]
        specs.append({"questionType": "behavior_conflicts_with_instruction",
                       "questionText": "Claim %r is explicitly stated but demonstrated behavior contradicts it -- which should MOGO trust, the stated rule or the observed behavior?" % claim_id,
                       "priority": "critical", "blockingStatus": "blocks_promotion",
                       "reason": "A direct_explicit supporting item and a direct_demonstrated contradicting item both exist for this claim.",
                       "evidenceIds": conflict_ids})

    for link in links:
        item = items_by_id.get(link["evidenceId"])
        if item and item.get("evidenceType") == "exception_statement":
            has_exception_sibling = any(c["claimType"] == "exception" and _scope_tuple(c) == _scope_tuple(claim)
                                         for c in all_claims)
            if not has_exception_sibling:
                specs.append({"questionType": "unruled_exception",
                               "questionText": "An exception was mentioned in evidence for claim %r but no exception claim captures it -- what is the exact rule for when this exception applies?" % claim_id,
                               "priority": "medium", "blockingStatus": "non_blocking",
                               "reason": "evidenceType='exception_statement' is linked but no sibling claimType='exception' exists in scope.",
                               "evidenceIds": [item["evidenceId"]]})
                break

    if claim["confidenceState"] in ("insufficient_evidence", "tentative"):
        specs.append({"questionType": "insufficient_independent_support",
                       "questionText": "Claim %r is only %r -- what additional independent source would raise confidence?" % (
                           claim_id, claim["confidenceState"]),
                       "priority": "medium", "blockingStatus": "blocks_rule_candidate",
                       "reason": "confidenceState is %r." % claim["confidenceState"]})

    if claim_type in RULE_ELIGIBLE_CLAIM_TYPES and claim["confidenceState"] in ("supported", "strongly_supported"):
        specs.append({"questionType": "missing_replay_validation",
                       "questionText": "Claim %r looks well-supported by evidence but has no replay validation yet -- does it hold up against historical price action?" % claim_id,
                       "priority": "low", "blockingStatus": "blocks_promotion",
                       "reason": "Rule-eligible claimType with confidenceState in {supported, strongly_supported} but no replay evidence producer has run yet (out of scope for Phase 1B)."})
        specs.append({"questionType": "missing_paper_validation",
                       "questionText": "Claim %r looks well-supported by evidence but has no paper-trading validation yet -- has it been tested live without capital risk?" % claim_id,
                       "priority": "low", "blockingStatus": "blocks_promotion",
                       "reason": "Rule-eligible claimType with confidenceState in {supported, strongly_supported} but no paper-trading evidence producer has run yet (out of scope for Phase 1B)."})

    specs.sort(key=lambda s: s["questionType"])
    return specs


def generate_questions_for_claim(questions_dir, now, claim, links, items_by_id, all_claims):
    """Detects and persists EvidenceQuestion records for one claim. Returns
    the created records. Idempotency (never re-raising an identical question
    twice) is a review-queue/report-time concern, not this function's --
    detection stays a pure function of current state."""
    specs = detect_questions_for_claim(claim, links, items_by_id, all_claims)
    created = []
    for spec in specs:
        record = create_question(
            questions_dir, now, spec["questionType"], spec["questionText"], spec["priority"],
            spec["reason"], spec["blockingStatus"], claimId=claim["claimId"],
            evidenceIds=spec.get("evidenceIds"), sourceIds=spec.get("sourceIds"))
        created.append(record)
    return created

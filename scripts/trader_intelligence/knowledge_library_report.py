#!/usr/bin/env python3
"""PROGRAM-007 Phase 7A (Knowledge Library vertical slice, Deliverable 6) --
human-review report for one trader's processed Knowledge Library.

Pure Python standard library. NO NETWORK ACCESS. Every factual statement in
this report is read directly from an already-generated TraderProfile,
StrategyBlueprint, KnowledgeGap list, and Hypothesis list -- nothing here is
free-form narrative or a fabricated conclusion. This report is itself
research output: it never marks anything executable, never computes a
profitability figure, and never changes review status on its own (see
review_queues.apply_review_action() for the only code path that does that,
and only ever on explicit human instruction).
"""
import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import evidence_common as evc  # noqa: E402

REPORT_SCHEMA_VERSION = 1

# Mirrors trader_profile.py's own _DIRECT_DIRECTNESS split -- kept here too
# (rather than imported) since the two modules classify slightly different
# things (concept status vs. explicit-vs-implied rule text) from the same
# underlying vocabulary.
_DIRECT_DIRECTNESS = ("direct_explicit", "direct_demonstrated")
_IMPLIED_DIRECTNESS = ("indirect_implied", "inferred_from_context", "derived_from_analysis")

_MANDATORY_DISCLAIMERS = {
    "researchOnly": True,
    "unvalidated": True,
    "notExecutable": True,
    "noProfitabilityClaim": True,
    "requiresReplayValidation": True,
    "requiresPaperTradingValidation": True,
}

_DISCLAIMER_TEXT = (
    "This report is research output only. Nothing in it has been validated, "
    "is executable, or carries any profitability claim. Every rule-like "
    "statement here requires replay validation and paper-trading validation "
    "before it could ever be considered for live or paper execution -- and "
    "even then, only through the existing StrategyRule promotion pipeline, "
    "never automatically from this report."
)


def _claim_evidence_excerpts(idx, claim_id):
    out = []
    for l in idx.links_for_claim(claim_id):
        item = idx.items.get(l["evidenceId"])
        if item:
            out.append({"evidenceId": item["evidenceId"], "directness": item.get("directness"),
                        "exactExcerpt": item.get("exactExcerpt")})
    return sorted(out, key=lambda e: e["evidenceId"])


def _claim_directness_bucket(idx, claim_id):
    directness_values = {e["directness"] for e in _claim_evidence_excerpts(idx, claim_id)}
    if directness_values & set(_DIRECT_DIRECTNESS):
        return "explicit"
    if directness_values & set(_IMPLIED_DIRECTNESS):
        return "implied_or_inferred"
    return "other"


def _claim_row(idx, claim):
    return {
        "claimId": claim["claimId"], "claimType": claim["claimType"],
        "normalizedClaim": claim["normalizedClaim"], "confidenceState": claim["confidenceState"],
        "confidenceScore": claim["confidenceScore"], "claimStatus": claim["claimStatus"],
        "evidenceExcerpts": _claim_evidence_excerpts(idx, claim["claimId"]),
    }


def generate_knowledge_library_report(idx, trader_id, profile, blueprint, gaps, hypotheses, now=None):
    """Returns None if profile or blueprint is None (nothing real to report
    on yet -- callers distinguish this the same way the rest of this system
    does: not_found/empty, never a fabricated placeholder report)."""
    if profile is None or blueprint is None:
        return None
    now = now or datetime.now(timezone.utc)
    gaps = gaps or []
    hypotheses = hypotheses or []

    claims = idx.claims_for_trader(trader_id)
    claim_ids = {c["claimId"] for c in claims}

    source_ids = profile["sourceLineage"]["sourceIds"]
    sources = [idx.sources[sid] for sid in source_ids if sid in idx.sources]

    explicit_rules = []
    implied_rules = []
    for c in claims:
        bucket = _claim_directness_bucket(idx, c["claimId"])
        if bucket == "explicit":
            explicit_rules.append(_claim_row(idx, c))
        elif bucket == "implied_or_inferred":
            implied_rules.append(_claim_row(idx, c))
    explicit_rules.sort(key=lambda r: r["claimId"])
    implied_rules.sort(key=lambda r: r["claimId"])

    pending_review_claims = sorted([c["claimId"] for c in claims if c["claimStatus"] == "pending_review"])
    open_questions = sorted(
        [{"questionId": q["questionId"], "questionText": q["questionText"], "priority": q["priority"]}
         for q in idx.questions.values() if q.get("claimId") in claim_ids and q["researchStatus"] in ("open", "researching")],
        key=lambda q: q["questionId"])
    relevant_entity_ids = claim_ids | set(source_ids)
    open_queue_entries = sorted(
        [{"queueEntryId": e["queueEntryId"], "queueType": e["queueType"], "entityId": e["entityId"],
          "priority": e["priority"], "reason": e["reason"]}
         for e in idx.queue_entries.values()
         if e.get("entityId") in relevant_entity_ids and e["reviewStatus"] in ("open", "in_review")],
        key=lambda e: e["queueEntryId"])
    items_requiring_review = {
        "pendingReviewClaimIds": pending_review_claims,
        "openUnresolvedQuestions": open_questions,
        "openReviewQueueEntries": open_queue_entries,
    }

    replay_recommendations = sorted({h["proposedReplayTest"] for h in hypotheses}) + sorted(
        {g["proposedValidationMethod"] for g in gaps if "replay" in g["proposedValidationMethod"].lower()})
    paper_recommendations = sorted({h["proposedPaperTest"] for h in hypotheses}) + sorted(
        {g["proposedValidationMethod"] for g in gaps if "paper" in g["proposedValidationMethod"].lower()})
    if not replay_recommendations:
        replay_recommendations = ["No hypotheses or gaps yet reference a replay test -- "
                                   "generate hypotheses/gaps before any replay work is scheduled."]
    if not paper_recommendations:
        paper_recommendations = ["No hypotheses or gaps yet reference a paper-trading test -- "
                                  "generate hypotheses/gaps before any paper-trading work is scheduled."]

    limitations = sorted(set(
        profile.get("limitations", []) +
        blueprint["limitations"]["missingInformation"] +
        blueprint["limitations"]["discretionaryLanguage"] +
        blueprint["limitations"]["ambiguousDefinitions"] +
        blueprint["limitations"]["insufficientEvidence"]
    ))

    report = {
        "reportId": "KLREPORT|%s|%s" % (trader_id, now.strftime("%Y%m%dT%H%M%SZ")),
        "traderId": trader_id, "profileId": profile["profileId"], "blueprintId": blueprint["blueprintId"],
        "reportSchemaVersion": REPORT_SCHEMA_VERSION, "generatedAt": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "disclaimers": _MANDATORY_DISCLAIMERS, "disclaimerText": _DISCLAIMER_TEXT,

        # 1. Source summary
        "sourceSummary": {
            "sourceCount": len(sources),
            "sources": [{"sourceId": s["sourceId"], "title": s.get("title"), "sourceType": s.get("sourceType"),
                         "provenanceStatus": s.get("provenanceStatus")} for s in sources],
        },
        # 2. Extraction statistics
        "extractionStatistics": {
            "evidenceCount": profile["evidenceCount"], "observationCount": profile["observationCount"],
            "claimCount": profile["claimCount"], "contradictionCount": profile["contradictionCount"],
            "unresolvedQuestionCount": profile["unresolvedQuestionCount"],
            "hypothesisCount": profile["hypothesisCount"], "sourceCount": profile["sourceCount"],
            "extractionStatus": profile["extractionStatus"],
        },
        # 3. Trader Profile
        "traderProfile": profile,
        # 4. Draft Strategy Blueprint
        "strategyBlueprint": blueprint,
        # 5. Explicit rules
        "explicitRules": explicit_rules,
        # 6. Implied or inferred rules
        "impliedOrInferredRules": implied_rules,
        # 7. Contradictions
        "contradictions": blueprint["contradictions"],
        # 8. Knowledge gaps
        "knowledgeGaps": gaps,
        # 9. Proposed hypotheses
        "proposedHypotheses": hypotheses,
        # 10. Items requiring human review
        "itemsRequiringHumanReview": items_requiring_review,
        # 11. Replay recommendations
        "replayRecommendations": replay_recommendations,
        # 12. Paper-trading recommendations
        "paperTradingRecommendations": paper_recommendations,
        # 13. Limitations
        "limitations": limitations,
        # 14. Full lineage summary
        "lineageSummary": {
            "profileSourceLineage": profile["sourceLineage"],
            "blueprintSourceLineage": blueprint["sourceLineage"],
        },
    }
    return report


def render_knowledge_library_report_markdown(report):
    lines = []
    lines.append("# Knowledge Library Report: %s" % report["traderId"])
    lines.append("")
    lines.append("_Generated %s. reportSchemaVersion=%d._" % (report["generatedAt"], report["reportSchemaVersion"]))
    lines.append("")
    lines.append("> **%s**" % report["disclaimerText"])
    lines.append("")

    def section(title, body_lines):
        lines.append("## %s" % title)
        if body_lines:
            lines.extend(body_lines)
        else:
            lines.append("_None._")
        lines.append("")

    ss = report["sourceSummary"]
    section("1. Source Summary", ["- %s (%s): %s" % (s["sourceId"], s["sourceType"], s["title"])
                                    for s in ss["sources"]] or None)

    es = report["extractionStatistics"]
    section("2. Extraction Statistics", [
        "- Evidence: %d, Observations: %d, Claims: %d" % (es["evidenceCount"], es["observationCount"], es["claimCount"]),
        "- Contradictions: %d, Unresolved questions: %d, Hypotheses: %d" % (
            es["contradictionCount"], es["unresolvedQuestionCount"], es["hypothesisCount"]),
        "- Sources: %d, Extraction status: %s" % (es["sourceCount"], es["extractionStatus"]),
    ])

    tp = report["traderProfile"]
    section("3. Trader Profile", [
        "- Canonical name: %s (traderId=%s)" % (tp["canonicalName"], tp["traderId"]),
        "- Profile ID: %s, schemaVersion=%d" % (tp["profileId"], tp["schemaVersion"]),
        "- Review status: %s" % tp["reviewStatus"],
    ])

    sb = report["strategyBlueprint"]
    section("4. Draft Strategy Blueprint", [
        "- Blueprint ID: %s, status=%s (research-only, never executable)" % (sb["blueprintId"], sb["status"]),
        "- Strategy name: %s" % sb["strategyName"],
        "- Validation status: research=%s, replay=%s, paperTrading=%s, production=%s" % (
            sb["validationStatus"]["researchStatus"], sb["validationStatus"]["replayStatus"],
            sb["validationStatus"]["paperTradingStatus"], sb["validationStatus"]["productionStatus"]),
    ])

    section("5. Explicit Rules", ["- [%s] %s (confidence=%s)" % (r["claimId"], r["normalizedClaim"], r["confidenceState"])
                                   for r in report["explicitRules"]])
    section("6. Implied or Inferred Rules", ["- [%s] %s (confidence=%s)" % (
        r["claimId"], r["normalizedClaim"], r["confidenceState"]) for r in report["impliedOrInferredRules"]])
    section("7. Contradictions", ["- %s: %s (sections: %s)" % (
        c["contradictionRecordId"], " vs ".join(c["conflictingClaimIds"]), ", ".join(c["affectedSections"]))
        for c in report["contradictions"]])
    section("8. Knowledge Gaps", ["- [%s/%s] %s -> %s (answer: %s)" % (
        g["category"], g["researchPriority"], g["question"], g["currentBestAnswer"] or "unanswered", g["answerStatus"])
        for g in report["knowledgeGaps"]])
    section("9. Proposed Hypotheses", ["- [%s/%s] %s" % (h["status"], h["confidence"], h["statement"])
                                        for h in report["proposedHypotheses"]])

    irr = report["itemsRequiringHumanReview"]
    review_lines = []
    review_lines.extend("- Claim pending review: %s" % cid for cid in irr["pendingReviewClaimIds"])
    review_lines.extend("- Open question [%s]: %s" % (q["priority"], q["questionText"]) for q in irr["openUnresolvedQuestions"])
    review_lines.extend("- Open review-queue entry [%s]: %s (%s)" % (e["queueType"], e["entityId"], e["reason"])
                         for e in irr["openReviewQueueEntries"])
    section("10. Items Requiring Human Review", review_lines)

    section("11. Replay Recommendations", ["- %s" % r for r in report["replayRecommendations"]])
    section("12. Paper-Trading Recommendations", ["- %s" % r for r in report["paperTradingRecommendations"]])
    section("13. Limitations", ["- %s" % l for l in report["limitations"]])

    ls = report["lineageSummary"]
    section("14. Full Lineage Summary", [
        "- Profile sources: %s" % (", ".join(ls["profileSourceLineage"]["sourceIds"]) or "none"),
        "- Profile claims: %s" % (", ".join(ls["profileSourceLineage"]["claimIds"]) or "none"),
        "- Blueprint sources: %s" % (", ".join(ls["blueprintSourceLineage"]["sourceIds"]) or "none"),
        "- Blueprint segments: %s" % (", ".join(ls["blueprintSourceLineage"]["segmentIds"]) or "none"),
        "- Blueprint evidence: %s" % (", ".join(ls["blueprintSourceLineage"]["evidenceIds"]) or "none"),
        "- Blueprint claims: %s" % (", ".join(ls["blueprintSourceLineage"]["claimIds"]) or "none"),
    ])

    return "\n".join(lines)

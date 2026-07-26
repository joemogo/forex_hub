#!/usr/bin/env python3
"""PROGRAM-006 Phase 1B (ADR-009, Deliverable 15) -- TJR (or any trader)
research report generator.

Pure Python standard library. NO NETWORK ACCESS. Every factual statement in
the report is read directly from stored records (idx) -- nothing here is
free-form narrative. Works for a completed OR partially-completed intake,
and for a genuinely empty corpus (report sections are simply empty/zero).
"""
import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import evidence_common as evc  # noqa: E402

REPORT_SCHEMA_VERSION = 1


def _item_summary(item):
    return {"evidenceId": item["evidenceId"], "evidenceType": item["evidenceType"],
            "directness": item.get("directness"), "extractionCertainty": item.get("extractionCertainty"),
            "exactExcerpt": item.get("exactExcerpt"), "startTimestamp": item.get("startTimestamp")}


def _claim_summary(claim):
    return {"claimId": claim["claimId"], "claimType": claim["claimType"],
            "normalizedClaim": claim["normalizedClaim"], "claimStatus": claim["claimStatus"],
            "confidenceState": claim["confidenceState"], "confidenceScore": claim["confidenceScore"]}


def generate_tjr_research_report(idx, intakeId, now=None):
    """Returns None if intakeId is not found (caller distinguishes not_found
    the same way every other query in this system does)."""
    intake = idx.intakes.get(intakeId)
    if intake is None:
        return None
    now = now or datetime.now(timezone.utc)

    segments = idx.segments_for_intake(intakeId)
    annotations = sorted([a for a in idx.annotations.values() if a["intakeId"] == intakeId],
                          key=lambda a: a["annotationId"])
    sourceId = intake.get("sourceId")
    source = idx.sources.get(sourceId) if sourceId else None
    items = sorted(idx.items_for_source(sourceId), key=lambda i: i["evidenceId"]) if sourceId else []
    claims = sorted(idx.claims_for_source(sourceId), key=lambda c: c["claimId"]) if sourceId else []
    claim_ids = {c["claimId"] for c in claims}
    links = [l for l in idx.links.values() if l["claimId"] in claim_ids]
    contradictions = sorted(
        [cr for cr in idx.contradictions.values() if cr["claimAId"] in claim_ids or cr["claimBId"] in claim_ids],
        key=lambda c: c["contradictionId"])
    questions = sorted([q for q in idx.questions.values() if q.get("claimId") in claim_ids],
                        key=lambda q: q["questionId"])
    proposals = sorted(
        [p for p in idx.proposals.values() if claim_ids & set(p.get("originatingClaimIds", []))],
        key=lambda p: p["proposalId"])
    queue_entries = sorted(
        [e for e in idx.queue_entries.values() if e["entityId"] in claim_ids or e["entityId"] == intakeId],
        key=lambda e: e["queueEntryId"])

    explicit_statements = [i for i in items if i.get("directness") == "direct_explicit"]
    demonstrated_behavior = [i for i in items if i.get("directness") == "direct_demonstrated"]
    inferred_observations = [i for i in items if i.get("directness") in ("inferred_from_context", "derived_from_analysis")]
    opinions_unsupported = [i for i in items if i.get("evidenceType") in ("opinion", "intuition", "prediction")]
    exceptions = [i for i in items if i.get("evidenceType") == "exception_statement"]

    missing_component_question_types = {"missing_invalidation", "missing_stop_placement", "missing_timeframe",
                                          "missing_session", "missing_target_logic", "unclear_scope"}
    missing_strategy_components = sorted({q["questionText"] for q in questions if q["questionType"] in missing_component_question_types})

    supported = [c for c in claims if c["confidenceState"] in ("supported", "strongly_supported")]
    what_learned = ["%s (%s, score=%s)" % (c["normalizedClaim"], c["confidenceState"], c["confidenceScore"]) for c in supported]
    what_unknown = [q["questionText"] for q in questions if q["researchStatus"] in ("open", "researching")]

    if intake["intakeStatus"] in ("registered", "validated"):
        recommended_next_source = "Continue this intake: run/segment the transcript and begin annotation before starting a new source."
    elif intake["intakeStatus"] in ("review_required",):
        recommended_next_source = "Review the pending claims and unresolved questions from this intake before registering a new one."
    elif intake["intakeStatus"] == "approved" and not questions:
        recommended_next_source = "This source is fully processed with no open questions -- register the next TJR source."
    else:
        recommended_next_source = "Resolve open items on this intake (see ownerReviewItems) before moving to a new source."

    report = {
        "reportId": "TJRREPORT|%s|%s" % (intakeId, now.strftime("%Y%m%dT%H%M%SZ")),
        "intakeId": intakeId, "sourceId": sourceId, "reportSchemaVersion": REPORT_SCHEMA_VERSION,
        "generatedAt": now.strftime("%Y-%m-%dT%H:%M:%SZ"),

        "sourceOverview": {
            "title": intake.get("title"), "traderId": intake.get("traderId"), "sourceType": intake.get("sourceType"),
            "intakeStatus": intake["intakeStatus"], "registeredAt": intake.get("registeredAt"),
        },
        "provenance": {
            "canonicalReference": intake.get("canonicalReference"), "licensingStatus": intake.get("licensingStatus"),
            "contentHash": intake.get("contentHash"),
            "sourceProvenanceStatus": source.get("provenanceStatus") if source else None,
        },
        "transcriptQuality": {
            "transcriptFormat": intake.get("transcriptFormat"), "transcriptCompleteness": intake.get("transcriptCompleteness"),
            "language": intake.get("language"), "warnings": intake.get("warnings", []),
        },
        "extractionStatus": intake["extractionStatus"],
        "segmentsAnalyzed": {"count": len(segments), "segmentIds": [s["segmentId"] for s in segments]},
        "evidenceExtracted": {"count": len(items), "evidenceIds": [i["evidenceId"] for i in items],
                              "annotationCount": len(annotations)},
        "explicitStatements": [_item_summary(i) for i in explicit_statements],
        "demonstratedBehavior": [_item_summary(i) for i in demonstrated_behavior],
        "inferredObservations": [_item_summary(i) for i in inferred_observations],
        "opinionsAndUnsupportedStatements": [_item_summary(i) for i in opinions_unsupported],
        "claimsGenerated": [_claim_summary(c) for c in claims],
        "claimConfidence": {c["claimId"]: {"state": c["confidenceState"], "score": c["confidenceScore"]} for c in claims},
        "contradictions": contradictions,
        "exceptions": [_item_summary(i) for i in exceptions],
        "unresolvedQuestions": questions,
        "ruleCandidates": proposals,
        "missingStrategyComponents": missing_strategy_components,
        "replayHypotheses": [],
        "paperTradingHypotheses": [],
        "whatMogoLearned": what_learned,
        "whatMogoStillDoesNotKnow": what_unknown,
        "recommendedNextSource": recommended_next_source,
        "ownerReviewItems": queue_entries,
        "processingWarnings": intake.get("warnings", []),
        "productionBehaviorChanged": False,
    }
    return report


def render_tjr_report_markdown(report):
    lines = []
    lines.append("# TJR Research Report: %s" % report["intakeId"])
    lines.append("")
    lines.append("_Generated %s. reportSchemaVersion=%d._" % (report["generatedAt"], report["reportSchemaVersion"]))
    lines.append("")
    lines.append("**No production behavior changed while generating this report.**" if not report["productionBehaviorChanged"]
                 else "**WARNING: productionBehaviorChanged=True.**")
    lines.append("")

    def section(title, body_lines):
        lines.append("## %s" % title)
        if body_lines:
            lines.extend(body_lines)
        else:
            lines.append("_None._")
        lines.append("")

    so = report["sourceOverview"]
    section("1. Source Overview", ["- Title: %s" % so.get("title"), "- Trader: %s" % so.get("traderId"),
                                    "- Source type: %s" % so.get("sourceType"), "- Intake status: %s" % so.get("intakeStatus")])
    prov = report["provenance"]
    section("2. Provenance", ["- Canonical reference: %s" % prov.get("canonicalReference"),
                               "- Licensing status: %s" % prov.get("licensingStatus"),
                               "- Source provenance status: %s" % prov.get("sourceProvenanceStatus")])
    tq = report["transcriptQuality"]
    section("3. Transcript Quality", ["- Format: %s" % tq.get("transcriptFormat"),
                                       "- Completeness: %s" % tq.get("transcriptCompleteness"),
                                       "- Warnings: %s" % (", ".join(tq.get("warnings", [])) or "none")])
    section("4. Extraction Status", ["- %s" % report["extractionStatus"]])
    section("5. Segments Analyzed", ["- Count: %d" % report["segmentsAnalyzed"]["count"]])
    section("6. Evidence Extracted", ["- Count: %d (from %d annotations)" % (
        report["evidenceExtracted"]["count"], report["evidenceExtracted"]["annotationCount"])])
    section("7. Explicit Statements", ["- %s: %s" % (i["evidenceId"], i["exactExcerpt"]) for i in report["explicitStatements"]])
    section("8. Demonstrated Behavior", ["- %s: %s" % (i["evidenceId"], i["exactExcerpt"]) for i in report["demonstratedBehavior"]])
    section("9. Inferred Observations", ["- %s: %s" % (i["evidenceId"], i["exactExcerpt"]) for i in report["inferredObservations"]])
    section("10. Opinions and Unsupported Statements", ["- %s: %s" % (i["evidenceId"], i["exactExcerpt"]) for i in report["opinionsAndUnsupportedStatements"]])
    section("11. Claims Generated", ["- %s: %s" % (c["claimId"], c["normalizedClaim"]) for c in report["claimsGenerated"]])
    section("12. Claim Confidence", ["- %s: %s (score=%s)" % (cid, v["state"], v["score"]) for cid, v in report["claimConfidence"].items()])
    section("13. Contradictions", ["- %s: %s vs %s" % (cr["contradictionId"], cr["claimAId"], cr["claimBId"]) for cr in report["contradictions"]])
    section("14. Exceptions", ["- %s: %s" % (i["evidenceId"], i["exactExcerpt"]) for i in report["exceptions"]])
    section("15. Unresolved Questions", ["- [%s] %s" % (q["priority"], q["questionText"]) for q in report["unresolvedQuestions"]])
    section("16. Rule Candidates", ["- %s (claimType=%s, status=%s)" % (p["proposalId"], p["claimType"], p["status"]) for p in report["ruleCandidates"]])
    section("17. Missing Strategy Components", ["- %s" % s for s in report["missingStrategyComponents"]])
    section("18. Replay Hypotheses", report["replayHypotheses"] or None)
    section("19. Paper-Trading Hypotheses", report["paperTradingHypotheses"] or None)
    section("20. What MOGO Learned", ["- %s" % s for s in report["whatMogoLearned"]])
    section("21. What MOGO Still Does Not Know", ["- %s" % s for s in report["whatMogoStillDoesNotKnow"]])
    section("22. Recommended Next Source", [report["recommendedNextSource"]])
    section("23. Owner-Review Items", ["- [%s] %s (%s)" % (e["queueType"], e["entityId"], e["reason"]) for e in report["ownerReviewItems"]])
    section("24. Processing Warnings", ["- %s" % w for w in report["processingWarnings"]])
    section("25. Production Behavior Changed", ["%s" % report["productionBehaviorChanged"]])

    return "\n".join(lines)

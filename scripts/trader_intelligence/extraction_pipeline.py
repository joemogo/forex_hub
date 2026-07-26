#!/usr/bin/env python3
"""PROGRAM-006 Phase 1B (ADR-009, Deliverable 9) -- controlled, offline,
deterministic evidence extraction pipeline.

Pure Python standard library. NO NETWORK ACCESS. NO LLM.

This is explicitly a *controlled framework*, not a semantic interpreter: it
segments an already-locally-supplied transcript and surfaces deterministic,
configured-phrase-based SUGGESTIONS for what a researcher might annotate --
it never creates an EvidenceItem or Claim on its own. Real evidence and
claims only ever come from an approved ManualAnnotation
(annotation_pipeline.apply_annotation), exactly as Deliverable 10/11
require. This keeps a clean seam where a future LLM-assisted suggester could
be swapped in later behind the same suggest_candidate_evidence() contract,
without touching the canonical evidence models at all.
"""
import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import evidence_common as evc              # noqa: E402
import transcript_adapters as ta           # noqa: E402
import intake_registry as ir               # noqa: E402
import evidence_questions as eq            # noqa: E402
import rule_candidate_proposals as rcp     # noqa: E402
import review_queues as rev                # noqa: E402
import query_evidence as qe                # noqa: E402

# Configured lexicons -- deterministic phrase matching only, never NLP.
_RULE_LANGUAGE_MARKERS = ("must ", "always ", "never ", "required", "has to ", "needs to ", "the rule is")
_HEDGE_MARKERS = ("sometimes", "i think", "maybe", "possibly", "in some cases", "it depends", "might ", "kind of")
_EXCEPTION_MARKERS = ("except", "unless", "however", "but in", "exception")


def suggest_candidate_evidence(segment):
    """Deterministic, configured-phrase-based suggestion for one
    TranscriptSegment. Returns a suggestion dict or None -- never persisted,
    never authoritative. A human researcher reviews this and, if they agree,
    creates a real ManualAnnotation (possibly adjusting every field)."""
    text = (segment.get("rawText") or "").lower()
    if any(marker in text for marker in _EXCEPTION_MARKERS):
        return {"segmentId": segment["segmentId"], "matchedMarkerCategory": "exception",
                "suggestedEvidenceType": "exception_statement", "suggestedDirectness": "direct_explicit",
                "suggestedExtractionCertainty": "moderate", "excerpt": segment["rawText"]}
    if any(marker in text for marker in _RULE_LANGUAGE_MARKERS):
        return {"segmentId": segment["segmentId"], "matchedMarkerCategory": "rule_language",
                "suggestedEvidenceType": "explicit_statement", "suggestedDirectness": "direct_explicit",
                "suggestedExtractionCertainty": "high", "excerpt": segment["rawText"]}
    if any(marker in text for marker in _HEDGE_MARKERS):
        return {"segmentId": segment["segmentId"], "matchedMarkerCategory": "hedge",
                "suggestedEvidenceType": "opinion", "suggestedDirectness": "inferred_from_context",
                "suggestedExtractionCertainty": "low", "excerpt": segment["rawText"]}
    return None


def run_intake_extraction_pipeline(evidence_root, intakeId, raw_transcript_content, now=None, actor="pipeline"):
    """Steps 1-6 of Deliverable 9: validate -> segment -> suggest. Never
    creates EvidenceItem/Claim records. Transitions the IntakeManifest's
    status through the extraction lifecycle and always returns a structured
    audit report, whether or not extraction succeeded."""
    now = now or datetime.now(timezone.utc)
    intake_dir = os.path.join(evidence_root, "intake")
    segments_dir = os.path.join(evidence_root, "segments")
    lifecycle_dir = os.path.join(evidence_root, "lifecycle")

    idx = qe.EvidenceIndex.load(evidence_root)
    intake = idx.intakes.get(intakeId)
    if intake is None:
        raise evc.EvidenceValidationError("Cannot run extraction for nonexistent intakeId %r" % (intakeId,))

    warnings = []
    try:
        parsed_segments = ta.parse_transcript(raw_transcript_content, intake["transcriptFormat"])
    except evc.EvidenceValidationError as exc:
        ir.transition_intake_status(intake_dir, lifecycle_dir, intakeId, "failed", actor, now,
                                     reason="Extraction failed during transcript validation.",
                                     failureReason=str(exc), extractionStatus="failed")
        return {"intakeId": intakeId, "status": "failed", "failureReason": str(exc),
                "segmentsCreated": [], "candidateSuggestions": [], "warnings": []}

    if intake["intakeStatus"] == "ready_for_extraction":
        ir.transition_intake_status(intake_dir, lifecycle_dir, intakeId, "extraction_in_progress", actor, now,
                                     reason="Beginning controlled extraction.", extractionStatus="in_progress")

    segment_records = ir.register_transcript_segments(segments_dir, intake_dir, now, intakeId, parsed_segments,
                                                       sourceId=intake.get("sourceId"))
    suggestions = [s for s in (suggest_candidate_evidence(seg) for seg in segment_records) if s]

    ir.transition_intake_status(intake_dir, lifecycle_dir, intakeId, "extracted", actor, now,
                                 reason="Segmentation and candidate-suggestion complete; awaiting annotation review.",
                                 extractionStatus="completed",
                                 extraWarnings=warnings)

    return {
        "intakeId": intakeId, "status": "extracted",
        "segmentsCreated": [s["segmentId"] for s in segment_records],
        "candidateSuggestions": suggestions, "warnings": warnings,
    }


_RULE_ELIGIBLE_CONFIDENCE_STATES = ("supported", "strongly_supported")


def run_post_annotation_pipeline(evidence_root, claimIds, now=None, actor="pipeline"):
    """Steps 10-13 of Deliverable 9, run after one or more ManualAnnotations
    have been applied (real EvidenceItems/Claims now exist): generates
    EvidenceQuestions for each affected claim, auto-proposes a (non-
    executable) RuleCandidateProposal for any claim that is both rule-type-
    eligible and already confidenceState in {supported, strongly_supported},
    rebuilds all 14 review queues, and returns an audit report. Never
    creates/modifies a StrategyRule, never touches index.html."""
    now = now or datetime.now(timezone.utc)
    dirs = {name: os.path.join(evidence_root, name) for name in
            ("sources", "items", "claims", "links", "lifecycle", "contradictions",
             "questions", "proposals", "intake", "review-queue")}

    idx = qe.EvidenceIndex.load(evidence_root)
    all_claims = list(idx.claims.values())
    questions_created = []
    proposals_created = []

    for claim_id in sorted(claimIds):
        claim = idx.claims.get(claim_id)
        if claim is None:
            continue
        links = idx.links_for_claim(claim_id)
        created = eq.generate_questions_for_claim(dirs["questions"], now, claim, links, idx.items, all_claims)
        questions_created.extend(created)

        if claim["claimType"] in evc.RULE_CANDIDATE_ELIGIBLE_CLAIM_TYPES and \
                claim["confidenceState"] in _RULE_ELIGIBLE_CONFIDENCE_STATES:
            already_proposed = any(claim_id in p.get("originatingClaimIds", []) and p["status"] == "proposed"
                                    for p in idx.proposals.values())
            if not already_proposed:
                proposal = rcp.propose_rule_candidate(
                    dirs["proposals"], dirs["claims"], dirs["links"], dirs["items"], dirs["contradictions"],
                    dirs["questions"], now, [claim_id], actor,
                    "Auto-suggested by the controlled extraction pipeline: claimType=%r reached confidenceState=%r." % (
                        claim["claimType"], claim["confidenceState"]))
                proposals_created.append(proposal)

    # Refresh review queues against the now-current state (idempotent: each
    # run appends fresh entries reflecting current findings; nothing is
    # deleted, mirroring the append-only convention used everywhere else).
    queue_results = rev.build_all_review_queues(
        dirs["review-queue"], now, dirs["sources"], dirs["items"], dirs["claims"], dirs["contradictions"],
        dirs["questions"], dirs["proposals"], dirs["intake"])

    return {
        "claimIdsProcessed": sorted(claimIds),
        "questionsCreated": [q["questionId"] for q in questions_created],
        "proposalsCreated": [p["proposalId"] for p in proposals_created],
        "reviewQueueCounts": {k: len(v) for k, v in queue_results.items()},
    }

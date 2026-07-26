#!/usr/bin/env python3
"""PROGRAM-006 Phase 1B (ADR-009, Deliverables 10-11) -- manual annotation
format and claim-candidate generation.

Pure Python standard library. NO NETWORK ACCESS. A ManualAnnotation is the
only sanctioned way for a researcher (human or Claude, per the milestone) to
prepare an import package from a TranscriptSegment without writing directly
to production EvidenceItem/Claim records. Applying an *approved* annotation
is the only path from raw transcript text into the canonical evidence model,
and it never auto-approves the resulting claim.
"""
import glob as globmod
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import graph_common as gc              # noqa: E402
import evidence_common as evc          # noqa: E402
import evidence_registry as reg        # noqa: E402
import evidence_dedup as dedup         # noqa: E402


def _load_all(dir_path, id_field):
    out = {}
    if not os.path.isdir(dir_path):
        return out
    for path in sorted(globmod.glob(os.path.join(dir_path, "*.json"))):
        with open(path, "r", encoding="utf-8") as f:
            record = json.load(f)
        out[record[id_field]] = record
    return out


# ---------------------------------------------------------------------------
# ManualAnnotation (Deliverable 10)
# ---------------------------------------------------------------------------

def register_annotation(annotations_dir, segments_dir, intake_dir, now, intakeId, segmentId,
                         exactExcerpt, evidenceType, directness, extractionCertainty, reviewer,
                         **fields):
    intakes = _load_all(intake_dir, "intakeId")
    if intakeId not in intakes:
        raise evc.EvidenceValidationError("Annotation references nonexistent intakeId %r" % (intakeId,))
    segments = _load_all(segments_dir, "segmentId")
    if segmentId not in segments:
        raise evc.EvidenceValidationError("Annotation references nonexistent segmentId %r" % (segmentId,))
    segment = segments[segmentId]
    if segment["intakeId"] != intakeId:
        raise evc.EvidenceValidationError(
            "segmentId %r belongs to intakeId %r, not %r" % (segmentId, segment["intakeId"], intakeId))
    if evidenceType not in evc.EVIDENCE_TYPES:
        raise evc.EvidenceValidationError("Unknown evidenceType %r" % (evidenceType,))
    if directness not in evc.DIRECTNESS_CLASSIFICATIONS:
        raise evc.EvidenceValidationError("Unknown directness %r" % (directness,))
    if extractionCertainty not in evc.EXTRACTION_CERTAINTY_LEVELS:
        raise evc.EvidenceValidationError("Unknown extractionCertainty %r" % (extractionCertainty,))
    evidenceQuality = fields.get("evidenceQuality", "unknown")
    if evidenceQuality not in evc.EVIDENCE_QUALITIES:
        raise evc.EvidenceValidationError("Unknown evidenceQuality %r" % (evidenceQuality,))
    if not exactExcerpt or not exactExcerpt.strip():
        raise evc.EvidenceValidationError("exactExcerpt must not be empty")
    if exactExcerpt not in segment["rawText"]:
        raise evc.EvidenceValidationError(
            "exactExcerpt is not found verbatim within segment %r's rawText -- annotations must quote "
            "the source exactly, not paraphrase it." % (segmentId,))
    existingClaimId = fields.get("existingClaimId")
    relationshipType = fields.get("relationshipType")
    if existingClaimId and relationshipType and relationshipType not in evc.RELATIONSHIP_TYPES:
        raise evc.EvidenceValidationError("Unknown relationshipType %r" % (relationshipType,))
    claimType = fields.get("claimType")
    if claimType and claimType not in evc.CLAIM_TYPES:
        raise evc.EvidenceValidationError("Unknown claimType %r" % (claimType,))

    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    annotationId = evc.next_annotation_id(annotations_dir, intakeId, now)
    record = {
        "annotationId": annotationId, "intakeId": intakeId, "segmentId": segmentId,
        "exactExcerpt": exactExcerpt, "evidenceType": evidenceType, "directness": directness,
        "extractionCertainty": extractionCertainty, "evidenceQuality": evidenceQuality,
        "normalizedObservation": fields.get("normalizedObservation"),
        "proposedClaim": fields.get("proposedClaim"), "claimType": claimType,
        "relationshipType": relationshipType, "existingClaimId": existingClaimId,
        "traderId": fields.get("traderId"), "strategyFamilyId": fields.get("strategyFamilyId"),
        "timeframe": fields.get("timeframe"), "session": fields.get("session"),
        "marketCondition": fields.get("marketCondition"), "symbol": fields.get("symbol"),
        "entryContext": fields.get("entryContext"), "exitContext": fields.get("exitContext"),
        "riskContext": fields.get("riskContext"), "failureContext": fields.get("failureContext"),
        "successContext": fields.get("successContext"),
        "unresolvedQuestionText": fields.get("unresolvedQuestionText"),
        "notes": fields.get("notes"), "reviewer": reviewer, "reviewStatus": "draft",
        "schemaVersion": evc.SCHEMA_VERSION, "createdAt": now_iso,
    }
    path = os.path.join(annotations_dir, evc.annotation_id_to_filename(annotationId))
    gc.atomic_write_text(path, gc.pretty_json(record))
    return record


def set_annotation_review_status(annotations_dir, annotationId, newStatus, now):
    """Advances an annotation through draft -> submitted -> approved/rejected
    -> applied. Never skips straight to 'applied' except via apply_annotation
    itself, which sets it after successfully creating evidence/claim records."""
    annotations = _load_all(annotations_dir, "annotationId")
    if annotationId not in annotations:
        raise evc.EvidenceValidationError("Cannot update nonexistent annotationId %r" % (annotationId,))
    if newStatus not in evc.ANNOTATION_REVIEW_STATUSES:
        raise evc.EvidenceValidationError("Unknown reviewStatus %r" % (newStatus,))
    record = annotations[annotationId]
    record["reviewStatus"] = newStatus
    path = os.path.join(annotations_dir, evc.annotation_id_to_filename(annotationId))
    gc.atomic_write_text(path, gc.pretty_json(record))
    return record


# ---------------------------------------------------------------------------
# Claim-candidate generation (Deliverable 11)
# ---------------------------------------------------------------------------

def classify_claim_relationship(proposed_normalized, proposed_scope, existing_claims):
    """Deterministically classifies a proposed claim against existing claims:
    returns one of 'exact_duplicate', 'near_duplicate', 'scoped_variant',
    'possible_contradiction', or 'independent', plus the matched claimId (or
    None). Never merges or mutates anything -- purely advisory
    classification consumed by apply_annotation."""
    fingerprint = evc.compute_claim_fingerprint(
        proposed_normalized, proposed_scope.get("traderId"), proposed_scope.get("strategyFamilyId"),
        proposed_scope.get("timeframe"), proposed_scope.get("session"), proposed_scope.get("marketCondition"))
    for claim in existing_claims:
        if claim["normalizedFingerprint"] == fingerprint:
            return "exact_duplicate", claim["claimId"]
    same_text_different_scope = [
        c for c in existing_claims
        if evc.normalize_claim_text(c["normalizedClaim"]) == evc.normalize_claim_text(proposed_normalized)
    ]
    if same_text_different_scope:
        return "scoped_variant", same_text_different_scope[0]["claimId"]
    scope_tuple = (proposed_scope.get("traderId"), proposed_scope.get("strategyFamilyId"),
                   proposed_scope.get("timeframe"), proposed_scope.get("session"), proposed_scope.get("marketCondition"))
    for claim in existing_claims:
        claim_scope = (claim.get("traderId"), claim.get("strategyFamilyId"), claim.get("timeframe"),
                       claim.get("session"), claim.get("marketCondition"))
        if claim_scope != scope_tuple:
            continue
        if evc.is_near_duplicate(proposed_normalized, claim["normalizedClaim"]):
            return "near_duplicate", claim["claimId"]
    return "independent", None


def apply_annotation(annotations_dir, segments_dir, intake_dir, items_dir, sources_dir, claims_dir,
                      links_dir, lifecycle_dir, now, annotationId, actor):
    """The only sanctioned path from an approved ManualAnnotation to a real
    EvidenceItem (+ Claim + EvidenceClaimLink). Requires reviewStatus ==
    'approved' -- draft/submitted/rejected annotations can never be applied.
    The IntakeManifest this annotation belongs to must already have a linked
    sourceId (a real EvidenceSource must exist before evidence can cite it --
    same ordering ADR-008 already requires). Any claim newly created here is
    given claimStatus='pending_review', never 'active', because it originates
    from unreviewed extraction until a human confirms it via the review
    queue (Deliverable 14)."""
    annotations = _load_all(annotations_dir, "annotationId")
    if annotationId not in annotations:
        raise evc.EvidenceValidationError("Cannot apply nonexistent annotationId %r" % (annotationId,))
    annotation = annotations[annotationId]
    if annotation["reviewStatus"] != "approved":
        raise evc.EvidenceValidationError(
            "Annotation %r has reviewStatus=%r; only 'approved' annotations may be applied." % (
                annotationId, annotation["reviewStatus"]))

    intakes = _load_all(intake_dir, "intakeId")
    intake = intakes.get(annotation["intakeId"])
    if intake is None:
        raise evc.EvidenceValidationError("Annotation references nonexistent intakeId %r" % (annotation["intakeId"],))
    if not intake.get("sourceId"):
        raise evc.EvidenceValidationError(
            "IntakeManifest %r has no linked EvidenceSource yet -- register and link a source "
            "(evidence_registry.register_source + intake_registry.link_intake_to_source) before "
            "applying annotations." % (annotation["intakeId"],))

    segments = _load_all(segments_dir, "segmentId")
    segment = segments.get(annotation["segmentId"])
    if segment is None:
        raise evc.EvidenceValidationError("Annotation references nonexistent segmentId %r" % (annotation["segmentId"],))

    item = reg.register_evidence_item(
        items_dir, sources_dir, lifecycle_dir, intake["sourceId"], annotation["evidenceType"],
        annotation.get("evidenceQuality", "unknown"), actor, now, exactExcerpt=annotation["exactExcerpt"],
        normalizedObservation=annotation.get("normalizedObservation"),
        extractionMethod="manual_transcription", directness=annotation["directness"],
        extractionCertainty=annotation["extractionCertainty"],
        sourceLocator=segment["segmentId"], startTimestamp=segment.get("startTimestamp"),
        endTimestamp=segment.get("endTimestamp"), timeframe=annotation.get("timeframe"),
        session=annotation.get("session"), marketCondition=annotation.get("marketCondition"),
        marketSymbol=annotation.get("symbol"),
        metadata={"annotationId": annotationId, "entryContext": annotation.get("entryContext"),
                  "exitContext": annotation.get("exitContext"), "riskContext": annotation.get("riskContext"),
                  "failureContext": annotation.get("failureContext"), "successContext": annotation.get("successContext")},
    )

    claim_id = annotation.get("existingClaimId")
    relationship = annotation.get("relationshipType") or "supports"
    classification = "independent"
    if not claim_id:
        proposed_text = annotation.get("proposedClaim")
        if not proposed_text:
            raise evc.EvidenceValidationError(
                "Annotation %r has neither existingClaimId nor proposedClaim -- nothing to link evidence to." % (annotationId,))
        scope = {"traderId": annotation.get("traderId"), "strategyFamilyId": annotation.get("strategyFamilyId"),
                 "timeframe": annotation.get("timeframe"), "session": annotation.get("session"),
                 "marketCondition": annotation.get("marketCondition")}
        existing_claims = list(_load_all(claims_dir, "claimId").values())
        classification, matched_claim_id = classify_claim_relationship(proposed_text, scope, existing_claims)
        if classification == "exact_duplicate" and matched_claim_id:
            # Only an exact fingerprint match (identical text AND identical
            # scope) is safe to reuse. scoped_variant and near_duplicate are
            # deliberately NOT merged here -- ADR-008/009 require scope to
            # matter and forbid destructive/automatic merges (Deliverable
            # 6/11); matched_claim_id is preserved below only as advisory
            # metadata for a human reviewer.
            claim_id = matched_claim_id
        else:
            claim = reg.register_claim(
                claims_dir, lifecycle_dir, annotation.get("claimType") or "other", proposed_text, actor, now,
                traderId=scope["traderId"], strategyFamilyId=scope["strategyFamilyId"],
                timeframe=scope["timeframe"], session=scope["session"], marketCondition=scope["marketCondition"],
                claimStatus="pending_review",
                possibleDuplicateClaimIds=[matched_claim_id] if matched_claim_id else [])
            claim_id = claim["claimId"]

    link = reg.link_evidence_to_claim(links_dir, items_dir, claims_dir, lifecycle_dir,
                                       item["evidenceId"], claim_id, relationship, actor, now)

    set_annotation_review_status(annotations_dir, annotationId, "applied", now)
    return {"evidenceItem": item, "claimId": claim_id, "link": link, "claimClassification": classification}

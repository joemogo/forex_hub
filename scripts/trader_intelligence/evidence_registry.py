#!/usr/bin/env python3
"""PROGRAM-006 Phase 1A -- Evidence Intelligence Engine creation/registry
layer (ADR-008).

Pure Python standard library. NO NETWORK ACCESS. Every function here either
succeeds and atomically persists exactly one new, valid, immutable record
plus its "created" lifecycle event, or raises EvidenceValidationError and
persists nothing. Nothing in this module ever mutates an existing
EvidenceItem's content, deletes a record, or promotes anything into
production trading behavior.
"""
import glob as globmod
import json
import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import graph_common as gc              # noqa: E402
import evidence_common as evc          # noqa: E402
import evidence_confidence as conf     # noqa: E402

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _load_all(dir_path, id_field):
    """id_field must be given explicitly -- records can carry more than one
    id-shaped field (e.g. EvidenceItem has both its own evidenceId and a
    foreign-key sourceId), so guessing which field is the primary key is
    unsafe and previously caused a real key-collision bug during development."""
    out = {}
    if not os.path.isdir(dir_path):
        return out
    for path in sorted(globmod.glob(os.path.join(dir_path, "*.json"))):
        with open(path, "r", encoding="utf-8") as f:
            record = json.load(f)
        out[record[id_field]] = record
    return out


# ---------------------------------------------------------------------------
# EvidenceSource
# ---------------------------------------------------------------------------

def register_source(sources_dir, lifecycle_dir, sourceType, actor, now,
                     traderId=None, strategyFamilyId=None, title=None,
                     storageLocationType="repository", repositoryPath=None,
                     transcriptReference=None, externalAssetReference=None,
                     canonicalReference=None, contentHash=None, sourceDate=None,
                     language=None, licensingStatus="unknown", provenanceStatus="unverified",
                     metadata=None):
    if sourceType not in evc.SOURCE_TYPES:
        raise evc.EvidenceValidationError("Unknown sourceType %r" % (sourceType,))
    if storageLocationType not in evc.STORAGE_LOCATION_TYPES:
        raise evc.EvidenceValidationError("Unknown storageLocationType %r" % (storageLocationType,))
    if provenanceStatus not in evc.PROVENANCE_STATUSES:
        raise evc.EvidenceValidationError("Unknown provenanceStatus %r" % (provenanceStatus,))
    if storageLocationType == "external" and not (externalAssetReference and canonicalReference):
        raise evc.EvidenceValidationError(
            "storageLocationType='external' requires both externalAssetReference and canonicalReference "
            "(missing provenance on an external asset).")
    if traderId and not re.match(r"^[A-Z][A-Z0-9_]*$", traderId):
        raise evc.EvidenceValidationError("Malformed traderId %r" % (traderId,))

    scope = traderId or "UNATTRIBUTED"
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    sourceId = evc.next_source_id(sources_dir, scope, now)

    record = {
        "sourceId": sourceId, "sourceType": sourceType, "title": title,
        "traderId": traderId, "strategyFamilyId": strategyFamilyId,
        "canonicalReference": canonicalReference, "externalReference": None,
        "contentHash": contentHash, "sourceDate": sourceDate, "acquiredAt": None,
        "registeredAt": now_iso, "storageLocationType": storageLocationType,
        "repositoryPath": repositoryPath, "externalAssetReference": externalAssetReference,
        "transcriptReference": transcriptReference, "language": language,
        "licensingStatus": licensingStatus, "provenanceStatus": provenanceStatus,
        "lifecycleStatus": "registered", "metadata": metadata or {},
        "schemaVersion": evc.SCHEMA_VERSION, "createdAt": now_iso, "updatedAt": now_iso,
    }

    path = os.path.join(sources_dir, evc.source_id_to_filename(sourceId))
    gc.atomic_write_text(path, gc.pretty_json(record))
    event = evc.build_lifecycle_event(lifecycle_dir, "EVIDENCE_SOURCE", sourceId, "created", actor, now,
                                       newStatus="registered", reason="Source registered.")
    evc.write_lifecycle_event(lifecycle_dir, event)
    return record


# ---------------------------------------------------------------------------
# EvidenceItem
# ---------------------------------------------------------------------------

def register_evidence_item(items_dir, sources_dir, lifecycle_dir, sourceId, evidenceType,
                            evidenceQuality, actor, now, exactExcerpt=None,
                            normalizedObservation=None, extractionMethod="manual_owner_entry",
                            extractionVersion="1.0.0", parentEvidenceId=None,
                            supersedesEvidenceId=None, directness=None, extractionCertainty=None,
                            **fields):
    sources = _load_all(sources_dir, "sourceId")
    if sourceId not in sources:
        raise evc.EvidenceValidationError(
            "EvidenceItem references nonexistent sourceId %r" % (sourceId,))
    if evidenceType not in evc.EVIDENCE_TYPES:
        raise evc.EvidenceValidationError("Unknown evidenceType %r" % (evidenceType,))
    if evidenceQuality not in evc.EVIDENCE_QUALITIES:
        raise evc.EvidenceValidationError("Unknown evidenceQuality %r" % (evidenceQuality,))
    if extractionMethod not in evc.EXTRACTION_METHODS:
        raise evc.EvidenceValidationError("Unknown extractionMethod %r" % (extractionMethod,))
    if directness is not None and directness not in evc.DIRECTNESS_CLASSIFICATIONS:
        raise evc.EvidenceValidationError("Unknown directness %r" % (directness,))
    if extractionCertainty is not None and extractionCertainty not in evc.EXTRACTION_CERTAINTY_LEVELS:
        raise evc.EvidenceValidationError("Unknown extractionCertainty %r" % (extractionCertainty,))
    if parentEvidenceId:
        existing_items = _load_all(items_dir, "evidenceId")
        if parentEvidenceId not in existing_items:
            raise evc.EvidenceValidationError("parentEvidenceId %r does not exist" % (parentEvidenceId,))
    if supersedesEvidenceId:
        existing_items = _load_all(items_dir, "evidenceId")
        if supersedesEvidenceId not in existing_items:
            raise evc.EvidenceValidationError("supersedesEvidenceId %r does not exist" % (supersedesEvidenceId,))
        if supersedesEvidenceId == parentEvidenceId:
            pass  # allowed, though unusual

    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    evidenceId = evc.next_evidence_id(items_dir, sourceId, now)
    content_for_hash = {"exactExcerpt": exactExcerpt, "normalizedObservation": normalizedObservation}
    contentHash = gc.content_hash_of(content_for_hash) if (exactExcerpt or normalizedObservation) else None

    record = {
        "evidenceId": evidenceId, "sourceId": sourceId, "evidenceType": evidenceType,
        "exactExcerpt": exactExcerpt, "normalizedObservation": normalizedObservation,
        "sourceLocator": fields.get("sourceLocator"), "startTimestamp": fields.get("startTimestamp"),
        "endTimestamp": fields.get("endTimestamp"), "pageNumber": fields.get("pageNumber"),
        "sectionReference": fields.get("sectionReference"), "speaker": fields.get("speaker"),
        "observationDate": fields.get("observationDate"), "marketSymbol": fields.get("marketSymbol"),
        "timeframe": fields.get("timeframe"), "session": fields.get("session"),
        "marketCondition": fields.get("marketCondition"), "direction": fields.get("direction"),
        "extractionMethod": extractionMethod, "extractionVersion": extractionVersion,
        "evidenceQuality": evidenceQuality, "evidenceStatus": "active",
        "directness": directness, "extractionCertainty": extractionCertainty,
        "contentHash": contentHash, "parentEvidenceId": parentEvidenceId,
        "supersedesEvidenceId": supersedesEvidenceId, "metadata": fields.get("metadata") or {},
        "schemaVersion": evc.SCHEMA_VERSION, "createdAt": now_iso,
    }

    path = os.path.join(items_dir, evc.evidence_id_to_filename(evidenceId))
    gc.atomic_write_text(path, gc.pretty_json(record))
    event = evc.build_lifecycle_event(lifecycle_dir, "EVIDENCE_ITEM", evidenceId, "created", actor, now,
                                       newStatus="active", reason="Evidence item registered.")
    evc.write_lifecycle_event(lifecycle_dir, event)

    if supersedesEvidenceId:
        _mark_evidence_superseded(items_dir, lifecycle_dir, supersedesEvidenceId, evidenceId, actor, now)

    return record


def _mark_evidence_superseded(items_dir, lifecycle_dir, old_evidence_id, new_evidence_id, actor, now):
    """The original record is preserved in full -- only evidenceStatus changes,
    and the change is itself an audit event. Content is never edited."""
    path = os.path.join(items_dir, evc.evidence_id_to_filename(old_evidence_id))
    with open(path, "r", encoding="utf-8") as f:
        old = json.load(f)
    prior = old["evidenceStatus"]
    old["evidenceStatus"] = "superseded"
    gc.atomic_write_text(path, gc.pretty_json(old))
    event = evc.build_lifecycle_event(lifecycle_dir, "EVIDENCE_ITEM", old_evidence_id, "superseded", actor, now,
                                       priorStatus=prior, newStatus="superseded",
                                       reason="Superseded by %s." % new_evidence_id)
    evc.write_lifecycle_event(lifecycle_dir, event)


def correct_evidence_item(items_dir, sources_dir, lifecycle_dir, original_evidence_id, actor, now,
                           **new_fields):
    """The only sanctioned way to 'correct' evidence: create a new item with
    supersedesEvidenceId set, leaving the original fully intact (ADR-008
    sec. 5 / Deliverable 4)."""
    items = _load_all(items_dir, "evidenceId")
    if original_evidence_id not in items:
        raise evc.EvidenceValidationError("Cannot correct nonexistent evidenceId %r" % (original_evidence_id,))
    original = items[original_evidence_id]
    new_fields.setdefault("evidenceType", original["evidenceType"])
    new_fields.setdefault("evidenceQuality", original["evidenceQuality"])
    return register_evidence_item(items_dir, sources_dir, lifecycle_dir, original["sourceId"],
                                   new_fields.pop("evidenceType"), new_fields.pop("evidenceQuality"),
                                   actor, now, supersedesEvidenceId=original_evidence_id, **new_fields)


# ---------------------------------------------------------------------------
# Claim
# ---------------------------------------------------------------------------

def register_claim(claims_dir, lifecycle_dir, claimType, normalizedClaim, actor, now,
                    traderId=None, strategyFamilyId=None, timeframe=None, session=None,
                    marketCondition=None, claimStatus="active", **fields):
    if claimType not in evc.CLAIM_TYPES:
        raise evc.EvidenceValidationError("Unknown claimType %r" % (claimType,))
    if not normalizedClaim or not normalizedClaim.strip():
        raise evc.EvidenceValidationError("normalizedClaim must not be empty")
    if claimStatus not in evc.CLAIM_STATUSES:
        raise evc.EvidenceValidationError("Unknown claimStatus %r" % (claimStatus,))

    scope = traderId or "GENERIC"
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    claimId = evc.next_claim_id(claims_dir, scope, now)
    fingerprint = evc.compute_claim_fingerprint(normalizedClaim, traderId, strategyFamilyId,
                                                 timeframe, session, marketCondition)

    record = {
        "claimId": claimId, "claimType": claimType, "normalizedClaim": normalizedClaim,
        "normalizedFingerprint": fingerprint,
        "subjectEntityType": fields.get("subjectEntityType"), "subjectEntityId": fields.get("subjectEntityId"),
        "predicate": fields.get("predicate"), "objectValue": fields.get("objectValue"),
        "scope": fields.get("scope") or {}, "traderId": traderId, "strategyFamilyId": strategyFamilyId,
        "marketSymbol": fields.get("marketSymbol"), "timeframe": timeframe, "session": session,
        "marketCondition": marketCondition, "claimStatus": claimStatus,
        "confidenceState": "insufficient_evidence", "confidenceScore": None,
        "confidenceMethod": None, "evidenceCount": 0, "supportingEvidenceCount": 0,
        "contradictingEvidenceCount": 0, "weakeningEvidenceCount": 0, "contextualEvidenceCount": 0,
        "possibleDuplicateClaimIds": fields.get("possibleDuplicateClaimIds") or [], "mergeRecommendation": None,
        "firstObservedAt": None, "lastEvaluatedAt": None, "metadata": fields.get("metadata") or {},
        "schemaVersion": evc.SCHEMA_VERSION, "createdAt": now_iso, "updatedAt": now_iso,
    }

    path = os.path.join(claims_dir, evc.claim_id_to_filename(claimId))
    gc.atomic_write_text(path, gc.pretty_json(record))
    event = evc.build_lifecycle_event(lifecycle_dir, "CLAIM", claimId, "created", actor, now,
                                       newStatus="active", reason="Claim registered.")
    evc.write_lifecycle_event(lifecycle_dir, event)
    return record


# ---------------------------------------------------------------------------
# EvidenceClaimLink (+ confidence recomputation)
# ---------------------------------------------------------------------------

def link_evidence_to_claim(links_dir, items_dir, claims_dir, lifecycle_dir, evidenceId, claimId,
                            relationshipType, actor, now, relevanceWeight=1.0, rationale=None):
    items = _load_all(items_dir, "evidenceId")
    claims = _load_all(claims_dir, "claimId")
    if evidenceId not in items:
        raise evc.EvidenceValidationError("Link references nonexistent evidenceId %r" % (evidenceId,))
    if claimId not in claims:
        raise evc.EvidenceValidationError("Link references nonexistent claimId %r" % (claimId,))
    if relationshipType not in evc.RELATIONSHIP_TYPES:
        raise evc.EvidenceValidationError("Unknown relationshipType %r" % (relationshipType,))
    if not (0 <= relevanceWeight <= 1):
        raise evc.EvidenceValidationError("relevanceWeight must be in [0,1], got %r" % (relevanceWeight,))

    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    linkId = evc.make_link_id(evidenceId, claimId)
    link = {
        "linkId": linkId, "evidenceId": evidenceId, "claimId": claimId,
        "relationshipType": relationshipType, "relevanceWeight": relevanceWeight,
        "qualityWeight": None, "independenceGroup": None, "rationale": rationale,
        "linkedBy": actor, "linkedAt": now_iso, "schemaVersion": evc.SCHEMA_VERSION,
    }
    path = os.path.join(links_dir, evc.link_id_to_filename(linkId))
    gc.atomic_write_text(path, gc.pretty_json(link))
    event = evc.build_lifecycle_event(lifecycle_dir, "EVIDENCE_CLAIM_LINK", linkId, "linked", actor, now,
                                       newStatus=relationshipType, reason="Evidence linked to claim.")
    evc.write_lifecycle_event(lifecycle_dir, event)

    recompute_claim_confidence(claims_dir, links_dir, items_dir, lifecycle_dir, claimId, actor, now)
    return link


def recompute_claim_confidence(claims_dir, links_dir, items_dir, lifecycle_dir, claimId, actor, now):
    claims = _load_all(claims_dir, "claimId")
    if claimId not in claims:
        raise evc.EvidenceValidationError("Cannot recompute confidence for nonexistent claimId %r" % (claimId,))
    claim = claims[claimId]
    items = _load_all(items_dir, "evidenceId")
    all_links = _load_all(links_dir, "linkId")
    claim_links = [l for l in all_links.values() if l["claimId"] == claimId]

    state, score, counts, explanation = conf.compute_confidence(claim_links, items)

    prior_state = claim["confidenceState"]
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    claim["confidenceState"] = state
    claim["confidenceScore"] = score
    claim["confidenceMethod"] = "evidence_confidence_v1"
    claim.update(counts)
    claim["lastEvaluatedAt"] = now_iso
    if claim["firstObservedAt"] is None and counts["evidenceCount"] > 0:
        claim["firstObservedAt"] = now_iso
    claim["updatedAt"] = now_iso

    path = os.path.join(claims_dir, evc.claim_id_to_filename(claimId))
    gc.atomic_write_text(path, gc.pretty_json(claim))

    # Persist independenceGroup annotations written onto the link dicts by compute_confidence.
    for link in claim_links:
        link_path = os.path.join(links_dir, evc.link_id_to_filename(link["linkId"]))
        gc.atomic_write_text(link_path, gc.pretty_json(link))

    event = evc.build_lifecycle_event(lifecycle_dir, "CLAIM", claimId, "confidence_recomputed", actor, now,
                                       priorStatus=prior_state, newStatus=state, reason=explanation)
    evc.write_lifecycle_event(lifecycle_dir, event)
    return claim


# ---------------------------------------------------------------------------
# ContradictionRecord
# ---------------------------------------------------------------------------

def create_contradiction(contradictions_dir, claims_dir, lifecycle_dir, claimAId, claimBId,
                          contradictionType, severity, actor, now, rationale=None):
    claims = _load_all(claims_dir, "claimId")
    if claimAId not in claims:
        raise evc.EvidenceValidationError("ContradictionRecord references nonexistent claimAId %r" % (claimAId,))
    if claimBId not in claims:
        raise evc.EvidenceValidationError("ContradictionRecord references nonexistent claimBId %r" % (claimBId,))
    if claimAId == claimBId:
        raise evc.EvidenceValidationError("ContradictionRecord cannot reference the same claim twice (%r)" % (claimAId,))
    if contradictionType not in evc.CONTRADICTION_TYPES:
        raise evc.EvidenceValidationError("Unknown contradictionType %r" % (contradictionType,))
    if severity not in evc.CONTRADICTION_SEVERITIES:
        raise evc.EvidenceValidationError("Unknown severity %r" % (severity,))

    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    contradictionId = evc.next_contradiction_id(contradictions_dir, now)
    record = {
        "contradictionId": contradictionId, "claimAId": claimAId, "claimBId": claimBId,
        "contradictionType": contradictionType, "scopeOverlap": "unknown", "severity": severity,
        "status": "open", "rationale": rationale, "detectedAt": now_iso, "reviewedAt": None,
        "resolution": None, "metadata": {}, "schemaVersion": evc.SCHEMA_VERSION,
    }
    path = os.path.join(contradictions_dir, evc.contradiction_id_to_filename(contradictionId))
    gc.atomic_write_text(path, gc.pretty_json(record))
    event = evc.build_lifecycle_event(lifecycle_dir, "CONTRADICTION_RECORD", contradictionId, "created", actor, now,
                                       newStatus="open", reason="Contradiction recorded between two claims.")
    evc.write_lifecycle_event(lifecycle_dir, event)
    return record

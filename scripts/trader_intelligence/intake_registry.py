#!/usr/bin/env python3
"""PROGRAM-006 Phase 1B (ADR-009) -- TJR-first (but generic) intake registry.

Pure Python standard library. NO NETWORK ACCESS. Registers IntakeManifest and
TranscriptSegment records and manages the intake status lifecycle. Never
downloads, fetches, or scrapes anything -- every transcript this module ever
sees was already supplied locally by the caller.
"""
import glob as globmod
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import graph_common as gc              # noqa: E402
import evidence_common as evc          # noqa: E402

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


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
# IntakeManifest
# ---------------------------------------------------------------------------

ALLOWED_INTAKE_TRANSITIONS = {
    "registered": {"validated", "duplicate", "rejected", "blocked"},
    "validated": {"ready_for_extraction", "rejected", "blocked"},
    "ready_for_extraction": {"extraction_in_progress", "blocked"},
    "extraction_in_progress": {"extracted", "failed", "blocked"},
    "extracted": {"review_required", "blocked"},
    "review_required": {"approved", "rejected", "blocked"},
    "approved": {"superseded"},
    "blocked": {"validated", "ready_for_extraction", "extraction_in_progress", "extracted",
                "review_required", "rejected"},
    "failed": {"validated"},
    "rejected": set(),
    "duplicate": set(),
    "superseded": set(),
}


def register_intake_manifest(intake_dir, lifecycle_dir, sourceType, actor, now,
                              traderId=None, strategyFamilyId=None, title=None,
                              canonicalReference=None, externalReference=None,
                              repositoryPath=None, transcriptPath=None, originalMediaReference=None,
                              sourceDate=None, language=None, transcriptFormat=None,
                              transcriptProvider=None, transcriptCompleteness="unknown",
                              licensingStatus="unknown", contentHash=None, sourceMetadata=None,
                              expectedTopics=None):
    if sourceType not in evc.SOURCE_TYPES:
        raise evc.EvidenceValidationError("Unknown sourceType %r" % (sourceType,))
    if transcriptFormat is not None and transcriptFormat not in evc.TRANSCRIPT_FORMATS:
        raise evc.EvidenceValidationError("Unknown transcriptFormat %r" % (transcriptFormat,))
    if transcriptCompleteness not in ("unknown", "complete", "partial"):
        raise evc.EvidenceValidationError("Unknown transcriptCompleteness %r" % (transcriptCompleteness,))
    if traderId and not re.match(r"^[A-Z][A-Z0-9_]*$", traderId):
        raise evc.EvidenceValidationError("Malformed traderId %r" % (traderId,))

    scope = traderId or "UNATTRIBUTED"
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    intakeId = evc.next_intake_id(intake_dir, scope, now)

    record = {
        "intakeId": intakeId, "sourceId": None, "traderId": traderId,
        "strategyFamilyId": strategyFamilyId, "title": title, "sourceType": sourceType,
        "canonicalReference": canonicalReference, "externalReference": externalReference,
        "repositoryPath": repositoryPath, "transcriptPath": transcriptPath,
        "originalMediaReference": originalMediaReference, "sourceDate": sourceDate,
        "acquiredAt": None, "registeredAt": now_iso, "language": language,
        "transcriptFormat": transcriptFormat, "transcriptProvider": transcriptProvider,
        "transcriptCompleteness": transcriptCompleteness, "licensingStatus": licensingStatus,
        "contentHash": contentHash, "sourceMetadata": sourceMetadata or {},
        "expectedTopics": expectedTopics or [], "intakeStatus": "registered",
        "extractionStatus": "not_started", "reviewStatus": "pending",
        "duplicateStatus": "unknown", "supersessionStatus": "none", "supersedesIntakeId": None,
        "failureReason": None, "warnings": [], "schemaVersion": evc.SCHEMA_VERSION,
        "createdAt": now_iso, "updatedAt": now_iso,
    }
    path = os.path.join(intake_dir, evc.intake_id_to_filename(intakeId))
    gc.atomic_write_text(path, gc.pretty_json(record))
    event = evc.build_lifecycle_event(lifecycle_dir, "INTAKE_MANIFEST", intakeId, "created", actor, now,
                                       newStatus="registered", reason="Intake manifest registered.")
    evc.write_lifecycle_event(lifecycle_dir, event)
    return record


def transition_intake_status(intake_dir, lifecycle_dir, intakeId, newStatus, actor, now,
                              reason=None, failureReason=None, extraWarnings=None, extractionStatus=None):
    """The only sanctioned way to change intakeStatus. Never erases history --
    every transition appends a lifecycle event; the prior status is preserved
    in that event even though the manifest record itself only shows the
    current status (its own full history is reconstructable from
    lifecycle/*.json, exactly like EvidenceItem/Claim)."""
    intakes = _load_all(intake_dir, "intakeId")
    if intakeId not in intakes:
        raise evc.EvidenceValidationError("Cannot transition nonexistent intakeId %r" % (intakeId,))
    if newStatus not in evc.INTAKE_STATUSES:
        raise evc.EvidenceValidationError("Unknown intakeStatus %r" % (newStatus,))
    record = intakes[intakeId]
    prior = record["intakeStatus"]
    allowed = ALLOWED_INTAKE_TRANSITIONS.get(prior, set())
    if newStatus not in allowed:
        raise evc.EvidenceValidationError(
            "Illegal intake status transition %r -> %r (allowed from %r: %r)" % (prior, newStatus, prior, sorted(allowed)))

    if extractionStatus is not None and extractionStatus not in evc.INTAKE_EXTRACTION_STATUSES:
        raise evc.EvidenceValidationError("Unknown extractionStatus %r" % (extractionStatus,))

    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    record["intakeStatus"] = newStatus
    record["updatedAt"] = now_iso
    if failureReason is not None:
        record["failureReason"] = failureReason
    if extraWarnings:
        record["warnings"] = list(record.get("warnings", [])) + list(extraWarnings)
    if extractionStatus is not None:
        record["extractionStatus"] = extractionStatus

    path = os.path.join(intake_dir, evc.intake_id_to_filename(intakeId))
    gc.atomic_write_text(path, gc.pretty_json(record))
    event = evc.build_lifecycle_event(lifecycle_dir, "INTAKE_MANIFEST", intakeId, "status_changed", actor, now,
                                       priorStatus=prior, newStatus=newStatus,
                                       reason=reason or ("Transitioned %s -> %s." % (prior, newStatus)))
    evc.write_lifecycle_event(lifecycle_dir, event)
    return record


def link_intake_to_source(intake_dir, lifecycle_dir, intakeId, sourceId, actor, now):
    """Populates IntakeManifest.sourceId once a real EvidenceSource has been
    registered for it (evidence_registry.register_source), without changing
    intakeStatus -- that is a separate, explicit transition."""
    intakes = _load_all(intake_dir, "intakeId")
    if intakeId not in intakes:
        raise evc.EvidenceValidationError("Cannot link nonexistent intakeId %r" % (intakeId,))
    record = intakes[intakeId]
    record["sourceId"] = sourceId
    record["updatedAt"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    path = os.path.join(intake_dir, evc.intake_id_to_filename(intakeId))
    gc.atomic_write_text(path, gc.pretty_json(record))
    event = evc.build_lifecycle_event(lifecycle_dir, "INTAKE_MANIFEST", intakeId, "other", actor, now,
                                       reason="Linked to EvidenceSource %s." % sourceId)
    evc.write_lifecycle_event(lifecycle_dir, event)
    return record


# ---------------------------------------------------------------------------
# TranscriptSegment
# ---------------------------------------------------------------------------

def register_transcript_segments(segments_dir, intake_dir, now, intakeId, parsed_segments,
                                  sourceId=None, segment_types=None):
    """parsed_segments: list of dicts as produced by transcript_adapters.py
    (sequenceNumber, speaker, startTimestamp, endTimestamp, lineStart, lineEnd,
    sectionTitle, rawText, language). segment_types: optional dict mapping
    sequenceNumber -> segmentType (defaults to 'other' for any segment not
    named). Writes one TranscriptSegment record per parsed segment and
    returns them in sequence order."""
    intakes = _load_all(intake_dir, "intakeId")
    if intakeId not in intakes:
        raise evc.EvidenceValidationError("Cannot register segments for nonexistent intakeId %r" % (intakeId,))
    segment_types = segment_types or {}

    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    records = []
    for parsed in parsed_segments:
        segType = segment_types.get(parsed["sequenceNumber"], "other")
        if segType not in evc.SEGMENT_TYPES:
            raise evc.EvidenceValidationError("Unknown segmentType %r" % (segType,))
        segmentId = evc.next_segment_id(segments_dir, intakeId, now)
        record = {
            "segmentId": segmentId, "intakeId": intakeId, "sourceId": sourceId,
            "sequenceNumber": parsed["sequenceNumber"], "speaker": parsed.get("speaker"),
            "startTimestamp": parsed.get("startTimestamp"), "endTimestamp": parsed.get("endTimestamp"),
            "lineStart": parsed.get("lineStart"), "lineEnd": parsed.get("lineEnd"),
            "sectionTitle": parsed.get("sectionTitle"), "rawText": parsed["rawText"],
            "normalizedText": None, "textHash": evc.text_sha256(parsed["rawText"]),
            "language": parsed.get("language"), "segmentType": segType, "metadata": {},
            "schemaVersion": evc.SCHEMA_VERSION, "createdAt": now_iso,
        }
        path = os.path.join(segments_dir, evc.segment_id_to_filename(segmentId))
        gc.atomic_write_text(path, gc.pretty_json(record))
        records.append(record)
    return records

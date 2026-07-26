#!/usr/bin/env python3
"""PROGRAM-006 Phase 1B (ADR-009, Deliverable 14) -- deterministic review
queues.

Pure Python standard library. NO NETWORK ACCESS. Every queue-building
function here is read-only against already-stored records; resolving an
entry (review_queues.set_entry_review_status) only ever changes the entry
itself, never the entity it points at, and never any production behavior.
"""
import glob as globmod
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import graph_common as gc          # noqa: E402
import evidence_common as evc      # noqa: E402
import evidence_dedup as dedup     # noqa: E402


def _load_all(dir_path, id_field):
    out = {}
    if not os.path.isdir(dir_path):
        return out
    for path in sorted(globmod.glob(os.path.join(dir_path, "*.json"))):
        with open(path, "r", encoding="utf-8") as f:
            record = json.load(f)
        out[record[id_field]] = record
    return out


def _make_entry(queue_dir, now, entityType, entityId, queueType, priority, reason, blockingStatus="non_blocking"):
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    queueEntryId = evc.next_queue_entry_id(queue_dir, queueType, now)
    record = {
        "queueEntryId": queueEntryId, "entityType": entityType, "entityId": entityId,
        "queueType": queueType, "priority": priority, "reason": reason, "blockingStatus": blockingStatus,
        "createdAt": now_iso, "updatedAt": now_iso, "reviewStatus": "open", "reviewer": None,
        "resolution": None, "metadata": {}, "schemaVersion": evc.SCHEMA_VERSION,
    }
    path = os.path.join(queue_dir, evc.queue_entry_id_to_filename(queueEntryId))
    gc.atomic_write_text(path, gc.pretty_json(record))
    return record


def _detect_low_certainty_evidence(items):
    return sorted(
        [("EVIDENCE_ITEM", i["evidenceId"], "medium", "extractionCertainty='low'.")
         for i in items.values() if i.get("extractionCertainty") == "low"],
        key=lambda t: t[1])


def _detect_ambiguous_evidence(items):
    return sorted(
        [("EVIDENCE_ITEM", i["evidenceId"], "high", "extractionCertainty=%r." % i.get("extractionCertainty"))
         for i in items.values() if i.get("extractionCertainty") in ("ambiguous", "unresolved")],
        key=lambda t: t[1])


def _detect_inferred_evidence(items):
    return sorted(
        [("EVIDENCE_ITEM", i["evidenceId"], "low", "directness=%r (not a direct statement/observation)." % i.get("directness"))
         for i in items.values() if i.get("directness") in ("inferred_from_context", "derived_from_analysis")],
        key=lambda t: t[1])


def _detect_duplicate_candidates(claims):
    claim_list = list(claims.values())
    entries = []
    for group in dedup.find_exact_duplicate_groups(claim_list):
        for cid in sorted(group):
            entries.append(("CLAIM", cid, "medium", "Exact-duplicate fingerprint shared with %r." % [c for c in group if c != cid]))
    for cand in dedup.find_near_duplicate_candidates(claim_list):
        entries.append(("CLAIM", cand["claimAId"], "low",
                         "Near-duplicate candidate with %s (similarity=%.2f)." % (cand["claimBId"], cand["similarity_ratio"])))
    return sorted(entries, key=lambda t: t[1])


def _detect_contradiction_candidates(contradictions):
    return sorted(
        [("CONTRADICTION_RECORD", cr["contradictionId"], "high", "status='open'.")
         for cr in contradictions.values() if cr["status"] == "open"],
        key=lambda t: t[1])


def _detect_contested_claims(claims):
    return sorted(
        [("CLAIM", c["claimId"], "high", "confidenceState='contested'.")
         for c in claims.values() if c["confidenceState"] == "contested"],
        key=lambda t: t[1])


def _detect_unresolved_questions(questions):
    return sorted(
        [("EVIDENCE_QUESTION", q["questionId"], q["priority"], "researchStatus=%r." % q["researchStatus"])
         for q in questions.values() if q["researchStatus"] in ("open", "researching")],
        key=lambda t: t[1])


def _detect_rule_candidates(proposals):
    return sorted(
        [("RULE_CANDIDATE_PROPOSAL", p["proposalId"], "medium", "status='proposed', awaiting owner review.")
         for p in proposals.values() if p["status"] == "proposed" and p["ownerReviewStatus"] == "not_reviewed"],
        key=lambda t: t[1])


def _detect_incomplete_transcripts(intakes):
    return sorted(
        [("INTAKE_MANIFEST", m["intakeId"], "medium", "transcriptCompleteness=%r." % m["transcriptCompleteness"])
         for m in intakes.values() if m.get("transcriptCompleteness") in ("partial", "unknown")
         and m["intakeStatus"] not in ("rejected", "duplicate", "superseded")],
        key=lambda t: t[1])


def _detect_unresolved_licensing(intakes):
    return sorted(
        [("INTAKE_MANIFEST", m["intakeId"], "critical", "licensingStatus=%r." % m["licensingStatus"])
         for m in intakes.values() if m.get("licensingStatus") in ("unknown", "restricted_third_party")
         and m["intakeStatus"] not in ("rejected", "duplicate", "superseded")],
        key=lambda t: t[1])


def _detect_missing_provenance(sources):
    return sorted(
        [("EVIDENCE_SOURCE", s["sourceId"], "medium", "provenanceStatus='unverified'.")
         for s in sources.values() if s.get("provenanceStatus") == "unverified"],
        key=lambda t: t[1])


def _detect_insufficient_independent_evidence(claims):
    return sorted(
        [("CLAIM", c["claimId"], "low", "confidenceState=%r." % c["confidenceState"])
         for c in claims.values() if c["confidenceState"] in ("insufficient_evidence", "tentative")],
        key=lambda t: t[1])


def _detect_supersession_review(items):
    return sorted(
        [("EVIDENCE_ITEM", i["evidenceId"], "low", "This item supersedes %r -- confirm the correction was applied for the right reason." % i["supersedesEvidenceId"])
         for i in items.values() if i.get("supersedesEvidenceId")],
        key=lambda t: t[1])


def _detect_extraction_failures(intakes):
    return sorted(
        [("INTAKE_MANIFEST", m["intakeId"], "high", "extractionStatus=%r%s." % (
            m["extractionStatus"], (" (%s)" % m["failureReason"]) if m.get("failureReason") else ""))
         for m in intakes.values() if m["extractionStatus"] == "failed" or m["intakeStatus"] == "failed"],
        key=lambda t: t[1])


_QUEUE_BUILDERS = {
    "low_certainty_evidence": ("items", _detect_low_certainty_evidence),
    "ambiguous_evidence": ("items", _detect_ambiguous_evidence),
    "inferred_evidence": ("items", _detect_inferred_evidence),
    "duplicate_candidates": ("claims", _detect_duplicate_candidates),
    "contradiction_candidates": ("contradictions", _detect_contradiction_candidates),
    "contested_claims": ("claims", _detect_contested_claims),
    "unresolved_questions": ("questions", _detect_unresolved_questions),
    "rule_candidates": ("proposals", _detect_rule_candidates),
    "incomplete_transcripts": ("intakes", _detect_incomplete_transcripts),
    "unresolved_licensing": ("intakes", _detect_unresolved_licensing),
    "missing_provenance": ("sources", _detect_missing_provenance),
    "insufficient_independent_evidence": ("claims", _detect_insufficient_independent_evidence),
    "supersession_review": ("items", _detect_supersession_review),
    "extraction_failures": ("intakes", _detect_extraction_failures),
}


def build_all_review_queues(queue_dir, now, sources_dir, items_dir, claims_dir, contradictions_dir,
                             questions_dir, proposals_dir, intake_dir):
    """Loads current state once, deterministically computes every one of the
    14 required queues, persists a ReviewQueueEntry per finding, and returns
    {queueType: [entries]}. Never mutates any source record."""
    data = {
        "sources": _load_all(sources_dir, "sourceId"), "items": _load_all(items_dir, "evidenceId"),
        "claims": _load_all(claims_dir, "claimId"), "contradictions": _load_all(contradictions_dir, "contradictionId"),
        "questions": _load_all(questions_dir, "questionId"), "proposals": _load_all(proposals_dir, "proposalId"),
        "intakes": _load_all(intake_dir, "intakeId"),
    }
    results = {}
    for queueType in evc.REVIEW_QUEUE_TYPES:
        dataset_name, builder = _QUEUE_BUILDERS[queueType]
        findings = builder(data[dataset_name])
        entries = [_make_entry(queue_dir, now, entityType, entityId, queueType, priority, reason)
                   for entityType, entityId, priority, reason in findings]
        results[queueType] = entries
    return results


def set_entry_review_status(queue_dir, queueEntryId, newStatus, now, reviewer=None, resolution=None):
    entries = _load_all(queue_dir, "queueEntryId")
    if queueEntryId not in entries:
        raise evc.EvidenceValidationError("Cannot update nonexistent queueEntryId %r" % (queueEntryId,))
    if newStatus not in evc.REVIEW_QUEUE_REVIEW_STATUSES:
        raise evc.EvidenceValidationError("Unknown reviewStatus %r" % (newStatus,))
    record = entries[queueEntryId]
    record["reviewStatus"] = newStatus
    record["updatedAt"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    if reviewer is not None:
        record["reviewer"] = reviewer
    if resolution is not None:
        record["resolution"] = resolution
    path = os.path.join(queue_dir, evc.queue_entry_id_to_filename(queueEntryId))
    gc.atomic_write_text(path, gc.pretty_json(record))
    return record

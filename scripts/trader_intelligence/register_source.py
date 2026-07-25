#!/usr/bin/env python3
"""PROGRAM-004 Phase 1 -- offline research-candidate registration.

Pure Python standard library. NO NETWORK ACCESS. Registers exactly one
ResearchSourceCandidate per invocation from a URL, uploaded text, or an
owner note. DISCOVERED is transient (in-memory, pre-validation); nothing is
written to disk unless validation succeeds, at which point the candidate is
persisted as REGISTERED -- and that DISCOVERED -> REGISTERED transition is
itself recorded as the first changeLog entry (PROGRAM-004 Correction 2), via
acquisition_common.advance_status().

Content-origin and storage-policy defaults (PROGRAM-004 Correction 1):
supplying or pasting text never by itself establishes that the owner
authored it or approved committing the full text to git. COMMITTED_OWNER_CONTENT
is only ever auto-selected for discoveryMethod=OWNER_NOTE; every other
discovery method defaults to REFERENCED_LOCAL_CONTENT (when a controlled
local file exists) or METADATA_ONLY, and committing full text requires an
explicit storage_policy argument, which is then recorded in
provenance.explicitStoragePolicySelection.
"""
import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import graph_common as gc          # noqa: E402
import acquisition_common as ac    # noqa: E402

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


class RegistrationError(ValueError):
    """Raised whenever discovery occurred but durable registration failed --
    no candidate file is ever written when this is raised. discovery_event
    lets a caller report that discovery happened without a persisted,
    possibly-invalid production candidate record (PROGRAM-004 Correction 2)."""

    def __init__(self, message, discovery_event=None):
        super().__init__(message)
        self.discovery_event = discovery_event or {}


def _discovery_event(discovery_method, now, submitted_by, reason):
    return {
        "priorStatus": "DISCOVERED", "newStatus": None,  # registration never completed
        "discoveryMethod": discovery_method, "discoveredAt": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "actor": submitted_by, "reason": reason,
    }


def register_candidate(candidates_dir, ti_root, discovery_method, submitted_by, now,
                        url=None, title=None, creator_name=None, claimed_trader_id=None,
                        description=None, language=None, text_content=None,
                        local_file_path=None, uploads_root=None, storage_policy=None,
                        content_origin=None, source_type_override=None):
    """Validates and, on success, atomically writes one new candidate JSON
    file. Raises RegistrationError (never writes anything) on any failure --
    this is the DISCOVERED->REGISTERED boundary."""
    if discovery_method not in ac.DISCOVERY_METHODS:
        raise RegistrationError("Unknown discoveryMethod %r" % (discovery_method,),
                                 _discovery_event(discovery_method, now, submitted_by, "unknown discoveryMethod"))

    url_norm = None
    platform = "UNKNOWN"
    playlist_id = None
    source_type_hint = None

    if discovery_method in ac.URL_REQUIRED_DISCOVERY_METHODS:
        if not url:
            raise RegistrationError(
                "discoveryMethod %r requires a url" % (discovery_method,),
                _discovery_event(discovery_method, now, submitted_by, "missing required url"))
        url_norm = ac.normalize_url(url)
        platform = url_norm["platform"]
        playlist_id = url_norm["playlistId"]
        source_type_hint = url_norm["sourceTypeHint"]
        forced = {
            "PLAYLIST_URL": "PLAYLIST", "CHANNEL_URL": "CHANNEL",
            "SEARCH_RESULTS_URL": "SEARCH_RESULTS_PAGE", "ARTICLE_URL": "ARTICLE",
        }
        if discovery_method in forced:
            source_type_hint = forced[discovery_method]
        normalized_url = url_norm["normalizedUrl"]
    else:
        normalized_url = None
        platform = {"UPLOADED_TEXT": "LOCAL_UPLOAD", "PDF_REFERENCE": "LOCAL_UPLOAD",
                    "OWNER_NOTE": "OWNER_NOTE"}[discovery_method]
        source_type_hint = {"UPLOADED_TEXT": "TRANSCRIPT", "PDF_REFERENCE": "COURSE_MATERIAL",
                             "OWNER_NOTE": "USER_NOTE"}[discovery_method]

    source_type = source_type_override or source_type_hint

    content_reference = None
    content_hash = None
    content_size_bytes = None
    content_type = None
    explicit_storage_selection = storage_policy is not None
    resolved_storage_policy = storage_policy  # None means "not yet resolved -- apply narrow defaults below"
    resolved_content_origin = content_origin  # None means "not yet resolved -- apply narrow defaults below"

    if text_content is not None:
        encoded = text_content.encode("utf-8")
        if len(encoded) > ac.MAX_TEXT_SIZE_BYTES:
            raise RegistrationError(
                "Text content exceeds MAX_TEXT_SIZE_BYTES (%d > %d)" % (len(encoded), ac.MAX_TEXT_SIZE_BYTES),
                _discovery_event(discovery_method, now, submitted_by, "oversized text content"))
        content_hash = hashlib.sha256(encoded).hexdigest()
        content_size_bytes = len(encoded)
        content_type = "text/plain"
        if resolved_storage_policy is None:
            # COMMITTED_OWNER_CONTENT is only ever a narrow default for an
            # owner-authored note. Every other method defaults to
            # METADATA_ONLY -- a contentHash is still computed above so exact
            # content-hash duplicate detection keeps working even though the
            # full text is never written under docs/trader-intelligence/.
            resolved_storage_policy = "COMMITTED_OWNER_CONTENT" if discovery_method == "OWNER_NOTE" else "METADATA_ONLY"
        if resolved_content_origin is None:
            resolved_content_origin = "OWNER_AUTHORED" if discovery_method == "OWNER_NOTE" else "THIRD_PARTY_OWNER_PROVIDED"

    if local_file_path is not None:
        if uploads_root is None:
            raise RegistrationError(
                "uploads_root is required when local_file_path is provided",
                _discovery_event(discovery_method, now, submitted_by, "missing uploads_root"))
        resolved_path = ac.validate_local_reference(local_file_path, uploads_root)
        with open(resolved_path, "rb") as f:
            data = f.read()
        content_hash = hashlib.sha256(data).hexdigest()
        content_size_bytes = len(data)
        content_type = "application/pdf" if resolved_path.lower().endswith(".pdf") else "text/plain"
        content_reference = os.path.relpath(resolved_path, uploads_root)
        if resolved_storage_policy is None:
            resolved_storage_policy = "REFERENCED_LOCAL_CONTENT"
        if resolved_content_origin is None:
            resolved_content_origin = "THIRD_PARTY_OWNER_PROVIDED"

    if resolved_storage_policy is None:
        resolved_storage_policy = "METADATA_ONLY"
    if resolved_content_origin is None:
        resolved_content_origin = "UNKNOWN_ORIGIN"

    if resolved_storage_policy == "COMMITTED_OWNER_CONTENT" and discovery_method != "OWNER_NOTE" and not explicit_storage_selection:
        # Defensive: this should be unreachable given the defaulting logic
        # above, but never silently commit third-party content to git.
        raise RegistrationError(
            "COMMITTED_OWNER_CONTENT for discoveryMethod=%r requires an explicit storage_policy selection" % (
                discovery_method,),
            _discovery_event(discovery_method, now, submitted_by, "inferred commit of non-owner-note content blocked"))

    if resolved_storage_policy != "METADATA_ONLY" and content_hash is None:
        raise RegistrationError(
            "storagePolicy %r requires content (text_content or local_file_path)" % (resolved_storage_policy,),
            _discovery_event(discovery_method, now, submitted_by, "storage policy set with no content"))

    metadata_confidence = "owner_provided" if (title or creator_name or description) else "unverified"
    authenticity_status = ac.assess_authenticity_heuristic(creator_name, claimed_trader_id, ti_root)
    assert authenticity_status in ac.HEURISTIC_ALLOWED_AUTHENTICITY

    topic_candidates = ac.classify_topics(title, description, text_content, now)

    candidate_id = ac.next_candidate_id(candidates_dir, now)
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    provenance = {"registeredVia": "register_source.py"}
    if explicit_storage_selection:
        provenance["explicitStoragePolicySelection"] = True
        provenance["explicitStoragePolicyValue"] = resolved_storage_policy

    candidate = {
        "candidateId": candidate_id,
        "submittedBy": submitted_by,
        "discoveryMethod": discovery_method,
        "discoveredAt": now_iso,
        "url": url,
        "normalizedUrl": normalized_url,
        "platform": platform,
        "sourceType": source_type,
        "title": title,
        "creatorName": creator_name,
        "claimedTraderId": claimed_trader_id,
        "verifiedTraderId": None,
        "channelOrPublisher": creator_name,
        "publicationDate": None,
        "durationSeconds": None,
        "playlistId": playlist_id,
        "playlistPosition": None,
        "language": language,
        "description": description,
        "metadataConfidence": metadata_confidence,
        "authenticityStatus": authenticity_status,
        "acquisitionStatus": "DISCOVERED",  # advanced to REGISTERED immediately below
        "processingStatus": "registered",
        "priorityAssessments": [],
        "duplicateStatus": "NONE",
        "canonicalCandidateId": None,
        "relatedCandidateIds": [],
        "topicCandidates": topic_candidates,
        "strategyFamilyCandidates": [],
        "ownerReviewStatus": "not_reviewed",
        "ownerDecisionIds": [],
        "rejectionReason": None,
        "provenance": provenance,
        "storagePolicy": resolved_storage_policy,
        "contentOrigin": resolved_content_origin,
        "contentReference": content_reference,
        "contentHash": content_hash,
        "contentSizeBytes": content_size_bytes,
        "contentType": content_type,
        "changeLog": [],
        "createdAt": now_iso,
        "updatedAt": now_iso,
    }

    ac.advance_status(candidate, "REGISTERED", now,
                       "Candidate successfully validated and durably registered.", actor=submitted_by)

    next_status = "METADATA_VERIFIED" if title else "METADATA_PENDING"
    ac.advance_status(candidate, next_status, now, "Phase 1 has no async metadata fetch -- "
                       "whatever metadata was provided at registration is all that will ever be known "
                       "without a future connector.", actor=submitted_by)
    candidate["processingStatus"] = "metadata_processed"

    out_path = os.path.join(candidates_dir, ac.candidate_id_to_filename(candidate_id))
    gc.atomic_write_text(out_path, gc.pretty_json(candidate))

    if resolved_storage_policy == "COMMITTED_OWNER_CONTENT" and text_content is not None:
        content_path = out_path[: -len(".json")] + ".content.txt"
        gc.atomic_write_text(content_path, text_content)

    return candidate


def main():
    parser = argparse.ArgumentParser(description="Register one PROGRAM-004 research source candidate.")
    parser.add_argument("--discovery-method", required=True, choices=ac.DISCOVERY_METHODS)
    parser.add_argument("--submitted-by", default="Joe Mogollon")
    parser.add_argument("--url")
    parser.add_argument("--title")
    parser.add_argument("--creator-name")
    parser.add_argument("--claimed-trader-id")
    parser.add_argument("--description")
    parser.add_argument("--language")
    parser.add_argument("--text-file", help="Path to a local text file whose contents become text_content")
    parser.add_argument("--local-file", help="Path (relative to --uploads-root) for PDF_REFERENCE")
    parser.add_argument("--storage-policy", choices=ac.STORAGE_POLICIES,
                         help="Explicit storage-policy selection -- required to commit full third-party text")
    parser.add_argument("--content-origin", choices=["OWNER_AUTHORED", "THIRD_PARTY_OWNER_PROVIDED", "UNKNOWN_ORIGIN"])
    parser.add_argument("--uploads-root", default=os.path.join(REPO_ROOT, "docs", "trader-intelligence", "acquisition", "candidates"))
    parser.add_argument("--candidates-dir", default=os.path.join(REPO_ROOT, "docs", "trader-intelligence", "acquisition", "candidates"))
    parser.add_argument("--ti-root", default=os.path.join(REPO_ROOT, "docs", "trader-intelligence"))
    args = parser.parse_args()

    text_content = None
    if args.text_file:
        with open(args.text_file, "r", encoding="utf-8") as f:
            text_content = f.read()

    now = datetime.now(timezone.utc)
    try:
        candidate = register_candidate(
            args.candidates_dir, args.ti_root, args.discovery_method, args.submitted_by, now,
            url=args.url, title=args.title, creator_name=args.creator_name,
            claimed_trader_id=args.claimed_trader_id, description=args.description,
            language=args.language, text_content=text_content, local_file_path=args.local_file,
            uploads_root=args.uploads_root, storage_policy=args.storage_policy,
            content_origin=args.content_origin,
        )
    except RegistrationError as e:
        print("REGISTRATION FAILED: %s" % e, file=sys.stderr)
        print("Discovery event: %s" % json.dumps(e.discovery_event), file=sys.stderr)
        return 1
    print("Registered %s (status=%s)" % (candidate["candidateId"], candidate["acquisitionStatus"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

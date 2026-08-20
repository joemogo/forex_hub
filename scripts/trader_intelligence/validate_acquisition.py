#!/usr/bin/env python3
"""PROGRAM-004 Phase 1 -- acquisition integrity validator.

Pure Python standard library. NO NETWORK ACCESS. Read-only against every
candidate/report file -- never edits an authoritative candidate record and
never edits a generated artifact; it only reports on them.
"""
import argparse
import glob as globmod
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import graph_common as gc          # noqa: E402
import acquisition_common as ac    # noqa: E402

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

_DISALLOWED_EXTENSIONS = {".exe", ".zip", ".tar", ".gz", ".rar", ".7z", ".sh", ".bat", ".dmg", ".app"}


def _finding(findings, category, severity, message, affected_ids):
    findings.append({
        "findingId": "F%04d" % (len(findings) + 1),
        "severity": severity, "category": category, "message": message,
        "affectedIds": affected_ids, "blocksArtifactReplacement": severity in ("ERROR", "FATAL"),
    })


def _reachable_statuses():
    seen = {"REGISTERED"}
    frontier = ["REGISTERED"]
    while frontier:
        cur = frontier.pop()
        for nxt in ac.ALLOWED_TRANSITIONS.get(cur, set()):
            if nxt not in seen:
                seen.add(nxt)
                frontier.append(nxt)
    return seen


_REACHABLE = _reachable_statuses()


def load_candidates(candidates_dir, findings):
    candidates = []
    for path in sorted(globmod.glob(os.path.join(candidates_dir, "*.json"))):
        try:
            with open(path, "r", encoding="utf-8") as f:
                candidates.append((path, json.load(f)))
        except (OSError, json.JSONDecodeError) as e:
            _finding(findings, "INVALID_JSON", "FATAL", "Malformed JSON in %s: %s" % (path, e), [path])
    return candidates


def check_duplicate_ids(candidates, findings):
    seen = {}
    for path, c in candidates:
        cid = c.get("candidateId")
        if cid in seen:
            _finding(findings, "DUPLICATE_ENTITY_ID", "FATAL",
                     "Duplicate candidateId %s in %s and %s" % (cid, seen[cid], path), [cid])
        else:
            seen[cid] = path


def check_enum_values(candidates, findings):
    for path, c in candidates:
        cid = c.get("candidateId", path)
        if c.get("platform") not in ac.PLATFORMS:
            _finding(findings, "INVALID_PLATFORM", "ERROR", "%s has invalid platform %r" % (cid, c.get("platform")), [cid])
        if c.get("acquisitionStatus") not in ac.ACQUISITION_STATUSES:
            _finding(findings, "INVALID_STATUS", "ERROR",
                     "%s has invalid acquisitionStatus %r" % (cid, c.get("acquisitionStatus")), [cid])
        elif c["acquisitionStatus"] not in _REACHABLE:
            _finding(findings, "ILLEGAL_STATUS_TRANSITION", "FATAL",
                     "%s is at acquisitionStatus %r which is unreachable from REGISTERED." % (cid, c["acquisitionStatus"]),
                     [cid])
        if c.get("duplicateStatus") not in ac.DUPLICATE_STATUSES:
            _finding(findings, "INVALID_STATUS", "ERROR",
                     "%s has invalid duplicateStatus %r" % (cid, c.get("duplicateStatus")), [cid])
        if c.get("authenticityStatus") not in ac.AUTHENTICITY_STATUSES:
            _finding(findings, "INVALID_STATUS", "ERROR",
                     "%s has invalid authenticityStatus %r" % (cid, c.get("authenticityStatus")), [cid])


def check_owner_decision_requirements(candidates, findings):
    for path, c in candidates:
        cid = c.get("candidateId", path)
        if c.get("authenticityStatus") in ac.OWNER_ONLY_AUTHENTICITY and not c.get("ownerDecisionIds"):
            _finding(findings, "VERIFIED_WITHOUT_OWNER_DECISION", "ERROR",
                     "%s has authenticityStatus=%s with no ownerDecisionIds." % (cid, c["authenticityStatus"]), [cid])
        if c.get("acquisitionStatus") in ("APPROVED_FOR_ACQUISITION", "APPROVED_FOR_RESEARCH_INTAKE", "REJECTED") \
                and not c.get("ownerDecisionIds"):
            _finding(findings, "APPROVAL_WITHOUT_OWNER_DECISION", "ERROR",
                     "%s is at acquisitionStatus=%s with no ownerDecisionIds." % (cid, c["acquisitionStatus"]), [cid])
        if c.get("duplicateStatus") == "POSSIBLE_NEAR_DUPLICATE" and c.get("canonicalCandidateId"):
            _finding(findings, "CANONICAL_WITHOUT_OWNER_APPROVAL", "ERROR",
                     "%s is POSSIBLE_NEAR_DUPLICATE but has canonicalCandidateId set automatically -- "
                     "near-duplicate canonical selection requires an OwnerDecision." % (cid,), [cid])


def check_content_and_storage(candidates, findings, uploads_root):
    for path, c in candidates:
        cid = c.get("candidateId", path)
        storage = c.get("storagePolicy")
        if storage != "METADATA_ONLY" and not c.get("contentHash"):
            _finding(findings, "MISSING_CONTENT_HASH", "ERROR",
                     "%s has storagePolicy=%s but no contentHash." % (cid, storage), [cid])
        if c.get("contentOrigin") not in ("OWNER_AUTHORED", "THIRD_PARTY_OWNER_PROVIDED", "UNKNOWN_ORIGIN"):
            _finding(findings, "INVALID_STATUS", "ERROR",
                     "%s has invalid contentOrigin %r." % (cid, c.get("contentOrigin")), [cid])
        if storage == "COMMITTED_OWNER_CONTENT" and c.get("discoveryMethod") != "OWNER_NOTE" \
                and not c.get("provenance", {}).get("explicitStoragePolicySelection"):
            _finding(findings, "UNAUTHORIZED_CONTENT_COMMIT", "FATAL",
                     "%s commits full content (storagePolicy=COMMITTED_OWNER_CONTENT) for discoveryMethod=%s "
                     "with no recorded explicit storage-policy selection -- pasting/uploading text never by "
                     "itself authorizes committing it (PROGRAM-004 Correction 1)." % (cid, c.get("discoveryMethod")),
                     [cid])
        content_ref = c.get("contentReference")
        if content_ref:
            ext = os.path.splitext(content_ref)[1].lower()
            if ext in _DISALLOWED_EXTENSIONS:
                _finding(findings, "DISALLOWED_EXTENSION", "ERROR",
                         "%s references a disallowed file extension %r." % (cid, ext), [cid])
            elif ext and ext not in ac.ALLOWED_UPLOAD_EXTENSIONS:
                _finding(findings, "DISALLOWED_EXTENSION", "ERROR",
                         "%s references an unsupported file extension %r." % (cid, ext), [cid])
            if ".." in content_ref or os.path.isabs(content_ref):
                _finding(findings, "PATH_TRAVERSAL", "FATAL",
                         "%s contentReference %r looks like a path-traversal attempt." % (cid, content_ref), [cid])
        size = c.get("contentSizeBytes")
        if size is not None and c.get("contentType") == "text/plain" and size > ac.MAX_TEXT_SIZE_BYTES:
            _finding(findings, "OVERSIZED_TEXT", "ERROR",
                     "%s contentSizeBytes=%d exceeds MAX_TEXT_SIZE_BYTES=%d." % (cid, size, ac.MAX_TEXT_SIZE_BYTES), [cid])


def check_score_history(candidates, findings):
    for path, c in candidates:
        cid = c.get("candidateId", path)
        assessments = c.get("priorityAssessments", [])
        seen_ids = set()
        for a in assessments:
            aid = a.get("assessmentId")
            if aid in seen_ids:
                _finding(findings, "SCORE_HISTORY_OVERWRITE", "ERROR",
                         "%s has a duplicate assessmentId %s in priorityAssessments." % (cid, aid), [cid])
            seen_ids.add(aid)
            dims = a.get("dimensions", {})
            missing = set(a.get("missingDimensions", []))
            for dim_name, val in dims.items():
                if val == 0 and dim_name in missing:
                    _finding(findings, "UNKNOWN_COERCED_TO_ZERO", "ERROR",
                             "%s assessment %s lists dimension %s as both 0 and missing -- contradictory." % (
                                 cid, aid, dim_name), [cid])


def check_changelog_ordering(candidates, findings):
    for path, c in candidates:
        cid = c.get("candidateId", path)
        entries = c.get("changeLog", [])
        timestamps = [e["changedAt"] for e in entries]
        if timestamps != sorted(timestamps):
            _finding(findings, "BROKEN_CHANGELOG_ORDERING", "ERROR",
                     "%s changeLog is not in non-decreasing changedAt order." % (cid,), [cid])


def check_provenance(candidates, findings):
    for path, c in candidates:
        cid = c.get("candidateId", path)
        if not c.get("provenance", {}).get("registeredVia"):
            _finding(findings, "MISSING_PROVENANCE", "ERROR", "%s is missing provenance.registeredVia." % (cid,), [cid])


def check_duplicate_group_consistency(candidates, duplicate_groups, findings):
    by_id = {c["candidateId"] for _p, c in candidates}
    for group in duplicate_groups:
        for member_id in group.get("memberCandidateIds", []):
            if member_id not in by_id:
                _finding(findings, "DUPLICATE_ASSESSMENT_INCONSISTENCY", "ERROR",
                         "DuplicateGroup %s references non-existent candidate %s." % (group["groupId"], member_id),
                         [group["groupId"], member_id])


def check_no_runtime_coupling(repo_root, findings):
    index_path = os.path.join(repo_root, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            content = f.read()
        if "acquisition" in content.lower() and "docs/trader-intelligence/acquisition" in content:
            _finding(findings, "NO_RUNTIME_COUPLING_VIOLATION", "FATAL",
                     "index.html references docs/trader-intelligence/acquisition.", [])


def run_integrity_checks(candidates_dir, reports_dir, repo_root, uploads_root=None):
    findings = []
    candidates = load_candidates(candidates_dir, findings)
    check_duplicate_ids(candidates, findings)
    check_enum_values(candidates, findings)
    check_owner_decision_requirements(candidates, findings)
    check_content_and_storage(candidates, findings, uploads_root or candidates_dir)
    check_score_history(candidates, findings)
    check_changelog_ordering(candidates, findings)
    check_provenance(candidates, findings)

    dup_report_path = os.path.join(reports_dir, "duplicate-report.json")
    duplicate_groups = []
    if os.path.exists(dup_report_path):
        with open(dup_report_path, "r", encoding="utf-8") as f:
            duplicate_groups = json.load(f).get("groups", [])
    check_duplicate_group_consistency(candidates, duplicate_groups, findings)
    check_no_runtime_coupling(repo_root, findings)

    summary = {"INFO": 0, "WARNING": 0, "ERROR": 0, "FATAL": 0}
    for f in findings:
        summary[f["severity"]] += 1
    return findings, summary


def main():
    parser = argparse.ArgumentParser(description="Validate PROGRAM-004 acquisition candidates and reports.")
    parser.add_argument("--candidates-dir", default=os.path.join(REPO_ROOT, "docs", "trader-intelligence", "acquisition", "candidates"))
    parser.add_argument("--reports-dir", default=os.path.join(REPO_ROOT, "docs", "trader-intelligence", "acquisition", "reports"))
    parser.add_argument("--repo-root", default=REPO_ROOT)
    args = parser.parse_args()

    findings, summary = run_integrity_checks(args.candidates_dir, args.reports_dir, args.repo_root)
    print("Summary: %r" % (summary,))
    for f in findings:
        print("%s %s: %s" % (f["severity"], f["category"], f["message"]))
    return gc.exit_code_for(summary)


if __name__ == "__main__":
    raise SystemExit(main())

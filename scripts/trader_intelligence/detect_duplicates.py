#!/usr/bin/env python3
"""PROGRAM-004 Phase 1 -- offline exact/near-duplicate detection.

Pure Python standard library. NO NETWORK ACCESS.

Automatic detection may only ever set duplicateStatus to NONE, EXACT_DUPLICATE,
or POSSIBLE_NEAR_DUPLICATE (PROGRAM-004 Owner Decision 7). canonicalCandidateId
is auto-assigned only within an EXACT_DUPLICATE group (URL/content-hash
identity); a POSSIBLE_NEAR_DUPLICATE group is always left with
canonicalCandidateId=null and status=pending_owner_review, however similar the
titles look -- selecting a canonical candidate, or upgrading the relationship
to DERIVATIVE/EXCERPT/UPDATED_VERSION, requires an OwnerDecision.
"""
import argparse
import difflib
import glob as globmod
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import graph_common as gc          # noqa: E402
import acquisition_common as ac    # noqa: E402

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

NEAR_DUPLICATE_TITLE_THRESHOLD = 0.82


def _load_candidates(candidates_dir):
    candidates = []
    for path in sorted(globmod.glob(os.path.join(candidates_dir, "*.json"))):
        with open(path, "r", encoding="utf-8") as f:
            candidates.append((path, json.load(f)))
    return candidates


def _record_change(candidate, now_iso, changed_fields, reason):
    candidate["changeLog"].append({"changedAt": now_iso, "changedFields": changed_fields, "reason": reason})
    candidate["updatedAt"] = now_iso


def detect_duplicates(candidates_dir, now):
    """Mutates and rewrites affected candidate files in place (they are
    authoritative, mutable records with their own changeLog -- unlike the
    generated graph/queue artifacts). Returns the list of DuplicateGroup dicts
    (these are serialized into reports/duplicate-report.json by the caller,
    never as one-file-per-group)."""
    loaded = _load_candidates(candidates_dir)
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    groups = []
    seq = 1
    date_str = now.strftime("%Y%m%d")

    by_url = {}
    by_hash = {}
    for path, c in loaded:
        if c.get("normalizedUrl"):
            by_url.setdefault(c["normalizedUrl"], []).append((path, c))
        if c.get("contentHash"):
            by_hash.setdefault(c["contentHash"], []).append((path, c))

    exact_grouped_ids = set()

    def make_exact_group(members, match_basis):
        nonlocal seq
        members_sorted = sorted(members, key=lambda pc: pc[1]["discoveredAt"])
        canonical_path, canonical = members_sorted[0]
        group_id = ac.make_duplicate_group_id(date_str, seq)
        seq += 1
        member_ids = [c["candidateId"] for _p, c in members_sorted]
        for path, c in members_sorted[1:]:
            if c["duplicateStatus"] != "EXACT_DUPLICATE" or c["canonicalCandidateId"] != canonical["candidateId"]:
                c["duplicateStatus"] = "EXACT_DUPLICATE"
                c["canonicalCandidateId"] = canonical["candidateId"]
                _record_change(c, now_iso, ["duplicateStatus", "canonicalCandidateId"],
                                "automatic exact-duplicate detection (%s)" % match_basis)
            exact_grouped_ids.add(c["candidateId"])
        others = [c["candidateId"] for _p, c in members_sorted[1:]]
        if set(canonical.get("relatedCandidateIds", [])) != set(others):
            canonical["relatedCandidateIds"] = others
            _record_change(canonical, now_iso, ["relatedCandidateIds"],
                            "automatic exact-duplicate detection (%s)" % match_basis)
        return {
            "generated": True, "groupId": group_id, "memberCandidateIds": member_ids,
            "canonicalCandidateId": canonical["candidateId"], "matchBasis": match_basis,
            "status": "resolved", "ownerDecisionId": None,
            "createdAt": now_iso, "updatedAt": now_iso,
        }

    for url, members in by_url.items():
        if len(members) > 1:
            groups.append(make_exact_group(members, "NORMALIZED_URL"))
    for h, members in by_hash.items():
        if len(members) > 1:
            already = {c["candidateId"] for _p, c in members} & exact_grouped_ids
            if len(already) == len(members):
                continue  # fully covered by a URL-based group already
            groups.append(make_exact_group(members, "CONTENT_HASH"))

    # Near-duplicate heuristic: title similarity among candidates not already
    # exact-duplicates of each other. Never sets canonicalCandidateId.
    remaining = [(p, c) for p, c in loaded if c["candidateId"] not in exact_grouped_ids and c.get("title")]
    considered_pairs = set()
    for i in range(len(remaining)):
        for j in range(i + 1, len(remaining)):
            _pi, ci = remaining[i]
            _pj, cj = remaining[j]
            pair_key = tuple(sorted([ci["candidateId"], cj["candidateId"]]))
            if pair_key in considered_pairs:
                continue
            considered_pairs.add(pair_key)
            ratio = difflib.SequenceMatcher(None, ci["title"].lower(), cj["title"].lower()).ratio()
            if ratio >= NEAR_DUPLICATE_TITLE_THRESHOLD:
                for c in (ci, cj):
                    if c["duplicateStatus"] not in ("POSSIBLE_NEAR_DUPLICATE",):
                        c["duplicateStatus"] = "POSSIBLE_NEAR_DUPLICATE"
                        _record_change(c, now_iso, ["duplicateStatus"],
                                        "automatic near-duplicate title-similarity heuristic (ratio=%.2f)" % ratio)
                related = set(ci.get("relatedCandidateIds", [])) | {cj["candidateId"]}
                if related != set(ci.get("relatedCandidateIds", [])):
                    ci["relatedCandidateIds"] = sorted(related)
                related2 = set(cj.get("relatedCandidateIds", [])) | {ci["candidateId"]}
                if related2 != set(cj.get("relatedCandidateIds", [])):
                    cj["relatedCandidateIds"] = sorted(related2)
                group_id = ac.make_duplicate_group_id(date_str, seq)
                seq += 1
                groups.append({
                    "generated": True, "groupId": group_id,
                    "memberCandidateIds": sorted([ci["candidateId"], cj["candidateId"]]),
                    "canonicalCandidateId": None, "matchBasis": "TITLE_SIMILARITY",
                    "status": "pending_owner_review", "ownerDecisionId": None,
                    "createdAt": now_iso, "updatedAt": now_iso,
                })

    # Advance any candidate that has passed metadata verification into
    # DUPLICATE_REVIEW now that dedup has actually run against it.
    for _path, c in loaded:
        if c["acquisitionStatus"] == "METADATA_VERIFIED":
            ac.advance_status(c, "DUPLICATE_REVIEW", now, "detect_duplicates.py has processed this candidate "
                               "(duplicateStatus=%s)" % c["duplicateStatus"])

    # Persist any mutated candidate files back to disk (authoritative, atomic).
    for path, c in loaded:
        gc.atomic_write_text(path, gc.pretty_json(c))

    groups.sort(key=lambda g: g["groupId"])
    return groups


def main():
    parser = argparse.ArgumentParser(description="Detect exact/near-duplicate PROGRAM-004 candidates.")
    parser.add_argument("--candidates-dir", default=os.path.join(REPO_ROOT, "docs", "trader-intelligence", "acquisition", "candidates"))
    parser.add_argument("--report-path", default=os.path.join(REPO_ROOT, "docs", "trader-intelligence", "acquisition", "reports", "duplicate-report.json"))
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    groups = detect_duplicates(args.candidates_dir, now)
    report = {
        "generated": True, "builderVersion": gc.BUILDER_VERSION,
        "generatedAt": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "groupCount": len(groups), "groups": groups,
    }
    gc.atomic_write_text(args.report_path, gc.pretty_json(report))
    print("Wrote %s (%d duplicate group(s))" % (args.report_path, len(groups)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

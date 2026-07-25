#!/usr/bin/env python3
"""PROGRAM-004 Phase 1 -- deterministic research-queue builder.

Pure Python standard library. NO NETWORK ACCESS.

Produces queue/queue-snapshot.json, queue/manifest.json, and
reports/priority-report.json from the current candidate records. A failed
build (any candidate file that is not valid JSON, or missing candidateId)
never replaces the last successful queue-snapshot.json/manifest.json --
same atomic-write discipline as build_graph.py.
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


def _latest_assessment(candidate):
    assessments = candidate.get("priorityAssessments") or []
    return assessments[-1] if assessments else None


def _sort_key(candidate):
    assessment = _latest_assessment(candidate)
    score = assessment["recommendationScore"] if assessment else None
    # None sorts last: represent as a tuple flag so unscored candidates never
    # outrank scored ones, while still being fully deterministic among themselves.
    return (0 if score is not None else 1, -(score or 0), candidate["discoveredAt"], candidate["candidateId"])


def build_queue(candidates_dir, weights_dir, queue_dir, reports_dir, now):
    date_str = now.strftime("%Y%m%d")
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    candidate_paths = sorted(globmod.glob(os.path.join(candidates_dir, "*.json")))
    candidates = []
    load_errors = []
    for path in candidate_paths:
        try:
            with open(path, "r", encoding="utf-8") as f:
                c = json.load(f)
            if "candidateId" not in c:
                raise ValueError("missing candidateId")
            candidates.append(c)
        except Exception as e:
            load_errors.append({"path": path, "error": str(e)})

    manifest_path = os.path.join(queue_dir, "manifest.json")
    seq = 1
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                prev = json.load(f)
            parts = prev.get("buildId", "").split("|")
            if len(parts) == 3 and parts[1] == date_str:
                seq = int(parts[2]) + 1
        except (OSError, ValueError, json.JSONDecodeError):
            seq = 1
    build_id = ac.make_queue_build_id(date_str, seq)

    blocked = len(load_errors) > 0

    candidates_sorted = sorted(candidates, key=_sort_key)
    entries = []
    for c in candidates_sorted:
        assessment = _latest_assessment(c)
        entries.append({
            "candidateId": c["candidateId"],
            "title": c.get("title"),
            "recommendationScore": assessment["recommendationScore"] if assessment else None,
            "scoringConfidence": assessment["scoringConfidence"] if assessment else None,
            "acquisitionStatus": c["acquisitionStatus"],
            "ownerReviewStatus": c["ownerReviewStatus"],
            "duplicateStatus": c["duplicateStatus"],
            "discoveredAt": c["discoveredAt"],
        })

    priority_rows = []
    for c in candidates_sorted:
        assessment = _latest_assessment(c)
        priority_rows.append({
            "candidateId": c["candidateId"],
            "assessment": assessment,
        })

    input_files = [{"path": os.path.relpath(p, REPO_ROOT), "contentHash": gc.file_hash(p)} for p in candidate_paths]

    queue_snapshot = {
        "generated": True, "builderVersion": gc.BUILDER_VERSION, "queueBuildId": build_id,
        "builtAt": now_iso, "candidateCount": len(candidates_sorted), "entries": entries,
    }
    priority_report = {
        "generated": True, "builderVersion": gc.BUILDER_VERSION, "generatedAt": now_iso,
        "queueBuildId": build_id, "rows": priority_rows,
    }
    manifest = {
        "generated": True, "buildId": build_id, "builderVersion": gc.BUILDER_VERSION, "builtAt": now_iso,
        "inputFiles": input_files,
        "outputFiles": [
            {"path": "docs/trader-intelligence/acquisition/queue/queue-snapshot.json",
             "contentHash": gc.content_hash_of(queue_snapshot)},
        ],
        "candidateCount": len(candidates_sorted),
        "status": "failed" if blocked else "success",
        "loadErrors": load_errors,
    }

    priority_report_path = os.path.join(reports_dir, "priority-report.json")
    gc.atomic_write_text(priority_report_path, gc.pretty_json(priority_report))

    if not blocked:
        gc.atomic_write_text(os.path.join(queue_dir, "queue-snapshot.json"), gc.pretty_json(queue_snapshot))
        gc.atomic_write_text(manifest_path, gc.pretty_json(manifest))

    return (not blocked), manifest, queue_snapshot, priority_report


def main():
    parser = argparse.ArgumentParser(description="Build the PROGRAM-004 deterministic research queue.")
    parser.add_argument("--candidates-dir", default=os.path.join(REPO_ROOT, "docs", "trader-intelligence", "acquisition", "candidates"))
    parser.add_argument("--weights-dir", default=os.path.join(REPO_ROOT, "docs", "trader-intelligence", "acquisition", "weights"))
    parser.add_argument("--queue-dir", default=os.path.join(REPO_ROOT, "docs", "trader-intelligence", "acquisition", "queue"))
    parser.add_argument("--reports-dir", default=os.path.join(REPO_ROOT, "docs", "trader-intelligence", "acquisition", "reports"))
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    promoted, manifest, snapshot, report = build_queue(args.candidates_dir, args.weights_dir, args.queue_dir, args.reports_dir, now)
    print("buildId=%s status=%s candidates=%d" % (manifest["buildId"], manifest["status"], manifest["candidateCount"]))
    return 0 if promoted else 1


if __name__ == "__main__":
    raise SystemExit(main())

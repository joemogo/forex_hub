#!/usr/bin/env python3
"""PROGRAM-003 Phase 1 -- deterministic Knowledge Graph builder.

Pure Python standard library. Reads every authoritative Trader Intelligence
record under docs/trader-intelligence/traders/** and
docs/trader-intelligence/graph/decisions/**, and deterministically produces
GraphNode/GraphEdge/GraphManifest/GraphIntegrityReport artifacts under
docs/trader-intelligence/graph/{build,reports}/.

This script never modifies an authoritative record. It never writes anything
outside docs/trader-intelligence/graph/{build,reports}/. A failed build (any
FATAL or ERROR-severity integrity finding) never replaces the last valid
nodes.json/edges.json/manifest.json -- see promote() below.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import graph_common as gc
import validate_graph

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _next_build_id(graph_root, now):
    date_str = now.strftime("%Y%m%d")
    manifest_path = os.path.join(graph_root, "build", "manifest.json")
    seq = 1
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                prev = json.load(f)
            prev_id = prev.get("buildId", "")
            parts = prev_id.split("|")
            if len(parts) == 3 and parts[1] == date_str:
                seq = int(parts[2]) + 1
        except (OSError, ValueError, json.JSONDecodeError):
            seq = 1
    return gc.make_build_id(date_str, seq)


def _input_files_manifest(repo_root, ti_root, graph_root):
    """One entry per distinct source file (not per entity -- the
    open-questions cross-reference file holds many entities in one file)."""
    seen_files = set()
    out = []
    for _node_type, _entity, source_file in gc.discover_entities(repo_root, ti_root, graph_root):
        if source_file in seen_files:
            continue
        seen_files.add(source_file)
        abs_path = os.path.join(repo_root, source_file)
        out.append({"path": source_file, "contentHash": gc.file_hash(abs_path)})
    out.sort(key=lambda x: x["path"])
    return out


def build(repo_root, ti_root, graph_root, now=None):
    """Runs one full build+validate cycle. Returns (promoted: bool, manifest: dict,
    integrity_report: dict, nodes: list, edges: list)."""
    now = now or datetime.now(timezone.utc)

    nodes, edges, construction_findings, raw_by_entity_id = gc.build_nodes_and_edges(repo_root, ti_root, graph_root)

    build_id = _next_build_id(graph_root, now)
    report = validate_graph.run_integrity_checks(nodes, edges, raw_by_entity_id, construction_findings, build_id)

    node_counts = {}
    for n in nodes:
        node_counts[n["nodeType"]] = node_counts.get(n["nodeType"], 0) + 1
    edge_counts = {}
    for e in edges:
        edge_counts[e["edgeType"]] = edge_counts.get(e["edgeType"], 0) + 1

    input_files = _input_files_manifest(repo_root, ti_root, graph_root)

    nodes_path = os.path.join(graph_root, "build", "nodes.json")
    edges_path = os.path.join(graph_root, "build", "edges.json")
    manifest_path = os.path.join(graph_root, "build", "manifest.json")
    report_path = os.path.join(graph_root, "reports", "integrity-report.json")

    blocked = report["summary"]["FATAL"] > 0 or report["summary"]["ERROR"] > 0

    manifest = {
        "generated": True,
        "buildId": build_id,
        "builderVersion": gc.BUILDER_VERSION,
        "builtAt": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "inputFiles": input_files,
        "outputFiles": [
            {"path": "docs/trader-intelligence/graph/build/nodes.json", "contentHash": gc.content_hash_of(nodes)},
            {"path": "docs/trader-intelligence/graph/build/edges.json", "contentHash": gc.content_hash_of(edges)},
        ],
        "nodeCounts": node_counts,
        "edgeCounts": edge_counts,
        "status": "failed" if blocked else "success",
        "integrityReportId": report["integrityReportId"],
        "notes": "" if not blocked else "Build blocked: %d ERROR + %d FATAL finding(s). Last valid nodes.json/edges.json/manifest.json were NOT replaced." % (
            report["summary"]["ERROR"], report["summary"]["FATAL"]),
    }

    # Integrity report is diagnostic output, not one of "the last valid
    # artifacts" -- it is always written so a failed attempt is visible.
    gc.atomic_write_text(report_path, gc.pretty_json(report))

    if not blocked:
        gc.atomic_write_text(nodes_path, gc.pretty_json(nodes))
        gc.atomic_write_text(edges_path, gc.pretty_json(edges))
        gc.atomic_write_text(manifest_path, gc.pretty_json(manifest))

    return (not blocked), manifest, report, nodes, edges


def main():
    parser = argparse.ArgumentParser(description="Build the PROGRAM-003 Knowledge Graph deterministically.")
    parser.add_argument("--repo-root", default=REPO_ROOT)
    parser.add_argument("--ti-root", default=None)
    parser.add_argument("--graph-root", default=None)
    args = parser.parse_args()

    repo_root = os.path.abspath(args.repo_root)
    ti_root = args.ti_root or os.path.join(repo_root, "docs", "trader-intelligence")
    graph_root = args.graph_root or os.path.join(ti_root, "graph")

    promoted, manifest, report, nodes, edges = build(repo_root, ti_root, graph_root)
    print("buildId=%s status=%s nodes=%d edges=%d summary=%r" % (
        manifest["buildId"], manifest["status"], len(nodes), len(edges), report["summary"]))
    return 0 if promoted else 1


if __name__ == "__main__":
    raise SystemExit(main())

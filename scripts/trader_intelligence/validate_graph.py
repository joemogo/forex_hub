#!/usr/bin/env python3
"""PROGRAM-003 Phase 1 -- Knowledge Graph integrity validator.

Pure Python standard library. Read-only against every authoritative Trader
Intelligence record. Produces a GraphIntegrityReport describing data-quality
problems in an already-built graph -- it never edits nodes.json/edges.json
and never edits any authoritative source file.

Can be run standalone (`python3 validate_graph.py`) to re-validate the graph
currently committed under docs/trader-intelligence/graph/build/, or imported
and called by build_graph.py to validate an in-memory graph before deciding
whether to promote it over the last good artifacts.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import graph_common as gc

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TI_ROOT = os.path.join(REPO_ROOT, "docs", "trader-intelligence")
GRAPH_ROOT = os.path.join(TI_ROOT, "graph")

_EVIDENTIARY_EDGE_TYPES = {"SUPPORTS", "EVIDENCES", "CONTRADICTS", "VALIDATES", "RESOLVES", "PARTIALLY_RESOLVES",
                           # PROGRAM-007 Phase 7A: BLUEPRINT_DERIVED_FROM_CLAIM and
                           # CLAIM_CONTRADICTS_HYPOTHESIS always carry a real, non-empty evidenceIds at
                           # creation time (see graph_common.py's edge-derivation blocks). CLAIM_SUPPORTS_
                           # HYPOTHESIS is deliberately NOT included here: a hypothesis may legitimately be
                           # anchored to a claim with zero supportingEvidenceIds of its own (e.g. a gap-derived
                           # hypothesis, where the claim itself -- already the edge's fromNode -- is the only
                           # provenance), so requiring extra evidenceIds on that edge would misclassify valid data.
                           "BLUEPRINT_DERIVED_FROM_CLAIM", "CLAIM_CONTRADICTS_HYPOTHESIS"}
_CONFIDENCE_ENUM = {"unknown", "not_applicable", "very_low", "low", "medium", "high", "very_high"}


def _finding(findings, category, severity, message, affected_ids):
    findings.append({
        "findingId": "F%04d" % (len(findings) + 1),
        "severity": severity,
        "category": category,
        "message": message,
        "affectedIds": affected_ids,
        "blocksArtifactReplacement": severity in ("ERROR", "FATAL"),
    })


def check_duplicates(nodes, edges, findings):
    seen_entity = {}
    for n in nodes:
        key = (n["nodeType"], n["entityId"])
        if key in seen_entity:
            _finding(findings, "DUPLICATE_ENTITY_ID", "FATAL",
                     "Entity id %s used by more than one %s record." % (n["entityId"], n["nodeType"]),
                     [n["nodeId"]])
        seen_entity[key] = True
    node_ids = [n["nodeId"] for n in nodes]
    if len(node_ids) != len(set(node_ids)):
        _finding(findings, "DUPLICATE_NODE_ID", "FATAL", "Duplicate nodeId detected in node set.", [])
    edge_ids = [e["edgeId"] for e in edges]
    if len(edge_ids) != len(set(edge_ids)):
        _finding(findings, "DUPLICATE_EDGE_ID", "ERROR", "Duplicate edgeId detected in edge set.", [])


def check_types_and_direction(nodes, edges, findings):
    node_type_by_id = {n["nodeId"]: n["nodeType"] for n in nodes}
    for n in nodes:
        if n["nodeType"] not in gc.NODE_TYPES:
            _finding(findings, "INVALID_NODE_TYPE", "ERROR", "Unknown nodeType %r." % (n["nodeType"],), [n["nodeId"]])
    for e in edges:
        if e["edgeType"] not in gc.EDGE_TYPES:
            _finding(findings, "INVALID_EDGE_TYPE", "ERROR", "Unknown edgeType %r." % (e["edgeType"],), [e["edgeId"]])
            continue
        from_type = node_type_by_id.get(e["fromNodeId"])
        to_type = node_type_by_id.get(e["toNodeId"])
        if from_type is None or to_type is None:
            _finding(findings, "MISSING_REFERENCE", "ERROR",
                     "Edge %s references a node id that does not exist." % (e["edgeId"],), [e["edgeId"]])
            continue
        allowed = _EDGE_DIRECTION_TABLE.get(e["edgeType"])
        if allowed and (from_type, to_type) not in allowed:
            _finding(findings, "INVALID_EDGE_DIRECTION", "ERROR",
                     "Edge %s has disallowed direction %s -> %s for edgeType %s." % (
                         e["edgeId"], from_type, to_type, e["edgeType"]),
                     [e["edgeId"]])


_EDGE_DIRECTION_TABLE = {
    "BELONGS_TO_TRADER": {(t, "TRADER") for t in gc.NODE_TYPES if t != "TRADER"},
    "BELONGS_TO_STRATEGY_FAMILY": {("STRATEGY_ASSERTION", "STRATEGY_FAMILY"), ("CHART_EXAMPLE", "STRATEGY_FAMILY"),
                                    ("STRATEGY_RULE", "STRATEGY_FAMILY"), ("UNRESOLVED_QUESTION", "STRATEGY_FAMILY"),
                                    ("EVIDENCE_SOURCE", "STRATEGY_FAMILY"), ("EVIDENCE_ITEM", "STRATEGY_FAMILY"),
                                    ("CLAIM", "STRATEGY_FAMILY")},
    "DERIVED_FROM": {("SOURCE_SEGMENT", "RESEARCH_SOURCE"), ("STRATEGY_ASSERTION", "RESEARCH_SOURCE"),
                      ("CHART_EXAMPLE", "RESEARCH_SOURCE"), ("RESEARCH_INTAKE_REPORT", "RESEARCH_SOURCE"),
                      ("EVIDENCE_ITEM", "EVIDENCE_SOURCE"), ("EVIDENCE_ITEM", "EVIDENCE_ITEM"),
                      # B-32. Mirrors EVIDENCE_ITEM -> EVIDENCE_SOURCE: an observation
                      # is derived from the source it was minted from. Enumerated as an
                      # explicit pair rather than loosening the table, so the direction
                      # gate keeps rejecting every combination nobody has justified --
                      # it caught this edge on the first build, which is the point of it.
                      ("TRADE_OBSERVATION", "EVIDENCE_SOURCE")},
    "SEGMENT_OF": {("SOURCE_SEGMENT", "RESEARCH_SOURCE"),
                   ("TRANSCRIPT_SEGMENT", "INTAKE_MANIFEST")},  # PROGRAM-006 Phase 1B
    "ASSERTED_IN": {("STRATEGY_ASSERTION", "SOURCE_SEGMENT")},
    "SUPPORTS": {("STRATEGY_ASSERTION", "STRATEGY_RULE"), ("EVIDENCE_ITEM", "CLAIM")},
    "EVIDENCES": {("RULE_EVIDENCE", "STRATEGY_RULE")},
    "CONTRADICTS": {("RULE_CONTRADICTION", "STRATEGY_RULE"), ("EVIDENCE_ITEM", "CLAIM"),
                     ("CONTRADICTION_RECORD", "CLAIM")},
    "IMPLEMENTS": set(),  # not populated in Phase 1 -- no valid direction has ever been exercised
    "SUPERSEDES": {("STRATEGY_ASSERTION", "STRATEGY_ASSERTION"), ("RULE_VERSION", "RULE_VERSION"),
                    ("OWNER_DECISION", "OWNER_DECISION"), ("EVIDENCE_ITEM", "EVIDENCE_ITEM")},
    "REFERENCES": {(t, u) for t in gc.NODE_TYPES for u in gc.NODE_TYPES},  # deliberately permissive, generic citation
    "BLOCKS": {("UNRESOLVED_QUESTION", "STRATEGY_RULE"), ("UNRESOLVED_QUESTION", "STRATEGY_FAMILY"),
               ("UNRESOLVED_QUESTION", "TRADER")},
    "RESOLVES": {("STRATEGY_ASSERTION", "UNRESOLVED_QUESTION")},
    "PARTIALLY_RESOLVES": {("STRATEGY_ASSERTION", "UNRESOLVED_QUESTION")},
    "REQUIRES_OWNER_DECISION": {("STRATEGY_RULE", "OWNER_DECISION")},
    "VERSION_OF": {("RULE_VERSION", "STRATEGY_RULE")},
    "VALIDATES": set(),  # not populated in Phase 1 -- no replay/paper integration yet
    # PROGRAM-006 (ADR-008) additive edge types:
    "WEAKENS": {("EVIDENCE_ITEM", "CLAIM")},
    "CONTEXTUALIZES": {("EVIDENCE_ITEM", "CLAIM")},
    "EXEMPLIFIES": {("EVIDENCE_ITEM", "CLAIM")},
    "QUALIFIES": {("EVIDENCE_ITEM", "CLAIM")},
    "UNRESOLVED": {("EVIDENCE_ITEM", "CLAIM")},
    "CANDIDATE_FOR_RULE": {("CLAIM", "STRATEGY_RULE")},
    # PROGRAM-006 Phase 1B (ADR-009) additive edge types:
    "EVIDENCE_FROM_SEGMENT": {("EVIDENCE_ITEM", "TRANSCRIPT_SEGMENT")},
    "RAISES_QUESTION": {("CLAIM", "EVIDENCE_QUESTION")},
    "REQUIRES_REVIEW": {(t, "REVIEW_QUEUE_ENTRY") for t in (
        "EVIDENCE_SOURCE", "EVIDENCE_ITEM", "CLAIM", "CONTRADICTION_RECORD",
        "EVIDENCE_QUESTION", "RULE_CANDIDATE_PROPOSAL", "INTAKE_MANIFEST", "TRANSCRIPT_SEGMENT")},
    "PROPOSES_RULE": {("CLAIM", "RULE_CANDIDATE_PROPOSAL")},
    "BLOCKED_BY": {("RULE_CANDIDATE_PROPOSAL", "CONTRADICTION_RECORD"),
                   ("RULE_CANDIDATE_PROPOSAL", "EVIDENCE_QUESTION")},
    "RESOLVED_BY_EVIDENCE": {("EVIDENCE_QUESTION", "EVIDENCE_ITEM")},
    # PROGRAM-007 Phase 7A (Knowledge Library vertical slice) additive edge types:
    "BLUEPRINT_DERIVED_FROM_CLAIM": {("STRATEGY_BLUEPRINT", "CLAIM")},
    "BLUEPRINT_HAS_GAP": {("STRATEGY_BLUEPRINT", "KNOWLEDGE_GAP")},
    "GAP_GENERATES_RESEARCH_QUESTION": {("KNOWLEDGE_GAP", "EVIDENCE_QUESTION")},
    "CLAIM_SUPPORTS_HYPOTHESIS": {("CLAIM", "HYPOTHESIS")},
    "CLAIM_CONTRADICTS_HYPOTHESIS": {("CLAIM", "HYPOTHESIS")},
}


def check_observation_trader_isolation(nodes, edges, findings):
    """No TRADE_OBSERVATION may reach a TRADER or STRATEGY_FAMILY at ANY hop.

    Stated as a REACHABILITY invariant rather than another builder exclusion,
    because the builder exclusions kept being right about one hop and silent about
    the next. Excluding TRADE_OBSERVATION from BELONGS_TO_TRADER stopped the direct
    edge; adding `traderId` to one cited SOURCE then produced

        observation --DERIVED_FROM--> source --BELONGS_TO_TRADER--> ALEX_G

    in two hops with every gate silent, because a source may legitimately belong to
    a trader. Every edge-construction fix answers "may THIS node type link to a
    trader"; none answers the question that matters -- whether MOGO's execution
    record can be walked to a human trader's evidence by any route at all.

    Why it matters, from CLAUDE.md: `alex_g_sr_v1` is MOGO's implementation, `ALEX_G`
    is a person. A path between them lets a query count OBSERVED paper trades as
    evidence for a SOURCE_STATED claim -- "the easiest way to manufacture a false
    result here". Two hops contaminate exactly as much as one.

    ERROR, and it names the path, because "an observation reaches a trader somehow"
    is not actionable without knowing which edge to look at.
    """
    by_id = {n["nodeId"]: n for n in nodes}
    adjacency = {}
    for edge in edges:
        adjacency.setdefault(edge["fromNodeId"], []).append((edge["toNodeId"], edge["edgeType"]))
        adjacency.setdefault(edge["toNodeId"], []).append((edge["fromNodeId"], edge["edgeType"]))

    forbidden = {"TRADER", "STRATEGY_FAMILY"}
    for start in [n for n in nodes if n["nodeType"] == "TRADE_OBSERVATION"]:
        # Undirected: direction is irrelevant to contamination -- a query walking
        # either way joins the two populations just the same.
        seen = {start["nodeId"]}
        queue = [(start["nodeId"], [])]
        while queue:
            current, path = queue.pop(0)
            for neighbour, edge_type in adjacency.get(current, []):
                if neighbour in seen:
                    continue
                seen.add(neighbour)
                node = by_id.get(neighbour)
                if node is None:
                    continue
                trail = path + [edge_type]
                if node["nodeType"] in forbidden:
                    _finding(findings, "OBSERVATION_TRADER_CONTAMINATION", "ERROR",
                             "%s reaches %s %s in %d hop(s) via %s. MOGO's own execution "
                             "record must not be walkable to a human trader's evidence by "
                             "any route -- one is what MOGO's code did, the other is what a "
                             "person said." % (start["entityId"], node["nodeType"],
                                               node["entityId"], len(trail), " -> ".join(trail)),
                             [start["nodeId"], node["nodeId"]])
                    queue = []
                    break
                queue.append((neighbour, trail))


def check_orphans(nodes, edges, findings):
    touched = set()
    for e in edges:
        touched.add(e["fromNodeId"])
        touched.add(e["toNodeId"])
    for n in nodes:
        if n["nodeType"] == "TRADER":
            continue  # traders are the graph's roots; never orphans by definition
        if n["nodeId"] not in touched:
            _finding(findings, "ORPHAN_NODE", "WARNING",
                     "Node %s has zero edges of any kind." % (n["nodeId"],), [n["nodeId"]])


def check_circular_supersession(nodes, edges, findings):
    adj = {}
    for e in edges:
        if e["edgeType"] == "SUPERSEDES":
            adj.setdefault(e["fromNodeId"], []).append(e["toNodeId"])

    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n["nodeId"]: WHITE for n in nodes}

    def visit(node_id, stack):
        color[node_id] = GRAY
        stack.append(node_id)
        for nxt in adj.get(node_id, []):
            if color.get(nxt, WHITE) == GRAY:
                cycle = stack[stack.index(nxt):] + [nxt]
                _finding(findings, "CIRCULAR_SUPERSESSION", "FATAL",
                         "Circular SUPERSEDES chain: %s" % (" -> ".join(cycle),), cycle)
            elif color.get(nxt, WHITE) == WHITE:
                visit(nxt, stack)
        stack.pop()
        color[node_id] = BLACK

    for node_id in list(adj.keys()):
        if color.get(node_id, WHITE) == WHITE:
            visit(node_id, [])


def check_version_chains(nodes, edges, raw_by_entity_id, findings):
    versions_by_rule = {}
    for node in nodes:
        if node["nodeType"] != "RULE_VERSION":
            continue
        _, entity, _src = raw_by_entity_id[node["entityId"]]
        rule_id = entity.get("ruleId")
        versions_by_rule.setdefault(rule_id, []).append(entity.get("versionNumber"))
    for rule_id, numbers in versions_by_rule.items():
        expected = list(range(1, len(numbers) + 1))
        if sorted(n for n in numbers if n is not None) != expected:
            _finding(findings, "BROKEN_VERSION_CHAIN", "ERROR",
                     "RuleVersion chain for %s is not a contiguous 1..N sequence: found %r." % (rule_id, sorted(numbers)),
                     [rule_id])


def check_provenance(edges, findings):
    for e in edges:
        if e["edgeType"] in _EVIDENTIARY_EDGE_TYPES and not e.get("evidenceIds"):
            _finding(findings, "MISSING_PROVENANCE", "ERROR",
                     "Edge %s (%s) carries no evidenceIds." % (e["edgeId"], e["edgeType"]), [e["edgeId"]])


def check_modeled_rules_have_evidence(nodes, edges, raw_by_entity_id, findings):
    evidences_targets = {e["toNodeId"] for e in edges if e["edgeType"] == "EVIDENCES"}
    for node in nodes:
        if node["nodeType"] != "STRATEGY_RULE":
            continue
        _, entity, _src = raw_by_entity_id[node["entityId"]]
        if entity.get("modelingStatus") == "modeled":
            has_field_evidence = bool(entity.get("sourceEvidenceIds"))
            has_edge_evidence = node["nodeId"] in evidences_targets
            if not has_field_evidence or not has_edge_evidence:
                _finding(findings, "MODELED_RULE_WITHOUT_EVIDENCE", "ERROR",
                         "Rule %s is modelingStatus=modeled but lacks traceable evidence (field=%s, edge=%s)." % (
                             node["entityId"], has_field_evidence, has_edge_evidence),
                         [node["entityId"]])


def check_confidence_misuse(nodes, raw_by_entity_id, findings):
    for node in nodes:
        if node["nodeType"] != "STRATEGY_RULE":
            continue
        _, entity, _src = raw_by_entity_id[node["entityId"]]
        for field in ("sourceConfidence", "interpretationConfidence", "implementationConfidence", "performanceConfidence"):
            v = entity.get(field)
            if v is not None and v not in _CONFIDENCE_ENUM:
                _finding(findings, "CONFIDENCE_MISUSE", "ERROR",
                         "Rule %s field %s has non-enum value %r." % (node["entityId"], field, v), [node["entityId"]])


def check_performance_confidence(nodes, edges, raw_by_entity_id, findings):
    validates_targets = {e["toNodeId"] for e in edges if e["edgeType"] == "VALIDATES"}
    for node in nodes:
        if node["nodeType"] != "STRATEGY_RULE":
            continue
        _, entity, _src = raw_by_entity_id[node["entityId"]]
        pc = entity.get("performanceConfidence", "not_applicable")
        if pc not in ("unknown", "not_applicable") and node["nodeId"] not in validates_targets:
            _finding(findings, "PERFORMANCE_CONFIDENCE_WITHOUT_EVIDENCE", "ERROR",
                     "Rule %s has performanceConfidence=%s with no VALIDATES evidence." % (node["entityId"], pc),
                     [node["entityId"]])


def check_promotion_states(nodes, raw_by_entity_id, findings):
    """Defensive / forward-looking check. strategy-rule.schema.json does not
    define a promotionState field in Phase 1 (deliberately -- see the Phase 1
    report's §17), so this currently returns zero findings against any real
    or synthetic data. It exists now so a future schema revision that adds
    promotionState needs no new validator code, only new data to check."""
    decisions_by_affected = {}
    for node in nodes:
        if node["nodeType"] == "OWNER_DECISION":
            _, entity, _src = raw_by_entity_id[node["entityId"]]
            for affected in entity.get("affectedEntityIds", []):
                decisions_by_affected.setdefault(affected, []).append(entity)

    for node in nodes:
        if node["nodeType"] != "STRATEGY_RULE":
            continue
        _, entity, _src = raw_by_entity_id[node["entityId"]]
        state = entity.get("promotionState")
        if state is None:
            continue
        if state not in gc.PROMOTION_STATES:
            _finding(findings, "INVALID_PROMOTION_TRANSITION", "ERROR",
                     "Rule %s has unknown promotionState %r." % (node["entityId"], state), [node["entityId"]])
            continue
        idx = gc.PROMOTION_STATES.index(state)
        if idx >= gc.PROMOTION_STATES.index("IMPLEMENTATION_APPROVED"):
            decisions = decisions_by_affected.get(node["entityId"], [])
            if not any(d.get("status") == "active" and d.get("implementationAuthorization") for d in decisions):
                _finding(findings, "PROMOTION_WITHOUT_OWNER_AUTHORIZATION", "ERROR",
                         "Rule %s is at %s with no active OwnerDecision granting implementationAuthorization." % (
                             node["entityId"], state), [node["entityId"]])
        for stage, bool_field, category in (
            ("PAPER_APPROVED", "paperAuthorization", "PAPER_APPROVAL_WITHOUT_STATE"),
            ("PRODUCTION_APPROVED", "productionAuthorization", "PRODUCTION_APPROVAL_WITHOUT_STATE"),
            ("LIVE_APPROVED", "liveAuthorization", "LIVE_APPROVAL_WITHOUT_STATE"),
        ):
            if idx >= gc.PROMOTION_STATES.index(stage):
                decisions = decisions_by_affected.get(node["entityId"], [])
                if not any(d.get("status") == "active" and d.get(bool_field) for d in decisions):
                    _finding(findings, category, "ERROR",
                             "Rule %s reached %s with no active OwnerDecision granting %s." % (
                                 node["entityId"], state, bool_field),
                             [node["entityId"]])


def check_strategy_family_backrefs(raw_by_entity_id, findings):
    """TraderRecord.strategyFamilyIds is the reverse direction of
    StrategyFamily.traderId. No graph edge is generated from this field
    (StrategyFamily's own BELONGS_TO_TRADER edge already covers the
    relationship), but it is still cheap and valuable to confirm every id a
    TraderRecord lists actually resolves to a real StrategyFamily node."""
    known_family_ids = {eid for eid, (t, _e, _s) in raw_by_entity_id.items() if t == "STRATEGY_FAMILY"}
    for eid, (node_type, entity, _src) in raw_by_entity_id.items():
        if node_type != "TRADER":
            continue
        for fam_id in entity.get("strategyFamilyIds", []):
            if fam_id not in known_family_ids:
                _finding(findings, "INVALID_STRATEGY_FAMILY_REFERENCE", "ERROR",
                         "TraderRecord %s lists strategyFamilyIds entry %s with no matching StrategyFamily record." % (
                             eid, fam_id),
                         [eid, fam_id])


def run_integrity_checks(nodes, edges, raw_by_entity_id, construction_findings, build_id):
    findings = []
    for cf in construction_findings:
        _finding(findings, cf["category"], cf["severity"], cf["message"], cf["affectedIds"])

    check_duplicates(nodes, edges, findings)
    check_types_and_direction(nodes, edges, findings)
    check_orphans(nodes, edges, findings)
    check_observation_trader_isolation(nodes, edges, findings)
    check_circular_supersession(nodes, edges, findings)
    check_version_chains(nodes, edges, raw_by_entity_id, findings)
    check_provenance(edges, findings)
    check_modeled_rules_have_evidence(nodes, edges, raw_by_entity_id, findings)
    check_confidence_misuse(nodes, raw_by_entity_id, findings)
    check_performance_confidence(nodes, edges, raw_by_entity_id, findings)
    check_promotion_states(nodes, raw_by_entity_id, findings)
    check_strategy_family_backrefs(raw_by_entity_id, findings)

    summary = {"INFO": 0, "WARNING": 0, "ERROR": 0, "FATAL": 0}
    for f in findings:
        summary[f["severity"]] += 1

    report = {
        "generated": True,
        "integrityReportId": gc.make_integrity_report_id(build_id),
        "buildId": build_id,
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "findings": findings,
        "summary": summary,
    }
    return report


def main():
    parser = argparse.ArgumentParser(description="Validate the currently-built PROGRAM-003 Knowledge Graph.")
    parser.add_argument("--repo-root", default=REPO_ROOT)
    parser.add_argument("--ti-root", default=None)
    parser.add_argument("--graph-root", default=None)
    # See validate_evidence.py --check. Same contract: the SAME checks and the SAME exit code,
    # recomputed from the current build on every run, with only the report write skipped.
    parser.add_argument("--check", action="store_true",
                        help="run the full validation and report findings WITHOUT writing "
                             "the integrity report (same checks, same exit code)")
    args = parser.parse_args()

    repo_root = os.path.abspath(args.repo_root)
    ti_root = args.ti_root or os.path.join(repo_root, "docs", "trader-intelligence")
    graph_root = args.graph_root or os.path.join(ti_root, "graph")

    build_path = os.path.join(graph_root, "build", "manifest.json")
    if not os.path.exists(build_path):
        print("No existing build manifest at %s -- run build_graph.py first." % build_path, file=sys.stderr)
        return 1
    with open(build_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    build_id = manifest["buildId"]

    nodes, edges, construction_findings, raw_by_entity_id = gc.build_nodes_and_edges(repo_root, ti_root, graph_root)
    report = run_integrity_checks(nodes, edges, raw_by_entity_id, construction_findings, build_id)

    out_path = os.path.join(graph_root, "reports", "integrity-report.json")
    if args.check:
        print("CHECK ONLY -- %s not written" % out_path)
    else:
        gc.atomic_write_text(out_path, gc.pretty_json(report))
        print("Wrote %s" % out_path)
    print("Summary: %r" % (report["summary"],))
    return gc.exit_code_for(report["summary"])


if __name__ == "__main__":
    raise SystemExit(main())

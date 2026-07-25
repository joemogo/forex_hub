#!/usr/bin/env python3
"""PROGRAM-003 Phase 1 -- deterministic, read-only Knowledge Graph queries.

Pure Python standard library. Every query returns a structured JSON
GraphQueryResult. No query fabricates a missing link: a query either finds
real traversal results, or reports one of a small set of explicit statuses
(not_found / empty / not_implemented / blocked) -- never silently invents an
answer. This module is Layer A only (graph storage and traversal) -- it does
not interpret, weigh, or explain evidence; that is a future, separate
reasoning layer (out of scope for Phase 1).
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import graph_common as gc

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


class GraphIndex:
    def __init__(self, nodes, edges, raw_by_entity_id):
        self.nodes = nodes
        self.edges = edges
        self.raw = raw_by_entity_id
        self.node_by_id = {n["nodeId"]: n for n in nodes}
        self.node_by_entity_id = {n["entityId"]: n for n in nodes}
        self.edges_from = {}
        self.edges_to = {}
        for e in edges:
            self.edges_from.setdefault(e["fromNodeId"], []).append(e)
            self.edges_to.setdefault(e["toNodeId"], []).append(e)

    @classmethod
    def load(cls, repo_root, ti_root, graph_root):
        nodes_path = os.path.join(graph_root, "build", "nodes.json")
        edges_path = os.path.join(graph_root, "build", "edges.json")
        with open(nodes_path, "r", encoding="utf-8") as f:
            nodes = json.load(f)
        with open(edges_path, "r", encoding="utf-8") as f:
            edges = json.load(f)
        _, _, _, raw = gc.build_nodes_and_edges(repo_root, ti_root, graph_root)
        return cls(nodes, edges, raw)

    def raw_of(self, entity_id):
        t = self.raw.get(entity_id)
        return t[1] if t else None

    def node_of(self, entity_id):
        return self.node_by_entity_id.get(entity_id)


def _result(query, inputs, status, results, uncertainty_notes=None):
    return {
        "query": query,
        "inputs": inputs,
        "status": status,  # ok | not_found | empty | not_implemented | blocked
        "results": results,
        "resultCount": len(results),
        "uncertaintyNotes": uncertainty_notes or [],
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def _by_edge_type(edge_list, edge_type):
    return [e for e in edge_list if e["edgeType"] == edge_type]


# 1. Evidence supporting a rule
def evidence_supporting_rule(idx, rule_id):
    node = idx.node_of(rule_id)
    if node is None:
        return _result("evidence_supporting_rule", {"ruleId": rule_id}, "not_found", [])
    incoming = idx.edges_to.get(node["nodeId"], [])
    hits = [e for e in incoming if e["edgeType"] in ("SUPPORTS", "EVIDENCES")]
    results = [{"edgeType": e["edgeType"], "fromEntityId": idx.node_by_id[e["fromNodeId"]]["entityId"],
                "evidenceIds": e["evidenceIds"], "confidenceDimensions": e["confidenceDimensions"]} for e in hits]
    return _result("evidence_supporting_rule", {"ruleId": rule_id}, "ok" if results else "empty", results)


# 2. Evidence contradicting a rule
def evidence_contradicting_rule(idx, rule_id):
    node = idx.node_of(rule_id)
    if node is None:
        return _result("evidence_contradicting_rule", {"ruleId": rule_id}, "not_found", [])
    incoming = _by_edge_type(idx.edges_to.get(node["nodeId"], []), "CONTRADICTS")
    results = [{"contradictionEntityId": idx.node_by_id[e["fromNodeId"]]["entityId"], "evidenceIds": e["evidenceIds"],
                "metadata": e["metadata"]} for e in incoming]
    return _result("evidence_contradicting_rule", {"ruleId": rule_id}, "ok" if results else "empty", results)


# 3. Unresolved questions blocking a strategy family
def unresolved_questions_blocking_family(idx, strategy_family_id):
    family_node = idx.node_of(strategy_family_id)
    if family_node is None:
        return _result("unresolved_questions_blocking_family", {"strategyFamilyId": strategy_family_id}, "not_found", [])
    direct = _by_edge_type(idx.edges_to.get(family_node["nodeId"], []), "BLOCKS")
    results = [{"questionId": idx.node_by_id[e["fromNodeId"]]["entityId"],
                "question": idx.raw_of(idx.node_by_id[e["fromNodeId"]]["entityId"]).get("question")} for e in direct]
    notes = []
    trader_edges = _by_edge_type(idx.edges_from.get(family_node["nodeId"], []), "BELONGS_TO_TRADER")
    if trader_edges:
        trader_node_id = trader_edges[0]["toNodeId"]
        trader_blocks = _by_edge_type(idx.edges_to.get(trader_node_id, []), "BLOCKS")
        if trader_blocks:
            notes.append(
                "%d additional question(s) block this family's trader directly rather than the family "
                "specifically, because they do not yet carry a strategyFamilyId in their source record." % len(trader_blocks))
    return _result("unresolved_questions_blocking_family", {"strategyFamilyId": strategy_family_id},
                   "ok" if results else "empty", results, notes)


# 4. Assertions from a source
def assertions_from_source(idx, source_id):
    node = idx.node_of(source_id)
    if node is None:
        return _result("assertions_from_source", {"sourceId": source_id}, "not_found", [])
    incoming = [e for e in idx.edges_to.get(node["nodeId"], [])
                if e["edgeType"] == "DERIVED_FROM" and idx.node_by_id[e["fromNodeId"]]["nodeType"] == "STRATEGY_ASSERTION"]
    results = [{"assertionId": idx.node_by_id[e["fromNodeId"]]["entityId"]} for e in incoming]
    return _result("assertions_from_source", {"sourceId": source_id}, "ok" if results else "empty", results)


# 5. Rules lacking primary evidence
def rules_lacking_primary_evidence(idx, trader_id=None):
    results = []
    for n in idx.nodes:
        if n["nodeType"] != "STRATEGY_RULE":
            continue
        if trader_id and n["traderId"] != trader_id:
            continue
        incoming = idx.edges_to.get(n["nodeId"], [])
        if not any(e["edgeType"] in ("SUPPORTS", "EVIDENCES") for e in incoming):
            results.append({"ruleId": n["entityId"]})
    return _result("rules_lacking_primary_evidence", {"traderId": trader_id}, "ok" if results else "empty", results)


# 6. Rules with unresolved contradictions
def rules_with_unresolved_contradictions(idx, trader_id=None):
    results = []
    for n in idx.nodes:
        if n["nodeType"] != "STRATEGY_RULE":
            continue
        if trader_id and n["traderId"] != trader_id:
            continue
        incoming = _by_edge_type(idx.edges_to.get(n["nodeId"], []), "CONTRADICTS")
        unresolved = []
        for e in incoming:
            contra_id = idx.node_by_id[e["fromNodeId"]]["entityId"]
            raw = idx.raw_of(contra_id)
            if raw and raw.get("status") != "resolved_by_owner":
                unresolved.append(contra_id)
        if unresolved:
            results.append({"ruleId": n["entityId"], "contradictionIds": unresolved})
    return _result("rules_with_unresolved_contradictions", {"traderId": trader_id}, "ok" if results else "empty", results)


# 7. Rules without replay validation
def rules_without_replay_validation(idx, trader_id=None):
    results = []
    for n in idx.nodes:
        if n["nodeType"] != "STRATEGY_RULE":
            continue
        if trader_id and n["traderId"] != trader_id:
            continue
        incoming = _by_edge_type(idx.edges_to.get(n["nodeId"], []), "VALIDATES")
        if not incoming:
            results.append({"ruleId": n["entityId"]})
    notes = ["VALIDATES edges are never populated in Phase 1 (no replay/paper integration yet) -- "
             "this query is therefore currently vacuous: every existing rule is returned."] if results else []
    return _result("rules_without_replay_validation", {"traderId": trader_id}, "ok" if results else "empty", results, notes)


# 8. Rules eligible for modeling review
def rules_eligible_for_modeling_review(idx, trader_id=None):
    results = []
    for n in idx.nodes:
        if n["nodeType"] != "STRATEGY_RULE":
            continue
        if trader_id and n["traderId"] != trader_id:
            continue
        raw = idx.raw_of(n["entityId"])
        incoming = idx.edges_to.get(n["nodeId"], [])
        has_evidence = any(e["edgeType"] in ("SUPPORTS", "EVIDENCES") for e in incoming)
        if raw.get("modelingStatus") == "not_modeled" and has_evidence:
            results.append({"ruleId": n["entityId"]})
    return _result("rules_eligible_for_modeling_review", {"traderId": trader_id}, "ok" if results else "empty", results)


# 9. Rules blocked from paper trading
def rules_blocked_from_paper_trading(idx, trader_id=None):
    results = []
    for n in idx.nodes:
        if n["nodeType"] != "STRATEGY_RULE":
            continue
        if trader_id and n["traderId"] != trader_id:
            continue
        raw = idx.raw_of(n["entityId"])
        if raw.get("validationStatus") == "paper_approved":
            continue
        blocking = _by_edge_type(idx.edges_to.get(n["nodeId"], []), "BLOCKS")
        if blocking:
            results.append({"ruleId": n["entityId"],
                             "blockingQuestionIds": [idx.node_by_id[e["fromNodeId"]]["entityId"] for e in blocking]})
    return _result("rules_blocked_from_paper_trading", {"traderId": trader_id}, "ok" if results else "empty", results)


# 10. What changed between rule versions
def rule_version_diff(idx, rule_id, v1, v2):
    rule_node = idx.node_of(rule_id)
    if rule_node is None:
        return _result("rule_version_diff", {"ruleId": rule_id, "v1": v1, "v2": v2}, "not_found", [])
    versions = {}
    for n in idx.nodes:
        if n["nodeType"] != "RULE_VERSION":
            continue
        raw = idx.raw_of(n["entityId"])
        if raw.get("ruleId") == rule_id:
            versions[raw.get("versionNumber")] = raw
    if v1 not in versions or v2 not in versions:
        return _result("rule_version_diff", {"ruleId": rule_id, "v1": v1, "v2": v2}, "not_found", [])
    a, b = versions[v1], versions[v2]
    keys = set(a.keys()) | set(b.keys())
    diff = {k: {"before": a.get(k), "after": b.get(k)} for k in sorted(keys) if a.get(k) != b.get(k)}
    return _result("rule_version_diff", {"ruleId": rule_id, "v1": v1, "v2": v2}, "ok", [diff])


# 11. ADR-007 questions informed by a source
def adr007_questions_informed_by_source(idx, source_id):
    source_node = idx.node_of(source_id)
    if source_node is None:
        return _result("adr007_questions_informed_by_source", {"sourceId": source_id}, "not_found", [])
    assertion_node_ids = {e["fromNodeId"] for e in idx.edges_to.get(source_node["nodeId"], [])
                           if e["edgeType"] == "DERIVED_FROM" and idx.node_by_id[e["fromNodeId"]]["nodeType"] == "STRATEGY_ASSERTION"}
    results = []
    for e in idx.edges:
        if e["edgeType"] in ("RESOLVES", "PARTIALLY_RESOLVES") and e["fromNodeId"] in assertion_node_ids:
            q_node = idx.node_by_id.get(e["toNodeId"])
            if q_node:
                results.append({"questionId": q_node["entityId"], "classification": e["edgeType"]})
    notes = [] if results else ["No RESOLVES/PARTIALLY_RESOLVES edges exist yet -- this is vacuous until a real "
                                 "research-intake wave produces assertions that resolve ADR-007 questions."]
    return _result("adr007_questions_informed_by_source", {"sourceId": source_id}, "ok" if results else "empty", results, notes)


# 12. Known facts about a trader excluding inferred assertions
def known_facts_about_trader(idx, trader_id):
    trader_node = idx.node_of(trader_id)
    if trader_node is None:
        return _result("known_facts_about_trader", {"traderId": trader_id}, "not_found", [])
    results = []
    for n in idx.nodes:
        if n["nodeType"] == "TRADER" and n["entityId"] == trader_id:
            results.append({"nodeType": n["nodeType"], "entityId": n["entityId"], "label": n["label"]})
            continue
        if n["traderId"] != trader_id:
            continue
        if n["nodeType"] == "STRATEGY_ASSERTION":
            raw = idx.raw_of(n["entityId"])
            if raw.get("evidenceClassification") == "INFERRED":
                continue
        results.append({"nodeType": n["nodeType"], "entityId": n["entityId"], "label": n["label"]})
    return _result("known_facts_about_trader", {"traderId": trader_id}, "ok" if results else "empty", results)


# 13. Explicit versus inferred assertions
def explicit_vs_inferred(idx, trader_id):
    trader_node = idx.node_of(trader_id)
    if trader_node is None:
        return _result("explicit_vs_inferred", {"traderId": trader_id}, "not_found", [])
    explicit, inferred = [], []
    for n in idx.nodes:
        if n["nodeType"] != "STRATEGY_ASSERTION" or n["traderId"] != trader_id:
            continue
        raw = idx.raw_of(n["entityId"])
        cls = raw.get("evidenceClassification")
        entry = {"assertionId": n["entityId"], "evidenceClassification": cls}
        if cls == "EXPLICIT":
            explicit.append(entry)
        elif cls == "INFERRED":
            inferred.append(entry)
    results = [{"explicit": explicit, "inferred": inferred}]
    status = "ok" if (explicit or inferred) else "empty"
    return _result("explicit_vs_inferred", {"traderId": trader_id}, status, results)


# 14. Owner decisions affecting an entity
def owner_decisions_affecting_entity(idx, entity_id):
    entity_node = idx.node_of(entity_id)
    if entity_node is None:
        return _result("owner_decisions_affecting_entity", {"entityId": entity_id}, "not_found", [])
    incoming = [e for e in idx.edges_to.get(entity_node["nodeId"], [])
                if e["edgeType"] == "REFERENCES" and e["fromNodeId"].startswith("NODE|OWNER_DECISION|")]
    results = []
    for e in incoming:
        decision_node = idx.node_by_id.get(e["fromNodeId"])
        if decision_node:
            results.append({"decisionId": decision_node["entityId"], "label": decision_node["label"]})
    return _result("owner_decisions_affecting_entity", {"entityId": entity_id}, "ok" if results else "empty", results)


# 15. Promotion history for a rule
def promotion_history_for_rule(idx, rule_id):
    rule_node = idx.node_of(rule_id)
    if rule_node is None:
        return _result("promotion_history_for_rule", {"ruleId": rule_id}, "not_found", [])
    versions = []
    for n in idx.nodes:
        if n["nodeType"] != "RULE_VERSION":
            continue
        raw = idx.raw_of(n["entityId"])
        if raw.get("ruleId") == rule_id:
            versions.append({"ruleVersionId": n["entityId"], "versionNumber": raw.get("versionNumber"),
                              "changeSummary": raw.get("changeSummary")})
    versions.sort(key=lambda v: v["versionNumber"] or 0)
    raw_rule = idx.raw_of(rule_id)
    promotion_state = raw_rule.get("promotionState")
    notes = []
    if promotion_state is None:
        notes.append("promotionState is not yet a field on strategy-rule.schema.json in Phase 1 -- "
                     "only version history is available, not a promotion-stage timeline.")
    results = [{"versions": versions, "promotionState": promotion_state}]
    return _result("promotion_history_for_rule", {"ruleId": rule_id}, "ok", results, notes)


QUERIES = {
    "evidence_supporting_rule": evidence_supporting_rule,
    "evidence_contradicting_rule": evidence_contradicting_rule,
    "unresolved_questions_blocking_family": unresolved_questions_blocking_family,
    "assertions_from_source": assertions_from_source,
    "rules_lacking_primary_evidence": rules_lacking_primary_evidence,
    "rules_with_unresolved_contradictions": rules_with_unresolved_contradictions,
    "rules_without_replay_validation": rules_without_replay_validation,
    "rules_eligible_for_modeling_review": rules_eligible_for_modeling_review,
    "rules_blocked_from_paper_trading": rules_blocked_from_paper_trading,
    "rule_version_diff": rule_version_diff,
    "adr007_questions_informed_by_source": adr007_questions_informed_by_source,
    "known_facts_about_trader": known_facts_about_trader,
    "explicit_vs_inferred": explicit_vs_inferred,
    "owner_decisions_affecting_entity": owner_decisions_affecting_entity,
    "promotion_history_for_rule": promotion_history_for_rule,
}


def main():
    parser = argparse.ArgumentParser(description="Run a read-only PROGRAM-003 Knowledge Graph query.")
    parser.add_argument("query", choices=sorted(QUERIES.keys()))
    parser.add_argument("args", nargs="*")
    parser.add_argument("--repo-root", default=REPO_ROOT)
    parser.add_argument("--ti-root", default=None)
    parser.add_argument("--graph-root", default=None)
    args = parser.parse_args()

    repo_root = os.path.abspath(args.repo_root)
    ti_root = args.ti_root or os.path.join(repo_root, "docs", "trader-intelligence")
    graph_root = args.graph_root or os.path.join(ti_root, "graph")

    idx = GraphIndex.load(repo_root, ti_root, graph_root)
    result = QUERIES[args.query](idx, *args.args)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

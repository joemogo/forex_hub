#!/usr/bin/env python3
"""PROGRAM-003 Phase 1 test suite. Pure stdlib (unittest). Run with:

    python3 -m unittest discover -s tests/trader_intelligence -p 'test_*.py' -v

or directly:

    python3 tests/trader_intelligence/test_graph.py

Uses the real repository docs/trader-intelligence data wherever practical
(TestRealProductionBuild), and merges synthetic, clearly-marked test-only
fixtures (tests/trader_intelligence/fixtures/) into a temporary copy for
everything the real repository has no data for yet -- these fixtures never
touch docs/trader-intelligence/.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts", "trader_intelligence")
FIXTURES_DIR = os.path.join(REPO_ROOT, "tests", "trader_intelligence", "fixtures")
TI_ROOT = os.path.join(REPO_ROOT, "docs", "trader-intelligence")
GRAPH_ROOT = os.path.join(TI_ROOT, "graph")

sys.path.insert(0, SCRIPTS_DIR)
import graph_common as gc          # noqa: E402
import build_graph                 # noqa: E402
import validate_graph              # noqa: E402
import query_graph                 # noqa: E402


def _copy_fixture(name, dest_dir, dest_filename=None):
    os.makedirs(dest_dir, exist_ok=True)
    shutil.copy(os.path.join(FIXTURES_DIR, name), os.path.join(dest_dir, dest_filename or os.path.basename(name)))


class TempRepo:
    """Builds a throwaway copy of docs/trader-intelligence so tests can add
    synthetic data and run destructive scenarios (duplicates, broken refs)
    without ever touching the real repository."""

    def __init__(self):
        self.root = tempfile.mkdtemp(prefix="mogo_graph_test_")
        self.ti_root = os.path.join(self.root, "docs", "trader-intelligence")
        self.graph_root = os.path.join(self.ti_root, "graph")
        shutil.copytree(TI_ROOT, self.ti_root)

    def tjr_dir(self, sub):
        d = os.path.join(self.ti_root, "traders", "tjr", sub)
        os.makedirs(d, exist_ok=True)
        return d

    def decisions_dir(self):
        d = os.path.join(self.graph_root, "decisions")
        os.makedirs(d, exist_ok=True)
        return d

    def add_happy_path(self):
        _copy_fixture("happy_path/source.json", self.tjr_dir("sources"))
        _copy_fixture("happy_path/segment.json", self.tjr_dir("segments"))
        _copy_fixture("happy_path/assertion_explicit.json", self.tjr_dir("assertions"))
        _copy_fixture("happy_path/assertion_inferred.json", self.tjr_dir("assertions"), "assertion_inferred.json")
        _copy_fixture("happy_path/rule.json", self.tjr_dir("rules"))
        _copy_fixture("happy_path/rule_evidence.json", self.tjr_dir("rule-evidence"))
        _copy_fixture("happy_path/rule_version.json", self.tjr_dir("rule-versions"))
        _copy_fixture("happy_path/contradiction.json", self.tjr_dir("contradictions"))
        _copy_fixture("happy_path/owner_decision.json", self.decisions_dir(), "synthetic-owner-decision.json")

    def cleanup(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def build(self):
        return build_graph.build(self.root, self.ti_root, self.graph_root)


# ---------------------------------------------------------------------------
# Unit tests: deterministic IDs, canonical JSON, hashing, promotion enum
# ---------------------------------------------------------------------------

class TestDeterministicIdsAndHashing(unittest.TestCase):
    def test_make_node_id_format(self):
        self.assertEqual(gc.make_node_id("TRADER", "TJR"), "NODE|TRADER|TJR")

    def test_make_node_id_rejects_unknown_type(self):
        with self.assertRaises(ValueError):
            gc.make_node_id("NOT_A_TYPE", "X")

    def test_make_edge_id_short_form(self):
        eid = gc.make_edge_id("BELONGS_TO_TRADER", "SF|TJR|X", "TJR")
        self.assertEqual(eid, "EDGE|BELONGS_TO_TRADER|SF|TJR|X|TJR")

    def test_make_edge_id_long_form_is_deterministic_and_stable(self):
        long_from = "SRC|TJR|20260101|001|SEG|001|ASSERT|" + ("0" * 200)
        eid1 = gc.make_edge_id("SUPPORTS", long_from, "RULE|TJR|ENTRY|X")
        eid2 = gc.make_edge_id("SUPPORTS", long_from, "RULE|TJR|ENTRY|X")
        self.assertEqual(eid1, eid2)
        self.assertLess(len(eid1), len(long_from) + 50)
        self.assertIn("~", eid1)

    def test_make_edge_id_rejects_unknown_type(self):
        with self.assertRaises(ValueError):
            gc.make_edge_id("NOT_AN_EDGE_TYPE", "a", "b")

    def test_canonical_json_is_key_order_independent(self):
        a = {"b": 1, "a": 2, "nested": {"z": 1, "y": 2}}
        b = {"a": 2, "nested": {"y": 2, "z": 1}, "b": 1}
        self.assertEqual(gc.canonical_json_bytes(a), gc.canonical_json_bytes(b))

    def test_canonical_json_preserves_array_order(self):
        a = {"x": [1, 2, 3]}
        b = {"x": [3, 2, 1]}
        self.assertNotEqual(gc.canonical_json_bytes(a), gc.canonical_json_bytes(b))

    def test_content_hash_deterministic_and_sha256(self):
        obj = {"a": 1, "b": [1, 2]}
        h1 = gc.content_hash_of(obj)
        h2 = gc.content_hash_of(dict(reversed(list(obj.items()))))
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)
        int(h1, 16)  # raises ValueError if not valid hex

    def test_promotion_states_enum_completeness(self):
        schema_path = os.path.join(GRAPH_ROOT, "schema", "promotion-state.schema.json")
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        self.assertEqual(gc.PROMOTION_STATES, schema["enum"])
        self.assertEqual(len(gc.PROMOTION_STATES), 18)
        self.assertEqual(gc.PROMOTION_STATES[0], "DISCOVERED")
        self.assertEqual(gc.PROMOTION_STATES[-1], "LIVE_APPROVED")


# ---------------------------------------------------------------------------
# Real production data: the graph as it exists in the actual repository
# ---------------------------------------------------------------------------

class TestRealProductionBuild(unittest.TestCase):
    def test_clean_build_zero_blocking_findings(self):
        nodes, edges, findings, raw = gc.build_nodes_and_edges(REPO_ROOT, TI_ROOT, GRAPH_ROOT)
        self.assertEqual(findings, [], "construction-time findings against real data should be empty")
        report = validate_graph.run_integrity_checks(nodes, edges, raw, findings, "BUILD|TESTONLY|001")
        self.assertEqual(report["summary"]["ERROR"], 0, report["findings"])
        self.assertEqual(report["summary"]["FATAL"], 0, report["findings"])

    def test_expected_node_and_edge_counts(self):
        nodes, edges, findings, raw = gc.build_nodes_and_edges(REPO_ROOT, TI_ROOT, GRAPH_ROOT)
        counts = {}
        for n in nodes:
            counts[n["nodeType"]] = counts.get(n["nodeType"], 0) + 1
        self.assertEqual(counts.get("TRADER"), 3)
        self.assertEqual(counts.get("STRATEGY_FAMILY"), 3)
        self.assertEqual(counts.get("UNRESOLVED_QUESTION"), 35)
        self.assertEqual(counts.get("OWNER_DECISION"), 1)
        self.assertEqual(len(nodes), 42)
        self.assertEqual(len(edges), 76)

    def test_no_trader_self_belongs_to_trader_edge(self):
        nodes, edges, findings, raw = gc.build_nodes_and_edges(REPO_ROOT, TI_ROOT, GRAPH_ROOT)
        for e in edges:
            if e["edgeType"] == "BELONGS_TO_TRADER":
                self.assertNotEqual(e["fromNodeId"], e["toNodeId"])

    def test_strategy_family_backrefs_all_resolve(self):
        nodes, edges, findings, raw = gc.build_nodes_and_edges(REPO_ROOT, TI_ROOT, GRAPH_ROOT)
        report = validate_graph.run_integrity_checks(nodes, edges, raw, findings, "BUILD|TESTONLY|002")
        backref_findings = [f for f in report["findings"] if f["category"] == "INVALID_STRATEGY_FAMILY_REFERENCE"]
        self.assertEqual(backref_findings, [])


# ---------------------------------------------------------------------------
# Merged fixture build: exercises every node/edge type at least once
# ---------------------------------------------------------------------------

class TestMergedFixtureBuild(unittest.TestCase):
    def setUp(self):
        self.repo = TempRepo()
        self.repo.add_happy_path()

    def tearDown(self):
        self.repo.cleanup()

    def test_build_promotes_cleanly(self):
        promoted, manifest, report, nodes, edges = self.repo.build()
        self.assertTrue(promoted, report["findings"])
        self.assertEqual(report["summary"]["ERROR"], 0, report["findings"])
        self.assertEqual(report["summary"]["FATAL"], 0, report["findings"])

    def test_every_required_node_type_present_or_explicitly_absent(self):
        _promoted, _m, _r, nodes, _edges = self.repo.build()
        present = {n["nodeType"] for n in nodes}
        # Present with real+synthetic data:
        for t in ("TRADER", "STRATEGY_FAMILY", "RESEARCH_SOURCE", "SOURCE_SEGMENT",
                  "STRATEGY_ASSERTION", "RULE_EVIDENCE", "STRATEGY_RULE", "RULE_VERSION",
                  "RULE_CONTRADICTION", "UNRESOLVED_QUESTION", "OWNER_DECISION"):
            self.assertIn(t, present, "%s should have at least one node" % t)
        # Deliberately absent in Phase 1 (no CHART_EXAMPLE/RESEARCH_INTAKE_REPORT
        # fixtures were required or created):
        for t in ("CHART_EXAMPLE", "RESEARCH_INTAKE_REPORT"):
            self.assertNotIn(t, present)

    def test_supports_and_evidences_edges_both_created(self):
        _promoted, _m, _r, nodes, edges = self.repo.build()
        edge_types = {e["edgeType"] for e in edges}
        self.assertIn("SUPPORTS", edge_types)
        self.assertIn("EVIDENCES", edge_types)
        self.assertIn("CONTRADICTS", edge_types)
        self.assertIn("VERSION_OF", edge_types)
        self.assertIn("BELONGS_TO_STRATEGY_FAMILY", edge_types)

    def test_validates_and_implements_never_populated(self):
        _promoted, _m, _r, _nodes, edges = self.repo.build()
        edge_types = {e["edgeType"] for e in edges}
        self.assertNotIn("VALIDATES", edge_types)
        self.assertNotIn("IMPLEMENTS", edge_types)

    def test_deterministic_rebuild_byte_identical(self):
        _p1, _m1, _r1, nodes1, edges1 = self.repo.build()
        _p2, _m2, _r2, nodes2, edges2 = self.repo.build()
        self.assertEqual(gc.pretty_json(nodes1), gc.pretty_json(nodes2))
        self.assertEqual(gc.pretty_json(edges1), gc.pretty_json(edges2))

    def test_atomic_write_failure_does_not_clobber_last_good_artifacts(self):
        promoted1, _m1, _r1, _n1, _e1 = self.repo.build()
        self.assertTrue(promoted1)
        nodes_path = os.path.join(self.repo.graph_root, "build", "nodes.json")
        edges_path = os.path.join(self.repo.graph_root, "build", "edges.json")
        manifest_path = os.path.join(self.repo.graph_root, "build", "manifest.json")
        with open(nodes_path, "rb") as f:
            good_nodes = f.read()
        with open(edges_path, "rb") as f:
            good_edges = f.read()
        with open(manifest_path, "rb") as f:
            good_manifest = f.read()

        _copy_fixture("broken/rule_duplicate.json", self.repo.tjr_dir("rules"))
        promoted2, _m2, report2, _n2, _e2 = self.repo.build()
        self.assertFalse(promoted2)
        self.assertGreater(report2["summary"]["FATAL"] + report2["summary"]["ERROR"], 0)

        with open(nodes_path, "rb") as f:
            self.assertEqual(f.read(), good_nodes)
        with open(edges_path, "rb") as f:
            self.assertEqual(f.read(), good_edges)
        with open(manifest_path, "rb") as f:
            self.assertEqual(f.read(), good_manifest)

        report_path = os.path.join(self.repo.graph_root, "reports", "integrity-report.json")
        with open(report_path, "r", encoding="utf-8") as f:
            latest_report = json.load(f)
        self.assertGreater(latest_report["summary"]["FATAL"] + latest_report["summary"]["ERROR"], 0)

    def test_query_correctness_against_merged_graph(self):
        self.repo.build()
        idx = query_graph.GraphIndex.load(self.repo.root, self.repo.ti_root, self.repo.graph_root)

        r = query_graph.evidence_supporting_rule(idx, "RULE|TJR|ENTRY|SYNTHETIC_TEST_ENTRY_RULE")
        self.assertEqual(r["status"], "ok")
        self.assertGreaterEqual(r["resultCount"], 2)  # SUPPORTS (assertion) + EVIDENCES (bundle)

        r = query_graph.evidence_contradicting_rule(idx, "RULE|TJR|ENTRY|SYNTHETIC_TEST_ENTRY_RULE")
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["resultCount"], 1)

        r = query_graph.explicit_vs_inferred(idx, "TJR")
        self.assertEqual(r["status"], "ok")
        self.assertEqual(len(r["results"][0]["explicit"]), 1)
        self.assertEqual(len(r["results"][0]["inferred"]), 1)

        r = query_graph.owner_decisions_affecting_entity(idx, "RULE|TJR|ENTRY|SYNTHETIC_TEST_ENTRY_RULE")
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["resultCount"], 1)

        r = query_graph.rule_version_diff(idx, "RULE|TJR|ENTRY|SYNTHETIC_TEST_ENTRY_RULE", 1, 1)
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["results"], [{}])  # v1 vs v1: no differences

        r = query_graph.promotion_history_for_rule(idx, "RULE|TJR|ENTRY|SYNTHETIC_TEST_ENTRY_RULE")
        self.assertEqual(r["status"], "ok")
        self.assertEqual(len(r["results"][0]["versions"]), 1)
        self.assertIsNone(r["results"][0]["promotionState"])
        self.assertTrue(r["uncertaintyNotes"])

        r = query_graph.evidence_supporting_rule(idx, "RULE|DOES_NOT_EXIST|X|Y")
        self.assertEqual(r["status"], "not_found")

    def test_modeled_rule_without_edge_evidence_is_flagged(self):
        """A rule declaring sourceEvidenceIds but with no RuleEvidence entity
        actually pointing back at it must be caught, not silently trusted."""
        repo2 = TempRepo()
        rule_dir = repo2.tjr_dir("rules")
        with open(os.path.join(FIXTURES_DIR, "happy_path", "rule.json"), "r", encoding="utf-8") as f:
            rule = json.load(f)
        rule["ruleId"] = "RULE|TJR|ENTRY|SYNTHETIC_UNBACKED_RULE"
        rule["sourceEvidenceIds"] = ["EVID|RULE|TJR|ENTRY|SYNTHETIC_UNBACKED_RULE|999"]  # no such evidence file exists
        os.makedirs(rule_dir, exist_ok=True)
        with open(os.path.join(rule_dir, "unbacked_rule.json"), "w", encoding="utf-8") as f:
            json.dump(rule, f)
        try:
            promoted, manifest, report, nodes, edges = repo2.build()
            self.assertFalse(promoted)
            categories = {f["category"] for f in report["findings"]}
            self.assertIn("MODELED_RULE_WITHOUT_EVIDENCE", categories)
        finally:
            repo2.cleanup()


# ---------------------------------------------------------------------------
# Isolated negative-path tests: missing reference / circular supersession
# ---------------------------------------------------------------------------

class TestMissingReferenceDetection(unittest.TestCase):
    def test_broken_assertion_reference_is_caught(self):
        repo = TempRepo()
        try:
            _copy_fixture("broken/assertion_missing_ref.json", repo.tjr_dir("assertions"))
            promoted, manifest, report, nodes, edges = repo.build()
            self.assertFalse(promoted)
            categories = {f["category"] for f in report["findings"]}
            self.assertIn("MISSING_REFERENCE", categories)
        finally:
            repo.cleanup()


class TestCircularSupersessionDetection(unittest.TestCase):
    def test_circular_supersession_is_caught(self):
        repo = TempRepo()
        try:
            _copy_fixture("happy_path/source.json", repo.tjr_dir("sources"))
            _copy_fixture("happy_path/segment.json", repo.tjr_dir("segments"))
            _copy_fixture("broken/assertion_circular_a.json", repo.tjr_dir("assertions"))
            _copy_fixture("broken/assertion_circular_b.json", repo.tjr_dir("assertions"))
            promoted, manifest, report, nodes, edges = repo.build()
            self.assertFalse(promoted)
            categories = {f["category"] for f in report["findings"]}
            self.assertIn("CIRCULAR_SUPERSESSION", categories)
        finally:
            repo.cleanup()


class TestDuplicateIdDetection(unittest.TestCase):
    def test_duplicate_rule_id_is_caught(self):
        repo = TempRepo()
        try:
            _copy_fixture("happy_path/rule.json", repo.tjr_dir("rules"))
            _copy_fixture("broken/rule_duplicate.json", repo.tjr_dir("rules"), "rule_duplicate_2.json")
            promoted, manifest, report, nodes, edges = repo.build()
            self.assertFalse(promoted)
            categories = {f["category"] for f in report["findings"]}
            self.assertTrue({"DUPLICATE_ENTITY_ID", "DUPLICATE_NODE_ID"} & categories)
        finally:
            repo.cleanup()


# ---------------------------------------------------------------------------
# No-runtime-coupling guard (belt-and-suspenders alongside the manual grep in
# the pre-commit report -- keeps this invariant covered by the test suite too)
# ---------------------------------------------------------------------------

class TestNoRuntimeCoupling(unittest.TestCase):
    def test_index_html_never_references_trader_intelligence(self):
        index_path = os.path.join(REPO_ROOT, "index.html")
        with open(index_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertNotIn("trader-intelligence", content)


if __name__ == "__main__":
    unittest.main(verbosity=2)

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
import hashlib
import json
import os
import re
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


# Every evidence/ record collection that a *scratch* copy of the tree must
# start empty. evidence/schema/ is structural, not data, so it is kept.
SCRATCH_EVIDENCE_COLLECTIONS = tuple(sorted(
    # B-32: the ENTITY collections are derived from graph_common so a new graph
    # entity type cannot be added to discovery and forgotten here -- that omission
    # seeded every fixture with 259 production observations. The extras below are
    # collections that are NOT graph entities (links are edges; lifecycle,
    # annotations and reports are not nodes) and so must stay listed by hand.
    set(gc.EVIDENCE_ENTITY_COLLECTIONS)
    | {"links", "lifecycle", "annotations", "reports"}))


def clear_scratch_evidence_tree(ti_root):
    """A copied docs/trader-intelligence tree is used by these fixtures as a
    SCRATCH evidence tree. That was implicitly true only while production
    evidence/ was empty; once a real transcript intake exists on disk,
    copytree would silently seed every fixture with production records and
    quietly invalidate their assertions. Emptying each record collection on
    copy makes the scratch guarantee explicit instead of accidental."""
    evidence_root = os.path.join(ti_root, "evidence")
    for name in SCRATCH_EVIDENCE_COLLECTIONS:
        d = os.path.join(evidence_root, name)
        if os.path.isdir(d):
            shutil.rmtree(d)
        os.makedirs(d, exist_ok=True)


def independent_content_hash(entity):
    """The expected contentHash, computed WITHOUT gc.content_hash_of.

    Deliberate duplication. Computing the expected value with the function the
    builder used proves only that both sides called the same function: an
    independent verifier gutted `content_hash_of` so it dropped every list- and
    dict-valued field, and every "contentHash matches" assertion in this
    repository stayed green.
    """
    return hashlib.sha256(
        json.dumps(entity, sort_keys=True, separators=(",", ":"),
                   ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


# Pinned by IDENTITY, not by count, and listed here rather than derived from
# graph_common so that a discovery glob silently matching nothing is visible.
# Breaking one glob removed an entire node type from the production graph while
# every structural assertion stayed green, because the test rebuilt its
# expectation from the same generator the build had used.
EXPECTED_ENTITY_DIRS = {
    "docs/trader-intelligence/evidence/blueprints",
    "docs/trader-intelligence/evidence/claims",
    "docs/trader-intelligence/evidence/contradictions",
    "docs/trader-intelligence/evidence/gaps",
    "docs/trader-intelligence/evidence/hypotheses",
    "docs/trader-intelligence/evidence/intake",
    "docs/trader-intelligence/evidence/items",
    "docs/trader-intelligence/evidence/observations",   # B-32
    "docs/trader-intelligence/evidence/profiles",
    "docs/trader-intelligence/evidence/proposals",
    "docs/trader-intelligence/evidence/questions",
    "docs/trader-intelligence/evidence/review-queue",
    "docs/trader-intelligence/evidence/segments",
    "docs/trader-intelligence/evidence/sources",
    "docs/trader-intelligence/graph/decisions",
    "docs/trader-intelligence/traders/*/open-questions",
    "docs/trader-intelligence/traders/*/strategy-families",
    "docs/trader-intelligence/traders/alex-g",
    "docs/trader-intelligence/traders/ict",
    "docs/trader-intelligence/traders/jvm",
    "docs/trader-intelligence/traders/rayner-teo",
    "docs/trader-intelligence/traders/tjr",
}

# Every edge type the production build is expected to derive. Pinned by identity
# so that an entire derivation silently producing nothing is caught -- a build
# emitting one edge instead of five thousand satisfied `len(edges) > 0`.
EXPECTED_EDGE_TYPES = {
    "BELONGS_TO_TRADER", "BLOCKED_BY", "BLOCKS", "BLUEPRINT_DERIVED_FROM_CLAIM",
    "BLUEPRINT_HAS_GAP", "CLAIM_SUPPORTS_HYPOTHESIS", "CONTEXTUALIZES",
    "CONTRADICTS", "DERIVED_FROM", "EVIDENCE_FROM_SEGMENT", "PROPOSES_RULE",
    "RAISES_QUESTION", "REFERENCES", "REQUIRES_REVIEW", "RESOLVED_BY_EVIDENCE",
    "SEGMENT_OF", "SUPPORTS",
}

# OwnerDecision records are governance artifacts: a new one appearing in the
# graph is an authorization event, not corpus growth. Pinned by identity so that
# adding one is a deliberate edit here rather than something that slips in.
EXPECTED_OWNER_DECISIONS = {
    "DECISION|MOGO|20260725|001", "DECISION|MOGO|20260725|002",
    "DECISION|MOGO|20260727|003", "DECISION|MOGO|20260727|004",
    "DECISION|MOGO|20260727|005", "DECISION|MOGO|20260727|006",
    # 007 records the TradingView ClaudeBot-exclusion ruling. It authorizes
    # NOTHING -- approvalScope research_only, every authorization flag false --
    # so it is a governance record of a REFUSAL, not a grant. Listed here for the
    # same reason as the grants: the set must change only by an explicit edit.
    "DECISION|MOGO|20260819|007",
}


class TempRepo:
    """Builds a throwaway copy of docs/trader-intelligence so tests can add
    synthetic data and run destructive scenarios (duplicates, broken refs)
    without ever touching the real repository."""

    def __init__(self):
        self.root = tempfile.mkdtemp(prefix="mogo_graph_test_")
        self.ti_root = os.path.join(self.root, "docs", "trader-intelligence")
        self.graph_root = os.path.join(self.ti_root, "graph")
        shutil.copytree(TI_ROOT, self.ti_root)
        clear_scratch_evidence_tree(self.ti_root)

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

    def test_production_build_is_structurally_sound_and_fully_sourced(self):
        """Every node traces to a file, nothing is duplicated, no edge dangles.

        This replaces four absolute counts (43 nodes, 79 edges, 35 questions, and
        so on). Those pinned one afternoon's corpus, so every legitimate addition
        broke them, and they said nothing about whether the graph was CORRECT --
        a build that emitted 43 fabricated nodes would have passed.

        What the counts were reaching for is structural: the graph is a faithful
        1:1 projection of the entity files on disk. That is asserted here directly,
        and it keeps holding as the corpus grows.
        """
        nodes, edges, findings, raw = gc.build_nodes_and_edges(REPO_ROOT, TI_ROOT, GRAPH_ROOT)
        self.assertGreater(len(nodes), 0, "empty graph -- the checks below would be vacuous")
        self.assertGreater(len(edges), 0, "no edges -- the edge checks below would be vacuous")

        node_ids = [n["nodeId"] for n in nodes]
        self.assertEqual(len(node_ids), len(set(node_ids)),
                         "duplicate nodeId: the same entity was emitted more than once")
        edge_ids = [e["edgeId"] for e in edges]
        self.assertEqual(len(edge_ids), len(set(edge_ids)), "duplicate edgeId")

        # Compare against the entities the discovery pass actually found, rather
        # than re-loading each sourceFile: UNRESOLVED_QUESTION records live as
        # array items inside one cross-reference file, so a whole-file hash is
        # simply the wrong quantity for them. Reading it back through
        # discover_entities also makes this an exact 1:1 correspondence -- it
        # catches an OMITTED entity, which no count of nodes ever could.
        discovered = {}
        entity_by_id = {}
        for node_type, entity, source_file in gc.discover_entities(
                REPO_ROOT, TI_ROOT, GRAPH_ROOT):
            node_id = gc.make_node_id(node_type, entity[gc.NODE_TYPE_FIELD_MAP[node_type]["id_field"]])
            discovered[node_id] = (node_type, source_file, gc.content_hash_of(entity))
            entity_by_id[node_id] = entity

        self.assertEqual(set(node_ids), set(discovered),
                         "the graph's nodes are not exactly the entities on disk")

        for node in nodes:
            self.assertIn(node["nodeType"], gc.NODE_TYPES,
                          "%s has unregistered nodeType %s" % (node["nodeId"], node["nodeType"]))
            node_type, source_file, content_hash = discovered[node["nodeId"]]
            self.assertEqual(node["nodeType"], node_type)
            self.assertEqual(node["sourceFile"], source_file)
            self.assertEqual(node["contentHash"], content_hash,
                             "%s does not match the entity discovered in %s"
                             % (node["nodeId"], source_file))
            self.assertEqual(node["contentHash"], independent_content_hash(entity_by_id[node["nodeId"]]),
                             "%s's contentHash does not cover its entity"
                             % node["nodeId"])
            path = os.path.join(REPO_ROOT, node["sourceFile"])
            self.assertTrue(os.path.isfile(path),
                            "%s cites sourceFile %s, which does not exist"
                            % (node["nodeId"], node["sourceFile"]))
            # The cited file must actually contain this entity. Existence alone is
            # satisfied by a path pointing at a DIFFERENT real file, which is what
            # a wrong relpath computation looks like. A substring check over the
            # raw text handles both shapes uniformly -- one entity per file, and
            # the cross-reference file whose entities are array items.
            with open(path, "r", encoding="utf-8") as handle:
                raw = handle.read()
            self.assertIn(node["entityId"], raw,
                          "%s cites %s, but that file does not contain the entity"
                          % (node["nodeId"], node["sourceFile"]))

        known = set(node_ids)
        for edge in edges:
            self.assertIn(edge["edgeType"], gc.EDGE_TYPES,
                          "%s has unregistered edgeType %s" % (edge["edgeId"], edge["edgeType"]))
            for end in ("fromNodeId", "toNodeId"):
                self.assertIn(edge[end], known,
                              "%s points at %s, which is not a node in this graph"
                              % (edge["edgeId"], edge[end]))

        # --- Oracles that do NOT flow from discover_entities ------------------
        # Everything above compares the graph against the same generator the
        # build itself used, so a bug INSIDE discovery is invisible to it. These
        # three constrain it from outside.
        emitted_dirs = {re.sub(r"/traders/[^/]+/", "/traders/*/", os.path.dirname(n["sourceFile"]))
                        for n in nodes}
        self.assertEqual(emitted_dirs, EXPECTED_ENTITY_DIRS,
                         "the set of directories contributing entities changed; a "
                         "discovery glob that matches nothing looks exactly like this")

        self.assertEqual({e["edgeType"] for e in edges}, EXPECTED_EDGE_TYPES,
                         "an edge derivation produced nothing at all")

        self.assertEqual({n["entityId"] for n in nodes if n["nodeType"] == "OWNER_DECISION"},
                         EXPECTED_OWNER_DECISIONS,
                         "the set of OwnerDecision records changed -- that is a "
                         "governance event and must be an explicit edit here")

        # Independent COUNTS, derived from the entities' own reference fields
        # rather than from the edge builder. Identity-pinning the edge types above
        # catches a derivation that produces nothing at all, but not one that drops
        # most of its edges -- a build emitting 1 edge instead of 5142 satisfied
        # every other assertion here.
        traders = {n["entityId"] for n in nodes if n["nodeType"] == "TRADER"}
        expected_belongs = sum(1 for n in nodes
                               if n.get("traderId") in traders and n["nodeType"] != "TRADER")
        self.assertEqual(sum(1 for e in edges if e["edgeType"] == "BELONGS_TO_TRADER"),
                         expected_belongs)

        # (edgeType, source nodeType, reference field, target nodeType). A
        # reference that does not resolve produces a MISSING_REFERENCE finding
        # instead of an edge, so only resolving references are counted.
        derivations = [
            ("CLAIM_SUPPORTS_HYPOTHESIS", "HYPOTHESIS", ("sourceClaimIds",), "CLAIM"),
            ("BLUEPRINT_DERIVED_FROM_CLAIM", "STRATEGY_BLUEPRINT",
             ("sourceLineage", "claimIds"), "CLAIM"),
            ("RAISES_QUESTION", "EVIDENCE_QUESTION", ("claimId",), "CLAIM"),
        ]
        checked = 0
        for edge_type, source_type, path, target_type in derivations:
            targets = {n["entityId"] for n in nodes if n["nodeType"] == target_type}
            expected = 0
            for node_id, entity in entity_by_id.items():
                if discovered[node_id][0] != source_type:
                    continue
                value = entity
                for key in path:
                    value = (value or {}).get(key)
                refs = value if isinstance(value, list) else ([value] if value else [])
                expected += sum(1 for ref in refs if ref in targets)
            self.assertGreater(expected, 0,
                               "%s derives nothing from the corpus -- this check "
                               "would be vacuous" % edge_type)
            self.assertEqual(sum(1 for e in edges if e["edgeType"] == edge_type),
                             expected,
                             "%s edge count does not match what the entities declare"
                             % edge_type)
            checked += 1
        self.assertEqual(checked, len(derivations))

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
            # Asserted SPECIFICALLY, not as an OR over two categories. The OR read
            # as though either guard would do; in fact this fixture never produces
            # DUPLICATE_ENTITY_ID at all, so the whole assertion rested on
            # DUPLICATE_NODE_ID while appearing to allow an alternative. Naming the
            # category that actually fires is what makes deleting it fail.
            self.assertIn("DUPLICATE_NODE_ID", categories)
        finally:
            repo.cleanup()

    def test_validate_graph_catches_a_duplicate_node_id_directly(self):
        """The VALIDATOR's guard, which the fixture test above does not reach.

        DUPLICATE_NODE_ID is emitted twice in this codebase: at construction
        (graph_common) and at validation (validate_graph). The fixture test goes
        through build_graph, so it exercises the construction one only -- deleting
        the validator's guard outright changed nothing anywhere in the suite. Both
        are guards; both need a control that fails when they are removed.
        """
        import validate_graph as vg
        node = self.minimal_node()
        report = vg.run_integrity_checks([node, dict(node)], [], {}, [], "TEST")
        self.assertIn("DUPLICATE_NODE_ID", {f["category"] for f in report["findings"]})

    def minimal_node(self):
        return {"nodeId": "NODE|TRADER|T", "nodeType": "TRADER", "entityId": "T",
                "sourceFile": "x.json", "contentHash": "h", "traderId": "T",
                "strategyFamilyId": None, "label": "", "status": "active",
                "createdAt": "", "updatedAt": None, "metadata": {}, "generated": True}

    def test_duplicate_edge_id_is_caught(self):
        """The sibling guard, which had no coverage of any kind."""
        import validate_graph as vg
        node = self.minimal_node()
        edge = {"edgeId": "EDGE|SAME", "edgeType": "BELONGS_TO_TRADER",
                "fromNodeId": "NODE|TRADER|T", "toNodeId": "NODE|TRADER|T",
                "entityId": "T", "traderId": "T", "sourceFile": "x.json",
                "createdAt": "", "metadata": {}, "generated": True}
        report = vg.run_integrity_checks([node], [edge, dict(edge)], {}, [], "TEST")
        self.assertIn("DUPLICATE_EDGE_ID", {f["category"] for f in report["findings"]})


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


# ---------------------------------------------------------------------------
# B-32: TradeObservation as a first-class graph node
# ---------------------------------------------------------------------------

class TradeObservationCase(unittest.TestCase):
    """Shared fixture: a scratch tree holding only what each test writes.

    Everything here builds from records the test authored itself. Copying the
    live corpus would make these assertions depend on whatever the running
    instance happened to preserve that hour -- the failure mode that has already
    been found repeatedly in this repository.
    """

    def setUp(self):
        self.repo = TempRepo()

    def tearDown(self):
        self.repo.cleanup()

    def _evdir(self, name):
        d = os.path.join(self.repo.ti_root, "evidence", name)
        os.makedirs(d, exist_ok=True)
        return d

    def source(self, source_id="EVSRC|MOGO|20260819|001", source_type="paper_trade", **extra):
        rec = {"sourceId": source_id, "sourceType": source_type,
               "title": "capture " + source_id, "storageLocationType": "repository",
               "provenanceStatus": "owner_supplied", "createdAt": "2026-08-19T00:00:00Z"}
        rec.update(extra)
        name = source_id.replace("|", "_") + ".json"
        with open(os.path.join(self._evdir("sources"), name), "w", encoding="utf-8") as h:
            json.dump(rec, h)
        return rec

    def observation(self, obs_id="TOBS|MOGO|20260819|001",
                    source_id="EVSRC|MOGO|20260819|001", **extra):
        rec = {"observationId": obs_id, "sourceId": source_id, "actor": "MOGO",
               "lane": "RESEARCH", "instrument": "GBP/USD", "direction": "sell",
               "outcome": "Loss", "rMultiple": -1, "strategyId": "alex_g_sr_v1",
               "sourceContentHash": "a" * 64, "createdAt": "2026-08-19T00:00:00Z",
               "schemaVersion": "mogo.trade-observation.v1"}
        rec.update(extra)
        name = obs_id.replace("|", "_") + ".json"
        with open(os.path.join(self._evdir("observations"), name), "w", encoding="utf-8") as h:
            json.dump(rec, h)
        return rec

    def build(self):
        # build_nodes_and_edges returns (nodes, edges, findings, raw_by_entity_id);
        # the fourth is not needed here.
        nodes, edges, findings, _raw = gc.build_nodes_and_edges(
            self.repo.root, self.repo.ti_root, self.repo.graph_root)
        return nodes, edges, findings

    def obs_nodes(self, nodes):
        return [n for n in nodes if n["nodeType"] == "TRADE_OBSERVATION"]

    def derived_edges(self, edges):
        return [e for e in edges if e["edgeType"] == "DERIVED_FROM"]


class TestTradeObservationIsAFirstClassNode(TradeObservationCase):

    def test_an_observation_becomes_a_node_linked_to_its_source(self):
        self.source()
        self.observation()
        nodes, edges, findings = self.build()
        self.assertEqual(len(self.obs_nodes(nodes)), 1)
        obs_node = gc.make_node_id("TRADE_OBSERVATION", "TOBS|MOGO|20260819|001")
        src_node = gc.make_node_id("EVIDENCE_SOURCE", "EVSRC|MOGO|20260819|001")
        edge = [e for e in self.derived_edges(edges) if e["fromNodeId"] == obs_node]
        self.assertEqual(len(edge), 1)
        self.assertEqual(edge[0]["toNodeId"], src_node)
        self.assertEqual([f for f in findings if f["severity"] in ("ERROR", "FATAL")], [])

    def test_the_node_preserves_the_observation_id_verbatim(self):
        # The graph must not mint its own identity for a preserved record.
        self.source()
        self.observation(obs_id="TOBS|MOGO|20260819|042")
        nodes, _edges, _f = self.build()
        self.assertEqual(self.obs_nodes(nodes)[0]["entityId"], "TOBS|MOGO|20260819|042")

    def test_the_node_hash_is_of_the_preserved_record_not_a_projection(self):
        # Computed independently of gc.content_hash_of -- see independent_content_hash.
        self.source()
        rec = self.observation()
        nodes, _e, _f = self.build()
        self.assertEqual(self.obs_nodes(nodes)[0]["contentHash"],
                         independent_content_hash(rec))

    def test_outcome_is_NOT_surfaced_as_node_status(self):
        # "Loss" is a result, not a lifecycle state. Surfacing it as status would
        # let a reader filter the graph for "active" work and silently drop every
        # losing trade.
        self.source()
        self.observation(outcome="Loss")
        nodes, _e, _f = self.build()
        self.assertEqual(self.obs_nodes(nodes)[0]["status"], "active")


class TestNoFabricatedRelationships(TradeObservationCase):
    """The edges that must NOT exist, which is the substantive part of B-32."""

    def test_strategyId_does_NOT_link_an_observation_to_a_strategy_family(self):
        # alex_g_sr_v1 is MOGO's IMPLEMENTATION; SF|ALEX_G|... is the human
        # trader's method. An edge here would let a query walk from MOGO's own
        # paper trades into a human trader's evidence and count one as evidence
        # for the other -- OBSERVED data answering a SOURCE_STATED question.
        self.source()
        self.observation(strategyId="alex_g_sr_v1")
        nodes, edges, _f = self.build()
        obs_node = self.obs_nodes(nodes)[0]
        touching = [e for e in edges if obs_node["nodeId"] in (e["fromNodeId"], e["toNodeId"])]
        self.assertEqual([e["edgeType"] for e in touching], ["DERIVED_FROM"],
                         "an observation must have exactly one relationship: its source")

    def test_an_observation_never_gains_a_trader_edge_EVEN_IF_IT_CLAIMS_ONE(self):
        # The fixture deliberately CARRIES a traderId. Without one, this test passed
        # while the exclusion was absent from the builder -- the guarantee rested on
        # the data happening not to contain the field, and adding it to one record
        # built a real edge putting MOGO's paper trades three hops from a trader's
        # evidence.
        self.source()
        self.observation(traderId="ALEX_G")
        nodes, edges, _f = self.build()
        obs_node = self.obs_nodes(nodes)[0]
        self.assertEqual(
            [e for e in edges
             if e["edgeType"] == "BELONGS_TO_TRADER" and e["fromNodeId"] == obs_node["nodeId"]],
            [], "an observation must not belong to a human trader even when the record "
                "claims one -- it is MOGO's execution, not the trader's")
        self.assertEqual([e["edgeType"] for e in edges
                          if obs_node["nodeId"] in (e["fromNodeId"], e["toNodeId"])],
                         ["DERIVED_FROM"])

    def test_an_observation_never_gains_a_trader_edge(self):
        # No observation record carries a traderId. If one ever did, attributing
        # MOGO's own execution to a human trader is the contamination this guards.
        self.source()
        self.observation()
        nodes, edges, _f = self.build()
        obs_node = self.obs_nodes(nodes)[0]
        self.assertIsNone(obs_node["traderId"])
        self.assertEqual(
            [e for e in edges
             if e["edgeType"] == "BELONGS_TO_TRADER" and e["fromNodeId"] == obs_node["nodeId"]],
            [])

    def test_a_missing_source_produces_a_FINDING_not_a_synthesized_node(self):
        # Fabricating a placeholder source would make the lineage look whole while
        # the artifact it claims to describe does not exist.
        self.observation(source_id="EVSRC|MOGO|20260819|999")
        nodes, edges, findings = self.build()
        self.assertEqual([n for n in nodes if n["nodeType"] == "EVIDENCE_SOURCE"], [])
        self.assertEqual(self.derived_edges(edges), [])
        self.assertTrue(any(f["category"] == "MISSING_REFERENCE" for f in findings))

    def test_an_observation_with_no_sourceId_yields_no_edge_and_no_guess(self):
        # SCOPE, and it was read too broadly once. This asserts only that the GRAPH
        # invents nothing: no edge, no placeholder source. It is NOT a statement that
        # the record is acceptable -- an observation with no sourceId has no derivable
        # population, and adversarial verification used exactly that to move 24
        # observations into UNKNOWN. That is the evidence validator's job and it now
        # reports UNRESOLVED_POPULATION for it; see
        # TestPopulationRebindingIsDetected.test_an_absent_sourceId_is_an_error.
        self.source()
        rec = self.observation()
        del rec["sourceId"]
        with open(os.path.join(self._evdir("observations"),
                               "TOBS_MOGO_20260819_001.json"), "w", encoding="utf-8") as h:
            json.dump(rec, h)
        _n, edges, findings = self.build()
        self.assertEqual(self.derived_edges(edges), [])
        self.assertEqual([f for f in findings if f["severity"] in ("ERROR", "FATAL")], [])


class TestPopulationSeparationSurvivesTheGraph(TradeObservationCase):
    """HISTORICAL / FORWARD / RECONSTRUCTED must not be merged or inverted."""

    def test_observations_of_different_populations_stay_on_separate_sources(self):
        self.source("EVSRC|MOGO|20260819|001", source_type="replay_observation")   # HISTORICAL
        self.source("EVSRC|MOGO|20260819|002", source_type="paper_trade")          # FORWARD
        self.source("EVSRC|MOGO|20260819|003", source_type="journal_entry")        # RECONSTRUCTED
        self.observation("TOBS|MOGO|20260819|001", "EVSRC|MOGO|20260819|001")
        self.observation("TOBS|MOGO|20260819|002", "EVSRC|MOGO|20260819|002")
        self.observation("TOBS|MOGO|20260819|003", "EVSRC|MOGO|20260819|003")
        _n, edges, _f = self.build()
        pairs = {(e["fromNodeId"], e["toNodeId"]) for e in self.derived_edges(edges)}
        expected = {(gc.make_node_id("TRADE_OBSERVATION", "TOBS|MOGO|20260819|00%d" % i),
                     gc.make_node_id("EVIDENCE_SOURCE", "EVSRC|MOGO|20260819|00%d" % i))
                    for i in (1, 2, 3)}
        self.assertEqual(pairs, expected,
                         "an observation must point at ITS OWN source; a crossed edge "
                         "silently reclassifies replay evidence as forward evidence")

    def test_the_graph_does_not_denormalise_population_onto_the_node(self):
        # Population is derived from the source's sourceType, never stored on the
        # observation. A copy on the node would be a second source of truth that
        # can disagree with the source record.
        self.source("EVSRC|MOGO|20260819|001", source_type="replay_observation")
        self.observation()
        nodes, _e, _f = self.build()
        node = self.obs_nodes(nodes)[0]
        self.assertNotIn("population", node)
        self.assertNotIn("population", node["metadata"])

    def test_evidence_class_mutation_on_the_source_does_not_alter_the_observation_node(self):
        # Changing the SOURCE's type changes the derived population; it must not
        # rewrite the observation node's own identity or hash.
        self.source("EVSRC|MOGO|20260819|001", source_type="replay_observation")
        rec = self.observation()
        before = self.obs_nodes(self.build()[0])[0]
        self.source("EVSRC|MOGO|20260819|001", source_type="paper_trade")
        after = self.obs_nodes(self.build()[0])[0]
        self.assertEqual(before["contentHash"], after["contentHash"])
        self.assertEqual(before["entityId"], after["entityId"])
        self.assertEqual(before["contentHash"], independent_content_hash(rec))


class TestAdversarialInputs(TradeObservationCase):

    def test_two_observations_with_the_same_id_are_a_FATAL_duplicate(self):
        self.source()
        self.observation("TOBS|MOGO|20260819|001")
        # Same observationId, different filename -- an identity collision.
        rec = dict(self.observation("TOBS|MOGO|20260819|001"))
        with open(os.path.join(self._evdir("observations"), "zz_collision.json"),
                  "w", encoding="utf-8") as h:
            json.dump(rec, h)
        nodes, _e, findings = self.build()
        self.assertEqual(len(self.obs_nodes(nodes)), 1)
        self.assertTrue(any(f["category"] == "DUPLICATE_NODE_ID" and f["severity"] == "FATAL"
                            for f in findings))

    def test_distinct_observations_sharing_one_source_all_link(self):
        self.source()
        for i in range(1, 6):
            self.observation("TOBS|MOGO|20260819|00%d" % i)
        _n, edges, findings = self.build()
        self.assertEqual(len(self.derived_edges(edges)), 5)
        self.assertEqual([f for f in findings if f["severity"] in ("ERROR", "FATAL")], [])

    def test_discovery_is_sorted_so_the_build_cannot_inherit_directory_order(self):
        # Asserts the PROPERTY, not two runs of the same code.
        #
        # The previous version of this test wrote the same records in a different
        # sequence and compared the two builds. That could never fail: the build
        # sorts, so reversing discovery order produced a byte-identical graph and
        # the mutation survived as an equivalent mutant. It duplicated the
        # idempotency test while claiming to check something else.
        self.source()
        for i in (3, 1, 2):
            self.observation("TOBS|MOGO|20260819|00%d" % i)
        # The filesystem must not be allowed to supply the property for free. On
        # this machine raw glob.glob already returns lexical order for a 3-file
        # directory, so simply asserting the output is sorted passes even with
        # sorted() DELETED from _sorted_glob -- verified: that mutation survived.
        # The underlying glob is replaced with one that returns reverse order, so
        # the assertion can only hold if _sorted_glob sorts.
        real_glob = gc.globmod.glob
        try:
            gc.globmod.glob = lambda pattern: list(reversed(sorted(real_glob(pattern))))
            found = gc._sorted_glob(self._evdir("observations"), "*.json")
        finally:
            gc.globmod.glob = real_glob
        self.assertEqual(len(found), 3, "the fixture must be non-empty or this passes "
                                        "vacuously")
        self.assertEqual(found, sorted(found),
                         "discovery must SORT; unsorted, node identity would depend on "
                         "filesystem enumeration order")

    def test_node_identity_survives_renaming_the_file_that_carries_it(self):
        # The real property behind "ordering does not matter": identity and content
        # come from the RECORD, not from where it happens to live. Only sourceFile,
        # which exists to say where it was read from, may differ.
        self.source()
        self.observation()
        before = self.obs_nodes(self.build()[0])[0]
        d = self._evdir("observations")
        os.rename(os.path.join(d, "TOBS_MOGO_20260819_001.json"),
                  os.path.join(d, "zzz_renamed.json"))
        after = self.obs_nodes(self.build()[0])[0]
        self.assertEqual(before["nodeId"], after["nodeId"])
        self.assertEqual(before["entityId"], after["entityId"])
        self.assertEqual(before["contentHash"], after["contentHash"])
        self.assertNotEqual(before["sourceFile"], after["sourceFile"])
        self.assertEqual({k: v for k, v in before.items() if k != "sourceFile"},
                         {k: v for k, v in after.items() if k != "sourceFile"})

    def test_a_partial_corpus_builds_without_inventing_the_rest(self):
        # One source, one of its two observations present. The absent one must
        # simply not exist -- no placeholder, no error.
        self.source()
        self.observation("TOBS|MOGO|20260819|001")
        nodes, edges, findings = self.build()
        self.assertEqual(len(self.obs_nodes(nodes)), 1)
        self.assertEqual(len(self.derived_edges(edges)), 1)
        self.assertEqual([f for f in findings if f["severity"] in ("ERROR", "FATAL")], [])

    def test_a_corrupted_source_reference_does_not_silently_attach_elsewhere(self):
        # Two real sources; the observation points at neither. It must NOT fall
        # back to "the only source available".
        self.source("EVSRC|MOGO|20260819|001")
        self.source("EVSRC|MOGO|20260819|002")
        self.observation(source_id="EVSRC|MOGO|20260819|BAD")
        _n, edges, findings = self.build()
        self.assertEqual(self.derived_edges(edges), [])
        self.assertTrue(any(f["category"] == "MISSING_REFERENCE" for f in findings))

    def test_rebuilding_is_idempotent(self):
        self.source()
        for i in range(1, 4):
            self.observation("TOBS|MOGO|20260819|00%d" % i)
        runs = []
        for _ in range(3):
            nodes, edges, findings = self.build()
            runs.append((sorted(n["nodeId"] + n["contentHash"] for n in nodes),
                         sorted(e["edgeId"] for e in edges),
                         len(findings)))
        self.assertEqual(runs[0], runs[1])
        self.assertEqual(runs[1], runs[2])
        # And no duplication crept in across rebuilds.
        self.assertEqual(len(runs[0][1]), len(set(runs[0][1])))


class TestGenuineOrphanDetectionSurvives(TradeObservationCase):
    """B-32 exists to stop FALSE orphans burying real ones. Proving the real ones
    still surface is the whole point, so both controls are here.

    These call the PRODUCTION check, `validate_graph.check_orphans`. An earlier
    version of this class reimplemented orphan detection in a local helper, which
    made every assertion below true of the test's own code and true of nothing
    else: an independent verifier disarmed the real check by skipping
    EVIDENCE_SOURCE nodes, live ORPHAN_NODE warnings fell from 31 to 1, and the
    whole suite still passed. Verifying a parallel approximation of a check is
    indistinguishable from not verifying it.
    """

    def orphan_ids(self, nodes, edges):
        """entityIds the PRODUCTION orphan check reports, resolved back from nodeIds."""
        findings = []
        validate_graph.check_orphans(nodes, edges, findings)
        reported = set()
        for finding in findings:
            self.assertEqual(finding["category"], "ORPHAN_NODE")
            reported.update(finding["affectedIds"])
        return {n["entityId"] for n in nodes if n["nodeId"] in reported}

    def test_POSITIVE_CONTROL_a_source_nothing_cites_is_still_an_orphan(self):
        self.source("EVSRC|MOGO|20260819|001")
        self.source("EVSRC|MOGO|20260819|002")          # cited by nobody
        self.observation(source_id="EVSRC|MOGO|20260819|001")
        nodes, edges, _f = self.build()
        self.assertIn("EVSRC|MOGO|20260819|002", self.orphan_ids(nodes, edges))

    def test_NEGATIVE_CONTROL_a_cited_source_is_not_an_orphan(self):
        self.source("EVSRC|MOGO|20260819|001")
        self.observation(source_id="EVSRC|MOGO|20260819|001")
        nodes, edges, _f = self.build()
        self.assertNotIn("EVSRC|MOGO|20260819|001", self.orphan_ids(nodes, edges))

    def test_the_observation_itself_is_never_an_orphan_when_its_source_exists(self):
        self.source()
        self.observation()
        nodes, edges, _f = self.build()
        self.assertNotIn("TOBS|MOGO|20260819|001", self.orphan_ids(nodes, edges))


class TestProductionOrphanCheckItself(unittest.TestCase):
    """Direct tests of `validate_graph.check_orphans`.

    This exists because of a surviving mutation. Widening its TRADER exemption to
    `("TRADER", "EVIDENCE_SOURCE")` dropped live ORPHAN_NODE warnings from 31 to 1
    and the entire suite still passed -- nothing anywhere under tests/ referenced
    ORPHAN_NODE or check_orphans. The suppressor that B-32 removed the NEED for was
    itself untested in both directions, so the "30 remaining orphans are genuine"
    claim rested on a check nothing was watching.

    Built from hand-authored node/edge dicts rather than a corpus copy, so these
    assert the RULE and cannot rot when the live corpus changes.
    """

    def node(self, node_type, entity_id):
        return {"nodeId": gc.make_node_id(node_type, entity_id),
                "nodeType": node_type, "entityId": entity_id}

    def edge(self, from_node, to_node):
        return {"edgeId": "EDGE|X|%s|%s" % (from_node["entityId"], to_node["entityId"]),
                "edgeType": "DERIVED_FROM",
                "fromNodeId": from_node["nodeId"], "toNodeId": to_node["nodeId"]}

    def orphans(self, nodes, edges):
        findings = []
        validate_graph.check_orphans(nodes, edges, findings)
        return {f["affectedIds"][0] for f in findings if f["category"] == "ORPHAN_NODE"}

    def test_an_uncited_EVIDENCE_SOURCE_is_reported(self):
        # THE case the surviving mutation silenced.
        lonely = self.node("EVIDENCE_SOURCE", "EVSRC|MOGO|20260819|001")
        self.assertIn(lonely["nodeId"], self.orphans([lonely], []))

    def test_a_cited_EVIDENCE_SOURCE_is_NOT_reported(self):
        # Negative control: the report must be caused by having no edges.
        src = self.node("EVIDENCE_SOURCE", "EVSRC|MOGO|20260819|001")
        obs = self.node("TRADE_OBSERVATION", "TOBS|MOGO|20260819|001")
        self.assertEqual(self.orphans([src, obs], [self.edge(obs, src)]), set())

    def test_an_uncited_TRADE_OBSERVATION_is_reported(self):
        lonely = self.node("TRADE_OBSERVATION", "TOBS|MOGO|20260819|001")
        self.assertIn(lonely["nodeId"], self.orphans([lonely], []))

    def test_TRADER_is_the_ONLY_exempt_node_type(self):
        # The exemption is legitimate -- traders are graph roots -- but it must stay
        # exactly one node type wide. Widening it is how the check was disarmed, and
        # a widened exemption looks identical to a clean corpus from the outside.
        edgeless = [self.node(t, "ID|%s" % t) for t in gc.NODE_TYPES]
        reported = self.orphans(edgeless, [])
        exempt = [n["nodeType"] for n in edgeless if n["nodeId"] not in reported]
        self.assertEqual(exempt, ["TRADER"],
                         "exactly one node type may be exempt from orphan reporting; "
                         "any other exemption silently hides real provenance gaps")

    def test_every_orphan_finding_is_a_WARNING_naming_its_node(self):
        lonely = self.node("EVIDENCE_SOURCE", "EVSRC|MOGO|20260819|001")
        findings = []
        validate_graph.check_orphans([lonely], [], findings)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["severity"], "WARNING")
        self.assertEqual(findings[0]["affectedIds"], [lonely["nodeId"]])

    def test_an_edge_in_EITHER_direction_clears_the_orphan(self):
        # Orphan means zero edges of ANY kind, incoming or outgoing.
        a = self.node("EVIDENCE_SOURCE", "EVSRC|MOGO|20260819|001")
        b = self.node("TRADE_OBSERVATION", "TOBS|MOGO|20260819|001")
        self.assertEqual(self.orphans([a, b], [self.edge(b, a)]), set())
        self.assertEqual(self.orphans([a, b], [self.edge(a, b)]), set())

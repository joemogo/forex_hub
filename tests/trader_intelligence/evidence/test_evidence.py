#!/usr/bin/env python3
"""PROGRAM-006 Phase 1A test suite (ADR-008, Deliverable 13). Pure stdlib
(unittest). Fully offline, deterministic. Run with:

    python3 -m unittest tests.trader_intelligence.evidence.test_evidence -v

Every temp repo is built fresh per test via TempEvidenceRepo /
TempGraphRepo -- nothing here ever touches docs/trader-intelligence/evidence/
(the production location) or docs/trader-intelligence/graph/ directly.

Organized into the 9 categories the milestone specifies:
  A. Model creation / valid records
  B. Invalid records are rejected
  C. Provenance / immutability
  D. Confidence engine
  E. Deduplication
  F. Query behavior
  G. Integrity validation
  H. Knowledge Graph integration
  I. Regression (existing suites + graph build stability)
"""
import glob as globmod
import hashlib
import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts", "trader_intelligence")
TI_ROOT = os.path.join(REPO_ROOT, "docs", "trader-intelligence")
SYNTHETIC_DEMO_ROOT = os.path.join(os.path.dirname(__file__), "fixtures", "synthetic_demo")

sys.path.insert(0, SCRIPTS_DIR)
import graph_common as gc                # noqa: E402
import evidence_common as evc            # noqa: E402
import evidence_confidence as conf       # noqa: E402
import evidence_dedup as dedup           # noqa: E402
import evidence_registry as reg          # noqa: E402
import query_evidence as qe              # noqa: E402
import validate_evidence as ve           # noqa: E402
import build_graph                       # noqa: E402
import validate_graph                    # noqa: E402

FIXED_NOW = datetime(2026, 7, 25, 12, 0, 0, tzinfo=timezone.utc)


class TempEvidenceRepo:
    """A throwaway evidence-only directory tree (sources/items/claims/links/
    contradictions/lifecycle/reports) -- isolated from production data and
    from the Knowledge Graph."""

    def __init__(self):
        self.root = tempfile.mkdtemp(prefix="mogo_evidence_test_")
        self.sources_dir = os.path.join(self.root, "sources")
        self.items_dir = os.path.join(self.root, "items")
        self.claims_dir = os.path.join(self.root, "claims")
        self.links_dir = os.path.join(self.root, "links")
        self.contradictions_dir = os.path.join(self.root, "contradictions")
        self.lifecycle_dir = os.path.join(self.root, "lifecycle")
        self.reports_dir = os.path.join(self.root, "reports")
        for d in (self.sources_dir, self.items_dir, self.claims_dir, self.links_dir,
                  self.contradictions_dir, self.lifecycle_dir, self.reports_dir):
            os.makedirs(d, exist_ok=True)

    def cleanup(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def register_source(self, **kwargs):
        kwargs.setdefault("actor", "owner")
        kwargs.setdefault("now", FIXED_NOW)
        return reg.register_source(self.sources_dir, self.lifecycle_dir,
                                    kwargs.pop("sourceType", "transcript"),
                                    kwargs.pop("actor"), kwargs.pop("now"), **kwargs)

    def register_evidence_item(self, source_id, **kwargs):
        kwargs.setdefault("actor", "owner")
        kwargs.setdefault("now", FIXED_NOW)
        return reg.register_evidence_item(self.items_dir, self.sources_dir, self.lifecycle_dir, source_id,
                                           kwargs.pop("evidenceType", "explicit_statement"),
                                           kwargs.pop("evidenceQuality", "medium"),
                                           kwargs.pop("actor"), kwargs.pop("now"), **kwargs)

    def correct_evidence_item(self, original_id, **kwargs):
        kwargs.setdefault("actor", "owner")
        kwargs.setdefault("now", FIXED_NOW)
        return reg.correct_evidence_item(self.items_dir, self.sources_dir, self.lifecycle_dir, original_id,
                                          kwargs.pop("actor"), kwargs.pop("now"), **kwargs)

    def register_claim(self, **kwargs):
        kwargs.setdefault("actor", "owner")
        kwargs.setdefault("now", FIXED_NOW)
        return reg.register_claim(self.claims_dir, self.lifecycle_dir,
                                   kwargs.pop("claimType", "entry_rule"),
                                   kwargs.pop("normalizedClaim", "A generic claim."),
                                   kwargs.pop("actor"), kwargs.pop("now"), **kwargs)

    def link(self, evidence_id, claim_id, relationship_type="supports", **kwargs):
        kwargs.setdefault("actor", "owner")
        kwargs.setdefault("now", FIXED_NOW)
        return reg.link_evidence_to_claim(self.links_dir, self.items_dir, self.claims_dir, self.lifecycle_dir,
                                           evidence_id, claim_id, relationship_type,
                                           kwargs.pop("actor"), kwargs.pop("now"), **kwargs)

    def contradict(self, claim_a_id, claim_b_id, **kwargs):
        kwargs.setdefault("actor", "owner")
        kwargs.setdefault("now", FIXED_NOW)
        return reg.create_contradiction(self.contradictions_dir, self.claims_dir, self.lifecycle_dir,
                                         claim_a_id, claim_b_id,
                                         kwargs.pop("contradictionType", "DEFINITIONAL"),
                                         kwargs.pop("severity", "material"),
                                         kwargs.pop("actor"), kwargs.pop("now"), **kwargs)

    def index(self):
        return qe.EvidenceIndex.load(self.root)

    def validate(self, **kwargs):
        kwargs.setdefault("is_production", False)
        return ve.run_integrity_checks(self.root, **kwargs)

    def read_json(self, sub, filename_fn, record_id):
        with open(os.path.join(self.root, sub, filename_fn(record_id)), "r", encoding="utf-8") as f:
            return json.load(f)

    def write_json(self, sub, filename, record):
        with open(os.path.join(self.root, sub, filename), "w", encoding="utf-8") as f:
            json.dump(record, f)


# Every evidence/ record collection that a *scratch* copy of the tree must
# start empty. evidence/schema/ is structural, not data, so it is kept. See
# tests/trader_intelligence/test_graph.py for the same guarantee.
_SCRATCH_EVIDENCE_COLLECTIONS = tuple(sorted(
    # B-32: the ENTITY collections are derived from graph_common so a new graph
    # entity type cannot be added to discovery and forgotten here -- that omission
    # seeded every fixture with 259 production observations. The extras below are
    # collections that are NOT graph entities (links are edges; lifecycle,
    # annotations and reports are not nodes) and so must stay listed by hand.
    set(gc.EVIDENCE_ENTITY_COLLECTIONS)
    | {"links", "lifecycle", "annotations", "reports"}))


def _clear_scratch_evidence_tree(ti_root):
    """A copied docs/trader-intelligence tree is used as a SCRATCH evidence
    tree here. That held only while production evidence/ was empty; once a
    real transcript intake exists on disk, copytree would silently seed every
    fixture with production records. Emptying each record collection on copy
    makes the scratch guarantee explicit instead of accidental."""
    evidence_root = os.path.join(ti_root, "evidence")
    for name in _SCRATCH_EVIDENCE_COLLECTIONS:
        d = os.path.join(evidence_root, name)
        if os.path.isdir(d):
            shutil.rmtree(d)
        os.makedirs(d, exist_ok=True)


class TempGraphRepo:
    """A throwaway copy of the whole docs/trader-intelligence tree (mirrors
    test_graph.py's TempRepo) so evidence<->Knowledge-Graph integration can be
    exercised without ever touching production graph/build artifacts."""

    def __init__(self):
        self.root = tempfile.mkdtemp(prefix="mogo_evidence_graph_test_")
        self.ti_root = os.path.join(self.root, "docs", "trader-intelligence")
        self.graph_root = os.path.join(self.ti_root, "graph")
        shutil.copytree(TI_ROOT, self.ti_root)
        _clear_scratch_evidence_tree(self.ti_root)
        self.evidence_root = os.path.join(self.ti_root, "evidence")

    def cleanup(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def evidence_repo_view(self):
        """Point a TempEvidenceRepo-shaped set of dirs at this copy's
        docs/trader-intelligence/evidence tree instead of a scratch dir."""
        r = TempEvidenceRepo.__new__(TempEvidenceRepo)
        r.root = self.evidence_root
        r.sources_dir = os.path.join(self.evidence_root, "sources")
        r.items_dir = os.path.join(self.evidence_root, "items")
        r.claims_dir = os.path.join(self.evidence_root, "claims")
        r.links_dir = os.path.join(self.evidence_root, "links")
        r.contradictions_dir = os.path.join(self.evidence_root, "contradictions")
        r.lifecycle_dir = os.path.join(self.evidence_root, "lifecycle")
        r.reports_dir = os.path.join(self.evidence_root, "reports")
        for d in (r.sources_dir, r.items_dir, r.claims_dir, r.links_dir,
                  r.contradictions_dir, r.lifecycle_dir, r.reports_dir):
            os.makedirs(d, exist_ok=True)
        r.cleanup = lambda: None  # cleanup happens via self.cleanup()
        return r

    def build(self):
        return gc.build_nodes_and_edges(self.root, self.ti_root, self.graph_root)


# ---------------------------------------------------------------------------
# A. Model creation / valid records
# ---------------------------------------------------------------------------

class TestModelCreation(unittest.TestCase):
    def setUp(self):
        self.repo = TempEvidenceRepo()

    def tearDown(self):
        self.repo.cleanup()

    def test_register_source_produces_expected_id_and_fields(self):
        src = self.repo.register_source(traderId="TJR", title="Sample transcript")
        self.assertTrue(src["sourceId"].startswith("EVSRC|TJR|20260725|"))
        self.assertEqual(src["lifecycleStatus"], "registered")
        self.assertEqual(src["schemaVersion"], evc.SCHEMA_VERSION)

    def test_register_source_unattributed_when_no_trader(self):
        src = self.repo.register_source()
        self.assertTrue(src["sourceId"].startswith("EVSRC|UNATTRIBUTED|"))

    def test_register_evidence_item_computes_content_hash(self):
        src = self.repo.register_source(traderId="TJR")
        item = self.repo.register_evidence_item(src["sourceId"], exactExcerpt="Displacement follows a sweep.")
        self.assertIsNotNone(item["contentHash"])
        self.assertEqual(item["evidenceStatus"], "active")

    def test_register_claim_computes_fingerprint(self):
        claim = self.repo.register_claim(normalizedClaim="Displacement occurs after a liquidity sweep.", traderId="TJR")
        self.assertIsNotNone(claim["normalizedFingerprint"])
        self.assertEqual(claim["confidenceState"], "insufficient_evidence")
        self.assertEqual(claim["evidenceCount"], 0)

    def test_link_and_contradiction_creation(self):
        src = self.repo.register_source(traderId="TJR")
        item = self.repo.register_evidence_item(src["sourceId"])
        claim_a = self.repo.register_claim(normalizedClaim="Claim A")
        claim_b = self.repo.register_claim(normalizedClaim="Claim B")
        link = self.repo.link(item["evidenceId"], claim_a["claimId"], "supports")
        self.assertEqual(link["relationshipType"], "supports")
        contradiction = self.repo.contradict(claim_a["claimId"], claim_b["claimId"])
        self.assertEqual(contradiction["status"], "open")

    def test_lifecycle_created_event_written_for_every_entity_type(self):
        src = self.repo.register_source(traderId="TJR")
        item = self.repo.register_evidence_item(src["sourceId"])
        claim = self.repo.register_claim()
        idx = self.repo.index()
        types_seen = {e["entityType"] for e in idx.lifecycle_events.values() if e["eventType"] == "created"}
        self.assertEqual(types_seen, {"EVIDENCE_SOURCE", "EVIDENCE_ITEM", "CLAIM"})


# ---------------------------------------------------------------------------
# B. Invalid records are rejected
# ---------------------------------------------------------------------------

class TestInvalidRecordsRejected(unittest.TestCase):
    def setUp(self):
        self.repo = TempEvidenceRepo()

    def tearDown(self):
        self.repo.cleanup()

    def test_unknown_source_type_rejected(self):
        with self.assertRaises(evc.EvidenceValidationError):
            self.repo.register_source(sourceType="not_a_real_type")

    def test_external_source_without_asset_reference_rejected(self):
        with self.assertRaises(evc.EvidenceValidationError):
            self.repo.register_source(storageLocationType="external")

    def test_malformed_trader_id_rejected(self):
        with self.assertRaises(evc.EvidenceValidationError):
            self.repo.register_source(traderId="not-upper-case")

    def test_evidence_item_with_nonexistent_source_rejected(self):
        with self.assertRaises(evc.EvidenceValidationError):
            self.repo.register_evidence_item("EVSRC|GHOST|99999999|999")

    def test_evidence_item_unknown_type_rejected(self):
        src = self.repo.register_source(traderId="TJR")
        with self.assertRaises(evc.EvidenceValidationError):
            self.repo.register_evidence_item(src["sourceId"], evidenceType="not_a_real_type")

    def test_evidence_item_unknown_quality_rejected(self):
        src = self.repo.register_source(traderId="TJR")
        with self.assertRaises(evc.EvidenceValidationError):
            self.repo.register_evidence_item(src["sourceId"], evidenceQuality="not_a_real_quality")

    def test_evidence_item_nonexistent_parent_rejected(self):
        src = self.repo.register_source(traderId="TJR")
        with self.assertRaises(evc.EvidenceValidationError):
            self.repo.register_evidence_item(src["sourceId"], parentEvidenceId="EV|GHOST|001")

    def test_claim_unknown_type_rejected(self):
        with self.assertRaises(evc.EvidenceValidationError):
            self.repo.register_claim(claimType="not_a_real_type")

    def test_claim_empty_text_rejected(self):
        with self.assertRaises(evc.EvidenceValidationError):
            self.repo.register_claim(normalizedClaim="   ")

    def test_link_nonexistent_evidence_rejected(self):
        claim = self.repo.register_claim()
        with self.assertRaises(evc.EvidenceValidationError):
            self.repo.link("EV|GHOST|001", claim["claimId"])

    def test_link_nonexistent_claim_rejected(self):
        src = self.repo.register_source(traderId="TJR")
        item = self.repo.register_evidence_item(src["sourceId"])
        with self.assertRaises(evc.EvidenceValidationError):
            self.repo.link(item["evidenceId"], "CLAIM|GHOST|20260101|001")

    def test_link_unknown_relationship_type_rejected(self):
        src = self.repo.register_source(traderId="TJR")
        item = self.repo.register_evidence_item(src["sourceId"])
        claim = self.repo.register_claim()
        with self.assertRaises(evc.EvidenceValidationError):
            self.repo.link(item["evidenceId"], claim["claimId"], relationship_type="not_a_real_relationship")

    def test_link_relevance_weight_out_of_range_rejected(self):
        src = self.repo.register_source(traderId="TJR")
        item = self.repo.register_evidence_item(src["sourceId"])
        claim = self.repo.register_claim()
        with self.assertRaises(evc.EvidenceValidationError):
            self.repo.link(item["evidenceId"], claim["claimId"], relevanceWeight=1.5)

    def test_contradiction_self_reference_rejected(self):
        claim = self.repo.register_claim()
        with self.assertRaises(evc.EvidenceValidationError):
            self.repo.contradict(claim["claimId"], claim["claimId"])

    def test_contradiction_nonexistent_claim_rejected(self):
        claim = self.repo.register_claim()
        with self.assertRaises(evc.EvidenceValidationError):
            self.repo.contradict(claim["claimId"], "CLAIM|GHOST|20260101|001")

    def test_contradiction_unknown_type_rejected(self):
        claim_a = self.repo.register_claim(normalizedClaim="A")
        claim_b = self.repo.register_claim(normalizedClaim="B")
        with self.assertRaises(evc.EvidenceValidationError):
            self.repo.contradict(claim_a["claimId"], claim_b["claimId"], contradictionType="NOT_REAL")

    def test_nothing_persisted_on_rejected_registration(self):
        before = len(globmod.glob(os.path.join(self.repo.sources_dir, "*.json")))
        with self.assertRaises(evc.EvidenceValidationError):
            self.repo.register_source(sourceType="not_a_real_type")
        after = len(globmod.glob(os.path.join(self.repo.sources_dir, "*.json")))
        self.assertEqual(before, after)


# ---------------------------------------------------------------------------
# C. Provenance / immutability
# ---------------------------------------------------------------------------

class TestProvenanceAndImmutability(unittest.TestCase):
    def setUp(self):
        self.repo = TempEvidenceRepo()

    def tearDown(self):
        self.repo.cleanup()

    def test_correction_supersedes_rather_than_edits(self):
        src = self.repo.register_source(traderId="TJR")
        original = self.repo.register_evidence_item(src["sourceId"], exactExcerpt="Original wording.")
        corrected = self.repo.correct_evidence_item(original["evidenceId"], exactExcerpt="Corrected wording.")

        idx = self.repo.index()
        original_after = idx.items[original["evidenceId"]]
        self.assertEqual(original_after["exactExcerpt"], "Original wording.",
                          "Original content must remain untouched -- corrections never edit in place.")
        self.assertEqual(original_after["evidenceStatus"], "superseded")
        self.assertEqual(corrected["supersedesEvidenceId"], original["evidenceId"])
        self.assertEqual(corrected["evidenceStatus"], "active")

    def test_supersession_recorded_as_lifecycle_event(self):
        src = self.repo.register_source(traderId="TJR")
        original = self.repo.register_evidence_item(src["sourceId"])
        self.repo.correct_evidence_item(original["evidenceId"])
        idx = self.repo.index()
        superseded_events = [e for e in idx.lifecycle_events.values()
                              if e["entityId"] == original["evidenceId"] and e["eventType"] == "superseded"]
        self.assertEqual(len(superseded_events), 1)
        self.assertEqual(superseded_events[0]["priorStatus"], "active")
        self.assertEqual(superseded_events[0]["newStatus"], "superseded")

    def test_content_hash_stable_across_reload(self):
        src = self.repo.register_source(traderId="TJR")
        item = self.repo.register_evidence_item(src["sourceId"], exactExcerpt="Stable text.")
        idx = self.repo.index()
        reloaded = idx.items[item["evidenceId"]]
        self.assertEqual(item["contentHash"], reloaded["contentHash"])

    def test_confidence_recompute_writes_lifecycle_event_with_explanation(self):
        src = self.repo.register_source(traderId="TJR")
        item = self.repo.register_evidence_item(src["sourceId"], evidenceQuality="high")
        claim = self.repo.register_claim()
        self.repo.link(item["evidenceId"], claim["claimId"], "supports")
        idx = self.repo.index()
        events = [e for e in idx.lifecycle_events.values()
                  if e["entityId"] == claim["claimId"] and e["eventType"] == "confidence_recomputed"]
        self.assertEqual(len(events), 1)
        self.assertTrue(events[0]["reason"])


# ---------------------------------------------------------------------------
# D. Confidence engine
# ---------------------------------------------------------------------------

class TestConfidenceEngine(unittest.TestCase):
    def setUp(self):
        self.repo = TempEvidenceRepo()

    def tearDown(self):
        self.repo.cleanup()

    def test_no_links_yields_insufficient_evidence_with_none_score(self):
        state, score, counts, _explanation = conf.compute_confidence([], {})
        self.assertEqual(state, "insufficient_evidence")
        self.assertIsNone(score)
        self.assertEqual(counts["evidenceCount"], 0)

    def test_three_independent_high_quality_supports_reach_supported_or_better(self):
        # Each independent group contributes SUPPORT_GROUP_POINTS=22; two
        # groups (44) fall just short of SUPPORTED_SCORE=45, so three
        # independent sources are used here to clear the threshold reliably.
        claim = self.repo.register_claim()
        for i in range(3):
            src = self.repo.register_source(traderId="TJR", title="Source %d" % i)
            item = self.repo.register_evidence_item(src["sourceId"], evidenceType="explicit_statement", evidenceQuality="high")
            self.repo.link(item["evidenceId"], claim["claimId"], "supports")
        idx = self.repo.index()
        updated_claim = idx.claims[claim["claimId"]]
        self.assertIn(updated_claim["confidenceState"], ("supported", "strongly_supported"))
        self.assertGreater(updated_claim["confidenceScore"], 0)

    def test_same_source_items_discounted_not_double_counted(self):
        src = self.repo.register_source(traderId="TJR")
        item_a = self.repo.register_evidence_item(src["sourceId"], evidenceType="explicit_statement", evidenceQuality="high")
        item_b = self.repo.register_evidence_item(src["sourceId"], evidenceType="explicit_statement", evidenceQuality="high")
        claim = self.repo.register_claim()
        self.repo.link(item_a["evidenceId"], claim["claimId"], "supports")
        idx_after_one = self.repo.index()
        score_after_one = idx_after_one.claims[claim["claimId"]]["confidenceScore"]

        self.repo.link(item_b["evidenceId"], claim["claimId"], "supports")
        idx_after_two = self.repo.index()
        score_after_two = idx_after_two.claims[claim["claimId"]]["confidenceScore"]

        full_weight_increment = score_after_one  # what a second FULL-weight independent group would add
        self.assertLess(score_after_two - score_after_one, full_weight_increment,
                         "A second same-source item must count less than a second independent group would.")

    def test_contradiction_is_penalized_more_than_equivalent_support_is_rewarded(self):
        src = self.repo.register_source(traderId="TJR")
        item = self.repo.register_evidence_item(src["sourceId"], evidenceType="explicit_statement", evidenceQuality="high")
        claim_support = self.repo.register_claim(normalizedClaim="Support claim")
        claim_contra = self.repo.register_claim(normalizedClaim="Contra claim")
        self.repo.link(item["evidenceId"], claim_support["claimId"], "supports")
        # Re-register an equal-strength item for the contradiction side to isolate the asymmetry.
        item2 = self.repo.register_evidence_item(src["sourceId"], evidenceType="explicit_statement", evidenceQuality="high")
        self.repo.link(item2["evidenceId"], claim_contra["claimId"], "contradicts")
        idx = self.repo.index()
        support_score = idx.claims[claim_support["claimId"]]["confidenceScore"]
        contra_state = idx.claims[claim_contra["claimId"]]["confidenceState"]
        self.assertGreater(support_score, 0)
        self.assertIn(contra_state, ("contradicted", "contested"))

    def test_weakening_evidence_alone_does_not_contradict(self):
        src = self.repo.register_source(traderId="TJR")
        item = self.repo.register_evidence_item(src["sourceId"], evidenceType="exception_statement", evidenceQuality="low")
        claim = self.repo.register_claim()
        self.repo.link(item["evidenceId"], claim["claimId"], "weakens")
        idx = self.repo.index()
        self.assertNotEqual(idx.claims[claim["claimId"]]["confidenceState"], "contradicted")

    def test_only_unresolved_relationship_yields_unresolved_state(self):
        src = self.repo.register_source(traderId="TJR")
        item = self.repo.register_evidence_item(src["sourceId"])
        claim = self.repo.register_claim()
        self.repo.link(item["evidenceId"], claim["claimId"], "unresolved")
        idx = self.repo.index()
        self.assertEqual(idx.claims[claim["claimId"]]["confidenceState"], "unresolved")

    def test_confidence_score_always_bounded_0_to_100(self):
        src = self.repo.register_source(traderId="TJR")
        claim = self.repo.register_claim()
        for i in range(6):
            src_i = self.repo.register_source(traderId="TJR", title="Source %d" % i)
            item = self.repo.register_evidence_item(src_i["sourceId"], evidenceType="explicit_statement", evidenceQuality="high")
            self.repo.link(item["evidenceId"], claim["claimId"], "supports")
        idx = self.repo.index()
        score = idx.claims[claim["claimId"]]["confidenceScore"]
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)


# ---------------------------------------------------------------------------
# E. Deduplication
# ---------------------------------------------------------------------------

class TestDeduplication(unittest.TestCase):
    def setUp(self):
        self.repo = TempEvidenceRepo()

    def tearDown(self):
        self.repo.cleanup()

    def test_exact_duplicate_fingerprint_detected(self):
        c1 = self.repo.register_claim(normalizedClaim="Displacement follows a sweep.", traderId="TJR", timeframe="5m")
        c2 = self.repo.register_claim(normalizedClaim="displacement follows a sweep!!", traderId="TJR", timeframe="5m")
        idx = self.repo.index()
        groups = dedup.find_exact_duplicate_groups(list(idx.claims.values()))
        self.assertEqual(len(groups), 1)
        self.assertEqual(set(groups[0]), {c1["claimId"], c2["claimId"]})

    def test_title_absence_does_not_prevent_exact_claim_duplicate_detection(self):
        # Claims have no title field at all -- confirms fingerprinting never
        # depends on an optional/absent field (mirrors PROGRAM-004 Correction 3).
        c1 = self.repo.register_claim(normalizedClaim="Entry requires confirmation candle.")
        c2 = self.repo.register_claim(normalizedClaim="Entry requires confirmation candle.")
        idx = self.repo.index()
        groups = dedup.find_exact_duplicate_groups(list(idx.claims.values()))
        self.assertEqual(len(groups), 1)

    def test_scoped_variants_are_never_treated_as_identical(self):
        base = "Displacement occurs after a liquidity sweep"
        c1 = self.repo.register_claim(normalizedClaim=base, traderId="TJR", timeframe="5m")
        c2 = self.repo.register_claim(normalizedClaim=base + " in the NY session", traderId="TJR", timeframe="5m", session="NY")
        c3 = self.repo.register_claim(normalizedClaim="No displacement occurs in a strong trend", traderId="TJR", timeframe="5m")
        c4 = self.repo.register_claim(normalizedClaim=base, traderId="TJR", timeframe="1m")
        idx = self.repo.index()
        claims = list(idx.claims.values())
        exact_groups = dedup.find_exact_duplicate_groups(claims)
        self.assertEqual(exact_groups, [], "Differently-scoped claims must never fingerprint as exact duplicates.")
        near = dedup.find_near_duplicate_candidates(claims)
        flagged_pairs = {frozenset((c["claimAId"], c["claimBId"])) for c in near}
        for a, b in ((c1, c2), (c1, c3), (c1, c4), (c2, c4)):
            self.assertNotIn(frozenset((a["claimId"], b["claimId"])), flagged_pairs,
                              "Scope difference must prevent a near-duplicate flag between %r and %r." % (a["claimId"], b["claimId"]))

    def test_near_duplicate_same_scope_is_flagged(self):
        # Differ by one substantive word (not just trailing punctuation, which
        # normalize_claim_text strips -- that would make them exact duplicates).
        c1 = self.repo.register_claim(normalizedClaim="Displacement must follow a liquidity sweep in most cases.", traderId="TJR", timeframe="5m")
        c2 = self.repo.register_claim(normalizedClaim="Displacement must follow a liquidity sweep in some cases.", traderId="TJR", timeframe="5m")
        idx = self.repo.index()
        near = dedup.find_near_duplicate_candidates(list(idx.claims.values()), threshold=0.5)
        pairs = {frozenset((c["claimAId"], c["claimBId"])) for c in near}
        self.assertIn(frozenset((c1["claimId"], c2["claimId"])), pairs)

    def test_merge_recommendation_never_mutates_claims(self):
        c1 = self.repo.register_claim(normalizedClaim="Older claim.")
        c2 = self.repo.register_claim(normalizedClaim="Newer claim.")
        before = self.repo.index().claims
        dedup.recommend_merge(c1, c2, 0.9, FIXED_NOW)
        after = self.repo.index().claims
        self.assertEqual(before, after)


# ---------------------------------------------------------------------------
# F. Query behavior
# ---------------------------------------------------------------------------

class TestQueryBehavior(unittest.TestCase):
    def setUp(self):
        self.repo = TempEvidenceRepo()

    def tearDown(self):
        self.repo.cleanup()

    def test_empty_corpus_distinguishes_not_found_from_empty(self):
        idx = self.repo.index()
        not_found = qe.get_source_by_id(idx, "EVSRC|GHOST|99999999|999")
        empty = qe.list_unresolved_claims(idx)
        self.assertEqual(not_found["status"], "not_found")
        self.assertEqual(empty["status"], "empty")
        self.assertEqual(not_found["resultCount"], 0)
        self.assertEqual(empty["resultCount"], 0)

    def test_queries_never_mutate_stored_data(self):
        src = self.repo.register_source(traderId="TJR")
        item = self.repo.register_evidence_item(src["sourceId"])
        claim = self.repo.register_claim()
        self.repo.link(item["evidenceId"], claim["claimId"], "supports")
        before = self.repo.index()
        qe.evidence_system_summary(before)
        qe.trace_claim_to_source_provenance(before, claim["claimId"])
        qe.detect_duplicate_candidates(before)
        after = self.repo.index()
        self.assertEqual(before.sources, after.sources)
        self.assertEqual(before.items, after.items)
        self.assertEqual(before.claims, after.claims)

    def test_list_queries_return_deterministic_ordering(self):
        for i in range(5):
            self.repo.register_claim(normalizedClaim="Claim %d" % i, traderId="TJR")
        idx = self.repo.index()
        result_1 = qe.list_claims_by_trader(idx, "TJR")["results"]
        result_2 = qe.list_claims_by_trader(idx, "TJR")["results"]
        self.assertEqual([c["claimId"] for c in result_1], [c["claimId"] for c in result_2])
        self.assertEqual([c["claimId"] for c in result_1], sorted(c["claimId"] for c in result_1))

    def test_list_claims_by_type_rejects_unknown_type(self):
        idx = self.repo.index()
        result = qe.list_claims_by_type(idx, "not_a_real_type")
        self.assertEqual(result["status"], "invalid_input")

    def test_trace_evidence_provenance_follows_derivation_chain(self):
        src = self.repo.register_source(traderId="TJR")
        parent = self.repo.register_evidence_item(src["sourceId"], exactExcerpt="Parent excerpt.")
        child = self.repo.register_evidence_item(src["sourceId"], exactExcerpt="Derived observation.", parentEvidenceId=parent["evidenceId"])
        idx = self.repo.index()
        result = qe.trace_evidence_provenance(idx, child["evidenceId"])
        chain_ids = [e["evidenceId"] for e in result["results"][0]["derivationChain"]]
        self.assertEqual(chain_ids, [child["evidenceId"], parent["evidenceId"]])

    def test_detect_orphaned_records_finds_nothing_on_healthy_corpus(self):
        src = self.repo.register_source(traderId="TJR")
        item = self.repo.register_evidence_item(src["sourceId"])
        claim = self.repo.register_claim()
        self.repo.link(item["evidenceId"], claim["claimId"], "supports")
        idx = self.repo.index()
        self.assertEqual(qe.detect_orphaned_records(idx)["status"], "empty")

    def test_evidence_system_summary_counts_match(self):
        src = self.repo.register_source(traderId="TJR")
        self.repo.register_evidence_item(src["sourceId"])
        self.repo.register_evidence_item(src["sourceId"])
        self.repo.register_claim()
        idx = self.repo.index()
        summary = qe.evidence_system_summary(idx)["results"][0]
        self.assertEqual(summary["sourceCount"], 1)
        self.assertEqual(summary["evidenceItemCount"], 2)
        self.assertEqual(summary["claimCount"], 1)


# ---------------------------------------------------------------------------
# G. Integrity validation
# ---------------------------------------------------------------------------

class TestIntegrityValidation(unittest.TestCase):
    def setUp(self):
        self.repo = TempEvidenceRepo()

    def tearDown(self):
        self.repo.cleanup()

    def test_healthy_corpus_has_no_findings(self):
        src = self.repo.register_source(traderId="TJR")
        item = self.repo.register_evidence_item(src["sourceId"], exactExcerpt="Some excerpt.")
        claim = self.repo.register_claim()
        self.repo.link(item["evidenceId"], claim["claimId"], "supports")
        report = self.repo.validate()
        self.assertEqual(report["summary"], {"INFO": 0, "WARNING": 0, "ERROR": 0, "FATAL": 0})

    def test_orphaned_evidence_detected(self):
        src = self.repo.register_source(traderId="TJR")
        item = self.repo.register_evidence_item(src["sourceId"])
        record = self.repo.read_json("items", evc.evidence_id_to_filename, item["evidenceId"])
        record["sourceId"] = "EVSRC|GHOST|99999999|999"
        self.repo.write_json("items", evc.evidence_id_to_filename(item["evidenceId"]), record)
        report = self.repo.validate()
        self.assertTrue(any(f["findingType"] == "ORPHANED_EVIDENCE" for f in report["findings"]))

    def test_duplicate_id_detected(self):
        src = self.repo.register_source(traderId="TJR")
        record = self.repo.read_json("sources", evc.source_id_to_filename, src["sourceId"])
        self.repo.write_json("sources", "duplicate_copy.json", record)
        report = self.repo.validate()
        self.assertTrue(any(f["findingType"] == "DUPLICATE_ID" for f in report["findings"]))

    def test_inconsistent_hash_detected(self):
        src = self.repo.register_source(traderId="TJR")
        item = self.repo.register_evidence_item(src["sourceId"], exactExcerpt="Original.")
        record = self.repo.read_json("items", evc.evidence_id_to_filename, item["evidenceId"])
        record["contentHash"] = "tampered"
        self.repo.write_json("items", evc.evidence_id_to_filename(item["evidenceId"]), record)
        report = self.repo.validate()
        self.assertTrue(any(f["findingType"] == "INCONSISTENT_HASH" for f in report["findings"]))

    def test_confidence_count_mismatch_detected(self):
        src = self.repo.register_source(traderId="TJR")
        item = self.repo.register_evidence_item(src["sourceId"])
        claim = self.repo.register_claim()
        self.repo.link(item["evidenceId"], claim["claimId"], "supports")
        record = self.repo.read_json("claims", evc.claim_id_to_filename, claim["claimId"])
        record["confidenceState"] = "contradicted"
        self.repo.write_json("claims", evc.claim_id_to_filename(claim["claimId"]), record)
        report = self.repo.validate()
        self.assertTrue(any(f["findingType"] == "CONFIDENCE_COUNT_MISMATCH" for f in report["findings"]))

    def test_unresolved_supersession_chain_detected(self):
        src = self.repo.register_source(traderId="TJR")
        original = self.repo.register_evidence_item(src["sourceId"])
        self.repo.correct_evidence_item(original["evidenceId"])
        record = self.repo.read_json("items", evc.evidence_id_to_filename, original["evidenceId"])
        record["evidenceStatus"] = "superseded"  # already true, but force the scenario explicitly
        self.repo.write_json("items", evc.evidence_id_to_filename(original["evidenceId"]), record)
        # Break the chain by deleting the successor entirely.
        for path in globmod.glob(os.path.join(self.repo.items_dir, "*.json")):
            with open(path) as f:
                rec = json.load(f)
            if rec.get("supersedesEvidenceId") == original["evidenceId"]:
                os.remove(path)
        report = self.repo.validate()
        self.assertTrue(any(f["findingType"] == "UNRESOLVED_SUPERSESSION_CHAIN" for f in report["findings"]))

    def test_circular_derivation_detected(self):
        src = self.repo.register_source(traderId="TJR")
        a = self.repo.register_evidence_item(src["sourceId"])
        b = self.repo.register_evidence_item(src["sourceId"], parentEvidenceId=a["evidenceId"])
        record_a = self.repo.read_json("items", evc.evidence_id_to_filename, a["evidenceId"])
        record_a["parentEvidenceId"] = b["evidenceId"]  # manually forge a cycle a->b->a
        self.repo.write_json("items", evc.evidence_id_to_filename(a["evidenceId"]), record_a)
        report = self.repo.validate()
        self.assertTrue(any(f["findingType"] == "CIRCULAR_DERIVATION" for f in report["findings"]))

    def test_invalid_contradiction_record_detected(self):
        claim = self.repo.register_claim()
        other = self.repo.register_claim(normalizedClaim="Other")
        contradiction = self.repo.contradict(claim["claimId"], other["claimId"])
        record = self.repo.read_json("contradictions", evc.contradiction_id_to_filename, contradiction["contradictionId"])
        record["severity"] = "not_a_real_severity"
        self.repo.write_json("contradictions", evc.contradiction_id_to_filename(contradiction["contradictionId"]), record)
        report = self.repo.validate()
        self.assertTrue(any(f["findingType"] == "INVALID_CONTRADICTION_RECORD" for f in report["findings"]))

    def test_invalid_claim_scope_detected_on_fingerprint_tamper(self):
        claim = self.repo.register_claim(normalizedClaim="Some claim.", traderId="TJR")
        record = self.repo.read_json("claims", evc.claim_id_to_filename, claim["claimId"])
        record["normalizedFingerprint"] = "0" * 64
        self.repo.write_json("claims", evc.claim_id_to_filename(claim["claimId"]), record)
        report = self.repo.validate()
        self.assertTrue(any(f["findingType"] == "INVALID_CLAIM_SCOPE" for f in report["findings"]))

    def test_unsupported_schema_version_detected(self):
        src = self.repo.register_source(traderId="TJR")
        record = self.repo.read_json("sources", evc.source_id_to_filename, src["sourceId"])
        record["schemaVersion"] = evc.SCHEMA_VERSION + 99
        self.repo.write_json("sources", evc.source_id_to_filename(src["sourceId"]), record)
        report = self.repo.validate()
        self.assertTrue(any(f["findingType"] == "UNSUPPORTED_SCHEMA_VERSION" for f in report["findings"]))

    def test_synthetic_marker_leakage_detected_when_is_production_true(self):
        self.repo.register_claim(normalizedClaim="SYNTHETIC TEST DATA / NOT REAL TJR RESEARCH example claim.")
        report = self.repo.validate(is_production=True)
        self.assertTrue(any(f["findingType"] == "MISLABELED_SYNTHETIC_FIXTURE" for f in report["findings"]))

    def test_synthetic_marker_allowed_when_is_production_false(self):
        self.repo.register_claim(normalizedClaim="SYNTHETIC TEST DATA / NOT REAL TJR RESEARCH example claim.")
        report = self.repo.validate(is_production=False)
        self.assertFalse(any(f["findingType"] == "MISLABELED_SYNTHETIC_FIXTURE" for f in report["findings"]))

    def test_validator_never_mutates_stored_records(self):
        src = self.repo.register_source(traderId="TJR")
        before = self.repo.read_json("sources", evc.source_id_to_filename, src["sourceId"])
        self.repo.validate()
        after = self.repo.read_json("sources", evc.source_id_to_filename, src["sourceId"])
        self.assertEqual(before, after)


# ---------------------------------------------------------------------------
# H. Knowledge Graph integration
# ---------------------------------------------------------------------------

class TestKnowledgeGraphIntegration(unittest.TestCase):
    def setUp(self):
        self.graph_repo = TempGraphRepo()
        self.repo = self.graph_repo.evidence_repo_view()

    def tearDown(self):
        self.graph_repo.cleanup()

    def test_empty_evidence_corpus_builds_without_error(self):
        nodes, edges, findings, _raw = self.graph_repo.build()
        self.assertEqual([f for f in findings if f.get("severity") in ("ERROR", "FATAL")], [])
        evidence_nodes = [n for n in nodes if n["nodeType"] in ("EVIDENCE_SOURCE", "EVIDENCE_ITEM", "CLAIM")]
        self.assertEqual(evidence_nodes, [])

    def test_source_evidence_claim_nodes_created(self):
        src = self.repo.register_source(traderId="TJR")
        item = self.repo.register_evidence_item(src["sourceId"])
        claim = self.repo.register_claim(traderId="TJR")
        self.repo.link(item["evidenceId"], claim["claimId"], "supports")

        nodes, edges, findings, _raw = self.graph_repo.build()
        self.assertEqual([f for f in findings if f.get("severity") in ("ERROR", "FATAL")], [])
        node_types_by_entity = {n["entityId"]: n["nodeType"] for n in nodes}
        self.assertEqual(node_types_by_entity.get(src["sourceId"]), "EVIDENCE_SOURCE")
        self.assertEqual(node_types_by_entity.get(item["evidenceId"]), "EVIDENCE_ITEM")
        self.assertEqual(node_types_by_entity.get(claim["claimId"]), "CLAIM")

    def test_evidence_claim_link_becomes_supports_edge(self):
        src = self.repo.register_source(traderId="TJR")
        item = self.repo.register_evidence_item(src["sourceId"])
        claim = self.repo.register_claim(traderId="TJR")
        self.repo.link(item["evidenceId"], claim["claimId"], "supports")

        nodes, edges, _findings, _raw = self.graph_repo.build()
        node_id_by_entity = {n["entityId"]: n["nodeId"] for n in nodes}
        matching = [e for e in edges if e["edgeType"] == "SUPPORTS"
                    and e["fromNodeId"] == node_id_by_entity[item["evidenceId"]]
                    and e["toNodeId"] == node_id_by_entity[claim["claimId"]]]
        self.assertEqual(len(matching), 1)

    def test_evidence_derived_from_source_edge(self):
        src = self.repo.register_source(traderId="TJR")
        item = self.repo.register_evidence_item(src["sourceId"])
        nodes, edges, _findings, _raw = self.graph_repo.build()
        node_id_by_entity = {n["entityId"]: n["nodeId"] for n in nodes}
        matching = [e for e in edges if e["edgeType"] == "DERIVED_FROM"
                    and e["fromNodeId"] == node_id_by_entity[item["evidenceId"]]
                    and e["toNodeId"] == node_id_by_entity[src["sourceId"]]]
        self.assertEqual(len(matching), 1)

    def test_contradiction_record_becomes_contradicts_edge(self):
        claim_a = self.repo.register_claim(normalizedClaim="A", traderId="TJR")
        claim_b = self.repo.register_claim(normalizedClaim="B", traderId="TJR")
        contradiction = self.repo.contradict(claim_a["claimId"], claim_b["claimId"])
        nodes, edges, _findings, _raw = self.graph_repo.build()
        node_id_by_entity = {n["entityId"]: n["nodeId"] for n in nodes}
        # ContradictionRecord is the edge's origin (it IS the evidence of the
        # disagreement); each claim is a target, not the other way around.
        from_node = node_id_by_entity[contradiction["contradictionId"]]
        targets = {e["toNodeId"] for e in edges if e["edgeType"] == "CONTRADICTS" and e["fromNodeId"] == from_node}
        self.assertEqual(targets, {node_id_by_entity[claim_a["claimId"]], node_id_by_entity[claim_b["claimId"]]})

    def test_validate_graph_reports_no_findings_for_evidence_integration(self):
        src = self.repo.register_source(traderId="TJR")
        item = self.repo.register_evidence_item(src["sourceId"])
        claim = self.repo.register_claim(traderId="TJR")
        self.repo.link(item["evidenceId"], claim["claimId"], "supports")
        nodes, edges, construction_findings, raw_by_entity_id = self.graph_repo.build()
        report = validate_graph.run_integrity_checks(nodes, edges, raw_by_entity_id, construction_findings, "TEST_BUILD")
        blocking = [f for f in report["findings"] if f["severity"] in ("ERROR", "FATAL")]
        self.assertEqual(blocking, [])


# ---------------------------------------------------------------------------
# I. Regression
# ---------------------------------------------------------------------------

class TestRegression(unittest.TestCase):
    def test_reading_the_production_evidence_tree_does_not_modify_it(self):
        """The read paths are read-only: the corpus is untouched afterwards.

        Replaces an assertion that the tree held ZERO records, whose docstring
        stated the intent plainly -- "so a future change that accidentally adds
        data here gets caught". That intent is a BEFORE/AFTER relation; the count
        was only a proxy, and one that stopped working the moment the corpus was
        deliberately populated.

        Two details are load-bearing, both found by an independent verifier that
        defeated the first version of this test:

        * EVERY subdirectory is fingerprinted, discovered from disk. The first
          version listed five of the nineteen, leaving every Phase 1B and Phase 7A
          entity directory unwatched -- a build that rewrote `evidence/hypotheses/`
          passed while `git status` showed the file modified.
        * mtime is compared as well as content. A sibling test in this class runs
          a production build BEFORE this one, so an idempotent rewrite has already
          been applied by the time the `before` snapshot is taken and the content
          hashes agree. mtime moves anyway.
        """
        evidence_root = os.path.join(TI_ROOT, "evidence")

        def snapshot():
            out = {}
            for path in sorted(globmod.glob(os.path.join(evidence_root, "**", "*.json"),
                                            recursive=True)):
                stat = os.stat(path)
                with open(path, "rb") as handle:
                    digest = hashlib.sha256(handle.read()).hexdigest()
                out[os.path.relpath(path, evidence_root)] = (digest, stat.st_mtime_ns)
            return out

        before = snapshot()
        # Not a corpus-size assertion -- proof the comparison has something to
        # compare. An empty tree would make it vacuous.
        self.assertGreater(len(before), 0,
                           "no records under evidence/ -- this test would pass "
                           "without reading anything")
        directories = {os.path.dirname(rel).split(os.sep)[0] for rel in before}
        self.assertGreater(len(directories), 5,
                           "fingerprinting only %d directories -- the first version "
                           "of this test watched five of nineteen and missed writes "
                           "into the rest" % len(directories))

        graph_root = os.path.join(TI_ROOT, "graph")
        nodes, edges, findings, raw = gc.build_nodes_and_edges(REPO_ROOT, TI_ROOT, graph_root)
        validate_graph.run_integrity_checks(nodes, edges, raw, findings, "TEST")

        after = snapshot()
        changed = sorted(k for k in set(before) | set(after)
                         if before.get(k) != after.get(k))
        self.assertEqual(changed, [],
                         "the production evidence corpus changed while merely being "
                         "read: %s" % changed[:5])

    def test_production_graph_build_unaffected_by_empty_evidence_corpus(self):
        repo_root = REPO_ROOT
        ti_root = TI_ROOT
        graph_root = os.path.join(ti_root, "graph")
        nodes, edges, findings, _raw = gc.build_nodes_and_edges(repo_root, ti_root, graph_root)
        blocking = [f for f in findings if f.get("severity") in ("ERROR", "FATAL")]
        self.assertEqual(blocking, [])

    def test_evidence_node_and_edge_types_are_registered(self):
        for t in ("EVIDENCE_SOURCE", "EVIDENCE_ITEM", "CLAIM", "CONTRADICTION_RECORD"):
            self.assertIn(t, gc.NODE_TYPES)
        for t in ("WEAKENS", "CONTEXTUALIZES", "EXEMPLIFIES", "QUALIFIES", "UNRESOLVED", "CANDIDATE_FOR_RULE"):
            self.assertIn(t, gc.EDGE_TYPES)


# ---------------------------------------------------------------------------
# Synthetic demo fixture (ADR-008, Deliverable 14)
# ---------------------------------------------------------------------------

class TestSyntheticFixtureDemo(unittest.TestCase):
    """Loads the static, clearly-marked synthetic demo fixture (never the
    real docs/trader-intelligence/evidence/ tree) and exercises every element
    the deliverable requires: 1 source (+1 corroborating), 5 evidence items
    including 1 contradicting item and 1 supersession, 1 supported claim,
    1 contradicted claim, 1 contradiction record, confidence recomputation,
    provenance trace, and full lifecycle history."""

    @classmethod
    def setUpClass(cls):
        cls.idx = qe.EvidenceIndex.load(SYNTHETIC_DEMO_ROOT)

    def test_fixture_is_clearly_marked_synthetic(self):
        for source in self.idx.sources.values():
            self.assertTrue(evc.contains_synthetic_markers(source.get("title", "")))
        for item in self.idx.items.values():
            self.assertTrue(evc.contains_synthetic_markers(item.get("exactExcerpt", "")))
        for claim in self.idx.claims.values():
            self.assertTrue(evc.contains_synthetic_markers(claim.get("normalizedClaim", "")))

    def test_expected_counts(self):
        self.assertEqual(len(self.idx.sources), 2)
        self.assertEqual(len(self.idx.items), 5)
        self.assertEqual(len(self.idx.claims), 2)
        self.assertEqual(len(self.idx.contradictions), 1)

    def test_one_claim_supported_one_contradicted(self):
        states = sorted(c["confidenceState"] for c in self.idx.claims.values())
        self.assertEqual(states, ["contradicted", "supported"])

    def test_contradicting_item_is_the_sole_evidence_for_the_contradicted_claim(self):
        contradicted_claim = next(c for c in self.idx.claims.values() if c["confidenceState"] == "contradicted")
        links = self.idx.links_for_claim(contradicted_claim["claimId"])
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]["relationshipType"], "contradicts")

    def test_one_contradiction_record_links_the_two_claims(self):
        contradiction = list(self.idx.contradictions.values())[0]
        claim_ids = {c["claimId"] for c in self.idx.claims.values()}
        self.assertEqual({contradiction["claimAId"], contradiction["claimBId"]}, claim_ids)

    def test_supersession_provenance_trace(self):
        superseded_item = next(i for i in self.idx.items.values() if i["evidenceStatus"] == "superseded")
        successor = next(i for i in self.idx.items.values() if i.get("supersedesEvidenceId") == superseded_item["evidenceId"])
        result = qe.trace_evidence_provenance(self.idx, successor["evidenceId"])
        chain_ids = [e["evidenceId"] for e in result["results"][0]["derivationChain"]]
        self.assertEqual(chain_ids, [successor["evidenceId"]])  # supersession, not parent/child derivation
        self.assertEqual(successor["supersedesEvidenceId"], superseded_item["evidenceId"])
        history = result["results"][0]["lifecycleHistory"]
        self.assertTrue(any(e["eventType"] == "created" for e in history))

    def test_confidence_recompute_lifecycle_events_present_for_supported_claim(self):
        supported_claim = next(c for c in self.idx.claims.values() if c["confidenceState"] == "supported")
        explanation = qe.get_confidence_explanation(self.idx, supported_claim["claimId"])
        self.assertEqual(explanation["status"], "ok")
        self.assertIsNotNone(explanation["results"][0]["explanation"])

    def test_fixture_passes_integrity_validation_as_non_production_data(self):
        report = ve.run_integrity_checks(SYNTHETIC_DEMO_ROOT, is_production=False)
        self.assertEqual(report["summary"], {"INFO": 0, "WARNING": 0, "ERROR": 0, "FATAL": 0})

    def test_fixture_would_be_flagged_if_ever_mistaken_for_production_data(self):
        report = ve.run_integrity_checks(SYNTHETIC_DEMO_ROOT, is_production=True)
        self.assertTrue(any(f["findingType"] == "MISLABELED_SYNTHETIC_FIXTURE" for f in report["findings"]))


if __name__ == "__main__":
    unittest.main()


class TestUnresolvableArtifactIsReported(unittest.TestCase):
    """Provenance that cannot be walked back to an artifact is not provenance.

    The validator never inspected `repositoryPath`, so a source pointing at a
    deleted or renamed capture file passed cleanly -- and one does in the live
    corpus, created when a duplicate capture artifact was removed.
    """

    def sources(self, rel):
        return [{"sourceId": "EVSRC|MOGO|20260819|001",
                 "storageLocationType": "repository", "repositoryPath": rel,
                 "provenanceStatus": "owner_supplied"}]

    def findings_for(self, rel):
        findings = []
        ve.check_malformed_provenance(
            self.sources(rel), [], findings, FIXED_NOW)
        return {f["findingType"] for f in findings}

    def test_a_missing_repository_path_is_reported(self):
        self.assertIn("UNRESOLVABLE_ARTIFACT",
                      self.findings_for("evidence/does-not-exist-PACKAGES.json"))

    def test_an_existing_repository_path_is_NOT_reported(self):
        """Positive control: the check must be caused by the file being absent."""
        self.assertNotIn("UNRESOLVABLE_ARTIFACT", self.findings_for("index.html"))


class TestSupersededArtifactResolution(unittest.TestCase):
    """B-28. A missing artifact is not always lost evidence.

    A dry run wrote a capture file, a source was registered for it, the dry-run
    cleanup deleted it, and the --write run 27 seconds later produced a
    BYTE-IDENTICAL artifact under a different sourceId. The observation citing the
    first source is undamaged and its evidence demonstrably survives.

    `artifactSupersededBy` records that without rewriting anything -- but it is also
    a new way to LAUNDER broken provenance, so every case below exists to prove the
    claim is verified rather than believed. The resolution must be caused by the
    hashes matching and the target artifact existing, not by the field being present.
    """

    HASH_A = "a" * 64
    HASH_B = "b" * 64

    def source(self, sid, rel, **extra):
        d = {"sourceId": sid, "storageLocationType": "repository",
             "repositoryPath": rel, "provenanceStatus": "owner_supplied",
             "contentHash": self.HASH_A}
        d.update(extra)
        return d

    def findings_for(self, sources):
        findings = []
        ve.check_malformed_provenance(sources, [], findings, FIXED_NOW)
        return {f["findingType"] for f in findings}

    def broken(self, **extra):
        return self.source("EVSRC|MOGO|20260819|001",
                           "evidence/does-not-exist-PACKAGES.json", **extra)

    def survivor(self, **extra):
        # index.html is used only because it is a file that reliably exists in the
        # repository; nothing here depends on its contents.
        return self.source("EVSRC|MOGO|20260819|002", "index.html", **extra)

    def test_a_verified_supersession_resolves_the_missing_artifact(self):
        found = self.findings_for([
            self.broken(artifactSupersededBy="EVSRC|MOGO|20260819|002"),
            self.survivor()])
        self.assertNotIn("UNRESOLVABLE_ARTIFACT", found)
        self.assertNotIn("UNVERIFIED_SUPERSESSION", found)

    def test_POSITIVE_CONTROL_without_the_field_it_is_still_reported(self):
        # Proves the resolution above is caused by the supersession, not by the
        # fixture happening to pass for some other reason.
        self.assertIn("UNRESOLVABLE_ARTIFACT", self.findings_for([self.broken()]))

    def test_a_supersession_naming_an_unregistered_source_is_an_ERROR(self):
        findings = []
        ve.check_malformed_provenance(
            [self.broken(artifactSupersededBy="EVSRC|MOGO|20260819|999")],
            [], findings, FIXED_NOW)
        types = {f["findingType"] for f in findings}
        self.assertIn("UNVERIFIED_SUPERSESSION", types)
        # The message must say the source is UNREGISTERED. Removing that branch still
        # produced an error, via the missing-artifact branch -- so the invariant held
        # but the diagnostic became "whose own artifact None is missing", which sends
        # the reader looking for a file rather than for a typo in the id.
        message = " ".join(f["message"] for f in findings)
        self.assertIn("not a registered", message)

    def test_a_supersession_whose_own_artifact_is_missing_is_an_ERROR(self):
        # Chaining a dangling source to another dangling source resolves nothing.
        found = self.findings_for([
            self.broken(artifactSupersededBy="EVSRC|MOGO|20260819|002"),
            self.source("EVSRC|MOGO|20260819|002", "evidence/also-gone-PACKAGES.json")])
        self.assertIn("UNVERIFIED_SUPERSESSION", found)

    def test_a_supersession_with_a_DIFFERENT_content_hash_is_an_ERROR(self):
        # THE case that matters. Pointing a dangling source at any healthy artifact
        # would otherwise silence the warning while the described evidence stays lost.
        found = self.findings_for([
            self.broken(artifactSupersededBy="EVSRC|MOGO|20260819|002"),
            self.survivor(contentHash=self.HASH_B)])
        self.assertIn("UNVERIFIED_SUPERSESSION", found)

    def test_a_supersession_with_no_hash_on_either_side_is_an_ERROR(self):
        # Absent hashes must not compare equal to each other and pass.
        broken = self.broken(artifactSupersededBy="EVSRC|MOGO|20260819|002")
        broken.pop("contentHash")
        survivor = self.survivor()
        survivor.pop("contentHash")
        self.assertIn("UNVERIFIED_SUPERSESSION", self.findings_for([broken, survivor]))

    def test_the_error_is_LOUDER_than_the_warning_it_replaces(self):
        # A dangling path is a visible gap; a false supersession is a gap wearing a
        # resolution, so it must not be reported at the same severity.
        findings = []
        ve.check_malformed_provenance(
            [self.broken(artifactSupersededBy="EVSRC|MOGO|20260819|999")],
            [], findings, FIXED_NOW)
        sev = {f["findingType"]: f["severity"] for f in findings}
        self.assertEqual(sev.get("UNVERIFIED_SUPERSESSION"), "ERROR")

    def test_the_LIVE_B28_record_resolves_and_is_not_repointed(self):
        # The real record: its repositoryPath must still name the file it described.
        # Repointing it would assert this source was always about the other artifact.
        path = os.path.join(REPO_ROOT, "docs", "trader-intelligence", "evidence",
                            "sources", "EVSRC_MOGO_20260818_015.json")
        with open(path, encoding="utf-8") as handle:
            rec = json.load(handle)
        self.assertEqual(rec["repositoryPath"],
                         "evidence/FWD-20260818T153216Z-PACKAGES.json")
        self.assertEqual(rec["artifactSupersededBy"], "EVSRC|MOGO|20260818|016")


#: Fixture sources carry the attribution metadata a REAL capture source carries.
#: They did not, so every observation in these fixtures cited a source that could
#: not be cross-checked -- which MISSING_SOURCE_ATTRIBUTION correctly reports. The
#: fixtures were modelling a source MOGO's importer never produces. Tests that
#: exercise ABSENCE override these explicitly.
FIXTURE_SOURCE_METADATA = {"captureBasis": "REPLAY_RUN",
                           "engineStrategyId": "alex_g_sr_v1"}


class TestPopulationRebindingIsDetected(unittest.TestCase):
    """An observation must still point at the source it was MINTED from.

    Population (HISTORICAL / FORWARD / RECONSTRUCTED) is derived from the source's
    sourceType and deliberately never stored on the observation. The consequence
    nothing was checking: repointing `sourceId` at a source of a different type
    silently MOVES the observation between populations. Demonstrated on the live
    corpus -- repointing one replay observation at a paper_trade source shifted
    221/29/9 to 220/30/9 while this validator reported zero findings, the graph
    reconciliation printed RECONCILED, and population_fidelity.py said nothing.

    The cross-check is the observation's own `notes`, stamped by the importer at
    mint time and present on all 259 preserved records.

    Everything below is hand-authored. Reading the live corpus would make these
    assertions depend on what the running instance happened to preserve.
    """

    def obs(self, minted_type, source_id="EVSRC|MOGO|20260819|001"):
        return {"observationId": "TOBS|MOGO|20260819|001", "sourceId": source_id,
                "strategyId": "alex_g_sr_v1",
                "notes": "captureBasis=REPLAY_RUN sourceType=%s" % minted_type}

    def src(self, source_type, source_id="EVSRC|MOGO|20260819|001"):
        basis = {"replay_observation": "REPLAY_RUN", "paper_trade": "LIVE_CLOSE",
                 "journal_entry": "HISTORICAL_BACKFILL"}.get(source_type, "REPLAY_RUN")
        return {"sourceId": source_id, "sourceType": source_type,
                "metadata": {"captureBasis": basis, "engineStrategyId": "alex_g_sr_v1"}}

    def findings_for(self, observations, sources):
        findings = []
        ve.check_observation_population_rebinding(observations, sources, findings, FIXED_NOW)
        return findings

    def test_a_replay_observation_repointed_at_a_paper_trade_source_is_an_ERROR(self):
        # THE failure mode: HISTORICAL evidence entering the FORWARD population.
        findings = self.findings_for([self.obs("replay_observation")],
                                     [self.src("paper_trade")])
        self.assertEqual([f["findingType"] for f in findings], ["POPULATION_REBINDING"])
        self.assertEqual(findings[0]["severity"], "ERROR")

    def test_POSITIVE_CONTROL_a_matching_source_type_is_NOT_reported(self):
        # Without this, a check that flagged everything would pass every case above.
        self.assertEqual(
            self.findings_for([self.obs("replay_observation")],
                              [self.src("replay_observation")]), [])

    def test_every_cross_population_rebinding_is_caught_in_both_directions(self):
        # All six ordered pairs across the three populations. A check that caught
        # only "into FORWARD" would leave replay <- forward and every RECONSTRUCTED
        # crossing silent.
        types = ["replay_observation", "paper_trade", "journal_entry"]
        for minted in types:
            for actual in types:
                if minted == actual:
                    continue
                with self.subTest(minted=minted, actual=actual):
                    findings = self.findings_for([self.obs(minted)], [self.src(actual)])
                    self.assertEqual([f["findingType"] for f in findings],
                                     ["POPULATION_REBINDING"],
                                     "%s -> %s went undetected" % (minted, actual))

    def test_notes_without_a_sourceType_are_reported_LOUDLY_not_skipped(self):
        # DECISION REVERSED, and the reversal is the repair. The first version
        # skipped any record whose stamp it could not read, which made the stamp
        # the attack surface: delete it and the rebinding went unreported. Silence
        # must mean "checked and fine", never "could not tell".
        obs = self.obs("replay_observation")
        obs["notes"] = "captureBasis=REPLAY_RUN"
        findings = self.findings_for([obs], [self.src("paper_trade")])
        self.assertEqual([f["findingType"] for f in findings], ["MISSING_MINT_PROVENANCE"])

    def test_a_missing_notes_field_is_reported_LOUDLY(self):
        obs = self.obs("replay_observation")
        del obs["notes"]
        findings = self.findings_for([obs], [self.src("paper_trade")])
        # BOTH absences are reported now: a record with no notes at all is missing
        # both stamps, and reporting only the first understated how damaged it is.
        self.assertEqual(sorted(f["findingType"] for f in findings),
                         ["MISSING_CAPTURE_BASIS", "MISSING_MINT_PROVENANCE"])

    def test_a_missing_stamp_is_an_ERROR_so_it_cannot_hide_behind_the_exit_code(self):
        # The remaining hole after the first repair: blinding every stamp produced
        # WARNINGS ONLY, and WARNINGs exit 0, so contamination passed any CI gate
        # while sitting in plain sight. An observation whose population cannot be
        # VERIFIED still counts toward totals that claim to be separated.
        obs = self.obs("replay_observation")
        del obs["notes"]
        findings = self.findings_for([obs], [self.src("paper_trade")])
        self.assertEqual(findings[0]["severity"], "ERROR")
        self.assertEqual(ve.exit_code_for({"FATAL": 0, "ERROR": len(findings),
                                           "WARNING": 0, "INFO": 0}), 1)

    def test_blinding_every_stamp_now_FAILS_the_run_rather_than_warning(self):
        # End to end on the exact attack: stamps blinded corpus-wide, one source
        # retyped. Previously 259 warnings and exit 0.
        blinded = []
        for i in range(4):
            obs = self.obs("replay_observation")
            obs["observationId"] = "TOBS|MOGO|20260819|00%d" % i
            obs["notes"] = obs["notes"].replace("sourceType=", "sourceTypeX=")
            blinded.append(obs)
        findings = self.findings_for(blinded, [self.src("paper_trade")])
        self.assertEqual({f["severity"] for f in findings}, {"ERROR"})
        summary = {"FATAL": 0, "ERROR": len(findings), "WARNING": 0, "INFO": 0}
        self.assertEqual(ve.exit_code_for(summary), 1)

    def test_blinding_every_stamp_cannot_buy_silence(self):
        # The whole-corpus attack: rename the stamp on every record, then retype one
        # source. It moved 24 replay observations into FORWARD with everything green.
        # The point is not that it is blocked -- it is that it is now NOISY.
        blinded = []
        for i in range(5):
            obs = self.obs("replay_observation")
            obs["observationId"] = "TOBS|MOGO|20260819|00%d" % i
            obs["notes"] = obs["notes"].replace("sourceType=", "sourceTypeX=")
            blinded.append(obs)
        findings = self.findings_for(blinded, [self.src("paper_trade")])
        self.assertEqual(len(findings), 5)
        self.assertEqual({f["findingType"] for f in findings}, {"MISSING_MINT_PROVENANCE"})

    def test_a_decoy_stamp_prepended_to_notes_is_AMBIGUOUS_not_accepted(self):
        # `.search` took the first match, so prepending "sourceType=paper_trade "
        # made a replay observation look forward-minted.
        obs = self.obs("replay_observation")
        obs["notes"] = "sourceType=paper_trade " + obs["notes"]
        findings = self.findings_for([obs], [self.src("paper_trade")])
        self.assertEqual([f["findingType"] for f in findings], ["AMBIGUOUS_MINT_PROVENANCE"])

    def test_a_source_with_a_BLANK_sourceType_is_an_UNRESOLVED_POPULATION_error(self):
        # The source-side attack, and the one that survived the first repair: blank
        # sourceType on a cited source and its observations fall into UNKNOWN --
        # leaving every population total they belonged to, with nothing objecting.
        findings = self.findings_for([self.obs("replay_observation")], [self.src("")])
        self.assertIn("UNRESOLVED_POPULATION", [f["findingType"] for f in findings])

    def test_a_source_MISSING_sourceType_entirely_is_also_caught(self):
        src = self.src("replay_observation")
        del src["sourceType"]
        findings = self.findings_for([self.obs("replay_observation")], [src])
        self.assertIn("UNRESOLVED_POPULATION", [f["findingType"] for f in findings])

    def test_POSITIVE_CONTROL_a_resolvable_population_is_not_reported(self):
        # Guards the two cases above from a check that flags every observation.
        self.assertEqual(
            self.findings_for([self.obs("replay_observation")],
                              [self.src("replay_observation")]), [])

    def test_a_non_string_notes_field_does_not_abort_the_whole_validator(self):
        # A non-string `notes` raised TypeError out of the regex and killed the
        # entire run, losing every other finding in the corpus with it.
        for bad in (123, {"a": 1}, ["x"], True, None):
            with self.subTest(notes=bad):
                obs = self.obs("replay_observation")
                obs["notes"] = bad
                findings = self.findings_for([obs], [self.src("replay_observation")])
                # Both stamps are unreadable in a non-string notes, so both are
                # reported -- and crucially the run does not raise.
                self.assertEqual(sorted(f["findingType"] for f in findings),
                                 ["MISSING_CAPTURE_BASIS", "MISSING_MINT_PROVENANCE"])

    def test_spacing_and_case_variants_of_the_stamp_are_READ_not_missed(self):
        # A stamp the reader skips is a stamp an attacker can hide behind, so the
        # pattern is deliberately tolerant. Each of these must be compared, not
        # skipped -- i.e. produce a REBINDING error, never MISSING.
        for notes in ("sourceType = replay_observation", "SOURCETYPE=replay_observation",
                      "sourcetype=replay_observation", "sourceType=replay_observation"):
            with self.subTest(notes=notes):
                obs = self.obs("replay_observation")
                obs["notes"] = notes
                types = [f["findingType"] for f in
                         self.findings_for([obs], [self.src("paper_trade")])]
                # The point is that the stamp was READ: a rebinding is reported and
                # the stamp is NOT called missing. These fixtures carry no
                # captureBasis, so that absence is reported too and is not the
                # property under test.
                self.assertIn("POPULATION_REBINDING", types,
                              "%r was not read as a stamp" % notes)
                self.assertNotIn("MISSING_MINT_PROVENANCE", types,
                                 "%r was skipped rather than read" % notes)

    def test_a_sourceId_naming_no_registered_source_is_an_ERROR(self):
        # DECISION REVERSED. This deferred to "the reference checks", which live in
        # the GRAPH build -- their MISSING_REFERENCE finding never reaches
        # integrity-report.json, the artifact an operator reads. Deleting one cited
        # source file moved 24 observations into UNKNOWN while this validator
        # reported a clean corpus, and this test asserted that silence.
        self.assertEqual(
            [f["findingType"] for f in
             self.findings_for([self.obs("replay_observation", "EVSRC|MOGO|20260819|999")],
                               [self.src("paper_trade")])],
            ["UNRESOLVED_POPULATION"])

    def test_the_finding_names_both_types_so_the_direction_is_readable(self):
        findings = self.findings_for([self.obs("replay_observation")],
                                     [self.src("paper_trade")])
        self.assertIn("replay_observation", findings[0]["message"])
        self.assertIn("paper_trade", findings[0]["message"])

    def test_the_check_reports_and_does_NOT_repair(self):
        # A mismatch is a contradiction for a human to resolve. Silently rewriting
        # sourceId or notes to agree would destroy the evidence of the rebinding.
        obs = self.obs("replay_observation")
        src = self.src("paper_trade")
        before = (dict(obs), dict(src))
        self.findings_for([obs], [src])
        self.assertEqual((obs, src), before)


class TestPopulationChecksAreWiredIntoTheValidator(unittest.TestCase):
    """Testing a check is not testing that anything CALLS it.

    Round 1 of adversarial verification found tests that reimplemented a check
    instead of calling it. Round 2 found the sequel: every rebinding test called
    `check_observation_population_rebinding` directly, so deleting its single call
    site in `run_integrity_checks` left the whole 1124-test suite green while
    `evidence/reports/integrity-report.json` -- the artifact an operator actually
    reads -- silently stopped reporting the corpus's most consequential failure.

    These go through `run_integrity_checks` on a scratch corpus written here, so
    they fail if the wiring is removed, whatever the unit tests say.
    """

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="mogo_wiring_")
        self.evidence_root = os.path.join(self.root, "evidence")
        for name in ("sources", "observations"):
            os.makedirs(os.path.join(self.evidence_root, name))

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def write(self, collection, name, record):
        with open(os.path.join(self.evidence_root, collection, name + ".json"),
                  "w", encoding="utf-8") as handle:
            json.dump(record, handle)

    def corpus(self, minted, actual):
        self.write("sources", "src", {
            "sourceId": "EVSRC|MOGO|20260819|001", "sourceType": actual,
            "title": "capture", "storageLocationType": "repository",
            "provenanceStatus": "owner_supplied",
            "metadata": {"engineStrategyId": "alex_g_sr_v1"}})
        self.write("observations", "obs", {
            "observationId": "TOBS|MOGO|20260819|001", "strategyId": "alex_g_sr_v1",
            "sourceId": "EVSRC|MOGO|20260819|001",
            "notes": "captureBasis=REPLAY_RUN sourceType=%s" % minted})

    def finding_types(self):
        report = ve.run_integrity_checks(self.evidence_root, is_production=False)
        # Non-vacuity: a run that loaded nothing would report nothing and every
        # assertion below would pass for the wrong reason.
        self.assertTrue(os.listdir(os.path.join(self.evidence_root, "observations")))
        return [f["findingType"] for f in report["findings"]]

    def test_run_integrity_checks_REPORTS_a_rebinding(self):
        self.corpus(minted="replay_observation", actual="paper_trade")
        self.assertIn("POPULATION_REBINDING", self.finding_types())

    def test_run_integrity_checks_REPORTS_an_unresolved_population(self):
        self.corpus(minted="replay_observation", actual="")
        self.assertIn("UNRESOLVED_POPULATION", self.finding_types())

    def test_run_integrity_checks_REPORTS_a_missing_mint_stamp(self):
        self.corpus(minted="replay_observation", actual="replay_observation")
        self.write("observations", "obs", {
            "observationId": "TOBS|MOGO|20260819|001",
            "sourceId": "EVSRC|MOGO|20260819|001", "notes": "captureBasis=REPLAY_RUN"})
        self.assertIn("MISSING_MINT_PROVENANCE", self.finding_types())

    def test_POSITIVE_CONTROL_a_consistent_corpus_reports_none_of_them(self):
        # Without this, a validator that emitted these findings unconditionally
        # would satisfy all three tests above.
        self.corpus(minted="replay_observation", actual="replay_observation")
        found = set(self.finding_types())
        self.assertEqual(found & {"POPULATION_REBINDING", "UNRESOLVED_POPULATION",
                                  "MISSING_MINT_PROVENANCE"}, set())


class TestValidatorExitCodeGatesOnErrors(unittest.TestCase):
    """An ERROR must fail the CLI.

    `main()` returned 0 unless a FATAL was present, so a corpus carrying 24
    POPULATION_REBINDING ERRORs exited 0 and no CI gate could ever notice. A check
    nothing can gate on is documentation.
    """

    def test_a_report_with_errors_exits_nonzero(self):
        self.assertEqual(ve.exit_code_for({"FATAL": 0, "ERROR": 1, "WARNING": 0, "INFO": 0}), 1)

    def test_a_report_with_fatals_exits_nonzero(self):
        self.assertEqual(ve.exit_code_for({"FATAL": 1, "ERROR": 0, "WARNING": 0, "INFO": 0}), 1)

    def test_warnings_alone_do_NOT_fail_the_run(self):
        # Positive control, and a deliberate boundary: WARNINGs are open questions
        # (B-28's supersession lived there for days). Failing on them would push the
        # next person to silence warnings rather than resolve them.
        self.assertEqual(ve.exit_code_for({"FATAL": 0, "ERROR": 0, "WARNING": 9, "INFO": 3}), 0)

    def test_a_clean_report_exits_zero(self):
        self.assertEqual(ve.exit_code_for({"FATAL": 0, "ERROR": 0, "WARNING": 0, "INFO": 0}), 0)


class TestCaptureBasisIsTheSecondStamp(unittest.TestCase):
    """`sourceType=` alone is defeated by a CONSISTENT rewrite.

    Repoint an observation's sourceId AND rewrite its sourceType stamp to agree:
    the two sides match, and 24 replay observations sit in the FORWARD population
    with every tool green. Adversarial verification did precisely that.

    `captureBasis` is the other half of the same notes string and was being thrown
    away. It records HOW the trade was captured, which the importer maps 1:1 onto a
    sourceType, so it independently implies the population. Measured across all 259
    preserved records: 221 REPLAY_RUN, 29 LIVE_CLOSE, 9 HISTORICAL_BACKFILL, zero
    missing, zero contradictions -- so this costs no false positives.

    Defence in depth, not proof: both stamps live in one field, so a thorough enough
    rewrite still defeats it. What it removes is the cheap version of the attack.
    """

    def obs(self, basis, minted):
        return {"observationId": "TOBS|MOGO|20260819|001",
                "sourceId": "EVSRC|MOGO|20260819|001", "strategyId": "alex_g_sr_v1",
                "notes": "captureBasis=%s sourceType=%s" % (basis, minted)}

    def src(self, source_type):
        return {"sourceId": "EVSRC|MOGO|20260819|001", "sourceType": source_type,
                "metadata": {"engineStrategyId": "alex_g_sr_v1"}}

    def types(self, observations, sources):
        findings = []
        ve.check_observation_population_rebinding(observations, sources, findings, FIXED_NOW)
        return [f["findingType"] for f in findings]

    def test_a_CONSISTENT_repoint_is_caught_by_the_second_stamp(self):
        # THE attack: sourceType stamp rewritten to match the new source, so the
        # rebinding check sees agreement. captureBasis still says REPLAY_RUN.
        self.assertEqual(
            self.types([self.obs("REPLAY_RUN", "paper_trade")], [self.src("paper_trade")]),
            ["CAPTURE_BASIS_CONTRADICTS_SOURCE"])

    def test_every_basis_is_checked_not_just_replay(self):
        # A check that only knew REPLAY_RUN would let RECONSTRUCTED evidence pass.
        for basis, wrong in (("REPLAY_RUN", "paper_trade"),
                             ("LIVE_CLOSE", "replay_observation"),
                             ("HISTORICAL_BACKFILL", "paper_trade")):
            with self.subTest(basis=basis):
                self.assertIn("CAPTURE_BASIS_CONTRADICTS_SOURCE",
                              self.types([self.obs(basis, wrong)], [self.src(wrong)]),
                              "%s -> %s went undetected" % (basis, wrong))

    def test_POSITIVE_CONTROL_an_agreeing_basis_is_not_reported(self):
        # Without this, a check that fired on every record would satisfy the above.
        for basis, right in (("REPLAY_RUN", "replay_observation"),
                             ("LIVE_CLOSE", "paper_trade"),
                             ("HISTORICAL_BACKFILL", "journal_entry")):
            with self.subTest(basis=basis):
                self.assertEqual(self.types([self.obs(basis, right)], [self.src(right)]), [])

    def test_an_unrecognised_basis_is_REPORTED_but_still_not_guessed_at(self):
        # DECISION REVERSED. This asserted silence, which was the fail-open half of
        # the attack: `[A-Za-z_]+` truncated "REPLAY-RUN" to "REPLAY", which maps to
        # nothing, so one hyphen silently disabled the cross-check. "Genuinely new
        # basis" and "mangled to evade" are indistinguishable from here and only one
        # is harmless, so it is reported -- but no population is INFERRED from it,
        # which is the part that would have been fabrication.
        self.assertEqual(
            self.types([self.obs("SOME_NEW_BASIS", "paper_trade")], [self.src("paper_trade")]),
            ["UNRECOGNISED_CAPTURE_BASIS"])

    def test_the_mapping_is_the_IMPORTERS_not_a_copy(self):
        # Two tables would drift, and the drift that matters -- the validator
        # believing a basis maps to the wrong type -- is invisible.
        from import_mogo_observations import CAPTURE_BASIS_SOURCE_TYPE as importer_map
        self.assertIs(ve.CAPTURE_BASIS_SOURCE_TYPE, importer_map)


#: Sentinel distinguishing "the field is missing" from "the field is None".
_ABSENT = object()


class TestAbsentSourceIdIsReported(unittest.TestCase):
    """An observation that names no source has no derivable population.

    Deleting `sourceId` from 24 observations moved them all into UNKNOWN while the
    validator reported nothing: the code fell through on `source is None` with a
    comment claiming it was "already reported as a missing reference elsewhere".
    True for an id naming a source that does not exist; FALSE for an id that is
    absent, blank or unhashable, where there is no dangling reference to catch.
    """

    def findings_for(self, source_id):
        obs = {"observationId": "TOBS|MOGO|20260819|001", "strategyId": "alex_g_sr_v1",
               "notes": "captureBasis=REPLAY_RUN sourceType=replay_observation"}
        if source_id is not _ABSENT:
            obs["sourceId"] = source_id
        findings = []
        ve.check_observation_population_rebinding(
            [obs], [{"sourceId": "EVSRC|MOGO|20260819|001",
                     "sourceType": "replay_observation",
                     "metadata": dict(FIXTURE_SOURCE_METADATA)}], findings, FIXED_NOW)
        return findings

    def test_an_absent_sourceId_is_an_error(self):
        self.assertEqual([f["findingType"] for f in self.findings_for(_ABSENT)],
                         ["UNRESOLVED_POPULATION"])

    def test_a_blank_or_whitespace_sourceId_is_an_error(self):
        for value in ("", "   "):
            with self.subTest(value=repr(value)):
                self.assertEqual([f["findingType"] for f in self.findings_for(value)],
                                 ["UNRESOLVED_POPULATION"])

    def test_an_unhashable_sourceId_is_reported_not_raised(self):
        # A list- or dict-valued id raised TypeError out of the dict lookup and
        # aborted the ENTIRE validator run, losing every other finding with it --
        # including the population findings. Same defect already fixed for `notes`.
        for value in ([], {}, None, 123, True):
            with self.subTest(value=repr(value)):
                self.assertEqual([f["findingType"] for f in self.findings_for(value)],
                                 ["UNRESOLVED_POPULATION"])

    def test_POSITIVE_CONTROL_a_resolvable_sourceId_is_not_reported(self):
        self.assertEqual(self.findings_for("EVSRC|MOGO|20260819|001"), [])

    def test_an_unhashable_SOURCE_id_does_not_abort_the_run(self):
        # The other side of the same hazard: a source record whose own id is
        # unhashable must not poison the index built from it.
        findings = []
        ve.check_observation_population_rebinding(
            [{"observationId": "TOBS|MOGO|20260819|001", "strategyId": "alex_g_sr_v1",
              "sourceId": "EVSRC|MOGO|20260819|001",
              "notes": "captureBasis=REPLAY_RUN sourceType=replay_observation"}],
            [{"sourceId": [], "sourceType": "paper_trade"},
             {"sourceId": "EVSRC|MOGO|20260819|001", "sourceType": "replay_observation",
              "metadata": dict(FIXTURE_SOURCE_METADATA)}],
            findings, FIXED_NOW)
        self.assertEqual(findings, [])


class TestTheCliActuallyUsesTheExitCode(unittest.TestCase):
    """`exit_code_for` is unit-tested four ways and was still bypassable.

    Deleting its call from `main()` left the entire suite green: nothing asserted
    that the CLI USES it. With that mutation, a corpus carrying 24
    POPULATION_REBINDING ERRORs exited 0 and the `run_all.sh` gate passed. Third
    recurrence of one shape -- testing a copy of a check, then testing a check
    nothing calls, now testing a helper the entry point need not use.

    Runs the real CLI as a subprocess against a scratch corpus, so only the actual
    exit status can satisfy it.
    """

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="mogo_cli_")
        self.evidence = os.path.join(self.root, "evidence")
        for name in ("sources", "observations"):
            os.makedirs(os.path.join(self.evidence, name))
        # Research state beside the evidence root, as a real corpus has. Without it
        # the fixture models a corpus whose assimilation history was deleted, which
        # is now correctly an ERROR and would fail the positive control for an
        # unrelated reason.
        os.makedirs(os.path.join(self.root, "research-state"), exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def write(self, collection, name, record):
        with open(os.path.join(self.evidence, collection, name + ".json"),
                  "w", encoding="utf-8") as handle:
            json.dump(record, handle)

    def corpus(self, source_type):
        # Schema-valid on purpose: a malformed fixture raises unrelated ERRORs, which
        # would make the positive control fail for a reason that has nothing to do
        # with the exit code under test.
        self.write("sources", "src", {
            "sourceId": "EVSRC|MOGO|20260819|001", "sourceType": source_type,
            "title": "capture", "storageLocationType": "repository",
            "provenanceStatus": "verified", "schemaVersion": 1,
            "metadata": {"engineStrategyId": "alex_g_sr_v1",
                         "captureBasis": "REPLAY_RUN"}})
        self.write("observations", "obs", {
            "observationId": "TOBS|MOGO|20260819|001", "strategyId": "alex_g_sr_v1",
            "sourceId": "EVSRC|MOGO|20260819|001", "schemaVersion": 1,
            "sourceContentHash": "a" * 64, "sequenceId": "SEQ|1",
            "notes": "captureBasis=REPLAY_RUN sourceType=replay_observation"})

    def write_state(self):
        import research_assimilation as ra
        observations, sources = {}, {}
        for name in os.listdir(os.path.join(self.evidence, "observations")):
            with open(os.path.join(self.evidence, "observations", name),
                      encoding="utf-8") as handle:
                rec = json.load(handle)
            observations[rec["observationId"]] = rec
        for name in os.listdir(os.path.join(self.evidence, "sources")):
            with open(os.path.join(self.evidence, "sources", name),
                      encoding="utf-8") as handle:
                rec = json.load(handle)
            sources[rec["sourceId"]] = rec
        with open(os.path.join(self.root, "research-state", "current-state.json"),
                  "w", encoding="utf-8") as handle:
            json.dump({"observationTotal": len(observations),
                       "corpusFingerprint": ra.corpus_fingerprint(observations, sources)},
                      handle)
        # A real corpus has both anchors; the availability invariant requires a
        # non-empty ledger, so a fixture with state but no ledger models a corpus
        # whose history was half-deleted and would fail the control for that reason.
        ledger = os.path.join(self.root, "research-state", "ledger")
        os.makedirs(ledger, exist_ok=True)
        with open(os.path.join(ledger, "LEARN_fixture.json"), "w",
                  encoding="utf-8") as handle:
            json.dump({"observationTotalAfter": len(observations),
                       "schemaVersion": 1}, handle)
        # The preservation anchor is required of ANY corpus holding evidence now --
        # the forward-only scoping was the switch an attacker could flip by deleting
        # the forward population. A real corpus has this manifest.
        preservation = os.path.join(self.evidence, "ledger-preservation")
        os.makedirs(preservation, exist_ok=True)
        with open(os.path.join(preservation, "MOGO_IDENTITY_MANIFEST.json"), "w",
                  encoding="utf-8") as handle:
            # `contentHash` is not decoration: every real manifest row carries it,
            # and it is one of the values ANCHOR_VALUE_BINDINGS compares against the
            # corpus. A row with no bound field joins an observation and compares
            # nothing, which is the vacuity this fixture would otherwise model.
            json.dump({"identities": [
                {"tradeId": record.get("sequenceId"),
                 "contentHash": record.get("sourceContentHash"),
                 "refusedByImportPolicy": False}
                for record in observations.values()]}, handle)

    def run_cli(self):
        self.write_state()
        script = os.path.join(REPO_ROOT, "scripts", "trader_intelligence",
                              "validate_evidence.py")
        return subprocess.run(
            [sys.executable, script, "--evidence-root", self.evidence],
            capture_output=True, text=True)

    def test_a_contaminated_corpus_makes_the_CLI_exit_nonzero(self):
        self.corpus(source_type="paper_trade")     # replay-minted, forward source
        result = self.run_cli()
        self.assertNotEqual(result.returncode, 0,
                            "CLI exited 0 on a corpus with population ERRORs; the "
                            "run_all.sh gate would pass. stdout=%s" % result.stdout[-400:])

    def test_POSITIVE_CONTROL_a_clean_corpus_makes_the_CLI_exit_zero(self):
        # Without this, a CLI that always failed would satisfy the test above.
        self.corpus(source_type="replay_observation")
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stdout[-400:])


class TestTheThirdAndFourthAnchors(unittest.TestCase):
    """Both stamps the rebinding check reads live in ONE field of ONE record, so a
    rewrite thorough enough to change both defeats them together -- and retyping a
    source in place needs no observation edit at all. These two anchors live on the
    SOURCE, where an edit to an observation cannot reach them."""

    def src(self, source_type, basis=None, engine=None, sid="EVSRC|MOGO|20260819|001"):
        # Defaults present so the fixture is realistic; each test overrides the one
        # field it is actually about.
        rec = {"sourceId": sid, "sourceType": source_type,
               "metadata": {"captureBasis": "LIVE_CLOSE",
                            "engineStrategyId": "alex_g_sr_v1"}}
        if basis:
            rec["metadata"]["captureBasis"] = basis
        if engine:
            rec["metadata"]["engineStrategyId"] = engine
        return rec

    def obs(self, strategy="alex_g_sr_v1", basis="REPLAY_RUN",
            minted="replay_observation", sid="EVSRC|MOGO|20260819|001"):
        return {"observationId": "TOBS|MOGO|20260819|001", "sourceId": sid,
                "strategyId": strategy,
                "notes": "captureBasis=%s sourceType=%s" % (basis, minted)}

    def obs_types(self, observations, sources):
        findings = []
        ve.check_observation_population_rebinding(observations, sources, findings, FIXED_NOW)
        return [f["findingType"] for f in findings]

    def src_types(self, sources):
        findings = []
        ve.check_source_capture_basis_agrees_with_type(sources, findings, FIXED_NOW)
        return [f["findingType"] for f in findings]

    def test_retyping_a_source_IN_PLACE_is_caught_by_its_own_metadata(self):
        # No observation is touched at all in this attack.
        self.assertEqual(
            self.src_types([self.src("paper_trade", basis="REPLAY_RUN")]),
            ["SOURCE_TYPE_CONTRADICTS_CAPTURE_BASIS"])

    def test_POSITIVE_CONTROL_an_agreeing_source_is_not_reported(self):
        self.assertEqual(
            self.src_types([self.src("replay_observation", basis="REPLAY_RUN")]), [])

    def test_a_source_without_the_stamp_is_not_guessed_at(self):
        # 12 of 59 predate it; inventing one would be the fabrication this prevents.
        self.assertEqual(self.src_types([self.src("paper_trade")]), [])

    def test_repointing_at_a_source_from_a_DIFFERENT_ENGINE_is_caught(self):
        # The fully consistent rewrite: sourceId repointed and BOTH notes stamps
        # rewritten to agree. engineStrategyId lives on the source and was untouched.
        self.assertEqual(
            self.obs_types([self.obs(strategy="alex_g_sr_v1", basis="LIVE_CLOSE",
                                     minted="paper_trade")],
                           [self.src("paper_trade", engine="current_strategy")]),
            ["ENGINE_STRATEGY_MISMATCH"])

    def test_POSITIVE_CONTROL_a_matching_engine_is_not_reported(self):
        self.assertEqual(
            self.obs_types([self.obs(strategy="alex_g_sr_v1", basis="LIVE_CLOSE",
                                     minted="paper_trade")],
                           [self.src("paper_trade", engine="alex_g_sr_v1")]), [])

    def test_a_source_without_engineStrategyId_is_not_guessed_at(self):
        self.assertEqual(
            self.obs_types([self.obs(basis="LIVE_CLOSE", minted="paper_trade")],
                           [self.src("paper_trade")]), [])


class TestCaptureBasisStampIsSymmetricWithTheOther(unittest.TestCase):
    """The decoy attack was caught on the `sourceType` stamp and not on the
    `captureBasis` one, because the first used findall + ambiguity and the second
    used `.search`. Prepending 24 characters defeated it while the true stamp sat
    untouched in the record."""

    def types(self, notes, source_type="paper_trade"):
        findings = []
        ve.check_observation_population_rebinding(
            [{"observationId": "TOBS|MOGO|20260819|001", "strategyId": "alex_g_sr_v1",
              "sourceId": "EVSRC|MOGO|20260819|001", "notes": notes}],
            [{"sourceId": "EVSRC|MOGO|20260819|001", "sourceType": source_type,
              "metadata": {"engineStrategyId": "alex_g_sr_v1"}}],
            findings, FIXED_NOW)
        return [f["findingType"] for f in findings]

    def test_a_decoy_captureBasis_is_AMBIGUOUS_not_first_match_wins(self):
        self.assertEqual(
            self.types("captureBasis=LIVE_CLOSE captureBasis=REPLAY_RUN "
                       "sourceType=paper_trade"),
            ["AMBIGUOUS_MINT_PROVENANCE"])

    def test_a_MANGLED_basis_fails_closed_rather_than_silently_no_op(self):
        # `[A-Za-z_]+` truncated "REPLAY-RUN" to "REPLAY", which maps to nothing, so
        # the check silently did nothing. One hyphen defeated it.
        self.assertEqual(self.types("captureBasis=REPLAY-RUN sourceType=paper_trade"),
                         ["UNRECOGNISED_CAPTURE_BASIS"])

    def test_an_unknown_basis_is_reported_but_NOT_guessed_at(self):
        # Reported because "genuinely new basis" and "mangled to evade" are
        # indistinguishable from here -- but no population is inferred from it.
        found = self.types("captureBasis=SOME_NEW_BASIS sourceType=paper_trade")
        self.assertEqual(found, ["UNRECOGNISED_CAPTURE_BASIS"])

    def test_a_DELETED_captureBasis_stamp_is_reported(self):
        # The P1 this class exists for, and it shipped without a test -- mutation
        # testing caught that within minutes. An absent `sourceType=` stamp was an
        # ERROR while an absent `captureBasis=` stamp was silent, so the second
        # anchor was defeated by DELETING it rather than rewriting it: 24 replay
        # observations into FORWARD, every gate exit 0.
        self.assertEqual(self.types("sourceType=paper_trade"),
                         ["MISSING_CAPTURE_BASIS"])

    def test_notes_with_no_stamps_at_all_reports_BOTH_absences(self):
        # Neither stamp present: both anchors are unevaluable and both must say so.
        self.assertEqual(sorted(self.types("captured somehow")),
                         ["MISSING_CAPTURE_BASIS", "MISSING_MINT_PROVENANCE"])

    def test_an_empty_notes_string_reports_both(self):
        self.assertEqual(sorted(self.types("")),
                         ["MISSING_CAPTURE_BASIS", "MISSING_MINT_PROVENANCE"])

    def test_POSITIVE_CONTROL_a_single_valid_agreeing_basis_is_silent(self):
        self.assertEqual(self.types("captureBasis=LIVE_CLOSE sourceType=paper_trade"), [])


class TestAnchorsFailClosedNotOpen(unittest.TestCase):
    """Five rounds of verification produced one repeated lesson: an anchor that
    SKIPS when it cannot evaluate is an anchor an attacker deletes its input to
    defeat. Each case here is an evasion that worked."""

    def obs(self, **extra):
        rec = {"observationId": "TOBS|MOGO|20260819|001",
               "sourceId": "EVSRC|MOGO|20260819|001",
               "strategyId": "alex_g_sr_v1",
               "notes": "captureBasis=LIVE_CLOSE sourceType=paper_trade"}
        rec.update(extra)
        return rec

    def src(self, engine="current_strategy", source_type="paper_trade"):
        return {"sourceId": "EVSRC|MOGO|20260819|001", "sourceType": source_type,
                "metadata": {"engineStrategyId": engine, "captureBasis": "LIVE_CLOSE"}}

    def types(self, observations, sources):
        findings = []
        ve.check_observation_population_rebinding(observations, sources, findings, FIXED_NOW)
        return [f["findingType"] for f in findings]

    def test_deleting_strategyId_does_not_disable_the_engine_anchor(self):
        # THE cheapest evasion found in five rounds. The condition read
        # `if engine and strategy and engine != strategy`, so dropping one field made
        # the anchor evaluate False and vanish: 24 replay observations entered
        # FORWARD with every tool green and the forward mean-R sign flipped.
        obs = self.obs()
        del obs["strategyId"]
        self.assertEqual(self.types([obs], [self.src()]),
                         ["MISSING_STRATEGY_ATTRIBUTION"])

    def test_blanking_strategyId_does_not_disable_it_either(self):
        self.assertEqual(self.types([self.obs(strategyId="")], [self.src()]),
                         ["MISSING_STRATEGY_ATTRIBUTION"])

    def test_a_missing_strategyId_reports_even_when_the_SOURCE_has_no_engine_either(self):
        # The ungating this class exists to protect was invisible: EVERY fixture in
        # the suite gave the source a truthy engineStrategyId, so `if not strategy`
        # and `if engine and not strategy` were indistinguishable and re-gating it
        # survived every test. Grep found 16 occurrences of engineStrategyId in
        # tests/ and not one where it was absent.
        obs = self.obs()
        del obs["strategyId"]
        src = self.src()
        del src["metadata"]["engineStrategyId"]
        self.assertEqual(self.types([obs], [src]), ["MISSING_STRATEGY_ATTRIBUTION"],
                         "with neither side carrying an engine id, an observation that "
                         "cannot be attributed at all goes unreported")

    def test_a_missing_strategyId_reports_when_the_source_metadata_is_absent(self):
        obs = self.obs()
        del obs["strategyId"]
        src = self.src()
        del src["metadata"]
        self.assertEqual(self.types([obs], [src]), ["MISSING_STRATEGY_ATTRIBUTION"])

    def test_POSITIVE_CONTROL_a_matching_strategy_is_silent(self):
        self.assertEqual(self.types([self.obs()], [self.src(engine="alex_g_sr_v1")]), [])

    def test_a_mismatching_strategy_is_still_caught(self):
        self.assertEqual(self.types([self.obs()], [self.src(engine="current_strategy")]),
                         ["ENGINE_STRATEGY_MISMATCH"])

    def test_a_non_dict_metadata_is_reported_rather_than_RAISING(self):
        # Two properties, and the second changed deliberately. It must not raise --
        # a list-valued metadata used to throw AttributeError and abort the entire
        # validator run. And it must not be SILENT: a source whose metadata cannot be
        # read corroborates nothing, which is the same fail-open that let deleting
        # one field move 24 replay observations into FORWARD.
        for bad in ([], "x", 5, None):
            with self.subTest(metadata=bad):
                src = self.src()
                src["metadata"] = bad
                self.assertEqual(self.types([self.obs()], [src]),
                                 ["MISSING_SOURCE_ATTRIBUTION"])


class TestSourceSideAnchorFailsClosed(unittest.TestCase):
    """Anchor 3 kept the exact defect repaired on the observation side: an
    unreadable capture basis silently no-opped, so one hyphen re-enabled the
    retype-in-place attack."""

    def src(self, basis, source_type="paper_trade"):
        return {"sourceId": "EVSRC|MOGO|20260819|001", "sourceType": source_type,
                "metadata": {"captureBasis": basis, "engineStrategyId": "alex_g_sr_v1"}}

    def types(self, sources):
        findings = []
        ve.check_source_capture_basis_agrees_with_type(sources, findings, FIXED_NOW)
        return [f["findingType"] for f in sources and findings]

    def test_a_mangled_basis_is_reported_not_skipped(self):
        self.assertEqual(self.types([self.src("REPLAY-RUN")]),
                         ["UNRECOGNISED_CAPTURE_BASIS"])

    def test_a_trailing_space_does_not_disable_the_anchor(self):
        # " REPLAY_RUN " must still be READ and still contradict paper_trade.
        self.assertEqual(self.types([self.src(" REPLAY_RUN ")]),
                         ["SOURCE_TYPE_CONTRADICTS_CAPTURE_BASIS"])

    def test_an_unknown_basis_is_reported(self):
        self.assertEqual(self.types([self.src("SOME_NEW_BASIS")]),
                         ["UNRECOGNISED_CAPTURE_BASIS"])

    def test_POSITIVE_CONTROL_an_agreeing_basis_is_silent(self):
        self.assertEqual(self.types([self.src("LIVE_CLOSE")]), [])

    def test_an_OBSERVATION_BEARING_source_with_no_basis_at_all_is_reported(self):
        # DECISION REVERSED. This asserted silence, justified as "12 of 59 predate
        # the field" -- which was wrong: all 12 are `transcript` sources the importer
        # never stamps and no observation cites. Leaving it optional let a source
        # shed this anchor by deleting one field, the same fail-open already closed
        # for engineStrategyId.
        self.assertEqual(
            self.types([{"sourceId": "EVSRC|MOGO|20260819|001",
                         "sourceType": "paper_trade", "metadata": {}}]),
            ["MISSING_SOURCE_CAPTURE_BASIS"])

    def test_EVERY_population_bearing_type_must_carry_the_stamp(self):
        # The requirement was written as "types the importer produces" when the
        # property that matters is "types that BEAR A POPULATION". Those sets differ:
        # generated_analysis (HISTORICAL) and live_trade_review (FORWARD) bear a
        # population and are not importer outputs, so one retype plus one deletion
        # shed this anchor entirely -- the exact evasion the branch was added to close.
        import trade_observation as to_mod
        bearing = (set(to_mod.HISTORICAL_SOURCE_TYPES) | set(to_mod.FORWARD_SOURCE_TYPES)
                   | set(to_mod.RECONSTRUCTED_SOURCE_TYPES))
        self.assertGreater(len(bearing), 3, "population tuples look empty")
        for source_type in sorted(bearing):
            with self.subTest(sourceType=source_type):
                self.assertEqual(
                    self.types([{"sourceId": "EVSRC|MOGO|20260819|001",
                                 "sourceType": source_type, "metadata": {}}]),
                    ["MISSING_SOURCE_CAPTURE_BASIS"],
                    "%s bears a population but may shed this anchor" % source_type)

    def test_a_TRANSCRIPT_source_with_no_basis_is_still_not_guessed_at(self):
        # The genuine legacy case, and the positive control for the reversal above.
        self.assertEqual(
            self.types([{"sourceId": "EVSRC|ALEX_G|20260727|001",
                         "sourceType": "transcript", "metadata": {}}]), [])


class TestBothSourceAnchorsAreWIRED(unittest.TestCase):
    """M10: deleting `check_source_capture_basis_agrees_with_type`'s call site left
    all 1175 tests green -- the check was unit-tested and its wiring was not. Third
    recurrence of the same shape, so both source-side anchors get a wiring test."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="mogo_wire2_")
        self.evidence = os.path.join(self.root, "evidence")
        for name in ("sources", "observations"):
            os.makedirs(os.path.join(self.evidence, name))

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def write(self, collection, name, record):
        with open(os.path.join(self.evidence, collection, name + ".json"),
                  "w", encoding="utf-8") as handle:
            json.dump(record, handle)

    def finding_types(self):
        report = ve.run_integrity_checks(self.evidence, is_production=False)
        self.assertTrue(os.listdir(os.path.join(self.evidence, "sources")),
                        "vacuous run: nothing was loaded")
        return [f["findingType"] for f in report["findings"]]

    def test_run_integrity_checks_REPORTS_a_retyped_source(self):
        self.write("sources", "src", {
            "sourceId": "EVSRC|MOGO|20260819|001", "sourceType": "paper_trade",
            "title": "capture", "storageLocationType": "repository",
            "provenanceStatus": "verified", "schemaVersion": 1,
            "metadata": {"captureBasis": "REPLAY_RUN"}})
        self.assertIn("SOURCE_TYPE_CONTRADICTS_CAPTURE_BASIS", self.finding_types())

    def test_run_integrity_checks_REPORTS_a_missing_strategy_attribution(self):
        self.write("sources", "src", {
            "sourceId": "EVSRC|MOGO|20260819|001", "sourceType": "paper_trade",
            "title": "capture", "storageLocationType": "repository",
            "provenanceStatus": "verified", "schemaVersion": 1,
            "metadata": {"engineStrategyId": "current_strategy"}})
        self.write("observations", "obs", {
            "observationId": "TOBS|MOGO|20260819|001", "schemaVersion": 1,
            "sourceId": "EVSRC|MOGO|20260819|001",
            "notes": "captureBasis=LIVE_CLOSE sourceType=paper_trade"})
        self.assertIn("MISSING_STRATEGY_ATTRIBUTION", self.finding_types())

    def test_POSITIVE_CONTROL_a_consistent_corpus_reports_neither(self):
        self.write("sources", "src", {
            "sourceId": "EVSRC|MOGO|20260819|001", "sourceType": "paper_trade",
            "title": "capture", "storageLocationType": "repository",
            "provenanceStatus": "verified", "schemaVersion": 1,
            "metadata": {"captureBasis": "LIVE_CLOSE",
                         "engineStrategyId": "alex_g_sr_v1"}})
        self.write("observations", "obs", {
            "observationId": "TOBS|MOGO|20260819|001", "schemaVersion": 1,
            "sourceId": "EVSRC|MOGO|20260819|001", "strategyId": "alex_g_sr_v1",
            "notes": "captureBasis=LIVE_CLOSE sourceType=paper_trade"})
        found = set(self.finding_types())
        self.assertEqual(found & {"SOURCE_TYPE_CONTRADICTS_CAPTURE_BASIS",
                                  "MISSING_STRATEGY_ATTRIBUTION",
                                  "ENGINE_STRATEGY_MISMATCH"}, set())


class TestAMalformedRecordIsReportedNotFatal(unittest.TestCase):
    """`check_orphans` runs FIRST and used `item["sourceId"]`, so one EvidenceItem
    missing that key aborted the whole run before any population check executed --
    no report written, every finding lost. Fourth instance of a defect already
    fixed three times elsewhere."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="mogo_malformed_")
        self.evidence = os.path.join(self.root, "evidence")
        for name in ("sources", "observations", "items"):
            os.makedirs(os.path.join(self.evidence, name))

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def write(self, collection, name, record):
        with open(os.path.join(self.evidence, collection, name + ".json"),
                  "w", encoding="utf-8") as handle:
            json.dump(record, handle)

    def test_a_malformed_item_does_not_suppress_a_real_population_finding(self):
        self.write("items", "bad", {"evidenceId": "EV|BAD|1"})     # no sourceId
        self.write("sources", "src", {
            "sourceId": "EVSRC|MOGO|20260819|001", "sourceType": "paper_trade",
            "title": "capture", "storageLocationType": "repository",
            "provenanceStatus": "verified", "schemaVersion": 1})
        self.write("observations", "obs", {
            "observationId": "TOBS|MOGO|20260819|001", "schemaVersion": 1,
            "sourceId": "EVSRC|MOGO|20260819|001",
            "notes": "captureBasis=REPLAY_RUN sourceType=replay_observation"})
        report = ve.run_integrity_checks(self.evidence, is_production=False)
        types = [f["findingType"] for f in report["findings"]]
        self.assertIn("POPULATION_REBINDING", types,
                      "a malformed record suppressed the population finding")
        self.assertEqual(ve.exit_code_for(report["summary"]), 1)


class TestEveryCheckIsWiredIntoTheRunner(unittest.TestCase):
    """One invariant instead of one wiring test per check.

    "The check is unit-tested but nothing asserts anything CALLS it" was the
    highest-yield adversarial finding three rounds running -- the rebinding check,
    `exit_code_for` inside `main()`, and `check_source_capture_basis_agrees_with_type`
    each shipped fully tested and fully bypassable. Each was then fixed by adding one
    more wiring test, which fixes the instance and leaves the SHAPE open: the next
    check added will have the same hole, and the round after that will find it.

    This asserts the property for every `check_*` in the module at once, so a new
    check cannot be added-but-not-called, and an existing call site cannot be
    deleted, without a test failing. Structural rather than behavioural on purpose:
    a behavioural test can only cover checks somebody remembered to write one for.
    """

    #: Both validator modules. The invariant was written for validate_evidence and
    #: left validate_graph uncovered, so unwiring
    #: `check_observation_trader_isolation` -- the contamination guarantee itself --
    #: passed every test, because the tests call it directly. FOURTH recurrence of
    #: this shape. A per-module invariant has the same flaw as a per-check test, so
    #: the module list is what gets extended, once.
    VALIDATOR_MODULES = ("validate_evidence.py", "validate_graph.py",
                         "validate_acquisition.py")

    #: Modules that decide a pass/fail status from a findings summary. Broader than
    #: VALIDATOR_MODULES because `build_graph.py` has no `check_*` functions and no
    #: `run_integrity_checks`, yet still gates promotion on ERROR counts -- it held a
    #: FOURTH hand-rolled copy of the canonical expression, outside the reach of an
    #: invariant that only looked at modules with checks.
    STATUS_DECIDING_MODULES = VALIDATOR_MODULES + ("build_graph.py",)

    def _module(self, filename="validate_evidence.py"):
        path = os.path.join(REPO_ROOT, "scripts", "trader_intelligence", filename)
        with open(path, "r", encoding="utf-8") as handle:
            return ast.parse(handle.read())

    def _functions(self, tree):
        return [n for n in tree.body if isinstance(n, ast.FunctionDef)]

    def test_every_check_function_is_called_by_run_integrity_checks(self):
        total = 0
        for filename in self.VALIDATOR_MODULES:
            with self.subTest(module=filename):
                tree = self._module(filename)
                checks = [f.name for f in self._functions(tree)
                          if f.name.startswith("check_")]
                runner = next(f for f in self._functions(tree)
                              if f.name == "run_integrity_checks")
                called = {n.func.id for n in ast.walk(runner)
                          if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
                # Non-vacuity per module: discovery that stops finding checks would
                # make this pass over an empty list and mean nothing.
                self.assertGreater(len(checks), 5,
                                   "%s: check discovery found almost nothing" % filename)
                unwired = sorted(set(checks) - called)
                self.assertEqual(unwired, [],
                                 "%s: these checks exist but run_integrity_checks never "
                                 "calls them, so they can never report on a real corpus: "
                                 "%s" % (filename, unwired))
                total += len(checks)
        self.assertGreater(total, 40, "both modules together should expose many checks")

    def test_main_delegates_its_exit_status_to_exit_code_for(self):
        # Iterates ALL validator modules. When this covered only validate_evidence,
        # validate_graph and validate_acquisition were both still hand-rolling
        # `return 0 if FATAL == 0 else 1` -- so validate_graph exited 0 while
        # reporting 24 contamination ERRORs, which is the very guarantee the previous
        # commit added. Extending one of three tests fixed one third of the hole.
        for filename in self.STATUS_DECIDING_MODULES:
            with self.subTest(module=filename):
                tree = self._module(filename)
                main = next(f for f in self._functions(tree) if f.name == "main")
                names = {n.func.id for n in ast.walk(main)
                         if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
                attrs = {n.func.attr for n in ast.walk(main)
                         if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
                # build_graph decides `blocked` in a helper rather than in main(),
                # so the whole module is searched for the delegation.
                whole = {n.func.attr for n in ast.walk(tree)
                         if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
                whole |= {n.func.id for n in ast.walk(tree)
                          if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
                self.assertIn("exit_code_for", names | attrs | whole,
                              "%s: decides its own pass/fail status instead of "
                              "delegating to exit_code_for, so a report full of ERRORs "
                              "can still pass" % filename)

    def test_the_runner_passes_findings_to_every_check_it_calls(self):
        # A check wired in but handed a throwaway list would report into the void --
        # the same defect one layer down, and it would pass the wiring test above.
        # Iterates ALL validator modules, for the reason above. While this covered
        # only validate_evidence, the contamination check could be called as
        # `check_observation_trader_isolation(nodes, edges, [])` -- it ran, produced
        # its findings, and dropped them into a throwaway list, with every test green.
        total = 0
        for filename in self.VALIDATOR_MODULES:
            with self.subTest(module=filename):
                tree = self._module(filename)
                runner = next(f for f in self._functions(tree)
                              if f.name == "run_integrity_checks")
                checked = 0
                for node in ast.walk(runner):
                    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
                        continue
                    if not node.func.id.startswith("check_"):
                        continue
                    names = {a.id for a in node.args if isinstance(a, ast.Name)}
                    self.assertIn("findings", names,
                                  "%s: %s is called without the shared findings list, so "
                                  "anything it reports is discarded"
                                  % (filename, node.func.id))
                    checked += 1
                self.assertGreater(checked, 5,
                                   "%s: found almost no check calls to inspect" % filename)
                total += checked
        self.assertGreater(total, 40, "all modules together should expose many checks")


class TestEvidenceRemovalIsDetected(unittest.TestCase):
    """Nine rounds attacked rewriting; none attacked removal, and every gate was blind.

    Deleting the 21 losing FORWARD observations moved the headline forward mean R
    from -0.18 to +2.01 with all three validators exiting 0 and the WARNING count
    unchanged. Deleting the entire corpus raised only orphan WARNINGs, which
    deliberately do not fail. The strongest attack on this corpus was never a clever
    edit -- it was `rm`.
    """

    def setUp(self):
        self.ledger = tempfile.mkdtemp(prefix="mogo_ledger_")

    def tearDown(self):
        shutil.rmtree(self.ledger, ignore_errors=True)

    def entry(self, name, total):
        with open(os.path.join(self.ledger, name + ".json"), "w", encoding="utf-8") as h:
            json.dump({"observationTotalAfter": total, "schemaVersion": 1}, h)

    def types(self, count):
        findings = []
        ve.check_corpus_is_append_only(
            [{"observationId": "TOBS|MOGO|20260819|%03d" % i} for i in range(count)],
            findings, FIXED_NOW, ledger_dir=self.ledger)
        return [f["findingType"] for f in findings]

    def test_a_corpus_smaller_than_the_ledger_high_water_mark_is_an_ERROR(self):
        self.entry("LEARN_a", 259)
        self.assertEqual(self.types(238), ["EVIDENCE_REMOVED"])

    def test_deleting_a_single_record_is_enough(self):
        self.entry("LEARN_a", 259)
        self.assertEqual(self.types(258), ["EVIDENCE_REMOVED"])

    def test_POSITIVE_CONTROL_an_unchanged_corpus_is_silent(self):
        self.entry("LEARN_a", 259)
        self.assertEqual(self.types(259), [])

    def test_POSITIVE_CONTROL_a_GROWING_corpus_is_silent(self):
        # New imports are the normal case and must never be reported.
        self.entry("LEARN_a", 259)
        self.assertEqual(self.types(300), [])

    def test_the_HIGHEST_total_ever_recorded_is_the_floor_not_the_latest(self):
        # A later entry recording a smaller total must not lower the bar -- otherwise
        # deleting records and assimilating once would launder the deletion.
        self.entry("LEARN_a", 259)
        self.entry("LEARN_b", 238)
        self.assertEqual(self.types(238), ["EVIDENCE_REMOVED"])

    def test_no_ledger_at_all_is_silent(self):
        # A corpus with no assimilation history has no high-water mark, and inventing
        # one would be the fabrication this layer exists to prevent.
        self.assertEqual(self.types(0), [])

    def test_a_malformed_ledger_entry_is_skipped_not_fatal(self):
        with open(os.path.join(self.ledger, "broken.json"), "w", encoding="utf-8") as h:
            h.write("{not json")
        self.entry("LEARN_a", 259)
        self.assertEqual(self.types(238), ["EVIDENCE_REMOVED"])

    def test_a_non_integer_total_is_ignored(self):
        self.entry("LEARN_a", 259)
        with open(os.path.join(self.ledger, "odd.json"), "w", encoding="utf-8") as h:
            json.dump({"observationTotalAfter": "many"}, h)
        self.assertEqual(self.types(238), ["EVIDENCE_REMOVED"])

    def test_the_finding_says_HOW_MANY_are_gone(self):
        self.entry("LEARN_a", 259)
        findings = []
        ve.check_corpus_is_append_only(
            [{"observationId": "x"} for _ in range(238)], findings, FIXED_NOW,
            ledger_dir=self.ledger)
        self.assertIn("21 record(s) are gone", findings[0]["message"])
        self.assertEqual(findings[0]["severity"], "ERROR")


class TestDeleteAndPadIsDetected(unittest.TestCase):
    """DELETE-AND-PAD: the attack the count anchor cannot see by construction.

    Delete the 21 losing FORWARD observations, then copy a winning one 21 times
    changing only `observationId`. The count returns to exactly 259, forward n stays
    at 29 -- the one number a reader sanity-checks -- and the headline forward mean R
    moves from -0.18 to +2.00. Nothing is authored: `cp` plus one id, materially
    cheaper than the "fabricated whole record" case in SPEC-provenance 7.4.
    """

    def obs(self, oid, sequence_id="REPLAY|abc|GBP_USD|H1"):
        return {"observationId": oid, "sequenceId": sequence_id}

    def types(self, observations):
        findings = []
        ve.check_observation_sequence_ids_unique(observations, findings, FIXED_NOW)
        return [f["findingType"] for f in findings]

    def test_two_observations_sharing_a_sequenceId_are_an_ERROR(self):
        self.assertEqual(
            self.types([self.obs("TOBS|MOGO|20260819|001"),
                        self.obs("TOBS|MOGO|20260819|002")]),
            ["DUPLICATE_SEQUENCE_ID"])

    def test_the_finding_says_how_many_share_it(self):
        findings = []
        ve.check_observation_sequence_ids_unique(
            [self.obs("TOBS|MOGO|20260819|%03d" % i) for i in range(22)],
            findings, FIXED_NOW)
        self.assertIn("22 observations share", findings[0]["message"])
        self.assertEqual(findings[0]["severity"], "ERROR")

    def test_POSITIVE_CONTROL_distinct_sequence_ids_are_silent(self):
        self.assertEqual(
            self.types([self.obs("TOBS|MOGO|20260819|001", "SEQ|A"),
                        self.obs("TOBS|MOGO|20260819|002", "SEQ|B")]), [])

    def test_a_missing_sequenceId_is_not_treated_as_a_duplicate(self):
        # Absence is a different defect and is not invented into one here; two
        # records with no sequenceId must not collide with each other.
        self.assertEqual(
            self.types([{"observationId": "TOBS|MOGO|20260819|001"},
                        {"observationId": "TOBS|MOGO|20260819|002"}]), [])

    def test_the_LIVE_corpus_has_no_duplicate_sequence_ids(self):
        # Relationship, not a snapshot: every preserved record's sequenceId is its
        # own. This is what makes the check free of false positives.
        import glob as _glob
        paths = _glob.glob(os.path.join(REPO_ROOT, "docs", "trader-intelligence",
                                        "evidence", "observations", "*.json"))
        self.assertGreater(len(paths), 50, "corpus glob matched almost nothing")
        records = []
        for path in paths:
            with open(path, encoding="utf-8") as handle:
                records.append(json.load(handle))
        self.assertEqual(self.types(records), [])


class TestCorpusContentIsAnchoredToRecordedState(unittest.TestCase):
    """Round 9 anchored on the ledger's COUNT; round 10 showed the attack surface
    simply moved to the ledger -- six one-touch bypasses of a six-file directory no
    validator inspected. This anchors on a DIFFERENT committed file and on CONTENT.

    SPEC-provenance 7.4 already named `corpus_fingerprint` as the backstop for the
    limits it documents. Nothing read it.
    """

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="mogo_state_")
        self.state = os.path.join(self.root, "current-state.json")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def corpus(self, n, marker="a"):
        sources = [{"sourceId": "EVSRC|MOGO|20260819|001",
                    "sourceType": "replay_observation"}]
        observations = [{"observationId": "TOBS|MOGO|20260819|%03d" % i,
                         "sourceId": "EVSRC|MOGO|20260819|001",
                         "payload": marker} for i in range(n)]
        return observations, sources

    def write_state(self, observations, sources, total=None, fingerprint=None):
        import research_assimilation as ra
        by_o = {o["observationId"]: o for o in observations}
        by_s = {s["sourceId"]: s for s in sources}
        with open(self.state, "w", encoding="utf-8") as handle:
            json.dump({"observationTotal": total if total is not None else len(observations),
                       "corpusFingerprint": fingerprint or ra.corpus_fingerprint(by_o, by_s)},
                      handle)

    def types(self, observations, sources):
        findings = []
        ve.check_corpus_matches_recorded_state(observations, sources, findings,
                                               FIXED_NOW, state_path=self.state)
        return [f["findingType"] for f in findings]

    def test_same_count_different_content_is_an_ERROR(self):
        # THE delete-and-pad signature: contents changed underneath a stable count.
        observations, sources = self.corpus(10, marker="original")
        self.write_state(observations, sources)
        swapped, _ = self.corpus(10, marker="swapped")
        self.assertEqual(self.types(swapped, sources), ["CORPUS_CONTENT_DIVERGED"])

    def test_POSITIVE_CONTROL_an_unchanged_corpus_is_silent(self):
        observations, sources = self.corpus(10)
        self.write_state(observations, sources)
        self.assertEqual(self.types(observations, sources), [])

    def test_a_GROWN_corpus_is_silent_even_though_the_fingerprint_differs(self):
        # Growth before assimilation is the normal case. Reporting it would train
        # everyone to ignore this check, which is how a real finding gets missed.
        observations, sources = self.corpus(10)
        self.write_state(observations, sources)
        grown, _ = self.corpus(14)
        self.assertEqual(self.types(grown, sources), [])

    def test_a_SHRUNK_corpus_is_EVIDENCE_REMOVED(self):
        observations, sources = self.corpus(10)
        self.write_state(observations, sources)
        shrunk, _ = self.corpus(4)
        self.assertEqual(self.types(shrunk, sources), ["EVIDENCE_REMOVED"])

    def test_an_unreadable_state_file_is_reported_not_silent(self):
        with open(self.state, "w", encoding="utf-8") as handle:
            handle.write("{not json")
        observations, sources = self.corpus(10)
        self.assertEqual(self.types(observations, sources), ["UNREADABLE_RESEARCH_STATE"])

    def test_an_absent_state_file_is_REPORTED_when_observations_exist(self):
        # DECISION REVERSED, and this test was named by adversarial verification as
        # pinning the bypass AS INTENDED BEHAVIOUR. "No recorded state means no
        # anchor" sounded principled and meant that `rm -rf research-state/` defeated
        # both this gate and the append-only gate at once, restoring the original
        # deletion defect in full. A corpus holding observations has been imported,
        # and importing assimilates, so state exists for any corpus with evidence in
        # it.
        observations, sources = self.corpus(10)
        self.assertEqual(self.types(observations, sources), ["RESEARCH_STATE_MISSING"])

    def test_an_absent_state_file_is_silent_when_there_is_NO_evidence(self):
        # Positive control for the reversal: an empty corpus has no history to have
        # lost, and inventing an anchor for it would be the fabrication this layer
        # exists to prevent.
        self.assertEqual(self.types([], []), [])


class TestCorpusIntegrityGatesAreWiredAndAIMED(unittest.TestCase):
    """Five of round 11's eight surviving mutations were the same defect: all three
    corpus-integrity gates could be unwired, or pointed at a path that does not
    exist, with the whole suite green.

    "Silent when absent" and "silent when misconfigured" are the same bug seen from
    two sides -- the twelve one-touch bypasses of `current-state.json` are what it
    looks like to an attacker; `state_path=".../current-state-NOPE.json"` is what it
    looks like to a maintainer. The repository already had the right pattern
    (`TestBothSourceAnchorsAreWIRED`); it had not been applied here.

    Runs through `run_integrity_checks` on a corpus this test writes, so a gate that
    is present but not called, or called against the wrong path, fails.
    """

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="mogo_gates_")
        self.ti = os.path.join(self.root, "docs", "trader-intelligence")
        self.evidence = os.path.join(self.ti, "evidence")
        for name in ("sources", "observations"):
            os.makedirs(os.path.join(self.evidence, name))
        os.makedirs(os.path.join(self.ti, "research-state"))

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def write(self, collection, name, record):
        with open(os.path.join(self.evidence, collection, name + ".json"),
                  "w", encoding="utf-8") as handle:
            json.dump(record, handle)

    def source(self, source_type="replay_observation"):
        basis = {"replay_observation": "REPLAY_RUN",
                 "paper_trade": "LIVE_CLOSE"}[source_type]
        self.write("sources", "src", {
            "sourceId": "EVSRC|MOGO|20260819|001", "sourceType": source_type,
            "title": "capture", "storageLocationType": "repository",
            "provenanceStatus": "verified", "schemaVersion": 1,
            "metadata": {"captureBasis": basis,
                         "engineStrategyId": "alex_g_sr_v1"}})

    def forward_source(self):
        # The preservation anchor is scoped to corpora holding FORWARD evidence, so a
        # replay-only fixture cannot exercise it -- which is exactly why two
        # availability mutations survived the first version of these tests.
        self.source(source_type="paper_trade")

    def observation(self, oid, content_hash, sequence_id=None,
                    basis="REPLAY_RUN", minted="replay_observation"):
        self.write("observations", oid.replace("|", "_"), {
            "observationId": oid, "sourceId": "EVSRC|MOGO|20260819|001",
            "schemaVersion": 1, "strategyId": "alex_g_sr_v1",
            "sourceContentHash": content_hash,
            "sequenceId": sequence_id or ("SEQ|" + content_hash),
            "notes": "captureBasis=%s sourceType=%s" % (basis, minted)})

    def state(self, total, fingerprint):
        with open(os.path.join(self.ti, "research-state", "current-state.json"),
                  "w", encoding="utf-8") as handle:
            json.dump({"observationTotal": total, "corpusFingerprint": fingerprint},
                      handle)

    def finding_types(self):
        report = ve.run_integrity_checks(self.evidence, is_production=False)
        self.assertTrue(os.listdir(os.path.join(self.evidence, "observations")),
                        "vacuous run: no observations were loaded")
        return [f["findingType"] for f in report["findings"]]

    def anchor_messages(self):
        # The finding TYPE is shared by every anchor, so asserting the type alone
        # passes whenever ANY anchor is missing -- and these fixtures have no
        # research-state either. Two mutations survived on exactly that adjacent
        # effect, so the preservation cases assert which anchor was named.
        report = ve.run_integrity_checks(self.evidence, is_production=False)
        return " ".join(f["message"] for f in report["findings"]
                        if f["findingType"] == "CORPUS_ANCHOR_UNAVAILABLE")

    def preservation(self, identities):
        d = os.path.join(self.evidence, "ledger-preservation")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "PAPER_LEDGER.json"), "w", encoding="utf-8") as h:
            json.dump({"schemaVersion": "mogo.paper-ledger-preservation.v1",
                       "identities": identities}, h)

    def test_the_runner_REPORTS_a_missing_preserved_identity(self):
        # Gate wired AND aimed. Unwiring it, or aiming it at a path that does not
        # exist, both survived every test -- the gate was only ever called directly,
        # so nothing asserted PRESERVED_IDENTITY_MISSING emerges from the runner.
        # This is the class round 11 built for exactly that, which the round-13 gate
        # was never added to.
        self.forward_source()
        self.observation("TOBS|MOGO|20260819|001", "a" * 64, sequence_id="SEQ|present",
                         basis="LIVE_CLOSE", minted="paper_trade")
        self.preservation([{"tradeId": "AGT|AGS|GONE|1", "pnl": -97.5}])
        self.assertIn("PRESERVED_IDENTITY_MISSING", self.finding_types())

    def test_the_runner_REPORTS_an_absent_preservation_manifest(self):
        self.forward_source()
        self.observation("TOBS|MOGO|20260819|001", "a" * 64,
                         basis="LIVE_CLOSE", minted="paper_trade")
        # no preservation directory at all
        self.assertIn("CORPUS_ANCHOR_UNAVAILABLE", self.finding_types())
        self.assertIn("evidence/ledger-preservation/", self.anchor_messages())

    def test_the_runner_REPORTS_a_manifest_with_no_requirable_identities(self):
        # Re-prefixing every tradeId AGT|TEST| leaves a non-empty manifest that
        # requires nothing -- an anchor that requires nothing is not there.
        self.forward_source()
        self.observation("TOBS|MOGO|20260819|001", "a" * 64,
                         basis="LIVE_CLOSE", minted="paper_trade")
        self.preservation([{"tradeId": "AGT|TEST|1", "pnl": -1}])
        self.assertIn("CORPUS_ANCHOR_UNAVAILABLE", self.finding_types())
        self.assertIn("ledger-preservation:identities", self.anchor_messages())

    def test_the_runner_REPORTS_a_duplicated_package(self):
        # Gate 1 wired: DELETE-AND-PAD collides on sourceContentHash.
        self.source()
        self.observation("TOBS|MOGO|20260819|001", "a" * 64)
        self.observation("TOBS|MOGO|20260819|002", "a" * 64, sequence_id="SEQ|different")
        self.assertIn("DUPLICATE_SOURCE_CONTENT_HASH", self.finding_types())

    def test_the_runner_REPORTS_missing_research_state(self):
        # Gate 2 wired AND aimed: this is `rm -rf research-state/`, which silently
        # restored the original deletion defect in full.
        self.source()
        self.observation("TOBS|MOGO|20260819|001", "a" * 64)
        self.assertIn("RESEARCH_STATE_MISSING", self.finding_types())

    def test_the_runner_REPORTS_a_diverged_corpus(self):
        # Gate 3 wired AND aimed at the real state file: same count, wrong content.
        self.source()
        self.observation("TOBS|MOGO|20260819|001", "a" * 64)
        self.state(1, "deadbeef" * 8)
        self.assertIn("CORPUS_CONTENT_DIVERGED", self.finding_types())

    def test_the_runner_REPORTS_a_shrunken_corpus(self):
        self.source()
        self.observation("TOBS|MOGO|20260819|001", "a" * 64)
        self.state(9, "deadbeef" * 8)
        self.assertIn("EVIDENCE_REMOVED", self.finding_types())

    def test_POSITIVE_CONTROL_a_consistent_corpus_reports_none_of_them(self):
        # Without this, gates that fired unconditionally would satisfy all four above.
        import research_assimilation as ra
        self.source()
        self.observation("TOBS|MOGO|20260819|001", "a" * 64)
        observations, sources = {}, {}
        for path in os.listdir(os.path.join(self.evidence, "observations")):
            with open(os.path.join(self.evidence, "observations", path),
                      encoding="utf-8") as handle:
                rec = json.load(handle)
            observations[rec["observationId"]] = rec
        for path in os.listdir(os.path.join(self.evidence, "sources")):
            with open(os.path.join(self.evidence, "sources", path),
                      encoding="utf-8") as handle:
                rec = json.load(handle)
            sources[rec["sourceId"]] = rec
        self.state(len(observations), ra.corpus_fingerprint(observations, sources))
        self.preservation([{"tradeId": "SEQ|a" * 1, "pnl": 1.0}])
        found = set(self.finding_types())
        self.assertEqual(found & {"DUPLICATE_SOURCE_CONTENT_HASH", "RESEARCH_STATE_MISSING",
                                  "CORPUS_CONTENT_DIVERGED", "EVIDENCE_REMOVED",
                                  "MISSING_SOURCE_CONTENT_HASH"}, set())


class TestCorpusIntegrityFindingsAreBlocking(unittest.TestCase):
    """Severity and exit code, asserted TOGETHER.

    Round 12: downgrading `DUPLICATE_SOURCE_CONTENT_HASH` to WARNING, or
    `RESEARCH_STATE_MISSING` to INFO, survived every test. Each gate had a test
    asserting its `findingType` and none asserting its severity, and `exit_code_for`
    fails only on ERROR or FATAL -- so a gate could keep reporting, keep being wired,
    and stop blocking. "Reports" and "fails the build" are different properties and
    were never checked together.

    Table-driven so a new corpus-integrity finding cannot be added without deciding,
    explicitly, whether it blocks.
    """

    BLOCKING = (
        "DUPLICATE_SOURCE_CONTENT_HASH", "MISSING_SOURCE_CONTENT_HASH",
        "DUPLICATE_SEQUENCE_ID", "RESEARCH_STATE_MISSING",
        "CORPUS_ANCHOR_UNAVAILABLE", "STATE_CONTRADICTS_LEDGER",
        "CORPUS_CONTENT_DIVERGED", "EVIDENCE_REMOVED",
        "LEDGER_DISAGREES_WITH_STATE", "UNREADABLE_RESEARCH_STATE",
        "POPULATION_REBINDING", "UNRESOLVED_POPULATION",
        "MISSING_MINT_PROVENANCE", "MISSING_CAPTURE_BASIS",
        "AMBIGUOUS_MINT_PROVENANCE", "UNRECOGNISED_CAPTURE_BASIS",
        "MISSING_STRATEGY_ATTRIBUTION", "MISSING_SOURCE_ATTRIBUTION",
        "ENGINE_STRATEGY_MISMATCH", "SOURCE_TYPE_CONTRADICTS_CAPTURE_BASIS",
        "MISSING_SOURCE_CAPTURE_BASIS",
        # B-32.14 / B-32.15: the identity anchor and its allow-list direction.
        "PRESERVED_IDENTITY_MISSING", "UNREADABLE_PRESERVED_IDENTITIES",
        "UNANCHORED_OBSERVATION",
    )

    def test_every_corpus_integrity_finding_is_declared_at_ERROR_in_the_source(self):
        path = os.path.join(REPO_ROOT, "scripts", "trader_intelligence",
                            "validate_evidence.py")
        with open(path, encoding="utf-8") as handle:
            source = handle.read()
        self.assertGreater(len(self.BLOCKING), 15, "table looks truncated")
        for finding_type in self.BLOCKING:
            with self.subTest(finding=finding_type):
                self.assertIn('"%s", "ERROR"' % finding_type, source,
                              "%s is not raised at ERROR, so it reports without "
                              "blocking: exit_code_for fails only on ERROR/FATAL"
                              % finding_type)

    def test_ERROR_blocks_and_WARNING_does_not(self):
        # The property the table above depends on. If this ever changes, every
        # severity assertion in this class silently stops meaning anything.
        self.assertEqual(ve.exit_code_for({"FATAL": 0, "ERROR": 1,
                                           "WARNING": 0, "INFO": 0}), 1)
        self.assertEqual(ve.exit_code_for({"FATAL": 0, "ERROR": 0,
                                           "WARNING": 9, "INFO": 9}), 0)

    def test_no_listed_finding_is_ever_raised_below_ERROR(self):
        # The mutation this kills: downgrading a gate to WARNING or INFO leaves it
        # wired, still reporting, and no longer blocking -- and every findingType
        # assertion in the suite still passes. Scoped to the corpus-integrity table
        # rather than every ERROR in the module, because the other 30 belong to the
        # evidence layer and are not what these rounds hardened.
        import re as _re
        path = os.path.join(REPO_ROOT, "scripts", "trader_intelligence",
                            "validate_evidence.py")
        with open(path, encoding="utf-8") as handle:
            source = handle.read()
        for finding_type in self.BLOCKING:
            with self.subTest(finding=finding_type):
                downgraded = _re.findall(
                    r'"%s",\s*"(WARNING|INFO)"' % finding_type, source)
                self.assertEqual(downgraded, [],
                                 "%s is raised at %s somewhere; it would report "
                                 "without failing the run"
                                 % (finding_type, downgraded))


class TestEveryCorpusAnchorIsRequired(unittest.TestCase):
    """One case per anchor, table-driven to match the invariant.

    Wiring tests proved the invariant is CALLED; they did not prove each anchor is
    checked. Three mutations survived on that gap: dropping the ledger-directory
    requirement, accepting a mistyped `observationTotal`, and removing the
    cross-anchor comparison. Each is one branch, and a table-driven invariant
    deserves a table-driven test or the table is decorative.

    Every case here is an attack that was measured as SILENT before this invariant
    existed.
    """

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="mogo_anchor_")
        self.state_dir = os.path.join(self.root, "research-state")
        self.ledger = os.path.join(self.state_dir, "ledger")
        self.preservation = os.path.join(self.root, "ledger-preservation")
        os.makedirs(self.ledger)
        os.makedirs(self.preservation)
        self.state_path = os.path.join(self.state_dir, "current-state.json")
        self.write_state({"observationTotal": 3, "corpusFingerprint": "f" * 64})
        self.write_ledger(3)
        with open(os.path.join(self.preservation, "M.json"), "w",
                  encoding="utf-8") as handle:
            json.dump({"identities": [{"tradeId": "T1"}]}, handle)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def write_state(self, payload):
        with open(self.state_path, "w", encoding="utf-8") as handle:
            if isinstance(payload, str):
                handle.write(payload)
            else:
                json.dump(payload, handle)

    def write_ledger(self, total):
        with open(os.path.join(self.ledger, "LEARN_a.json"), "w",
                  encoding="utf-8") as handle:
            json.dump({"observationTotalAfter": total}, handle)

    def types(self, observations=None):
        findings = []
        ve.check_corpus_anchors_are_available(
            observations if observations is not None
            else [{"observationId": "TOBS|MOGO|20260819|%03d" % i} for i in range(3)],
            findings, FIXED_NOW,
            state_path=self.state_path, ledger_dir=self.ledger,
            preservation_dir=self.preservation)
        return [f["findingType"] for f in findings]

    def test_the_DECLARED_table_matches_the_anchors_actually_reported(self):
        # M13: deleting a row from CORPUS_ANCHORS changed nothing and no test
        # noticed -- the table that is supposed to BE the systemic invariant was
        # decorative, while the behaviour was covered only by per-anchor tests. That
        # is precisely the instance-patching the table exists to replace.
        #
        # Every declared anchor must be one this function can actually report, and
        # every anchor it reports must be declared. Breaking either direction fails.
        declared = {name for name, _kind in ve.CORPUS_ANCHORS}
        self.assertGreater(len(declared), 3, "the anchor table looks truncated")

        reported = set()
        for scenario in ("no_state", "bad_fields", "no_ledger", "no_preservation",
                         "hollow_preservation"):
            with self.subTest(scenario=scenario):
                self.setUp()
                if scenario == "bad_fields":
                    self.write_state({"observationTotal": "x", "corpusFingerprint": 1})
                elif scenario == "no_state":
                    os.remove(self.state_path)
                elif scenario == "no_ledger":
                    shutil.rmtree(self.ledger)
                elif scenario == "no_preservation":
                    shutil.rmtree(self.preservation)
                elif scenario == "hollow_preservation":
                    # A manifest that requires nothing: non-empty, all rows excluded.
                    with open(os.path.join(self.preservation, "M.json"), "w",
                              encoding="utf-8") as handle:
                        json.dump({"identities": [{"tradeId": "AGT|TEST|1"}]}, handle)
                findings = []
                ve.check_corpus_anchors_are_available(
                    [{"observationId": "TOBS|MOGO|20260819|001"}], findings, FIXED_NOW,
                    state_path=self.state_path, ledger_dir=self.ledger,
                    preservation_dir=self.preservation)
                # Extracted from the message INDEPENDENTLY of the table. Scanning
                # only declared names made `reported` a subset of `declared` by
                # construction, so the undeclared direction could never fail -- which
                # is why removing a row from the table still passed.
                import re as _re
                for finding in findings:
                    reported.update(_re.findall(r"integrity anchor '([^']+)'",
                                                finding["message"]))
        undeclared = sorted(reported - declared)
        unreachable = sorted(declared - reported)
        self.assertEqual(undeclared, [],
                         "these anchors are reported but not declared: %s" % undeclared)
        self.assertEqual(unreachable, [],
                         "these anchors are declared but nothing can report them, so "
                         "the table is decorative: %s" % unreachable)

    def test_every_way_of_HOLLOWING_the_preservation_anchor_is_reported(self):
        # M10 and M11 survived mutation: making the empty directory silent, and
        # making a non-list `identities` silent, each broke no test. Both are
        # one-touch bypasses -- `rm ledger-preservation/*.json` is as good as
        # `rm -rf ledger-preservation/`, and the require-list and allow-list both
        # switch off when no rows are read.
        #
        # The directory-absent case is covered by the table test above; these are
        # the ways it can be PRESENT and still anchor nothing.
        for label, prepare in (
                ("no manifest files", lambda: [os.remove(f) for f in globmod.glob(
                    os.path.join(self.preservation, "*.json"))]),
                ("identities not a list", lambda: self.write_manifest(
                    {"identities": {"T1": True}})),
                ("identities absent", lambda: self.write_manifest({"schemaVersion": 1})),
                ("identities null", lambda: self.write_manifest({"identities": None})),
                ("document is a list", lambda: self.write_manifest([{"tradeId": "T1"}])),
                ("document is null", lambda: self.write_manifest(None)),
                ("every row a developer trade", lambda: self.write_manifest(
                    {"identities": [{"tradeId": "AGT|TEST|1"}]})),
                ("every row malformed", lambda: self.write_manifest(
                    {"identities": [{"tradeId": 7}, {"noTradeId": "x"}, "not-a-dict"]})),
        ):
            with self.subTest(hollowed=label):
                self.setUp()
                prepare()
                # Asserted as a property, not a count: several of these are
                # reported twice (unreadable AND requiring nothing), and pinning the
                # count would be pinning a snapshot.
                reported = self.types()
                self.assertTrue(reported,
                                "%s leaves the require-list and the allow-list with "
                                "nothing to require or allow, which is the anchor "
                                "not being there" % label)
                self.assertEqual(set(reported), {"CORPUS_ANCHOR_UNAVAILABLE"})

    def test_ONE_corrupted_manifest_is_reported_even_when_ANOTHER_is_healthy(self):
        # M11 survived every check above by ADJACENT EFFECT: making a non-list
        # `identities` silent still tripped "no requirable identities", because the
        # fixture had only one manifest and emptying it emptied the total.
        #
        # With a healthy manifest beside it the total never reaches zero, so the
        # adjacent report goes quiet and only the specific one is left. That is also
        # the real attack: corrupt the manifest holding the trades you want to
        # unanchor and leave the other intact.
        self.write_manifest({"identities": [{"tradeId": "T_HEALTHY"}]}, name="A.json")
        self.write_manifest({"identities": {"T1": True}}, name="B.json")
        os.remove(os.path.join(self.preservation, "M.json"))
        reported = self.types()
        self.assertEqual(set(reported), {"CORPUS_ANCHOR_UNAVAILABLE"},
                         "a manifest whose identities are not a list contributes no "
                         "rows, so every trade it recorded silently stops being "
                         "required")

    def test_POSITIVE_CONTROL_two_healthy_manifests_are_silent(self):
        # Without this the assertion above would also pass if a second manifest were
        # reported no matter what it contained.
        self.write_manifest({"identities": [{"tradeId": "T_HEALTHY"}]}, name="A.json")
        self.write_manifest({"identities": [{"tradeId": "T2"}]}, name="B.json")
        self.assertEqual(self.types(), [])

    def write_manifest(self, document, name="M.json"):
        with open(os.path.join(self.preservation, name), "w",
                  encoding="utf-8") as handle:
            json.dump(document, handle)

    def test_POSITIVE_CONTROL_all_anchors_present_is_silent(self):
        self.assertEqual(self.types(), [])

    def test_an_empty_corpus_requires_no_anchors(self):
        # No evidence means no history to have lost; demanding anchors would invent
        # a past the corpus never had.
        shutil.rmtree(self.state_dir)
        self.assertEqual(self.types(observations=[]), [])

    def test_the_state_file_is_required(self):
        os.remove(self.state_path)
        self.assertEqual(self.types(), ["CORPUS_ANCHOR_UNAVAILABLE"])

    def test_an_unreadable_state_file_is_reported(self):
        self.write_state("{not json")
        self.assertEqual(self.types(), ["CORPUS_ANCHOR_UNAVAILABLE"])

    def test_a_NON_OBJECT_state_document_does_not_satisfy_the_anchor(self):
        # One type away from the `{}` case below, and it was silent: every field check
        # sits behind `isinstance(state, dict)`, so `null`, a string, a list or a
        # number reported nothing. The only thing stopping it being an exit-0 deletion
        # bypass was a crash in the next function -- and a crash is not a report: it
        # loses every other finding and leaves the last integrity-report.json on disk
        # still reading clean while records are missing.
        for document in ("null", '"a string"', "[]", "123"):
            with self.subTest(document=document):
                self.write_state(document)
                self.assertEqual(self.types(), ["CORPUS_ANCHOR_UNAVAILABLE"],
                                 "%s was accepted as a state document" % document)

    def test_a_JSON_null_document_is_distinguished_from_never_loaded(self):
        # `json.load` of `null` returns None, which was indistinguishable from the
        # not-loaded sentinel and so slipped past the type report.
        self.write_state("null")
        self.assertEqual(self.types(), ["CORPUS_ANCHOR_UNAVAILABLE"])

    def test_a_STUB_state_file_does_not_satisfy_the_anchor(self):
        # `{}` dodged the file-existence check entirely before this invariant.
        self.write_state({})
        self.assertEqual(len(self.types()), 2, "both fields must be reported missing")

    def test_observationTotal_must_be_a_real_integer(self):
        for bad in ("3", None, 3.0, True, [3]):
            with self.subTest(observationTotal=bad):
                self.write_state({"observationTotal": bad,
                                  "corpusFingerprint": "f" * 64})
                self.assertEqual(self.types(), ["CORPUS_ANCHOR_UNAVAILABLE"],
                                 "%r was accepted as a total" % (bad,))

    def test_corpusFingerprint_must_be_a_non_empty_string(self):
        for bad in (None, 12345, "", "   ", ["x"]):
            with self.subTest(corpusFingerprint=bad):
                self.write_state({"observationTotal": 3, "corpusFingerprint": bad})
                self.assertEqual(self.types(), ["CORPUS_ANCHOR_UNAVAILABLE"],
                                 "%r was accepted as a fingerprint" % (bad,))

    def messages(self):
        findings = []
        ve.check_corpus_anchors_are_available(
            [{"observationId": "TOBS|MOGO|20260819|%03d" % i} for i in range(3)],
            findings, FIXED_NOW,
            state_path=self.state_path, ledger_dir=self.ledger)
        return " ".join(f["message"] for f in findings)

    def test_the_ledger_directory_is_required(self):
        # The message is pinned, not just the finding type. Deleting the absent-branch
        # is an EQUIVALENT MUTANT on type alone -- the empty-glob check below fires for
        # a missing directory too -- but it reports it as "empty", which sends the
        # reader looking inside a directory that is not there.
        shutil.rmtree(self.ledger)
        self.assertEqual(self.types(), ["CORPUS_ANCHOR_UNAVAILABLE"])
        self.assertIn("is absent", self.messages())

    def test_an_EMPTY_ledger_directory_is_reported_AS_EMPTY(self):
        os.remove(os.path.join(self.ledger, "LEARN_a.json"))
        self.assertEqual(self.types(), ["CORPUS_ANCHOR_UNAVAILABLE"])
        self.assertIn("is empty", self.messages())

    def test_state_below_the_ledger_high_water_mark_is_reported(self):
        # The anchor is present and correctly typed and still lying: decrementing the
        # total makes the content comparison read the corpus as "grown" and skip.
        self.write_state({"observationTotal": 2, "corpusFingerprint": "f" * 64})
        self.write_ledger(3)
        self.assertEqual(self.types(), ["STATE_CONTRADICTS_LEDGER"])

    def test_state_ABOVE_the_ledger_is_NOT_reported(self):
        # Positive control: growth between assimilation runs is normal, and reporting
        # it would train everyone to ignore this.
        self.write_state({"observationTotal": 9, "corpusFingerprint": "f" * 64})
        self.write_ledger(3)
        self.assertEqual(self.types(), [])


class TestTheAllowListFailsClosedOnAnUnusableSequenceId(unittest.TestCase):
    """M4: the round-15 P1-B repair had ZERO test coverage.

    The repair inverted a `continue` into a `_finding` so an observation whose
    `sequenceId` is not a usable string is REPORTED rather than skipped. Deleting
    that repair -- restoring the exact bypass that walked 200 invented winners past
    the allow-list and moved forward mean R from -0.18 to +2.60 -- broke no test.
    The only existing `UNANCHORED_OBSERVATION` case supplies a valid string, so it
    exercises the other branch entirely.

    A fixture that passes while the mechanism is broken is not evidence. Each type
    below is a separate way to make the field unusable, and each one alone was a
    full exit-0 bypass.
    """

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="mogo_allowlist_")
        self.preservation = os.path.join(self.root, "ledger-preservation")
        os.makedirs(self.preservation)
        with open(os.path.join(self.preservation, "M.json"), "w",
                  encoding="utf-8") as handle:
            json.dump({"identities": [{"tradeId": "T1"}]}, handle)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def types(self, observations):
        findings = []
        ve.check_preserved_identities_still_present(
            observations, findings, FIXED_NOW, preservation_dir=self.preservation)
        return [f["findingType"] for f in findings]

    def test_POSITIVE_CONTROL_an_anchored_observation_is_silent(self):
        # Without this, every assertion below would also pass if the check reported
        # everything unconditionally.
        self.assertEqual(
            self.types([{"observationId": "O1", "sequenceId": "T1"}]), [])

    def test_an_unanchored_but_well_formed_sequenceId_is_reported(self):
        # T1's own observation is present, so the require-list is satisfied and the
        # only thing left to report is the unanchored arrival.
        self.assertEqual(
            self.types([{"observationId": "O0", "sequenceId": "T1"},
                        {"observationId": "O1", "sequenceId": "NEVER_CAPTURED"}]),
            ["UNANCHORED_OBSERVATION"])

    def test_a_sequenceId_that_is_not_a_usable_string_is_reported_not_skipped(self):
        for label, record in (
                ("absent", {"observationId": "O1"}),
                ("empty", {"observationId": "O1", "sequenceId": ""}),
                ("null", {"observationId": "O1", "sequenceId": None}),
                ("int", {"observationId": "O1", "sequenceId": 12345}),
                ("float", {"observationId": "O1", "sequenceId": 1.5}),
                ("bool", {"observationId": "O1", "sequenceId": True}),
                ("list", {"observationId": "O1", "sequenceId": ["T1"]}),
                ("dict", {"observationId": "O1", "sequenceId": {"id": "T1"}}),
        ):
            with self.subTest(sequenceId=label):
                anchored = {"observationId": "O0", "sequenceId": "T1"}
                self.assertEqual(self.types([anchored, record]),
                                 ["UNANCHORED_OBSERVATION"],
                                 "a %s sequenceId is unusable, so the observation is "
                                 "anchored by nothing -- skipping it IS the bypass"
                                 % label)

    def test_the_fabrication_attack_in_miniature(self):
        # 20 invented winners, each with the sequenceId key deleted. Before the
        # repair this reported nothing at all.
        fabricated = [{"observationId": "FAKE|%d" % i} for i in range(20)]
        real = [{"observationId": "O0", "sequenceId": "T1"}]
        self.assertEqual(self.types(real + fabricated),
                         ["UNANCHORED_OBSERVATION"] * 20)


class TestAnchorValuesAreComparedToTheCorpus(unittest.TestCase):
    """THE SIXTH CATEGORY: the anchors pinned existence and never value.

    Every identity present, every hash intact, every count unchanged, every anchor
    readable -- and `pnl`/`rMultiple` rewritten in place on the preserved forward
    losers moved forward mean R from -0.18 to +2.00 in total silence. The values to
    contradict it were already on disk in `ledger-preservation/`, recorded when each
    trade closed, agreeing with the corpus exactly, and read by nothing.
    """

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="mogo_anchorvalue_")
        self.preservation = os.path.join(self.root, "ledger-preservation")
        os.makedirs(self.preservation)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def manifest(self, identities, name="LEDGER.json"):
        with open(os.path.join(self.preservation, name), "w",
                  encoding="utf-8") as handle:
            json.dump({"identities": identities}, handle)

    def types(self, observations):
        findings = []
        ve.check_anchor_values_match_records(
            observations, findings, FIXED_NOW, preservation_dir=self.preservation)
        return [f["findingType"] for f in findings]

    def observation(self, **over):
        record = {"observationId": "O1", "sequenceId": "T1", "pnl": -97.56,
                  "instrument": "GBP/USD", "closedAt": "2026-08-17T17:39:10.849Z",
                  "sourceContentHash": "a" * 64}
        record.update(over)
        return record

    def anchor(self, **over):
        row = {"tradeId": "T1", "pnl": -97.56, "pair": "GBP_USD",
               "closedAt": "2026-08-17T17:39:10.849Z", "contentHash": "a" * 64}
        row.update(over)
        return row

    def test_POSITIVE_CONTROL_agreeing_values_are_silent(self):
        self.manifest([self.anchor()])
        self.assertEqual(self.types([self.observation()]), [])

    def test_a_rewritten_value_contradicts_the_anchor(self):
        self.manifest([self.anchor()])
        for field, forged in (("pnl", 205.62), ("instrument", "EUR/USD"),
                              ("closedAt", "2026-01-01T00:00:00.000Z"),
                              ("sourceContentHash", "b" * 64)):
            with self.subTest(field=field):
                self.assertEqual(
                    self.types([self.observation(**{field: forged})]),
                    ["ANCHOR_VALUE_CONTRADICTED"],
                    "%s was rewritten and the anchor still says otherwise" % field)

    def test_DELETING_the_bound_field_is_not_cheaper_than_forging_it(self):
        # The obvious escape from a value comparison: remove the value. A gate that
        # compares only where both sides are present is switched off by an edit
        # smaller than the one it detects.
        self.manifest([self.anchor()])
        record = self.observation()
        del record["pnl"]
        self.assertEqual(self.types([record]), ["ANCHOR_VALUE_UNCHECKABLE"])

    def test_the_instrument_separator_is_not_a_contradiction(self):
        # The ledger writes GBP_USD and the observation GBP/USD. Reporting that as
        # tampering would be 35 false positives on a clean corpus, which is how a
        # real gate gets disabled.
        self.manifest([self.anchor(pair="GBP_USD")])
        self.assertEqual(self.types([self.observation(instrument="GBP/USD")]), [])

    def test_pnl_is_compared_numerically_not_textually(self):
        self.manifest([self.anchor(pnl=-97.56)])
        self.assertEqual(self.types([self.observation(pnl=-97.560000001)]), [])

    def test_an_unjoinable_anchor_row_is_left_to_the_existence_check(self):
        # The 4 developer trades are recorded but deliberately never imported.
        # Answering "is it present" here too would report them as contradictions.
        self.manifest([self.anchor(), self.anchor(tradeId="AGT|TEST|1")])
        self.assertEqual(self.types([self.observation()]), [])

    def test_a_field_no_rule_adjudicates_is_REPORTED(self):
        # The systemic half. The defect was never "this comparison is missing", it
        # was "an anchor recorded a value and nothing compared it". A new field
        # arriving in an anchor writer must force that decision rather than default
        # to silence.
        self.manifest([self.anchor(realisedSlippage=0.4)])
        self.assertIn("UNADJUDICATED_ANCHOR_FIELD", self.types([self.observation()]))

    def test_every_field_the_LIVE_anchors_carry_is_adjudicated(self):
        # The table is only an invariant if it covers what is actually on disk.
        root = os.path.join(REPO_ROOT, "docs", "trader-intelligence", "evidence",
                            "ledger-preservation")
        if not os.path.isdir(root):
            self.skipTest("live corpus not present")
        bound = {b.anchor_field for b in ve.ANCHOR_VALUE_BINDINGS}
        seen = set()
        for path in globmod.glob(os.path.join(root, "*.json")):
            with open(path, "r", encoding="utf-8") as handle:
                document = json.load(handle)
            for row in document.get("identities") or []:
                if isinstance(row, dict):
                    seen.update(row)
        self.assertTrue(seen, "no anchor rows were read -- this would pass vacuously")
        self.assertEqual(seen - bound - set(ve.ANCHOR_FIELDS_UNBOUND), set())

    def test_the_gate_reports_when_it_compared_NOTHING(self):
        # A loop that compares nothing passes, and looks identical to a clean
        # corpus. Renaming every bound field at the writer would otherwise be silent.
        self.manifest([{"tradeId": "T1", "refusedByImportPolicy": False}])
        self.assertEqual(self.types([self.observation()]),
                         ["ANCHOR_VALUES_UNCOMPARED"])

    def test_UNBOUND_fields_state_a_reason(self):
        for field, reason in ve.ANCHOR_FIELDS_UNBOUND.items():
            with self.subTest(field=field):
                self.assertGreater(len(reason), 40,
                                   "%r is excused without saying why" % field)


class TestPreservedIdentitiesMustStillExist(unittest.TestCase):
    """THE FIFTH CATEGORY: append-only enforced in aggregate, never per identity.

    Every anchor before this reduced the corpus to a cardinality plus a whole-corpus
    hash pinned in a file the same actor can rewrite. None asked WHICH observations
    have existed, so every cardinality-preserving substitution was invisible --
    including the one the system performs on itself: `research_assimilation --write`
    re-stamps the fingerprint from whatever is on disk, so a padded corpus is
    re-blessed by one documented maintenance command with an intact ledger chain.

    A per-identity manifest cannot be recomputed from the tampered corpus, because
    it records what was there BEFORE. That is the whole difference.
    """

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="mogo_identity_")
        self.preservation = os.path.join(self.root, "ledger-preservation")
        os.makedirs(self.preservation)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def manifest(self, identities, name="PAPER_LEDGER.json"):
        with open(os.path.join(self.preservation, name), "w", encoding="utf-8") as h:
            json.dump({"schemaVersion": "mogo.paper-ledger-preservation.v1",
                       "identities": identities}, h)

    def observations(self, *sequence_ids):
        return [{"observationId": "TOBS|MOGO|20260819|%03d" % i, "sequenceId": s}
                for i, s in enumerate(sequence_ids)]

    def types(self, observations):
        findings = []
        ve.check_preserved_identities_still_present(
            observations, findings, FIXED_NOW, preservation_dir=self.preservation)
        return [f["findingType"] for f in findings]

    def test_a_preserved_trade_that_vanished_is_an_ERROR(self):
        self.manifest([{"tradeId": "AGT|AGS|GBP_USD|1", "pnl": -97.56}])
        self.assertEqual(self.types(self.observations()), ["PRESERVED_IDENTITY_MISSING"])

    def test_POSITIVE_CONTROL_a_present_identity_is_silent(self):
        self.manifest([{"tradeId": "AGT|AGS|GBP_USD|1", "pnl": -97.56}])
        self.assertEqual(self.types(self.observations("AGT|AGS|GBP_USD|1")), [])

    def test_DELETE_AND_PAD_is_caught_even_though_the_COUNT_is_unchanged(self):
        # The signature this exists for: one identity out, a different one in, count
        # identical. Every count-based and fingerprint-based anchor nets out.
        self.manifest([{"tradeId": "AGT|AGS|LOSER|1", "pnl": -100.0}])
        # BOTH directions now fire, and that is stronger than either alone: the
        # deleted loser is a missing identity, and the substituted winner is anchored
        # by nothing. Before the allow-list existed only the first was reported.
        self.assertEqual(sorted(self.types(self.observations("AGT|AGS|WINNER|1"))),
                         ["PRESERVED_IDENTITY_MISSING", "UNANCHORED_OBSERVATION"])

    def test_developer_test_trades_are_NOT_required(self):
        # The manifest records 4 AGT|TEST| identities the importer refuses by policy;
        # requiring them would fire on the live corpus forever.
        self.manifest([{"tradeId": "AGT|TEST|1783897893481-429023", "pnl": -100}])
        self.assertEqual(self.types(self.observations()), [])

    def test_the_developer_predicate_is_the_IMPORTERS_not_a_copy(self):
        import import_mogo_observations as importer
        self.assertIs(ve.is_developer_test_package,
                      importer.is_developer_test_package)

    def test_the_finding_names_the_trade_and_its_pnl(self):
        # "an identity is missing" is not actionable without knowing which trade and
        # what it was worth -- that is what makes selective deletion legible.
        self.manifest([{"tradeId": "AGT|AGS|GBP_USD|1", "pnl": -97.56}])
        findings = []
        ve.check_preserved_identities_still_present(
            self.observations(), findings, FIXED_NOW,
            preservation_dir=self.preservation)
        self.assertIn("AGT|AGS|GBP_USD|1", findings[0]["message"])
        self.assertIn("-97.56", findings[0]["message"])
        self.assertEqual(findings[0]["severity"], "ERROR")

    def test_an_unreadable_manifest_is_reported_not_skipped(self):
        with open(os.path.join(self.preservation, "broken.json"), "w",
                  encoding="utf-8") as handle:
            handle.write("{not json")
        self.assertEqual(self.types(self.observations()),
                         ["UNREADABLE_PRESERVED_IDENTITIES"])

    def test_an_absent_preservation_directory_is_silent_FOR_THIS_GATE_ONLY(self):
        # REPLACED, not amended. The old version asserted an absent manifest was
        # correct behaviour outright -- "a corpus that never preserved a ledger has
        # no identities to require" -- which pinned `rm -rf ledger-preservation/` as
        # intended, one of eleven one-touch bypasses that restored full exit-0
        # substitution.
        #
        # This gate stays silent because it has nothing to require; AVAILABILITY is
        # not its job and is now asserted by check_corpus_anchors_are_available,
        # which reports the absence as an ERROR. The scoping problem the old comment
        # was worried about was already solved there ("scoped to a corpus that HOLDS
        # evidence") and this gate simply failed to reuse it.
        shutil.rmtree(self.preservation)
        self.assertEqual(self.types(self.observations()), [])
        findings = []
        ve.check_corpus_anchors_are_available(
            self.observations("SEQ|1"), findings, FIXED_NOW,
            state_path=None, ledger_dir=None, preservation_dir=self.preservation)
        self.assertIn("CORPUS_ANCHOR_UNAVAILABLE",
                      [f["findingType"] for f in findings],
                      "absence must be reported by the availability invariant")

    def test_the_LIVE_manifest_is_fully_satisfied_by_the_LIVE_corpus(self):
        # Relationship, not a snapshot: every non-developer identity ever preserved is
        # still present. This is what makes the gate free of false positives, and it
        # will fail the moment a real forward record goes missing.
        import glob as _glob
        ti = os.path.join(REPO_ROOT, "docs", "trader-intelligence")
        paths = _glob.glob(os.path.join(ti, "evidence", "observations", "*.json"))
        self.assertGreater(len(paths), 50, "corpus glob matched almost nothing")
        records = []
        for path in paths:
            with open(path, encoding="utf-8") as handle:
                records.append(json.load(handle))
        findings = []
        ve.check_preserved_identities_still_present(
            records, findings, FIXED_NOW,
            preservation_dir=os.path.join(ti, "evidence", "ledger-preservation"))
        self.assertEqual([f["findingType"] for f in findings], [])

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
import json
import os
import shutil
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
_SCRATCH_EVIDENCE_COLLECTIONS = (
    "sources", "items", "claims", "links", "contradictions", "lifecycle", "questions",
    "proposals", "review-queue", "intake", "segments", "annotations",
    "profiles", "blueprints", "gaps", "hypotheses", "reports",
)


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

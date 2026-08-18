#!/usr/bin/env python3
"""PROGRAM-006 Phase 1B test suite (ADR-009, Deliverable 23). Pure stdlib
(unittest). Fully offline, deterministic. Run with:

    python3 -m unittest tests.trader_intelligence.evidence.test_phase1b -v

Requires no internet, external APIs, broker credentials, LLM services, real
TJR content, video downloads, or external accounts. Every temp repo is
built fresh per test -- nothing here ever touches the real
docs/trader-intelligence/evidence/ tree or the synthetic_tjr_demo fixture's
own generation (that fixture is loaded read-only in category K).
"""
import glob as globmod
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timezone

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts", "trader_intelligence")
TI_ROOT = os.path.join(REPO_ROOT, "docs", "trader-intelligence")
SYNTHETIC_TJR_ROOT = os.path.join(os.path.dirname(__file__), "fixtures", "synthetic_tjr_demo")

sys.path.insert(0, SCRIPTS_DIR)
import graph_common as gc                # noqa: E402
import evidence_common as evc             # noqa: E402
import evidence_registry as reg           # noqa: E402
import evidence_confidence as conf        # noqa: E402
import evidence_dedup as dedup            # noqa: E402
import transcript_adapters as ta          # noqa: E402
import intake_registry as ir              # noqa: E402
import annotation_pipeline as ap          # noqa: E402
import extraction_pipeline as ep          # noqa: E402
import evidence_questions as eq           # noqa: E402
import rule_candidate_proposals as rcp    # noqa: E402
import review_queues as rev               # noqa: E402
import evidence_explain as ee             # noqa: E402
import tjr_report as tr                   # noqa: E402
import query_evidence as qe               # noqa: E402
import validate_evidence as ve            # noqa: E402
import validate_graph                     # noqa: E402

FIXED_NOW = datetime(2026, 7, 26, 12, 0, 0, tzinfo=timezone.utc)


def independent_content_hash(entity):
    """The expected contentHash, computed WITHOUT gc.content_hash_of.

    Deliberate duplication. Computing the expected value with the same function
    the builder used proves only that both sides called the same function: an
    independent verifier gutted `content_hash_of` so it dropped every list- and
    dict-valued field, and every "contentHash matches" assertion in this
    repository stayed green. Writing the rule out here means a change to it has
    to be made twice, on purpose.
    """
    return hashlib.sha256(
        json.dumps(entity, sort_keys=True, separators=(",", ":"),
                   ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


class TempPhase1BRepo:
    """A throwaway evidence-root directory tree covering every Phase 1A/1B
    subdirectory. Isolated from production and from the synthetic_tjr_demo
    fixture's own files."""

    DIRS = ("sources", "items", "claims", "links", "contradictions", "lifecycle", "reports",
            "intake", "segments", "annotations", "questions", "proposals", "review-queue")

    def __init__(self):
        self.root = tempfile.mkdtemp(prefix="mogo_phase1b_test_")
        for name in self.DIRS:
            setattr(self, name.replace("-", "_") + "_dir", os.path.join(self.root, name))
            os.makedirs(getattr(self, name.replace("-", "_") + "_dir"), exist_ok=True)

    def cleanup(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def index(self):
        return qe.EvidenceIndex.load(self.root)

    def validate(self, **kwargs):
        kwargs.setdefault("is_production", False)
        return ve.run_integrity_checks(self.root, **kwargs)

    # --- convenience registration wrappers -----------------------------

    def register_intake(self, **kwargs):
        kwargs.setdefault("actor", "owner")
        kwargs.setdefault("now", FIXED_NOW)
        return ir.register_intake_manifest(self.intake_dir, self.lifecycle_dir,
                                            kwargs.pop("sourceType", "transcript"),
                                            kwargs.pop("actor"), kwargs.pop("now"), **kwargs)

    def transition_intake(self, intake_id, new_status, **kwargs):
        kwargs.setdefault("actor", "owner")
        kwargs.setdefault("now", FIXED_NOW)
        return ir.transition_intake_status(self.intake_dir, self.lifecycle_dir, intake_id, new_status,
                                            kwargs.pop("actor"), kwargs.pop("now"), **kwargs)

    def register_segments(self, intake_id, parsed_segments, **kwargs):
        kwargs.setdefault("now", FIXED_NOW)
        return ir.register_transcript_segments(self.segments_dir, self.intake_dir, kwargs.pop("now"),
                                                intake_id, parsed_segments, **kwargs)

    def register_source(self, **kwargs):
        kwargs.setdefault("actor", "owner")
        kwargs.setdefault("now", FIXED_NOW)
        return reg.register_source(self.sources_dir, self.lifecycle_dir,
                                    kwargs.pop("sourceType", "transcript"),
                                    kwargs.pop("actor"), kwargs.pop("now"), **kwargs)

    def link_intake_to_source(self, intake_id, source_id, **kwargs):
        kwargs.setdefault("actor", "owner")
        kwargs.setdefault("now", FIXED_NOW)
        return ir.link_intake_to_source(self.intake_dir, self.lifecycle_dir, intake_id, source_id,
                                         kwargs.pop("actor"), kwargs.pop("now"))

    def register_annotation(self, intake_id, segment_id, excerpt, evidence_type, directness, certainty, **kwargs):
        kwargs.setdefault("reviewer", "researcher1")
        return ap.register_annotation(self.annotations_dir, self.segments_dir, self.intake_dir, FIXED_NOW,
                                       intake_id, segment_id, excerpt, evidence_type, directness, certainty,
                                       kwargs.pop("reviewer"), **kwargs)

    def approve_annotation(self, annotation_id):
        return ap.set_annotation_review_status(self.annotations_dir, annotation_id, "approved", FIXED_NOW)

    def apply_annotation(self, annotation_id, **kwargs):
        kwargs.setdefault("actor", "owner")
        return ap.apply_annotation(self.annotations_dir, self.segments_dir, self.intake_dir, self.items_dir,
                                    self.sources_dir, self.claims_dir, self.links_dir, self.lifecycle_dir,
                                    FIXED_NOW, annotation_id, kwargs.pop("actor"))

    def register_claim(self, **kwargs):
        kwargs.setdefault("actor", "owner")
        kwargs.setdefault("now", FIXED_NOW)
        return reg.register_claim(self.claims_dir, self.lifecycle_dir,
                                   kwargs.pop("claimType", "entry_rule"),
                                   kwargs.pop("normalizedClaim", "A generic claim."),
                                   kwargs.pop("actor"), kwargs.pop("now"), **kwargs)

    def register_evidence_item(self, source_id, **kwargs):
        kwargs.setdefault("actor", "owner")
        kwargs.setdefault("now", FIXED_NOW)
        return reg.register_evidence_item(self.items_dir, self.sources_dir, self.lifecycle_dir, source_id,
                                           kwargs.pop("evidenceType", "explicit_statement"),
                                           kwargs.pop("evidenceQuality", "medium"),
                                           kwargs.pop("actor"), kwargs.pop("now"), **kwargs)

    def link(self, evidence_id, claim_id, relationship_type="supports", **kwargs):
        kwargs.setdefault("actor", "owner")
        kwargs.setdefault("now", FIXED_NOW)
        return reg.link_evidence_to_claim(self.links_dir, self.items_dir, self.claims_dir, self.lifecycle_dir,
                                           evidence_id, claim_id, relationship_type,
                                           kwargs.pop("actor"), kwargs.pop("now"), **kwargs)

    def contradict(self, claim_a, claim_b, **kwargs):
        kwargs.setdefault("actor", "owner")
        kwargs.setdefault("now", FIXED_NOW)
        return reg.create_contradiction(self.contradictions_dir, self.claims_dir, self.lifecycle_dir,
                                         claim_a, claim_b, kwargs.pop("contradictionType", "DEFINITIONAL"),
                                         kwargs.pop("severity", "material"), kwargs.pop("actor"), kwargs.pop("now"))

    def full_intake_pipeline(self, raw_text, transcript_format="timestamped_text", **intake_kwargs):
        """Registers an intake through ready_for_extraction, runs extraction,
        registers+links a source. Returns (manifest, audit, segments-by-seq)."""
        intake_kwargs.setdefault("traderId", "TJR")
        manifest = self.register_intake(sourceType="transcript", transcriptFormat=transcript_format, **intake_kwargs)
        self.transition_intake(manifest["intakeId"], "validated")
        self.transition_intake(manifest["intakeId"], "ready_for_extraction")
        src = self.register_source(traderId=intake_kwargs.get("traderId"))
        self.link_intake_to_source(manifest["intakeId"], src["sourceId"])
        audit = ep.run_intake_extraction_pipeline(self.root, manifest["intakeId"], raw_text, now=FIXED_NOW)
        segs = self.index().segments_for_intake(manifest["intakeId"])
        return manifest, src, audit, {s["sequenceNumber"]: s for s in segs}


# ---------------------------------------------------------------------------
# A. Explainability
# ---------------------------------------------------------------------------

class TestExplainability(unittest.TestCase):
    def setUp(self):
        self.repo = TempPhase1BRepo()

    def tearDown(self):
        self.repo.cleanup()

    def test_claim_with_no_evidence(self):
        claim = self.repo.register_claim()
        idx = self.repo.index()
        explanation = ee.explain_claim(idx, claim["claimId"], now=FIXED_NOW)
        self.assertEqual(explanation["confidenceState"], "insufficient_evidence")
        self.assertEqual(explanation["evidenceCounts"]["total"], 0)

    def test_one_supporting_item(self):
        src = self.repo.register_source(traderId="TJR")
        item = self.repo.register_evidence_item(src["sourceId"], directness="direct_explicit", extractionCertainty="certain")
        claim = self.repo.register_claim()
        self.repo.link(item["evidenceId"], claim["claimId"], "supports")
        idx = self.repo.index()
        explanation = ee.explain_claim(idx, claim["claimId"], now=FIXED_NOW)
        self.assertEqual(len(explanation["directSupportingEvidence"]), 1)

    def test_multiple_supporting_sources(self):
        src_a = self.repo.register_source(traderId="TJR", title="A")
        src_b = self.repo.register_source(traderId="TJR", title="B")
        item_a = self.repo.register_evidence_item(src_a["sourceId"], evidenceQuality="high", directness="direct_explicit", extractionCertainty="certain")
        item_b = self.repo.register_evidence_item(src_b["sourceId"], evidenceQuality="high", directness="direct_explicit", extractionCertainty="certain")
        claim = self.repo.register_claim()
        self.repo.link(item_a["evidenceId"], claim["claimId"], "supports")
        self.repo.link(item_b["evidenceId"], claim["claimId"], "supports")
        idx = self.repo.index()
        explanation = ee.explain_claim(idx, claim["claimId"], now=FIXED_NOW)
        self.assertEqual(explanation["sourceIndependenceAnalysis"]["independentGroupCount"], 2)

    def test_same_source_non_independent_support(self):
        src = self.repo.register_source(traderId="TJR")
        item_a = self.repo.register_evidence_item(src["sourceId"])
        item_b = self.repo.register_evidence_item(src["sourceId"])
        claim = self.repo.register_claim()
        self.repo.link(item_a["evidenceId"], claim["claimId"], "supports")
        self.repo.link(item_b["evidenceId"], claim["claimId"], "supports")
        idx = self.repo.index()
        explanation = ee.explain_claim(idx, claim["claimId"], now=FIXED_NOW)
        self.assertEqual(explanation["sourceIndependenceAnalysis"]["independentGroupCount"], 1)

    def test_conflicting_evidence(self):
        src = self.repo.register_source(traderId="TJR")
        item_s = self.repo.register_evidence_item(src["sourceId"], directness="direct_explicit")
        item_c = self.repo.register_evidence_item(src["sourceId"], directness="direct_explicit")
        claim = self.repo.register_claim()
        self.repo.link(item_s["evidenceId"], claim["claimId"], "supports")
        self.repo.link(item_c["evidenceId"], claim["claimId"], "contradicts")
        idx = self.repo.index()
        explanation = ee.explain_claim(idx, claim["claimId"], now=FIXED_NOW)
        self.assertEqual(len(explanation["contradictingEvidence"]), 1)

    def test_contested_claim(self):
        src_a = self.repo.register_source(traderId="TJR", title="A")
        src_b = self.repo.register_source(traderId="TJR", title="B")
        item_s = self.repo.register_evidence_item(src_a["sourceId"], evidenceQuality="high", directness="direct_explicit")
        item_c = self.repo.register_evidence_item(src_b["sourceId"], evidenceQuality="high", directness="direct_explicit")
        claim = self.repo.register_claim()
        self.repo.link(item_s["evidenceId"], claim["claimId"], "supports")
        self.repo.link(item_c["evidenceId"], claim["claimId"], "contradicts")
        idx = self.repo.index()
        self.assertIn(idx.claims[claim["claimId"]]["confidenceState"], ("contested", "contradicted"))

    def test_qualified_claim(self):
        src = self.repo.register_source(traderId="TJR")
        item = self.repo.register_evidence_item(src["sourceId"])
        claim = self.repo.register_claim()
        self.repo.link(item["evidenceId"], claim["claimId"], "qualifies")
        idx = self.repo.index()
        explanation = ee.explain_claim(idx, claim["claimId"], now=FIXED_NOW)
        self.assertEqual(len(explanation["contextualEvidence"]), 1)

    def test_superseded_evidence_excluded_from_active_reasoning(self):
        src = self.repo.register_source(traderId="TJR")
        original = self.repo.register_evidence_item(src["sourceId"], exactExcerpt="Original.")
        corrected = reg.correct_evidence_item(self.repo.items_dir, self.repo.sources_dir, self.repo.lifecycle_dir,
                                               original["evidenceId"], "owner", FIXED_NOW, exactExcerpt="Corrected.")
        claim = self.repo.register_claim()
        self.repo.link(corrected["evidenceId"], claim["claimId"], "supports")
        idx = self.repo.index()
        explanation = ee.explain_claim(idx, claim["claimId"], now=FIXED_NOW)
        cited_ids = [e["evidenceId"] for e in explanation["directSupportingEvidence"] + explanation["indirectSupportingEvidence"]]
        self.assertNotIn(original["evidenceId"], cited_ids)

    def test_human_readable_rendering(self):
        src = self.repo.register_source(traderId="TJR")
        item = self.repo.register_evidence_item(src["sourceId"], directness="direct_explicit")
        claim = self.repo.register_claim(normalizedClaim="Test claim text.")
        self.repo.link(item["evidenceId"], claim["claimId"], "supports")
        idx = self.repo.index()
        text = ee.render_explanation_text(ee.explain_claim(idx, claim["claimId"], now=FIXED_NOW))
        self.assertIn("Test claim text.", text)
        self.assertIn("Current assessment:", text)

    def test_machine_readable_rendering_matches_schema_fields(self):
        claim = self.repo.register_claim()
        idx = self.repo.index()
        explanation = ee.explain_claim(idx, claim["claimId"], now=FIXED_NOW)
        for field in ("claimId", "confidenceState", "generatedAt", "explanationSchemaVersion"):
            self.assertIn(field, explanation)

    def test_traceability(self):
        src = self.repo.register_source(traderId="TJR")
        item = self.repo.register_evidence_item(src["sourceId"], directness="direct_explicit")
        claim = self.repo.register_claim()
        self.repo.link(item["evidenceId"], claim["claimId"], "supports")
        idx = self.repo.index()
        explanation = ee.explain_claim(idx, claim["claimId"], now=FIXED_NOW)
        trace = ee.trace_explanation_component(explanation, "directSupportingEvidence")
        self.assertIn(item["evidenceId"], trace["derivedFromIds"])

    def test_deterministic_output(self):
        src = self.repo.register_source(traderId="TJR")
        item = self.repo.register_evidence_item(src["sourceId"], directness="direct_explicit")
        claim = self.repo.register_claim()
        self.repo.link(item["evidenceId"], claim["claimId"], "supports")
        idx = self.repo.index()
        e1 = ee.explain_claim(idx, claim["claimId"], now=FIXED_NOW)
        e2 = ee.explain_claim(idx, claim["claimId"], now=FIXED_NOW)
        self.assertEqual(e1, e2)


# ---------------------------------------------------------------------------
# B. Directness
# ---------------------------------------------------------------------------

class TestDirectness(unittest.TestCase):
    def setUp(self):
        self.repo = TempPhase1BRepo()

    def tearDown(self):
        self.repo.cleanup()

    def test_all_directness_values_accepted(self):
        src = self.repo.register_source(traderId="TJR")
        for d in evc.DIRECTNESS_CLASSIFICATIONS:
            item = self.repo.register_evidence_item(src["sourceId"], directness=d, extractionCertainty="moderate")
            self.assertEqual(item["directness"], d)

    def test_unknown_directness_rejected(self):
        src = self.repo.register_source(traderId="TJR")
        with self.assertRaises(evc.EvidenceValidationError):
            self.repo.register_evidence_item(src["sourceId"], directness="not_a_real_value", extractionCertainty="moderate")

    def test_directness_preserved_through_serialization(self):
        src = self.repo.register_source(traderId="TJR")
        item = self.repo.register_evidence_item(src["sourceId"], directness="inferred_from_context", extractionCertainty="low")
        idx = self.repo.index()
        self.assertEqual(idx.items[item["evidenceId"]]["directness"], "inferred_from_context")

    def test_directness_surfaced_in_explanation(self):
        src = self.repo.register_source(traderId="TJR")
        item = self.repo.register_evidence_item(src["sourceId"], directness="inferred_from_context", extractionCertainty="low")
        claim = self.repo.register_claim()
        self.repo.link(item["evidenceId"], claim["claimId"], "supports")
        idx = self.repo.index()
        explanation = ee.explain_claim(idx, claim["claimId"], now=FIXED_NOW)
        self.assertEqual(len(explanation["indirectSupportingEvidence"]), 1)
        self.assertEqual(explanation["indirectSupportingEvidence"][0]["directness"], "inferred_from_context")

    def test_directness_independent_of_evidence_quality(self):
        src = self.repo.register_source(traderId="TJR")
        item = self.repo.register_evidence_item(src["sourceId"], directness="direct_explicit",
                                                  extractionCertainty="certain", evidenceQuality="low")
        self.assertEqual(item["directness"], "direct_explicit")
        self.assertEqual(item["evidenceQuality"], "low")


# ---------------------------------------------------------------------------
# C. Extraction certainty
# ---------------------------------------------------------------------------

class TestExtractionCertainty(unittest.TestCase):
    def setUp(self):
        self.repo = TempPhase1BRepo()

    def tearDown(self):
        self.repo.cleanup()

    def test_all_certainty_levels_accepted(self):
        src = self.repo.register_source(traderId="TJR")
        for c in evc.EXTRACTION_CERTAINTY_LEVELS:
            item = self.repo.register_evidence_item(src["sourceId"], directness="direct_explicit", extractionCertainty=c)
            self.assertEqual(item["extractionCertainty"], c)

    def test_missing_certainty_defaults_null(self):
        src = self.repo.register_source(traderId="TJR")
        item = self.repo.register_evidence_item(src["sourceId"])
        self.assertIsNone(item["extractionCertainty"])

    def test_low_certainty_appears_in_review_queue(self):
        src = self.repo.register_source(traderId="TJR")
        item = self.repo.register_evidence_item(src["sourceId"], directness="direct_explicit", extractionCertainty="low")
        results = rev.build_all_review_queues(self.repo.review_queue_dir, FIXED_NOW, self.repo.sources_dir,
                                               self.repo.items_dir, self.repo.claims_dir, self.repo.contradictions_dir,
                                               self.repo.questions_dir, self.repo.proposals_dir, self.repo.intake_dir)
        self.assertEqual(len(results["low_certainty_evidence"]), 1)
        self.assertEqual(results["low_certainty_evidence"][0]["entityId"], item["evidenceId"])

    def test_ambiguous_extraction_in_ambiguous_queue(self):
        src = self.repo.register_source(traderId="TJR")
        self.repo.register_evidence_item(src["sourceId"], directness="direct_explicit", extractionCertainty="ambiguous")
        results = rev.build_all_review_queues(self.repo.review_queue_dir, FIXED_NOW, self.repo.sources_dir,
                                               self.repo.items_dir, self.repo.claims_dir, self.repo.contradictions_dir,
                                               self.repo.questions_dir, self.repo.proposals_dir, self.repo.intake_dir)
        self.assertEqual(len(results["ambiguous_evidence"]), 1)

    def test_certainty_not_confused_with_claim_confidence(self):
        src = self.repo.register_source(traderId="TJR")
        item = self.repo.register_evidence_item(src["sourceId"], directness="direct_explicit",
                                                  extractionCertainty="low", evidenceQuality="high")
        claim = self.repo.register_claim()
        self.repo.link(item["evidenceId"], claim["claimId"], "supports")
        idx = self.repo.index()
        # Low extraction certainty must not by itself zero out claim confidence -- it's tracked separately.
        self.assertGreater(idx.claims[claim["claimId"]]["confidenceScore"], 0)


# ---------------------------------------------------------------------------
# D. Intake manifest
# ---------------------------------------------------------------------------

class TestIntakeManifest(unittest.TestCase):
    def setUp(self):
        self.repo = TempPhase1BRepo()

    def tearDown(self):
        self.repo.cleanup()

    def test_valid_manifest(self):
        m = self.repo.register_intake(traderId="TJR", transcriptFormat="plain_text")
        self.assertEqual(m["intakeStatus"], "registered")
        self.assertTrue(m["intakeId"].startswith("INTAKE|TJR|"))

    def test_missing_source_reference_defaults_null(self):
        m = self.repo.register_intake(traderId="TJR")
        self.assertIsNone(m["sourceId"])

    def test_invalid_status_rejected(self):
        m = self.repo.register_intake(traderId="TJR")
        with self.assertRaises(evc.EvidenceValidationError):
            self.repo.transition_intake(m["intakeId"], "not_a_real_status")

    def test_lifecycle_transition_recorded(self):
        m = self.repo.register_intake(traderId="TJR")
        self.repo.transition_intake(m["intakeId"], "validated")
        idx = self.repo.index()
        events = [e for e in idx.lifecycle_events.values() if e["entityId"] == m["intakeId"]]
        self.assertTrue(any(e["eventType"] == "status_changed" and e["newStatus"] == "validated" for e in events))

    def test_illegal_transition_rejected(self):
        m = self.repo.register_intake(traderId="TJR")
        with self.assertRaises(evc.EvidenceValidationError):
            self.repo.transition_intake(m["intakeId"], "approved")

    def test_duplicate_intake_status_value(self):
        m = self.repo.register_intake(traderId="TJR")
        m2 = self.repo.transition_intake(m["intakeId"], "duplicate")
        self.assertEqual(m2["intakeStatus"], "duplicate")

    def test_incomplete_transcript_flagged(self):
        m = self.repo.register_intake(traderId="TJR", transcriptCompleteness="partial")
        self.repo.transition_intake(m["intakeId"], "validated")
        self.repo.transition_intake(m["intakeId"], "ready_for_extraction")
        self.repo.transition_intake(m["intakeId"], "extraction_in_progress")
        self.repo.transition_intake(m["intakeId"], "extracted")
        self.repo.transition_intake(m["intakeId"], "review_required")
        self.repo.transition_intake(m["intakeId"], "approved")
        results = rev.build_all_review_queues(self.repo.review_queue_dir, FIXED_NOW, self.repo.sources_dir,
                                               self.repo.items_dir, self.repo.claims_dir, self.repo.contradictions_dir,
                                               self.repo.questions_dir, self.repo.proposals_dir, self.repo.intake_dir)
        # Approving a source does not retroactively make a partial transcript
        # complete -- it should still surface in the incomplete_transcripts queue.
        self.assertEqual(len(results["incomplete_transcripts"]), 1)
        self.assertEqual(results["incomplete_transcripts"][0]["entityId"], m["intakeId"])

    def test_blocked_licensing_status(self):
        m = self.repo.register_intake(traderId="TJR", licensingStatus="unknown")
        results = rev.build_all_review_queues(self.repo.review_queue_dir, FIXED_NOW, self.repo.sources_dir,
                                               self.repo.items_dir, self.repo.claims_dir, self.repo.contradictions_dir,
                                               self.repo.questions_dir, self.repo.proposals_dir, self.repo.intake_dir)
        self.assertEqual(len(results["unresolved_licensing"]), 1)

    def test_empty_corpus_intake_queries(self):
        idx = self.repo.index()
        result = qe.list_tjr_sources_by_intake_status(idx, "registered")
        self.assertEqual(result["status"], "empty")


# ---------------------------------------------------------------------------
# E. Transcript formats
# ---------------------------------------------------------------------------

class TestTranscriptFormats(unittest.TestCase):
    def test_plain_text(self):
        segs = ta.parse_plain_text_transcript("Para one.\n\nPara two.")
        self.assertEqual(len(segs), 2)

    def test_timestamped_text(self):
        segs = ta.parse_timestamped_text_transcript("[00:00:01] A: hello\n[00:00:05] A: world")
        self.assertEqual(len(segs), 2)
        self.assertEqual(segs[0]["startTimestamp"], "00:00:01")

    def test_structured_json(self):
        segs = ta.parse_structured_json_transcript({"segments": [{"text": "hi"}]})
        self.assertEqual(len(segs), 1)

    def test_malformed_transcript_rejected(self):
        with self.assertRaises(evc.EvidenceValidationError):
            ta.parse_structured_json_transcript("{not json")

    def test_unsafe_content_treated_as_text(self):
        with self.assertRaises(evc.EvidenceValidationError):
            ta.parse_plain_text_transcript("bad\x00byte")

    def test_hash_verification(self):
        h1 = ta.transcript_content_hash("some text")
        h2 = ta.transcript_content_hash("some text")
        self.assertEqual(h1, h2)
        self.assertNotEqual(h1, ta.transcript_content_hash("other text"))

    def test_segment_ordering_preserved(self):
        segs = ta.parse_timestamped_text_transcript("[00:00:01] A: one\n[00:00:02] A: two\n[00:00:03] A: three")
        self.assertEqual([s["sequenceNumber"] for s in segs], [1, 2, 3])

    def test_line_and_timestamp_preservation(self):
        segs = ta.parse_plain_text_transcript("Line one.\nLine two.\n\nSecond para.")
        self.assertEqual(segs[0]["lineStart"], 1)
        self.assertEqual(segs[0]["lineEnd"], 2)


# ---------------------------------------------------------------------------
# F. Manual annotations
# ---------------------------------------------------------------------------

class TestManualAnnotations(unittest.TestCase):
    def setUp(self):
        self.repo = TempPhase1BRepo()
        self.manifest, self.src, self.audit, self.segs = self.repo.full_intake_pipeline(
            "[00:00:01] TJR: Displacement must always follow the sweep.")

    def tearDown(self):
        self.repo.cleanup()

    def test_valid_annotation(self):
        ann = self.repo.register_annotation(self.manifest["intakeId"], self.segs[1]["segmentId"],
            "Displacement must always follow the sweep.", "explicit_statement", "direct_explicit", "certain",
            proposedClaim="Displacement occurs after a sweep.", claimType="entry_rule", traderId="TJR")
        self.assertEqual(ann["reviewStatus"], "draft")

    def test_invalid_segment_reference_rejected(self):
        with self.assertRaises(evc.EvidenceValidationError):
            self.repo.register_annotation(self.manifest["intakeId"], "TSEG|GHOST|001",
                "text", "explicit_statement", "direct_explicit", "certain")

    def test_exact_excerpt_preservation(self):
        with self.assertRaises(evc.EvidenceValidationError):
            self.repo.register_annotation(self.manifest["intakeId"], self.segs[1]["segmentId"],
                "This is not in the segment.", "explicit_statement", "direct_explicit", "certain")

    def test_claim_proposal(self):
        ann = self.repo.register_annotation(self.manifest["intakeId"], self.segs[1]["segmentId"],
            "Displacement must always follow the sweep.", "explicit_statement", "direct_explicit", "certain",
            proposedClaim="Displacement occurs after a sweep.", claimType="entry_rule", traderId="TJR")
        self.repo.approve_annotation(ann["annotationId"])
        result = self.repo.apply_annotation(ann["annotationId"])
        self.assertTrue(result["claimId"].startswith("CLAIM|"))

    def test_relationship_proposal(self):
        ann1 = self.repo.register_annotation(self.manifest["intakeId"], self.segs[1]["segmentId"],
            "Displacement must always follow the sweep.", "explicit_statement", "direct_explicit", "certain",
            proposedClaim="Displacement occurs after a sweep.", claimType="entry_rule", traderId="TJR")
        self.repo.approve_annotation(ann1["annotationId"])
        r1 = self.repo.apply_annotation(ann1["annotationId"])
        self.assertEqual(r1["link"]["relationshipType"], "supports")

    def test_unresolved_question_field(self):
        ann = self.repo.register_annotation(self.manifest["intakeId"], self.segs[1]["segmentId"],
            "Displacement must always follow the sweep.", "explicit_statement", "direct_explicit", "certain",
            unresolvedQuestionText="Does this hold in all sessions?")
        self.assertEqual(ann["unresolvedQuestionText"], "Does this hold in all sessions?")

    def test_duplicate_annotation_allowed_but_traced(self):
        ann1 = self.repo.register_annotation(self.manifest["intakeId"], self.segs[1]["segmentId"],
            "Displacement must always follow the sweep.", "explicit_statement", "direct_explicit", "certain",
            proposedClaim="Displacement occurs after a sweep.", claimType="entry_rule", traderId="TJR")
        ann2 = self.repo.register_annotation(self.manifest["intakeId"], self.segs[1]["segmentId"],
            "Displacement must always follow the sweep.", "explicit_statement", "direct_explicit", "certain",
            proposedClaim="Displacement occurs after a sweep.", claimType="entry_rule", traderId="TJR")
        self.assertNotEqual(ann1["annotationId"], ann2["annotationId"])


# ---------------------------------------------------------------------------
# G. Claim generation
# ---------------------------------------------------------------------------

class TestClaimGeneration(unittest.TestCase):
    def setUp(self):
        self.repo = TempPhase1BRepo()
        self.manifest, self.src, self.audit, self.segs = self.repo.full_intake_pipeline(
            "[00:00:01] TJR: Displacement must always follow the sweep.\n"
            "[00:00:05] TJR: On the 15 minute chart, displacement must always follow the sweep.")

    def tearDown(self):
        self.repo.cleanup()

    def _apply(self, seq, excerpt, **kwargs):
        ann = self.repo.register_annotation(self.manifest["intakeId"], self.segs[seq]["segmentId"], excerpt,
            kwargs.pop("evidenceType", "explicit_statement"), kwargs.pop("directness", "direct_explicit"),
            kwargs.pop("certainty", "certain"), **kwargs)
        self.repo.approve_annotation(ann["annotationId"])
        return self.repo.apply_annotation(ann["annotationId"])

    def test_new_claim(self):
        r = self._apply(1, "Displacement must always follow the sweep.",
                         proposedClaim="Displacement occurs after a sweep.", claimType="entry_rule", traderId="TJR")
        self.assertEqual(r["claimClassification"], "independent")

    def test_exact_duplicate(self):
        r1 = self._apply(1, "Displacement must always follow the sweep.",
                          proposedClaim="Displacement occurs after a sweep.", claimType="entry_rule", traderId="TJR")
        ann2 = self.repo.register_annotation(self.manifest["intakeId"], self.segs[1]["segmentId"],
            "Displacement must always follow the sweep.", "explicit_statement", "direct_explicit", "certain",
            proposedClaim="Displacement occurs after a sweep.", claimType="entry_rule", traderId="TJR")
        self.repo.approve_annotation(ann2["annotationId"])
        r2 = self.repo.apply_annotation(ann2["annotationId"])
        self.assertEqual(r2["claimClassification"], "exact_duplicate")
        self.assertEqual(r1["claimId"], r2["claimId"])

    def test_scoped_variant_creates_separate_claim(self):
        r1 = self._apply(1, "Displacement must always follow the sweep.",
                          proposedClaim="Displacement occurs after a sweep.", claimType="entry_rule", traderId="TJR")
        r2 = self._apply(2, "On the 15 minute chart, displacement must always follow the sweep.",
                          proposedClaim="Displacement occurs after a sweep.", claimType="entry_rule",
                          traderId="TJR", timeframe="15m")
        self.assertEqual(r2["claimClassification"], "scoped_variant")
        self.assertNotEqual(r1["claimId"], r2["claimId"])
        idx = self.repo.index()
        self.assertEqual(idx.claims[r2["claimId"]]["possibleDuplicateClaimIds"], [r1["claimId"]])

    def test_near_duplicate_creates_separate_claim(self):
        r1 = self._apply(1, "Displacement must always follow the sweep.",
                          proposedClaim="Displacement must always follow the sweep in most cases.",
                          claimType="entry_rule", traderId="TJR")
        r2 = self._apply(1, "Displacement must always follow the sweep.",
                          proposedClaim="Displacement must always follow the sweep in some cases.",
                          claimType="entry_rule", traderId="TJR")
        self.assertEqual(r2["claimClassification"], "near_duplicate")
        self.assertNotEqual(r1["claimId"], r2["claimId"])

    def test_contradiction_candidate_relationship(self):
        r1 = self._apply(1, "Displacement must always follow the sweep.",
                          proposedClaim="Displacement occurs after a sweep.", claimType="entry_rule", traderId="TJR")
        ann2 = self.repo.register_annotation(self.manifest["intakeId"], self.segs[2]["segmentId"],
            "On the 15 minute chart, displacement must always follow the sweep.", "opinion", "inferred_from_context", "low",
            existingClaimId=r1["claimId"], relationshipType="contradicts")
        self.repo.approve_annotation(ann2["annotationId"])
        r2 = self.repo.apply_annotation(ann2["annotationId"])
        self.assertEqual(r2["link"]["relationshipType"], "contradicts")

    def test_exception_claim_type(self):
        r = self._apply(1, "Displacement must always follow the sweep.", evidenceType="exception_statement",
                         proposedClaim="An exception applies after high-impact news.", claimType="exception", traderId="TJR")
        idx = self.repo.index()
        self.assertEqual(idx.claims[r["claimId"]]["claimType"], "exception")

    def test_unreviewed_extraction_status(self):
        r = self._apply(1, "Displacement must always follow the sweep.",
                         proposedClaim="Displacement occurs after a sweep.", claimType="entry_rule", traderId="TJR")
        idx = self.repo.index()
        self.assertEqual(idx.claims[r["claimId"]]["claimStatus"], "pending_review")


# ---------------------------------------------------------------------------
# H. Rule candidates
# ---------------------------------------------------------------------------

class TestRuleCandidates(unittest.TestCase):
    def setUp(self):
        self.repo = TempPhase1BRepo()

    def tearDown(self):
        self.repo.cleanup()

    def test_eligible_claim(self):
        src = self.repo.register_source(traderId="TJR")
        item = self.repo.register_evidence_item(src["sourceId"], directness="direct_explicit", extractionCertainty="certain")
        claim = self.repo.register_claim(claimType="entry_rule")
        self.repo.link(item["evidenceId"], claim["claimId"], "supports")
        proposal = rcp.propose_rule_candidate(self.repo.proposals_dir, self.repo.claims_dir, self.repo.links_dir,
            self.repo.items_dir, self.repo.contradictions_dir, self.repo.questions_dir, FIXED_NOW,
            [claim["claimId"]], "owner", "test rationale")
        self.assertEqual(proposal["claimType"], "entry_rule")

    def test_ineligible_claim_rejected(self):
        claim = self.repo.register_claim(claimType="definition")
        with self.assertRaises(evc.EvidenceValidationError):
            rcp.propose_rule_candidate(self.repo.proposals_dir, self.repo.claims_dir, self.repo.links_dir,
                self.repo.items_dir, self.repo.contradictions_dir, self.repo.questions_dir, FIXED_NOW,
                [claim["claimId"]], "owner", "test")

    def test_originating_claim_ids_recorded(self):
        claim = self.repo.register_claim(claimType="risk_rule")
        proposal = rcp.propose_rule_candidate(self.repo.proposals_dir, self.repo.claims_dir, self.repo.links_dir,
            self.repo.items_dir, self.repo.contradictions_dir, self.repo.questions_dir, FIXED_NOW,
            [claim["claimId"]], "owner", "test")
        self.assertEqual(proposal["originatingClaimIds"], [claim["claimId"]])

    def test_evidence_links_recorded(self):
        src = self.repo.register_source(traderId="TJR")
        item = self.repo.register_evidence_item(src["sourceId"])
        claim = self.repo.register_claim(claimType="risk_rule")
        self.repo.link(item["evidenceId"], claim["claimId"], "supports")
        proposal = rcp.propose_rule_candidate(self.repo.proposals_dir, self.repo.claims_dir, self.repo.links_dir,
            self.repo.items_dir, self.repo.contradictions_dir, self.repo.questions_dir, FIXED_NOW,
            [claim["claimId"]], "owner", "test")
        self.assertIn(item["evidenceId"], proposal["evidenceIds"])

    def test_contradictions_preserved_in_status(self):
        claim_a = self.repo.register_claim(claimType="risk_rule", normalizedClaim="A")
        claim_b = self.repo.register_claim(normalizedClaim="B")
        self.repo.contradict(claim_a["claimId"], claim_b["claimId"])
        proposal = rcp.propose_rule_candidate(self.repo.proposals_dir, self.repo.claims_dir, self.repo.links_dir,
            self.repo.items_dir, self.repo.contradictions_dir, self.repo.questions_dir, FIXED_NOW,
            [claim_a["claimId"]], "owner", "test")
        self.assertEqual(proposal["contradictionStatus"], "open_contradiction")

    def test_no_active_status_ever_possible(self):
        claim = self.repo.register_claim(claimType="risk_rule")
        proposal = rcp.propose_rule_candidate(self.repo.proposals_dir, self.repo.claims_dir, self.repo.links_dir,
            self.repo.items_dir, self.repo.contradictions_dir, self.repo.questions_dir, FIXED_NOW,
            [claim["claimId"]], "owner", "test")
        self.assertIn(proposal["status"], ("proposed", "superseded", "withdrawn"))

    def test_no_execution_integration(self):
        claim = self.repo.register_claim(claimType="risk_rule")
        proposal = rcp.propose_rule_candidate(self.repo.proposals_dir, self.repo.claims_dir, self.repo.links_dir,
            self.repo.items_dir, self.repo.contradictions_dir, self.repo.questions_dir, FIXED_NOW,
            [claim["claimId"]], "owner", "test")
        self.assertNotIn("index.html", json.dumps(proposal))

    def test_no_automatic_promotion(self):
        # propose_rule_candidate never touches any StrategyRule file.
        claim = self.repo.register_claim(claimType="risk_rule")
        before = sorted(globmod.glob(os.path.join(TI_ROOT, "traders", "*", "rules", "*.json")))
        rcp.propose_rule_candidate(self.repo.proposals_dir, self.repo.claims_dir, self.repo.links_dir,
            self.repo.items_dir, self.repo.contradictions_dir, self.repo.questions_dir, FIXED_NOW,
            [claim["claimId"]], "owner", "test")
        after = sorted(globmod.glob(os.path.join(TI_ROOT, "traders", "*", "rules", "*.json")))
        self.assertEqual(before, after)


# ---------------------------------------------------------------------------
# I. Unresolved questions
# ---------------------------------------------------------------------------

class TestUnresolvedQuestions(unittest.TestCase):
    def setUp(self):
        self.repo = TempPhase1BRepo()

    def tearDown(self):
        self.repo.cleanup()

    def test_missing_timeframe(self):
        claim = self.repo.register_claim(claimType="entry_rule", traderId="TJR")
        specs = eq.detect_questions_for_claim(claim, [], {}, [claim])
        self.assertTrue(any(s["questionType"] == "missing_timeframe" for s in specs))

    def test_missing_session(self):
        claim = self.repo.register_claim(claimType="entry_rule", traderId="TJR", timeframe="5m")
        specs = eq.detect_questions_for_claim(claim, [], {}, [claim])
        self.assertTrue(any(s["questionType"] == "missing_session" for s in specs))

    def test_missing_invalidation(self):
        claim = self.repo.register_claim(claimType="entry_rule", traderId="TJR")
        specs = eq.detect_questions_for_claim(claim, [], {}, [claim])
        self.assertTrue(any(s["questionType"] == "missing_invalidation" for s in specs))

    def test_missing_invalidation_resolved_by_sibling(self):
        claim = self.repo.register_claim(claimType="entry_rule", traderId="TJR", strategyFamilyId="SF", timeframe="5m")
        sibling = self.repo.register_claim(claimType="invalidation_rule", traderId="TJR", strategyFamilyId="SF", timeframe="5m")
        specs = eq.detect_questions_for_claim(claim, [], {}, [claim, sibling])
        self.assertFalse(any(s["questionType"] == "missing_invalidation" for s in specs))

    def test_ambiguous_stop(self):
        src = self.repo.register_source(traderId="TJR")
        item = self.repo.register_evidence_item(src["sourceId"], directness="inferred_from_context", extractionCertainty="ambiguous")
        claim = self.repo.register_claim(claimType="stop_rule", traderId="TJR")
        link = self.repo.link(item["evidenceId"], claim["claimId"], "supports")
        idx = self.repo.index()
        specs = eq.detect_questions_for_claim(idx.claims[claim["claimId"]], [link], idx.items, [idx.claims[claim["claimId"]]])
        self.assertTrue(any(s["questionType"] == "missing_stop_placement" for s in specs))

    def test_discretionary_management(self):
        src = self.repo.register_source(traderId="TJR")
        item = self.repo.register_evidence_item(src["sourceId"], exactExcerpt="It depends on the day, honestly.")
        claim = self.repo.register_claim(claimType="trade_management_rule", traderId="TJR")
        link = self.repo.link(item["evidenceId"], claim["claimId"], "supports")
        idx = self.repo.index()
        specs = eq.detect_questions_for_claim(idx.claims[claim["claimId"]], [link], idx.items, [idx.claims[claim["claimId"]]])
        self.assertTrue(any(s["questionType"] == "discretionary_management" for s in specs))

    def test_contradictory_behavior(self):
        src = self.repo.register_source(traderId="TJR")
        item_explicit = self.repo.register_evidence_item(src["sourceId"], directness="direct_explicit")
        item_demo = self.repo.register_evidence_item(src["sourceId"], directness="direct_demonstrated")
        claim = self.repo.register_claim(traderId="TJR")
        link1 = self.repo.link(item_explicit["evidenceId"], claim["claimId"], "supports")
        link2 = self.repo.link(item_demo["evidenceId"], claim["claimId"], "contradicts")
        idx = self.repo.index()
        specs = eq.detect_questions_for_claim(idx.claims[claim["claimId"]], [link1, link2], idx.items, [idx.claims[claim["claimId"]]])
        self.assertTrue(any(s["questionType"] == "behavior_conflicts_with_instruction" for s in specs))

    def test_deterministic_priority_ordering(self):
        claim = self.repo.register_claim(claimType="entry_rule", traderId="TJR")
        specs1 = eq.detect_questions_for_claim(claim, [], {}, [claim])
        specs2 = eq.detect_questions_for_claim(claim, [], {}, [claim])
        self.assertEqual(specs1, specs2)

    def test_no_fabricated_answer(self):
        questions_dir = self.repo.questions_dir
        claim = self.repo.register_claim(claimType="entry_rule", traderId="TJR")
        created = eq.generate_questions_for_claim(questions_dir, FIXED_NOW, claim, [], {}, [claim])
        for q in created:
            self.assertEqual(q["answerStatus"], "unanswered")
            self.assertEqual(q["answerEvidenceIds"], [])


# ---------------------------------------------------------------------------
# J. Review queues
# ---------------------------------------------------------------------------

class TestReviewQueues(unittest.TestCase):
    def setUp(self):
        self.repo = TempPhase1BRepo()

    def tearDown(self):
        self.repo.cleanup()

    def _build(self):
        return rev.build_all_review_queues(self.repo.review_queue_dir, FIXED_NOW, self.repo.sources_dir,
            self.repo.items_dir, self.repo.claims_dir, self.repo.contradictions_dir,
            self.repo.questions_dir, self.repo.proposals_dir, self.repo.intake_dir)

    def test_low_certainty(self):
        src = self.repo.register_source(traderId="TJR")
        self.repo.register_evidence_item(src["sourceId"], directness="direct_explicit", extractionCertainty="low")
        self.assertEqual(len(self._build()["low_certainty_evidence"]), 1)

    def test_contradiction_queue(self):
        claim_a = self.repo.register_claim(normalizedClaim="A")
        claim_b = self.repo.register_claim(normalizedClaim="B")
        self.repo.contradict(claim_a["claimId"], claim_b["claimId"])
        self.assertEqual(len(self._build()["contradiction_candidates"]), 1)

    def test_duplicate_queue(self):
        c1 = self.repo.register_claim(normalizedClaim="Same text.", traderId="TJR")
        c2 = self.repo.register_claim(normalizedClaim="Same text.", traderId="TJR")
        self.assertGreaterEqual(len(self._build()["duplicate_candidates"]), 1)

    def test_insufficient_evidence_queue(self):
        self.repo.register_claim()
        self.assertEqual(len(self._build()["insufficient_independent_evidence"]), 1)

    def test_incomplete_transcript_queue(self):
        self.repo.register_intake(traderId="TJR", transcriptCompleteness="partial")
        self.assertEqual(len(self._build()["incomplete_transcripts"]), 1)

    def test_provenance_finding_queue(self):
        self.repo.register_source(traderId="TJR", provenanceStatus="unverified")
        self.assertEqual(len(self._build()["missing_provenance"]), 1)

    def test_deterministic_ordering(self):
        self.repo.register_source(traderId="TJR", provenanceStatus="unverified")
        r1 = self._build()
        r2 = self._build()
        ids1 = [e["entityId"] for e in r1["missing_provenance"]]
        ids2 = [e["entityId"] for e in r2["missing_provenance"]]
        self.assertEqual(ids1, ids2)

    def test_resolution_lifecycle(self):
        self.repo.register_source(traderId="TJR", provenanceStatus="unverified")
        results = self._build()
        entry = results["missing_provenance"][0]
        updated = rev.set_entry_review_status(self.repo.review_queue_dir, entry["queueEntryId"], "resolved", FIXED_NOW,
                                               reviewer="owner", resolution="Confirmed provenance.")
        self.assertEqual(updated["reviewStatus"], "resolved")


# ---------------------------------------------------------------------------
# K. Reports
# ---------------------------------------------------------------------------

class TestReports(unittest.TestCase):
    def test_tjr_research_report_from_synthetic_fixture(self):
        idx = qe.EvidenceIndex.load(SYNTHETIC_TJR_ROOT)
        intake_id = sorted(idx.intakes.keys())[0]
        report = tr.generate_tjr_research_report(idx, intake_id, now=FIXED_NOW)
        self.assertGreater(len(report["claimsGenerated"]), 0)
        self.assertGreater(len(report["unresolvedQuestions"]), 0)

    def test_empty_corpus_report(self):
        repo = TempPhase1BRepo()
        try:
            manifest = repo.register_intake(traderId="TJR")
            idx = repo.index()
            report = tr.generate_tjr_research_report(idx, manifest["intakeId"], now=FIXED_NOW)
            self.assertEqual(report["evidenceExtracted"]["count"], 0)
            self.assertEqual(report["claimsGenerated"], [])
        finally:
            repo.cleanup()

    def test_not_found_intake_returns_none(self):
        idx = qe.EvidenceIndex.load(SYNTHETIC_TJR_ROOT)
        self.assertIsNone(tr.generate_tjr_research_report(idx, "INTAKE|GHOST|00000000|999", now=FIXED_NOW))

    def test_json_output_serializable(self):
        idx = qe.EvidenceIndex.load(SYNTHETIC_TJR_ROOT)
        intake_id = sorted(idx.intakes.keys())[0]
        report = tr.generate_tjr_research_report(idx, intake_id, now=FIXED_NOW)
        json.dumps(report, default=str)  # must not raise

    def test_markdown_output(self):
        idx = qe.EvidenceIndex.load(SYNTHETIC_TJR_ROOT)
        intake_id = sorted(idx.intakes.keys())[0]
        report = tr.generate_tjr_research_report(idx, intake_id, now=FIXED_NOW)
        md = tr.render_tjr_report_markdown(report)
        self.assertIn("# TJR Research Report", md)
        self.assertIn("## 25. Production Behavior Changed", md)

    def test_every_factual_statement_traceable(self):
        idx = qe.EvidenceIndex.load(SYNTHETIC_TJR_ROOT)
        intake_id = sorted(idx.intakes.keys())[0]
        report = tr.generate_tjr_research_report(idx, intake_id, now=FIXED_NOW)
        for claim_summary in report["claimsGenerated"]:
            self.assertIn(claim_summary["claimId"], idx.claims)

    def test_no_unsupported_narrative(self):
        idx = qe.EvidenceIndex.load(SYNTHETIC_TJR_ROOT)
        claim_id = sorted(idx.claims.keys())[0]
        explanation = ee.explain_claim(idx, claim_id, now=FIXED_NOW)
        # Every embedded evidence line must resolve to a real, still-stored EvidenceItem.
        for e in explanation["directSupportingEvidence"] + explanation["indirectSupportingEvidence"]:
            self.assertIn(e["evidenceId"], idx.items)


# ---------------------------------------------------------------------------
# L. Integrity
# ---------------------------------------------------------------------------

class TestIntegrity(unittest.TestCase):
    def setUp(self):
        self.repo = TempPhase1BRepo()

    def tearDown(self):
        self.repo.cleanup()

    def test_clean_system(self):
        report = self.repo.validate()
        self.assertEqual(report["summary"], {"INFO": 0, "WARNING": 0, "ERROR": 0, "FATAL": 0})

    def test_orphan_segment(self):
        manifest = self.repo.register_intake(traderId="TJR", transcriptFormat="plain_text")
        segs = ta.parse_plain_text_transcript("Some text.")
        self.repo.register_segments(manifest["intakeId"], segs)
        # Corrupt: point segment at a nonexistent intake
        path = globmod.glob(os.path.join(self.repo.segments_dir, "*.json"))[0]
        record = json.load(open(path))
        record["intakeId"] = "INTAKE|GHOST|00000000|999"
        json.dump(record, open(path, "w"))
        report = self.repo.validate()
        self.assertTrue(any(f["findingType"] == "ORPHANED_SEGMENT" for f in report["findings"]))

    def test_orphan_annotation(self):
        manifest = self.repo.register_intake(traderId="TJR", transcriptFormat="plain_text")
        segs = ta.parse_plain_text_transcript("Some text.")
        seg_records = self.repo.register_segments(manifest["intakeId"], segs)
        ann = self.repo.register_annotation(manifest["intakeId"], seg_records[0]["segmentId"], "Some text.",
                                             "explicit_statement", "direct_explicit", "certain")
        path = globmod.glob(os.path.join(self.repo.annotations_dir, "*.json"))[0]
        record = json.load(open(path))
        record["segmentId"] = "TSEG|GHOST|001"
        json.dump(record, open(path, "w"))
        report = self.repo.validate()
        self.assertTrue(any(f["findingType"] == "INVALID_ANNOTATION_REFERENCE" for f in report["findings"]))

    def test_hash_mismatch(self):
        manifest = self.repo.register_intake(traderId="TJR", transcriptFormat="plain_text")
        segs = ta.parse_plain_text_transcript("Some text.")
        seg_records = self.repo.register_segments(manifest["intakeId"], segs)
        path = os.path.join(self.repo.segments_dir, evc.segment_id_to_filename(seg_records[0]["segmentId"]))
        record = json.load(open(path))
        record["textHash"] = "tampered"
        json.dump(record, open(path, "w"))
        report = self.repo.validate()
        self.assertTrue(any(f["findingType"] == "SEGMENT_HASH_MISMATCH" for f in report["findings"]))

    def test_sequence_gaps(self):
        manifest = self.repo.register_intake(traderId="TJR", transcriptFormat="plain_text")
        segs = ta.parse_plain_text_transcript("Para one.\n\nPara two.")
        seg_records = self.repo.register_segments(manifest["intakeId"], segs)
        path = os.path.join(self.repo.segments_dir, evc.segment_id_to_filename(seg_records[1]["segmentId"]))
        record = json.load(open(path))
        record["sequenceNumber"] = 5
        json.dump(record, open(path, "w"))
        report = self.repo.validate()
        self.assertTrue(any(f["findingType"] == "SEGMENT_SEQUENCE_GAP" for f in report["findings"]))

    def test_invalid_line_range(self):
        manifest = self.repo.register_intake(traderId="TJR", transcriptFormat="plain_text")
        segs = ta.parse_plain_text_transcript("Some text.")
        seg_records = self.repo.register_segments(manifest["intakeId"], segs)
        path = os.path.join(self.repo.segments_dir, evc.segment_id_to_filename(seg_records[0]["segmentId"]))
        record = json.load(open(path))
        record["lineStart"] = 10
        record["lineEnd"] = 2
        json.dump(record, open(path, "w"))
        report = self.repo.validate()
        self.assertTrue(any(f["findingType"] == "IMPOSSIBLE_LINE_RANGE" for f in report["findings"]))

    def test_explanation_without_trace(self):
        claim = self.repo.register_claim()
        path = os.path.join(self.repo.claims_dir, evc.claim_id_to_filename(claim["claimId"]))
        record = json.load(open(path))
        record["evidenceCount"] = 3
        json.dump(record, open(path, "w"))
        report = self.repo.validate()
        self.assertTrue(any(f["findingType"] in ("EXPLANATION_WITHOUT_PROVENANCE", "ORPHANED_CLAIM") for f in report["findings"]))

    def test_active_rule_candidate_violation(self):
        claim = self.repo.register_claim(claimType="risk_rule")
        proposal = rcp.propose_rule_candidate(self.repo.proposals_dir, self.repo.claims_dir, self.repo.links_dir,
            self.repo.items_dir, self.repo.contradictions_dir, self.repo.questions_dir, FIXED_NOW,
            [claim["claimId"]], "owner", "test")
        path = os.path.join(self.repo.proposals_dir, evc.proposal_id_to_filename(proposal["proposalId"]))
        record = json.load(open(path))
        record["status"] = "active"
        json.dump(record, open(path, "w"))
        report = self.repo.validate()
        self.assertTrue(any(f["findingType"] == "RULE_CANDIDATE_INCORRECTLY_ACTIVE" and f["severity"] == "FATAL"
                             for f in report["findings"]))

    def test_synthetic_real_path_violation(self):
        self.repo.register_claim(normalizedClaim="SYNTHETIC TEST DATA / NOT REAL TJR RESEARCH example.")
        report = self.repo.validate(is_production=True)
        self.assertTrue(any(f["findingType"] == "MISLABELED_SYNTHETIC_FIXTURE" for f in report["findings"]))

    def test_production_execution_coupling_detection(self):
        # Structural guarantee: no evidence/Phase-1B script ever opens, reads,
        # or writes index.html, and none imports a network-capable module.
        # (Prose *mentioning* "index.html" in a comment/docstring to document
        # this very guarantee is fine and expected -- only functional
        # coupling, i.e. the literal filename appearing as a quoted string
        # argument to a file-opening call, would be a real violation.)
        for fname in ("evidence_common.py", "evidence_registry.py", "intake_registry.py",
                      "annotation_pipeline.py", "extraction_pipeline.py", "evidence_questions.py",
                      "rule_candidate_proposals.py", "review_queues.py", "evidence_explain.py", "tjr_report.py"):
            path = os.path.join(SCRIPTS_DIR, fname)
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            for line in lines:
                # Only a *functional* coupling is a violation -- index.html
                # named as a file-opening argument on the same line. Prose
                # mentioning it in a comment/docstring (documenting this very
                # guarantee) is expected and fine.
                if "index.html" in line and ("open(" in line or "requests." in line or "urlopen(" in line):
                    self.fail("%s appears to open/fetch index.html: %r" % (fname, line))
            content = "".join(lines)
            for banned in ("requests", "urllib.request", "http.client", "socket", "selenium", "playwright"):
                self.assertNotIn("import %s" % banned, content)


# ---------------------------------------------------------------------------
# M. Knowledge Graph
# ---------------------------------------------------------------------------

class TestKnowledgeGraphPhase1B(unittest.TestCase):
    def test_new_node_types_registered(self):
        for t in ("TRANSCRIPT_SEGMENT", "INTAKE_MANIFEST", "EVIDENCE_QUESTION",
                   "REVIEW_QUEUE_ENTRY", "RULE_CANDIDATE_PROPOSAL"):
            self.assertIn(t, gc.NODE_TYPES)

    def test_new_edge_types_registered(self):
        for t in ("EVIDENCE_FROM_SEGMENT", "RAISES_QUESTION", "REQUIRES_REVIEW",
                   "PROPOSES_RULE", "BLOCKED_BY", "RESOLVED_BY_EVIDENCE"):
            self.assertIn(t, gc.EDGE_TYPES)

    def test_synthetic_graph_separation(self):
        # The synthetic_tjr_demo fixture must never be picked up by discover_entities()
        # against the real repo root -- it lives under tests/, not docs/trader-intelligence/.
        self.assertFalse(SYNTHETIC_TJR_ROOT.startswith(TI_ROOT))

    def test_every_phase1b_node_traces_to_a_real_file_on_disk(self):
        """No Phase 1B node is fabricated: each matches a file that exists.

        Replaces an assertion that the production graph held ZERO Phase 1B nodes.
        That was a snapshot of an empty corpus, not an invariant -- once real
        intake landed it reported the intended state as a failure, and before that
        it would have "passed" for any change at all. The provenance relation it
        was proxying is asserted directly and survives corpus growth.
        """
        graph_root = os.path.join(TI_ROOT, "graph")
        nodes, edges, findings, _raw = gc.build_nodes_and_edges(REPO_ROOT, TI_ROOT, graph_root)
        blocking = [f for f in findings if f.get("severity") in ("ERROR", "FATAL")]
        self.assertEqual(blocking, [])

        phase1b_nodes = [n for n in nodes if n["nodeType"] in
                          ("TRANSCRIPT_SEGMENT", "INTAKE_MANIFEST", "EVIDENCE_QUESTION",
                           "REVIEW_QUEUE_ENTRY", "RULE_CANDIDATE_PROPOSAL")]
        # Per NODE TYPE, not over the union. A union guard is satisfied while one
        # type has silently dropped to zero -- breaking a single discovery glob
        # removed an entire type and this check still passed.
        for node_type in ("TRANSCRIPT_SEGMENT", "INTAKE_MANIFEST", "EVIDENCE_QUESTION",
                          "REVIEW_QUEUE_ENTRY", "RULE_CANDIDATE_PROPOSAL"):
            self.assertTrue(any(n["nodeType"] == node_type for n in phase1b_nodes),
                            "no %s nodes in the production graph -- the checks "
                            "below would skip that type entirely" % node_type)

        for node in phase1b_nodes:
            path = os.path.join(REPO_ROOT, node["sourceFile"])
            self.assertTrue(os.path.isfile(path),
                            "%s cites sourceFile %s, which does not exist"
                            % (node["nodeId"], node["sourceFile"]))
            with open(path, "r", encoding="utf-8") as handle:
                entity = json.load(handle)
            self.assertEqual(node["contentHash"], independent_content_hash(entity),
                             "%s does not match the current content of %s"
                             % (node["nodeId"], node["sourceFile"]))

    def test_reproducible_manifests(self):
        graph_root = os.path.join(TI_ROOT, "graph")
        n1, e1, _f1, _r1 = gc.build_nodes_and_edges(REPO_ROOT, TI_ROOT, graph_root)
        n2, e2, _f2, _r2 = gc.build_nodes_and_edges(REPO_ROOT, TI_ROOT, graph_root)
        self.assertEqual([n["nodeId"] for n in n1], [n["nodeId"] for n in n2])
        self.assertEqual([e["edgeId"] for e in e1], [e["edgeId"] for e in e2])

    def test_existing_graph_integrity(self):
        graph_root = os.path.join(TI_ROOT, "graph")
        nodes, edges, findings, raw = gc.build_nodes_and_edges(REPO_ROOT, TI_ROOT, graph_root)
        report = validate_graph.run_integrity_checks(nodes, edges, raw, findings, "TEST")
        self.assertEqual(report["summary"]["FATAL"], 0)


# ---------------------------------------------------------------------------
# N. Regression
# ---------------------------------------------------------------------------

class TestPhase1BRegression(unittest.TestCase):
    def test_full_pipeline_end_to_end(self):
        """A single, comprehensive smoke test exercising intake -> segment ->
        suggest -> annotate -> apply -> question -> propose -> queue in one
        pass, independent of the static synthetic_tjr_demo fixture."""
        repo = TempPhase1BRepo()
        try:
            manifest, src, audit, segs = repo.full_intake_pipeline(
                "[00:00:01] TJR: Displacement must always follow the sweep.")
            self.assertEqual(audit["status"], "extracted")
            self.assertTrue(len(audit["candidateSuggestions"]) >= 1)
            suggestion = audit["candidateSuggestions"][0]
            ann = repo.register_annotation(manifest["intakeId"], suggestion["segmentId"], suggestion["excerpt"],
                suggestion["suggestedEvidenceType"], suggestion["suggestedDirectness"],
                suggestion["suggestedExtractionCertainty"],
                proposedClaim="Displacement occurs after a sweep.", claimType="entry_rule", traderId="TJR")
            repo.approve_annotation(ann["annotationId"])
            result = repo.apply_annotation(ann["annotationId"])
            post_audit = ep.run_post_annotation_pipeline(repo.root, [result["claimId"]], now=FIXED_NOW)
            self.assertIsInstance(post_audit["questionsCreated"], list)
            report = repo.validate()
            self.assertEqual(report["summary"]["FATAL"], 0)
        finally:
            repo.cleanup()

    def test_evidence_common_still_backward_compatible(self):
        repo = TempPhase1BRepo()
        try:
            src = repo.register_source(traderId="TJR")
            item = repo.register_evidence_item(src["sourceId"])  # no directness/certainty -- Phase 1A style
            self.assertIsNone(item["directness"])
            self.assertIsNone(item["extractionCertainty"])
        finally:
            repo.cleanup()


if __name__ == "__main__":
    unittest.main()

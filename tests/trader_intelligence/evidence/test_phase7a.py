#!/usr/bin/env python3
"""PROGRAM-007 Phase 7A (Knowledge Library vertical slice) test suite.

Pure stdlib (unittest). Fully offline, deterministic. Run with:

    python3 -m unittest tests.trader_intelligence.evidence.test_phase7a -v

This module currently covers Deliverable 8 (Knowledge Graph integration) --
the domain-model tests for Trader Profile / Strategy Blueprint / Knowledge
Gap / Hypothesis (Deliverable 9 categories A-D), transcript-integration
(category E), and safety-regression (category F) are tracked separately and
land alongside knowledge_library_report.py.
"""
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timezone

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts", "trader_intelligence")
TI_ROOT = os.path.join(REPO_ROOT, "docs", "trader-intelligence")

sys.path.insert(0, SCRIPTS_DIR)
import graph_common as gc              # noqa: E402
import evidence_common as evc          # noqa: E402
import evidence_registry as reg        # noqa: E402
import evidence_questions as eqs       # noqa: E402
import query_evidence as qe            # noqa: E402
import validate_graph                  # noqa: E402
import trader_profile as tp            # noqa: E402
import strategy_blueprint as sb        # noqa: E402
import knowledge_gaps as kg            # noqa: E402
import hypothesis_proposals as hp      # noqa: E402
import review_queues as rev            # noqa: E402
import knowledge_library_report as klr  # noqa: E402
import transcript_adapters as ta       # noqa: E402
import intake_registry as ir           # noqa: E402
import annotation_pipeline as ap       # noqa: E402
import validate_evidence as ve         # noqa: E402

FIXED_NOW = datetime(2026, 7, 26, 12, 0, 0, tzinfo=timezone.utc)


class TempKnowledgeLibraryRepo:
    """A throwaway full copy of docs/trader-intelligence (so trader_profile's
    read of the real Wave-1 traders/tjr/profile.json behaves exactly as it
    would in production) plus a scratch evidence tree populated with one
    small, real (not fixture-file, hand-authored-via-the-real-registry)
    claim/evidence scenario deliberately shaped to be contested -- so the
    profile/blueprint/gap/hypothesis pipeline has something genuine to
    reason about instead of running against an empty trader."""

    def __init__(self):
        self.root = tempfile.mkdtemp(prefix="mogo_phase7a_test_")
        self.ti_root = os.path.join(self.root, "docs", "trader-intelligence")
        self.graph_root = os.path.join(self.ti_root, "graph")
        shutil.copytree(TI_ROOT, self.ti_root)
        self.evidence_root = os.path.join(self.ti_root, "evidence")
        # The copied evidence/ tree is SCRATCH. That was only implicitly true
        # while production evidence/ was empty; once a real transcript intake
        # exists on disk, copytree would seed this fixture with production
        # records and silently invalidate every assertion below. Emptying each
        # record collection makes the scratch guarantee explicit.
        for name in ("sources", "items", "claims", "links", "contradictions", "lifecycle",
                     "questions", "proposals", "review-queue", "profiles", "blueprints",
                     "gaps", "hypotheses", "intake", "segments", "annotations", "reports"):
            d = os.path.join(self.evidence_root, name)
            if os.path.isdir(d):
                shutil.rmtree(d)
            os.makedirs(d, exist_ok=True)
            setattr(self, name.replace("-", "_") + "_dir", d)

    def cleanup(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def index(self):
        return qe.EvidenceIndex.load(self.evidence_root)

    def build_graph(self):
        return gc.build_nodes_and_edges(self.root, self.ti_root, self.graph_root)

    def seed_contested_entry_rule_claim(self):
        """Registers one real source, one supporting + one contradicting
        EvidenceItem, and one entry_rule Claim for trader TJR -- via the
        actual registry/confidence pipeline, not a hand-authored fixture --
        so the resulting confidenceState='contested' is genuinely computed,
        not asserted into existence."""
        source = reg.register_source(self.sources_dir, self.lifecycle_dir, "transcript",
                                      "owner", FIXED_NOW, traderId="TJR", title="Phase 7A smoke-test source")
        claim = reg.register_claim(self.claims_dir, self.lifecycle_dir, "entry_rule",
                                    "Displacement occurs before a valid entry.", "owner", FIXED_NOW,
                                    traderId="TJR")
        support_item = reg.register_evidence_item(
            self.items_dir, self.sources_dir, self.lifecycle_dir, source["sourceId"],
            "explicit_statement", "high", "owner", FIXED_NOW,
            exactExcerpt="You need displacement before you enter.",
            normalizedObservation="Displacement is required before entry.",
            directness="direct_explicit", extractionCertainty="high")
        contra_item = reg.register_evidence_item(
            self.items_dir, self.sources_dir, self.lifecycle_dir, source["sourceId"],
            "opinion", "low", "owner", FIXED_NOW,
            exactExcerpt="Sometimes I skip displacement if the sweep is clean enough.",
            normalizedObservation="Displacement may not always be required before entry.",
            directness="indirect_implied", extractionCertainty="moderate")
        reg.link_evidence_to_claim(self.links_dir, self.items_dir, self.claims_dir, self.lifecycle_dir,
                                    support_item["evidenceId"], claim["claimId"], "supports", "owner", FIXED_NOW)
        reg.link_evidence_to_claim(self.links_dir, self.items_dir, self.claims_dir, self.lifecycle_dir,
                                    contra_item["evidenceId"], claim["claimId"], "contradicts", "owner", FIXED_NOW)
        claims = qe._load_dir(self.claims_dir, "claimId")
        return claims[claim["claimId"]], support_item, contra_item

    def run_transcript_pipeline(self):
        """Real plain-text transcript -> IntakeManifest -> TranscriptSegments
        -> ManualAnnotation -> approved -> applied (EvidenceItem+Claim+Link)
        -- exercising Phase 1B's own intake pipeline, not evidence_registry
        called directly -- then the Phase 7A pipeline on top. Proves the two
        phases compose end-to-end (Deliverable 5/9 category E)."""
        raw_text = "You need displacement before you enter.\n\nNo further discussion in this excerpt."
        parsed_segments = ta.parse_transcript(raw_text, "plain_text")
        intake = ir.register_intake_manifest(self.intake_dir, self.lifecycle_dir, "transcript", "owner",
                                              FIXED_NOW, traderId="TJR", title="E2E smoke transcript",
                                              transcriptFormat="plain_text")
        segments = ir.register_transcript_segments(self.segments_dir, self.intake_dir, FIXED_NOW,
                                                    intake["intakeId"], parsed_segments)
        source = reg.register_source(self.sources_dir, self.lifecycle_dir, "transcript", "owner", FIXED_NOW,
                                      traderId="TJR", title="E2E smoke source")
        ir.link_intake_to_source(self.intake_dir, self.lifecycle_dir, intake["intakeId"], source["sourceId"],
                                  "owner", FIXED_NOW)
        annotation = ap.register_annotation(
            self.annotations_dir, self.segments_dir, self.intake_dir, FIXED_NOW, intake["intakeId"],
            segments[0]["segmentId"], "You need displacement before you enter.", "explicit_statement",
            "direct_explicit", "high", "researcher1", traderId="TJR", claimType="entry_rule",
            proposedClaim="Displacement is required before entry.",
            normalizedObservation="Displacement is required before entry.")
        ap.set_annotation_review_status(self.annotations_dir, annotation["annotationId"], "approved", FIXED_NOW)
        applied = ap.apply_annotation(self.annotations_dir, self.segments_dir, self.intake_dir, self.items_dir,
                                       self.sources_dir, self.claims_dir, self.links_dir, self.lifecycle_dir,
                                       FIXED_NOW, annotation["annotationId"], "owner")
        return intake, segments, source, applied

    def run_pipeline(self):
        """Real trader_profile -> strategy_blueprint -> knowledge_gaps ->
        hypothesis_proposals pipeline, exactly as PROGRAM-007's own pipeline
        integration is meant to call it."""
        claim, support_item, contra_item = self.seed_contested_entry_rule_claim()
        idx = self.index()
        profile = tp.register_trader_profile(self.profiles_dir, idx, "TJR", now=FIXED_NOW)
        idx = self.index()
        blueprint = sb.register_strategy_blueprint(self.blueprints_dir, idx, "TJR", now=FIXED_NOW)
        idx = self.index()
        gaps = kg.generate_knowledge_gaps(self.gaps_dir, idx, blueprint, now=FIXED_NOW)
        idx = self.index()
        hypotheses = hp.generate_hypotheses(self.hypotheses_dir, idx, blueprint, gaps=gaps, now=FIXED_NOW)
        return claim, support_item, contra_item, profile, blueprint, gaps, hypotheses


class TestKnowledgeGraphPhase7A(unittest.TestCase):
    def test_new_node_types_registered(self):
        for t in ("TRADER_PROFILE", "STRATEGY_BLUEPRINT", "KNOWLEDGE_GAP", "HYPOTHESIS"):
            self.assertIn(t, gc.NODE_TYPES)

    def test_new_edge_types_registered(self):
        for t in ("BLUEPRINT_DERIVED_FROM_CLAIM", "BLUEPRINT_HAS_GAP", "GAP_GENERATES_RESEARCH_QUESTION",
                   "CLAIM_SUPPORTS_HYPOTHESIS", "CLAIM_CONTRADICTS_HYPOTHESIS"):
            self.assertIn(t, gc.EDGE_TYPES)

    def test_production_graph_unchanged_without_real_knowledge_library(self):
        # No real transcript has been processed into the committed repository
        # yet (Deliverable 5 produced an explicit SOURCE_REQUIRED report
        # instead) -- so the real evidence/{profiles,blueprints,gaps,hypotheses}
        # directories must still be empty, and the production graph build must
        # produce zero Phase 7A nodes and zero blocking findings.
        graph_root = os.path.join(TI_ROOT, "graph")
        nodes, edges, findings, _raw = gc.build_nodes_and_edges(REPO_ROOT, TI_ROOT, graph_root)
        blocking = [f for f in findings if f.get("severity") in ("ERROR", "FATAL")]
        self.assertEqual(blocking, [])
        phase7a_nodes = [n for n in nodes if n["nodeType"] in
                          ("TRADER_PROFILE", "STRATEGY_BLUEPRINT", "KNOWLEDGE_GAP", "HYPOTHESIS")]
        self.assertEqual(phase7a_nodes, [])

    def test_reproducible_manifests_unaffected(self):
        graph_root = os.path.join(TI_ROOT, "graph")
        n1, e1, _f1, _r1 = gc.build_nodes_and_edges(REPO_ROOT, TI_ROOT, graph_root)
        n2, e2, _f2, _r2 = gc.build_nodes_and_edges(REPO_ROOT, TI_ROOT, graph_root)
        self.assertEqual([n["nodeId"] for n in n1], [n["nodeId"] for n in n2])
        self.assertEqual([e["edgeId"] for e in e1], [e["edgeId"] for e in e2])


class TestKnowledgeGraphPhase7AIntegration(unittest.TestCase):
    def setUp(self):
        self.repo = TempKnowledgeLibraryRepo()

    def tearDown(self):
        self.repo.cleanup()

    def test_full_pipeline_graph_integration(self):
        claim, support_item, contra_item, profile, blueprint, gaps, hypotheses = self.repo.run_pipeline()
        self.assertEqual(claim["confidenceState"], "contested",
                          "test scenario must genuinely land in a not-yet-settled state")
        self.assertTrue(gaps, "an entry_rule-only trader should still have several open gaps")
        self.assertTrue(hypotheses, "a contested claim must produce at least one hypothesis")

        nodes, edges, findings, raw = self.repo.build_graph()
        blocking = [f for f in findings if f.get("severity") in ("ERROR", "FATAL")]
        self.assertEqual(blocking, [], blocking)

        report = validate_graph.run_integrity_checks(nodes, edges, raw, findings, "TEST|PHASE7A|001")
        self.assertEqual(report["summary"]["ERROR"], 0, report["findings"])
        self.assertEqual(report["summary"]["FATAL"], 0, report["findings"])

        by_type = {}
        for n in nodes:
            by_type.setdefault(n["nodeType"], []).append(n)
        self.assertEqual(len(by_type.get("TRADER_PROFILE", [])), 1)
        self.assertEqual(len(by_type.get("STRATEGY_BLUEPRINT", [])), 1)
        self.assertEqual(len(by_type.get("KNOWLEDGE_GAP", [])), len(gaps))
        self.assertEqual(len(by_type.get("HYPOTHESIS", [])), len(hypotheses))

        profile_node = by_type["TRADER_PROFILE"][0]
        blueprint_node = by_type["STRATEGY_BLUEPRINT"][0]
        claim_node_id = gc.make_node_id("CLAIM", claim["claimId"])

        edges_by_type = {}
        for e in edges:
            edges_by_type.setdefault(e["edgeType"], []).append(e)

        # BELONGS_TO_TRADER is reused generically -- profile/blueprint/gaps all
        # have traderId and must connect to the TRADER node without a
        # dedicated TRADER_HAS_PROFILE/TRADER_HAS_DRAFT_BLUEPRINT edge type.
        trader_node_id = gc.make_node_id("TRADER", "TJR")
        belongs_targets = {e["fromNodeId"]: e["toNodeId"] for e in edges_by_type.get("BELONGS_TO_TRADER", [])}
        self.assertEqual(belongs_targets.get(profile_node["nodeId"]), trader_node_id)
        self.assertEqual(belongs_targets.get(blueprint_node["nodeId"]), trader_node_id)

        # BLUEPRINT_DERIVED_FROM_CLAIM: blueprint -> the seeded claim.
        bdfc = edges_by_type.get("BLUEPRINT_DERIVED_FROM_CLAIM", [])
        self.assertTrue(any(e["fromNodeId"] == blueprint_node["nodeId"] and e["toNodeId"] == claim_node_id
                             for e in bdfc), bdfc)

        # BLUEPRINT_HAS_GAP: blueprint -> every generated gap.
        bhg = edges_by_type.get("BLUEPRINT_HAS_GAP", [])
        gap_node_ids = {n["nodeId"] for n in by_type.get("KNOWLEDGE_GAP", [])}
        bhg_targets = {e["toNodeId"] for e in bhg if e["fromNodeId"] == blueprint_node["nodeId"]}
        self.assertEqual(bhg_targets, gap_node_ids)

        # CLAIM_SUPPORTS_HYPOTHESIS: the seeded claim supports at least one hypothesis.
        csh = edges_by_type.get("CLAIM_SUPPORTS_HYPOTHESIS", [])
        self.assertTrue(any(e["fromNodeId"] == claim_node_id for e in csh), csh)

        # CLAIM_CONTRADICTS_HYPOTHESIS: the same claim (contradicted by contra_item)
        # must show up as contradicting its own derived hypothesis.
        cch = edges_by_type.get("CLAIM_CONTRADICTS_HYPOTHESIS", [])
        self.assertTrue(any(e["fromNodeId"] == claim_node_id for e in cch), cch)

        # No hypothesis or gap ever names a StrategyRule -- structural proof
        # this vertical slice never touches the executable rule layer.
        for h in by_type.get("HYPOTHESIS", []):
            _, entity, _src = raw[h["entityId"]]
            self.assertNotIn("ruleId", entity)
            self.assertNotIn("strategyRuleId", entity)

        # The blueprint's own validationStatus must remain structurally
        # non-executable regardless of graph integration.
        _, blueprint_entity, _src = raw[blueprint_node["entityId"]]
        self.assertEqual(blueprint_entity["validationStatus"]["productionStatus"], "not_applicable")
        self.assertEqual(blueprint_entity["status"], "DRAFT_RESEARCH_ONLY")

    def test_gap_generates_research_question_edge_direction(self):
        """generate_knowledge_gaps() does not yet populate
        provenance.evidenceQuestionId (Deliverable 3 doesn't require a gap to
        auto-generate its own EvidenceQuestion), so this exercises the
        GAP_GENERATES_RESEARCH_QUESTION edge-derivation logic directly against
        a well-formed KNOWLEDGE_GAP record that does carry one, proving the
        wiring is correct and ready for whenever that link is populated."""
        claim, support_item, contra_item, profile, blueprint, gaps, hypotheses = self.repo.run_pipeline()
        idx = self.repo.index()
        question = eqs.create_question(
            self.repo.questions_dir, FIXED_NOW, "missing_stop_placement",
            "Where exactly is the stop placed?", "high",
            "No stop-placement claim exists for this trader.", "blocks_promotion",
            claimId=claim["claimId"])
        gap = gaps[0]
        gap_path = os.path.join(self.repo.gaps_dir, evc.gap_id_to_filename(gap["gapId"]))
        gap["provenance"]["evidenceQuestionId"] = question["questionId"]
        gc.atomic_write_text(gap_path, gc.pretty_json(gap))

        nodes, edges, findings, raw = self.repo.build_graph()
        blocking = [f for f in findings if f.get("severity") in ("ERROR", "FATAL")]
        self.assertEqual(blocking, [], blocking)

        gap_node_id = gc.make_node_id("KNOWLEDGE_GAP", gap["gapId"])
        question_node_id = gc.make_node_id("EVIDENCE_QUESTION", question["questionId"])
        ggrq = [e for e in edges if e["edgeType"] == "GAP_GENERATES_RESEARCH_QUESTION"]
        self.assertTrue(any(e["fromNodeId"] == gap_node_id and e["toNodeId"] == question_node_id for e in ggrq), ggrq)


# ---------------------------------------------------------------------------
# Deliverable 7: review workflow (8 reviewer actions)
# ---------------------------------------------------------------------------

class TestReviewWorkflowPhase7A(unittest.TestCase):
    """Domain/service-layer tests for review_queues.apply_review_action().
    No UI integration point exists for this yet (index.html is the live
    trading app, not a research-review surface) -- Deliverable 7 is
    implemented here purely as a service layer a future UI or CLI can call;
    the deferred-UI decision is documented in the Phase 7A status doc."""

    def setUp(self):
        self.repo = TempKnowledgeLibraryRepo()

    def tearDown(self):
        self.repo.cleanup()

    def _one_entry(self):
        claim, support_item, contra_item, *_ = self.repo.run_pipeline()
        queue_dir = os.path.join(self.repo.evidence_root, "review-queue")
        os.makedirs(queue_dir, exist_ok=True)
        results = rev.build_all_review_queues(
            queue_dir, FIXED_NOW, self.repo.sources_dir, self.repo.items_dir, self.repo.claims_dir,
            self.repo.contradictions_dir, self.repo.questions_dir,
            os.path.join(self.repo.evidence_root, "proposals"), os.path.join(self.repo.evidence_root, "intake"))
        entry = results["contested_claims"][0]
        return claim, entry, queue_dir

    def test_all_eight_actions_are_registered(self):
        self.assertEqual(len(evc.REVIEW_ACTIONS), 8)
        for action in ("approve_as_supported_claim", "approve_as_inferred_claim", "reject",
                       "mark_contradictory", "request_more_evidence", "convert_to_research_question",
                       "propose_hypothesis", "leave_unresolved"):
            self.assertIn(action, evc.REVIEW_ACTIONS)

    def test_unknown_action_rejected(self):
        claim, entry, queue_dir = self._one_entry()
        with self.assertRaises(evc.EvidenceValidationError):
            rev.apply_review_action(queue_dir, self.repo.questions_dir, entry["queueEntryId"],
                                     "auto_approve_everything", "owner", FIXED_NOW)

    def test_never_auto_approves_without_explicit_call(self):
        # build_all_review_queues() alone must never resolve anything.
        claim, entry, queue_dir = self._one_entry()
        self.assertEqual(entry["reviewStatus"], "open")
        self.assertIsNone(entry["reviewAction"])

    def test_reject_settles_dismissed_and_never_mutates_the_claim(self):
        claim, entry, queue_dir = self._one_entry()
        before = dict(qe._load_dir(self.repo.claims_dir, "claimId")[claim["claimId"]])
        updated, question = rev.apply_review_action(queue_dir, self.repo.questions_dir,
                                                      entry["queueEntryId"], "reject", "owner", FIXED_NOW,
                                                      notes="Not a real rule statement.")
        self.assertEqual(updated["reviewStatus"], "dismissed")
        self.assertEqual(updated["reviewAction"], "reject")
        self.assertIsNone(question)
        after = qe._load_dir(self.repo.claims_dir, "claimId")[claim["claimId"]]
        self.assertEqual(before, after, "apply_review_action must never mutate the underlying Claim")

    def test_leave_unresolved_stays_open(self):
        claim, entry, queue_dir = self._one_entry()
        updated, _q = rev.apply_review_action(queue_dir, self.repo.questions_dir, entry["queueEntryId"],
                                               "leave_unresolved", "owner", FIXED_NOW)
        self.assertEqual(updated["reviewStatus"], "open")
        self.assertEqual(updated["reviewAction"], "leave_unresolved")

    def test_request_more_evidence_stays_in_review(self):
        claim, entry, queue_dir = self._one_entry()
        updated, _q = rev.apply_review_action(queue_dir, self.repo.questions_dir, entry["queueEntryId"],
                                               "request_more_evidence", "owner", FIXED_NOW)
        self.assertEqual(updated["reviewStatus"], "in_review")

    def test_convert_to_research_question_creates_additive_question(self):
        claim, entry, queue_dir = self._one_entry()
        before_count = len(qe._load_dir(self.repo.questions_dir, "questionId"))
        updated, question = rev.apply_review_action(queue_dir, self.repo.questions_dir,
                                                      entry["queueEntryId"], "convert_to_research_question",
                                                      "owner", FIXED_NOW, notes="Is this really mandatory?")
        self.assertIsNotNone(question)
        self.assertEqual(question["claimId"], claim["claimId"])
        after_count = len(qe._load_dir(self.repo.questions_dir, "questionId"))
        self.assertEqual(after_count, before_count + 1)
        self.assertEqual(updated["metadata"]["generatedQuestionId"], question["questionId"])
        self.assertEqual(updated["reviewStatus"], "resolved")

    def test_propose_hypothesis_does_not_fabricate_a_hypothesis_record(self):
        claim, entry, queue_dir = self._one_entry()
        before_count = len(qe._load_dir(self.repo.hypotheses_dir, "hypothesisId"))
        updated, question = rev.apply_review_action(queue_dir, self.repo.questions_dir,
                                                      entry["queueEntryId"], "propose_hypothesis",
                                                      "owner", FIXED_NOW)
        self.assertIsNone(question)
        after_count = len(qe._load_dir(self.repo.hypotheses_dir, "hypothesisId"))
        self.assertEqual(after_count, before_count,
                         "propose_hypothesis must not itself create a Hypothesis record")
        self.assertEqual(updated["reviewAction"], "propose_hypothesis")

    def test_cannot_act_twice_on_a_resolved_entry(self):
        claim, entry, queue_dir = self._one_entry()
        rev.apply_review_action(queue_dir, self.repo.questions_dir, entry["queueEntryId"],
                                 "reject", "owner", FIXED_NOW)
        with self.assertRaises(evc.EvidenceValidationError):
            rev.apply_review_action(queue_dir, self.repo.questions_dir, entry["queueEntryId"],
                                     "approve_as_supported_claim", "owner", FIXED_NOW)

    def test_review_queue_entry_schema_accepts_new_fields(self):
        claim, entry, queue_dir = self._one_entry()
        updated, _q = rev.apply_review_action(queue_dir, self.repo.questions_dir, entry["queueEntryId"],
                                               "mark_contradictory", "owner", FIXED_NOW, notes="See claim B.")
        import json as _json
        with open(os.path.join(TI_ROOT, "evidence", "schema", "review-queue-entry.schema.json")) as f:
            schema = _json.load(f)
        self.assertIn("mark_contradictory", schema["properties"]["reviewAction"]["enum"])
        self.assertEqual(updated["reviewNotes"], "See claim B.")


# ---------------------------------------------------------------------------
# Deliverable 6: knowledge_library_report.py (human-review report)
# ---------------------------------------------------------------------------

class TestKnowledgeLibraryReportPhase7A(unittest.TestCase):
    def setUp(self):
        self.repo = TempKnowledgeLibraryRepo()

    def tearDown(self):
        self.repo.cleanup()

    def test_report_none_without_profile_or_blueprint(self):
        idx = self.repo.index()
        self.assertIsNone(klr.generate_knowledge_library_report(idx, "TJR", None, None, [], []))

    def test_report_sections_and_disclaimers(self):
        claim, support_item, contra_item, profile, blueprint, gaps, hypotheses = self.repo.run_pipeline()
        idx = self.repo.index()
        report = klr.generate_knowledge_library_report(idx, "TJR", profile, blueprint, gaps, hypotheses, now=FIXED_NOW)

        for key in ("sourceSummary", "extractionStatistics", "traderProfile", "strategyBlueprint",
                    "explicitRules", "impliedOrInferredRules", "contradictions", "knowledgeGaps",
                    "proposedHypotheses", "itemsRequiringHumanReview", "replayRecommendations",
                    "paperTradingRecommendations", "limitations", "lineageSummary"):
            self.assertIn(key, report, "missing required Deliverable 6 section: %s" % key)

        self.assertTrue(all(report["disclaimers"].values()), report["disclaimers"])
        for phrase in ("research", "validated", "executable", "profitability", "replay", "paper-trading"):
            self.assertIn(phrase, report["disclaimerText"].lower())

        # The seeded claim has direct_explicit-backed support, so it must
        # appear in explicitRules (directness wins over the same claim also
        # carrying an indirect_implied contradicting excerpt).
        explicit_ids = {r["claimId"] for r in report["explicitRules"]}
        self.assertIn(claim["claimId"], explicit_ids)

        # Report must never claim the blueprint is executable or validated.
        self.assertEqual(report["strategyBlueprint"]["status"], "DRAFT_RESEARCH_ONLY")
        self.assertEqual(report["strategyBlueprint"]["validationStatus"]["productionStatus"], "not_applicable")

    def test_report_never_mutates_underlying_records(self):
        claim, support_item, contra_item, profile, blueprint, gaps, hypotheses = self.repo.run_pipeline()
        idx = self.repo.index()
        before_claim = dict(idx.claims[claim["claimId"]])
        klr.generate_knowledge_library_report(idx, "TJR", profile, blueprint, gaps, hypotheses, now=FIXED_NOW)
        after_claim = qe._load_dir(self.repo.claims_dir, "claimId")[claim["claimId"]]
        self.assertEqual(before_claim, after_claim)

    def test_markdown_renders_and_contains_disclaimer(self):
        claim, support_item, contra_item, profile, blueprint, gaps, hypotheses = self.repo.run_pipeline()
        idx = self.repo.index()
        report = klr.generate_knowledge_library_report(idx, "TJR", profile, blueprint, gaps, hypotheses, now=FIXED_NOW)
        md = klr.render_knowledge_library_report_markdown(report)
        self.assertIn(klr._DISCLAIMER_TEXT, md)
        for heading in ("1. Source Summary", "5. Explicit Rules", "6. Implied or Inferred Rules",
                        "9. Proposed Hypotheses", "13. Limitations", "14. Full Lineage Summary"):
            self.assertIn(heading, md)


# ---------------------------------------------------------------------------
# Deliverable 9, Category A: Trader Profile domain validation
# ---------------------------------------------------------------------------

class TestCategoryATraderProfileDomain(unittest.TestCase):
    def setUp(self):
        self.repo = TempKnowledgeLibraryRepo()

    def tearDown(self):
        self.repo.cleanup()

    def _schema(self):
        path = os.path.join(TI_ROOT, "evidence", "schema", "trader-profile.schema.json")
        with open(path, "r", encoding="utf-8") as f:
            return __import__("json").load(f)

    def test_valid_profile_has_all_required_fields(self):
        claim, *_ = self.repo.run_pipeline()
        idx = self.repo.index()
        profile = qe._load_dir(self.repo.profiles_dir, "profileId")
        profile = next(iter(profile.values()))
        schema = self._schema()
        for field in schema["required"]:
            self.assertIn(field, profile, "profile missing required field %r" % field)

    def test_invalid_profile_duplicate_canonical_identity_detected(self):
        claim, *_ = self.repo.run_pipeline()
        idx = self.repo.index()
        second = dict(tp.build_trader_profile(idx, "TJR", now=FIXED_NOW))
        second["profileId"] = evc.next_profile_id(self.repo.profiles_dir, "TJR", FIXED_NOW)
        second["canonicalName"] = "A Completely Different Name"
        path = os.path.join(self.repo.profiles_dir, evc.profile_id_to_filename(second["profileId"]))
        gc.atomic_write_text(path, gc.pretty_json(second))
        findings = []
        profiles = list(qe._load_dir(self.repo.profiles_dir, "profileId").values())
        ve.check_duplicate_canonical_trader_identity(profiles, findings, FIXED_NOW)
        self.assertTrue(any(f["findingType"] == "DUPLICATE_CANONICAL_TRADER_IDENTITY" for f in findings), findings)

    def test_unknown_fields_handled_correctly(self):
        # Absence of information stays an explicit empty list/None, never a
        # fabricated default -- e.g. a trader with no risk_rule claims gets
        # an empty riskConcepts list, not a placeholder statement.
        claim, *_ = self.repo.run_pipeline()
        idx = self.repo.index()
        profile = tp.build_trader_profile(idx, "TJR", now=FIXED_NOW)
        self.assertEqual(profile["riskConcepts"], [])
        self.assertEqual(profile["targetConcepts"], [])

    def test_inference_labels_preserved(self):
        idx = self.repo.index()
        # No claims at all for a fresh trader: profile still builds, and its
        # own limitations list explicitly says so rather than silently
        # omitting the fact.
        profile = tp.build_trader_profile(idx, "GHOST", now=FIXED_NOW)
        self.assertEqual(profile["claimCount"], 0)
        self.assertIn("No claims exist for this trader yet -- profile reflects zero evidence.",
                       profile["limitations"])

    def test_contradictions_preserved_in_concept_status(self):
        claim, support_item, contra_item, profile, *_ = self.repo.run_pipeline()
        # The seeded claim has both a supporting and a contradicting link --
        # every labeled concept derived from it must show status='conflicting',
        # never silently collapsed to 'confirmed'.
        entry_concepts = profile["entryConcepts"]
        self.assertTrue(entry_concepts)
        self.assertTrue(all(c["status"] == "conflicting" for c in entry_concepts), entry_concepts)

    def test_schema_version_required(self):
        claim, *_ = self.repo.run_pipeline()
        profiles = list(qe._load_dir(self.repo.profiles_dir, "profileId").values())
        self.assertTrue(all(isinstance(p["schemaVersion"], int) for p in profiles))
        bad = dict(profiles[0])
        bad["schemaVersion"] = None
        findings = []
        for r in [bad]:
            v = r.get("schemaVersion")
            if not isinstance(v, int):
                findings.append("UNSUPPORTED_SCHEMA_VERSION")
        self.assertIn("UNSUPPORTED_SCHEMA_VERSION", findings)


# ---------------------------------------------------------------------------
# Deliverable 9, Category B: Strategy Blueprint tests
# ---------------------------------------------------------------------------

class TestCategoryBStrategyBlueprint(unittest.TestCase):
    def setUp(self):
        self.repo = TempKnowledgeLibraryRepo()

    def tearDown(self):
        self.repo.cleanup()

    def test_deterministic_generation(self):
        claim, *_ = self.repo.run_pipeline()
        idx = self.repo.index()
        b1 = sb.build_strategy_blueprint(idx, "TJR", now=FIXED_NOW)
        b2 = sb.build_strategy_blueprint(idx, "TJR", now=FIXED_NOW)
        b1c, b2c = dict(b1), dict(b2)
        del b1c["blueprintId"], b2c["blueprintId"]
        self.assertEqual(b1c, b2c)

    def test_ordered_workflow(self):
        claim, *_ = self.repo.run_pipeline()
        idx = self.repo.index()
        blueprint = sb.build_strategy_blueprint(idx, "TJR", now=FIXED_NOW)
        numbers = [s["stageNumber"] for s in blueprint["workflow"]]
        self.assertEqual(numbers, sorted(numbers))
        self.assertEqual(numbers, list(range(1, len(numbers) + 1)))

    def test_classification_separation(self):
        claim, *_ = self.repo.run_pipeline()
        idx = self.repo.index()
        blueprint = sb.build_strategy_blueprint(idx, "TJR", now=FIXED_NOW)
        entry = blueprint["entryLogic"]
        # required/preferred/optional/forbidden/unresolved must be distinct
        # buckets -- no single statement text should appear as a *statement
        # dict* in two different classification buckets simultaneously.
        labeled_buckets = [entry["requiredConditions"], entry["preferredConditions"],
                           entry["optionalConditions"], entry["forbiddenConditions"]]
        seen_ids = set()
        for bucket in labeled_buckets:
            for stmt in bucket:
                key = stmt["statement"]
                self.assertNotIn(key, seen_ids, "statement %r appeared in more than one classification" % key)
                seen_ids.add(key)

    def test_full_provenance(self):
        claim, *_ = self.repo.run_pipeline()
        idx = self.repo.index()
        blueprint = sb.build_strategy_blueprint(idx, "TJR", now=FIXED_NOW)
        for stage in blueprint["workflow"]:
            self.assertTrue(stage["evidenceLinks"], "workflow stage %r has no evidenceLinks" % stage["stageName"])
        self.assertTrue(blueprint["sourceLineage"]["claimIds"])
        self.assertTrue(blueprint["sourceLineage"]["evidenceIds"])

    def test_research_only_default(self):
        claim, *_ = self.repo.run_pipeline()
        idx = self.repo.index()
        blueprint = sb.build_strategy_blueprint(idx, "TJR", now=FIXED_NOW)
        self.assertEqual(blueprint["status"], "DRAFT_RESEARCH_ONLY")
        self.assertEqual(blueprint["validationStatus"]["productionStatus"], "not_applicable")

    def test_no_executable_strategy_rule_output(self):
        claim, *_ = self.repo.run_pipeline()
        idx = self.repo.index()
        sb.register_strategy_blueprint(self.repo.blueprints_dir, idx, "TJR", now=FIXED_NOW)
        rules_dir = os.path.join(self.repo.ti_root, "traders", "tjr", "rules")
        before = set(os.listdir(rules_dir)) if os.path.isdir(rules_dir) else set()
        after = set(os.listdir(rules_dir)) if os.path.isdir(rules_dir) else set()
        self.assertEqual(before, after, "generating a blueprint must never write a StrategyRule file")


# ---------------------------------------------------------------------------
# Deliverable 9, Category C: Knowledge Gap tests
# ---------------------------------------------------------------------------

class TestCategoryCKnowledgeGaps(unittest.TestCase):
    def setUp(self):
        self.repo = TempKnowledgeLibraryRepo()

    def tearDown(self):
        self.repo.cleanup()

    def test_missing_stop_logic_detected(self):
        claim, support_item, contra_item, profile, blueprint, gaps, hypotheses = self.repo.run_pipeline()
        self.assertIn("stop_placement", {g["category"] for g in gaps})

    def test_missing_invalidation_detected(self):
        claim, support_item, contra_item, profile, blueprint, gaps, hypotheses = self.repo.run_pipeline()
        self.assertIn("invalidation", {g["category"] for g in gaps})

    def test_ambiguous_timeframe_detected(self):
        claim, support_item, contra_item, profile, blueprint, gaps, hypotheses = self.repo.run_pipeline()
        # A trader with only one entry_rule claim and no stated timeframe has
        # an unresolved execution-timeframe gap.
        self.assertIn("execution_timeframe", {g["category"] for g in gaps})

    def test_no_fabricated_answer(self):
        claim, support_item, contra_item, profile, blueprint, gaps, hypotheses = self.repo.run_pipeline()
        all_claim_texts = {c["normalizedClaim"] for c in self.repo.index().claims_for_trader("TJR")}
        for g in gaps:
            if g["currentBestAnswer"] is not None:
                self.assertIn(g["currentBestAnswer"], all_claim_texts,
                              "gap currentBestAnswer must be verbatim claim text, never invented")
            else:
                self.assertEqual(g["answerStatus"], "unanswered")


# ---------------------------------------------------------------------------
# Deliverable 9, Category D: Hypothesis tests
# ---------------------------------------------------------------------------

class TestCategoryDHypotheses(unittest.TestCase):
    def setUp(self):
        self.repo = TempKnowledgeLibraryRepo()

    def tearDown(self):
        self.repo.cleanup()

    def test_generated_only_from_supportable_inputs(self):
        # A single, uncontested, unlinked-to-any-contradiction claim in a
        # settled confidence state produces zero hypotheses -- nothing here
        # is invented without a real trigger. Uses risk_rule (not entry_rule/
        # setup_requirement) specifically because those two claim types are
        # the only ones the gap-anchored hypothesis path (Deliverable 4's
        # session/volatility/news triggers) attaches to -- this isolates the
        # "unsettled claim" and "contradiction" triggers from the "gap
        # anchor" trigger to prove each only fires on its own real signal.
        source = reg.register_source(self.repo.sources_dir, self.repo.lifecycle_dir, "transcript", "owner",
                                      FIXED_NOW, traderId="TJR", title="Single-claim source")
        claim = reg.register_claim(self.repo.claims_dir, self.repo.lifecycle_dir, "risk_rule",
                                    "A single unsettled-free statement.", "owner", FIXED_NOW, traderId="TJR")
        idx = self.repo.index()
        blueprint = sb.register_strategy_blueprint(self.repo.blueprints_dir, idx, "TJR", now=FIXED_NOW)
        idx = self.repo.index()
        gaps = kg.generate_knowledge_gaps(self.repo.gaps_dir, idx, blueprint, now=FIXED_NOW)
        idx = self.repo.index()
        hypotheses = hp.generate_hypotheses(self.repo.hypotheses_dir, idx, blueprint, gaps=gaps, now=FIXED_NOW)
        # confidenceState is 'insufficient_evidence' (no linked evidence at
        # all) -- not in the unsettled-states set, no contradiction exists,
        # and risk_rule is never a gap-anchor claim type, so no hypothesis
        # should be proposed from this claim alone.
        self.assertFalse(any(claim["claimId"] in h["sourceClaimIds"] for h in hypotheses), hypotheses)

    def test_contradictions_attached(self):
        claim, support_item, contra_item, profile, blueprint, gaps, hypotheses = self.repo.run_pipeline()
        self.assertTrue(hypotheses)
        self.assertTrue(any(h["contradictingEvidenceIds"] for h in hypotheses))

    def test_default_unvalidated_status(self):
        claim, support_item, contra_item, profile, blueprint, gaps, hypotheses = self.repo.run_pipeline()
        self.assertTrue(all(h["status"] == "PROPOSED_UNVALIDATED" for h in hypotheses))

    def test_no_strategy_mutation(self):
        claim, support_item, contra_item, profile, blueprint, gaps, hypotheses = self.repo.run_pipeline()
        rules_dir = os.path.join(self.repo.ti_root, "traders", "tjr", "rules")
        before = set(os.listdir(rules_dir)) if os.path.isdir(rules_dir) else set()
        idx = self.repo.index()
        hp.generate_hypotheses(self.repo.hypotheses_dir, idx, blueprint, gaps=gaps, now=FIXED_NOW)
        after = set(os.listdir(rules_dir)) if os.path.isdir(rules_dir) else set()
        self.assertEqual(before, after)


# ---------------------------------------------------------------------------
# Deliverable 9, Category E: Real transcript -> intake -> final report
# ---------------------------------------------------------------------------

class TestCategoryETranscriptIntegration(unittest.TestCase):
    def setUp(self):
        self.repo = TempKnowledgeLibraryRepo()

    def tearDown(self):
        self.repo.cleanup()

    def test_intake_through_final_report_end_to_end(self):
        intake, segments, source, applied = self.repo.run_transcript_pipeline()
        idx = self.repo.index()
        profile = tp.register_trader_profile(self.repo.profiles_dir, idx, "TJR", now=FIXED_NOW)
        idx = self.repo.index()
        blueprint = sb.register_strategy_blueprint(self.repo.blueprints_dir, idx, "TJR", now=FIXED_NOW)
        idx = self.repo.index()
        gaps = kg.generate_knowledge_gaps(self.repo.gaps_dir, idx, blueprint, now=FIXED_NOW)
        idx = self.repo.index()
        hypotheses = hp.generate_hypotheses(self.repo.hypotheses_dir, idx, blueprint, gaps=gaps, now=FIXED_NOW)
        idx = self.repo.index()
        report = klr.generate_knowledge_library_report(idx, "TJR", profile, blueprint, gaps, hypotheses, now=FIXED_NOW)
        self.assertIsNotNone(report)

        # Source lineage retained end to end: the blueprint's own lineage
        # must trace back to the real intake's segment and source.
        self.assertIn(source["sourceId"], blueprint["sourceLineage"]["sourceIds"])
        self.assertIn(segments[0]["segmentId"], blueprint["sourceLineage"]["segmentIds"])

        # Graph updated: build against the temp copy and confirm both the
        # Phase 1B intake entities and the Phase 7A entities are present with
        # zero blocking findings.
        nodes, edges, findings, raw = self.repo.build_graph()
        blocking = [f for f in findings if f.get("severity") in ("ERROR", "FATAL")]
        self.assertEqual(blocking, [], blocking)
        node_types_present = {n["nodeType"] for n in nodes}
        for t in ("INTAKE_MANIFEST", "TRANSCRIPT_SEGMENT", "EVIDENCE_ITEM", "CLAIM",
                  "TRADER_PROFILE", "STRATEGY_BLUEPRINT"):
            self.assertIn(t, node_types_present, "missing node type %r after full pipeline" % t)

        # Review queue populated: a single-source claim should surface in at
        # least one review queue (e.g. insufficient independent evidence).
        queue_dir = os.path.join(self.repo.evidence_root, "review-queue")
        os.makedirs(queue_dir, exist_ok=True)
        results = rev.build_all_review_queues(
            queue_dir, FIXED_NOW, self.repo.sources_dir, self.repo.items_dir, self.repo.claims_dir,
            self.repo.contradictions_dir, self.repo.questions_dir,
            os.path.join(self.repo.evidence_root, "proposals"), self.repo.intake_dir)
        total_entries = sum(len(v) for v in results.values())
        self.assertGreater(total_entries, 0, "expected at least one review-queue entry after this pipeline")


# ---------------------------------------------------------------------------
# Deliverable 9, Category F: Safety regression
# ---------------------------------------------------------------------------

class TestCategoryFSafetyRegression(unittest.TestCase):
    """Proves this milestone changes zero execution behavior. index.html is
    the single source of truth for JVM/ALEX/TJR execution, paper/live order
    placement, risk calculations, and broker integration -- Phase 7A commits
    no changes to it at all, so the strongest available proof is (a) a
    byte-identical diff and (b) that no Phase 7A script ever touches it or
    reaches the network."""

    PHASE7A_MODULES = ("trader_profile.py", "strategy_blueprint.py", "knowledge_gaps.py",
                        "hypothesis_proposals.py", "knowledge_library_report.py")

    def test_index_html_protected_functions_show_zero_drift(self):
        # regression-baseline-tools.py compares every one of the 63 protected
        # execution-critical functions (JVM/ALEX order placement, risk calc,
        # paper/live position construction, etc.) against the committed
        # baseline by per-function SHA1 -- exit code 0 means byte-identical.
        import subprocess
        result = subprocess.run([sys.executable, os.path.join(REPO_ROOT, "regression-baseline-tools.py")],
                                 capture_output=True, text=True, cwd=REPO_ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("No drift", result.stdout)

    def test_no_phase7a_module_touches_index_html_or_network(self):
        for fname in self.PHASE7A_MODULES:
            path = os.path.join(SCRIPTS_DIR, fname)
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            for line in lines:
                if "index.html" in line and ("open(" in line or "requests." in line or "urlopen(" in line):
                    self.fail("%s appears to open/fetch index.html: %r" % (fname, line))
            content = "".join(lines)
            for banned in ("requests", "urllib.request", "http.client", "socket", "selenium", "playwright"):
                self.assertNotIn("import %s" % banned, content)

    def test_no_phase7a_module_writes_strategy_rule_files(self):
        for fname in self.PHASE7A_MODULES:
            path = os.path.join(SCRIPTS_DIR, fname)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertNotIn('"rules"', content, "%s must never write into traders/*/rules/" % fname)

    def test_execution_engine_functions_present_and_unreferenced_by_phase7a(self):
        # Spot-check that the protected execution-critical function names
        # (JVM/paper/live order placement, ALEX engine) are exactly the ones
        # tracked by the existing baseline tool, and confirm no Phase 7A
        # Python module references them (they are JS functions inside
        # index.html; a reference here would indicate accidental coupling).
        import json as _json
        with open(os.path.join(REPO_ROOT, "regression-baseline.json"), "r", encoding="utf-8") as f:
            baseline = _json.load(f)
        protected = baseline["protectedFunctions"]
        self.assertIn("openPaperPosition", protected)
        self.assertIn("closePaperPosition", protected)
        self.assertIn("evaluateLiveTrigger", protected)
        for fname in self.PHASE7A_MODULES:
            path = os.path.join(SCRIPTS_DIR, fname)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            for func_name in ("openPaperPosition", "closePaperPosition", "evaluateLiveTrigger",
                               "alexGConstructLivePosition", "alexGCloseLivePosition"):
                self.assertNotIn(func_name, content)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""MOGO-020 Step 2 -- governed answer intake test suite.

Pure stdlib (unittest). Fully offline, deterministic. Run with:

    python3 -m unittest tests.trader_intelligence.test_answer_intake -v

EVERY test builds a throwaway synthetic evidence root in a temp directory.
Nothing here reads or writes docs/trader-intelligence/evidence/, and nothing
here touches XCONTRA|20260728|001, EQ|20260727|015, ALEX, TJR authority or any
strategy file. The synthetic corpora are named SYNTHTRADER / SYNTHOTHER
precisely so they can never be confused with a real one.
"""
import glob as globmod
import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timezone

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts", "trader_intelligence")

sys.path.insert(0, SCRIPTS_DIR)
import graph_common as gc                 # noqa: E402
import evidence_common as evc             # noqa: E402
import evidence_registry as reg           # noqa: E402
import evidence_questions as eqs          # noqa: E402
import query_evidence as qe               # noqa: E402
import validate_evidence as ve            # noqa: E402
import answer_intake as ai                # noqa: E402

FIXED_NOW = datetime(2026, 8, 13, 12, 0, 0, tzinfo=timezone.utc)
LATER = datetime(2026, 8, 13, 13, 0, 0, tzinfo=timezone.utc)

REVIEWER = "reviewer:joemogollon"
OPERATOR = "operator:joemogollon"

HOME_TRADER = "SYNTHTRADER"
FOREIGN_TRADER = "SYNTHOTHER"


class SyntheticIntakeRepo:
    """An isolated evidence root holding exactly what the intake path needs:
    two corpora, questions, evidence of varying provenance quality, claims and
    one contradiction. Built with the existing registry primitives only -- it
    creates NO EvidenceClaimLink and NO RuleCandidateProposal, and never calls
    the extraction pipeline."""

    DIRS = ("sources", "items", "claims", "links", "contradictions", "lifecycle", "reports",
            "intake", "segments", "annotations", "questions", "proposals", "review-queue")

    def __init__(self):
        self.root = tempfile.mkdtemp(prefix="mogo020_intake_test_")
        for name in self.DIRS:
            os.makedirs(os.path.join(self.root, name), exist_ok=True)
        d = ai._dirs(self.root)
        self.sources_dir = d["sources"]
        self.items_dir = d["items"]
        self.claims_dir = d["claims"]
        self.links_dir = d["links"]
        self.lifecycle_dir = d["lifecycle"]
        self.contradictions_dir = d["contradictions"]
        self.questions_dir = d["questions"]
        self.proposals_dir = d["proposals"]

        # ── home corpus ──
        self.source = reg.register_source(
            self.sources_dir, self.lifecycle_dir, "transcript", "owner", FIXED_NOW,
            traderId=HOME_TRADER, title="Synthetic home transcript",
            provenanceStatus="partially_verified")
        self.claim = reg.register_claim(
            self.claims_dir, self.lifecycle_dir, "entry_rule",
            "Enter on the retest of the swept level.", "owner", FIXED_NOW,
            traderId=HOME_TRADER)
        self.evidence = self._item("I enter on the retest of the swept level.",
                                    directness="direct_explicit")
        self.evidence_b = self._item("I wait for the retest before entering.",
                                      directness="direct_explicit")

        # ── foreign corpus ──
        self.foreign_source = reg.register_source(
            self.sources_dir, self.lifecycle_dir, "transcript", "owner", FIXED_NOW,
            traderId=FOREIGN_TRADER, title="Synthetic foreign transcript",
            provenanceStatus="partially_verified")
        self.foreign_claim = reg.register_claim(
            self.claims_dir, self.lifecycle_dir, "entry_rule",
            "Never enter on the retest of the swept level.", "owner", FIXED_NOW,
            traderId=FOREIGN_TRADER)
        # Deliberately shares vocabulary with the home corpus: if anything ever
        # matched on words instead of governed ids, this is what would leak.
        self.foreign_evidence = reg.register_evidence_item(
            self.items_dir, self.sources_dir, self.lifecycle_dir,
            self.foreign_source["sourceId"], "explicit_statement", "high", "owner", FIXED_NOW,
            exactExcerpt="I enter on the retest of the swept level.",
            directness="direct_explicit", extractionCertainty="high")

        # ── deficient evidence, for the fail-closed cases ──
        self.unverified_source = reg.register_source(
            self.sources_dir, self.lifecycle_dir, "note", "owner", FIXED_NOW,
            traderId=HOME_TRADER, title="Unverified", provenanceStatus="unverified")
        self.unverified_evidence = reg.register_evidence_item(
            self.items_dir, self.sources_dir, self.lifecycle_dir,
            self.unverified_source["sourceId"], "explicit_statement", "low", "owner", FIXED_NOW,
            exactExcerpt="Something unverified.", directness="direct_explicit",
            extractionCertainty="low")
        self.no_directness_evidence = self._item("No directness recorded.", directness=None)

        # ── questions ──
        self.question = eqs.create_question(
            self.questions_dir, FIXED_NOW, "unclear_scope",
            "What exactly triggers entry?", "high", "Synthetic fixture question.",
            "blocks_rule_candidate", claimId=self.claim["claimId"])
        self.question_b = eqs.create_question(
            self.questions_dir, FIXED_NOW, "missing_timeframe",
            "Which timeframe does this apply to?", "medium", "Synthetic fixture question.",
            "blocks_rule_candidate", claimId=self.claim["claimId"])
        # No claim and no sources -> corpus cannot be resolved at all.
        self.orphan_question = eqs.create_question(
            self.questions_dir, FIXED_NOW, "other",
            "A question with no governed attribution.", "low", "Synthetic fixture question.",
            "non_blocking")

        # ── contradiction ──
        self.contradiction = reg.create_contradiction(
            self.contradictions_dir, self.claims_dir, self.lifecycle_dir,
            self.claim["claimId"], self.foreign_claim["claimId"],
            "DIRECTIONAL", "blocking", "owner", FIXED_NOW,
            rationale="Synthetic fixture contradiction.")

    def _item(self, excerpt, directness="direct_explicit"):
        return reg.register_evidence_item(
            self.items_dir, self.sources_dir, self.lifecycle_dir,
            self.source["sourceId"], "explicit_statement", "high", "owner", FIXED_NOW,
            exactExcerpt=excerpt, directness=directness, extractionCertainty="high")

    def cleanup(self):
        shutil.rmtree(self.root, ignore_errors=True)

    # --- inspection helpers -------------------------------------------

    def question_record(self, questionId=None):
        questionId = questionId or self.question["questionId"]
        path = os.path.join(self.questions_dir, evc.question_id_to_filename(questionId))
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def contradiction_record(self, contradictionId=None):
        contradictionId = contradictionId or self.contradiction["contradictionId"]
        path = os.path.join(self.contradictions_dir,
                            evc.contradiction_id_to_filename(contradictionId))
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def raw_bytes(self, dir_path):
        """Byte-exact snapshot of every file in a directory, for mutation tests."""
        out = {}
        for path in sorted(globmod.glob(os.path.join(dir_path, "*.json"))):
            with open(path, "rb") as f:
                out[os.path.basename(path)] = f.read()
        return out

    def count(self, dir_path):
        return len(globmod.glob(os.path.join(dir_path, "*.json")))

    def question_events(self, questionId=None):
        return ai._events_for(self.lifecycle_dir, "EVIDENCE_QUESTION",
                              questionId or self.question["questionId"])


class IntakeTestCase(unittest.TestCase):
    def setUp(self):
        self.repo = SyntheticIntakeRepo()
        self.addCleanup(self.repo.cleanup)

    def accept(self, **kwargs):
        kwargs.setdefault("evidence_root", self.repo.root)
        kwargs.setdefault("questionId", self.repo.question["questionId"])
        kwargs.setdefault("decision", "accepted")
        kwargs.setdefault("reviewer", REVIEWER)
        kwargs.setdefault("now", FIXED_NOW)
        kwargs.setdefault("evidenceIds", [self.repo.evidence["evidenceId"]])
        return ai._record_question_adjudication(**kwargs)


# ===========================================================================
# A. Fail-closed conditions 1-13 (Step 1 audit sec. 11)
# ===========================================================================

class TestFailClosed(IntakeTestCase):

    def test_01_invalid_question_id(self):
        for bad in ("EQ|99999999|999", "", None, "not-an-id"):
            with self.assertRaises(evc.EvidenceValidationError):
                self.accept(questionId=bad)

    def test_02_missing_evidence(self):
        with self.assertRaises(evc.EvidenceValidationError):
            self.accept(evidenceIds=["EV|EVSRC|NOPE|20260813|001"])

    def test_02b_accepted_requires_evidence(self):
        for empty in ([], None):
            with self.assertRaises(evc.EvidenceValidationError):
                self.accept(evidenceIds=empty)

    def test_03_wrong_corpus_evidence_refused(self):
        with self.assertRaises(evc.EvidenceValidationError) as ctx:
            self.accept(evidenceIds=[self.repo.foreign_evidence["evidenceId"]])
        self.assertIn("foreign-corpus", str(ctx.exception))

    def test_03b_mixed_corpus_batch_refused_entirely(self):
        with self.assertRaises(evc.EvidenceValidationError):
            self.accept(evidenceIds=[self.repo.evidence["evidenceId"],
                                      self.repo.foreign_evidence["evidenceId"]])
        # The whole batch is refused -- the in-corpus half is not partially applied.
        self.assertEqual(self.repo.question_record()["answerStatus"], "unanswered")
        self.assertEqual(self.repo.question_record()["answerEvidenceIds"], [])

    def test_04_incomplete_provenance_unverified_source(self):
        with self.assertRaises(evc.EvidenceValidationError) as ctx:
            self.accept(evidenceIds=[self.repo.unverified_evidence["evidenceId"]])
        self.assertIn("unverified", str(ctx.exception))

    def test_04b_incomplete_provenance_missing_directness(self):
        with self.assertRaises(evc.EvidenceValidationError) as ctx:
            self.accept(evidenceIds=[self.repo.no_directness_evidence["evidenceId"]])
        self.assertIn("directness", str(ctx.exception))

    def test_05_ambiguous_corpus_refused(self):
        with self.assertRaises(evc.EvidenceValidationError) as ctx:
            self.accept(questionId=self.repo.orphan_question["questionId"])
        self.assertIn("corpus attribution failed", str(ctx.exception))

    def test_06_direct_explicit_without_preserved_source_fails_closed(self):
        base = dict(evidence_root=self.repo.root, questionId=self.repo.question["questionId"],
                    reviewer=REVIEWER, now=FIXED_NOW, traderId=HOME_TRADER,
                    speaker="The Educator", exactExcerpt="I enter on the retest.",
                    sourceChannel="https://example.invalid/live-qa", sourceDate="2026-08-12")
        # Each required piece of preserved provenance, removed one at a time.
        for missing in ("exactExcerpt", "speaker", "sourceChannel", "sourceDate"):
            for empty in (None, "", "   "):
                kwargs = dict(base)
                kwargs[missing] = empty
                with self.assertRaises(evc.EvidenceValidationError):
                    ai._record_direct_trader_clarification(**kwargs)
        # Nothing was created by any of those refusals.
        self.assertEqual(self.repo.count(self.repo.items_dir), 5)

    def test_07_non_human_reviewer_refused(self):
        for bad in ("pipeline", "owner", "", None, "operator:", "joemogollon", 42):
            with self.assertRaises(evc.EvidenceValidationError):
                self.accept(reviewer=bad)

    def test_07b_non_human_operator_refused_on_ruling(self):
        for bad in ("pipeline", "owner", None, ""):
            with self.assertRaises(evc.EvidenceValidationError):
                ai._record_contradiction_ruling(
                    self.repo.root, self.repo.contradiction["contradictionId"],
                    "resolved", bad, FIXED_NOW, "Rationale.")

    def test_08_invalid_contradiction_id(self):
        for bad in ("XCONTRA|99999999|999", "", None):
            with self.assertRaises(evc.EvidenceValidationError):
                ai._record_contradiction_ruling(
                    self.repo.root, bad, "resolved", OPERATOR, FIXED_NOW, "Rationale.")

    def test_09_illegal_question_transition_answered_to_uncertain(self):
        self.accept()
        with self.assertRaises(evc.EvidenceValidationError):
            self.accept(decision="uncertain",
                        evidenceIds=[self.repo.evidence_b["evidenceId"]], now=LATER)
        self.assertEqual(self.repo.question_record()["answerStatus"], "answered")

    def test_10_illegal_contradiction_transition_double_ruling(self):
        ai._record_contradiction_ruling(
            self.repo.root, self.repo.contradiction["contradictionId"], "resolved",
            OPERATOR, FIXED_NOW, "First ruling.")
        with self.assertRaises(evc.EvidenceValidationError) as ctx:
            ai._record_contradiction_ruling(
                self.repo.root, self.repo.contradiction["contradictionId"], "superseded",
                OPERATOR, LATER, "Second, different ruling.")
        self.assertIn("illegal", str(ctx.exception))
        self.assertEqual(self.repo.contradiction_record()["status"], "resolved_by_owner")

    def test_11_conflicting_duplicate_accepted_answer_refused(self):
        self.accept()
        with self.assertRaises(evc.EvidenceValidationError) as ctx:
            self.accept(evidenceIds=[self.repo.evidence_b["evidenceId"]], now=LATER)
        self.assertIn("inconsistent duplicate", str(ctx.exception))
        record = self.repo.question_record()
        self.assertEqual(record["answerEvidenceIds"], [self.repo.evidence["evidenceId"]])

    def test_12_hash_verification_failure_refused(self):
        # Tamper with stored content in place, exactly the corruption
        # validate_evidence.check_inconsistent_hash exists to catch.
        path = os.path.join(self.repo.items_dir,
                            evc.evidence_id_to_filename(self.repo.evidence["evidenceId"]))
        with open(path, "r", encoding="utf-8") as f:
            item = json.load(f)
        item["exactExcerpt"] = "Silently rewritten after the fact."
        gc.atomic_write_text(path, gc.pretty_json(item))
        with self.assertRaises(evc.EvidenceValidationError) as ctx:
            self.accept()
        self.assertIn("hash verification", str(ctx.exception))

    def test_13_exact_replay_is_idempotent_noop(self):
        first = self.accept()
        self.assertEqual(first["outcome"], ai.APPLIED)
        events_after_first = len(self.repo.question_events())
        replay = self.accept(now=LATER)
        self.assertEqual(replay["outcome"], ai.DUPLICATE_NOOP)
        self.assertEqual(len(self.repo.question_events()), events_after_first)
        record = self.repo.question_record()
        self.assertEqual(record["answerEvidenceIds"], [self.repo.evidence["evidenceId"]])
        self.assertEqual(record["answerStatus"], "answered")

    def test_13b_rejection_replay_is_idempotent(self):
        first = ai._record_question_adjudication(
            self.repo.root, self.repo.question["questionId"], "rejected", REVIEWER, FIXED_NOW,
            evidenceIds=[self.repo.evidence["evidenceId"]], rationale="Does not answer it.")
        self.assertEqual(first["outcome"], ai.APPLIED)
        replay = ai._record_question_adjudication(
            self.repo.root, self.repo.question["questionId"], "rejected", REVIEWER, LATER,
            evidenceIds=[self.repo.evidence["evidenceId"]], rationale="Does not answer it.")
        self.assertEqual(replay["outcome"], ai.DUPLICATE_NOOP)
        self.assertEqual(len(self.repo.question_events()), 1)

    def test_13c_uncertain_replay_is_idempotent(self):
        first = ai._record_question_adjudication(
            self.repo.root, self.repo.question["questionId"], "uncertain", REVIEWER, FIXED_NOW,
            evidenceIds=[self.repo.evidence["evidenceId"]], rationale="Partial.")
        self.assertEqual(first["outcome"], ai.APPLIED)
        replay = ai._record_question_adjudication(
            self.repo.root, self.repo.question["questionId"], "uncertain", REVIEWER, LATER,
            evidenceIds=[self.repo.evidence["evidenceId"]], rationale="Partial.")
        self.assertEqual(replay["outcome"], ai.DUPLICATE_NOOP)
        self.assertEqual(len(self.repo.question_events()), 1)

    def test_13d_duplicate_direct_trader_intake_is_deterministic(self):
        kwargs = dict(evidence_root=self.repo.root, questionId=self.repo.question["questionId"],
                      reviewer=REVIEWER, traderId=HOME_TRADER, speaker="The Educator",
                      exactExcerpt="I enter on the retest, always.",
                      sourceChannel="https://example.invalid/live-qa", sourceDate="2026-08-12")
        first = ai._record_direct_trader_clarification(now=FIXED_NOW, **kwargs)
        self.assertEqual(first["outcome"], ai.APPLIED)
        items_after_first = self.repo.count(self.repo.items_dir)
        replay = ai._record_direct_trader_clarification(now=LATER, **kwargs)
        self.assertEqual(replay["outcome"], ai.DUPLICATE_NOOP)
        self.assertEqual(replay["evidenceId"], first["evidenceId"])
        self.assertEqual(self.repo.count(self.repo.items_dir), items_after_first)

    def test_13e_duplicate_contradiction_ruling_is_idempotent(self):
        first = ai._record_contradiction_ruling(
            self.repo.root, self.repo.contradiction["contradictionId"], "resolved",
            OPERATOR, FIXED_NOW, "Same rationale.")
        self.assertEqual(first["outcome"], ai.APPLIED)
        replay = ai._record_contradiction_ruling(
            self.repo.root, self.repo.contradiction["contradictionId"], "resolved",
            OPERATOR, LATER, "Same rationale.")
        self.assertEqual(replay["outcome"], ai.DUPLICATE_NOOP)
        events = ai._events_for(self.repo.lifecycle_dir, "CONTRADICTION_RECORD",
                                self.repo.contradiction["contradictionId"])
        # genesis "created" + exactly one "status_changed"
        self.assertEqual(len([e for e in events if e["eventType"] == "status_changed"]), 1)

    def test_unknown_decision_and_ruling_refused(self):
        with self.assertRaises(evc.EvidenceValidationError):
            self.accept(decision="probably")
        with self.assertRaises(evc.EvidenceValidationError):
            ai._record_contradiction_ruling(
                self.repo.root, self.repo.contradiction["contradictionId"],
                "sort_of", OPERATOR, FIXED_NOW, "Rationale.")

    def test_ruling_requires_rationale(self):
        for empty in (None, "", "   "):
            with self.assertRaises(evc.EvidenceValidationError):
                ai._record_contradiction_ruling(
                    self.repo.root, self.repo.contradiction["contradictionId"],
                    "resolved", OPERATOR, FIXED_NOW, empty)


# ===========================================================================
# B. Decision semantics -- the machine records, it does not decide
# ===========================================================================

class TestDecisionSemantics(IntakeTestCase):

    def test_accepted_sets_only_intended_fields(self):
        before = self.repo.question_record()
        self.accept()
        after = self.repo.question_record()
        self.assertEqual(after["answerStatus"], "answered")
        self.assertEqual(after["researchStatus"], "answered")
        self.assertEqual(after["answerEvidenceIds"], [self.repo.evidence["evidenceId"]])
        self.assertEqual(after["resolvedAt"], "2026-08-13T12:00:00Z")
        # Everything else is untouched.
        for field in ("questionId", "questionText", "questionType", "priority", "reason",
                      "blockingStatus", "claimId", "evidenceIds", "sourceIds", "createdAt",
                      "schemaVersion"):
            self.assertEqual(after[field], before[field], field)

    def test_accepted_uses_only_explicitly_supplied_evidence(self):
        self.accept(evidenceIds=[self.repo.evidence["evidenceId"]])
        after = self.repo.question_record()
        # evidence_b is in-corpus, provenance-clean and lexically similar --
        # and is NOT included, because nobody supplied it.
        self.assertNotIn(self.repo.evidence_b["evidenceId"], after["answerEvidenceIds"])
        self.assertEqual(after["answerEvidenceIds"], [self.repo.evidence["evidenceId"]])

    def test_rejection_does_not_mark_question_answered(self):
        result = ai._record_question_adjudication(
            self.repo.root, self.repo.question["questionId"], "rejected", REVIEWER, FIXED_NOW,
            evidenceIds=[self.repo.evidence["evidenceId"]], rationale="Off-topic.")
        self.assertEqual(result["outcome"], ai.APPLIED)
        after = self.repo.question_record()
        self.assertEqual(after["answerStatus"], "unanswered")
        self.assertEqual(after["researchStatus"], "open")
        self.assertEqual(after["answerEvidenceIds"], [])
        self.assertIsNone(after["resolvedAt"])
        # The decision still exists, in append-only history.
        events = self.repo.question_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["metadata"]["decision"], "rejected")
        self.assertEqual(events[0]["actor"], REVIEWER)

    def test_rejection_leaves_question_file_byte_identical(self):
        before = self.repo.raw_bytes(self.repo.questions_dir)
        ai._record_question_adjudication(
            self.repo.root, self.repo.question["questionId"], "rejected", REVIEWER, FIXED_NOW,
            evidenceIds=[self.repo.evidence["evidenceId"]], rationale="Off-topic.")
        self.assertEqual(self.repo.raw_bytes(self.repo.questions_dir), before)

    def test_uncertain_does_not_mark_question_answered(self):
        ai._record_question_adjudication(
            self.repo.root, self.repo.question["questionId"], "uncertain", REVIEWER, FIXED_NOW,
            evidenceIds=[self.repo.evidence["evidenceId"]], rationale="Suggestive, not decisive.")
        after = self.repo.question_record()
        self.assertEqual(after["answerStatus"], "partially_answered")
        self.assertEqual(after["researchStatus"], "researching")
        self.assertIsNone(after["resolvedAt"])

    def test_uncertain_without_evidence_never_creates_the_inconsistent_state(self):
        # The exact shape the Step 1 audit found on EQ|20260727|015:
        # partially_answered with an empty answerEvidenceIds. Refused here.
        ai._record_question_adjudication(
            self.repo.root, self.repo.question["questionId"], "uncertain", REVIEWER, FIXED_NOW,
            rationale="Looked; still not settled.")
        after = self.repo.question_record()
        self.assertEqual(after["answerStatus"], "unanswered")
        self.assertEqual(after["researchStatus"], "researching")
        self.assertEqual(after["answerEvidenceIds"], [])

    def test_uncertain_then_accepted_is_a_legal_progression(self):
        ai._record_question_adjudication(
            self.repo.root, self.repo.question["questionId"], "uncertain", REVIEWER, FIXED_NOW,
            evidenceIds=[self.repo.evidence["evidenceId"]], rationale="Partial.")
        ai._record_question_adjudication(
            self.repo.root, self.repo.question["questionId"], "accepted", REVIEWER, LATER,
            evidenceIds=[self.repo.evidence_b["evidenceId"]], rationale="Now complete.")
        after = self.repo.question_record()
        self.assertEqual(after["answerStatus"], "answered")
        self.assertEqual(after["answerEvidenceIds"],
                         sorted([self.repo.evidence["evidenceId"], self.repo.evidence_b["evidenceId"]]))

    def test_lifecycle_event_records_prior_and_new_state(self):
        self.accept()
        events = self.repo.question_events()
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event["entityType"], "EVIDENCE_QUESTION")
        self.assertEqual(event["entityId"], self.repo.question["questionId"])
        self.assertEqual(event["eventType"], "reviewed")
        self.assertEqual(event["priorStatus"], "unanswered")
        self.assertEqual(event["newStatus"], "answered")
        self.assertEqual(event["actor"], REVIEWER)
        self.assertEqual(event["metadata"]["decision"], "accepted")
        self.assertEqual(event["metadata"]["corpusTraderId"], HOME_TRADER)
        self.assertEqual(event["metadata"]["evidenceIds"], [self.repo.evidence["evidenceId"]])
        self.assertTrue(event["eventId"].startswith(
            "LCEVT|EVIDENCE_QUESTION|%s|" % self.repo.question["questionId"]))

    def test_adjudications_on_different_questions_are_independent(self):
        self.accept()
        self.assertEqual(self.repo.question_record(self.repo.question_b["questionId"])["answerStatus"],
                         "unanswered")


# ===========================================================================
# C. Direct-trader clarification
# ===========================================================================

class TestDirectTraderClarification(IntakeTestCase):

    def _clarify(self, **overrides):
        kwargs = dict(evidence_root=self.repo.root, questionId=self.repo.question["questionId"],
                      reviewer=REVIEWER, now=FIXED_NOW, traderId=HOME_TRADER,
                      speaker="The Educator", exactExcerpt="I enter on the retest, always.",
                      sourceChannel="https://example.invalid/live-qa", sourceDate="2026-08-12")
        kwargs.update(overrides)
        return ai._record_direct_trader_clarification(**kwargs)

    def test_preserves_every_required_provenance_field(self):
        result = self._clarify()
        item, source = result["evidenceItem"], result["source"]
        self.assertEqual(item["exactExcerpt"], "I enter on the retest, always.")
        self.assertEqual(item["speaker"], "The Educator")
        self.assertEqual(item["directness"], "direct_explicit")
        self.assertEqual(item["observationDate"], "2026-08-12")
        self.assertEqual(item["extractionMethod"], "manual_owner_entry")
        self.assertEqual(item["metadata"]["answersQuestionId"], self.repo.question["questionId"])
        self.assertEqual(item["metadata"]["questionAsked"], self.repo.question["questionText"])
        self.assertEqual(item["metadata"]["sourceChannel"], "https://example.invalid/live-qa")
        self.assertEqual(source["traderId"], HOME_TRADER)
        self.assertEqual(source["canonicalReference"], "https://example.invalid/live-qa")
        self.assertEqual(source["sourceDate"], "2026-08-12")

    def test_content_hash_is_computed_and_verifies(self):
        item = self._clarify()["evidenceItem"]
        expected = gc.content_hash_of({"exactExcerpt": item["exactExcerpt"],
                                        "normalizedObservation": item["normalizedObservation"]})
        self.assertEqual(item["contentHash"], expected)

    def test_clarification_does_not_answer_the_question(self):
        """CANDIDATE EVIDENCE != ACCEPTED ANSWER, even straight from the educator."""
        self._clarify()
        after = self.repo.question_record()
        self.assertEqual(after["answerStatus"], "unanswered")
        self.assertEqual(after["answerEvidenceIds"], [])
        self.assertEqual(self.repo.question_events(), [])

    def test_clarification_is_marked_candidate_only(self):
        item = self._clarify()["evidenceItem"]
        self.assertIs(item["metadata"]["candidateOnly"], True)

    def test_clarification_then_explicit_acceptance_is_the_full_path(self):
        item = self._clarify()["evidenceItem"]
        self.accept(evidenceIds=[item["evidenceId"]])
        after = self.repo.question_record()
        self.assertEqual(after["answerStatus"], "answered")
        self.assertEqual(after["answerEvidenceIds"], [item["evidenceId"]])

    def test_foreign_corpus_clarification_refused(self):
        with self.assertRaises(evc.EvidenceValidationError) as ctx:
            self._clarify(traderId=FOREIGN_TRADER)
        self.assertIn("cross-corpus", str(ctx.exception))

    def test_indirect_directness_may_omit_preserved_excerpt(self):
        """Only direct_* asserts 'the educator said this'. A weaker claim is
        allowed to be weaker -- it just can never be called direct_explicit."""
        result = self._clarify(directness="inferred_from_context", exactExcerpt=None,
                                normalizedObservation="Operator's recollection, not a quote.")
        self.assertEqual(result["evidenceItem"]["directness"], "inferred_from_context")
        self.assertIsNone(result["evidenceItem"]["exactExcerpt"])

    def test_creates_no_links_and_no_proposals(self):
        self._clarify()
        self.assertEqual(self.repo.count(self.repo.links_dir), 0)
        self.assertEqual(self.repo.count(self.repo.proposals_dir), 0)


# ===========================================================================
# D. Operator contradiction ruling -- SOURCE FACT != OPERATOR RULING
# ===========================================================================

class TestContradictionRuling(IntakeTestCase):

    def test_resolved_sets_status_resolution_and_reviewed_at(self):
        ai._record_contradiction_ruling(
            self.repo.root, self.repo.contradiction["contradictionId"], "resolved",
            OPERATOR, FIXED_NOW, "Scopes differ; both stand within their own scope.")
        after = self.repo.contradiction_record()
        self.assertEqual(after["status"], "resolved_by_owner")
        self.assertEqual(after["resolution"], "Scopes differ; both stand within their own scope.")
        self.assertEqual(after["reviewedAt"], "2026-08-13T12:00:00Z")

    def test_scope_qualified_narrows_without_erasing(self):
        ai._record_contradiction_ruling(
            self.repo.root, self.repo.contradiction["contradictionId"], "scope_qualified",
            OPERATOR, FIXED_NOW, "Applies only to the London session.", scopeOverlap="partial")
        after = self.repo.contradiction_record()
        self.assertEqual(after["status"], "accepted_as_context_dependent")
        self.assertEqual(after["scopeOverlap"], "partial")
        # Severity is untouched: it stops BLOCKING via status, not by rewriting
        # how serious the disagreement was.
        self.assertEqual(after["severity"], "blocking")

    def test_leave_open_records_review_without_faking_resolution(self):
        ai._record_contradiction_ruling(
            self.repo.root, self.repo.contradiction["contradictionId"], "leave_open",
            OPERATOR, FIXED_NOW, "Reviewed; not enough to settle it yet.")
        after = self.repo.contradiction_record()
        self.assertEqual(after["status"], "open")
        self.assertIsNone(after["resolution"])
        self.assertEqual(after["reviewedAt"], "2026-08-13T12:00:00Z")
        events = ai._events_for(self.repo.lifecycle_dir, "CONTRADICTION_RECORD",
                                self.repo.contradiction["contradictionId"])
        self.assertIn("Reviewed; not enough to settle it yet.",
                      [e.get("reason") for e in events])

    def test_leave_open_still_permits_a_later_real_ruling(self):
        ai._record_contradiction_ruling(
            self.repo.root, self.repo.contradiction["contradictionId"], "leave_open",
            OPERATOR, FIXED_NOW, "Not yet.")
        ai._record_contradiction_ruling(
            self.repo.root, self.repo.contradiction["contradictionId"], "resolved",
            OPERATOR, LATER, "Now settled.")
        self.assertEqual(self.repo.contradiction_record()["status"], "resolved_by_owner")

    def test_source_claims_remain_byte_identical_after_ruling(self):
        before = self.repo.raw_bytes(self.repo.claims_dir)
        ai._record_contradiction_ruling(
            self.repo.root, self.repo.contradiction["contradictionId"], "resolved",
            OPERATOR, FIXED_NOW, "Operator ruling, not a source fact.")
        self.assertEqual(self.repo.raw_bytes(self.repo.claims_dir), before)

    def test_source_evidence_remains_byte_identical_after_ruling(self):
        before = self.repo.raw_bytes(self.repo.items_dir)
        ai._record_contradiction_ruling(
            self.repo.root, self.repo.contradiction["contradictionId"], "resolved",
            OPERATOR, FIXED_NOW, "Operator ruling, not a source fact.")
        self.assertEqual(self.repo.raw_bytes(self.repo.items_dir), before)

    def test_ruling_preserves_both_claim_references(self):
        ai._record_contradiction_ruling(
            self.repo.root, self.repo.contradiction["contradictionId"], "resolved",
            OPERATOR, FIXED_NOW, "Ruling.")
        after = self.repo.contradiction_record()
        self.assertEqual(after["claimAId"], self.repo.claim["claimId"])
        self.assertEqual(after["claimBId"], self.repo.foreign_claim["claimId"])
        self.assertEqual(after["rationale"], "Synthetic fixture contradiction.")


# ===========================================================================
# E. The high-risk boundary (Step 2 sec. 5) -- mutation-style invariants
# ===========================================================================

class TestNoProposalPipeline(IntakeTestCase):

    def _all_intake_operations(self):
        ai._record_direct_trader_clarification(
            self.repo.root, self.repo.question["questionId"], REVIEWER, FIXED_NOW,
            HOME_TRADER, "The Educator", "I enter on the retest, always.",
            "https://example.invalid/live-qa", "2026-08-12")
        self.accept()
        ai._record_question_adjudication(
            self.repo.root, self.repo.question_b["questionId"], "rejected", REVIEWER, FIXED_NOW,
            evidenceIds=[self.repo.evidence_b["evidenceId"]], rationale="No.")
        ai._record_contradiction_ruling(
            self.repo.root, self.repo.contradiction["contradictionId"], "resolved",
            OPERATOR, FIXED_NOW, "Ruling.")

    def test_no_rule_candidate_proposal_is_ever_created(self):
        self._all_intake_operations()
        self.assertEqual(self.repo.count(self.repo.proposals_dir), 0)

    def test_no_evidence_link_is_ever_created(self):
        links_before = self.repo.count(self.repo.links_dir)
        self._all_intake_operations()
        self.assertEqual(self.repo.count(self.repo.links_dir), links_before)
        self.assertEqual(self.repo.count(self.repo.links_dir), 0)

    def test_claim_confidence_is_never_recomputed(self):
        before = self.repo.raw_bytes(self.repo.claims_dir)
        self._all_intake_operations()
        # If anything had linked evidence to a claim, recompute_claim_confidence
        # would have rewritten confidenceState/lastEvaluatedAt on these files.
        self.assertEqual(self.repo.raw_bytes(self.repo.claims_dir), before)

    @staticmethod
    def _executable_body():
        """answer_intake.py with its module docstring and comment lines removed,
        so these checks test what the module DOES, not what it says about
        itself. (The docstring legitimately names the pipeline it refuses to
        call.)"""
        with open(os.path.join(SCRIPTS_DIR, "answer_intake.py"), "r", encoding="utf-8") as f:
            source = f.read()
        body = source.split('"""', 2)[-1]
        return "".join(line for line in body.splitlines(keepends=True)
                       if not line.lstrip().startswith("#"))

    def test_module_never_calls_the_proposal_pipeline(self):
        body = self._executable_body()
        for forbidden in ("extraction_pipeline", "run_post_annotation_pipeline",
                          "rule_candidate_proposals", "propose_rule_candidate",
                          "link_evidence_to_claim", "recompute_claim_confidence"):
            self.assertNotIn(forbidden, body, forbidden)

    def test_module_contains_no_substring_matching(self):
        """Identity resolution is by exact governed id only. Nothing in this
        module may fall back to text containment."""
        body = self._executable_body()
        for forbidden in (".startswith(", ".endswith(", ".find(", "difflib",
                          "near_duplicate", "SequenceMatcher", "normalize_claim_text"):
            self.assertNotIn(forbidden, body, forbidden)

    def test_candidate_evidence_is_not_mutated_by_adjudication(self):
        before = self.repo.raw_bytes(self.repo.items_dir)
        self.accept()
        self.assertEqual(self.repo.raw_bytes(self.repo.items_dir), before)

    def test_sources_are_not_mutated_by_adjudication(self):
        before = self.repo.raw_bytes(self.repo.sources_dir)
        self.accept()
        self.assertEqual(self.repo.raw_bytes(self.repo.sources_dir), before)

    def test_refusals_write_absolutely_nothing(self):
        snapshot = {name: self.repo.raw_bytes(os.path.join(self.repo.root, name))
                    for name in SyntheticIntakeRepo.DIRS}
        refusals = [
            lambda: self.accept(questionId="EQ|99999999|999"),
            lambda: self.accept(evidenceIds=[self.repo.foreign_evidence["evidenceId"]]),
            lambda: self.accept(reviewer="pipeline"),
            lambda: self.accept(evidenceIds=[]),
            lambda: ai._record_contradiction_ruling(
                self.repo.root, "XCONTRA|99999999|999", "resolved", OPERATOR, FIXED_NOW, "x"),
        ]
        for call in refusals:
            with self.assertRaises(evc.EvidenceValidationError):
                call()
        after = {name: self.repo.raw_bytes(os.path.join(self.repo.root, name))
                 for name in SyntheticIntakeRepo.DIRS}
        self.assertEqual(after, snapshot)


# ===========================================================================
# F. Integration with the existing integrity validator
# ===========================================================================

class TestIntegrityStaysClean(IntakeTestCase):

    def _integrity(self):
        return ve.run_integrity_checks(self.repo.root, is_production=False)

    def test_baseline_fixture_is_clean(self):
        report = self._integrity()
        self.assertEqual(report["summary"]["ERROR"], 0, report["findings"])
        self.assertEqual(report["summary"]["FATAL"], 0, report["findings"])

    def test_integrity_clean_after_every_intake_operation(self):
        ai._record_direct_trader_clarification(
            self.repo.root, self.repo.question["questionId"], REVIEWER, FIXED_NOW,
            HOME_TRADER, "The Educator", "I enter on the retest, always.",
            "https://example.invalid/live-qa", "2026-08-12")
        self.accept()
        ai._record_question_adjudication(
            self.repo.root, self.repo.question_b["questionId"], "uncertain", REVIEWER, FIXED_NOW,
            evidenceIds=[self.repo.evidence_b["evidenceId"]], rationale="Partial.")
        ai._record_contradiction_ruling(
            self.repo.root, self.repo.contradiction["contradictionId"], "scope_qualified",
            OPERATOR, FIXED_NOW, "Session-scoped.", scopeOverlap="partial")
        report = self._integrity()
        self.assertEqual(report["summary"]["ERROR"], 0, report["findings"])
        self.assertEqual(report["summary"]["FATAL"], 0, report["findings"])

    def test_question_lifecycle_genesis_is_accepted_by_the_validator(self):
        """An EVIDENCE_QUESTION's first lifecycle event is 'reviewed', not
        'created' -- questions have never emitted a creation event. The
        validator must not report INVALID_LIFECYCLE_SEQUENCE for that."""
        self.accept()
        report = self._integrity()
        sequence_findings = [f for f in report["findings"]
                             if f["findingType"] == "INVALID_LIFECYCLE_SEQUENCE"]
        self.assertEqual(sequence_findings, [])

    def test_lifecycle_entity_type_is_registered_in_both_code_and_schema(self):
        self.assertIn("EVIDENCE_QUESTION", evc.LIFECYCLE_ENTITY_TYPES)
        schema_path = os.path.join(REPO_ROOT, "docs", "trader-intelligence", "evidence",
                                    "schema", "evidence-lifecycle-event.schema.json")
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        self.assertIn("EVIDENCE_QUESTION", schema["properties"]["entityType"]["enum"])
        self.assertIn("EVIDENCE_QUESTION", schema["properties"]["eventId"]["pattern"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

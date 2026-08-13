#!/usr/bin/env python3
"""MOGO-020 Step 4 -- governed intake preview and commit boundary test suite.

Pure stdlib (unittest). Fully offline, deterministic. Run with:

    python3 -m unittest tests.trader_intelligence.test_answer_intake_preview -v

EVERY test builds a throwaway two-corpus synthetic evidence root in a temp
directory (reusing the Step 3 fixture). Nothing here reads or writes
docs/trader-intelligence/evidence/, and nothing here touches
XCONTRA|20260728|001, EQ|20260727|015, the 281 production questions, ALEX, TJR
authority or any strategy file.

WHAT THESE TESTS PROVE

    PREVIEW never writes and never authorizes.
    COMMIT performs only the exact action that was previewed, against the exact
    state that was reviewed -- and refuses otherwise.
"""
import json
import os
import sys
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts", "trader_intelligence")

sys.path.insert(0, SCRIPTS_DIR)
import graph_common as gc                 # noqa: E402
import evidence_common as evc             # noqa: E402
import research_understanding as ru       # noqa: E402
import answer_intake as ai                # noqa: E402

from tests.trader_intelligence.test_answer_intake_reevaluation import (  # noqa: E402
    TwoCorpusRepo, CORPUS_A, CORPUS_B, REVIEWER, OPERATOR,
    FIXED_NOW, LATER, NO_DESTINATIONS, read_json, module_identifiers,
)


class PreviewTestCase(unittest.TestCase):
    def setUp(self):
        self.repo = TwoCorpusRepo()
        self.addCleanup(self.repo.cleanup)

    # --- action builders ------------------------------------------------

    def accept_kwargs(self, corpus=CORPUS_A, **overrides):
        kwargs = {"questionId": self.repo.question_id(corpus), "decision": "accepted",
                  "reviewer": REVIEWER,
                  "evidenceIds": [self.repo.answer_evidence_id(corpus)],
                  "rationale": "The educator states the trigger explicitly here."}
        kwargs.update(overrides)
        return kwargs

    def clarify_kwargs(self, corpus=CORPUS_A, **overrides):
        kwargs = {"questionId": self.repo.question_id(corpus), "reviewer": REVIEWER,
                  "traderId": corpus, "speaker": "The Educator",
                  "exactExcerpt": "Entry triggers on the first retest after the sweep.",
                  "sourceChannel": "https://example.invalid/live-qa",
                  "sourceDate": "2026-08-12"}
        kwargs.update(overrides)
        return kwargs

    def ruling_kwargs(self, contradictionId, **overrides):
        kwargs = {"contradictionId": contradictionId, "ruling": "resolved",
                  "operator": OPERATOR, "rationale": "Operator ruling on a synthetic record."}
        kwargs.update(overrides)
        return kwargs

    # --- helpers --------------------------------------------------------

    def preview(self, action, now=FIXED_NOW, **kwargs):
        return ai.preview(self.repo.root, action, now,
                          approved_destinations=NO_DESTINATIONS, **kwargs)

    def commit(self, action, token, now=FIXED_NOW, **kwargs):
        return ai.commit(self.repo.root, action, now, token,
                         approved_destinations=NO_DESTINATIONS, **kwargs)

    def question_record(self, corpus=CORPUS_A):
        return read_json(os.path.join(
            self.repo.questions_dir,
            evc.question_id_to_filename(self.repo.question_id(corpus))))


# ===========================================================================
# A. Preview writes nothing (conditions 1, 2, 3, 18)
# ===========================================================================

class TestPreviewWritesNothing(PreviewTestCase):

    def test_01_preview_performs_zero_writes(self):
        snapshot = self.repo.snapshot_all()
        contradiction = self.repo.add_blocking_contradiction(CORPUS_A)
        snapshot = self.repo.snapshot_all()          # after fixture mutation
        self.preview(ai.QUESTION_ADJUDICATION, **self.accept_kwargs())
        self.preview(ai.DIRECT_TRADER_CLARIFICATION, **self.clarify_kwargs())
        self.preview(ai.CONTRADICTION_RULING,
                     **self.ruling_kwargs(contradiction["contradictionId"]))
        self.assertEqual(self.repo.snapshot_all(), snapshot)

    def test_02_repeated_identical_preview_is_deterministic(self):
        first = self.preview(ai.QUESTION_ADJUDICATION, **self.accept_kwargs())
        second = self.preview(ai.QUESTION_ADJUDICATION, **self.accept_kwargs())
        self.assertEqual(first["previewToken"], second["previewToken"])
        self.assertEqual(first, second)

    def test_03_preview_appends_no_lifecycle_events(self):
        before = self.repo.count("lifecycle")
        for _ in range(3):
            self.preview(ai.QUESTION_ADJUDICATION, **self.accept_kwargs())
            self.preview(ai.DIRECT_TRADER_CLARIFICATION, **self.clarify_kwargs())
        self.assertEqual(self.repo.count("lifecycle"), before)
        self.assertEqual(self.repo.question_events(self.repo.question_id(CORPUS_A)), [])

    def test_18_prospective_reevaluation_creates_no_persistent_change(self):
        snapshot = self.repo.snapshot_all()
        result = self.preview(ai.QUESTION_ADJUDICATION, **self.accept_kwargs())
        # The preview forecasts a real change...
        self.assertTrue(result["eligibilityChanges"])
        self.assertEqual(result["eligibilityAfter"], ru.ELIGIBLE)
        # ...while stored state still says otherwise.
        self.assertEqual(self.repo.snapshot_all(), snapshot)
        self.assertEqual(self.repo.reevaluate(CORPUS_A)["eligibilityStatus"], ru.BLOCKED)

    def test_preview_of_a_refused_action_raises_and_writes_nothing(self):
        snapshot = self.repo.snapshot_all()
        for kwargs in (self.accept_kwargs(evidenceIds=[self.repo.answer_evidence_id(CORPUS_B)]),
                       self.accept_kwargs(reviewer="pipeline"),
                       self.accept_kwargs(questionId="EQ|99999999|999")):
            with self.assertRaises(evc.EvidenceValidationError):
                self.preview(ai.QUESTION_ADJUDICATION, **kwargs)
        self.assertEqual(self.repo.snapshot_all(), snapshot)


# ===========================================================================
# B. Preview content
# ===========================================================================

class TestPreviewContent(PreviewTestCase):

    def test_preview_exposes_the_full_operator_review_surface(self):
        result = self.preview(ai.QUESTION_ADJUDICATION, **self.accept_kwargs())
        for field in ("previewToken", "action", "targetType", "targetId", "actor", "decision",
                      "rationale", "corpusTraderId", "evidenceIds", "currentRecord",
                      "proposedRecord", "changedFields", "wouldAppendLifecycleEvent",
                      "provenanceSummary", "reevaluationBefore", "reevaluationAfter",
                      "blockersRemoved", "blockersRetained", "eligibilityChanges",
                      "routingChanged", "authorizes", "isAuthorization"):
            self.assertIn(field, result, field)

    def test_preview_reports_exactly_the_fields_that_would_change(self):
        result = self.preview(ai.QUESTION_ADJUDICATION, **self.accept_kwargs())
        self.assertEqual(sorted(result["changedFields"]),
                         ["answerEvidenceIds", "answerStatus", "researchStatus", "resolvedAt"])
        self.assertEqual(result["changedFields"]["answerStatus"],
                         {"from": "unanswered", "to": "answered"})

    def test_preview_reports_the_lifecycle_event_that_would_be_appended(self):
        result = self.preview(ai.QUESTION_ADJUDICATION, **self.accept_kwargs())
        event = result["wouldAppendLifecycleEvent"]
        self.assertEqual(event["entityType"], "EVIDENCE_QUESTION")
        self.assertEqual(event["actor"], REVIEWER)
        self.assertEqual(event["priorStatus"], "unanswered")
        self.assertEqual(event["newStatus"], "answered")

    def test_preview_reports_blockers_removed_and_retained(self):
        self.repo.add_blocking_contradiction(CORPUS_A)
        result = self.preview(ai.QUESTION_ADJUDICATION, **self.accept_kwargs())
        self.assertIn("BLOCKING_QUESTION|%s" % self.repo.question_id(CORPUS_A),
                      result["blockersRemoved"])
        self.assertTrue([k for k in result["blockersRetained"]
                         if k.startswith("BLOCKING_CONTRADICTION")])
        # A retained blocker means eligibility does NOT change.
        self.assertFalse(result["eligibilityChanges"])

    def test_preview_carries_provenance_for_every_cited_item(self):
        result = self.preview(ai.QUESTION_ADJUDICATION, **self.accept_kwargs())
        row = result["provenanceSummary"][0]
        self.assertEqual(row["evidenceId"], self.repo.answer_evidence_id(CORPUS_A))
        self.assertEqual(row["traderId"], CORPUS_A)
        self.assertEqual(row["directness"], "direct_explicit")
        self.assertEqual(row["provenanceStatus"], "partially_verified")
        self.assertTrue(row["contentHash"])
        self.assertTrue(row["exactExcerpt"])

    def test_preview_states_it_authorizes_nothing(self):
        result = self.preview(ai.QUESTION_ADJUDICATION, **self.accept_kwargs())
        self.assertFalse(result["isAuthorization"])
        for phrase in ("RuleCandidateProposal", "no backtest", "no paper trading",
                       "live-money authority"):
            self.assertIn(phrase, result["authorizes"])

    def test_preview_is_json_serializable(self):
        result = self.preview(ai.QUESTION_ADJUDICATION, **self.accept_kwargs())
        self.assertIsInstance(json.dumps(result, sort_keys=True), str)


# ===========================================================================
# C. Commit requires a valid, state-bound token (conditions 4-12)
# ===========================================================================

class TestCommitBoundary(PreviewTestCase):

    def test_04_valid_preview_then_valid_commit_succeeds(self):
        preview = self.preview(ai.QUESTION_ADJUDICATION, **self.accept_kwargs())
        result = self.commit(ai.QUESTION_ADJUDICATION, preview["previewToken"],
                             **self.accept_kwargs())
        self.assertEqual(result["outcome"], ai.APPLIED)
        self.assertEqual(self.question_record()["answerStatus"], "answered")
        # And the committed reality matches what preview forecast.
        self.assertEqual(result["reevaluation"]["eligibilityStatus"],
                         preview["eligibilityAfter"])

    def test_05_commit_without_a_token_fails(self):
        for token in (None, "", "   "):
            with self.assertRaises(evc.EvidenceValidationError) as ctx:
                self.commit(ai.QUESTION_ADJUDICATION, token, **self.accept_kwargs())
            self.assertIn("previewToken", str(ctx.exception))
        self.assertEqual(self.question_record()["answerStatus"], "unanswered")

    def test_05b_commit_with_a_fabricated_token_fails(self):
        with self.assertRaises(evc.EvidenceValidationError):
            self.commit(ai.QUESTION_ADJUDICATION, "0" * 64, **self.accept_kwargs())
        self.assertEqual(self.question_record()["answerStatus"], "unanswered")

    def test_06_modified_target_after_preview_blocks_commit(self):
        preview = self.preview(ai.QUESTION_ADJUDICATION, **self.accept_kwargs())
        # Somebody else moves the question on to "researching" in the meantime.
        ai._record_question_adjudication(
            self.repo.root, self.repo.question_id(CORPUS_A), "uncertain", REVIEWER, LATER,
            rationale="Still looking.")
        with self.assertRaises(evc.EvidenceValidationError) as ctx:
            self.commit(ai.QUESTION_ADJUDICATION, preview["previewToken"],
                        **self.accept_kwargs())
        self.assertIn("material state changed after preview", str(ctx.exception))

    def test_07_modified_evidence_after_preview_blocks_commit(self):
        preview = self.preview(ai.QUESTION_ADJUDICATION, **self.accept_kwargs())
        path = os.path.join(self.repo.items_dir,
                            evc.evidence_id_to_filename(self.repo.answer_evidence_id(CORPUS_A)))
        item = read_json(path)
        item["exactExcerpt"] = "Rewritten after the operator reviewed it."
        item["contentHash"] = gc.content_hash_of(
            {"exactExcerpt": item["exactExcerpt"],
             "normalizedObservation": item["normalizedObservation"]})
        gc.atomic_write_text(path, gc.pretty_json(item))
        with self.assertRaises(evc.EvidenceValidationError) as ctx:
            self.commit(ai.QUESTION_ADJUDICATION, preview["previewToken"],
                        **self.accept_kwargs())
        self.assertIn("material state changed after preview", str(ctx.exception))
        self.assertEqual(self.question_record()["answerStatus"], "unanswered")

    def test_08_modified_provenance_after_preview_blocks_commit(self):
        preview = self.preview(ai.QUESTION_ADJUDICATION, **self.accept_kwargs())
        path = os.path.join(self.repo.sources_dir,
                            evc.source_id_to_filename(self.repo.corpus[CORPUS_A]["source"]["sourceId"]))
        source = read_json(path)
        source["provenanceStatus"] = "verified"
        gc.atomic_write_text(path, gc.pretty_json(source))
        with self.assertRaises(evc.EvidenceValidationError) as ctx:
            self.commit(ai.QUESTION_ADJUDICATION, preview["previewToken"],
                        **self.accept_kwargs())
        self.assertIn("material state changed after preview", str(ctx.exception))

    def test_08b_tampered_hash_after_preview_blocks_commit(self):
        preview = self.preview(ai.QUESTION_ADJUDICATION, **self.accept_kwargs())
        path = os.path.join(self.repo.items_dir,
                            evc.evidence_id_to_filename(self.repo.answer_evidence_id(CORPUS_A)))
        item = read_json(path)
        item["exactExcerpt"] = "Edited in place, hash left stale."
        gc.atomic_write_text(path, gc.pretty_json(item))
        # Hash verification refuses this before the token is even compared.
        with self.assertRaises(evc.EvidenceValidationError) as ctx:
            self.commit(ai.QUESTION_ADJUDICATION, preview["previewToken"],
                        **self.accept_kwargs())
        self.assertIn("hash verification", str(ctx.exception))

    def test_09_wrong_corpus_after_preview_fails(self):
        preview = self.preview(ai.QUESTION_ADJUDICATION, **self.accept_kwargs())
        path = os.path.join(self.repo.sources_dir,
                            evc.source_id_to_filename(self.repo.corpus[CORPUS_A]["source"]["sourceId"]))
        source = read_json(path)
        source["traderId"] = CORPUS_B
        gc.atomic_write_text(path, gc.pretty_json(source))
        with self.assertRaises(evc.EvidenceValidationError) as ctx:
            self.commit(ai.QUESTION_ADJUDICATION, preview["previewToken"],
                        **self.accept_kwargs())
        self.assertIn("foreign-corpus", str(ctx.exception))
        self.assertEqual(self.question_record()["answerStatus"], "unanswered")

    def test_10_changed_actor_invalidates_the_token(self):
        preview = self.preview(ai.QUESTION_ADJUDICATION, **self.accept_kwargs())
        with self.assertRaises(evc.EvidenceValidationError) as ctx:
            self.commit(ai.QUESTION_ADJUDICATION, preview["previewToken"],
                        **self.accept_kwargs(reviewer="operator:somebody-else"))
        self.assertIn("material state changed after preview", str(ctx.exception))

    def test_10b_changed_rationale_invalidates_the_token(self):
        preview = self.preview(ai.QUESTION_ADJUDICATION, **self.accept_kwargs())
        with self.assertRaises(evc.EvidenceValidationError):
            self.commit(ai.QUESTION_ADJUDICATION, preview["previewToken"],
                        **self.accept_kwargs(rationale="A different justification entirely."))

    def test_10c_changed_evidence_set_invalidates_the_token(self):
        preview = self.preview(ai.QUESTION_ADJUDICATION, **self.accept_kwargs())
        other = self.repo.corpus[CORPUS_A]["items"]["entry_rule"]["evidenceId"]
        with self.assertRaises(evc.EvidenceValidationError):
            self.commit(ai.QUESTION_ADJUDICATION, preview["previewToken"],
                        **self.accept_kwargs(evidenceIds=[other]))

    def test_11_token_cannot_authorize_a_different_target(self):
        preview = self.preview(ai.QUESTION_ADJUDICATION, **self.accept_kwargs(corpus=CORPUS_A))
        with self.assertRaises(evc.EvidenceValidationError) as ctx:
            self.commit(ai.QUESTION_ADJUDICATION, preview["previewToken"],
                        **self.accept_kwargs(corpus=CORPUS_B))
        self.assertIn("material state changed after preview", str(ctx.exception))
        self.assertEqual(self.question_record(CORPUS_B)["answerStatus"], "unanswered")

    def test_12_token_cannot_authorize_a_different_decision(self):
        preview = self.preview(ai.QUESTION_ADJUDICATION, **self.accept_kwargs())
        with self.assertRaises(evc.EvidenceValidationError):
            self.commit(ai.QUESTION_ADJUDICATION, preview["previewToken"],
                        **self.accept_kwargs(decision="rejected"))
        self.assertEqual(self.question_record()["answerStatus"], "unanswered")

    def test_12b_token_cannot_authorize_a_different_action_type(self):
        contradiction = self.repo.add_blocking_contradiction(CORPUS_A)
        preview = self.preview(ai.QUESTION_ADJUDICATION, **self.accept_kwargs())
        with self.assertRaises(evc.EvidenceValidationError):
            self.commit(ai.CONTRADICTION_RULING, preview["previewToken"],
                        **self.ruling_kwargs(contradiction["contradictionId"]))
        self.assertEqual(
            self.repo.contradiction_record(contradiction["contradictionId"])["status"], "open")

    def test_13_exact_duplicate_commit_is_idempotent(self):
        preview = self.preview(ai.QUESTION_ADJUDICATION, **self.accept_kwargs())
        first = self.commit(ai.QUESTION_ADJUDICATION, preview["previewToken"],
                            **self.accept_kwargs())
        self.assertEqual(first["outcome"], ai.APPLIED)
        events = len(self.repo.question_events(self.repo.question_id(CORPUS_A)))
        # Replaying the same token AND the same action is a no-op, even though
        # the target record has legitimately moved on since the token was issued.
        second = self.commit(ai.QUESTION_ADJUDICATION, preview["previewToken"], now=LATER,
                             **self.accept_kwargs())
        self.assertEqual(second["outcome"], ai.DUPLICATE_NOOP)
        self.assertEqual(len(self.repo.question_events(self.repo.question_id(CORPUS_A))), events)

    def test_unknown_action_is_refused(self):
        with self.assertRaises(evc.EvidenceValidationError):
            self.preview("freeze_specification", questionId=self.repo.question_id(CORPUS_A))


# ===========================================================================
# D. Rejected / uncertain previews (conditions 14, 15)
# ===========================================================================

class TestRejectedAndUncertainPreview(PreviewTestCase):

    def test_14_rejected_preview_mutates_nothing(self):
        snapshot = self.repo.snapshot_all()
        result = self.preview(ai.QUESTION_ADJUDICATION,
                              **self.accept_kwargs(decision="rejected"))
        self.assertEqual(self.repo.snapshot_all(), snapshot)
        self.assertEqual(result["changedFields"], {})
        self.assertEqual(result["blockersRemoved"], [])
        self.assertFalse(result["eligibilityChanges"])

    def test_14b_rejected_commit_writes_only_history(self):
        preview = self.preview(ai.QUESTION_ADJUDICATION,
                               **self.accept_kwargs(decision="rejected"))
        questions_before = self.repo.raw_bytes("questions")
        result = self.commit(ai.QUESTION_ADJUDICATION, preview["previewToken"],
                             **self.accept_kwargs(decision="rejected"))
        self.assertEqual(result["outcome"], ai.APPLIED)
        self.assertEqual(self.repo.raw_bytes("questions"), questions_before)
        self.assertEqual(len(self.repo.question_events(self.repo.question_id(CORPUS_A))), 1)

    def test_15_uncertain_preview_does_not_falsely_resolve(self):
        result = self.preview(ai.QUESTION_ADJUDICATION,
                              **self.accept_kwargs(decision="uncertain"))
        self.assertEqual(result["proposedRecord"]["answerStatus"], "partially_answered")
        self.assertEqual(result["proposedRecord"]["researchStatus"], "researching")
        self.assertIsNone(result["proposedRecord"]["resolvedAt"])
        self.assertEqual(result["eligibilityAfter"], ru.BLOCKED)
        self.assertEqual(result["blockersRemoved"], [])

    def test_15b_uncertain_without_evidence_never_previews_the_bad_shape(self):
        result = self.preview(ai.QUESTION_ADJUDICATION,
                              **self.accept_kwargs(decision="uncertain", evidenceIds=None))
        self.assertEqual(result["proposedRecord"]["answerStatus"], "unanswered")
        self.assertEqual(result["proposedRecord"]["answerEvidenceIds"], [])
        self.assertEqual(result["proposedRecord"]["researchStatus"], "researching")


# ===========================================================================
# E. Direct-trader two-stage boundary (condition 16)
# ===========================================================================

class TestDirectTraderTwoStage(PreviewTestCase):

    def test_16_clarification_preview_is_candidate_only(self):
        result = self.preview(ai.DIRECT_TRADER_CLARIFICATION, **self.clarify_kwargs())
        self.assertFalse(result["answersQuestion"])
        self.assertEqual(result["changedFields"], {})
        self.assertEqual(result["blockersRemoved"], [])
        self.assertFalse(result["eligibilityChanges"])
        self.assertEqual(result["eligibilityBefore"], result["eligibilityAfter"])
        row = [r for r in result["provenanceSummary"] if r.get("candidateOnly")][0]
        self.assertEqual(row["speaker"], "The Educator")
        self.assertEqual(row["directness"], "direct_explicit")
        self.assertEqual(row["sourceChannel"], "https://example.invalid/live-qa")

    def test_16b_predicted_identifiers_match_what_commit_creates(self):
        preview = self.preview(ai.DIRECT_TRADER_CLARIFICATION, **self.clarify_kwargs())
        result = self.commit(ai.DIRECT_TRADER_CLARIFICATION, preview["previewToken"],
                             **self.clarify_kwargs())
        self.assertEqual(result["source"]["sourceId"], preview["plannedSourceId"])
        self.assertEqual(result["evidenceId"], preview["plannedEvidenceId"])

    def test_16c_clarification_commit_does_not_answer_its_own_question(self):
        preview = self.preview(ai.DIRECT_TRADER_CLARIFICATION, **self.clarify_kwargs())
        self.commit(ai.DIRECT_TRADER_CLARIFICATION, preview["previewToken"],
                    **self.clarify_kwargs())
        self.assertEqual(self.question_record()["answerStatus"], "unanswered")
        self.assertEqual(self.repo.reevaluate(CORPUS_A)["eligibilityStatus"], ru.BLOCKED)

    def test_16d_a_second_explicit_preview_and_commit_is_required(self):
        first = self.preview(ai.DIRECT_TRADER_CLARIFICATION, **self.clarify_kwargs())
        created = self.commit(ai.DIRECT_TRADER_CLARIFICATION, first["previewToken"],
                              **self.clarify_kwargs())
        accept = self.accept_kwargs(evidenceIds=[created["evidenceId"]],
                                     rationale="The educator answered it directly.")
        second = self.preview(ai.QUESTION_ADJUDICATION, now=LATER, **accept)
        self.assertTrue(second["eligibilityChanges"])
        self.assertNotEqual(first["previewToken"], second["previewToken"])
        result = self.commit(ai.QUESTION_ADJUDICATION, second["previewToken"], now=LATER, **accept)
        self.assertEqual(result["outcome"], ai.APPLIED)
        self.assertEqual(result["reevaluation"]["eligibilityStatus"], ru.ELIGIBLE)

    def test_16e_clarification_token_cannot_commit_the_acceptance(self):
        clarify = self.preview(ai.DIRECT_TRADER_CLARIFICATION, **self.clarify_kwargs())
        with self.assertRaises(evc.EvidenceValidationError):
            self.commit(ai.QUESTION_ADJUDICATION, clarify["previewToken"], **self.accept_kwargs())
        self.assertEqual(self.question_record()["answerStatus"], "unanswered")

    def test_16f_direct_explicit_without_preserved_source_fails_at_preview(self):
        for missing in ("exactExcerpt", "speaker", "sourceChannel", "sourceDate"):
            with self.assertRaises(evc.EvidenceValidationError):
                self.preview(ai.DIRECT_TRADER_CLARIFICATION,
                             **self.clarify_kwargs(**{missing: ""}))


# ===========================================================================
# F. Operator ruling boundary (condition 17)
# ===========================================================================

class TestContradictionPreviewBoundary(PreviewTestCase):

    def setUp(self):
        super().setUp()
        self.contradiction = self.repo.add_blocking_contradiction(CORPUS_A)
        self.contradiction_id = self.contradiction["contradictionId"]

    def test_17_preview_names_source_claims_and_marks_them_unchanged(self):
        result = self.preview(ai.CONTRADICTION_RULING,
                              **self.ruling_kwargs(self.contradiction_id))
        self.assertEqual(result["sourceClaimIds"],
                         [self.contradiction["claimAId"], self.contradiction["claimBId"]])
        self.assertTrue(result["sourceClaimsUnchanged"])
        # The ruling touches ONLY governed resolution fields.
        self.assertEqual(sorted(result["changedFields"]),
                         ["resolution", "reviewedAt", "status"])

    def test_17b_commit_leaves_source_claims_byte_identical(self):
        claims_before = self.repo.raw_bytes("claims")
        items_before = self.repo.raw_bytes("items")
        preview = self.preview(ai.CONTRADICTION_RULING,
                               **self.ruling_kwargs(self.contradiction_id))
        self.commit(ai.CONTRADICTION_RULING, preview["previewToken"],
                    **self.ruling_kwargs(self.contradiction_id))
        self.assertEqual(self.repo.raw_bytes("claims"), claims_before)
        self.assertEqual(self.repo.raw_bytes("items"), items_before)

    def test_17c_detection_rationale_is_never_overwritten_by_the_ruling(self):
        preview = self.preview(ai.CONTRADICTION_RULING,
                               **self.ruling_kwargs(self.contradiction_id,
                                                     rationale="Operator interpretation."))
        self.commit(ai.CONTRADICTION_RULING, preview["previewToken"],
                    **self.ruling_kwargs(self.contradiction_id,
                                          rationale="Operator interpretation."))
        record = self.repo.contradiction_record(self.contradiction_id)
        self.assertEqual(record["rationale"], "Synthetic fixture contradiction.")
        self.assertEqual(record["resolution"], "Operator interpretation.")

    def test_17d_leave_open_preview_shows_the_blocker_retained(self):
        result = self.preview(ai.CONTRADICTION_RULING,
                              **self.ruling_kwargs(self.contradiction_id, ruling="leave_open"))
        self.assertIn("BLOCKING_CONTRADICTION|%s" % self.contradiction_id,
                      result["blockersRetained"])
        self.assertEqual(result["blockersRemoved"], [])
        self.assertFalse(result["eligibilityChanges"])
        self.assertIsNone(result["proposedRecord"]["resolution"])

    def test_17e_modified_contradiction_after_preview_blocks_commit(self):
        preview = self.preview(ai.CONTRADICTION_RULING,
                               **self.ruling_kwargs(self.contradiction_id))
        ai._record_contradiction_ruling(self.repo.root, self.contradiction_id, "leave_open",
                                        OPERATOR, LATER, "Someone else reviewed it first.")
        with self.assertRaises(evc.EvidenceValidationError) as ctx:
            self.commit(ai.CONTRADICTION_RULING, preview["previewToken"],
                        **self.ruling_kwargs(self.contradiction_id))
        self.assertIn("material state changed after preview", str(ctx.exception))

    def test_17f_invalid_contradiction_target_fails_at_preview(self):
        with self.assertRaises(evc.EvidenceValidationError):
            self.preview(ai.CONTRADICTION_RULING,
                         **self.ruling_kwargs("XCONTRA|99999999|999"))


# ===========================================================================
# G. Downstream stays unreachable (conditions 19, 20)
# ===========================================================================

class TestNoDownstreamEffects(PreviewTestCase):

    def _full_preview_commit_flow(self):
        contradiction = self.repo.add_blocking_contradiction(CORPUS_A)
        for action, kwargs, now in (
            (ai.DIRECT_TRADER_CLARIFICATION, self.clarify_kwargs(), FIXED_NOW),
            (ai.QUESTION_ADJUDICATION, self.accept_kwargs(), FIXED_NOW),
            (ai.CONTRADICTION_RULING, self.ruling_kwargs(contradiction["contradictionId"]), LATER),
        ):
            preview = self.preview(action, now=now, **kwargs)
            self.commit(action, preview["previewToken"], now=now, **kwargs)
        return self.repo.reevaluate(CORPUS_A)

    def test_19_no_rule_candidate_proposal_is_created(self):
        result = self._full_preview_commit_flow()
        self.assertEqual(result["eligibilityStatus"], ru.ELIGIBLE)
        self.assertEqual(self.repo.count("proposals"), 0)

    def test_20_no_unintended_evidence_links_are_created(self):
        before = self.repo.count("links")
        self._full_preview_commit_flow()
        self.assertEqual(self.repo.count("links"), before)

    def test_claims_remain_byte_identical_through_the_whole_flow(self):
        before = self.repo.raw_bytes("claims")
        self._full_preview_commit_flow()
        self.assertEqual(self.repo.raw_bytes("claims"), before)

    def test_no_strategy_backtest_or_paper_artifact(self):
        self._full_preview_commit_flow()
        self.assertEqual(set(os.listdir(self.repo.root)) - set(TwoCorpusRepo.DIRS), set())
        self.assertEqual(self.repo.count("blueprints"), 0)

    def test_preview_and_commit_cannot_reach_the_proposal_pipeline(self):
        referenced = module_identifiers("answer_intake.py")
        for forbidden in ("extraction_pipeline", "run_post_annotation_pipeline",
                          "rule_candidate_proposals", "propose_rule_candidate",
                          "link_evidence_to_claim", "recompute_claim_confidence",
                          "strategy_blueprint", "backtest", "paper_trade"):
            self.assertNotIn(forbidden, referenced, forbidden)

    def test_corpus_b_is_untouched_by_a_full_flow_in_a(self):
        before = self.repo.reevaluate(CORPUS_B)
        self._full_preview_commit_flow()
        after = self.repo.reevaluate(CORPUS_B)
        self.assertEqual(after["blockerKeys"], before["blockerKeys"])
        self.assertEqual(self.question_record(CORPUS_B)["answerStatus"], "unanswered")


# ===========================================================================
# H. Token construction
# ===========================================================================

class TestTokenConstruction(PreviewTestCase):

    def test_material_parts_are_declared_and_cannot_drift(self):
        self.assertEqual(
            set(ai._MATERIAL_PARTS),
            {"action", "targetType", "targetId", "targetRecord", "corpusTraderId",
             "evidence", "sources", "plannedIds"})

    def test_token_is_a_sha256_hex_digest(self):
        token = self.preview(ai.QUESTION_ADJUDICATION, **self.accept_kwargs())["previewToken"]
        self.assertEqual(len(token), 64)
        int(token, 16)

    def test_distinct_actions_produce_distinct_tokens(self):
        tokens = {
            self.preview(ai.QUESTION_ADJUDICATION, **self.accept_kwargs())["previewToken"],
            self.preview(ai.QUESTION_ADJUDICATION,
                         **self.accept_kwargs(decision="rejected"))["previewToken"],
            self.preview(ai.QUESTION_ADJUDICATION,
                         **self.accept_kwargs(corpus=CORPUS_B))["previewToken"],
            self.preview(ai.DIRECT_TRADER_CLARIFICATION, **self.clarify_kwargs())["previewToken"],
        }
        self.assertEqual(len(tokens), 4)


# ===========================================================================
# I. MOGO-020 Step 5.3.1 regression -- the direct-write bypass stays closed
#
# The Step 5 commit gate found that the three `record_*` writers were public
# and would write a governed research decision with no preview and no token --
# precisely the stale-approval hazard the Step 4 boundary exists to prevent.
# These tests exist so that bypass can never be reopened silently.
# ===========================================================================

class TestNoPublicDirectWriteBypass(PreviewTestCase):

    _RENAMED = ("record_question_adjudication",
                "record_direct_trader_clarification",
                "record_contradiction_ruling")

    def test_old_public_writers_no_longer_exist(self):
        for name in self._RENAMED:
            self.assertFalse(hasattr(ai, name),
                             "%s is public again -- the Step 5.3.1 bypass has reopened" % name)
            self.assertTrue(hasattr(ai, "_" + name),
                            "_%s should still exist as private implementation" % name)

    def test_the_only_public_mutating_callables_are_commit(self):
        """Every public callable is either read-only, pure, or commit()."""
        import ast
        with open(os.path.join(SCRIPTS_DIR, "answer_intake.py"), "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
        public = {n.name for n in tree.body
                  if isinstance(n, ast.FunctionDef) and not n.name.startswith("_")}
        # preview/reevaluate are read-only; blocker_key/preview_token are pure;
        # main is the CLI, which enforces --preview XOR --commit-token.
        self.assertEqual(
            public, {"preview", "commit", "reevaluate", "blocker_key", "preview_token", "main"})

    def test_no_public_callable_writes_except_commit(self):
        """Behavioural: call every public read-only entry point and prove the
        evidence root is byte-identical afterwards."""
        snapshot = self.repo.snapshot_all()
        self.preview(ai.QUESTION_ADJUDICATION, **self.accept_kwargs())
        ai.reevaluate(self.repo.root, CORPUS_A, approved_destinations=NO_DESTINATIONS)
        ai.blocker_key({"blockerType": "BLOCKING_QUESTION", "questionId": "EQ|1|1"})
        self.assertEqual(self.repo.snapshot_all(), snapshot)

    def test_private_writers_are_still_fully_validated(self):
        """Making them private must not have weakened them: the private path
        still refuses a non-human actor and foreign-corpus evidence."""
        for kwargs in ({"reviewer": "pipeline"},
                       {"evidenceIds": [self.repo.answer_evidence_id(CORPUS_B)]}):
            with self.assertRaises(evc.EvidenceValidationError):
                ai._record_question_adjudication(
                    self.repo.root, **dict(
                        {"questionId": self.repo.question_id(CORPUS_A), "decision": "accepted",
                         "reviewer": REVIEWER, "now": FIXED_NOW,
                         "evidenceIds": [self.repo.answer_evidence_id(CORPUS_A)]}, **kwargs))
        self.assertEqual(self.question_record()["answerStatus"], "unanswered")

    def test_supported_cli_cannot_perform_a_bare_direct_write(self):
        """argparse must reject a mutating subcommand that names neither side
        of the boundary. SystemExit(2) is argparse's usage error."""
        for argv in (["--evidence-root", self.repo.root, "adjudicate",
                      "--question-id", self.repo.question_id(CORPUS_A),
                      "--decision", "accepted", "--reviewer", REVIEWER],
                     ["--evidence-root", self.repo.root, "rule-contradiction",
                      "--contradiction-id", "XCONTRA|20260813|001",
                      "--ruling", "resolved", "--operator", OPERATOR,
                      "--rationale", "x"]):
            with open(os.devnull, "w") as devnull:
                stderr, sys.stderr = sys.stderr, devnull
                try:
                    with self.assertRaises(SystemExit) as ctx:
                        ai.main(argv)
                finally:
                    sys.stderr = stderr
            self.assertEqual(ctx.exception.code, 2)
        self.assertEqual(self.question_record()["answerStatus"], "unanswered")

    def test_the_supported_path_still_works_end_to_end(self):
        preview = self.preview(ai.QUESTION_ADJUDICATION, **self.accept_kwargs())
        result = self.commit(ai.QUESTION_ADJUDICATION, preview["previewToken"],
                             **self.accept_kwargs())
        self.assertEqual(result["outcome"], ai.APPLIED)
        self.assertEqual(self.question_record()["answerStatus"], "answered")
        self.assertEqual(result["reevaluation"]["eligibilityStatus"], ru.ELIGIBLE)

    def test_the_supported_path_still_fails_closed_on_stale_state(self):
        preview = self.preview(ai.QUESTION_ADJUDICATION, **self.accept_kwargs())
        # Material state moves on underneath the reviewed snapshot.
        ai._record_question_adjudication(
            self.repo.root, self.repo.question_id(CORPUS_A), "uncertain", REVIEWER, LATER,
            rationale="Someone else looked first.")
        with self.assertRaises(evc.EvidenceValidationError) as ctx:
            self.commit(ai.QUESTION_ADJUDICATION, preview["previewToken"],
                        **self.accept_kwargs())
        self.assertIn("material state changed after preview", str(ctx.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)

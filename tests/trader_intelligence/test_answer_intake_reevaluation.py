#!/usr/bin/env python3
"""MOGO-020 Step 3 -- deterministic post-intake reevaluation test suite.

Pure stdlib (unittest). Fully offline, deterministic. Run with:

    python3 -m unittest tests.trader_intelligence.test_answer_intake_reevaluation -v

EVERY test builds a throwaway two-corpus synthetic evidence root in a temp
directory. Nothing here reads or writes docs/trader-intelligence/evidence/, and
nothing here touches XCONTRA|20260728|001, EQ|20260727|015, the 281 production
questions, ALEX, TJR authority or any strategy file.

WHAT THESE TESTS PROVE

    A governed human decision recorded through the Step 2 intake path changes
    what the EXISTING Step 2/3/4 evaluators say -- and changes nothing else.

    Expected eligibility outcomes are NEVER hard-coded against a copy of the
    rules. Every assertion reads research_understanding.eligibility()'s own
    output, so the test proves the existing evaluator caused the result.
"""
import ast
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
import evidence_common as evc             # noqa: E402
import evidence_registry as reg           # noqa: E402
import evidence_questions as eqs          # noqa: E402
import research_understanding as ru       # noqa: E402
import validate_evidence as ve            # noqa: E402
import answer_intake as ai                # noqa: E402

FIXED_NOW = datetime(2026, 8, 13, 12, 0, 0, tzinfo=timezone.utc)
LATER = datetime(2026, 8, 13, 13, 0, 0, tzinfo=timezone.utc)

REVIEWER = "reviewer:joemogollon"
OPERATOR = "operator:joemogollon"

CORPUS_A = "SYNTHALPHA"
CORPUS_B = "SYNTHBETA"

# The five rule categories research_understanding derives as REQUIRED from
# knowledge_gaps. Read from the evaluator itself so the fixture cannot drift
# away from what the evaluator actually requires.
REQUIRED = ru.REQUIRED_RULE_CATEGORIES

# No acquisition surface is consulted: the planner is given an explicit empty
# approved-destination map so routing is deterministic and offline.
NO_DESTINATIONS = {}


def read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def module_identifiers(filename):
    """Every name a module actually references -- imports, bare names and
    attribute names -- collected from its AST.

    Structural rather than textual: a module may safely DOCUMENT the pipeline
    it refuses to call, and this must not be confused with calling it.
    """
    with open(os.path.join(SCRIPTS_DIR, filename), "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
                if alias.asname:
                    names.add(alias.asname)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module.split(".")[0])
            for alias in node.names:
                names.add(alias.name)
                if alias.asname:
                    names.add(alias.asname)
    return names


class TwoCorpusRepo:
    """Two isolated synthetic corpora, each with all five REQUIRED rule
    categories fully supported by direct_explicit evidence, and each carrying
    exactly one blocking EvidenceQuestion.

    Both corpora therefore start BLOCKED for one identifiable reason each, so a
    decision applied to one is visible and a decision NOT applied to the other
    is equally visible.
    """

    DIRS = ("sources", "items", "claims", "links", "contradictions", "lifecycle", "reports",
            "intake", "segments", "annotations", "questions", "proposals", "review-queue",
            "gaps", "hypotheses", "profiles", "blueprints")

    def __init__(self):
        self.root = tempfile.mkdtemp(prefix="mogo020_reeval_test_")
        for name in self.DIRS:
            os.makedirs(os.path.join(self.root, name), exist_ok=True)
        d = ai._dirs(self.root)
        for key, value in d.items():
            setattr(self, key.replace("-", "_") + "_dir", value)

        self.corpus = {}
        for trader in (CORPUS_A, CORPUS_B):
            self.corpus[trader] = self._build_corpus(trader)

    def _build_corpus(self, trader):
        source = reg.register_source(
            self.sources_dir, self.lifecycle_dir, "transcript", "owner", FIXED_NOW,
            traderId=trader, title="Synthetic %s transcript" % trader,
            provenanceStatus="partially_verified")

        claims, items = {}, {}
        for category in REQUIRED:
            claim = reg.register_claim(
                self.claims_dir, self.lifecycle_dir, category,
                "%s stated rule for %s." % (trader, category), "owner", FIXED_NOW,
                traderId=trader)
            item = reg.register_evidence_item(
                self.items_dir, self.sources_dir, self.lifecycle_dir, source["sourceId"],
                "explicit_statement", "high", "owner", FIXED_NOW,
                exactExcerpt="%s said the rule for %s out loud." % (trader, category),
                directness="direct_explicit", extractionCertainty="high")
            # Fixture setup only. The intake path itself never creates links --
            # that is separately asserted in every scenario below.
            reg.link_evidence_to_claim(
                self.links_dir, self.items_dir, self.claims_dir, self.lifecycle_dir,
                item["evidenceId"], claim["claimId"], "supports", "owner", FIXED_NOW)
            claims[category] = claim
            items[category] = item

        # A non-rule claim, so a contradiction can implicate exactly one
        # REQUIRED category rather than two.
        definition = reg.register_claim(
            self.claims_dir, self.lifecycle_dir, "definition",
            "%s definition of the traded structure." % trader, "owner", FIXED_NOW,
            traderId=trader)
        definition_item = reg.register_evidence_item(
            self.items_dir, self.sources_dir, self.lifecycle_dir, source["sourceId"],
            "explicit_statement", "high", "owner", FIXED_NOW,
            exactExcerpt="%s defined the structure explicitly." % trader,
            directness="direct_explicit", extractionCertainty="high")
        reg.link_evidence_to_claim(
            self.links_dir, self.items_dir, self.claims_dir, self.lifecycle_dir,
            definition_item["evidenceId"], definition["claimId"], "supports", "owner", FIXED_NOW)

        # Unlinked, provenance-complete, in-corpus evidence: the material a
        # human may later cite as the answer to the blocking question.
        answer_evidence = reg.register_evidence_item(
            self.items_dir, self.sources_dir, self.lifecycle_dir, source["sourceId"],
            "explicit_statement", "high", "owner", FIXED_NOW,
            exactExcerpt="%s answered the entry-trigger question directly." % trader,
            directness="direct_explicit", extractionCertainty="high")

        question = eqs.create_question(
            self.questions_dir, FIXED_NOW, "unclear_scope",
            "What exactly triggers entry for %s?" % trader, "high",
            "Synthetic fixture blocker.", "blocks_rule_candidate",
            claimId=claims["entry_rule"]["claimId"])

        return {"traderId": trader, "source": source, "claims": claims, "items": items,
                "definition": definition, "answerEvidence": answer_evidence,
                "question": question}

    # --- fixture mutators (setup, never the code under test) -----------

    def add_blocking_contradiction(self, trader):
        c = self.corpus[trader]
        return reg.create_contradiction(
            self.contradictions_dir, self.claims_dir, self.lifecycle_dir,
            c["claims"]["entry_rule"]["claimId"], c["definition"]["claimId"],
            "DEFINITIONAL", "blocking", "owner", FIXED_NOW,
            rationale="Synthetic fixture contradiction.")

    def cleanup(self):
        shutil.rmtree(self.root, ignore_errors=True)

    # --- inspection helpers -------------------------------------------

    def reevaluate(self, trader):
        return ai.reevaluate(self.root, trader, approved_destinations=NO_DESTINATIONS)

    def raw_bytes(self, *dir_names):
        out = {}
        for name in dir_names:
            for path in sorted(globmod.glob(os.path.join(self.root, name, "*.json"))):
                with open(path, "rb") as f:
                    out["%s/%s" % (name, os.path.basename(path))] = f.read()
        return out

    def snapshot_all(self):
        return self.raw_bytes(*self.DIRS)

    def count(self, name):
        return len(globmod.glob(os.path.join(self.root, name, "*.json")))

    def load_all(self, name):
        return [read_json(p) for p in
                sorted(globmod.glob(os.path.join(self.root, name, "*.json")))]

    def question_events(self, questionId):
        return ai._events_for(self.lifecycle_dir, "EVIDENCE_QUESTION", questionId)

    def contradiction_record(self, contradictionId):
        return read_json(os.path.join(
            self.contradictions_dir,
            evc.contradiction_id_to_filename(contradictionId)))

    def question_id(self, trader):
        return self.corpus[trader]["question"]["questionId"]

    def answer_evidence_id(self, trader):
        return self.corpus[trader]["answerEvidence"]["evidenceId"]


class ReevaluationTestCase(unittest.TestCase):
    def setUp(self):
        self.repo = TwoCorpusRepo()
        self.addCleanup(self.repo.cleanup)

    def accept_a(self, now=FIXED_NOW):
        return ai._record_question_adjudication(
            self.repo.root, self.repo.question_id(CORPUS_A), "accepted", REVIEWER, now,
            evidenceIds=[self.repo.answer_evidence_id(CORPUS_A)],
            rationale="The educator states the trigger explicitly here.")

    def question_blocker_keys(self, result, trader):
        return [k for k in result["blockerKeys"]
                if k.endswith(self.repo.question_id(trader))]


# ===========================================================================
# A. Baseline -- the fixture blocks for exactly the reason we think it does
# ===========================================================================

class TestFixtureBaseline(ReevaluationTestCase):

    def test_both_corpora_start_blocked_by_their_own_question(self):
        for trader in (CORPUS_A, CORPUS_B):
            result = self.repo.reevaluate(trader)
            self.assertEqual(result["eligibilityStatus"], ru.BLOCKED, trader)
            self.assertIn("BLOCKING_QUESTION|%s" % self.repo.question_id(trader),
                          result["blockerKeys"], trader)

    def test_entry_rule_is_ambiguous_because_of_the_blocking_question(self):
        result = self.repo.reevaluate(CORPUS_A)
        categories = result["eligibility"]["categories"]
        self.assertEqual(categories["entry_rule"]["status"], ru.AMBIGUOUS)
        # Every other REQUIRED category is already supported, so the question
        # is the only thing standing between this corpus and eligibility.
        for name in REQUIRED:
            if name != "entry_rule":
                self.assertEqual(categories[name]["status"], ru.SUPPORTED, name)

    def test_routing_reflects_the_unresolved_gap(self):
        result = self.repo.reevaluate(CORPUS_A)
        items = {i["blockerId"]: i for i in result["plan"]["items"]}
        self.assertIn(self.repo.question_id(CORPUS_A), items)
        self.assertEqual(items[self.repo.question_id(CORPUS_A)]["autonomy"], ru.HUMAN_INPUT)

    def test_reevaluation_is_read_only(self):
        before = self.repo.snapshot_all()
        self.repo.reevaluate(CORPUS_A)
        self.repo.reevaluate(CORPUS_B)
        self.assertEqual(self.repo.snapshot_all(), before)


# ===========================================================================
# B. Accepted answer -> the existing evaluator clears the blocker
# ===========================================================================

class TestAcceptedReevaluation(ReevaluationTestCase):

    def test_accepted_answer_clears_exactly_that_blocker(self):
        before = self.repo.reevaluate(CORPUS_A)
        self.assertTrue(self.question_blocker_keys(before, CORPUS_A))

        self.accept_a()

        after = self.repo.reevaluate(CORPUS_A)
        self.assertEqual(self.question_blocker_keys(after, CORPUS_A), [])
        self.assertLess(after["blockerCount"], before["blockerCount"])
        # One unanswered question blocks in TWO distinct ways: as a
        # BLOCKING_QUESTION in its own right, and by making its claim's rule
        # category AMBIGUOUS. Accepting the answer clears both, and the
        # existing evaluator -- not this test -- then reports ELIGIBLE.
        self.assertEqual(sorted(before["blockerKeys"]),
                         ["BLOCKING_QUESTION|%s" % self.repo.question_id(CORPUS_A),
                          "REQUIRED_CATEGORY_AMBIGUOUS|entry_rule"])
        self.assertEqual(after["blockerCount"], 0)
        self.assertEqual(after["eligibilityStatus"], ru.ELIGIBLE)

    def test_accepted_answer_makes_the_category_supported(self):
        self.assertEqual(self.repo.reevaluate(CORPUS_A)["eligibility"]
                         ["categories"]["entry_rule"]["status"], ru.AMBIGUOUS)
        self.accept_a()
        self.assertEqual(self.repo.reevaluate(CORPUS_A)["eligibility"]
                         ["categories"]["entry_rule"]["status"], ru.SUPPORTED)

    def test_understanding_view_no_longer_lists_the_question_as_unresolved(self):
        after = self.repo.reevaluate(CORPUS_A)  # before acceptance
        entry = after["view"]["ruleCategories"]["entry_rule"][0]
        self.assertIn(self.repo.question_id(CORPUS_A),
                      [q["questionId"] for q in entry["unresolvedQuestions"]])
        self.accept_a()
        entry = self.repo.reevaluate(CORPUS_A)["view"]["ruleCategories"]["entry_rule"][0]
        self.assertEqual([q["questionId"] for q in entry["unresolvedQuestions"]], [])

    def test_routing_drops_the_resolved_item(self):
        self.accept_a()
        result = self.repo.reevaluate(CORPUS_A)
        self.assertNotIn(self.repo.question_id(CORPUS_A),
                         [i["blockerId"] for i in result["plan"]["items"]])

    def test_unrelated_blockers_are_untouched(self):
        self.repo.add_blocking_contradiction(CORPUS_A)
        before = self.repo.reevaluate(CORPUS_A)
        contradiction_keys = [k for k in before["blockerKeys"]
                              if k.startswith("BLOCKING_CONTRADICTION")]
        self.assertTrue(contradiction_keys)
        self.accept_a()
        after = self.repo.reevaluate(CORPUS_A)
        # The question blocker is gone; the contradiction blocker is not.
        self.assertEqual(self.question_blocker_keys(after, CORPUS_A), [])
        self.assertEqual([k for k in after["blockerKeys"]
                          if k.startswith("BLOCKING_CONTRADICTION")], contradiction_keys)
        self.assertEqual(after["eligibilityStatus"], ru.BLOCKED)


# ===========================================================================
# C. No status inflation -- rejected and uncertain
# ===========================================================================

class TestNoStatusInflation(ReevaluationTestCase):

    def test_rejected_keeps_the_blocker_and_the_routing_item(self):
        before = self.repo.reevaluate(CORPUS_A)
        ai._record_question_adjudication(
            self.repo.root, self.repo.question_id(CORPUS_A), "rejected", REVIEWER, FIXED_NOW,
            evidenceIds=[self.repo.answer_evidence_id(CORPUS_A)],
            rationale="Does not answer the question.")
        after = self.repo.reevaluate(CORPUS_A)
        self.assertEqual(after["blockerKeys"], before["blockerKeys"])
        self.assertEqual(after["eligibilityStatus"], ru.BLOCKED)
        self.assertEqual(after["eligibility"]["categories"]["entry_rule"]["status"], ru.AMBIGUOUS)
        self.assertIn(self.repo.question_id(CORPUS_A),
                      [i["blockerId"] for i in after["plan"]["items"]])

    def test_uncertain_does_not_produce_a_fully_answered_state(self):
        before = self.repo.reevaluate(CORPUS_A)
        ai._record_question_adjudication(
            self.repo.root, self.repo.question_id(CORPUS_A), "uncertain", REVIEWER, FIXED_NOW,
            evidenceIds=[self.repo.answer_evidence_id(CORPUS_A)],
            rationale="Suggestive, not decisive.")
        after = self.repo.reevaluate(CORPUS_A)
        self.assertEqual(after["blockerKeys"], before["blockerKeys"])
        self.assertEqual(after["eligibilityStatus"], ru.BLOCKED)

    def test_uncertain_preserves_researching_semantics_in_the_view(self):
        ai._record_question_adjudication(
            self.repo.root, self.repo.question_id(CORPUS_A), "uncertain", REVIEWER, FIXED_NOW,
            evidenceIds=[self.repo.answer_evidence_id(CORPUS_A)], rationale="Partial.")
        entry = self.repo.reevaluate(CORPUS_A)["view"]["ruleCategories"]["entry_rule"][0]
        question = [q for q in entry["unresolvedQuestions"]
                    if q["questionId"] == self.repo.question_id(CORPUS_A)][0]
        self.assertEqual(question["answerStatus"], "partially_answered")
        self.assertEqual(question["researchStatus"], "researching")

    def test_neither_rejected_nor_uncertain_makes_the_corpus_eligible(self):
        for decision in ("rejected", "uncertain"):
            repo = TwoCorpusRepo()
            self.addCleanup(repo.cleanup)
            ai._record_question_adjudication(
                repo.root, repo.question_id(CORPUS_A), decision, REVIEWER, FIXED_NOW,
                evidenceIds=[repo.answer_evidence_id(CORPUS_A)], rationale="x")
            result = ai.reevaluate(repo.root, CORPUS_A, approved_destinations=NO_DESTINATIONS)
            self.assertEqual(result["eligibilityStatus"], ru.BLOCKED, decision)


# ===========================================================================
# D. Contradiction ruling reevaluation
# ===========================================================================

class TestContradictionRulingReevaluation(ReevaluationTestCase):

    def setUp(self):
        super().setUp()
        self.contradiction = self.repo.add_blocking_contradiction(CORPUS_A)
        self.contradiction_id = self.contradiction["contradictionId"]
        # Remove the question blocker so the contradiction is the variable
        # under study.
        self.accept_a()

    def _rule(self, ruling, **kwargs):
        return ai._record_contradiction_ruling(
            self.repo.root, self.contradiction_id, ruling, OPERATOR, LATER,
            kwargs.pop("rationale", "Operator ruling on a synthetic contradiction."), **kwargs)

    def test_before_ruling_the_contradiction_blocks(self):
        before = self.repo.reevaluate(CORPUS_A)
        self.assertEqual(before["eligibilityStatus"], ru.BLOCKED)
        self.assertIn("BLOCKING_CONTRADICTION|%s" % self.contradiction_id, before["blockerKeys"])
        self.assertEqual(before["eligibility"]["categories"]["entry_rule"]["status"], ru.CONFLICTED)

    def test_resolved_ruling_clears_the_contradiction_blocker(self):
        self._rule("resolved")
        after = self.repo.reevaluate(CORPUS_A)
        self.assertNotIn("BLOCKING_CONTRADICTION|%s" % self.contradiction_id, after["blockerKeys"])
        self.assertEqual(after["eligibility"]["categories"]["entry_rule"]["status"], ru.SUPPORTED)
        self.assertEqual(after["eligibilityStatus"], ru.ELIGIBLE)

    def test_scope_qualified_ruling_also_stops_blocking(self):
        self._rule("scope_qualified", scopeOverlap="partial")
        after = self.repo.reevaluate(CORPUS_A)
        self.assertNotIn("BLOCKING_CONTRADICTION|%s" % self.contradiction_id, after["blockerKeys"])
        self.assertEqual(after["eligibilityStatus"], ru.ELIGIBLE)

    def test_leave_open_ruling_keeps_the_blocker(self):
        before = self.repo.reevaluate(CORPUS_A)
        self._rule("leave_open", rationale="Reviewed; not settled.")
        after = self.repo.reevaluate(CORPUS_A)
        self.assertEqual(after["blockerKeys"], before["blockerKeys"])
        self.assertEqual(after["eligibilityStatus"], ru.BLOCKED)
        self.assertEqual(after["eligibility"]["categories"]["entry_rule"]["status"], ru.CONFLICTED)

    def test_superseded_ruling_stops_blocking(self):
        self._rule("superseded")
        after = self.repo.reevaluate(CORPUS_A)
        self.assertNotIn("BLOCKING_CONTRADICTION|%s" % self.contradiction_id, after["blockerKeys"])

    def test_source_claims_unchanged_by_ruling_and_reevaluation(self):
        before = self.repo.raw_bytes("claims", "items")
        self._rule("resolved")
        self.repo.reevaluate(CORPUS_A)
        self.assertEqual(self.repo.raw_bytes("claims", "items"), before)

    def test_operator_ruling_stays_distinguishable_from_source_fact(self):
        self._rule("resolved", rationale="Operator judgement, not something either educator said.")
        record = read_json(os.path.join(
            self.repo.contradictions_dir,
            evc.contradiction_id_to_filename(self.contradiction_id)))
        # detection-time reasoning and ruling-time reasoning remain separate fields
        self.assertEqual(record["rationale"], "Synthetic fixture contradiction.")
        self.assertEqual(record["resolution"],
                         "Operator judgement, not something either educator said.")
        events = ai._events_for(self.repo.lifecycle_dir, "CONTRADICTION_RECORD",
                                self.contradiction_id)
        ruling_events = [e for e in events if e["eventType"] == "status_changed"]
        self.assertEqual(len(ruling_events), 1)
        self.assertEqual(ruling_events[0]["actor"], OPERATOR)
        self.assertEqual(ruling_events[0]["priorStatus"], "open")


# ===========================================================================
# E. Direct-trader clarification must not auto-resolve
# ===========================================================================

class TestDirectTraderDoesNotAutoResolve(ReevaluationTestCase):

    def _clarify(self):
        return ai._record_direct_trader_clarification(
            self.repo.root, self.repo.question_id(CORPUS_A), REVIEWER, FIXED_NOW,
            CORPUS_A, "The Educator",
            "Entry triggers on the first retest after the sweep, on the 5-minute chart.",
            "https://example.invalid/live-qa", "2026-08-12")

    def test_clarification_creates_preserved_candidate_evidence(self):
        result = self._clarify()
        self.assertEqual(result["outcome"], ai.APPLIED)
        item = result["evidenceItem"]
        self.assertEqual(item["directness"], "direct_explicit")
        self.assertIs(item["metadata"]["candidateOnly"], True)
        self.assertEqual(item["metadata"]["answersQuestionId"], self.repo.question_id(CORPUS_A))

    def test_clarification_alone_does_not_clear_the_blocker(self):
        before = self.repo.reevaluate(CORPUS_A)
        self._clarify()
        after = self.repo.reevaluate(CORPUS_A)
        self.assertEqual(after["blockerKeys"], before["blockerKeys"])
        self.assertEqual(after["eligibilityStatus"], ru.BLOCKED)
        self.assertEqual(after["eligibility"]["categories"]["entry_rule"]["status"], ru.AMBIGUOUS)

    def test_eligibility_does_not_treat_candidate_evidence_as_an_answer(self):
        self._clarify()
        entry = self.repo.reevaluate(CORPUS_A)["view"]["ruleCategories"]["entry_rule"][0]
        question = [q for q in entry["unresolvedQuestions"]
                    if q["questionId"] == self.repo.question_id(CORPUS_A)][0]
        self.assertEqual(question["answerStatus"], "unanswered")

    def test_only_explicit_human_acceptance_resolves_it(self):
        item = self._clarify()["evidenceItem"]
        self.assertEqual(self.repo.reevaluate(CORPUS_A)["eligibilityStatus"], ru.BLOCKED)
        ai._record_question_adjudication(
            self.repo.root, self.repo.question_id(CORPUS_A), "accepted", REVIEWER, LATER,
            evidenceIds=[item["evidenceId"]], rationale="The educator answered it directly.")
        after = self.repo.reevaluate(CORPUS_A)
        self.assertEqual(self.question_blocker_keys(after, CORPUS_A), [])
        self.assertEqual(after["eligibilityStatus"], ru.ELIGIBLE)

    def test_clarification_creates_no_link_and_no_proposal(self):
        self._clarify()
        self.repo.reevaluate(CORPUS_A)
        self.assertEqual(self.repo.count("proposals"), 0)
        # 12 fixture links (6 per corpus); the clarification adds none.
        self.assertEqual(self.repo.count("links"), 12)


# ===========================================================================
# F. Corpus isolation
# ===========================================================================

class TestCorpusIsolation(ReevaluationTestCase):

    def test_accepting_in_a_does_not_change_b(self):
        before_b = self.repo.reevaluate(CORPUS_B)
        self.accept_a()
        after_b = self.repo.reevaluate(CORPUS_B)
        self.assertEqual(after_b["blockerKeys"], before_b["blockerKeys"])
        self.assertEqual(after_b["eligibilityStatus"], ru.BLOCKED)
        self.assertEqual(after_b["eligibility"]["categories"],
                         before_b["eligibility"]["categories"])

    def test_b_question_remains_unanswered_on_disk(self):
        self.accept_a()
        path = os.path.join(self.repo.questions_dir,
                            evc.question_id_to_filename(self.repo.question_id(CORPUS_B)))
        record = read_json(path)
        self.assertEqual(record["answerStatus"], "unanswered")
        self.assertEqual(record["answerEvidenceIds"], [])

    def test_ruling_in_a_does_not_change_b(self):
        contradiction = self.repo.add_blocking_contradiction(CORPUS_A)
        before_b = self.repo.reevaluate(CORPUS_B)
        ai._record_contradiction_ruling(
            self.repo.root, contradiction["contradictionId"], "resolved", OPERATOR, LATER,
            "Ruling scoped to corpus A.")
        after_b = self.repo.reevaluate(CORPUS_B)
        self.assertEqual(after_b["blockerKeys"], before_b["blockerKeys"])

    def test_cross_corpus_evidence_cannot_answer_a_question(self):
        with self.assertRaises(evc.EvidenceValidationError) as ctx:
            ai._record_question_adjudication(
                self.repo.root, self.repo.question_id(CORPUS_A), "accepted", REVIEWER, FIXED_NOW,
                evidenceIds=[self.repo.answer_evidence_id(CORPUS_B)], rationale="x")
        self.assertIn("foreign-corpus", str(ctx.exception))
        self.assertEqual(self.repo.reevaluate(CORPUS_A)["eligibilityStatus"], ru.BLOCKED)

    def test_no_cross_corpus_link_is_introduced(self):
        self.accept_a()
        self.repo.reevaluate(CORPUS_A)
        self.repo.reevaluate(CORPUS_B)
        owners = {c["claimId"]: c.get("traderId") for c in self.repo.load_all("claims")}
        sources = {s["sourceId"]: s.get("traderId") for s in self.repo.load_all("sources")}
        items = {i["evidenceId"]: i["sourceId"] for i in self.repo.load_all("items")}
        for link in self.repo.load_all("links"):
            self.assertEqual(sources[items[link["evidenceId"]]], owners[link["claimId"]],
                             "cross-corpus link %s" % link["linkId"])


# ===========================================================================
# G. Idempotent, read-only reevaluation
# ===========================================================================

class TestReevaluationIdempotency(ReevaluationTestCase):

    def test_repeated_reevaluation_is_byte_identical_and_writes_nothing(self):
        self.accept_a()
        snapshot = self.repo.snapshot_all()
        first = self.repo.reevaluate(CORPUS_A)
        second = self.repo.reevaluate(CORPUS_A)
        third = self.repo.reevaluate(CORPUS_A)
        self.assertEqual(self.repo.snapshot_all(), snapshot)
        for later in (second, third):
            self.assertEqual(later["eligibilityStatus"], first["eligibilityStatus"])
            self.assertEqual(later["blockerKeys"], first["blockerKeys"])
            self.assertEqual(later["eligibility"], first["eligibility"])
            self.assertEqual(later["plan"], first["plan"])

    def test_reevaluation_appends_no_lifecycle_events(self):
        self.accept_a()
        before = self.repo.count("lifecycle")
        for _ in range(3):
            self.repo.reevaluate(CORPUS_A)
            self.repo.reevaluate(CORPUS_B)
        self.assertEqual(self.repo.count("lifecycle"), before)

    def test_replayed_adjudication_plus_reevaluation_is_stable(self):
        self.accept_a()
        first = self.repo.reevaluate(CORPUS_A)
        replay = self.accept_a(now=LATER)
        self.assertEqual(replay["outcome"], ai.DUPLICATE_NOOP)
        self.assertEqual(self.repo.reevaluate(CORPUS_A)["blockerKeys"], first["blockerKeys"])


# ===========================================================================
# H. The downstream strategy pipeline stays unreachable
# ===========================================================================

class TestDownstreamUnreachable(ReevaluationTestCase):

    def _full_scenario(self):
        contradiction = self.repo.add_blocking_contradiction(CORPUS_A)
        ai._record_direct_trader_clarification(
            self.repo.root, self.repo.question_id(CORPUS_A), REVIEWER, FIXED_NOW,
            CORPUS_A, "The Educator", "Entry triggers on the first retest.",
            "https://example.invalid/live-qa", "2026-08-12")
        self.repo.reevaluate(CORPUS_A)
        self.accept_a()
        self.repo.reevaluate(CORPUS_A)
        ai._record_contradiction_ruling(
            self.repo.root, contradiction["contradictionId"], "resolved", OPERATOR, LATER,
            "Ruling.")
        return self.repo.reevaluate(CORPUS_A)

    def test_full_scenario_reaches_eligible_and_still_creates_no_proposal(self):
        result = self._full_scenario()
        # The corpus becomes ELIGIBLE -- and that is the exact moment the old
        # pipeline would have auto-proposed a rule candidate. It does not.
        self.assertEqual(result["eligibilityStatus"], ru.ELIGIBLE)
        self.assertEqual(self.repo.count("proposals"), 0)

    def test_full_scenario_creates_no_unintended_links(self):
        before = self.repo.count("links")
        self._full_scenario()
        self.assertEqual(self.repo.count("links"), before)

    def test_full_scenario_leaves_claims_byte_identical(self):
        before = self.repo.raw_bytes("claims")
        self._full_scenario()
        self.assertEqual(self.repo.raw_bytes("claims"), before)

    def test_no_strategy_backtest_or_paper_artifact_is_produced(self):
        self._full_scenario()
        produced = set(os.listdir(self.repo.root))
        self.assertEqual(produced - set(TwoCorpusRepo.DIRS), set())
        for name in ("blueprints", "proposals"):
            self.assertEqual(self.repo.count(name), 0, name)

    def test_reevaluation_body_cannot_reach_the_proposal_pipeline(self):
        """Structural, via AST: every name the module actually REFERENCES.

        Immune to prose -- the module's docstrings legitimately discuss the
        backtesting and paper trading it refuses to authorize, and a plain
        string search would trip over its own safety documentation.
        """
        referenced = module_identifiers("answer_intake.py")
        for forbidden in ("extraction_pipeline", "run_post_annotation_pipeline",
                          "rule_candidate_proposals", "propose_rule_candidate",
                          "link_evidence_to_claim", "recompute_claim_confidence",
                          "strategy_blueprint", "backtest", "paper_trade",
                          "rcp", "ep"):
            self.assertNotIn(forbidden, referenced, forbidden)

    def test_reevaluation_only_calls_the_existing_evaluators(self):
        """No second eligibility/routing engine: the orchestration delegates.

        MOGO-020 Step 4 moved the evaluator chain into `_reevaluate_index()` so
        preview() can run it against an in-memory prospective index; the
        invariant is unchanged, only its location.
        """
        with open(os.path.join(SCRIPTS_DIR, "answer_intake.py"), "r", encoding="utf-8") as f:
            source = f.read()
        start = source.index("def _reevaluate_index(")
        body = source[start:source.index("\ndef ", start + 10)]
        for delegated in ("ru.corpus_view(", "ru.eligibility(", "ru.research_plan(",
                          "ru.load_gaps("):
            self.assertIn(delegated, body, delegated)
        # And the public entry point still routes through it.
        self.assertIn("_reevaluate_index(EvidenceIndex.load(evidence_root)", source)


# ===========================================================================
# I. Integrity stays clean through the whole Step 3 flow
# ===========================================================================

class TestIntegrityThroughReevaluation(ReevaluationTestCase):

    def test_integrity_clean_after_intake_and_reevaluation(self):
        contradiction = self.repo.add_blocking_contradiction(CORPUS_A)
        self.accept_a()
        ai._record_contradiction_ruling(
            self.repo.root, contradiction["contradictionId"], "scope_qualified", OPERATOR,
            LATER, "Session-scoped.", scopeOverlap="partial")
        self.repo.reevaluate(CORPUS_A)
        self.repo.reevaluate(CORPUS_B)
        report = ve.run_integrity_checks(self.repo.root, is_production=False)
        self.assertEqual(report["summary"]["ERROR"], 0, report["findings"])
        self.assertEqual(report["summary"]["FATAL"], 0, report["findings"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

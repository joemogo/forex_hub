#!/usr/bin/env python3
"""MOGO-019 Step 10 -- governed candidate-evidence search.

The properties under test:

  * IT NOMINATES, IT DOES NOT ADJUDICATE. Every result carries CANDIDATE_ONLY /
    NOT_ANSWERED / NOT_ADJUDICATED, and running the search changes no record.
  * THE CORPUS IS THE BOUNDARY. A TJR question searches TJR evidence only, and
    terminology two educators share must never pull one corpus into the other's
    results.
  * IT FAILS CLOSED on an unknown question, an already-answered question, or a
    corpus that cannot be resolved uniquely.
  * ORDERING IS STABLE AND GOVERNED-FIRST.
  * IT SURFACES THE REAL STEP 9 FINDINGS -- the acceptance criterion is that
    candidate evidence appears, NOT that any question becomes answered.
"""

import ast
import glob
import hashlib
import json
import os
import sys
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts", "trader_intelligence"))

import candidate_search as cs                     # noqa: E402
import research_understanding as ru               # noqa: E402
import rule_conformance as rc                     # noqa: E402
from query_evidence import EvidenceIndex          # noqa: E402

TJR = "TJR"
ALEX = "ALEX_G"

# The four Step 9 blockers whose answers appeared to be already in the corpus,
# plus the two structural timeframe questions.
ACCEPTANCE = ("EQ|20260727|018", "EQ|20260727|013", "EQ|20260727|003",
              "EQ|20260727|009", "EQ|20260727|012", "EQ|20260727|014")


def index():
    return EvidenceIndex.load(rc.EVIDENCE_ROOT)


def open_acceptance(idx):
    """The acceptance questions that are still UNANSWERED.

    candidate_search.search() refuses an answered question by design -- candidate
    search exists to find evidence for open questions. EQ|20260727|014 was answered
    on 2026-08-13 by the governed MOGO-020 TJR adjudication, so iterating the raw
    tuple raised SearchRefused: the corpus moving forward, not a regression. The
    tuple above is kept intact as the declared acceptance set, so if 014 is ever
    reopened it returns to these tests automatically.

    This is deliberately NOT `assertGreater(len, 0)`-free: a filter that silently
    empties would turn every loop below into a vacuous pass.
    """
    open_ids = [q for q in ACCEPTANCE
                if idx.questions[q].get("answerStatus") != "answered"]
    assert open_ids, ("every acceptance question is answered -- these loops would "
                      "pass vacuously; choose new open questions")
    return open_ids


class SearchCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.idx = index()


class TestAcceptanceCases(SearchCase):
    """Real TJR questions from MOGO-019 Step 9."""

    def test_every_acceptance_question_surfaces_candidates(self):
        for question_id in open_acceptance(self.idx):
            with self.subTest(question=question_id):
                result = cs.search(self.idx, question_id, limit=None)
                self.assertEqual(result["traderId"], TJR)
                self.assertGreater(result["candidateCount"], 0)

    def test_the_step_9_break_of_structure_evidence_is_surfaced(self):
        """`EV|...|001|020` defines break of structure; Step 9 found it by hand.

        It ranks below the governed-relationship tiers -- which is the ordering
        the design mandates -- but it MUST appear, and within the default limit.
        """
        result = cs.search(self.idx, "EQ|20260727|018", limit=None)
        ranks = {c["evidenceId"]: c["rank"] for c in result["candidates"]}
        target = "EV|EVSRC|TJR|20260727|001|020"
        self.assertIn(target, ranks)
        self.assertLessEqual(ranks[target], 10, "must survive the default limit")
        candidate = next(c for c in result["candidates"]
                         if c["evidenceId"] == target)
        self.assertIn("break structure", candidate["exactExcerpt"])

    def test_the_take_profit_evidence_ranks_first_for_the_tp_question(self):
        result = cs.search(self.idx, "EQ|20260727|003", limit=3)
        surfaced = {c["evidenceId"] for c in result["candidates"]}
        self.assertIn("EV|EVSRC|TJR|20260727|001|041", surfaced)
        self.assertIn("EV|EVSRC|TJR|20260727|001|042", surfaced)

    def test_a_required_category_question_is_marked_as_such(self):
        result = cs.search(self.idx, "EQ|20260727|013", limit=None)
        self.assertEqual(result["subjectClaimType"], "entry_rule")
        self.assertTrue(result["requiredCategory"])


class TestCorpusIsolation(SearchCase):

    def test_a_tjr_question_returns_only_tjr_evidence(self):
        alex_sources = {s["sourceId"] for s in self.idx.sources.values()
                        if s.get("traderId") == ALEX}
        for question_id in open_acceptance(self.idx):
            with self.subTest(question=question_id):
                result = cs.search(self.idx, question_id, limit=None)
                for candidate in result["candidates"]:
                    self.assertEqual(candidate["traderId"], TJR)
                    self.assertNotIn(candidate["sourceId"], alex_sources)
                    self.assertNotIn("ALEX", candidate["evidenceId"])

    def test_shared_terminology_does_not_cross_corpora(self):
        """Both educators discuss liquidity sweeps. Vocabulary is not corpus."""
        alex_question = next(
            q["questionId"] for q in self.idx.questions.values()
            if (self.idx.claims.get(q.get("claimId")) or {}).get("traderId") == ALEX
            and q.get("answerStatus") != "answered")
        result = cs.search(self.idx, alex_question, limit=None)
        self.assertEqual(result["traderId"], ALEX)
        for candidate in result["candidates"]:
            self.assertNotIn("TJR", candidate["evidenceId"])
            self.assertNotIn("TJR", candidate["sourceId"])

    def test_explicit_references_outside_the_corpus_are_dropped(self):
        idx = index()
        target = "EQ|20260727|018"
        alex_item = next(evidence_id for evidence_id, item in idx.items.items()
                         if "ALEX" in (item.get("sourceId") or ""))
        idx.questions = dict(idx.questions)
        idx.questions[target] = dict(idx.questions[target],
                                     evidenceIds=[alex_item])
        result = cs.search(idx, target, limit=None)
        surfaced = {c["evidenceId"] for c in result["candidates"]}
        self.assertNotIn(alex_item, surfaced)


class TestFailsClosed(SearchCase):

    def test_an_unknown_question_is_refused(self):
        for bad in ("EQ|GHOST|999", "", None, "not-an-id"):
            with self.subTest(question=bad):
                with self.assertRaises(cs.SearchRefused):
                    cs.search(self.idx, bad)

    def test_an_already_answered_question_is_refused(self):
        idx = index()
        target = "EQ|20260727|018"
        idx.questions = dict(idx.questions)
        idx.questions[target] = dict(idx.questions[target],
                                     answerStatus="answered")
        with self.assertRaises(cs.SearchRefused):
            cs.search(idx, target)

    def test_a_question_with_no_resolvable_trader_is_refused(self):
        idx = index()
        target = "EQ|20260727|018"
        idx.questions = dict(idx.questions)
        idx.questions[target] = dict(idx.questions[target], claimId=None,
                                     sourceIds=[])
        with self.assertRaises(cs.SearchRefused):
            cs.search(idx, target)

    def test_an_ambiguous_corpus_is_refused_rather_than_picked(self):
        idx = index()
        target = "EQ|20260727|018"
        alex_source = next(s["sourceId"] for s in idx.sources.values()
                           if s.get("traderId") == ALEX)
        idx.questions = dict(idx.questions)
        idx.questions[target] = dict(idx.questions[target],
                                     sourceIds=[alex_source])
        with self.assertRaises(cs.SearchRefused) as caught:
            cs.search(idx, target)
        self.assertIn("ambiguous", str(caught.exception).lower())

    def test_an_unattributed_claim_does_not_silently_widen_the_search(self):
        idx = index()
        target = "EQ|20260727|018"
        claim_id = idx.questions[target]["claimId"]
        idx.claims = dict(idx.claims)
        idx.claims[claim_id] = dict(idx.claims[claim_id], traderId=None)
        idx.questions = dict(idx.questions)
        idx.questions[target] = dict(idx.questions[target], sourceIds=[])
        with self.assertRaises(cs.SearchRefused):
            cs.search(idx, target)


class TestDeterministicRanking(SearchCase):

    def test_two_runs_are_byte_identical(self):
        a = json.dumps(cs.search(index(), "EQ|20260727|009", limit=None),
                       sort_keys=True)
        b = json.dumps(cs.search(index(), "EQ|20260727|009", limit=None),
                       sort_keys=True)
        self.assertEqual(a, b)

    def test_governed_relationships_rank_above_lexical_ones(self):
        for question_id in open_acceptance(self.idx):
            with self.subTest(question=question_id):
                result = cs.search(self.idx, question_id, limit=None)
                ranks = [cs._TIER_RANK[c["tier"]] for c in result["candidates"]]
                self.assertEqual(ranks, sorted(ranks))

    def test_rank_is_contiguous_and_starts_at_one(self):
        result = cs.search(self.idx, "EQ|20260727|018", limit=None)
        self.assertEqual([c["rank"] for c in result["candidates"]],
                         list(range(1, result["candidateCount"] + 1)))

    def test_ties_break_on_a_stable_identifier(self):
        result = cs.search(self.idx, "EQ|20260727|009", limit=None)
        groups = {}
        for candidate in result["candidates"]:
            key = (candidate["tier"], len(candidate["distinctiveTokens"]),
                   len(candidate["matchedTokens"]))
            groups.setdefault(key, []).append(candidate["evidenceId"])
        for identifiers in groups.values():
            self.assertEqual(identifiers, sorted(identifiers))

    def test_no_opaque_numeric_score_is_emitted(self):
        def walk(node):
            if isinstance(node, dict):
                for key, value in node.items():
                    self.assertNotIsInstance(value, float, key)
                    self.assertNotIn("score", key.lower())
                    self.assertNotIn("confidence", key.lower())
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)
        walk(cs.search(self.idx, "EQ|20260727|018", limit=None))

    def test_every_candidate_states_why_it_was_nominated(self):
        result = cs.search(self.idx, "EQ|20260727|018", limit=None)
        for candidate in result["candidates"]:
            self.assertTrue(candidate["reasons"])
            self.assertIn(candidate["tier"], cs.TIERS)

    def test_the_limit_truncates_without_reordering(self):
        full = cs.search(self.idx, "EQ|20260727|009", limit=None)["candidates"]
        limited = cs.search(self.idx, "EQ|20260727|009", limit=3)["candidates"]
        self.assertEqual([c["evidenceId"] for c in limited],
                         [c["evidenceId"] for c in full[:3]])


class TestNominationIsNotAdjudication(SearchCase):

    def test_every_result_is_labelled_candidate_only(self):
        """Asserted against LITERAL strings, not the module's own constants.

        Comparing to `cs.NOT_ANSWERED` would be tautological: redefining the
        constant would move both sides of the assertion together, and a mutation
        that relabelled results as ANSWERED would pass. It did, until this test
        was rewritten.
        """
        result = cs.search(self.idx, "EQ|20260727|018", limit=None)
        self.assertEqual(cs.CANDIDATE_ONLY, "CANDIDATE_ONLY")
        self.assertEqual(cs.NOT_ANSWERED, "NOT_ANSWERED")
        self.assertEqual(cs.NOT_ADJUDICATED, "NOT_ADJUDICATED")
        self.assertEqual(result["status"], "CANDIDATE_ONLY")
        self.assertEqual(result["answerStatus"], "NOT_ANSWERED")
        self.assertEqual(result["adjudicationStatus"], "NOT_ADJUDICATED")
        for candidate in result["candidates"]:
            self.assertEqual(candidate["status"], "CANDIDATE_ONLY")
            self.assertEqual(candidate["answerStatus"], "NOT_ANSWERED")
            self.assertEqual(candidate["adjudicationStatus"], "NOT_ADJUDICATED")

    def test_the_output_never_claims_to_answer_or_link(self):
        blob = json.dumps(cs.search(self.idx, "EQ|20260727|018", limit=None))
        for forbidden in ('"answerEvidenceIds"', '"linkId"', '"resolution"',
                          '"proposalId"', '"approved"', '"resolved"'):
            self.assertNotIn(forbidden, blob)

    def test_the_meaning_states_the_limit_explicitly(self):
        meaning = cs.search(self.idx, "EQ|20260727|018",
                            limit=None)["meaning"].lower()
        self.assertIn("nominates", meaning)
        self.assertIn("does not answer", meaning)


class TestNoStateChange(SearchCase):

    def test_searching_mutates_no_file(self):
        roots = [os.path.join(rc.EVIDENCE_ROOT, d)
                 for d in ("questions", "links", "items", "claims",
                           "contradictions", "proposals", "gaps")]

        def digest():
            out = {}
            for root in roots:
                for path in sorted(glob.glob(os.path.join(root, "*.json"))):
                    with open(path, "rb") as handle:
                        out[path] = hashlib.sha256(handle.read()).hexdigest()
            return out

        before = digest()
        for question_id in open_acceptance(self.idx):
            cs.render(cs.search(index(), question_id, limit=None))
        self.assertEqual(digest(), before)

    def test_no_question_becomes_answered_and_no_link_is_created(self):
        links_before = len(glob.glob(os.path.join(rc.EVIDENCE_ROOT, "links",
                                                  "*.json")))
        answered_before = sum(1 for q in index().questions.values()
                              if q.get("answerStatus") == "answered")
        for question_id in open_acceptance(self.idx):
            cs.search(index(), question_id, limit=None)
        after = index()
        self.assertEqual(sum(1 for q in after.questions.values()
                             if q.get("answerStatus") == "answered"),
                         answered_before)
        self.assertEqual(len(glob.glob(os.path.join(rc.EVIDENCE_ROOT, "links",
                                                    "*.json"))), links_before)
        # `answered_before == 0` and `links_before == 416` asserted facts about one
        # moment of the corpus, not anything searching does. Both before/after
        # comparisons above are the actual invariant and remain.

    def test_no_proposal_or_contradiction_state_changes(self):
        before = {c["contradictionId"]: (c["status"], c.get("resolution"))
                  for c in index().contradictions.values()}
        proposals_before = sorted(glob.glob(os.path.join(rc.EVIDENCE_ROOT,
                                                         "proposals", "*.json")))
        for question_id in open_acceptance(self.idx):
            cs.search(index(), question_id, limit=None)
        self.assertEqual({c["contradictionId"]: (c["status"], c.get("resolution"))
                          for c in index().contradictions.values()}, before)
        # Before/after, matching the contradiction check above. Global emptiness was a
        # proxy that broke once the first authorized rule candidates existed, and could
        # not have caught a write after that point either.
        self.assertEqual(sorted(glob.glob(os.path.join(rc.EVIDENCE_ROOT,
                                                       "proposals", "*.json"))),
                         proposals_before)

    def test_eligibility_is_unchanged_by_searching(self):
        before = ru.eligibility(ru.corpus_view(index(), TJR))
        for question_id in open_acceptance(self.idx):
            cs.search(index(), question_id, limit=None)
        after = ru.eligibility(ru.corpus_view(index(), TJR))
        self.assertEqual(after["eligibility"], before["eligibility"])
        self.assertEqual(after["blockerCount"], before["blockerCount"])
        self.assertEqual(after["eligibility"], ru.BLOCKED)
        # The two before/after comparisons above are what "unchanged by searching"
        # means; pinning the literal 17 tested the corpus instead.


class TestFirewall(SearchCase):

    MODULE = cs.__file__

    def code(self):
        with open(self.MODULE, encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        for node in ast.walk(tree):
            body = getattr(node, "body", None)
            if isinstance(body, list) and body and isinstance(
                    node, (ast.Module, ast.ClassDef, ast.FunctionDef)):
                first = body[0]
                if isinstance(first, ast.Expr) and isinstance(
                        first.value, ast.Constant) and isinstance(
                        first.value.value, str):
                    body.pop(0)
        return ast.unparse(tree)

    def test_the_module_never_writes_or_opens_a_file(self):
        code = self.code()
        for forbidden in ('"w"', "'w'", '"a"', "'a'", "open(", "os.remove",
                          "shutil", "unlink", "rmtree", "mkdir", "setattr"):
            self.assertNotIn(forbidden, code)

    def test_the_module_has_no_network_or_acquisition_path(self):
        code = self.code().lower()
        for forbidden in ("urllib", "requests", "socket", "http", "connector",
                          "transport", "acquire", "acquisition", "subprocess"):
            self.assertNotIn(forbidden, code)

    def test_the_module_imports_only_read_only_helpers(self):
        with open(self.MODULE, encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {a.name for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
        self.assertEqual(imported, {"argparse", "json", "os", "sys",
                                    "research_understanding", "rule_conformance",
                                    "query_evidence"})

    def test_no_trading_authorization_or_adjudication_identifier(self):
        with open(self.MODULE, encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, ast.Attribute):
                names.add(node.attr)
            elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                names.add(node.name)
        forbidden = {"paper", "backtest", "live", "trading", "execute",
                     "promote", "promotion", "freeze", "approve", "adjudicate",
                     "authorize", "authorization"}
        for identifier in names:
            with self.subTest(identifier=identifier):
                self.assertEqual(set(identifier.lower().split("_")) & forbidden,
                                 set())

    def test_authorization_state_is_untouched(self):
        sys.path.insert(0, os.path.join(REPO_ROOT, "platform", "src"))
        from mogo_platform.runtime import connector_authorization as gate
        before = {s: gate.APPROVED_DESTINATIONS[s]["operation"]
                  for s in gate.approved_source_ids()}
        cs.search(index(), "EQ|20260727|018", limit=None)
        self.assertEqual({s: gate.APPROVED_DESTINATIONS[s]["operation"]
                          for s in gate.approved_source_ids()}, before)
        self.assertEqual(set(before.values()), {"metadata"})

    def test_the_search_boundary_is_enforced_by_source_trader_not_text(self):
        """Corpus membership comes from a governed identifier comparison.

        Quote-insensitive: `ast.unparse` normalizes string quoting, so matching
        on a literal spelling would be brittle rather than meaningful.
        """
        code = self.code()
        self.assertTrue(
            any(form in code for form in
                ("source.get('traderId') == trader_id",
                 'source.get("traderId") == trader_id')),
            "corpus membership must be decided by traderId, not by text")


# ---------------------------------------------------------------------------
# MOGO-019 Step 11 -- claim-level candidate search
# ---------------------------------------------------------------------------

class ClaimSearchCase(SearchCase):
    """The canonical case: EQ|013's answer lives one abstraction level up."""

    EQ013 = "EQ|20260727|013"
    TARGET = "CLAIM|TJR|20260727|022"
    SUBJECT = "CLAIM|TJR|20260727|027"


class TestEQ013AcceptanceCase(ClaimSearchCase):

    def test_the_invalidation_claim_is_surfaced_first(self):
        """Step 10 could not find this; Step 11 must, and must rank it first."""
        result = cs.search_claims(self.idx, self.EQ013, limit=None)
        self.assertGreater(result["candidateCount"], 0)
        top = result["candidates"][0]
        self.assertEqual(top["claimId"], self.TARGET)
        self.assertEqual(top["claimType"], "invalidation_rule")
        self.assertEqual(top["tier"], "WANTED_CATEGORY")
        self.assertEqual(top["rank"], 1)

    def test_the_wanted_category_is_derived_from_the_question_type(self):
        result = cs.search_claims(self.idx, self.EQ013, limit=None)
        self.assertEqual(result["questionType"], "missing_invalidation")
        self.assertEqual(result["wantedCategory"], "invalidation_rule")
        self.assertIn("missing_invalidation",
                      cs.WANTED_CATEGORY_BY_QUESTION_TYPE)

    def test_the_1m_versus_5m_scope_difference_is_exposed_not_resolved(self):
        top = cs.search_claims(self.idx, self.EQ013, limit=1)["candidates"][0]
        scope = top["scopeComparison"]
        self.assertEqual(scope["timeframe"]["subject"], "1m")
        self.assertEqual(scope["timeframe"]["candidate"], "5m")
        self.assertIn("timeframe", top["scopeDifferences"])
        self.assertIn("session", top["scopeDifferences"])
        # named, never resolved
        joined = " ".join(top["reasons"]).lower()
        self.assertIn("not resolved here", joined)
        self.assertNotIn("resolution", top)
        self.assertNotIn("scopeCompatible", top)

    def test_the_subject_claim_is_never_its_own_candidate(self):
        result = cs.search_claims(self.idx, self.EQ013, limit=None)
        self.assertEqual(result["subjectClaimId"], self.SUBJECT)
        self.assertNotIn(self.SUBJECT,
                         {c["claimId"] for c in result["candidates"]})

    def test_eq013_is_not_answered_or_linked_by_searching(self):
        cs.search_claims(index(), self.EQ013, limit=None)
        after = index()
        self.assertNotEqual(after.questions[self.EQ013].get("answerStatus"),
                            "answered")
        self.assertEqual(after.questions[self.EQ013].get("answerEvidenceIds")
                         or [], [])
        self.assertEqual(len(glob.glob(os.path.join(rc.EVIDENCE_ROOT, "links",
                                                    "*.json"))), 416)


class TestScopeDifferencePreservation(ClaimSearchCase):

    def test_every_candidate_carries_a_full_scope_comparison(self):
        for question_id in ("EQ|20260727|013", "EQ|20260727|007",
                            "EQ|20260727|002"):
            with self.subTest(question=question_id):
                result = cs.search_claims(self.idx, question_id, limit=None)
                for candidate in result["candidates"]:
                    for field in cs.SCOPE_FIELDS:
                        self.assertIn(field, candidate["scopeComparison"])
                        self.assertIn("subject",
                                      candidate["scopeComparison"][field])
                        self.assertIn("candidate",
                                      candidate["scopeComparison"][field])

    def test_a_difference_is_recorded_whenever_the_values_differ(self):
        for question_id in ("EQ|20260727|013", "EQ|20260727|007"):
            with self.subTest(question=question_id):
                for candidate in cs.search_claims(self.idx, question_id,
                                                  limit=None)["candidates"]:
                    scope = candidate["scopeComparison"]
                    expected = sorted(field for field in cs.SCOPE_FIELDS
                                      if scope[field]["subject"]
                                      != scope[field]["candidate"])
                    self.assertEqual(sorted(candidate["scopeDifferences"]),
                                     expected)

    def test_scope_fields_are_only_the_ones_the_corpus_populates(self):
        """Designing around empty fields would be designing around nothing."""
        self.assertEqual(cs.SCOPE_FIELDS, ("timeframe", "session"))
        tjr_claims = [c for c in self.idx.claims.values()
                      if c.get("traderId") == TJR]
        for empty in ("marketSymbol", "marketCondition", "subjectEntityType"):
            self.assertEqual(sum(1 for c in tjr_claims if c.get(empty)), 0)


class TestClaimCorpusIsolation(ClaimSearchCase):

    def test_a_tjr_question_returns_only_tjr_claims(self):
        for question_id in ("EQ|20260727|013", "EQ|20260727|007",
                            "EQ|20260727|018"):
            with self.subTest(question=question_id):
                result = cs.search_claims(self.idx, question_id, limit=None)
                for candidate in result["candidates"]:
                    self.assertEqual(candidate["traderId"], TJR)
                    self.assertNotIn("ALEX", candidate["claimId"])
                    for source_id in candidate["sourceIds"]:
                        self.assertNotIn("ALEX", source_id or "")

    def test_an_alex_question_returns_only_alex_claims(self):
        alex_question = next(
            q["questionId"] for q in self.idx.questions.values()
            if (self.idx.claims.get(q.get("claimId")) or {}).get("traderId") == ALEX
            and q.get("answerStatus") != "answered")
        result = cs.search_claims(self.idx, alex_question, limit=None)
        self.assertEqual(result["traderId"], ALEX)
        for candidate in result["candidates"]:
            self.assertNotIn("TJR", candidate["claimId"])

    def test_supporting_evidence_never_crosses_the_corpus(self):
        alex_sources = {s["sourceId"] for s in self.idx.sources.values()
                        if s.get("traderId") == ALEX}
        for candidate in cs.search_claims(self.idx, self.EQ013,
                                          limit=None)["candidates"]:
            for source_id in candidate["sourceIds"]:
                self.assertNotIn(source_id, alex_sources)

    def test_an_ambiguous_corpus_is_refused(self):
        idx = index()
        alex_source = next(s["sourceId"] for s in idx.sources.values()
                           if s.get("traderId") == ALEX)
        idx.questions = dict(idx.questions)
        idx.questions[self.EQ013] = dict(idx.questions[self.EQ013],
                                         sourceIds=[alex_source])
        with self.assertRaises(cs.SearchRefused):
            cs.search_claims(idx, self.EQ013)

    def test_unknown_and_answered_questions_are_refused(self):
        with self.assertRaises(cs.SearchRefused):
            cs.search_claims(self.idx, "EQ|GHOST|999")
        idx = index()
        idx.questions = dict(idx.questions)
        idx.questions[self.EQ013] = dict(idx.questions[self.EQ013],
                                         answerStatus="answered")
        with self.assertRaises(cs.SearchRefused):
            cs.search_claims(idx, self.EQ013)


class TestClaimRankingIsDeterministic(ClaimSearchCase):

    def test_two_runs_are_byte_identical(self):
        a = json.dumps(cs.search_claims(index(), self.EQ013, limit=None),
                       sort_keys=True)
        b = json.dumps(cs.search_claims(index(), self.EQ013, limit=None),
                       sort_keys=True)
        self.assertEqual(a, b)

    def test_structural_tiers_rank_above_lexical_ones(self):
        for question_id in ("EQ|20260727|013", "EQ|20260727|007",
                            "EQ|20260727|009"):
            with self.subTest(question=question_id):
                ranks = [cs._CLAIM_TIER_RANK[c["tier"]] for c in
                         cs.search_claims(self.idx, question_id,
                                          limit=None)["candidates"]]
                self.assertEqual(ranks, sorted(ranks))

    def test_ties_break_on_the_claim_identifier(self):
        candidates = cs.search_claims(self.idx, "EQ|20260727|007",
                                      limit=None)["candidates"]
        groups = {}
        for candidate in candidates:
            key = (candidate["tier"], len(candidate["distinctiveTokens"]),
                   len(candidate["matchedTokens"]))
            groups.setdefault(key, []).append(candidate["claimId"])
        for identifiers in groups.values():
            self.assertEqual(identifiers, sorted(identifiers))

    def test_shared_scope_alone_does_not_nominate(self):
        """Nine TJR claims share `session`. Scope must coincide with wording."""
        for candidate in cs.search_claims(self.idx, self.EQ013,
                                          limit=None)["candidates"]:
            if candidate["tier"] == "SHARED_SCOPE":
                self.assertTrue(candidate["matchedTokens"])

    def test_no_opaque_score_is_emitted(self):
        def walk(node):
            if isinstance(node, dict):
                for key, value in node.items():
                    self.assertNotIsInstance(value, float, key)
                    self.assertNotIn("score", key.lower())
                    self.assertNotIn("confidence", key.lower())
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)
        result = cs.search_claims(self.idx, self.EQ013, limit=None)
        for candidate in result["candidates"]:
            walk({k: v for k, v in candidate.items()
                  if k != "confidenceState"})   # a governed enum, not a score


class TestClaimNominationIsNotAnswering(ClaimSearchCase):

    def test_labels_are_asserted_against_literals_not_constants(self):
        """Comparing to the module's own constants would let code and test
        mutate together -- the exact defect Step 10's mutation exposed."""
        result = cs.search_claims(self.idx, self.EQ013, limit=None)
        self.assertEqual(cs.NOT_LINKED, "NOT_LINKED")
        self.assertEqual(result["status"], "CANDIDATE_ONLY")
        self.assertEqual(result["answerStatus"], "NOT_ANSWERED")
        self.assertEqual(result["adjudicationStatus"], "NOT_ADJUDICATED")
        self.assertEqual(result["linkStatus"], "NOT_LINKED")
        for candidate in result["candidates"]:
            self.assertEqual(candidate["status"], "CANDIDATE_ONLY")
            self.assertEqual(candidate["answerStatus"], "NOT_ANSWERED")
            self.assertEqual(candidate["adjudicationStatus"], "NOT_ADJUDICATED")
            self.assertEqual(candidate["linkStatus"], "NOT_LINKED")

    def test_the_output_never_claims_an_answer_or_a_link(self):
        blob = json.dumps(cs.search_claims(self.idx, self.EQ013, limit=None))
        for forbidden in ('"answerEvidenceIds"', '"linkId"', '"resolution"',
                          '"proposalId"', '"approved"', '"resolved"',
                          '"answers"', '"validated"'):
            self.assertNotIn(forbidden, blob)

    def test_the_meaning_states_scope_is_not_resolved(self):
        meaning = cs.search_claims(self.idx, self.EQ013,
                                   limit=None)["meaning"].lower()
        self.assertIn("nominates", meaning)
        self.assertIn("does not answer", meaning)
        self.assertIn("scope difference", meaning)


class TestClaimSearchChangesNothing(ClaimSearchCase):

    QUESTIONS = ("EQ|20260727|013", "EQ|20260727|007", "EQ|20260727|002",
                 "EQ|20260727|018")

    def test_no_file_is_mutated(self):
        roots = [os.path.join(rc.EVIDENCE_ROOT, d)
                 for d in ("claims", "questions", "links", "items",
                           "contradictions", "proposals")]

        def digest():
            out = {}
            for root in roots:
                for path in sorted(glob.glob(os.path.join(root, "*.json"))):
                    with open(path, "rb") as handle:
                        out[path] = hashlib.sha256(handle.read()).hexdigest()
            return out

        before = digest()
        for question_id in self.QUESTIONS:
            cs.render_claims(cs.search_claims(index(), question_id, limit=None))
        self.assertEqual(digest(), before)

    def test_questions_claims_links_and_proposals_are_unchanged(self):
        before = index()
        answered = sum(1 for q in before.questions.values()
                       if q.get("answerStatus") == "answered")
        claims = {c["claimId"]: c.get("normalizedClaim")
                  for c in before.claims.values()}
        links_before = sorted(glob.glob(os.path.join(rc.EVIDENCE_ROOT, "links",
                                                     "*.json")))
        proposals_before = sorted(glob.glob(os.path.join(rc.EVIDENCE_ROOT,
                                                         "proposals", "*.json")))
        for question_id in self.QUESTIONS:
            cs.search_claims(index(), question_id, limit=None)
        after = index()
        # This test asks whether SEARCHING changes anything, so every assertion below
        # compares after-to-before. It previously also pinned three absolute corpus
        # snapshots -- answered==0, len(links)==416, proposals==[] -- as proxies for
        # "unchanged". Those are not invariants of searching: they are facts about one
        # moment of the corpus, and they broke on legitimate research progress (the
        # governed MOGO-020 adjudication answered EQ|20260727|014, and the first
        # authorized rule candidates were created). Each proxy was also weaker than the
        # comparison it sat next to, since it could not detect a change once the corpus
        # moved off the pinned value.
        self.assertEqual(sum(1 for q in after.questions.values()
                             if q.get("answerStatus") == "answered"), answered)
        self.assertEqual({c["claimId"]: c.get("normalizedClaim")
                          for c in after.claims.values()}, claims)
        self.assertEqual(sorted(glob.glob(os.path.join(rc.EVIDENCE_ROOT, "links",
                                                       "*.json"))), links_before)
        self.assertEqual(sorted(glob.glob(os.path.join(rc.EVIDENCE_ROOT,
                                                       "proposals", "*.json"))),
                         proposals_before)

    def test_xcontra_is_untouched(self):
        for question_id in self.QUESTIONS:
            cs.search_claims(index(), question_id, limit=None)
        record = index().contradictions["XCONTRA|20260728|001"]
        self.assertEqual(record["status"], "open")
        self.assertEqual(record["severity"], "blocking")
        self.assertIsNone(record["resolution"])

    def test_tjr_eligibility_is_unchanged(self):
        # "Unchanged" needs a before. Asserting an absolute blockerCount of 17 never
        # established that searching left eligibility alone -- it only pinned one
        # moment of the corpus, and it broke when the governed MOGO-020 adjudication
        # answered EQ|20260727|014 and legitimately retired a blocker.
        before = ru.eligibility(ru.corpus_view(index(), TJR))
        for question_id in self.QUESTIONS:
            cs.search_claims(index(), question_id, limit=None)
        result = ru.eligibility(ru.corpus_view(index(), TJR))
        self.assertEqual(result["eligibility"], "BLOCKED")
        self.assertEqual(result["blockerCount"], before["blockerCount"])
        self.assertEqual(result["eligibility"], before["eligibility"])

    def test_authorization_is_unchanged(self):
        sys.path.insert(0, os.path.join(REPO_ROOT, "platform", "src"))
        from mogo_platform.runtime import connector_authorization as gate
        before = {s: gate.APPROVED_DESTINATIONS[s]["operation"]
                  for s in gate.approved_source_ids()}
        cs.search_claims(index(), self.EQ013, limit=None)
        self.assertEqual({s: gate.APPROVED_DESTINATIONS[s]["operation"]
                          for s in gate.approved_source_ids()}, before)
        self.assertEqual(set(before.values()), {"metadata"})


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""MOGO-019 Step 2 -- the derived research-understanding view.

Six focused categories, matching the Step 1 audit:
determinism · strategy isolation · provenance chain · source-vs-inference ·
conflict/ambiguity · execution firewall.

The isolation and firewall tests are MUTATION-CHECKED where practical: a test
that cannot fail is not a proof.
"""

import ast
import copy
import glob
import hashlib
import json
import os
import sys
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts", "trader_intelligence"))

import research_understanding as ru            # noqa: E402
from query_evidence import EvidenceIndex       # noqa: E402

TJR = "TJR"
ALEX = "ALEX_G"


def index():
    return EvidenceIndex.load(ru.EVIDENCE_ROOT)


class ViewCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.idx = index()
        cls.view = ru.corpus_view(cls.idx, TJR)

    def entries(self, view=None):
        view = view or self.view
        rows = [e for v in view["ruleCategories"].values() for e in v]
        rows += [e for v in view["nonRuleClaims"].values() for e in v]
        return rows


# ---------------------------------------------------------------------------
# 1. Determinism
# ---------------------------------------------------------------------------

class TestDeterminism(ViewCase):

    def test_same_corpus_produces_byte_identical_output(self):
        a = json.dumps(ru.corpus_view(index(), TJR), sort_keys=True)
        b = json.dumps(ru.corpus_view(index(), TJR), sort_keys=True)
        self.assertEqual(a, b)

    def test_rendering_is_deterministic(self):
        self.assertEqual(ru.render(self.view), ru.render(self.view))

    def test_rule_categories_come_from_the_schema_not_a_local_copy(self):
        """The vocabulary must not be able to drift from the schema."""
        with open(os.path.join(ru.EVIDENCE_ROOT, "schema",
                               "rule-candidate-proposal.schema.json"),
                  encoding="utf-8") as handle:
            enum = json.load(handle)["properties"]["claimType"]["enum"]
        self.assertEqual(list(ru.RULE_CATEGORIES), enum)
        self.assertEqual(sorted(self.view["ruleCategories"]), sorted(enum))


# ---------------------------------------------------------------------------
# 2. Strategy isolation
# ---------------------------------------------------------------------------

class TestStrategyIsolation(ViewCase):

    def test_no_alex_claim_appears_in_the_tjr_view(self):
        for entry in self.entries():
            self.assertEqual(entry["traderId"], TJR)
            self.assertNotIn("ALEX", entry["claimId"])

    def test_no_alex_evidence_reaches_the_tjr_view(self):
        for entry in self.entries():
            for row in entry["evidence"]:
                self.assertNotIn("ALEX", row["evidenceId"])
                self.assertNotIn("ALEX", row["sourceId"] or "")

    def test_a_cross_corpus_contradiction_names_but_never_expands_the_foreign_claim(self):
        cross = self.view["crossCorpusContradictions"]
        self.assertTrue(cross, "the corpus genuinely has cross-corpus records")
        corpus_ids = {e["claimId"] for e in self.entries()}
        for record in cross:
            self.assertIn(record["corpusClaimId"], corpus_ids)
            self.assertNotIn(record["foreignClaimId"], corpus_ids)
            self.assertNotEqual(record["foreignTraderId"], TJR)
            # named, but no foreign CONTENT crossed the boundary
            self.assertNotIn("normalizedClaim", record)
            self.assertNotIn("evidence", record)

    def test_cross_trader_hypotheses_are_separated_from_corpus_hypotheses(self):
        owners = {cid: c.get("traderId") for cid, c in self.idx.claims.items()}
        for row in self.view["corpusHypotheses"]:
            self.assertEqual({owners[c] for c in row["sourceClaimIds"]}, {TJR})
        self.assertTrue(self.view["crossTraderHypotheses"])
        for row in self.view["crossTraderHypotheses"]:
            traders = {owners.get(c) for c in row["sourceClaimIds"]}
            self.assertIn(TJR, traders)
            self.assertTrue(traders - {TJR})
            self.assertTrue(row["otherTraderIds"])

    def test_string_matching_would_have_contaminated_the_view(self):
        """Why identifiers are RESOLVED rather than matched.

        Records belonging to other traders mention 'TJR' in their text. A naive
        substring filter pulls them in; resolution does not.
        """
        naive = [q for q in self.idx.questions.values() if "TJR" in json.dumps(q)]
        resolved = {q["questionId"]
                    for e in self.entries() for q in e["unresolvedQuestions"]}
        self.assertGreater(len(naive), len(resolved))
        foreign = [q for q in naive
                   if (self.idx.claims.get(q.get("claimId")) or {}).get("traderId")
                   not in (None, TJR)]
        self.assertTrue(foreign, "a foreign record does mention TJR")
        for question in foreign:
            self.assertNotIn(question["questionId"], resolved)

    def test_MUTATION_an_alex_claim_relabelled_tjr_enters_the_view(self):
        """The isolation tests must be capable of failing.

        Relabelling one ALEX claim as TJR in an in-memory copy must pull it in.
        Nothing on disk is touched.
        """
        idx = index()
        victim = next(c for c in idx.claims.values() if c.get("traderId") == ALEX)
        before = {e["claimId"] for e in self.entries()}
        idx.claims = dict(idx.claims)
        idx.claims[victim["claimId"]] = dict(victim, traderId=TJR)
        mutated = ru.corpus_view(idx, TJR)
        after = {e["claimId"] for e in self.entries(mutated)}
        self.assertIn(victim["claimId"], after)
        self.assertNotIn(victim["claimId"], before)

    def test_an_unattributed_claim_fails_closed(self):
        idx = index()
        victim = next(iter(idx.claims))
        idx.claims = dict(idx.claims)
        idx.claims[victim] = dict(idx.claims[victim], traderId=None)
        with self.assertRaises(ru.CorpusAmbiguous):
            ru.corpus_view(idx, TJR)

    def test_an_unknown_corpus_is_refused_rather_than_returned_empty(self):
        for bad in ("NOBODY", "", None):
            with self.subTest(trader=bad):
                with self.assertRaises(ru.CorpusAmbiguous):
                    ru.corpus_view(self.idx, bad)


# ---------------------------------------------------------------------------
# 3. Provenance chain
# ---------------------------------------------------------------------------

class TestProvenanceChain(ViewCase):

    def test_every_claim_traces_to_evidence_to_a_source(self):
        for entry in self.entries():
            with self.subTest(claim=entry["claimId"]):
                self.assertTrue(entry["evidence"], "claim with no evidence link")
                for row in entry["evidence"]:
                    self.assertTrue(row["present"], row["evidenceId"])
                    item = self.idx.items[row["evidenceId"]]
                    self.assertEqual(item["sourceId"], row["sourceId"])
                    self.assertIn(item["sourceId"], self.idx.sources)

    def test_extraction_method_and_certainty_are_carried_not_dropped(self):
        for entry in self.entries():
            for row in entry["evidence"]:
                self.assertIsNotNone(row["extractionMethod"])
                self.assertIsNotNone(row["extractionCertainty"])

    def test_the_raw_directness_is_preserved_alongside_the_mapped_class(self):
        """The mapping must remain auditable against the record."""
        for entry in self.entries():
            for row in entry["evidence"]:
                item = self.idx.items[row["evidenceId"]]
                self.assertEqual(row["directness"], item.get("directness"))
                self.assertEqual(row["class"],
                                 ru.classify_directness(item.get("directness")))


# ---------------------------------------------------------------------------
# 4. Source fact vs MOGO inference
# ---------------------------------------------------------------------------

class TestSourceVersusInference(ViewCase):

    def test_the_two_classes_are_never_summed(self):
        counts = self.view["sufficiency"]["evidenceClassCounts"]
        for name in ru.EVIDENCE_CLASSES:
            self.assertIn(name, counts)
        self.assertGreater(counts[ru.SOURCE_SAID], 0)

    def test_direct_and_inferred_map_to_distinct_classes(self):
        self.assertEqual(ru.classify_directness("direct_explicit"), ru.SOURCE_SAID)
        self.assertEqual(ru.classify_directness("direct_demonstrated"),
                         ru.SOURCE_SAID)
        self.assertEqual(ru.classify_directness("inferred_from_context"),
                         ru.MOGO_INFERRED)
        self.assertEqual(ru.classify_directness("derived_from_analysis"),
                         ru.MOGO_INFERRED)
        self.assertNotEqual(ru.SOURCE_SAID, ru.MOGO_INFERRED)

    def test_an_unknown_directness_fails_to_unresolved_not_to_source_said(self):
        for bad in (None, "", "something_new", "unresolved"):
            with self.subTest(directness=bad):
                self.assertEqual(ru.classify_directness(bad), ru.UNRESOLVED)

    def test_a_claim_without_direct_support_is_not_marked_source_backed(self):
        flagged = [e for e in self.entries() if not e["hasSourceSaidSupport"]]
        self.assertTrue(flagged, "the corpus genuinely contains such claims")
        for entry in flagged:
            self.assertEqual(entry["evidenceClassCounts"][ru.SOURCE_SAID], 0)

    def test_interpretation_dependent_requires_inference_and_no_source_said(self):
        for entry in self.entries():
            counts = entry["evidenceClassCounts"]
            expected = (counts[ru.SOURCE_SAID] == 0
                        and counts[ru.MOGO_INFERRED] > 0)
            self.assertEqual(entry["interpretationDependent"], expected)

    def test_hypotheses_are_never_reported_as_source_evidence(self):
        """A Hypothesis is MOGO's interpretation and must stay outside the
        evidence classes entirely."""
        evidence_ids = {row["evidenceId"]
                        for e in self.entries() for row in e["evidence"]}
        for row in self.view["corpusHypotheses"] + self.view["crossTraderHypotheses"]:
            self.assertNotIn(row["hypothesisId"], evidence_ids)


# ---------------------------------------------------------------------------
# 5. Conflict and ambiguity
# ---------------------------------------------------------------------------

class TestConflictAndAmbiguity(ViewCase):

    def test_open_contradictions_surface_and_are_not_resolved(self):
        records = (self.view["internalContradictions"]
                   + self.view["crossCorpusContradictions"])
        self.assertTrue(records)
        for record in records:
            self.assertIn(record["severity"],
                          ("cosmetic", "minor", "material", "blocking"))
            self.assertNotIn("resolution", record)

    def test_a_blocking_contradiction_remains_visibly_blocking(self):
        blocking = self.view["sufficiency"]["openBlockingCrossCorpusContradictionIds"]
        self.assertTrue(blocking, "the corpus has an open blocking contradiction")
        for cid in blocking:
            record = next(r for r in self.view["crossCorpusContradictions"]
                          if r["contradictionId"] == cid)
            self.assertEqual(record["severity"], "blocking")
            self.assertEqual(record["status"], "open")

    def test_unanswered_questions_surface_and_answered_ones_do_not(self):
        surfaced = {q["questionId"]
                    for e in self.entries() for q in e["unresolvedQuestions"]}
        self.assertTrue(surfaced)
        for qid in surfaced:
            self.assertNotEqual(self.idx.questions[qid].get("answerStatus"),
                                "answered")

    def test_blocking_questions_are_counted_separately(self):
        s = self.view["sufficiency"]
        self.assertTrue(s["blockingQuestionIds"])
        self.assertLessEqual(len(s["blockingQuestionIds"]),
                             s["unresolvedQuestionCount"])
        for qid in s["blockingQuestionIds"]:
            self.assertIn(self.idx.questions[qid]["blockingStatus"],
                          ("blocks_rule_candidate", "blocks_promotion"))

    def test_nothing_is_resolved_merged_or_dropped(self):
        """Every unanswered question on a corpus claim must appear."""
        corpus = {e["claimId"] for e in self.entries()}
        expected = {q["questionId"] for q in self.idx.questions.values()
                    if q.get("claimId") in corpus
                    and q.get("answerStatus") != "answered"}
        actual = {q["questionId"]
                  for e in self.entries() for q in e["unresolvedQuestions"]}
        self.assertEqual(actual, expected)


# ---------------------------------------------------------------------------
# 6. Sufficiency is facts, never a verdict
# ---------------------------------------------------------------------------

class TestSufficiencyIsFactsOnly(ViewCase):

    FORBIDDEN = ("ready", "readiness", "valid", "invalid", "profitable",
                 "approved", "tradable", "score", "grade", "rating",
                 "recommend", "mature", "complete", "sufficient")

    # Fields that quote the SOURCE verbatim. The educator may say "invalid" or
    # "complete" and that is evidence, not a MOGO verdict -- so the scan applies
    # to MOGO's own vocabulary, not to what it faithfully reproduces.
    VERBATIM_FIELDS = ("normalizedClaim", "exactExcerpt", "questionText",
                       "statement")

    def _mogo_vocabulary(self, node, out):
        """Every field NAME and MOGO-authored string value in the view."""
        if isinstance(node, dict):
            for key, value in node.items():
                out.append(key)
                if key not in self.VERBATIM_FIELDS:
                    self._mogo_vocabulary(value, out)
        elif isinstance(node, list):
            for value in node:
                self._mogo_vocabulary(value, out)
        elif isinstance(node, str):
            out.append(node)
        return out

    def test_no_verdict_word_appears_in_mogo_authored_vocabulary(self):
        """MOGO must state no verdict of its own.

        Word-boundary matched, because `invalidation_rule` is a legitimate
        schema category and a substring scan would flag it forever.
        """
        import re
        tokens = self._mogo_vocabulary(self.view, [])
        # The schema's own category names are vocabulary MOGO reuses, not coins.
        allowed = set(ru.RULE_CATEGORIES) | {"invalidation", "validationStatus"}
        for word in self.FORBIDDEN:
            pattern = re.compile(r"\b%s\b" % word, re.I)
            for token in tokens:
                if token in allowed:
                    continue
                with self.subTest(word=word, token=token[:60]):
                    self.assertIsNone(pattern.search(token))

    def test_verbatim_source_text_is_still_reproduced_faithfully(self):
        """The scan above must not have been satisfied by censoring the source."""
        entry = next(e for e in self.entries() if e["normalizedClaim"])
        self.assertEqual(entry["normalizedClaim"],
                         self.idx.claims[entry["claimId"]]["normalizedClaim"])
        for row in entry["evidence"]:
            self.assertEqual(row["exactExcerpt"],
                             self.idx.items[row["evidenceId"]].get("exactExcerpt"))

    def test_no_score_or_percentage_field_exists(self):
        def walk(node):
            if isinstance(node, dict):
                for key, value in node.items():
                    self.assertNotIsInstance(
                        value, float, "float %r would be a score" % (key,))
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)
        walk(self.view["sufficiency"])

    def test_present_and_missing_categories_partition_the_vocabulary(self):
        s = self.view["sufficiency"]
        self.assertEqual(sorted(s["categoriesPresent"] + s["categoriesMissing"]),
                         sorted(ru.RULE_CATEGORIES))
        self.assertFalse(set(s["categoriesPresent"]) & set(s["categoriesMissing"]))
        for name in s["categoriesMissing"]:
            self.assertEqual(self.view["ruleCategories"][name], [])

    def test_unmapped_claim_types_are_reported_not_forced_into_a_category(self):
        s = self.view["sufficiency"]
        self.assertTrue(s["nonRuleClaimTypes"])
        for name in s["nonRuleClaimTypes"]:
            self.assertNotIn(name, ru.RULE_CATEGORIES)
        self.assertEqual(s["claimCount"],
                         s["ruleCategoryClaimCount"] + s["nonRuleClaimCount"])


# ---------------------------------------------------------------------------
# 7. Execution firewall
# ---------------------------------------------------------------------------

class TestExecutionFirewall(ViewCase):

    MODULE = ru.__file__

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

    def test_the_module_never_opens_a_file_for_writing(self):
        code = self.code()
        for forbidden in ('"w"', "'w'", '"a"', "'a'", '"wb"', "'wb'",
                          "os.remove", "shutil", "unlink", "rmtree", "mkdir"):
            self.assertNotIn(forbidden, code)

    def test_the_module_names_no_executable_or_campaign_path(self):
        code = self.code()
        for forbidden in ("index.html", "docs/campaigns", "hypothesis-registry",
                          "PREREG-", "paper", "backtest", "live"):
            self.assertNotIn(forbidden.lower(), code.lower())

    def test_the_module_imports_nothing_from_the_trading_engine(self):
        with open(self.MODULE, encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {a.name for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
        self.assertEqual(imported,
                         {"argparse", "json", "os", "sys", "query_evidence"})

    def test_running_the_view_mutates_no_file_on_disk(self):
        roots = [os.path.join(ru.EVIDENCE_ROOT, d)
                 for d in ("claims", "items", "links", "questions",
                           "contradictions", "hypotheses", "sources")]
        def digest():
            out = {}
            for root in roots:
                for path in sorted(glob.glob(os.path.join(root, "*.json"))):
                    with open(path, "rb") as handle:
                        out[path] = hashlib.sha256(handle.read()).hexdigest()
            return out
        before = digest()
        ru.corpus_view(index(), TJR)
        ru.render(ru.corpus_view(index(), TJR))
        self.assertEqual(digest(), before)

    def test_the_view_carries_the_research_lane_and_never_promotes(self):
        self.assertEqual(self.view["lane"], "RESEARCH")
        self.assertEqual(self.view["promotionStatus"], "NOT_A_TRADING_RULE")
        blob = json.dumps(self.view)
        for stage in ("PAPER_APPROVED", "LIVE_APPROVED", "PRODUCTION_APPROVED",
                      "IMPLEMENTATION_APPROVED", "promotionState"):
            self.assertNotIn(stage, blob)

    def test_no_rule_candidate_proposal_record_is_created(self):
        """Step 2 produces a VIEW, not a stored proposal."""
        self.assertEqual(
            glob.glob(os.path.join(ru.EVIDENCE_ROOT, "proposals", "*.json")), [])
        self.assertNotIn("proposalId", json.dumps(self.view))


if __name__ == "__main__":
    unittest.main()

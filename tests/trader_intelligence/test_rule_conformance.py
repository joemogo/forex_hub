#!/usr/bin/env python3
"""MOGO-019 Step 7 -- Rule-2 conformance analyzer.

The property under test is NOT "the analyzer finds problems". It is:

  * IT DETECTS ADDED CONTENT. A number, time, instrument, direction or
    quantifier present in a claim and absent from every SUPPORTING excerpt is
    surfaced. Adversarial mutations of a real claim must each be caught.
  * IT USES SUPPORT RELATIONSHIPS ONLY. `contextualizes` is background, not
    support -- treating it as support is the exact error MOGO-019 Step 6's first
    pass made.
  * IT FAILS CLOSED. Missing, foreign, ambiguous or malformed support never
    produces CLEAN_MECHANICAL_MATCH.
  * CLEAN IS NOT APPROVAL. Asserted in the report, the renderer and here.
  * IT WRITES NOTHING.
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

import rule_conformance as rc                    # noqa: E402
from query_evidence import EvidenceIndex         # noqa: E402

TJR = "TJR"
ALEX = "ALEX_G"


def index():
    return EvidenceIndex.load(rc.EVIDENCE_ROOT)


def claim(text):
    return {"claimId": "CLAIM|TJR|TEST", "traderId": TJR,
            "claimType": "entry_rule", "normalizedClaim": text}


def item(excerpt, evidence_id="EV|TEST|1"):
    return {"evidenceId": evidence_id, "exactExcerpt": excerpt,
            "directness": "direct_explicit", "extractionCertainty": "certain",
            "extractionMethod": "manual_transcription", "sourceId": "EVSRC|TJR|1"}


class TestAddedContentIsDetected(unittest.TestCase):
    """Adversarial mutations of ONE real, clean claim/excerpt pair."""

    BASE_EXCERPT = "we wait for a confirmation before we take the entry"
    BASE_CLAIM = "A confirmation is required before the entry is taken."

    def analyze(self, text, excerpt=None):
        return rc.analyze_claim(claim(text), [item(excerpt or self.BASE_EXCERPT)])

    def test_the_unmutated_pair_is_clean(self):
        self.assertEqual(self.analyze(self.BASE_CLAIM)["classification"], rc.CLEAN)

    def test_a_changed_number_is_caught(self):
        result = self.analyze("2 confirmations are required before the entry.")
        self.assertEqual(result["classification"], rc.REVIEW_NUMERIC)
        self.assertIn("2", result["discrepancies"][rc.REVIEW_NUMERIC])

    def test_a_changed_timeframe_is_caught(self):
        for text, token in (("A confirmation on M5 is required before the entry.", "m5"),
                            ("A confirmation is required 30 minutes before the entry.", "minutes")):
            with self.subTest(text=text):
                result = self.analyze(text)
                self.assertIn(rc.REVIEW_TIME, result["flaggedClasses"])
                self.assertIn(token, result["discrepancies"][rc.REVIEW_TIME])

    def test_a_changed_instrument_is_caught(self):
        result = self.analyze("A confirmation on EURUSD is required before the entry.")
        self.assertEqual(result["classification"], rc.REVIEW_INSTRUMENT)
        self.assertIn("eurusd", result["discrepancies"][rc.REVIEW_INSTRUMENT])

    def test_an_inserted_direction_is_caught(self):
        result = self.analyze("A confirmation is required before a long entry.")
        self.assertEqual(result["classification"], rc.REVIEW_DIRECTION)
        self.assertIn("long", result["discrepancies"][rc.REVIEW_DIRECTION])

    def test_inserted_always_never_only_are_each_caught(self):
        for word in ("always", "never", "only", "every", "must", "exactly"):
            with self.subTest(word=word):
                result = self.analyze(
                    "A confirmation is %s required before the entry." % word)
                self.assertEqual(result["classification"], rc.REVIEW_QUANTIFIER)
                self.assertIn(word, result["discrepancies"][rc.REVIEW_QUANTIFIER])

    def test_several_additions_report_every_class(self):
        result = self.analyze(
            "2 confirmations on EURUSD are always required 5 minutes before a long entry.")
        self.assertEqual(result["classification"], rc.REVIEW_MULTIPLE)
        for name in (rc.REVIEW_NUMERIC, rc.REVIEW_TIME, rc.REVIEW_INSTRUMENT,
                     rc.REVIEW_DIRECTION, rc.REVIEW_QUANTIFIER):
            self.assertIn(name, result["flaggedClasses"])

    def test_a_token_present_in_ANY_supporting_excerpt_is_not_flagged(self):
        result = rc.analyze_claim(
            claim("A confirmation on EURUSD is required."),
            [item("we wait for a confirmation", "EV|TEST|1"),
             item("this only applies to EURUSD", "EV|TEST|2")])
        self.assertEqual(result["classification"], rc.CLEAN)


class TestConservativeNormalization(unittest.TestCase):
    """Formatting equivalence must not create obvious false positives -- but
    only where the equivalence is DETERMINISTIC."""

    def test_instrument_separator_formatting_is_equivalent(self):
        for written in ("EUR/USD", "EUR-USD", "eurusd", "EUR USD"):
            with self.subTest(form=written):
                result = rc.analyze_claim(claim("Trade %s on the open." % written),
                                          [item("we trade EURUSD on the open")])
                self.assertNotIn(rc.REVIEW_INSTRUMENT, result["flaggedClasses"])

    def test_case_and_punctuation_do_not_flag(self):
        result = rc.analyze_claim(claim("ALWAYS wait -- always!"),
                                  [item("i always wait")])
        self.assertEqual(result["classification"], rc.CLEAN)

    def test_thousands_separators_are_equivalent(self):
        result = rc.analyze_claim(claim("The target is 1,000 points."),
                                  [item("the target is 1000 points")])
        self.assertEqual(result["classification"], rc.CLEAN)

    def test_normalization_does_NOT_resolve_meaning(self):
        """Ordinal words and morphological variants are NOT treated as equal.

        `first` is not `1` and `day` is not `daily` here, deliberately: those are
        semantic/morphological judgments, not deterministic formatting. They are
        SURFACED, and the report documents them as a known false-positive class.
        """
        self.assertEqual(rc.analyze_claim(claim("Step 1 is the sweep."),
                                          [item("the first thing is the sweep")]
                                          )["classification"], rc.REVIEW_NUMERIC)
        self.assertIn(rc.REVIEW_TIME,
                      rc.analyze_claim(claim("The daily step."),
                                       [item("every single day")])["flaggedClasses"])

    def test_three_letter_words_are_not_mistaken_for_currency_pairs(self):
        result = rc.analyze_claim(claim("The low was the key level."),
                                  [item("the low was the key level")])
        self.assertEqual(result["classification"], rc.CLEAN)


class TestSupportRelationshipSemantics(unittest.TestCase):

    def test_only_supporting_relationships_are_defined_as_support(self):
        self.assertEqual(set(rc.SUPPORTING_RELATIONSHIPS), {"supports", "exemplifies"})
        for other in ("contextualizes", "contradicts", "weakens", "qualifies",
                      "supersedes", "unresolved"):
            self.assertNotIn(other, rc.SUPPORTING_RELATIONSHIPS)

    def test_contextual_evidence_is_not_treated_as_support(self):
        """THE Step 6 error, pinned.

        CLAIM|TJR|20260727|003 has a `contextualizes` link whose excerpt
        discusses the 9:30 open and a `supports` link that is the verbatim
        sentence. Reading the contextualizing excerpt as support flags 8:30 as
        added content -- a false Rule-2 violation.
        """
        idx = index()
        report = rc.conformance_report(idx, TJR)
        row = next(r for r in report["claims"]
                   if r["claimId"] == "CLAIM|TJR|20260727|003")
        self.assertEqual(row["classification"], rc.CLEAN)
        self.assertEqual([e["relationshipType"] for e in row["supportingEvidence"]],
                         ["supports"])
        for entry in row["supportingEvidence"]:
            self.assertNotIn("9:30", entry["exactExcerpt"])

    def test_a_wrong_relationship_removes_the_evidence_from_support(self):
        idx = index()
        target = "CLAIM|TJR|20260727|003"
        idx.links = dict(idx.links)
        for link_id, link in list(idx.links.items()):
            if link["claimId"] == target and link["relationshipType"] == "supports":
                idx.links[link_id] = dict(link, relationshipType="contextualizes")
        row = next(r for r in rc.conformance_report(idx, TJR)["claims"]
                   if r["claimId"] == target)
        self.assertEqual(row["classification"], rc.MISSING_SUPPORT)

    def test_an_unknown_relationship_is_ambiguous_not_clean(self):
        idx = index()
        target = "CLAIM|TJR|20260727|003"
        idx.links = dict(idx.links)
        for link_id, link in list(idx.links.items()):
            if link["claimId"] == target:
                idx.links[link_id] = dict(link, relationshipType="something_new")
        row = next(r for r in rc.conformance_report(idx, TJR)["claims"]
                   if r["claimId"] == target)
        self.assertEqual(row["classification"], rc.AMBIGUOUS_SUPPORT)


class TestFailsClosed(unittest.TestCase):

    def test_missing_support_is_not_clean(self):
        self.assertEqual(rc.analyze_claim(claim("anything"), [])["classification"],
                         rc.MISSING_SUPPORT)

    def test_an_empty_or_absent_excerpt_is_a_provenance_failure(self):
        for bad in (None, "", "   ", 42):
            with self.subTest(excerpt=bad):
                self.assertEqual(
                    rc.analyze_claim(claim("anything"), [item(bad)])["classification"],
                    rc.PROVENANCE_FAILURE)

    def test_a_claim_with_no_text_is_a_provenance_failure(self):
        for bad in (None, "", "  "):
            with self.subTest(text=bad):
                self.assertEqual(
                    rc.analyze_claim(claim(bad), [item("x")])["classification"],
                    rc.PROVENANCE_FAILURE)

    def test_an_unresolvable_evidence_reference_fails_closed(self):
        idx = index()
        target = "CLAIM|TJR|20260727|003"
        idx.links = dict(idx.links)
        for link_id, link in list(idx.links.items()):
            if link["claimId"] == target:
                idx.links[link_id] = dict(link, evidenceId="EV|GHOST|999")
        row = next(r for r in rc.conformance_report(idx, TJR)["claims"]
                   if r["claimId"] == target)
        self.assertEqual(row["classification"], rc.PROVENANCE_FAILURE)

    def test_an_unknown_or_empty_corpus_is_refused(self):
        idx = index()
        for bad in ("NOBODY", "", None):
            with self.subTest(trader=bad):
                with self.assertRaises(ValueError):
                    rc.conformance_report(idx, bad)


class TestCorpusIsolation(unittest.TestCase):

    def test_foreign_trader_evidence_is_a_provenance_failure(self):
        """Evidence reached from this corpus must belong to this corpus."""
        idx = index()
        target = "CLAIM|TJR|20260727|003"
        alex_source = next(s for s in idx.sources.values()
                           if s.get("traderId") == ALEX)
        idx.items = dict(idx.items)
        for link in idx.links.values():
            if link["claimId"] == target:
                original = idx.items[link["evidenceId"]]
                idx.items[link["evidenceId"]] = dict(
                    original, sourceId=alex_source["sourceId"])
        row = next(r for r in rc.conformance_report(idx, TJR)["claims"]
                   if r["claimId"] == target)
        self.assertEqual(row["classification"], rc.PROVENANCE_FAILURE)

    def test_no_alex_claim_or_evidence_appears_in_the_tjr_report(self):
        report = rc.conformance_report(index(), TJR)
        for row in report["claims"]:
            self.assertEqual(row["traderId"], TJR)
            self.assertNotIn("ALEX", row["claimId"])
            for entry in row["supportingEvidence"]:
                self.assertNotIn("ALEX", entry["evidenceId"])
                self.assertNotIn("ALEX", entry["sourceId"] or "")

    def test_the_two_corpora_report_independently(self):
        tjr = rc.conformance_report(index(), TJR)
        alex = rc.conformance_report(index(), ALEX)
        self.assertNotEqual(tjr["totalClaims"], 0)
        self.assertNotEqual(alex["totalClaims"], 0)
        tjr_ids = {r["claimId"] for r in tjr["claims"]}
        alex_ids = {r["claimId"] for r in alex["claims"]}
        self.assertEqual(tjr_ids & alex_ids, set())


class TestCleanIsNotApproval(unittest.TestCase):

    def test_the_report_states_what_clean_does_not_mean(self):
        report = rc.conformance_report(index(), TJR)
        meaning = report["cleanMeaning"].lower()
        self.assertIn("not", meaning)
        for word in ("approved", "correct", "faithful", "reviewed"):
            self.assertIn(word, meaning)

    def test_the_rendered_output_carries_the_caveat(self):
        text = "\n".join(rc.render(rc.conformance_report(index(), TJR)))
        self.assertIn("cannot prove", text.lower())
        self.assertIn("human semantic-review requirement remains authoritative",
                      text.lower())

    def test_the_report_never_emits_an_approval_field(self):
        blob = json.dumps(rc.conformance_report(index(), TJR))
        for forbidden in ("approved", "accepted", "verified", "validated",
                          "promotionState", "proposalId"):
            self.assertNotIn('"%s"' % forbidden, blob)

    def test_clean_carries_no_score(self):
        def walk(node):
            if isinstance(node, dict):
                for key, value in node.items():
                    self.assertNotIsInstance(value, float, key)
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)
        walk(rc.conformance_report(index(), TJR))


class TestDeterminism(unittest.TestCase):

    def test_two_runs_are_byte_identical(self):
        a = json.dumps(rc.conformance_report(index(), TJR), sort_keys=True)
        b = json.dumps(rc.conformance_report(index(), TJR), sort_keys=True)
        self.assertEqual(a, b)

    def test_counts_reconcile(self):
        report = rc.conformance_report(index(), TJR)
        self.assertEqual(sum(report["countsByClassification"].values()),
                         report["totalClaims"])
        self.assertEqual(report["cleanCount"] + report["reviewCount"],
                         report["totalClaims"])


class TestFirewall(unittest.TestCase):

    MODULE = rc.__file__

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
        for forbidden in ('"w"', "'w'", '"a"', "'a'", "os.remove", "shutil",
                          "unlink", "rmtree", "mkdir", "setattr"):
            self.assertNotIn(forbidden, code)

    def test_the_module_names_no_protected_or_executable_path(self):
        code = self.code().lower()
        for forbidden in ("index.html", "docs/campaigns", "hypothesis-registry",
                          "prereg-", "proposals", "blueprints", "graph/build"):
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
        self.assertEqual(imported, {"argparse", "json", "os", "re", "sys",
                                    "query_evidence", "evidence_common"})

    def test_no_trading_or_promotion_identifier_is_referenced(self):
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
        forbidden = {"paper", "backtest", "live", "trade", "trading", "order",
                     "execute", "promote", "promotion", "freeze", "approve",
                     "resolve", "answer"}
        for identifier in names:
            with self.subTest(identifier=identifier):
                self.assertEqual(set(identifier.lower().split("_")) & forbidden,
                                 set())

    def test_running_the_analyzer_mutates_no_file(self):
        roots = [os.path.join(rc.EVIDENCE_ROOT, d)
                 for d in ("claims", "items", "links", "questions",
                           "contradictions", "proposals", "blueprints")]

        def digest():
            out = {}
            for root in roots:
                for path in sorted(glob.glob(os.path.join(root, "*.json"))):
                    with open(path, "rb") as handle:
                        out[path] = hashlib.sha256(handle.read()).hexdigest()
            return out

        before = digest()
        rc.render(rc.conformance_report(index(), TJR))
        rc.render(rc.conformance_report(index(), ALEX))
        self.assertEqual(digest(), before)

    def test_no_proposal_contradiction_or_question_state_changes(self):
        idx_before = index()
        open_contradictions = {c["contradictionId"]: c["status"]
                               for c in idx_before.contradictions.values()}
        answered = {q["questionId"]: q.get("answerStatus")
                    for q in idx_before.questions.values()}
        proposals_pattern = os.path.join(rc.EVIDENCE_ROOT, "proposals", "*.json")
        proposals_before = sorted(glob.glob(proposals_pattern))
        rc.conformance_report(index(), TJR)
        idx_after = index()
        self.assertEqual({c["contradictionId"]: c["status"]
                          for c in idx_after.contradictions.values()},
                         open_contradictions)
        self.assertEqual({q["questionId"]: q.get("answerStatus")
                          for q in idx_after.questions.values()}, answered)
        # Compare before/after, exactly like the two assertions above. Asserting this
        # directory was EMPTY was a proxy for "conformance_report wrote no proposal" that
        # held only while the corpus contained none: it failed once the first authorized
        # rule candidates were created, and it could never have caught a write after that.
        self.assertEqual(sorted(glob.glob(proposals_pattern)), proposals_before)


if __name__ == "__main__":
    unittest.main()

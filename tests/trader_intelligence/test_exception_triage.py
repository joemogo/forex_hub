#!/usr/bin/env python3
"""MOGO-019 Step 8 -- exception-queue triage.

The properties under test:

  * IT PRIORITIZES, IT DOES NOT ADJUDICATE. No claim is approved, no question
    answered, no contradiction settled, no proposal created.
  * IT NEVER DROPS A CLAIM ON A GUESS. A flag is downgraded only when every
    flagged token was DEMONSTRATED mechanical, and a blocker-relevant claim is
    never demoted at all.
  * `REVIEW_CAN_RESOLVE` IS COMPUTED, NOT ASSUMED. On this corpus it is empty,
    and that is a result the test pins rather than an omission.
  * TRADER AND SUPPORT ISOLATION SURVIVE the composition of three views.
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

import exception_triage as et                     # noqa: E402
import research_understanding as ru               # noqa: E402
import rule_conformance as rc                     # noqa: E402
from query_evidence import EvidenceIndex          # noqa: E402

TJR = "TJR"
ALEX = "ALEX_G"


def index():
    return EvidenceIndex.load(rc.EVIDENCE_ROOT)


class TriageCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.idx = index()
        cls.result = et.triage(cls.idx, TJR)


class TestDeterminism(TriageCase):

    def test_two_runs_are_byte_identical(self):
        a = json.dumps(et.triage(index(), TJR), sort_keys=True)
        b = json.dumps(et.triage(index(), TJR), sort_keys=True)
        self.assertEqual(a, b)

    def test_the_queue_is_ordered_by_fixed_priority_rank(self):
        keys = [(et._RANK[i["reviewPriority"]], i["claimId"])
                for i in self.result["items"]]
        self.assertEqual(keys, sorted(keys))

    def test_counts_reconcile_with_items(self):
        self.assertEqual(sum(self.result["countsByPriority"].values()),
                         self.result["flaggedCount"])
        self.assertEqual(self.result["flaggedCount"] + self.result["cleanCount"],
                         self.result["totalClaims"])

    def test_no_numeric_priority_score_exists(self):
        def walk(node):
            if isinstance(node, dict):
                for key, value in node.items():
                    self.assertNotIsInstance(value, float, key)
                    self.assertNotIn("score", key.lower())
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)
        walk(self.result["items"])


class TestOnlyFlaggedClaimsEnterTheQueue(TriageCase):

    def test_clean_claims_are_absent_from_the_queue(self):
        conformance = rc.conformance_report(self.idx, TJR)
        clean = {r["claimId"] for r in conformance["claims"]
                 if r["classification"] == rc.CLEAN}
        queued = {i["claimId"] for i in self.result["items"]}
        self.assertEqual(clean & queued, set())
        self.assertTrue(clean)

    def test_clean_is_still_not_described_as_approved(self):
        meaning = self.result["cleanMeaning"].lower()
        for word in ("approved", "correct", "faithful", "reviewed"):
            self.assertIn(word, meaning)
        self.assertIs(self.result["adjudicatesNothing"], True)


class TestStrategyRelevance(TriageCase):

    def test_rule_categories_come_from_the_shared_schema_vocabulary(self):
        for item in self.result["items"]:
            self.assertEqual(item["isRuleCategory"],
                             item["claimType"] in ru.RULE_CATEGORIES)
            self.assertEqual(item["isRequiredCategory"],
                             item["claimType"] in ru.REQUIRED_RULE_CATEGORIES)

    def test_a_rule_category_claim_is_marked_critical(self):
        for item in self.result["items"]:
            if item["isRuleCategory"]:
                self.assertIn(et.CRITICAL_RULE_MEANING, item["triageClasses"])

    def test_non_rule_claims_are_not_marked_critical(self):
        for item in self.result["items"]:
            if not item["isRuleCategory"]:
                self.assertNotIn(et.CRITICAL_RULE_MEANING, item["triageClasses"])

    def test_required_category_flagged_count_is_a_subset_of_rule_category(self):
        self.assertLessEqual(self.result["requiredCategoryFlaggedCount"],
                             self.result["ruleCategoryFlaggedCount"])


class TestFalsePositiveHandlingFailsClosed(TriageCase):

    def test_a_downgrade_requires_every_token_to_be_demonstrated(self):
        for item in self.result["items"]:
            if item["reviewPriority"] == et.LIKELY_MECHANICAL_FALSE_POSITIVE:
                shown = len(item["demonstratedMechanicalReasons"])
                total = sum(len(v) for v in item["discrepancies"].values())
                self.assertEqual(shown, total, item["claimId"])

    def test_an_undemonstrated_flag_is_never_downgraded(self):
        row = {"claimId": "C", "traderId": TJR, "claimType": "definition",
               "normalizedClaim": "the target is 42 points",
               "classification": rc.REVIEW_NUMERIC,
               "flaggedClasses": [rc.REVIEW_NUMERIC],
               "discrepancies": {rc.REVIEW_NUMERIC: ["42"]},
               "supportingEvidence": [{"exactExcerpt": "the target is set",
                                       "evidenceId": "E", "directness": "x",
                                       "extractionCertainty": "y"}],
               "blockingQuestionIds": [], "contradictionIds": []}
        item = et.triage_row(row, set(ru.RULE_CATEGORIES),
                             set(ru.REQUIRED_RULE_CATEGORIES))
        self.assertEqual(item["demonstratedMechanicalReasons"], [])
        self.assertNotEqual(item["reviewPriority"],
                            et.LIKELY_MECHANICAL_FALSE_POSITIVE)

    def test_a_partly_demonstrated_claim_stays_in_the_real_queue(self):
        row = {"claimId": "C", "traderId": TJR, "claimType": "entry_rule",
               "normalizedClaim": "step 1 requires 42 points",
               "classification": rc.REVIEW_NUMERIC,
               "flaggedClasses": [rc.REVIEW_NUMERIC],
               "discrepancies": {rc.REVIEW_NUMERIC: ["1", "42"]},
               "supportingEvidence": [{"exactExcerpt": "the first requirement",
                                       "evidenceId": "E", "directness": "x",
                                       "extractionCertainty": "y"}],
               "blockingQuestionIds": [], "contradictionIds": []}
        item = et.triage_row(row, set(ru.RULE_CATEGORIES),
                             set(ru.REQUIRED_RULE_CATEGORIES))
        self.assertTrue(item["demonstratedMechanicalReasons"])
        self.assertNotEqual(item["reviewPriority"],
                            et.LIKELY_MECHANICAL_FALSE_POSITIVE)

    def test_a_blocker_relevant_claim_is_never_demoted(self):
        row = {"claimId": "C", "traderId": TJR, "claimType": "entry_rule",
               "normalizedClaim": "step 1 of the setup",
               "classification": rc.REVIEW_NUMERIC,
               "flaggedClasses": [rc.REVIEW_NUMERIC],
               "discrepancies": {rc.REVIEW_NUMERIC: ["1"]},
               "supportingEvidence": [{"exactExcerpt": "the first thing",
                                       "evidenceId": "E", "directness": "x",
                                       "extractionCertainty": "y"}],
               "blockingQuestionIds": ["EQ|X"], "contradictionIds": []}
        item = et.triage_row(row, set(ru.RULE_CATEGORIES),
                             set(ru.REQUIRED_RULE_CATEGORIES))
        self.assertIn(et.LIKELY_MECHANICAL_FALSE_POSITIVE, item["triageClasses"])
        self.assertEqual(item["reviewPriority"], et.BLOCKER_RELEVANT)

    def test_an_unknown_claim_type_is_not_treated_as_strategy_critical(self):
        row = {"claimId": "C", "traderId": TJR, "claimType": "something_new",
               "normalizedClaim": "x always y", "classification": rc.REVIEW_QUANTIFIER,
               "flaggedClasses": [rc.REVIEW_QUANTIFIER],
               "discrepancies": {rc.REVIEW_QUANTIFIER: ["always"]},
               "supportingEvidence": [{"exactExcerpt": "x y", "evidenceId": "E",
                                       "directness": "d", "extractionCertainty": "c"}],
               "blockingQuestionIds": [], "contradictionIds": []}
        item = et.triage_row(row, set(ru.RULE_CATEGORIES),
                             set(ru.REQUIRED_RULE_CATEGORIES))
        self.assertFalse(item["isRuleCategory"])
        self.assertNotIn(et.CRITICAL_RULE_MEANING, item["triageClasses"])
        self.assertIn(et.MODAL_OR_QUANTIFIER_ESCALATION, item["triageClasses"])

    def test_a_claim_with_no_matching_class_gets_general_review(self):
        row = {"claimId": "C", "traderId": TJR, "claimType": "definition",
               "normalizedClaim": "x", "classification": rc.PROVENANCE_FAILURE,
               "flaggedClasses": [], "discrepancies": {},
               "supportingEvidence": [], "blockingQuestionIds": [],
               "contradictionIds": []}
        item = et.triage_row(row, set(ru.RULE_CATEGORIES),
                             set(ru.REQUIRED_RULE_CATEGORIES))
        self.assertEqual(item["triageClasses"], [et.GENERAL_SEMANTIC_REVIEW])


class TestBlockerImpactMap(TriageCase):

    def test_every_blocker_is_mapped_exactly_once(self):
        view = ru.corpus_view(self.idx, TJR)
        eligibility = ru.eligibility(view)
        self.assertEqual(len(self.result["blockerImpact"]),
                         eligibility["blockerCount"])
        ids = [r["blockerId"] for r in self.result["blockerImpact"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_no_blocker_is_resolvable_by_rule_2_review(self):
        """COMPUTED, not assumed. Blockers come from questions and
        contradictions; a Rule-2 review decides paraphrase faithfulness. The
        empty result is the finding."""
        impacts = [r["reviewImpact"] for r in self.result["blockerImpact"]]
        self.assertEqual(impacts.count(et.REVIEW_CAN_RESOLVE), 0)
        self.assertIn(et.REVIEW_CAN_CLARIFY_BUT_NOT_RESOLVE, impacts)
        self.assertIn(et.REVIEW_CANNOT_RESOLVE, impacts)

    def test_a_blocker_with_no_flagged_claim_cannot_be_clarified(self):
        for row in self.result["blockerImpact"]:
            if not row["flaggedClaimIds"]:
                self.assertEqual(row["reviewImpact"], et.REVIEW_CANNOT_RESOLVE)

    def test_a_missing_required_category_has_nothing_to_review(self):
        row = next(r for r in self.result["blockerImpact"]
                   if r["blockerType"] == "REQUIRED_CATEGORY_MISSING")
        self.assertEqual(row["relatedClaimIds"], [])
        self.assertEqual(row["reviewImpact"], et.REVIEW_CANNOT_RESOLVE)

    def test_the_contradiction_still_requires_an_operator_ruling(self):
        row = next(r for r in self.result["blockerImpact"]
                   if r["blockerId"] == "XCONTRA|20260728|001")
        self.assertTrue(row["stillRequiresOperatorRuling"])
        self.assertEqual(row["reviewImpact"], et.REVIEW_CANNOT_RESOLVE)

    def test_the_minimum_review_set_contains_only_clarifiable_claims(self):
        clarifiable = {c for r in self.result["blockerImpact"]
                       if r["reviewImpact"] != et.REVIEW_CANNOT_RESOLVE
                       for c in r["flaggedClaimIds"]}
        self.assertEqual(set(self.result["minimumReviewSet"]), clarifiable)
        queued = {i["claimId"] for i in self.result["items"]}
        self.assertTrue(set(self.result["minimumReviewSet"]) <= queued)


class TestIsolation(TriageCase):

    def test_no_alex_claim_or_evidence_enters_the_tjr_triage(self):
        for item in self.result["items"]:
            self.assertEqual(item["traderId"], TJR)
            self.assertNotIn("ALEX", item["claimId"])
            for entry in item["supportingEvidence"]:
                self.assertNotIn("ALEX", entry["evidenceId"])
        for row in self.result["blockerImpact"]:
            for claim_id in row["relatedClaimIds"] + row["flaggedClaimIds"]:
                self.assertNotIn("ALEX", claim_id)

    def test_support_relationship_isolation_survives_composition(self):
        """Only `supports`/`exemplifies` evidence reaches a packet."""
        for item in self.result["items"]:
            for entry in item["supportingEvidence"]:
                self.assertIn(entry["relationshipType"],
                              rc.SUPPORTING_RELATIONSHIPS)

    def test_the_two_corpora_triage_independently(self):
        alex = et.triage(index(), ALEX)
        self.assertNotEqual(alex["flaggedCount"], 0)
        tjr_ids = {i["claimId"] for i in self.result["items"]}
        alex_ids = {i["claimId"] for i in alex["items"]}
        self.assertEqual(tjr_ids & alex_ids, set())

    def test_an_unknown_corpus_is_refused(self):
        for bad in ("NOBODY", "", None):
            with self.subTest(trader=bad):
                with self.assertRaises((ValueError, ru.CorpusAmbiguous)):
                    et.triage(self.idx, bad)


class TestFirewall(TriageCase):

    MODULE = et.__file__

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

    def test_the_module_never_writes(self):
        code = self.code()
        for forbidden in ('"w"', "'w'", '"a"', "'a'", "os.remove", "shutil",
                          "unlink", "rmtree", "mkdir", "setattr", "open("):
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
                                    "research_understanding", "rule_conformance",
                                    "query_evidence"})

    def test_no_trading_or_adjudication_identifier(self):
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
        # "order" is deliberately NOT here: this module is about QUEUE order,
        # and `PRIORITY_ORDER` is sort order, not a trade order. The trading
        # sense is already covered by trade/trading/execute.
        forbidden = {"paper", "backtest", "live", "trade", "trading",
                     "execute", "promote", "promotion", "freeze", "approve",
                     "adjudicate", "answer"}
        for identifier in names:
            with self.subTest(identifier=identifier):
                self.assertEqual(set(identifier.lower().split("_")) & forbidden,
                                 set())

    def test_running_triage_mutates_no_file_and_changes_no_state(self):
        roots = [os.path.join(rc.EVIDENCE_ROOT, d)
                 for d in ("claims", "items", "links", "questions",
                           "contradictions", "proposals", "blueprints", "gaps")]

        def digest():
            out = {}
            for root in roots:
                for path in sorted(glob.glob(os.path.join(root, "*.json"))):
                    with open(path, "rb") as handle:
                        out[path] = hashlib.sha256(handle.read()).hexdigest()
            return out

        before = digest()
        et.render_packets(et.triage(index(), TJR))
        et.render_packets(et.triage(index(), ALEX))
        # The digest above already spans "proposals" by path AND content, so triage writing
        # or editing a proposal fails here. Additionally asserting the directory was globally
        # EMPTY added no detection power and froze a corpus state -- it began failing the
        # moment the first authorized rule candidates were created, reporting a firewall
        # breach that had not happened. Removed, not rebaselined.
        self.assertEqual(digest(), before)

    def test_eligibility_is_reported_but_not_changed(self):
        view = ru.corpus_view(index(), TJR)
        eligibility = ru.eligibility(view)
        self.assertEqual(self.result["eligibility"], eligibility["eligibility"])
        self.assertEqual(self.result["eligibility"], ru.BLOCKED)
        self.assertEqual(self.result["blockerCount"], 17)

    def test_the_packet_offers_a_decision_but_records_none(self):
        text = "\n".join(et.render_packets(self.result, limit=1))
        self.assertIn("HUMAN DECISION", text)
        self.assertIn("[ ] faithful", text)
        blob = json.dumps(self.result)
        for forbidden in ("decision", "adjudicated", "approved", "accepted",
                          "proposalId", "promotionState"):
            self.assertNotIn('"%s"' % forbidden, blob)


if __name__ == "__main__":
    unittest.main()

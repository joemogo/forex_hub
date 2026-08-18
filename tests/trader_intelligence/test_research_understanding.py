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
import types
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
        """No path into executable or campaign state, anywhere."""
        code = self.code()
        for forbidden in ("index.html", "docs/campaigns", "hypothesis-registry",
                          "PREREG-", "docs/evidence"):
            self.assertNotIn(forbidden.lower(), code.lower())

    def test_no_trading_identifier_is_referenced_in_executable_code(self):
        """Checks IDENTIFIERS, not prose.

        The module must not name a paper/backtest/live variable, attribute or
        call. It MAY say the words in a disclaimer string -- the Step 3 result
        has to state that it authorizes no backtest, no paper trading and no
        live trading, and forbidding the words outright would forbid the safety
        notice itself.
        """
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
            elif isinstance(node, ast.keyword) and node.arg:
                names.add(node.arg)
        # Segment-exact, not substring: `trader_id` names the EDUCATOR and must
        # not be confused with trading.
        forbidden = {"paper", "backtest", "live", "trade", "trading", "order",
                     "execute", "exec", "promote", "promotion", "freeze",
                     "position", "broker"}
        for identifier in names:
            segments = set(identifier.lower().split("_"))
            with self.subTest(identifier=identifier):
                self.assertEqual(segments & forbidden, set())

    def test_the_module_imports_nothing_from_the_trading_engine(self):
        with open(self.MODULE, encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {a.name for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
        # MOGO-019 Step 4 widened this allow-list by exactly ONE module, and
        # deliberately: Step 4 must report what acquisition is currently
        # authorized, which means READING the approved-destination registry.
        # `connector_authorization` is the research-acquisition gate -- the
        # module whose job is to REFUSE unapproved destinations -- not trading
        # logic, and it is imported inside a try/except that fails closed to an
        # empty registry. The property that matters is that no WRITE path
        # exists, which `test_the_planner_never_mutates_the_authorization_registry`
        # and the on-disk digest tests assert directly.
        self.assertEqual(imported,
                         {"argparse", "json", "os", "sys", "query_evidence",
                          "glob", "mogo_platform.runtime"})
        self.assertNotIn("index", imported)

    def test_the_authorization_registry_is_only_ever_read(self):
        """The one platform import must never be written through.

        Checked structurally: subscripting the registry is how you READ it, so
        a text scan would ban the correct usage. What must not exist is an
        ASSIGNMENT, augmented assignment, deletion or mutating method call
        targeting it.
        """
        with open(self.MODULE, encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        registry = "APPROVED_DESTINATIONS"

        def touches(node):
            return any(isinstance(n, ast.Name) and n.id == registry
                       or isinstance(n, ast.Attribute) and n.attr == registry
                       for n in ast.walk(node))

        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
                targets = (node.targets if isinstance(node, ast.Assign)
                           else [node.target])
                for target in targets:
                    self.assertFalse(touches(target),
                                     "assignment into the registry")
            elif isinstance(node, ast.Delete):
                for target in node.targets:
                    self.assertFalse(touches(target), "deletion from registry")
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in ("update", "pop", "clear", "setdefault",
                                      "__setitem__"):
                    self.assertFalse(touches(node.func.value),
                                     "mutating call on the registry")
        self.assertNotIn("setattr", ast.unparse(tree))

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
        # The claim is that the STEP writes no proposal -- not that the repository
        # contains none. Asserting the directory is empty conflated the two: it began
        # failing the moment the first authorized rule candidates were created (reporting
        # a firewall breach that had not happened), and it would not have detected a write
        # at all once any proposal legitimately exists. Before/after is the actual invariant
        # and is strictly stronger in both directions.
        pattern = os.path.join(ru.EVIDENCE_ROOT, "proposals", "*.json")
        before = sorted(glob.glob(pattern))
        ru.corpus_view(index(), TJR)
        self.assertEqual(sorted(glob.glob(pattern)), before)
        self.assertNotIn("proposalId", json.dumps(self.view))


# ---------------------------------------------------------------------------
# MOGO-019 Step 3 -- reconstruction eligibility
# ---------------------------------------------------------------------------

class EligibilityCase(ViewCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.result = ru.eligibility(cls.view)

    def rebuilt(self, view):
        return ru.eligibility(view)


class TestRequiredCategoriesComeFromExistingArchitecture(EligibilityCase):

    def test_required_categories_match_the_critical_knowledge_gaps(self):
        """The requirement is NOT invented here -- it is knowledge_gaps'
        `critical` priority, and it must not be able to drift from it."""
        import knowledge_gaps as kg
        blueprint = {"scope": {"instruments": [], "sessions": [],
                               "higherTimeframes": [], "executionTimeframes": []},
                     "workflow": [], "entryLogic": {"requiredConditions": []},
                     "exitLogic": {"setupInvalidation": [], "stopPlacement": [],
                                   "profitTargets": []},
                     "riskLogic": {"statedRiskRules": [], "inferredRiskRules": []}}
        critical = {spec[0] for spec in kg._category_spec(None, blueprint, {})
                    if spec[5] == "critical"}
        self.assertEqual(set(ru.REQUIRED_BY_GAP_CATEGORY), critical)

    def test_every_required_category_is_a_real_rule_category(self):
        for name in ru.REQUIRED_RULE_CATEGORIES:
            self.assertIn(name, ru.RULE_CATEGORIES)

    def test_optional_categories_are_not_treated_as_required(self):
        for name in ("timeframe_rule", "target_rule", "confirmation_rule",
                     "session_rule", "trade_management_rule"):
            self.assertFalse(self.result["categories"][name]["required"], name)


class TestEligibilityIsDeterministicAndBlocking(EligibilityCase):

    def test_repeated_evaluation_is_byte_identical(self):
        a = json.dumps(ru.eligibility(ru.corpus_view(index(), TJR)), sort_keys=True)
        b = json.dumps(ru.eligibility(ru.corpus_view(index(), TJR)), sort_keys=True)
        self.assertEqual(a, b)

    def test_the_real_tjr_corpus_is_blocked(self):
        self.assertEqual(self.result["eligibility"], ru.BLOCKED)
        self.assertGreater(self.result["blockerCount"], 0)

    def test_every_blocker_is_surfaced_not_just_the_first(self):
        kinds = {b["blockerType"] for b in self.result["blockers"]}
        self.assertIn("BLOCKING_QUESTION", kinds)
        self.assertIn("BLOCKING_CONTRADICTION", kinds)
        self.assertTrue(any(k.startswith("REQUIRED_CATEGORY_") for k in kinds))
        self.assertEqual(len(self.result["blockers"]), self.result["blockerCount"])

    def test_a_corpus_with_no_blockers_is_eligible(self):
        """The predicate must be capable of returning ELIGIBLE."""
        clean = copy.deepcopy(self.view)
        clean["internalContradictions"] = []
        clean["crossCorpusContradictions"] = []
        for name in ru.REQUIRED_RULE_CATEGORIES:
            clean["ruleCategories"][name] = [{
                "claimId": "CLAIM|%s|SYNTHETIC" % TJR, "claimType": name,
                "hasSourceSaidSupport": True, "unresolvedQuestions": [],
                "evidence": [{"present": True, "directness": "direct_explicit"}],
            }]
        for name in ru.RULE_CATEGORIES:
            for entry in clean["ruleCategories"][name]:
                entry["unresolvedQuestions"] = []
        for entries in clean["nonRuleClaims"].values():
            for entry in entries:
                entry["unresolvedQuestions"] = []
        result = self.rebuilt(clean)
        self.assertEqual(result["eligibility"], ru.ELIGIBLE, result["blockers"])

    def test_one_reintroduced_blocker_flips_it_back_to_blocked(self):
        clean = copy.deepcopy(self.view)
        clean["internalContradictions"] = []
        clean["crossCorpusContradictions"] = []
        for name in ru.REQUIRED_RULE_CATEGORIES:
            clean["ruleCategories"][name] = [{
                "claimId": "CLAIM|%s|SYNTHETIC" % TJR, "claimType": name,
                "hasSourceSaidSupport": True, "unresolvedQuestions": [],
                "evidence": [{"present": True, "directness": "direct_explicit"}]}]
        for name in ru.RULE_CATEGORIES:
            for entry in clean["ruleCategories"][name]:
                entry["unresolvedQuestions"] = []
        for entries in clean["nonRuleClaims"].values():
            for entry in entries:
                entry["unresolvedQuestions"] = []
        self.assertEqual(self.rebuilt(clean)["eligibility"], ru.ELIGIBLE)
        # remove ONE required category -> blocked again
        blocked = copy.deepcopy(clean)
        blocked["ruleCategories"]["risk_rule"] = []
        result = self.rebuilt(blocked)
        self.assertEqual(result["eligibility"], ru.BLOCKED)
        self.assertEqual([b["ruleCategory"] for b in result["blockers"]],
                         ["risk_rule"])


class TestCategoryStatusSemantics(EligibilityCase):

    def test_missing_required_category_is_reported_missing(self):
        risk = self.result["categories"]["risk_rule"]
        self.assertEqual(risk["status"], ru.MISSING)
        self.assertTrue(risk["required"])
        self.assertEqual(risk["claimCount"], 0)

    def test_a_blocking_question_makes_its_category_ambiguous(self):
        entry_rule = self.result["categories"]["entry_rule"]
        self.assertEqual(entry_rule["status"], ru.AMBIGUOUS)
        self.assertTrue(entry_rule["implicatedClaimIds"])

    def test_a_blocking_contradiction_makes_its_category_conflicted(self):
        setup = self.result["categories"]["setup_requirement"]
        self.assertEqual(setup["status"], ru.CONFLICTED)

    def test_a_non_blocking_question_does_not_block(self):
        """Only blocks_rule_candidate / blocks_promotion may block."""
        view = copy.deepcopy(self.view)
        for entries in view["ruleCategories"].values():
            for entry in entries:
                entry["unresolvedQuestions"] = [
                    {"questionId": "EQ|SYNTH|1", "questionType": "other",
                     "questionText": "x", "blockingStatus": "non_blocking",
                     "answerStatus": "unanswered", "researchStatus": "open"}]
        for entries in view["nonRuleClaims"].values():
            for entry in entries:
                entry["unresolvedQuestions"] = []
        result = self.rebuilt(view)
        self.assertFalse([b for b in result["blockers"]
                          if b["blockerType"] == "BLOCKING_QUESTION"])

    def test_a_resolved_or_non_blocking_contradiction_does_not_block(self):
        view = copy.deepcopy(self.view)
        view["internalContradictions"] = [
            {"contradictionId": "X|1", "claimAId": "a", "claimBId": "b",
             "contradictionType": "T", "severity": "blocking",
             "status": "resolved_by_owner"},
            {"contradictionId": "X|2", "claimAId": "a", "claimBId": "b",
             "contradictionType": "T", "severity": "material", "status": "open"}]
        view["crossCorpusContradictions"] = []
        result = self.rebuilt(view)
        self.assertFalse([b for b in result["blockers"]
                          if b["blockerType"] == "BLOCKING_CONTRADICTION"])

    def test_inference_only_support_is_not_treated_as_source_backed(self):
        view = copy.deepcopy(self.view)
        view["internalContradictions"] = []
        view["crossCorpusContradictions"] = []
        for entries in list(view["ruleCategories"].values()) \
                + list(view["nonRuleClaims"].values()):
            for entry in entries:
                entry["unresolvedQuestions"] = []
        view["ruleCategories"]["stop_rule"] = [{
            "claimId": "CLAIM|TJR|INFERRED", "claimType": "stop_rule",
            "hasSourceSaidSupport": False, "unresolvedQuestions": [],
            "evidence": [{"present": True,
                          "directness": "inferred_from_context"}]}]
        result = self.rebuilt(view)
        self.assertEqual(result["categories"]["stop_rule"]["status"],
                         ru.INFERENCE_ONLY)
        self.assertIn("REQUIRED_CATEGORY_INFERENCE_ONLY",
                      [b["blockerType"] for b in result["blockers"]])

    def test_a_provenance_failure_fails_closed(self):
        view = copy.deepcopy(self.view)
        view["ruleCategories"]["stop_rule"] = [{
            "claimId": "CLAIM|TJR|BROKEN", "claimType": "stop_rule",
            "hasSourceSaidSupport": True, "unresolvedQuestions": [],
            "evidence": [{"present": False, "directness": None}]}]
        result = self.rebuilt(view)
        self.assertEqual(result["categories"]["stop_rule"]["status"],
                         ru.PROVENANCE_GAP)

    def test_a_claim_with_no_evidence_at_all_fails_closed(self):
        view = copy.deepcopy(self.view)
        view["ruleCategories"]["stop_rule"] = [{
            "claimId": "CLAIM|TJR|NOEV", "claimType": "stop_rule",
            "hasSourceSaidSupport": True, "unresolvedQuestions": [],
            "evidence": []}]
        self.assertEqual(self.rebuilt(view)["categories"]["stop_rule"]["status"],
                         ru.PROVENANCE_GAP)


class TestEligibilityBlockersAreActionable(EligibilityCase):

    def test_every_blocking_unanswered_question_in_scope_surfaces(self):
        """The set is DERIVED from the corpus, not pinned at a number.

        This previously asserted exactly 12. That was one afternoon's corpus: a
        question has since been answered through the governed intake path, so the
        real total is 11 and the count began failing for the system working
        correctly. Worse, a count cannot tell a MISSING blocker from a spurious
        one -- 12 of the wrong questions would have passed.

        The specification is restated instead: a question that is in scope, marked
        blocking, and not answered must surface. That is independent of how
        eligibility() computes it, so it remains a real oracle rather than a
        restatement of the implementation.
        """
        questions = [b for b in self.result["blockers"]
                     if b["blockerType"] == "BLOCKING_QUESTION"]

        in_scope = {e["claimId"] for e in self.entries()}
        expected = {qid for qid, q in self.idx.questions.items()
                    if q["claimId"] in in_scope
                    and q["blockingStatus"] != "non_blocking"
                    and q["answerStatus"] != "answered"}
        self.assertGreater(len(expected), 0,
                           "no blocking questions in scope -- this test would be vacuous")
        self.assertEqual({b["questionId"] for b in questions}, expected)
        self.assertEqual(len(questions), len(expected), "a question surfaced twice")

        # The blocker's PAYLOAD, not just its identity. `affectedClaimId` is what
        # makes a blocker actionable -- which claim is blocked -- and re-attributing
        # every blocker to one wrong claim left the identity check above green.
        for blocker in questions:
            self.assertEqual(blocker["affectedClaimId"],
                             self.idx.questions[blocker["questionId"]]["claimId"],
                             "%s is attributed to the wrong claim" % blocker["questionId"])
        for blocker in questions:
            self.assertTrue(blocker["questionId"].startswith("EQ|"))
            self.assertIn(blocker["blockingStatus"],
                          ("blocks_rule_candidate", "blocks_promotion"))
            self.assertNotEqual(blocker["answerStatus"], "answered")
            self.assertTrue(blocker["whyItBlocks"])
            # the research NEED is stated; the question is NOT answered
            self.assertTrue(blocker["researchNeed"])
            self.assertNotIn("answer", blocker)

    def test_it_is_answerStatus_that_gates_a_blocker_not_researchStatus(self):
        """A positive control for the FIELD, not just the value.

        The derived-set check above filters on `answerStatus != "answered"`, which
        is the same expression corpus_view() uses, so it proves plumbing rather
        than correctness. In this corpus the two status fields happen to agree on
        every question -- an independent verifier swapped the implementation to
        read `researchStatus` instead and every corpus-derived assertion stayed
        green.

        A stub index forces them to disagree. The filter runs at VIEW
        CONSTRUCTION, not in eligibility(), so the control has to be applied
        there: mutating a built view cannot exercise it.
        """
        def index_with(answer_status, research_status):
            claim = {"claimId": "CLAIM|X|1", "traderId": "X", "claimType": "stop_rule",
                     "claimText": "the stop goes under the low",
                     "confidenceState": "single_source", "sourceIds": ["EVSRC|X|1"]}
            question = {"questionId": "EQ|X|1", "claimId": "CLAIM|X|1",
                        "questionText": "which low?",
                        "questionType": "missing_stop_placement",
                        "blockingStatus": "blocks_rule_candidate",
                        "answerStatus": answer_status,
                        "researchStatus": research_status,
                        "reason": "unstated", "priority": "high"}
            return types.SimpleNamespace(
                claims={"CLAIM|X|1": claim}, links={}, items={},
                questions={"EQ|X|1": question}, contradictions={}, hypotheses={})

        def blockers_for(answer_status, research_status):
            view = ru.corpus_view(index_with(answer_status, research_status), "X")
            return {b["questionId"] for b in ru.eligibility(view)["blockers"]
                    if b["blockerType"] == "BLOCKING_QUESTION"}

        # Answered, but research still open: it must NOT block.
        self.assertEqual(blockers_for("answered", "open"), set(),
                         "an ANSWERED question still blocks -- researchStatus is "
                         "being read where answerStatus was intended")
        # Unanswered, but research closed: it must still block.
        self.assertEqual(blockers_for("unanswered", "complete"), {"EQ|X|1"},
                         "an UNANSWERED question stopped blocking because research "
                         "was closed -- the wrong field is gating the blocker")

    def test_blocking_questions_are_resolved_by_identifier_not_text(self):
        surfaced = {b["questionId"] for b in self.result["blockers"]
                    if b["blockerType"] == "BLOCKING_QUESTION"}
        corpus = {e["claimId"] for e in self.entries()}
        for qid in surfaced:
            self.assertIn(self.idx.questions[qid]["claimId"], corpus)

    def test_every_required_category_blocker_states_a_research_need(self):
        for blocker in self.result["blockers"]:
            if blocker["blockerType"].startswith("REQUIRED_CATEGORY_"):
                self.assertTrue(blocker["researchNeed"])
                self.assertTrue(blocker["requiredBecause"])


class TestEligibilityIsolation(EligibilityCase):

    def test_the_cross_corpus_contradiction_blocks_without_importing_evidence(self):
        blockers = [b for b in self.result["blockers"]
                    if b["blockerType"] == "BLOCKING_CONTRADICTION"]
        self.assertTrue(blockers)
        cross = [b for b in blockers if b["scope"] == "CROSS_CORPUS"]
        self.assertTrue(cross)
        for blocker in cross:
            self.assertEqual(blocker["foreignTraderId"], ALEX)
            self.assertTrue(blocker["foreignClaimId"].startswith("CLAIM|ALEX"))
            # identified for conflict reporting ONLY -- no foreign content
            self.assertNotIn("normalizedClaim", blocker)
            self.assertNotIn("evidence", blocker)

    def test_xcontra_20260728_001_is_present_and_not_resolved(self):
        blocker = next(b for b in self.result["blockers"]
                       if b.get("contradictionId") == "XCONTRA|20260728|001")
        self.assertEqual(blocker["status"], "open")
        self.assertEqual(blocker["severity"], "blocking")
        self.assertNotIn("resolution", blocker)

    def test_no_alex_claim_id_appears_as_a_corpus_side_blocker(self):
        for blocker in self.result["blockers"]:
            for key in ("affectedClaimId", "corpusClaimId"):
                if blocker.get(key):
                    self.assertNotIn("ALEX", blocker[key])
        for row in self.result["categories"].values():
            for claim_id in row["claimIds"]:
                self.assertNotIn("ALEX", claim_id)

    def test_ambiguous_corpus_fails_closed_before_eligibility(self):
        idx = index()
        victim = next(iter(idx.claims))
        idx.claims = dict(idx.claims)
        idx.claims[victim] = dict(idx.claims[victim], traderId=None)
        with self.assertRaises(ru.CorpusAmbiguous):
            ru.eligibility(ru.corpus_view(idx, TJR))


class TestEligibilityFreezeFirewall(EligibilityCase):

    def test_no_numerical_readiness_score_exists(self):
        def walk(node):
            if isinstance(node, dict):
                for key, value in node.items():
                    self.assertNotIsInstance(value, float, key)
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)
        walk(self.result)

    def test_eligibility_is_a_two_valued_fact_not_a_grade(self):
        self.assertIn(self.result["eligibility"], (ru.ELIGIBLE, ru.BLOCKED))

    def test_the_result_states_it_authorizes_nothing(self):
        self.assertIs(self.result["informationalOnly"], True)
        self.assertEqual(self.result["promotionStatus"], "NOT_A_TRADING_RULE")
        self.assertEqual(self.result["lane"], "RESEARCH")
        for word in ("freeze", "frozen", "authorized", "approved"):
            self.assertNotIn(word, json.dumps(
                {k: v for k, v in self.result.items() if k != "meaning"}).lower())

    def test_eligibility_emits_no_promotion_stage(self):
        blob = json.dumps(self.result)
        for stage in ("promotionState", "DISCOVERED", "PAPER_", "LIVE_",
                      "PRODUCTION_", "IMPLEMENTATION_", "REPLAY_", "SHADOW_"):
            self.assertNotIn(stage, blob)

    def test_eligibility_creates_no_record_and_mutates_no_file(self):
        roots = [os.path.join(ru.EVIDENCE_ROOT, d)
                 for d in ("claims", "items", "links", "questions",
                           "contradictions", "hypotheses", "proposals")]
        def digest():
            out = {}
            for root in roots:
                for path in sorted(glob.glob(os.path.join(root, "*.json"))):
                    with open(path, "rb") as handle:
                        out[path] = hashlib.sha256(handle.read()).hexdigest()
            return out
        before = digest()
        ru.eligibility(ru.corpus_view(index(), TJR))
        # The digest above already covers "proposals" by path AND content, so it fails if
        # this step creates or edits a proposal. A trailing assertion that the directory is
        # globally EMPTY added no detection power and instead froze a corpus state, breaking
        # once the first authorized rule candidates existed. Removed, not rebaselined.
        self.assertEqual(digest(), before)


# ---------------------------------------------------------------------------
# MOGO-019 Step 4 -- research-gap resolution planner
# ---------------------------------------------------------------------------

class PlannerCase(EligibilityCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.gaps = ru.load_gaps()
        cls.plan = ru.research_plan(cls.view, cls.result, cls.gaps)

    def replanned(self, gaps=None, approved=None, result=None):
        return ru.research_plan(self.view, result or self.result,
                                self.gaps if gaps is None else gaps,
                                approved_destinations=approved)


class TestPlanningIsDeterministicAndComplete(PlannerCase):

    def test_planning_is_byte_identical_across_runs(self):
        a = json.dumps(self.replanned(), sort_keys=True)
        b = json.dumps(self.replanned(), sort_keys=True)
        self.assertEqual(a, b)

    def test_every_blocker_receives_exactly_one_plan_item(self):
        self.assertEqual(self.plan["itemCount"], self.result["blockerCount"])
        ids = [i["blockerId"] for i in self.plan["items"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_item_carries_a_known_action_and_autonomy(self):
        for item in self.plan["items"]:
            self.assertIn(item["researchAction"], ru._ACTION_RANK)
            self.assertEqual(item["autonomy"],
                             ru._AUTONOMY[item["researchAction"]])

    def test_counts_reconcile_with_items(self):
        self.assertEqual(sum(self.plan["countsByAction"].values()),
                         self.plan["itemCount"])
        self.assertEqual(sum(self.plan["countsByAutonomy"].values()),
                         self.plan["itemCount"])

    def test_ordering_is_deterministic_and_explained(self):
        self.assertTrue(self.plan["orderingRule"])
        keys = [(0 if i["requiredCategory"] else 1,
                 ru._ACTION_RANK[i["researchAction"]], i["blockerId"])
                for i in self.plan["items"]]
        self.assertEqual(keys, sorted(keys))

    def test_no_opaque_numeric_priority_exists(self):
        def walk(node):
            if isinstance(node, dict):
                for key, value in node.items():
                    self.assertNotIsInstance(value, float, key)
                    self.assertNotIn("score", key.lower())
                    self.assertNotIn("priority", key.lower())
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)
        walk(self.plan["items"])


class TestExistingCorpusFirst(PlannerCase):

    def test_a_partially_answered_gap_routes_to_searching_what_we_have(self):
        item = next(i for i in self.plan["items"]
                    if i["blockerId"] == "REQUIRED_CATEGORY|entry_rule")
        self.assertEqual(item["researchAction"], ru.SEARCH_EXISTING_CORPUS)
        self.assertEqual(item["autonomy"], ru.ACTIONABLE_NOW)
        gap = next(g for g in self.gaps if g["gapId"] == item["knowledgeGapId"])
        self.assertEqual(gap["answerStatus"], "partially_answered")
        self.assertTrue(gap["currentBestAnswer"])

    def test_searching_existing_corpus_outranks_acquisition(self):
        self.assertLess(ru._ACTION_RANK[ru.SEARCH_EXISTING_CORPUS],
                        ru._ACTION_RANK[ru.AUTHORIZATION_REQUIRED])
        self.assertLess(ru._ACTION_RANK[ru.SEARCH_EXISTING_CORPUS],
                        ru._ACTION_RANK[ru.ACQUIRE_FROM_APPROVED_SOURCE])

    def test_an_unanswered_gap_does_not_claim_the_corpus_has_the_answer(self):
        gaps = copy.deepcopy(self.gaps)
        for gap in gaps:
            if gap.get("traderId") == TJR:
                gap["answerStatus"] = "unanswered"
                gap["currentBestAnswer"] = None
        plan = self.replanned(gaps=gaps)
        self.assertEqual(plan["countsByAction"].get(ru.SEARCH_EXISTING_CORPUS, 0), 0)


class TestAuthorizationAwareness(PlannerCase):

    def test_the_approved_source_is_reported_without_granting_acquisition(self):
        item = self.plan["items"][0]
        auth = item["authorization"]
        self.assertTrue(auth["approvedSource"])
        self.assertEqual(auth["approvedOperations"], ["metadata"])
        # approved SOURCE is not an approved ANSWER
        self.assertFalse(auth["operationAvailable"])
        self.assertFalse(auth["autonomousAcquisitionPermitted"])

    def test_transcript_needs_are_never_autonomously_actionable_today(self):
        for item in self.plan["items"]:
            if item["researchAction"] == ru.AUTHORIZATION_REQUIRED:
                self.assertEqual(item["autonomy"], ru.AFTER_AUTHORIZATION)
                self.assertFalse(item["autonomousActionPermittedNow"])

    def test_an_unknown_authorization_surface_fails_closed(self):
        plan = self.replanned(approved={})
        for item in plan["items"]:
            self.assertFalse(item["authorization"]["approvedSource"])
            self.assertFalse(item["authorization"]["autonomousAcquisitionPermitted"])
        self.assertEqual(plan["countsByAction"].get(
            ru.ACQUIRE_FROM_APPROVED_SOURCE, 0), 0)

    def test_MUTATION_authorizing_transcripts_would_change_the_plan(self):
        """The authorization predicate must be capable of mattering."""
        widened = {"SRC|youtube|11cd2542b5b0": {
            "sourceLabel": "TJRTrades", "operation": "transcript"}}
        plan = self.replanned(approved=widened)
        self.assertGreater(
            plan["countsByAction"].get(ru.ACQUIRE_FROM_APPROVED_SOURCE, 0), 0)
        self.assertEqual(plan["countsByAction"].get(ru.AUTHORIZATION_REQUIRED, 0), 0)
        # and the real, unwidened plan authorizes none of it
        self.assertEqual(self.plan["countsByAction"].get(
            ru.ACQUIRE_FROM_APPROVED_SOURCE, 0), 0)

    def test_the_planner_never_mutates_the_authorization_registry(self):
        import sys as _sys
        _sys.path.insert(0, os.path.join(REPO_ROOT, "platform", "src"))
        from mogo_platform.runtime import connector_authorization as gate
        before = dict(gate.APPROVED_DESTINATIONS)
        before_ops = {s: gate.APPROVED_DESTINATIONS[s]["operation"]
                      for s in gate.approved_source_ids()}
        self.replanned()
        self.assertEqual(dict(gate.APPROVED_DESTINATIONS), before)
        self.assertEqual({s: gate.APPROVED_DESTINATIONS[s]["operation"]
                          for s in gate.approved_source_ids()}, before_ops)
        self.assertEqual(set(before_ops.values()), {"metadata"})


class TestDirectTraderClarificationIsPreserved(PlannerCase):

    def test_risk_rule_routes_to_a_direct_question_not_more_video(self):
        """The gap itself records 'direct question to trader'. That must not be
        silently converted into passive collection."""
        item = next(i for i in self.plan["items"]
                    if i["blockerId"] == "REQUIRED_CATEGORY|risk_rule")
        self.assertEqual(item["researchAction"], ru.DIRECT_TRADER_CLARIFICATION)
        self.assertEqual(item["autonomy"], ru.HUMAN_INPUT)
        self.assertEqual(item["recommendedNextSourceType"],
                         "direct question to trader")
        self.assertNotEqual(item["researchAction"], ru.AUTHORIZATION_REQUIRED)
        self.assertNotEqual(item["researchAction"],
                            ru.ACQUIRE_FROM_APPROVED_SOURCE)

    def test_direct_only_and_transcript_only_route_differently(self):
        self.assertEqual(ru._route_recommended_source("direct question to trader"),
                         ru.DIRECT_TRADER_CLARIFICATION)
        self.assertEqual(
            ru._route_recommended_source("additional transcript on targets"),
            ru.AUTHORIZATION_REQUIRED)

    def test_an_unrecognised_recommendation_fails_closed(self):
        for bad in (None, "", "   ", "consult the oracle", 42, []):
            with self.subTest(value=bad):
                self.assertIsNone(ru._route_recommended_source(bad))

    def test_a_meaning_question_asks_the_educator_not_the_archive(self):
        for question_type in ("ambiguous_statement", "unclear_scope",
                              "implied_requirement", "unruled_exception"):
            self.assertEqual(ru._QUESTION_ROUTE[question_type],
                             ru.DIRECT_TRADER_CLARIFICATION)


class TestContradictionRouting(PlannerCase):

    def test_the_cross_corpus_contradiction_routes_to_an_operator_ruling(self):
        item = next(i for i in self.plan["items"]
                    if i["blockerId"] == "XCONTRA|20260728|001")
        self.assertEqual(item["researchAction"], ru.OPERATOR_RULING_REQUIRED)
        self.assertEqual(item["autonomy"], ru.HUMAN_INPUT)
        self.assertEqual(item["foreignTraderId"], ALEX)

    def test_the_foreign_claim_is_referenced_for_routing_only(self):
        item = next(i for i in self.plan["items"]
                    if i["blockerId"] == "XCONTRA|20260728|001")
        self.assertTrue(item["foreignClaimId"].startswith("CLAIM|ALEX"))
        # identity only -- no foreign content
        self.assertNotIn("normalizedClaim", item)
        self.assertNotIn("evidence", item)
        self.assertEqual(item["currentSupportingEvidence"]["claimIds"], [])

    def test_a_contradiction_is_not_treated_as_missing_information(self):
        for kind in ("DIRECTIONAL", "CONDITIONAL_SCOPE", "SCOPE_MISMATCH"):
            self.assertEqual(ru._CONTRADICTION_ROUTE[kind],
                             ru.OPERATOR_RULING_REQUIRED)

    def test_no_contradiction_is_resolved_by_the_planner(self):
        for item in self.plan["items"]:
            self.assertNotIn("resolution", item)
        source = next(c for c in self.idx.contradictions.values()
                      if c["contradictionId"] == "XCONTRA|20260728|001")
        self.assertIsNone(source["resolution"])
        self.assertEqual(source["status"], "open")


class TestPlannerFailsClosed(PlannerCase):

    def test_an_unknown_question_type_fails_closed(self):
        result = copy.deepcopy(self.result)
        for blocker in result["blockers"]:
            if blocker["blockerType"] == "BLOCKING_QUESTION":
                blocker["questionType"] = "something_new"
        plan = self.replanned(result=result)
        unknown = [i for i in plan["items"]
                   if i["blockerType"] == "BLOCKING_QUESTION"]
        self.assertTrue(unknown)
        for item in unknown:
            self.assertEqual(item["researchAction"], ru.NO_RESOLUTION_PATH)
            self.assertEqual(item["autonomy"], ru.NO_KNOWN_PATH)
            self.assertFalse(item["autonomousActionPermittedNow"])

    def test_an_unknown_contradiction_type_fails_closed(self):
        result = copy.deepcopy(self.result)
        for blocker in result["blockers"]:
            if blocker["blockerType"] == "BLOCKING_CONTRADICTION":
                blocker["contradictionType"] = "MYSTERY"
                blocker["scope"] = "INTERNAL"
        plan = self.replanned(result=result)
        item = next(i for i in plan["items"]
                    if i["blockerType"] == "BLOCKING_CONTRADICTION")
        self.assertEqual(item["researchAction"], ru.NO_RESOLUTION_PATH)

    def test_unknown_is_never_classified_as_autonomous(self):
        self.assertEqual(ru._AUTONOMY[ru.NO_RESOLUTION_PATH], ru.NO_KNOWN_PATH)
        self.assertNotEqual(ru._AUTONOMY[ru.NO_RESOLUTION_PATH],
                            ru.ACTIONABLE_NOW)


class TestPlannerIsolationAndSideEffects(PlannerCase):

    def test_no_alex_claim_enters_the_plan(self):
        for item in self.plan["items"]:
            for claim_id in item["currentSupportingEvidence"]["claimIds"]:
                self.assertNotIn("ALEX", claim_id)
            if item["blockerId"].startswith("CLAIM"):
                self.assertNotIn("ALEX", item["blockerId"])

    def test_planning_performs_no_acquisition_and_writes_nothing(self):
        roots = [os.path.join(ru.EVIDENCE_ROOT, d)
                 for d in ("claims", "items", "gaps", "questions",
                           "contradictions", "proposals")]
        def digest():
            out = {}
            for root in roots:
                for path in sorted(glob.glob(os.path.join(root, "*.json"))):
                    with open(path, "rb") as handle:
                        out[path] = hashlib.sha256(handle.read()).hexdigest()
            return out
        before = digest()
        self.replanned()
        ru.render_plan(self.plan)
        # As above: the digest already spans "proposals" by path and content, so planning
        # writing a proposal fails here. The global-emptiness assertion that followed was
        # redundant and corpus-frozen. Removed, not rebaselined.
        self.assertEqual(digest(), before)

    def test_the_plan_states_it_is_not_an_authorization(self):
        self.assertIs(self.plan["planningOnly"], True)
        self.assertIn("not an authorization", self.plan["meaning"].lower())
        self.assertEqual(self.plan["promotionStatus"], "NOT_A_TRADING_RULE")
        self.assertEqual(self.plan["lane"], "RESEARCH")

    def test_the_plan_creates_no_strategy_or_proposal_object(self):
        blob = json.dumps(self.plan)
        for forbidden in ("proposalId", "blueprintId", "ruleId",
                          "promotionState", "specification"):
            self.assertNotIn(forbidden, blob)


if __name__ == "__main__":
    unittest.main()

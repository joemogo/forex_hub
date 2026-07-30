"""MOGO-002.5 Phase 8 — tests for the strategy-fidelity toolchain.

Covers: stable serialization/parsing, version handling, every comparison status,
missing/differing/extra/ambiguous handling, deterministic report output, report
aggregation, and backward compatibility.
"""
import copy
import json
import os
import sys
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts", "strategy_fidelity"))

import fidelity_model as fm          # noqa: E402
import fidelity_compare as fc        # noqa: E402
import alex_specification as aspec   # noqa: E402
import alex_manifest as amanifest    # noqa: E402
import build_fidelity_report as brep # noqa: E402


def _src(kind="repository_constant", locator="index.html:1"):
    return [fm.rule_source_reference(kind, locator)]


def _rule(rid, classification="EXPLICIT", category="SETUP", required=True,
          deterministic=True, **kw):
    return fm.strategy_rule(rid, "v1", "Title " + rid, "Statement " + rid,
                            classification, category, required, deterministic,
                            _src(), **kw)


class TestModelValidation(unittest.TestCase):

    def test_rule_requires_a_source_reference(self):
        with self.assertRaises(fm.FidelityModelError):
            fm.strategy_rule("R", "v1", "t", "s", "EXPLICIT", "SETUP", True, True, [])

    def test_unknown_vocabulary_is_rejected(self):
        for bad in [("NOT_A_CLASS", "SETUP"), ("EXPLICIT", "NOT_A_CATEGORY")]:
            with self.assertRaises(fm.FidelityModelError):
                fm.strategy_rule("R", "v1", "t", "s", bad[0], bad[1], True, True, _src())

    def test_discretionary_rule_cannot_be_required(self):
        """The source cannot both mandate an outcome and leave it to judgement."""
        with self.assertRaises(fm.FidelityModelError):
            _rule("R", classification="DISCRETIONARY", required=True)

    def test_unresolved_rule_cannot_be_deterministic(self):
        with self.assertRaises(fm.FidelityModelError):
            _rule("R", classification="UNRESOLVED", deterministic=True)

    def test_duplicate_rule_ids_are_rejected(self):
        with self.assertRaises(fm.FidelityModelError):
            fm.strategy_specification("s", "v1", "t", [_rule("A"), _rule("A")])

    def test_unknown_dependency_is_rejected(self):
        with self.assertRaises(fm.FidelityModelError):
            fm.strategy_specification("s", "v1", "t", [_rule("A", dependencies=["MISSING"])])

    def test_implemented_without_inspection_is_rejected(self):
        """'Do not claim a rule is implemented unless the code path has been inspected.'"""
        with self.assertRaises(fm.FidelityModelError):
            fm.implementation_rule_mapping("R", "IMPLEMENTED",
                                           implementation_references=[{"locator": "x"}],
                                           inspected=False)

    def test_implemented_without_reference_is_rejected(self):
        with self.assertRaises(fm.FidelityModelError):
            fm.implementation_rule_mapping("R", "IMPLEMENTED", inspected=True)

    def test_approximated_requires_detail(self):
        with self.assertRaises(fm.FidelityModelError):
            fm.implementation_rule_mapping("R", "APPROXIMATED",
                                           implementation_references=[{"locator": "x"}],
                                           inspected=True)

    def test_unknown_status_needs_no_inspection(self):
        m = fm.implementation_rule_mapping("R", "UNKNOWN")
        self.assertEqual(m["implementationStatus"], "UNKNOWN")
        self.assertFalse(m["inspected"])

    def test_extra_rule_requires_references(self):
        with self.assertRaises(fm.FidelityModelError):
            fm.extra_implementation_rule("X", "t", "RISK", "d", [])

    def test_finding_requires_rationale(self):
        with self.assertRaises(fm.FidelityModelError):
            fm.strategy_fidelity_finding("R", "MATCH", "SETUP", "EXPLICIT", True, True, "")


class TestSerialization(unittest.TestCase):

    def test_round_trip_is_lossless(self):
        spec = fm.strategy_specification("s", "v1", "t", [_rule("A"), _rule("B")])
        self.assertEqual(fm.loads(fm.dumps(spec)), spec)

    def test_serialization_is_deterministic(self):
        spec = fm.strategy_specification("s", "v1", "t", [_rule("A")])
        self.assertEqual(fm.dumps(spec), fm.dumps(copy.deepcopy(spec)))

    def test_rule_set_hash_is_key_order_independent(self):
        a = fm.strategy_specification("s", "v1", "t", [_rule("A")])
        b = fm.strategy_specification("s", "v1", "t", [_rule("A")])
        self.assertEqual(a["ruleSetHash"], b["ruleSetHash"])

    def test_rule_set_hash_changes_when_a_rule_changes(self):
        a = fm.strategy_specification("s", "v1", "t", [_rule("A")])
        b = fm.strategy_specification("s", "v1", "t", [_rule("A", required=False)])
        self.assertNotEqual(a["ruleSetHash"], b["ruleSetHash"])

    def test_rule_set_hash_ignores_note_only_edits(self):
        """Hash covers the rule's SUBSTANCE, so re-wording a note is not a spec change."""
        a = fm.strategy_specification("s", "v1", "t", [_rule("A", notes="one")])
        b = fm.strategy_specification("s", "v1", "t", [_rule("A", notes="two")])
        self.assertEqual(a["ruleSetHash"], b["ruleSetHash"])


class TestVersionHandling(unittest.TestCase):

    def test_version_reference_requires_identity(self):
        with self.assertRaises(fm.FidelityModelError):
            fm.strategy_version_reference("", "v1")
        with self.assertRaises(fm.FidelityModelError):
            fm.strategy_version_reference("s", "")

    def test_absent_versions_are_explicit_null_not_fabricated(self):
        ref = fm.strategy_version_reference("s", "v1")
        for k in ("implementationVersion", "engineVersion", "ruleSetHash",
                  "configurationHash", "decisionTraceVersion"):
            self.assertIsNone(ref[k], k)

    def test_strategy_id_mismatch_is_rejected(self):
        spec = fm.strategy_specification("alpha", "v1", "t", [_rule("A")])
        man = fm.strategy_implementation_manifest("beta", "i1", "v1", [])
        with self.assertRaises(fm.FidelityModelError):
            fc.compare(spec, man)

    def test_specification_version_mismatch_is_reported_not_raised(self):
        """A version skew must be surfaced, not silently tolerated or fatal."""
        spec = fm.strategy_specification("s", "v2", "t", [_rule("A")])
        man = fm.strategy_implementation_manifest("s", "i1", "v1", [])
        self.assertTrue(fc.compare(spec, man)["specificationVersionMismatch"])


class TestComparisonStatuses(unittest.TestCase):

    def _compare_one(self, rule, mapping):
        spec = fm.strategy_specification("s", "v1", "t", [rule])
        man = fm.strategy_implementation_manifest("s", "i1", "v1",
                                                  [mapping] if mapping else [])
        return fc.compare(spec, man)["findings"][0]

    def test_explicit_implemented_is_match(self):
        f = self._compare_one(_rule("A"), fm.implementation_rule_mapping(
            "A", "IMPLEMENTED", implementation_references=[{"locator": "x"}], inspected=True))
        self.assertEqual(f["status"], "MATCH")

    def test_not_implemented_is_missing(self):
        f = self._compare_one(_rule("A"), fm.implementation_rule_mapping("A", "NOT_IMPLEMENTED"))
        self.assertEqual(f["status"], "MISSING_IMPLEMENTATION")

    def test_unsupported_is_implementation_differs(self):
        f = self._compare_one(_rule("A"), fm.implementation_rule_mapping("A", "UNSUPPORTED"))
        self.assertEqual(f["status"], "IMPLEMENTATION_DIFFERS")

    def test_approximated_is_approximated(self):
        f = self._compare_one(_rule("A"), fm.implementation_rule_mapping(
            "A", "APPROXIMATED", implementation_references=[{"locator": "x"}],
            inspected=True, approximation_detail="substituted a threshold"))
        self.assertEqual(f["status"], "APPROXIMATED")
        self.assertIn("substituted a threshold", f["rationale"])

    def test_unknown_status_is_unverifiable_not_missing(self):
        """Absence of inspection is not evidence of absence of code."""
        f = self._compare_one(_rule("A"), fm.implementation_rule_mapping("A", "UNKNOWN"))
        self.assertEqual(f["status"], "UNVERIFIABLE")

    def test_absent_mapping_is_unverifiable_not_missing(self):
        f = self._compare_one(_rule("A"), None)
        self.assertEqual(f["status"], "UNVERIFIABLE")

    def test_unresolved_rule_is_always_ambiguous_even_when_implemented(self):
        """The central guarantee: uncertainty is never converted into a MATCH."""
        f = self._compare_one(
            _rule("A", classification="UNRESOLVED", deterministic=False),
            fm.implementation_rule_mapping("A", "IMPLEMENTED",
                                           implementation_references=[{"locator": "x"}],
                                           inspected=True))
        self.assertEqual(f["status"], "AMBIGUOUS")

    def test_discretionary_rule_is_not_applicable_even_when_implemented(self):
        f = self._compare_one(
            _rule("A", classification="DISCRETIONARY", required=False, deterministic=False),
            fm.implementation_rule_mapping("A", "IMPLEMENTED",
                                           implementation_references=[{"locator": "x"}],
                                           inspected=True))
        self.assertEqual(f["status"], "NOT_APPLICABLE")

    def test_discretionary_rule_is_not_applicable_even_when_missing(self):
        """Omitting a rule the source never mandated is not a fidelity failure."""
        f = self._compare_one(
            _rule("A", classification="DISCRETIONARY", required=False, deterministic=False),
            fm.implementation_rule_mapping("A", "NOT_IMPLEMENTED"))
        self.assertEqual(f["status"], "NOT_APPLICABLE")

    def test_inferred_rule_without_test_is_unverifiable(self):
        f = self._compare_one(
            _rule("A", classification="INFERRED"),
            fm.implementation_rule_mapping("A", "IMPLEMENTED",
                                           implementation_references=[{"locator": "x"}],
                                           inspected=True))
        self.assertEqual(f["status"], "UNVERIFIABLE")

    def test_inferred_rule_with_test_is_approximated_never_match(self):
        f = self._compare_one(
            _rule("A", classification="INFERRED"),
            fm.implementation_rule_mapping("A", "IMPLEMENTED",
                                           implementation_references=[{"locator": "x"}],
                                           inspected=True, tests=["t.js"]))
        self.assertEqual(f["status"], "APPROXIMATED")

    def test_orphan_mapping_is_extra_implementation_rule(self):
        spec = fm.strategy_specification("s", "v1", "t", [_rule("A")])
        man = fm.strategy_implementation_manifest("s", "i1", "v1", [
            fm.implementation_rule_mapping("A", "UNKNOWN"),
            fm.implementation_rule_mapping("GHOST", "UNKNOWN")])
        statuses = {f["ruleId"]: f["status"] for f in fc.compare(spec, man)["findings"]}
        self.assertEqual(statuses["GHOST"], "EXTRA_IMPLEMENTATION_RULE")

    def test_declared_extra_rules_become_findings(self):
        spec = fm.strategy_specification("s", "v1", "t", [_rule("A")])
        man = fm.strategy_implementation_manifest(
            "s", "i1", "v1", [fm.implementation_rule_mapping("A", "UNKNOWN")],
            extra_implementation_rules=[fm.extra_implementation_rule(
                "X1", "extra", "RISK", "desc", [{"locator": "x"}])])
        f = [x for x in fc.compare(spec, man)["findings"] if x["ruleId"] == "X1"][0]
        self.assertEqual(f["status"], "EXTRA_IMPLEMENTATION_RULE")
        self.assertEqual(f["category"], "RISK")


class TestAggregation(unittest.TestCase):

    def setUp(self):
        self.spec = aspec.build_specification()
        self.man = amanifest.build_manifest()
        self.cmp = fc.compare(self.spec, self.man)

    def test_every_category_appears_in_summaries(self):
        cats = [c["category"] for c in self.cmp["categorySummaries"]]
        self.assertEqual(cats, fm.RULE_CATEGORIES)

    def test_category_counts_sum_to_finding_count(self):
        total = sum(c["ruleCount"] for c in self.cmp["categorySummaries"])
        self.assertEqual(total, len(self.cmp["findings"]))

    def test_coverage_reports_numerator_and_denominator(self):
        for key in ("explicitRuleCoverage", "requiredRuleCoverage",
                    "deterministicRuleFidelity", "riskFidelity",
                    "tradeManagementFidelity"):
            c = self.cmp["coverage"][key]
            self.assertIn("matched", c)
            self.assertIn("total", c)
            self.assertLessEqual(c["matched"], c["total"])

    def test_unmatched_rule_ids_are_listed_not_just_counted(self):
        c = self.cmp["coverage"]["requiredRuleCoverage"]
        self.assertEqual(len(c["unmatchedRuleIds"]), c["total"] - c["matched"])

    def test_status_totals_exclude_extra_rules(self):
        st = self.cmp["coverage"]["statusTotals"]
        self.assertEqual(st["EXTRA_IMPLEMENTATION_RULE"], 0,
                         "extra rules are counted separately, never inside spec totals")
        self.assertGreater(self.cmp["coverage"]["extraImplementationRuleCount"], 0)


class TestAlexArtifacts(unittest.TestCase):
    """These assert repository truth, so they fail loudly if the artifact changes."""

    def test_specification_extracts_from_the_protected_constant(self):
        spec = aspec.build_specification()
        self.assertEqual(spec["strategyId"], "alex_g_sr_v1")
        self.assertEqual(spec["extractedFrom"]["artifact"], "RULES_ALEXG")
        self.assertGreater(spec["ruleCount"], 0)

    def test_every_rule_cites_a_source_reference(self):
        for r in aspec.build_specification()["rules"]:
            self.assertTrue(r["sourceReferences"], r["id"])
            self.assertEqual(r["sourceReferences"][0]["kind"], "repository_constant")

    def test_specification_never_cites_the_trader_intelligence_library(self):
        """DECISION|MOGO|20260727|004: the engine's rules are MOGO's own, not the educator's."""
        for r in aspec.build_specification()["rules"]:
            for ref in r["sourceReferences"]:
                self.assertNotEqual(ref["kind"], "evidence_claim", r["id"])

    def test_unclassified_concept_raises_rather_than_being_dropped(self):
        saved = aspec.CONCEPT_RULES
        try:
            aspec.CONCEPT_RULES = saved[:-1]
            with self.assertRaises(aspec.SpecExtractionError):
                aspec.build_specification()
        finally:
            aspec.CONCEPT_RULES = saved

    def test_missing_artifact_raises_stop_condition_error(self):
        with self.assertRaises(aspec.SpecExtractionError):
            aspec.extract_rules_alexg(os.path.join(REPO_ROOT, "README.md"))

    def test_all_manifest_code_references_resolve(self):
        man = amanifest.build_manifest()
        self.assertEqual(man["referenceVerification"]["problemCount"], 0,
                         man["referenceVerification"]["problems"])

    def test_manifest_marks_inspected_for_every_implemented_rule(self):
        for m in amanifest.build_manifest()["mappings"]:
            if m["implementationStatus"] in ("IMPLEMENTED", "APPROXIMATED"):
                self.assertTrue(m["inspected"], m["ruleId"])

    def test_extra_rules_declare_whether_they_affect_trading(self):
        for e in amanifest.build_manifest()["extraImplementationRules"]:
            self.assertIsInstance(e["affectsTradingBehavior"], bool)


class TestReport(unittest.TestCase):

    def setUp(self):
        self.report = brep.build_report()

    def test_profitability_is_unconditionally_unvalidated(self):
        self.assertEqual(self.report["profitabilityStatus"], "UNVALIDATED")

    def test_execution_readiness_is_not_verified_and_says_why(self):
        er = self.report["executionReadiness"]
        self.assertEqual(er["status"], "NOT_VERIFIED")
        self.assertGreater(er["failedCount"], 0)
        for c in er["criteria"]:
            self.assertTrue(c["evidence"], c["criterion"])

    def test_report_states_every_required_version(self):
        vr = self.report["versionReference"]
        self.assertTrue(vr["specificationVersion"])
        self.assertTrue(vr["implementationVersion"])
        self.assertTrue(self.report["reportGeneratorVersion"])
        self.assertTrue(vr["decisionTraceVersion"])

    def test_report_reuses_the_existing_decision_trace_version(self):
        self.assertEqual(self.report["versionReference"]["decisionTraceVersion"],
                         "mogo.decision-event.v1")

    def test_all_finding_buckets_are_present_even_when_empty(self):
        for key in ("verifiedMatches", "missingImplementation", "differingImplementation",
                    "approximations", "extraImplementationLogic", "ambiguousRules",
                    "unverifiableRules", "notApplicable"):
            self.assertIn(key, self.report["findingsByStatus"])

    def test_knowledge_gaps_each_carry_a_completion_path(self):
        gaps = self.report["missingStrategyKnowledge"]
        self.assertGreater(len(gaps), 0)
        for g in gaps:
            self.assertTrue(g["completionPath"], g["id"])
            self.assertTrue(g["evidence"], g["id"])

    def test_risk_gap_is_reported_because_the_spec_has_no_risk_rules(self):
        ids = {g["id"] for g in self.report["missingStrategyKnowledge"]}
        self.assertIn("GAP-RISK-001", ids)
        self.assertEqual(self.report["coverage"]["riskFidelity"]["total"], 0)

    def test_report_is_deterministic(self):
        self.assertEqual(fm.dumps(self.report), fm.dumps(brep.build_report()))

    def test_markdown_renders_and_states_the_headline_statuses(self):
        md = brep.render_markdown(self.report)
        self.assertIn("UNVALIDATED", md)
        self.assertIn("NOT_VERIFIED", md)
        self.assertIn("Risk fidelity", md)

    def test_markdown_is_deterministic(self):
        self.assertEqual(brep.render_markdown(self.report),
                         brep.render_markdown(brep.build_report()))


class TestBackwardCompatibility(unittest.TestCase):

    def test_report_parses_as_plain_json(self):
        json.loads(fm.dumps(brep.build_report()))

    def test_unknown_future_fields_survive_a_round_trip(self):
        """A newer generator's extra fields must not be lost by an older parser path."""
        spec = fm.strategy_specification("s", "v1", "t", [_rule("A")])
        spec["someFutureField"] = {"added": "later"}
        self.assertEqual(fm.loads(fm.dumps(spec))["someFutureField"], {"added": "later"})

    def test_model_version_is_stamped_on_every_top_level_record(self):
        self.assertEqual(
            fm.strategy_specification("s", "v1", "t", [])["modelVersion"],
            fm.FIDELITY_MODEL_VERSION)
        self.assertEqual(
            fm.strategy_implementation_manifest("s", "i", "v1", [])["modelVersion"],
            fm.FIDELITY_MODEL_VERSION)


class TestRuleEvaluationTrace(unittest.TestCase):

    def test_trace_requires_a_known_result(self):
        with self.assertRaises(fm.FidelityModelError):
            fm.rule_evaluation_trace("R", "v1", "MAYBE", "eval", "2026-01-01T00:00:00Z")

    def test_trace_carries_a_market_data_pointer_not_a_payload(self):
        t = fm.rule_evaluation_trace(
            "R", "v1", "PASS", "alexGEvaluateRepeatedReaction", "2026-01-01T00:00:00Z",
            market_data_reference={"pair": "EUR_USD", "timeframe": "H1",
                                   "candleCloseTime": "2026-01-01T00:00:00Z"})
        self.assertIn("pair", t["marketDataReference"])
        self.assertNotIn("candles", t["marketDataReference"])

    def test_trace_accepts_the_full_required_field_set(self):
        t = fm.rule_evaluation_trace(
            "ALEX_SIGNAL_STALENESS", "alex_g_sr_v1", "FAIL", "alexGIsSetupSignalStale",
            "2026-01-01T00:00:00Z", observed_input={"ageMinutes": 90}, reason="STATE_SIGNAL_STALE",
            required=True, confidence="HIGH",
            version_reference=fm.strategy_version_reference("alex_g_sr_v1", "alex_g_sr_v1"))
        for k in ("ruleId", "ruleVersion", "observedInput", "result", "reason", "required",
                  "confidence", "evaluator", "timestamp", "versionReference"):
            self.assertIn(k, t)


if __name__ == "__main__":
    unittest.main(verbosity=2)

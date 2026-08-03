#!/usr/bin/env python3
"""ALEX rule-to-evidence join — fixture-based test suite. Pure stdlib (unittest).

    python3 -m unittest discover -s tests/strategy_fidelity -p 'test_*.py' -v
    python3 tests/strategy_fidelity/test_rule_evidence_join.py

Every test drives the REAL generator functions against SYNTHETIC, clearly-marked fixtures. The
suite never reads the operator's Evidence Packages: it must pass on a machine that has none, which
is exactly why the fixtures are built inline rather than copied from a run.

The governing property under test: the join NEVER guesses. A rule links only when a declared
evidence field is genuinely populated, and everything else is classified honestly.
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "strategy_fidelity"))
import build_alex_rule_evidence_join as J  # noqa: E402


def pkg(setup_type="B_breakRetest", **over):
    """A minimal but genuinely shaped Evidence Package."""
    structure = {
        "zoneId": "AGZ|z1", "zoneLow": 1.1, "zoneHigh": 1.11, "zoneCenter": 1.105,
        "zoneStrength": "strong", "zoneQualityAtQualification": "clean",
        "zoneRoleAtQualification": "support", "reactionId": "AGR|r1", "zoneTouchNumber": 4,
        "breakCycleId": ("AGB|c1" if setup_type == "B_breakRetest" else None),
        "brokenDirection": ("downThroughSupport" if setup_type == "B_breakRetest" else None),
        "barsSinceBreak": (14 if setup_type == "B_breakRetest" else None),
    }
    structure.update(over.pop("structureRefs", {}))
    p = {
        "packageId": over.pop("packageId", "PKG|alex_g_sr_v1|20260406|1"),
        "sourceTradeId": "REPLAY|abc123|AGT|1",
        "identity": {"runId": "r" * 64, "strategyId": "alex_g_sr_v1"},
        "configSnapshot": {"config": {"minRR": 2, "riskPercent": 1,
                                      "maxBarsBetweenBreakAndRetest": 50}},
        "objects": {
            "qualifiedSetups": [{
                "setupId": "AGS|alex_g_sr_v1|EUR_USD|H1|z1|" + setup_type + "|r1",
                "setupType": setup_type, "timeframe": "H1",
                "structureRefs": structure,
                "contextRefs": {"session": "London", "dayOfWeek": "Mon", "hourOfDay": 10,
                                "trendContext": "DOWNTREND", "atrAtEntry": 0.0012,
                                "nearestPsych500Level": 1.1, "distanceToPsych500Pips": 5,
                                "nearestPsych100Level": 1.1, "distanceToPsych100Pips": 5},
            }],
            "positions": [{"positionId": "REPLAY|abc123|AGT|1", "direction": "sell",
                           "entryPrice": 1.1, "originalStop": 1.105, "target": 1.09,
                           "plannedRR": 2, "positionSize": 0.2, "riskAmount": 100,
                           "riskPercent": 1}],
            "outcomes": [{"outcomeId": "REPLAY|abc123|AGT|1|outcome",
                          "exitReasonCode": over.pop("result", "Loss"),
                          "recordedResultR": over.pop("resultR", -1),
                          "maePips": over.pop("maePips", 16.0),
                          "mfePips": over.pop("mfePips", 0.0)}],
        },
    }
    p.update(over)
    return p


REGISTER = {"rules": [
    {"ruleId": "AXR-BR", "domain": "break_and_retest", "normalizedStatement": "break then retest",
     "evidenceClass": "EXPLICIT", "authorship": "EDUCATOR", "deterministic": True,
     "confidenceStatus": "emerging", "distinctSourceCount": 1, "supportingClaimIds": ["CLAIM|1"]},
    {"ruleId": "AXR-RZR", "domain": "entry_setup", "normalizedStatement": "repeated reaction",
     "evidenceClass": "EXPLICIT", "authorship": "EDUCATOR", "deterministic": True,
     "confidenceStatus": "emerging", "distinctSourceCount": 1, "supportingClaimIds": ["CLAIM|2"]},
    {"ruleId": "AXR-MISSING", "domain": "entry_confirmation", "normalizedStatement": "engulfing",
     "evidenceClass": "EXPLICIT", "authorship": "EDUCATOR", "deterministic": True,
     "confidenceStatus": "emerging", "distinctSourceCount": 1, "supportingClaimIds": []},
    {"ruleId": "AXR-MOGO", "domain": "trade_management", "normalizedStatement": "break even",
     "evidenceClass": "INFERRED", "authorship": "MOGO", "deterministic": True,
     "confidenceStatus": "emerging", "distinctSourceCount": 0, "supportingClaimIds": []},
    {"ruleId": "AXR-LIVE", "domain": "entry_execution", "normalizedStatement": "entry price",
     "evidenceClass": "EXPLICIT", "authorship": "EDUCATOR", "deterministic": True,
     "confidenceStatus": "emerging", "distinctSourceCount": 1, "supportingClaimIds": []},
    {"ruleId": "AXR-NOFIELD", "domain": "zone_clustering", "normalizedStatement": "cluster",
     "evidenceClass": "EXPLICIT", "authorship": "EDUCATOR", "deterministic": True,
     "confidenceStatus": "emerging", "distinctSourceCount": 1, "supportingClaimIds": []},
    {"ruleId": "AXR-ORPHAN", "domain": "misc", "normalizedStatement": "no matrix row",
     "evidenceClass": "EXPLICIT", "authorship": "EDUCATOR", "deterministic": False,
     "confidenceStatus": "emerging", "distinctSourceCount": 1, "supportingClaimIds": []},
]}

MATRIX = {"⚠️lineageWarning": "convergence not derivation", "rows": [
    {"educatorRuleId": "AXR-BR", "fidelityStatus": "FUNCTIONAL_MATCH",
     "codeLocation": "alexGEvaluateBreakRetest (index.html:3147)", "mogoRuleId": "ALEX_SR_003",
     "implementationBehaviour": "first-class setup type", "lineageNote": "CONVERGENT_NOT_DERIVED",
     "supportingClaimIds": ["CLAIM|1"]},
    {"educatorRuleId": "AXR-RZR", "fidelityStatus": "PRESENT_BUT_DIFFERENT",
     "codeLocation": "alexGEvaluateRepeatedReaction (index.html:3165)", "mogoRuleId": None,
     "implementationBehaviour": "stricter touch requirement", "lineageNote": "MOGO_AUTHORED_PARAMETER",
     "supportingClaimIds": ["CLAIM|2"]},
    {"educatorRuleId": "AXR-MISSING", "fidelityStatus": "MISSING_FROM_MOGO",
     "codeLocation": None, "mogoRuleId": None, "implementationBehaviour": "not implemented",
     "lineageNote": None, "supportingClaimIds": []},
    {"educatorRuleId": "AXR-MOGO", "fidelityStatus": "IMPLEMENTED_WITHOUT_EDUCATOR_SUPPORT",
     "codeLocation": "somewhere", "mogoRuleId": "ALEX_X_009",
     "implementationBehaviour": "MOGO authored", "lineageNote": None, "supportingClaimIds": []},
    {"educatorRuleId": "AXR-LIVE", "fidelityStatus": "PRESENT_BUT_DIFFERENT",
     "codeLocation": "alexGConstructLivePosition (index.html:3956)", "mogoRuleId": None,
     "implementationBehaviour": "entry at qualification close", "lineageNote": None,
     "supportingClaimIds": []},
    {"educatorRuleId": "AXR-NOFIELD", "fidelityStatus": "PRESENT_BUT_DIFFERENT",
     "codeLocation": "alexGAssignCluster (index.html:2763)", "mogoRuleId": None,
     "implementationBehaviour": "clusters zones", "lineageNote": None, "supportingClaimIds": []},
]}


def build(pkgs):
    return J.build(REGISTER, MATRIX, pkgs, "test-run")


class TestJoinStatuses(unittest.TestCase):
    def setUp(self):
        self.records, self.run_ids = build([pkg("B_breakRetest"), pkg("A_repeatedReaction",
                                                                     packageId="PKG|x|2")])
        self.by_id = {r["ruleId"]: r for r in self.records}

    def test_linked_only_when_a_declared_field_is_populated(self):
        r = self.by_id["AXR-BR"]
        self.assertEqual(r["status"], "LINKED")
        self.assertEqual(r["evidence"]["status"], "LINKED")
        self.assertEqual(r["evidence"]["packageCount"], 1, "scoped to its own setup type")
        self.assertIn("breakCycleId", " ".join(r["evidence"]["fieldsObserved"]))

    def test_setup_type_scoping_prevents_over_linking(self):
        """The RZR evaluator must not link to Break & Retest packages via a shared field."""
        r = self.by_id["AXR-RZR"]
        self.assertEqual(r["evidence"]["packageCount"], 1)
        self.assertNotIn("PKG|alex_g_sr_v1|20260406|1", r["evidence"]["packageIds"])

    def test_not_implemented_is_not_confused_with_unlinked(self):
        self.assertEqual(self.by_id["AXR-MISSING"]["status"], "NOT_IMPLEMENTED")

    def test_mogo_authored_rules_are_unsupported(self):
        self.assertEqual(self.by_id["AXR-MOGO"]["status"], "UNSUPPORTED")

    def test_live_only_implementations_are_not_exercised_by_a_replay(self):
        r = self.by_id["AXR-LIVE"]
        self.assertEqual(r["status"], "NOT_EXERCISED")
        self.assertIn("LIVE", r["evidence"]["reason"])

    def test_unmappable_code_location_is_unresolved_never_guessed(self):
        r = self.by_id["AXR-NOFIELD"]
        self.assertEqual(r["status"], "UNRESOLVED")
        self.assertEqual(r["unresolvedReason"], "NO_EVIDENCE_FIELD_EXISTS")

    def test_rule_absent_from_the_matrix_is_unresolved(self):
        r = self.by_id["AXR-ORPHAN"]
        self.assertEqual(r["status"], "UNRESOLVED")
        self.assertEqual(r["unresolvedReason"], "NO_FIDELITY_ROW")

    def test_not_exercised_when_the_field_is_absent_from_every_package(self):
        """A Break & Retest rule with only RZR packages present must not link."""
        records, _ = build([pkg("A_repeatedReaction")])
        by_id = {r["ruleId"]: r for r in records}
        self.assertEqual(by_id["AXR-BR"]["status"], "NOT_EXERCISED")
        self.assertEqual(by_id["AXR-BR"]["evidence"]["packageIds"], [])

    def test_every_record_states_its_link_basis(self):
        for r in self.records:
            self.assertTrue(r["linkBasis"], r["ruleId"] + " must justify its classification")
            for line in r["linkBasis"]:
                self.assertIsInstance(line, str)

    def test_the_three_knowledge_bodies_stay_separate(self):
        r = self.by_id["AXR-BR"]
        self.assertIn("educator", r)
        self.assertIn("implementation", r)
        self.assertIn("evidence", r)
        self.assertEqual(r["implementation"]["lineageNote"], "CONVERGENT_NOT_DERIVED")


class TestMeasurableEvidence(unittest.TestCase):
    def test_outcomes_are_measured_from_packages_not_asserted(self):
        pkgs = [pkg("B_breakRetest", result="Loss", resultR=-1),
                pkg("B_breakRetest", packageId="PKG|x|2", result="Win", resultR=2, mfePips=40.0)]
        outcomes = J._resolved_outcomes(pkgs)
        b = outcomes["B_breakRetest"]
        self.assertEqual(b["trades"], 2)
        self.assertEqual(b["wins"], 1)
        self.assertEqual(b["losses"], 1)
        self.assertEqual(b["netR"], 1.0)
        self.assertEqual(b["winRate"], 50.0)
        self.assertEqual(b["expectancyR"], 0.5)
        self.assertEqual(b["meanMfePips"], 20.0)


class TestHypotheses(unittest.TestCase):
    def setUp(self):
        self.pkgs = [pkg("B_breakRetest"), pkg("A_repeatedReaction", packageId="PKG|x|2")]
        self.records, self.run_ids = build(self.pkgs)
        self.outcomes = J._resolved_outcomes(self.pkgs)
        self.hyps = J.build_hypotheses(self.records, self.outcomes, self.run_ids)
        self.by_rule = {h["ruleId"]: h for h in self.hyps}

    def test_every_rule_gets_a_hypothesis(self):
        self.assertEqual(len(self.hyps), len(self.records))

    def test_no_placeholder_text_survives(self):
        blob = json.dumps(self.hyps)
        for placeholder in ("compare outcomes", "compare results",
                            "Replay historical price action"):
            self.assertNotIn(placeholder, blob)

    def test_each_hypothesis_is_actually_testable(self):
        for h in self.hyps:
            if h["status"] == "NOT_APPLICABLE":
                continue
            self.assertIn(h["metricId"], J.METRIC_REGISTRY)
            self.assertTrue(h["comparison"]["armA"] and h["comparison"]["armB"])
            self.assertIsInstance(h["threshold"]["minimumDifference"], (int, float))
            self.assertEqual(h["minimumSamplePerArm"], J.MINIMUM_SAMPLE_PER_ARM)
            self.assertTrue(h["falsificationCondition"])
            self.assertIn("REFUTED", h["falsificationCondition"])

    def test_threshold_and_sample_are_declared_in_advance(self):
        for h in self.hyps:
            if h["status"] == "NOT_APPLICABLE":
                continue
            self.assertTrue(h["threshold"]["declaredInAdvance"])
            self.assertIn("Declared in advance", h["minimumSampleBasis"])

    def test_insufficient_sample_is_stated_not_hidden(self):
        h = self.by_rule["AXR-BR"]
        self.assertEqual(h["status"], "INSUFFICIENT_SAMPLE")
        self.assertGreater(h["shortfall"], 0, "the gap to the declared minimum must be stated")
        self.assertEqual(h["currentEvidence"]["resolvedTrades"], 1)

    def test_replay_evidence_can_never_promote_past_the_ceiling(self):
        for h in self.hyps:
            self.assertEqual(h["promotionCeiling"], "REPLAY_EVIDENCE_ONLY")

    def test_unimplemented_and_unsupported_rules_are_not_applicable(self):
        self.assertEqual(self.by_rule["AXR-MISSING"]["status"], "NOT_APPLICABLE")
        self.assertEqual(self.by_rule["AXR-MOGO"]["status"], "NOT_APPLICABLE")

    def test_live_only_rules_are_not_testable_by_replay(self):
        self.assertEqual(self.by_rule["AXR-LIVE"]["status"], "NOT_TESTABLE_BY_REPLAY")

    def test_status_vocabulary_is_closed(self):
        for h in self.hyps:
            self.assertIn(h["status"], J.HYPOTHESIS_STATUSES)

    def test_a_sufficient_sample_becomes_testable(self):
        many = [pkg("B_breakRetest", packageId="PKG|x|%d" % i,
                    result=("Win" if i % 2 else "Loss"), resultR=(2 if i % 2 else -1))
                for i in range(J.MINIMUM_SAMPLE_PER_ARM + 2)]
        records, run_ids = build(many)
        outcomes = J._resolved_outcomes(many)
        hyps = {h["ruleId"]: h for h in J.build_hypotheses(records, outcomes, run_ids)}
        self.assertEqual(hyps["AXR-BR"]["status"], "TESTABLE_NOW")
        self.assertEqual(hyps["AXR-BR"]["shortfall"], 0)


class TestMetricRegistry(unittest.TestCase):
    def test_every_metric_defines_itself_once_and_names_its_source(self):
        for mid, m in J.METRIC_REGISTRY.items():
            self.assertTrue(mid.startswith("MET_"))
            for key in ("name", "unit", "formula", "sourceFields", "betterWhen"):
                self.assertIn(key, m)
            self.assertTrue(m["sourceFields"], mid + " must name the package fields it reads")
            self.assertIn(m["betterWhen"], ("higher", "lower"))


class TestReadOnly(unittest.TestCase):
    def test_the_generator_never_writes_to_evidence(self):
        path = os.path.join(os.path.dirname(__file__), "..", "..", "scripts",
                            "strategy_fidelity", "build_alex_rule_evidence_join.py")
        with open(path, encoding="utf-8") as fh:
            src = fh.read()
        for forbidden in ("shutil.rmtree", "os.remove", "os.unlink"):
            self.assertNotIn(forbidden, src)
        body = src.split("def load_packages")[1].split("def ")[0]
        self.assertNotIn('"w"', body, "packages must only ever be opened for reading")

    def test_packages_are_not_mutated_by_the_join(self):
        pkgs = [pkg("B_breakRetest")]
        before = json.dumps(pkgs, sort_keys=True)
        build(pkgs)
        J._resolved_outcomes(pkgs)
        self.assertEqual(json.dumps(pkgs, sort_keys=True), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)

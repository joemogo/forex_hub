"""MOGO-002.6 Phase 11 — tests for the Knowledge Engineering system.

Fixtures are based on repository evidence. No speculative educator interpretation is
encoded as an expected truth: where a test asserts a claim's meaning, it asserts the
evidence store's own recorded value, not a reading invented here.
"""
import copy
import json
import os
import sys
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts", "knowledge_engineering"))

import ke_model as ke          # noqa: E402
import ke_inventory as kinv    # noqa: E402
import ke_analysis as kan      # noqa: E402
import build_ke_artifacts as kb  # noqa: E402


def _sm(rule_id="R1"):
    return [ke.rule_source_mapping(rule_id, "C1", "S1", "primary")]


class TestModelGuards(unittest.TestCase):

    def test_normalized_rule_requires_a_source_mapping(self):
        with self.assertRaises(ke.KEModelError):
            ke.normalized_rule("R", "v", "E", "s", "ENTRY", "EXPLICIT", True, True,
                               source_mappings=[])

    def test_unresolved_rule_cannot_be_deterministic(self):
        with self.assertRaises(ke.KEModelError):
            ke.normalized_rule("R", "v", "E", "s", "ENTRY", "UNRESOLVED", True, True,
                               source_mappings=_sm("R"))

    def test_discretionary_rule_cannot_be_deterministic(self):
        with self.assertRaises(ke.KEModelError):
            ke.normalized_rule("R", "v", "E", "s", "ENTRY", "DISCRETIONARY", False, True,
                               source_mappings=_sm("R"))

    def test_cannot_promote_to_approved_without_a_reference(self):
        """OD-1 modification 6, enforced as a hard error."""
        with self.assertRaises(ke.KEModelError):
            ke.normalized_rule("R", "v", "E", "s", "ENTRY", "EXPLICIT", True, True,
                               source_mappings=_sm("R"), approval_status="APPROVED")

    def test_cannot_exceed_normalized_maturity(self):
        for bad in ("IMPLEMENTED", "REPLAY_TESTED", "PAPER_VALIDATED", "PRODUCTION_READY"):
            with self.assertRaises(ke.KEModelError):
                ke.normalized_rule("R", "v", "E", "s", "ENTRY", "EXPLICIT", True, True,
                                   source_mappings=_sm("R"), maturity=bad)

    def test_draft_cannot_reuse_the_production_strategy_id(self):
        with self.assertRaises(ke.KEModelError):
            ke.strategy_specification_draft("alex_g_sr_v1", "v", "t", [], [], "n", "ALEX_G")

    def test_contradiction_requires_two_interpretations(self):
        with self.assertRaises(ke.KEModelError):
            ke.rule_contradiction("X", ["a", "b"], "i", "DIRECTIONAL", "material", "ENTRY",
                                  ["only one"])

    def test_claim_requires_provenance(self):
        with self.assertRaises(ke.KEModelError):
            ke.educator_claim("C", "E", [], "text", "para", "ENTRY", "ENTRY", "EXPLICIT", "LOW")

    def test_duplicate_group_needs_two_members(self):
        with self.assertRaises(ke.KEModelError):
            ke.duplicate_claim_group("G", ["one"], "c", "IDENTICAL", [], [], "MERGE", "LOW")

    def test_normalization_decision_requires_every_rationale(self):
        with self.assertRaises(ke.KEModelError):
            ke.normalization_decision("D", "R", ["C"], [], "d", "c", "", [], [], "LOW",
                                      "det", "req", "draft")

    def test_review_item_requires_smallest_decision_and_alternatives(self):
        with self.assertRaises(ke.KEModelError):
            ke.human_review_state("V", "i", [], [], None, "x", ["only one"], "r", "d", 1)
        with self.assertRaises(ke.KEModelError):
            ke.human_review_state("V", "i", [], [], None, "x", ["a", "b"], "r", "", 1)


class TestStableIdsAndSerialization(unittest.TestCase):

    def setUp(self):
        self.inv = kinv.build_inventory()

    def test_ids_are_stable_across_runs(self):
        g1 = kan.build_duplicate_groups(self.inv)
        g2 = kan.build_duplicate_groups(kinv.build_inventory())
        self.assertEqual([g["groupId"] for g in g1], [g["groupId"] for g in g2])

    def test_candidate_and_rule_ids_correspond(self):
        ev = kinv.load_evidence()
        g = kan.build_duplicate_groups(self.inv)
        x = kan.build_contradictions(self.inv, ev)
        c = kan.build_candidate_rules(self.inv, g, x)
        r, _, _ = kan.normalize(c, self.inv)
        for rule in r:
            self.assertTrue(rule["ruleId"].startswith("KERULE|"))
            self.assertIn(rule["ruleId"].replace("KERULE", "KECAND"),
                          [q["candidateRuleId"] for q in c])

    def test_serialization_round_trips(self):
        d = ke.strategy_specification_draft("x_draft", "v", "t", [], [], "n", "ALEX_G")
        self.assertEqual(json.loads(ke.dumps(d)), d)

    def test_serialization_is_deterministic(self):
        d = ke.strategy_specification_draft("x_draft", "v", "t", [], [], "n", "ALEX_G")
        self.assertEqual(ke.dumps(d), ke.dumps(copy.deepcopy(d)))


class TestInventoryAndProvenance(unittest.TestCase):

    def setUp(self):
        self.inv = kinv.build_inventory()

    def test_all_195_claims_are_inventoried(self):
        self.assertEqual(self.inv["claimCount"], 195)
        self.assertEqual(self.inv["sourceArtifactCount"], 8)

    def test_every_claim_keeps_a_source_reference(self):
        for c in self.inv["claims"]:
            self.assertTrue(c["sourceReferences"], c["claimId"])
            self.assertTrue(c["sourceReferences"][0]["sourceId"], c["claimId"])

    def test_source_text_and_paraphrase_are_separate_fields(self):
        """A paraphrase must never be presentable as a quotation."""
        withtext = [c for c in self.inv["claims"] if c["sourceText"]]
        self.assertGreater(len(withtext), 0)
        for c in withtext[:25]:
            self.assertIn("sourceText", c)
            self.assertIn("normalizedParaphrase", c)

    def test_inventory_does_not_mutate_the_evidence_store(self):
        before = kinv.load_evidence()
        snap = json.dumps({k: sorted(v) for k, v in
                           {kk: list(vv) for kk, vv in before.items()}.items()}, sort_keys=True)
        kinv.build_inventory()
        after = kinv.load_evidence()
        snap2 = json.dumps({k: sorted(v) for k, v in
                            {kk: list(vv) for kk, vv in after.items()}.items()}, sort_keys=True)
        self.assertEqual(snap, snap2)

    def test_classification_records_its_derivation(self):
        for cl in self.inv["classifications"]:
            self.assertTrue(cl["derivedFrom"], cl["claimId"])
            self.assertTrue(any(d.startswith("claimType=") for d in cl["derivedFrom"]))
            self.assertTrue(cl["rationale"])

    def test_every_claim_states_why_it_was_or_was_not_promoted(self):
        for cl in self.inv["classifications"]:
            if cl["candidateRuleEligible"]:
                self.assertIn("eligible", cl["rationale"].lower())
            else:
                self.assertIn("not promoted", cl["rationale"].lower())

    def test_marketing_and_psychology_are_never_rule_eligible(self):
        by_id = {c["claimId"]: c for c in self.inv["claims"]}
        for cl in self.inv["classifications"]:
            if by_id[cl["claimId"]]["classification"] in ("MARKETING", "PSYCHOLOGY", "OPINION"):
                self.assertFalse(cl["candidateRuleEligible"], cl["claimId"])

    def test_blocking_questions_downgrade_explicitness(self):
        """A rule stated plainly but missing its parameter is UNRESOLVED, not EXPLICIT."""
        unresolved = [c for c in self.inv["claims"] if c["explicitness"] == "UNRESOLVED"]
        self.assertGreater(len(unresolved), 0)
        for c in unresolved[:10]:
            self.assertTrue(c["notes"] and "blocking" in c["notes"])

    def test_missing_library_raises_stop_condition(self):
        saved = kinv.EVIDENCE
        try:
            kinv.EVIDENCE = os.path.join(REPO_ROOT, "no_such_dir")
            with self.assertRaises(kinv.InventoryError):
                kinv.load_evidence()
        finally:
            kinv.EVIDENCE = saved


class TestDuplicateGrouping(unittest.TestCase):

    def setUp(self):
        self.inv = kinv.build_inventory()
        self.groups = kan.build_duplicate_groups(self.inv)

    def test_groups_have_at_least_two_members(self):
        for g in self.groups:
            self.assertGreaterEqual(len(g["memberClaimIds"]), 2)

    def test_blocked_groups_are_never_recommended_for_merge(self):
        for g in self.groups:
            if g["blockingReasons"]:
                self.assertEqual(g["mergeRecommendation"], "DO_NOT_MERGE", g["groupId"])

    def test_differing_thresholds_block_a_merge(self):
        a = ke.educator_claim("A", "E", [ke.source_reference("S")], "t",
                              "risk 1% of the account", "RISK", "RISK", "EXPLICIT", "LOW",
                              origin_claim_type="risk_rule")
        b = ke.educator_claim("B", "E", [ke.source_reference("S")], "t",
                              "risk 5% of the account", "RISK", "RISK", "EXPLICIT", "LOW",
                              origin_claim_type="risk_rule")
        self.assertTrue(any("thresholds differ" in x for x in kan._merge_blockers(a, b)))

    def test_mandatory_and_optional_never_merge(self):
        a = ke.educator_claim("A", "E", [ke.source_reference("S")], "t", "always do this",
                              "ENTRY", "ENTRY", "EXPLICIT", "LOW", origin_claim_type="entry_rule")
        b = ke.educator_claim("B", "E", [ke.source_reference("S")], "t", "always do this",
                              "ENTRY", "ENTRY", "DISCRETIONARY", "LOW", origin_claim_type="exception")
        self.assertTrue(any("mandatory" in x for x in kan._merge_blockers(a, b)))

    def test_entry_and_management_never_merge(self):
        a = ke.educator_claim("A", "E", [ke.source_reference("S")], "t", "same words",
                              "ENTRY", "ENTRY", "EXPLICIT", "LOW", origin_claim_type="entry_rule")
        b = ke.educator_claim("B", "E", [ke.source_reference("S")], "t", "same words",
                              "ENTRY", "ENTRY", "EXPLICIT", "LOW",
                              origin_claim_type="trade_management_rule")
        self.assertTrue(any("entry and trade-management" in x for x in kan._merge_blockers(a, b)))

    def test_merged_groups_preserve_all_source_references(self):
        claims = {c["claimId"]: c for c in self.inv["claims"]}
        for g in self.groups:
            srcs = {r["sourceId"] for m in g["memberClaimIds"]
                    for r in claims[m]["sourceReferences"]}
            self.assertTrue(set(g["sourceChronology"]).issubset(srcs) or g["sourceChronology"])


class TestContradictions(unittest.TestCase):

    def setUp(self):
        self.inv = kinv.build_inventory()
        self.x = kan.build_contradictions(self.inv, kinv.load_evidence())

    def test_contradictions_are_imported_with_their_origin(self):
        self.assertGreater(len(self.x), 0)
        for c in self.x:
            self.assertTrue(c["originRecord"].startswith("XCONTRA|"))

    def test_every_contradiction_offers_alternatives_and_stays_open(self):
        for c in self.x:
            self.assertGreaterEqual(len(c["possibleInterpretations"]), 2)
            self.assertEqual(c["resolutionStatus"], "OPEN")
            self.assertTrue(c["recommendedCompletionPath"])

    def test_the_blocking_contradiction_is_carried_through(self):
        self.assertTrue(any(c["severity"] == "blocking" for c in self.x))


class TestNormalization(unittest.TestCase):

    def setUp(self):
        self.inv = kinv.build_inventory()
        ev = kinv.load_evidence()
        g = kan.build_duplicate_groups(self.inv)
        x = kan.build_contradictions(self.inv, ev)
        self.cands = kan.build_candidate_rules(self.inv, g, x)
        self.rules, self.decisions, self.deferred = kan.normalize(self.cands, self.inv)

    def test_every_rule_has_a_normalization_decision(self):
        self.assertEqual(len(self.rules), len(self.decisions))
        ids = {d["ruleId"] for d in self.decisions}
        for r in self.rules:
            self.assertIn(r["ruleId"], ids)

    def test_no_rule_exceeds_needs_review(self):
        for r in self.rules:
            self.assertEqual(r["approvalStatus"], "NEEDS_REVIEW", r["ruleId"])
            self.assertEqual(r["maturity"], "NORMALIZED", r["ruleId"])

    def test_unresolved_parameters_are_preserved_not_filled(self):
        withunres = [r for r in self.rules if r["unresolvedElements"]]
        self.assertGreater(len(withunres), 0)
        for r in withunres:
            self.assertFalse(r["deterministic"], r["ruleId"])

    def test_every_rule_maps_back_to_a_claim_and_a_source(self):
        for r in self.rules:
            self.assertTrue(r["sourceMappings"], r["ruleId"])
            for m in r["sourceMappings"]:
                self.assertTrue(m["claimId"])
                self.assertTrue(m["sourceId"])

    def test_decisions_state_assumptions_avoided(self):
        for d in self.decisions:
            self.assertTrue(d["assumptionsAvoided"])
            self.assertTrue(d["determinismRationale"])
            self.assertTrue(d["draftRationale"])

    def test_deferred_candidates_are_recorded_with_a_reason(self):
        for d in self.deferred:
            self.assertTrue(d["reason"])

    def test_canonical_statement_is_the_stores_own_wording(self):
        """Normalization must not re-author the claim text."""
        claims = {c["claimId"]: c for c in self.inv["claims"]}
        for r in self.rules[:30]:
            origin = r["sourceMappings"][0]["claimId"]
            self.assertEqual(r["canonicalStatement"], claims[origin]["normalizedParaphrase"])


class TestDraftSpecification(unittest.TestCase):

    def setUp(self):
        self.ctx = kb.generate_all()

    def test_draft_is_separate_from_production(self):
        self.assertNotEqual(self.ctx["draft"]["strategyId"], "alex_g_sr_v1")
        self.assertEqual(self.ctx["draft"]["strategyId"], "alex_g_educator_v2_draft")

    def test_draft_carries_every_required_status_flag(self):
        f = self.ctx["draft"]["statusFlags"]
        for k in ("NOT_PRODUCTION", "NOT_IMPLEMENTED", "NOT_REPLAY_VALIDATED",
                  "NOT_PAPER_VALIDATED", "PROFITABILITY_UNVALIDATED",
                  "ENGINEERING_AUTHORITY_APPROVAL_REQUIRED"):
            self.assertTrue(f[k], k)

    def test_draft_references_rules_rather_than_copying_them(self):
        for ref in self.ctx["draft"]["ruleReferences"]:
            self.assertEqual(sorted(ref.keys()), ["domain", "ruleId", "version"])

    def test_every_domain_is_reported_even_when_empty(self):
        domains = [d["domain"] for d in self.ctx["draft"]["domainReports"]]
        self.assertEqual(domains, ke.STRATEGY_DOMAINS)

    def test_exit_domain_is_honestly_reported_as_empty(self):
        exit_report = [d for d in self.ctx["draft"]["domainReports"] if d["domain"] == "EXIT"][0]
        self.assertEqual(exit_report["normalizedRules"], 0)
        self.assertEqual(exit_report["coverageLevel"], "NONE")

    def test_production_specification_is_untouched(self):
        import alex_specification as aspec
        spec = aspec.build_specification()
        self.assertEqual(spec["strategyId"], "alex_g_sr_v1")
        self.assertEqual(spec["ruleCount"], 13)

    def test_report_generation_is_deterministic(self):
        again = kb.generate_all()
        self.assertEqual(ke.dumps(self.ctx["draft"]), ke.dumps(again["draft"]))
        self.assertEqual(ke.dumps(self.ctx["coverage"]), ke.dumps(again["coverage"]))

    def test_coverage_uses_numerator_and_denominator(self):
        t = self.ctx["coverage"]["totals"]
        self.assertIn("n", t["candidateRuleEligibleClaims"])
        self.assertIn("of", t["candidateRuleEligibleClaims"])
        self.assertEqual(t["approvedRules"]["n"], 0)

    def test_review_queue_prioritises_trade_gating_items(self):
        q = self.ctx["queue"]
        self.assertGreater(len(q), 0)
        self.assertLessEqual(q[0]["priorityRank"], 3)
        for item in q:
            self.assertTrue(item["smallestDecisionRequired"])
            self.assertGreaterEqual(len(item["availableInterpretations"]), 2)

    def test_delta_declares_neither_specification_correct(self):
        self.assertIn("Neither specification is declared correct", self.ctx["delta"]["note"])

    def test_delta_reports_the_unclosed_risk_gap(self):
        self.assertEqual(self.ctx["delta"]["riskGap"]["draftStopPlacementRules"], 0)
        self.assertIn("NOT closed", self.ctx["delta"]["riskGap"]["finding"])


class TestProductionPromotionPrevention(unittest.TestCase):
    """The milestone's hardest constraint: nothing here may reach production."""

    def test_no_draft_artifact_is_written_into_the_evidence_store(self):
        import glob
        before = set(glob.glob(os.path.join(kinv.EVIDENCE, "**", "*.json"), recursive=True))
        kb.generate_all()
        after = set(glob.glob(os.path.join(kinv.EVIDENCE, "**", "*.json"), recursive=True))
        self.assertEqual(before, after, "the KE system must never write into evidence/")

    def test_no_rule_candidate_proposal_is_created(self):
        """Writing into evidence/proposals/ would make the dashboard report movement
        that has not happened."""
        import glob
        self.assertEqual(
            len(glob.glob(os.path.join(kinv.EVIDENCE, "proposals", "*.json"))), 0)

    def test_a_raw_claim_cannot_become_a_rule_without_passing_classification(self):
        inv = kinv.build_inventory()
        elig = {c["claimId"] for c in inv["classifications"] if c["candidateRuleEligible"]}
        ev = kinv.load_evidence()
        g = kan.build_duplicate_groups(inv)
        x = kan.build_contradictions(inv, ev)
        cands = kan.build_candidate_rules(inv, g, x)
        for c in cands:
            for cid in c["originatingClaimIds"]:
                self.assertIn(cid, elig,
                              "candidate %s originates from an ineligible claim" % c["candidateRuleId"])


class TestBackwardCompatibility(unittest.TestCase):

    def test_unknown_future_fields_survive_a_round_trip(self):
        d = ke.strategy_specification_draft("x_draft", "v", "t", [], [], "n", "ALEX_G")
        d["futureField"] = {"added": "later"}
        self.assertEqual(ke.loads(ke.dumps(d))["futureField"], {"added": "later"})

    def test_model_version_is_stamped(self):
        d = ke.strategy_specification_draft("x_draft", "v", "t", [], [], "n", "ALEX_G")
        self.assertEqual(d["modelVersion"], ke.KE_MODEL_VERSION)

    def test_existing_evidence_vocabularies_are_reused_not_redefined(self):
        self.assertEqual(ke.CONTRADICTION_TYPES, list(ke.evc.CONTRADICTION_TYPES))
        self.assertEqual(ke.CONTRADICTION_SEVERITIES, list(ke.evc.CONTRADICTION_SEVERITIES))


if __name__ == "__main__":
    unittest.main(verbosity=2)

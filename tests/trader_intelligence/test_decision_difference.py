#!/usr/bin/env python3
"""MOGO-022 -- decision-difference classification.

The properties under test:

  * IT CLASSIFIES, IT DOES NOT ADJUDICATE OR PROMOTE. No contradiction is
    resolved, no claim status changed, no rule proposed. `promotionStatus` is
    NOT_A_TRADING_RULE on every record the module can emit.
  * IT FAILS CLOSED. A position that cannot be walked back to a verbatim excerpt
    attributable to its actor yields INSUFFICIENT_EVIDENCE and nothing else --
    and that test dominates every downstream signal.
  * EVERY GATE IS LOAD-BEARING. Each of the six classifications has a positive
    control, and each conservative gate is mutation-tested: perturbing exactly
    the input the gate reads must flip the verdict. A gate that cannot be made
    to fire is not evidence of anything.
  * THE SPECIMEN IS REAL. The liquidity-sweep disagreement between TJR and
    Alex G is classified from the live corpus, with cited evidence ids, and the
    verdict is pinned.
  * IT READS. Running the classifier leaves the corpus byte-identical.
"""

import copy
import hashlib
import glob
import json
import os
import sys
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts", "trader_intelligence"))

import decision_difference as dd                   # noqa: E402
import research_understanding as ru                # noqa: E402
from query_evidence import EvidenceIndex           # noqa: E402

# The worked specimen: TJR builds his setup on liquidity sweeps; Alex G says no
# consistent strategy can be built on them.
SPECIMEN = "XCONTRA|20260728|001"
TJR_CLAIM = "CLAIM|TJR|20260727|006"
ALEX_CLAIM = "CLAIM|ALEX_G|20260728|025"
TJR_EVIDENCE = "EV|EVSRC|TJR|20260727|001|008"
ALEX_EVIDENCE = "EV|EVSRC|ALEX_G|20260728|002|013"


def index():
    return EvidenceIndex.load(dd.EVIDENCE_ROOT)


def position(side="A", actor="X", claim_type="entry_rule", scope=None,
             gaps=(), directness_class=ru.SOURCE_SAID):
    """A synthetic position. Built by hand so a gate can be exercised in
    isolation, never loaded from the corpus."""
    full_scope = {name: None for name in dd.SCOPE_DIMENSIONS}
    full_scope.update(scope or {})
    return {
        "side": side,
        "claimId": "CLAIM|%s|20260101|001" % (actor,),
        "actorId": actor,
        "claimType": claim_type,
        "isRuleCategory": claim_type in ru.RULE_CATEGORIES,
        "normalizedClaim": "synthetic",
        "claimStatus": "pending_review",
        "decisionScope": full_scope,
        "statedDimensions": sorted(k for k, v in full_scope.items() if v is not None),
        "evidence": [{"evidenceId": "EV|%s" % actor, "directnessClass": directness_class}],
        "evidenceIds": ["EV|%s" % actor],
        "sourceIds": ["EVSRC|%s" % actor],
        "provenanceComplete": not gaps,
        "provenanceGaps": sorted(gaps),
    }


class SpecimenCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.idx = index()
        cls.result = dd.decision_difference(cls.idx, SPECIMEN)


# ---------------------------------------------------------------- the specimen

class TestTheLiquiditySweepSpecimen(SpecimenCase):

    def test_it_classifies_as_an_interpretation_hypothesis(self):
        self.assertEqual(self.result["classification"], dd.INTERPRETATION_HYPOTHESIS)
        self.assertTrue(self.result["reconciliationIsMogoReading"])

    def test_both_sides_are_provenance_complete(self):
        self.assertTrue(self.result["provenanceComplete"])
        self.assertEqual(self.result["positionA"]["provenanceGaps"], [])
        self.assertEqual(self.result["positionB"]["provenanceGaps"], [])

    def test_it_cites_the_real_claim_and_evidence_ids(self):
        self.assertEqual(self.result["citedClaimIds"], sorted([ALEX_CLAIM, TJR_CLAIM]))
        self.assertEqual(self.result["citedEvidenceIds"],
                         sorted([ALEX_EVIDENCE, TJR_EVIDENCE]))
        self.assertEqual(self.result["citedSourceIds"],
                         ["EVSRC|ALEX_G|20260728|002", "EVSRC|TJR|20260727|001"])

    def test_each_side_carries_the_verbatim_excerpt_it_rests_on(self):
        excerpts = [e["exactExcerpt"]
                    for key in ("positionA", "positionB")
                    for e in self.result[key]["evidence"]]
        self.assertIn("My strategy is based off of liquidity sweeps.", excerpts)
        self.assertIn("There's no way that you can have a specific strategy to "
                      "trade solely off of these sweeps.", excerpts)

    def test_the_verdict_rests_on_neither_actor_stating_a_scope(self):
        # The REASON it is a hypothesis, pinned: both sides are rule-bearing and
        # would otherwise be a RULE_DIFFERENCE. Nothing stated separates them.
        self.assertTrue(self.result["positionA"]["isRuleCategory"])
        self.assertTrue(self.result["positionB"]["isRuleCategory"])
        self.assertEqual(self.result["positionA"]["statedDimensions"], [])
        self.assertEqual(self.result["positionB"]["statedDimensions"], [])

    def test_the_source_contradiction_is_quoted_not_replaced(self):
        source = self.idx.contradictions[SPECIMEN]
        derived = self.result["derivedFrom"]
        self.assertEqual(derived["contradictionType"], source["contradictionType"])
        self.assertEqual(derived["severity"], source["severity"])
        self.assertEqual(derived["status"], source["status"])
        self.assertEqual(derived["recordedRationale"], source["rationale"])

    def test_the_id_is_derived_from_the_contradiction_it_explains(self):
        self.assertEqual(self.result["decisionDifferenceId"], "XDD|20260728|001")


# ------------------------------------------------------- one control per class

class TestEveryClassificationHasAPositiveControl(unittest.TestCase):

    def test_insufficient_evidence(self):
        verdict, _ = dd.classify(position("A", "H", gaps=["NO_SUPPORTING_EVIDENCE"]),
                                 position("B", "M"))
        self.assertEqual(verdict, dd.INSUFFICIENT_EVIDENCE)

    def test_data_difference(self):
        verdict, _ = dd.classify(position("A", "H", scope={"marketSymbol": "EURUSD"}),
                                 position("B", "M", scope={"marketSymbol": "GBPUSD"}))
        self.assertEqual(verdict, dd.DATA_DIFFERENCE)

    def test_timing_difference_from_stated_dimensions(self):
        verdict, _ = dd.classify(position("A", "H", scope={"session": "london"}),
                                 position("B", "M", scope={"session": "newyork"}))
        self.assertEqual(verdict, dd.TIMING_DIFFERENCE)

    def test_timing_difference_from_the_recorded_contradiction_type(self):
        verdict, _ = dd.classify(position("A", "H"), position("B", "M"),
                                 contradiction_type="TEMPORAL_DRIFT")
        self.assertEqual(verdict, dd.TIMING_DIFFERENCE)

    def test_implementation_difference(self):
        verdict, _ = dd.classify(position("A", "H", claim_type="stop_rule"),
                                 position("B", "M", claim_type="stop_rule"),
                                 contradiction_type="NUMERIC_THRESHOLD")
        self.assertEqual(verdict, dd.IMPLEMENTATION_DIFFERENCE)

    def test_rule_difference(self):
        verdict, _ = dd.classify(
            position("A", "H", claim_type="entry_rule", scope={"timeframe": "M15"}),
            position("B", "M", claim_type="stop_rule", scope={"timeframe": "M15"}))
        self.assertEqual(verdict, dd.RULE_DIFFERENCE)

    def test_interpretation_hypothesis(self):
        verdict, _ = dd.classify(position("A", "H"), position("B", "M"))
        self.assertEqual(verdict, dd.INTERPRETATION_HYPOTHESIS)

    def test_every_declared_classification_was_exercised(self):
        exercised = {
            dd.INSUFFICIENT_EVIDENCE, dd.DATA_DIFFERENCE, dd.TIMING_DIFFERENCE,
            dd.IMPLEMENTATION_DIFFERENCE, dd.RULE_DIFFERENCE,
            dd.INTERPRETATION_HYPOTHESIS,
        }
        self.assertEqual(exercised, set(dd.CLASSIFICATIONS))
        self.assertEqual(set(dd.CLASSIFICATION_MEANING), set(dd.CLASSIFICATIONS))


# ----------------------------------------------------- the gates are load-bearing

class TestGatesAreLoadBearing(unittest.TestCase):
    """Mutation controls. Each perturbs exactly the input one gate reads; if the
    verdict does not move, that gate is decorative."""

    def test_removing_the_scope_flips_rule_difference_to_hypothesis(self):
        a = position("A", "H", claim_type="entry_rule", scope={"timeframe": "M15"})
        b = position("B", "M", claim_type="stop_rule", scope={"timeframe": "M15"})
        self.assertEqual(dd.classify(a, b)[0], dd.RULE_DIFFERENCE)
        stripped_a, stripped_b = copy.deepcopy(a), copy.deepcopy(b)
        for side in (stripped_a, stripped_b):
            side["decisionScope"]["timeframe"] = None
            side["statedDimensions"] = []
        self.assertEqual(dd.classify(stripped_a, stripped_b)[0],
                         dd.INTERPRETATION_HYPOTHESIS)

    def test_adding_a_stated_scope_flips_the_real_specimen(self):
        # The specimen's verdict is caused by the ABSENCE of stated scope, not by
        # a hardcoded answer: state a shared timeframe and it becomes a rule
        # difference. Operates on copies -- the corpus is never touched.
        idx = index()
        a = copy.deepcopy(dd.build_position(idx, ALEX_CLAIM, "A"))
        b = copy.deepcopy(dd.build_position(idx, TJR_CLAIM, "B"))
        self.assertEqual(dd.classify(a, b, "DIRECTIONAL")[0],
                         dd.INTERPRETATION_HYPOTHESIS)
        for side in (a, b):
            side["decisionScope"]["timeframe"] = "M5"
            side["statedDimensions"] = ["timeframe"]
        self.assertEqual(dd.classify(a, b, "DIRECTIONAL")[0], dd.RULE_DIFFERENCE)

    def test_a_non_rule_claim_type_blocks_implementation_difference(self):
        rule = dd.classify(position("A", "H", claim_type="stop_rule"),
                           position("B", "M", claim_type="stop_rule"),
                           contradiction_type="NUMERIC_THRESHOLD")[0]
        self.assertEqual(rule, dd.IMPLEMENTATION_DIFFERENCE)
        non_rule = dd.classify(position("A", "H", claim_type="performance_hypothesis"),
                               position("B", "M", claim_type="performance_hypothesis"),
                               contradiction_type="NUMERIC_THRESHOLD")[0]
        self.assertEqual(non_rule, dd.INTERPRETATION_HYPOTHESIS)

    def test_a_dimension_only_one_side_states_proves_nothing(self):
        # A half-stated dimension is not a demonstrated difference.
        verdict, _ = dd.classify(position("A", "H", scope={"marketSymbol": "EURUSD"}),
                                 position("B", "M"))
        self.assertEqual(verdict, dd.INTERPRETATION_HYPOTHESIS)

    def test_insufficient_evidence_dominates_a_data_difference(self):
        # Fail-closed ordering: a broken chain is reported even when a downstream
        # gate would otherwise have produced a confident-looking answer.
        verdict, basis = dd.classify(
            position("A", "H", scope={"marketSymbol": "EURUSD"},
                     gaps=["NO_VERBATIM_EXCERPT|EV|H"]),
            position("B", "M", scope={"marketSymbol": "GBPUSD"}))
        self.assertEqual(verdict, dd.INSUFFICIENT_EVIDENCE)
        self.assertEqual([step["test"] for step in basis],
                         ["PROVENANCE_COMPLETE_BOTH_SIDES"])

    def test_mogo_inferred_only_evidence_is_not_the_actors_position(self):
        gaps = dd.build_position(index(), TJR_CLAIM, "A")["provenanceGaps"]
        self.assertEqual(gaps, [])
        synthetic = position("A", "H", directness_class=ru.MOGO_INFERRED)
        # build_position is what applies the rule; assert it directly.
        self.assertEqual(synthetic["evidence"][0]["directnessClass"], ru.MOGO_INFERRED)
        self.assertNotIn(ru.MOGO_INFERRED, dd._ATTRIBUTABLE)

    def test_a_missing_claim_is_a_provenance_gap_not_a_crash(self):
        built = dd.build_position(index(), "CLAIM|NOBODY|20260101|999", "A")
        self.assertEqual(built["provenanceGaps"], ["CLAIM_NOT_IN_CORPUS"])
        self.assertFalse(built["provenanceComplete"])
        self.assertEqual(dd.classify(built, position("B", "M"))[0],
                         dd.INSUFFICIENT_EVIDENCE)


# -------------------------------------------------------------- basis integrity

class TestTheBasisIsAnAudit(unittest.TestCase):

    def test_exactly_one_test_fires_and_it_is_the_last_one(self):
        for a, b, kind in (
                (position("A", "H", gaps=["NO_SUPPORTING_EVIDENCE"]), position("B", "M"), None),
                (position("A", "H", scope={"marketSymbol": "EURUSD"}),
                 position("B", "M", scope={"marketSymbol": "GBPUSD"}), None),
                (position("A", "H"), position("B", "M"), "TEMPORAL_DRIFT"),
                (position("A", "H", claim_type="stop_rule"),
                 position("B", "M", claim_type="stop_rule"), "NUMERIC_THRESHOLD"),
                (position("A", "H", claim_type="entry_rule", scope={"timeframe": "M15"}),
                 position("B", "M", claim_type="stop_rule", scope={"timeframe": "M15"}), None),
                (position("A", "H"), position("B", "M"), None)):
            _, basis = dd.classify(a, b, kind)
            fired = [step for step in basis if step["fired"]]
            self.assertEqual(len(fired), 1, basis)
            self.assertIs(fired[0], basis[-1])

    def test_every_basis_step_records_what_it_looked_at(self):
        _, basis = dd.classify(position("A", "H"), position("B", "M"))
        for step in basis:
            self.assertTrue(step["detail"])
            self.assertIsInstance(step["fired"], bool)


# ------------------------------------------------------ governance and read-only

class TestItPromotesNothing(SpecimenCase):

    def test_every_record_is_pinned_to_the_research_lane(self):
        for record in dd.decision_differences(self.idx):
            self.assertEqual(record["lane"], "RESEARCH")
            self.assertEqual(record["promotionStatus"], "NOT_A_TRADING_RULE")
            self.assertTrue(record["adjudicatesNothing"])
            self.assertTrue(record["changesNoStrategyRule"])

    def test_no_record_carries_a_resolution_or_a_status_change(self):
        blob = json.dumps(dd.decision_differences(self.idx), sort_keys=True)
        for forbidden in ("resolved_by_owner", "\"resolution\"", "reviewedAt",
                          "approved", "promote"):
            self.assertNotIn(forbidden, blob)

    def test_the_source_contradiction_is_still_open(self):
        self.assertEqual(self.idx.contradictions[SPECIMEN]["status"], "open")
        self.assertIsNone(self.idx.contradictions[SPECIMEN]["resolution"])

    def test_the_module_writes_no_evidence_record(self):
        with open(dd.__file__, "r", encoding="utf-8") as handle:
            source = handle.read()
        for writer in ("register_evidence_item", "link_evidence_to_claim",
                       "register_claim", "lifecycle", "create_proposal"):
            self.assertNotIn(writer, source)


class TestItIsAReadOnlyDerivation(SpecimenCase):

    def _corpus_digest(self):
        digest = hashlib.sha256()
        for path in sorted(glob.glob(os.path.join(dd.EVIDENCE_ROOT, "*", "*.json"))):
            if os.sep + "reports" + os.sep in path:
                continue          # derived output lives here by design
            digest.update(path.encode("utf-8"))
            with open(path, "rb") as handle:
                digest.update(handle.read())
        return digest.hexdigest()

    def test_classifying_every_contradiction_changes_no_byte(self):
        before = self._corpus_digest()
        dd.decision_differences(index())
        self.assertEqual(self._corpus_digest(), before)

    def test_two_runs_are_byte_identical(self):
        a = json.dumps(dd.decision_differences(index()), sort_keys=True)
        b = json.dumps(dd.decision_differences(index()), sort_keys=True)
        self.assertEqual(a, b)

    def test_every_recorded_contradiction_is_classifiable(self):
        records = dd.decision_differences(self.idx)
        self.assertEqual(len(records), len(self.idx.contradictions))
        for record in records:
            self.assertIn(record["classification"], dd.CLASSIFICATIONS)

    def test_an_unknown_contradiction_is_refused_not_guessed(self):
        with self.assertRaises(dd.DecisionDifferenceRefused):
            dd.decision_difference(self.idx, "XCONTRA|19700101|999")


class TestTheWorkedRecordOnDisk(SpecimenCase):
    """The committed artifact must still equal what the code derives today."""

    PATH = os.path.join(dd.EVIDENCE_ROOT, "reports",
                        "decision-difference-XCONTRA_20260728_001.json")

    def test_the_artifact_matches_a_fresh_derivation(self):
        with open(self.PATH, "r", encoding="utf-8") as handle:
            stored = json.load(handle)
        self.assertEqual(stored, self.result)

    def test_it_lives_under_reports_not_among_primary_records(self):
        self.assertTrue(os.path.basename(os.path.dirname(self.PATH)) == "reports")


if __name__ == "__main__":
    unittest.main()

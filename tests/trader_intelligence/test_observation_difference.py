#!/usr/bin/env python3
"""Human-vs-MOGO decision differences, from TradeObservation records (MOGO-022).

The properties under test:

  * IT FAILS CLOSED. An unknown or inferred reading of anything that feeds the
    comparison yields INSUFFICIENT_EVIDENCE, never a cause.
  * IT REUSES THE AUDITED PROCEDURE. Observations feed the same classify() the
    claim path uses, so there is one taxonomy and one authoritative verdict.
  * IT CANNOT CLAIM A RULE DIFFERENCE. Two trades differing is a hypothesis about
    the rules, not evidence of them. RULE_DIFFERENCE and IMPLEMENTATION_DIFFERENCE
    are structurally unreachable here, and that ceiling is asserted, not assumed.
  * IT ADJUDICATES NOTHING and writes nothing.

Refusal tests are paired with positive controls: a guard that refuses everything
is indistinguishable from a working one unless the accepting case is also pinned.
"""

import glob
import hashlib
import os
import sys
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts", "trader_intelligence"))

import decision_difference as dd    # noqa: E402
import trade_observation as to      # noqa: E402


def human(**overrides):
    record = {
        "observationId": "TOBS|HUMAN|20260817|001",
        "actor": "HUMAN",
        "sourceId": "EVSRC|TJR|20260817|001",
        "instrument": "EUR/USD",
        "timeframe": "H1",
        "direction": "long",
        "strategyId": "tjr_manual",
        "fieldClassification": {
            "instrument": "DIRECTLY_OBSERVED",
            "timeframe": "DIRECTLY_OBSERVED",
            "direction": "DIRECTLY_OBSERVED",
        },
        "unknowns": [],
        "extractedBy": "operator:joe",
        "lane": "RESEARCH",
        "schemaVersion": to.SCHEMA_VERSION,
        "createdAt": "2026-08-17T12:00:00Z",
    }
    record.update(overrides)
    return record


def mogo(**overrides):
    record = human()
    record.update({
        "observationId": "TOBS|MOGO|20260817|001",
        "actor": "MOGO",
        "sourceId": "EVSRC|MOGO|20260817|001",
        "strategyId": "alex_g_sr_v1",
        "extractedBy": "mogo:paper-engine",
    })
    record.update(overrides)
    return record


class TestTheBaselinePairIsActuallyComparable(unittest.TestCase):
    """If the baseline were provenance-incomplete, every test below would read
    INSUFFICIENT_EVIDENCE and prove nothing about the procedure."""

    def test_both_baseline_sides_are_provenance_complete(self):
        a = dd.build_position_from_observation(human(), "HUMAN")
        b = dd.build_position_from_observation(mogo(), "MOGO")
        self.assertEqual(a["provenanceGaps"], [])
        self.assertEqual(b["provenanceGaps"], [])
        self.assertTrue(a["provenanceComplete"])
        self.assertTrue(b["provenanceComplete"])


class TestItFailsClosed(unittest.TestCase):

    def test_an_unknown_scope_field_yields_insufficient_evidence(self):
        blind = human(timeframe=None, unknowns=["timeframe"])
        del blind["fieldClassification"]["timeframe"]
        result = dd.observation_difference(blind, mogo())
        self.assertEqual(result["classification"], dd.INSUFFICIENT_EVIDENCE)

    def test_an_inferred_scope_field_yields_insufficient_evidence(self):
        """An inference is the EXTRACTOR's reading, not the actor's action."""
        guessed = human()
        guessed["fieldClassification"]["direction"] = "INFERRED"
        guessed["inferenceReasons"] = {"direction": "arrow colour"}
        result = dd.observation_difference(guessed, mogo())
        self.assertEqual(result["classification"], dd.INSUFFICIENT_EVIDENCE)
        gaps = result["positions"][0]["provenanceGaps"]
        self.assertIn("FIELD_INFERRED|direction", gaps)

    def test_a_missing_required_field_yields_insufficient_evidence(self):
        result = dd.observation_difference(human(instrument=None), mogo())
        self.assertEqual(result["classification"], dd.INSUFFICIENT_EVIDENCE)

    def test_a_missing_source_yields_insufficient_evidence(self):
        result = dd.observation_difference(human(sourceId=""), mogo())
        self.assertEqual(result["classification"], dd.INSUFFICIENT_EVIDENCE)
        self.assertIn("NO_SOURCE_ID", result["positions"][0]["provenanceGaps"])

    def test_an_absent_side_yields_insufficient_evidence(self):
        result = dd.observation_difference(None, mogo())
        self.assertEqual(result["classification"], dd.INSUFFICIENT_EVIDENCE)
        self.assertIn("OBSERVATION_NOT_IN_CORPUS",
                      result["positions"][0]["provenanceGaps"])

    def test_positive_control_a_complete_pair_is_NOT_insufficient(self):
        """Without this, every test above would pass against a function that
        returned INSUFFICIENT_EVIDENCE unconditionally."""
        result = dd.observation_difference(human(), mogo())
        self.assertNotEqual(result["classification"], dd.INSUFFICIENT_EVIDENCE)


class TestTheClassification(unittest.TestCase):

    def test_a_different_instrument_is_a_data_difference(self):
        result = dd.observation_difference(human(), mogo(instrument="GBP/USD"))
        self.assertEqual(result["classification"], dd.DATA_DIFFERENCE)

    def test_a_different_timeframe_is_a_timing_difference(self):
        result = dd.observation_difference(human(), mogo(timeframe="H4"))
        self.assertEqual(result["classification"], dd.TIMING_DIFFERENCE)

    def test_data_beats_timing_when_both_differ(self):
        """Two deciders looking at different inputs are not disagreeing about
        timing -- the ordering is load-bearing, so it is pinned."""
        result = dd.observation_difference(
            human(), mogo(instrument="GBP/USD", timeframe="H4"))
        self.assertEqual(result["classification"], dd.DATA_DIFFERENCE)

    def test_same_scope_different_behaviour_is_only_a_hypothesis(self):
        result = dd.observation_difference(human(), mogo())
        self.assertEqual(result["classification"], dd.INTERPRETATION_HYPOTHESIS)


class TestItCannotClaimARuleDifference(unittest.TestCase):

    def test_neither_side_is_ever_rule_bearing(self):
        for record, side in ((human(), "HUMAN"), (mogo(), "MOGO")):
            with self.subTest(side=side):
                self.assertFalse(
                    dd.build_position_from_observation(record, side)["isRuleCategory"])

    def test_no_combination_of_observations_reaches_a_rule_verdict(self):
        """Swept rather than argued: RULE_DIFFERENCE and IMPLEMENTATION_DIFFERENCE
        must be unreachable from this path for EVERY scope combination."""
        instruments = ("EUR/USD", "GBP/USD")
        timeframes = ("H1", "H4", None)
        strategies = ("alex_g_sr_v1", "tjr_manual")
        seen = set()
        for a_i in instruments:
            for b_i in instruments:
                for a_t in timeframes:
                    for b_t in timeframes:
                        for a_s in strategies:
                            for b_s in strategies:
                                a = human(instrument=a_i, timeframe=a_t, strategyId=a_s)
                                b = mogo(instrument=b_i, timeframe=b_t, strategyId=b_s)
                                for rec in (a, b):
                                    if rec["timeframe"] is None:
                                        rec["unknowns"] = ["timeframe"]
                                        rec["fieldClassification"].pop("timeframe", None)
                                seen.add(
                                    dd.observation_difference(a, b)["classification"])
        self.assertNotIn(dd.RULE_DIFFERENCE, seen)
        self.assertNotIn(dd.IMPLEMENTATION_DIFFERENCE, seen)
        # The sweep must actually have exercised more than one outcome, or its
        # absence assertions would be satisfied by a single degenerate verdict.
        self.assertGreaterEqual(len(seen), 3, "sweep did not discriminate: %s" % seen)


class TestActorsMustDiffer(unittest.TestCase):

    def test_two_human_observations_are_refused(self):
        with self.assertRaises(dd.DecisionDifferenceRefused):
            dd.observation_difference(human(), human())

    def test_two_mogo_observations_are_refused(self):
        with self.assertRaises(dd.DecisionDifferenceRefused):
            dd.observation_difference(mogo(), mogo())

    def test_the_sides_cannot_be_swapped(self):
        with self.assertRaises(dd.DecisionDifferenceRefused):
            dd.observation_difference(mogo(), human())


class TestItAdjudicatesNothingAndWritesNothing(unittest.TestCase):

    def test_the_result_declares_it_adjudicates_nothing(self):
        result = dd.observation_difference(human(), mogo())
        self.assertFalse(result["adjudicates"])
        self.assertEqual(result["lane"], "RESEARCH")
        self.assertEqual(result["comparisonType"], "HUMAN_VS_MOGO_OBSERVATION")

    def test_the_basis_records_every_test_that_ran(self):
        result = dd.observation_difference(human(), mogo())
        names = [b["test"] for b in result["basis"]]
        self.assertIn("PROVENANCE_COMPLETE_BOTH_SIDES", names)
        self.assertIn("NO_STATED_DIMENSION_SEPARATES_THE_POSITIONS", names)

    def test_comparing_mutates_no_evidence_file(self):
        roots = [os.path.join(dd.EVIDENCE_ROOT, d)
                 for d in ("claims", "items", "links", "questions",
                           "contradictions", "proposals", "observations")]

        def digest():
            out = {}
            for root in roots:
                for path in sorted(glob.glob(os.path.join(root, "*.json"))):
                    with open(path, "rb") as handle:
                        out[path] = hashlib.sha256(handle.read()).hexdigest()
            return out

        before = digest()
        dd.observation_difference(human(), mogo())
        dd.observation_difference(human(), mogo(instrument="GBP/USD"))
        self.assertEqual(digest(), before)

    def test_the_inputs_themselves_are_not_mutated(self):
        a, b = human(), mogo()
        import copy
        a_before, b_before = copy.deepcopy(a), copy.deepcopy(b)
        dd.observation_difference(a, b)
        self.assertEqual(a, a_before)
        self.assertEqual(b, b_before)


if __name__ == "__main__":
    unittest.main()

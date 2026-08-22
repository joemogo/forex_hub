"""Can a preserved observation's own fields all be true at once? (MOGO-023)"""
import os
import sys
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                         "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts", "trader_intelligence"))

import observation_integrity as oi   # noqa: E402
import trade_observation as to       # noqa: E402

SOURCES = {"EVSRC|F|1": {"sourceId": "EVSRC|F|1", "sourceType": "paper_trade"},
           "EVSRC|H|1": {"sourceId": "EVSRC|H|1", "sourceType": "replay_observation"}}


def rec(oid="o1", opened="2026-08-06T13:11:15.571Z", closed="2026-08-06T15:11:15.571Z",
        entry=1.0850, stop=1.0830, target=1.0890, exit_price=1.0875,
        direction="buy", outcome="Win", r=1.25, source="EVSRC|F|1",
        strategy="alex_g_sr_v1"):
    return {"observationId": oid, "sourceId": source, "actor": "MOGO",
            "openedAt": opened, "closedAt": closed, "entry": entry, "stop": stop,
            "target": target, "exitPrice": exit_price, "direction": direction,
            "outcome": outcome, "rMultiple": r, "strategyId": strategy}


class TestTheLoadBearingRule(unittest.TestCase):
    """An exit pinned to the target in less time than a price update.

    This is the shape TOBS|MOGO|20260806|025 has and the shape closePaperPosition()
    cannot produce: it books fetchBidAsk(), never pos.target.
    """

    def test_the_real_shape_is_caught(self):
        v = oi.evaluate(rec(closed="2026-08-06T13:11:15.575Z", exit_price=1.0890, r=2))
        self.assertEqual([x["ruleId"] for x in v],
                         ["EXIT_PINNED_TO_TARGET_WITH_IMPLAUSIBLE_HOLD"])

    def test_a_target_exit_after_a_REAL_hold_is_NOT_caught(self):
        # The negative control that keeps this from being a "round numbers are bad" rule.
        # Reaching your target is the system working; only the impossible duration is a defect.
        v = oi.evaluate(rec(closed="2026-08-06T17:00:00.000Z", exit_price=1.0890, r=2))
        self.assertEqual(v, [], "a legitimate target exit was flagged")

    def test_a_FAST_exit_that_is_NOT_at_the_target_is_NOT_caught(self):
        # The other half of the conjunction. Speed alone must not condemn a record.
        v = oi.evaluate(rec(closed="2026-08-06T13:11:15.575Z", exit_price=1.0863))
        self.assertEqual(v, [], "a fast but market-priced exit was flagged")

    def test_the_conjunction_is_REQUIRED_not_incidental(self):
        both = oi.evaluate(rec(closed="2026-08-06T13:11:15.575Z", exit_price=1.0890, r=2))
        self.assertTrue(both, "the conjunction must fire")


class TestTheOtherRules(unittest.TestCase):

    def test_a_trade_cannot_close_before_it_opens(self):
        v = oi.evaluate(rec(opened="2026-08-06T15:00:00Z", closed="2026-08-06T14:00:00Z"))
        self.assertIn("CLOSED_AT_OR_BEFORE_OPEN", [x["ruleId"] for x in v])

    def test_a_zero_duration_trade_is_caught(self):
        v = oi.evaluate(rec(opened="2026-08-06T15:00:00Z", closed="2026-08-06T15:00:00Z"))
        self.assertIn("CLOSED_AT_OR_BEFORE_OPEN", [x["ruleId"] for x in v])

    def test_a_win_on_adverse_movement_is_caught(self):
        v = oi.evaluate(rec(entry=1.0850, exit_price=1.0800, outcome="Win"))
        self.assertIn("OUTCOME_CONTRADICTS_PRICE", [x["ruleId"] for x in v])

    def test_a_sell_is_judged_in_ITS_OWN_direction(self):
        # A sell closing BELOW entry is a Win. Judging it with the buy's arithmetic
        # would flag every profitable short in the corpus.
        v = oi.evaluate(rec(direction="sell", entry=1.0850, exit_price=1.0800,
                            outcome="Win", target=1.0800, stop=1.0900,
                            closed="2026-08-06T17:00:00Z"))
        self.assertEqual(v, [], "a legitimate winning short was flagged")

    def test_a_loss_on_favourable_movement_is_caught(self):
        v = oi.evaluate(rec(entry=1.0850, exit_price=1.0900, outcome="Loss",
                            target=1.0950, closed="2026-08-06T17:00:00Z"))
        self.assertIn("OUTCOME_CONTRADICTS_PRICE", [x["ruleId"] for x in v])


class TestItRefusesToGuess(unittest.TestCase):

    def test_missing_timestamps_do_not_fabricate_a_violation(self):
        self.assertEqual(oi.evaluate(rec(opened=None, closed=None)), [])

    def test_missing_prices_do_not_fabricate_a_violation(self):
        self.assertEqual(oi.evaluate(rec(exit_price=None, entry=None)), [])

    def test_an_unparseable_instant_is_not_treated_as_zero(self):
        self.assertIsNone(oi.holding_seconds({"openedAt": "not-a-date",
                                              "closedAt": "2026-08-06T15:00:00Z"}))

    def test_a_rule_that_RAISES_is_reported_not_silently_passed(self):
        # A check that cannot evaluate must report. A raising rule counting as a pass is
        # exactly the absence-is-not-silence defect this milestone exists to end.
        def exploding(_record):
            raise ValueError("boom")
        original = oi.RULES
        oi.RULES = original + (exploding,)
        try:
            ids = [x["ruleId"] for x in oi.evaluate(rec())]
        finally:
            oi.RULES = original
        self.assertTrue(any(x.startswith("RULE_ERROR:") for x in ids),
                        "a raising rule was silently counted as a pass")


class TestThePopulationPartition(unittest.TestCase):

    def corpus(self):
        return {"good": rec("good", r=1.0),
                "bad": rec("bad", closed="2026-08-06T13:11:15.575Z",
                           exit_price=1.0890, r=2.0)}

    def test_raw_and_authoritative_are_reported_TOGETHER(self):
        r = oi.report(self.corpus(), SOURCES, population=to.FORWARD)
        self.assertEqual(r["rawPreservedPopulation"]["n"], 2)
        self.assertEqual(r["authoritativeVerifiedPopulation"]["n"], 1)
        self.assertEqual(r["excludedFromAuthoritative"]["n"], 1)

    def test_the_quantitative_effect_of_exclusion_is_disclosed(self):
        r = oi.report(self.corpus(), SOURCES, population=to.FORWARD)
        self.assertEqual(r["effectOfExclusion"]["sumR"], -2.0,
                         "the report must price what excluding the record does")

    def test_the_excluded_record_names_the_rule_it_violated(self):
        r = oi.report(self.corpus(), SOURCES, population=to.FORWARD)
        self.assertEqual(len(r["findings"]), 1)
        self.assertEqual(r["findings"][0]["observationId"], "bad")
        self.assertTrue(r["findings"][0]["violations"][0]["detail"])

    def test_nothing_is_removed_from_the_raw_population(self):
        r = oi.report(self.corpus(), SOURCES, population=to.FORWARD)
        self.assertEqual(r["rawPreservedPopulation"]["n"],
                         r["authoritativeVerifiedPopulation"]["n"]
                         + r["excludedFromAuthoritative"]["n"],
                         "the partition must be exhaustive -- nothing may vanish")


class TestAgainstTheRealCorpus(unittest.TestCase):

    def test_exactly_one_forward_record_fails_and_it_is_the_known_one(self):
        r = oi.report(population=to.FORWARD)
        ids = [f["observationId"] for f in r["findings"]]
        self.assertEqual(ids, ["TOBS|MOGO|20260806|025"],
                         "the set of unverified forward records changed: %s" % ids)

    def test_the_replay_population_is_CLEAN_so_the_rules_are_not_trigger_happy(self):
        # 221 records. If these rules had a meaningful false-positive rate it would show
        # here, and the rule set would be wrong rather than the corpus.
        r = oi.report(population=to.HISTORICAL)
        self.assertEqual(r["excludedFromAuthoritative"]["n"], 0,
                         "the rules fired on replay evidence: %s" % r["findings"])
        self.assertGreater(r["rawPreservedPopulation"]["n"], 200,
                           "the filter selected almost nothing, so this proves little")

    def test_excluding_the_record_makes_forward_performance_WORSE_not_better(self):
        # The direction matters: the record flatters the sample, so removing it must
        # lower the result. A guard that improved the numbers would be suspect itself.
        r = oi.report(population=to.FORWARD)
        self.assertLess(r["authoritativeVerifiedPopulation"]["sumR"],
                        r["rawPreservedPopulation"]["sumR"])

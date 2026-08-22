"""Is a missing cohort STARVATION or just rarity? (MOGO-022)"""
import os
import sys
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                         "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts", "trader_intelligence"))

import forward_coverage as fc      # noqa: E402
import trade_observation as to     # noqa: E402

SOURCES = {"EVSRC|F|1": {"sourceId": "EVSRC|F|1", "sourceType": "paper_trade"},
           "EVSRC|H|1": {"sourceId": "EVSRC|H|1", "sourceType": "replay_observation"}}


def obs(oid, source_id, timeframe):
    return {"observationId": oid, "sourceId": source_id, "actor": "MOGO",
            "timeframe": timeframe}


class TestTheRarityDistinction(unittest.TestCase):
    """The whole reason this exists: an absent cohort looks identical whether the
    setup is rare or the engine stopped evaluating it."""

    def test_absent_with_a_tiny_expectation_is_rarity_not_starvation(self):
        # Weekly's real shape: 2 of 221 historical, 0 forward at n=27 -> expect ~0.24
        verdict, expected = fc.assess_cohort(0, 2 / 221.0, 27)
        self.assertEqual(verdict, fc.ABSENT_CONSISTENT_WITH_RARITY)
        self.assertLess(expected, 1.0)

    def test_absent_where_several_were_expected_IS_flagged(self):
        """The positive control. Without it the report could call every absence
        'rarity' and never surface a real starvation."""
        verdict, expected = fc.assess_cohort(0, 0.5, 40)
        self.assertEqual(verdict, fc.ABSENT_UNEXPLAINED)
        self.assertGreaterEqual(expected, fc.EXPECTED_COUNT_ALARM_THRESHOLD)

    def test_the_same_cohort_flips_verdict_as_the_sample_grows(self):
        """Rarity is not a permanent excuse: a cohort absent at small n becomes
        unexplained once enough forward evidence exists."""
        share = 0.10
        self.assertEqual(fc.assess_cohort(0, share, 10)[0],
                         fc.ABSENT_CONSISTENT_WITH_RARITY)
        self.assertEqual(fc.assess_cohort(0, share, 200)[0], fc.ABSENT_UNEXPLAINED)

    def test_present_is_present_regardless_of_base_rate(self):
        self.assertEqual(fc.assess_cohort(1, 0.0001, 1000)[0], fc.PRESENT)

    def test_no_historical_evidence_is_UNKNOWN_not_fine(self):
        verdict, expected = fc.assess_cohort(0, None, 100)
        self.assertEqual(verdict, fc.NO_BASE_RATE)
        self.assertIsNone(expected)


class TestTheReport(unittest.TestCase):

    def corpus(self, forward_tfs, historical_tfs):
        records = {}
        for i, tf in enumerate(forward_tfs):
            records["f%d" % i] = obs("f%d" % i, "EVSRC|F|1", tf)
        for i, tf in enumerate(historical_tfs):
            records["h%d" % i] = obs("h%d" % i, "EVSRC|H|1", tf)
        return records

    def test_a_configured_cohort_with_no_evidence_at_all_still_appears(self):
        r = fc.report(self.corpus(["H1"], ["H1"]), SOURCES, configured=["H1", "W"])
        cohorts = {row["cohort"] for row in r["rows"]}
        self.assertIn("W", cohorts, "a configured cohort vanished from the report")

    def test_an_unexplained_absence_is_surfaced_at_the_top_level(self):
        # 20 of 20 historical are H4, so at 20 forward H4 is expected 20 times.
        r = fc.report(self.corpus(["H1"] * 20, ["H4"] * 20), SOURCES,
                      configured=["H1", "H4"])
        self.assertIn("H4", r["unexplainedAbsences"])

    def test_a_rare_absence_is_NOT_surfaced(self):
        r = fc.report(self.corpus(["H1"] * 27, ["H1"] * 219 + ["W", "W"]), SOURCES,
                      configured=["H1", "W"])
        self.assertEqual(r["unexplainedAbsences"], [])

    def test_it_states_what_the_base_rate_does_not_support(self):
        r = fc.report(self.corpus(["H1"], ["H1"]), SOURCES, configured=["H1"])
        blob = " ".join(r["doesNotSupport"]).lower()
        self.assertIn("says nothing about how that cohort performs", blob)
        self.assertFalse(r["adjudicates"])

    def test_reconstructed_evidence_is_not_counted_as_forward(self):
        records = self.corpus(["H1"], ["H1"])
        sources = dict(SOURCES)
        sources["EVSRC|R|1"] = {"sourceId": "EVSRC|R|1", "sourceType": "journal_entry"}
        records["r1"] = obs("r1", "EVSRC|R|1", "W")
        r = fc.report(records, sources, configured=["H1", "W"])
        row = [x for x in r["rows"] if x["cohort"] == "W"][0]
        self.assertEqual(row["forwardCount"], 0,
                         "reconstructed evidence was counted as forward coverage")


class TestAgainstTheRealCorpus(unittest.TestCase):

    def test_no_configured_timeframe_is_unexplainedly_absent(self):
        r = fc.report(configured=["H1", "H4", "D", "W"], key="timeframe")
        self.assertEqual(r["unexplainedAbsences"], [],
                         "a configured timeframe has no forward evidence and rarity "
                         "does not explain it: %s" % r["unexplainedAbsences"])

    def test_the_report_covers_every_configured_timeframe(self):
        r = fc.report(configured=["H1", "H4", "D", "W"], key="timeframe")
        self.assertEqual({row["cohort"] for row in r["rows"]} & {"H1", "H4", "D", "W"},
                         {"H1", "H4", "D", "W"})


def obs_s(oid, source_id, timeframe, strategy_id):
    """An observation that names its strategy. `strategy_id=None` means unattributed."""
    record = obs(oid, source_id, timeframe)
    if strategy_id is not None:
        record["strategyId"] = strategy_id
    return record


class TestStrategyPopulationIsolation(unittest.TestCase):
    """MOGO-023: no strategy may silently contribute to another's population.

    The real defect: the forward population is 27 `alex_g_sr_v1` + 2 `current_strategy`
    (JVM) while the historical base rate is 221 `alex_g_sr_v1` and nothing else. The
    report divided by one population and counted another, and scoping to ALEX flips
    AUD/USD from PRESENT to ABSENT_CONSISTENT_WITH_RARITY -- a different conclusion, not
    a cosmetic label.
    """

    def mixed(self):
        records = {}
        # forward: 2 ALEX on H1, 1 JVM on H4 -- the JVM row is the contaminant
        records["f0"] = obs_s("f0", "EVSRC|F|1", "H1", "alex_g_sr_v1")
        records["f1"] = obs_s("f1", "EVSRC|F|1", "H1", "alex_g_sr_v1")
        records["f2"] = obs_s("f2", "EVSRC|F|1", "H4", "current_strategy")
        # historical: ALEX only, which is what makes the base rate ALEX's
        for i in range(10):
            records["h%d" % i] = obs_s("h%d" % i, "EVSRC|H|1", "H1", "alex_g_sr_v1")
        return records

    def test_an_unscoped_report_DECLARES_that_it_mixes_strategies(self):
        r = fc.report(self.mixed(), SOURCES, configured=["H1", "H4"])
        self.assertFalse(r["strategyScoped"])
        self.assertTrue(r["strategyMixing"],
                        "two strategies contributed and the report did not say so")
        self.assertEqual(r["forwardStrategyComposition"],
                         {"alex_g_sr_v1": 2, "current_strategy": 1})

    def test_scoping_EXCLUDES_the_other_strategy_from_the_counts(self):
        r = fc.report(self.mixed(), SOURCES, configured=["H1", "H4"],
                      strategy_id="alex_g_sr_v1")
        self.assertTrue(r["strategyScoped"])
        self.assertFalse(r["strategyMixing"], "a scoped report cannot be mixed")
        self.assertEqual(r["forwardTotal"], 2, "JVM's row was counted as ALEX's")
        h4 = [x for x in r["rows"] if x["cohort"] == "H4"][0]
        self.assertEqual(h4["forwardCount"], 0,
                         "the JVM H4 trade still appears in ALEX's coverage")

    def test_the_excluded_rows_are_COUNTED_not_silently_dropped(self):
        r = fc.report(self.mixed(), SOURCES, configured=["H1", "H4"],
                      strategy_id="alex_g_sr_v1")
        self.assertEqual(r["excluded"]["forwardOtherStrategy"], 1,
                         "an excluded record must be reported, never merely absent")

    def test_a_record_missing_the_cohort_key_is_REPORTED_not_vanished(self):
        # JVM hardcodes timeframe:null, which is exactly how forwardTotal read 27
        # while the forward population held 29 and nothing said two were dropped.
        records = self.mixed()
        records["f3"] = obs_s("f3", "EVSRC|F|1", None, "alex_g_sr_v1")
        r = fc.report(records, SOURCES, configured=["H1"], strategy_id="alex_g_sr_v1")
        self.assertEqual(r["excluded"]["forwardMissingCohortKey"], 1)
        self.assertEqual(r["forwardTotal"], 2,
                         "a record with no cohort value must not inflate the total")

    def test_attribution_is_never_GUESSED_for_an_unattributed_record(self):
        records = self.mixed()
        records["f9"] = obs_s("f9", "EVSRC|F|1", "H1", None)   # no strategyId at all
        r = fc.report(records, SOURCES, configured=["H1"])
        self.assertEqual(r["forwardStrategyComposition"].get(fc.UNATTRIBUTED), 1,
                         "a record with no strategyId must be UNATTRIBUTED, not folded "
                         "into whichever strategy happens to be nearby")
        scoped = fc.report(records, SOURCES, configured=["H1"],
                           strategy_id="alex_g_sr_v1")
        self.assertEqual(scoped["forwardTotal"], 2,
                         "an unattributed record was counted as ALEX's")

    def test_an_unscoped_mixed_report_states_it_describes_no_single_strategy(self):
        r = fc.report(self.mixed(), SOURCES, configured=["H1", "H4"])
        self.assertTrue(any("NOT scoped to one strategy" in s
                            for s in r["doesNotSupport"]),
                        "a mixed report must disclaim strategy-specific readings")

    def test_configured_cohorts_belong_to_their_own_dimension(self):
        # The timeframe universe must not be injected into an instrument report.
        self.assertEqual(fc.CONFIGURED_BY_KEY.get("instrument"), None)
        self.assertEqual(fc.CONFIGURED_BY_KEY["timeframe"], ["H1", "H4", "D", "W"])


class TestTheRealCorpusIsStrategySegmentable(unittest.TestCase):

    def test_the_live_forward_population_is_measurably_mixed(self):
        r = fc.report(key="instrument")
        self.assertTrue(r["strategyMixing"],
                        "the real forward population is ALEX + JVM; if this ever goes "
                        "false, verify segregation rather than assuming it improved")
        self.assertIn("current_strategy", r["forwardStrategyComposition"])

    def test_scoping_to_ALEX_changes_a_verdict_on_the_real_corpus(self):
        mixed = fc.report(key="instrument")
        alex = fc.report(key="instrument", strategy_id="alex_g_sr_v1")
        self.assertLess(alex["forwardTotal"], mixed["forwardTotal"],
                        "scoping removed nothing, so the arms were never mixed")
        self.assertEqual(alex["excluded"]["forwardOtherStrategy"],
                         mixed["forwardTotal"] - alex["forwardTotal"])

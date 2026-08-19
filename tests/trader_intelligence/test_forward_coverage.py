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

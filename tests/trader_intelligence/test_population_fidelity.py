"""Population-fidelity comparison: does replay predict forward? (MOGO-022)

Fixtures only. No real paper trade is written or read as the subject of a test --
the production corpus is used in exactly one integration check, read-only.
"""
import os
import sys
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                         "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts", "trader_intelligence"))

import population_fidelity as pf     # noqa: E402
import trade_observation as to       # noqa: E402


def source(source_id, source_type):
    return {"sourceId": source_id, "sourceType": source_type}


SOURCES = {
    "EVSRC|REPLAY|1": source("EVSRC|REPLAY|1", "replay_observation"),
    "EVSRC|FWD|1": source("EVSRC|FWD|1", "paper_trade"),
    "EVSRC|MYSTERY|1": source("EVSRC|MYSTERY|1", "something_unregistered"),
}


def observation(obs_id, source_id, r_multiple, outcome="Loss",
                strategy_id="alex_g_sr_v1", instrument="GBP/USD"):
    return {
        "observationId": obs_id,
        "sourceId": source_id,
        "strategyId": strategy_id,
        "actor": "MOGO",
        "instrument": instrument,
        "rMultiple": r_multiple,
        "outcome": outcome,
        "closedAt": "2026-08-0%dT00:00:00.000Z" % ((abs(hash(obs_id)) % 9) + 1),
        "unknowns": [],
    }


def corpus(pairs):
    """pairs: (sourceId, rMultiple, outcome) -> an observations dict."""
    return {("TOBS|MOGO|%03d" % i): observation("TOBS|MOGO|%03d" % i, src, r, outcome)
            for i, (src, r, outcome) in enumerate(pairs)}


IDEALIZED_REPLAY = [("EVSRC|REPLAY|1", -1.0, "Loss"), ("EVSRC|REPLAY|1", 2.0, "Win"),
                    ("EVSRC|REPLAY|1", -1.0, "Loss")]
SLIPPING_FORWARD = [("EVSRC|FWD|1", -1.0774, "Loss"), ("EVSRC|FWD|1", 2.0431, "Win"),
                    ("EVSRC|FWD|1", -1.0234, "Loss")]


class TestRefusals(unittest.TestCase):

    def test_it_refuses_to_compare_without_the_source_map(self):
        with self.assertRaises(to.ObservationRefused):
            pf.compare(corpus(IDEALIZED_REPLAY), None, "alex_g_sr_v1")

    def test_it_refuses_without_a_strategy(self):
        with self.assertRaises(to.ObservationRefused):
            pf.compare(corpus(IDEALIZED_REPLAY), SOURCES, "")

    def test_with_both_supplied_it_does_not_refuse(self):
        """Positive control: the refusals above must be caused by the missing
        argument, not by the fixture being unusable for any other reason."""
        report = pf.compare(corpus(IDEALIZED_REPLAY), SOURCES, "alex_g_sr_v1")
        self.assertEqual(report["byPopulation"]["HISTORICAL"]["n"], 3)


class TestPopulationsAreNeverBlended(unittest.TestCase):

    def test_no_aggregate_total_across_populations_is_offered(self):
        report = pf.compare(corpus(IDEALIZED_REPLAY + SLIPPING_FORWARD),
                            SOURCES, "alex_g_sr_v1")
        self.assertEqual(set(report["populationsPresent"]), {"HISTORICAL", "FORWARD"})
        self.assertNotIn("total", report)
        self.assertNotIn("n", report)

    def test_another_strategy_is_not_counted(self):
        records = corpus(IDEALIZED_REPLAY)
        stray = observation("TOBS|MOGO|999", "EVSRC|FWD|1", -1.0,
                            strategy_id="some_other_strategy")
        records[stray["observationId"]] = stray
        report = pf.compare(records, SOURCES, "alex_g_sr_v1")
        self.assertNotIn("FORWARD", report["byPopulation"])

    def test_an_unresolvable_source_lands_in_UNKNOWN_not_forward(self):
        records = corpus([("EVSRC|MYSTERY|1", -1.5, "Loss")])
        report = pf.compare(records, SOURCES, "alex_g_sr_v1")
        self.assertEqual(sorted(report["byPopulation"]), ["UNKNOWN"])


class TestTheFinding(unittest.TestCase):

    def report(self, pairs):
        return pf.compare(corpus(pairs), SOURCES, "alex_g_sr_v1")

    def codes(self, report):
        return {f["code"] for f in report["findings"]}

    def test_it_fires_when_replay_is_idealized_and_forward_overshoots(self):
        report = self.report(IDEALIZED_REPLAY + SLIPPING_FORWARD)
        self.assertIn(pf.REPLAY_IDEALIZES_EXITS, self.codes(report))

    def test_it_does_not_fire_when_replay_also_overshoots(self):
        """The negative case that makes the finding mean something: if replay
        models slippage too, there is no mechanism difference to report."""
        replay_with_slippage = [("EVSRC|REPLAY|1", -1.08, "Loss"),
                                ("EVSRC|REPLAY|1", 2.04, "Win"),
                                ("EVSRC|REPLAY|1", -1.02, "Loss")]
        report = self.report(replay_with_slippage + SLIPPING_FORWARD)
        self.assertNotIn(pf.REPLAY_IDEALIZES_EXITS, self.codes(report))

    def test_it_does_not_fire_when_forward_does_not_overshoot(self):
        clean_forward = [("EVSRC|FWD|1", -1.0, "Loss"), ("EVSRC|FWD|1", 2.0, "Win")]
        report = self.report(IDEALIZED_REPLAY + clean_forward)
        self.assertNotIn(pf.REPLAY_IDEALIZES_EXITS, self.codes(report))

    def test_it_does_not_fire_with_only_one_population(self):
        self.assertEqual(self.report(IDEALIZED_REPLAY)["findings"], [])
        self.assertEqual(self.report(SLIPPING_FORWARD)["findings"], [])

    def test_rounding_noise_is_not_reported_as_slippage(self):
        """-1.003R is a rounded 1R, not an overshoot. Without a tolerance the
        finding would fire on arithmetic noise and mean nothing."""
        barely = [("EVSRC|FWD|1", -1.003, "Loss"), ("EVSRC|FWD|1", 2.0, "Win")]
        report = self.report(IDEALIZED_REPLAY + barely)
        self.assertEqual(report["byPopulation"]["FORWARD"]["offReplayLattice"], [])
        self.assertNotIn(pf.REPLAY_IDEALIZES_EXITS, self.codes(report))

    def test_a_real_overshoot_is_reported_as_slippage(self):
        """The positive control for the tolerance above: it must not be so wide
        that it swallows the effect it exists to distinguish from noise."""
        report = self.report(IDEALIZED_REPLAY + SLIPPING_FORWARD)
        self.assertEqual(report["byPopulation"]["FORWARD"]["offReplayLattice"],
                         [-1.0774, -1.0234, 2.0431])

    def test_both_directions_of_overshoot_are_reported(self):
        """The correction that matters. An earlier draft reported only the adverse
        side and stated that replay "understates what a loss costs" -- one-sided,
        and misleading, because forward exits overshoot the TARGET too and the mean
        overshoot on wins is favourable. Both sides must appear in the basis."""
        report = self.report(IDEALIZED_REPLAY + SLIPPING_FORWARD)
        basis = [f for f in report["findings"]
                 if f["code"] == pf.REPLAY_IDEALIZES_EXITS][0]["basis"]
        self.assertEqual(basis["worseThanReplayWorst"], [-1.0774, -1.0234])
        self.assertEqual(basis["betterThanReplayBest"], [2.0431])

    def test_a_purely_favourable_overshoot_still_fires(self):
        """Guards against a finding that only ever looks for adverse slippage: an
        exit that gaps past the TARGET is the same mechanism."""
        favourable = [("EVSRC|FWD|1", 2.09, "Win"), ("EVSRC|FWD|1", -1.0, "Loss")]
        report = self.report(IDEALIZED_REPLAY + favourable)
        self.assertIn(pf.REPLAY_IDEALIZES_EXITS, self.codes(report))
        basis = [f for f in report["findings"]
                 if f["code"] == pf.REPLAY_IDEALIZES_EXITS][0]["basis"]
        self.assertEqual(basis["worseThanReplayWorst"], [])
        self.assertEqual(basis["betterThanReplayBest"], [2.09])

    def test_the_finding_states_what_it_does_not_support(self):
        report = self.report(IDEALIZED_REPLAY + SLIPPING_FORWARD)
        finding = [f for f in report["findings"]
                   if f["code"] == pf.REPLAY_IDEALIZES_EXITS][0]
        self.assertTrue(finding["doesNotSupport"])
        self.assertTrue(report["doesNotSupport"])
        self.assertFalse(report["adjudicates"])

    def test_win_rate_difference_is_never_promoted_to_a_finding(self):
        """A large win-rate gap with no slippage difference must yield NO finding.
        The gap is real in the data and deliberately not concluded from."""
        losing_forward = [("EVSRC|FWD|1", -1.0, "Loss")] * 9 + \
                         [("EVSRC|FWD|1", 2.0, "Win")]
        winning_replay = [("EVSRC|REPLAY|1", 2.0, "Win")] * 9 + \
                         [("EVSRC|REPLAY|1", -1.0, "Loss")]
        report = self.report(winning_replay + losing_forward)
        self.assertEqual(report["findings"], [])


class TestAgainstTheRealCorpus(unittest.TestCase):
    """One read-only integration check. Asserts the RELATION, not a snapshot."""

    @classmethod
    def setUpClass(cls):
        cls.report = pf.compare(to.load_observations(), to.load_sources(),
                                "alex_g_sr_v1")

    def test_both_populations_are_present_for_the_implementation(self):
        self.assertEqual(set(self.report["populationsPresent"]), {"HISTORICAL", "FORWARD"})

    def test_replay_books_fewer_distinct_outcomes_than_forward(self):
        historical = self.report["byPopulation"]["HISTORICAL"]
        forward = self.report["byPopulation"]["FORWARD"]
        self.assertGreater(historical["n"], 0)
        self.assertGreater(forward["n"], 0)
        self.assertLess(len(historical["distinctRMultiples"]),
                        len(forward["distinctRMultiples"]))

    def test_the_slippage_finding_holds_on_the_real_corpus(self):
        self.assertIn(pf.REPLAY_IDEALIZES_EXITS,
                      {f["code"] for f in self.report["findings"]})


if __name__ == "__main__":
    unittest.main()

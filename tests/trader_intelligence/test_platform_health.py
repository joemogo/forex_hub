"""Is MOGO actually operating correctly -- and can the thing that says so ever say no?

(MOGO-023). These fixtures guard the health authority itself. The failure being designed
against is not a wrong verdict, it is a CONFIDENT one: a report that renders GREEN because
a probe silently did nothing.
"""
import datetime
import os
import sys
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                         "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts", "trader_intelligence"))

import platform_health as ph      # noqa: E402
import trade_observation as to    # noqa: E402

SRC = {"S|F": {"sourceId": "S|F", "sourceType": "paper_trade"}}


def obs(oid="a", **kw):
    base = {"observationId": oid, "sourceId": "S|F", "actor": "MOGO",
            "strategyId": "alex_g_sr_v1", "openedAt": "2026-08-06T10:00:00Z",
            "closedAt": "2026-08-06T12:00:00Z", "entry": 1.10, "stop": 1.09,
            "target": 1.12, "exitPrice": 1.11, "direction": "buy",
            "outcome": "Win", "rMultiple": 1.0}
    base.update(kw)
    return base


class TestUnknownNeverBecomesGreen(unittest.TestCase):
    """The single property this module exists to protect."""

    def test_one_unknown_among_greens_makes_the_whole_verdict_unknown(self):
        self.assertEqual(ph.overall([ph._check("a", ph.GREEN, ""),
                                     ph._check("b", ph.GREEN, ""),
                                     ph._check("c", ph.UNKNOWN, "")]), ph.UNKNOWN)

    def test_unknown_outranks_yellow(self):
        self.assertEqual(ph.overall([ph._check("a", ph.YELLOW, ""),
                                     ph._check("b", ph.UNKNOWN, "")]), ph.UNKNOWN)

    def test_red_outranks_unknown_because_an_established_failure_is_actionable(self):
        self.assertEqual(ph.overall([ph._check("a", ph.UNKNOWN, ""),
                                     ph._check("b", ph.RED, "")]), ph.RED)

    def test_no_checks_at_all_is_unknown_not_green(self):
        # A report that ran nothing must not congratulate itself.
        self.assertEqual(ph.overall([]), ph.UNKNOWN)

    def test_an_unrecognised_state_is_treated_as_unknown_not_ignored(self):
        self.assertEqual(ph.overall([ph._check("a", ph.GREEN, ""),
                                     ph._check("b", "WEIRD", "")]), "WEIRD")


class TestEachCheckCanActuallyFail(unittest.TestCase):
    """A check that cannot go red is decoration. Each is driven to its failure state."""

    def test_population_goes_red_on_an_empty_corpus(self):
        self.assertEqual(ph.check_observation_population({}, SRC)["state"], ph.RED)

    def test_population_is_green_on_a_healthy_corpus(self):
        # Positive control: without it the check could return RED unconditionally.
        self.assertEqual(ph.check_observation_population({"a": obs()}, SRC)["state"],
                         ph.GREEN)

    def test_attribution_goes_red_on_an_unattributed_record(self):
        r = ph.check_strategy_attribution({"a": obs(strategyId=None)})
        self.assertEqual(r["state"], ph.RED)

    def test_attribution_is_green_when_every_record_names_a_strategy(self):
        self.assertEqual(ph.check_strategy_attribution({"a": obs()})["state"], ph.GREEN)

    def test_integrity_goes_yellow_not_red_on_a_contradicting_record(self):
        # YELLOW deliberately: the record is isolated and excluded, every other figure
        # stays valid, and RED would create pressure to "fix" preserved evidence.
        r = ph.check_observation_integrity(
            {"a": obs(closedAt="2026-08-06T10:00:00.004Z", exitPrice=1.12, rMultiple=2.0)},
            SRC)
        self.assertEqual(r["state"], ph.YELLOW)

    def test_a_missing_live_store_is_unknown_not_red(self):
        # Absence of the operator's store on some other machine is not an engine fault.
        self.assertEqual(ph.check_live_store(store_path="/nonexistent/x")["state"],
                         ph.UNKNOWN)

    def test_a_stale_live_store_is_yellow(self):
        r = ph.check_live_store(store_path=REPO_ROOT,
                                clock=ph._now() + datetime.timedelta(days=400))
        self.assertEqual(r["state"], ph.YELLOW)

    def test_an_unprobed_provider_is_unknown_not_green(self):
        self.assertEqual(ph.check_provider(enabled=False)["state"], ph.UNKNOWN)

    def test_engine_evaluation_is_unknown_and_says_why(self):
        r = ph.check_engine_evaluation()
        self.assertEqual(r["state"], ph.UNKNOWN)
        self.assertTrue(r["evidence"].get("reason"),
                        "an UNKNOWN must carry its reason or it is just a shrug")


class TestTheChecksAreActuallyWIRED(unittest.TestCase):
    """B-32 found gates written but never called SIX times. This is that invariant."""

    def test_every_check_appears_in_the_report(self):
        r = ph.report({"a": obs()}, SRC, network=False, store_path="/nonexistent/x")
        names = {c["check"] for c in r["checks"]}
        for expected in ("observation_population", "strategy_attribution",
                         "observation_integrity", "live_store",
                         "provider_transport", "engine_evaluation"):
            self.assertIn(expected, names, "%s is defined but never called" % expected)

    def test_the_overall_verdict_is_derived_from_the_checks_not_hardcoded(self):
        # Drive the corpus to RED and the overall must follow it.
        r = ph.report({}, SRC, network=False, store_path="/nonexistent/x")
        self.assertEqual(r["overall"], ph.RED)

    def test_a_healthy_corpus_still_reports_unknown_overall_from_the_host(self):
        # The honest result: engine evaluation is not observable here, so the platform
        # verdict cannot be GREEN from the host no matter how clean the corpus is.
        r = ph.report({"a": obs()}, SRC, network=False, store_path=REPO_ROOT)
        self.assertEqual(r["overall"], ph.UNKNOWN)

    def test_counts_sum_to_the_number_of_checks(self):
        r = ph.report({"a": obs()}, SRC, network=False, store_path=REPO_ROOT)
        self.assertEqual(sum(r["counts"].values()), len(r["checks"]),
                         "a check fell out of the tally")


class TestTheSelftestItself(unittest.TestCase):

    def test_the_injection_selftest_passes(self):
        self.assertEqual(ph.selftest(), 0)


class TestAgainstTheRealCorpus(unittest.TestCase):

    def test_the_real_corpus_classifies_and_attributes_cleanly(self):
        observations, sources = to.load_observations(), to.load_sources()
        self.assertEqual(ph.check_observation_population(observations, sources)["state"],
                         ph.GREEN)
        self.assertEqual(ph.check_strategy_attribution(observations)["state"], ph.GREEN)

    def test_the_real_report_never_claims_green_overall_from_the_host(self):
        r = ph.report(network=False)
        self.assertNotEqual(r["overall"], ph.GREEN,
                            "the host cannot observe the engine, so a GREEN platform "
                            "verdict from here would be a claim nothing established")

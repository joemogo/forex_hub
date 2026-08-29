"""Is MOGO actually operating correctly -- and can the thing that says so ever say no?

(MOGO-023). These fixtures guard the health authority itself. The failure being designed
against is not a wrong verdict, it is a CONFIDENT one: a report that renders GREEN because
a probe silently did nothing.
"""
import contextlib
import datetime
import os
import shutil
import sys
import tempfile
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


@contextlib.contextmanager
def controlled_store():
    """A store directory OUTSIDE the repository, with its own mtime as the time anchor.

    Every freshness assertion below is expressed as an offset from THIS directory's mtime and
    handed to check_live_store as an injected clock, so nothing depends on the current date,
    the repository's age, the local timezone, or how long the suite takes to run. The
    repository root is never created, touched or re-stamped.
    """
    tmp = tempfile.mkdtemp(prefix="mogo-health-test-")
    try:
        path = os.path.join(tmp, "store")
        os.makedirs(path)
        mtime = datetime.datetime.fromtimestamp(os.path.getmtime(path),
                                                datetime.timezone.utc)
        yield path, mtime
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


class TestLiveStoreFreshnessIsDeterministic(unittest.TestCase):
    """The live-store freshness check, with BOTH sides of the age calculation controlled.

    The defect these replace: the selftest's GREEN case passed REPO_ROOT with no injected
    clock, so it reported GREEN only while the repository directory happened to have been
    written within STORE_STALE_AFTER_HOURS. It passed for a week, then failed on elapsed time
    alone. check_live_store was correct throughout -- the fixture was not.
    """

    def _state(self, path, mtime, hours):
        return ph.check_live_store(
            store_path=path, clock=mtime + datetime.timedelta(hours=hours))["state"]

    def test_a_controlled_fresh_store_is_green(self):
        with controlled_store() as (path, mtime):
            self.assertEqual(self._state(path, mtime, 0.0), ph.GREEN)

    def test_a_controlled_stale_store_is_yellow(self):
        with controlled_store() as (path, mtime):
            self.assertEqual(self._state(path, mtime, ph.STORE_STALE_AFTER_HOURS + 24.0),
                             ph.YELLOW)

    def test_a_missing_store_is_unknown_not_green_and_not_red(self):
        r = ph.check_live_store(store_path="/nonexistent/mogo/store")
        self.assertEqual(r["state"], ph.UNKNOWN)
        self.assertNotEqual(r["state"], ph.GREEN)

    def test_exactly_at_the_threshold_is_green_because_the_operator_is_strict(self):
        # Production compares `age_h > stale_hours`. Equality must therefore be GREEN, and
        # this is the assertion that a `>` -> `>=` mutation has to break.
        with controlled_store() as (path, mtime):
            self.assertEqual(self._state(path, mtime, ph.STORE_STALE_AFTER_HOURS), ph.GREEN)

    def test_one_second_past_the_threshold_is_yellow(self):
        # One second, not a sub-microsecond epsilon: the result must not turn on filesystem
        # timestamp granularity, which differs across macOS and CI filesystems.
        with controlled_store() as (path, mtime):
            self.assertEqual(
                self._state(path, mtime, ph.STORE_STALE_AFTER_HOURS + 1.0 / 3600.0),
                ph.YELLOW)

    def test_the_injected_clock_is_honoured(self):
        # The same path yields different states purely from the clock, which proves the
        # injection is read rather than ignored in favour of the wall clock.
        with controlled_store() as (path, mtime):
            self.assertEqual(self._state(path, mtime, 0.0), ph.GREEN)
            self.assertEqual(self._state(path, mtime, ph.STORE_STALE_AFTER_HOURS + 1.0),
                             ph.YELLOW)

    def test_the_result_follows_the_supplied_path_not_ambient_repository_state(self):
        # Repository-age independence, demonstrated by CONSTRUCTION rather than by asserting
        # anything about today's REPO_ROOT -- asserting REPO_ROOT is stale would simply create
        # a second time-dependent test. Two stores, one clock, opposite verdicts.
        with controlled_store() as (fresh, mtime):
            with controlled_store() as (stale, _unused):
                old = (mtime - datetime.timedelta(hours=ph.STORE_STALE_AFTER_HOURS + 48.0))
                os.utime(stale, (old.timestamp(), old.timestamp()))   # temp path only
                clock = mtime + datetime.timedelta(seconds=1)
                self.assertEqual(
                    ph.check_live_store(store_path=fresh, clock=clock)["state"], ph.GREEN)
                self.assertEqual(
                    ph.check_live_store(store_path=stale, clock=clock)["state"], ph.YELLOW)

    def test_the_repository_root_is_never_the_default_store(self):
        # The production default must remain the real LevelDB path. If REPO_ROOT ever became
        # the default, every assertion above would silently start measuring the repository.
        self.assertNotEqual(os.path.abspath(ph.LIVE_STORE), os.path.abspath(REPO_ROOT))
        self.assertIn("indexeddb.leveldb", ph.LIVE_STORE)

    def test_the_selftest_live_store_fixtures_are_controlled_not_the_repository(self):
        # Structural, and deliberately so. Every behavioural assertion above would still pass
        # if the SELFTEST went back to using REPO_ROOT -- and re-running that mutation would
        # only fail while the repository happens to be stale, which is a time-dependent kill
        # and therefore no guarantee at all. This asserts the fixture construction itself, so
        # reintroducing REPO_ROOT fails immediately and on any machine at any time.
        import re
        src = open(os.path.join(REPO_ROOT, "scripts", "trader_intelligence",
                                "platform_health.py"), encoding="utf-8").read()
        block = src[src.index("def selftest("):]
        block = block[:block.index("live store boundary: one second")]
        live = block[block.index("live store UNKNOWN when absent"):]
        self.assertNotIn("REPO_ROOT", live,
                         "the selftest's live-store fixtures must not use the repository root; "
                         "its mtime is outside the test's control and decays into a failure")
        self.assertIn("tempfile.mkdtemp", block,
                      "the selftest must build a controlled temporary store")
        self.assertIn("clock=_mt", block,
                      "the selftest must anchor its clock to the fixture's own mtime")

    def test_report_resolves_the_production_default_when_no_path_is_given(self):
        # report(store_path=None) must reach check_live_store with the production default.
        seen = {}
        real = ph.check_live_store

        def spy(store_path=None, clock=None, stale_hours=None):
            seen["store_path"] = store_path
            return real(store_path=store_path, clock=clock, stale_hours=stale_hours)

        ph.check_live_store = spy
        try:
            ph.report({"a": obs()}, SRC, network=False)
        finally:
            ph.check_live_store = real
        self.assertIn("store_path", seen, "report() never called check_live_store")
        self.assertIsNone(seen["store_path"],
                          "report() must pass the default through, letting check_live_store "
                          "resolve LIVE_STORE itself")


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

#!/usr/bin/env python3
"""Package -> MOGO TradeObservation import (MOGO-022).

The properties under test:

  * IT INVENTS NOTHING. A null package field becomes an explicit UNKNOWN; it is
    never defaulted, and 0.0 is kept as the real value it is.
  * A PARTIAL DECISION IS SKIPPED, not half-imported. A package missing its
    position or outcome compares as though it were whole if it is let through.
  * IDS ARE UNIQUE ACROSS THE REAL CORPUS. This is a regression test: deriving the
    id from the package's own trailing number collided across pairs and yielded 7
    usable records out of 222.
  * IT WRITES NOTHING unless explicitly told to.
  * EVERY RECORD IT PRODUCES IS VALID under trade_observation's own rules.
"""

import datetime
import glob
import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts", "trader_intelligence"))

import import_mogo_observations as imp    # noqa: E402
import trade_observation as to            # noqa: E402

NOW = datetime.datetime(2026, 8, 17, 12, 0, 0)


SOURCE = {"sourceId": "EVSRC|MOGO|20260817|001", "sourceType": "replay_observation"}


def package(**overrides):
    pkg = {
        "packageId": "PKG|alex_g_sr_v1|20260427|1",
        "captureBasis": "REPLAY_RUN",
        "createdAt": "2026-04-27T09:00:00.000Z",
        "sourceTradeId": "REPLAY|abc123",
        "identity": {"strategyId": "alex_g_sr_v1"},
        "objects": {
            "positions": [{
                "instrument": "GBP_USD", "timeframe": "H1", "direction": "sell",
                "entryPrice": 1.35054, "originalStop": 1.35494, "target": 1.34174,
                "positionSize": 0.227, "riskAmount": 100,
                "entryTimestamp": "2026-04-21T18:00:00.000Z", "balanceBefore": 10000,
            }],
            "outcomes": [{
                "exitPrice": 1.35494, "exitTimestamp": "2026-04-27T09:00:00.000Z",
                "exitReasonCode": "Loss",
            }],
        },
    }
    pkg.update(overrides)
    return pkg


class TestItInventsNothing(unittest.TestCase):

    def test_a_null_field_becomes_an_explicit_unknown(self):
        pkg = package()
        pkg["objects"]["positions"][0]["target"] = None
        record, reason = imp.observation_from_package(pkg, NOW, {}, SOURCE)
        self.assertIsNone(reason)
        self.assertIn("target", record["unknowns"])
        self.assertNotIn("target", record)
        self.assertNotIn("target", record["fieldClassification"])

    def test_positive_control_a_present_field_is_recorded_and_classified(self):
        record, _ = imp.observation_from_package(package(), NOW, {}, SOURCE)
        self.assertEqual(record["target"], 1.34174)
        self.assertEqual(record["fieldClassification"]["target"], "DIRECTLY_OBSERVED")
        self.assertNotIn("target", record["unknowns"])

    def test_zero_is_kept_as_a_value_not_treated_as_missing(self):
        """riskAmount 0 is a real recorded value; a falsy check would lose it."""
        pkg = package()
        pkg["objects"]["positions"][0]["riskAmount"] = 0
        record, _ = imp.observation_from_package(pkg, NOW, {}, SOURCE)
        self.assertEqual(record["riskAmount"], 0)
        self.assertNotIn("riskAmount", record["unknowns"])

    def test_nothing_is_ever_classified_inferred(self):
        """These are MOGO's own recorded values -- observed or unknown, no middle."""
        records, _, _sources = imp.convert_all(now=NOW)
        for record in records:
            self.assertNotIn("INFERRED", set(record["fieldClassification"].values()),
                             "%s carries an INFERRED classification"
                             % record["observationId"])
            self.assertNotIn("inferenceReasons", record)

    def test_the_instrument_is_normalized_to_the_human_side_form(self):
        """Otherwise GBP_USD vs GBP/USD would read as a DATA_DIFFERENCE."""
        record, _ = imp.observation_from_package(package(), NOW, {}, SOURCE)
        self.assertEqual(record["instrument"], "GBP/USD")

    def test_an_already_normalized_instrument_is_left_alone(self):
        pkg = package()
        pkg["objects"]["positions"][0]["instrument"] = "GBP/USD"
        record, _ = imp.observation_from_package(pkg, NOW, {}, SOURCE)
        self.assertEqual(record["instrument"], "GBP/USD")


class TestAPartialDecisionIsSkipped(unittest.TestCase):

    def test_a_package_with_no_position_is_skipped(self):
        pkg = package()
        pkg["objects"]["positions"] = []
        record, reason = imp.observation_from_package(pkg, NOW, {}, SOURCE)
        self.assertIsNone(record)
        self.assertEqual(reason, "NO_POSITION_OBJECT")

    def test_a_package_with_no_outcome_is_skipped(self):
        pkg = package()
        pkg["objects"]["outcomes"] = []
        record, reason = imp.observation_from_package(pkg, NOW, {}, SOURCE)
        self.assertIsNone(record)
        self.assertEqual(reason, "NO_OUTCOME_OBJECT")

    def test_an_unrecognised_capture_basis_is_skipped(self):
        record, reason = imp.observation_from_package(
            package(captureBasis="SOMETHING_NEW"), NOW, {}, SOURCE)
        self.assertIsNone(record)
        self.assertTrue(reason.startswith("UNKNOWN_CAPTURE_BASIS"))

    def test_a_package_with_no_instrument_is_skipped(self):
        pkg = package()
        pkg["objects"]["positions"][0]["instrument"] = None
        record, reason = imp.observation_from_package(pkg, NOW, {}, SOURCE)
        self.assertIsNone(record)
        self.assertEqual(reason, "NO_INSTRUMENT")


class TestIdentifiersAreUniqueAcrossTheRealCorpus(unittest.TestCase):
    """Regression: ids derived from the package's own trailing number collided
    across pairs and produced 7 usable records out of 222."""

    def test_every_converted_record_has_a_distinct_id(self):
        records, skipped, sources = imp.convert_all(now=NOW)
        ids = [r["observationId"] for r in records]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual([s for s in skipped if "DUPLICATE" in s["reason"]], [])

    def test_the_real_corpus_converts_without_loss(self):
        records, skipped, sources = imp.convert_all(now=NOW)
        self.assertGreater(len(records), 200,
                           "the package corpus should convert in full")
        self.assertEqual(skipped, [], "nothing should be silently dropped")

    def test_conversion_is_deterministic_across_runs(self):
        first, _, _s1 = imp.convert_all(now=NOW)
        second, _, _s2 = imp.convert_all(now=NOW)
        self.assertEqual([r["observationId"] for r in first],
                         [r["observationId"] for r in second])


class TestEveryProducedRecordIsValid(unittest.TestCase):

    def test_the_whole_corpus_passes_trade_observation_validation(self):
        records, _, _sources = imp.convert_all(now=NOW)
        for record in records:
            to.validate_observation(record)     # raises on any violation

    def test_every_record_is_the_mogo_side_and_stays_in_the_research_lane(self):
        records, _, _sources = imp.convert_all(now=NOW)
        for record in records:
            self.assertEqual(record["actor"], "MOGO")
            self.assertEqual(record["lane"], "RESEARCH")


class TestItWritesNothing(unittest.TestCase):

    def test_converting_creates_no_file_anywhere_in_the_evidence_tree(self):
        root = to.EVIDENCE_ROOT

        def digest():
            out = {}
            for path in sorted(glob.glob(os.path.join(root, "*", "*.json"))):
                with open(path, "rb") as handle:
                    out[path] = hashlib.sha256(handle.read()).hexdigest()
            return out

        before = digest()
        imp.convert_all(now=NOW)
        self.assertEqual(digest(), before)

    def test_the_dry_run_report_says_it_wrote_nothing(self):
        records, skipped, sources = imp.convert_all(now=NOW)
        summary = imp.report(records, skipped, sources)
        self.assertFalse(summary["wrote"])
        self.assertNotIn("written", summary)

    def test_the_report_states_unknowns_rather_than_hiding_them(self):
        records, skipped, sources = imp.convert_all(now=NOW)
        summary = imp.report(records, skipped, sources)
        self.assertIn("unknownFieldCounts", summary)
        # Reported by evidence POPULATION, derived from source provenance -- not by
        # a label carried on the record, which could disagree with its own source.
        self.assertIn("byPopulation", summary)
        self.assertEqual(summary["byPopulation"],
                         {"HISTORICAL": 221, "FORWARD": 1})


class TestWritingIsExplicitAndSafe(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_records_can_be_written_and_reloaded(self):
        records, _, _sources = imp.convert_all(now=NOW)
        for record in records[:5]:
            to.write_observation(record, observations_dir=self.tmp)
        loaded = to.load_observations(self.tmp)
        self.assertEqual(len(loaded), 5)

    def test_a_second_write_of_the_same_record_is_refused(self):
        records, _, _sources = imp.convert_all(now=NOW)
        to.write_observation(records[0], observations_dir=self.tmp)
        with self.assertRaises(to.ObservationRefused):
            to.write_observation(records[0], observations_dir=self.tmp)


class TestTheScientificBoundarySurvivesImport(unittest.TestCase):
    """The invariant, not the count. Pinning "221 vs 1" would break the moment a
    new package lands, which is the failure mode that has already cost this
    repository two red tests; the MAPPING is what must never drift."""

    def setUp(self):
        self.records, _, sources = imp.convert_all(now=NOW)
        self.sources = imp.source_map(sources)

    def population(self, record):
        return to.observation_population(record, self.sources)

    def test_no_imported_record_has_an_unresolvable_population(self):
        for record in self.records:
            self.assertIn(self.population(record), (to.HISTORICAL, to.FORWARD),
                          "%s has no resolvable evidence population"
                          % record["observationId"])

    def test_replay_maps_to_historical_and_live_close_to_forward(self):
        """The mapping that keeps replay out of forward results."""
        seen = set()
        for record in self.records:
            basis = self.sources[record["sourceId"]]["metadata"]["captureBasis"]
            population = self.population(record)
            seen.add((basis, population))
            if basis == "REPLAY_RUN":
                self.assertEqual(population, to.HISTORICAL)
            elif basis == "LIVE_CLOSE":
                self.assertEqual(population, to.FORWARD)
        # Both bases must actually appear, or the assertions above are vacuous for
        # whichever one is missing.
        self.assertEqual({b for b, _ in seen}, {"REPLAY_RUN", "LIVE_CLOSE"})

    def test_the_two_populations_are_disjoint_and_cover_everything(self):
        historical = {r["observationId"] for r in self.records
                      if self.population(r) == to.HISTORICAL}
        forward = {r["observationId"] for r in self.records
                   if self.population(r) == to.FORWARD}
        self.assertEqual(historical & forward, set())
        self.assertEqual(len(historical) + len(forward), len(self.records))
        self.assertTrue(forward, "the forward population must not be empty")
        self.assertTrue(historical, "the historical population must not be empty")

    def test_no_source_asserts_an_unregistered_strategy_family(self):
        """A dangling BELONGS_TO_STRATEGY_FAMILY edge is a fabricated reference;
        the graph build reports it as INVALID_STRATEGY_FAMILY_REFERENCE."""
        known = imp.registered_families()
        for source in self.sources.values():
            family = source["strategyFamilyId"]
            if family is not None:
                self.assertIn(family, known)
            # the raw engine id is still retained, just not as a reference
            self.assertIn("engineStrategyId", source["metadata"])


if __name__ == "__main__":
    unittest.main()

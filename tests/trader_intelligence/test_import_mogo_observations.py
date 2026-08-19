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

# `skip_imported=False` in the mapping tests below: convert_all() is INCREMENTAL by
# default and the real corpus is already imported, so the default would correctly
# return zero records and every mapping assertion would pass vacuously. These tests
# are about the mapping; TestImportIsIncrementalAndAdditive covers the skipping.


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
        records, _, _sources = imp.convert_all(now=NOW, skip_imported=False)
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
        records, skipped, sources = imp.convert_all(now=NOW, skip_imported=False)
        ids = [r["observationId"] for r in records]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual([s for s in skipped if "DUPLICATE" in s["reason"]], [])

    def test_the_real_corpus_converts_without_loss(self):
        records, skipped, sources = imp.convert_all(now=NOW, skip_imported=False)
        self.assertGreater(len(records), 200,
                           "the package corpus should convert in full")
        # A skip is acceptable ONLY when it is a deliberate refusal. Asserting an
        # empty list stopped being right once developer TEST trades began being
        # refused -- but relaxing it to "any skip is fine" would hide a genuine
        # conversion loss, which is what this test exists to catch.
        unexpected = [x for x in skipped if x.get("reason") != "DEVELOPER_TEST_TRADE"]
        self.assertEqual(unexpected, [], "a package was dropped for a reason that is "
                                          "not a deliberate refusal")

    def test_conversion_is_deterministic_across_runs(self):
        first, _, _s1 = imp.convert_all(now=NOW, skip_imported=False)
        second, _, _s2 = imp.convert_all(now=NOW, skip_imported=False)
        self.assertEqual([r["observationId"] for r in first],
                         [r["observationId"] for r in second])


class TestEveryProducedRecordIsValid(unittest.TestCase):

    def test_the_whole_corpus_passes_trade_observation_validation(self):
        records, _, _sources = imp.convert_all(now=NOW, skip_imported=False)
        for record in records:
            to.validate_observation(record)     # raises on any violation

    def test_every_record_is_the_mogo_side_and_stays_in_the_research_lane(self):
        records, _, _sources = imp.convert_all(now=NOW, skip_imported=False)
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
        imp.convert_all(now=NOW, skip_imported=False)
        self.assertEqual(digest(), before)

    def test_the_dry_run_report_says_it_wrote_nothing(self):
        records, skipped, sources = imp.convert_all(now=NOW, skip_imported=False)
        summary = imp.report(records, skipped, sources)
        self.assertFalse(summary["wrote"])
        self.assertNotIn("written", summary)

    def test_the_report_states_unknowns_rather_than_hiding_them(self):
        records, skipped, sources = imp.convert_all(now=NOW, skip_imported=False)
        summary = imp.report(records, skipped, sources)
        self.assertIn("unknownFieldCounts", summary)
        # Reported by evidence POPULATION, derived from source provenance -- not by
        # a label carried on the record, which could disagree with its own source.
        self.assertIn("byPopulation", summary)
        # The INVARIANT, not the counts: both populations are present, they account
        # for every converted record, and nothing lands in UNKNOWN. Pinning "221/1"
        # would break the moment a forward close is imported -- which is exactly what
        # happened, and is normal operation rather than a regression.
        # Derived from what the corpus actually holds, not a pinned pair. A third
        # population (RECONSTRUCTED) arrived with the B-22 backfill; a fourth would
        # arrive the same way.
        self.assertTrue(set(summary["byPopulation"]).issubset(set(to.POPULATIONS)))
        self.assertNotIn(to.UNKNOWN_POPULATION, summary["byPopulation"])
        self.assertEqual(sum(summary["byPopulation"].values()), summary["converted"])


class TestWritingIsExplicitAndSafe(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_records_can_be_written_and_reloaded(self):
        records, _, _sources = imp.convert_all(now=NOW, skip_imported=False)
        for record in records[:5]:
            to.write_observation(record, observations_dir=self.tmp)
        loaded = to.load_observations(self.tmp)
        self.assertEqual(len(loaded), 5)

    def test_a_second_write_of_the_same_record_is_refused(self):
        records, _, _sources = imp.convert_all(now=NOW, skip_imported=False)
        to.write_observation(records[0], observations_dir=self.tmp)
        with self.assertRaises(to.ObservationRefused):
            to.write_observation(records[0], observations_dir=self.tmp)


class TestTheScientificBoundarySurvivesImport(unittest.TestCase):
    """The invariant, not the count. Pinning "221 vs 1" would break the moment a
    new package lands, which is the failure mode that has already cost this
    repository two red tests; the MAPPING is what must never drift."""

    def setUp(self):
        self.records, _, sources = imp.convert_all(now=NOW, skip_imported=False)
        self.sources = imp.source_map(sources)

    def population(self, record):
        return to.observation_population(record, self.sources)

    def test_no_imported_record_has_an_unresolvable_population(self):
        for record in self.records:
            self.assertNotEqual(self.population(record), to.UNKNOWN_POPULATION,
                          "%s has no resolvable evidence population"
                          % record["observationId"])

    def test_every_capture_basis_maps_to_its_own_population(self):
        """The mapping that keeps replay out of forward results -- and now keeps
        reconstructed evidence out of both.

        Was pinned to two bases. The B-22 backfill added HISTORICAL_BACKFILL, whose
        whole purpose is to be neither: a MINIMAL/UNSAFE_TO_RECONSTRUCT record filed
        as `paper_trade` would retroactively weaken every live-captured one.
        """
        expected = {"REPLAY_RUN": to.HISTORICAL,
                    "LIVE_CLOSE": to.FORWARD,
                    "HISTORICAL_BACKFILL": to.RECONSTRUCTED}
        seen = set()
        for record in self.records:
            basis = self.sources[record["sourceId"]]["metadata"]["captureBasis"]
            population = self.population(record)
            seen.add(basis)
            self.assertIn(basis, expected, "unmapped capture basis %r" % basis)
            self.assertEqual(population, expected[basis],
                             "%s (%s) landed in %s" % (record["observationId"], basis,
                                                        population))
        # Non-vacuity: assertions inside a loop prove nothing if the loop is thin.
        self.assertGreaterEqual(len(seen), 2,
                                "only %r present -- the mapping is barely exercised" % seen)
        self.assertEqual(len(set(expected[b] for b in seen)), len(seen),
                         "two capture bases share a population")

    def test_the_populations_are_disjoint_and_cover_everything(self):
        """Every record lands in exactly one population, and none is UNKNOWN.

        Was "the TWO populations". A third (RECONSTRUCTED) arrived with the B-22
        backfill, so the invariant is stated over whatever populations are present
        rather than over a pinned pair -- the count was never the point.
        """
        buckets = {}
        for record in self.records:
            buckets.setdefault(self.population(record), set()).add(record["observationId"])
        self.assertNotIn(to.UNKNOWN_POPULATION, buckets,
                         "a record has no resolvable population")
        self.assertGreaterEqual(len(buckets), 2,
                                "fewer than two populations -- disjointness would be vacuous")
        seen = set()
        for population, ids in buckets.items():
            self.assertEqual(seen & ids, set(), "%s overlaps another population" % population)
            seen |= ids
        self.assertEqual(len(seen), len(self.records), "a record was counted twice or not at all")
        self.assertTrue(buckets.get(to.FORWARD), "the forward population must not be empty")
        self.assertTrue(buckets.get(to.HISTORICAL), "the historical population must not be empty")

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


class TestImportIsIncrementalAndAdditive(unittest.TestCase):
    """A forward close mints a new package. It has to reach the observation corpus
    WITHOUT renumbering or rewriting the records already there."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_a_second_run_against_an_imported_corpus_converts_nothing(self):
        records, _, _s = imp.convert_all(now=NOW, observations_dir=self.tmp)
        for record in records:
            to.write_observation(record, observations_dir=self.tmp)
        again, skipped, _s2 = imp.convert_all(now=NOW, observations_dir=self.tmp)
        self.assertEqual(again, [], "a re-run must be a no-op, not a re-mint")
        unexpected = [x for x in skipped if x.get("reason") != "DEVELOPER_TEST_TRADE"]
        self.assertEqual(unexpected, [])

    def test_positive_control_the_first_run_is_not_empty(self):
        """Otherwise the idempotence test above would pass against a function that
        always returns nothing."""
        records, _, _s = imp.convert_all(now=NOW, observations_dir=self.tmp)
        self.assertGreater(len(records), 200)

    def test_an_already_imported_package_is_recognised_by_its_content_hash(self):
        # Keyed on contentHash, NOT packageId. See TestTheDeduplicationKeyIsGlobal
        # for why a package id cannot serve as the key.
        records, _, _s = imp.convert_all(now=NOW, observations_dir=self.tmp)
        to.write_observation(records[0], observations_dir=self.tmp)
        mapping = imp.already_imported(self.tmp)
        self.assertEqual(mapping[records[0]["sourceContentHash"]],
                         records[0]["observationId"])

    def test_a_partial_corpus_imports_only_what_is_missing(self):
        records, _, _s = imp.convert_all(now=NOW, observations_dir=self.tmp)
        for record in records[:10]:
            to.write_observation(record, observations_dir=self.tmp)
        remaining, _, _s2 = imp.convert_all(now=NOW, observations_dir=self.tmp)
        self.assertEqual(len(remaining), len(records) - 10)
        already = {r["sourcePackageId"] for r in records[:10]}
        self.assertEqual(already & {r["sourcePackageId"] for r in remaining}, set())

    def test_new_ids_continue_the_sequence_and_never_collide(self):
        records, _, _s = imp.convert_all(now=NOW, observations_dir=self.tmp)
        for record in records[:10]:
            to.write_observation(record, observations_dir=self.tmp)
        remaining, _, _s2 = imp.convert_all(now=NOW, observations_dir=self.tmp)
        written = {r["observationId"] for r in records[:10]}
        self.assertEqual(written & {r["observationId"] for r in remaining}, set(),
                         "a re-run must not reissue an id already on disk")

    def test_an_existing_source_is_reused_not_overwritten(self):
        _r, _s, sources = imp.convert_all(now=NOW, observations_dir=self.tmp)
        first = imp.write_sources(sources, sources_dir=self.tmp)
        self.assertTrue(first["written"])
        self.assertEqual(first["reused"], [])
        second = imp.write_sources(sources, sources_dir=self.tmp)
        self.assertEqual(second["written"], [])
        self.assertEqual(sorted(second["reused"]), sorted(first["written"]))

    def test_a_reused_source_file_is_byte_identical_afterwards(self):
        _r, _s, sources = imp.convert_all(now=NOW, observations_dir=self.tmp)
        imp.write_sources(sources, sources_dir=self.tmp)
        before = {p: hashlib.sha256(open(p, "rb").read()).hexdigest()
                  for p in glob.glob(os.path.join(self.tmp, "*.json"))}
        imp.write_sources(sources, sources_dir=self.tmp)
        after = {p: hashlib.sha256(open(p, "rb").read()).hexdigest()
                 for p in glob.glob(os.path.join(self.tmp, "*.json"))}
        self.assertEqual(after, before)


class TestTheDeduplicationKeyIsGlobal(unittest.TestCase):
    """REGRESSION. `packageId` is PKG|<strategy>|<date>|<ordinal> and the ordinal
    only counts within one capture run, so it is NOT a global primary key: 21 of the
    25 forward LIVE_CLOSE packages share a packageId with an unrelated REPLAY_RUN
    package. Keyed on packageId, the import reported those 21 as already-imported
    and silently dropped exactly the forward evidence it exists to preserve."""

    def test_package_ids_really_do_collide_across_capture_runs(self):
        """The precondition. If this ever stops holding, the regression below is
        no longer testing anything and should be re-examined, not deleted."""
        by_basis = {}
        for path in glob.glob(os.path.join(imp.REPO_ROOT, "evidence",
                                           "*-PACKAGES.json")):
            with open(path, "r", encoding="utf-8") as handle:
                for package in json.load(handle):
                    by_basis.setdefault(package["captureBasis"], set()).add(
                        package["packageId"])
        replay = by_basis.get("REPLAY_RUN", set())
        live = by_basis.get("LIVE_CLOSE", set())
        self.assertTrue(replay & live,
                        "expected packageId collisions across capture bases")

    def test_content_hash_is_unique_across_every_package(self):
        hashes = []
        for path in glob.glob(os.path.join(imp.REPO_ROOT, "evidence",
                                           "*-PACKAGES.json")):
            with open(path, "r", encoding="utf-8") as handle:
                hashes += [p["contentHash"] for p in json.load(handle)]
        self.assertEqual(len(hashes), len(set(hashes)))

    def test_already_imported_is_keyed_on_content_hash(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        records, _, _s = imp.convert_all(now=NOW, skip_imported=False,
                                         observations_dir=tmp)
        to.write_observation(records[0], observations_dir=tmp)
        mapping = imp.already_imported(tmp)
        self.assertIn(records[0]["sourceContentHash"], mapping)
        self.assertNotIn(records[0]["sourcePackageId"], mapping)

    def test_a_colliding_package_id_does_not_suppress_a_distinct_decision(self):
        """The bug, reproduced end to end: two packages sharing a packageId but
        carrying different content must both convert."""
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        records, _, _s = imp.convert_all(now=NOW, skip_imported=False,
                                         observations_dir=tmp)
        by_pkg = {}
        for record in records:
            by_pkg.setdefault(record["sourcePackageId"], []).append(record)
        shared = [v for v in by_pkg.values() if len(v) > 1]
        self.assertTrue(shared, "expected at least one shared packageId")
        for group in shared:
            hashes = {r["sourceContentHash"] for r in group}
            self.assertEqual(len(hashes), len(group),
                             "records sharing a packageId must differ by hash")

    def test_every_imported_record_carries_a_content_hash(self):
        records, _, _s = imp.convert_all(now=NOW, skip_imported=False)
        for record in records:
            self.assertTrue(record.get("sourceContentHash"),
                            "%s has no sourceContentHash" % record["observationId"])


class TestBackfillIsStrictlyAdditive(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_it_resolves_the_real_corpus_with_nothing_left_unresolved(self):
        result = imp.backfill_content_hashes()
        self.assertEqual(result["unresolved"], [])
        self.assertFalse(result["wrote"])

    def test_a_dry_run_changes_no_file(self):
        root = to.OBSERVATIONS_DIR

        def digest():
            return {p: hashlib.sha256(open(p, "rb").read()).hexdigest()
                    for p in sorted(glob.glob(os.path.join(root, "*.json")))}

        before = digest()
        imp.backfill_content_hashes()
        self.assertEqual(digest(), before)

    def test_a_record_that_cannot_be_resolved_is_left_alone_not_guessed(self):
        record = {"observationId": "TOBS|MOGO|20260101|001", "actor": "MOGO",
                  "sourceId": "EVSRC|GHOST|1", "instrument": "EUR/USD",
                  "sourcePackageId": "PKG|nope|1",
                  "fieldClassification": {"instrument": "DIRECTLY_OBSERVED"},
                  "unknowns": [], "extractedBy": "t", "lane": "RESEARCH",
                  "schemaVersion": to.SCHEMA_VERSION, "createdAt": "2026-01-01T00:00:00Z"}
        to.write_observation(record, observations_dir=self.tmp)
        result = imp.backfill_content_hashes(observations_dir=self.tmp, write=True)
        self.assertEqual(result["resolved"], 0)
        self.assertEqual(len(result["unresolved"]), 1)
        reloaded = to.load_observations(self.tmp)["TOBS|MOGO|20260101|001"]
        self.assertNotIn("sourceContentHash", reloaded)


class TestBackfillResolvesThroughItsOwnSource(unittest.TestCase):
    """Exercised on a purpose-built corpus. The live corpus now carries a hash on
    every record, so these code paths are unreachable there and a mutation to them
    would survive against real data alone."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.obs_dir = os.path.join(self.tmp, "observations")
        self.src_dir = os.path.join(self.tmp, "sources")
        os.makedirs(self.obs_dir)
        os.makedirs(self.src_dir)

    def _packages(self, name, content_hash, package_id="PKG|SHARED|1"):
        path = os.path.join(self.tmp, name)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump([{"packageId": package_id, "captureBasis": "REPLAY_RUN",
                        "contentHash": content_hash}], handle)
        return path

    def _source(self, source_id, path):
        record = {"sourceId": source_id, "sourceType": "replay_observation",
                  "repositoryPath": path, "contentHash": "x",
                  "registeredAt": "2026-01-01T00:00:00Z",
                  "storageLocationType": "repository",
                  "provenanceStatus": "verified", "lifecycleStatus": "registered",
                  "schemaVersion": 1, "createdAt": "2026-01-01T00:00:00Z",
                  "updatedAt": "2026-01-01T00:00:00Z"}
        with open(os.path.join(self.src_dir, source_id.replace("|", "_") + ".json"),
                  "w", encoding="utf-8") as handle:
            json.dump(record, handle)

    def _observation(self, source_id, package_id="PKG|SHARED|1"):
        record = {"observationId": "TOBS|MOGO|20260101|001", "actor": "MOGO",
                  "sourceId": source_id, "instrument": "EUR/USD",
                  "sourcePackageId": package_id,
                  "fieldClassification": {"instrument": "DIRECTLY_OBSERVED"},
                  "unknowns": [], "extractedBy": "t", "lane": "RESEARCH",
                  "schemaVersion": to.SCHEMA_VERSION,
                  "createdAt": "2026-01-01T00:00:00Z"}
        to.write_observation(record, observations_dir=self.obs_dir)

    def test_it_takes_the_hash_from_the_file_its_own_source_names(self):
        """Two files share a packageId with DIFFERENT content. A global search would
        take whichever sorts first; only the source-scoped lookup is correct."""
        self._packages("A-PACKAGES.json", "hash_from_A")
        second = self._packages("B-PACKAGES.json", "hash_from_B")
        self._source("EVSRC|MOGO|1", second)          # points at B, not A
        self._observation("EVSRC|MOGO|1")
        result = imp.backfill_content_hashes(observations_dir=self.obs_dir,
                                             sources_dir=self.src_dir, write=True)
        self.assertEqual(result["resolved"], 1)
        record = to.load_observations(self.obs_dir)["TOBS|MOGO|20260101|001"]
        self.assertEqual(record["sourceContentHash"], "hash_from_B")

    def test_a_package_with_no_hash_is_left_unresolved_not_written_as_null(self):
        path = self._packages("A-PACKAGES.json", None)
        self._source("EVSRC|MOGO|1", path)
        self._observation("EVSRC|MOGO|1")
        result = imp.backfill_content_hashes(observations_dir=self.obs_dir,
                                             sources_dir=self.src_dir, write=True)
        self.assertEqual(result["resolved"], 0)
        self.assertEqual(len(result["unresolved"]), 1)
        record = to.load_observations(self.obs_dir)["TOBS|MOGO|20260101|001"]
        self.assertNotIn("sourceContentHash", record)

    def test_backfill_adds_that_field_and_changes_nothing_else(self):
        path = self._packages("A-PACKAGES.json", "hash_from_A")
        self._source("EVSRC|MOGO|1", path)
        self._observation("EVSRC|MOGO|1")
        before = dict(to.load_observations(self.obs_dir)["TOBS|MOGO|20260101|001"])
        imp.backfill_content_hashes(observations_dir=self.obs_dir,
                                    sources_dir=self.src_dir, write=True)
        after = dict(to.load_observations(self.obs_dir)["TOBS|MOGO|20260101|001"])
        self.assertEqual(after.pop("sourceContentHash"), "hash_from_A")
        self.assertEqual(after, before, "backfill must be strictly additive")


class TestASourceIsNeverRepointed(unittest.TestCase):

    def test_reuse_is_refused_when_the_id_describes_a_different_artifact(self):
        """Source ids are positional. A file added earlier in sort order shifts
        them, and a blind reuse would repoint a source that observations cite."""
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        _r, _s, sources = imp.convert_all(now=NOW, skip_imported=False,
                                          observations_dir=tmp)
        imp.write_sources(sources, sources_dir=tmp)
        shifted = {}
        for key, source in sources.items():
            shifted[key] = dict(source, repositoryPath="evidence/SOMETHING-ELSE.json")
        with self.assertRaises(to.ObservationRefused):
            imp.write_sources(shifted, sources_dir=tmp)

    def test_positive_control_an_identical_source_reuses_cleanly(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        _r, _s, sources = imp.convert_all(now=NOW, skip_imported=False,
                                          observations_dir=tmp)
        imp.write_sources(sources, sources_dir=tmp)
        result = imp.write_sources(sources, sources_dir=tmp)
        self.assertEqual(result["written"], [])
        self.assertTrue(result["reused"])


class TestRealizedPerformanceIsObservedNotDerived(unittest.TestCase):
    """pnl / accountBalanceAfter / rMultiple are COPIED from the package. Deriving
    P&L from prices would convert an observed quantity into an inferred one, which
    is the conversion this subsystem exists to prevent."""

    def setUp(self):
        # Drive the MAPPING, not the corpus already on disk. Reading the written
        # records would assert stored state: every mutation of the importer below
        # survived that way, because the files do not change when the code does.
        records, _skipped, sources = imp.convert_all(now=NOW, skip_imported=False)
        self.records = records
        self.sources = imp.source_map(sources)

    def forward(self):
        return {r["observationId"]: r for r in self.records
                if to.observation_population(r, self.sources) == to.FORWARD}

    def historical(self):
        return {r["observationId"]: r for r in self.records
                if to.observation_population(r, self.sources) == to.HISTORICAL}

    def test_every_forward_record_carries_realized_pnl(self):
        self.assertTrue(self.forward())
        for record in self.forward().values():
            self.assertIsNotNone(record.get("pnl"),
                                 "%s has no pnl" % record["observationId"])
            self.assertEqual(record["fieldClassification"]["pnl"],
                             "DIRECTLY_OBSERVED")

    def test_replay_records_declare_pnl_unknown_rather_than_zero(self):
        """A replay produces no realized P&L. Recording 0 would make 221 losing
        trades look break-even in any aggregate."""
        self.assertTrue(self.historical())
        for record in self.historical().values():
            self.assertNotIn("pnl", record)
            self.assertIn("pnl", record.get("unknowns") or [])

    def test_r_multiple_is_recorded_from_the_observed_exit_not_the_plan(self):
        """`realizedR` carries realizedRProvenance OBSERVED_FROM_EXIT. `plannedR`
        is intent, not result, and must not be what lands here."""
        for record in self.records:
            self.assertIsNotNone(record.get("rMultiple"))
        planned = {2, 2.0}
        forward_r = {r["rMultiple"] for r in self.forward().values()}
        self.assertTrue(forward_r - planned,
                        "every rMultiple equals plannedR -- the plan was mapped, "
                        "not the realized result")


class TestTheWideningGuardActuallyGuards(unittest.TestCase):
    """_assert_widening_only is what makes the backfill safe to run against
    committed evidence. It is a pure function, so it is tested directly -- the live
    corpus is already backfilled, so no realistic run exercises its failure path."""

    BEFORE = {"observationId": "TOBS|MOGO|1", "entry": 1.2345, "outcome": "Win",
              "unknowns": ["pnl"],
              "fieldClassification": {"entry": "DIRECTLY_OBSERVED"}}

    def test_a_valid_widening_is_permitted(self):
        after = dict(self.BEFORE, pnl=10.0, unknowns=["pnl", "rMultiple"],
                     fieldClassification={"entry": "DIRECTLY_OBSERVED",
                                          "pnl": "DIRECTLY_OBSERVED"})
        imp._assert_widening_only("TOBS|MOGO|1", self.BEFORE, after)   # must not raise

    def test_changing_an_existing_value_is_refused(self):
        after = dict(self.BEFORE, entry=9.9999)
        with self.assertRaises(to.ObservationRefused):
            imp._assert_widening_only("TOBS|MOGO|1", self.BEFORE, after)

    def test_removing_a_key_is_refused(self):
        after = {k: v for k, v in self.BEFORE.items() if k != "outcome"}
        with self.assertRaises(to.ObservationRefused):
            imp._assert_widening_only("TOBS|MOGO|1", self.BEFORE, after)

    def test_shrinking_unknowns_is_refused(self):
        """An unknown silently disappearing is how a field that was never observed
        starts looking like one that was."""
        after = dict(self.BEFORE, unknowns=[])
        with self.assertRaises(to.ObservationRefused):
            imp._assert_widening_only("TOBS|MOGO|1", self.BEFORE, after)

    def test_changing_an_existing_classification_is_refused(self):
        after = dict(self.BEFORE,
                     fieldClassification={"entry": "INFERRED"})
        with self.assertRaises(to.ObservationRefused):
            imp._assert_widening_only("TOBS|MOGO|1", self.BEFORE, after)


class TestForwardEvidenceCoverageIsDisclosed(unittest.TestCase):
    """The forward population covers only the closes that minted a package. It is
    NOT the account's full history, and a performance figure computed from it must
    not be presented as the account's performance."""

    def test_the_balance_chain_has_gaps_and_that_is_expected(self):
        obs, sources = to.load_observations(), to.load_sources()
        forward = [r for r in to.select_population(obs, sources, to.FORWARD).values()
                   if r.get("strategyId") == "alex_g_sr_v1"]
        forward.sort(key=lambda r: r["closedAt"])
        breaks = [a["observationId"] for a, b in zip(forward, forward[1:])
                  if abs(a["accountBalanceAfter"] - b["accountBalanceBefore"]) > 0.005]
        # Documented, not asserted away: the packages cover a subset of the
        # account's closes (B-22 -- the oldest closes predate the evidence DB being
        # recreated), so the chain is expected to be discontinuous. Pinning this
        # stops a future reader treating the set as a complete account history.
        self.assertTrue(breaks,
                        "no gaps found -- if the package set became complete, the "
                        "coverage caveat in MOGO_022_TJR_EVIDENCE_REQUIREMENTS.md "
                        "and B-22 should be revisited rather than this test deleted")

    def test_balances_reconcile_once_concurrent_positions_are_accounted_for(self):
        """The forward evidence is internally consistent -- but NOT trade-by-trade.

        Two earlier drafts of this assertion were wrong, and both errors are worth
        keeping visible:

        1. It first pinned the live balance at 9756.23. That is a snapshot, not an
           invariant, and it broke within the hour when GBP/USD stopped out and the
           account moved to 9658.67 -- normal operation reported as a test failure.
        2. It then asserted balanceAfter == balanceBefore + pnl. That is false here:
           `balanceBefore` is stamped at ENTRY and `balanceAfter` at EXIT, and this
           account runs up to FIVE concurrent positions, so other trades closing in
           between move the balance. 12 of 26 records "failed" a rule that was never
           true.

        The real invariant, verified: the residual equals the summed P&L of the other
        preserved trades that closed inside this trade's lifetime. Anyone
        reconstructing an equity curve by chaining these fields trade-by-trade would
        get a wrong answer, which is why this is pinned rather than left implicit.
        """
        obs, sources = to.load_observations(), to.load_sources()
        forward = [r for r in to.select_population(obs, sources, to.FORWARD).values()
                   if None not in (r.get("accountBalanceBefore"),
                                   r.get("accountBalanceAfter"), r.get("pnl"))
                   and r.get("openedAt") and r.get("closedAt")]
        self.assertTrue(forward)
        earliest_close = min(r["closedAt"] for r in forward)

        checked = 0
        for record in forward:
            # Only trades whose whole lifetime lies inside the preserved window can
            # be reconciled: for anything opened before the first preserved close, an
            # UNPRESERVED earlier trade may have moved the balance (backlog B-22).
            if record["openedAt"] < earliest_close:
                continue
            residual = (record["accountBalanceAfter"]
                        - record["accountBalanceBefore"] - record["pnl"])
            contributors = [other["pnl"] for other in forward if other is not record
                            and record["openedAt"] < other["closedAt"]
                            < record["closedAt"]]
            concurrent = sum(contributors)
            # Each pnl is stored rounded to a cent, so a sum of k of them can drift
            # by up to half a cent per term. The tolerance scales with the number of
            # terms rather than being loosened globally -- one record here missed a
            # flat 2-place check by exactly 0.01 across 2 contributors. Real
            # corruption is orders of magnitude larger, and the mutation fixtures
            # (a 50.00 shift, a flipped sign) confirm this still discriminates.
            tolerance = 0.005 * (len(contributors) + 2)
            self.assertAlmostEqual(
                residual, concurrent, delta=tolerance,
                msg="%s: residual %.2f is not explained by concurrent closes %.2f "
                    "(%d contributors, tolerance %.3f)"
                    % (record["observationId"], residual, concurrent,
                       len(contributors), tolerance))
            checked += 1
        self.assertGreater(checked, 10,
                           "too few fully-covered trades to be meaningful")

    def test_the_account_really_does_run_concurrent_positions(self):
        """Precondition for the test above. If this became false, the simpler
        trade-by-trade rule would apply and the reconciliation above would be
        weaker than it looks."""
        obs, sources = to.load_observations(), to.load_sources()
        forward = [r for r in to.select_population(obs, sources, to.FORWARD).values()
                   if r.get("openedAt") and r.get("closedAt")]
        overlap = max(sum(1 for o in forward
                          if o["openedAt"] <= r["openedAt"] < o["closedAt"])
                      for r in forward)
        self.assertGreater(overlap, 1,
                           "no concurrent positions found; revisit the model")


if __name__ == "__main__":
    unittest.main()


class TestBackfillDoesNotContaminateForward(unittest.TestCase):
    """The capture-basis mapping is the contamination boundary (B-22).

    Lane A's review called this load-bearing: without a test here, changing
    HISTORICAL_BACKFILL's mapping to `paper_trade` is a one-character edit that
    silently merges reconstructed evidence into the genuine forward population,
    and every forward statistic afterwards is computed over a mixed set.

    Verified as a real gap: mutating that mapping killed nothing in
    test_trade_observation, because that module does not exercise the importer.
    """

    def test_backfill_maps_to_a_source_type_that_is_not_forward(self):
        source_type = imp.CAPTURE_BASIS_SOURCE_TYPE["HISTORICAL_BACKFILL"]
        self.assertNotIn(source_type, to.FORWARD_SOURCE_TYPES,
                         "HISTORICAL_BACKFILL maps to %r, which derives the FORWARD "
                         "population -- reconstructed evidence would be pooled with "
                         "live-captured evidence" % source_type)

    def test_backfill_derives_the_RECONSTRUCTED_population(self):
        source_type = imp.CAPTURE_BASIS_SOURCE_TYPE["HISTORICAL_BACKFILL"]
        population = to.observation_population(
            {"sourceId": "EVSRC|B|1"},
            {"EVSRC|B|1": {"sourceId": "EVSRC|B|1", "sourceType": source_type}})
        self.assertEqual(population, to.RECONSTRUCTED)

    def test_live_close_still_derives_FORWARD(self):
        """Positive control: the boundary test above must not pass merely because
        the mapping is broken in both directions."""
        source_type = imp.CAPTURE_BASIS_SOURCE_TYPE["LIVE_CLOSE"]
        population = to.observation_population(
            {"sourceId": "EVSRC|F|1"},
            {"EVSRC|F|1": {"sourceId": "EVSRC|F|1", "sourceType": source_type}})
        self.assertEqual(population, to.FORWARD)

    def test_every_capture_basis_maps_to_a_distinct_population(self):
        seen = {}
        for basis, source_type in imp.CAPTURE_BASIS_SOURCE_TYPE.items():
            population = to.observation_population(
                {"sourceId": "S"}, {"S": {"sourceId": "S", "sourceType": source_type}})
            self.assertNotEqual(population, to.UNKNOWN_POPULATION,
                                "%s maps to %r which derives no known population"
                                % (basis, source_type))
            seen[basis] = population
        self.assertEqual(len(set(seen.values())), len(seen),
                         "two capture bases share a population: %r" % seen)

    def test_an_unrecognised_basis_is_still_refused(self):
        self.assertNotIn("SOMETHING_NEW", imp.CAPTURE_BASIS_SOURCE_TYPE)


class TestDeveloperTradesAreNotEvidence(unittest.TestCase):
    """Synthetic Developer-Mode trades must never enter the research corpus.

    They travel the real paper-engine code path, so they mint real packages -- but
    they never observed a market. The B-22 backfill minted 13 packages, 4 of them
    `AGT|TEST|` developer trades, and the importer had no filter at the time.
    """

    NOW = datetime.datetime(2026, 8, 19, 0, 0, 0, tzinfo=datetime.timezone.utc)

    def package(self, **position_extra):
        position = {"instrument": "GBP_USD", "direction": "buy", "entryPrice": 1.0,
                    "originalStop": 0.99, "target": 1.02, "riskAmount": 100.0,
                    "balanceBefore": 10000.0}
        position.update(position_extra)
        return {"packageId": "PKG|s|20260713|1",
                "sourceTradeId": position_extra.pop("_tradeId", "AGT|GBP_USD|1"),
                "captureBasis": "HISTORICAL_BACKFILL", "contentHash": "h1",
                "objects": {"positions": [position],
                             "outcomes": [{"exitPrice": 0.99, "pnl": -100.0,
                                            "exitReasonCode": "Loss",
                                            "exitTimestamp": "2026-07-13T00:00:00.000Z",
                                            "balanceAfter": 9900.0, "realizedR": -1.0}]}}

    SOURCE = {"sourceId": "EVSRC|MOGO|20260819|001", "sourceType": "journal_entry"}

    def convert(self, package):
        return imp.observation_from_package(package, self.NOW, counters={},
                                             source=self.SOURCE)

    def test_isDeveloperTrade_is_refused(self):
        record, reason = self.convert(self.package(isDeveloperTrade=True))
        self.assertIsNone(record)
        self.assertEqual(reason, "DEVELOPER_TEST_TRADE")

    def test_tradeSource_TEST_is_refused(self):
        record, reason = self.convert(self.package(tradeSource="TEST"))
        self.assertIsNone(record)
        self.assertEqual(reason, "DEVELOPER_TEST_TRADE")

    def test_an_AGT_TEST_trade_id_is_refused(self):
        package = self.package()
        package["sourceTradeId"] = "AGT|TEST|1783897893481-42902"
        record, reason = self.convert(package)
        self.assertIsNone(record)
        self.assertEqual(reason, "DEVELOPER_TEST_TRADE")

    def test_each_marker_is_checked_independently(self):
        """Any one marker could be absent on an older record, so no single one may
        be load-bearing on its own."""
        for extra in ({"isDeveloperTrade": True}, {"tradeSource": "TEST"}):
            record, reason = self.convert(self.package(**extra))
            self.assertEqual(reason, "DEVELOPER_TEST_TRADE", "marker %r not checked" % extra)

    def test_a_REAL_trade_is_still_converted(self):
        """Positive control. Without it, the refusals above would pass against an
        importer that rejects everything."""
        record, reason = self.convert(self.package())
        self.assertIsNotNone(record, "a real trade was refused: %s" % reason)
        self.assertEqual(record["instrument"], "GBP/USD")

    def test_a_real_trade_with_the_flag_explicitly_false_is_converted(self):
        record, reason = self.convert(self.package(isDeveloperTrade=False,
                                                    tradeSource="LIVE"))
        self.assertIsNotNone(record, "refused a genuine trade: %s" % reason)


class TestTheTrueMarketExitIsPreserved(unittest.TestCase):
    """`closedAt` is when the close was RECORDED, not when the market filled.

    Every package in the store carries exitDetectionSource `historical_candle` --
    the exit was reconstructed on a re-walk. On 6 of 29 the recorded exit is more
    than an hour after the true one; the worst is 351.8 hours, turning a 216.1h
    holding period into an apparent 567.9h. The candle boundary was stated by the
    package all along and the corpus was discarding it.
    """

    NOW = datetime.datetime(2026, 8, 19, 0, 0, 0, tzinfo=datetime.timezone.utc)
    SOURCE = {"sourceId": "EVSRC|MOGO|20260819|001", "sourceType": "paper_trade"}

    def package(self, **outcome_extra):
        outcome = {"exitPrice": 0.99, "pnl": -100.0, "exitReasonCode": "Loss",
                   "exitTimestamp": "2026-08-17T12:56:08.675Z", "balanceAfter": 9900.0,
                   "realizedR": -1.0, "exitCandleEnd": 1785704940000,
                   "exitDetectionSource": "historical_candle"}
        outcome.update(outcome_extra)
        return {"packageId": "PKG|s|20260817|1", "sourceTradeId": "AGT|NZD_USD|1",
                "captureBasis": "LIVE_CLOSE", "contentHash": "h1",
                "objects": {"positions": [{"instrument": "NZD_USD", "direction": "sell",
                                            "entryPrice": 0.57, "originalStop": 0.59,
                                            "target": 0.55, "riskAmount": 100.0,
                                            "balanceBefore": 10000.0,
                                            "entryTimestamp": "2026-07-24T21:00:37.145Z"}],
                             "outcomes": [outcome]}}

    def convert(self, package):
        record, reason = imp.observation_from_package(package, self.NOW, counters={},
                                                       source=self.SOURCE)
        self.assertIsNotNone(record, "conversion refused: %s" % reason)
        return record

    def test_the_true_market_exit_is_recorded_as_ISO(self):
        record = self.convert(self.package())
        self.assertEqual(record["marketExitAt"], "2026-08-02T21:09:00.000Z")

    def test_it_is_distinct_from_closedAt_and_both_are_kept(self):
        """Neither corrects the other: closedAt is a real fact about when MOGO
        recorded the close, and marketExitAt is a real fact about the fill."""
        record = self.convert(self.package())
        self.assertEqual(record["closedAt"], "2026-08-17T12:56:08.675Z")
        self.assertNotEqual(record["marketExitAt"], record["closedAt"])

    def test_the_detection_source_is_recorded(self):
        self.assertEqual(self.convert(self.package())["exitDetectionSource"],
                         "historical_candle")

    def test_an_absent_candle_boundary_becomes_UNKNOWN_not_a_guess(self):
        record = self.convert(self.package(exitCandleEnd=None))
        self.assertIn("marketExitAt", record.get("unknowns") or [])
        self.assertNotIn("marketExitAt", record)

    def test_a_non_numeric_candle_boundary_becomes_UNKNOWN(self):
        for bad in ("2026-08-02", True, {}):
            record = self.convert(self.package(exitCandleEnd=bad))
            self.assertIn("marketExitAt", record.get("unknowns") or [],
                          "accepted %r" % (bad,))

    def test_the_conversion_and_backfill_paths_share_one_transformation(self):
        """The defect that made this necessary: the backfill read the package field
        raw, so it wrote 1785704940000.0 into marketExitAt on 258 records while the
        conversion path wrote ISO. Two mapping paths, one transformation."""
        raw = 1785704940000
        self.assertEqual(imp.map_outcome_value("marketExitAt", raw),
                         "2026-08-02T21:09:00.000Z")
        # A field with no transformation passes through untouched.
        self.assertEqual(imp.map_outcome_value("pnl", -100.0), -100.0)


class TestRecordedDurationIsNotAssumedToBeTheHoldingPeriod(unittest.TestCase):
    """A relation over the real corpus, asserted rather than a pinned count."""

    @classmethod
    def setUpClass(cls):
        cls.sources = to.load_sources()
        cls.observations = to.load_observations()

    def test_where_a_true_exit_exists_it_is_never_after_the_recorded_close(self):
        checked = 0
        for record in self.observations.values():
            market, closed = record.get("marketExitAt"), record.get("closedAt")
            if not (isinstance(market, str) and closed):
                continue
            self.assertLessEqual(market, closed,
                                 "%s: the market exit is AFTER the recorded close"
                                 % record["observationId"])
            checked += 1
        self.assertGreater(checked, 10, "too few records carry a true exit to be meaningful")

    def test_every_recorded_true_exit_is_an_ISO_timestamp(self):
        for record in self.observations.values():
            market = record.get("marketExitAt")
            if market is None:
                continue
            self.assertIsInstance(market, str,
                                  "%s carries a non-ISO market exit: %r"
                                  % (record["observationId"], market))
            self.assertTrue(market.endswith("Z"))


class TestTheBackfillPathAppliesTheSameTransformation(unittest.TestCase):
    """Drives backfill_mapped_fields itself, not the helper it should call.

    Testing `map_outcome_value` directly proves the helper works; it does NOT prove
    the backfill calls it. The backfill read the package field raw and wrote
    1785704940000.0 into `marketExitAt` on 258 records while the conversion path
    wrote ISO -- and a mutation reintroducing exactly that survived a suite that
    tested the helper. This is the test that fails when the paths diverge.
    """

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="mogo_backfill_")
        self.obs_dir = os.path.join(self.root, "observations")
        self.src_dir = os.path.join(self.root, "sources")
        os.makedirs(self.obs_dir)
        os.makedirs(self.src_dir)
        self.capture = os.path.join(REPO_ROOT, "evidence",
                                    "TEST-BACKFILL-%d-PACKAGES.json" % os.getpid())

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)
        if os.path.exists(self.capture):
            os.remove(self.capture)

    def test_a_backfilled_market_exit_is_ISO_not_raw_milliseconds(self):
        package = {"packageId": "PKG|s|20260817|9", "contentHash": "hbf1",
                   "captureBasis": "LIVE_CLOSE", "sourceTradeId": "AGT|X|9",
                   "objects": {"positions": [{"instrument": "NZD_USD"}],
                                "outcomes": [{"exitCandleEnd": 1785704940000,
                                               "exitDetectionSource": "historical_candle"}]}}
        with open(self.capture, "w", encoding="utf-8") as handle:
            json.dump([package], handle)
        rel = os.path.relpath(self.capture, REPO_ROOT)

        with open(os.path.join(self.src_dir, "EVSRC_MOGO_20260817_001.json"), "w",
                  encoding="utf-8") as handle:
            json.dump({"sourceId": "EVSRC|MOGO|20260817|001", "sourceType": "paper_trade",
                       "repositoryPath": rel, "contentHash": "irrelevant"}, handle)
        record = {"observationId": "TOBS|MOGO|20260817|900",
                  "sourceId": "EVSRC|MOGO|20260817|001",
                  "actor": "MOGO", "sourcePackageId": "PKG|s|20260817|9",
                  "sourceContentHash": "hbf1",
                  "schemaVersion": to.SCHEMA_VERSION, "lane": "RESEARCH",
                  "recordedAt": "2026-08-17T00:00:00Z", "extractedBy": "test-fixture",
                  "strategyId": "alex_g_sr_v1",
                  "instrument": "NZD/USD", "direction": "sell",
                  "fieldClassification": {"instrument": "DIRECTLY_OBSERVED",
                                           "direction": "DIRECTLY_OBSERVED"},
                  # marketExitAt deliberately NOT listed: the field did not exist
                  # when records like this were written, which is the situation the
                  # backfill exists for. An already-explicit UNKNOWN is a different
                  # case and is pinned separately below.
                  "unknowns": [f for f in to.OBSERVABLE_FIELDS
                                if f not in ("instrument", "direction", "marketExitAt")]}
        with open(os.path.join(self.obs_dir, "TOBS_MOGO_20260817_900.json"), "w",
                  encoding="utf-8") as handle:
            json.dump(record, handle)

        report = imp.backfill_mapped_fields(observations_dir=self.obs_dir,
                                             sources_dir=self.src_dir, write=True)
        self.assertEqual(report["unresolved"], [])
        with open(os.path.join(self.obs_dir, "TOBS_MOGO_20260817_900.json"),
                  encoding="utf-8") as handle:
            written = json.load(handle)
        self.assertEqual(written.get("marketExitAt"), "2026-08-02T21:09:00.000Z",
                         "the backfill path did not apply the epoch conversion")
        self.assertIsInstance(written.get("marketExitAt"), str)
        self.assertNotIn("marketExitAt", written.get("unknowns") or [],
                         "the field stayed UNKNOWN after being filled")


class TestAnExplicitUnknownIsNeverOverwritten(unittest.TestCase):
    """The widening rule cuts both ways.

    A field the record already declares UNKNOWN stays UNKNOWN. Filling it from a
    package later would silently convert a recorded absence into a value, which is
    the opposite of what "UNKNOWN remains UNKNOWN" means.
    """

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="mogo_bf_unknown_")
        self.obs_dir = os.path.join(self.root, "observations")
        self.src_dir = os.path.join(self.root, "sources")
        os.makedirs(self.obs_dir)
        os.makedirs(self.src_dir)
        self.capture = os.path.join(REPO_ROOT, "evidence",
                                    "TEST-UNKNOWN-%d-PACKAGES.json" % os.getpid())

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)
        if os.path.exists(self.capture):
            os.remove(self.capture)

    def test_a_declared_unknown_survives_a_backfill_that_could_fill_it(self):
        package = {"packageId": "PKG|s|20260817|8", "contentHash": "hbf2",
                   "captureBasis": "LIVE_CLOSE", "sourceTradeId": "AGT|X|8",
                   "objects": {"positions": [{"instrument": "NZD_USD"}],
                                "outcomes": [{"exitCandleEnd": 1785704940000}]}}
        with open(self.capture, "w", encoding="utf-8") as handle:
            json.dump([package], handle)
        with open(os.path.join(self.src_dir, "EVSRC_MOGO_20260817_002.json"), "w",
                  encoding="utf-8") as handle:
            json.dump({"sourceId": "EVSRC|MOGO|20260817|002", "sourceType": "paper_trade",
                       "repositoryPath": os.path.relpath(self.capture, REPO_ROOT),
                       "contentHash": "irrelevant"}, handle)
        record = {"observationId": "TOBS|MOGO|20260817|901",
                  "sourceId": "EVSRC|MOGO|20260817|002", "actor": "MOGO",
                  "sourcePackageId": "PKG|s|20260817|8", "sourceContentHash": "hbf2",
                  "schemaVersion": to.SCHEMA_VERSION, "lane": "RESEARCH",
                  "recordedAt": "2026-08-17T00:00:00Z", "strategyId": "alex_g_sr_v1",
                  "extractedBy": "test-fixture",
                  "instrument": "NZD/USD", "direction": "sell",
                  "fieldClassification": {"instrument": "DIRECTLY_OBSERVED",
                                           "direction": "DIRECTLY_OBSERVED"},
                  "unknowns": [f for f in to.OBSERVABLE_FIELDS
                                if f not in ("instrument", "direction")]}
        with open(os.path.join(self.obs_dir, "TOBS_MOGO_20260817_901.json"), "w",
                  encoding="utf-8") as handle:
            json.dump(record, handle)

        imp.backfill_mapped_fields(observations_dir=self.obs_dir,
                                    sources_dir=self.src_dir, write=True)
        with open(os.path.join(self.obs_dir, "TOBS_MOGO_20260817_901.json"),
                  encoding="utf-8") as handle:
            written = json.load(handle)
        self.assertIn("marketExitAt", written["unknowns"])
        self.assertNotIn("marketExitAt", {k: v for k, v in written.items()
                                           if k != "unknowns"})


class TestSourceIdentityFollowsTheArtifactNotThePosition(unittest.TestCase):
    """B-27. Ids were assigned by position in a sorted glob, so inserting or
    deleting any capture file shifted every id after it; write_sources then
    correctly refused to repoint a cited source and the whole import was blocked.
    That happened twice in one session -- once removing a duplicate artifact, once
    restoring it.
    """

    NOW = datetime.datetime(2026, 8, 19, 0, 0, 0, tzinfo=datetime.timezone.utc)

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="mogo_srcid_")
        self.pkg_dir = os.path.join(self.root, "packages")
        self.src_dir = os.path.join(self.root, "sources")
        os.makedirs(self.pkg_dir)
        os.makedirs(self.src_dir)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def write_capture(self, name, trade_id):
        package = {"packageId": "PKG|s|20260819|1", "sourceTradeId": trade_id,
                   "captureBasis": "LIVE_CLOSE", "contentHash": "h-" + trade_id,
                   "identity": {"strategyId": "alex_g_sr_v1"},
                   "objects": {"positions": [{"instrument": "GBP_USD"}],
                                "outcomes": [{}]}}
        with open(os.path.join(self.pkg_dir, name), "w", encoding="utf-8") as handle:
            json.dump([package], handle)

    def build(self):
        return imp.build_sources(self.NOW,
                                  package_glob=os.path.join(self.pkg_dir, "*.json"),
                                  sources_dir=self.src_dir)

    def persist(self, sources):
        imp.write_sources(sources, sources_dir=self.src_dir)

    def ids_by_path(self, sources):
        return {key[0]: value["sourceId"] for key, value in sources.items()}

    def test_inserting_a_file_that_sorts_FIRST_moves_no_existing_identity(self):
        self.write_capture("B-PACKAGES.json", "T-B")
        self.write_capture("C-PACKAGES.json", "T-C")
        before = self.ids_by_path(self.build())
        self.persist(self.build())

        self.write_capture("A-PACKAGES.json", "T-A")   # sorts before both
        after = self.ids_by_path(self.build())

        for path, source_id in before.items():
            self.assertEqual(after[path], source_id,
                             "%s changed identity because a file was inserted "
                             "before it" % path)
        new = set(after) - set(before)
        self.assertEqual(len(new), 1)
        self.assertNotIn(after[new.pop()], set(before.values()),
                         "the new artifact reused an existing id")

    def test_removing_a_file_moves_no_other_identity(self):
        for name, trade in (("A-PACKAGES.json", "T-A"), ("B-PACKAGES.json", "T-B"),
                            ("C-PACKAGES.json", "T-C")):
            self.write_capture(name, trade)
        before = self.ids_by_path(self.build())
        self.persist(self.build())

        os.remove(os.path.join(self.pkg_dir, "A-PACKAGES.json"))
        after = self.ids_by_path(self.build())

        for path, source_id in after.items():
            self.assertEqual(source_id, before[path],
                             "%s changed identity because another file was "
                             "removed" % path)

    def test_a_removed_file_can_be_restored_without_blocking_the_import(self):
        """The exact sequence that blocked the pipeline twice."""
        for name, trade in (("A-PACKAGES.json", "T-A"), ("B-PACKAGES.json", "T-B")):
            self.write_capture(name, trade)
        self.persist(self.build())
        original = self.ids_by_path(self.build())

        os.remove(os.path.join(self.pkg_dir, "A-PACKAGES.json"))
        self.persist(self.build())            # must not refuse
        self.write_capture("A-PACKAGES.json", "T-A")
        self.persist(self.build())            # must not refuse either

        self.assertEqual(self.ids_by_path(self.build()), original,
                         "identities did not survive a remove/restore cycle")

    def test_an_existing_recorded_source_is_reused_whatever_scheme_minted_it(self):
        """Backward compatibility. A source recorded under the old positional
        scheme keeps its id -- observations already cite it, and rewriting it would
        silently reinterpret preserved evidence."""
        self.write_capture("B-PACKAGES.json", "T-B")
        built = self.build()
        artifact = list(built.values())[0]
        legacy = dict(artifact)
        legacy["sourceId"] = "EVSRC|MOGO|20260101|042"
        with open(os.path.join(self.src_dir,
                               "EVSRC_MOGO_20260101_042.json"), "w",
                  encoding="utf-8") as handle:
            json.dump(legacy, handle)

        rebuilt = list(self.build().values())[0]
        self.assertEqual(rebuilt["sourceId"], "EVSRC|MOGO|20260101|042")

    def test_a_new_artifact_never_reuses_a_sequence_already_on_disk(self):
        self.write_capture("A-PACKAGES.json", "T-A")
        self.persist(self.build())
        first = list(self.build().values())[0]["sourceId"]

        self.write_capture("B-PACKAGES.json", "T-B")
        ids = {v["sourceId"] for v in self.build().values()}
        self.assertIn(first, ids)
        self.assertEqual(len(ids), 2, "the second artifact collided with the first")

    def test_two_new_artifacts_in_one_run_get_distinct_ids(self):
        self.write_capture("A-PACKAGES.json", "T-A")
        self.write_capture("B-PACKAGES.json", "T-B")
        ids = [v["sourceId"] for v in self.build().values()]
        self.assertEqual(len(ids), len(set(ids)))

    def test_the_real_corpus_mints_nothing_new(self):
        """Against the live corpus: every artifact already has a recorded id, so
        the migration changes no identity that any observation cites."""
        built = imp.build_sources(self.NOW)
        recorded = set()
        for path in glob.glob(os.path.join(
                REPO_ROOT, "docs", "trader-intelligence", "evidence", "sources", "*.json")):
            with open(path, encoding="utf-8") as handle:
                recorded.add(json.load(handle)["sourceId"])
        minted = {v["sourceId"] for v in built.values()} - recorded
        self.assertEqual(minted, set(),
                         "the migration would mint new ids for existing artifacts")


class TestTheTieBreakWhenOneArtifactHasSeveralRecords(unittest.TestCase):
    """15 of 30 live artifacts carry more than one recorded source (successive
    import generations), so the tie-break decides most identities in the corpus --
    and flipping it from min to max passed all 83 tests before these existed.
    """

    NOW = datetime.datetime(2026, 8, 19, 0, 0, 0, tzinfo=datetime.timezone.utc)

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="mogo_tiebreak_")
        self.pkg_dir = os.path.join(self.root, "packages")
        self.src_dir = os.path.join(self.root, "sources")
        self.obs_dir = os.path.join(self.root, "observations")
        for d in (self.pkg_dir, self.src_dir, self.obs_dir):
            os.makedirs(d)
        self.capture = os.path.join(self.pkg_dir, "A-PACKAGES.json")
        with open(self.capture, "w", encoding="utf-8") as handle:
            json.dump([{"packageId": "PKG|s|1", "sourceTradeId": "T-A",
                        "captureBasis": "LIVE_CLOSE", "contentHash": "h-A",
                        "identity": {"strategyId": "alex_g_sr_v1"},
                        "objects": {"positions": [{}], "outcomes": [{}]}}], handle)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def record_source(self, source_id, content_hash="FILLED"):
        built = list(self.build().values())[0]
        record = dict(built)
        record["sourceId"] = source_id
        if content_hash != "FILLED":
            record["contentHash"] = content_hash
        with open(os.path.join(self.src_dir,
                               source_id.replace("|", "_") + ".json"), "w",
                  encoding="utf-8") as handle:
            json.dump(record, handle)

    def record_observation(self, source_id):
        with open(os.path.join(self.obs_dir, "TOBS_X.json"), "w",
                  encoding="utf-8") as handle:
            json.dump({"observationId": "TOBS|MOGO|20260819|001",
                       "sourceId": source_id}, handle)

    def build(self):
        return imp.build_sources(self.NOW,
                                  package_glob=os.path.join(self.pkg_dir, "*.json"),
                                  sources_dir=self.src_dir,
                                  observations_dir=self.obs_dir)

    def resolved(self):
        return list(self.build().values())[0]["sourceId"]

    def test_the_id_an_observation_CITES_wins(self):
        """The migration's entire promise is that no citation moves."""
        self.record_source("EVSRC|MOGO|20260817|001")
        self.record_source("EVSRC|MOGO|20260819|009")
        self.record_observation("EVSRC|MOGO|20260819|009")
        self.assertEqual(self.resolved(), "EVSRC|MOGO|20260819|009")

    def test_without_a_citation_the_oldest_record_wins(self):
        self.record_source("EVSRC|MOGO|20260819|009")
        self.record_source("EVSRC|MOGO|20260817|001")
        self.assertEqual(self.resolved(), "EVSRC|MOGO|20260817|001")

    def test_sequences_are_compared_NUMERICALLY_not_as_strings(self):
        """A raw string minimum picks |1000 over |999, so "first writer wins" was
        false the moment a sequence reached four digits."""
        self.record_source("EVSRC|MOGO|20260819|999")
        self.record_source("EVSRC|MOGO|20260819|1000")
        self.assertEqual(self.resolved(), "EVSRC|MOGO|20260819|999")

    def test_a_foreign_trader_scope_never_hijacks_the_identity(self):
        """'EVSRC|ALEX_G|...' < 'EVSRC|MOGO|...' as a string, so a raw minimum
        handed the identity to another scope's record silently -- write_sources
        would not object, because the (path, type, hash) triple still matches."""
        # The foreign record is deliberately OLDER. With an earlier date it would
        # win on the date component alone, so only the scope component can save
        # the identity here -- an earlier fixture had the MOGO record older and so
        # never exercised the scope check at all.
        self.record_source("EVSRC|ALEX_G|20260101|001")
        self.record_source("EVSRC|MOGO|20260817|002")
        self.assertEqual(self.resolved(), "EVSRC|MOGO|20260817|002")

    def test_a_citation_outranks_even_an_older_record(self):
        self.record_source("EVSRC|MOGO|20260101|001")
        self.record_source("EVSRC|MOGO|20260819|050")
        self.record_observation("EVSRC|MOGO|20260819|050")
        self.assertEqual(self.resolved(), "EVSRC|MOGO|20260819|050")


class TestContentChangeAtTheSamePath(unittest.TestCase):
    """contentHash is load-bearing in the artifact key, not decoration."""

    NOW = datetime.datetime(2026, 8, 19, 0, 0, 0, tzinfo=datetime.timezone.utc)

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="mogo_contentchange_")
        self.pkg_dir = os.path.join(self.root, "packages")
        self.src_dir = os.path.join(self.root, "sources")
        os.makedirs(self.pkg_dir)
        os.makedirs(self.src_dir)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def write(self, trade_id):
        with open(os.path.join(self.pkg_dir, "A-PACKAGES.json"), "w",
                  encoding="utf-8") as handle:
            json.dump([{"packageId": "PKG|s|1", "sourceTradeId": trade_id,
                        "captureBasis": "LIVE_CLOSE", "contentHash": "h-" + trade_id,
                        "identity": {"strategyId": "alex_g_sr_v1"},
                        "objects": {"positions": [{}], "outcomes": [{}]}}], handle)

    def build(self):
        return imp.build_sources(self.NOW,
                                  package_glob=os.path.join(self.pkg_dir, "*.json"),
                                  sources_dir=self.src_dir)

    def test_different_content_at_the_same_path_gets_a_NEW_id(self):
        """Reusing the old id here would hand a recorded identity to different
        content; write_sources would then refuse and the import would be blocked --
        B-27's own failure mode arriving by another route."""
        self.write("T-A")
        first = list(self.build().values())[0]
        imp.write_sources(self.build(), sources_dir=self.src_dir)

        self.write("T-B")               # same path, different content
        second = list(self.build().values())[0]
        self.assertNotEqual(second["sourceId"], first["sourceId"])
        self.assertNotEqual(second["contentHash"], first["contentHash"])

    def test_identical_content_at_the_same_path_reuses_the_id(self):
        """Positive control: the check above must be caused by the content
        changing, not by rebuilding."""
        self.write("T-A")
        first = list(self.build().values())[0]
        imp.write_sources(self.build(), sources_dir=self.src_dir)
        self.assertEqual(list(self.build().values())[0]["sourceId"], first["sourceId"])


class TestCaptureBasisMappingIsInjective(unittest.TestCase):
    """`sources` is keyed by captureBasis; the lookup is keyed by sourceType.

    Correctness silently depends on the mapping being injective. If two bases ever
    shared a sourceType they would collapse onto one sourceId and source_map(),
    keyed by sourceId, would drop one group -- a non-idempotent import with no
    error. Not reachable today; nothing asserted it either.
    """

    def test_no_two_capture_bases_share_a_source_type(self):
        values = list(imp.CAPTURE_BASIS_SOURCE_TYPE.values())
        self.assertEqual(len(values), len(set(values)),
                         "two capture bases map to one sourceType: %r"
                         % imp.CAPTURE_BASIS_SOURCE_TYPE)


class TestObservationIdentityIsIndependentOfFileOrdering(unittest.TestCase):
    """B-29. Sequences are assigned in CONTENT order, not file-discovery order.

    The mechanism was already bounded -- contentHash-keyed dedup, counters
    continuing from the recorded maximum, and write_observation refusing to
    overwrite -- so no CITED identity could ever move. What was unguarded was which
    sequence two same-date pending packages received: reversing the package glob
    passed the entire suite before these existed.
    """

    NOW = datetime.datetime(2026, 8, 19, 0, 0, 0, tzinfo=datetime.timezone.utc)

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="mogo_obsid_")
        self.pkg_dir = os.path.join(self.root, "packages")
        self.obs_dir = os.path.join(self.root, "observations")
        self.src_dir = os.path.join(self.root, "sources")
        for d in (self.pkg_dir, self.obs_dir, self.src_dir):
            os.makedirs(d)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def package(self, tag, created="2026-08-19T00:00:00.000Z", basis="LIVE_CLOSE"):
        return {"packageId": "PKG|s|20260819|1", "sourceTradeId": "AGT|X|" + tag,
                "captureBasis": basis, "contentHash": "hash-" + tag,
                "createdAt": created, "identity": {"strategyId": "alex_g_sr_v1"},
                "objects": {"positions": [{"instrument": "GBP_USD", "direction": "buy",
                                            "entryPrice": 1.0, "originalStop": 0.99,
                                            "target": 1.02, "riskAmount": 100.0,
                                            "balanceBefore": 10000.0}],
                             "outcomes": [{"exitPrice": 0.99, "pnl": -100.0,
                                            "exitReasonCode": "Loss", "realizedR": -1.0,
                                            "exitTimestamp": "2026-08-19T01:00:00.000Z",
                                            "balanceAfter": 9900.0}]}}

    def write_capture(self, name, tags, **kw):
        with open(os.path.join(self.pkg_dir, name), "w", encoding="utf-8") as handle:
            json.dump([self.package(t, **kw) for t in tags], handle)

    def convert(self):
        records, skipped, _sources = imp.convert_all(
            package_glob=os.path.join(self.pkg_dir, "*.json"), now=self.NOW,
            observations_dir=self.obs_dir, sources_dir=self.src_dir)
        return {r["sourceContentHash"]: r["observationId"] for r in records}, skipped

    def convert_and_record(self):
        """Convert, then PERSIST -- which is what a real --write run does.

        Without persisting, every run re-mints the whole corpus from scratch, so a
        test can appear to show renumbering that `--write` can never produce. The
        invariant that matters is that a RECORDED identity never moves.
        """
        mapping, skipped = self.convert()
        for content_hash, observation_id in mapping.items():
            name = observation_id.replace("|", "_") + ".json"
            with open(os.path.join(self.obs_dir, name), "w", encoding="utf-8") as handle:
                json.dump({"observationId": observation_id,
                           "sourceContentHash": content_hash,
                           "sourceId": "EVSRC|MOGO|20260819|001"}, handle)
        return mapping, skipped

    # ---- ordering attacks -------------------------------------------------

    def test_reordering_files_changes_no_identity(self):
        """Renaming files to invert sort order must change nothing."""
        self.write_capture("A-PACKAGES.json", ["a"])
        self.write_capture("B-PACKAGES.json", ["b"])
        first, _ = self.convert()
        os.rename(os.path.join(self.pkg_dir, "A-PACKAGES.json"),
                  os.path.join(self.pkg_dir, "Z-PACKAGES.json"))
        second, _ = self.convert()
        self.assertEqual(first, second, "file order changed an observation identity")

    def test_inserting_a_file_that_sorts_first_moves_no_RECORDED_identity(self):
        self.write_capture("M-PACKAGES.json", ["m"])
        self.write_capture("N-PACKAGES.json", ["n"])
        before, _ = self.convert_and_record()
        self.write_capture("A-PACKAGES.json", ["a"])
        after, _ = self.convert()
        after = dict(before, **after)
        for content_hash, observation_id in before.items():
            self.assertEqual(after[content_hash], observation_id,
                             "inserting a file moved %s" % content_hash)

    def test_deleting_a_file_moves_no_RECORDED_identity(self):
        self.write_capture("A-PACKAGES.json", ["a"])
        self.write_capture("M-PACKAGES.json", ["m"])
        before, _ = self.convert_and_record()
        os.remove(os.path.join(self.pkg_dir, "A-PACKAGES.json"))
        after, _ = self.convert()
        # Everything was already recorded, so a re-run must convert nothing at all.
        self.assertEqual(after, {}, "a recorded observation was re-minted")
        recorded = {json.load(open(os.path.join(self.obs_dir, n)))["observationId"]
                    for n in os.listdir(self.obs_dir)}
        self.assertEqual(recorded, set(before.values()),
                         "a recorded identity changed when a file was deleted")

    def test_splitting_the_same_packages_across_different_files_changes_nothing(self):
        """Same content, different file layout."""
        self.write_capture("ONE-PACKAGES.json", ["a", "b", "c"])
        together, _ = self.convert()
        os.remove(os.path.join(self.pkg_dir, "ONE-PACKAGES.json"))
        self.write_capture("X-PACKAGES.json", ["c"])
        self.write_capture("Y-PACKAGES.json", ["a"])
        self.write_capture("Z-PACKAGES.json", ["b"])
        apart, _ = self.convert()
        self.assertEqual(together, apart)

    # ---- identity and dedup ----------------------------------------------

    def test_identical_content_in_two_files_yields_one_observation(self):
        self.write_capture("A-PACKAGES.json", ["dup"])
        self.write_capture("B-PACKAGES.json", ["dup"])
        records, skipped = self.convert()
        self.assertEqual(len(records), 1)
        self.assertTrue(any(s["reason"].startswith("DUPLICATE_CONTENT_HASH")
                            for s in skipped),
                        "one package's content was minted twice: %r" % skipped)

    def test_same_content_hash_different_source_file_is_still_one_observation(self):
        self.write_capture("A-PACKAGES.json", ["same"])
        self.write_capture("B-PACKAGES.json", ["same"])
        records, _ = self.convert()
        self.assertEqual(len(set(records.values())), 1)

    def test_every_identity_is_unique(self):
        self.write_capture("A-PACKAGES.json", ["a", "b", "c", "d"])
        records, _ = self.convert()
        self.assertEqual(len(set(records.values())), len(records))

    # ---- sequence boundaries ---------------------------------------------

    def test_sequences_pass_999_without_collision_or_truncation(self):
        prior = {}
        for n in range(1, 1002):
            prior["h%04d" % n] = "TOBS|MOGO|20260819|%03d" % n
        with open(os.path.join(self.obs_dir, "seed.json"), "w", encoding="utf-8") as h:
            json.dump({"observationId": "TOBS|MOGO|20260819|1001",
                       "sourceContentHash": "h1001", "sourceId": "EVSRC|MOGO|1"}, h)
        self.write_capture("A-PACKAGES.json", ["past999"])
        records, _ = self.convert()
        new_id = list(records.values())[0]
        self.assertEqual(new_id, "TOBS|MOGO|20260819|1002",
                         "the sequence did not continue past 999 correctly")

    # ---- population isolation --------------------------------------------

    def test_a_reconstructed_package_does_not_renumber_forward_ones(self):
        self.write_capture("A-PACKAGES.json", ["fwd1"])
        self.write_capture("B-PACKAGES.json", ["fwd2"])
        before, _ = self.convert()
        self.write_capture("AA-PACKAGES.json", ["recon"], basis="HISTORICAL_BACKFILL")
        after, _ = self.convert()
        for content_hash, observation_id in before.items():
            self.assertEqual(after[content_hash], observation_id,
                             "a reconstructed package renumbered forward evidence")

    # ---- idempotence / retry ---------------------------------------------

    def test_repeated_conversion_is_byte_identical(self):
        self.write_capture("A-PACKAGES.json", ["a", "b"])
        self.assertEqual(self.convert()[0], self.convert()[0])

    def test_an_already_recorded_observation_is_never_re_minted(self):
        self.write_capture("A-PACKAGES.json", ["a"])
        records, _ = self.convert()
        content_hash, observation_id = list(records.items())[0]
        with open(os.path.join(self.obs_dir, "rec.json"), "w", encoding="utf-8") as h:
            json.dump({"observationId": observation_id,
                       "sourceContentHash": content_hash, "sourceId": "EVSRC|MOGO|1"}, h)
        self.write_capture("B-PACKAGES.json", ["b"])
        again, _ = self.convert()
        self.assertNotIn(content_hash, again, "an already-recorded package was re-minted")
        self.assertNotIn(observation_id, set(again.values()),
                         "a recorded identity was reissued to different content")

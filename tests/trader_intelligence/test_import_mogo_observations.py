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
        self.assertEqual(skipped, [], "nothing should be silently dropped")

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
        self.assertEqual(set(summary["byPopulation"]), {"HISTORICAL", "FORWARD"})
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
        self.assertEqual(skipped, [])

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

    def test_the_most_recent_close_reconciles_with_the_live_account(self):
        """Cross-validation against state observed independently in the browser:
        the newest preserved close must land on the live balance."""
        obs, sources = to.load_observations(), to.load_sources()
        forward = [r for r in to.select_population(obs, sources, to.FORWARD).values()
                   if r.get("strategyId") == "alex_g_sr_v1"]
        latest = max(forward, key=lambda r: r["closedAt"])
        self.assertAlmostEqual(latest["accountBalanceAfter"], 9756.23, places=2)


if __name__ == "__main__":
    unittest.main()

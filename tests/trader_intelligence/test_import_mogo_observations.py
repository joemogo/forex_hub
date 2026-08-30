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
import inspect                            # noqa: E402
import validate_evidence as ve            # noqa: E402

imo = imp
FIXED_NOW = datetime.datetime(2026, 8, 21, tzinfo=datetime.timezone.utc)
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


# ─────────────────────────────────────────────────────────────────────────────
# THE SYNTHETIC CORPUS
#
# `evidence/*-PACKAGES.json` is OANDA-derived licensed capture data. It is not
# readable from a test process, and it never was a CONTRACT -- it was a
# convenient fixture that happened to contain every shape the importer maps.
# Reaching for it also made this module non-hermetic in the worst way: with the
# corpus unreadable `imp.convert_all()` returns an EMPTY list, so every loop-based
# assertion below passed vacuously and every "the corpus is fine" claim was a
# claim about nothing.
#
# The corpus is therefore built here: deterministic, hermetic, and shaped like the
# real one in exactly the ways the importer's contract depends on --
#
#   * three capture bases, so the population mapping is exercised end to end;
#   * REPLAY_RUN and LIVE_CLOSE packages IN ONE FILE, which is what makes a
#     file-level sourceType wrong and forces one source per (file, basis);
#   * packageIds deliberately COLLIDING across capture bases, which is the B-?? /
#     dedup regression this module exists to hold down;
#   * realized P&L present on LIVE_CLOSE and absent from REPLAY_RUN;
#   * developer TEST packages, which must be refused.
#
# The counts are derived from the builder, never pinned by hand: a package added
# below changes them without editing an assertion.
SYNTH_ROOT = None
SYNTH_GLOB = None
SYNTH_EMPTY = None
#: Every package written, converted or refused. Asserted, so a builder that
#: silently stopped writing files cannot make a refusal count look right.
SYNTH_PACKAGE_COUNT = 0
#: Packages the importer must refuse as developer TEST trades.
SYNTH_DEVELOPER_COUNT = 0
#: Packages the importer must convert. SYNTH_PACKAGE_COUNT - SYNTH_DEVELOPER_COUNT.
SYNTH_CONVERTIBLE = 0


def _synth_package(basis, date, ordinal, seq, *, instrument="GBP_USD",
                   pnl=None, balance_after=None, realized_r=-1.0,
                   trade_id=None, position_extra=None):
    """One deterministic package. `seq` is corpus-unique and fixes the contentHash."""
    position = {"instrument": instrument, "timeframe": "H1", "direction": "sell",
                "entryPrice": 1.35054, "originalStop": 1.35494, "target": 1.34174,
                "positionSize": 0.227, "riskAmount": 100.0,
                "entryTimestamp": "2026-04-21T18:00:00.000Z",
                "balanceBefore": 10000.0}
    position.update(position_extra or {})
    day = "%s-%s-%s" % (date[:4], date[4:6], date[6:])
    outcome = {"exitPrice": 1.35494,
               "exitTimestamp": "%sT09:00:00.000Z" % day,
               "exitCandleEnd": 1785704940000 + seq * 60000,
               "exitDetectionSource": "historical_candle",
               "exitReasonCode": "Loss",
               # realizedR is present on every package: `rMultiple` is mapped from
               # the OBSERVED exit on all of them, and a corpus where it were
               # sometimes absent would let the plan-vs-result test pass by
               # accident.
               "realizedR": realized_r}
    if pnl is not None:
        outcome["pnl"] = pnl
    if balance_after is not None:
        outcome["balanceAfter"] = balance_after
    return {"packageId": "PKG|alex_g_sr_v1|%s|%d" % (date, ordinal),
            "captureBasis": basis,
            "createdAt": "%sT%02d:00:00.000Z" % (day, seq % 24),
            "sourceTradeId": trade_id or "SYNTH|%s|%d" % (basis, seq),
            # Corpus-wide unique, which is what the dedup key relies on.
            "contentHash": "%064d" % seq,
            "identity": {"strategyId": "alex_g_sr_v1"},
            "objects": {"positions": [position], "outcomes": [outcome]}}


def _build_synthetic_corpus(root):
    """Write the corpus. Returns (total packages, developer packages)."""
    seq = 0
    developer = 0

    mixed = []
    for ordinal in range(1, 13):
        seq += 1
        mixed.append(_synth_package("REPLAY_RUN", "20260427", ordinal, seq))
    # The forward closes. Their packageIds 1..3 COLLIDE with the replay packages
    # above -- exactly the shape that made a packageId-keyed dedup drop 21 forward
    # records -- and they carry the realized performance a replay cannot have.
    for ordinal, realized in ((1, -1.0), (2, 1.7), (3, 0.5)):
        seq += 1
        mixed.append(_synth_package(
            "LIVE_CLOSE", "20260427", ordinal, seq, pnl=-100.0 * ordinal,
            balance_after=10000.0 - 100.0 * ordinal, realized_r=realized,
            trade_id="AGT|GBP_USD|%d" % ordinal))

    replay = []
    for ordinal in range(1, 11):
        seq += 1
        replay.append(_synth_package("REPLAY_RUN", "20260428", ordinal, seq,
                                     instrument="EUR_USD"))

    backfilled = []
    for ordinal in range(1, 4):
        seq += 1
        backfilled.append(_synth_package(
            "HISTORICAL_BACKFILL", "20260713", ordinal, seq, instrument="USD_JPY",
            pnl=-50.0, balance_after=9950.0))
    # Developer Mode test trades. One per marker, so a marker that stops being
    # refused fails here rather than silently shrinking the refused set.
    for ordinal, trade_id, extra in ((90, "AGT|TEST|1783897893481-42902", None),
                                     (91, None, {"isDeveloperTrade": True}),
                                     (92, None, {"tradeSource": "TEST"})):
        seq += 1
        developer += 1
        backfilled.append(_synth_package(
            "HISTORICAL_BACKFILL", "20260713", ordinal, seq,
            trade_id=trade_id, position_extra=extra))

    for name, body in (("C1-01-GBP_USD-PACKAGES.json", mixed),
                       ("C2-02-EUR_USD-PACKAGES.json", replay),
                       ("C3-03-BACKFILL-PACKAGES.json", backfilled)):
        with open(os.path.join(root, name), "w", encoding="utf-8") as handle:
            json.dump(body, handle)
    return seq, developer


def setUpModule():
    global SYNTH_ROOT, SYNTH_GLOB, SYNTH_EMPTY
    global SYNTH_PACKAGE_COUNT, SYNTH_DEVELOPER_COUNT, SYNTH_CONVERTIBLE
    SYNTH_ROOT = tempfile.mkdtemp(prefix="mogo_synth_corpus_")
    # Deliberately empty, and passed EXPLICITLY everywhere: with these defaulting
    # to None the importer would read the live docs/ corpus, and a test would be
    # asserting over whatever happens to be recorded today.
    SYNTH_EMPTY = os.path.join(SYNTH_ROOT, "empty")
    os.makedirs(SYNTH_EMPTY)
    SYNTH_PACKAGE_COUNT, SYNTH_DEVELOPER_COUNT = _build_synthetic_corpus(SYNTH_ROOT)
    SYNTH_CONVERTIBLE = SYNTH_PACKAGE_COUNT - SYNTH_DEVELOPER_COUNT
    SYNTH_GLOB = os.path.join(SYNTH_ROOT, "*-PACKAGES.json")


def tearDownModule():
    if SYNTH_ROOT:
        shutil.rmtree(SYNTH_ROOT, ignore_errors=True)


def convert_synthetic(now=NOW, skip_imported=False, observations_dir=None,
                      sources_dir=None):
    """`imp.convert_all` over the synthetic corpus. Same production function.

    Every directory argument is explicit, so nothing resolves against the live
    corpus and no run can be made to pass by what is already on disk.
    """
    return imp.convert_all(package_glob=SYNTH_GLOB, now=now,
                           skip_imported=skip_imported,
                           observations_dir=observations_dir or SYNTH_EMPTY,
                           sources_dir=sources_dir or SYNTH_EMPTY)


class TestTheSyntheticCorpusIsReal(unittest.TestCase):
    """The vacuity trap this whole module fell into once, closed explicitly.

    Every assertion below is over a corpus this file authors. If the builder wrote
    nothing, or `convert_all` returned early, the loops would pass in silence --
    which is precisely how the unreadable `evidence/` corpus turned this module
    green while proving nothing. Assert the fixture before trusting anything
    derived from it.
    """

    def test_the_corpus_files_were_written_and_hold_every_package(self):
        files = sorted(glob.glob(SYNTH_GLOB))
        self.assertEqual(len(files), 3, "the corpus builder wrote %r" % files)
        loaded = []
        for path in files:
            with open(path, "r", encoding="utf-8") as handle:
                loaded += json.load(handle)
        self.assertEqual(len(loaded), SYNTH_PACKAGE_COUNT)
        self.assertGreater(SYNTH_CONVERTIBLE, 10,
                           "too few convertible packages for the partial-import "
                           "and first-N tests below to mean anything")

    def test_every_package_is_accounted_for_as_converted_or_refused(self):
        records, skipped, _sources = convert_synthetic()
        self.assertEqual(len(records) + len(skipped), SYNTH_PACKAGE_COUNT,
                         "a package vanished; every count derived from this run "
                         "would then be a lie")
        self.assertEqual(len(records), SYNTH_CONVERTIBLE)
        self.assertEqual(sorted(x["reason"] for x in skipped),
                         ["DEVELOPER_TEST_TRADE"] * SYNTH_DEVELOPER_COUNT,
                         "a package was dropped for a reason that is not a "
                         "deliberate refusal")

    def test_the_corpus_carries_all_three_capture_bases(self):
        _r, _s, sources = convert_synthetic()
        bases = {s["metadata"]["captureBasis"] for s in sources.values()}
        self.assertEqual(bases, set(imp.CAPTURE_BASIS_SOURCE_TYPE),
                         "a capture basis is unexercised, so its mapping is "
                         "asserted by nothing")


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
        records, _, _sources = convert_synthetic()
        self.assertEqual(len(records), SYNTH_CONVERTIBLE, "nothing to check; vacuous")
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


class TestIdentifiersAreUniqueAcrossTheCorpus(unittest.TestCase):
    """Regression: ids derived from the package's own trailing number collided
    across pairs and produced 7 usable records out of 222.

    `test_the_real_corpus_converts_without_loss` used to live here. Its subject was
    the preserved OANDA-derived capture set, not the mapping, so it moved to
    tests/integration_real_evidence/. What the mapping owes -- every package
    accounted for, no unexplained loss -- is asserted over the synthetic corpus by
    TestTheSyntheticCorpusIsReal.
    """

    def test_every_converted_record_has_a_distinct_id(self):
        records, skipped, sources = convert_synthetic()
        ids = [r["observationId"] for r in records]
        self.assertEqual(len(ids), SYNTH_CONVERTIBLE, "nothing converted; vacuous")
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual([s for s in skipped if "DUPLICATE" in s["reason"]], [])

    def test_conversion_is_deterministic_across_runs(self):
        first, _, _s1 = convert_synthetic()
        second, _, _s2 = convert_synthetic()
        self.assertTrue(first, "nothing converted; the comparison is vacuous")
        self.assertEqual([r["observationId"] for r in first],
                         [r["observationId"] for r in second])


class TestEveryProducedRecordIsValid(unittest.TestCase):

    def test_the_whole_corpus_passes_trade_observation_validation(self):
        records, _, _sources = convert_synthetic()
        self.assertEqual(len(records), SYNTH_CONVERTIBLE, "nothing validated; vacuous")
        for record in records:
            to.validate_observation(record)     # raises on any violation

    def test_every_record_is_the_mogo_side_and_stays_in_the_research_lane(self):
        records, _, _sources = convert_synthetic()
        self.assertEqual(len(records), SYNTH_CONVERTIBLE, "nothing to check; vacuous")
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
        convert_synthetic()
        self.assertEqual(digest(), before)

    def test_the_dry_run_report_says_it_wrote_nothing(self):
        records, skipped, sources = convert_synthetic()
        self.assertTrue(records, "nothing converted; the report is empty and vacuous")
        summary = imp.report(records, skipped, sources)
        self.assertFalse(summary["wrote"])
        self.assertNotIn("written", summary)

    def test_the_report_states_unknowns_rather_than_hiding_them(self):
        records, skipped, sources = convert_synthetic()
        self.assertTrue(records, "nothing converted; the report is empty and vacuous")
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
        records, _, _sources = convert_synthetic()
        for record in records[:5]:
            to.write_observation(record, observations_dir=self.tmp)
        loaded = to.load_observations(self.tmp)
        self.assertEqual(len(loaded), 5)

    def test_a_second_write_of_the_same_record_is_refused(self):
        records, _, _sources = convert_synthetic()
        to.write_observation(records[0], observations_dir=self.tmp)
        with self.assertRaises(to.ObservationRefused):
            to.write_observation(records[0], observations_dir=self.tmp)


class TestTheScientificBoundarySurvivesImport(unittest.TestCase):
    """The invariant, not the count. Pinning "221 vs 1" would break the moment a
    new package lands, which is the failure mode that has already cost this
    repository two red tests; the MAPPING is what must never drift."""

    def setUp(self):
        self.records, _, sources = convert_synthetic()
        self.sources = imp.source_map(sources)
        # Every test in this class is a loop over `self.records`. An empty run
        # would make all of them pass in silence -- which is exactly what an
        # unreadable corpus used to do here.
        self.assertEqual(len(self.records), SYNTH_CONVERTIBLE,
                         "no records converted; every assertion below is vacuous")
        self.assertTrue(self.sources, "no sources; population lookup is vacuous")

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
        records, _, _s = convert_synthetic(skip_imported=True, observations_dir=self.tmp)
        for record in records:
            to.write_observation(record, observations_dir=self.tmp)
        again, skipped, _s2 = convert_synthetic(skip_imported=True, observations_dir=self.tmp)
        self.assertEqual(again, [], "a re-run must be a no-op, not a re-mint")
        unexpected = [x for x in skipped if x.get("reason") != "DEVELOPER_TEST_TRADE"]
        self.assertEqual(unexpected, [])

    def test_positive_control_the_first_run_is_not_empty(self):
        """Otherwise the idempotence test above would pass against a function that
        always returns nothing."""
        records, _, _s = convert_synthetic(skip_imported=True, observations_dir=self.tmp)
        self.assertEqual(len(records), SYNTH_CONVERTIBLE)
        self.assertGreater(len(records), 0)

    def test_an_already_imported_package_is_recognised_by_its_content_hash(self):
        # Keyed on contentHash, NOT packageId. See TestTheDeduplicationKeyIsGlobal
        # for why a package id cannot serve as the key.
        records, _, _s = convert_synthetic(skip_imported=True, observations_dir=self.tmp)
        to.write_observation(records[0], observations_dir=self.tmp)
        mapping = imp.already_imported(self.tmp)
        self.assertEqual(mapping[records[0]["sourceContentHash"]],
                         records[0]["observationId"])

    def test_a_partial_corpus_imports_only_what_is_missing(self):
        records, _, _s = convert_synthetic(skip_imported=True, observations_dir=self.tmp)
        for record in records[:10]:
            to.write_observation(record, observations_dir=self.tmp)
        remaining, _, _s2 = convert_synthetic(skip_imported=True, observations_dir=self.tmp)
        self.assertEqual(len(remaining), len(records) - 10)
        # Keyed on the CONTENT HASH, which is what `already_imported` keys on.
        # This asserted disjoint sourcePackageIds, which is a different and false
        # claim: a packageId's ordinal only counts within one capture run, so a
        # written record and a still-pending one legitimately share one. Against
        # the real corpus the two sets happened not to overlap for the first ten
        # records, so the wrong key passed by luck.
        already = {r["sourceContentHash"] for r in records[:10]}
        self.assertEqual(len(already), 10, "the written set collapsed; vacuous")
        self.assertEqual(already & {r["sourceContentHash"] for r in remaining}, set())

    def test_new_ids_continue_the_sequence_and_never_collide(self):
        records, _, _s = convert_synthetic(skip_imported=True, observations_dir=self.tmp)
        for record in records[:10]:
            to.write_observation(record, observations_dir=self.tmp)
        remaining, _, _s2 = convert_synthetic(skip_imported=True, observations_dir=self.tmp)
        written = {r["observationId"] for r in records[:10]}
        self.assertEqual(written & {r["observationId"] for r in remaining}, set(),
                         "a re-run must not reissue an id already on disk")

    def test_an_existing_source_is_reused_not_overwritten(self):
        _r, _s, sources = convert_synthetic(skip_imported=True, observations_dir=self.tmp)
        first = imp.write_sources(sources, sources_dir=self.tmp)
        self.assertTrue(first["written"])
        self.assertEqual(first["reused"], [])
        second = imp.write_sources(sources, sources_dir=self.tmp)
        self.assertEqual(second["written"], [])
        self.assertEqual(sorted(second["reused"]), sorted(first["written"]))

    def test_a_reused_source_file_is_byte_identical_afterwards(self):
        _r, _s, sources = convert_synthetic(skip_imported=True, observations_dir=self.tmp)
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
        """The precondition, over the corpus this module actually runs against.

        The same question asked of the PRESERVED capture set -- do real capture runs
        genuinely collide, and is every real contentHash unique -- is a property of
        that licensed data, not of the importer, and lives in
        tests/integration_real_evidence/.
        """
        by_basis = {}
        for path in glob.glob(SYNTH_GLOB):
            with open(path, "r", encoding="utf-8") as handle:
                for package in json.load(handle):
                    by_basis.setdefault(package["captureBasis"], set()).add(
                        package["packageId"])
        replay = by_basis.get("REPLAY_RUN", set())
        live = by_basis.get("LIVE_CLOSE", set())
        self.assertTrue(replay, "no REPLAY_RUN packages; the check is vacuous")
        self.assertTrue(live, "no LIVE_CLOSE packages; the check is vacuous")
        self.assertTrue(replay & live,
                        "expected packageId collisions across capture bases")

    def test_content_hash_is_unique_across_every_package(self):
        hashes = []
        for path in glob.glob(SYNTH_GLOB):
            with open(path, "r", encoding="utf-8") as handle:
                hashes += [p["contentHash"] for p in json.load(handle)]
        self.assertEqual(len(hashes), SYNTH_PACKAGE_COUNT, "no packages read; vacuous")
        self.assertEqual(len(hashes), len(set(hashes)))

    def test_already_imported_is_keyed_on_content_hash(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        records, _, _s = convert_synthetic(observations_dir=tmp)
        to.write_observation(records[0], observations_dir=tmp)
        mapping = imp.already_imported(tmp)
        self.assertIn(records[0]["sourceContentHash"], mapping)
        self.assertNotIn(records[0]["sourcePackageId"], mapping)

    def test_a_colliding_package_id_does_not_suppress_a_distinct_decision(self):
        """The bug, reproduced end to end: two packages sharing a packageId but
        carrying different content must both convert."""
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        records, _, _s = convert_synthetic(observations_dir=tmp)
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
        records, _, _s = convert_synthetic()
        self.assertEqual(len(records), SYNTH_CONVERTIBLE, "nothing to check; vacuous")
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
        _r, _s, sources = convert_synthetic(observations_dir=tmp)
        imp.write_sources(sources, sources_dir=tmp)
        shifted = {}
        for key, source in sources.items():
            shifted[key] = dict(source, repositoryPath="evidence/SOMETHING-ELSE.json")
        with self.assertRaises(to.ObservationRefused):
            imp.write_sources(shifted, sources_dir=tmp)

    def test_positive_control_an_identical_source_reuses_cleanly(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        _r, _s, sources = convert_synthetic(observations_dir=tmp)
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
        records, _skipped, sources = convert_synthetic()
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



class TestTheImporterMintsWhatTheWitnessWillCheck(unittest.TestCase):
    """The mapping that decides what a record SAYS was pinned by nothing.

    Five mutations of `POSITION_MAP`/`OUTCOME_MAP` survived the whole suite --
    `entry <- originalStop`, `exitPrice <- balanceAfter`,
    `accountBalanceBefore <- balanceAfter`, reading `positions[-1]` instead of
    `positions[0]`, and minting every record with `sequenceId = None`. The first
    mints a record whose entry equals its stop.

    None of them is a forgery bypass: the round-21 package witness catches the
    resulting records, and `UNANCHORED_OBSERVATION` catches the last. But that catch
    is downstream and conditional on the gitignored artifact surviving, and
    `forward_capture.sh` does not run the evidence validator -- so a mis-mapping
    importer would write corrupted forward evidence and the capture chain would exit
    0.

    The invariant, rather than five assertions: the importer's mapping for a field
    the witness compares MUST BE the pairing the witness compares it by. Two tables
    that must agree, checked against each other, so neither can be edited alone.
    """

    def maps(self):
        pairs = {}
        for record_field, package_field in imo.POSITION_MAP:
            pairs[("positions", record_field)] = package_field
        for record_field, package_field in imo.OUTCOME_MAP:
            pairs[("outcomes", record_field)] = package_field
        return pairs

    def test_the_two_tables_are_not_empty(self):
        self.assertGreater(len(imo.POSITION_MAP), 5)
        self.assertGreater(len(imo.OUTCOME_MAP), 3)
        self.assertGreater(len(ve.PACKAGE_WITNESSES), 5)

    def test_every_WITNESSED_field_is_minted_from_the_field_it_is_checked_against(self):
        pairs = self.maps()
        for witness in ve.PACKAGE_WITNESSES:
            with self.subTest(field=witness.record_field):
                key = (witness.object_kind, witness.record_field)
                self.assertIn(key, pairs,
                              "%s is compared against the package by the witness but "
                              "the importer never mints it from there"
                              % witness.record_field)
                self.assertEqual(
                    pairs[key], witness.package_field,
                    "the importer mints %s from %r while the witness checks it "
                    "against %r -- one of the two tables was edited alone, and a "
                    "record minted from the wrong field is wrong at birth"
                    % (witness.record_field, pairs[key], witness.package_field))

    def test_the_importer_reads_the_FIRST_position_and_outcome(self):
        # `positions[-1]` is identical on every well-formed package and differs only
        # where the package is ambiguous -- which is exactly where a guess is worst.
        source = inspect.getsource(imo)
        self.assertIn("positions[0], outcomes[0]", source)
        self.assertNotIn("positions[-1]", source)

    def test_a_package_with_TWO_positions_is_skipped_not_partially_imported(self):
        package = self.package()
        package["objects"]["positions"].append(
            dict(package["objects"]["positions"][0]))
        record, reason = imo.observation_from_package(package, FIXED_NOW, source=self.source())
        self.assertIsNone(record, "a partial import is a guess about which trade "
                                  "this package describes")
        self.assertIn("positions", reason)

    def test_POSITIVE_CONTROL_a_well_formed_package_still_converts(self):
        record, reason = imo.observation_from_package(self.package(), FIXED_NOW, source=self.source())
        self.assertIsNotNone(record, "reason=%r" % (reason,))

    def test_the_minted_record_carries_the_package_trade_id_as_its_sequenceId(self):
        # Minting `sequenceId = None` on every record survived the suite. It is
        # caught downstream by UNANCHORED_OBSERVATION, but the anchor should not be
        # the first thing to notice that the importer stopped recording identity.
        record, _reason = imo.observation_from_package(self.package(), FIXED_NOW, source=self.source())
        self.assertEqual(record.get("sequenceId"),
                         self.package().get("sourceTradeId"))

    def test_the_minted_record_agrees_with_its_own_package_under_the_WITNESS(self):
        # End to end: mint a record, then run the production witness against the
        # package it came from. This is the property all of the above serve.
        package = self.package()
        record, _reason = imo.observation_from_package(package, FIXED_NOW, source=self.source())
        findings = []
        ve.check_observation_matches_its_package(
            [dict(record, sourceContentHash=package["contentHash"],
                  sourceId="S1")],
            [{"sourceId": "S1", "repositoryPath": self.artifact(package)}],
            findings, FIXED_NOW)
        self.assertEqual([f["findingType"] for f in findings], [],
                         "the importer minted a record its own witness rejects")

    def artifact(self, package):
        path = os.path.join(self.tmp, "PACKAGES.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"packages": [package]}, handle)
        return path

    def source(self):
        return {"sourceId": "EVSRC|MOGO|20260801|001",
                "sourceType": "live_trade_review",
                "repositoryPath": os.path.join(self.tmp, "PACKAGES.json"),
                "metadata": {"engineStrategyId": "alex_g_sr_v1",
                             "captureBasis": "LIVE_CLOSE"}}

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="mogo_mintmap_")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def package(self):
        return {
            "packageId": "PKG|1", "sourceTradeId": "AGT|AGS|GBP_USD|1",
            "contentHash": "c" * 64, "captureBasis": "LIVE_CLOSE",
            "strategyId": "alex_g_sr_v1", "createdAt": "2026-08-01T00:00:00.000Z",
            "objects": {
                "positions": [{
                    "instrument": "GBP/USD", "timeframe": "H1", "direction": "buy",
                    "entryPrice": 1.2000, "originalStop": 1.1950, "target": 1.2100,
                    "positionSize": 10000, "riskAmount": 100.0,
                    "entryTimestamp": "2026-08-01T00:00:00.000Z",
                    "balanceBefore": 10000.0}],
                "outcomes": [{
                    "exitPrice": 1.2100, "exitTimestamp": "2026-08-01T05:00:00.000Z",
                    "exitCandleEnd": 1785000000000,
                    "exitDetectionSource": "historical_candle",
                    "balanceAfter": 10200.0, "pnl": 200.0, "realizedR": 2.0}],
            },
        }

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
        # NOT under `evidence/`. That directory holds OANDA-derived licensed
        # capture data and a test has no business writing into it; the backfill
        # resolves `repositoryPath` through os.path.join(REPO_ROOT, rel), which
        # returns an absolute path unchanged, so a temp artifact works identically.
        self.capture = os.path.join(self.root, "TEST-BACKFILL-PACKAGES.json")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_a_backfilled_market_exit_is_ISO_not_raw_milliseconds(self):
        package = {"packageId": "PKG|s|20260817|9", "contentHash": "hbf1",
                   "captureBasis": "LIVE_CLOSE", "sourceTradeId": "AGT|X|9",
                   "objects": {"positions": [{"instrument": "NZD_USD"}],
                                "outcomes": [{"exitCandleEnd": 1785704940000,
                                               "exitDetectionSource": "historical_candle"}]}}
        with open(self.capture, "w", encoding="utf-8") as handle:
            json.dump([package], handle)
        rel = self.capture

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
        # See TestTheBackfillPathAppliesTheSameTransformation: the artifact lives
        # in the temp root, never in the restricted `evidence/` tree.
        self.capture = os.path.join(self.root, "TEST-UNKNOWN-PACKAGES.json")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

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
                       "repositoryPath": self.capture,
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

    # `test_the_real_corpus_mints_nothing_new` moved to
    # tests/integration_real_evidence/: it asks whether the B-27 migration would
    # renumber the PRESERVED artifacts, which can only be answered against the
    # licensed capture set. Run against an unreadable `evidence/` it built zero
    # sources and minted zero ids, so it passed while checking nothing.


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


class TestRefusedDeveloperPackagesProduceZeroObservationsAtCorpusLevel(unittest.TestCase):
    """The refusal, asserted over a whole synthetic CORPUS rather than one package.

    TestDeveloperTradesAreNotEvidence proves `observation_from_package` returns None for
    each developer marker. That is a per-package claim, and it is not the claim the corpus
    actually depends on: what matters is that after a full `convert_all` run over a package
    set containing developer trades, NOTHING derived from them is in the records -- not an
    observation, not a sequence number, not a source citation. A per-package refusal that
    the corpus loop then routed around would satisfy every existing fixture.

    This is the shape of the real event. The B-22 backfill minted 13 packages, 4 of them
    `AGT|TEST|` developer trades, and the importer had no filter at the time. The live
    corpus today reports exactly 4 identities flagged `refusedByImportPolicy` and 0
    observations derived from them -- but that is a MEASUREMENT of production data, not a
    test, and it cannot fail in CI. These fixtures are synthetic and deterministic, and no
    OANDA-derived artifact is opened, copied or read.

    The vacuity traps are explicit. A corpus-level refusal test passes trivially if the
    package set never loaded, if every package was skipped for an unrelated reason, or if
    `convert_all` returned early -- so the fixture count, the real-package count and the
    refusal count are all asserted, and a positive control proves non-developer packages
    from the SAME run are still converted.
    """

    NOW = datetime.datetime(2026, 8, 19, 0, 0, 0, tzinfo=datetime.timezone.utc)

    #: The four developer markers, one per refused package. Kept as a table so a marker
    #: that stops being refused fails HERE rather than silently shrinking the refused set.
    DEVELOPER_MARKERS = (
        ("isDeveloperTrade flag", {"isDeveloperTrade": True}, "AGT|GBP_USD|d1"),
        ("tradeSource TEST", {"tradeSource": "TEST"}, "AGT|GBP_USD|d2"),
        ("AGT|TEST| trade id", {}, "AGT|TEST|1783897893481-42902"),
        ("AGT|TEST| trade id, second", {}, "AGT|TEST|1783897893482-42903"),
    )
    REAL_TRADE_IDS = ("AGT|GBP_USD|r1", "AGT|EUR_USD|r2", "AGT|USD_JPY|r3")

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="mogo_devrefusal_")
        self.pkg_dir = os.path.join(self.root, "packages")
        self.obs_dir = os.path.join(self.root, "observations")
        self.src_dir = os.path.join(self.root, "sources")
        for directory in (self.pkg_dir, self.obs_dir, self.src_dir):
            os.makedirs(directory)
        self.packages = self.build_corpus()
        with open(os.path.join(self.pkg_dir, "SYNTHETIC-PACKAGES.json"), "w",
                  encoding="utf-8") as handle:
            json.dump(self.packages, handle)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def make_package(self, trade_id, index, **position_extra):
        position = {"instrument": "GBP_USD", "timeframe": "H1", "direction": "buy",
                    "entryPrice": 1.30, "originalStop": 1.29, "target": 1.32,
                    "positionSize": 0.1, "riskAmount": 100.0, "balanceBefore": 10000.0,
                    "entryTimestamp": "2026-07-13T00:00:00.000Z"}
        position.update(position_extra)
        return {"packageId": "PKG|alex_g_sr_v1|20260713|%d" % index,
                "captureBasis": "HISTORICAL_BACKFILL",
                "createdAt": "2026-07-13T00:00:00.000Z",
                "sourceTradeId": trade_id,
                "contentHash": "hash-%d" % index,
                "identity": {"strategyId": "alex_g_sr_v1"},
                "objects": {"positions": [position],
                            "outcomes": [{"exitPrice": 1.29, "pnl": -100.0,
                                          "exitReasonCode": "Loss",
                                          "exitTimestamp": "2026-07-13T04:00:00.000Z",
                                          "balanceAfter": 9900.0, "realizedR": -1.0}]}}

    def build_corpus(self):
        packages, index = [], 0
        for _label, extra, trade_id in self.DEVELOPER_MARKERS:
            index += 1
            packages.append(self.make_package(trade_id, index, **extra))
        for trade_id in self.REAL_TRADE_IDS:
            index += 1
            packages.append(self.make_package(trade_id, index))
        return packages

    def convert(self):
        return imp.convert_all(
            package_glob=os.path.join(self.pkg_dir, "*.json"), now=self.NOW,
            skip_imported=False, observations_dir=self.obs_dir,
            sources_dir=self.src_dir)

    # ── the fixture itself must be real ─────────────────────────────────────────────────
    def test_the_synthetic_corpus_actually_loaded(self):
        # The trap this whole class exists inside: zero developer observations is also what
        # an EMPTY run produces. Assert the corpus is real before asserting anything about
        # what it refused.
        self.assertEqual(len(self.packages), 7)
        records, skipped, _sources = self.convert()
        self.assertEqual(len(records) + len(skipped), 7,
                         "every synthetic package must be accounted for as converted or "
                         "skipped; a package that vanished makes the refusal count a lie")

    def test_POSITIVE_CONTROL_the_real_packages_in_the_SAME_run_are_converted(self):
        # Without this, a convert_all that refused EVERYTHING would satisfy every refusal
        # assertion below while destroying the corpus.
        records, _skipped, _sources = self.convert()
        self.assertEqual(len(records), len(self.REAL_TRADE_IDS))
        self.assertTrue(records, "the positive control collected nothing")

    # ── the refusal, at corpus level ────────────────────────────────────────────────────
    def test_all_four_developer_packages_are_refused(self):
        _records, skipped, _sources = self.convert()
        refused = [s for s in skipped if s["reason"] == "DEVELOPER_TEST_TRADE"]
        self.assertEqual(len(refused), 4,
                         "expected exactly the four developer packages to be refused, got "
                         + repr([s["packageId"] for s in refused]))

    def test_each_developer_MARKER_is_refused_individually(self):
        # Table-driven, so a marker that stops being refused fails here rather than being
        # absorbed by the other three still failing closed.
        _records, skipped, _sources = self.convert()
        refused_ids = {s["packageId"] for s in skipped
                       if s["reason"] == "DEVELOPER_TEST_TRADE"}
        for index, (label, _extra, _trade_id) in enumerate(self.DEVELOPER_MARKERS, start=1):
            with self.subTest(marker=label):
                self.assertIn("PKG|alex_g_sr_v1|20260713|%d" % index, refused_ids)

    def test_the_refused_packages_produce_ZERO_observations(self):
        records, _skipped, _sources = self.convert()
        developer_ids = {trade_id for _l, _e, trade_id in self.DEVELOPER_MARKERS}
        # `sequenceId` is where a record carries its originating trade id. Asserted to be
        # PRESENT first: the first draft of this filtered on `sourceTradeId`, which records
        # do not have, so `r.get(...)` was None for every record and the assertion passed
        # over an empty list -- the exact vacuous pass this class is written against.
        self.assertTrue(records, "no records to check")
        for record in records:
            self.assertIn("sequenceId", record,
                          "the field this refusal is asserted on must exist")
        self.assertEqual(
            [r for r in records if r["sequenceId"] in developer_ids], [],
            "a developer trade reached the records")

    def test_no_AGT_TEST_identity_appears_ANYWHERE_in_the_records(self):
        # Indirect entry: not the sourceTradeId field alone, but the serialized record. A
        # refused trade must not survive as a citation, a provenance note or an id fragment.
        records, _skipped, _sources = self.convert()
        blob = json.dumps(records)
        self.assertNotIn("AGT|TEST|", blob)
        for _label, _extra, trade_id in self.DEVELOPER_MARKERS:
            self.assertNotIn(trade_id, blob, "%s survived into the records" % trade_id)

    def test_the_refused_packages_consume_no_observation_SEQUENCE_number(self):
        # A refused package that still incremented the counter would leave a permanent gap
        # in the corpus numbering -- evidence of a trade that must not be evidenced.
        records, _skipped, _sources = self.convert()
        sequences = sorted(int(r["observationId"].split("|")[3]) for r in records)
        self.assertEqual(sequences, list(range(1, len(self.REAL_TRADE_IDS) + 1)),
                         "sequence numbers must be contiguous from 1; a gap means a "
                         "refused package was numbered before being discarded")

    def test_every_surviving_record_is_one_of_the_REAL_trades(self):
        records, _skipped, _sources = self.convert()
        self.assertEqual(sorted(r["sequenceId"] for r in records),
                         sorted(self.REAL_TRADE_IDS))

    def test_a_corpus_of_ONLY_developer_packages_yields_no_records_and_no_error(self):
        # The degenerate case, and the one whose "0 observations" is honest rather than
        # vacuous: every package present, every one refused, nothing raised.
        only_developer = [p for p in self.packages
                          if p["sourceTradeId"] not in self.REAL_TRADE_IDS]
        self.assertEqual(len(only_developer), 4)
        with open(os.path.join(self.pkg_dir, "SYNTHETIC-PACKAGES.json"), "w",
                  encoding="utf-8") as handle:
            json.dump(only_developer, handle)
        records, skipped, _sources = self.convert()
        self.assertEqual(records, [])
        self.assertEqual(len(skipped), 4)
        self.assertEqual({s["reason"] for s in skipped}, {"DEVELOPER_TEST_TRADE"})

    def test_the_refusal_predicate_agrees_with_the_corpus_outcome(self):
        # Ties the unit-level predicate to the corpus-level result, so the two cannot drift
        # into disagreeing about which packages are developer trades.
        _records, skipped, _sources = self.convert()
        refused_ids = {s["packageId"] for s in skipped
                       if s["reason"] == "DEVELOPER_TEST_TRADE"}
        predicate_ids = {p["packageId"] for p in self.packages
                         if imp.is_developer_test_package(p)}
        self.assertEqual(refused_ids, predicate_ids)
        self.assertEqual(len(predicate_ids), 4)

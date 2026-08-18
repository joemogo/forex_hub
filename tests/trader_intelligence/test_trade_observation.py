#!/usr/bin/env python3
"""TradeObservation -- MOGO-019 gap 2.

The properties under test are the ones that make a screenshot usable as evidence
rather than as a story about a screenshot:

  * ONE SHAPE, TWO ACTORS. A human trade and a MOGO decision are the same record
    type, distinguishable by `actor` and by identifier, so a comparison compares
    decisions rather than schemas.
  * NOTHING RECORDED IS UNCLASSIFIED, and nothing classified is unrecorded.
  * KNOWN XOR UNKNOWN. Never both, never neither.
  * AN INFERENCE MUST SAY WHY. An inference that cannot is refused, so it can
    never come to sit where a source-stated fact would.
  * ABSENT IS NOT ZERO. A missing stop is unknown; 0.0 is a real value.

Every refusal test below is paired with a POSITIVE CONTROL -- the same record
with only the offending detail corrected must be accepted. A test that only ever
asserts a refusal cannot tell a working guard from a function that refuses
everything.
"""

import datetime
import os
import shutil
import sys
import tempfile
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts", "trader_intelligence"))

import trade_observation as to      # noqa: E402
import evidence_common as ec        # noqa: E402

NOW = datetime.datetime(2026, 8, 17, 12, 0, 0)


def base(**overrides):
    """A minimal VALID human observation. Overrides are applied last."""
    record = {
        "observationId": "TOBS|HUMAN|20260817|001",
        "actor": "HUMAN",
        "sourceId": "EVSRC|TJR|20260817|001",
        "instrument": "EUR/USD",
        "entry": 1.0840,
        "stop": 1.0820,
        "direction": "long",
        "fieldClassification": {
            "instrument": "DIRECTLY_OBSERVED",
            "entry": "DIRECTLY_OBSERVED",
            "stop": "DIRECTLY_OBSERVED",
            "direction": "DIRECTLY_OBSERVED",
        },
        "unknowns": ["target", "pnl"],
        "extractedBy": "operator:joe",
        "lane": "RESEARCH",
        "schemaVersion": to.SCHEMA_VERSION,
        "createdAt": "2026-08-17T12:00:00Z",
    }
    record.update(overrides)
    return record


class TestTheBaselineIsActuallyValid(unittest.TestCase):
    """If `base()` were invalid, every refusal test below would pass vacuously."""

    def test_the_shared_baseline_is_accepted(self):
        to.validate_observation(base())   # must not raise


class TestActorGovernsIdentity(unittest.TestCase):

    def test_both_actors_are_accepted(self):
        to.validate_observation(base(actor="HUMAN"))
        to.validate_observation(base(actor="MOGO",
                                     observationId="TOBS|MOGO|20260817|001"))

    def test_an_unknown_actor_is_refused(self):
        for actor in ("human", "", None, "SYSTEM", 3):
            with self.subTest(actor=actor):
                with self.assertRaises(to.ObservationRefused):
                    to.validate_observation(base(actor=actor))

    def test_the_identifier_carries_the_actor_and_counts_per_actor(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = ec.next_observation_id(tmp, "HUMAN", NOW)
            self.assertEqual(first, "TOBS|HUMAN|20260817|001")
            to.write_observation(base(observationId=first), observations_dir=tmp)
            # MOGO's counter is independent -- it must not inherit HUMAN's sequence.
            mogo = ec.next_observation_id(tmp, "MOGO", NOW)
            self.assertEqual(mogo, "TOBS|MOGO|20260817|001")
            to.write_observation(base(actor="MOGO", observationId=mogo),
                                 observations_dir=tmp)
            self.assertEqual(ec.next_observation_id(tmp, "HUMAN", NOW),
                             "TOBS|HUMAN|20260817|002")
            self.assertEqual(ec.next_observation_id(tmp, "MOGO", NOW),
                             "TOBS|MOGO|20260817|002")

    def test_an_id_cannot_be_minted_for_an_unknown_actor(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ec.EvidenceValidationError):
                ec.next_observation_id(tmp, "SYSTEM", NOW)


class TestNothingRecordedIsUnclassified(unittest.TestCase):

    def test_a_value_with_no_classification_is_refused(self):
        record = base(target=1.0900)          # value added, classification not
        with self.assertRaises(to.ObservationRefused):
            to.validate_observation(record)

    def test_positive_control_the_same_value_classified_is_accepted(self):
        record = base(target=1.0900, unknowns=["pnl"])
        record["fieldClassification"]["target"] = "DIRECTLY_OBSERVED"
        to.validate_observation(record)       # must not raise

    def test_a_classification_with_no_value_is_refused(self):
        # `exitPrice` deliberately, NOT a field in base()'s unknowns: classifying an
        # unknown field is refused by the known-XOR-unknown rule, so using one would
        # have passed this test while proving nothing about this guard.
        record = base()
        record["fieldClassification"]["exitPrice"] = "DIRECTLY_OBSERVED"
        with self.assertRaises(to.ObservationRefused):
            to.validate_observation(record)

    def test_an_unrecognised_field_cannot_be_classified(self):
        record = base()
        record["fieldClassification"]["profitFactor"] = "DIRECTLY_OBSERVED"
        with self.assertRaises(to.ObservationRefused):
            to.validate_observation(record)

    def test_an_unrecognised_classification_is_refused(self):
        record = base()
        record["fieldClassification"]["entry"] = "PROBABLY"
        with self.assertRaises(to.ObservationRefused):
            to.validate_observation(record)


class TestKnownExclusiveOrUnknown(unittest.TestCase):

    def test_a_field_cannot_be_both_valued_and_unknown(self):
        with self.assertRaises(to.ObservationRefused):
            to.validate_observation(base(unknowns=["entry"]))

    def test_a_field_cannot_be_both_classified_and_unknown(self):
        record = base(target=None)
        record["fieldClassification"]["target"] = "UNKNOWN"
        record["unknowns"] = ["target", "pnl"]
        with self.assertRaises(to.ObservationRefused):
            to.validate_observation(record)

    def test_a_field_that_is_valued_classified_and_unknown_is_refused(self):
        """The case the other two invariants cannot see.

        Such a field has a value (so "classification with no value" cannot fire) and
        a classification (so "value with no classification" cannot fire). Only the
        known-XOR-unknown rule catches it, which is why that rule is one check
        rather than two mutually-covering halves.
        """
        record = base(unknowns=["entry", "pnl"])   # entry is valued AND classified
        with self.assertRaises(to.ObservationRefused):
            to.validate_observation(record)

    def test_unknowns_must_name_real_fields(self):
        with self.assertRaises(to.ObservationRefused):
            to.validate_observation(base(unknowns=["screenshotQuality"]))

    def test_unknowns_is_required_and_must_be_a_list(self):
        for bad in (None, "target", 0):
            with self.subTest(unknowns=bad):
                record = base()
                record["unknowns"] = bad
                with self.assertRaises(to.ObservationRefused):
                    to.validate_observation(record)


class TestAnInferenceMustStateItsBasis(unittest.TestCase):

    def test_an_inferred_field_without_a_reason_is_refused(self):
        record = base()
        record["fieldClassification"]["entry"] = "INFERRED"
        with self.assertRaises(to.ObservationRefused):
            to.validate_observation(record)

    def test_positive_control_an_inferred_field_with_a_reason_is_accepted(self):
        record = base()
        record["fieldClassification"]["entry"] = "INFERRED"
        record["inferenceReasons"] = {
            "entry": "price label was cropped; read from the order line"}
        to.validate_observation(record)       # must not raise

    def test_an_empty_reason_does_not_satisfy_the_requirement(self):
        for blank in ("", "   ", None, 1):
            with self.subTest(reason=blank):
                record = base()
                record["fieldClassification"]["entry"] = "INFERRED"
                record["inferenceReasons"] = {"entry": blank}
                with self.assertRaises(to.ObservationRefused):
                    to.validate_observation(record)

    def test_a_reason_on_a_non_inferred_field_is_refused(self):
        """Otherwise an observed field could carry inference prose and read as
        though it had been reasoned about."""
        record = base()
        record["inferenceReasons"] = {"entry": "looked about right"}
        with self.assertRaises(to.ObservationRefused):
            to.validate_observation(record)


class TestAbsentIsNotZero(unittest.TestCase):

    def test_zero_is_a_real_value_and_must_be_classified(self):
        """The classic falsy trap: 0.0 is a legitimate price/P&L, not absence."""
        record = base(pnl=0.0, unknowns=["target"])
        with self.assertRaises(to.ObservationRefused):
            to.validate_observation(record)   # unclassified value, even though falsy

    def test_positive_control_zero_classified_is_accepted(self):
        record = base(pnl=0.0, unknowns=["target"])
        record["fieldClassification"]["pnl"] = "DIRECTLY_OBSERVED"
        to.validate_observation(record)

    def test_zero_is_not_treated_as_unknown(self):
        record = base(pnl=0.0, unknowns=["target", "pnl"])
        record["fieldClassification"]["pnl"] = "DIRECTLY_OBSERVED"
        with self.assertRaises(to.ObservationRefused):
            to.validate_observation(record)

    def test_builder_does_not_default_an_absent_number(self):
        record = to.build_observation(
            actor="HUMAN", sourceId="EVSRC|TJR|20260817|001", instrument="EUR/USD",
            fields={"entry": 1.0840},
            classification={"instrument": "DIRECTLY_OBSERVED",
                            "entry": "DIRECTLY_OBSERVED"},
            unknowns=["stop", "target"], extractedBy="operator:joe", now=NOW,
            observationId="TOBS|HUMAN|20260817|001")
        for absent in ("stop", "target", "pnl", "positionSize"):
            self.assertNotIn(absent, record,
                             "%s must stay absent, not be defaulted" % absent)

    def test_builder_preserves_a_zero_it_was_given(self):
        record = to.build_observation(
            actor="MOGO", sourceId="EVSRC|MOGO|20260817|001", instrument="EUR/USD",
            fields={"pnl": 0.0},
            classification={"instrument": "DIRECTLY_OBSERVED",
                            "pnl": "DIRECTLY_OBSERVED"},
            unknowns=[], extractedBy="mogo:paper-engine", now=NOW,
            observationId="TOBS|MOGO|20260817|001")
        self.assertIn("pnl", record)
        self.assertEqual(record["pnl"], 0.0)


class TestProvenanceCarriesThePopulation(unittest.TestCase):
    """The replay-vs-forward distinction is DERIVED from the source, so these are
    the guards that keep it derivable and keep it failing closed."""

    def test_a_sourceid_that_is_not_an_evidence_source_is_refused(self):
        """The importer originally pointed sourceId straight at a package id. That
        looks traceable, resolves to nothing, and silently violates the schema's
        `^EVSRC\\|` pattern -- so the population becomes unknowable."""
        for bad in ("PKG|alex_g_sr_v1|20260427|1", "TOBS|MOGO|1", "just-a-string"):
            with self.subTest(sourceId=bad):
                with self.assertRaises(to.ObservationRefused):
                    to.validate_observation(base(sourceId=bad))

    def test_positive_control_an_evidence_source_id_is_accepted(self):
        to.validate_observation(base(sourceId="EVSRC|TJR|20260817|001"))

    def test_an_unlisted_source_type_is_unknown_not_forward(self):
        """Fail closed in the direction that matters: a source type nobody has
        classified must never silently count as forward evidence."""
        for source_type in ("transcript", "note", "screenshot", "video", None):
            with self.subTest(sourceType=source_type):
                sources = {"EVSRC|TJR|20260817|001": {
                    "sourceId": "EVSRC|TJR|20260817|001", "sourceType": source_type}}
                self.assertEqual(to.observation_population(base(), sources),
                                 to.UNKNOWN_POPULATION)

    def test_positive_control_the_two_classified_types_resolve(self):
        for source_type, expected in (("replay_observation", to.HISTORICAL),
                                      ("paper_trade", to.FORWARD),
                                      ("live_trade_review", to.FORWARD)):
            with self.subTest(sourceType=source_type):
                sources = {"EVSRC|TJR|20260817|001": {
                    "sourceId": "EVSRC|TJR|20260817|001", "sourceType": source_type}}
                self.assertEqual(to.observation_population(base(), sources), expected)

    def test_summarize_refuses_without_the_source_map(self):
        """Invariant 3, structurally: there is no signature by which a caller gets
        a total that silently mixes replay with forward."""
        with self.assertRaises(to.ObservationRefused):
            to.summarize({}, None)

    def test_select_population_names_the_population_it_returns(self):
        sources = {"EVSRC|A": {"sourceId": "EVSRC|A", "sourceType": "replay_observation"},
                   "EVSRC|B": {"sourceId": "EVSRC|B", "sourceType": "paper_trade"}}
        obs = {"r": base(sourceId="EVSRC|A"), "f": base(sourceId="EVSRC|B")}
        self.assertEqual(list(to.select_population(obs, sources, to.HISTORICAL)), ["r"])
        self.assertEqual(list(to.select_population(obs, sources, to.FORWARD)), ["f"])
        with self.assertRaises(to.ObservationRefused):
            to.select_population(obs, sources, "LIVE_MONEY")


class TestLaneIsPinned(unittest.TestCase):

    def test_a_non_research_lane_is_refused(self):
        for lane in ("TRADING", "PRODUCTION", "LIVE", ""):
            with self.subTest(lane=lane):
                with self.assertRaises(to.ObservationRefused):
                    to.validate_observation(base(lane=lane))

    def test_the_builder_pins_the_lane_and_ignores_an_attempt_to_set_it(self):
        record = to.build_observation(
            actor="MOGO", sourceId="EVSRC|MOGO|20260817|001", instrument="EUR/USD",
            fields={}, classification={"instrument": "DIRECTLY_OBSERVED"},
            unknowns=[], extractedBy="mogo:paper-engine", now=NOW,
            observationId="TOBS|MOGO|20260817|001", lane="TRADING")
        self.assertEqual(record["lane"], "RESEARCH")


class TestWritingIsSafe(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_a_record_round_trips(self):
        path = to.write_observation(base(), observations_dir=self.tmp)
        self.assertTrue(os.path.exists(path))
        loaded = to.load_observations(self.tmp)
        self.assertEqual(loaded["TOBS|HUMAN|20260817|001"]["entry"], 1.0840)

    def test_an_observation_is_immutable_once_recorded(self):
        to.write_observation(base(), observations_dir=self.tmp)
        with self.assertRaises(to.ObservationRefused):
            to.write_observation(base(entry=9.9999), observations_dir=self.tmp)
        # and the original reading is intact
        loaded = to.load_observations(self.tmp)
        self.assertEqual(loaded["TOBS|HUMAN|20260817|001"]["entry"], 1.0840)

    def test_an_invalid_record_is_never_written(self):
        bad = base(target=1.09)               # unclassified value
        with self.assertRaises(to.ObservationRefused):
            to.write_observation(bad, observations_dir=self.tmp)
        self.assertEqual(to.load_observations(self.tmp), {},
                         "a refused record must leave nothing behind")

    def test_loading_an_absent_directory_is_empty_not_an_error(self):
        self.assertEqual(
            to.load_observations(os.path.join(self.tmp, "nope")), {})


SOURCES = {
    "EVSRC|TJR|20260817|001": {"sourceId": "EVSRC|TJR|20260817|001",
                               "sourceType": "live_trade_review"},
    "EVSRC|MOGO|20260817|001": {"sourceId": "EVSRC|MOGO|20260817|001",
                                "sourceType": "paper_trade"},
    "EVSRC|MOGO|20260817|009": {"sourceId": "EVSRC|MOGO|20260817|009",
                                "sourceType": "replay_observation"},
}


class TestSummaryIsHonest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_it_counts_both_sides_and_reports_unknowns(self):
        to.write_observation(base(), observations_dir=self.tmp)
        to.write_observation(
            base(actor="MOGO", observationId="TOBS|MOGO|20260817|001"),
            observations_dir=self.tmp)
        summary = to.summarize(to.load_observations(self.tmp), SOURCES)
        forward = summary["byPopulation"]["FORWARD"]
        self.assertEqual(forward["total"], 2)
        self.assertEqual(forward["byActor"]["HUMAN"]["count"], 1)
        self.assertEqual(forward["byActor"]["MOGO"]["count"], 1)
        self.assertEqual(forward["byActor"]["HUMAN"]["unknownFields"], 2)
        self.assertEqual(summary["lane"], "RESEARCH")

    def test_comparable_is_the_lesser_side_not_the_total(self):
        """Two human observations and no MOGO decision means NOTHING is
        comparable. Reporting 2 would overstate what the corpus supports."""
        to.write_observation(base(), observations_dir=self.tmp)
        to.write_observation(base(observationId="TOBS|HUMAN|20260817|002"),
                             observations_dir=self.tmp)
        summary = to.summarize(to.load_observations(self.tmp), SOURCES)
        forward = summary["byPopulation"]["FORWARD"]
        self.assertEqual(forward["total"], 2)
        self.assertEqual(forward["comparable"], 0)


class TestStaysInSyncWithTheSchema(unittest.TestCase):

    def test_every_observable_field_exists_in_the_schema(self):
        import json
        schema_path = os.path.join(
            REPO_ROOT, "docs", "trader-intelligence", "evidence", "schema",
            "trade-observation.schema.json")
        with open(schema_path, "r", encoding="utf-8") as handle:
            schema = json.load(handle)
        props = schema["properties"]
        for field in to.OBSERVABLE_FIELDS:
            self.assertIn(field, props,
                          "%s is classifiable in code but absent from the schema"
                          % field)
        self.assertIn("inferenceReasons", props)

    def test_the_actor_enum_matches(self):
        import json
        schema_path = os.path.join(
            REPO_ROOT, "docs", "trader-intelligence", "evidence", "schema",
            "trade-observation.schema.json")
        with open(schema_path, "r", encoding="utf-8") as handle:
            schema = json.load(handle)
        self.assertEqual(tuple(schema["properties"]["actor"]["enum"]), to.ACTORS)


if __name__ == "__main__":
    unittest.main()


class TestReconstructedIsItsOwnPopulation(unittest.TestCase):
    """B-22: backfilled records must never be pooled with genuine forward evidence.

    A package minted by the app's backfill carries captureBasis HISTORICAL_BACKFILL
    and completenessReport level MINIMAL with `*` marked UNSAFE_TO_RECONSTRUCT.
    Filing that alongside a live-captured record under one population would make
    the two indistinguishable forever and retroactively weaken all 26 genuine
    forward records.
    """

    def sources(self):
        return {
            "EVSRC|R|1": {"sourceId": "EVSRC|R|1", "sourceType": "replay_observation"},
            "EVSRC|F|1": {"sourceId": "EVSRC|F|1", "sourceType": "paper_trade"},
            "EVSRC|B|1": {"sourceId": "EVSRC|B|1", "sourceType": "journal_entry"},
            "EVSRC|X|1": {"sourceId": "EVSRC|X|1", "sourceType": "not_a_real_type"},
        }

    def population(self, source_id):
        return to.observation_population({"sourceId": source_id}, self.sources())

    def test_a_backfilled_source_is_RECONSTRUCTED(self):
        self.assertEqual(self.population("EVSRC|B|1"), to.RECONSTRUCTED)

    def test_it_is_not_FORWARD(self):
        """The contamination boundary. This is the assertion that stops a
        one-character edit in CAPTURE_BASIS_SOURCE_TYPE from silently merging
        reconstructed evidence into the forward population."""
        self.assertNotEqual(self.population("EVSRC|B|1"), to.FORWARD)

    def test_it_is_not_HISTORICAL_either(self):
        self.assertNotEqual(self.population("EVSRC|B|1"), to.HISTORICAL)

    def test_UNKNOWN_still_means_cannot_determine(self):
        """RECONSTRUCTED must not be implemented by widening UNKNOWN. An
        unrecognised source type still fails closed to UNKNOWN, and a deliberate
        third class is distinguishable from an unresolvable one."""
        self.assertEqual(self.population("EVSRC|X|1"), to.UNKNOWN_POPULATION)
        self.assertNotEqual(self.population("EVSRC|B|1"), to.UNKNOWN_POPULATION)

    def test_a_source_absent_from_the_map_is_UNKNOWN_not_RECONSTRUCTED(self):
        """Fail-closed on an ABSENT source, distinct from an unrecognised type.
        Both paths return UNKNOWN and both must: an observation whose source
        cannot be found is unresolvable, and quietly calling it reconstructed
        would invent a provenance class for it."""
        self.assertEqual(
            to.observation_population({"sourceId": "EVSRC|NOT|PRESENT"}, self.sources()),
            to.UNKNOWN_POPULATION)
        self.assertEqual(to.observation_population({}, self.sources()),
                         to.UNKNOWN_POPULATION)

    def test_the_three_known_populations_are_mutually_exclusive(self):
        got = {self.population(s) for s in ("EVSRC|R|1", "EVSRC|F|1", "EVSRC|B|1")}
        self.assertEqual(got, {to.HISTORICAL, to.FORWARD, to.RECONSTRUCTED})

    def test_select_population_isolates_reconstructed(self):
        observations = {
            "a": {"observationId": "a", "sourceId": "EVSRC|F|1"},
            "b": {"observationId": "b", "sourceId": "EVSRC|B|1"},
            "c": {"observationId": "c", "sourceId": "EVSRC|R|1"},
        }
        forward = to.select_population(observations, self.sources(), to.FORWARD)
        self.assertEqual([r["observationId"] for r in forward.values()], ["a"])
        reconstructed = to.select_population(observations, self.sources(), to.RECONSTRUCTED)
        self.assertEqual([r["observationId"] for r in reconstructed.values()], ["b"])

    def test_summarize_reports_reconstructed_separately_and_offers_no_blended_total(self):
        observations = {
            "a": {"observationId": "a", "sourceId": "EVSRC|F|1", "actor": "MOGO"},
            "b": {"observationId": "b", "sourceId": "EVSRC|B|1", "actor": "MOGO"},
        }
        report = to.summarize(observations, self.sources())
        self.assertEqual(set(report["populationsPresent"]), {to.FORWARD, to.RECONSTRUCTED})
        self.assertEqual(report["byPopulation"][to.FORWARD]["total"], 1)
        self.assertEqual(report["byPopulation"][to.RECONSTRUCTED]["total"], 1)
        self.assertNotIn("total", report)

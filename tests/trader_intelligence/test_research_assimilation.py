"""Storage is not learning: the assimilation layer (MOGO-022).

The real-corpus cases assert RELATIONS, never snapshot counts -- the corpus grows
every time a trade closes, and a pinned count would report that as a failure.
"""
import datetime
import json
import os
import shutil
import sys
import tempfile
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                         "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts", "trader_intelligence"))

import research_assimilation as ra    # noqa: E402
import trade_observation as to        # noqa: E402

NOW = datetime.datetime(2026, 8, 18, 22, 0, 0, tzinfo=datetime.timezone.utc)

SOURCES = {
    "EVSRC|R|1": {"sourceId": "EVSRC|R|1", "sourceType": "replay_observation"},
    "EVSRC|F|1": {"sourceId": "EVSRC|F|1", "sourceType": "paper_trade"},
    "EVSRC|B|1": {"sourceId": "EVSRC|B|1", "sourceType": "journal_entry"},
}


def obs(observation_id, source_id, r_multiple, outcome="Loss", unknowns=None,
        content_hash=None):
    return {"observationId": observation_id, "sourceId": source_id, "actor": "MOGO",
            "strategyId": "alex_g_sr_v1", "rMultiple": r_multiple, "outcome": outcome,
            "unknowns": unknowns or [],
            "sourceContentHash": content_hash or ("h-" + observation_id)}


class AssimilationCase(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="mogo_assim_")
        self.state = os.path.join(self.root, "current-state.json")
        self.ledger = os.path.join(self.root, "ledger")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def run_once(self, observations, write=True, now=NOW):
        return ra.assimilate(now, observations=observations, sources=SOURCES,
                             write=write, state_path=self.state, ledger_dir=self.ledger)

    def ledger_count(self):
        return len(ra.ledger_records(self.ledger))


class TestExactlyOnceScientificEffect(AssimilationCase):
    """Processing may be at-least-once; the scientific effect must be exactly-once."""

    def test_reprocessing_the_same_corpus_records_nothing_further(self):
        corpus = {"a": obs("a", "EVSRC|F|1", -1.0)}
        first = self.run_once(corpus)
        self.assertTrue(first["corpusChanged"])
        self.assertEqual(self.ledger_count(), 1)

        for _ in range(3):
            again = self.run_once(corpus)
            self.assertFalse(again["corpusChanged"])
            self.assertEqual(again["learningKinds"], [ra.NO_SCIENTIFIC_CHANGE])
        self.assertEqual(self.ledger_count(), 1, "reprocessing wrote another record")

    def test_a_genuinely_new_observation_does_record(self):
        """Positive control. Without it, the idempotence test above would pass on a
        function that never records anything at all."""
        corpus = {"a": obs("a", "EVSRC|F|1", -1.0)}
        self.run_once(corpus)
        corpus["b"] = obs("b", "EVSRC|F|1", 2.0, outcome="Win")
        second = self.run_once(corpus)
        self.assertTrue(second["corpusChanged"])
        self.assertEqual(self.ledger_count(), 2)

    def test_a_record_rewritten_in_place_changes_the_fingerprint(self):
        """Silent rewriting must not slip past the exactly-once key."""
        corpus = {"a": obs("a", "EVSRC|F|1", -1.0, content_hash="h1")}
        first = ra.corpus_fingerprint(corpus, SOURCES)
        corpus["a"]["sourceContentHash"] = "h2"
        self.assertNotEqual(ra.corpus_fingerprint(corpus, SOURCES), first)

    def test_moving_an_observation_between_populations_changes_the_fingerprint(self):
        corpus = {"a": obs("a", "EVSRC|F|1", -1.0)}
        forward = ra.corpus_fingerprint(corpus, SOURCES)
        corpus["a"]["sourceId"] = "EVSRC|B|1"
        self.assertNotEqual(ra.corpus_fingerprint(corpus, SOURCES), forward)

    def test_a_dry_run_writes_nothing(self):
        corpus = {"a": obs("a", "EVSRC|F|1", -1.0)}
        self.run_once(corpus, write=False)
        self.assertEqual(self.ledger_count(), 0)
        self.assertFalse(os.path.exists(self.state))


class TestNothingLearnedIsAValidResult(AssimilationCase):

    def test_an_unchanged_corpus_is_classified_as_no_change(self):
        corpus = {"a": obs("a", "EVSRC|F|1", -1.0)}
        self.run_once(corpus)
        record = self.run_once(corpus)
        self.assertEqual(record["learningKinds"], [ra.NO_SCIENTIFIC_CHANGE])
        self.assertIn("nothing may be claimed", record["legitimateConclusion"])

    def test_no_lesson_is_manufactured_from_a_trade_that_moves_nothing(self):
        """A trade is not automatically a lesson. Re-running must not invent one."""
        corpus = {"a": obs("a", "EVSRC|F|1", -1.0)}
        self.run_once(corpus)
        record = self.run_once(corpus)
        self.assertNotIn(ra.UPDATES_DESCRIPTIVE_STATISTICS, record["learningKinds"])
        self.assertEqual(record["changedState"], {})


class TestClassifyDirectly(unittest.TestCase):
    """classify() exercised on its own.

    assimilate() short-circuits on an unchanged fingerprint and never calls
    classify(), so every no-change guarantee inside classify was untested until
    these existed -- mutating it to always claim a statistics change, and to drop
    the no-change branch entirely, both survived the whole suite.
    """

    def state(self, forward_n, mean_r=-1.0, verdicts=None):
        return {
            "corpusFingerprint": "fp-%s-%s" % (forward_n, mean_r),
            "observationTotal": forward_n,
            "byPopulation": {"FORWARD": {"n": forward_n, "meanR": mean_r,
                                          "byOutcome": {"Loss": forward_n},
                                          "unknownFieldCounts": {}}},
            "byStrategyAndPopulation": {"alex_g_sr_v1|FORWARD": forward_n},
            "fidelity": {},
            "hypotheses": {"byVerdict": verdicts or {"BLOCKED": 641},
                            "byBlocker": {}},
        }

    def test_identical_states_yield_NO_SCIENTIFIC_CHANGE_and_nothing_else(self):
        kinds, changes = ra.classify(self.state(5), self.state(5))
        self.assertEqual(kinds, [ra.NO_SCIENTIFIC_CHANGE])
        self.assertEqual(changes, {})

    def test_identical_states_do_NOT_claim_statistics_moved(self):
        """The don't-manufacture-a-lesson guarantee, asserted where it lives."""
        kinds, _ = ra.classify(self.state(5), self.state(5))
        self.assertNotIn(ra.UPDATES_DESCRIPTIVE_STATISTICS, kinds)
        self.assertNotIn(ra.CHANGES_COHORT, kinds)
        self.assertNotIn(ra.WINNER_LOSER_EVIDENCE, kinds)

    def test_a_state_that_only_changes_fingerprint_is_still_no_change(self):
        """The fingerprint is bookkeeping, not evidence. A differing fingerprint
        with identical statistics must not be reported as learning."""
        before, after = self.state(5), self.state(5)
        after["corpusFingerprint"] = "something-else"
        kinds, changes = ra.classify(before, after)
        self.assertEqual(kinds, [ra.NO_SCIENTIFIC_CHANGE])
        self.assertEqual(changes, {})

    def test_a_real_change_IS_classified(self):
        """Positive control for all three above."""
        kinds, changes = ra.classify(self.state(5), self.state(6))
        self.assertIn(ra.UPDATES_DESCRIPTIVE_STATISTICS, kinds)
        self.assertNotIn(ra.NO_SCIENTIFIC_CHANGE, kinds)
        self.assertTrue(changes)

    def test_a_hypothesis_verdict_change_is_a_confidence_change(self):
        kinds, _ = ra.classify(self.state(5),
                                self.state(5, verdicts={"BLOCKED": 640, "TESTABLE": 1}))
        self.assertIn(ra.CHANGES_CONFIDENCE, kinds)
        self.assertNotIn(ra.LEAVES_HYPOTHESES_UNCHANGED, kinds)

    def test_a_change_that_touches_no_population_does_not_claim_statistics_moved(self):
        """Each learning kind must be earned by the state that actually moved.

        The no-change case returns early, so it never reaches the per-kind
        conditions -- mutating the statistics condition to fire unconditionally
        survived the entire suite until this case existed. Here hypotheses move and
        populations do not, which reaches the condition and constrains it.
        """
        kinds, changes = ra.classify(
            self.state(5), self.state(5, verdicts={"BLOCKED": 640, "TESTABLE": 1}))
        self.assertTrue(changes, "fixture must actually change something")
        self.assertNotIn(ra.UPDATES_DESCRIPTIVE_STATISTICS, kinds)
        self.assertNotIn(ra.CHANGES_COHORT, kinds)
        self.assertNotIn(ra.WINNER_LOSER_EVIDENCE, kinds)

    def test_no_prior_state_is_a_baseline_not_a_lesson(self):
        kinds, _ = ra.classify(None, self.state(5))
        self.assertEqual(kinds, ["BASELINE_ESTABLISHED"])


class TestLearningIsClassifiedFromEvidence(AssimilationCase):

    def test_a_new_forward_close_updates_statistics_and_cohort(self):
        corpus = {"a": obs("a", "EVSRC|F|1", -1.0)}
        self.run_once(corpus)
        corpus["b"] = obs("b", "EVSRC|F|1", 2.0, outcome="Win")
        record = self.run_once(corpus)
        self.assertIn(ra.UPDATES_DESCRIPTIVE_STATISTICS, record["learningKinds"])
        self.assertIn(ra.CHANGES_COHORT, record["learningKinds"])
        self.assertIn(ra.WINNER_LOSER_EVIDENCE, record["learningKinds"])

    def test_an_observation_with_unknown_fields_reveals_a_deficiency(self):
        corpus = {"a": obs("a", "EVSRC|F|1", -1.0)}
        self.run_once(corpus)
        corpus["b"] = obs("b", "EVSRC|F|1", -1.0,
                          unknowns=["accountBalanceBefore", "timeframe"])
        record = self.run_once(corpus)
        self.assertIn(ra.REVEALS_EVIDENCE_DEFICIENCY, record["learningKinds"])

    def test_hypotheses_unchanged_is_stated_explicitly_not_left_implicit(self):
        corpus = {"a": obs("a", "EVSRC|F|1", -1.0)}
        self.run_once(corpus)
        corpus["b"] = obs("b", "EVSRC|F|1", -1.0)
        record = self.run_once(corpus)
        self.assertIn(ra.LEAVES_HYPOTHESES_UNCHANGED, record["learningKinds"])

    def test_every_record_carries_its_non_conclusions(self):
        corpus = {"a": obs("a", "EVSRC|F|1", -1.0)}
        record = self.run_once(corpus)
        self.assertTrue(record["nonConclusion"])
        self.assertFalse(record["adjudicates"])


class TestPopulationsAreNotPooled(AssimilationCase):

    def test_reconstructed_evidence_does_not_move_forward_statistics(self):
        """The contamination boundary, at the assimilation layer. A backfilled
        record must change the RECONSTRUCTED cohort and leave FORWARD alone."""
        corpus = {"a": obs("a", "EVSRC|F|1", -1.0)}
        self.run_once(corpus)
        corpus["b"] = obs("b", "EVSRC|B|1", 2.0, outcome="Win")
        record = self.run_once(corpus)
        moved = record["changedState"]
        self.assertTrue(any(k.startswith("byPopulation.RECONSTRUCTED") for k in moved),
                        "the reconstructed cohort did not move")
        forward_moved = [k for k in moved if k.startswith("byPopulation.FORWARD")]
        self.assertEqual(forward_moved, [],
                         "reconstructed evidence moved FORWARD statistics: %s"
                         % forward_moved)

    def test_replay_evidence_does_not_move_forward_statistics(self):
        corpus = {"a": obs("a", "EVSRC|F|1", -1.0)}
        self.run_once(corpus)
        corpus["b"] = obs("b", "EVSRC|R|1", 2.0, outcome="Win")
        record = self.run_once(corpus)
        forward_moved = [k for k in record["changedState"]
                         if k.startswith("byPopulation.FORWARD")]
        self.assertEqual(forward_moved, [])


class TestAgainstTheRealCorpus(unittest.TestCase):
    """One real genuine Forward PAPER close, proven end to end."""

    TARGET = "TOBS|MOGO|20260817|026"

    @classmethod
    def setUpClass(cls):
        cls.sources = to.load_sources()
        cls.observations = to.load_observations()
        cls.without = {k: v for k, v in cls.observations.items() if k != cls.TARGET}
        cls.before = ra.research_state(cls.without, cls.sources)
        cls.after = ra.research_state(cls.observations, cls.sources)
        cls.kinds, cls.changes = ra.classify(cls.before, cls.after)

    def test_the_target_close_is_a_complete_genuine_forward_observation(self):
        record = self.observations[self.TARGET]
        self.assertEqual(to.observation_population(record, self.sources), to.FORWARD)
        self.assertEqual(record.get("unknowns"), [],
                         "the proof case should be a complete observation")

    def test_removing_it_changes_the_corpus_fingerprint(self):
        self.assertNotEqual(self.before["corpusFingerprint"],
                            self.after["corpusFingerprint"])

    def test_it_moves_the_forward_cohort_by_exactly_one(self):
        self.assertEqual(self.after["byPopulation"][to.FORWARD]["n"]
                         - self.before["byPopulation"][to.FORWARD]["n"], 1)

    def test_it_moves_no_other_population(self):
        for population in (to.HISTORICAL, to.RECONSTRUCTED):
            b = self.before["byPopulation"].get(population, {}).get("n", 0)
            a = self.after["byPopulation"].get(population, {}).get("n", 0)
            self.assertEqual(a, b, "%s moved on a FORWARD close" % population)

    def test_it_is_classified_as_statistics_and_cohort_but_not_hypothesis_change(self):
        self.assertIn(ra.UPDATES_DESCRIPTIVE_STATISTICS, self.kinds)
        self.assertIn(ra.CHANGES_COHORT, self.kinds)
        self.assertIn(ra.LEAVES_HYPOTHESES_UNCHANGED, self.kinds)
        self.assertNotIn(ra.CONTRADICTS_HYPOTHESIS, self.kinds)

    def test_no_hypothesis_verdict_moved(self):
        self.assertEqual(self.before["hypotheses"]["byVerdict"],
                         self.after["hypotheses"]["byVerdict"],
                         "a single forward close moved a hypothesis verdict")


if __name__ == "__main__":
    unittest.main()

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

    def test_a_corpus_edited_in_place_IS_recorded_even_though_the_count_is_unchanged(self):
        """The exactly-once KEY, not just the hash function.

        Replacing the key with the raw observation count passes every other
        exactly-once test here, because they all change the count as well. This is
        the case that separates them -- and it is the real one:
        `backfill_mapped_fields` edits existing records in place and adds no rows,
        so a count-based key would let a genuine statistics change go unrecorded
        while the ledger asserted "no change".
        """
        corpus = {"a": obs("a", "EVSRC|F|1", -1.0)}
        first = self.run_once(corpus)
        self.assertTrue(first["corpusChanged"])
        count_before = len(corpus)

        corpus["a"]["rMultiple"] = 8.0
        corpus["a"]["outcome"] = "Win"
        second = self.run_once(corpus)

        self.assertEqual(len(corpus), count_before, "fixture must not change the count")
        self.assertTrue(second["corpusChanged"],
                        "an in-place edit was treated as no change")
        self.assertNotIn(ra.NO_SCIENTIFIC_CHANGE, second["learningKinds"])
        self.assertEqual(self.ledger_count(), 2)

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



class TestTheDiagnosticSurvivesADamagedCorpus(unittest.TestCase):
    """A diagnostic that crashes leaves the PREVIOUS run's clean report on disk.

    The statistics group by `outcome`, so a record with none produces a `None` group
    key, and `sorted(keys)` raised `TypeError: '<' not supported between instances of
    'str' and 'NoneType'` -- out of `run_integrity_checks`, before the report was
    written. Other tooling then reads an `ERROR: 0` describing a corpus that no
    longer exists. Same shape as the NaN crash (B-32.18), different trigger.

    The corpus that produces this is itself invalid -- `RECORD_FIELD_MISSING` now
    reports it -- but the diagnostic must survive long enough to SAY so.
    """

    def test_a_None_group_key_does_not_raise(self):
        changes = ra._diff_numbers({"byOutcome": {None: 1, "Win": 2}},
                                   {"byOutcome": {None: 3, "Win": 2}})
        self.assertEqual(changes, {"byOutcome.None": {"before": 1, "after": 3}})

    def test_mixed_key_types_do_not_raise(self):
        for keys in ({None: 1, "a": 2}, {1: 1, "a": 2}, {True: 1, "a": 2},
                     {None: 1, 2: 2, "c": 3}):
            with self.subTest(keys=sorted(map(str, keys))):
                after = {k: (v + 1) for k, v in keys.items()}
                self.assertTrue(ra._diff_numbers({"g": keys}, {"g": after}))

    def test_POSITIVE_CONTROL_ordinary_keys_still_diff(self):
        self.assertEqual(
            ra._diff_numbers({"n": 1}, {"n": 2}), {"n": {"before": 1, "after": 2}})

if __name__ == "__main__":
    unittest.main()


class TestTheFingerprintCoversTheEvidenceItself(AssimilationCase):
    """Non-circular fingerprint tests.

    The original test mutated `sourceContentHash` -- the very input to the hash --
    and so proved only that the hash function reads its argument. An independent
    verifier demonstrated on the REAL corpus that editing rMultiple/outcome/pnl in
    place left the fingerprint identical, and that the already_recorded
    short-circuit then OVERRODE classify(): forward meanR moved from -0.149302 to
    +0.172127 while the ledger asserted "no change". These edit the trade data.
    """

    def fingerprint(self, corpus, sources=None):
        return ra.corpus_fingerprint(corpus, sources or SOURCES)

    def test_editing_rMultiple_in_place_changes_the_fingerprint(self):
        corpus = {"a": obs("a", "EVSRC|F|1", -1.0)}
        before = self.fingerprint(corpus)
        corpus["a"]["rMultiple"] = 8.0
        self.assertNotEqual(self.fingerprint(corpus), before)

    def test_editing_outcome_in_place_changes_the_fingerprint(self):
        corpus = {"a": obs("a", "EVSRC|F|1", -1.0, outcome="Loss")}
        before = self.fingerprint(corpus)
        corpus["a"]["outcome"] = "Win"
        self.assertNotEqual(self.fingerprint(corpus), before)

    def test_a_widening_backfill_changes_the_fingerprint(self):
        """import_mogo_observations.backfill_mapped_fields performs exactly this
        edit, and its widening-only guard REQUIRES sourceContentHash to stay put.
        Before this, running it after an assimilation moved meanR with no way for
        assimilation to notice."""
        corpus = {"a": obs("a", "EVSRC|F|1", -1.0)}
        before = self.fingerprint(corpus)
        corpus["a"]["accountBalanceAfter"] = 9658.67
        self.assertNotEqual(self.fingerprint(corpus), before)

    def test_retyping_a_source_within_its_own_population_changes_the_fingerprint(self):
        """Population is derived from the source, so a source rewritten under the
        observation changes what the evidence means."""
        corpus = {"a": obs("a", "EVSRC|R|1", -1.0)}
        before = self.fingerprint(corpus)
        sources = dict(SOURCES)
        sources["EVSRC|R|1"] = {"sourceId": "EVSRC|R|1", "sourceType": "generated_analysis"}
        self.assertNotEqual(self.fingerprint(corpus, sources), before)

    def test_the_key_is_not_merely_the_observation_count(self):
        """A count-based key passes every other exactly-once test in this file,
        because they all happen to change the count too."""
        one = {"a": obs("a", "EVSRC|F|1", -1.0)}
        other = {"a": obs("a", "EVSRC|F|1", 2.0, outcome="Win")}
        self.assertEqual(len(one), len(other))
        self.assertNotEqual(self.fingerprint(one), self.fingerprint(other))

    def test_an_unchanged_corpus_still_produces_a_stable_fingerprint(self):
        """Positive control: the tests above must fail because the evidence moved,
        not because the hash is unstable."""
        corpus = {"a": obs("a", "EVSRC|F|1", -1.0)}
        self.assertEqual(self.fingerprint(corpus), self.fingerprint(dict(corpus)))


class TestInterruptionDoesNotDoubleRecord(AssimilationCase):

    def test_a_crash_between_the_ledger_and_the_state_does_not_double_record(self):
        """The ledger is the scientific effect; current-state.json is the
        suppressor. Crashing between them left the effect recorded and the
        suppressor absent, so the retry wrote a SECOND record asserting the same
        transition. The ledger record is now named by the transition it records,
        so the retry lands on the same file."""
        corpus = {"a": obs("a", "EVSRC|F|1", -1.0)}
        self.run_once(corpus)
        corpus["b"] = obs("b", "EVSRC|F|1", 2.0, outcome="Win")

        real_open = open
        state_path = self.state

        def failing_open(path, *args, **kwargs):
            if str(path) == state_path and "w" in str(args[0] if args else kwargs.get("mode", "")):
                raise IOError("fixture crash between ledger and state")
            return real_open(path, *args, **kwargs)

        import builtins
        builtins.open = failing_open
        try:
            with self.assertRaises(IOError):
                self.run_once(corpus)
        finally:
            builtins.open = real_open

        after_crash = self.ledger_count()
        self.run_once(corpus)          # the retry
        self.assertEqual(self.ledger_count(), after_crash,
                         "the retry wrote a second record for the same transition")

    def test_two_records_never_assert_the_same_transition(self):
        corpus = {"a": obs("a", "EVSRC|F|1", -1.0)}
        self.run_once(corpus)
        corpus["b"] = obs("b", "EVSRC|F|1", 2.0, outcome="Win")
        self.run_once(corpus)
        fingerprints = [r["corpusFingerprintAfter"] for r in ra.ledger_records(self.ledger)]
        self.assertEqual(len(fingerprints), len(set(fingerprints)))


class TestDerivedStatisticsAreConstrained(unittest.TestCase):
    """Every number in _population_stats had zero assertions on it."""

    def stats(self, records):
        return ra._population_stats(records)

    def test_a_break_even_trade_is_not_counted_as_a_win(self):
        s = self.stats([obs("a", "EVSRC|F|1", 0.0, outcome="BreakEven"),
                        obs("b", "EVSRC|F|1", 2.0, outcome="Win")])
        self.assertEqual(s["winCount"], 1)

    def test_an_absent_rMultiple_is_skipped_not_counted_as_zero(self):
        """The same invariant trade_observation defends with a whole test class:
        absent is not zero. 221 records already carry pnl as an explicit unknown."""
        no_r = obs("a", "EVSRC|F|1", None)
        s = self.stats([no_r, obs("b", "EVSRC|F|1", 2.0, outcome="Win")])
        self.assertEqual(s["rMultipleCount"], 1)
        self.assertEqual(s["meanR"], 2.0)

    def test_worst_and_best_are_not_transposed(self):
        s = self.stats([obs("a", "EVSRC|F|1", -1.0), obs("b", "EVSRC|F|1", 2.0)])
        self.assertEqual(s["worstR"], -1.0)
        self.assertEqual(s["bestR"], 2.0)

    def test_meanR_keeps_enough_precision_to_move_on_one_trade(self):
        s = self.stats([obs("a", "EVSRC|F|1", -1.0), obs("b", "EVSRC|F|1", -1.0),
                        obs("c", "EVSRC|F|1", 2.0)])
        self.assertAlmostEqual(s["meanR"], 0.0, places=6)
        s2 = self.stats([obs("a", "EVSRC|F|1", -1.0), obs("b", "EVSRC|F|1", -1.0),
                         obs("c", "EVSRC|F|1", -1.0), obs("d", "EVSRC|F|1", 2.0)])
        self.assertNotEqual(s["meanR"], s2["meanR"])

    def test_n_reflects_the_records_supplied(self):
        self.assertEqual(self.stats([obs("a", "EVSRC|F|1", -1.0)])["n"], 1)


class TestUnearnedKindsAreNotClaimed(unittest.TestCase):

    def state(self, **kw):
        base = {"corpusFingerprint": "fp", "observationTotal": kw.get("total", 1),
                "byPopulation": {"FORWARD": {"n": kw.get("n", 1), "meanR": -1.0,
                                              "byOutcome": {"Loss": 1},
                                              "unknownFieldCounts": kw.get("unknowns", {})}},
                "byStrategyAndPopulation": {"s|FORWARD": kw.get("n", 1)},
                "fidelity": kw.get("fidelity", {}),
                "hypotheses": {"byVerdict": {"BLOCKED": 1}, "byBlocker": {}}}
        return base

    def test_a_candidate_question_is_not_claimed_when_fidelity_did_not_move(self):
        kinds, _ = ra.classify(self.state(n=1), self.state(n=2, total=2))
        self.assertNotIn(ra.GENERATES_CANDIDATE_QUESTION, kinds)

    def test_a_candidate_question_IS_claimed_when_fidelity_moves(self):
        """Positive control for the assertion above."""
        kinds, _ = ra.classify(
            self.state(fidelity={}),
            self.state(fidelity={"s": {"findings": ["REPLAY_IDEALIZES_EXITS"]}}))
        self.assertIn(ra.GENERATES_CANDIDATE_QUESTION, kinds)

    def test_shrinking_unknowns_is_not_an_evidence_deficiency(self):
        """Unknown counts going DOWN means the evidence improved. Claiming a
        deficiency there asserts the opposite of what happened."""
        kinds, _ = ra.classify(self.state(unknowns={"timeframe": 3}),
                                self.state(unknowns={"timeframe": 1}))
        self.assertNotIn(ra.REVEALS_EVIDENCE_DEFICIENCY, kinds)

    def test_growing_unknowns_IS_an_evidence_deficiency(self):
        kinds, _ = ra.classify(self.state(unknowns={"timeframe": 1}),
                                self.state(unknowns={"timeframe": 3}))
        self.assertIn(ra.REVEALS_EVIDENCE_DEFICIENCY, kinds)

    def test_a_vanishing_population_is_reported_not_silently_dropped(self):
        before = self.state(n=2)
        before["byPopulation"]["HISTORICAL"] = {"n": 5, "byOutcome": {},
                                                 "unknownFieldCounts": {}}
        after = self.state(n=2)
        _kinds, changes = ra.classify(before, after)
        self.assertTrue(any(k.startswith("byPopulation.HISTORICAL") for k in changes),
                        "an entire population disappeared without being reported")

    def test_the_conclusion_does_not_assert_statistics_moved_when_they_did_not(self):
        kinds, changes = ra.classify(
            self.state(), self.state(fidelity={"s": {"findings": ["X"]}}))
        text = ra._conclusion(self.state(), self.state(), kinds, changes)
        self.assertNotIn("Descriptive statistics", text)

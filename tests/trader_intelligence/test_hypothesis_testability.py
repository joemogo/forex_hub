#!/usr/bin/env python3
"""Hypothesis testability triage (MOGO-022).

The properties under test:

  * A SHARED TEST SPECIFICATION IS NOT A TEST. Detected by measuring repetition in
    the corpus, not by matching known boilerplate, so it keeps working when the
    template wording changes.
  * A TRADER'S CLAIM IS NOT TESTED BY MOGO'S IMPLEMENTATION. Evidence for
    `alex_g_sr_v1` (MOGO replaying its own engine) is not evidence about ALEX_G.
  * EVERY BLOCKER IS REPORTED, not just the first. Fixing one of three leaves a
    hypothesis exactly as untestable as before.
  * IT WRITES NOTHING and improves no hypothesis. Generating more specific test
    prose would manufacture the appearance of testability, which is the failure
    this module exists to detect.
"""

import glob
import hashlib
import json
import os
import sys
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts", "trader_intelligence"))

import hypothesis_testability as ht    # noqa: E402
import trade_observation as to         # noqa: E402


def hyp(hypothesis_id, replay="unique replay test %s", claims=("CLAIM|TJR|1",),
        limitations=(), independent=("entry_rule",)):
    return {
        "hypothesisId": hypothesis_id,
        "statement": "a statement",
        "sourceClaimIds": list(claims),
        "proposedReplayTest": replay % hypothesis_id if "%s" in replay else replay,
        "proposedPaperTest": "paper",
        "independentVariables": list(independent),
        "dependentVariables": ["setup validity"],
        "limitations": list(limitations),
        "status": "PROPOSED_UNVALIDATED",
        "confidence": "emerging",
    }


SOURCES = {"EVSRC|MOGO|1": {"sourceId": "EVSRC|MOGO|1",
                            "sourceType": "replay_observation"}}


def obs(strategy_id):
    return {"o1": {"observationId": "TOBS|MOGO|20260817|001", "actor": "MOGO",
                   "sourceId": "EVSRC|MOGO|1", "strategyId": strategy_id,
                   "instrument": "GBP/USD", "fieldClassification": {},
                   "unknowns": [], "extractedBy": "x"}}


class TestASharedSpecificationIsNotATest(unittest.TestCase):

    def test_two_hypotheses_sharing_a_specification_are_both_blocked(self):
        shared = {"H1": hyp("H1", replay="same"), "H2": hyp("H2", replay="same")}
        unique = ht.discriminating_specs(shared)
        self.assertEqual(unique, set())
        for h in shared.values():
            verdict, blockers, _ = ht.assess(h, unique, {"TJR"}, {"TJR"})
            self.assertIn(ht.NON_DISCRIMINATING_TEST,
                          [b["blocker"] for b in blockers])

    def test_positive_control_a_unique_specification_is_not_blocked_for_that(self):
        distinct = {"H1": hyp("H1", replay="one"), "H2": hyp("H2", replay="two")}
        unique = ht.discriminating_specs(distinct)
        self.assertEqual(len(unique), 2)
        for h in distinct.values():
            _, blockers, _ = ht.assess(h, unique, {"TJR"}, {"TJR"})
            self.assertNotIn(ht.NON_DISCRIMINATING_TEST,
                             [b["blocker"] for b in blockers])

    def test_repetition_is_measured_not_pattern_matched(self):
        """Rewording the boilerplate must not make it look discriminating."""
        reworded = {"H%d" % i: hyp("H%d" % i, replay="a totally different sentence")
                    for i in range(5)}
        self.assertEqual(ht.discriminating_specs(reworded), set())

    def test_a_spec_differing_only_in_variables_still_counts_as_distinct(self):
        pair = {"H1": hyp("H1", replay="same", independent=("entry_rule",)),
                "H2": hyp("H2", replay="same", independent=("risk_rule",))}
        self.assertEqual(len(ht.discriminating_specs(pair)), 2)


class TestAnImplementationIsNotTheTrader(unittest.TestCase):

    def test_mogo_replay_evidence_does_not_satisfy_an_ALEX_G_hypothesis(self):
        """`alex_g_sr_v1` is MOGO's implementation. ALEX_G is a person. Evidence
        about the first is not evidence about the second."""
        h = hyp("H1", claims=("CLAIM|ALEX_G|1",))
        actors = ht.observation_actors(obs("alex_g_sr_v1"), SOURCES)
        self.assertNotIn("ALEX_G", actors)
        _, blockers, _ = ht.assess(h, {ht._spec_of(h)}, actors, {"ALEX_G"})
        self.assertIn(ht.NO_EVIDENCE_POPULATION, [b["blocker"] for b in blockers])

    def test_positive_control_evidence_for_the_actor_removes_that_blocker(self):
        h = hyp("H1", claims=("CLAIM|ALEX_G|1",))
        actors = ht.observation_actors(obs("ALEX_G"), SOURCES)
        verdict, blockers, _ = ht.assess(h, {ht._spec_of(h)}, actors, {"ALEX_G"})
        self.assertEqual(blockers, [])
        self.assertEqual(verdict, ht.TESTABLE)

    def test_claim_actors_are_read_from_the_claim_ids(self):
        h = hyp("H1", claims=("CLAIM|TJR|1", "CLAIM|ALEX_G|2"))
        self.assertEqual(ht.claim_actors(h), {"TJR", "ALEX_G"})


class TestEveryBlockerIsReported(unittest.TestCase):

    def test_a_hypothesis_blocked_three_ways_reports_three(self):
        h = hyp("H1", replay="shared", claims=("CLAIM|TJR|1",),
                limitations=["Derived from an unresolved ContradictionRecord "
                             "(XCONTRA|20260727|003) -- requires owner review."])
        other = hyp("H2", replay="shared")
        unique = ht.discriminating_specs({"H1": h, "H2": other})
        verdict, blockers, _ = ht.assess(h, unique, {}, {"TJR"})
        kinds = {b["blocker"] for b in blockers}
        self.assertEqual(kinds, {ht.NO_EVIDENCE_POPULATION,
                                 ht.UNRESOLVED_CONTRADICTION,
                                 ht.NON_DISCRIMINATING_TEST})

    def test_the_primary_verdict_is_the_most_fundamental_blocker(self):
        """Missing evidence outranks a weak specification: writing a better test
        for a hypothesis with nothing to test it against changes nothing."""
        h = hyp("H1", replay="shared")
        other = hyp("H2", replay="shared")
        unique = ht.discriminating_specs({"H1": h, "H2": other})
        verdict, _, _ = ht.assess(h, unique, {}, {"TJR"})
        self.assertEqual(verdict, ht.NO_EVIDENCE_POPULATION)

    def test_evidence_of_the_wrong_kind_alone_is_reported_as_such(self):
        h = hyp("H1", claims=("CLAIM|ALEX_G|1",))
        actors = ht.observation_actors(obs("alex_g_sr_v1"), SOURCES)
        verdict, blockers, _ = ht.assess(h, {ht._spec_of(h)}, actors, {"ALEX_G"})
        self.assertEqual(verdict, ht.TESTABLE_AGAINST_IMPLEMENTATION)
        self.assertEqual(len(blockers), 1)
        self.assertIn("IMPLEMENTATION", ht.VERDICT_MEANING[verdict])


class TestAgainstTheRealCorpus(unittest.TestCase):

    def setUp(self):
        self.summary = ht.what_is_still_required()

    def test_no_hypothesis_is_currently_testable(self):
        """The finding, pinned. If this ever fails, real evidence arrived and the
        result should be examined rather than the test adjusted."""
        self.assertEqual(self.summary["byVerdict"].get(ht.TESTABLE, 0), 0)

    def test_almost_no_specification_is_unique(self):
        self.assertLess(self.summary["discriminatingSpecifications"],
                        self.summary["hypotheses"] * 0.05)

    def test_every_hypothesis_carries_at_least_one_blocker(self):
        results = ht.triage()
        for result in results.values():
            self.assertGreaterEqual(result["blockerCount"], 1)

    def test_the_observations_we_hold_are_mogo_implementations_not_traders(self):
        held = self.summary["tradeObservationsHeldFor"]
        self.assertIn("alex_g_sr_v1", held)
        for human in ("TJR", "ALEX_G", "RAYNER_TEO"):
            self.assertNotIn(human, held)


class TestTheAcquisitionQueueCoversTheBindingConstraint(unittest.TestCase):
    """MOGO-022 priority 7. The queue is only useful if it records what is actually
    blocking research. Every trader whose hypotheses are untestable for want of
    OBSERVED TRADES must have an acquisition gap saying so -- otherwise the queue
    describes the rule questions while omitting the constraint that dominates them."""

    def setUp(self):
        self.results = ht.triage()
        self.gaps = [json.load(open(f)) for f in sorted(glob.glob(
            os.path.join(ht.EVIDENCE_ROOT, "gaps", "*.json")))]

    def blocked_traders(self):
        out = set()
        for result in self.results.values():
            if any(b["blocker"] == ht.NO_EVIDENCE_POPULATION
                   for b in result["blockers"]):
                out |= set(result["claimActors"])
        return out

    def test_every_blocked_trader_has_an_observed_trade_evidence_gap(self):
        covered = {g["traderId"] for g in self.gaps
                   if g.get("category") == "observed_trade_evidence"}
        missing = self.blocked_traders() - covered
        self.assertEqual(missing, set(),
                         "no acquisition gap records the missing trade evidence for: "
                         "%s" % sorted(missing))

    def test_the_precondition_holds_there_are_blocked_traders(self):
        """Without this, the test above passes vacuously the moment the triage
        stops finding anything."""
        self.assertTrue(self.blocked_traders())

    def test_those_gaps_ask_for_trade_records_not_another_transcript(self):
        """A further transcript cannot close this class of gap. If the recommended
        next source were another transcript, the queue would send acquisition effort
        somewhere that cannot resolve it."""
        for gap in self.gaps:
            if gap.get("category") != "observed_trade_evidence":
                continue
            recommended = (gap.get("recommendedNextSourceType") or "").lower()
            self.assertTrue(
                any(k in recommended for k in ("screenshot", "trade record",
                                               "journal")),
                "%s recommends %r, which cannot close an observed-trade gap"
                % (gap["gapId"], gap.get("recommendedNextSourceType")))
            self.assertEqual(gap.get("answerStatus"), "unanswered")


class TestItWritesNothing(unittest.TestCase):

    def test_triage_mutates_no_evidence_file(self):
        roots = [os.path.join(ht.EVIDENCE_ROOT, d)
                 for d in ("hypotheses", "observations", "sources", "claims",
                           "proposals")]

        def digest():
            out = {}
            for root in roots:
                for path in sorted(glob.glob(os.path.join(root, "*.json"))):
                    with open(path, "rb") as handle:
                        out[path] = hashlib.sha256(handle.read()).hexdigest()
            return out

        before = digest()
        ht.triage()
        ht.what_is_still_required()
        self.assertEqual(digest(), before)

    def test_the_summary_declares_it_adjudicates_nothing(self):
        summary = ht.what_is_still_required()
        self.assertFalse(summary["adjudicates"])
        self.assertEqual(summary["lane"], "RESEARCH")


if __name__ == "__main__":
    unittest.main()

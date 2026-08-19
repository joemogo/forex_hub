"""Could a strategy actually be REBUILT from this candidate? (MOGO-022)"""
import glob as globmod
import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                         "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts", "trader_intelligence"))

import reconstructability as rc      # noqa: E402

CANDIDATES = os.path.join(REPO_ROOT, "docs", "trader-intelligence", "acquisition",
                          "candidates", "*.json")


def candidate(cid="CAND|T|1", trader="TJR", policy="METADATA_ONLY",
              content_hash=None, facts=None, title="Some video"):
    record = {"candidateId": cid, "claimedTraderId": trader, "title": title,
              "storagePolicy": policy, "contentHash": content_hash}
    if facts is not None:
        record["tradeFactsPresent"] = facts
    return record


ALL_ANCHORS = {"entry": True, "stop": True, "target": True, "outcome": True,
               "direction": True, "instrument": True, "timeframe": True,
               "timestamp": True}


class TestContentIsWhatDecides(unittest.TestCase):

    def test_metadata_only_means_no_content_however_rich_the_metadata(self):
        self.assertFalse(rc.content_acquired(
            candidate(policy="METADATA_ONLY", content_hash="h1")))

    def test_a_content_hash_with_a_storing_policy_means_content_is_held(self):
        self.assertTrue(rc.content_acquired(
            candidate(policy="COMMITTED_OWNER_CONTENT", content_hash="h1")))

    def test_no_content_hash_means_no_content(self):
        self.assertFalse(rc.content_acquired(
            candidate(policy="COMMITTED_OWNER_CONTENT", content_hash=None)))


class TestUnacquiredContentIsUNKNOWNNotLow(unittest.TestCase):
    """The distinction the whole assessment turns on."""

    def test_an_unacquired_candidate_is_UNKNOWN(self):
        verdict, known, unknown = rc.assess(candidate())
        self.assertEqual(verdict, rc.CONTENT_NOT_ACQUIRED)
        self.assertEqual(known, [])
        self.assertEqual(set(unknown), set(rc.TRADE_FACTS))

    def test_a_promising_TITLE_does_not_make_it_reconstructable(self):
        """A video called "Stop Losses" is not evidence that it states a stop rule.
        This is the exact inference the assessment exists to refuse."""
        verdict, known, _unknown = rc.assess(
            candidate(title="Boot Camp Day 38: Stop Losses -- entry, stop and target"))
        self.assertEqual(verdict, rc.CONTENT_NOT_ACQUIRED)
        self.assertEqual(known, [])

    def test_it_is_not_reported_as_NOT_reconstructable(self):
        """UNKNOWN and NOT-RECONSTRUCTABLE are different claims. Collapsing them
        would write off sources that were simply never fetched."""
        verdict, _k, _u = rc.assess(candidate())
        self.assertNotEqual(verdict, rc.NO_TRADE_LEVEL_DETAIL)
        self.assertNotEqual(verdict, rc.CONTENT_NOT_RETRIEVABLE)


class TestVerdictsOnAcquiredContent(unittest.TestCase):

    def acquired(self, facts):
        return candidate(policy="COMMITTED_OWNER_CONTENT", content_hash="h1",
                         facts=facts)

    def test_all_four_anchors_present_is_reconstructable(self):
        verdict, known, _u = rc.assess(self.acquired(ALL_ANCHORS))
        self.assertEqual(verdict, rc.RECONSTRUCTABLE)
        self.assertEqual(set(known), set(rc.TRADE_FACTS))

    def test_a_missing_anchor_is_only_PARTIAL(self):
        facts = dict(ALL_ANCHORS, stop=False)
        verdict, _k, unknown = rc.assess(self.acquired(facts))
        self.assertEqual(verdict, rc.PARTIAL)
        self.assertIn("stop", unknown)

    def test_content_stating_no_trade_facts_is_not_reconstructable(self):
        verdict, known, _u = rc.assess(self.acquired({f: False for f in rc.TRADE_FACTS}))
        self.assertEqual(verdict, rc.NO_TRADE_LEVEL_DETAIL)
        self.assertEqual(known, [])

    def test_partial_is_never_promoted_to_reconstructable(self):
        """Reconstruction from a partial set would require inventing the missing
        rules, which is exactly what is not permitted."""
        for missing in ("entry", "stop", "target", "outcome"):
            facts = dict(ALL_ANCHORS)
            facts[missing] = False
            verdict, _k, _u = rc.assess(self.acquired(facts))
            self.assertEqual(verdict, rc.PARTIAL, "missing %s was still called "
                             "reconstructable" % missing)


class TestTheReportNamesTheBindingConstraint(unittest.TestCase):

    def test_with_nothing_acquired_the_constraint_is_ACQUISITION(self):
        r = rc.report([candidate(cid="CAND|T|%d" % i) for i in range(3)])
        self.assertEqual(r["assessableOnContent"], 0)
        self.assertIn("ACQUISITION", r["bindingConstraint"])

    def test_with_content_the_constraint_becomes_ANALYSIS(self):
        """Positive control: the sentence above must be caused by the evidence, not
        be a constant."""
        acquired = candidate(cid="CAND|T|9", policy="COMMITTED_OWNER_CONTENT",
                             content_hash="h1", facts=ALL_ANCHORS)
        r = rc.report([candidate(), acquired])
        self.assertEqual(r["assessableOnContent"], 1)
        self.assertIn("ANALYSIS", r["bindingConstraint"])

    def test_every_candidate_lands_in_exactly_one_verdict(self):
        r = rc.report([candidate(cid="CAND|T|%d" % i) for i in range(5)])
        self.assertEqual(sum(r["byVerdict"].values()), r["candidates"])
        self.assertEqual(len(r["rows"]), r["candidates"])

    def test_it_declares_that_it_mutates_nothing(self):
        r = rc.report([candidate()])
        self.assertFalse(r["mutatesCandidates"])
        self.assertFalse(r["adjudicates"])


class TestItIsReadOnly(unittest.TestCase):
    """Runs against a fixture this test writes itself -- a copy of live data can
    already carry a sibling's mutation, which is how two earlier read-only tests in
    this repository passed against the very defect they existed to catch."""

    def test_assessing_does_not_modify_any_candidate(self):
        root = tempfile.mkdtemp(prefix="mogo_recon_ro_")
        try:
            for i in range(3):
                record = candidate(cid="CAND|T|%d" % i)
                with open(os.path.join(root, "c%d.json" % i), "w",
                          encoding="utf-8") as handle:
                    json.dump(record, handle)
            pattern = os.path.join(root, "*.json")

            def fingerprint():
                return {os.path.basename(p): hashlib.sha256(
                    open(p, "rb").read()).hexdigest()
                    for p in sorted(globmod.glob(pattern))}

            before = fingerprint()
            r = rc.report(pattern=pattern)
            self.assertEqual(r["candidates"], 3, "fixture not read -- test vacuous")
            self.assertEqual(fingerprint(), before, "a candidate was modified")
        finally:
            shutil.rmtree(root, ignore_errors=True)


class TestAgainstTheLiveRegistry(unittest.TestCase):

    def test_the_live_registry_is_assessed_without_inventing_anything(self):
        r = rc.report()
        self.assertGreater(r["candidates"], 0)
        # Whatever the counts are, no candidate may be called reconstructable while
        # its content has never been acquired.
        for row in r["rows"]:
            if row["verdict"] == rc.CONTENT_NOT_ACQUIRED:
                self.assertEqual(row["knownTradeFacts"], [],
                                 "%s claims trade facts with no acquired content"
                                 % row["candidateId"])


if __name__ == "__main__":
    unittest.main()

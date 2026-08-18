"""Review by exception, without touching a single governance control (MOGO-022)."""
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

import acquisition_triage as at      # noqa: E402

CANDIDATES = os.path.join(REPO_ROOT, "docs", "trader-intelligence", "acquisition",
                          "candidates", "*.json")


def candidate(candidate_id, trader="TJR", source_type="VIDEO", url="https://x/y",
              status="OWNER_REVIEW"):
    return {"candidateId": candidate_id, "claimedTraderId": trader,
            "sourceType": source_type, "normalizedUrl": url,
            "acquisitionStatus": status}


class TestItIsReadOnly(unittest.TestCase):
    """The load-bearing property. This tool exists inside a governance boundary and
    its entire licence is that it reports rather than decides."""

    def fingerprint(self, pattern):
        out = {}
        for path in sorted(globmod.glob(pattern)):
            with open(path, "rb") as handle:
                out[os.path.basename(path)] = hashlib.sha256(handle.read()).hexdigest()
        return out

    def test_triage_does_not_modify_any_candidate(self):
        """Run against a fixture this test WRITES ITSELF.

        Two weaker versions of this test both passed against a mutation that makes
        triage advance a candidate's status:

          1. Fingerprinting the live directory -- a sibling test calls triage()
             first (method names sort that way), so the write was already applied
             before the "before" snapshot was taken.
          2. Copying the live directory -- the sibling had already mutated the
             SOURCE, so the copy inherited the mutation and re-writing it produced
             identical bytes.

        Only data that no other test can have touched actually constrains this.
        Same defect shape as the evidence-tree read-only test earlier in this
        milestone, which is why it is spelled out rather than just fixed.
        """
        root = tempfile.mkdtemp(prefix="mogo_triage_ro_")
        try:
            fixtures = [candidate("CAND|T|1", trader="TJR"),
                        candidate("CAND|T|2", trader=None),
                        candidate("CAND|T|3", source_type="PLAYLIST")]
            for record in fixtures:
                name = record["candidateId"].replace("|", "_") + ".json"
                with open(os.path.join(root, name), "w", encoding="utf-8") as handle:
                    json.dump(record, handle, indent=2)
            pattern = os.path.join(root, "*.json")
            before = self.fingerprint(pattern)
            self.assertEqual(len(before), len(fixtures))

            report = at.triage(pattern=pattern)
            self.assertEqual(report["candidatesInOwnerReview"], len(fixtures),
                             "the fixture was not actually read -- test would be vacuous")
            self.assertEqual(self.fingerprint(pattern), before,
                             "triage modified a candidate record")
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_the_report_declares_that_it_mutates_nothing(self):
        report = at.triage()
        self.assertFalse(report["mutatesCandidates"])
        self.assertFalse(report["adjudicates"])


class TestBucketsAreDerivedNotListed(unittest.TestCase):
    """Derived from record FIELDS. A hardcoded id list would be a snapshot that
    stops matching the moment the corpus grows -- the defect class this repository
    has fixed repeatedly."""

    def test_an_unattributed_candidate_is_a_durable_negative_record(self):
        self.assertEqual(at.bucket_of(candidate("C|1", trader=None)),
                         at.DURABLE_NEGATIVE_RECORD)

    def test_a_playlist_has_no_expansion_connector(self):
        self.assertEqual(at.bucket_of(candidate("C|2", source_type="PLAYLIST")),
                         at.NO_EXPANSION_CONNECTOR)

    def test_a_sitemap_has_no_expansion_connector(self):
        self.assertEqual(
            at.bucket_of(candidate("C|3", url="https://e.com/post-sitemap.xml")),
            at.NO_EXPANSION_CONNECTOR)

    def test_an_ordinary_video_awaits_an_owner_decision(self):
        self.assertEqual(at.bucket_of(candidate("C|4")), at.AWAITING_OWNER_ACQUISITION)

    def test_unattributed_wins_over_playlist(self):
        """Order matters: an unattributed playlist is a negative record first."""
        self.assertEqual(
            at.bucket_of(candidate("C|5", trader=None, source_type="PLAYLIST")),
            at.DURABLE_NEGATIVE_RECORD)

    def test_a_new_candidate_is_bucketed_without_any_code_change(self):
        report = at.triage(candidates=[candidate("C|NEW|999", trader="SOMEONE_NEW")])
        self.assertEqual(report["candidatesInOwnerReview"], 1)
        self.assertIn("SOMEONE_NEW",
                      report["buckets"][at.AWAITING_OWNER_ACQUISITION]["byTrader"])


class TestItPartitions(unittest.TestCase):

    def test_every_reviewed_candidate_lands_in_exactly_one_bucket(self):
        report = at.triage()
        total = sum(b["count"] for b in report["buckets"].values())
        self.assertEqual(total, report["candidatesInOwnerReview"])
        seen = [cid for b in report["buckets"].values() for cid in b["candidateIds"]]
        self.assertEqual(len(seen), len(set(seen)), "a candidate is in two buckets")

    def test_candidates_not_in_owner_review_are_excluded(self):
        report = at.triage(candidates=[
            candidate("C|1"), candidate("C|2", status="REGISTERED")])
        self.assertEqual(report["candidatesInOwnerReview"], 1)

    def test_it_reports_fewer_decisions_than_records(self):
        """The whole point: the operator reviews decisions, not records."""
        report = at.triage()
        self.assertGreater(report["candidatesInOwnerReview"],
                           report["distinctAcquisitionDecisions"])
        self.assertGreater(report["distinctAcquisitionDecisions"], 0)


if __name__ == "__main__":
    unittest.main()

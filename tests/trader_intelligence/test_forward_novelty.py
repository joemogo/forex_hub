"""Which recovered packages count as NEW (MOGO-022).

Fixtures only. Every case here corresponds to a defect that actually reached live
use, or to the boundary that would let one back in.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                         "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts", "trader_intelligence"))

import forward_novelty as fn      # noqa: E402


def package(content_hash, package_id="PKG|s|20260101|1"):
    return {"packageId": package_id, "contentHash": content_hash,
            "captureBasis": "LIVE_CLOSE", "objects": {"positions": [{}]}}


class NoveltyCase(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="mogo_novelty_")
        self.obs_dir = os.path.join(self.root, "observations")
        self.staged_dir = os.path.join(self.root, "staged")
        os.makedirs(self.obs_dir)
        os.makedirs(self.staged_dir)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def observation(self, name, content_hash):
        path = os.path.join(self.obs_dir, name + ".json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"observationId": "TOBS|MOGO|%s" % name,
                       "sourceContentHash": content_hash}, handle)

    def staged(self, name, hashes):
        path = os.path.join(self.staged_dir, name + "-PACKAGES.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump([package(h) for h in hashes], handle)

    def select(self, recovered):
        return fn.select_new(recovered,
                             observations_glob=os.path.join(self.obs_dir, "*.json"),
                             staged_glob=os.path.join(self.staged_dir, "*-PACKAGES.json"))


class TestTheBasicRule(NoveltyCase):

    def test_an_unseen_package_is_new(self):
        self.assertEqual(len(self.select([package("aa")])), 1)

    def test_an_already_imported_package_is_not_new(self):
        self.observation("001", "aa")
        self.assertEqual(self.select([package("aa")]), [])

    def test_order_is_preserved(self):
        got = self.select([package("aa"), package("bb"), package("cc")])
        self.assertEqual([p["contentHash"] for p in got], ["aa", "bb", "cc"])


class TestTheDefectsThatReachedLiveUse(NoveltyCase):

    def test_the_whole_store_is_not_re_presented_as_fresh(self):
        """DEFECT 1. Recovery reconstructs every package in the store. Of 27
        recovered with 26 already imported, exactly ONE is new -- not 27."""
        for i in range(26):
            self.observation("%03d" % i, "h%02d" % i)
        recovered = [package("h%02d" % i) for i in range(26)] + [package("NEW")]
        got = self.select(recovered)
        self.assertEqual([p["contentHash"] for p in got], ["NEW"])

    def test_a_package_already_staged_in_a_capture_file_is_not_new(self):
        """DEFECT 2, and the one that actually minted a bad record. A dry run left
        its capture file behind; the next --write run staged the same package
        twice and the importer minted two observations for it."""
        self.staged("FWD-earlier", ["aa"])
        self.assertEqual(self.select([package("aa")]), [])

    def test_staged_and_imported_are_both_consulted(self):
        self.observation("001", "aa")
        self.staged("FWD-earlier", ["bb"])
        got = self.select([package("aa"), package("bb"), package("cc")])
        self.assertEqual([p["contentHash"] for p in got], ["cc"])

    def test_a_duplicate_within_one_batch_is_not_counted_twice(self):
        """The same defect's third form: one recovery yielding the same hash twice
        must still produce one record."""
        got = self.select([package("aa", "PKG|s|1"), package("aa", "PKG|s|2")])
        self.assertEqual(len(got), 1)


class TestTheKeyIsContentHashNotPackageId(NoveltyCase):

    def test_identical_package_ids_with_different_hashes_are_both_new(self):
        """packageId ordinals only count within one capture run, so packageId is
        not a global identity. De-duplicating on it once dropped 21 of 25 real
        forward records."""
        got = self.select([package("aa", "PKG|s|20260101|1"),
                           package("bb", "PKG|s|20260101|1")])
        self.assertEqual(len(got), 2)

    def test_different_package_ids_with_the_same_hash_are_one(self):
        got = self.select([package("aa", "PKG|s|20260101|1"),
                           package("aa", "PKG|s|20260102|7")])
        self.assertEqual(len(got), 1)


class TestItRefusesRatherThanGuesses(NoveltyCase):

    def test_a_package_with_no_content_hash_is_REFUSED(self):
        with self.assertRaises(fn.NoveltyRefused):
            self.select([{"packageId": "PKG|s|1"}])

    def test_a_hashless_package_does_not_silently_pass_through(self):
        """Positive control for the refusal: without it the package would be
        treated as new and land in the corpus unverifiable."""
        try:
            got = self.select([package("aa"), {"packageId": "PKG|s|2"}])
        except fn.NoveltyRefused:
            return
        self.fail("a hashless package was accepted: %r" % got)

    def test_a_missing_recovered_list_is_REFUSED(self):
        with self.assertRaises(fn.NoveltyRefused):
            self.select(None)


if __name__ == "__main__":
    unittest.main()


def developer_package(content_hash, marker="tradeId", package_id="PKG|s|20260101|1"):
    """A package the importer refuses. `marker` selects WHICH of the three
    independent markers is present, because any one of them may be the only one on
    an older record."""
    pkg = package(content_hash, package_id)
    if marker == "tradeId":
        pkg["sourceTradeId"] = "AGT|TEST|1783897900066-459503"
    elif marker == "isDeveloperTrade":
        pkg["objects"]["positions"] = [{"isDeveloperTrade": True}]
    elif marker == "tradeSource":
        pkg["objects"]["positions"] = [{"tradeSource": "TEST"}]
    else:
        raise AssertionError("unknown marker %r" % marker)
    return pkg


class TestRefusedIsNotPending(NoveltyCase):
    """B-31. Four developer test trades sat in `pending` forever because the importer
    refuses them by policy and they could therefore never clear.

    Why that mattered more than the noise: PENDING is the alarm that says a real close
    was stranded, and an alarm with a permanent floor of 4 cannot ring. The next
    stranded close would have read "5 pending" and looked like the steady state."""

    def classify(self, recovered):
        return fn.classify_recovered(
            recovered,
            observations_glob=os.path.join(self.obs_dir, "*.json"),
            staged_glob=os.path.join(self.staged_dir, "*-PACKAGES.json"))

    def test_a_staged_developer_trade_is_refused_NOT_pending(self):
        # The live condition exactly: staged, unimported, unimportable.
        self.staged("cap", [])
        path = os.path.join(self.staged_dir, "cap-PACKAGES.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump([developer_package("dd")], handle)
        fresh, pending, refused = self.classify([developer_package("dd")])
        self.assertEqual(len(refused), 1)
        self.assertEqual(len(pending), 0, "a package that can never import is not pending work")
        self.assertEqual(len(fresh), 0)

    def test_an_unstaged_developer_trade_is_refused_NOT_fresh(self):
        # Excluded from fresh too: staging one creates a capture file that can never
        # import, which is how the permanent-pending state arose in the first place.
        fresh, pending, refused = self.classify([developer_package("dd")])
        self.assertEqual((len(fresh), len(pending), len(refused)), (0, 0, 1))

    def test_each_of_the_three_markers_independently_refuses(self):
        for marker in ("tradeId", "isDeveloperTrade", "tradeSource"):
            with self.subTest(marker=marker):
                fresh, _pending, refused = self.classify(
                    [developer_package("dd", marker=marker)])
                self.assertEqual(len(refused), 1, "marker %s did not refuse" % marker)
                self.assertEqual(len(fresh), 0)

    def test_POSITIVE_CONTROL_a_real_package_is_still_fresh(self):
        # Without this, a predicate that refused EVERYTHING would pass every
        # assertion above and silently stop capturing real forward closes.
        fresh, pending, refused = self.classify([package("aa")])
        self.assertEqual((len(fresh), len(pending), len(refused)), (1, 0, 0))

    def test_POSITIVE_CONTROL_a_real_package_survives_alongside_a_refused_one(self):
        # The discriminating case: same batch, one refused and one kept, so the
        # exclusion is shown to be selective rather than total.
        fresh, _pending, refused = self.classify(
            [developer_package("dd"), package("aa", package_id="PKG|s|20260101|2")])
        self.assertEqual([p["contentHash"] for p in fresh], ["aa"])
        self.assertEqual([p["contentHash"] for p in refused], ["dd"])

    def test_a_real_staged_package_is_still_pending(self):
        # The B-31 fix must not disarm the stranded-close alarm it exists to protect.
        self.staged("cap", ["aa"])
        fresh, pending, refused = self.classify([package("aa")])
        self.assertEqual((len(fresh), len(pending), len(refused)), (0, 1, 0))

    def test_the_refusal_test_is_the_IMPORTERS_not_a_copy(self):
        # Two definitions of "developer trade" would drift, and the direction that
        # matters -- the pipeline believing one is importable -- is unnoticeable.
        import import_mogo_observations as importer
        self.assertIs(fn.is_developer_test_package,
                      importer.is_developer_test_package)

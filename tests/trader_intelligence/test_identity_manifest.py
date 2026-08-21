"""MOGO's append-only trade-identity manifest (B-32.14, operator option A).

The anchor that closes the fifth category -- append-only enforced in AGGREGATE was
not append-only at all, because no gate asked WHICH trades existed. Its predecessor
covered 13.5% of the corpus and decayed, because the script that wrote it was
invoked by nothing.

Everything here builds packages the test authors itself. Reading the live store
would make these assertions depend on whatever the running instance happened to
hold that hour -- the failure mode this repository has found repeatedly.
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

import identity_manifest as im      # noqa: E402
import validate_evidence as ve      # noqa: E402


def package(trade_id, content_hash="a" * 64, basis="LIVE_CLOSE"):
    return {"sourceTradeId": trade_id, "contentHash": content_hash,
            "captureBasis": basis}


class ManifestCase(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="mogo_manifest_")
        self.path = os.path.join(self.root, "MOGO_IDENTITY_MANIFEST.json")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def ids(self):
        return [row["tradeId"] for row in im.load(self.path)["identities"]]


class TestAppendOnly(ManifestCase):

    def test_a_recorded_identity_is_never_removed(self):
        # The property the whole anchor rests on: a trade that existed cannot stop
        # having existed, so a later capture that no longer sees it must not drop it.
        im.update_from_packages([package("T1"), package("T2")], self.path)
        im.update_from_packages([package("T2")], self.path)
        self.assertEqual(self.ids(), ["T1", "T2"])

    def test_an_empty_capture_removes_nothing(self):
        im.update_from_packages([package("T1")], self.path)
        im.update_from_packages([], self.path)
        self.assertEqual(self.ids(), ["T1"])

    def test_new_identities_accumulate_across_captures(self):
        # Coverage must GROW with the system. The predecessor manifest froze at one
        # snapshot and decayed from 100% to 13.5% as trades accrued.
        for i in range(4):
            im.update_from_packages([package("T%d" % i, content_hash="%064d" % i)],
                                    self.path)
        self.assertEqual(self.ids(), ["T0", "T1", "T2", "T3"])

    def test_re_running_the_same_capture_changes_nothing(self):
        result = im.update_from_packages([package("T1"), package("T2")], self.path)
        self.assertEqual(len(result["added"]), 2)
        again = im.update_from_packages([package("T1"), package("T2")], self.path)
        self.assertEqual(again["added"], [])
        self.assertEqual(again["before"], again["after"])


class TestItInventsNothing(ManifestCase):

    def test_a_package_with_no_trade_id_is_skipped(self):
        # Synthesising an id would be the fabrication this layer exists to prevent.
        im.update_from_packages([{"contentHash": "a" * 64}, package("T1")], self.path)
        self.assertEqual(self.ids(), ["T1"])

    def test_a_blank_or_non_string_trade_id_is_skipped(self):
        im.update_from_packages([package(""), package("   "), package(None),
                                 package(123), package(["T"]), package("T1")],
                                self.path)
        self.assertEqual(self.ids(), ["T1"])

    def test_a_non_dict_package_does_not_raise(self):
        im.update_from_packages(["nonsense", None, 5, package("T1")], self.path)
        self.assertEqual(self.ids(), ["T1"])


class TestConflictsAreReportedNotAbsorbed(ManifestCase):
    """A tradeId arriving with a DIFFERENT contentHash is the signature of a
    rewritten package. Taking the newer value would let it launder itself into the
    very manifest that is supposed to anchor it."""

    def test_the_first_recorded_hash_is_kept(self):
        im.update_from_packages([package("T1", content_hash="a" * 64)], self.path)
        im.update_from_packages([package("T1", content_hash="b" * 64)], self.path)
        rows = im.load(self.path)["identities"]
        self.assertEqual(rows[0]["contentHash"], "a" * 64)

    def test_the_conflict_is_reported(self):
        im.update_from_packages([package("T1", content_hash="a" * 64)], self.path)
        result = im.update_from_packages([package("T1", content_hash="b" * 64)],
                                         self.path)
        self.assertEqual(len(result["conflicts"]), 1)
        self.assertEqual(result["conflicts"][0]["tradeId"], "T1")

    def test_POSITIVE_CONTROL_the_same_hash_is_not_a_conflict(self):
        im.update_from_packages([package("T1", content_hash="a" * 64)], self.path)
        result = im.update_from_packages([package("T1", content_hash="a" * 64)],
                                         self.path)
        self.assertEqual(result["conflicts"], [])

    def test_the_CLI_exits_nonzero_on_a_conflict(self):
        # A conflict that only prints is a conflict nothing gates on -- the defect
        # this repository found four times in other validators.
        capture = os.path.join(self.root, "pkgs.json")
        with open(capture, "w", encoding="utf-8") as handle:
            json.dump([package("T1", content_hash="a" * 64)], handle)
        self.assertEqual(im.main(["--packages", capture, "--manifest", self.path]), 0)
        with open(capture, "w", encoding="utf-8") as handle:
            json.dump([package("T1", content_hash="b" * 64)], handle)
        self.assertEqual(im.main(["--packages", capture, "--manifest", self.path]), 1)


class TestCrashAndPartialPersistence(ManifestCase):
    """Interrupted writes, retries and rollback must fail safely and be detectable."""

    def test_an_interrupted_write_leaves_the_PREVIOUS_manifest_intact(self):
        # Atomic rename: a crash mid-write leaves the old file or the new one, never
        # a truncated one. A truncated manifest reads as identities that never
        # existed, which is the exact failure this anchor must not have.
        im.update_from_packages([package("T1"), package("T2")], self.path)
        original = open(self.path, encoding="utf-8").read()
        real_write = im.gc.atomic_write_text

        def explode(path, text):
            raise IOError("simulated crash mid-write")

        im.gc.atomic_write_text = explode
        try:
            with self.assertRaises(IOError):
                im.update_from_packages([package("T3")], self.path)
        finally:
            im.gc.atomic_write_text = real_write
        self.assertEqual(open(self.path, encoding="utf-8").read(), original)
        self.assertEqual(self.ids(), ["T1", "T2"])

    def test_a_retry_after_a_crash_converges(self):
        im.update_from_packages([package("T1")], self.path)
        real_write = im.gc.atomic_write_text
        im.gc.atomic_write_text = lambda p, t: (_ for _ in ()).throw(IOError("crash"))
        try:
            with self.assertRaises(IOError):
                im.update_from_packages([package("T2")], self.path)
        finally:
            im.gc.atomic_write_text = real_write
        im.update_from_packages([package("T2")], self.path)      # retry
        self.assertEqual(self.ids(), ["T1", "T2"])

    def test_a_truncated_manifest_is_REFUSED_not_silently_reset(self):
        # Silently starting fresh would erase every identity ever recorded -- the
        # anchor would delete itself in response to damage.
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write('{"schemaVersion": "mogo.identity-mani')
        with self.assertRaises(ValueError):
            im.load(self.path)

    def test_a_manifest_without_an_identities_list_is_REFUSED(self):
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump({"schemaVersion": im.SCHEMA_VERSION}, handle)
        with self.assertRaises(ValueError):
            im.load(self.path)

    def test_a_non_object_manifest_is_REFUSED(self):
        for document in ([], "x", 5, None):
            with self.subTest(document=document):
                with open(self.path, "w", encoding="utf-8") as handle:
                    json.dump(document, handle)
                with self.assertRaises(ValueError):
                    im.load(self.path)

    def test_an_absent_manifest_starts_empty_rather_than_failing(self):
        # A first run has nothing to load; that is not damage.
        self.assertEqual(im.load(self.path)["identities"], [])

    def test_reordered_input_produces_an_IDENTICAL_manifest(self):
        im.update_from_packages([package("T%d" % i, "%064d" % i) for i in range(5)],
                                self.path)
        first = open(self.path, encoding="utf-8").read()
        other = os.path.join(self.root, "other.json")
        im.update_from_packages(
            [package("T%d" % i, "%064d" % i) for i in reversed(range(5))], other)
        self.assertEqual(first, open(other, encoding="utf-8").read())


class TestTheProductionValidatorEnforcesIt(unittest.TestCase):
    """Through `run_integrity_checks`, not a reimplementation. Round 11 found five
    gates that were unit-tested and never asserted to be WIRED."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="mogo_manifest_prod_")
        self.evidence = os.path.join(self.root, "evidence")
        for name in ("sources", "observations", "ledger-preservation"):
            os.makedirs(os.path.join(self.evidence, name))
        os.makedirs(os.path.join(self.root, "research-state", "ledger"))
        self.write("sources", "src", {
            "sourceId": "EVSRC|MOGO|20260819|001", "sourceType": "paper_trade",
            "title": "capture", "storageLocationType": "repository",
            "provenanceStatus": "verified", "schemaVersion": 1,
            "metadata": {"captureBasis": "LIVE_CLOSE",
                         "engineStrategyId": "alex_g_sr_v1"}})

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def write(self, collection, name, record):
        with open(os.path.join(self.evidence, collection, name + ".json"),
                  "w", encoding="utf-8") as handle:
            json.dump(record, handle)

    def observation(self, oid, sequence_id):
        self.write("observations", oid.replace("|", "_"), {
            "observationId": oid, "sourceId": "EVSRC|MOGO|20260819|001",
            "schemaVersion": 1, "strategyId": "alex_g_sr_v1",
            "sourceContentHash": sequence_id + "-hash",
            "sequenceId": sequence_id,
            "notes": "captureBasis=LIVE_CLOSE sourceType=paper_trade"})

    def manifest(self, packages):
        im.update_from_packages(
            packages,
            os.path.join(self.evidence, "ledger-preservation",
                         "MOGO_IDENTITY_MANIFEST.json"))

    def finding_types(self):
        report = ve.run_integrity_checks(self.evidence, is_production=False)
        self.assertTrue(os.listdir(os.path.join(self.evidence, "observations")),
                        "vacuous run: no observations were loaded")
        return [f["findingType"] for f in report["findings"]]

    def test_a_manifest_identity_with_no_observation_is_reported(self):
        self.observation("TOBS|MOGO|20260819|001", "TRADE|1")
        self.manifest([package("TRADE|1"), package("TRADE|GONE", "b" * 64)])
        self.assertIn("PRESERVED_IDENTITY_MISSING", self.finding_types())

    def test_POSITIVE_CONTROL_a_fully_covered_corpus_is_silent(self):
        self.observation("TOBS|MOGO|20260819|001", "TRADE|1")
        self.manifest([package("TRADE|1")])
        self.assertNotIn("PRESERVED_IDENTITY_MISSING", self.finding_types())

    def test_the_manifest_written_by_the_pipeline_satisfies_the_validator(self):
        # End to end: what identity_manifest writes is what validate_evidence reads.
        # Two modules agreeing on a schema is not something to assume.
        self.observation("TOBS|MOGO|20260819|001", "TRADE|1")
        self.observation("TOBS|MOGO|20260819|002", "TRADE|2")
        self.manifest([package("TRADE|1"), package("TRADE|2")])
        self.assertNotIn("PRESERVED_IDENTITY_MISSING", self.finding_types())
        os.remove(os.path.join(self.evidence, "observations",
                               "TOBS_MOGO_20260819_002.json"))
        self.assertIn("PRESERVED_IDENTITY_MISSING", self.finding_types())


class TestLiveCoverage(unittest.TestCase):
    """Coverage stated as a RELATIONSHIP, not a snapshot count -- the anti-pattern
    this repository has been bitten by repeatedly."""

    def test_every_live_observation_identity_is_in_the_manifest(self):
        import glob
        ti = os.path.join(REPO_ROOT, "docs", "trader-intelligence")
        paths = glob.glob(os.path.join(ti, "evidence", "observations", "*.json"))
        self.assertGreater(len(paths), 50, "corpus glob matched almost nothing")
        sequence_ids = set()
        for path in paths:
            with open(path, encoding="utf-8") as handle:
                sequence_ids.add(json.load(handle).get("sequenceId"))
        recorded = set()
        for path in glob.glob(os.path.join(ti, "evidence", "ledger-preservation",
                                           "*.json")):
            with open(path, encoding="utf-8") as handle:
                document = json.load(handle)
            for row in document.get("identities") or []:
                if isinstance(row, dict) and isinstance(row.get("tradeId"), str):
                    recorded.add(row["tradeId"])
        uncovered = sorted(s for s in sequence_ids if s and s not in recorded)
        self.assertEqual(uncovered, [],
                         "these live observations have no identity anchor, so "
                         "deleting them would be invisible: %s" % uncovered[:5])


if __name__ == "__main__":
    unittest.main()


class TestFabricationByAppendIsDetected(unittest.TestCase):
    """The OTHER direction, askable only once coverage became continuous (B-32.15).

    Fourteen rounds asked "did something disappear". Nothing asked "did something
    APPEAR that was never observed" -- so appending a source and 200 invented winning
    observations moved forward mean R from -0.18 to +1.72 with every gate green and
    every preserved identity still present. Growth is what append-only expects, and a
    require-list cannot tell invented growth from real growth.

    Only an allow-list can, and an allow-list needs a manifest covering the whole
    corpus -- which is why this could not have been enabled before the coverage work
    and can be now.
    """

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="mogo_append_")
        self.evidence = os.path.join(self.root, "evidence")
        for name in ("sources", "observations", "ledger-preservation"):
            os.makedirs(os.path.join(self.evidence, name))
        os.makedirs(os.path.join(self.root, "research-state", "ledger"))
        self.write("sources", "src", {
            "sourceId": "EVSRC|MOGO|20260819|001", "sourceType": "paper_trade",
            "title": "capture", "storageLocationType": "repository",
            "provenanceStatus": "verified", "schemaVersion": 1,
            "metadata": {"captureBasis": "LIVE_CLOSE",
                         "engineStrategyId": "alex_g_sr_v1"}})

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def write(self, collection, name, record):
        with open(os.path.join(self.evidence, collection, name + ".json"),
                  "w", encoding="utf-8") as handle:
            json.dump(record, handle)

    def observation(self, oid, sequence_id):
        self.write("observations", oid.replace("|", "_"), {
            "observationId": oid, "sourceId": "EVSRC|MOGO|20260819|001",
            "schemaVersion": 1, "strategyId": "alex_g_sr_v1",
            "sourceContentHash": sequence_id + "-hash", "sequenceId": sequence_id,
            "notes": "captureBasis=LIVE_CLOSE sourceType=paper_trade"})

    def manifest(self, trade_ids):
        im.update_from_packages(
            [package(t, content_hash=t + "-hash") for t in trade_ids],
            os.path.join(self.evidence, "ledger-preservation",
                         "MOGO_IDENTITY_MANIFEST.json"))

    def types(self):
        report = ve.run_integrity_checks(self.evidence, is_production=False)
        self.assertTrue(os.listdir(os.path.join(self.evidence, "observations")),
                        "vacuous run: no observations were loaded")
        return [f["findingType"] for f in report["findings"]]

    def test_an_observation_anchored_by_no_manifest_is_an_ERROR(self):
        self.observation("TOBS|MOGO|20260819|001", "TRADE|real")
        self.observation("TOBS|MOGO|29990101|001", "INVENTED|1")
        self.manifest(["TRADE|real"])
        self.assertIn("UNANCHORED_OBSERVATION", self.types())

    def test_POSITIVE_CONTROL_a_fully_anchored_corpus_is_silent(self):
        # Without this, a check that flagged every observation would satisfy the test
        # above and make the whole corpus permanently red.
        self.observation("TOBS|MOGO|20260819|001", "TRADE|real")
        self.manifest(["TRADE|real"])
        self.assertNotIn("UNANCHORED_OBSERVATION", self.types())

    def test_bulk_fabrication_reports_every_invented_record(self):
        # Reporting only the first would understate the scale, and the count is what
        # tells a reader this was a bulk append rather than one stray record.
        self.observation("TOBS|MOGO|20260819|001", "TRADE|real")
        for i in range(20):
            self.observation("TOBS|MOGO|29990101|%03d" % i, "INVENTED|%03d" % i)
        self.manifest(["TRADE|real"])
        self.assertEqual(sum(1 for t in self.types() if t == "UNANCHORED_OBSERVATION"),
                         20)

    def test_it_is_silent_when_NO_manifest_exists_at_all(self):
        # An allow-list with nothing to allow would condemn the entire corpus. The
        # manifest's ABSENCE is reported by the availability invariant, not by
        # declaring every observation fabricated.
        self.observation("TOBS|MOGO|20260819|001", "TRADE|real")
        self.assertNotIn("UNANCHORED_OBSERVATION", self.types())

    def test_an_observation_with_no_sequenceId_is_left_to_the_other_checks(self):
        # Reporting it here too would double-count one defect under two names.
        self.observation("TOBS|MOGO|20260819|001", "TRADE|real")
        self.write("observations", "no_seq", {
            "observationId": "TOBS|MOGO|20260819|002",
            "sourceId": "EVSRC|MOGO|20260819|001", "schemaVersion": 1,
            "strategyId": "alex_g_sr_v1", "sourceContentHash": "z" * 64,
            "notes": "captureBasis=LIVE_CLOSE sourceType=paper_trade"})
        self.manifest(["TRADE|real"])
        self.assertNotIn("UNANCHORED_OBSERVATION", self.types())

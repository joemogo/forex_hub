"""MOGO's append-only trade-identity manifest (B-32.14, operator option A).

The anchor that closes the fifth category -- append-only enforced in AGGREGATE was
not append-only at all, because no gate asked WHICH trades existed. Its predecessor
covered 13.5% of the corpus and decayed, because the script that wrote it was
invoked by nothing.

Everything here builds packages the test authors itself. Reading the live store
would make these assertions depend on whatever the running instance happened to
hold that hour -- the failure mode this repository has found repeatedly.
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

import identity_manifest as im      # noqa: E402

#: A fixed timestamp, so findings are deterministic.
FIXED_NOW = datetime.datetime(2026, 8, 21, tzinfo=datetime.timezone.utc)
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
        # No `if s` guard. Filtering out falsy ids made this pass unchanged even if
        # observations LOST their sequenceId -- the same fail-open, inside the test
        # that certifies the coverage claim.
        self.assertNotIn(None, sequence_ids,
                         "an observation has no sequenceId, so it is anchored by "
                         "nothing and this coverage assertion would skip it")
        uncovered = sorted(s for s in sequence_ids if s not in recorded)
        self.assertEqual(uncovered, [],
                         "these live observations have no identity anchor, so "
                         "deleting them would be invisible: %s" % uncovered[:5])


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

    def test_an_observation_with_no_sequenceId_is_UNANCHORED(self):
        # DECISION REVERSED, and this test was the bypass. It asserted silence on the
        # grounds that reporting here "would double-count one defect under two names"
        # -- but there was no other name: `sequenceId` is read in exactly two places
        # and both skipped a non-string. Deleting one key per fabricated record walked
        # 200 invented winners past the allow-list, forward mean R -0.18 to +2.60.
        self.observation("TOBS|MOGO|20260819|001", "TRADE|real")
        self.write("observations", "no_seq", {
            "observationId": "TOBS|MOGO|20260819|002",
            "sourceId": "EVSRC|MOGO|20260819|001", "schemaVersion": 1,
            "strategyId": "alex_g_sr_v1", "sourceContentHash": "z" * 64,
            "notes": "captureBasis=LIVE_CLOSE sourceType=paper_trade"})
        self.manifest(["TRADE|real"])
        self.assertIn("UNANCHORED_OBSERVATION", self.types())

    def test_every_non_string_sequenceId_is_UNANCHORED(self):
        # One key deleted was the cheapest variant; these are the rest of the family.
        self.observation("TOBS|MOGO|20260819|001", "TRADE|real")
        self.manifest(["TRADE|real"])
        for bad in ("", 12345, None, [], 3.5, True):
            with self.subTest(sequenceId=bad):
                self.write("observations", "bad", {
                    "observationId": "TOBS|MOGO|20260819|003",
                    "sourceId": "EVSRC|MOGO|20260819|001", "schemaVersion": 1,
                    "strategyId": "alex_g_sr_v1", "sourceContentHash": "y" * 64,
                    "sequenceId": bad,
                    "notes": "captureBasis=LIVE_CLOSE sourceType=paper_trade"})
                self.assertIn("UNANCHORED_OBSERVATION", self.types(),
                              "sequenceId=%r walked past the allow-list" % (bad,))



class TestDeveloperRefusalIsRECORDEDNotRederived(ManifestCase):
    """The importer refuses a developer trade on THREE markers. A manifest row
    carries no position object, so a validator re-deriving that from the id alone
    sees one of three -- and a developer trade without the `AGT|TEST|` prefix would
    be required forever and never satisfiable, because the importer refuses it and
    the manifest is append-only.

    Four mutations survived on this: no fixture had a developer trade lacking the
    prefix, so re-deriving and recording were indistinguishable.
    """

    def dev_package(self, trade_id, marker):
        pkg = {"sourceTradeId": trade_id, "contentHash": "d" * 64,
               "captureBasis": "LIVE_CLOSE"}
        if marker == "flag":
            pkg["objects"] = {"positions": [{"isDeveloperTrade": True}]}
        elif marker == "source":
            pkg["objects"] = {"positions": [{"tradeSource": "TEST"}]}
        return pkg

    def rows(self):
        return {row["tradeId"]: row for row in im.load(self.path)["identities"]}

    def test_a_developer_trade_WITHOUT_the_prefix_is_recorded_as_refused(self):
        # The two markers a validator cannot see from an id.
        for marker in ("flag", "source"):
            with self.subTest(marker=marker):
                path = os.path.join(self.root, marker + ".json")
                im.update_from_packages([self.dev_package("NO|PREFIX|1", marker)], path)
                row = im.load(path)["identities"][0]
                self.assertTrue(row["refusedByImportPolicy"],
                                "marker %s was not recorded, so this trade would be "
                                "required forever and never satisfiable" % marker)

    def test_the_prefix_marker_is_also_recorded(self):
        im.update_from_packages([self.dev_package("AGT|TEST|1", "prefix")], self.path)
        self.assertTrue(self.rows()["AGT|TEST|1"]["refusedByImportPolicy"])

    def test_POSITIVE_CONTROL_a_real_trade_is_recorded_as_NOT_refused(self):
        # Without this, recording True for everything would satisfy the tests above
        # and silently exempt the entire corpus from the require-list.
        im.update_from_packages([package("REAL|1")], self.path)
        self.assertFalse(self.rows()["REAL|1"]["refusedByImportPolicy"])

    def test_the_validator_requires_a_trade_recorded_as_NOT_refused(self):
        findings = []
        ve.check_preserved_identities_still_present(
            [], findings, FIXED_NOW,
            preservation_dir=self._manifest_dir([
                {"tradeId": "NO|PREFIX|1", "refusedByImportPolicy": False}]))
        self.assertEqual([f["findingType"] for f in findings],
                         ["PRESERVED_IDENTITY_MISSING"])

    def test_the_validator_EXEMPTS_a_trade_recorded_as_refused(self):
        # The drift case end to end: no prefix, so a re-derived predicate would
        # demand it forever; the recorded flag exempts it correctly.
        findings = []
        ve.check_preserved_identities_still_present(
            [], findings, FIXED_NOW,
            preservation_dir=self._manifest_dir([
                {"tradeId": "NO|PREFIX|1", "refusedByImportPolicy": True}]))
        self.assertEqual(findings, [])

    def _manifest_dir(self, identities):
        d = os.path.join(self.root, "preservation")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "M.json"), "w", encoding="utf-8") as handle:
            json.dump({"identities": identities}, handle)
        return d


class TestAConflictDoesNotAdvanceTheManifest(ManifestCase):
    """An anchor that moves on its own failure path has a state that depends on
    whether anyone read the exit code."""

    def test_the_file_is_unchanged_when_a_conflict_is_reported(self):
        im.update_from_packages([package("T1", content_hash="a" * 64)], self.path)
        before = open(self.path, encoding="utf-8").read()
        result = im.update_from_packages(
            [package("T1", content_hash="b" * 64), package("T2", content_hash="c" * 64)],
            self.path)
        self.assertTrue(result["conflicts"])
        self.assertEqual(open(self.path, encoding="utf-8").read(), before,
                         "the manifest advanced on the failure path")

    def test_the_unconflicted_rest_of_the_batch_is_NOT_committed_either(self):
        # Partial commit on a failing batch is how a manifest ends up in a state
        # nobody chose. T2 is clean, but the batch failed.
        im.update_from_packages([package("T1", content_hash="a" * 64)], self.path)
        im.update_from_packages(
            [package("T1", content_hash="b" * 64), package("T2", content_hash="c" * 64)],
            self.path)
        self.assertEqual([r["tradeId"] for r in im.load(self.path)["identities"]], ["T1"])

    def test_POSITIVE_CONTROL_a_clean_batch_does_commit(self):
        im.update_from_packages([package("T1", content_hash="a" * 64)], self.path)
        im.update_from_packages([package("T2", content_hash="c" * 64)], self.path)
        self.assertEqual([r["tradeId"] for r in im.load(self.path)["identities"]],
                         ["T1", "T2"])


class TestMergeNeverShrinksAndNeverLocksInANull(unittest.TestCase):
    """Two ways the append-only record quietly stopped being one.

    `merge` rebuilt `document["identities"]` from a dict comprehension that filtered
    out non-dict rows and non-string tradeIds -- so merging DROPPED those rows and
    wrote the shrunk manifest, in the module whose own docstring says a shrinking
    manifest is the defect it exists to catch. It computed before > after, printed
    it, and returned success.

    And a row recorded from a package carrying no `contentHash` anchored nothing:
    the conflict predicate requires BOTH hashes truthy, so first-hash-wins locked
    the null in forever and the real hash was never reported. The stated defence --
    "stored WITH the contentHash, so the manifest can be checked against the
    packages rather than believed" -- was silently void for that row.
    """

    def test_a_malformed_row_is_CARRIED_not_dropped(self):
        document = {"identities": [{"tradeId": "A", "contentHash": "aa"},
                                   {"tradeId": 7}, "not-a-dict", {"noTradeId": 1}]}
        before = len(document["identities"])
        document, added, conflicts = im.merge(document, [
            {"tradeId": "B", "contentHash": "bb", "captureBasis": "X",
             "refusedByImportPolicy": False}])
        self.assertEqual(added, ["B"])
        self.assertEqual(conflicts, [])
        self.assertEqual(len(document["identities"]), before + 1,
                         "an append-only record does not get to decide which of "
                         "its rows were worth keeping")

    def test_repeated_merges_never_reduce_the_row_count(self):
        document = {"identities": [{"tradeId": 7}, "not-a-dict"]}
        for _ in range(3):
            document, _added, _conflicts = im.merge(document, [])
            self.assertEqual(len(document["identities"]), 2)

    def test_an_ABSENT_contentHash_is_filled_by_a_later_package(self):
        document = {"identities": [{"tradeId": "C", "contentHash": None}]}
        document, added, conflicts = im.merge(document, [
            {"tradeId": "C", "contentHash": "real", "captureBasis": "X",
             "refusedByImportPolicy": False}])
        row = [r for r in document["identities"] if r["tradeId"] == "C"][0]
        self.assertEqual(row["contentHash"], "real",
                         "a null hash anchors nothing and must not be permanent")
        self.assertEqual(conflicts, [])
        self.assertTrue(added, "filling an absent hash is a change worth reporting")

    def test_but_a_RECORDED_hash_is_never_overwritten(self):
        # The distinction that matters: filling an absent value is not the same as
        # taking a newer one, which is how a rewritten package would launder itself
        # into the manifest meant to anchor it.
        document = {"identities": [{"tradeId": "D", "contentHash": "one"}]}
        document, _added, conflicts = im.merge(document, [
            {"tradeId": "D", "contentHash": "two", "captureBasis": "X",
             "refusedByImportPolicy": False}])
        row = [r for r in document["identities"] if r["tradeId"] == "D"][0]
        self.assertEqual(row["contentHash"], "one")
        self.assertEqual([c["tradeId"] for c in conflicts], ["D"])

    def test_POSITIVE_CONTROL_an_ordinary_append_still_works(self):
        document = {"identities": [{"tradeId": "A", "contentHash": "aa"}]}
        document, added, conflicts = im.merge(document, [
            {"tradeId": "B", "contentHash": "bb", "captureBasis": "X",
             "refusedByImportPolicy": False}])
        self.assertEqual(added, ["B"])
        self.assertEqual(conflicts, [])
        self.assertEqual(len(document["identities"]), 2)

if __name__ == "__main__":
    unittest.main()

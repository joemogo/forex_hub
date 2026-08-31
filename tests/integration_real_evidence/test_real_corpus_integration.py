#!/usr/bin/env python3
"""OPT-IN lane: the checks whose subject IS the preserved capture corpus.

WHY THIS LANE EXISTS

    `evidence/*-PACKAGES.json` is OANDA-derived licensed market data. It is
    gitignored, and a sandbox refuses to read it. Most of the tests that used to
    open it never needed it -- the corpus was a convenient fixture for a
    behavioural contract, and those have been rewritten against deterministic
    synthetic packages in tests/trader_intelligence/.

    The tests HERE are the residue: their subject is the real capture history
    itself. "Does every indexed artifact still hash to what the index says", "did
    the preserved corpus convert without loss", "do real capture runs genuinely
    collide on packageId". No synthetic fixture can answer those, and pretending
    one could would be manufacturing a result and labelling it verification.

    So they are preserved here rather than weakened or deleted, and gated. Precisely, of the
    nine tests in this file: FIVE were moved verbatim and removed from their original modules
    (test_the_real_corpus_converts_without_loss, test_the_real_corpus_mints_nothing_new,
    test_2_every_indexed_artifact_exists_and_matches_its_whole_file_hash,
    test_3_package_hashes_verify_through_the_production_canonicalizer, and
    test_no_LIVE_record_states_a_value_its_package_leaves_null -- the last STRENGTHENED, not
    verbatim: its `skipTest("live corpus not present")` became a hard assertion, because in this
    lane an absent corpus is the failure). TWO were COPIED, not moved -- their originals remain
    in tests/trader_intelligence/test_import_mogo_observations.py retargeted at a synthetic glob
    (test_package_ids_really_do_collide_across_capture_runs,
    test_content_hash_is_unique_across_every_package), so the behaviour is covered in the routine
    lane and the real-corpus claim is covered here. The remaining TWO are new preconditions.

WHY IT IS OUTSIDE tests/trader_intelligence/

    Deliberate. The Python count guard collects that tree; this lane must not be
    auto-collected, because it cannot run where the data is unreadable.

HOW TO RUN IT

    MOGO_RUN_REAL_EVIDENCE=1 python3 -m unittest \
        tests.integration_real_evidence.test_real_corpus_integration

    Only on a host where `evidence/` is readable -- the operator's machine, with
    the capture set present. It is READ-ONLY: it opens artifacts and hashes them
    and writes nothing anywhere.

NO SKIP-TO-GREEN

    The env var is the ONLY thing that may skip this lane. Once it is set, absent
    or unreadable data is a FAILURE, not a skip: every test asserts its inputs are
    non-empty before asserting anything about them, nothing is wrapped in a
    try/except, and no PermissionError is swallowed. A lane that goes green
    because the evidence vanished is worse than no lane at all -- that is the
    exact defect that sent these tests here.
"""

import datetime
import glob
import hashlib
import json
import os
import subprocess
import sys
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts", "trader_intelligence"))

import import_mogo_observations as imp    # noqa: E402
import trade_observation as to            # noqa: E402
import validate_evidence as ve            # noqa: E402

RUN_REAL_EVIDENCE = os.environ.get("MOGO_RUN_REAL_EVIDENCE") == "1"
_GATE = "real-evidence lane is opt-in; set MOGO_RUN_REAL_EVIDENCE=1"

NOW = datetime.datetime(2026, 8, 17, 12, 0, 0)
FIXED_NOW = datetime.datetime(2026, 8, 21, tzinfo=datetime.timezone.utc)

INDEX_PATH = os.path.join(REPO_ROOT, "docs", "trader-intelligence", "evidence",
                          "ledger-preservation", "ARTIFACT_INDEX.json")


def _index():
    with open(INDEX_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _sha256(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


@unittest.skipUnless(RUN_REAL_EVIDENCE, _GATE)
class TestThePreservedCaptureSetIsPresent(unittest.TestCase):
    """The precondition, asserted FIRST and loudly.

    Every test below reads `evidence/`. If it is absent, empty or unreadable, each
    of them would otherwise report something misleading -- an empty corpus that
    "converted without loss", a migration that "minted nothing". This class exists
    so the lane fails on the real cause instead.
    """

    def test_the_capture_directory_exists_and_holds_package_files(self):
        directory = os.path.join(REPO_ROOT, "evidence")
        self.assertTrue(os.path.isdir(directory),
                        "%s is absent; the real-evidence lane cannot run" % directory)
        files = glob.glob(imp.PACKAGE_GLOB)
        self.assertTrue(files, "no *-PACKAGES.json under evidence/; every check in "
                               "this lane would pass vacuously")

    def test_every_package_file_is_readable_and_holds_packages(self):
        files = sorted(glob.glob(imp.PACKAGE_GLOB))
        self.assertTrue(files, "no capture files; vacuous")
        total = 0
        for path in files:
            # No try/except: an EPERM or a truncated file must surface as the error
            # it is, not become "0 packages" and a green run.
            with open(path, "r", encoding="utf-8") as handle:
                packages = json.load(handle)
            self.assertIsInstance(packages, list, "%s is not a package list" % path)
            total += len(packages)
        self.assertGreater(total, 200, "the preserved capture set is far smaller "
                                       "than the corpus these checks describe")


@unittest.skipUnless(RUN_REAL_EVIDENCE, _GATE)
class TestTheRealCorpusConverts(unittest.TestCase):
    """Moved from tests/trader_intelligence/test_import_mogo_observations.py.

    Regression: ids derived from the package's own trailing number collided across
    pairs and produced 7 usable records out of 222.
    """

    def test_the_real_corpus_converts_without_loss(self):
        records, skipped, sources = imp.convert_all(now=NOW, skip_imported=False)
        self.assertGreater(len(records), 200,
                           "the package corpus should convert in full")
        # A skip is acceptable ONLY when it is a deliberate refusal. Asserting an
        # empty list stopped being right once developer TEST trades began being
        # refused -- but relaxing it to "any skip is fine" would hide a genuine
        # conversion loss, which is what this test exists to catch.
        unexpected = [x for x in skipped if x.get("reason") != "DEVELOPER_TEST_TRADE"]
        self.assertEqual(unexpected, [], "a package was dropped for a reason that is "
                                          "not a deliberate refusal")


@unittest.skipUnless(RUN_REAL_EVIDENCE, _GATE)
class TestTheDeduplicationKeyIsGlobalInTheRealCorpus(unittest.TestCase):
    """Moved from tests/trader_intelligence/test_import_mogo_observations.py.

    `packageId` is PKG|<strategy>|<date>|<ordinal> and the ordinal only counts
    within one capture run, so it is NOT a global primary key: 21 of the 25 forward
    LIVE_CLOSE packages share a packageId with an unrelated REPLAY_RUN package.
    Keyed on packageId, the import reported those 21 as already-imported and
    silently dropped exactly the forward evidence it exists to preserve.

    The synthetic corpus in the unit lane reproduces the collision and pins the
    importer's behaviour. What only the real artifacts can say is whether the
    collision is still a REAL property of capture, and whether contentHash is
    still globally unique across everything actually preserved.
    """

    def test_package_ids_really_do_collide_across_capture_runs(self):
        """The precondition. If this ever stops holding, the regression is no
        longer testing anything and should be re-examined, not deleted."""
        by_basis = {}
        for path in glob.glob(os.path.join(imp.REPO_ROOT, "evidence",
                                           "*-PACKAGES.json")):
            with open(path, "r", encoding="utf-8") as handle:
                for package in json.load(handle):
                    by_basis.setdefault(package["captureBasis"], set()).add(
                        package["packageId"])
        self.assertTrue(by_basis, "no packages read; the check is vacuous")
        replay = by_basis.get("REPLAY_RUN", set())
        live = by_basis.get("LIVE_CLOSE", set())
        self.assertTrue(replay & live,
                        "expected packageId collisions across capture bases")

    def test_content_hash_is_unique_across_every_package(self):
        hashes = []
        for path in glob.glob(os.path.join(imp.REPO_ROOT, "evidence",
                                           "*-PACKAGES.json")):
            with open(path, "r", encoding="utf-8") as handle:
                hashes += [p["contentHash"] for p in json.load(handle)]
        self.assertGreater(len(hashes), 200, "no packages read; vacuous")
        self.assertEqual(len(hashes), len(set(hashes)))


@unittest.skipUnless(RUN_REAL_EVIDENCE, _GATE)
class TestSourceIdentityAgainstTheRealCorpus(unittest.TestCase):
    """Moved from tests/trader_intelligence/test_import_mogo_observations.py.

    B-27. Ids were assigned by position in a sorted glob, so inserting or deleting
    any capture file shifted every id after it; write_sources then correctly
    refused to repoint a cited source and the whole import was blocked.
    """

    NOW = datetime.datetime(2026, 8, 19, 0, 0, 0, tzinfo=datetime.timezone.utc)

    def test_the_real_corpus_mints_nothing_new(self):
        """Against the live corpus: every artifact already has a recorded id, so
        the migration changes no identity that any observation cites."""
        built = imp.build_sources(self.NOW)
        self.assertTrue(built, "no sources built from the capture set; the "
                               "comparison below would be vacuous")
        recorded = set()
        for path in glob.glob(os.path.join(
                REPO_ROOT, "docs", "trader-intelligence", "evidence", "sources", "*.json")):
            with open(path, encoding="utf-8") as handle:
                recorded.add(json.load(handle)["sourceId"])
        self.assertTrue(recorded, "no recorded sources; vacuous")
        minted = {v["sourceId"] for v in built.values()} - recorded
        self.assertEqual(minted, set(),
                         "the migration would mint new ids for existing artifacts")


@unittest.skipUnless(RUN_REAL_EVIDENCE, _GATE)
class TestIndexMatchesReality(unittest.TestCase):
    """Moved from tests/trader_intelligence/test_backup_source_artifacts.py.

    2-3: the index describes the artifacts that actually exist.
    """

    def test_2_every_indexed_artifact_exists_and_matches_its_whole_file_hash(self):
        artifacts = _index()["artifacts"]
        self.assertTrue(artifacts, "no artifacts; vacuous")
        for artifact in artifacts:
            path = os.path.join(REPO_ROOT, artifact["path"])
            self.assertTrue(os.path.isfile(path), "missing artifact %s" % artifact["path"])
            self.assertFalse(os.path.islink(path), "artifact is a symlink: %s" % artifact["path"])
            self.assertEqual(_sha256(path), artifact["sha256"],
                             "whole-file hash disagrees with the index for %s" % artifact["path"])
            self.assertEqual(os.path.getsize(path), artifact["bytes"])

    def test_3_package_hashes_verify_through_the_production_canonicalizer(self):
        """Identity I2, via the canonicalizer extracted from the committed index.html."""
        artifacts = _index()["artifacts"]
        self.assertTrue(artifacts, "no artifacts; vacuous")
        files = [os.path.join(REPO_ROOT, a["path"]) for a in artifacts]
        script = r"""
          const fs=require('fs'),crypto=require('crypto');
          const src=fs.readFileSync(process.argv[1],'utf8');
          const grab=(re,l)=>{const m=src.match(re); if(!m) throw new Error('cannot extract '+l); return m[0];};
          const parts=[
            grab(/const EVIDENCE_HASH_EXCLUDED_FIELDS=Object\.freeze\(\[[^\]]*\]\);/,'excluded'),
            grab(/function evidenceCanonValue\(v,seen\)\{[\s\S]*?\n\}/,'canonValue'),
            grab(/function evidenceCanonicalize\(pkg\)\{[\s\S]*?\n\}/,'canonicalize')];
          const g={}; new Function('g',parts.join('\n')+'\ng.canonicalize=evidenceCanonicalize;')(g);
          let ok=0,bad=0;
          for(const f of JSON.parse(process.argv[3])){
            for(const p of JSON.parse(fs.readFileSync(f,'utf8'))){
              const h=crypto.createHash('sha256').update(g.canonicalize(p),'utf8').digest('hex');
              if(h===p.contentHash) ok++; else bad++;
            }
          }
          process.stdout.write(JSON.stringify({ok,bad}));
        """
        result = subprocess.run(
            ["node", "-e", script, os.path.join(REPO_ROOT, "index.html"), "--", json.dumps(files)],
            capture_output=True, text=True, cwd=REPO_ROOT)
        self.assertEqual(result.returncode, 0, result.stderr[:400])
        counts = json.loads(result.stdout)
        self.assertGreater(counts["ok"], 0, "verified no packages; vacuous")
        self.assertEqual(counts["bad"], 0, "packages whose contentHash does not re-derive")
        indexed = sum(len(a["packageContentHashes"]) for a in artifacts)
        self.assertEqual(counts["ok"], indexed,
                         "the index declares a different number of packages than exist")


@unittest.skipUnless(RUN_REAL_EVIDENCE, _GATE)
class TestTheLiveRecordsAgreeWithTheirPackages(unittest.TestCase):
    """Moved from tests/trader_intelligence/evidence/test_evidence.py.

    The `nullable` flag asserted directly against the preserved corpus: if a record
    ever states a value the engine did not record, that is the thing to know -- not
    which field it happened to be.
    """

    def test_no_LIVE_record_states_a_value_its_package_leaves_null(self):
        root = os.path.join(REPO_ROOT, "docs", "trader-intelligence", "evidence")
        # Was `self.skipTest("live corpus not present")`. In this lane an absent
        # corpus is the failure, not a reason to go green: the operator asked for
        # the real-evidence checks and must be told they could not run.
        self.assertTrue(os.path.isdir(os.path.join(root, "observations")),
                        "live corpus not present at %s" % root)
        sources, records = [], []
        for path in glob.glob(os.path.join(root, "sources", "**", "*.json"),
                              recursive=True):
            with open(path, "r", encoding="utf-8") as handle:
                sources.append(json.load(handle))
        for path in glob.glob(os.path.join(root, "observations", "**", "*.json"),
                              recursive=True):
            with open(path, "r", encoding="utf-8") as handle:
                records.append(json.load(handle))
        self.assertGreater(len(records), 100, "would pass vacuously")
        packages, _u, _c = ve._packages_by_content_hash(
            sources, {r.get("sourceId") for r in records})
        self.assertGreater(len(packages), 100, "no packages read; passes vacuously")
        offenders = []
        for record in records:
            package = packages.get(record.get("sourceContentHash"))
            if package is None:
                continue
            for witness in ve.PACKAGE_WITNESSES:
                if witness.record_field not in record:
                    continue
                if ve._witness_value(package, witness) is ve._WITNESS_NULL:
                    offenders.append((record.get("observationId"),
                                      witness.record_field))
        self.assertEqual(offenders, [],
                         "these records state a value their captured package "
                         "records as null: %s" % offenders[:5])


if __name__ == "__main__":
    unittest.main()

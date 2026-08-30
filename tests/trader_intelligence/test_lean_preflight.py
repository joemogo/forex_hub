"""The synthetic LEAN upload preflight must refuse to hand an operator unreviewed bytes.

`tests/lean_synthetic/preflight.py` is the one command run before anything is uploaded to
QuantConnect. It is only worth having if it FAILS when the package has drifted, so every test
here drives the real command as a subprocess against a disposable copy of the package inside a
disposable git repository, mutates exactly one thing, and requires the outcome to change.

Nothing here runs LEAN, touches the network, reads a historical artifact, or writes anywhere
except a temporary directory. The package the tests copy is the synthetic one -- generated
arithmetic, no market observation of any kind.

The positive control at the bottom exists because every assertion below looks for a failure
token in the command's output: if the pristine tree also emitted those tokens, or if the
command failed for an unrelated reason, the mutation tests would pass vacuously.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                         "..", ".."))
REAL_PKG = os.path.join(REPO_ROOT, "tests", "lean_synthetic")

#: Copied verbatim into each disposable tree. Deliberately explicit: __pycache__ and the
#: preserved evidence/ subdirectory are never copied, and nothing outside this list is.
PACKAGE_FILES = (
    "MANIFEST.sha256",
    "RUN_PROCEDURE.md",
    "br_machine.py",
    "main.py",
    "mogo_synthetic_qualify.csv",
    "mogo_synthetic_reject.csv",
    "preflight.py",
    "synthetic_bars.py",
    "test_synthetic_local.py",
)

UPLOAD_FILES = ("main.py", "br_machine.py", "synthetic_bars.py")
FIXTURE_FILES = ("mogo_synthetic_qualify.csv", "mogo_synthetic_reject.csv")

#: Failure tokens the mutation tests look for. The positive control asserts that a pristine
#: run emits NONE of them -- otherwise finding one proves nothing.
FAILURE_TOKENS = ("HASH MISMATCH", "MISSING:", "UNLISTED:", "VERDICT FAIL", "VERDICT NOT-CHECKED")

EXIT_OK = 0
EXIT_MANIFEST = 2
EXIT_REFRESHED = 3
EXIT_DIRTY = 4
EXIT_LOCAL_CHECKS = 5


def _sha256(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def _git(repo, *args):
    return subprocess.run(("git", "-C", repo,
                           "-c", "user.email=preflight-test@example.invalid",
                           "-c", "user.name=preflight test") + args,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


class PreflightCase(unittest.TestCase):
    """Gives each test a private git repo containing a copy of the synthetic package."""

    template = None
    _template_root = None

    @classmethod
    def setUpClass(cls):
        # Built once: a committed, CLEAN repo holding tests/lean_synthetic. Each test copies
        # it (including .git) so mutations never leak between tests or near the real repo.
        cls._template_root = tempfile.mkdtemp(prefix="mogo-preflight-template-")
        repo = os.path.join(cls._template_root, "repo")
        pkg = os.path.join(repo, "tests", "lean_synthetic")
        os.makedirs(pkg)
        for name in PACKAGE_FILES:
            shutil.copyfile(os.path.join(REAL_PKG, name), os.path.join(pkg, name))
        assert _git(repo, "init").returncode == 0, "could not init the disposable repo"
        assert _git(repo, "add", "-A").returncode == 0
        assert _git(repo, "commit", "-m", "synthetic package").returncode == 0
        cls.template = repo

    @classmethod
    def tearDownClass(cls):
        if cls._template_root:
            shutil.rmtree(cls._template_root, ignore_errors=True)

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="mogo-preflight-")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.repo = os.path.join(self.root, "repo")
        shutil.copytree(self.template, self.repo, symlinks=True)
        self.pkg = os.path.join(self.repo, "tests", "lean_synthetic")
        # The bundle destination is OUTSIDE the disposable repo, exactly as the command
        # requires of the real one.
        self.out = os.path.join(self.root, "bundle")

    # -- helpers ------------------------------------------------------------------

    def run_preflight(self, *flags):
        proc = subprocess.run(
            [sys.executable, os.path.join(self.pkg, "preflight.py"), "--out", self.out] +
            list(flags),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=self.root)
        return proc

    def bundle_stamp(self):
        with open(os.path.join(self.out, "BUNDLE.json"), encoding="utf-8") as handle:
            return json.load(handle)

    def head_commit(self):
        return _git(self.repo, "rev-parse", "HEAD").stdout.strip()

    def porcelain(self):
        return [line for line in
                _git(self.repo, "status", "--porcelain", "--", self.pkg).stdout.splitlines()
                if line.strip()]

    def write(self, name, text):
        with open(os.path.join(self.pkg, name), "w", encoding="utf-8") as handle:
            handle.write(text)


class TestTheHappyPath(PreflightCase):

    def test_a_clean_tree_produces_a_bundle_of_exactly_the_three_upload_files_and_a_stamp(self):
        proc = self.run_preflight()
        self.assertEqual(proc.returncode, EXIT_OK, proc.stdout)
        self.assertIn("VERDICT READY", proc.stdout)
        self.assertEqual(sorted(os.listdir(self.out)),
                         sorted(("BUNDLE.json",) + UPLOAD_FILES))
        # The copies must be byte-identical to the reviewed sources, not merely present.
        for name in UPLOAD_FILES:
            self.assertEqual(_sha256(os.path.join(self.out, name)),
                             _sha256(os.path.join(self.pkg, name)), name)
        # The CSVs are fetched by LEAN from the pinned gist and must NOT be uploaded.
        for name in FIXTURE_FILES:
            self.assertNotIn(name, os.listdir(self.out))

    def test_the_clean_run_stamps_clean_and_reports_the_manifest_and_local_checks(self):
        proc = self.run_preflight()
        self.assertEqual(proc.returncode, EXIT_OK, proc.stdout)
        stamp = self.bundle_stamp()
        self.assertEqual(stamp["treeState"], "CLEAN")
        self.assertEqual(stamp["gitDirtyEntries"], [])
        self.assertEqual(stamp["manifest"]["result"], "MATCH")
        self.assertEqual(stamp["manifest"]["filesChecked"], 6)
        self.assertEqual(stamp["localChecks"]["result"], "PASS")
        self.assertEqual(stamp["localChecks"]["exitCode"], 0)

    def test_the_command_modifies_no_tracked_file(self):
        before = self.porcelain()
        self.assertEqual(before, [], "the disposable repo did not start clean")
        proc = self.run_preflight()
        self.assertEqual(proc.returncode, EXIT_OK, proc.stdout)
        self.assertEqual(self.porcelain(), [],
                         "preflight left the package tree dirty; it must write nothing tracked")

    def test_it_refuses_to_write_the_bundle_inside_the_repository(self):
        self.out = os.path.join(self.repo, "tests", "lean_synthetic", "bundle")
        proc = self.run_preflight()
        self.assertNotEqual(proc.returncode, EXIT_OK, proc.stdout)
        self.assertIn("refusing to write the bundle inside the repository", proc.stdout)
        self.assertFalse(os.path.exists(self.out))


class TestTheManifestIsActuallyRecomputed(PreflightCase):

    # --allow-dirty throughout this class so the only thing that can fail is the manifest;
    # editing a package file necessarily dirties the tree as well.

    def test_a_changed_file_fails_with_a_hash_mismatch_naming_the_file(self):
        with open(os.path.join(self.pkg, "main.py"), "a", encoding="utf-8") as handle:
            handle.write("\n# one byte of drift\n")
        proc = self.run_preflight("--allow-dirty")
        self.assertEqual(proc.returncode, EXIT_MANIFEST, proc.stdout)
        self.assertIn("HASH MISMATCH", proc.stdout)
        self.assertIn("main.py", proc.stdout)
        self.assertFalse(os.path.exists(self.out), "no bundle may be produced on failure")

    def test_a_file_listed_in_the_manifest_but_missing_from_disk_fails(self):
        os.remove(os.path.join(self.pkg, "synthetic_bars.py"))
        proc = self.run_preflight("--allow-dirty")
        self.assertEqual(proc.returncode, EXIT_MANIFEST, proc.stdout)
        self.assertIn("MISSING:", proc.stdout)
        self.assertIn("synthetic_bars.py", proc.stdout)
        self.assertFalse(os.path.exists(self.out))

    def test_a_package_file_present_but_unlisted_fails(self):
        self.write("rogue_fixture.csv", "bar_index,open,high,low,close\n0,1,1,1,1\n")
        proc = self.run_preflight("--allow-dirty")
        self.assertEqual(proc.returncode, EXIT_MANIFEST, proc.stdout)
        self.assertIn("UNLISTED:", proc.stdout)
        self.assertIn("rogue_fixture.csv", proc.stdout)
        self.assertFalse(os.path.exists(self.out))

    def test_a_corrupt_manifest_line_fails_rather_than_being_skipped(self):
        self.write("MANIFEST.sha256", "not-a-hash  main.py\n")
        proc = self.run_preflight("--allow-dirty")
        self.assertEqual(proc.returncode, EXIT_MANIFEST, proc.stdout)
        self.assertIn("VERDICT FAIL", proc.stdout)


class TestDirtyVersusCommitted(PreflightCase):

    def dirty_the_package(self):
        # RUN_PROCEDURE.md is tracked but outside the manifest, so this dirties the tree
        # WITHOUT changing any hashed byte -- isolating the git check from the manifest check.
        with open(os.path.join(self.pkg, "RUN_PROCEDURE.md"), "a", encoding="utf-8") as handle:
            handle.write("\nlocal scratch note\n")
        self.assertNotEqual(self.porcelain(), [], "the mutation did not dirty the tree")

    def test_a_dirty_tree_fails_the_approved_cloud_run_and_produces_no_bundle(self):
        self.dirty_the_package()
        proc = self.run_preflight()
        self.assertEqual(proc.returncode, EXIT_DIRTY, proc.stdout)
        self.assertIn("DIRTY", proc.stdout)
        self.assertIn("VERDICT FAIL", proc.stdout)
        self.assertFalse(os.path.exists(self.out))

    def test_allow_dirty_produces_a_bundle_that_is_stamped_dirty_and_labelled_inspection_only(self):
        self.dirty_the_package()
        proc = self.run_preflight("--allow-dirty")
        self.assertEqual(proc.returncode, EXIT_OK, proc.stdout)
        stamp = self.bundle_stamp()
        self.assertEqual(stamp["treeState"], "DIRTY")
        self.assertTrue(stamp["gitDirtyEntries"], "the dirty entries must be recorded")
        self.assertIn("RUN_PROCEDURE.md", " ".join(stamp["gitDirtyEntries"]))
        self.assertIn("LOCAL INSPECTION", proc.stdout.upper())
        self.assertNotIn("VERDICT READY", proc.stdout)

    def test_an_untracked_addition_the_manifest_does_not_cover_still_counts_as_dirty(self):
        # A stray subdirectory is outside the manifest's flat scan, so ONLY the git check can
        # catch it. Without that check an uncommitted package would sail through.
        os.makedirs(os.path.join(self.pkg, "scratch_dir"))
        with open(os.path.join(self.pkg, "scratch_dir", "note.md"), "w",
                  encoding="utf-8") as handle:
            handle.write("uncommitted\n")
        proc = self.run_preflight()
        self.assertEqual(proc.returncode, EXIT_DIRTY, proc.stdout)
        self.assertNotIn("UNLISTED:", proc.stdout,
                         "this must fail as DIRTY, not as a manifest problem")

    def test_an_unresolvable_git_state_fails_closed_as_dirty(self):
        shutil.rmtree(os.path.join(self.repo, ".git"))
        proc = self.run_preflight()
        self.assertEqual(proc.returncode, EXIT_DIRTY, proc.stdout)
        self.assertIn("fail closed", proc.stdout)
        self.assertFalse(os.path.exists(self.out))


class TestRefreshManifestIsNeverGreen(PreflightCase):

    def test_refresh_rewrites_the_manifest_and_still_exits_nonzero(self):
        before = _sha256(os.path.join(self.pkg, "MANIFEST.sha256"))
        self.write("rogue_fixture.csv", "bar_index\n0\n")

        proc = self.run_preflight("--refresh-manifest")
        self.assertEqual(proc.returncode, EXIT_REFRESHED, proc.stdout)
        after = _sha256(os.path.join(self.pkg, "MANIFEST.sha256"))
        self.assertNotEqual(before, after, "the manifest was not actually rewritten")
        with open(os.path.join(self.pkg, "MANIFEST.sha256"), encoding="utf-8") as handle:
            refreshed = handle.read()
        self.assertIn("rogue_fixture.csv", refreshed)

        # It must not claim anything passed, and must not hand over a bundle.
        self.assertNotIn("VERDICT READY", proc.stdout)
        self.assertIn("NOT-CHECKED", proc.stdout)
        self.assertIn("re-run", proc.stdout)
        self.assertFalse(os.path.exists(self.out))

    def test_the_refreshed_manifest_is_the_one_a_later_run_validates_against(self):
        # Proves the refresh did real work rather than merely exiting nonzero: the same
        # package that failed as UNLISTED before the refresh validates after it.
        self.write("rogue_fixture.csv", "bar_index\n0\n")
        first = self.run_preflight("--allow-dirty")
        self.assertEqual(first.returncode, EXIT_MANIFEST, first.stdout)

        self.assertEqual(self.run_preflight("--refresh-manifest").returncode, EXIT_REFRESHED)

        second = self.run_preflight("--allow-dirty")
        self.assertEqual(second.returncode, EXIT_OK, second.stdout)
        self.assertIn("MANIFEST OK", second.stdout)


class TestTheLocalChecksAreReallyRun(PreflightCase):

    def test_failing_local_checks_fail_the_preflight_and_produce_no_bundle(self):
        # Replace the local validator with one that fails, refresh so the manifest agrees,
        # and require preflight to surface the failure rather than bundling anyway.
        self.write("test_synthetic_local.py",
                   "import sys\nprint('LOCAL CHECKS DELIBERATELY FAILING')\nsys.exit(1)\n")
        self.assertEqual(self.run_preflight("--refresh-manifest").returncode, EXIT_REFRESHED)

        proc = self.run_preflight("--allow-dirty")
        self.assertEqual(proc.returncode, EXIT_LOCAL_CHECKS, proc.stdout)
        self.assertIn("LOCAL CHECKS DELIBERATELY FAILING", proc.stdout,
                      "the failing validator's own output must reach the operator")
        self.assertIn("VERDICT FAIL", proc.stdout)
        self.assertFalse(os.path.exists(self.out))


class TestTheStampRecordsWhatItClaims(PreflightCase):

    def setUp(self):
        super().setUp()
        self.proc = self.run_preflight()
        self.assertEqual(self.proc.returncode, EXIT_OK, self.proc.stdout)
        self.stamp = self.bundle_stamp()

    def test_it_records_the_git_commit_that_is_actually_checked_out(self):
        self.assertEqual(self.stamp["gitCommit"], self.head_commit())
        self.assertRegex(self.stamp["gitCommit"], r"^[0-9a-f]{40}$")

    def test_it_records_the_sha256_of_every_source_file(self):
        for name in UPLOAD_FILES:
            self.assertEqual(self.stamp["uploadFiles"][name]["sha256"],
                             _sha256(os.path.join(self.pkg, name)), name)
        self.assertEqual(sorted(self.stamp["uploadFiles"]), sorted(UPLOAD_FILES))

    def test_it_records_the_sha256_of_both_published_fixtures(self):
        for name in FIXTURE_FILES:
            self.assertEqual(self.stamp["publishedFixtures"][name]["sha256"],
                             _sha256(os.path.join(self.pkg, name)), name)
        self.assertEqual(sorted(self.stamp["publishedFixtures"]), sorted(FIXTURE_FILES))

    def test_it_records_the_pinned_gist_revision_taken_from_the_algorithm(self):
        with open(os.path.join(self.pkg, "main.py"), encoding="utf-8") as handle:
            source = handle.read()
        pinned = set(re.findall(r"/raw/([0-9a-f]{40})/", source))
        self.assertEqual(len(pinned), 1, "main.py must pin exactly one gist revision")
        self.assertEqual(self.stamp["pinnedGistRevision"], pinned.pop())
        self.assertRegex(self.stamp["pinnedGistId"], r"^[0-9a-f]{32}$")

    def test_the_stamp_and_the_output_disclaim_proving_what_ran_in_quantconnect(self):
        self.assertIn("QuantConnect", self.stamp["disclaimer"])
        self.assertIn("PREPARED LOCALLY", self.stamp["disclaimer"])
        self.assertFalse(self.stamp["provesQuantConnectExecution"])
        self.assertTrue(self.stamp["provesLocalPreparationOnly"])
        self.assertFalse(self.stamp["localChecks"]["isEngineRun"])
        self.assertIn("QuantConnect", self.proc.stdout)
        self.assertIn("PREPARED LOCALLY", self.proc.stdout)


class TestPositiveControl(PreflightCase):
    """Without this, every mutation test above could be passing for the wrong reason."""

    def test_a_pristine_tree_emits_none_of_the_failure_tokens_the_other_tests_look_for(self):
        proc = self.run_preflight()
        self.assertEqual(proc.returncode, EXIT_OK, proc.stdout)
        for token in FAILURE_TOKENS:
            self.assertNotIn(token, proc.stdout,
                             "%r appears even with nothing wrong, so finding it elsewhere "
                             "proves nothing" % token)
        self.assertTrue(os.path.isfile(os.path.join(self.out, "BUNDLE.json")))

    def test_each_guard_changes_the_outcome_of_the_very_same_invocation(self):
        # One invocation, held fixed; only the tree changes. Each mutation must move the exit
        # code away from the pristine 0 -- a guard that cannot fail is not a guard.
        baseline = self.run_preflight("--allow-dirty")
        self.assertEqual(baseline.returncode, EXIT_OK, baseline.stdout)

        mutations = {}

        with open(os.path.join(self.pkg, "br_machine.py"), "a", encoding="utf-8") as handle:
            handle.write("\n# drift\n")
        mutations["changed file"] = self.run_preflight("--allow-dirty").returncode
        self.setUp()

        os.remove(os.path.join(self.pkg, "mogo_synthetic_reject.csv"))
        mutations["missing file"] = self.run_preflight("--allow-dirty").returncode
        self.setUp()

        self.write("unlisted.py", "# not in the manifest\n")
        mutations["unlisted file"] = self.run_preflight("--allow-dirty").returncode
        self.setUp()

        with open(os.path.join(self.pkg, "RUN_PROCEDURE.md"), "a", encoding="utf-8") as handle:
            handle.write("\nscratch\n")
        mutations["dirty tree"] = self.run_preflight().returncode

        for label, code in mutations.items():
            self.assertNotEqual(code, EXIT_OK, "the %s guard did not fail the run" % label)
        self.assertEqual(len(mutations), 4)


if __name__ == "__main__":
    unittest.main()

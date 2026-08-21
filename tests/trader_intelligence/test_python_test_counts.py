"""The gate that stops the Python lane quietly shrinking (B-32.22).

Twenty-one rounds of adversarial hardening are STORED as Python tests -- they are
what kills every mutation. `run_all.sh` guarded the JS lane against silent
shrinkage with a per-runner manifest and gave the Python lane only the exit code
of one `unittest` call over all modules, counting FILES rather than tests. So
renaming `test_` to `xtest_` across a whole module de-collected every test in it
and the run still exited 0, because the sibling modules kept the total non-zero.

This suite tests the guard itself. Without it the guard is the one thing in the
repository that nothing checks -- and a mutation making `--check` always pass
survived the entire suite until these existed.
"""
import os
import subprocess
import sys
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCRIPT = os.path.join(REPO_ROOT, "tests", "count_python_tests.py")
MANIFEST = os.path.join(REPO_ROOT, "tests", "expected_python_test_counts.tsv")
sys.path.insert(0, os.path.join(REPO_ROOT, "tests"))
import count_python_tests as cpt   # noqa: E402


class TestTheCountGate(unittest.TestCase):

    def check(self, expected_rows):
        """Run the real --check logic against a substituted manifest."""
        original = cpt.read_expected
        cpt.read_expected = lambda: expected_rows
        try:
            return cpt.main(["--check"])
        finally:
            cpt.read_expected = original

    def actual(self):
        return {name: cpt.count(name) for name in cpt.modules()}

    def test_POSITIVE_CONTROL_the_real_manifest_is_in_sync(self):
        self.assertEqual(cpt.main(["--check"]), 0,
                         "the committed manifest does not match what is collected")

    def test_the_enumeration_is_not_empty(self):
        found = cpt.modules()
        self.assertGreater(len(found), 10,
                           "module discovery found almost nothing, so every "
                           "assertion here would pass vacuously")
        self.assertIn("tests.trader_intelligence.evidence.test_evidence", found)

    def test_a_suite_that_SHRINKS_fails(self):
        rows = self.actual()
        target = "tests.trader_intelligence.evidence.test_evidence"
        rows[target] += 1                       # manifest expects one more
        self.assertEqual(self.check(rows), 1,
                         "a suite collecting fewer tests than declared has not "
                         "passed, it has stopped asking")

    def test_a_suite_de_collected_ENTIRELY_fails(self):
        rows = self.actual()
        rows["tests.trader_intelligence.evidence.test_evidence"] = 281
        rows_zero = dict(rows)
        # Simulate the module collecting nothing at all.
        original = cpt.count
        cpt.count = lambda name: (0 if name.endswith("test_evidence")
                                  else original(name))
        try:
            self.assertEqual(self.check(rows_zero), 1)
        finally:
            cpt.count = original

    def test_a_suite_that_GROWS_unannounced_fails(self):
        rows = self.actual()
        rows["tests.trader_intelligence.evidence.test_evidence"] -= 1
        self.assertEqual(self.check(rows), 1,
                         "tests added without updating the manifest make the "
                         "count stop meaning anything")

    def test_an_UNREGISTERED_suite_fails(self):
        rows = self.actual()
        del rows["tests.trader_intelligence.evidence.test_evidence"]
        self.assertEqual(self.check(rows), 1)

    def test_a_REGISTERED_suite_that_vanished_fails(self):
        rows = self.actual()
        rows["tests.trader_intelligence.test_module_that_does_not_exist"] = 7
        self.assertEqual(self.check(rows), 1)

    def test_an_EMPTY_manifest_fails_rather_than_passing_vacuously(self):
        self.assertEqual(self.check({}), 1,
                         "no manifest means no guard, which must not read as "
                         "'in sync'")

    def test_a_module_that_cannot_be_IMPORTED_is_not_counted_as_one_test(self):
        # unittest turns an import failure into a single synthetic _FailedTest, so
        # a suite that cannot load would otherwise report a plausible "1".
        original = cpt.count
        cpt.count = lambda name: (-1 if name.endswith("test_evidence")
                                  else original(name))
        try:
            rows = {name: (1 if name.endswith("test_evidence") else v)
                    for name, v in self.actual().items()}
            self.assertEqual(self.check(rows), 1)
        finally:
            cpt.count = original

    def test_the_gate_is_WIRED_into_the_canonical_runner(self):
        # A gate nobody runs is not a gate -- the shape found six times in this
        # milestone.
        with open(os.path.join(REPO_ROOT, "tests", "run_all.sh"),
                  encoding="utf-8") as handle:
            runner = handle.read()
        self.assertIn("count_python_tests.py --check", runner)
        self.assertIn("OVERALL_EXIT=1",
                      runner.split("count_python_tests.py --check")[1][:200],
                      "the runner calls the gate but does not fail on it")

    def test_the_manifest_is_committed_and_non_trivial(self):
        self.assertTrue(os.path.exists(MANIFEST))
        rows = cpt.read_expected()
        self.assertGreater(len(rows), 10)
        self.assertGreater(sum(rows.values()), 500)

    def test_the_script_runs_as_a_subprocess_and_reports_its_verdict(self):
        result = subprocess.run([sys.executable, SCRIPT, "--check"],
                                capture_output=True, text=True, cwd=REPO_ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("IN SYNC", result.stdout)


if __name__ == "__main__":
    unittest.main()

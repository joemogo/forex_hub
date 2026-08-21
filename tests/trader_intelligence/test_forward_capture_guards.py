"""Every step in the live capture chain must fail the run when it fails (B-32.24).

`scripts/forward_capture.sh` is the chain that runs on live forward evidence:
detect -> preserve -> recover -> import -> reconcile. Under `set -o pipefail` a
pipeline reports the rightmost non-zero status, so `if ! cmd | sed` is safe -- but
a pipeline whose output is merely printed needs its status captured explicitly,
and the reconcile step did not do that. It piped into `sed` and moved on, so
`--write` completed, assimilated and exited 0 whether the reconciliation passed,
failed, or never collected a test.

That was repaired. The repair was then pinned by NOTHING: two mutations neutering
it survived the entire suite, and nothing in the repository read the file at all.
By this repo's own standing rule a fixture is not evidence until breaking the
mechanism makes it fail -- so the repair was not yet evidence.

Two levels here, deliberately:

  * a STRUCTURAL invariant over every failure-capable pipeline in the script, so
    the "lane exits 0 while its check did not pass" shape cannot reappear in a
    step added later. That shape has now been repaired three times -- run_all.sh,
    the reconcile step, and whatever comes next -- with nothing pinning any of it.
  * a BEHAVIOURAL test that executes the REAL BYTES of the reconcile block,
    extracted from the shipped file, against a stubbed command. Rewriting the
    guard into the test would verify a copy, which is defect shape (a) from this
    milestone: a test that passes while the shipped path is broken.
"""
import os
import re
import subprocess
import tempfile
import textwrap
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCRIPT = os.path.join(REPO_ROOT, "scripts", "forward_capture.sh")


def source():
    with open(SCRIPT, "r", encoding="utf-8") as handle:
        return handle.read()


class TestEveryFailableStepIsChecked(unittest.TestCase):

    #: A pipeline starting with one of these can fail meaningfully. `echo "$VAR" |
    #: sed` cannot, and demanding a guard for it would be noise that gets ignored.
    FAILABLE = ("python3", "node", "bash", "osascript")

    def pipelines(self):
        found = []
        for number, line in enumerate(source().splitlines(), start=1):
            stripped = line.strip()
            if "|" not in stripped or stripped.startswith("#"):
                continue
            head = stripped
            for prefix in ("if ! ", "if ", "! "):
                if head.startswith(prefix):
                    head = head[len(prefix):]
                    break
            if head.split(" ", 1)[0] in self.FAILABLE:
                found.append((number, stripped))
        return found

    def test_the_scan_finds_the_pipelines_it_is_supposed_to(self):
        found = self.pipelines()
        self.assertGreaterEqual(len(found), 4,
                                "the scan found almost nothing, so every assertion "
                                "below would pass vacuously: %r" % (found,))

    def test_pipefail_is_set_or_the_if_not_form_proves_nothing(self):
        # `if ! cmd | sed` only catches a failing `cmd` BECAUSE pipefail is set.
        # Without it the pipeline reports sed's status, which is always 0.
        self.assertRegex(source(), r"set -[a-z]*o pipefail|set -o pipefail")

    def test_every_failable_pipeline_is_GUARDED(self):
        lines = source().splitlines()
        for number, text in self.pipelines():
            with self.subTest(line=number, code=text[:70]):
                guarded_inline = text.lstrip().startswith(("if ! ", "! "))
                # Follows the VARIABLE, not a fixed number of lines. A window of N
                # lines is broken by adding a comment -- which is how this test
                # first failed, on a step that was correctly guarded.
                window = "\n".join(lines[number:number + 12])
                captured = re.search(r"([A-Za-z_][A-Za-z0-9_]*)=\$\{PIPESTATUS\[0\]\}",
                                     window)
                tested = bool(captured and re.search(
                    r"\$\{%s[:\-}][^\n]*-eq 0 \]" % re.escape(captured.group(1)),
                    window))
                self.assertTrue(guarded_inline or (captured and tested),
                                "line %d runs a command that can fail and neither "
                                "guards it with `if !` nor captures PIPESTATUS and "
                                "tests it. A step that cannot fail the run is not a "
                                "step, it is a log line." % number)

    def test_the_reconcile_step_specifically_is_guarded(self):
        # Named, because it is the last gate in the chain and the one that was not.
        body = source()
        self.assertIn("RECONCILE_RC=${PIPESTATUS[0]}", body)
        self.assertRegex(body, r'RECONCILE_RC[^\n]*\n\s*\[ "\$\{RECONCILE_RC[^\n]*-eq 0 \]')

    def test_every_rc_DEFAULT_fails_closed(self):
        # `${RC:-0}` and `${RC:-1}` behave identically while the assignment above
        # them runs -- which is why flipping one survived every behavioural test.
        # The default exists for the case where that assignment is removed, skipped
        # or added out of order, and that is exactly the case where it must fail
        # CLOSED. A defensive default that defaults to "fine" is decoration.
        defaults = re.findall(r"\$\{([A-Z_]*RC):-(\d+)\}", source())
        self.assertTrue(defaults, "no rc defaults found -- passes vacuously")
        for name, value in defaults:
            with self.subTest(variable=name):
                self.assertNotEqual(
                    value, "0",
                    "%s defaults to 0, so if its assignment is ever removed the "
                    "step silently passes -- the failure this guard exists to "
                    "prevent, arriving through the guard itself" % name)


class TestTheShippedReconcileGuardActuallyFails(unittest.TestCase):
    """Executes the real bytes of the guard, not a rewrite of it."""

    def extract(self):
        """The reconcile block, lifted verbatim out of the shipped script."""
        body = source()
        say = body.index('  say "reconcile:')
        # Back up to the `if` that opens the block, or the extracted fragment
        # carries a closing `fi` with nothing to close.
        start = body.rindex("if [ $WRITE -eq 1 ]; then", 0, say)
        end = body.index("\nfi", say) + len("\nfi")
        block = body[start:end]
        self.assertIn("PIPESTATUS", block)
        self.assertTrue(block.rstrip().endswith("fi"))
        return block

    def run_with(self, exit_code, output="Ran 3 tests\nOK\n"):
        """Run the extracted block with `python3` stubbed to a chosen exit code."""
        tmp = tempfile.mkdtemp(prefix="mogo_reconcile_")
        stub = os.path.join(tmp, "python3")
        with open(stub, "w", encoding="utf-8") as handle:
            handle.write("#!/bin/sh\nprintf '%s' \"$STUB_OUTPUT\"\nexit %d\n"
                         % ("%s", exit_code))
        os.chmod(stub, 0o755)
        script = os.path.join(tmp, "fragment.sh")
        with open(script, "w", encoding="utf-8") as handle:
            handle.write("set -uo pipefail\nsay() { echo \"$*\"; }\n")
            handle.write(self.extract().replace("if [ $WRITE -eq 1 ]; then",
                                                "if [ 1 -eq 1 ]; then", 1))
            handle.write("\necho REACHED_THE_END\n")
        env = dict(os.environ, PATH=tmp + os.pathsep + os.environ["PATH"],
                   STUB_OUTPUT=output)
        return subprocess.run(["bash", script], capture_output=True, text=True,
                              env=env)

    def test_a_PASSING_reconciliation_continues(self):
        result = self.run_with(0)
        self.assertIn("REACHED_THE_END", result.stdout, result.stderr)
        self.assertEqual(result.returncode, 0)

    def test_a_FAILING_reconciliation_stops_the_run(self):
        result = self.run_with(1, output="Ran 102 tests\nFAILED (failures=1)\n")
        self.assertNotIn("REACHED_THE_END", result.stdout,
                         "the capture chain continued past a failed reconciliation")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FAIL: reconciliation failed", result.stderr)

    def test_a_reconciliation_that_COLLECTED_NOTHING_stops_the_run(self):
        # `python3 -m unittest` returns 5 on NO TESTS RAN, so a suite that silently
        # stopped collecting is a failure rather than a pass.
        result = self.run_with(5, output="\nNO TESTS RAN\n")
        self.assertNotIn("REACHED_THE_END", result.stdout)
        self.assertNotEqual(result.returncode, 0)

    def test_unittest_really_does_return_5_on_no_tests(self):
        # The premise of the test above, measured rather than assumed.
        tmp = tempfile.mkdtemp(prefix="mogo_empty_")
        module = os.path.join(tmp, "empty_suite.py")
        with open(module, "w", encoding="utf-8") as handle:
            handle.write("import unittest\n")
        result = subprocess.run(["python3", "-m", "unittest", "empty_suite"],
                                capture_output=True, text=True, cwd=tmp)
        self.assertNotEqual(result.returncode, 0,
                            "a suite that collected nothing exited 0, so the "
                            "no-collection guard proves nothing")


if __name__ == "__main__":
    unittest.main()

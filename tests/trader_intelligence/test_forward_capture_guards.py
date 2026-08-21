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

    #: INVERTED, and deliberately. This was a list of commands that CAN fail --
    #: `python3`, `node`, `bash`, `osascript` -- so a piped call to
    #: `scripts/mogo_evidence_checkpoint.sh` (which this script already invokes
    #: twice), or `env python3 ...`, or `cat x | python3 ...`, was simply not seen.
    #: A scan that must be told about each new command fails open on the next one.
    #:
    #: Everything is failure-capable unless it is one of these, which cannot fail in
    #: a way worth guarding.
    CANNOT_FAIL = ("echo", "printf", "true", ":", "sed", "awk", "tail", "head",
                   "grep", "tr", "cut", "sort", "wc", "basename", "dirname", "date")

    def logical_lines(self):
        """Physical lines joined into the statements the shell actually runs.

        `splitlines()` saw a continued pipeline as two lines -- the first with no
        `|` at all, the second beginning with `| sed`, whose only segment is a
        filter -- so neither looked failure-capable and the step was invisible.
        A scan that reads physical lines is scanning a different program than the
        one bash runs.
        """
        joined, buffer, start = [], "", None
        for number, line in enumerate(source().splitlines(), start=1):
            stripped = line.rstrip()
            if start is None:
                start = number
            continues = stripped.endswith("\\") or stripped.rstrip().endswith("|")
            buffer += (stripped[:-1] if stripped.endswith("\\") else stripped) + " "
            if continues:
                continue
            joined.append((start, buffer.strip()))
            buffer, start = "", None
        if buffer.strip():
            joined.append((start, buffer.strip()))
        return joined

    def pipelines(self):
        """Bare pipelines whose exit status is otherwise discarded.

        Skipped, because their status is already consumed by the shell: `if <pipe>`
        and `while <pipe>`; anything containing `||`, which guards inline; a `[ ... ]`
        test, which is not a command; and `VAR="$(...)"`, where the assignment
        carries the status and the script tests the captured value instead.

        What is left is a statement whose status the shell throws away -- the only
        place a guard has to be written by hand, and the place the reconcile step
        was missing one.
        """
        found = []
        for number, line in self.logical_lines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if stripped.startswith(("[", "if ", "elif ", "while ", "until ")):
                continue
            if "||" in stripped or "&&" in stripped:
                continue
            # Command substitution is checked BEFORE the pipe requirement:
            # `VAR="$(python3 ...)"` has no pipe at all, so requiring one skipped
            # every unexamined capture that was not also a pipeline.
            substitution = re.match(
                r'^(?:local\s+)?([A-Za-z_][A-Za-z0-9_]*)="?\$\(', stripped)
            if substitution:
                # Skipped ONLY if the captured value is actually examined. The
                # assignment carries the status, but a value nothing looks at is a
                # command whose failure nobody notices -- `VAR=$(python3 ...)` with
                # no test is as unguarded as a bare pipeline.
                name = substitution.group(1)
                inner = stripped[stripped.index("$(") + 2:]
                heads = [seg.strip().split(" ", 1)[0].lstrip("!$(").strip()
                         for seg in inner.split("|") if seg.strip()]
                if all(head in self.CANNOT_FAIL for head in heads):
                    # `X="$(echo "$OUT" | awk ...)"` captures a filter chain that
                    # cannot fail; demanding a test for it would be noise, and noise
                    # is how a real scan ends up deleted.
                    continue
                # Guarded if the VALUE is examined, or if the STATUS is captured
                # on the following line and tested -- `X="$(...)"` then `X_RC=$?`
                # then `if [ $X_RC -ne 0 ]` is the form this script actually uses.
                if self.is_examined(name) or self.status_is_checked(number):
                    continue
                found.append((number, stripped))
                continue
            if "|" not in stripped:
                continue
            segments = [seg.strip().split(" ", 1)[0].lstrip("!").strip()
                        for seg in stripped.split("|") if seg.strip()]
            if all(seg in self.CANNOT_FAIL for seg in segments):
                continue
            found.append((number, stripped))
        return found

    def is_examined(self, name):
        """Is this captured value ever tested, rather than merely assigned?"""
        body = source()
        return bool(re.search(
            r'(\[\s*-[nz]\s+"?\$\{?%s\}?"?|\$\{?%s\}?"?\s*-eq |'
            r'\[\s*"?\$\{%s[:\-}][^\]]*\]|\$\{%s:\?)'
            % (re.escape(name), re.escape(name), re.escape(name),
               re.escape(name)), body))

    def status_is_checked(self, number):
        """Does a `$?` captured just after this line get tested?"""
        lines = source().splitlines()
        window = "\n".join(lines[number:number + 4])
        captured = re.search(r'([A-Za-z_][A-Za-z0-9_]*)="?\$\?"?', window)
        if not captured:
            return False
        after = "\n".join(lines[number:number + 14])
        return bool(re.search(r'\$\{?%s\}?"?\s*-(?:eq|ne) ' % re.escape(
            captured.group(1)), after))

    def test_the_scan_finds_the_pipelines_it_is_supposed_to(self):
        found = self.pipelines()
        self.assertGreaterEqual(len(found), 3,
                                "the scan found almost nothing, so every assertion "
                                "below would pass vacuously: %r" % (found,))
        # By content, not only by count: the reconcile step is the one that was
        # unguarded, so a scan that stops seeing it has stopped doing its job even
        # if the total happens to hold.
        self.assertTrue(any("test_import_mogo_observations" in text
                            for _line, text in found),
                        "the reconcile pipeline is no longer scanned")

    def test_the_scan_DETECTS_an_unguarded_step_added_to_the_script(self):
        # The anti-vacuity proof, and the thing a count cannot give: feed the scan a
        # script containing steps it must catch and steps it must not, and check it
        # separates them. Written against the real predicate, not a copy of it.
        must_catch = [
            'python3 scripts/thing.py 2>&1 | sed \'s/^/    /\'',
            'node scripts/thing.js --flag 2>&1 | tail -3',
            'scripts/mogo_evidence_checkpoint.sh --selftest 2>&1 | sed \'s/^/  /\'',
            'env python3 scripts/thing.py 2>&1 | sed \'s/^/  /\'',
            'cat input.json | python3 scripts/thing.py | sed \'s/^/  /\'',
            # Round 25's three: a continued pipeline, an unexamined capture, and a
            # quoted status assignment with a fail-open default.
            'python3 scripts/thing.py 2>&1 \\\n    | sed \'s/^/    /\'',
            'UNCHECKED="$(python3 scripts/thing.py)"',
        ]
        must_ignore = [
            'echo "$DETECT" | sed \'s/^/    /\'',
            'if ! python3 scripts/thing.py 2>&1 | sed \'s/^/ /\'; then',
            'python3 scripts/thing.py | sed \'s/^/ /\' || exit 1',
            'CKPT="$(echo "$OUT" | awk \'{print $3}\')"',
            '[ -n "$STORE" ] | true',
        ]
        original = globals()["source"]
        for line in must_catch:
            with self.subTest(catch=line[:44]):
                globals()["source"] = lambda body=line: body
                try:
                    self.assertEqual(len(self.pipelines()), 1,
                                     "an unguarded failure-capable step was not "
                                     "seen, so adding one would be silent")
                finally:
                    globals()["source"] = original
        for line in must_ignore:
            with self.subTest(ignore=line[:44]):
                globals()["source"] = lambda body=line: body
                try:
                    self.assertEqual(self.pipelines(), [],
                                     "a step whose status the shell already "
                                     "consumes was reported; false positives are "
                                     "how a real scan gets deleted")
                finally:
                    globals()["source"] = original

    def test_pipefail_is_set_or_the_if_not_form_proves_nothing(self):
        # `if ! cmd | sed` only catches a failing `cmd` BECAUSE pipefail is set.
        # Without it the pipeline reports sed's status, which is always 0.
        self.assertRegex(source(), r"set -[a-z]*o pipefail|set -o pipefail")

    def test_every_failable_pipeline_is_GUARDED(self):
        lines = source().splitlines()
        for number, text in self.pipelines():
            with self.subTest(line=number, code=text[:70]):
                # Follows the VARIABLE, not a fixed number of lines. A window of N
                # lines is broken by adding a comment -- which is how this test
                # first failed, on a step that was correctly guarded.
                window = "\n".join(lines[number:number + 12])
                captured = re.search(r"([A-Za-z_][A-Za-z0-9_]*)=\$\{PIPESTATUS\[0\]\}",
                                     window)
                # AFTER the capture, not merely somewhere near it. Testing the
                # variable on the line above its assignment reads as guarded to any
                # window-based scan while the variable is unset at the moment of the
                # test. It fails closed today only because the default is 1 -- which
                # is the whole reason that default is 1.
                tested = bool(captured and re.search(
                    r"\$\{%s[:\-}][^\n]*-eq 0 \]" % re.escape(captured.group(1)),
                    window[captured.end():]))
                self.assertTrue(captured and tested,
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
        # Scoped by USAGE, not by name. The first version matched `[A-Z_]*RC`,
        # written while looking at IMPORT_RC and RECONCILE_RC -- and a lowercase
        # `rc` sibling four lines from the top of the same file, inside the function
        # called before every exit of the chain, was invisible to it. An invariant
        # scoped to the names you happened to be looking at is an instance patch
        # wearing a table.
        #
        # Widening it to every variable was wrong the other way: `${REFUSED_COUNT:-0}`
        # is a count, and zero is its correct default. A STATUS variable is one
        # assigned from `$?` or `PIPESTATUS` -- that is what makes zero mean "fine".
        body = source()
        # Quoted forms too. `EXTRA_RC="$?"` is the same variable with the same
        # meaning, and matching only the bare form let a fail-open default sit
        # beside it unseen.
        status_vars = set(re.findall(
            r'(?:local\s+)?([A-Za-z_][A-Za-z0-9_]*)="?\$\{PIPESTATUS\[\d+\]\}"?',
            body))
        status_vars |= set(re.findall(
            r'(?:local\s+)?([A-Za-z_][A-Za-z0-9_]*)="?\$\?"?', body))
        self.assertTrue(status_vars,
                        "no exit-status variables found -- passes vacuously")
        defaults = [(name, value) for name, value
                    in re.findall(r"\$\{([A-Za-z_][A-Za-z0-9_]*):-(\d+)\}", body)
                    if name in status_vars]
        self.assertTrue(defaults, "no rc defaults found -- passes vacuously")
        self.assertTrue(defaults,
                        "no exit-status defaults found -- passes vacuously")
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

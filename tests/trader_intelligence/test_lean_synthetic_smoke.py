"""The synthetic LEAN smoke package must stay reproducible, isolated and honestly labelled.

This is the REGISTERED guard over tests/lean_synthetic/. It does not run LEAN and cannot: it
asserts that the package still generates its own data, still reaches no historical input, still
matches its manifest, and still matches the expectations the engine algorithm asserts.

WHY IT EXISTS. The package's own local validator lives beside the package and is run by hand.
Nothing in the repository gate noticed if the package rotted, if a fixture stopped reproducing,
or if someone pointed it at the historical corpus. That last one matters most: a previous
session ran two Mode B harnesses that DID read OANDA-derived CSVs, after reporting that no raw
evidence had been opened. The isolation assertions below are the durable form of that lesson.

No network access, no historical artifact, and no OANDA-derived data is touched by any test here.
"""
import ast
import hashlib
import os
import re
import subprocess
import sys
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                         "..", ".."))
PKG = os.path.join(REPO_ROOT, "tests", "lean_synthetic")
sys.path.insert(0, PKG)

import synthetic_bars as sb        # noqa: E402
from br_machine import BreakRetestMachine, Bar, S_LOCKED, S_BROKEN   # noqa: E402

CONFIG = {"breakConfirmationCloses": 1, "maxBarsBetweenBreakAndRetest": 50,
          "stopATRBuffer": 0.25, "atrPeriod": 14, "minRR": 2.0, "trendSwingLookback": 3,
          "rejectionConfirmWithinBars": 1, "rejectionDisplacementATRMultiplier": 0.25}

#: The reviewed Mode B state machine, byte-identical to the variant recorded in the Mode B
#: package. If this hash moves, the smoke test is no longer exercising the reviewed code.
REVIEWED_BR_MACHINE_SHA = \
    "29e29578c1b841b7e03a13ba58ca1692815094922adbe00b7fba387b98aaa54a"


def _read(name):
    with open(os.path.join(PKG, name), encoding="utf-8") as handle:
        return handle.read()


def _sha(name):
    with open(os.path.join(PKG, name), "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def _run(case):
    machine = BreakRetestMachine(CONFIG, sb.ZONE_LOW, sb.ZONE_HIGH, sb.ZONE_ROLE,
                                 sb.ZONE_FROM_INDEX)
    for index, ms, o, h, l, c in sb.series(case):
        machine.on_bar(Bar(index, ms, o, h, l, c))
    return machine


class TestTheSyntheticDataIsGeneratedNotBorrowed(unittest.TestCase):

    def test_the_generator_imports_nothing_and_opens_nothing(self):
        # Asserted over the AST, not the file text: the module's own docstring says the word
        # OANDA in a disclaimer, and a substring search over prose would be satisfied by it --
        # the same comment-satisfies-the-assertion trap a run_all fixture hit earlier.
        tree = ast.parse(_read("synthetic_bars.py"))
        imports, opens = [], []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports += [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")
            elif isinstance(node, ast.Call) and getattr(node.func, "id", "") == "open":
                opens.append(ast.unparse(node))
        self.assertEqual(imports, [], "the generator must import nothing at all")
        self.assertEqual(opens, [], "the generator must read no file")

    def test_no_package_file_names_a_historical_input_in_code(self):
        pattern = re.compile(r"MBR\d|vectors_part|ledger-preservation|/evidence/", re.I)
        for name in ("synthetic_bars.py", "br_machine.py", "main.py"):
            with self.subTest(file=name):
                tree = ast.parse(_read(name))
                docstrings = set()
                for node in ast.walk(tree):
                    if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                                         ast.ClassDef)):
                        doc = ast.get_docstring(node)
                        if doc:
                            docstrings.add(doc)
                hits = [n.value for n in ast.walk(tree)
                        if isinstance(n, ast.Constant) and isinstance(n.value, str)
                        and n.value not in docstrings and pattern.search(n.value)]
                self.assertEqual(hits, [], "%s references a historical input in code" % name)

    def test_both_fixtures_reproduce_byte_exactly_from_the_generator(self):
        for case in sb.CASES:
            with self.subTest(case=case):
                self.assertEqual(_read("mogo_synthetic_%s.csv" % case), sb.csv_text(case))

    def test_the_fixtures_are_numeric_only(self):
        for case in sb.CASES:
            with self.subTest(case=case):
                rows = _read("mogo_synthetic_%s.csv" % case).strip().split("\n")[1:]
                self.assertEqual(len(rows), 120)
                for row in rows:
                    self.assertRegex(row, r"^\d+,\d+,[\d.]+,[\d.]+,[\d.]+,[\d.]+$")

    def test_every_bar_is_well_formed_ohlc(self):
        for case in sb.CASES:
            with self.subTest(case=case):
                for index, _ms, o, h, l, c in sb.series(case):
                    self.assertTrue(l <= o <= h and l <= c <= h,
                                    "bar %d is not well-formed" % index)


class TestTheReviewedMachineAndTheExpectedCases(unittest.TestCase):

    def test_the_state_machine_is_the_REVIEWED_one(self):
        self.assertEqual(_sha("br_machine.py"), REVIEWED_BR_MACHINE_SHA)

    def test_the_machine_knows_nothing_about_the_cases_or_expected_answers(self):
        # Expected answers must live in validation code. A machine that could see them would
        # make every assertion below circular.
        self.assertNotRegex(_read("br_machine.py"), r"SYNQUAL|SYNREJ|EXPECT|locked_at")

    def test_the_qualifying_case_produces_a_decision(self):
        machine = _run("qualify")
        self.assertEqual(machine.state, S_LOCKED)
        self.assertTrue(machine.decision and machine.decision["qualifies"] is True)

    def test_the_rejecting_case_produces_NO_decision(self):
        machine = _run("reject")
        self.assertEqual(machine.state, S_BROKEN, "the break must still have happened")
        self.assertIsNone(machine.decision)

    def test_the_two_cases_DIFFER(self):
        # Without this, the rejecting case would also pass if nothing ever qualified.
        self.assertIsNotNone(_run("qualify").decision)
        self.assertIsNone(_run("reject").decision)

    def test_the_algorithm_expects_what_the_machine_actually_produces(self):
        decision = _run("qualify").decision
        main_src = _read("main.py")
        self.assertIn("'locked_at': %d" % decision["lockedAtBarIndex"], main_src)
        self.assertIn("'state': 'LOCKED'", main_src)
        self.assertIn("'state': 'BROKEN'", main_src)

    def test_the_decision_uses_only_bars_up_to_the_lock(self):
        full = _run("qualify")
        lock = full.decision["barsConsumedAtLock"]
        truncated = BreakRetestMachine(CONFIG, sb.ZONE_LOW, sb.ZONE_HIGH, sb.ZONE_ROLE,
                                       sb.ZONE_FROM_INDEX)
        for index, ms, o, h, l, c in sb.series("qualify")[:lock]:
            truncated.on_bar(Bar(index, ms, o, h, l, c))
        self.assertEqual(truncated.decision, full.decision)

    def test_POSITIVE_CONTROL_poisoning_from_BEFORE_the_lock_does_move_the_decision(self):
        # The truncation test above is only meaningful if the feed can move the decision at all.
        full = _run("qualify")
        lock = full.decision["barsConsumedAtLock"]
        poisoned = BreakRetestMachine(CONFIG, sb.ZONE_LOW, sb.ZONE_HIGH, sb.ZONE_ROLE,
                                      sb.ZONE_FROM_INDEX)
        for k, (index, ms, o, h, l, c) in enumerate(sb.series("qualify")):
            if k >= lock - 6:
                o, h, l, c = o + 50, h + 50, l + 50, c + 50
            poisoned.on_bar(Bar(index, ms, o, h, l, c))
        self.assertNotEqual(poisoned.decision, full.decision)


class TestThePackageIsCompleteAndHonestlyLabelled(unittest.TestCase):

    def test_the_manifest_covers_every_file_and_matches(self):
        manifest = {}
        for line in _read("MANIFEST.sha256").splitlines():
            if line.startswith("#") or not line.strip():
                continue
            digest, name = line.split("  ", 1)
            manifest[name] = digest
        on_disk = {f for f in os.listdir(PKG)
                   if not f.startswith(".") and f not in ("__pycache__", "MANIFEST.sha256",
                                                          "RUN_PROCEDURE.md")}
        self.assertEqual(set(manifest), on_disk, "manifest and directory disagree")
        for name, digest in manifest.items():
            with self.subTest(file=name):
                self.assertEqual(_sha(name), digest)

    def test_the_engine_algorithm_uses_revision_pinned_urls(self):
        pinned = re.findall(r"/raw/([0-9a-f]{40})/", _read("main.py"))
        self.assertEqual(len(pinned), 2, "both cases must have a pinned fixture URL")
        self.assertEqual(len(set(pinned)), 1, "both must pin the SAME gist revision")
        self.assertNotIn("REPLACE-ME", _read("main.py"))

    def test_the_run_procedure_does_not_claim_local_validation_is_an_engine_run(self):
        procedure = _read("RUN_PROCEDURE.md")
        self.assertIn("not** an engine run", procedure)
        self.assertIn("Creative Red Panda", procedure,
                      "the procedure must name the parity project it must NOT touch")

    def test_the_local_validator_runs_clean_offline(self):
        # The package's own validator, executed as a subprocess. Its inputs were audited: it
        # imports only stdlib plus the two package modules and opens only files in its own
        # directory, so it cannot reach a historical artifact.
        result = subprocess.run([sys.executable, os.path.join(PKG, "test_synthetic_local.py")],
                                capture_output=True, text=True, cwd=PKG)
        self.assertEqual(result.returncode, 0,
                         "local validator failed:\n%s" % result.stdout[-1500:])
        self.assertIn("RESULT: PASS", result.stdout)
        self.assertIn("THIS IS NOT AN ENGINE RUN", result.stdout,
                      "the validator must keep saying what it is not")

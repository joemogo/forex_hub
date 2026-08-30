"""The engine-log importer must accept exactly one shape of evidence and refuse the rest.

WHAT IS UNDER TEST. `tests/lean_synthetic/smoke_log.py` (the shared parser, the ONLY place the
verdict logic lives) and `tests/lean_synthetic/import_run.py` (the command that validates a log
and preserves its bytes).

WHAT THE INPUTS ARE. Synthetic logs built in temp directories by mutating ONE already-preserved
artefact, `tests/lean_synthetic/evidence/CALM_YELLOW_PIG_2026-08-30.log`, which is read and
never written. No network, no historical corpus, no OANDA-derived data, no forward evidence.
Every write in this file goes to a `mkdtemp` directory; nothing is written into the package's
own `evidence/`, and a test at the end asserts the preserved log is byte-identical afterwards.

WHY EACH REJECTION HAS A POSITIVE CONTROL. A rejection test passes vacuously if the importer
rejects everything -- including the mutation's own base. Every mutation below is built by the
same helper that builds the accepted base log, and `test_POSITIVE_CONTROL_the_unmutated_builder
_is_ACCEPTED` proves that pipeline yields an accepted import, so a rejection is attributable to
the mutation and to nothing else.

WHAT NONE OF THIS ESTABLISHES. That LEAN ran, that the numbers in any log are true, or that the
source executed in QuantConnect is the source in this repository. This is a test of a reader of
reports, not of the thing the reports describe.
"""
import ast
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                         "..", ".."))
PKG = os.path.join(REPO_ROOT, "tests", "lean_synthetic")
PRESERVED_LOG = os.path.join(PKG, "evidence", "CALM_YELLOW_PIG_2026-08-30.log")
IMPORT_RUN = os.path.join(PKG, "import_run.py")
sys.path.insert(0, PKG)

import smoke_log                                                       # noqa: E402


def read_text(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def read_bytes(path):
    with open(path, "rb") as handle:
        return handle.read()


with open(PRESERVED_LOG, encoding="utf-8") as _handle:
    BASE_TEXT = _handle.read()
with open(os.path.join(PKG, "main.py"), encoding="utf-8") as _handle:
    MAIN_SRC = _handle.read()
DECLARED = smoke_log.declared_checks_from_source(MAIN_SRC)

OK = 0
REJECTED = 2
NOT_ENGINE_EVIDENCE = 3
COLLISION = 4
BUNDLE_MISMATCH = 5

OTHER_ID = "a1b2c3d4e5f60718293a4b5c6d7e8f90"


# ---------------------------------------------------------------------------- log mutation --
def lines_of(text):
    return text.splitlines(True)


def drop_lines(text, needle):
    kept = [line for line in lines_of(text) if needle not in line]
    assert len(kept) < len(lines_of(text)), "mutation matched nothing: %r" % needle
    return "".join(kept)


def replace_in_line(text, needle, old, new):
    out, hits = [], 0
    for line in lines_of(text):
        if needle in line and old in line:
            line, hits = line.replace(old, new), hits + 1
        out.append(line)
    assert hits, "mutation matched nothing: %r / %r" % (needle, old)
    return "".join(out)


def duplicate_line(text, needle):
    out, hits = [], 0
    for line in lines_of(text):
        out.append(line)
        if needle in line and not hits:
            out.append(line)
            hits += 1
    assert hits, "mutation matched nothing: %r" % needle
    return "".join(out)


def insert_after(text, needle, new_line):
    out, hits = [], 0
    for line in lines_of(text):
        out.append(line)
        if needle in line and not hits:
            out.append(new_line if new_line.endswith("\n") else new_line + "\n")
            hits += 1
    assert hits, "mutation matched nothing: %r" % needle
    return "".join(out)


def truncate_after(text, count):
    return "".join(lines_of(text)[:count])


# ---------------------------------------------------------------------------- CLI harness ---
class ImporterHarness(unittest.TestCase):
    """Every test gets its own throwaway source and evidence directories."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="lean_import_test_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.src = os.path.join(self.tmp, "incoming")
        self.evidence = os.path.join(self.tmp, "evidence")
        os.makedirs(self.src)
        os.makedirs(self.evidence)

    def write_log(self, text, name="TEST_RUN_2026-08-30.log"):
        path = os.path.join(self.src, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def run_import(self, log_path, *extra):
        argv = [sys.executable, IMPORT_RUN, log_path,
                "--evidence-dir", self.evidence, "--package-dir", PKG] + list(extra)
        proc = subprocess.run(argv, capture_output=True, text=True, cwd=self.tmp)
        return proc.returncode, proc.stdout + proc.stderr

    def import_text(self, text, *extra, **kwargs):
        return self.run_import(self.write_log(text, kwargs.get("name",
                                                               "TEST_RUN_2026-08-30.log")),
                               *extra)

    def evidence_files(self):
        return sorted(os.listdir(self.evidence))

    def record_text(self, name="TEST_RUN_2026-08-30.RUN_RECORD.md"):
        with open(os.path.join(self.evidence, name), encoding="utf-8") as handle:
            return handle.read()

    def assertRefused(self, code, output, expected_code, *needles):
        self.assertEqual(code, expected_code, "wrong exit code. output:\n%s" % output)
        self.assertIn("IMPORT REFUSED", output)
        for needle in needles:
            self.assertIn(needle, output)


# ---------------------------------------------------------------------- the parser is shared -
class TestTheVerdictLogicLivesInExactlyOnePlace(unittest.TestCase):

    def test_the_importer_reimplements_no_part_of_the_log_grammar(self):
        # If the importer grew its own regexes, the two would drift and the log would be
        # judged by whichever one the caller happened to reach. It must delegate.
        source = read_text(IMPORT_RUN)
        self.assertIn("import smoke_log", source)
        self.assertIn("smoke_log.parse_smoke_log", source)
        for token in ("SMOKE-CHECK", "SMOKE-CASE", "SMOKE-VERDICT", "Launching analysis",
                      "Algorithm Id:"):
            with self.subTest(token=token):
                self.assertNotIn(token, source,
                                 "the importer parses %r itself instead of delegating" % token)

    def test_the_parser_is_a_library_with_no_import_time_side_effects(self):
        tree = ast.parse(read_text(os.path.join(PKG, "smoke_log.py")))
        for node in tree.body:
            with self.subTest(node=type(node).__name__):
                self.assertIsInstance(node, (ast.Import, ast.ImportFrom, ast.Assign,
                                             ast.AnnAssign, ast.FunctionDef, ast.ClassDef,
                                             ast.Expr))
                if isinstance(node, ast.Expr):
                    self.assertIsInstance(node.value, ast.Constant,
                                          "a bare call runs at import time")
        opens = [n for n in ast.walk(tree)
                 if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "open"]
        self.assertEqual(opens, [], "the parser must open no file of its own")

    def test_the_expected_checks_are_DERIVED_from_the_algorithm_not_hard_coded(self):
        # The point of the extraction: a new log can be judged without editing a constant,
        # and a change to the algorithm's checks moves the expectation with it.
        self.assertEqual(set(DECLARED.tickers), {"SYNQUAL", "SYNREJ"})
        self.assertEqual(len(DECLARED.case_checks), 10)
        self.assertEqual(len(set(DECLARED.case_checks)), 10, "the algorithm declares a dup")
        self.assertEqual(set(DECLARED.global_checks),
                         {"case_state_isolated", "no_unexpected_symbols"})
        logged = set(name for _case, name, _status
                     in smoke_log.parse_smoke_log(BASE_TEXT).check_tuples)
        self.assertEqual(logged, set(DECLARED.case_checks) | set(DECLARED.global_checks))

    def test_a_check_the_algorithm_stops_declaring_is_no_longer_expected(self):
        # Derivation, demonstrated: strike a check out of a COPY of the algorithm source and
        # the expectation follows. Nothing on disk is touched.
        edited = MAIN_SRC.replace("('locked_at', st.locked_at == exp['locked_at'],", "(", 1)
        self.assertNotIn("locked_at",
                         smoke_log.declared_checks_from_source(edited).case_checks)
        self.assertIn("locked_at", DECLARED.case_checks)


# ------------------------------------------------------------------- the known-good artefact -
class TestThePreservedLogIsTheKnownGoodCase(unittest.TestCase):

    def parse(self):
        return smoke_log.parse_smoke_log(BASE_TEXT, declared=DECLARED)

    def test_it_parses_with_no_problem_at_all(self):
        result = self.parse()
        self.assertEqual(result.reasons(), [])
        self.assertTrue(result.ok)

    def test_the_identifiers_come_out_of_the_parse(self):
        result = self.parse()
        self.assertRegex(result.launch_id, r"^[0-9a-f]{32}$")
        self.assertEqual(result.launch_id, result.completion_id)
        self.assertEqual(len(result.algorithm_ids), 1)
        self.assertEqual(result.lean_version, "2.5.0.0.18041")

    def test_the_structure_comes_out_of_the_parse(self):
        result = self.parse()
        self.assertEqual(len(result.checks), 22)
        self.assertEqual([c for c in result.checks if not c.passed], [])
        self.assertEqual(sorted(result.cases), ["SYNQUAL", "SYNREJ"])
        self.assertEqual(len(result.checks_for("SYNQUAL")), 10)
        self.assertEqual(len(result.checks_for("SYNREJ")), 10)
        self.assertEqual(len(result.checks_for(smoke_log.GLOBAL_CASE)), 2)
        self.assertTrue(result.verdict.passed)
        self.assertEqual(result.engine, "LEAN")
        self.assertEqual(result.cases["SYNQUAL"].locked_at, "55")
        self.assertEqual(result.cases["SYNREJ"].state, "BROKEN")

    def test_it_qualifies_as_engine_evidence(self):
        is_engine, reasons = smoke_log.engine_evidence(self.parse())
        self.assertTrue(is_engine, reasons)
        self.assertEqual(reasons, [])


# ------------------------------------------------------------------------------- acceptance --
class TestAValidLogIsImported(ImporterHarness):

    def test_POSITIVE_CONTROL_the_unmutated_builder_is_ACCEPTED(self):
        # Every rejection below mutates the text this test imports, through this same helper.
        # Without this, a rejection test could pass because the harness rejects everything.
        code, out = self.import_text(BASE_TEXT)
        self.assertEqual(code, OK, out)
        self.assertIn("IMPORT OK", out)
        self.assertIn("22/22 PASS", out)

    def test_the_bytes_are_preserved_verbatim_and_hashed_automatically(self):
        code, out = self.import_text(BASE_TEXT)
        self.assertEqual(code, OK, out)
        target = os.path.join(self.evidence, "TEST_RUN_2026-08-30.log")
        with open(target, "rb") as handle:
            written = handle.read()
        self.assertEqual(written, BASE_TEXT.encode("utf-8"))
        digest = hashlib.sha256(written).hexdigest()
        self.assertIn(digest, out)
        self.assertIn(digest, self.record_text())

    def test_the_name_and_date_come_from_the_filename_or_the_flags(self):
        code, out = self.import_text(BASE_TEXT, "--name", "Calm Yellow Pig",
                                     "--date", "2026-08-30")
        self.assertEqual(code, OK, out)
        self.assertIn("CALM_YELLOW_PIG_2026-08-30.log", self.evidence_files())
        self.assertIn("CALM_YELLOW_PIG_2026-08-30.RUN_RECORD.md", self.evidence_files())

    def test_an_undatable_filename_is_REFUSED_rather_than_dated_by_guesswork(self):
        # Stamping today's date on a run observed at an unknown time would fabricate a fact.
        code, out = self.import_text(BASE_TEXT, name="mystery.log")
        self.assertEqual(code, 6, out)
        self.assertIn("--date", out)
        # POSITIVE CONTROL: the same file with the date supplied imports.
        code, out = self.import_text(BASE_TEXT, "--date", "2026-08-30", name="mystery.log")
        self.assertEqual(code, OK, out)

    def test_the_record_identifiers_are_PARSED_not_transcribed(self):
        # A record built from a template with the id typed in would carry the OLD id here.
        moved = BASE_TEXT.replace("3fca3b003a7f8db84f343512ea9835fa", OTHER_ID)
        moved = moved.replace("v2.5.0.0.18041", "v9.9.9.9.99999")
        code, out = self.import_text(moved)
        self.assertEqual(code, OK, out)
        record = self.record_text()
        self.assertIn(OTHER_ID, record)
        self.assertIn("v9.9.9.9.99999", record)
        self.assertNotIn("3fca3b003a7f8db84f343512ea9835fa", record)

    def test_the_dry_run_validates_and_writes_nothing(self):
        code, out = self.import_text(BASE_TEXT, "--dry-run")
        self.assertEqual(code, OK, out)
        self.assertEqual(self.evidence_files(), [])


# ------------------------------------------------------------------------------- rejections --
class TestABadLogIsRefusedAndTheReasonIsNamed(ImporterHarness):

    def parse(self, text):
        return smoke_log.parse_smoke_log(text, declared=DECLARED)

    def test_a_MISSING_check_is_refused(self):
        text = drop_lines(BASE_TEXT, "SMOKE-CHECK SYNREJ   first_index")
        self.assertIn("missing_check", self.parse(text).problem_codes)
        code, out = self.import_text(text)
        self.assertRefused(code, out, REJECTED, "missing_check", "first_index")

    def test_a_DUPLICATE_check_is_refused(self):
        text = duplicate_line(BASE_TEXT, "SMOKE-CHECK SYNQUAL  last_index")
        self.assertIn("duplicate_check", self.parse(text).problem_codes)
        code, out = self.import_text(text)
        self.assertRefused(code, out, REJECTED, "duplicate_check", "last_index")

    def test_a_check_the_algorithm_does_not_declare_is_refused(self):
        text = insert_after(
            BASE_TEXT, "SMOKE-CHECK SYNQUAL  last_index",
            "2020-06-01 16:00:00 SMOKE-CHECK SYNQUAL  invented_check           PASS 0")
        self.assertIn("undeclared_check", self.parse(text).problem_codes)
        code, out = self.import_text(text)
        self.assertRefused(code, out, REJECTED, "undeclared_check", "invented_check")

    def test_a_FAILED_case_is_refused_even_when_the_log_is_self_consistent(self):
        # Consistently reported failure: check FAIL, case FAIL, verdict FAIL, all agreeing.
        # It must still be refused -- and refused for the FAILURE, not for an inconsistency.
        text = replace_in_line(BASE_TEXT, "SMOKE-CHECK SYNQUAL  locked_at",
                               "PASS 55 want 55", "FAIL 54 want 55")
        text = replace_in_line(text, "SMOKE-CASE SYNQUAL",
                               "PASS bars=120", "FAIL bars=120")
        text = replace_in_line(text, "SMOKE-CASE SYNQUAL", "failed=none", "failed=locked_at")
        text = replace_in_line(text, "SMOKE-VERDICT", "PASS engine", "FAIL engine")
        text = replace_in_line(text, "SMOKE-VERDICT", "failed=none", "failed=locked_at")
        codes = self.parse(text).problem_codes
        self.assertIn("check_failed", codes)
        self.assertNotIn("case_contradiction", codes)
        self.assertNotIn("verdict_contradiction", codes)
        code, out = self.import_text(text)
        self.assertRefused(code, out, REJECTED, "check_failed", "locked_at")

    def test_a_verdict_that_CONTRADICTS_its_own_checks_is_refused(self):
        # The dangerous shape: a green verdict over a red check.
        text = replace_in_line(BASE_TEXT, "SMOKE-CHECK SYNREJ   terminal_state",
                               "PASS BROKEN want BROKEN", "FAIL LOCKED want BROKEN")
        codes = self.parse(text).problem_codes
        self.assertIn("verdict_contradiction", codes)
        self.assertIn("case_contradiction", codes)
        code, out = self.import_text(text)
        self.assertRefused(code, out, REJECTED, "verdict_contradiction")
        self.assertIn("PASS while", out)

    def test_a_PASS_verdict_over_a_consistently_reported_failure_is_refused(self):
        # The sharpest form, and the one a redundant sibling check cannot catch: the case line
        # and the verdict's own failed= list BOTH name the failure honestly, and only the
        # verdict's PASS/FAIL word lies. Nothing but the status-versus-failures gate sees it.
        text = replace_in_line(BASE_TEXT, "SMOKE-CHECK SYNREJ   terminal_state",
                               "PASS BROKEN want BROKEN", "FAIL LOCKED want BROKEN")
        text = replace_in_line(text, "SMOKE-CASE SYNREJ", "PASS bars=120", "FAIL bars=120")
        text = replace_in_line(text, "SMOKE-CASE SYNREJ", "failed=none", "failed=terminal_state")
        text = replace_in_line(text, "SMOKE-VERDICT", "failed=none", "failed=terminal_state")
        result = self.parse(text)
        self.assertNotIn("case_contradiction", result.problem_codes,
                         "the case line is honest here; only the verdict is not")
        self.assertIn("verdict_contradiction", result.problem_codes)
        self.assertTrue(any("verdict is PASS" in reason for reason in result.reasons()),
                        result.reasons())
        code, out = self.import_text(text)
        self.assertRefused(code, out, REJECTED, "verdict_contradiction")

    def test_a_case_summary_that_CONTRADICTS_its_own_check_detail_is_refused(self):
        # Every check still says PASS; only the summary was edited. Nothing but the
        # summary-versus-detail cross-check can catch this.
        text = replace_in_line(BASE_TEXT, "SMOKE-CASE SYNQUAL",
                               "state=LOCKED", "state=BROKEN")
        self.assertIn("case_contradiction", self.parse(text).problem_codes)
        code, out = self.import_text(text)
        self.assertRefused(code, out, REJECTED, "case_contradiction", "state")

    def test_a_case_summary_that_understates_its_bar_count_is_refused(self):
        text = replace_in_line(BASE_TEXT, "SMOKE-CASE SYNREJ", "bars=120", "bars=119")
        self.assertIn("case_contradiction", self.parse(text).problem_codes)
        code, out = self.import_text(text)
        self.assertRefused(code, out, REJECTED, "case_contradiction", "bars")

    def test_DIFFERING_launch_and_completion_ids_are_refused(self):
        text = replace_in_line(BASE_TEXT, "Algorithm Id:",
                               "3fca3b003a7f8db84f343512ea9835fa", OTHER_ID)
        codes = self.parse(text).problem_codes
        self.assertIn("algorithm_id_mismatch", codes)
        self.assertIn("algorithm_id_count", codes)
        code, out = self.import_text(text)
        self.assertRefused(code, out, REJECTED, "algorithm_id_mismatch", OTHER_ID)

    def test_a_second_algorithm_id_ANYWHERE_is_refused(self):
        text = insert_after(BASE_TEXT, "Launching analysis",
                            "2019-12-31 00:00:01 Cloned from backtest %s" % OTHER_ID)
        self.assertIn("algorithm_id_count", self.parse(text).problem_codes)
        code, out = self.import_text(text)
        self.assertRefused(code, out, REJECTED, "algorithm_id_count")

    def test_TWO_launch_records_are_refused(self):
        text = duplicate_line(BASE_TEXT, "Launching analysis")
        self.assertIn("launch_record", self.parse(text).problem_codes)
        code, out = self.import_text(text)
        self.assertRefused(code, out, REJECTED, "launch_record", "found 2")

    def test_a_TRUNCATED_log_is_refused(self):
        text = truncate_after(BASE_TEXT, 15)
        codes = self.parse(text).problem_codes
        self.assertIn("truncated_log", codes)
        code, out = self.import_text(text)
        self.assertRefused(code, out, REJECTED, "truncated_log")

    def test_a_log_cut_after_the_verdict_is_still_refused(self):
        text = drop_lines(BASE_TEXT, "completed in")
        self.assertIn("truncated_log", self.parse(text).problem_codes)
        code, out = self.import_text(text)
        self.assertRefused(code, out, REJECTED, "completion record")

    def test_a_whole_MISSING_case_is_refused(self):
        text = "".join(line for line in lines_of(BASE_TEXT) if "SYNREJ" not in line)
        codes = self.parse(text).problem_codes
        self.assertIn("missing_case", codes)
        code, out = self.import_text(text)
        self.assertRefused(code, out, REJECTED, "SYNREJ")

    def test_checks_without_their_case_summary_are_refused(self):
        text = drop_lines(BASE_TEXT, "SMOKE-CASE SYNREJ")
        self.assertIn("missing_case_line", self.parse(text).problem_codes)
        code, out = self.import_text(text)
        self.assertRefused(code, out, REJECTED, "SMOKE-CASE")

    def test_a_missing_verdict_is_refused(self):
        text = drop_lines(BASE_TEXT, "SMOKE-VERDICT")
        self.assertIn("no_verdict", self.parse(text).problem_codes)
        code, out = self.import_text(text)
        self.assertRefused(code, out, REJECTED, "no_verdict")

    def test_NOTHING_is_written_when_a_log_is_refused(self):
        code, _out = self.import_text(drop_lines(BASE_TEXT, "SMOKE-VERDICT"))
        self.assertNotEqual(code, OK)
        self.assertEqual(self.evidence_files(), [])
        # POSITIVE CONTROL: the same directory does receive an accepted log.
        code, out = self.import_text(BASE_TEXT)
        self.assertEqual(code, OK, out)
        self.assertEqual(len(self.evidence_files()), 2)


# --------------------------------------------------------------------------- engine evidence -
class TestALocalRunIsNeverEngineEvidence(ImporterHarness):

    def test_engine_plain_python_is_REFUSED_however_green_it_is(self):
        # Every check still PASSes. The only difference is the engine token, and that alone
        # must be disqualifying: it means AlgorithmImports did not import.
        text = replace_in_line(BASE_TEXT, "SMOKE-VERDICT",
                               "engine=LEAN", "engine=%s" % smoke_log.LOCAL_ENGINE)
        result = smoke_log.parse_smoke_log(text, declared=DECLARED)
        self.assertEqual(result.reasons(), [], "the log is otherwise perfectly well formed")
        is_engine, reasons = smoke_log.engine_evidence(result)
        self.assertFalse(is_engine)
        self.assertTrue(any("LOCAL run" in reason for reason in reasons), reasons)
        code, out = self.import_text(text)
        self.assertRefused(code, out, NOT_ENGINE_EVIDENCE, smoke_log.LOCAL_ENGINE, "LOCAL run")
        self.assertEqual(self.evidence_files(), [], "a local run must not be preserved as one")

    def test_POSITIVE_CONTROL_the_same_log_with_engine_LEAN_is_accepted(self):
        # Without this, the refusal above would also pass if the importer refused everything.
        code, out = self.import_text(BASE_TEXT)
        self.assertEqual(code, OK, out)

    def test_engine_LEAN_ALONE_is_NOT_sufficient(self):
        # The algorithm prints `engine=LEAN` about itself. Strip the platform's own records --
        # which the algorithm cannot print -- and the claim is uncorroborated.
        text = drop_lines(BASE_TEXT, "Launching analysis")
        result = smoke_log.parse_smoke_log(text, declared=DECLARED)
        self.assertEqual(result.engine, "LEAN")
        is_engine, reasons = smoke_log.engine_evidence(result)
        self.assertFalse(is_engine, "engine=LEAN was accepted with no platform record")
        self.assertTrue(any("Launching analysis" in reason for reason in reasons), reasons)
        code, out = self.import_text(text)
        self.assertNotEqual(code, OK)
        self.assertIn("launch record", out)

    def test_an_unrecognised_engine_token_is_refused(self):
        text = replace_in_line(BASE_TEXT, "SMOKE-VERDICT", "engine=LEAN", "engine=something")
        is_engine, reasons = smoke_log.engine_evidence(
            smoke_log.parse_smoke_log(text, declared=DECLARED))
        self.assertFalse(is_engine, reasons)
        code, out = self.import_text(text)
        self.assertRefused(code, out, NOT_ENGINE_EVIDENCE, "something")


# ------------------------------------------------------------------- idempotency and collision
class TestPreservedBytesAreNeverOverwritten(ImporterHarness):

    def test_re_importing_the_IDENTICAL_log_changes_nothing(self):
        first_code, first_out = self.import_text(BASE_TEXT)
        self.assertEqual(first_code, OK, first_out)
        before = {name: read_bytes(os.path.join(self.evidence, name))
                  for name in self.evidence_files()}
        self.assertEqual(len(before), 2)

        second_code, second_out = self.import_text(BASE_TEXT)
        self.assertEqual(second_code, OK, second_out)
        self.assertIn("[unchanged]", second_out)
        after = {name: read_bytes(os.path.join(self.evidence, name))
                 for name in self.evidence_files()}
        self.assertEqual(after, before, "an idempotent re-import rewrote the evidence")

    def test_the_SAME_name_with_DIFFERENT_bytes_is_a_COLLISION(self):
        code, out = self.import_text(BASE_TEXT)
        self.assertEqual(code, OK, out)
        preserved = read_bytes(os.path.join(self.evidence, "TEST_RUN_2026-08-30.log"))

        other = BASE_TEXT.replace("3fca3b003a7f8db84f343512ea9835fa", OTHER_ID)
        self.assertNotEqual(other, BASE_TEXT)
        code, out = self.run_import(self.write_log(other, "OTHER.log"),
                                    "--name", "TEST_RUN", "--date", "2026-08-30")
        self.assertRefused(code, out, COLLISION, "already exists with DIFFERENT bytes")
        self.assertEqual(read_bytes(os.path.join(self.evidence,
                                                 "TEST_RUN_2026-08-30.log")), preserved,
                         "the collision overwrote the preserved bytes")

    def test_POSITIVE_CONTROL_the_colliding_log_imports_fine_under_its_own_name(self):
        # Without this, the collision test would also pass if the second log were simply bad.
        code, out = self.import_text(BASE_TEXT)
        self.assertEqual(code, OK, out)
        other = BASE_TEXT.replace("3fca3b003a7f8db84f343512ea9835fa", OTHER_ID)
        code, out = self.run_import(self.write_log(other, "OTHER_2026-08-31.log"))
        self.assertEqual(code, OK, out)
        self.assertIn("OTHER_2026-08-31.log", self.evidence_files())
        self.assertEqual(len(self.evidence_files()), 4)

    def test_the_generated_record_never_takes_the_hand_written_RUN_RECORD_name(self):
        code, out = self.import_text(BASE_TEXT)
        self.assertEqual(code, OK, out)
        self.assertNotIn("RUN_RECORD.md", self.evidence_files(),
                         "the importer must not be able to clobber the hand-written record")
        self.assertIn("TEST_RUN_2026-08-30.RUN_RECORD.md", self.evidence_files())


# -------------------------------------------------------------------------------- provenance -
class TestProvenanceIsReportedHonestly(ImporterHarness):

    def bundle(self, path, mapping):
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"files": mapping}, handle)
        return path

    def real_hashes(self):
        out = {}
        for name in ("main.py", "br_machine.py", "synthetic_bars.py"):
            out[name] = hashlib.sha256(read_bytes(os.path.join(PKG, name))).hexdigest()
        return out

    def test_without_a_bundle_the_cloud_source_is_marked_OPERATOR_REPORTED(self):
        code, out = self.import_text(BASE_TEXT)
        self.assertEqual(code, OK, out)
        record = self.record_text()
        self.assertIn("OPERATOR-REPORTED, NOT VERIFIED", record)
        self.assertIn("NOT downloaded", record)
        self.assertIn("NOT hash-compared", record)
        self.assertIn("never inferred from a successful run", record)
        self.assertIn("OPERATOR-REPORTED, not verified", out)

    def test_a_bundle_MISMATCH_refuses_the_import(self):
        wrong = self.real_hashes()
        wrong["main.py"] = "0" * 64
        path = self.bundle(os.path.join(self.tmp, "BUNDLE.json"), wrong)
        code, out = self.import_text(BASE_TEXT, "--bundle", path)
        self.assertRefused(code, out, BUNDLE_MISMATCH, "main.py", "0" * 64)
        self.assertEqual(self.evidence_files(), [],
                         "a mismatched bundle must not leave evidence behind")

    def test_a_bundle_naming_a_file_that_is_not_source_is_refused(self):
        rogue = self.real_hashes()
        rogue["notes.txt"] = "1" * 64
        path = self.bundle(os.path.join(self.tmp, "BUNDLE.json"), rogue)
        code, out = self.import_text(BASE_TEXT, "--bundle", path)
        self.assertRefused(code, out, BUNDLE_MISMATCH, "notes.txt")

    def test_a_MATCHING_bundle_still_does_not_prove_what_the_cloud_executed(self):
        # POSITIVE CONTROL for the mismatch test above -- and the substantive claim: a matching
        # local hash narrows provenance, it does not resolve it.
        path = self.bundle(os.path.join(self.tmp, "BUNDLE.json"), self.real_hashes())
        code, out = self.import_text(BASE_TEXT, "--bundle", path)
        self.assertEqual(code, OK, out)
        record = self.record_text()
        self.assertIn("OPERATOR-REPORTED, NOT VERIFIED", record)
        self.assertIn("does NOT prove which source executed", record)
        self.assertIn("QuantConnect", record)
        self.assertIn("never inferred from a successful run", record)
        for name, digest in self.real_hashes().items():
            with self.subTest(file=name):
                self.assertIn(digest, record)
        self.assertNotIn("VERIFIED SOURCE", record.upper().replace("NOT VERIFIED", ""))

    def test_the_record_states_what_the_run_does_NOT_establish(self):
        code, out = self.import_text(BASE_TEXT)
        self.assertEqual(code, OK, out)
        record = self.record_text()
        for claim in ("Historical parity", "profitability", "production readiness",
                      "report a program wrote about itself"):
            with self.subTest(claim=claim):
                self.assertIn(claim, record)

    def test_the_record_says_engine_LEAN_alone_would_not_have_been_enough(self):
        code, out = self.import_text(BASE_TEXT)
        self.assertEqual(code, OK, out)
        record = self.record_text()
        self.assertIn("ALONE is not engine evidence", record)
        self.assertIn(smoke_log.LOCAL_ENGINE, record)


# --------------------------------------------------------------------------- evidence safety -
class TestTheseTestsTouchedNoPreservedEvidence(unittest.TestCase):

    def test_the_preserved_log_is_byte_identical_to_what_was_read_at_import_time(self):
        with open(PRESERVED_LOG, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), BASE_TEXT)

    def test_the_package_evidence_directory_gained_no_file(self):
        # Every write in this module goes to a mkdtemp directory. If a default path leaked
        # through, it would land here.
        present = sorted(os.listdir(os.path.join(PKG, "evidence")))
        self.assertEqual(present, ["CALM_YELLOW_PIG_2026-08-30.log", "RUN_RECORD.md"])


if __name__ == "__main__":
    unittest.main()

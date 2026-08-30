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


class TestTheAdapterSurvivesTheInternalUniverseSymbol(unittest.TestCase):
    """The exact initialization failure observed in the cloud, and its repair.

    OBSERVED, not hypothetical. Project 35863117, run `Hyper Active Red Orange Termite`,
    LEAN 2.5.0.0.18041, died in Initialize with:

        KeyError: 'QC-UNIVERSE-USERDEFINED-USA-BASE'   at GetSource

    `AddData` registers the security AND a user-defined universe, and LEAN copy-constructs the
    universe config from the security's subscription with the universe symbol substituted and
    isInternalFeed:true -- so the universe config carries the SAME custom data type with a
    different Symbol, and GetSource is called with it.

    THESE ARE MOCKED, LOCAL CHECKS. They drive GetSource and Reader directly through the
    module's offline shim. They prove the adapter cannot raise and cannot misroute; they prove
    NOTHING about whether LEAN delivers bars, which only a cloud run can establish.
    """

    UNIVERSE = 'QC-UNIVERSE-USERDEFINED-USA-BASE'

    def setUp(self):
        import importlib
        sys.path.insert(0, PKG)
        self.main = importlib.import_module("main")
        importlib.reload(self.main)

    class _Sym(object):
        def __init__(self, value):
            self.Value = value

    class _Config(object):
        def __init__(self, value):
            self.Symbol = TestTheAdapterSurvivesTheInternalUniverseSymbol._Sym(value)

    def test_GetSource_does_not_raise_on_the_INTERNAL_UNIVERSE_symbol(self):
        # The regression. Before the repair this raised KeyError and killed Initialize.
        for ticker, cls in self.main.CASE_TYPES.items():
            with self.subTest(case=ticker):
                src = cls().GetSource(self._Config(self.UNIVERSE), None, False)
                self.assertIsNotNone(src)
                self.assertIn("gist.githubusercontent.com", src.Source)

    def test_SYNQUAL_serves_the_QUALIFY_fixture(self):
        src = self.main.SyntheticBarQualify().GetSource(self._Config('SYNQUAL'), None, False)
        self.assertTrue(src.Source.endswith("mogo_synthetic_qualify.csv"))

    def test_SYNREJ_serves_the_REJECT_fixture(self):
        src = self.main.SyntheticBarReject().GetSource(self._Config('SYNREJ'), None, False)
        self.assertTrue(src.Source.endswith("mogo_synthetic_reject.csv"))

    def test_each_type_can_only_ever_serve_its_OWN_fixture(self):
        # The property that makes an unknown symbol harmless: there is no lookup to get wrong.
        # Asserted for the universe symbol AND a garbage symbol, per type.
        for ticker, cls in self.main.CASE_TYPES.items():
            expected = cls.URL
            for value in (ticker, self.UNIVERSE, 'NOT-A-CASE', ''):
                with self.subTest(case=ticker, symbol=value):
                    got = cls().GetSource(self._Config(value), None, False).Source
                    self.assertEqual(got, expected,
                                     "%s served a different fixture for %r" % (ticker, value))

    def test_the_two_types_serve_DIFFERENT_fixtures(self):
        # Without this, "each type serves its own" would also hold if both served the same one.
        self.assertNotEqual(self.main.SyntheticBarQualify.URL,
                            self.main.SyntheticBarReject.URL)

    def test_Reader_REFUSES_a_line_whose_symbol_is_not_a_declared_case(self):
        line = '0,1577836800000,99.00000,99.05000,98.95000,99.00000'
        for value in (self.UNIVERSE, 'NOT-A-CASE', ''):
            with self.subTest(symbol=value):
                row = self.main.SyntheticBarQualify().Reader(
                    self._Config(value), line, None, False)
                self.assertIsNone(row, "%r was parsed into a bar" % value)

    def test_POSITIVE_CONTROL_Reader_ACCEPTS_a_declared_case_line(self):
        # Without this the refusal above would also pass if Reader returned None for everything.
        row = self.main.SyntheticBarQualify().Reader(
            self._Config('SYNQUAL'),
            '7,1578441600000,99.28000,99.33000,99.23000,99.28000', None, False)
        self.assertIsNotNone(row)
        self.assertEqual(row['BarIndex'], 7)
        self.assertEqual(row['EpochMs'], 1578441600000)

    def test_the_epoch_is_carried_VERBATIM_not_re_derived_from_a_naive_datetime(self):
        # Adjacent assumption this failure prompted a review of: the previous adapter passed
        # int(row.Time.timestamp() * 1000), and Time is a NAIVE datetime, so timestamp()
        # reinterprets it in the host's LOCAL timezone -- wrong by whole hours off UTC.
        row = self.main.SyntheticBarQualify().Reader(
            self._Config('SYNQUAL'),
            '0,1577836800000,99.00000,99.05000,98.95000,99.00000', None, False)
        self.assertEqual(row['EpochMs'], 1577836800000)
        self.assertNotIn("Time.timestamp()", _read("main.py"))

    def test_header_and_malformed_lines_are_refused_for_a_VALID_symbol(self):
        for line in ('index,timestamp,open,high,low,close', '', '1,2,3'):
            with self.subTest(line=line):
                self.assertIsNone(self.main.SyntheticBarQualify().Reader(
                    self._Config('SYNQUAL'), line, None, False))

    def test_case_state_is_INDEPENDENT_per_case(self):
        a, b = self.main.CaseState(), self.main.CaseState()
        self.assertIsNot(a.machine, b.machine)
        self.assertIsNot(a.delivered, b.delivered)
        self.assertIsNot(a.seen, b.seen)
        a.machine.on_bar(Bar(0, 0, 1.0, 1.1, 0.9, 1.0))
        self.assertEqual(a.machine.bars_seen, 1)
        self.assertEqual(b.machine.bars_seen, 0, "one case advanced the other's machine")

    def test_the_algorithm_counts_unexpected_delivered_symbols_and_fails_on_them(self):
        src = _read("main.py")
        self.assertIn("self.unexpected_symbols += 1", src)
        self.assertIn("no_unexpected_symbols", src,
                      "an unexpected delivery must be a named FAILING check, not a silent skip")


class TestTheReaderToOnDataInterface(unittest.TestCase):
    """The complete Reader -> OnData -> state-machine boundary, audited field by field.

    WHY THIS CLASS EXISTS. Two cloud runs died at this boundary -- first on symbol routing,
    then on field TYPE (`Muscular Red Orange Fly`, algorithm c89520ff9658ee55535bb8c960133ae0:
    `No method matches given arguments for set_item: (<class 'str'>, <class 'int'>)`). Each
    time only one line was wrong, and each time the mock was more permissive than the engine,
    so nothing local objected. These tests pin every assignment on the path, not just the one
    that failed last.

    WHAT THE MOCK CANNOT ESTABLISH -- stated plainly, because a green run here has now twice
    preceded a red run in the cloud:

      * It does not exercise pythonnet. The shim REFUSES int the way LEAN was observed to,
        but that is a model of the engine's behaviour written from LEAN's source, not the
        Python/.NET bridge itself. A type the real bridge rejects for a different reason
        would still pass here.
      * It does not run LEAN's subscription pipeline: no RemoteFile fetch, no universe
        selection, no Slice construction, no timezone or fill-forward handling.
      * `row.Time`/`row.EndTime`/`row.Value`/`row.Symbol` are plain Python attributes here.
        Under LEAN they are typed BaseData members with .NET conversions this mock omits.
      * It cannot establish that any bar is DELIVERED to OnData, which is the entire question
        the cloud run answers.

    Everything below is therefore a NECESSARY condition, never a sufficient one.
    """

    def setUp(self):
        import importlib
        sys.path.insert(0, PKG)
        self.main = importlib.import_module("main")
        importlib.reload(self.main)
        self.cfg = TestTheAdapterSurvivesTheInternalUniverseSymbol._Config('SYNQUAL')
        self.line = '7,1578441600000,99.28000,99.33000,99.23000,99.28000'
        self.row = self.main.SyntheticBarQualify().Reader(self.cfg, self.line, None, False)

    # ---- concrete construction and symbol -------------------------------------------------
    def test_the_reader_returns_the_CONCRETE_subclass_not_the_base(self):
        self.assertIsInstance(self.row, self.main.SyntheticBarQualify)
        reject = self.main.SyntheticBarReject().Reader(
            TestTheAdapterSurvivesTheInternalUniverseSymbol._Config('SYNREJ'),
            self.line, None, False)
        self.assertIsInstance(reject, self.main.SyntheticBarReject)

    def test_the_symbol_is_carried_from_the_CONFIG_not_invented(self):
        self.assertIs(self.row.Symbol, self.cfg.Symbol)

    # ---- time --------------------------------------------------------------------------
    def test_Time_is_derived_from_the_epoch_and_EndTime_is_one_bar_later(self):
        from datetime import datetime, timedelta
        self.assertEqual(self.row.Time, datetime(1970, 1, 1) + timedelta(milliseconds=1578441600000))
        self.assertEqual(self.row.EndTime - self.row.Time, timedelta(days=1))
        self.assertGreater(self.row.EndTime, self.row.Time)

    def test_the_epoch_is_NOT_re_derived_from_the_naive_datetime_anywhere(self):
        # row.Time is naive, so .timestamp() would reinterpret it in the host's LOCAL zone.
        self.assertNotIn("Time.timestamp()", _read("main.py"))

    # ---- field TYPES: the failure that killed the second run ------------------------------
    def test_EVERY_custom_field_is_stored_as_a_float(self):
        # The regression. LEAN's PythonData indexer converts double -> decimal and has no
        # binding for a Python int, so an int assignment raises on the FIRST row.
        for key in ('BarIndex', 'EpochMs', 'Open', 'High', 'Low', 'Close'):
            with self.subTest(field=key):
                value = self.row[key]
                self.assertIsInstance(value, float)
                self.assertNotIsInstance(value, bool)

    def test_the_shim_REFUSES_an_int_exactly_as_the_engine_did(self):
        # Without this the mock would be more permissive than LEAN and would have stayed
        # green through the observed failure -- which is precisely what happened.
        row = self.main.SyntheticBarQualify()
        with self.assertRaises(TypeError):
            row['BarIndex'] = 7
        with self.assertRaises(TypeError):
            row['Flag'] = True            # bool is an int subclass and must not slip through
        row['BarIndex'] = 7.0             # positive control: float is accepted
        self.assertEqual(row['BarIndex'], 7.0)

    # ---- exactness -----------------------------------------------------------------------
    def test_the_index_and_epoch_round_trip_EXACTLY_through_float(self):
        self.assertEqual(int(self.row['BarIndex']), 7)
        self.assertEqual(int(self.row['EpochMs']), 1578441600000)

    def test_every_bar_of_both_fixtures_round_trips_exactly(self):
        # Asserted over the whole corpus, not one row: float64 is exact to 2**53 and a ms
        # epoch is ~1.58e12, but that is a claim worth checking rather than reciting.
        for case in sb.CASES:
            with self.subTest(case=case):
                for index, ms, o, h, l, c in sb.series(case):
                    self.assertEqual(int(float(index)), index)
                    self.assertEqual(int(float(ms)), ms)

    def test_a_value_that_would_NOT_round_trip_is_REFUSED_not_stored_lossy(self):
        lossy = '%d,1578441600000,1,1,1,1' % (2 ** 53 + 1)
        with self.assertRaises(ValueError):
            self.main.SyntheticBarQualify().Reader(self.cfg, lossy, None, False)

    # ---- OHLC and Value ------------------------------------------------------------------
    def test_the_OHLC_fields_carry_the_parsed_prices(self):
        self.assertEqual((self.row['Open'], self.row['High'],
                          self.row['Low'], self.row['Close']),
                         (99.28, 99.33, 99.23, 99.28))

    def test_Value_is_the_close_as_a_float(self):
        self.assertIsInstance(self.row.Value, float)
        self.assertEqual(self.row.Value, 99.28)

    # ---- conversion into the UNCHANGED state machine --------------------------------------
    def test_the_row_converts_into_a_Bar_the_machine_accepts(self):
        bar = Bar(int(self.row['BarIndex']), int(self.row['EpochMs']),
                  float(self.row['Open']), float(self.row['High']),
                  float(self.row['Low']), float(self.row['Close']))
        self.assertEqual(bar.index, 7)
        machine = BreakRetestMachine(CONFIG, sb.ZONE_LOW, sb.ZONE_HIGH, sb.ZONE_ROLE,
                                     sb.ZONE_FROM_INDEX)
        machine.on_bar(bar)
        self.assertEqual(machine.bars_seen, 1)

    def test_a_full_fixture_replayed_THROUGH_the_reader_reproduces_the_expected_verdict(self):
        # End to end across the adapter: CSV text -> Reader -> Bar -> machine, for both cases.
        # This is the strongest local statement available, and it still does not involve LEAN.
        for case, want_state, want_decision in (('qualify', S_LOCKED, True),
                                                ('reject', S_BROKEN, False)):
            with self.subTest(case=case):
                ticker = 'SYNQUAL' if case == 'qualify' else 'SYNREJ'
                cls = self.main.CASE_TYPES[ticker]
                cfg = TestTheAdapterSurvivesTheInternalUniverseSymbol._Config(ticker)
                machine = BreakRetestMachine(CONFIG, sb.ZONE_LOW, sb.ZONE_HIGH, sb.ZONE_ROLE,
                                             sb.ZONE_FROM_INDEX)
                delivered = 0
                for line in sb.csv_text(case).strip().split('\n'):
                    row = cls().Reader(cfg, line, None, False)
                    if row is None:
                        continue
                    delivered += 1
                    machine.on_bar(Bar(int(row['BarIndex']), int(row['EpochMs']),
                                       float(row['Open']), float(row['High']),
                                       float(row['Low']), float(row['Close'])))
                self.assertEqual(delivered, 120, 'the header must be the only refused line')
                self.assertEqual(machine.state, want_state)
                self.assertEqual(bool(machine.decision), want_decision)

    def test_the_algorithm_still_declares_both_global_checks(self):
        src = _read("main.py")
        self.assertIn("no_unexpected_symbols", src)
        self.assertIn("case_state_isolated", src)


class TestThePreservedEngineRunEvidence(unittest.TestCase):
    """The preserved cloud log must stay intact and keep agreeing with the committed algorithm.

    This is evidence ABOUT a run, not a re-run: nothing here executes LEAN. It guards the log
    from silent edit and pins the claim the run record makes, so a later change to the
    algorithm's expectations cannot drift away from the evidence that was actually observed.
    """

    EVIDENCE = os.path.join(PKG, "evidence")
    LOG = os.path.join(EVIDENCE, "CALM_YELLOW_PIG_2026-08-30.log")
    LOG_SHA = "83e377e54c5dc93b83416fe023598425d2e431a4c1767a63b329d149c71b1ecd"
    ALGORITHM_ID = "3fca3b003a7f8db84f343512ea9835fa"

    def log(self):
        with open(self.LOG, encoding="utf-8") as handle:
            return handle.read()

    def test_the_log_is_preserved_byte_for_byte(self):
        with open(self.LOG, "rb") as handle:
            self.assertEqual(hashlib.sha256(handle.read()).hexdigest(), self.LOG_SHA)

    def test_the_log_carries_both_platform_records_for_ONE_algorithm(self):
        text = self.log()
        self.assertEqual(len(re.findall(r"Launching analysis", text)), 1)
        self.assertEqual(len(re.findall(r"completed in", text)), 1)
        self.assertEqual(set(re.findall(r"[0-9a-f]{32}", text)), {self.ALGORITHM_ID})
        self.assertIn("v2.5.0.0.18041", text)

    def test_the_log_is_22_checks_all_PASS_with_no_duplicates(self):
        checks = re.findall(r"SMOKE-CHECK (\S+)\s+(\S+)\s+(PASS|FAIL)", self.log())
        self.assertEqual(len(checks), 22)
        self.assertTrue(all(c[2] == "PASS" for c in checks))
        self.assertNotIn("FAIL", self.log())
        for case in ("SYNQUAL", "SYNREJ"):
            names = [c[1] for c in checks if c[0] == case]
            self.assertEqual(len(names), 10)
            self.assertEqual(len(names), len(set(names)), "%s has a duplicate check" % case)

    def test_every_logged_check_name_is_DECLARED_in_the_committed_algorithm(self):
        src = _read("main.py")
        logged = set(re.findall(r"SMOKE-CHECK \S+\s+(\S+)\s+PASS", self.log()))
        declared = set(re.findall(r"\('(\w+)', ", src)) | {"case_state_isolated",
                                                           "no_unexpected_symbols"}
        self.assertTrue(logged <= declared, "log reports checks the algorithm does not declare")

    def test_the_logged_outcomes_still_match_the_committed_expectations(self):
        # If someone changes EXPECT, this fails -- the preserved evidence and the code it
        # describes cannot silently diverge.
        text, src = self.log(), _read("main.py")
        self.assertIn("SMOKE-CASE SYNQUAL PASS bars=120 state=LOCKED decision=True "
                      "locked_at=55 failed=none", text)
        self.assertIn("SMOKE-CASE SYNREJ PASS bars=120 state=BROKEN decision=False "
                      "locked_at=None failed=none", text)
        self.assertIn("'locked_at': 55", src)
        self.assertIn("SMOKE-VERDICT PASS engine=LEAN failed=none", text)

    def test_the_run_record_does_NOT_claim_the_cloud_source_was_hash_verified(self):
        record = open(os.path.join(self.EVIDENCE, "RUN_RECORD.md"), encoding="utf-8").read()
        self.assertIn("INFERRED, not verified", record)
        self.assertIn("NOT downloaded", record)
        self.assertIn("b1d46d3f89429464e6a647b465fd47075e765ebe", record)

    def test_the_run_record_states_what_was_NOT_established(self):
        record = open(os.path.join(self.EVIDENCE, "RUN_RECORD.md"), encoding="utf-8").read()
        for claim in ("Historical Mode B parity", "break-cycle divergences",
                      "profitability", "no orders"):
            with self.subTest(claim=claim):
                self.assertIn(claim, record)


class TestThePackageIsCompleteAndHonestlyLabelled(unittest.TestCase):

    def test_the_manifest_covers_every_file_and_matches(self):
        manifest = {}
        for line in _read("MANIFEST.sha256").splitlines():
            if line.startswith("#") or not line.strip():
                continue
            digest, name = line.split("  ", 1)
            manifest[name] = digest
        # FILES only, and only the reproduction inputs. `evidence/` holds run records whose
        # hashes are recorded in RUN_RECORD.md itself, not here -- a preserved log is evidence
        # ABOUT a run, not an input needed to reproduce one.
        on_disk = {f for f in os.listdir(PKG)
                   if not f.startswith(".")
                   and os.path.isfile(os.path.join(PKG, f))
                   and f not in ("MANIFEST.sha256", "RUN_PROCEDURE.md")}
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

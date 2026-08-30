"""Shared parser for the synthetic Mode B ENGINE SMOKE TEST log.

This module is a LIBRARY. Importing it runs nothing, reads no file, touches no network and
has no side effects; every entry point takes text (or a path handed to it explicitly) and
returns a value.

WHY IT EXISTS. The verdict logic used to live welded into unittest assertions over hard-coded
constants (`LOG`, `LOG_SHA`, `ALGORITHM_ID`), so a NEW log could not be validated without
editing test constants first -- which is exactly backwards: the test would then be pinned to
the artefact it is supposed to judge. The judgement lives here, once, and both the registered
tests and `import_run.py` use it. Do not restate any of it anywhere else.

WHAT IT ESTABLISHES. Only what the log bytes say. A log is a report a program wrote about
itself: this module checks that the report is internally consistent, structurally complete and
consistent with the algorithm that claims to have produced it. It cannot establish that LEAN
ran, that the source in the cloud was the source in this repository, or that any number in the
log is true. `engine=LEAN` is a string the algorithm printed; it is evidence only in company
with the platform's OWN launch and completion records, which the algorithm cannot print.
"""
import ast
import re

#: The check-line "case" the algorithm uses for checks that belong to no single case.
GLOBAL_CASE = "GLOBAL"

_LAUNCH_RE = re.compile(
    r"Launching analysis for ([0-9a-f]{32}) with LEAN Engine v(\S+)")
_COMPLETION_RE = re.compile(
    r"Algorithm Id:\(([0-9a-f]{32})\) completed in ")
_HEX32_RE = re.compile(r"\b[0-9a-f]{32}\b")
_CHECK_RE = re.compile(r"SMOKE-CHECK\s+(\S+)\s+(\S+)\s+(PASS|FAIL)\b\s*(.*?)\s*$")
_CASE_RE = re.compile(
    r"SMOKE-CASE\s+(\S+)\s+(PASS|FAIL)\s+bars=(\S+)\s+state=(\S+)\s+decision=(\S+)"
    r"\s+locked_at=(\S+)\s+failed=(\S+)\s*$")
_VERDICT_RE = re.compile(r"SMOKE-VERDICT\s+(PASS|FAIL)\s+engine=(\S+)\s+failed=(\S+)\s*$")

#: The engine token the algorithm prints when it is NOT running under LEAN. A log carrying it
#: is a local run and can never be engine evidence, however green it is.
LOCAL_ENGINE = "plain-python"
LEAN_ENGINE = "LEAN"


def _split_failed(field):
    """`failed=none` means the empty set; anything else is a comma-separated name list."""
    if field == "none":
        return []
    return [part for part in field.split(",") if part]


class Check(object):
    __slots__ = ("case", "name", "status", "detail", "line_no", "line")

    def __init__(self, case, name, status, detail, line_no, line):
        self.case, self.name, self.status = case, name, status
        self.detail, self.line_no, self.line = detail, line_no, line

    @property
    def passed(self):
        return self.status == "PASS"

    def __repr__(self):
        return "Check(%s, %s, %s)" % (self.case, self.name, self.status)


class Case(object):
    __slots__ = ("case", "status", "bars", "state", "decision", "locked_at",
                 "failed", "line_no", "line")

    def __init__(self, case, status, bars, state, decision, locked_at, failed,
                 line_no, line):
        self.case, self.status, self.bars = case, status, bars
        self.state, self.decision, self.locked_at = state, decision, locked_at
        self.failed, self.line_no, self.line = failed, line_no, line

    @property
    def passed(self):
        return self.status == "PASS"

    def __repr__(self):
        return "Case(%s, %s)" % (self.case, self.status)


class Verdict(object):
    __slots__ = ("status", "engine", "failed", "line_no", "line")

    def __init__(self, status, engine, failed, line_no, line):
        self.status, self.engine, self.failed = status, engine, failed
        self.line_no, self.line = line_no, line

    @property
    def passed(self):
        return self.status == "PASS"

    def __repr__(self):
        return "Verdict(%s, engine=%s)" % (self.status, self.engine)


class Problem(object):
    """One reason a log is not acceptable. `code` is stable; `message` is for humans."""
    __slots__ = ("code", "message")

    def __init__(self, code, message):
        self.code, self.message = code, message

    def __str__(self):
        return "%s: %s" % (self.code, self.message)

    def __repr__(self):
        return "Problem(%r, %r)" % (self.code, self.message)


class DeclaredChecks(object):
    """What the committed algorithm says it will emit. Derived, never hand-listed."""
    __slots__ = ("tickers", "case_checks", "global_checks")

    def __init__(self, tickers, case_checks, global_checks):
        self.tickers = tuple(tickers)
        self.case_checks = tuple(case_checks)
        self.global_checks = tuple(global_checks)

    def __repr__(self):
        return "DeclaredChecks(tickers=%r, case_checks=%d, global_checks=%r)" % (
            self.tickers, len(self.case_checks), self.global_checks)


def declared_checks_from_source(main_src):
    """Derive the expected check structure from the algorithm's OWN source.

    Nothing here is hard-coded: the case tickers come from the `CASE_TICKERS` literal, the
    per-case check names from the elements of the `checks = [...]` list (read over the AST, so
    a name mentioned in a comment or docstring cannot satisfy it), and the global check names
    from the GLOBAL log format strings. If the algorithm gains or loses a check, the expected
    set moves with it and no constant in this repository needs editing.
    """
    tree = ast.parse(main_src)
    tickers, case_checks = (), []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        names = [getattr(t, "id", None) for t in node.targets]
        if "CASE_TICKERS" in names and isinstance(node.value, (ast.Tuple, ast.List)):
            tickers = tuple(el.value for el in node.value.elts
                            if isinstance(el, ast.Constant) and isinstance(el.value, str))
        elif "checks" in names and isinstance(node.value, ast.List):
            for element in node.value.elts:
                if (isinstance(element, ast.Tuple) and element.elts
                        and isinstance(element.elts[0], ast.Constant)
                        and isinstance(element.elts[0].value, str)):
                    case_checks.append(element.elts[0].value)
    globals_ = []
    for name in re.findall(r"SMOKE-CHECK GLOBAL\s+(\w+)", main_src):
        if name not in globals_:
            globals_.append(name)
    return DeclaredChecks(tickers, case_checks, globals_)


#: Cross-checks between a SMOKE-CASE summary line and the detail of its own checks. Each entry
#: maps a check name to (field on the Case, callable extracting the observed value from the
#: check detail). A summary that disagrees with the detail it summarises is a contradiction:
#: exactly the shape of a log that was edited by hand after the fact.
def _first_token(detail):
    parts = detail.split()
    return parts[0] if parts else None


def _second_token(detail):
    parts = detail.split()
    return parts[1] if len(parts) > 1 else None


_CASE_DETAIL_CROSSCHECKS = {
    "delivered_event_count": ("bars", _first_token),
    "terminal_state": ("state", _first_token),
    "decision_presence": ("decision", _second_token),
    "locked_at": ("locked_at", _first_token),
}


class SmokeLogResult(object):
    """The parse of one smoke log, plus every reason it is not acceptable."""

    def __init__(self, text):
        self.text = text
        self.launch_id = None
        self.completion_id = None
        self.lean_version = None
        self.launch_line = None
        self.completion_line = None
        self.checks = []            # list of Check
        self.cases = {}             # ticker -> Case (GLOBAL never appears here)
        self.case_order = []
        self.verdict = None         # Verdict or None
        self.problems = []
        self.algorithm_ids = []

    # -- convenience ---------------------------------------------------------------------
    @property
    def engine(self):
        return self.verdict.engine if self.verdict else None

    @property
    def ok(self):
        return not self.problems

    @property
    def problem_codes(self):
        return set(p.code for p in self.problems)

    @property
    def algorithm_id(self):
        return self.launch_id

    @property
    def failed_checks(self):
        return [c for c in self.checks if not c.passed]

    @property
    def check_tuples(self):
        """(case, name, status) triples, in log order -- the shape callers usually want."""
        return [(c.case, c.name, c.status) for c in self.checks]

    def checks_for(self, case):
        return [c for c in self.checks if c.case == case]

    def _add(self, code, message):
        self.problems.append(Problem(code, message))

    def reasons(self):
        return [str(p) for p in self.problems]


def parse_smoke_log(text, declared=None):
    """Parse and judge a smoke log. Returns a `SmokeLogResult`; never raises on bad input.

    `declared`, when given (a `DeclaredChecks`), additionally requires the log's cases and
    check names to be exactly the ones the committed algorithm declares. Without it the
    expected check names are derived from the log's OWN structure -- the union of the names
    seen across the cases -- so a name missing from one case is still caught, but a name the
    algorithm never declares is not.
    """
    result = SmokeLogResult(text)
    lines = text.splitlines()

    launches, completions = [], []
    for number, line in enumerate(lines, start=1):
        match = _LAUNCH_RE.search(line)
        if match:
            launches.append((number, line, match.group(1), match.group(2)))
        match = _COMPLETION_RE.search(line)
        if match:
            completions.append((number, line, match.group(1)))

        if "SMOKE-CHECK" in line:
            match = _CHECK_RE.search(line)
            if match:
                result.checks.append(Check(match.group(1), match.group(2), match.group(3),
                                           match.group(4), number, line))
            else:
                result._add("malformed_check_line", "line %d is not a parsable check: %r"
                            % (number, line.strip()))
        if "SMOKE-CASE" in line:
            match = _CASE_RE.search(line)
            if match:
                case = Case(match.group(1), match.group(2), match.group(3), match.group(4),
                            match.group(5), match.group(6), _split_failed(match.group(7)),
                            number, line)
                if case.case in result.cases:
                    result._add("duplicate_case_line",
                                "case %s has more than one SMOKE-CASE line" % case.case)
                else:
                    result.cases[case.case] = case
                    result.case_order.append(case.case)
            else:
                result._add("malformed_case_line", "line %d is not a parsable case summary: %r"
                            % (number, line.strip()))
        if "SMOKE-VERDICT" in line:
            match = _VERDICT_RE.search(line)
            if match:
                if result.verdict is not None:
                    result._add("duplicate_verdict", "the log carries more than one verdict")
                else:
                    result.verdict = Verdict(match.group(1), match.group(2),
                                             _split_failed(match.group(3)), number, line)
            else:
                result._add("malformed_verdict_line",
                            "line %d is not a parsable verdict: %r" % (number, line.strip()))

    _identity(result, lines, launches, completions)
    _completeness(result, declared)
    _contradictions(result)
    _truncation(result, text, lines)
    return result


# -- identity -------------------------------------------------------------------------------
def _identity(result, lines, launches, completions):
    if len(launches) != 1:
        result._add("launch_record", "expected exactly 1 platform launch record, found %d"
                    % len(launches))
    if len(completions) != 1:
        result._add("completion_record",
                    "expected exactly 1 platform completion record, found %d"
                    % len(completions))
    if launches:
        result.launch_id, result.lean_version = launches[0][2], launches[0][3]
        result.launch_line = launches[0][1].strip()
    if completions:
        result.completion_id = completions[0][2]
        result.completion_line = completions[0][1].strip()
    if result.launch_id and result.completion_id and result.launch_id != result.completion_id:
        result._add("algorithm_id_mismatch",
                    "launch record names %s but completion record names %s"
                    % (result.launch_id, result.completion_id))

    ids = []
    for line in lines:
        for found in _HEX32_RE.findall(line):
            if found not in ids:
                ids.append(found)
    result.algorithm_ids = ids
    if len(ids) != 1:
        result._add("algorithm_id_count",
                    "expected exactly 1 algorithm id in the whole log, found %d: %s"
                    % (len(ids), ", ".join(ids) or "none"))
    if launches and not result.lean_version:
        result._add("lean_version", "the launch record carries no LEAN version")


# -- completeness ---------------------------------------------------------------------------
def _completeness(result, declared):
    case_names = [c for c in result.case_order]
    check_cases = []
    for check in result.checks:
        if check.case not in check_cases:
            check_cases.append(check.case)
    per_case_check_cases = [c for c in check_cases if c != GLOBAL_CASE]

    if not result.checks:
        result._add("no_checks", "the log carries no SMOKE-CHECK line at all")
    if not case_names:
        result._add("no_case_lines", "the log carries no SMOKE-CASE line at all")
    if result.verdict is None:
        result._add("no_verdict", "the log carries no SMOKE-VERDICT line")

    # Every case that emitted checks must also summarise itself, and vice versa.
    for case in per_case_check_cases:
        if case not in result.cases:
            result._add("missing_case_line",
                        "case %s emitted checks but no SMOKE-CASE line" % case)
    for case in case_names:
        if case not in per_case_check_cases:
            result._add("case_without_checks",
                        "case %s has a SMOKE-CASE line but emitted no check" % case)

    # Expected per-case names: from the algorithm when we have it, else the log's own union.
    if declared is not None:
        expected = list(declared.case_checks)
    else:
        expected = []
        for check in result.checks:
            if check.case != GLOBAL_CASE and check.name not in expected:
                expected.append(check.name)

    for case in per_case_check_cases:
        seen = {}
        for check in result.checks_for(case):
            seen[check.name] = seen.get(check.name, 0) + 1
        for name in expected:
            count = seen.get(name, 0)
            if count == 0:
                result._add("missing_check", "case %s is missing check %s" % (case, name))
            elif count > 1:
                result._add("duplicate_check",
                            "case %s reports check %s %d times" % (case, name, count))
        for name in seen:
            if name not in expected:
                result._add("undeclared_check",
                            "case %s reports check %s, which is not expected" % (case, name))

    if declared is not None:
        expected_global = list(declared.global_checks)
        seen_global = {}
        for check in result.checks_for(GLOBAL_CASE):
            seen_global[check.name] = seen_global.get(check.name, 0) + 1
        for name in expected_global:
            count = seen_global.get(name, 0)
            if count == 0:
                result._add("missing_check", "the GLOBAL checks are missing %s" % name)
            elif count > 1:
                result._add("duplicate_check",
                            "the GLOBAL check %s is reported %d times" % (name, count))
        for name in seen_global:
            if name not in expected_global:
                result._add("undeclared_check",
                            "GLOBAL reports check %s, which the algorithm does not declare"
                            % name)
        for case in per_case_check_cases:
            if case not in declared.tickers:
                result._add("undeclared_case",
                            "the log reports case %s, which the algorithm does not declare"
                            % case)
        for ticker in declared.tickers:
            if ticker not in result.cases:
                result._add("missing_case",
                            "the algorithm declares case %s, which the log does not report"
                            % ticker)
    else:
        # Without the algorithm we can still require the cases to agree with each other.
        for case in per_case_check_cases:
            names = set(c.name for c in result.checks_for(case))
            if names != set(expected):
                missing = sorted(set(expected) - names)
                if missing:
                    result._add("missing_check",
                                "case %s is missing %s" % (case, ", ".join(missing)))


# -- contradictions -------------------------------------------------------------------------
def _contradictions(result):
    for check in result.checks:
        if not check.passed:
            result._add("check_failed", "%s/%s FAILED: %s"
                        % (check.case, check.name, check.detail or "(no detail)"))

    for case_name in result.case_order:
        case = result.cases[case_name]
        failed_here = [c.name for c in result.checks_for(case_name) if not c.passed]
        if case.passed and failed_here:
            result._add("case_contradiction",
                        "case %s reports PASS while its own checks %s FAILED"
                        % (case_name, ", ".join(failed_here)))
        if not case.passed and not failed_here:
            result._add("case_contradiction",
                        "case %s reports FAIL while every one of its checks PASSED"
                        % case_name)
        if sorted(case.failed) != sorted(failed_here):
            result._add("case_contradiction",
                        "case %s says failed=%s but its failing checks are %s"
                        % (case_name, ",".join(case.failed) or "none",
                           ",".join(failed_here) or "none"))
        # The summary must agree with the detail of the checks it summarises.
        for check in result.checks_for(case_name):
            crosscheck = _CASE_DETAIL_CROSSCHECKS.get(check.name)
            if not crosscheck or not check.passed:
                continue
            field, extract = crosscheck
            observed = extract(check.detail)
            claimed = getattr(case, field)
            if observed is not None and observed != claimed:
                result._add("case_contradiction",
                            "case %s says %s=%s but its %s check reports %s"
                            % (case_name, field, claimed, check.name, observed))

    if result.verdict is not None:
        all_failed = [c.name for c in result.checks if not c.passed]
        if result.verdict.passed and all_failed:
            result._add("verdict_contradiction",
                        "the verdict is PASS while %d check(s) FAILED: %s"
                        % (len(all_failed), ", ".join(all_failed)))
        if not result.verdict.passed and not all_failed:
            result._add("verdict_contradiction",
                        "the verdict is FAIL while every check PASSED")
        if sorted(result.verdict.failed) != sorted(all_failed):
            result._add("verdict_contradiction",
                        "the verdict says failed=%s but the failing checks are %s"
                        % (",".join(result.verdict.failed) or "none",
                           ",".join(all_failed) or "none"))
        case_failures = set()
        for case_name in result.case_order:
            case_failures.update(result.cases[case_name].failed)
        if not case_failures <= set(result.verdict.failed):
            result._add("verdict_contradiction",
                        "a case reports failures the verdict does not carry: %s"
                        % ", ".join(sorted(case_failures - set(result.verdict.failed))))


# -- truncation -----------------------------------------------------------------------------
def _truncation(result, text, lines):
    """A log is truncated when the records that can only appear at the END are absent.

    The verdict is the last thing the algorithm prints and the completion record is the last
    thing the platform prints, so a log missing either -- or carrying them out of order -- was
    cut short, whatever else it contains.
    """
    if not text.strip():
        result._add("truncated_log", "the log is empty")
        return
    if result.verdict is None or not result.completion_id:
        result._add("truncated_log",
                    "the log ends before its %s"
                    % ("verdict and completion record"
                       if result.verdict is None and not result.completion_id
                       else "verdict" if result.verdict is None else "completion record"))
        return
    completion_line_no = None
    for number, line in enumerate(lines, start=1):
        if _COMPLETION_RE.search(line):
            completion_line_no = number
            break
    if completion_line_no is not None and completion_line_no < result.verdict.line_no:
        result._add("truncated_log",
                    "the completion record appears before the verdict, so the log is not whole")


# -- engine evidence --------------------------------------------------------------------------
def engine_evidence(result):
    """Is this log evidence that the ENGINE ran, or only that a program ran?

    Returns (bool, [reasons]). `engine=plain-python` is refused outright: that is the token the
    algorithm prints when `AlgorithmImports` did not import, i.e. a local run. `engine=LEAN` on
    its own is refused too -- it is a string the ALGORITHM printed, and an algorithm can print
    anything. The platform's own launch and completion records are what the algorithm cannot
    fabricate from inside itself, so both are required, naming one and the same algorithm id.
    """
    reasons = []
    engine = result.engine
    if engine is None:
        reasons.append("the log carries no verdict, so it claims no engine at all")
    elif engine == LOCAL_ENGINE:
        reasons.append(
            "engine=%s means AlgorithmImports did not import: this is a LOCAL run and can "
            "never be engine evidence, however many checks pass" % LOCAL_ENGINE)
    elif engine != LEAN_ENGINE:
        reasons.append("engine=%s is not a recognised engine token" % engine)

    if not result.launch_id:
        reasons.append("engine=LEAN is a string the algorithm printed; the platform's own "
                       "'Launching analysis' record is absent, so nothing corroborates it")
    if not result.completion_id:
        reasons.append("engine=LEAN is a string the algorithm printed; the platform's own "
                       "completion record is absent, so nothing corroborates it")
    if (result.launch_id and result.completion_id
            and result.launch_id != result.completion_id):
        reasons.append("the launch and completion records name different algorithms")
    return (not reasons), reasons

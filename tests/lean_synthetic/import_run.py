#!/usr/bin/env python3
"""Import ONE engine smoke-test log as preserved evidence, or refuse it and say why.

    python3 tests/lean_synthetic/import_run.py <log-path> [options]

WHAT IT DOES. Parses the log with the shared parser (`smoke_log.py` -- the ONLY place the
verdict logic lives), refuses it unless every identity, completeness and consistency property
holds, refuses it as ENGINE evidence unless the platform's own records corroborate the
algorithm's `engine=` claim, copies the bytes VERBATIM into the evidence directory, and writes
a run record whose every identifier comes from the parse rather than from a human retyping it.

WHAT IT REFUSES TO DO. It never overwrites an existing evidence file with different bytes; a
name collision is a hard failure, because silently replacing preserved evidence is the one
mistake that cannot be undone. Re-importing the identical log is a no-op that succeeds.

WHAT IT CANNOT ESTABLISH. That the source which executed in the cloud is the source in this
repository. A run that behaves exactly as the local code predicts is corroboration, not
identity: nothing observable in a log is a hash of the uploaded file. `--bundle` narrows this
only to "the local files match the hashes someone recorded for them", which still does not say
what QuantConnect executed. The run record is required to say so in those words.

Exit codes: 0 imported (or already present, unchanged); 2 the log is not acceptable;
3 the log is not engine evidence; 4 evidence-name collision; 5 source-bundle mismatch;
6 usage or I/O error.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import smoke_log                                                      # noqa: E402

EXIT_OK = 0
EXIT_LOG_REJECTED = 2
EXIT_NOT_ENGINE_EVIDENCE = 3
EXIT_COLLISION = 4
EXIT_BUNDLE_MISMATCH = 5
EXIT_USAGE = 6

#: Files a bundle is allowed to pin: the algorithm and the modules it carries with it. A bundle
#: naming anything else is a mistake worth failing on rather than quietly ignoring.
BUNDLE_ALLOWED = ("main.py", "br_machine.py", "synthetic_bars.py")

#: The hand-written record that predates this tool. Never a target: generated records are
#: always named for the run they describe.
RESERVED_RECORD_NAMES = ("RUN_RECORD.md",)

_NAME_DATE_RE = re.compile(r"^(?P<name>.+?)_(?P<date>\d{4}-\d{2}-\d{2})$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def normalise_name(raw):
    """`Calm Yellow Pig` -> `CALM_YELLOW_PIG`. Deterministic, and rejects an empty result."""
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", raw).strip("_").upper()
    return cleaned


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    with open(path, "rb") as handle:
        return sha256_bytes(handle.read())


class Refusal(Exception):
    def __init__(self, code, reasons):
        Exception.__init__(self, "; ".join(reasons))
        self.code = code
        self.reasons = list(reasons)


def derive_name_and_date(log_path, name_arg, date_arg):
    stem = os.path.basename(log_path)
    if stem.lower().endswith(".log"):
        stem = stem[:-4]
    match = _NAME_DATE_RE.match(stem)
    derived_name = match.group("name") if match else stem
    derived_date = match.group("date") if match else None

    name = normalise_name(name_arg if name_arg else derived_name)
    if not name:
        raise Refusal(EXIT_USAGE, ["no usable backtest name: pass --name"])

    date = date_arg or derived_date
    if not date:
        raise Refusal(EXIT_USAGE, [
            "no observation date could be derived from %r and none was given: pass "
            "--date YYYY-MM-DD (the log's own timestamps are SIMULATION times, not the date "
            "the run was observed, so they must not be used for this)" % os.path.basename(log_path)])
    if not _DATE_RE.match(date):
        raise Refusal(EXIT_USAGE, ["--date must be YYYY-MM-DD, got %r" % date])
    try:
        datetime.date(*[int(part) for part in date.split("-")])
    except ValueError:
        raise Refusal(EXIT_USAGE, ["--date %r is not a real date" % date])
    return name, date


def load_declared(package_dir):
    main_path = os.path.join(package_dir, "main.py")
    try:
        with open(main_path, encoding="utf-8") as handle:
            source = handle.read()
    except IOError as error:
        raise Refusal(EXIT_USAGE, ["cannot read the committed algorithm %s: %s"
                                   % (main_path, error)])
    declared = smoke_log.declared_checks_from_source(source)
    if not declared.tickers or not declared.case_checks:
        raise Refusal(EXIT_USAGE, [
            "no checks could be derived from %s, so completeness cannot be judged" % main_path])
    return declared


def compare_bundle(bundle_path, package_dir):
    """Compare a supplied hash bundle against the LOCAL files. Returns a report dict.

    A match means the local files are the ones the bundle names. It does NOT mean those files
    are what QuantConnect executed, and the record must not say otherwise.
    """
    try:
        with open(bundle_path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (IOError, ValueError) as error:
        raise Refusal(EXIT_USAGE, ["cannot read --bundle %s: %s" % (bundle_path, error)])

    files = data.get("files", data) if isinstance(data, dict) else None
    if not isinstance(files, dict) or not files:
        raise Refusal(EXIT_USAGE, [
            "--bundle must be a JSON object of {filename: sha256} or {\"files\": {...}}"])

    rows, mismatches = [], []
    for name in sorted(files):
        expected = files[name]
        if name not in BUNDLE_ALLOWED:
            mismatches.append("the bundle pins %s, which is not part of the uploaded source "
                              "(%s)" % (name, ", ".join(BUNDLE_ALLOWED)))
            rows.append((name, str(expected), "NOT-A-SOURCE-FILE", False))
            continue
        local_path = os.path.join(package_dir, name)
        if not os.path.isfile(local_path):
            mismatches.append("the bundle pins %s, which is not present in %s"
                              % (name, package_dir))
            rows.append((name, str(expected), "MISSING", False))
            continue
        actual = sha256_file(local_path)
        agree = (str(expected).lower() == actual)
        rows.append((name, str(expected).lower(), actual, agree))
        if not agree:
            mismatches.append("%s: bundle says %s, local file is %s"
                              % (name, expected, actual))
    if mismatches:
        raise Refusal(EXIT_BUNDLE_MISMATCH, mismatches)
    return {"path": os.path.abspath(bundle_path), "rows": rows,
            "revision": data.get("revision") if isinstance(data, dict) else None}


def render_record(result, meta, bundle):
    """Build the run record. EVERY identifier is read off the parse -- none is retyped."""
    cases = [result.cases[name] for name in result.case_order]
    total = len(result.checks)
    passed = len([c for c in result.checks if c.passed])

    lines = []
    add = lines.append
    add("# LEAN runtime evidence record — %s" % meta["name"])
    add("")
    add("**Status: OBSERVED.** Generated by `tests/lean_synthetic/import_run.py` from the")
    add("preserved log bytes. Every identifier below was taken from the parse of those bytes,")
    add("never hand-transcribed. Regenerating it from the same log reproduces this file exactly.")
    add("")
    add("## 1. The run")
    add("")
    add("| Field | Value |")
    add("|---|---|")
    add("| Backtest name | `%s` |" % meta["name"])
    add("| Algorithm ID | `%s` |" % result.algorithm_id)
    add("| LEAN version | `v%s` |" % result.lean_version)
    add("| Date observed | %s |" % meta["date"])
    add("| Log | `%s` (%d bytes, %d lines) |"
        % (meta["log_name"], meta["byte_count"], meta["line_count"]))
    add("| Log SHA-256 | `%s` |" % meta["sha256"])
    add("")
    add("Platform launch record, verbatim:")
    add("")
    add("    %s" % result.launch_line)
    add("")
    add("Platform completion record, verbatim:")
    add("")
    add("    %s" % result.completion_line)
    add("")
    add("## 2. Result")
    add("")
    add("**%d/%d checks PASS.** Verdict line, verbatim:" % (passed, total))
    add("")
    add("    %s" % result.verdict.line.strip())
    add("")
    add("| Case | bars | state | decision | locked_at | result |")
    add("|---|---|---|---|---|---|")
    for case in cases:
        add("| %s | %s | %s | %s | %s | %s |"
            % (case.case, case.bars, case.state, case.decision, case.locked_at, case.status))
    add("")
    add("Checks by case: %s." % ", ".join(
        "%s %d" % (case, len(result.checks_for(case)))
        for case in sorted(set(c.case for c in result.checks))))
    add("")
    add("The import refused unless: exactly one platform launch record and one completion")
    add("record naming the SAME algorithm id; exactly one algorithm id in the whole log; every")
    add("check the committed algorithm declares present EXACTLY ONCE per case; no FAIL; no case")
    add("or verdict contradicting the checks it summarises; and the log not truncated.")
    add("")
    add("## 3. Engine evidence")
    add("")
    add("The algorithm printed `engine=%s`. That string ALONE is not engine evidence — the"
        % result.engine)
    add("algorithm prints it about itself and could print anything. It is accepted here only")
    add("because the platform's own launch and completion records are present and name the same")
    add("algorithm id `%s`, which the algorithm cannot emit from inside itself."
        % result.algorithm_id)
    add("")
    add("A log carrying `engine=%s` is REFUSED outright by this importer: that token means"
        % smoke_log.LOCAL_ENGINE)
    add("`AlgorithmImports` did not import, i.e. a local run.")
    add("")
    add("## 4. Provenance of the executed source")
    add("")
    if bundle is None:
        add("**OPERATOR-REPORTED, NOT VERIFIED.** The executed source was")
        add("NOT downloaded from QuantConnect and NOT hash-compared against this repository.")
        add("No `--bundle` was supplied, so nothing here narrows it at all. Whatever procedure")
        add("the operator reports for the upload is a report, not a measurement.")
    else:
        add("**OPERATOR-REPORTED, NOT VERIFIED — narrowed, not resolved, by a local bundle.**")
        add("A hash bundle was supplied and every hash in it matches the corresponding LOCAL")
        add("file:")
        add("")
        add("| File | Bundle SHA-256 | Local SHA-256 | Agree |")
        add("|---|---|---|---|")
        for name, expected, actual, agree in bundle["rows"]:
            add("| `%s` | `%s` | `%s` | %s |" % (name, expected, actual,
                                                 "yes" if agree else "NO"))
        add("")
        add("Bundle: `%s`." % os.path.basename(bundle["path"]))
        if bundle["revision"]:
            add("Bundle revision as recorded: `%s`." % bundle["revision"])
        add("")
        add("**A matching local bundle hash does NOT prove which source executed in")
        add("QuantConnect.** It establishes only that these local files are the files the bundle")
        add("names. The cloud-side source was still not retrieved and still not hashed.")
    add("")
    add("**Upload identity is never inferred from a successful run.** Behaviour matching the")
    add("local code is corroboration, not identity: a different source that happens to behave")
    add("the same way produces the same log. Treat cloud-side source identity as UNKNOWN unless")
    add("the executed file is retrieved and hashed.")
    add("")
    add("## 5. What this record does NOT establish")
    add("")
    add("Historical parity. Any statement about preserved forward cases. Order execution,")
    add("profitability or production readiness. That any number in the log is TRUE — a log is a")
    add("report a program wrote about itself, and this import checks that the report is")
    add("internally consistent and structurally complete, nothing more.")
    add("")
    return "\n".join(lines)


def import_run(log_path, evidence_dir, package_dir, name_arg=None, date_arg=None,
               bundle_path=None, dry_run=False):
    """Do the whole import. Returns a dict describing what happened; raises Refusal otherwise."""
    if not os.path.isfile(log_path):
        raise Refusal(EXIT_USAGE, ["no such log: %s" % log_path])
    with open(log_path, "rb") as handle:
        raw = handle.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise Refusal(EXIT_LOG_REJECTED, ["the log is not valid UTF-8: %s" % error])

    declared = load_declared(package_dir)
    result = smoke_log.parse_smoke_log(text, declared=declared)
    if result.problems:
        raise Refusal(EXIT_LOG_REJECTED, result.reasons())

    is_engine, why_not = smoke_log.engine_evidence(result)
    if not is_engine:
        raise Refusal(EXIT_NOT_ENGINE_EVIDENCE, why_not)

    bundle = compare_bundle(bundle_path, package_dir) if bundle_path else None

    name, date = derive_name_and_date(log_path, name_arg, date_arg)
    log_name = "%s_%s.log" % (name, date)
    record_name = "%s_%s.RUN_RECORD.md" % (name, date)
    if record_name in RESERVED_RECORD_NAMES or log_name in RESERVED_RECORD_NAMES:
        raise Refusal(EXIT_USAGE, ["%s is a reserved name" % record_name])

    target_log = os.path.join(evidence_dir, log_name)
    target_record = os.path.join(evidence_dir, record_name)
    digest = sha256_bytes(raw)

    log_state = "created"
    if os.path.exists(target_log):
        with open(target_log, "rb") as handle:
            existing = handle.read()
        if existing != raw:
            raise Refusal(EXIT_COLLISION, [
                "%s already exists with DIFFERENT bytes (preserved sha256 %s, incoming %s): "
                "preserved evidence is never overwritten -- import under a different --name or "
                "--date, or establish which log is authentic first"
                % (target_log, sha256_bytes(existing), digest)])
        log_state = "unchanged"

    meta = {"name": name, "date": date, "log_name": log_name, "sha256": digest,
            "byte_count": len(raw), "line_count": len(text.splitlines())}
    record_text = render_record(result, meta, bundle)

    record_state = "created"
    if os.path.exists(target_record):
        with open(target_record, encoding="utf-8") as handle:
            record_state = "unchanged" if handle.read() == record_text else "updated"

    if not dry_run:
        if not os.path.isdir(evidence_dir):
            os.makedirs(evidence_dir)
        if log_state == "created":
            with open(target_log, "wb") as handle:
                handle.write(raw)
            written = sha256_file(target_log)
            if written != digest:
                raise Refusal(EXIT_COLLISION, [
                    "the preserved copy does not re-derive its hash (%s vs %s)"
                    % (written, digest)])
        if record_state != "unchanged":
            with open(target_record, "w", encoding="utf-8") as handle:
                handle.write(record_text)

    return {"log": target_log, "record": target_record, "sha256": digest,
            "log_state": log_state, "record_state": record_state, "result": result,
            "name": name, "date": date, "bundle": bundle, "dry_run": dry_run}


def build_parser():
    parser = argparse.ArgumentParser(
        prog="import_run.py",
        description="Validate and preserve one engine smoke-test log as evidence.")
    parser.add_argument("log", help="path to the raw log to import")
    parser.add_argument("--name", help="backtest name (default: derived from the filename)")
    parser.add_argument("--date", help="observation date YYYY-MM-DD (default: from the filename)")
    parser.add_argument("--evidence-dir", default=os.path.join(HERE, "evidence"),
                        help="where preserved evidence lives (default: %(default)s)")
    parser.add_argument("--package-dir", default=HERE,
                        help="package holding the committed algorithm (default: %(default)s)")
    parser.add_argument("--bundle", help="JSON {filename: sha256} to compare against the LOCAL "
                                         "source files; a match still does not prove what "
                                         "QuantConnect executed")
    parser.add_argument("--dry-run", action="store_true",
                        help="validate and report, write nothing")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        outcome = import_run(args.log, args.evidence_dir, args.package_dir,
                             name_arg=args.name, date_arg=args.date,
                             bundle_path=args.bundle, dry_run=args.dry_run)
    except Refusal as refusal:
        sys.stdout.write("IMPORT REFUSED (%d reason%s)\n"
                         % (len(refusal.reasons), "" if len(refusal.reasons) == 1 else "s"))
        for reason in refusal.reasons:
            sys.stdout.write("  - %s\n" % reason)
        return refusal.code

    result = outcome["result"]
    passed = len([c for c in result.checks if c.passed])
    sys.stdout.write("IMPORT OK%s\n" % (" (dry run, nothing written)"
                                        if outcome["dry_run"] else ""))
    sys.stdout.write("  name          : %s\n" % outcome["name"])
    sys.stdout.write("  date          : %s\n" % outcome["date"])
    sys.stdout.write("  algorithm id  : %s\n" % result.algorithm_id)
    sys.stdout.write("  LEAN version  : v%s\n" % result.lean_version)
    sys.stdout.write("  checks        : %d/%d PASS across %d case(s)\n"
                     % (passed, len(result.checks), len(result.cases)))
    sys.stdout.write("  engine        : %s (corroborated by the platform launch and "
                     "completion records)\n" % result.engine)
    sys.stdout.write("  log           : %s [%s]\n" % (outcome["log"], outcome["log_state"]))
    sys.stdout.write("  sha256        : %s\n" % outcome["sha256"])
    sys.stdout.write("  record        : %s [%s]\n"
                     % (outcome["record"], outcome["record_state"]))
    sys.stdout.write("  provenance    : cloud-side source identity is %s\n"
                     % ("OPERATOR-REPORTED, not verified" if outcome["bundle"] is None else
                        "OPERATOR-REPORTED, not verified; local bundle hashes match but do "
                        "not prove what QuantConnect executed"))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())

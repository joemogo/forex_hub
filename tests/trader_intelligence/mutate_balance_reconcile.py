#!/usr/bin/env python3
"""Can the balance-reconciliation fixtures still DETECT a broken gate or a broken importer?

A DEDICATED GATE, not a registered suite. The filename deliberately does NOT start with
`test_`, so it adds nothing to `expected_python_test_counts.tsv`. Same design as
mutate_platform_health.py, whose docstring records why each guard exists:

  * every mutation goes to a FRESH mirrored temporary tree, so the test modules' own
    REPO_ROOT resolves inside it, and a provenance probe proves the MUTATED modules loaded;
  * an anchor must match exactly once, or the mutation is NOT APPLIED / AMBIGUOUS, never
    silently skipped;
  * a mutant that does not compile, or that changes the collected count, is a setup failure
    and never a kill;
  * a kill counts only if the NAMED discriminator failed;
  * guarded repository files are hashed before and after, and must not move.

The corpus is never copied: the focused tests are hermetic, so no corpus behaviour can
influence a verdict.

Run directly:  python3 tests/trader_intelligence/mutate_balance_reconcile.py
Self-test:     python3 tests/trader_intelligence/mutate_balance_reconcile.py --self-test
"""
import hashlib
import json
import os
import py_compile
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.realpath(os.path.join(HERE, "..", ".."))

MODULE_REL = os.path.join("scripts", "trader_intelligence")
BR_REL = os.path.join(MODULE_REL, "balance_reconcile.py")
IMP_REL = os.path.join(MODULE_REL, "import_mogo_observations.py")
TESTS = (os.path.join("tests", "trader_intelligence", "test_balance_reconcile.py"),
         os.path.join("tests", "trader_intelligence", "test_import_mogo_observations.py"))

FOCUSED = ("tests.trader_intelligence.test_balance_reconcile",
           "tests.trader_intelligence.test_import_mogo_observations"
           ".TestTheImporterRecordsWhatClosedAtMeans")
EXPECTED_FOCUSED_TESTS = 25

GUARDED = (BR_REL, IMP_REL) + TESTS + (
    "index.html", os.path.join("tests", "expected_python_test_counts.tsv"))

M = dict
MUTATIONS = (
    M(mid="B1", target=BR_REL, desc="discard the capturedAt upper bound",
      anchor="    return closed, captured\n", replacement="    return closed, closed\n",
      discriminator="test_positive_control_the_real_catch_up_reconciles"),
    M(mid="B2", target=BR_REL, desc="treat capture time as the EXACT processing instant",
      anchor="    return closed, captured\n", replacement="    return captured, captured\n",
      discriminator="test_the_catch_up_pair_is_ambiguous_in_both_directions"),
    M(mid="B3", target=BR_REL, desc="count every ambiguous contributor as definite",
      anchor="                ambiguous.append(other)\n",
      replacement="                definite.append(other)\n",
      discriminator="test_positive_control_the_real_catch_up_reconciles"),
    M(mid="B4", target=BR_REL, desc="drop every ambiguous contributor",
      anchor="                ambiguous.append(other)\n", replacement="                pass\n",
      discriminator="test_positive_control_the_real_catch_up_reconciles"),
    M(mid="B5", target=BR_REL, desc="subset search accepts any residual",
      anchor="            if abs(residual - base - sum(subset)) <= tolerance:\n",
      replacement="            if True:\n",
      discriminator="test_a_missing_close_inside_a_long_trade_is_caught"),
    M(mid="B6", target=BR_REL, desc="bounded basis without capturedAt silently becomes exact",
      anchor="    if not record.get(\"capturedAt\"):\n        raise",
      replacement="    if not record.get(\"capturedAt\"):\n        return closed, closed\n        raise",
      discriminator="test_a_bounded_basis_without_capturedAt_is_refused"),
    M(mid="B7", target=BR_REL, desc="unrecognised basis accepted",
      anchor="    if basis != BOUNDED_BASIS:\n", replacement="    if False:\n",
      discriminator="test_an_unrecognised_basis_is_refused"),
    M(mid="B8", target=BR_REL, desc="remove the ambiguity cap (fail-closed)",
      anchor="        if len(ambiguous) > max_ambiguous:\n", replacement="        if False:\n",
      discriminator="test_too_many_ambiguous_contributors_fail_closed"),
    M(mid="B9", target=BR_REL, desc="compare timestamps as text",
      anchor="    return datetime.datetime.fromisoformat(value.replace(\"Z\", \"+00:00\"))\n",
      replacement="    return value\n",
      discriminator="test_timestamps_are_compared_as_instants_not_text"),
    M(mid="B10", target=BR_REL, desc="drop the per-term rounding tolerance",
      anchor="        tolerance = 0.005 * (n_definite + k + 2)\n",
      replacement="        tolerance = 0.0\n",
      discriminator="test_positive_control_the_real_catch_up_reconciles"),
    M(mid="B11", target=BR_REL, desc="stop skipping records opened before the first close",
      anchor="        if _instant(record[\"openedAt\"]) < earliest_close:\n            continue\n",
      replacement="",
      discriminator="test_positive_control_the_real_catch_up_reconciles"),
    M(mid="I1", target=IMP_REL, desc="importer drops the closedAt basis",
      anchor="        closedAtBasis=outcome.get(\"exitTimestampBasis\"),\n",
      replacement="        closedAtBasis=None,\n",
      discriminator="test_the_basis_is_copied_from_the_package"),
    M(mid="I2", target=IMP_REL, desc="importer mints capturedAt from the exit, not the capture",
      anchor="        capturedAt=package.get(\"createdAt\"),\n",
      replacement="        capturedAt=outcome.get(\"exitTimestamp\"),\n",
      discriminator="test_capturedAt_is_the_package_capture_time_not_the_exit"),
    M(mid="I3", target=IMP_REL, desc="importer DEFAULTS a missing basis",
      anchor="        closedAtBasis=outcome.get(\"exitTimestampBasis\"),\n",
      replacement="        closedAtBasis=outcome.get(\"exitTimestampBasis\") or \"exit_detected_at\",\n",
      discriminator="test_a_package_without_a_basis_gets_none_rather_than_a_default"),
)


def _sha256(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def guarded_hashes():
    return {rel: _sha256(os.path.join(REPO_ROOT, rel)) for rel in GUARDED}


def build_root(parent):
    root = os.path.join(parent, "root")
    dst_mod = os.path.join(root, MODULE_REL)
    os.makedirs(dst_mod)
    for name in os.listdir(os.path.join(REPO_ROOT, MODULE_REL)):
        if name.endswith(".py"):
            shutil.copy2(os.path.join(REPO_ROOT, MODULE_REL, name), os.path.join(dst_mod, name))
    for rel in TESTS:
        os.makedirs(os.path.dirname(os.path.join(root, rel)), exist_ok=True)
        shutil.copy2(os.path.join(REPO_ROOT, rel), os.path.join(root, rel))
    return root


_PROBE = r"""
import json, os, sys
real = os.path.realpath(%r)
import tests.trader_intelligence.test_balance_reconcile as a
import tests.trader_intelligence.test_import_mogo_observations as b
leaked = sorted(n for n, m in list(sys.modules.items())
                if getattr(m, "__file__", None)
                and os.path.realpath(m.__file__).startswith(real + os.sep))
print(json.dumps({"br": os.path.realpath(a.br.__file__),
                  "imp": os.path.realpath(b.imp.__file__), "leaked": leaked}))
"""


def _env():
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def provenance(root):
    proc = subprocess.run([sys.executable, "-c", _PROBE % REPO_ROOT], cwd=root,
                          capture_output=True, text=True, env=_env())
    if proc.returncode != 0:
        return "LOADER", (proc.stderr.strip().splitlines() or ["?"])[-1][:200]
    info = json.loads(proc.stdout.strip().splitlines()[-1])
    rroot = os.path.realpath(root)
    problems = ["%s loaded from %s" % (k, info[k]) for k in ("br", "imp")
                if not info[k].startswith(rroot + os.sep)]
    if info["leaked"]:
        problems.append("modules imported from the real repository: %s" % info["leaked"])
    return ("PROVENANCE", "; ".join(problems)) if problems else (None, None)


def run_focused(root):
    proc = subprocess.run([sys.executable, "-m", "unittest", "-v"] + list(FOCUSED), cwd=root,
                          capture_output=True, text=True, env=_env())
    out = proc.stdout + proc.stderr
    failures = sorted(set(re.findall(r"^(\w+) \(.*\) \.\.\. (?:FAIL|ERROR)$", out, re.M))
                      | set(re.findall(r"^(?:FAIL|ERROR): (\w+)", out, re.M)))
    match = re.search(r"^Ran (\d+) tests?", out, re.M)
    return proc.returncode, failures, (int(match.group(1)) if match else -1)


def baseline():
    """POSITIVE CONTROL: the UNMUTATED mirror must pass in full. If it does not, every mutation
    would score as a kill against a suite that was already red, and the result means nothing."""
    parent = tempfile.mkdtemp(prefix="mogo-br-base-")
    try:
        root = build_root(parent)
        kind, problem = provenance(root)
        if kind:
            return False, "%s ERROR on the unmutated mirror: %s" % (kind, problem)
        code, failures, collected = run_focused(root)
        if collected != EXPECTED_FOCUSED_TESTS:
            return False, "collected %d tests, expected %d" % (collected, EXPECTED_FOCUSED_TESTS)
        if code != 0:
            return False, "the unmutated suite FAILS: %s" % failures
        return True, "%d/%d pass on the unmutated mirror" % (collected, EXPECTED_FOCUSED_TESTS)
    finally:
        shutil.rmtree(parent, ignore_errors=True)


def evaluate(mutation, expected_count=EXPECTED_FOCUSED_TESTS):
    parent = tempfile.mkdtemp(prefix="mogo-br-mut-%s-" % mutation["mid"])
    try:
        root = build_root(parent)
        target = os.path.join(root, mutation["target"])
        source = open(target, encoding="utf-8").read()
        n = source.count(mutation["anchor"])
        if n == 0:
            return "NOT APPLIED", "anchor matched 0 times -- this mutation tested NOTHING"
        if n > 1:
            return "AMBIGUOUS", "anchor matched %d times; exactly 1 is required" % n
        mutated = source.replace(mutation["anchor"], mutation["replacement"])
        if mutated == source:
            return "NO-OP", "the mutation did not change any bytes"
        open(target, "w", encoding="utf-8").write(mutated)
        try:
            py_compile.compile(target, doraise=True, cfile=os.path.join(parent, "m.pyc"))
        except py_compile.PyCompileError as exc:
            return "SYNTAX INVALID", str(exc).strip().splitlines()[-1][:120]
        kind, problem = provenance(root)
        if kind:
            return "%s ERROR" % kind, problem + " -- NOT a kill"
        code, failures, collected = run_focused(root)
        if collected != expected_count:
            return "SETUP ERROR", "collected %d tests, expected %d -- NOT a kill" \
                                  % (collected, expected_count)
        if code == 0:
            return "SURVIVED", "the focused suite still passed"
        if mutation["discriminator"] not in failures:
            return "KILLED FOR WRONG REASON", "%s did not fail; failures were %s" \
                                              % (mutation["discriminator"], failures)
        return "KILLED", "by %s (%d failing)" % (mutation["discriminator"], len(failures))
    finally:
        shutil.rmtree(parent, ignore_errors=True)


def self_test():
    """The harness must REFUSE to call these kills. Temporary inputs only."""
    good = MUTATIONS[0]
    cases = [
        ("missing anchor", dict(good, anchor="NO_SUCH_TOKEN_XYZ"), "NOT APPLIED", None),
        ("ambiguous anchor", dict(good, anchor="    return "), "AMBIGUOUS", None),
        ("no-op", dict(good, replacement=good["anchor"]), "NO-OP", None),
        ("syntax invalid", dict(good, replacement="    return (((\n"), "SYNTAX INVALID", None),
        ("loader failure", dict(good, anchor="import itertools\n",
                                replacement="import itertools\nimport no_such_mogo_mod\n"),
         "LOADER ERROR", None),
        ("wrong collected count", good, "SETUP ERROR", EXPECTED_FOCUSED_TESTS + 1),
        ("wrong discriminator", dict(good, discriminator="test_misnamed_xyz"),
         "KILLED FOR WRONG REASON", None),
        ("true kill still recognised", good, "KILLED", None),
    ]
    ok_all = True
    for desc, mutation, expect, count in cases:
        verdict, note = evaluate(mutation, expected_count=count or EXPECTED_FOCUSED_TESTS)
        ok = verdict == expect
        ok_all &= ok
        print("  %-28s -> %-24s %s" % (desc, verdict, "PASS" if ok else "FAIL (want %s)" % expect))
    kind, problem = provenance(REPO_ROOT)   # read-only: the real tree must NOT pass as a mirror
    ok = bool(kind)
    ok_all &= ok
    print("  %-28s -> %-24s %s" % ("provenance on real repo", kind or "ACCEPTED",
                                   "PASS" if ok else "FAIL"))
    return ok_all


def main():
    before = guarded_hashes()
    if "--self-test" in sys.argv:
        ok = self_test()
    else:
        base_ok, base_note = baseline()
        print("BASE positive control (unmutated)                            %-24s %s"
              % ("PASS" if base_ok else "FAIL", base_note))
        if not base_ok:
            print("FAIL: no mutation verdict is meaningful against a failing baseline")
            return 1
        verdicts = []
        for mutation in MUTATIONS:
            verdict, note = evaluate(mutation)
            verdicts.append(verdict)
            print("%-4s %-58s %-24s %s" % (mutation["mid"], mutation["desc"], verdict, note))
        killed = sum(v == "KILLED" for v in verdicts)
        print("RESULT: %d/%d killed" % (killed, len(MUTATIONS)))
        ok = killed == len(MUTATIONS)
    moved = sorted(rel for rel, h in guarded_hashes().items() if before[rel] != h)
    if moved:
        print("FAIL: the harness changed repository files: %s" % moved)
        ok = False
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

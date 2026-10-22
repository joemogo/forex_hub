#!/usr/bin/env python3
"""Can the bar-quantization fixtures still DETECT a broken close-stamp rule?

R-3 (MOGO-IMPORT-SCOPE-2026-10-20.md): from v12.42.0 a forward `closedAt` can be the
minute-aligned MARKET exit, and counting it as the engine's clock withdrew
REPLAY_IS_BAR_QUANTIZED. P1 below IS that pre-fix behaviour; it must be killed.

A DEDICATED GATE, not a registered suite: the filename does NOT start with `test_`, so it adds
nothing to `expected_python_test_counts.tsv`. Same design as mutate_balance_reconcile.py:

  * every mutation goes to a FRESH mirrored temporary tree, so the test module's own REPO_ROOT
    resolves inside it, and a provenance probe proves the MUTATED modules loaded;
  * an anchor must match exactly once, or the mutation is NOT APPLIED / AMBIGUOUS, never
    silently skipped;
  * a mutant that does not compile, or that changes the collected count, is a setup failure
    and never a kill;
  * a kill counts only if the NAMED discriminator failed;
  * an unmutated mirror must pass in full first (positive control), or no verdict is scored;
  * guarded repository files are hashed before and after, and must not move.

The corpus is never copied: only the hermetic classes run, so no corpus behaviour can
influence a verdict. The real-corpus checks run in the ordinary suite.

Run directly:  python3 tests/trader_intelligence/mutate_population_fidelity.py
Self-test:     python3 tests/trader_intelligence/mutate_population_fidelity.py --self-test
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
PF_REL = os.path.join(MODULE_REL, "population_fidelity.py")
TEST_REL = os.path.join("tests", "trader_intelligence", "test_population_fidelity.py")

_T = "tests.trader_intelligence.test_population_fidelity."
FOCUSED = (_T + "TestAMarketExitCloseStampIsNotTheEngineClock",
           _T + "TestUninterpretableCloseTimingIsRefused",
           _T + "TestBarQuantization")
EXPECTED_FOCUSED_TESTS = 17

GUARDED = (PF_REL, TEST_REL, os.path.join(MODULE_REL, "balance_reconcile.py"), "index.html",
           os.path.join("tests", "expected_python_test_counts.tsv"))

M = dict
MUTATIONS = (
    M(mid="P1", target=PF_REL, desc="PRE-FIX: forward counts closedAt whatever its basis",
      anchor="population_stats(rows, processing_clock=(name == to.FORWARD))",
      replacement="population_stats(rows, processing_clock=False)",
      discriminator="test_POSITIVE_CONTROL_minute_aligned_market_exits_do_not_erase_the_finding"),
    M(mid="P2", target=PF_REL, desc="bounded basis reads the market exit, not capturedAt",
      anchor="    return record[\"capturedAt\"]\n", replacement="    return record[\"closedAt\"]\n",
      discriminator="test_POSITIVE_CONTROL_minute_aligned_market_exits_do_not_erase_the_finding"),
    M(mid="P3", target=PF_REL, desc="replay also swaps in capturedAt (its wall clock)",
      anchor="population_stats(rows, processing_clock=(name == to.FORWARD))",
      replacement="population_stats(rows, processing_clock=True)",
      discriminator="test_replay_keeps_its_own_clock_even_with_a_bounded_basis"),
    M(mid="P4", target=PF_REL, desc="prefer capturedAt whenever present, ignoring the basis",
      anchor="    if record.get(\"closedAtBasis\") in br.EXACT_BASES:\n",
      replacement="    if not record.get(\"capturedAt\"):\n",
      discriminator="test_an_exact_basis_still_reads_closedAt"),
    M(mid="P5", target=PF_REL, desc="skip validating the basis and capturedAt",
      anchor="        br.processing_bounds(record)\n", replacement="        pass\n",
      discriminator="test_an_unparseable_capturedAt_is_refused"),
    M(mid="P6", target=PF_REL, desc="swallow the refusal (uncountable close skipped silently)",
      anchor="        _refuse(\"%s: cannot tell",
      replacement="        return None\n        _refuse(\"%s: cannot tell",
      discriminator="test_a_bounded_basis_without_capturedAt_is_refused"),
    M(mid="P7", target=PF_REL, desc="ignore every close stamp (count openedAt only)",
      anchor="             for stamp in (r.get(\"openedAt\"), close) if stamp]),\n",
      replacement="             for stamp in (r.get(\"openedAt\"),) if stamp]),\n",
      discriminator="test_a_genuinely_quantized_forward_capture_is_still_detected"),
    M(mid="P8", target=PF_REL, desc="drop entry stamps (count the close only)",
      anchor="             for stamp in (r.get(\"openedAt\"), close) if stamp]),\n",
      replacement="             for stamp in (close,) if stamp]),\n",
      discriminator="test_entry_timestamps_are_counted_too_not_just_exits"),
    M(mid="P9", target=PF_REL, desc="ANY sub-second forward stamp suffices (not ALL)",
      anchor="                and forward_grid[\"subSecond\"] == forward_total):\n",
      replacement="                and forward_grid[\"subSecond\"] > 0):\n",
      discriminator="test_a_genuinely_quantized_forward_capture_is_still_detected"),
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
    os.makedirs(os.path.dirname(os.path.join(root, TEST_REL)), exist_ok=True)
    shutil.copy2(os.path.join(REPO_ROOT, TEST_REL), os.path.join(root, TEST_REL))
    return root


_PROBE = r"""
import json, os, sys
real = os.path.realpath(%r)
import tests.trader_intelligence.test_population_fidelity as t
leaked = sorted(n for n, m in list(sys.modules.items())
                if getattr(m, "__file__", None)
                and os.path.realpath(m.__file__).startswith(real + os.sep))
print(json.dumps({"pf": os.path.realpath(t.pf.__file__),
                  "br": os.path.realpath(t.pf.br.__file__), "leaked": leaked}))
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
    problems = ["%s loaded from %s" % (k, info[k]) for k in ("pf", "br")
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
    parent = tempfile.mkdtemp(prefix="mogo-pf-base-")
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
    parent = tempfile.mkdtemp(prefix="mogo-pf-mut-%s-" % mutation["mid"])
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
        ("syntax invalid", dict(good, replacement="population_stats((("), "SYNTAX INVALID", None),
        ("loader failure", dict(good, anchor="import statistics\n",
                                replacement="import statistics\nimport no_such_mogo_mod\n"),
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

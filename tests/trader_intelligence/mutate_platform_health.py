#!/usr/bin/env python3
"""Can the platform-health freshness fixtures still DETECT a broken live-store check?

A DEDICATED GATE, not a registered suite. Its assertions are about whether
`TestLiveStoreFreshnessIsDeterministic` can still notice incorrectness -- so folding them
into `expected_python_test_counts.tsv` would conflate "the code is correct" with "the tests
can see it go wrong". The filename deliberately does NOT start with `test_`, which is the
prefix both `tests/run_all.sh` and `tests/count_python_tests.py` enumerate by, so this file
adds nothing to the registered 1515-test / 30-module totals.

WHY THIS EXISTS. `994e2da` repaired a fixture that used REPO_ROOT as a stand-in live store
and therefore decayed into a failure once the repository had not been written for
STORE_STALE_AFTER_HOURS. That repair is correct and is unchanged here. But its commit
message reported "7/7 killed" from a scratch tool that was never committed, and described
the mutated module as being "re-pointed at via sys.path". That mechanism was re-examined and
does not hold:

  * A plain `sys.path.insert(0, tmpdir)` does NOT redirect the import. `test_platform_health`
    performs its own `sys.path.insert(0, REPO_ROOT/scripts/trader_intelligence)` when it is
    imported, which wins -- so the REAL module loads and every mutation survives silently.
  * Pre-seeding `sys.modules` with the mutated copy does load it, but leaves the TEST module
    rooted in the real repository. Its `REPO_ROOT` then points at a tree the mutated module
    knows nothing about, the real-corpus test loads an empty corpus and reports RED, and
    that unrelated failure was the only failure produced. A NO-OP "mutation" scores as a
    kill under those conditions, which makes the whole result meaningless.

So a nonzero unittest exit is NOT evidence of a kill, and neither is "some test failed".
This harness mirrors the tree instead: the module copy AND the test module copy live under
one temporary root, so the test module's own REPO_ROOT resolves inside that root and the
structural source-reading assertion reads the MUTATED file. Every kill must be attributed to
a NAMED discriminator.

FOCUSED BY CONSTRUCTION. Only `TestLiveStoreFreshnessIsDeterministic` runs, because only its
ten tests discriminate P1-P7. The observation corpus is never copied, symlinked, opened or
depended on, so no corpus behaviour can influence a mutation verdict -- which is precisely
the defect that made the earlier evidence invalid. The full 31-test module still runs once
per lane against the real committed source in `tests/run_all.sh`.

RESULT: 7/7 killed -- 6 BEHAVIOURAL and 1 STRUCTURAL-CONTRACT. P1 is structural and is
reported as such. No behavioural assertion can distinguish a REPO_ROOT selftest fixture from
a controlled one without depending on the repository's current mtime, which is exactly the
time-dependence being designed out; a "behavioural" kill of P1 would fire or not fire
according to the calendar. Do not describe this gate as uniform behavioural coverage.

Run directly:  python3 tests/trader_intelligence/mutate_platform_health.py
Self-test:     python3 tests/trader_intelligence/mutate_platform_health.py --self-test
"""
import hashlib
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
PH_REL = os.path.join(MODULE_REL, "platform_health.py")
TEST_REL = os.path.join("tests", "trader_intelligence", "test_platform_health.py")

FOCUSED = "tests.trader_intelligence.test_platform_health.TestLiveStoreFreshnessIsDeterministic"

#: The focused class collects exactly this many tests. A mutated run that collects a
#: different number did not exercise the discriminators and is a setup failure, never a kill.
EXPECTED_FOCUSED_TESTS = 10

#: Re-hashed before and after the run. Drift here means the harness wrote to the repository,
#: which it must never do -- every mutation goes to a temporary copy.
GUARDED = (PH_REL, TEST_REL, "index.html", "regression-baseline.json",
           os.path.join("tests", "expected_python_test_counts.tsv"))

BEHAVIOURAL, STRUCTURAL = "BEHAVIOURAL", "STRUCTURAL-CONTRACT"


# ── mutation catalog ────────────────────────────────────────────────────────────────────────
# Each entry mutates a COPY of platform_health.py and names the ONE test whose failure counts
# as the kill. Anchors must match exactly once; a catalog whose anchor has drifted is reported
# as NOT APPLIED rather than silently skipped.
MUTATIONS = (
    dict(
        mid="P1",
        kind=STRUCTURAL,
        desc="reintroduce REPO_ROOT as the GREEN selftest fixture",
        why="The defect 994e2da repaired. Killed structurally on purpose: a behavioural kill "
            "would depend on the repository's current mtime, which is the very "
            "time-dependence being designed out.",
        anchor='        t("live store GREEN when freshly written",\n'
               '          _at(0.0) == GREEN)',
        replacement='        t("live store GREEN when freshly written",\n'
                    '          check_live_store(store_path=REPO_ROOT)["state"] == GREEN)',
        discriminator="test_the_selftest_live_store_fixtures_are_controlled_not_the_repository",
    ),
    dict(
        mid="P2",
        kind=BEHAVIOURAL,
        desc="ignore the injected clock",
        why="Restores the wall-clock read that made the original fixture decay.",
        anchor="    return clock if clock is not None else "
               "datetime.datetime.now(datetime.timezone.utc)",
        replacement="    return datetime.datetime.now(datetime.timezone.utc)",
        discriminator="test_the_injected_clock_is_honoured",
    ),
    dict(
        mid="P3",
        kind=BEHAVIOURAL,
        desc="force a fresh store to YELLOW (comparison always true)",
        why="A store being written right now must not report as stale.",
        anchor="        if age_h > stale_hours:",
        replacement="        if True:",
        discriminator="test_a_controlled_fresh_store_is_green",
    ),
    dict(
        mid="P4",
        kind=BEHAVIOURAL,
        desc="force a stale store to GREEN (comparison always false)",
        why="The failure that matters operationally: a dead engine reporting healthy.",
        anchor="        if age_h > stale_hours:",
        replacement="        if False:",
        discriminator="test_a_controlled_stale_store_is_yellow",
    ),
    dict(
        mid="P5",
        kind=BEHAVIOURAL,
        desc="change the threshold comparison from > to >=",
        why="Production defines `age_h > stale_hours`, so exactly at the threshold is GREEN. "
            "This is the off-by-one the two boundary cases were added for.",
        anchor="        if age_h > stale_hours:",
        replacement="        if age_h >= stale_hours:",
        discriminator="test_exactly_at_the_threshold_is_green_because_the_operator_is_strict",
    ),
    dict(
        mid="P6",
        kind=BEHAVIOURAL,
        desc="bypass the stale threshold at the resolution site",
        why="Same outcome as P4 but a DIFFERENT source line, so the threshold resolution is "
            "covered independently of the comparison.",
        anchor="    stale_hours = STORE_STALE_AFTER_HOURS if stale_hours is None else stale_hours",
        replacement="    stale_hours = float('inf')",
        discriminator="test_a_controlled_stale_store_is_yellow",
    ),
    dict(
        mid="P7",
        kind=BEHAVIOURAL,
        desc="treat a missing store as GREEN",
        why="Absence is not health. UNKNOWN must never be smoothed into GREEN.",
        anchor='            return _check("live_store", UNKNOWN,\n'
               '                          "the MOGO origin store is not present at the '
               'expected path",',
        replacement='            return _check("live_store", GREEN,\n'
                    '                          "the MOGO origin store is not present at the '
                    'expected path",',
        discriminator="test_a_missing_store_is_unknown_not_green_and_not_red",
    ),
)


# ── repository guard ────────────────────────────────────────────────────────────────────────
def _sha256(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def guarded_hashes():
    return {rel: _sha256(os.path.join(REPO_ROOT, rel)) for rel in GUARDED}


def drifted(before):
    """Guarded repository files that no longer match `before`. Empty is the only good answer."""
    now = guarded_hashes()
    return sorted(rel for rel in before if before[rel] != now.get(rel))


# ── mirrored tree ───────────────────────────────────────────────────────────────────────────
def build_root(parent):
    """A temporary mirror holding ONLY what the focused tests need.

    Copies the module tree's `.py` files and the one test module. Nothing else -- no
    `__pycache__`, no `.pyc`, no generated reports, no evidence, no corpus. The test module's
    REPO_ROOT therefore resolves to this root, which is what makes the structural assertion
    read the MUTATED source instead of the repository's.
    """
    root = os.path.join(parent, "root")
    dst_mod = os.path.join(root, MODULE_REL)
    os.makedirs(dst_mod)
    os.makedirs(os.path.dirname(os.path.join(root, TEST_REL)))
    src_mod = os.path.join(REPO_ROOT, MODULE_REL)
    for name in os.listdir(src_mod):
        if name.endswith(".py"):
            shutil.copy2(os.path.join(src_mod, name), os.path.join(dst_mod, name))
    shutil.copy2(os.path.join(REPO_ROOT, TEST_REL), os.path.join(root, TEST_REL))
    return root


_PROBE = r"""
import hashlib, json, os, sys
m = __import__(%r, fromlist=["*"])
real = os.path.realpath(%r)
# The exact path the structural assertion opens.
structural = os.path.join(m.REPO_ROOT, "scripts", "trader_intelligence", "platform_health.py")
leaked = sorted(
    name for name, mod in list(sys.modules.items())
    if getattr(mod, "__file__", None)
    and os.path.realpath(mod.__file__).startswith(real + os.sep))
print(json.dumps({
    "module_file": os.path.realpath(m.ph.__file__),
    "test_repo_root": os.path.realpath(m.REPO_ROOT),
    "structural_path": os.path.realpath(structural),
    "structural_sha": hashlib.sha256(open(structural, "rb").read()).hexdigest(),
    "leaked_from_repo": leaked,
}))
"""


def provenance(root):
    """Prove the temporary module -- not the repository's -- is what the tests loaded.

    `sys.path` insertion is NOT accepted as proof: it demonstrably fails to redirect this
    import. Every path is realpath-normalised, because macOS hands back `/var/...` from
    `tempfile` and `/private/var/...` from the child process, and the naive string compare
    reports a false provenance failure.

    Returns (info, problem, kind). `kind` separates the two ways this can go wrong, because
    conflating them would misreport the cause: a probe that cannot RUN is a loader failure
    (the mutant broke the import), whereas a probe that runs and reports the wrong paths is a
    genuine provenance failure (the real module was loaded). Neither is ever a kill.
    """
    module_name = FOCUSED.rsplit(".", 1)[0]
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [sys.executable, "-c", _PROBE % (module_name, REPO_ROOT)],
        cwd=root, capture_output=True, text=True, env=env)
    if proc.returncode != 0:
        return None, "the module could not be imported at all: %s" \
                     % (proc.stderr.strip().splitlines()[-1][:200],), "LOADER"
    try:
        import json
        info = json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception as exc:                                          # noqa: BLE001
        return None, "provenance probe produced no parseable result: %s" % exc, "LOADER"

    rroot = os.path.realpath(root)
    expected_sha = _sha256(os.path.join(root, PH_REL))
    problems = []
    if not info["module_file"].startswith(rroot + os.sep):
        problems.append("platform_health loaded from %s -- OUTSIDE the temporary root"
                        % info["module_file"])
    if info["test_repo_root"] != rroot:
        problems.append("test module REPO_ROOT is %s, expected %s"
                        % (info["test_repo_root"], rroot))
    if not info["structural_path"].startswith(rroot + os.sep):
        problems.append("the structural assertion would read %s -- OUTSIDE the temporary root"
                        % info["structural_path"])
    if info["structural_sha"] != expected_sha:
        problems.append("the structural assertion reads a file whose sha256 is not the "
                        "temporary source's")
    if info["leaked_from_repo"]:
        problems.append("modules imported from the real repository: %s"
                        % ", ".join(info["leaked_from_repo"]))
    return info, ("; ".join(problems) if problems else None), "PROVENANCE"


def run_focused(root):
    """Run ONLY the focused class. Returns (returncode, failing test names, collected count)."""
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run([sys.executable, "-m", "unittest", "-v", FOCUSED],
                          cwd=root, capture_output=True, text=True, env=env)
    out = proc.stdout + proc.stderr
    failures = sorted(set(re.findall(r"^(?:FAIL|ERROR): (\w+)", out, re.M)))
    match = re.search(r"^Ran (\d+) tests?", out, re.M)
    return proc.returncode, failures, (int(match.group(1)) if match else -1)


# ── one mutation ────────────────────────────────────────────────────────────────────────────
def evaluate(mutation, expected_count=EXPECTED_FOCUSED_TESTS):
    """Apply one mutation to a FRESH temporary copy and classify the outcome.

    Returns (verdict, note, failures). Only "KILLED" counts; every other verdict fails the
    gate. Each mutation is applied independently to an unmodified copy, so no mutation can
    mask or assist another.
    """
    parent = tempfile.mkdtemp(prefix="mogo-ph-mut-%s-" % mutation["mid"])
    try:
        root = build_root(parent)
        target = os.path.join(root, PH_REL)
        with open(target, encoding="utf-8") as handle:
            source = handle.read()

        matches = source.count(mutation["anchor"])
        if matches == 0:
            return "NOT APPLIED", "anchor matched 0 times -- the catalog has drifted from " \
                                  "the source and this mutation tested NOTHING", []
        if matches > 1:
            return "AMBIGUOUS", "anchor matched %d times; exactly 1 is required" % matches, []

        mutated = source.replace(mutation["anchor"], mutation["replacement"])
        if mutated == source:
            return "NO-OP", "the mutation did not change any bytes", []
        with open(target, "w", encoding="utf-8") as handle:
            handle.write(mutated)

        try:
            py_compile.compile(target, doraise=True,
                               cfile=os.path.join(parent, "mutant.pyc"))
        except py_compile.PyCompileError as exc:
            return "SYNTAX INVALID", "the mutant does not compile (%s) -- NOT a kill" \
                                     % str(exc).strip().splitlines()[-1][:120], []

        info, problem, kind = provenance(root)
        if problem:
            verdict = ("LOADER/SETUP ERROR" if kind == "LOADER" else "PROVENANCE FAILURE")
            return verdict, "%s -- NOT a kill" % problem, []

        code, failures, collected = run_focused(root)
        if collected != expected_count:
            return "LOADER/SETUP ERROR", \
                   "collected %d tests, expected %d -- the discriminators did not run, " \
                   "so this is NOT a kill" % (collected, expected_count), failures
        if code == 0:
            return "SURVIVED", "the focused suite still passed", []
        if mutation["discriminator"] not in failures:
            return "KILLED FOR WRONG REASON", \
                   "%s did not fail; the failures were %s" \
                   % (mutation["discriminator"], ", ".join(failures) or "none"), failures
        return "KILLED", "by %s" % mutation["discriminator"], failures
    finally:
        shutil.rmtree(parent, ignore_errors=True)


# ── self-test ───────────────────────────────────────────────────────────────────────────────
def _synthetic(desc, mutation, expect, expected_count=EXPECTED_FOCUSED_TESTS):
    verdict, note, _ = evaluate(mutation, expected_count=expected_count)
    ok = verdict == expect
    print("  %-28s -> %-24s %s" % (desc, verdict, "PASS" if ok else "FAIL (expected %s)" % expect))
    print("      %s" % note)
    return ok


def self_test():
    """Prove the harness REJECTS each way a mutation run can lie.

    Everything below runs on temporary synthetic inputs. No repository file is modified to
    test a failure path -- a gate that had to damage the tree to prove it works would be a
    worse problem than the one it detects.
    """
    print("=== SELF-TEST: the harness must refuse to call these kills ===")
    good = "        if age_h > stale_hours:"
    base = dict(mid="ST", kind=BEHAVIOURAL, desc="", why="",
                discriminator="test_a_controlled_fresh_store_is_green")
    results = []

    results.append(_synthetic(
        "1 missing anchor",
        dict(base, anchor="        if age_h > NO_SUCH_TOKEN:", replacement="        if True:"),
        "NOT APPLIED"))
    results.append(_synthetic(
        "2 ambiguous anchor",
        dict(base, anchor="        return _check(", replacement="        return _check("),
        "AMBIGUOUS"))
    results.append(_synthetic(
        "3 syntax-invalid mutation",
        dict(base, anchor=good, replacement="        if age_h > (((stale_hours:"),
        "SYNTAX INVALID"))
    results.append(_synthetic(
        "4 no-op mutation",
        dict(base, anchor=good, replacement=good),
        "NO-OP"))
    results.append(_synthetic(
        "5 loader failure",
        dict(base, anchor="import argparse",
             replacement="import argparse\nimport nonexistent_mogo_module_xyz"),
        "LOADER/SETUP ERROR"))
    # A mutation that de-collects a test rather than failing one: the count guard, not the
    # discriminator guard, is what has to catch this.
    results.append(_synthetic(
        "6 wrong collected count",
        dict(base, anchor=good, replacement="        if True:"),
        "LOADER/SETUP ERROR", expected_count=EXPECTED_FOCUSED_TESTS + 1))
    results.append(_synthetic(
        "7 wrong expected discriminator",
        dict(base, anchor=good, replacement="        if True:",
             discriminator="test_a_controlled_fresh_store_is_green_MISNAMED"),
        "KILLED FOR WRONG REASON"))

    # 8 provenance failure: point the probe at the REAL repository root, which is exactly the
    # condition the naive sys.path approach silently produced. Read-only; nothing is written.
    print("  %-28s -> " % "8 provenance failure", end="")
    _info, problem, _kind = provenance(REPO_ROOT)
    ok = bool(problem)
    print("%-24s %s" % ("PROVENANCE FAILURE" if ok else "NOT DETECTED",
                        "PASS" if ok else "FAIL"))
    print("      %s" % (problem or "the real repository was accepted as a temporary root"))
    results.append(ok)

    # 9 repository hash mismatch: corrupt the EXPECTED value, never the file.
    print("  %-28s -> " % "9 repository hash mismatch", end="")
    tampered = guarded_hashes()
    tampered[PH_REL] = "0" * 64
    found = drifted(tampered)
    ok = found == [PH_REL]
    print("%-24s %s" % ("DRIFT DETECTED" if ok else "NOT DETECTED", "PASS" if ok else "FAIL"))
    print("      guard reported: %s" % (", ".join(found) or "nothing"))
    results.append(ok)

    passed = sum(1 for r in results if r)
    print("\nself-test: %d/%d false-kill conditions rejected" % (passed, len(results)))
    return 0 if passed == len(results) else 1


# ── main ────────────────────────────────────────────────────────────────────────────────────
def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    before = guarded_hashes()

    if "--self-test" in argv:
        code = self_test()
        found = drifted(before)
        if found:
            print("\nREPOSITORY DRIFT during self-test: %s" % ", ".join(found))
            return 1
        print("guarded repository files unchanged")
        return code

    print("=== PLATFORM-HEALTH MUTATION GATE ===")
    print("focused suite: %s" % FOCUSED)
    print("the observation corpus is never copied, opened or depended on\n")

    # An unmutated control FIRST. Without it, "SURVIVED" and "the suite never really ran"
    # are indistinguishable -- and a no-op scoring as a kill is precisely how the earlier,
    # uncommitted evidence for this repair went wrong.
    parent = tempfile.mkdtemp(prefix="mogo-ph-control-")
    try:
        root = build_root(parent)
        info, problem, kind = provenance(root)
        if problem:
            print("CONTROL %s: %s" % ("LOADER FAILURE" if kind == "LOADER"
                                      else "PROVENANCE FAILURE", problem))
            return 1
        print("provenance: platform_health -> %s" % info["module_file"])
        print("provenance: test REPO_ROOT  -> %s" % info["test_repo_root"])
        print("provenance: structural read -> %s" % info["structural_path"])
        print("provenance: no modules imported from the repository")
        code, failures, collected = run_focused(root)
        if code != 0 or collected != EXPECTED_FOCUSED_TESTS:
            print("CONTROL FAILED: collected %d (expected %d), failures %s"
                  % (collected, EXPECTED_FOCUSED_TESTS, ", ".join(failures) or "none"))
            print("The unmutated mirror does not pass, so no mutation result is meaningful.")
            return 1
        print("control: %d/%d focused tests pass unmutated\n" % (collected, collected))
    finally:
        shutil.rmtree(parent, ignore_errors=True)

    results = []
    for mutation in MUTATIONS:
        verdict, note, failures = evaluate(mutation)
        results.append((mutation, verdict, note, failures))
        print("%s [%s] %s" % (mutation["mid"], mutation["kind"], mutation["desc"]))
        print("    %-24s %s" % (verdict, note))
        if failures:
            print("    all failures: %s" % ", ".join(failures))

    killed = [m for m, v, _n, _f in results if v == "KILLED"]
    behavioural = [m for m in killed if m["kind"] == BEHAVIOURAL]
    structural = [m for m in killed if m["kind"] == STRUCTURAL]

    print("\n%d/%d killed -- %d behavioural, %d structural-contract"
          % (len(killed), len(MUTATIONS), len(behavioural), len(structural)))
    if structural:
        print("NOT uniform behavioural coverage: %s killed by a source-structure assertion, "
              "because a behavioural kill would depend on the repository's current age."
              % ", ".join(m["mid"] for m in structural))

    found = drifted(before)
    if found:
        print("\nREPOSITORY DRIFT: %s -- the harness wrote to the repository" % ", ".join(found))
        return 1
    print("guarded repository files unchanged")

    if len(killed) != len(MUTATIONS):
        print("\nGATE FAILED: %s"
              % ", ".join("%s=%s" % (m["mid"], v) for m, v, _n, _f in results if v != "KILLED"))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

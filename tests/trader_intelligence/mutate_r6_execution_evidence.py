#!/usr/bin/env python3
"""Can the R-6 fixtures still DETECT a broken execution-evidence mechanism?

R-6 (MOGO_R6_OPTION_A_IMPLEMENTATION.md): the importer carries the v12.42.0 gap-exit
evidence beside the booked exit, refuses inconsistent evidence, and the validator
refuses any broker or execution-verified claim on a MOGO record. Each mutation below
breaks exactly one of those properties, and each must be killed by the test NAMED
for it.

A DEDICATED GATE, not a registered suite: the filename does NOT start with `test_`,
so it adds nothing to `expected_python_test_counts.tsv`. Same design as
mutate_population_fidelity.py:

  * every mutation goes to a FRESH mirrored temporary tree. The test module's own
    REPO_ROOT resolves inside that tree, and a provenance probe proves the MUTATED
    modules are the ones loaded;
  * an anchor must match exactly once. Otherwise the mutation is NOT APPLIED or
    AMBIGUOUS, never silently skipped;
  * a mutant that does not compile, or that changes the collected test count, is a
    setup failure and never a kill;
  * a kill counts only if the NAMED discriminator failed;
  * an unmutated mirror must pass in full first (positive control), or no verdict is
    scored;
  * guarded repository files are hashed before and after, and must not move.

Only the hermetic classes run. The real-corpus and schema checks run in the ordinary
suite.

Run directly:  python3 tests/trader_intelligence/mutate_r6_execution_evidence.py
Self-test:     python3 tests/trader_intelligence/mutate_r6_execution_evidence.py --self-test
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
IMP_REL = os.path.join(MODULE_REL, "import_mogo_observations.py")
TO_REL = os.path.join(MODULE_REL, "trade_observation.py")
TEST_REL = os.path.join("tests", "trader_intelligence", "test_r6_execution_evidence.py")

_T = "tests.trader_intelligence.test_r6_execution_evidence."
FOCUSED = tuple(_T + c for c in (
    "TestTheFixturesAreTheRealPackages",
    "TestTheGapExitsCarryTheirEvidence",
    "TestTheControlsKeepTheirClassification",
    "TestEveryRealPackageKeepsItsBookedValues",
    "TestInconsistentExecutionEvidenceIsRefused",
    "TestARefusalHaltsTheWholeRun",
    "TestNoBrokerClaimCanBeRecorded",
    "TestNothingIsRetroactive",
))
EXPECTED_FOCUSED_TESTS = 47

GUARDED = (IMP_REL, TO_REL, TEST_REL, "index.html",
           os.path.join("tests", "expected_python_test_counts.tsv"),
           os.path.join("docs", "trader-intelligence", "evidence", "schema",
                        "trade-observation.schema.json"))

_CARRIED = "test_every_execution_field_is_carried_from_its_package_field"
_EXEC_LOOP = "    for target_field, source_key in EXECUTION_MAP:\n        value = outcome.get(source_key)\n"

M = dict
_DROPS = tuple(
    M(mid="D%d" % i, target=IMP_REL, desc="drop EXECUTION_MAP entry %s" % entry,
      anchor="    %s,\n" % entry, replacement="", discriminator=_CARRIED)
    for i, entry in enumerate((
        '("exitPriceBasis", "exitPriceBasis")',
        '("exitTriggerLevel", "exitTriggerLevel")',
        '("exitModeledExecutablePrice", "exitExecutablePrice")',
        '("exitGapPips", "exitGapPips")',
        '("exitGapR", "exitGapR")',
        '("exitQuoteBid", "exitBid")',
        '("exitQuoteAsk", "exitAsk")',
        '("exitQuoteSpreadPips", "exitSpreadPips")',
        '("recordedResultR", "recordedResultR")'), start=1))

MUTATIONS = _DROPS + (
    # --- missing evidence must stay UNKNOWN ---------------------------------------
    M(mid="U1", target=IMP_REL, desc="absent execution field defaulted to 0",
      anchor=_EXEC_LOOP,
      replacement=_EXEC_LOOP + "        value = 0 if value is None else value\n",
      discriminator="test_an_old_format_package_records_every_execution_field_UNKNOWN"),
    M(mid="U2", target=IMP_REL, desc="absent basis defaulted to trigger_level",
      anchor=_EXEC_LOOP,
      replacement=_EXEC_LOOP + "        if target_field == \"exitPriceBasis\" and value is None:\n"
                               "            value = \"trigger_level\"\n",
      discriminator="test_the_snapshot_exit_keeps_an_UNKNOWN_basis"),
    M(mid="U3", target=IMP_REL, desc="a package with no mode assumed LIVE_PAPER",
      anchor='    mode = (package.get("identity") or {}).get("mode")\n',
      replacement='    mode = (package.get("identity") or {}).get("mode") or "LIVE_PAPER"\n',
      discriminator="test_a_package_with_no_mode_is_not_assumed_simulated"),
    M(mid="U4", target=IMP_REL, desc="crossed quote fields (bid <- ask)",
      anchor='    ("exitQuoteBid", "exitBid"),\n', replacement='    ("exitQuoteBid", "exitAsk"),\n',
      discriminator=_CARRIED),
    # --- the seven checks, and the mode check ------------------------------------
    M(mid="C1", target=IMP_REL, desc="rule 1: accept an unsupported basis",
      anchor="    if basis not in EXIT_PRICE_BASES:\n", replacement="    if False:\n",
      discriminator="test_rule1_an_unsupported_basis_is_refused"),
    M(mid="C1b", target=IMP_REL, desc="rule 1: accept gap evidence with no basis",
      anchor="        if stray:\n", replacement="        if False:\n",
      discriminator="test_rule1_gap_evidence_without_a_basis_is_refused"),
    M(mid="C2", target=IMP_REL, desc="rule 2: accept missing / non-finite figures",
      anchor="        if not _finite_number(value):\n", replacement="        if False:\n",
      discriminator="test_rule2_a_non_finite_gap_is_refused"),
    M(mid="C2b", target=IMP_REL, desc="rule 2: accept a gap exit with no gap",
      anchor='    if basis == "candle_open_gap" and (gap_pips <= 0',
      replacement='    if False and (gap_pips <= 0',
      discriminator="test_rule2_a_gap_exit_with_no_gap_is_refused"),
    M(mid="C3", target=IMP_REL, desc="rule 3: accept a stop modelled favourably",
      anchor="        if sign * (executable - trigger) > 0:\n", replacement="        if False:\n",
      discriminator="test_rule3_a_stop_exit_modelled_in_the_positions_favour_is_refused"),
    M(mid="C3b", target=IMP_REL, desc="rule 3 NAIVE: also refuse a favourable TARGET gap",
      anchor="        if sign * (executable - trigger) < 0:\n",
      replacement="        if sign * (executable - trigger) > 0:\n",
      discriminator="test_rule3_a_target_gap_in_the_positions_favour_is_ACCEPTED"),
    M(mid="C4", target=IMP_REL, desc="rule 4: accept a trigger_level exit with a gap",
      anchor='    if basis == "trigger_level" and (gap_pips != 0',
      replacement='    if False and (gap_pips != 0',
      discriminator="test_rule4_a_trigger_level_exit_carrying_a_gap_is_refused"),
    M(mid="C5", target=IMP_REL, desc="rule 5: skip the gap-vs-price consistency check",
      anchor="    if not (math.isclose(gap_pips,", replacement="    if False and not (math.isclose(gap_pips,",
      discriminator="test_rule5_gap_pips_that_disagree_with_the_prices_are_refused"),
    M(mid="C6", target=IMP_REL, desc="rule 6: accept a basis on a snapshot exit",
      anchor='    if outcome.get("exitDetectionSource") != "historical_candle":\n',
      replacement="    if False:\n",
      discriminator="test_rule6_a_basis_on_a_snapshot_exit_is_refused"),
    M(mid="C7", target=IMP_REL, desc="rule 7: accept an exit booked at the model",
      anchor='    if outcome.get("exitPrice") != trigger:\n', replacement="    if False:\n",
      discriminator="test_rule7_an_exit_booked_at_the_model_is_refused"),
    M(mid="C8", target=IMP_REL, desc="accept an unknown mode as SIMULATED",
      anchor="    if mode not in SIMULATED_MODES:\n", replacement="    if False:\n",
      discriminator="test_an_unknown_mode_is_refused"),
    M(mid="H1", target=IMP_REL, desc="a refusal SKIPS the package instead of halting",
      anchor="    check_execution_evidence(package)\n",
      replacement="    try:\n        check_execution_evidence(package)\n"
                  "    except ExecutionEvidenceRefused as exc:\n        return None, str(exc)\n",
      discriminator="test_one_bad_package_stops_every_package_and_writes_nothing"),
    # --- accidental re-pricing ----------------------------------------------------
    M(mid="R1", target=IMP_REL, desc="booked exitPrice re-priced to the model",
      anchor="    provenance = execution_provenance(package, fields)\n",
      replacement="    if fields.get(\"exitModeledExecutablePrice\") is not None:\n"
                  "        fields[\"exitPrice\"] = fields[\"exitModeledExecutablePrice\"]\n"
                  "    provenance = execution_provenance(package, fields)\n",
      discriminator="test_the_booked_values_are_the_simulator_booking_not_the_model"),
    M(mid="R2", target=IMP_REL, desc="pnl and rMultiple re-priced by the gap",
      anchor="    provenance = execution_provenance(package, fields)\n",
      replacement="    if fields.get(\"exitGapR\"):\n"
                  "        fields[\"rMultiple\"] = fields[\"rMultiple\"] - fields[\"exitGapR\"]\n"
                  "        fields[\"pnl\"] = round(fields[\"pnl\"] * (1 + fields[\"exitGapR\"]), 2)\n"
                  "    provenance = execution_provenance(package, fields)\n",
      discriminator="test_the_booked_values_are_the_simulator_booking_not_the_model"),
    # --- false broker-fill classification -----------------------------------------
    M(mid="B1", target=IMP_REL, desc="importer stamps brokerFill CONFIRMED",
      anchor='    return {"executionKind": "SIMULATED", "brokerFill": "NONE",',
      replacement='    return {"executionKind": "SIMULATED", "brokerFill": "CONFIRMED",',
      discriminator="test_provenance_is_simulated_with_no_broker_fill"),
    M(mid="B2", target=TO_REL, desc="validator accepts any brokerFill",
      anchor='    if prov["brokerFill"] != BROKER_FILL_FOR_KIND[kind]:\n', replacement="    if False:\n",
      discriminator="test_a_CONFIRMED_broker_fill_is_refused"),
    M(mid="B3", target=TO_REL, desc="validator accepts executionVerified true",
      anchor='    if prov["executionVerified"] is not False:\n', replacement="    if False:\n",
      discriminator="test_an_execution_verified_claim_is_refused"),
    M(mid="B4", target=TO_REL, desc="validator accepts a caller-chosen field role",
      anchor="        if role != FIELD_ROLES[field]:\n", replacement="        if False:\n",
      discriminator="test_the_booked_exit_cannot_be_relabelled_as_a_fill"),
    M(mid="B5", target=TO_REL, desc="validator ignores broker-named MOGO fields",
      anchor='            if "broker" in key.lower():\n', replacement="            if False:\n",
      discriminator="test_a_broker_named_field_on_a_MOGO_record_is_refused"),
    M(mid="B6", target=TO_REL, desc="validator accepts a broker execution kind",
      anchor="    if kind not in EXECUTION_KINDS:\n", replacement="    if False:\n",
      discriminator="test_a_broker_execution_kind_is_refused"),
    M(mid="B7", target=TO_REL, desc="validator accepts a realized outcome basis",
      anchor='    if prov["outcomeBasis"] != OUTCOME_BASIS_FOR_KIND[kind]:\n',
      replacement="    if False:\n",
      discriminator="test_a_realized_outcome_basis_is_refused"),
    M(mid="B8", target=TO_REL, desc="validator lets an UNKNOWN kind assign roles",
      anchor='    if kind == "UNKNOWN" and roles:\n', replacement="    if False:\n",
      discriminator="test_an_unknown_kind_cannot_assign_roles"),
    M(mid="B9", target=TO_REL, desc="execution_verified_pnl sums booked pnl",
      anchor="    count = len(observations or {})\n",
      replacement="    return sum(r.get(\"pnl\") or 0 for r in (observations or {}).values())\n"
                  "    count = len(observations or {})\n",
      discriminator="test_execution_verified_pnl_refuses_the_eight_records"),
    M(mid="B10", target=TO_REL, desc="provenance validation never called",
      anchor="    _validate_execution_provenance(record)\n    return record\n",
      replacement="    return record\n",
      discriminator="test_a_CONFIRMED_broker_fill_is_refused"),
    # --- whitelist and backfill ---------------------------------------------------
    M(mid="W1", target=TO_REL, desc="whitelist loses the gap fields",
      anchor='    "exitPriceBasis", "exitTriggerLevel", "exitModeledExecutablePrice",\n',
      replacement="",
      discriminator="test_both_gap_exits_record_the_engine_model_beside_the_booking"),
    M(mid="F1", target=IMP_REL, desc="EXECUTION_MAP joins the widening backfill",
      anchor="        for field, key in OUTCOME_MAP:\n",
      replacement="        for field, key in OUTCOME_MAP + EXECUTION_MAP:\n",
      discriminator="test_the_backfill_adds_no_execution_field_to_a_preserved_record"),
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
import tests.trader_intelligence.test_r6_execution_evidence as t
leaked = sorted(n for n, m in list(sys.modules.items())
                if getattr(m, "__file__", None)
                and os.path.realpath(m.__file__).startswith(real + os.sep))
print(json.dumps({"imp": os.path.realpath(t.imp.__file__),
                  "to": os.path.realpath(t.to.__file__),
                  "imp_to": os.path.realpath(t.imp.to.__file__), "leaked": leaked}))
"""


def _env():
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("MOGO_R6_PACKAGES", None)
    return env


def provenance(root):
    proc = subprocess.run([sys.executable, "-c", _PROBE % REPO_ROOT], cwd=root,
                          capture_output=True, text=True, env=_env())
    if proc.returncode != 0:
        return "LOADER", (proc.stderr.strip().splitlines() or ["?"])[-1][:200]
    info = json.loads(proc.stdout.strip().splitlines()[-1])
    rroot = os.path.realpath(root)
    problems = ["%s loaded from %s" % (k, info[k]) for k in ("imp", "to", "imp_to")
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
    """POSITIVE CONTROL: the UNMUTATED mirror must pass in full."""
    parent = tempfile.mkdtemp(prefix="mogo-r6-base-")
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
    parent = tempfile.mkdtemp(prefix="mogo-r6-mut-%s-" % mutation["mid"])
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
    good = next(m for m in MUTATIONS if m["mid"] == "C5")
    cases = [
        ("missing anchor", dict(good, anchor="NO_SUCH_TOKEN_XYZ"), "NOT APPLIED", None),
        ("ambiguous anchor", dict(good, anchor="    return "), "AMBIGUOUS", None),
        ("no-op", dict(good, replacement=good["anchor"]), "NO-OP", None),
        ("syntax invalid", dict(good, replacement="    if (((:"), "SYNTAX INVALID", None),
        ("loader failure", dict(good, anchor="import math\n",
                                replacement="import math\nimport no_such_mogo_mod\n"),
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
    kind, _problem = provenance(REPO_ROOT)   # read-only: the real tree must NOT pass as a mirror
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

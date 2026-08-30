#!/usr/bin/env bash
# Canonical repository test runner for MOGO Trading OS.
#
# Runs EVERY permanent, repository-owned fixture suite under tests/ (files matching
# tests/run_*_tests.js), the Python research suites (tests/trader_intelligence/test_*.py,
# enumerated from disk rather than listed by hand), the evidence-checkpoint selftest,
# the auto-mode governance drift check, and the protected-function/constant drift check.
#
# SCOPE: this runs ONLY repository-owned permanent suites. It does NOT run, and does
# NOT claim to run, the ~22 historical suites that still exist only in an ephemeral
# Claude Code scratchpad outside this repository -- see docs/KNOWN_ISSUES.md and
# docs/TESTING.md for that disclosed, pre-existing gap. This script uses only files
# contained in this repository and never reads from any scratchpad path.
#
# Usage (from anywhere):
#   tests/run_all.sh
# or:
#   bash tests/run_all.sh
#
# Exit status is nonzero if any permanent suite fails, errors, or if protected-function/
# constant drift is detected.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT" || { echo "Could not cd to repository root"; exit 1; }

echo "================================================================"
echo "MOGO Trading OS — canonical repository test run"
echo "Repository root: $REPO_ROOT"
echo "Scope: repository-owned permanent suites under tests/ ONLY."
echo "This does NOT run the historical suites that exist only in an"
echo "ephemeral Claude Code scratchpad outside this repository --"
echo "see docs/KNOWN_ISSUES.md."
echo "================================================================"
echo ""

TOTAL_SUITES=0
TOTAL_FIXTURES=0
TOTAL_PASS=0
TOTAL_FAIL=0
TOTAL_EXEC_ERRORS=0
OVERALL_EXIT=0

shopt -s nullglob
RUNNERS=(tests/run_*_tests.js)
shopt -u nullglob

if [ ${#RUNNERS[@]} -eq 0 ]; then
  echo "No permanent suites found under tests/ (no tests/run_*_tests.js files)."
  echo "Nothing to run."
  exit 1
fi

for runner in "${RUNNERS[@]}"; do
  TOTAL_SUITES=$((TOTAL_SUITES + 1))
  echo "--- $runner ---"
  # A runner may DECLARE its own execution command with a `// RUN_ALL_EXEC:` line.
  #
  # Every suite here runs under osascript, which is right for fixtures that drive index.html.
  # v131 is different: its fixtures test real filesystem and SHA-256 behaviour, so they live in a
  # Node program and the .js file beside them is only a shim that shells out to Node via
  # AppleScript's `doShellScript`. Inside the Bash sandbox that call is denied at the Mach
  # bootstrap port, and the shim used it for BOTH locating Node and running the suite -- so the
  # whole launcher failed and 73 real assertions silently stopped executing while the summary
  # still rendered a suite.
  #
  # The declaration moves that process-launch into this harness, which already has a working
  # shell. It changes no assertion and no production behaviour; the suite still reports its own
  # PASS/FAIL lines and is counted exactly like every other one.
  EXEC_LINE="$(grep -m1 '^// RUN_ALL_EXEC: ' "$runner" 2>/dev/null | sed 's|^// RUN_ALL_EXEC: ||')"
  if [ -n "$EXEC_LINE" ]; then
    OUT="$(eval "$EXEC_LINE" 2>&1)"
  else
    OUT="$(osascript -l JavaScript "$runner" 2>&1)"
  fi
  EC=$?
  # Match only per-fixture result lines ("PASS -- ..." / "FAIL -- ..."), not the suite's
  # own trailing summary line (e.g. "FAILURES: 1/28"), which would otherwise be double-
  # counted as an extra failing fixture since it also starts with "FAIL".
  NP=$(printf '%s\n' "$OUT" | grep -c '^PASS -- ' || true)
  NF=$(printf '%s\n' "$OUT" | grep -c '^FAIL -- ' || true)

  # Count self-reported internal errors. Every runner in this repository catches its own
  # load/parse failures, prints "RUNNER ERROR: ..." and then exits 0 -- so the interpreter's
  # exit code alone cannot be trusted to reveal a suite that never ran.
  RE=$(printf '%s\n' "$OUT" | grep -c '^RUNNER ERROR' || true)

  # A suite that produced NO fixture results has not passed -- it has failed to run.
  #
  # This condition previously also required a nonzero interpreter exit code, which made it
  # unreachable in practice: because each runner swallows its own error and exits 0, a suite
  # that failed to load reported "0 PASS, 0 FAIL" and the overall run still exited 0. If
  # index.html had ever failed to parse, every suite would have reported RUNNER ERROR, zero
  # fixtures would have run, and this script would have declared success. Zero fixtures is now
  # a failure on its own, regardless of exit code.
  if [ $((NP + NF)) -eq 0 ]; then
    echo "$OUT"
    echo "EXECUTION ERROR (exit code $EC) -- suite produced no fixture results"
    TOTAL_EXEC_ERRORS=$((TOTAL_EXEC_ERRORS + 1))
    OVERALL_EXIT=1
    echo ""
    continue
  fi

  # A runner can also report an internal error AFTER emitting some fixtures -- e.g. an async
  # rejection partway through. Those fixtures are real, but the suite is still not trustworthy.
  if [ "$RE" -gt 0 ]; then
    printf '%s\n' "$OUT" | grep '^RUNNER ERROR'
    echo "RUNNER ERROR reported by this suite -- treating as a failure"
    TOTAL_EXEC_ERRORS=$((TOTAL_EXEC_ERRORS + 1))
    OVERALL_EXIT=1
  fi

  # A nonzero interpreter exit is a failure even when fixtures were emitted.
  if [ "$EC" -ne 0 ]; then
    echo "NONZERO INTERPRETER EXIT ($EC) -- treating as a failure"
    OVERALL_EXIT=1
  fi

  if [ "$NF" -gt 0 ]; then
    printf '%s\n' "$OUT" | grep '^FAIL -- '
    OVERALL_EXIT=1
  fi

  # A suite that runs SHORT is a failure, even when every fixture it did run passed.
  #
  # This gate had no notion of how many fixtures a suite should produce. A section that throws
  # part-way is caught by the suite's own try/catch, collapses several fixtures into one reported
  # error, and the suite quietly emits fewer results -- observed during MOGO-021 verification, where
  # a suite ran 36 instead of 39 and nothing objected to the three that vanished. Zero fixtures was
  # already a failure; N-minus-three was not. (§18.12)
  #
  # MORE than expected is also a failure: it means fixtures were added without updating the manifest,
  # so the count would silently stop meaning anything.
  EXPECTED_FILE="tests/expected_fixture_counts.tsv"
  RUNNER_BASE="$(basename "$runner")"
  EXPECTED="$(grep -v '^#' "$EXPECTED_FILE" 2>/dev/null | awk -F'\t' -v r="$RUNNER_BASE" '$1==r{print $2}')"
  ACTUAL=$((NP + NF))
  if [ -z "$EXPECTED" ]; then
    echo "NO EXPECTED FIXTURE COUNT registered for $RUNNER_BASE in $EXPECTED_FILE."
    echo "  A new suite must register its count -- run tests/update_expected_counts.sh and review the diff."
    OVERALL_EXIT=1
  elif [ "$ACTUAL" -ne "$EXPECTED" ]; then
    echo "FIXTURE COUNT MISMATCH for $RUNNER_BASE: expected $EXPECTED, got $ACTUAL."
    if [ "$ACTUAL" -lt "$EXPECTED" ]; then
      echo "  The suite ran SHORT -- fixtures went missing rather than failing. Check for a section"
      echo "  that threw and was swallowed by the suite's own try/catch."
    else
      echo "  The suite ran LONG -- fixtures were added without updating $EXPECTED_FILE."
    fi
    echo "  If the change was deliberate: tests/update_expected_counts.sh, then review the diff."
    OVERALL_EXIT=1
  fi

  echo "$NP PASS, $NF FAIL"
  TOTAL_FIXTURES=$((TOTAL_FIXTURES + NP + NF))
  TOTAL_PASS=$((TOTAL_PASS + NP))
  TOTAL_FAIL=$((TOTAL_FAIL + NF))
  echo ""
done

echo "--- G-2 mutation gate (scan-eligibility freshness) ---"
# A DEDICATED GATE, not an ordinary fixture suite. Its assertions are ABOUT the v1240 suite --
# whether that suite can still detect a broken G-2 -- so folding them into the registered
# fixture count would double-count G-2 coverage and conflate "the code is correct" with "the
# tests can notice incorrectness". It therefore adds nothing to expected_fixture_counts.tsv.
#
# It runs the v1240 suite 11 further times (one unmutated control plus ten mutations) against
# temporary copies of index.html. That duplicated runtime is disclosed rather than hidden; it
# costs roughly two seconds. The ordinary v1240 suite above is unaffected and still runs once.
if ! node tests/mutate_v1240_scan_freshness.js; then
  OVERALL_EXIT=1
fi
echo ""

echo "--- G-4 mutation gate (exit provenance) ---"
# A DEDICATED GATE, on the same terms as the G-2 stage above: its assertions are about whether
# the v1241 suite can still detect a broken exit-provenance repair, so counting them would
# conflate "the code is correct" with "the tests can notice incorrectness". The filename does
# not match tests/run_*_tests.js, which the loop above enumerates, so expected_fixture_counts.tsv
# stays at 2754 and v1241 stays registered once at 83.
#
# It runs the v1241 suite 12 further times (one unmutated control plus eleven mutations) against
# temporary copies of index.html. That duplicated runtime is disclosed rather than hidden; it
# costs roughly twenty seconds. The ordinary v1241 suite above is unaffected and still runs once.
if ! node tests/mutate_v1241_exit_provenance.js; then
  OVERALL_EXIT=1
fi
echo ""

echo "--- Protected-function / protected-constant drift check ---"
if ! python3 regression-baseline-tools.py; then
  OVERALL_EXIT=1
fi
echo ""

# The Python research suites were never in this runner. That is why five failing
# tests sat unnoticed and why a hand-typed module list under-reported the total:
# discovery is not importable here (the test packages have no __init__ chain from
# the repo root), so the modules are enumerated from the filesystem instead of
# being listed by hand, and a new suite file is picked up automatically.
echo "--- Python research suites (trader intelligence) ---"
PY_MODULES="$(find tests/trader_intelligence -name 'test_*.py' \
  | sed 's#/#.#g; s#\.py$##' | sort)"
PY_COUNT="$(printf '%s\n' "$PY_MODULES" | grep -c .)"
if [ "$PY_COUNT" -eq 0 ]; then
  echo "FAIL: no Python test modules found -- the enumeration above is broken."
  OVERALL_EXIT=1
else
  echo "$PY_COUNT module(s)"
  find . -name __pycache__ -type d -not -path "./node_modules/*" -exec rm -rf {} + 2>/dev/null
  # A Python suite that runs SHORT is a failure, exactly as a JS suite is.
  #
  # This lane's only gate was the exit code of the single unittest call below, and
  # PY_COUNT counts FILES rather than tests -- so renaming test_ to xtest_ across a
  # whole module de-collected every test in it and the run still exited 0, because
  # the sibling modules kept the total non-zero. Every mutation killed across
  # twenty-one adversarial rounds is stored in these suites; this lane was the one
  # with no guard against that record quietly shrinking, while the lane holding UI
  # fixtures had one.
  if ! python3 tests/count_python_tests.py --check; then
    OVERALL_EXIT=1
  fi
  if ! python3 -m unittest $PY_MODULES; then
    OVERALL_EXIT=1
  fi
fi
echo ""

echo "--- Real-evidence integration lane (opt-in) ---"
# THIS LANE IS NOT PART OF THE ROUTINE VERDICT, AND THE VERDICT MUST NOT BE READ AS IF IT WERE.
#
# A handful of checks exist specifically to verify the ACTUAL preserved corpus -- that every
# indexed artifact is present and still hashes to its recorded sha256, that the real packages
# re-derive through the production canonicalizer. Those cannot be satisfied by a synthetic
# fixture: a synthetic pass would assert nothing about the real bytes, and labelling one as
# real-corpus verification would be exactly the manufactured result this project forbids.
#
# They therefore live in tests/integration_real_evidence/, deliberately OUTSIDE
# tests/trader_intelligence/ so the count guard does not auto-collect them, and they read
# `evidence/` -- which the sandbox now denies by policy. Running them requires an operator who
# has consciously decided to expose that data to the session.
#
# The routine gate reports NOT RUN. It does not skip quietly, and it never reports success it
# did not observe: if the lane IS enabled and the data is absent or unreadable, the lane fails
# loudly rather than degrading to green.
#
#   MOGO_RUN_REAL_EVIDENCE=1 tests/run_all.sh      # opt in, needs read access to evidence/
if [ "${MOGO_RUN_REAL_EVIDENCE:-0}" = "1" ]; then
  echo "ENABLED -- verifying the ACTUAL preserved corpus."
  if ! MOGO_RUN_REAL_EVIDENCE=1 python3 -m unittest tests.integration_real_evidence.test_real_corpus_integration; then
    OVERALL_EXIT=1
  fi
else
  echo "NOT RUN -- real-evidence verification did NOT execute and is OUTSIDE this run's verdict."
  echo "  The routine verdict below says nothing about the real preserved corpus."
  echo "  Enable deliberately with: MOGO_RUN_REAL_EVIDENCE=1 tests/run_all.sh"
fi
echo ""

echo "--- Evidence extractor selftest ---"
if ! node scripts/mogo_evidence_leveldb_extract.js --selftest; then
  OVERALL_EXIT=1
fi
echo ""

echo "--- Observation coverage selftest ---"
if ! node scripts/mogo_observation_coverage.js --selftest; then
  OVERALL_EXIT=1
fi
echo ""

echo "--- Evidence checkpoint selftest ---"
if ! bash scripts/mogo_evidence_checkpoint.sh --selftest; then
  OVERALL_EXIT=1
fi
echo ""

# MOGO-023. The health authority is itself a critical component: a green indicator nobody
# has ever seen go red is a decoration, not a check. This selftest injects a representative
# failure per check and asserts the aggregation property the whole module exists for --
# UNKNOWN never becomes GREEN. It is bounded, in-process, and touches nothing on disk.
echo "--- Platform health selftest (failure injection) ---"
if ! python3 scripts/trader_intelligence/platform_health.py --selftest; then
  OVERALL_EXIT=1
fi
echo ""

echo "--- Platform-health mutation gate (live-store freshness) ---"
# A DEDICATED GATE, not an ordinary suite. Its assertions are ABOUT whether
# TestLiveStoreFreshnessIsDeterministic can still detect a broken live-store check, so
# counting them would conflate "the code is correct" with "the tests can notice
# incorrectness". The filename does not start with test_, which is the prefix both the
# enumeration below and count_python_tests.py match on, so the registered totals stay at
# 1515 tests / 30 modules and the ordinary module above still runs exactly once.
#
# It runs the FOCUSED 10-test class 8 further times -- one unmutated control plus seven
# mutations -- each against its own temporary mirrored tree. That duplicated runtime is
# disclosed rather than hidden; it costs roughly three seconds. The observation corpus is
# never copied or opened, so no corpus behaviour can influence a mutation verdict.
if ! python3 tests/trader_intelligence/mutate_platform_health.py; then
  OVERALL_EXIT=1
fi
echo ""

# The auto-mode governance block lives in the USER settings file and its sections REPLACE the
# shipped defaults rather than merging, so every rule a newer Claude Code ships is silently
# absent until the generator is re-run. Nothing else would ever say so.
# B-32. The observation<->graph reconciliation was a diagnostic an operator runs by
# hand and CI never did -- so the one check that compares the PRESERVED records
# against the DERIVED graph could drift indefinitely between manual runs. It is
# read-only, writes nothing, and fails closed on an empty corpus, so it is safe to
# run here and meaningless to skip.
echo "--- Observation <-> graph reconciliation ---"
if ! python3 scripts/trader_intelligence/observation_graph_reconcile.py; then
  OVERALL_EXIT=1
fi
echo ""

# The evidence corpus's own integrity report. Its CLI now exits nonzero on an ERROR
# (it gated on FATAL only, so population rebindings exited 0), which is what makes it
# usable as a gate at all.
#
# --check, DELIBERATELY. A no-arg run REWRITES docs/trader-intelligence/evidence/reports/
# integrity-report.json, so this gate could not verify the corpus without mutating a tracked
# artifact -- the lane had to modify the repository in order to report on it, and a full run
# was therefore unavailable to anyone who needed the working tree left alone. --check runs the
# SAME checks and returns the SAME exit code; only the write is skipped. Nothing is filtered,
# downgraded, or read from a cached report.
#
#   verify (this gate):  python3 scripts/trader_intelligence/validate_evidence.py --check
#   regenerate:          python3 scripts/trader_intelligence/validate_evidence.py
echo "--- Evidence corpus integrity ---"
# MOVED BEHIND THE OPT-IN GATE, WITH ITS SEMANTICS UNCHANGED.
#
# `validate_evidence.py --check` validates the ACTUAL preserved corpus, and to do that it must
# resolve each EvidenceSource to its captured artifact under `evidence/` -- a directory the
# sandbox now denies by policy. With that read denied the validator does exactly what it should:
# it reports what it cannot see (WARNING 2 -> 48, ERROR 0 -> 1) and exits nonzero. Those findings
# are CORRECT. Suppressing them, lowering a threshold, or teaching the validator to tolerate an
# unreadable artifact would be weakening the one check that exists to notice missing evidence.
#
# So the invocation moves rather than changes: same command, same findings, same nonzero
# propagation, run only when an operator has deliberately opened that data to the session.
# Nothing about the validator, its thresholds, or the integrity reports is altered.
#
# ROUTINE COVERAGE IS NOT LOST. The validator's BEHAVIOUR is exercised against synthetic corpora
# in tests/trader_intelligence/evidence/test_evidence.py -- including TestCheckModeValidatesWithoutWriting
# (clean input passes, invalid input fails, a missing anchor fails honestly, --check recomputes
# rather than reading a stale report, and check/write modes agree on findings). What the routine
# lane cannot establish is anything about the REAL bytes, and it now says so.
if [ "${MOGO_RUN_REAL_EVIDENCE:-0}" = "1" ]; then
  if ! python3 scripts/trader_intelligence/validate_evidence.py --check; then
    OVERALL_EXIT=1
  fi
else
  echo "REAL-CORPUS INTEGRITY: NOT RUN"
  echo "A routine PASS does not establish real-corpus integrity."
  echo "  The validator's behaviour is covered synthetically; the real corpus is not read here."
  echo "  Enable deliberately with: MOGO_RUN_REAL_EVIDENCE=1 tests/run_all.sh"
fi
echo ""

# The graph validator was NOT a gate, which meant the observation/trader
# contamination guarantee -- the strongest integrity rule in the repository -- had no
# CI gate at all. It also exited 0 on ERRORs until the shared exit_code_for landed, so
# wiring it here before that fix would have gated on nothing.
#
#   verify (this gate):  python3 scripts/trader_intelligence/validate_graph.py --check
#   regenerate:          python3 scripts/trader_intelligence/validate_graph.py
echo "--- Knowledge graph integrity ---"
if ! python3 scripts/trader_intelligence/validate_graph.py --check; then
  OVERALL_EXIT=1
fi
echo ""

echo "--- Acquisition registry integrity ---"
if ! python3 scripts/trader_intelligence/validate_acquisition.py; then
  OVERALL_EXIT=1
fi
echo ""

echo "--- Auto-mode governance config drift check ---"
if ! command -v claude >/dev/null 2>&1; then
  echo "SKIPPED: the 'claude' CLI is not on PATH, so the shipped defaults cannot be read."
  echo "         This check is skipped, NOT passed."
elif ! python3 scripts/auto_mode/build_auto_mode_config.py --check; then
  OVERALL_EXIT=1
fi
echo ""

echo "================================================================"
echo "SUMMARY (repository-owned permanent suites only)"
echo "  Suites run:       $TOTAL_SUITES"
echo "  Execution errors: $TOTAL_EXEC_ERRORS"
echo "  Fixtures run:     $TOTAL_FIXTURES"
echo "  Passed:           $TOTAL_PASS"
echo "  Failed:           $TOTAL_FAIL"
# MOGO-023: THE SUMMARY USED TO RENDER GREEN WHILE THE GATE EXITED RED.
# Every counter above is a FIXTURE counter, but several gates fail the run without touching one:
# a fixture-count mismatch, an unregistered suite, protected-function drift, a validator ERROR,
# auto-mode drift. A v12.40.0 run exited 1 on a fixture-count mismatch while printing
# "Failed: 0" -- an all-green block above an authoritative red exit code. Anyone reading the
# summary rather than `echo $?` would have concluded the gate passed.
# The verdict is therefore derived from OVERALL_EXIT itself, so the block cannot disagree with
# the exit code by construction. UNKNOWN must never render as GREEN, and neither must FAILED.
if [ "$OVERALL_EXIT" -eq 0 ]; then
  echo "  VERDICT:          PASS (exit 0)"
else
  echo "  VERDICT:          FAIL (exit $OVERALL_EXIT) -- scroll up for the failing gate."
  echo "                    A red gate is NOT always a failed fixture: count mismatch,"
  echo "                    unregistered suite, protected drift, validator ERROR or"
  echo "                    auto-mode drift all fail the run with 'Failed: 0' above."
fi
echo ""
echo "NOTE: this run covers repository-owned permanent suites only. Historical"
echo "suites that exist solely in an ephemeral scratchpad outside this repository"
echo "were intentionally NOT run and are NOT counted above -- see docs/KNOWN_ISSUES.md."
echo "================================================================"

exit $OVERALL_EXIT

#!/usr/bin/env bash
# Canonical repository test runner for MOGO Trading OS.
#
# Runs EVERY permanent, repository-owned fixture suite under tests/ (files matching
# tests/run_*_tests.js), plus the protected-function/constant drift check.
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
  OUT="$(osascript -l JavaScript "$runner" 2>&1)"
  EC=$?
  # Match only per-fixture result lines ("PASS -- ..." / "FAIL -- ..."), not the suite's
  # own trailing summary line (e.g. "FAILURES: 1/28"), which would otherwise be double-
  # counted as an extra failing fixture since it also starts with "FAIL".
  NP=$(printf '%s\n' "$OUT" | grep -c '^PASS -- ' || true)
  NF=$(printf '%s\n' "$OUT" | grep -c '^FAIL -- ' || true)

  if [ "$EC" -ne 0 ] && [ $((NP + NF)) -eq 0 ]; then
    echo "$OUT"
    echo "EXECUTION ERROR (exit code $EC) -- suite produced no fixture results"
    TOTAL_EXEC_ERRORS=$((TOTAL_EXEC_ERRORS + 1))
    OVERALL_EXIT=1
    echo ""
    continue
  fi

  if [ "$NF" -gt 0 ]; then
    printf '%s\n' "$OUT" | grep '^FAIL -- '
    OVERALL_EXIT=1
  fi

  echo "$NP PASS, $NF FAIL"
  TOTAL_FIXTURES=$((TOTAL_FIXTURES + NP + NF))
  TOTAL_PASS=$((TOTAL_PASS + NP))
  TOTAL_FAIL=$((TOTAL_FAIL + NF))
  echo ""
done

echo "--- Protected-function / protected-constant drift check ---"
if ! python3 regression-baseline-tools.py; then
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
echo ""
echo "NOTE: this run covers repository-owned permanent suites only. Historical"
echo "suites that exist solely in an ephemeral scratchpad outside this repository"
echo "were intentionally NOT run and are NOT counted above -- see docs/KNOWN_ISSUES.md."
echo "================================================================"

exit $OVERALL_EXIT

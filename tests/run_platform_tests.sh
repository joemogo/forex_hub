#!/usr/bin/env bash
# Standalone runner for the MOGO Automation Platform test suites.
#
# SCOPE: this runs ONLY the platform suites under tests/platform/. It is
# deliberately separate from tests/run_all.sh, which is the canonical
# repository gate and whose modification is separately governed (ADR-012 D-12,
# MOGO-009 Architecture section 33). Until that authorization lands, the
# platform suites run here and the canonical gate stays byte-identical.
#
# This script is named *.sh precisely so that run_all.sh's `tests/run_*_tests.js`
# glob cannot pick it up.
#
# Usage (from anywhere):
#   bash tests/run_platform_tests.sh
#
# Exit status is nonzero if any platform suite fails or errors.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT" || { echo "Could not cd to repository root"; exit 1; }

SUITES=(
  tests.platform.test_platform_identifiers
  tests.platform.test_platform_envelopes
  tests.platform.test_platform_task_states
  tests.platform.test_platform_boundaries
  tests.platform.test_runtime_store_schema
  tests.platform.test_runtime_event_log
  tests.platform.test_runtime_projection
  tests.platform.test_runtime_orchestrator
  tests.platform.test_runtime_capability
  tests.platform.test_runtime_retry
  tests.platform.test_runtime_lease
  tests.platform.test_runtime_dead_letter
  tests.platform.test_runtime_policy_gate
  tests.platform.test_runtime_authorization
  tests.platform.test_runtime_connector_authorization
  tests.platform.test_runtime_connector_transport
  tests.platform.test_runtime_scheduled_collection
  tests.platform.test_runtime_review_disposition
  tests.platform.test_runtime_recovery
  tests.platform.test_runtime_end_to_end
)

echo "================================================================"
echo "MOGO Automation Platform -- platform suites only"
echo "Repository root: $REPO_ROOT"
echo "Python:          $(python3 --version 2>&1)"
echo "Scope: tests/platform/ ONLY. This is NOT the canonical repository"
echo "gate -- run tests/run_all.sh for that. See ADR-012 D-12."
echo "================================================================"
echo ""

OVERALL_EXIT=0
TOTAL_SUITES=0
TOTAL_TESTS=0
TOTAL_FAIL=0
TOTAL_ERROR=0
TOTAL_SKIP=0

for suite in "${SUITES[@]}"; do
  TOTAL_SUITES=$((TOTAL_SUITES + 1))
  echo "--- $suite ---"
  OUT="$(python3 -m unittest "$suite" 2>&1)"
  EC=$?

  # unittest writes its summary to stderr, which is folded into OUT above.
  RAN=$(printf '%s\n' "$OUT" | sed -n 's/^Ran \([0-9][0-9]*\) test.*/\1/p' | tail -1)
  RAN=${RAN:-0}
  NF=$(printf '%s\n' "$OUT" | sed -n 's/.*failures=\([0-9][0-9]*\).*/\1/p' | tail -1)
  NF=${NF:-0}
  NE=$(printf '%s\n' "$OUT" | sed -n 's/.*errors=\([0-9][0-9]*\).*/\1/p' | tail -1)
  NE=${NE:-0}
  NS=$(printf '%s\n' "$OUT" | sed -n 's/.*skipped=\([0-9][0-9]*\).*/\1/p' | tail -1)
  NS=${NS:-0}

  # A suite that reported zero tests has not passed -- it has failed to run.
  if [ "$RAN" -eq 0 ]; then
    printf '%s\n' "$OUT"
    echo "EXECUTION ERROR (exit code $EC) -- suite produced no test results"
    OVERALL_EXIT=1
    echo ""
    continue
  fi

  if [ "$EC" -ne 0 ]; then
    printf '%s\n' "$OUT"
    echo "NONZERO EXIT ($EC) -- treating as a failure"
    OVERALL_EXIT=1
  fi

  echo "$RAN tests, $NF failures, $NE errors, $NS skipped"
  TOTAL_TESTS=$((TOTAL_TESTS + RAN))
  TOTAL_FAIL=$((TOTAL_FAIL + NF))
  TOTAL_ERROR=$((TOTAL_ERROR + NE))
  TOTAL_SKIP=$((TOTAL_SKIP + NS))
  echo ""
done

echo "================================================================"
echo "SUMMARY (platform suites only)"
echo "  Suites run: $TOTAL_SUITES"
echo "  Tests run:  $TOTAL_TESTS"
echo "  Passed:     $((TOTAL_TESTS - TOTAL_FAIL - TOTAL_ERROR - TOTAL_SKIP))"
echo "  Failures:   $TOTAL_FAIL"
echo "  Errors:     $TOTAL_ERROR"
echo "  Skipped:    $TOTAL_SKIP"
echo ""
echo "NOTE: the canonical repository gate is tests/run_all.sh, which this"
echo "script does not run and does not modify."
echo "================================================================"

exit $OVERALL_EXIT

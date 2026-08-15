#!/usr/bin/env bash
# Regenerates tests/expected_fixture_counts.tsv from an actual run.
# Run this ONLY after deliberately adding or removing fixtures, and read the diff before committing:
# a count that DROPS without you intending it is exactly what the gate exists to catch.
set -uo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT" || exit 1
TMP="$(mktemp)"
sed -n '1,/^# Regenerate with/p' tests/expected_fixture_counts.tsv > "$TMP"
for r in tests/run_*_tests.js; do
  n=$(osascript -l JavaScript "$r" 2>&1 | grep -c '^PASS -- \|^FAIL -- ')
  printf '%s\t%s\n' "$(basename "$r")" "$n" >> "$TMP"
done
mv "$TMP" tests/expected_fixture_counts.tsv
echo "Updated tests/expected_fixture_counts.tsv -- REVIEW THE DIFF before committing."

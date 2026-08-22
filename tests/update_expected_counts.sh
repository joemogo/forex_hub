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

# The Python lane has the same guard, for the same reason -- see
# tests/count_python_tests.py. Regenerated here so the two lanes cannot drift apart
# in whether they are protected at all.
echo ""
echo "Regenerating tests/expected_python_test_counts.tsv ..."
{
  echo "# Expected COLLECTED test count per Python suite. Format: <module><TAB><count>"
  echo "#"
  echo "# The Python analogue of expected_fixture_counts.tsv. run_all.sh gated the Python lane on the"
  echo "# exit code of one unittest call over every module, and counted FILES rather than tests -- so"
  echo "# de-collecting an entire module (test_ -> xtest_) still exited 0, because the sibling modules"
  echo "# kept the total non-zero. Twenty-one rounds of adversarial hardening are stored as these tests."
  echo "#"
  echo "# Regenerate deliberately:  bash tests/update_expected_counts.sh"
  echo "#"
  echo "# MOGO-023: this header used to name 'python3 tests/count_python_tests.py > <this file>'"
  echo "# instead -- and that command emits NO header, so following the file's own instruction"
  echo "# deleted the reason the file exists. It is regenerated from the template in"
  echo "# update_expected_counts.sh, so hand-edits to these comment lines are also discarded;"
  echo "# change the template, not the output."
  python3 tests/count_python_tests.py
} > tests/expected_python_test_counts.tsv
python3 tests/count_python_tests.py --check

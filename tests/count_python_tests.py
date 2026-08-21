#!/usr/bin/env python3
"""Count the tests each Python suite COLLECTS, without running them.

WHY THIS EXISTS
---------------
`tests/run_all.sh` guards the JS lane against silent shrinkage with a per-runner
manifest (`expected_fixture_counts.tsv`), added after a suite quietly ran 36
fixtures instead of 39 and nothing objected. The Python lane had no equivalent:
its only gate was the exit code of ONE `python3 -m unittest` call over all
modules, and its `PY_COUNT` counted FILES, not tests.

So renaming `test_` to `xtest_` across a whole module de-collects every test in
it and the run still exits 0, because the sibling modules keep the total
non-zero. Twenty-one rounds of adversarial hardening are STORED as Python tests
-- they are what kills every mutation -- so the lane holding the entire
accumulated kill record was the one lane with no guard against that record
quietly shrinking. The ruling that silent shrinkage is a failure already existed;
it had only been applied to the other lane.

A test count is not live data, so pinning it is not the corpus-snapshot
anti-pattern CLAUDE.md warns about: it changes only when someone edits a test
file, and then deliberately.

    python3 tests/count_python_tests.py            # print <module><TAB><count>
    python3 tests/count_python_tests.py --check     # exit 1 on any drift
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
EXPECTED = os.path.join(HERE, "expected_python_test_counts.tsv")


def modules():
    found = []
    for dirpath, _dirnames, filenames in os.walk(
            os.path.join(HERE, "trader_intelligence")):
        for name in filenames:
            if name.startswith("test_") and name.endswith(".py"):
                rel = os.path.relpath(os.path.join(dirpath, name), REPO_ROOT)
                found.append(rel[:-3].replace(os.sep, "."))
    return sorted(found)


def count(module):
    """Collected test count, or -1 if the module cannot be loaded.

    A module that fails to import yields a single synthetic `_FailedTest`, which
    would otherwise read as "this suite has 1 test" -- a suite that cannot load
    reporting a plausible-looking number is exactly what this file exists to stop.
    """
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromName(module)
    if getattr(loader, "errors", None):
        return -1
    return suite.countTestCases()


def read_expected():
    rows = {}
    if not os.path.exists(EXPECTED):
        return rows
    with open(EXPECTED, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name, _tab, value = line.partition("\t")
            rows[name.strip()] = int(value.strip())
    return rows


def main(argv):
    sys.path.insert(0, REPO_ROOT)
    found = modules()
    if not found:
        print("FAIL: no Python test modules found -- the enumeration is broken.")
        return 1
    actual = {name: count(name) for name in found}
    if "--check" not in argv:
        for name in found:
            print("%s\t%d" % (name, actual[name]))
        return 0

    expected = read_expected()
    if not expected:
        print("FAIL: %s is missing or empty, so the Python lane has no shrinkage "
              "guard at all." % os.path.basename(EXPECTED))
        return 1
    drift = []
    for name in sorted(set(expected) | set(actual)):
        want, have = expected.get(name), actual.get(name)
        if have == -1:
            drift.append("%s FAILED TO LOAD (it would otherwise report 1 test)"
                         % name)
        elif want is None:
            drift.append("%s is not registered -- a new suite must declare its "
                         "count" % name)
        elif have is None:
            drift.append("%s is registered but no longer exists" % name)
        elif want != have:
            how = "SHORT" if have < want else "LONG"
            drift.append("%s ran %s: expected %d, collected %d" % (name, how, want, have))
    if drift:
        print("Python test collection has DRIFTED:")
        for line in drift:
            print("  " + line)
        print("\nA suite that collects fewer tests than it declares has not passed --")
        print("it has stopped asking. If the change was deliberate, run")
        print("  python3 tests/count_python_tests.py > tests/expected_python_test_counts.tsv")
        print("and review the diff.")
        return 1
    print("Python test collection IN SYNC (%d modules, %d tests)"
          % (len(actual), sum(actual.values())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

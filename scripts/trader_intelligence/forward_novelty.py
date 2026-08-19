#!/usr/bin/env python3
"""Which recovered packages are actually NEW? (MOGO-022)

WHY THIS IS ITS OWN MODULE
--------------------------
This logic lived inside a heredoc in scripts/forward_capture.sh, where nothing
could test it, and it carried two defects that both reached live use:

  1. The whole store was written into every capture file. Recovery reconstructs
     every package in the store, so writing that straight into evidence/
     re-presented already-preserved packages as fresh captures -- breaking the
     invariant that a package appears in exactly ONE capture file.

  2. A DRY RUN left its capture file behind, so the next --write run saw the same
     package staged twice and the importer minted TWO observations for it: same
     sourceContentHash, different observationId.

Both were caught by the corpus test suite rather than by inspection, which is the
argument for moving the logic somewhere it can have its own tests.

THE RULE
--------
A package is new when its contentHash is not already present as an imported
observation's `sourceContentHash` AND is not already staged in a capture file.
Keyed on contentHash, never packageId: the ordinal in a packageId only counts
within one capture run, so packageId is not a global identity, and de-duplicating
on it silently drops real records (measured once: 21 of 25 forward records).

READ-ONLY. Decides; writes nothing.
"""
import argparse
import glob as globmod
import json
import os
import sys

REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
OBSERVATIONS_GLOB = os.path.join(
    REPO_ROOT, "docs", "trader-intelligence", "evidence", "observations", "*.json")
STAGED_GLOB = os.path.join(REPO_ROOT, "evidence", "*-PACKAGES.json")


from import_mogo_observations import is_developer_test_package


class NoveltyRefused(Exception):
    """Raised rather than guessing. A capture run that cannot establish what is
    already preserved must stop, not import."""


def imported_hashes(observations_glob=None):
    """contentHashes already recorded as observations."""
    out = set()
    for path in sorted(globmod.glob(observations_glob or OBSERVATIONS_GLOB)):
        with open(path, "r", encoding="utf-8") as handle:
            record = json.load(handle)
        if record.get("sourceContentHash"):
            out.add(record["sourceContentHash"])
    return out


def staged_hashes(staged_glob=None):
    """contentHashes already sitting in a capture file, awaiting import.

    Counted as known. A leftover capture file otherwise presents the same package
    a second time and a second observation is minted for it.
    """
    out = set()
    for path in sorted(globmod.glob(staged_glob or STAGED_GLOB)):
        with open(path, "r", encoding="utf-8") as handle:
            packages = json.load(handle)
        for package in packages:
            if package.get("contentHash"):
                out.add(package["contentHash"])
    return out


def classify_recovered(recovered, observations_glob=None, staged_glob=None):
    """Split recovered packages into FRESH, PENDING, REFUSED and DONE.

    Four states, and conflating any two of them has now caused a real defect:

      fresh   -- neither imported nor staged. Needs a capture file AND an import.
      pending -- already staged in a capture file but NOT yet an observation.
                 Must NOT be staged again (that mints a duplicate observation),
                 but MUST still be imported.
      refused -- the importer will never accept it on policy grounds, so it can
                 never become an observation. Not work. See below.
      done    -- already an observation. Nothing to do.

    Treating `pending` as simply "known" is what stranded a real forward close: it
    was staged by a run whose import did not complete, and every subsequent run then
    reported "0 new" and skipped the import entirely, so the close sat in
    `evidence/` unimported with nothing left to notice it.

    REFUSED exists because `pending` then acquired the opposite failure (B-31). Four
    developer test trades were staged and the importer refuses them by policy, so they
    could never clear -- every run reported "4 pending" forever. That is worse than
    noise: PENDING is the signal that a real close was stranded, and it only works
    while it reads zero. A permanent floor of 4 means the next stranded close shows up
    as "5 pending" and looks exactly like the steady state.

    The refusal test is imported from the importer rather than restated here, so the
    pipeline and the gate cannot disagree about what a developer trade is.

    Refused packages are excluded from `fresh` as well, not just `pending`: staging one
    would create a capture file that can never import, which is how this state arose in
    the first place. They are returned rather than dropped so the caller can report
    them -- if this predicate is ever wrong, the mistake must be visible rather than a
    real close silently vanishing from capture.
    """
    if recovered is None:
        raise NoveltyRefused("no recovered package list was supplied")
    imported = imported_hashes(observations_glob)
    staged = staged_hashes(staged_glob)
    fresh, pending, refused, seen = [], [], [], set()
    for package in recovered:
        content_hash = package.get("contentHash")
        if not content_hash:
            # Never silently accepted: a package with no hash cannot be shown to
            # be new, and cannot be de-duplicated against anything later.
            raise NoveltyRefused(
                "package %r has no contentHash; refusing to classify it"
                % (package.get("packageId"),))
        if content_hash in imported or content_hash in seen:
            continue
        seen.add(content_hash)           # a duplicate WITHIN one batch is not new either
        if is_developer_test_package(package):
            refused.append(package)
            continue
        if content_hash in staged:
            pending.append(package)
        else:
            fresh.append(package)
    return fresh, pending, refused


def select_new(recovered, observations_glob=None, staged_glob=None):
    """The packages worth WRITING to a new capture file. Order preserved."""
    fresh, _pending, _refused = classify_recovered(recovered, observations_glob, staged_glob)
    return fresh


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("recovered", help="JSON file of recovered packages")
    parser.add_argument("--out", help="write the new packages here (only if any)")
    args = parser.parse_args(argv)

    with open(args.recovered, "r", encoding="utf-8") as handle:
        recovered = json.load(handle)
    try:
        fresh, pending, refused = classify_recovered(recovered)
    except NoveltyRefused as exc:
        print("REFUSED: %s" % exc, file=sys.stderr)
        return 1
    if fresh and args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            json.dump(fresh, handle, indent=2)
            handle.write("\n")
    # Printed as "fresh pending refused". The caller must import when either of the
    # first two is non-zero: pending packages are already staged and would otherwise
    # never be imported. REFUSED must NOT trigger an import -- it is reported so a
    # misclassification is visible, not because there is anything to do about it.
    print("%d %d %d" % (len(fresh), len(pending), len(refused)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

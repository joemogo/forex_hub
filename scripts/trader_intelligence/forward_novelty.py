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
    """Split recovered packages into FRESH, PENDING and DONE.

    Three states, not two, and conflating the middle one caused a real loss:

      fresh   -- neither imported nor staged. Needs a capture file AND an import.
      pending -- already staged in a capture file but NOT yet an observation.
                 Must NOT be staged again (that mints a duplicate observation),
                 but MUST still be imported.
      done    -- already an observation. Nothing to do.

    Treating `pending` as simply "known" is what stranded a real forward close: it
    was staged by a run whose import did not complete, and every subsequent run then
    reported "0 new" and skipped the import entirely, so the close sat in
    `evidence/` unimported with nothing left to notice it.
    """
    if recovered is None:
        raise NoveltyRefused("no recovered package list was supplied")
    imported = imported_hashes(observations_glob)
    staged = staged_hashes(staged_glob)
    fresh, pending, seen = [], [], set()
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
        if content_hash in staged:
            pending.append(package)
        else:
            fresh.append(package)
    return fresh, pending


def select_new(recovered, observations_glob=None, staged_glob=None):
    """The packages worth WRITING to a new capture file. Order preserved."""
    fresh, _pending = classify_recovered(recovered, observations_glob, staged_glob)
    return fresh


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("recovered", help="JSON file of recovered packages")
    parser.add_argument("--out", help="write the new packages here (only if any)")
    args = parser.parse_args(argv)

    with open(args.recovered, "r", encoding="utf-8") as handle:
        recovered = json.load(handle)
    try:
        fresh, pending = classify_recovered(recovered)
    except NoveltyRefused as exc:
        print("REFUSED: %s" % exc, file=sys.stderr)
        return 1
    if fresh and args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            json.dump(fresh, handle, indent=2)
            handle.write("\n")
    # Printed as "fresh pending". The caller must import when EITHER is non-zero:
    # pending packages are already staged and would otherwise never be imported.
    print("%d %d" % (len(fresh), len(pending)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

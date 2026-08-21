#!/usr/bin/env python3
"""MOGO's own append-only record of which trades have existed (B-32.14).

WHY THIS EXISTS

Every corpus-integrity gate before this reduced the corpus to a cardinality plus a
whole-corpus hash pinned in a file the same actor can rewrite. None asked WHICH
trades have existed, so a count-preserving substitution -- delete the losers, pad
with copies of a winner -- was invisible to all of them, and
`research_assimilation --write` would re-bless it on request.

`ledger-preservation/PAPER_LEDGER_PRE_BACKFILL.json` closed that for 35 records and
then froze: the script that wrote it is invoked by nothing, so coverage decayed with
every new trade. Making it continuous by checkpointing Chrome Local Storage was
rejected by the operator -- correctly: unlike IndexedDB's per-origin directories,
Local Storage is one shared store holding 136 origins of personal browsing, and the
existing checkpoint is safe precisely because IndexedDB can be origin-scoped.

WHAT THIS DOES INSTEAD

The identities were already inside MOGO's own IndexedDB origin all along. Every
evidence package carries `sourceTradeId`, and the capture pipeline already extracts
hash-verified packages from the origin-scoped checkpoint. This turns that stream
into a committed, append-only manifest -- so coverage grows with every capture
instead of decaying, MOGO owns the record end to end, and nothing outside its origin
is ever read.

WHY IT IS NOT A NEW SINGLE POINT OF TRUST

Each identity is stored WITH the contentHash of the package it came from, so the
manifest can be checked against the packages rather than believed. It is append-only
and committed, so removing an entry is a diff. And it is derived from the same bytes
the observations are minted from -- not from the observations, which would be
circular.

APPEND-ONLY, AND WHY THAT IS THE POINT

An identity is never removed and never rewritten. A trade that existed cannot stop
having existed, so a shrinking manifest is itself the defect this exists to catch.
Re-running is idempotent: the same packages produce the same manifest.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)

import graph_common as gc          # noqa: E402
from import_mogo_observations import is_developer_test_package as _is_developer  # noqa: E402

SCHEMA_VERSION = "mogo.identity-manifest.v1"

MANIFEST_PATH = os.path.join(REPO_ROOT, "docs", "trader-intelligence", "evidence",
                             "ledger-preservation", "MOGO_IDENTITY_MANIFEST.json")


def load(path=None):
    """The manifest as it stands, or an empty one. Never invents identities."""
    path = path or MANIFEST_PATH
    if not os.path.exists(path):
        return {"schemaVersion": SCHEMA_VERSION, "generated": True, "identities": []}
    with open(path, "r", encoding="utf-8") as handle:
        document = json.load(handle)
    if not isinstance(document, dict):
        raise ValueError("%s is not a JSON object" % path)
    if not isinstance(document.get("identities"), list):
        raise ValueError("%s has no identities list" % path)
    return document


def identities_from_packages(packages):
    """(tradeId, contentHash, captureBasis) for every package that names a trade.

    A package with no `sourceTradeId` is skipped rather than given a synthetic id:
    inventing an identity is the fabrication this whole layer exists to prevent.
    """
    rows = []
    for package in packages or []:
        if not isinstance(package, dict):
            continue
        trade_id = package.get("sourceTradeId")
        if not isinstance(trade_id, str) or not trade_id.strip():
            continue
        rows.append({
            "tradeId": trade_id,
            "contentHash": package.get("contentHash"),
            "captureBasis": package.get("captureBasis"),
            # Recorded HERE, where the whole package is visible, because the
            # importer's refusal test reads three markers -- `isDeveloperTrade`,
            # `tradeSource == "TEST"` and the id prefix -- and a manifest row carries
            # no position object. A validator re-deriving this from the id alone can
            # only ever see one of the three, so a developer trade without the prefix
            # would be required forever and could never be satisfied: the importer
            # refuses it, and the manifest is append-only. The capture step is the
            # only place that can answer this correctly.
            "refusedByImportPolicy": bool(_is_developer(package)),
        })
    return rows


def merge(document, rows):
    """Append-only union. Returns (document, added, conflicts).

    A tradeId already present is NOT overwritten -- the first record of an identity
    is the authoritative one, and a later package claiming the same trade with a
    different contentHash is a CONFLICT to report, not a value to take. Silently
    accepting the newer hash would let a rewritten package launder itself into the
    manifest that is supposed to anchor it.
    """
    existing = {row.get("tradeId"): row for row in document["identities"]
                if isinstance(row, dict) and isinstance(row.get("tradeId"), str)}
    added, conflicts = [], []
    for row in rows:
        trade_id = row["tradeId"]
        previous = existing.get(trade_id)
        if previous is None:
            existing[trade_id] = row
            added.append(trade_id)
            continue
        if (previous.get("contentHash") and row.get("contentHash")
                and previous["contentHash"] != row["contentHash"]):
            conflicts.append({
                "tradeId": trade_id,
                "recordedContentHash": previous["contentHash"],
                "observedContentHash": row["contentHash"],
            })
    document["identities"] = [existing[k] for k in sorted(existing)]
    document["schemaVersion"] = SCHEMA_VERSION
    document["generated"] = True
    return document, added, conflicts


def write(document, path=None):
    """Atomic, so an interrupted write cannot leave a truncated manifest.

    `atomic_write_text` writes a temp file and renames, which is atomic on POSIX --
    a crash mid-write leaves either the old manifest or the new one, never half of
    either. A truncated manifest would read as identities that never existed, which
    is the failure this anchor must not have.
    """
    path = path or MANIFEST_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    gc.atomic_write_text(path, gc.pretty_json(document))
    return path


def update_from_packages(packages, path=None):
    """The whole operation: load, merge append-only, write atomically.

    A conflict does NOT advance the manifest. The first version wrote first and
    reported after, so a run that exited nonzero on a conflict had already committed
    the rest of the batch -- an anchor that moves on the failure path is an anchor
    whose state depends on whether anyone read the exit code.
    """
    document = load(path)
    before = len(document["identities"])
    document, added, conflicts = merge(document, identities_from_packages(packages))
    if conflicts:
        return {"before": before, "after": before, "added": [], "conflicts": conflicts}
    write(document, path)
    return {"before": before, "after": len(document["identities"]),
            "added": added, "conflicts": conflicts}


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--packages", action="append", default=[],
                        help="JSON file of recovered packages (repeatable)")
    parser.add_argument("--manifest", default=None)
    args = parser.parse_args(argv)

    packages = []
    for path in args.packages:
        with open(path, "r", encoding="utf-8") as handle:
            loaded = json.load(handle)
        packages.extend(loaded if isinstance(loaded, list) else loaded.get("packages", []))

    result = update_from_packages(packages, args.manifest)
    print("identity manifest: %d -> %d identities (%d new)"
          % (result["before"], result["after"], len(result["added"])))
    if result["conflicts"]:
        print("CONFLICTS -- a trade already recorded arrived with a different "
              "contentHash; the recorded one is kept:")
        for conflict in result["conflicts"][:5]:
            print("  %s recorded=%s observed=%s"
                  % (conflict["tradeId"], conflict["recordedContentHash"][:12],
                     conflict["observedContentHash"][:12]))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

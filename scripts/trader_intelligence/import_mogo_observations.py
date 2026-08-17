#!/usr/bin/env python3
"""Convert MOGO evidence packages into MOGO-side TradeObservations (MOGO-022).

WHY
---
Human-vs-MOGO decision-difference analysis needs BOTH sides as TradeObservations.
The human side arrives through operator intake. The MOGO side already exists, in a
different shape: the evidence packages under `evidence/*-PACKAGES.json`, each
carrying a `positions[]` and `outcomes[]` record for one decision MOGO actually
made, with `contentHashProvenance: OBSERVED`.

This module does the mapping and nothing else. It is the narrow bridge between a
package (MOGO's operational record) and an observation (the comparable research
record), so the comparison in decision_difference.py has real data on its MOGO side.

WHAT IT REFUSES TO INVENT
-------------------------
Every field is copied from the package or left UNKNOWN. Specifically:

  * A package field that is null becomes an entry in `unknowns`. It is never
    defaulted, and never back-filled from a sibling package or a plausible guess.
  * Nothing is classified INFERRED here. These are MOGO's own recorded values, so
    they are DIRECTLY_OBSERVED or they are unknown -- there is no middle reading to
    make, and offering one would be inventing provenance the package does not carry.
  * A package missing its position or outcome object is SKIPPED with a reason, not
    partially imported. A half-imported decision compares as though it were whole.

DRY RUN BY DEFAULT. Writing 222 records into a corpus is a corpus change; this
prints what it would create and exits unless `--write` is passed explicitly.

NO NETWORK ACCESS ANYWHERE IN THIS MODULE.
"""
import argparse
import datetime
import glob as globmod
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trade_observation as to      # noqa: E402

REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
PACKAGE_GLOB = os.path.join(REPO_ROOT, "evidence", "*-PACKAGES.json")

# package capture basis -> the EvidenceSource sourceType it corresponds to.
CAPTURE_BASIS_SOURCE_TYPE = {
    "REPLAY_RUN": "replay_observation",
    "LIVE_CLOSE": "paper_trade",
}

# TradeObservation field <- (package object, key). Order is the report order.
POSITION_MAP = (
    ("instrument", "instrument"),
    ("timeframe", "timeframe"),
    ("direction", "direction"),
    ("entry", "entryPrice"),
    ("stop", "originalStop"),
    ("target", "target"),
    ("positionSize", "positionSize"),
    ("riskAmount", "riskAmount"),
    ("openedAt", "entryTimestamp"),
    ("accountBalanceBefore", "balanceBefore"),
)
OUTCOME_MAP = (
    ("exitPrice", "exitPrice"),
    ("closedAt", "exitTimestamp"),
    ("outcome", "exitReasonCode"),
)


def _normalize_instrument(value):
    """GBP_USD -> GBP/USD, matching how the human side records an instrument.

    Done here rather than at comparison time: two records that mean the same pair
    must not read as a DATA_DIFFERENCE because one used an underscore.
    """
    if isinstance(value, str) and "_" in value and "/" not in value:
        return value.replace("_", "/")
    return value


def observation_from_package(package, now, counters=None):
    """Map one package to a TradeObservation, or return (None, reason).

    Pure: reads the package, writes nothing. `counters` carries the per-date
    sequence so ids are unique; see _observation_id for why it is not derived
    from the package's own trailing number.
    """
    objects = package.get("objects") or {}
    positions = objects.get("positions") or []
    outcomes = objects.get("outcomes") or []
    if not positions:
        return None, "NO_POSITION_OBJECT"
    if not outcomes:
        return None, "NO_OUTCOME_OBJECT"

    position, outcome = positions[0], outcomes[0]
    fields, classification, unknowns = {}, {}, []

    for target_field, source_key in POSITION_MAP:
        value = position.get(source_key)
        if target_field == "instrument":
            value = _normalize_instrument(value)
        if value is None:
            unknowns.append(target_field)
        else:
            fields[target_field] = value
            classification[target_field] = "DIRECTLY_OBSERVED"

    for target_field, source_key in OUTCOME_MAP:
        value = outcome.get(source_key)
        if value is None:
            unknowns.append(target_field)
        else:
            fields[target_field] = value
            classification[target_field] = "DIRECTLY_OBSERVED"

    if fields.get("instrument") is None:
        return None, "NO_INSTRUMENT"

    identity = package.get("identity") or {}
    basis = package.get("captureBasis")
    source_type = CAPTURE_BASIS_SOURCE_TYPE.get(basis)
    if source_type is None:
        return None, "UNKNOWN_CAPTURE_BASIS|%s" % (basis,)

    record = to.build_observation(
        actor="MOGO",
        sourceId=package.get("packageId"),
        instrument=fields.pop("instrument"),
        fields=fields,
        classification=classification,
        unknowns=unknowns,
        extractedBy="mogo:import_mogo_observations",
        now=now,
        observationId=_observation_id(package, counters),
        strategyId=identity.get("strategyId"),
        sequenceId=package.get("sourceTradeId"),
        notes="captureBasis=%s sourceType=%s" % (basis, source_type),
    )
    return record, None


def _observation_id(package, counters):
    """TOBS|MOGO|<package date>|<per-date sequence>.

    The package's OWN trailing number cannot be used: packageIds look like
    `PKG|alex_g_sr_v1|20260427|1`, and that number restarts per pair, so twelve
    pairs collide on the same date. A first attempt did exactly that and produced
    7 usable records out of 222 -- caught only because the importer refuses a
    duplicate id rather than silently overwriting.

    The sequence is therefore assigned during the walk. Files are globbed sorted
    and packages are read in file order, so a given corpus always produces the
    same ids; but the ids are positional, so re-running after new packages are
    added mid-sequence would renumber later records. Import is consequently a
    one-shot operation, and `write_observation` refuses to overwrite an existing
    record, so a second run reports refusals rather than silently reshuffling
    what is already recorded.
    """
    date = (package.get("createdAt") or "")[:10].replace("-", "") or "00000000"
    if counters is None:
        counters = {}
    counters[date] = counters.get(date, 0) + 1
    return "TOBS|MOGO|%s|%03d" % (date, counters[date])


def convert_all(package_glob=None, now=None):
    """Read every package file and map it. Writes nothing."""
    now = now or datetime.datetime(2026, 1, 1)
    records, skipped, seen = [], [], set()
    counters = {}
    for path in sorted(globmod.glob(package_glob or PACKAGE_GLOB)):
        with open(path, "r", encoding="utf-8") as handle:
            packages = json.load(handle)
        for package in packages:
            record, reason = observation_from_package(package, now, counters)
            if record is None:
                skipped.append({"file": os.path.basename(path),
                                "packageId": package.get("packageId"),
                                "reason": reason})
                continue
            if record["observationId"] in seen:
                skipped.append({"file": os.path.basename(path),
                                "packageId": package.get("packageId"),
                                "reason": "DUPLICATE_OBSERVATION_ID|%s"
                                          % record["observationId"]})
                continue
            seen.add(record["observationId"])
            records.append(record)
    return records, skipped


def report(records, skipped):
    """A summary that states what was NOT imported as prominently as what was."""
    by_basis, unknown_counts = {}, {}
    for record in records:
        basis = (record.get("notes") or "").split(" ")[0]
        by_basis[basis] = by_basis.get(basis, 0) + 1
        for field in record.get("unknowns") or []:
            unknown_counts[field] = unknown_counts.get(field, 0) + 1
    reasons = {}
    for entry in skipped:
        key = entry["reason"].split("|")[0]
        reasons[key] = reasons.get(key, 0) + 1
    return {
        "converted": len(records),
        "skipped": len(skipped),
        "byCaptureBasis": by_basis,
        "skipReasons": reasons,
        "unknownFieldCounts": unknown_counts,
        "wrote": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--write", action="store_true",
                        help="actually write the observations (default: dry run)")
    parser.add_argument("--json", action="store_true", help="machine-readable report")
    args = parser.parse_args(argv)

    records, skipped = convert_all(now=datetime.datetime.now(datetime.timezone.utc))
    summary = report(records, skipped)

    if args.write:
        written = 0
        for record in records:
            try:
                to.write_observation(record)
                written += 1
            except to.ObservationRefused as exc:
                skipped.append({"packageId": record.get("sourceId"),
                                "reason": "REFUSED_ON_WRITE|%s" % (exc,)})
        summary = report(records, skipped)
        summary["wrote"] = True
        summary["written"] = written

    print(json.dumps(summary, indent=2, sort_keys=True) if args.json
          else _human(summary))
    return 0


def _human(summary):
    lines = ["MOGO observation import -- %s"
             % ("WROTE RECORDS" if summary["wrote"] else "DRY RUN, nothing written")]
    lines.append("  convertible: %d" % summary["converted"])
    lines.append("  skipped:     %d" % summary["skipped"])
    for key, count in sorted(summary["byCaptureBasis"].items()):
        lines.append("    %s: %d" % (key, count))
    if summary["skipReasons"]:
        lines.append("  skip reasons:")
        for key, count in sorted(summary["skipReasons"].items()):
            lines.append("    %s: %d" % (key, count))
    if summary["unknownFieldCounts"]:
        lines.append("  fields recorded UNKNOWN (not defaulted):")
        for key, count in sorted(summary["unknownFieldCounts"].items(),
                                 key=lambda kv: (-kv[1], kv[0])):
            lines.append("    %s: %d" % (key, count))
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())

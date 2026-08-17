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
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trade_observation as to      # noqa: E402
import evidence_common as ec        # noqa: E402
import graph_common as gc           # noqa: E402

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


_FAMILY_GLOB = os.path.join(REPO_ROOT, "docs", "trader-intelligence", "traders",
                            "*", "strategy-families", "*.json")


def registered_families():
    """The StrategyFamily ids that actually exist, read from the same location the
    graph builder reads (traders/*/strategy-families/*.json)."""
    out = set()
    for path in sorted(globmod.glob(_FAMILY_GLOB)):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                out.add(json.load(handle).get("strategyFamilyId"))
        except (ValueError, OSError):
            continue
    return {f for f in out if f}


def _file_content_hash(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def build_sources(now, package_glob=None):
    """One EvidenceSource per (package file, captureBasis). Returns a dict.

    Per FILE and captureBasis, not per file alone: C1-01-GBP_USD-PACKAGES.json holds
    24 REPLAY_RUN packages AND the single LIVE_CLOSE, so a file-level sourceType
    would mislabel the one record that is genuinely forward evidence.

    Not per PACKAGE either: 222 sources for 11 artifacts would bury the distinction
    in noise without making provenance any more exact, because each observation
    already carries its own `sourcePackageId`.

    Writes nothing. The caller decides whether these are persisted.
    """
    sources, seq = {}, {}
    for path in sorted(globmod.glob(package_glob or PACKAGE_GLOB)):
        with open(path, "r", encoding="utf-8") as handle:
            packages = json.load(handle)
        content_hash = _file_content_hash(path)
        rel = os.path.relpath(path, REPO_ROOT)
        for basis in sorted({p.get("captureBasis") for p in packages}):
            source_type = CAPTURE_BASIS_SOURCE_TYPE.get(basis)
            if source_type is None:
                continue
            date_str = now.strftime("%Y%m%d")
            seq[date_str] = seq.get(date_str, 0) + 1
            source_id = "EVSRC|MOGO|%s|%03d" % (date_str, seq[date_str])
            stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
            # Derived from the packages in THIS group, never assumed. The single
            # LIVE_CLOSE package is `current_strategy`, not `alex_g_sr_v1`, so a
            # hardcoded family would have attached a fabricated attribute to the
            # one genuinely forward source in the corpus. Mixed group -> None,
            # because there is no single honest answer.
            families = {(p.get("identity") or {}).get("strategyId")
                        for p in packages if p.get("captureBasis") == basis}
            raw_family = families.pop() if len(families) == 1 else None
            # ...and only ASSERTED when a StrategyFamily is actually registered.
            # `alex_g_sr_v1` resolves; `current_strategy` does not, and claiming it
            # produced a dangling BELONGS_TO_STRATEGY_FAMILY edge that the graph
            # build reported as INVALID_STRATEGY_FAMILY_REFERENCE. The raw value is
            # kept in metadata, where it is descriptive rather than a reference, so
            # nothing is lost and nothing is fabricated.
            family = raw_family if raw_family in registered_families() else None
            sources[(rel, basis)] = {
                "sourceId": source_id,
                # THE distinction, in existing vocabulary. replay_observation vs
                # paper_trade is what separates historical from forward evidence.
                "sourceType": source_type,
                "traderId": None,
                "strategyFamilyId": family,
                "title": "%s (%s)" % (os.path.basename(rel), basis),
                "registeredAt": stamp,
                "acquiredAt": None,
                "storageLocationType": "repository",
                "repositoryPath": rel,
                "contentHash": content_hash,
                "contentHashAlgorithm": "sha256",
                "canonicalReference": None,
                "externalReference": None,
                "externalAssetReference": None,
                "language": None,
                "licensingStatus": "owned",
                "provenanceStatus": "verified",
                "lifecycleStatus": "registered",
                "metadata": {
                    "captureBasis": basis,
                    # Descriptive, NOT a reference: the engine's own strategy id as
                    # recorded in the packages, retained even when no StrategyFamily
                    # is registered for it.
                    "engineStrategyId": raw_family,
                    "packageCount": sum(1 for p in packages
                                        if p.get("captureBasis") == basis),
                    "importedBy": "import_mogo_observations",
                },
                "schemaVersion": ec.SCHEMA_VERSION,
                "createdAt": stamp,
                "updatedAt": stamp,
            }
    return sources


def _normalize_instrument(value):
    """GBP_USD -> GBP/USD, matching how the human side records an instrument.

    Done here rather than at comparison time: two records that mean the same pair
    must not read as a DATA_DIFFERENCE because one used an underscore.
    """
    if isinstance(value, str) and "_" in value and "/" not in value:
        return value.replace("_", "/")
    return value


def observation_from_package(package, now, counters=None, source=None):
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
    if source is None:
        return None, "NO_REGISTERED_SOURCE|%s" % (basis,)

    record = to.build_observation(
        actor="MOGO",
        sourceId=source["sourceId"],
        instrument=fields.pop("instrument"),
        fields=fields,
        classification=classification,
        unknowns=unknowns,
        extractedBy="mogo:import_mogo_observations",
        now=now,
        observationId=_observation_id(package, counters),
        strategyId=identity.get("strategyId"),
        sequenceId=package.get("sourceTradeId"),
        # Exact artifact provenance: sourceId names the registered EvidenceSource,
        # sourcePackageId names the individual package inside it.
        sourcePackageId=package.get("packageId"),
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
    """Read every package file and map it. Writes nothing.

    Returns (records, skipped, sources).
    """
    now = now or datetime.datetime(2026, 1, 1)
    sources = build_sources(now, package_glob)
    records, skipped, seen = [], [], set()
    counters = {}
    for path in sorted(globmod.glob(package_glob or PACKAGE_GLOB)):
        rel = os.path.relpath(path, REPO_ROOT)
        with open(path, "r", encoding="utf-8") as handle:
            packages = json.load(handle)
        for package in packages:
            source = sources.get((rel, package.get("captureBasis")))
            record, reason = observation_from_package(package, now, counters, source)
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
    return records, skipped, sources


def source_map(sources):
    """sourceId -> EvidenceSource, the shape trade_observation's population
    functions consume."""
    return {src["sourceId"]: src for src in (sources or {}).values()}


def report(records, skipped, sources):
    """A summary that states what was NOT imported as prominently as what was.

    Grouped by EVIDENCE POPULATION, derived from each record's source, never by a
    label on the record itself. `sources` is required for the same reason
    trade_observation.summarize() requires it: a count that does not separate
    replay from forward is the number that misleads.
    """
    smap = source_map(sources)
    by_population, unknown_counts = {}, {}
    for record in records:
        population = to.observation_population(record, smap)
        by_population[population] = by_population.get(population, 0) + 1
        for field in record.get("unknowns") or []:
            unknown_counts[field] = unknown_counts.get(field, 0) + 1
    reasons = {}
    for entry in skipped:
        key = entry["reason"].split("|")[0]
        reasons[key] = reasons.get(key, 0) + 1
    return {
        "converted": len(records),
        "skipped": len(skipped),
        "sourcesRegistered": len(smap),
        "byPopulation": by_population,
        "bySourceType": {src["sourceId"]: src["sourceType"]
                         for src in smap.values()},
        "skipReasons": reasons,
        "unknownFieldCounts": unknown_counts,
        "wrote": False,
    }


def write_sources(sources, sources_dir=None):
    """Persist the EvidenceSources. Refuses to overwrite an existing one."""
    target_dir = sources_dir or os.path.join(to.EVIDENCE_ROOT, "sources")
    os.makedirs(target_dir, exist_ok=True)
    written = []
    for source in sorted(sources.values(), key=lambda s: s["sourceId"]):
        path = os.path.join(target_dir,
                            ec.source_id_to_filename(source["sourceId"]))
        if os.path.exists(path):
            raise to.ObservationRefused(
                "%s already exists; refusing to overwrite a registered source." % path)
        gc.atomic_write_text(path, gc.pretty_json(source))
        written.append(source["sourceId"])
    return written


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--write", action="store_true",
                        help="actually write the sources and observations "
                             "(default: dry run)")
    parser.add_argument("--json", action="store_true", help="machine-readable report")
    args = parser.parse_args(argv)

    records, skipped, sources = convert_all(
        now=datetime.datetime.now(datetime.timezone.utc))
    summary = report(records, skipped, sources)

    if args.write:
        summary["sourcesWritten"] = write_sources(sources)
        written = 0
        for record in records:
            try:
                to.write_observation(record)
                written += 1
            except to.ObservationRefused as exc:
                skipped.append({"packageId": record.get("sourcePackageId"),
                                "reason": "REFUSED_ON_WRITE|%s" % (exc,)})
        summary = dict(report(records, skipped, sources),
                       sourcesWritten=summary["sourcesWritten"],
                       wrote=True, written=written)

    print(json.dumps(summary, indent=2, sort_keys=True) if args.json
          else _human(summary))
    return 0


def _human(summary):
    lines = ["MOGO observation import -- %s"
             % ("WROTE RECORDS" if summary["wrote"] else "DRY RUN, nothing written")]
    lines.append("  convertible: %d" % summary["converted"])
    lines.append("  skipped:     %d" % summary["skipped"])
    lines.append("  sources registered: %d" % summary["sourcesRegistered"])
    lines.append("  by evidence population (derived from source provenance):")
    for key, count in sorted(summary["byPopulation"].items()):
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

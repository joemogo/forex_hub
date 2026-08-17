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
    # Realized performance. `pnl` is present on exactly the 26 LIVE_CLOSE packages
    # and absent from all 221 REPLAY_RUN ones -- a replay produces no realized P&L,
    # so it becomes an explicit UNKNOWN there rather than a zero.
    ("pnl", "pnl"),
    ("accountBalanceAfter", "balanceAfter"),
    # `realizedR` carries realizedRProvenance OBSERVED_FROM_EXIT on all 247, so it
    # is recorded as DIRECTLY_OBSERVED. `plannedR` is the intent, not the result,
    # and is deliberately NOT mapped here.
    ("rMultiple", "realizedR"),
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
        # The GLOBAL key. See already_imported() for why the package id is not one.
        sourceContentHash=package.get("contentHash"),
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


def already_imported(observations_dir=None):
    """sourcePackageId -> observationId, for packages already recorded.

    Import must be repeatable: a forward close mints a new package, and that
    package has to reach the observation corpus without disturbing the records
    already there. Keying on the artifact -- not on position in a walk -- is what
    makes a re-run additive instead of a renumbering.

    Keyed on contentHash, NOT packageId. A packageId is
    `PKG|<strategy>|<date>|<ordinal>` and the ordinal only counts within one capture
    run, so it is not a global primary key: 21 of the 25 forward LIVE_CLOSE packages
    share a packageId with an unrelated REPLAY_RUN package already imported. Keyed on
    packageId this function would have reported those 21 as already-imported and
    silently dropped exactly the forward evidence it exists to preserve. contentHash
    is unique across all 247 artifacts.
    """
    existing = to.load_observations(observations_dir)
    return {r["sourceContentHash"]: r["observationId"]
            for r in existing.values() if r.get("sourceContentHash")}


def backfill_content_hashes(observations_dir=None, sources_dir=None, write=False):
    """Add `sourceContentHash` to observations recorded before it existed.

    STRICTLY ADDITIVE. The observationId, every recorded value, every
    classification and every unknown is left exactly as written; the only change is
    the addition of one provenance field that was missing. Any record where the
    hash cannot be resolved UNAMBIGUOUSLY is left untouched and reported, never
    guessed -- a wrong hash here would silently merge two distinct decisions.

    Resolution goes through the observation's OWN source, not a global packageId
    search: sourceId -> source.repositoryPath -> that file's packages -> packageId.
    A global search would now be ambiguous for the 21 package ids that a forward
    LIVE_CLOSE package shares with an unrelated REPLAY_RUN one. Within a single
    file, package ids are unique (verified across all 12 files).
    """
    observations = to.load_observations(observations_dir)
    sources = to.load_sources(sources_dir)
    by_file = {}
    updated, unresolved = [], []

    for observation_id in sorted(observations):
        record = observations[observation_id]
        if record.get("sourceContentHash"):
            continue
        source = sources.get(record.get("sourceId"))
        package_id = record.get("sourcePackageId")
        if source is None or not package_id:
            unresolved.append({"observationId": observation_id,
                               "reason": "NO_SOURCE_OR_PACKAGE_ID"})
            continue
        rel = source.get("repositoryPath")
        if rel not in by_file:
            path = os.path.join(REPO_ROOT, rel) if rel else None
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    by_file[rel] = json.load(handle)
            except (OSError, ValueError, TypeError):
                by_file[rel] = None
        packages = by_file.get(rel)
        if packages is None:
            unresolved.append({"observationId": observation_id,
                               "reason": "SOURCE_ARTIFACT_UNREADABLE|%s" % (rel,)})
            continue
        matches = [p for p in packages if p.get("packageId") == package_id]
        if len(matches) != 1 or not matches[0].get("contentHash"):
            unresolved.append({
                "observationId": observation_id,
                "reason": "AMBIGUOUS_OR_MISSING_HASH|%d match(es)" % len(matches)})
            continue
        updated.append((observation_id, matches[0]["contentHash"]))

    if write:
        target_dir = observations_dir or to.OBSERVATIONS_DIR
        for observation_id, content_hash in updated:
            record = observations[observation_id]
            before = dict(record)
            record["sourceContentHash"] = content_hash
            # Prove additivity rather than trusting it: everything except the one
            # new key must be identical to what was on disk.
            if {k: v for k, v in record.items() if k != "sourceContentHash"} != before:
                raise to.ObservationRefused(
                    "backfill would change more than sourceContentHash on %s"
                    % observation_id)
            to.validate_observation(record)
            path = os.path.join(
                target_dir, ec.observation_id_to_filename(observation_id))
            gc.atomic_write_text(path, gc.pretty_json(record))

    return {"resolved": len(updated), "unresolved": unresolved, "wrote": bool(write)}


def backfill_mapped_fields(observations_dir=None, sources_dir=None, write=False):
    """Add fields the mapping gained after a record was written.

    STRICTLY WIDENING. An existing key's value is never changed and nothing is ever
    removed: the only permitted edits are adding a mapped field that was absent, and
    APPENDING to `unknowns`. Both are proven per record before anything is written,
    not asserted in a comment.

    Needed because OUTCOME_MAP gained pnl / accountBalanceAfter / rMultiple after the
    247 records were imported. Without this, forward-performance analysis would have
    to re-derive P&L from prices -- turning an observed quantity into an inferred
    one, which is the conversion this whole subsystem exists to prevent.
    """
    observations = to.load_observations(observations_dir)
    sources = to.load_sources(sources_dir)
    by_file, updated, unresolved = {}, [], []

    for observation_id in sorted(observations):
        record = observations[observation_id]
        source = sources.get(record.get("sourceId"))
        package_id = record.get("sourcePackageId")
        content_hash = record.get("sourceContentHash")
        if source is None or not package_id:
            unresolved.append({"observationId": observation_id,
                               "reason": "NO_SOURCE_OR_PACKAGE_ID"})
            continue
        rel = source.get("repositoryPath")
        if rel not in by_file:
            try:
                with open(os.path.join(REPO_ROOT, rel), "r", encoding="utf-8") as h:
                    by_file[rel] = json.load(h)
            except (OSError, ValueError, TypeError):
                by_file[rel] = None
        packages = by_file.get(rel)
        if packages is None:
            unresolved.append({"observationId": observation_id,
                               "reason": "SOURCE_ARTIFACT_UNREADABLE|%s" % (rel,)})
            continue
        # Match on contentHash where we have it -- the package id is not unique.
        matches = [p for p in packages
                   if (p.get("contentHash") == content_hash if content_hash
                       else p.get("packageId") == package_id)]
        if len(matches) != 1:
            unresolved.append({"observationId": observation_id,
                               "reason": "AMBIGUOUS|%d" % len(matches)})
            continue
        package = matches[0]
        outcome = (package.get("objects") or {}).get("outcomes") or [{}]
        additions, new_unknowns = {}, []
        for field, key in OUTCOME_MAP:
            if field in record or field in (record.get("unknowns") or []):
                continue
            value = outcome[0].get(key)
            if value is None:
                new_unknowns.append(field)
            else:
                additions[field] = value
        if not additions and not new_unknowns:
            continue
        updated.append((observation_id, additions, new_unknowns))

    if write:
        target_dir = observations_dir or to.OBSERVATIONS_DIR
        for observation_id, additions, new_unknowns in updated:
            record = observations[observation_id]
            before = json.loads(json.dumps(record))
            for field, value in additions.items():
                record[field] = value
                record["fieldClassification"][field] = "DIRECTLY_OBSERVED"
            record["unknowns"] = sorted(set(record.get("unknowns") or [])
                                        | set(new_unknowns))
            _assert_widening_only(observation_id, before, record)
            to.validate_observation(record)
            gc.atomic_write_text(
                os.path.join(target_dir,
                             ec.observation_id_to_filename(observation_id)),
                gc.pretty_json(record))

    return {"updated": len(updated), "unresolved": unresolved, "wrote": bool(write)}


def _assert_widening_only(observation_id, before, after):
    """No existing value changed; nothing removed; `unknowns` only grew."""
    for key, value in before.items():
        if key in ("unknowns", "fieldClassification"):
            continue
        if key not in after or after[key] != value:
            raise to.ObservationRefused(
                "backfill would change %r on %s" % (key, observation_id))
    if not set(before.get("unknowns") or []) <= set(after.get("unknowns") or []):
        raise to.ObservationRefused(
            "backfill would remove an unknown from %s" % observation_id)
    old_class = before.get("fieldClassification") or {}
    new_class = after.get("fieldClassification") or {}
    for field, how in old_class.items():
        if new_class.get(field) != how:
            raise to.ObservationRefused(
                "backfill would change the classification of %r on %s"
                % (field, observation_id))


def convert_all(package_glob=None, now=None, skip_imported=True,
                observations_dir=None):
    """Read every package file and map it. Writes nothing.

    Returns (records, skipped, sources).
    """
    now = now or datetime.datetime(2026, 1, 1)
    sources = build_sources(now, package_glob)
    records, skipped, seen = [], [], set()
    imported = already_imported(observations_dir) if skip_imported else {}
    # Continue each date's sequence from what is already recorded, so a second run
    # appends rather than colliding with -- or renumbering -- existing records.
    counters = {}
    for observation_id in imported.values():
        parts = observation_id.split("|")
        if len(parts) == 4 and parts[3].isdigit():
            counters[parts[2]] = max(counters.get(parts[2], 0), int(parts[3]))
    for path in sorted(globmod.glob(package_glob or PACKAGE_GLOB)):
        rel = os.path.relpath(path, REPO_ROOT)
        with open(path, "r", encoding="utf-8") as handle:
            packages = json.load(handle)
        for package in packages:
            if package.get("contentHash") in imported:
                continue          # already recorded; never re-minted, never rewritten
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
    """Persist the EvidenceSources. Never overwrites an existing one.

    An already-registered source is left exactly as it is and reported as reused.
    Rewriting it would change registeredAt/contentHash on a record other
    observations already point at -- a silent mutation of preserved evidence.
    """
    target_dir = sources_dir or os.path.join(to.EVIDENCE_ROOT, "sources")
    os.makedirs(target_dir, exist_ok=True)
    written, reused = [], []
    for source in sorted(sources.values(), key=lambda s: s["sourceId"]):
        path = os.path.join(target_dir,
                            ec.source_id_to_filename(source["sourceId"]))
        if os.path.exists(path):
            # Source ids are assigned by position in a sorted glob, so adding a file
            # that sorts EARLIER would shift every later id by one and quietly make
            # this "reuse" point at a different artifact than the one it describes.
            # Verify identity before reusing; refuse loudly rather than mismatch.
            with open(path, "r", encoding="utf-8") as handle:
                existing = json.load(handle)
            same = (existing.get("repositoryPath") == source["repositoryPath"]
                    and existing.get("sourceType") == source["sourceType"]
                    and existing.get("contentHash") == source["contentHash"])
            if not same:
                raise to.ObservationRefused(
                    "%s already exists but describes a different artifact "
                    "(recorded %s/%s, would now be %s/%s). Source ids are positional; "
                    "a file added earlier in sort order has shifted them. Refusing "
                    "rather than repointing a source that observations already cite."
                    % (source["sourceId"], existing.get("repositoryPath"),
                       existing.get("sourceType"), source["repositoryPath"],
                       source["sourceType"]))
            reused.append(source["sourceId"])
            continue
        gc.atomic_write_text(path, gc.pretty_json(source))
        written.append(source["sourceId"])
    return {"written": written, "reused": reused}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--write", action="store_true",
                        help="actually write the sources and observations "
                             "(default: dry run)")
    parser.add_argument("--json", action="store_true", help="machine-readable report")
    parser.add_argument("--backfill-content-hashes", action="store_true",
                        help="add sourceContentHash to records written before that "
                             "field existed (additive only; combine with --write)")
    parser.add_argument("--backfill-mapped-fields", action="store_true",
                        help="add fields the mapping gained after import "
                             "(widening only; combine with --write)")
    args = parser.parse_args(argv)

    if args.backfill_mapped_fields:
        result = backfill_mapped_fields(write=args.write)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    if args.backfill_content_hashes:
        result = backfill_content_hashes(write=args.write)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    records, skipped, sources = convert_all(
        now=datetime.datetime.now(datetime.timezone.utc))
    summary = report(records, skipped, sources)

    if args.write:
        summary["sources"] = write_sources(sources)
        written = 0
        for record in records:
            try:
                to.write_observation(record)
                written += 1
            except to.ObservationRefused as exc:
                skipped.append({"packageId": record.get("sourcePackageId"),
                                "reason": "REFUSED_ON_WRITE|%s" % (exc,)})
        summary = dict(report(records, skipped, sources),
                       sources=summary["sources"], wrote=True, written=written)

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

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
import re
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
    # Minted by the app's own backfill from the account journal, long after the
    # close, because no package was captured at the time (B-22). It maps to a
    # DISTINCT sourceType so it derives the RECONSTRUCTED population -- never
    # `paper_trade`, which would file a MINIMAL/UNSAFE_TO_RECONSTRUCT record
    # alongside live-captured ones and retroactively weaken all of them.
    "HISTORICAL_BACKFILL": "journal_entry",
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
    # THE TRUE MARKET EXIT, which the corpus was discarding. `exitTimestamp` is the
    # moment the close was RECORDED; for an exit reconstructed from candles that is
    # when the re-walk noticed it. Every package in the store carries
    # exitDetectionSource `historical_candle`, and on 6 of 29 the recorded exit is
    # more than an hour after the true one -- worst case 351.8 hours, which turned a
    # 216.1h holding period into an apparent 567.9h. Nothing is inferred here: the
    # candle boundary is stated by the package, in epoch milliseconds, and only the
    # unit is converted.
    ("marketExitAt", "exitCandleEnd"),
    ("exitDetectionSource", "exitDetectionSource"),
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


SOURCE_ID_RE = re.compile(r"^EVSRC\|([A-Z0-9_]+)\|(\d{8})\|(\d{3,})$")


def _source_id_rank(source_id, cited_ids):
    """Rank for choosing between several records describing ONE artifact.

    Lower sorts first. Three deliberate components, each fixing a real defect:

      * A CITED id always wins. The whole point of the migration is that no
        observation's citation moves, so an id some observation already points at
        outranks any other by construction.
      * The scope is compared explicitly, and a foreign scope loses. A raw string
        minimum silently preferred any other trader's record, because
        "EVSRC|ALEX_G|..." < "EVSRC|MOGO|...".
      * The sequence is compared NUMERICALLY. A raw string minimum picked |1000
        over |999, so the comment claiming "first writer wins" became false the
        moment a sequence reached four digits.
    """
    match = SOURCE_ID_RE.match(source_id or "")
    if not match:
        # Unparseable ids sort last rather than being dropped: they are still real
        # records, and discarding one silently would hide it.
        return (1, 1, "", 0, source_id or "")
    scope, date_str, seq = match.group(1), match.group(2), int(match.group(3))
    return (0 if source_id in cited_ids else 1,
            0 if scope == "MOGO" else 1,
            date_str, seq, source_id)


def observation_cited_source_ids(observations_dir=None):
    """Every sourceId that a recorded observation actually points at."""
    target = observations_dir or os.path.join(to.EVIDENCE_ROOT, "observations")
    out = set()
    for path in globmod.glob(os.path.join(target, "*.json")):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                record = json.load(handle)
        except (OSError, ValueError):
            continue
        if record.get("sourceId"):
            out.add(record["sourceId"])
    return out


def existing_sources_by_artifact(sources_dir=None, observations_dir=None):
    """Recorded sources, keyed by the ARTIFACT they describe.

    The key is (repositoryPath, sourceType, contentHash) -- exactly the triple
    write_sources already verifies before reusing an id. Reading it back here is
    what lets an id follow its artifact instead of its position.

    `contentHash` is load-bearing in that key, not decoration: without it, a file
    whose CONTENT changes while its path stays the same would be handed the old
    id, write_sources would refuse, and the import would be blocked -- which is
    B-27's own failure mode returning by a different route.
    """
    target = sources_dir or os.path.join(to.EVIDENCE_ROOT, "sources")
    cited = observation_cited_source_ids(observations_dir)
    out = {}
    for path in sorted(globmod.glob(os.path.join(target, "*.json"))):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                record = json.load(handle)
        except (OSError, ValueError):
            continue
        key = (record.get("repositoryPath"), record.get("sourceType"),
               record.get("contentHash"))
        source_id = record.get("sourceId")
        if not all(k is not None for k in key) or not source_id:
            continue
        if key not in out or _source_id_rank(source_id, cited) < _source_id_rank(out[key], cited):
            out[key] = source_id
    return out


def _highest_recorded_seq(sources_dir, date_str):
    """The largest sequence already used on `date_str`, across recorded sources."""
    target = sources_dir or os.path.join(to.EVIDENCE_ROOT, "sources")
    pattern = re.compile(r"^EVSRC_[A-Z0-9_]+_%s_(\d{3,})$" % re.escape(date_str))
    highest = 0
    for path in globmod.glob(os.path.join(target, "*.json")):
        match = pattern.match(os.path.splitext(os.path.basename(path))[0])
        if match:
            highest = max(highest, int(match.group(1)))
    return highest


def build_sources(now, package_glob=None, sources_dir=None, observations_dir=None):
    """One EvidenceSource per (package file, captureBasis). Returns a dict.

    Per FILE and captureBasis, not per file alone: C1-01-GBP_USD-PACKAGES.json holds
    24 REPLAY_RUN packages AND the single LIVE_CLOSE, so a file-level sourceType
    would mislabel the one record that is genuinely forward evidence.

    Not per PACKAGE either: 222 sources for 11 artifacts would bury the distinction
    in noise without making provenance any more exact, because each observation
    already carries its own `sourcePackageId`.

    Writes nothing. The caller decides whether these are persisted.
    """
    # B-27. Ids used to be assigned by POSITION in the sorted glob, so inserting or
    # deleting any capture file shifted every id after it -- write_sources then
    # correctly refused to repoint a source that observations already cite, and the
    # whole import was blocked until the file layout was restored. That happened
    # twice in one session, from removing a duplicate artifact and from restoring it.
    #
    # An id now follows its ARTIFACT. A source already recorded for this exact
    # (path, type, contentHash) keeps the id it was given, whatever scheme minted
    # it, so no existing record changes and no observation's citation moves. Only a
    # genuinely new artifact is allocated an id, and it takes the next sequence not
    # already used that day rather than a positional one.
    recorded = existing_sources_by_artifact(sources_dir, observations_dir)
    date_str = now.strftime("%Y%m%d")
    next_seq = _highest_recorded_seq(sources_dir, date_str) + 1
    sources = {}
    for path in sorted(globmod.glob(package_glob or PACKAGE_GLOB)):
        with open(path, "r", encoding="utf-8") as handle:
            packages = json.load(handle)
        content_hash = _file_content_hash(path)
        rel = os.path.relpath(path, REPO_ROOT)
        for basis in sorted({p.get("captureBasis") for p in packages}):
            source_type = CAPTURE_BASIS_SOURCE_TYPE.get(basis)
            if source_type is None:
                continue
            source_id = recorded.get((rel, source_type, content_hash))
            if source_id is None:
                source_id = "EVSRC|MOGO|%s|%03d" % (date_str, next_seq)
                next_seq += 1
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


def map_outcome_value(field, value):
    """The single place an OUTCOME_MAP value is transformed.

    Both the conversion path and the widening-backfill path read the same package
    field, and until this existed only the conversion path applied the epoch->ISO
    transformation -- so the backfill wrote raw milliseconds into `marketExitAt`
    for 258 records. Two mapping paths with one transformation between them is the
    defect; this removes the second path's ability to diverge.
    """
    if field == "marketExitAt":
        return _epoch_ms_to_iso(value)
    return value


def _epoch_ms_to_iso(value):
    """Epoch milliseconds -> ISO-8601 Z. A unit conversion, not an inference.

    Returns None (which becomes an explicit UNKNOWN) for anything that is not a
    number, rather than guessing.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return (datetime.datetime.fromtimestamp(value / 1000.0, datetime.timezone.utc)
            .strftime("%Y-%m-%dT%H:%M:%S.") + "%03dZ" % (int(value) % 1000))


def _normalize_instrument(value):
    """GBP_USD -> GBP/USD, matching how the human side records an instrument.

    Done here rather than at comparison time: two records that mean the same pair
    must not read as a DATA_DIFFERENCE because one used an underscore.
    """
    if isinstance(value, str) and "_" in value and "/" not in value:
        return value.replace("_", "/")
    return value


def is_developer_test_package(package):
    """Is this package a Developer Mode test trade rather than an observation?

    THE AUTHORITATIVE definition, deliberately singular. It lives here because this
    is the module that refuses such a package, but the capture pipeline needs the
    same answer for a different reason: a package refused on policy will never
    become an observation, so counting it as work "awaiting import" makes it
    pending forever (B-31). Two copies of this test would drift, and the direction
    of drift that matters -- the pipeline believing a developer trade is importable
    -- is the one nobody would notice.

    Three independent markers, per the reasoning at the call site: any one may be
    absent on an older record.
    """
    positions = (package.get("objects") or {}).get("positions") or []
    position = positions[0] if positions else {}
    trade_id = str(package.get("sourceTradeId") or "")
    return bool(position.get("isDeveloperTrade")
                or position.get("tradeSource") == "TEST"
                or trade_id.startswith("AGT|TEST|"))


def observation_from_package(package, now, counters=None, source=None):
    """Map one package to a TradeObservation, or return (None, reason).

    Pure: reads the package, writes nothing. `counters` carries the per-date
    sequence so ids are unique; see _observation_id for why it is not derived
    from the package's own trailing number.
    """
    objects = package.get("objects") or {}
    positions = objects.get("positions") or []
    outcomes = objects.get("outcomes") or []
    # EXACTLY ONE, or skip. A package carrying two positions minted one record from
    # `positions[0]` with no skip entry and no report line -- a silent partial
    # import, contradicting this module's own contract that a package missing its
    # position or outcome is SKIPPED with a reason. It also disagrees with the
    # witness, which treats a list that is not exactly one entry as unreadable
    # (`_witness_value`), so the record it minted could never be checked anyway.
    if len(positions) > 1 or len(outcomes) > 1:
        return None, ("package carries %d positions and %d outcomes; exactly one of "
                      "each is required, and choosing between them would be a guess"
                      % (len(positions), len(outcomes)))
    if not positions:
        return None, "NO_POSITION_OBJECT"
    if not outcomes:
        return None, "NO_OUTCOME_OBJECT"

    position, outcome = positions[0], outcomes[0]

    # DEVELOPER TEST TRADES ARE NOT EVIDENCE. They are synthetic BUY/SELL/WIN/LOSS
    # trades the operator generates from Developer Mode to exercise the paper
    # engine's UI; they travel the real code path, so they mint real packages, but
    # they never observed a market. Importing one would put a fabricated trade into
    # a research corpus as an observation of trading, which is the one thing this
    # corpus may never contain.
    #
    # Found when the B-22 backfill minted 13 packages: 9 real closes and 4
    # `AGT|TEST|` developer trades. The importer had no filter, and index.html
    # already excludes them from trade-integrity checks by the same id prefix.
    # Three independent markers are checked because any one of them could be
    # absent on an older record, and a developer trade slipping through is worse
    # than a real trade being skipped -- which would be caught as a missing record.
    if is_developer_test_package(package):
        return None, "DEVELOPER_TEST_TRADE"

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
        value = map_outcome_value(target_field, value)
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
            value = map_outcome_value(field, outcome[0].get(key))
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
                observations_dir=None, sources_dir=None):
    """Read every package file and map it. Writes nothing.

    Returns (records, skipped, sources).
    """
    now = now or datetime.datetime(2026, 1, 1)
    sources = build_sources(now, package_glob, sources_dir=sources_dir,
                            observations_dir=observations_dir)
    records, skipped, seen, seen_hashes = [], [], set(), set()
    imported = already_imported(observations_dir) if skip_imported else {}
    # Continue each date's sequence from what is already recorded, so a second run
    # appends rather than colliding with -- or renumbering -- existing records.
    counters = {}
    for observation_id in imported.values():
        parts = observation_id.split("|")
        if len(parts) == 4 and parts[3].isdigit():
            counters[parts[2]] = max(counters.get(parts[2], 0), int(parts[3]))
    # B-29. Sequences are assigned in CONTENT order, not file-discovery order.
    #
    # The mechanism was already bounded -- `imported` is contentHash-keyed so a
    # recorded observation is never re-minted, each date's counter continues from
    # the recorded maximum, and write_observation refuses to overwrite -- so no
    # identity that anything cites could ever move. But WHICH sequence two
    # same-date pending packages received depended on the order their files
    # happened to be globbed, and reversing that order passed the entire suite.
    #
    # Migrating the id format was considered and REJECTED: `observationId` is
    # embedded in 259 preserved records and cited across the corpus, so a
    # content-derived id would mean renaming preserved evidence to make a
    # migration convenient. Sorting the pending set by a key the PACKAGE carries
    # removes the ordering dependence without touching a single recorded id.
    #
    # (createdAt, contentHash) is a total order: contentHash is unique per package
    # -- it is the corpus-wide identity used for deduplication everywhere else --
    # so the sort is deterministic even when timestamps collide.
    pending = []
    for path in sorted(globmod.glob(package_glob or PACKAGE_GLOB)):
        rel = os.path.relpath(path, REPO_ROOT)
        with open(path, "r", encoding="utf-8") as handle:
            packages = json.load(handle)
        for package in packages:
            if package.get("contentHash") in imported:
                continue          # already recorded; never re-minted, never rewritten
            pending.append((package.get("createdAt") or "",
                            package.get("contentHash") or "", rel, package))

    for _created, _hash, rel, package in sorted(pending, key=lambda x: (x[0], x[1])):
            source = sources.get((rel, package.get("captureBasis")))
            record, reason = observation_from_package(package, now, counters, source)
            if record is None:
                skipped.append({"file": os.path.basename(rel),
                                "packageId": package.get("packageId"),
                                "reason": reason})
                continue
            # WITHIN-RUN dedup on contentHash, not just on the assigned id.
            #
            # `imported` catches a package already RECORDED, and `seen` catches an id
            # collision -- but two packages carrying the SAME contentHash in one run
            # receive DIFFERENT sequence numbers, so neither check fired and BOTH were
            # minted: one package's content became two observations. That is the
            # duplicate-mint defect which already reached the live corpus once, via two
            # capture files holding one package. It was fixed in the pipeline's novelty
            # check; the importer -- the authoritative gate -- still allowed it.
            content_hash = record.get("sourceContentHash")
            if content_hash and content_hash in seen_hashes:
                skipped.append({"file": os.path.basename(rel),
                                "packageId": package.get("packageId"),
                                "reason": "DUPLICATE_CONTENT_HASH|%s" % content_hash})
                continue
            if content_hash:
                seen_hashes.add(content_hash)
            if record["observationId"] in seen:
                skipped.append({"file": os.path.basename(rel),
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

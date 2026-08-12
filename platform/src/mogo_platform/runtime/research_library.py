#!/usr/bin/env python3
"""MOGO Automation Platform -- the research library bridge. MOGO-018 Step 2.

WHAT THIS IS

    A DERIVED INDEX connecting the governed autonomous acquisition lane
    (MOGO-014..017) to the existing Knowledge Library's organizational
    namespace -- trader and strategy family.

    One entry per (sourceId, resourceId) comparison stream, built by reading
    `capability_results`. Every value is derived from authoritative existing
    data except the educator attribution, which cannot be derived and is
    declared in ONE committed file.

WHAT IT IS NOT, AND THIS IS THE WHOLE DESIGN

    It is NOT a store, NOT evidence and NOT a source of truth. It writes
    nothing. `entries()` is a read, and running it twice on unchanged input
    produces byte-identical output -- so the index can always be thrown away
    and rebuilt, exactly as the event log's derived index can.

    It does NOT convert, copy, reshape or rewrite anything. Immutable
    acquisition artifacts are REFERENCED by id and path, never duplicated, and
    committed Knowledge Library evidence is never read for mutation and never
    written at all.

TWO CONTENT HASHES EXIST AND THEY ARE NOT THE SAME NUMBER

    Lane A (`EvidenceSource.contentHash`) is SHA-256 of a stored TRANSCRIPT
    FILE. Lane B (`connector_transport.content_hash`) is SHA-256 of the exact
    validated EXTERNAL RESPONSE BODY BYTES, and is MOGO-017's scientific
    content identity.

    They answer different questions and must never be conflated. This module
    therefore never emits a bare field called `contentHash`. It emits
    `acceptedContentIdentity` alongside an explicit
    `acceptedContentIdentityBasis`, so a reader cannot mistake one for the
    other and no future code can quietly substitute one for the other. A test
    asserts both properties.

IDENTIFIERS ARE MAPPED, NEVER FORCED TOGETHER

    Lane A and Lane B both have a field spelled `sourceId`, and they mean
    DIFFERENT THINGS:

        Lane A  EVSRC|<TRADER>|<DATE>|<N>   ONE piece of source material
        Lane B  SRC|<provider>|<12-hex>      ONE educator's channel

    Lane B's (sourceId, resourceId) PAIR is what corresponds to a Lane A
    EvidenceSource; Lane B's sourceId alone corresponds to a Lane A traderId.
    Collapsing the two `sourceId` fields because they share a name would be
    exactly the wrong move, so this module never does it and never mints an
    EVSRC identifier.

ORGANIZATION IS NOT VALIDATION

    An entry says "this material was collected for this corpus". It does not
    say the strategy is valid, that the material was verified, or that anything
    became a trading rule. Every entry carries lane RESEARCH and
    promotionStatus NOT_A_TRADING_RULE, and this module creates no hypothesis,
    rule, blueprint, backtest, campaign or trading decision -- it has no code
    path to any of them.
"""

import json
import os

from ..contracts import ids  # noqa: E402
from . import change_detection  # noqa: E402
from . import errors as runtime_errors  # noqa: E402
from .capabilities import acquire_approved_source_metadata as acquire  # noqa: E402

ATTRIBUTION_SCHEMA_VERSION = "mogo.research-library-attribution.v1"
ENTRY_SCHEMA_VERSION = "mogo.research-library-entry.v1"

# The basis of the identity this index reports. Named explicitly and carried on
# every entry so Lane A's transcript hash and Lane B's external-byte hash can
# never be read as the same thing.
CONTENT_IDENTITY_BASIS = "RAW_EXTERNAL_RESPONSE_BYTES"

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))
ATTRIBUTION_PATH = os.path.join(REPO_ROOT, "docs", "trader-intelligence",
                                "library", "source-attribution.json")

ATTRIBUTION_REQUIRED = ("sourceId", "sourceIdDerivation", "traderId",
                        "strategyFamilyIds")

# Newest first, so the first accepted row for a stream is its current accepted
# content. `rowid` breaks a same-millisecond tie deterministically -- the same
# ordering acquisition_history uses, for the same reason.
_ACQUISITIONS = (
    "SELECT idempotency_key, result_json, recorded_at, rowid AS row_id "
    "FROM capability_results WHERE capability_id = ? "
    "ORDER BY recorded_at DESC, rowid DESC")


def _refuse(message):
    runtime_errors.fail(message, runtime_errors.ContractValidationError)


def resolve_attribution(document):
    """The declared educator attribution, VERIFIED rather than trusted.

    Takes an ALREADY-PARSED document rather than a path, so this module performs
    no I/O at all -- the same split `scheduled_collection.py` uses, and for the
    same reason: the runtime's write-guard boundary is easier to keep exact when
    a module simply has no file access to audit.

    `sourceId` is RECOMPUTED from the declared provider and channel URL and the
    record is refused if it disagrees. That is what turns this file from a
    pasted identifier into a checked one: a typo, or a channel URL swapped
    under an unchanged id, fails closed instead of silently attributing one
    educator's material to another.
    """
    if not hasattr(document, "get"):
        _refuse("the attribution document must be a mapping, got %s"
                % (type(document).__name__,))

    if document.get("schemaVersion") != ATTRIBUTION_SCHEMA_VERSION:
        _refuse("attribution schemaVersion %r is not %r"
                % (document.get("schemaVersion"), ATTRIBUTION_SCHEMA_VERSION))

    attributions = document.get("attributions")
    if not isinstance(attributions, list) or not attributions:
        _refuse("attribution file must declare a non-empty attributions array")

    resolved = {}
    for record in attributions:
        if not isinstance(record, dict):
            _refuse("each attribution must be an object")
        missing = [name for name in ATTRIBUTION_REQUIRED if name not in record]
        if missing:
            _refuse("attribution is missing %s" % (missing,))

        source_id = record["sourceId"]
        ids.require_composite_id(source_id, "SRC", "sourceId")

        derivation = record["sourceIdDerivation"]
        if not isinstance(derivation, dict):
            _refuse("sourceIdDerivation must be an object")
        provider = derivation.get("provider")
        channel_url = derivation.get("channelUrl")
        if not provider or not channel_url:
            _refuse("sourceIdDerivation requires provider and channelUrl so the "
                    "sourceId can be recomputed rather than trusted")
        recomputed = ids.make_source_id(provider, channel_url)
        if recomputed != source_id:
            _refuse("attribution declares sourceId %r but %r derives %r from the "
                    "channel URL; refusing to attribute material to an educator "
                    "on an identifier that does not check out"
                    % (source_id, provider, recomputed))

        trader_id = record["traderId"]
        if not isinstance(trader_id, str) or not trader_id.strip():
            _refuse("traderId must be a non-empty string")

        families = record["strategyFamilyIds"]
        if not isinstance(families, list):
            _refuse("strategyFamilyIds must be an array -- one artifact may "
                    "belong to several corpora, so this is a list by design")
        for family in families:
            if not isinstance(family, str) or not family.startswith("SF|"):
                _refuse("strategy family %r is not an SF| identifier" % (family,))
        if len(set(families)) != len(families):
            _refuse("strategyFamilyIds contains a duplicate entry")

        if source_id in resolved:
            _refuse("source %s is attributed twice; ambiguous ownership is "
                    "refused rather than resolved by picking one" % (source_id,))
        resolved[source_id] = {"traderId": trader_id,
                               "strategyFamilyIds": list(families)}
    return resolved


def _accepted(result):
    """The accepted external content identity of a recorded acquisition, or None.

    Reuses the MOGO-017 contract rather than restating it, so the library and
    the detector can never disagree about what counts as accepted.
    """
    return change_detection.accepted_identity_from_acquisition(result)


def entries(connection, attribution_document):
    """The derived library index. A READ. Deterministic. Writes nothing.

    One entry per (sourceId, resourceId) stream that has at least one ACCEPTED
    acquisition. A stream whose every acquisition failed validation produces no
    entry at all -- a failure must not put material into a corpus.
    """
    attribution = resolve_attribution(attribution_document)
    rows = connection.execute(_ACQUISITIONS, (acquire.CAPABILITY_ID,)).fetchall()

    streams = {}
    for row in rows:                                   # newest first
        try:
            result = json.loads(row["result_json"])
        except (ValueError, TypeError):
            continue                                   # unparseable is not evidence
        source_id = result.get("sourceId")
        resource_id = result.get("resourceId")
        if not source_id or not resource_id:
            continue
        identity = _accepted(result)
        if identity is None:
            continue                                   # recorded, but NOT accepted

        key = (source_id, resource_id)
        entry = streams.get(key)
        if entry is None:
            # First row seen for this stream is the NEWEST, so it carries the
            # current accepted identity and the artifact reference.
            attributed = attribution.get(source_id)
            detection = result.get("changeDetection") or {}
            entry = {
                "schemaVersion": ENTRY_SCHEMA_VERSION,
                # ── which approved source/resource ──
                "sourceId": source_id,
                "resourceId": resource_id,
                # ── organizational attribution (NOT a validity claim) ──
                "traderId": None if attributed is None else attributed["traderId"],
                "strategyFamilyIds": ([] if attributed is None
                                      else list(attributed["strategyFamilyIds"])),
                "attributionStatus": ("ATTRIBUTED" if attributed is not None
                                      else "UNATTRIBUTED"),
                # ── which immutable artifact, BY REFERENCE ──
                "artifactId": (result.get("ingestion") or {}).get("artifactId"),
                "artifactPath": (result.get("ingestion") or {}).get("storedPath"),
                "rawAcquisitionPath": result.get("rawArtifactPath"),
                "intakeRef": result.get("intakeRef"),
                # ── current accepted external content identity ──
                # Deliberately NOT called `contentHash`: Lane A already uses that
                # name for a transcript-file hash, and the two must never be
                # readable as the same thing.
                "acceptedContentIdentity": identity,
                "acceptedContentIdentityBasis": CONTENT_IDENTITY_BASIS,
                "acceptedContentIdentityAlgorithm": "SHA-256",
                # ── provenance / history REFERENCES ──
                "authorizationId": result.get("authorizationId"),
                "lastAcquisitionKey": row["idempotency_key"],
                "lastObservedAt": row["recorded_at"],
                "lastClassification": detection.get("classification"),
                "firstObservedAt": row["recorded_at"],
                # ── deterministic counts that fall out of the walk ──
                "acceptedObservationCount": 0,
                "distinctAcceptedContentIdentities": 0,
                # ── the boundary, carried with the entry ──
                "lane": "RESEARCH",
                "promotionStatus": "NOT_A_TRADING_RULE",
            }
            entry["_identities"] = set()
            streams[key] = entry

        entry["acceptedObservationCount"] += 1
        entry["_identities"].add(identity)
        # Rows arrive newest first, so the last one seen is the oldest.
        entry["firstObservedAt"] = row["recorded_at"]

    ordered = []
    for key in sorted(streams):
        entry = streams[key]
        entry["distinctAcceptedContentIdentities"] = len(entry.pop("_identities"))
        ordered.append(entry)
    return ordered


def corpus_summary(connection, attribution_document):
    """Deterministic counts per strategy family. No score, no verdict, no flag.

    Facts that fall out of the index, and nothing more. Whether a corpus is
    "mature enough" for anything is a judgement this module does not make and
    must not appear to make.
    """
    summary = {}
    for entry in entries(connection, attribution_document):
        for family in (entry["strategyFamilyIds"] or ["(unattributed)"]):
            bucket = summary.setdefault(family, {
                "strategyFamilyId": family,
                "traderId": entry["traderId"],
                "streams": 0,
                "acceptedObservations": 0,
                "distinctContentIdentities": 0,
                "lane": "RESEARCH",
                "promotionStatus": "NOT_A_TRADING_RULE",
            })
            bucket["streams"] += 1
            bucket["acceptedObservations"] += entry["acceptedObservationCount"]
            bucket["distinctContentIdentities"] += \
                entry["distinctAcceptedContentIdentities"]
    return [summary[name] for name in sorted(summary)]

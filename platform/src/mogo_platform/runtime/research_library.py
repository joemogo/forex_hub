#!/usr/bin/env python3
"""MOGO Automation Platform -- the research library bridge. MOGO-018 Step 2,
extended in Step 3D with a read-only corpus observability report.

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
from . import authorizations as authorizations_module  # noqa: E402
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


# ---------------------------------------------------------------------------
# MOGO-018 Step 3D -- the read-only corpus observability report
# ---------------------------------------------------------------------------
# A SECOND DERIVED VIEW over the SAME rows `entries()` already walks. It adds no
# store, no table, no file and no index: it answers "what does the autonomous
# research system currently possess, by source and by strategy family" from the
# acquisition history and the declared attribution, and nothing else.
#
# It lives beside the Step 2 bridge rather than in a module of its own because
# it needs exactly what the bridge needs -- the acquisition rows and the
# resolved attribution -- and a second module would have duplicated that walk.
# `entries()` and `corpus_summary()` are NOT modified; their output is unchanged.

REPORT_SCHEMA_VERSION = "mogo.research-corpus-report.v1"

# Every acquisition row is walked, not just accepted ones, because a refused
# acquisition is a FACT AN OPERATOR NEEDS -- it just must never become content.
_ALL_ACQUISITIONS = (
    "SELECT idempotency_key, result_json, recorded_at, rowid AS row_id "
    "FROM capability_results WHERE capability_id = ? "
    "ORDER BY recorded_at ASC, rowid ASC")          # OLDEST first: chain order

# The classifications MOGO-017 can record. `NOT_RECORDED` is not one of them --
# it is this report's own bucket for rows written before the change-detection
# contract existed, and it is surfaced rather than folded into UNCHANGED.
CLASSIFICATIONS = ("FIRST_OBSERVATION", "UNCHANGED", "CHANGED")
CLASSIFICATION_NOT_RECORDED = "NOT_RECORDED"

# What a COMPLETE acquisition provenance record carries. Checked by presence on
# the authoritative `capability_results` row -- never by reading an artifact
# file, and never by writing one.
ACQUISITION_PROVENANCE_FIELDS = (
    "sourceId", "resourceId", "authorizationId", "connectorId",
    "contentHash", "httpStatus", "finalUrl", "acquiredAt",
)


def _classification_of(result):
    detection = result.get("changeDetection")
    if not isinstance(detection, dict):
        return CLASSIFICATION_NOT_RECORDED
    value = detection.get("classification")
    return value if value in CLASSIFICATIONS else CLASSIFICATION_NOT_RECORDED


def _acquisition_provenance(result):
    """Presence check over the AUTHORITATIVE acquisition record. Pure.

    THE DISTINCTION THIS EXISTS TO DRAW. The research ARTIFACT WRAPPER carries
    `acquisitionPerformed: false` and `networkAccessPerformed: false` even when
    the upstream governed acquisition genuinely opened a socket -- because the
    wrapper is minted by the local-intake ingestion capability and those fields
    describe THE INGEST STEP, not the acquisition. Reading them as acquisition
    provenance would report every autonomously acquired artifact as
    operator-supplied, which is false.

    So acquisition provenance is derived HERE, from `capability_results`, which
    is the authoritative record of what the connector and transport actually
    did. Nothing is rewritten: the wrapper keeps saying what it says, and this
    report simply does not ask it a question it cannot answer.
    """
    missing = [name for name in ACQUISITION_PROVENANCE_FIELDS
               if result.get(name) in (None, "")]
    decision = result.get("connectorDecision")
    if not isinstance(decision, dict):
        missing.append("connectorDecision")
    elif decision.get("decidedAt") in (None, ""):
        missing.append("connectorDecision.decidedAt")
    return {
        "complete": not missing,
        "missingFields": sorted(set(missing)),
        # Network access is a FACT derivable from the record, not a claim copied
        # from a wrapper: a recorded HTTP status and a final URL mean a socket
        # was opened and answered.
        "networkAccessPerformed": bool(result.get("httpStatus"))
                                  and bool(result.get("finalUrl")),
    }


def _authorization_status(connection, source_id):
    """What authorization is in force for this source, or why none is."""
    record, problem = authorizations_module.resolve(connection, source_id)
    if record is None:
        return {"status": "NOT_AUTHORIZED", "problem": problem,
                "authorizationId": None, "policyStatus": None,
                "permittedOperations": []}
    return {
        "status": "AUTHORIZED",
        "problem": None,
        "authorizationId": record.get("authorizationId"),
        "policyStatus": record.get("policyStatus"),
        "permittedOperations": list(record.get("permittedOperations") or []),
    }


def corpus_report(connection, attribution_document):
    """The read-only corpus observability report. A READ. Writes NOTHING.

    Deterministic: same rows and same attribution produce byte-identical output.
    There is no clock, no network, no acquisition and no file access in this
    function or anything it calls, so generating a report cannot change what the
    report describes.

    NO VERDICT IS PRODUCED. Every number here is a count, a timestamp or a
    presence check. Nothing scores a corpus, ranks an educator, or says a
    strategy is ready, valid, good, bad or profitable -- and there is
    deliberately no field in which such a judgement could be recorded.
    """
    attribution = resolve_attribution(attribution_document)
    rows = connection.execute(_ALL_ACQUISITIONS,
                              (acquire.CAPABILITY_ID,)).fetchall()

    streams = {}
    for row in rows:                                    # OLDEST first
        try:
            result = json.loads(row["result_json"])
        except (ValueError, TypeError):
            continue
        source_id = result.get("sourceId")
        resource_id = result.get("resourceId")
        if not source_id or not resource_id:
            continue

        key = (source_id, resource_id)
        stream = streams.get(key)
        if stream is None:
            attributed = attribution.get(source_id)
            stream = {
                "sourceId": source_id,
                "resourceId": resource_id,
                "traderId": None if attributed is None else attributed["traderId"],
                "strategyFamilyIds": ([] if attributed is None
                                      else list(attributed["strategyFamilyIds"])),
                "attributionStatus": ("ATTRIBUTED" if attributed is not None
                                      else "UNATTRIBUTED"),
                "authorization": _authorization_status(connection, source_id),
                "observations": {"recorded": 0, "accepted": 0, "notAccepted": 0},
                "classifications": dict.fromkeys(
                    CLASSIFICATIONS + (CLASSIFICATION_NOT_RECORDED,), 0),
                "firstAcceptedAt": None,
                "lastAcceptedAt": None,
                "latestContentIdentity": None,
                "latestClassification": None,
                "contentIdentityBasis": CONTENT_IDENTITY_BASIS,
                "contentIdentityAlgorithm": "SHA-256",
                "distinctContentIdentities": 0,
                "artifactIds": [],
                "artifactCount": 0,
                "acquisitionProvenance": {"completeObservations": 0,
                                          "incompleteObservations": 0,
                                          "missingFields": [],
                                          "networkAccessObservations": 0},
                "integrity": {},
                "lane": "RESEARCH",
                "promotionStatus": "NOT_A_TRADING_RULE",
            }
            stream["_identities"] = []
            stream["_artifacts"] = []
            stream["_missing"] = set()
            stream["_streamMismatch"] = 0
            stream["_chainBreaks"] = 0
            stream["_noArtifact"] = 0
            streams[key] = stream

        stream["observations"]["recorded"] += 1
        classification = _classification_of(result)
        stream["classifications"][classification] += 1

        provenance = _acquisition_provenance(result)
        target = stream["acquisitionProvenance"]
        target["completeObservations" if provenance["complete"]
               else "incompleteObservations"] += 1
        if provenance["networkAccessPerformed"]:
            target["networkAccessObservations"] += 1
        stream["_missing"].update(provenance["missingFields"])

        # ISOLATION, CHECKED ROW BY ROW. Each row's own comparison stream must
        # be its own (sourceId, resourceId). A row whose detector compared it
        # against another source is exactly the contamination this milestone
        # exists to make impossible, so it is counted rather than assumed away.
        detection = result.get("changeDetection")
        if isinstance(detection, dict):
            declared = detection.get("comparisonStream")
            if isinstance(declared, dict) and (
                    declared.get("sourceId"), declared.get("resourceId")) != key:
                stream["_streamMismatch"] += 1

        identity = _accepted(result)
        if identity is None:
            stream["observations"]["notAccepted"] += 1
            continue

        # ── from here: ACCEPTED content only ──
        # The prior identity a row recorded must be the previous ACCEPTED
        # identity of THIS stream. That is the history chain, verified rather
        # than trusted -- and it cannot hold if two sources ever shared history.
        if isinstance(detection, dict):
            prior = detection.get("priorContentIdentity")
            expected = stream["_identities"][-1] if stream["_identities"] else None
            if prior != expected:
                stream["_chainBreaks"] += 1

        stream["observations"]["accepted"] += 1
        stream["_identities"].append(identity)
        stream["latestContentIdentity"] = identity
        stream["latestClassification"] = (
            classification if classification != CLASSIFICATION_NOT_RECORDED
            else None)
        stream["lastAcceptedAt"] = row["recorded_at"]
        if stream["firstAcceptedAt"] is None:
            stream["firstAcceptedAt"] = row["recorded_at"]

        artifact_id = (result.get("ingestion") or {}).get("artifactId")
        if not artifact_id:
            # Accepted content that names no immutable artifact would be content
            # the corpus cannot show you. Counted, never silently tolerated.
            stream["_noArtifact"] += 1
        elif artifact_id not in stream["_artifacts"]:
            stream["_artifacts"].append(artifact_id)

    ordered = []
    for key in sorted(streams):
        stream = streams[key]
        identities = stream.pop("_identities")
        artifacts = stream.pop("_artifacts")
        missing = stream.pop("_missing")
        mismatches = stream.pop("_streamMismatch")
        chain_breaks = stream.pop("_chainBreaks")
        no_artifact = stream.pop("_noArtifact")
        stream["distinctContentIdentities"] = len(set(identities))
        # ARTIFACTS ARE COUNTED BY DISTINCT IDENTIFIER, never by observation.
        # Eight acquisitions of unchanged content are ONE artifact; counting
        # observations here would inflate every corpus that is working properly.
        stream["artifactIds"] = list(artifacts)
        stream["artifactCount"] = len(artifacts)
        stream["acquisitionProvenance"]["missingFields"] = sorted(missing)
        stream["integrity"] = {
            "comparisonStreamMismatches": mismatches,
            "historyChainBreaks": chain_breaks,
            "acceptedObservationsWithoutArtifact": no_artifact,
            "status": ("OK" if not mismatches and not chain_breaks
                       and not no_artifact else "REVIEW"),
            "checks": "recorded-record consistency only; corpus files on disk "
                      "are NOT re-hashed by this report",
        }
        ordered.append(stream)

    return {
        "schemaVersion": REPORT_SCHEMA_VERSION,
        "lane": "RESEARCH",
        "promotionStatus": "NOT_A_TRADING_RULE",
        "streams": ordered,
        "corpora": _corpora(ordered),
        "totals": {
            "streams": len(ordered),
            "attributedStreams": sum(1 for s in ordered
                                     if s["attributionStatus"] == "ATTRIBUTED"),
            "unattributedStreams": sum(1 for s in ordered
                                       if s["attributionStatus"] != "ATTRIBUTED"),
            "acceptedObservations": sum(s["observations"]["accepted"]
                                        for s in ordered),
            "artifacts": sum(s["artifactCount"] for s in ordered),
        },
    }


def _corpora(streams):
    """Per-strategy-family FACTS. Counts and timestamps -- never a judgement.

    An UNATTRIBUTED stream is reported under an explicit `(unattributed)` bucket
    rather than being dropped or guessed into somebody's corpus: material whose
    owner is undeclared is exactly the thing an operator must be told about.
    """
    buckets = {}
    for stream in streams:
        families = stream["strategyFamilyIds"] or ["(unattributed)"]
        for family in families:
            bucket = buckets.setdefault(family, {
                "strategyFamilyId": family,
                "traderId": stream["traderId"],
                "sourceIds": [],
                "distinctApprovedResources": 0,
                "acceptedObservations": 0,
                "changedObservations": 0,
                "firstObservationCount": 0,
                "unchangedObservations": 0,
                "classificationNotRecorded": 0,
                "artifacts": 0,
                "distinctContentIdentities": 0,
                "observedFrom": None,
                "observedTo": None,
                "provenanceCompleteObservations": 0,
                "provenanceIncompleteObservations": 0,
                "integrityStatus": "OK",
                "lane": "RESEARCH",
                "promotionStatus": "NOT_A_TRADING_RULE",
            })
            if stream["sourceId"] not in bucket["sourceIds"]:
                bucket["sourceIds"].append(stream["sourceId"])
            bucket["distinctApprovedResources"] += 1
            bucket["acceptedObservations"] += stream["observations"]["accepted"]
            bucket["changedObservations"] += stream["classifications"]["CHANGED"]
            bucket["firstObservationCount"] += \
                stream["classifications"]["FIRST_OBSERVATION"]
            bucket["unchangedObservations"] += \
                stream["classifications"]["UNCHANGED"]
            bucket["classificationNotRecorded"] += \
                stream["classifications"][CLASSIFICATION_NOT_RECORDED]
            bucket["artifacts"] += stream["artifactCount"]
            bucket["distinctContentIdentities"] += \
                stream["distinctContentIdentities"]
            bucket["provenanceCompleteObservations"] += \
                stream["acquisitionProvenance"]["completeObservations"]
            bucket["provenanceIncompleteObservations"] += \
                stream["acquisitionProvenance"]["incompleteObservations"]
            for name, value in (("observedFrom", stream["firstAcceptedAt"]),
                                ("observedTo", stream["lastAcceptedAt"])):
                if value is None:
                    continue
                current = bucket[name]
                if current is None:
                    bucket[name] = value
                elif name == "observedFrom":
                    bucket[name] = min(current, value)
                else:
                    bucket[name] = max(current, value)
            if stream["integrity"]["status"] != "OK":
                bucket["integrityStatus"] = "REVIEW"
    return [buckets[name] for name in sorted(buckets)]

#!/usr/bin/env python3
"""TradeObservation records -- MOGO-019 gap 2, closed.

WHY THIS EXISTS
---------------
MOGO-019 case 002 stalled because the operator supplied a SCREENSHOT of a trade
and the corpus had nowhere to put it. Two things were missing:

  1. EvidenceSource had no "screenshot" sourceType (closed separately, in
     evidence-source.schema.json and evidence_common.SOURCE_TYPES).
  2. There was no structured record for "a trade was observed", as distinct from
     "a trader said something". A claim captures an assertion about how to trade.
     It cannot capture that EUR/USD was entered at 1.0840 with a 20-pip stop.

A TradeObservation is the second. It is deliberately ONE record type for both
actors:

    actor = "HUMAN"  -- a trade the operator took, usually read off a screenshot
    actor = "MOGO"   -- a decision MOGO made, PAPER or replay

That is the whole point. Human-vs-MOGO decision-difference analysis needs both
sides in the same shape, or every comparison silently compares two schemas
instead of two decisions. The actor is carried in the identifier itself
(TOBS|HUMAN|... vs TOBS|MOGO|...) so the two can never be conflated by accident.

WHAT THIS MODULE REFUSES TO DO
------------------------------
The failure mode this guards against is a screenshot being read generously --
a number that was never visible becoming a recorded fact, or a reasonable
inference ("that looks like a 1:2 target") being stored indistinguishably from
something the image actually showed. So:

  * Every recorded value MUST carry a classification. An unclassified value is
    refused, not defaulted.
  * Every classification MUST correspond to a recorded value. You cannot classify
    a field you did not record.
  * A field is either KNOWN (has a value and a classification) or UNKNOWN (listed
    in `unknowns`, with no value). Never both, never neither.
  * INFERRED requires a stated reason. An inference that cannot say why it was
    inferred is not evidence.
  * An absent number stays absent. Nothing here defaults a price, a size or a
    P&L to zero -- a missing stop is UNKNOWN, and zero is a real stop loss.

`lane` is pinned to RESEARCH. A TradeObservation is an observation. It is not a
rule, it does not become one here, and nothing in this module promotes anything.

NO NETWORK ACCESS ANYWHERE IN THIS MODULE.
"""
import argparse
import glob as globmod
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import graph_common as gc            # noqa: E402
import evidence_common as ec         # noqa: E402

REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
EVIDENCE_ROOT = os.path.join(REPO_ROOT, "docs", "trader-intelligence", "evidence")
OBSERVATIONS_DIR = os.path.join(EVIDENCE_ROOT, "observations")

SCHEMA_VERSION = "mogo.trade-observation.v1"
LANE = "RESEARCH"

ACTORS = ("HUMAN", "MOGO")

CLASSIFICATIONS = ("DIRECTLY_OBSERVED", "SOURCE_STATED", "INFERRED", "UNKNOWN")

# ---------------------------------------------------------------------------
# Evidence population -- replay/historical vs forward/live
# ---------------------------------------------------------------------------
#
# NO NEW TAXONOMY. The distinction already exists in the provenance model: an
# observation points at an EvidenceSource, and that source's `sourceType` says what
# kind of artifact it is. `replay_observation` and `paper_trade` are both already in
# evidence_common.SOURCE_TYPES. So the population is DERIVED from provenance rather
# than asserted on the record, which means it cannot disagree with the source it
# came from -- a denormalized flag could.
#
# The consequence, deliberately: population is not knowable from an observation
# alone. Every function below that could blend populations REQUIRES the source map,
# so producing a forward statistic without the provenance that distinguishes forward
# from replay is not something a caller can do by forgetting.
HISTORICAL = "HISTORICAL"
RECONSTRUCTED = "RECONSTRUCTED"
FORWARD = "FORWARD"
UNKNOWN_POPULATION = "UNKNOWN"
POPULATIONS = (HISTORICAL, FORWARD, RECONSTRUCTED, UNKNOWN_POPULATION)

# Deliberately a small allowlist on the FORWARD side and UNKNOWN for everything
# unlisted. Fail closed in the direction that matters: a source type nobody has
# classified must never silently count as forward evidence.
HISTORICAL_SOURCE_TYPES = ("replay_observation", "generated_analysis")
FORWARD_SOURCE_TYPES = ("paper_trade", "live_trade_review")
# Reconstructed after the fact from the account's own journal, because the evidence
# package that would have been minted at close time does not exist. Its own
# population, NOT a flavour of FORWARD and NOT folded into UNKNOWN: forward means
# captured live as it happened, and UNKNOWN must keep meaning "cannot be
# determined" rather than doubling as a bucket for a class we chose deliberately.
RECONSTRUCTED_SOURCE_TYPES = ("journal_entry",)

# The fields that describe the trade itself and therefore require classification.
# Metadata (ids, timestamps, lane, notes) is not evidence about a trade and is
# deliberately excluded.
OBSERVABLE_FIELDS = (
    "instrument", "timeframe", "direction", "entry", "stop", "target",
    "exitPrice", "positionSize", "riskAmount", "pnl", "rMultiple",
    "accountBalanceBefore", "accountBalanceAfter", "openedAt", "closedAt",
    "outcome", "decisionTaken", "declineReason",
)


class ObservationRefused(ec.EvidenceValidationError):
    """Raised when a trade observation cannot be recorded as stated.

    Refusing is the correct outcome: a half-read screenshot recorded as fact is
    worse than no record, because downstream comparison cannot tell the two apart.
    """


def _refuse(message):
    raise ObservationRefused(message)


def validate_observation(record):
    """Validate a TradeObservation. Returns the record; raises ObservationRefused.

    Pure: mutates nothing and touches no file, so it is safe to call on a
    candidate record before deciding whether to write it.
    """
    if not isinstance(record, dict):
        _refuse("a trade observation must be an object, got %r" % type(record).__name__)

    actor = record.get("actor")
    if actor not in ACTORS:
        _refuse("actor %r must be one of %s -- an observation whose origin is unknown "
                "cannot be used in a human-vs-MOGO comparison." % (actor, list(ACTORS)))

    for field in ("observationId", "sourceId", "instrument", "extractedBy"):
        value = record.get(field)
        if not isinstance(value, str) or not value.strip():
            _refuse("%s is required and must be a non-empty string (got %r). An "
                    "observation with no %s cannot be traced back to what was seen."
                    % (field, value, field))

    # sourceId must be a real EvidenceSource, not some other artifact's identifier.
    # This is what makes the evidence population derivable: the source carries the
    # sourceType that says whether this was replay or forward. An importer pointing
    # sourceId straight at a package id (PKG|...) looks traceable and is not -- it
    # resolves to nothing, so the population is unknowable and the schema pattern
    # `^EVSRC\|` is violated silently.
    if not record["sourceId"].startswith("EVSRC|"):
        _refuse("sourceId %r must be an EvidenceSource id beginning 'EVSRC|'. The "
                "population of an observation (replay vs forward) is derived from its "
                "source's sourceType, so a sourceId that resolves to no source makes "
                "the observation unusable in either analysis."
                % (record["sourceId"],))

    lane = record.get("lane", LANE)
    if lane != LANE:
        _refuse("lane %r is not permitted; a trade observation is always %r. This "
                "record type never carries trading authority." % (lane, LANE))

    classification = record.get("fieldClassification")
    if not isinstance(classification, dict):
        _refuse("fieldClassification is required and must be an object mapping each "
                "recorded field to how it was known.")

    unknowns = record.get("unknowns")
    if not isinstance(unknowns, list):
        _refuse("unknowns is required and must be a list -- state what was NOT visible "
                "explicitly. An empty list is a claim that everything was known.")

    for field, how in sorted(classification.items()):
        if field not in OBSERVABLE_FIELDS:
            _refuse("fieldClassification names %r, which is not an observable trade "
                    "field. Classifiable fields are: %s"
                    % (field, ", ".join(OBSERVABLE_FIELDS)))
        if how not in CLASSIFICATIONS:
            _refuse("fieldClassification[%r] = %r is not one of %s"
                    % (field, how, list(CLASSIFICATIONS)))
        if record.get(field) is None:
            _refuse("fieldClassification classifies %r but the record has no value for "
                    "it. A classification without a value is a claim about nothing."
                    % (field,))

    for field in unknowns:
        if field not in OBSERVABLE_FIELDS:
            _refuse("unknowns names %r, which is not an observable trade field." % (field,))
        # ONE check, deliberately, rather than a value-side and a classification-side
        # test. As two separate guards they covered each other: a field with a value
        # AND a classification AND an unknowns entry was caught by whichever remained,
        # so deleting either in isolation changed no outcome and no fixture could tell.
        # Deleting BOTH opened a real hole -- the "recorded value must be classified"
        # and "classification must have a value" checks elsewhere in this function
        # cannot see that case, because such a field has both. Collapsed so the
        # invariant fails as a unit.
        if record.get(field) is not None or field in classification:
            _refuse("%r is listed as UNKNOWN but is also recorded (value=%r, "
                    "classification=%r). A field is either known or unknown, never "
                    "both -- an unknown that carries data is how a half-read "
                    "screenshot becomes a fact."
                    % (field, record.get(field), classification.get(field)))

    # The core invariant: nothing recorded is unclassified.
    for field in OBSERVABLE_FIELDS:
        if record.get(field) is not None and field not in classification:
            _refuse("%r has the value %r but no entry in fieldClassification. Every "
                    "recorded value must say how it was known -- observed, stated, or "
                    "inferred." % (field, record.get(field)))

    reasons = record.get("inferenceReasons") or {}
    if not isinstance(reasons, dict):
        _refuse("inferenceReasons must be an object mapping an inferred field to why.")
    for field, how in sorted(classification.items()):
        if how == "INFERRED":
            why = reasons.get(field)
            if not isinstance(why, str) or not why.strip():
                _refuse("%r is classified INFERRED but inferenceReasons[%r] is missing. "
                        "An inference that cannot state its basis is not evidence, and "
                        "must never be stored where a source-stated fact would sit."
                        % (field, field))
        elif field in reasons:
            _refuse("inferenceReasons names %r, which is classified %s rather than "
                    "INFERRED. Only an inference carries an inference reason."
                    % (field, how))

    return record


def build_observation(actor, sourceId, instrument, fields, classification,
                      unknowns, extractedBy, now, inferenceReasons=None,
                      observationId=None, **extra):
    """Assemble and validate a TradeObservation without writing it.

    `fields` carries the observed trade values; anything absent stays absent
    rather than being defaulted.
    """
    if now is None:
        _refuse("now is required -- a record with no creation time cannot be ordered "
                "against the trades it is compared with.")
    record = {
        "observationId": observationId or ec.next_observation_id(
            OBSERVATIONS_DIR, actor, now),
        "actor": actor,
        "sourceId": sourceId,
        "instrument": instrument,
        "fieldClassification": dict(classification or {}),
        "unknowns": sorted(unknowns or []),
        "extractedBy": extractedBy,
        "lane": LANE,
        "schemaVersion": SCHEMA_VERSION,
        "createdAt": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if inferenceReasons:
        record["inferenceReasons"] = dict(inferenceReasons)
    for key, value in (fields or {}).items():
        if key not in OBSERVABLE_FIELDS:
            _refuse("%r is not an observable trade field." % (key,))
        if value is not None:
            record[key] = value
    for key, value in extra.items():
        if value is not None:
            record.setdefault(key, value)
    return validate_observation(record)


def write_observation(record, observations_dir=None):
    """Validate, then write atomically. Refuses to overwrite an existing record."""
    validate_observation(record)
    target_dir = observations_dir or OBSERVATIONS_DIR
    os.makedirs(target_dir, exist_ok=True)
    path = os.path.join(
        target_dir, ec.observation_id_to_filename(record["observationId"]))
    if os.path.exists(path):
        _refuse("%s already exists. A trade observation is immutable once recorded; "
                "correct it with a new record that supersedes it, so the original "
                "reading stays auditable." % (path,))
    gc.atomic_write_text(path, gc.pretty_json(record))
    return path


def load_observations(observations_dir=None):
    """Read every observation. Read-only."""
    target_dir = observations_dir or OBSERVATIONS_DIR
    out = {}
    if not os.path.isdir(target_dir):
        return out
    for path in sorted(globmod.glob(os.path.join(target_dir, "*.json"))):
        with open(path, "r", encoding="utf-8") as handle:
            record = json.load(handle)
        out[record["observationId"]] = record
    return out


def observation_population(record, sources):
    """HISTORICAL / FORWARD / UNKNOWN, derived from the source's sourceType.

    `sources` maps sourceId -> EvidenceSource record. Fails closed: an observation
    whose source is not present resolves to UNKNOWN rather than being assumed
    forward, because assuming forward is the error that contaminates live results.
    """
    source = (sources or {}).get(record.get("sourceId"))
    if source is None:
        return UNKNOWN_POPULATION
    source_type = source.get("sourceType")
    if source_type in HISTORICAL_SOURCE_TYPES:
        return HISTORICAL
    if source_type in FORWARD_SOURCE_TYPES:
        return FORWARD
    if source_type in RECONSTRUCTED_SOURCE_TYPES:
        return RECONSTRUCTED
    return UNKNOWN_POPULATION


def select_population(observations, sources, population):
    """The sanctioned way to obtain one evidence population.

    Callers name the population they mean, so a forward-performance question can
    never be answered from replay records by omission.
    """
    if population not in POPULATIONS:
        _refuse("population %r must be one of %s" % (population, list(POPULATIONS)))
    return {k: v for k, v in (observations or {}).items()
            if observation_population(v, sources) == population}


def summarize(observations, sources):
    """A read-only view: how much of each side exists, and how well-evidenced.

    `sources` is REQUIRED, not optional. That is the structural guarantee behind
    invariant 3: this function cannot produce a count without the provenance that
    separates replay from forward, so there is no signature by which a caller
    accidentally gets a blended total. Every figure is reported per population, and
    no aggregate across populations is offered at all -- a combined "222 trades"
    number is exactly the artifact that would mislead.

    Reports UNKNOWN coverage rather than hiding it -- the number of unknowns is
    the honest measure of how far a screenshot actually got.
    """
    if sources is None:
        _refuse("summarize() requires the EvidenceSource map. Without it, replay and "
                "forward observations are indistinguishable and any total mixes them.")
    by_population = {}
    for record in (observations or {}).values():
        population = observation_population(record, sources)
        group = by_population.setdefault(population, {"total": 0, "byActor": {}})
        group["total"] += 1
        bucket = group["byActor"].setdefault(record["actor"], {
            "count": 0, "byClassification": {}, "unknownFields": 0})
        bucket["count"] += 1
        bucket["unknownFields"] += len(record.get("unknowns") or [])
        for how in (record.get("fieldClassification") or {}).values():
            bucket["byClassification"][how] = \
                bucket["byClassification"].get(how, 0) + 1
    for group in by_population.values():
        # Comparability is per population: a human trade and a MOGO REPLAY are not
        # a comparable pair, so pairing them across populations is never counted.
        group["comparable"] = min(group["byActor"].get("HUMAN", {}).get("count", 0),
                                  group["byActor"].get("MOGO", {}).get("count", 0))
    return {
        "lane": LANE,
        "schemaVersion": SCHEMA_VERSION,
        "byPopulation": by_population,
        "populationsPresent": sorted(by_population),
    }


def load_sources(sources_dir=None):
    """Read every EvidenceSource. Read-only. The population map for summarize()."""
    target_dir = sources_dir or os.path.join(EVIDENCE_ROOT, "sources")
    out = {}
    if not os.path.isdir(target_dir):
        return out
    for path in sorted(globmod.glob(os.path.join(target_dir, "*.json"))):
        with open(path, "r", encoding="utf-8") as handle:
            record = json.load(handle)
        out[record["sourceId"]] = record
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--summary", action="store_true",
                        help="print a read-only summary of recorded observations")
    args = parser.parse_args(argv)
    if args.summary:
        print(json.dumps(summarize(load_observations(), load_sources()),
                         indent=2, sort_keys=True))
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

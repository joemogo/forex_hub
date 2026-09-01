#!/usr/bin/env python3
"""Strict local boundary for one synthetic MOGO -> LEAN zone request.

The boundary accepts one JSON value from stdin and writes one JSON response to stdout.  It is
purposefully closed: an unknown or missing field is a refusal, rather than an invitation to make
up a default.  This is a synthetic contract test, not production wiring, a cloud run, or an
assertion that a caller supplied zone has historical provenance.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
PACKAGE = os.path.dirname(HERE)
if PACKAGE not in sys.path:
    sys.path.insert(0, PACKAGE)

from br_machine import Bar, BreakRetestMachine

REQUEST_SCHEMA = "mogo.lean.zone-request.v1"
RESPONSE_SCHEMA = "mogo.lean.zone-result.v1"
MAX_REQUEST_BYTES = 2 * 1024 * 1024
MAX_BARS = 10000

REQUEST_FIELDS = frozenset(("schemaVersion", "caseId", "config", "zone", "bars"))
ZONE_FIELDS = frozenset(("low", "high", "role", "availableFromIndex"))
BAR_FIELDS = frozenset(("index", "timestamp", "open", "high", "low", "close"))
CONFIG_FIELDS = frozenset((
    "breakConfirmationCloses", "maxBarsBetweenBreakAndRetest", "stopATRBuffer", "atrPeriod",
    "minRR", "trendSwingLookback", "rejectionConfirmWithinBars",
    "rejectionDisplacementATRMultiplier",
))


class Refusal(ValueError):
    """A named, caller-safe reason the boundary will not evaluate an input."""
    def __init__(self, code, message):
        ValueError.__init__(self, message)
        self.code = code
        self.message = message


def _refuse(code, message):
    raise Refusal(code, message)


def _unique_object(pairs):
    """Build a JSON object while refusing duplicate keys instead of silently taking the last."""
    result = {}
    for key, value in pairs:
        if key in result:
            _refuse("REFUSE_JSON_DUPLICATE_FIELD", "duplicate JSON field: %s" % key)
        result[key] = value
    return result


def _finite_json(value, path="response"):
    """Refuse derived non-finite numbers before they can escape as non-standard JSON."""
    if isinstance(value, float) and not math.isfinite(value):
        _refuse("REFUSE_NONFINITE_RESULT", "%s is not finite" % path)
    if isinstance(value, dict):
        for key, child in value.items():
            _finite_json(child, "%s.%s" % (path, key))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _finite_json(child, "%s[%d]" % (path, index))


def _object(value, name, fields):
    if not isinstance(value, dict):
        _refuse("REFUSE_%s_TYPE" % name, "%s must be an object" % name.lower())
    actual = frozenset(value)
    unknown = sorted(actual - fields)
    missing = sorted(fields - actual)
    if unknown:
        _refuse("REFUSE_%s_UNKNOWN_FIELD" % name,
                "%s has unknown field(s): %s" % (name.lower(), ", ".join(unknown)))
    if missing:
        _refuse("REFUSE_%s_MISSING_FIELD" % name,
                "%s is missing field(s): %s" % (name.lower(), ", ".join(missing)))
    return value


def _number(value, path):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _refuse("REFUSE_NUMBER", "%s must be a finite number" % path)
    value = float(value)
    if not math.isfinite(value):
        _refuse("REFUSE_NUMBER", "%s must be a finite number" % path)
    return value


def _integer(value, path, minimum=0):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        _refuse("REFUSE_INTEGER", "%s must be an integer >= %d" % (path, minimum))
    return value


def _validate(request):
    request = _object(request, "REQUEST", REQUEST_FIELDS)
    if request["schemaVersion"] != REQUEST_SCHEMA:
        _refuse("REFUSE_SCHEMA_VERSION", "schemaVersion must be %s" % REQUEST_SCHEMA)
    if not isinstance(request["caseId"], str) or not request["caseId"]:
        _refuse("REFUSE_CASE_ID", "caseId must be a non-empty string")

    config = _object(request["config"], "CONFIG", CONFIG_FIELDS)
    clean_config = {}
    for key in CONFIG_FIELDS:
        value = _number(config[key], "config.%s" % key)
        if key in ("breakConfirmationCloses", "maxBarsBetweenBreakAndRetest", "atrPeriod",
                   "trendSwingLookback", "rejectionConfirmWithinBars"):
            if value != int(value) or value < 1:
                _refuse("REFUSE_CONFIG", "config.%s must be a positive integer" % key)
            clean_config[key] = int(value)
        elif value < 0:
            _refuse("REFUSE_CONFIG", "config.%s must not be negative" % key)
        else:
            clean_config[key] = value
    if clean_config["minRR"] <= 0:
        _refuse("REFUSE_CONFIG", "config.minRR must be greater than zero")

    zone = _object(request["zone"], "ZONE", ZONE_FIELDS)
    low, high = _number(zone["low"], "zone.low"), _number(zone["high"], "zone.high")
    if low > high:
        _refuse("REFUSE_ZONE_RANGE", "zone.low must not exceed zone.high")
    if zone["role"] not in ("support", "resistance"):
        _refuse("REFUSE_ZONE_ROLE", "zone.role must be support or resistance")
    available = _integer(zone["availableFromIndex"], "zone.availableFromIndex")

    bars = request["bars"]
    if not isinstance(bars, list) or not bars:
        _refuse("REFUSE_BARS", "bars must be a non-empty array")
    if len(bars) > MAX_BARS:
        _refuse("REFUSE_BARS_LIMIT", "bars must contain at most %d items" % MAX_BARS)
    clean_bars = []
    expected_index = None
    for row_number, raw in enumerate(bars):
        bar = _object(raw, "BAR", BAR_FIELDS)
        index = _integer(bar["index"], "bars[%d].index" % row_number)
        timestamp = _integer(bar["timestamp"], "bars[%d].timestamp" % row_number, minimum=1)
        if expected_index is None:
            expected_index = index
        if index != expected_index:
            _refuse("REFUSE_BAR_INDEX", "bar indexes must be contiguous and ordered")
        expected_index += 1
        o = _number(bar["open"], "bars[%d].open" % row_number)
        h = _number(bar["high"], "bars[%d].high" % row_number)
        l = _number(bar["low"], "bars[%d].low" % row_number)
        c = _number(bar["close"], "bars[%d].close" % row_number)
        if not (l <= o <= h and l <= c <= h):
            _refuse("REFUSE_BAR_OHLC", "bars[%d] is not well-formed OHLC" % row_number)
        if clean_bars and timestamp <= clean_bars[-1][1]:
            _refuse("REFUSE_BAR_TIMESTAMP", "bar timestamps must be strictly increasing")
        clean_bars.append((index, timestamp, o, h, l, c))
    if available < clean_bars[0][0] or available > clean_bars[-1][0]:
        _refuse("REFUSE_ZONE_AVAILABILITY", "zone availability must fall within delivered bars")
    return request["caseId"], clean_config, (low, high, zone["role"], available), clean_bars


def evaluate(request):
    """Validate and consume a complete synthetic request. Returns JSON-safe output only."""
    case_id, config, zone, bars = _validate(request)
    machine = BreakRetestMachine(config, zone[0], zone[1], zone[2], zone[3])
    for index, timestamp, o, h, l, c in bars:
        machine.on_bar(Bar(index, timestamp, o, h, l, c))
    result = {
        "schemaVersion": RESPONSE_SCHEMA,
        "caseId": case_id,
        "barsConsumed": machine.bars_seen,
        "state": machine.state,
        "decision": machine.decision,
    }
    _finite_json(result)
    return result


def main(stdin=None, stdout=None):
    """CLI entry point. Exactly one JSON object in; exactly one JSON line out."""
    stdin, stdout = stdin or sys.stdin, stdout or sys.stdout
    try:
        raw = stdin.read(MAX_REQUEST_BYTES + 1)
        if len(raw.encode("utf-8")) > MAX_REQUEST_BYTES:
            _refuse("REFUSE_REQUEST_SIZE", "request exceeds %d UTF-8 bytes" % MAX_REQUEST_BYTES)
        request = json.loads(raw, object_pairs_hook=_unique_object,
                             parse_constant=lambda value: _refuse(
                                 "REFUSE_JSON_NUMBER", "non-finite JSON number: %s" % value))
        response = {"ok": True, "response": evaluate(request)}
        code = 0
    except Refusal as error:
        response = {"ok": False, "refusal": {"code": error.code, "message": error.message}}
        code = 2
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        response = {"ok": False, "refusal": {"code": "REFUSE_JSON", "message": str(error)}}
        code = 2
    stdout.write(json.dumps(response, sort_keys=True, separators=(",", ":"),
                            allow_nan=False) + "\n")
    return code


if __name__ == "__main__":
    sys.exit(main())

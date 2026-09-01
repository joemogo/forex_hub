#!/usr/bin/env python3
"""Closed v2 synthetic boundary.  This is not production wiring or a cloud adapter.

v2 makes the break direction authoritative: support broken down is a sell, and
resistance broken up is a buy.  ``preBreakRole`` is retained as provenance and
must agree with that direction; it is never silently used as a decision proxy.
"""
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
SYNTHETIC = os.path.dirname(HERE)
if SYNTHETIC not in sys.path:
    sys.path.insert(0, SYNTHETIC)
from br_machine import Bar, BreakRetestMachine

REQUEST_SCHEMA = "mogo.lean.zone-request.v2"
RESPONSE_SCHEMA = "mogo.lean.zone-result.v2"
MAX_REQUEST_BYTES = 2 * 1024 * 1024
MAX_BARS = 10000
SEMANTICS = "START_TIME_UTC_MS"
TIMEFRAMES = frozenset(("H1", "H4", "D", "W"))
TOP = frozenset(("schemaVersion", "caseId", "identity", "versions", "barTimestampSemantics",
                 "zone", "breakEvent", "setup", "dataset", "config", "bars"))
IDENTITY = frozenset(("pair", "timeframe"))
VERSIONS = frozenset(("strategyVersion", "ruleVersion", "appVersion"))
ZONE = frozenset(("id", "low", "high", "formedAt", "preBreakRole"))
AT = frozenset(("index", "barStartTimeUtcMs", "closeTimeUtcMs"))
BREAK = frozenset(("id", "brokenDirection", "at"))
SETUP = frozenset(("id", "type", "reaction", "retestAt", "qualificationAt"))
DATASET = frozenset(("id", "hash"))
HASH = frozenset(("algorithm", "value"))
BAR = frozenset(("index", "startTimeUtcMs", "open", "high", "low", "close"))
CONFIG = frozenset(("breakConfirmationCloses", "maxBarsBetweenBreakAndRetest", "stopATRBuffer",
                    "atrPeriod", "minRR", "trendSwingLookback", "rejectionConfirmWithinBars",
                    "rejectionDisplacementATRMultiplier"))

class Refusal(ValueError):
    def __init__(self, code, message):
        ValueError.__init__(self, message); self.code, self.message = code, message

def _no(code, message): raise Refusal(code, message)
def _unique(pairs):
    out = {}
    for key, value in pairs:
        if key in out: _no("REFUSE_JSON_DUPLICATE_FIELD", "duplicate JSON field: %s" % key)
        out[key] = value
    return out
def _obj(value, name, fields):
    if not isinstance(value, dict): _no("REFUSE_%s_TYPE" % name, "%s must be an object" % name.lower())
    unknown, missing = sorted(set(value) - fields), sorted(fields - set(value))
    if unknown: _no("REFUSE_%s_UNKNOWN_FIELD" % name, "unknown field(s): %s" % ", ".join(unknown))
    if missing: _no("REFUSE_%s_MISSING_FIELD" % name, "missing field(s): %s" % ", ".join(missing))
    return value
def _num(value, path):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        _no("REFUSE_NUMBER", "%s must be finite" % path)
    return float(value)
def _int(value, path, minimum=0):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        _no("REFUSE_INTEGER", "%s must be an integer >= %d" % (path, minimum))
    return value
def _string(value, path):
    if not isinstance(value, str) or not value: _no("REFUSE_STRING", "%s must be a non-empty string" % path)
    return value
def _finite(value):
    if isinstance(value, float) and not math.isfinite(value): _no("REFUSE_NONFINITE_RESULT", "non-finite result")
    if isinstance(value, dict):
        for child in value.values(): _finite(child)
    if isinstance(value, list):
        for child in value: _finite(child)

def _at(value, name, bars):
    item = _obj(value, name, AT); index = _int(item["index"], name + ".index")
    start = _int(item["barStartTimeUtcMs"], name + ".barStartTimeUtcMs", 1)
    close = _int(item["closeTimeUtcMs"], name + ".closeTimeUtcMs", 1)
    known = bars.get(index)
    if known is None or known["startTimeUtcMs"] != start:
        _no("REFUSE_PROVENANCE_TIMESTAMP", "%s must name a delivered bar start time" % name.lower())
    if known["closeTimeUtcMs"] != close:
        _no("REFUSE_PROVENANCE_CLOSE_TIME", "%s must carry that bar's derived close time" % name.lower())
    return index, start, close

def _cadence_ok(timeframe, delta):
    hour = 3600000
    if timeframe == "H1": return delta == hour
    if timeframe == "H4": return delta == 4 * hour
    if timeframe == "D": return delta in (23 * hour, 24 * hour, 25 * hour)
    if timeframe == "W": return delta in (167 * hour, 168 * hour, 169 * hour)
    return False

def _validate(request):
    request = _obj(request, "REQUEST", TOP)
    if request["schemaVersion"] != REQUEST_SCHEMA: _no("REFUSE_SCHEMA_VERSION", "wrong schema")
    _string(request["caseId"], "caseId")
    ident = _obj(request["identity"], "IDENTITY", IDENTITY)
    _string(ident["pair"], "identity.pair")
    if ident["timeframe"] not in TIMEFRAMES: _no("REFUSE_TIMEFRAME", "timeframe must be H1, H4, D, or W")
    versions = _obj(request["versions"], "VERSIONS", VERSIONS)
    for key in VERSIONS: _string(versions[key], "versions." + key)
    if request["barTimestampSemantics"] != SEMANTICS: _no("REFUSE_TIMESTAMP_SEMANTICS", "bar timestamp semantics must be " + SEMANTICS)
    bars_raw = request["bars"]
    if not isinstance(bars_raw, list) or not bars_raw: _no("REFUSE_BARS", "bars must be a non-empty array")
    if len(bars_raw) > MAX_BARS: _no("REFUSE_BARS_LIMIT", "too many bars")
    bars, prior_time, expected = {}, None, None
    clean = []
    for pos, raw in enumerate(bars_raw):
        row = _obj(raw, "BAR", BAR); index = _int(row["index"], "bars.index")
        timestamp = _int(row["startTimeUtcMs"], "bars.startTimeUtcMs", 1)
        if expected is None: expected = index
        if index != expected: _no("REFUSE_BAR_INDEX", "bar indexes must be contiguous and ordered")
        expected += 1
        if prior_time is not None and timestamp <= prior_time: _no("REFUSE_BAR_TIMESTAMP", "bar times must increase")
        o,h,l,c = [_num(row[key], "bars.%s" % key) for key in ("open","high","low","close")]
        if not (l <= o <= h and l <= c <= h): _no("REFUSE_BAR_OHLC", "malformed OHLC")
        if prior_time is not None and not _cadence_ok(ident["timeframe"], timestamp - prior_time):
            _no("REFUSE_BAR_CADENCE", "bar spacing contradicts identity.timeframe")
        prior_time = timestamp
        cooked = {"index": index, "startTimeUtcMs": timestamp, "open":o,"high":h,"low":l,"close":c}
        bars[index] = cooked; clean.append(cooked)
    for pos, row in enumerate(clean):
        if pos + 1 < len(clean):
            row["closeTimeUtcMs"] = clean[pos + 1]["startTimeUtcMs"]
        else:
            delta = clean[-1]["startTimeUtcMs"] - clean[-2]["startTimeUtcMs"] if len(clean) > 1 else None
            if delta is None or not _cadence_ok(ident["timeframe"], delta):
                _no("REFUSE_LAST_BAR_CLOSE_TIME", "cannot derive the final bar close time")
            row["closeTimeUtcMs"] = row["startTimeUtcMs"] + delta
    zone = _obj(request["zone"], "ZONE", ZONE); low, high = _num(zone["low"], "zone.low"), _num(zone["high"], "zone.high")
    if low > high: _no("REFUSE_ZONE_RANGE", "zone low exceeds high")
    if zone["preBreakRole"] not in ("support", "resistance"): _no("REFUSE_ZONE_ROLE", "invalid pre-break role")
    _string(zone["id"], "zone.id")
    formed_index, _, _ = _at(zone["formedAt"], "FORMED_AT", bars)
    brk = _obj(request["breakEvent"], "BREAK", BREAK)
    direction = brk["brokenDirection"]
    if direction not in ("downThroughSupport", "upThroughResistance"): _no("REFUSE_BROKEN_DIRECTION", "invalid break direction")
    expected_role = "support" if direction == "downThroughSupport" else "resistance"
    if zone["preBreakRole"] != expected_role: _no("REFUSE_ROLE_DIRECTION", "pre-break role contradicts broken direction")
    _string(brk["id"], "breakEvent.id")
    break_index, _, _ = _at(brk["at"], "BREAK_AT", bars)
    if break_index <= formed_index: _no("REFUSE_PROVENANCE_ORDER", "break must follow formation")
    break_bar = bars[break_index]
    if direction == "downThroughSupport" and not break_bar["close"] < low: _no("REFUSE_BREAK_GEOMETRY", "down break close must be below support")
    if direction == "upThroughResistance" and not break_bar["close"] > high: _no("REFUSE_BREAK_GEOMETRY", "up break close must be above resistance")
    setup = _obj(request["setup"], "SETUP", SETUP)
    _string(setup["id"], "setup.id")
    if setup["type"] != "break-retest": _no("REFUSE_SETUP_TYPE", "setup type must be break-retest")
    if setup["reaction"] != "rejection": _no("REFUSE_SETUP_REACTION", "setup reaction must be rejection")
    retest_index, _, _ = _at(setup["retestAt"], "RETEST_AT", bars)
    if retest_index <= break_index: _no("REFUSE_PROVENANCE_ORDER", "retest must follow break")
    qualification_index, _, _ = _at(setup["qualificationAt"], "QUALIFICATION_AT", bars)
    if qualification_index < retest_index: _no("REFUSE_PROVENANCE_ORDER", "qualification must not precede retest")
    dataset = _obj(request["dataset"], "DATASET", DATASET); _string(dataset["id"], "dataset.id")
    digest = _obj(dataset["hash"], "HASH", HASH)
    if digest["algorithm"] != "SHA-256": _no("REFUSE_HASH_ALGORITHM", "dataset hash algorithm must be SHA-256")
    if not isinstance(digest["value"], str) or not re.fullmatch(r"[0-9a-f]{64}", digest["value"]):
        _no("REFUSE_HASH_VALUE", "dataset hash value must be 64 lowercase hexadecimal characters")
    cfg = _obj(request["config"], "CONFIG", CONFIG); clean_cfg = {}
    integer_keys = ("breakConfirmationCloses", "maxBarsBetweenBreakAndRetest", "atrPeriod", "trendSwingLookback", "rejectionConfirmWithinBars")
    for key in CONFIG:
        value = _num(cfg[key], "config." + key)
        if key in integer_keys:
            if value != int(value) or value < 1: _no("REFUSE_CONFIG", key + " must be positive integer")
            clean_cfg[key] = int(value)
        elif value < 0: _no("REFUSE_CONFIG", key + " must not be negative")
        else: clean_cfg[key] = value
    if clean_cfg["minRR"] <= 0: _no("REFUSE_CONFIG", "minRR must be positive")
    return request, clean_cfg, clean, direction, (low, high), retest_index, qualification_index

def evaluate(request):
    request, cfg, bars, direction, zone, declared_retest, declared_qualification = _validate(request)
    # Adapter deliberately maps explicit direction to legacy synthetic machine role; v1 stays unchanged.
    legacy_role = "support" if direction == "upThroughResistance" else "resistance"
    machine = BreakRetestMachine(cfg, zone[0], zone[1], legacy_role, request["zone"]["formedAt"]["index"])
    for row in bars: machine.on_bar(Bar(row["index"], row["startTimeUtcMs"], row["open"], row["high"], row["low"], row["close"]))
    decision = machine.decision
    if decision is None: _no("REFUSE_UNQUALIFIED_SETUP", "declared setup did not qualify")
    if decision["brokenDirection"] != direction: _no("REFUSE_DIRECTION_MISMATCH", "adapter decision differs from explicit break direction")
    if decision["anchorBarIndex"] != declared_retest: _no("REFUSE_RETEST_MISMATCH", "retest provenance differs from evaluation")
    if decision["lockedAtBarIndex"] != declared_qualification: _no("REFUSE_QUALIFICATION_MISMATCH", "qualification provenance differs from evaluation")
    result = {"schemaVersion": RESPONSE_SCHEMA, "caseId": request["caseId"], "pair": request["identity"]["pair"],
              "timeframe": request["identity"]["timeframe"], "barsConsumed": machine.bars_seen,
              "decision": decision}
    _finite(result); return result

def main(stdin=None, stdout=None):
    stdin, stdout = stdin or sys.stdin, stdout or sys.stdout
    try:
        raw = stdin.read(MAX_REQUEST_BYTES + 1)
        if len(raw.encode("utf-8")) > MAX_REQUEST_BYTES: _no("REFUSE_REQUEST_SIZE", "request too large")
        request = json.loads(raw, object_pairs_hook=_unique, parse_constant=lambda x: _no("REFUSE_JSON_NUMBER", "non-finite JSON number"))
        output, code = {"ok": True, "response": evaluate(request)}, 0
    except Refusal as err: output, code = {"ok": False, "refusal": {"code":err.code,"message":err.message}}, 2
    except (ValueError, TypeError, json.JSONDecodeError) as err: output, code = {"ok":False,"refusal":{"code":"REFUSE_JSON","message":str(err)}}, 2
    stdout.write(json.dumps(output, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"); return code

if __name__ == "__main__": sys.exit(main())

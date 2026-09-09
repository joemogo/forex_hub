"""Pure arithmetic fixtures for the isolated v2 contract; never reads production state."""
import json
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
SYNTHETIC = os.path.dirname(HERE)
if SYNTHETIC not in sys.path: sys.path.insert(0, SYNTHETIC)
import synthetic_bars as sb
from zone_contract_v2.boundary import REQUEST_SCHEMA, SEMANTICS

CONFIG = {"breakConfirmationCloses": 1, "maxBarsBetweenBreakAndRetest": 50, "stopATRBuffer": .25,
          "atrPeriod": 14, "minRR": 2.0, "trendSwingLookback": 3,
          "rejectionConfirmWithinBars": 1, "rejectionDisplacementATRMultiplier": .25}

def _up_bars():
    return [{"index":i,"startTimeUtcMs":t,"open":o,"high":h,"low":l,"close":c}
            for i,t,o,h,l,c in sb.series("qualify")]

def _down_bars():
    # Reflection around 100.25 mirrors the documented synthetic up fixture exactly.
    # It produces a support broken down, retaining the same deterministic retest geometry.
    out = []
    for row in _up_bars():
        out.append({"index":row["index"], "startTimeUtcMs":row["startTimeUtcMs"],
                    "open":200.5-row["open"], "high":200.5-row["low"],
                    "low":200.5-row["high"], "close":200.5-row["close"]})
    return out

def emit(case):
    if case not in ("buy", "sell"): raise ValueError("unknown synthetic v2 case: %s" % case)
    buy = case == "buy"; bars = _up_bars() if buy else _down_bars()
    direction = "upThroughResistance" if buy else "downThroughSupport"
    role = "resistance" if buy else "support"
    def at(index):
        return {"index":index, "barStartTimeUtcMs":bars[index]["startTimeUtcMs"],
                "closeTimeUtcMs":bars[index + 1]["startTimeUtcMs"]}
    dataset_bytes = json.dumps(bars, sort_keys=True, separators=(",", ":")).encode("utf-8")
    # First strict confirmed close through the outer edge is index 40; the machine locks at 55.
    return {"schemaVersion": REQUEST_SCHEMA, "caseId": "V2-%s" % case.upper(),
            "identity":{"pair":"SYNTHETIC_%s" % case.upper(),"timeframe":"D"},
            "versions":{"strategyVersion":"alex-v2-synthetic","ruleVersion":"br-v2-synthetic","appVersion":"mogo-synthetic"},
            "barTimestampSemantics": SEMANTICS,
            "zone":{"id":"zone-%s" % case,"low":100.0,"high":100.5,
                    "formedAt":at(20),"preBreakRole":role},
            "breakEvent":{"id":"break-%s" % case,"brokenDirection":direction,
                          "at":at(40)},
            "setup":{"id":"setup-%s" % case,"type":"break-retest","reaction":"rejection",
                     "retestAt":at(52),"qualificationAt":at(55)},
            "dataset":{"id":"synthetic-arithmetic-v2","hash":{"algorithm":"SHA-256","value":hashlib.sha256(dataset_bytes).hexdigest()}},
            "config":dict(CONFIG),"bars":bars}

def json_text(case): return json.dumps(emit(case), sort_keys=True, separators=(",", ":")) + "\n"

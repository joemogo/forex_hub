#!/usr/bin/env python3
"""Synthetic stand-in for a future MOGO-side zone-request emitter.

It emits only arithmetic fixtures from ``synthetic_bars``.  It does not read MOGO production
state, derive zones, inspect evidence, access a network, or represent a production integration.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PACKAGE = os.path.dirname(HERE)
if PACKAGE not in sys.path:
    sys.path.insert(0, PACKAGE)

import synthetic_bars as sb
from zone_contract.boundary import REQUEST_SCHEMA

CONFIG = {
    "breakConfirmationCloses": 1,
    "maxBarsBetweenBreakAndRetest": 50,
    "stopATRBuffer": 0.25,
    "atrPeriod": 14,
    "minRR": 2.0,
    "trendSwingLookback": 3,
    "rejectionConfirmWithinBars": 1,
    "rejectionDisplacementATRMultiplier": 0.25,
}
CASE_IDS = {"qualify": "SYNQUAL", "reject": "SYNREJ"}


def emit(case):
    """Return the entire closed request envelope for a named synthetic fixture."""
    if case not in CASE_IDS:
        raise ValueError("unknown synthetic case: %s" % case)
    return {
        "schemaVersion": REQUEST_SCHEMA,
        "caseId": CASE_IDS[case],
        "config": dict(CONFIG),
        "zone": {
            "low": sb.ZONE_LOW,
            "high": sb.ZONE_HIGH,
            "role": sb.ZONE_ROLE,
            "availableFromIndex": sb.ZONE_FROM_INDEX,
        },
        "bars": [
            {"index": index, "timestamp": timestamp, "open": o, "high": h,
             "low": l, "close": c}
            for index, timestamp, o, h, l, c in sb.series(case)
        ],
    }


def json_text(case):
    """Canonical JSON for pipe transport and byte-stable test fixtures."""
    return json.dumps(emit(case), sort_keys=True, separators=(",", ":")) + "\n"


if __name__ == "__main__":
    case = sys.argv[1] if len(sys.argv) == 2 else "qualify"
    sys.stdout.write(json_text(case))

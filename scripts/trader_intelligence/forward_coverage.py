#!/usr/bin/env python3
"""Is a missing cohort STARVATION, or just rarity? (MOGO-022)

WHY
---
The standing self-check asks whether every configured instrument and timeframe is
actually covered. Coverage of the ENGINE is answered by
`scripts/mogo_observation_coverage.js`, which reads the browser observation store.
This answers the other half: which cohorts have produced preserved forward
EVIDENCE, and -- the part that matters -- whether an empty cohort is a problem.

THE DISTINCTION THIS EXISTS FOR
-------------------------------
"No trade because no setup" is not "no trade because evaluation failed", and an
absent cohort looks identical from the outside. Weekly is configured and holds ZERO
forward observations, which reads as alarming until the base rate is applied: W is
2 of 221 replay observations, so at 29 forward trades the expectation is about 0.26.
Zero is what rarity predicts, not evidence of a fault.

So an empty cohort is reported with its EXPECTED count, derived from the historical
base rate, and is only called unexplained when the evidence is actually
inconsistent with rarity. The reverse error matters as much: a cohort that SHOULD
have produced several trades and produced none is a starvation signal that a plain
coverage list would show as a shrug.

READ-ONLY over the corpus. Writes one report. NO NETWORK ACCESS.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trade_observation as to      # noqa: E402

REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
REPORT_PATH = os.path.join(REPO_ROOT, "docs", "trader-intelligence", "evidence",
                            "reports", "forward-coverage-report.json")
SCHEMA_VERSION = "mogo.forward-coverage.v1"

# An empty cohort is only "unexplained" once rarity stops explaining it. At an
# expectation below this, absence is the ordinary outcome and flagging it would
# manufacture an alarm.
EXPECTED_COUNT_ALARM_THRESHOLD = 3.0

PRESENT = "PRESENT"
ABSENT_CONSISTENT_WITH_RARITY = "ABSENT_CONSISTENT_WITH_RARITY"
ABSENT_UNEXPLAINED = "ABSENT_UNEXPLAINED"
NO_BASE_RATE = "ABSENT_NO_BASE_RATE"

VERDICT_MEANING = {
    PRESENT: "Forward evidence exists for this cohort.",
    ABSENT_CONSISTENT_WITH_RARITY:
        "No forward evidence, and none is expected yet: the historical base rate "
        "predicts fewer than %.1f trades at the current forward sample size. This is "
        "rarity, not starvation." % EXPECTED_COUNT_ALARM_THRESHOLD,
    ABSENT_UNEXPLAINED:
        "No forward evidence where the historical base rate predicts several. Rarity "
        "does NOT explain this, so it is a starvation candidate and warrants "
        "investigating whether evaluation is actually running for this cohort.",
    NO_BASE_RATE:
        "No forward evidence and no historical evidence either, so there is no base "
        "rate to judge the absence against. UNKNOWN rather than fine.",
}


def cohort_counts(observations, sources, population, key):
    out = {}
    for record in (observations or {}).values():
        if to.observation_population(record, sources) != population:
            continue
        value = record.get(key)
        if value is None:
            continue
        out[value] = out.get(value, 0) + 1
    return out


def assess_cohort(forward_count, historical_share, forward_total):
    """Verdict for one cohort. Pure.

    `historical_share` is the cohort's fraction of the historical population, used
    only as a prior for how often it should appear -- never as evidence about
    performance.
    """
    if forward_count > 0:
        return PRESENT, None
    if historical_share is None:
        return NO_BASE_RATE, None
    expected = historical_share * forward_total
    if expected >= EXPECTED_COUNT_ALARM_THRESHOLD:
        return ABSENT_UNEXPLAINED, round(expected, 3)
    return ABSENT_CONSISTENT_WITH_RARITY, round(expected, 3)


def report(observations=None, sources=None, configured=None, key="timeframe"):
    sources = to.load_sources() if sources is None else sources
    observations = to.load_observations() if observations is None else observations

    forward = cohort_counts(observations, sources, to.FORWARD, key)
    historical = cohort_counts(observations, sources, to.HISTORICAL, key)
    forward_total = sum(forward.values())
    historical_total = sum(historical.values())

    universe = sorted(set(configured or []) | set(forward) | set(historical))
    rows = []
    for cohort in universe:
        share = (historical.get(cohort, 0) / historical_total
                 if historical_total and cohort in historical else None)
        verdict, expected = assess_cohort(forward.get(cohort, 0), share, forward_total)
        rows.append({"cohort": cohort,
                     "forwardCount": forward.get(cohort, 0),
                     "historicalCount": historical.get(cohort, 0),
                     "expectedForwardCount": expected,
                     "verdict": verdict})

    unexplained = [r["cohort"] for r in rows if r["verdict"] == ABSENT_UNEXPLAINED]
    return {
        "generated": True,
        "schemaVersion": SCHEMA_VERSION,
        "lane": "RESEARCH",
        "adjudicates": False,
        "cohortKey": key,
        "configured": sorted(configured or []),
        "forwardTotal": forward_total,
        "historicalTotal": historical_total,
        "rows": rows,
        "unexplainedAbsences": unexplained,
        "verdictMeaning": {r["verdict"]: VERDICT_MEANING[r["verdict"]] for r in rows},
        "doesNotSupport": [
            "The historical base rate is used ONLY to predict how OFTEN a cohort "
            "should appear. It says nothing about how that cohort performs, and no "
            "performance figure may be derived from it here.",
            "An absence consistent with rarity is not proof that evaluation ran. It "
            "means the evidence does not distinguish rarity from failure at this "
            "sample size -- engine-side coverage answers that, not this report.",
        ],
    }


def render(r):
    lines = ["FORWARD COHORT COVERAGE -- derived, read-only (%s)" % r["cohortKey"],
             "  forward observations: %d | historical: %d"
             % (r["forwardTotal"], r["historicalTotal"])]
    for row in r["rows"]:
        expected = ("expected %.2f" % row["expectedForwardCount"]
                    if row["expectedForwardCount"] is not None else "")
        lines.append("    %-6s forward=%-4d historical=%-5d %-32s %s"
                     % (row["cohort"], row["forwardCount"], row["historicalCount"],
                        row["verdict"], expected))
    lines.append("  unexplained absences: %s" % (r["unexplainedAbsences"] or "none"))
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--key", default="timeframe",
                        help="cohort dimension: timeframe, instrument, direction")
    parser.add_argument("--configured", default="H1,H4,D,W",
                        help="comma-separated configured cohorts")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    configured = [c for c in args.configured.split(",") if c] if args.configured else []
    r = report(configured=configured, key=args.key)
    print(json.dumps(r, indent=2, sort_keys=True) if args.json else render(r))
    if args.write:
        os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
        with open(REPORT_PATH, "w", encoding="utf-8") as handle:
            json.dump(r, handle, indent=2, sort_keys=True)
            handle.write("\n")
        print("written to %s" % REPORT_PATH)
    return 1 if r["unexplainedAbsences"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

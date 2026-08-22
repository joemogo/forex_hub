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

#: Configured cohorts are a property of the DIMENSION, not a global list. Only the
#: timeframe universe is fixed and knowable ahead of the evidence; instrument and
#: direction universes are read from the corpus itself, so they get no injected set.
CONFIGURED_BY_KEY = {"timeframe": ["H1", "H4", "D", "W"]}

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


#: A record whose `strategyId` is absent or not a string. It is NEVER guessed and never
#: folded into a named strategy -- MOGO-023 established that `current_strategy` is JVM's
#: real registry id, so an unrecognised value is a fact about attribution, not a typo.
UNATTRIBUTED = "UNATTRIBUTED"


def strategy_of(record):
    """The record's strategy identity, or UNATTRIBUTED. Pure. Never infers."""
    value = (record or {}).get("strategyId")
    return value if isinstance(value, str) and value else UNATTRIBUTED


def cohort_counts(observations, sources, population, key, strategy_id=None):
    """Cohort counts for ONE population, and a full account of what was NOT counted.

    MOGO-023: this used to return only the counts, and dropped two different things in
    silence -- records belonging to another strategy, and records missing the cohort key.
    Both mattered here. The forward population is 27 `alex_g_sr_v1` + 2 `current_strategy`
    (JVM), while the historical population is 221 `alex_g_sr_v1` and nothing else, so the
    base rate this report divides by was ALEX's while the numerator was not. And because
    JVM's journal builder hardcodes `timeframe: null`, the two JVM records vanished from a
    `--key timeframe` run entirely: `forwardTotal` read 27 and nothing said two were
    dropped. The number was right by coincidence, not by segmentation.

    Returns `(counts, accounting)`. `accounting` is not decoration -- it is what makes the
    exclusions reportable instead of silent.
    """
    counts = {}
    composition = {}
    missing_cohort_key = 0
    excluded_other_strategy = 0
    for record in (observations or {}).values():
        if to.observation_population(record, sources) != population:
            continue
        found = strategy_of(record)
        composition[found] = composition.get(found, 0) + 1
        if strategy_id is not None and found != strategy_id:
            excluded_other_strategy += 1
            continue
        value = record.get(key)
        if value is None:
            missing_cohort_key += 1
            continue
        counts[value] = counts.get(value, 0) + 1
    return counts, {"strategyComposition": composition,
                    "missingCohortKey": missing_cohort_key,
                    "excludedOtherStrategy": excluded_other_strategy}


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


def report(observations=None, sources=None, configured=None, key="timeframe",
           strategy_id=None):
    """Cohort coverage. `strategy_id` scopes BOTH arms to one strategy.

    Left unscoped the report is explicitly NOT a strategy-specific claim, and says so:
    `strategyScoped` is false and `strategyMixing` is true whenever more than one
    strategy contributed. A mixed report is a coverage diagnostic, never an authoritative
    statement about any one strategy's behaviour.
    """
    sources = to.load_sources() if sources is None else sources
    observations = to.load_observations() if observations is None else observations

    forward, fwd_acct = cohort_counts(observations, sources, to.FORWARD, key, strategy_id)
    historical, hist_acct = cohort_counts(observations, sources, to.HISTORICAL, key,
                                          strategy_id)
    forward_total = sum(forward.values())
    historical_total = sum(historical.values())

    # Mixing is judged on what CONTRIBUTED to the arms, so a scoped report is never
    # reported as mixed merely because other strategies exist in the corpus.
    contributing = set()
    for acct in (fwd_acct, hist_acct):
        contributing |= set(acct["strategyComposition"])
    if strategy_id is not None:
        contributing = {strategy_id} & contributing
    mixing = len(contributing) > 1

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
        # MOGO-023 strategy-population invariant. A cohort report must name the population
        # it describes, draw both arms from it, and account for every record it excluded.
        "strategyId": strategy_id,
        "strategyScoped": strategy_id is not None,
        "strategyMixing": mixing,
        "forwardStrategyComposition": fwd_acct["strategyComposition"],
        "historicalStrategyComposition": hist_acct["strategyComposition"],
        "excluded": {
            "forwardOtherStrategy": fwd_acct["excludedOtherStrategy"],
            "historicalOtherStrategy": hist_acct["excludedOtherStrategy"],
            "forwardMissingCohortKey": fwd_acct["missingCohortKey"],
            "historicalMissingCohortKey": hist_acct["missingCohortKey"],
        },
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
        ] + ([
            "This report is NOT scoped to one strategy and more than one contributed to "
            "it, so no row here describes any single strategy's behaviour. Re-run with "
            "--strategy to obtain a strategy-specific reading.",
        ] if mixing else []),
    }


def _composition(mapping):
    return ", ".join("%s %d" % (k, mapping[k]) for k in sorted(mapping)) or "none"


def render(r):
    scope = r["strategyId"] if r.get("strategyScoped") else "ALL STRATEGIES (unscoped)"
    lines = ["FORWARD COHORT COVERAGE -- derived, read-only (%s)" % r["cohortKey"],
             "  strategy scope: %s" % scope,
             "  forward observations: %d | historical: %d"
             % (r["forwardTotal"], r["historicalTotal"])]
    if r.get("strategyMixing"):
        lines += [
            "  ** STRATEGY MIXING -- these rows describe NO SINGLE STRATEGY **",
            "     forward:    %s" % _composition(r["forwardStrategyComposition"]),
            "     historical: %s" % _composition(r["historicalStrategyComposition"]),
            "     The base rate divides by one population and counts another. Re-run",
            "     with --strategy for a reading that is about one strategy.",
        ]
    exc = r.get("excluded") or {}
    # Exclusions are printed whenever they are non-zero, because a dropped record that
    # nothing mentions is how forwardTotal read 27 while the population held 29.
    if any(exc.get(k) for k in exc):
        lines.append("  excluded from the counts above:")
        for label, k in (("other strategy (forward)", "forwardOtherStrategy"),
                         ("other strategy (historical)", "historicalOtherStrategy"),
                         ("missing '%s' (forward)" % r["cohortKey"],
                          "forwardMissingCohortKey"),
                         ("missing '%s' (historical)" % r["cohortKey"],
                          "historicalMissingCohortKey")):
            if exc.get(k):
                lines.append("     %-32s %d" % (label, exc[k]))
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
    # MOGO-023: this defaulted to "H1,H4,D,W" for EVERY key, so `--key instrument` and
    # `--key direction` unioned four TIMEFRAME labels into their universe and reported
    # them as absent instruments and absent directions. Harmless-looking
    # (ABSENT_NO_BASE_RATE) but it is fabricated rows in a report whose entire job is to
    # say whether an absence is real. Configured cohorts belong to a dimension.
    parser.add_argument("--configured", default=None,
                        help="comma-separated configured cohorts (default: the known "
                             "set for --key timeframe, none for other dimensions)")
    parser.add_argument("--strategy", default=None,
                        help="scope BOTH arms to one strategyId (e.g. alex_g_sr_v1). "
                             "Unscoped reports disclose strategy mixing instead.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.configured is None:
        configured = CONFIGURED_BY_KEY.get(args.key, [])
    else:
        configured = [c for c in args.configured.split(",") if c]
    r = report(configured=configured, key=args.key, strategy_id=args.strategy)
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

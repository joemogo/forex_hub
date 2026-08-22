#!/usr/bin/env python3
"""Can a preserved observation's own fields all be true at once? (MOGO-023)

WHY THIS EXISTS
---------------
`index.html` has carried `TRADE_INTEGRITY_RULES` since v12.15.0, added because INC-005
found a hand-seeded record counted as a real ALEX paper trade. That layer is rule-based,
runs at read time, quarantines nothing on disk, and states invariants a genuine trade
cannot violate.

**The preserved observation corpus had no equivalent.** The app-side rules key on MAE and
MFE, which the observation schema does not carry, so they cannot even be evaluated here.
A record whose own fields are mutually impossible therefore entered the authoritative
performance population unchallenged -- and one did.

`TOBS|MOGO|20260806|025` records a buy entered at 1.0850 with target 1.0890, closed
0.004 seconds later at **exactly 1.0890**, for exactly +2.000R and exactly +$200.
`closePaperPosition()` books its exit from `fetchBidAsk()` -- `bid` for a buy, `ask` for a
sell -- falling back to the live mid or, for a manual close with no price, to `pos.entry`.
**No MOGO code path assigns `exitPrice = pos.target`.** The engine books the market, never
the objective.

WHAT THIS DOES, AND WHAT IT REFUSES TO DO
-----------------------------------------
It classifies. It does not delete, rewrite, reclassify or quarantine anything on disk, and
it never edits the corpus. Preserved evidence stays byte-identical; INC-005's own lesson is
that the record is the evidence.

The output is a partition, not a judgement about a person:

  RAW PRESERVED POPULATION        every observation, exactly as preserved
  AUTHORITATIVE VERIFIED          those whose fields are mutually consistent
  UNVERIFIED FOR PERFORMANCE      those that are not, each with the rule it violated

Both populations are reported together with the quantitative difference between them,
because reporting one alone is how a 2.0R record silently flattered a 29-trade sample.

RULE DESIGN -- CONJUNCTIVE, NOT SUSPICIOUS
------------------------------------------
Rules fire on **structural impossibility**, never on "this looks odd". A round number is
not a defect; a 2R win is the system working. So the load-bearing rule is a CONJUNCTION:
an exit pinned bit-identically to the target *and* a holding period too short for any
market exit. Either alone has a real false-positive rate. Together they describe something
the close path cannot produce.

Every rule states what it would take to be wrong. A rule that cannot be wrong is not a rule.

READ-ONLY over the corpus. NO NETWORK ACCESS. Writes nothing unless --write is given, and
then only its own report.
"""
import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trade_observation as to      # noqa: E402

REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
REPORT_PATH = os.path.join(REPO_ROOT, "docs", "trader-intelligence", "evidence",
                           "reports", "observation-integrity-report.json")
SCHEMA_VERSION = "mogo.observation-integrity.v1"

VERIFIED = "VERIFIED"
UNVERIFIED = "UNVERIFIED_FOR_AUTHORITATIVE_PERFORMANCE"

#: A market exit is detected by a poll loop reading a live price. Below this, no price
#: update separates entry from exit and the exit cannot have been observed from the market.
#: Deliberately far below the real scan cadence: this must catch the impossible, not the
#: merely fast, because excluding a legitimate trade corrupts the population in the other
#: direction.
MIN_PLAUSIBLE_HOLD_SECONDS = 1.0


def _ts(value):
    """Parse an ISO-8601 instant, or None. Never raises on bad input."""
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def holding_seconds(record):
    """Holding period in seconds, or None when either instant is unusable."""
    opened, closed = _ts((record or {}).get("openedAt")), _ts((record or {}).get("closedAt"))
    if opened is None or closed is None:
        return None
    return (closed - opened).total_seconds()


def _rule_exit_pinned_to_target_in_no_time(record):
    """Exit bit-identical to target, in less time than a price update.

    WOULD BE WRONG IF: MOGO ever booked an exit at the target price rather than the
    market, or if a market exit could be detected without a price update between entry
    and exit. Neither is true of `closePaperPosition()`.
    """
    exit_price, target = record.get("exitPrice"), record.get("target")
    if exit_price is None or target is None or exit_price != target:
        return None
    held = holding_seconds(record)
    if held is None or held >= MIN_PLAUSIBLE_HOLD_SECONDS:
        return None
    return ("EXIT_PINNED_TO_TARGET_WITH_IMPLAUSIBLE_HOLD",
            "exitPrice is bit-identical to target (%r) after %.3fs. closePaperPosition() "
            "books the exit from fetchBidAsk(), never from pos.target, and no price update "
            "separates entry from exit at this duration."
            % (exit_price, held))


def _rule_closes_before_it_opens(record):
    """A trade cannot close at or before it opened.

    WOULD BE WRONG IF: a legitimate record could carry a non-positive duration. It cannot;
    this mirrors the app's own TRADE_INTEGRITY_RULES check.
    """
    held = holding_seconds(record)
    if held is None or held > 0:
        return None
    return ("CLOSED_AT_OR_BEFORE_OPEN",
            "closedAt (%s) is not strictly after openedAt (%s)"
            % (record.get("closedAt"), record.get("openedAt")))


def _rule_outcome_disagrees_with_price(record):
    """The recorded result must agree with the direction the price actually moved.

    WOULD BE WRONG IF: a Win could be booked on adverse movement. Costs are not modelled
    in the observation schema, so a zero move is not judged either way.
    """
    entry, exit_price = record.get("entry"), record.get("exitPrice")
    direction, outcome = record.get("direction"), record.get("outcome")
    if None in (entry, exit_price) or direction not in ("buy", "sell"):
        return None
    if outcome not in ("Win", "Loss"):
        return None
    move = (exit_price - entry) if direction == "buy" else (entry - exit_price)
    if move == 0:
        return None
    if outcome == "Win" and move < 0:
        return ("OUTCOME_CONTRADICTS_PRICE",
                "recorded Win but the %s moved adversely (entry %r -> exit %r)"
                % (direction, entry, exit_price))
    if outcome == "Loss" and move > 0:
        return ("OUTCOME_CONTRADICTS_PRICE",
                "recorded Loss but the %s moved favourably (entry %r -> exit %r)"
                % (direction, entry, exit_price))
    return None


#: Order is not significance -- every rule is evaluated and every violation reported, so a
#: record failing two rules says so rather than stopping at the first.
RULES = (
    _rule_closes_before_it_opens,
    _rule_exit_pinned_to_target_in_no_time,
    _rule_outcome_disagrees_with_price,
)


def evaluate(record):
    """Violations for one observation. Pure. A rule that raises is a rule that FAILED,
    and is reported as such rather than silently counting as a pass."""
    violations = []
    for rule in RULES:
        try:
            found = rule(record or {})
        except Exception as exc:                                  # noqa: BLE001
            violations.append({"ruleId": "RULE_ERROR:%s" % rule.__name__,
                               "detail": "rule raised %s" % type(exc).__name__})
            continue
        if found:
            violations.append({"ruleId": found[0], "detail": found[1]})
    return violations


def _r(record):
    value = record.get("rMultiple")
    return value if isinstance(value, (int, float)) else None


def _stats(records):
    rs = [_r(x) for x in records]
    rs = [x for x in rs if x is not None]
    wins = sum(1 for x in records if x.get("outcome") == "Win")
    return {"n": len(records),
            "withRMultiple": len(rs),
            "sumR": round(sum(rs), 6) if rs else None,
            "meanR": round(sum(rs) / len(rs), 6) if rs else None,
            "wins": wins,
            "winRate": round(wins / len(records), 6) if records else None}


def report(observations=None, sources=None, population=None, strategy_id=None):
    """Partition one population into authoritative and unverified, and price the gap."""
    sources = to.load_sources() if sources is None else sources
    observations = to.load_observations() if observations is None else observations
    population = to.FORWARD if population is None else population

    selected = []
    for record in (observations or {}).values():
        if to.observation_population(record, sources) != population:
            continue
        if strategy_id is not None and record.get("strategyId") != strategy_id:
            continue
        selected.append(record)

    verified, unverified = [], []
    findings = []
    for record in sorted(selected, key=lambda x: x.get("observationId") or ""):
        violations = evaluate(record)
        if violations:
            unverified.append(record)
            findings.append({"observationId": record.get("observationId"),
                             "strategyId": record.get("strategyId"),
                             "rMultiple": _r(record),
                             "violations": violations})
        else:
            verified.append(record)

    raw_stats, auth_stats = _stats(selected), _stats(verified)
    delta = None
    if raw_stats["sumR"] is not None and auth_stats["sumR"] is not None:
        delta = {"sumR": round(auth_stats["sumR"] - raw_stats["sumR"], 6),
                 "meanR": (round(auth_stats["meanR"] - raw_stats["meanR"], 6)
                           if None not in (auth_stats["meanR"], raw_stats["meanR"])
                           else None)}

    return {
        "generated": True,
        "schemaVersion": SCHEMA_VERSION,
        "lane": "RESEARCH",
        "adjudicates": False,
        "population": population,
        "strategyId": strategy_id,
        "strategyScoped": strategy_id is not None,
        "rawPreservedPopulation": raw_stats,
        "authoritativeVerifiedPopulation": auth_stats,
        "excludedFromAuthoritative": _stats(unverified),
        "effectOfExclusion": delta,
        "findings": findings,
        "doesNotSupport": [
            "This classifies FIELD CONSISTENCY, not authenticity. A violation means the "
            "record's own values cannot all be true at once -- it does not establish who "
            "or what produced it, and this report never claims to know.",
            "Nothing here is deleted, rewritten, reclassified or quarantined on disk. "
            "The preserved record remains byte-identical and remains the evidence.",
            "A VERIFIED record is not a validated trade. It means no rule here caught a "
            "contradiction, which is a much weaker claim than correctness.",
        ],
    }


def render(r):
    raw, auth, exc = (r["rawPreservedPopulation"], r["authoritativeVerifiedPopulation"],
                      r["excludedFromAuthoritative"])
    scope = r["strategyId"] if r["strategyScoped"] else "ALL STRATEGIES (unscoped)"

    def line(label, s):
        if not s["n"]:
            return "  %-32s n=0" % label
        return ("  %-32s n=%-4d sumR=%-10s meanR=%-10s winRate=%s"
                % (label, s["n"],
                   "%+.3f" % s["sumR"] if s["sumR"] is not None else "--",
                   "%+.4f" % s["meanR"] if s["meanR"] is not None else "--",
                   "%.1f%%" % (s["winRate"] * 100) if s["winRate"] is not None else "--"))

    lines = ["OBSERVATION INTEGRITY -- derived, read-only, adjudicates nothing",
             "  population: %s | strategy scope: %s" % (r["population"], scope),
             line("RAW PRESERVED POPULATION", raw),
             line("AUTHORITATIVE VERIFIED", auth),
             line("EXCLUDED (unverified)", exc)]
    if r["effectOfExclusion"] and exc["n"]:
        lines.append("  effect of exclusion: sumR %+.3f, meanR %+.4f"
                     % (r["effectOfExclusion"]["sumR"],
                        r["effectOfExclusion"]["meanR"]
                        if r["effectOfExclusion"]["meanR"] is not None else float("nan")))
    for f in r["findings"]:
        lines.append("    %s (%s) R=%s" % (f["observationId"], f["strategyId"], f["rMultiple"]))
        for v in f["violations"]:
            lines.append("      %-46s %s" % (v["ruleId"], v["detail"]))
    if not r["findings"]:
        lines.append("  no field-consistency violations in this population")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--population", default=to.FORWARD)
    parser.add_argument("--strategy", default=None,
                        help="scope to one strategyId (e.g. alex_g_sr_v1)")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    r = report(population=args.population, strategy_id=args.strategy)
    print(json.dumps(r, indent=2, sort_keys=True) if args.json else render(r))
    if args.write:
        os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
        with open(REPORT_PATH, "w", encoding="utf-8") as handle:
            json.dump(r, handle, indent=2, sort_keys=True)
            handle.write("\n")
        print("written to %s" % REPORT_PATH)
    # Exit 0: an unverified record is a REPORT, not a build failure. Failing the gate here
    # would create pressure to "fix" the corpus, which is the one thing that must not happen.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

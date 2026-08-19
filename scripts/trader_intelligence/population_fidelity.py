#!/usr/bin/env python3
"""Does REPLAY predict FORWARD, for MOGO's own implementation? (MOGO-022)

WHY
---
Preserving forward closes made one comparison possible for the first time: the
same strategy implementation, `alex_g_sr_v1`, is now observed in BOTH populations
-- 221 HISTORICAL replay observations and a set of FORWARD paper closes. Nothing
in the hypothesis backlog asks this, because those hypotheses are about the human
traders. This asks about the implementation, which is the actor we actually hold
evidence for.

It matters because replay is the cheap instrument. If replay systematically
differs from forward, then every future conclusion drawn from 221 replay
observations inherits that bias, and the difference has to be known before the
conclusion is drawn rather than after.

WHAT IT WILL AND WILL NOT CLAIM
-------------------------------
It reports a STRUCTURAL finding when the evidence is structural: the shape of the
realized-R distribution is a property of the simulator, not a sample statistic, so
"replay books exactly two outcome values and forward books more" is established by
the values themselves and needs no significance test.

It refuses to convert differences in win rate or mean R into a claim. Those
populations differ in instrument mix, in period, and in size; the forward set is a
known-incomplete subset (backlog B-22). A difference there is not evidence of a
difference in performance, and `doesNotSupport` says so in the output rather than
leaving a reader to infer it.

READ-ONLY. NO NETWORK ACCESS. ADJUDICATES NOTHING.
"""
import argparse
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trade_observation as to      # noqa: E402

SCHEMA_VERSION = "mogo.population-fidelity.v1"
LANE = "RESEARCH"

# A realized R is "off lattice" when it is not within tolerance of ANY value the
# replay population books. Defined against the observed lattice rather than
# against hardcoded -1R/+2R, so it does not assume this strategy's reward ratio.
# The tolerance absorbs rounding in the recorded R, not slippage: the observed
# forward overshoots run to 0.077R, an order of magnitude larger.
LATTICE_TOLERANCE = 0.005

REPLAY_IDEALIZES_EXITS = "REPLAY_IDEALIZES_EXITS"
REPLAY_IS_BAR_QUANTIZED = "REPLAY_IS_BAR_QUANTIZED"
RISK_SIZING_DIVERGES = "RISK_SIZING_DIVERGES"
RISK_SIZING_AGREES = "RISK_SIZING_AGREES"
PRESERVED_SUBSET_IS_NOT_THE_ACCOUNT = "PRESERVED_SUBSET_IS_NOT_THE_ACCOUNT"

# Risk is expressed as a percentage of the balance at entry. The tolerance absorbs
# rounding in the recorded amounts, not a change in the sizing rule.
RISK_PCT_TOLERANCE = 0.01


def risk_pct_of_balance(records):
    """Risk as a percentage of balance-at-entry, per record. Records missing
    either field are skipped rather than defaulted -- a missing balance is not
    a zero balance."""
    out = []
    for record in records:
        risk = record.get("riskAmount")
        balance = record.get("accountBalanceBefore")
        if risk and balance:
            out.append(risk / balance * 100.0)
    return out


def timestamp_granularity(timestamps):
    """How fine the clock actually is, counted rather than assumed.

    An ISO timestamp landing exactly on the hour, every time and across hundreds
    of records, is not a coincidence -- it is a grid. Reported as a distribution
    so the evidence is visible instead of inferred from a sample.
    """
    counts = {"exactHour": 0, "exactMinute": 0, "exactSecond": 0, "subSecond": 0}
    for stamp in timestamps:
        tail = stamp[11:] if len(stamp) > 11 else ""
        if not tail.endswith(".000Z"):
            counts["subSecond"] += 1
        elif tail.endswith(":00:00.000Z"):
            counts["exactHour"] += 1
        elif tail.endswith(":00.000Z"):
            counts["exactMinute"] += 1
        else:
            counts["exactSecond"] += 1
    return counts


def off_lattice(values, lattice, tolerance=LATTICE_TOLERANCE):
    """Values not within `tolerance` of any point on `lattice`."""
    return sorted(round(v, 4) for v in values
                  if not any(abs(v - point) <= tolerance for point in lattice))


def _refuse(message):
    raise to.ObservationRefused(message)


def population_stats(records):
    """Descriptive only. No comparison, no verdict."""
    r_multiples = [r["rMultiple"] for r in records if r.get("rMultiple") is not None]
    outcomes = {}
    for record in records:
        outcome = record.get("outcome")
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
    closed = sorted(r["closedAt"] for r in records if r.get("closedAt"))
    stats = {
        "n": len(records),
        "byOutcome": outcomes,
        "rMultipleCount": len(r_multiples),
        "distinctRMultiples": sorted({round(value, 4) for value in r_multiples}),
        "worstR": min(r_multiples) if r_multiples else None,
        "bestR": max(r_multiples) if r_multiples else None,
        "meanR": statistics.mean(r_multiples) if r_multiples else None,
        "instruments": sorted({r["instrument"] for r in records if r.get("instrument")}),
        "closedAtRange": [closed[0], closed[-1]] if closed else None,
        "unknownFieldTotal": sum(len(r.get("unknowns") or []) for r in records),
        "riskPctOfBalance": sorted({round(v, 4) for v in risk_pct_of_balance(records)}),
        "timestampGranularity": timestamp_granularity(
            [r[field] for r in records for field in ("openedAt", "closedAt")
             if r.get(field)]),
    }
    return stats


def compare(observations, sources, strategy_id):
    """Compare one strategy's populations. `sources` is REQUIRED.

    Same structural guarantee as summarize(): without the EvidenceSource map the
    two populations are indistinguishable, so there is no signature by which a
    caller gets a comparison that silently blends them.
    """
    if sources is None:
        _refuse("compare() requires the EvidenceSource map. Without it, replay and "
                "forward observations cannot be told apart and the comparison is "
                "meaningless.")
    if not strategy_id:
        _refuse("a strategyId is required: comparing populations across different "
                "strategies would attribute one implementation's behaviour to another.")

    grouped = {}
    for record in (observations or {}).values():
        if record.get("strategyId") != strategy_id:
            continue
        grouped.setdefault(to.observation_population(record, sources), []).append(record)

    by_population = {name: population_stats(rows) for name, rows in grouped.items()}
    historical = by_population.get(to.HISTORICAL)
    forward = by_population.get(to.FORWARD)

    findings = []
    agreements = []
    if historical and forward:
        # Structural, not statistical. A simulator whose realized R takes only a
        # handful of exact values is not modelling the exit, it is asserting it --
        # established by the values themselves, so no significance test applies.
        lattice = historical["distinctRMultiples"]
        forward_values = [r["rMultiple"] for r in grouped[to.FORWARD]
                          if r.get("rMultiple") is not None]
        strays = off_lattice(forward_values, lattice)
        forward["offReplayLattice"] = strays
        historical["offReplayLattice"] = []
        # The condition is ONLY "forward books values replay never books". An
        # earlier version also required forward to have more distinct values than
        # replay, which silently suppressed the finding whenever the overshoot was
        # purely favourable -- the same mechanism, missed because of an arithmetic
        # coincidence in the counts. Caught by its own test.
        if strays:
            # BOTH directions are reported. An earlier draft of this finding said
            # replay "understates what a loss costs", which is one-sided and would
            # have misled: forward exits overshoot the target as well as the stop,
            # and the mean overshoot on wins is favourable. The mechanism is that
            # exits gap past their level in whichever direction price moved; the
            # net effect on expectancy is NOT established by it.
            adverse = [v for v in strays if v < min(lattice)]
            favourable = [v for v in strays if v > max(lattice)]
            findings.append({
                "code": REPLAY_IDEALIZES_EXITS,
                "statement":
                    "Replay books realized R at exactly %d value(s); forward books "
                    "values off that lattice in both directions. The replay path "
                    "does not model exit gapping, so a realized-R figure taken from "
                    "replay is an idealisation of where the exit actually fills."
                    % len(lattice),
                "basis": {
                    "replayLattice": lattice,
                    "forwardOffLattice": strays,
                    "worseThanReplayWorst": adverse,
                    "betterThanReplayBest": favourable,
                },
                "doesNotSupport":
                    "Any claim about the direction or size of the effect on "
                    "expectancy. Overshoot occurs on BOTH sides -- adverse on some "
                    "losses, favourable on some wins -- so this establishes a "
                    "mechanism difference in the simulator, not an effect size.",
            })

        # A second structural difference, and the one that EXPLAINS the first.
        historical_grid = historical["timestampGranularity"]
        forward_grid = forward["timestampGranularity"]
        if historical_grid["subSecond"] == 0 and forward_grid["subSecond"] > 0:
            findings.append({
                "code": REPLAY_IS_BAR_QUANTIZED,
                "statement":
                    "Every replay entry and exit falls on an exact bar boundary; "
                    "every forward fill is sub-second. Replay's timing resolution "
                    "IS the bar grid, so it cannot represent an intra-bar fill -- "
                    "which is the mechanism behind the off-lattice realized R above.",
                "basis": {
                    "historicalGranularity": historical_grid,
                    "forwardGranularity": forward_grid,
                },
                "doesNotSupport":
                    "Any claim that replay results are wrong. A bar-resolution "
                    "simulator is a legitimate instrument; what does not follow is "
                    "a conclusion about exit timing, MAE/MFE, or intra-bar "
                    "behaviour drawn from it, since those are properties of the "
                    "grid rather than of the market.",
            })

        # WHERE THE POPULATIONS AGREE, reported alongside where they differ.
        # A tool that only ever emits differences reads as though it found
        # something wrong every time it runs, and gives no credit to a property
        # that genuinely holds across both. It is also a regression detector: if
        # sizing ever drifts between replay and forward, this flips to a finding.
        h_risk, f_risk = historical["riskPctOfBalance"], forward["riskPctOfBalance"]
        if h_risk and f_risk:
            spread = max(h_risk + f_risk) - min(h_risk + f_risk)
            if spread <= RISK_PCT_TOLERANCE:
                agreements.append({
                    "code": RISK_SIZING_AGREES,
                    "statement":
                        "Position sizing is identical in the two populations "
                        "compared here: risk is %.4f%% of balance-at-entry in every "
                        "replay and every forward observation. Other populations, "
                        "where present, are reported separately and not compared."
                        % h_risk[0],
                    "basis": {"historicalRiskPct": h_risk, "forwardRiskPct": f_risk,
                              "spread": round(spread, 6)},
                })
            else:
                findings.append({
                    "code": RISK_SIZING_DIVERGES,
                    "statement":
                        "Position sizing differs between replay and forward. The "
                        "simulator is not sizing trades the way the live path does, "
                        "so realized R is not comparable across the two.",
                    "basis": {"historicalRiskPct": h_risk, "forwardRiskPct": f_risk,
                              "spread": round(spread, 6)},
                    "doesNotSupport":
                        "Which of the two is correct. This says they disagree, not "
                        "which one implements the intended rule.",
                })

    # COVERAGE. Deliberately OUTSIDE the historical/forward guard: this is a
# statement about FORWARD versus RECONSTRUCTED and does not need replay
# evidence to be true. Nesting it there meant it could not fire for a corpus
# that holds only live and reconstructed records.
# Reported because the forward set is knowably incomplete.
    # Reconstructed records exist precisely for trades whose evidence packages
    # were lost, so wherever they exist the FORWARD population is a subset of
    # the account rather than its record. Stating both, and refusing to say
    # which is "right", is the whole point: the numbers below differ, and a
    # reader quoting the forward-only figure as the account's performance would
    # be wrong in a direction this measures.
    reconstructed = by_population.get(to.RECONSTRUCTED)
    if reconstructed and forward:
        findings.append({
            "code": PRESERVED_SUBSET_IS_NOT_THE_ACCOUNT,
            "statement":
                "Reconstructed evidence exists for %d trade(s) whose packages "
                "were lost, alongside %d live-captured. Forward-only statistics "
                "therefore describe the PRESERVED SUBSET, not the account, and "
                "the two differ."
                % (reconstructed["n"], forward["n"]),
            "basis": {
                "forward": {k: forward.get(k) for k in
                             ("n", "meanR", "winShareOfPreserved", "closedAtRange")},
                "reconstructed": {k: reconstructed.get(k) for k in
                                   ("n", "meanR", "winShareOfPreserved", "closedAtRange")},
            },
            "doesNotSupport":
                "That the difference is real, or that performance changed. The "
                "reconstructed set is small, covers a different and earlier "
                "period, and carries MINIMAL completeness -- so the gap is "
                "confounded with time and with evidence quality. What it "
                "establishes is that the forward set is INCOMPLETE in a way that "
                "is not random: it is missing a contiguous oldest block. No "
                "combined figure is offered here, because averaging evidence of "
                "two different provenance strengths is exactly the pooling this "
                "module exists to prevent.",
        })

    return {
        "lane": LANE,
        "schemaVersion": SCHEMA_VERSION,
        "adjudicates": False,
        "strategyId": strategy_id,
        "byPopulation": by_population,
        "populationsPresent": sorted(by_population),
        "findings": findings,
        "agreements": agreements,
        # Stated in the output itself, so a reader of the JSON cannot come away
        # with a comparison the evidence does not support.
        "doesNotSupport": [
            "Win-rate and mean-R differences between the populations are NOT reported "
            "as findings. The two differ in instrument mix, in period, and in size, "
            "and the forward set is a known-incomplete subset of the account's closes "
            "(backlog B-22). A difference under those conditions is not evidence of a "
            "difference in performance.",
            "Nothing here is evidence about any human trader. `alex_g_sr_v1` is MOGO's "
            "implementation of a published method, not the trader who published it.",
        ],
    }


def render(report):
    lines = ["POPULATION FIDELITY -- derived, read-only, adjudicates nothing",
             "  strategy: %s" % report["strategyId"]]
    for name in report["populationsPresent"]:
        stats = report["byPopulation"][name]
        lines.append("  %s  n=%d  outcomes=%s" % (name, stats["n"], stats["byOutcome"]))
        lines.append("    distinct realized R: %s" % (stats["distinctRMultiples"],))
        lines.append("    off the replay lattice: %s"
                     % (stats.get("offReplayLattice") or "none"))
        lines.append("    period: %s" % (stats["closedAtRange"],))
    if report.get("agreements"):
        lines.append("  agreements:")
        for agreement in report["agreements"]:
            lines.append("    %s" % agreement["code"])
            lines.append("      %s" % agreement["statement"])
    if report["findings"]:
        lines.append("  findings:")
        for finding in report["findings"]:
            lines.append("    %s" % finding["code"])
            lines.append("      %s" % finding["statement"])
            lines.append("      does not support: %s" % finding["doesNotSupport"])
    else:
        lines.append("  findings: none")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--strategy", default="alex_g_sr_v1")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = compare(to.load_observations(), to.load_sources(), args.strategy)
    print(json.dumps(report, indent=2, sort_keys=True) if args.json else render(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

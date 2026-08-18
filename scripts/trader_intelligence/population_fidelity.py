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

    return {
        "lane": LANE,
        "schemaVersion": SCHEMA_VERSION,
        "adjudicates": False,
        "strategyId": strategy_id,
        "byPopulation": by_population,
        "populationsPresent": sorted(by_population),
        "findings": findings,
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

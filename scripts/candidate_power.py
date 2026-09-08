#!/usr/bin/env python3
"""Can this candidate's effect clear its costs, and could this sample see it if it did?

WHY THIS EXISTS. Six arms were built and tested in this project before anyone asked either
question in advance. Two of them could have been dismissed in an hour:

  tod_session_v1  a 0.58-pip gross effect against a ~0.8-pip spread. It was negative before the
                  statistics began, and the sample could only have resolved an effect of 2.02 pips
                  anyway -- 3.5x larger than the one being looked for.
  carry_g10_v1    a real 3.01%/yr effect, of which the broker keeps 1.09%/yr. The 1.92%/yr that
                  survives sits below the 4.13%/yr that 22.5 years of a ~10%-volatility basket can
                  distinguish from zero.

Both were built first and costed afterwards. This script is the check that goes first.

TWO FLOORS, AND A CANDIDATE MUST CLEAR BOTH.

  COST FLOOR       the effect has to be bigger than what it costs to capture. Spread for a trade
                   rule, financing markup for a carry rule. Below this the strategy loses money
                   whether or not the effect is real.

  DETECTION FLOOR  1.96 * sigma / sqrt(n). Below this the effect cannot be told apart from zero at
                   the sample available, so the experiment returns "no effect found" REGARDLESS of
                   whether one exists. A null from an underpowered test is not evidence of absence.

The second is the one nobody checks, and it is the one that makes a null result meaningless.

USAGE
  python3 scripts/candidate_power.py --effect 0.58 --sigma 32.6 --n 1002 --cost 0.8 --unit pips
  python3 scripts/candidate_power.py --effect 3.01 --sigma 10 --n 22.5 --cost 1.09 --unit %/yr
  python3 scripts/candidate_power.py --selftest
"""
import argparse, math, sys

Z95 = 1.959963984540054


def detection_floor(sigma, n):
    """Smallest effect distinguishable from zero at 95%, given spread `sigma` over `n` observations.

    Returns None for a sample or spread that cannot support the question, rather than a number --
    an unanswerable question must not come back as a small floor that looks easy to clear.
    """
    if sigma is None or n is None:
        return None
    if not (sigma > 0) or not (n > 0):
        return None
    return Z95 * sigma / math.sqrt(n)


def samples_needed(effect, sigma):
    """How many observations to resolve `effect` at 95%. None when the question is degenerate."""
    if effect is None or sigma is None:
        return None
    if not (sigma > 0) or effect == 0:
        return None
    return math.ceil((Z95 * sigma / abs(effect)) ** 2)


def assess(effect, sigma, n, cost=0.0):
    """The verdict, as a record. Never a sentence -- the caller decides what it means."""
    cost = cost or 0.0
    net = effect - cost
    floor = detection_floor(sigma, n)
    out = {
        "effect_gross": effect,
        "cost": cost,
        "effect_net": net,
        "detection_floor": floor,
        "clears_cost": net > 0,
        # Compared on NET, not gross: an effect the costs consume is not an effect you can detect
        # in a live result, however visible it is in a costless backtest.
        "clears_detection": (floor is not None) and (abs(net) > floor),
        "samples_needed_for_net": samples_needed(net, sigma),
        "samples_available": n,
    }
    out["worth_building"] = bool(out["clears_cost"] and out["clears_detection"])
    # The distinct reasons a candidate fails, kept separate because they call for different actions:
    # a cost failure kills the idea at this venue; a power failure means get more data or measure
    # something with a tighter error bar, and says NOTHING about whether the effect is real.
    reasons = []
    if not out["clears_cost"]:
        reasons.append("COST: the effect is smaller than the cost of capturing it")
    if floor is None:
        reasons.append("POWER: sigma or n missing, so detectability is unknown -- not zero")
    elif not out["clears_detection"]:
        reasons.append("POWER: below what this sample can resolve; a null here would mean nothing")
    out["reasons"] = reasons
    return out


def render(a, unit="R"):
    L = []
    L.append(f"  gross effect      {a['effect_gross']:+.4f} {unit}")
    L.append(f"  cost              {a['cost']:.4f} {unit}")
    L.append(f"  NET effect        {a['effect_net']:+.4f} {unit}   "
             f"{'clears cost' if a['clears_cost'] else 'BELOW COST -- loses money either way'}")
    if a["detection_floor"] is None:
        L.append("  detection floor   unknown (sigma or n not supplied)")
    else:
        L.append(f"  detection floor   {a['detection_floor']:.4f} {unit}   "
                 f"(1.96 x sigma / sqrt({a['samples_available']:g}))")
    if a["samples_needed_for_net"] is not None:
        L.append(f"  samples needed    {a['samples_needed_for_net']:,} to resolve the NET effect; "
                 f"{a['samples_available']:g} available")
    L.append(f"  VERDICT           {'worth building' if a['worth_building'] else 'DO NOT BUILD YET'}")
    for r in a["reasons"]:
        L.append(f"                    - {r}")
    return "\n".join(L)


def selftest():
    """Fixtures are the project's own six arms. If this script had existed, four would not have
    been built in the form they were."""
    fails = []

    def check(name, got, want):
        if got != want:
            fails.append(f"{name}: expected {want}, got {got}")

    # tod_session_v1, EUR/USD. Gross 0.58 pips, sigma from its own SE (1.03 * sqrt(1002)).
    tod = assess(0.58, 1.03 * math.sqrt(1002), 1002, cost=0.8)
    check("tod clears_cost", tod["clears_cost"], False)
    check("tod worth_building", tod["worth_building"], False)

    # carry_g10_v1. A REAL 3.01%/yr effect that still fails -- the case that proves a candidate can
    # be genuine and not worth building, which is the whole point of the cost floor.
    carry = assess(3.01, 10.0, 22.5, cost=1.09)
    check("carry clears_cost", carry["clears_cost"], True)
    check("carry clears_detection", carry["clears_detection"], False)
    check("carry worth_building", carry["worth_building"], False)

    # A genuinely good candidate must pass, or the gate is just a rejector.
    good = assess(0.30, 1.0, 5000, cost=0.05)
    check("good clears_cost", good["clears_cost"], True)
    check("good clears_detection", good["clears_detection"], True)
    check("good worth_building", good["worth_building"], True)

    # A large NEGATIVE effect is detectable -- detection is about magnitude, not direction. Two of
    # this project's arms were in exactly this position and measured real losses.
    neg = assess(-0.092, 1.0, 502, cost=0.0)
    check("negative is detectable", neg["clears_detection"], True)
    check("negative not worth building", neg["worth_building"], False)

    # Degenerate inputs must refuse rather than return a flattering small floor.
    check("zero sigma floor", detection_floor(0, 100), None)
    check("zero n floor", detection_floor(1.0, 0), None)
    check("negative sigma floor", detection_floor(-1, 100), None)
    check("missing sigma floor", detection_floor(None, 100), None)
    check("zero-effect samples", samples_needed(0, 1.0), None)
    check("zero-sigma samples", samples_needed(0.1, 0), None)
    unknown = assess(0.5, None, 1000, cost=0.1)
    check("unknown power is not a pass", unknown["worth_building"], False)
    check("unknown power says unknown", any("not zero" in r for r in unknown["reasons"]), True)

    # Cost is charged before detection, so a costless-but-real effect still fails on net.
    eaten = assess(0.10, 1.0, 100000, cost=0.099)
    check("cost charged before detection", eaten["clears_detection"], False)

    # Sanity: the arithmetic itself.
    check("floor arithmetic", round(detection_floor(10.0, 100), 6), round(Z95, 6))
    check("samples arithmetic", samples_needed(0.1, 1.0), math.ceil((Z95 / 0.1) ** 2))

    for f in fails:
        print("FAIL -- " + f)
    print(f"selftest: {'PASS' if not fails else 'FAIL'} ({len(fails)} failure(s))")
    return 1 if fails else 0


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--effect", type=float, help="gross effect per observation, in --unit")
    p.add_argument("--sigma", type=float, help="standard deviation of the per-observation outcome")
    p.add_argument("--n", type=float, help="observations available")
    p.add_argument("--cost", type=float, default=0.0, help="cost per observation, same unit")
    p.add_argument("--unit", default="R")
    p.add_argument("--selftest", action="store_true")
    a = p.parse_args()
    if a.selftest:
        return selftest()
    if a.effect is None or a.n is None:
        p.error("--effect and --n are required (or use --selftest)")
    print(render(assess(a.effect, a.sigma, a.n, a.cost), a.unit))
    return 0


if __name__ == "__main__":
    sys.exit(main())

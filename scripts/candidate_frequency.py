#!/usr/bin/env python3
"""How long would it take to CONFIRM this candidate? Usually longer than anyone has.

WHY THIS EXISTS. `candidate_power.py` asks whether a sample can resolve an effect. This asks
the question one level up, and it is the one that decides what is worth looking for at all:

    given that an effect occurs f times a year, how many YEARS of observation does it take
    before the result means anything?

The answer is brutal for exactly the candidates that look most attractive.

THE TENSION THIS MEASURES. A candidate has to clear two floors that pull in opposite
directions:

  to clear COST      the effect must be LARGE relative to spread. In a liquid market, large
                     effects come from mechanical flows -- rebalancing, index reconstitution,
                     settlement, expiry -- and those happen on a calendar, a dozen times a
                     year, not continuously.

  to clear POWER     you need MANY observations. At a dozen a year, "many" is measured in
                     decades.

So the candidates big enough to be worth trading are usually too rare to confirm, and the
candidates frequent enough to confirm are usually too small to trade. This script puts a
number on which side of that trade-off a given idea falls, BEFORE anyone builds it.

WHAT A LONG CONFIRMATION TIME DOES AND DOES NOT MEAN. It does NOT mean the effect is fake.
It means the effect cannot be established by forward observation on a human timescale, so
the evidence has to come from history -- which is precisely when a pre-registered holdout
split (`holdout_gate.py`) stops being good practice and becomes the only honest option.

USAGE
  python3 scripts/candidate_frequency.py --effect 25 --sigma 86.5 --cost 10 \\
      --per-year 12 --unit bp
  python3 scripts/candidate_frequency.py --table
  python3 scripts/candidate_frequency.py --selftest
"""
import argparse, math, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from candidate_power import samples_needed, Z95  # noqa: E402

# Beyond this, "wait and see" stops being a plan a person can act on.
HUMAN_HORIZON_YEARS = 5.0


def years_to_confirm(effect_net, sigma, per_year):
    """Years of observation before the NET effect clears its own detection floor.

    None when the question is degenerate -- a zero effect, a zero spread, or a candidate that
    never occurs. An unanswerable question must not return a small, encouraging number.
    """
    if per_year is None or not (per_year > 0):
        return None
    n = samples_needed(effect_net, sigma)
    if n is None:
        return None
    return n / per_year


def assess_frequency(effect, sigma, cost, per_year, history_years=None):
    """The verdict as a record. Whether it is tradeable, and whether it is knowable."""
    cost = cost or 0.0
    net = effect - cost
    yrs = years_to_confirm(net, sigma, per_year)
    n_needed = samples_needed(net, sigma)
    out = {
        "effect_gross": effect, "cost": cost, "effect_net": net,
        "per_year": per_year,
        "samples_needed": n_needed,
        "years_to_confirm": yrs,
        "clears_cost": net > 0,
        # Confirmable by WAITING -- the thing a forward paper test can actually deliver.
        "confirmable_forward": (yrs is not None) and yrs <= HUMAN_HORIZON_YEARS,
    }
    # Confirmable from HISTORY, if enough history exists and is trustworthy. This is the
    # escape hatch for rare effects, and the reason the holdout gate exists.
    if history_years is not None and per_year:
        avail = history_years * per_year
        out["history_years"] = history_years
        out["samples_in_history"] = avail
        out["confirmable_from_history"] = (n_needed is not None) and avail >= n_needed
    else:
        out["confirmable_from_history"] = None
    return out


def render(a, unit="R"):
    L = [f"  gross effect      {a['effect_gross']:+.4g} {unit}",
         f"  cost              {a['cost']:.4g} {unit}",
         f"  NET effect        {a['effect_net']:+.4g} {unit}   "
         f"{'clears cost' if a['clears_cost'] else 'BELOW COST'}",
         f"  occurs            {a['per_year']:g} times a year"]
    if a["samples_needed"] is None:
        L.append("  samples needed    undefined (zero effect or zero spread)")
    else:
        L.append(f"  samples needed    {a['samples_needed']:,}")
    if a["years_to_confirm"] is None:
        L.append("  years to confirm  undefined")
    else:
        L.append(f"  years to confirm  {a['years_to_confirm']:.1f}")
    if a.get("confirmable_from_history") is not None:
        L.append(f"  in {a['history_years']:g}y of history  "
                 f"{a['samples_in_history']:,.0f} observations -- "
                 f"{'ENOUGH' if a['confirmable_from_history'] else 'NOT ENOUGH'}")
    if not a["clears_cost"]:
        v = "DEAD -- costs exceed the effect"
    elif a["confirmable_forward"]:
        v = "TRADEABLE AND CONFIRMABLE BY WAITING"
    elif a.get("confirmable_from_history"):
        v = "TRADEABLE, but only confirmable FROM HISTORY -- needs a pre-registered holdout"
    else:
        v = "TRADEABLE ON PAPER, NOT CONFIRMABLE -- would be an act of faith"
    L.append(f"  VERDICT           {v}")
    return "\n".join(L)


ARCHETYPES = [
    # name, gross effect, sigma, cost, events/yr, unit, years of usable history
    ("chart pattern, intraday", 0.005, 1.0, 0.05, 2500, "R", 10),
    ("chart pattern, optimistic", 0.05, 1.0, 0.05, 2500, "R", 10),
    ("time-of-day session", 0.58, 32.6, 0.80, 1000, "pips", 10),
    ("carry, G10 basket", 3.01, 10.0, 1.09, 1, "%/yr", 22.5),
    ("Treasury month-end, 10y", 25.0, 86.5, 10.0, 12, "bp", 36),
    ("index reconstitution", 40.0, 150.0, 15.0, 4, "bp", 36),
    ("equity drift (buy and hold)", 8.0, 16.0, 0.1, 1, "%/yr", 100),
]


def table():
    print(f"{'candidate':<30}{'net':>10}{'/yr':>7}{'n need':>9}{'years':>8}   verdict")
    print("-" * 100)
    for name, eff, sig, cost, f, unit, hist in ARCHETYPES:
        a = assess_frequency(eff, sig, cost, f, hist)
        y = a["years_to_confirm"]
        ystr = "--" if y is None else (f"{y:.1f}" if y < 1000 else ">1000")
        nstr = "--" if a["samples_needed"] is None else f"{a['samples_needed']:,}"
        if not a["clears_cost"]:
            v = "dead: cost"
        elif a["confirmable_forward"]:
            v = "confirmable by waiting"
        elif a.get("confirmable_from_history"):
            v = "history only -- needs holdout"
        else:
            v = "not confirmable"
        print(f"{name:<30}{a['effect_net']:>+10.4g}{f:>7g}{nstr:>9}{ystr:>8}   {v}")
    print("-" * 100)
    print("Units differ per row -- read each row against itself, never across rows.")


def selftest():
    fails = []

    def check(name, got, want):
        if got != want:
            fails.append(f"{name}: expected {want}, got {got}")

    # The Treasury month-end case this script was written for. 15bp net, sigma 86.5 ->
    # 128 observations at 12 a year -> 10.7 years. Tradeable, not confirmable by waiting.
    t = assess_frequency(25.0, 86.5, 10.0, 12, history_years=36)
    check("treasury n", t["samples_needed"], 128)
    check("treasury years", round(t["years_to_confirm"], 1), 10.7)
    check("treasury clears cost", t["clears_cost"], True)
    check("treasury not forward-confirmable", t["confirmable_forward"], False)
    check("treasury history is enough", t["confirmable_from_history"], True)

    # A frequent, tiny effect: confirmable fast, but dead on cost. Both floors must be
    # reported independently -- a candidate can fail one and pass the other.
    c = assess_frequency(0.005, 1.0, 0.05, 2500)
    check("chart pattern fails cost", c["clears_cost"], False)
    check("chart pattern net is negative", c["effect_net"] < 0, True)
    # Detection is about MAGNITUDE, so a large negative net is still resolvable. The script
    # must not report a cost failure as if it were a power failure.
    check("chart pattern still has a finite horizon", c["years_to_confirm"] is not None, True)

    # A big, frequent effect must come back confirmable, or the script is only a rejector.
    g = assess_frequency(0.30, 1.0, 0.05, 2500)
    check("good candidate clears cost", g["clears_cost"], True)
    check("good candidate confirmable", g["confirmable_forward"], True)

    # An effect that occurs once a year cannot be confirmed however large, unless it is huge
    # relative to its own spread. This is the structural point of the script.
    rare = assess_frequency(25.0, 86.5, 10.0, 1)
    check("rare effect needs 128 years", round(rare["years_to_confirm"]), 128)
    check("rare effect not forward-confirmable", rare["confirmable_forward"], False)

    # History rescues a rare effect only when there IS enough history.
    short = assess_frequency(25.0, 86.5, 10.0, 12, history_years=5)
    check("5y history is not enough", short["confirmable_from_history"], False)

    # Degenerate inputs refuse rather than flatter.
    check("zero frequency", years_to_confirm(1.0, 1.0, 0), None)
    check("negative frequency", years_to_confirm(1.0, 1.0, -3), None)
    check("zero net effect", years_to_confirm(0.0, 1.0, 12), None)
    check("zero sigma", years_to_confirm(1.0, 0.0, 12), None)
    z = assess_frequency(5.0, 1.0, 5.0, 12)      # net exactly zero
    check("zero net is not confirmable", z["confirmable_forward"], False)
    check("zero net does not clear cost", z["clears_cost"], False)

    # Arithmetic, independent of the helper.
    check("years arithmetic",
          round(years_to_confirm(10.0, 100.0, 4), 4),
          round(math.ceil((Z95 * 100.0 / 10.0) ** 2) / 4, 4))

    for f in fails:
        print("FAIL -- " + f)
    print(f"selftest: {'PASS' if not fails else 'FAIL'} ({len(fails)} failure(s))")
    return 1 if fails else 0


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--effect", type=float); p.add_argument("--sigma", type=float)
    p.add_argument("--cost", type=float, default=0.0)
    p.add_argument("--per-year", type=float, help="how many times a year the effect occurs")
    p.add_argument("--history-years", type=float, help="years of usable history available")
    p.add_argument("--unit", default="R")
    p.add_argument("--table", action="store_true")
    p.add_argument("--selftest", action="store_true")
    a = p.parse_args()
    if a.selftest:
        return selftest()
    if a.table:
        table(); return 0
    if a.effect is None or a.sigma is None or a.per_year is None:
        p.error("--effect, --sigma and --per-year are required (or --table / --selftest)")
    print(render(assess_frequency(a.effect, a.sigma, a.cost, a.per_year, a.history_years),
                 a.unit))
    return 0


if __name__ == "__main__":
    sys.exit(main())

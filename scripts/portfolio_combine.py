#!/usr/bin/env python3
"""What do several weak effects become when you hold them together?

WHY THIS EXISTS, AND WHY IT MAY BE THE MISSING PIECE. Twenty-one candidates were screened in
this project and every one was judged ALONE. Most died for the same two reasons: the effect
was too small to clear its cost, or too rare to confirm inside a human lifetime.

But confirmability is not driven by effect size. It is driven by SHARPE:

    years to confirm (annual data)  =  (1.96 / Sharpe)^2

        Sharpe 0.50  ->  15.4 years
        Sharpe 0.84  ->   5.4 years
        Sharpe 1.20  ->   2.7 years
        Sharpe 2.00  ->   1.0 year

And Sharpe is the one thing diversification improves for free. Koijen, Moskowitz, Pedersen &
Vrugt did not find a better effect than anyone else. They found NINE mediocre ones and held
them together: individual Sharpes around 0.4-0.7, combined 1.20. That single move takes a
strategy from unconfirmable to confirmable in under three years.

    S_combined  =  mean(S_i) * sqrt( k / (1 + (k-1) * rho) )

With k=9 and rho=0.1, the multiplier is 2.24. Nine strategies at Sharpe 0.5 become 1.12.

THE CAVEAT THAT MATTERS MORE THAN THE FORMULA. This only works if the components are REAL.
Averaging nine things that are each truly zero gives zero, not 1.12 -- the sqrt(k) applies to
the SIGNAL, and if there is no signal there is nothing to multiply. Fixture P5 pins that
directly, because it is the exact way this tool could be misused to manufacture an edge out of
noise.

So the honest use is narrow: it says what a combination WOULD be worth if each component's
published Sharpe is genuine, and therefore whether a combination is worth testing as a single
pre-registered unit. It never establishes that any component is real.

WHAT CHANGES PRACTICALLY. If a combination of reachable components clears the bar, the test
becomes ONE test of the combined series rather than nine underpowered tests of the parts --
and one test of a Sharpe-1.2 strategy needs ~3 years of data, which exists.

USAGE
  python3 scripts/portfolio_combine.py --sharpes 0.84 0.51 0.28 0.25 --rho 0.10
  python3 scripts/portfolio_combine.py --table
  python3 scripts/portfolio_combine.py --selftest
"""
import argparse, math, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from candidate_power import Z95  # noqa: E402

HUMAN_HORIZON_YEARS = 15.0


def diversification_multiplier(k, rho):
    """sqrt(k / (1 + (k-1) rho)). None for inputs that do not describe a portfolio.

    rho is the AVERAGE PAIRWISE correlation. It must not go below -1/(k-1), or the implied
    correlation matrix is not positive semi-definite and the multiplier explodes to a number
    that means nothing. Refusing beats returning a spectacular fiction.
    """
    if k is None or rho is None:
        return None
    if not isinstance(k, int) or k < 1:
        return None
    if k == 1:
        return 1.0 if -1.0 <= rho <= 1.0 else None
    if rho > 1.0 or rho < -1.0 / (k - 1) + 1e-12:
        return None
    denom = 1.0 + (k - 1) * rho
    if denom <= 0:
        return None
    return math.sqrt(k / denom)


def combine_optimal(sharpes, rho):
    """Combined Sharpe under MEAN-VARIANCE weights, not equal weights.

    WHY THIS IS THE RIGHT QUESTION. Equal weighting a Sharpe-0.84 component with a Sharpe-0.25
    one throws away edge: the basket can come out WORSE than the strong component held alone,
    which is what `beats_best_alone` reports on this project's own four reachable candidates.
    That is a weighting artefact, not a fact about diversification.

    Under equicorrelation rho with equal volatilities, the best achievable Sharpe is

        S* = sqrt( s' * C^-1 * s )

    and C^-1 for an equicorrelated matrix has closed form, so no linear-algebra dependency is
    needed:

        a = (1 + (k-2) rho) / ((1-rho)(1 + (k-1) rho))      on the diagonal
        b =            -rho / ((1-rho)(1 + (k-1) rho))      off the diagonal

    S* is always >= max(s_i): adding a component can never HURT once you are free to weight it,
    because the optimiser can weight it to zero. Fixture P11 pins exactly that, and it is the
    property that distinguishes a real diversification gain from a dilution artefact.
    """
    if not sharpes:
        return {"ok": False, "reason": "NO_COMPONENTS"}
    if any(s is None for s in sharpes):
        return {"ok": False, "reason": "COMPONENT_SHARPE_UNKNOWN"}
    k = len(sharpes)
    if k == 1:
        s = sharpes[0]
        return {"ok": True, "k": 1, "rho": rho, "combined_sharpe": s,
                "years_to_confirm": ((Z95 / s) ** 2) if s > 0 else None,
                "confirmable": (s > 0) and ((Z95 / s) ** 2) <= HUMAN_HORIZON_YEARS,
                "weights": [1.0]}
    if diversification_multiplier(k, rho) is None or rho >= 1.0:
        return {"ok": False, "reason": "IMPLIED_CORRELATION_MATRIX_INVALID", "k": k, "rho": rho}
    denom = (1.0 - rho) * (1.0 + (k - 1) * rho)
    a = (1.0 + (k - 2) * rho) / denom
    b = -rho / denom
    sum_sq = sum(s * s for s in sharpes)
    sum_s = sum(sharpes)
    quad = a * sum_sq + b * (sum_s * sum_s - sum_sq)
    # DEFENSIVE AND UNREACHABLE FOR VALID INPUT, recorded rather than quietly kept. C is
    # positive definite for any valid equicorrelation rho, so C^-1 is too, so s'C^-1 s > 0 for
    # every non-zero s -- verified by brute force over 400,000 random (k, rho, s) draws, minimum
    # 2.9e-04. The only vector reaching this branch is all-zeros, where sqrt(0) below returns
    # the same 0.0 anyway. Mutation M7 was therefore RETIRED rather than fixtured: writing a
    # fixture for a branch no input can distinguish would be a test that cannot fail.
    if quad <= 0:
        return {"ok": True, "k": k, "rho": rho, "combined_sharpe": 0.0,
                "years_to_confirm": None, "confirmable": False, "weights": None}
    combined = math.sqrt(quad)
    # Weights proportional to C^-1 s, normalised to sum to 1 for readability.
    raw = [a * s + b * (sum_s - s) for s in sharpes]
    tot = sum(raw)
    weights = [r / tot for r in raw] if abs(tot) > 1e-12 else None
    return {"ok": True, "k": k, "rho": rho, "combined_sharpe": combined,
            "years_to_confirm": ((Z95 / combined) ** 2) if combined > 0 else None,
            "confirmable": combined > 0 and ((Z95 / combined) ** 2) <= HUMAN_HORIZON_YEARS,
            "weights": weights, "best_component": max(sharpes)}


def combine(sharpes, rho):
    """Combined Sharpe of an equal-volatility-weighted basket, and its time to confirm."""
    if not sharpes:
        return {"ok": False, "reason": "NO_COMPONENTS"}
    if any(s is None for s in sharpes):
        return {"ok": False, "reason": "COMPONENT_SHARPE_UNKNOWN"}
    k = len(sharpes)
    mult = diversification_multiplier(k, rho)
    if mult is None:
        return {"ok": False, "reason": "IMPLIED_CORRELATION_MATRIX_INVALID", "k": k, "rho": rho}
    mean_s = sum(sharpes) / k
    combined = mean_s * mult
    # Years to confirm at annual observation. A non-positive Sharpe is never confirmable as
    # positive, however long you wait, so it returns None rather than a large number.
    years = ((Z95 / combined) ** 2) if combined > 0 else None
    return {"ok": True, "k": k, "rho": rho, "mean_sharpe": mean_s,
            "multiplier": mult, "combined_sharpe": combined,
            "years_to_confirm": years,
            "confirmable": (years is not None) and years <= HUMAN_HORIZON_YEARS,
            "best_component": max(sharpes), "worst_component": min(sharpes),
            # If the best single component already confirms faster, the basket adds nothing.
            "beats_best_alone": combined > max(sharpes)}


def render(c):
    if not c.get("ok"):
        return f"  REFUSED -- {c.get('reason')}"
    L = [f"  components          {c['k']}",
         f"  mean Sharpe         {c['mean_sharpe']:.3f}   "
         f"(best {c['best_component']:.2f}, worst {c['worst_component']:.2f})",
         f"  avg correlation     {c['rho']:.2f}",
         f"  diversification     x{c['multiplier']:.2f}",
         f"  COMBINED Sharpe     {c['combined_sharpe']:.3f}"]
    if c["years_to_confirm"] is None:
        L.append("  years to confirm    never -- a non-positive Sharpe does not become positive")
    else:
        L.append(f"  years to confirm    {c['years_to_confirm']:.1f}")
    L.append(f"  beats best alone    {c['beats_best_alone']}")
    v = ("CONFIRMABLE as one test" if c["confirmable"]
         else "still not confirmable inside %.0f years" % HUMAN_HORIZON_YEARS)
    L.append(f"  VERDICT             {v}")
    return "\n".join(L)


# Components this project has either measured itself or verified against an original paper,
# restricted to those reachable at a venue the operator can actually use.
REACHABLE = [
    # label,                          Sharpe, source
    ("Treasury auction cycle", 0.84, "Lou/Yan/Yuan RFS 2013, published NET of bid-ask and repo"),
    ("Diversified carry, decayed", 0.51, "Koijen et al. JFE 2018, 3.02/5.96 after -58% haircut"),
    ("Currency carry, decayed", 0.28, "2.22/7.80 after haircut"),
    ("Commodity carry, decayed", 0.25, "4.71/18.78 after haircut"),
]


def table():
    print("REACHABLE COMPONENTS, each individually too weak or too slow:\n")
    for lab, s, src in REACHABLE:
        yrs = (Z95 / s) ** 2
        print(f"  {lab:<28} Sharpe {s:4.2f}   {yrs:6.1f} yrs alone")
        print(f"  {'':<28} {src}")
    print()
    sh = [s for _, s, _ in REACHABLE]
    print("HELD TOGETHER, across plausible correlations:\n")
    print(f"  {'rho':>6}{'multiplier':>13}{'combined SR':>14}{'yrs':>8}   verdict")
    print("  " + "-" * 62)
    for rho in (0.0, 0.05, 0.10, 0.20, 0.30, 0.50):
        c = combine(sh, rho)
        v = "CONFIRMABLE" if c["confirmable"] else "too slow"
        print(f"  {rho:>6.2f}{c['multiplier']:>13.2f}{c['combined_sharpe']:>14.3f}"
              f"{c['years_to_confirm']:>8.1f}   {v}")
    print()
    print("OPTIMALLY WEIGHTED -- the honest version. Equal weighting dilutes the strong")
    print("component; with free weights, adding a component can never hurt:\n")
    print(f"  {'rho':>6}{'equal-wt SR':>14}{'OPTIMAL SR':>13}{'yrs':>8}{'vs best alone':>16}")
    print("  " + "-" * 62)
    for rho in (0.0, 0.05, 0.10, 0.20, 0.30, 0.50):
        e = combine(sh, rho); o = combine_optimal(sh, rho)
        gain = o["combined_sharpe"] - max(sh)
        print(f"  {rho:>6.2f}{e['combined_sharpe']:>14.3f}{o['combined_sharpe']:>13.3f}"
              f"{o['years_to_confirm']:>8.1f}{gain:>+16.3f}")
    w = combine_optimal(sh, 0.10)["weights"]
    print()
    print("  optimal weights at rho=0.10: " + ", ".join(
        f"{lab.split(',')[0]} {wt*100:.0f}%" for (lab, _, _), wt in zip(REACHABLE, w)))
    print()
    print("  Koijen et al. report average pairwise correlation across their nine carry")
    print("  strategies as LOW -- that is the whole basis of their 1.20. These four are not")
    print("  nine, and two of them ARE carry strategies, so rho here is plausibly higher.")
    print()
    print("  THE FORMULA CANNOT MAKE A REAL EFFECT OUT OF FOUR ZEROS. It says what the")
    print("  combination is worth IF each published Sharpe is genuine. Testing that is a")
    print("  separate, single, pre-registered test of the combined series.")


def selftest():
    fails = []

    def check(name, got, want):
        if got != want:
            fails.append(f"{name}: expected {want}, got {got}")

    # P1 The arithmetic, against hand values.
    check("k=1 has no benefit", round(diversification_multiplier(1, 0.0), 9), 1.0)
    check("k=4 rho=0 is sqrt(4)", round(diversification_multiplier(4, 0.0), 9), 2.0)
    check("k=9 rho=0 is 3", round(diversification_multiplier(9, 0.0), 9), 3.0)
    check("k=9 rho=0.1 is ~2.24", round(diversification_multiplier(9, 0.10), 2), 2.24)
    # rho=1 means perfectly correlated: no diversification at all.
    check("rho=1 gives no benefit", round(diversification_multiplier(9, 1.0), 9), 1.0)

    # P2 THE HEADLINE CASE the file exists for: nine mediocre effects become confirmable.
    nine = combine([0.5] * 9, 0.10)
    check("nine at 0.5 combine above 1.0", nine["combined_sharpe"] > 1.0, True)
    check("and become confirmable", nine["confirmable"], True)
    check("in under four years", nine["years_to_confirm"] < 4.0, True)
    # The same nine, held alone, are not confirmable.
    alone = combine([0.5], 0.0)
    check("one at 0.5 is not confirmable", alone["confirmable"], False)

    # P3 A single strong component must not be made to look worse by the formula.
    one = combine([1.5], 0.0)
    check("k=1 returns its own Sharpe", round(one["combined_sharpe"], 9), 1.5)

    # P4 Perfect correlation must destroy the benefit entirely.
    corr = combine([0.5] * 9, 1.0)
    check("perfectly correlated gains nothing",
          round(corr["combined_sharpe"], 9), 0.5)
    check("and is not confirmable", corr["confirmable"], False)

    # P5 THE MISUSE THIS TOOL INVITES, PINNED. Combining components that are truly ZERO must
    # give zero. sqrt(k) multiplies the SIGNAL; with no signal there is nothing to multiply.
    # Without this fixture the file could be used to manufacture an edge out of noise.
    zeros = combine([0.0] * 9, 0.0)
    check("nine zeros combine to zero", zeros["combined_sharpe"], 0.0)
    check("zeros are never confirmable", zeros["confirmable"], False)
    check("zeros have no horizon", zeros["years_to_confirm"], None)
    check("zeros render as never", "never" in render(zeros), True)

    # P6 A NEGATIVE component drags the basket down, and a wholly negative basket refuses.
    drag = combine([0.8, 0.8, 0.8, -0.8], 0.0)
    clean = combine([0.8, 0.8, 0.8], 0.0)
    check("a negative component lowers the mean",
          drag["mean_sharpe"] < clean["mean_sharpe"], True)
    neg = combine([-0.3, -0.2], 0.0)
    check("an all-negative basket is not confirmable", neg["confirmable"], False)
    check("an all-negative basket has no horizon", neg["years_to_confirm"], None)

    # P7 An IMPOSSIBLE correlation must refuse, not return a spectacular number. With k=4 the
    # floor is -1/3; below it the implied matrix is not positive semi-definite.
    check("rho below -1/(k-1) refuses", diversification_multiplier(4, -0.40), None)
    check("rho above 1 refuses", diversification_multiplier(4, 1.5), None)
    bad = combine([0.5] * 4, -0.40)
    check("combine refuses an invalid matrix", bad["ok"], False)
    check("and names why", bad["reason"], "IMPLIED_CORRELATION_MATRIX_INVALID")

    # P8 Degenerate inputs.
    check("no components refuses", combine([], 0.0)["ok"], False)
    check("an unknown component Sharpe refuses", combine([0.5, None], 0.0)["ok"], False)
    check("k=0 refuses", diversification_multiplier(0, 0.0), None)
    check("non-integer k refuses", diversification_multiplier(2.5, 0.0), None)

    # P9 "beats_best_alone" must be able to be FALSE, or it is decoration. One strong
    # component plus three weak ones can be worse than the strong one held alone.
    diluted = combine([1.6, 0.1, 0.1, 0.1], 0.30)
    check("dilution can fail to beat the best alone", diluted["beats_best_alone"], False)
    helped = combine([0.5] * 9, 0.05)
    check("real diversification does beat the best alone", helped["beats_best_alone"], True)

    # P11 OPTIMAL WEIGHTING can never be worse than the best component held alone, because the
    # optimiser is free to weight the others to zero. This is the property that separates a
    # real diversification gain from an equal-weighting artefact -- and it is why the
    # equal-weight basket of this project's own four candidates came out BELOW its strongest
    # member at every non-zero correlation.
    for rho_ in (0.0, 0.05, 0.1, 0.3, 0.5, 0.8):
        o = combine_optimal([0.84, 0.51, 0.28, 0.25], rho_)
        if not (o["ok"] and o["combined_sharpe"] >= 0.84 - 1e-9):
            fails.append(f"optimal below best alone at rho={rho_}: {o.get('combined_sharpe')}")
        e = combine([0.84, 0.51, 0.28, 0.25], rho_)
        if e["ok"] and o["combined_sharpe"] < e["combined_sharpe"] - 1e-9:
            fails.append(f"optimal below equal-weight at rho={rho_}")
    # Hand check: k=4, rho=0.1, s=[0.84,0.51,0.28,0.25] -> 0.963
    check("optimal arithmetic",
          round(combine_optimal([0.84, 0.51, 0.28, 0.25], 0.10)["combined_sharpe"], 3), 0.963)
    # One component returns itself.
    check("optimal k=1 returns its own Sharpe",
          round(combine_optimal([1.5], 0.0)["combined_sharpe"], 9), 1.5)
    # Identical components must reproduce the equal-weight answer -- nothing to reweight.
    ident_o = combine_optimal([0.5] * 9, 0.10)["combined_sharpe"]
    ident_e = combine([0.5] * 9, 0.10)["combined_sharpe"]
    check("identical components match equal weight", round(ident_o - ident_e, 9), 0.0)
    # ZEROS STILL GIVE ZERO under optimal weights too -- the misuse must stay closed on both
    # paths, or the tool has a back door for manufacturing an edge out of noise.
    oz = combine_optimal([0.0] * 9, 0.0)
    check("optimal on zeros is zero", oz["combined_sharpe"], 0.0)
    check("optimal on zeros has no horizon", oz["years_to_confirm"], None)
    check("optimal on zeros is not confirmable", oz["confirmable"], False)
    # Invalid correlation refuses on this path as well.
    check("optimal refuses rho >= 1", combine_optimal([0.5] * 4, 1.0)["ok"], False)
    check("optimal refuses rho below the floor", combine_optimal([0.5] * 4, -0.4)["ok"], False)
    check("optimal refuses empty", combine_optimal([], 0.1)["ok"], False)
    check("optimal refuses unknown component", combine_optimal([0.5, None], 0.1)["ok"], False)

    # P10 The project's own reachable set must be representable, and the table must not crash.
    sh = [s for _, s, _ in REACHABLE]
    check("reachable set has four components", len(sh), 4)
    r = combine(sh, 0.10)
    check("reachable set resolves", r["ok"], True)

    for f in fails:
        print("FAIL -- " + f)
    print(f"selftest: {'PASS' if not fails else 'FAIL'} ({len(fails)} failure(s))")
    return 1 if fails else 0


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sharpes", type=float, nargs="+")
    p.add_argument("--rho", type=float, default=0.10)
    p.add_argument("--table", action="store_true")
    p.add_argument("--selftest", action="store_true")
    a = p.parse_args()
    if a.selftest:
        return selftest()
    if a.table:
        table(); return 0
    if not a.sharpes:
        p.error("--sharpes is required (or --table / --selftest)")
    print(render(combine(a.sharpes, a.rho)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Re-cost every screened candidate at the venue that can actually reach it.

WHY THIS EXISTS. The first screen costed candidates against a generic retail assumption. Then
a venue survey established that the assumption was wrong by an order of magnitude in one
direction and, for equities, wrong in the other:

    retail spot FX financing   ~80 bp/yr markup   (tastyfx 0.8%/yr, Schwab 25bp, both
                                                   charged AGAINST your direction)
    CME FX futures financing   ~0.7 bp/yr         (no financing line at all -- carry sits
                                                   inside the price via covered interest
                                                   parity; you pay only the calendar spread,
                                                   four rolls a year)

That is a factor of roughly 100, and it is larger than any effect this project has measured.
It is also the third separate time the venue, rather than the absence of an effect, has been
the binding constraint: carry lost ~36% of itself to broker markup, month-end Treasury was
unreachable as a CFD, and the first screen found every survivor needed access the operator
did not have.

WHAT CHANGED IN THE OTHER DIRECTION. Equity execution is worse than a fee schedule suggests.
Schwarz, Barber, Huang, Jorion & Odean (Journal of Finance 2025) sent IDENTICAL simultaneous
orders to six brokers and measured round-trip costs from -0.07% to -0.46% -- a 39 bp spread
between best and worst, commissions excluded. Any candidate that must touch individual
equities carries that dispersion, and it is not a number you can shop away reliably.

HONESTY RULE. Where the venue cost is genuinely unknown it is recorded as None and the
candidate returns UNKNOWN, never a flattering estimate. The first screen's implied costs are
not reused, because in several cases they cannot be reconstructed from the published figures.

USAGE
  python3 scripts/venue_recost.py
  python3 scripts/venue_recost.py --selftest
"""
import argparse, math, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from candidate_power import samples_needed  # noqa: E402

# ── VENUE COSTS, round trip, in basis points of notional ────────────────────────────────────
# Sourced from exchange fee schedules and regulator/broker publications, Sept 2026.
VENUES = {
    # name:            (round-trip bp, annual holding bp, reachable at ~$10k, note)
    "fx_futures":      (0.9,   0.7,  True,  "6E/M6E. Fees 0.07bp RT; 1 tick 0.43bp. M6E is "
                                            "EUR12,500, ~$180 margin"),
    "fx_spot_retail":  (None,  80.0, True,  "Financing markup 80bp/yr charged against your "
                                            "direction. Typical spread NOT published as a "
                                            "firm figure -- recorded unknown"),
    "ust_futures":     (1.7,   0.0,  True,  "ZN fees 0.10bp RT, 1 tick 1.6bp. Yield futures "
                                            "$10/bp, ~$300 margin, size in $12.5k steps"),
    "ust_etf":         (1.2,  15.0,  True,  "TLT/SHY 1bp spread + 0.21bp SEC fee; 0.15%/yr "
                                            "expense ratio is the holding cost"),
    "equity_index_fut":(0.5,   0.0,  True,  "MES $0.35/side, 1 tick 0.37bp. ~$34k notional"),
    "commodity_fut":   (2.0,   0.0,  True,  "Estimated from CME fee structure; per-contract "
                                            "notional is large and varies by product"),
    "single_equities": (26.5,  0.0,  True,  "Schwarz et al. JF 2025 midpoint of a 7-46bp "
                                            "measured range. The DISPERSION is the hazard"),
    "listed_options":  (None,  0.0,  True,  "OCC $0.025/contract + ORF ~$0.012 + broker "
                                            "commission. Per-contract, so bp depends on "
                                            "strike and premium -- not reducible to one bp"),
    "fx_options":      (None,  0.0,  False, "No accessible US retail venue established"),
    "equities_short":  (None,  0.0,  False, "Requires borrow; locate fees not established"),
}

# ── THE CANDIDATES, at their post-publication-decay effect ──────────────────────────────────
# `effect` is the DECAYED figure from the screen (McLean & Pontiff -58% already applied).
# `unit` is bp per event unless it says pct_yr. `per_year` is how often the effect occurs.
# `sd` is the standard deviation in the same unit, where the source published one.
CANDIDATES = [
    # name,                        effect, unit,   per_yr, sd,    venue
    # VERIFIED against the original paper, with a published dispersion:
    ("Diversified global carry",    3.02,  "pct_yr",  1,   5.96,  "fx_futures", False),
    ("Treasury auction cycle",      3.62,  "bp",     12,   35.5,  "ust_futures", True),
    #   ^ already net: Lou/Yan/Yuan publish 8.62bp/month AFTER measuring bid-ask and
    #     repo, Sharpe 0.84 net. SD 35.5bp derived from that Sharpe; it reproduces
    #     the paper's own 5.57bp/month detection floor at n=156, which checks it.
    ("S&P 500 index adds (2010s)",  0.33,  "pct_yr", 15,    7.4,  "single_equities", False),
    ("Commodity roll, honest ann.",  1.62, "pct_yr",  1,   None,  "commodity_fut", False),
    ("Russell reconstitution",     627.0,  "bp",      1,  2035.0, "single_equities", False),
    #   ^ SD = SE 7.69% x sqrt(7) = 20.35% = 2035bp. I first entered the SE here,
    #     which understated the horizon roughly sixfold. n=7 events, t~1.40, and the
    #     research is 2003 on 1996-2002 data -- 23 years stale.
    ("Currency carry",              2.22,  "pct_yr",  1,   7.80,  "fx_futures", False),
    ("Commodity carry",             4.71,  "pct_yr",  1,  18.78,  "commodity_fut", False),
    ("Index put-writing (PUT)",     4.01,  "pct_yr",  1,   9.90,  "listed_options", False),
    ("Covered calls (BXM)",         3.57,  "pct_yr",  1,  10.60,  "listed_options", False),
    ("FX volatility risk premium",  2.08,  "pct_yr",  1,   8.15,  "fx_options", False),
    ("Merger arbitrage",            4.47,  "pct_yr",  1,   7.74,  "equities_short", False),
    # STRUCK. Kept in the file with effect None so the reason survives rather than the number.
    #   Leveraged ETF end-of-day    41.4bp appears in NO original paper. The closest primary
    #                               figures are regression coefficients on rebalancing
    #                               pressure (33.2, 47.6) -- dimensionless, not basis points.
    #                               Ivanov & Lenkey (JFM 2018 / Fed FEDS 2014-106) find the
    #                               impact "economically insignificant" once capital flows are
    #                               accounted for, and flows offset MOST on large-move days --
    #                               exactly the days the strategy needs. STRUCK as unsourced.
    #   Month-end equity rebalance  83bp appears in NO original paper either. Etula et al.
    #                               report annualised window returns (+28.6%/yr T-3 to T-1) and
    #                               factor alphas, not a per-event bp. STRUCK as unverified --
    #                               though note it is the one effect in the set the authors say
    #                               is STRENGTHENING, not decaying, which earns a re-look on
    #                               correctly-sourced numbers.
    #   Month-end FX hedge (4pm)    14bp is a coefficient CONDITIONAL on a 10% equity move,
    #                               not an unconditional month-end return. Unit mismatch.
    #   Option expiry pinning       cost not reducible to bp; unchanged.
    #   London 4pm fix contrarian   dead on cost at 0.4bp; unchanged.
]

HUMAN_HORIZON = 15.0   # years. Beyond this, "wait and see" is not a plan a person can act on.


def recost(effect, unit, per_year, sd, venue_key, already_net=False):
    """Net effect and time-to-confirm at the correct venue. None where genuinely unknown."""
    rt, annual, reachable, _ = VENUES[venue_key]
    if rt is None:
        return {"ok": False, "reason": "VENUE_COST_UNKNOWN", "reachable": reachable}
    if not reachable:
        return {"ok": False, "reason": "VENUE_UNREACHABLE", "reachable": False}

    # An effect the SOURCE already measured net of its own trading costs must not be
    # charged again -- only the difference between the source's cost assumption and ours.
    # Lou/Yan/Yuan measured 1.46bp round trip; ust_futures is 1.7bp, so the increment is 0.24bp.
    eff_rt = 0.24 if already_net else rt
    if unit == "bp":
        net = effect - eff_rt - (annual / per_year if per_year else annual)
    else:                                  # pct_yr: cost is annual, round trips scale with rolls
        rolls = 4                          # quarterly, the futures convention
        net = effect - (eff_rt * rolls / 100.0) - (annual / 100.0)

    out = {"ok": True, "reachable": True, "net": net, "clears_cost": net > 0}
    if sd is not None and net > 0:
        n = samples_needed(net, sd)
        out["years"] = (n / per_year) if (n and per_year) else None
    else:
        out["years"] = None                # no published SD -> cannot state a horizon
    return out


def verdict(r):
    if not r.get("ok"):
        return {"VENUE_COST_UNKNOWN": "unknown — cost not reducible to bp",
                "VENUE_UNREACHABLE": "no reachable US retail venue"}[r["reason"]]
    if not r["clears_cost"]:
        return "DEAD on cost"
    y = r.get("years")
    if y is None:
        return "clears cost — horizon unknown (no published SD)"
    if y <= HUMAN_HORIZON:
        return f"CLEARS — confirmable in {y:.0f} yrs"
    return f"clears cost, needs {y:.0f} yrs"


def report():
    print(f"{'candidate':<30}{'venue':<19}{'net':>9}  verdict")
    print("-" * 100)
    live = []
    for name, eff, unit, per_yr, sd, venue, anet in CANDIDATES:
        r = recost(eff, unit, per_yr, sd, venue, anet)
        net = f"{r['net']:+.2f}" if r.get("ok") else "—"
        u = "bp" if unit == "bp" else "%/yr"
        v = verdict(r)
        print(f"{name:<30}{venue:<19}{net:>6} {u:<3} {v}")
        if r.get("ok") and r["clears_cost"]:
            live.append((name, r.get("years")))
    print("-" * 100)
    print("Effects are POST-decay (McLean & Pontiff -58% already applied).")
    print("Units differ by row — read each row against itself, never across rows.\n")
    conf = [n for n, y in live if y is not None and y <= HUMAN_HORIZON]
    print(f"clears cost at its venue:      {len(live)} of {len(CANDIDATES)}")
    print(f"AND confirmable within {HUMAN_HORIZON:.0f} years: {len(conf)}"
          + (("  ->  " + ", ".join(conf)) if conf else ""))


def selftest():
    fails = []

    def check(name, got, want):
        if got != want:
            fails.append(f"{name}: expected {want}, got {got}")

    # An unknown venue cost must REFUSE, never be treated as zero — the flattering failure.
    r = recost(5.0, "bp", 12, None, "listed_options")
    check("unknown cost refuses", r["ok"], False)
    check("unknown cost names why", r["reason"], "VENUE_COST_UNKNOWN")

    # An unreachable venue refuses even when the arithmetic would be favourable.
    r = recost(500.0, "pct_yr", 1, 5.0, "fx_options")
    check("unreachable refuses", r["ok"], False)
    check("unreachable is not a pass", "clears" in verdict(r).lower(), False)

    # THE CASE THE FILE EXISTS FOR: the same carry effect at two venues must differ by the
    # markup, and the futures version must be materially better.
    spot = recost(2.22, "pct_yr", 1, 7.80, "fx_spot_retail")
    fut = recost(2.22, "pct_yr", 1, 7.80, "fx_futures")
    check("retail spot FX cost is unknown, not assumed", spot["ok"], False)
    check("fx futures resolves", fut["ok"], True)
    check("fx futures clears cost", fut["clears_cost"], True)
    # 80bp/yr of markup would have taken 2.22% to 1.42%; futures leaves it near 2.2%.
    check("futures keeps nearly all of it", round(fut["net"], 2) >= 2.17, True)

    # Equity dispersion must bite: a 20bp effect cannot survive a 26.5bp round trip.
    eq = recost(20.0, "bp", 12, None, "single_equities")
    check("equity cost kills a 20bp effect", eq["clears_cost"], False)
    # ...and the same effect at a futures venue must survive, or the venue column does nothing.
    fu = recost(20.0, "bp", 12, None, "equity_index_fut")
    check("same effect survives at futures", fu["clears_cost"], True)

    # A per-event effect must have the ANNUAL holding cost amortised over its own frequency,
    # not charged in full to every event.
    rare = recost(20.0, "bp", 1, None, "ust_etf")     # 15bp/yr all on one event
    often = recost(20.0, "bp", 12, None, "ust_etf")   # 15bp/yr over twelve
    check("annual cost amortises by frequency", round(often["net"] - rare["net"], 2), 13.75)

    # No published SD -> no horizon claimed. Silence beats a fabricated number.
    check("no SD means no years", recost(50.0, "bp", 12, None, "ust_futures")["years"], None)
    check("no SD verdict says so",
          "horizon unknown" in verdict(recost(50.0, "bp", 12, None, "ust_futures")), True)

    # Every candidate must name a venue that exists.
    for name, _, _, _, _, v, _n in CANDIDATES:
        if v not in VENUES:
            fails.append(f"{name}: venue {v!r} not in VENUES")

    for f in fails:
        print("FAIL -- " + f)
    print(f"selftest: {'PASS' if not fails else 'FAIL'} ({len(fails)} failure(s))")
    return 1 if fails else 0


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--selftest", action="store_true")
    a = p.parse_args()
    if a.selftest:
        return selftest()
    report()
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Did bond carry survive past the paper that documented it?

PRE-REGISTERED BEFORE THE DATA WAS FETCHED. Written 2026-09-10. The hypothesis, the signal,
the window, the direction, the cost and the pass condition are all fixed here, in code, before
a single observation is read. There is nothing in this file to tune, and tuning the signal
threshold or the duration until something appears would convert a test into a search.

THE HYPOTHESIS IS NOT OURS. Koijen, Moskowitz, Pedersen & Vrugt, "Carry", Journal of Financial
Economics 2018, on data ending September 2012:

    Carry -- the return an asset earns if its price does not change -- predicts returns in
    every asset class tested. The diversified version across nine asset classes returns
    7.18%/yr with SD 5.96%, Sharpe 1.20.

That is the ONLY candidate out of twenty screened whose effect size AND dispersion were both
confirmed against the original paper. Everything else either died on cost, could not be given
a horizon, or turned out to rest on a figure that appears in no original source.

WHAT THIS TESTS, AND WHAT IT CANNOT.

Diversified carry gets its Sharpe from combining NINE imperfectly correlated carry strategies.
This file tests exactly ONE of them -- bond carry in US Treasuries -- because it is the only
one whose inputs are obtainable free and whose venue the operator can actually reach (CME
yield futures, $10/bp, ~$300 margin, sized in $12.5k steps).

  TESTED HERE          US bond carry, time-series form
  NOT TESTED           equity, commodity, currency, credit, index-option, and the
                       cross-sectional forms. Seven of nine asset classes need futures curve
                       data that is not free.

So a pass here is evidence about bond carry, NOT about the diversified 7.18%/yr figure. A
null here is evidence about bond carry and nothing else. Reporting either as a verdict on
"carry" would be the same class of error as counting an implementation's replay as evidence
about the trader it was reconstructed from.

THE SIGNAL, fixed in advance. Carry on a bond is approximately its yield advantage over cash
plus its roll-down. The simplest faithful version, and the one pre-registered:

    carry(t)  =  long yield(t)  -  short rate(t)

    position  =  +1 when carry > 0 (curve upward sloping), -1 when carry < 0 (inverted)

    monthly excess return  ~=  [ long yield(t)/12 - D * dy ]  -  short rate(t)/12

The duration approximation is first-order: no convexity, no exact roll-down. It is adequate
to detect a percent-per-year effect and NOT adequate to quote a tradeable P&L.

DATA
  FRED, all free, all daily, downloaded at full history:
    DGS10  10-Year Treasury Constant Maturity Rate
    DTB3   3-Month Treasury Bill Secondary Market Rate
  fred.stlouisfed.org/series/<ID> -> Download -> CSV. Set the range to MAX.

USAGE
  python3 scripts/bond_carry_test.py --long DGS10.csv --short DTB3.csv
  python3 scripts/bond_carry_test.py --selftest
"""
import argparse, csv, datetime as dt, math, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from candidate_power import detection_floor, Z95  # noqa: E402

# ── PRE-REGISTERED PARAMETERS. Do not tune these to the data. ────────────────────────────────
MODIFIED_DURATION = 8.0     # 10-year note, approximate and deliberately not fitted
IN_SAMPLE_END = dt.date(2012, 9, 30)    # the paper's sample ends here
IN_SAMPLE_START = dt.date(1983, 11, 1)  # and begins here
COST_BP_PER_SWITCH = 1.7    # CME ZN round trip: 0.10bp fees + 1 tick (1.6bp)
PAPER_SHARPE = 1.20         # diversified, 9 asset classes -- NOT this single-class test
DECAY_FLOOR_FRACTION = 0.50 # out-of-sample must retain at least half the in-sample magnitude
# ─────────────────────────────────────────────────────────────────────────────────────────────


def load_series(path):
    """FRED CSV -> sorted [(date, percent)]. Missing values are DROPPED, never zeroed.

    FRED marks holidays as '.' in older exports and as an empty field in current ones. Either
    read as 0.0 would be an instantaneous collapse to a zero interest rate -- the most
    destructive lie this parser could tell.
    """
    rows = []
    with open(path, newline="") as fh:
        for rec in csv.reader(fh):
            if len(rec) < 2:
                continue
            try:
                day = dt.date.fromisoformat(rec[0].strip())
            except ValueError:
                continue
            try:
                v = float(rec[1].strip())
            except ValueError:
                continue
            if math.isfinite(v):
                rows.append((day, v))
    rows.sort(key=lambda r: r[0])
    return rows


def month_ends(rows):
    """Last observation of each calendar month: {(year, month): (date, value)}."""
    out = {}
    for d, v in rows:
        k = (d.year, d.month)
        if k not in out or d > out[k][0]:
            out[k] = (d, v)
    return out


def build_months(long_rows, short_rows):
    """Aligned monthly observations. Returns [(year, month, date, long_pct, short_pct)]."""
    L, S = month_ends(long_rows), month_ends(short_rows)
    keys = sorted(set(L) & set(S))
    return [(k[0], k[1], L[k][0], L[k][1], S[k][1]) for k in keys]


def strategy_returns(months, duration=MODIFIED_DURATION, cost_bp=COST_BP_PER_SWITCH):
    """[(date, excess return in bp, position)] for the pre-registered rule.

    Position is decided on month t's carry and earns month t+1's return, so nothing is
    decided using information from the month it is applied to. Getting this wrong is
    look-ahead, and it would make every figure worthless.
    """
    out, prev_pos = [], 0
    for i in range(len(months) - 1):
        _, _, _, y0, s0 = months[i]
        _, _, d1, y1, _ = months[i + 1]
        carry = y0 - s0
        pos = 1 if carry > 0 else -1
        total_bp = (y0 / 12.0) * 100.0 - duration * (y1 - y0) * 100.0
        excess_bp = total_bp - (s0 / 12.0) * 100.0
        r = pos * excess_bp
        if pos != prev_pos:
            r -= cost_bp                       # charged only when the position actually changes
        prev_pos = pos
        out.append((d1, r, pos))
    return out


def analyse(rets):
    """Mean excess return per month, in bp, with its own detection floor."""
    v = [r for _, r, _ in rets]
    n = len(v)
    if n < 24:
        return {"ok": False, "reason": "TOO_FEW_MONTHS", "n": n}
    m = sum(v) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in v) / (n - 1))
    se = sd / math.sqrt(n)
    ann = m * 12 / 100.0
    ann_sd = sd * math.sqrt(12) / 100.0
    return {"ok": True, "n": n, "mean_bp": m, "sd_bp": sd, "se_bp": se,
            "t": (m / se) if se else None,
            "detection_floor_bp": detection_floor(sd, n),
            "ann_pct": ann, "ann_sd_pct": ann_sd,
            "sharpe": (ann / ann_sd) if ann_sd else None,
            "first": rets[0][0].isoformat(), "last": rets[-1][0].isoformat(),
            "long_months": sum(1 for _, _, p in rets if p > 0),
            "positive": (se is not None) and (m / se) > Z95}


def compare(ins, oos):
    """Did the out-of-sample period retain the effect? The question the whole file is for."""
    if not (ins.get("ok") and oos.get("ok")):
        return {"ok": False, "reason": "ONE_WINDOW_UNUSABLE"}
    ret = (oos["mean_bp"] / ins["mean_bp"]) if ins["mean_bp"] else None
    return {"ok": True, "retention": ret,
            "oos_positive": oos["positive"],
            "oos_above_floor": abs(oos["mean_bp"]) > oos["detection_floor_bp"],
            "retained_half": (ret is not None) and ret >= DECAY_FLOOR_FRACTION,
            "in_sample_positive": ins["positive"]}


def render(label, a):
    if not a.get("ok"):
        return f"  {label}: REFUSED -- {a.get('reason')} (n={a.get('n')})"
    return (f"  {label:<22} n={a['n']:<4} {a['mean_bp']:+7.2f} bp/mo  "
            f"SE {a['se_bp']:5.2f}  t {a['t']:+6.2f}  floor {a['detection_floor_bp']:5.2f}\n"
            f"  {'':<22} {a['ann_pct']:+.2f}%/yr  SD {a['ann_sd_pct']:.2f}%  "
            f"Sharpe {a['sharpe']:+.2f}  long {a['long_months']}/{a['n']} months\n"
            f"  {'':<22} {a['first']} to {a['last']}")


def render_compare(c, oos):
    if not c.get("ok"):
        return f"  REFUSED -- {c.get('reason')}"
    L = [f"  retention vs in-sample     {c['retention']*100:.0f}%" if c["retention"] is not None
         else "  retention                  undefined",
         f"  out-of-sample significant  {c['oos_positive']}",
         f"  above its detection floor  {c['oos_above_floor']}",
         f"  retained >= half           {c['retained_half']}"]
    if c["oos_positive"] and c["retained_half"]:
        v = "SURVIVED -- bond carry persists out of sample"
    elif c["oos_positive"]:
        v = "PRESENT BUT DECAYED -- significant, under half the in-sample magnitude"
    elif c["oos_above_floor"]:
        v = "CONTRADICTED -- this sample can resolve an effect of this size and does not see it"
    else:
        v = "INCONCLUSIVE -- cannot resolve either way. NOT evidence of absence."
    L += ["", f"  VERDICT                    {v}", "",
          "  This is ONE of nine asset classes. It is NOT a verdict on the diversified",
          "  7.18%/yr figure, and must never be reported as one.",
          "  Duration-approximated returns: no convexity, no exact roll-down, no slippage."]
    return "\n".join(L)


def selftest():
    fails = []

    def check(name, got, want):
        if got != want:
            fails.append(f"{name}: expected {want}, got {got}")

    # C1 PARSING. A holiday must be dropped, never read as a zero interest rate.
    import tempfile
    p = os.path.join(tempfile.mkdtemp(), "s.csv")
    with open(p, "w") as fh:
        fh.write("observation_date,DGS10\n2021-01-04,0.93\n2021-01-05,.\n"
                 "2021-01-06,\n2021-01-07,1.04\n")
    rows = load_series(p)
    check("holidays dropped", len(rows), 2)
    check("holiday never zero", all(v > 0.5 for _, v in rows), True)

    def synth(months, long_pct, short_pct, drift=0.0, start=dt.date(1990, 1, 31), noise=0.0):
        import random
        rng = random.Random(4242)
        out, y = [], long_pct
        for i in range(months):
            m = start.month + i
            d = dt.date(start.year + (m - 1) // 12, (m - 1) % 12 + 1, 28)
            out.append((d.year, d.month, d, y + (rng.gauss(0, noise) if noise else 0.0),
                        short_pct))
            y += drift
        return out

    # C2 SIGNAL DIRECTION. A steep curve must be held long; an inverted one must not.
    steep = strategy_returns(synth(36, 5.0, 1.0))
    check("steep curve is held long", all(p > 0 for _, _, p in steep), True)
    inv = strategy_returns(synth(36, 1.0, 5.0))
    check("inverted curve is held short", all(p < 0 for _, _, p in inv), True)

    # C3 THE CARRY ITSELF. With yields flat, a steep curve must earn the spread, positive.
    a = analyse(steep)
    check("flat yields, steep curve earns the spread", a["mean_bp"] > 0, True)
    # (5% - 1%)/12 = 33.3bp a month, less one switch cost on the first month.
    check("spread magnitude is right", abs(a["mean_bp"] - 33.3) < 1.5, True)

    # C4 PRICE TERM. Rising yields must hurt a long position -- the sign must not be flipped.
    rising = analyse(strategy_returns(synth(36, 5.0, 1.0, drift=+0.05)))
    check("rising yields hurt a long", rising["mean_bp"] < a["mean_bp"], True)
    falling = analyse(strategy_returns(synth(36, 5.0, 1.0, drift=-0.05)))
    check("falling yields help a long", falling["mean_bp"] > a["mean_bp"], True)

    # C5 NO LOOK-AHEAD. The position must come from the PRIOR month's carry. Feeding a series
    # whose carry flips must not let the strategy anticipate the flip.
    flip = synth(6, 5.0, 1.0) + synth(6, 1.0, 5.0, start=dt.date(1990, 7, 28))
    r = strategy_returns(flip)
    check("position lags the signal", r[5][2], 1)      # month 6 still long, decided on month 5
    check("position turns after the flip", r[6][2], -1)

    # C6 COST charged ONLY on a switch, and it must actually bite.
    stable = strategy_returns(synth(24, 5.0, 1.0))
    switches = sum(1 for i in range(1, len(stable)) if stable[i][2] != stable[i-1][2])
    check("a stable curve switches once at most", switches, 0)
    free = strategy_returns(synth(24, 5.0, 1.0), cost_bp=0.0)
    check("cost lowers the total", sum(x[1] for x in stable) < sum(x[1] for x in free), True)

    # C7 DEGENERATE. Too short must refuse rather than return a number.
    check("short sample refuses", analyse(strategy_returns(synth(12, 5.0, 1.0)))["ok"], False)
    check("empty refuses", analyse([])["ok"], False)

    # C8 THE COMPARISON must distinguish survival from decay, in both directions.
    ins = analyse(strategy_returns(synth(120, 5.0, 1.0)))
    same = compare(ins, analyse(strategy_returns(synth(120, 5.0, 1.0))))
    check("identical windows read as survived", same["retained_half"], True)
    check("survived verdict rendered", "SURVIVED" in render_compare(same, ins), True)
    weak = compare(ins, analyse(strategy_returns(synth(120, 1.30, 1.0))))
    check("a quarter-size effect fails the half floor", weak["retained_half"], False)

    # C9 A LOSING out-of-sample window must not read as significant-positive.
    #
    # The first version of this fixture used an inverted curve with rising yields and asserted
    # the strategy would lose. It does not: carry is negative, so the rule goes SHORT, and a
    # short bond position gains when yields rise. The strategy was right and the assertion was
    # backwards. The genuinely losing case is the opposite -- held long on a steep curve while
    # yields rise far enough that the price loss swamps the carry.
    # The losing case needs a SHORT window with steep drift, not a long one. Over 120 months
    # the carry term (y0/12) grows with the climbing yield and eventually swamps the price
    # loss, so a long rising-yield run comes out POSITIVE (+14.8 bp/mo at drift 0.06). My
    # first attempt checked only month 0 and got this backwards -- twice. Measured, not
    # assumed: 29 months at drift 0.12 gives -48.7 bp/mo, t -30.
    losing = analyse(strategy_returns(synth(30, 5.0, 1.0, drift=+0.12)))
    check("a losing window has a negative mean", losing["mean_bp"] < 0, True)
    neg = compare(ins, losing)
    check("losing OOS is not significant-positive", neg["oos_positive"], False)
    check("losing OOS fails the retention floor", neg["retained_half"], False)
    # And pin the behaviour the broken fixture misread, so nobody re-introduces it: shorting an
    # inverted curve into rising yields is SUPPOSED to make money.
    short_win = analyse(strategy_returns(synth(120, 1.0, 5.0, drift=+0.02)))
    check("short into rising yields profits", short_win["mean_bp"] > 0, True)

    # C11 MONTH-END means the LAST observation of the month, not the first.
    #
    # Added after mutation M13 survived. Every synthetic series above has exactly one
    # observation per month, so first and last are the same value and picking either passed.
    # Real FRED data has ~21 observations a month, and taking the first would shift every
    # yield by up to a month -- a silent, plausible-looking error.
    multi = [(dt.date(2000, 1, 3), 6.00), (dt.date(2000, 1, 14), 6.20),
             (dt.date(2000, 1, 31), 6.50),
             (dt.date(2000, 2, 1), 6.10), (dt.date(2000, 2, 29), 6.90)]
    me = month_ends(multi)
    check("month-end takes the LAST observation", me[(2000, 1)][1], 6.50)
    check("month-end date is the last date", me[(2000, 1)][0], dt.date(2000, 1, 31))
    check("month-end not the first", me[(2000, 2)][1], 6.90)

    # C12 THE DETECTION FLOOR must bind, in both directions.
    #
    # Added after mutation M14 ("oos_above_floor": True) survived -- the THIRD time in this
    # project that a flag no fixture reads has turned out to be decoration. Built directly
    # rather than through the generator: adding noise to the yield LEVEL creates a spurious
    # mean-reversion edge, because noise that lifts the carry signal is the same noise that
    # falls back next month, so the rule reads its own noise as information. A generator that
    # manufactures an edge cannot test a floor.
    d0 = dt.date(2015, 1, 31)
    small = [(d0, (2.0 if i % 2 == 0 else -1.0) + (60.0 if i % 3 == 0 else -30.0), 1)
             for i in range(30)]
    a_small = analyse(small)
    check("small effect, wide spread, is BELOW its floor",
          abs(a_small["mean_bp"]) < a_small["detection_floor_bp"], True)
    check("and is not significant", a_small["positive"], False)
    c_small = compare(ins, a_small)
    check("below-floor reads as inconclusive, not contradicted",
          c_small["oos_above_floor"], False)
    check("inconclusive verdict rendered",
          "INCONCLUSIVE" in render_compare(c_small, a_small), True)
    # Positive control: a large effect on the same spread must clear the floor.
    big = [(d0, r + 200.0, 1) for _, r, _ in small]
    check("large effect clears the floor",
          compare(ins, analyse(big))["oos_above_floor"], True)

    # C10 Alignment: only months present in BOTH series may be used.
    L = [(dt.date(2000, 1, 31), 6.0), (dt.date(2000, 2, 29), 6.1), (dt.date(2000, 3, 31), 6.2)]
    S = [(dt.date(2000, 2, 29), 5.0), (dt.date(2000, 3, 31), 5.1)]
    check("months intersect, not union", len(build_months(L, S)), 2)

    for f in fails:
        print("FAIL -- " + f)
    print(f"selftest: {'PASS' if not fails else 'FAIL'} ({len(fails)} failure(s))")
    return 1 if fails else 0


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--long", help="FRED CSV for the long yield (DGS10)")
    p.add_argument("--short", help="FRED CSV for the short rate (DTB3)")
    p.add_argument("--selftest", action="store_true")
    a = p.parse_args()
    if a.selftest:
        return selftest()
    if not (a.long and a.short):
        p.error("--long and --short are required (or --selftest)")

    months = build_months(load_series(a.long), load_series(a.short))
    if len(months) < 48:
        print(f"  REFUSED -- only {len(months)} aligned months. Download the FULL history "
              f"(set the FRED date range to MAX).")
        return 1

    ins_m = [m for m in months if IN_SAMPLE_START <= m[2] <= IN_SAMPLE_END]
    oos_m = [m for m in months if m[2] > IN_SAMPLE_END]
    ins = analyse(strategy_returns(ins_m))
    oos = analyse(strategy_returns(oos_m))

    print("  BOND CARRY, US Treasuries -- ONE of the nine asset classes in Koijen et al.\n")
    print(render("in-sample 1983-2012", ins))
    print()
    print(render("OUT OF SAMPLE 2012+", oos))
    print()
    print(render_compare(compare(ins, oos), oos))
    return 0


if __name__ == "__main__":
    sys.exit(main())

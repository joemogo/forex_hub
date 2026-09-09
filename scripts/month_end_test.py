#!/usr/bin/env python3
"""Did the end-of-month Treasury effect survive past the paper that documented it?

PRE-REGISTERED BEFORE THE DATA WAS SEEN. This file was written on 2026-09-09 in a session
that could not fetch the price series -- FRED returned binary through the available fetch
tool and was recorded unavailable per CLAUDE.md rather than worked around. That is an
accident, and it is also the correct order: the hypothesis, the window, the direction and
the pass condition are all fixed here, in code, before a single observation is read.

THE HYPOTHESIS IS NOT MINE. It is Hartley & Schwarz's, published on data ending December
2018:

    Treasury returns are positive and significant in the last few trading days of the
    month, and not significantly different from zero at other times. ~25bp per month-end
    at the 10-year maturity, annualised Sharpe ~1.0, bid-ask 2-3bp.

Because the hypothesis is fixed by a published paper and the test sample is data published
AFTER it, this is a genuine out-of-sample test -- the strongest form available without a
time machine. There is nothing to tune. Tuning the window, the duration, or the day count
until something appears would convert this from a test into a search, and the result would
mean nothing.

WHY IT MATTERS. Run through the project's gates, this effect is the first candidate to
return "TRADEABLE AND CONFIRMABLE BY WAITING" -- 23bp net at futures cost, 4.6 years to
confirm. But the verdict is NOT robust to decay: halve the effect and it needs 21.8 years;
halve it with costs 3x higher and it needs 56.8 and becomes an act of faith. The paper's
data stops in 2018 and the result is published, which is exactly when an anomaly gets
arbitraged away. So this test decides the candidate.

WHAT THIS MEASURES, AND WHAT IT DOES NOT. FRED publishes YIELDS, not total returns. This
converts yield changes to approximate price returns with a fixed modified duration:

    price return  ~=  -D * change in yield

That is a first-order approximation. It ignores convexity, it ignores the coupon carry
earned over the window, and it uses one duration for a maturity whose real duration drifts
with the yield level. It is adequate to detect a 25bp directional effect and NOT adequate
to quote a tradeable P&L. Any number this prints is a screen, not a backtest.

DATA
  FRED series DGS10 (10-Year Treasury Constant Maturity Rate), daily, percent.
  Download: fred.stlouisfed.org/series/DGS10 -> Download -> CSV
  Format: a header line, then DATE,<value> with "." for market holidays.

USAGE
  python3 scripts/month_end_test.py --csv DGS10.csv --start 2019-01-01
  python3 scripts/month_end_test.py --selftest
"""
import argparse, csv, datetime as dt, math, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from candidate_power import detection_floor, Z95  # noqa: E402

# ── PRE-REGISTERED PARAMETERS. Do not tune these to the data. ────────────────────────────
WINDOW_DAYS = 3          # the paper's "last few days"; it reports the effect over the last 3
MODIFIED_DURATION = 8.0  # 10-year note, approximate and deliberately not fitted
PAPER_EFFECT_BP = 25.0   # what Hartley & Schwarz measured through 2018
DECAY_FLOOR_BP = 12.5    # half the paper's effect -- below this the candidate is not worth
                         # a futures account, per candidate_frequency.py
# ─────────────────────────────────────────────────────────────────────────────────────────


def load_yields(path):
    """FRED CSV -> sorted [(date, yield_pct)]. Holidays are '.' and are DROPPED, not zeroed.

    A '.' read as 0.0 would be a 400bp yield collapse -- the single most destructive lie this
    parser could tell, and the same class of error as `isFinite(null)` being true.
    """
    rows = []
    with open(path, newline="") as fh:
        for rec in csv.reader(fh):
            if len(rec) < 2:
                continue
            d, v = rec[0].strip(), rec[1].strip()
            try:
                day = dt.date.fromisoformat(d)
            except ValueError:
                continue                      # header, blank, or malformed date
            try:
                y = float(v)
            except ValueError:
                continue                      # "." -- market holiday, genuinely absent
            if not math.isfinite(y):
                continue
            rows.append((day, y))
    rows.sort(key=lambda r: r[0])
    return rows


def daily_returns(rows, duration=MODIFIED_DURATION):
    """[(date, approx price return in bp)]. First observation has no prior, so no return.

    SIGN: a FALLING yield is a RISING price. return_bp = -D * dy_pct * 100.
    Getting this backwards would invert the entire finding while still producing a
    plausible-looking number, so fixture S1 asserts it directly.
    """
    out = []
    for i in range(1, len(rows)):
        (d0, y0), (d1, y1) = rows[i - 1], rows[i]
        out.append((d1, -duration * (y1 - y0) * 100.0))
    return out


def month_end_flags(dates, window=WINDOW_DAYS):
    """True for each date in the last `window` TRADING days of its month.

    Trading days, not calendar days: a month ending on a Saturday has its last trading day
    on the Friday, and counting back calendar days would silently shift the window off the
    effect. This is the same defect that made the tod_session complement cut at weekends.
    """
    if window <= 0:
        raise ValueError("window must be positive")
    by_month = {}
    for i, d in enumerate(dates):
        by_month.setdefault((d.year, d.month), []).append(i)
    flags = [False] * len(dates)
    for _, idxs in by_month.items():
        for i in idxs[-window:]:
            flags[i] = True
    return flags


def split_returns(rets, window=WINDOW_DAYS):
    """(month_end_returns, other_returns) in bp."""
    dates = [d for d, _ in rets]
    flags = month_end_flags(dates, window)
    me = [r for (d, r), f in zip(rets, flags) if f]
    other = [r for (d, r), f in zip(rets, flags) if not f]
    return me, other


def analyse(rets, window=WINDOW_DAYS):
    """The verdict as a record. Per-EVENT effect, so it is comparable to the paper's 25bp.

    The paper quotes ~25bp for the whole month-end window, not per day, so the daily returns
    inside each window are SUMMED per month before averaging. Averaging the daily returns
    instead would report roughly a third of the effect and read as decay that is not there.
    """
    dates = [d for d, _ in rets]
    flags = month_end_flags(dates, window)
    per_month = {}
    others = []
    for (d, r), f in zip(rets, flags):
        if f:
            per_month.setdefault((d.year, d.month), 0.0)
            per_month[(d.year, d.month)] += r
        else:
            others.append(r)
    events = list(per_month.values())
    n = len(events)
    if n < 2:
        return {"ok": False, "reason": "TOO_FEW_MONTHS", "n_events": n}
    mean = sum(events) / n
    var = sum((x - mean) ** 2 for x in events) / (n - 1)
    sd = math.sqrt(var)
    se = sd / math.sqrt(n) if n else None
    floor = detection_floor(sd, n)
    return {
        "ok": True, "n_events": n, "n_other_days": len(others),
        "mean_bp": mean, "sd_bp": sd, "se_bp": se,
        "t": (mean / se) if se else None,
        "detection_floor_bp": floor,
        "first": min(dates).isoformat(), "last": max(dates).isoformat(),
        # The three pre-registered checks. Booleans, so no sentence can claim what they deny.
        "positive_and_significant": (se is not None) and (mean / se) > Z95,
        "above_detection_floor": (floor is not None) and abs(mean) > floor,
        "above_decay_floor": mean > DECAY_FLOOR_BP,
    }


def render(a):
    if not a.get("ok"):
        return f"  REFUSED -- {a.get('reason')} (n_events={a.get('n_events')})"
    L = [f"  sample            {a['first']} to {a['last']}",
         f"  month-end events  {a['n_events']}   (other days: {a['n_other_days']:,})",
         f"  mean per event    {a['mean_bp']:+.2f} bp   (SD {a['sd_bp']:.1f}, SE {a['se_bp']:.2f})",
         f"  t                 {a['t']:+.2f}",
         f"  detection floor   {a['detection_floor_bp']:.2f} bp",
         f"  paper's effect    {PAPER_EFFECT_BP:+.2f} bp   (Hartley & Schwarz, through 2018)",
         "",
         f"  positive and significant   {a['positive_and_significant']}",
         f"  above detection floor      {a['above_detection_floor']}",
         f"  above decay floor ({DECAY_FLOOR_BP:.1f}bp)   {a['above_decay_floor']}"]
    if a["positive_and_significant"] and a["above_decay_floor"]:
        v = "SURVIVED -- effect persists out of sample; the candidate stands"
    elif a["positive_and_significant"]:
        v = ("PRESENT BUT DECAYED -- significant, but under half the paper's effect. "
             "candidate_frequency says 21.8+ years to confirm. Not worth a futures account.")
    elif a["above_detection_floor"]:
        v = "CONTRADICTED -- the sample can resolve an effect this size and does not see it"
    else:
        v = ("INCONCLUSIVE -- this sample cannot resolve the effect either way. "
             "NOT evidence of absence.")
    L += ["", f"  VERDICT           {v}"]
    L.append("")
    L.append("  Duration-approximated price returns from yields. A screen, not a backtest:")
    L.append("  no convexity, no coupon carry, no financing, no slippage.")
    return "\n".join(L)


def selftest():
    fails = []

    def check(name, got, want):
        if got != want:
            fails.append(f"{name}: expected {want}, got {got}")

    # S1 SIGN. A falling yield must be a POSITIVE return. Backwards, this inverts every
    # conclusion while still printing a believable number.
    r = daily_returns([(dt.date(2020, 1, 2), 2.00), (dt.date(2020, 1, 3), 1.99)])
    check("falling yield is a positive return", r[0][1] > 0, True)
    check("sign magnitude", round(r[0][1], 6), round(8.0 * 0.01 * 100, 6))
    r2 = daily_returns([(dt.date(2020, 1, 2), 2.00), (dt.date(2020, 1, 3), 2.01)])
    check("rising yield is a negative return", r2[0][1] < 0, True)

    # S2 TRADING DAYS, NOT CALENDAR DAYS. May 2021 ended on Monday the 31st (Memorial Day,
    # market closed), so the last three TRADING days are 26, 27, 28 May.
    days = [dt.date(2021, 5, d) for d in (24, 25, 26, 27, 28)]   # 29-31 absent from the data
    f = month_end_flags(days, 3)
    check("last three trading days flagged", f, [False, False, True, True, True])

    # A month present in the data with fewer days than the window flags all of them rather
    # than reaching back into the previous month.
    short = [dt.date(2021, 6, 1), dt.date(2021, 6, 2)]
    check("short month does not bleed backwards", month_end_flags(short, 3), [True, True])

    # S3 MONTH BOUNDARIES. Windows must not merge across a month change.
    two = [dt.date(2021, 4, 28), dt.date(2021, 4, 29), dt.date(2021, 4, 30),
           dt.date(2021, 5, 3), dt.date(2021, 5, 4), dt.date(2021, 5, 5)]
    check("each month gets its own window", month_end_flags(two, 3), [True] * 6)
    three = [dt.date(2021, 4, 27), dt.date(2021, 4, 28), dt.date(2021, 4, 29),
             dt.date(2021, 4, 30), dt.date(2021, 5, 3)]
    check("window is per month, not global",
          month_end_flags(three, 3), [False, True, True, True, True])

    def synth(months, effect_bp, seed=5, per_month=21):
        """Daily returns with `effect_bp` planted across each month's last 3 days."""
        import random
        rng = random.Random(seed)
        out, y, m = [], 2019, 1
        for _ in range(months):
            d = 1
            for k in range(per_month):
                day = dt.date(y, m, min(d, 28))
                noise = rng.gauss(0, 30)
                bump = (effect_bp / 3.0) if k >= per_month - 3 else 0.0
                out.append((day, noise + bump))
                d += 1
            m += 1
            if m > 12:
                m, y = 1, y + 1
        return out

    # S4 PLANTED EFFECT must be recovered at the EVENT level, near the planted size.
    a = analyse(synth(120, 25.0), 3)
    check("planted effect recovered", abs(a["mean_bp"] - 25.0) < 12, True)
    check("planted effect is significant", a["positive_and_significant"], True)
    check("planted effect clears the decay floor", a["above_decay_floor"], True)
    check("event count matches months", a["n_events"], 120)

    # S5 NULL must not pass. Without this the harness is a rubber stamp.
    n0 = analyse(synth(120, 0.0, seed=9), 3)
    check("null is not significant", n0["positive_and_significant"], False)
    check("null does not clear the decay floor", n0["above_decay_floor"], False)

    # S6 DECAYED effect must be distinguished from a survivor -- the whole point of the run.
    dec = analyse(synth(400, 8.0, seed=11), 3)
    check("decayed effect is under the decay floor", dec["above_decay_floor"], False)

    # S6b DETECTION FLOOR must actually bind, in both directions. Added after mutation M10
    # ("above_detection_floor": True) survived the harness -- nothing here had ever asserted
    # on that flag, so hardcoding it to True broke nothing. A flag no fixture reads is not a
    # check, it is decoration, and this is the third time that class of gap has been found
    # in this project.
    check("big effect clears the detection floor", a["above_detection_floor"], True)
    tiny = analyse(synth(24, 3.0, seed=23), 3)
    check("small effect in a small sample does NOT clear the floor",
          tiny["above_detection_floor"], False)
    # And an underpowered null must report INCONCLUSIVE, never a contradiction of the paper.
    check("underpowered null is not significant", tiny["positive_and_significant"], False)
    check("underpowered null is reported as inconclusive, not contradicted",
          "INCONCLUSIVE" in render(tiny), True)

    # S7 SUMMING vs AVERAGING inside the window. Averaging daily returns reports ~1/3 of the
    # effect and would read as decay that is not there.
    s = analyse(synth(120, 30.0, seed=13), 3)
    check("window is summed, not averaged", s["mean_bp"] > 20, True)

    # S8 DEGENERATE inputs refuse rather than return a number.
    check("one month refuses", analyse(synth(1, 25.0), 3)["ok"], False)
    check("empty refuses", analyse([], 3)["ok"], False)
    try:
        month_end_flags([dt.date(2021, 1, 4)], 0)
        fails.append("zero window: expected a refusal, got none")
    except ValueError:
        pass

    # S9 HOLIDAY PARSING. "." must be dropped, never read as 0.0 -- that would be a 400bp
    # yield collapse invented out of a market holiday.
    import tempfile
    p = os.path.join(tempfile.mkdtemp(), "d.csv")
    with open(p, "w") as fh:
        fh.write("DATE,DGS10\n2021-01-04,0.93\n2021-01-05,.\n2021-01-06,1.04\n")
    rows = load_yields(p)
    check("holiday row dropped", len(rows), 2)
    check("holiday not read as zero", all(r[1] > 0.5 for r in rows), True)
    check("dates parsed", rows[0][0], dt.date(2021, 1, 4))

    for f_ in fails:
        print("FAIL -- " + f_)
    print(f"selftest: {'PASS' if not fails else 'FAIL'} ({len(fails)} failure(s))")
    return 1 if fails else 0


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--csv", help="FRED DGS10 CSV")
    p.add_argument("--start", help="ISO date; use 2019-01-01 for the out-of-sample test")
    p.add_argument("--end", help="ISO date")
    p.add_argument("--window", type=int, default=WINDOW_DAYS)
    p.add_argument("--selftest", action="store_true")
    a = p.parse_args()
    if a.selftest:
        return selftest()
    if not a.csv:
        p.error("--csv is required (or --selftest)")
    rows = load_yields(a.csv)
    if a.start:
        s = dt.date.fromisoformat(a.start)
        rows = [r for r in rows if r[0] >= s]
    if a.end:
        e = dt.date.fromisoformat(a.end)
        rows = [r for r in rows if r[0] <= e]
    if len(rows) < 2:
        print("  REFUSED -- fewer than two usable observations after filtering.")
        return 1
    if a.window != WINDOW_DAYS:
        print(f"  NOTE: window is {a.window}, not the pre-registered {WINDOW_DAYS}. "
              f"This is exploratory and its result is NOT the pre-registered test.\n")
    res = analyse(daily_returns(rows), a.window)
    print(render(res))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())

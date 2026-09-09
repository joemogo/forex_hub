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

# THE PAPER'S MATURITY GRADIENT IS ENTIRELY DURATION, AND THAT IS THE MOST USEFUL FACT IN IT.
#
# Hartley & Schwarz report the effect RISING with maturity: 6bp at 2y, 15bp at 5y, 25bp at
# 10y. Divide each by that maturity's approximate modified duration (1.9, 4.6, 8.0):
#
#       2y   6.0 / 1.9  =  3.16 bp
#       5y  15.0 / 4.6  =  3.26 bp
#      10y  25.0 / 8.0  =  3.12 bp
#
# Within 4% of one another. The gradient is not three findings, it is ONE finding seen
# through three different durations: yields fall about 3.2bp into month-end at every point
# on the curve, and the price effect is larger at the long end only because duration is.
#
# This matters twice over:
#
#   1. THE TEST CAN RUN IN YIELD SPACE, where FRED's data is exact. The duration
#      approximation -- the weakest assumption in this file -- is then needed only to convert
#      a confirmed result into P&L, never to decide whether the effect is there.
#
#   2. IT SHARPENS THE PREDICTION ENORMOUSLY. "Some positive number appeared" is weak. "About
#      -3.2bp, at 2y AND 5y AND 10y independently" is a specific, falsifiable signature that
#      noise has to work hard to imitate.
PAPER_YIELD_BP = -3.18   # mean yield CHANGE across the month-end window; negative = yields fall
YIELD_AGREEMENT_SE = 2.0 # maturities agree if every pairwise difference is within this many SE
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


def analyse_yield(rows, window=WINDOW_DAYS):
    """Mean YIELD CHANGE across each month-end window, in basis points. No duration anywhere.

    This is the primary measurement. It uses FRED's numbers as published and inherits none of
    the duration approximation, so a result here is a statement about the bond market rather
    than about my arithmetic. The prediction is PAPER_YIELD_BP -- about -3.2bp, yields falling
    into month-end -- and it is the same number at every maturity.
    """
    if len(rows) < 2:
        return {"ok": False, "reason": "TOO_FEW_OBSERVATIONS", "n_events": 0}
    dates = [d for d, _ in rows]
    flags = month_end_flags(dates, window)
    # Change across the window = last yield in it minus the yield on the last day BEFORE it.
    # Differencing inside the window and summing would give the same answer; anchoring to the
    # prior close is stated explicitly so the boundary is not left to the reader.
    per_month, prior = {}, {}
    for i, ((d, y), f) in enumerate(zip(rows, flags)):
        key = (d.year, d.month)
        if f:
            if key not in prior:
                prior[key] = rows[i - 1][1] if i > 0 else None
            per_month[key] = y
    events = [(per_month[k] - prior[k]) * 100.0      # percent -> basis points
              for k in per_month if prior.get(k) is not None]
    n = len(events)
    if n < 2:
        return {"ok": False, "reason": "TOO_FEW_MONTHS", "n_events": n}
    mean = sum(events) / n
    sd = math.sqrt(sum((x - mean) ** 2 for x in events) / (n - 1))
    se = sd / math.sqrt(n)
    return {"ok": True, "n_events": n, "mean_bp": mean, "sd_bp": sd, "se_bp": se,
            "t": (mean / se) if se else None,
            "detection_floor_bp": detection_floor(sd, n),
            "first": min(dates).isoformat(), "last": max(dates).isoformat(),
            # Yields FALLING into month-end is the paper's direction. A positive mean here
            # contradicts it regardless of how significant it is.
            "direction_matches": mean < 0,
            "significant": (se is not None) and abs(mean / se) > Z95}


def compare_maturities(results):
    """Do the maturities agree on one common yield effect, as the paper's own numbers do?

    `results` is {label: analyse_yield(...)}. Agreement is the corroborating signature: a
    single positive mean is easy for noise to produce, three maturities independently landing
    on the same number is not. Under exchangeable maturities the chance that all pairwise
    differences fall within YIELD_AGREEMENT_SE is small, and it is reported rather than
    asserted.
    """
    usable = {k: v for k, v in results.items() if v.get("ok")}
    if len(usable) < 2:
        return {"ok": False, "reason": "NEED_TWO_MATURITIES", "n_maturities": len(usable)}
    labels = sorted(usable)
    worst, worst_pair = 0.0, None
    for i in range(len(labels)):
        for j in range(i + 1, len(labels)):
            a, b = usable[labels[i]], usable[labels[j]]
            se = math.sqrt(a["se_bp"] ** 2 + b["se_bp"] ** 2)
            if not se > 0:
                continue
            z = abs(a["mean_bp"] - b["mean_bp"]) / se
            if z > worst:
                worst, worst_pair = z, (labels[i], labels[j])
    means = [usable[k]["mean_bp"] for k in labels]
    return {"ok": True, "n_maturities": len(usable), "labels": labels, "means_bp": means,
            "worst_z": worst, "worst_pair": worst_pair,
            "agree": worst <= YIELD_AGREEMENT_SE,
            "all_same_direction": all(m < 0 for m in means) or all(m > 0 for m in means),
            "all_match_paper_direction": all(m < 0 for m in means)}


def render_yield(a, label="10y"):
    if not a.get("ok"):
        return f"  {label}: REFUSED -- {a.get('reason')} (n_events={a.get('n_events')})"
    return (f"  {label:<5} n={a['n_events']:<4} mean {a['mean_bp']:+6.2f} bp   "
            f"SE {a['se_bp']:4.2f}   t {a['t']:+5.2f}   "
            f"floor {a['detection_floor_bp']:5.2f}   "
            f"{'falls (matches paper)' if a['direction_matches'] else 'RISES (contradicts)'}"
            f"{'' if a['significant'] else '   [not significant]'}")


def render_comparison(c):
    if not c.get("ok"):
        return f"  REFUSED -- {c.get('reason')}"
    L = [f"  maturities        {', '.join(c['labels'])}",
         f"  means (bp)        " + ", ".join(f"{m:+.2f}" for m in c["means_bp"]),
         f"  worst disagreement {c['worst_z']:.2f} SE"
         + (f"  ({c['worst_pair'][0]} vs {c['worst_pair'][1]})" if c["worst_pair"] else ""),
         "",
         f"  all fall into month-end    {c['all_match_paper_direction']}",
         f"  agree within {YIELD_AGREEMENT_SE:.0f} SE          {c['agree']}",
         f"  paper's common value       {PAPER_YIELD_BP:+.2f} bp"]
    if c["all_match_paper_direction"] and c["agree"]:
        v = ("CORROBORATED -- every maturity falls into month-end and they agree on one "
             "value, which is the paper's own signature")
    elif c["all_match_paper_direction"]:
        v = ("DIRECTION HOLDS, MAGNITUDES DISAGREE -- consistent with a real but unstable "
             "effect, or with one maturity being driven by something else")
    elif c["all_same_direction"]:
        v = "INVERTED -- consistent across maturities but the WRONG WAY. Not the paper's effect."
    else:
        v = "NO COMMON SIGNATURE -- maturities disagree in direction. Most consistent with noise."
    L += ["", f"  VERDICT           {v}"]
    return "\n".join(L)


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

    # ── YIELD-SPACE PATH. The primary measurement, and it must be tested as hard. ─────────
    def synth_yields(months, drop_bp, seed=3, per_month=21, start=2.00, on_day=None):
        """Daily yields with `drop_bp` of decline planted across each month's last 3 days.

        `on_day` concentrates the whole drop on one day of that window (0 = its first day),
        which is what makes the window's ANCHOR testable -- see Y9.
        """
        import random
        rng = random.Random(seed)
        out, y, m, level = [], 2019, 1, start
        for _ in range(months):
            for k in range(per_month):
                day = dt.date(y, m, min(k + 1, 28))
                level += rng.gauss(0, 0.04)                        # ~4bp of daily noise
                pos = k - (per_month - 3)                          # 0,1,2 inside the window
                if pos >= 0:
                    share = 1.0 if (on_day is not None and pos == on_day) else \
                            (0.0 if on_day is not None else 1.0 / 3.0)
                    level += (-drop_bp * share) / 100.0            # bp -> percent
                out.append((day, level))
            m += 1
            if m > 12:
                m, y = 1, y + 1
        return out

    # Y1 DIRECTION. Yields falling must read as a match, and the sign must not be flipped.
    y1 = analyse_yield(synth_yields(150, 3.18), 3)
    check("planted yield drop is detected as falling", y1["direction_matches"], True)
    check("planted yield drop recovered", abs(y1["mean_bp"] - (-3.18)) < 1.5, True)
    check("planted yield drop is significant", y1["significant"], True)

    # Y2 INVERTED. A RISING yield must contradict, not quietly pass on magnitude alone.
    y2 = analyse_yield(synth_yields(150, -3.18, seed=8), 3)
    check("rising yield contradicts the paper", y2["direction_matches"], False)

    # Y3 NULL must not pass.
    y3 = analyse_yield(synth_yields(150, 0.0, seed=12), 3)
    check("yield null is not significant", y3["significant"], False)

    # Y4 DEGENERATE.
    check("empty yield series refuses", analyse_yield([], 3)["ok"], False)
    check("one month refuses", analyse_yield(synth_yields(1, 3.18), 3)["ok"], False)

    # Y5 CROSS-MATURITY AGREEMENT. Three maturities on the same effect must corroborate.
    same = {lab: analyse_yield(synth_yields(150, 3.18, seed=s), 3)
            for lab, s in (("02y", 21), ("05y", 22), ("10y", 23))}
    c = compare_maturities(same)
    check("agreeing maturities are recognised", c["agree"], True)
    check("agreeing maturities all match direction", c["all_match_paper_direction"], True)
    check("corroborated verdict rendered", "CORROBORATED" in render_comparison(c), True)

    # Y6 DISAGREEMENT must be caught -- otherwise the check is decoration. One maturity
    # planted with a large opposite effect has to break agreement AND direction.
    mixed = dict(same)
    mixed["30y"] = analyse_yield(synth_yields(150, -12.0, seed=24), 3)
    cm = compare_maturities(mixed)
    check("disagreeing maturity breaks agreement", cm["agree"], False)
    check("disagreeing maturity breaks direction", cm["all_match_paper_direction"], False)
    check("no-common-signature verdict rendered",
          "NO COMMON SIGNATURE" in render_comparison(cm), True)

    # Y7 A single maturity cannot be "compared" -- it must refuse rather than self-agree.
    check("one maturity refuses to compare",
          compare_maturities({"10y": same["10y"]})["ok"], False)
    check("no usable maturities refuses",
          compare_maturities({"10y": {"ok": False}})["ok"], False)

    # Y9 THE WINDOW'S ANCHOR. The change must be measured from the close BEFORE the window,
    # not from its first day -- otherwise a 3-day window silently measures 2 days.
    #
    # Added after mutation M15 (`prior[key] = rows[i][1]`) survived: with the drop spread
    # evenly it recovered two thirds of the effect, which sat inside Y1's tolerance and
    # looked like mild decay. Concentrating the entire drop on the window's FIRST day makes
    # the two anchorings disagree completely instead of slightly -- correct anchoring sees
    # the whole effect, wrong anchoring sees none of it.
    y9 = analyse_yield(synth_yields(150, 6.0, seed=31, on_day=0), 3)
    check("drop on the window's first day is captured", y9["mean_bp"] < -4.0, True)
    check("first-day drop is significant", y9["significant"], True)
    # And the mirror: a drop on the LAST day is captured under either anchoring, so it must
    # NOT be used as the discriminator. Asserted so nobody later "simplifies" Y9 into it.
    y9b = analyse_yield(synth_yields(150, 6.0, seed=32, on_day=2), 3)
    check("drop on the window's last day is also captured", y9b["mean_bp"] < -4.0, True)

    # Y8 The paper's own numbers must pass its own check. If the reference case fails, the
    # thresholds are wrong, not the data.
    check("paper's implied yield effect is negative", PAPER_YIELD_BP < 0, True)
    check("paper's three maturities agree within 4%",
          max(6.0 / 1.9, 15.0 / 4.6, 25.0 / 8.0) / min(6.0 / 1.9, 15.0 / 4.6, 25.0 / 8.0) < 1.05,
          True)

    for f_ in fails:
        print("FAIL -- " + f_)
    print(f"selftest: {'PASS' if not fails else 'FAIL'} ({len(fails)} failure(s))")
    return 1 if fails else 0


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--csv", help="FRED DGS10 CSV")
    p.add_argument("--compare", nargs="+", metavar="LABEL=CSV",
                   help="two or more maturities, e.g. 02y=DGS2.csv 05y=DGS5.csv 10y=DGS10.csv")
    p.add_argument("--start", help="ISO date; use 2019-01-01 for the out-of-sample test")
    p.add_argument("--end", help="ISO date")
    p.add_argument("--window", type=int, default=WINDOW_DAYS)
    p.add_argument("--selftest", action="store_true")
    a = p.parse_args()
    if a.selftest:
        return selftest()
    if not a.csv and not a.compare:
        p.error("--csv or --compare is required (or --selftest)")
    if a.window != WINDOW_DAYS:
        print(f"  NOTE: window is {a.window}, not the pre-registered {WINDOW_DAYS}. "
              f"This is exploratory and its result is NOT the pre-registered test.\n")

    def prepared(path):
        rows = load_yields(path)
        if a.start:
            s = dt.date.fromisoformat(a.start)
            rows = [r for r in rows if r[0] >= s]
        if a.end:
            e = dt.date.fromisoformat(a.end)
            rows = [r for r in rows if r[0] <= e]
        return rows

    if a.compare:
        results = {}
        for spec in a.compare:
            if "=" not in spec:
                p.error(f"--compare needs LABEL=CSV, got {spec!r}")
            lab, path = spec.split("=", 1)
            results[lab] = analyse_yield(prepared(path), a.window)
        print("  PRIMARY MEASUREMENT -- yield space, no duration assumption\n")
        for lab in sorted(results):
            print(render_yield(results[lab], lab))
        print()
        c = compare_maturities(results)
        print(render_comparison(c))
        return 0 if c.get("ok") else 1

    rows = prepared(a.csv)
    if len(rows) < 2:
        print("  REFUSED -- fewer than two usable observations after filtering.")
        return 1
    yres = analyse_yield(rows, a.window)
    print("  PRIMARY -- yield space, no duration assumption\n")
    print(render_yield(yres, "10y"))
    print(f"\n  paper implies {PAPER_YIELD_BP:+.2f} bp at every maturity "
          f"(its 6/15/25bp gradient is duration, not three findings)\n")
    print("  DERIVED -- price return, duration-approximated. A screen, not a backtest.\n")
    res = analyse(daily_returns(rows), a.window)
    print(render(res))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())

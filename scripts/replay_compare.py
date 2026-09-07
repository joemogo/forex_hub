#!/usr/bin/env python3
"""Compare MOGO replay evidence packages, the same way every time.

WHY THIS EXISTS. The identical analysis has now been typed by hand four times -- ALEX,
baseline_trend_v1, crt_v1, psych_level_v1 -- and it is the same analysis each time: per-arm
distribution, an error bar, a pairwise difference, a subgroup sweep with a multiple-comparison
correction, and spread charged per trade. Retyping it is slow and, worse, it means the method can
drift between runs without anyone noticing. CLAUDE.md: prefer a diagnostic to a reconstruction.

WHAT IT REFUSES TO DO, and why each refusal is here:

  * It will not mix captureBasis populations. REPLAY_RUN and LIVE_CLOSE answer different
    questions, and silently averaging them has already cost this project a published conclusion.
  * It will not report a win rate of 0% for an arm with nothing decisive closed. That is null.
  * It will not charge spread against the mean. Spread cost in R is spread/risk, so it scales
    INVERSELY with stop size and is not neutral between arms whose stops differ -- charging it
    against an average understates the damage to the tighter-stopped arm. This is the exact error
    that hid the CRT result for an afternoon.
  * It will not report a subgroup as significant on its uncorrected p-value. Slicing 17 ways and
    keeping the best one manufactures findings.
  * It reports MEDIAN planned R and stop size beside the means. A mean planned R of 10.46 sat
    next to a median of 1.57 in the CRT run, and that gap was the entire result.

Usage:
    python3 scripts/replay_compare.py PACKAGE [PACKAGE ...] [--spread PIPS] [--band LO HI]

    --spread  pips of spread to charge per trade (default 1.0; 0 disables)
    --band    restrict to trades whose stop is within LO..HI pips, so two arms with different
              stop-size distributions can be compared on comparable geometry
"""

import argparse
import json
import math
import os
import statistics
import sys


def pip_size(instrument):
    return 0.01 if instrument and "JPY" in instrument else 0.0001


def load_trades(path):
    """Flatten one evidence package into trade records. Returns (meta, trades)."""
    with open(path) as fh:
        pkg = json.load(fh)
    objs = pkg.get("objects") or {}
    setups = {s.get("setupId"): s for s in objs.get("qualifiedSetups") or []}
    outcomes = {o.get("positionId"): o for o in objs.get("outcomes") or []}
    meta = {
        "path": os.path.basename(path),
        "strategyId": (pkg.get("identity") or {}).get("strategyId"),
        "strategyVersion": (pkg.get("identity") or {}).get("strategyVersion"),
        "captureBasis": pkg.get("captureBasis"),
        "mode": (pkg.get("identity") or {}).get("mode"),
        "config": pkg.get("configSnapshot") or {},
        "disclosures": pkg.get("replayDisclosures") or {},
    }
    trades = []
    for pos in objs.get("positions") or []:
        s = setups.get(pos.get("setupId"))
        o = outcomes.get(pos.get("positionId"))
        if not s or not o:
            continue
        r = o.get("realizedR")
        if not isinstance(r, (int, float)):
            continue                                    # still open, or no decisive result
        refs = s.get("structureRefs") or {}
        risk = refs.get("riskPips")
        if not isinstance(risk, (int, float)) or risk <= 0:
            entry, stop = pos.get("entryPrice"), pos.get("originalStop")
            if isinstance(entry, (int, float)) and isinstance(stop, (int, float)):
                risk = abs(entry - stop) / pip_size(pos.get("instrument"))
            else:
                risk = None
        # The arm label: a controlled experiment names it explicitly; otherwise the setup type
        # is the honest fallback, and a single-arm package gets one bucket.
        arm = refs.get("arm") or s.get("setupType") or meta["strategyId"] or "all"
        trades.append({
            "arm": str(arm),
            "pair": pos.get("instrument"),
            "tf": pos.get("timeframe"),
            "setupType": s.get("setupType"),
            "R": float(r),
            "win": r > 0,
            "risk": risk,
            "plannedRR": pos.get("plannedRR"),
        })
    return meta, trades


def summarize(rows, spread_pips):
    """Per-arm distribution. Returns None for an empty set rather than a fabricated zero."""
    if not rows:
        return None
    R = [t["R"] for t in rows]
    n = len(R)
    mean = sum(R) / n
    se = statistics.stdev(R) / math.sqrt(n) if n > 1 else None
    risks = [t["risk"] for t in rows if isinstance(t["risk"], (int, float)) and t["risk"] > 0]
    rrs = [t["plannedRR"] for t in rows if isinstance(t["plannedRR"], (int, float))]
    charged = None
    if spread_pips and risks:
        with_cost = [t["R"] - spread_pips / t["risk"]
                     for t in rows if isinstance(t["risk"], (int, float)) and t["risk"] > 0]
        charged = sum(with_cost) / len(with_cost)
    return {
        "n": n,
        "wins": sum(1 for t in rows if t["win"]),
        "winRate": sum(1 for t in rows if t["win"]) / n,
        "mean": mean,
        "se": se,
        "ci": (mean - 1.96 * se, mean + 1.96 * se) if se else None,
        "medPlannedRR": statistics.median(rrs) if rrs else None,
        "meanPlannedRR": sum(rrs) / len(rrs) if rrs else None,
        "medRisk": statistics.median(risks) if risks else None,
        "tightStopShare": sum(1 for r in risks if r < 5) / len(risks) if risks else None,
        "spreadCharged": charged,
    }


def fmt(x, places=3, suffix=""):
    if x is None:
        return "—"
    return ("%+." + str(places) + "f") % x + suffix if places else str(x)


def arm_table(by_arm, spread_pips):
    hdr = ("%-26s %6s %7s %8s %8s %7s %8s %9s %18s %10s"
           % ("arm", "n", "win%", "medR", "medStop", "<5p", "R/trade", "1 SE",
              "95% CI", "-%.1fp" % spread_pips))
    lines = [hdr, "-" * len(hdr)]
    for arm in sorted(by_arm, key=lambda a: -by_arm[a]["n"]):
        s = by_arm[arm]
        ci = ("%+.3f to %+.3f" % s["ci"]) if s["ci"] else "—"
        lines.append("%-26s %6d %6.1f%% %8s %8s %6s %8s %9s %18s %10s" % (
            arm[:26], s["n"], 100 * s["winRate"],
            ("%.2f" % s["medPlannedRR"]) if s["medPlannedRR"] is not None else "—",
            ("%.1f" % s["medRisk"]) if s["medRisk"] is not None else "—",
            ("%.1f%%" % (100 * s["tightStopShare"])) if s["tightStopShare"] is not None else "—",
            fmt(s["mean"]), ("±%.3f" % s["se"]) if s["se"] else "—",
            ci, fmt(s["spreadCharged"])))
    return "\n".join(lines)


def compare(a, b, label_a, label_b):
    if not a or not b or a["se"] is None or b["se"] is None:
        return "  %s vs %s: not comparable (an arm has too few decisive trades)" % (label_a, label_b)
    d = a["mean"] - b["mean"]
    se = math.sqrt(a["se"] ** 2 + b["se"] ** 2)
    z = d / se if se else float("nan")
    lo, hi = d - 1.96 * se, d + 1.96 * se
    verdict = ("DISTINGUISHABLE" if abs(z) > 1.96
               else "not distinguishable from zero")
    return ("  %s minus %s: %+.4f R   z=%+.2f   95%% CI %+.3f to %+.3f   -> %s\n"
            "    an effect larger than %.3f R/trade is ruled out at 95%%"
            % (label_a, label_b, d, z, lo, hi, verdict, abs(d) + 1.96 * se))


def subgroups(trades, spread_pips, min_n=30):
    """Slice by pair, timeframe and setup type, then apply Sidak across every slice examined.

    The correction counts EVERY slice looked at, not just the interesting ones -- otherwise the
    correction is chosen after seeing the answer, which defeats it.
    """
    dims = [("setup type", "setupType"), ("timeframe", "tf"), ("pair", "pair")]
    slices = []
    for label, key in dims:
        groups = {}
        for t in trades:
            if t.get(key) is not None:
                groups.setdefault(t[key], []).append(t)
        qualifying = {k: rows for k, rows in groups.items() if len(rows) >= min_n}
        # A dimension with ONE level is not a slice -- it is the overall result wearing a label.
        # Reporting it as a subgroup finding is circular, and counting it inflates the correction
        # denominator, which makes every real slice harder to detect. Caught when a CRT package
        # (H4 only) reported "timeframe H4, z=4.09, SURVIVES" -- a restatement of the whole run.
        if len(qualifying) < 2:
            continue
        for k, rows in qualifying.items():
            s = summarize(rows, spread_pips)
            if s and s["se"]:
                slices.append((label, str(k), s))
    if not slices:
        return "  no slice reached the %d-trade minimum" % min_n
    k = len(slices)
    alpha = 1 - (1 - 0.05) ** (1.0 / k)
    # Two-sided normal quantile for the corrected alpha, by bisection -- no scipy in this env.
    lo, hi = 0.0, 10.0
    target = 1 - alpha / 2
    for _ in range(200):
        mid = (lo + hi) / 2
        cdf = 0.5 * (1 + math.erf(mid / math.sqrt(2)))
        if cdf < target:
            lo = mid
        else:
            hi = mid
    zcrit = (lo + hi) / 2
    out = ["  %d slices examined -> Sidak alpha %.4f -> |z| must exceed %.2f" % (k, alpha, zcrit),
           "  %-12s %-12s %6s %8s %8s   %s" % ("dimension", "slice", "n", "R/trade", "z", "survives?")]
    survivors = []
    for label, name, s in sorted(slices, key=lambda x: abs(x[2]["mean"] / x[2]["se"]), reverse=True):
        z = s["mean"] / s["se"]
        ok = abs(z) > zcrit
        if ok:
            survivors.append((label, name, s["mean"]))
        out.append("  %-12s %-12s %6d %8s %8.2f   %s"
                   % (label, name[:12], s["n"], fmt(s["mean"]), z, "YES" if ok else "no"))
    if survivors:
        pos = [s for s in survivors if s[2] > 0]
        out.append("")
        out.append("  %d slice(s) survive correction; %d of them positive." % (len(survivors), len(pos)))
        if not pos:
            out.append("  EVERY surviving slice is NEGATIVE -- there is no pocket of edge here, "
                       "only pockets of worse.")
    else:
        out.append("")
        out.append("  Nothing survives correction. No subgroup escapes the overall result.")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("packages", nargs="+")
    ap.add_argument("--spread", type=float, default=1.0,
                    help="pips of spread charged per trade (0 disables)")
    ap.add_argument("--band", nargs=2, type=float, metavar=("LO", "HI"),
                    help="restrict to trades with a stop between LO and HI pips")
    ap.add_argument("--min-n", type=int, default=30, help="minimum trades for a subgroup slice")
    args = ap.parse_args()

    all_trades, metas = [], []
    for p in args.packages:
        meta, trades = load_trades(p)
        metas.append((meta, len(trades)))
        for t in trades:
            t["_pkg"] = meta["strategyId"] or meta["path"]
        all_trades.extend(trades)

    print("=" * 100)
    print("MOGO REPLAY COMPARISON")
    print("=" * 100)
    for meta, n in metas:
        print("  %-46s %-18s %-12s %5d decisive trades"
              % (meta["path"][:46], meta["strategyId"], meta["captureBasis"], n))

    # A population mix is refused, not warned about. The two answer different questions.
    bases = {m["captureBasis"] for m, _ in metas}
    if len(bases) > 1:
        print("\nREFUSED: these packages carry different captureBasis values (%s)."
              % ", ".join(sorted(str(b) for b in bases)))
        print("Replay and forward populations answer different questions and are never averaged.")
        print("Run them separately.")
        return 2

    if args.band:
        lo, hi = args.band
        before = len(all_trades)
        all_trades = [t for t in all_trades
                      if isinstance(t["risk"], (int, float)) and lo <= t["risk"] <= hi]
        print("\n  MATCHED GEOMETRY: stops between %.0f and %.0f pips — %d of %d trades kept."
              % (lo, hi, len(all_trades), before))
        print("  Two arms may only be compared raw when their stop distributions match; this is"
              " how that is enforced rather than assumed.")

    if not all_trades:
        print("\nNo decisive trades. Nothing to report — and that is a result, not an error.")
        return 0

    by_arm = {}
    for t in all_trades:
        by_arm.setdefault(t["arm"], []).append(t)
    summaries = {a: summarize(rows, args.spread) for a, rows in by_arm.items()}
    summaries = {a: s for a, s in summaries.items() if s}

    print("\n" + "-" * 100)
    print("PER ARM  (read left to right: sample and geometry BEFORE the win rate)")
    print("-" * 100)
    print(arm_table(summaries, args.spread))

    if len(summaries) >= 2:
        print("\n" + "-" * 100)
        print("PAIRWISE")
        print("-" * 100)
        names = sorted(summaries, key=lambda a: -summaries[a]["n"])
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                print(compare(summaries[names[i]], summaries[names[j]], names[i], names[j]))

    print("\n" + "-" * 100)
    print("SUBGROUPS  (corrected for the number of slices examined)")
    print("-" * 100)
    print(subgroups(all_trades, args.spread, args.min_n))

    print("\n" + "-" * 100)
    print("CAVEATS CARRIED FROM THE PACKAGES")
    print("-" * 100)
    seen = set()
    for meta, _ in metas:
        for k in ("entryComparabilityWarning", "referenceCandleSelection", "frictionNote",
                  "frictionIsNotNeutralBetweenArms", "entryNote", "populationNote"):
            v = meta["disclosures"].get(k)
            if v and v not in seen:
                seen.add(v)
                print("  * %s" % v)
    if not seen:
        print("  (none recorded in these packages)")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())

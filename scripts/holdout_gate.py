#!/usr/bin/env python3
"""Freeze a sample, hide half of it, and let the pre-registered test run EXACTLY ONCE.

WHY THIS EXISTS. Six arms were built in this project and every one of them was measured on
the same data it was explored on. That is not a moral failure, it is the default: you look
at the data, something looks promising, you test the promising thing, and the test has
already been contaminated by the looking. The p-value that comes out is not the p-value you
think it is.

The only external methodology this project has seen that produced an honest answer used a
train/hidden-test split: ~3,699 trades, explore on the training half, test once on data
never examined. The reported outcome was "almost nothing survived. Most of what looked
promising in training fell apart the moment I tested it on the hidden data." That is what a
correctly-run gate looks like from the inside. It mostly says no.

WHAT THIS ENFORCES, AND WHAT IT CANNOT.

  ENFORCED   the split is deterministic from a declared seed, so it cannot be re-rolled
             until it looks favourable
  ENFORCED   the split is stable when the population grows -- new records get assigned, old
             records keep their side, so a sample cannot be "refreshed" into a better answer
  ENFORCED   the hypothesis, the threshold and the population are hashed into a manifest
             BEFORE the holdout is touched; changing any of them afterwards makes the test
             refuse to run
  ENFORCED   the holdout test runs once per manifest. A second run returns the first
             verdict, not a new one.

  NOT ENFORCED   nothing stops a person deleting the manifest and starting over. This is a
                 discipline aid, not a security control, and pretending otherwise would be
                 the same class of error as a pass condition that lives only in prose.
                 What it does is make re-rolling a deliberate act instead of an accident.

USAGE
  # 1. freeze -- do this BEFORE looking at anything
  python3 scripts/holdout_gate.py freeze --records trades.json --id-field tradeId \\
      --outcome-field realizedR --group-field armSide \\
      --hypothesis "kept beats rejected by more than 0.06R gross" \\
      --min-effect 0.06 --seed alex-progression-2026-09 --manifest .holdout/alex.json

  # 2. explore the TRAIN half as much as you like -- no p-values leave this side
  python3 scripts/holdout_gate.py train --manifest .holdout/alex.json --records trades.json

  # 3. test the HOLDOUT half. Once.
  python3 scripts/holdout_gate.py test --manifest .holdout/alex.json --records trades.json

  python3 scripts/holdout_gate.py --selftest
"""
import argparse, hashlib, json, math, os, statistics, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from candidate_power import assess, detection_floor  # noqa: E402

SCHEMA = "holdout_gate_v1"
DEFAULT_HOLDOUT_RATIO = 0.40
BUCKETS = 100000


# ──────────────────────────────────────────────────────────────────────────────────────────
# THE SPLIT
# ──────────────────────────────────────────────────────────────────────────────────────────

def _bucket(seed, record_id):
    """Deterministic 0..BUCKETS-1 from the seed and the record's own id.

    Hashing the ID -- not the row index, not a running counter -- is what makes the split
    STABLE UNDER GROWTH. Adding 500 new trades next month assigns those 500 and leaves every
    existing record on the side it was already on. An index-based or shuffle-based split
    silently reshuffles the whole population on every refresh, which quietly hands you a
    fresh holdout every time the old one disappoints. That is the failure mode this line
    exists to prevent.
    """
    h = hashlib.sha256((str(seed) + "\x00" + str(record_id)).encode("utf-8")).hexdigest()
    return int(h[:12], 16) % BUCKETS


def side_of(seed, record_id, holdout_ratio):
    """'HOLDOUT' or 'TRAIN'. Pure, order-independent, and identical on every machine."""
    return "HOLDOUT" if _bucket(seed, record_id) < holdout_ratio * BUCKETS else "TRAIN"


def split_records(records, seed, id_field, holdout_ratio):
    """Partition into (train, holdout). Refuses on a duplicate or missing id.

    A duplicate id is not a nuisance to be tolerated -- the same record could land on both
    sides and the holdout would no longer be hidden. It is a hard stop.
    """
    seen, train, holdout = set(), [], []
    for r in records:
        rid = r.get(id_field)
        if rid is None or rid == "":
            raise ValueError(f"record missing '{id_field}': cannot be split reproducibly")
        if rid in seen:
            raise ValueError(f"duplicate id {rid!r}: a record could land on both sides")
        seen.add(rid)
        (holdout if side_of(seed, rid, holdout_ratio) == "HOLDOUT" else train).append(r)
    return train, holdout


# ──────────────────────────────────────────────────────────────────────────────────────────
# THE MANIFEST — what gets locked, and how tampering is detected
# ──────────────────────────────────────────────────────────────────────────────────────────

def population_hash(records, id_field):
    """Hash of the sorted id set. Order-independent, so re-serialising the file is not
    tampering, but adding or removing a single record is."""
    ids = sorted(str(r.get(id_field)) for r in records)
    return hashlib.sha256("\x00".join(ids).encode("utf-8")).hexdigest()


def manifest_hash(m):
    """Hash of everything that must not change after the freeze.

    Deliberately EXCLUDES 'runs' -- the manifest is written to when a test executes, and that
    write must not invalidate it. Everything a person could tune to manufacture a pass is in
    here: the hypothesis text, the threshold, the seed, the ratio, the population.
    """
    locked = {k: m[k] for k in (
        "schema", "seed", "holdout_ratio", "id_field", "outcome_field", "group_field",
        "hypothesis", "min_effect", "population_hash", "n_total")}
    return hashlib.sha256(json.dumps(locked, sort_keys=True).encode("utf-8")).hexdigest()


def freeze(records, seed, hypothesis, min_effect, id_field, outcome_field,
           group_field=None, holdout_ratio=DEFAULT_HOLDOUT_RATIO):
    """Build the locked manifest. Nothing here looks at an outcome value."""
    if not records:
        raise ValueError("cannot freeze an empty population")
    if not (0.0 < holdout_ratio < 1.0):
        raise ValueError("holdout_ratio must be strictly between 0 and 1")
    if not hypothesis or not str(hypothesis).strip():
        raise ValueError("a freeze without a stated hypothesis is not a pre-registration")
    train, holdout = split_records(records, seed, id_field, holdout_ratio)
    if not train or not holdout:
        raise ValueError(f"degenerate split: {len(train)} train / {len(holdout)} holdout")
    m = {
        "schema": SCHEMA,
        "seed": seed,
        "holdout_ratio": holdout_ratio,
        "id_field": id_field,
        "outcome_field": outcome_field,
        "group_field": group_field,
        "hypothesis": hypothesis,
        "min_effect": min_effect,
        "population_hash": population_hash(records, id_field),
        "n_total": len(records),
        "n_train": len(train),
        "n_holdout": len(holdout),
        "runs": [],
    }
    m["manifest_hash"] = manifest_hash(m)
    return m


def verify_manifest(m, records):
    """Every reason the holdout test may refuse. Returns a list -- empty means clean."""
    problems = []
    if m.get("schema") != SCHEMA:
        problems.append(f"manifest schema is {m.get('schema')!r}, expected {SCHEMA!r}")
        return problems
    if manifest_hash(m) != m.get("manifest_hash"):
        problems.append("MANIFEST ALTERED after freeze: the hypothesis, threshold, seed, "
                        "ratio or population was edited. The holdout is no longer hidden.")
    if population_hash(records, m["id_field"]) != m["population_hash"]:
        problems.append("POPULATION CHANGED since freeze: records were added or removed. "
                        "Re-freeze on the new population and state that you did.")
    if m.get("runs"):
        problems.append(f"ALREADY RUN {len(m['runs'])} time(s). The holdout is spent.")
    return problems


# ──────────────────────────────────────────────────────────────────────────────────────────
# THE TEST
# ──────────────────────────────────────────────────────────────────────────────────────────

def two_sample(a, b):
    """Difference of means with an honest standard error. Records, never a sentence."""
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return {"ok": False, "reason": "TOO_FEW", "n_a": na, "n_b": nb}
    ma, mb = statistics.fmean(a), statistics.fmean(b)
    va, vb = statistics.variance(a), statistics.variance(b)
    se = math.sqrt(va / na + vb / nb)
    if not se > 0:
        return {"ok": False, "reason": "ZERO_VARIANCE", "n_a": na, "n_b": nb}
    diff = ma - mb
    return {"ok": True, "n_a": na, "n_b": nb, "mean_a": ma, "mean_b": mb,
            "diff": diff, "se": se, "t": diff / se,
            # Pooled sigma, for the detection floor. The floor asks what THIS sample could
            # have resolved, which is a property of the spread and the count, not of the
            # answer that came back.
            "sigma": math.sqrt((va * (na - 1) + vb * (nb - 1)) / (na + nb - 2)),
            "n_total": na + nb}


def run_holdout_test(m, records, t_bar=1.959963984540054):
    """Evaluate the pre-registered hypothesis on the hidden half. Returns a verdict record.

    THE VERDICT IS BUILT FROM BOOLEANS. No sentence in this project may claim a pass that a
    boolean did not produce -- a carry run once printed "meets the pre-registered
    conditions" on a result that failed a condition living only in prose.
    """
    problems = verify_manifest(m, records)
    if problems:
        return {"ok": False, "refused": True, "problems": problems,
                "previous_runs": m.get("runs", [])}

    _, holdout = split_records(records, m["seed"], m["id_field"], m["holdout_ratio"])
    of, gf = m["outcome_field"], m.get("group_field")

    def val(r):
        v = r.get(of)
        return v if isinstance(v, (int, float)) and math.isfinite(v) else None

    if gf:
        groups = {}
        for r in holdout:
            v = val(r)
            if v is None:
                continue
            groups.setdefault(str(r.get(gf)), []).append(v)
        if len(groups) != 2:
            return {"ok": False, "refused": True,
                    "problems": [f"expected exactly 2 groups in '{gf}', found "
                                 f"{sorted(groups)} -- the pre-registered comparison is "
                                 f"two-sample and will not be reshaped to fit"]}
        (ka, a), (kb, b) = sorted(groups.items())
        stat = two_sample(a, b)
        stat["group_a"], stat["group_b"] = ka, kb
    else:
        vals = [v for v in (val(r) for r in holdout) if v is not None]
        stat = two_sample(vals, [0.0, 0.0] * max(1, len(vals) // 2))
        stat["group_a"], stat["group_b"] = "sample", "zero"

    if not stat.get("ok"):
        return {"ok": False, "refused": True,
                "problems": [f"holdout cannot support the test: {stat.get('reason')}"]}

    floor = detection_floor(stat["sigma"], stat["n_total"])
    power = assess(stat["diff"], stat["sigma"], stat["n_total"], cost=0.0)
    checks = {
        "effect_exceeds_min": stat["diff"] > m["min_effect"],
        "t_exceeds_bar": abs(stat["t"]) > t_bar,
        "above_detection_floor": (floor is not None) and abs(stat["diff"]) > floor,
    }
    return {"ok": True, "refused": False, "stat": stat, "detection_floor": floor,
            "power": power, "checks": checks, "t_bar": t_bar,
            "min_effect": m["min_effect"], "hypothesis": m["hypothesis"],
            "passed": all(checks.values())}


def render(v):
    if v.get("refused"):
        L = ["  REFUSED -- the holdout test did not run."]
        L += [f"    - {p}" for p in v.get("problems", [])]
        for r in v.get("previous_runs", []):
            L.append(f"    first run at {r.get('at')}: "
                     f"{'PASS' if r.get('passed') else 'FAIL'}, diff {r.get('diff'):+.4f}")
        return "\n".join(L)
    s, c = v["stat"], v["checks"]
    L = [f"  hypothesis        {v['hypothesis']}",
         f"  holdout n         {s['n_total']:,}  ({s['group_a']} {s['n_a']:,} / "
         f"{s['group_b']} {s['n_b']:,})",
         f"  difference        {s['diff']:+.4f}   (SE {s['se']:.4f}, t {s['t']:+.2f})",
         f"  detection floor   {v['detection_floor']:.4f}",
         "",
         f"  effect > {v['min_effect']:.4f}      {c['effect_exceeds_min']}",
         f"  |t| > {v['t_bar']:.2f}          {c['t_exceeds_bar']}",
         f"  above floor       {c['above_detection_floor']}",
         "",
         f"  VERDICT           {'PASS' if v['passed'] else 'FAIL'}"]
    if not v["passed"] and c["effect_exceeds_min"] and not c["above_detection_floor"]:
        L.append("                    the effect is above the bar but below what this "
                 "holdout can resolve -- neither a pass nor a null")
    return "\n".join(L)


# ──────────────────────────────────────────────────────────────────────────────────────────

def selftest():
    fails = []

    def check(name, got, want):
        if got != want:
            fails.append(f"{name}: expected {want}, got {got}")

    def recs(n, start=0, eff=0.0, seed=7):
        """Synthetic trades. 'kept' beats 'rejected' by `eff`, deterministically."""
        import random
        rng = random.Random(seed)
        out = []
        for i in range(start, start + n):
            kept = i % 2 == 0
            out.append({"tradeId": f"T{i:06d}", "side": "kept" if kept else "rejected",
                        "realizedR": rng.gauss(eff if kept else 0.0, 1.0)})
        return out

    base = recs(4000)

    # --- the split ---------------------------------------------------------------------
    a1, h1 = split_records(base, "s1", "tradeId", 0.4)
    a2, h2 = split_records(base, "s1", "tradeId", 0.4)
    check("split deterministic", [r["tradeId"] for r in h1], [r["tradeId"] for r in h2])

    shuffled = list(reversed(base))
    _, h3 = split_records(shuffled, "s1", "tradeId", 0.4)
    check("split order-independent",
          sorted(r["tradeId"] for r in h1), sorted(r["tradeId"] for r in h3))

    check("split disjoint",
          set(r["tradeId"] for r in a1) & set(r["tradeId"] for r in h1), set())
    check("split exhaustive", len(a1) + len(h1), len(base))

    # THE ONE THAT MATTERS: growing the population must not move anyone.
    grown = base + recs(500, start=4000)
    _, hg = split_records(grown, "s1", "tradeId", 0.4)
    was = set(r["tradeId"] for r in h1)
    still = set(r["tradeId"] for r in hg if int(r["tradeId"][1:]) < 4000)
    check("split stable under growth", still, was)

    check("split ratio ~40%", abs(len(h1) / len(base) - 0.4) < 0.02, True)

    # A different seed must give a genuinely different split, or the seed is decoration.
    _, hs = split_records(base, "s2", "tradeId", 0.4)
    check("seed changes the split",
          len(was & set(r["tradeId"] for r in hs)) < len(was) * 0.75, True)

    try:
        split_records([{"tradeId": "A"}, {"tradeId": "A"}], "s", "tradeId", 0.4)
        fails.append("duplicate id: expected a refusal, got none")
    except ValueError:
        pass
    try:
        split_records([{"x": 1}], "s", "tradeId", 0.4)
        fails.append("missing id: expected a refusal, got none")
    except ValueError:
        pass

    # --- the freeze --------------------------------------------------------------------
    def fz(records=None, **kw):
        d = dict(seed="s1", hypothesis="kept beats rejected by more than 0.06R",
                 min_effect=0.06, id_field="tradeId", outcome_field="realizedR",
                 group_field="side", holdout_ratio=0.4)
        d.update(kw)
        return freeze(records if records is not None else base, **d)

    m = fz()
    check("freeze is clean", verify_manifest(m, base), [])

    for name, kw in (("empty", {"records": []}), ("no hypothesis", {"hypothesis": "  "}),
                     ("ratio 0", {"holdout_ratio": 0.0}), ("ratio 1", {"holdout_ratio": 1.0})):
        try:
            fz(**kw)
            fails.append(f"freeze {name}: expected a refusal, got none")
        except ValueError:
            pass

    # --- tampering must be caught ------------------------------------------------------
    t = dict(m); t["min_effect"] = 0.001
    check("threshold edit caught", any("ALTERED" in p for p in verify_manifest(t, base)), True)
    t = dict(m); t["hypothesis"] = "anything at all"
    check("hypothesis edit caught", any("ALTERED" in p for p in verify_manifest(t, base)), True)
    t = dict(m); t["seed"] = "s2"
    check("seed reroll caught", any("ALTERED" in p for p in verify_manifest(t, base)), True)
    check("population edit caught",
          any("POPULATION" in p for p in verify_manifest(m, base[:-1])), True)
    # Re-serialising the same records in a different order is NOT tampering.
    check("reordering is not tampering", verify_manifest(m, shuffled), [])

    # --- the test ----------------------------------------------------------------------
    planted = recs(4000, eff=0.30, seed=11)
    mp = fz(records=planted)
    vp = run_holdout_test(mp, planted)
    check("planted effect passes", vp["passed"], True)
    check("planted effect recovered", abs(vp["stat"]["diff"] - 0.30) < 0.12, True)

    null = recs(4000, eff=0.0, seed=13)
    mn = fz(records=null)
    vn = run_holdout_test(mn, null)
    check("null does not pass", vn["passed"], False)

    # A REAL but SUB-BAR effect must fail. This is the case the whole project turns on: an
    # effect can be genuine and still not clear the cost of capturing it.
    small = recs(4000, eff=0.02, seed=17)
    ms = fz(records=small)
    vs = run_holdout_test(ms, small)
    check("sub-bar effect fails", vs["passed"], False)

    # --- run-once ----------------------------------------------------------------------
    mp["runs"].append({"at": "2026-09-09T00:00:00Z", "passed": True, "diff": 0.30})
    v2 = run_holdout_test(mp, planted)
    check("second run refused", v2["refused"], True)
    check("second run says spent", any("ALREADY RUN" in p for p in v2["problems"]), True)
    # Recording a run must NOT itself invalidate the manifest.
    check("run record does not alter hash",
          any("ALTERED" in p for p in v2["problems"]), False)

    # --- degenerate ---------------------------------------------------------------------
    three = [{"tradeId": f"X{i}", "side": ["a", "b", "c"][i % 3], "realizedR": 0.1}
             for i in range(90)]
    m3 = fz(records=three)
    v3 = run_holdout_test(m3, three)
    check("three groups refused", v3["refused"], True)

    for f in fails:
        print("FAIL -- " + f)
    print(f"selftest: {'PASS' if not fails else 'FAIL'} ({len(fails)} failure(s))")
    return 1 if fails else 0


# ──────────────────────────────────────────────────────────────────────────────────────────

def _load(path):
    with open(path) as fh:
        d = json.load(fh)
    return d if isinstance(d, list) else d.get("records", d.get("trades", []))


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("command", nargs="?", choices=["freeze", "train", "test"])
    p.add_argument("--records"); p.add_argument("--manifest")
    p.add_argument("--id-field", default="tradeId")
    p.add_argument("--outcome-field", default="realizedR")
    p.add_argument("--group-field")
    p.add_argument("--hypothesis"); p.add_argument("--min-effect", type=float, default=0.06)
    p.add_argument("--seed"); p.add_argument("--holdout-ratio", type=float,
                                             default=DEFAULT_HOLDOUT_RATIO)
    p.add_argument("--selftest", action="store_true")
    a = p.parse_args()
    if a.selftest:
        return selftest()
    if not a.command:
        p.error("a command is required (freeze | train | test), or --selftest")
    if not a.records or not a.manifest:
        p.error("--records and --manifest are required")

    records = _load(a.records)

    if a.command == "freeze":
        if os.path.exists(a.manifest):
            print(f"  REFUSED -- {a.manifest} already exists. Re-freezing discards a "
                  f"holdout that may already be spent; delete it deliberately if that is "
                  f"what you mean.")
            return 1
        if not a.seed or not a.hypothesis:
            p.error("--seed and --hypothesis are required to freeze")
        m = freeze(records, a.seed, a.hypothesis, a.min_effect, a.id_field,
                   a.outcome_field, a.group_field, a.holdout_ratio)
        os.makedirs(os.path.dirname(os.path.abspath(a.manifest)), exist_ok=True)
        with open(a.manifest, "w") as fh:
            json.dump(m, fh, indent=2, sort_keys=True)
        print(f"  frozen: {m['n_train']:,} train / {m['n_holdout']:,} holdout")
        print(f"  hypothesis: {m['hypothesis']}")
        print(f"  manifest:   {a.manifest}")
        print("  The holdout is now hidden. Explore the train half only.")
        return 0

    with open(a.manifest) as fh:
        m = json.load(fh)

    if a.command == "train":
        train, _ = split_records(records, m["seed"], m["id_field"], m["holdout_ratio"])
        print(f"  train half: {len(train):,} records. Explore freely -- nothing computed "
              f"here is evidence, and no p-value from this half may be reported.")
        out = a.manifest.replace(".json", ".train.json")
        with open(out, "w") as fh:
            json.dump(train, fh)
        print(f"  written to {out}")
        return 0

    v = run_holdout_test(m, records)
    print(render(v))
    if not v.get("refused"):
        m.setdefault("runs", []).append(
            {"at": __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc).isoformat(),
             "passed": v["passed"], "diff": v["stat"]["diff"], "t": v["stat"]["t"]})
        with open(a.manifest, "w") as fh:
            json.dump(m, fh, indent=2, sort_keys=True)
        print("\n  This holdout is now spent. A second run will refuse.")
    return 0 if (v.get("ok") and v.get("passed")) else 1


if __name__ == "__main__":
    sys.exit(main())

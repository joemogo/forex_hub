# MOGO-022 — Does replay predict forward, for MOGO's own implementation?

**Status: derived, read-only. Adjudicates nothing, promotes nothing, changes no strategy.**
**Every number reproduced by `python3 scripts/trader_intelligence/population_fidelity.py`.**

---

## 0. Why this question, and why only now

Preserving the forward closes made one comparison possible for the first time: the
same implementation, `alex_g_sr_v1`, is now observed in **both** evidence
populations — 221 HISTORICAL replay observations and 26 FORWARD paper closes.

None of the 641 hypotheses ask this, because they are all about the human traders
(ALEX_G, TJR, RAYNER_TEO) and no trade evidence exists for any of them. This asks
about the **implementation**, which is the only actor MOGO actually holds evidence
for. That distinction is the one thing this document must not blur.

It matters because replay is the cheap instrument. If replay differs from forward,
every future conclusion drawn from 221 replay observations inherits the difference
— and it needs to be known *before* such a conclusion is drawn.

## 1. The finding

**Replay does not model exit gapping.** Across all 221 replay observations,
realized R takes exactly **two** values:

```
HISTORICAL  n=221   distinct realized R: [-1, 2]
```

Forward books eight, six of which replay never produces:

```
FORWARD     n=26    distinct realized R: [-1.0774, -1.0413, -1.0234, -1.0191, -1, 2, 2.0431, 2.0555]
                    off the replay lattice: [-1.0774, -1.0413, -1.0234, -1.0191, 2.0431, 2.0555]
```

This is a **structural** observation, not a sample statistic. A simulator whose
realized R takes only two exact values is not modelling where the exit fills; it
is asserting it. The claim is established by the values themselves, so no
significance test applies and none is offered.

## 1b. The second finding, which explains the first

**Replay's timing resolution IS the bar grid.** Across all 221 replay observations,
*every* entry and *every* exit falls on an exact hour boundary. Across all 26
forward observations, every entry and exit is sub-second:

| | exact hour | sub-second |
|---|---|---|
| HISTORICAL (442 timestamps) | 442 | 0 |
| FORWARD (52 timestamps) | 0 | 52 |

A simulator that can only act on H1 bar boundaries **cannot represent an intra-bar
fill** — which is precisely the mechanism producing the off-lattice realized R
above. The two findings are one phenomenon seen from two angles.

This does not make replay wrong. A bar-resolution simulator is a legitimate
instrument. What does not follow is any conclusion about **exit timing, MAE/MFE, or
intra-bar behaviour** drawn from replay: those are properties of the grid, not of
the market.

## 1c. Where the two populations AGREE

Reported deliberately, because a tool that only ever emits differences reads as
though something is wrong every time it runs.

**Position sizing is identical.** Risk is exactly **1.0000% of balance-at-entry** in
all 247 observations — 221 replay and 26 forward — with zero spread. Whatever else
differs, the simulator sizes trades the way the live path does.

This doubles as a regression detector: if sizing ever drifts between replay and
forward, `RISK_SIZING_AGREES` flips to a `RISK_SIZING_DIVERGES` finding. A fixture
with 1% against 2% sizing proves it can flip — an agreement that cannot become a
finding is a decoration, not a detector.

## 2. What it does NOT establish — stated because the tempting reading is wrong

**The overshoot runs in both directions.** 4 of 19 forward losses exceed −1R, and
2 of 7 forward wins exceed +2R. Mean overshoot is **−0.0085R on losses** and
**+0.0141R on wins**.

An earlier draft of this analysis said replay "understates what a loss actually
costs." That is one-sided and would have misled: exits gap past their level in
whichever direction price moved, and on this evidence the favourable side is the
slightly larger one. **The net effect on expectancy is not established.**

Also deliberately not concluded from:

- **Win rate.** 86/221 replay (38.9%) against 7/26 forward (26.9%). Different
  instrument mix, different period, n=26, and the forward set is a known-incomplete
  subset of the account's closes (backlog B-22). A difference under those conditions
  is not evidence of a difference in performance.
- **Mean R.** +0.167 replay against −0.195 forward, for the same reasons.
- **Anything about a human trader.** `alex_g_sr_v1` is MOGO's implementation of a
  published method, not the person who published it.

The tool refuses to promote any of these to a finding, and a test pins that
refusal: a fixture with a 9:1 win-rate gap and no gapping difference yields no
finding at all.

## 3. What follows from it

One thing, and it is a caveat rather than a change:

> A realized-R figure taken from replay is an idealisation of where the exit
> actually fills. Quote replay expectancy as a property of the simulator, not as a
> forward estimate.

**No strategy semantics change.** Whether replay *should* model gapping is a
question about the replay engine, not about ALEX's frozen trading rules, and it is
not decided here.

## 4. Coverage and honesty about the sample

| | HISTORICAL | FORWARD |
|---|---|---|
| n | 221 | 26 |
| period | 2026-01-23 → 2026-08-06 | 2026-07-17 → 2026-08-17 |
| unknown fields | 1 per record | 0 |

The forward set is the **preserved subset**, not the account: the oldest closes
minted no evidence package (B-22). Every forward figure above carries that caveat.

## 5. Reproducing

```
python3 scripts/trader_intelligence/population_fidelity.py
python3 scripts/trader_intelligence/population_fidelity.py --json
python3 -m unittest tests.trader_intelligence.test_population_fidelity
```

Read-only; mutates nothing. 31 tests, mutation-verified 20/20 — including both
directions of the tolerance (too tight reports rounding noise as gapping, too loose
swallows real gapping), a positive control that a purely favourable overshoot still
fires, and a fixture where a replay trade ENTERS mid-bar so that dropping `openedAt`
from the granularity computation is caught. That last mutation survived until the
fixture existed, because every real record happens to share one granularity across
both timestamps.

# CRT closes the randomness finding — and two method errors it exposed

**7 September 2026.** `crt_v1` was the arm left out of
`entries-are-indistinguishable-from-random.md` because its 29.9 MB package had not been staged. It is
now included, and the conclusion holds across all four arms. Getting there took two wrong answers
first, and **both of them pointed toward a discovery**, which is why they are recorded here in full
rather than quietly fixed.

## Error 1 — a "+0.37R" control arm that was 659 degenerate trades

The raw figures look startling:

| arm | n | mean realized R |
|---|---|---|
| `crt_swept` | 7,838 | −0.0244 |
| `crt_unswept_control` | 4,882 | **+0.3707** |

A control arm printing +0.37R per trade would be the largest result this project has produced. It is
not real. **CRT places its stop beyond the anchor extreme plus an ATR buffer, and nothing forbids
that distance from being tiny.** `plannedR` reaches 26,040 and `realizedR` reaches 221 — numbers only
possible when the risk denominator is approaching zero.

| arm | stops under 5 pips | mean R of those | mean R of the rest |
|---|---|---|---|
| `crt_swept` | 119 (1.5%) | +0.897 | **−0.039** |
| `crt_unswept_control` | 659 (13.5%) | +2.674 | **+0.011** |

**13.5% of control-arm trades carry the entire mean.** Strip stops under 5 pips and the arm is
+0.011R — zero. Those trades are not tradeable: a sub-5-pip stop is inside the spread on most of
these instruments and would be taken out on entry, if it filled at all. The same defect class was
already known here — it is why `replay_compare.py` has `--band` and reports `tightStopShare`.

## Error 2 — my own benchmark conditioning, biased for variable-target arms

Excluding degenerate stops, CRT still appeared to beat the coin by 5–11 points at z = 5 to 9. That
was **my measurement error, not a finding.**

The benchmark scores each level T only on trades whose target was at least T away, since MFE is
truncated by a trade's own exit. For ALEX, psych_level and baseline_trend the target is a **fixed
2R**, so that filter selects *every* trade and introduces nothing. **CRT's target is the opposite
range extreme, so `plannedR` varies from 0 to 26,040** — and the same filter then selects trades
whose target sits far from their stop. That is a geometry selection, and geometry is exactly what
inflates MFE measured in R.

Matching CRT to the others — target in a 1.8–2.2R band, stops ≥ 5 pips — removes it:

| reach | crt_swept (n=401) | crt_unswept (n=317) | zero-information coin |
|---|---|---|---|
| +0.5R | 63.6% | 64.0% | **66.7%** |
| +1.0R | 50.6% | 52.1% | **50.0%** |
| +1.5R | 41.6% | 46.7% | **40.0%** |

`crt_swept` mean realized **−0.0010R**, z of 0.25 at +1R and 0.67 at +1.5R. **Indistinguishable from
the coin**, like the other three. The control arm's +1.5R row (z = 2.43) does not survive correction
for the levels examined at n = 317.

## The lesson, which generalises

Both errors pushed in the **same direction — toward a discovery**. A degenerate denominator inflates
R, and conditioning on a variable target selects the trades that travel. Neither was visible in a
mean or a t-statistic; both were only caught by asking whether the comparison was between comparable
objects. **Any future arm whose target is not fixed must be geometry-matched before its excursions
are compared to anything.**

## Verdict across all four arms

Support/resistance reaction, sweep-and-reclaim, round numbers, and trend-following — **four
independently derived entry rules, ~19,300 replayed trades, all indistinguishable from random entry
once geometry is matched.**


## Standing

This closes the completeness gap named in `entries-are-indistinguishable-from-random.md`. That
document's caveat — that CRT was not staged — is superseded by this one. Its broader conclusion is
unchanged and now rests on four arms rather than three.

`crt_v1` remains replay-only. **Paper-trading readiness: not assessed.**

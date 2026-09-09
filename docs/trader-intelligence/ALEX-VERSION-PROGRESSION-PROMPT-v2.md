# ALEX version-progression test — prompt v2 (cut build)

> **Status before you start: NOT RECOMMENDED TO RUN.** See "Why this may not be worth
> running" at the bottom. This prompt exists so the decision is Joe's, not the absence
> of a written option. If it is run, run it exactly as written — the cuts below are the
> whole point.

---

## What is being asked

ALEX's rules changed across versions. The question is whether the higher-timeframe bias
filters that were added in later versions actually improve per-trade outcome, or whether
they are decoration that removes trades without improving the ones that remain.

Three variants, pre-registered before any measurement:

| variant | entry rule | bias filter |
|---|---|---|
| **PURE**  | ALEX entry, unfiltered | none |
| **DAILY** | ALEX entry | daily bias must agree |
| **FULL**  | ALEX entry | daily **and** weekly bias must agree |

Every variant is evaluated on the **same captureBasis** and the same instrument set. Do
not mix `LIVE_CLOSE`, `HISTORICAL_BACKFILL` and `REPLAY_RUN` populations.

---

## Hypotheses (pre-registered, fixed before the first number is computed)

- **H1** — DAILY's kept trades beat DAILY's rejected trades by more than 0.06R gross.
- **H2** — FULL's kept trades beat FULL's rejected trades by more than 0.06R gross.
- **H3** — the improvement is monotone: FULL's kept-vs-rejected gap ≥ DAILY's.

**Three tests. Šidák at k=3: α_adj = 1 − 0.95^(1/3) = 0.0170, two-sided t-bar 2.39.**

Nothing else is tested. Nothing else gets a p-value.

---

## Change 1 — the comparison is kept-vs-rejected, NOT variant-vs-variant

**This is the correction that matters most.** A bias filter can only *remove* trades.
FULL's trade set is a strict subset of PURE's. Comparing FULL's mean to PURE's mean
compares a set against a set that contains it — the two share most of their observations,
the difference is driven entirely by the removed trades, and the standard error of that
difference is not the standard error of two independent means. Any t-statistic computed
that way is wrong, and wrong in the optimistic direction.

**Do this instead.** Take the PURE population. For each of DAILY and FULL, split it in two:

- **KEPT** — trades the filter would have allowed through
- **REJECTED** — trades the filter would have blocked

These two halves are disjoint and exhaust the sample. `mean(KEPT) − mean(REJECTED)` is a
real two-sample difference with an honest standard error:

```
SE = sqrt( s_kept² / n_kept  +  s_rejected² / n_rejected )
```

If the filter has value, the trades it throws away are worse than the trades it keeps.
That is the entire claim, and this split is the only clean way to test it.

Report `n_kept` and `n_rejected` for each variant. If either side falls below 300, say so
and treat the result as descriptive only — the split has become too lopsided to resolve
anything.

---

## Change 2 — three pooled numbers, nothing else gets tested

The earlier design tested per-pair × per-timeframe cells: 72 of them, Šidák t-bar 3.38,
smallest cell n=105 with a detection floor of 0.241R. That design could not have found
anything real and would have produced roughly 3.6 false positives at a naive 5%.

**Compute exactly three test statistics** — H1, H2, H3. That is the whole inferential
surface.

---

## Change 3 — dimensional breakdowns are descriptive-only

Per-pair, per-timeframe, per-setup and per-session tables may still be **printed**,
because they are useful for spotting a data fault. They must be printed:

- with **no p-values**
- with **no significance stars, colours or verdict language**
- under a header that reads exactly:
  `DESCRIPTIVE ONLY — NOT TESTED, NOT POWERED, NOT EVIDENCE`
- with each cell's own detection floor shown beside its mean, so the reader can see
  directly that the cell cannot resolve what it appears to show

A cell that looks striking in this table is not a finding and must never be reported as
one. If a cell genuinely looks worth pursuing, it becomes a **new pre-registered
hypothesis on a fresh sample**, not a result from this run.

---

## Change 4 — the pass condition lives in code, not in prose

Every condition below must be an assertion the harness evaluates and reports. A pass
condition stated only in a comment or a markdown paragraph is not a pass condition — this
project has already shipped one verdict that claimed a pass it had not earned, because the
drawdown condition existed only in prose.

A variant passes only if **all** of:

1. `mean(KEPT) − mean(REJECTED) > 0.06` (R, gross)
2. `|t| > 2.39` (Šidák-adjusted, k=3)
3. `abs(net effect) > detection_floor` from `scripts/candidate_power.py`
4. `n_kept >= 300 and n_rejected >= 300`

The harness prints the four booleans. The verdict sentence is generated from the
booleans, never typed by hand.

---

## Required fixtures (write these before the measurement code)

The harness must be able to fail. Prove it can:

- **F1 — tiling.** KEPT ∪ REJECTED = PURE exactly, with no trade in both and none lost.
  Assert on counts, not on a spot check. (The `tod_session_v1` complement bug survived
  every eyeball check and was caught only by a tiling fixture.)
- **F2 — null injection.** Feed a filter that keeps a random 50% of trades. The harness
  must report no effect. If it reports one, the split is leaking.
- **F3 — planted effect.** Feed a filter whose kept trades are constructed to beat
  rejected by exactly 0.10R. The harness must recover 0.10R ± its own SE.
- **F4 — degenerate split.** Feed a filter that keeps everything, and one that keeps
  nothing. Both must return a refusal, not a number.
- **F5 — verdict cannot be typed.** Mutate the pass threshold in the source and confirm
  the printed verdict changes. If the verdict text is hardcoded, this fixture fails.

---

## Provenance line (required in the output header)

The bias-filter concept traces to ALEX's published material. **"Revelio" has no
established provenance in this project** — it appears in source material without an
identifiable primary reference, methodology, or code. Mark every rule that depends on it
`PROVENANCE: UNVERIFIED — name appears in source material, no primary reference located`.
Do not mark it `SOURCE_STATED`; that tier requires a locatable source.

---

## Why this may not be worth running

Read this before spending the 3–4 hours.

**1. The question has already been tested externally, and it failed.** A public 10-year
backtest of a structurally similar smart-money strategy tested an hourly higher-timeframe
bias filter across five assets. One asset improved slightly; four got worse. That is the
signature of noise, not of a filter with value. It is self-reported, has no published code
and no independent verification — `SOURCE_STATED` at best — but it is the only direct
evidence anyone has on this exact question, and it points at null.

**2. Even the pooled headline is barely powered for the decision.** At n≈2,542 the
detection floor is **0.089R**. The standing bar is **0.06R**. So an effect of 0.07R —
real, tradeable, worth having — returns "no effect" from this test. The run can only rule
out a *large* edge. It cannot find the marginal one, which is the only kind still
plausibly on the table after six null arms.

**3. Four arms across ~19,300 trades already landed on 1/(1+T).** ALEX's entries are
among them. A bias filter reorders which of those entries are taken; it does not change
what they are.

**What the same hours would buy instead.** A standing hidden-test-split gate — sample
frozen, split declared, held-out half untouched until the pre-registered test runs once.
The external backtest ran that discipline and reported "almost nothing survived"; the one
survivor was long-only on indices, which is equity drift, not a strategy. That gate is the
single most transferable thing in the source material, it applies to every future
candidate rather than one, and it is roughly the same build cost.

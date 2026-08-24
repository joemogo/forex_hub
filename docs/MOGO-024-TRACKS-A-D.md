# MOGO-024 / Tracks A–D — exit-data integrity and display truth

Four bounded tracks. **No protected function changed; drift 0; no baseline change.**

---

## Track A — ALEX executable-candle integrity (highest priority)

### Root cause

`alexGFetchExecutableCandles` calls `GET /v3/instruments/{pair}/candles?granularity=M1&price=BA&count=5000&from=…`
and paginates forward. It **filtered on `c.complete` and parsed floats, and did nothing else** — no
identity verification, no OHLC validation, no completeness classification. Its three sibling
fetchers (`fetchCandlesDiagnosed`, `fetchCandlesRange`, and ALEX replay via `fetchCandlesRange`)
all run `marketDataIdentityOutcome` **and** `marketDataCandleIntegrity`.

This is the path that decides whether a **real** position hit its stop or its target.

### Actual impact — two measured consequences

**NaN silently disables every exit test.** In `alexGReconstructExitFromCandles` (PROTECTED,
untouched) `hitStop` and `hitTarget` are numeric comparisons; against NaN both are `false`. No exit
is detected — **but `lastProcessedTime` still advances**, so `lastExitCheckTimestamp` moves past
that window and the interval is **never re-examined**. A stop genuinely touched inside it is missed
permanently. This is the same failure mode §18.34 documented for the still-forming bar.

**A wrong-instrument response fabricates a winning exit.** GBP/JPY prices (~199) against a EUR/USD
position with a target near 1.08 make `side.h >= pos.target` fire immediately. The position is
closed as a **Win**, booked to the account, journalled, and preserved as evidence.

Also reachable before this repair: Infinity, zero and negative prices, impossible OHLC
relationships (`h<l`, `h<o`, `l>c`) on either side, duplicate and out-of-order timestamps, and a
**truncated** window — the walk is bounded by `guard<20`, and exhausting it returned a partial
accumulation indistinguishable from a whole one.

### The repair, and why it needed no consumer change

The caller already fails closed on `null`:

```js
if(candles===null){
  // do NOT advance lastExitCheckTimestamp, do NOT fall back to a snapshot; retry the full gap
}
```

So returning `null` on identity/integrity/truncation failure is correct **fail-closed behaviour
with zero change to any consumer**, and `alexGReconstructExitFromCandles` stays byte-identical.
This follows v12.40.0's precedent of leaving a fetch's return contract deliberately unchanged.

Enforced now, all by **reusing the existing shared abstractions**:

| Rule | Mechanism |
|---|---|
| Identity | `marketDataIdentityOutcome(d,pair,'M1')` — refuses **MISMATCH** only |
| Finite, positive OHLC | `marketDataCandleIntegrity` |
| Valid OHLC relationships | `marketDataCandleIntegrity` |
| Ordering / duplicates | `marketDataCandleIntegrity`, on the **accumulated** series so cross-page faults are caught too |
| Completeness | `guard>=20 && cursor<toMs` ⇒ refuse |
| Both executable sides | integrity run on **bid and ask separately** |

**Disclosed residual.** Identity is verifiable only when the response carries the echo. A response
omitting `instrument`/`granularity` is `UNVERIFIABLE`, not a mismatch, and is **accepted** —
refusing it would invent a guarantee the API does not make. Mutation MUT-A5 proves this tolerance
is load-bearing: refusing UNVERIFIABLE kills the entire suite.

### Market closures are NOT missing data

Gaps are **deliberately not an error**. FX closes; M1 bars legitimately do not exist across a
weekend or holiday. Only *ordering* and *per-bar validity* are enforced — never interval presence.
`ALEXEXEC.16` drives a real ~3-day weekend gap and requires both sides to reconstruct, with a
positive control asserting the gap genuinely spans multiple days so the fixture cannot pass
vacuously.

### Historical assessment — no record modified

| Population | n | Classification |
|---|---|---|
| `exitDetectionSource: historical_candle` | **28** | **VERIFIED_WITH_AVAILABLE_EVIDENCE** |
| `live_snapshot` | 8 | VERIFIED — never touched this path |
| replay / backfill (no exit source) | 223 | VERIFIED — `fetchCandlesRange`, full integrity |

All 28 exposed records were coherence-checked **read-only**: every recorded entry/stop/target/exit
sits on its own instrument's price scale, and every exit sits at the level its own outcome names.
A wrong-instrument fabrication would have shown as off-scale; a NaN-corrupted reconstruction would
have produced no exit at all. **0 incoherent, 0 missing fields**, across 12 instruments,
2026-07-13 → 2026-08-19.

**Honest limit:** this establishes that no *detectable* failure mode reached the preserved set. It
cannot prove every underlying candle was pristine — a subtle same-instrument, in-scale corruption
would not be visible this way. No record was rewritten, and none needed to be.

### A latent defect the new check exposed

`ALEXEXEC.3` (stalled cursor) previously asserted only that *an array* came back. On a stall the
page is **concatenated before the stall is detected**, so the returned series contained every
minute **twice** — exactly the corruption `ALEXEXEC.5` exists to prevent. It now refuses, and the
fixture was **strengthened** (termination still asserted, plus a positive control proving a
*non-duplicating* stall still returns its bars, so the refusal is caused by duplication and not by
stalling as such).

---

## Track B — three causes, never collapsed

`loadChart` folds `awaitingScanForTimeframe` into `evaluationSuppressed`, so the banner announced
**"Market data incomplete"** for a pair whose data was entirely **COMPLETE** — while
`renderChartEvaluationState`, inches away, correctly said the opposite. Two panels, one screen,
contradictory causes. *(This was my own regression, introduced in D4 / commit `1ac1f16`.)*

| Cause | Before | After |
|---|---|---|
| Selected timeframe not scanned | "Market data incomplete…" ❌ | "This timeframe has not been scanned yet… **NOT a market-data problem**" |
| Data genuinely incomplete | "Market data incomplete…" | **unchanged** |
| Evaluated, nothing found | "NO SETUP / Evaluated on complete data…" | **unchanged** |

`awaitingScanForTimeframe` was already computed and already passed to `renderChartEvaluationState`;
it is now threaded to the two renderers beside it. The chart state line is untouched.

## Track C — sidebar timeframe attribution

`pairEvaluationDisplayState` gains an **optional** third argument. Callers that omit it
(`renderScan`, `renderWatchlist`) are byte-identical, and a record with no `timeframe` stamp is
never reclassified on a comparison it cannot support.

A score from another timeframe now returns `EVALUATED_ON_OTHER_TIMEFRAME` and is **labelled with
its source timeframe next to the score** — the score is *not* erased, because erasing a real
evaluation would destroy correct information; the requirement is only that it not be attributed to
a timeframe it does not belong to. Pair-level grades and higher-timeframe bias are untouched.

## Track D — alert timeframe attribution (implemented, not deferred)

`sweepTf` was already in scope at the single `addAlert` call site, and `scanPair`, `addAlert` and
`renderAlertLog` are all unprotected — so this was safely additive. Alerts now record `tf`, and it
is **null when unknown, never defaulted to `'M15'`**: labelling an unknown alert with the trading
timeframe is precisely the falsehood the field exists to prevent. Legacy alerts carrying no `tf`
render unchanged.

---

## Verification

| Suite | Before | After |
|---|---|---|
| `v1239_market_data_continuity` | 41 | **51** |
| `v1239_chart_aoi_fidelity` | 69 | **83** |
| `v1239_paper_trading_e2e` | 144 | **150** |

Fixtures were written **failing first**: 7 of the 10 new ALEXEXEC fixtures failed pre-repair, while
all 3 positive controls passed — proving the gap was real and that the repair would not over-block.

### Mutations — all killed

| Mutation | Killed by |
|---|---|
| Identity check removed | ALEXEXEC.8, .9 |
| Bid integrity removed | ALEXEXEC.11, .12, .13 |
| **Ask integrity removed** | ALEXEXEC.12, .13 — proves the ask side is independently necessary |
| Truncation check removed | ALEXEXEC.15 |
| **Over-block: refuse UNVERIFIABLE identity** | 8 fixtures — the tolerance is load-bearing |
| Un-thread `awaitingScanForTimeframe` | TRKB.1, .2, .3, .5, .8 |
| Not-scanned message reworded to blame data | CAF-TF.10, TRKB.1, .2, .5 |
| Sidebar ignores selected timeframe | TRKC.1 |
| **Over-flag: always report other-timeframe** | TRKC.3, .4, .5 |
| Alert `tf` hardcoded to `'M15'` | ALERTTF.2, .3, .4 |
| `scanPair` stops passing `sweepTf` | ALERTTF.1, .2, .3 |

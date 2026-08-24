# MOGO-024 / D4 — "I could not see the market" must not render as "the strategy found nothing"

**Success condition.** No MOGO surface may represent missing, insufficient or unevaluated market
data as a strategy conclusion.

**Status: PARTIALLY MET. Three surfaces repaired and mutation-pinned; six remain collapsed and are
ranked below. This is deliberately not claimed as closed.**

Zero protected-function drift — all 63 protected functions and 4 protected constants are
byte-identical. Every change here is in display/observability code.

---

## 1. What is actually wired, and what only looks wired

Two mechanisms exist. Only one runs.

| Mechanism | States | Production call sites | Gates evaluation? |
|---|---|---|---|
| `marketDataCompletenessOf` / `MARKET_DATA_COMPLETENESS` | COMPLETE / PARTIAL / UNAVAILABLE | 6 (`scanPair`, `evaluateLiveTrigger`, `getStructuralAOI`, `runAutoTopDownScan`, `alexGEvaluatePairForLiveSetups`, `loadChart`) | **yes, fail-closed** |
| `historySufficiency` / `historySufficiencyReport` | SUFFICIENT / REDUCED_WINDOW / INSUFFICIENT / UNKNOWN | **0** | **no — dead code** |

`historySufficiency` (`index.html:7636`) and `historySufficiencyReport` (`7644`) are referenced
**only from inside their own definition block, lines 7626–7657**, and from
`tests/v130_candle_completeness_regression_tests.js`. Verified by exhaustive grep across
`index.html` and `scripts/`. `historySufficiencyReport` has no caller at all.

That matters because of what it was written to say — the string exists, and never reaches a screen:

> `'No AOI determination was possible -- this is NOT evidence that no AOI exists.'`

The real AOI floor is enforced independently, by a literal inside the protected `computeAOI`
(`index.html:7669`): `if(!candles||candles.length<20) return{support:null,resistance:null,band:0};`
`AOI_MIN_USABLE_CANDLES=20` merely mirrors that literal. **A history shortfall is therefore silent
at runtime**, and `computeAOI`'s "could not determine" return is the same shape as its "determined,
found nothing" return.

`computeAOI` is PROTECTED. Distinguishing those two returns at source is a protected change and is
**not** attempted here.

## 2. Repaired

All three sites had the distinguishing fact **already available** and simply were not using it.
`loadChart` computes `evaluationSuppressed` and has always passed it to
`renderChartEvaluationState` — but not to the two renderers next to it.

### D4-a — `renderRecBanner` was wrong in *both* directions

```js
if(!conf||conf.total===0){ label='AWAITING DATA'; detail='No pattern detected on this timeframe'; }
```

`bestConfluence(null,…)` returns `{total:0,items:[]}`, so:

* **data missing** → *"No pattern detected on this timeframe"* — a market finding MOGO never made;
* **data complete, nothing qualified** → *"AWAITING DATA"* — blames a data fault for a legitimate,
  fully-evaluated quiet-market conclusion.

Now `NOT EVALUATED` / *"…This is NOT a finding that no setup exists."* versus `NO SETUP` /
*"Evaluated on complete data — no qualifying pattern on this timeframe."*

### D4-b — `renderConfluencePanel` rendered `No data` for a fully-evaluated 0%

Now states which case it is, in both branches, and still renders no percentage, no LONG and no
SHORT in either — preserving CAF-TF.9.

### D4-c — `buildAiContext` reported an unobserved instrument as a measured `0%`

The worst of the three, because its output is prose the operator may act on. `ld.conf` is truthy
for a suppressed pair and carries no `direction`, so the model was told:

> `EUR/USD (grade A, live confluence 0% undefined)`

An LLM cannot recover the distinction from that string. It now states the data fault positively
rather than emitting a fake figure. **`buildAiContext` had no fixture anywhere in the repository
before this** — which is why this survived every gate.

## 3. Testing

`CAF-TF.14/.15/.16` (chart fidelity) and `D4.1–D4.4` (paper-trading audit), plus `CAF-TF.10`
strengthened from asserting the collapsed string to asserting the explicit not-evaluated label.

`CAF-TF.15` and `D4.4` are **discriminators**: they drive *both* causes through the real code and
require the outputs to differ. A one-sided fixture cannot catch a regression that collapses both
causes onto the same string, which is exactly how the original defect passed 2,528 fixtures.

### Mutations — all killed

| Mutation | Killed by |
|---|---|
| Un-thread `evaluationSuppressed` from `renderRecBanner` | CAF-TF.10, **CAF-TF.15** |
| Make the evaluated-zero case claim a data fault (reverse collapse) | CAF-TF.14, **CAF-TF.15** |
| Un-thread `evaluationSuppressed` from `renderConfluencePanel` | CAF-TF.16 |
| Revert `buildAiContext` to the collapsed string | D4.1, D4.2 |
| Silence confluence for *everything* (over-correction) | **D4.3** (positive control) |

**A defect found in my own fixtures by mutation, and the reason the mutation step is not optional
here:** CAF-TF.14/.15/.16 were first written with the audit suite's 3-argument `assert(name,cond,detail)`,
but the chart suite's signature is `assert(name,desc,cond,detail)`. The *detail string* was
therefore being evaluated as the condition — always truthy. All three reported `PASS … : false`
and were **vacuous**. Only the reverse-collapse mutation exposed it.

## 4. NOT repaired — ranked

| # | Surface | Collapse | Rank |
|---|---|---|---|
| 1 | `computeAOI` / `computeAOIWithTouches` | "could not determine" and "determined, none found" share a return shape — the root cause. **PROTECTED**; needs owner authorization | **P1** |
| 2 | `historySufficiency` / `historySufficiencyReport` | dead code; the "NOT evidence that no AOI exists" sentence reaches nothing. Wiring it usefully requires #1 | **P1** |
| 3 | chart D/W AOI overlay (`loadChart` ~12187) | `getStructuralAOI` returns `incomplete`, and the overlay never destructures it — no band and no message in either case | **P2** |
| 4 | `completenessSuppressed` (`scanData`, written 9867/9883) | **write-only** — no reader anywhere in `index.html`. `bucket='—'` is also what a genuinely-assessed low score gets | **P2** |
| ~~5~~ | ~~`renderScan` / `renderWatchlist`~~ | **REPAIRED — see D4-d below** | — |
| 6 | `setupCount` (10318) / `dashOpportunities` | a total provider outage renders "0 setups", identical to an observed quiet market | **P2** |
| 7 | replay diagnostics (8843–8858) | records the *strategy verdict* "No valid structural AOI" with `observedValue:'none'` when `dSlice` is 1–19 bars — a fabricated rule rejection | **P2** |
| 8 | `evaluateSetupFullBreakdownCore` (7903) | computes `'AOI NOT EVALUATED -- incomplete D/W market data'`; both consumers filter to `MANUAL REVIEW ELIGIBLE`, which requires the AOI gate to have *passed*, so the string has no render path | **P3** |

**Scope note.** `evaluationSuppressed` describes only the M15/`activeTf` scan fetch. The D/W
structural fetch inside `getStructuralAOI` has its own completeness that is never written to
`pairData` — so a pair can render as fully evaluated with its Daily and Weekly history entirely
unavailable, and no surface says so. That is the same defect class as #3 and is the reason #1
cannot be fixed at the display layer alone.

### D4-d — `renderScan` and `renderWatchlist` (added after the first D4 commit)

Both read `pairData` and neither read suppression. A suppressed pair carries
`conf={total:0,items:[]}`, which is below `ALERT_THRESHOLD` and below the watchlist's own `>=40`,
so the Sunday-scan row rendered **a live price beside a blank confluence** and the Active-Watch
card rendered **nothing at all** — in both cases byte-identical to an instrument MOGO observed and
found unremarkable. The Active-Watch list is the surface the operator acts from.

Both now reuse `pairEvaluationDisplayState` — the same pure helper `renderPairList` already uses,
carrying the reason string — rather than re-deriving suppression in two more places.

Fixtures `D4.5–D4.9`, with `D4.8` a positive control and `D4.9` a discriminator across both
surfaces. Mutations killed: reverting the scan marker (D4.5), reverting the watchlist marker
(D4.6), and marking *everything* not-evaluated (D4.8 **and** D4.9).

`D4.8` failed on first write and was correct to: it asserted over the whole `scan-tbody`, where
the other 11 configured pairs legitimately render `NOT EVAL` because they have no `pairData` at
all. The assertion is now scoped to the row under test.

## 5. Trading safety — unchanged by all of the above

No trade can be opened on suppressed data, and that was true before this milestone. The trading
path is gated independently of every display surface listed here: `checkAutoTrades` filters on
`bucket==='Active watch'`, then `evaluateLiveTrigger` applies its own completeness gate
(`index.html:7808`) and returns `{fires:false,reason:'Incomplete market data (M15)'}`.

**The defects in §4 are truth-in-reporting defects, not open trading holes.** They matter because
the operator, and the AI assistant, read those surfaces to decide what to do next.

# Protected-Change Authorization Package — D1 / D2 / D3

**Status: investigation complete, NO protected code modified.** Every number below was produced by an
independent reference calculator built from FX convention, then compared against a transcription of
MOGO's implementation — never by calling the implementation and calling its output correct.

**NO LIVE-MONEY AUTHORITY EXISTS. PAPER SIMULATION ONLY.**

---

## Reference used as the oracle

```
1 standard lot = 100,000 units of the BASE currency
pip size       = 0.01 for JPY-quoted pairs, else 0.0001
pipValue(QUOTE) = pipSize × 100,000
pipValue(USD)   = pipValue(QUOTE) / rate(USD/QUOTE)
```

The divisor depends on **the quote currency only** — never the base. Self-checked against textbook
values before use: `EUR_USD → 10.0000`, `USD_JPY @150 → 6.6667`, `GBP_CHF @0.88 → 11.3636`.

---

# D1 — `pipValuePerLot` conversion-rate substitution

## Status: **CONFIRMED DEFECT** — but materially narrower than first reported

## Current behaviour

```js
const rate=(pairData['USD_'+quote]&&pairData['USD_'+quote].price)||(pairData[pair]&&pairData[pair].price);
if(rate) return (pip*lotUnits)/rate;
return null;
```

The `||` substitutes `rate(BASE/QUOTE)` for `rate(USD/QUOTE)`. Equal only when `BASE === 'USD'`,
where the branch is redundant. It fires **before** the `return null` guard whose own comment says it
exists to stop "risk-sizing on a fabricated number" — so that guard is unreachable whenever the pair
itself has a price.

## Known-answer results (independent reference vs implementation)

$10,000 account, 1 % risk, 50-pip stop.

| pair | pipValue ref | pipValue MOGO | error | lots ref | lots MOGO | exposure error | true risk taken |
|---|---|---|---|---|---|---|---|
| GBP_CHF | 11.3636 | 9.0090 | −20.7 % | 0.1760 | 0.2220 | **+26.1 %** | 1.26 % |
| GBP_JPY | 6.6667 | 5.1282 | −23.1 % | 0.3000 | 0.3900 | **+30.0 %** | 1.30 % |
| EUR_GBP | 12.6582 | 11.6279 | −8.1 % | 0.1580 | 0.1720 | +8.9 % | 1.09 % |
| AUD_NZD | 6.0606 | 9.1743 | +51.4 % | 0.3300 | 0.2180 | **−33.9 %** | 0.66 % |

Direction depends on whether the pair's own rate sits above or below `USD/QUOTE`, so the error is
**market-price dependent**, not a constant.

## The correction that matters most

**The error cancels exactly out of the R-multiple, and out of recorded P&L.**

```
lots = risk/(stopPips·pv)   and   pnl = movePips·pv·lots   ⇒   R = movePips/stopPips
```

`pv` cancels. Verified numerically: the same trade at four different pip values (5.1282, 9.0090,
11.3636, 6.0606) yields **identical** lots-adjusted P&L, identical R, identical balance.

**So D1 does not corrupt R.** My earlier "P1 statistical corruption" characterisation was **wrong**,
and this package corrects it.

**Adversarial review then corrected my correction, and it was right.** The cancellation is exact in
the ideal algebra, but the code quantises the lot size *before* using it:

```js
lots:parseFloat(lots.toFixed(2)),            // index.html:18450
const pnl=movePips*pipVal*pos.lots;          // index.html:18540
```

so `R_recorded = (movePips/stopPips) x round2(lots)/lots`. Measured:

| case | lots raw | lots 2dp | R ideal | R recorded | error |
|---|---|---|---|---|---|
| EUR_USD 50p stop | 0.2000 | 0.20 | 2.00 | 2.00 | 0.00 |
| GBP_CAD 30p stop | 0.4548 | 0.45 | 2.00 | 1.98 | −0.02 |
| GBP_JPY 1040p stop | 0.0149 | 0.01 | 2.00 | **1.34** | **−0.66** |
| GBP_JPY 2500p stop | 0.0062 | 0.01 | 2.00 | **3.23** | **+1.23** |

**This is a SEPARATE defect (D4), not a consequence of D1** — it affects correctly-priced pairs
equally. D1 only determines which side of the rounding a trade lands on. See D4 below.

### The sharpening the review added, and it strengthens D1

When `base === 'USD'`, `convPair` is **literally the same string as `pair`** (`'USD_'+quote === pair`),
and `quote === 'USD'` returns earlier. So the `||` alternative is **either a no-op on the identical
key, or wrong** — it can never produce a correct value it would not otherwise have. The error is
exactly `pipVal_wrong = pipVal_correct / rate(BASE/USD)`.

**MOGO's own self-test is vacuous with respect to this defect.** `index.html:19179-19184` seeds
`EUR_USD`, `USD_JPY`, `USD_CAD` and asserts `pipValuePerLot('GBP_CAD') ≈ 10/1.3650` — the correct
formula — but because it seeds `USD_CAD` and never `GBP_CAD`, the primary branch always wins and the
fallback is never exercised.

What is genuinely wrong is narrower: the **stated position size does not correspond to the stated
risk**. MOGO books exactly $100 every time, but the position actually held would risk 0.66 %–1.30 %
of the account at a real broker.

## Affected / unaffected

- **Unaffected:** every USD-quoted pair (`EUR_USD`, `GBP_USD`, `AUD_USD`, `NZD_USD` …) — early return.
- **Unaffected:** every USD-**based** pair (`USD_JPY`, `USD_CHF`, `USD_CAD` …) — `convPair === pair`,
  so the fallback is arithmetically identical.
- **Transiently affected:** the 9 non-USD-base pairs in `SCAN_PAIRS`, whenever the conversion pair's
  `fetchPrice` returns null on that sweep.
- **Permanently affected (measured):** 6 pairs with no configured conversion pair —
  `EUR_GBP, EUR_AUD, EUR_NZD, GBP_AUD, GBP_NZD, AUD_NZD`. `ALL_PAIRS` has no `USD_GBP`/`USD_AUD`/
  `USD_NZD`, so the fallback is their only branch, always.

## Historical blast radius

| Surface | Classification | Reason |
|---|---|---|
| R-multiples, win rate, expectancy, profit factor | **UNAFFECTED** | `pv` cancels — proven above |
| Recorded USD P&L and balance trajectory | **UNAFFECTED** | internally consistent with intended risk |
| `positionSize` / `units` on trade records | **CONFIRMED_AFFECTED** | wrong by −34 % to +30 % on affected pairs |
| Real-execution fidelity | **CONFIRMED_AFFECTED** | paper exposure ≠ what a broker would have held |
| Backtest / optimizer rankings | **UNAFFECTED** | ranked on R, which is invariant |

**No recomputation of statistics is required.** Only the `positionSize` field is wrong, and it is not
an input to any performance figure.

## Strategy-semantics impact: **A — implementation math only**

The intended semantic ("risk 1 % of equity per trade") is unchanged; the implementation currently
executes it inaccurately. Correcting it makes MOGO execute the *existing* intent accurately.

## Proposed smallest fix (NOT APPLIED)

Delete the fallback operand. `pipValuePerLot` then returns `null` when the conversion rate is
genuinely unavailable, which every caller already handles by blocking the trade — the behaviour the
existing comment claims.

```js
const rate = pairData[convPair] && pairData[convPair].price;
```

**Downstream impact:** the 6 permanently-affected pairs would stop sizing entirely rather than size
wrongly. That is the correct fail-closed outcome, and it makes an existing configuration gap visible
instead of papering over it. Consider adding `USD_GBP`/`USD_AUD`/`USD_NZD` to `ALL_PAIRS` as
conversion-only instruments — a **separate, non-protected** change.

## Recommendation: **AUTHORIZE FIX** — low urgency, high clarity

No statistic needs recomputation, no history is invalid, and the fix is a deletion.

---

# D2 — `pipD` magnitude heuristic

## Status: **CONFIRMED DEFECT**, low reachability

## Current behaviour

`const pipD = last.c < 10 ? 0.0001 : 0.01` at three sites, standing in for the canonical
`pipSize(pair){return pair.includes('JPY')?0.01:0.0001;}`.

It is a proxy for "is this JPY" and fails for **any non-JPY instrument trading above 10**.

## Correct domain behaviour

Convention: pip = 0.0001 for these crosses (quoted to 4–5 decimals); 0.01 applies to JPY quotes only.
`pipSize()` is right and the heuristic is wrong — the heuristic infers the *currency* from the
*price magnitude*, which is not a property of the currency.

## Affected instruments — **my "five instruments at 100x" was wrong**

Adversarial review corrected this and I verified the mechanism. `pipD` is never used raw: it appears
only as `aoiTol = Math.max(aoi.band || 0, pipD*12)`, and `band` already scales with price —
`tolerance = Math.max(range*0.04, currentPrice*0.001)` (`index.html:7610`). That 0.1 %-of-price floor
is 10 pips on EUR/USD but ~180 pips on a price-18 instrument, so **the band absorbs most of the
100x**:

| pair | price | band | tol w/ heuristic | tol w/ `pipSize()` | real inflation |
|---|---|---|---|---|---|
| USD_NOK | 10.6 | 0.020 | 0.120 | 0.020 | **6.0x** |
| USD_ZAR | 18.0 | 0.032 | 0.120 | 0.032 | **3.8x** |
| USD_MXN | 18.5 | 0.036 | 0.120 | 0.036 | **3.3x** |
| USD_TRY | 42.0 | 0.120 | 0.120 | 0.120 | 1.0x — band wins |
| USD_SEK | 9.6 | 0.018 | 0.018 | 0.018 | 1.0x — **heuristic is CORRECT here** |

The threshold is *price < 10*, so `USD_SEK` (~9–11) flips with the market rather than being a fixed
member of the set. **The constant is 100x wrong; the consumed quantity is 1x–6x wrong on three
instruments.** That is still a real defect, and a far smaller one than I reported.

## Reachability — this is why severity is not higher

**None is in `SCAN_PAIRS` (12), and the apparent Manual Review route is dead.** `runManualReviewScan`
filters `ALL_PAIRS`, which looks like a live path to `openPaperPosition` — but its gate is
`sd && sd.bucket === 'Active watch'`, and `scanData` is only ever seeded for `SCAN_PAIRS`
(`index.html:12479`). `runAutoTopDownScan`, the only automatic writer of `Active watch`, also
iterates `SCAN_PAIRS`. So the `ALL_PAIRS` breadth there is **inert**.

The corruption reaches displayed confluence, grade, setup count and alert eligibility — never a
position. `pipD` touches no pip counting, stop, target, R:R or sizing; those all use `pipSize()`.
Manual `placePaperTrade()` on `activePair` is possible, but its entry/stop/target come from operator
input and its sizing uses `pipSize()`, so `pipD` is not in that path either.

## Historical blast radius

| Surface | Classification |
|---|---|
| Auto-traded positions | **UNAFFECTED** — the five cannot auto-trade |
| Displayed confluence / grade / alerts for those five | **CONFIRMED_AFFECTED** |
| Any statistic derived from their trades | **UNAFFECTED** — no such trades exist |

## Strategy-semantics impact

**C — strategy entry/exit semantics, for those five instruments.** Correcting `pipD` changes the AOI
proximity test and therefore which setups qualify. It is a *correction*, but it does change outputs,
so it is not merely implementation math. **Two of the three sites are inside protected functions.**

## Recommendation: **NEEDS GOVERNANCE DECISION**

The right fix is to replace the heuristic with `pipSize(pair)` at all three sites. That requires
threading `pair` into `scoreConfluence`/`detectSignals`, which both already receive. Because it
changes qualification for five instruments, authorize it as a governed protected change — or,
cheaper and fully safe, **remove those five from `ALL_PAIRS`** (non-protected) if they are not wanted,
which eliminates the exposure without touching frozen code.

---

# D3 — trade geometry and unbounded position size

## Status: **CONFIRMED DEFECT — latent, not realised. Highest forward risk of the three.**

## Current behaviour

```js
const riskPips=Math.abs(price-stop)/pip, rewardPips=Math.abs(target-price)/pip;
if(riskPips<=0) return{fires:false,reason:'Invalid stop distance',conf};
const ratio=rewardPips/riskPips;
if(ratio<1.99) return ...
```
then `lots = riskAmount/(riskPips*pipVal)`.

Three compounding facts, all measured:

1. **`Math.abs` discards the sign.** No check that a buy's stop is *below* entry. For a buy,
   `stop = aoi.support − pip*7`; the AOI comes from **daily/weekly** candles filtered against the last
   **closed** bar and cached 15 minutes, while `price` is **live**. When price trades below
   `support−7pip`, the stop sits **above** the entry and `abs()` makes the risk positive again.
2. **The R:R gate admits the dangerous case.** `ratio = reward/risk`, so as risk → 0 the ratio → ∞
   and sails past the 1.99 minimum. The one gate that looks protective is the one that lets it
   through. Measured: at 0.05 pips of risk the ratio is **2000:1**.
3. **No cap of any kind exists.** Grep for `maxLots|MAX_LOTS|maxUnits|notional|marginRequired|
   Math.min(lots` returns **nothing** between the trigger and the committed position.

## Known-answer sizing ($10,000 account, 1 % risk, pipValue 10)

| riskPips | lots | units | leverage | 1-pip adverse move | 5-pip adverse move |
|---|---|---|---|---|---|
| 7.00 | 1.43 | 142,857 | 14× | $14 | $71 |
| 2.00 | 5.00 | 500,000 | 50× | $50 | $250 |
| 0.50 | 20.00 | 2,000,000 | **200×** | $200 (2 %) | $1,000 (10 %) |
| 0.10 | 100.00 | 10,000,000 | **1,000×** | $1,000 (10 %) | $5,000 (50 %) |
| 0.05 | 200.00 | 20,000,000 | **2,000×** | $2,000 (20 %) | **$10,000 — the whole account** |

The position is sized as though the stop were 0.05 pips away, but `closePaperPosition` books the exit
from `fetchBidAsk()` **at market**, so the realised move is at least the spread.

**Review added three findings here, all verified:**

- **`riskPips` is not tick-quantised, so the size is genuinely unbounded.** `clusterLevels` returns a
  **mean** of the clustered swing points, so `aoi.support` is not on the 0.00001 price grid and
  `price − stop` can be arbitrarily small. At `riskPips = 1e-5` the size is 1,000,000 lots.
- **An infinite lot size COMMITS at open and wedges the position permanently.**
  `commitPaperLedger` inspects only `balance` and the 5 most recent *closed* P&Ls; at open, balance
  is unchanged and nothing is closed, so `Infinity` commits ( `(Infinity).toFixed(2)` is
  `'Infinity'`, which survives `parseFloat`). At close the balance goes non-finite, the commit is
  **refused and rolled back** — leaving a position that can never be closed and a ledger in a
  blocking-error state.
- **There is no `balance > 0` guard.** `riskAmount = balance*0.01` goes negative on a blown account
  and produces negative lot sizes with nothing rejecting them.
- **The inverted-stop case closes at a fabricated loss.** `hitStop = live <= pos.stop` is true on the
  first tick, and the close fills at the live bid, not at `pos.stop` — so with a 100-lot position and
  a 1.5-pip spread the realised loss is ~$1,500 against a $100 stated risk: **`resultR = −15.0`**,
  written to the journal as a normal `STOP_LOSS`. That single trade would corrupt the R-distribution
  D1 leaves intact.

MOGO **discloses the absence of limits itself** at `index.html:7952-7953`: *"No maximum-open-trades or
correlated-pair exposure limit exists in code today"* and *"No daily-loss or account-risk circuit
breaker exists in code today."*

## Historical blast radius — **CLEAN, and this is the key result**

Measured across **all 259 preserved observations**:

- smallest risk distance: **5.03 pips**
- largest position: **2.17 lots**
- inverted-geometry records: **0**

**Classification: UNAFFECTED.** No historical record would have been rejected by the proposed
validator, and no remediation or recomputation is required.

But note 5.03 < the 7-pip floor the stop construction implies, so **the sub-7 region is demonstrably
reachable** — the geometry simply has not yet landed in the dangerous part of it. This is the case
for fixing before it does, not evidence that it cannot.

## Strategy-semantics impact: **B — risk-management implementation**

A minimum risk distance and a sign check are **safety floors**, not strategy rules. `MIN_RISK_PIPS`
rejects geometry no broker would fill meaningfully (a stop inside the spread). It must never be tuned
to admit or exclude setups — that would make it a strategy parameter.

Since no historical trade has risk below 5.03 pips, **a 1-pip floor rejects nothing MOGO has ever
done.**

## Proposed fix (BUILT, TESTED, DELIBERATELY NOT WIRED)

`validateTradeGeometry(dir, entry, stop, target, pip, minRiskPips)` — pure, in `index.html`, **not
called by any protected function**. Returns `VALID` / `STOP_WRONG_SIDE` / `RISK_TOO_SMALL` /
`TARGET_WRONG_SIDE` / `NON_FINITE` on **signed** geometry.

The protected change would be a single call added to `evaluateLiveTrigger` and/or
`openPaperPosition`. The logic is already written and covered, so the authorized edit is minimal.

**Tests:** `GEOM-1..8` — long/short valid and invalid geometry, stop equal to entry, near-zero risk at
0.5 and 0.05 pips, the R:R gate demonstrably admitting what geometry refuses, malformed and
non-finite inputs, wrong-side targets, a **positive control** proving normal trades stay valid, and a
fixture asserting the floor sits below every distance the corpus contains.

## Recommendation: **AUTHORIZE FIX — highest priority of the three**

It is the only one of the three that can produce an arbitrarily large position, it rejects nothing in
MOGO's history, and the implementation is already written and tested.

---

# D4 — lot-size quantisation (found by adversarial review)

## Status: **CONFIRMED DEFECT, latent** — JVM only

`openPaperPosition` stores `lots: parseFloat(lots.toFixed(2))` and `closePaperPosition` computes
`pnl = movePips * pipVal * pos.lots`, so the **rounded** size determines P&L and therefore R.

`R_recorded = (movePips/stopPips) × round2(lots)/lots`. The error is negligible at normal sizes and
severe at small ones: a 1040-pip GBP/JPY stop gives `lots = 0.0149 → 0.01`, an R of **1.34 instead of
2.00**. That stop distance is not hypothetical — the v3.3 changelog documents a real observed trade
at entry 208.184 with Daily support ~1040 pips away, attributing it to "the frozen strategy's
uncapped stop distance".

## Historical blast radius — **UNAFFECTED, and here is why**

- **ALEX does not round.** `positionSize = riskAmount/(riskDistancePips*pipValue)`
  (`index.html:4772`, `4243`) — no `toFixed`. All **257** ALEX records are clean.
- **JVM has only 2 records**, at 0.5 and 0.96 lots — quantisation error 1.0 % and 0.5 %.

Measured: 141 of 259 records have a position small enough that 2 dp rounding *could* shift R by >1 %,
and 12 by >5 % — **but every one of them is ALEX**, which does not round. The exposure is real and
has not been realised.

## Strategy-semantics impact: **A — implementation math only**

## Recommendation: **AUTHORIZE FIX** alongside D1 — store the unrounded size and round only for display

---

# Summary

| | D1 | D2 | D3 | D4 |
|---|---|---|---|---|
| Confirmed | yes | **partially** | yes | yes |
| Realised historically | exposure only | no | **no** | **no** |
| R-multiples affected | no (see D4) | no | no | yes, at small sizes |
| Statistics need recomputation | **no** | **no** | **no** | **no** |
| Semantics impact | A (math) | C (qualification) | B (risk floor) | A (math) |
| Magnitude vs first report | as stated | **100x → 1x–6x** | as stated | newly found |
| Forward risk | moderate | low | **high** | moderate |
| Recommendation | AUTHORIZE | GOVERNANCE DECISION | **AUTHORIZE FIRST** | AUTHORIZE with D1 |

**No historical evidence requires quarantine or recomputation.** That is the single most useful
conclusion here, and it was not the expected one.

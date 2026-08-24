# MOGO-024 / D1 — the pip-value conversion boundary

**Success condition.** `pipValuePerLot()` never returns a monetary value it cannot derive from a
real conversion rate.

**Status: MET.** The fabricating term is gone, every execution path blocks on the resulting
`null`, and the change is proven to be the only protected change (§6).

This required an **owner-authorized protected change** — `pipValuePerLot` is one of the 63
protected functions, and one of the two `BASELINE_SHARED_RISK_FUNCTIONS` both engines call.

---

## 1. The defect

```js
const convPair='USD_'+quote;
const rate=(pairData[convPair]&&pairData[convPair].price)||(pairData[pair]&&pairData[pair].price);
```

The second operand is the price of **the instrument being sized**, not the `USD/QUOTE` rate the
conversion requires. GBP/JPY is not USD/JPY.

The `return null` guard immediately below it was written to stop exactly this fabrication. The
`||` fires first, so that guard was unreachable whenever the instrument itself had a price —
which, on a live scanner, is the normal case.

## 2. The universe, partitioned

The 12 configured `SCAN_PAIRS` fall into exactly three classes, and the removed term behaves
differently in each:

| Class | n | Instruments | Effect of the removed term |
|---|---|---|---|
| USD-quoted | 4 | GBP/USD, EUR/USD, AUD/USD, NZD/USD | never reached — early `return pip*lotUnits` |
| USD-base | 3 | USD/JPY, USD/CAD, USD/CHF | **exactly redundant** — `convPair === pair` |
| Non-USD-base cross | 5 | GBP/JPY, EUR/JPY, AUD/JPY, GBP/CHF, GBP/CAD | **always fabrication** |

The USD-base row is what makes the repair a one-term deletion rather than a rewrite: for those
three, `'USD_'+quote === pair`, so the second operand re-read the slot the first operand had
already read. Removing it cannot change their result, and fixtures D1.5.* prove it does not.

## 3. Measured error

Driven against the real, unmodified function with realistic quotes, with the required
`USD/QUOTE` rate withheld:

| Instrument | correct $/pip | fabricated $/pip | error |
|---|---|---|---|
| GBP/JPY | 6.3694 | 5.0153 | **−21.3%** |
| GBP/CHF | 11.2360 | 8.8472 | **−21.3%** |
| GBP/CAD | 7.3529 | 5.7897 | **−21.3%** |
| AUD/JPY | 6.3694 | 9.6506 | **+51.5%** |
| EUR/JPY | 6.3694 | 5.8976 | **−7.4%** |

Direction matters. `lots = riskAmount / (riskPips * pipVal)`, so an **understated** pip value
**oversizes** the position: GBP/JPY's −21.3% is **+27.1% more risk than the account budgeted**,
silently. This was later observed directly — the mutation run in §5 opened a real position at
`pipValueAtEntry: 5.015` against a correct `6.3694`, sized `0.2` lots where `0.157` was correct.

## 4. Reachability — the fallback was not theoretical

`scanPair()` writes `pairData[pair]` **unconditionally** with whatever `fetchPrice()` returned
(`index.html:10210`), and `fetchPrice()` returns `null` on any non-OK status and `undefined` when
the response carries no `prices` field (`index.html:7206`).

So `pairData.USD_JPY.price == null` while `pairData.GBP_JPY.price` holds a real number is an
ordinary production state, produced by either:

* a per-instrument pricing failure on the conversion leg alone, or
* the first sweep's `Promise.all` population race, before every pair has resolved.

## 5. Historical blast radius — LATENT, never realised

The sizing formula is invertible, so the pip value **actually used** by every preserved trade can
be recovered without trusting any recorded field:

```
impliedPipVal = riskAmount / (riskPips * positionSize)
```

Applied to all 259 preserved observations (all 259 usable, none skipped):

* **0 of 115** cross-pair observations match the fabrication hypothesis.
* The three JPY crosses — AUD/JPY, GBP/JPY, EUR/JPY — whose own prices would have produced
  fabricated values spanning **4.58 to 9.05** — instead converge on a single implied band of
  **6.10–6.32**. Three different instruments can only converge like that if all three divided by
  the same real USD/JPY rate.
* GBP/CAD implies USD/CAD ≈ 1.402–1.410; GBP/CHF implies USD/CHF ≈ 0.812–0.819. Both plausible.

**No historical record was rewritten.** The defect is confirmed LATENT: reachable, never reached.

## 6. Protected-change evidence

| Item | Result |
|---|---|
| `pipValuePerLot` at HEAD vs committed baseline | `46d7604…` len 626 — **exact match**, pre-change state pristine |
| `pipValuePerLot` after repair | `0e36662…` len 2361 |
| Other 62 protected functions, HEAD vs working tree | **all byte-identical** |
| 4 protected constants, HEAD vs working tree | **all byte-identical** |
| Drift report before re-baseline | `DRIFT DETECTED in 1 protected item(s): CHANGED: pipValuePerLot` — and nothing else |
| `regression-baseline.json` re-baseline diff | 2 lines, both inside the `pipValuePerLot` entry |

Comments stripped, the entire functional diff is one term removed from one line. The length grows
from 626 to 2361 because the rationale is recorded in the function itself.

## 7. Testing

14 fixtures in `tests/v_paper_trading_audit_tests.js` (D1.1–D1.11 plus three per-instrument
D1.5.* cases), driving the real protected function and the real `openPaperPosition`:

* **D1.1** asserts the universe still partitions 4/3/5 — without it an empty cross set would make
  the fail-closed fixtures pass vacuously.
* **D1.2/D1.3** the normal path matches an independent first-principles oracle for all 12, and is
  not trivially constant.
* **D1.4/D1.5** USD-quoted and USD-base instruments are unaffected.
* **D1.6** the fail-closed boundary — the fixture the restored fallback kills.
* **D1.7/D1.10** positive controls: the same instruments convert correctly once the rate arrives.
* **D1.9** driven end-to-end: `openPaperPosition` refuses GBP/JPY and creates no position.
* **D1.11** the accepted position's `pipValueAtEntry` equals the oracle.

`tests/v130_candle_completeness_regression_tests.js`: `DEFECT-1`, which previously **documented**
this defect, instructed its own replacement — *"If this assertion ever FAILS, the defect was fixed
and this fixture must be replaced by the correct-behaviour assertion."* It is now
`D1 (REPAIRED, was DEFECT-1)`, asserting the inverse. The assertions were inverted, not deleted.

### Mutation results

| Mutation | Killed by |
|---|---|
| Restore `||(pairData[pair]&&pairData[pair].price)` | **D1.6, D1.9** (and v130 `D1 (REPAIRED)`) |
| Force `rate=null` (over-blocking) | **9 fixtures**, including both positive controls D1.7 and D1.10 |

The second mutation initially produced a suite-aborting `TypeError` rather than clean failures;
D1.3 was hardened to be null-tolerant so an over-blocking mutation registers as a failure instead
of hiding which assertion died.

## 8. Disclosed consequence — six instruments now fail closed permanently

`ALL_PAIRS` (35) contains no `USD_GBP`, `USD_AUD` or `USD_NZD`. Six configured instruments
therefore have **no conversion leg at all** and now return `null` unconditionally:

**EUR/GBP, EUR/AUD, EUR/NZD, GBP/AUD, GBP/NZD, AUD/NZD**

* **None of the six is in the 12 traded `SCAN_PAIRS`.** No automated trading path loses an
  instrument.
* Before D1 they were sized on a fabricated value. After D1 they are refused. A blocked trade is
  safe; an invented lot size is not.
* The correct remedy is an **inverse rate** (`USD/GBP = 1 / GBP/USD`), and the inverse leg is
  configured for all six. That is a new conversion capability, deliberately **out of scope** for
  this authorization, and is tracked as **D2**.

Pinned by fixture `D1-CONSEQUENCE (DISCLOSED)`, including a positive control proving the inverse
leg exists — so D2 is a missing conversion with a known remedy, not an unfixable instrument.

# Known Issues & Limitations

This is a list of **documented, intentional** current limitations — scope boundaries and tooling
constraints that are already understood and disclosed, not bugs waiting to be quietly patched
around. If you're about to "fix" one of these, check [ROADMAP.md](ROADMAP.md) first: it may
already be a planned, scoped future release rather than an oversight.

For actual production defects that were found and fixed, see [INCIDENTS.md](INCIDENTS.md)
instead — this file is for things that are working exactly as currently designed.

**Rule for future releases:** update this file whenever a release closes one of these gaps, or
opens a new one that should be disclosed here rather than silently shipped.

## ~~Incomplete candle history is treated as complete~~ — RESOLVED in v12.8.3

**Status:** ✅ **Resolved** by the Market Data Completeness Contract
([ADR-011](adr/ADR-011-market-data-completeness-contract.md)). Retained here as the record of a
verified defect and the reasoning that produced the contract.

`tests/v130_candle_completeness_regression_tests.js` now passes 10/10. `SAFETY-1` … `SAFETY-4`
were written **first** and failed against the pre-fix build; they are the regression guard and
**must not be weakened, inverted, skipped or deleted**.

**One accepted trade-off shipped with the fix:** an instrument whose *genuine* history is shorter
than the requested lookback is classified `PARTIAL` and will not be scanned. MOGO cannot
distinguish a truncated response from an instrument that simply has less history, and the
conservative reading was chosen deliberately. The remedy for a legitimately short-history
instrument is a per-request lookback it can satisfy — **not** a relaxation of the contract.

*The defect as originally found is recorded below.*

**Initial audit hypothesized** that `fetchCandles()` silently paginated and returned truncated
data after HTTP 429. **Test-first investigation disproved that** for `fetchCandles()`: it issues a
single request and returns `null` on any non-OK status, and `null` is rejected by every downstream
guard.

**The mechanism does exist in `fetchCandlesRange()`**, which paginates and `break`s on a
later-page HTTP 429, returning the partial accumulation with no error signal. Its consumers are
the replay/backtest paths, so it does not reach `scanPair()` — but it is directly relevant to
replay trustworthiness.

**The risk on the live scanner path is different in kind.** A *successful* response containing
materially fewer candles than requested is treated as complete, because production validates only
a minimum usable length (`candles.length < 10`), never the requested lookback. `scanPair()`
requests 220 and will score confluence and emit signals from 80.

**Future completeness protections should therefore key on requested-versus-observed history, not
HTTP error handling alone** — while recording only directly observable facts. Requested-minus-received
is *not* a count of missing market candles; legitimate session, weekend, holiday and liquidity gaps
make that subtraction unsound. The observable facts are `requestedCount`, `receivedCount`,
`pagesRequested`, `pagesReceived`, `paginationTerminationReason`, `httpStatus`, `fetchDurationMs`
and `retryCount`.

**Measured behaviour** (real functions, network scripted only at the `fetch()` boundary):

| Path | Requested | Result |
|---|---|---|
| `fetchCandles()` + HTTP 429 | 220 | `null` — 1 request, no accumulation ✅ safe |
| `fetchCandles()` + HTTP 200 carrying 80 complete candles | 220 | 80-length array, no completeness metadata |
| `fetchCandlesRange()`, page 2 HTTP 429 | 220 | 80-length array after 2 pages, HTTP 429 invisible |
| `scanPair()` with an 80-candle response | 220 | `signals=1`, `conf.total=20`, `pairData` records only `[candles, price, signals, conf]` |

~~`v130` is deliberately **excluded** from `FIXTURE_COUNTS` in `regression-baseline-tools.py` until
production satisfies the contract, so its red state is not recorded as an accepted baseline.~~

**Superseded 2026-08-04.** Production now satisfies the contract, `v130` passes **14/14**, and it is
carried in `FIXTURE_COUNTS` as a normal suite. The exclusion was correct while the suite was red and
is obsolete now that it is green.

---

## Pip/tick quantisation is not centralised — IEEE-754 at the one-pip boundary (R1/D3)

**Status:** Found 2026-08-22 during D3. **Contained locally, deliberately NOT generalised.**
Severity **P3**, but flagged as a candidate for a centralised risk/math correction.

A nominal one-pip stop is **not** 1.0 in IEEE-754. Measured:

| entry | stop | computed riskPips |
|---|---|---|
| 1.10000 | 1.09990 | **0.9999999999998899** |
| 195.000 | 194.990 | **0.9999999999990905** |
| 0.86000 | 0.85990 | 0.9999999999998899 |

A bare `riskPips < floor` therefore rejects a **legitimate** one-pip stop by representation error
rather than by the rule. Caught by the pre-existing `PTE2E-BOUND.2` fixture — which exists
precisely as a positive control so its sibling could not pass for the wrong reason — and fixed
with a single `1e-9` epsilon inside `validateTradeGeometry`, four orders of magnitude above the
~1e-13 error.

**Deliberately NOT done: scattering epsilons through the codebase.** The same class of comparison
appears wherever prices are differenced and divided by a pip size, and patching each site
independently is how a codebase acquires a dozen slightly different tolerances.

**The real question, deferred:** should MOGO quantise prices and pip distances to the instrument's
tick grid at a single canonical point, rather than comparing raw IEEE-754 differences at each
site? That is a centralised risk/math correction touching protected arithmetic, and it needs its
own evidence and authorization. **Do not address it piecemeal.**

---

## A finite but excessive position is still permitted — no exposure model exists (D3)

**Status:** Recorded 2026-08-22. **Explicitly out of scope for D3/D3B.** Severity: unresolved
**portfolio/risk-governance** requirement, not an implementation defect.

D3 removed the *unbounded* case: near-zero risk distance can no longer size a position at all.
It did **not** introduce a maximum-lot policy, and none exists anywhere in the codebase — measured:
`maxLots`, `maxUnits`, `notional`, `marginRequired` and any `Math.min` on lot size all return zero
hits in trading code.

At the guard's own floor — EUR/USD, `riskPips = 1.0`, `pipValue 10`, a $10,000 balance —
`lots = 100/(1×10) = 10 lots = 1,000,000 units`, roughly **100× leverage**. That is now the
guard-permitted maximum on a default account.

MOGO **discloses the absence itself** (`index.html:7952-7953`): *"No maximum-open-trades or
correlated-pair exposure limit exists in code today"* and *"No daily-loss or account-risk circuit
breaker exists in code today."*

**Why no cap was invented here.** A maximum lot size is a *risk-governance parameter*, not a safety
floor. Unlike `MIN_RISK_PIPS` — which rejects geometry no broker would fill and sits five times
below the tightest distance in the corpus, so it cannot decide which setups qualify — a lot cap
**would** decide which setups qualify, and picking a number without an account-risk model behind it
would be inventing a strategy rule under the banner of a safety fix.

**What it actually requires:** an evidence-based account-risk/exposure model covering maximum
per-position notional, aggregate open exposure, correlated-pair exposure, and a daily-loss circuit
breaker. That is a governed piece of work with its own authorization, not an increment to D3.

---

## PROTECTED-FUNCTION DEFECTS found in R1 — operator decision required

**Status:** Found and verified 2026-08-22 (R1 §29). **Pinned as documented behaviour, NOT repaired.**
Both live in **protected** functions, so a fix is a governed protected-function change with drift
re-baselining — the same class as the owner-authorized v12.22.0 trade-id change. Severity **P1
(sizing correctness)** and **P2**.

### D1 — `pipValuePerLot` substitutes the wrong conversion rate. **P1.**

```js
const rate=(pairData[convPair]&&pairData[convPair].price)||(pairData[pair]&&pairData[pair].price);
if(rate) return (pip*lotUnits)/rate;
// Returning null forces every caller to block instead of risk-sizing on a fabricated number.
return null;
```

The second operand is **the rate of the pair being sized**, not `USD/quote`. It is correct only when
`base === 'USD'` — where `convPair === pair` and the branch is redundant. **The `||` fires before the
`return null` guard written to prevent exactly this fabrication**, so that guard is unreachable
whenever the pair itself has a price.

**Measured:** sizing `GBP_CHF` with `USD_CHF` absent yields **9.0090** instead of **11.3636** — a
**21 % error** in pip value, hence in lot size and in every realized P&L derived from it.
`openPaperPosition` freezes it as `pipValueAtEntry` and `closePaperPosition` reuses it, so one
momentary pricing failure **on an unrelated instrument** permanently mis-sizes a position and
mis-books its P&L into the journal and every statistic downstream.

Two triggers, one transient and one permanent:

- **Transient** — a single failed `fetchPrice` for `USD_CHF` on one sweep is enough. `SCAN_PAIRS`
  contains nine non-USD-base pairs, so this reaches the auto-traded universe.
- **Structural** — `ALL_PAIRS` contains no `USD_GBP`, `USD_AUD` or `USD_NZD`. **Measured: 6 pairs
  can never resolve a real conversion rate** — `EUR_GBP, EUR_AUD, EUR_NZD, GBP_AUD, GBP_NZD,
  AUD_NZD`. For these the fallback is the *only* branch that ever executes.

The Diagnostics self-test misses it: its three cases are `EUR_USD` (early return), `USD_JPY`
(`convPair === pair`) and `GBP_CAD` (`USD_CAD` seeded). None reaches the fallback.

### D2 — a price-magnitude heuristic stands in for `pipSize`. **P2.**

`const pipD = last.c < 10 ? 0.0001 : 0.01` appears at three sites (two of them inside protected
functions). The canonical function is one line long: `pipSize(pair){return pair.includes('JPY')?0.01:0.0001;}`.

The heuristic is a proxy for "is this JPY" and **fails for every non-JPY instrument trading above
10**. Measured: `USD_MXN, USD_ZAR, USD_TRY, USD_SEK, USD_NOK` are all configured and all get a
**100× pip size**, so `aoiTol = max(band, pipD*12)` is dominated by `0.12` instead of `0.0012`,
`nearSup`/`nearRes` is true essentially always, and the AOI confluence points are awarded
unconditionally — feeding the score, the grade, the setup count and the alert threshold.

### Why neither was repaired here

`pipValuePerLot`, `pipSize`, `scoreConfluence`, `detectSignals` and `openPaperPosition` are all
**protected**. Changing sizing changes lot sizes, which changes outcomes and every statistic derived
from them. That is a frozen-semantics change requiring operator authorization and a re-baselined
drift check.

**Pinned instead** as `DEFECT-1/2/3` in `tests/v130_...js`, asserting what production does **today**
with the measured magnitudes, so a future fix **flips** them and cannot land unnoticed.

---

## ALEX exit monitor kept running after disconnect — REPAIRED (R1)

**Status:** Found and **repaired** 2026-08-22.

`disconnect()` cleared `scanInterval`, `countdownInterval` and `autoScanTimer` but **not
`alexGLiveInterval`** — the timer that monitors and closes open ALEX paper positions.
`stopAlexGLivePollingIfDone()` could not retire it either: its predicate is
`alexGAutoTrading.enabled || openPositions.length > 0`, and `disconnect` changes neither.

So with auto-trading on, or any ALEX position open, the timer survived and kept firing every 60 s
against the credentials cleared on the very next line. Every fetch then 401s — and
`alexGLivePollTick`'s two failure paths (`alexGFetchExecutableCandles` → `null`, `fetchBidAsk` →
`null`) `continue` **silently**, with no engine error and no decision event, while the poll ledger
kept recording `outcome:'OK'`.

**Net effect: an exit monitor that was running, reporting healthy, and monitoring nothing** — with
open positions running past their stops for the whole disconnected window.

Repaired symmetrically with `autoScanTimer`. Safe because `initAll()` restarts it on reconnect.
Regression: `LEAK-1`.

**Related, NOT repaired:** those two silent `null` returns still have no consecutive-failure counter
and no escalation. A pricing outage disables the ALEX exit monitor indefinitely while the ledger
reports OK. Recorded for the next cycle.

---

## AOI runs on a shorter window than it declares, and says nothing (R1)

**Status:** Measured 2026-08-22 (R1 §5). **Reported, deliberately NOT repaired** — the repair would
change frozen strategy behaviour. Severity **P2 (observability)**, escalated to the operator.

### What was measured

The binding constraint on history is **not** any `candles.length < N` guard — it is the **window
size each computation declares**. `findAOIs(candles)` is `computeAOI(candles, 100, 3)`: a 100-bar
window. Every guard in the file sits *below* the window its own function then addresses, which is
exactly why a short window is silent — `slice(-100)` on 59 bars returns 59 and does not fail.

Declared 100 vs actually supplied, on live paths:

| Path | Declares | Fetches | Usable after `c.complete` |
|---|---|---|---|
| `evaluateLiveTrigger` (M15, **the entry timeframe**) | 100 | **60** | ~59 |
| `getStructuralAOI` weekly leg | 100 | **60** | ~59 |
| `runAutoTopDownScan` weekly leg | 100 | **60** | ~59 |
| `getStructuralAOI` daily leg | 100 | 100 | ~99 |
| `scanPair` (active TF) | 100 | 220 | ~219 — genuine surplus |

Also measured, and worth encoding anywhere a contract is written: **`COMPLETE` does not mean "N
candles available".** `marketDataClassify` compares `rawCount >= requestedCount` *before* the
`c.complete` filter, so a healthy fetch of N yields about **N−1 usable**.

### This is NOT an undetected bug — and that correction matters

An initial audit reported it as a "live defect". **It is not.** `computeAOI`'s own comment documents
the tolerance as deliberate:

> *"if fewer candles are actually available … the algorithm should still try with whatever it has
> rather than bailing out entirely. Previously required half of the full window … a razor-thin
> margin that **silently broke weekly AOI detection**."*

The floor is 20, and a shorter supply is intended to still produce a determination. Calling that a
defect would invert a decision made for good reasons.

### What IS wrong

**Nothing reports it.** No surface states that an AOI determination was computed on 59 bars against
a 100-bar declaration. That matters because a reduced window biases toward *finding no AOI* — fewer
swing points reach the `touches>=3` filter — so the failure mode is a **quietly absent AOI**, which
is indistinguishable from a genuine "no qualifying structure here".

R1 §5 forbids exactly this: insufficient history must never silently present as NO AOI / NO SETUP.

### What was done

`historySufficiency()` / `historySufficiencyReport()` classify supply against the declared window as
**SUFFICIENT / REDUCED_WINDOW / INSUFFICIENT / UNKNOWN**, state the shortfall, and carry the
qualifying sentence with the result — *"an absent AOI is weaker evidence than a full window would
give"*, and for INSUFFICIENT, *"this is NOT evidence that no AOI exists."* Pure measurement; no
behaviour changed. Fixtures `HIST-8..13`, including `HIST-12` which pins the floor against
`computeAOI` itself rather than restating the constant.

### What was NOT done, and why it is an operator decision

Raising the M15 and weekly fetches from 60 to 100 would supply the declared window — and **would
change what the engine sees, producing more AOIs and therefore more trades.** That is a frozen
strategy semantic change on a **protected function** (`evaluateLiveTrigger`), and R1 forbids
loosening rules to produce more trades. It also may be the *right* change: the engine currently
asks for less than it declares.

**Operator decision required.** The options are (a) leave supply as-is and rely on the new reporting,
(b) raise the weekly/M15 fetches to 100 as a governed protected-function change with drift
re-baselining, or (c) lower the declared window to match supply. Each changes different things.

---

## Replay/backtest candle path has no integrity validation (MOGO-023)

**Status:** Found 2026-08-22 by adversarial review, **not repaired**. Severity **P2** for research
fidelity; **not** a live-trading exposure.

The MOGO-023 acquisition-boundary checks (OHLC validity, strict timestamp ordering, instrument and
granularity identity) were added to `fetchCandlesDiagnosed()`, which covers the FORWARD path:
`scanPair` → evaluation, plus `evaluateLiveTrigger` and TJR via `fetchCandles`.

**`fetchCandlesRange()` received none of them.** Its only integrity-adjacent guard is
`CURSOR_NOT_ADVANCING`, which by its own comment catches a replayed *page* and cannot see a bar
repeated within one — and says nothing about OHLC validity or instrument identity.

Unguarded consumers: `fetchAlexGReplayDatasets` (W/D/H4/H1), `runBacktest` / `fetchAllPairCandles`
(full sweep + optimizer), `fetchReplayDatasets` (W/D/H4/M15). So a reversed page, an inverted bar or
a wrong-instrument body reaches ALEX-G replay and the backtester classified `COMPLETE`.

**Why it matters even though no live trade is at risk:** MOGO tracks replay-vs-forward fidelity
explicitly, and this change makes the two paths diverge in exactly the dimension that tracking
measures. A replay result and a forward result are no longer validated to the same standard.

`fetchCandlesAroundWindow()` is also unguarded and returns a bare array with no completeness at all
— display-only, lower concern.

**Not repaired in this run** because the forward path was the live exposure and extending the guard
to a paginated accumulator needs its own fixtures (page boundaries, partial accumulation, the
existing cursor guard's interaction). Recorded rather than half-done.

---

## The pair list now names unevaluated pairs; three surfaces still do not (MOGO-023)

**Status:** Partially repaired 2026-08-22. Severity **P3** (was P2 before the row fix).

Repaired: `renderPairList()` now renders an explicit `NOT EVAL` state naming the transport reason,
so a suppressed pair is no longer byte-identical to a quiet market. `ROW-2` is the control proving a
genuine no-setup is still not flagged.

**Still collapsing a data fault into a market verdict:**

1. **Chart AOI overlay** — `getStructuralAOI(...).then(({support,resistance,band,fetchedAt})=>…)`
   drops `incomplete`, so on a D/W outage no purple lines are drawn and nothing says why. Visually
   identical to a pair with no 3-touch structure. (The Manual Review classifier's version of this
   *was* repaired — it now reports `AOI NOT EVALUATED`.)
2. **`instrumentsSkipped` is write-only.** `scanAll()`'s `finally` records
   `NOT_REACHED_THIS_SCAN` / `DISPATCHED_NO_RESULT` / `MARKET_DATA_UNAVAILABLE` /
   `EVALUATION_SUPPRESSED_INCOMPLETE_DATA` into the durable forward-observation ledger, and
   `evidenceSummarizeObservations()` reads only `instrumentsEvaluated`. The two codes that name a
   never-reached pair are reachable only by opening DevTools and reading IndexedDB by hand.
3. **No per-pair evaluation timestamp.** `pairData[pair]` carries no time field, so staleness of the
   last successful per-pair evaluation is not detectable from any screen. `sweepToken` exists but is
   explicitly demoted to diagnostic-only.

**Related, and disclosed rather than fixed:** 23 of the 35 pairs in `ALL_PAIRS` can never trade —
`checkAutoTrades()` iterates `SCAN_PAIRS` (12) and narrows to `Active watch`. Those 23 are also
scored with `score=0, bias='—'` because `scanData` has no entry for them, permanently depressing
their confluence. The sidebar renders all 35 under the heading **"All Pairs"** with nothing marking
tradeability.

---

## Paper P&L models no financing/carry cost at all (MOGO-023)

**Status:** Measured 2026-08-22, **not repaired**. Severity **P3** rising to **P2** for any
multi-day holding period. Affects ALEX and JVM figures that already exist.

`swapRate`, `financingCharge`, `rolloverCost`, `interestRate` and `financing` appear **zero times**
in `index.html` (verified by grep). Every paper P&L is computed as pure price movement:
`movePips × pipVal × lots`. No overnight financing, swap or rollover is applied.

**Consequence.** Realized R on any position held across a rollover is wrong by the unmodelled
financing, in a direction that depends on the pair and the side — systematically favourable for a
positive-carry long, systematically unfavourable for its short. Forward figures inherit this. The
error is small for an intraday hold and compounds with duration; ALEX's forward population contains
holds of many hours to days, so it is not negligible there.

**This is separate from the spread**, which v12.x *does* model — `closePaperPosition()` books the
exit from `fetchBidAsk()`, buys filling at the ask and exits at the bid, so spread cost is
represented. Financing is not.

**Available at zero marginal cost, and not yet taken.** OANDA exposes
`financing.longRate/shortRate` per instrument via `GET /v3/accounts/{id}/instruments` on the
**already-authorized host, with the existing credential, inside the existing CSP allow-list**. No new
provider, no new dependency, no security-boundary change.

Two caveats that make this a decision rather than a task:

1. It is a **current snapshot with no history**, so it cannot retroactively correct any existing
   figure. It can only make future observations correct — which is why the cost of not starting
   compounds daily.
2. It is the **broker's retail financing rate including OANDA's markup**. That makes it the correct
   object for MOGO's own cost model and the *wrong* object for a market-carry signal. Do not reuse it
   for the `MOGO Trend-Structure` §3.8 carry hypothesis; those are different questions.

**Do not** back-fill or estimate financing onto preserved observations. An invented cost is an
invented number, and the records are the evidence.

---

## A 4-millisecond forward observation carries an exactly-2R win (MOGO-023)

**Status:** Measured 2026-08-21, **not repaired**. Diagnosis only — preserved evidence must not be
bulk-rewritten. Severity **P2** (forward-statistic validity).

`TOBS|MOGO|20260806|025` records `openedAt 2026-08-06T13:11:15.571Z` and
`closedAt 2026-08-06T13:11:15.575Z` — a **4-millisecond holding period** — with `outcome Win` and
`rMultiple` exactly `2`. The next-shortest hold in the FORWARD population is 945 seconds, roughly
**236,000× longer**.

That combination is the signature described in **INC-005**: a hand-seeded record with a
zero-duration hold and a clean +2.00R win. INC-005's record was confined to a non-production origin
and never entered the corpus. **This one is in the corpus, is anchored in the identity manifest, and
is classified FORWARD** — the population forward performance is computed from.

Measured impact on the 29-observation FORWARD population:

| | with the record | excluding it |
|---|---|---|
| n | 29 | 28 |
| Σ R | **−5.180** | −7.180 |
| mean R | **−0.1786** | −0.2564 |
| win rate | **27.6 %** | 25.0 % |

A single record of doubtful provenance is **flattering forward performance by 2.0R** — 39 % of the
population's total loss, and 44 % of its mean.

**CORRECTED 2026-08-22 — `current_strategy` is not a placeholder.** An earlier revision of this
entry called it a stray placeholder literal. **That was wrong**, and measurement falsified it:

```js
const JVM_MANIFEST={ id:'current_strategy', family:'jvm', label:'JVM', ...
  capabilities:{ scanning:true, paperTrading:true, automation:true, journal:true } };
```

`current_strategy` is **JVM's canonical registered strategy identifier** — a legacy literal, but a
real registry id. The Journal filter renders it as `<option value="current_strategy">JVM</option>`,
and `buildJVMJournalOpenRecord()` writes `strategy/strategyId: 'current_strategy'`,
`strategyLabel: 'JVM'`, **and `timeframe: null`** on every JVM record.

**One fact explains both "data-quality items" completely.** These are **JVM paper trades**. The
missing `timeframe` is not corruption — JVM's journal builder hardcodes `null`, and the importer
honestly recorded it in `unknowns` rather than inventing one. The `current_strategy` item and the
missing-timeframe item are the **same two records**, and neither is a defect in the importer.

### The consequential correction: JVM's recorded governance status is wrong

`docs/MOGO-022-TO-023-HANDOFF.md` §7 states JVM is *"RESEARCH / STRUCTURAL ONLY… **Evidence
produced: zero observations. Not paper trading.**"* and separately dismisses `current_strategy` as
*"anomaly, not a strategy."*

**Measured: JVM has produced 2 observations, both in the FORWARD population**, minted from
`LIVE_CLOSE` paper trades (`PKG|current_strategy|20260806|1`, `PKG|current_strategy|20260818|1`),
and its own manifest declares `paperTrading: true, automation: true`. Forward statistics that are
described as ALEX's therefore contain **2 JVM trades** — 2 of 29, including the 2R outlier above.

**Severity P2, governance/accuracy.** This is not a code defect: it is a strategy-attribution and
population-purity question. Nothing was rewritten. The open items are (a) whether JVM should be
producing forward evidence at all under current governance, and (b) whether forward statistics must
be segmented by `strategyId` before any figure is quoted. **Both are operator decisions.**

### Provenance traced 2026-08-22 — classified UNVERIFIED FOR AUTHORITATIVE PERFORMANCE

JVM being the strategy does **not** account for a 4 ms hold with an exactly-2R win. The record was
traced as far as the evidence technically allows. **It has not been altered, and must not be.**

Full recovered field set, beside the *other* JVM record for contrast:

| | `TOBS\|MOGO\|20260806\|025` (suspect) | `TOBS\|MOGO\|20260818\|001` (ordinary) |
|---|---|---|
| entry / stop / target | **1.085 / 1.083 / 1.089** | 0.71071 / 0.7096633333333334 / 0.712803333333333 |
| exitPrice | **1.089 — exactly the target** | 0.70954 — *not* the target |
| rMultiple | **exactly 2** | −1.117834 |
| pnl / riskAmount / size | **200 / 100 / 0.5** | −112.32 / 100 / 0.96 |
| holding period | **0.004 s** | 20,627.9 s |
| `exitDetectionSource` | UNKNOWN | UNKNOWN |
| `marketExitAt` | UNKNOWN | UNKNOWN |

The ordinary record carries the residue of real arithmetic — `0.7096633333333334`, `−1.117834`,
`−112.32`. The suspect carries none: every value is a hand-typeable round number.

**The decisive finding is `exitPrice === target`.** `closePaperPosition()` books the exit from
`fetchBidAsk()` — `bid` for a buy, `ask` for a sell — falling back to the live mid, or to `pos.entry`
for a manual close with no price available. **No code path in MOGO sets `exitPrice` to `pos.target`.**
The engine books the market, never the objective. For this record the two are bit-identical.

Supporting facts, each independently weak and jointly conclusive:

1. A buy at 1.0850 reaching 1.0890 is **40 pips in 4 milliseconds** — not a market movement.
2. `pnl` is computed as `movePips × pipVal × lots`, a float product; landing on exactly `200` while
   the sibling lands on `−112.32` is not what that expression does.
3. Risk 0.0020 and reward 0.0040 give exactly 2.000R — a designed ratio, not a measured one.
4. `exitDetectionSource` and `marketExitAt` are UNKNOWN, so **no exit provenance exists at all**.
5. It matches **INC-005**'s documented hand-seeded signature almost exactly — that record was
   `entry 1.10000, stop 1.09500, target 1.11000, exit 1.11000, +2.00R, +$200`, duration 0m. Same
   shape: round prices, exit pinned to target, exactly 2R, exactly +$200, ~zero hold.

**Classification: `UNVERIFIED FOR AUTHORITATIVE PERFORMANCE` (INFERRED, not MEASURED).** The evidence
strongly indicates the record was not produced by MOGO's close path. It does **not** establish who or
what wrote it, and this entry does not claim to. INC-005's forensics were possible because the
storage still held the origin; here the record arrived through import on 2026-08-17, 11 days after
the stated trade, and the pre-import origin is no longer recoverable.

**Consequence for reporting.** Forward figures must distinguish the **RAW PRESERVED POPULATION**
(n=29, ΣR −5.180, mean R −0.1786, win rate 27.6 %) from the **AUTHORITATIVE VERIFIED POPULATION**
(n=28, ΣR −7.180, mean R −0.2564, win rate 25.0 %). The excluded record accounts for **2.0R — 39 % of
the raw population's total loss.** Neither number is quoted without the other, and the record stays
in the corpus.

### The systemic gap this exposes

`index.html` carries `TRADE_INTEGRITY_RULES` (v12.15.0), a rule-based quarantine layer added *because
of INC-005*: a Win must show favourable excursion above zero, a trade must close strictly after it
opened, and so on. **The preserved observation corpus has no equivalent.** The observation schema
carries no MAE/MFE, so the app-side rules cannot even be evaluated against it, and a record whose own
fields are internally impossible enters the authoritative population unchallenged.

**The invariant that is missing:** *a preserved observation whose own fields are mutually impossible
must not enter an authoritative performance population.* Severity **P2**.

**Do not** rewrite, delete or reclassify these records to tidy the counts. The open question is
provenance: what minted a 4 ms trade. Until answered, every forward figure carries this caveat
alongside B-22.

---

## Stop/target detection is suspended while market data is unavailable (INC-006)

**Status:** Disclosed 2026-08-21. Correct fail-closed behaviour; recorded as a fidelity limit.
Severity **P3**.

`checkPaperPositions()` evaluates stops and targets only from a live price, and returns early per
position when there is none (`if(!live)return;`). Through a provider outage that guard holds — which
is right, since inventing a fill price would be far worse.

The consequence is that a stop or target which *would* have been hit **during** an outage is instead
detected at the first price **after** it. Realized R for any position open across an outage window is
therefore measured against a later price than the simulation implies, in an unpredictable direction.

No position, balance or record is corrupted. But an outage window is **not** an observed window, and
forward statistics spanning one should say so.

---

## `regression-baseline.json` is stale — four suites behind `FIXTURE_COUNTS`

**Status:** Disclosed, deliberately not fixed. Found during the MOGO-004 isolation audit, 2026-08-04.

`regression-baseline-tools.py`'s `FIXTURE_COUNTS` dict is the source of truth and is current.
**The committed `regression-baseline.json` snapshot is not**, and has not been regenerated since
v12.5.0:

| | `FIXTURE_COUNTS` (current) | `regression-baseline.json` (committed) |
|---|---|---|
| Suite entries | **34** | 30 |
| Total fixtures | **984** | 759 |
| `appVersion` | — | **absent** |

**Four whole suites are missing from the committed snapshot:** `v127` (ALEX v1.1 release), `v128`
(Evidence Platform), **`v129` (INC-001/INC-004 isolation guards)** and `v130` (ADR-011 candle
completeness). The isolation guard suite being invisible to the committed baseline is the most
notable of these, and is why it is recorded here rather than left to a commit message.

**What is and is not affected.** The **protected-function/constant drift gate is unaffected and
fully current** — it hashes the 63 functions and 4 constants out of `index.html` on every run and
reports zero drift. `tests/run_all.sh` counts fixtures live and reports the real number (944 as of
this entry; the 984 dict total includes the 22 historical scratch-only suites that a fresh clone
cannot run). **Only the committed fixture-count snapshot is stale.**

**Why it has not been fixed here.** Regenerating it means running
`regression-baseline-tools.py --update`, which redefines the committed baseline wholesale — sweeping
in thirteen releases of accumulated change under whatever task happened to notice. This file's own
rule and [TESTING.md](TESTING.md) §3 both say the same thing: *never run `--update` reflexively just
to make the tool pass.* **Rebaselining is a deliberate, separately-reviewed act**, not a side effect
of an audit. Any release that does it must first confirm every suite's count and disclose the
version jump.

---

## Browser-isolation guards cannot intercept ad-hoc tool-layer scripts (INC-004)

**Status:** Accepted limitation, disclosed rather than implied away.

`tests/v129_browser_isolation_guard_tests.js` and
[`scripts/browser_test_profile.sh`](../scripts/browser_test_profile.sh) enforce the mandatory
browser-profile isolation introduced after
[INC-004](INCIDENTS.md#inc-004--real-alex-and-jvm-paper-trading-data-destroyed-by-developer-browser-testing).
They are effective against a **committed** regression: no source file in this repository can
perform a destructive browser-storage call, reference the operator's Chrome profile directory, or
weaken the launcher's fail-closed behaviour without failing the suite.

**What they cannot do:** INC-004 was not caused by anything in this repository. It was caused by
**ad-hoc inline JavaScript issued at the tool layer** — `localStorage.clear()` typed directly into a
live browser tab through automation. No repository fixture can observe or veto that. `run_all.sh`
runs offline JXA suites; it has no visibility into a browser session at all.

**What actually controls this risk:**

1. The Browser Testing Policy's Rule 0 in [TESTING.md](TESTING.md) — procedural, and binding on
   whoever is performing verification.
2. Always launching through `scripts/browser_test_profile.sh`, so the only profile ever exposed is
   disposable and empty.
3. **The only hard technical stop:** removing the browser automation tools from the session's
   permitted-tool configuration (`.claude/settings.json`). That file is operator configuration and
   is deliberately **not** modified by the repository or by any automated change.

This is recorded here because a guard that appears to prevent something it cannot prevent is worse
than no guard — it converts a known risk into an assumed-safe one.

---

## Browser evidence export fails silently — no file, no error (EXP-001)

**Status:** Open defect, disclosed. A supported workaround exists; the underlying failure is unfixed.

During the MOGO-004 Step 1 pilot, an evidence export from a disposable test profile produced **no
file and no error**. The run had in fact succeeded: fifty packages were captured to IndexedDB and
every one of them later hash-verified. But nothing reached disk, nothing surfaced to the operator,
and the run was believed to have produced no artifacts at all for roughly a day.

**The evidence for what happened, rather than a theory about it:** Chrome's `downloads` table for
that profile contained **zero rows**, and the profile's `Preferences` carried no download keys.
The export did not fail partway and it was not interrupted — **no download was ever registered
with the browser**. The precise mechanism is not established, and it is recorded that way rather
than guessed at.

**What is NOT the defect.** The v12.8.0 design is correct and behaved correctly: a package is
marked exported only after the write resolves *and* re-verification passes, so nothing was ever
falsely marked as exported, and the unexported count stayed honest. The gap is narrower and
nastier — **silence was indistinguishable from success.** There was no failure surface at all.

**Workaround, and the current supported path:**
[`scripts/mogo_evidence_receiver.js`](../scripts/mogo_evidence_receiver.js) — see *Evidence egress*
in [TESTING.md](TESTING.md). It writes POSTed bytes verbatim, so it cannot alter evidence, and
`--selftest` proves that byte-for-byte before a run depends on it.

**Consequence while this is open:** the download path must not be relied on for any campaign run.
Combined with `alexGReplayRejected` being memory-only and surviving exactly one replay
(`index.html:4119`), an unnoticed export failure between runs destroys the earlier run's rejection
record permanently — which is exactly what happened to the pilot's first run.

---

## Diagnostics: "Paper trading engine (sizing + auto-close)" self-test failing

Discovered during v12.0.0 (Strategy Framework Foundation, Release 1) live verification, this is
a genuine defect, not an intentional limitation — flagged here rather than silently left
undocumented because it was out of scope for that release to fix. The check (in `runDiagnostics()`,
`index.html`) simulates a JVM paper trade end-to-end against a synthetic account and currently
fails with `Cannot read properties of undefined (reading 'id')`, meaning `placePaperTrade(true)`
did not open a position in the isolated synthetic `paperAccount` the test constructs. Confirmed
**not** caused by the v12.0.0 Strategy Framework work: all 63 `PROTECTED_FUNCTIONS` (including
`openPaperPosition`, `closePaperPosition`, `placePaperTrade`'s dependencies) are byte-identical
to the v11.4.0 baseline, and `paperAccount` was never touched by that release's code changes. The
check's own `finally` block still restores and re-commits the real `paperAccount` regardless of
the simulation's outcome, so this failure does not put real paper-trading data at risk — confirmed
live by a byte-identical `fxhub_paper` before/after. Root cause not yet investigated (a follow-up
investigation task has been queued). See [RELEASE_NOTES.md](RELEASE_NOTES.md#v1200) for context.

## Manual Review Eligible: several gates are disclosed, not enforced

As of v12.1.2, the MANUAL REVIEW ELIGIBLE workflow's eligibility checklist includes 17 items, but
only the ones already enforced somewhere in this codebase are actually gated:
higher-timeframe alignment, structural AOI, confluence, directional confirmation, minimum R:R,
approved session, duplicate-position exclusion, and the weekday preference itself (the one gate
this workflow deliberately overrides). Five items have **no enforced code path anywhere in the
app today** — not in `checkAutoTrades()`, not here: news blackout protection, spread protection,
correlated/pair-exposure limits, a daily-loss or account-risk circuit breaker, and the Friday
cutoff as a hard block (a cutoff *warning* is shown and does gate approval, but there is no
general-purpose hard-block mechanism reused from elsewhere, since none exists). Rather than
silently treating these as passing, `classifySetupEligibility()` populates a
`gatesNotYetEnforced` list that the Review Trade modal displays explicitly. This scope was a
deliberate decision, confirmed with the user before implementation (see the release's scope
assessment) — building real enforcement for these was assessed as materially larger and riskier
scope than this release. See [RELEASE_NOTES.md](RELEASE_NOTES.md) for v12.1.2 context.

## Navigation items with no dedicated page yet

Six top-nav items open a shared, honest "Coming Soon" panel (`comingSoonOpen()`) rather than a
built page. Each states in-app what's planned and where the closest working functionality lives
today:

| Nav item | Closest working functionality today |
|---|---|
| Charts | The full charting experience (including drawing tools) already lives on the Scanner page. |
| Analytics | Trade-level filtering and stats are available on the Journal page. |
| Reports | The same underlying data is fully browsable on the Journal page. |
| Market Outlook | The closest available view is Sunday Scan. |
| Preferences | Available toggles live on the Diagnostics page. |
| Developer | Developer Mode and the Developer Test Tools it reveals already exist on the Diagnostics page. |

(Trade Inspector was on this list through v9.0 and graduated to a real, dedicated page in v10.0
— it is not in this table anymore.)

## MOGO Academy content coverage

As of v11.4.0's School restructure (the original 5 Tracks were renamed to Schools, and a 6th,
Market Intelligence, was added), the Academy has **55** named modules across 6 Schools. **1**
module — Forex Foundations, "How the Forex Market Works" — has the full v11.4.0 premium lesson
treatment (structured content, worked examples, an interactive exercise, a scored knowledge
check with retry/best-score, homework, and personal notes). **2** more (also in Forex
Foundations: *Understanding Currency Pairs*, *Pips, Lots, Spread, and Leverage*) still have their
original v8.0-era legacy content and simple quiz. The remaining **52** are real, titled,
School-assigned, and time-estimated, but honestly display "content coming in a future release"
rather than placeholder/filler text — this is intentional per v11.4.0's own stated goal ("build
the system and one excellent lesson first," not many shallow ones).

One Academy feature remains explicitly not built yet:
- Interactive Trading Drills (spotting AOIs, grading confluence, sizing risk on real historical
  charts) is a named, scoped, not-yet-built feature — opens its own "Coming Soon" panel.

(The Academy Home "study streak" placeholder mentioned in earlier releases was removed in
v11.4.0's Academy Home rewrite — it was never wired to anything and the user's v11.4.0 spec
explicitly called for professional progress indicators over gamification.)

## Strategy Center — ALEX tab

The Strategy Center's Strategy/ALEX tab selector shows a full, built-out Strategy tab for JVM;
the ALEX tab currently shows an honest "Coming Soon" panel rather than an ALEX-specific
methodology writeup.

## Strategy Performance requires a minimum real sample

`computeMogoStrategyPerformance()` (Strategy Center) intentionally shows an "insufficient clean
sample" message rather than a computed win rate/expectancy until there are at least 50 real
(non-test) closed JVM trades. This is a deliberate anti-fabrication design choice, not a bug —
see [ADR-004](adr/ADR-004-read-only-analytics-principle.md).

## Trade Inspector — AI Review

The Trade Inspector's "AI Review" section is a static, clearly-labeled "Coming Soon" card. No AI
call happens on that page. AI-assisted trade grading/coaching was explicitly deferred when the
Trade Inspector foundation shipped (v10.0) and remains unbuilt.

## Offline test harness cannot resolve real async calls

The JXA-based offline fixture harness (`osascript -l JavaScript`) cannot complete a function whose
promise settles on **genuinely pending external I/O**. See [TESTING.md](TESTING.md) for the full
explanation and pattern.

**SCOPE CORRECTED (MOGO-021).** This was previously written as an unqualified permanent constraint,
and was used to defer JVM close-math coverage to a live browser. It does **not** apply when `fetch`
is stubbed to return an already-resolved promise — which every offline suite here already does. In
that case the microtask chain drains and `await` completes. Demonstrated:
`run_v1233_jvm_autotrade_reliability_tests.js` awaits a real `closePaperPosition()` and observes
post-`await` state, proven by mutations after the `await` being killed. **Do not cite this section to
defer coverage without first checking whether the I/O in question is stubbed.**

## Two visual/design passes are scoped but not started

- **v7.3**: a visual/spacing redesign pass on Journal, Paper Trading, and the AI Assistant pages.
- **v7.4**: a design-system pass and full responsive audit.

Neither has been started as of v11.0.1. See [ROADMAP.md](ROADMAP.md).

## No Content Security Policy in production (v12.1.3)

A CSP was built and verified in a scratch/dev copy during the v12.1.3 Security Baseline release
(see [SECURITY.md](SECURITY.md#content-security-policy--built-tested-not-yet-in-production)) but
was deliberately **not** added to production `index.html` — it requires explicit approval and
a live-browser verification pass against the real file first (Charts, Scanner, Replay, exports,
Anthropic connectivity), per the release's own stop-and-approve discipline. Not a silent gap: the
policy, its allow-list rationale, and its `'unsafe-inline'` limitation are fully documented and
ready to ship in a follow-up once approved.

## Anthropic AI key uses a temporary, provider-discouraged direct-browser design

As of v12.1.3's security inspection, the AI Assistant's Anthropic API key is a real, persisted
(client-side, explicit-user-action) provider credential sent directly from the browser using
Anthropic's own `anthropic-dangerous-direct-browser-access` opt-in header — a pattern the provider's
own naming signals is discouraged outside personal/local use, and one MOGO's own error handling
already anticipates being CORS-fragile depending on hosting context. This is disclosed, not a
silent defect: no leakage was found (the key never reaches `innerHTML`, logs, diagnostics, or
exports), but a formal Future AI Security Boundary rule now governs any expansion — see
[SECURITY.md](SECURITY.md#anthropic-api-key--temporary-design-disclosed). The existing AI
Assistant chat feature is frozen as-is; new AI features require a real backend/serverless
endpoint first.

## No real order execution

MOGO never places a real order against any brokerage account — every trade it opens or closes is
a simulated paper position. This is a permanent design boundary, not a gap to be filled — see
[ADR-004](adr/ADR-004-read-only-analytics-principle.md).

## Baseline Registry's JS-side protected-function lists are manually synced, not shared-source

As of v12.4.0 (PROGRAM-001 Phase 1), `BASELINE_JVM_FUNCTIONS`/`BASELINE_ALEX_FUNCTIONS` in
`index.html` are a copy of `regression-baseline-tools.py`'s `PROTECTED_FUNCTIONS` list, generated
programmatically from that file at the time this feature was built (not hand-transcribed), so they
started in exact agreement. There is no shared source between that Python build-time tool and this
browser-side JS, so if a future release adds a name to `PROTECTED_FUNCTIONS`, these two JS arrays
must be updated by hand to match, or the in-app Baseline Registry Diagnostics card will silently
under-cover the real protected set (it will still correctly fingerprint everything it knows about,
it just won't know about the new addition until synced). This is an accepted limitation for this
release, not a defect: the in-app registry is explicitly a lightweight **companion** diagnostic for
Developer Mode, never a replacement for `regression-baseline-tools.py`, which remains the sole
authoritative, build-time drift gate `tests/run_all.sh` actually fails on. Do not expand this into
a shared-source refactor (e.g., generating the JS arrays from the Python file at build time) without
a deliberate, scoped follow-up release — this repository has no build step today, and introducing
one is a significant architectural change of its own.

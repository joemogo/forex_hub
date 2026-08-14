# MOGO-021 — Forward Trading Reliability & End-to-End Pipeline Validation

**Status:** IN PROGRESS · continuation of MOGO-020
**Gates:** canonical 24 suites 1,316/1,316 · platform 1,049/1,049 · ALEX protected drift 0
**Started from:** `c443ed6` (MOGO-020 close-out)
**Paper trading only · live-money NOT AUTHORIZED · TJR paper NOT activated · ALEX frozen**

---

## ⚠️ Handoff-prompt note

The instruction stated *"Read and execute the full MOGO-021 handoff prompt provided immediately
after this message."* **No such message arrived.** This milestone is therefore being executed
against the scope described inline in the kickoff message — market observation, all configured
instruments/timeframes, candle accuracy, strategy evaluation, decisions, paper execution,
persistence, ledger/account state, reconciliation, reporting, independent verification, for ALEX
and JVM. If the full handoff document contains requirements beyond that, it has not been seen and
those requirements are not yet addressed.

---

## 1. Authoritative state reconstructed

| Item | Value |
|---|---|
| Repository / branch | `joemogo/forex_hub` · `main` |
| HEAD at start | `c443ed6a32f819ed4b5510436891842280c68899` · 0/0 with `origin/mogo-main` |
| MOGO-020 close-out commits | `c24b96b` (coverage observability), `c443ed6` (loop-correctness proof) |
| Gates at start | canonical 20 suites **1,180/1,180** · platform **1,049/1,049** · ALEX drift **0** |
| Paper-authorized strategies | **ALEX** (`alex_g_sr_v1`) and **JVM** (`current_strategy`) — both `scanning/paperTrading/automation/journal: true` |
| Not authorized | **TJR** — `status:'development'`, all four capabilities `false`. Untouched. |
| Configured instruments | `SCAN_PAIRS`, **12 pairs**, byte-identical in every commit examined |
| ALEX timeframes | H1 (master clock) · H4 · D · W |
| JVM timeframe | M15 |
| Forward activation cutoff | `2026-08-11T02:43:57.894Z` — unchanged |
| Live campaign | **running** (durable ledger written 1 s before inspection) |

### Authoritative instrument × timeframe coverage (read from the live campaign)

| | ALEX (`alex_g_sr_v1`) | JVM (`current_strategy`) |
|---|---|---|
| Instruments **scanned** | `SCAN_PAIRS` — **12** | `ALL_PAIRS` — **35** |
| Instruments **eligible to auto-trade** | the same **12** | **12** — `checkAutoTrades` filters to `SCAN_PAIRS`, not `ALL_PAIRS` |
| Timeframes evaluated | **H1** (master clock), **H4**, **D**, **W** — confirmed from the live cursor's own sub-keys | **M15** for entry timing, regardless of the displayed chart timeframe |
| Signal-age limit per timeframe | H1 60 · H4 240 · D 1440 · W 10080 minutes (one bar-period each) | none — JVM has no staleness gate |
| Auto-trading state in the live campaign | **enabled** | **enabled** |
| Forward-observation coverage ledger | **yes** | **no** (§2.14) |

The scan/trade asymmetry is worth stating plainly: **JVM scans 35 instruments but can only
auto-trade 12.** The other 23 are scored and charted but are never eligible for an automated entry.
That is the existing design, not a defect, but it means "35 pairs scanned" must never be read as
"35 pairs traded".

### Live-campaign caveat carried forward

The running page loaded its code **before** `c24b96b`. Originally inferred from absence in the
durable store; now **confirmed directly** by reading the live page's own `REASON_CODE_REGISTRY` over
CDP — it contains neither `DATA_INSUFFICIENT_HISTORY` nor `STATE_CURSOR_AHEAD_OF_CLOCK`. **The new
diagnostics are not active in the live campaign.** Activating them needs a page reload, which costs
re-entering broker credentials (MOGO-013) — an operator action, recorded as a blocker rather than
taken unilaterally.

This caveat turned out to be the whole story: §2.10 shows the pre-`c24b96b` durable evidence is
**structurally incapable** of reporting the first pairs in scan order, and that is what produced the
false EUR_USD diagnosis.

---

## 2. Work completed this milestone

### 2.1 JVM auto-trade path — first direct test coverage (`2a22ea5`) — ⚠️ SUPERSEDED

`checkAutoTrades()` — JVM's live auto-entry decision path — had **zero** test coverage, and this
commit added 16 fixtures against it.

> **That suite was subsequently found non-discriminating and has been rebuilt. See §2.5.** Eight of
> its sixteen fixtures could not fail. The entry above is retained only as a record of what was
> committed at the time; do not cite its claims. In particular the original JVM-15 ("JVM emits zero
> decision events") is **imprecise** — `checkAutoTrades` is called from `scanAll`, which does emit
> scan-level events. The accurate statement is that JVM emits no candidate-, rule- or
> rejection-level events of its own (§6.2).

The one claim from this commit that survived verification unchanged is the discarded reason:
`evaluateLiveTrigger` computes `{fires:false, reason:'Confluence below threshold'}` and
`checkAutoTrades` drops it at `if(!result.fires)return;`. That is now asserted properly, including
the discard itself, by **JVM-29**.

### 2.2 The JVM diagnostics gap is governance-blocked

The fix is small — record the reason already computed. But **all four** functions on that path are
in the protected set:

| Function | Protected? |
|---|---|
| `checkAutoTrades` | **PROTECTED** |
| `evaluateLiveTrigger` | **PROTECTED** |
| `openPaperPosition` | **PROTECTED** |
| `getSession` | **PROTECTED** |

Unlike ALEX — whose coverage plumbing (`alexGEvaluatePairForLiveSetups`, `alexGLivePollTick`) is
**not** protected, which is why MOGO-020 could fix it autonomously — **JVM's entire auto-trade
decision path is protected.** Adding diagnostics there breaks drift-0 and requires a governed
protected-function change. Recorded as a blocker; not done unilaterally.

Three further silent drop points in `checkAutoTrades`, all inside protected code:

1. `if(!result.fires)return;` — verdict and reason discarded (16545)
2. `if(pos.error){return;}` — explicitly commented *"skip silently, try again next cycle"* (16550)
3. the eligibility filter (16532-16539) — excluded pairs leave no trace

---

### 2.3 Cursor-sanity detection — a fail-open guard I wrote, and withdrew

`alexGLivePollTick` skips any instrument whose evaluation cursor is not behind the current H1
boundary. A cursor dated *ahead* of the boundary therefore suppresses evaluation. I implemented a
guard that detected this and **auto-repaired it** — clearing the cursor so the instrument resumed
evaluation — and verified it worked: the reproduction went from 0/8 hourly evaluations to 8/8.

**Adversarial verification refuted it, and the refutation was correct.** The only two conditions
that can produce a cursor >2h ahead are future-dated candle timestamps or a local clock running
more than two hours slow. In *both* cases the app's time reference is untrustworthy — and both of
ALEX's time-based trade gates read that same reference:

| Gate | Code | Behaviour under the fault |
|---|---|---|
| `alexGIsSetupEligibleForLiveTrading` | `setup.qualificationTimestamp>=alexGAutoTrading.activatedAt` (`index.html:4520`) | a future-dated qualification **always passes** |
| `alexGIsSetupSignalStale` | `(nowMs-setup.qualificationTimestamp)/60000>maxAge` (`index.html:4532`) | age is negative → **never stale** |

So the guard's remedy for "this instrument's timestamps cannot be trusted" was "resume trading it",
at the exact moment the two gates that would catch a bad-timestamp setup both degenerate to
always-pass. Before the change the instrument was starved and opened nothing; after it, it could
open a trade on corrupt data. **That is a trade that would not otherwise happen.** It also
contradicted the in-repo precedent: the other data-integrity guard in the same function (short H1
dataset, `index.html:4562`) responds record-and-`return` — skip the instrument.

A second defect: after `delete`, the pair moved out of `__obsSkipped` into `__obsEvaluated`, so the
**durable** `instrumentsSkipped` diagnostic — the operator-visible detector this milestone exists
to build — stopped reporting the faulted instrument entirely. The guard destroyed the evidence of
the fault it detected, leaving only a 500-entry in-memory ring that a page reload erases.

**The auto-repair was withdrawn.** The shipped version is detection-only and fail-closed: the
condition is recorded on the decision bus (latched once per `pair|cursor`, so a persistent fault
cannot flood the ring) and, durably, as `cursorAheadOfClock` on the skip record itself — so the
ledger distinguishes "no new bar yet" from "this cursor is impossible". The cursor is **not**
repaired; the instrument stays out of live evaluation until an operator resolves the source.

### 2.4 Correction: the starvation was never permanent

I described this failure as starving an instrument "for the rest of the campaign", "with no path
back". **That was wrong**, and the fixture that appeared to prove it was arithmetic, not evidence:
STARVE-1 injected a cursor 72 hours ahead and then observed only 8 hours, so `seen===0` was
guaranteed before any application code ran. The cursor only advances when the pair is evaluated;
while skipped it is frozen while the wall clock advances, so **starvation is self-limiting**,
bounded by `(cursor − now)`. To explain the observed ~56-hour EUR_USD loss this way the cursor
would have had to be dated ≥56h ahead, and **no mechanism producing that has been identified**.

`fetchCandlesRange` filters to `c.complete` (so forming candles are excluded) and `getCandleCloseTime`
puts the last H1 candle's close exactly *on* the boundary (fixture LOOP-3: 12/12 cursors land on
the boundary). What ships here is detection that will identify a cursor anomaly durably if one ever
occurs — not a fix, and it is not claimed as one.

> **Since superseded: the root cause IS now established, and it is not starvation of any kind.**
> See **§2.10**. Live production state shows EUR_USD's cursor healthy and 30 setups qualifying per
> cycle. The cursor-sanity detector remains worth keeping as a genuine data-integrity guard, but it
> is no longer connected to the EUR_USD question.

### 2.5 JVM suite rebuilt — the first version could not fail

The 16-fixture JVM suite committed in `2a22ea5` was found non-discriminating under adversarial
verification, and the finding was correct. Because the fixture used a flat, structureless M15
series, **nothing ever fired** — so every exclusion fixture asserted `openPositions.length===0` in
a world where that count was zero regardless. Verified vacuities:

* **JVM-7/12/13/14** (disabled gate, open-position, traded-today, not-Active-watch) would have
  passed identically **if the exclusion logic were deleted outright**.
* **JVM-15** filtered `decisionEventLog` on `e.source` matching `checkAutoTrades|evaluateLiveTrigger`.
  I confirmed independently that the only `source` values any emit site produces are `scanAll` and
  `alexGLivePollTick` — the filter could never match, so the fixture returned 0 regardless of
  behaviour.
* **JVM-8** asserted `typeof pos.error==="string" || pos.id!=null` — true either way — and its
  `else` branch recorded JVM-9/10/11 as literal `true`. Four fixtures unconditionally green.

My own suite header had argued *against* building a positive control, on the grounds that
"engineering a synthetic confluence would prove only that the fixture can be tuned". That argument
produced a suite that proved nothing. **An exclusion test is only meaningful against a baseline
that would otherwise fire.**

The suite is rebuilt to 27 fixtures around a positive control, under a strict rule: **the candles
are constructed; the verdict is not.** No threshold, weight or rule is altered, overridden or
stubbed. The series is an ordinary bullish setup — 3/3 bias, a standard engulfing bar that also
breaks structure, a priority session, a daily support shelf with resistance far above — and the
frozen scorer rates it **65 against its own threshold of 55** (bias 25 + engulf 20 + session 10 +
MSB 10; AOI and wick both score **zero**), returning **R:R 3.51:1** of its own accord.
`checkAutoTrades` then opens **4 positions**. Every exclusion is re-asserted against that baseline
and now discriminates:

| Fixture | Result | Contrast |
|---|---|---|
| JVM-17 auto-trading disabled | 0 opened | vs baseline 4 |
| JVM-18 not in Active watch | 0 opened | vs baseline 4 |
| JVM-19 already traded today | **3 opened** | that pair blocked, the others still fire |
| JVM-20 existing open position | 1 position on that pair | no duplicate |
| JVM-21 inactive session | 0 opened | session `Off-hours` |
| JVM-22 outside Mon-Wed | 0 opened | reason states the window |

**Scope of the claim:** this proves the auto-entry path fires end-to-end and that each exclusion
suppresses a trade that would otherwise open. It proves **nothing** about profitability,
calibration, or how often real markets produce this setup. No live-money path is touched; TJR
paper trading remains unauthorized and untouched.

### 2.6 A silent drop point — real mechanism, and a rate that is *not* a production rate

**This section previously stated the wrong cause and an arithmetically wrong breakdown.** Both were
caught in verification and are corrected here.

Calling `checkAutoTrades()` directly, 8 of 12 pairs opened nothing:

| Pairs | Why | Real in production? |
|---|---|---|
| USD_JPY, GBP_JPY, AUD_JPY, EUR_JPY (**4**) | the strategy declined: `R:R only 0.23:1` | **no** — the stub prices JPY pairs at 1.10 while `pipSize` uses 0.01, inflating risk 100× |
| GBP_CHF, GBP_CAD, USD_CAD, USD_CHF (**4**) | signal **fired**, `openPaperPosition` rejected it for want of a conversion rate | **no** — see below |

*(My earlier text said "2 JPY + 3 conversion", which is both wrong and doesn't sum to 8; GBP_CAD was
missing entirely.)*

**The cause was misattributed.** I blamed the `/pricing` stub serving one quote for every
instrument. That stub feeds `fetchBidAsk` (the entry price), not the conversion lookup. The real
cause is that `pipValuePerLot` needs `pairData['USD_'+quote].price`, and `pairData` is populated
only by `scanPair()` — which a direct `checkAutoTrades()` call never runs.

**And it does not happen in a real sweep.** `scanAll()` populates `pairData` for every pair
*before* calling `checkAutoTrades`, and every conversion pair needed (`USD_JPY`, `USD_CHF`,
`USD_CAD`) is itself in `SCAN_PAIRS`. Fixture **JVM-25** now runs the real entry point and records
the contrast directly: **8 positions open via `scanAll()` versus 4 via a direct call.** The
remaining 4 are the JPY pairs, declined by the strategy's own R:R gate (JVM-26).

So: **the drop mechanism is real production code** — `pipValuePerLot` returns `null`,
`openPaperPosition` returns an error, and `checkAutoTrades` discards it at
`if(pos.error){return;}` with no journal entry, no `tradedToday` mark and no decision event
(JVM-23/24). **The 8-of-12 rate is not.** All eight drops in the direct-call fixture are artifacts
of one kind or the other, and the suite now says so in its own fixture text rather than presenting
them as a production finding.

### 2.7 Candle accuracy and timeframe alignment — first coverage (27 fixtures)

The four functions that decide when a candle actually *closes* had **zero** direct coverage:
`getNYOffsetMinutes`, `nyAlignedClose`, `getCandleCloseTime`, `precomputeCloseTimes`. Everything
downstream depends on them — the H1 master clock gating ALEX's live poll, the replay two-pointer
walk, and the evaluation cursor itself. They are pure functions, so the suite needs no seams at
all: no network, no clock stubbing.

Established, against real IANA transition dates and the runtime's own timezone database:

* **DST is genuinely honoured, to the minute** — UTC−5 in January, UTC−4 in July, and both 2026
  transitions (8 Mar 07:00Z, 1 Nov 06:00Z) flip exactly at the boundary. The offset is not
  hard-coded anywhere.
* **17:00 New York is 22:00Z in winter and 21:00Z in summer** — daily/weekly closes track the NY
  wall clock rather than drifting an hour twice a year — and alignment uses the **New York**
  calendar date, not the UTC one (02:00Z on the 16th correctly aligns to the 15th's session).
* **Only the last candle is estimated.** Every other candle's close is read exactly from the next
  candle's start — no duration math, no timezone guessing. The last-candle fallback is per
  granularity (H1 +1h, H4 +4h, M15 +15m, D/W to 17:00 NY).
* **ALIGN-11/12 test the property the cursor work depends on**: an H1 close lands exactly on a UTC
  hour boundary, and never ahead of the boundary current at any instant the series can exist. That
  claim had been asserted in commit messages but never tested.

One fixture (ALIGN-12) initially failed and the **fixture was wrong, not the code**: I had compared
the close against a "now" equal to the last candle's *start*, but a candle starting at 09:00 is
only complete once 10:00 has passed, so that instant was never reachable. Corrected to assert the
real invariant.

### 2.8 Reconciliation — a ledger-mutating path documented as tested, with no tests (24 fixtures)

`applyPaperReconciliation()` is the one function in the JVM paper ledger that restores a trade and
**moves the balance** outside the normal open/close lifecycle. The v11.0 release note states that
fixtures cover it — naming "applying a reconciliation restores exactly once, updates balance
exactly once, and is audited", "the same tradeId can never be reconciled twice", and "an incomplete
journal record is skipped rather than reconstructed".

**No such fixtures exist.** `applyPaperReconciliation` and `computeReconciliationPreview` are
referenced by **no file in the repository**, and by no test file in **any commit** reachable from
the current history (checked across the 300 most recent). The *reporting* side
(`computePaperLedgerIntegrity`, `ledgerReconcileBalance`, `ledgerBuildReconciliationReport`) is
covered; the *mutating* side never was. The release note overstates coverage that does not exist.

24 fixtures now test exactly the guarantees the note claims, and they hold:

| Guarantee | Result |
|---|---|
| Preview mutates nothing — account and audit byte-identical | holds |
| Balance moves by the **stored** pnl, never recalculated from prices | holds (10000 → 10200) |
| Restored trade tagged `source:'reconciled'`, distinguishable from a real fill | holds |
| Audited with action, pnl applied, and before/after balance | holds |
| A record missing required fields is skipped with a reason, never reconstructed | holds |
| A tradeId that is not a proven orphan yields nothing — arbitrary trades cannot be injected | holds |
| A failed commit **rolls back** account *and* audit, leaving the trade visibly orphaned | holds |
| After a successful restore the ledger reconciles to a $0.00 difference | holds |

The rollback case is driven through the **real** optimistic-concurrency guard (by advancing the
persisted version so `savePaperAccountGuarded` returns `STALE_VERSION`), not by stubbing the save.

**A finding on the double-credit protection.** It has two layers, and they fire in different
situations — which the release note's single claim obscures. The *primary* defence is that a
restored trade is no longer an unexplained orphan, so it is never a candidate again; the
`alreadyReconciled` audit check is **unreachable in the normal flow**. That audit check is the
*secondary* defence, and it matters precisely in the scenario this tool exists for: if the restored
position is lost from the account *again*, the trade becomes an orphan once more and only the audit
trail prevents a second credit. Both layers are now tested separately (RECON-14, 14b, 14c).

Nothing real was persisted: `localStorage` is an in-memory stub, the ledger is fixture data, and no
paper trade was opened or closed through the live engine.

**The gap was isolated, not systemic.** I swept every other state-mutating ledger and trading
entry point — `openPaperPosition`, `closePaperPosition`, `checkAutoTrades`, both reset paths,
`savePaperAccountGuarded`, `saveAlexGAccountGuarded`, `commitPaperLedger`,
`alexGConstructLivePosition`, `alexGAttemptOpenLivePosition`, `alexGCheckLivePositions`,
`deleteEntry` — and every one is referenced by existing fixtures. `applyPaperReconciliation` was
the only mutating path with none.

### 2.9 Timeliness and latency — how the system actually enforces it (read-only finding)

MOGO-021 lists timeliness/latency. Mapping what exists, before proposing anything:

| Mechanism | What it measures | Is it a decision input? |
|---|---|---|
| `alexGIsSetupSignalStale` | signal **age** vs one bar-period per timeframe (`H1:60, H4:240, D:1440, W:10080` min) | **yes** — rejects stale setups |
| `maxLiveEntryDelayPips` (rule `ALEX_X_002`) | **price distance** between the historical qualification close and the live fill | **yes** — rejects chased entries |
| `fetchDurationMs` | wall-clock fetch latency | **no, deliberately** — ADR-011 records it as a forensic diagnostic and explicitly forbids any consumer making an evaluation decision from it |
| poll `startedAt` / `finishedAt` | per-tick wall-clock duration | no — durable observation only |

So timeliness is enforced on **signal age and price displacement**, not on wall-clock latency, and
that is an intentional contract rather than an omission — ADR-011 notes that branching on transport
diagnostics is exactly what re-creates the defect it was written to close. The rule origin is also
disclosed honestly in the codebase: `ALEX_X_002` is marked `origin:'MOGO Operationalization'` with
`evidence:'source never addresses live execution latency'` — i.e. it is a MOGO-added operational
gate, not a frozen strategy rule. **No change proposed**; recorded so the milestone does not later
mistake a deliberate contract for a gap.

### 2.10 EUR_USD ROOT CAUSE — ESTABLISHED. It was never starved.

**Conclusion: the "EUR_USD starvation" never existed. The original observation was a measurement
artifact of a truncated in-memory ring, and I built two successive wrong theories on top of it.**

#### How the evidence was obtained, safely

The evaluation cursor is memory-only and never persisted, so no amount of disk forensics could ever
reveal it — which is why four prior investigations stalled. The running campaign's Chrome was
started with `--remote-debugging-port=9222`, so the live in-memory state is readable over CDP
**without a reload, without credentials, and without touching campaign state**. All reads went
through a helper that refuses any expression containing an assignment, a mutating call, or a
navigation (`scratchpad/cdp_read.js`); only pure expressions were evaluated. The campaign was
confirmed live (durable store written seconds before each read).

#### What the live campaign actually shows

| Observation | Value |
|---|---|
| Cursors, all 12 pairs | **identical**, `H1 = 2026-08-14T01:00:00Z` = **exactly the current H1 boundary** |
| Hours behind boundary | **0** — the healthy state, confirming fixture LOOP-3 in production |
| `alexGSetupState` | 383 setups; **EUR_USD = 30**, mid-pack of 12 (GBP_CHF highest at 54) |
| `alexGLiveSetupStatuses` | exactly **300** — at cap |
| Statuses for EUR_USD / GBP_USD | **0 / 0**; GBP_JPY 4 of its 26 |
| `alexGEngineErrors` | 0 |
| Running build | **pre-`c24b96b`** — neither new reason code exists in its registry |

EUR_USD's cursor is healthy and it qualifies 30 setups per cycle. **It is being evaluated normally,
identically to the other eleven.** The cursor is *behind or on* the boundary, never ahead — so the
entire cursor-ahead theory is refuted in production, not merely doubted.

#### The actual mechanism

`alexGRecordLiveSetupStatus` (**PROTECTED**, `index.html:4282`):

```js
if(alexGLiveSetupStatuses.some(e=>e.signalId===entry.signalId)) return;
alexGLiveSetupStatuses.unshift(entry);                 // newest to the FRONT
if(alexGLiveSetupStatuses.length>300) alexGLiveSetupStatuses.length=300;   // truncate the TAIL
```

Newest goes to the front; truncation drops the **tail**, i.e. the **oldest**. Pairs are evaluated in
`SCAN_PAIRS` order, so the pairs evaluated *first* sit nearest the tail and are evicted *first*.
One cycle produces 383 setups against a 300 cap.

The arithmetic works out as `383 − 300 = 83 = 31 (GBP_USD) + 30 (EUR_USD) + 22 (GBP_JPY partial)`.

**I originally presented that as the proof. It is not — verification showed it is tautological.**
Given "the ring is the last 300 of one 383-entry pass", the missing 83 *must* be the first 83 in
scan order; it cannot come out any other way, so it restates the model rather than testing it.

The genuinely discriminating evidence is the ring's **block structure**, which I checked as a
prediction before looking: the pairs appear in **exactly reverse `SCAN_PAIRS` order**, each pair
contiguous, no interleaving, with only the tail block cut mid-pair —

> `USD_CHF, USD_CAD, EUR_JPY, AUD_JPY, NZD_USD, GBP_CAD, GBP_CHF, USD_JPY, AUD_USD, GBP_JPY`

— and head/tail timestamps spanning **20.2 seconds of a single scan**. No alternative partition
survives that. Two competing hypotheses were tested and rejected: a mid-scan abort would favour
*early* pairs, not late ones; a per-pair error would leave `failures` or `outcome ≠ OK` entries, and
the ledger contains **zero** error polls.

And `alexGLivePollTick` records that same array verbatim into the durable ledger
(`statuses:` at `index.html:5125`). **So the `statuses` evidence structurally cannot contain
GBP/USD or EUR/USD** — the two pairs at the front of scan order.

#### Correction: this explains "zero evaluations", but NOT "zero poll appearances"

I initially folded the whole original claim into this one artifact. That was wrong, and it hid a
**third, separate error**. Truncation cannot touch `instrumentsEvaluated` — that field is built
from the poll loop (`__obsEvaluated.push(oPair)`), not from the ring, and **the pre-`c24b96b`
running build already persisted it**. Read directly from the durable ledger across 67 advancing
polls:

| GBP_USD | EUR_USD | GBP_JPY | AUD_USD | USD_JPY | GBP_CHF | GBP_CAD | NZD_USD | AUD_JPY | EUR_JPY | USD_CAD | USD_CHF |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 61 | **61** | 61 | 61 | 61 | 62 | 61 | 62 | 62 | 63 | 64 | 67 |

**EUR_USD is 61/67, identical to GBP_USD and in line with every peer.** The MOGO-020 claim of an
asymmetry between them — "EUR_USD zero poll appearances, GBP_USD ~one per H1 boundary" — has no
basis in the data. It was a reading error, and the evidence to refute it was present in the ledger
the whole time. The suite header that asserted it has been retracted in place.

Reproduced offline as regression protection (**BIAS-1..5**, `run_v1232`): 384 statuses recorded in
scan order overflow the ring to exactly 300, and the pairs it evicts are `GBP_USD, EUR_USD` —
precisely the two the original audit flagged.

#### It is already remediated in committed code

`instrumentsEvaluated` / `instrumentsConfigured` / `instrumentsSkipped` (added in `c24b96b`) are
built from the **poll loop itself**, not from the status ring, so they are immune to this
truncation. **BIAS-4/5** assert exactly that: 12/12 instruments named in the durable coverage
record even while the ring has evicted the first two. The running campaign predates that commit,
which is why the data I originally analysed was blind.

#### The remaining consequence is trading-relevant and governance-blocked

The duplicate guard at `index.html:4641` is documented *"PERMANENT, never reconsidered"* but reads
that **same truncated ring**. For the evicted pairs the short-circuit cannot fire, so their setups
are re-evaluated on every poll rather than being decided once.

A duplicate **trade** is still prevented: `alexGConstructLivePosition` (`index.html:4302`) checks
`alexGAutoTrading.tradedSignals` (persisted, unbounded) plus open/closed positions and journal
entries. The real deviation is narrower: a setup blocked for a **transient** reason can be retried
on a later poll, contrary to the documented finality — bounded by the staleness gate, since
`signalAgeMinutesAtEvaluation` is measured from `qualificationTimestamp` and grows with the clock
(one bar-period: H1 60 min).

#### The consequence is larger than I first reported: the dedup is void for ALL twelve pairs

I framed this as affecting only the evicted pairs. Verification showed that is wrong, and the
correct version is a **strategy-fidelity defect**, not an observability one.

A pair's own entries survive to its *next* turn only if `(totalSetups − thatPairsSetups) < 300`.
The most-favoured instrument is GBP_CHF at 54 setups: `383 − 54 = 329 > 300`. **No pair clears the
bar.** Measured independently in the durable ledger: **377 distinct signalIds against 17,700
evaluation records — ~47 re-decisions per signal.** Even USD_CHF, evaluated last and sitting at the
ring head, shows ~61 — one per advancing poll. Offline, **REDEC-1..4** reproduce it: every one of
the 12 pairs retains **0 of 32** prior decisions into its next turn.

So a setup blocked for a **transient** reason is re-attempted on every advancing poll, bounded only
by staleness (one bar-period). Polls advance hourly, so the exposure is per-timeframe:

| Timeframe | Live setups | Extra attempts that can reach the entry gate |
|---|---|---|
| H1 | 281 | ~0 — the 60-minute window matches the hourly cadence **by coincidence, not by design** |
| H4 | 89 | up to **3** |
| D | 11 | up to **23** |
| W | 2 | up to **72** (not 167 — see below) |

**Two corrections to my first version of this table**, both from verification:

1. **The W bound was overstated ~2.3×.** Re-decisions are not the same as entry-delay re-tests: the
   `ALEX_V11_ENTRY_DAY` rule is evaluated at `nowMs` and only Mon/Tue/Wed UTC pass, so across a
   168-hour staleness window at most **72** attempts can reach `alexGConstructLivePosition`. The
   same truncation applies to D when a setup qualifies late on a Wednesday.
2. **The suspension currently excludes two-thirds of the exposure.** `A_repeatedReaction` is 257 of
   383 live setups and is rejected at `index.html:4746` *before* the entry-delay check, so while
   the research suspension is on, chasing can only apply to `B_breakRetest`. Live D and W setups
   are 11 and 2 and are **all pre-activation**, so there are **zero live instances today** — the
   mechanism is structurally real but currently unexercised.

The mechanism itself was confirmed with a positive control against unmodified `index.html`: a setup
rejected `BLOCKED — ENTRY MOVED` on one poll, with the rejection written to the ring, **opens on the
next poll once that ring entry is evicted** (`entryDelayPips` 2.0), while a control with the ring
entry intact correctly holds.

The sharpest case is `ENTRY_MOVED_TOO_FAR_FROM_SIGNAL` (`index.html:4333`). The v4.2 contract is
explicit that the rule *rejects, never chases*, when price has moved >5 pips from
`qualificationClose`. With hourly re-decision, a D-timeframe setup rejected at hour 1 is re-tested
every hour for a day and **opens the moment price wanders back inside 5 pips — which is chasing.**
`BLOCKED — EXISTING POSITION` behaves the same way once the blocking position closes.

**Not repaired autonomously.** `alexGRecordLiveSetupStatus` is protected, and raising the cap
changes which setups ALEX reconsiders — a frozen-strategy semantic change. See §7.2. This is the
single most consequential open item in the milestone.

#### Honesty note on the CDP evidence

The read helper refuses assignments and known mutating calls, but a regex over source text
**cannot** enforce read-only in JavaScript — verification demonstrated working bypasses
(`Object.assign(...)`, `Array.prototype.sort/reverse/fill`, `Reflect.set`, string-built names). The
guard reduces accident; it does not prove safety. The read-only property of this evidence rests on
the expressions actually issued, all of which are recorded above, and every load-bearing figure was
independently re-derived by the verifier from the durable on-disk ledger rather than taken from my
reads.

### 2.11 Why ALEX produces ~1 trade — answered from live production, and it is not a defect

The MOGO-020 question that started this whole thread ("why has ALEX produced ~1 paper trade?") is
now answered with live production evidence rather than inference. **Two frozen rules, both working
exactly as designed, account for it completely.**

| Stage | Live value |
|---|---|
| Setups in the engine's 90-day rebuild | **383** |
| Qualification timestamps span | 2025-12-12 → 2026-08-13 |
| Activation cutoff (`activatedAt`) | 2026-08-11T02:43:57.894Z |
| Setups qualifying **after** activation | **8 of 383 — 2.1%** |
| `tradedSignals` / closed positions / balance | **1** / **1** / **$9,900** (one −1R trade) |

**⚠️ CORRECTED.** I originally wrote that all 8 post-activation setups were "25–43 hours old" and
"all rejected `STATE_SIGNAL_STALE`", giving "0 new trades". **That was wrong on both counts**, and
wrong in an instructive way: those ages are ages at the **~47th re-decision**, i.e. artifacts of the
very ring defect §2.10 documents. I explained the funnel using a symptom of the bug.

The durable ledger records each setup's **first** evaluation (`firstLiveEvaluationTimestamp`). Read
from it, **7 of the 8 were first seen at age 1 minute — not stale at all**:

| Setup | Age at FIRST evaluation | Real first verdict |
|---|---|---|
| AUD_JPY H1 `B_breakRetest` | 1 min | **TRADE OPENED** |
| AUD_USD H1 RZR | 1 min | SUSPENDED — RESEARCH HOLD |
| EUR_JPY H1 RZR | 1 min | SUSPENDED — RESEARCH HOLD |
| AUD_USD H1 RZR | 1 min | SUSPENDED — RESEARCH HOLD |
| NZD_USD H1 RZR | 1 min | SUSPENDED — RESEARCH HOLD |
| USD_CHF H1 RZR | 1 min | IGNORED — ENTRY DAY NOT ELIGIBLE |
| GBP_JPY H4 RZR | 1 min | IGNORED — ENTRY DAY NOT ELIGIBLE |
| AUD_JPY H1 RZR | 539 min | IGNORED — STALE (a genuine restart backlog) |
| EUR_USD H1 `B_breakRetest` | — | **unobservable** — EUR_USD has 0 of 18,000 ledger records (§2.10) |

*(Nine rows against a funnel that says 8: the first eight are the ledger-observable set at the time
of reading, and EUR_USD is listed separately because it is structurally invisible in the ledger
rather than absent from the engine. The live post-activation count also moves as the window rolls —
383 setups at first reading, 387 later.)*

**The dominant blockers are the research suspension and the Thursday entry-day rule, not
staleness** — staleness accounts for exactly one, and that one is the restart-backlog case.
And "0 new trades" is simply false: the AUD_JPY `B_breakRetest` **was traded**, opened at age
1 minute. That is the trade sitting in the ledger.

So the corrected picture: with the tab open, post-activation setups are seen within about a minute
of qualifying — the pipeline is prompt. **For ALEX to trade, a setup must be `B_breakRetest`,
qualify after `activatedAt`, land on Mon/Tue/Wed UTC, arrive while the tab is open, and fill within
5 pips of `qualificationClose`.** The AUD_JPY trade met all five conditions. The behaviour is
defensible; my earlier explanation of it was not.

**The activation cutoff is still doing its job.** `alexGRunSetupEngine` rebuilds 90 days on every
poll, so almost everything it finds is historical and must not be back-filled. The pipeline runs the
full chain on all 12 instruments every H1 boundary and declines correctly. What changed is *which*
gate does the declining: the suspension and entry-day rules, not staleness.

**The operational consequence worth flagging** (in scope under *restart/recovery*): both
`alexGLiveSetupStatuses` and the evaluation cursor are **session-only** — a page reload clears them.
On the first poll after any restart the engine re-derives all 383 setups and evaluates the
post-activation ones *for the first time* long after they qualified, so they are permanently
recorded `IGNORED — STALE SIGNAL`. That is the frozen rule behaving correctly (never trade a signal
you missed), but it means **every restart burns the entire backlog of post-activation setups**, and
only setups qualifying while the tab stays open can ever trade. Recorded as a characteristic, not a
defect — changing it would be a frozen-strategy semantic change.

#### Decision-event accuracy, validated against live production

Checked directly on the running campaign's 500-event ring (~31 minutes, 76 scans):

| Property | Result |
|---|---|
| `sequenceNumber` strictly increasing | **yes** — 34,654 → 35,153, no reordering |
| Schema version | single (`mogo.decision-event.v1`) |
| `evidenceCompleteness` | `COMPLETE` on 500/500 |
| `scanId` ≠ `correlationId` | **0 events** |
| Scans started but never completed | **0** |
| Events carrying `parentEventId` | 172 |
| Unregistered reason codes | **none** |

The single `SCAN_COMPLETED` without a matching `SCAN_STARTED` is the ring boundary — its start event
was evicted — not a correctness defect.

### 2.15 Ledger, account and reconciliation state — verified against LIVE production

Everything in §2.8 is fixture evidence. This is the live campaign, read read-only.

| | ALEX | JVM |
|---|---|---|
| Balance | **$9,900** | **$10,000** |
| Open / closed positions | 0 / 1 | **1** / 0 |
| Journal entries | 1 | 1 |
| Arithmetic | 10,000 + (−100) = **9,900 ✓** | 10,000 + 0 = **10,000 ✓** (balance moves on close, not open) |

ALEX's single closed trade is `AUD_JPY H1, Loss, −$100, −1.00R`, with
`exitDetectionSource: historical_candle` — i.e. the exit was reconstructed from real M1
executable-price candles by the v4.2.1 gap-recovery path, not from a live snapshot. That is the
exit-monitoring mechanism working on real data.

**JVM currently holds an open paper position.** Worth stating, because the milestone's narrative
has centred on ALEX's single trade: JVM is trading in this campaign.

The app's own read-only integrity check, run against live state:

| Check | Result |
|---|---|
| `balanceDifference` | **0.00** |
| Journal records with no account position | **0** |
| Account positions with no journal record | **0** |
| Duplicate account trade IDs / duplicate journal trade IDs | **0 / 0** |
| Closed journal records missing P&L | **0** |
| `newlyOrphanedAfterReset` (the INC-001 signature) | **0** |

The same check for **ALEX**, via `computePaperTradingHealthReport()`:

| Check | Result |
|---|---|
| Expected vs actual balance | **9,900 vs 9,900 — difference 0.00** |
| Journal records with no account position | **0** |
| Account positions with no journal record | **0** |
| Duplicate account trade IDs | **0** |

**Both live ledgers reconcile exactly, and the JOURNAL_ONLY orphan class that triggered INC-001 has
not recurred in this campaign** — on either strategy.

### 2.12 Chart data vs strategy-evaluation data — separation is deliberate and surfaced

The chart and the engine fetch independently, so the question is whether an operator can see a
chart that disagrees with what the strategy decided. Established by inspection:

* **Verdicts cannot disagree.** `evaluateLiveTrigger` is the single source for both the chart's
  live-trigger badge and JVM auto-trading, so the badge and the trade decision are the same
  computation, not two implementations.
* **Candles deliberately differ, and that is recorded.** `scanPair` keeps the full candle array in
  `pairData` for charting while gating *evaluation* on the ADR-011 completeness contract
  (`index.html:8834-8847`), setting `evaluationSuppressed` when they diverge.
* **The divergence is operator-visible.** `renderMarketDataCompletenessDiagnostics`
  (`index.html:6051`) renders an amber card naming every pair whose history was too short to
  evaluate, with requested/received counts and the pagination reason. It is called from `scanAll`
  (`index.html:8881`) inside a `try/catch` so an indicator can never break a scan, and it is
  covered by `run_v130_candle_completeness_regression_tests.js`.
* **Timeframes differ by design**: JVM always evaluates entry timing on M15 regardless of the
  displayed timeframe, which the code states explicitly.

**No change proposed.** The one residual is that the chart will happily draw a pair the engine
refused to score; the amber card is what tells the operator why, and it exists.

### 2.13 Concurrent poll ticks — production-observed, and trading-safe

Ledger analysis found **9 hours containing two advancing polls with disjoint, non-contiguous pair
sets** (most separated by ~25 s, though two gaps are 223 s and 2,774 s) (e.g. a 12-pair poll followed by a 5-pair poll covering only late
scan-order pairs). That is the signature of two `alexGLivePollTick` executions overlapping: the
second finds the early pairs' cursors already advanced by the first and skips them.

`startAlexGLivePollingIfNeeded` (`index.html:5011`) is guarded against creating a second interval,
so this is overlap of a long-running tick with the next interval firing, not a duplicate timer.
There is **no re-entrancy guard** on the tick itself.

Rather than speculate about the risk, it was exercised: two ticks launched concurrently against a
setup that does open a trade. Result — **exactly one position, one journal entry, one
`tradedSignals` entry, one `TRADE_OPENED`, and uncorrupted setup state**, with both ticks
confirmed to have genuinely run (`SCAN_STARTED` = 2).

**Correction to my attribution.** I credited `alexGConstructLivePosition`'s identity checks. That is
wrong, and mutation testing shows it: with all five identity-keyed guards disabled the fixtures
still pass. The guard that actually holds under concurrency is the **pair+timeframe overlap rule**
(`index.html:4314`) — removing *that* produces two open positions. RE-6 now asserts the correct
attribution, and RE-7 records the scope limit: both ticks share one identity, so this scenario does
**not** exercise the drift defect in §2.16.

**Conclusion: no code change is warranted.** The missing re-entrancy guard is a code-hygiene
observation, not a trading-correctness defect, and is now backed by evidence rather than by the
absence of a counter-example. Recorded so the open item can be closed honestly.

### 2.14 Inheritance by a future paper-authorized strategy

Which MOGO-021 protections a newly authorized strategy would inherit for free, and which it would
not:

| Protection | Inherited? | Why |
|---|---|---|
| Decision-event schema, reason-code registry, evidence model | **yes** | strategy-agnostic; `emitDecisionEvent` validates against a central registry |
| Market-data completeness contract (ADR-011) | **yes** | applied in `scanPair`, shared by every scanned instrument |
| Protected-function/constant drift gate | **yes** | `regression-baseline.json` covers whatever is registered |
| Paper-ledger version guard / commit + rollback | **yes, if it uses the shared ledger** | `commitPaperLedger` / `savePaperAccountGuarded` |
| **Forward-observation coverage ledger (MOGO-013)** | **NO** | `evidenceRecordForwardObservations` is called **only** from `alexGLivePollTick`. JVM's `scanAll` records none, so JVM has no forward coverage evidence at all today |
| **Candidate-level instrumentation** | **NO** | wired only into ALEX's non-protected plumbing; JVM's is protected (§7.1) |
| Ledger-integrity / reconciliation tooling | **partly** | `computePaperLedgerIntegrity` is JVM-shaped (`paperAccount` + `journalEntries`); ALEX has a separate equivalent |

**The actionable gap is the forward-coverage ledger.** It is the mechanism that makes "was this
instrument actually evaluated?" answerable, it is what finally settled the EUR_USD question, and
**JVM does not have it** — nor would a new strategy.

It is **not governance-blocked**: `scanAll`, `evidenceRecordForwardObservations`,
`evidenceBuildPollObservation` and `evidenceObservationBase` are all unprotected. But it is also not
a one-line call, because the observation schema is currently ALEX-shaped —
`evidenceObservationBase` hard-codes `strategyId` from `RULES_ALEXG.ruleVersion`, so recording a JVM
poll through it today would **mislabel JVM evidence as ALEX**. The specified change is:

1. Add an optional `strategyId` argument to `evidenceObservationBase`, defaulting to today's value
   so every existing ALEX record stays **byte-identical** — asserted by fixture, not assumed.
2. Thread it through `evidenceBuildPollObservation`.
3. Record a JVM poll observation from `scanAll`, in a `finally` so a failed scan is recorded too
   (ALEX's own precedent), carrying `instrumentsConfigured = ALL_PAIRS.length` (35),
   `instrumentsEvaluated` from the pairs actually scanned, and the auto-trade-eligible subset (12).

Natural keys do not collide: POLL keys on `tickId`, and JVM's scanId comes from the same unique
generator ALEX uses. The one thing to be careful of is that step 1 touches a function ALEX's
evidence depends on — a regression there would corrupt ALEX's forward ledger, so it needs the same
implement → independently verify → remediate loop as everything else in this milestone.

### 2.16 🔴 SIGNAL IDENTITY IS NOT STABLE — all four duplicate-trade guards can miss

**This is the most serious defect found in the milestone, it was found by verification rather than
by me, and it falsifies a safety claim I made in §2.10.**

I wrote that a duplicate trade is prevented because `alexGConstructLivePosition` (`index.html:4302`)
checks `tradedSignals`, open positions, closed positions and journal entries. **All four key on
`signalId`, and `signalId` is not stable across rebuilds.**

`alexGLiveSignalId` (`index.html:4273`) embeds `setup.setupId`, which embeds the `zoneId`, which
embeds the cluster's **first-reaction close time** and the zone's **validation time**. The engine
rebuilds from a fixed-count candle window (2,220 H1 bars ≈ 128 days), so when the oldest reaction in
a cluster falls out of that window the zone **re-anchors** and the same economic setup acquires a
**different `signalId`**.

Confirmed in live production. The one trade this campaign has ever made, and its own reconstruction
now — same pair, same timeframe, same setup type, same reaction `AGR|AUD_JPY|H1|low|1786503600000`,
same `qualificationTimestamp` `1786514400000`:

| | zone component of `signalId` |
|---|---|
| As traded (in `tradedSignals` **and** `closedPositions`) | `AGZ\|AGC\|AUD_JPY\|H1\|high\|`**`1775610000000`**`\|v`**`1786395600000`** |
| As reconstructed now | `AGZ\|AGC\|AUD_JPY\|H1\|high\|`**`1783983600000`**`\|v`**`1786420800000`** |

Measured against live state: `alexGSetupState.map(alexGLiveSignalId)` yields **0 matches** against
`tradedSignals`, and **0 matches** against `closedPositions`. **Every one of the four guards misses,
right now, on the only trade the campaign has made.** The ring dedup at `index.html:4641` keys on
the same field and cannot help either.

**Consequence — reproduced end-to-end with ZERO guards mutated.** Against pristine `index.html`:
poll 1 opens a real position; the position is closed; the *only* other change is that the oldest H1
candles fall out of the fetch window; poll 2 then opens a **second real paper position on the same
economic setup** (`rid_same=true qt_same=true qualClose_same=true zid_same=false`, ending
`open=1 closed=1 journal=2 tradedSignals=2`). The only remaining bound is the staleness gate, which
is a race rather than a guard: one bar-period from qualification (H1 60 min, H4 4 h, D 24 h,
W 7 days).

**It has already happened in production.** The durable ledger contains **9 post-activation
signalIds for 8 economic setups**. The extra one is the traded AUD_JPY setup under its *re-anchored*
identity, first evaluated `2026-08-13T23:01:09.987Z` and recorded `IGNORED — STALE SIGNAL` at age
2,461 minutes. The engine treated a setup it had already traded as one it had never seen; every
guard missed, and **only staleness prevented a second trade.** Drift is endemic rather than
exceptional: **14 stable keys carry ≥2 signalIds and three carry 3** — roughly 4% of setups have
re-anchored at least once.

**Two corrections to my own first account of this, both in the unsafe direction:**

* **There is a FIFTH guard, and it drifts identically.** `index.html:4361` keys on
  `tradeId = AGT|setupId`, and `setupId` embeds the same `zoneId`. It is load-bearing *today* —
  with the four `signalId` guards disabled but this one intact, the re-open is still blocked — so
  any fix that covers only `signalId` leaves the defect half-repaired.
* **One of the "four" guards is dead code and always has been.** `alexGJournalEntries.some(e =>
  e.signalId === signalId)` (`index.html:4305`) can never fire: `buildAlexJournalOpenRecord`
  (`index.html:2315`) never writes a `signalId` field, and live production confirms
  `alexGJournalEntries[0].signalId === undefined`. It is **three** live identity guards plus one
  that has never fired — independent of drift.

**Correction to the mechanism label:** the rebuild window is not "90 days".
`fetchAlexGReplayDatasets` (`index.html:4027`) requests a fixed **count** — `days*24+60 = 2220` H1
bars ≈ **128 calendar days**. The mechanism is as described; my label was wrong.

**Why the ring fix does not address it.** Raising the status-ring cap (§7.2) does nothing here: the
identity itself changes, so a larger ring simply stores the old identity that no longer matches.
These are two independent defects that happen to share a symptom.

**A stable identity already exists in the data.** `pair | timeframe | setupType | reactionId |
qualificationTimestamp` are all preserved across re-anchoring — only the zone-anchor components
drift. So the fix is available without inventing anything.

**Not repaired autonomously**: `alexGLiveSignalId` and `alexGConstructLivePosition` are both
protected, and changing signal identity changes which trades ALEX considers duplicates — a frozen
strategy semantic. Recorded in §7.4 with the smallest governed change.

### 2.17 Identity-drift detector — instrumenting §2.16 without pre-empting the governed fix

§2.16 is governance-blocked: repairing the duplicate guards means changing signal identity inside
protected functions, which is Joe's decision. But **detecting** the condition is not blocked —
`alexGEvaluatePairForLiveSetups` is not protected — and until now the defect was invisible in
production except by hand-analysis of the ledger.

Shipped: a detector that fires when a setup's **anchor-free identity** matches an already
open/closed position carrying a **different `signalId`** — precisely the state in which every
duplicate guard misses.

```js
function alexGStableSetupIdentity(x){
  return [x.pair,x.timeframe,x.setupType,x.reactionId,x.qualificationTimestamp].join('|');
}
```

Every component survives a re-anchor, and the same function serves both setup records and stored
position records because both carry all five fields. When drift is detected it emits
`STATE_SIGNAL_IDENTITY_DRIFTED` on the decision bus **and** records a durable `IDENTITY_DRIFT`
pipeline observation — so the frequency in real trading becomes measurable rather than estimated.

**It is deliberately observation-only.** It does not block, skip, `continue`, or alter any value the
trading path reads, and the whole detector is wrapped so an observation defect can never reach a
trading decision. Repairing the guard is the governed change in §7.3; this records the evidence for
that decision instead of quietly making it.

Lessons from earlier in this milestone are applied rather than re-learned: the reason code is
registered **before** use, the latch is a **bounded** Set with FIFO eviction, and it is **cleared in
`clearDecisionEvents()`** so a dev-only button cannot permanently silence an ongoing condition.

**DRIFT-1..9 (`run_v1236`) include a regression proof of the defect itself.** DRIFT-6 drives the
full production path with every persisted record carrying the pre-drift identity and the
freshly-derived setup carrying the new one, and the result is **one economic setup, two open/closed
positions**. Independent verification reproduced the same outcome **organically** — rolling the
candle window with every guard intact, no hand-edited records — so it is not a fixture artifact.
That fixture is expected to invert when the governed fix in §7.3 lands, at which point it becomes
the proof the fix works.

**Calibration, from verification:** the guard miss is real and certain; the *second position* also
requires the drift to land inside the staleness window. Drift takes roughly 128 days to arrive,
by which time `alexGIsSetupSignalStale` normally rejects the setup. So this is a narrow coincidence
rather than a routine occurrence — but it is not prevented by anything, and it has already produced
a real guard miss in production (§2.16).

**Verified observation-only, four independent ways.** The detector was removed surgically and the
entire 24-suite run compared: the only deltas are the DRIFT fixtures themselves. Hooking both event
sinks and diffing an identical scenario with and without the detector gives an **identical pipeline
stream and a byte-identical final account state**. Forcing the identity function to throw on every
setup in every evaluation fails only the DRIFT fixtures — every trading fixture is unaffected.

**Blind spot found and closed.** The first version scanned only `alexGAccount` positions. Because
`loadAlexGSaved` loads `fxhub_alexg_account` and `fxhub_alexg_auto` independently (INC-001 per-key
isolation), an unreadable account key leaves positions empty while the journal and `tradedSignals`
survive — a state where the guards miss *and* the detector was blind. Verification demonstrated a
second real position opening with **zero** drift events. The detector now also scans
`alexGJournalEntries` (matched on `tradeId`, since journal records carry no `signalId`), and
**DRIFT-9** proves detection from the journal alone.

**Three of my own fixtures could not fail, and were fixed.** DRIFT-5's second poll evaluated zero
instruments — the cursor gate skipped every pair — so it passed with the latch permanently
disabled. DRIFT-8 ran against an empty account, so a degenerate identity returning a constant
survived. DRIFT-4 asserted only `reason`, so `stage` and `sourceTradeId` could be stripped
silently. All three now die to the mutation that breaks what they name, each killing only its own
fixture. The latch is also now marked **after** a successful emit rather than before, so a rejected
event can no longer suppress the condition silently, and it keys on `(stableId, signalId)` so a
second re-anchor is still reported.

---

## 3. Gates

| Gate | Result |
|---|---|
| Canonical | **24 suites · 1,316 / 1,316 · 0 failures · 0 errors** |
| Platform | **1,049 / 1,049** |
| Protected ALEX drift | **0** — 63 functions, 4 constants, byte-identical |
| Campaign C1 | intact |

---

## 4. Independent verification

Verification was run as adversarial falsification, not review — verifiers were instructed to
assume the engineer was wrong and to attack specific claims, and were given the authority to run
the gates themselves rather than trust reported numbers.

**Findings were returned against my own work in three separate places, and all three were upheld
after I checked them myself:**

1. The cursor auto-repair was **fail-open** in exactly the condition it detected (§2.3) — withdrawn.
2. The "permanent starvation" model was **arithmetically wrong**, and the fixture proving it was
   tautological (§2.4) — corrected. The root cause was later established outright (§2.10).
3. Eight of sixteen JVM fixtures **could not fail** (§2.5) — suite rebuilt around a positive control.

Six adversarial passes ran across the milestone. Every one returned findings against my own work,
and the cumulative tally is the honest summary of this milestone's engineering:

| Round | Target | Outcome |
|---|---|---|
| 1 | MOGO-020 carry-over claims | cursor guard **fail-open**; starvation model arithmetically wrong; 8/16 JVM fixtures could not fail |
| 2 | the fail-closed cursor detector | no trading defect, but the latch survived `clearDecisionEvents()`, was unbounded, and **STARVE-3 was a fake proof** |
| 3 | the JVM positive control | core survived **6/6 gate-deletion mutants**; drop-point and auditability claims overstated |
| 4 | the EUR_USD root cause | mechanism upheld, but my lead arithmetic was **tautological**, "0 poll appearances" was a **separate error**, and the dedup defect was **larger than I reported** |
| 5 | the remediation | **found the signal-identity defect I missed** (§2.16); E2E-11/12 and E2E-15 vacuous; REDEC-4 vacuous; §2.11 falsified from the ledger |
| 6 | the final remediation | **§2.16 confirmed and UNDERSTATED** — a second position reproduced end-to-end with zero guards mutated, and it has already occurred in production; a fifth guard and a dead guard found; §7.2's retracted number was still in place |

**Sixteen distinct defects in my own work were found by verification rather than by me**, including
one — signal-identity instability — that is the most serious trading-correctness finding of the
milestone. Every one was reproduced independently before being accepted, and every fixture fix was
mutation-tested to confirm it now fails when the thing it tests is broken.

The method that made the difference was granting verifiers authority to **mutate a copy of the
codebase** rather than only read it. Four separate vacuous fixtures of mine passed review and died
only to mutation.

**Corrections to earlier reporting**, both surfaced by verification:

* "JVM emits zero decision events" is imprecise. `checkAutoTrades` is called from `scanAll`, which
  does emit `SCAN_STARTED` / `SCAN_COMPLETED` / `ENGINE_ERROR`. The accurate statement is that JVM
  emits **no candidate-, rule- or rejection-level events of its own**.
* The `evaluateLiveTrigger` rejection reasons are **free-form English strings**, not registry
  codes, and one is interpolated (`` `R:R only ${ratio}:1` ``). Calling them "structured" overstated
  it; they also do reach a human today via the chart's live-trigger badge (`index.html:10266`),
  just never a durable record.
* The `c443ed6` commit message said "20 fixtures in this suite"; the file contained 23.

---

## 5. Carried forward from MOGO-020

* **EUR_USD** — 0 poll appearances, 0 evaluations. Loop logic proven correct (`c443ed6`, LOOP-1..5);
  a fetch failure would leave the cursor unset and cause retry every tick (~655 appearances), so the
  observed 0 means it is skipped by the cursor gate. Single remaining hypothesis: its last complete
  H1 candle carries a close time one boundary ahead of the local `currentH1Boundary`. The
  `instrumentsSkipped` diagnostic records exactly the two numbers that settle it.
* **GBP_USD** — ~54 poll appearances ≈ one per H1 boundary is the **correct** cadence; it is
  evaluating and producing no setups. Distinguishable by the same diagnostic.
* **Dedup contract defect** — the naive fix broke 20 fixtures (a parallel set desynchronizes when
  the ring is reset externally). Correct fix needs the protected `alexGRecordLiveSetupStatus`.
  Reverted in MOGO-020; still open.
* **Observation continuity** — 84.5% over the audited span, 12 gaps >10 min, one confirmed runtime
  restart. Operational.

### Open items raised by verification, not yet addressed

| Item | Where | Status |
|---|---|---|
| 🔴 **Signal identity not stable — all four duplicate-trade guards can miss** | §2.16 / §7.3 | **open, governance-blocked** — the only open item with a path to a real duplicate paper trade |
| EUR_USD root cause | §2.10 | **RESOLVED** — never starved; a truncated 300-entry status ring made the front-of-scan-order pairs invisible in the durable ledger |
| `alexGLiveSetupStatuses` 300-entry FIFO vs its "PERMANENT, never reconsidered" contract (`index.html:4282` vs `4641`) | ALEX | **open, governance-blocked** — now with production proof (§2.10); smallest governed change in §7.2 |
| PIPELINE natural key omits the pair (`index.html:13039`), so two instruments failing in the same millisecond collide and one record is dropped as a duplicate | MOGO-020 carry-over | open |
| `instrumentsEvaluated` is pushed **before** the `await`, so it means "attempted" | naming | open |
| `alexGCheckLivePositions()` runs before the per-pair loop and is not individually guarded — a throw there aborts the whole tick | ALEX | open |
| No re-entrancy guard on `alexGLivePollTick` under `setInterval` | ALEX | **CLOSED** — overlap is production-observed and was exercised directly; trading-safe (§2.13) |
| JVM diagnostics fix remains governance-blocked (all four functions protected) | §2.2 | blocked, needs governed change |
| Live campaign still runs pre-`c24b96b` code; new diagnostics inactive until an operator reloads (costs re-entering broker credentials) | §1 | operator action |

---

## 6. Verification result

Two adversarial verifiers ran against the redesigned work, both instructed to falsify rather than
review, and both authorised to run the gates and to **mutate a copy** of the code to test whether a
fixture actually discriminates.

### 6.1 The fail-closed cursor detector — no trading-correctness defect

The central claim was **proved, not merely accepted**: `cursorAhead === true` implies
`lastEval > currentH1Boundary`, which implies the pre-existing skip predicate
`currentH1Boundary <= lastEval` is true by transitivity, so `continue` always fires and
`alexGEvaluatePairForLiveSetups` — which has exactly one call site — is unreachable on that
iteration. There is no threshold at which the detector is true and the skip is false. `NaN` cannot
enter (`|| 0` makes it 0). Behaviour when the flag is false is bit-identical: the comparison is
side-effect-free, no event is emitted, so the sequence counter and event ring are unperturbed.

Three real findings, all fixed:

| Finding | Fix |
|---|---|
| **`clearDecisionEvents()` did not reset the latch.** A dev-only Diagnostics button would leave the latch saying "already reported" while deleting the event it referred to — permanently silencing an *ongoing* fault on the bus. Same failure class the reverted revision was faulted for. | latch now cleared alongside `decisionEventKnownCandidateIds`; **STARVE-10** proves the detector re-arms |
| **The latch key space was unbounded.** My "one key per pair" assumption was wrong: under a persistently future-dating feed the cursor advances each time the pair is finally evaluated, minting a new key — reproduced at ~3 keys/hour (~26k/year) in a tab designed to stay open. It was the only unbounded structure in the file. | converted to a `Set` with FIFO eviction at a named cap; **STARVE-11/12** |
| **STARVE-3 was a fake proof.** It asserted on the object handed to the recorder, *before* `evidenceBuildPollObservation` ran — it tested the capture hook, not the durable schema, and passed even when the field was stripped. | now asserts on the **builder's output**; I mutation-tested it myself — stripping the field makes it fail 0/8, killing exactly its own fixture |

The `2*3600000` literal is now the named `ALEXG_CURSOR_MAX_AHEAD_MS`, with a comment pinning its
H1-only scope.

**A claim of mine was corrected in the opposite direction.** I had reasoned that `.D`/`.W` cursors
can legitimately sit days ahead, making the guard dangerous to generalize. That is **false**: both
engines write those cursors only inside a loop gated on `closeTimes[tf][ptr+1] <= h1CloseTs`, so
`.D`/`.W` are structurally clamped at or behind `.H1` and can never lead it (measured six hours
*behind*). Generalizing the guard would be redundant, not dangerous — the correct rationale, now in
the code comment.

**Two limitations recorded rather than papered over.** The durable flag is a snapshot of
`cursor > boundary + 2h`, so under continuous future-dating it reads true in only ~25% of hourly
samples, and a +1h or +2h fault never sets it at all while still costing evaluations. And no UI
surface renders `instrumentsSkipped` — an operator reaches it only via a raw ledger export.

### 6.2 The JVM positive control — the core survived a harder test than I ran

The verifier did not merely un-apply preconditions; it **deleted each gate from a copy of
`index.html`** — the exact failure mode that sank the first version. Six mutants:

| Gate deleted | Fixture | Result |
|---|---|---|
| `if(!autoTrading.enabled)return;` | JVM-17 | **FAIL** — 4 opened vs baseline 4 |
| `bucket!=='Active watch'` filter | JVM-18 | **FAIL** |
| `tradedToday` checks (×2) | JVM-19 | **FAIL** |
| open-position checks (×2) | JVM-20 | **FAIL** — `EUR_USD positions=2` |
| `if(!sess.active)return;` | JVM-21 | **FAIL** |
| `isPreferredTradingDay()` | JVM-22 | **FAIL** |

**Each mutant killed exactly its own fixture and nothing else** — no collateral, no accidental
cross-coverage. Mutating the scorer itself (threshold 55→70, `WEIGHTS.engulf`→0,
`WEIGHTS.bias3`→0, R:R floor→4.99) collapsed the suite, confirming the positive control is coupled
to the frozen scorer rather than tuned to pass.

The "candles constructed, verdict not" rule was independently checked and held: no rule, weight,
threshold or protected function is reassigned anywhere; the only seams are `fetch`, `Date` and DOM
stubs. AOI scoring 0 and wick scoring 0 were verified on the live objects, the engulf bar satisfies
the app's stricter-than-documented `sw` loop with strict inequality on both sides (no boundary
exploitation), and the daily AOI clusters survive re-running at `tolerance=1e-9` — the touches are
genuine, not tolerance-gamed. The negative control scores 43 vs 55, a real near-miss rather than a
0-vs-55 no-op.

**Overclaims found and fixed** (see §2.6 for the drop-point correction):

* **JVM-26 as worded was false for production.** "The whole sweep leaves the decision log EMPTY"
  held only because the fixture never called `scanAll`, which emits `SCAN_STARTED`/`SCAN_COMPLETED`.
  Replaced: the suite now runs the real `scanAll()` and asserts the accurate claim — scan-level
  events are present (`{"SCAN_STARTED":1,"SCAN_COMPLETED":1}`) while **not one**
  candidate-, rule- or trade-level event appears, with 8 positions open (**JVM-27**), and every
  event is sourced to `scanAll` (**JVM-28**).
* **The old JVM-25 was still vacuous** — it filtered `e.source` on a regex matching strings no emit
  site produces. Removed entirely rather than kept as decoration.
* **JVM-27 (old) claimed a discard it never tested.** Now **JVM-29** asserts the discard itself:
  the reason exists on the verdict, and after the sweep journal, decision log and `tradedToday` are
  all empty.
* Minor: JVM-19's detail string was hard-coded to say "blocked" and could print a self-contradiction
  under mutation; `autoTrading.log[0]` was unguarded so a scoring regression produced an execution
  error instead of clean failures; JVM-18 lacked the baseline-contrast conjunct. All fixed.

**Residual limitation, recorded not hidden:** the daily/weekly AOI touches land at bit-identical
prices from a period-6 synthetic cycle. It satisfies the frozen 3-touch rule honestly, but no real
market produces that. The positive control proves the path fires; it is **not** evidence about how
often real structure would.

---

## 7. Governance boundaries — what stays unobservable, and the smallest change that would fix it

Two gaps are blocked by the protected-function contract, not by engineering difficulty. Neither is
repaired autonomously. For each: what is unobservable, why it is blocked, the **smallest** governed
change, and whether a non-invasive method gives equivalent proof.

### 7.1 JVM candidate-level diagnostics

**Unobservable today.** JVM emits scan-level events only (`SCAN_STARTED`, `SCAN_COMPLETED`,
`ENGINE_ERROR`, all from `scanAll`). Not one candidate-, rule- or rejection-level event exists —
proven against a real firing sweep by **JVM-27/28**, where 8 positions opened and the only events
present were the two scan-level ones. Three drop points discard already-computed detail:

| Site | Discarded | Line |
|---|---|---|
| `if(!result.fires)return;` | `result.reason` and `result.conf` | `index.html:16593` |
| `if(pos.error){return;}` | structured sizing error on a **fired** signal | `index.html:16597` |
| the eligibility filter | which pairs were excluded and why | `index.html:16580-16588` |

**Why blocked.** All four functions on that path — `checkAutoTrades`, `evaluateLiveTrigger`,
`openPaperPosition`, `getSession` — are protected. Any emit added inside them breaks drift-0.
ALEX's equivalent plumbing is *not* protected, which is why ALEX could be instrumented
autonomously and JVM cannot.

**Smallest governed change.** One line at `index.html:16593`, before the existing `return`:

```js
if(!result.fires){ emitDecisionEvent({eventType:'CANDIDATE_REJECTED',strategyId:'current_strategy',
  pair:oPair,source:'checkAutoTrades',stage:'LIVE_TRIGGER',decision:'REJECTED',
  reasonCode:'CONFLUENCE_BELOW_THRESHOLD',reasonText:result.reason,
  context:{confluence:result.conf&&result.conf.total},evidenceCompleteness:'PARTIAL'}); return; }
```

It touches one protected function, adds no branch, changes no rule, and reuses a value the function
already computed. It would require a new baseline hash for `checkAutoTrades` and one new reason
code registered **before** use. Cost: drift-0 must be re-established against a new baseline.

**Non-invasive equivalent? Partial, and it should not be mistaken for the real thing.**
`evaluateLiveTrigger` is pure and callable from outside, so a shadow observer could recompute the
verdict for each eligible pair and record *that*. It would reproduce the reason text faithfully.
What it could **not** do is prove the recomputed verdict is the one the live path actually acted on
— it is a re-derivation, not a record of the real decision, and it would double the market-data
cost. Recommended only if the governed change is declined.

### 7.2 ALEX live-setup status ring (the §2.10 residue)

**Unobservable / incorrect today.** `alexGLiveSetupStatuses` is a 300-entry ring that holds less
than one poll cycle (383 setups). Consequences: the pairs earliest in `SCAN_PAIRS` order are absent
from the panel and from the `statuses` array written to the durable ledger; and the duplicate guard
at `index.html:4641`, documented *"PERMANENT, never reconsidered"*, reads that same truncated ring,
so for evicted pairs a setup's fate is **not** decided once.

**Why blocked.** `alexGRecordLiveSetupStatus` is protected. Raising the cap, or separating the
"decided" set from the "display" ring, means editing it.

**Severity — this is the milestone's most consequential open item.** It is not merely a display
cap. Because no pair's entries survive to its next turn (`383 − 54 = 329 > 300` in the best case,
and REDEC-1..4 measure 0 of 32 retained for all twelve), the duplicate short-circuit never fires,
and the durable ledger records **~47 re-decisions per signalId**. A setup blocked for a transient
reason is therefore re-attempted every advancing poll until it goes stale: up to 3 extra attempts
on H4, 23 on D, and **≤72 on W** — not 167, because `ALEX_V11_ENTRY_DAY` admits only Mon/Tue/Wed
UTC, and any 168-hour window contains exactly 72 such hours. For
`ENTRY_MOVED_TOO_FAR_FROM_SIGNAL` that converts the documented *"rejecting — never chasing"* rule
into chasing on the D and W timeframes. H1 is safe only because the 60-minute staleness window
happens to match the hourly poll cadence — a coincidence, not a guard.

**Current exposure is smaller than the bound suggests.** The suspension gate (`index.html:4746`)
runs *before* the entry-delay check (`index.html:4332`), so while `A_repeatedReaction` is suspended
— 259 of 387 live setups — chasing can only reach `B_breakRetest`. Live D and W setups are 11 and 2
and are all pre-activation, so there are **zero live instances today**. The mechanism is
structurally real and currently unexercised.

**Smallest governed change.** Raise the cap so it exceeds one cycle's setup count with headroom —
`if(alexGLiveSetupStatuses.length>5000) alexGLiveSetupStatuses.length=5000;` — a single numeric
literal in one protected function. It restores the documented finality contract, removes the ledger
bias, and eliminates the chasing exposure in one edit. It **does** change ALEX's live behaviour:
setups currently re-decided each poll would be decided once, as the contract already says they
should be. **That is a frozen-strategy semantic question and is Joe's call, not mine.**

**Non-invasive equivalent? Yes for observability, no for the dedup.**
* *Observability:* already solved and shipped. `instrumentsEvaluated`/`instrumentsConfigured`/
  `instrumentsSkipped` derive from the poll loop, not the ring, and are immune to the truncation
  (**BIAS-4/5**). No protected change needed. The running campaign simply predates it.
* *Dedup:* a parallel unbounded decided-signal `Set` in the non-protected caller would work
  mechanically, but a prior attempt was reverted for desynchronizing whenever
  `alexGLiveSetupStatuses` is reset externally (`index.html:5195`, and existing suites do this).
  That specific desync is now solvable — the reset sites are known and a parallel structure can be
  cleared alongside them. **But it would still change which setups ALEX reconsiders**, which is the
  same semantic change as above, reached by a back door that evades the protected-function gate.
  Doing it that way would be worse governance, not better. Not done.

### 7.3 Signal identity instability (§2.16) — the most severe open item

**Unobservable / incorrect today.** `signalId` embeds zone-anchor timestamps that drift as the
rolling 90-day window advances, so all four duplicate-trade guards in
`alexGConstructLivePosition` (`index.html:4302`) can miss. Confirmed live: 0 of 387 current
signalIds match the one entry in `tradedSignals`, for a trade that demonstrably happened.

**Why blocked.** `alexGLiveSignalId` and `alexGConstructLivePosition` are both protected, and
changing signal identity changes which trades ALEX treats as duplicates.

**Smallest governed change.** Add a second, anchor-free identity to the duplicate check rather than
altering `signalId` itself — every component needed is already on the setup record:

```js
const stableId=`${setup.pair}|${setup.timeframe}|${setup.setupType}|${setup.reactionId}|${setup.qualificationTimestamp}`;
```

Store it alongside `tradedSignals[signalId]` and test both. That keeps `signalId` byte-identical for
every existing consumer (journal, ledger, analytics) and adds one OR-term to the guard.

**It must cover BOTH duplicate checks.** There are two, not one, and they drift together:

| Site | Keys on | Drifts? |
|---|---|---|
| `index.html:4302` | `signalId` (× 3 live checks; the journal one is dead code) | **yes** |
| `index.html:4361` | `tradeId` = `AGT\|setupId`, which embeds the same `zoneId` | **yes** |

A fix applied only at 4302 leaves 4361 drifting — and 4361 is currently load-bearing, so a partial
fix would look like it worked while removing the guard that is actually holding today. The change
touches two protected functions and changes no rule.

**While here, `index.html:4305` should be deleted or repaired.** `alexGJournalEntries.some(e =>
e.signalId === signalId)` has never been able to fire because no ALEX journal record carries a
`signalId`. It reads as defence-in-depth and is not.

**Non-invasive equivalent? No.** The check lives inside a protected function on the trade-open path;
there is no external hook between the duplicate test and the open. A shadow observer could *detect*
a duplicate after the fact but could not prevent one. **This is the one open item where the absence
of a governed change leaves a path to a real duplicate paper trade.**

### 7.4 Standing constraints, all intact

PAPER ONLY · live-money **NOT AUTHORIZED** and no live-money gate touched · TJR **not**
paper-authorized and untouched (`status:'development'`, all four capabilities false) · ALEX
protected drift **0** (63 functions, 4 constants byte-identical) · JVM governed strategy integrity
preserved — every JVM function on the decision path is called as-is and none was modified.

---

## 8. MOGO-021 completion standard — coverage matrix

| Scope item | Status | Evidence |
|---|---|---|
| Authoritative ALEX/JVM instrument × timeframe coverage | **done** | §1 table, read from live state. ALEX 12 pairs H1/H4/D/W; JVM scans 35, auto-trades 12, M15 entry |
| H1/H4/D/W candle completeness and boundary correctness | **done** | `run_v1234` (27) — DST to the minute, 17:00 NY, per-granularity fallbacks; ADR-011 contract + `run_v130` |
| Chart data vs strategy-evaluation data consistency | **done** | §2.12 — shared verdict function, deliberate candle divergence, operator-visible amber card |
| Stale / incomplete / missing candle handling | **done** | RESIL-1..4, `DATA_INSUFFICIENT_HISTORY`, E2E-13/14, `run_v130` |
| Restart / recovery behaviour | **done** | E2E-11/12/13; §2.11 restart-backlog characteristic |
| Observation and evaluation continuity | **done** | COVERAGE-1..11, BIAS-4/5; live: 12/12 instruments, EUR_USD 61/67 in line with peers |
| Decision-event accuracy | **done** | Live 500-event validation: strictly increasing sequence, single schema, 100% `scanId==correlationId`, 0 unterminated scans |
| AOI / setup / signal qualification correctness | **done** | `v126` (61) organic zone/setup engine; E2E-1 gate chain |
| Valid paper order-generation path | **done** | ALEX E2E-6..9; JVM-12..16 |
| Deterministic end-to-end paper execution (ALEX + JVM) | **done** | ALEX `run_v1236` through `alexGLivePollTick`; JVM `run_v1233` through `scanAll` |
| Lifecycle persistence | **done** | E2E-8, E2E-12 (isolated persisted guard) |
| Ledger / account consistency | **done** | `run_v1235` (24) + §2.15 live: both ledgers reconcile to 0.00 |
| Reconciliation | **done** | `run_v1235` — the mutating path had never been tested despite v11.0 claiming coverage |
| Reporting accuracy | **done** | §2.15 — live integrity checks clean on both strategies, INC-001 signature absent |
| Failure isolation | **done** | E2E-15/16 (pricing seam genuinely reached), RESIL-1..4, concurrency RE-1..5 |
| Diagnostic coverage | **done** | cursor-sanity detector, `instrumentsSkipped`/`Configured`, completeness card |
| Future strategy inheritance | **done (analysis)** | §2.14 — the forward-coverage ledger is ALEX-only and would **not** be inherited; `scanAll` is unprotected so wiring it is not governance-blocked |
| **EUR_USD root cause** | **RESOLVED** | §2.10 — never starved; status-ring truncation bias |
| **Why ALEX trades rarely** | **ANSWERED** | §2.11 — suspension + entry-day dominate; corrected from the durable ledger |

### Why this closes YELLOW, not GREEN

Every scope item above is complete, and every defect found in my own work has been corrected and
re-verified. **Three trading-fidelity defects remain open, all blocked by the protected-function
contract rather than by engineering difficulty**, and one of them has a path to a real duplicate
paper trade. Declaring GREEN with a known, fixable trading-correctness defect outstanding would be
exactly the failure mode this milestone was created to prevent.

| # | Defect | Severity | Smallest governed change |
|---|---|---|---|
| 1 | **Signal identity not stable** — all four duplicate-trade guards can miss; a closed setup can re-open (§2.16) | **highest — path to a duplicate paper trade** | add an anchor-free `stableId` as a second OR-term in the duplicate check (§7.3) |
| 2 | **Status ring holds less than one cycle** — "PERMANENT, never reconsidered" is void for all 12 pairs; converts *reject, never chase* into chasing on D/W (§2.10) | high, currently unexercised (all live D/W setups pre-activation) | one numeric literal: cap 300 → 5000 (§7.2) |
| 3 | **JVM emits no candidate-level diagnostics** — rejections and dropped fills are unauditable (§7.1) | medium — observability, not correctness | one `emitDecisionEvent` before the existing `return` (§7.1) |

**What is required from Joe** — three decisions, not implementation work:

1. **Authorize the governed protected-function change for #1** (or direct otherwise). This is the
   only item that can produce a wrong trade. The change adds a guard term; it removes none.
2. **Rule on #2**, which is a frozen-strategy semantic question: raising the cap means setups
   currently re-decided every poll would be decided once, as the contract already states they
   should be.
3. **Rule on #3**, a governed change to `checkAutoTrades` purely to record a value it already
   computes.

Each would re-baseline the affected protected function, so drift-0 must be re-established against a
new baseline — which is the governance step, and is Joe's to authorize.

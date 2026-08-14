# MOGO-021 — Forward Trading Reliability & End-to-End Pipeline Validation

**Status:** IN PROGRESS · continuation of MOGO-020
**Gates:** canonical 24 suites 1,297/1,297 · platform 1,049/1,049 · ALEX protected drift 0
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

| Timeframe | Live setups | Extra trade attempts before the setup goes stale |
|---|---|---|
| H1 | 281 | ~0 — the 60-minute window matches the hourly cadence **by coincidence, not by design** |
| H4 | 89 | up to **3** |
| D | 11 | up to **23** |
| W | 2 | up to **167** |

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
| Those 8, evaluated against the H1 staleness limit | ages **1,501 / 1,621 / 2,161 / 2,581 minutes** vs `maxAgeMinutes: 60` |
| Result | all rejected `STATE_SIGNAL_STALE` |
| `tradedSignals` / closed positions / balance | **1** / **1** / **$9,900** (one −1R trade) |

So the funnel is: 383 setups → 375 rejected `CONFIG_BEFORE_ACTIVATION` (they pre-date activation) →
8 survive → all are 25–43 hours old against a one-bar-period limit → 0 new trades. The dominant
reason code in the live event log is `CONFIG_BEFORE_ACTIVATION` (335 of 500 events), with
`ALEX_ACTIVATION_CUTOFF` recorded `FAIL` 171 times and `STATE_SIGNAL_STALE` 8 times.

**This is the activation-cutoff rule doing its job.** `alexGRunSetupEngine` rebuilds 90 days of
history on every poll, so almost everything it finds is historical and must not be back-filled into
live trading. Nothing here indicates a pipeline failure — the pipeline is running the full chain
(rebuild → dedup → activation → staleness) on all 12 instruments every H1 boundary, and correctly
declining.

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

---

## 3. Gates

| Gate | Result |
|---|---|
| Canonical | **24 suites · 1,297 / 1,297 · 0 failures · 0 errors** |
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

Two further verifications ran after the redesign — one attacking the fail-closed detector, one
attempting to prove the new JVM positive control is non-discriminating by **deleting each gate from
a copy of `index.html`** and confirming the corresponding fixture then fails. Both returned further
findings against my work, all of which are fixed. Full results in §6.

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
| EUR_USD root cause | §2.10 | **RESOLVED** — never starved; a truncated 300-entry status ring made the front-of-scan-order pairs invisible in the durable ledger |
| `alexGLiveSetupStatuses` 300-entry FIFO vs its "PERMANENT, never reconsidered" contract (`index.html:4282` vs `4641`) | ALEX | **open, governance-blocked** — now with production proof (§2.10); smallest governed change in §7.2 |
| PIPELINE natural key omits the pair (`index.html:13039`), so two instruments failing in the same millisecond collide and one record is dropped as a duplicate | MOGO-020 carry-over | open |
| `instrumentsEvaluated` is pushed **before** the `await`, so it means "attempted" | naming | open |
| `alexGCheckLivePositions()` runs before the per-pair loop and is not individually guarded — a throw there aborts the whole tick | ALEX | open |
| No re-entrancy guard on `alexGLivePollTick` under `setInterval` | ALEX | open |
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
on H4, 23 on D, 167 on W. For `ENTRY_MOVED_TOO_FAR_FROM_SIGNAL` that converts the documented
*"rejecting — never chasing"* rule into chasing on the D and W timeframes. H1 is safe only because
the 60-minute staleness window happens to match the hourly poll cadence — a coincidence, not a
guard.

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

### 7.3 Standing constraints, all intact

PAPER ONLY · live-money **NOT AUTHORIZED** and no live-money gate touched · TJR **not**
paper-authorized and untouched (`status:'development'`, all four capabilities false) · ALEX
protected drift **0** (63 functions, 4 constants byte-identical) · JVM governed strategy integrity
preserved — every JVM function on the decision path is called as-is and none was modified.

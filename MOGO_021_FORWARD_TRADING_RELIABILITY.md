# MOGO-021 — Forward Trading Reliability & End-to-End Pipeline Validation

**Status:** IN PROGRESS · continuation of MOGO-020
**Gates:** canonical 24 suites 1,391/1,391 · platform 1,049/1,049 · ALEX protected drift 0 (v12.20.0 baseline)
**Started from:** `c443ed6` (MOGO-020 close-out)
**Last independent re-verification:** 2026-08-14, from scratch, after a forced session restart
**Governed remediation:** all four owner-authorized decisions IMPLEMENTED — see §9
**Paper trading only · live-money NOT AUTHORIZED · TJR paper NOT activated · ALEX frozen**

> **Line numbers in this report were corrected on 2026-08-14 and are accurate as of that tree.**
> Every `index.html:NNNN` pointer had drifted — offsets ranged from +25 to +239 because different
> sections were written against different revisions, and §2.2 and §7.1 carried two *different*
> wrong numbers for the same three lines. Pointers are now anchored to a function or statement name
> as well as a line, so the next drift is detectable rather than silent.

---

## ⚠️ Recovery note — 2026-08-14

An earlier session was terminated mid-verification because macOS required Terminal to restart for
Full Disk Access to take effect. **No verification result from that interrupted session is relied on
here.** Filesystem access was re-confirmed, repository state was reconstructed from git, and the
gates, the ALEX drift check, the JVM ledger, the identity-drift detector and the EUR_USD conclusion
were all re-established from scratch by independent adversarial verifiers.

That re-verification did not merely reconfirm the prior state. It found **a regression introduced by
`e778cec` itself** (§2.14a), a **silent evidence-loss defect** (§2.14b), and **four false or
overstated claims in this report** — including one governance blocker (§7.2) that does not exist.
All are recorded below. The earlier handoff-prompt note has been removed: a handoff arrived with
this recovery session and its scope is the scope executed.

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

1. `if(!result.fires)return;` — verdict and reason discarded (`index.html:16831`)
2. `if(pos.error){return;}` — explicitly commented *"skip silently, try again next cycle"* (`index.html:16836`)
3. the eligibility filter (`index.html:16818-16825`) — excluded pairs leave no trace

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
| `alexGIsSetupEligibleForLiveTrading` | `setup.qualificationTimestamp>=alexGAutoTrading.activatedAt` (`index.html:4567`) | a future-dated qualification **always passes** |
| `alexGIsSetupSignalStale` | `(nowMs-setup.qualificationTimestamp)/60000>maxAge` (`index.html:4579`) | age is negative → **never stale** |

So the guard's remedy for "this instrument's timestamps cannot be trusted" was "resume trading it",
at the exact moment the two gates that would catch a bad-timestamp setup both degenerate to
always-pass. Before the change the instrument was starved and opened nothing; after it, it could
open a trade on corrupt data. **That is a trade that would not otherwise happen.** It also
contradicted the in-repo precedent: the other data-integrity guard in the same function (short H1
dataset, `index.html:4626`) responds record-and-`return` — skip the instrument.

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

`alexGRecordLiveSetupStatus` (**PROTECTED**, `index.html:4308`):

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
(`statuses:` at `index.html:5213`). **So the `statuses` evidence structurally cannot contain
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

#### The remaining consequence is trading-relevant — and is NOT governance-blocked

> **Heading corrected 2026-08-14.** This was titled *"…and governance-blocked"*. It is not.
> `alexGRecordLiveSetupStatus` is protected, but it only *appends to a display array*; **the guard
> that decides whether a setup is reconsidered lives in the non-protected
> `alexGEvaluatePairForLiveSetups`** (`index.html:4729`). Only the narrow option of raising the `300`
> literal requires a protected edit, and that option is withdrawn (§7.2). What blocks this is a
> frozen-strategy *semantic* decision, not the protected-function contract.

The duplicate guard at `index.html:4729` is documented *"PERMANENT, never reconsidered"* but reads
that **same truncated ring**. For the evicted pairs the short-circuit cannot fire, so their setups
are re-evaluated on every poll rather than being decided once — measured at **≈53 re-decisions per
signalId** (398 distinct signalIds across 21,000 EVALUATION records).

A duplicate **trade** is still prevented *by this path*: `alexGConstructLivePosition`
(`index.html:4328`) checks `alexGAutoTrading.tradedSignals` (persisted, unbounded) plus open/closed
positions and journal entries. The real deviation here is narrower: a setup blocked for a
**transient** reason can be retried on a later poll, contrary to the documented finality — bounded
by the staleness gate, since `signalAgeMinutesAtEvaluation` is measured from `qualificationTimestamp`
and grows with the clock (one bar-period: H1 60 min).

> **⚠️ "A duplicate trade is still prevented" is true only of *this* mechanism.** It is falsified in
> general by §2.16 — every one of those guards keys on an identity that drifts — and §2.17 reproduces
> a second real paper position end-to-end. Read this paragraph as scoped to the status-ring defect,
> not as a statement that duplicate trades cannot occur.

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

The sharpest case is `ENTRY_MOVED_TOO_FAR_FROM_SIGNAL` (`index.html:4359`). The v4.2 contract is
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
  (`index.html:8934-8942`), setting `evaluationSuppressed` when they diverge.
* **The divergence is operator-visible.** `renderMarketDataCompletenessDiagnostics`
  (`index.html:6139`) renders an amber card naming every pair whose history was too short to
  evaluate, with requested/received counts and the pagination reason. It is called from `scanAll`
  (`index.html:9022`) inside a `try/catch` so an indicator can never break a scan, and it is
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

`startAlexGLivePollingIfNeeded` (`index.html:5099`) is guarded against creating a second interval,
so this is overlap of a long-running tick with the next interval firing, not a duplicate timer.
There is **no re-entrancy guard** on the tick itself.

Rather than speculate about the risk, it was exercised: two ticks launched concurrently against a
setup that does open a trade. Result — **exactly one position, one journal entry, one
`tradedSignals` entry, one `TRADE_OPENED`, and uncorrupted setup state**, with both ticks
confirmed to have genuinely run (`SCAN_STARTED` = 2).

**Correction to my attribution.** I credited `alexGConstructLivePosition`'s identity checks. That is
wrong, and mutation testing shows it: with all five identity-keyed guards disabled the fixtures
still pass. The guard that actually holds under concurrency is the **pair+timeframe overlap rule**
(`index.html:4429`) — removing *that* produces two open positions. RE-6 now asserts the correct
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

It was **not governance-blocked** — `scanAll` and the whole evidence platform are unprotected — but
it was not a one-line call either: `evidenceObservationBase` hard-coded `strategyId` from
`RULES_ALEXG.ruleVersion`, so recording a JVM poll through it would have **mislabelled JVM evidence
as ALEX**, which is worse than having none.

**Now implemented**, in three additive steps, none touching protected code:

1. `evidenceObservationBase` takes an **optional** `strategyId`. Omitted, it resolves exactly as
   before — **JVMOBS-6** asserts an ALEX-shaped record still resolves to `alex_g_sr_v1`, because
   this was the change carrying real regression risk: a mistake here would have corrupted ALEX's
   forward ledger, the very evidence that settled §2.10.
2. `evidenceBuildPollObservation` threads it through.
3. `scanAll` records a JVM poll observation in a **`finally`** — a ledger that only remembers
   successful scans hides exactly the gaps it exists to expose.

Proven by **JVMOBS-1..11**: the observation is recorded (`kind: POLL`), labelled `current_strategy`
and **not** ALEX's ruleVersion, covers the scanned universe while recording that only 12 of 35 are
tradeable, carries the real outcome and auto-trading state, and — **JVMOBS-5** — a *failed* scan is
still recorded with `outcome: ERROR` **while the original error still propagates unchanged**.

#### Two defects in my first version, both making the ledger actively misleading

**It reported stale coverage, and lied hardest on exactly the scan it exists to catch.**
`instrumentsEvaluated` was derived from `pairData`, which **persists between scans**. Ordinary fetch
failures were fine (`fetchCandles` returns null, so `scanPair` still writes `candles: null`), but a
sweep that *aborts* leaves unreached pairs holding the previous scan's data. Measured: an aborted
scan claimed **35/35 coverage for 25 instruments it never touched**, with `instrumentsSkipped`
empty and `evaluationAdvanced: true` — precisely the "silently unscanned instrument is
indistinguishable from a scanned one" signature this ledger was built to end.

**My first fix for this was itself incomplete, and verification proved it with real concurrency.**
I reference-diffed `pairData` across the sweep. But reference inequality proves *someone* rewrote
an entry, not that *this sweep* did — and `scanAll` has no re-entrancy guard and is invoked
unawaited from three places, including `setTf()` on a single operator click. With one sweep's fetch
held open and a second run to completion, the aborted sweep reported **`evaluated 35, skipped 0,
evaluationAdvanced true`** — field for field the original defect, reproduced against my own fix.

> **⚠️ The paragraph below describes `e778cec` as shipped, and BOTH of its claims were subsequently
> refuted. It is retained as the record of what that commit did; do not cite it. See §2.14a for what
> replaced it.** The token-stamped-into-`pairData` scheme still read shared state after the fact and
> produced a *worse* failure than the one it fixed; and the "credited exactly once, combined 35/35"
> property is not a property this system has or should have — two overlapping complete sweeps
> legitimately report 35 each.

Coverage is now attributed **per sweep**: `scanAll` takes a monotonic `sweepToken`, passes it to
`scanPair`, which stamps it into the `pairData` entry it writes, and the ledger counts only entries
carrying its own token. `instrumentsAttempted` is the true dispatch list rather than a count of
writes. **JVMOBS-12** asserts the property directly: across two overlapping sweeps every instrument
is credited **exactly once** — combined `35/35`, zero double-credits, where object-identity diffing
produced 70.

The predicate is also now **fail-closed**: evaluation requires `completenessState === COMPLETE`
rather than the absence of a flag, so an entry written by any future second writer of `pairData`
reads as *not evaluated* rather than silently restoring 35/35 over-reporting. And a **transport
failure is no longer labelled as a contract suppression** — `MARKET_DATA_UNAVAILABLE` and
`EVALUATION_SUPPRESSED_INCOMPLETE_DATA` are distinct, with `completenessState` recorded alongside
(**JVMOBS-14/15**), restoring the information the original `NO_CANDLES_THIS_SCAN` carried.

**JVMOBS-7/8 now pin exact numbers** — 10 evaluated, 25 `NOT_REACHED_THIS_SCAN`. The earlier
`evaluated > 0 && evaluated < 35` range passed for any partial value, and let both an off-by-one
and a whole lost chunk through under mutation.

**It counted instruments the strategy had explicitly refused to evaluate.** `pairData[p].candles` is
truthy for `[]`, and ADR-011 deliberately suppresses evaluation for anything short of `COMPLETE`,
recording that as `evaluationSuppressed` in the same object. The ledger ignored it — the app said
"not evaluated" while the ledger said "evaluated". The predicate now honours the completeness
contract, and **JVMOBS-10** asserts a suppressed instrument is reported skipped with
`EVALUATION_SUPPRESSED_INCOMPLETE_DATA`.

Two smaller corrections from the same pass: `evidenceObservationBase` accepted `""`/`false`/`0` as a
strategy identity (only a non-empty string overrides now), and the POLL natural key carried no
strategy component. The key now includes `strategyId`, and the existing contract fixture **L7** was
updated to match, deliberately, rather than the change being hidden.

*Rationale corrected:* I justified this as closing a cross-tab collision where two tabs mint the
same `tickId`. That overstated it — `generateDecisionEventId` already embeds a millisecond
timestamp *and* a counter, so the collision needs both to coincide. The change is reasonable
namespacing now that two strategies write POLL records, but it was sold on a hazard the id format
had largely closed, and it cost key-format continuity with ~3,250 existing durable rows. Verified
harmless: `naturalKey` is never used as a lookup anywhere (`evidenceListObservations` is `getAll`,
retention reads the `bySeq` index and deletes by `observationId`), old and new key shapes cannot
collide, and no ALEX **record body** changed — only the POLL key.

One fixture of mine had to be corrected as a result: **JVM-28** asserted every event on a sweep is
sourced to `scanAll`, which stopped being true once the observation write began emitting
evidence-platform `DATA_UNAVAILABLE` events in the offline harness. It now scopes to
**strategy-sourced** events, which is what the claim was always about — storage availability is not
the JVM decision path.

**JVM now has forward-coverage parity with ALEX**, and a future paper-authorized strategy inherits
the mechanism rather than the gap.

### 2.14a 🔴 `e778cec` introduced a REGRESSION — a successful sweep reporting a total outage

**Found by independent re-verification on 2026-08-14, against the commit that claimed to have fixed
this exact class of defect.** This is the third version of the JVM coverage ledger, and the second
one refuted under concurrency.

`e778cec` stamped a monotonic `sweepToken` into `pairData[pair]` and, in `scanAll`'s `finally`,
counted the entries whose token matched. That is still reading **shared** state after the fact, and
`pairData[pair]` is a **single slot per instrument** — whichever sweep writes last owns it. So the
count measures the *last writer*, not *this sweep*:

| Interleaving | What `e778cec` reported |
|---|---|
| Sweep A writes all 35, then sits in its post-chunk work (`await checkAutoTrades()` / `runManualReviewScan()`, both real network I/O) while sweep B overwrites `pairData` and finishes first | A reports **`instrumentsEvaluated: []`, `evaluationAdvanced: false`, 35 × `DISPATCHED_NO_RESULT`** — a fabricated total outage on a sweep that did everything right |
| A held mid-fetch, released, overtaken by B; both complete | instruments double-credited across the two records |

The first row is the serious one: it manufactures precisely the phantom-starvation signature that
cost four investigations, and the *pre-`e778cec`* code reported that case correctly. It was a
regression, not a residual gap.

**Root cause, stated plainly: attribution was being READ BACK OUT of shared state instead of being
RECORDED AT WRITE TIME.** Both refuted designs share that single mistake — object-identity diffing
and token-counting are two ways of asking shared state a question only the writer can answer.

**Fixed properly — sweep-local attribution.** `scanPair` (not protected, exactly one call site) now
takes a third argument: the caller's own results object. It records `sweepResults[pair] =
completenessState` at the moment the outcome is produced, immediately after the `pairData` write and
*before* the alert block, so an alerting failure cannot lose a genuine evaluation. `scanAll` creates
one `Object.create(null)` per invocation and derives evaluated / skipped / attempted entirely from
it. No other sweep can reach that object, so the result is **interleaving-independent by
construction** rather than by argument. Each poll record now answers exactly one question honestly:
*which instruments did THIS sweep evaluate?*

The `sweepToken` field is still stamped into `pairData` but is now **diagnostic only** — it records
which sweep last wrote an entry, and no ledger arithmetic reads it.

**The invariant `e778cec` asserted was itself wrong.** JVMOBS-12 claimed that across two overlapping
sweeps every instrument is credited *exactly once*, combined 35/35. Overlapping sweeps do not
partition the instrument universe — each independently scans all 35, so two complete sweeps
legitimately report **35 each**. "Combined 35" held only for one particular interleaving; other
interleavings of the same code produced 66 and 0. JVMOBS-12 has been rewritten to assert the property
that actually matters: **per-sweep honesty**.

**Coverage.** JVMOBS-16/17 (the overtaken sweep), rewritten JVMOBS-12 (overlap), JVMOBS-18/18a
(`DISPATCHED_NO_RESULT` vs a rejected fetch), JVMOBS-19 (`instrumentsAttempted` is the dispatch
list). Three of `e778cec`'s own changes had shipped with **zero** coverage — reverting them survived
both gates — and two of those are now pinned. Mutation matrix, every mutation byte-diff proven
applied before its suite ran:

| Mutation | Fixtures killed |
|---|---|
| revert the `finally` to reading `pairData` + token (the `e778cec` form) | JVMOBS-12, 16, 17 |
| `instrumentsAttempted` → write count (its pre-MOGO-021 meaning) | JVMOBS-19 |
| delete the `DISPATCHED_NO_RESULT` branch | JVMOBS-18 |

**A reachability finding, reported rather than papered over.** `DISPATCHED_NO_RESULT` cannot be
reached through the I/O layer at all: `fetchCandles` and `fetchPrice` both end in `catch{return
null;}` — probed with six failure shapes, neither function ever rejects — so a rejected request
becomes a null dataset and the instrument *is* written, as `UNAVAILABLE`. JVMOBS-18a pins exactly
that. **But the branch is live, not merely defensive**, which I first understated: verification
reached it through the **real, unstubbed** `scanPair` by making the protected `bestConfluence` throw,
and it also fires for an instrument that never threw at all — a sibling still in flight when its own
sweep aborts mid-chunk.

**One residual inaccuracy, disclosed rather than implied away.** If a sweep aborts while its own
`scanPair` promises are still in flight, the `finally` emits before those writes land, so a sibling
that later succeeds is reported `DISPATCHED_NO_RESULT` while `pairData` does end up holding its fresh
data — the ledger under-reports its own coverage. Measured in 7 of 175 fuzz records. It is
**fail-closed** (it never claims work it did not do) and is **identically present in `e778cec` and in
the original identity-diffing version**, so it is not a regression — but it is a real inaccuracy and
is recorded here and in the code rather than left to be rediscovered.

**Independent verification of this fix.** An adversarial verifier built an exact write-time oracle
(a `Proxy` on the sink, recording every write at the instant it happened, tagged with the token
`scanPair` was actually called with) and ran a **60-trial randomized fuzz** — 2–4 concurrent sweeps,
random gated pair, short-history pair, transport-failure pair, evaluator throw, abort point 1–12,
parking in `checkAutoTrades` and `runManualReviewScan`, and `scanAll` re-entered from *inside*
`checkAutoTrades`. Result: **175 records checked, 0 violations.** The fuzzer is not vacuous — the
same fuzz against the reverted `e778cec` `finally` produces **3,401 violations**, the first being
exactly the refuted defect (`ledger=[] oracle=[all 35]`). Eight deterministic single-sweep scenarios
were also diffed against `e778cec` and are **byte-identical**, so nothing that previously worked
changed.

### 2.14b Silent evidence loss — the PIPELINE natural key could not name the instrument

Found while reconciling this report against the tree. `evidenceObservationNaturalKey`
(`index.html:13291`, not protected) built the PIPELINE key as
`PIPE|<stage>|<sourceTradeId||tradeId||setupId>|<occurredAt>`. **Not every stage has any of those
three.** `alexGRecordPipelineStage('DATA_INSUFFICIENT', …)` (`index.html:4626`) is recorded *before*
any setup exists and supplies none of them, so its key collapsed to
`PIPE|DATA_INSUFFICIENT||<occurredAt>` — **byte-identical for every instrument**.

Two pairs failing the H1 history check in the same millisecond therefore minted the same key; the
UNIQUE `naturalKey` index rejected the second; and `evidencePutObservation` classifies a CONSTRAINT
error as `{ok:true, duplicate:true}`. **The observation was dropped silently and reported as a
success** — and it is precisely the record that says *which* instrument was skipped, the question
this ledger exists to answer.

**Fixed** by including `pair` and `timeframe`, both already on the record — no new state is stored.
Adding a component can only ever *split* keys apart, never merge two distinct observations, so it
cannot cause a new silent drop; a genuine duplicate (same pair, same stage, same instant) still
collapses as before. Six fixtures (2A.48–2A.53); reverting the key kills 2A.48, 2A.49 and 2A.51, and
the collision is visible in the failure output as two identical keys. 2A.50/52/53 are deliberately
controls that survive both ways.

*Scope note:* this changes the key shape, so a PIPELINE record written before the fix and one
written after would not dedup against each other. That is acceptable and bounded — `naturalKey` is
**never** used as a lookup (verified: the `byNaturalKey` index is created and never read; nothing
anywhere reads `naturalKey` except the writer), and these are point-in-time events with distinct
`occurredAt` values.

### 2.16 🔴 SIGNAL IDENTITY IS NOT STABLE — every duplicate-trade guard can miss

**This is the most serious defect found in the milestone, it was found by verification rather than
by me, and it falsifies a safety claim I made in §2.10.**

I wrote that a duplicate trade is prevented because `alexGConstructLivePosition` (`index.html:4328`)
checks `tradedSignals`, open positions, closed positions and journal entries. **All four key on
`signalId`, and `signalId` is not stable across rebuilds.**

`alexGLiveSignalId` (`index.html:4299`) embeds `setup.setupId`, which embeds the `zoneId`, which
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
right now, on the only trade the campaign has made.** The ring dedup at `index.html:4729` keys on
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

* **There is a FIFTH guard, and it drifts identically.** `index.html:4386` keys on
  `tradeId = AGT|setupId`, and `setupId` embeds the same `zoneId`. It is load-bearing *today* —
  with the four `signalId` guards disabled but this one intact, the re-open is still blocked — so
  any fix that covers only `signalId` leaves the defect half-repaired.
* **One of the "four" guards is dead code and always has been.** `alexGJournalEntries.some(e =>
  e.signalId === signalId)` (`index.html:4331`) can never fire: `buildAlexJournalOpenRecord`
  (`index.html:2341`) never writes a `signalId` field, and live production confirms
  `alexGJournalEntries[0].signalId === undefined`. It is **three** live identity guards plus one
  that has never fired — independent of drift.

**Correction to the mechanism label:** the rebuild window is not "90 days".
`fetchAlexGReplayDatasets` (`index.html:4052`) requests a fixed **count** — `days*24+60 = 2220` H1
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

> **⚠️ It is observing nothing yet.** Verified directly over CDP: the running tab has no
> `alexGStableSetupIdentity`, and neither `STATE_SIGNAL_IDENTITY_DRIFTED` nor
> `STATE_CURSOR_AHEAD_OF_CLOCK` exists in its registry — it predates all of this milestone's
> diagnostics. **The tab must be reloaded before any of these detectors measure anything**, and a
> reload costs re-entering broker credentials (MOGO-013). That is an operator action, and it is now
> the single thing standing between these detectors and real production evidence.

**DRIFT-1..9 (`run_v1236`) include a regression proof of the defect itself.** DRIFT-6 drives the
full production path with every persisted record carrying the pre-drift identity and the
freshly-derived setup carrying the new one, and the result is **one economic setup, two open/closed
positions**. Independent verification reproduced the same outcome **organically** — rolling the
candle window with every guard intact, no hand-edited records — so it is not a fixture artifact.
That fixture is expected to invert when the governed fix in §7.3 lands, at which point it becomes
the proof the fix works.

**Calibration — REWRITTEN 2026-08-14. The original was wrong, and so was my first correction of it.**

The original text read *"Drift takes roughly 128 days to arrive, by which time
`alexGIsSetupSignalStale` normally rejects the setup. So this is a narrow coincidence."* **128 days
is the WINDOW, not the DELAY.** A cluster re-anchors when its **first reaction** falls into the oldest
`atrPeriod` (14) bars of the fixed-count window — `calcATR` returns `null` below 15 bars and
`qualifies = atr && …` then fails — so the delay after qualification is
`windowBars − 14 − ageOfFirstReactionAtQualification`, i.e. anything in `[1, windowBars−14]`, set by
how old the zone already was when it qualified rather than by elapsed time since the trade. Measured
against the frozen engine, the law holds exactly: A = 143 → k = 43; A = 73 → k = 113; A = 63 →
k = 123. The traded AUD_JPY setup proves it in production — its cluster's first reaction was already
**126.2 days old at qualification** against a ~128-day usable H1 window, and the re-anchor was first
evaluated **1.7 days** later. Confirmed live: the campaign's oldest surviving H1 reaction is
`2026-04-08T16:00Z`, fifteen hours *after* that setup's original anchor.

**My first correction then over-reacted, and verification refuted it.** I proposed that this made
drift "a per-trade lottery on every trade" of roughly `staleness / window` — ~1.4% on W, 43× H1.
**That model is wrong in kind, not just in its arithmetic.** `maxLiveSignalAgeMinutes` is *exactly*
one bar-period on every timeframe (60/240/1440/10080), a pair is re-evaluated *exactly* once per H1
boundary, and a fixed-**count** window can only roll when a new bar of that timeframe closes — so the
first poll that can see a rolled window sits one whole bar-period **plus poll latency** after
qualification. **A whole-bar roll is structurally incapable of landing inside the staleness window.**
Proven end-to-end: a genuine daily `B_breakRetest` traded, then rolled by exactly one bar, is
rejected `IGNORED — STALE SIGNAL` at age 1440.5 min. And the distribution is skewed young, not
uniform — across 388 live setups the first-reaction age is a median **9.8%** of the window, and
**zero of 388 are in the band where a whole-bar roll could land inside staleness**.

**🔴 But a second real paper position DOES open — by a mechanism neither account identified.**
The exposure is not whole-bar rolls. It is **any window-start movement that is NOT a whole-bar
roll** — a changed candle count, a short broker page, a retroactively backfilled bar — because that
re-anchors the identity at an arbitrary moment *inside* the staleness window. Verified against
pristine `index.html` with **zero guards and zero config mutated**, as a positive/negative control
pair differing only in two daily candles:

| Poll 2, four hours after the trade | Identity | Age | Outcome | Final state |
|---|---|---|---|---|
| broker returns **148** daily candles instead of 150 | drifted | 240.5 min | **TRADE OPENED** | `open=1 closed=1 journal=2 tradedSignals=2` |
| control — full 150-bar fetch | stable | 240.5 min | `DUPLICATE` blocked | `open=0 closed=1 journal=1 tradedSignals=1` |

In the first row **all five identity guards miss** (`tradeId` drifts too) and the drift detector
fires once and blocks nothing.

**What actually prevents a duplicate today is not a guard.** It is (a) the arithmetic equality
`maxLiveSignalAgeMinutes[tf] == one bar-period`, whose entire margin is the poll latency — measured
at 63–70 s in production, and a zero-latency poll opens the trade — and (b) `ALEX_V11_ENTRY_DAY`, a
**config flag that fails open**. Neither is a structural guarantee. At-risk polls per traded setup,
where an off-boundary shift can drift the identity while the setup is still fresh: **H1 0, H4 3,
D 23, W 167** (up to 72 entry-day-eligible on W).

**The unguarded surface is specific and is in NON-protected code.**
`alexGEvaluatePairForLiveSetups` length-checks **only** `datasets.H1 (< 60)`. **H4, D and W have no
length or completeness check at all**, and `fetchCandlesRange` classifies a short single page as
`RAW_COUNT_SHORT → COMPLETE`. That is exactly the input above, and today it is invisible.

**A third drift trigger was found, and it defeats the proposed §7.3 fix.** `getCandleCloseTime`
returns the next bar's start once one exists but an **estimate** while the bar is newest. For the
last bar of a trading week that close time moves by **48 hours** when the market reopens — changing
`qualificationTimestamp` *and* `reactionId`, which are **two of the five components** the proposed
anchor-free `stableId` depends on. This happens **every weekend**, not once per window. An anchor-free
identity is therefore necessary but **not sufficient**; the key must derive from the anchor bar's own
*start* time rather than its computed close.

**Net effect on severity.** Not raised as a *rate* — my "~1.4% of every trade" is not defensible.
Not lowered as a *fact* — a second real paper position opens end-to-end under pristine production
config. What changes is the framing: **the duplicate guards are unconditionally broken, and what
stands between that and a wrong trade is an arithmetic coincidence plus a config flag.**

**Verified observation-only, four independent ways.** The detector was removed surgically and the
entire 24-suite run compared: the only deltas are the DRIFT fixtures themselves. Hooking both event
sinks and diffing an identical scenario with and without the detector gives an **identical pipeline
stream, an identical `alexGRecordLiveSetupStatus` stream, and a byte-identical final account,
journal and `tradedSignals` state**. Forcing the identity function — or `alexGTradeId`, or the
journal scan — to throw on every setup fails only the DRIFT fixtures.

> **⚠️ That last sentence is FALSE at the current tree, and was not re-checked after round 2.**
> Re-verification measured it: forcing `alexGStableSetupIdentity` to throw globally gives
> **0 PASS / 38 FAIL with `EXECUTION ERROR: forced identity failure`**, because DRIFT-11 — added in
> `39ba786` — calls that function directly at fixture scope, so a global throw aborts the harness
> rather than failing a subset. The claim was true when written (at `322f2da`) and went stale.
> **The underlying safety property still holds and was re-proved independently:** throwing at the
> detector's own call site leaves the trading outcome byte-identical. It is the "only the DRIFT
> fixtures" wording that is wrong, not the observation-only guarantee.

*Precision correction:* I first wrote that both sinks are identical. The **decision bus is not** —
118 vs 116 non-drift events. The extra durable observation triggers one more evidence-store write
attempt, and with IndexedDB absent in the offline harness that produces two `DATA_UNAVAILABLE`
events. No trading path reads them (`recordAlexGEngineError` is a bounded display-only array with
no circuit breaker), but the claim as first stated was too strong.

**Blind spot narrowed — but the INC-001 attribution was wrong, and one blind spot SURVIVES.**
The first version scanned only `alexGAccount` positions; it now also scans `alexGJournalEntries`
(matched on `tradeId`, since journal records carry no `signalId`), and **DRIFT-9** proves detection
from the journal alone. Two corrections, both from re-verification that drove `loadAlexGSaved` for
real across eight partial-state combinations:

* **The INC-001 framing is FALSE.** This section claimed an *unreadable* `fxhub_alexg_account` key
  leaves positions empty while journal and `tradedSignals` survive, and that "verification
  demonstrated a second real position opening with zero drift events". **That state cannot produce a
  second position at all.** `saveAlexGAccountGuarded` (`index.html:2866`) blocks *every* commit when
  a present-but-unreadable key is detected — the open is rolled back as `LOAD_INTEGRITY_BLOCKED`.
  Measured: account-unreadable → drift detected 1, second position **0**; journal-unreadable → drift
  1, second position **0**. What DRIFT-9/9b actually model is the *key-removed* state, not the
  INC-001 present-but-unreadable state. The fixtures are sound; the label on them was not.
* **🔴 A real blind spot survives.** With positions **and** journal both absent but
  `fxhub_alexg_auto` intact — so `tradedSignals` is populated and nothing else is — the detector's
  round-2 cheap exit returns immediately and emits **zero drift events**, while the guards still
  miss because `tradedSignals` is keyed on the drifted `signalId`. Measured: **drift events 0,
  second position 1 — opened unobserved.** This is the same failure class this paragraph claims to
  have closed, and it is recorded in the open-items table rather than quietly fixed, because it is
  a detector change that deserves its own verification pass.

**Three of my own fixtures could not fail, and were fixed.** DRIFT-5's second poll evaluated zero
instruments — the cursor gate skipped every pair — so it passed with the latch permanently
disabled. DRIFT-8 ran against an empty account, so a degenerate identity returning a constant
survived. DRIFT-4 asserted only `reason`, so `stage` and `sourceTradeId` could be stripped
silently. All three now die to the mutation that breaks what they name. *(Precision: the `stage`
and `sourceTradeId` mutations also kill ~18 unrelated fixtures, because
`evidenceBuildPipelineObservation` is shared by every pipeline stage — so "each kills exactly its
own fixture" is true of the detector mutations, not of those two.)*

**🔴 And the whole DRIFT suite could not fail either — the worst test defect in this milestone.**
Found by re-verification on 2026-08-14. Every DRIFT fixture faked drift by **string-prefixing** the
stored `signalId`/`tradeId` (`"AGL|DRIFTED|"+…`) while leaving the stored **`zoneId` unchanged** —
which a real re-anchor never does. The consequence, measured: append `,x.zoneId` to
`alexGStableSetupIdentity` — making the "stable" identity drift along with the zone, i.e. destroying
the detector's entire reason to exist — and **all 38 fixtures still passed**. Against a real
re-anchor that same mutant reports **zero drift events at the exact moment a second position opens.**
The suite could not distinguish a working detector from a blind one.

**Closed.** Eight fixtures added (DRIFT-12a, 12, 12b, 13, 14, 15, 16, 17) built on an **organic**
re-anchor: six real swing-low touches with the first anchored at bar 14 — the earliest bar at which
the frozen confirmation path can accept a reaction, since it calls `calcATR(…,14)` — so dropping the
two oldest H1 candles makes the **frozen engine itself** unable to confirm that touch, the cluster
re-anchors on the second, and the zone validates later. Different `clusterId` *and* different
`validatedAtCloseTimeMs` → genuinely different `zoneId`, while `reactionId` and
`qualificationTimestamp` do not move. **The only intervention between the two polls is the candle
window rolling forward** — no stored record hand-edited, no guard mutated.

| Mutation (each proven applied) | Old suite (38) | New suite (46) |
|---|---|---|
| `,x.zoneId` appended to the stable identity | **38/38 PASS — blind** | **3 die** (DRIFT-12 `events=0`, 14, 15) |
| drop `reactionId` | **38/38 PASS — blind** | 2 die (15, 16) |
| drop `qualificationTimestamp` | **38/38 PASS — blind** | 2 die (15, 17) |
| remove `j.tradeId!==currentTradeId` | DRIFT-1b **survives** | **DRIFT-1b dies** |

DRIFT-1b was also vacuous for its stated purpose and only *appeared* to pass: a false positive in an
earlier fixture latched `(stableId, signalId)` and suppressed the condition it was meant to test.
Resetting the latch before its own poll — one line — makes it discriminate. And a fixture-level
positive control was run for the new block: with `index.html` pristine and only the window roll
removed, DRIFT-12/12b/13/14 all fail, so none of them passes for an unrelated reason.

**The latch-order fix was itself a no-op, and is now real.** I reordered the mark to after the emit
and claimed that stopped a rejected event from suppressing the condition. It did not:
`emitDecisionEvent` never throws — it returns `{ok:false}` — and I never inspected the return, so a
rejected event still latched. Verification measured exactly that. The detector now checks the
result, and forcing the bus to reject this reason code gives **`latchSize = 0` with the durable row
still written** (it measured 1 before). The latch also keys on `(stableId, signalId)`, so a second
re-anchor to a third identity is still reported.

**DRIFT-9 was weaker than its name and is now faithful.** It rewrote only the stored journal
`tradeId`, leaving `tradedSignals` matching — so it proved detection but not that the guards miss.
Every recorded identity is now re-anchored, and **DRIFT-9b** asserts what follows: in that state a
**second position does open**. **DRIFT-1b** was added as the false-positive guard — re-evaluating a
normally-traded setup, with its own journal entry present, must report zero drift. That is the
fixture that would catch a `tradeId` derivation mismatch, and it is the likeliest way the journal
scan could have gone wrong.

**Performance.** The scan runs for every non-latched setup on every poll and stays unlatched in the
common no-drift case, so it now exits immediately when there is nothing to have drifted from —
no allocation, no scan.

---

## 3. Gates

Re-established from scratch on 2026-08-14 after the forced session restart — not carried over from
the interrupted session.

| Gate | Result |
|---|---|
| Canonical | **24 suites · 1,354 / 1,354 · 0 failures · 0 execution errors** (1,335 at `e778cec`; +11 from §2.14a/§2.14b, +8 from the organic drift fixtures in §2.17) |
| Platform | **25 suites · 1,049 / 1,049** · 0 failures, 0 errors, 0 skipped |
| Protected ALEX drift | **0** — 63 functions, 4 constants, byte-identical; known-good hash match True |
| Campaign C1 | intact — live campaign untouched, never reloaded |

**A gate caveat worth stating.** All three gates were green at `e778cec` too, and `e778cec` shipped a
regression (§2.14a). Green gates are a floor, not evidence of correctness: every defect found this
session was found by adversarial mutation against a passing suite, not by the suite itself.

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

| 7 | `e778cec`'s JVM ledger, re-verified from scratch after the restart | **REGRESSION FOUND IN THE FIX ITSELF** — a successful 35-instrument sweep reports a total outage (§2.14a); three of that commit's changes had zero coverage; its mutation matrix's first row was false |
| 8 | the EUR_USD conclusion and the status ring | the mechanism is upheld, but **the asymmetry it was invoked to explain does not exist** — GBP/USD is scan index 0 and EUR/USD index 1, both evicted, both measured at 72 evaluations; and **§7.2's governance blocker is refuted** — the guard is in non-protected code |
| 9 | the identity-drift detector | **the DRIFT fixtures cannot tell a working detector from a blind one** — an identity mutated to include `zoneId` passes all 38; a surviving blind spot; §2.17's INC-001 attribution is false |
| 10 | the reload-cost assumption, unverified across two milestones | credentials claim **upheld and understated**; §5's EUR_USD hypothesis refuted from live state; §7.1's "new reason code" cost is false |
| 11 | my own corrected drift calibration | **my correction was itself refuted** — the per-trade-lottery model is wrong in kind. But verification then found a **second real paper position opening end-to-end** via a short broker page (§2.17, §7.4) |

**Twenty-three distinct defects in my own work were found by verification rather than by me** —
including, in this recovery session, a regression inside the commit that claimed to fix that very
class of defect, and a live path to a duplicate paper trade that neither the report nor my own
correction had identified. Every one was reproduced independently before being accepted, and every
fixture fix was mutation-tested to confirm it now fails when the thing it tests is broken.

**Two rounds refuted work I had just written, and one refuted a correction I had just made.** That is
the system behaving as intended, and it is the reason this report should be read as a record of
what survived falsification rather than a record of what I believed.

The method that made the difference was granting verifiers authority to **mutate a copy of the
codebase** rather than only read it. Four separate vacuous fixtures of mine passed review and died
only to mutation.

**Corrections to earlier reporting**, both surfaced by verification:

* "JVM emits zero decision events" is imprecise. `checkAutoTrades` is called from `scanAll`, which
  does emit `SCAN_STARTED` / `SCAN_COMPLETED` / `ENGINE_ERROR`. The accurate statement is that JVM
  emits **no candidate-, rule- or rejection-level events of its own**.
* The `evaluateLiveTrigger` rejection reasons are **free-form English strings**, not registry
  codes, and one is interpolated (`` `R:R only ${ratio}:1` ``). Calling them "structured" overstated
  it; they also do reach a human today via the chart's live-trigger badge (`index.html:10513`),
  just never a durable record.
* The `c443ed6` commit message said "20 fixtures in this suite"; the file contained 23.

---

## 5. Carried forward from MOGO-020

> **⚠️ These three bullets were STALE and are corrected below.** The first two still asserted the
> MOGO-020 reading that §2.10 had already refuted, and the third named a governance blocker that does
> not exist. All three were caught by independent re-verification on 2026-08-14, and all three were
> wrong in the direction of *understating* what is fixable without authorization.

* **EUR_USD — RESOLVED, never starved (§2.10).** The MOGO-020 reading of "0 poll appearances, 0
  evaluations" had no basis in the data. Measured from the durable ledger over **3,719 polls / 79
  advancing polls** (2026-08-11 → 2026-08-14), `instrumentsEvaluated` is **EUR_USD 72, GBP_USD 72** —
  identical, and in line with all twelve (range 72–79). The cursor-ahead hypothesis is refuted in
  production: all 12 cursors sit **exactly at** the current H1 boundary (`aheadMs = 0` for every
  one), with 0 cursor-ahead conditions, 0 fetch failures and 0 engine errors recorded.
* **GBP_USD — the "~54 vs 0" asymmetry does not exist.** This is the correction that matters, and it
  inverts the original reasoning. `SCAN_PAIRS` puts **GBP/USD at index 0 and EUR/USD at index 1** —
  so the 300-entry ring evicts **both** before a 388-setup cycle finishes, and the durable `statuses`
  evidence contains **0 records for either**. The ring artifact explains why both are invisible; it
  explains **no asymmetry whatsoever**, because there is none to explain. Any account that uses the
  ring to explain "EUR_USD 0 vs GBP_USD 54" is incoherent. The one real gradient — 72 evaluations at
  the front of scan order rising to 79 at the back — runs **toward** the late pairs and is
  attributable to overlapping poll ticks (§2.13), which is the opposite of starvation.
* **Dedup contract defect — still open, and the stated blocker was WRONG.** The claim *"correct fix
  needs the protected `alexGRecordLiveSetupStatus`"* is **refuted**. That protected function's only
  job is to append to a display array; **the duplicate guard already lives in the NON-protected
  `alexGEvaluatePairForLiveSetups`** (`index.html:4729`). The corrective change therefore needs
  **zero protected-function edits**. Measured severity: 398 distinct signalIds across 21,000
  EVALUATION records — **≈53 re-decisions per signalId**, up to 70 distinct decision instants for a
  single signal. See §7.2, which is rewritten accordingly.
* **Observation continuity** — 84.5% over the audited span, 12 gaps >10 min, one confirmed runtime
  restart. Operational.

### Open items raised by verification, not yet addressed

| Item | Where | Status |
|---|---|---|
| 🔴 **Signal identity not stable — every duplicate-trade guard can miss** | §2.16 / §7.3 | **open, governance-blocked** — a second real paper position was reproduced end-to-end with zero guards mutated (§2.17) |
| 🔴 **No length/completeness check on `datasets.H4`, `D` or `W`** (`alexGEvaluatePairForLiveSetups`; only H1 is checked, `< 60`). A short broker page shifts the window off a bar boundary, re-anchors the identity *inside* the staleness window, and opens a duplicate | §2.17 | **OPEN — in NON-protected code, but every candidate fix changes which setups ALEX evaluates or treats as duplicates. Joe's call (§7.4)** |
| 🔴 **`getCandleCloseTime` re-estimates the newest bar's close**, moving it by 48 h at every weekend reopen and mutating `qualificationTimestamp` + `reactionId` — two of the five components the proposed `stableId` fix relies on | §2.17 / §7.3 | **OPEN — makes the §7.3 fix as currently specified incomplete** |
| 🔴 **Drift-detector blind spot: `tradedSignals` present, positions and journal both absent** → zero drift events and a second position opens unobserved | §2.17 | open |
| EUR_USD root cause | §2.10 / §5 | **RESOLVED** — never starved. Measured 72 evaluations vs GBP_USD's 72 over 3,719 polls; the "~54 vs 0" asymmetry never existed |
| `alexGLiveSetupStatuses` 300-entry FIFO vs its "PERMANENT, never reconsidered" contract (`index.html:4308` vs `4729`) | ALEX / §7.2 | **open — NOT governance-blocked as previously claimed.** The guard lives in non-protected code; ≈53 re-decisions per signalId measured |
| PIPELINE natural key omitted the pair, silently dropping the record that names which instrument was skipped | §2.14b | **CLOSED** — fixed, 6 fixtures, mutation-proven |
| JVM coverage ledger read attribution back out of shared `pairData` — a successful sweep reported a total outage | §2.14a | **CLOSED** — regression in `e778cec`, fixed with sweep-local attribution, 5 fixtures, mutation-proven |
| `DISPATCHED_NO_RESULT` is unreachable through the I/O layer (both fetchers swallow errors) | §2.14a | **disclosed** — kept as a defensive branch, labelled as such, covered at the dispatch seam |
| `alexV2BuildLegacyDecisionSummary` takes `statuses[statuses.length-1]` as "latest" from an `unshift`-ordered ring — that is the **oldest** entry (`index.html:20128`) | ALEX-v2 shadow | open — latent today (shadow log empty), would poison the v2 comparison dataset |
| IndexedDB write amplification: the whole status ring is re-submitted to the ledger every advancing poll, each record burning a readwrite seq allocation *before* the duplicate is rejected | §7.2 | open — would be made ~16.7× worse by the withdrawn cap-raise option |
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

Four gaps remain, none of them blocked by engineering difficulty and **none repaired autonomously**.
For each: what is wrong, what actually blocks it, the **smallest correct** change, and whether a
non-invasive method gives equivalent proof.

> **This section previously opened "Two gaps are blocked by the protected-function contract." Both
> halves of that were wrong.** There are four, and **two of them (§7.2, §7.4) need no protected edit
> at all.** The real boundary is narrower and more honest than the protected-function contract: it is
> that each remaining change alters **which setups ALEX evaluates, or which it treats as duplicates**
> — frozen-strategy semantics, which are Joe's to authorize regardless of where the code happens to
> live. Treating "unprotected" as "therefore mine to change" would be the same back-door reasoning
> §7.2 rejects, applied to myself.

### 7.1 JVM candidate-level diagnostics — ✅ AUTHORIZED AND IMPLEMENTED (§9.4)

**Unobservable today.** JVM emits scan-level events only (`SCAN_STARTED`, `SCAN_COMPLETED`,
`ENGINE_ERROR`, all from `scanAll`). Not one candidate-, rule- or rejection-level event exists —
proven against a real firing sweep by **JVM-27/28**, where 8 positions opened and the only events
present were the two scan-level ones. Three drop points discard already-computed detail:

| Site | Discarded | Line |
|---|---|---|
| `if(!result.fires)return;` | `result.reason` and `result.conf` | `index.html:16831` |
| `if(pos.error){return;}` | structured sizing error on a **fired** signal | `index.html:16836` |
| the eligibility filter | which pairs were excluded and why | `index.html:16818-16825` |

**Why blocked.** All four functions on that path — `checkAutoTrades`, `evaluateLiveTrigger`,
`openPaperPosition`, `getSession` — are protected. Any emit added inside them breaks drift-0.
ALEX's equivalent plumbing is *not* protected, which is why ALEX could be instrumented
autonomously and JVM cannot.

**Smallest governed change.** One line at `index.html:16831`, before the existing `return`:

```js
if(!result.fires){ emitDecisionEvent({eventType:'CANDIDATE_REJECTED',strategyId:'current_strategy',
  pair:oPair,source:'checkAutoTrades',stage:'LIVE_TRIGGER',decision:'REJECTED',
  reasonCode:'CONFLUENCE_BELOW_THRESHOLD',reasonText:result.reason,
  context:{confluence:result.conf&&result.conf.total},evidenceCompleteness:'PARTIAL'}); return; }
```

It touches one protected function, adds no branch, changes no rule, and reuses a value the function
already computed. **Correction:** this previously said it needs "one new reason code registered
before use". It does not — `CONFLUENCE_BELOW_THRESHOLD` is **already registered**
(`index.html:11747`) and is already present in the running tab's registry. The entire cost is a new
baseline hash for `checkAutoTrades`, i.e. drift-0 re-established against a new baseline. This
decision is one item cheaper than stated.

**Non-invasive equivalent? Partial, and it should not be mistaken for the real thing.**
`evaluateLiveTrigger` is pure and callable from outside, so a shadow observer could recompute the
verdict for each eligible pair and record *that*. It would reproduce the reason text faithfully.
What it could **not** do is prove the recomputed verdict is the one the live path actually acted on
— it is a re-derivation, not a record of the real decision, and it would double the market-data
cost. Recommended only if the governed change is declined.

### 7.2 ALEX live-setup status ring (the §2.10 residue) — ✅ AUTHORIZED AND IMPLEMENTED (§9.3)

**Unobservable / incorrect today.** `alexGLiveSetupStatuses` is a 300-entry ring that holds less
than one poll cycle (383 setups). Consequences: the pairs earliest in `SCAN_PAIRS` order are absent
from the panel and from the `statuses` array written to the durable ledger; and the duplicate guard
at `index.html:4729`, documented *"PERMANENT, never reconsidered"*, reads that same truncated ring,
so for evicted pairs a setup's fate is **not** decided once.

**Why blocked — RETRACTED. It is not blocked.** This section previously stated that
`alexGRecordLiveSetupStatus` is protected, so "raising the cap, or separating the 'decided' set from
the 'display' ring, means editing it." The second half is **false**, and it is the half that
mattered. That protected function's entire body is *"skip if this signalId is already in the array;
unshift; truncate to 300"* — it is the **display** recorder. **The duplicate guard that actually
decides whether a setup is reconsidered lives in the NON-protected
`alexGEvaluatePairForLiveSetups`** (`index.html:4729`), which reads the ring from outside. Separating
the decided-authority from the display ring therefore requires **zero protected-function edits**.

What *is* genuinely blocked is only the narrow option of **raising the cap**, because the `300`
literal does sit inside the protected function. That option is no longer recommended.

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
runs *before* the entry-delay check (`index.html:4359`), so while `A_repeatedReaction` is suspended
— **257 of 388 live setups**, read read-only from the campaign on 2026-08-14 — chasing can only
reach `B_breakRetest`. The mechanism is structurally real and, on this path, currently unexercised.

> *Figure reconciliation:* this section previously said "259 of 387" while §2.10 said "257 of 383".
> Both were point-in-time reads taken days apart, and neither was wrong when written; the live count
> genuinely drifted 383 → 387 → 388 across the milestone. The current figure is **257 of 388**, and
> that drift is itself the argument in §7.2 against any fixed count cap. The related claim that live
> D and W setups are "all pre-activation, so there are zero live instances today" is **superseded**:
> §2.17 reproduced a second real position on a daily `B_breakRetest`, and the campaign currently
> holds **5 tradeable daily `B_breakRetest` setups** (96 H1 / 30 H4 / 5 D / 0 W).

**Raising the cap to 5000 was the previous recommendation. It is withdrawn.** It is not wrong at
today's rates, but it is bounded by the wrong quantity and it buys less than it costs.

Measured cadence is **1.14 advancing cycles/hour** (79 advancing polls / 69.4 h), and above a cap of
388 the dedup starts firing so the ring only gains *genuinely new* signalIds — measured birth rate
**1.68/hour**. On those numbers:

| Cap | First eviction of a still-decidable record | vs the W staleness window (168 h) |
|---|---|---|
| 300 (today) | **immediate — within the same cycle** | **fails** |
| 670 | 168 h | break-even |
| 5000 | 2,745 h ≈ **114 days** | 16.3× margin |

So at measured rates 5000 is a repair, not a postponement. **But three things break that margin, and
the third is decisive:**

1. **It is bounded by COUNT where the requirement is TIME.** Those coincide only by accident.
2. **Setups-per-cycle is unbounded.** `alexGSetupState.push` has no cap anywhere. Headroom is 12.9×
   today, **4.5× at 34 pairs**, ~2.3× at 34 pairs with a 180-day lookback — all config values. The
   count observably drifted 383 → 387 → 388 *within this milestone*.
3. **On a drifting key it collapses.** The ring keys on `signalId`, which re-anchors (§2.16). If
   re-anchoring ever becomes systemic, the birth rate is 388/cycle and 5000 is exhausted in
   **11.9 hours** — shorter than the D window (24 h) and **14× shorter than W (168 h)**. A count cap
   on a drifting key is unsound in principle, and its margin is a measurement rather than a
   guarantee.

It also costs what it does not advertise: **~6–7.5 MB resident**, and — because
`alexGLivePollTick` hands the *whole ring* to the durable ledger every advancing poll
(`index.html:5213`) and `evidencePutObservation` burns a readwrite meta transaction to allocate a
seq **before** discovering the record is a duplicate — **~16.7× IndexedDB write amplification,
~10,000 transactions/hour and ~120k wasted sequence numbers/day**, essentially all of it discarded.

**Smallest CORRECT change — separate the two concerns, and key the authority on the stable identity.**
The display ring stays a bounded 300-entry display ring, which is all it was ever fit to be. The
decided-authority becomes its own structure with the *correct lifetime*:

> A setup stops being re-decidable the moment `alexGIsSetupSignalStale` fires. Past that point it
> `continue`s before ever reaching `alexGConstructLivePosition`, so a decided record about it can
> never change an outcome. **Evicting by age — `now − qualificationTimestamp > maxLiveSignalAgeMinutes[tf]`
> — is therefore behaviourally identical to keeping it forever.** That is a proof, not an estimate,
> and it is what makes a bounded structure fully correct here.

Steady-state size is `Σ birthRate × TTL` ≈ **300–700 entries, ~100 KB** — roughly **40–70× smaller
than the 5000-entry ring, and strictly more correct at every timeframe**.

It must key on `alexGStableSetupIdentity` (`index.html:2198`), **not** `signalId`: a decided-set
keyed on `signalId` inherits the drift wholesale and re-creates the exact failure it exists to
prevent. That function already exists, is **not protected**, and is **already computed on this exact
hot path** by the drift detector — and it already carries `timeframe` and `qualificationTimestamp`,
which are precisely the two fields the age-eviction rule needs. The key and the eviction key are the
same object.

**No new persistent state is required, and none should be created.** For *traded* signals the durable
authority already exists: `alexGAccount.closedPositions` and `alexGJournalEntries` both carry all
five stable components, so the identity is computable from already-persisted data —
`alexGAutoTrading.tradedSignals` is a redundant index over that data, and it is the one copy that
drifts. For *decided-but-not-traded* signals nothing existing can serve (the durable observation
ledger genuinely is the decided authority, but it is async IndexedDB and the guard is synchronous),
so a **session-scoped in-memory map is the minimum new state — and session scope is correct**,
because "decided" is only meaningful for at most 7 days.

**Where it lands.** Guard site `index.html:4729`, mark sites beside the six existing
`alexGRecordLiveSetupStatus` calls, prune once per tick, and clear alongside the single production
reset in `resetAlexGLiveAccount` (`index.html:5283` — the previously cited `5195` is a `}catch(e){`).
There is **exactly one** production reset site and it already clears `tradedSignals` on the adjacent
line, so the desync that reverted the MOGO-020 attempt is a one-line fix. The 20 broken fixtures were
*test* desync, not production desync.

**On the "back door" objection, stated honestly.** The previous text argued that doing this in the
non-protected caller "evades the protected-function gate" and would be worse governance. Half of that
survives and half does not. What survives: **the semantic change is identical wherever the code
lives** — setups decided once instead of ~53 times — so **Joe's authorization is required either
way**, and the governance question is about *where the change is recorded*, not whether behaviour
changes. What does not survive: the "back door" framing itself. The guard is *already* in the
non-protected caller; putting the decided-set next to it is cohesion, not evasion. Editing a
protected function *specifically so the change registers as drift* would be governance theatre — it
buys a baseline diff and pays for it with an unnecessary edit to frozen code.

**One companion change needs NO authorization and should ship regardless.** The durable ledger's
blindness to the front of scan order is caused by feeding it a *snapshot of the ring*
(`statuses:` at `index.html:5213`) rather than *this tick's decisions*. Collecting each status object
as the non-protected callers produce it, and passing that per-tick array instead, removes the
truncation bias entirely, keeps IDB traffic proportional to real decisions, touches **zero protected
functions and changes zero strategy semantics**. It is a pure reporting-integrity fix and is
independent of the decision above.

**Interaction with §2.16 — these should be ONE governed change, not two.** A stableId-keyed
decided-map means a re-anchored, already-decided setup never re-reaches
`alexGConstructLivePosition`, so the drifted guards inside it are never consulted — which closes most
of §7.3's duplicate-trade exposure **for the live-poll path with zero protected edits**, where
§7.3's own proposal edits *two* protected functions to achieve less. *Honest limit:* the map is
memory-only, so the protection lapses after a reload; the staleness gate bounds that residual window
to ≤7 days.

### 7.3 Signal identity instability (§2.16) — ✅ AUTHORIZED AND IMPLEMENTED (§9.3)

**Unobservable / incorrect today.** `signalId` embeds zone-anchor timestamps that drift as the
**fixed-count 2,220-bar H1 window (≈129.5 calendar days)** advances — *not* a "rolling 90-day
window"; `days=90` is the parameter name, `days*24+60 = 2220` bars is the actual request
(`fetchAlexGReplayDatasets`, `index.html:4052`). Three live `signalId` guards in
`alexGConstructLivePosition` (`index.html:4328`) can miss, **plus a fourth that has never been able
to fire and a fifth that keys on `tradeId` and drifts identically** — see the table below; "all four
guards" was the wrong count in both directions. Confirmed live: 0 of 388 current signalIds match the
one entry in `tradedSignals`, for a trade that demonstrably happened.

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
| `index.html:4328` | `signalId` (× 3 live checks; the journal one is dead code) | **yes** |
| `index.html:4386` | `tradeId` = `AGT\|setupId`, which embeds the same `zoneId` | **yes** |

A fix applied only at 4302 leaves 4361 drifting — and 4361 is currently load-bearing, so a partial
fix would look like it worked while removing the guard that is actually holding today. The change
touches two protected functions and changes no rule.

**While here, `index.html:4331` should be deleted or repaired.** `alexGJournalEntries.some(e =>
e.signalId === signalId)` has never been able to fire because no ALEX journal record carries a
`signalId`. It reads as defence-in-depth and is not.

**Non-invasive equivalent? No.** The check lives inside a protected function on the trade-open path;
there is no external hook between the duplicate test and the open. A shadow observer could *detect*
a duplicate after the fact but could not prevent one. **This is the one open item where the absence
of a governed change leaves a path to a real duplicate paper trade.**

### 7.4 The H4/D/W completeness gap — ✅ AUTHORIZED AND IMPLEMENTED (§9.2)

**This is new, it is the most actionable item in the milestone, and it is NOT protected — yet I have
deliberately not fixed it.** Explaining why is the point of this section.

**What is wrong.** `alexGEvaluatePairForLiveSetups` checks the length of `datasets.H1` only
(`< 60`). `datasets.H4`, `datasets.D` and `datasets.W` are used with **no length and no completeness
check whatsoever**, and `fetchCandlesRange` classifies a short single page as
`RAW_COUNT_SHORT → COMPLETE`. Because the fetch is by fixed **count**, any shortfall shifts the
window start **off a bar boundary**, which re-anchors the zone identity at an arbitrary moment —
including *inside* the staleness window, where a whole-bar roll can never land. That is the input
that opened a second real paper position in §2.17's control pair, with every guard intact.

**Why I did not fix it autonomously.** The function is unprotected, so the *contract* does not block
me — but every candidate fix changes ALEX's frozen behaviour, and the right form is genuinely
ambiguous:

| Candidate | What it does | Why it is not obviously right |
|---|---|---|
| Mirror the H1 floor (`length < N`) on H4/D/W | cheapest, matches existing code | **Does not close the defect.** The demonstrated case is 148 candles against 150 — far above any sensible floor |
| Require `completenessState === COMPLETE` for H4/D/W | closes it, and matches ADR-011's posture everywhere else | Applies ADR-011 to ALEX for the first time. An instrument whose genuine history is shorter than the request would stop being evaluated at all — on W that is 73 weeks, which would silently drop legitimately young instruments |
| Quantise the window start (trim to a bar-aligned boundary) | closes it without suppressing anything | Changes the candle set the frozen engine sees — the one input the whole strategy freeze exists to hold constant |
| Change the fetch to a time range rather than a count | removes the class entirely | Explicitly out of scope: "no change to market-data requests" is a standing release constraint |

Choosing among these decides *which setups ALEX evaluates and which trades it takes*. That is a
frozen-strategy semantic decision, and it is Joe's, not mine. Picking one unilaterally because the
function happens to be unprotected would be exactly the "back door" reasoning §7.2 correctly warns
against — the protected-function boundary is a proxy for the semantic boundary, not a substitute for
it.

**What I recommend.** Option 2 (require COMPLETE), scoped so a genuinely short-history instrument is
*recorded and skipped* rather than silently evaluated on a shifted window — which is what ADR-011
already does for JVM, and what the existing H1 check already implies for ALEX. It closes the only
demonstrated live path to a duplicate paper trade and needs no protected edit.

**Interaction with §7.3.** The `stableId` fix and this one are complementary, not alternatives.
`stableId` does not help here on its own, because the weekend close-time re-estimation mutates two of
its five components (§2.17). A complete fix keys the stable identity on the anchor bar's **start**
time and closes the completeness gap.

---

### 7.5 Standing constraints, all intact

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

### Why this closed YELLOW — and what changed since

> **⚠️ HISTORICAL — this section records the state at which the milestone paused for authorization.
> All four decisions below were subsequently AUTHORIZED by the owner and are IMPLEMENTED. See §9 for
> what shipped, the mutation evidence, and the governance record.** The analysis is retained because
> it is what the authorization was granted against.

Every scope item above is complete. Two defects found this session were fixed, verified and
mutation-proven (§2.14a, §2.14b). **Four trading-fidelity defects remain open. The previous claim
that all of them are "blocked by the protected-function contract" was FALSE** — re-verification
established that two of the four need no protected edit at all. What blocks them is a *frozen-strategy
semantic* decision, which is Joe's, and that is a different and more honest boundary.

A second real paper position has now been reproduced end-to-end under pristine production config,
with zero guards and zero config mutated. Declaring GREEN with that outstanding would be exactly the
failure mode this milestone was created to prevent.

| # | Defect | Severity | Protected edit needed? | Smallest correct change |
|---|---|---|---|---|
| 1 | **Signal identity not stable** — three live `signalId` guards plus a fifth `tradeId` guard all drift; a closed setup can re-open (§2.16) | **highest** | yes, two functions | anchor-free `stableId` as a second OR-term in **both** duplicate checks — and keyed on the anchor bar's **start** time, or the weekend close-time re-estimation defeats it (§2.17, §7.3) |
| 2 | **H4/D/W have no length or completeness check** — a short broker page shifts the window off a bar boundary and opens a duplicate *inside* the staleness window (§2.17) | **highest — the only DEMONSTRATED live path to a duplicate trade** | **no** | require `completenessState === COMPLETE` for H4/D/W, recording and skipping a genuinely short instrument (§7.4) |
| 3 | **Status ring holds less than one cycle** — "PERMANENT, never reconsidered" is void for all 12 pairs; ≈53 re-decisions per signalId (§2.10, §7.2) | high | **no** — the guard is in non-protected code | separate the decided-authority from the display ring, key it on `stableId`, evict it **by age**; ~100 KB. The cap 300→5000 option is **withdrawn** (§7.2) |
| 4 | **JVM emits no candidate-level diagnostics** — rejections and dropped fills are unauditable (§7.1) | medium — observability, not correctness | yes, one function | one `emitDecisionEvent` before the existing `return`; the reason code is **already registered**, so the only cost is a new baseline hash (§7.1) |

**What is required from Joe — four decisions, no implementation work.**

1. **Authorize the identity fix (#1)** — or direct otherwise. Note the added requirement: keying on
   the anchor bar's start time, since `qualificationTimestamp` and `reactionId` both move every
   weekend. Adds guard terms; removes none.
2. **Rule on the H4/D/W completeness gap (#2).** No protected edit, but it changes which setups ALEX
   evaluates. This is the one that closes the demonstrated duplicate path, and I recommend taking it
   first.
3. **Rule on the decided-authority separation (#3).** Frozen-strategy semantic question: setups
   currently re-decided ~53 times would be decided once, as the contract already states they should
   be. **#1 and #3 are best authorized as a single change** — they share the same identity, and #3
   incidentally closes most of #1's exposure on the live-poll path.
4. **Rule on the JVM diagnostic (#4)** — a governed change purely to record a value the function
   already computes.

Only #1 and #4 re-baseline a protected function. **One further change needs no authorization at all
and will ship on the next pass regardless:** feeding the durable ledger this tick's decisions instead
of a snapshot of the truncated ring (§7.2), which is pure reporting integrity with zero semantic
change.

---

## 9. Governed remediation — AUTHORIZED AND IMPLEMENTED (2026-08-14)

Joe authorized all four decisions from §8. All four are implemented. This section records what was
built, what it cost in governance terms, and what each claim is proven by. **§7.1–§7.4 describe the
problems and the options considered; this section is what actually shipped, and it supersedes those
sections' "not done autonomously" framing.**

| Gate | Before | After |
|---|---|---|
| Canonical | 24 suites · 1,354 / 1,354 | **24 suites · 1,391 / 1,391 · 0 failures · 0 execution errors** |
| Platform | 1,049 / 1,049 | **1,049 / 1,049** |
| Protected drift | 0 against the v12.5.0 baseline | **0 against the re-issued v12.20.0 baseline** |
| Protected functions changed | — | **exactly one: `checkAutoTrades`** (0 added, 0 removed, 0 constants changed) |

### 9.1 The governance record, stated precisely

`APP_VERSION` 12.19.0 → **12.20.0**, with a full release note in `APP_VERSION_LOG`.
`regression-baseline.json` re-issued from 12.20.0.

**The drift check was run as a positive control on the governance mechanism itself, before
re-baselining.** It reported `DRIFT DETECTED in 1 protected item(s): CHANGED: checkAutoTrades` and
exit 1 — naming exactly the one function Decision 4 authorizes and nothing else. That is
independent, mechanical confirmation that **Decisions 1, 2 and 3 touched no protected code at all**,
which is the claim §7.2 previously got wrong in the other direction. A before/after diff of the
baseline confirms: 63 → 63 protected functions, one changed, none added, none removed, 4 → 4
protected constants, none changed.

No confluence, threshold, setup definition, pattern definition, entry, stop, target, filter, risk,
sizing rule or exclusion was altered by any of the four changes.

### 9.2 Decision 1 — higher-timeframe completeness. **DONE.**

Two repairs, because the gate alone would have been a mute button rather than a fix.

1. **`fetchCandlesRange` no longer treats a short page as proof of exhaustion.** It used to `break`
   on the first `RAW_COUNT_SHORT` and then classify the short accumulation **COMPLETE**. A broker
   returning 148 candles when asked for 150 was indistinguishable at that point from one that had
   genuinely run out. The walk now **continues**: if more history exists the cursor retrieves it and
   the count is reached, so the shortfall is **repaired**, not merely detected; if the instrument
   really is exhausted the next page comes back empty and `EMPTY_PAGE` records true exhaustion.
   That distinction is the whole point — **a window pinned at the real start of history cannot
   move, so its identity is stable, whereas a window that stopped early for a transient reason
   moves on the next poll.** Only `REACHED_COUNT` or `EMPTY_PAGE` now satisfy the request.
2. **`alexGEvaluatePairForLiveSetups` gates evaluation on `completenessState === COMPLETE` for all
   four timeframes.** Previously only `datasets.H1.length < 60` was checked and H4, D and W had no
   check of any kind. Gated on `completenessState` and **nothing else**, per ADR-011's central rule —
   branching on `receivedCount`/`httpStatus`/`paginationTerminationReason` here would have
   re-created the original defect one layer down. Fail-closed (`marketDataCompletenessOf` reports
   unclassified data as UNAVAILABLE) and scoped per-pair. Transport and contract failures are
   recorded distinctly: `DATA_CANDLES_UNAVAILABLE` vs the newly registered
   `DATA_TIMEFRAME_INCOMPLETE`, with `context.incompleteTimeframes`,
   `context.completenessByTimeframe`, and a durable `DATA_INCOMPLETE` pipeline stage.

*One harness-fidelity correction was needed and is worth recording, because it is the kind of thing
that hides a real defect:* the `run_v1232` fetch stub ignored the `&to=` continuation cursor and
replayed the same page. That was harmless only while a short page ended the walk. It now returns an
empty continuation, as a real broker does and as the `run_v1236` stub already did. **This made the
stub more faithful, not more permissive.**

### 9.3 Decisions 2+3 — stable economic identity and a decided-authority. **DONE, as one change.**

The withdrawn `300 → 5000` workaround was **not** implemented.

**Two identities, because one is provably not enough.** `alexGStableSetupIdentity` drops the zone
anchor and so survives a window roll and ring eviction — but `getCandleCloseTime` returns an
**estimate** for the newest bar, so every artifact anchored on the last bar of a trading week has
its close time move by ~48h at the weekend reopen, changing `reactionId` **and**
`qualificationTimestamp`: two of that identity's five components. The new
`alexGEconomicSetupIdentity` is therefore built from immutable categorical fields and **prices**,
which no re-estimation touches. It is an additional OR-term — it can only ever block a duplicate,
never admit one. **DECIDED-2b pins that it excludes the zone anchor**, a gap that survived the first
mutation pass and would otherwise have let the identity be quietly folded back into uselessness.

**The authority is separated from the display ring, and introduces no new persistent state.**
`alexGLiveSetupStatuses` remains a bounded 300-entry display buffer, which is all it was ever fit to
be. Whether a setup was already **traded** is derived from the **existing durable** account and
journal records — both already carry every field these identities need. Whether it was already
**decided** is a session-scoped map, and session scope is *correct*: "decided" is only meaningful
while the setup can still be acted on, so a reload legitimately re-decides, and persisting it would
create a second durable authority that could desynchronise from the account. **No parallel
persistent Set was introduced** (DECIDED-12 asserts zero new storage keys).

**Eviction is by age, and provably lossless.** A setup stops being re-decidable the moment
`alexGIsSetupSignalStale` fires, so an age-evicted record could never have changed an outcome —
unlike a count cap, which evicts records that are still load-bearing. DECIDED-9 pins that the
eviction boundary **is** the staleness boundary, and DECIDED-10 that the lifetime is per timeframe
(a W decision outlives an H1 one by its own contract). The prune reads `RULES_ALEXG.config`, the
exact object the frozen gate reads.

> **A real defect in my own implementation, caught by its own fixture.** The prune was first wired to
> `snapshotAlexGConfig()`, which nests the rules under `.config` — so `maxLiveSignalAgeMinutes` read
> `undefined` and **the age eviction silently did nothing**. It passed every other fixture. This is
> exactly the class of silent no-op this milestone has been burned by repeatedly, and it is the
> second time in two sessions that writing the fixture is what found the bug.

**`alexGResetLiveDecisionState()` is the single primitive owning both the ring and the authority**,
so they cannot desynchronise — the specific failure that caused the MOGO-020 attempt to be reverted.

**SEMANTIC CHANGE, AUTHORIZED AND VISIBLE:** setups previously re-decided every poll (~53 times per
signalId) are now decided once, as the contract already stated. This is why several suites needed
their scenario resets updated: a scenario that does not clear session state now correctly inherits
the previous scenario's decisions.

### 9.4 Decision 4 — JVM candidate-level diagnostic. **DONE.**

`checkAutoTrades` discarded the verdict `evaluateLiveTrigger` had already computed. The protected
diff is **a single statement**: `if(!result.fires)return;` →
`if(!result.fires){jvmRecordCandidateRejected(oPair,result);return;}`. Both helpers live outside the
protected function, in non-protected code.

It **records the decision the strategy actually made** and never recomputes it — `evaluateLiveTrigger`
is called exactly once, by the trading path, and this reads its result. `jvmRecordCandidateRejected`
is total by construction: wholly wrapped, returns undefined, result never read, so it cannot alter,
delay or prevent a trading decision.

**All eight of `evaluateLiveTrigger`'s rejection reasons map to reason codes that already existed** —
none was invented, none stretched. §7.1's claim that this needed "one new reason code registered
before use" was already retracted; in fact it needed none. The interpolated `R:R only X:1` reason is
matched by prefix, and an unmapped reason yields `UNKNOWN_NOT_RECORDED` rather than a fabricated
code. `evidenceCompleteness` is **PARTIAL**, not COMPLETE, because `evaluateLiveTrigger`
short-circuits on its first failed gate — the later gates genuinely were not evaluated, and claiming
otherwise would be the fabrication this ledger exists to prevent.

**JVM-27/28/29 asserted the auditability gap and are inverted** to assert the contract instead; they
are now the proof the diagnostic landed and fail again the moment it is removed. **JVM-30** pins that
the reason *code* corresponds to the actual computation rather than a fixed placeholder, and
**JVM-31** that no unregistered code can be emitted.

### 9.5 Mutation evidence

Every mutation was proven applied (anchor asserted unique, then byte-diffed) before its result was
accepted.

| Mutation | Fixtures killed |
|---|---|
| revert the ALEX four-timeframe completeness gate | D1 suppression + duplicate-from-short-page fixtures |
| restore `break` on `RAW_COUNT_SHORT` and re-admit it as satisfied | D1 short-page fixtures |
| collapse the transport and contract reason codes | D1 transport-vs-contract fixture |
| gate on H1 only (drop W/D/H4) | D1 H4, D and W suppression fixtures |
| drop the economic identity from the guard | DECIDED-6 |
| drop the durable positions/journal scan | DECIDED-11, DECIDED-13 |
| make age eviction a no-op | DECIDED-8, DECIDED-10 |
| stop clearing the authority on reset | DECIDED-14 |
| fold the zone anchor back into the economic identity | DECIDED-2b |

### 9.6 What this does and does not close

**Closed:** the only *demonstrated* live path to a duplicate paper trade (§7.4), the void
"PERMANENT, never reconsidered" contract (§7.2), signal-identity instability across window rolls,
ring eviction **and** the weekend close-time re-estimation (§2.16/§7.3), and JVM's candidate-level
auditability gap (§7.1).

**Explicitly not claimed:** that ALEX or JVM is profitable, well-calibrated, or that these changes
say anything about edge. Nothing here is evidence about strategy quality — only about whether the
system does what its own contracts say.

### 9.6a A defect Decision 1 exposed — ALEX claimed coverage it had not achieved

Implementing Decision 1 surfaced the ALEX twin of the JVM defect fixed in §2.14a, and made it
materially worse. `alexGLivePollTick` did:

```js
__obsAdvanced=true; __obsEvaluated.push(oPair);
await alexGEvaluatePairForLiveSetups(oPair,__scanId);
```

The pair was credited as **evaluated before evaluation ran**, and `instrumentsAttempted` was derived
from that same array — so attempted and evaluated were **identical by construction** and neither
could ever reveal a gap. That was tolerable only while suppression was rare. Decision 1 makes
suppression a real, expected outcome, so a pair skipped for incomplete higher-timeframe data would
have been reported as **fully evaluated**: a diagnostic claiming healthy coverage for evaluation that
never happened, which is precisely what this ledger exists to prevent (completion-standard item 11).

`alexGEvaluatePairForLiveSetups` (not protected) now returns
`{evaluated, reason, incompleteTimeframes}` — `evaluated:true` only on the path where the frozen
engine actually ran — and the tick credits `instrumentsEvaluated` only on that outcome, records a
reasoned `instrumentsSkipped` entry otherwise, and takes `instrumentsAttempted` from a separate true
dispatch list. The swallow-and-continue error behaviour is unchanged; the ledger simply stops calling
a faulted pair evaluated.

**Two existing fixtures had encoded the dishonest attribution and were corrected, not accommodated.**
MDC-13 asserted 12/12 evaluated *while one instrument was suppressed* — only ever true because an
attempt counted as an evaluation; it now asserts 11 evaluated + 1 named in `instrumentsSkipped` = 12
configured. Phase2C.33 pinned the return value as `undefined` as a proxy for "the catch did not
rethrow"; it now asserts the actual intent plus the new honesty. Both changes make the assertions
strictly stronger, and both are flagged to independent verification precisely because changing a
fixture that fails because of one's own edit is the move that most deserves suspicion.

Mutation-proven: making the tick credit every attempt as an evaluation kills MDC-13 (reporting
`12 evaluated + 0 skipped` — the dishonest state); deriving `instrumentsAttempted` from the evaluated
list kills MDC-13b.

### 9.7 Residuals and characteristics, disclosed rather than discovered later

* **Pagination cost.** Removing the `break` on a short page means a short page now costs one extra
  request to settle (retrieve the rest, or confirm exhaustion with an empty page). A *healthy* fetch
  is unchanged — it already needed a second page, because the newest candle is still forming and is
  filtered out. A broker that ignored the `to` cursor and replayed the same page would previously
  have been stopped by the `break`; it is now stopped by an explicit **cursor-not-advancing** guard,
  which reports `PARTIAL` rather than returning a window padded with duplicates. That guard is a
  hazard I introduced with this change and closed in the same change, not a pre-existing one.
* **Decided-authority lookup cost.** `alexGFindPriorDecision` consults the session map first and only
  falls through to the durable scan on a miss, so after the first poll of a session almost every
  setup resolves from the map. The worst case is the first poll after a reload: 388 setups × the
  number of durable records. At today's campaign size that is ~1,200 string builds once per hour.
  It is bounded by the journal, not by the ring, and it is not on a latency-sensitive path.
* **The economic identity keys on a 5-decimal price.** Two genuinely distinct setups sharing pair,
  timeframe, setup type, swing direction *and* an identical qualification close would collapse. It is
  consulted only against traded records and the session map, and it is an OR-term beside the precise
  identity, so a collision costs one skipped re-decision rather than a wrong trade — but it is a real
  and stated limitation, not a proof of uniqueness.
* **The authority is memory-only by design.** A reload legitimately re-decides. The already-*traded*
  half survives, because it is derived from the durable account and journal; only the
  decided-but-not-traded half is session-scoped, and that is correct — "decided" is meaningful for at
  most 7 days.

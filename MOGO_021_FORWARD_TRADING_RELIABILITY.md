# MOGO-021 — Forward Trading Reliability & End-to-End Pipeline Validation

**Status:** IN PROGRESS · continuation of MOGO-020
**Gates:** canonical 25 suites 1,538/1,538 · platform 1,049/1,049 · ALEX protected drift 0 (v12.20.0 baseline)
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

### 2.12 Chart data vs strategy-evaluation data — ⚠️ SUPERSEDED BY §10

> **Three of this section's four load-bearing claims are FALSE against current code**, and its line
> citations are 200–300 lines off, so it was written against an earlier revision and never re-checked.
> In particular "the divergence is operator-visible" was wrong — the amber card lives in a
> `display:none` panel — and the chart independently recomputed a full recommendation with no
> completeness gate at all. Retained as the record of what was believed; **read §10 instead.**

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
| Chart data vs strategy-evaluation data consistency | ⚠️ **REOPENED, then largely fixed** | §2.12's conclusion did not survive re-derivation. §10 records what was actually wrong; the chart now reads the engine's own verdict, gates on completeness, and states suppression where the operator is looking. **One item escalated (§10.5).** |
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
| Diagnostic coverage | **done, and corrected twice** | cursor-sanity detector, `instrumentsSkipped`/`Configured`, completeness card — plus §9.6a (the ledger credited an attempt as an evaluation) and §11.2 (a throw after the engine ran reported the pair skipped while a real position existed) |
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
| Canonical | 24 suites · 1,354 / 1,354 | **24 suites · 1,422 / 1,422 · 0 failures · 0 execution errors** |
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
  timeframe, setup type, swing direction *and* an identical qualification close would collapse.
  > **⚠️ This bullet originally said "a collision costs one skipped re-decision rather than a wrong
  > trade." Verification proved that FALSE for the durable half, which had no age bound at all:** a
  > genuinely new setup **30 days later** with the same economic identity was refused, and would have
  > been refused *for the life of the account and journal*. That is a permanently lost trade, which is
  > worse than the duplicate it prevents. Quantified: a repeated-reaction setup is by definition price
  > returning to the same zone, so pair/timeframe/setupType/swingType repeat almost by construction and
  > only the price discriminates — roughly **0.5% per pair of same-zone setups**, and JPY crosses get no
  > extra protection from their 3-decimal quoting. **Fixed:** the durable economic match now requires
  > the two qualification timestamps to be within the timeframe's staleness limit plus a four-day
  > market-gap allowance — which still catches the weekend re-estimation (~48h apart) and the pure
  > re-anchor (0 apart), but can never mistake a new setup weeks later for a re-derivation. Developer
  > test trades are also excluded, because they go through the same frozen functions by design and so
  > land in the account and journal like any other — a test trade must not durably block a real setup.
* **The authority is memory-only by design.** A reload legitimately re-decides. The already-*traded*
  half survives, because it is derived from the durable account and journal; only the
  decided-but-not-traded half is session-scoped, and that is correct — "decided" is meaningful for at
  most 7 days.

---

## 10. Chart ↔ engine fidelity (completion items 3 and 5)

Re-derived from `035853b`. **§2.12's conclusion does not survive re-derivation** — three of its four
load-bearing claims are false against current code, and its line citations are ~200–300 lines off,
confirming it was written against an earlier revision and never re-checked.

### 10.1 🔴 The trade path is LESS protected than the display path — and that is backwards

**This is the most serious finding and it is a governance escalation, not something I fixed.**

MOGO-021 Decision 1 gated ALEX on the completeness contract. `scanPair` — which only *scores for
display and alerting* — has been gated since ADR-011. But **`evaluateLiveTrigger`, which is JVM's
live auto-entry decision and actually opens trades, is gated only by `candles.length < 25`**, with no
completeness check at all (`index.html:6908-6909`). Its structural stop/target levels come from
`getStructuralAOI` (`index.html:6876-6890`), which fetches D and W and checks **neither** for
completeness: `findAOIs(daily||[])` on a PARTIAL 40-bar daily response clears `computeAOI`'s
`length<20` floor and produces a real support level that sets a **real stop on a real trade**.

So today: the pair list can suppress an instrument as incomplete while auto-trading, on the same
instrument, computes an entry, a stop and a target from data it never checked.

**Why I did not fix it.** Every correct fix changes which trades JVM takes. `evaluateLiveTrigger` and
`checkAutoTrades` are both **protected**, so those routes are blocked outright.
`getStructuralAOI` is *not* protected — but gating there makes `evaluateLiveTrigger` reject more
often, which is a change to frozen JVM strategy semantics. That is **a genuinely new
frozen-strategy semantic decision not covered by the current authorization**, which Decision 1 scoped
explicitly to ALEX. Recorded as an operator decision (§10.5), not taken unilaterally.

Related and blocked for the same reason: shortening `structuralAOICache`'s 15-minute TTL, and not
caching a `null`-derived AOI (a single transient fetch failure currently yields 15 minutes of
"No valid support AOI" rejections with no retry). The **in-flight dedup** half of that is
semantically neutral and is not blocked.

### 10.2 What the chart shows that the engine did not decide

| # | Defect | Severity |
|---|---|---|
| **D1** | `loadChart` independently recomputes `detectSignals`/`bestConfluence` and renders signal badges, a confluence panel and a **"▲ STRATEGY RECOMMENDS BUY"** banner with **no ADR-011 gate** (`index.html:10809-10814`). For a pair `scanPair` suppressed, the pair row shows `—`/0% while the chart shows a confident recommendation. Same pair, same timeframe, same second, directly contradictory | **HIGH — misleads about what the system decided** |
| **D2** | The chart's entire strategy layer is a **one-shot snapshot** taken at load. There is no `candleSeries.update()` anywhere, and `loadChart` is not on the scan tick, while the engine re-evaluates every 60 s. The badge can read "no live trigger right now" after `checkAutoTrades` has already opened a position on that pair | **HIGH — misleads** |
| **D3** | The amber completeness card — the mitigation §2.12 relied on when it called the divergence "operator-visible" — lives at `index.html:1360`, **inside `panel-diagnostics`**, and `.panel{display:none}`. `scanAll`'s own comment claims it is refreshed "rather than only when they open Diagnostics", which is the opposite of what happens. ADR-011 does place this state in Diagnostics, so the ADR is not violated — the **code comment and §2.12 were** | **HIGH** |
| **D4** | The "AOI touch" badge and confluence item derive from an `activeTf` AOI (100 bars of the displayed timeframe), while the purple lines drawn beside them are the **D/W** AOI the trade path actually uses. Different window, different tolerance. The source comment at `index.html:9081-9082` asserts they "can never disagree with what the confluence score or Auto Trading see" — same *engine*, different *inputs*, so the claim is false | **MEDIUM-HIGH** |
| **D5** | Drawn AOI lines never refresh; the engine's cache rolls every 15 minutes. An operator measures stop distance off a level the engine has already superseded | MEDIUM |
| **D6** | **ALEX suppression has no operator surface at all.** The completeness card reads only `pairData[].evaluationSuppressed`, a JVM structure. ALEX has no chart anywhere — `alexGZoneState` has no drawing site in the file | MEDIUM |
| **D9–D12** | Badges/confluence/banner state no timeframe while the two deliberately-labelled surfaces do; `scanAll` refreshes `#chartPrice` while OHLC stays pinned to load time; `fetchCandlesAroundWindow` never attaches completeness | LOW |

**Deliberate and documented, left alone:** per-call-site fetch counts; JVM entry timing always M15
(and *stated in the UI*); AOI sourced from D/W rather than the displayed timeframe (also stated);
`scanPair` retaining full candles for charting while gating evaluation; ADR-011 placing completeness
state in Diagnostics.

### 10.3 Test coverage — the honest gap

**Not one fixture anywhere asserts chart/engine consistency.** Nothing asserts `loadChart` gates on
completeness (it does not), that the drawn AOI equals the AOI the trigger consumed, or that a
suppressed pair's chart differs from an evaluated one's. The closest, `VISIBILITY-1`, stubs
`document.getElementById` and asserts the returned `innerHTML` — **it would pass identically for an
element in a `display:none` panel, which is exactly the case.** That is the vacuity class this
milestone keeps rediscovering, and it is why D3 survived.

### 10.4 ALEX zones are never drawn

`alexGZoneState` has no chart-drawing site anywhere in the file; there is no ALEX chart surface. The
shared chart is a JVM surface and makes no ALEX claim, so it does not *assert* anything false about
ALEX — but the owner's framing holds: the chart draws a pair ALEX explicitly refused to evaluate,
with zero indication, and there is no ALEX surface an operator could consult instead. TJR already
does this correctly, rendering `(incomplete)` in its chart legend — so the pattern exists in-repo.

### 10.6 What was fixed (items 3 and 5)

Everything below is display-layer and semantically neutral: no rule, threshold, entry, stop, target
or filter changed, and protected drift stayed 0 throughout.

* **D1 — the chart no longer forms a second opinion.** `loadChart` reads the engine's own verdict out
  of `pairData[activePair]` — literally the same object `scanPair` produced — and falls back to a
  local computation only before the first scan. Both paths are gated on the completeness contract,
  and a suppressed instrument renders an explicit **NOT EVALUATED** state instead of a fabricated 0%.
  *(CHART-1/2/3, mutation-proven.)*
* **D3 — the suppression indicator is now where the operator is looking.** The completeness card
  renders to a Scanner container as well as the Diagnostics one. **VISIBILITY-2 asserts structural
  reachability** — that the container genuinely lives inside `panel-scanner` — because the
  pre-existing `VISIBILITY-1` stubs `getElementById` and would pass identically for an element nobody
  can see. That is exactly how this defect survived, and it is the vacuity class this milestone keeps
  rediscovering.
* **D4/D9 — AOI labels can no longer be misread.** An "AOI touch" badge and the "AOI zone touch"
  confluence item now state the timeframe they were computed on, so they cannot be read as referring
  to the D/W lines drawn beside them. `detectSignals` and `scoreConfluence` are **protected** and
  their labels are frozen, so the qualifier is added at the display layer, where it changes no
  decision. Non-AOI items are deliberately left untouched. *(AOI-1/2/3.)*
* **D5 — the drawn AOI carries its computation time.** Those lines are drawn once and never refresh
  while the engine's cache rolls every 15 minutes, so an operator could measure a stop against a
  superseded level. Stating *when* it was computed is the honest, zero-semantic-change half;
  shortening the TTL would change which minutes JVM can trade in and is **not** authorized. *(AOI-4.)*
* **D8 (first half) — concurrent callers now share one AOI computation.** On a cold cache the chart
  and `evaluateLiveTrigger` each issued their own D+W fetch pair, last writer won the cache, and the
  chart drew *its* result while the engine used the other. They are now literally the same object.
  Semantically neutral — same function, same inputs, strictly fewer requests. *(AOI-5.)* The other
  half (not caching a `null`-derived AOI, which changes retry timing) remains **blocked**.

**One thing I deliberately did not fix.** The source comment at `index.html:9156` claims the AOI
badges "can never disagree with what the confluence score or Auto Trading see". It is **false** —
same engine, different inputs — but it sits **inside the protected `detectSignals`**, so correcting a
comment would cost a protected-function re-baseline. The correction is recorded here instead. That is
the protected contract working exactly as intended, and it is worth noting that it applies even to
prose.

### 10.5 JVM completeness parity — ✅ AUTHORIZED AND IMPLEMENTED (§12)

Decision 1 gated **ALEX** on the completeness contract. The same gap exists on **JVM's trade path**
(§10.1) and is *not* covered by that authorization. Closing it changes which trades JVM takes.

**The decision:** should JVM's live auto-entry path — `evaluateLiveTrigger` and the structural AOI
that sets its stops — be held to the same completeness contract ALEX now is?

* **If yes:** the smallest route is to gate inside `getStructuralAOI` (unprotected) and, for the M15
  entry series, inside `evaluateLiveTrigger` (**protected** — requires a governed change and a new
  baseline, exactly like Decision 4).
* **If no:** the asymmetry should be recorded deliberately, because at present JVM's display layer is
  stricter than its trading layer, which no one chose.

I have not implemented either. Everything in §10.2 that is display-only and semantically neutral is
being fixed under the existing authorization.

---

## 11. Independent adversarial verification of the four remediations

Run against `035853b` by a verifier instructed to disprove, with every mutation proven applied by
unique-anchor assertion plus byte diff before its result was accepted.

### 11.1 The headline held

**No duplicate paper position could be opened through the reproduced construction.** The verifier
first proved the scenario is a genuine duplicate-generator rather than one that never could be: with
**both** the completeness gate and the decided-authority removed, the short-page construction reports
`open=1 closed=1` — a second real position on an already-traded setup. With the shipped code it
reports `open=0 closed=1`, zero setups derived, suppression recorded. **Defence in depth is real and
was measured:** removing the gate alone still blocks (the authority catches it); removing the
authority alone still blocks (the gate catches it).

Decision 4 was upheld strongly: across `checkAutoTrades` runs in both flat and *firing* mode (8 real
positions), with `emitDecisionEvent` made to throw, to return `{ok:false}`, and to be undefined, and
with the reason mapper made to throw, the paper account, auto-trade log, `tradedToday` and journal
were **identical every time**, and nothing rethrew. The eight reason strings were checked against the
literal source of `evaluateLiveTrigger` rather than against a copy of the map.

The governance record was independently reproduced: drift against the pre-milestone baseline reports
exactly `CHANGED: checkAutoTrades`, and regenerating `regression-baseline.json` in a scratchpad
produced a byte-identical file.

### 11.2 What it found, and what I fixed

| Finding | Severity | Status |
|---|---|---|
| **The durable half of the decided-authority had NO age bound.** A genuinely new setup 30 days later sharing an economic identity was refused — and would have been refused for the life of the account. A **permanently lost trade**, worse than the duplicate it prevents. Developer TEST journal entries could durably block real setups too | **HIGH — over-blocking** | **FIXED** — age-bounded to the staleness limit + a four-day market-gap allowance; developer records excluded |
| **The two decided-maps CAN drift apart**, contrary to a code comment asserting they "cannot". Two setups sharing an economic identity but differing in stable identity leave an orphan the stable-map walk never evicts | MEDIUM | **FIXED** — the prune walks both indexes on their own terms; the false comment is corrected |
| **A false negative in the poll ledger.** A throw *downstream* of the frozen engine (a toast, a render, `saveAlexG`) reported the instrument as SKIPPED while a real position was already durably recorded. A coverage row contradicting a trade record is a wrong report, not a safe under-report | MEDIUM | **FIXED** — coverage is reported on whether the engine ran, not on whether the surrounding code finished |
| **Six mutations survived all 1,396 fixtures** — the prune's *wiring* (including the exact `snapshotAlexGConfig()` defect already shipped once), the durable economic term, `CURSOR_NOT_ADVANCING`, `ALEXG_DECIDED_MAX`, and `DATA_INSUFFICIENT_HISTORY ⇒ evaluated:false` | HIGH (test integrity) | **CLOSED** — 23 fixtures added; every one dies to its named acceptance mutation. Two are outright positive controls: removing the durable economic term **opens a second real position**, and removing the cursor guard accumulates duplicates all the way to the requested count and would classify them COMPLETE |
| Release note omitted three behavioural changes | MEDIUM (governance) | **FIXED** |
| §9.7's "a collision costs one skipped re-decision rather than a wrong trade" | false | **CORRECTED** |
| DECIDED-9 is mis-titled — it asserts the frozen staleness boundary, not eviction | LOW | **STRENGTHENED, not renamed.** Renaming was cheaper, but "eviction is provably lossless" is the *only* thing justifying eviction at all, so it is now tested rather than retitled: it measures the eviction boundary against the staleness boundary to the millisecond on all four timeframes. It is the only fixture in the entire gate that catches an off-by-one at that boundary |

### 11.3 Residuals I did NOT fix, and why

* **`EMPTY_PAGE` is trusted as exhaustion regardless of count.** A page short by 2 followed by an
  *empty* continuation classifies COMPLETE at 71/73 with the window start moved. This is the original
  defect's shape, but it now costs **two** independent transient faults rather than zero, and the
  consequence — a re-anchored identity — is caught by the decided-authority. Distinguishing "genuinely
  exhausted" from "short twice in a row" requires cross-poll state, i.e. a new persistent source of
  truth, which the authorization explicitly forbids creating unnecessarily. Disclosed rather than
  papered over.
* **`tradedSignals` present while positions AND journal are both absent leaves the authority blind.**
  `tradedSignals` values are bare `true` and carry no economic identity, so no identity match is
  possible from them. Making them self-sufficient means changing a *persisted* shape late in a
  session, and the present-but-unreadable variant of this state is already blocked by
  `saveAlexGAccountGuarded` (no second position can commit). Recorded as an open item, not changed.
* **ALEX poll-tick observation attribution — NOW FIXED.** `alexGLivePollTick` has no re-entrancy
  guard and is driven by `setInterval`, and the pipeline drain used to take the **whole** shared
  buffer — so whichever of two overlapping ticks drained second wrote the other tick's rows under its
  own `scanId`. That is the same read-shared-state-after-the-fact mistake the JVM coverage ledger was
  refuted for **twice**, on the other engine. Fixed the same way: each row is stamped with the tick
  that produced it, **at the moment it is produced**, and a tick drains only its own rows. The stamp
  is non-enumerable, so the durable observation is byte-identical and no consumer sees a new field;
  unstamped rows still drain to any tick, so nothing regresses. TICKATTR-1/2/3, mutation-proven —
  restoring the whole-buffer drain kills 1 and 2, making the stamp enumerable kills 3, and never
  stamping kills all three.
  *No re-entrancy guard was added:* overlap is production-observed and §2.13 established it is
  trading-safe, so suppressing it would be a behaviour change nobody authorized. This fixes the
  **attribution**, not the concurrency.

---

## 12. JVM market-data completeness parity — AUTHORIZED AND IMPLEMENTED

The §10.5 escalation was authorized: *"JVM must not open a paper trade from incomplete required
market data"*, as a DATA VALIDITY change only.

**The asymmetry, restated.** `scanPair` — which only *scores for display* — has been ADR-011 gated
since v12.8.3. The path that actually **opens trades** was not. `evaluateLiveTrigger` was guarded
only by `candles.length < 25`, and `getStructuralAOI` set the real stop and target from Daily/Weekly
data it never checked: a PARTIAL 40-bar daily response clears `computeAOI`'s own length floor and
yields a perfectly plausible support level, which then becomes a **stop on a real paper trade**.

**Three gates, all on `completenessState` and nothing else, all fail-closed, all scoped per pair:**

1. `evaluateLiveTrigger` refuses an M15 entry series that is not COMPLETE. *(one protected function)*
2. `getStructuralAOI` refuses to hand out levels derived from non-COMPLETE D/W, and reports that as
   a **distinct fact** rather than as "no valid AOI". *(unprotected)*
3. `runAutoTopDownScan` refuses to derive bias from incomplete W/D/H4. **These are required
   trade-path inputs, not display inputs** — that bias becomes `scanData[pair].bucket`, and
   `checkAutoTrades`' eligibility filter requires `bucket === 'Active watch'`. *(unprotected)*

**An incomplete AOI is deliberately NOT cached.** Caching a data fault for the 15-minute TTL would
turn one transient short page into 15 minutes of refused trades — losing valid setups to a gate that
exists to protect them, which the authorization explicitly rules out.

**Three facts stay three codes:** `DATA_CANDLES_UNAVAILABLE` (nothing arrived) vs
`DATA_TIMEFRAME_INCOMPLETE` (it arrived and failed the contract) vs
`CONFLUENCE_BELOW_THRESHOLD` / `STRUCTURE_AOI_NOT_VALIDATED` (the strategy declined). Collapsing any
two would make a data fault indistinguishable from a rule rejection — the exact confusion the old
code produced, since an incomplete AOI simply looked like "no valid support AOI".

**Nothing economic was touched.** Setup definitions, scoring, confluences, thresholds, entries,
stops, targets, risk and sizing are unchanged; the gate decides only whether the frozen evaluators
are handed data at all. JVMCG-1/2 prove it: with COMPLETE data the trigger still fires and
direction, entry, stop, target, confluence and R:R are unchanged and self-consistent.

### 12.1 The 14 required proofs

| # | Requirement | Fixture |
|---|---|---|
| 1, 11, 12 | COMPLETE data still evaluates, still fires, same economic decision, no valid setup lost | JVMCG-1, JVMCG-2 |
| 2 | Incomplete **required entry timeframe** fails closed | JVMCG-3 |
| 3 | Incomplete **H4** fails closed | JVMCG-6 |
| 4 | Incomplete **D** fails closed | JVMCG-4 |
| 5 | Incomplete **W** fails closed | JVMCG-5 |
| 6 | **UNKNOWN** completeness fails closed | JVMCG-7 |
| 7 | A short broker page cannot generate a JVM paper trade | JVMCG-11 |
| 8 | One incomplete instrument does not suppress healthy ones | JVMCG-8 |
| 9, 10 | Transport vs completeness vs strategy rejection stay distinct | JVMCG-9, JVMCG-10 |
| 13 | Restart/recovery — a transient fault is not cached into a lasting refusal | JVMCG-13 |
| 14 | Overlapping scans cannot bypass the gate | JVMCG-12 |

*Honest mapping note on requirement 2:* JVM's trade path requires **M15** (entry timing) plus **D**
and **W** (the structural AOI that sets the stop). H1 is required only when it is the active scan
timeframe, and that path — `scanPair` — was already gated. JVMCG-3 covers the required entry series.

### 12.2 Mutation evidence — every mutation proven applied

| Mutation | Fixtures killed |
|---|---|
| remove the M15 completeness guard | JVMCG-3 |
| remove the D/W AOI incompleteness guard | JVMCG-4, 5, 10, 13 |
| make the AOI never report incompleteness | JVMCG-4, 5, 8, 10, 11, 12, 13 |
| remove the bias-scan completeness gate | JVMCG-6 |
| cache the incomplete AOI (15-minute refusal) | JVMCG-13 |
| collapse completeness into a strategy code | JVMCG-9 |

### 12.3 Governance record

`APP_VERSION` 12.20.0 → **12.21.0**; `regression-baseline.json` re-issued. The drift check was again
run as a **positive control before re-baselining**: it named exactly `CHANGED: evaluateLiveTrigger`
and nothing else, independently confirming `getStructuralAOI`, `runAutoTopDownScan` and the reason
mapper are unprotected. Baseline delta: 63 → 63 protected functions, **one changed**, none added,
none removed; 4 → 4 constants, none changed.

Gates: canonical 24 suites **1,440 / 1,440** · platform **1,049 / 1,049** · drift **0**.

---

## 12A. FINAL VERIFICATION PROGRAM — run from the authoritative repository state

Run at **v12.22.0**, commit `8cdb0ad`, working tree clean.

### 12A.1 Gates

| Gate | Result |
|---|---|
| canonical (JXA) | **25 suites, 1,759 / 1,759**, 0 failures |
| platform + knowledge-engineering (Python `unittest`) | ~~**1,050 tests**~~, 25 of 26 suites `OK` — **the test count is wrong; see §18.3.** Reproduced from the recovered state it is platform **1,049** + knowledge-engineering **57** = **1,106**, of which 1,104 pass |
| protected drift | **0** — all 63 protected functions and 4 protected constants byte-identical to the **v12.22.0** baseline |

> **The platform gate does not need `pytest`.** It is pure-stdlib `unittest`; three suites appear to
> fail when a file is run directly and pass under `PYTHONPATH=.` — an import-path artefact, not a
> defect. Recorded because the earlier checkpoint's "platform 1,049/1,049" figure was unreproducible
> until this was worked out.

### 12A.2 🟡 Two pre-existing failures, both TJR-domain

`tests/knowledge_engineering/test_knowledge_engineering.py` — **2 of 57** fail:

* `test_all_195_claims_are_inventoried` — asserts 195 claims / 8 source artifacts; the corpus now
  holds **226**.
* `test_delta_reports_the_unclosed_risk_gap` — asserts **0** draft stop-placement rules; there are
  now **2**.

Both pin a **point-in-time snapshot** that the TJR corpus has since grown past. Neither is MOGO core
reliability, and **nothing in this milestone touched knowledge-engineering or TJR** — that file was
last modified in `592ca97`, an earlier milestone. They are carried into the TJR research program as
the first thing it must reconcile, and are **not** counted as core-reliability failures.

### 12A.3 Every named verification area has real, passing coverage

Fixture names collected from all 25 suites individually (1,768 lines including disclosed notes) and
mapped to the areas named in the authorization. **No area is empty:**

| Area | Fixtures | | Area | Fixtures |
|---|---|---|---|---|
| market-data completeness | 130 | | trade-ID uniqueness | 45 |
| scanner cadence/concurrency | 28 | | position lifecycle | 5 |
| scanner failure isolation | 21 | | ledger | 95 |
| detection rules | 21 | | account state | 158 |
| pattern/setup controls | 40 | | reconciliation | 37 |
| chart fidelity | 12 | | health diagnostics | 30 |
| AOI fidelity | 31 | | outage detection | 10 |
| ALEX end-to-end paper path | 57 | | evidence completeness | 29 |
| JVM end-to-end paper path | 88 | | restart/recovery | 50 |
| duplicate protection | 71 | | | |

**This is a presence check, not a strength check.** What establishes strength is the mutation
evidence recorded per section — a count of fixtures proves only that the area is not silent.

## 13. CONTINUATION CHECKPOINT — resume here

*Kept current. If a session ends, resume from this section rather than re-investigating.*

**Commit:** `d08c397` on `main`, pushed to `origin/mogo-main`, **0 ahead / 0 behind**.
Working tree clean apart from the pre-existing untracked `MOGO-019-ALEX-IG-CASE-002-REPORT.md`.

**Gates:** canonical **25** suites **1,706 / 1,706** · protected drift **0** against the
**v12.21.0** baseline (63 functions, 4 constants). App version **12.21.3**.

**Shipped since the last checkpoint** — every one found by adversarial mutation against a *green*
gate, never by the gate itself:

| | |
|---|---|
| `v12.21.1` §17.2 | the health check **could not report unhealthy**. `reconciliationStatus` consulted 10 of 19 detectors, so a ledger with account positions having **no journal record at all** signed off as `CLEAN`. Deleting an entire detector, and forcing the verdict permanently CLEAN, each killed **0** of 1,623 fixtures. +15 |
| `v12.21.2` §17.4 | the evidence completeness contract was **a comment with nothing behind it** — a `LIVE_TRIGGER` rejection could claim `COMPLETE`. Now refused *and surfaced*. +7 |
| `v12.21.3` §17.3 | a system **dead for three hours reported itself healthy** — no trailing-gap term. Optional `nowMs`; `ongoingOutage: null` means *not asked*. +4 |
| §16.5b | JVM close math — 18/18 acceptance mutations now die (was 0). +27 |
| §15.9 | detection surface — **52 of 53** now die; `AG-21` proven semantically equivalent. +13 |

### Governance decisions already authorized and DONE — do not re-litigate

| Decision | State |
|---|---|
| D1 · ALEX H4/D/W completeness gate | done (§9.2) |
| D2+3 · stable economic identity + decided-authority | done (§9.3) |
| D4 · JVM candidate-rejection diagnostic | done (§9.4) |
| Chart/AOI fidelity (completion items 3 and 5) | done (§10.6) |
| JVM completeness parity | done (§12) |

Protected functions changed across the whole milestone: **`checkAutoTrades`** (D4) and
**`evaluateLiveTrigger`** (JVM parity). Nothing else. Each was re-baselined deliberately, with the
drift check run first as a positive control.

### Standing constraints — unchanged

PAPER ONLY · live money **NOT AUTHORIZED** · TJR **RESEARCH ONLY**, no paper authority, untouched ·
frozen ALEX and JVM economic semantics preserved (no confluence, threshold, setup definition,
pattern, entry, stop, target, filter, risk, sizing or exclusion altered) · **the live campaign has
never been reloaded**, and a reload remains an operator action requiring broker credentials (§R4).

### In flight at checkpoint time

**Nothing is in flight.** Every audit and agent has returned and been independently re-verified.
`v1237` is 83 fixtures. The two audit agents that died at the usage limit were recovered from their
own scratchpad logs rather than re-run — their work had completed before they died.

### ⚠️ Methodology note that cost real time — read before running mutations (§15.10)

**One driver, one directory.** I ran a re-score twice concurrently over the same working copy; the
two processes' mutate/restore cycles interleaved and produced a **perfect off-by-one attribution
shift**, i.e. 11 false survivors out of 53. Also: `cp -R tests dest/tests` **nests** as
`dest/tests/tests` when the destination exists, silently running the old suite. Rebuild the
scratchpad copy with `rm -rf` first; never refresh it in place. Cross-check each stored result
against its own printed log line.

### 🔴🔴 OPEN GOVERNANCE ITEM AWAITING JOE — duplicate trade IDs (§16.6)

`openPaperPosition` mints `id = Date.now() + random(1000)`; two opens in the same millisecond collide
at ~1/1000, `checkAutoTrades` opens via `Promise.all` so that is routine, and `closePaperPosition`
resolves by `findIndex(p => p.id === id)` — **so a collision closes the wrong position.** Money, not
cosmetics. `openPaperPosition` is **protected** and no authorization covers it. Smallest fix: a
monotonic counter combined with the timestamp (the shape `generateDecisionEventId` already uses),
plus making `TEST J.2` deterministic. **Escalated, not taken.**

### 🔴 Largest open coverage item: the paper-execution layer (§16)

Of the original 47 surviving execution mutations: the **JVM close-math and exit-detection half is
closed** (§16.5b, 18/18), the **ALEX half is closed** (§16.5a), and the **three §16.4 ledger
survivors are closed** (§16.4a). The remainder are the reporting-only ones neither agent's brief
covered.

> **Correction to an earlier version of this checkpoint.** It said "~29 remain open, chiefly the
> ledger/persistence survivors in §16.4". That was wrong on both counts: §16.4 named only **three**
> survivors, all now closed, and the remainder are spread across reporting surfaces rather than
> concentrated in the ledger. The ledger layer was, and remains, the best-covered code here.

### Open after this checkpoint

**One coverage item, and one escalation.**

1. **§16 reporting-only execution survivors** — the mutations neither execution agent's brief
   covered. **Not re-enumerated since those agents ran**, so treat the old "~29" as stale: the
   correct next step is to re-score the paper-lifecycle audit's 97-mutation set against the current
   1,706-fixture gate and work from *that* list, not from the original one.
2. **🔴 §16.6 duplicate trade IDs — awaiting Joe.** Unchanged. The fix is written and validated.

Everything else in §15, §16.4, §17.2, §17.3, §17.4 and §17.5 is closed and mutation-verified against
a controlled pre/post comparison.

### Closed since the previous checkpoint

| | |
|---|---|
| §15.9 | detection surface — **52 of 53** die; `AG-21` proven semantically equivalent |
| §16.4a | the three ledger survivors — version *advance*, post-commit `save()`, drawdown growth |
| §17.2a | the warning **surfaces** — four banners and the severity wording went from **0** kills to 1–2 each |
| §17.3 | the trailing-outage term (`v12.21.3`) **and** the card that renders it (`v12.21.4`) |
| §17.4a | the entry-day gate's FAIL path — five mutations, **0 → 1–2** each |
| §17.5 | two assertions that did not mean what they said (a fixture-quality fix, not new coverage) |

**Five of my own fixtures were caught being vacuous by mutation testing during this stretch** — a
"tie" that was not a tie in floating point, a duplicate-guard test that never reached the guard, a
`reasonText` test whose scenario had only one reason, an `async` fixture in a synchronous runner, and
a clock default sitting behind an `await` the harness cannot drain. Each is recorded where it
happened. **The gate never caught any of them; only mutation did.**

### The ALEX zone engine's own rules (§15.5b) — CLOSED

19 of 19 previously-surviving mutations now die, including the inverted break direction. Both other
copies of the counter-trend rule and `alexGFindSwingPoints` are covered too.

### Not yet re-examined with mutation testing

§8 marks these done on evidence gathered before the "anchored coverage" disease was understood.
Each should get the same mutation treatment before anything is called GREEN: market-data continuity;
ALEX and JVM end-to-end paper trading; position lifecycle, persistence and ledger/account
reconciliation; restart/recovery; diagnostics and observability.

### Known open items — not defects I have chosen to leave, but work not yet reached

| Item | Where |
|---|---|
| `EMPTY_PAGE` is trusted as exhaustion regardless of count (two-fault residual; mitigated by the identity layer) | §11.3 |
| `tradedSignals` present while positions **and** journal are both absent leaves the decided-authority blind | §11.3 |
| The comment at `index.html:9156` is false but sits inside the protected `detectSignals` | §10.6 |
| Remaining program: market-data continuity, ALEX/JVM end-to-end paper trading, position lifecycle, persistence, ledger/account reconciliation, restart/recovery, diagnostics | completion standard |

### Exact next action

Consume the two audit reports; fix what they find that does not cross a new governance boundary;
re-run gates; commit and push; then continue the completion program in the order above. **TJR
research completion does not begin until core reliability, scanner, charts, AOIs, ALEX and JVM have
all passed independent verification.**

**Do not declare GREEN because the gates are green.** Every defect this milestone found was found by
adversarial mutation against a *passing* suite.

---

## 14. Scanner cadence, coverage, concurrency and failure isolation (completion item 4)

Independent adversarial audit against `562f677`. It found a **demonstrated wrong trading outcome**,
which is the first concurrency defect in this milestone to change what ALEX actually trades rather
than what it reports.

### 14.1 🔴 Overlapping ticks re-rolled a rejection the design calls PERMANENT

`alexGLivePollTick` has no re-entrancy guard and is driven by `setInterval`. The duplicate gate is
consulted **before** the trade attempt, the decision is recorded only **after** it, and the attempt
suspends on `await fetchBidAsk` in between. Two in-flight ticks therefore both passed the gate for
the same `signalId`:

* tick 1 was blocked by the price-dependent entry-delay rule and recorded a **permanent** rejection;
* tick 2 — already past the gate — re-evaluated the **same setup** against a **fresh bid/ask** and
  **opened a real position the sequential path refuses.**

Measured: sequential `openPositions = 0` versus overlapping `openPositions = 1`, a $100-risk
position, with `ENTRY_MOVED = 1` **and** `TRADE_OPENED = 1` for one setup inside one H1 boundary, and
**zero** `STATE_SIGNAL_ALREADY_DECIDED` events.

**Why nothing caught it.** Every duplicate guard looks for an **existing position**, and tick 1 never
opened one. This is not a duplicate trade — it is an **extra** trade past a permanent rejection,
which is exactly why it survived everything this milestone hardened. It generalises to every gate
evaluated against live price or `Date.now()`: staleness, entry-day, entry-delay, invalid-stop, R:R.
Under overlap each was a coin flipped twice.

**Fixed** with an in-flight claim keyed on `signalId`, tested-and-set **synchronously** in the same
statement as the duplicate check and released in a `finally` around the await — the pattern already
shipped and proven for `closePaperPosition`'s `paperPositionsClosing` guard. It invents no policy: it
makes the documented *"decided a single time, never re-evaluated on a later poll"* contract actually
hold under overlap, so the concurrent path behaves exactly like the sequential one.

> **Governance judgment, stated so it can be overruled.** I treated this as *inside* the already
> authorized Decisions 2+3 remediation, whose stated purpose is that the same economic setup is not
> reconsidered. The concurrency hole means the authorized decided-authority does not actually hold;
> closing it completes that work rather than deciding something new. It is also the conservative
> direction — it removes a trade rather than adding one.

**No re-entrancy guard was added to the tick.** That would suppress polls that today genuinely run —
including the exit monitoring in `alexGCheckLivePositions` — and would silently reduce scans per
hour, the very number §14.2 says must not change silently. It is **not** a neutral change and was not
made.

CONCUR-1..6, mutation-proven twice: removing the claim reproduces the defect exactly, and *moving the
claim to after the await* reproduces it identically — proving the claim must be **synchronous**, not
merely present.

**JVM does not have this defect**, and the asymmetry is worth recording: JVM has no permanent
per-signal rejection, `evaluateLiveTrigger` is re-derived every sweep anyway, and `checkAutoTrades`'
post-await re-check plus `openPaperPosition` are a single await-free block, with
`tradedToday[oPair]` capping it at one trade per pair per day regardless.

### 14.2 Failure isolation, accounting and a leaked timer — all fixed

| Defect | Effect |
|---|---|
| `scanPair` had **no try/catch** and was dispatched bare into `Promise.all` | One instrument throwing rejected its chunk, aborted every remaining chunk, and skipped `checkPaperPositions`, `checkAutoTrades` **and** `runManualReviewScan` for the whole sweep. **One instrument's display fault suppressed the entire trade pass.** |
| `renderAlexGLivePanel()` sat outside every `try`, inside a function awaited **before** the pair loop | A panel repaint throwing left **all twelve instruments unevaluated** |
| `__obsSkipped` is only pushed from inside the pair loop | On any pre-loop abort the ledger reported `instrumentsSkipped:[]` beside `instrumentsConfigured:12` — **0 of 12 accounted for**, the same unanswerable-coverage asymmetry closed for JVM in §2.14a and left open here |
| `disconnect()` cleared `scanInterval` and `countdownInterval` but not `autoScanTimer` | `initAll` then assigned a **new** hourly timer over the handle, stranding the old one unstoppable. Every disconnect/reconnect cycle permanently added one top-down scan per hour — and that scan writes `scanData[pair].bucket`, which is `checkAutoTrades`' eligibility gate |

Fixture `L15` caught my first attempt at the accounting fix — it asserts by source inspection that
the ledger seam call is the first statement inside its own `try`, and I had inserted ahead of it.
It was right to.

### 14.3 What the audit confirmed is already sound

Every fetch primitive ends in `catch{return null}`, so a rejected fetch, non-OK response or malformed
JSON cannot throw into either engine. **All 24 snapshot→mutate→commit→rollback critical sections in
the file contain zero `await`** — mechanically verified — so there is no lost update and no
resurrection. JVM's 35-instrument chunking is an exact partition with every instrument accounted for
on every path. `structuralAOICache`/`structuralAOIInflight`, the decided-authority maps and the
tick-stamped pipeline buffer are all safe under overlap. **No duplicate paper position was reachable
through any interleaving the auditor could construct** — the residual damage was the extra trade in
§14.1, not duplication.

### 14.4 Coverage — CLOSED

All four §14.2 fixes shipped **without coverage**, which is precisely the disease this milestone
keeps finding. 22 fixtures added (1,446 → 1,468). Every acceptance mutation was first confirmed
**green on the pre-existing gate**, so the audit's claim was independently reproduced rather than
taken on trust:

| Mutation | Pre-existing gate | Now |
|---|---|---|
| remove the per-dispatch `scanPair` `.catch()` | **1,446/1,446 green** | JVMISO-1..4 |
| unwrap `renderAlexGLivePanel()` | **green** | TICKISO-1, 2 |
| delete the ledger accounting block | **green** | LEDGER-2 |
| remove `clearInterval` from `disconnect()` | **green** | JVMTMR-1 |
| remove the `initAll` timer guard | **green** | JVMTMR-2 |

`JVMISO-4` is the one that matters: with a fault injected at `bestConfluence` for an
`ALL_PAIRS`-only instrument — so it throws inside the **real, unstubbed** `scanPair` — the trade pass
is still reached and 8 real positions still open.

**Three guards that were protected only by the drift byte-check now have behavioural fixtures:**
`checkAutoTrades`' post-await re-check (**each half isolated**, so removing either alone dies),
`paperPositionsClosing`, and the four "observation must never reach the trading path" `catch` blocks —
asserted in comments at four sites and tested at none. *A drift check proves the bytes did not
change; it does not prove the guard works.*

**Honestly not claimed**, and recorded in the fixture comments rather than overstated: `JVMTMR-0` is
a harness control, not a code claim; `JVMCLOSE-1` does **not** discriminate the concurrent-close
guard because the pre-existing `idx2` re-validation already prevents a second record — only
`JVMCLOSE-2` does; and `LEDGER-1`'s killer is already caught by the pre-existing `L2`.

**Still open:** the `DISPATCHED_NO_RESULT` residual — a sweep aborting with its own `scanPair`
promises in flight under-reports its own coverage. Pre-existing, fail-closed, documented in code,
and unpinned by any fixture.

* **Cadence still has no fixture** beyond the timer-leak guards: interval *periods* and the
  extra-sweep triggers remain changeable with a green gate.
* MAE/MFE mutations on a `pos` held across a concurrent `alexGAccount` rollback are discarded
  (`alexGCloseLivePosition` is **protected**; recorded as a residual, not touched).

---

## 15. 🔴 Detection-surface coverage (completion item 6) — the largest gap in the milestone

Independent adversarial audit: **117 proven-applied behaviour-changing mutations across the entire
detection surface. 64 kill ZERO fixtures out of 1,440.** Three are provably equivalent mutants, so
**61 genuinely uncovered trading rules — 54% of the non-equivalent surface.**

**These are not production defects. The rules are correct; they are simply not protected.** Any of
them could be changed tomorrow, by anyone, and every gate would stay green.

### 15.1 The structural cause

**Only 6 of 24 suites ever kill anything, and every kill is a second-order consequence of one
scenario ceasing to fire.** There is not one fixture in the repository that asserts a detection
function's own output value against crafted input.

Blinding `computeAOI` entirely, zeroing `scoreConfluence`, emptying `detectSignals`, inverting
`getBias`, raising `ALERT_THRESHOLD` to 95 and zeroing `WEIGHTS.engulf` all kill **the same
37-fixture set** — the single engineered "textbook bullish continuation" in `run_v1233`. Every
organic ALEX kill is the same 39-fixture block — one qualifying repeated-reaction setup.

> **The detection surface is not covered, it is ANCHORED.** Two hand-built scenarios hold up 1,440
> fixtures. Anything that does not extinguish one of them is invisible.

### 15.2 Severity 1 — silently changes which trades are taken, or at what price

| # | Uncovered rule | Mutation that survives |
|---|---|---|
| 1 | **The counter-trend block — no fixture at all, on either side** | `biasMatch` forced always-true; and the entry trigger no longer required to match bias. Directly contradicts `RULES.entry`: *"Never enter against confirmed top-down bias."* → **trades in the wrong direction** |
| 2 | **R:R 1.99 minimum** | 1.99 → 1.50, and → 2.99 |
| 3 | **`ALERT_THRESHOLD` = 55** | 55 → 56 and → 54, and the `<`→`<=` boundary flip. Only a move to 95 is felt |
| 4 | **The AOI 3-touch rule** — *"fewer than 3 = no AOI, move on"* | 3+ → 2+, and → 4+ |
| 5 | **Engulfing confirmation** — *"no break, no trade"* | the requirement deleted outright |
| 6 | **ALEX `qualificationClose` from the wrong candle** | → wrong entry price on every live ALEX trade, and it silently defeats `maxLiveEntryDelayPips` |
| 7 | **ALEX break DIRECTION inverted** | `brokenDirection` drives break-and-retest direction → **buys where it should sell** |
| 8 | **Stop/target inputs** | 7→20 pip stop buffer; `stopATRBuffer`; `minRR` |
| 9 | **AOI direction swaps** | confluence credits a long for sitting at *resistance* |
| 10 | **`maxLiveEntryDelayPips` boundary** | a fill exactly at 5 pips flips accept↔reject |

### 15.3 Three fixture anti-patterns this exposed

* **The drift check wearing a fixture costume.** Ten `RULES_ALEXG` zone/risk constants die *only* to
  `v127` fixtures whose failure text is *"expected 0.5, got 1"* — they read the constant and compare
  it to a hard-coded number. Set `minRR` to 1.0 and the only objection is a fixture asserting that
  `minRR` is 2.0. **Not one fixture observes a different trading outcome.** These must stop being
  counted as rule coverage; `regression-baseline.json` already does that job, and better.
* **Negative controls that could never have fired.** `JVM-2` and `JVM-29` assert silence against a
  flat series — but emptying `detectSignals` entirely kills 36 fixtures and *not those two*. This is
  the identical defect corrected earlier in this same suite; the correction was applied to the data
  contract and never extended to the rules.
* **An assertion true for every possible input.** The only direct `findSwingPoints` fixture asserts
  `swingHighs.length + swingLows.length >= 0`.

### 15.4 What is genuinely well built — and is the model to copy

`v128`'s B3/B4 falsify the two ALEX setup qualifiers by flipping **exactly one field** off a passing
baseline, eight and four times. That discipline is why six separate break-and-retest and
repeated-reaction mutations all die. And `DECIDED-9` pins the staleness boundary to the millisecond —
**the only threshold in the entire system with a real at-boundary control**, and it catches a
`>`→`>=` flip nothing else in 1,440 fixtures would.

The team knows how to do this. It was applied to two functions out of the whole surface.

### 15.5a Severity-1 coverage — CLOSED (`tests/v1237_detection_controls_tests.js`)

A new dedicated suite, **46 fixtures, 45 mutations, 45 killed, 0 survivors** — each proven applied
(anchor unique, byte diff) and scored against the **whole gate**. Gate is now
**25 suites · 1,514 / 1,514 · drift 0**.

Covered: the counter-trend block (S1), R:R 1.99 (S2), `ALERT_THRESHOLD` (S3), the AOI 3-touch rule
(S4), pattern thresholds — wick, doji, engulf swallow, both engulf colour requirements, both MSB
close requirements (S5), `getSession` window edges (S6), the `getBias` table (S7), **item-level**
confluence including the AOI side-swap and all seven `WEIGHTS` terms (S8), swing detection including
the equal-neighbour boundary and blindness to highs (S9), `alexGZoneRole`'s inclusive edges (S10),
and the `maxLiveEntryDelayPips` boundary (S11).

**Independently re-verified here, not taken on trust:** deleting `&& s.biasMatch` from
`evaluateLiveTrigger`'s entry-trigger predicate now kills `BIAS-BLOCK-3` — *"a bullish trigger
against a confirmed Bearish top-down bias must NOT fire — expected false, got true"*. That rule
previously had **no control of any kind, on either side**.

**Three disclosures worth more than the fixtures themselves:**

* **One of the new fixtures was itself vacuous, and was caught before shipping.** `WEIGHTS.aoi 20→15`
  killed nothing, because every confluence fixture compared an item's points against `WEIGHTS.aoi`
  *itself* — a self-referential assertion true for any value. `CONFITEM-0` now pins all seven literals
  plus the identity that the best attainable score is exactly 100, and all seven weight mutations die.
* **The audit's own S6 recipe was wrong.** It asked for `21:00 → active===false`; the frozen New York
  branch is `utcM>=1200 && utcM<2100` — 2100 *minutes* — so 21:00 is New York and active, and
  Off-hours is 00:00–07:59 only. The fixture asserts the **frozen behaviour** and records the
  discrepancy; writing to the recipe would have demanded a production change to satisfy a test.
* **`ALERT_THRESHOLD` 55→54 is an equivalent mutant behaviourally.** Confluence totals are sums of the
  frozen weights, so only 39 values are reachable and neither 54 nor 56 is among them. 55→56 *is*
  killable; 55→54 changes no verdict and is caught only by pinning the constant — and that fixture
  derives the reachable lattice from the live `WEIGHTS`, so it also fails if any weight ever makes 54
  or 56 reachable.

### 15.5b The ALEX zone engine's own rules — CLOSED

24 fixtures added to the same suite (46 → 70). **19 of 19 previously-surviving mutations now die**,
each scored against the whole gate, each proven applied with `index.html` restored and hash-verified
after every run. Gate: **25 suites · 1,538 / 1,538 · drift 0**.

Killed, all of which previously survived all 1,514 fixtures: displacement threshold and its `>=`
boundary; same-interaction dedup; break-confirmation count; **break direction inverted**; the
wick-only penetration side (a bonus find, not on the brief); the choppy boundary; prior-role
inference; `zoneStrength` tiers; inclusive touch bounds; `qualificationClose` taken from the previous
candle; the same-interaction gap; the swing lookback-edge guard; blindness to swing highs; cluster
tolerance; and highs sharing a low cluster. **Independently re-verified here:** inverting
`zone.brokenDirection` now kills ZONE-Z3-1 and ZONE-Z5-1/2/3/4 — before this work it killed nothing.

**Both remaining copies of the counter-trend rule are now covered too** —
`evaluateSetupFullBreakdownCore` and both gates inside `simulateTrueMTFReplay` — as is
`alexGFindSwingPoints`, the parallel copy of `findSwingPoints`.

**How the series are built, because it is the part that makes the boundary fixtures possible:** every
bar's range is exactly `2^-10` with each close inside the next bar's range, so the frozen `calcATR`
returns exactly `2^-10` with no floating-point residue. The displacement threshold is then exactly
`2^-12`, and a candle can sit *exactly* on it — which is the only way to kill a `>=`→`>` flip. The
engine decides everything after that.

**Three honesty notes from that work, each of which I'd rather have than a clean sweep:**

* **One recipe I supplied was not constructible, and the agent said so instead of faking it.** "Two
  swing lows 3 bars apart → one touch" cannot exist: with lookback 3, a swing low at bar *j* requires
  the next three lows to be higher, while a swing low at *j+3* requires the opposite. Two same-type
  anchors can never be within `lookback` bars in one array. But the dedup rule is **not** an
  equivalent mutant — `alexGRunSetupEngine` re-runs over a rolling window every poll while
  `alexGZoneState` persists, so the same interaction is re-offered at a bar index that shifts by one
  each time a candle closes. The fixtures exercise exactly that, and only the shifted variant kills
  the gap-to-zero mutation.
* **One listed gap was already covered.** The closest real rule — inverting the anchor price selection
  — killed 39 existing fixtures before anything was written. No new coverage was needed, and none was
  invented to look productive.
* **The one arguably self-referential assertion is isolated and labelled** a precondition on the
  fixture's own inputs, with the actual verdict asserted separately — the trap that caught the
  previous agent.

### 15.5c Still uncovered, and named rather than implied

* **Not yet re-examined with mutation testing:** market-data continuity; ALEX and JVM end-to-end
  paper trading; position lifecycle, persistence and ledger/account reconciliation; restart/recovery;
  diagnostics and observability. §8 marks these done, but on evidence gathered *before* the anchored-
  coverage problem was understood. Each needs the same treatment before anything is called GREEN.

### 15.5 Disposition

This is **test debt on frozen, correct rules**, so it crosses no governance boundary — writing
fixtures changes no behaviour. It is being closed in severity order, starting with the counter-trend
block, which is the one rule with no control of any kind on either side.

The constraint holds throughout: **the candles may be constructed; the verdict must not be.** No
fixture may stub, override or force a protected function's outcome.

---

### 15.9 Detection surface CLOSED — 52 of 53, and one proven unkillable

The `v1237` suite is now **83 fixtures**. Scored serially in a clean directory, one driver, one
working copy:

| | mutations |
|---|---|
| originally uncovered (killed 0 of 1,440) | **53** |
| now killed | **52** |
| proven semantically equivalent | **1** |

**The one that remains is not a gap.** `AG-21` swaps the order in which break-retest and
repeated-reaction are evaluated. `alexGEvaluateRepeatedReaction` requires `zone.status==='validated'`
and `alexGEvaluateBreakRetest` requires `'broken'` — **mutually exclusive by construction**, so no
zone can satisfy both and the order cannot change any outcome. No honest fixture can kill it.
`PRECEDENCE-1` instead pins the *invariant that makes it equivalent*, in both directions, so if
either status guard were ever relaxed, precedence would start deciding real setups and this fixture
would notice.

The last eleven closed: the AOI clustering **tolerance** (three touches spread over 10 pips are one
zone at the real tolerance and three separate levels at a hundredth of it — every pre-existing
3-touch fixture used touches at the *same* price, which cluster at any tolerance and so could never
discriminate); the `detectSignals` AOI badge; the **partial** wick credit and its exclusive 0.35
boundary; the swing window's outermost neighbour; nearest-cluster assignment and its two tie-breaks;
the inclusive same-interaction window; the 10-candle usable floor; the live trigger's 25-candle
floor; that the engine evaluates H4/D/W **at all**; and that an HTF candle closing *exactly* on the
H1 close is consumed in that step rather than left one candle stale forever.

> **Two of my own fixtures passed for the wrong reason and mutation testing caught both.**
> `SC-WICK-2`'s first "tie" was not a tie — `1.10050−1.10000` and `1.10000−1.09950` are not equal in
> binary floating point, so it was really a nearest-wins case proving nothing about the tie-break
> cascade; rebuilt from identical centres. And **`DUPE-1` did not touch the guard it was named
> for**: re-running the engine never reaches `alexGCreateSetupRecord` twice for the same touch,
> because an upstream mechanism already prevents it, so the duplicate guard could be deleted
> outright with the fixture still green. It now drives the guard **directly**, with the real zone and
> touch the engine just produced, plus a positive control proving the same call records against
> empty state.

### 15.10 ⚠️ A re-score I published nothing from, because it was invalid

I ran the 53-mutation re-score twice concurrently — the first launched with `nohup … &` *inside* an
already-backgrounded call, which I wrongly concluded had died. Both processes mutated and restored
**the same working copy** while running gates, so one wrote mutant *i* while the other's gate scored
it as *i−1*. The results were a **perfect off-by-one shift**: every mutation credited with its
neighbour's kill count, yielding **11 false survivors out of 53**.

The tell was a stored record contradicting its own log line — one mutation's JSON entry held a
different mutation's failure and `drift_detected:true`. Re-run serially, **all four survivors I
spot-checked first actually died.**

This is the same disease as an unapplied mutation: *the gate that ran was not the gate you think you
scored.* Proving a mutation applied is necessary but not sufficient — it must still be applied when
the suite executes. **One driver, one directory.** (A second harness error found the same way: `cp -R
tests dest/tests` nests as `dest/tests/tests` when the destination exists, silently running the old
suite. Rebuild the copy; never refresh it in place.)

## 16. 🔴 Paper-trade execution coverage — the worst gap found, and it is where the money is

Independent adversarial audit. **96 behaviour-changing mutations scored against the whole
1,538-fixture gate. 47 killed ZERO fixtures.** Unlike §15 this is not spread evenly — the
concentration is precisely on *what price a position closes at, which side of the book it closes on,
whether it closes at all, how large it is, and how an ambiguous candle is resolved.*

**The auditor established this is not a harness artifact.** Positive control: making
`openPaperPosition` return an error for every input kills 37 fixtures — the gate *does* observe
lifecycle behaviour. The uncovered verdicts below are real.

### 16.1 Two protected functions have NO execution coverage whatsoever

`checkPaperPositions` and `alexGReconstructExitFromCandles` can each be **deleted outright** and the
gate still reports 1,538/1,538. Statically confirmed: `alexGReconstructExitFromCandles` appears in
zero files under `tests/`; `checkPaperPositions` appears once, in a comment.

### 16.2 JVM close arithmetic — entirely uncovered

Every one of these kills nothing: **buy closes on the ask and sell on the bid (sides swapped)**;
**exit filled at mid**, erasing the simulated spread cost; the move-pips sign inverted; **the P&L
sign flipped, so every win becomes a loss**; Win/Loss classification inverted; the recorded
`exitPrice` replaced by the entry price; the post-await re-validation removed; a failed-commit
rollback skipped so the close applies in memory anyway; take-profit and stop-loss reasons swapped;
and a missing pip value no longer blocking the close.

**Why it looked covered.** `JVMCLOSE-1` drives a real close and asserts a balance — but its clause is
`balance === balBefore + closedPos.pnl`, **comparing two outputs of the same computation.** It dies
only if the balance update diverges from the recorded P&L, and is blind to a wrong P&L, a wrong exit
price, a wrong side or a wrong result label. It is a consistency check, not an assertion about money.
Everything else claiming to cover the close is **source-text assertion** — `getSource(...)` matching
return-statement strings, which all thirteen mutations leave intact. The drift check wearing a
fixture costume, again.

**And the stated reason for the gap is no longer true.** `docs/TESTING.md` and the paper-audit suite
declare the close math permanently unverifiable offline because osascript "never drains the microtask
queue". `run_v1233` disproves that — it is an async runner with a pricing stub, it awaits real
closes, and two mutations died *because* the post-await balance write was observed. The deferral to
"Phase 11 live browser" rests on a limitation a later suite in this same repository already
superseded.

### 16.3 ALEX — sizing, stops and the ambiguity rule

| Uncovered | Consequence |
|---|---|
| `riskAmount` **100× too large** (`riskPercent` not divided by 100) | every position sized 100× intended risk |
| position size doubled | — |
| ATR stop buffer applied on the **wrong side** of the zone | `E2E-7` only asserts `stop < entry`, which stays true |
| snapshot exit side swapped / priced at mid | — |
| **MAE and MFE allowed to SHRINK** from recorded extremes | the only "coverage" is a source-substring check |
| reconstruction walks the wrong executable side | — |
| the same-candle ambiguity branch removed, or resolved as a **Win at target** instead of conservatively as a Loss | **turns losses into wins** |
| the replay engine's ambiguous-candle rule flippable Loss→Win | corrupts the research record that governs live rules |

**Every ALEX P&L assertion is a LONG.** Both covered scenarios are buys, so inverting sell-side P&L,
entry side, exit side or reconstruction side kills nothing.

### 16.4 What IS genuinely well covered — attacked harder and held

The **ledger, commit, rollback, version-guard and INC-001 persistence layers.** Version guards,
rollback paths, INC-001 blocking, commit contracts, derived balance and reconciliation all die hard
(one mutation kills 30 fixtures, another 13). The auditor extended past the three reconciliation
probes I ran myself, and the extensions die too. Three survivors: the JVM version never *advancing*
(the guard's rejection half is covered, its advance half is not), `save()`/`saveAlexGRest()` never
called after a successful commit, and max-drawdown never growing.

### 16.4a The three §16.4 survivors — CLOSED (and one of them was the wrong function)

| Survivor | Now killed by |
|---|---|
| the JVM version guard's **advance** half (its rejection half was covered) | `Ledger.V1–V3` — advances by exactly 1 per successful commit, twice in a row, and **not at all** on a rejected one |
| `save()` / `saveAlexGRest()` never called after a successful commit | `Ledger.S1–S3` — the non-ledger state reaches storage on success, and **none of it** on a rejection |
| max drawdown never growing | `Replay.DD1–DD5` |

> **The drawdown survivor was not the function I first assumed.** I wrote four fixtures against
> `alexGComputeEquityStats` — and pinning its `maxDD` to zero kills **six** fixtures across three
> suites, so it was already covered and my fixtures were additive, not the closure. The two
> implementations that genuinely could be pinned to zero with the whole gate silent are the
> **replay** statistics: `alexGComputeReplayStats` (ALEX research replay) and `computeReplayStats`
> (TRUE MTF replay). **Three separate copies of the same peak-to-trough arithmetic is itself the
> risk**, and each now has its own control, including a positive control proving an only-rising
> curve reports zero rather than the figure being a constant that happens to match.

The version-guard mutation is anchored on the JVM-only error text above it, because the ALEX block
five lines away is otherwise byte-identical and would have been hit by accident.

### 16.5 End-to-end stops at "a position opened"

**No fixture anywhere drives a trade from signal to a closed record with a verified exit price, R
multiple, P&L and balance — for either engine.** `run_v1236`'s `closeOpenPosition()` **hand-forges
the close** (`exitPrice=target; result="Win"; resultR=2; pnl=200`) and never calls
`alexGCloseLivePosition`. The one fixture that does close through the real path asserts only
structure — no price, no result, no R, no P&L, no balance — and deliberately routes around the exit
reconstruction by forcing its history fetch to fail. The JVM paper-audit suite **re-implements the
close inside the fixture** and then tests the commit: the commit path is covered, the arithmetic that
should have produced those numbers is never compared against them.

### 16.5a ALEX execution coverage — CLOSED

56 fixtures added. **23 of 24 mutations survived the pristine 1,538-fixture gate; all 24 die now.**
Each proven applied (anchor unique, byte diff), each scored against the whole gate.

| Previously invisible | Now killed by |
|---|---|
| **`alexGReconstructExitFromCandles` deleted outright** | 10 fixtures |
| the same-candle ambiguity resolved as a **Win at target** instead of conservatively as a Loss | F3.5/6/7 — and the replay engine's identical flip, F3.11/12/15 |
| buy/sell executable exit sides swapped; sell reading the bid; exit priced at **mid** | 9 fixtures each |
| **MAE and MFE allowed to shrink**, on *both* the snapshot and reconstruction paths | F4.3/6/8/9/14 |
| **`riskAmount` 100× too large** (`riskPercent` not divided by 100) | SIZE-1/2/3, SELL-4 |
| position size doubled; **ATR stop buffer on the wrong side of the zone** | SIZE-2/3/4/5, SELL-3/4 |
| **the entire ALEX sell branch** — every prior P&L assertion was a long | SELL-1..5, ALEX.5..10 |
| **`fxhub_alexg_auto` never loaded on restart** — a restart re-opening a completed trade | RESTART-1/2 |
| `fxhub_alexg_journal` never loaded on restart | RESTART-4/5/6 |

**Independently re-verified here:** making `riskAmount` 100× too large now kills SIZE-1, SIZE-2,
SIZE-3 and SELL-4. Before this work it killed nothing — a one-character change would have sized every
ALEX position at a hundred times its intended risk with a fully green gate.

The sell-side coverage is genuinely organic: the H1 series is a **price reflection** about 1.1000, so
the frozen zone engine validates a *resistance* zone and derives `sell` **on its own**. No direction,
verdict or outcome is injected. And the restart fixtures write real storage keys, reset
`tradedSignals` to an **empty** map that is never re-seeded, and call the real `loadAlexGSaved()` —
with positive controls one variable away that **do** open a second position.

**Three honest disclosures from that work:**
* One mutation — swapping *both* fill sides — turned out to be **already caught** incidentally by the
  pre-existing `ENTRYDELAY-2/3`. Reported as found rather than claimed as a new kill. The *sell-only*
  variant genuinely was uncovered and now dies.
* **Sell-side *exit* through the live poll loop is covered only at unit level.** There is no organic
  end-to-end sell that opens *and* is closed by `alexGCheckLivePositions`.
* **`alexGFetchExecutableCandles` remains uncovered** — the async wrapper feeding the reconstruction.
  Its pagination, its `null`-on-failure contract, and the caller's "do not advance
  `lastExitCheckTimestamp` on failure" rule have no fixture. A separate gap, not opened.

### 16.5b JVM close math and automatic exit detection — CLOSED

27 fixtures (suite 78 → 105). **All 18 acceptance mutations survived the pristine gate; all 18 die
now.** Scored as a controlled experiment — every other suite pinned to one snapshot, only the JVM
suite differing — with each mutation proven applied by unique anchor, byte delta and distinct sha256.

Now killed: buy closing on the **ask** (16 fixtures), exit at **mid** (16), the move-pips sign, **the
P&L sign flipped so every win books as a loss** (13), manual Win/Loss inverted, the break-even
epsilon, `exitPrice` replaced by the entry price, the post-await re-validation removed, the rollback
skipped, TAKE_PROFIT↔STOP_LOSS swapped, a missing pip value no longer blocking the close,
**sell-side-only** P&L sign, `hitTarget`/`hitStop` inverted, the same-tick ordering flipped, the
auto-close labels swapped, and **`checkPaperPositions` reduced to a bare `return;`**.

**Independently re-verified here:** making a buy close on the ask now kills 16 fixtures. Before this
work it killed nothing.

The assertions are deliberately built to defeat the trap that hid this gap: each compares against a
**literal the fixture chose** — `exitPrice === 1.10500` (explicitly *not* the ask 1.10530, not the mid
1.10515), `pnl === 250` hand-computed, `balance === 10250` asserted against the constant rather than
`before + pnl`. `JVMEXIT-*` uses a **pure pass-through spy** that records the arguments handed to
`closePaperPosition` and returns its real promise unaltered, so both the call and the resulting record
are asserted without stubbing a verdict.

**Three disclosures the agent made rather than glossing:**
* **The ambiguity fixture uses a deliberately degenerate bracket** (stop *above* target). That is
  unavoidable: for a coherent buy (`stop < entry < target`) no single price can satisfy both crossing
  tests, so the target-first ordering is undetectable without it. Documented as degenerate in the
  fixture, it is exactly the state a mis-applied stop adjustment leaves behind, and it is the **only**
  thing that kills the reordering mutation.
* **Deleting the pip-value guard does not produce NaN** — `null` multiplies to zero, so the balance
  never moves. A balance assertion alone would have been **vacuous**; the kill comes from the position
  remaining open and the closed-record count.
* **~29 of the original 47 surviving mutations were outside this brief and remain open** — chiefly the
  ledger/persistence survivors in §16.4 and the remaining reporting-only ones.

### 16.5c Attribution correction

Commits `769a197` and `cbe3459` swept two agents' in-flight test files into commits whose messages
describe *other* work. The record: the `run_v1233` JVM close-math fixtures and the `run_v1236` /
`v_paper_trading_audit` ALEX execution fixtures were produced by those agents, not by the change each
commit is titled for. `index.html` was byte-identical across both, so no result was affected — but
staging with `-A` while agents are writing is the wrong habit, and paths are being staged explicitly
from here.

### 16.6 🔴 A REAL PRODUCTION DEFECT, not test debt — and a NEW governance boundary

`openPaperPosition` mints `id: Date.now() + Math.floor(Math.random()*1000)`. **Two opens in the same
millisecond collide with p ≈ 1/1000**, and `checkAutoTrades` opens via `Promise.all` across eligible
pairs, so same-millisecond opens are a normal occurrence rather than a contrivance.

`closePaperPosition` resolves its target by `findIndex(p => p.id === id)`. **A collision closes the
wrong position.** That is money-affecting, not cosmetic.

**The fixture that appears to guard this is worthless in BOTH directions**, which is worse than
having none. `TEST J.2`'s stated purpose is *"two distinct opens never collide on trade ID"*. During
the audit it **failed spuriously** against an unrelated mutation (a genuine collision,
`id1 = id2 = 1786748218934`) — and then, when the id was deliberately reduced to a bare `Date.now()`
so collisions became *systematic*, it **passed**. Whichever way the two opens happen to straddle a
millisecond boundary decides the result. It is not evidence of uniqueness in either direction, and it
will randomly redden the gate.

(The systematic-collision mutation *was* caught — but by `JVMCLOSE-1`, an unrelated fixture. The one
written to guard trade-id uniqueness did not notice.)

**`openPaperPosition` is PROTECTED, and no authorization covers this.** It is not a setup definition,
scoring rule, confluence, threshold, entry, stop, target, risk, sizing or economic-logic change — it
is identity generation — but it still requires a governed protected-function edit and a re-baseline.
**Escalated, not taken.**

**The fix is written and validated on a scratchpad copy, ready to apply the moment it is authorized.**

```js
let paperTradeIdSeq=0;
function paperNextTradeId(){                       // module scope, OUTSIDE the protected function
  const t=Date.now()*1000;
  paperTradeIdSeq=(t>paperTradeIdSeq)?t:paperTradeIdSeq+1;
  return paperTradeIdSeq;
}
```
The protected diff is then **one expression**: `id: Date.now()+Math.floor(Math.random()*1000)` →
`id: paperNextTradeId()`.

Constraints it had to satisfy, and does: the id must stay a **number** and must survive exact-equality
matching, because it is not only the close-lookup key — it also becomes the journal `tradeId` that
reconciliation and orphan detection match on (`p.id === r.tradeId`). Measured: 50,000 ids in a tight
burst produced **50,000 distinct**, strictly increasing, all safe integers, with ~229 years of
headroom below 2^53.

> **A first candidate of mine was wrong, and my own test caught it.** `Date.now()*1000 + (seq++ % 1000)`
> looked fine and passed the full gate at 1,538/1,538 — but a 5,000-id burst yielded only **2,000
> distinct**, because the modulo wraps after 1,000 opens in one millisecond. The gate could not have
> caught that either. The monotonic-clock form above has no wrap and no such ceiling.

`TEST J.2` should be replaced at the same time with a deterministic check — freeze the clock, open
twice, assert distinct — so it stops being a coin flip in both directions.

---

## 16A. TRADE-ID INTEGRITY — the authorized protected change (§16.6 closed)

**Owner-authorized**, narrowly scoped to identity generation. Recorded here in full because it is the
only protected-function change of this milestone that touches the paper-execution path.

### 16A.1 The defect, and why it was money rather than cosmetics

`openPaperPosition` minted `id: Date.now() + Math.floor(Math.random()*1000)`. Two opens in the same
millisecond collide with **p ≈ 1/1000**, and `checkAutoTrades` opens across eligible pairs via
`Promise.all`, so same-millisecond opens are ordinary rather than contrived. `closePaperPosition`
resolves its target with `findIndex(p => p.id === id)` — **a collision closes the wrong position** —
and the same value is the journal `tradeId` that reconciliation and orphan detection match on.

### 16A.2 The change: one expression, proven

```js
let paperTradeIdSeq=0;
function paperNextTradeId(){
  const t=Date.now()*1000;
  paperTradeIdSeq=(t>paperTradeIdSeq)?t:paperTradeIdSeq+1;
  return paperTradeIdSeq;
}
```

The protected diff is **one line**: `id:Date.now()+Math.floor(Math.random()*1000)` → `id:paperNextTradeId()`.

| | |
|---|---|
| pre-change `openPaperPosition` | sha1 `829154ba5b13e617f07e3bd5f5b6913408bf45d6`, length 3069 — **matches the committed baseline exactly**, confirming the pre-change state was pristine |
| post-change | sha1 `06a704e5ec56d37097bdeee21fb297649377db90`, length 3046 |
| lines changed inside the function | **1** |
| protected items flagged by the drift check | **exactly `openPaperPosition`, nothing else** |

Running the drift check *before* re-baselining is the positive control: it names the one function
intended to change, which independently proves the other 62 functions and 4 constants were untouched.
Sizing, entry, stop, target, direction, the zero-risk guard and the snapshot/rollback are
byte-identical.

### 16A.3 A second defect the fix would otherwise have introduced

A monotonic clock is monotonic **only while the clock is**. Across a restart the counter starts at 0,
so a system clock that moved **backwards** — an NTP correction, a hardware fault, a profile restored
from backup — would re-mint ids at or below already-persisted ones: the same wrong-position-closed
defect, through the back door. §17.3 already established that backwards intervals are a *recorded*
condition here, not a hypothetical.

`paperSeedTradeIdSeq()`, called at the end of `loadSaved()`, raises the floor above everything already
durable. It reads all three stores — open positions, closed positions and the journal — because an id
can legitimately exist in one without the others (that is what orphan detection exists to report).
**It is read-only: no id is rewritten and no migration occurs.**

### 16A.4 The rejected alternative, kept as a live control

`Date.now()*1000 + (seq++ % 1000)` was tried first. It **passed the entire gate** and is wrong: a
5,000-id burst yields only 2,000 distinct ids, because the modulo wraps after 1,000 opens inside one
millisecond — reintroducing the same collision at a higher threshold. `TradeID.5` keeps that form as
a **live control**, asserting the shipped generator does *not* behave like it, so a future
"simplification" back to any bounded within-ms term fails here instead of silently regressing.

### 16A.5 Evidence — 28 fixtures, every one against a FROZEN clock

The clock is frozen in every fixture, so "same millisecond" is **forced rather than hoped for**. The
old implementation's entire collision space was 1,000 ids per millisecond; these go 50× past it.

* **50,000 ids in one frozen millisecond → 50,000 distinct**, strictly increasing, all safe integers,
  ~229 years of headroom below `Number.MAX_SAFE_INTEGER`.
* **500 real positions** opened through the real engine in one millisecond → 500 distinct ids, 500
  distinct journal records, and `findIndex(p => p.id === id)` — the exact lookup `closePaperPosition`
  uses — resolves every one to **itself**.
* **The defect reproduced as a control**: force two ids equal and the same lookup resolves to the
  *wrong* position. Without that control, `TradeID.9` would be a claim rather than a demonstration.
* **Restart with the clock rewound an hour**: a clock-only generator would mint *below* the persisted
  id (asserted as a precondition); the durable floor defeats it.
* **ALEX vs JVM**: ALEX mints the *string* `AGT|<setupId>`, JVM a *number*. They cannot collide under
  the exact-equality matching every association uses — pinned so a future change making them
  type-compatible fails here.
* **200-position book**: no duplicate account ids, no duplicate journal trade ids, no orphan on either
  side, reconciliation `CLEAN`.

**`TEST J.2` replaced.** The original was worthless in both directions and its own parenthetical said
why — *"unique in practice"*. It ran two opens against the wall clock, so whichever side of a
millisecond boundary they landed on decided the result: during the audit it **failed spuriously**
against a genuine collision and then **passed** when the id was reduced to a bare `Date.now()` so
collisions became systematic. It is now deterministic.

### 16A.6 🔴 INDEPENDENT ADVERSARIAL VERIFICATION DEFEATED THE FIRST IMPLEMENTATION

The verifier's brief was to break it, not review it. **It did.** Every finding is fixed.

| Defeat | Mechanism | Fix |
|---|---|---|
| **A persisted id ≥ 2^53 makes every id in the session identical** | at 2^53, `seq+1 === seq`, so the increment is a **no-op forever**. Driven end-to-end: three positions, **one id**, **one journal record between them**, and the close lookup resolving to the wrong position | the floor requires `Number.isSafeInteger` |
| `1e300`, and a non-integer such as `…000.5` propagating a fractional part through every later id | `isFinite()` admits both | same |
| **One malformed store silently disabled the whole floor** | a single shared `try` — the *first* throw skipped the rest, leaving the floor at **0** while a real id sat in the journal | **one `try` per store** |
| The generator could not report its own failure | every other integrity failure here records an error; this one degraded silently and permanently | records a paper-engine error when the sequence leaves safe-integer range |
| Dead code | `[] || []` parses as a no-op and *reads* as null-protection while providing none; a `typeof` check on a same-scope `let` | removed |

**The floor was a new failure surface.** The old `Date.now()+random` construction was *immune* to all
of it — which is exactly why an unclamped floor is worse than no floor, and why this had to be found
by someone trying to break it rather than by me checking my own work.

**What held, under attack:** clock backwards mid-session; clock +1yr then back; `loadSaved()` again
mid-session; burst spill then the clock advancing into already-issued range; `NaN`/`Infinity`/`-1`/
`undefined`/`'abc'`/`{}`/`true` persisted; account-only reset then restart then rewind; the developer
test-trade generator; reconciliation restoring an orphan under a rewound clock; two tabs (the version
guard blocks the duplicate from reaching storage); and legacy ids loaded and used.

### 16A.7 Three ledger defects found while attacking the change

None is in the generator. All three are cases where a diagnostic goes blind **exactly when the
condition it exists to detect is present**. Diagnostic-only; no protected function.

* **`accountPositionsWithNoJournal` counted EXISTENCE, not cardinality.** Three positions sharing one
  id with a single journal record between them satisfied `some()` for all three and reported **zero**
  unjournalled — the detector for orphaned twins was green precisely in the case that creates them.
  Now a count. Reduces to the old behaviour exactly when ids are unique.
* **The duplicate counters used raw object keys.** A JS object key is always a string, so the number
  `5` and the string `"5"` were reported as **duplicates of each other** — a false positive turning
  the verdict red over two genuinely distinct records, while strict `===` treats them as different
  everywhere else. Now type-tagged; the reported output shape is unchanged.
* **`computeReconciliationPreview` matched by `String()`.** A brand-new live id could select a
  *different* historical record that stored the string form and **restore the wrong trade** — which
  moves real money in the paper account. Ambiguity now **fails closed**: neither is restored, and the
  reason names the ambiguity.

The floor also reads the two stores that outlive `confirmPaperResetFull` — trade notes (keyed
`JVMJ|<id>`) and the reconciliation audit — so a re-minted id can never inherit another trade's note
or be born already-reconciled.

### 16A.8 🔴 Five of my own fixtures were caught vacuous — three of them tautologies

The verifier's per-fixture mutation matrix found **three fixtures that could not fail at all**:

* **`TradeID.12`**, presented as the strongest evidence here, was the weakest: it deep-copied the
  account, **wrote the collision itself**, then ran a `findIndex` **written in the fixture** — an
  assertion about `Array.prototype.findIndex`, not about this application. It now forces the
  collision into the **real** account and drives the **real** ledger detector.
* **`TradeID.19`** compared a fixture string literal against a number. False for no possible id.
* **`TradeID.20`** asserted two journals were disjoint two lines after the fixture populated one.
* `TradeID.5`'s first clause and `TradeID.18`'s second were hand-computed constants — dropped.

And two proved the seeder *worked* while proving nothing about it being **wired**:



Both are the *"covered but wired to nothing"* class this project keeps producing:

* **Removing `paperSeedTradeIdSeq()` from `loadSaved()` killed nothing.** Every restart fixture called
  the seeder **directly**, proving the function works and proving nothing about it being *reached*.
  `TradeID.17a/b` now drive the real `loadSaved()` over real persisted bytes.
* **Ignoring `closedPositions`, and separately `openPositions`, each killed nothing** — the wiring
  fixture had the id in *both* stores, so it stayed green if either branch was deleted. `TradeID.17c/d`
  seed from one store at a time.

A third mutation reported nothing because its **anchor was not unique** (`return paperTradeIdSeq;`
appears in both functions). It was re-anchored, not counted — an unapplied mutation is not a survivor.

### 16A.9 Rebaseline — and the proof it hides nothing

**18 mutations, all killed**, including every one the verifier found uncovered.

| | |
|---|---|
| `openPaperPosition` | `829154ba…` (3069) → `06a704e5…` (3046) |
| `closePaperPosition` | `b03719e4…` (6075) → **unchanged** |
| `checkAutoTrades` | `01a78e29…` (1916) → **unchanged** |
| all other 60 functions + 4 constants | **unchanged** |

The rebaseline rewrote **one hash**. Every other recorded value in `regression-baseline.json` is
byte-identical to what it was before this change — which is the check that the rebaseline was not
used to launder unrelated drift. Gate **1,759/1,759**, drift **0** against the new v12.22.0 baseline.

### 16A.10 Was it the smallest correct solution?

The verifier's assessment, which I accept: **yes, and neither half is redundant.**

* **The floor is necessary.** Deleting it kills six fixtures: with the clock rewound one hour across
  a restart, a clock-only generator mints *below* an already-persisted id.
* **The clock is necessary.** A pure seeded counter would be correct until
  `confirmPaperResetFull` wipes every durable id — then it restarts at 1 and *unconditionally*
  reuses ids still live in trade notes, the reconciliation audit and the evidence store. The clock
  restarts above all history because it only moves forward.

**One correction the verifier made to my own justification, which I accept:** my code comment cited
§17.3 as evidence that backwards clocks are an *observed* condition here. That was overstated. §17.3
added the ability to **report** a backwards interval; it did not record one occurring. The comment is
corrected in place, and the justification now rests on the reproduction and the six dead fixtures.

---

## 17. Continuity, alignment and observability integrity (completion items 1, 2, 11)

Independent adversarial audit: **93 behaviour-changing mutations, 63 killed, 30 killed nothing.** A
healthier surface than detection (64/117) or execution (47/96) — but the survivors cluster in the
worst possible place: **the Paper Trading Health Check's headline verdict and its entire
balance-reconciliation arm cannot report unhealthy.**

### 17.1 ✅ The one I fixed immediately — a vacuous fixture guarding the identity-drift mechanism

`ALIGN-9` is titled *"every candle but the last closes EXACTLY at the next candle start (no duration
math)"* — and supplied a **perfectly regular hourly series**, where "next bar's start" and "start + 1h"
are the same number at every index. **The property it names was untestable against its own data.**
Verified: deleting the exact-close branch from `getCandleCloseTime` **entirely** left 27/27 passing.

This is not academic. That estimate/exact split is the documented mechanism by which `reactionId` and
`qualificationTimestamp` move ~48h at every weekend reopen — which re-anchors zone identity, and is
what drove the entire identity-drift workstream (§2.16, §2.17). **It was unpinned in both
directions:** nothing would have noticed if the estimate stopped being confined to the newest bar, or
if it spread to every bar.

Rebuilt on a **gap-bearing** series — the only shape where the two readings differ — plus `ALIGN-9b`
pinning that the estimate stays confined to the newest bar, and `ALIGN-9c` retaining the original
regular-series case. Both mutations now die.

> **My first fix was itself insufficient, and my own mutation test caught it.** I used
> `00:00 / 05:00 / 06:00` — but bars 1 and 2 are exactly an hour apart, so index 1 could not
> discriminate, and narrowing the exact branch to `i < length-2` still survived. Both gaps are now
> irregular (`00:00 / 05:00 / 09:00`). The lesson is the audit's own: a fixture's *data* decides what
> it can detect, not its title.

### 17.2 ✅ FIXED — the health check could not report unhealthy (v12.21.1)

Five mutations, none of which kill anything:

| Mutation | Effect |
|---|---|
| `reconciliationStatus` forced to `'CLEAN — no reconciliation issues detected'` | the verdict an operator pastes into a review is unfalsifiable |
| `balanceDifference = 0` unconditionally (JVM **and** ALEX) | — |
| **`expectedBalance = paperAccount.balance`** (JVM **and** ALEX) | `expectedBalance` exists to be an *independent* recomputation. Point it at `actual` and the check becomes `actual − actual === 0` — **a constant compared against itself, forever CLEAN** |

The last is the "drift check wearing a fixture costume" trap, except escaped into **production code**.
Why nothing catches it: the only assertions are `balanceDifference === 0` in two suites — **both
asserting the healthy value** — and `HealthCheck.6` asserts `CLEAN` on a deliberately clean, empty
account. **A positive control with no negative control anywhere; no fixture ever drives this function
to `ISSUES DETECTED`.**

**And a real production defect sits behind it.** `reconciliationStatus` consults `balanceDifference`,
duplicate account ids, newly-orphaned records and four mismatch arrays — but **omits**
`accountPositionsWithNoJournal`, `duplicateJournalTradeIds`, `closedJournalMissingPnl`,
`closedAccountMissingJournalClosure`, `invalidTimestamps`, `invalidPrices` and `missingStrategyId`. A
ledger with account positions that have **no journal record at all** currently reports
**"CLEAN — no reconciliation issues detected"**, and that line ends the copyable report.

---

**RESOLVED in v12.21.1.** The verdict is now assembled from a **named check per detector** and both
flips correctly and states *which* detectors fired — `ISSUES DETECTED — JVM account positions with no
journal record; invalid prices` — with the named list also returned as `reconciliationIssues` so a
fixture can assert **which** detector fired rather than merely that a string changed.

`legacyRecords` and `testArtifacts` are deliberately **excluded**: pre-v10.0 manual entries and
explicitly-tagged developer trades are expected states, and a verdict permanently stuck on ISSUES is
noise an operator learns to ignore — over-blocking is its own defect. Both exclusions have their own
fixtures. JVM keeps the reset-explained-filtered orphan list by design; ALEX, which has no reset
history, correctly uses its raw list.

**15 fixtures (HealthCheck.16–30):** eleven negative controls, one per newly-wired detector, each
requiring the verdict to flip *and* name that detector; two over-blocking controls; one proving the
**copyable text** carries the named issues; one proving several simultaneous defects are **all**
named rather than only the first.

**Controlled experiment, both directions:**

| Mutation | Pre-fix (1,623) | Post-fix (1,638) |
|---|---|---|
| `accountPositionsWithNoJournal` detector deleted outright | **0** | 3 |
| verdict forced permanently `CLEAN` | **0** | 12 |
| `expectedBalance = paperAccount.balance` (JVM self-comparison) | **0** | 2 |
| `alexExpectedBalance = alexGAccount.balance` | **0** | 1 |
| duplicate-journal-id omission re-introduced | — | 1 |
| `invalidPrices` omission re-introduced | — | 2 |
| issue list truncated to its first entry | — | 1 |
| names stripped from the copied string | — | 12 |
| informational categories made to turn the verdict red | — | 2 |

The **first four rows are the finding**: against the pre-fix code, deleting an entire detector and
forcing the sign-off line permanently CLEAN each killed **nothing**. `computePaperTradingHealthReport`
is not protected; drift remained 0 across the change.

#### 17.2a The warning SURFACES — CLOSED (v12.21.3 test debt, fixtures only)

Detection was covered; **display** was not. A warning nobody can see is indistinguishable from one
that was never raised. 17 fixtures (`Banner.1–14`, `Risk.1–3`), each asserting **both** directions —
the banner appears when the condition holds and is empty when it does not — so neither *never render*
nor *always render* survives.

| Mutation | Pre (1,677) | Post (1,694) |
|---|---|---|
| JVM blocking banner silenced | **0** | 1 |
| JVM blocking banner forced always-on | **0** | 2 |
| JVM ledger-integrity banner silenced | **0** | 1 |
| ALEX ledger-integrity banner silenced | **0** | 1 |
| evidence-storage banner silenced | **0** | 2 |
| `⚠ EVIDENCE NOT BEING SAVED` collapsed into the milder wording | **0** | 1 |
| unexported-packages banner silenced | 3 | 5 |
| `sharedRiskStatus` forced to `MATCH` | 1 | 3 |

> **Two rows correct the original finding.** §17.2 said all five banners and `sharedRiskStatus` could
> be silenced "with zero fixtures objecting". That holds for the four banners and the severity
> wording; it was **overstated** for the unexported-packages banner (already 3) and `sharedRiskStatus`
> (already 1). Both are now stronger, but they were not starting from nothing.

The severity fixture matters on its own: `⚠ EVIDENCE NOT BEING SAVED` versus `⚠ EVIDENCE WRITE
PROBLEM` is a distinction an operator acts on differently, and the two were interchangeable.
`Risk.1–3` drive the real registry — baseline absent, baseline locked from the current registry, and
the same baseline with **only** the stored risk fingerprint changed — so the status is proven
computed rather than constant.

**Original finding, for the record:** every warning banner can be silenced. Five render functions — the two ledger-integrity banners,
the blocking banner, the evidence-storage banner ("⚠ EVIDENCE NOT BEING SAVED") and the unexported
-packages warning — can each be made to render nothing forever with zero fixtures objecting. The
underlying **detection** is covered; only the **display** is not. `sharedRiskStatus` can likewise be
forced to `'MATCH'`, so drift in `pipSize`/`pipValuePerLot` — the two functions both engines' risk
math depends on — would report clean.

### 17.3 ✅ PARTLY FIXED — the summariser could not see an ongoing outage (v12.21.3)

`evidenceSummarizeObservations` appears **exactly once in the application — its own definition.**
Nothing consumes `missedIntervals`, `maxGapMs` or `lastSuccessfulPollAt`. **The "84.5% continuity, 12
gaps > 10 min" figure in §5 was produced by an analyst reading the ledger, not by code** — so there is
nothing there for the gate to cover.

The arithmetic itself is reasonably covered, but structurally blind in the direction that matters:

* **A system dead for three hours reports `missedIntervals = 0`, `maxGapMs = 60000`.** The summariser
  takes no notion of "now" and has no trailing-gap term — a gap exists only *between two records that
  both exist*. An outage is detectable only if the system came back. A frozen tab, a sleep that never
  wakes, or any **ongoing** outage is invisible, which is precisely the question an operator would
  consult it to answer.
* A rewound clock pushes a **negative** interval that is silently clamped away.

> **Two bullets originally in this section do not hold, and are withdrawn.** I claimed a poll built
> with no `outcome` is recorded as `'OK'` and counted in `pollsOk`, and that a poll with no
> `startedAt` is stamped "now". Checked against the code: `evidenceBuildPollObservation` defaults
> `outcome` to `'UNKNOWN'` — counted as neither `pollsOk` nor `pollsFailed` — and leaves `startedAt`
> null; the continuity arithmetic keys on `startedAt`, so such a record contributes no interval at
> all. Only `evidenceObservationBase` stamps `occurredAt`, which the gap math never reads. An audit
> finding that does not survive checking must not stand.

---

**RESOLVED in v12.21.3 — the trailing-gap blindness and the silent negative clamp.**

An **optional, purely additive** `nowMs` parameter adds a trailing term measured from the last poll
to now (`trailingGapMs`, `trailingMissedIntervals`, `trailingSince`, `ongoingOutage`). Omitting it
reports `ongoingOutage: null` — **not asked**, which is distinct from false — so no existing caller
or fixture changes. The term is folded into `missedIntervals` and `maxGapMs` too, because those are
the figures an operator actually glances at. It measures from the last poll of **any** outcome, not
the last successful one: the question is whether the loop is running at all, which a failing poll
still answers yes to. `lastSuccessfulPollAt` keeps the other question.

Negative intervals are now **counted and reported** rather than clamped away, while the
missed-interval arithmetic still refuses to invent negatives.

**4 fixtures (L10a–d), both directions** — a healthy loop 30s past its last poll must *not* report an
outage, and a short trailing gap must not displace the real widest historical gap. Seven mutations
(term removed; measured from the last success; not folded into the headline; `ongoingOutage` forced
true; negative counter disabled; trailing gap always overwriting `maxGapMs`; count off by one) each
kill 1–3 fixtures.

**RESOLVED in v12.21.4 — it is now on a screen.** A Developer-Mode-gated **Forward-Observation
Continuity** card on Diagnostics renders the summary from the real ledger. Three states, three
different strings: an outage in progress reports **YES** with the real elapsed time; a healthy loop
reports **no**; and a summary built with no clock reports **"not evaluated (no clock supplied)"** —
reporting healthy for a question nobody asked is the exact defect this card exists to end. A
backwards clock is surfaced in plain words, and the widest gap is marked **still open** when it has
not closed.

> **Mutation found the most important line uncovered, and reshaped the code.** Removing `Date.now()`
> from the renderer's call — the one line that makes the whole trailing term work — killed
> **nothing**, because it sat behind an `await` this offline harness cannot drain. The clock default
> was extracted into a pure `evidenceContinuitySummaryFor()` seam *so the claim became reachable*;
> both directions are now pinned (no argument uses now, an explicit clock wins over it).
>
> **And my own first wiring fixture was vacuous.** It was an `async function` in a **synchronous**
> runner, whose `t()` pushes PASS the moment `fn()` returns — so it reported PASS for a promise
> nobody awaited and would have swallowed every assertion inside it. Rebuilt to assert only what this
> harness can observe, with the limit disclosed in the fixture itself.

Seven mutations — outage question removed, unasked rendered as healthy, backwards clock not
surfaced, still-open marker dropped, Developer-Mode gate removed, clock default removed, explicit
clock ignored — each kill 1–2 fixtures.

### 17.4 ✅ FIXED — evidence integrity: a stated contract with nothing behind it (v12.21.2)

Reason-code validation is **properly closed** (every registry, type and completeness-level check dies
when removed), and `JVM-30` is a genuine differential fixture. But:

**JVM's `CANDIDATE_REJECTED` can declare `evidenceCompleteness: 'COMPLETE'` with nothing objecting** —
against the contract stated in that very code's own comment, which I wrote in §9.4: *"PARTIAL, not
COMPLETE: evaluateLiveTrigger short-circuits on its first failed gate… Claiming COMPLETE here would be
the fabrication this ledger exists to prevent."* **The comment states the rule; nothing enforces it.**
Also unpinned: `reasonText` can be hard-coded while `reasonCode` stays correct, so the two fields
would contradict each other in the same record; and the entry-day gate has no FAIL-path fixture.

---

**RESOLVED in v12.21.2.** `validateDecisionEvent` now enforces the rule the comment described.

Deliberately an **error** — the event is refused and the refusal recorded in
`decisionEventValidationFailures` — rather than a silent downgrade to `PARTIAL`. Rewriting a caller's
completeness claim would conceal the very defect being checked for; a record that never enters the
ledger *while its refusal is surfaced* is far safer than one sitting in the ledger with a false
completeness claim. The rule is **scoped** to the short-circuiting `LIVE_TRIGGER` stage, with its own
positive control: broadening it to every `CANDIDATE_REJECTED` breaks **14** fixtures across four
suites, because stages that genuinely do evaluate everything may legitimately claim COMPLETE.

**7 fixtures (JVM-32…38)**, and a controlled experiment against the pre-fix code:

| Mutation | Pre-fix (1,623) | Post-fix (1,645) |
|---|---|---|
| the rejection record claims `COMPLETE` | **0** | 6 |
| `reasonText` hard-coded so code and text contradict | **0** | 1 |
| enforcement removed | — | 2 |
| enforcement broadened to every stage (over-blocking) | — | 14 |

> **Disclosed: my first `reasonText` fixture was vacuous, and my own mutation test caught it.** The
> scenario runs `setMode("flat")`, where every pair rejects for the *same* reason — so a `reasonText`
> hard-coded to that one reason stayed self-consistent with its own code and survived all 1,644
> fixtures. Rebuilt on a **mixed** set driven through the real recorder with three of the eight reason
> strings `evaluateLiveTrigger` actually returns, so any single hard-coded text contradicts at least
> two records. The reasons are real strategy outputs; no verdict is faked.

#### 17.4a The entry-day gate's FAIL path — CLOSED

The Mon–Wed gate had a PASS-path assertion (`E2E-1`) and **no FAIL-path fixture at all**. Its
rejection could have stopped emitting `RULE_EVALUATED:FAIL`, stopped emitting the linked
`CANDIDATE_REJECTED`, or stopped recording the permanent status row — with the gate still correctly
blocking the trade and the whole gate green. **The block is the safe direction, which is exactly why
the evidence half is the part that can rot unnoticed.**

7 fixtures (`ENTRYDAY-F1…F7`). The clock moves to a **Thursday** and the series is rebuilt from the
new `now`, so the setup stays ~5 minutes old and the staleness gate ahead of this one still **PASSes**
— `F1` asserts that precondition explicitly, because otherwise the refusal would come from staleness
and the fixture would prove nothing.

| Mutation | Pre (1,694) | Post (1,701) |
|---|---|---|
| the rule always records `PASS` with no reason code | **0** | 2 |
| the linked `CANDIDATE_REJECTED` is never emitted | **0** | 1 |
| the `parentEventId` link is dropped | **0** | 1 |
| the evaluated day is hard-coded to Monday | **0** | 1 |
| the status row is no longer `liveEvaluationFinal` | **0** | 1 |

`F3` is the one that matters most: the FAIL record must carry **the day it actually evaluated and the
days it allows** (`entryDayUTC: 4`, `allowedDaysUTC: [1,2,3]`), not a bare unfalsifiable verdict.
`F7` proves the chain stops there — the setup-execution rule after it never runs on that candidate.

### 17.5 A fourth fixture anti-pattern, added to the register

`v128:1378` asserts `p.expectedIntervalMs === EVIDENCE_POLL_EXPECTED_INTERVAL_MS` — but the record's
field is set *from* that constant one line earlier. **It compares the constant to itself**, because
both sides move together. (The stored field is also read by nothing; the summariser uses the global.)
And `L9` pins seq-ordering with a **regex over the function's source text** rather than behaviourally
— it caught a sort mutation only because the text changed.

**Both rebuilt.** `L1` now pins the literal `60000` on both the record *and* the constant, so a change
to the poll cadence must update the fixture rather than slip past it. `L9` is now driven: the same
three records are handed to the summariser **in an order that disagrees with their seq**, and the
answer is only correct if the sort genuinely runs — walking the array as given would produce a
*negative* interval and a 60-second maximum, and neither appears.

> **This is a fixture-QUALITY fix, not a coverage gain, and the numbers say so.** Doubling the
> constant killed 2 fixtures before and 4 after; removing the sort killed 1 before and 1 after;
> reversing it killed 7 before and 7 after. Neighbouring fixtures were already catching the
> mutations — what was wrong was that *these two assertions did not mean what they said*. One
> compared a value to itself; the other would break on a rename and pass on a correct
> reimplementation. Recorded as such rather than presented as new coverage.

---

## 18. POST-RESTART RECOVERY — authoritative state re-established from durable evidence

The Mac restarted unexpectedly while the autonomous verification program was running. Nothing
in-memory survived. This section records what was re-established from **durable repository
evidence and fresh reruns**, not from the restored terminal transcript.

### 18.1 What the restart actually destroyed

| | |
|---|---|
| Repository work | **nothing.** `a8b1891` was committed *and pushed* before the crash; `0 ahead / 0 behind origin/mogo-main` |
| Working tree | clean apart from the pre-existing untracked `MOGO-019-ALEX-IG-CASE-002-REPORT.md` (Aug 12, unrelated) |
| `git fsck` | clean. Three dangling commits are dropped stashes from Jul 24, Aug 12 and Aug 13 — all *predate* the restart. No lost MOGO-021 work |
| Ephemeral scratchpad | **destroyed.** This is where the §16 96-mutation list lived, so that list is **gone** and was reconstructed rather than re-scored |
| Live evidence campaign | **did not survive.** Chrome relaunched 08:24 without `--remote-debugging-port`; no listener on 9222. Restoring it is an operator action requiring broker credentials (§R4) — **not taken** |

**No uncommitted recoverable work existed.** Every pre-restart claim was already durable.

### 18.2 Gates re-run fresh from the recovered state

| Gate | Result | Classification |
|---|---|---|
| canonical (JXA) | **25 suites, 1,759 / 1,759**, 0 failures, 0 execution errors | PROVEN DURABLE |
| protected drift | **0** — 63 functions + 4 constants byte-identical to the v12.22.0 baseline | PROVEN DURABLE |
| platform (Python `unittest`) | **1,049 / 1,049**, 25 suites | PROVEN DURABLE |
| knowledge-engineering | 57 tests, **2 failures** — the two TJR-domain snapshot pins | PROVEN DURABLE (pre-existing, TJR-domain) |

### 18.3 🟡 A correction to §12A.1's own figures

§12A.1 recorded the Python gate as **"1,050 tests, 25 of 26 suites OK"**. The suite count is right;
**the test count is not.** Reproduced from the recovered state:

* `tests/run_platform_tests.sh` — **25 suites, 1,049 tests**, all passing.
* `tests/knowledge_engineering/` — **1 suite, 57 tests**, 55 passing, 2 failing.
* Platform + knowledge-engineering therefore totals **26 suites, 1,106 tests, 1,104 passing**.

There is no composition under which the figure is 1,050. The corrected numbers are the ones above.
The two failures are unchanged and remain TJR-domain, carried into the TJR program.

### 18.4 The rebaseline claim, now proven from git history rather than asserted

§16A.9 claimed the v12.22.0 rebaseline rewrote exactly one hash. That is now verified
**independently of the report**, by diffing the committed artifact:

```
git diff 8cdb0ad~1 8cdb0ad -- regression-baseline.json
  - "generatedFromAppVersion": "12.21.0"      + "12.22.0"
  - "sha1": "829154ba…", "length": 3069       + "sha1": "06a704e5…", "length": 3046
```

**Three substantive lines: the version bump and one function.** Every other one of the 63 protected
functions and 4 protected constants is byte-identical in the committed baseline. The rebaseline was
not used to launder unrelated drift — this is the durable form of the positive control §16A.2 ran.

### 18.5 A check on the drift check itself — `knownGoodHtmlSha1` is NOT stale

`knownGoodHtmlSha1` did **not** change in `8cdb0ad` even though `index.html` did, and the baseline
value (`31baa279…`) does not match `index.html` (`01094c74…`) — which looks exactly like a stale
anchor making the check vacuous. **It is not.** `regression-baseline-tools.py:32` resolves
`KNOWN_GOOD_HTML` to the frozen archival `index-v2.9-KNOWN-GOOD.html`, whose sha1 *is* `31baa279…`.
The check pins an immutable reference file, correctly, and `hash_match: True` is legitimate.

> **One genuine caveat found while confirming this.** `regression-baseline.json` carries
> `fixtureCounts` and `totalFixtureCount: 984`, badly stale against a 1,759-fixture gate — but
> `cmd_compare()` reads **neither**. They are inert metadata that *read* like a pinned assertion.
> Harmless today; a trap for anyone who assumes the baseline pins fixture counts.

### 18.6 Fresh presence check over the recovered 1,759-fixture corpus

All 1,759 passing fixture names were re-collected from all 25 suites individually and matched against
every area named in the recovery authorization. **No area is empty.**

| Area | | Area | | Area | |
|---|---|---|---|---|---|
| market-data completeness | 152 | detection rules | 222 | duplicate prevention | 155 |
| H1/H4/D/W handling | 127 | pattern/setup positive | 256 | trade-ID uniqueness | 125 |
| scanner coverage | 90 | negative controls | 153 | position lifecycle | 426 |
| scanner cadence | 61 | boundary controls | 209 | persistence | 228 |
| scanner concurrency | 53 | chart fidelity | 77 | ledger | 229 |
| failure isolation | 170 | AOI fidelity | 108 | account state | 196 |
| evidence completeness | 173 | chart-vs-engine authority | 116 | reconciliation | 97 |
| health diagnostics | 185 | ALEX paper path | 197 | outage detection | 90 |
| restart/recovery | 58 | JVM paper path | 132 | | |

**This is a presence floor, not a strength claim, and its patterns are deliberately broader than
§12A.3's** — so these counts are *not* comparable to that table and should not be read as growth.
A fixture count proves only that an area is not silent. Strength is what the per-section mutation
evidence establishes, and the standing rule of this milestone is unchanged: **do not declare GREEN
because the gates are green.**

### 18.7 🔴 The §16A.7 ledger fixes were half-applied — independent re-verification, and the repair

The three §16A.7 ledger fixes were re-attacked **from scratch** rather than re-run. All three were
present and working. **Two of them had only ever been applied to the JVM arm**, and the symmetrical
ALEX arm one screen below still carried the original defective code — both reproduced live through
the real `computePaperTradingHealthReport()`, not argued from source.

| | Defect still live | Reproduction |
|---|---|---|
| **ALEX orphan cardinality** (`alexAccountPositionsWithNoJournal`, in `computePaperTradingHealthReport`) | still `some()` — existence, not count | three ALEX positions sharing `AGT\|1` with one journal record between them → **`alex.accountPositionsWithNoJournal.length === 0`**. The JVM arm reports 2 for the identical shape |
| **ALEX duplicate counters** (`alexIdCounts` / `alexJournalIdCounts`, same function) | still raw object keys | ALEX `tradeId` `5` and `'5'` reported as **duplicates of each other**, driving the verdict to **`ISSUES DETECTED`** — the exact false positive the fix existed to remove, surviving one screen away |

**A fix that lands on one of two symmetrical arms is not a fix. It is a fix and a remaining defect.**
Both arms now use the same type-tagged, counting form.

#### The one that moved money

`computeReconciliationPreview`'s ambiguity guard counted only how many **orphans** shared a string
form. That closes the orphan-versus-orphan half and leaves **the half its own comment describes**:

> a **live** position holding the numeric id `999`, and an unrelated historical orphan storing `'999'`.
> Only one *orphan* carries that string form, so `stringFormCounts` never reaches 2, the preview queued
> the historical record, and **its `pnl` was applied to the balance** — the wrong trade restored.

A live position is not in `newlyOrphanedAfterReset`, so it is now looked for where it actually lives.

**Cross-type matching itself is NOT blocked, and must not be.** The UI renders every selection as a
quoted string literal (the `previewPaperReconciliationUI` / `confirmPaperReconciliationUI`
button templates), so a *string* selection against a
*numerically stored* orphan is the ordinary legitimate restore path. Blocking cross-type matching
would have broken every real restore. Only the **collision** fails closed. `LiveTwin.5` pins the
legitimate path so a future tightening cannot quietly take it away.

#### Mutation evidence — the fixtures are discriminating, and one is honestly not

12 fixtures added, each paired with a positive control. Every mutation had a **unique anchor and a
non-zero byte diff**; none was unapplied.

| Mutation | Result |
|---|---|
| revert ALEX orphan detector to `some()` | **kills `AlexCard.1`** |
| revert the ALEX type tag to a raw string key | **kills `AlexConflate.1`, `.2`** |
| disable the live-collision guard | **kills `LiveTwin.1`, `.2`, `.3`** |
| revert the **JVM** `idKey` type tag | **kills `IdKeyWire.1`** — this mutation killed **zero of 251** before |
| *positive control:* switch the ALEX orphan detector off entirely | kills `AlexCard.1`, `HealthCheck.17`, `RollbackFailure.12` — it is not a detector that has been silenced |
| revert `applyPaperReconciliation`'s twin guard to strict `===` | **SURVIVED — killed zero** |

**That last row is reported as a survivor rather than quietly dropped.** It is *not* a coverage gap
to be closed: the guard is **unreachable by construction**, because `applyPaperReconciliation`
derives its own list from `computeReconciliationPreview`, which now fails closed on exactly that
shape. The two comparisons can only ever agree. It is kept as defence in depth and recorded as
**proven unkillable**, in the same class as `AG-21` in §15.9 — never as covered.

#### Two corrections to the v12.22.0 record, from the same verification

* **§16A.7's "the reported output shape is unchanged" is false on ordering.** Element type is
  unchanged; order is not. `Object.keys()` over integer-like raw keys enumerates in ascending
  *numeric* order, while `'number:30'` is an ordinary string key enumerating in *insertion* order —
  so ids `[30,10,30,10]` used to report `["10","30"]` and now report `["30","10"]`. Every consumer
  found reads only `.length` and no fixture asserts ordering, so nothing depends on it. The claim
  was still wrong, and is corrected in the code comment rather than left standing.
* **`Cardinality.1`/`.2` do not drive the cardinality defect**, though their comment claimed they
  "drive the same defect from the other direction". With three *unique* ids, `some()` and a count
  return identical answers — both pass either way. `TradeID.12c` is the only fixture that dies when
  the `some()` form is restored. They are **positive controls** and are now labelled as such.

**Gate after the repair: 25 suites, 1,771 / 1,771. Protected drift 0 against the *unchanged*
v12.22.0 protected baseline — no protected function was touched, so nothing was re-baselined.**
App version `12.23.0`.

> **The lesson is the one this milestone keeps re-learning.** These three fixes shipped with 251
> passing fixtures and a green gate. The gate never noticed that two of them covered half the
> surface, or that the third guarded the narrower of the two cases in its own comment. Only an
> independent verifier attacking them found it — which is why re-running fixtures is not
> re-verification.

### 18.8 🔴 The trade-id floor was off by one — independent re-verification of §16A

The v12.22.0 trade-id remediation was re-attacked from scratch: **39 mutations and a
46-assertion probe harness the verifier wrote itself**, driving the real functions rather than
re-running the shipped fixtures. The design held on thirteen attack angles — it does not wrap, does
not regress across a restart, a rewound clock or a mid-session re-`loadSaved()`, never rewrites a
persisted id, and cannot collide with ALEX. **The gate reproduced exactly (1,759/1,759, drift 0),
and the one-expression protected diff was independently confirmed from the raw git diff** rather
than from the re-issued baseline.

One implementation defect survived that scrutiny, and four evidence defects.

#### D1 🔴 `Number.MAX_SAFE_INTEGER` was accepted as a floor — and is instantly fatal

`Number.isSafeInteger(2^53-1)` is **`true`**, so `MAX_SAFE_INTEGER` passed the guard. The very
first mint then computes `max+1 = 2^53`, where `seq+1 === seq` **forever**:

| | |
|---|---|
| ids in the session | **all identical, from mint one** |
| consequence | three positions share one id, one journal record between them, and `findIndex(p => p.id === id)` resolves to the **wrong position** |
| severity | **moves money** — wrong position closed, wrong P&L applied |

The old guard **rejected `2^53+1` and admitted the one value that reaches `2^53` in a single step** —
off by one, in the exact failure mode its own comment describes. `MAX_SAFE_INTEGER` is also the
*likeliest* corrupt value of all: it is the canonical "max int" sentinel a naive export or migration
writes. The `POISON` list tested `2^53+1` and never tested `2^53-1`, so nothing objected.

The bound is now strictly **below** `Number.MAX_SAFE_INTEGER`, and a refused value is **surfaced**
as a paper-engine error once per load rather than silently swallowed.

> **Disclosed residual, deliberately not defended with an invented threshold.** A persisted floor
> just below the bound still exhausts fast — `2^53-5` yields five distinct ids and then repeats. It
> is not silent (the generator already records an error the moment the sequence leaves safe range),
> but it is degradation rather than prevention. Any cut-off short of the arithmetic limit would be
> an arbitrary number dressed up as an invariant, so the arithmetic limit is where it sits.

#### D2–D5 The evidence defects — including a *sixth* vacuous fixture

| | Defect | Repair |
|---|---|---|
| **D2** | **`TradeID.17` was VACUOUS** — the sixth, after the five the previous round caught. It ran with the clock frozen **above** the journal id it tested, so the clock term alone satisfied it and the floor contributed nothing. Dropping the journal scan killed `17i` and **not** it | clock rewound below the id, plus `TradeID.17p` stating the precondition explicitly |
| **D3** | **The clock freeze was never asserted**, though the suite header claims every fixture *forces* "same millisecond". A no-op `freezeClock` killed **1 of 43** | `Freeze.1/2/3` assert it from **inside the application scope** |
| **D4** | `TradeID.17k/17l` proved the seeder **reads** trade notes and the reconciliation audit while proving nothing about it being **reached** after they load — both called it directly | both now drive the real `loadSaved()` over real persisted bytes |
| **D5** | `TradeID.17n/17o` compared `paperEngineErrors.LENGTH` against a log capped at 50 by `unshift`+`slice`. Firing the error on **every** mint — exactly the noise `17o` exists to detect — made `17n` fail spuriously (`50 > 50` is false) while **`17o` PASSED**. The negative control was blind precisely in its own failure case | both reset the log and match on **content** |

**D3 is not a defect in the generator** — the monotonic counter makes ids unique whether or not the
clock moves, which is the good news. But the *framing* was unverified, and a runner refactor that
silently broke the freeze would have left the suite green while its headline claim became false.

#### Mutation evidence

15 fixtures added. Every mutation had a unique anchor and a non-zero byte diff.

| Mutation | Kills |
|---|---|
| revert the floor bound to plain `isSafeInteger` | `MaxSafe.3`, `.4`, `.5` |
| stop surfacing the refusal | `MaxSafe.5` |
| make `freezeClock` a no-op | `Freeze.1`, `TradeID.15` |
| drop the journal scan from the floor | `TradeID.17`, `.17i` — **`17` did not die before this repair** |
| reorder `loadSaved()` so the seeder runs first | `TradeID.17k`, `.17l` — **neither died before** |
| fire the safe-integer error on every mint | `TradeID.17o` — **it PASSED before** |

> **One mutation of my own was wrong, and is recorded rather than quietly re-run.** My first D4
> mutation *added* a seeder call at the top of `loadSaved()` instead of *moving* it, so the original
> call still ran and picked the stores up anyway — it survived, and the survival meant nothing. The
> true reorder kills both fixtures. An unapplied or mis-specified mutation is not evidence in either
> direction.

**Gate: 25 suites, 1,782 / 1,782. Protected drift 0 against the unchanged v12.22.0 baseline.**
App version `12.24.0`.

### 18.9 🔴 The symmetry repair had the same flaw it was fixing

v12.23.0's thesis was *"a fix that lands on one of two symmetrical arms is not a fix."* Independent
re-verification confirmed its 12 fixtures all discriminate, that the reconciliation guard does **not**
over-block (multi-select, the quoted-string UI path, null/missing ids — all still restore correctly),
and that the `applyPaperReconciliation` "unreachable" claim is true as shipped. **Then it found the
commit had done exactly what it criticised, one level down.**

| | Finding | Killed before |
|---|---|---|
| **F1** | **The ALEX cardinality type tag was uncovered** — the same gap `IdKeyWire.1` exists to close on the JVM arm, recreated on the ALEX arm *by the commit that closed it for JVM*. A numeric ALEX position id matched by a string-form journal record reported clean | **0 of 274** |
| **F2** | `journalWithNoAccountMatch` was the one remaining id comparison held to strict `===` by nothing, **on both arms**. The ALEX one **drives the bottom-line verdict** | **0 of 274** each |
| **F3** | **Two detectors existed on the JVM arm only**, with no ALEX counterpart at all: an ALEX position closed in the account while its journal record is still `OPEN`, and an ALEX `CLOSED` record with no P&L, both signed off **CLEAN** while the identical JVM shapes were reported. Neither previous round caught it | n/a — absent |
| **F4** | **The closed half of the live-collision map was pinned by nothing.** All five `LiveTwin` fixtures used an *open* live position | **0 of 263** |
| **F5** | **A false positive this milestone introduced**, on both arms: converting the orphan detector from `some()` to a count without skipping null ids made a position with no id a permanent "no journal record" report. The old `some()` matched `null===null` and stayed quiet | **0** — no fixture either way |

#### F4 is the one that matters most, because another claim rested on it

Deleting `.concat(paperAccount.closedPositions)` killed zero fixtures. With a **closed** live position
holding the numeric id and an orphan storing the string form, the preview offered a **false +$200**
and a Confirm that silently did nothing — and with the apply guard also reverted, it **restored the
wrong trade for real**, leaving a string/number twin pair permanently unmatchable by the `findIndex`
that closes trades.

> **This corrects §18.7.** `applyPaperReconciliation`'s guard was recorded there as "proven
> unkillable, unreachable by construction". That remains true *as shipped* — but the unreachability
> argument **depends on an uncovered line**. The honest statement is not "unreachable by
> construction" but **"unreachable given a line that nothing pinned"**. It is now pinned, and the
> guard is recorded as **live defence, not redundancy.**

#### Mutation evidence — 20 fixtures added, every finding controlled

| Mutation | Kills |
|---|---|
| revert the **ALEX** cardinality type tag | `AlexIdKeyWire.1`, `.2` |
| report `p.id` instead of `p.tradeId` on ALEX rows | `AlexIdKeyWire.2`, `RollbackFailure.12` |
| loosen the JVM cross-match to `String()` | `CrossMatch.1` |
| loosen the ALEX cross-match to `String()` | `CrossMatch.3` |
| switch either new ALEX detector off | `AlexParity.1`/`.2`, `.4`/`.5` |
| make the P&L detector fire on a **zero** P&L | `AlexParity.6` |
| drop `closedPositions` from the live map | `LiveTwin.6`, `.7` |
| remove either null-id skip | `NullId.1`, `.2`/`.3` |
| swap the live-twin reason for the orphan one verbatim | `LiveTwin.2` |

**Two fixture-quality fixes on top.** `LiveTwin.2` could not tell the two ambiguity guards apart —
both messages open with the same phrase, so swapping one for the other verbatim survived the whole
suite; it now pins the live-position wording. And `AlexIdKeyWire.2` indexes defensively: a bare
`[0].id` **aborted the entire runner** rather than failing one fixture once the detector correctly
went silent — an aborted suite is caught by `run_all.sh`, but it hides which assertion died.

> **Process note for future briefs.** The verifier reported that my scratchpad copy recipe was
> insufficient: copying only `index.html`, `tests/` and the baseline files omits `docs/` and
> `scripts/`, which silently produces 19 failures and under-counts by 72 fixtures. **Copy the whole
> tree minus `.git`.** Recorded because a wrong baseline makes every survivor verdict wrong.

**Gate: 25 suites, 1,801 / 1,801. Protected drift 0 against the unchanged v12.22.0 baseline.**
App version `12.25.0`.

### 18.10 🔴 §16 execution-reporting coverage — the re-score, and closing it

**The §16 item is answered: FAIL.** The pre-restart list was destroyed with the scratchpad, so the
mutation set was **reconstructed**, not re-scored. 110 behaviour-changing mutations of the
execution-reporting surface were scored against the 1,759-fixture gate. **79 killed zero fixtures —
72%.** The same 79 also survived the current HEAD, so none of the v12.23/24/25 work touched them.

**The verdict is trustworthy because the controls fired.** Doubling the close P&L kills 13 fixtures;
four *concurrent* unmutated copies each ran 1,759/1,759 (so no kill is a parallelism artefact); eight
headline survivors were re-confirmed serially with per-run hashes; **zero unapplied mutations.**

#### The structural cause, in one line: nothing that renders or journals was observed

| Survivor | What it means |
|---|---|
| `journalNoteCloseJVM` deleted from `closePaperPosition` | **a JVM close is never journalled at all** |
| `entry.result` → `'Win'` | **every closed trade journals as a Win** |
| `fmtRMult` sign-flipped | **every R-multiple displayed app-wide** is wrong |
| paper-panel win rate `*100` → `*1000` | win rate **10× too large** |
| ALEX win-rate tile fed `st.losses` | the tile reports the **loss** rate |
| all seven `computeGroupTradeStats` | inverted profit factor, expectancy as a **net** not a mean, drawdown that never accumulates |

**74 of the 79 were on non-protected code that nothing in the gate detected.** Five sat inside
protected functions, where the drift check *would* block an edit — but **a drift check is a hash
comparison, not evidence the code is right. Protection is not coverage.**

**One apparent kill was reclassified as a survivor:** it was credited to a `getSource()` substring
match — the source-text anti-pattern, which survives every behavioural mutation and dies on cosmetic
edits.

#### Closed — 174 fixtures across four new suites

| Suite | Fixtures | Survivors closed |
|---|---|---|
| `v1238_execution_reporting_journal` | 73 | 19 — journal write path, normalization, the real close |
| `v1238_execution_reporting_display` | 39 | 36 — panels, tables, formatters, Trade Inspector |
| `v1238_execution_reporting_provenance` | 38 | 7 assigned + 4 found by its own sweep |
| `v1238_execution_reporting_stats` | 24 | 19 — aggregate and derived statistics |

Every fixture is mutation-proven against the specific defect it exists to catch, each with positive
controls. Gate **25 suites / 1,801 → 29 suites / 1,975**.

> **Independently re-verified by me, not accepted on report.** Deleting `journalNoteCloseJVM` from
> the real protected close kills **18** fixtures while `JVM-CLOSE-CONTROL.1` (asserting `exitPrice`,
> `pnl`, `balance`) keeps passing — the close ran, only the journal write vanished, which is exactly
> the right signature. And making the **protected** `alexGComputeReplayStats` report the loss rate as
> the win rate now kills `ERS.T1` and its control; that mutation previously killed nothing.

#### The harness limitation that justified the gap is disproven

Since v4.2 this repository documented `closePaperPosition`'s post-`await` body as permanently
unverifiable offline — and *that deferral is why the close path was never journalled under test*.
**The failure was never the rejection; it was the spin-wait.** JavaScriptCore under `osascript`
drains its microtask queue once the top-level script body finishes, and `console.log` from a
`.then()` continuation is flushed before exit. A suite that **returns a promise and prints from the
continuation** observes post-`await` state normally, even when `fetch` genuinely rejects.

The real, unmodified, **protected** `closePaperPosition` is now driven end to end offline with no
production function stubbed, patched or bypassed. **There is no remaining async deferral for the
paper close path**, and `docs/TESTING.md` is corrected accordingly.

### 18.11 🔴 Both mini-journals showed "No trades yet." for every real trade

Found independently by **two** agents converging from different directions, and confirmed by reading
the code before it was touched.

`v12.3.2` correctly made `strategyId` the ownership key in `getFilteredJournalRecords` — display
labels are metadata and could misattribute a record. **But the two render call sites kept passing the
label.** `renderPaperMiniJournal` asked for `'JVM'` and `renderMiniJournal` for `'ALEX'`; no record's
`strategyId` is ever `'JVM'` or `'ALEX'` — they are `'current_strategy'` and `'alex_g_sr_v1'`.

**The filter matched nothing, permanently.** And because those mini-journals are the *only* surface
that renders `classifyJvmJournalRecord`'s verdict, **the entire account-relationship badge display
was dead** on both the Paper Trading and ALEX pages.

**Fixed at the caller**, resolving the label through `STRATEGY_REGISTRY` — *not* by re-admitting
labels inside the filter, which would undo v12.3.2's deliberate correction.

| Mutation | Kills |
|---|---|
| revert the JVM call site | `MiniJournal.2`, `.3` |
| revert the shared renderer | `MiniJournal.4` |
| make the strategy filter a no-op | `MiniJournal.1`, `.5` |
| revert the fix (tranche B's own regression fixture) | `M0` |

**`MiniJournal.5` is the control that matters:** an unrecognised label must *still* filter to
nothing. It proves the fix **resolved** the label rather than **disabling** the filter — which would
have been a worse defect than the one it replaced.

> **Two fixture-quality notes against my own work.** My first draft of `MiniJournal.3` OR-ed two DOM
> readers behind a defensive ternary and printed the wrong one in its failure message: it passed
> while displaying an empty string as its evidence. The summary is written with `textContent`, so it
> is now read with `elText` directly. And an earlier spot-check of mine used a **non-unique anchor**
> (count 2) and therefore proved nothing in either direction — it was re-run positionally and the
> claim held. An unapplied mutation is not evidence, including when it is mine.

**Gate: 29 suites, 1,975 / 1,975. Protected drift 0 against the unchanged v12.22.0 baseline.**
App version `12.26.0`.

### 18.12 🔴 The fix for a label-vs-id defect was itself keyed on a label

Independent adversarial verification of the 174 new fixtures. **It could not find a single unclosed
survivor** — all 19 sampled mutations still kill, deleting `journalNoteCloseJVM` from the protected
close kills **precisely 18** fixtures while the `exitPrice`/`pnl`/`balance` control holds, and it
confirmed by reading all four runners line by line that **nothing is monkey-patched**: every `g.*`
export is a bare reference to the real symbol, `fetch` genuinely rejects, and the `await` is
unconditional. The async-deferral claim survives scrutiny.

It found two defects in **my** v12.26.0 fix, and one in the gate itself.

#### F1 — rename fragility: the fix used the one lookup marked "not for new code"

The fix resolved a hardcoded display label through `findStrategyEntryByLabel` — whose own docblock
says **legacy compatibility only**, explicitly not for new code, *precisely because a renamed label
stops resolving*.

Renaming `JVM_MANIFEST.label` to `'JVM Strategy'` — a pure display-metadata edit, **exactly what
ADR-006 says labels exist to permit** — reintroduced the original "No trades yet. for every real
trade" defect **in full**, killing the same 8 fixtures as reverting the fix outright.

Both call sites now pass **Manifest ids**. `MiniJournal.7` performs the rename and proves the panel
survives it; `MiniJournal.8` is its precondition, confirming the rename genuinely happened.

#### F2 — failing open: a falsy label disabled the filter entirely

`getFilteredJournalRecords` skips the strategy filter when the value is falsy or `'All'`. So `''`,
`null`, `undefined` and `'All'` did not mean *no match* — they meant **no filter**, leaking every
strategy's trades into a strategy-specific panel.

That is the precise "worse defect than the one it replaced" that **`MiniJournal.5` was written to
exclude — and it missed**, because it only ever tested a *truthy* unknown label. Resolution now runs
id-first, label-second (legacy only), then **fails closed** on a sentinel no record carries.
`MiniJournal.6` drives all four falsy shapes.

#### F3 — the gate could not see a suite running short

`run_all.sh` failed a suite on zero fixtures, a `RUNNER ERROR`, a nonzero exit, or a `FAIL` line —
**never on producing fewer fixtures than it should.** A section that throws is caught by the suite's
own `try/catch`, collapses several fixtures into one reported error, and runs short. During
verification a suite silently ran **36 instead of 39** and nothing objected to the missing three.

`regression-baseline.json` *had* a `fixtureCounts` map — but stale (34 suites, 984 total) and the
tool only ever **wrote** it, never compared. **This is the inert-metadata trap recorded in §18.5,
now cashed in as a real miss.** `tests/expected_fixture_counts.tsv` is the assertion; `run_all.sh`
enforces it in both directions (short = fixtures vanished; long = added without registering).

> **Proven by positive control, not asserted.** Deleting one passing fixture — so the suite reports
> **1,977/1,977 with zero failures** — now **fails the gate with exit 1**. Before this change that
> was a green run.

#### Fixture-evidence repairs

| | |
|---|---|
| **`ISOLATION.1` was VACUOUS — a seventh unkillable fixture** | It reduced to `({balance:10000}).balance === 10000` with **no production code in its path** (the harness setters/getters are bare assignments). It survived all 27 verification mutations, including one that killed 21 fixtures *in its own suite*. **Deleted**, not reworded |
| **Three presence-only assertions accepted wrong values** | `JVM-CLOSE-DURATION.1` and `ALEX-CLOSE-DURATION.1` checked "is a number ≥ 0" and **passed against a mutation journalling `durationMs` as 1 for every trade**; `JVM-CLOSE-CLOSEDAT.1` checked "is an ISO string" and **passed against one journalling the open time as the close time**. All three now pin exact literals — which required freezing the **`Date` constructor**, since the close timestamps with `new Date()` and freezing `Date.now` alone left both stamps on the wall clock. Both mutations now die |
| **`JVM-CLOSE-REACH.2` claimed "(kills A5)" and does not** | Deleting the journal call leaves the trade's untouched OPEN row in place, so it passes. Relabelled to what it actually pins: *no second row appended* |
| **`N1.1` had a tautological conjunct** | `cls==='Active position' && cls!=='Closed account trade'` — the second is implied. Dropped rather than left looking like extra rigour |
| **The stats runner printed `ALL FIXTURES PASSED (0 executed)` when it crashed** | `run_all.sh` caught it twice over, but a human running the suite standalone saw a green last line. Zero executed is now reported as a failure |

> **Disclosed and NOT closed: six fixtures are strict logical subsets of others** (`J4`⊂`J3`,
> `R1a`⊂`J5`, `R1b`⊂`L3`, `R1c`⊂`P4`, `P3`⊂`R4`, `ERS.G5`⊂`ERS.G3`∧`ERS.G4`). They cannot fail
> independently — no mutation kills a subset alone. They are **redundant, not vacuous**: each is a
> true statement that corroborates its superset. They are left in place and recorded here so the
> count is not read as 174 pieces of *independent* evidence. Two others (`U5.2`/`U5.4`) feed
> `SETUP_EVALUATOR_VERSION` back into a comparison the code makes against itself — cosmetic
> self-consistency, with `U5.1/.3/.5` carrying the real load.

**Gate: 29 suites, 1,977 / 1,977, with the new per-suite count check active. Drift 0.**
App version `12.27.0`.

---

## 18.13 RECOVERY — the operator-requested pause for computer transport

The session was stopped deliberately, mid-flight. Two mutation campaigns (end-to-end paper
trading; lifecycle/reconciliation) were **explicitly stopped by the operator and are NOT complete.**

### What was durable versus what was interrupted

| | |
|---|---|
| Repository | `4244763` committed **and pushed** before the pause, 0 ahead / 0 behind |
| The two stopped campaigns | **wrote nothing into the repository.** Confirmed: no `v1239_paper_trading_e2e` or `v1239_lifecycle_reconciliation` files existed in the tree |
| Their scratchpads | *did* contain draft suite files, with **no mutation evidence and no completion report behind them**. **Discarded**, not salvaged — a suite whose fixtures have never been shown to fail is not evidence, and adopting one would be the exact false-green this milestone exists to remove |
| Uncommitted legitimate work | the market-data suite and two fixture repairs, all individually mutation-verified before the pause — **preserved**, re-gated, and committed as `718f908` |

**No PASS was inferred from partial output.** The interrupted campaigns are being re-run from
scratch rather than resumed.

## 18.14 §13 area 1 of 5 — MARKET-DATA CONTINUITY, mutation-verified

25 behaviour-changing mutations of candle acquisition, completeness, continuity and
multi-instrument observation, each scored against the whole gate, with a per-suite
executed-count shortfall counted as a crash-kill rather than a survivor. **Three killed zero
fixtures:**

| Survivor | What it meant |
|---|---|
| the completeness filter neutered | **a still-FORMING candle treated as closed** — the strategy evaluates a bar that has not finished |
| the backward pagination cursor reading the wrong end of a page | history walks re-request the same window or skip one |
| a scan serving the **previous sweep's** candles under **this** sweep's verdict | the completeness verdict blesses data it did not describe |

All three are closed by `tests/v1239_market_data_continuity_tests.js` (18 fixtures) using a
router-based `fetch` seam keyed on instrument/granularity/count/cursor. **No application function
is stubbed and no trade is opened.** Controls: positive; negative (healthy data is *not*
suppressed and genuinely scores, which is what makes the suppression assertions discriminating);
boundary (requested-minus-one, the 220th raw bar, a 49-hour weekend hole **preserved rather than
filled**, the exact `to` cursor literal); failure isolation (one dead and one short instrument, the
other 33 still evaluated, transport failure kept distinct from contract failure);
persistence/restart; and end-to-end (the frozen evaluators receive the blessed array **or nothing
at all**).

> **Independently spot-checked rather than accepted on report:** neutering the forming-bar filter
> kills exactly the four fixtures claimed — `MDCONT-1`, `-4`, `-15`, `-18`.

**No production defects found in this area.** Two hardening observations, neither exploitable:
`fetchCandlesRange`'s all-incomplete branch advances the cursor without the `CURSOR_NOT_ADVANCING`
check its sibling branch applies (it still fails closed via the guard limit), and `scanPair`
duplicates the literal `220` as a `requestedCount` fallback.

### 18.14a Two existing fixtures were defective — the eighth unkillable one

**`ALIGN-21` was VACUOUS.** `precomputeCloseTimes` **is**
`candles.map((c,i)=>getCandleCloseTime(candles,i,granularity).getTime())`, and the fixture asserted
`pre[i] === getCandleCloseTime(h1,i,'H1').getTime()` — that is `map(f)[i] === f(i)`, **true by
construction for any `f`**. Its stated claim ("one methodology, not two") is a property of the
implementation's *shape*, so no behaviour change could falsify it. Proven: halving the H1 close
interval kills `ALIGN-9b/10/11/12/27` and **`ALIGN-21` passed**.

Rewritten to the spec property it was reaching for — a close is exactly `3600000`ms after its own
open, and consecutive closes are exactly that far apart — both literal constants from the timeframe
definition rather than values re-derived by calling the function under test. Plus `ALIGN-21b`.
**Verified: the same mutation now kills both.**

**`SAFETY-4` was presence-only and far weaker than its title.** It asserted
`hasCompletenessState(c)`, which accepts **any** of `COMPLETE`/`PARTIAL`/`UNAVAILABLE` — so a
429-terminated walk classified `COMPLETE` passed it, and only `CURSOR-1` fired from that suite. Its
first disjunct was also dead code (`c` is always an array, so `!Array.isArray(c)` is always false).
Now asserts the ADR-011 contract value `PARTIAL` **and** the `HTTP_ERROR` diagnostic.
**Verified: forcing `satisfied=true` now kills it.**

`CONTRACT-2`'s two `getSource()` regex clauses are labelled **STRUCTURAL** so they are not mistaken
for behavioural coverage; its behavioural half is what carries the contract.

## 18.15 CONTINUATION CHECKPOINT — resume here

**Commit:** `718f908` on `main`, pushed to `origin/mogo-main`, **0 ahead / 0 behind.** Working tree
clean apart from the pre-existing untracked `MOGO-019-ALEX-IG-CASE-002-REPORT.md`.

**Gates:** canonical **30 suites, 1,996 / 1,996**, 0 execution errors, **per-suite fixture-count
check active**; platform **1,049 / 1,049**; knowledge-engineering 57 with **2 known TJR-domain
failures** (carried into the TJR program); protected drift **0** against the v12.22.0 baseline. App
version `12.27.0`.

### §13 areas — mutation status

| Area | State |
|---|---|
| Market-data continuity / completeness / multi-instrument | ✅ **CLOSED** (§18.14) |
| ALEX/JVM end-to-end paper trading, order generation, duplicate prevention, ALEX/JVM isolation | 🔄 campaign running |
| Lifecycle, persistence, ledger/journal/account reconciliation | 🔄 campaign running |
| Restart / recovery / diagnostics | ⬜ **not started** — interrupted by the session limit, never relaunched |
| Chart↔engine fidelity, AOI, pattern/setup detection | ⬜ **not started** — same |

### Standing constraints — unchanged

PAPER ONLY · live money **NOT AUTHORIZED** · TJR **RESEARCH ONLY**, not begun, gated behind CORE ·
frozen ALEX and JVM economic semantics preserved · **the live evidence campaign did not survive the
Mac restart** and restoring it needs broker credentials and an operator (§18.1).

### Exact restart instructions

1. `git log --oneline -1` should read `718f908`; `git status` clean but for the MOGO-019 report.
2. `bash tests/run_all.sh` → 30 suites / 1,996 / 0 failed / drift 0. If a suite reports a **count
   mismatch**, a fixture vanished — investigate, do not regenerate the manifest to make it green.
3. Relaunch the outstanding campaigns above **in bounded waves of two**, never five: five concurrent
   heavy campaigns exhausted the session budget once already.
4. Any suite file found in a scratchpad without a completion report and per-fixture kill evidence is
   **untrusted — discard and re-run.**
5. **CORE is NOT GREEN** and must not be declared so while any row above is unclosed.

## 18.16 §13 area 2 — LIFECYCLE, PERSISTENCE, LEDGER/JOURNAL RECONCILIATION

25 mutations of the position state machine and the three stores that must agree. **Three killed zero
fixtures:** a closed trade left in **both** `openPositions` and `closedPositions`; a rejected commit
rolling the **account** back while leaving the **journal** row `CLOSED`; and a rolled-back commit
leaving its newly written storage keys persisted.

Closed by `tests/v1239_lifecycle_reconciliation_tests.js` (51 fixtures, prefix `LCR-`), which returns
a promise and **awaits every close**, driving the real, unmodified, protected open/close path.
Nothing in production is stubbed — the only new seam is a write/remove failure injector inside the
harness's own `localStorage` **stub**, because a storage exception is otherwise unreachable offline.

> **Independently re-verified:** leaving a closed trade in both stores kills **9** fixtures in the
> new suite and **0** in the old paper-audit suite. That is the gap, measured.

### 18.16a 🔴 The NINTH unkillable fixture — an async close that was never awaited

`Reconciliation.1` claimed *"a normal open→close cycle produces zero integrity findings."*
`runPaperTradingAuditFixtures` is **not** `async` and `closePaperPosition` **is**, so the un-awaited
call returned a pending promise and the assertion ran before the close did anything.

**Measured at the assertion point: `open=1, closed=0, balance=10000, journal OPEN`.** It was asserting
that a freshly *opened* trade is self-consistent — trivially true, and structurally incapable of
detecting any close-path defect. Corroborated independently by the mutation scores: leaving a closed
trade in both stores (*exactly* the `duplicateAccountIds` condition it asserts is empty) killed
nothing, and deleting the `closedPositions` write killed 21 fixtures elsewhere and **none** here.

Retitled to what it observes, with a new `Reconciliation.0` precondition pinning that state.
`TEST I.1`/`I.2` in the same file also fire un-awaited closes but **disclose** that they observe only
the synchronous prefix — they were honest; this one was not.

## 18.17 §13 area 3+4 — END-TO-END TRADING, and CHART↔ENGINE FIDELITY

### Cross-strategy STATE isolation was entirely unobserved

28 mutations of the signal→closed-record path; **five killed zero fixtures.** The two that matter:

| | |
|---|---|
| a **JVM close also crediting `alexGAccount.balance`** | passed all 1,996 fixtures |
| an **ALEX open also filing into `paperAccount.openPositions`** | passed all 1,996 fixtures |

**Every pre-existing `*ISO*` fixture in that area tests _fault_ isolation** — a throw in one
observability path not aborting a tick — **never _state_ isolation.** The name looked like coverage.

> **Independently re-verified:** with the JVM→ALEX leak injected, the **full gate reports exactly two
> failures and both are new fixtures.** Nothing in the pre-existing 1,996 could see a JVM close
> moving money into the ALEX account.

Three further survivors were defence-in-depth outer layers an inner guard compensates for — correct
behaviour, but the outer guard could be deleted silently, and under one of them a pair already
holding an open position was still **evaluated**, including a real API round-trip.

### 🔴 D1 — the chart attributed the engine's verdict to a timeframe it never evaluated

**15 of 25 render-layer mutations killed zero of 2,105 fixtures.** Every AOI-drawing, chart-authority,
trade-marker and rendered-setup mutation survived. `loadChart()` **had never once been executed** by
the gate — §10.3's "honest gap" was the entire render layer.

`pairData` recorded `conf`/`signals` but **no timeframe**, and `loadChart` granted engine authority on
mere presence, then labelled the result with `activeTf`. `setTf()` assigns `activeTf` and calls
`loadChart()` **before** `scanAll()`, so switching H1→H4 rendered the H1 verdict under the words
*"Showing the scanner's own H4 verdict for this pair"* — confidence reading **LONG 83% from H1 while
the state line claimed H4.** The verdict shown and the timeframe named came from different places.

**Fixed at both ends**, display-only, drift 0: `scanPair` records the timeframe it evaluated on, and
`loadChart` requires it to match. A verdict with **no** recorded timeframe **fails closed**.

**D2** — the live setups panel rendered ALEX's internal research ids while every other surface renders
the frozen label. Resolved by a display helper that necessarily **duplicates** a mapping inside the
protected `alexGCreateSetupRecord`; the duplication is **pinned** by `CAF-LABEL.1` rather than left
to become a third copy of the same truth.

> **Two self-corrections, recorded rather than quietly fixed.** An early draft of the timeframe
> fixtures moved `activeTf` to a granularity the chart router does not serve, so `loadChart` returned
> early and the assertions read **stale DOM from the previous fixture** — passing without the code
> under test running at all. And deleting the **recording half** of the D1 fix killed **zero**
> fixtures, because the authority fixtures seed `pairData` directly: covered-but-wired-to-nothing, in
> the coverage of my own fix. Both are closed and both halves are mutation-covered. A tautology of my
> own (a callback returning `true` unconditionally) was caught and removed before delivery.

## 18.18 §13 area 5 — RESTART/RECOVERY AND DIAGNOSTICS

25 mutations; **six killed zero of 2,105 fixtures** — including a **restart that concatenates closed
positions into open ones, re-opening every completed trade**, and the engine-error log keeping the
**oldest** 50 so every new error is discarded while its length stays exactly 50, **on both arms**.

### 🔴 PD-1 — ALEX engine errors were recorded and never surfaced

`alexGEngineErrors` had **three sites in the entire application** — declaration, `unshift`, `slice` —
and **no read site at all**, while its own declaration comment claimed *"surfaced in Diagnostics,
mirrors paperEngineErrors."* The ALEX arm was built by mirroring `recordPaperEngineError`; the
matching **render** block never was.

Every ALEX failure through that channel was invisible: `commitAlexGLedger`'s `ROLLBACK_FAILED` FATAL,
`STALE_VERSION`, `LOAD_INTEGRITY_BLOCKED`, and the INC-001 storage-load notice **whose entire purpose
is to tell the operator their data is being preserved** — `recordStorageLoadFailure` deliberately
fires both channels for exactly that reason, and on the ALEX side it went nowhere. Now rendered
beside the JVM block under the same Developer Mode gate; the misleading comment corrected in place.

### 🔴 The TENTH unkillable fixture — a security control satisfied by emptiness

`RollbackFailure.15` asserted the ALEX error log never contains the API key or account ID — a pure
*must-not-contain* check with **no positive precondition**, so an **empty log satisfies it**, which is
precisely the condition its own title claims to test under. Proven: making `recordAlexGEngineError` a
no-op kills four fixtures elsewhere gate-wide and leaves that one **green**.

**A credential-leak assertion that passes when nothing was logged is not a security control.**
`RollbackFailure.15a` now requires a non-empty log whose newest entry is the `commitAlexGLedger`
FATAL before the leak check is applied.

> **A structural fix, not just two fixture fixes:** the new runner **refuses to report anything
> unless the suite returns a Promise**, so an un-awaited async suite cannot go false-green there —
> a direct answer to §18.16a.

## 18.19 §13 COMPLETE — all five areas mutation-verified

| Area | Mutations | Survivors | Fixtures added | Production defects |
|---|---|---|---|---|
| Market-data continuity | 25 | 3 | 18 | 0 |
| Lifecycle / persistence / reconciliation | 25 | 3 | 51 | 0 |
| ALEX/JVM end-to-end + isolation | 28 | 5 | 57 | 0 |
| Chart↔engine / AOI / scanner | 25 | 15 | 38 | **2** (D1, D2) |
| Restart / recovery / diagnostics | 25 | 6 | 36 | **1** (PD-1) |
| **Total** | **128** | **32** | **200** | **3** |

**Ten literally unkillable fixtures have now been found across this milestone**, plus four
source-text fixtures relabelled, one duplicate fixture ID renamed, and 54 cross-suite ID collisions
disclosed as an attribution hazard.

**Gate: 34 suites, 2,180 / 2,180.** Platform **1,049 / 1,049**. Knowledge-engineering 57 with the
**2 known TJR-domain failures**. Protected drift **0** against the v12.22.0 baseline. App `12.29.0`.

**CORE is NOT yet declared GREEN.** A consolidated independent adversarial pass over all five new
suites and the three production fixes is running; every previous round of this milestone found that
work passing its author's own checks failed an independent attack.

## 18.20 Independent verification round 1 — the isolation snapshots were allowlists

Two adversaries re-attacked the five §13 suites. **107 of 108 trading fixtures proven killable**, no
tautology, no source-text assertion, **no un-awaited close**, no self-consistent balance assertion,
and every claimed-closed survivor independently re-scored as genuinely closed. Then the isolation
claim broke.

**Six cross-strategy leaks passed the entire 2,180-fixture gate with zero protected-function drift**,
because the snapshots were hand-written **allowlists** while `PTE2E-ISO.4` claimed to compare *"every
JVM localStorage key"*. Two would move or block real money:

| Leak | Why it matters |
|---|---|
| an ALEX close poisoning the shared `pairData` **price cache** | `closePaperPosition` fills its exit from it when live bid/ask is unavailable, and `checkPaperPositions` reads it to decide TAKE_PROFIT/STOP_LOSS |
| an ALEX commit inserting open JVM ids into `paperPositionsClosing` | that is the in-flight close lock — those trades **can never close again** |

The rest: a write to `fxhub_alexv2_account` (an ALEX-family key matching **neither** prefix);
overwriting JVM-owned `fxhub_scan`/`fxhub_autoscan`; rewriting `alexGDecidedSetups` **contents** while
preserving `.size`, which was all the snapshot recorded; and clearing `storageLoadFailures`,
disarming the INC-001 guard.

**The allowlist is now a denylist** — every key that is not ALEX-owned — so a new key is covered by
default rather than needing to be remembered.

### 18.20a The exclusion filter was spoofable, and the snapshot had nothing to lose

**Spoofable:** evidence-platform entries were excluded from the ALEX error log by matching the
**message prefix** — content a leak chooses for itself. Proven: JVM P&L written into that log under
the right opening words survived the whole gate; the identical leak under any other prefix died.
`recordAlexGEngineError` now takes an optional `meta` and the evidence platform tags its own entries,
so the exclusion is **provenance recorded by the writer**, not inference by the reader.

**Nothing to lose:** the reset helpers did not clear four fields the snapshots *compare*, so a leak
writing the **same value twice** was identical before and after — an idempotent leak is still a leak.
And a leak that *clears* shared state, or adds one entry per open JVM position, is invisible when the
scenario has neither. The ALEX→JVM block now seeds a real open JVM position and a non-empty INC-001
register **before** snapshotting. All six leaks are caught, each verified individually.

## 18.21 Independent verification round 2 — the v12.28.0 chart fix was worse than the bug

**89 of 92 fixtures proven killable**, no tautology, no source-text assertion, no un-awaited fixture.
Then four code defects, **three of them in my own fixes**.

### 🔴 The regression I introduced

`setTf()` is `activeTf=tf; loadChart(); scanAll();` with neither awaited — so on **every timeframe
click** the recorded verdict stops matching, and the v12.28.0 guard sent the chart down the
chart-local path. For a pair the engine had **refused to evaluate on incomplete data**, the chart
rendered an invented **"LONG 43%" and a "SETUP FORMING" recommendation banner** — verbatim what that
block's own comment says it exists to prevent.

| | state line | banner | confluence |
|---|---|---|---|
| on H1 (verdict matches) | `NOT EVALUATED — incomplete market data` | `AWAITING DATA` | — |
| after clicking H4 | `Computed on this chart's H4 data…` | **`▲ SETUP FORMING`** | **`▲ LONG — 43%`** |

**I traded a labelling error for a fabricated verdict**, and the banner carries no qualifier at all —
only an 11px grey line did. A verdict recorded on a different timeframe now yields its own explicit
state (*this timeframe has not been scanned yet*, naming both) and the chart shows **nothing**.

### 🔴 Re-entrancy, also mine

`loadChart` read the live `activeTf` across two awaits, so a mid-load timeframe click could have the
**fetch** use one value while the guard and label read another — **H1 candles drawn under an H4
verdict, labelled H4.** That is the exact property §18.17 claimed to have closed. The timeframe is
now captured once, as the pair already was.

### 🔴 PD-1 was unreachable by the sequence an operator uses

`applyDeveloperModeVisibility` explicitly re-renders five Developer-Mode surfaces and **did not**
re-render the Paper Ledger Integrity card — the only operator-visible view of `paperEngineErrors` and
`alexGEngineErrors`. Turning Developer Mode ON left the card showing what it rendered while the flag
was OFF. Developer Mode is session-only and defaults OFF, so the INC-001 load-time notice was
invisible on every fresh session. **Surfacing errors is worth nothing if the surface is not repainted
when it becomes visible.**

Also: **D2 missed a third path** (`renderTradeOverlayLegend` fell through to the internal research id
whenever `setupLabel` was null), and an **eleventh empty-log-satisfied assertion** (`RSTDG-RESTART.4`
recorded a sentinel and never asserted it was recorded; a no-op recorder kills 13 fixtures gate-wide
and left it green).

### 18.21a The second unwatched copy of the pagination arithmetic

`runHistoricalDataDiagnostic` is an **entirely separate implementation** of the backward walk from
`fetchCandlesRange`, reached from the Diagnostics button — with **zero** behavioural coverage. Three
mutations each killed 0 of 2,188. **The tool an operator uses to check data continuity could report a
reversed, duplicated or truncated window as healthy.** `MDHIST-1/2/3` close it, pinning both sides of
the termination test with a positive control proving the duplicate detector fires.

`CAF-LABEL.1` compared the helper against **hand-written literals**, so changing the mapping inside
the protected `alexGCreateSetupRecord` left it green — it pinned the helper, not the *duplication*.
It now reads the label off a **real** setup record. *Disclosed scope:* only the setup type the engine
actually produces is pinned; the other branch remains a literal comparison and is labelled as one.

> **My own fixes failed independent attack three times in this programme** — a half-applied ledger
> repair, an off-by-one floor, a symmetry fix that repeated its own error, and now a chart fix that
> was worse than the bug. That is the argument for the loop, not against it.

### 18.21b Still open, and named

* **`drawTradeOverlay` / `drawTjrZoneOverlay` are reachable-but-unpinned** — deleting either call
  site kills **zero** fixtures, so both can be disconnected from the render path at no cost to the
  gate. Closing it needs the real draw path (`focusChartOnTradeWindow`), which requires a windowed
  fetch the fixture router does not model. `CAF-LEGEND.1/.2` pin the **label** and say plainly that
  they do not pin the wiring.
* **The inner pre-open re-check** in the auto-trade path is uncovered — the outer eligibility filter
  is pinned (`EXCL.1/.3`), but under genuinely overlapping ticks the inner re-check is the one that
  matters.
* **`CAF-LABEL.1b`** is a literal comparison for the `B_breakRetest` branch.

**Gate: 34 suites, 2,193 / 2,193.** Platform **1,049 / 1,049**. Protected drift **0**. App `12.31.0`.

**CORE is still NOT declared GREEN.** A final adversarial sweep and an independent completeness audit
of the full operational chain are running; two prior rounds each found real defects in work that had
passed its author's own checks.

## 18.25 The module-state axis — 15 channels, two of which move money

The v12.30.0 denylist closed the **storage** axis properly. The **module-state** axis was still a
hand-written allowlist with the identical failure mode: 13+ cross-strategy channels injected into
**non-protected** functions all survived 2,207/2,207 with zero drift.

| Channel | Consequence |
|---|---|
| **`paperTradeIdSeq`** | the JVM **trade-ID space**. Poisoned to `MAX_SAFE_INTEGER`, `seq+1===seq` forever — **every** subsequent JVM id identical, and the close lookup resolves to the **wrong position**. The floor guard screens *persisted* values only |
| **`structuralAOICache`** | the shared D/W cache `getStructuralAOI` serves, which sets the real **stop and target** on a JVM paper trade |
| `cfg.env` | flipping to `'live'` repoints `apiBase()` at the live OANDA host; only the *storage key* was compared, so an in-memory flip was invisible |
| `alexGIdentityDriftReported`, `alexGCursorSanityReported` | **silence ALEX's own integrity reporting** |
| `firedAlerts`, `hideTestTradesPaper`, manual-review guards, health-report cache, lifecycle log, replay statistics | reporting, dedup and diagnostics |

**All 15 now die.** The widening needed two repairs, and both were the same lesson recurring *on the
fix for that lesson*:

* **Adding a field is not enough if nothing resets it.** `alexGIdentityDriftReported` was *already*
  `true` when the snapshot was taken — polluted by an earlier block — so the leak stayed invisible
  even after the field was compared. That is §18.20a's "nothing to lose" defect, reproduced on the
  fields added to fix §18.20a.
* **Adding a field is not enough if the scenario leaves it EMPTY.** The ALEX decision sets are empty
  in every isolation block, so a leak that *clears* them changes nothing — including the
  **size-preserving rewrite §18.20 explicitly named and still could not detect.** And the first
  seeding attempt ran *before* the cleanup wiped it back, so the wipe leak was still invisible until
  the seeder ran **last**.

> **One field was removed again after measurement.** The evidence-platform counters are **not**
> ALEX-owned — the platform is strategy-agnostic and legitimately records a JVM operation, so
> comparing them reported a normal JVM write as an ALEX leak and failed on a clean tree. Removed for
> the same reason the engine-error entries are cross-referenced rather than compared raw.

## 18.26 The last four CORE items

### Three money-path mutations inside PROTECTED functions

The drift baseline was their only control — and **a drift hash says the bytes did not change, never
that the arithmetic is right.** Each survived the full gate:

| Mutation | What it does |
|---|---|
| `>=` → `>` on the target test | a price that touches its target **to the pip** never takes profit, and the trade runs on to its stop |
| pip value **re-derived** at close instead of fixed at entry | the JVM analogue of the fixed-vs-recomputed-R hole |
| the manual-close fallback collapsed | a manual close with no bid/ask **and** no cached price silently **no-ops**, stranding the position open forever |

`JVMEXIT-10/11/12` close all three by observing the protected functions' **output** rather than
editing them: exactly-at-target takes profit; a position seeded with `pipValueAtEntry: 25` books
**+$625.00** where a re-derivation would give $250.00; a feed-less manual close fills at the entry
for **exactly $0.00** and leaves nothing open.

### 🔴 A diagnostic that over-reported its own coverage

`MDHIST-1..3` pinned the **walk**; every figure the operator actually **reads** was free.
`calendarDays` and `tradingDays` are now hand-computed literals over a Monday→Wednesday window
(9 calendar days, 8 trading days) with a positive control on a window containing proportionally more
weekend.

**And the fixture found a real defect.** `totalRaw` **double-counted every duplicate**: `all` is the
merged array and already contains them, so `all.length + duplicates` reported one *more* bar than
the pages returned for each repeat. A diagnostic whose job is to report coverage, over-reporting its
own. Found because the hand-computed literal did not match the shipped arithmetic — **and the
arithmetic was wrong.**

### The chart overlay wiring, pinned at last

Deleting `drawTradeOverlay`'s call site killed **zero** fixtures, because every overlay fixture
called the helper **directly** — it could be permanently disconnected from the render path at no
cost. The blocker was the fixture router: `fetchCandlesAroundWindow` builds a *different* URL shape
(`granularity/price/count/from`), so the regex never matched and the router was handed a null
context. It models both shapes now, and `CAF-WIRE.0/.1` drive `focusTradeOnChart` end to end.

### Two items disclosed rather than closed — with proof, not assertion

* **`requestCount` from the loop guard is an EQUIVALENT MUTANT.** `guard++` runs once per iteration
  and *every* path through the body pushes exactly one `pages` entry, so the two are equal by
  construction.
* **`CAF-TF.2` is a COMPANION to `CAF-TF.1`, not independent evidence.** Under the shipped guard the
  string it forbids is structurally unproducible, so no single behaviour-changing mutation can make
  it fail.

**Gate: 34 suites, 2,219 / 2,219.** Platform **1,049 / 1,049**. Protected drift **0**. App `12.33.0`.
A final independent falsification of this batch is running; **CORE is not declared GREEN until it
returns clean.**

## 18.27 Round four — one quadrant of four, and two channels compared against a constant

### 🔴 Three of the four exit boundaries had no coverage — including both stop-loss sides

`JVMEXIT-10` pinned **one** of the four comparisons in `checkPaperPositions`: the buy target. The
other three each survived the whole gate.

| Boundary | Before |
|---|---|
| buy target `>=` | covered by `JVMEXIT-10` |
| **sell target `<=`** | **0 kills** |
| **buy stop `<=`** | **0 kills** |
| **sell stop `>=`** | **0 kills** |

**Two of the three are the stop side.** A price that touches its stop *to the pip* does not stop out,
and the position runs on past it **with no bound** — strictly worse than the target case the fixture
was written for. I closed one quadrant of four and reported the boundary as covered.
`JVMEXIT-13/14/15` pin the rest.

### 🔴 Two of the fifteen isolation channels were compared against a constant

`alexGIdentityDriftReported` and `alexGCursorSanityReported` are **`Set`s**, and
`JSON.stringify(new Set([...]))` is `"{}"` for **every** possible content. So the two channels §18.25
named as *"the two flags that silence ALEX's own integrity reporting"* were never compared at all.
**"All 15 now die" was false — 13 did.** The hole was the **type**, not the reset.

### 🔴 A sixteenth channel, and it moves money

`structuralAOIInflight` is returned by `getStructuralAOI` **before any fetch and before the ADR-011
completeness gate**, so a seeded promise puts a **fabricated stop and target** on a real JVM trade.
§18.25 added its *cache* and missed the in-flight lock for that same cache — the exact sibling of
`paperPositionsClosing`, which an earlier round had already added for the close path. My first
attempt put it in the **ALEX** snapshot, the wrong side entirely; it stayed invisible until moved
beside its cache in the JVM one.

### Six more uncompared channels, and the same lesson a third time

`cfg.accountId` (in the URL of every pricing fetch that fills a close) and `cfg.key`;
`storageLoadFailures` **values** — keys alone were compared, so rewriting every INC-001 message to
`"ALL CLEAR"` survived, which is the *same size-preserving rewrite* §18.20 named and fixed elsewhere;
`alexGReplayState`; `hideTestTradesAlex`; `alexGPipelineObservationBuffer`.

> **`alexGReplayState` and `hideTestTradesAlex` were added to the snapshot and NOT to the reset**, so
> they were already polluted and their leaks stayed invisible. That is the third time in this
> milestone. **Adding a field to a snapshot and adding it to the reset are one change, not two.**

### 🔴 My §18.26 relabel created the fourteenth unkillable fixture

Merging `CAF-TF.2`'s id and description turned a **4-arg** assert into a **3-arg** one, so the real
check landed in the *description* slot and `cond` received a string its own precondition guarantees
is non-empty. Proven dead in both directions. Restored.

### A harness defect: a helper that disabled the guard it was meant to observe

`seedIsolationScratch` replaced the production **`Map`** `alexGDecidedSetups` with a **`Set`**, so
`.set(...)` threw inside the bookkeeping `try/catch` that *"must never break a trading decision"* —
ALEX's duplicate-decision bookkeeping was silently **inert** for the rest of the suite. Latent rather
than a live false green, but a helper that substitutes the **type** disables the guard the suite
exists to observe.

**Gate: 34 suites, 2,222 / 2,222.** Platform **1,049 / 1,049**. Protected drift **0**. App `12.34.0`.

> **Four consecutive independent rounds have each found real defects, including in my own
> corrections.** That is the argument for the loop, and the reason CORE is still not declared GREEN:
> a fifth round is the gate on that decision, not the fixture count.

---

## §18.29 — Round 5: a production surface that did not exist, and an exclusion filter that contradicted its own comment

Fifth independent adversarial round. Two independent agents attacked the repaired production paths
and the isolation/evidence machinery. Both found real defects.

### PD-2 (PRODUCTION) — `alexGLedgerBlockingError` had no render site anywhere in the application

`alexGLedgerBlockingError` is assigned on every rejected ALEX ledger commit, and its declaration
comment says it mirrors `paperLedgerBlockingError`. The JVM twin renders an always-visible red card
via `renderPaperLedgerBlockingBanner`. The ALEX one had **no read site at all** outside the
assignment — the same shape as PD-1 (§18.18), one release later, and found the same way: by asking
what actually consumes a variable rather than whether it is correctly set.

**Consequence.** A cross-tab version conflict rolls an ALEX open back and emits a decision event.
The operator, who believes the trade was placed, sees nothing on any screen.

**Fix.** `renderAlexGLedgerBlockingBanner()` mirrors the JVM function and is called first in
`renderAlexGLivePanel()`. Deliberately **not** Developer-Mode gated: Developer Mode is session-only
and defaults OFF, so gating it would reproduce PD-1's invisibility on every fresh session.

**Coverage.** `RSTDG-ALEXBLOCK.1` drives it with Developer Mode explicitly OFF and requires the
operator-facing text and the error's own content. `RSTDG-ALEXBLOCK.2` is the negative control: a
cleared error must clear the banner rather than leave a stale one.

### The evidence-platform exclusion, defeated for the sixth time — by a 44-character prefix

The §18.28 filter's own comment asserted:

> Only those EXACT strings are excluded. A leak must smuggle its payload somewhere, and any payload
> changes the message — so an excluded entry is one that provably carries no information.

The code was `msg.indexOf("IndexedDB is not available in this context")===-1` — **substring
containment**. Appending a payload leaves the phrase intact, so the entry is still dropped.

Independently proven, then re-scored by me against a frozen tree:

| Leak injected into `commitPaperLedger` | Old filter (`indexOf`) | New filter (`Set.has`) |
|---|---|---|
| `'R5B-CONTROL-CONSTANT'` (control) | KILLED ISO.2 + ISO.6 | KILLED ISO.2 + ISO.6 |
| `'IndexedDB is not available in this context \| R5B-LEAK-CONSTANT'` | **SURVIVED** | **KILLED ISO.2 + ISO.6** |
| `'IndexedDB is not available in this context'` (zero payload) | survived | survives *by design* |

Version six was **strictly weaker than the version it replaced**: §18.24 at least required writing a
second structure; this one required only choosing the right opening words — the original §18.20
message-prefix defect, restored.

**Fix.** The artifact message is built at exactly one site as
`'Evidence platform ['+context+'] '+kind+': '+message`, where `context` comes from a finite set of
literal call-site strings. The complete set of artifact messages is therefore enumerable, and
membership is now tested with `Set.has` — true equality. **Fail-closed under drift:** a new
production context that is not listed is *compared* rather than excluded, so a missing entry costs a
false failure, never a false pass.

*Methodology note.* My first two attack runs appeared to survive the repaired filter. They had not:
the injected leak referenced an identifier that threw inside the swallowing `catch`, so nothing was
ever recorded. A hit counter placed *before* the record call showed 66 invocations and concealed
this. **An injection counter proves the hook fired, not that the payload landed.** The control leak
was re-run with a constant message to establish that the hook could kill at all, before any survival
was believed.

### Fourteen fixtures that could not fail, across four suites

Twelve `assert` sites in `tests/v1212_manual_review_and_replay_diagnostics_tests.js` passed the
literal `true` (fourteen emitted PASS lines — one site is a three-mode `forEach`). Each printed a
PASS line and was counted in the gate total.

Two were **real safety gates** and are now driven end to end:

- **Fixture 38** — "Approve Paper Trade is disabled until the acknowledgment checkbox is checked."
  Now exercises `mrModalUpdateApproveEnabled()` in both directions, with a precondition proving the
  modal opened on a genuinely eligible candidate. Mutation-proven by removing the acknowledgment gate
  entirely. *The obvious mutation — dropping `||!ack` from `btn.disabled` — is an equivalent mutant,*
  because the `else if(!ack)` branch already sets `reason`; it was scored as the no-op it is rather
  than counted as a kill.
- **Fixture 44** — "Cancel creates no trade." Now closes the modal on an acknowledged, approvable
  candidate, with a positive control (`44pc`) that approves the identical setup and requires a trade
  to appear — so "no trade" cannot pass because nothing was approvable. Mutation-proven by making
  `closeManualReviewModal` commit.

The remaining ten are disclosed on a **NOTE channel** that is printed separately and is not counted
as a fixture. A claim a human checked by reading source is a note; only an executing assertion is a
fixture.

Two more in `v017_step2a`, both now real:

- **2A.19** asserted `true` *inside* an `if`, so the enclosing guard did all the work and the
  record's content was never checked — a record with the right stage but a null status or missing
  `tradeId` passed. It now asserts the stage, the status, the count and the `tradeId`.
- **2A.28** asserted `true` as a **precondition**. If no position had ever been opened, 2A.29's
  "closed" would have passed on an empty account while this line still claimed a real position
  existed. It now inspects the position under test.

**Phase2C.34** claims that no JVM function appears in a past release's diff. That is provenance, not
a runtime property, and no assertion can re-derive it at fixture time. It moves to the
`source-verified` note channel rather than pretending to be a test.

### Two more must-not-contain credential checks satisfied by emptiness

The `RollbackFailure.15` defect (§18.18) was fixed for **one** fixture and never generalised.

- **`HealthCheck.15`** — proven to pass when `buildPaperTradingHealthReportText` returns `''` (the
  same mutation kills `HealthCheck.29` and `RSTDG-VERDICT.3`). `HealthCheck.15a` now requires the
  report to carry its real structure before the credential check is applied.
- **v12.3.1 `Fixture 20`** was worse. It asserted that the TJR Developer tab exposes no credentials
  — *with no credentials configured anywhere*. There was nothing to leak, and no positive
  precondition, so both an empty render and a leaking one passed. It now installs sentinel secrets
  in live config and requires the tab to have genuinely rendered. Proven both ways: by an empty
  renderer (kills `20pre`) and by a real `cfg.accountId` leak wired into the **taken** return path
  (kills `20`) — the first leak attempt landed in an untaken early-return branch and was re-sited
  before being scored.

### Gate

34 suites, **2,215 / 2,215**, 0 execution errors, protected drift **0**. Fixture-count manifest
updated in both directions (v1212 52→42 as ten claims became notes and two real fixtures were added;
v126 61→60; v1231 31→32; restart-diagnostics 38→40; paper-trading audit 295→296).

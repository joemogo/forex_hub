# MOGO Research & Validation Standard v1.0

**Milestone:** MOGO-003 · **Date:** 2026-07-30 · **HEAD:** `a332d04` · **Engine:** `APP_VERSION` 12.7.0
**Status:** Proposed standard, awaiting Engineering Authority approval. **Documentation and repository analysis only — no code was modified.**

> **Governance basis.** Repository truth overrides prior assumptions. Every capability claim below
> cites a file, function and line. Where the repository uses the word *replay* but the capability is
> absent or partial, this document says so.

**Legend used throughout:**

| Tag | Meaning |
|---|---|
| ✅ **EXISTS** | Verified in code, working as described |
| 🟡 **PARTIAL** | Exists but incomplete or with a material caveat |
| ❌ **MISSING** | No implementation found |
| 📐 **PROPOSED** | This standard defines it; nothing implements it yet |

---

# SECTION 1 — PURPOSE AND SCOPE

## 1.1 Why MOGO requires a formal research standard

A real replay engine already exists (§1.4). What does not exist is a defined basis for **believing
its output**. Concretely, at HEAD:

- replay results are **session-only** and vanish on reload (`index.html:2137`), so no result is auditable after the fact;
- replay has **no run identifier**, so two runs cannot be told apart;
- the historical window is **anchored to wall-clock "now"**, so the same request returns a different dataset tomorrow;
- **spread and slippage are captured and deliberately given zero effect** on outcomes (`index.html:3634-3642`).

Those four facts mean a number produced today cannot be reproduced, cited, or compared. The standard
exists to fix that ordering: define the evidence rules **before** the first number is generated, so
no result is ever produced under rules written afterwards to fit it.

## 1.2 Scope

**Applies to:** every strategy MOGO evaluates — `alex_g_sr_v1` / `alex_g_sr_v1_1`, `JVM`, `TJR_SLR`,
`ALEX_SCORE_V2`, and any future strategy; and to every evidence-producing subsystem (replay, paper
trading, journal, statistics, Trader Intelligence).

**Does not apply to:** UI presentation, Academy content, or documentation structure.

## 1.3 What this standard does not claim to prove

**It cannot establish that any strategy will be profitable.** It governs whether a *claim* is
supported by reproducible evidence — never whether the underlying edge is real or durable.

> **Historical profitability does not prove future profitability.**
>
> **Replay results are research evidence, not a guarantee.**

## 1.4 The six distinct activities — never interchangeable

| # | Activity | Question answered | Repository status |
|---|---|---|---|
| 1 | **Implementation verification** | Does the code do what the specification says? | ✅ **EXISTS** — MOGO-002.5 fidelity toolchain, `scripts/strategy_fidelity/`, 63 tests |
| 2 | **Historical replay** | What would this strategy have done on past data? | 🟡 **PARTIAL** — engine exists (`alexGRunSetupReplay`, `index.html:3781`); results not persisted, not identified, not cost-modelled |
| 3 | **Backtesting** | Optimising parameters against history | ❌ **MISSING** — and deliberately so. No parameter sweep exists. `zoneClusterATRMultiplier` declares a `sensitivityRange` but nothing consumes it |
| 4 | **Forward paper trading** | What does it do on unseen live data? | ✅ **EXISTS** — ALEX v1.1 live paper engine, 60 s poll (`index.html:4676`) |
| 5 | **Statistical validation** | Is the sample large and stable enough to support a conclusion? | ❌ **MISSING** — no confidence interval, no sample-size gate, no tiering |
| 6 | **Live-trading validation** | Does it work with real money? | ❌ **OUT OF SCOPE, PERMANENTLY** — `ADR-004` establishes MOGO as read-only analytics; no order endpoint is ever called |

**The most common misreading this standard exists to prevent:** treating (1) as evidence for (2), or
(2) as evidence for (6). MOGO-002.5 verified ALEX is faithful to its own specification. That says
nothing about profitability.

---

# SECTION 2 — STRATEGY RESEARCH LIFECYCLE

Twelve mandatory stages. A strategy may not skip a stage or enter one before the prior gate passes.

**Authority key:** *Research* = Trader Intelligence workstream · *Engineering* = implementation ·
*EA* = Engineering Authority (human decision).

| # | Stage | Required input | Required output | Acceptance gate | Failure condition | Authority | Evidence retained |
|---|---|---|---|---|---|---|---|
| 1 | **Source acquisition** | Primary source + verified attribution | Registered `EvidenceSource` with content hash | Attribution verified; raw archive byte-preserved | Attribution unverifiable → `ATTRIBUTION_UNCERTAIN` | Research | `evidence/sources/`, raw + `.sha256` |
| 2 | **Reverse engineering** | Transcript | Verbatim excerpts + normalized claims | 100% of claims trace to an excerpt | Any claim without provenance | Research | `evidence/items/`, `claims/`, `links/` |
| 3 | **Rule classification** | Claims | Explicit / illustrative / opinion / unsupported | Every rule carries a class + evidence class | A demonstration promoted to a universal rule | Research | Canonical rule register |
| 4 | **Deterministic specification** | Classified rules | Rule set where every parameter has a value | **Every parameter is stated or explicitly MOGO-authored** | Any invented parameter presented as the educator's | EA | Specification JSON + rule-set hash |
| 5 | **Implementation** | Specification | Code + tests | Tests pass; zero protected drift | Drift, or an untested rule | Engineering | Test suite, drift report |
| 6 | **Repository verification** | Code + specification | Fidelity report | No `MISSING_IMPLEMENTATION`, no `IMPLEMENTATION_DIFFERS` | Any unexplained divergence | Engineering | `docs/strategy-fidelity/reports/` |
| 7 | **Strategy version release** | Verified implementation | Immutable version + changelog | New `ruleVersion`; prior version preserved | In-place edit of a released version | EA | `APP_VERSION_LOG`, `RELEASE_NOTES.md` |
| 8 | **Forward paper trading** | Released version | Live paper trades with version stamps | Engine running; every trade version-stamped | Untagged trade, or duplicates | Engineering | `fxhub_alexg_account`, `fxhub_alexg_journal` |
| 9 | **Historical replay** | Released version + §3 gate | Replay run + trades + rejected candidates | **§3 checklist all PASS** | Any FAIL | EA authorises; Engineering runs | Replay run record (📐 — see §15) |
| 10 | **Statistical validation** | Replay + paper results | Metrics at a declared tier | Tier requirements met (§9) | Sample below tier minimum | Research | Metrics report |
| 11 | **Decision** | Validation output | One of the six decisions (§12) | Objective criteria met | Decision on win rate alone | **EA only** | Decision record |
| 12 | **Promote / reject / revise / continue** | Decision | Action + changelog | Action matches the decision | Silent parameter change | EA | `OwnerDecision` record |

**Standing constraint at every stage:** `POLICY-001` — no rule is promoted to validated knowledge on
a single source; confidence rises only through independent corroboration, replay, paper trading, or
historical testing.

**Current position:** ALEX v1.1 has completed stages 1–8. **Stage 9 is gated by §3.**

---

# SECTION 3 — REPLAY READINESS GATE

## 3.1 The checklist

Every item must **PASS** before a strategy enters replay. Any **FAIL** blocks.

| # | Requirement | Verification method |
|---|---|---|
| R1 | Immutable strategy version | Version constant unchanged since release; drift check clean |
| R2 | Verified entry rules | Fidelity report shows no `MISSING_IMPLEMENTATION` |
| R3 | Verified exit rules | Every exit path enumerated and tested |
| R4 | Deterministic position sizing | Same inputs → same size, with no live-data dependency |
| R5 | Deterministic stop calculation | Formula fixed; inputs frozen at entry |
| R6 | Deterministic target calculation | Formula fixed; inputs frozen at entry |
| R7 | Explicit time and session handling | Candle and session timezone stated; day rules explicit |
| R8 | Transaction-cost assumptions | Spread, commission, slippage each **applied or explicitly declared zero** |
| R9 | Verified historical candle source | Provider, price side, granularity, availability window documented |
| R10 | No unresolved critical defects | Open CRITICAL defect list empty |
| R11 | Traceable decision logging | Every accept/reject reason recoverable after the run |
| R12 | Reproducible configuration | Full config captured in the run record |
| R13 | Known end-of-dataset handling | Open-position policy defined and applied |

## 3.2 Applied to ALEX v1.1 — repository evidence

| # | Result | Evidence |
|---|---|---|
| **R1** | ✅ **PASS** | `RULES_ALEXG_V11.ruleVersion = 'alex_g_sr_v1_1'`. `RULES_ALEXG` is a protected constant; drift check confirms 63 functions / 4 constants byte-identical |
| **R2** | ✅ **PASS** | `alex_g_sr_v1.fidelity-report.json`: 0 `MISSING`, 0 `DIFFERING`. Setup qualification is deterministic given candles |
| **R3** | ✅ **PASS** | Replay exits are exhaustive: `alexGWalkOutcome` (`index.html:3593`) → Win / Loss / Excluded / Still open |
| **R4** | ❌ **FAIL** | `alexGConstructTrade` calls `pipValuePerLot()`, which reads **live `pairData`** (`index.html:11842`). The code states: *"a live-data approximation, not historically exact"*. **Position size and money P&L are therefore non-reproducible.** R-based statistics are unaffected |
| **R5** | ✅ **PASS** | `stop = zoneLow/High ∓ 0.25 × ATR(14 @ qualification bar)`, `index.html:3660-3663`. ATR uses only candles ≤ qualification bar |
| **R6** | ✅ **PASS** | `target = entry ± 2.0 × riskDistance`, `index.html:3668-3670` |
| **R7** | 🟡 **PARTIAL** | Candle timestamps are UTC-derived; `getSession()` and `isPreferredTradingDay()` are UTC. **But:** the v1.1 Mon–Wed gate lives in the *live* path (`alexGEvaluatePairForLiveSetups`) and **is not applied by the replay path** — see §3.3 |
| **R8** | ❌ **FAIL** | `alexGConstructTrade` threads spread/slippage but the comment states they *"deliberately have ZERO effect on entry/stop/target/outcome math in this v1"* (`index.html:3634-3642`). Commission does not exist. Candles are fetched `price=M` — **mid only** (`index.html:5563`) |
| **R9** | 🟡 **PARTIAL** | Source verified: OANDA v3 `/instruments/{pair}/candles`, `granularity`, `price=M`, `complete` candles only. **But** a code comment records *"a hard ceiling around ~48 days of available OANDA practice history"* (`index.html:2008`) against a UI offering up to **365 days** |
| **R10** | ✅ **PASS** — *corrected 2026-08-04, see §3.5* | The defect this row originally cited was **already superseded when this document was written** and has since been **empirically falsified**. Corrected rather than retained. |
| **R11** | 🟡 **PARTIAL** | `alexGRunSetupReplay` returns a `rejected[]` array with reasons (`index.html:3790`). **But** it is session-only and captures only rejections at trade-construction stage — not rule-level detail |
| **R12** | ❌ **FAIL** | No run record exists. `runAlexGReplay` returns a plain object (`index.html:3926`) with **no run ID, no commit hash, no config snapshot, no timestamp** |
| **R13** | ✅ **PASS** | Still-open trades are explicit: `result='Still open'`, `exitBarIndex = candles.length-1`, excluded from `decided` statistics and counted separately (`stillOpenCount`) |

### 3.3 Gate verdict

> ### ⚠️ SUPERSEDED — 2026-08-04. The verdict below was recorded against HEAD `a332d04` / engine
> 12.7.0 and **two of its four blocking items no longer hold**. See §3.5 for the current position.
> The original text is preserved unedited, because a gate verdict that quietly changes is worthless
> as a record.

# ❌ **FAIL — 4 blocking, 3 partial, 6 pass**

**ALEX v1.1 may not enter replay.**

**Blocking (R4, R8, R10, R12).** The most serious is **R10**: a documented structural defect that
prevents one entire setup direction from ever occurring. A replay run today would produce a
directionally-biased sample and there would be no way to tell from the output that it had.

### 3.4 ⚠️ Additional finding — the v1.1 Mon–Wed gate is not in the replay path

Verified: the gate is implemented in `alexGEvaluatePairForLiveSetups` (live), and
`alexGRunSetupReplay` does not call `alexGV11EntryDayEligible`.

**Consequence:** a replay of "ALEX v1.1" would today replay **v1.0 entry behaviour**, and would
overstate trade count relative to live v1.1. This is not a defect in v1.1 — the gate was deliberately
placed in the non-protected live seam — but it means **replay and live are currently different
strategies**, and any comparison between them would be invalid.

📐 **PROPOSED:** replay must apply the identical eligibility rule set as live, or the run record must
declare which rules were not applied.

### 3.5 ✅ Correction — R10 / B1 struck, 2026-08-04

**This section corrects an error in this document. It is not a re-adjudication of the gate.**

**What R10 and B1 asserted.** Both cited the `APP_VERSION_LOG` v4.0 discovery that
`alexGProcessTimeframeCandle`'s role fallback made it *"structurally impossible for the frozen zone
engine to ever produce a validated, never-broken resistance-role zone, or a genuine
`brokenDirection='upThroughResistance'`."* R10 rated this the **most serious** of four blocking
items, on the reasoning that it biases the long/short distribution of any replay.

**Why it is wrong — two independent grounds.**

1. **It was already fixed before this document was written.** v4.0.1, the *Alex G S&R zone-role
   correction release*, replaced the `role = zone.lastKnownRole || 'support'` default with the
   deterministic, stateless `alexGInferPriorZoneRole(zone, candles, currentBarIndex)`, which searches
   strictly backward for the most recent completed close outside the zone, returns
   `support` / `resistance` / `unknown`, never defaults, and skips break detection entirely when no
   prior role can be established rather than guessing. **v4.0.1 predates engine 12.7.0**, the version
   this document was written against. The quoted limitation did not hold at the time of writing.

2. **It has since been falsified empirically.** Verified replay **RUN-001** (engine 12.9.0,
   `runId 3d7c3dc1af7f`) produced **8 validated never-broken resistance zones** and **3 Break & Retest
   BUY trades** carrying `brokenDirection: upThroughResistance` — packages `…20260518|1`,
   `…20260507|1`, `…20260617|2`. The capability the row calls impossible is directly observable in
   hash-verified evidence.

**Consequence for the gate.** R10 is **PASS**. B1 is **struck**, not downgraded — it describes a
defect that does not exist. `MOGO-003-CLOSEOUT.md` §4 recorded this as an outstanding stale claim;
this section closes it.

**What this correction does NOT do.**

- **It does not authorize any replay.** Authorization is a separate, explicit instruction from the
  Engineering Authority. This document is still marked *proposed, awaiting approval*, and an
  unapproved standard neither permits nor forbids a run.
- **It does not clear R4 or R8**, which were independently re-verified against engine 12.18.0 on
  2026-08-03 and **still hold**:
  - **R4** — `alexGConstructTrade` calls `pipValuePerLot()` (`index.html:3802` → `15031`), which reads
    live `pairData`. Money-space position size and P&L remain non-reproducible; **R-space is
    unaffected**.
  - **R8** — spread and slippage are threaded but *"deliberately have ZERO effect"*
    (`index.html:3755`); commission does not exist; a gap through a stop still fills at the exact stop
    price.
- **It does not clear §3.4**, which stands: replay does not apply the v1.1 Mon–Wed gate, so replay and
  live remain different rule sets and must never be compared without saying so.
- **R12 is separately closed** by MOGO-003's replay run identity (v12.9.0), which this document
  predates.

**Resulting scope of validity, not a pass/fail.** Replay evidence from this engine is valid for
**R-space comparisons** — expectancy in R, net R, win rate, MAE/MFE, drawdown in R — and is **not
valid** for money-space figures, for expectancy claims near zero where unmodelled costs of roughly
3–10% of risk per round turn could move the sign, or for any statement about live v1.1 behaviour.

**Correction basis.** `docs/MOGO-003-VERIFIED-REPLAY-RECORD.md` §RUN-001 ·
`docs/strategy-fidelity/ALEX-BREAK-RETEST-LOSS-FORENSICS-2026-07.md` §1.1 (corrected 2026-08-03) ·
`APP_VERSION_LOG` v4.0.1 · `docs/reports/MOGO-003-CLOSEOUT.md` §4.

---

# SECTION 4 — REPLAY PROTOCOL

Every run must declare all 25 fields below. 📐 **PROPOSED — no run record exists at HEAD.**

| # | Field | Current status | Note |
|---|---|---|---|
| 1 | `strategyId` | ✅ on each trade | `setup.strategy` |
| 2 | `strategyVersion` | 🟡 | `ruleVersion` on trades; replay uses `RULES_ALEXG.config` so it is always v1.0 |
| 3 | `softwareCommitHash` | ❌ | **Not captured anywhere.** `createdByEngineVersion` stores `APP_VERSION` only |
| 4 | `instrument` | ✅ | Single pair per run (`oPair`) |
| 5 | `timeframe` | ✅ | All four (H1/H4/D/W) per run |
| 6 | `historicalDateRange` | ❌ | **Only `days` back from now** — see §4.1 |
| 7 | `dataSource` | 🟡 | OANDA v3; not recorded in output |
| 8 | `candleTimezone` | 🟡 | UTC via RFC3339; not declared |
| 9 | `sessionTimezone` | 🟡 | UTC in `getSession()`; not declared |
| 10 | `spreadModel` | ❌ | Captured, **zero effect** |
| 11 | `commissionModel` | ❌ | Does not exist |
| 12 | `slippageModel` | ❌ | Captured, **zero effect** |
| 13 | `startingBalance` | ✅ | `replayParams.startBalance`, default 10000 |
| 14 | `riskPerTrade` | ✅ | `cfg.riskPercent = 1.0` |
| 15 | `maxSimultaneousPositions` | 🟡 | Enforced as one per pair+timeframe; never recorded as a parameter |
| 16 | `warmUpPeriod` | 🟡 | Implicit: `days*24+60` H1 candles; `<60` aborts. Never declared |
| 17 | `missingCandleHandling` | 🟡 | `c.complete` filter drops incomplete candles; gaps are not detected |
| 18 | `duplicateCandleHandling` | ❌ | No de-duplication logic found |
| 19 | `weekendHandling` | ❌ | No weekend logic; absent candles are simply absent |
| 20 | `marketGapHandling` | ❌ | A gap through a stop fills **at the stop price**, not the gap price (§11.3) |
| 21 | `orderFillAssumptions` | 🟡 | Entry = qualification close; stop/target = exact level |
| 22 | `intrabarSequencing` | ✅ | Explicit: same-candle stop+target is `ambiguous`, resolved conservative / optimistic / exclude |
| 23 | `endOfDataHandling` | ✅ | `Still open`, excluded from decided stats |
| 24 | `randomSeed` | ✅ **N/A** | No randomness in the engine — IDs are deterministic, verified no `Math.random` in the ALEX engine range |
| 25 | **`replayRunId`** | ❌ | **Does not exist** |

## 4.1 ⚠️ The date-range problem

`fetchCandlesRange` (`index.html:5557`) walks **backward from now** using OANDA's `to` cursor. There
is no `from` date. The UI offers 30 / 60 / 90 / 180 / 365 days.

**Therefore "90 days" means a different dataset every day it is run.** A run cannot be reproduced
tomorrow, and two runs a week apart are not comparable. 📐 The protocol must require **explicit
absolute `from`/`to` timestamps** recorded in the run record.

## 4.2 Replay-run ID

📐 **PROPOSED:** `RUN|<strategyVersion>|<YYYYMMDD>|<seq>`, deterministic, recorded on the run and on
every trade and rejected candidate it produces.

---

# SECTION 5 — DETERMINISM STANDARD

## 5.1 Definition

> The same **strategy version**, **code version**, **data**, **configuration** and **starting state**
> must produce **identical** results.

## 5.2 Fields that must match exactly between repeated runs

| Field | Deterministic at HEAD? | Evidence |
|---|---|---|
| Number of decisions / candidates | ✅ | Setup engine is pure over candles |
| Number of entries | ✅ | Deterministic sort + overlap rule |
| Timestamps | ✅ | Derived from candle close times |
| Entry prices | ✅ | `setup.qualificationClose` |
| Stop prices | ✅ | ATR at qualification bar |
| Target prices | ✅ | `2.0 × riskDistance` |
| Exits | ✅ | `alexGWalkOutcome` is pure |
| Realized R | ✅ | Fixed `+minRR` / `−1` |
| Rejection reasons | ✅ | Deterministic strings |
| **P&L (money)** | ❌ | `pipValuePerLot()` reads live `pairData` |
| **Final balance** | ❌ | Derived from money P&L |
| **Drawdown (money)** | ❌ | Same cause |
| Drawdown (R) | ✅ | R-based, independent of live data |

## 5.3 ⚠️ Determinism verdict

**ALEX replay is deterministic in R-space and non-deterministic in money-space.** The code discloses
this honestly and confines the contamination to informational fields.

📐 **PROPOSED:** until fixed, money-denominated metrics **may not be cited as validation evidence**.
R-denominated metrics may.

## 5.4 Deterministic replay test procedure

📐 **PROPOSED — no such test exists.**

1. Run with a pinned dataset and full configuration; record the run.
2. Re-run with identical inputs.
3. Compare every §5.2 field.
4. **Any mismatch fails validation** and blocks all downstream conclusions.
5. Re-run a third time on a different machine to catch environment dependence.

**Prerequisite:** a pinned dataset — impossible today (§4.1).

---

# SECTION 6 — REQUIRED TRADE RECORD

| # | Field | Status | Evidence / gap |
|---|---|---|---|
| 1 | Trade ID | ✅ | `alexGTradeId(setupId)` → `AGT\|<setupId>` |
| 2 | **Replay-run ID** | ❌ | **Missing** |
| 3 | Strategy ID | ✅ | `trade.strategy` |
| 4 | Strategy version | ✅ | `trade.ruleVersion` |
| 5 | Software version | 🟡 | `createdByEngineVersion` = `APP_VERSION`; **no commit hash** |
| 6 | Instrument | ✅ | `trade.pair` |
| 7 | Timeframe | ✅ | `trade.timeframe` |
| 8 | Direction | ✅ | `trade.direction` |
| 9 | Signal timestamp | ✅ | `qualificationTimestamp` |
| 10 | Entry timestamp | ✅ | `entryTimestamp` |
| 11 | Entry price | ✅ | `entry` |
| 12 | Stop price | ✅ | `stop` |
| 13 | Target price | ✅ | `target` |
| 14 | Exit timestamp | ✅ | `exitTimestamp` |
| 15 | Exit price | ✅ | `exitPrice` |
| 16 | Exit reason | 🟡 | `result` (Win/Loss/Excluded/Still open) — outcome, not a reason code |
| 17 | Planned R | ✅ | `plannedRR` |
| 18 | Realized R | 🟡 | `resultR` — **fixed `+minRR`/`−1`, not computed from the exit price**. Correct in replay (exits are exact at stop/target), unlike live |
| 19 | Monetary risk | 🟡 | `riskAmount` — non-deterministic (§5.3) |
| 20 | P&L | 🟡 | Same |
| 21 | Balance before | ✅ | `balanceBefore` |
| 22 | Balance after | 🟡 | Non-deterministic |
| 23 | MFE | ✅ | `mfePips`, `alexGComputeMAEMFE` |
| 24 | MAE | ✅ | `maePips` |
| 25 | Duration | ✅ | `barsHeld`, `calendarHours` |
| 26 | Qualifying rule evidence | 🟡 | Zone/touch/role fields present; **no per-rule pass list** |
| 27 | Rejection / override evidence | 🟡 | Separate `rejected[]`; not linked from the trade |
| 28 | **Source candle references** | ❌ | `entryBarIndex` is an **array index**, meaningless without the exact array. No candle timestamp/hash |
| 29 | **Data-quality flags** | ❌ | No gap, staleness, or completeness flag |

**Summary: 14 present, 10 partial, 5 missing.** The two most consequential absences are **#2
(run ID)** and **#28 (source candle references)** — without them a trade cannot be traced to the data
that produced it.

**Present and notable:** `lookaheadPass` / `lookaheadFailures` from `alexGValidateTradeNoLookahead`
(`index.html:3739`), which independently re-derives timestamps and is a genuine integrity control
beyond the required list.

---

# SECTION 7 — REJECTED-CANDIDATE RECORD

## 7.1 Why rejected candidates are necessary

Trades alone answer *"what happened?"* Rejections answer *"what nearly happened, and which rule
stopped it?"* Without them:

- no rule can be attributed a filtering cost (how much did the choppy filter actually remove?);
- a rule that never fires is indistinguishable from one that fires constantly;
- a future rule change cannot be evaluated against the population it would have affected;
- `AXR-008`-class questions (MOGO constrains where the educator declines to) are unanswerable.

## 7.2 Required fields

| # | Field | Status | Gap |
|---|---|---|---|
| 1 | Candidate ID | ✅ | `setupId` / `tradeId` in `rejected[]` |
| 2 | Timestamp | ❌ | **Not recorded on the rejection record** |
| 3 | Strategy version | ❌ | Not on the rejection record |
| 4 | Instrument | ✅ | `pair` |
| 5 | Candidate type | 🟡 | Only via `UNSUPPORTED_SETUP_TYPE` |
| 6 | **Rules passed** | ❌ | Not captured |
| 7 | **Rules failed** | ❌ | Only the first failing reason |
| 8 | Rejection reason | ✅ | 9 codes incl. `EXISTING_OPEN_TRADE_SAME_PAIR_TIMEFRAME`, `ATR_UNAVAILABLE`, `INVALID_ZONE_BOUNDS` |
| 9 | Market context | ❌ | Not captured |
| 10 | Deterministic? | ❌ | Not flagged |
| 11 | Data available? | 🟡 | Inferable from `NO_CANDLE_DATA` / `ATR_UNAVAILABLE` |

## 7.3 ⚠️ Structural limitation — rule-level detail is unreachable

`alexGEvaluateBreakRetest` and `alexGEvaluateRepeatedReaction` return `{qualifies:false}` and
**discard which of their conditions failed**. Both are protected functions.

**Therefore "rules failed" cannot be captured for setup qualification without a protected-function
edit.** This is the same limitation MOGO-002.5 recorded as `TRACE-LIM-001`. Rejections *after*
qualification (trade construction) are fully capturable.

## 7.4 Scope rule

📐 A candidate exists only where the strategy's own logic defines one — for ALEX, a touch reaching
`alexGClassifyTouch`. **Every candle must not become a candidate.**

---

# SECTION 8 — REQUIRED PERFORMANCE METRICS

`W` = wins, `L` = losses, `N` = decided trades, `Rᵢ` = realized R of trade *i*.

| # | Metric | Formula | Status | Finding |
|---|---|---|---|---|
| 1 | Total trades | count(all) | ✅ | `totalTrades` |
| 2 | Wins | count(`result='Win'`) | ✅ | |
| 3 | Losses | count(`result='Loss'`) | ✅ | |
| 4 | **Break-even trades** | count(`R = 0`) | ❌ | **Structurally impossible** — `resultR` is only `+minRR` or `−1` |
| 5 | Win rate | `W / N` | 🟡 | ⚠️ `Math.round(w/d*100)` — **integer percent**, loses precision |
| 6 | **Gross profit** | `Σ P&L where P&L > 0` | ❌ | Only R-space `grossWin` |
| 7 | **Gross loss** | `\|Σ P&L where P&L < 0\|` | ❌ | Only R-space |
| 8 | **Net P&L** | `Σ P&L` | ❌ | Non-deterministic (§5.3) |
| 9 | Net R | `Σ Rᵢ` | ✅ | `netR` |
| 10 | Average R | `Σ Rᵢ / N` | ✅ | = `expectancyR` |
| 11 | **Median R** | middle of sorted `Rᵢ` | ❌ | **Not computed** |
| 12 | Expectancy (R) | `(W/N)·avgWin_R − (L/N)·\|avgLoss_R\|` | ✅ | Equivalent to `netR/N` |
| 13 | Profit factor | `grossWin_R / \|grossLoss_R\|` | ✅ | Guards ÷0 → `Infinity` or `null` |
| 14 | **Average winner** | `Σ R(wins) / W` | ❌ | Degenerate — always `minRR` |
| 15 | **Average loser** | `Σ R(losses) / L` | ❌ | Degenerate — always `−1` |
| 16 | **Payoff ratio** | `avgWin / \|avgLoss\|` | ❌ | Degenerate — always `minRR` |
| 17 | **Max drawdown (money)** | peak-to-trough of balance | ❌ | Not computed; would be non-deterministic |
| 18 | **Max drawdown (%)** | `maxDD$ / peakBalance` | ❌ | Not computed |
| 19 | Max drawdown (R) | peak-to-trough of `Σ R` | ✅ | `maxDrawdownR` |
| 20 | **Recovery factor** | `netR / maxDrawdownR` | ❌ | Not computed |
| 21 | **Longest winning streak** | max consecutive wins | ❌ | Not computed |
| 22 | **Longest losing streak** | max consecutive losses | ❌ | Not computed |
| 23 | Average duration | `Σ duration / N` | ✅ | `avgBarsHeld`, `avgCalendarHours` |
| 24 | **Median duration** | middle of sorted durations | ❌ | Not computed |
| 25 | **Trades per week** | `N / weeks` | ❌ | Not computed |
| 26 | **Exposure** | `Σ time in market / total time` | ❌ | Not computed |
| 27 | **Max simultaneous positions** | max concurrent open | ❌ | Not computed (bounded by the overlap rule, never measured) |

**14 of 27 missing, 1 imprecise, 12 correct.**

## 8.1 ⚠️ The degenerate-metric finding

**Metrics 4, 14, 15 and 16 are not merely missing — they are meaningless under the current model.**
Because `resultR` is assigned `+minRR` for a win and `−1` for a loss, every winner is identical and
every loser is identical. Average winner ≡ 2.0R, average loser ≡ −1.0R, payoff ratio ≡ 2.0, *by
construction and regardless of what the market did*.

**This is defensible in replay** (exits land exactly on stop/target by definition of
`alexGWalkOutcome`) but it means those four metrics carry **zero information** and must not be
reported as if they did.

**It is not defensible in live paper trading**, where real exits slip — which is precisely why ALEX
v1.1 added `alexGRealizedR()` for the live path.

📐 **PROPOSED:** replay must adopt the same realized-R calculation, so replay and paper metrics are
computed identically and can legitimately be compared.

## 8.2 Additional analytics already present (beyond requirement)

`alexGComputeReplayStats` also produces breakdowns by pair, timeframe, setup type, session, day,
trend context, touch number, and psych-level bucket — plus long/short splits and MAE/MFE averages.
These are genuine capability and should be retained.

---

# SECTION 9 — SAMPLE-SIZE AND VALIDATION TIERS

**No single trade count proves profitability.** Tiers describe what a body of evidence *may* support.

| Tier | Purpose | Minimum evidence | Conclusions ALLOWED | Conclusions PROHIBITED |
|---|---|---|---|---|
| **0 — Engineering verification** | Code does what the spec says | Fidelity report; tests pass; zero drift | "Implementation is faithful to specification" | **Anything about profitability** |
| **1 — Initial behavioural sample** | Does it behave sanely? | ≥1 deterministic run; ≥10 trades; rejections captured | "Produces trades"; "rules fire as designed"; defect identification | Any statistical claim; any expectancy claim |
| **2 — Preliminary statistical sample** | First measurable estimate | ≥100 decided trades, single period, deterministic rerun verified | "Observed expectancy over this period was X R"; hypothesis generation | "The strategy is profitable"; extrapolation beyond the period |
| **3 — Cross-period validation** | Does it hold across regimes? | ≥3 non-overlapping periods, ≥100 trades each, dates fixed in advance | "Behaviour was consistent/inconsistent across periods"; regime dependence | Any live-trading expectation |
| **4 — Robustness validation** | Instrument/parameter sensitivity | ≥3 instruments; parameter sensitivity across declared ranges | "Result is/is not parameter-fragile"; "generalises across instruments" | "Optimal parameters are X" (that is optimisation, not validation) |
| **5 — Forward paper confirmation** | Does out-of-sample match? | ≥100 forward paper trades under the **same version**; compared to replay | "Forward behaviour is/is not consistent with replay" | "Proven profitable"; any real-money projection |

## 9.1 On the 50-trade question

**50 trades may support an operational review. It is insufficient by itself to prove durable
profitability.** At a 2R fixed payoff and ~40% win rate, the standard error on expectancy across 50
trades is large enough that a genuinely break-even strategy will frequently appear profitable, and
vice versa. **50 trades is Tier 1–2 evidence.** It can justify continuing, and cannot justify
promotion.

## 9.2 Tier-jumping is prohibited

Tiers are cumulative. Tier 3 requires Tier 2 satisfied on each period.

## 9.3 ALEX v1.1 current tier

**Tier 0 — engineering verification only.** Zero replay trades exist; forward paper trading has just
been released and holds no v1.1 trades yet.

---

# SECTION 10 — DATA PARTITIONING

## 10.1 Period definitions

📐 **PROPOSED — no partitioning exists at HEAD.** The UI offers only "N days back from now."

| Period | Purpose | Rule |
|---|---|---|
| **Development** | Building and debugging | Unlimited inspection. **Never cited as evidence** |
| **In-sample** | First measurement | Fixed dates declared before running |
| **Validation** | Tuning check | Separate from in-sample; limited examinations, each logged |
| **Out-of-sample** | Held back | **Examined once.** A second examination reclassifies it as validation |
| **Walk-forward** | Rolling re-validation | Sequential non-overlapping windows |
| **Forward paper** | True unseen data | Live; cannot be re-run |

## 10.2 ⚠️ Dates must be fixed before results are examined

**And this is currently impossible.** With no `from`/`to` control (§4.1), a period cannot be
pre-declared. **Explicit date-range support is a prerequisite for any tier above 1.**

## 10.3 Bias controls

| Bias | Definition | MOGO status |
|---|---|---|
| **Look-ahead** | Using data unavailable at decision time | ✅ **Genuinely controlled** — `alexGValidateTradeNoLookahead` independently re-derives timestamps; ATR uses only candles ≤ qualification bar; outcome walk starts at `entryBarIndex+1` |
| **Survivorship** | Only surviving instruments | 🟡 Low risk — major FX pairs |
| **Data leakage** | Test data influencing design | ❌ Uncontrolled — no partitioning |
| **Selection bias** | Choosing the flattering period | ❌ Uncontrolled — "N days back" is chosen at run time |
| **Overfitting** | Tuning to noise | 🟡 Low today — no optimiser exists; risk rises the moment `sensitivityRange` is swept |
| **Repeated holdout testing** | Re-testing the same holdout | ❌ No examination counter |

**Look-ahead control is the single strongest existing guarantee in the replay engine.** The other
five are unaddressed.

---

# SECTION 11 — TRANSACTION COSTS AND FILL MODEL

## 11.1 Current state

| Item | Status | Evidence |
|---|---|---|
| Bid/ask spread | ❌ **Zero effect** | Captured then ignored (`index.html:3634-3642`) |
| Commission | ❌ **Does not exist** | No commission field anywhere |
| Slippage | ❌ **Zero effect** | Same as spread |
| Stop fills | 🟡 | Filled at **exact stop price**; a gap through it is not modelled |
| Target fills | 🟡 | Filled at **exact target price** |
| Gaps | ❌ | Not detected or modelled |
| Same-candle stop **and** target | ✅ **Handled well** | `ambiguous` flag; conservative default = Loss |
| Candle-only limitation | ✅ **Disclosed** | Intrabar path unknown; acknowledged in code |

## 11.2 ⚠️ Consequence

**Replay results at HEAD are gross of all costs.** For a 2R strategy on major FX pairs, a 1–2 pip
spread against a stop distance of ~20–40 pips is roughly **3–10% of risk per round turn** — enough to
move a marginal expectancy across zero. **Reporting a replay expectancy without stating that costs
are excluded would misrepresent it.**

## 11.3 The gap-fill asymmetry

`alexGWalkOutcome` tests `bar.l <= stop` and fills at `stop`. If a candle **gaps through** the stop,
the real fill would be worse. The engine therefore **systematically overstates** outcomes in gap
conditions — most likely at weekly opens, which is exactly when FX gaps.

## 11.4 Proposed minimum standard

📐 Conservative handling is mandatory where intrabar order is unknowable:

1. Spread applied on **both** entry and exit, or explicitly declared zero **in the run record**.
2. Stop fills at `min(stopPrice, candleOpen)` for a long (worse of the two) when a gap is detected.
3. Target fills at the **target price only** — never better.
4. Same-candle stop+target defaults to **Loss** (already implemented).
5. Any cost declared zero must be stated in the run record and in every report drawn from it.

---

# SECTION 12 — STRATEGY DECISION FRAMEWORK

Decisions are made by the Engineering Authority only. **No decision may rest on win rate alone.**

| Decision | Objective requirements |
|---|---|
| **CONTINUE TESTING** | Tier requirements not yet met; no blocking defect; strategy behaves as specified |
| **PROMOTE TO NEXT TIER** | Current tier fully satisfied · deterministic rerun verified · no open CRITICAL/HIGH defect · costs modelled or explicitly declared · expectancy and drawdown both reported · implementation integrity confirmed |
| **REVISE** | A specific, named rule defect identified · change traceable to evidence · requires a **new strategy version** (§13) · prior results preserved |
| **REJECT** | Expectancy ≤ 0 across ≥2 independent periods at Tier 3+ · **or** drawdown exceeds a pre-declared tolerance · **or** the edge depends on a defect |
| **SUSPEND FOR DEFECT** | Any CRITICAL implementation defect · any determinism failure · any look-ahead failure. **Mandatory, not discretionary** |
| **INCONCLUSIVE** | Sample too small · data quality insufficient · results period-dependent without explanation. **A valid and expected outcome** |

## 12.1 Mandatory considerations

Every decision record must address **all eight**: expectancy · drawdown · trade count · stability
across periods · transaction costs · period dependence · implementation integrity · forward-paper
consistency.

**A decision citing fewer than eight is incomplete and must be returned.**

## 12.2 ALEX v1.1 today

**SUSPEND FOR DEFECT** would apply to *replay* — R10's structural directional defect is exactly the
mandatory-suspension case. It does **not** apply to forward paper trading, which is unaffected by a
replay-path bias and may continue.

---

# SECTION 13 — STRATEGY CHANGE CONTROL

## 13.1 When a new version is mandatory

Any change to: **entry logic · exit logic · filter logic · session logic · position sizing · risk
model · stop placement · target placement · trade management · transaction-cost model (when results
are being compared)**.

## 13.2 The repository already enforces this

✅ **EXISTS** — `RULES_ALEXG`'s own header states: *"Once alex_g_sr_v1 trades or zones exist, these
values must never change in place — any future rule or default change requires a new ruleVersion."*
ALEX v1.1 followed it: a new additive constant `RULES_ALEXG_V11`, with `RULES_ALEXG` byte-identical.
This is a genuine, working change-control mechanism and should be the model for every strategy.

## 13.3 Required artefacts per version

Changelog · rationale · rule source (educator / MOGO-authored / engineering necessity) · expected
effect · prior-version preservation · **independent replay results** · explicit prohibition on
overwriting prior results.

## 13.4 ⚠️ Gap

❌ **Results are not versioned.** Replay output is session-only with no version tag beyond
`ruleVersion` on individual trades. **A v1.0 and a v1.1 result set cannot currently be held side by
side** — the second run simply replaces the first in memory.

---

# SECTION 14 — ALEX v1.1 INITIAL REPLAY PLAN

**Not executed. Presented for approval only, and blocked by §3.**

| Item | Value | Source |
|---|---|---|
| Strategy identifier | `alex_g_sr_v1_1` | `RULES_ALEXG_V11.ruleVersion` |
| Engine version | `12.7.0` | `APP_VERSION` |
| Required commit/tag | **ENGINEERING AUTHORITY DECISION REQUIRED** | Nothing is committed; HEAD is `a332d04` and does not contain v1.1 |
| Instrument | `EUR_USD` | **EA DECISION REQUIRED** — highest liquidity / tightest spread among `SCAN_PAIRS`; not defined in code |
| Timeframes | H1, H4, D, W (all four) | Hardcoded; not selectable |
| Historical period | **EA DECISION REQUIRED** | No date-range control exists (§4.1) |
| Warm-up | ≥60 H1 candles (hard minimum); ATR needs 15; swing detection needs 3 either side | `index.html:3916`, `calcATR`, `trendSwingLookback` |
| Spread assumption | **EA DECISION REQUIRED** — recommend explicitly declaring **0.0 with costs excluded** until §11 is implemented | Currently zero-effect |
| Slippage | As above | |
| Commission | **Not modelled** | |
| Starting balance | `10000` | `replayParams.startBalance` default |
| Risk per trade | `1.0%` | `cfg.riskPercent` |
| Ambiguous-candle mode | `conservative` (count as loss) | UI default |
| Max simultaneous | 1 per pair+timeframe | `alexGRunSetupReplay` overlap rule |
| Required outputs | Trades, rejected candidates, R-space statistics | `alexGComputeReplayStats` |
| Deterministic rerun | **REQUIRED — cannot currently be satisfied** | §4.1, §5.3 |

## 14.1 Initial engineering test

**Purpose:** does the engine run correctly? — **not** is the strategy profitable.

1. Run once; record every §4 field obtainable.
2. Verify `lookaheadPass !== false` on **every** trade.
3. Verify rejection reasons are populated and plausible.
4. Re-run identically; compare all §5.2 fields.
5. **Expected failure at HEAD:** money fields will differ (§5.3), and the dataset itself will differ if runs straddle an H1 boundary.

## 14.2 Initial research test

**Purpose:** Tier 1 behavioural sanity only.

Does it produce trades? Are both directions represented? *(**Expected answer: no** — R10 predicts an
absent `upThroughResistance` direction. Confirming that prediction is itself a valuable result.)*
Are durations plausible? Does the rejection distribution make sense?

**Permitted conclusion:** "the engine produces trades and rules fire as designed / does not."
**Prohibited:** any expectancy claim.

## 14.3 Conditions that invalidate the run

Any `lookaheadPass === false` · non-identical rerun in R-space · fewer than 60 H1 candles · dataset
straddling a live H1 boundary · a code change mid-run · **any citation of money-denominated metrics**.

---

# SECTION 15 — CURRENT REPOSITORY GAP ANALYSIS

## 15.1 Replay-blocking defects

| # | Requirement | Status | Evidence | Severity | Blocks replay? | Milestone |
|---|---|---|---|---|---|---|
| ~~B1~~ | ~~Resistance-role zones can form~~ | ✅ **NOT A DEFECT** — *struck 2026-08-04, see §3.5* | Fixed by v4.0.1 before this document was written; falsified empirically by RUN-001 (8 validated never-broken resistance zones, 3 `upThroughResistance` breaks) | — | **NO** | — |
| B2 | Explicit date range | ❌ | `fetchCandlesRange` walks back from now; no `from` | **CRITICAL** | **YES** | MOGO-004 |
| B3 | Replay-run ID + run record | ❌ | `runAlexGReplay` returns a bare object | **CRITICAL** | **YES** | MOGO-004 |
| B4 | Result persistence | ❌ | `alexGReplayTrades` session-only (`index.html:2137`) | **CRITICAL** | **YES** | MOGO-004 |
| B5 | Deterministic money math | ❌ | `pipValuePerLot()` reads live `pairData` | **HIGH** | **YES** for money metrics | MOGO-004 |
| B6 | Transaction costs applied | ❌ | Zero effect by design (`index.html:3634`) | **HIGH** | **YES** for any expectancy claim | MOGO-005 |
| B7 | Replay applies v1.1 rules | ❌ | Mon–Wed gate is live-path only | **HIGH** | **YES** for a v1.1 replay | MOGO-004 |
| B8 | Commit hash on results | ❌ | Only `APP_VERSION` | **MEDIUM** | **YES** for auditability | MOGO-004 |

## 15.2 Validation-blocking defects

| # | Requirement | Status | Evidence | Severity | Blocks replay? | Milestone |
|---|---|---|---|---|---|---|
| V1 | Realized R in replay | 🟡 Degenerate | Fixed `±R`; §8.1 | **HIGH** | No | MOGO-005 |
| V2 | 14 missing metrics | ❌ | §8 | **HIGH** | No | MOGO-005 |
| V3 | Data partitioning | ❌ | No period concept | **HIGH** | No | MOGO-005 |
| V4 | Rejected-candidate detail | 🟡 | Reason only; rule-level unreachable (`TRACE-LIM-001`) | **MEDIUM** | No | MOGO-005 |
| V5 | Source candle references | ❌ | Array index only | **MEDIUM** | No | MOGO-005 |
| V6 | Win-rate precision | 🟡 | `Math.round(...*100)` | **LOW** | No | MOGO-005 |
| V7 | Data-quality flags | ❌ | No gap/staleness detection | **MEDIUM** | No | MOGO-005 |
| V8 | Result versioning | ❌ | Second run replaces the first | **MEDIUM** | No | MOGO-005 |

## 15.3 Future enhancements (explicitly not now)

| # | Item | Severity | Note |
|---|---|---|---|
| F1 | Parameter sensitivity sweep | LOW | `sensitivityRange` declared, unused. **Optimisation, not validation** |
| F2 | Multi-instrument runs | LOW | Tier 4 only |
| F3 | Walk-forward automation | LOW | Tier 3 prerequisite is partitioning |
| F4 | Rule-level rejection detail | MEDIUM | Requires a protected-function edit — EA decision |

---

# SECTION 16 — IMPLEMENTATION SEQUENCE

**Smallest safe path to a trustworthy first replay. Not started.**

### Phase 1 — Replay trustworthiness
**Deliverable:** explicit `from`/`to` date range; `replayRunId`; run record with full §4 configuration + commit hash; persisted results.
**Dependencies:** none.
**Exit criteria:** two runs of the same declared period produce the same dataset and two distinguishable, retrievable run records.

### Phase 2 — Deterministic engine verification
**Deliverable:** fix B1 (resistance-role defect) and B5 (live-data contamination in sizing); automated deterministic-rerun test (§5.4).
**Dependencies:** Phase 1 (needs pinned datasets).
**Exit criteria:** all §5.2 fields identical across two runs; both trade directions demonstrably reachable.

> **B1 requires editing a protected function** (`alexGProcessTimeframeCandle`). That is an **EA
> decision**, and it will require re-baselining. It cannot be done silently.

### Phase 3 — Trade and candidate evidence capture
**Deliverable:** trade records completed to §6 (run ID, candle references, data-quality flags); rejected-candidate records completed to §7 within the `TRACE-LIM-001` limit.
**Dependencies:** Phase 1.
**Exit criteria:** every trade traceable to its source candles; every rejection carries timestamp, version and reason.

### Phase 4 — Metrics and reporting
**Deliverable:** the 14 missing metrics; realized R in replay (V1); win-rate precision; a report distinguishing gross from net of costs.
**Dependencies:** Phases 2–3.
**Exit criteria:** every §8 metric computed or explicitly marked not-applicable with a reason.

### Phase 5 — Initial ALEX v1.1 replay
**Deliverable:** execute §14 under the approved standard.
**Dependencies:** Phases 1–4 complete; §3 checklist all PASS.
**Exit criteria:** a Tier 1 behavioural result with a verified deterministic rerun.

**Costs (B6) may be deferred to Phase 4** provided every report states results are gross of costs.

---

# SECTION 17 — FINAL READINESS DECISION

# ❌ NOT READY — BLOCKING DEFECTS EXIST

## 17.1 Basis

**8 replay-blocking items, 4 of them CRITICAL.** The determining ones:

1. **B1 — the structural resistance-role defect.** Documented in the repository since v4.0 and
   verified empirically. A replay today produces a **directionally biased sample with no indication in
   the output that it is biased.** This alone is disqualifying.
2. **B2 — no explicit date range.** "90 days back from now" cannot be pre-declared, so §10's
   requirement that dates be fixed before results are examined is unsatisfiable.
3. **B3/B4 — no run ID and no persistence.** A result that vanishes on reload and cannot be named is
   not auditable evidence.

**What is genuinely good and should not be rebuilt:** the look-ahead controls
(`alexGValidateTradeNoLookahead`), the ambiguous-candle handling, the deterministic ID scheme, the
still-open handling, the rich analytic breakdowns, and the change-control rule embedded in
`RULES_ALEXG`. **The engine's logic is sound; its evidence layer is not.**

## 17.2 Exact blocking items

**B1** resistance-role defect (CRITICAL, protected-code edit, EA decision) · **B2** date range
(CRITICAL) · **B3** run ID + record (CRITICAL) · **B4** persistence (CRITICAL) · **B5** deterministic
money math (HIGH) · **B6** transaction costs (HIGH — blocks expectancy claims, not the run itself) ·
**B7** replay does not apply v1.1 rules (HIGH) · **B8** commit hash (MEDIUM).

## 17.3 Exact next engineering task

> **Phase 1 only: replay trustworthiness.**
> Add explicit `from`/`to` date-range support to the ALEX replay path, a deterministic
> `replayRunId`, a run record capturing the full §4 configuration plus a commit hash, and persistence
> for run records and their trades.
>
> **All four are additive and touch no protected function.** This is the smallest change that makes
> any replay result citable.

## 17.4 What should NOT be worked on yet

- **Do not run a replay** — results would be unciteable and directionally biased.
- **Do not fix B1 yet.** It needs a protected-function edit and re-baselining; sequence it as Phase 2 with explicit EA authorisation.
- **Do not build metrics (Phase 4)** before determinism (Phase 2) — metrics over non-deterministic output are worse than none.
- **Do not model transaction costs** before results can be reproduced.
- **Do not begin parameter sensitivity work.** That is optimisation, and it is out of scope for this standard.
- **Do not acquire more educator research.** No verified missing educator rule blocks deterministic implementation; every blocker above is an engineering defect in MOGO's own evidence layer.

---

*MOGO-003 complete. Documentation and repository analysis only — no production code modified, no
strategy logic changed, no replay executed, nothing committed.*

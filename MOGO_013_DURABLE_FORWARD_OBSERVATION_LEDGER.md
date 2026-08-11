# MOGO-013 — Durable Forward Observation Ledger

**Status:** ✅ **COMPLETE — DURABLE FORWARD OBSERVATION ACTIVE**
**Commit:** `c4616770ceb52d28e2406dc72facaaf6d71e1135` · pushed to `origin/mogo-main`
**POST-MOGO-013 durable-observation era begins:** **`2026-08-11T14:59:03.962Z`** (observation `seq 1`)
**Date:** 2026-08-11 · **Campaign:** ALEX forward paper trading, running and untouched
**PAPER TRADING ONLY — live-money trading is not authorized**

---

## Executive summary

**The ledger is built, and it works.** 1,113/1,113 canonical fixtures pass, protected-function drift is **zero**, and a real IndexedDB test in a **disposable** profile proved **21/21** behaviours including the one that matters most: **all observations survived a page reload**.

**The running campaign was never touched.** It is still executing the *old* code — verified directly: the live page reports `EVIDENCE_DB_VERSION: 1` and `evidenceRecordForwardObservations: undefined`. The new code exists only on disk. Nothing was reloaded, restarted, or re-credentialed.

**Preservation was completed first and remains byte-identical** (`91abd1da…1a26a9`).

**The mutation protocol found three real gaps and all three are fixed.** Two were the same trap this codebase keeps setting: fixtures that test a *contract* while nothing tests the *wiring*. Silently feeding the ledger an empty status list, silently truncating it to one entry, and hardcoding retention to always evict all survived the first pass — each disabling the ledger's actual purpose while every builder test stayed green.

**One decision remains: activation requires a page reload, and a reload costs re-entering broker credentials.** That is yours to authorize.

## 1. Preservation — CRITICAL FIRST STEP ✅

### The artifact

| | |
|---|---|
| **File** | `MOGO-013-PRE-LEDGER-EPHEMERAL-RECOVERY.json` (repository root) |
| **Label** | **PRE-MOGO-013 EPHEMERAL FORWARD OBSERVATION RECOVERY** |
| **Schema** | `mogo.pre-013-recovery.v1` |
| **Size** | 954,526 bytes |
| **SHA-256** | `91abd1dab26da5b398108681700887c7ed5f0284410ef78a2b94baed5c1a26a9` |
| **Captured at** | 2026-08-11T13:41Z (campaign activated 2026-08-11T02:43:57.894Z) |
| **Method** | Chrome DevTools Protocol `Runtime.evaluate`, **read-only** — no application state written |

Hash re-computed after writing and again on independent re-read: **stable and identical**.

### What was recovered

| Content | Count |
|---|---|
| `alexGLiveSetupStatuses` (forward setup observations) | **300** |
| Decision Event log entries | **500** (ring at capacity) |
| Per-pair market-data cursors | **12** |
| Open / closed positions, journal entries | 0 / 0 / 0 |
| Evidence packages in store | 0 |
| Status breakdown | `IGNORED — BEFORE ACTIVATION` × 299 · `IGNORED — STALE SIGNAL` × 1 |
| Pairs represented | 10 of 12 |

**MOGO-012-INC-001 preserved intact:** AUD_JPY · H1 · `A_repeatedReaction` · `IGNORED — STALE SIGNAL` · `SIGNAL_TOO_OLD_AT_FIRST_EVALUATION`, with its full signal identity, qualification timestamp, first-evaluation timestamp and age.

### Provenance recorded in the artifact

The artifact carries a ten-field provenance block stating, in its own text:

- **source:** current runtime memory of the live page, read-only;
- **originallyDurable: `false`** — these observations were never persisted by the application;
- **exportedAfterTheFact: `true`** — captured hours after they were produced;
- **completenessGuarantee: `NONE`** — cannot be independently guaranteed; the array is capped at 300 in code, so earlier observations may already have been evicted, and the Decision Event ring had already wrapped;
- **knownArchitecturalLimitation:** MOGO-012-INC-001 demonstrated the limits of the original architecture — no durable polling/evaluation telemetry exists, so the record cannot be reconstructed or cross-checked against any independent source;
- **isNotEquivalentTo:** this is **not** equivalent to the future MOGO-013 durable ledger; it is a one-time salvage with lower guarantees;
- **transformationsApplied: `NONE`** — no field synthesized, defaulted, corrected, reordered or inferred.

No observation was converted into an evidence package. No history was rewritten. No missing field was manufactured.

---

## 2. What preservation revealed — the problem is worse than diagnosed

MOGO-012 concluded the observation record was *ephemeral*. Measurement shows it is **ephemeral and actively self-overwriting**.

**Same signal, two readings, hours apart:**

| Reading | `firstLiveEvaluationTimestamp` | Age at evaluation |
|---|---|---|
| Morning audit (12:03Z) | `2026-08-11T12:01:05.807Z` | **361.10 min** |
| Recovery capture (13:41Z) | `2026-08-11T13:01:02.086Z` | **421.03 min** |

Every one of the 300 entries carries a first-evaluation timestamp inside a single ~28-second window (13:00:46 → 13:01:14Z). **The entire array was rebuilt in one poll tick.**

**Why:** `alexGLivePollTick` ticks every 60 s but only *evaluates* when a new completed H1 candle exists (`if(currentH1Boundary<=lastEval) continue;`). Evaluation therefore runs **hourly, at the top of the hour**, re-deriving setups from 90 days of candles each time. Because the signal identity embeds an advancing zone version, each hourly pass records **new** status entries, and the 300-entry cap evicts the previous hour's.

**Consequences, stated plainly:**

1. The exact values my morning audit quoted **no longer exist in the system**. They survive only in that document and in this analysis.
2. Observations from earlier in the campaign are **already permanently gone** — evicted before any capture was possible.
3. The recovery artifact is an honest snapshot of **one hour's re-derivation**, not the campaign's history. Its provenance says so.

**A factual refinement to MOGO-012-INC-001, discovered by measurement.** My morning audit described the stale classification as "final and non-retryable." `liveEvaluationFinal: true` is indeed set on the entry — but the *entry itself* is re-created each hour under a new signal identity, with a freshly computed first-evaluation time and a steadily increasing age. The setup is therefore effectively **re-decided hourly**, not decided once. This is frozen-strategy behaviour and **must not be changed**; it is recorded here because it materially changes how the incident should be read, and because it is exactly the kind of fact that only a durable ledger would have made visible without a same-day audit.

---

## 3. Attachment seams and protected functions

**Verified against `regression-baseline-tools.py` (64 protected functions):**

| Function | Status | Role |
|---|---|---|
| `alexGRecordLiveSetupStatus` | 🔒 **PROTECTED** | records status entries — **must not be touched** |
| `alexGIsSetupSignalStale` | 🔒 **PROTECTED** | staleness rule — **must not be touched** |
| `alexGRunSetupEngine` | 🔒 **PROTECTED** | setup engine — **must not be touched** |
| `alexGLivePollTick` | ✅ not protected | **poll seam** |
| `alexGEvaluatePairForLiveSetups` | ✅ not protected | **evaluation seam** |
| `alexGAttemptOpenLivePosition` | ✅ not protected | trade-pipeline seam |
| `emitDecisionEvent` | ✅ not protected | existing fire-and-forget bus |
| `evidencePersistTradePackage` | ✅ not protected | evidence capture seam |

**Precedent:** these are the identical seams the Decision Event bus used in v12.5.0 / v12.6.0, which shipped with **zero protected-function drift**. The pattern is proven in this codebase: additive, fire-and-forget, return value never consulted by the trading path.

---

## 4. What was built

### Files changed — three

| File | Change |
|---|---|
| `index.html` | **+~300 / −4** — schema v2, the `observations` store, six pure builders/analysers, four async writers, and the poll-seam attachment |
| `tests/v128_evidence_platform_tests.js` | **+21 fixtures** (L1–L19, L15b) plus D2 re-expressed and SI1/SI2 updated for the v2 schema |
| `tests/run_v128_evidence_platform_tests.js` | ledger surface exported to the harness |

### Schema — `mogo.observation.v1`

New object store **`observations`** in the existing `mogo_evidence` database, key `observationId`, with a **UNIQUE `naturalKey` index** (structural duplicate protection), plus `bySeq` (unique), `byKind`, `byOccurredAt`.

**Common to every record:** `schemaVersion`, `kind`, `seq` (monotonic), `occurredAt` **and** `recordedAt` as distinct fields, `captureOrigin`, `appVersion`, `strategyId`, `provenance: FORWARD_LIVE_OBSERVATION`.

| Kind | Carries |
|---|---|
| **POLL** | `tickId`, `startedAt`/`finishedAt`/`durationMs`, `outcome` (OK / ERROR / SKIPPED_DISABLED), `expectedIntervalMs` **stored on the record**, `tradingEnabled`, `evaluationAdvanced`, `instrumentsAttempted`, `instrumentsEvaluated[]`, `failures[]`, `errorText` |
| **EVALUATION** | `signalId`, `setupId`, `pair`, `timeframe`, `setupType`, `direction`, `qualificationTimestamp`, `firstLiveEvaluationTimestamp`, `signalAgeMinutesAtEvaluation`, `status`, `reason`, `liveEvaluationFinal`, `zoneId`, `zoneTouchNumber`, `strategyVersion`, `engineVersion`, `configHash`, `paramsHash`, `scanId`, plus clearly-named `derived*` classifications |
| **PIPELINE** | `stage`, `pair`, `setupId`, `signalId`, `status`, `reason`, and **references only** — `sourceTradeId`, `tradeId`, `packageId` |
| **RETENTION** | `evictedCount`, `evictedSeqFrom`/`To`, `evictedOccurredFrom`/`To`, `evictedByKind`, `cap`, `retentionReason`, and a note that the range is not recoverable from this store |

**Derived fields are named as derivations** (`derivedStale`, `derivedQualifying`, `derivedActivationCutoffPassed`, `ruleAttribution`) so a future reader can always separate an observation from an interpretation.

### Attachment point — one seam, non-protected

`alexGLivePollTick` only. Local bookkeeping variables, a ledger call in the **`finally`** block so a *failed* poll is recorded too, and an early call on the disabled path so "running but off" is distinguishable from "not running". The original `throw e` is preserved exactly.

**Protected functions untouched:** `alexGRecordLiveSetupStatus`, `alexGIsSetupSignalStale`, `alexGRunSetupEngine` — fixture **L16** asserts the ledger never even references them.

### Integrity design

- **Duplicate protection is structural** — `add()`, never `put()`, against a UNIQUE index. A duplicate returns `DUPLICATE_ALREADY_RECORDED`, which is a success: the observation is already durably recorded.
- **The hourly re-creation MOGO-012 discovered is preserved deliberately.** `EVAL` natural keys include `firstLiveEvaluationTimestamp`, so each hourly re-evaluation is a **distinct** observation. Collapsing them would erase the exact phenomenon the ledger exists to record.
- **Retention can never delete silently.** The RETENTION marker naming the evicted range is written **before** anything is removed, so a crash between the two loses nothing quietly. Cap 200,000 (~a month); planning is a pure, inspectable function.
- **Observation can never affect trading** — never awaited, return value never read, wrapped in its own `try`, failures routed to the existing write-failure channel.

---

## 5. Validation results

### Canonical regression and drift

| Gate | Result |
|---|---|
| `run_v128_evidence_platform_tests.js` | **320/320** (300 → 320) |
| **Canonical gate** | **18 suites · 1,113 fixtures · 1,113 passed · 0 failed** |
| **Protected-function drift** | **0** — 63 functions, 4 constants byte-identical |

### Real IndexedDB test — disposable profile, port 8752, **21/21**

Run in a fresh disposable profile via `browser_test_profile.sh`, on a separate port, with a separate debugging port. **The campaign profile was never opened by this test.**

```
PASS  database upgraded to v2                    PASS  sequence numbers unique and monotonic
PASS  observations store created                 PASS  6-minute gap detected, 5 missed intervals
PASS  packages and meta intact after upgrade     PASS  the gap is reported
PASS  successful AND failed polls persisted      PASS  evaluation stats derived from the store
PASS  rejected setup persisted                   PASS  ALL 7 observations SURVIVED PAGE RELOAD
PASS  qualifying setup persisted                 PASS  polls and evaluations both survived
PASS  stale setup persisted                      PASS  gap still computable after reload
PASS  hourly re-creation = TWO distinct records  PASS  retention plans eviction when over cap
PASS  duplicate reported, count NOT inflated
```

### Mutation protocol — 9 applied, 8 detected, 1 control correctly unflagged

| Mutation | Result |
|---|---|
| A — hourly re-creation deduped away | DETECTED (L6) |
| B — `add()` → `put()`, history overwritable | DETECTED (L8) |
| C — retention marker written *after* deletion | DETECTED (L13) |
| **D — seam feeds an empty status list** | **SURVIVED → fixed → DETECTED (L15b)** |
| E — `finally` removed, failed polls unrecorded | DETECTED (L2) |
| F — behaviour-preserving edit *(control)* | correctly **not** flagged |
| **G — seam silently truncates the feed** | **SURVIVED → fixed → DETECTED (L15b)** |
| **H — retention ignores its own planner** | **SURVIVED → fixed → DETECTED (L13)** |
| I — provenance stripped | DETECTED (L18) |

`index.html` restored byte-identical after every mutation.

**The three survivors are the honest headline.** D, G and H each disabled the ledger's real purpose while every builder fixture stayed green — a ledger wired to nothing, a feed truncated to one entry, and a retention planner nobody consulted. This is the third milestone in a row where the gap was *contract tested, wiring untested*.

### Integrity

| Check | Result |
|---|---|
| Campaign C1 | **33/33 · 0 missing · 0 mismatched · 0 unlisted** |
| Legacy corpus | **220 re-derived · 0 mismatched**, rollup matches |
| Existing evidence packages | untouched; `packages`/`meta` verified intact after the v2 upgrade |
| **Pre-MOGO-013 recovery artifact** | **UNCHANGED** — `91abd1dab26da5b398108681700887c7ed5f0284410ef78a2b94baed5c1a26a9` |
| MOGO-012-INC-001 | preserved, not rewritten |
| Repository | `8e8a0af`, 3 files modified, **nothing committed**, 0 ahead / 0 behind |

---

## 6. ACTIVATION — executed and verified

### Sequence

| Step | Result |
|---|---|
| 1 · Pre-commit verification | intended files only; recovery artifact unchanged; gate 1,113/1,113; drift 0; C1 33/33; corpus 220/0 ✅ |
| 2 · Commit and push | **`c4616770ceb52d28e2406dc72facaaf6d71e1135`** → `origin/mogo-main`, trees identical, 0 ahead / 0 behind ✅ |
| 3 · Pre-activation capture | recorded below; evidence store already checkpointed (rollup unchanged) ✅ |
| 4 · Controlled reload | `2026-08-11T14:57:16Z` ✅ |
| 5 · Schema activation | v1 → **v2**, `observations` created, `packages`/`meta` intact ✅ |
| — · Credential restoration | performed **by the operator** through the normal MOGO connect interface ✅ |
| 6 · ALEX restoration | enabled, polling, **original cutoff intact** ✅ |
| 7 · First live observations | **609 durable observations written** ✅ |
| 8 · Read-back and integrity | 609/609 valid, zero defects ✅ |
| 9 · Post-activation health | **GREEN** ✅ |

### Pre-activation state — recorded `2026-08-11T14:56:42Z`

ALEX enabled `true` · activated `2026-08-11T02:43:57.894Z` · balance **$10,000.00** · 0 open / 0 closed / 0 journal · 0 wins / 0 losses · **0 evidence packages** · polling active · 300 in-memory statuses · 12 cursors · 0 write failures · `alex_g_sr_v1` / 12.19.0 · loaded code `EVIDENCE_DB_VERSION: 1`, ledger absent.

### The activation cutoff is INTACT — the critical scientific check

| | |
|---|---|
| Before reload | `1786416237894` = `2026-08-11T02:43:57.894Z` |
| **After reload** | **`1786416237894` = `2026-08-11T02:43:57.894Z`** |

**Byte-identical.** The campaign's activation boundary was preserved through the reload, restored from `fxhub_alexg_auto` rather than re-stamped. The operator confirms ALEX was **not** manually toggled and the account was **not** reset. The frozen forward sample is continuous across activation.

Strategy identity unchanged: `alex_g_sr_v1` / APP_VERSION 12.19.0. Balance **$10,000.00**, 0 open / 0 closed / 0 journal — reconciles exactly with pre-activation.

### A moment worth recording

Immediately after the reload the page reported `alexEnabled: false` and `activatedAt: null`, which looked like the campaign had been lost. It had not: MOGO was sitting on its connect screen and had not yet loaded stored ALEX state, while `localStorage.fxhub_alexg_auto` still held `{"enabled":true,"activatedAt":1786416237894}`. Checking the durable value before reporting is what distinguished "state lost" from "state not yet loaded" — and is why the activation procedure requires verification rather than inference.

---

## 7. First live durable observations — the decisive test

**609 observations written from genuine live forward activity**, within ~10 minutes of activation, with **zero write failures**.

| | |
|---|---|
| POLL | **9** — all `outcome: OK`, 12/12 instruments |
| EVALUATION | **600** — 598 `IGNORED — BEFORE ACTIVATION`, **2 `IGNORED — STALE SIGNAL`** |
| RETENTION | 0 (cap 200,000 nowhere near) |
| Poll continuity | last successful `15:07:04.164Z`, expected interval 60,000 ms, max gap 81,200 ms, **0 missed intervals**, 0 gaps |

**First durable observation — `seq 1`, the start of the POST-MOGO-013 era:**

```
observationId  OBS|1|POLL|SCAN|1786460343962-3
occurredAt     2026-08-11T14:59:03.962Z    recordedAt 2026-08-11T14:59:19.744Z
outcome        OK      durationMs 15782    expectedIntervalMs 60000
instruments    12 attempted, 12 evaluated (all pairs)
captureOrigin  http://localhost:8751       provenance FORWARD_LIVE_OBSERVATION
```

**The observation that proves the point — MOGO-012-INC-001's AUD_JPY signal, now durable:**

```
signalId        AGL|alex_g_sr_v1|AUD_JPY|H1|...|1786428000000
setupId         AGS|alex_g_sr_v1|AUD_JPY|H1|...   zoneId AGZ|...  touch 4
pair/timeframe  AUD_JPY / H1        setupType A_repeatedReaction
qualifiedAt     2026-08-11T06:00:00.000Z
firstEvaluated  2026-08-11T15:00:38.512Z    age 540.64 min
status          IGNORED — STALE SIGNAL
reason          SIGNAL_TOO_OLD_AT_FIRST_EVALUATION
ruleAttribution ALEX_SIGNAL_STALENESS       derivedActivationCutoffPassed true
strategyVersion alex_g_sr_v1   engineVersion 12.19.0   scanId SCAN|1786460403966-776
seq 392
```

This is the same signal the morning audit could only read from volatile memory, and whose earlier readings no longer exist anywhere in the system. **It is now on disk with full identity and provenance** — and its age climbing from 361 → 421 → 540 minutes across successive hours captures, durably and for the first time, the hourly re-creation behaviour MOGO-012 discovered. No trade or setup was manufactured; these are ordinary rejected evaluations, which is exactly what was needed.

`configHash` / `paramsHash` are `null` on these records. That is correct, not a gap: those fields are REPLAY-only by design and are null for `LIVE_PAPER` in the committed schema.

---

## 8. Read-back and integrity verification

Every observation was read back from IndexedDB and checked:

| Check | Result |
|---|---|
| Total read back | **609** |
| Unique `seq` | **609** — range 1…609, **no gaps, no duplicates** |
| Unique `naturalKey` | **609** — zero collisions |
| Ordering | monotonic ✅ |
| Wrong/missing `schemaVersion` | **0** |
| Missing `provenance` | **0** |
| Missing `captureOrigin` | **0** |
| Missing `observationId` | **0** |
| Distinct origins | **1** — `http://localhost:8751` |

**WRITE → READ BACK → IDENTITY/INTEGRITY → DURABLE STORE: proven on live data.** No additional reload was performed; offline testing already proved reload survival, and interrupting the campaign again to re-prove it would have been gratuitous.

---

## 9. Post-activation health — 🟢 GREEN

| Component | Status |
|---|---|
| Polling active | 🟢 9/9 polls OK |
| Broker / API healthy | 🟢 no failures, no errors |
| Instruments healthy | 🟢 **12 of 12** |
| Evidence capture armed | 🟢 store live, 0 packages (no trades yet) |
| **Observation ledger active** | 🟢 **609 observations, 0 failures** |
| Evidence write failures | 🟢 0 |
| Ledger write failures | 🟢 0 |
| Campaign C1 | 🟢 **33/33 · 0 mismatched** |
| Legacy corpus | 🟢 **220 re-derived · 0 mismatched** |
| Recovery artifact | 🟢 `91abd1da…1a26a9` unchanged |
| Protected-function drift | 🟢 **0** |
| Repository | 🟢 `c461677`, clean, 0 ahead / 0 behind |
| Strategy unchanged | 🟢 `alex_g_sr_v1` / 12.19.0, cutoff intact |

**No stop condition was triggered at any point.** No migration failure, no evidence lost, no integrity change, no drift, no unexpected balance or position change, no interference with polling or evaluation — poll durations ran 1 ms when idle and 15.8 s during full evaluation, with the ledger never awaited on the trading path.

---

## 10. The scientific boundary

| Era | Record |
|---|---|
| **PRE-MOGO-013** | `MOGO-013-PRE-LEDGER-EPHEMERAL-RECOVERY.json` — recovered ephemeral observations, after the fact, from runtime memory, **completeness explicitly unguaranteed** |
| **POST-MOGO-013** | Durable observations under `mogo.observation.v1`, beginning **`2026-08-11T14:59:03.962Z`** |

**Nothing was backfilled.** The ledger contains only observations captured live after activation. The recovery artifact remains a separate, hashed, clearly-labelled salvage and is not merged into the store.

**MOGO-012-INC-001 is preserved exactly.** Its historical unknown interval was not rewritten and remains unknown. MOGO-013 provides future observability and manufactures no retroactive certainty — from now on, a gap of that kind would be *measured*, not inferred.

---

## 11. Completion conditions

| # | Condition | |
|---|---|---|
| 1 | Code committed and pushed | ✅ `c461677` |
| 2 | Durable profile schema activated | ✅ v2, observations store |
| 3 | Credentials safely restored | ✅ by operator, normal interface |
| 4 | ALEX resumed forward polling | ✅ 9/9 polls, 12/12 instruments |
| 5 | Live forward observations written durably | ✅ 609 |
| 6 | Observations read back and verified | ✅ 609/609, zero defects |
| 7 | Existing trade evidence intact | ✅ 0 → 0, none lost |
| 8 | Campaign C1 intact | ✅ 33/33 |
| 9 | Legacy corpus intact | ✅ 220, 0 mismatched |
| 10 | Protected-function drift zero | ✅ 0 |
| 11 | Repository synchronized | ✅ 0 ahead / 0 behind |
| 12 | POST-MOGO-013 start timestamp recorded | ✅ `2026-08-11T14:59:03.962Z` |

**All twelve pass.**

---

## 12. Remaining limitations

- The ledger does not retroactively explain MOGO-012-INC-001; the historical unknown interval stays unknown.
- The recovery artifact is not the campaign's history — one hour's re-derivation, captured after the fact.
- **Credentials remain memory-only.** MOGO-013 does not make the campaign survive a restart unattended; a reload still requires manual reconnection. That is a separate milestone with its own security governance.
- Retention rollover is unit- and plan-tested but has never triggered at the 200,000 cap — roughly a month away at ~600 observations/hour.
- The ledger records the frozen strategy's hourly re-creation behaviour faithfully. Changing that behaviour would be a separately governed strategy decision.

---

## 13. Backlog — preserved, not implemented

**MOGO-012-BL-001 — Audible notification on confirmed paper execution only.** Sound must fire only after a **confirmed successful paper trade execution/opening**; watching, scanning, monitoring or evaluating a pair must not trigger it. *Not implemented.*

---

## 14. Next milestone

**MOGO-014 — connect the governed automation runtime to real research acquisition.** With durable forward observation solved, autonomous research returns to the critical path: the runtime has 31 modules and **zero effectful capabilities registered**, while 34 research scripts run only by hand. Registering the first effectful acquire→ingest capability with a scheduled trigger turns both halves into one autonomous loop.

---

*Activated, verified, and complete. The forward campaign is running with durable observation active.*

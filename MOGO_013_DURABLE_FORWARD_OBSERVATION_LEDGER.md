# MOGO-013 — Durable Forward Observation Ledger

**Status:** ✅ **BUILT AND VALIDATED OFFLINE** · ⏸️ **NOT ACTIVATED — awaiting MOGO-013 ACTIVATION AUTHORIZATION**
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

## 6. 🛑 ACTIVATION DECISION PACKAGE

### Does activation require a page reload? **Yes.**

Proven directly against the live page: it reports `EVIDENCE_DB_VERSION: 1` and `evidenceRecordForwardObservations: undefined`. It loaded its JavaScript at `2026-08-11T02:34:44Z` and will not use the new code without a reload.

### Expected campaign interruption

| | |
|---|---|
| Market monitoring | **stops from reload until credentials are re-entered** |
| Evaluation cadence | hourly, on the H1 boundary — a reload between boundaries costs no evaluation if credentials are restored before the next hour |
| Lost on reload | the ~300 in-memory statuses **(already preserved)**, the 12 per-pair cursors, the Decision Event ring |
| Survives | `activatedAt` and enabled state, paper account, journal, **all IndexedDB evidence**, Campaign C1, checkpoints |
| Paper account | **untouched** — $10,000.00, 0 open, 0 closed |

### Credential implications

Broker credentials are **memory-only** — no credential key exists in `localStorage`. **They must be re-entered by hand after the reload**, and polling does not resume until they are. This is the single largest cost of activation and the reason it is not automatic.

### Risks of activation

| Risk | Severity | Mitigation |
|---|---|---|
| Credentials not re-entered promptly → extended monitoring gap | **Medium** | Reload only with credentials to hand |
| IndexedDB v1→v2 upgrade fails on the live store | **Low** | Upgrade is additive and was exercised on a real profile; `packages`/`meta` verified intact |
| Ledger write volume affects the tab | **Low** | Fire-and-forget, never awaited; ~300 records/hour |
| Reload lands mid-hour and skips an evaluation | **Low** | Reload just *after* an hourly evaluation |
| A new defect in ledger code affects trading | **Low** | Never awaited, return value never read, own `try`; drift 0; L15/L16 assert isolation |

### Recommended safest activation window

> **Shortly after an hourly evaluation completes (a few minutes past the hour), with broker credentials to hand, on AC power with the tab foregrounded.**

The current campaign has produced **zero trades and zero evidence packages**, so the reload costs no trade evidence — only in-memory observations that are already preserved. **This is the cheapest activation window the campaign will ever have**, and it gets cheaper never: once trades exist, a reload carries more risk.

---

## 7. Remaining limitations

- **The ledger does not retroactively explain MOGO-012-INC-001.** It makes *future* continuity measurable. The historical unknown interval stays unknown.
- **The recovery artifact is not the campaign's history** — one hour's re-derivation, captured after the fact, completeness explicitly unguaranteed.
- **Credentials remain memory-only.** MOGO-013 does not make the campaign survive a restart unattended; that is a separate milestone with its own security governance.
- **Retention rollover has been unit- and plan-tested but never triggered at the 200,000 cap** in a live store. At ~300 records/hour that is roughly a month away.
- **The ledger records what the frozen strategy does, including the hourly re-creation.** Any proposal to change that behaviour is a separately governed strategy decision, not a MOGO-013 concern.

---

## 8. Backlog — preserved, not implemented

**MOGO-012-BL-001 — Audible notification on confirmed paper execution only.** Sound must fire only after a **confirmed successful paper trade execution/opening**; watching, scanning, monitoring or evaluating a pair must not trigger it. *Not implemented.*

**Phase II follow-on:** once durable forward observation is operational, autonomous research acquisition returns to the critical path — connecting the governed automation runtime (31 modules, **zero effectful capabilities registered**) to the 34 existing research scripts.

---

## 9. Next action

# ⏸️ REQUESTING: MOGO-013 ACTIVATION AUTHORIZATION

Built, validated, and **not activated**. The campaign is running untouched on the old code. On your authorization I will reload the durable MOGO page at a moment you choose, confirm the v1→v2 upgrade succeeded with all evidence intact, and verify the ledger begins recording — after which you re-enter broker credentials to resume monitoring.

**Nothing is committed.** Say the word and I will commit and push first, or activate first, in whichever order you prefer.

---

*Built and validated offline. The running forward campaign was not modified, reloaded, or interrupted at any point.*

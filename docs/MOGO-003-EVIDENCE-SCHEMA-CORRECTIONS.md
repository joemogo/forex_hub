# MOGO-003 — Evidence Schema & Replay Reporting Corrections

**Status:** PLAN ONLY — no code written, no package modified, nothing staged.
**Origin:** MOGO-003 forensic reconciliation, 2026-08-03. Source run: `docs/MOGO-003-VERIFIED-REPLAY-RECORD.md` §RUN-001.
**Baseline:** engine 12.9.0 · commit `65c9444` · schema `mogo.evidence-package.v1` · canon `mogo.evidence-canon.v1`.

---

## 0. The two constraints that shape every item below

**C-1 — The classification engine is PROTECTED and cannot be edited.**
`regression-baseline.json` protects 63 functions and 4 constants. The functions that *know* the
classification facts we want to record are all protected:

`alexGClassifyTouch` · `alexGEvaluateBreakRetest` · `alexGEvaluateRepeatedReaction` ·
`alexGCreateSetupRecord` · `alexGConstructTrade` · `alexGWalkOutcome` · `alexGComputeMAEMFE` ·
`alexGRunSetupReplay` · `alexGComputeReplayStats` · `alexGRunSetupEngine` · `alexGRunZoneEngine` ·
`alexGProcessTimeframeCandle(WithSetups)`. Constants: `RULES_ALEXG`, `RULES`, `WEIGHTS`,
`ALERT_THRESHOLD`.

Every correction below must therefore be built in **non-protected** territory: `runAlexGReplay`
(`index.html:4004`), `runAlexGReplayUI` (`:4064`), and the whole evidence layer (`:11551-12600`).
Anything that genuinely requires new computation *inside* a protected function is out of scope for a
schema correction and would need a new `ruleVersion` under separate authorization.

**C-2 — Canonicalization is frozen. `evidenceCanonicalize` (`:11620`) must not change.**
Existing packages' `contentHash` values verify against the current canonical form. Altering key
ordering, `undefined`→`null` handling, array-order significance or the excluded-field list would
silently invalidate all 24 verified packages. **Adding fields to new packages is safe; changing how any
package is canonicalized is not.**

**The good news, established by inspection:** most of the missing evidence is *already computed and
already stored somewhere* — it is dropped in transit by non-protected code. Those items are cheap.

---

## 1. Defect register and corrections

| ID | Defect | Root location | Best achievable provenance | Protected code needed? |
|---|---|---|---|---|
| CORR-1 | No `ruleIds` / `triggeredConditions` on qualified setups (0/24) | schema gap | `DERIVED_FROM_OBSERVED_FIELDS` | No (mirror + differential tests) |
| CORR-2 | Specification version and running release collapsed into one field | `evidenceBuildPackageFromTrade` `:11930-11948` | `OBSERVED` | No |
| CORR-3 | `outcomes[].realizedR` null in 24/24; value hidden in `recordedResultR` | `evidenceBuildPackageFromTrade` | `OBSERVED_FROM_EXIT` | No |
| CORR-4 | `breakCandleRef` / `retestCandleRef` / `penetrationDepth` = `FUTURE_WORK` in 24/24 | capture seam drops available fields | `OBSERVED` (break/retest), `FUTURE_WORK` (penetration depth) | No |
| CORR-5 | `objects.decisions` empty in 24/24 | decisions are memory-only; replay emits none | `DERIVED` at boundaries only | **Yes** for true in-engine capture |
| CORR-6 | `objects.marketContexts` empty in 24/24 | candles never handed to capture | `OBSERVED` | No |
| CORR-7 | `timeToMFE` / `timeToMAE` null in 24/24 | `alexGComputeMAEMFE` returns extremes only | `DERIVED_BY_RECOMPUTATION` | No (recompute + agreement test) |
| CORR-8 | "Repeated Reaction" vs "Repeated Zone Reaction" used interchangeably | display/report strings | n/a | No |
| CORR-9 | No run is independently reproducible: `datasetHash` fingerprints candles that are never stored | replay fetches, persists nothing | `OBSERVED` | No |

---

### CORR-1 — Immutable rule attribution (`ruleIds`, `triggeredConditions`)

**Target:** `objects.qualifiedSetups[].ruleAttribution`, always present.

```
ruleAttribution: {
  ruleSetId: "alex_g_sr_v1",
  ruleIds: ["ALEX_SR_B_BREAK_RETEST"],            // canonical, registry-backed
  triggeredConditions: [
    {conditionId:"B_TOUCH_INDEX_GE_3",  satisfied:true, observed:{zoneTouchNumber:4}},
    {conditionId:"B_ZONE_STATUS_BROKEN",satisfied:true, observed:{zoneStatusAtQualification:"broken"}},
    {conditionId:"B_RETEST_AFTER_BREAK",satisfied:true, observed:{barsSinceBreak:14, max:50}},
    {conditionId:"B_SWING_SIDE_MATCH",  satisfied:true, observed:{swingType:"high", fromSide:"below"}},
    {conditionId:"B_FIRST_RETEST_IN_CYCLE", satisfied:true, observed:{breakCycleId:"AGB|…"}}
  ],
  precedenceApplied: "BREAK_RETEST_EVALUATED_BEFORE_RZR",
  rzrEvaluated: true,          // false when B&R qualified first — the one-directional ambiguity
  provenance: "DERIVED_FROM_OBSERVED_FIELDS"
}
```

**Why DERIVED and not OBSERVED:** the protected evaluators return only `{qualifies, breakCycleId,
barsSinceBreak}`. They do not emit which condition decided the outcome, and C-1 forbids making them.
The conditions are, however, fully decidable from fields the setup record already stores
(`zoneStatusAtQualification`, `zoneTouchNumber`, `zoneQualityAtQualification`, `brokenDirection`,
`reactionSwingType`, `reactionFromSide`, `barsSinceBreak`, `breakCycleId`) plus `configSnapshot`.

**Honesty requirement:** the field is labelled `DERIVED_FROM_OBSERVED_FIELDS`, never `OBSERVED`. A
derivation that agrees with the engine is still a derivation.

**New non-protected code:** `alexGRuleAttributionMirror(setupRecord, cfg)` — a pure function mirroring
`alexGEvaluateBreakRetest` / `alexGEvaluateRepeatedReaction` condition-for-condition, plus a rule
registry `RULES_ALEXG_ATTRIBUTION` (new constant, **not** added to the protected set).

**Mandatory differential test:** for every synthetic case in the existing Phase-3 fixtures plus
generated boundary cases, `alexGRuleAttributionMirror(...).qualifies` must equal the protected
evaluator's `qualifies`. Any disagreement fails the suite. Without this the mirror is a second opinion,
not attribution.

---

### CORR-2 — Split specification version from running release

**Target:** `identity`, always present.

| Field | Value for RUN-001-style replay | Source |
|---|---|---|
| `strategyId` | `alex_g_sr_v1` | unchanged |
| `strategySpecificationVersion` | `alex_g_sr_v1` | `alexGStrategyVersionReference().strategySpecificationVersion` |
| `releaseVersion` | `alex_g_sr_v1_1` | `ALEX_V11_RULE_VERSION` |
| `releaseGatesApplied` | `[]` for replay; `["ALEX_V11_001","ALEX_V11_006", …]` for live paper | which v1.1 gates the executing path actually consults |
| `strategyVersion` | `alex_g_sr_v1` | **kept** for backward compatibility |

`alexGStrategyVersionReference()` (`:2674`) already distinguishes these; the evidence builder collapses
them. `releaseGatesApplied` is the field that would have made this reconciliation a five-minute read
instead of a trace: it states plainly that replay ran under no v1.1 gate.

**Files:** `evidenceBuildPackageFromTrade` (`:11917-11960`), `evidenceValidatePackage` (`:12044`).

---

### CORR-3 — Serialize `realizedR` in the obvious field

`outcomes[].realizedR` is null in 24/24 with `realizedRProvenance: DERIVED_AT_READ_TIME`, while the
number lives in `recordedResultR`. Any consumer reading the obvious field gets nothing.

**Correction:** populate `realizedR` from the actual exit — `(exitPrice − entryPrice) / riskDistance`,
sign-adjusted for direction — with `realizedRProvenance: "OBSERVED_FROM_EXIT"`; fall back to
`recordedResultR` with provenance `RECORDED_BY_ENGINE` when the inputs are absent; null only when
neither exists. `recordedResultR` is retained unchanged so old and new packages stay comparable.
This is the evidence-layer expression of rule `ALEX_V11_002`.

**Files:** `evidenceBuildPackageFromTrade`; `evidenceNormalizeReplayTrade` (`:12212`) must forward
`riskDistance` (present on the trade record at `:3801`, currently dropped).

---

### CORR-4 — `breakCandleRef` and `retestCandleRef` (the cheapest high-value fix)

**These are not future work. The protected engine already records them and non-protected code throws
them away.** `alexGCreateSetupRecord` (`:3515`) stores `brokenAtBar` and `brokenAt` (break candle index
and timestamp) and `qualificationBarIndex` / `qualificationTimestamp` (the retest candle). But
`alexGConstructTrade` (protected, `:3736`) does not copy `brokenAtBar`/`brokenAt` onto the trade, and
the capture seam receives **only trades**:

```js
// index.html:4095 — current
evidenceCaptureReplayTrades(result.runIdentity, result.trades);
```

**Correction:** widen the seam to pass the setup records alongside the trades — both are already in
scope in `runAlexGReplay` (non-protected) — and record:

```
structureRefs.breakCandleRef  = {barIndex: brokenAtBar, timestampUTC: brokenAt, timeframe}   // OBSERVED
structureRefs.retestCandleRef = {barIndex: qualificationBarIndex, timestampUTC: qualificationTimestamp} // OBSERVED
```

RZR setups keep both null with reason `NOT_APPLICABLE` (no break cycle), never `FUTURE_WORK`.
`penetrationDepth` stays honestly `FUTURE_WORK` — nothing computes it today.

**Files:** `runAlexGReplay` (`:4004`), `runAlexGReplayUI` (`:4064`), `evidenceCaptureReplayTrades`
(`:12254`), `evidenceNormalizeReplayTrade` (`:12212`), `evidenceBuildPackageFromTrade`. Zero protected
edits. The live-paper path needs the equivalent seam widening in its own capture call.

---

### CORR-5 — Decision-chain capture (Phase 2, partially blocked)

Replay emits **no** decision events: `emitDecisionEvent` calls sit in `alexGEvaluatePairForLiveSetups`
(live path), and `decisionEventLog` is memory-only with a 500-event cap. Capturing a *faithful* replay
decision chain means emitting from inside the protected classification/replay functions — blocked by
C-1.

**Two honest options, to be decided before implementation:**

- **5a (in scope, partial):** a non-protected boundary shim in `runAlexGReplay` that records, per
  setup, the inputs handed to and the outputs returned by each protected call
  (`alexGRunSetupEngine` → `alexGRunSetupReplay` → `alexGConstructTrade` → `alexGWalkOutcome`).
  Chain fidelity is boundary-level, not step-level. Provenance `DERIVED_AT_BOUNDARY`; the
  completeness report must keep naming step-level decisions a gap.
- **5b (out of scope here):** emit decision events inside the protected functions. Requires a new
  `ruleVersion` and separate authorization. Not proposed.

**Recommendation:** implement 5a, and do not describe it as a decision chain — call it a
`boundaryTrace`, so nobody later mistakes it for step-level capture.

---

### CORR-6 — Market-context capture (Phase 3)

`objects.marketContexts` is empty in 24/24. `runAlexGReplay` holds all four datasets and is
non-protected, so a **bounded** window is capturable as `OBSERVED`: N candles before entry through
exit, per timeframe, N configurable (default 50 pre-entry).

Size check with RUN-001 as the yardstick: 24 trades × ~100 candles × 4 fields ≈ well under 1 MB total —
immaterial against the 3,043-candle dataset. Storage-quota classification already exists
(`evidenceClassifyStorageError`), and this is the largest single growth item in the plan, so the cap
must be explicit and logged when it truncates.

---

### CORR-7 — Excursion timing for loss forensics

`alexGComputeMAEMFE` (protected) returns extremes without timing. Non-protected correction: recompute
the excursion path over the same candle window in the evidence layer and record `timeToMFE` /
`timeToMAE` (bars and minutes) with provenance `DERIVED_BY_RECOMPUTATION`.

**Mandatory agreement test:** the recomputation's MAE/MFE **extremes** must equal the protected
function's `maePips`/`mfePips` for every fixture. If the extremes disagree, the timing is not describing
the same path and must not be written.

Answers the exact questions the July forensics document could not: how long the EUR/USD 14 Jul trade
sat at 0.0 MFE before stopping out, and whether the GBP/USD 0.949R excursion was early or late.

---

### CORR-8 — Canonical naming

One category, one name. **Canonical:** "Repeated Zone Reaction" · **abbreviation:** RZR ·
**internal id:** `A_repeatedReaction` (unchanged — written by protected code) · **display label:**
`REPEATED ZONE REACTION` (unchanged, `:3525`). "Repeated Reaction" is deprecated.

**Correction is presentation-only:** a single non-protected `alexGSetupTypeCanonicalName(setupType)`
used by every report, dashboard and stats key; `alexGComputeReplayStats` is protected and its
`bySetupType` keys stay as they are — the mapping happens at render time. Add both names to
`docs/trader-intelligence/GLOSSARY.md` with the alias marked deprecated.

---

### CORR-9 — Independent reproduction

Today `datasetHash` proves two runs used the same candles but **no one can obtain those candles** —
`fetchCandlesRange` persists nothing. A third party cannot reproduce RUN-001 at all.

**Correction:** an operator-invoked **dataset export artifact** — the four timeframes' candles as
written, hashed with the *same* function that produced `datasetHash`, exported next to the packages as
`mogo-dataset-<runId12>.json`, and re-import-verified exactly like a package. A run is then
reproducible from `{dataset artifact + commit + configHash + paramsHash}` with no broker access.

Keep it operator-invoked, not automatic: it is a disk write of market data and should be a deliberate act.

---

## 2. Exact impact surface

### Source (`index.html`) — all non-protected unless flagged

| Area | Lines | Change |
|---|---|---|
| `evidenceBuildPackageFromTrade` | 11917-12043 | CORR-2, CORR-3, CORR-4, CORR-7 fields |
| `evidenceValidatePackage` | 12044-12121 | accept + require the new always-present keys |
| `evidenceNormalizeReplayTrade` | 12212-12252 | forward `riskDistance`, break/retest refs, setup linkage |
| `evidenceNormalizeJvmTrade` | 12290-12315 | keep key parity; JVM genuinely lacks these → explicit null |
| `evidenceCaptureReplayTrades(Async)` | 12254-12283 | accept setup records alongside trades |
| `runAlexGReplay` | 4004-4037 | return setups + bounded candle windows in the result |
| `runAlexGReplayUI` | 4064-4107 | widened capture call (seam stays fire-and-forget, own try/catch) |
| `alexGBuildReplayRunIdentity` | 12180-12209 | record dataset-artifact availability |
| **New:** `alexGRuleAttributionMirror`, `RULES_ALEXG_ATTRIBUTION`, `alexGSetupTypeCanonicalName`, `evidenceBuildBoundaryTrace`, `evidenceRecomputeExcursionTiming`, `evidenceExportDataset` | — | CORR-1, CORR-5a, CORR-7, CORR-8, CORR-9 |
| **Must not change** | — | `evidenceCanonicalize` (C-2) and all 63 protected functions / 4 protected constants (C-1) |

### Schema and storage

- **Schema version: keep `mogo.evidence-package.v1`.** All new keys are *always present* (null where
  inapplicable), following the v12.9.0 precedent that added `datasetHash`/`replayDateRange` additively.
  This preserves fixture R5's identical-key-set invariant for newly captured packages.
- ⚠️ **Compatibility landmine — verified in source.** `evidenceImportPackageObject` (`:12558`) rejects
  any package whose `packageSchemaVersion !== EVIDENCE_PACKAGE_SCHEMA_VERSION`, and any
  `mogo.evidence-package.*` string that differs is reported as `NEWER_SCHEMA_READ_ONLY`. **If the
  version string is ever bumped, the existing 24 packages stop importing — and re-import is the only
  mechanism that can verify them.** Any future bump MUST first add an accepted-older-versions list and
  correct older-vs-newer discrimination. This is a prerequisite, not a follow-up.
- **IndexedDB:** `EVIDENCE_DB_VERSION` 1 → 2 to add a `byRunId` index (run-level queries are currently
  a full scan). `onupgradeneeded` only creates the index; existing records are re-indexed by the
  browser. No record is rewritten. The unique `bySourceTradeId` index is untouched.
- **`localStorage`:** no new keys. If a dataset-artifact pointer is retained, register it in
  `docs/STORAGE_KEYS.md` first.

### Migrations

**None for existing packages. There is no migration path and there must not be one** — packages are
immutable; the backfill routine stays read-only and must continue to skip anything already captured.

### Documentation

`docs/MOGO-003-EVIDENCE-PLATFORM-ARCHITECTURE.md` (schema + provenance vocabulary) ·
`docs/MOGO-003-PHASE-1-SPECIFICATION.md` (completeness report gap list shrinks) ·
`docs/DECISION_EVENT_ARCHITECTURE.md` (CORR-5a boundary trace, and why it is not a decision chain) ·
`docs/STORAGE_KEYS.md` (only if keys are added) · `docs/trader-intelligence/GLOSSARY.md` (CORR-8) ·
`docs/TESTING.md` + `docs/RELEASE_NOTES.md` · a new ADR for "derived rule attribution is not observed
attribution".

---

## 3. Tests required

| Suite | Fixtures |
|---|---|
| **New** `tests/v131_rule_attribution_tests.js` | **Differential:** mirror vs protected `alexGEvaluateBreakRetest` / `alexGEvaluateRepeatedReaction` across all Phase-3 fixtures + boundary cases (`touchIndex` 2/3, `barsSinceBreak` at `maxBarsBetweenBreakAndRetest` ±1, `choppy` quality, already-used break cycle). Every `ruleId` emitted exists in the registry. `precedenceApplied` and `rzrEvaluated` correct in both orders. Provenance is `DERIVED_FROM_OBSERVED_FIELDS` and never `OBSERVED`. |
| `tests/v128_evidence_platform_tests.js` (extend) | CORR-2 version split incl. `releaseGatesApplied` empty for replay / populated for live; CORR-3 `realizedR` populated with correct provenance and `recordedResultR` unchanged; CORR-4 break/retest refs `OBSERVED` for B&R and `NOT_APPLICABLE` for RZR; identical key sets across REPLAY/LIVE_PAPER and ALEX/JVM (R5 extended); **canonicalization unchanged — recompute the hash of a stored fixture package and assert it still verifies**; CORR-7 timing present only when extremes agree; CORR-6 window bounded and truncation logged; CORR-9 dataset artifact hash equals `datasetHash`. |
| **New** compatibility fixtures | A v1 package **captured before these changes** still validates, still hash-verifies, and still re-imports as `EXPORT_VERIFIED_BY_REIMPORT` under the new engine. Use a copy of a RUN-001 package as the fixture. Plus: bumping the version string is proven to break import (a red test that documents the landmine). |
| `regression-baseline-tools.py` | Zero drift: 63 protected functions and 4 protected constants byte-identical, run before **and** after every edit. |
| `tests/run_all.sh` | Suite count 17 → 18; fixture total 815 → 815 + new. No suite may produce zero fixtures (existing guard). |

Browser-only, as always disclosed: `crypto.subtle` digests and the IndexedDB v2 upgrade cannot be
exercised by the offline JXA runner and must be verified live in the disposable profile.

---

## 4. Do these corrections require rewriting the existing 24 packages?

**No. Every correction is prospective, and the existing 24 stay valid, untouched and verifiable.**

1. Packages are immutable by construction: capture uses `add()` (never `put()`), keyed on `packageId`
   with a unique `sourceTradeId` index. Re-running RUN-001 with identical inputs yields the identical
   deterministic `runId` and is a no-op, not a duplicate or an overwrite.
2. `contentHash` verification is unaffected **provided C-2 holds** — canonicalization must not change.
   Old packages hash exactly as they did.
3. New keys appear only in newly captured packages. Old packages simply lack them, which is honest:
   they were captured by an engine that did not observe those facts. Nothing is back-filled, and no
   value is ever invented for a run that did not record it.
4. RUN-001 remains the authoritative ALEX sample after these corrections ship. Its evidentiary
   ceiling — partial rule attribution, partial loss forensics — is a property of that run and is
   already recorded in the register.

The only thing that could invalidate the 24 is a careless version bump (§2) or a change to
`evidenceCanonicalize`. Both are now written down as prohibitions.

---

## 5. Sequencing

| Unit | Contents | Protected code | Schema bump | Risk |
|---|---|---|---|---|
| **A** | CORR-2, CORR-3, CORR-4, CORR-8 | none | none | **Low** — evidence layer + one seam widening |
| B | CORR-1 (+ mirror registry and differential suite) | none | none | Medium — correctness of the mirror is the whole point |
| C | CORR-7, CORR-6 | none | none | Medium — payload growth, needs explicit caps |
| D | CORR-9 dataset artifact | none | none | Medium — new export/verify path |
| E | CORR-5a boundary trace | none | none | Medium |
| — | CORR-5b in-engine decisions | **yes** | — | **Not proposed.** New `ruleVersion` + separate authorization. |

**Unit A is the proposed first implementation unit.** It fixes three of the four defects that made this
reconciliation slow, touches no protected function, needs no schema-version bump and no migration, and
its largest component (CORR-4) is recovering data the engine *already computes* and current code
discards.

No strategy rule, threshold or classification change is proposed anywhere in this document. Nothing
here is contingent on RUN-001's results, and no result from 8 or 16 trades is treated as evidence about
either setup.

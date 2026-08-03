# MOGO-002.8B — ALEX Setup Isolation Audit

**Date:** 2026-07-30 · **HEAD:** `a332d04` · **Engine:** `APP_VERSION` 12.7.0 · **Strategy:** `alex_g_sr_v1_1`
**Scope:** Determine the smallest repository-supported change that suspends **new** Repeated Zone Reaction paper trades while Break & Retest continues.
**No production code modified. No implementation. No commit.**

---

## 0. Scope note on the reported sample

> ### ⚠️ ANNOTATION — 2026-08-03 · MOGO-003 forensic reconciliation
>
> **The figures in this section are UNVERIFIED TIER 1 LIVE-PAPER OBSERVATIONS. They came from a
> different sample than any verified replay, and MUST NOT be compared directly with verified
> replay runs.**
>
> | | This section's figures | Verified replay RUN-001 |
> |---|---|---|
> | Evidence mode | `LIVE_PAPER`, forward paper trading | `REPLAY`, `runId 3d7c3dc1af7f…` |
> | Instruments | multi-pair (incl. GBP/USD) | EUR_USD only |
> | Period | live trading up to 2026-07-30 | observed 2026-03-25 → 2026-08-03 |
> | Engine / release | 12.7.0 · v1.0 trades | 12.9.0 · `alex_g_sr_v1` executed |
> | Verifiable? | **No** — browser `localStorage` only, never persisted (stated in this section) | **Yes** — 24 Evidence Packages, SHA-256 content hashes, re-import verified on disk |
> | B&R | 6 trades, 5W/1L | 8 trades, 1W/7L, −5.00R |
> | RZR | 18 trades, 1W/17L | 16 trades, 5W/11L, −1.00R |
>
> **Why the two were mistaken for one sample:** both total 24 trades with 6 wins and 18 losses. That
> aggregate collision is coincidence. The matching −6R total is *not* an independent coincidence — with
> fixed 2R targets and −1R stops, any 24-trade sample with 6W/18L is exactly (6×2) − 18 = −6R, so the
> R agreement follows arithmetically from the win/loss coincidence. Note also that the "6" here is a
> *trade count* while the "6" in the replay is a *win count*.
>
> **Consequence for this audit's conclusion:** the operational decision recorded below (suspend RZR,
> keep B&R active) rested in part on the 5-of-6 B&R win rate above. In the one verified sample that
> now exists, B&R is the weaker of the two setups. **This does not reverse the suspension and no rule
> change is proposed** — 8 and 16 trades settle nothing, neither setup is validated, and RZR remains
> suspended from paper and live execution. It is recorded so the asymmetry is not carried forward as
> if it were evidence.
>
> Reconciliation record: `docs/MOGO-003-VERIFIED-REPLAY-RECORD.md` §RUN-001. Related open flag:
> `ALEX-BREAK-RETEST-LOSS-FORENSICS-2026-07.md` §1.2 (sample-count discrepancy) — **now resolved**:
> the two losing B&R paper trades and this section's 5W/1L belong to the same unverified live-paper
> record, and neither can be reconciled against replay evidence.

The 24 reported trades (B&R 6: 5W/1L; RZR 18: 1W/17L) **cannot be verified from the repository.** ALEX
paper trades persist only in browser `localStorage` (`fxhub_alexg_account`, `fxhub_alexg_journal`);
nothing writes them into the repo. This audit therefore **takes the observation as given** and does not
attempt to confirm, extend, or draw statistical conclusions from it.

Two facts that bound how the sample may be used:

1. **Under MOGO-003 §9 this is Tier 1 evidence** — an initial behavioural sample. It may justify an
   operational change; it may not support any expectancy claim about either setup type.
2. **The sample predates ALEX v1.1.** v1.1 released today and holds zero trades. These are `v1.0`
   trades, and v1.1's Monday–Wednesday gate did not apply to any of them.

The directive's framing is correct and is adopted here: this justifies an **engineering audit**, not a
conclusion about setup validity.

---

## TASK 1 — SETUP ARCHITECTURE

### 1.1 Where each setup exists

| | Break & Retest | Repeated Zone Reaction |
|---|---|---|
| **Internal identifier** | `'B_breakRetest'` | `'A_repeatedReaction'` |
| **Display label** | `'BREAK & RETEST'` | `'REPEATED ZONE REACTION'` |
| **Qualifier function** | `alexGEvaluateBreakRetest` — `index.html:3319` | `alexGEvaluateRepeatedReaction` — `index.html:3337` |
| **Protection status** | 🔒 **PROTECTED** | 🔒 **PROTECTED** |
| **Assigned at** | `alexGClassifyTouch` `index.html:3466-3467` | `alexGClassifyTouch` `index.html:3472-3473` |
| **Record creation** | `alexGCreateSetupRecord` (🔒 PROTECTED) | same |
| **Direction resolution** | `alexGDetermineTradeDirection` `index.html:3574` | `index.html:3569` |

### 1.2 How setup type is stored

**A plain JavaScript string field — not an enum, not a structured type, not a derived label.**

`alexGCreateSetupRecord` (`index.html:3431`) writes both a stable identifier and a display label:

```js
setupType,                                                    // 'A_repeatedReaction' | 'B_breakRetest'
setupLabel: setupType==='B_breakRetest' ? 'BREAK & RETEST' : 'REPEATED ZONE REACTION',
```

`setupType` is the **stable identity**; `setupLabel` is derived from it at creation and frozen onto the
record. Both propagate unchanged into the position object and the journal record.

**This is favourable for isolation:** filtering on `setupType` is an exact string comparison against a
value that is already stored on every setup, position and journal record.

### 1.3 Precedent — a third setup type already circulates safely

`generateTestAlexTrade` creates positions with `setupType:'DEV_TEST'` (`index.html:4826`). Downstream
consumers already handle an unrecognised value gracefully — `computeAlexExplanations`
(`index.html:2197`) has an explicit `else` branch. **Consumers do not assume exactly two setup types.**

### 1.4 Existing precedent — replay already filters on setup type

`alexGRunSetupReplay` (`index.html:3796`) already contains exactly this pattern:

```js
if(setup.setupType!=='A_repeatedReaction' && setup.setupType!=='B_breakRetest'){
  rejected.push({tradeId,setupId,pair,timeframe,reason:'UNSUPPORTED_SETUP_TYPE'});
  continue;
}
```

**A setup-type gate that records a rejection rather than silently skipping is an established pattern in
this codebase**, not a new idea.

### 1.5 ❌ Does setup-level enable/disable already exist?

**No.** Verified by exhaustive search:

| Searched | Result |
|---|---|
| `RULES_ALEXG.config` (20 keys) | **No setup-type key** |
| `RULES_ALEXG_V11.v11Config` | **No setup-type key** |
| `enabledSetupTypes` / `setupTypeEnabled` / `disableSetup` / `suspendSetup` | **Zero occurrences** |
| `ALEX_MANIFEST.capabilities` | Strategy-level only (`scanning`, `paperTrading`, `automation`…). **No setup granularity.** `settings:false` — config *"not exposed through Services this release"* (`index.html:5179`) |
| `STRATEGY_REGISTRY` (`index.html:13197`) | Maps strategy → manifest/services. **No sub-strategy concept** |
| UI controls | Toggle is all-or-nothing: `toggleAlexGLiveTrading()` enables/disables **the whole ALEX engine** |

**Finding: the only existing control is strategy-wide. Disabling RZR today would require disabling
Break & Retest too — which is precisely what the objective forbids.**

---

## TASK 2 — EXECUTION CONTROL

### 2.1 Option assessment

| Option | Viable? | Reason |
|---|---|---|
| **A. Configuration only** | ❌ **No** | No configuration key exists, and none can be *read* into effect without a code change. Adding a key to `RULES_ALEXG` is impossible — it is a **protected constant**. Adding one to `RULES_ALEXG_V11` is possible, but nothing reads it, so a code change is still required |
| **B. Existing execution gate** | ❌ **No** | No setup-type gate exists in the live path. The live gates are activation cutoff, staleness, entry-day (v1.1), duplicate, direction, overlap, ATR, bid/ask, entry-delay, stop validity, pip value, size. **None discriminates by setup type** |
| **C. Minimal code change** | ✅ **YES** | One gate in a **non-protected** function, mirroring the v1.1 entry-day gate exactly |
| **D. Major redesign** | ❌ Unnecessary | Nothing in the architecture resists per-setup control |

### 2.2 Recommended — smallest safe option

> ### ✅ **C — MINIMAL CODE CHANGE**
>
> **One gate in `alexGEvaluatePairForLiveSetups` (NOT protected), placed immediately after the v1.1
> entry-day gate and before `alexGAttemptOpenLivePosition`.**

**Why this exact location:**

1. **`alexGEvaluatePairForLiveSetups` is not protected** — verified against `regression-baseline.json`. Every alternative site is protected:

   | Candidate site | Status |
   |---|---|
   | `alexGEvaluateRepeatedReaction` (stop qualifying) | 🔒 PROTECTED |
   | `alexGClassifyTouch` (stop classifying) | 🔒 PROTECTED |
   | `alexGCreateSetupRecord` (stop recording) | 🔒 PROTECTED |
   | `alexGConstructLivePosition` (block at construction) | 🔒 PROTECTED |
   | `alexGRunSetupEngine` | 🔒 PROTECTED |
   | **`alexGEvaluatePairForLiveSetups`** | ✅ **NOT protected** |

2. **The pattern is already proven twice in this same function** — the activation-cutoff and staleness gates, and the v1.1 entry-day gate added yesterday, all follow the identical shape: evaluate → emit `RULE_EVALUATED` → on fail, record a permanent status via `alexGRecordLiveSetupStatus` + emit linked `CANDIDATE_REJECTED` → `continue`.

3. **Setups still qualify and are still recorded.** The zone/setup engine is untouched, so RZR setups continue to be detected, classified, stored in `alexGSetupState`, and persisted to `fxhub_alexg_setups`. **Only the trade-open step is suppressed.** This preserves the research record completely — the exact opposite of removing the setup type.

4. **Reversible by one boolean.** Suspension should be config-gated in `RULES_ALEXG_V11.v11Config`, so re-enabling requires no code change.

### 2.3 What must NOT be done

| Approach | Why rejected |
|---|---|
| Edit `alexGEvaluateRepeatedReaction` to stop qualifying | Protected → baseline drift; **and destroys the research record** — the setups would never exist |
| Remove `A_repeatedReaction` from `alexGClassifyTouch` | Protected; same research loss |
| Delete historical RZR trades | Violates data preservation; corrupts balance history |
| Disable ALEX entirely | Stops Break & Retest, which the objective requires to continue |
| Change entry/exit/stop/target logic | Explicitly prohibited by this directive |

---

## TASK 3 — DATA PRESERVATION

**Verified: no historical migration is required. Nothing is rewritten.**

| Asset | Preserved? | Evidence |
|---|---|---|
| **Completed trades** | ✅ | `alexGAccount.closedPositions` is never touched by an entry gate. The gate runs *before* `alexGAttemptOpenLivePosition` and only skips new opens |
| **Open trades** | ✅ | Exit monitoring is `alexGCheckLivePositions` → `alexGCloseLivePosition`, a **completely separate path** that runs first each tick (`index.html:4680`) and never consults `setupType`. **An open RZR position continues to be managed and closed normally** |
| **Journal** | ✅ | `alexGJournalEntries` is append/update-by-`tradeId`. No new record is created for a suppressed setup; no existing record changes |
| **Analytics** | ✅ | Dashboard stats recompute from `closedPositions` on render. Historical RZR trades continue to contribute exactly as before. `bySetupType` breakdown (`index.html:3874`) keeps working |
| **Replay compatibility** | ✅ | Replay is a separate path — see Task 4 |
| **Strategy versions** | ✅ | `RULES_ALEXG` untouched. If gated via `RULES_ALEXG_V11.v11Config`, this is a **v1.1-scoped operational control**, not a rule change |
| **Setup records** | ✅ | RZR setups continue to be created and persisted to `fxhub_alexg_setups`. **Research value fully retained** |

### 3.1 Two behaviours worth confirming explicitly

**Open RZR positions are unaffected.** The exit path never reads `setupType`. A position opened before
suspension runs to its stop or target normally. **No orphaned position is created.**

**The Trade Inspector and explanations continue to work** for historical RZR trades —
`computeAlexExplanations` reads `pos.setupType` from the frozen record, which still says
`'A_repeatedReaction'`.

### 3.2 ⚠️ One version-semantics decision for the Authority

If the gate is added to `RULES_ALEXG_V11.v11Config`, then **`alex_g_sr_v1_1` means something different
before and after the change.**

Under MOGO-003 §13, *filter logic* change ⇒ new strategy version. Two defensible readings:

| Reading | Implication |
|---|---|
| **Operational suspension** (recommended) | A reversible execution control, not a rule change. `alex_g_sr_v1_1` unchanged. Justified because the *rule set* is identical — only which setups are permitted to execute changes |
| **Rule change** | Requires `alex_g_sr_v1_2` |

**Recommendation: treat as operational suspension**, and record the suspension window (start/end
timestamps) so any future analysis can partition trades by whether RZR was permitted. **Without that
record, a future reader cannot tell a period with zero RZR trades from a period where RZR was
suppressed.** This is the single most important non-obvious requirement in this audit.

**ENGINEERING AUTHORITY DECISION REQUIRED.**

---

## TASK 4 — REPLAY IMPACT

### 4.1 Direct impact: none

| Aspect | Impact | Reason |
|---|---|---|
| **Replay determinism** | ✅ **None** | `alexGRunSetupReplay` is 🔒 PROTECTED and unmodified. The proposed gate lives in the **live** path only |
| **Replay readiness** | ✅ **None** | MOGO-003 §3 found ALEX **NOT READY** for 4 unrelated reasons (B1 resistance-role defect, B2 no date range, B3 no run ID, B4 no persistence). This change neither helps nor harms any of them |
| **Replay metrics** | ✅ **None** | `alexGComputeReplayStats` unchanged, including the `bySetupType` breakdown |
| **Version history** | ✅ **None** | `RULES_ALEXG` byte-identical; protected drift check stays clean |
| **Future validation** | ✅ **Improved** | Replay continues generating **both** setup types, so the RZR question stays answerable with a proper sample |

### 4.2 ⭐ Replay must NOT be suspended

The objective says *"stop opening NEW paper trades"* — that is **forward paper trading only**.

**Replay is research, not execution.** Suspending RZR in replay would destroy the only mechanism
capable of producing a sample large enough to actually evaluate it. The 18-trade observation is Tier 1;
answering it needs Tier 2+ (≥100 decided trades), and replay is the only route there.

**Recommendation: suspend RZR in live paper trading; leave replay generating both setup types.**

### 4.3 Why replay must record rejected candidates rather than silently skip

This is the crux of the question, and it applies to the **live gate** as well.

**If a suppressed setup leaves no record, the following become impossible:**

1. **Counting the suppression.** A period with zero RZR trades is indistinguishable from a period where
   RZR was suppressed. Any future comparison of the two periods is invalid.
2. **Measuring the counterfactual.** "How many RZR setups did we decline, and what would they have
   done?" is the *only* question that can retire this decision. A silent skip erases the numerator.
3. **Reproducing a run.** MOGO-003 §5 requires that number of decisions, number of candidates and
   rejection reasons all match between reruns. A silently skipped candidate breaks the candidate count.
4. **Auditing the gate itself.** Without a rejection record there is no evidence the gate fired at all —
   only an absence, which is equally consistent with the gate being broken.
5. **Attributing filter cost.** MOGO-003 §7 requires every rule to be attributable a filtering cost.
   Silent skips make that permanently unrecoverable.

**Therefore the gate must record a permanent status entry and emit a linked decision-event pair**,
exactly as the activation, staleness and entry-day gates already do. **A `continue` without a record is
not acceptable.**

### 4.4 A structural limitation this does not fix

`alexGEvaluateBreakRetest` and `alexGEvaluateRepeatedReaction` return `{qualifies:false}` and **discard
which condition failed** (MOGO-002.5 `TRACE-LIM-001`). Both are protected. This audit's gate operates on
*already-qualified* setups, so it is unaffected — but rule-level rejection detail for RZR qualification
remains unreachable without a protected-function edit. **Not in scope here.**

---

## TASK 5 — IMPLEMENTATION PLAN

**Specification only. Nothing implemented.**

### 5.1 Files requiring modification

| File | Change |
|---|---|
| `index.html` | Config key + one gate + (optional) suspension-window record |
| `tests/v127_alex_v11_release_tests.js` *or* a new `tests/v128_*_tests.js` | Fixtures |
| `tests/run_v128_*_tests.js` | Runner, if a new suite |
| `regression-baseline-tools.py` | `FIXTURE_COUNTS` entry, if a new suite |
| `docs/RELEASE_NOTES.md` + `APP_VERSION_LOG` | Required for a behaviour-changing release |

### 5.2 Functions requiring modification

| Function | Protected? | Change |
|---|---|---|
| **`alexGEvaluatePairForLiveSetups`** | ✅ **Not protected** | **Insert one gate** after the entry-day gate, before `alexGAttemptOpenLivePosition` |
| `RULES_ALEXG_V11` (constant) | ✅ Not protected | Add `suspendedSetupTypes: ['A_repeatedReaction']` + `setupSuspensionEnabled` + a suspension-window record |
| *(new pure helper)* `alexGV11SetupTypePermitted(setupType, v11)` | n/a | Mirrors `alexGV11EntryDayEligible`; **fails open** |

**Zero protected functions modified. Zero constants modified. Expected drift: none.**

### 5.3 Estimated lines changed

| Area | Lines |
|---|---|
| Config keys + suspension-window record | ~10 |
| Pure helper | ~8 |
| Gate (mirrors entry-day gate incl. status + 2 decision events) | ~22 |
| Rule-registry entry | ~2 |
| `APP_VERSION` bump | 1 |
| **`index.html` total** | **~43 lines added, 0 removed** |
| Test fixtures (~14) | ~90 |
| Docs | ~30 |

### 5.4 Regression tests required

**New fixtures (~14):**

1. RZR setup → suppressed, status `IGNORED — SETUP TYPE SUSPENDED`
2. B&R setup → **still opens normally** *(the critical fixture)*
3. `DEV_TEST` unaffected
4. Suspension disabled → RZR opens again (reversibility)
5. Fails open on an unrecognised setup type
6. Fails open on empty/missing suspension list
7. Rejection record is created — **never a silent skip**
8. `RULE_EVALUATED` emitted with correct rule id and reason code
9. `CANDIDATE_REJECTED` linked via `parentEventId`
10. Status is permanent — not reconsidered on a later poll
11. An **open** RZR position still closes normally
12. Historical RZR trades still counted in dashboard stats
13. RZR setups still created and persisted to `alexGSetupState`
14. Suspension window recorded with a start timestamp

**Existing suites that must stay green:** all 14 (**656 fixtures**), plus zero protected drift.

⚠️ **Note the v126 precedent:** the v1.1 entry-day gate broke 9 pre-existing fixtures because they open
trades end-to-end. Those fixtures use `A_repeatedReaction` setups. **A setup-type gate will break them
again** unless the suspension defaults OFF in test context or the fixtures pin the config. **This must
be planned for, not discovered.**

---

## TASK 6 — FINAL CLASSIFICATION

# ✅ MINIMAL CODE CHANGE REQUIRED

**Basis:** no setup-level enable/disable exists (Task 1.5); no existing execution gate discriminates by
setup type (Task 2.1); the change is ~43 additive lines in one non-protected function, mirroring a
pattern already used three times in that same function; zero protected functions or constants are
touched; and it is fully reversible by a single boolean.

---

## Summary of recommendations

1. **Gate in `alexGEvaluatePairForLiveSetups`**, config-driven, fail-open, reversible.
2. **Record every suppression** — permanent status + linked decision events. Never a silent skip.
3. **Do not suspend replay.** Both setup types must keep generating research evidence.
4. **Record the suspension window** so future analysis can partition periods correctly.
5. **Treat as operational suspension, not a rule change** — Authority decision required.
6. **Plan for the v126 fixture interaction** before implementing.

---

*MOGO-002.8B audit complete. No production code modified; no implementation; no commit.*

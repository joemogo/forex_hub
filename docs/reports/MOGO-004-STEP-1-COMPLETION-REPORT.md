# MOGO-004 — Step 1 Completion Report

**Prepared:** 2026-08-04 · **Repository HEAD:** `bb8498f` · **Prepared against:** working tree, no modifications made
**Scope:** verification of the evidence at `~/Desktop/MOGO-Evidence/`, the PRE-REG-001 gate fields, and the Step 1 pilot gate.
**Code changed:** none. **Campaign C1:** not started. **Temporary copy:** not used — every check ran against the original directories.

---

## 0. Verdict, stated first

> ## ⛔ STEP 1 IS NOT COMPLETE. THE PILOT HAS NOT BEEN RUN.
>
> The evidence in `~/Desktop/MOGO-Evidence/` is **RUN-001** — the pre-existing MOGO-003 baseline,
> captured on engine **12.9.0** on **2026-08-03**, *one day before* PRE-REG-001 was declared. It is
> not the Step 1 pilot and cannot be substituted for it.
>
> **The Step 1 gate is evaluated below and it FAILS: 0/24 on all three required fields.** That failure
> is not a defect in the evidence — RUN-001 was never capable of passing, because it predates all five
> engine units that produce those fields. It is the correct and expected result of applying the gate to
> the wrong artifact.
>
> **Campaign C1 must not run.** Not because the pilot failed, but because the pilot has not yet happened.

**What *is* complete:** a full independent verification of RUN-001. That work is sound, and every claim
in `MOGO-003-VERIFIED-REPLAY-RECORD.md` reproduced exactly. It establishes the baseline. It does not
discharge Step 1.

---

## 1. Two premises in the tasking that did not survive contact with the directory

Both are corrected here rather than worked around.

| Premise as given | What is actually on disk |
|---|---|
| "27 evidence package files" | **24** evidence packages + **4** `RUN-HARVEST-*.json` files = **28** files total |
| "The rejection record is also present" | **No rejection record file exists.** Only aggregate counts, spread across three harvest files |

**On the count of 24.** This is not a matter of interpretation. Three independent sources agree:
`RUN-HARVEST-harvest_final.json` reports `packages.total: 24`; `MOGO-004-PLAN.md` §0 states "24 Evidence
Packages"; `MOGO-003-VERIFIED-REPLAY-RECORD.md` states "24 packages, one per resolved trade"; and I
counted 24 files and verified 24 distinct `packageId`s. **Nothing is missing** — 24 is the correct and
expected number, one per resolved trade. The figure 27 does not correspond to any quantity in this run.

**On the rejection record.** See §6. This one is a genuine gap, not a miscount.

---

## 2. Repository access — verified

| Check | Result |
|---|---|
| Working directory | `/Users/joemogollon/Desktop/Forex Hub` — accessible |
| Git repository | yes · branch `main` · HEAD `bb8498f` |
| Working tree | clean but for one untracked file: `docs/reports/MOGO-RESEARCH-ACQUISITION-ARCHITECTURE.md` |
| Evidence directory | `/Users/joemogollon/Desktop/MOGO-Evidence/alex_g_sr_v1-EUR_USD-90d-3d7c3dc1af7f` — accessible, 28 files |
| Modifications made | **none** — all checks read-only; verifier written to the session scratchpad, not the repository |

---

## 3. The actual runId — determined, then independently recomputed

```
runId  3d7c3dc1af7fea769af06fda26f08da73a4c605d931bbde0947021f3aa5ab806
```

Present and **identical in all 24 packages** (`identity.runId`), in `RUN-HARVEST-harvest_final.json`,
and in the register in `MOGO-003-VERIFIED-REPLAY-RECORD.md`. The directory name and the
`REPLAY|3d7c3dc1af7f|…` trade-ID namespace carry its first 12 characters.

I did not take the stored value on trust. I re-derived the identity chain from the packages' own
contents, using a clean-room port of `alexGBuildReplayRunIdentity` (`index.html:13560`) and
`mogo.evidence-canon.v1` (`index.html:12159`, rules K1–K8):

| Value | Recomputed from | Result |
|---|---|---|
| `configHash` | the package's own `configSnapshot` block | ✅ **MATCH** `dbbb29b6…62c5adb` |
| `paramsHash` | the replay params at `index.html:4104`, `ambiguousMode: conservative` | ✅ **MATCH** `8fe841e6…21c6cae5` |
| `runId` | `strategyId` + `pair` + observed window + the three hashes | ✅ **MATCH** `3d7c3dc1…aa5ab806` |
| `datasetHash` | — | ⚠️ **cannot be recomputed** — see below |

The `paramsHash` match is worth naming separately: it independently confirms the **declared replay
parameters** were the ones actually used. Spread `none`, fixed spread 0, slippage 0, start balance
10,000, `ambiguousMode: conservative`. Had any of those five differed, the hash would not have
reproduced.

**Disclosed limitation.** `datasetHash` is a SHA-256 over every OHLC value in all four timeframes
(`evidenceReplayDatasetHash`, `index.html:13541`). The candles themselves are not retained anywhere in
the repository or the evidence directory, so this hash **cannot be independently recomputed** — it can
only be confirmed identical across all 24 packages and the harvest, which it is. This is the
content-addressed candle store gap, still open. It means the dataset is *fingerprinted* but not
*reproducible*: I can prove all 24 packages came from one dataset; I cannot prove which dataset.

---

## 4. Canonical content and hashes — 24/24 verified

I reimplemented `evidenceCanonicalize` and the SHA-256 step from the specification in `index.html`
(K1/K2 field exclusion, K3 key sort, K4 array-order significance, K5 null coercion, K6 non-finite
rejection, K7 UTF-8, K8 no whitespace) and ran it against the file bytes.

**Result: 24 PASS, 0 FAIL.** Every stored `contentHash` reproduces from its own canonical content.

| Invariant | Result |
|---|---|
| Distinct `packageId` | 24 / 24 — no duplicates |
| Distinct `contentHash` | 24 / 24 — no duplicates, no collisions |
| Distinct `runId` | 1 — all packages belong to one run |
| `engineVersion` | `12.9.0` on all 24 |
| `mode` | `REPLAY` on all 24 |
| `packageSchemaVersion` | `mogo.evidence-package.v1` on all 24 |
| `captureBasis` / `configSnapshotProvenance` | `REPLAY_RUN` / `OBSERVED` on all 24 |
| `strategyVersion` | `alex_g_sr_v1` on all 24 · `alex_g_sr_v1_1` appears in **0** of 24 |
| Filename hash-12 prefix vs `contentHash` | 24 / 24 consistent, 0 mismatches |
| `completenessReport.level` | `PARTIAL` on all 24 — none overclaims |
| `dataQualityFlags` | empty on all 24 |
| `export.exportedAt` | `null` on all 24 — **expected**, and explained below |

**On `exportedAt: null`.** This is by design, not a fault. The `export` block is one of the six fields
excluded from the hash (`EVIDENCE_HASH_EXCLUDED_FIELDS`), and the stamp is written to the stored record
*after* the file bytes are produced — so exported files necessarily carry `null`. The verification
outcome lives in `RUN-HARVEST-harvest_final.json` (`VERIFIED_ON_DISK: 24`). Consistent with the note
already recorded in the replay record.

### Statistics recomputed from the packages alone

Computed from the 24 package files, ignoring every published figure, then compared:

| Figure | Recomputed | Record | |
|---|---|---|---|
| RZR (`A_repeatedReaction`) | 16 trades · 5W/11L · −1.00R · 31.25% · −0.0625R | identical | ✅ |
| Break & Retest (`B_breakRetest`) | 8 trades · 1W/7L · −5.00R · 12.50% · −0.6250R | identical | ✅ |
| Overall | 24 · 6W/18L · −6.00R · 25.00% · −0.25R · PF 0.6667 | identical | ✅ |
| Direction split | buy 11 / sell 13 | identical | ✅ |
| avg MAE / MFE pips | RZR 40.41/31.45 · B&R 44.86/29.55 | identical | ✅ |
| Unresolved · ambiguous | 0 · 0 | identical | ✅ |

**Every published RUN-001 figure reproduces exactly.** The evidence chain is intact and the record is
accurate.

One provenance note that matters for later adjudication: `realizedRProvenance` is
`DERIVED_AT_READ_TIME` on **all 24** outcomes. The R values are computed on read, not stored as
observations. They are deterministic and reproducible, but they are derivations.

---

## 5. PRE-REG-001 gate fields — checked

### 5.1 The document itself is properly anchored

| Property | Check | Result |
|---|---|---|
| Content fixed | SHA-256 of the file vs the hash recorded in its own commit message | ✅ `16e29f64…92836da1` — **match** |
| Unmodified since | `git diff f83a9b1..HEAD` on the file | ✅ **empty** — never edited |
| Time fixed | commit `f83a9b1`, 2026-08-04T07:57:30-04:00, parent `25c6c52` | ✅ anchored |
| Precedence provable | 3 commits since, all documentation/isolation work | ✅ **no observation commit exists yet** |
| Declaration HEAD `f8004fe` | exists, and is an ancestor of `f83a9b1` | ✅ consistent |

Immutability holds. The falsifiable anchor is real, and precedence over the campaign's first
observation is currently trivial to demonstrate — because there is no observation.

### 5.2 The declared family of 12 reproduces exactly

Reconstructed independently from `hypothesis-registry.json` at `f8004fe`:

- 41 hypotheses total · **12 `COLLECTING`** · 19 `UNSUPPORTED` · 10 `UNRESOLVED` — matches §2 exactly.
- The 12 IDs match the §2 table exactly, in order: AXR-001, 002, 003, 004, 005, 007, 030, 041, 043, 051, 071, 090.
- Setup scopes match: AXR-003/004 → `B_breakRetest` (8 observed), AXR-005 → `A_repeatedReaction` (16), the rest `ALL_SETUPS` (24).
- Observed counts and shortfalls-to-30 match the §2 table row for row.
- The registry is **unchanged** between `f8004fe` and HEAD — no drift since declaration.

### 5.3 Gate fields present on all 12

| Field | Status |
|---|---|
| `measurableOutcome.primaryMetricId` | ✅ `MET_EXPECTANCY_R` on all 12 |
| Secondary metrics | ✅ win rate, net R, MAE pips, MFE pips |
| `comparisonGroup` (armA / armB / basis) | ✅ present on all 12, wording matches §3 |
| `minimumOperationalSample` | ✅ **30** on all 12 |
| `recommendedStatisticalSample` | ✅ **100** on all 12 |
| `promotionThreshold` | ✅ ≥ 0.25R with interval excluding zero |
| `rejectionThreshold` | ✅ < 0.25R or favours armB, both arms ≥ 30 |
| `promotionCeiling` | ✅ **`REPLAY_EVIDENCE_ONLY`** on all 12 |
| `evidenceRunIds` | ✅ all 12 → `[3d7c3dc1…aa5ab806]`, the verified runId |
| `joinStatus` | ✅ `LINKED` on all 12 |

**MOGO-004 Gap 2 is closed for this family.** These twelve are genuinely executable — they carry a named
metric, a comparison, a threshold, a minimum sample and an evidence join. The placeholder-test problem
described in `MOGO-004-PLAN.md` §3 no longer applies to them.

**One minor finding.** No field is named `falsificationCondition`. Objective G5 calls for one explicitly.
`rejectionThreshold` performs exactly that role and is well-formed, so this is a naming gap, not a
substantive one. Recording it rather than silently treating the two as synonymous.

---

## 6. Censoring and the rejection record — a real gap

PRE-REG-001 §9 is unambiguous: *"the full contents of the `alexGReplayRejected` global … are saved
alongside that run's packages, per setup, with reason,"* and *"a result computed on a censored sample
that does not report the censoring is not a result."*

**What exists** — aggregates only, in three places, mutually consistent:

| Source | Content |
|---|---|
| `RUN-HARVEST-harvest1.json` | `rejectedCount: 15` · `rejectionReasons: {EXISTING_OPEN_TRADE_SAME_PAIR_TIMEFRAME: 15}` |
| `RUN-HARVEST-last.json` | `rejectedByType: {A_repeatedReaction: 10, B_breakRetest: 5}` · `rejectedKeys: [tradeId, setupId, pair, timeframe, reason]` |
| `RUN-HARVEST-harvest_final.json` | `rejectedDetail: {"? / EXISTING_OPEN_TRADE_SAME_PAIR_TIMEFRAME": 15}` |

**What does not exist:** the 15 individual rejection records. `rejectedKeys` names the five fields each
record *would* carry — it is the schema, not the data. No file contains the per-setup rows.

**Arithmetic confirms the census is complete:** 24 traded + 15 suppressed = 39 qualified. **Suppression
rate 38.46%.** Consistent across every source.

**Assessment.** RUN-001 predates PRE-REG-001, so §9 does not bind it retroactively — this is not a
compliance breach. But the practical consequence stands and is worth stating plainly: the individual
suppressed setups are **not recoverable from this evidence directory**. The censoring can be quantified
in aggregate; it cannot be analysed. Whether suppression correlates with market structure — the exact
concern §9 raises — is **not answerable from what is on disk**.

For the pilot and for C1 this is not optional. `alexGReplayRejected` (`index.html:4119`) must be saved
in full, per setup, with reason.

---

## 7. The Step 1 pilot gate — evaluated honestly

### 7.1 What the gate requires

`MOGO-004-ARCHITECTURE-REVIEW.md` §"Revised roadmap":

```
STEP 1 — PILOT RUN
  · RUN-001's window, current engine, isolated profile
  · Discharge the 10-item browser checklist
  · Save packages + alexGReplayRejected + harvest
  → GATE: do the packages actually carry triggeredConditions,
    timeToMFE/timeToMAE, and market context?
       NO  → stop. Fix capture. Campaign would waste 11 runs.
       YES → proceed.
```

PRE-REG-001 §6: *"The pilot proceeds to C1 **only if** the captured packages carry populated
`triggeredConditions`, `timeToMFE`/`timeToMAE`, and market context. **If they do not, C1 does not run.**"*

### 7.2 Measured against the 24 packages on disk

| Required field | Populated | Verdict |
|---|---|---|
| `triggeredConditions` | **0 / 24** — the string appears nowhere in any package | ❌ **FAIL** |
| `timeToMFE` | **0 / 24** — present as a key, `null` on every outcome | ❌ **FAIL** |
| `timeToMAE` | **0 / 24** — present as a key, `null` on every outcome | ❌ **FAIL** |
| `objects.marketContexts` | **0 / 24** — empty array on every package | ❌ **FAIL** |
| *(informational)* `exitPathCandleRefs` | 0 / 24 — empty on every outcome | — |

Corroborated by the packages' own self-reporting: all 24 declare `objects.marketContexts [FUTURE_WORK]`
and `outcomes[].timeToMFE [FUTURE_WORK]` in `completenessReport.missing`. **The packages correctly
declare these gaps.** They are not silently absent — the evidence layer is being honest about its own
limits, which is the behaviour the platform was built for.

### 7.3 Why the gate failed — and why that is the wrong question

**This evidence could never have passed, and applying the gate to it is a category error.**

`MOGO-003-VERIFIED-REPLAY-RECORD.md` states the ceiling explicitly: RUN-001 was captured on engine
**12.9.0** and predates all five capture units —

| Unit | Version | Adds |
|---|---|---|
| Unit A | 12.10.0 | version split, `realizedR`, break/retest candle refs |
| **Unit B** | **12.11.0** | **rule attribution — `triggeredConditions`** |
| **Unit C1** | **12.12.0** | **excursion timing — `timeToMFE`/`timeToMAE`** |
| **Unit C2-M1** | **12.13.0** | **bounded own-timeframe market context** |
| Unit C2-M2 | 12.14.0 | higher-timeframe context at entry close |

*"RUN-001 predates all five … and nothing has been or will be backfilled."*

The three gate fields were **introduced by 12.11.0, 12.12.0 and 12.13.0**. RUN-001 ran on 12.9.0. Its
0/24 is arithmetic, not a capture defect.

### 7.4 The actual finding

**The Step 1 pilot was never executed.** Four independent facts establish this:

1. **Engine version.** Packages carry `12.9.0`. Step 1 requires *"current engine"* — 12.18.0 at PRE-REG-001's declaration.
2. **Chronology.** RUN-001 executed 2026-08-03. PRE-REG-001 declared 2026-08-04. **The evidence predates the pre-registration that governs the pilot by one day.** A pilot cannot precede the document defining its gate.
3. **Identity.** The `runId` is RUN-001's, already registered as *"Verified · authoritative"* in `MOGO-003-VERIFIED-REPLAY-RECORD.md`. A pilot on the current engine over the same window would produce a **different `runId`** — a different `configHash` and a different dataset.
4. **Provenance.** `MOGO-004-PLAN.md` §0 opens by naming these same 24 packages as MOGO-003's output, the *starting position* for MOGO-004.

The shape coincidence is real and is what makes this trap easy to fall into: the pilot is specified as
EUR_USD, one run, 90-day lookback, ~24 expected trades — which describes RUN-001 exactly. **That is
because the pilot was designed to re-run RUN-001's window on the current engine.** Same window, same
pair, same parameter; different engine, different run, different `runId`.

> **Reading RUN-001 as a failed pilot would be the single most damaging error available here.** It would
> conclude "capture is broken, fix the engine" when nothing is broken — the capture units exist and
> shipped across 12.10.0–12.14.0. It would burn effort re-fixing working code, and it would leave the
> genuine question — *does the current engine actually populate these fields in a browser?* — still
> unasked. That question remains **completely untested**. `MOGO-003-VERIFIED-REPLAY-RECORD.md` records
> that browser verification of timing- and context-bearing packages *"is still pending"*, and
> PRE-REG-001 §6 gives the reason the pilot exists at all: *"nothing since engine 12.9.0 has been
> exercised in a browser."*

**Correct verdict: the gate is UNEVALUATED, because the artifact it governs does not exist yet.**

---

## 8. Evidence chain — end-to-end status

| Link | Status |
|---|---|
| Dataset → `datasetHash` | ⚠️ fingerprinted, **not reproducible** — candles not retained |
| `datasetHash` + `configHash` + `paramsHash` + window → `runId` | ✅ **independently recomputed, exact match** |
| `configSnapshot` → `configHash` | ✅ **independently recomputed, exact match** |
| Replay params → `paramsHash` | ✅ **independently recomputed, exact match** — confirms declared params were used |
| Trades → 24 packages | ✅ 24 resolved trades, 24 packages, 1:1, no duplicates |
| Package content → `contentHash` | ✅ **24/24 verified** against a clean-room canonicalizer |
| Packages → published statistics | ✅ **every figure reproduces exactly** |
| Packages → `MOGO-003-VERIFIED-REPLAY-RECORD.md` | ✅ fully consistent; no correction required |
| Packages → hypothesis registry | ✅ all 12 `evidenceRunIds` point at the verified `runId`, `joinStatus: LINKED` |
| Suppressed setups → rejection record | ❌ **aggregates only — 15 individual records absent** |
| Packages → rule-level attribution | ❌ **absent** — 0/24, engine predates Unit B |

**Integrity: intact. Completeness: PARTIAL, correctly and honestly declared.**

Scope note, per the platform's own wording: `contentHash` is `INTEGRITY_ONLY_NOT_AUTHENTICITY`. These
checks prove the packages have not been *altered* since capture. They are not a signature and offer no
protection against someone able to replace both a package and its hash.

---

## 9. What Step 1 still requires

Nothing below has been started. Listed so the remaining work is explicit, not as a proposal to proceed.

1. **Authorization for one replay run.** Separate and explicit — PRE-REG-001 §11 grants none.
2. **Run the pilot:** EUR_USD, 90-day lookback parameter, **current engine**, isolated browser profile.
3. **Discharge the 10-item browser checklist.**
4. **Save all three artifacts:** packages, **`alexGReplayRejected` in full** (§6 above), harvest.
5. **Record the §8 per-run entry:** `runId`, three hashes, observed absolute UTC window, per-timeframe candle counts, ADR-011 completeness, `APP_VERSION`, commit, re-import verification, register entry.
6. **Evaluate the gate on the pilot's own packages** — `triggeredConditions`, `timeToMFE`/`timeToMAE`, market context.

Then, and only then, does the C1 question arise.

---

## 10. Decision gate — your approval required

Stopping here, as instructed. Two decisions, neither of which is mine to make.

### Decision 1 — Replay authorization for the Step 1 pilot

One replay run: `alex_g_sr_v1`, EUR_USD, 90-day lookback parameter, current engine, isolated profile,
read-only market-data retrieval, no paper or live execution, no OANDA writes.

PRE-REG-001 §11 is explicit that it authorizes nothing. Without this, Step 1 cannot proceed and C1 is
blocked behind it.

### Decision 2 — The rejection-record gap for RUN-001

The 15 suppressed setups are not individually recoverable from the evidence directory (§6). Options,
with my recommendation first:

- **(a) Accept and disclose.** RUN-001 predates §9, so it is not in breach. Record the limitation, report
  the 38.46% suppression rate wherever RUN-001 is cited, and enforce §9 strictly from the pilot forward.
  **Recommended** — it costs nothing, it is honest, and re-running RUN-001 to recover the list would
  produce a different run with a different `runId`, not a repair of this one.
- **(b) Attempt recovery.** Would require re-executing RUN-001's exact dataset. The dataset is not
  retained, so this is very likely impossible — and any new run is new evidence, not a backfill.
- **(c) Treat RUN-001 as uninterpretable** until the list exists. Defensible in the strict reading of
  §9, but it would discard a run whose integrity is otherwise fully verified.

### For the avoidance of doubt

- **No code was modified.** No feature was implemented. **Campaign C1 was not begun.**
- No temporary copy was used — every check ran against `~/Desktop/Forex Hub` and `~/Desktop/MOGO-Evidence` directly.
- **No hypothesis was adjudicated, and none may be.** PRE-REG-001 §7 permits adjudication **once**, after the declared runs complete. Zero declared runs have completed.
- RZR remains suspended. No strategy is approved for live execution. Nothing here changes that.

---

**RUN-001 is verified, authoritative, and exactly what the record says it is. It is not the Step 1
pilot. Step 1 remains open, and the pilot gate remains genuinely unevaluated — which is the honest
position, and the only one that leaves the gate able to do its job.**

# PRE_ADJUDICATION_PROTOCOL.md — Campaign C1

**Milestone:** MOGO-007 · **Protocol version:** 1.0 · **Finalized:** 2026-08-06
**Status:** **APPROVED — ready for adjudication**
**Campaign:** `CAMP|ALEX|C1|2026-08-05` (frozen, `cd3da72`)
**Governs:** the single adjudication permitted by PREREG-001 §7

**Purpose.** Fix every methodological decision *before* any statistic is calculated, so adjudication
is the mechanical execution of a settled method rather than a sequence of judgment calls made while
looking at results.

**This document computes nothing.** No campaign statistic, no arm population, no comparison, no
ranking, no promotion, no rejection. Structural counts appear only where they were needed to
determine whether a declared method is executable at all.

**Sources:** `PREREG-001-alex-multipair-2026-08-04.md`, `PREREG-002-alex-c1-execution-2026-08-05.md`,
`STATISTICAL-GOVERNANCE.md`, `hypothesis-registry.json` (byte-unchanged since HEAD `f8004fe`, the
version PREREG-001 §2 binds to). **None of these is modified by this protocol.**

---

# Part 0 — Governing principles

## P1 — Adjudication Determinism Principle

> Given identical frozen evidence, pre-registration, protocol version, engine version, registry
> state, statistical methods, seeds, and parameters, **adjudication must produce identical outputs and
> conclusions**. No analyst discretion may be introduced after adjudication begins.

**Enforcement.** Every stochastic procedure has a fixed, recorded seed (§P1.1). Every ordering is
total and explicit (§P1.2). Every threshold comparison is defined to the operation (§P1.3). The
execution environment is recorded (§P1.4). If any step in Part 3 admits two answers, that is a defect
in this protocol and adjudication **stops** until it is amended and re-approved — it is never resolved
at the keyboard.

**P1.1 — Seeds.** The only stochastic procedure is the BCa bootstrap. Its parameters are fixed here
and may not be varied: **seed `20260806`**, **10,000 resamples**, **BCa** (bias-corrected and
accelerated), resampling **per-trade R values within each arm independently**, two-sided, 95%. The
seed and resample count are recorded in the adjudication output for every interval produced.

**P1.2 — Orderings.** The trade table is sorted by `runId` ascending, then `packageId` ascending
(both lexicographic, byte order). Holm–Bonferroni ranks by ascending p-value; **ties break by
`hypothesisId` ascending, lexicographic.** No other ordering affects any result.

**P1.3 — Numeric comparisons.** All comparisons are performed on IEEE-754 double precision values as
computed, never on rounded values. Reported figures are rounded to **4 decimal places for R
quantities** and **1 decimal place for percentages**, for display only. The declared thresholds are
applied exactly as written: `≥ 0.25R` means greater-than-or-equal, so an exact 0.25 satisfies it;
`< 0.10R` means strictly less than.

**P1.4 — Environment.** Record interpreter and version, library names and versions, operating system,
protocol version (1.0), this document's SHA-256, and the campaign manifest's verification result. A
re-run producing different figures under an identical record is a defect to be investigated, not a
new result.

## P2 — Conservative Decision-Boundary Principle

> When multiple scientifically defensible methods disagree at a rule-promotion boundary, the decision
> **must resolve in the direction that does not promote the rule**.

**Scope.** P2 governs *disagreement between methods*, and only in the promoting direction. It **never**
overrides a declared threshold, never converts a satisfied gate into an unsatisfied one absent
disagreement, and never manufactures a rejection — rejection is a positive finding with its own
declared preconditions (§R9).

**Applications in this protocol:** the Welch/bootstrap tie-break (§R7), the conjunctive reading of the
interval gate and the multiplicity correction (§R13), and any future case where two defensible
readings of a declared threshold differ at the boundary.

---

# Part 1 — Settled by pre-registration. Not reopened.

| # | Item | Value | Source |
|---|---|---|---|
| S1 | Primary metric | `MET_EXPECTANCY_R` = net R ÷ resolved trades | PREREG-001 §3 |
| S2 | Metric source field | `objects.outcomes[].recordedResultR` | registry `metricRegistry` |
| S3 | Secondary metrics | `MET_WIN_RATE`, `MET_NET_R`, `MET_MAE_PIPS`, `MET_MFE_PIPS` | PREREG-001 §3 |
| S4 | Comparison surface | **R-space only**; money-space reported, never compared | PREREG-001 §3, SG §1 |
| S5 | Promotion threshold | armA − armB ≥ 0.25R **and** interval excludes zero | PREREG-001 §4 |
| S6 | Rejection threshold | difference < 0.25R, or favours armB, **with both arms ≥ 30** | PREREG-001 §4 |
| S7 | Minimum operational sample | **30 resolved trades per arm**; not lowerable | PREREG-001 §4, SG §3 |
| S8 | Multiplicity | Holm–Bonferroni across the declared family | PREREG-001 §4, SG §4 |
| S9 | Effect-size bands | < 0.10R indistinguishable · 0.10–0.25R suggestive only · ≥ 0.25R promotable if conditions hold · ≥ 0.50R large, check for artifact | SG §5 |
| S10 | Promotion ceiling | `REPLAY_EVIDENCE_ONLY`, categorical, at any sample size | PREREG-001 §5, SG §6 |
| S11 | Family | The 12 named hypotheses. **None may be added.** | PREREG-001 §2 |
| S12 | Adjudication frequency | **Once.** No interim looks. No run added to reach a threshold. | PREREG-001 §7 |
| S13 | Profit factor, zero losses | `null`, never infinity | SG §1 |
| S14 | Cost basis | **Gross**; any near-zero result must say so | PREREG-001 §3 |
| S15 | Post-hoc patterns | Become new pre-registered hypotheses awaiting new evidence | SG §4.4 |
| S16 | Allowed statuses | `UNSUPPORTED`, `COLLECTING`, `SUPPORTED`, `REJECTED`, `UNRESOLVED` | registry |

---

# Part 2 — Resolved decisions

All twelve questions from the MOGO-007 review are resolved. Five were approved by the operator on
2026-08-06 (**R1, R2, R5, R7, R10**); the remainder apply existing pre-registered text. **No
placeholder or open question remains.**

## R1 — Arm B is empty by construction · APPROVED

**Finding.** The ten `conditionId`s in the evidence are setup qualification gates: a trade exists
*because* they were satisfied. Structural inspection: **1,142 `triggeredConditions`, all
`satisfied=true`, zero `failedConditionIds`, zero engine-classification contradictions.** The
`candidates` and `decisions` arrays are **empty on all 221 packages** (durable decision chains remain
MOGO-003 Phase 2, memory-only). Rejection records carry only `tradeId`, `setupId`, `pair`,
`timeframe`, `reason` — no condition detail, no outcome — and those setups were suppressed by the
portfolio constraint, not by condition failure.

**Resolution.** Adjudicate exactly as pre-registered. **Arm B is not redefined post hoc under any
circumstance.** Where arm B cannot be populated, record the outcome under the existing registry
framework with a precise `statusReason` (§R9, §R10). Additionally: `AXR-001` and `AXR-090` are
definitional rather than per-trade predicates, and `AXR-030`, `AXR-041`, `AXR-043` are configuration
constants identical across every campaign trade — each admits no contrast, and the `statusReason`
must say which of these applies.

**Required future work — not performed in this milestone.** A **successor pre-registration** governing
future evidence collection capable of populating both arms. It requires an engine capability that does
not currently exist (durable capture of non-qualifying candidates with condition detail, or a design
in which the condition is deliberately varied). It governs future evidence only and **is not a
prerequisite for adjudicating C1**.

**Nature:** applies existing text. No amendment.

## R2 — `datasetHash` differs per instrument · APPROVED

**Resolution.** **Campaign-level pooling is the primary adjudication basis**, because strategy,
engine version, `configHash` and `paramsHash` are invariant across Campaign C1 — the arm basis clause
functions as an anti-confounding rule, and pooling within one campaign does not confound the arm
contrast. Each trade **retains its own `datasetHash`** in the trade table, so the pooling is fully
reversible by any later analyst. Per-instrument results are reported **only as clearly labelled
secondary analyses that do not independently determine any adjudication outcome.**

**Nature:** clarification of existing text. No threshold, metric or arm definition changes.

## R3 — Evidence admitted

**Resolution.** **Campaign C1 only** — 221 packages across eleven runs. RUN-001 (engine 12.9.0, no
rule attribution) and the MOGO-004 pilot (engine 12.18.0, declared capture-verification, PREREG-002
§1: "not a C1 run") are **excluded**. Mixing engine versions would violate the arm basis in a way that
pooling instruments does not (§R2).

**Nature:** pre-registered.

## R4 — Unresolved (still-open) trades

**Resolution.** Excluded — they produce no package by design, and every declared threshold is written
in terms of **resolved** trades. The excluded count and its share of trades created are stated
alongside every headline figure. **No outcome is ever imputed.** A sensitivity bound (all excluded
trades scored maximum-adverse, then all maximum-favourable) is produced **only** if a headline figure
lands within 0.05R of a declared threshold; if produced it is reported as a bound, never substituted
for the primary figure.

**Nature:** pre-registered.

## R5 — Suppression accounting · APPROVED

**Resolution.** Report the suppression rate at the **campaign level and for every relevant subgroup or
comparison** — per arm, per instrument, and for any subgroup over which a figure is computed.
**Suppression is observed censoring to be disclosed, not repaired: no model-correction, imputation,
synthesis, or estimation of suppressed setups' outcomes, ever.** Rate definition, unchanged from
`CAMPAIGN_C1_IDENTITY.md`: `suppressed ÷ (trades created + suppressed)`, denominator **trades
created**, not packages.

Where the suppression rate differs across the arms of a comparison, the comparison must state that
the censoring is **differential**, which biases a contrast rather than merely shrinking it.

**Nature:** §9 mandates campaign-level reporting; subgroup reporting is a strengthening that adds
disclosure and removes no constraint.

## R6 — Multiplicity denominator

**Resolution.** Holm–Bonferroni with family size **m = 12**, always — the full declared family,
regardless of how many hypotheses reach a computable comparison. The family was fixed in advance and
none may be added (S11); the symmetric protection is that none may be dropped from the correction.

**Nature:** pre-registered.

## R7 — Confidence interval for a difference · APPROVED

**Resolution.**
- **Primary:** Welch (unequal-variance) two-sample 95% confidence interval on the difference in mean
  per-trade R between arms. Welch–Satterthwaite degrees of freedom.
- **Robustness check, recorded:** **fixed-seed BCa bootstrap**, seed `20260806`, 10,000 resamples,
  two-sided 95%, resampling per-trade R within each arm independently. Seed and all parameters are
  recorded in the output (§P1.1).
- **Disagreement rule:** if Welch and bootstrap disagree about whether zero is excluded, **the result
  is treated as not excluding zero** (P2). This can only prevent a promotion, never create one.

Wilson intervals are used for proportions (win rate), as declared.

**Nature:** fills a gap — the pre-registration specifies intervals for quantities but not for a
difference. No declared value changes. Fixed **before** any computation.

## R8 — Effect size

**Resolution.** **Difference = armA expectancy − armB expectancy**, in R, signed, arms exactly as
defined in the registry's `comparisonGroup`. Graded against S9. Reported **with its interval**, never
as a point estimate (SG §7). **A difference ≥ 0.50R triggers a mandatory data-artifact check before
the figure is reported:** re-verify the contributing packages' `contentHash` values; confirm no single
instrument or run contributes a disproportionate share; confirm the subgroup's suppression rate is not
an outlier against the campaign rate. The check and its findings are recorded whether or not anything
is found.

**Nature:** formula and direction implicit in the declared threshold, now explicit; the artifact check
is new and can only delay or prevent a promotion.

## R9 — Gates when the arm precondition is unmet

**Resolution.** A hypothesis whose arm precondition is unmet is **neither `SUPPORTED` nor
`REJECTED`.** It retains `COLLECTING` with a `statusReason` naming the specific unmet precondition.

Rejection is a **positive finding** requiring both arms at or above 30 (S6). Recording rejection
because evidence is absent would be the mirror of the prohibited practice "treating 'not yet refuted'
as support" (SG §7), and is forbidden.

**Nature:** pre-registered — this is the registry's definition of `COLLECTING` verbatim.

## R10 — Status terminology · APPROVED

**Resolution.** **The registry schema is not modified.** Only the five existing `allowedStatuses` are
used. Insufficient or inconclusive cases map to **`COLLECTING`**, with the exact explanation in
`statusReason`. The words **"insufficient" and "inconclusive" appear only as descriptive prose in
adjudication reports, never as schema status values.**

`UNRESOLVED` is **not** used for C1 hypotheses: it means the hypothesis can never be resolved by the
available evidence class, which would prejudge whether a redesigned future campaign could populate
arm B — a stronger claim than C1 establishes.

**Nature:** terminology reconciliation between two documents, neither of which is edited.

## R11 — Promotion criteria

**Resolution.** All four registry `promotionGate` conditions must hold — minimum sample in both arms,
predeclared metric measured, comparison completed, confidence threshold satisfied — **and** the
categorical `REPLAY_EVIDENCE_ONLY` ceiling applies regardless. Per SG §6, replay-only evidence may
**never** reach `SUPPORTED` on its own, so on this evidence class `SUPPORTED` is unreachable whatever
any number shows. The ceiling is stated for every hypothesis in the adjudication report so no reader
infers that a large enough effect could have escaped it.

**Nature:** pre-registered.

## R12 — Recording the outcome

**Resolution.** Per hypothesis record: status (R9/R10), `statusReason`, both arm cardinalities, the
metric value where computable, its interval, the subgroup suppression rate, and the evidence-class
ceiling. The adjudication is written to a **new** document. `hypothesis-registry.json` is updated
(`currentStatus`, `statusReason`, `observedResolvedTrades`, `evidenceRunIds`) **only after** the
adjudication report is approved, as a **separate reviewed commit**. **No additional run may be added
to reach a threshold** (S12); extending coverage requires a successor pre-registration declared before
those runs execute.

**Nature:** pre-registered; recording mechanics are procedural.

## R13 — Interval gate and multiplicity are conjunctive · APPROVED

**Issue, surfaced while making Part 3 mechanically executable.** Holm–Bonferroni operates on
**p-values**; the declared promotion gate is stated as a **confidence interval excluding zero** at the
declared 1.96 (95%) level. Both are pre-registered (S5, S8) and the pre-registration does not say how
they combine. Three readings exist: interval only; Holm only; or both.

**Resolution — conjunctive.** A hypothesis satisfies the confidence condition **only if all of**:

1. difference ≥ 0.25R (S5), **and**
2. the Welch 95% interval excludes zero, with the bootstrap agreeing (R7, P2), **and**
3. its Holm-adjusted p-value is < 0.05, with family size m = 12 (R6).

The p-value is the two-sided Welch t-test p-value on the same difference, keeping the interval and the
test mutually consistent. Applying only one of (2) or (3) would discard a declared requirement;
requiring both is the reading that discards none, and is the non-promoting direction under **P2**.

**Technical note.** Under Welch alone the interval clause is logically implied by the Holm clause: a
Holm-adjusted p < 0.05 entails a raw p below α/(m+1−i) ≤ 0.05, which entails the unadjusted 95%
interval already excluding zero. **The interval clause becomes independently binding through the
bootstrap agreement requirement** (R7, P2) — a BCa interval on a bimodal 2R/−1R distribution can
include zero where the parametric interval does not. The conjunction is therefore not redundant as
implemented.

An equivalent formulation — constructing the interval at the Holm-adjusted level rather than at 95% —
selects exactly the same hypotheses. It was **not** adopted, because nothing declared authorises
widening the interval beyond the stated 1.96 multiplier, and doing so would report an interval that no
document pre-registered. The conjunctive form preserves both declared quantities in their declared form.

### Operator-approved clarification — recorded 2026-08-06

R13 is adopted as an **operator-approved protocol clarification**. Specifically, and for the record:

- **R13 does not introduce a new promotion threshold.** Every element — 0.25R, the 95% interval, Holm
  at m = 12, α = 0.05, 30 resolved trades per arm — was declared in advance and is unchanged.
- **R13 does not amend PRE-REG-001 or PRE-REG-002.** Neither document is edited, and no declared value
  is altered, weakened, added or removed.
- **R13 specifies only how two already-pre-registered requirements interact** — the confidence
  condition (PREREG-001 §4, SG §2) and the multiplicity correction (PREREG-001 §4, SG §4) — which the
  pre-registration declares separately without stating their composition.
- **R13 exists to eliminate analyst discretion before adjudication begins.** Left unresolved, an
  adjudicator reaching Step 7 would face three defensible compositions and no declared basis for
  choosing — precisely the discretion P1 forbids.
- **Future pre-registrations should state this interaction explicitly** rather than relying on
  protocol interpretation. See Part 5.

**Nature:** clarification in form, strengthening in effect, **not an amendment**. Relative to the
weaker readings it can only make promotion harder; it can never promote what either requirement alone
would have blocked. That direction is what makes adopting it after the evidence exists defensible.

---

# Part 3 — Executable adjudication method

Steps run in order. Each is deterministic under P1. **If any step admits two answers, stop** — do not
choose.

### Step 0 — Freeze and verify inputs
1. Re-verify all 33 artifact SHA-256 values against `CAMPAIGN_C1_EVIDENCE_MANIFEST.md`. **Any
   mismatch aborts adjudication.**
2. Load Campaign C1 only (R3).
3. Apply `mode == "REPLAY"` to every loaded file — this excludes the one `LIVE_CLOSE` package in
   `C1-01-GBP_USD-PACKAGES.json` (limitation B6). Expected campaign packages: **221**.
4. Record the environment per P1.4, including this document's SHA-256.

### Step 1 — Build the trade table
One row per package, sorted per P1.2. Columns: `runId`, `datasetHash` (retained per R2), `packageId`,
instrument, `setupType`, timeframe, `recordedResultR`, `exitReasonCode`, `maePips`, `mfePips`,
`timeToMFE`, `timeToMAE`, and the full `triggeredConditions` array.

**Every figure is recomputed from packages. The harvest `stats` blocks are never cited** — they are
engine-computed conveniences; where they disagree with package-derived values, **the packages win**,
and the disagreement is recorded.

### Step 2 — Form arms, per hypothesis
Using the registry's `comparisonGroup` **unchanged** (R1), pooled at campaign level (R2).
**Record both arm cardinalities before computing any metric.**

- If **either** arm < 30 → stop for that hypothesis; assign `COLLECTING` with a `statusReason` naming
  the unmet precondition (R9, R10). **Do not compute a comparison that cannot be adjudicated.**
- If **both** arms ≥ 30 → proceed to Step 3.

### Step 3 — Compute metrics
`MET_EXPECTANCY_R` (primary) from `recordedResultR`; secondaries per registry. Profit factor `null`
with zero losses (S13). R-space only (S4).

### Step 4 — Intervals
Welch 95% two-sample interval on the difference (primary), plus the fixed-seed BCa bootstrap (R7,
P1.1). Disagreement about excluding zero resolves as **not excluding zero** (P2). Wilson for
proportions.

### Step 5 — Effect size
armA − armB, signed, in R; grade against S9; mandatory artifact check at ≥ 0.50R (R8).

### Step 6 — Multiplicity
Two-sided Welch t-test p-value per tested hypothesis; Holm–Bonferroni with **m = 12** (R6), ties
broken by `hypothesisId` ascending (P1.2).

### Step 7 — Apply gates
Confidence condition per **R13** (all three of: ≥ 0.25R, interval excludes zero with bootstrap
agreement, Holm-adjusted p < 0.05). Then all four registry `promotionGate` conditions, then the
categorical `REPLAY_EVIDENCE_ONLY` ceiling (R11). Assign status from the five allowed values only
(R10).

### Step 8 — Report
Every figure carries: its interval, its subgroup suppression rate (R5), both arm cardinalities, the
excluded still-open count (R4), the gross-of-costs disclosure (S14), the family size (S8), and the
evidence-class ceiling (R11). Per-instrument figures are labelled secondary and non-determinative
(R2). Adjudicate **once** (S12).

### Step 9 — Record
Adjudication report first. Registry update only after approval, as a separate commit (R12).

---

# Part 4 — Validation

| Check | Result |
|---|---|
| **Internal contradictions** | **None found.** The one latent conflict — interval gate vs. multiplicity correction — is identified and resolved conjunctively in **R13** under P2. R2 (pooling) and R3 (engine invariance) are consistent: pooling occurs *within* one engine and one config, never across. R9 and R10 are consistent: both route unmet preconditions to `COLLECTING`. P2 and S6 do not conflict — P2 governs method disagreement only and never manufactures a rejection. |
| **Every methodological decision explicit** | **Yes.** Evidence set (R3), filtering (Step 0.3), arm formation (R1, R2), sample floor handling (R9), metrics and source fields (S1, S2), interval method (R7), effect size and direction (R8), multiplicity (R6), gate composition (R13), status vocabulary (R10), reporting requirements (Step 8), recording (R12). |
| **Stochastic procedures seeded** | **Yes.** One stochastic procedure exists — the BCa bootstrap. Seed `20260806`, 10,000 resamples, BCa, two-sided 95%, per-arm independent resampling; seed and parameters recorded with every interval (P1.1). |
| **No analyst discretion at boundaries** | **Yes.** Method disagreement resolves conservatively (P2, R7). Gate composition is conjunctive, not selectable (R13). Orderings and tie-breaks are total (P1.2). Comparisons occur on unrounded doubles with thresholds applied exactly as declared (P1.3). Sensitivity analysis has a pre-declared trigger of 0.05R rather than an analyst's judgement (R4). |
| **Mechanically executable against frozen evidence** | **Yes.** Every input is a named field on the frozen packages or a value fixed in this document. Steps 0–9 are executable without a further decision; any step admitting two answers halts adjudication by P1. |
| **Repository tracked modifications** | **Zero.** This document is the only change and is untracked; nothing committed. |

**Preserved unchanged:** all pre-registered thresholds, metric definitions, arm definitions, the
twelve-hypothesis family, the registry schema and its five allowed statuses, the promotion ceiling,
and both pre-registration documents.

---

# Part 5 — Guidance for successor pre-registrations

**Not performed here. Recorded as required future work.** These are gaps this protocol had to resolve
by interpretation, and which a successor should declare outright so no future campaign inherits them.

1. **State whether multiplicity is a gate condition.** The registry's `promotionGate` is a four-element
   list that omits it, while PREREG-001 §4 and SG §4 both mandate it. Add an explicit
   `multiplicityCorrectionApplied` element, or state that it is subsumed under
   `confidenceThresholdSatisfied`.
2. **Declare one decision object for the confidence gate.** Preferably: *"the promotion interval is
   constructed at the Holm-adjusted level for that hypothesis's rank."* That makes the interval and
   the correction a single object with no interaction left to specify, and removes the need for R13
   entirely.
3. **Name the p-value's provenance** — which test produces it — so the interval and the test are
   guaranteed mutually consistent rather than incidentally so.
4. **Pre-register the robustness-disagreement rule**, rather than deriving it from a principle at
   adjudication time.
5. **Declare the arm basis at campaign level**, distinguishing invariants that must match (strategy,
   engine, config, params) from strata that may be pooled with disclosure (instrument, timeframe,
   session). See R2.
6. **Require a feasibility demonstration before authorising a campaign** — proof that both arms are
   populatable by the intended evidence class. See R1: this is a cheap paper exercise that would have
   been decisive before eleven runs.
7. **Separate the portfolio constraint from evidence collection** where possible, so suppression need
   not be disclosed as informative censoring. See R5.

# Part 6 — Readiness

☒ **Ready for adjudication**

Protocol version 1.0. Adjudication may proceed on operator authorization, executing Part 3 exactly as
written.

**Recorded as required future work, not performed here:** a successor pre-registration governing
future evidence collection capable of populating both arms (R1).

---

**No adjudication performed. No statistic computed. No arm populated. No strategy or rule compared,
ranked, promoted or rejected. No trading change recommended.** The promotion ceiling remains
`REPLAY_EVIDENCE_ONLY`; RZR remains suspended.

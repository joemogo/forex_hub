# MOGO-004 — Trader Intelligence & Evidence Expansion

**Status:** PLANNING — awaiting approval. Nothing implemented.
**Predecessor:** MOGO-003 (`mogo-003-complete`, engine 12.18.0)
**Governing constraint:** this project **consumes** the evidence platform. It does not extend it.

---

## 0. The premise

MOGO-003 built the machinery to make trade evidence trustworthy. It ends with **one verified replay,
24 Evidence Packages, and no validated strategy** — RZR 16 trades at −1.00R, Break & Retest 8 trades
at −5.00R. Neither settles anything.

**MOGO-004 is about volume and breadth, not more infrastructure.** The question it must be able to
answer at the end is: *which rules and confluences actually change outcomes?* Today nothing in the
repository can answer that, because the samples are too small and only one educator is covered.

## 1. Objectives

| # | Goal | Success measure |
|---|---|---|
| G1 | Increase the quantity of validated trade evidence | verified replay runs across multiple pairs and windows, every run carrying a `runId`, dataset hash and hash-verified packages |
| G2 | Increase the *quality* of that evidence | every new package carries rule attribution, excursion timing and market context — none of which RUN-001 has |
| G3 | Expand educator coverage beyond Alex | at least one further educator taken to the same standard: canonical rule register + fidelity matrix + rule-to-evidence join |
| G4 | Build statistically meaningful datasets | sample sizes stated against a declared threshold, per setup type, with the threshold justified rather than asserted |
| G5 | Prepare testable hypotheses | every hypothesis carries a metric, a comparison, a threshold, a minimum sample and a falsification condition |

## 2. Hard boundaries

- **No protected trading logic changes.** The 63 functions and 4 constants stay byte-identical.
- **No replay behaviour changes.** Replay is used, not modified.
- **No evidence-package schema changes.** MOGO-004 writes no new package fields. If a gap is found,
  it is *recorded* and deferred, not filled mid-project.
- **No strategy rule, threshold or sizing change**, and no conclusion drawn from an insufficient
  sample. RZR remains suspended; nothing becomes approved for live execution inside this project.

## 3. The two gaps that shape sequencing

**Gap 1 — RUN-001 cannot answer rule-level questions.** It predates Unit B, so it carries no
`triggeredConditions`, no timing and no context. Every rule-level or forensic question therefore needs
a **new** replay. This makes replay authorization the first dependency, not a late one.

**Gap 2 — every hypothesis in the corpus is untestable as written.** All 641 carry the placeholder
*"Replay historical price action with and without this condition and compare outcomes."* No metric, no
threshold, no sample size, no falsification condition. Until that is fixed, more evidence produces no
more answers.

## 4. Proposed milestones

### M1 — Real-account validation *(prerequisite, one page load)*
Diagnostics → Ledger Reconciliation on the real ALEX and JVM accounts, read-only. Confirms the
integrity rules produce no false positive on genuine history and that reconciliation is clean.
**Blocks nothing technically, but everything interpretively** — statistics built on an unvalidated
account are not worth computing.

### M2 — Resume and finish the ALEX rule-to-evidence join
Paused, intact, two untracked files. Add the fixture-based tests, commit, and use its `UNRESOLVED`
list as the concrete evidence-schema gap register for later projects.

### M3 — Evidence expansion, ALEX *(needs replay authorization)*
Additional authorized replays on the current engine, so packages carry attribution, timing and
context. Sequenced to change one variable at a time: EUR_USD over a longer window first, then
additional pairs. Each run recorded in the verified replay register with its identity and hashes.

### M4 — Hypothesis testability upgrade
Convert ALEX hypotheses from placeholder tests to executable ones: named metric, comparison,
threshold, minimum sample, falsification condition. Add a metric registry so a measure is defined once
and referenced, and a validation ledger with an explicit ceiling — **replay evidence alone can never
raise a rule above `REPLAY_EVIDENCE_ONLY`.**

### M5 — Second educator to ALEX standard
TJR first (the corpus already holds TJR claims and a Phase-1 session engine). Deliverables mirror
ALEX: canonical rule register, fidelity matrix with code locations, rule-to-evidence join. **Strategies
stay independently measurable — no cross-strategy merging, ever.**

### M6 — Statistical readiness report
Per strategy and per setup type: sample size, what is and is not answerable at that size, and which
hypotheses remain untestable. Explicitly permitted to conclude *"still insufficient"* — that is a
finding, not a failure.

## 5. Sequencing logic

M1 first because conclusions from an unvalidated account are worthless. M2 next because it is already
built and its gap register informs everything after. M3 before M4 so hypotheses are written against
evidence that actually exists. M5 after the ALEX pattern is proven end-to-end once. M6 last because it
reports on the rest.

## 6. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| **Sample size never reaches significance** | **High** | state it plainly in M6; do not lower the bar to manufacture a conclusion |
| Replay authorization not granted | High | M1, M2, M4 proceed without it; M3 and M5 stall — sequence accordingly |
| Quarantine false positives distort samples | Medium | M1 settles this before any statistics are computed |
| Educator expansion produces breadth without depth | Medium | one educator taken fully to standard beats three taken partially |
| Multiple-comparison error across many hypotheses | Medium | pre-register hypotheses in M4 *before* the M3 evidence is analysed |
| Scope creep back into infrastructure | Medium | the boundary in §2 is the test: if it changes a package field, it is not MOGO-004 |

## 7. Explicitly out of scope

Sizing authority · enabling derived reporting · the content-addressed candle store ·
untraded-candidate context · decision chains · any schema change · any strategy-rule change · any
live-execution approval.

## 8. Open decisions needed before starting

1. **Replay authorization** — how many runs, which pairs, which windows? M3 and M5 depend on it.
2. **Second educator** — TJR confirmed, or a different one?
3. **The significance threshold** — what sample size counts as meaningful? I would propose declaring
   it *before* seeing more results, so it cannot be rationalised afterwards.
4. **The stored 8899 balance** — corrected, or left as a forensic artifact?

---

**MOGO-004 succeeds if, at the end, we can say which rules matter — or say honestly that the evidence
still cannot tell us.** Both are acceptable outcomes. Manufacturing the first when the truth is the
second is not.

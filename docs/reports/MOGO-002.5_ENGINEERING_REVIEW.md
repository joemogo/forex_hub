# MOGO-002.5 — Engineering Review Package

**Milestone:** Strategy Fidelity Audit · **Status:** COMPLETE, awaiting Engineering Authority review
**Date:** 2026-07-29 · **HEAD:** `a332d04` (milestone work uncommitted)
**Subject:** `alex_g_sr_v1` — the ALEX paper-trading implementation

> **No further implementation will proceed until this package is reviewed.**

---

## 1. Executive Summary

MOGO-002.5 built the infrastructure to answer one question: *does the ALEX paper-trading engine
actually execute the reconstructed Alex strategy?* It now can, and the first answer is available.

**The infrastructure works and the engine is largely faithful to what the source states.** Of 13
specification rules, **9 MATCH**, 2 are approximations, 1 is ambiguous by the source's own admission,
1 is not applicable because the source declined to mandate it. **Nothing is missing and nothing
outright differs.** Where the source is definite, the code follows it — the three-reactions-validate
rule, the never-trade-against-role prohibition and the break-and-retest sequence are all enforced
exactly, verified by calling the real protected functions.

**The material finding is not a mismatch. It is a gap in the specification itself.**

> **Risk fidelity is 0/0 and trade-management fidelity is 0/0.** The specification contains **zero**
> risk rules and **zero** trade-management rules, yet every ALEX paper trade is opened with a stop, a
> target and a position size — `stopATRBuffer 0.25`, `riskPercent 1.0`, `minRR 2.0`.

This is not a defect introduced by anyone. `RULES_ALEXG` has always recorded it plainly: the
stop-loss/take-profit/risk/R:R mechanism is *"100% unaddressed by the source"*. What this milestone
changes is that the consequence is now measured rather than noted. **Risk fidelity is not
unverified — it is undefined, because there is nothing to verify against.** Six of eight
extra-implementation rules affect real trading behaviour.

**Execution readiness is `NOT_VERIFIED`** (6 of 10 criteria failed) and **profitability is
`UNVALIDATED`** and structurally cannot be anything else — the report generator hard-codes it.

**Three repository facts shaped every design decision, and each is worth the Authority's attention:**

1. **48 of 63 protected functions are ALEX.** Every rule evaluator that matters is protected. The
   fidelity toolchain therefore lives outside the application as an offline auditor, and trade
   provenance is stamped in the one non-protected seam. **Result: 113 insertions, 0 deletions, zero
   drift.**
2. **Two strategies claim the Alex name.** `alex_g_sr_v1` paper-trades; `ALEX_SCORE_V2`
   (`1.0.0-research`) is shadow-only. Any statement about "ALEX fidelity" must say which.
3. **A third body of Alex knowledge exists and was deliberately not used.** 195 educator claims sit
   in `docs/trader-intelligence/`, all at `emerging` confidence. `DECISION|MOGO|20260727|004` and
   `traders/alex-g/profile.json` both state the engine's rules are MOGO's own, *not* the educator's.
   Using them as the specification would have fabricated a lineage the repository explicitly denies.

**What the Authority is being asked to decide** is smaller than it might appear. The single
consequential question is `GAP-PROV-001`: should `alex_g_sr_v1` be re-specified against the educator
library? If yes, the specification is not 13 concepts but something far larger, and every fidelity
number in this package is measured against the wrong baseline. If no, the engine should be formally
recorded as MOGO-authored beyond its source, and `GAP-RISK-001` becomes an acquisition target rather
than a defect. **Everything else can wait on that answer.**

**Validation:** 591/591 JS fixtures across 13 suites · 63/63 new Python tests · **zero
protected-function/constant drift** · 4 pre-existing, unrelated Trader Intelligence failures reported
separately and unchanged.

---

## 2. Repository Truth Report

Full detail: [`docs/strategy-fidelity/MOGO-002.5-REPOSITORY-TRUTH-AUDIT.md`](../strategy-fidelity/MOGO-002.5-REPOSITORY-TRUTH-AUDIT.md)

### 2.1 The reconstructed artifact — identified

`RULES_ALEXG` is a **protected constant** and already separates the two evidence classes:

| Field | Count | Role |
|---|---|---|
| `originalAlexConcepts` | **13** | What the source states → **the specification** |
| `hubTestStandardizations` | **15** | What MOGO chose → **extra implementation** |
| `config` | 20 keys | The parameters actually traded |
| `experimentalParams` | 1 | Explicitly untuned |

The stop condition *"the reconstructed Alex strategy artifact cannot be identified"* does not apply.

### 2.2 Protected-code topology

63 protected functions, 4 protected constants. **48 functions are `alexG*`**, including
`alexGConstructLivePosition`, `alexGRunSetupEngine`, `alexGEvaluateBreakRetest`,
`alexGEvaluateRepeatedReaction`, `alexGDetermineTradeDirection`. Protected constants include
`RULES_ALEXG` itself.

### 2.3 Existing infrastructure reused, not duplicated

| Requirement | Already existed |
|---|---|
| Rule-level tracing | `mogo.decision-event.v1` — `RULE_EVALUATED` carries `ruleId`/`ruleVersion`/`ruleResult`/`reasonCode` |
| ALEX rule IDs | `ALEX_ACTIVATION_CUTOFF`, `ALEX_SIGNAL_STALENESS` (17 emit sites) |
| Per-trade config snapshot | `configurationSnapshot` + `createdByEngineVersion` |
| Canonical JSON / hashing | `graph_common.py` |

### 2.4 Prior test coverage

12 suites, 530 fixtures. **No suite covered strategy fidelity or trade provenance** before this
milestone.

---

## 3. Files Added

| Path | Lines | Purpose |
|---|---|---|
| `scripts/strategy_fidelity/fidelity_model.py` | 422 | Domain model, vocabularies, validation |
| `scripts/strategy_fidelity/alex_specification.py` | 295 | Extracts the spec from `RULES_ALEXG` |
| `scripts/strategy_fidelity/alex_manifest.py` | 415 | Implementation manifest + symbol resolver |
| `scripts/strategy_fidelity/fidelity_compare.py` | 230 | Deterministic comparison engine |
| `scripts/strategy_fidelity/build_fidelity_report.py` | 361 | Report generator (JSON + Markdown) |
| `tests/strategy_fidelity/test_strategy_fidelity.py` | 430 | 63 tests |
| `tests/v1027_strategy_fidelity_provenance_tests.js` | 302 | 61 fixtures |
| `tests/run_v1027_strategy_fidelity_provenance_tests.js` | 117 | Runner (auto-discovered) |
| `docs/strategy-fidelity/MOGO-002.5-REPOSITORY-TRUTH-AUDIT.md` | 114 | Phase 1 |
| `docs/strategy-fidelity/manifests/*.json` | 3 files | Spec, manifest, trace mapping |
| `docs/strategy-fidelity/reports/*` | 2 files | Fidelity report (JSON + MD) |

**None of the Python is imported by, or reachable from, trading code.**

## 4. Files Modified

**`index.html` — 113 insertions, 0 deletions.** The only modified file.

| Addition | Location | Protected? |
|---|---|---|
| `ALEX_PROVENANCE_SCHEMA_VERSION`, `ALEX_IMPLEMENTATION_VERSION`, `ALEX_PROVENANCE_CLASSES` | before `snapshotAlexGConfig` | No |
| `alexGStableHash`, `alexGStrategyVersionReference`, `alexGStampTradeProvenance`, `alexGClassifyTradeProvenance`, `alexGProvenanceSummary` | same block | No |
| One call: `alexGStampTradeProvenance(position);` | inside `alexGAttemptOpenLivePosition` | **No** |

`alexGConstructLivePosition` was **not** edited. Verified: zero drift.

---

## 5. Architecture Decisions Made

### AD-1 — The fidelity toolchain is an offline Python auditor, not an in-app module

**Why.** 48 of 63 protected functions are ALEX. An in-app auditor would either touch protected code
or sit beside it and drift. An offline tool that reads the repository as data **cannot alter trading
behaviour by construction**, which is the milestone's first governance requirement.

**Evidence.** `regression-baseline.json`; the `scripts/trader_intelligence/` precedent for offline
analysis tooling; zero drift measured after the fact.

**Alternatives.** (a) In-app JS module — rejected: adds runtime surface to a file where 48 functions
are frozen, and a bug could reach the trading path. (b) Extend an existing protected function —
rejected outright: baseline drift. (c) Separate repository — rejected: code references could not be
verified against the source they describe.

**Confidence: HIGH.** The constraint is documented and machine-checked.

### AD-2 — The specification is `RULES_ALEXG.originalAlexConcepts`, NOT the Trader Intelligence library

**Why.** The repository states in two places that the engine's rules are MOGO's own, not the
educator's. Treating 195 `emerging` claims as this engine's specification would fabricate a denied
lineage and import unvalidated material into a fidelity baseline.

**Evidence.** `DECISION|MOGO|20260727|004`; `traders/alex-g/profile.json` — *"fully specified by
MOGO's own implementation and documentation … not derived from an external trader's research"*; the
195 claims carry **zero** rule candidates.

**Alternatives.** (a) Use the TI library — rejected on the above. (b) Merge both — rejected: silently
mixes two evidence classes the governance requires be kept separate. (c) Refuse to proceed — rejected:
a valid approved artifact exists; refusing would have been over-cautious.

**Confidence: HIGH** on the choice; the *question* of whether it should change is `GAP-PROV-001`,
which is explicitly the Authority's to answer.

### AD-3 — Rule classification consulted before implementation status

**Why.** The brief requires that ambiguous and unresolved rules never become false matches. If
implementation status decided first, a confident implementation of an ambiguous rule would score as
fidelity. So: `UNRESOLVED → AMBIGUOUS`, `DISCRETIONARY → NOT_APPLICABLE`, `INFERRED → UNVERIFIABLE`,
**always**, regardless of the code.

**Evidence.** `ALEX_SR_008` is `IMPLEMENTED` in the manifest and reports `AMBIGUOUS` — the guarantee
is live, not aspirational. Two tests assert it directly.

**Alternatives.** (a) Status-first with an ambiguity flag — rejected: the headline number would still
be wrong. (b) Exclude ambiguous rules — rejected: hides them.

**Confidence: HIGH.**

### AD-4 — `UNKNOWN`/absent mapping reports `UNVERIFIABLE`, never `MISSING_IMPLEMENTATION`

**Why.** Absence of inspection is not absence of code. Reporting uninspected rules as missing would
overstate the failure and invite unnecessary changes to working behaviour.

**Evidence.** Enforced in `compare_rule`; two tests.

**Alternatives.** (a) Treat as missing — rejected as dishonest. (b) Omit — rejected: silently shrinks
the denominator.

**Confidence: HIGH.**

### AD-5 — `IMPLEMENTED` is structurally rejected without `inspected=True` + a code reference

**Why.** The brief says do not claim a rule is implemented unless the code path has been inspected.
Making that a model-level error rather than a convention means it cannot be forgotten.

**Evidence.** `fidelity_model.py` raises `FidelityModelError`; test asserts the raise.

**Alternatives.** (a) Warning — rejected: warnings get ignored. (b) Trust the author — rejected: the
manifest's entire authority rests on this being true.

**Confidence: HIGH.**

### AD-6 — Code references resolve by SYMBOL at build time, not by stored line numbers

**Why.** Line numbers rot. **This milestone's own Phase 5 edit invalidated 26 of them in one
change**, which the verifier caught. Resolving from symbols means a rename or deletion is reported
instead of silently pointing at unrelated code.

**Evidence.** The failure occurred and was caught; after refactor, all 26 references resolve live and
a test asserts `problemCount == 0`.

**Alternatives.** (a) Keep line numbers with a checker — rejected: requires manual maintenance
forever. (b) No verification — rejected: an unverifiable manifest that looks authoritative is worse
than none.

**Confidence: HIGH.** Demonstrated by a real failure inside this milestone.

### AD-7 — Provenance is stamped in the non-protected caller, on the object the protected constructor returned

**Why.** Phase 5 requires new trades to carry version identity. `alexGConstructLivePosition` is
protected. `alexGAttemptOpenLivePosition` is not, and holds the position before it is pushed and
committed — the exact seam v12.6.0 used for the same reason.

**Evidence.** 113 insertions / 0 deletions; zero drift; fixtures C1–C3 assert entry/stop/target are
byte-identical after stamping.

**Alternatives.** (a) Edit the constructor — rejected: drift, and it would change a protected
function for observability. (b) A separate side-table keyed by `tradeId` — rejected: provenance
could desynchronise from the trade it describes.

**Confidence: HIGH.**

### AD-8 — A third provenance class, `PARTIAL_PROVENANCE`, alongside `VERSIONED` and `LEGACY_UNVERSIONED`

**Why.** Pre-existing trades already carry `configurationSnapshot` and `createdByEngineVersion` —
genuinely partial version evidence. Rounding them up to `VERSIONED` would claim provenance they never
had; rounding down to `LEGACY_UNVERSIONED` would discard real evidence. The brief forbids the first;
the second is simply inaccurate.

**Evidence.** Inspected trade shape; fixtures D3/D4 assert `PARTIAL`, D7 asserts no mutation.

**Alternatives.** (a) Two classes only — rejected: forces a false choice. (b) Migrate old records —
**rejected outright**: the brief forbids rewriting old records to imply provenance that did not exist.

**Confidence: HIGH.** ⚠️ This adds a class the brief did not name — flagged for review as **OD-6**.

### AD-9 — Reuse `mogo.decision-event.v1` for tracing; do not build a parallel trace

**Why.** The brief says reuse existing trace architecture if present. It is present, already carries
every required trace field, and is already wired to ALEX's candidate lifecycle at 17 sites.

**Evidence.** `docs/DECISION_EVENT_ARCHITECTURE.md`; the trace mapping records which lifecycle stages
are traced (5 of 7) and which are structurally unreachable.

**Alternatives.** (a) New trace store — rejected: duplication, and two traces would drift. (b)
Instrument the protected setup evaluators — **rejected: forbidden**, and their `{qualifies:false}`
contract discards which condition failed regardless.

**Confidence: HIGH** on reuse; **MEDIUM** on completeness — 2 of 7 lifecycle stages remain untraced
and cannot be reached without an Authority decision.

### AD-10 — Coverage reported as numerator/denominator; no composite fidelity score

**Why.** The brief says do not rely solely on a composite score. A single number would hide the
difference between an ambiguous rule and an unimplemented one, and `0/0` risk fidelity would round to
something meaningless.

**Evidence.** Every coverage metric emits `matched`, `total` and `unmatchedRuleIds`.

**Alternatives.** (a) Weighted score — rejected: invents weights the repository does not have.
(b) Percentage — rejected: `0/0` has no percentage.

**Confidence: HIGH.**

### AD-11 — `profitabilityStatus` is hard-coded; `executionReadiness` is computed and defaults to NOT_VERIFIED

**Why.** Fidelity and profitability are orthogonal. No input to this generator could justify any
other profitability value, so it is not a computed field at all.

**Evidence.** Constant in the generator; test asserts it. Readiness fails 6 of 10 criteria, each
reported individually with its evidence.

**Alternatives.** (a) Compute profitability — rejected: nothing measures it. (b) Omit — rejected: its
explicit absence is the point.

**Confidence: HIGH.**

---

## 6. Initial ALEX Strategy Fidelity Report

Full report: [`docs/strategy-fidelity/reports/ALEX-FIDELITY-REPORT.md`](../strategy-fidelity/reports/ALEX-FIDELITY-REPORT.md)

| Field | Value |
|---|---|
| Strategy | `alex_g_sr_v1` |
| Specification version | `alex_g_sr_v1` (rule-set hash `a0b7641e288c1725`) |
| Implementation version | `alex_g_sr_v1.impl.1` |
| Engine version | `12.6.0` |
| Report generator / comparison engine | `1.0.0` / `1.0.0` |
| Decision trace version | `mogo.decision-event.v1` |
| **Profitability** | **`UNVALIDATED`** |
| **Execution readiness** | **`NOT_VERIFIED`** — 6/10 criteria failed |

| Coverage metric | Value | Unmatched |
|---|---|---|
| Explicit-rule coverage | **9 / 11** | `ALEX_SR_007`, `ALEX_SR_012` |
| Required-rule coverage | **7 / 8** | `ALEX_SR_008` |
| Deterministic-rule fidelity | **7 / 8** | `ALEX_SR_012` |
| **Risk fidelity** | **0 / 0** | — |
| **Trade-management fidelity** | **0 / 0** | — |
| Source traceability | **13 / 13** | — |
| Test coverage (named tests) | **10 / 13** | `ALEX_SR_007/008/012` |

**Findings:** 9 MATCH · 2 APPROXIMATED · 1 AMBIGUOUS · 1 NOT_APPLICABLE · 8 EXTRA ·
**0 MISSING · 0 DIFFERING · 0 UNVERIFIABLE**

**Category distribution** — note that ENTRY, RISK and SESSION_RESTRICTIONS contain **only** extra
implementation rules and no specification rules at all:

| Category | Spec rules | Extra impl |
|---|---|---|
| SETUP | 7 | 3 |
| TIMEFRAMES | 2 | 0 |
| MARKET_STRUCTURE | 2 | 0 |
| NO_TRADE_CONDITIONS | 1 | 1 |
| DIRECTIONAL_BIAS | 1 | 0 |
| **ENTRY** | **0** | **2** |
| **RISK** | **0** | **1** |
| **SESSION_RESTRICTIONS** | **0** | **1** |

## 7. Missing ALEX Rules

**Zero rules are MISSING_IMPLEMENTATION.** Every rule the source states has a code path.

Two rules are unmatched for reasons that are *not* missing implementation:

- **`ALEX_SR_008` (zone tightness)** — `AMBIGUOUS`. Required by the method; the source gives no
  formula. Cannot be scored either way.
- **`ALEX_SR_013` (trend direction)** — `NOT_APPLICABLE`. The source calls it *"a single soft
  mention … never stated as a requirement"*. The engine records trend context and never gates on
  it — **faithful**, precisely because it does not enforce it.

## 8. Implementation Differences

**Zero rules are IMPLEMENTATION_DIFFERS.** Three are `APPROXIMATED`:

| Rule | Difference |
|---|---|
| **`ALEX_SR_007`** | Source: more touches always better, **no ceiling**. Code: strength saturates at `strong` for 4+, so a 12-touch and 4-touch zone are indistinguishable to every consumer. Raw count is retained but unused. |
| **`ALEX_SR_008`** | Source: *"no formula given"*. Code: substitutes `zoneClusterATRMultiplier = 0.5`, flagged EXPERIMENTAL and *"not tuned against outcomes"*. |
| **`ALEX_SR_012`** | Source: round numbers are *"additional, non-mandatory confluence"*. Code: records raw distances only and **never uses them as confluence** — the proximity boolean was deliberately removed in v3.6.1. |

Plus one behavioural discrepancy that does not change today's trades:

- **`FIDELITY-DISC-001`** — `RULES_ALEXG.config.zoneTimeframes` is declared but **never read**. All
  three real loops hardcode `['H1','H4','D','W']`. Behaviour is correct; the config key is dead, so a
  future edit to it would silently have no effect.

## 9. Extra Rules Found

Eight behaviours in code with no specification rule. **Six affect real trading behaviour.**

| ID | Category | Affects trading | Origin | Behaviour |
|---|---|---|---|---|
| **`ALEX_X_001`** | **RISK** | **YES** | hub standardization | **The entire stop/TP/risk/R:R mechanism.** `stopATRBuffer 0.25`, `riskPercent 1.0`, `minRR 2.0` |
| `ALEX_X_002` | ENTRY | YES | engineering necessity | Live entry-delay gate, 5 pips |
| `ALEX_X_003` | ENTRY | YES | engineering necessity | Signal staleness, one bar-period per timeframe |
| `ALEX_X_004` | NO_TRADE | YES | engineering necessity | Activation cutoff |
| `ALEX_X_005` | SETUP | YES | hub standardization | Choppy-zone filter (≥3 penetrations / 50 bars) |
| `ALEX_X_006` | SETUP | YES | hub standardization | Rejection-confirmation window + 0.25 ATR displacement |
| `ALEX_X_007` | SESSION | no | hub standardization | Zero session/day/news filtering (deliberate) |
| `ALEX_X_008` | SETUP | no | experimental | **`ALEX_SCORE_V2` — a second strategy claiming the Alex name**, shadow-only |

`ALEX_X_001` is the one that matters: **every stop, target and position size the engine has ever
placed derives from rules with no source authority.**

## 10. Strategy Knowledge Gaps

| ID | Gap | Completion path |
|---|---|---|
| **`GAP-RISK-001`** | Zero risk rules in the spec; a full risk model in the code | Acquire and approve source material stating stop placement, target selection and sizing. **Do not back-fill from the TI library** |
| **`GAP-TM-001`** | Zero trade-management rules | Same; exit behaviour is entirely unspecified |
| **`GAP-AMBIG-001`** | Zone tightness has no computable definition | Sensitivity testing across `[0.25, 0.5, 0.75, 1.0]` — **requires replay authorization** |
| **`GAP-PROV-001`** | Two unrelated bodies of Alex knowledge must not be merged without a decision | **Engineering Authority decision** — a new milestone if yes |

## 11. Test Results

| Suite | Result |
|---|---|
| `tests/strategy_fidelity/test_strategy_fidelity.py` | **63 / 63 pass** |
| `tests/run_v1027_strategy_fidelity_provenance_tests.js` | **61 executed, 61 pass**, 1 disclosed source-verified note |

**Coverage:** stable serialization/parsing · version handling · all 8 comparison statuses ·
missing/differing/extra/ambiguous · legacy unversioned trades · provenance persistence · trace
generation · deterministic report output · report aggregation · backward compatibility · body-close
vs wick-break · incomplete-candle · missing-context · required-condition rejection · zero-risk
protection · session restrictions.

**Behavioural fixtures call the REAL protected functions** (`alexGEvaluateRepeatedReaction`,
`alexGDetermineTradeDirection`, `alexGZoneRole`, `alexGDetermineFromSide`,
`alexGComputeTrendContext`) rather than restating their logic. **No speculative educator rule is
encoded in any test.**

## 12. Regression Results

| Check | Result |
|---|---|
| `tests/run_all.sh` | **591 / 591 fixtures**, 13 suites, **0 failures**, 0 execution errors (was 530 / 12) |
| Protected-function / constant drift | **ZERO** — 63 functions, 4 constants byte-identical |
| `index.html` diff | **113 insertions, 0 deletions** |
| Python compile | clean |

**Pre-existing, unrelated failures — reported separately, not hidden:**
`tests.trader_intelligence.*` — **307 tests, 4 failures**, identical before and after this milestone:
`test_expected_node_and_edge_counts`, `test_production_evidence_tree_is_still_genuinely_empty`,
`test_production_graph_unchanged_without_real_corpus`,
`test_production_graph_unchanged_without_real_knowledge_library`. All four assert the production
evidence tree is empty — obsolete since the first real transcript ingestion. Confirmed by two
independent runs (307/4 and a 282/3 subset, arithmetically consistent).

## 13. Known Limitations

1. **Per-condition tracing for `ALEX_SR_005` and `ALEX_SR_011` is structurally unreachable.**
   `alexGEvaluateBreakRetest` and `alexGEvaluateRepeatedReaction` are protected **and** their
   `{qualifies:false}` contract discards which condition failed.
2. **Managed and closed positions are untraced** (2 of 7 lifecycle stages) —
   `alexGUpdatePositionExcursionAndCheckExit` and `alexGCloseLivePosition` are protected.
3. **Decision events are memory-only** (500-event cap, zero storage keys). A fidelity report cannot
   be built from historical traces — only live observation.
4. **Fidelity is assessed statically.** No trade has yet been executed and compared against the
   specification; that is replay work, out of scope.
5. **Three rules have no named test** — `ALEX_SR_007`, `ALEX_SR_008`, `ALEX_SR_012`. All three are
   the approximations, where a test would encode the approximation rather than the rule.
6. **Rule classification involved judgement.** The 13 concepts were classified using the artifact's
   own hedging language, recorded per rule with its reasoning — but a reviewer could reasonably
   disagree on `ALEX_SR_007` or `ALEX_SR_012`.
7. **`ALEX_SCORE_V2` was not audited.** It does not paper-trade.

## 14. Open Engineering Decisions

| # | Decision | Why it needs the Authority | Recommendation |
|---|---|---|---|
| **OD-1** | **`GAP-PROV-001`** — should `alex_g_sr_v1` be re-specified against the 195-claim educator library? | Determines whether the specification is 13 concepts or far larger. **Every number in §6 depends on this.** | **Decide first.** Recommend NO for now: the claims are all `emerging` with zero rule candidates, so they cannot support a fidelity baseline yet |
| **OD-2** | `GAP-RISK-001`/`GAP-TM-001` — acquire risk source material, or formally accept the engine as MOGO-authored beyond its source? | Determines whether 0/0 risk fidelity is a defect or a recorded property | Recommend formal acceptance **and** recording it in `ALEX_MANIFEST`, so it is visible outside this report |
| **OD-3** | `FIDELITY-DISC-001` — wire `config.zoneTimeframes` or delete it? | Wiring it touches protected code | Recommend **document, do not touch.** Behaviour is correct; the risk is a future edit, not today |
| **OD-4** | `TRACE-LIM-001` — accept unreachable per-condition tracing, or authorize a protected-function edit? | Only the Authority can authorize protected-code changes | Recommend **accept the limitation.** The trade-off is poor: full re-baselining for observability |
| **OD-5** | `FIDELITY-DISC-004` — record an ADR for the fidelity model? | It has no approved ADR | Recommend **yes** if the model will be depended upon |
| **OD-6** | **AD-8** — is `PARTIAL_PROVENANCE` acceptable as a third class the brief did not name? | I added a class beyond the specified two | Recommend **yes**; if rejected, `PARTIAL` should collapse to `LEGACY_UNVERSIONED`, never to `VERSIONED` |
| **OD-7** | `ALEX_SCORE_V2` — promote, retire, or leave in shadow? | Two strategies claim the Alex name | Recommend an explicit status decision; ambiguity here will confuse every future report |

## 15. Risks

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| **R-1** | **The 9/11 explicit-rule coverage is read as "the engine is 82% faithful."** It is not — it says nothing about risk, which is 0/0. | **High** | **High** | No composite score is emitted; risk fidelity is stated separately; this package leads with the gap |
| **R-2** | The specification is measured against the wrong baseline if OD-1 resolves the other way | Medium | **High** | Nothing has been built on these numbers; OD-1 is first |
| **R-3** | Static fidelity is mistaken for behavioural validation | Medium | High | Execution readiness is `NOT_VERIFIED`; "replay validation performed" is an explicit failed criterion |
| **R-4** | Rules classified `MATCH` are assumed profitable | Medium | High | Profitability is hard-coded `UNVALIDATED` |
| **R-5** | The manifest rots as `index.html` changes | Low | Medium | Symbol resolution at build time; a test asserts zero unresolved references |
| **R-6** | Provenance stamping is assumed to cover historical trades | Low | Medium | Old records untouched; `LEGACY_UNVERSIONED` and `MIXED_VERSION` reported explicitly |
| **R-7** | A future edit to `config.zoneTimeframes` silently does nothing | Low | Medium | `FIDELITY-DISC-001`; OD-3 |
| **R-8** | Classification judgement is treated as objective | Medium | Low | Every classification records its reasoning; limitation 6 discloses it |

## 16. Recommended Next Milestone

**MOGO-002.6 — Fidelity Finding Resolution.** Decision work, not engineering.

**Sequence, and the ordering matters:**

1. **Resolve OD-1 (`GAP-PROV-001`) before anything else.** It determines whether the current
   specification is the right baseline. Resolving it after other work would risk invalidating that
   work.
2. Resolve OD-2 (risk/trade-management gaps) — accept or acquire.
3. Resolve OD-3 through OD-7, which are all independent and low-cost once OD-1 is settled.
4. Only then consider replay engineering, which `GAP-AMBIG-001` genuinely needs.

**Explicitly not recommended now:** changing any ALEX trading rule to improve a fidelity score. The
report contains **zero missing implementations and zero implementation differences** — there is no
fidelity defect to fix. The gaps are in the *specification*, and specifications are not fixed by
editing code.

---

*Prepared by MOGO-002.5. No further implementation will proceed pending Engineering Authority review.*

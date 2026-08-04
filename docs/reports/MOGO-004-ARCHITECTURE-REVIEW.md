# MOGO-004 — Architecture Review

**Session:** MOGO-004 initialization and architecture review · **Date:** 2026-08-03
**Predecessor:** MOGO-003 (`mogo-003-complete`, engine `APP_VERSION` 12.18.0)
**Status:** Review complete. **Nothing implemented. No code, schema, or storage modified.**

> This document is the verbatim record of the six deliverables produced during the MOGO-004
> architecture review, in the order they were produced. The text is reproduced exactly as written;
> only the part dividers, this header, and the contents list below are additive.

## Contents

| Part | Document |
|---|---|
| **I** | Repository Review |
| **II** | Architectural Assessment — Canonical Knowledge Architecture |
| **III** | MOGO Canonical Research Domain Model |
| **IV** | MOGO Permanent Scientific Workflow |
| **V** | ADR-012 Implementation Plan — Canonical Knowledge Architecture |
| **VI** | The MOGO Scientific Success Model |
| **VII** | Independent Review — verification of Parts I–VI |
| **VIII** | Ruthless Reduction — first pass |
| **IX** | Second Reduction Pass |

> **Reading order note.** Parts I–VI are the original architecture review. **Part VII verifies them
> against the repository and finds three factual errors in Parts I–VI, which are NOT corrected in
> place.** Parts VIII–IX then reduce the resulting plan twice. **Where Parts I–VI and Parts VII–IX
> disagree, Parts VII–IX are authoritative.**

---
---

# PART I — REPOSITORY REVIEW

---

# MOGO-004 — Repository Review

## 0. Reading performed

`docs/reports/MOGO-003-CLOSEOUT.md` · `docs/MOGO-004-PLAN.md` · `TESTING.md` · `ARCHITECTURE.md` · `CODING_STANDARDS.md` · `KNOWN_ISSUES.md` · `INCIDENTS.md` · `ROADMAP.md` · ADR-001→011 · `MOGO-003-REPORTING-AUTHORITY.md` · `MOGO-003-VERIFIED-REPLAY-RECORD.md` · `MOGO-RESEARCH-VALIDATION-STANDARD-V1.md` · the trader-intelligence governance set · the ALEX rule-to-evidence join · relevant `index.html` source.

**`AGENTS.md` does not exist in this repository** (nor a `CLAUDE.md`). It was on the required-reading list. Everything else was found.

---

## 1. Repository assessment

### What I verified mechanically, not by reading a claim

| Check | Result |
|---|---|
| `tests/run_all.sh` | ✅ **943/943 fixtures, 17 suites, 0 failures, 0 execution errors** |
| Protected drift | ✅ **Zero** — 63 functions + 4 constants byte-identical |
| `index-v2.9-KNOWN-GOOD.html` | ✅ hash match |
| Python research suites (8 modules) | ⚠️ **451 tests, 6 failures** |

The stated state is accurate **for the JavaScript engine**. The "943/943 passing" headline does not cover the Python research subsystem, and that subsystem is not green.

### The six Python failures

| Module | Test | Failure |
|---|---|---|
| `test_graph` | `test_expected_node_and_edge_counts` | exact-count assertion |
| `test_evidence` | `test_production_evidence_tree_is_still_genuinely_empty` | tree is no longer empty |
| `test_phase1b` | `test_production_graph_unchanged_without_real_corpus` | corpus now real |
| `test_phase7a` | `test_production_graph_unchanged_without_real_knowledge_library` | library now real |
| `test_knowledge_engineering` | `test_all_195_claims_are_inventoried` | `226 != 195` |
| `test_knowledge_engineering` | `test_delta_reports_the_unclosed_risk_gap` | `2 != 0` |

Every one is the failure mode `TESTING.md` §4 already names and warns against — *"Prefer invariants over emptiness… those assertions expire the first time real data is ingested, and they fail in a way that looks like a regression but is not."* The prior session fixed this pattern in three fixtures; these six were missed. They are **not application defects**, but a suite that fails by design trains people to ignore it, and it will mask a real failure the first time one occurs.

`TESTING.md` §4 is also stale: it documents 5 modules / 307 tests. There are now 8 modules / 451 tests.

### The working tree is the largest immediate risk

61 changed or untracked entries, **~134,000 lines of diff**, uncommitted at `mogo-003-complete`:

- The entire rebuilt Knowledge Graph (`edges.json` +89k lines, `nodes.json` +36k, `manifest.json` +9.5k)
- ~7,000 new evidence records (416 items/annotations/links, 641 hypotheses, 341 claims, 4,472 lifecycle records, 325 review-queue entries)
- **`docs/MOGO-RESEARCH-VALIDATION-STANDARD-V1.md`** — 752 lines, the only written replay-authorization gate in the repository, never committed, status *"awaiting Engineering Authority approval"*
- **The entire `docs/trader-intelligence/governance/` directory** — `STATISTICAL-GOVERNANCE.md`, `REPLAY-CAMPAIGN-PLAN.md`, `RESEARCH-ROADMAP.md`, `hypothesis-registry.json` (41), `evidence-gap-matrix.json` (41 rows), `educator-coverage-matrix.json` (5 educators)

This is not scratch work. It is the substantive analytical foundation MOGO-004 is supposed to stand on, and none of it is under version control.

### MOGO-004-PLAN.md is already partly stale

The plan was written at `4f4417d`. The next commit, `656719e`, did a large part of it:

| Plan milestone | Actual state |
|---|---|
| **M2** — resume + finish the ALEX join, add fixtures, commit | ✅ **Done and committed** — 41 rules, 4,761-line artifact, 24 passing tests |
| **M4** — hypothesis testability + metric registry + validation ledger with `REPLAY_EVIDENCE_ONLY` ceiling | ✅ **Done for ALEX's 41 rules** in the same commit; metric registry (6 metrics) and the ceiling both exist |
| **M4** — governance policy | ✅ Written (`STATISTICAL-GOVERNANCE.md`) — **uncommitted** |
| **M3** — replay authorization + campaign design | ✅ Designed (`REPLAY-CAMPAIGN-PLAN.md`, C1–C5) — **uncommitted, unauthorized** |
| **M6** — statistical readiness | Scaffolding exists (`evidence-gap-matrix.json`) — uncommitted |

There are now **two competing plans with conflicting milestone numbering**: `MOGO-004-PLAN.md` (M1 = real-account validation) and `RESEARCH-ROADMAP.md` (M2 = real-account validation, M3 = campaign C1). One must be retired.

### Architecture and boundaries — sound

The protected-code boundary held through ten commits and holds now. The seam pattern (capture installed at non-protected callers, fire-and-forget, own try/catch) is consistently applied. The evidence layer reads trading state and never writes it. Reporting authority ships OFF and is byte-identical when off. The research subsystem's one-directional boundary with the application is real and test-enforced. **This is a well-governed repository — the debt below is almost entirely scientific and process debt, not structural.**

---

## 2. Remaining technical debt

Carried from the closeout, plus what I found:

| # | Item | Severity for MOGO-004 | Notes |
|---|---|---|---|
| T1 | **Nothing since v12.9.0 has been exercised in a browser** | 🔴 **Critical** | Units A, B, C1, C2-M1, C2-M2 — every field the campaign exists to collect — are proven only in an offline harness that has *neither* `crypto.subtle` *nor* `indexedDB`. The 10-item evidence-platform browser checklist in `TESTING.md` is unrun. |
| T2 | **134k-line uncommitted working tree** | 🔴 High | Includes the governance corpus and the validation standard. One `git checkout` mistake loses it. |
| T3 | **6 failing Python tests + stale `TESTING.md` §4** | 🟠 Medium | Anti-pattern the repo already documented; teaches the suite is ignorable. |
| T4 | **Candle duplication** | 🟠 Medium | ~47.6 KB/package. Campaign C1 (~264 trades) ≈ **12.6 MB** of IndexedDB, all duplicated overlapping candles. Not a blocker; is a real quota and export-time concern the campaign plan does not cost. |
| T5 | **No explicit date-range control for replay** | 🟠 Medium | Verified: `fetchCandlesRange(pair, tf, totalCount)` (`index.html:5937`) paginates backward from *now* by candle count. Absolute windows are **discovered and recorded**, never **chosen**. RUN-001's own record concedes "90 days" is a control label, not a sample boundary (its H1 window spans ~131 calendar days). Windows therefore cannot be pre-declared, which is in direct tension with pre-registration. |
| T6 | **Zero transaction-cost model** | 🟠 Medium | `index.html:3755` — spread and slippage "deliberately have ZERO effect"; commission does not exist; a gap through a stop fills at the exact stop price. Replay outcomes are gross of costs and systematically optimistic in gap conditions. Disclosed, not fixed. |
| T7 | **Money-space figures non-reproducible** | 🟢 Low | `pipValuePerLot()` (`index.html:15031`) reads live `pairData`; called by `alexGConstructTrade` at `3802`. Already flagged `DERIVED`/`LIVE_DATA_DEPENDENCY`. On a multi-pair campaign it will return **null** for cross pairs with no loaded conversion rate → `positionSize: null`. **R-space is unaffected**, so this is a "expect it and record it" item, not a blocker. |
| T8 | `AGT\|MANUAL-B\|…` still in storage on `localhost:8899`, inflating that stored balance to 10,200 | 🟢 Low | Quarantined from every statistic; the stored number is uncorrected. Open owner decision. |
| T9 | The **B1 stale claim** | 🟢 Low | Asserted in `MOGO-RESEARCH-VALIDATION-STANDARD-V1.md` (as blocking gate **R10**) and `ALEX-BREAK-RETEST-LOSS-FORENSICS-2026-07.md`; contradicted by RUN-001's own evidence. Low technical impact, **high governance impact** — see S6 below. |
| T10 | 22 historical scratch-only fixture suites (476 fixtures) unreproducible from a clone | 🟢 Low | Long-disclosed. |
| T11 | `RELEASE_NOTES.md` unmaintained across MOGO-003 | 🟢 Low | In-code `APP_VERSION_LOG` is authoritative. |
| T12 | Baseline registry JS arrays manually synced with the Python `PROTECTED_FUNCTIONS` | 🟢 Low | Disclosed; do not refactor. |

---

## 3. Remaining scientific debt

This is where the real work is.

| # | Item | Notes |
|---|---|---|
| S1 | **No setup is validated.** | RZR 16 trades, −1.00R, expectancy −0.0625R. B&R 8 trades, −5.00R, expectancy −0.625R. Overall 24 trades, −6.00R. Neither sample distinguishes an edge from variance in either direction. |
| S2 | **n = 1 across every axis.** | One run, one pair, one window, one educator, one engine build. |
| S3 | **The corpus is untestable.** | **All 641** hypotheses carry placeholder replay tests (552 share one exact string; the other 89 are four further placeholder variants). Only the 41 ALEX join hypotheses are testable-shaped — and their `TESTABLE_NOW` count is **0**: 12 `INSUFFICIENT_SAMPLE`, 6 `UNTESTED`, 4 `NOT_TESTABLE_BY_REPLAY`, 19 `NOT_APPLICABLE`. |
| S4 | **The RUN-001 sample is censored, and nobody has named it.** | 15 of 39 qualified setups were suppressed as `EXISTING_OPEN_TRADE_SAME_PAIR_TIMEFRAME`. Those outcomes are **unobserved, and the suppression is not random** — it correlates with clustering, which correlates with market structure. This is informative censoring: the 24 observed trades are a biased draw from the 39, not a smaller unbiased one. **No governance document I read addresses it**, and it will get worse at multi-pair scale, not better. This is the most under-recognized item in the repository. |
| S5 | **Replay and live are different strategies.** | Both v1.1 gates (`alexGV11EntryDayEligible`, `alexGV11SetupTypePermitted`) live in `alexGEvaluatePairForLiveSetups` — the live path only, unreachable from replay. Confirmed behaviourally in RUN-001: Thu/Fri entries the Mon–Wed gate would block, and 16 RZR trades the suspension would block. **Any replay-versus-live comparison is invalid as currently constructed.** |
| S6 | **The only written replay gate currently says NO.** | `MOGO-RESEARCH-VALIDATION-STANDARD-V1.md` §3.3: *"❌ FAIL — 4 blocking… ALEX v1.1 may not enter replay,"* and §12.2 assigns **SUSPEND FOR DEFECT**. Re-adjudicating each blocker against today's HEAD: **R12 is now closed** (run identity shipped in 12.9.0). **R4 and R8 I verified still hold.** **R10's premise is contradicted** by RUN-001's own evidence. The document is uncommitted and unapproved — but it is the only such gate that exists, and a campaign launched over it without formal re-adjudication is an authorization built on a document that says the opposite. |
| S7 | **Two unreconciled sample-size regimes.** | Validation Standard §9: Tier 2 requires **≥100 decided trades**. Statistical Governance §3: **30 operational** / 100 recommended, with promotion permitted at 30. Both are normative, both uncommitted, and they disagree about what permits a conclusion. |
| S8 | **Five of six bias controls are uncontrolled.** | Look-ahead is genuinely controlled (`alexGValidateTradeNoLookahead` independently re-derives timestamps). Data leakage, selection bias, repeated-holdout, and partitioning are all unaddressed — and T5 makes partitioning currently *impossible*. |
| S9 | **The independence ceiling is 1.** | Review #1 (2026-07-28): after 10 ingestions, 47 → 264 claims, **zero** confidence-state changes, zero rule candidates, zero replays. The maximum independent-group count behind any claim is still 1. **No further transcript ingestion can move any claim to `supported`.** The binding constraint stopped being knowledge around ingestion #4. |
| S10 | **Educator coverage is one deep, four shallow.** | ALEX_G: 9 sources, 226 claims, 41 implemented rules, 24 packages, 1 verified run. TJR: 2 sources, 69 claims, **0 implemented rules**. RAYNER_TEO: 46 claims, **no engine strategy**. ICT: profile only, 0 sources, 0 claims. CRT: **no material exists in the repository at all**. |
| S11 | 6 ALEX rules are `UNRESOLVED` — 4 `NO_EVIDENCE_FIELD_EXISTS`, 2 `FIDELITY_STATUS_UNRESOLVED` | AXR-008, -013, -040, -070 can never be observed without a schema change, which is explicitly out of MOGO-004 scope. Correctly recorded rather than guessed. |
| S12 | Quarantine correctness is unproven on real history | Verified on fixtures and the recovered INC-005 record only. A false positive would silently distort every statistic computed afterwards. |

---

## 4. Highest ROI milestone

**I recommend diverging from the campaign plan's C1-first ordering.**

`REPLAY-CAMPAIGN-PLAN.md` ranks **C1 (11 majors, 11 runs, ~264 trades)** as highest ROI, and on information-per-authorization it is right. But it spends **eleven** authorizations on an evidence-capture pipeline that **has never once been observed running in a browser** (T1). Units A/B/C1/C2 — rule attribution, excursion timing, market context, the exact fields the campaign exists to obtain — are proven only in a harness with no `crypto.subtle` and no `indexedDB`. If any of them fails to populate under real conditions, C1 yields 264 packages missing precisely the data that justified collecting them, and the failure is discovered after the spend, not before.

### The recommendation: an instrumented pilot run

> **MOGO-004 M-A — Pilot Replay & Browser Verification.**
> **One** authorized replay: re-run RUN-001's exact window on EUR_USD on the current engine (campaign **C3**), executed under the mandatory disposable-profile isolation of `TESTING.md` Rule 0, with the full 10-item evidence-platform browser checklist discharged in the same session.

One run, ~24 trades, and it retires more risk than any other single action available:

1. **Discharges the largest verification gap in the repository** — IndexedDB persistence, in-browser SHA-256 against NIST vectors, the export→re-import→verify cycle, quota handling, sequence continuity across reload. All ten checklist items, none of which is offline-provable.
2. **Proves the campaign's premise before it is funded.** Confirms Units A/B/C1/C2 actually populate `triggeredConditions`, `timeToMFE`/`timeToMAE`, and market context on real data.
3. **Converts the existing 24 trades from uncitable to rule-level citable.** Identical window, identical dataset — the *only* variable is engine version, so the two runs are directly comparable and any difference is attributable.
4. **Independently re-validates the engine.** RUN-001's exact window on a newer build should reproduce 24 trades at −6.00R. If it does not, that is a determinism finding worth more than the entire campaign.
5. **De-risks C1's operational unknowns cheaply** — package size at scale, export batch behaviour (the EXP-001 partial-write mode already bit once at 24 files), `pipValuePerLot` null-handling.

**Preconditions, both cheap (hours, not days):**
- **Commit the working tree.** Governance corpus, validation standard, graph rebuild. Non-negotiable before any new work.
- **M1 real-account validation** — one page load, Diagnostics → Ledger Reconciliation, read-only, on the real ALEX and JVM accounts. Settles S12. `MOGO-004-PLAN.md` is right that this blocks nothing technically and everything interpretively.

**Then, and only then, C1.** Sequence becomes: **stabilize → M1 → pilot (C3) → C1 → adjudication → readiness report.**

---

## 5. Risks

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R1 | **Sample never reaches significance.** Both setups are currently negative; the campaign may simply establish that more precisely. | 🔴 High | State it plainly. `REJECTED` and `INSUFFICIENT` are both real results. Do not lower a threshold to manufacture a conclusion. |
| R2 | **Capturing 264 packages with a defect discovered afterwards.** | 🔴 High | The pilot run in §4 exists specifically for this. |
| R3 | **Replay authorization not granted.** | 🔴 High | Stabilization, M1, hypothesis work and the readiness report all proceed without it. C1/C3 and TJR stall. |
| R4 | **Informative censoring (S4) silently biases every result.** | 🔴 High | Quantify suppression rate per setup per run as a first-class campaign output. If suppression exceeds ~20%, no comparison is interpretable without addressing it. **Currently unaddressed anywhere.** |
| R5 | **Governance contradiction (S6/S7) surfaces after results exist**, and threshold selection then looks post-hoc. | 🟠 Medium | Re-adjudicate the Replay Readiness Gate and reconcile the two sample regimes **before** the pilot, in writing, committed. |
| R6 | **INC-004 recurrence.** Any browser work touches the mechanism that destroyed real trading data on 2026-07-31. | 🔴 High | `scripts/browser_test_profile.sh` only. Origin confirmed with the operator, never inferred. Pre-clear inventory logged. If isolation cannot be positively verified, the run does not happen. |
| R7 | **Quarantine false positives distort samples.** | 🟠 Medium | M1 settles this before any statistic is computed. |
| R8 | **Multiple-comparison error across 41 hypotheses.** ~2 false positives by construction at 5%. | 🟠 Medium | Pre-register before analysing; Holm–Bonferroni across the family; report family size with any promotion. Already policy — the risk is that it is uncommitted policy. |
| R9 | **Scope creep back into infrastructure.** T4/T5/T6 are all genuinely tempting and all genuinely out of scope. | 🟠 Medium | The §2 boundary is the test: if it changes a package field, it is not MOGO-004. Record and defer. |
| R10 | **Cost model (T6) makes any near-zero expectancy uninterpretable.** | 🟠 Medium | State "gross of all costs" on every reported figure. At 1–2 pips against a 20–40 pip stop, costs are 3–10% of risk per round turn. |
| R11 | **Educator expansion produces breadth without depth.** TJR needs setup detection *and* replay before it produces one package. | 🟠 Medium | One educator fully to standard beats three partially. Sequence TJR after ALEX proves end-to-end. |
| R12 | **Working-tree loss.** | 🟠 Medium | Commit first. |

---

## 6. Success criteria

MOGO-004 succeeds if **all** of the following are true at closeout:

**Verification**
1. `tests/run_all.sh` green; zero protected drift; 63 functions + 4 constants byte-identical throughout.
2. Python suites green — the six emptiness assertions converted to invariants, not deleted or skipped; `TESTING.md` §4 counts corrected.
3. The 10-item evidence-platform browser checklist **fully discharged and recorded**, under verified profile isolation, with a pre-clear inventory logged and zero contamination of real paper-trading data.

**Evidence**
4. Every new run is in the verified replay register with `runId`, `datasetHash`, `configHash`, `paramsHash`, observed absolute window, ADR-011 completeness state, and hash-verified packages.
5. Every new package carries rule attribution, excursion timing and market context — **demonstrated, not assumed**.
6. Suppression counts reported per run per setup, and the censoring effect on interpretability stated explicitly.
7. RUN-001's 24 packages remain byte-identical. Nothing backfilled, ever.

**Science**
8. Thresholds (30 / 100 / 0.25R) confirmed by the owner and **committed before evidence is collected**.
9. The Replay Readiness Gate formally re-adjudicated against HEAD, in writing, with each of R4/R8/R10/R12 individually resolved.
10. The two sample-size regimes (Standard §9 vs. Governance §3) reconciled into one.
11. Every adjudicated hypothesis reports an interval, not a point estimate; family size stated; Holm–Bonferroni applied.
12. No rule promoted above `REPLAY_EVIDENCE_ONLY` on replay evidence alone, at any sample size.
13. For every ALEX rule: *supported*, *rejected*, or *here is exactly what is missing*. **Mostly the third is an acceptable outcome.**

**Boundaries**
14. Zero protected-function changes. Zero replay behaviour changes. Zero package-schema changes. Zero strategy-rule, threshold or sizing changes.
15. RZR remains suspended. No strategy approved for live execution. No live trading, no optimization, no curve fitting.

**Explicit non-criteria:** a positive expectancy, a validated setup, or a promotion. If the evidence does not support one, producing one is the only way this project fails.

---

## 7. Estimated implementation scope

| Phase | Work | Scope | Dependency |
|---|---|---|---|
| **0 — Stabilization** | Commit the working tree; retire the duplicate roadmap; convert 6 emptiness tests to invariants; correct `TESTING.md` §4; create the missing `AGENTS.md` | **Small** — hours | None |
| **1 — Governance reconciliation** | Re-adjudicate the Replay Readiness Gate against HEAD (R4/R8/R10/R12); reconcile Standard §9 with Governance §3; correct the B1 claim in both documents; owner confirms thresholds **in advance** | **Small–Medium** — 1 session | Owner decisions #2, #3 |
| **2 — M1 real-account validation** | One page load, read-only, Diagnostics → Ledger Reconciliation on real ALEX and JVM | **Trivial to execute, high interpretive value** | Operator at the keyboard |
| **3 — Pilot replay + browser verification** ⭐ | One authorized C3 run under disposable-profile isolation; all 10 checklist items; register entry; comparison against RUN-001 | **Medium** — 1–2 sessions, dominated by careful browser procedure | **Replay authorization** (decision #1) |
| **4 — Campaign C1** | 11 majors, 90-day control, one run each; ~264 trades; register entries; suppression accounting | **Large** — the bulk of MOGO-004; ~12.6 MB of packages; gated on Phase 3 | Phase 3 clean |
| **5 — Hypothesis adjudication** | Pre-registered comparisons under governance; Holm–Bonferroni; intervals; `REPLAY_EVIDENCE_ONLY` ceiling | **Medium** — machinery exists and is idle | Phase 4 |
| **6 — TJR to ALEX standard** | Rule register → fidelity matrix → join. **Needs setup detection *and* replay before one package exists** — larger than it appears | **Large** — realistically its own milestone | Decision #2; Phase 5 |
| **7 — Statistical readiness report** | Per strategy, per setup: sample, answerable, unanswerable | **Small** | Everything above |

**Overall:** Phases 0–3 are a genuinely small, high-value block deliverable quickly. Phase 4 is the bulk. **Phase 6 (TJR) is the item most likely to overrun** — the plan treats it as "mirror the ALEX deliverables," but TJR has 0 implemented rules and no replay path, so it is a build, not a port. I would recommend deferring it to MOGO-005 unless the owner specifically wants breadth this cycle.

**Out of scope, confirmed:** sizing authority · enabling derived reporting · content-addressed candle store · untraded-candidate context · decision chains · any schema change · any strategy-rule change · any live-execution approval. The four `NO_EVIDENCE_FIELD_EXISTS` rules stay recorded and unobservable — that is MOGO-005.

---

## Open decisions needed before I start

1. **Replay authorization** — how many runs, which pairs, which windows? I recommend authorizing **one pilot run first** (§4), then deciding on C1.
2. **Second educator** — TJR confirmed, or defer to MOGO-005? *(Note: CRT has no material in this repository at all.)*
3. **Thresholds** — confirm 30 operational / 100 statistical / 0.25R **now**, before evidence exists, so they cannot be rationalized afterwards.
4. **The stored 8899 balance** — corrected, or retained as a forensic artifact?
5. **Sequencing** — do you accept pilot-before-campaign, or do you want C1 as the campaign plan ranks it?

**Awaiting approval. Nothing will be implemented until you give it.**

---
---

# PART II — ARCHITECTURAL ASSESSMENT

---

# Architectural Assessment — Canonical Knowledge Architecture

## 0. Headline verdict

**Yes, this is an architectural decision, not an implementation detail** — but not for the reason stated in the proposal, and not in all six of its parts.

Of the six implications:

| | Implication | Actual status |
|---|---|---|
| 1 | Knowledge acquisition first, no conclusions during acquisition | ✅ **Already built and enforced** — this is the existing pipeline |
| 2 | Educators become sources attached to concepts | ⚠️ **Half already ratified** — `DECISION\|MOGO\|20260727\|004` (status `active`) already decided educator equality; the *concept* half is new |
| 3 | Hypotheses educator-independent | 🔴 **Genuinely architectural — and currently forbidden by schema** |
| 4 | Replay consumes hypotheses | ✅ **Already written policy**, unenforced — needs a mechanism, not a decision |
| 5 | Statistical promotion on predefined criteria | ✅ **Already written policy**, with a real schema gap |
| 6 | Canonical Knowledge Graph answering six questions | 🔴 **Genuinely architectural — and blocked by something the proposal does not name** |

**The most important finding in this review is item 6, and the proposal misdiagnoses it.**

---

## 1. The gap the proposal does not name

I enumerated the Knowledge Graph's actual node types from the committed build:

```
CLAIM 341 · CONTRADICTION_RECORD 16 · EVIDENCE_ITEM 416 · EVIDENCE_QUESTION 281
EVIDENCE_SOURCE 12 · HYPOTHESIS 641 · INTAKE_MANIFEST 12 · KNOWLEDGE_GAP 110
OWNER_DECISION 6 · REVIEW_QUEUE_ENTRY 325 · STRATEGY_BLUEPRINT 11
STRATEGY_FAMILY 3 · TRADER 5 · TRADER_PROFILE 11 · TRANSCRIPT_SEGMENT 197
UNRESOLVED_QUESTION 35
```

**There is no `EVIDENCE_PACKAGE` node. No `REPLAY_RUN`. No `REPLAY_CAMPAIGN`. No `STRATEGY_RULE` instance.**

The Knowledge Graph and the Evidence Platform are **two architecturally disjoint systems**. The graph knows what educators said. The evidence platform knows what the engine did. Nothing structural connects them. `alex-rule-evidence-join.json` — the 4,761-line artifact committed at `656719e` — is a **flat, point-to-point adapter file generated by a Python script**, not a graph traversal. It is a bridge built by hand across a gap that the architecture does not model.

Now test the proposal's own six target questions against that:

| § 6 question | Blocked by missing concepts? | Blocked by the graph/evidence disjunction? |
|---|---|---|
| Which educators teach this concept? | ✅ **Yes** | No |
| Which hypotheses depend on it? | ✅ **Yes** | No |
| Which replay campaigns tested it? | Partly | ✅ **Yes — decisive** |
| What evidence supports it? | Partly | ✅ **Yes — decisive** |
| What evidence contradicts it? | Partly | ✅ **Yes — decisive** |
| What is the current statistical confidence? | No | ✅ **Yes — decisive** |

**If you built the entire concept layer and changed nothing else, four of the six questions would remain unanswerable.** The concept registry fixes the *knowledge-side* questions. The graph/evidence bridge fixes the *validation-side* questions — and the validation side is what MOGO-004 exists to serve.

This does not refute the proposal. It reorders it. **The canonical concept layer is the right long-term shape; the graph-to-evidence bridge is the higher-priority half of the same architecture, and the proposal treats it as a downstream consequence rather than a peer.**

---

## 2. Question-by-question

### Q1 — Should canonical concepts become first-class entities?

**Yes — with one hard constraint, and the timing trigger has now fired.**

This is not a new idea in the repository. `PROPOSAL-003 — Concept Registry` already specifies it in detail: a `Concept` record, `traderTerminology[]`, `relatedConceptIds`/`distinguishedFromConceptIds`, four new graph edge types. It was **deferred by ADR-008 and re-affirmed as deferred** in `EVIDENCE_INTELLIGENCE.md` §589.

The deferral was conditional. `PROPOSAL-003` §6 recommended **Option 2: defer until source #3, then build and backfill**, and rated **Option 3 (defer indefinitely) as ROI-negative beyond ~3 sources**.

There are now **12 sources across 5 educators** (ALEX_G 9 sources / 226 claims; TJR 2 / 69; RAYNER_TEO 1 / 46; ICT 0; CRT nothing). **The deferral condition expired some time ago.** The proposal is, in effect, a request to execute a decision the repository already recommended and then didn't action.

The three failure modes it fixes are real and are actively degrading the library today:

- **F1** — same idea, different words, same trader → two `emerging` claims instead of one `supported`. This **actively suppresses confidence**, and Review #1's headline finding (max independent-group count = 1 after 10 ingestions) is at least partly F1 in action.
- **F2** — same word, different concepts, across traders → silent conflation.
- **F3** — no cross-trader comparison possible. `CROSS-STRATEGY-ANALYSIS.md` exists but is hand-maintained prose, not a queryable structure.

**The hard constraint, taken directly from `PROPOSAL-003` §4 and §5, which I endorse:**

> **A concept is a navigation and identity layer. It is never an evidence type, never citable as a trader's claim, and never an input to confidence scoring.**

The proposal's phrasing — *"normalize equivalent terminology across educators"*, *"treat concepts as permanent entities"* — drifts toward exactly the coupling `PROPOSAL-003` rejected. If two claims corroborate each other **because an operator mapped them to the same concept**, then confidence becomes a function of an editorial taxonomy edit rather than of stored evidence links. That is a real weakening of the one property `POLICY-001` depends on. Corroboration must continue to run through `EvidenceClaimLink.independenceGroup` — an explicit, operator-set, audit-trailed field — never implicitly through concept identity.

**Uncomfortable consequence you should weigh:** if concepts are correctly barred from driving corroboration, then **the concept registry does not fix the binding constraint.** It improves navigation, cross-educator querying, and operator onboarding. It does not produce validated knowledge. Only evidence volume does that. Anyone selling the concept layer as the fix for "zero confidence movement in ten ingestions" is overselling it.

### Q2 — Should educators become evidence sources instead of organizational units?

**Already decided. `DECISION|MOGO|20260727|004`, `decisionType: architectural`, `status: active`.**

> *"Treat ICT, TJR, JVM, Alex G, and all future educators as equal evidence sources, subject to the same extraction, provenance, and confidence rules."*

That decision goes further than the proposal does. It explicitly states that **MOGO's own strategies are not exempt** — that a repository-confirmed implementation fact is *evidence about MOGO's code, not evidence about any trader's method*, and that JVM's and ALEX's `externalResearchStatus: 'not_started'` is a genuine gap rather than an artifact of ordering.

So the *principle* is ratified. What is **not** done is the *structure*. The graph still carries `BELONGS_TO_TRADER` with **535 edges** and `TRADER` as a first-class node type with 5 instances. Educators are still the organizing spine in practice. The proposal's request is therefore: **finish implementing a decision already taken.** That is a much easier authorization than a new architectural choice.

**But there is a boundary here that must not be crossed, and the proposal walks right up to it.**

### ⚠️ The KEREV-B problem — the most serious risk in this proposal

`ALEX-CANONICAL-RULE-REGISTER.md` carries this scope warning:

> *"This is an audit view over the ALEX_G educator claim library. It is **not** a specification, it is **not approved**, and it **does not merge** with `alex_g_sr_v1`, whose rules are MOGO's own (`DECISION|MOGO|20260727|004`, KEREV-B)."*

And the join artifact's own `lineageWarning`:

> *"alex_g_sr_v1's rules are MOGO's own... any agreement below is **CONVERGENCE, NOT DERIVATION**. This matrix does not re-specify the production strategy and does not merge the two bodies of knowledge (**KEREV-B remains open**)."*

**A single "Canonical Rule Library" spanning educators and MOGO's own implemented rules is precisely the merge that KEREV-B has not authorized.** The register's own numbers show why this matters: of 41 canonical ALEX rules, **9 are `UNSUPPORTED` — no rule exists in any source** — and the join classifies **7 as MOGO-authored with no educator support**. Those are MOGO's inventions.

Collapse educators into "sources attached to concepts" without a `provenanceClass` discriminator, and within two years nobody will be able to tell which canonical concepts came from an educator and which MOGO invented and then convergently attributed. **That is knowledge laundering, and it is irreversible once the distinction is lost.**

**Mandatory guard:** every canonical rule and concept must carry an explicit, non-nullable provenance class — `EDUCATOR_ASSERTED` / `MOGO_AUTHORED` / `CONVERGENT` — enforced at schema level with an integrity check, exactly the way `Concept.definition` must be flagged MOGO-authored. And **ADR-012 must state that it does not resolve KEREV-B**, or KEREV-B must be resolved first, explicitly, by the Engineering Authority.

### Q3 — Should replay campaigns consume hypotheses rather than create them?

**Yes — and this is already written policy that lacks a mechanism.**

`STATISTICAL-GOVERNANCE.md` §4 already says it, in stronger language than the proposal:

> *"**Pre-register.** A hypothesis must exist in the registry with its metric and thresholds *before* the evidence that tests it is analysed."*
> *"**No post-hoc hypotheses.** A pattern noticed in existing data becomes a *new pre-registered* hypothesis awaiting *new* evidence — never a conclusion drawn from the data that suggested it."*

So Q3 needs no architectural decision. It needs an **artifact**: a `ReplayCampaign` record that declares, before execution, which hypothesis IDs it exists to answer, with the thresholds frozen at declaration time and hashed. Without that artifact, "pre-registered" is an honour system, and honour systems fail silently and unfalsifiably.

**My challenge to this item — strict consumption forecloses discovery, and MOGO has already benefited from discovery.**

RUN-001's single most valuable output was not a hypothesis test. It was a **discovery**: the "B1 stale claim" — that the frozen zone engine could never produce a validated never-broken resistance zone — was contradicted by the run's own evidence (8 validated never-broken resistance zones, 3 `upThroughResistance` breaks). Nobody pre-registered that. Under a strict *"replay only consumes hypotheses"* rule, that finding has no legal home, and a document asserting a falsehood stays uncorrected.

**Recommendation:** design it as **two channels, never mixed**, rather than as a prohibition:

- **Confirmatory channel** — pre-registered hypotheses only, Holm–Bonferroni across the declared family, promotion-eligible.
- **Exploratory channel** — anything the run reveals. **Never promotion-eligible.** Its only legal output is a *new* pre-registered hypothesis awaiting *new* evidence, or a factual correction to a repository document.

The governance policy already implies this; the architecture should make it structural, so an exploratory finding cannot be silently reclassified as confirmatory after the fact.

### Q4 — Does this philosophy belong in `AGENTS.md`?

**No. And I'd push back on this one specifically.**

Three reasons:

1. **`AGENTS.md` does not exist.** Creating it *as* a philosophy document sets its precedent wrongly and permanently.
2. **Philosophy in an operational file is the failure mode this repository already has.** In §1 of my prior review I found: two competing roadmaps with conflicting milestone numbering; two unreconciled sample-size regimes (Standard §9 = 100 trades, Governance §3 = 30); and — I found this while checking the schema — **two competing hypothesis status vocabularies**, one in `hypothesis.schema.json` (`PROPOSED_UNVALIDATED`/`UNDER_RESEARCH`/`SUPPORTED`/`REFUTED`/`WITHDRAWN`) and a different one in the join (`UNTESTED`/`INSUFFICIENT_SAMPLE`/`TESTABLE_NOW`/`NOT_TESTABLE_BY_REPLAY`/`NOT_APPLICABLE`). Adding a fourth normative surface makes this measurably worse.
3. `CODING_STANDARDS.md` already establishes the pattern: hard rules live in one place and every other document *links* to it.

**Recommendation:** `AGENTS.md` should exist, and should be a **thin operational index** — where the hard rules are, what to run before shipping, what is protected, which decisions are open. It should contain **one paragraph** on the knowledge architecture and a link to the ADR. The philosophy itself belongs in the ADR, with `ARCHITECTURE.md` carrying the summary.

### Q5 — Should this become a formal ADR?

**Yes. Unambiguously. This is the clearest yes in the review.**

It meets every criterion the repository's own ADR practice uses: it is hard to reverse, it changes entity identity, it constrains all future work, and — decisively — **it requires a schema change to a required field** (Q6 below). ADR-005 (strategy framework) and ADR-008 (evidence engine) were written for materially smaller decisions.

**Proposed: `ADR-012 — Canonical Knowledge Architecture.`** It must explicitly:

- Supersede or extend **ADR-008 §14** (the two-generation schema coexistence)
- **Resolve `PROPOSAL-003`** — accept, with the phase-A constraint that concepts never enter confidence scoring
- Declare the `provenanceClass` discriminator as a hard rule
- **State its relationship to KEREV-B** — either "does not resolve" or "requires resolution first"
- Define the `ReplayCampaign` entity and the confirmatory/exploratory two-channel rule
- Define the graph-to-evidence bridge: `EVIDENCE_PACKAGE` and `REPLAY_RUN` as node types
- Reconcile the two hypothesis status vocabularies into one

### Q6 — Which governance documents should permanently incorporate it?

| Document | Change | Why |
|---|---|---|
| **`ADR-012`** (new) | The decision itself | Source of record |
| **`ARCHITECTURE.md`** | New section; revise the Trader Intelligence section | Currently describes three layers (acquisition/evidence/graph); becomes four with the canonical layer |
| **`AGENTS.md`** (new) | One paragraph + links | Operational index only |
| **`MOGO-RESEARCH-VALIDATION-STANDARD-V1.md`** | §2 lifecycle stages 2–4 and 10–11 | The 12-stage lifecycle is currently educator-rooted; must become concept-rooted. **Also still uncommitted and unapproved.** |
| **`STATISTICAL-GOVERNANCE.md`** | §4 pre-registration → reference the `ReplayCampaign` record | Gives the policy a mechanism |
| **`docs/trader-intelligence/README.md`** | "Which entity model do I use?" table | Already flagged in-file as *"the single most common point of confusion"*; a fourth layer without it will be worse |
| **`STANDARDS-extraction.md`** | Concept assignment at annotation time | `PROPOSAL-003` §6: the cheapest moment to assign a concept is at annotation, never later |
| **`SPEC-provenance.md`** | The `provenanceClass` discriminator | Where the KEREV-B guard is actually enforced |
| **`GLOSSARY.md`** | Becomes generated from the concept registry | Currently 572 hand-maintained lines that will immediately diverge |
| **`EVIDENCE_INTELLIGENCE.md`** §589 | Reverse the concept-registry deferral | It is the document that re-affirmed the deferral |
| **`PROPOSAL-003`** | Mark resolved by ADR-012 | Close the loop |
| **`TESTING.md`** §4 | Integrity checks for the new constraints | Concepts-never-scored and provenance-class must be test-enforced, not convention |

### Q7 — Roadmap impact, preserving all of MOGO-003

**Every MOGO-003 component survives untouched. The change is purely additive.** I checked each:

| MOGO-003 deliverable | Impact |
|---|---|
| Evidence Platform, `mogo.evidence-package.v1` | **None** — no schema change. Packages gain a graph node *referencing* them; the packages themselves are never rewritten |
| Replay Identity (`runId`/`datasetHash`/`configHash`) | **None** — becomes the natural primary key for the `REPLAY_RUN` node. This architecture is what run identity was *for* |
| Units A / B / C1 / C2 | **None** — capture is unchanged |
| Trade Integrity, Immutable Ledger, Reconciliation, Reporting Authority | **None** — different subsystem entirely |
| 63 protected functions + 4 constants | **None** — this is documentation and research tooling; it cannot reach protected code |
| RUN-001's 24 packages | **None** — immutable, byte-identical, never backfilled |
| The rule-to-evidence join (`656719e`) | **Reframed, not discarded** — it stops being a hand-built adapter and becomes a *generated projection* over graph edges. Its 24 tests and its `UNRESOLVED` register carry forward intact |

The roadmap shift is one of **sequencing and framing**, and it is smaller than it looks:

- **M2 (join) is already done** — and under this architecture it is the prototype of the bridge, which strengthens the case rather than invalidating it.
- **M4 (hypothesis testability)** stops being ALEX-scoped. Its metric registry and `REPLAY_EVIDENCE_ONLY` ceiling become the canonical layer's property rather than one educator's.
- **M5 (TJR)** changes character most: no longer "port the ALEX deliverables to TJR" but "map TJR's claims onto shared concepts, and observe which concepts two educators independently assert." **That is a materially better milestone** — it produces cross-educator structure, which is the one thing more ALEX evidence can never produce.
- **M3 (replay campaigns)** gains a required precondition: a `ReplayCampaign` declaration.
- **M6 (readiness report)** becomes a graph query rather than a written document.

**What I would not do:** allow this to displace the pilot replay. My §4 recommendation stands unchanged — **nothing since v12.9.0 has been exercised in a browser**, and no amount of knowledge architecture fixes that. The two workstreams are genuinely independent: one is documentation and Python tooling, the other is browser verification. They can proceed in parallel without contention, and the architecture work is a good use of any period during which replay authorization is withheld.

### Q8 — Does it better support long-term research, reproducibility, expansion, and evidence quality?

Honestly, and separated rather than answered as one question:

| Dimension | Verdict |
|---|---|
| **Educator expansion** | ✅ **Strong yes.** This is the clearest win. Adding educator #3 currently costs a full parallel stack. Under concepts, the marginal educator attaches to existing concepts, and — crucially — **each new educator increases the independent-group count on concepts that already exist**, which is the only mechanism that can raise confidence |
| **Long-term scientific research** | ✅ **Yes.** Hypotheses become durable objects that outlive the educator that suggested them. That is what a research OS means |
| **Reproducibility** | 🟡 **Yes for knowledge lineage; no change to result reproducibility.** Concepts make it reproducible *why* a hypothesis exists. They do nothing for T5 (no explicit date-range control), T6 (zero cost model), or T7 (money-space live-data dependency). Those remain exactly as they were |
| **Evidence quality** | 🟡 **Improves organization and queryability; does not improve the evidence.** RUN-001 stays 24 trades. RZR stays −1.00R. B&R stays −5.00R |
| **The binding constraint (independent groups = 1)** | 🔴 **Not fixed, if built to `PROPOSAL-003`'s correct design.** Concepts barred from driving corroboration cannot raise the independence ceiling directly. Only new independent sources and new replay evidence do |

---

## 3. The item that is currently illegal

**Proposal #3 — *"Every hypothesis must be educator-independent"* — cannot be implemented as stated, and if implemented literally would destroy provenance.**

From `evidence/schema/hypothesis.schema.json`:

```json
"sourceClaimIds": {
  "type": "array",
  "minItems": 1,
  "items": { "type": "string", "pattern": "^CLAIM\\|" }
}
```

`sourceClaimIds` is **required with `minItems: 1`**, and every `CLAIM` reaches an educator through `BELONGS_TO_TRADER`. **A hypothesis structurally cannot exist today without at least one educator claim.** All 641 are educator-derived by construction. This is a hard schema constraint on a required field — which is exactly why the proposal is architectural rather than cosmetic.

Two consequences:

**First, a real gap this exposes.** There is currently **no legal representation for a MOGO-authored hypothesis.** Yet the join identifies **7 MOGO-authored ALEX rules with no educator support**, and the register finds **9 canonical rules where no source states any rule at all**. Those questions exist and are being tracked *outside* the hypothesis system because the schema won't hold them. That is a genuine argument for the proposal, independent of concepts.

**Second, the fix must not be to drop the linkage.** Removing `sourceClaimIds` would produce hypotheses with no traceable origin, violating the validation standard's own stage-2 gate (*"100% of claims trace to an excerpt"*). The correct form is:

> **Hypothesis identity anchors to a concept. Educator claims attach as many-to-many supporting provenance, which may legitimately be empty when `provenanceClass = MOGO_AUTHORED`.**

That decouples identity from the educator while *strengthening* provenance — because it forces MOGO-authored hypotheses to declare themselves rather than hide as educator-derived.

**A second schema defect, found while checking this.** `hypothesis.status` is `PROPOSED_UNVALIDATED | UNDER_RESEARCH | SUPPORTED | REFUTED | WITHDRAWN`. The proposal's implication 5 requires that *"unsupported hypotheses remain unresolved rather than promoted or discarded"* — **and the schema has no state for that.** A hypothesis tested at insufficient sample must currently be parked in `UNDER_RESEARCH` (misleading — it may be permanently untestable) or `WITHDRAWN` (wrong — it wasn't). Worse, `SUPPORTED` exists with **no evidence-class ceiling enforcement**, so nothing at schema level prevents a hypothesis reaching `SUPPORTED` on replay evidence alone, in direct violation of `STATISTICAL-GOVERNANCE.md` §6. The join worked around this by inventing its own parallel vocabulary. **That divergence is itself evidence the current schema is the wrong shape**, and it supports the proposal on its own merits.

---

## 4. Advantages, tradeoffs, risks, weaknesses

### Advantages

1. Fixes F1/F2/F3, which are actively degrading the library at 12 sources.
2. Makes the marginal educator cheap — the single biggest structural constraint on expansion.
3. Gives MOGO-authored knowledge a legal, self-declaring home instead of an invisible one.
4. Turns `CROSS-STRATEGY-ANALYSIS.md` and `GLOSSARY.md` from hand-maintained prose into generated projections.
5. Makes hypotheses durable objects that survive the educator that suggested them.
6. Forces the graph/evidence bridge to be built properly rather than as a per-milestone adapter script.
7. `runId`/`datasetHash` already provide exactly the identity the bridge needs — the hard part is done.

### Tradeoffs

1. **Editorial judgment enters the system.** Someone decides "liquidity sweep" and "stop hunt" are one concept. Contained only if concepts never touch scoring.
2. **Backfill cost** across 341 claims and 641 hypotheses. Bounded and mechanical, but real, and `PROPOSAL-003` §6 correctly notes it grows without bound.
3. **A fourth entity layer** in a README that already calls its three-layer model *"the single most common point of confusion."*
4. **Slower ingestion** — concept assignment is per-claim operator work.
5. **Taxonomy is a permanent maintenance surface.**

### Risks

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| A1 | **Knowledge laundering** — MOGO's 7 authored rules become indistinguishable from educator-asserted knowledge; KEREV-B resolved by accident | 🔴 **Highest** | Non-nullable `provenanceClass`, integrity-check-enforced. ADR-012 states its KEREV-B relationship explicitly |
| A2 | **Concepts leak into confidence scoring**, making promotion a function of taxonomy edits | 🔴 High | `PROPOSAL-003` §4: navigation layer only. Test-enforced, not convention |
| A3 | **Displacement** — the architecture becomes the work, and evidence volume (the actual binding constraint) stalls behind it | 🔴 High | Run in parallel with the pilot replay; never let it gate authorization |
| A4 | **Taxonomy bikeshedding** | 🟠 Medium | Seed only from concepts already appearing in real claims; forbid speculative concepts |
| A5 | **Scope creep into the evidence-package schema** — the bridge "needs one more field" | 🟠 Medium | MOGO-004 §2's boundary test: if it changes a package field, it is not MOGO-004 |
| A6 | **Fifth normative surface**, worsening existing document drift | 🟠 Medium | One ADR; everything else links |
| A7 | Big-bang migration destabilizes a working graph build | 🟠 Medium | Additive node/edge types, mirroring how Phase 7A added four. Build is deterministic and re-derivable |

### Weaknesses in the philosophy as written

1. **It presents the lifecycle as linear** — Educator → Extraction → Library → Registry → Campaign → Packages → Validation → Approved Knowledge. **Real research is a loop.** RUN-001 produced a finding that should flow *backwards* and correct a document. A strictly linear pipeline has no return edge, and the repository has already needed one.

2. **"Educator-independent" is stated too strongly** and, read literally, deletes provenance. It should read *"educator-independent in identity, educator-traceable in provenance."*

3. **It omits the graph/evidence bridge** — the half that actually unblocks four of its own six target questions.

4. **It implies concepts fix confidence.** They don't, if built correctly. Evidence volume does. Stating this plainly now prevents disappointment in six months when the concept layer ships and every claim is still `emerging`.

5. **It doesn't address the informative-censoring problem (S4).** No knowledge architecture makes a censored sample interpretable. That remains the deepest unaddressed *scientific* issue, and it is orthogonal to all of this.

---

## 5. Recommendation

**Adopt the philosophy. Write `ADR-012`. Do not let it displace the pilot replay.**

Specifically:

1. **Yes** to concepts as first-class, with `PROPOSAL-003`'s phase-A constraint intact.
2. Educator-as-source is **already ratified** — implement, don't re-decide.
3. **Yes** to campaigns consuming hypotheses, as a two-channel design with an exploratory escape hatch.
4. **No** to philosophy in `AGENTS.md`; create it as a thin operational index.
5. **Yes** to ADR-012 — this is the clearest yes here.
6. The twelve documents in Q6.
7. Roadmap reframed, not rewritten. **Every MOGO-003 component survives untouched.**
8. **Strong yes** for expansion and long-term research; **partial** for reproducibility; **no material change** to the binding constraint.

**Two things I would require before ADR-012 is written**, because both are cheap and both become expensive if deferred:

- **Resolve or explicitly scope KEREV-B.** A canonical library that merges educator and MOGO-authored rules without that resolution is the one decision here that cannot be walked back.
- **Commit the working tree first.** The validation standard, the governance corpus, and the graph rebuild are 134k lines of uncommitted work that this architecture would build directly on top of.

**Nothing has been implemented. No code, schema, or document was modified. Awaiting your direction.**

---
---

# PART III — CANONICAL RESEARCH DOMAIN MODEL

---

# MOGO Canonical Research Domain Model

**Conceptual architecture. No implementation, storage, schema, or code decisions are made or implied here.**

---

## 0. The five modeling decisions that carry the weight

Before the roster, the decisions that everything else follows from. Each one departs from the entity list as given, and each is defended below.

| # | Decision | Why it matters |
|---|---|---|
| **D1** | **"Rule" splits into two entities: `Rule Statement` and `Mechanism`.** | This is the KEREV-B firewall made structural. A normative assertion about how to trade and a thing that executes are different in kind. Conflating them is how MOGO's own inventions become "canonical trading knowledge." |
| **D2** | **`Observation` is primary; `Trade` is a subtype.** | RUN-001 suppressed 15 of 39 qualified setups. If trades are the atomic unit, the unobserved is structurally invisible — and the censoring problem becomes permanent and unfixable. |
| **D3** | **`Replay Campaign` generalizes to `Campaign`, with modality as an attribute.** | The model must survive new markets, engines, and asset classes. Baking "replay" into an entity name guarantees a rewrite the first time a second evidence modality matters. |
| **D4** | **"Evidence" is a *role*, not an entity.** | Nothing *is* evidence. Things are evidence *for* or *against* a proposition. The repository currently uses one word for transcript excerpts and replay trade records, which are not the same kind of object. |
| **D5** | **Confidence is not one quantity. It is three, and they must never be summed.** | Integrity (is this record intact?), Attestation (did they actually say this?), and Epistemic (is it true?) are independent. Collapsing them is the single most likely way this model fails. |

---

## 1. Entity roster

### Accepted as proposed

`Educator` · `Source` · `Concept` · `Claim` · `Hypothesis` · `Evidence Package` · `Statistical Result` · `Approved Knowledge`

### Accepted with modification

| Proposed | Becomes | Reason |
|---|---|---|
| `Rule` | **`Rule Statement`** + **`Mechanism`** | D1 |
| `Replay Campaign` | **`Campaign`** | D3 |
| `Observation` / `Trade` | **`Observation`**, with `Trade` as one subtype | D2 |
| `Evidence` | **`Attestation`** (source side) + **`Evidence Package`** (observation side) | D4 |

### Rejected as first-class entities

| Proposed | Verdict | Reason |
|---|---|---|
| **`Alias`** | ❌ Demote to a **Terminology Binding** — a reified relationship | An alias has no independent existence. It is always *this educator, using this term, for this concept, evidenced here, during this period.* It carries state and provenance, so it must be reified — but it is never independently addressable as knowledge. Promoting it to an entity invites someone to reason about aliases as if they were claims. |
| **`Confidence`** | ❌ Not an entity | It is a derived property of other entities. An entity you can create is an entity someone can author by hand. Confidence must never be authorable. |
| **`Trade`** as a peer | ❌ Subtype only | D2 |
| **`Educator`** as an organizing unit | ⚠️ Retained as an **attribution entity only** | `DECISION\|MOGO\|20260727\|004` already ratified educator equality. Educators must remain nameable — attribution is an ethical and legal requirement, and terminology is genuinely educator-specific — but nothing may be *organized* by educator. |

### Missing entities the proposal omits

These are not optional. Each closes a gap I can point to in the current repository.

| Entity | Why it must exist |
|---|---|
| **`Dataset`** | A campaign's results are meaningless without a fingerprinted, re-identifiable description of the market data it ran over. RUN-001 records a dataset hash but there is no entity that *is* the dataset. Without it, reproducibility across time, brokers, or asset classes is impossible — and this is the entity that makes the model survive a move beyond FX. |
| **`Open Question`** | "We don't know" must be a first-class, addressable, prioritizable object. Otherwise ignorance is invisible, and acquisition priorities are set by vibes. Also the only honest destination for an insufficient result. |
| **`Contradiction`** | Cross-educator disagreement is the most valuable signal a multi-educator library can produce. It must be recorded and preserved, **never resolved by fiat**. A model with no contradiction entity will silently pick a winner. |
| **`Decision`** | The only thing permitted to move any entity's state. Every promotion, every rejection, every authorization cites one. Without it, promotion is emergent, and emergent promotion is how unvalidated things ship. |
| **`Metric Definition`** | A measure is defined once and referenced. Two analyses that each define "win rate" inline will eventually disagree, and nobody will be able to say which was wrong. |
| **`Investigation Protocol`** | The frozen, timestamped declaration of what a campaign will test and by what criteria, fixed **before** execution. Without it, pre-registration is an honour system — unfalsifiable, and therefore worthless as a control. |

---

## 2. Entity definitions

Throughout: **Authoritative** = a human or an external world created it; it is the source of truth. **Derived** = it must be fully re-computable from authoritative entities; if it cannot be re-derived, it is not derived, it is authored, and it is lying about its nature.

---

### `Educator`

| | |
|---|---|
| **Purpose** | Attribution. A named person or organization whose material MOGO studies. |
| **Why it exists** | Attribution is non-negotiable for honesty. Terminology is genuinely educator-specific. Independence of corroboration is measured partly by authorship. |
| **Represents** | An attribution target and a terminology namespace. |
| **Does NOT represent** | An organizing unit. A container for knowledge. A standing or authority level. A truth-bearer. **No educator is more credible by virtue of being implemented, ingested first, or well known.** |
| **Authority** | Authoritative |
| **Mutability** | Evolving — an educator's body of work grows. Their *past statements* never change. |

> **Challenge.** Retaining `Educator` at all risks re-establishing the organizing pattern by habit. The discipline that prevents this: **an educator has no properties that constitute knowledge.** Ask "which educators teach X" and you get an answer *by traversal through concepts* — never by opening an educator and reading their contents. If anyone ever asks "what does MOGO know about TJR's method," the correct answer is a query, not a folder.

---

### `Source`

| | |
|---|---|
| **Purpose** | The primary provenance anchor. A specific, archived, fingerprinted artifact of external material. |
| **Why it exists** | Every downstream statement must terminate in something that exists in the world and can be re-examined. |
| **Represents** | One retrievable artifact and its verified attribution. |
| **Does NOT represent** | An educator's overall position. A summary. Anything MOGO wrote. **A source is never MOGO-authored** — that is what makes it a source. |
| **Authority** | Authoritative |
| **Mutability** | **Immutable.** Permanently. A corrected transcript is a new source that supersedes, never an edit. |

---

### `Attestation`

*(the source-side unit currently called "evidence item" — renamed for D4)*

| | |
|---|---|
| **Purpose** | A verbatim excerpt from a source, preserved exactly, with its location. |
| **Why it exists** | It is the atom of provenance. Everything asserted about an educator must trace to one. |
| **Represents** | What was *actually said or shown*, in the original language. |
| **Does NOT represent** | What it means. Whether it is true. Whether MOGO agrees. **Interpretation lives in `Claim`, never here.** |
| **Authority** | Authoritative |
| **Mutability** | **Immutable.** Forever. This is the deepest floor of the model. |

---

### `Concept`

| | |
|---|---|
| **Purpose** | Canonical vocabulary. A named trading idea, defined once, independent of who teaches it. |
| **Why it exists** | Without it, the same idea in different words is two unrelated strings; the same word for different ideas is a silent conflation; and cross-educator comparison — the entire point of a multi-educator library — is impossible. |
| **Represents** | An identity. A stable name for an idea, so that statements about it can be gathered. |
| **Does NOT represent** | **Truth. Ever.** A concept is not a claim, is not evidenced, is not confirmed, and cannot be right or wrong. It does not represent an educator's definition — its definition is MOGO's own editorial normalization, and is never citable as anyone's assertion. |
| **Authority** | Authoritative as vocabulary; **never authoritative as knowledge** |
| **Mutability** | **Evolving, versioned, never deleted.** A concept may be split, merged, deprecated, or superseded — and each such change is itself a decision with a record. Deprecated concepts are retained forever so historical statements remain readable. |

> **The load-bearing constraint.** *A concept must never influence confidence.* If two claims corroborate each other **because an operator mapped them to one concept**, then epistemic confidence becomes a function of a taxonomy edit. Corroboration must always run through an explicit, audited independence judgment — never implicitly through vocabulary. This is the difference between a library and a machine for confirming what you already believe.

---

### `Terminology Binding` *(reified relationship)*

| | |
|---|---|
| **Purpose** | Records that a given educator, in a given source, used a given term for a given concept. |
| **Why it exists** | Terminology is the one genuinely educator-specific thing, and mapping it is an editorial act that requires its own provenance and its own audit trail. |
| **Represents** | An asserted equivalence between one educator's words and one canonical concept. |
| **Does NOT represent** | That the educator agrees with MOGO's definition. That two educators using one concept *mean* the same thing at the level of detail that matters. |
| **Authority** | Authoritative, but **editorial** — must be visibly distinguishable from observed fact |
| **Mutability** | Versioned. Educators change vocabulary over time; a binding is scoped to a period and a source. |

---

### `Claim`

| | |
|---|---|
| **Purpose** | MOGO's normalized statement of what an educator asserted. |
| **Why it exists** | Attestations are unusable at scale; something must carry meaning while remaining anchored to verbatim language. |
| **Represents** | An interpretation of one or more attestations, expressed in concept vocabulary. |
| **Does NOT represent** | Truth. **A claim being well-attested says nothing whatsoever about whether it works.** It also does not represent MOGO's position. |
| **Authority** | Authoritative as a record of interpretation |
| **Mutability** | **Immutable; corrections supersede.** The full revision history stays walkable. |

---

### `Rule Statement`

| | |
|---|---|
| **Purpose** | A normative proposition about how to trade, expressed in concept vocabulary, precise enough to be argued about. |
| **Why it exists** | Claims are utterances; rules are positions. Multiple claims across multiple educators may express one rule, and one rule is the thing a hypothesis actually tests. |
| **Represents** | "Under conditions C, one should do D." Nothing more. |
| **Does NOT represent** | What any code does. That it is correct, validated, or approved. Authorization to implement anything. |
| **Authority** | Authoritative |
| **Mutability** | Versioned; prior versions preserved permanently |

> **Mandatory, non-nullable property: `provenance class`.**
> **`EDUCATOR_ASSERTED`** — traceable to attestations.
> **`MOGO_AUTHORED`** — MOGO's own invention. No educator states it.
> **`CONVERGENT`** — MOGO authored it independently and an educator was later found to agree. **Convergence is not derivation**, and must never be relabelled as educator knowledge.
>
> This exists because the current repository holds **9 canonical ALEX rules that no source states** and **7 classified as MOGO-authored with no educator support**. Without a permanent, structural discriminator, those become indistinguishable from educator knowledge inside a decade — and that loss is irreversible.

---

### `Mechanism`

| | |
|---|---|
| **Purpose** | A specific, versioned, executable procedure that produces trading decisions. |
| **Why it exists** | **What the code does is not knowledge. It is an artifact under test.** This entity is the firewall that keeps implementation facts from being read as facts about the world. |
| **Represents** | A frozen, identifiable engine version and its behaviour. |
| **Does NOT represent** | An educator's method. Knowledge of any kind. That its behaviour is correct or desirable. **A mechanism's behaviour is evidence about MOGO's code and about nothing else.** |
| **Authority** | Authoritative about itself only |
| **Mutability** | **Immutable per version.** Behaviour change means a new version, always. |

> **Why this split is the most important one in the model.** A `Rule Statement` says what *should* happen. A `Mechanism` does something. The gap between them is **fidelity**, and fidelity is an *observation about the code*, never evidence about markets. The repository already discovered why this matters: replay and live currently run different entry rules, because two gates live only in the live path. Under a model where "rule" and "mechanism" are one entity, that divergence is invisible. Under this model it is a first-class, reportable fidelity fact.

---

### `Hypothesis`

| | |
|---|---|
| **Purpose** | A falsifiable proposition about the world, stated so that evidence can move it. |
| **Why it exists** | It is the **only** entity in the model that can be true or false about markets. Everything upstream is vocabulary, testimony, or machinery. |
| **Represents** | A prediction, its metric, its comparison, its threshold, its minimum sample, and — mandatorily — **its falsification condition**. |
| **Does NOT represent** | An educator's belief. A rule. A conclusion. Anything MOGO intends to do. |
| **Authority** | Authoritative |
| **Mutability** | **Immutable once pre-registered.** Amendment creates a successor and voids any claim to pre-registration against already-collected evidence. |

> **Identity is anchored to concepts, not to educators.** This is the correct reading of "educator-independent": a hypothesis is *about* concepts and rule statements; educator claims attach as **supporting provenance, which may legitimately be empty** when the hypothesis is `MOGO_AUTHORED`.
>
> **Challenge to the proposal as stated:** *"every hypothesis must be educator-independent"* read literally would strip claim linkage and produce untraceable propositions. The requirement is **educator-independent in identity, educator-traceable in provenance.** Those are different, and only the second preserves the ability to answer "why do we even think this?"
>
> **A hypothesis must also be able to be permanently unresolvable.** Some propositions cannot be tested by any available modality. That is a legitimate terminal state, and a model without it will quietly park them in "under research" forever.

---

### `Campaign`

| | |
|---|---|
| **Purpose** | A bounded, authorized, pre-declared effort to generate observations answering specific hypotheses. |
| **Why it exists** | Evidence generation must be *intentional and declared in advance*, or every result is post-hoc. |
| **Represents** | An authorization, a protocol, a dataset scope, a mechanism version, and the hypotheses it exists to answer. |
| **Does NOT represent** | Its results. A conclusion. Permission to generate a *different* result than the one it declared. |
| **Authority** | Authoritative |
| **Mutability** | **Immutable once declared.** Changing scope mid-campaign creates a new campaign. |

> **Modality is an attribute, not an identity** (D3). Replay is one way to generate observations. Forward paper is another. Others will exist. **Every modality carries its own permanent ceiling on what it can establish** — replay observes one mechanism over one dataset, and agreement with the mechanism that produced the trades is not independent confirmation, at any sample size. Naming the entity "Replay Campaign" would encode today's only modality into the permanent model.

---

### `Investigation Protocol`

| | |
|---|---|
| **Purpose** | The frozen declaration of what will be tested, how, and by what criteria — fixed before any observation exists. |
| **Why it exists** | Pre-registration that can be edited afterwards is not pre-registration. This entity is what makes "declared in advance" **falsifiable** rather than merely asserted. |
| **Represents** | Hypotheses under test, metrics, thresholds, minimum samples, family size for multiplicity correction, and stopping rules. |
| **Does NOT represent** | Findings. Anything learned during execution. |
| **Authority** | Authoritative |
| **Mutability** | **Immutable, and timestamped relative to observation.** Its whole value is that its timestamp precedes the data. |

---

### `Dataset`

| | |
|---|---|
| **Purpose** | An identified, fingerprinted body of market data with a stated completeness and provenance. |
| **Why it exists** | A result is reproducible only if the data is re-identifiable. Also the entity through which **asset-class and market portability** enters the model at all. |
| **Represents** | What the world looked like, as recorded by a named provider, over an absolute window, at stated granularities, with declared completeness. |
| **Does NOT represent** | Reality. It is a *recording*, subject to revision, gaps, and provider error. |
| **Authority** | Authoritative |
| **Mutability** | **Immutable by fingerprint.** A revised candle is a different dataset, and the model must be able to notice that. |

> This entity is where the model earns its durability. A new asset class introduces a new dataset provenance and new completeness semantics — **and nothing else in the model changes.** Session-bound concepts simply carry a scope that a 24/7 market does not satisfy.

---

### `Observation`

| | |
|---|---|
| **Purpose** | One atomic recorded fact produced by a campaign. |
| **Why it exists** | It is the unit of empirical content, and the level at which **what did not happen must be recorded**. |
| **Represents** | Something that occurred, or was evaluated and did not occur, under a known mechanism over a known dataset. |
| **Does NOT represent** | Its interpretation. Its significance. Anything aggregated. |
| **Authority** | Authoritative |
| **Mutability** | **Immutable.** Permanently. |

> **Subtypes include, and must include more than, `Trade`:**
> **`Trade`** — a position taken and resolved.
> **`Candidate`** — a setup that qualified but was not taken, **with the reason it was not taken.**
> **`Rejection`** — an evaluation that did not qualify, with the rule that excluded it.
>
> **This is D2, and it is the fix for the single deepest scientific flaw currently in the repository.** RUN-001 suppressed 15 of 39 qualified setups under a portfolio constraint, and those outcomes are unobserved. That suppression is **not random** — it correlates with clustering, which correlates with market structure. The 24 observed trades are therefore a *biased draw* from 39, not a smaller unbiased one. If `Trade` were the atomic unit, this would be structurally unrepresentable and would silently corrupt every statistic computed from it, at any sample size. **Making the unobserved a first-class observation is what makes the censoring visible, and therefore correctable.**

---

### `Evidence Package`

| | |
|---|---|
| **Purpose** | The durable, integrity-verified container that carries observations out of a volatile runtime and into the permanent record. |
| **Why it exists** | An observation that exists only in memory is not evidence; it is a rumour. |
| **Represents** | A sealed, content-addressed record of observations plus the full identity of the conditions that produced them. |
| **Does NOT represent** | Truth, significance, or interpretation. **And integrity is not authenticity** — it detects alteration, and nothing more. |
| **Authority** | Authoritative |
| **Mutability** | **Immutable. Never backfilled, under any circumstance.** |

> **The non-negotiable rule this entity encodes:** *arithmetic on two stored values is a derivation, not an observation.* A package records what was observed and explicitly marks what was unavailable. It never reconstructs a missing figure and presents it as recorded. A package whose capture predates a later improvement stays permanently at its original ceiling, and the correct response is a new campaign — never a retro-fill.

---

### `Statistical Result`

| | |
|---|---|
| **Purpose** | The outcome of applying a declared protocol to a declared body of observations. |
| **Why it exists** | It is the only legitimate bridge from observation to knowledge. |
| **Represents** | A measured quantity **with its uncertainty**, its sample, its family size, and its multiplicity correction. |
| **Does NOT represent** | A decision. Truth. A point estimate — **a result reported without an interval is not a result.** |
| **Authority** | **Derived — and must be fully re-derivable** |
| **Mutability** | Immutable per computation; recomputation on new observations creates a new result, never an update |

> If a statistical result cannot be regenerated from its inputs and its protocol, it is not derived — it is authored, and it must be treated as an opinion.

---

### `Contradiction`

| | |
|---|---|
| **Purpose** | A preserved record that two well-attested statements disagree. |
| **Why it exists** | Disagreement between educators is the most informative signal a multi-educator library produces. A model without this entity will silently pick a winner and lose the disagreement forever. |
| **Represents** | An unresolved conflict, with both sides fully preserved. |
| **Does NOT represent** | An error. Something to be fixed. A defect in the library. |
| **Authority** | Authoritative |
| **Mutability** | **Immutable. Recorded, never resolved by fiat.** It may be *superseded by evidence* — which is a new record, not an edit. |

---

### `Open Question`

| | |
|---|---|
| **Purpose** | A named, addressable, prioritizable statement of what MOGO does not know. |
| **Why it exists** | Ignorance must be as visible as knowledge, or acquisition priorities become arbitrary and gaps persist indefinitely without anyone noticing. |
| **Represents** | A gap, what would close it, and what it currently blocks. |
| **Does NOT represent** | A defect or a task. Some questions are permanently unanswerable, and recording that is a finding. |
| **Authority** | Authoritative |
| **Mutability** | Evolving; closure requires a decision citing what closed it |

> **This is the entity that makes "insufficient" a first-class result** rather than a failure to be quietly avoided.

---

### `Metric Definition`

| | |
|---|---|
| **Purpose** | One measure, defined once, referenced everywhere. |
| **Why it exists** | Inline redefinition is how two analyses come to disagree about "win rate" with no way to adjudicate. |
| **Represents** | A definition, its direction of goodness, its degenerate cases, and its comparison surface. |
| **Does NOT represent** | A value. A threshold. A judgment. |
| **Authority** | Authoritative |
| **Mutability** | Versioned; **changing a definition invalidates comparability** with every prior result computed under the old one, and must say so |

---

### `Decision`

| | |
|---|---|
| **Purpose** | A recorded human judgment that authorizes a state change. |
| **Why it exists** | **Nothing in this model promotes itself.** Every movement along the promotion ladder is a human act, recorded, with its basis, and permanently attributable. |
| **Represents** | Who decided what, when, on what basis, considering which alternatives, and what it authorizes. |
| **Does NOT represent** | Evidence. A decision is not proof of anything except that a decision was made. |
| **Authority** | Authoritative |
| **Mutability** | **Immutable.** Reversal is a new decision that supersedes. |

---

### `Approved Knowledge`

| | |
|---|---|
| **Purpose** | A proposition MOGO currently accepts, at a stated confidence, up to a stated evidence-class ceiling, by a cited decision. |
| **Why it exists** | The output of the whole system. |
| **Represents** | A hypothesis that met predefined criteria, plus the ceiling its evidence class permits, plus the decision that promoted it. |
| **Does NOT represent** | **Truth. Permanence. Profitability. Authorization to trade.** Approved knowledge is a current best estimate under a declared standard — nothing stronger. |
| **Authority** | Derived from a hypothesis, a statistical result, and a decision |
| **Mutability** | **Evolving, and explicitly demotable** |

> **The demotion path is mandatory, and it is absent from the current repository.** Markets change; edges decay; data gets revised. A model in which knowledge can only ratchet upward is a model that will eventually defend a dead edge with a citation. **Approved Knowledge must be able to expire, be contradicted, and be demoted by new evidence — through the same decision mechanism that promoted it.**

---

## 3. Relationships

### The provenance spine — how a statement is grounded

```
Educator ──authors──▶ Source ──contains──▶ Attestation
                                                │
                                          supports
                                                ▼
Concept ◀──expressed in── Claim ──interpreted from──▶ Attestation
   ▲                        │
   │                   contributes to
   │                        ▼
   └──expressed in── Rule Statement ──[provenance class]──▶ EDUCATOR_ASSERTED
                                                          │ MOGO_AUTHORED
                                                          │ CONVERGENT
Educator ──[Terminology Binding]──▶ Concept
```

### The empirical spine — how a proposition is tested

```
Concept + Rule Statement ──motivate──▶ Hypothesis
                                            │
                                    declared in
                                            ▼
                              Investigation Protocol
                                            │
                                     frozen into
                                            ▼
Mechanism ─┐                            Campaign ◀── authorized by ── Decision
Dataset  ──┼──────────────produces──────▶  │
           │                                ▼
           └──identifies────────────▶ Observation  (Trade | Candidate | Rejection)
                                            │
                                      sealed into
                                            ▼
                                    Evidence Package
                                            │
                              supports / contradicts / is silent on
                                            ▼
                                       Hypothesis
                                            │
                                    measured under
                                            ▼
                            Metric Definition ──▶ Statistical Result
                                            │
                                  evaluated against Protocol
                                            ▼
                                        Decision
                                            │
                                        promotes
                                            ▼
                                   Approved Knowledge
```

### The two spines meet in exactly one place

**Only at `Hypothesis`.** That is deliberate and load-bearing.

Nothing an educator said can reach `Approved Knowledge` without passing through a falsifiable proposition that evidence was given a fair chance to refute. And nothing observed can be attributed to an educator without a rule statement whose provenance class says whether they actually asserted it.

**This single junction is what prevents both failure modes at once:** testimony being promoted as fact, and MOGO's own inventions being laundered as educator knowledge.

### Cross-cutting relationships

| Relationship | Note |
|---|---|
| `Claim` **contradicts** `Claim` → `Contradiction` | Preserved; never auto-resolved |
| `Rule Statement` **is implemented by** `Mechanism` → **fidelity** | An observation about code, never evidence about markets |
| `Statistical Result` **may fail to resolve** `Hypothesis` → `Open Question` | Insufficiency is a recorded outcome, not a non-event |
| `Evidence Package` **contradicts** any prior document → **correction** | The backward edge; see §7 |
| `Decision` **authorizes** every state change everywhere | No exceptions |
| `Concept` **relates to / is distinguished from** `Concept` | Explicit near-miss disambiguation |

---

## 4. Vocabulary and evidence — six terms, six responsibilities, no overlap

This is the section that keeps the model honest in five years. Each term answers exactly one question, and no other.

| Term | Answers | Never answers | Failure if confused |
|---|---|---|---|
| **Concept** | *What do we call this idea?* | Whether it is true, taught, or useful | A vocabulary edit silently changes confidence |
| **Claim** | *What did this educator assert?* | Whether it works | A well-attested claim gets treated as a validated one |
| **Rule Statement** | *What position is being taken about how to trade?* | Who said it, whether it's right, what the code does | MOGO's inventions become educator knowledge — **KEREV-B, unrecoverable** |
| **Hypothesis** | *What falsifiable prediction can evidence move?* | What anyone believes | Untestable beliefs occupy the testing pipeline forever |
| **Evidence** *(role)* | *What was observed, and what does it bear on?* | What it means | Observation and interpretation fuse; the interpretation becomes unfalsifiable |
| **Knowledge** | *What do we currently accept, at what confidence, under what ceiling?* | What is true | An estimate under a standard becomes a permanent fact |

**Two disciplines that fall directly out of this table:**

1. **"Evidence" is never a noun standing alone.** Something is evidence *for* or *against* a specific hypothesis. An `Evidence Package` is a container of observations; it becomes evidence only in relation to a proposition. A package that supports nothing is still a valid, complete record — it is simply not yet evidence of anything.

2. **A claim can never be promoted directly to knowledge, no matter how well attested.** The path *must* go through a hypothesis and a statistical result. Ten educators agreeing is ten claims — it is not one validated fact. **Consensus is a property of testimony, not of markets.**

---

## 5. Provenance

### The three rules

**Rule 1 — Provenance flows downward and never upward.**
A derived entity inherits the provenance of everything it rests on. A conclusion never confers legitimacy backwards onto its inputs. A hypothesis reaching `SUPPORTED` does not make the claim that suggested it any better attested.

**Rule 2 — A chain is no stronger than its weakest link, and the weakest link is always visible.**
A statistical result resting on one `MOGO_AUTHORED` rule statement **cannot be reported as educator knowledge**, regardless of how strong the statistics are. Provenance class does not attenuate with distance — it **propagates**.

**Rule 3 — Every derived entity must name what it could not observe.**
Absence is part of provenance. A package that could not compute an integrity hash says so. A result computed on a censored sample says so. **A gap that is not recorded becomes, within one generation of documents, an implied completeness that was never true.**

### What is inherited

| Level | Inherits |
|---|---|
| `Claim` | Source identity, attestation location, attribution certainty |
| `Rule Statement` | All contributing claims' provenance; **plus its own provenance class**, which is authored, not inherited |
| `Hypothesis` | The provenance class of every rule statement it rests on; concept scope |
| `Observation` | Mechanism version, dataset fingerprint, campaign authorization |
| `Evidence Package` | Everything above, plus integrity status and what was unavailable |
| `Statistical Result` | Every package's provenance, plus sample composition **and censoring** |
| `Approved Knowledge` | The whole chain, plus its evidence-class ceiling, plus the decision |

### What is preserved forever, without exception

1. **The verbatim excerpt.** The exact language, unedited. The floor of the model.
2. **The dataset fingerprint.** Otherwise no result is reproducible, ever.
3. **The mechanism version.** Otherwise "what produced this" is unanswerable.
4. **The provenance class.** The KEREV-B firewall. Its loss is silent and irreversible.
5. **The pre-registration timestamp.** The only thing distinguishing a prediction from a story.
6. **Every decision.** Including reversed ones — a reversed decision is part of the record of how MOGO thinks.
7. **Contradictions.** Both sides, permanently.
8. **What was suppressed, rejected, or unobserved.** The censoring record.

### What can never be lost

> **The ability to answer, for any statement MOGO holds: *"Who said this, where exactly, what did MOGO add, what did the code actually do, over what data, and who decided it counted?"***

If any entity is ever added that cannot answer that chain, it does not belong in this model.

---

## 6. Confidence

### The core finding: confidence is three quantities, and they are not commensurable

The single most likely way this model degrades is someone collapsing these into one number because a dashboard needed one.

| Quantity | Question | Attaches to | Moves when |
|---|---|---|---|
| **Integrity** | *Is this record intact and unaltered?* | `Source`, `Attestation`, `Evidence Package`, `Dataset` | Never — it is verified or it is not. **Binary, not graded.** |
| **Attestation confidence** | *Did they actually say and mean this?* | `Claim` (and `Terminology Binding`) | Better sources, clearer language, corroborating attestations |
| **Epistemic confidence** | *Is this true about markets?* | `Hypothesis` — **and nowhere else** | Only observations. Never testimony, never consensus, never vocabulary. |

### Where confidence attaches — and where it must not

| Entity | Confidence? | Why |
|---|---|---|
| **`Concept`** | ❌ **Never** | Vocabulary cannot be true. A concept is not more or less correct — it is more or less *useful*, which is not confidence. **This prohibition is what prevents taxonomy edits from moving belief.** |
| **`Claim`** | ✅ **Attestation only** | How sure we are they said it. **Explicitly not whether it works.** A perfectly attested claim about a losing method is a perfect claim. |
| **`Rule Statement`** | ❌ No independent confidence | It carries *support* — attestation inherited from claims — and *status*, from hypotheses. Giving it its own confidence creates a place for belief to accumulate without evidence, which is exactly how a well-argued rule becomes a fact. |
| **`Hypothesis`** | ✅ **Epistemic — the primary locus** | The only entity that can be true or false about the world. This is where evidence lands. |
| **`Observation` / `Evidence Package`** | ❌ **Integrity only** | An observation either happened or didn't. It is not "70% likely." Confusing integrity with epistemic confidence would let a well-hashed package look like a well-supported finding. |
| **`Statistical Result`** | ❌ It *carries* uncertainty; it does not *have* confidence | An interval is a property of a measurement, not a belief about it. |
| **`Approved Knowledge`** | ✅ **Derived, never independent** | Its confidence is the hypothesis's epistemic confidence, **bounded by the evidence-class ceiling**, **authorized by a decision**. It can never exceed any of the three. |

### Justification

**Why not on concepts.** If confidence attached to vocabulary, then merging two concepts would merge two confidences, and an editorial judgment would move belief. That is the exact failure the concept layer must be designed to prevent, and it is subtle enough to happen by accident.

**Why attestation and epistemic must stay separate.** Collapsing them produces the single most damaging error available to this system: **treating a well-evidenced claim as a well-evidenced strategy.** Nine educators agreeing that you should trade with the trend is nine well-attested claims and zero evidence about outcomes. The current repository already articulates this — verified implementation fidelity says nothing about profitability — and the model must make it structurally impossible to confuse.

**Why epistemic confidence lives only on hypotheses.** Because a hypothesis is the only thing with a falsification condition. Anything without a falsification condition cannot have its confidence *lowered* by evidence — and a confidence that can only rise is not a confidence, it is an accumulating enthusiasm.

**Why the ceiling is a hard bound, not a discount.** Replay observes one mechanism over one dataset. Agreement with the engine that produced the trades is not independent confirmation, **and no sample size changes that.** A ceiling is categorical: 10,000 replay trades and 100 replay trades both stop at the same wall. Only a *different modality* moves it.

**Nothing self-corroborates.** A single source cannot corroborate itself into support, however many times it repeats. Neither can a single mechanism, a single dataset, or a single campaign.

---

## 7. The scientific lifecycle

### The forward path

```
① EXTERNAL KNOWLEDGE      Educator → Source → Attestation
                          Record what was said. Interpret nothing.

② CANONICAL VOCABULARY    Attestation → Claim → Concept · Rule Statement
                          Normalize language. Assign provenance class.
                          Draw NO conclusions.

③ HYPOTHESIS              Concept + Rule Statement → Hypothesis
                          Make it falsifiable, or record why it cannot be.

④ PRE-REGISTRATION        Hypothesis → Investigation Protocol → Campaign
                          Freeze criteria BEFORE data exists. Authorize.

⑤ OBSERVATION             Mechanism + Dataset → Observation
                          Trades AND candidates AND rejections.
                          Record the unobserved.

⑥ EVIDENCE                Observation → Evidence Package
                          Seal. Verify integrity. Never backfill.

⑦ STATISTICS              Evidence Package + Metric → Statistical Result
                          Intervals, not points. Correct for family size.
                          Report censoring.

⑧ KNOWLEDGE               Statistical Result + Decision → Approved Knowledge
                          Bounded by the evidence-class ceiling.
```

### The feedback loops — where the real work happens

A purely linear pipeline is a naïve model of research. **Seven return edges are mandatory.** Their absence is how a research system silently stops learning.

**L1 — Correction.** *Evidence Package → any prior document.*
Observation may contradict something MOGO wrote. The repository has already needed this: a documented "structural impossibility" was falsified by a run's own evidence, and it still stands asserted in two documents. **Without an authorized backward edge, a research system accumulates falsehoods it has already disproven.** This is the most under-appreciated loop in the model.

**L2 — Insufficiency.** *Statistical Result → Open Question → acquisition and campaign priority.*
"Not enough evidence" is a finding that must generate work, not silence.

**L3 — Exploratory discovery.** *Observation → new Hypothesis → future Campaign.*
A pattern noticed in data becomes a **new pre-registered hypothesis awaiting new evidence** — never a conclusion from the data that suggested it. Two channels, never mixed: confirmatory findings are promotion-eligible; exploratory findings are **never** promotion-eligible, and their only legal outputs are a new hypothesis or a factual correction.

**L4 — Contradiction.** *Contradiction → Hypothesis.*
Two educators disagreeing is the most testable situation available. Disagreement is a research prompt, not a defect.

**L5 — Fidelity.** *Mechanism vs. Rule Statement → Open Question.*
When code diverges from the rule it claims to implement, the question is not automatically "fix the code." It may be an unstated rule, an unresolved specification gap, or a genuine defect. **All three are findings; only one is a bug.**

**L6 — Ceiling.** *Approved Knowledge at ceiling → Campaign of a different modality.*
When a hypothesis is capped by its evidence class, the correct response is a *different kind* of evidence — never more of the same, and never lowering the ceiling.

**L7 — Decay and demotion.** *New evidence → demotion of Approved Knowledge.*
Edges expire. Regimes change. Data gets revised. **Without this loop the model is a ratchet, and a ratchet in research is a machine for defending dead ideas with citations.**

### The two rules that keep the loops honest

1. **No loop may promote using the same observations that suggested it.** Every return edge terminates in a *new* pre-registration awaiting *new* evidence.
2. **Every loop traversal is a decision, and every decision is recorded.** Loops are where post-hoc reasoning enters a research system; the audit trail is what keeps them from becoming laundering paths.

---

## 8. Permanent design principles

Ordered roughly by how expensive each is to violate.

### On separation

**P1 — Concepts are vocabulary, not truth.** A concept can never be true, false, evidenced, confirmed, or confident. It is a name.

**P2 — What was said, what is true, and what the code does are three separate bodies of knowledge, and they are never merged.** Testimony, reality, and implementation. This principle is the whole of KEREV-B.

**P3 — Convergence is not derivation.** MOGO authoring something an educator independently agrees with is convergence, and it stays labelled as such permanently. Silent relabelling is knowledge laundering.

**P4 — Evidence is a role, not a thing.** Nothing is evidence in isolation. It is evidence *for* a specific proposition, or it is a record.

### On provenance

**P5 — Provenance is immutable, flows downward only, and is never lost.** Corrections supersede; they do not edit.

**P6 — A chain inherits its weakest provenance, and that weakness stays visible at every level.** Provenance class propagates; it does not attenuate.

**P7 — Absence is part of the record.** What was unavailable, suppressed, unobserved, or unverifiable is recorded as explicitly as what was observed. **An unrecorded gap becomes an implied completeness.**

### On evidence

**P8 — Evidence cannot be inferred.** Arithmetic on two stored values is a derivation, not an observation, and must be labelled as such. A missing figure is reported missing, never reconstructed.

**P9 — Records are immutable and never backfilled.** A record captured under an earlier capability keeps that ceiling forever. The remedy is a new campaign, never a retro-fill.

**P10 — Integrity is not authenticity, and neither is confidence.** Verifying that a record is unaltered says nothing about whether it is true or who produced it.

**P11 — The unobserved must be observable.** Candidates and rejections are first-class observations. **A sample that hides what it excluded cannot be interpreted at any size.**

### On inference

**P12 — Replay reduces uncertainty; it cannot create authority.** Every modality has a permanent ceiling that sample size does not move.

**P13 — Nothing self-corroborates.** Not a source, not an educator, not a mechanism, not a dataset, not a campaign.

**P14 — Criteria are declared before evidence exists, and never lowered afterwards.** A threshold adjusted after seeing results is not a threshold.

**P15 — A measure is defined once and referenced.** Inline redefinition guarantees eventual, unadjudicable disagreement.

**P16 — Report intervals, not point estimates. A difference whose interval includes zero is not a difference.**

**P17 — "Insufficient" is a result.** Permanently unanswerable is also a result. Neither is a failure, and neither may be quietly converted into a weak conclusion.

### On knowledge

**P18 — Knowledge is promoted only through predefined statistical criteria, and only by a recorded decision.** Nothing promotes itself.

**P19 — Knowledge is demotable.** Approved Knowledge is a current best estimate under a declared standard, not a permanent fact. Without a demotion path the model is a ratchet.

**P20 — Contradiction is preserved, never resolved by fiat.** It may be superseded by evidence — as a new record, not an edit.

**P21 — Consensus is a property of testimony, not of markets.** Ten educators agreeing is ten claims.

### On the model itself

**P22 — No entity is both authoritative and derived.** If a derived entity cannot be regenerated from its inputs, it is authored and must say so.

**P23 — The model is modality-, market-, and asset-class-agnostic.** New markets enter through `Dataset` and concept scope. If a new asset class requires a new entity, the model was wrong.

**P24 — Immutability applies to records, not to understanding.** The record of what was said and observed never changes. What MOGO concludes from it is expected to.

---

## 9. Where I would challenge this model

An honest design states its own failure modes.

**W1 — The concept layer's benefit is real but narrower than it appears.** Correctly built, concepts cannot drive corroboration — which means they do **not** raise the independence ceiling, and therefore do not fix the constraint currently blocking every claim in the library. They fix navigation, cross-educator comparison, and terminology collision. They do not produce validated knowledge. **Only evidence volume does.** Anyone presenting this model as the answer to "why has nothing been validated" is misreading it.

**W2 — The Rule Statement / Mechanism split has an ongoing cost.** Every implementation fact must be entered twice conceptually: once as what the code does, once as what someone claims should happen. This is real overhead. **I judge it worth paying, because the alternative failure is silent and irreversible** — but it will feel like bureaucracy on a Tuesday, and it will be tempting to collapse. It must not be.

**W3 — Provenance class is only as good as the discipline applying it.** No structure can stop someone marking a MOGO invention `CONVERGENT` because an educator said something vaguely similar. The model makes the distinction *expressible and auditable*; it cannot make it *correct*. This needs periodic adversarial review, not just a field.

**W4 — Terminology Binding is the model's weakest joint.** Asserting that two educators mean the same thing is a judgment that can be wrong in ways nothing downstream will surface. Two educators using "liquidity sweep" may differ on the detail that decides every trade. The mitigation — explicit `distinguished-from` disambiguation — is only as good as the operator's care.

**W5 — Seven feedback loops is a lot of governed surface.** Each is a place where post-hoc reasoning can enter. I have not found a way to remove any of them without losing something real, but the number should be treated as a cost, and each loop should have to justify itself annually.

**W6 — Recording candidates and rejections may generate far more data than trades.** RUN-001 produced 24 trades from 39 qualified setups out of an unknown but much larger number of evaluations. Recording every rejection could be orders of magnitude more volume than recording every trade. **The principle is right; the granularity needs a deliberate, declared boundary** — and wherever that boundary is drawn, what falls outside it must be stated, or P7 is violated by the very mechanism meant to satisfy it.

**W7 — This model cannot make a censored sample interpretable.** It makes censoring *visible*, which is a precondition for handling it, but the statistical treatment of informative censoring is a separate and genuinely hard problem that no domain model solves. **Do not let the presence of a `Candidate` entity create the impression that the problem is handled.**

**W8 — The model has no opinion about how much evidence is enough.** Deliberately — that belongs in governance, not the domain model. But it means the model can be fully, correctly implemented and still produce nothing of value if the thresholds are set badly. **A domain model is a container for rigor. It is not rigor.**

---

**Nothing has been implemented. No code, schema, storage, or document was created or modified. This is a conceptual model awaiting your review.**

---
---

# PART IV — PERMANENT SCIENTIFIC WORKFLOW

---

# MOGO Permanent Scientific Workflow

**Methodology and governance only. No implementation, storage, schema, or code decisions are made or implied.**

---

## 0. The structural correction this workflow makes

The candidate stage list, and the repository's existing 12-stage lifecycle, both describe **one linear chain**: acquire → extract → formalize → *implement* → verify → *replay* → validate → decide.

That ordering embeds an assumption that is false and expensive: **that knowledge must be implemented before it can be tested.**

Its consequences are visible in the repository today. RAYNER_TEO has 46 claims and 31 hypotheses and can produce nothing, because there is no engine. TJR has 69 claims and is described as needing "setup detection and replay before it can produce evidence — a larger lift than it appears." Both are stalled behind an engineering dependency that most of their hypotheses **do not actually have.**

The correction:

> **Two tracks that converge at the hypothesis, not one chain that runs through implementation.**
>
> **Track A — Knowledge Formation.** Cheap, parallel across unlimited educators, requires no engine, never blocked by engineering.
> **Track B — Instrument Readiness.** Expensive, sequential, engineering-owned. **Entered only when a hypothesis genuinely requires a mechanism.**
> **Track C — Inquiry.** Where they meet. Some hypotheses reach it needing only a dataset. Others need a verified mechanism.

This mirrors the domain model directly: the provenance spine and the empirical spine meet only at `Hypothesis`.

And it introduces the single highest-leverage distinction in this document:

| Campaign type | Requires | Answers | Ceiling |
|---|---|---|---|
| **Measurement campaign** | A dataset. **No mechanism.** | Questions about market structure — *"do zones with ≥4 touches produce reactions more often than zones with 2?"* | Bounded by dataset breadth, not by any engine |
| **Strategy campaign** | A verified mechanism + dataset | Questions about a decision procedure — *"does this rule set produce positive expectancy?"* | Bounded by the mechanism it observed |

**A large fraction of every educator's teaching is market-structure assertion, not strategy assertion.** Those hypotheses are testable *now*, for every educator, without implementing anything. The current lifecycle cannot express that, which is why the library has 641 hypotheses and zero adjudications.

---

## 1. The lifecycle stages

### Track A — Knowledge Formation

*No engine. No authorization beyond acquisition. Runs continuously and in parallel across all educators.*

| | Stage | Purpose |
|---|---|---|
| **A1** | **Source Acquisition** | Obtain and archive a specific external artifact with verified attribution |
| **A2** | **Attestation** | Capture verbatim what was said or shown, with location. **Interpret nothing.** |
| **A3** | **Claim Registration** | State what the educator asserted, in concept vocabulary. Propose new concepts where existing vocabulary does not fit. |
| **A4** | **Concept Ratification** | Accept, split, merge, or reject proposed vocabulary. **Asynchronous and batched** — never blocks A3. |
| **A5** | **Rule Formalization** | Convert claims into normative propositions with a mandatory provenance class |

### Track B — Instrument Readiness

*Entered only on demand from C2. Never a prerequisite for Track A.*

| | Stage | Purpose |
|---|---|---|
| **B1** | **Mechanism Specification** | Every parameter stated or explicitly declared MOGO-authored |
| **B2** | **Implementation** | Build it. Freeze it. Version it. |
| **B3** | **Fidelity Verification** | Establish where the mechanism diverges from the rule statements it claims to implement — **and record the divergences rather than eliminating them** |

### Track C — Inquiry

*Where the tracks converge. This is the actual research cycle, and it repeats indefinitely.*

| | Stage | Purpose |
|---|---|---|
| **C1** | **Hypothesis Formulation** | Convert a proposition into a falsifiable prediction with metric, comparison, threshold, minimum sample, and falsification condition |
| **C2** | **Testability Adjudication** | Determine *whether*, and *by which modality*, this can be tested at all |
| **C3** | **Pre-Registration & Authorization** | Freeze criteria, declare the family, authorize the campaign — **before any observation exists** |
| **C4** | **Campaign Execution** | Generate and seal observations, including candidates and rejections |
| **C5** | **Statistical Analysis** | Apply the frozen protocol. Nothing else. |
| **C6** | **Scientific Review** | Interpret the result against the pre-registered criteria and the evidence-class ceiling |
| **C7** | **Disposition** | Record the outcome and its consequences |

### Perpetual — Knowledge Stewardship

**Not stages.** These are transitions in a state machine that begins the moment anything is promoted and never terminates. Modeling them as pipeline stages — as the candidate list does — implies you pass through them once, which is exactly backwards.

Confirmation · Erosion · Contest · Obsolescence · Supersession · Demotion · Retirement · Reopening

### Why I changed the candidate list

| Candidate stage | Disposition | Reason |
|---|---|---|
| Observation Collection + Evidence Packaging | **Merged into C4** | Packaging is a mechanical property of collecting, not a decision point. A gate with no decision is pure overhead. |
| Replay Campaign | **Generalized to Campaign Execution** | Baking one modality into a permanent stage guarantees a rewrite the first time a second modality matters. |
| Concept Mapping | **Split** into proposal (inside A3) and ratification (A4) | The cheapest moment to assign a concept is at annotation. Making ratification synchronous would block every ingestion behind a taxonomy debate. |
| Research Planning | **Absorbed into C2 + C3** | As a free-standing stage it has no gate and no artifact. As testability adjudication plus pre-registration it has both. |
| Knowledge Demotion, Retirement, Reopening | **Moved out of the pipeline** | They are perpetual state transitions, not stages. |
| — | **Added: Testability Adjudication (C2)** | The repository holds 641 hypotheses carrying placeholder tests and **zero** that are testable now. A stage that would have caught this on entry did not exist. |
| — | **Added: Fidelity Verification as a first-class stage (B3)** | Divergence between rule and mechanism is a *finding*, not a bug to be silently fixed. |
| — | **Made explicit: Pre-Registration is separate from Hypothesis Registration** | Registering a hypothesis is cataloguing. Pre-registering it is committing. Both need independent timestamps, and only the second is falsifiable. |

---

## 2. Entry and exit criteria

### Track A

| Stage | Required in | Required out | Advances when | **Blocked when** |
|---|---|---|---|---|
| **A1** | A candidate artifact | Archived source, verified attribution, fingerprint | Attribution verified and archive is byte-preserved | Attribution unverifiable → recorded as attribution-uncertain, **usable but permanently flagged**; never silently promoted |
| **A2** | An archived source | Verbatim excerpts with locations | Every excerpt traces to an exact location | Any excerpt that cannot be located; **any paraphrase presented as verbatim** |
| **A3** | Attestations | Claims in concept vocabulary; proposed concepts | 100% of claims trace to an attestation | Any claim without provenance; **any claim asserting something the source did not say** — including a plausible generalization of a single worked example |
| **A4** | Proposed concepts | Ratified, split, merged, or rejected vocabulary | Batch review completed | A speculative concept with no claim referencing it. **Vocabulary is seeded from real usage, never invented in advance.** |
| **A5** | Claims | Rule statements with provenance class | Every rule carries an explicit class and an evidence class | **Any rule whose provenance class is unstated.** An illustrative demonstration promoted to a universal rule. |

> **The critical A5 constraint.** A rule shown once and never generalized is illustrative and **does not become a rule**. In the ALEX register, 5 of 41 are illustrative and 9 are unsupported by any source. That register's most important number is that **only 6 of 41 are deterministic** — the method is described richly and specified thinly. **A5's job is to expose that gap, not to close it by invention.** Closing it by invention is exactly how `MOGO_AUTHORED` content enters wearing an educator's name.

### Track B

| Stage | Required in | Required out | Advances when | **Blocked when** |
|---|---|---|---|---|
| **B1** | Rule statements + a hypothesis needing a mechanism | A specification where every parameter has a value or is declared MOGO-authored | Every parameter accounted for | **Any invented parameter presented as the educator's.** Any unresolved specification gap not recorded as an open question. |
| **B2** | A specification | A frozen, versioned mechanism | Tests pass; protected boundaries intact | Any behaviour change without a version increment |
| **B3** | Mechanism + rule statements | A fidelity record naming every divergence | All divergences located and classified | **A divergence silently "fixed" instead of adjudicated.** A rule that cannot be located in code recorded as implemented. |

> **B3's non-obvious rule.** A divergence has three possible meanings: a defect, an unstated rule the educator never articulated, or a deliberate MOGO decision. **All three are findings; only one is a bug.** A workflow that reflexively treats divergence as a defect destroys the second and third categories — and the second is often the most interesting thing in the corpus.

### Track C

| Stage | Required in | Required out | Advances when | **Blocked when** |
|---|---|---|---|---|
| **C1** | A rule statement or open question | A hypothesis with metric, comparison, threshold, minimum sample, falsification condition | All five present and referencing a defined metric | **Any missing falsification condition.** A metric defined inline rather than referenced. A prediction that no outcome could contradict. |
| **C2** | A hypothesis | A testability verdict and a required modality | A modality exists that could reach it, or it is recorded as untestable | Advancement is blocked, **not failed** — untestable is a valid, recorded terminal or holding state |
| **C3** | A testable hypothesis + a fit instrument (if required) | A frozen protocol, declared family, authorization | Criteria frozen and **timestamped before any observation exists** | **Any observation already collected for this question.** Family size undeclared. Instrument not fit (Track B incomplete). Modality's ceiling not stated. |
| **C4** | An authorized campaign | Sealed, integrity-verified observations — trades, candidates, **and rejections** | Observations sealed; suppression and exclusions recorded | **Any change to the protocol mid-campaign.** Any observation discarded without record. A campaign producing a result for a question it did not declare. |
| **C5** | Sealed observations + frozen protocol | Statistical results with intervals, sample composition, and censoring | Protocol applied exactly as frozen | **Any analysis not specified in the protocol** — that output is exploratory and can never be promoted. A point estimate without an interval. Multiplicity uncorrected. |
| **C6** | Statistical results | An interpretation against pre-registered criteria and the ceiling | All mandatory considerations addressed | **Any consideration unaddressed.** Any interpretation using a threshold different from the frozen one. |
| **C7** | A reviewed result | A recorded disposition and its consequences | A decision exists citing the basis | **Any disposition without a decision record.** Any promotion above the modality's ceiling. |

---

## 3. Decision gates

**A stage is work. A gate is a human judgment that work cannot proceed past.** Conflating them is how methodology becomes bureaucracy — so this workflow has **fifteen stages and five gates**, and only two of the five are heavyweight.

### G1 — Concept Ratification *(periodic, batched, lightweight)*

**Decides:** whether proposed vocabulary is accepted, split, merged, or rejected; whether two educators' terms denote one concept.
**Requires:** real claims already using the term; explicit disambiguation against near-miss concepts.
**Prohibited:** ratifying a concept no claim references. **Declaring two educators' terms equivalent without evidence that both mean the same thing at the level of detail that decides a trade.** Retiring a concept in a way that makes historical claims unreadable.

> **Never synchronous.** If ingestion waits on taxonomy, ingestion stops.

### G2 — Instrument Fitness *(per mechanism version)*

**Decides:** whether a mechanism is fit to generate evidence, and **what its evidence can and cannot establish.**
**Requires:** determinism, fidelity record, an enumerated cost model (applied or explicitly declared absent), a documented data source, traceable accept/reject reasoning, defined end-of-data handling.
**Prohibited:** **declaring fitness by omission** — every unmet criterion must be stated as a stated limitation on what the evidence can support, not quietly ignored. Waiving a criterion because a campaign is desired.

> **This gate produces a scope of validity, not a pass/fail.** A mechanism with no cost model is not unfit — it is fit for R-space comparisons and unfit for expectancy claims near zero. Saying so precisely is more useful than a binary, and far more honest than a silent pass.
>
> Applied to the repository's own state, this is the gate that would have said: *replay and live currently run different entry rules; therefore replay evidence is valid about the replay mechanism and says nothing about live behaviour.* That is a usable verdict. "FAIL — may not enter replay" was not.

### G3 — Pre-Registration & Authorization ⭐ *(heavyweight — the load-bearing gate)*

**Decides:** which hypotheses this campaign will answer; the frozen criteria; the declared family size; the modality and its ceiling; the resource authorization.
**Requires:** testable hypotheses; a fit instrument if one is needed; a declared dataset scope; a stated ceiling; **confirmation that no observation for these questions already exists.**
**Prohibited:**
- Authorizing a campaign whose questions are not named in advance
- Declaring criteria after any observation exists
- **Setting thresholds by reference to a result already seen, in this or any prior campaign**
- Omitting family size — it is the input to multiplicity correction and cannot be reconstructed later
- Authorizing a campaign whose declared ceiling would not permit the conclusion it is intended to reach

> **This is the only gate whose value comes entirely from its timestamp.** Everything else could in principle be reconstructed. This cannot. If G3 is weak, every downstream control is decorative.

### G4 — Disposition ⭐ *(heavyweight)*

**Decides:** promote, refute, inconclusive, insufficient, or contested — and what follows.
**Requires:** statistical results with intervals; multiplicity correction applied; sample composition **and censoring** reported; the ceiling restated; every mandatory consideration addressed.
**Prohibited:**
- Promoting on a point estimate
- Promoting above the modality's ceiling **at any sample size**
- Promoting on statistical significance without a material effect size
- Concluding from an analysis not in the frozen protocol
- **Treating "not refuted" as support**
- Lowering a threshold to reach a conclusion
- **Declining to record an inconclusive or insufficient result** — silence is not a disposition

### G5 — Stewardship *(periodic)*

**Decides:** demotion, obsolescence, supersession, retirement, reopening.
**Requires:** the new evidence, the changed condition, or the elapsed review interval that triggered it.
**Prohibited:** demoting without a record. **Retiring knowledge to avoid contradicting it.** Reopening a settled question without new evidence or a newly available modality.

### What has *no* gate, deliberately

Attestation, claim registration, hypothesis formulation, campaign execution, statistical computation. **These are work.** Gating them adds latency and removes nothing — a claim cannot do harm; only a promotion can. Rigor belongs where irreversible things happen.

---

## 4. Feedback loops

### F1 — Evidence revises hypotheses *(forward)*
A result moves a hypothesis's state within its evidence class. **It never edits the hypothesis** — an amended hypothesis is a successor, and it forfeits any claim to pre-registration against evidence already collected.

### F2 — Contradictory evidence *(the asymmetry that matters)*
Two campaigns disagreeing produces `CONTESTED`, **not a re-average and not an overwrite.** Averaging across campaigns destroys the disagreement, which is usually more informative than either result: it means something differs between conditions, and *that* is the next hypothesis.

> **Evidence removes confidence more readily than it confers it.** Refutation needs one well-conducted campaign meeting a pre-declared falsification condition. Support needs criteria, ceiling, replication, and a decision. **This asymmetry is deliberate and must never be levelled** — it is what stops a research system from becoming a belief-accumulator.

### F3 — New educators affect existing concepts
A new educator contributes: new terminology bindings to existing concepts; possibly new concepts; **and — uniquely — new independence groups.**

> This is the only loop that can raise epistemic ceilings through knowledge work rather than evidence work, and it is why educator expansion is not merely coverage. But the effect is on *attestation* corroboration, not on epistemic confidence. **Two educators agreeing raises how sure we are that this is a widely-taught idea. It does not make it more likely to be true.**

### F4 — Concepts split and merge
**Split** when one concept demonstrably covers two distinct ideas. **Merge** when two are shown to denote one.

> **Both are irreversible-feeling operations that must not disturb belief.** Historical claims stay readable; superseded concepts are retained forever; and — the load-bearing rule — **a split or merge never changes any hypothesis's state.** If reorganizing vocabulary could move confidence, then confidence would be a function of taxonomy, and the whole model collapses. If a merge *suggests* two hypotheses were the same question, that produces a **new** hypothesis awaiting **new** evidence.

### F5 — Approved knowledge is reconsidered
Triggers: contradicting evidence · a mechanism version change · a dataset revision · a regime change invalidating scope · elapsed review interval · a superseding better-specified hypothesis.

> **Every promotion carries a review interval at the moment it is promoted.** Knowledge without an expiry is knowledge nobody will ever revisit.

### F6 — Insufficiency drives acquisition
An insufficient or inconclusive result generates an open question stating exactly what would resolve it, which feeds campaign and acquisition priority. **This is how "we don't know" becomes work rather than silence.**

### F7 — Exploratory discovery *(the strictly-controlled loop)*
Campaigns reveal things nobody asked about. RUN-001's most valuable single output was a discovery: a documented "structural impossibility" was falsified by the run's own evidence.

**Two channels, never mixed:**
- **Confirmatory** — pre-registered only. Promotion-eligible.
- **Exploratory** — anything else. **Never promotion-eligible.** Its only legal outputs are a new pre-registered hypothesis awaiting new evidence, or a factual correction under F8.

### F8 — Correction *(the backward edge)*
When evidence contradicts a repository document, the document is corrected, citing the evidence.

> **This loop is mandatory and is the one most often missing.** The repository currently contains a claim asserted in two documents that its own evidence has already falsified. **A research system without an authorized backward edge accumulates falsehoods it has already disproven** — and those falsehoods keep being cited, because they are still written down.

### F9 — Fidelity divergence
A rule/mechanism divergence generates an open question, resolved as defect, unstated rule, or deliberate decision. Never auto-resolved to "defect."

### F10 — Ceiling escape
A hypothesis capped by its evidence class requires a **different modality**, never more of the same. More replay evidence never escapes a replay ceiling.

---

## 5. Hypothesis states

### The central structural point

> **A hypothesis does not have one state. It has one state per evidence class.**

A hypothesis may be simultaneously `SUPPORTED` at the replay class and `AWAITING_EVIDENCE` at the live class. **Collapsing that into a single global state is precisely how "supported" comes to be read as "validated"** — and once that reading takes hold, the ceiling is decorative.

### The states

| State | Meaning | Terminal? |
|---|---|---|
| **`DRAFT`** | Proposed, not yet adjudicated for testability | No |
| **`UNTESTABLE_AS_WRITTEN`** | Real question, malformed as a test. **Fixable by rewriting.** | No — holding |
| **`UNTESTABLE_IN_PRINCIPLE`** | No modality can reach it, now or foreseeably | **Yes** — a legitimate scientific answer |
| **`REGISTERED`** | Testable, catalogued, not committed to a campaign | No |
| **`PRE_REGISTERED`** | Criteria frozen, campaign authorized, evidence not yet collected | No |
| **`IN_TESTING`** | Campaign executing | No |
| **`INSUFFICIENT`** | Tested; sample below the pre-declared minimum. **No adjudication is permitted.** | No |
| **`INCONCLUSIVE`** | Tested at adequate sample; interval includes zero. **A real finding: no detectable effect at this power.** | No |
| **`SUPPORTED`** | Criteria met **within a named evidence class**, at a named ceiling | No — always provisional |
| **`REFUTED`** | Falsification condition met. **A permanent, valuable result.** | Effectively yes |
| **`CONTESTED`** | Campaigns disagree. Both preserved. | No — demands a new hypothesis |
| **`SUPERSEDED`** | Replaced by a better-specified successor; history preserved | Yes |
| **`WITHDRAWN`** | Retracted before testing as malformed or duplicated | Yes |
| **`RETIRED`** | Scope no longer exists — instrument delisted, regime gone | Yes, reopenable |

### What the candidate list got wrong

| Issue | Correction |
|---|---|
| **No untestable states** | The repository holds 641 hypotheses that are untestable as written, and they currently sit indistinguishable from testable ones. **Two states are needed, not one:** malformed-but-fixable is work; unreachable-in-principle is an answer. |
| **"Contradicted" conflated with "Rejected"** | `REFUTED` = evidence met the falsification condition. `CONTESTED` = campaigns disagree. Merging them lets a second campaign silently overwrite a first. |
| **No `INSUFFICIENT` distinct from `INCONCLUSIVE`** | "Sample too small to say" and "adequately powered, no effect found" are **completely different findings**. The first demands more evidence; the second is often a final answer. Merging them causes indefinite, pointless collection. |
| **"In Testing" covering pre-registration** | A pre-registered hypothesis awaiting a campaign is not being tested. Separating them is what makes the pre-registration timestamp meaningful. |
| **`SUPPORTED` as a bare state** | It must always carry its evidence class and ceiling. A bare `SUPPORTED` will be read as validated within a year. |

### Legal transitions

```
DRAFT ──▶ REGISTERED | UNTESTABLE_AS_WRITTEN | UNTESTABLE_IN_PRINCIPLE | WITHDRAWN

UNTESTABLE_AS_WRITTEN ──(rewrite → new successor)──▶ DRAFT
UNTESTABLE_IN_PRINCIPLE ──(new modality becomes available)──▶ DRAFT

REGISTERED ──▶ PRE_REGISTERED | SUPERSEDED | WITHDRAWN
PRE_REGISTERED ──▶ IN_TESTING
IN_TESTING ──▶ INSUFFICIENT | INCONCLUSIVE | SUPPORTED | REFUTED

INSUFFICIENT  ──▶ PRE_REGISTERED   (more evidence, same class)
INCONCLUSIVE  ──▶ PRE_REGISTERED   (higher power, or a different modality)
SUPPORTED     ──▶ CONTESTED | REFUTED | SUPPORTED@higher-class | RETIRED
REFUTED       ──▶ CONTESTED        (only on new contradicting evidence)
CONTESTED     ──(never resolved by fiat)──▶ new hypothesis
```

**Illegal, permanently:** any transition to `SUPPORTED` without a G4 decision · any transition skipping `PRE_REGISTERED` · `REFUTED → SUPPORTED` on the same evidence · any state change from a concept split, merge, or rename.

---

## 6. The knowledge lifecycle

Approved Knowledge is **a current best estimate under a declared standard**, never a fact. Five things can happen to it, and all five must be possible.

### Gains confidence

Only two mechanisms, and neither is "more of the same":

1. **Replication** — an independent campaign, different dataset or period, meeting the same criteria. **Narrows the interval within the existing class.**
2. **Class escalation** — a *different modality* meeting the gate. **The only thing that raises a ceiling.**

> **What does not confer confidence:** more evidence from the same modality on the same mechanism; more educators asserting it; elapsed time without contradiction; being useful; being believed.

### Loses confidence

**Erosion** — new evidence shifts the interval toward zero.
**Contest** — a campaign disagrees; the item is marked contested and **cannot be cited as settled while contested.**
**Foundation failure** — a rule statement it depends on is refuted, a mechanism version is invalidated, or a dataset is revised. **Confidence is inherited, so it is also revocable through inheritance.**

### Becomes obsolete

Its **scope of validity** no longer describes the world: the instrument is delisted; the regime it was measured in has passed; the mechanism version is retired; the data provider changed methodology.

> Obsolete knowledge is **not wrong.** It was true of a world that no longer exists. It is retained, scope-annotated, and no longer cited as current. **Deleting it would destroy the record of how MOGO's understanding changed** — which is itself the most durable thing a research programme produces.

### Becomes superseded

A better-specified successor answers the same question more precisely. The predecessor is retained, linked, and never edited. **Supersession is not refutation** — the old statement may still be true, merely coarser.

### Remains unresolved indefinitely

**The most likely outcome for most questions, and it must be comfortable.**

Permanent unresolution is honest when: no modality can reach it; the required sample will never be attainable; it depends on an unresolvable specification gap; or its effect size is genuinely below detectable resolution.

> **The system must make sitting at `UNRESOLVED` for years costless.** If unresolved items generate recurring pressure, someone will eventually resolve one to make the pressure stop — and that resolution will be the least defensible item in the corpus.

### Demotion is mandatory, and it is the hardest rule to keep

Demotion runs through **the same gate that promoted it**, with the same evidentiary standard. It is recorded, never quietly dropped.

> **A model where knowledge only ratchets upward is a machine for defending dead ideas with citations.** Every promoted item carries a review interval set *at promotion time* — because the moment you are most willing to specify how you might be wrong is before you have invested in being right.

---

## 7. Governance boundaries

| Function | Owns | **Never does** |
|---|---|---|
| **Research** | Acquisition, attestation, claims, concepts, rule formalization, hypothesis formulation, testability adjudication | **Never sets thresholds. Never decides promotion. Never computes the result it will interpret.** |
| **Statistics** | Metric definitions, protocol design, computation, intervals, multiplicity correction, censoring reporting | **Never chooses which analyses to report after seeing them. Never interprets. Never decides.** Computes exactly what the frozen protocol specifies — no more. |
| **Governance** | All five gates. Authorization. Promotion, demotion, retirement. Threshold ratification. Resolving what a divergence *means*. | **Never computes a statistic. Never adjusts a criterion after data exists. Never overrides a result — only decides what follows from it.** |
| **Engineering** | Mechanism specification, implementation, versioning, fidelity records, evidence integrity, reproducibility | **Never decides whether a divergence is acceptable. Never authorizes a campaign. Never interprets an outcome.** |

### The separation that actually matters, for a solo operator

The obvious objection: **MOGO is one person. All four roles are the same human.** Role separation between identical people is theatre.

**The separation is therefore temporal and procedural, not personnel-based:**

> **Governance commits to the criteria before Statistics can compute anything, and Statistics computes only what was committed.**

That single ordering constraint delivers most of the value of organizational separation without requiring a second person. The criteria cannot bend to the result **because they were fixed and timestamped before the result existed.** Independence is manufactured by sequence, not by headcount.

**The one boundary that cannot be simulated by sequencing:** deciding what a fidelity divergence means, and deciding whether an unmet fitness criterion is acceptable. Those are genuine judgment calls made by the same person who built the thing. **The only available control is that the reasoning is written down before the answer is convenient** — which is weaker than independence, and should be acknowledged as weaker rather than dressed up.

### The permanently prohibited overlap

**Whoever authors a hypothesis may not also decide, after seeing the result, what threshold it should have met.** Every other overlap is a manageable weakness. This one voids the entire method.

---

## 8. Scientific invariants

### Ordering

**I1 — No hypothesis is tested before it is registered, and none is analysed before its criteria are frozen and timestamped.**
**I2 — Criteria are declared before evidence exists and are never lowered afterwards.** A threshold adjusted after seeing a result is not a threshold.
**I3 — Family size is declared at pre-registration.** It cannot be reconstructed afterwards, and without it multiplicity correction is unavailable.
**I4 — Confirmatory and exploratory findings are never mixed, and exploratory findings are never promotion-eligible.**
**I5 — A pattern found in data becomes a new pre-registered hypothesis awaiting new evidence — never a conclusion drawn from the data that suggested it.**

### Records

**I6 — No evidence is edited after recording. Ever. Corrections supersede; they never overwrite.**
**I7 — Nothing is backfilled.** A record captured under an earlier capability keeps that ceiling permanently. The remedy is a new campaign.
**I8 — The unobserved is recorded.** Candidates, rejections, suppressions and exclusions are part of the evidence. **A sample that conceals what it excluded is uninterpretable at any size.**
**I9 — Evidence is never inferred.** Arithmetic on two stored values is a derivation. A missing figure is reported missing.
**I10 — Provenance is immutable and flows downward only.** A conclusion never confers legitimacy backward on its inputs.

### Inference

**I11 — Promotion occurs only through predefined statistical criteria, and only by a recorded decision.** Nothing promotes itself.
**I12 — Promotion never exceeds the modality's ceiling, at any sample size.**
**I13 — Nothing self-corroborates** — not a source, an educator, a mechanism, a dataset, or a campaign.
**I14 — "Not refuted" is never support.**
**I15 — Report intervals. A difference whose interval includes zero is not a difference.**
**I16 — Statistical significance without a material effect size is not a result.**
**I17 — Consensus is a property of testimony, not of markets.** Ten educators agreeing is ten claims.

### Outcomes

**I18 — Unknown is a valid, recordable, permanently acceptable scientific outcome.** So is untestable.
**I19 — Refutation is a first-class success.** It permanently removes something from consideration, which is the cheapest knowledge available.
**I20 — Contradiction is preserved, never resolved by fiat or by averaging.**
**I21 — Demotion is always possible, through the same gate as promotion.**
**I22 — Every promotion carries a review interval, set at promotion time.**

### Structure

**I23 — Vocabulary changes never change confidence.** A concept split, merge, or rename is forbidden from altering any hypothesis state.
**I24 — What was said, what is true, and what the code does are never merged**, and every rule statement carries a provenance class permanently.
**I25 — Evidence that contradicts a MOGO document triggers correction of that document.** Not optional. Not deferred.

---

## 9. Critique

### Where bureaucracy could slow research

**B1 — Fifteen stages reads as heavy.** It is fifteen stages and **five gates**, only two of which are heavyweight. But the framing invites gate-creep: every stage will eventually attract a proposed checkpoint. **The count of gates should require an explicit decision to increase, and the burden of proof sits with the addition.**

**B2 — Two tracks double the bookkeeping.** Track A and Track B genuinely diverge, and something must record which hypotheses need which. Justified only because the alternative — one chain — is what has stalled three educators behind an engineering dependency they mostly don't have.

**B3 — Pre-registration friction will suppress small questions.** If G3 costs a day, nobody registers the cheap question worth ten minutes, and the corpus fills with only the questions someone was willing to do paperwork for. **Mitigation: a lightweight lane for measurement campaigns** — same frozen criteria, same timestamp, far less ceremony, because no mechanism authorization is involved.

**B4 — The 641-hypothesis backlog could become a make-work project.** Rewriting all of them to be testable would consume enormous effort for questions nobody will run. **Triage, don't rewrite: adjudicate testability only when a hypothesis is a candidate for a campaign.** The rest sit at `DRAFT` indefinitely, which is honest and costs nothing.

**B5 — Concept ratification is a natural bottleneck.** Mitigated by being asynchronous and batched. If it ever becomes synchronous with ingestion, ingestion stops.

**B6 — Recording every candidate and rejection may dwarf recording trades** by orders of magnitude. The principle is right; **the granularity boundary must be declared deliberately, and whatever falls outside it must be stated** — otherwise the mechanism intended to satisfy I8 violates it.

### Where scientific rigor could be weakened

**R1 — One person occupying all four roles.** The temporal control (criteria frozen before data) covers most of it. It does **not** cover judgment calls about fidelity divergence and fitness waivers. **Acknowledge this as a genuine, unmitigated weakness rather than papering it with role labels.**

**R2 — Gates degrading into batch rubber-stamps.** Five gates approved in one sitting is one gate. **Gates that always pass are not gates**, and a gate that has never blocked anything should be examined for whether it is real.

**R3 — "Inconclusive" is socially unattractive.** The pressure to keep collecting until something crosses a line is the single most likely path to a fabricated conclusion here. **Countermeasure: a stopping rule declared at G3.** Not "collect until it resolves" but "collect N, then adjudicate whatever the answer is."

**R4 — Ceilings treated as discounts.** The failure mode is someone reasoning that 500 replay trades is *"basically"* validated. **A ceiling is categorical, not a confidence penalty.** This needs restating in every report, because it is intuitive to get wrong.

**R5 — Exploratory findings drifting confirmatory.** The gap between "we noticed this" and "we found this" closes silently over a few retellings. **Structural separation of channels is the only defence; social discipline will not hold.**

**R6 — Provenance class assigned self-servingly.** Nothing prevents marking a MOGO invention `CONVERGENT` because an educator said something adjacent. The structure makes the distinction expressible and auditable; it cannot make it correct. **Needs periodic adversarial review, not just a field.**

**R7 — Correction (F8) is the loop most likely to be skipped**, because correcting your own prior document is unrewarding and nothing breaks if you don't. The repository already demonstrates this: a falsified claim still stands in two documents. **Correction should be a required output of campaign review, not a follow-up task.**

### The simplest workflow that preserves MOGO's rigor

Everything above is the durable model. **Here is the operating minimum that preserves the rigor and can be run today** — the rest activates when scale demands it.

**Four gates. Three artifacts. One rule.**

**The four gates:**
1. **Instrument Fitness** — once per mechanism version. Output is a **scope of validity**, not a pass/fail.
2. **Pre-Registration** — hypotheses, metrics, thresholds, minimum sample, family size, stopping rule, ceiling. Frozen and timestamped **before** any observation.
3. **Disposition** — promote / refute / inconclusive / insufficient / contested, against the frozen criteria only.
4. **Stewardship review** — periodic; demote, retire, reopen.

*(Concept ratification stays a batched editorial task, not a gate, until vocabulary volume forces it.)*

**The three artifacts:**
1. **The frozen protocol** — what will be tested and by what criteria. **Its timestamp is the entire control.**
2. **The sealed evidence** — observations including the unobserved, integrity-verified, never edited.
3. **The disposition record** — the outcome, the ceiling, the decision, and **what document it corrects.**

**The one rule:**

> **Nothing is promoted that was not predicted in advance, by criteria fixed before the evidence existed, within the ceiling its evidence class permits.**

**What can be deferred without weakening rigor:** the full 15-stage articulation, formal role separation, concept ratification as a gate, exhaustive testability adjudication across the backlog, and the distinction between erosion and contest.

**What can never be deferred, at any scale, for any reason:** the pre-registration timestamp · the immutability of evidence · recording the unobserved · the evidence-class ceiling · the demotion path · the correction loop · and the legitimacy of answering *"we don't know."*

---

**Nothing has been implemented. No code, schema, storage, or document was created or modified. This is a methodology proposal awaiting your review.**

---
---

# PART V — ADR-012 IMPLEMENTATION PLAN

---

# ADR-012 Implementation Plan — Canonical Knowledge Architecture

**Status: PLANNING. Nothing implemented. Awaiting approval before Milestone 0.**

---

## 0. The scope property that makes this low-risk

I checked the tooling layout to confirm this rather than assume it:

> **ADR-012 requires no change to `index.html`. Not one line. The file is never opened for writing at any milestone in this plan.**

Every entity in the approved model lives in the research subsystem — `docs/trader-intelligence/`, `docs/strategy-fidelity/`, and their Python tooling under `scripts/`. `ARCHITECTURE.md` already establishes this boundary as deliberate and one-directional: *the research subsystem may read `index.html`; nothing in the application reads the research subsystem.*

Three of your seven constraints are therefore satisfied **structurally rather than by verification**:

| Constraint | How it is satisfied |
|---|---|
| **#5 — Maintain replay determinism** | Replay lives entirely in `index.html`. It is not touched, so determinism cannot change. `runId` recomputation is unaffected. |
| **#6 — No protected function changes** | The 63 functions and 4 constants live in `index.html`. Not touched. **Zero authorization is requested in this plan.** |
| **#4 — Preserve every MOGO-003 component** | Every MOGO-003 deliverable is either in `index.html` (untouched) or is an immutable Evidence Package (read-only). See §2. |

**The one place this could be violated** is the evidence bridge (M3), which must read Evidence Packages. It follows the precedent already committed at `656719e`: `build_alex_rule_evidence_join.py` is **read-only over Evidence Packages**, and its 24 tests drive the real generator against synthetic fixtures so the suite passes on a machine with no packages present. Every milestone here obeys the same rule.

---

## 1. Global regression contract

**Applies to every milestone. A milestone is not complete until all five hold.**

| # | Requirement | Command |
|---|---|---|
| G-1 | JS regression **943/943**, 17 suites, 0 failures, 0 execution errors | `tests/run_all.sh` |
| G-2 | **Zero protected drift** — 63 functions, 4 constants byte-identical | included in `run_all.sh`; also asserted by `test_phase7a` |
| G-3 | **All Python suites green** *(becomes enforceable after M0)* | the 8 `unittest` modules |
| G-4 | `index.html` **byte-identical** before and after the milestone | direct hash comparison |
| G-5 | RUN-001's 24 Evidence Packages **byte-identical**; hashes verify; schema validates | read-only verification, no writes |

**Additional standing rules:**

- Every milestone is **independently shippable**. If the next never happens, the repository is coherent, green, and better than before.
- Every milestone that changes documented behaviour updates `TESTING.md`, `KNOWN_ISSUES.md`, and the relevant ADR — the existing documentation obligation in `CODING_STANDARDS.md`.
- **Every new integrity constraint ships with a test written first that fails against the pre-change build**, following the `SAFETY-1…4` precedent from ADR-011.
- Graph build artifacts are **deterministic and regenerable**; they are committed as outputs, never hand-edited.

---

## 2. MOGO-003 preservation register

Verified component-by-component. Every one is untouched by this plan.

| MOGO-003 component | Location | Impact |
|---|---|---|
| Evidence Platform, `mogo.evidence-package.v1` | `index.html` + IndexedDB | **None** — no schema change; ADR-012 writes no package field |
| Replay Identity (`runId`/`datasetHash`/`configHash`/`paramsHash`) | `index.html` | **None** — consumed as an identifier, never recomputed or altered |
| Units A / B / C1 / C2-M1 / C2-M2 | `index.html` | **None** |
| Trade Integrity & Quarantine | `index.html` | **None** |
| Immutable Trade Ledger, Reconciliation | `index.html` | **None** |
| Reporting Authority (flag OFF) | `index.html` | **None** |
| 63 protected functions, 4 constants | `index.html` | **None — no authorization requested** |
| RUN-001's 24 packages | `~/Desktop/MOGO-Evidence/…` | **Read-only. Never modified, never backfilled.** |
| `MOGO-003-VERIFIED-REPLAY-RECORD.md` | `docs/` | Extended with new entries only; existing RUN-001 entry untouched |
| ALEX rule-to-evidence join (`656719e`) | `docs/strategy-fidelity/` | **Reframed, not discarded** — becomes a generated projection (M3). Its `UNRESOLVED` register (6 rules: 4 `NO_EVIDENCE_FIELD_EXISTS`, 2 `FIDELITY_STATUS_UNRESOLVED`) carries forward unchanged |

---

## 3. Milestone overview

| # | Milestone | Size | Depends on | Retires |
|---|---|---|---|---|
| **M0** | Repository stabilization | S | — | 134k uncommitted lines; 6 red tests |
| **M1** | ADR-012 and the governance baseline | S | M0 | Two competing roadmaps; unapproved standard |
| **M2** | Provenance-class firewall | S | M1 | **KEREV-B irreversibility risk** |
| **M3** | Evidence bridge — Dataset, Run, Observation, Package | **L** | M1 | **4 of the 6 target questions** |
| **M4** | Campaign and Investigation Protocol | M | M3 | Unfalsifiable pre-registration |
| **M5** | Concept registry, phase A | M | M1 | F1/F2/F3 vocabulary failures |
| **M6** | Concept mapping and backfill | M | M5 | Cross-educator opacity |
| **M7** | Hypothesis model reconciliation | M | M2, M5 | Two competing status vocabularies |
| **M8** | Metric registry and Statistical Result | S | M4, M7 | Inline metric redefinition |
| **M9** | Knowledge lifecycle — promotion and demotion | M | M8 | The ratchet problem |
| **M10** | Query surface and readiness reporting | S | M3, M6, M9 | **The remaining 2 questions** |

**S** ≈ one session · **M** ≈ one to two · **L** ≈ two to three.

**Sequencing rationale.** M2 is placed early despite being small because it is the only item in this plan whose omission is *irreversible* — once educator-asserted and MOGO-authored content are indistinguishable, no later milestone recovers the distinction. M3 precedes the concept work because it unblocks four of the six target questions and is independent of vocabulary; M5–M6 unblock the other two.

---

## 4. Milestones

---

### M0 — Repository stabilization

**Prerequisite. Not ADR-012 work. Nothing else may begin until this is green.**

**Objective.** Bring the repository to a committed, fully-green baseline so that every subsequent milestone's diff is attributable.

**Expected repository changes.**
- Commit the working tree in coherent, separately-reviewable commits: (a) the graph rebuild + evidence corpus, (b) the governance corpus and `MOGO-RESEARCH-VALIDATION-STANDARD-V1.md`, (c) the three test-fixture scratch-isolation fixes already staged, (d) tooling additions
- Convert the **6 failing Python tests** from emptiness/exact-count assertions to invariants, per `TESTING.md` §4's own stated rule
- Correct `TESTING.md` §4: **8 modules / 451 tests**, not 5 / 307
- Retire `RESEARCH-ROADMAP.md`'s competing milestone numbering in favour of one plan
- Create `AGENTS.md` as a thin operational index

**Tests.** All 8 Python modules green. The 6 converted tests must assert what *must remain true* (every source traces to a registered intake; every blueprint is `DRAFT_RESEARCH_ONLY`) rather than what merely happens to be true today.

**Regression.** G-1 … G-5. This milestone establishes G-3 as enforceable for the first time.

**Risks.**
| Risk | Mitigation |
|---|---|
| A 134k-line commit is unreviewable | Split by concern; graph artifacts are regenerable and reviewed by rebuilding, not by reading |
| Converting tests weakens them | Each conversion states what invariant replaced what assertion, and why the invariant is stronger |
| Committing the validation standard implies approval | Commit with `Status: proposed` unchanged. **M1 approves it, not M0.** |

**Completion criteria.** Working tree clean. All 8 Python modules green. G-1…G-5 hold. `TESTING.md` §4 accurate. One roadmap.

---

### M1 — ADR-012 and the governance baseline

**Objective.** Record the approved architecture as the repository's normative baseline, and resolve the conflicts found in review.

**Expected repository changes.**
- **`docs/adr/ADR-012-canonical-knowledge-architecture.md`** — the domain model, the workflow, the invariants, and the governance boundaries
- **`PROPOSAL-003` resolved** — accepted with the phase-A constraint that concepts never enter confidence scoring
- **`ARCHITECTURE.md`** — Trader Intelligence section revised from three layers to four
- **`docs/trader-intelligence/README.md`** — the "Which entity model do I use?" table extended
- **Reconcile the two sample-size regimes** — Validation Standard §9 (Tier 2 = 100) against Statistical Governance §3 (30 operational / 100 statistical). One authority.
- **Correct the B1 stale claim** in `MOGO-RESEARCH-VALIDATION-STANDARD-V1.md` (gate R10) and `ALEX-BREAK-RETEST-LOSS-FORENSICS-2026-07.md` — the F8 correction loop, exercised on its first real case
- **Re-adjudicate the Replay Readiness Gate** against HEAD: R12 closed by MOGO-003's run identity; R4 and R8 verified still open; R10's premise falsified. Output is a **scope of validity**, not a pass/fail.
- `AGENTS.md` gains one paragraph and a link

**Tests.** Documentation milestone — no new fixtures. A link-integrity check that every ADR-012 cross-reference resolves.

**Regression.** G-1 … G-5.

**Risks.**
| Risk | Mitigation |
|---|---|
| **ADR-012 accidentally resolves KEREV-B** | ADR-012 **must state explicitly that it does not resolve KEREV-B.** M2 builds the firewall; the merge decision stays with the Authority. |
| Re-adjudicating the gate reads as authorizing replay | The gate output authorizes nothing. **Replay authorization remains a separate, explicit instruction.** |
| A fifth normative surface | One ADR; every other document links rather than restates |

**Completion criteria.** ADR-012 committed. `PROPOSAL-003` resolved. Sample-size regimes reconciled to one. B1 corrected in both documents with the evidence cited. Gate re-adjudicated with a stated scope of validity. G-1…G-5 hold.

---

### M2 — Provenance-class firewall

**The highest value-per-line milestone in this plan.**

**Objective.** Make the distinction between educator-asserted, MOGO-authored, and convergent knowledge structural, mandatory, and mechanically enforced — before any merging or normalization work begins.

**Expected repository changes.**
- Provenance class becomes a **required, non-nullable** property on rule statements: `EDUCATOR_ASSERTED` · `MOGO_AUTHORED` · `CONVERGENT`
- Backfill across the **41 canonical ALEX rules**, driven by existing classifications: the register's 26 `EXPLICIT` / 5 `ILLUSTRATIVE` / 1 `OPINION` / **9 `UNSUPPORTED`**, and the join's **7 MOGO-authored**
- A **graph integrity check** that fails the build on any rule statement with an absent or unrecognized class
- `SPEC-provenance.md` documents the discriminator and its inheritance rule

**Tests.** New fixtures — written first, failing against the current build:
- A rule statement with no provenance class **fails validation**
- A rule statement whose class is `EDUCATOR_ASSERTED` but which cites no attestation **fails validation**
- `CONVERGENT` never renders, reports, or exports as `EDUCATOR_ASSERTED`
- Provenance class **propagates** to anything derived from the rule and does not attenuate with distance

**Regression.** G-1 … G-5, plus all existing `test_strategy_fidelity` (63) and `test_rule_evidence_join` (24) still green.

**Risks.**
| Risk | Mitigation |
|---|---|
| **Misclassification is self-serving** — marking a MOGO invention `CONVERGENT` because an educator said something adjacent | `CONVERGENT` requires *both* an independent MOGO authorship record *and* a cited attestation. Absent either, it is `MOGO_AUTHORED`. **Default is the more conservative class.** |
| Backfill of 41 rules introduces errors | Derived mechanically from existing committed classifications, never re-judged by hand |
| Perceived as bureaucracy | It is ~41 records and one integrity check. The alternative failure is silent and permanent. |

**Completion criteria.** All 41 ALEX rules carry a class. Integrity check active and proven to fail on omission. The 9 unsupported and 7 MOGO-authored rules are **individually enumerable in a report**. G-1…G-5 hold.

---

### M3 — Evidence bridge

**The largest milestone, and the one that unblocks four of the six target questions.**

**Objective.** Make Dataset, Campaign Run, Observation, and Evidence Package first-class graph entities, so the connection between what educators said and what the engine did becomes a traversal rather than a hand-built adapter file.

**Expected repository changes.**
- Four new graph node types and their connecting edge types, added **additively** — mirroring exactly how Phase 7A added its four node types to a working build
- `build_graph.py` / `graph_common.py` extended to project packages into nodes, **read-only**
- `validate_graph.py` extended with integrity checks for the new types
- `MOGO-003-VERIFIED-REPLAY-RECORD.md` becomes the authoritative source for run registration
- **`build_alex_rule_evidence_join.py` is reframed**: its `FUNCTION_EVIDENCE_MAP` becomes graph edges; the join artifact becomes a *generated projection*. Its `UNRESOLVED` register carries forward unchanged.

**Tests.** New fixtures, plus the existing 24 join tests must continue to pass unchanged:
- The bridge is **read-only over packages** — a package's bytes are identical before and after a full graph build (direct hash assertion)
- The build **succeeds on a machine with zero Evidence Packages present**, following the existing precedent
- A package whose integrity hash does not verify is **recorded as unverified, never silently included**
- Dataset identity derives from the recorded fingerprint and is never recomputed
- **Observation subtypes** — trades, candidates, and rejections are distinguishable; a run's suppression count is recoverable from the graph

**Regression.** G-1 … G-5. **G-5 is the load-bearing check here** and must be run explicitly before and after every graph build in this milestone.

**Risks.**
| Risk | Mitigation |
|---|---|
| **A write path to Evidence Packages is introduced by accident** | 🔴 Read-only by construction; a fixture asserts byte-identity after a full build; follows the committed join precedent exactly |
| Packages live outside the repository, so tests can't depend on them | Synthetic fixtures drive the real generator — the pattern already proven at `656719e` |
| Graph build destabilizes | Additive types only. Build is deterministic and fully regenerable; a bad build is discarded, not repaired |
| Scope creep into the package schema — "just one more field" | 🔴 **The boundary test: if it changes a package field, it is not this milestone.** Gaps are recorded as open questions and deferred |
| The 15 suppressed RUN-001 setups may not be recoverable from stored packages | **Investigate before building.** If suppressions were not captured per-setup, record that as a known limitation of RUN-001 and a requirement for future campaigns — **do not reconstruct them by inference** |

**Completion criteria.** All four node types build and validate. The join artifact regenerates from graph traversal and is **content-equivalent to the committed `656719e` version**, or every difference is explained. All 24 join tests green. Packages byte-identical. G-1…G-5 hold.

---

### M4 — Campaign and Investigation Protocol

**Objective.** Give pre-registration a falsifiable artifact, so "declared in advance" stops being an honour system.

**Expected repository changes.**
- `Campaign` and `Investigation Protocol` records, with modality as an attribute — **not** baked into the entity name
- The protocol is **frozen and timestamped**, carrying hypotheses under test, metrics, thresholds, minimum sample, declared family size, stopping rule, and modality ceiling
- Campaign authorization links to a `Decision` record
- **The measurement-campaign lane** — a campaign type requiring a dataset but no mechanism
- `STATISTICAL-GOVERNANCE.md` §4 updated to reference the artifact
- RUN-001 registered **retrospectively and explicitly labelled as pre-dating pre-registration** — never backdated

**Tests.**
- A protocol whose timestamp does not precede its campaign's first observation **fails validation**
- A campaign producing results for a hypothesis not in its protocol marks them **exploratory, never promotion-eligible**
- Family size is required; a protocol without it fails
- A measurement campaign validates with no mechanism reference
- **A protocol cannot be edited after its campaign has any observation** — amendment creates a successor

**Regression.** G-1 … G-5.

**Risks.**
| Risk | Mitigation |
|---|---|
| **RUN-001 backdated into apparent pre-registration** | 🔴 Explicit `PRE_DATES_PREREGISTRATION` marker. RUN-001 can never be cited as pre-registered evidence for any hypothesis. |
| Pre-registration friction suppresses small questions | The measurement lane — same freezing, far less ceremony |
| The artifact becomes paperwork nobody fills in | Keep it minimal: the timestamp is the control; everything else is supporting |

**Completion criteria.** Protocol and Campaign records validate. Timestamp-ordering enforced by test. RUN-001 registered with its limitation stated. Measurement lane demonstrated on at least one real hypothesis. G-1…G-5 hold.

---

### M5 — Concept registry, phase A

**Objective.** Establish canonical vocabulary as a navigation and identity layer — **explicitly barred from influencing confidence.**

**Expected repository changes.**
- `Concept` records and `Terminology Binding` as a reified relationship
- One new graph node type and four edge types, per `PROPOSAL-003` §2.3
- Concept definitions marked **MOGO-authored, never citable as any trader's claim**
- `GLOSSARY.md` becomes generated from the registry rather than hand-maintained
- `STANDARDS-extraction.md` documents concept proposal at annotation time
- **No concepts are populated in this milestone** — structure only

**Tests.** The critical ones, written first:
- **A concept never contributes to any confidence computation** — a fixture that adds a concept mapping and asserts every claim's confidence is byte-identical before and after
- A concept definition never appears in any claim or attestation output
- Concept split, merge, and rename **do not change any hypothesis state**
- Deprecated concepts remain readable; historical claims still resolve
- No concept may exist with zero referencing claims

**Regression.** G-1 … G-5, plus all 341 claims' confidence values byte-identical before and after.

**Risks.**
| Risk | Mitigation |
|---|---|
| **Concepts leak into confidence scoring** | 🔴 The byte-identity fixture is the guard, and it is the single most important test in this plan |
| Taxonomy bikeshedding | Structure only in M5; population is M6, seeded strictly from real claims |
| Premature abstraction | The `PROPOSAL-003` §6 trigger fired long ago — 12 sources, 5 educators. Deferral is now the riskier option |

**Completion criteria.** Node and edge types build and validate. Confidence byte-identity proven. Split/merge/rename proven state-neutral. Zero concepts populated. G-1…G-5 hold.

---

### M6 — Concept mapping and backfill

**Objective.** Populate the registry from real claims and make cross-educator comparison a query.

**Expected repository changes.**
- Concepts seeded **only** from vocabulary appearing in existing claims — never invented in advance
- Terminology bindings for ALEX_G, TJR, and RAYNER_TEO
- Backfill of concept references across the existing corpus, **operator-asserted, never auto-detected** — no clustering, no embeddings, no LLM
- `CROSS-STRATEGY-ANALYSIS.md` becomes generated rather than hand-written
- Explicit `distinguished-from` disambiguation for terminology collisions

**Tests.**
- Every concept traces to at least one real claim
- Confidence values unchanged across the entire backfill — **the M5 guard re-run at scale**
- A cross-educator query returns correct results against a synthetic multi-educator fixture
- Unmapped claims behave exactly as before

**Regression.** G-1 … G-5, plus a full corpus confidence-invariance check.

**Risks.**
| Risk | Mitigation |
|---|---|
| **Two educators' terms equated when they differ on the detail that decides a trade** | Mapping requires cited attestations from both sides; `distinguished-from` used liberally; **when in doubt, two concepts, not one** |
| Backfill volume across 341 claims and 416 items | Mechanical and bounded; incremental and independently committable |
| Mapping becomes a de facto merge of MOGO's rules with educator knowledge | M2's provenance class travels with every record and is asserted by test |

**Completion criteria.** Concepts populated from real usage across three educators. Cross-educator query works. Corpus-wide confidence invariance proven. G-1…G-5 hold.

---

### M7 — Hypothesis model reconciliation

**Objective.** Anchor hypothesis identity to concepts, permit MOGO-authored hypotheses, and reconcile the two competing status vocabularies into one.

**Expected repository changes.**
- Hypothesis identity anchors to concepts; educator claims become **many-to-many supporting provenance**, permitted to be empty **only** when the hypothesis is `MOGO_AUTHORED`
- **Status vocabulary unified.** Today two exist: the schema's 5 states, and the join's 5 different ones. Replaced by the approved single set, including the states neither has: `UNTESTABLE_AS_WRITTEN`, `UNTESTABLE_IN_PRINCIPLE`, `INSUFFICIENT` distinct from `INCONCLUSIVE`, and `CONTESTED`
- **State becomes per-evidence-class**, so `SUPPORTED` always carries its ceiling
- The **641 corpus hypotheses are triaged, not rewritten** — all move to `DRAFT`, and testability is adjudicated only when one becomes a campaign candidate

**Tests.**
- A hypothesis with no claims and no `MOGO_AUTHORED` class **fails validation**
- `SUPPORTED` without a named evidence class and ceiling **fails validation**
- A hypothesis cannot reach `SUPPORTED` from `PRE_REGISTERED` without an intervening decision
- `REFUTED → SUPPORTED` on the same evidence is **rejected**
- Every one of the 641 migrates to a legal state with no data loss

**Regression.** G-1 … G-5, plus all 45 `test_phase7a` hypothesis tests green.

**Risks.**
| Risk | Mitigation |
|---|---|
| **Relaxing the claim-linkage requirement destroys provenance** | 🔴 Relaxed *only* for `MOGO_AUTHORED`, enforced by test. Every other class still requires ≥1 claim. |
| Migrating 641 records loses information | Migration is additive; no field is dropped; original status preserved alongside the new one |
| The 641 become a rewriting project | 🔴 **Triage, do not rewrite.** All move to `DRAFT`; adjudication happens on demand. |

**Completion criteria.** One status vocabulary. All 641 migrated. MOGO-authored hypotheses expressible. Ceiling enforcement proven. G-1…G-5 hold.

---

### M8 — Metric registry and Statistical Result

**Objective.** Promote metrics out of the join into first-class definitions, and make statistical results re-derivable records rather than prose.

**Expected repository changes.**
- The 6 metrics currently embedded in the join become standalone `Metric Definition` records, referenced by id
- `Statistical Result` records carrying **intervals, sample composition, censoring, family size, and multiplicity correction**
- Governance thresholds referenced from `STATISTICAL-GOVERNANCE.md`, never restated inline

**Tests.**
- A result without an interval **fails validation**
- A result whose family size differs from its protocol's declared family **fails validation**
- Profit factor with zero losses reports **null, never infinity**
- A result is **fully re-derivable** from its packages and protocol — recomputation reproduces it exactly
- Censoring is required; a result computed on a sample with suppressions that does not report them fails

**Regression.** G-1 … G-5.

**Risks.**
| Risk | Mitigation |
|---|---|
| Metric extraction changes a computed value | Byte-comparison of all RUN-001-derived figures before and after: RZR 16 trades −1.00R; B&R 8 trades −5.00R; overall −6.00R |
| Results authored rather than derived | Re-derivability is a required test, not a convention |

**Completion criteria.** Metrics standalone. Existing figures reproduce byte-identically. Re-derivability proven. G-1…G-5 hold.

---

### M9 — Knowledge lifecycle

**Objective.** Implement promotion, demotion, and stewardship — including the demotion path currently absent from the repository.

**Expected repository changes.**
- `Approved Knowledge` records carrying evidence class, ceiling, decision reference, **and a review interval set at promotion time**
- Stewardship transitions: confirmation, erosion, contest, obsolescence, supersession, demotion, retirement, reopening
- Integration with the existing **18-stage `PromotionState`** ladder — extended, not replaced
- Demotion runs through the same decision mechanism as promotion

**Tests.**
- Promotion above the modality ceiling is **rejected at any sample size**
- Promotion without a decision reference is **rejected**
- Promotion without a review interval is **rejected**
- Demotion is reachable from every promoted state
- Contest preserves both results; **neither is overwritten, and no averaging occurs**
- A promoted item whose supporting rule statement is later refuted **is flagged**, not silently retained

**Regression.** G-1 … G-5. **No item is actually promoted in this milestone** — the machinery ships unused.

**Risks.**
| Risk | Mitigation |
|---|---|
| **Machinery existing invites its use before evidence justifies it** | 🔴 Ships with **zero promoted items**. First promotion requires a separate explicit decision. |
| Demotion never exercised, so it rots | A fixture exercises the full promote→demote cycle on synthetic data every run |
| Conflicts with the 18-stage ladder | Extend the existing ladder; do not introduce a parallel one |

**Completion criteria.** Lifecycle complete and test-covered. Demotion proven reachable. **Zero real promotions.** G-1…G-5 hold.

---

### M10 — Query surface and readiness reporting

**Objective.** Make the six target questions answerable, and generate the statistical readiness report as a query rather than a document.

**Expected repository changes.**
- `query_graph.py` extended for the six questions
- A generated readiness report: per strategy, per setup type — sample, what is answerable, what is not, which hypotheses remain untestable
- `KNOWLEDGE-DASHBOARD.md` regenerated over the new model

**Tests.** Each of the six questions returns correct results against a synthetic fixture spanning multiple educators, concepts, campaigns, and packages. The report **explicitly renders "still insufficient"** where true.

**Regression.** G-1 … G-5.

**Risks.**
| Risk | Mitigation |
|---|---|
| **A query surface makes thin evidence look substantial** | 🔴 Every answer renders sample size, evidence class, and ceiling alongside the result. **No figure is ever displayed bare.** |
| The report implies more than the evidence supports | It is explicitly permitted, and expected, to conclude "insufficient" |

**Completion criteria.** All six questions answerable and tested. Readiness report generated. `KNOWLEDGE-DASHBOARD.md` regenerates. G-1…G-5 hold.

---

## 5. Cross-cutting risks

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| X1 | **A write path to Evidence Packages introduced anywhere** | 🔴 | G-5 on every milestone; byte-identity fixtures; read-only by construction throughout |
| X2 | **Concepts leaking into confidence** | 🔴 | The M5 byte-identity guard, re-run at corpus scale in M6 |
| X3 | **Provenance class assigned self-servingly** | 🔴 | Conservative default; `CONVERGENT` requires both records; periodic adversarial review, not just a field |
| X4 | **This work displaces evidence collection** | 🔴 | Genuinely parallel — this is Python and documentation; the pilot replay is browser verification. **Neither blocks the other, and the browser gap remains the larger one.** |
| X5 | Scope creep into the package schema | 🟠 | Gaps recorded as open questions; **any package-field change is out of scope by definition** |
| X6 | Milestone chain abandoned midway | 🟠 | Every milestone independently shippable and green |
| X7 | 641-hypothesis triage becomes a rewriting project | 🟠 | Triage-on-demand; the backlog sits at `DRAFT` costlessly |
| X8 | **ADR-012 accidentally resolves KEREV-B** | 🔴 | Explicit non-resolution statement in M1; M2 builds the firewall without deciding the merge |

---

## 6. What this plan explicitly does not do

- **No `index.html` change.** No protected function, constant, or replay behaviour touched. **No authorization requested.**
- **No Evidence Package schema change**, at any milestone.
- **No backfill of RUN-001.** Its ceiling is fixed permanently.
- **No replay execution.** M3 and M4 build the machinery; running a campaign is separately authorized.
- **No real promotion.** M9 ships the lifecycle unused.
- **No resolution of KEREV-B**, S4 (informative censoring), T5 (date-range control), T6 (cost model), or T7 (money-space dependency). Recorded, deferred.
- **Does not close the browser-verification gap.** That remains the largest verification gap in the repository and is not addressed by any milestone here.

---

## 7. Decisions needed before M0

1. **Approve the milestone sequence**, or reorder — particularly whether M3 (bridge) should precede M5–M6 (concepts) as I have it.
2. **Confirm M0's commit strategy** — four coherent commits, or one.
3. **Confirm ADR-012 does not resolve KEREV-B**, or instruct that KEREV-B be resolved first.
4. **Confirm this runs in parallel with, not instead of, the pilot replay** and its browser verification.
5. **Ratify the sample-size reconciliation direction** for M1 — Validation Standard §9's 100-trade Tier 2, or Statistical Governance's 30/100 split, as the surviving authority.

---

**Nothing has been implemented. No file has been created or modified. Awaiting your approval before Milestone 0.**

---
---

# PART VI — THE SCIENTIFIC SUCCESS MODEL

---

# The MOGO Scientific Success Model

**Permanent. Philosophy only — no implementation, code, or storage.**

---

## 1. The primary objective

Not "learn to trade." Not "validate strategies." Not "build knowledge."

> ### MOGO exists to hold calibrated beliefs about trading claims — and to know, at all times, precisely how justified each belief is and why.

Two halves, and the order matters.

**Calibration** — when MOGO says it is confident, it should be right about as often as that confidence implies. When it says it does not know, that should be true rather than modest.

**Legibility** — every belief must carry its own justification, traceable to something that exists in the world.

**Knowledge is a byproduct, not the objective.** A system optimizing for knowledge will produce knowledge, including knowledge that is wrong. A system optimizing for calibration will produce *less* knowledge and will be right about how much it has. The second is a research system. The first is a library with opinions.

### The corollary that defines the category

> **A system that cannot become less confident is not a research system. It is an archive with a ratchet.**

The capacity to lose confidence — to demote, to refute, to say *"we believed this and we were wrong"* — is not a safety feature bolted onto a knowledge system. **It is the property that makes it a research system at all.** Everything else in MOGO's architecture is machinery in service of that one capacity.

### What the objective is not

| Not the objective | Why it fails as one |
|---|---|
| Profitable trading | An outcome MOGO cannot control and must never optimize for. Optimizing for it produces curve-fitting with extra steps. |
| Comprehensive knowledge of educators | Coverage is breadth. MOGO has already proved breadth uncorrelated with progress. |
| A large, well-organized corpus | An organized corpus of unvalidated claims is a very tidy pile of guesses. |
| Correct implementation of strategies | Fidelity is engineering. It says nothing about whether the strategy is worth implementing. |
| Answering every question | Most questions will remain open. **A mature system is comfortable with that.** |

---

## 2. Success — the five levels and why they are not the same thing

| Level | What it measures | Available on demand? | Can be faked by working harder? |
|---|---|---|---|
| **Activity** | Motion. Hours, sessions, transcripts watched, runs executed. | ✅ Always | ✅ Trivially |
| **Output** | Artifacts. Claims, hypotheses, packages, documents, commits. | ✅ Always | ✅ Trivially |
| **Evidence** | Observations bearing on a specific proposition. | ❌ Requires authorization and a declared question | ⚠️ Partly — volume yes, relevance no |
| **Knowledge** | Propositions MOGO is justified in believing, at a stated confidence, within a ceiling. | ❌ Requires evidence to be *decisive* | ❌ Not without breaking the gates |
| **Scientific progress** | **Change in the calibrated uncertainty of the corpus.** | ❌ Requires knowledge to *move* | ❌ Not at all |

### Why they differ, precisely

Each level is a **narrowing transformation** of the one below it, and **almost all of the information lives in the conversion rates, not the levels.**

Activity becomes output at a rate set by effort. Output becomes evidence only if it addresses a pre-declared question. Evidence becomes knowledge only if it is decisive at a declared threshold within a permitted ceiling. Knowledge becomes progress only if it *changes* — including downward.

**The failure mode this creates is structural and predictable:** the lower levels are always available, and the upper levels are not. A system under any pressure to demonstrate progress will substitute downward — reporting output where progress was asked for — and the substitution is nearly invisible because the numbers are real.

### MOGO has already run this experiment

The repository's own first periodic review, over ten ingestions:

| | Start | End |
|---|---|---|
| Claims | 47 | **264** |
| Confidence-state changes | — | **0** |
| Rule candidates | — | **0** |
| Replays run | — | **0** |
| Max independent groups behind any claim | 1 | **1** |

**Output rose 5.6×. Progress was exactly zero.** The review's own headline — *"breadth success, depth failure"* — is the most valuable sentence in the repository, because it names the substitution while it was happening rather than after.

That review also identified the mechanism: **the binding constraint stopped being knowledge around ingestion #4 and has been authorization ever since.** Ingestions 5 through 10 could not have produced progress no matter how well executed. They were the available work, not the useful work.

> **This is the permanent lesson: when the binding constraint is not what you are working on, working harder produces output and nothing else.**

---

## 3. Failure — how MOGO could look successful while getting weaker

Organized by which level they corrupt. **Nine of these have already occurred here, and are marked.** That is not an indictment; it is the evidence that this list is real rather than theoretical.

### Corrupting the corpus

| # | Failure mode | Signature |
|---|---|---|
| **F1** | **Breadth substituting for depth** ⚠️ *occurred* | Everything grows; confidence never moves |
| **F2** | **Untestable accumulation** ⚠️ *occurred* | 641 hypotheses registered, **0 testable now**. Corpus grows; answerable questions do not. |
| **F3** | **Provenance decay** | The graph outruns the provenance. Statements survive their justifications. |
| **F4** | **Canonical drift** | More educators, less consistent vocabulary. Concepts multiply until they distinguish nothing. |
| **F5** | **Specification thinness masked by richness** ⚠️ *present* | **6 of 41 ALEX rules are deterministic.** The register reads as comprehensive; the method is described richly and specified thinly. Descriptive richness is read as precision. |
| **F6** | **Corpus survivorship** | Ingesting only educators who agree; running only campaigns likely to succeed. Invisible, because everything you did worked. |

### Corrupting evidence

| # | Failure mode | Signature |
|---|---|---|
| **F7** | **Replay theatre** | Campaigns that answer no pre-registered question. Volume rises; uncertainty does not fall. |
| **F8** | **Censoring blindness** ⚠️ *present* | **15 of 39 setups suppressed, outcomes unobserved, suppression non-random.** The sample looks like 24 clean observations. It is a biased draw from 39. |
| **F9** | **Measuring the instrument, not the world** | More evidence from one mechanism over one dataset measures that mechanism ever more precisely — and says nothing more about markets. |
| **F10** | **Ceiling erosion** | Treating a categorical ceiling as a confidence discount. *"500 replay trades is basically validated."* |

### Corrupting knowledge

| # | Failure mode | Signature |
|---|---|---|
| **F11** | **Confidence inflation** | Confidence rising from restatement, familiarity, or elapsed time rather than observation |
| **F12** | **Self-corroboration** ⚠️ *structural risk* | One source repeating itself counted as corroboration. **Independence ceiling still 1.** |
| **F13** | **Knowledge laundering** ⚠️ *live risk* | **9 rules no source states; 7 MOGO-authored.** Without a permanent discriminator these become educator knowledge within a decade — silently and irreversibly. |
| **F14** | **The ratchet** ⚠️ *structural* | Knowledge only accumulates. **Zero demotions have ever occurred**, and until recently no demotion path existed. |
| **F15** | **Threshold erosion** | Standards relaxed after seeing results. Each individual relaxation is defensible; the sequence is fatal. |
| **F16** | **Post-hoc drift** | Exploratory findings retold as confirmatory. The gap closes silently over a few retellings. |

### Corrupting the system itself

| # | Failure mode | Signature |
|---|---|---|
| **F17** | **The uncorrected falsehood** ⚠️ *occurred* | Evidence falsified a documented claim; **the claim still stands in two documents and remains citable.** A research system that does not correct itself accumulates disproven beliefs it keeps citing. |
| **F18** | **Governance theatre** | Gates that always pass. Five gates approved in one sitting is one gate. |
| **F19** | **Tooling substituting for science** ⚠️ *live risk* | Building the apparatus becomes the work. **Reviewable, satisfying, and produces no evidence.** |
| **F20** | **Metric proliferation** | Enough measures that something always looks good |
| **F21** | **Complexity accretion** | The model outgrows its single operator. Shortcuts appear. The shortcuts become the real process. |

### The two most dangerous, and why

**F19 — tooling substituting for science** — because it is the failure mode MOGO is *currently most exposed to*. The architecture is excellent and the evidence base is one run. Every hour spent on architecture is defensible, produces visible artifacts, and reduces uncertainty by zero.

**F13 — knowledge laundering** — because it is the only one on this list that is **irreversible**. Every other failure can be detected and repaired later. Once educator-asserted and MOGO-authored content are indistinguishable, no future work recovers the distinction. The information is simply gone.

---

## 4. Research velocity — the hierarchy

### The single true measure

> **Uncertainty reduced per unit of authorized evidence.**

Everything else is a proxy, and every proxy has a corruption mode. The hierarchy below is ordered by how closely each tracks the true measure and how badly each corrupts when used as a target.

| Rank | Measure | Status | Corruption when targeted |
|---|---|---|---|
| **1** | **Uncertainty reduced** | The true measure | Gameable by declaring wide priors — mitigated because thresholds are pre-declared |
| **2** | **Hypotheses adjudicated** *(any outcome)* | **The best usable proxy** | Mild: encourages easy questions. Acceptable. |
| **3** | **Knowledge demoted** | **A health indicator** | Almost none — nobody games for demotions |
| **4** | **Questions closed / concepts clarified** | Enabling work | Encourages closing easy questions |
| **5** | **Statistical power achieved** | **Capacity, not progress** | Encourages collection without adjudication |
| **6** | **Evidence packages produced** | Input | Rewards volume over relevance |
| **7** | **Replay volume** | ❌ **Reject as a metric** | Measures spend. Perfectly gameable. |
| **8** | **Knowledge promoted** | ❌ **Reject — most dangerous** | See below |

### Why "knowledge promoted" must be rejected, explicitly

You asked me to reject metrics that create incentives weakening rigor. **This is the one.**

Every control in MOGO's governance model exists to make promotion *hard*: pre-declared thresholds, evidence-class ceilings, multiplicity correction, intervals, minimum samples, decision gates. **Measuring promotion rate places continuous pressure against every one of them simultaneously.**

The pressure does not arrive as a decision to cheat. It arrives as a series of reasonable-sounding judgments: *this threshold was always conservative* · *the ceiling is really more of a guideline* · *the interval barely includes zero* · *we've been collecting for months*. Each is arguable. The sequence is F15.

> **Promotion is an outcome. It must never be a target.** A year in which MOGO promotes nothing and refutes six things is a better year than one in which it promotes six things and refutes nothing.

### Why demotion belongs at rank 3

Counterintuitive and load-bearing:

> **A research system that has never demoted anything is either very young or not looking.**

Demotion is evidence that the corrective machinery works. It cannot be gamed — nobody manufactures demotions for credit. And its absence over time is one of the few unambiguous warning signs available. **MOGO's demotion count is currently zero, which is presently honest — nothing has been promoted — and becomes a red flag the moment anything is.**

### Refutation must be weighted at least equally with support

Per unit of evidence, **refutation is cheaper and more permanent**. It removes something from consideration forever. Support is always provisional and always ceiling-bound.

If velocity counts only supports, the system learns to test only what it expects to confirm — **F6, and it is invisible from the inside**, because every campaign succeeded.

### The velocity question that actually matters

Not *"how much did we do?"* but:

> **"What do we know now that we did not know a year ago — including things we now know we were wrong about?"**

If that question has no answer, the year produced output. It did not produce research.

---

## 5. Knowledge quality

Ranked by meaningfulness, not by ease of measurement — and the most meaningful is the hardest.

### 1. Calibration — the gold standard

**Do things MOGO says it is confident about turn out to be true at the implied rate?**

The only quality measure that **cannot be gamed by working harder**, because it compares stated belief against outcomes MOGO does not control.

**Currently unmeasurable, and will be for years.** It requires promoted knowledge and elapsed outcomes; MOGO has neither. This must be stated plainly rather than substituted around — **and the substitutes must never be mistaken for it.** Everything below is a proxy for a thing MOGO cannot yet see.

### 2. The independence ceiling

**The maximum number of genuinely independent groups behind any single claim.**

> **Currently: 1. After twelve sources and five educators.**

This is the single most diagnostic number in the repository. While it remains 1, **no amount of further ingestion can move any claim to supported** — a structural fact, not a matter of effort. It is the number that tells you which constraint is binding.

### 3. Provenance completeness

**What fraction of statements can be traced to something that exists in the world?**

Must be near 100% and must be *checked*, not assumed. It degrades silently, and it degrades fastest exactly when the corpus is growing fastest.

### 4. The answerable fraction

**Of registered questions, what fraction could be answered with currently available modalities?**

> **Currently: approximately zero. Of 41 structured hypotheses, `TESTABLE_NOW` = 0.**

A corpus where this fraction is falling is accumulating questions faster than capability — **F2**. A novel indicator, and one of the most honest available, because it cannot be improved by adding questions.

### 5. Specification density

**Of formalized rules, what fraction are deterministic — mechanically evaluable as stated?**

> **Currently: 6 of 41. Fifteen percent.**

This is the number that distinguishes a rich description from a testable method, and its absence is invisible in prose. A register can read as comprehensive at 15%.

### 6. Reproducibility rate

**What fraction of derived figures can be regenerated exactly from their inputs?**

Anything that cannot be regenerated is not derived — it is authored, and it is misrepresenting its own nature.

### 7. Contradiction retention

**Are disagreements preserved, or quietly resolved?**

Cross-educator contradiction is the most informative signal a multi-educator library produces. A falling contradiction count usually means the library is smoothing, not converging.

### 8. Correction latency

**Time from evidence falsifying a MOGO document to that document being corrected.**

> **Currently: unbounded. A falsified claim remains asserted in two documents.**

The purest measure of whether the self-correction loop is real or aspirational — because correcting your own prior work is the least rewarding task available, and therefore the first one skipped.

### 9. Demotion responsiveness

**Time from contradicting evidence to demotion.** Not measurable until something is promoted, and the first measurement will be the most informative one MOGO ever takes about itself.

---

## 6. Scientific maturity

### The three levels

| | **Immature** | **Competent** | **Mature** |
|---|---|---|---|
| **Core capacity** | Accumulates | **Tests** | **Self-corrects and knows its own error rate** |
| **Confidence** | Rises monotonically | Moves in both directions | **Calibrated** — matches outcomes |
| **Negative results** | Not recorded | Recorded | Actively sought |
| **Provenance** | Partial, decaying | Complete, checked | Complete, and its own completeness is measured |
| **"We don't know"** | Uncomfortable, avoided | Recordable | **Routine, precise, and unembarrassing** |
| **Demotion** | Impossible | Possible | Regular |
| **Self-knowledge** | Cannot say what it doesn't know | Can enumerate its gaps | **Can predict where it is likely to be wrong** |
| **Failure** | Invisible | Detected afterwards | Anticipated |

The transitions are sharper than the levels:

**Immature → Competent** is crossed the first time a negative result is recorded and kept.
**Competent → Mature** is crossed when the system's stated uncertainty becomes trustworthy enough that **a third party could act on it without independently re-verifying** — which requires calibration, which requires years of outcomes.

### Where MOGO sits

Honestly, and in two parts, because MOGO does not sit in one place:

> **MOGO's machinery is at the upper end of competent, approaching mature. MOGO's knowledge is unambiguously immature.**
>
> **It is a well-built instrument that has not yet taken a measurement.**

**The machinery** — immutable provenance, content-addressed integrity, deterministic run identity, a protected-logic boundary with zero drift across ten commits, 943 fixtures, an eighteen-stage promotion ladder, declared thresholds, evidence-class ceilings, pre-registration policy, a demotion path now designed. Much of this exceeds what most working research programmes maintain.

**The knowledge** — one replay run. Twenty-four trades. Zero hypotheses adjudicated. Zero confidence-state changes across ten ingestions. Independence ceiling of 1. Zero testable hypotheses. Nothing validated, and nothing close.

### The specific danger of this position

This combination is not neutral. It is the **highest-risk configuration a research system can occupy**:

> **A system with excellent apparatus and no results is under maximum pressure to produce results, and possesses every tool required to make weak results look rigorous.**

Confidence intervals, correction procedures, provenance chains, and integrity hashes are **equally capable of dressing a thin conclusion as of establishing a sound one.** The machinery does not know which it is being used for.

**The mitigation is not more machinery.** It is the discipline of letting the apparatus sit idle — of writing "insufficient" and shipping it — until real evidence arrives. **The next genuine milestone in MOGO's maturity is not a promoted rule. It is the first adjudicated hypothesis, whatever the answer, followed by the first demotion.**

---

## 7. Stopping conditions

### When there is enough evidence for a hypothesis

**The stopping rule is declared at pre-registration or it does not exist.**

*"Collect until it resolves"* is not a stopping rule. It is optional stopping, and under optional stopping a null effect will eventually cross any threshold with probability approaching one. **A system that keeps collecting until it sees what it wants will always eventually see it.**

Four legitimate terminations:

| Condition | Outcome |
|---|---|
| Declared sample reached; interval excludes the threshold | **Adjudicate** — supported or refuted |
| Declared sample reached; interval includes zero at adequate power | **`INCONCLUSIVE` — and this is a real answer.** No detectable effect at this power. Stop. |
| Declared sample unreachable in principle | **Futility. Stop before starting.** |
| Effect size below detectable resolution | **`UNTESTABLE_IN_PRINCIPLE`.** Not a failure. |

> **The most under-used stopping condition is futility.** If the achievable sample cannot resolve the effect size you care about, the campaign should never be authorized. Recognizing that *before* spending is the cheapest scientific act available — and it is almost never performed, because declining to run a campaign feels like doing nothing.

### When additional replay has diminishing scientific value

The crisp answer:

> **Replay's value collapses the moment the binding constraint shifts from *sample size* to *ceiling*.**

Below that point, more replay narrows intervals and buys real information. Above it, more replay buys precision about a number that **cannot be promoted regardless of how precise it becomes.** The evidence class, not the sample, is what binds — and no quantity of the same modality escapes it.

Three further diminishing-return signals:

1. **Arithmetic.** Intervals narrow as one over the square root of n. The fourth doubling costs eight times the first and buys half its predecessor's gain.
2. **You are measuring the instrument.** More runs on one mechanism over one dataset measure that mechanism more precisely and the world not at all.
3. **Censoring dominates.** Once bias from suppression exceeds sampling variance, **more data makes the estimate more precisely wrong.**

### The stopping condition for MOGO as a whole

There is none. But there is a **pausing** condition:

> **When the binding constraint is not what you are working on, stop working and change the constraint.**

Ingestions 5 through 10 were work performed against a constraint that was no longer binding. Recognizing that is worth more than any of them.

---

## 8. Continuous improvement over years

### What must remain stable

Change to any of these should require the same deliberation as the original decision, and should be rare enough to be memorable.

- **The invariants** — immutability, provenance, pre-registration, ceilings, demotion, and the legitimacy of "unknown"
- **The separation of vocabulary, testimony, mechanism, proposition, observation, and knowledge**
- **The three confidences** — integrity, attestation, epistemic — never summed
- **The provenance-class discriminator**
- **The gates** — and especially their *count*
- **The asymmetry** — refutation is cheap, support is expensive

### What must evolve

- **Vocabulary** — concepts split and merge as understanding sharpens. Continuously.
- **Thresholds** — by explicit, recorded, forward-looking decision. **Never retroactively.**
- **Modalities** — new evidence types arrive with their own ceilings
- **Markets, instruments, asset classes, educators** — through existing entities, never through new ones
- **Tooling** — freely
- **What is known** — necessarily and constantly

### Controlling complexity — three budgets

**The entity budget.** A new entity type requires demonstrating that no existing entity can carry the responsibility. The default answer is no.

**The gate budget.** Gates may only be added by explicit decision, never by drift. Every stage will eventually attract a proposed checkpoint; the burden of proof sits permanently with the addition.

**The annual subtraction.** Each year, something must be **removed** — a control that never fires, an artifact nobody reads, a distinction that never distinguished. A system that only adds becomes inoperable, and an inoperable system is not followed. It is worked around.

### The constraint that governs all three

> **MOGO must remain operable by one person having a bad week.**

This is not a concession to convenience. **Rigor that only holds when the operator is sharp is not rigor — it is a description of good days.** A process requiring perfect discipline will be abandoned exactly when conditions are worst, which is precisely when its protection matters most.

The controls that survive this test are the ones that are **structural rather than behavioural**: immutability that cannot be violated by forgetting; a timestamp that cannot be backdated; a ceiling that is categorical rather than a matter of judgment. **Prefer a control that works when nobody is watching over one that works when everyone is.**

---

## 9. Metrics considered and rejected

You asked me to reject any metric whose incentives would weaken rigor. These are the rejections and their reasons.

| Rejected metric | Why it corrupts |
|---|---|
| **Knowledge promoted** | Applies continuous pressure against every control that exists to make promotion hard. **The single most dangerous metric available to MOGO.** |
| **Replay volume** | Measures spend, not learning. Perfectly gameable, and expensive to game. |
| **Corpus size** — claims, hypotheses, sources | **Already demonstrated here to be uncorrelated with progress.** 47 → 264 claims, zero confidence movement. |
| **Graph size** | Grew by ~89,000 edges with no knowledge gain. Measures bookkeeping. |
| **Educator coverage** | Directly incentivizes F1 — breadth over depth. One educator taken fully to standard beats three taken partially. |
| **Average or total confidence** | Invites inflation, and structurally penalizes the demotions that indicate health. |
| **Percentage of hypotheses supported** | **Subtle and severe:** incentivizes testing only what you expect to confirm — F6 — which is the precise inversion of science. |
| **Time to promotion** | Applies speed pressure to the one process that should be slow. |
| **Test or fixture count** | Measures machinery. MOGO has 943 fixtures and one measurement. |

**Accepted with a stated caveat:** *uncertainty reduced* is gameable by declaring artificially wide priors. It survives only because thresholds are pre-declared and timestamped before evidence exists — **the metric is safe only because the gate is real.** If pre-registration ever weakens, this metric becomes as corruptible as the rest.

---

## 10. The permanent scientific success principles

Timeless. True regardless of which educators are studied, which markets or asset classes are added, which engines are built, or how capable the tools become.

---

**S1 — The objective is calibrated uncertainty, not accumulated knowledge.**
Knowledge is a byproduct. Being right about how much you know is the goal.

**S2 — Progress is change in uncertainty, not change in volume.**
Everything grew and nothing moved is a warning, not an achievement.

**S3 — A system that cannot lose confidence is not a research system.**
Demotion is the defining capacity, not a safety feature.

**S4 — Refutation is progress, and usually the cheapest kind available.**
It is permanent, it is inexpensive, and it removes something from consideration forever.

**S5 — "We don't know," stated precisely, outranks "we believe," stated vaguely.**
Unknown is a valid, permanent, comfortable outcome. A system embarrassed by it will eventually manufacture the alternative.

**S6 — Never measure what you most want, if measuring it would corrupt it.**
Promotion is an outcome. It is never a target.

**S7 — The conversion rates between activity, output, evidence, knowledge, and progress are the diagnostic. The levels are not.**
Every level is easy to inflate by doing more of the level below.

**S8 — Machinery is not maturity.**
An excellent instrument that has taken no measurement has proved only that it can be built.

**S9 — When the binding constraint is not what you are working on, working harder produces output and nothing else.**
Identify the constraint first. Then work.

**S10 — Every stated confidence is a testable prediction about the world, and will eventually be tested.**
Calibration is the only quality measure that cannot be gamed by effort.

**S11 — A control that never fires is not a control.**
A gate that always passes is documentation.

**S12 — Complexity must be paid for by removed complexity.**
The system must remain operable by one person on their worst day, or it will be worked around exactly when it matters.

**S13 — Prefer controls that work when nobody is watching.**
Structural beats behavioural. A timestamp that cannot be backdated beats a policy that must be remembered.

**S14 — Nothing self-corroborates — not a source, an educator, a mechanism, a dataset, or a campaign.**
Repetition is not independence, at any volume.

**S15 — Knowledge decays. Time is a variable.**
Every belief carries an expiry. Markets change, regimes pass, data is revised. A belief nobody will revisit is a belief nobody is responsible for.

**S16 — Correcting yourself is the least rewarding and most important work the system does.**
It will always be the first thing skipped, and its absence is the clearest sign a research system has stopped being one.

---

## 11. Challenging my own conclusions

**C1 — "Calibrated uncertainty" is unmeasurable for MOGO today, and will be for years.** I have made the primary objective something that cannot currently be evaluated. The proxies in §5 are genuine but they are proxies, and the risk is that one gets promoted to the objective through repetition. **Whenever a proxy is reported, it must be labelled as one.**

**C2 — The velocity hierarchy has a lower bound problem.** With zero adjudications, ranks 1–4 are all zero, and the only non-zero measures are the ones I rejected. **A system with nothing to report on the good metrics is under real pressure to report the bad ones.** The honest response is to report zero, and to name the constraint.

**C3 — "Refutation is cheap" is true per unit of evidence and false in practice**, because refuting requires the same authorization, campaign, and analysis as supporting. The asymmetry is epistemic, not operational, and I should not let the framing suggest refutations are easy to obtain here.

**C4 — The maturity assessment may be too flattering to the machinery.** Calling it "approaching mature" rests on controls that have never been stressed by a real result. **A gate that has never blocked anything has not been tested.** The honest revision: the machinery is *well-designed*, and its maturity is unproven.

**C5 — S12 and rigor are in genuine tension.** "Operable on a bad day" and "maximally rigorous" pull against each other, and I have not resolved it — I have asserted a preference for the simpler control. That preference could be wrong in specific cases, and each case should be argued rather than assumed.

**C6 — This document is itself an instance of F19.** Four sessions have produced architecture, methodology, a domain model, an implementation plan, and now a philosophy of success. **They have produced no evidence.** All of it is defensible and none of it has reduced uncertainty about a single trading claim.

> That is acceptable **once**, as foundation. It stops being acceptable the moment it becomes the pattern.
>
> **The next thing MOGO produces should be a measurement.**

---

**Nothing has been implemented. No file was created or modified across this exchange. The implementation plan remains at Milestone 0, awaiting your approval.**

---
---

# PART VII — INDEPENDENT REVIEW

---

> **Framing as produced:** the review request was posed as an external architecture review by another
> AI. It was not. The document under review (Parts I–VI) was authored in the same session by the same
> assistant now reviewing it. That disclosure opens Part VII because it materially changes how the
> verdicts should be read.

**Verification done. Three of my own claims did not survive it.**

# Independent Review — MOGO-004 Architecture Review

## 0. Disclosure

I authored the document under review. Every argument in it was one I found persuasive when writing it, which is precisely the bias a reviewer is supposed to lack. I have compensated the only way available: re-deriving the factual claims from the repository rather than from memory. Three failed. They are reported first, because a review that opens with praise for its own work is worthless.

---

## 1. Verification results

### Claims that FAILED re-verification

**❌ V1 — The "9 unsupported + 7 MOGO-authored" figure is a double-count.**

The document repeatedly pairs these as two populations (Part III, Part V M2, Part VI F13), implying ~16 rules of KEREV-B exposure. Verified:

```
register UNSUPPORTED (9): AXR-021,022,060,061,062,063,081,091,092
join     UNSUPPORTED (7): AXR-021,022,060,061,062,063,091
overlap:                  7 — the join set is a strict SUBSET
```

**It is one population of 9.** The 7 is the same rules counted at a later pipeline stage. Real KEREV-B exposure is **9 of 41 rules (22%)**, not the ~16 (39%) the phrasing implies. **The document overstates its most-emphasized risk by roughly 1.8×.**

**❌ V2 — The provenance-class firewall is already partially built.**

Part V M2 presents provenance class as a new discriminator to be introduced. Verified — every one of the 41 register rules already carries an `authorship` field:

```
authorship: {EDUCATOR: 31, UNSUPPORTED: 10}
```

M2 is **PARTIALLY IMPLEMENTED**, not absent. What is genuinely missing is narrower: `UNSUPPORTED` conflates *"MOGO invented this"* with *"we asked a question no source answers"* — two very different things — there is no `CONVERGENT` class, no integrity check, and no propagation downstream. **M2 shrinks from a milestone to roughly a day's work.**

**❌ V3 — Three of six "missing" entities already exist.**

Part III lists six entities as missing and claims *"each closes a gap I can point to in the current repository."* Verified against the graph build:

| Entity I called missing | Reality |
|---|---|
| `Open Question` | **Exists** — `EVIDENCE_QUESTION` 281, `KNOWLEDGE_GAP` 110, `UNRESOLVED_QUESTION` 35, with schemas |
| `Contradiction` | **Exists** — `CONTRADICTION_RECORD` 16, with schema |
| `Decision` | **Exists** — `OWNER_DECISION` 6, with schema |
| `Metric Definition` | **Partially exists** — 6 metrics live inside the join and the hypothesis registry |
| `Dataset` | Genuinely absent |
| `Investigation Protocol` | Genuinely absent |

**Two genuinely missing, not six.** The sentence is wrong as written.

### Claims that HELD

| Claim | Verification |
|---|---|
| 943/943 JS, zero drift | Re-run: ✅ |
| 6 Python failures across 8 modules (451 tests) | Re-run: ✅ |
| No `EVIDENCE_PACKAGE`/`REPLAY_RUN`/`CAMPAIGN` node | ✅ graph has 16 node types, none of these |
| 6 of 41 rules deterministic | ✅ `deterministicCount: 6` |
| 552/641 placeholder hypothesis tests | ✅ |
| `TESTABLE_NOW = 0` | ✅ |
| R4/R8 replay gate blockers still open | ✅ source-verified at 12.18.0 |
| 15 of 39 setups suppressed | ✅ |
| **Independence ceiling = 1** | ✅ **and stronger than stated** — see below |

**The independence claim came back stronger, not weaker.** Groups key on author: `AUTHOR|ALEX_G` 280 links, `AUTHOR|TJR` 86, `AUTHOR|RAYNER_TEO` 50. Max distinct groups behind any of 341 claims: **1**. Because grouping is by author, **no quantity of additional ALEX_G material can ever raise a single ALEX claim above 1.** Four rules have 2–3 distinct *sources* and still sit at one group. This is the hardest structural fact in the repository and the document under-sells it.

---

## 2. The ten claims, classified

| # | Claim | Classification | Where / what's missing | Priority | Measurable benefit |
|---|---|---|---|---|---|
| 1 | **Rule Statement vs Mechanism** | **PARTIALLY IMPLEMENTED** | Already real: canonical rule register (educator side) vs fidelity matrix + `alex_g_sr_v1` (code side), with `lineageWarning` enforcing non-merge. Missing: it's convention across two artifacts, not one enforced model | **Low** | Prevents KEREV-B laundering — but the existing scope warnings already do most of this |
| 2 | **Observation-first (candidates/rejections)** | **NOT IMPLEMENTED — and the best idea in the document** | `alexGRunSetupReplay` returns a session-only `rejected[]` array; 15 suppressions recorded only as an aggregate count in the run record. No durable per-candidate observation | **HIGH** | Directly fixes informative censoring. Without it every future statistic is a biased draw. **The only item that improves evidence quality itself** |
| 3 | **Provenance classes** | **PARTIALLY IMPLEMENTED** (V2) | `authorship: EDUCATOR/UNSUPPORTED` exists on all 41. Missing: MOGO_AUTHORED vs open-question split, `CONVERGENT`, integrity check, propagation | **Medium** | Small and irreversible-if-omitted. ~1 day, not a milestone |
| 4 | **Knowledge demotion** | **NOT IMPLEMENTED** | 18-stage `PromotionState` is monotonic; no demotion transition exists | **Low now, mandatory before first promotion** | Zero benefit today (nothing is promoted). Build it the day before it's needed, not now |
| 5 | **Separate confidence dimensions** | **IMPLEMENTED** | Already the repo's design — four confidence dimensions "never collapsed into one"; `contentHashProvenance` separate from claim confidence; ADR-008 promotion gate separate again | **None — already done** | The document restates existing architecture as if proposing it |
| 6 | **Replay evidence ≠ truth** | **IMPLEMENTED** | `MOGO-003-VERIFIED-REPLAY-RECORD.md` §0 evidence classes; `REPLAY_EVIDENCE_ONLY` ceiling in the join; `STATISTICAL-GOVERNANCE.md` §6 | **None — already done** | Restated, not added |
| 7 | **Campaign abstraction** | **NOT IMPLEMENTED** | No campaign or protocol entity anywhere | **Medium** | The frozen timestamp is the only falsifiable pre-registration control. Real value — but a dated text file achieves 90% of it |
| 8 | **Graph/evidence bridge** | **NOT IMPLEMENTED** | Verified absent. The join is a flat generated adapter | **Medium-High** | Unblocks 4 of 6 target questions. **But note: the join already answers them for ALEX today.** Value is generality, not capability |
| 9 | **Pilot replay before campaign** | **ALREADY PLANNED, unexecuted** | `REPLAY-CAMPAIGN-PLAN.md` C3 exists; the document reorders it to first | **HIGHEST** | Retires the largest verification gap. Nothing since v12.9.0 browser-tested |
| 10 | **Protected-code boundaries** | **IMPLEMENTED** | 63 functions + 4 constants, zero drift verified again today; enforced by `run_all.sh` and `test_phase7a` | **None — already done** | The document correctly requests no change here |

**Summary: 4 already implemented. 3 partially. 3 genuinely absent.** The document presents considerably more novelty than it delivers.

---

## 3. Challenging the architecture

### Unnecessary complexity

**The 15-stage / 5-gate workflow (Part IV).** For a solo operator with 24 trades of evidence and zero adjudicated hypotheses, this is a process designed for a research lab. The document itself concedes this at the end and offers *"four gates, three artifacts, one rule."* **That compression is the actual deliverable; the preceding fifteen stages are exposition.** Part IV should be cut to its final section.

**Twenty-plus domain entities (Part III) for a system with one measurement.** Several duplicate what exists (V3). `Terminology Binding` and `Metric Definition` as new entities are pure premature abstraction — one is a field on a mapping, the other already exists inside the join.

### Premature abstractions

**`Campaign` generalized over modality.** Justified as future-proofing against modalities that don't exist. MOGO has one. Generalizing over a set of size one is speculation, not design. **A dated pre-registration text file delivers the falsifiable timestamp at ~2% of the cost.**

**`Dataset` as a first-class entity.** `datasetHash` already exists and works. Promoting it to an entity buys asset-class portability MOGO will not need for years.

### Duplicated concepts

Three entities already exist under other names (V3). Building them again creates a second vocabulary for the same idea — **the exact failure the document itself diagnoses** when it criticizes two competing hypothesis status vocabularies. It then proposes doing it again.

### Hidden maintenance costs

Concept mapping is per-claim operator work forever. `GLOSSARY.md` and `CROSS-STRATEGY-ANALYSIS.md` become generated, so their generators become permanent dependencies. The graph build grows from 16 to ~21 node types.

### Governance that creates friction

**Pre-registration for measurement campaigns.** The document invents a "lightweight lane" to solve friction its own gate created. Simpler: pre-registration applies to promotion-eligible campaigns only. Exploratory measurement needs no gate because it can never promote.

### Where evidence generation is slowed

**M5–M7 (concepts + hypothesis reconciliation) is the bulk of the plan and, by the document's own repeated admission, does not fix the binding constraint.** It says so three times — Part II Q1, Part II Q8, Part VI §5 — and then schedules it as three of eleven milestones anyway. **That is the central incoherence in the document.**

### Where rigor is genuinely improved

1. **Observation-first.** The only proposal that improves the evidence itself.
2. **Pre-registration timestamp.** Cheap, falsifiable, irreplaceable.
3. **The correction loop.** A falsified claim still stands in two documents; that is a verified live defect.
4. **Ceilings as categorical.** Already policy; the document hardens the framing correctly.

### Where cost outweighs ROI

M5, M6, M7, M9, M10. Roughly half the plan, for benefits that are organizational rather than evidential.

---

## 4. ROI analysis

| Component | Complexity | Benefit | ROI | Keep? |
|---|---|---|---|---|
| **M0 stabilization** | Low | High — 6 red tests, 134k uncommitted lines | ★★★★★ | **Yes — immediately** |
| **Pilot replay + browser verification** | Medium | Very high — retires the largest gap | ★★★★★ | **Yes — first real work** |
| **Observation-first capture** | Medium | Very high — fixes censoring | ★★★★★ | **Yes** |
| **Provenance split (reduced M2)** | Very low | Medium, irreversible if skipped | ★★★★☆ | **Yes — ~1 day** |
| **Correction loop (fix B1)** | Very low | Medium | ★★★★☆ | **Yes — hours** |
| **Pre-registration as a dated file** | Very low | High | ★★★★★ | **Yes** |
| **ADR-012 document** | Low | Medium — records decisions | ★★★☆☆ | Yes, but short |
| **Evidence bridge (M3)** | High | Medium — join already covers ALEX | ★★☆☆☆ | **Postpone** |
| **Campaign/Protocol entities (M4)** | Medium | Low over a dated file | ★★☆☆☆ | **Postpone** |
| **Concept registry (M5)** | Medium | Low — cannot move confidence | ★★☆☆☆ | **Postpone** |
| **Concept backfill (M6)** | High | Low — same | ★☆☆☆☆ | **Postpone** |
| **Hypothesis reconciliation (M7)** | Medium | Low — 641 records, 0 testable | ★☆☆☆☆ | **Postpone** |
| **Statistical Result entity (M8)** | Low | Medium — when results exist | ★★★☆☆ | Postpone until needed |
| **Knowledge lifecycle (M9)** | Medium | Zero today | ★☆☆☆☆ | **Postpone** |
| **Query surface (M10)** | Low | Low | ★★☆☆☆ | **Postpone** |
| **15-stage workflow (Part IV)** | — | Negative (friction) | ☆☆☆☆☆ | **Remove; keep the 4-gate compression** |
| **Success model (Part VI)** | — | Zero implementation content | ☆☆☆☆☆ | **Remove from the plan; keep as a preface** |

---

## 5. Reality check against your objective

> *"Build the shortest path toward becoming a consistently profitable trader using reproducible evidence."*

**Measured against that sentence, the document is roughly 30% on-target and 70% architectural sophistication.**

| Contributes | Does not contribute |
|---|---|
| Pilot replay + browser verification | Concept registry and backfill |
| Observation-first (censoring) | Campaign/Protocol entity modelling |
| M0 stabilization | Knowledge lifecycle machinery |
| Provenance split | Query surface |
| Correction loop | The 15-stage workflow |
| Pre-registration timestamp | The entire success-model philosophy |

**Flagged as sophistication without evidential improvement:** the concept layer (explicitly cannot move confidence), the campaign abstraction (generalizes over one modality), the domain-model expansion (duplicates three existing entities), the workflow (fifteen stages for a one-person operation), and Part VI (zero implementation content).

**The document's own Part VI §11 C6 says this**: *"Four sessions have produced architecture… They have produced no evidence."* It diagnosed itself correctly and then submitted an eleven-milestone plan anyway. **The self-criticism is accurate and was not acted on.**

---

## 6. Final deliverables

### 1. Executive summary

The analysis is strong and largely verifiable; the prescription is roughly twice the size the evidence justifies. Four of ten headline claims describe things MOGO already does. Three factual errors inflate the case for the work being proposed — most importantly a 1.8× double-count of the KEREV-B exposure and a missed existing `authorship` field. The genuinely valuable content is about one-third of the document: pilot replay, observation-first capture, stabilization, and a one-day provenance fix. The remaining two-thirds is well-argued architecture that the document itself repeatedly concedes will not move the binding constraint.

### 2. Strengths

- Claims are repository-grounded and mostly survive re-verification
- The independence-ceiling finding is correct and under-stated
- Informative censoring (15/39) is a real defect nobody had named
- The pilot-before-campaign reordering is correct and well-argued
- Protected boundaries respected throughout; zero authorization requested
- It criticizes itself accurately, including the tooling-substituting-for-science trap

### 3. Weaknesses

- Three factual errors, all inflating the case for more work
- Presents four already-implemented capabilities as proposals
- Schedules three milestones it argues won't help
- Fifteen stages and twenty entities for a one-person, 24-trade research system
- Recreates three entities that already exist — the duplication failure it diagnoses elsewhere
- Part VI is philosophy with no implementation content

### 4. High-priority recommendations

1. **Commit the working tree.** 134k lines at risk.
2. **Fix the 6 Python tests.** A red suite trains you to ignore it.
3. **Run the pilot replay with full browser verification.**
4. **Capture candidates and rejections durably** as part of that run.
5. **Correct the B1 falsehood** in both documents.

### 5. Low-priority recommendations

Evidence bridge · campaign/protocol entities · statistical result entity · query surface · knowledge lifecycle. All real; none urgent.

### 6. Should be removed

- The 15-stage workflow — keep only "4 gates, 3 artifacts, 1 rule"
- `Terminology Binding` and `Metric Definition` as new entities
- Recreation of `Open Question`, `Contradiction`, `Decision`
- Part VI from the implementation plan (keep as a preface)
- The "9 + 7" phrasing — correct to 9

### 7. Should be postponed

M4–M10 entire. Revisit M5/M6 at educator #3 with real material; M8/M9 when the first result exists; M3 when a second strategy needs the bridge.

### 8. Implement immediately

| Action | Effort |
|---|---|
| Commit working tree | Hours |
| Fix 6 Python tests + `TESTING.md` §4 | Hours |
| Split `authorship: UNSUPPORTED` into MOGO_AUTHORED vs OPEN_QUESTION + integrity check | ~1 day |
| Correct B1 in both documents | Hours |
| Write ADR-012 — short, decisions only | ~1 session |
| Pilot replay + browser checklist | 1–2 sessions ⭐ |

### 9. Architecture score: **6 / 10**

Analysis 8–9: verified, honest, surfaces real defects. Prescription 4–5: over-scoped, partly redundant, and internally inconsistent — it schedules work it argues is ineffective. Errors 5: three, all directionally favouring more work, which is the failure mode a self-review is least likely to catch and I only caught by re-querying the data. **The underlying architecture MOGO already has scores higher than the document proposing to extend it.**

### 10. Recommended implementation order

```
1. Commit tree · fix tests · correct B1              hours
2. Provenance split + integrity check                ~1 day
3. ADR-012 (short — decisions, not philosophy)       1 session
4. Pilot replay + browser verification ⭐             1–2 sessions
   └ capture candidates/rejections durably
5. Pre-registration as a dated text file             hours
6. Campaign C1 — only if step 4 is clean             the bulk
7. First adjudication, whatever the answer
── STOP. Re-evaluate M3–M10 against what you learned. ──
```

**The single most valuable change: stop at step 7 and reassess.** Every postponed milestone will be easier to scope correctly after one real adjudication than it is now, and several may prove unnecessary.

---

**Nothing implemented. No file modified in this review.** The three verified errors are in `docs/reports/MOGO-004-ARCHITECTURE-REVIEW.md` as committed to disk — say the word and I'll correct them in place.

---
---

# PART VIII — RUTHLESS REDUCTION (FIRST PASS)

---

**Ruthless means turning the knife on what I preserved last round. One verification first — it decides whether the censoring fix is free or expensive.**

**Finding 1 — the censoring fix is free.** `alexGReplayRejected = result.rejected` (`index.html:4119`, non-protected UI layer) populates a readable global after every run, with structured per-setup reasons including `EXISTING_OPEN_TRADE_SAME_PAIR_TIMEFRAME`. Capturing the unobserved is a console read and a file save. **Zero engineering.** I previously scoped this as a medium milestone.

**Finding 2 — my "irreversible" argument for provenance was wrong.** `authorship: {EDUCATOR: 31, UNSUPPORTED: 10}` already exists on all 41 rules, and a replay campaign creates no new rules. Nothing degrades by waiting.

*(Also confirmed authoritatively: all four replay functions — `alexGRunSetupReplay`, `alexGConstructTrade`, `alexGWalkOutcome`, `alexGComputeReplayStats` — are in the 63 `PROTECTED_FUNCTIONS`. Nothing below touches them.)*

---

# MOGO-004 — Ruthless Reduction

## REQUIRED NOW

Five items. **Roughly two sessions plus two hours, total.**

### R1 — Commit the working tree · 30 min
**Q1–3: No.** This improves no evidence. **Q4: No** — 134k lines of unversioned work is one mistaken command from gone. **Q5: Real.** Not research; insurance. Kept only because the downside is catastrophic and the cost is thirty minutes.

### R2 — Re-adjudicate the replay gate and correct B1 · ~1 hour
**Q1: Yes — this is a hard blocker.** `MOGO-RESEARCH-VALIDATION-STANDARD-V1.md` §3.3 currently reads *"❌ FAIL — ALEX v1.1 may not enter replay"* and §12.2 assigns **SUSPEND FOR DEFECT**. Its most serious blocker, R10, rests on the B1 claim that RUN-001's own evidence falsified. **You cannot honestly authorize a campaign while your own written standard forbids it.** Either correct the record or the campaign is ungoverned.

Output: one page. R12 closed by run identity; R4 and R8 confirmed open and converted into a stated scope of validity (*R-space valid; money-space and near-zero expectancy claims not*); R10 struck with the evidence cited.

### R3 — Write the pre-registration file · 30 min
**Q4: No — this is the one thing that literally cannot be done later.** A dated markdown file naming: pairs, lookback parameter, hypotheses under test, thresholds, family size, stopping rule, declared ceiling. Its value is entirely in its timestamp.

**Write the honest limitation into it:** replay fetches by candle count backward from run time, so the absolute window is *discovered, not chosen*. Declare the parameter, record the window afterwards, and never describe it as pre-selected.

### R4 — Pilot replay + browser verification · 1–2 sessions ⭐
**Q1: Yes, maximally.** Nothing since v12.9.0 has run in a browser. Units A/B/C1/C2 — every field the campaign exists to collect — are proven only in a harness with neither `crypto.subtle` nor `indexedDB`. One run of RUN-001's window on the current engine, under `scripts/browser_test_profile.sh` isolation, discharging the 10-item checklist.

### R5 — Save `alexGReplayRejected` after every run · 0 min engineering
**Q1: Yes.** RUN-001 suppressed 15 of 39 qualified setups, non-randomly. Without the rejection list, every statistic is a biased draw and no sample size fixes it. The array already exists post-run. **Read it, save it beside the packages, done.**

---

## DEFER

Each with the specific evidence that would justify revisiting it.

| Item | Why it can wait | Trigger to revisit |
|---|---|---|
| **Fix 6 Python tests** | Research-subsystem only. Drift is separately gated by `run_all.sh`, which is green. Blocks no campaign. | Next time you touch `docs/trader-intelligence/` — fix them in that session, not as a milestone |
| **Provenance split** (`UNSUPPORTED` → MOGO_AUTHORED vs OPEN_QUESTION) | `authorship` already separates EDUCATOR from UNSUPPORTED. A campaign creates no rules, so the ambiguity cannot grow. 10 records, fixable any time. | When educator #2's rules are formalized — i.e. when new rules would be created without the discriminator |
| **Evidence bridge / graph node types** | The join already answers the rule↔evidence question for ALEX today. The bridge buys generality you have no second consumer for. | When a second strategy has evidence packages |
| **Campaign / Protocol entities** | R3's dated file delivers the falsifiable timestamp — the only part that matters — at ~2% of the cost | When you have ~5+ campaigns and the files become unmanageable |
| **Statistical Result entity** | Zero results exist to record | The first adjudication |
| **Knowledge lifecycle / demotion** | Nothing is promoted. Demotion machinery guarding an empty set. | The day before the first promotion — not before |
| **Concept registry + backfill** | By its own design it cannot move confidence. Verified: max independent groups behind any of 341 claims is **1**, and groups key on author — so no ALEX material can ever raise an ALEX claim | `PROPOSAL-003`'s own stated trigger: the first claim meaning the same as an existing claim that doesn't near-duplicate-match |
| **Hypothesis model reconciliation** | 641 hypotheses, `TESTABLE_NOW = 0`. Reconciling vocabularies for records nobody will test | When a hypothesis is actually adjudicated and the current states can't express the outcome |
| **Query surface / readiness report** | You can answer all six questions by hand at this corpus size | When answering by hand takes longer than writing the query |

---

## REMOVE

| Item | Why it provides no measurable value |
|---|---|
| **ADR-012 as a milestone** | `docs/reports/MOGO-004-ARCHITECTURE-REVIEW.md` already records every decision and its rationale, on disk. Writing an ADR now duplicates it and creates a second normative surface — the exact defect the review criticises elsewhere. Write ADR-012 **when a decision is actually implemented**, describing what was built |
| **The 15-stage workflow** | Fifteen stages for a one-person operation with 24 trades. Its own final section — *"four gates, three artifacts, one rule"* — is the deliverable. The preceding fourteen pages are exposition |
| **The 20-entity domain model expansion** | Three of the six "missing" entities already exist (`CONTRADICTION_RECORD`, `EVIDENCE_QUESTION`/`KNOWLEDGE_GAP`, `OWNER_DECISION`). Building them again is duplication |
| **`Terminology Binding` · `Metric Definition` · `Dataset` · modality-generalized `Campaign`** | Four entities abstracting over: a field, something already inside the join, a hash that already works, and a set of size one |
| **Part VI success model as a plan input** | Zero implementation content. Useful as a preface to remind you what you're optimizing for; worth no engineering hours |
| **The "measurement campaign lane"** | Invented to relieve friction created by a gate that isn't being built. Deleting the gate deletes the problem |
| **The M0–M10 numbering** | Eleven milestones implies eleven milestones of work. There are five items and a campaign |

---

## Revised roadmap

**Objective: maximum trustworthy evidence, minimum engineering.**

```
STEP 0 — CLEAR THE DECKS                                    ~2 hours
  · Commit the working tree                                    0.5h
  · Re-adjudicate the replay gate; strike B1                   1.0h
  · Write the dated pre-registration file                      0.5h
  → Campaign is now governed. Nothing else blocks it.

STEP 1 — PILOT RUN ⭐                                    1–2 sessions
  · RUN-001's window, current engine, isolated profile
  · Discharge the 10-item browser checklist
  · Save packages + alexGReplayRejected + harvest
  → GATE: do the packages actually carry triggeredConditions,
    timeToMFE/timeToMAE, and market context?
       NO  → stop. Fix capture. Campaign would waste 11 runs.
       YES → proceed.

STEP 2 — CAMPAIGN C1                                       the bulk
  · 11 majors, same lookback parameter, one run each
  · Every run: packages + rejections + register entry
  → ~264 trades carrying attribution, timing, context

STEP 3 — FIRST ADJUDICATION
  · Run the pre-registered comparisons. Nothing else.
  · Report intervals, family size, suppression rate
  · Whatever the answer is, record it

── STOP AND REASSESS ──
Every deferred item is easier to scope after one real adjudication
than it is now. Several will prove unnecessary.
```

### What this cuts

| | Before | After |
|---|---|---|
| Milestones before first evidence | 11 | **0** — three short tasks |
| Engineering hours before the pilot | ~1 session (ADR) + 1 day (provenance) + M0 | **~2 hours** |
| New entities built | ~20 | **0** |
| New documents written | 12+ | **2** (gate re-adjudication, pre-registration) |
| Code changed | Python tooling across 11 milestones | **None** |

### The three things that must not be cut, at any pressure

1. **The pre-registration timestamp.** Retroactive is impossible. Thirty minutes.
2. **The rejection list.** Free, and without it every statistic is uninterpretable regardless of sample size.
3. **The Step 1 gate.** The pilot exists to be allowed to fail. If it passes automatically it wasn't a gate, and C1 spends eleven authorizations on unverified capture.

### The honest summary

Of the original review, **about 15% survives as required work** — and most of that is not engineering at all, but a commit, a correction, and a dated text file. The single highest-value evidence improvement turned out to cost nothing. Everything else waits for the evidence to justify it.

**Nothing implemented. Awaiting approval to begin Step 0.**

---
---

# PART IX — SECOND REDUCTION PASS

---

> **Provenance of this part.** The reduction prompt was issued twice, verbatim. Rather than restate
> Part VIII, the five questions were applied to **the five items Part VIII preserved** — the only
> unexamined ground remaining. Two shrank and one turned out not to be the blocker Part VIII called it.
> **Where Part VIII and Part IX disagree, Part IX is authoritative.**

# Second Reduction Pass

## What changed

**R2 is not a hard blocker.** I called the replay-readiness gate a blocker because it says *"ALEX v1.1 may not enter replay."* But that document is **uncommitted and its own status line reads "Proposed standard, awaiting Engineering Authority approval."** You are the Engineering Authority. An unapproved proposal forbids nothing. Authorizing the campaign *is* the adjudication.

What survives is narrower and sharper: **B1 is a claim that the zone engine cannot produce a validated never-broken resistance zone — i.e. a structural directional bias.** If that were true, the campaign's entire long/short distribution would be uninterpretable. RUN-001 falsified it (8 such zones, 3 `upThroughResistance` breaks). Striking it isn't governance hygiene; it removes a live doubt about whether the evidence you are about to collect means anything. **One paragraph, ~15 minutes.** Not a 13-item re-adjudication.

**R4's checklist cuts from 10 items to 6.** Four of the ten do not gate campaign evidence quality: cancelled-export marking, `file://` banner behaviour, backfill idempotency, journal byte-identity. Real checks, wrong moment. The six that decide whether C1 is worth running:

1. Capture produces a package with no user action
2. **The new fields actually populate** — `triggeredConditions`, `timeToMFE`/`timeToMAE`, market context
3. In-browser SHA-256 matches NIST vectors
4. Export → re-import → verify converges *(EXP-001's partial write already bit once at 24 files)*
5. Reload continues the sequence, no duplicate `packageId`
6. Quota pressure surfaces in Diagnostics *(264 packages ≈ 12.6 MB)*

**R1's justification was wrong.** I kept it as insurance against data loss. The real campaign-linked reason: **the pilot produces new files, and a dirty 134k-line tree makes it impossible to see what the run actually generated.** Same 30 minutes, but now it earns its place.

---

## REQUIRED NOW

| | Item | Cost | Why it cannot wait |
|---|---|---|---|
| **1** | Commit the working tree | 30 min | Otherwise the pilot's output is invisible in `git status` |
| **2** | Strike B1, citing RUN-001's evidence | 15 min | Removes a live doubt that the evidence is directionally corrupt |
| **3** | **Dated pre-registration file** | 20 min | **Physically impossible to do later.** Pairs, lookback, hypotheses, thresholds (30/100/0.25R), family size, stopping rule, ceiling |
| **4** | **Pilot run + 6 checklist items** ⭐ | 1–2 sessions | The only thing that produces evidence |
| **5** | Save `alexGReplayRejected` per run | **0 min** | Free; without it every statistic is a biased draw |

**Total prep before the pilot: ~1 hour.** Down from ~2.

### The irreducible floor

If everything else were cut under pressure, three things remain, and they are the ones with no substitute:

> **Write the pre-registration file. Run the pilot. Save the rejection list.**

Item 3 is unrecoverable if skipped. Item 5 is free. Item 4 is the work. Items 1 and 2 are 45 minutes of hygiene that make the output legible — do them, but they are not the floor.

---

## DEFER — unchanged from the previous pass

Fix 6 Python tests · provenance split · evidence bridge · Campaign/Protocol entities · Statistical Result entity · knowledge lifecycle and demotion · concept registry and backfill · hypothesis model reconciliation · query surface and readiness report.

Nothing in this pass changed their triggers. Each remains gated on a specific future observation — a second educator's rules being formalized, a second strategy having evidence, the first adjudication, the first promotion, `PROPOSAL-003`'s own stated near-duplicate trigger.

**One addition to this list:** the four deferred browser-checklist items above. Trigger: run them the next time the app is open in a verified isolated profile — they cost minutes once a session already exists.

---

## REMOVE — unchanged from the previous pass

ADR-012 as a milestone · the 15-stage workflow · the 20-entity domain-model expansion · `Terminology Binding` / `Metric Definition` / `Dataset` / modality-generalized `Campaign` · Part VI as a plan input · the measurement-campaign lane · the M0–M10 numbering.

**One addition:** the full 13-item replay-gate re-adjudication. It was scoped to answer a document that is unapproved and therefore not binding. Only the B1 strike survives, and only because B1 is a factual claim about the engine rather than a governance opinion.

---

## Revised roadmap

```
STEP 0 — CLEAR THE DECKS                                     ~1 hour
  · Commit the tree                                            30m
  · Strike B1 with the evidence                                15m
  · Write the dated pre-registration file                      20m

STEP 1 — PILOT RUN ⭐                                    1–2 sessions
  · RUN-001's window, current engine, isolated profile
  · 6 checklist items — not 10
  · Save packages + alexGReplayRejected + harvest
  → GATE: did triggeredConditions, timing and context populate?
       NO  → stop. C1 would waste 11 authorizations.
       YES → proceed.

STEP 2 — CAMPAIGN C1
  · 11 majors, same lookback, one run each
  · Every run: packages + rejections + register entry

STEP 3 — FIRST ADJUDICATION
  · Only the pre-registered comparisons
  · Intervals, family size, suppression rate
  · Record the answer whatever it is

── STOP AND REASSESS ──
```

### Cumulative reduction across both passes

| | Original review | After pass 1 | **After pass 2** |
|---|---|---|---|
| Milestones before evidence | 11 | 0 | **0** |
| Prep hours before pilot | ~2 sessions + 1 day | ~2 hours | **~1 hour** |
| Documents to write | 12+ | 2 | **1** (pre-registration) + one paragraph |
| Browser checklist items | 10 | 10 | **6** |
| Code changed | 11 milestones of Python | none | **none** |
| Entities built | ~20 | 0 | **0** |

**The honest floor is one 20-minute file and a replay run.** Everything else in six documents of architecture was either already built, freely available, or waiting on evidence that does not yet exist.

**Nothing implemented. Awaiting approval to begin Step 0.**

---
---

*End of MOGO-004 Architecture Review — Parts I–IX.*

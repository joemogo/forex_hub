# MOGO-002.6 — Engineering Review Package

**Milestone:** Knowledge Engineering & Strategy Normalization · **Status:** COMPLETE, awaiting Engineering Authority review
**Date:** 2026-07-29 · **HEAD:** `a332d04` (uncommitted)
**Authority decision executed:** OD-1, approved with modification

> **No draft rule produced by this milestone may affect paper trading.** Every rule is capped at
> `NEEDS_REVIEW` / `NORMALIZED`, enforced as a hard model error, not a convention.

---

## 1. Executive Summary

MOGO-002.6 built the Knowledge Engineering system and ran the full ALEX_G educator library through
it. **All 195 claims were inventoried, classified, and traced; 115 were eligible to become candidate
rules; 111 were normalized; and a DRAFT specification `alex_g_educator_v2_draft` now exists,
completely separate from the production `alex_g_sr_v1`, which is unchanged.**

**The headline is what normalization revealed about the library's quality.**

An early pass classified **188 of 195 claims as EXPLICIT**, which looked excellent and was
misleading. It read *how plainly the educator spoke*, not *whether the rule was complete*. After
applying the guard that a rule-shaped claim carrying a **blocking open question** is `UNRESOLVED`
however plainly it was worded, the honest distribution is **122 EXPLICIT / 66 UNRESOLVED / 7
DISCRETIONARY** — and **66 of 111 normalized rules carry a parameter the source never states.**
Only **41 of 111 rules are deterministic.**

**Three domains are simply not in this library, and no amount of re-analysis can produce them:**

| Domain | Claims | Normalized rules |
|---|---|---|
| **EXIT** | **0** | **0** |
| **STOP PLACEMENT** (within RISK) | **0** | **0** |
| DIRECTIONAL_BIAS, MARKET_CONDITIONS | claims present, no rule-shaped claims | 0 |

The 13 RISK rules are **all sizing**. Position size = risk ÷ stop distance, so **not one of them is
implementable**. This does **not** close MOGO-002.5's `GAP-RISK-001`; it confirms it from the other
direction — neither the production specification nor the educator library states where the stop goes.

**What the draft does add** is trade management (8 rules against production's 0), session
restrictions (7 against 0), and entry detail (27 rules). Those are genuine, educator-supported
additions to domains the production specification does not cover at all.

**One structural caution the Authority should carry forward:** where the draft and production
specifications cover the same domain, that overlap is **convergence, not derivation**.
`DECISION|MOGO|20260727|004` establishes that `alex_g_sr_v1`'s rules came from MOGO's own
implementation. Reading domain overlap as corroboration would be a lineage error, and it is recorded
as such in the delta.

**Validation:** 57/57 new KE tests · 63/63 MOGO-002.5 fidelity tests still pass · 591/591 JS
fixtures across 13 suites · **zero protected-function drift** · evidence store byte-unchanged (310
claims, 0 proposals) · production specification unchanged (13 rules, hash `a0b7641e288c1725`).

---

## 2. Repository-Truth Findings

**The library reconciles exactly.** 195 ALEX_G claims, 8 source artifacts, and **complete
provenance** — every claim reaches a verbatim excerpt and a registered source with a content hash
and verified URL. No stop condition triggered.

| Check | Result |
|---|---|
| ALEX_G claims | **195** (of 310 library-wide) |
| Source artifacts | **8**, all `partially_verified`, all with content hash + canonical URL |
| Claims with no evidence link | **0** |
| Claims whose evidence has no registered source | **0** |
| Claims with no verbatim excerpt | **0** |
| Existing `RuleCandidateProposal` records | **0** |

**An approved equivalent model already exists**, and the audit's most consequential finding is why
it could not be the write target. `RuleCandidateProposal` (ADR-009 §8) is created by
`extraction_pipeline.run_post_annotation_pipeline()` **only for claims that reach `supported`**. All
195 ALEX_G claims are at `emerging`. Writing proposals into `evidence/proposals/` would therefore
require either lowering that gate — violating `POLICY-001` — or bypassing the pipeline, which would
make `KNOWLEDGE-DASHBOARD.md` report a non-zero rule-candidate count and imply confidence movement
that has not happened.

**Resolution:** the KE system reads the evidence store and writes to its own location. Its
vocabularies, ID conventions and canonical-JSON utilities are reused rather than reinvented. A test
asserts the evidence store is byte-unchanged after a full generation run.

---

## 3. Files Added

| Path | Lines | Purpose |
|---|---|---|
| `scripts/knowledge_engineering/ke_model.py` | 422 | 14 domain objects, vocabularies, governance guards |
| `scripts/knowledge_engineering/ke_inventory.py` | 296 | Phase 3 — inventory + classification (read-only) |
| `scripts/knowledge_engineering/ke_analysis.py` | 355 | Phases 4–6 — duplicates, contradictions, normalization |
| `scripts/knowledge_engineering/build_ke_artifacts.py` | 399 | Phases 7–10 + 12 — draft, delta, coverage, queue |
| `tests/knowledge_engineering/test_knowledge_engineering.py` | 402 | 57 tests |
| `docs/knowledge-engineering/` | 21 files | 12 JSON artifacts + 9 Markdown reports |
| `docs/reports/MOGO-002.6_ENGINEERING_REVIEW.md` | this file | |

## 4. Files Modified

**None.** MOGO-002.6 modified no existing file.

- `index.html` — untouched by this milestone (`git diff --numstat` still shows MOGO-002.5's 113/0)
- `evidence/` — 310 claims, 0 proposals, byte-unchanged (asserted by test)
- `alex_g_sr_v1` — 13 rules, hash `a0b7641e288c1725`, unchanged

---

## 5. Claim Inventory Totals

| | |
|---|---|
| Source artifacts | **8** |
| Claims inventoried | **195 / 195** |
| Claims with full provenance | **195 / 195** |
| Claims with a verbatim excerpt | **195 / 195** |

## 6. Classification Totals

**By classification**

| Classification | Claims | | Classification | Claims |
|---|---|---|---|---|
| EDUCATIONAL_COMMENTARY | 34 | | RISK | 13 |
| ENTRY | 29 | | PSYCHOLOGY | 13 |
| TRADING_RULE | 23 | | INVALIDATION | 9 |
| NO_TRADE_CONDITION | 16 | | TRADE_MANAGEMENT | 8 |
| DEFINITION | 15 | | DISCRETIONARY_GUIDANCE | 7 |
| MARKETING | 14 | | SESSION | 7 |
| | | | TIMEFRAME / EXAMPLE / MARKET_CONTEXT / UNKNOWN | 3 / 2 / 1 / 1 |

**By explicitness** — `EXPLICIT` **122** · `UNRESOLVED` **66** · `DISCRETIONARY` **7**

> The 66 `UNRESOLVED` are the important number. Each is a rule the educator stated plainly and did
> not finish — a session rule whose hours are shown on screen, an EMA whose period is never spoken,
> a scoring scale whose maximum is unknowable from the transcript.

**Candidate-rule eligibility** — `ELIGIBLE` **115** · `NOT_ELIGIBLE` **80**

The 80 ineligible break down as: not a rule-shaped `claimType`, or classified `MARKETING` /
`PSYCHOLOGY` / `EDUCATIONAL_COMMENTARY` / `EXAMPLE` / `UNKNOWN` — content describing the educator or
the reader rather than a market decision. **Every one records its own reason.**

## 7. Candidate-Rule Totals

**115 candidate rules**, one per eligible claim except where a duplicate group recommended merging.

## 8. Normalized-Rule Totals

**111 normalized rules · 4 deferred.**

| | |
|---|---|
| Deterministic | **41 / 111** |
| Carrying an unresolved parameter | **66 / 111** |
| Approval status | **111 / 111 at `NEEDS_REVIEW`** |
| Maturity | **111 / 111 at `NORMALIZED`** |
| With a source mapping | **111 / 111** |

**By domain:** ENTRY 27 · SETUP 21 · NO_TRADE_CONDITIONS 14 · RISK 13 · INVALIDATION 9 ·
TRADE_MANAGEMENT 8 · DISCRETIONARY_ELEMENTS 7 · SESSION_RESTRICTIONS 7 · TIMEFRAMES 3 · LIQUIDITY 2
· **EXIT 0** · **DIRECTIONAL_BIAS 0** · **MARKET_CONDITIONS 0**

The 4 deferred candidates each carry **both** a contradiction and an unresolved parameter — a
canonical statement would have to invent one and pick a side of the other.

## 9. Duplicate Groups

**4 groups** at a 0.40 Jaccard threshold within a domain: **3 `DO_NOT_MERGE`**, 1
`MERGE_WITH_CAVEATS`.

The low count has a real cause, not a detection failure: **the ingestion pipeline already
deduplicated at claim level** via `compute_claim_fingerprint()`, and **36 of 195 claims already
aggregate more than one evidence item**. What survives to this stage is semantic near-overlap, and
most of it is correctly blocked from merging.

**Merge blockers enforced** (from the governance list): differing thresholds · differing timeframes ·
differing session restrictions · one mandatory and one optional · entry mixed with trade management ·
different domains · a member participating in a contradiction. A group can be detected at high
overlap and still be `DO_NOT_MERGE`, with the reason recorded.

## 10. Contradictions

**11 contradiction records** involving at least one ALEX_G claim: **1 `blocking`**, 8 `material`,
2 `minor`.

**Imported, not re-derived.** The evidence store already recorded each with a rationale at ingestion;
re-deciding them here would discard that reasoning. Each gains what the KE model requires and the
evidence record lacks: **≥2 explicit alternative interpretations** and a **completion path**. The
model refuses a contradiction offering only one interpretation — offering one is resolving it.

**None is resolved automatically.** All 11 remain `OPEN`.

## 11. Unresolved Parameters

**66 of 111 rules.** The recurring categories:

- the source states the rule and withholds its parameter (session hours, scale maximum, touch count)
- a named indicator or window has no stated setting (the 4-hour EMA, across two sources)
- a blocking open question already recorded at ingestion

**None was filled in.** Where the educator demonstrates something visually without stating a formula,
it is carried as unresolved and the rule is marked non-deterministic.

## 12. Draft Specification Summary

**`alex_g_educator_v2_draft`** · version `v2.0.0-draft` · **111 rule references** · rule-set hash
recorded.

Rules are **referenced by id, never copied** — one rule, one definition.

**Status flags, all TRUE and not computed from anything:** `NOT_PRODUCTION` · `NOT_IMPLEMENTED` ·
`NOT_REPLAY_VALIDATED` · `NOT_PAPER_VALIDATED` · `PROFITABILITY_UNVALIDATED` ·
`ENGINEERING_AUTHORITY_APPROVAL_REQUIRED`

The model **refuses** to construct a draft using the production strategyId.

## 13. Current-vs-Draft Differences

| | `alex_g_sr_v1` (production) | `alex_g_educator_v2_draft` |
|---|---|---|
| Rules | 13 | 111 |
| Source | `RULES_ALEXG` (protected constant) | 195 educator claims |

**Shared domains:** SETUP, TIMEFRAMES, NO_TRADE_CONDITIONS, INVALIDATION-adjacent.

**Educator-supported additions** (draft covers, production does not): **TRADE_MANAGEMENT** (8 rules
vs 0), **SESSION_RESTRICTIONS** (7 vs 0), **ENTRY** (27 vs 0), RISK (13 vs 0), LIQUIDITY (2 vs 0).

**MOGO-authored only** (production covers, educator library yields nothing): **MARKET_STRUCTURE** and
**DIRECTIONAL_BIAS**.

**⚠️ Lineage conflict, recorded:** overlap between the two is **convergence, not derivation**. Treating
it as corroboration would be an error.

## 14. Risk Coverage

**13 draft rules — all sizing, zero stop placement.**

- Bands: conservative 0.5–1%, standard 1–2%, high 3–5% (personal accounts only)
- Stability: same percentage every trade; one percentage per month; never raised after wins

**Position size = risk ÷ stop distance. The second term does not exist anywhere in 195 claims across
8 sources.** `GAP-RISK-001` is **not closed** by this draft — it is confirmed from the educator side.

## 15. Trade-Management Coverage

**8 draft rules vs 0 in production** — the domain where the draft adds most.

Includes set-and-forget while price travels, the alarm-for-next-pullback response to a missed entry,
and the named exit failure mode (a 1:4 target cut at 1:2 on the dollar figure). The R:R figures
(1:2, 1:3, 1:4) are carried as **illustrative, not required** — no minimum ratio is stated anywhere.

## 16. Exit Coverage

**Zero. Zero claims, zero candidates, zero rules.**

No claim in the library describes closing a position on a market condition. This cannot be fixed by
re-analysis; it requires source acquisition. Recorded as `KEGAP-002`, priority `CRITICAL`, blocking.

## 17. Knowledge Gaps

| ID | Domain | Gap | Priority |
|---|---|---|---|
| **KEGAP-001** | RISK | No stop-placement rule anywhere in the library | **CRITICAL**, blocking |
| **KEGAP-002** | EXIT | No claim addresses closing a position | **CRITICAL**, blocking |
| **KEGAP-003** | SESSION | Session rules are prescriptive; hours never spoken | HIGH, blocking |
| **KEGAP-004** | MARKET_STRUCTURE | Swing significance undefined and cross-educator contradicted | HIGH |

## 18. Test Results

**57 / 57 pass** (`tests/knowledge_engineering/`).

Coverage: stable ID generation · serialization/parsing · schema validation · **provenance
preservation** · claim classification · candidate-rule promotion · duplicate grouping and every merge
blocker · contradiction creation · normalization decisions · **unresolved-parameter preservation** ·
source-to-rule mappings · draft generation · **specification separation** · deterministic reports ·
backward compatibility · **prevention of production promotion** · **prevention of direct
claim-to-production import**.

Notable guards asserted: a rule cannot exceed `NEEDS_REVIEW`; maturity cannot exceed `NORMALIZED`; a
draft cannot reuse `alex_g_sr_v1`; a contradiction cannot offer one interpretation; a claim cannot
exist without provenance; **the evidence store is byte-identical after a full generation run**.

## 19. Regression Results

| Check | Result |
|---|---|
| `tests/run_all.sh` | **591 / 591 fixtures**, 13 suites, 0 failures |
| MOGO-002.5 fidelity tests | **63 / 63 pass** |
| Protected-function drift | **ZERO** — 63 functions, 4 constants byte-identical |
| Python compile | clean |
| Evidence store | 310 claims, 0 proposals — unchanged |
| Production specification | 13 rules, hash `a0b7641e288c1725` — unchanged |

**Pre-existing, unrelated:** `tests.trader_intelligence.*` — 307 tests, **4 failures**, unchanged and
reported separately (they assert the production evidence tree is empty; obsolete since the first real
ingestion).

**One defect found and fixed in this milestone's own code:** the inventory loader leaked file handles
(`ResourceWarning` under test). Fixed with context management; tests re-run clean.

## 20. Known Limitations

1. **Classification is derived, not authoritative.** It comes from `claimType`, evidence
   `directness`, and blocking questions. Where content signals were needed (marketing, psychology),
   the lexical trigger is recorded — but a reviewer could reasonably reclassify individual claims.
2. **Duplicate detection is lexical.** Token-overlap within a domain will miss a genuine duplicate
   phrased in entirely different words.
3. **Normalization does not restructure claims.** Canonical statements are the evidence store's own
   `normalizedClaim`, unchanged. No claim was rewritten into a cleaner rule form — that would be
   re-authoring the source.
4. **No rule is validated.** 111 rules at `emerging`-derived confidence, none corroborated
   independently, none replayed.
5. **The draft is larger but not better.** 111 rules vs 13 does not mean more knowledge — 66 carry
   unresolved parameters and only 41 are deterministic.
6. **Deferral criteria are conservative.** 4 candidates were deferred; a reviewer might normalize
   some of them with explicit caveats.

## 21. Engineering Authority Decisions Required

**59 items in the review queue**, ranked by whether they affect whether a trade is taken. The
structural ones:

| # | Decision | Recommendation |
|---|---|---|
| **KEREV-A** | **Stop placement is absent from the entire library.** Acquire, accept as absent, or permit MOGO-authored? | **Acquire or accept.** Do not permit an unlabelled MOGO-authored stop inside a rule attributed to the educator |
| **KEREV-B** | Confirm the two specifications remain permanently separate | **Keep separate.** Reconciliation is its own governed milestone |
| **KEREV-C** | 1 `blocking` + 8 `material` contradictions — rule or defer each | **Defer those replay could settle**; rule on the rest |
| **KEREV-D** | Required gating rules with unresolved parameters — defer or reject for v2? | **Defer.** MOGO must not choose the parameter |
| **KEREV-E** | Accept the 66 `UNRESOLVED` classifications, or re-review individually? | Accept the derivation; spot-check the 7 `DISCRETIONARY` |

## 22. Recommended Next Milestone

**MOGO-002.7 — Source Acquisition for Blocking Gaps.** Not engineering; acquisition and decision.

The draft specification cannot progress past `NEEDS_REVIEW` in its blocking domains no matter how much
more analysis is applied to the existing 195 claims. **Two domains are empty at source** (EXIT,
stop placement) and a third is unreadable from transcripts (session hours). Those need material, not
modelling.

**Sequence:**

1. Decide KEREV-A — it determines whether the 13 risk rules are ever implementable.
2. Acquire against `BACKLOG-002/A1-STOP` and `A2-LIVE`, or record that the educator's published
   material cannot support them.
3. Rule on the contradiction register (KEREV-C).
4. Only then consider promoting any draft rule — through a separate governed milestone, as OD-1
   modification 6 requires.

**Explicitly not recommended:** promoting any draft rule now, or reconciling the two specifications.
Neither is blocked by engineering; both are blocked by evidence that does not exist yet.

## 23. Artifact Paths

**Engineering Review Package (this document)**
`docs/reports/MOGO-002.6_ENGINEERING_REVIEW.md`

**Markdown reports**
```
docs/knowledge-engineering/CLAIM-CLASSIFICATION-REPORT.md
docs/knowledge-engineering/DUPLICATE-OVERLAP-REPORT.md
docs/knowledge-engineering/CONTRADICTION-REGISTER.md
docs/knowledge-engineering/NORMALIZED-RULE-LIBRARY.md
docs/knowledge-engineering/CLAIM-TO-RULE-MAPPING.md
docs/knowledge-engineering/ALEX-STRATEGY-SPECIFICATION-V2-DRAFT.md
docs/knowledge-engineering/SPECIFICATION-DELTA.md
docs/knowledge-engineering/KNOWLEDGE-COVERAGE-REPORT.md
docs/knowledge-engineering/HUMAN-REVIEW-QUEUE.md
```

**Machine-readable JSON**
```
docs/knowledge-engineering/claim-inventory.json
docs/knowledge-engineering/duplicate-groups.json
docs/knowledge-engineering/contradiction-register.json
docs/knowledge-engineering/candidate-rules.json
docs/knowledge-engineering/normalized-rules.json
docs/knowledge-engineering/normalization-decisions.json
docs/knowledge-engineering/claim-to-rule-mapping.json
docs/knowledge-engineering/alex-strategy-specification-v2-draft.json
docs/knowledge-engineering/specification-delta.json
docs/knowledge-engineering/knowledge-coverage.json
docs/knowledge-engineering/human-review-queue.json
docs/knowledge-engineering/knowledge-gaps.json
```

**Source**
```
scripts/knowledge_engineering/{ke_model,ke_inventory,ke_analysis,build_ke_artifacts}.py
tests/knowledge_engineering/test_knowledge_engineering.py
```

**Prior milestone (referenced, unchanged)**
```
docs/reports/MOGO-002.5_ENGINEERING_REVIEW.md
docs/strategy-fidelity/MOGO-002.5-REPOSITORY-TRUTH-AUDIT.md
docs/strategy-fidelity/manifests/alex_g_sr_v1.specification.json
```

---

*MOGO-002.6 complete. No implementation will proceed pending Engineering Authority review.*

# PROGRAM-006 — Evidence Intelligence Engine — Status

**Phase:** 1A + 1B — Evidence Model/Provenance Foundation, then Explainability and
Controlled TJR Intake.
**Status:** Both phases complete. Phase 1A committed and pushed
(`adb4282f9a6efce5ba146847bc77a969f1c55463`, `origin/mogo-main`). Phase 1B complete, pending
final commit/push authorization and remote verification (see the Phase 1B section below).

## Required negative assertions

| Question | Answer |
|---|---|
| Was any real evidence ingested? | **No.** `docs/trader-intelligence/evidence/{sources,items,claims,links,contradictions}/` contain zero real records (confirmed by `test_production_evidence_tree_is_still_genuinely_empty`). |
| Does any real TJR (or other trader) corpus exist in this system? | **No.** Only a clearly-marked synthetic fixture exists, under `tests/trader_intelligence/evidence/fixtures/synthetic_demo/`, never read by production code. |
| Was any `StrategyRule` promoted, or its `modelingStatus`/`implementationStatus`/`promotionState` changed? | **No.** The only change to `strategy-rule.schema.json` is one additive, currently-unused field (`originatingClaimIds`); no existing `StrategyRule` record was modified. |
| Did any runtime trading behavior change? | **No.** `index.html` was not touched; `APP_VERSION` is unchanged; no protected function or constant drifted (verified against the existing regression baseline). |
| Was any network capability added? | **No.** Every new module is pure Python standard library; zero imports of `requests`, `urllib.request`, `http.client`, sockets, or browser automation anywhere in `scripts/trader_intelligence/evidence_*.py`, `query_evidence.py`, or `validate_evidence.py`. |
| Did paper or live execution capability change in any way? | **No.** Nothing in this phase can place, close, or modify a trade, connect to a broker, or touch `paperAccount`/journal storage. |

## What was built

- **ADR-008** (`docs/adr/ADR-008-evidence-intelligence-engine.md`) establishing the
  Source → Evidence → Claim → Confidence → Rule Candidate → Validated Rule → Production
  Rule model and the decision to extend `StrategyRule` rather than invent a parallel entity.
- **7 JSON Schemas** under `docs/trader-intelligence/evidence/schema/` (EvidenceSource,
  EvidenceItem, Claim, EvidenceClaimLink, EvidenceLifecycleEvent, ContradictionRecord,
  EvidenceIntegrityReport), plus one additive field on the existing
  `strategy-rule.schema.json`.
- **6 new Python modules**: `evidence_common.py`, `evidence_confidence.py`,
  `evidence_dedup.py`, `evidence_registry.py`, `query_evidence.py`, `validate_evidence.py`,
  plus a one-off fixture generator, `generate_synthetic_evidence_fixture.py`.
- **Additive Knowledge Graph integration**: 4 new node types, 6 new edge types in
  `graph_common.py`; new direction rules in `validate_graph.py`. The production graph build
  is unchanged (43 nodes / 79 edges, zero findings) both before and after this phase.
- **22 deterministic queries**, a **19-category integrity validator**, and a
  **77-test suite** (`tests/trader_intelligence/evidence/test_evidence.py`), bringing the
  combined Trader Intelligence / Research Acquisition / Evidence test count to **159**, all
  passing.
- **A synthetic demo fixture** (2 sources, 5 evidence items, 2 claims, 1 contradiction, 1
  supersession), clearly marked `SYNTHETIC TEST DATA / NOT REAL TJR RESEARCH / NOT
  VALIDATED TRADING KNOWLEDGE / NOT A PRODUCTION RULE` throughout.
- **`docs/EVIDENCE_INTELLIGENCE.md`** — the engineer/owner-facing documentation for this
  system.

## Issues found and fixed during implementation

Two real bugs were found (via test-driven verification, not by inspection alone) and
fixed before this phase was considered complete:

1. `evidence_common.next_lifecycle_event_id()` computed sequence numbers by pattern-matching
   filenames, but lifecycle events are stored under hash-derived filenames — so every event
   for a given entity silently received sequence `001`, making lifecycle ordering
   unreliable under same-second timestamps. Fixed to scan existing event *contents* instead
   of filenames.
2. Evidence-link and ContradictionRecord-derived Knowledge Graph edges did not populate
   `evidenceIds`, which `validate_graph.py`'s pre-existing provenance check correctly
   flagged. Fixed by populating `evidenceIds` with the edge's own originating record ID
   (the EvidenceItem or ContradictionRecord *is* the evidence for that edge).

Both fixes are covered by tests that would fail again if either regressed.

## Verification performed

- Full Python suite: `tests.trader_intelligence.test_graph` (25),
  `tests.trader_intelligence.acquisition.test_acquisition` (57),
  `tests.trader_intelligence.evidence.test_evidence` (77) — **159/159 passing**.
- `build_graph.py` against production data: 43 nodes / 79 edges, zero findings — identical
  to the pre-PROGRAM-006 baseline.
- `validate_graph.py` against the production build: zero findings.
- `validate_evidence.py` against the (empty) production evidence tree: zero findings.
- `py_compile` clean on every new/modified module.
- No changes to `index.html`, `APP_VERSION`, or any protected function/constant.

## Explicitly out of scope for this phase

No transcript ingestion, no video/browser automation, no LLM extraction, no
embeddings/vector search, no automated rule promotion, no replay/paper/live-trade
ingestion pipeline, no broker integration, no UI. See
`docs/EVIDENCE_INTELLIGENCE.md` §15 for the full list.

## Owner decisions required to proceed to Phase 1B

None identified during this phase. No stop condition from the Phase 1A authorization was
triggered — every decision made (schema field names, module boundaries, edge-type mapping,
confidence formula constants, test structure) was an ordinary engineering judgment call
within the phase's own explicit boundaries.

---

# Phase 1B — Explainability and Controlled TJR Intake (ADR-009)

**Baseline commit:** `adb4282f9a6efce5ba146847bc77a969f1c55463` (Phase 1A, confirmed identical
to `origin/mogo-main` at the start of this phase — verified directly, not trusted from the
prior report).
**Final commit:** pending (this document is written before Phase F commit/push).
**Branch:** `main` (pushed to `origin/mogo-main`, never `origin/main`).
**APP_VERSION:** `12.6.0` — unchanged throughout Phase 1B.

## Required negative assertions

| Question | Answer |
|---|---|
| Was any real TJR transcript found in the repository? | **No.** A fresh, direct search (transcript/media file extensions, untracked files, TJR-named paths, acquisition candidates, `traders/tjr/sources/`) found zero real research material — only MOGO's own architecture docs (ADR-007), the Phase 1A/1B synthetic fixtures, and unrelated JS test files. |
| Was any real TJR transcript ingested? | **No.** Both intakes in `synthetic_tjr_demo` are invented, clearly-marked synthetic content. |
| Was any source licensing decision required? | **No.** No real source exists, so no licensing decision was triggered. |
| Did any production rule change? | **No.** Zero writes to any file under `traders/*/rules/`; the one `RuleCandidateProposal` created by the synthetic fixture's post-annotation pipeline is a separate, non-executable record whose `status` can only ever be `proposed`/`superseded`/`withdrawn`. |
| Did any strategy behavior change? | **No.** `index.html` was not touched. |
| Was any paper trade created? | **No.** Nothing in this phase can create, modify, or close a paper or live trade. |
| Did live-trading capability change in any way? | **No.** |

## What was built

- **ADR-009** (`docs/adr/ADR-009-evidence-explainability-and-tjr-intake.md`) — explainability,
  traceability, directness/extraction-certainty classification, the extraction/normalization/
  interpretation/explanation/recommendation/promotion distinction, and the naming decision to
  call the new question entity `EvidenceQuestion` (not `UnresolvedQuestion`, which is already a
  distinct Wave-1 entity).
- **7 new JSON Schemas**: `intake-manifest`, `transcript-segment`, `manual-annotation`,
  `evidence-question`, `review-queue-entry`, `rule-candidate-proposal`, `claim-explanation`.
  Plus two small additive fields on existing Phase 1A schemas: `directness` +
  `extractionCertainty` on `EvidenceItem`, and a `pending_review` value added to `Claim`'s
  `claimStatus` enum.
- **10 new Python modules**: `transcript_adapters.py`, `intake_registry.py`,
  `annotation_pipeline.py`, `extraction_pipeline.py`, `evidence_questions.py`,
  `rule_candidate_proposals.py`, `review_queues.py`, `evidence_explain.py`, `tjr_report.py`,
  and `generate_synthetic_tjr_fixture.py`.
- **6 modified Python modules**: `evidence_common.py` (new vocabularies, ID generators),
  `evidence_registry.py` (`directness`/`extractionCertainty`/`claimStatus`/
  `possibleDuplicateClaimIds` parameters), `query_evidence.py` (22 new queries + `EvidenceIndex`
  extended with 6 new collections), `graph_common.py` (5 new node types, 6 new edge types),
  `validate_graph.py` (new edge-direction rules), `validate_evidence.py` (13 new integrity
  checks + `evidenceIds` extra-collections support in duplicate-ID checking).
- **22 new deterministic queries** (explainability, intake, segment, and report queries),
  bringing the query service to 44 total.
- **13 new integrity-check categories** (orphaned segments, missing transcript locators,
  invalid annotation references, missing directness/certainty, claim candidates without
  evidence, rule-candidate validity, question/review-queue reference integrity, approved-intake/
  licensing checks, segment hash/sequence/line-range checks, explanation provenance), bringing
  the evidence validator to 32 finding categories total.
- **Additive Knowledge Graph integration**: 5 new node types (`TRANSCRIPT_SEGMENT`,
  `INTAKE_MANIFEST`, `EVIDENCE_QUESTION`, `REVIEW_QUEUE_ENTRY`, `RULE_CANDIDATE_PROPOSAL`), 6 new
  edge types (`EVIDENCE_FROM_SEGMENT`, `RAISES_QUESTION`, `REQUIRES_REVIEW`, `PROPOSES_RULE`,
  `BLOCKED_BY`, `RESOLVED_BY_EVIDENCE`), `SEGMENT_OF` reused additively. Production graph
  unchanged at 43 nodes / 79 edges, zero findings, both before and after this phase.
- **A comprehensive synthetic TJR fixture**
  (`tests/trader_intelligence/evidence/fixtures/synthetic_tjr_demo/`): 2 intakes, 17 segments,
  15 annotations, 15 evidence items, 9 claims (1 supported, 1 contested, 1 insufficient-evidence,
  1 exception, plus
  5 others spanning stop/risk/trade-management/behavioral claim types), 1 contradiction record,
  17 unresolved questions, 1 rule-candidate proposal, all 14 review queues populated, a full
  explainability report, and a complete TJR research report (JSON + Markdown) — every string
  clearly marked `SYNTHETIC TEST DATA / NOT A REAL TJR TRANSCRIPT / NOT VALIDATED TRADING
  KNOWLEDGE / NOT A PRODUCTION STRATEGY / DO NOT USE FOR TRADING`.
- **103 new tests** (`tests/trader_intelligence/evidence/test_phase1b.py`, categories A–N),
  bringing the combined test count to **262** (Phase 1A/graph/acquisition 159 + Phase 1B 103),
  all passing.
- **`docs/EVIDENCE_INTELLIGENCE.md` §17–38 + owner workflow + First Real TJR Intake guide**
  appended to the existing Phase 1A documentation.

## Counts

| Metric | Count |
|---|---|
| Real TJR source count | 0 |
| Synthetic source count (fixtures) | 2 (`synthetic_tjr_demo`) + 2 (`synthetic_demo`, Phase 1A) |
| Real evidence count | 0 |
| Synthetic evidence count | 15 (`synthetic_tjr_demo`) + 5 (`synthetic_demo`) |
| Claim count (synthetic) | 9 (`synthetic_tjr_demo`) + 2 (`synthetic_demo`) |
| Contradiction count (synthetic) | 1 + 1 |
| Unresolved-question count (synthetic) | 17 |
| Rule-candidate count (synthetic) | 1 |
| Production-rule promotion count | 0 |

## Issues found and fixed during implementation

Four real bugs were found via test-driven verification (building the synthetic fixture and
targeted smoke tests) and fixed before this phase was considered complete:

1. `annotation_pipeline.classify_claim_relationship()`'s `scoped_variant` and `near_duplicate`
   classifications were being reused as the *same* claim in `apply_annotation()`, silently
   merging claims that ADR-008/009 explicitly require stay separate (only an exact fingerprint
   match should ever be reused). Fixed to only reuse the matched claim for `exact_duplicate`;
   `scoped_variant`/`near_duplicate` now always create a new claim, recording the match only as
   advisory `possibleDuplicateClaimIds` (which required also fixing `evidence_registry.
   register_claim()` to actually honor that field instead of hardcoding it to `[]`).
2. `annotation_pipeline.classify_claim_relationship()` called a nonexistent
   `evidence_dedup.is_near_duplicate()` — the function actually lives in `evidence_common`.
   Fixed the reference; this path had never been exercised by any test until the synthetic
   fixture build reached it.
3. `annotation_pipeline.apply_annotation()` always passed `evidenceQuality="unknown"` to
   `evidence_registry.register_evidence_item()`, silently discarding any quality signal a
   researcher supplied. Fixed by adding `evidenceQuality` as a proper `ManualAnnotation` field
   (schema + registration + apply) instead of hardcoding it.
4. `extraction_pipeline.run_intake_extraction_pipeline()` transitioned `intakeStatus` through
   the extraction lifecycle but never updated the separate `extractionStatus` field, which
   would have stayed `not_started` forever even after a successful extraction. Fixed by adding
   an `extractionStatus` parameter to `intake_registry.transition_intake_status()` and passing
   it through on both the success and failure paths.

All four are covered by tests that would fail again if any regressed.

## Verification performed

- Full Python suite: **262/262 passing** (`test_graph` 25, `test_acquisition` 57,
  `test_evidence` 77, `test_phase1b` 103).
- Full JavaScript suite: **530/530 fixtures passing**, 12 suites, 0 execution errors.
- Protected-function/constant drift: **zero** — all 63 protected functions and 4 protected
  constants byte-identical to the committed baseline.
- `build_graph.py` against production data: 43 nodes / 79 edges, zero findings — unchanged
  before and after this phase.
- `validate_graph.py` against the production build: zero findings.
- `validate_evidence.py` against the (still-empty) production evidence tree: zero findings.
- `validate_evidence.py` against `synthetic_tjr_demo` (non-production mode): zero findings
  beyond one expected `DUPLICATE_IMMUTABLE_CONTENT` warning (the fixture's deliberately
  duplicated statement, a true positive demonstrating the check works).
- `py_compile` clean on every new/modified module.
- No changes to `index.html` or `APP_VERSION`.

## Known limitations / deferred items

- The controlled extraction pipeline's `suggest_candidate_evidence()` is a fixed phrase-marker
  matcher, not general natural-language understanding — by design (ADR-009 §16).
- No replay or paper/live-trade evidence producer is wired up yet; the data model supports
  those evidence types generically, but no ingestion pipeline exists for them (unchanged from
  Phase 1A's own deferred scope).
- No UI exists for any of this — every interaction is via direct Python calls.
- `RuleCandidateProposal.ownerReviewStatus` is a field an owner can set, but no code path yet
  turns an "approved" proposal into an actual `StrategyRule` edit — that remains a deliberate,
  separate, human-driven step outside this phase's automation.

## Next recommended phase

Process the first real TJR transcript through this exact pipeline once the owner supplies one
(see `docs/EVIDENCE_INTELLIGENCE.md`'s "First Real TJR Intake — Owner Guide"). No new
architecture is anticipated to be required for that first real intake.

## Owner decisions required to proceed

None identified during this phase. No stop condition from the Phase 1B authorization was
triggered.

# PROGRAM-006 — Evidence Intelligence Engine — Status

**Phase:** 1A — Evidence Model and Provenance Foundation
**Status:** Complete, pending final commit/push authorization and remote verification.

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

# PROGRAM-007 — Real Trader Knowledge Library — Status

**Phase:** 7A — Real Trader Knowledge Library Vertical Slice.
**Status:** Complete, pending final commit/push authorization and remote verification.
**Baseline commit verified at phase start:** `4e65c0b8bbc2d7f33b996f3d2a3e76ee108d4031`
(`origin/mogo-main`) — independently re-verified (not trusted from any prior report): branch,
commit, working tree, remote, tags, all 262 Phase 1B tests, and every Phase 1B schema/module
confirmed present exactly as reported, with zero commits after this hash.
**Branch:** `main` (pushed to `origin/mogo-main`, never `origin/main`).
**APP_VERSION:** `12.6.0` — unchanged throughout Phase 7A.

## Required negative assertions

| Question | Answer |
|---|---|
| Was a real TJR (or other trader) transcript processed? | **No.** A fresh, direct search found zero real transcript material anywhere in the repository. See "Source Selection" below. |
| Was any `StrategyRule` created, modified, or promoted? | **No.** Zero writes to any file under `traders/*/rules/`; `check_no_executable_blueprint_linkage` structurally proves no `StrategyRule` ever references a `BLUEPRINT\|` id. |
| Did any runtime trading behavior change? | **No.** `index.html` untouched; `APP_VERSION` unchanged; all 63 protected functions and 4 protected constants byte-identical to baseline (verified via `regression-baseline-tools.py`, exit code 0). |
| Was any network capability added? | **No.** Every new module (`trader_profile.py`, `strategy_blueprint.py`, `knowledge_gaps.py`, `hypothesis_proposals.py`, `knowledge_library_report.py`) is pure Python standard library; zero imports of `requests`, `urllib.request`, `http.client`, sockets, or browser automation (enforced by `TestCategoryFSafetyRegression`). |
| Did paper or live execution capability change in any way? | **No.** Nothing in this phase can place, close, or modify a trade, connect to a broker, or touch `paperAccount`/journal storage. |
| Was any UI added or modified? | **No.** Deliverable 7's review workflow is a Python service layer only; no UI integration point was safe to use without redesigning unrelated screens, so UI work is explicitly deferred (see "Deferred Work"). |

## 1. Objective

Prove that MOGO can process a real trader transcript into structured, reviewable trading
intelligence: Real transcript → intake record → normalized segments → evidence →
observations → claims → unresolved questions → hypotheses → trader profile → draft strategy
blueprint → human-review report — using the Evidence Intelligence Engine (PROGRAM-006 Phase
1A/1B) as the foundation, without touching live/paper trading execution.

## 2. Scope

The smallest complete vertical slice that produces useful, reviewable output from one trader's
evidence: `TraderProfile`, `StrategyBlueprint`, `KnowledgeGap`, `Hypothesis` domain objects; a
review workflow extending the existing 14-type review-queue system; Knowledge Graph
integration; a human-review report; and the full A–G test suite (Deliverable 9). Explicitly
excluded: speculative enterprise infrastructure, autonomous trading, automatic `StrategyRule`
conversion, and any change to JVM/ALEX/TJR execution, order placement, trade management, or
broker integration.

## 3. Architecture

Built entirely on top of PROGRAM-006's Evidence Intelligence Engine — no new storage layer, no
new ID scheme style, no new hashing/serialization convention. New entities live as siblings
under `docs/trader-intelligence/evidence/{profiles,blueprints,gaps,hypotheses}/`, use the same
deterministic pipe-delimited ID style (`PROFILE|{TRADER}|{YYYYMMDD}|{seq}`,
`BLUEPRINT|{TRADER}|{YYYYMMDD}|{seq}`, `GAP|{YYYYMMDD}|{seq}`, `HYP|{YYYYMMDD}|{seq}`), and the
same `atomic_write_text`/`pretty_json`/`canonical_json_bytes` primitives from `graph_common.py`.
`query_evidence.EvidenceIndex` was extended (not replaced) to load the four new collections
with backward-compatible `or {}` defaults, so every pre-existing Phase 1A/1B query keeps
working unmodified. Full module/schema/graph details are in
`docs/EVIDENCE_INTELLIGENCE.md` Part 3 (§39–50).

## 4. Source Selection (Deliverable 5 / SOURCE_REQUIRED)

**No real TJR transcript, and no real transcript for any other trader, exists anywhere in this
repository as of Phase 7A.** This was independently re-verified via a fresh search (not reused
from the Phase 1B report): file-extension search across the repository, an untracked-files
check, a search of `docs/trader-intelligence/acquisition/` candidate queues, a direct check of
`docs/trader-intelligence/traders/tjr/sources/`, and a scratchpad search — all consistent with
Phase 1B's own findings recorded in `docs/PROGRAM_006_STATUS.md`.

Per the milestone's explicit instruction, this does not stop the rest of the implementation:

- The full transcript → intake → segment → annotation → evidence → claim → profile →
  blueprint → gap → hypothesis → report pipeline is implemented, wired together, and proven
  correct end to end using a real (not a pre-authored fixture file) plain-text transcript
  constructed inline by `TestCategoryETranscriptIntegration.test_intake_through_final_report_end_to_end`
  in `tests/trader_intelligence/evidence/test_phase7a.py` — this is the reusable, tested,
  production-ready pipeline; it needs no new code once a real transcript exists.
- Synthetic fixtures (Phase 1A's `synthetic_demo`, Phase 1B's `synthetic_tjr_demo`) remain in
  place, unmodified, for regression testing only — never read by production code paths.
- **Exact supported import location and format for the first real transcript:** any local
  plain-text (`plain_text`), timestamped-text (`timestamped_text`), or structured-JSON
  (`structured_json`) file, at any path you choose — no network fetch, no specific repository
  location required. Call `intake_registry.register_intake_manifest(...)` with
  `transcriptFormat` set accordingly, then follow the 11-step owner workflow already documented
  in `docs/EVIDENCE_INTELLIGENCE.md` ("Owner workflow: processing a real TJR transcript"), then
  run the Phase 7A pipeline (§4 "Exact commands" below) on top of the resulting claims.
- No transcript content was fabricated to avoid this limitation.

## 5. Domain Objects

- **TraderProfile** (`trader_profile.py`) — 32-field versioned summary; see
  `docs/EVIDENCE_INTELLIGENCE.md` §40.
- **StrategyBlueprint** (`strategy_blueprint.py`) — 10-section, structurally non-executable
  draft; see §41.
- **KnowledgeGap** (`knowledge_gaps.py`) — 17-category detector, never fabricates an answer;
  see §42.
- **Hypothesis** (`hypothesis_proposals.py`) — proposed only from a real claim, contradiction,
  or anchored gap; see §43.

## 6. Graph Relationships (Deliverable 8)

4 new node types, 5 new edge types, additive-only in `graph_common.py`/`validate_graph.py`;
5 new integrity checks in `validate_evidence.py`. Full list and rationale in
`docs/EVIDENCE_INTELLIGENCE.md` §47. Production graph build against real repository data
remains at its Phase 1B baseline (zero Phase 7A nodes present, since no real Knowledge Library
data exists yet) with zero blocking findings, confirmed by
`TestKnowledgeGraphPhase7A.test_production_graph_unchanged_without_real_knowledge_library`.

## 7. Workflow

Real transcript → `IntakeManifest` → `TranscriptSegment`(s) → `ManualAnnotation` (approved) →
`EvidenceItem` + `Claim` + `EvidenceClaimLink` (all Phase 1B, unchanged) → `TraderProfile` →
`StrategyBlueprint` → `KnowledgeGap`(s) → `Hypothesis`(es) → Knowledge Library Report. Every
step after evidence extraction is deterministic and re-derivable from stored state; nothing is
free-form narrative.

## 8. Review Lifecycle (Deliverable 7)

8 reviewer actions (`approve_as_supported_claim`, `approve_as_inferred_claim`, `reject`,
`mark_contradictory`, `request_more_evidence`, `convert_to_research_question`,
`propose_hypothesis`, `leave_unresolved`) via `review_queues.apply_review_action()`. Never
auto-approves; only ever changes the `ReviewQueueEntry` itself (plus, for
`convert_to_research_question`, one new additive `EvidenceQuestion`). No UI integration point
exists yet — see "Deferred Work". Full detail in `docs/EVIDENCE_INTELLIGENCE.md` §46.

## 9. Safety Boundaries

- No import of any network-capable module in any Phase 7A file (checked structurally by test).
- No file under `traders/*/rules/` is ever written by any Phase 7A module (checked
  structurally by test).
- `StrategyBlueprint.validationStatus.productionStatus` is a JSON Schema `const:
  "not_applicable"` — no code path can ever set it otherwise.
- `index.html`, `APP_VERSION`, and all 63 protected functions / 4 protected constants are
  byte-identical to the pre-Phase-7A baseline (verified via `regression-baseline-tools.py`,
  which this phase's test suite also runs and asserts on: `test_index_html_protected_functions_show_zero_drift`).

## 10. Test Coverage (Deliverable 9)

`tests/trader_intelligence/evidence/test_phase7a.py` — **45 tests**, categories A–G:

| Category | Focus | Test classes |
|---|---|---|
| A | Trader Profile domain validation | `TestCategoryATraderProfileDomain` |
| B | Strategy Blueprint (determinism, ordering, classification separation, provenance, research-only default, no executable output) | `TestCategoryBStrategyBlueprint` |
| C | Knowledge Gap (missing stop/invalidation/timeframe detection, no fabricated answers) | `TestCategoryCKnowledgeGaps` |
| D | Hypothesis (supportable-inputs-only, contradictions attached, default status, no mutation) | `TestCategoryDHypotheses` |
| E | Real transcript → intake → final report, end to end | `TestCategoryETranscriptIntegration` |
| F | Safety regression (no network, no index.html coupling, no rule-file writes, protected-function drift) | `TestCategoryFSafetyRegression` |
| G | Existing suite re-run | see "Verification performed" below |

Plus dedicated Deliverable 6/7/8 test classes (`TestKnowledgeLibraryReportPhase7A`,
`TestReviewWorkflowPhase7A`, `TestKnowledgeGraphPhase7A`/`TestKnowledgeGraphPhase7AIntegration`)
covering the report, review workflow, and graph integration in depth.

## Verification performed

- Full Python suite: **307/307 passing** (`test_graph` 25, `test_acquisition` 57,
  `test_evidence` 77, `test_phase1b` 103, `test_phase7a` 45).
- Full JavaScript suite: **530/530 fixtures passing**, 12 suites, 0 execution errors
  (`bash tests/run_all.sh`).
- Protected-function/constant drift: **zero** (`python3 regression-baseline-tools.py`, exit 0).
- `py_compile` clean on every new/modified Python module.
- No changes to `index.html` or `APP_VERSION`.
- Production Knowledge Graph build: zero Phase 7A nodes (no real data yet), zero blocking
  findings, identical to the Phase 1B baseline.

## Known limitations

- `TraderProfile`/`StrategyBlueprint` have no lifecycle-transition state machine the way
  `IntakeManifest` does — each build produces a brand-new immutable snapshot rather than an
  object that transitions through states, so "invalid lifecycle transitions" doesn't
  structurally apply to these two entities the way it does elsewhere.
- `KnowledgeGap.provenance.evidenceQuestionId` is never auto-populated by
  `generate_knowledge_gaps()` today (Deliverable 3 doesn't require auto-generating a linked
  `EvidenceQuestion` per gap) — the `GAP_GENERATES_RESEARCH_QUESTION` graph edge exists and is
  tested directly (`test_gap_generates_research_question_edge_direction`), but is not yet
  exercised by the standard pipeline.
- `propose_hypothesis` (review action) intentionally does not create a `Hypothesis` record by
  itself — see Deferred Work.

## Deferred work

- **UI for the review workflow.** No safe integration point exists in `index.html` (a live
  trading application, not a research-review surface); Deliverable 7 is implemented as a
  domain/service layer only, ready for a future Research Center UI to call directly.
- **Auto-populating `KnowledgeGap.provenance.evidenceQuestionId`** so `GAP_GENERATES_RESEARCH_QUESTION`
  fires from the standard pipeline, not just from a hand-constructed record.
- **A policy for turning an approved `RuleCandidateProposal` (Phase 1B) or validated Hypothesis
  (Phase 7A) into an actual `StrategyRule` edit** — remains a deliberate, separate, human-driven
  step outside all automation to date.
- Processing the first real trader transcript once the owner supplies one (see "Source
  Selection" above) — no new architecture is anticipated to be required.

## Exact commands: rerunning the pipeline

```bash
# From the repository root, with scripts/trader_intelligence on sys.path (handled automatically
# by every module below via sys.path.insert):
python3 -c "
import sys, os
sys.path.insert(0, 'scripts/trader_intelligence')
import query_evidence as qe, trader_profile as tp, strategy_blueprint as sb
import knowledge_gaps as kg, hypothesis_proposals as hp, knowledge_library_report as klr

evidence_root = 'docs/trader-intelligence/evidence'
idx = qe.EvidenceIndex.load(evidence_root)
trader_id = 'TJR'  # or ALEX_G / JVM / any registered traderId with real claims on disk

profile = tp.register_trader_profile(os.path.join(evidence_root, 'profiles'), idx, trader_id)
idx = qe.EvidenceIndex.load(evidence_root)
blueprint = sb.register_strategy_blueprint(os.path.join(evidence_root, 'blueprints'), idx, trader_id)
if blueprint is None:
    # Honest, expected result for a trader with zero claims (true of every
    # real trader as of Phase 7A -- see 'Source Selection' above): nothing
    # to draft a blueprint from yet, so gaps/hypotheses/report are skipped
    # rather than fabricated.
    print('No claims exist yet for %r -- profile generated (claimCount=%d), '
          'no blueprint/gaps/hypotheses/report to produce.' % (trader_id, profile['claimCount']))
else:
    idx = qe.EvidenceIndex.load(evidence_root)
    gaps = kg.generate_knowledge_gaps(os.path.join(evidence_root, 'gaps'), idx, blueprint)
    idx = qe.EvidenceIndex.load(evidence_root)
    hypotheses = hp.generate_hypotheses(os.path.join(evidence_root, 'hypotheses'), idx, blueprint, gaps=gaps)
    idx = qe.EvidenceIndex.load(evidence_root)
    report = klr.generate_knowledge_library_report(idx, trader_id, profile, blueprint, gaps, hypotheses)
    print(klr.render_knowledge_library_report_markdown(report))
"
```

## Exact commands: rerunning all tests

```bash
python3 -m unittest tests.trader_intelligence.test_graph \
  tests.trader_intelligence.acquisition.test_acquisition \
  tests.trader_intelligence.evidence.test_evidence \
  tests.trader_intelligence.evidence.test_phase1b \
  tests.trader_intelligence.evidence.test_phase7a

bash tests/run_all.sh

python3 regression-baseline-tools.py
```

## Owner decisions required to proceed

None identified during this phase. No stop condition from the Phase 7A authorization was
triggered — every decision made (module boundaries, edge-type reuse vs. addition, review-action
state mapping, UI-deferral) was an ordinary engineering judgment call within the phase's own
explicit boundaries.

## Next recommended milestone

Process the first real trader transcript through this exact pipeline once the owner supplies
one (see "Source Selection" above). No new architecture is anticipated to be required for that
first real intake.

# BACKLOG-003 — Pipeline Hardening for Scale

**Status:** Backlog. **Nothing here is implemented or authorized.**
**Scope:** engineering work on the Trader Intelligence subsystem only. No item touches `index.html`,
JVM, ALEX, or any protected function.

Items are grouped by what they unblock, and each carries a **trigger** — the condition that makes it
worth doing. Doing them earlier than the trigger is premature optimization; later is technical debt.

---

## A. Correctness defects (found by the first real ingestion)

### H1 — D1: unevidenced baseline facts stamped `confirmed`
`trader_profile.py:141-143` overrides concept status to `"confirmed"` for Wave-1 `markets`/
`sessions`, producing `markets: [forex]` with `evidenceIds: []` while all evidence says US indices.

**Fix:** add `"unevidenced"` to `PROFILE_CONCEPT_STATUSES` and use it when `evidenceIds` is empty;
add integrity check `BASELINE_CONTRADICTED_BY_EVIDENCE` (`WARNING`).
**Files:** `trader_profile.py`, `evidence_common.py`, `validate_evidence.py`,
`evidence/schema/trader-profile.schema.json`, `test_phase7a.py`
**Risk:** Medium — changes profile output; the new check will fire on TJR immediately (intended).
**Trigger:** bundle with PROPOSAL-001. **Priority: high** — it is actively misleading today.

### H2 — D2: permissive exceptions listed as forbidden
`strategy_blueprint.py:148-149` routes all `exception` claims into `entryLogic.forbiddenConditions`.

**Fix:** split into `forbiddenConditions` and `permittedExceptions`, classified by whether the
exception restricts or permits. Deriving this reliably from claim text alone is not possible —
recommend an explicit `exceptionPolarity` field on the annotation (`restricts` | `permits`).
**Files:** `strategy_blueprint.py`, `annotation_pipeline.py`, blueprint + annotation schemas, tests
**Risk:** Low — research-only artifact, no runtime exposure.
**Trigger:** before any consumer reads `forbiddenConditions` programmatically. **Priority: medium.**

### H3 — D4: questions about absences are unattributable
`trader_profile.py:132` counts only questions whose `claimId` is in the trader's claim set, so the
three most important TJR questions (no risk rule, no no-trade conditions, single-source ceiling) are
invisible to the profile.

**Fix:** add optional `traderId` to `EvidenceQuestion`; count by `claimId` **or** `traderId`.
**Files:** `evidence_questions.py`, `trader_profile.py`, question schema, tests
**Risk:** Low-moderate — schema addition; 14 existing records to migrate (cheap now, never cheaper).
**Trigger:** before source #2. **Priority: medium-high.**

### H4 — Provenance re-verification
Gaps G-a through G-d in `SPEC-provenance.md` §2: nothing re-checks the raw copy hash, the
normalization map, record content hashes, or confidence recomputability after ingestion day.

**Fix:** four integrity checks — `RAW_COPY_HASH_MISMATCH` ✅ (delivered as
`ingest.py --verify-provenance`, which also re-checks working copies, normalization maps and
excerpt verbatimness — 65 checks today), `NORMALIZATION_MAP_NOT_REVERSIBLE`,
`RECORD_CONTENT_HASH_MISMATCH`, `CLAIM_CONFIDENCE_NOT_RECOMPUTABLE` (still open).
**The delivered check found a real drift on its first run** — see `SPEC-provenance.md` §2.
**Files:** `validate_evidence.py`, tests
**Risk:** Low — read-only checks.
**Trigger:** before source #2. **Priority: high** — these are the cheapest guarantees in the whole
backlog and they turn four conventions into four enforced properties. `CLAIM_CONFIDENCE_NOT_
RECOMPUTABLE` in particular is the guard POLICY-001 §G2 depends on.

### H4b — D3: documented build order produces wrong report statistics
`TraderProfile` counts hypotheses and questions from the index at build time, and the Knowledge
Library Report reads its statistics straight off the profile — so the documented Phase 7A command
sequence, which builds the profile *first*, always yields `hypothesisCount: 0`. **The code is
correct; the documented order is wrong.**

**Fix:** correct the ordering in `PROGRAM_007_STATUS.md` (covered by H13), and optionally add a
`build_knowledge_library()` orchestrator so the order cannot be got wrong by hand.
**Files:** `docs/PROGRAM_007_STATUS.md`; optionally a new orchestrator module
**Risk:** None for the doc fix.
**Trigger:** at commit. **Priority: high (doc), low (orchestrator).**
*Mitigated today by `OPERATOR-PLAYBOOK.md` Stage 7, which specifies the correct order.*

### H5 — D5: confidence insensitive to evidence quality at n=1
A single `low` opinion and a single `high` explicit statement both score 22.0.

**Fix:** unknown — requires real data to calibrate.
**Risk:** **Highest in this backlog.** Rewrites every stored confidence value; affects blueprint
classification, gap detection, hypothesis generation, and rule eligibility.
**Trigger:** **after** source #2 exists and ranking behaviour can be observed. **Priority: deferred
— do not attempt with one data point.**

---

## B. Scale infrastructure

### H6 — Ingestion toolkit ✅ **DELIVERED 2026-07-27**
`scripts/trader_intelligence/ingest.py` + `transcript_normalize.py`. Phases A–C of `PROPOSAL-002`
are built: manifest schema, fail-closed `--dry-run` validator, full two-phase runner, `--rollback`,
`--status`, `--verify-provenance`. Verified by a synthetic round-trip (ingest → apply → rollback →
byte-identical 250-node/475-edge baseline) and a negative test (one changed character → refused,
nothing written). Phase D (`--suggest`, further normalization profiles) remains open.

### H17 — Review queues re-append on every ingestion *(mitigated, root cause open)*
`run_post_annotation_pipeline` rebuilds all 14 review queues and appends fresh entries without
removing prior ones. Observed: an unrelated ingestion took the queue from 23 → 46 entries, i.e.
every existing entry duplicated. After 10 ingestions each entry would appear ~11 times.

**Mitigated:** `ingest.py` calls `gc_orphans()` after the post-annotation pipeline and after every
rollback, collapsing duplicates and removing entries whose target no longer exists.
**Root cause open:** `extraction_pipeline.run_post_annotation_pipeline` still re-appends.
**Fix:** make queue rebuild idempotent per `(queueType, entityType, entityId)`.
**Risk:** low. **Trigger:** before source #3. **Priority: medium-high.**

### H18 — Rollback completeness *(fixed)*
The first `--rollback` left 4 dangling references (a contradiction and three questions still cited
by review-queue entries), which failed the graph build. Rollback now also removes contradictions and
questions scoped to the run, their lifecycle events, and orphaned queue entries. `TraderProfile` /
`StrategyBlueprint` / `KnowledgeGap` / `Hypothesis` snapshots are still left in place deliberately —
they are immutable point-in-time artifacts that may summarise other sources — and the command says
so. **Priority: closed; documented in the playbook.**

### H19 — Rollback destroyed a prior source's claim *(SEVERE; fixed 2026-07-27)*
`--rollback` deleted every claim *touched* by the run's evidence. When source #2 attached a
cross-source `contextualizes` link to `CLAIM|TJR|20260727|003` (a source #1 claim), rollback treated
that claim as belonging to run 002 and removed it — 200 records in total.

**Fixed:** rollback now excludes any claim that also carries evidence from another source, retains
it, and recomputes its confidence once the run's links are removed. Verified non-destructively: the
same rollback would now delete 22 claims (all created by run 002) and keep 1.
**Recovered:** the claim was rebuilt from its surviving `ManualAnnotation` and its confidence
recomputed from surviving links; its destroyed `created` lifecycle event was reconstructed
timestamped-now and labelled as a reconstruction.
**Generalises to:** any destructive operation must treat cross-source references as *incoming* edges
it does not own. **Priority: closed. Retain as a regression test target (see H15).**

### H20 — `repositoryPath` went stale on completion *(fixed 2026-07-27)*
Phase 2 recorded the queue path, then moved the file, leaving `IntakeManifest.repositoryPath`
pointing at nothing. Caught by `--verify-provenance`. Now records the raw-archive path (which never
moves); the original queue location is preserved in `sourceMetadata.originalQueuePath`. The
dashboard's pending counter was rewired to read `intake/pending` + `intake/processing`.
**Priority: closed.**

### H21 — Confidence did not rise on a second source *(behaviour, not a defect)*
Two sources, 69 claims, still 100% `emerging`. The sources sit at different levels of abstraction
(strategy vs beginner foundations) and barely overlap; the single cross-source link is
`contextualizes`, which is deliberately unscored. **No fix wanted** — but it means source-count is
not a proxy for evidential strength, and acquisition should prioritise sources that restate the same
claims. Recorded so a future reader does not mistake this for a scoring bug. See `BACKLOG-002`.

### H22 — Section proposer fails on unpunctuated captions *(open)*
`_propose_sections` splits only after a line ending in `.`/`?`/`!`. Auto-caption transcripts often
carry no line-end punctuation at all, so it returned **one section for a 1,006-line transcript**
(`EVSRC|ALEX_G|20260728|001`). Sections had to be cut by hand.

**Fix:** fall back to a character/line budget with a timestamp-gap preference when punctuation
density is below a threshold. **Risk:** low. **Trigger:** next unpunctuated source.
**Priority: medium** — the manual workaround is reliable but is exactly the manual step the toolkit
exists to remove.

### H23 — Confidence-adjusting steps must precede confidence-reading steps *(fixed)*
`apply_author_independence_policy()` ran **after** `run_post_annotation_pipeline()`, which
auto-proposes rule candidates for claims already at `supported`. The pipeline therefore saw
pre-policy confidence and created two rule candidates from same-educator repetition alone — exactly
what `DECISION|MOGO|20260727|006` forbids. Corrected by moving the policy earlier; spurious proposals
and their lifecycle events removed; dangling queue entries garbage-collected.

**Generalises to:** any future step that mutates confidence must run before every step that reads it.
Worth a regression test asserting `proposalsCreated == 0` when all links share one independence group.
**Priority: closed; test recommended (see H15).**

### H7 — Cross-source duplicate detection
`evidence_dedup` and `classify_claim_relationship` compare a proposed claim against existing claims
at ingestion time, which is right. But there is no **library-wide** duplicate sweep, and no report
of near-duplicate claims *across* sources after the fact.

**Fix:** a `report_claim_duplicates` command producing a review-queue-backed near-duplicate report
across all sources, with the `difflib` threshold configurable.
**Risk:** Low — reporting only, never auto-merges.
**Trigger:** source #2. **Priority: high** — this is the mechanism that will reveal whether
PROPOSAL-003's F1 problem is real, and how often.

### H8 — Batch / resumable ingestion
Currently one transcript per run, with partial state on failure. At ten-plus sources this needs
resumability and a per-source status board.

**Fix:** falls out of PROPOSAL-002 phases B–C (`--stage`, `--rollback`) plus an ingestion status
report across all `IntakeManifest`s.
**Trigger:** source #4. **Priority: medium.**

### H9 — Review surface
14 review queues, 8 reviewer actions, and 23 open entries exist as a Python service layer with **no
UI**, deferred in Phase 7A because `index.html` is a trading application, not a research surface.

**Fix:** a standalone static review page, or a CLI reviewer. Explicitly **not** integrated into
`index.html`.
**Risk:** Medium — the first genuinely new surface; must not import trading code.
**Trigger:** when open review entries exceed ~50, or a second human reviews. **Priority: medium.**
*This is the largest single manual-effort sink after extraction itself.*

### H10 — Instrument abstraction
See `PROPOSAL-001`. **Trigger:** the FX-vs-multi-asset decision. **Priority: high.**

### H11 — Concept registry
See `PROPOSAL-003`. **Trigger:** source #3. **Priority: medium, schema hook now.**

---

## C. Documentation and process debt

### H12 — Stale front door *(addressed 2026-07-27)*
`docs/trader-intelligence/README.md` documented only the Wave-1 model, had a directory layout
missing `evidence/`, `graph/`, `acquisition/`, `imports/`, and `proposals/`, and pointed its
workflow section at a design report "delivered in chat" that no longer exists. Corrected in this
work cycle; the lost 16-step template is superseded by `OPERATOR-PLAYBOOK.md`.

### H13 — Program status documents will be wrong on commit
`PROGRAM_007_STATUS.md` asserts *"Was a real TJR transcript processed? **No.**"*;
`PROGRAM_006_STATUS.md` and `EVIDENCE_INTELLIGENCE.md` §44 record the same zero-transcript finding.
All become false the moment the intake commits.

**Fix:** update the negative-assertion tables, the SOURCE_REQUIRED sections, and the "Exact
commands" ordering (defect D3).
**Risk:** None — documentation.
**Trigger:** at commit. **Priority: high** — a status document that is confidently wrong is worse
than no status document.

### H16 — Repo-wide documents do not mention this subsystem
`docs/KNOWN_ISSUES.md`, `docs/ROADMAP.md`, and `docs/ARCHITECTURE.md` contain **zero** references to
Trader Intelligence. Someone reading the repo's architecture or roadmap would not learn the
subsystem exists. (`docs/TESTING.md` had the same gap; corrected 2026-07-27 with a §4 covering the
307 Python tests and the two suite-specific conventions.)

**Fix:** an `ARCHITECTURE.md` section placing the research subsystem relative to the application; a
`ROADMAP.md` entry; and `KNOWN_ISSUES.md` entries for defects D1–D5 plus whatever test state the
commit decision settles on.
**Risk:** None — documentation.
**Trigger:** `ARCHITECTURE.md` now; `ROADMAP.md`/`KNOWN_ISSUES.md` **at commit**, because their
content depends on decisions the owner has not yet made (whether the intake commits, and whether
the four obsolete tests are updated). Writing them earlier would record a state that may not
happen. **Priority: medium-high.**

### H14 — No ADR for the first production intake
ADR-008 and ADR-009 cover the engine. Nothing records the decisions this ingestion forced:
single-source confidence ceiling, licensing posture, scope conflict, the fixture-isolation fix.

**Fix:** ADR-010 — "First production knowledge intake and its constraints".
**Trigger:** at commit, alongside POLICY-001 ratification. **Priority: medium-high.**

### H15 — Test-isolation fix needs a permanent guard
Three fixtures were corrected to empty the copied `evidence/` tree, but nothing prevents a fourth
fixture from reintroducing the bug.

**Fix:** a meta-test asserting that any fixture which `copytree`s `TI_ROOT` also clears the evidence
record collections.
**Risk:** Low.
**Trigger:** next new fixture. **Priority: medium.** *This is the "don't regress the lesson" item —
the original bug was silent, and a silent bug that recurs is worse than one that never happened.*

---

## D. Suggested sequencing

| Wave | Items | Gate |
|---|---|---|
| **Now** | H13 + H4b (doc corrections), H14 (ADR-010), H16 (repo-wide docs), H6 phase A | Commit approval + PROPOSAL-002 Option 2 |
| **Before source #2** | H4 (provenance checks), H3 (D4), H7 (dup sweep), H15 (meta-test) | — |
| **With PROPOSAL-001** | H1 (D1), H10 (instrument) | FX-vs-multi-asset decision |
| **After source #2** | H2 (D2), H6 phases B–D | — |
| **At source #3** | H11 (concept registry) | — |
| **At source #4 / 50 review items** | H8 (batch), H9 (review surface) | — |
| **Deferred** | H5 (confidence calibration) | Real ranking data |

## E. Explicitly out of scope

- Any change to `index.html`, JVM, ALEX, `pipSize`, `pipValuePerLot`, or any protected function.
- Any network capability in any Trader Intelligence module. The no-network guarantee is structural
  and tested; **every item above preserves it.**
- Any LLM call inside the pipeline. Extraction judgment happens *before* the pipeline, by an
  operator authoring a manifest.
- Automatic promotion of any claim to a `StrategyRule`, under any circumstances.

---

## H24 — `--rollback` does not remove ContradictionRecords created by the run ✅ **FIXED IN THIS CYCLE'S DATA, NOT IN CODE**

**Found:** 2026-07-28, rolling back `INTAKE|ALEX_G|20260728|003`.

`rollback()` removed 258 records and correctly kept the 9 claims shared with earlier sources (the
`foreign` guard from the earlier incident held). But it left `XCONTRA|20260728|003` behind, pointing
at a claim it had just deleted. `validate_evidence.py` caught it immediately as an **ERROR**
(`INVALID_CONTRADICTION_RECORD`), which is the system working — but rollback should not be creating
dangling references for the validator to find.

Same class of gap: the run's `TraderProfile`, `StrategyBlueprint`, `KnowledgeGap` and `Hypothesis`
snapshots are also left behind. The tool prints a NOTE telling the operator to delete them by hand,
which is honest but is exactly the manual work the charter says to remove. 80 such records had to be
identified by build timestamp and deleted manually.

**Fix:** extend `rollback()` to remove ContradictionRecords whose *both* sides are claims being
deleted (never one-sided ones — those belong to another source), and to remove the snapshot
artifacts stamped with the run's build time. Print what it removed.

## H25 — Chapter headings corrupted `youtube_duration_label` segments ✅ **FIXED**

**Found:** 2026-07-28, ingesting `INTAKE|ALEX_G|20260728|003`.

The transcript carried YouTube chapter markers (`Chapter 2: TPT`) as bare lines with no duration
label. They fell through to the profile's no-timestamp branch, which **kept them as spoken text at
0:00**. Two consequences, one cosmetic and one not:

1. Four segments were stamped `startTimestamp` `0:00` — caught as a WARNING
   (`OVERLAPPING_SEGMENT_TIMESTAMPS`).
2. **The headings were spliced into segment `rawText` as if spoken** — the exact corruption the
   `youtube_timestamp_lines_chaptered` profile was written to prevent, in a profile that had never
   met a chaptered transcript.

No excerpt crossed a heading, so no evidence was affected — but that was luck, not design.

**Fixed** in `transcript_normalize.py`: `_CHAPTER_HEADING` classifies these lines as removed
non-spoken chrome, carrying the running timestamp forward so a section beginning at one is not
stamped 0:00. Detection is **lexical** (`Chapter <n>: …`), matching the reasoning already recorded
for `_UI_HEADER` — a structural rule would also eat line 1, which is genuine content. Line count is
preserved, so reversibility and the coverage assertion are unaffected.

The intake was rolled back and re-applied on the corrected normalization: **1,021 nodes, 1,958
edges, zero findings across all three integrity reports.**

## H26 — A URL fused onto the first timestamp is retained as spoken text ⚠️ **open**

**Found:** 2026-07-28, ingesting `INTAKE|ALEX_G|20260728|004`.

The pasted transcript began `https://www.youtube.com/watch?v=BcWxqfcjk9A0:000 secondsThere's a
specific confirmation…` — the video URL glued directly onto the first timestamp. The line therefore
does not match `_YT_LABEL`, falls through to the no-timestamp branch, and the **URL is retained as
spoken text at 0:00**, contaminating segment 1's `rawText`.

Same class as H25, different trigger. Impact is smaller — the URL sits at the very start of the
first segment and no excerpt was taken from that line — but it is the second time in two ingestions
that non-spoken chrome has entered a segment as speech.

**Constraint on the fix:** the trailing-URL case is already handled by `_URL_ONLY` in the chaptered
profile, but that pattern requires the URL to be *alone* on the line. A fused prefix must be split
off and **recorded as removed**, not stripped silently, or per-line reversibility breaks. Recorded in
the manifest's `provenance.knownArtifacts` for this source in the meantime.

## H27 — Duplicate detection missed the same video in a different transcript rendering ✅ **FIXED**

**Found:** 2026-07-29, when video `sZAE_lqdeno` was supplied a second time.

That video was ingested in cycle 008 as `EVSRC|ALEX_G|20260728|001` from a **duration-label**
transcript copy (22,106 bytes). It was re-supplied as a **timestamp-lines** copy — YouTube's "Show
transcript" panel rendering of the *same speech*. Different bytes, different SHA-256, so the
`contentHash` duplicate check passed it straight through.

**Why this matters more than a wasted ingestion.** A second ingestion of the same source would have
created a second `EvidenceSource`, a second set of claims, and — critically — a second **evidence
item on the same assertions from what the confidence engine would treat as the same independence
group but a different source id**. Under `DECISION|MOGO|20260727|006` group membership is keyed on
`traderId`, so the discount would still have applied and nothing would have crossed a threshold. But
the library would have carried duplicate claims, inflated evidence counts, and a false impression of
corroboration in the dashboard. **It was caught by hand, not by the tool.**

**Fixed** in `ingest.py`: the duplicate check now runs on **two keys**.

| Key | Catches |
|---|---|
| `contentHash` | The same **file** offered twice |
| `canonicalReference` | The same **video** offered twice in a different transcript rendering |

`_video_key()` extracts the YouTube video id, so `?v=X`, `?v=X&list=Y`, `?v=X&t=90` and `youtu.be/X`
all collapse to one key. Non-YouTube URLs fall back to the URL with query and fragment stripped.

**Deliberately conservative.** A false negative (missed duplicate) is recoverable by `--rollback`; a
false positive would block a legitimate source. The matcher therefore errs toward under-matching, and
it is a no-op when `--url` is not supplied.

**Verified three ways:** the real duplicate is rejected with a message naming the prior source and
title; a new video id passes; omitting `--url` does not crash.

**Residual gap, recorded not fixed:** a source ingested **without** a `--url` cannot be
canonical-matched later. Ten of the eleven current sources have a `canonicalReference`; the
exception is `EVSRC|TJR|20260727|001`, whose upstream video identity has never been established. It
remains hash-only for duplicate purposes.


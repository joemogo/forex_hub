# MOGO Trader Intelligence Framework

**Status:** Operational research subsystem. Schemas, offline Python tooling
(`scripts/trader_intelligence/`), and one real ingested source. **No runtime storage and no trading
behavior** — nothing here is wired into `index.html`, and no record here authorizes any code change
by itself.

This directory turns trader research material (TJR, and eventually any other trader/strategy MOGO
studies) into structured, provenance-tracked, confidence-rated data that later, separately-
authorized waves can implement against — one resolved rule at a time, never by silent invention.

## Start here

| If you want to… | Read |
|---|---|
| **See current library state** | [`KNOWLEDGE-DASHBOARD.md`](KNOWLEDGE-DASHBOARD.md) — generated, always current |
| Ingest a transcript | [`OPERATOR-PLAYBOOK.md`](OPERATOR-PLAYBOOK.md) |
| See the periodic health review | [`TRADER-INTELLIGENCE-REVIEW.md`](TRADER-INTELLIGENCE-REVIEW.md) |
| Know how to classify an excerpt | [`STANDARDS-extraction.md`](STANDARDS-extraction.md) |
| Audit where a claim came from | [`SPEC-provenance.md`](SPEC-provenance.md) |
| Look up a term | [`GLOSSARY.md`](GLOSSARY.md) |
| Compare strategies | [`CROSS-STRATEGY-ANALYSIS.md`](CROSS-STRATEGY-ANALYSIS.md) |
| See what happened in each cycle | [`RESEARCH-LOG.md`](RESEARCH-LOG.md) |
| See what is proposed but not built | [`proposals/README.md`](proposals/README.md) |
| Understand the evidence engine in depth | [`../EVIDENCE_INTELLIGENCE.md`](../EVIDENCE_INTELLIGENCE.md) |
| See the current library's state | [`imports/tjr/PRE-COMMIT-RESEARCH-REPORT.md`](imports/tjr/PRE-COMMIT-RESEARCH-REPORT.md) |

## The three layers

Research flows through three subsystems, each with its own schemas and README:

1. **Acquisition** (`acquisition/`) — candidate sources, duplicate detection, priority scoring.
   Offline and manual; zero network capability by design. *What should we ingest next?*
2. **Evidence** (`evidence/`) — the engine added by PROGRAM-006/007: intake manifests, transcript
   segments, annotations, evidence items, claims, links, contradictions, questions, review queues,
   trader profiles, blueprints, knowledge gaps, hypotheses. *What do we actually know, and how
   well?*
3. **Knowledge Graph** (`graph/`) — a deterministic build over every authoritative record, with
   integrity validation and the 18-stage `PromotionState` gate. *How does it all connect, and what
   is authorized?*

## Which entity model do I use?

Two generations of schema coexist deliberately (ADR-008 §14). This is the single most common point
of confusion, so state it plainly:

| Layer | Schemas | Use for |
|---|---|---|
| **Evidence layer** (current) | `evidence/schema/` — `EvidenceSource`, `TranscriptSegment`, `ManualAnnotation`, `EvidenceItem`, `Claim`, `EvidenceClaimLink`, … | **All new research intake.** Everything the pipeline reads and writes. |
| **Wave-1 rule layer** (current, different level) | `schema/trader-record`, `strategy-family`, `strategy-rule`, `rule-version`, `rule-evidence`, `rule-contradiction`, `unresolved-question` | Trader records, strategy families, and — eventually — actual `StrategyRule`s and their evidence aggregation |
| **Wave-1 intake entities** (superseded in practice) | `schema/research-source`, `source-segment`, `strategy-assertion`, `chart-example`, `research-intake-report` | Nothing new. The evidence layer supersedes these; zero instances exist. Retained because ADR-008 performed no migration. |

Rule of thumb: **evidence layer for everything below a rule; Wave-1 layer for the rule itself and
the trader/family records that scope it.**

## Why generic, not per-trader

MOGO tracks (or will track) research on multiple traders/strategies — TJR, ALEX G, JVM, and
potentially future traders or MOGO-original hybrid strategies. This framework is deliberately
**trader-agnostic**: there is exactly one schema per entity type, and every trader-specific fact
lives in a `traderId`/`strategyFamilyId` field value, never in a type name. Adding a new trader
never requires a new schema file — only a new `TraderRecord` and, as research accumulates, new
instances of the same generic entities.

## Wave-1 entities

The original trader-agnostic schema set. See "Which entity model do I use?" above before writing
against these — the intake-related entries are superseded in practice by `evidence/schema/`.

| Entity | Schema file | Purpose |
|---|---|---|
| `TraderRecord` | `schema/trader-record.schema.json` | One per trader (TJR, ALEX_G, JVM, future) |
| `StrategyFamily` | `schema/strategy-family.schema.json` | One or more named methodologies per trader |
| `ResearchSource` | `schema/research-source.schema.json` | One external or internal source of research material |
| `SourceSegment` | `schema/source-segment.schema.json` | One excerpt/time-range within a source |
| `ChartExample` | `schema/chart-example.schema.json` | One chart/trade example cited as evidence |
| `StrategyAssertion` | `schema/strategy-assertion.schema.json` | One specific claim from one source segment |
| `RuleEvidence` | `schema/rule-evidence.schema.json` | Aggregates the assertions/examples supporting one rule |
| `StrategyRule` | `schema/strategy-rule.schema.json` | One discrete, named rule |
| `RuleVersion` | `schema/rule-version.schema.json` | One historical revision of a rule |
| `RuleContradiction` | `schema/rule-contradiction.schema.json` | A retained record of disagreeing evidence |
| `UnresolvedQuestion` | `schema/unresolved-question.schema.json` | An open question blocking further progress |
| `ResearchIntakeReport` | `schema/research-intake-report.schema.json` | Summary of one research intake session |

All schemas declare `"$schema": "https://json-schema.org/draft/2020-12/schema"` consistently.

## Core principles (non-negotiable, enforced by the schemas themselves where possible)

1. **A trader's operational codebase status and its external-research status are two separate
   fields** (`repositoryModelStatus` and `externalResearchStatus` on `TraderRecord`). A trader can
   be fully operational in MOGO's codebase while its external research status is `not_started`
   (true of ALEX_G and JVM today) — never conflate the two.
2. **Assertions are immutable.** A correction never edits an existing `StrategyAssertion` — it
   creates a new one with `supersedesAssertionId` pointing at the one it revises. The full history
   is always walkable.
3. **Exact source language is kept separate from MOGO's interpretation** — `exactQuoteOrFaithfulParaphrase`
   vs. `normalizedMeaning` on every assertion.
4. **A rule cannot become `modeled` without cited evidence.** `StrategyRule.sourceEvidenceIds` must
   be non-empty once `modelingStatus` is `modeled`.
5. **Four confidence dimensions, never collapsed into one:** `sourceConfidence`,
   `interpretationConfidence`, `implementationConfidence`, `performanceConfidence`. A rule can be
   extremely well-evidenced by source material (`sourceConfidence: very_high`) while completely
   unvalidated by real trading data (`performanceConfidence: not_applicable`) — collapsing these
   would hide that gap. **`performanceConfidence` must never be inferred from source material
   alone** — it requires real replay/shadow/paper trading data.
6. **Contradictions are retained forever, even once resolved.** `RuleContradiction.status`
   transitions, but the record and both sides of the disagreement are never deleted.
7. **Authoritative existing documents are cross-referenced, never duplicated.** Where a document
   like `docs/adr/ADR-007-tjr-strategy-definition.md` already records an open question in full,
   `UnresolvedQuestion.externalRef` cites it exactly rather than re-typing the text — preventing
   silent drift between two copies of the same ledger.
8. **This framework is documentation and data only.** Nothing here is wired into `index.html`,
   no `StrategyRule` becoming `modeled` here authorizes any code change by itself — every future
   implementation wave requires its own separate, explicit authorization, exactly like every other
   engineering milestone in this repository.

## Directory layout

```
docs/trader-intelligence/
  README.md                     -- this file
  OPERATOR-PLAYBOOK.md          -- how to ingest a transcript, end to end
  STANDARDS-extraction.md       -- how to classify what you extract
  SPEC-provenance.md            -- the provenance chain and its invariants

  schema/                       -- Wave-1 JSON Schema definitions (table above)

  intake/                       -- the transcript queue (drop files in pending/)
    README.md  pending/  processing/  completed/  rejected/  manifests/

  queues/                       -- replay and validation work queues
    README.md  replay/  validation/

  acquisition/                  -- candidate sources, duplicates, priority scoring
    README.md  schema/  candidates/  weights/  queue/  reports/

  evidence/                     -- the Evidence Intelligence Engine (PROGRAM-006/007)
    schema/                     -- 18 schemas: intake, segment, annotation, evidence,
                                --   claim, link, question, queue, profile, blueprint,
                                --   gap, hypothesis, contradiction, integrity report
    intake/ segments/ annotations/ sources/ items/ claims/ links/
    contradictions/ questions/ review-queue/ proposals/
    profiles/ blueprints/ gaps/ hypotheses/ lifecycle/ reports/

  graph/                        -- deterministic Knowledge Graph build
    README.md  schema/  build/  decisions/  reports/

  imports/                      -- raw source material and per-ingestion reports
    tjr/  raw/  normalized/

  proposals/                    -- proposals, policies, and backlog (not implemented)
    README.md  POLICY-001  PROPOSAL-001..003  BACKLOG-001..003

  traders/
    tjr/ alex-g/ jvm/           -- profile.json, strategy-families/, open-questions/
```

**Empty directories are never created as placeholders.** A subdirectory appears with its first
real file. (`evidence/` collections are the exception: the pipeline creates them on first run.)

Tooling lives in `scripts/trader_intelligence/` — pure Python standard library, no network, no LLM.
Tests live in `tests/trader_intelligence/`. The operator entry points are:

| Command | Purpose |
|---|---|
| `ingest.py <file> --trader X` | Phase 1: verify, dedupe, archive, normalize, section, draft manifest |
| `ingest.py --apply <manifest>` | Phase 2: validate fail-closed, then register, build, validate, publish |
| `ingest.py --status` | Queue and library state |
| `ingest.py --verify-provenance` | Re-verify archives, working copies, maps and excerpts |
| `ingest.py --rollback <intakeId>` | Remove every record from one run |
| `build_knowledge_dashboard.py` | Regenerate the dashboard (the CLI does this automatically) |

## Research intake workflow

**See [`OPERATOR-PLAYBOOK.md`](OPERATOR-PLAYBOOK.md)** for the validated end-to-end runbook. In
brief: drop the transcript in `intake/pending/`, run `ingest.py <file> --trader X`, fill in the
`annotations` array of the draft manifest, then run `ingest.py --apply <manifest>`. Everything
mechanical is automated; extraction judgment is deliberately not.

In short: verify and hash the raw file → preserve a byte-identical copy → normalize reversibly →
segment into traceable sections → register intake, source and segments → extract verbatim excerpts
into annotations → record contradictions and open questions → build profile, blueprint, gaps and
hypotheses → rebuild and validate the graph → report and **stop for owner review**.

> The Wave-1 16-step intake template referenced here previously lived only in a chat-delivered
> design report and is no longer retrievable. The playbook supersedes it and is validated against a
> real ingestion rather than a design sketch.

## Current state

One real source has been ingested (`INTAKE|TJR|20260727|001`, awaiting owner review): 47 claims, 62
evidence items, 24 segments, 2 contradictions, 14 open questions, 6 knowledge gaps, 21 hypotheses,
1 draft blueprint. **All 47 claims sit at `emerging` confidence and zero `StrategyRule`s exist** —
a single source cannot corroborate itself past the confidence threshold, by design. See
[`proposals/POLICY-001`](proposals/POLICY-001-emerging-confidence-ceiling.md).

# MOGO Trader Intelligence Framework

**Status:** Wave 1 — schema and documentation foundation only. No code, no runtime storage, no
trading behavior. This directory exists to turn future trader research material (TJR, and
eventually any other trader/strategy MOGO studies) into structured, provenance-tracked,
confidence-rated data that later, separately-authorized waves can implement against — one
resolved rule at a time, never by silent invention.

## Why generic, not per-trader

MOGO tracks (or will track) research on multiple traders/strategies — TJR, ALEX G, JVM, and
potentially future traders or MOGO-original hybrid strategies. This framework is deliberately
**trader-agnostic**: there is exactly one schema per entity type, and every trader-specific fact
lives in a `traderId`/`strategyFamilyId` field value, never in a type name. Adding a new trader
never requires a new schema file — only a new `TraderRecord` and, as research accumulates, new
instances of the same generic entities.

## Entities

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
  README.md
  schema/                       -- the 12 generic JSON Schema definitions above
  traders/
    tjr/
      profile.json
      open-questions/
        adr-007-cross-reference.json
    alex-g/
      profile.json
    jvm/
      profile.json
```

Subdirectories for `sources/`, `assertions/`, `rules/`, `contradictions/`, and `chart-examples/`
under a given trader are created only once that trader's first real file of that type exists —
never as empty placeholders.

## Research intake workflow

See the MOGO Trader Intelligence Framework Wave 1 design report (delivered in chat) for the full
16-step reusable intake template. In short: register the source → segment it → extract
explicit/implied/inferred assertions → capture chart/trade examples → match against existing
rules → propose new rules (never auto-model them) → record contradictions → update open
questions → record confidence changes → summarize impact on implementation/replay/shadow/paper
readiness → list exactly what requires an owner decision.

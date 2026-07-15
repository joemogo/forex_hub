# AI Roadmap

**Status: none of this is implemented yet.** This document records the approved *reservation* for
future AI features made during the Strategy SDK design pass — it is a roadmap, not a build plan,
and nothing here should be read as scheduled or in progress.

## The six named future capabilities

- AI Coach
- AI Trade Review
- AI Weekly Reports
- AI Strategy Comparison
- AI Research
- AI Replay

## The design principle: reuse the required SDK surface first

Rather than adding new required Service hooks for six features that don't exist yet, each was
evaluated against what it would actually need to consume:

- **AI Weekly Reports, AI Strategy Comparison, AI Research** are cross-strategy *aggregate*
  consumers — they read `computePerformance()` + Manifest DNA/Playbook across multiple Registry
  entries. **They need zero new per-strategy SDK surface.** They belong as Shared Services that
  consume the required contract, exactly like the Dashboard already does.
- **AI Trade Review / AI Coach** want a per-trade narrative. This already exists: journal records
  carry `whyQualified`, `howEntryWasCalculated`, `howStopWasCalculated`, `howTargetWasCalculated`,
  and `whyClosed` — fields built for human-readable trade explanation that are exactly what an AI
  coach would want to read. No new hook needed; this is a Shared Service reading data that's
  already there.
- **AI Replay** is the one genuinely new capability. It gets exactly one optional Service method,
  `getContextSnapshot()` (see [STRATEGY_SDK.md](STRATEGY_SDK.md)), returning a serializable,
  read-only bundle (Manifest identity + Playbook + recent normalized journal records +
  `computePerformance()` output where available). Default-derivable from required fields, so even
  a strategy that implements nothing AI-specific still has *something* for a future AI feature to
  work with.

**Net addition to the SDK for all six features: one optional method** (`getContextSnapshot()`,
plus the already-scoped `getExplanation(tradeId)` as a richer, optional per-trade variant), both
default-derived from data that's already required. This was a deliberate choice to avoid
speculative, ahead-of-need API surface — see
[../docs/adr/ADR-005-strategy-framework.md](../docs/adr/ADR-005-strategy-framework.md).

## What is explicitly NOT solved yet

- **Trust boundary for non-MOGO-authored strategy/AI code.** `Manifest.trustLevel` reserves a
  field (`verified` today) for a future `community`/untrusted tier, but nothing sandboxes or
  validates strategy code today — irrelevant while every strategy is MOGO-authored, but a real gap
  the moment third-party code is ever allowed to execute in the same page. Out of scope until
  that's a concrete plan.
- **Any actual model integration, prompt design, or UI for these six features.** This document
  reserves *where* they would plug in, not *how* they would work.
- **AI Assistant (the existing feature)** is unrelated to this roadmap — it's a general chat
  interface with read access to live app state, already shipped, not part of the Strategy SDK.

## Existing precedent this roadmap builds on

- `AI_ASSISTANT` (existing, shipped) already demonstrates the read-only-access pattern this
  roadmap extends: it can read live watchlist/positions/journal/rules state but has no write
  access to any trading state.
- `computeMogoStrategyPerformance()`'s honest insufficient-sample gating (never fabricating a win
  rate below a real sample size) is the pattern any future AI-facing statistic must follow — per
  [ADR-004](../docs/adr/ADR-004-read-only-analytics-principle.md), which applies to AI-consumed
  data exactly as it does to human-displayed data.

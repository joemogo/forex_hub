# PROGRAM-003 Knowledge Graph & Reasoning Engine — Phase 1 (Core Foundation)

**Status:** Phase 1A/1B/1C — schemas, deterministic builder, integrity validator, read-only query
engine. No reasoning layer, no runtime integration, no trading effect of any kind.

## Constitutional principle

Nothing may influence trading until it has passed through the Knowledge Graph and all required
promotion gates. This applies to external research, trader rules, AI-generated hypotheses,
repository observations, replay discoveries, paper-trading results, journal insights, and every
future live-performance finding. No research assertion, proposed rule, learned pattern, confidence
adjustment, or AI recommendation may directly alter strategy logic, candidate qualification,
entries, exits, stops, targets, position sizing, risk, paper execution, or live execution.

The graph **is**: a research and governance layer, deterministic, read-only relative to
authoritative research records, fully provenance-backed, isolated from runtime trading.

The graph **is not**: a trading engine, a strategy execution dependency, an autonomous promotion
mechanism, or an AI-generated source of truth.

## What this directory contains

```
docs/trader-intelligence/graph/
  README.md                          -- this file
  schema/
    graph-node.schema.json           -- GraphNode (generated artifact shape)
    graph-edge.schema.json           -- GraphEdge (generated artifact shape)
    graph-manifest.schema.json       -- GraphManifest / build record (one schema, both concepts)
    graph-integrity-report.schema.json
    owner-decision.schema.json       -- OwnerDecision (authoritative source data)
    promotion-state.schema.json      -- shared 18-state promotion-lifecycle enum
  build/
    nodes.json                       -- generated, committed, never hand-edited
    edges.json                       -- generated, committed, never hand-edited
    manifest.json                    -- generated, committed, never hand-edited
  reports/
    integrity-report.json            -- generated, committed, never hand-edited
  decisions/
    *.json                           -- OwnerDecision instances: authoritative, hand-authored,
                                         one file per decision, never edited after creation
```

Executable tooling lives outside `docs/`, under `scripts/trader_intelligence/`
(`build_graph.py`, `query_graph.py`) and `scripts/trader_intelligence/graph_common.py` (shared
canonical-JSON/hashing/ID utilities). Tests live under `tests/trader_intelligence/`.

## Authoritative-data rule

Every file under `docs/trader-intelligence/traders/**` (profiles, strategy families, and — once
research intake produces them — sources, segments, assertions, evidence, rules, rule versions,
contradictions, unresolved questions, intake reports) and every file under
`docs/trader-intelligence/graph/decisions/` is **authoritative**. The graph builder only *reads*
these files; it never writes to them, never edits them, and never becomes a second source of truth
for anything they say. Everything under `graph/build/` and `graph/reports/` is **generated**:
produced deterministically from the authoritative files, safe to delete and rebuild at any time,
and never hand-edited. Every generated node, edge, manifest, and integrity report carries
`"generated": true` and a `sourceFile`/`contentHash` pair identifying exactly which authoritative
record produced it and at what content state.

## What Phase 1 deliberately does not do

- No Concept Registry (deferred to a future phase, once real primary-source terminology exists to
  normalize — building it now would mean inventing normalized concepts from zero real data).
- No natural-language reasoning or LLM interpretation of graph output.
- No replay, paper-trade, journal, or Decision Event integration.
- No browser UI, no Strategy Center visualization, no runtime graph loading of any kind.
- No network access, no transcript acquisition, no source discovery.
- No trading-engine integration, no database (external, SQLite, or otherwise) — every artifact is
  plain, git-reviewable JSON.

## No runtime coupling

`index.html` never imports, fetches, reads, evaluates, or otherwise references anything under
`docs/trader-intelligence/`. This is verified directly (grep, not assumed) as part of every
milestone that touches this directory. If that ever needs to change, it is a separate, explicitly
authorized engineering milestone in its own right — never a side effect of a graph-layer change.

# PROGRAM-004 Research Acquisition and Prioritization Engine — Phase 1

**Status:** Phase 1A–1D — schemas, offline manual registration, duplicate/priority
scoring, read-only queue. Zero network connectors. Zero trading effect.

## Constitutional boundary

Research candidates are untrusted input. No acquisition record, priority score, topic
classification, duplicate assessment, uploaded transcript, owner note, or queue result
may directly influence candidate generation, trade qualification, entries, exits, stops,
targets, position sizing, risk, replay decisions, paper execution, or live execution.

This layer may: register research candidates, normalize URLs, store owner-provided
metadata, reference uploaded content, identify exact duplicates, flag possible
near-duplicates, classify likely topics with confidence, compute transparent priority
dimensions, produce a deterministic research queue, support owner review, and report
what should be researched next.

It may not: acquire content from the network, download videos/transcripts, scrape
websites, call external APIs, run browser automation, create `StrategyAssertion`s or
`StrategyRule`s, promote research into trading, add acquisition-specific nodes to the
Knowledge Graph, or modify runtime trading.

## Relationship to the Trader Intelligence Framework and Knowledge Graph

A `ResearchSourceCandidate` is **not** a `ResearchSource`. It carries zero authority
until a human, in a separate and explicitly authorized step, promotes an
`APPROVED_FOR_RESEARCH_INTAKE` candidate into a real `ResearchSource` file under
`docs/trader-intelligence/traders/{trader}/sources/` — at which point it becomes subject
to every existing Wave 1/Wave 2 rule (immutable assertions, four separate confidence
dimensions, no invented rules). Nothing in this directory is ever read by
`build_graph.py`'s existing node/edge discovery — the acquisition queue is a fully
separate, adjacent system, exactly as the Trader Intelligence Framework was to the
Knowledge Graph before PROGRAM-003.

## Directory layout

```
docs/trader-intelligence/acquisition/
  README.md
  schema/
    research-source-candidate.schema.json
    duplicate-group.schema.json
    priority-weight-profile.schema.json
    acquisition-status.schema.json      -- shared 18-state enum
  candidates/
    {candidateId}.json                  -- authoritative
    {candidateId}.content.txt           -- authoritative, only when storagePolicy=COMMITTED_OWNER_CONTENT
  queue/
    queue-snapshot.json                 -- generated
    manifest.json                       -- generated
  reports/
    duplicate-report.json               -- generated
    priority-report.json                -- generated
  weights/
    priority-profile-mogo-research-v1.json  -- authoritative, versioned
```

Acquisition `OwnerDecision` records reuse the existing, generic
`docs/trader-intelligence/graph/decisions/` directory and schema (extended additively
with an `acquisition` `decisionType`/`approvalScope` value) — one shared schema, not a
parallel one.

## Storage policy (Owner Decision 5)

Three policies: `METADATA_ONLY` (default for all third-party URLs), `REFERENCED_LOCAL_CONTENT`
(a controlled local file path + hash, content itself stays outside the repo),
`COMMITTED_OWNER_CONTENT` (small owner-authored text only, explicitly opted into per
candidate). Never stored: video/audio binaries, automatically downloaded transcripts,
books, course archives, executable files, compressed archives. PDFs are reference-only
in this milestone.

## No network rule

Zero network imports anywhere in `scripts/trader_intelligence/{acquisition_common,
register_source,detect_duplicates,prioritize_sources,build_research_queue,
query_research_queue,validate_acquisition}.py` — no `requests`, `urllib.request`,
`http.client`, sockets, browser automation, `curl`/`wget`/`yt-dlp`, or any external API.
Enforced by a permanent test (`test_no_network_imports`).

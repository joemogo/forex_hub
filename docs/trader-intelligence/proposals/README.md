# Trader Intelligence — Proposals and Backlog

Documents only. **Nothing in this directory has been implemented.** Each item requires explicit
owner approval — and, where noted, a traceable `OwnerDecision` record — before any code is written.

Created 2026-07-27, following the first production knowledge ingestion
(`INTAKE|TJR|20260727|001`). See `../imports/tjr/PRE-COMMIT-RESEARCH-REPORT.md` for the intake
itself.

| Document | Kind | Status |
|---|---|---|
| [POLICY-001 — Emerging Confidence Ceiling](POLICY-001-emerging-confidence-ceiling.md) | Policy | ✅ **Ratified** 2026-07-27 as `DECISION\|MOGO\|20260727\|003` + `\|004` |
| [PROPOSAL-001 — Instrument Abstraction](PROPOSAL-001-instrument-abstraction.md) | Proposal | **Decision required** — FX-only vs multi-asset |
| [PROPOSAL-002 — Ingestion Toolkit](PROPOSAL-002-ingestion-toolkit.md) | Proposal | **Decision required** — 4 options, phase A recommended |
| [PROPOSAL-003 — Concept Registry](PROPOSAL-003-concept-registry.md) | Proposal | **Decision required** — timing; defer to source #3 recommended |
| [BACKLOG-001 — Replay Validation](BACKLOG-001-replay-validation.md) | Backlog | Gated on pipeline review + replay authorization |
| [BACKLOG-002 — TJR Source Acquisition](BACKLOG-002-tjr-source-acquisition.md) | Backlog | Gated on licensing resolution |
| [BACKLOG-003 — Pipeline Hardening](BACKLOG-003-pipeline-hardening.md) | Backlog | 17 items, trigger-gated |
| [BACKLOG-004 — Human-Assisted Research Ingestion & Decision-Difference Analysis](BACKLOG-004-human-assisted-research-ingestion.md) | Backlog | Milestone number **deferred**; eligible after governed research intake, standardized research-package interface and artifact-ingestion governance mature |
| [REPLAY-CANDIDATES](REPLAY-CANDIDATES.md) | Specifications | 9 candidates, charter format; gated on replay authorization |
| [MOGO-IMPLEMENTATION-CANDIDATES](MOGO-IMPLEMENTATION-CANDIDATES.md) | Recommendations | 12 engines assessed; 4 buildable now, 8 evidence-blocked |

Normative documents that are **not** proposals (they describe how the system works today) live one
level up: [`../OPERATOR-PLAYBOOK.md`](../OPERATOR-PLAYBOOK.md),
[`../STANDARDS-extraction.md`](../STANDARDS-extraction.md),
[`../SPEC-provenance.md`](../SPEC-provenance.md), [`../GLOSSARY.md`](../GLOSSARY.md),
[`../CROSS-STRATEGY-ANALYSIS.md`](../CROSS-STRATEGY-ANALYSIS.md),
[`../RESEARCH-LOG.md`](../RESEARCH-LOG.md).

## Dependency order

```
Licensing resolution (owner)  ─┬─►  BACKLOG-002  ──►  2nd TJR source  ──┐
                               │                                        ├─►  claims exceed `emerging`
Pipeline review (owner)  ──────┴─►  BACKLOG-001  ──►  replay evidence ──┘         (POLICY-001)

FX-vs-multi-asset decision (owner) ──►  PROPOSAL-001  ──►  index modeling, RV-05, RV-09
                                            └──────────►  BACKLOG-003/H1 (defect D1)

Toolkit decision (owner) ──────────►  PROPOSAL-002  ──►  repeatable ingestion (Priorities 1 & 2)
                                            └──────────►  manifest schema ──► PROPOSAL-003 hook

source #3 ─────────────────────────►  PROPOSAL-003  ──►  cross-trader comparison

MOGO-020 governed answer intake ──┐
artifact-ingestion governance ────┼─►  BACKLOG-004  ──►  Decision-Difference dataset
standardized research package ────┘   (milestone number deferred)
```

`BACKLOG-004` is the only item here whose milestone number is deliberately unassigned: three of its
dependencies do not exist yet, so any number would imply a sequence position the dependency table
does not support. **MOGO-020 supplies foundational dependencies but does not implement it.**

## The four open owner decisions

| # | Decision | Cost to decide | Blocks |
|---|---|---|---|
| 1 | **Supply source material** — no unprocessed transcript exists | None (owner input) | **All ingestion. The pipeline is authorized and idle.** |
| 2 | Licensing posture on `EVSRC\|TJR\|20260727\|001` (and any new source) | None (owner input) | Acquisition of T8 (ICT) / T9 (Alex G) |
| 3 | FX-only vs multi-asset | None (owner input) | PROPOSAL-001, index modeling, defect D1 |
| 4 | Ingestion toolkit scope | Approval only | Priorities 1 & 2 |
| 5 | Commit the first intake + the 4 obsolete tests | Approval only | Everything downstream |

**Resolved 2026-07-27:** the confidence/promotion policy and equal evidence-source standing are
ratified as `DECISION|MOGO|20260727|003` and `|004`. Autonomous processing is authorized.

Decisions 1–3 require no engineering work. Decision 1 is now the binding constraint: every
governance obstacle has been removed and the pipeline has no input.

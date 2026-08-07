# ADR-012 — Automation Platform Architecture

**Status:** **Accepted** · **Date:** 2026-08-07 · **Approved:** 2026-08-07 (MOGO-009 Step 2A) · **Milestone:** MOGO-009 Step 2
**Constitution:** [`AUTOMATION_PLATFORM_CONSTITUTION.md`](../governance/AUTOMATION_PLATFORM_CONSTITUTION.md) v1.0 — binding, and senior to this ADR
**Specification:** [`MOGO-009-AUTOMATION-PLATFORM-ARCHITECTURE.md`](../architecture/MOGO-009-AUTOMATION-PLATFORM-ARCHITECTURE.md)
**Catalog:** [`MOGO-009-CONTRACT-CATALOG.md`](../architecture/MOGO-009-CONTRACT-CATALOG.md)
**Inventory:** [`MOGO-009-AUTOMATION-PLATFORM-ARCHITECTURE-INVENTORY.md`](../reports/MOGO-009-AUTOMATION-PLATFORM-ARCHITECTURE-INVENTORY.md)
**Related:** [ADR-004](ADR-004-read-only-analytics-principle.md) · [ADR-008](ADR-008-evidence-intelligence-engine.md) · [ADR-010](ADR-010-evidence-package-persistence.md)

> **Decision-identifier reconciliation.** The Step 1 inventory's decision register used an earlier
> numbering in which `D-01` was "modular monolith vs services" and every subsequent decision was
> offset by one. **This ADR's numbering is authoritative for Phase II.** Mapping:
>
> | Step 1 inventory | This ADR |
> |---|---|
> | D-01 modular monolith vs services | folded into the **Decision** section (approved, unnumbered) |
> | D-02 managed runtime + manifest | **D-01** |
> | D-03 orchestration engine | **D-02** |
> | D-04 queue technology | **D-03** |
> | D-05 event storage | **D-04** |
> | D-06 … D-14 | **D-06 … D-14** (unchanged) |
> | — | **D-05** persistence and recovery *(new in Step 2)* · **D-15** first connector *(new in Step 2)* |
>
> The Step 1 inventory is retained unedited as the historical record of that step.

---

## Context

MOGO-009 introduces an autonomous research platform. Step 1 established, by direct repository
inspection, that MOGO has a mature scientific core and a substantially complete ingestion pipeline
but **no operating platform**: zero occurrences of `worker`, `retry`, `backoff`, `checkpoint`,
`resume`, `concurren`, `correlation` or `causation` across `scripts/`, and no package manifest, lock
file, CI, or build system anywhere.

Fifteen decisions must be settled before contracts can be implemented. Each is recorded below with
the repository evidence that constrains it.

**Status vocabulary used per decision:**
**(A)** approved by existing governance · **(S)** safe additive architecture decision ·
**(H)** requires explicit human approval.

---

## D-01 — Runtime and first package-manifest strategy · **(H)**

**Problem.** The platform needs a runtime. MOGO has never had a dependency manifest.

**Evidence.** No `package.json`, `requirements.txt`, `pyproject.toml`, lock file, CI, or container.
`.gitignore` states MOGO is "a static, single-file application with no build step and no package
manager." The ingestion pipeline is 36 stdlib-only Python modules; the browser app has exactly one
CDN dependency.

**Options.** (a) stdlib-only, no manifest · (b) Python manifest, stdlib-biased · (c) Node manifest ·
(d) both.

**Advantages/disadvantages.** (a) preserves zero supply chain but leaves dependencies undeclared and
unpinned as the platform grows. (b) matches the existing pipeline language and test suites; adds the
project's first supply chain, minimally. (c) duplicates the language boundary for no gain — the
browser code is not importable. (d) two toolchains, two audit surfaces.

**Operational risk.** Low for (b): Python 3.14.6 is already required by `regression-baseline-tools.py`
and the 8 Python suites.
**Governance risk.** Low — no scientific artifact depends on the runtime.
**Reversibility.** High.

**Recommendation: (b) Python-first with a manifest, stdlib-biased.** Third-party dependencies require
justification per addition; the platform should be runnable from a bare clone.

## D-02 — Orchestration execution model · **(H)**

**Problem.** Nothing coordinates work today.

**Evidence.** The only precedent is the `intake/` four-state directory machine, documented as making
"queue position visible from the filesystem alone — no separate status database to drift out of sync."

**Options.** (a) internal minimal orchestrator · (b) adopt Temporal/Prefect/Airflow · (c) cron +
scripts.

**Advantages/disadvantages.** (a) small, inspectable, no infrastructure, fits one operator; must
implement leases/backoff/dead-letter correctly. (b) mature semantics free; heavy dependency, server
process, and a large operational surface for a single-operator research repo. (c) no durability, no
retry, no recovery — reproduces today's gap.

**Operational risk.** (a) medium — correctness is on us; mitigated by the state machine and tests.
**Governance risk.** (b) highest: a workflow engine's own state store invites operational state to
drift toward being treated as evidence.
**Reversibility.** (a) high — contracts are engine-agnostic.

**Recommendation: (a) internal minimal orchestrator.** Adopting an engine later is far easier than
removing one.

## D-03 — Queue and task-delivery model · **(S)**

**Problem.** How tasks are stored, claimed and delivered.

**Evidence.** No queue runtime; the `intake/` directories are the working precedent; a single
operator, single host.

**Options.** (a) filesystem directories · (b) SQLite-backed queue · (c) Redis · (d) broker.

**Advantages/disadvantages.** (a) maximum inspectability, no dependency; weak atomicity for
compare-and-set claims. (b) ACID claims, indexable, still a single file, stdlib `sqlite3`; slightly
less human-inspectable. (c)/(d) real infrastructure for load that does not exist.

**Operational risk.** (a) duplicate claims under concurrency. (b) low.
**Reversibility.** High — the task contract hides the store.

**Recommendation: (b) SQLite for task state and claims, with a human-readable filesystem projection**
so the `intake/` inspectability property is preserved without depending on directory renames for
correctness.

## D-04 — Operational event-store model · **(H)**

**Problem.** Where durable operational events live, and whether existing event infrastructure serves.

**Evidence.** `createDecisionEvent()` (`index.html:11429`) and `emitDecisionEvent()` (`:11502`) are
real and well-designed — 13 event types, 35+ fields, a 14-category reason-code registry — but the bus
is self-described as **"memory-only, append-only in-memory"**, lives in the browser, and is scoped to
trading decisions. The immutable trade ledger and `mogo_evidence` IndexedDB store are likewise
browser-resident and trading-scoped.

**Options.** (a) reuse the decision-event bus · (b) append-only JSONL + index · (c) SQLite event
table · (d) event-store product.

**Advantages/disadvantages.** (a) is not viable: no durability, wrong runtime, and it would couple
operational automation to trading evidence — a risk the charter names explicitly. (b) matches the
repository's file-first conventions, trivially auditable, greppable, easy to archive. (c) better
querying, weaker human inspectability. (d) unjustified.

**Governance risk.** (a) is the single most dangerous option in this ADR.
**Reversibility.** (b)→(c) is a migration of an append-only file; straightforward.

**Recommendation: (b) append-only JSONL in a distinct operational namespace, with a derived SQLite
index for queries.** The decision-event bus is **reference-only**: its *schema design* is adapted, its
*runtime* is not reused.

## D-05 — Persistence and recovery model · **(S)**

**Problem.** How state survives process death.

**Evidence.** No durability today; a file stranded in `processing/` currently has no recovery path
because `--resume` does not exist.

**Options.** (a) event log is the sole source of truth, state derived · (b) state table authoritative
· (c) both, with the table authoritative.

**Recommendation: (a) event log authoritative, state derived.** A transition is persisted as an event
*before* it is considered to have happened; the task table is a rebuildable read model. This makes
workflow reconstruction and crash recovery the same operation, and matches how the project already
treats evidence — the derived figure is never the authority.

## D-06 — Artifact storage · **(S)**

**Problem.** Where raw artifacts live.

**Evidence.** 8,055 tracked JSON files; `imports/*/raw` vs `normalized` already separates raw from
derived; `evidence/` is git-ignored with committed manifests — a pattern already proven across 33
artifacts and 221 packages.

**Recommendation: git-ignored content-addressed local store, with committed manifests.** Follows the
`evidence/` precedent exactly: the bytes stay out of git, the hashes go in.

## D-07 — Relational vs document model · **(S)**

**Recommendation: JSON records as the source of truth, SQLite as a derived index.** Consistent with
D-04/D-05 and with a corpus that is already JSON.

## D-08 — Source licensing and acquisition policy · **(H) — highest priority**

**Problem.** Acquisition must be impossible unless permission is established.

**Evidence.** `ingest.py` exposes a free-text `--licensing` flag; there is **no enforcement anywhere**.
Prior project testing found one prominent source's captions server-blocked (HTTP 200, 0 bytes) while
channel metadata remained retrievable — permission is source-specific and currently unrecorded.

**Options.** (a) permissive with disclosure · (b) explicit allowlist with recorded per-source basis ·
(c) legal review per source before any acquisition.

**Advantages/disadvantages.** (a) fastest, and irreversible when wrong — acquired material cannot be
un-acquired. (b) enforceable, auditable, and still allows governance to move quickly per source.
(c) safest and slowest; unnecessary for unambiguously public artifacts.

**Operational risk.** (b) adds a gate to every acquisition — by design.
**Governance risk.** (a) is unacceptable: it makes the platform's first autonomous act an
unreviewable one.
**Reversibility.** **Low.** This is the least reversible decision in MOGO-009.

**Recommendation: (b) — a closed machine-readable classification with `UNKNOWN` treated exactly as
`PROHIBITED`, an Acquisition Authorization Record required before any fetch, and no connector able to
override the gate.** The architecture carries decisions supplied by governance or legal review; it
makes no legal claim of its own.

## D-09 — Secret-management boundary · **(H)**

**Problem.** Unattended workers may need credentials; the browser model cannot apply.

**Evidence.** `docs/SECURITY.md`: the OANDA token "is never persisted anywhere, in any form" and is
absent from diagnostics, exports, alerts and logs. That model depends on a human being present.

**Options.** (a) OS keychain · (b) environment variables · (c) encrypted file · (d) no secrets in v1.

**Recommendation: (d) for the first connector, then (a)/(b) behind a `secretRef` indirection.** The
recommended first connector needs no credentials, so the vertical slice can be proven before any
secret exists. When secrets arrive: references only, connector-scoped, resolved in memory, never
logged, access audited, substitutes in tests.

## D-10 — Retention policy · **(H)**

**Evidence.** 8,055 tracked JSON files already; raw acquisition growth is unbounded; no policy exists.

**Recommendation: retain raw artifacts and manifests indefinitely; prune regenerable derived
artifacts under an explicit, audited policy.** Raw bytes are the reproducibility anchor; derived
artifacts can be rebuilt from them. Deletion is irreversible, so any pruning is an audited task, never
a background sweep.

## D-11 — Schema versioning · **(S)**

**Evidence.** 12 schemas under `docs/trader-intelligence/schema/` with no version policy;
`mogo.evidence-package.v1` survived ten releases by being additive-only.

**Recommendation: `schemaVersion` on every contract; additive-only within a major version; a breaking
change is a new type, not a new version.** Adopt the discipline that already worked.

## D-12 — Test-runner integration · **(S)**

**Evidence.** `tests/run_all.sh` globs `tests/run_*_tests.js` only; all 8 Python suites are outside
the canonical gate; `regression-baseline.json` is separately known-stale.

**Recommendation: extend the runner with clearly-labelled sections — JS, Python, platform — each
reporting its own counts, with the protected-function drift gate running last and remaining
decisive.** Not performed in Step 2.

## D-13 — Worker sandboxing · **(S)**

**Recommendation: subprocess isolation with declared resource limits and no ambient network access
in tests.** Containers only if evidence later demands them.

## D-14 — Observability platform · **(S)**

**Recommendation: structured logs plus event-derived metrics and operator views. No external
platform.** Everything needed is derivable from the event log.

## D-15 — First connector · **(H)**

**Problem.** Which source proves the platform.

**Evidence.** YouTube is the highest-value source and the most-referenced in the corpus, but prior
testing found captions server-blocked while metadata was retrievable; its licensing status is
unresolved under D-08; its content mutates and disappears.

**Options.** filesystem/operator-drop · documentation/static web · GitHub · research papers ·
YouTube. Compared across nine dimensions in the specification §26.1.

**Recommendation: filesystem / operator-drop connector first; GitHub second; YouTube only after the
platform is proven and D-08 has produced a decision for it specifically.**

The first connector's purpose is to prove the platform, not to obtain the best content. A filesystem
connector has perfect legal clarity, no credentials, no rate limits, deterministic fixtures and
reproducible bytes — so any failure in the vertical slice is unambiguously a platform defect. It also
serves a real workflow: `intake/pending/` already works this way.

---

## Decision

Adopt the architecture in
[`MOGO-009-AUTOMATION-PLATFORM-ARCHITECTURE.md`](../architecture/MOGO-009-AUTOMATION-PLATFORM-ARCHITECTURE.md):
a **modular monolith** in a new top-level `platform/`, fourteen bounded contexts in four rings,
ring-ordered dependencies, an **append-only operational event log in its own namespace**, an
**enforced licensing gate**, and **structural read-only isolation** of all scientific evidence.

**Nothing is implemented by this ADR.**

## Consequences

**Positive.** The missing layer is added without touching protected or frozen material. Ingestion is
reused rather than rebuilt. Autonomous promotion of knowledge becomes structurally impossible rather
than merely forbidden. The `--resume` drift gets a real recovery model instead of a flag. The platform
is testable without network access.

**Negative.** MOGO acquires its first dependency manifest and its first managed runtime. An internal
orchestrator means implementing lease, backoff and dead-letter semantics correctly ourselves. The
policy gate slows acquisition by design.

**Neutral.** The decision-event bus and evidence ledger remain exactly as they are, referenced but
never reused.

## Operator approvals — recorded 2026-08-07 (MOGO-009 Step 2A)

The operator explicitly approved the following. Each is now binding architecture.

| # | Approved decision | Reference |
|---|---|---|
| 1 | **Modular-monolith-first** architecture | Decision, above |
| 2 | **New top-level `platform/`** bounded context | Spec §10 |
| 3 | **Operational event history separate from scientific evidence** | D-04, Constitution §6.8 |
| 4 | **Workers never directly call workers** | Constitution §4.4 |
| 5 | **Internal minimal orchestrator** for the first implementation phase | D-02 |
| 6 | **Append-only JSONL event log with derived SQLite index** as the initial durable model | D-04 |
| 7 | **Event log authoritative; task state derived** | D-05 |
| 8 | **SQLite + filesystem projection** for initial task delivery | D-03 |
| 9 | **Git-ignored artifact storage with committed manifests and hashes** | D-06 |
| 10 | **JSON + SQLite** initial persistence | D-07 |
| 11 | **Closed machine-readable licensing classification** | D-08, Catalog §M |
| 12 | **`UNKNOWN` behaves as `PROHIBITED`** | D-08, Constitution §5.2 |
| 13 | **Acquisition Authorization Record required before acquisition** | D-08, Constitution §5.1 |
| 14 | **No connector may bypass the policy gate** | D-08, Constitution §5.5 |
| 15 | **Filesystem / operator-drop is the first connector** | D-15 |
| 16 | **GitHub is the next external connector candidate** after the platform proof | D-15 |
| 17 | **YouTube explicitly deferred** until licensing, access, transcript and mutation concerns are governed and tested | D-15 |
| 18 | **Capability Registry required** as a formal platform component | D-16 |

## D-16 — Capability Registry · **approved**

**Problem.** The orchestrator must know what capabilities exist, what each may do, and whether it is
permitted to run — without inferring any of it from code.

**Decision.** A **Capability Registry** is a required platform component. Every worker or platform
capability is described by a self-describing, auditable record: `capabilityId`, `name`, `version`,
`owner`, `description`, `acceptedCommands`, `emittedEvents`, `requiredPermissions`,
`requiredConnectors`, `requiredSecretReferences`, `resourceLimits`, `testSuite`, `healthStatus`,
`lifecycleStatus`, `enabledState`, `compatibility`, `deprecationStatus`.

**Lifecycle states:** `proposed` → `experimental` → `approved` → `production` → `deprecated` →
`disabled` → `retired`.

**Binding rules.**

- The orchestrator **may dispatch work only to an enabled capability whose declared compatibility
  admits the requested command version.**
- A capability that declares a secret, connector, or permission it does not need is a defect; a
  capability that uses one it did not declare is a violation.
- **Capability registration does not grant scientific authority.** A registered, enabled, production
  capability still cannot approve a rule, promote a hypothesis, or write scientific evidence.

**Not implemented.** Specified in Catalog §O; implementation is Step 3 work.

## Deferred — explicitly out of scope for MOGO-009

External workflow engine · external message broker · microservices · cloud deployment ·
**Knowledge Graph** · YouTube connector · automatic rule generation · automatic hypothesis promotion ·
replay execution automation · autonomous statistical conclusions.

**On the Knowledge Graph.** Noted only as a **deferred architectural extension of the Canonical Rule
Library**, not a current requirement. It is recorded here to prevent scope creep, and with one
clarification that matters: a graph capability *already exists* in Phase I
(`scripts/trader_intelligence/graph_common.py`, `build_graph.py`, `validate_graph.py`, plus 16 graph
JSON records). The deferred item is **not** that graph — it is a future canonical-knowledge graph
built on approved rules. The existing Phase I graph remains as it is and is not extended by MOGO-009.

## Decisions requiring explicit human approval — status

All resolved as of 2026-08-07: **D-01** runtime · **D-02** orchestration · **D-04** event store ·
**D-08** licensing *(least reversible)* · **D-09** secret boundary · **D-10** retention ·
**D-15** first connector · **D-16** capability registry. **Approved.**

Safe additive, adopted: D-03, D-05, D-06, D-07, D-11, D-12, D-13, D-14.

**Approval covers architecture only.** It authorizes no implementation; Step 3 requires its own
authorization.

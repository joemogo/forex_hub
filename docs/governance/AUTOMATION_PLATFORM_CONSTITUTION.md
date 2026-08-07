# Automation Platform Constitution

**Constitution Version:** 1.0 · **Status:** Approved for MOGO Phase II
**Effective milestone:** MOGO-009 · **Date:** 2026-08-07
**Binding on:** every automation component, present and future
**Related:** [ADR-012](../adr/ADR-012-automation-platform-architecture.md) · [Architecture](../architecture/MOGO-009-AUTOMATION-PLATFORM-ARCHITECTURE.md) · [Contract Catalog](../architecture/MOGO-009-CONTRACT-CATALOG.md) · [Inventory](../reports/MOGO-009-AUTOMATION-PLATFORM-ARCHITECTURE-INVENTORY.md)

---

## 1. Purpose

Automation exists to **increase the quantity and trustworthiness of evidence, and to reduce the human
effort of acquiring it — without weakening scientific discipline by even a small amount.**

Speed is not a justification for a weaker control. If automation and scientific discipline conflict,
discipline wins and the automation waits.

## 2. Scope

This constitution binds: orchestration · operational events · tasks · workflows · workers ·
connectors · source discovery · source acquisition · raw artifacts · transformations ·
deduplication · metadata extraction · evidence candidates · review queues · rule candidates ·
hypothesis candidates · replay preparation · evidence preparation · the capability registry · and
every future autonomous capability.

It binds components that do not yet exist. A capability added later inherits these rules
automatically; no component is exempt because it was written after this document.

## 3. Authority order

Highest to lowest. **No lower-level document, contract, or implementation may override a higher one.**

1. **Frozen Campaign C1 artifacts** — evidence, manifests, tags, adjudication records, archival state
2. **Scientific governance and pre-registration** — PREREG-001, PREREG-002, `STATISTICAL-GOVERNANCE.md`, `PRE_ADJUDICATION_PROTOCOL.md`
3. **Protected-function rules** — the 63 protected functions and 4 protected constants, and their drift gate
4. **This constitution**
5. **Architecture Decision Records** — ADR-012 and successors
6. **Architecture specifications** — the MOGO-009 specification and contract catalog
7. **Worker and connector contracts** — capability manifests
8. **Implementation details** — code, configuration, defaults

Where two documents at the same level conflict, the more restrictive rule applies until governance
resolves the conflict.

## 4. Foundational principles

**Binding. Each is a rule, not an aspiration.**

1. **Evidence before conclusions.**
2. **Automation is not scientific authority.** Executing a step confers no right to interpret it.
3. **Workers perform narrow, declared capabilities.**
4. **Workers never directly call other workers.** No exception, including through shared libraries,
   adapters, or subprocess invocation.
5. **Work is coordinated only through governed commands, workflows, and events.**
6. **Operational events are not scientific evidence.**
7. **Operational workflow state is not canonical knowledge.**
8. **Acquired content is not validated knowledge.**
9. **Educator statements are not proven facts.** They are claims about claims.
10. **Canonical knowledge requires governed human review.**
11. **Hypotheses may not be auto-promoted.**
12. **Pre-registration may not be bypassed, weakened, or amended by automation.**
13. **No post-outcome parameter fitting.**
14. **No live trading.** No automation component may place, modify, or cancel a real order.
15. **No automatic strategy optimization.**
16. **Frozen campaigns are immutable.**
17. **Every meaningful transformation preserves provenance.**
18. **Failures, retries, rejections, suppressions and duplicates remain visible.** Silence is a defect.
19. **Every acquisition and transformation path is idempotent.**
20. **Every governed decision is auditable** — who, what, when, why, under which policy version.
21. **Scientific evidence may be written only through authorized governed interfaces**, and no such
    interface exists for automation in Phase II.
22. **No automation component may write directly to protected scientific directories or records.**

## 5. Source acquisition rules

1. **Policy authorization precedes acquisition.** No fetch without an Acquisition Authorization Record.
2. **`UNKNOWN` behaves exactly as `PROHIBITED`.** Absence of a known permission is not permission.
3. **`PROHIBITED` content is not acquired** — not partially, not for evaluation, not "temporarily".
4. **Discovery may collect only the minimum metadata necessary for policy review** — typically title,
   publisher, locator, date. This allowance exists solely to make classification possible and expires
   the moment a classification is recorded.
5. **No connector may bypass the policy gate**, by configuration, flag, argument, or code path.
6. **Source terms and authorization decisions must be recorded**, including the deciding authority and
   the policy version in force.
7. **Policy changes trigger re-evaluation** of affected sources. A change never retroactively
   legitimises a past acquisition and never silently invalidates one.
8. **Restricted content must respect** retention, deletion, redistribution and model-training
   restrictions as recorded in its authorization.
9. **This architecture makes no legal determination.** It records and enforces classifications
   supplied by project governance or legal review.

## 6. Event and execution rules

1. Operational events are **immutable**. Never updated, never deleted.
2. Every event carries **correlation and causation identifiers**.
3. Every event carries a **schema version** and a **payload hash**.
4. Execution history is **append-only**.
5. Every task reaches a **visible terminal outcome**.
6. **No silent failures.** A path that can end without an event is a defect.
7. **Historical events are never mutated.** A mistake is corrected by a **new correction or
   supersession event** that references the original — the same discipline the pre-registrations use.
8. Operational events are **stored separately** from trading decision events and from every scientific
   ledger, with their own namespace, store and identifier space.

## 7. Worker rules

Every worker must declare: capability · authorized commands · emitted events · bounded inputs and
outputs · idempotency rules · retry rules · failure classifications · secret-access boundaries ·
resource boundaries · health reporting · tests · prohibited actions.

- A worker may not accept a command it has not declared, nor emit an event it has not declared.
- A worker may not exceed its declared secret, connector, or resource scope.
- **A worker may not approve its own governed output.**
- A worker reports state; it does not transition state. Only the orchestrator writes task state.

## 8. Connector rules

Every connector must provide: a capability manifest · source-type declarations · policy-gate
integration · rate-limit handling · checkpointing where acquisition is resumable · raw-response
preservation where permitted · source mutation and deletion detection · fixtures and test doubles ·
explicit secret references.

**No hidden acquisition behaviour.** A connector that fetches anything not declared in its manifest
and permitted by its authorization is in violation, whether or not the content is retained.

## 9. Human review rules

Review is **mandatory and blocking** for: licensing ambiguity · educator or source identity conflict ·
suspected duplicate · source mutation · incomplete or low-quality transcript · contradictory metadata
· evidence-candidate approval · canonical-rule approval · hypothesis promotion · experiment
pre-flight exception.

Every review record preserves: **reviewer identity, decision, reason, timestamp, policy version, and
supporting references.** A decision without a reason is invalid. Rejected and suppressed items remain
visible and queryable permanently.

## 10. Provenance and lineage

Every derived object preserves: source identity · parent identity · input hash · output hash ·
transformation identity · transformation version · timestamp · worker identity · workflow identity ·
policy context · review history.

**A child's input hash must equal its parent's output hash. Broken lineage is a blocking defect** —
not a warning, not a repairable inconsistency.

## 11. Idempotency, retry and recovery

- Idempotency keys are **deterministic** and derived from semantic inputs, never from timestamps or
  attempt numbers.
- Retry is **bounded** with backoff.
- Every failure carries an **error classification**.
- **Prohibited and deterministic failures are not retried** unless the underlying condition has
  demonstrably changed. Retrying a policy denial is an attempt to launder it.
- Crash recovery resumes from the last **verified** checkpoint, never from an assumed one.
- Stale claims are reclaimed on lease expiry.
- Outputs are verified by re-hashing.
- Duplicate outputs for one idempotency key are a determinism violation — dead-letter and alert; never
  pick a winner.
- Dead-letter states are **visible**, not archived away.

## 12. Security and secrets

Secrets must never appear in: source artifacts · command payloads · event payloads · logs ·
documentation · evidence candidates · repository files · test fixtures.

Required: least privilege · connector-scoped access by reference only · redaction in all output ·
rotation without code change · access auditing that records the reference and never the value.
A test requiring a real credential is a design defect.

## 13. Observability

The platform must make visible: workflow state · task state · worker health · queue depth and oldest
queued task · retries · failures by class · dead letters · policy blocks · review backlog ·
provenance completeness · hash verification results · recovery actions.

**An operator must be able to answer "what failed, when, and why" without reading code.**

## 14. Scientific boundaries

Automation may **prepare**. It may not autonomously: approve canonical rules · approve or promote
hypotheses · alter a pre-registration · execute unauthorized replay · freeze a campaign · adjudicate
results · change statistical methodology after observation · modify scientific registries · trade
live · fit strategies to outcomes.

Preparation means assembling inputs for a human or governed decision. It never means making the
decision.

## 15. Change control

Amending a constitutional rule requires: explicit architectural justification · impact analysis ·
governance review · documented approval · a version increment.

**No amendment has retroactive effect on a frozen campaign.** A rule change governs future work only —
the same principle PREREG-001 §4 applies to thresholds.

## 16. Enforcement

**A violation of this constitution is a blocking defect**, not a code-review preference.

Architecture tests and protected-boundary tests should progressively enforce these rules
mechanically. At minimum, a static test must assert that no automation component contains a write
path to a frozen scientific location. A rule that is only enforced by good intentions is the rule most
likely to be broken under time pressure — MOGO-004's silent export failure is the standing example of
what unenforced assumptions cost.

## 17. Version and status

| | |
|---|---|
| **Constitution version** | **1.0** |
| **Status** | **Approved for MOGO Phase II** |
| **Effective milestone** | MOGO-009 |
| **Date** | 2026-08-07 |
| **Supersedes** | nothing — this is the first constitution |
| **Amendment** | §15 |

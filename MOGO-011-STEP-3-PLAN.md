# MOGO-011 STEP 3 — POLICY GATE PLAN

**Milestone:** MOGO-011 Step 3 — the authorization layer
**Baseline:** `7b2c0aa940d185995305e45a209edf063050e10b` (`origin/mogo-main`, synchronized)
**Status:** **design only — nothing implemented, staged, committed, tagged or pushed**
**Date:** 2026-08-08 · **Governing document:** Automation Platform Constitution v1.0 (senior to everything below)

---

## 1. Executive finding

Step 3 sits at **Architecture §32 item 5** — *"Policy gate — classification, authorization records,
enforcement tests. **Before any connector.**"* It is the control that every future connector, worker,
scheduler, ingestion adapter and autonomous capability must pass through before work executes.

Four findings shape the work. **The first is the most serious thing found in this milestone so far.**

### F-1 (SEVERE) — the current policy path fabricates its audit trail

This was verified by running an acquisition-class capability through the committed runtime, not by
reading code. Today, a task whose capability declares `operationClass: acquisition` produces this
event sequence:

```
TaskRequested → TaskPolicyCheckRequested → PolicyEvaluated → TaskClaimed
              → TaskStarted → TaskFailed → TaskDeadLettered
```

with this `PolicyEvaluated` payload:

```json
{"decision": "not_applicable", "operationClass": null, "reason": "routed to failure"}
```

**Three statements in that record are false.**

1. `decision: "not_applicable"` — the gate did **not** find the policy inapplicable. It refused
   because no policy gate exists. The log records the opposite of what happened.
2. `operationClass: null` — the operation class was `acquisition`, and it is precisely the fact that
   mattered. It is recorded as unknown.
3. `TaskClaimed` and `TaskStarted` were emitted for **an execution that never occurred**. No worker
   claimed the task, no capability ran. Step 1 emitted these to reach `running` "legitimately"
   because `TaskFailed` is defined as `running → failed`; the effect is a log that asserts work was
   claimed and started when it was not.

The *outcome* is defensible — the task fails closed and acquires nothing. **The record of how it got
there is not.** Constitution §4.20 requires every governed decision to be auditable —
*who, what, when, why, under which policy version* — and §4.18 requires failures and rejections to
remain visible rather than disguised. An audit trail that misstates the decision is worse than a
missing one, because it will be believed.

**This is the defect Step 3 exists to fix**, and it is why the gate cannot be bolted on beside the
existing path: the existing path must be replaced.

### F-2 — three approved task states are unreachable

`blocked`, `awaiting_review` and `suppressed` are in the committed contract with legal edges and
correct authorities, and **no event in the projection lands in any of them**. Verified:

```
states reachable via projection.TRANSITIONS:
  claimed, dead_lettered, failed, policy_check, queued, requested,
  retry_scheduled, running, succeeded
blocked: unreachable   awaiting_review: unreachable   suppressed: unreachable
```

`policy_check → blocked` is exactly the edge a denial is supposed to take. It has never been used.

### F-3 (GOOD NEWS) — **no new event name is required**

Unlike Step 1 (five names) and Step 2 (one name), **Step 3 needs no vocabulary extension.** Verified
against the committed contracts:

| Needed | Status |
|---|---|
| `PolicyEvaluated`, `AcquisitionAuthorized`, `AcquisitionDenied` | ✅ approved |
| `HumanReviewRequired`, `HumanReviewCompleted`, `WorkflowSuppressed` | ✅ approved |
| Commands `EvaluateSourcePolicy`, `RecordReviewDecision`, `RequestHumanReview` | ✅ approved |
| States `blocked`, `awaiting_review`, `suppressed` | ✅ approved |
| Edges `policy_check→blocked`, `blocked→awaiting_review`, `awaiting_review→queued\|suppressed` | ✅ approved, correct authorities |
| Licensing vocabulary — 12 statuses with per-operation permissions | ✅ committed in MOGO-010, **inert; Step 3 is its first consumer** |

**There is no blocking vocabulary decision in Step 3.** `contracts/vocabulary.py` and
`contracts/task_states.py` are both untouched.

### F-4 — `policy_blocked` has two distinct meanings that must not be conflated

The approved documents use it for two different things, and merging them would lose information:

| Meaning | Where | Mechanism | Outcome |
|---|---|---|---|
| **The gate denies authorization** at `policy_check` | Catalog §L, Architecture §20.2 | a **state transition** | `policy_check → blocked` |
| **A connector attempts an operation outside its authorization** at runtime | Architecture §20.3, Catalog §F | an **error class** on a failure | `running → failed → dead_lettered`, never retried |

Today the runtime uses the second to express the first. Step 3 separates them: the gate's denial
becomes a state, and `policy_blocked` as an error class is reserved for the runtime enforcement case
— which belongs with the first connector, though its *predicate* is built now (§7.4).

---

## 2. Baseline verification

| # | Check | Result |
|---|---|---|
| 1 | HEAD | `7b2c0aa940d185995305e45a209edf063050e10b` |
| 2 | `origin/mogo-main` | identical — **ahead 0, behind 0** |
| 3 | Tracked modifications | **0** |
| 4 | Platform suite | **14 suites · 622 tests · 622 passed** |
| 5 | Canonical gate | **17 suites · 947 fixtures · 947 passed** |
| 6 | Campaign C1 | **33 verified · 0 missing · 0 mismatched · 0 unlisted** |
| 7 | Protected-function drift | **63 functions · 4 constants · drift 0** |
| 8 | Third-party dependencies | **0** |
| 9 | Protected paths | clean |

---

## 3. Authority review

Read in full for this plan: the **Constitution v1.0**, the **MOGO-009 Architecture specification**
(§5–7 contexts and dependency rules, §15b, §18.1, §20 in full, §21, §22, §23, §25, §32, §33), the
**Contract Catalog** (§A–§O in full), **ADR-012** (D-08, D-09, D-15, D-16), and every committed
contract and runtime module.

**The clauses that actually bind Step 3:**

| Source | Clause | Binding effect |
|---|---|---|
| Constitution §5.1 | **Policy authorization precedes acquisition.** No fetch without an Acquisition Authorization Record | the gate is a precondition, not a filter |
| Constitution §5.2 | **`UNKNOWN` behaves exactly as `PROHIBITED`** | asserted as data equality **and** as a decision |
| Constitution §5.3 | `PROHIBITED` is not acquired — *not partially, not for evaluation, not "temporarily"* | no partial-permission path may exist |
| Constitution §5.5 | **No connector may bypass the gate** — by configuration, flag, argument, or code path | structural, not documentary (§8) |
| Constitution §5.6 | decisions recorded **with deciding authority and policy version in force** | both are required payload fields |
| Constitution §5.7 | a policy change never retroactively legitimises a past acquisition, nor silently invalidates one | §7.6 — decisions are frozen at the moment they are made |
| Constitution §5.9 | **the platform makes no legal determination** — it records and enforces classifications supplied by governance | the authorization record is an **input**, never minted by the platform |
| Constitution §4.20 | every governed decision is auditable — who, what, when, why, under which policy version | F-1 is a violation of this today |
| Constitution §6.5 / §6.6 | every task reaches a visible terminal outcome; no silent failures | **decision C-1** |
| Constitution §9 | review records preserve reviewer identity, decision, **reason (required)**, timestamp, policy version | if a review path is built, these are mandatory |
| Constitution §14 | automation may **prepare**; it never decides | the gate enforces a human decision; it never makes one |
| Catalog §L | `policy_check → queued` (permit / not_applicable) · `policy_check → blocked` (deny / unknown / **indeterminate**) | the two edges the gate owns |
| Catalog §M | 12 statuses, per-operation permissions, Acquisition Authorization Record fields | adopted verbatim |
| Architecture §20.2 | minimum-metadata allowance **expires the instant a classification is recorded** | §7.5 — no drip-feed path may exist |
| Architecture §32 item 5 | the gate precedes **any** connector | Step 3 builds no connector |
| ADR-012 D-08 | closed machine-readable classification; authorization record required; no connector override | the shape of the whole step |

---

## 4. Implementation boundary

### In scope

1. **Classification enforcement** — the 12-status licensing vocabulary becomes live, consumed from
   the single committed table.
2. **Acquisition Authorization Records** — validation, storage, lookup, expiry, supersession.
3. **The gate itself** — a pure decision function over recorded values, plus its single integration
   point in the orchestrator.
4. **Honest, event-backed decisions** — `PolicyEvaluated` carrying the real decision, plus
   `AcquisitionAuthorized` / `AcquisitionDenied`, replacing the fabricated path of F-1.
5. **`policy_check → blocked`** and the disposition of a blocked task (decision C-1).
6. **Bypass-impossibility** — enforced structurally and tested, not asserted.
7. **Operator visibility** — policy decisions, authorizations, blocks and the gate's own state
   answerable without reading code.

### Explicitly out of scope — and each is absent because no code path expresses it

**No connector of any kind** · no network, no socket, no HTTP · no source discovery · no source or
educator registry (context 5) · no raw artifact registry (context 6) · no transformation pipeline ·
no ingestion adapter into `scripts/trader_intelligence/` · no Research Acquisition Worker · no
secrets or `secretRef` resolution (ADR-012 D-09 remains at option (d): no secrets) · no retention
policy (D-10) · no scheduler or daemon · no second process · no review *queue* or workflow system ·
no effectful capability — **risk A-5 remains closed by prohibition** · no scientific write of any
kind.

**Nothing from a later milestone is pulled forward.** The gate is built against
**operator-supplied authorization records and pure local capabilities**, exactly as Step 2 was built
against a pure local capability rather than a connector. Boundary tests prove the absences rather
than asserting them.

### The line that decides "is this the gate, or is this acquisition?"

> The gate answers **"is this permitted?"** from recorded facts.
> It never answers **"go and get it."**

Any code that would fetch, resolve a locator, open a socket, or read outside the state root is out of
scope by construction.

---

## 5. Governance decisions required — five, none blocking on vocabulary

Unlike Steps 1 and 2, **no decision here blocks on the closed event vocabulary.** All five are scope
and semantics decisions.

### C-1 — disposition of a blocked task *(the one that matters)*

`policy_check → blocked` is approved, and `blocked` is **non-terminal**. `blocked → awaiting_review`
is approved, and `awaiting_review` is **non-terminal**. The review gate does not exist. So a denied
task strands — **exactly the Constitution §6.5 defect Step 2 was built to eliminate.**

| Option | Behaviour | Assessment |
|---|---|---|
| **A** | Stop at `blocked`. | **Rejected.** Recreates the §6.5 defect. |
| **B** | `blocked → awaiting_review`, stop. | **Rejected.** Same defect, one state later. |
| **C** | Keep today's behaviour: deny → `dead_lettered` with `policy_blocked`. | Terminal and fail-closed, and it **contradicts Catalog §L**, leaves three approved states unreachable, conflates the two meanings of `policy_blocked` (F-4), and makes a denial permanently unappealable — a governance approval could never release the task. |
| **D — RECOMMENDED** | `policy_check → blocked → awaiting_review`, plus a **minimal operator disposition path**: an explicit, audited operator decision resolves `awaiting_review → queued` (approved) or `→ suppressed` (rejected, terminal). | Every task reaches a terminal outcome; the approved edges are used with their approved authorities; a denial is appealable **by a human, never by the platform**; Constitution §9's required review fields are recorded. |

**Recommendation: D.** It is the smallest addition that keeps §6.5 true, and it is not a review
*system*: no queue, no assignment, no notification, no workflow — one operator command that records
identity, decision, reason (**required — a bare approval is invalid, Constitution §9**), timestamp
and policy version, and moves the task. The review *workflow* (§22) remains deferred.

**This is a scope decision and needs explicit approval**, because it implements a slice of the review
gate that Architecture §32 lists separately from item 5.

### C-2 — an acquisition-class demonstration capability

The gate cannot be proven end to end without a task the gate actually evaluates. Proposed: **one
capability declaring `operationClass: acquisition`, `effectClass: pure`, which acquires nothing** —
it performs the same local, deterministic normalization the existing capabilities do. Its only
purpose is to be *classified* as acquisition-class so the gate engages.

Same reasoning as Step 2's `fail_then_succeed`: the parameter under test is real, the capability is
inert. The alternative — testing the gate only through unit tests of pure functions — would leave the
orchestrator integration unproven, which is where F-1 lives.

**Acknowledgment requested**, because a capability declaring itself acquisition-class could be
misread as acquisition capability. It has no fetch path, and the boundary tests continue to prove
that no module under `platform/**` can reach a network.

### C-3 — Acquisition Authorization Records are **input**, stored as a local observation

Constitution §5.9 and Architecture §20.1: the platform *records and enforces* classifications
**supplied by governance or legal review**; it makes no legal determination. So an authorization
record is an input, exactly like a capability manifest.

Proposed: store them in an `acquisition_authorizations` table populated by an explicit operator
command, **marked non-replayable** alongside `capabilities` and `runs`. There is no approved event
meaning "governance created an authorization record", and inventing one would be the platform
claiming to have made a decision it did not make.

**Replay determinism is preserved by recording the decision, not the input:** every gate decision
event carries `authorizationId`, `policyStatus`, `policyVersion`, `decisionAuthority`, the permitted
operations in force, **and a content hash of the authorization record as it stood at decision time**.
Replay re-applies the recorded decision and never re-derives it — the Step 2 rule, unchanged. A later
edit to a record therefore cannot rewrite history, which is Constitution §5.7 made mechanical.

**Acknowledgment requested.**

### C-4 — `policy_blocked` reserved for runtime enforcement, not for gate denial

Per F-4. A gate denial is a **state** (`blocked`) carrying `AcquisitionDenied`; the `policy_blocked`
**error class** is reserved for a capability or connector attempting an operation outside its
authorization during execution. Both remain never-retryable.

**Acknowledgment requested**, because it changes the observable outcome of an acquisition-class task
from `dead_lettered` to `blocked` — a deliberate behaviour change, and the correction of F-1.

### C-5 — policy re-evaluation on version change is deferred, with its trigger named

Architecture §20.3 requires a policy version change to create a **re-evaluation task** for affected
sources. Step 3 has no source registry and no acquisitions to re-evaluate, so there is nothing to
re-evaluate. Deferred, with the trigger recorded: **the first acquisition that produces a retained
artifact.** The gate records `policyVersion` on every decision precisely so re-evaluation is possible
later.

**Acknowledgment requested.**

---

## 6. Design

### 6.1 The decision, as one pure function

```python
def evaluate(operation_class, requested_operations, authorization, now_ms):
    """Pure. No clock, no connection, no I/O. The single authorization decision."""
```

No clock (`now_ms` is an argument), no connection, no filesystem — the Step 2 discipline, so the
whole gate is exhaustively unit-testable and precisely mutation-testable.

**The decision ladder, fail-closed at every rung:**

| # | Condition | Decision | Reason |
|---:|---|---|---|
| 1 | operation class is `non_acquisition` | **PERMIT** | `not_applicable` |
| 2 | operation class is not a known class | **DENY** | `operation_class_indeterminate` |
| 3 | no authorization record for the subject | **DENY** | `no_authorization_record` |
| 4 | record's status is not a known status | **DENY** | `unknown_policy_status` |
| 5 | status does not permit acquisition (`UNKNOWN`, `PROHIBITED`, `RESTRICTED`, `AUTHENTICATION_REQUIRED`, `HUMAN_REVIEW_REQUIRED`) | **DENY** | `policy_status_denies_acquisition` |
| 6 | record has expired | **DENY** | `authorization_expired` |
| 7 | record has been superseded | **DENY** | `authorization_superseded` |
| 8 | a requested operation is not in `permittedOperations` | **DENY** | `operation_not_permitted` |
| 9 | a requested operation is `DENIED` for this status | **DENY** | `operation_denied_by_status` |
| 10 | status is `AS_RECORDED` and the record does not state the operation explicitly | **DENY** | `licence_does_not_state_operation` |
| 11 | otherwise | **PERMIT** | `authorized` |

**Rung 5 is where `UNKNOWN` is `PROHIBITED`.** It is decided by `permitsAcquisition` read from the
one committed table, never by a list of status names re-typed in the gate — the Step 2 rule that
there is exactly one authoritative table, applied to licensing.

**Rung 10 is the `AS_RECORDED` trap.** `PERMITTED_EXPLICIT_LICENCE` and
`PERMITTED_DOCUMENTED_POLICY` mark every operation `AS_RECORDED`, which is *not* an allowance — it
means "whatever the licence says". Treating it as permission would turn the two most nuanced statuses
into the most permissive ones. It requires the record to name the operation explicitly, and denies
otherwise.

**Deny is the default of the function, not the fall-through of a chain of ifs.** The implementation
computes a permit only by reaching rung 11; every earlier exit and every unanticipated state denies.

### 6.2 The Acquisition Authorization Record

Catalog §M / Architecture §20.3 fields, adopted verbatim:

`authorizationId` · `sourceId` · `policyStatus` · `policyVersion` · `decisionAuthority` ·
`decidedAt` · `permittedOperations[]` · `sourceTermsSnapshotRef` · `retentionRestrictions` ·
`deletionRequirements` · `redistributionRestrictions` · `modelTrainingRestrictions` · `expiresAt` ·
`supersedesAuthorizationId` · `auditHistory[]`

Validation is fail-closed: `policyStatus` must be one of the 12; `permittedOperations` ⊆
`{discover, metadata, transcript, artifact}`; `decisionAuthority` must be a non-empty human or
governance identity — **never a worker or capability** (Constitution §14, Catalog §N); `decidedAt`
and `expiresAt` canonical UTC; a record naming a `supersedesAuthorizationId` must reference an
existing record.

**Records are append-only and immutable.** Correction is by **supersession**, never by mutation —
Constitution §6.7's discipline, the same one the pre-registrations use. Enforced by the same
append-only triggers the event index uses.

### 6.3 Orchestrator integration — one choke point

`_evaluate_policy` is **replaced**, not extended. The fabricated `TaskClaimed`/`TaskStarted` path
(F-1) is deleted.

```
policy_check
   ├─ PERMIT  → PolicyEvaluated(decision=permit|not_applicable, …)   → queued
   │            + AcquisitionAuthorized(…)   [acquisition-class only]
   └─ DENY    → PolicyEvaluated(decision=deny, reason, …)            → blocked
                + AcquisitionDenied(…)
                → HumanReviewRequired(…)                             → awaiting_review
```

`PolicyEvaluated` becomes **payload-dependent** in the projection — carrying `policy_check → queued`
or `policy_check → blocked` according to its recorded decision. `TaskReclaimed` is already
payload-dependent, so this is an established shape, not a new one.

**Every payload records `who, what, when, why, under which policy version`** — Constitution §4.20
satisfied field by field, and F-1's three false statements each replaced by the true one.

### 6.4 Impossible to bypass

Six independent mechanisms. The requirement is *impossible*, not *discouraged*, so no single one is
relied on:

1. **One entry path.** A new task enters `queued` only through `policy_check`. The other edges into
   `queued` (`retry_scheduled→queued`, reclaim, `awaiting_review→queued`) belong to tasks that have
   **already** passed the gate.
2. **One decision site.** A source-level test asserts `policy.evaluate` is called from exactly one
   place in the runtime, and that no other module imports a permit constant.
3. **The projection refuses the shortcut.** `requested → queued` is not a legal Catalog §L edge, so
   `assert_legal_transition` raises before any UPDATE. A capability cannot be dispatched into a state
   it cannot legally reach.
4. **No flag, no argument, no environment variable may permit.** A test asserts the gate takes no
   override parameter and that no environment variable is consulted anywhere in the policy path —
   Constitution §5.5 names configuration and flags explicitly.
5. **Dispatch requires a permit record.** `_claim_and_execute` verifies the task carries a recorded
   permit before claiming, so even a hand-corrupted index row cannot execute an unauthorized
   acquisition — the same defence-in-depth shape as Step 2's lease-holder verification.
6. **The absence is structural.** Boundary tests continue to prove no network, no subprocess, no
   randomness, no clock outside `clock.py`, and no write outside the state root.

### 6.5 Determinism and replay

| Property | How it is preserved |
|---|---|
| Deterministic execution | `evaluate()` is pure; identical inputs give an identical decision, asserted over 1,000 iterations |
| Replay determinism | replay **re-applies** the recorded decision and never re-derives it — a test spies on `evaluate` during `rebuild()` and asserts it is **never called** (the Step 2 pattern) |
| Append-only history | no new write path; every decision rides inside the existing `_emit` protocol |
| Policy change cannot rewrite history | the decision event carries the record's content hash as it stood at decision time (C-3), so a later edit is detectable and inert |
| Immutable evidence | no scientific path exists; protected-path tests unchanged |

### 6.6 Schema v3 — additive only

`ALTER TABLE ... ADD COLUMN` and `CREATE TABLE` only. No down-migration, for the reason established
in Step 2: the correct reversal of a derived index is delete-and-rebuild from the log.

- `tasks` gains `policy_decision`, `policy_status`, `authorization_id`, `policy_version`,
  `blocked_reason` — each **copied from an event payload**, never computed.
- new `acquisition_authorizations` — the record store, append-only, non-replayable (C-3).
- new `policy_decisions` — derived decision history, rebuildable.
- `capabilities` gains `acquisition_operations` (optional, restrictive default `[]`).

**Echo and `fail_then_succeed` manifests stay byte-identical**, so their hashes stay pinned and every
existing state root upgrades — the Step 2 rule that no Step 3 field may be *required*.

---

## 7. Fail-closed matrix

The behaviours that must hold, each with the test that will prove it:

| Situation | Required outcome |
|---|---|
| No authorization record | **DENY** |
| `UNKNOWN` status | **DENY** — identical to `PROHIBITED`, asserted as data **and** as decision |
| `PROHIBITED` / `RESTRICTED` / `AUTHENTICATION_REQUIRED` | **DENY** |
| `HUMAN_REVIEW_REQUIRED` | **DENY** — no new acquisition of any kind |
| Expired record | **DENY** |
| Superseded record | **DENY** |
| Operation outside `permittedOperations` | **DENY** |
| Operation `DENIED` for the status | **DENY** |
| `AS_RECORDED` without an explicit statement | **DENY** |
| Operation class absent, empty, misspelled or unknown | **DENY** — treated as acquisition-class |
| Authorization record malformed | **refused at registration**; never silently ignored |
| Two records for one source | most recent non-superseded wins; ambiguity → **DENY** |
| Gate raises unexpectedly | task does **not** proceed; failure is recorded |

**`UNKNOWN` gets two independent guards**, as `policy_blocked` did in Step 2: the committed table's
`permitsAcquisition: False`, and a decision-level check that still denies when the table is
monkeypatched to claim otherwise. Constitution §5.2 is the second clause the Constitution states in
absolute terms, and it earns the same belt-and-braces treatment.

---

## 8. Proposed files — ~18 (6 created, ~12 modified)

**Create:** `runtime/policy.py` (pure decision) · `runtime/authorizations.py` (record validation and
store) · `runtime/capabilities/policy_probe.py` (C-2) · `tests/platform/test_runtime_policy_gate.py`
· `tests/platform/test_runtime_authorization.py` · `tests/platform/test_runtime_review_disposition.py`
(C-1 = D)

**Modify:** `runtime/{schema,projection,orchestrator,registry,errors,audit,cli}.py` ·
`platform/README.md` · `tests/platform/test_runtime_{projection,capability,end_to_end}.py` ·
`tests/platform/test_platform_boundaries.py` · `tests/run_platform_tests.sh`

**Explicitly not modified:** **`contracts/vocabulary.py`** (no new name — F-3) ·
**`contracts/task_states.py`** (every edge already exists with the correct authority) ·
`contracts/{ids,errors,command,event,boundaries}.py` · `capabilities/echo.py` and
`capabilities/fail_then_succeed.py` (pinned by hash) · `runtime/{paths,store,event_log,clock,retry,lease,worker}.py`
· `tests/run_all.sh` (ADR-012 D-12) · all protected paths.

---

## 9. Test plan

Target **622 → ~760 tests, 14 → 17 suites**, plus the Architecture §25 "Policy gate" row satisfied
directly: *"`UNKNOWN` and `PROHIBITED` cannot acquire; no connector path bypasses the gate."*

| Area | Coverage |
|---|---|
| Decision function | all 12 statuses × 4 operations = 48 cases, plus expiry, supersession, malformed and unknown inputs |
| `UNKNOWN` ≡ `PROHIBITED` | asserted as table equality **and** as identical decisions across every operation |
| Authorization records | validation, immutability, supersession, append-only enforcement, non-worker authority |
| Gate integration | permit → `queued`; deny → `blocked` → `awaiting_review`; every payload field present and true |
| **F-1 regression** | **no `TaskClaimed` or `TaskStarted` is emitted for a task that never executed**, and `PolicyEvaluated` never records `not_applicable` for an acquisition-class task |
| Bypass | six tests, one per mechanism in §6.4 |
| Replay | `evaluate` never called during `rebuild()`; whole-row equality after rebuild with the clock advanced |
| Disposition (C-1) | approve → `queued`; reject → `suppressed`; reason required; no self-approval |
| Boundaries | no network, no connector path, exactly three capabilities all `pure`, no environment override |
| Crash recovery | boundaries 23–28 across the gate and disposition transitions, real `os._exit(70)` |

**Mutation protocol as Steps 1 and 2** — apply to committed source, purge all bytecode, run the full
suite, revert, re-verify the file hash, bounded per run. **Target ~20 mutations, 0 survivors.**
Planned targets include: make `UNKNOWN` acquirable · permit on a missing record · ignore expiry ·
ignore supersession · treat `AS_RECORDED` as permission · permit an unlisted operation · default an
indeterminate class to permit · allow dispatch without a permit record · re-derive the decision
during replay · allow an environment variable to override.

**A survivor is a genuine gap and is closed before completion is reported** — and, as Step 2 showed,
a mutation that survives must first be checked for being *mis-specified* before it is called a gap.

---

## 10. Risks

| # | Risk | Severity | Disposition |
|---|---|---|---|
| **D-1** | **F-1: the committed runtime records a false audit trail** for acquisition-class tasks | **High** | fixed by this step; it is the reason the step exists |
| **D-2** | Building a gate with no connector to gate | Medium | the gate is proven against a pure acquisition-class capability (C-2). The alternative — building the gate *with* the connector — is precisely what Architecture §32 forbids |
| **D-3** | The disposition path (C-1 = D) is a slice of the review gate | Medium | minimal by design: one audited operator command, no queue, no workflow. Governance decision C-1 |
| **D-4** | Authorization records are not replayable | Low | named honestly, like `capabilities` and `runs`; the **decision** is replayable and carries the record's hash |
| **D-5** | A record could be created naming a worker as authority | Low | refused at registration; Constitution §14 and Catalog §N |
| **D-6** | Schema v3 on the repository's first database | Medium | additive only, one transaction, rebuild is the reversal — the Step 2 precedent |
| **A-5** | **Carried unchanged** | **High** | pure capabilities only; the gate is closed by data and Step 3 opens none of it |

**Also carried:** A-3, A-4, A-6, A-7, A-8, `fsync` structural only, and every Step 2 carried item.

---

## 11. Architecture drift check

| Rule | Source | Step 3 | Verdict |
|---|---|---|---|
| Policy authorization precedes acquisition | Constitution §5.1 | the gate is the only path to `queued` | ✅ implemented |
| `UNKNOWN` ≡ `PROHIBITED` | Constitution §5.2 | two independent guards | ✅ strengthened |
| No connector may bypass the gate | Constitution §5.5 | six mechanisms, §6.4 | ✅ implemented |
| Decisions record authority and policy version | Constitution §5.6 | required payload fields | ✅ implemented |
| Platform makes no legal determination | Constitution §5.9 | records are input; the platform never mints one | ✅ preserved |
| Every governed decision auditable | Constitution §4.20 | **fixes F-1** | ✅ **fixed** |
| Every task reaches a terminal outcome | Constitution §6.5 | decision C-1 | ⚠️ **depends on C-1** |
| Automation prepares; it never decides | Constitution §14 | the gate enforces a human decision | ✅ preserved |
| Event log authoritative, state derived | ADR-012 D-05 | every new column copied from a payload | ✅ preserved |
| Gate precedes any connector | Architecture §32 item 5 | no connector exists | ✅ preserved |
| Additive-only schema evolution | ADR-012 D-11 | `ALTER TABLE ADD` and `CREATE` only | ✅ preserved |
| Zero third-party dependencies | ADR-012 D-01 | 0 | ✅ preserved |
| Closed vocabulary unchanged | Architecture §11 | **no new event or command name** | ✅ **no extension needed** |
| Frozen campaigns immutable | Constitution §4.16 | C1 untouched, verified before and after | ✅ preserved |

**Task-state machine: zero drift.** `contracts/task_states.py` is not modified. Step 3 *uses* three
approved states that have never been reachable; it adds none.

---

## 12. Verdict

**Build Step 3 as specified, after five decisions — one of which (C-1) determines whether the step
satisfies Constitution §6.5.**

The step is unusually well-supported by what is already committed: every state, edge, event name,
command name and licensing status it needs was approved in MOGO-009 and transcribed in MOGO-010, and
has been sitting inert. **No vocabulary extension is required, which is why nothing here blocks the
way B-1 blocked Step 2.**

The work that matters is not the new machinery. It is **F-1** — the committed runtime currently
writes an audit trail that says a policy decision was "not applicable" when it was refused, and says
a task was claimed and started when it never ran. The platform's whole claim to auditability rests on
its log being true. Step 3's first job is to make it true.

| | Decision | Type |
|---|---|---|
| **C-1** | Disposition of a blocked task — **recommend Option D** | **scope decision; determines §6.5 compliance** |
| **C-2** | An acquisition-class demonstration capability that acquires nothing | acknowledgment |
| **C-3** | Authorization records are input, stored as a non-replayable local observation | acknowledgment |
| **C-4** | `policy_blocked` reserved for runtime enforcement, not gate denial | acknowledgment |
| **C-5** | Policy re-evaluation deferred, trigger named | acknowledgment |

Nothing has been implemented, staged, committed, tagged or pushed. The baseline is unchanged and
verified.

**NOT READY — STEP 3 GOVERNANCE DECISIONS REQUIRED**

# MOGO-011 STEP 2 — RETRY, LEASE, AND DEAD-LETTER PLAN

**Milestone:** MOGO-011 Step 2 — dependable failure-handling execution platform
**Baseline:** `c50f95ca839fd41f75e56f93997d82928261f0b3` (`origin/mogo-main`, synchronized)
**Status:** **design only — nothing implemented, staged, committed, tagged or pushed**
**Date:** 2026-08-08 · **Governing document:** Automation Platform Constitution v1.0 (senior to everything below)

---

## 1. Executive Finding

Step 2 is **smaller than Step 1 and mostly already legal**. That is the most useful thing this analysis found.

The task-state contract committed in MOGO-010 already contains every edge Step 2 needs — `running→failed`, `failed→retry_scheduled`, `failed→dead_lettered`, `retry_scheduled→queued`, `claimed→queued`, `running→queued` — with the correct authority on each. The Catalog §K error table is already committed as inert data with `retryable`/`terminal`/`routesToReview` per class. `attemptLimit` is already an optional command field with a declared default of 3. `tasks.attempt` already exists. The guarded UPDATE proven in Step 1 is already the exactly-once primitive that attempt counting and lease acquisition need. **Step 2 is mostly wiring committed contracts to a runtime that was built to receive them.**

Four findings change the shape of the work, and one is blocking.

**F-1 (BLOCKING) — one new event name is required.** Catalog §L requires `retry_scheduled → queued`; Constitution §6.6 and Architecture §18.1 require a transition to be an event *before* it is a state; Catalog §J provides **no name** for that transition. The only other approved event that lands in `queued` is `TaskReclaimed`, which means *an abandoned lease was recovered* — overloading it would make a retry indistinguishable from an abandonment in the audit trail, which Constitution §4.18 forbids. **`TaskRetryReleased` is proposed. This is the same class of decision as MOGO-011 Step 1's F-2 and requires operator approval before implementation.**

**F-2 — two Catalog §K error classes have nowhere legal to go.** `source_mutated` and `human_review_required` are `retryable=False, terminal=False, routesToReview=True`. From `failed`, the only legal successors are `retry_scheduled`, `dead_lettered` and `cancelled` — **there is no `failed → awaiting_review` edge** (verified against the committed contract, not assumed). A task failing with either class would strand in a non-terminal state with no legal exit, violating Constitution §6.5 ("every task reaches a visible terminal outcome"). Resolution proposed in §7.4: prohibit both at registration, and dead-letter them fail-closed at runtime with a distinct reason, rather than inventing an unapproved edge.

**F-3 — Architecture §19 says "backoff with jitter"; the Step 2 design principles forbid random jitter.** Both are right for their context. Jitter exists to decorrelate *concurrent* retriers; Step 2 has one process holding an exclusive `flock` and one task in flight at a time, so there is no herd to decorrelate, and randomness would destroy the determinism this milestone is built on. Proposed: the `jitterMs` field is retained in the retry policy and governed, its Step 2 value is **0**, and `random` remains structurally unimportable across `platform/**`. Disclosed as a deviation in §38.

**F-4 — Risk A-5 resolves to Option A.** Step 2 remains limited to pure capabilities and **mechanically prohibits** effectful registration. Neither capability Step 2 needs is effectful, so choosing Option B would mean building a result store, output verification and duplicate-effect prevention with nothing real to test them against — the definition of speculative abstraction. The prohibition is enforced by a registry gate whose four preconditions are declared as data and are all `False`, plus a static AST test over `capabilities/**`. Detail in §17.

**Engineering shape:** ~7 files created, ~14 modified, ~21 total — smaller than Step 1's 28. The three genuinely new pieces of thinking are the **clock discipline** (§10), the **lease earning its keep** (§13–15), and the **A-5 gate that cannot be opened by accident** (§17–18).

**Verdict is at §40. It is NOT READY, on five named decisions.**

---

## 2. Baseline Verification

Every item required by the authorization, verified before any planning work.

| # | Check | Result |
|---|---|---|
| 1 | Repository path | `/Users/joemogollon/Desktop/Forex Hub` ✅ |
| 2 | Current branch | `main` ✅ |
| 3 | Current HEAD | `c50f95ca839fd41f75e56f93997d82928261f0b3` |
| 4 | HEAD equals the approved commit | ✅ **exact match** |
| 5 | Upstream | `origin/mogo-main` ✅ |
| 6 | Local vs remote | `origin/mogo-main` = `c50f95ca…` · **ahead 0, behind 0** ✅ |
| 7 | Tracked modifications | **0** ✅ |
| 8 | Staged | **0** ✅ |
| 9 | Untracked | **17** — 13 MOGO reports + 4 legacy documents (enumerated below) |
| 10 | Protected paths | `git status` **empty** for all 12 ✅ |
| 11 | Runtime state git-ignored | `platform/runtime/.gitignore:12:*` matches both the database and the log ✅ |
| 12 | Active MOGO runtime process | **none** — state root holds only `.gitignore`; no lock, no open handles ✅ |
| 13 | Step 1 demo verifies | `result=4a45c52f…d192dad5e` · `INTEGRITY OK` · `REBUILT … 9 events, 5 transitions` ✅ |
| 14 | Platform tests | **11 suites, 450 tests, 450 passed, 0 failures, 0 errors, 0 skipped** ✅ |
| 15 | Canonical gate | **17 suites, 947 fixtures, 947 passed, 0 failed** ✅ |
| 16 | Campaign C1 | **33 verified, 0 missing, 0 mismatched, 0 unlisted** ✅ |
| 17 | Protected-function drift | **63 functions, 4 constants, drift 0** ✅ |

**Untracked inventory (item 9).** MOGO-010: `STEP-1-PLAN`, `STEP-1-CORRECTION-PLAN`, `STEP-1-IMPLEMENTATION-REPORT`, `STEP-1-SOURCE-REVIEW`, `STEP-1-RELEASE-NOTES`, `STEP-1-COMMIT-REPORT`, `PUSH-REPORT`. MOGO-011: `ENGINEERING-NOTEBOOK`, `STEP-1-PLAN`, `STEP-1-IMPLEMENTATION-REPORT`, `STEP-1-VALIDATION-REPORT`, `STEP-1-COMMIT-REPORT`, `STEP-1-PUSH-REPORT`. Legacy (2026-08-04, disposition still open): `docs/architecture/MOGO_AGENTIC_SYSTEM_BLUEPRINT.md`, `docs/reports/MOGO-004-STEP-1-COMPLETION-REPORT.md`, `docs/reports/MOGO-004-STEP-1-PILOT-EXECUTION-BLOCKED.md`, `docs/reports/MOGO-RESEARCH-ACQUISITION-ARCHITECTURE.md`.

**Baseline matches the authorization exactly. No repair, reset, rebase, merge, amend, branch switch or configuration change was performed or is needed.**

Environment: Python 3.14.6 · SQLite 3.53.3 · `fcntl` available · zero third-party dependencies · no package manifest.

---

## 3. Step 1 Runtime Assessment

What exists, and what each piece means for Step 2.

| Module | Lines | Step 2 impact |
|---|---:|---|
| `paths.py` | 159 | **unchanged** — confinement rule already covers every new write |
| `errors.py` | 115 | +4 classes |
| `store.py` | 154 | **unchanged** — `BEGIN IMMEDIATE`, `flock`, pragmas all still correct |
| `schema.py` | 250 | v1 → v2 migration; the ordered-migration framework already exists and is used as designed |
| `event_log.py` | 336 | **unchanged** — append/fsync/scan/verify/torn-tail need nothing |
| `projection.py` | 325 | 4 new transitions, attempt increment, lease mutation, attempt rows |
| `registry.py` | 178 | effect classification, failure classes, execution context, A-5 gate |
| `worker.py` | 66 | declared failure classes, execution context |
| `orchestrator.py` | 622 | retry/dead-letter/lease integration; the largest change |
| `audit.py` | 292 | attempts, retries, leases, dead letters, failures-by-class |
| `cli.py` | 315 | `failures` subcommand, `--now`, demo scenarios |
| `capabilities/echo.py` | 95 | **unchanged, and pinned by hash** (§16.4) |

**Five Step 1 properties Step 2 must not weaken, and how each is preserved:**

1. **The write protocol** — P1 append+fsync → P2 `BEGIN IMMEDIATE` → P3 cosmetic projection. Step 2 adds no new transaction shape. Every new fact (attempt increment, lease acquisition, attempt row) rides *inside* the existing P2 transaction of the event that implies it.
2. **`_emit()` is the only append site.** Step 2 adds no second write path.
3. **The guarded UPDATE is the exactly-once primitive.** Attempt counting and lease acquisition are expressed as additional `SET` clauses on the *same* guarded statement, not as separate bookkeeping. This is what makes "increments exactly once per execution" and "replay does not increment" the same property rather than two.
4. **JSONL authoritative, SQLite derived.** Every column added in §21 is populated from an event payload, never computed at projection time. §19 proves this column by column.
5. **Only the orchestrator writes task state.** The worker still receives no connection and no log reference.

**Three Step 1 behaviours Step 2 must change, and why each is a defect rather than a design:**

- `_fail_task()` stops at `failed` and emits `WorkflowFailed`. `failed` is non-terminal. Step 1 was explicit that retry and dead-letter were out of scope, but the result is a task that never reaches a terminal outcome — Constitution §6.5. Step 2 closes it.
- `recover()` reclaims **every** task in `claimed`/`running` unconditionally, on the assumption that single-writer implies the previous holder is gone. The assumption is true, but Constitution §11 requires recovery to resume from a **verified** checkpoint, "never from an assumed one". Step 2 replaces the assumption with a verified predicate (§15).
- `run_once()` selects only `("requested","policy_check","queued")`. Step 2 must add `failed` and *eligible* `retry_scheduled`, and must not add ineligible `retry_scheduled` — otherwise the `while True` loop would spin. §11.4.

---

## 4. Authority and Architecture Review

Read in full: the Constitution, the MOGO-009 Architecture specification, the Contract Catalog, ADR-012, `platform/README.md`, all 7 contract modules, all 13 runtime modules, all 11 test suites, and the five MOGO-011 Step 1 reports plus the engineering notebook. The four legacy untracked documents were **not** used as authority.

**The clauses that actually constrain Step 2:**

| Source | Clause | Binding effect on Step 2 |
|---|---|---|
| Constitution §4.18 | failures, retries, rejections, suppressions, duplicates remain visible; silence is a defect | every retry, release, exhaustion and reclaim is an event and appears in `audit` |
| Constitution §6.5 | every task reaches a **visible terminal outcome** | `failed` must always resolve to `retry_scheduled` or `dead_lettered`; F-2 exists because of this |
| Constitution §6.6 | no silent failures; a path that can end without an event is a defect | `TaskRetryReleased` is required (F-1) |
| Constitution §11 | keys deterministic, **never from timestamps or attempt numbers** | `attempt` may enter the *execution input*; it may never enter the idempotency key. §8.5 |
| Constitution §11 | **retry is bounded with backoff** | `attemptLimit` enforced; runtime ceiling §8.4 |
| Constitution §11 | **prohibited and deterministic failures are not retried**; retrying a policy denial is laundering | `policy_blocked` guarded twice, independently. §7.3 |
| Constitution §11 | crash recovery resumes from the last **verified** checkpoint, never an assumed one | the lease turns Step 1's assumption into a verified predicate. §15 |
| Constitution §11 | **stale claims are reclaimed on lease expiry** | §14–15 |
| Constitution §11 | dead-letter states are **visible, not archived away** | `status`, `audit`, and a dedicated `failures` view |
| Constitution §13 | operator answers "what failed, when, and why" **without reading code** | `failures` subcommand; §26 |
| Catalog §C | task carries `retryPolicy`, `timeoutPolicy`, `attempt`, `leaseHolder`, `leaseExpiresAt` | field names adopted verbatim; §21 |
| Catalog §K | the 12 error classes and their retryability | the **only** retryability table; never re-declared |
| Catalog §L | the transition table and its authorities | every Step 2 transition already exists there |
| Catalog §O | dispatch requires registered + enabled + lifecycle + command + version | unchanged; extended with the A-5 gate |
| Architecture §18.1 | claims are compare-and-set on `(taskId, leaseGeneration)` | `lease_generation` adopted by name |
| Architecture §24 | **only the lease holder may write results** | implemented as a pre-write verification, not a comment. §14.5 |
| Architecture §32 | policy gate (item 5) precedes **any** connector | unchanged; Step 2 builds items 3 and 9 only |
| ADR-012 D-05 | event log authoritative, task state derived | §19 proves every new column is rebuildable |

**Step 2 sits exactly at Architecture §32 items 3 and 9** — "task state machine: persisted transitions, leases, backoff, dead-letter" and "recovery and retry: checkpoints, resumption, stale-claim reclaim". It reaches no item 5 or later. No connector, no policy gate, no acquisition.

---

## 5. Proposed Step 2 Vertical Slice

One command, one task, three attempts, one retry released under a verified backoff, one success — and separately, one task that exhausts its attempts and dead-letters with a complete history.

```
submit  ──▶ CommandAccepted ──▶ TaskRequested ──▶ TaskPolicyCheckRequested
                                                        │
                                              PolicyEvaluated(not_applicable)
                                                        ▼
                                                     queued
                                                        │  TaskClaimed  ── lease acquired (gen 1)
                                                        ▼
                                                    claimed
                                                        │  TaskStarted  ── attempt 0 → 1
                                                        ▼
                                                    running ── capability raises transient
                                                        │  TaskFailed(transient)
                                                        ▼
                                                     failed
                                                        │  retryable ∧ attempt(1) < limit(3)
                                                        │  TaskRetryScheduled(eligibleAt = now + backoff(1))
                                                        ▼
                                                 retry_scheduled
                                                        │  now ≥ eligibleAt   ← VERIFIED, never skipped
                                                        │  TaskRetryReleased            ★ NEW NAME
                                                        ▼
                                                     queued
                                                        │  TaskClaimed ── lease gen 2
                                                        ▼  TaskStarted ── attempt 1 → 2
                                                    running ── capability succeeds
                                                        │  TaskSucceeded(resultHash)
                                                        ▼
                                                   succeeded ── terminal

second task, failUntilAttempt ≥ attemptLimit:
   … attempt 3 fails ──▶ failed ──▶ attempt(3) ≥ limit(3) ──▶ TaskDeadLettered
                                                             (reason=attempts_exhausted,
                                                              attemptHistory=[3 entries])
                                                        ▼
                                                 dead_lettered ── terminal
```

**Boundaries of the slice.** No connector, no acquisition, no filesystem ingestion, no network of any kind, no browser, no model call, no scientific write, no replay, no trading, no daemon, no second process, no distributed worker, no external scheduler, no secret storage, no policy-gate bypass, no effectful capability. Each is absent because no code path expresses it, and the boundary tests prove absence rather than asserting it.

**The fifteen Primary Outcomes map to the slice as follows** (test names in §30):

| # | Outcome | Where |
|---|---|---|
| 1 | valid command creates a task | unchanged Step 1 path |
| 2 | capability fails with a retryable operational error | `fail_then_succeed`, declared class `transient` |
| 3 | orchestrator records the failure | `TaskFailed` + `task_attempts` row |
| 4 | retry policy evaluated deterministically | `retry.classify_failure()` — pure, no clock |
| 5 | `running → failed → retry_scheduled → queued` | four events, in that order |
| 6 | backoff eligibility enforced, no silent skipping | `TaskRetryReleased` payload records `eligibleAt` and the observed `now`; a test re-derives the check from the log alone |
| 7 | claimed again under a real lease | `lease_generation` 1 → 2, new holder/expiry recorded |
| 8 | succeeds on a later approved attempt | attempt 2 |
| 9 | events ordered and auditable | contiguous `sequence` per workflow; `audit` timeline |
| 10 | restart during retry or lease recovery duplicates nothing | crash matrix §24, boundaries 12–21 |
| 11 | a task exhausts its attempt limit | second task |
| 12 | moves to `dead_lettered` with a complete audit trail | `TaskDeadLettered.attemptHistory` |
| 13 | re-running the same semantic command creates no duplicate | unchanged — idempotency key excludes attempt and time |
| 14 | SQLite rebuildable from the log | `reset --rebuild-index` after the full scenario |
| 15 | Campaign C1 and protected behaviour unchanged | §32 |

---

## 6. Event Vocabulary Analysis

### 6.1 Existing names cover almost everything (Q1)

| Concept | Approved event | Catalog source | New? |
|---|---|---|---|
| failure | **`TaskFailed`** | §J, §L `running→failed` | no |
| retry scheduling | **`TaskRetryScheduled`** | §J, §L `failed→retry_scheduled` | no |
| **retry readiness / release** | **— none exists —** | §L `retry_scheduled→queued` has no §J name | **YES — F-1** |
| dead-lettering | **`TaskDeadLettered`** | §J, §L `failed→dead_lettered` | no |
| lease expiry | **`TaskReclaimed`** | §J, §L `claimed`/`running`→`queued`, and §18.1 names it for exactly this | no |
| task reclaim | **`TaskReclaimed`** | same event; the reason is a payload field | no |
| final success | **`TaskSucceeded`** | §J, §L `running→succeeded` | no |
| claim (with lease) | **`TaskClaimed`** | §J, §L `queued→claimed` | no |
| execution start | **`TaskStarted`** | MOGO-011 F-2 addition | no |

**Lease expiry does not get its own event.** The expiry is not itself a transition — the *reclaim* is. Emitting a separate `LeaseExpired` would add a name for a fact already fully carried by `TaskReclaimed`'s payload (`reason`, `previousLeaseHolder`, `previousLeaseGeneration`, `leaseExpiresAt`, `observedAt`). Adding names that carry no transition is how a closed vocabulary stops being closed.

### 6.2 The one required new name (Q2) — **BLOCKING DECISION B-1**

```
TaskRetryReleased
```

**Why the existing set is insufficient.** Three facts hold simultaneously:

1. Catalog §L declares the edge `retry_scheduled → queued`, authority *orchestrator*, condition *backoff elapsed*. It is an approved transition.
2. Constitution §6.6 and Architecture §18.1 require every transition to be **persisted as an event before the state is considered changed**. ADR-012 D-05 makes task state derived from the log; a transition with no event is a state change the log cannot reproduce, which breaks rebuild.
3. Catalog §J contains no name for it. §J is explicitly "not finalized — names and payloads are Step 3 work", which is the provision MOGO-011 Step 1's F-2 already used, under approval, to add five names.

**Why not reuse `TaskReclaimed`.** It is the only other approved event landing in `queued`. Its meaning is *an abandoned claim was recovered*. Using it for a retry release would make two distinct operational facts — "this task was abandoned and rescued" and "this task failed, waited out its backoff, and is being retried" — indistinguishable in the log. Constitution §4.18 requires retries to remain **visible**; collapsing them into reclaims makes retry rate unmeasurable and Architecture §23's "retry counts" signal underivable. Rejected.

**Why not a `RetryTask` command instead.** Catalog §J lists a `RetryTask` *command*. Using it would mean the orchestrator issues commands to itself, creating a second command lifecycle (accept, idempotency key, task linkage) for a transition Catalog §L already assigns to the orchestrator directly. It adds a subsystem and changes no outcome. Rejected; recorded in §15 of the design questions.

**Why not model eligibility with no event at all** (derive `queued`-ness from `now ≥ eligibleAt`). Then task state would be a function of the wall clock rather than of the log, `rebuild()` would produce different states at different times, and ADR-012 D-05 would be broken. This is the strongest argument for the name. Rejected.

**Name choice.** `TaskRetryReleased` follows the §J past-participle convention (`Requested`, `Claimed`, `Reclaimed`, `Scheduled`, `Succeeded`, `Failed`, `DeadLettered`). `TaskRequeued` was considered and rejected as ambiguous with `TaskReclaimed`, which also results in `queued`. `TaskRetryReady`/`TaskRetryDue` were rejected as non-participles that break the convention.

**Additive only.** Nothing is renamed, removed or repurposed (Architecture §11). `EVENT_TYPES` goes 39 → 40. Payload and authority in §22.3.

### 6.3 Nothing else is proposed

No new command type. No new licensing status. No new capability lifecycle state. No new task state — all 13 remain, and `dead_lettered` was already terminal.

---

## 7. Error and Retryability Model

### 7.1 The single authoritative table (Q3, Q4, Q5)

`contracts.errors.ERROR_CLASSES` — committed in MOGO-010, transcribed from Catalog §K, inert until now. **Step 2 is its first consumer, and Step 2 does not copy it.** `retry.is_retryable(cls)` reads `ERROR_CLASSES[cls]["retryable"]` and nothing else. There is no second list of retryable classes anywhere in the runtime, and a test asserts that the string `"transient"` appears in no retry decision as a literal.

| Class | `retryable` | `terminal` | `routesToReview` | Step 2 disposition |
|---|:---:|:---:|:---:|---|
| `transient` | ✅ | ❌ | ❌ | **retry** if attempts remain |
| `rate_limited` | ✅ | ❌ | ❌ | **retry** if attempts remain |
| `dependency_unavailable` | ✅ | ❌ | ❌ | **retry** if attempts remain |
| `authentication` | ❌ | ✅ | ✅ | dead-letter, `non_retryable_error_class` |
| `policy_blocked` | ❌ | ✅ | ✅ | dead-letter, `policy_denial_never_retried` — **guarded twice** |
| `not_found` | ❌ | ✅ | ❌ | dead-letter, `non_retryable_error_class` |
| `validation` | ❌ | ✅ | ❌ | dead-letter, `non_retryable_error_class` |
| `deterministic_processing` | ❌ | ✅ | ✅ | dead-letter, `non_retryable_error_class` |
| `corrupted_input` | ❌ | ✅ | ✅ | dead-letter, `non_retryable_error_class` |
| `permanent` | ❌ | ✅ | ❌ | dead-letter, `non_retryable_error_class` |
| `source_mutated` | ❌ | ❌ | ✅ | **F-2** — dead-letter, `requires_review_no_gate`; prohibited at registration |
| `human_review_required` | ❌ | ❌ | ✅ | **F-2** — dead-letter, `requires_review_no_gate`; prohibited at registration |
| *anything else* | — | — | — | **fail closed** — dead-letter, `unknown_error_class`; never retried |

### 7.2 Derivation, exactly (Q5)

```python
def classify_failure(error_class, attempt, attempt_limit):
    """Pure. No clock, no connection, no I/O. The single retry decision."""
    if error_class in NEVER_RETRYABLE:                  # ("policy_blocked",)
        return Decision(RETRY_NO, "policy_denial_never_retried")
    record = ERROR_CLASSES.get(error_class)
    if record is None:                                  # fail closed
        return Decision(RETRY_NO, "unknown_error_class")
    if record["routesToReview"] and not record["terminal"]:
        return Decision(RETRY_NO, "requires_review_no_gate")   # F-2
    if not record["retryable"]:
        return Decision(RETRY_NO, "non_retryable_error_class")
    if attempt >= attempt_limit:
        return Decision(RETRY_NO, "attempts_exhausted")
    return Decision(RETRY_YES, "retryable_within_attempt_limit")
```

Order matters and is asserted by test: the `policy_blocked` guard is **first and independent of the table**, so a mutation that flips `ERROR_CLASSES["policy_blocked"]["retryable"]` to `True` is still caught — two independent tests fail, one on the table and one on the decision.

### 7.3 `policy_blocked` — two independent guards

Constitution §11 singles this class out: *"Retrying a policy denial is an attempt to launder it."* Belt-and-braces is justified for exactly one class:

- **Guard 1 (data):** `ERROR_CLASSES["policy_blocked"]["retryable"] is False`, asserted directly by `test_policy_blocked_is_not_retryable_in_the_contract_table`.
- **Guard 2 (decision):** `NEVER_RETRYABLE = ("policy_blocked",)` checked before the table is consulted, asserted by `test_policy_denial_is_refused_even_if_the_table_says_retryable` — which monkeypatches the table to claim retryable and proves the decision still refuses.

Mutation 1 ("mark policy denial retryable") is detected by whichever guard it attacks; attacking both is two mutations, and both are tested.

### 7.4 F-2 — the two review-routing classes — **DECISION B-3**

`source_mutated` and `human_review_required` are non-retryable and non-terminal. Verified against the committed contract:

```
legal_successors("failed") == ('cancelled', 'dead_lettered', 'retry_scheduled')
```

There is **no `failed → awaiting_review` edge**. A task failing with either class cannot legally retry, cannot legally reach review, and would sit in `failed` forever — violating Constitution §6.5.

Three options were considered:

| Option | Verdict |
|---|---|
| Add a `failed → awaiting_review` edge | **Rejected.** It changes Catalog §L, and `awaiting_review → queued` requires *review_gate* authority, which does not exist — the task would strand one state later. |
| Leave the task in `failed` | **Rejected.** Violates §6.5 directly. |
| **Dead-letter with a distinct reason, and prohibit at registration** | **Proposed.** |

Proposed, both halves:

- **Registration-time (primary):** a capability manifest whose `failureClasses[]` contains `source_mutated` or `human_review_required` is **refused** by `registry.register()`, naming the missing review gate. A capability cannot declare a failure the runtime cannot resolve.
- **Runtime (defence in depth):** if such a class arrives anyway (it can only arrive undeclared, which is already a violation), the task dead-letters with `deadLetterReason = "requires_review_no_gate"`, and the dead-letter event records that a review gate would have been the correct destination. Visible, terminal, honest, and reversible by a future step that adds the gate.

This needs operator acknowledgment because it decides the handling of two Catalog §K classes.

### 7.5 Where an error class comes from

A capability declares its failure classes in its manifest (`failureClasses[]`) and raises `CapabilityFailure(error_class=…)`. `worker.execute_task()` accepts the class **only if** it is in `ERROR_CLASS_NAMES` *and* declared in the manifest. Otherwise the failure is recorded as `deterministic_processing` (non-retryable) and a `capability_violations` row is written. Constitution §7: *"A worker may not … emit an event it has not declared."* The same discipline, applied to failure classes, and Catalog §E's `failureReporting` requires exactly this mapping.

Echo declares no failure classes and raises none — its behaviour is unchanged.

---

## 8. Attempt Semantics

### 8.1 Exact meaning (Q6)

| Value | Meaning |
|---|---|
| `attempt = 0` | **never executed.** Set at task creation. |
| `attempt = 1` | the **first** execution has begun. |
| `attempt = n` | the *n*-th execution has begun. |

`attempt` counts **executions started**, not executions completed, and not retries. It is incremented on the `claimed → running` transition — that is, when `TaskStarted` is applied. An attempt that crashes mid-execution has still been attempted; counting only completions would let an infinitely-crashing task retry forever, which Constitution §11's "retry is bounded" forbids.

### 8.2 `attemptLimit` counts **total attempts**, not retries (Q6)

`attemptLimit = 3` permits **3 executions**, i.e. the first attempt plus at most 2 retries. This is the reading Catalog §L uses — `failed → retry_scheduled` when *"retryable ∧ attempt < limit"* — and Catalog §A's default of 3 is a total, not an addend. Stated here because "3 retries" and "3 attempts" differ by one and the difference is a silent off-by-one in every implementation that leaves it implicit.

| attempt after failure | limit | Decision |
|---:|---:|---|
| 1 | 3 | retry (attempt 2 will run) |
| 2 | 3 | retry (attempt 3 will run) |
| 3 | 3 | **exhausted** → `dead_lettered` |
| 1 | 1 | **exhausted** → `dead_lettered` (no retry at all) |

### 8.3 Exactly-once increment — the mechanism, not a convention

The increment rides inside the guarded UPDATE that performs the transition:

```sql
UPDATE tasks
   SET state = 'running',
       attempt = attempt + 1,
       last_log_sequence = :seq
 WHERE task_id = :id
   AND state = 'claimed'
   AND last_log_sequence < :seq
```

- Applied once → `rowcount == 1` → attempt incremented once.
- Replayed → `last_log_sequence >= :seq` → `rowcount == 0` → **not incremented**.
- Late/illegal → `state != 'claimed'` → `rowcount == 0` → **not incremented**, anomaly recorded.

"Increments exactly once per execution" and "replay does not increment" are therefore **the same property of one statement**, not two behaviours a caller must remember to coordinate. Mutations 3 and 4 (fail to increment / increment twice) are both detected, and a double increment cannot be hidden anywhere else because no other statement in the runtime touches `tasks.attempt`. A test asserts that: `test_attempt_is_written_by_exactly_one_sql_statement_in_the_runtime`.

### 8.4 Default and ceiling (Q7) — **DECISION B-5**

- **Default:** `contracts.command.COMMAND_DEFAULTS["attemptLimit"]` = **3**, read from the committed contract, never re-declared in the runtime.
- **Floor:** 1, already enforced by `validate_command` (`minimum=1`).
- **Ceiling:** `MAX_ATTEMPT_LIMIT = 10`, enforced at submit time. A command declaring more is **rejected** (`CommandRejected`, reason recorded in `command_submissions`).

Rationale for the ceiling: Constitution §11 requires retry to be *bounded*. Catalog §A sets no upper bound, so an `attemptLimit` of 10⁶ would be contract-valid and unbounded in practice. A runtime ceiling does not contradict the Catalog (which is silent), is auditable (the rejection is recorded), and is a single named constant an operator can find. Flagged as a minor decision because it introduces a rejection path Catalog §A does not require.

### 8.5 `attempt` and the idempotency key — the line that must not blur

Constitution §11: keys are *"deterministic and derived from semantic inputs, never from timestamps or attempt numbers."*

- The **idempotency key** is computed from the semantic command payload alone, exactly as in Step 1. It does not change across attempts. That is why outcome 13 holds: re-submitting the same semantic command after three failed attempts still creates no second task.
- The **execution input** handed to a capability may include `attempt`, as a field of an *execution context* that is deliberately **not** part of the payload and **not** part of the key.

A test asserts both directions: `test_idempotency_key_is_identical_across_every_attempt` and `test_the_execution_context_is_not_part_of_the_idempotency_key`. `ids.idempotency_key()` already rejects undeclared parts, so an attempt number cannot be smuggled into a key even by mistake.

### 8.6 Preventing retry from duplicating completed work (Q33)

Three independent mechanisms, none of which relies on the others:

1. **Terminal absorption.** `succeeded` and `dead_lettered` are terminal; `apply_transition` records any later arrival as an anomaly and does not apply it (Step 1 behaviour, unchanged).
2. **The guarded UPDATE.** A retry can only leave `retry_scheduled`, and only once — a second `TaskRetryReleased` for the same task finds `state != 'retry_scheduled'` and records an anomaly. Mutation 17 ("allow replay to duplicate retry events") is caught here.
3. **Lease-holder verification before recording a result** (§14.5). Even if a stale execution were somehow to finish, it cannot record an outcome unless it still holds the lease generation it claimed with.

---

## 9. Deterministic Backoff Design

### 9.1 The formula (Q10)

```
backoff_ms(attempt) = min(backoffBaseMs * (backoffMultiplier ** (attempt - 1)), backoffCapMs)
                      + jitterMs
```

where `attempt` is the attempt that **just failed** (1-based), and all four parameters are integers.

**Defaults** (capability-declared, §16.3):

| Parameter | Default | Source |
|---|---:|---|
| `backoffBaseMs` | 1000 | capability manifest `retryPolicy` |
| `backoffMultiplier` | 2 | capability manifest `retryPolicy` |
| `backoffCapMs` | 60000 | capability manifest `retryPolicy` |
| `jitterMs` | **0** | governed; see §9.3 |

Resulting schedule with the defaults:

| failed attempt | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---:|---:|---:|---:|---:|---:|---:|
| `backoff_ms` | 1000 | 2000 | 4000 | 8000 | 16000 | 32000 | 60000 |

### 9.2 No floating point, anywhere

Every operand is an `int`; `**` on ints is exact; `min` on ints is exact. **There is no floating-point arithmetic in the backoff computation**, so the result is bit-identical on every platform and every Python build, with no rounding mode to reason about. A test asserts `isinstance(backoff_ms(a), int)` for every attempt in range and compares against a hard-coded expected table transcribed independently of the implementation.

`backoffMultiplier` is required to be an **integer ≥ 1**; a float multiplier is refused at registration (`RetryPolicyError`). A multiplier of 1 gives constant backoff, which is legitimate; a multiplier of 0 would give zero delay after the first retry and is refused.

### 9.3 Jitter — **DECISION B-2, disclosed deviation**

Architecture §18.1, §19 and §26 all say "exponential backoff **with jitter**". The Step 2 design principles say "avoid arbitrary jitter" and "avoid random backoff". Both are correct in their own frame, and the conflict is real rather than apparent.

**What jitter is for:** decorrelating many retriers that failed at the same instant, so they do not all return simultaneously (thundering herd). It is a *concurrency* remedy.

**Why Step 2 has no herd:** one process, holding an exclusive `flock` for the whole run, executing one task at a time, one-shot. There is nothing to decorrelate. Adding randomness would buy nothing and cost the determinism that every recovery, replay and mutation test in this milestone depends on.

**Proposed:** `jitterMs = 0` for Step 2. The field is **retained** in the retry policy (so Catalog §C's `retryPolicy` shape is unchanged and nothing is removed), it is **governed** (declared per capability, validated, recorded in the `TaskRetryScheduled` payload so an auditor sees the value that was in force), and randomness remains **structurally unavailable**: `random` and `secrets` are added to `BANNED_RUNTIME_IMPORTS`, so no module under `platform/**` can import them. Mutation 7 ("add random jitter") therefore fails twice — the boundary test refuses the import, and the determinism test refuses the varying value.

**When jitter becomes necessary** — a daemon, a second worker, or any concurrent claimer — the approved extension is *deterministic* jitter derived from the task identifier, e.g. `jitterMs = int(sha256(taskId)[:8], 16) % jitterSpanMs`, which decorrelates without randomness and remains replayable. Recorded here so the future step does not reach for `random`.

### 9.4 What the log records

`TaskRetryScheduled.payload` records `backoffMs` **and** all four policy parameters in force. A retry schedule is therefore verifiable from the log alone, without knowing which build produced it — which is what makes "retry scheduling is reconstructable from the log" (a required test) actually checkable.

---

## 10. Time and Clock Design

### 10.1 Does Step 2 require wall-clock time? (Q11)

**Yes, and the honest answer matters.** Two Step 2 facts are inherently temporal:

- *backoff elapsed* — Catalog §L's condition on `retry_scheduled → queued`
- *lease expired* — Constitution §11's condition for reclaiming a stale claim

Both could be faked with a logical counter, and the result would be a system that satisfies the tests and does nothing useful in production: a lease measured in log records does not expire when a machine is switched off, and a backoff measured in log records elapses instantly when the queue is busy and never when it is idle. **Step 2 uses real UTC time, and makes it deterministic by injection rather than by avoidance.**

### 10.2 Can Step 2 use a logical scheduler tick instead? (Q13)

**No, and it does not need to.** The reason "no sleeping in tests" and "real time" can both hold is that **the runtime never waits**. `run` is one-shot: it releases the retries that are eligible *now* and returns. Nothing sleeps, polls, or blocks. A test that wants to observe a release advances an injected clock and calls `run` again — instant, deterministic, and exercising exactly the production code path.

A logical tick is therefore unnecessary, and it is also *wrong*, because it would replace the property being tested with a different one.

### 10.3 Where the clock is read (Q12)

**In exactly one module — `runtime/clock.py` — and in exactly one place per operation.**

```python
class Clock:                       # protocol
    def now_iso(self) -> str: ...  # ISO-8601 UTC, millisecond precision
    def now_ms(self) -> int: ...   # epoch milliseconds

class SystemClock(Clock): ...      # datetime.now(timezone.utc), the only real read
class ManualClock(Clock):          # tests and --now; advances only when told
    def advance_ms(self, delta: int) -> None: ...
    def set_to(self, iso: str) -> None: ...
```

- The orchestrator holds **one** clock instance for its whole lifetime and passes it down. Step 1's `clock=utc_now` constructor parameter already exists; Step 2 replaces the bare callable with the `Clock` object and keeps injection.
- `retry.py` and `lease.py` **never read a clock.** They take `now_ms` as an argument. Every decision function is pure. This is what makes them unit-testable without a database, a log or a process.
- A boundary test asserts that `datetime.now`, `time.time` and `time.monotonic` appear **only** in `clock.py` across all of `platform/**`.

### 10.4 Which timestamps are authoritative (Q12)

| Timestamp | Authority | Recorded where | Recomputed on replay? |
|---|---|---|---|
| `occurredAt` / `recordedAt` | the emitting run's clock | event envelope | **never** |
| `eligibleAtUtc` | computed once, at scheduling | `TaskRetryScheduled.payload` | **never** — copied |
| `leaseAcquiredAt` / `leaseExpiresAt` | computed once, at claim | `TaskClaimed.payload` | **never** — copied |
| `observedAtUtc` | the releasing run's clock | `TaskRetryReleased.payload` | **never** |

**This is the property that keeps replay deterministic.** No time value is ever *derived* during projection; every one is *copied* from a payload that was written once. `rebuild()` at any later date reproduces byte-identical rows. A test proves it: rebuild the index a second time with the clock advanced by a year and assert every task row is identical.

The clock is consulted only when producing a **new** event — never when applying an old one. That is the whole rule, and it is stated in one sentence in the module docstring for the same reason.

### 10.5 Clock rollback and skew (Q12, Q29)

**Fail closed, with zero tolerance, and no fudge window.**

The runtime maintains a **monotonic floor**: the highest `recordedAt` in the log. Before appending any event, `_emit` checks `now >= floor`. If the injected or system clock returns an earlier value, the runtime raises `ClockRollbackError`, appends nothing, records the refusal in `recovery_actions`, and exits non-zero.

- The comparison is `>=`, not `>`. Nine events inside one millisecond is normal (the Step 1 demo does it) and must remain legal.
- **No skew tolerance is granted.** A tolerance window is an unaudited lie about when something happened, and Constitution §4.20 requires every governed decision to record *when*. Clamping forward (`max(now, floor)`) was considered and rejected for the same reason: it would write a timestamp the clock never produced.
- The remedy is to fix the clock. Step 2 provides no override, because an override that forges timestamps is worse than a refusal.

Consequences elsewhere, stated so they are not surprises:

- A backward clock cannot make an expired lease look live, because the lease comparison also fails closed: `is_expired(expires_at, now)` is evaluated only after the monotonic guard has passed.
- A **forward** jump is not an error — it can only make a backoff or a lease expire earlier than intended. It is recorded (`TaskRetryReleased.waitedMs` will exceed the scheduled `backoffMs`), and `verify` reports any release whose `waitedMs` is more than 10× the scheduled backoff as an `INFO` finding, so a large jump is visible without being fatal.

### 10.6 Timezone ambiguity (Q12)

Eliminated structurally, not by convention:

- The only format produced is `ids.require_iso8601_utc_ms`'s: `YYYY-MM-DDTHH:MM:SS.mmmZ`, with a literal `Z`. The regex is committed in MOGO-010 and admits no offset, no naive value, and no sub-millisecond precision.
- `SystemClock` reads `datetime.now(timezone.utc)` — aware, UTC, by construction.
- `clock.parse_iso8601_ms()` refuses any string the committed regex refuses, so a timestamp that entered the log from any source is either UTC-with-`Z` or rejected.
- There is no local-time path anywhere in `platform/**`, and a boundary test asserts `datetime.now()` is never called without a `tz` argument.

---

## 11. Retry Scheduling and Eligibility

### 11.1 Representation (Q15)

Asked as a choice of four; the correct answer assigns each a role with exactly one authority.

| Form | Role | Authority? |
|---|---|---|
| **Event** — `TaskRetryScheduled.payload.eligibleAtUtc` | **the fact** | ✅ **yes, sole** |
| **Projection field** — `tasks.retry_eligible_at` | queryable copy, for indexing and `status` | no — copied verbatim, never computed |
| **Derived time** — `now >= eligible_at` | the eligibility *test*, evaluated only when producing a new event | no — stateless predicate |
| **Scheduler command** — `RetryTask` | **not used** | rejected, §6.2 |

### 11.2 What makes a scheduled retry eligible (Q14)

Eligibility is the condition; **`TaskRetryReleased` is the event**, and the state does not change until it is durable.

```python
def is_eligible(eligible_at_ms, now_ms):
    return now_ms >= eligible_at_ms          # pure; ">=", so a 0 ms backoff releases at once
```

The orchestrator selects candidates with

```sql
SELECT * FROM tasks
 WHERE state = 'retry_scheduled' AND terminal = 0 AND retry_eligible_at <= :now_iso
 ORDER BY retry_eligible_at, created_log_sequence
```

ISO-8601 UTC with fixed width and millisecond precision sorts and compares **lexicographically in the same order as chronologically**, so the SQL comparison and the Python comparison cannot disagree. A test asserts the two agree across a table of boundary values (equal, one millisecond either side, year rollover).

### 11.3 The release is auditable without trusting the runtime

`TaskRetryReleased.payload` records `scheduledEligibleAtUtc`, `observedAtUtc`, `waitedMs`, `attempt`, `attemptLimit`. An auditor — or a test — can therefore re-derive, **from the log alone**, that no release was premature:

```
for every TaskRetryReleased: observedAtUtc >= scheduledEligibleAtUtc
                             and scheduledEligibleAtUtc == the matching TaskRetryScheduled's eligibleAtUtc
```

`test_no_release_precedes_its_eligibility_when_re_derived_from_the_log` does exactly this over the full scenario log. Mutation 5 ("remove retry eligibility enforcement") is caught by it even if every in-process assertion were removed, because the evidence is in the log rather than in the code.

### 11.4 `run_once` must not spin

Step 1's `run_once` loops `while True` over drivable tasks. Step 2 adds `failed` and *eligible* `retry_scheduled` to the drivable set — and **must not** add ineligible `retry_scheduled`, or the loop would select the same task forever.

Guarantee: the clock does not advance during a `run` (one `now` is sampled at the top of each loop iteration and is monotonic), and every iteration either advances a task's state or removes it from the drivable set. A task that fails and reschedules with a non-zero backoff leaves the drivable set immediately. A task with `backoffBaseMs = 0` becomes eligible at once and re-enters — bounded by `attemptLimit`, which is bounded by `MAX_ATTEMPT_LIMIT`. **Termination is therefore bounded by `MAX_ATTEMPT_LIMIT × tasks`.** A test asserts `run_once` terminates with `backoffBaseMs = 0` and `attemptLimit = 10`, and a second asserts it does **not** release a task whose backoff has not elapsed.

### 11.5 Ordering

The four-event retry sequence is fixed and asserted:

```
TaskFailed → TaskRetryScheduled → TaskRetryReleased → TaskClaimed → TaskStarted
```

`test_retry_event_ordering_is_exact` reads the log and asserts this subsequence per attempt, with contiguous `sequence` numbers within the workflow.

---

## 12. Dead-Letter Design

### 12.1 Eligibility (Q16)

`failed → dead_lettered` when `classify_failure()` returns `RETRY_NO`, for any of five reasons:

| `deadLetterReason` | Condition |
|---|---|
| `attempts_exhausted` | retryable class, `attempt >= attemptLimit` |
| `non_retryable_error_class` | class is terminal in Catalog §K |
| `policy_denial_never_retried` | class is `policy_blocked` |
| `requires_review_no_gate` | class routes to review and no review gate exists (F-2) |
| `unknown_error_class` | class is not in Catalog §K — **fail closed** |

There is no sixth path out of `failed` other than operator `cancelled`. A test enumerates every one of the 12 Catalog §K classes plus an invented one, drives a task to failure with each, and asserts the resulting terminal state and reason — 13 cases, no gaps.

### 12.2 Terminal (Q17)

`dead_lettered` is already in `TERMINAL_STATES` (committed MOGO-010; verified, not assumed). Consequences, all inherited from Step 1 rather than newly built:

- `terminal = 1` is set by the same guarded UPDATE.
- Any later transition is classified by `classify_late_transition`, recorded in `transition_anomalies`, and **not applied**.
- `run_once` never selects it (`terminal = 0` filter).
- A dead-lettered task cannot execute again — asserted directly by `test_a_dead_lettered_task_is_never_dispatched_again`, which drives a full second `run` and asserts zero new attempts. Mutation 11 is caught here.

### 12.3 What is preserved (Q18)

`TaskDeadLettered.payload`:

```json
{
  "reason": "attempts_exhausted",
  "finalErrorClass": "transient",
  "attempts": 3,
  "attemptLimit": 3,
  "capabilityId": "CAP|research|runtime-fail-then-succeed",
  "reviewGateRequired": false,
  "attemptHistory": [
    {"attempt": 1, "errorClass": "transient", "failedAtUtc": "…", "logSequence": 8,  "leaseGeneration": 1},
    {"attempt": 2, "errorClass": "transient", "failedAtUtc": "…", "logSequence": 13, "leaseGeneration": 2},
    {"attempt": 3, "errorClass": "transient", "failedAtUtc": "…", "logSequence": 18, "leaseGeneration": 3}
  ]
}
```

The dead-letter event is **self-contained**: one event answers "what failed, how often, why, and under which lease", satisfying Constitution §13 without following references.

**The history is not trusted because it is written — it is checked.** `test_dead_letter_history_matches_the_history_re_derived_from_the_log` rebuilds the attempt history by scanning `TaskFailed` events independently and asserts equality with the payload. A payload that lied would fail. This matters: a self-contained summary is a second copy of a fact, and a second copy that is never compared is a place for drift to hide.

### 12.4 Late transitions into and out of `dead_lettered`

- **Into** a task already dead-lettered — recorded as an anomaly, not applied (§12.2).
- **Out of** a dead-lettered task — impossible: `legal_successors("dead_lettered") == ()`. `assert_legal_transition` raises before any UPDATE, and the terminal check fires first anyway. `test_no_transition_out_of_dead_lettered_is_legal` asserts the contract directly, and `test_a_late_success_after_dead_letter_is_an_anomaly_not_applied` drives the real path.

### 12.5 Replay

`rebuild()` reproduces `dead_lettered` exactly, because every input to the decision — error class, attempt, attempt limit — is recorded in events, and the decision itself was already made and recorded as `TaskDeadLettered`. **Replay never re-decides; it re-applies.** Mutation 12 ("make dead-letter transition SQLite-only") is caught by `test_rebuild_reproduces_dead_letter_state_exactly`, which drops the index and rebuilds from the log.

---

## 13. Lease Data Model

### 13.1 What makes this lease useful rather than ceremonial (Q31)

Answering this first, because if it has no answer the lease should not be built.

**The lease is not what provides mutual exclusion in Step 2.** `fcntl.flock` does, and it does it better. If the lease were only a timestamp column nobody consults, it would be exactly the speculative abstraction the design principles forbid, and the right call would be to defer it.

It earns its place by doing two jobs that `flock` cannot:

**Job 1 — it turns Step 1's assumption into a verified fact.** Step 1's recovery reclaims *every* task in `claimed`/`running`, justified by "single-writer, so the previous holder is gone." That is true, and it is an **assumption**, and Constitution §11 requires recovery to resume from a *verified* checkpoint, "never from an assumed one". With a lease, reclaim becomes a checked predicate over recorded facts: the task is reclaimable iff its lease is held by a **provably absent owner** or has **provably expired**. "Provably absent" is decidable: we hold the exclusive `flock`, so no other runtime can be executing; therefore a lease stamped with a different `runId` belongs to a process that cannot act. The reclaim reason is recorded, and an unreclaimable task is left alone rather than swept up.

**Job 2 — it makes writing a result without authority impossible rather than merely unlikely.** Architecture §24: *"only the lease holder may write results."* Step 2 implements this as a check immediately before the success or failure append (§14.5). Without a lease there is nothing to check against, and the rule stays a sentence in a document.

Both jobs exist today, in Step 2, with one process. That is the test the lease had to pass.

### 13.2 The record (Q19, Q20)

A lease is not a separate table. It is **five columns on `tasks`**, written by the same guarded UPDATE that performs the `queued → claimed` transition, and populated from the `TaskClaimed` event payload.

| Column | Type | Meaning | Rebuildable from |
|---|---|---|---|
| `lease_holder` | TEXT | owner identity, `runner:<runId>` | `TaskClaimed.payload.leaseHolder` |
| `lease_generation` | INTEGER | monotonic per task; the CAS token of Architecture §18.1 | `TaskClaimed.payload.leaseGeneration` |
| `lease_acquired_at` | TEXT | ISO-8601 UTC ms | `TaskClaimed.payload.leaseAcquiredAt` |
| `lease_expires_at` | TEXT | ISO-8601 UTC ms | `TaskClaimed.payload.leaseExpiresAt` |
| `lease_ttl_ms` | INTEGER | the TTL in force, recorded so expiry is verifiable from the log | `TaskClaimed.payload.leaseTtlMs` |

Catalog §C names `leaseHolder` and `leaseExpiresAt`; Architecture §18.1 names `leaseGeneration`. All three are adopted **verbatim**. `leaseAcquiredAt` and `leaseTtlMs` are added so that an auditor can verify an expiry decision from the log without knowing the build's TTL default — the same reason §9.4 records the backoff parameters.

A lease is **cleared** (all five set to NULL/0-generation-preserved) on every transition out of `claimed`/`running`. `lease_generation` is *never* reset — it only increases, which is what makes it a valid CAS token across reclaims.

### 13.3 Owner identity (Q21)

```
leaseHolder = "runner:" + runId          # runId is a UUIDv4 minted once when Orchestrator.open() succeeds
```

- **Not a PID.** PIDs are reused, are OS state rather than log state, and are meaningless after a reboot.
- **Not a hostname.** Step 2 is single-host by construction; adding one would imply a distribution model that does not exist.
- **A per-run UUID** is unique per run, recorded in the event payload (so replay reproduces it), and gives the "provably absent owner" test its decidable form: `lease_holder != "runner:" + self.run_id` **and** we hold the exclusive `flock` ⇒ the holder cannot be executing.

`runId` is also recorded in a `runs` table (`run_id`, `started_at`, `ended_at`, `pid`) purely for the audit report, so an operator can see which run held which lease. That table is a **local observation**, not replayable truth, and is marked as such alongside `command_submissions` and `transition_anomalies`.

### 13.4 TTL, and why it cannot expire mid-execution (Q26)

```
leaseTtlMs = max(2 * capability.resourceLimits.wallClockMs, LEASE_TTL_FLOOR_MS)   # floor = 30000
```

Echo declares `wallClockMs: 5000` → TTL 30 s. `fail_then_succeed` declares `wallClockMs: 5000` → TTL 30 s.

Execution in Step 2 is **synchronous, in-process, single-threaded and bounded by the declared wall-clock limit**, so a lease at twice that limit cannot expire while its own execution is running under any normal condition. If a clock jump made it appear expired anyway, §14.5's holder verification refuses to record the result and records an anomaly instead of writing under an expired lease. Failing closed is correct here: the alternative is a result recorded by an authority the runtime cannot vouch for.

---

## 14. Lease Acquisition and Expiry

### 14.1 Acquisition is atomic (Q22)

The same guarded-UPDATE primitive Step 1 proved, with additional `SET` clauses. No new mechanism, no advisory locking, no read-then-write:

```sql
UPDATE tasks
   SET state             = 'claimed',
       lease_holder      = :holder,
       lease_generation  = lease_generation + 1,
       lease_acquired_at = :acquired_at,
       lease_expires_at  = :expires_at,
       lease_ttl_ms      = :ttl_ms,
       last_log_sequence = :seq
 WHERE task_id = :id
   AND state   = 'queued'
   AND last_log_sequence < :seq
```

`rowcount == 1` ⇒ claimed. `rowcount == 0` ⇒ either already applied (replay) or the task was not `queued` (a second claimant) — disambiguated by re-reading the row, exactly as Step 1 does. The whole statement runs inside the `BEGIN IMMEDIATE` transaction of the `TaskClaimed` event, so the index row, the state change and the lease commit together or not at all.

### 14.2 Only an eligible `queued` task can be leased (Q25)

The `AND state = 'queued'` clause is the entire rule. A task in `claimed`, `running`, `retry_scheduled`, `failed` or any terminal state cannot be leased, because the guard does not match. There is no code path that writes a lease outside this statement, asserted by `test_lease_columns_are_written_by_exactly_one_sql_statement`.

### 14.3 A second claimant fails

Within one run, a second claim attempt on a held task finds `state = 'claimed'` and does not match — `rowcount == 0`, no mutation, anomaly recorded. Across runs, a second process cannot start at all: `ProcessLock` refuses with `RuntimeBusyError` and exit code 5. Both are tested; the second is a Step 1 test that remains valid.

### 14.4 Expiry, and renewal (Q23, Q24)

```python
def is_expired(lease_expires_at_ms, now_ms):
    return now_ms >= lease_expires_at_ms      # pure
```

**Renewal is deliberately not implemented in Step 2.** Renewal exists to keep a lease alive across an execution longer than its TTL. Step 2's execution is synchronous and bounded at half the TTL, so no execution can outlive its lease. Building a renewal path now would mean building a heartbeat with nothing to keep alive, and a code path with no caller is a code path with no test.

**The condition that makes renewal necessary is named, so the future step does not have to rediscover it:** any execution that can exceed `leaseTtlMs / 2` — a long-running acquisition, an out-of-process worker, or a daemon. Recorded as a carried item (§37).

### 14.5 Only the lease holder may write results

Architecture §24, implemented rather than documented. Immediately before appending `TaskSucceeded` or `TaskFailed`, the orchestrator verifies:

```python
holder_ok = (row["lease_holder"] == self.lease_holder
             and row["lease_generation"] == claimed_generation)
```

If it does not hold, **no result event is appended**. A `transition_anomalies` row records `result_written_without_lease`, and the task is left for recovery to reclaim. The result is discarded rather than recorded under an authority the runtime cannot vouch for — Constitution §11's "never pick a winner" applied to authority rather than to output.

`claimed_generation` is captured at claim time and carried in memory through the execution, so the check compares against the generation *this* execution claimed with, not merely against "some current generation". That distinction is what makes the check meaningful: a reclaim that bumped the generation mid-flight is detected.

Mutation 9 ("remove lease-owner verification") is detected by `test_a_result_is_refused_when_the_lease_generation_changed_mid_execution`, which bumps the generation behind the executing code's back and asserts no `TaskSucceeded` is appended.

---

## 15. Lease Recovery

### 15.1 The reclaim predicate (Q27, Q28, Q29)

One pure function, four quadrants, all unit-tested without a database:

```python
def reclaim_reason(lease_holder, lease_expires_at_ms, now_ms, current_holder):
    """None → do not reclaim. Otherwise the recorded reason."""
    if lease_holder is None:
        return "no_lease"                 # claimed/running with no lease: pre-Step-2 row
    if lease_holder != current_holder:
        return "owner_gone"               # provably absent: we hold the exclusive flock
    if now_ms >= lease_expires_at_ms:
        return "lease_expired"
    return None                           # our own live lease — leave it alone
```

| `lease_holder` | expired? | Result | Test |
|---|---|---|---|
| another run | — | **`owner_gone`** → reclaim | `test_a_lease_from_a_previous_run_is_reclaimed` |
| ours | yes | **`lease_expired`** → reclaim | `test_an_expired_lease_is_reclaimed` |
| ours | no | **None** → refuse | `test_a_live_lease_is_not_reclaimed_prematurely` |
| absent | — | **`no_lease`** → reclaim | `test_a_claimed_task_with_no_lease_is_reclaimed` (Step 1 upgrade path) |

The third row is the one that matters: it is what makes the lease a *verification* rather than a rubber stamp, and it is the case Step 1 could not express. Mutations 8 and 10 are both detected here.

### 15.2 Recovery phase R4, rewritten

```
for each task in ('claimed','running'):
    reason = reclaim_reason(row.lease_holder, parse(row.lease_expires_at), now_ms, self.lease_holder)
    if reason is None:
        record anomaly 'live_lease_not_reclaimed'; leave the task alone
        continue
    emit TaskReclaimed(
        reclaimedFrom          = row.state,
        reason                 = reason,
        previousLeaseHolder    = row.lease_holder,
        previousLeaseGeneration= row.lease_generation,
        leaseExpiresAt         = row.lease_expires_at,
        observedAtUtc          = now,
    )                                     # → queued, lease cleared, generation preserved
```

Every reclaim is an event, carries its reason, and is idempotent: a second `recover()` finds nothing in `claimed`/`running` and emits nothing. `test_recover_is_idempotent` (Step 1) remains valid and is extended to the lease case.

### 15.3 Clock rollback during recovery (Q29)

The monotonic guard (§10.5) runs **before** any recovery event is appended, so a rolled-back clock aborts recovery rather than producing reclaims stamped earlier than the events they follow. A rolled-back clock therefore cannot cause a premature reclaim: the runtime refuses to act at all. Recorded in `recovery_actions` as `clock_rollback_refused`.

### 15.4 The full recovery order

Unchanged in shape from Step 1; two phases gain lease awareness.

| Phase | Action | Step 2 change |
|---|---|---|
| R1 | acquire the exclusive `flock` | — |
| R1b | **monotonic clock check** | **new** |
| R2 | quarantine and truncate a torn tail | — |
| R3 | replay everything the index missed | — |
| R4 | **reclaim by verified predicate** | **rewritten** (§15.1) |
| R5 | resume commands accepted with no task | — |
| R6 | **release retries whose backoff has elapsed** | **new** — folded into `run_once`, not `recover`, because it is forward progress rather than repair |

R6 is deliberately in `run_once` and not in `recover`: `recover` repairs the past, `run_once` makes progress. Putting a release in recovery would mean `submit` (which calls `recover`) silently advanced retries, which is a side effect an operator did not ask for.

---

## 16. Second Capability Design

### 16.1 Identity (Q42)

| | |
|---|---|
| `capabilityId` | `CAP|research|runtime-fail-then-succeed` |
| `name` | `research.runtime.fail-then-succeed.v1` |
| `version` | `1.0.0` |
| `lifecycleStatus` | **`approved`** — not `production` |
| `enabledState` | `true` |
| `operationClass` | `non_acquisition` |
| `effectClass` | **`pure`** |
| `acceptedCommands` | `["NormalizeArtifact"]` |
| `compatibility` | `{"NormalizeArtifact": [1]}` |
| `failureClasses` | `["transient"]` |
| `requiresExecutionContext` | `true` |
| `requiredConnectors` / `requiredSecretReferences` / `requiredPermissions` | `[]` |
| `resourceLimits` | `{"wallClockMs": 5000, "maxPayloadBytes": 65536}` |
| `retryPolicy` | `{"attemptLimit": 3, "backoffBaseMs": 0, "backoffMultiplier": 2, "backoffCapMs": 60000, "jitterMs": 0}` |

`lifecycleStatus: approved` rather than `production` is honest — this is an approved demonstration capability, not production work — and it exercises the second dispatchable lifecycle state, which Step 1 never did (echo is `production`). Coverage gained for free.

### 16.2 Behaviour, and the invariant that keeps it pure (Q43)

```python
def execute(payload, context):
    ids.require_json_shaped(payload, "$capabilityPayload")
    fail_until = payload.get("failUntilAttempt", 1)      # semantic, part of the idempotency key
    attempt    = context["attempt"]                      # execution context, NOT part of the key
    if attempt <= fail_until:
        raise CapabilityFailure("transient",
            "declared deterministic failure on attempt %d of at most %d" % (attempt, fail_until))
    semantic = {k: v for k, v in ids.as_plain(payload).items() if k != "failUntilAttempt"}
    canonical = ids.canonical_json_bytes(semantic)
    return {"normalizedPayload": semantic,
            "contentHash": ids.sha256_hex(canonical),
            "byteLength": len(canonical),
            "capabilityId": CAPABILITY_ID,
            "capabilityVersion": CAPABILITY_VERSION}
```

**The invariant, and it is the whole design:** the *decision* to fail depends on `attempt`; the *result content* does **not**. Attempt 2 and attempt 5 produce byte-identical output. That is what keeps crash boundary 8 safe for this capability under the same argument that keeps it safe for echo — re-execution after an interrupted run is indistinguishable from never having been interrupted.

Asserted by `test_the_success_result_is_identical_for_every_attempt_that_succeeds`, comparing `contentHash` across attempts 2 … 10.

**Purity, mechanically:** no file read, no socket, no subprocess, no clock, no randomness. Enforced by the same static AST scan that covers echo, extended to the whole `capabilities/` package with an additional clock-and-randomness clause.

### 16.3 Dead-letter demonstration without a second capability (Q44)

The tasking asks whether an always-fail capability is needed and warns against inventing one to satisfy a test. **It is not needed.** The same capability with `failUntilAttempt >= attemptLimit` fails every attempt and dead-letters deterministically. Three reasons this is better than a second capability:

1. It is not a special mode — `failUntilAttempt` is an ordinary declared parameter with ordinary semantics, exercised at a different value.
2. Because `failUntilAttempt` is part of the semantic payload, it participates in the idempotency key, so the retry scenario and the dead-letter scenario are naturally **different tasks** with different keys. A shared "always fail" flag outside the payload would have collided.
3. One capability, one manifest, one purity proof, one determinism proof.

`retryPolicy.backoffBaseMs = 0` on this capability makes the demonstration complete in a single `run` with **no sleeping and no clock manipulation** — the eligibility rule is enforced identically (`now >= eligibleAt` with a zero delay is still a real check). The *tests* use a non-zero base with a `ManualClock` to prove the rule bites; `test_a_retry_is_not_released_before_its_eligibility` asserts that with `backoffBaseMs = 1000` and an unadvanced clock, `run_once` releases nothing. Both are real; neither is a shortcut.

### 16.4 The first capability remains unchanged

`echo.py` is **not modified** — not its code, not its manifest, not its module docstring. This is enforced rather than intended:

```
test_the_echo_capability_module_is_byte_identical_to_the_committed_version
test_the_echo_manifest_hash_is_unchanged
    → 55a298289a3daaca6d2370c5a006b534c8e4b90fe0440763161eb033971ef82b
test_the_echo_result_hash_is_unchanged
    → 4a45c52fd69e19841fe5f8b10be04cfbb85031fc516cff13308bab3b192dad5e
```

The manifest hash pin is load-bearing for a second reason: `registry.register()` refuses a changed manifest under the same `capabilityId`, so an accidental change to echo would break every existing Step 1 state root on upgrade. The test catches it in the suite instead of in the field.

This is why nothing in Step 2 adds a *required* manifest field. `effectClass`, `failureClasses`, `requiresExecutionContext` and `retryPolicy` are all read with `manifest.get(…, <restrictive default>)`, so echo's committed manifest stays valid, byte-identical, and hash-stable. §18.3 explains why the restrictive default is the safe direction.

---

## 17. Risk A-5 Resolution

**Risk A-5, preserved verbatim from the Step 1 reports:**

> **Crash boundary 8 — interrupted between execution and recording success — is safe ONLY because the capability is pure.** Re-execution after an interrupted run produces a byte-identical result, so it is indistinguishable from never having been interrupted. **That is a property of *this capability*, not of the kernel.** The moment a capability performs an external effect, this argument fails. An effectful capability requires output verification and an idempotency-keyed result store **before** it may be registered. This is a hard gate on Step 2, on the first connector, and on any future autonomous agent that acquires, writes, or calls out.

### 17.1 Determination — **Option A**, requiring ratification (DECISION B-4)

> **Step 2 remains limited to pure capabilities. Registration of an effectful capability is mechanically prohibited.**

### 17.2 Why not Option B

The tasking says to prefer A "unless a genuinely useful and safely testable effectful capability can be implemented without expanding Step 2 beyond a bounded runtime milestone." Applying that test honestly:

| Question | Answer |
|---|---|
| Does Step 2 *need* an effectful capability? | **No.** Both scenarios — retry and dead-letter — are naturally pure. |
| Is there a useful one available? | **No.** Every effectful capability in the roadmap is a connector, and Architecture §32 item 5 puts the **policy gate before any connector**. There is no legal effectful capability to build. |
| Could the A-5 machinery be built anyway? | Yes — and it would be built with nothing to test it against. Constitution §11 requires output verification by re-hashing, duplicate-output detection ("never pick a winner"), and idempotency-keyed result storage. Those are correct only against a real effect. |
| Cost of choosing B | Two half-built subsystems instead of one finished one, and a safety mechanism whose first real exercise happens in a later milestone, which is exactly when a latent defect is most expensive. |

**Choosing B here would be choosing to look more advanced. That is the failure mode the tasking names explicitly.**

### 17.3 What the gate actually is

Not a comment and not a convention — a declared table of preconditions, all currently `False`:

```python
A5_EFFECTFUL_GATE = MappingProxyType({
    "idempotencyKeyedResultStore":  False,   # Constitution §11, Catalog §I
    "outputVerificationByRehash":   False,   # Constitution §11, Architecture §19
    "duplicateEffectPrevention":    False,   # Constitution §11 "never pick a winner"
    "postExecutionRecoveryRule":    False,   # the boundary-8 rule for an effectful capability
})

def assert_effect_class_permitted(effect_class):
    if effect_class == "pure":
        return
    missing = [k for k, ok in A5_EFFECTFUL_GATE.items() if not ok]
    fail("capability declares effectClass=%r; risk A-5 requires %s, none of which "
         "exists in this build" % (effect_class, missing), EffectClassRefusedError)
```

**The gate cannot be opened by accident.** Two tests bind it:

- `test_every_a5_gate_precondition_is_false_in_this_build` — asserts all four are `False`.
- `test_registering_an_effectful_capability_is_refused_and_names_every_missing_precondition` — registers a synthetic effectful manifest and asserts refusal, with all four names in the message.

A future step that builds the result store must flip a flag, which **fails the first test**, which forces a governance decision at exactly the moment the gate opens. That is the property worth having: the gate is closed by data, and opening it is loud.

### 17.4 What Step 2 does *not* claim

Step 2 adds **no** output verification, **no** result store, and **no** duplicate-effect prevention, because it registers nothing that needs them. A-5 is closed by **prohibition**, not by construction. Saying otherwise would be a false completeness claim, and the risk remains open for Step 3 in exactly the form quoted above.

### 17.5 A-5 restated for the next step, unweakened

Carried forward into §37 verbatim. Its severity is unchanged (**High**). Its scope narrows only in that Step 2 makes the prohibition mechanical rather than documentary — the underlying hazard is untouched.

---

## 18. Result Idempotency and Effect Classification

### 18.1 Distinguishing pure from effectful (Q45)

Three layers, and the declaration is the weakest of them — stated plainly because a declaration cannot make code pure:

| Layer | Mechanism | Strength |
|---|---|---|
| **Static** | AST scan over `capabilities/**`: no `open`, no filesystem mutation call, no network or subprocess import, **no clock read, no randomness** | **strongest** — applies whether or not anything is declared |
| **Registry** | `effectClass ∈ {"pure","effectful"}`; `effectful` refused by the A-5 gate | gate |
| **Declaration** | `effectClass` in the manifest, surfaced by `status` and `audit` | documentation |

### 18.2 Is effect classification added to the manifest? (Q46)

Yes — `effectClass`, plus `failureClasses[]`, `requiresExecutionContext`, and `retryPolicy`. All four are **optional with restrictive defaults**, for the reason in §16.4: making any of them required would invalidate echo's committed manifest, change its hash, and break upgrade of every existing state root.

| Field | Absent means | Why that default is the safe direction |
|---|---|---|
| `effectClass` | `"pure"` | `pure` **grants nothing**; `effectful` is the permissive value and must be declared explicitly — and is then refused. An undeclared capability gets the most restricted classification. |
| `failureClasses` | `[]` | any declared failure class is then a violation → non-retryable `deterministic_processing`. Absence grants no retryability. |
| `requiresExecutionContext` | `false` | the capability receives *less* information, not more. |
| `retryPolicy` | build defaults (§9.1) | bounded, non-zero, capped. |

**The residual risk is stated rather than hidden:** a genuinely effectful capability that declares `pure` is caught by the *static* layer, not by the registry. That is why the static layer is described as the enforcement and the declaration as documentation, and why the static scan — not the manifest — is the thing extended in Step 2. Recorded as risk B-3 in §36.

### 18.3 Blocking unsafe registration (Q47)

`registry.register()` refuses, before any INSERT, when **any** of:

1. `effectClass` is not in `("pure", "effectful")` → `ContractValidationError`
2. `effectClass == "effectful"` → `EffectClassRefusedError`, naming all four missing A-5 preconditions
3. `failureClasses` contains a name outside Catalog §K → `ContractValidationError`
4. `failureClasses` contains `source_mutated` or `human_review_required` → refused, no review gate (F-2)
5. `retryPolicy.backoffMultiplier` is not an integer ≥ 1, or any policy value is negative → `RetryPolicyError`
6. `retryPolicy.attemptLimit` exceeds `MAX_ATTEMPT_LIMIT` → `RetryPolicyError`

Each is a separate test, and each is a fail-closed refusal before any state change. Mutation 14 ("register an effectful capability without the A-5 gate") is caught by condition 2.

### 18.4 The gate before any future connector capability (Q48)

Four preconditions, in order, none satisfied:

| # | Gate | Authority | Status |
|---|---|---|---|
| 1 | **Policy gate** — classification, authorization records, enforcement tests | Architecture §32 item 5: *before any connector* | ❌ not built |
| 2 | **A-5 result store** — idempotency-keyed store, output verification, duplicate-effect prevention, post-execution recovery rule | Constitution §11; risk A-5 | ❌ not built |
| 3 | **D-15 first-connector approval** — filesystem/operator-drop | ADR-012 D-15 (approved in principle) | ⏸ approved, not authorized for implementation |
| 4 | **Acquisition Authorization Record** per source | Constitution §5.1, Catalog §M | ❌ none exists |

This table is declared as data in `registry.py` (`CONNECTOR_GATES`) and printed by `status`, so an operator can see what stands between the platform and its first acquisition **without reading code** — Constitution §13, applied to the gate itself.

---

## 19. JSONL Authority and SQLite Projection

### 19.1 How Step 2 preserves the log as authority (Q34)

Unchanged in principle, and checked column by column rather than asserted. Every new column is **copied from an event payload**, never computed during projection. That single rule is what makes the whole index rebuildable.

### 19.2 Rebuildability, column by column (Q35, Q36)

| Table.column | Source event | Source field | Computed at projection? |
|---|---|---|---|
| `tasks.attempt` | `TaskStarted` | — (increment) | derived by counting applied transitions — **deterministic**, see below |
| `tasks.attempt_limit` | `TaskRequested` | `payload.attemptLimit` | no — copied |
| `tasks.retry_eligible_at` | `TaskRetryScheduled` | `payload.eligibleAtUtc` | no — copied |
| `tasks.backoff_ms` | `TaskRetryScheduled` | `payload.backoffMs` | no — copied |
| `tasks.lease_holder` | `TaskClaimed` | `payload.leaseHolder` | no — copied |
| `tasks.lease_generation` | `TaskClaimed` | `payload.leaseGeneration` | no — copied |
| `tasks.lease_acquired_at` | `TaskClaimed` | `payload.leaseAcquiredAt` | no — copied |
| `tasks.lease_expires_at` | `TaskClaimed` | `payload.leaseExpiresAt` | no — copied |
| `tasks.lease_ttl_ms` | `TaskClaimed` | `payload.leaseTtlMs` | no — copied |
| `tasks.dead_letter_reason` | `TaskDeadLettered` | `payload.reason` | no — copied |
| `commands.attempt_limit` | `CommandAccepted` | `payload.attemptLimit` | no — copied |
| `capabilities.effect_class` | — | manifest at registration | **not replayable — see §19.4** |
| `task_attempts.*` | `TaskStarted` + `TaskSucceeded`/`TaskFailed` | payload fields | no — copied |
| `runs.*` | — | local observation | **not replayable — see §19.4** |

**`tasks.attempt` is the one derived value, and it is derived deterministically.** It is `attempt + 1` applied exactly once per `TaskStarted` transition. Replaying the same log always applies the same number of `TaskStarted` transitions in the same order, so the final value is identical. `lease_generation` has the same shape and the same guarantee — except that its value is *also* recorded in the payload, so it is doubly verifiable. A test asserts the rebuilt `lease_generation` equals the value recorded in the last `TaskClaimed` payload for every task, which catches a divergence between the increment and the record.

### 19.3 The rebuild test is the proof, not the argument

`test_rebuild_reproduces_every_step_2_column_exactly` runs the complete scenario (retry, release, success, dead-letter, reclaim), snapshots every row of `tasks`, `commands` and `task_attempts`, runs `reset --rebuild-index`, and asserts **byte-equality of every column**, including all lease and retry fields. If any column were computed from a clock at projection time, this test fails — which is precisely why it is written as a whole-row comparison rather than a spot check.

### 19.4 What is honestly not replayable (Q36)

Two tables hold **local observations** rather than replayable facts, and are marked as such in the schema alongside Step 1's `command_submissions` and `transition_anomalies`:

- **`capabilities`** — populated from manifests at registration, not from events. This was already true in Step 1. Catalog §O says every lifecycle transition should be an event; Step 2 does **not** add capability-lifecycle events, because no lifecycle transition occurs — capabilities are registered once at `init` and never change state. Recorded as a carried item, not claimed as done.
- **`runs`** — which run held which lease. Useful for audit, meaningless to replay.

Naming these is the point. A table that quietly held non-rebuildable truth while the design claimed full rebuildability would be exactly the drift ADR-012 D-05 exists to prevent.

---

## 20. Schema Migration Plan

### 20.1 Version and mechanism (Q37)

```python
SCHEMA_VERSION = 2
MIGRATIONS = ((1, _create_v1), (2, _migrate_v2))
```

The ordered-migration framework already exists and behaves correctly: `initialize()` applies every migration numbered above the stored version inside **one** `BEGIN IMMEDIATE`, and refuses a stored version higher than the build supports. Step 2 adds an entry to the tuple and changes one constant. **No migration machinery is invented.**

Ordering is enforced, not assumed: `test_migrations_are_ordered_contiguous_and_start_at_one` asserts the version numbers are `(1, 2)` in ascending order with no gaps, which is what makes mutation 16 ("corrupt schema migration ordering") detectable.

### 20.2 `_migrate_v2`, exactly

```sql
ALTER TABLE tasks        ADD COLUMN attempt_limit             INTEGER NOT NULL DEFAULT 3;
ALTER TABLE tasks        ADD COLUMN retry_eligible_at         TEXT;
ALTER TABLE tasks        ADD COLUMN backoff_ms                INTEGER;
ALTER TABLE tasks        ADD COLUMN lease_holder              TEXT;
ALTER TABLE tasks        ADD COLUMN lease_generation          INTEGER NOT NULL DEFAULT 0;
ALTER TABLE tasks        ADD COLUMN lease_acquired_at         TEXT;
ALTER TABLE tasks        ADD COLUMN lease_expires_at          TEXT;
ALTER TABLE tasks        ADD COLUMN lease_ttl_ms              INTEGER;
ALTER TABLE tasks        ADD COLUMN dead_letter_reason        TEXT;

ALTER TABLE commands     ADD COLUMN attempt_limit             INTEGER NOT NULL DEFAULT 3;

ALTER TABLE capabilities ADD COLUMN effect_class              TEXT    NOT NULL DEFAULT 'pure';
ALTER TABLE capabilities ADD COLUMN failure_classes           TEXT    NOT NULL DEFAULT '[]';
ALTER TABLE capabilities ADD COLUMN requires_execution_context INTEGER NOT NULL DEFAULT 0;
ALTER TABLE capabilities ADD COLUMN retry_policy              TEXT    NOT NULL DEFAULT '{}';

CREATE TABLE task_attempts (
    attempt_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id               TEXT    NOT NULL REFERENCES tasks (task_id),
    attempt               INTEGER NOT NULL,
    lease_generation      INTEGER NOT NULL,
    started_log_sequence  INTEGER NOT NULL,
    finished_log_sequence INTEGER NOT NULL,
    outcome               TEXT    NOT NULL CHECK (outcome IN ('succeeded','failed')),
    error_class           TEXT,
    result_hash           TEXT,
    started_at            TEXT    NOT NULL,
    finished_at           TEXT    NOT NULL,
    UNIQUE (task_id, attempt)
);

CREATE TABLE runs (
    run_id     TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    ended_at   TEXT,
    pid        INTEGER NOT NULL
);

CREATE TABLE capability_violations (
    violation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    detected_at  TEXT NOT NULL,
    capability_id TEXT NOT NULL,
    task_id      TEXT,
    violation    TEXT NOT NULL,
    detail       TEXT
);

CREATE INDEX idx_tasks_retry    ON tasks (state, retry_eligible_at);
CREATE INDEX idx_tasks_lease    ON tasks (lease_expires_at);
CREATE INDEX idx_attempts_task  ON task_attempts (task_id, attempt);
CREATE INDEX idx_attempts_error ON task_attempts (error_class, attempt_id);
```

`ALTER TABLE … ADD COLUMN` with a constant `DEFAULT` is supported and O(1) on SQLite 3.53.3, preserves every existing row, and cannot fail partway (the whole migration is inside one transaction, and a failure rolls back to v1 leaving a working v1 database).

`capability_violations` is append-only by trigger, joining `event_index`, `command_submissions` and `transition_anomalies` in `APPEND_ONLY_TABLES`. `task_attempts` is **not** append-only: rows are inserted complete, once, when the outcome event is applied, and `rebuild()` must be able to delete them.

`rebuild()`'s delete list grows from `("event_index","tasks","commands","transition_anomalies")` to include `task_attempts`. `runs`, `capabilities`, `command_submissions`, `recovery_actions` and `capability_violations` are **not** deleted by a rebuild — they are local observations, and destroying them would lose history the log cannot restore.

### 20.3 Reversibility for demonstration data (Q38)

**No down-migration is implemented, deliberately.** The correct rollback for a *derived* index is not to un-migrate it — it is to delete it and rebuild it from the authoritative log under the older build. That is stronger than a down-migration because it cannot half-apply, and it is the executable proof of ADR-012 D-05 that already exists.

Exact commands in §34. A down-migration would also have to drop columns, which is the one SQLite operation most likely to lose data on a partial failure — precisely the risk not worth taking for a rebuildable store.

### 20.4 Older Step 1 databases (Q39)

A state root created by the Step 1 build opens under Step 2 and migrates automatically:

1. `current_version()` returns 1 → `_migrate_v2` runs inside one transaction.
2. Existing `tasks` rows gain `attempt_limit = 3`, `lease_generation = 0`, and NULL lease fields.
3. A pre-Step-2 task sitting in `claimed`/`running` has **no lease**, so `reclaim_reason()` returns `"no_lease"` and it is reclaimed — the upgrade path is a first-class case, not an afterthought (§15.1, row 4).
4. Existing `CommandAccepted` events have **no `attemptLimit` in their payload**. The projection reads `payload.get("attemptLimit", COMMAND_DEFAULTS["attemptLimit"])` — the committed contract default, not a re-declared 3.
5. `task_attempts` starts empty for historical tasks. It is populated only from Step 2 onward, and `audit` labels historical tasks `attempts not recorded (pre-v2)` rather than reporting a misleading zero.

`test_a_step_1_state_root_upgrades_and_replays_correctly` builds a genuine v1 database and v1-shaped log with the Step 1 schema, opens it under Step 2, and asserts the migration, the defaults, the reclaim, and a clean `verify`.

### 20.5 Log valid, schema old (Q40)

Handled by the same path: migration runs at `open()`, then R3 replay catches the index up. A v1 log replayed into a v2 schema produces tasks with default attempt limits and no lease history — correct, because none existed. `test_a_v1_log_rebuilds_into_a_v2_schema` proves it via `reset --rebuild-index`.

### 20.6 Database newer than the runtime supports (Q41)

Already implemented in Step 1 and unchanged: `initialize()` raises `SchemaVersionError` and refuses to operate. Step 2 extends the test to version 3 and additionally asserts that the refusal happens **before** any pragma-level write and that the database is left untouched — `test_a_future_schema_is_refused_without_modifying_the_database` compares the file's SHA-256 before and after.

---

## 21. Exact Tables and Columns

Complete post-migration state. **Changed and new items in bold.**

### `tasks` — derived read model

| Column | Type | Notes |
|---|---|---|
| `task_id` | TEXT PK | |
| `workflow_id`, `correlation_id`, `command_id`, `capability_id` | TEXT NOT NULL | `command_id` REFERENCES `commands` |
| `idempotency_key` | TEXT NOT NULL **UNIQUE** | unchanged — excludes attempt and time |
| `state` | TEXT NOT NULL | Catalog §L |
| `attempt` | INTEGER NOT NULL DEFAULT 0 | executions **started** |
| **`attempt_limit`** | **INTEGER NOT NULL DEFAULT 3** | total attempts permitted |
| **`retry_eligible_at`** | **TEXT** | ISO-8601 UTC ms; NULL unless `retry_scheduled` |
| **`backoff_ms`** | **INTEGER** | delay in force for the current schedule |
| **`lease_holder`** | **TEXT** | `runner:<runId>` |
| **`lease_generation`** | **INTEGER NOT NULL DEFAULT 0** | CAS token; monotonic, never reset |
| **`lease_acquired_at`** | **TEXT** | |
| **`lease_expires_at`** | **TEXT** | |
| **`lease_ttl_ms`** | **INTEGER** | |
| **`dead_letter_reason`** | **TEXT** | one of the five §12.1 reasons |
| `created_log_sequence`, `last_log_sequence` | INTEGER NOT NULL | `last_log_sequence` is the replay guard |
| `terminal` | INTEGER NOT NULL DEFAULT 0 | |
| `result_hash`, `error_class` | TEXT | |

Indexes: `idx_tasks_state (state, task_id)` · **`idx_tasks_retry (state, retry_eligible_at)`** · **`idx_tasks_lease (lease_expires_at)`**

### `commands`

Unchanged except **`attempt_limit INTEGER NOT NULL DEFAULT 3`**. `UNIQUE (idempotency_key)` retained.

### `capabilities`

Unchanged plus **`effect_class TEXT NOT NULL DEFAULT 'pure'`**, **`failure_classes TEXT NOT NULL DEFAULT '[]'`**, **`requires_execution_context INTEGER NOT NULL DEFAULT 0`**, **`retry_policy TEXT NOT NULL DEFAULT '{}'`**.

### **`task_attempts`** — new, derived, rebuildable

| Column | Type |
|---|---|
| `attempt_id` | INTEGER PK AUTOINCREMENT |
| `task_id` | TEXT NOT NULL REFERENCES `tasks` |
| `attempt` | INTEGER NOT NULL |
| `lease_generation` | INTEGER NOT NULL |
| `started_log_sequence`, `finished_log_sequence` | INTEGER NOT NULL |
| `outcome` | TEXT NOT NULL CHECK IN (`succeeded`,`failed`) |
| `error_class`, `result_hash` | TEXT |
| `started_at`, `finished_at` | TEXT NOT NULL |
| — | **UNIQUE (task_id, attempt)** — the schema-level guarantee that an attempt is recorded once |

The `UNIQUE (task_id, attempt)` constraint is not decoration: it is a second, independent guard against double counting. Mutation 4 ("increment attempt count twice") produces a constraint violation here as well as a test failure, so a double increment cannot be silent even if a test were removed.

### **`runs`**, **`capability_violations`** — new, local observations

Defined in §20.2. `capability_violations` is append-only by trigger.

### Unchanged tables

`schema_meta`, `event_index`, `command_submissions`, `log_cursor`, `transition_anomalies`, `recovery_actions` — no column changes. `event_index` keeps its `UNIQUE (event_id)` and `UNIQUE (workflow_id, sequence)`.

---

## 22. Exact Event Payloads

All timestamps are ISO-8601 UTC millisecond (`…Z`). All payloads are JSON-shaped and canonically hashed by the committed `event.validate_event`, which is unchanged.

### 22.1 `TaskFailed` — extended (additive)

```json
{
  "reason": "declared deterministic failure on attempt 1 of at most 1",
  "attempt": 1,
  "attemptLimit": 3,
  "leaseGeneration": 1,
  "capabilityId": "CAP|research|runtime-fail-then-succeed",
  "declaredByCapability": true
}
```
Envelope: `executionResult: "failure"`, `errorClass: "transient"`, `producer: "orchestrator"`.
`declaredByCapability` distinguishes a failure the capability declared from one the worker classified because the capability escaped unclassified — a distinction an operator needs and cannot otherwise see.

### 22.2 `TaskRetryScheduled`

```json
{
  "attempt": 1,
  "attemptLimit": 3,
  "errorClass": "transient",
  "decisionReason": "retryable_within_attempt_limit",
  "backoffMs": 1000,
  "eligibleAtUtc": "2026-08-08T12:00:01.000Z",
  "scheduledAtUtc": "2026-08-08T12:00:00.000Z",
  "retryPolicy": {"backoffBaseMs": 1000, "backoffMultiplier": 2,
                  "backoffCapMs": 60000, "jitterMs": 0}
}
```
Authority: **orchestrator** (Catalog §L). Transition: `failed → retry_scheduled`.
The policy is recorded in full so the schedule is verifiable from the log without knowing the build.

### 22.3 `TaskRetryReleased` — **NEW NAME, pending approval B-1**

```json
{
  "attempt": 1,
  "attemptLimit": 3,
  "scheduledEligibleAtUtc": "2026-08-08T12:00:01.000Z",
  "observedAtUtc": "2026-08-08T12:00:01.004Z",
  "waitedMs": 1004,
  "scheduledBackoffMs": 1000,
  "causedByLogSequence": 9
}
```
Authority: **orchestrator** (Catalog §L, `retry_scheduled → queued`). Transition: `retry_scheduled → queued`.
`causedByLogSequence` points at the `TaskRetryScheduled` that created the obligation, so the pair is checkable without matching on timestamps.

### 22.4 `TaskClaimed` — extended (additive)

```json
{
  "capabilityId": "CAP|research|runtime-fail-then-succeed",
  "claimMode": "compare_and_set_lease",
  "leaseHolder": "runner:8f1c…",
  "leaseGeneration": 2,
  "leaseAcquiredAt": "2026-08-08T12:00:01.005Z",
  "leaseExpiresAt": "2026-08-08T12:00:31.005Z",
  "leaseTtlMs": 30000,
  "attempt": 1
}
```
`claimMode` changes from `compare_and_set_single_writer` to `compare_and_set_lease`. `attempt` is the value **before** the increment, so the payload states which attempt the claim is for.

### 22.5 `TaskReclaimed` — extended (additive)

```json
{
  "reclaimedFrom": "running",
  "reason": "owner_gone",
  "previousLeaseHolder": "runner:3a92…",
  "previousLeaseGeneration": 1,
  "leaseExpiresAt": "2026-08-08T12:00:31.005Z",
  "observedAtUtc": "2026-08-08T12:00:45.100Z",
  "attempt": 1
}
```
`reason` ∈ `owner_gone` | `lease_expired` | `no_lease`.

### 22.6 `TaskDeadLettered`

Full shape in §12.3. Authority: **orchestrator**. Transition: `failed → dead_lettered`. Envelope carries `executionResult: "failure"` and `errorClass: <finalErrorClass>`.

### 22.7 `TaskStarted`, `TaskSucceeded` — extended (additive)

`TaskStarted` gains `attempt` (the value **after** the increment) and `leaseGeneration`.
`TaskSucceeded` gains `attempt` and `leaseGeneration` alongside its existing `resultHash`, `byteLength`, `capabilityId`, `capabilityVersion`.

### 22.8 `TaskRequested` — extended (additive)

Gains `attemptLimit` (resolved: command override, else capability policy, else contract default) and `retryPolicy` (resolved from the capability manifest). Recording the *resolved* policy at task creation is what makes `tasks.attempt_limit` rebuildable and makes a later change to a capability's defaults unable to retroactively alter a running task's policy.

### 22.9 `CommandAccepted` — extended (additive)

Gains `attemptLimit`. Absent on Step 1 events; the projection falls back to the committed contract default (§20.4).

**Every extension above is additive to a payload.** The Catalog defines no payload shape for any event type (`vocabulary.py`, preserved verbatim: *"PAYLOAD SEMANTICS ARE NOT DEFINED"*), so no committed contract is changed by any of them. Only §22.3 requires approval, and only because the *name* is new.

---

## 23. Exact Transaction Boundaries

The Step 1 protocol is unchanged. Step 2 adds no new transaction shape; it adds statements **inside** existing transactions.

```
_emit(event):
    P1   log.append(envelope)                    ← one os.write(), then os.fsync()   [AUTHORITATIVE]
         ── crash boundary: after_*_append
    P2   BEGIN IMMEDIATE
           index_event(record)                   ← INSERT OR IGNORE event_index
           apply_transition(...)                 ← the guarded UPDATE, which now also carries:
                                                     TaskStarted   → attempt = attempt + 1
                                                     TaskClaimed   → the five lease columns
                                                     TaskRetryScheduled → retry_eligible_at, backoff_ms
                                                     TaskRetryReleased  → clears retry_eligible_at, backoff_ms
                                                     TaskReclaimed      → clears the lease columns
                                                     TaskDeadLettered   → dead_letter_reason
           insert task_attempts row              ← only on TaskSucceeded / TaskFailed
           UPDATE log_cursor
         COMMIT
         ── crash boundary: before_*_apply (kill with the transaction open)
    P3   _project_task(task_id)                  ← cosmetic; failure here never fails the run
```

**Three invariants, each with a named test:**

1. **One event per transaction, never a batch.** `test_no_transaction_applies_more_than_one_event` inspects the source for a loop around `apply_event` inside a transaction.
2. **Every state fact an event implies commits with that event.** A crash between P1 and P2 leaves the index behind; R3 replay converges. A crash *inside* P2 rolls back completely — no half-applied lease, no orphan attempt row. `test_a_kill_inside_the_transaction_leaves_nothing_half_applied` verifies with a real `os._exit`.
3. **No write outside P2.** The lease is never written by a bare UPDATE, the attempt is never incremented outside the transition statement, and both are asserted by source-level tests (§8.3, §14.2).

The retry release, the lease acquisition and the dead-letter transition are each **one** event and therefore **one** transaction. The multi-event sequences (`TaskFailed` → `TaskRetryScheduled`, or `TaskFailed` → `TaskDeadLettered`) are two transactions, and the gap between them is a crash boundary with a defined recovery rule (§24, boundaries 12 and 21).

---

## 24. Crash-Recovery Matrix

Step 1's boundaries 1–11 are unchanged and remain valid. Step 2 adds boundaries **12–21**, each with a real `os._exit(70)` in a child process — no unwinding, no `finally`, no flush.

| # | Crash point | Durable state after | Recovery | Duplicate work? |
|---|---|---|---|---|
| 12 | **after `TaskFailed` append**, before apply | event durable; index behind | R3 replays → `failed`; `run` then decides retry vs dead-letter | no — the decision is made from recorded state |
| 13 | **inside the `TaskFailed` transaction** (kill with it open) | event durable; transaction rolled back | identical to 12 | no |
| 14 | **after `TaskRetryScheduled` append**, before apply | event durable | R3 replays → `retry_scheduled` with `eligibleAt` **copied**, not recomputed | no — a recomputed eligibility would be a new deadline; copying makes the crash invisible |
| 15 | **before the retry projection** (transaction open) | event durable | R3 replays | no |
| 16 | **after `TaskRetryReleased` append**, before apply | event durable | R3 replays → `queued` | no — a second release finds `state != retry_scheduled` and is an anomaly |
| 17 | **after lease claim** (`TaskClaimed` applied), before `TaskStarted` | task `claimed`, lease held by a now-dead run | R4: `owner_gone` → `TaskReclaimed` → `queued`, generation bumped | no — the capability had not run; `attempt` was not incremented |
| 18 | **after lease expiry, before reclaim is appended** | task `claimed`/`running`, lease expired | R4 re-evaluates and reclaims; the predicate is a function of recorded state, so it reaches the same answer | no |
| 19 | **before requeue** (reclaim event durable, transition not applied) | event durable | R3 replays the reclaim | no |
| 20 | **during retry execution** (`running`, attempt n) | task `running`, attempt already incremented | R4 reclaims → `queued` → re-claimed → **attempt n+1** | no *observable* duplicate — the capability is pure. The attempt **is** consumed, which is correct: a crashed attempt was attempted |
| 21 | **after `TaskDeadLettered` append**, before apply | event durable | R3 replays → `dead_lettered`, terminal | no — later arrivals are anomalies |
| 22 | **after final `TaskSucceeded` append**, before apply | event durable | R3 replays → `succeeded`, terminal | no |

**Boundary 20 deserves its own sentence, because it is a design decision rather than a mechanism.** A crash mid-execution consumes an attempt. The alternative — decrementing on reclaim — would let a task that crashes the process on every attempt retry forever, defeating Constitution §11's bounded retry. Consuming the attempt is the fail-closed choice, it is recorded (`task_attempts` shows the attempt with no outcome row, and `TaskReclaimed` records `attempt`), and it is stated here so it is never mistaken for an off-by-one.

**Repeated restart converges.** `test_repeated_restart_converges_to_the_same_terminal_state` runs 5 restarts at randomly-chosen-but-fixed boundaries and asserts the final state, attempt count and result hash are identical to an uninterrupted run.

**Crash-simulation boundary names** added to `--simulate-crash-at`: `after_failure_append`, `inside_failure_transaction`, `after_retry_schedule_append`, `before_retry_projection`, `after_retry_release_append`, `after_lease_claim`, `after_lease_expiry`, `before_requeue`, `during_retry_execution`, `before_dead_letter_apply`, `after_dead_letter_append`. All refused unless `MOGO_RUNTIME_ALLOW_CRASH_SIM=1`, as in Step 1.

---

## 25. CLI and Demonstration Sequence

### 25.1 Subcommands

| Command | Change |
|---|---|
| `init` | registers **two** capabilities; prints effect class and retry policy for each |
| `submit` | unchanged; rejects `attemptLimit > MAX_ATTEMPT_LIMIT` |
| `run` | **new** `--now <iso8601>` (gated by `MOGO_RUNTIME_ALLOW_CLOCK_OVERRIDE=1`); releases eligible retries; drives failed tasks to retry or dead-letter; new crash boundaries |
| `status` | **extended** — attempts, retries scheduled/released, dead letters by reason, failures by error class, leases held and expiring, oldest `retry_scheduled` with its `eligibleAt`, A-5 gate and connector gates |
| `audit` | **extended** — ATTEMPTS, RETRY SCHEDULE, LEASES, DEAD LETTERS sections |
| **`failures`** | **new** — "what failed, when, and why", grouped by error class, with the last event of each. Architecture §23's *Failures* operator view. |
| `verify` | **extended** — no release precedes its eligibility; no attempt recorded twice; lease generations monotonic per task; every terminal task has a terminal event |
| `reset` | unchanged |
| `demo` | **extended** — `--scenario retry \| dead-letter \| all` (default `all`) |

### 25.2 Expected demonstration output

`python3 platform/mogo_runtime.py demo --scenario all`

```
========================================================================
MOGO-011 Step 2 -- retry, lease and dead-letter demonstration
========================================================================
initialized state root : /…/platform/runtime
schema version         : 2
capability CAP|research|runtime-echo               registered  effect=pure
capability CAP|research|runtime-fail-then-succeed  registered  effect=pure  retry=base0ms x2 cap60000ms jitter0ms

-- SCENARIO 1: retryable failure, backoff, release, success on attempt 2 --
  WorkflowStarted            seq=1  indexed only
  CommandAccepted            seq=2  indexed only
  TaskRequested              seq=3  created in requested   attemptLimit=3
  TaskPolicyCheckRequested   seq=4  requested -> policy_check
  PolicyEvaluated            seq=5  policy_check -> queued
  TaskClaimed                seq=6  queued -> claimed       lease gen=1 ttl=30000ms
  TaskStarted                seq=7  claimed -> running      attempt=1
  TaskFailed                 seq=8  running -> failed       errorClass=transient
  TaskRetryScheduled         seq=9  failed -> retry_scheduled  backoff=0ms eligibleAt=…T12:00:00.000Z
  TaskRetryReleased          seq=10 retry_scheduled -> queued  waited=0ms (>= 0ms required)
  TaskClaimed                seq=11 queued -> claimed       lease gen=2 ttl=30000ms
  TaskStarted                seq=12 claimed -> running      attempt=2
  TaskSucceeded              seq=13 running -> succeeded    result=<sha256>
  WorkflowCompleted          seq=14 indexed only
advanced=5 succeeded=1 failed=0 retried=1 deadLettered=0

-- SCENARIO 2: backoff is ENFORCED, not skipped --
  submitted with backoffBaseMs=1000
  run at T+0ms     -> TaskRetryScheduled eligibleAt=T+1000ms
                      RETRY NOT RELEASED: 1000ms remaining   ← the rule bites
  run at T+999ms   -> RETRY NOT RELEASED: 1ms remaining
  run at T+1000ms  -> TaskRetryReleased waited=1000ms        ← released exactly at eligibility

-- SCENARIO 3: attempts exhausted -> dead-letter --
  TaskFailed  attempt=1 transient   TaskRetryScheduled  TaskRetryReleased
  TaskFailed  attempt=2 transient   TaskRetryScheduled  TaskRetryReleased
  TaskFailed  attempt=3 transient
  TaskDeadLettered  reason=attempts_exhausted  attempts=3/3  history=3 entries
advanced=… succeeded=0 failed=1 retried=2 deadLettered=1

-- SCENARIO 4: restart during retry duplicates nothing --
  run --simulate-crash-at during_retry_execution   -> killed (exit 70)
  run                                              -> RECOVERED reclaimed 1 task (owner_gone)
                                                      completed; attempts=3 total, 1 result
-- SCENARIO 5: the log is the truth --
  reset --rebuild-index -> REBUILT from the log alone: 34 events, 21 transitions
  verify                -> INTEGRITY OK
                           no release precedes its eligibility
                           no attempt recorded twice
                           lease generations monotonic

-- OPERATOR VIEW --
failures
  transient                3  last: task 9d0b… attempt 3 at …T12:00:03.100Z
  dead-lettered            1  attempts_exhausted
  A-5 gate                 CLOSED (4 preconditions unmet) -- no effectful capability may register
  connector gates          4 unmet: policy gate, A-5 result store, D-15 authorization, authorization record
```

Scenario 2 is the one that proves Primary Outcome 6. It uses `--now` to move the clock without sleeping, and it shows the release being **refused twice** before being granted — visible enforcement rather than an assertion in a test file.

---

## 26. Operator Audit and Visibility

Constitution §13: *"An operator must be able to answer 'what failed, when, and why' without reading code."* Architecture §23 names the required signals. Mapping, with the gaps from Step 1 closed:

| §23 signal | Step 1 | Step 2 |
|---|---|---|
| task and workflow history | ✅ `audit` | ✅ + attempts |
| queue depth, oldest queued task | ✅ `status` | ✅ + oldest `retry_scheduled` and its `eligibleAt` |
| **retry counts** | ❌ | ✅ `status`, `failures` |
| **failure counts by error class** | ❌ | ✅ `failures` |
| **dead-letter count** | ❌ | ✅ `status`, `failures`, by reason |
| recovery actions | ✅ | ✅ + reclaim reasons |
| policy-block count | ✅ | ✅ |
| **lease visibility** | n/a | ✅ holder, generation, expiry, time remaining |
| worker heartbeat | ❌ | ❌ — no long-running worker exists; deferred honestly |
| connector health, review backlog, provenance, acquisition rate | ❌ | ❌ — no connector, no review gate, no artifact. Deferred, not simulated |

**What `failures` prints** — one screen, no code reading required:

```
FAILURES BY ERROR CLASS
  errorClass              count  retryable  last occurrence          last task
  transient                   3  yes        2026-08-08T12:00:03.100Z 9d0b01cc…
  validation                  1  no         2026-08-08T12:00:04.200Z 1c8760e5…

DEAD LETTERS
  taskId      reason                attempts  finalClass   deadLetteredAt
  4f2a11bc…   attempts_exhausted    3/3       transient    2026-08-08T12:00:03.400Z

ATTEMPT HISTORY  (task 4f2a11bc…)
  attempt  lease  outcome  errorClass  started                   finished
        1      1  failed   transient   …T12:00:00.100Z           …T12:00:00.110Z
        2      2  failed   transient   …T12:00:01.120Z           …T12:00:01.130Z
        3      3  failed   transient   …T12:00:02.140Z           …T12:00:02.150Z

LEASES
  taskId      holder            gen  acquired                 expires                  state
  (none held)

GATES
  A-5 effectful-capability gate   CLOSED   idempotencyKeyedResultStore, outputVerificationByRehash,
                                           duplicateEffectPrevention, postExecutionRecoveryRule
  connector gates                 4 UNMET  policy gate · A-5 result store · D-15 authorization ·
                                           acquisition authorization record
```

Printing the **gates** in an operator view is deliberate. The most important thing an operator can know about this platform is what it is not yet allowed to do, and why.

---

## 27. Exact Files to Create

**7 files.**

| # | Path | Purpose | Est. lines |
|---|---|---|---:|
| 1 | `platform/src/mogo_platform/runtime/clock.py` | `Clock` protocol, `SystemClock`, `ManualClock`, monotonic guard, ISO-8601 parse/format, `elapsed_ms`. **The only module in `platform/**` permitted to read a clock.** | ~140 |
| 2 | `platform/src/mogo_platform/runtime/retry.py` | `resolve_policy`, `is_retryable`, `classify_failure`, `backoff_ms`, `next_eligible_at`, `is_eligible`, `dead_letter_reason`. **Pure functions only** — no connection, no clock, no I/O. | ~190 |
| 3 | `platform/src/mogo_platform/runtime/lease.py` | `lease_expiry`, `is_expired`, `reclaim_reason`, `is_held_by`, `LEASE_TTL_FLOOR_MS`, the CAS clause fragments. **Pure predicates only.** | ~130 |
| 4 | `platform/src/mogo_platform/runtime/capabilities/fail_then_succeed.py` | `research.runtime.fail-then-succeed.v1` — pure, attempt-invariant result | ~110 |
| 5 | `tests/platform/test_runtime_retry.py` | retry policy, backoff, attempt semantics, eligibility | ~330 |
| 6 | `tests/platform/test_runtime_lease.py` | lease acquisition, expiry, reclaim predicate, holder verification | ~300 |
| 7 | `tests/platform/test_runtime_dead_letter.py` | exhaustion, terminal absorption, history, replay | ~280 |

`retry.py` and `lease.py` are separate modules rather than orchestrator methods for one reason: **every decision they make is a pure function of recorded values**, so they can be unit-tested exhaustively without a database, a log, or a process — and mutation-tested precisely. Step 1 established the same split with `task_states.py` (pure) versus `projection.py` (writes).

---

## 28. Exact Files to Modify

**14 files.**

| # | Path | Change |
|---|---|---|
| 1 | `contracts/vocabulary.py` | **+1 event name** `TaskRetryReleased` (39 → 40). **Blocking B-1.** Additive; comment records the authorization and reason, as F-2 did |
| 2 | `runtime/errors.py` | `+CapabilityFailure`, `+ClockRollbackError`, `+EffectClassRefusedError`, `+RetryPolicyError` (13 → 17 classes) |
| 3 | `runtime/schema.py` | `SCHEMA_VERSION = 2`; `_migrate_v2`; `capability_violations` in `APPEND_ONLY_TABLES` |
| 4 | `runtime/projection.py` | 4 transition entries; attempt increment; lease columns; retry columns; `task_attempts` insert; `rebuild()` delete list |
| 5 | `runtime/registry.py` | `effectClass`, `failureClasses`, `requiresExecutionContext`, `retryPolicy`; `A5_EFFECTFUL_GATE`; `CONNECTOR_GATES`; 6 refusal conditions |
| 6 | `runtime/worker.py` | `CapabilityFailure` handling; declared-class validation; execution context |
| 7 | `runtime/orchestrator.py` | retry/dead-letter decision; lease acquire/verify/clear; `run_id`; R1b monotonic check; R4 rewrite; R6 release; 11 crash boundaries; second capability registered |
| 8 | `runtime/audit.py` | attempts, retries, leases, dead letters, failures-by-class, gates; 4 new `verify` checks |
| 9 | `runtime/cli.py` | `failures` subcommand; `--now`; demo scenarios; extended `init`/`status` output |
| 10 | `platform/README.md` | Step 2: retry, lease, dead-letter, clock discipline, A-5 gate, the two-capability table |
| 11 | `tests/platform/test_platform_boundaries.py` | capability purity (clock + randomness); N capabilities not 1; `random`/`secrets` banned; clock reads confined to `clock.py` |
| 12 | `tests/platform/test_platform_envelopes.py` | independently transcribed event list 39 → 40 |
| 13 | `tests/platform/test_runtime_{store_schema,projection,orchestrator,capability,recovery,end_to_end}.py` | extended for v2 schema, new transitions, second capability, new crash boundaries, the 15 outcomes |
| 14 | `tests/run_platform_tests.sh` | 11 → 14 suites |

**Not modified, and each for a stated reason:** `capabilities/echo.py` (pinned by hash, §16.4) · `runtime/paths.py` (confinement already covers every new write) · `runtime/store.py` (pragmas, lock and transaction shape all still correct) · `runtime/event_log.py` (append, fsync, scan, verify, torn-tail need nothing) · `contracts/{ids,errors,command,event,task_states,boundaries}.py` (every needed edge, class and field is already committed) · `tests/run_all.sh` (ADR-012 D-12) · `docs/TESTING.md` · `docs/KNOWN_ISSUES.md` · `regression-baseline*` · `index.html` · `evidence/**` · `docs/campaigns/**` · governance documents · root `.gitignore`.

**`contracts/task_states.py` is not modified.** Verified against the committed contract: every Step 2 edge already exists with the correct authority. This is worth stating explicitly, because a plan that quietly widened the state machine would be the most consequential drift available.

---

## 29. Dependency Decision

**Zero new dependencies. No package manifest. No lock file.**

New stdlib imports introduced by Step 2: none beyond those already used. `clock.py` uses `datetime` (already imported by `orchestrator.py`). `retry.py` and `lease.py` use nothing but built-ins.

**`random` and `secrets` are added to `BANNED_RUNTIME_IMPORTS`**, joining the network and subprocess bans. This is the mechanical half of decision B-2: deterministic backoff is not a convention that could be violated by a future edit, it is an import that will not resolve.

ADR-012 D-01 (manifest) remains deferred: no genuine runtime dependency exists, and Step 2 introduces none. Verified the same way as Step 1 — import roots classified against `sys.stdlib_module_names`, expected result **third-party: 0**.

---

## 30. Test Plan

Named tests for every requirement. **Target: ~150 new tests, 450 → ~600.**

### 30.1 Retry policy — `test_runtime_retry.py`

| Requirement | Test |
|---|---|
| retryable error schedules retry | `test_a_retryable_failure_schedules_a_retry` |
| non-retryable does not | `test_a_non_retryable_failure_does_not_schedule_a_retry` |
| policy denial never retries | `test_policy_blocked_never_retries` + `test_policy_denial_is_refused_even_if_the_table_says_retryable` |
| unknown classification fails closed | `test_an_unknown_error_class_is_not_retryable` |
| max attempt limit enforced | `test_the_attempt_limit_is_enforced_exactly` (limit 1, 2, 3, 10) |
| attempt increments once per execution | `test_attempt_increments_exactly_once_per_execution` |
| duplicate replay does not increment | `test_replaying_task_started_does_not_increment_the_attempt` |
| retry event ordering exact | `test_retry_event_ordering_is_exact` |
| reconstructable from the log | `test_retry_scheduling_is_reconstructable_from_the_log_alone` |
| deterministic backoff | `test_backoff_is_identical_for_identical_inputs` (1000 iterations) · `test_backoff_matches_the_independently_transcribed_table` |
| no jitter unless governed | `test_jitter_is_zero_and_no_randomness_is_importable` |
| no retry before eligibility | `test_a_retry_is_not_released_before_its_eligibility` |
| retry occurs at eligibility | `test_a_retry_is_released_exactly_at_eligibility` (equal, ±1 ms) |
| restart during scheduling converges | `test_restart_during_retry_scheduling_converges` |
| every §K class disposition | `test_every_error_class_reaches_the_expected_terminal_state` (13 cases) |
| no floating point | `test_backoff_uses_integer_arithmetic_only` |
| key stable across attempts | `test_idempotency_key_is_identical_across_every_attempt` |
| context excluded from key | `test_the_execution_context_is_not_part_of_the_idempotency_key` |
| one increment site | `test_attempt_is_written_by_exactly_one_sql_statement_in_the_runtime` |
| `run_once` terminates | `test_run_once_terminates_with_zero_backoff_and_a_high_attempt_limit` |
| ceiling enforced | `test_an_attempt_limit_above_the_ceiling_is_rejected` |
| SQL and Python agree | `test_iso8601_lexical_order_matches_chronological_order` |

### 30.2 Dead-letter — `test_runtime_dead_letter.py`

`test_an_exhausted_retryable_task_becomes_dead_lettered` · `test_a_non_retryable_failure_follows_the_approved_terminal_path` · `test_the_dead_letter_transition_is_event_backed` · `test_a_dead_lettered_task_is_never_dispatched_again` · `test_the_dead_letter_audit_contains_all_attempts_and_causes` · `test_dead_letter_history_matches_the_history_re_derived_from_the_log` · `test_rebuild_reproduces_dead_letter_state_exactly` · `test_a_late_success_after_dead_letter_is_an_anomaly_not_applied` · `test_no_transition_out_of_dead_lettered_is_legal` · `test_the_five_dead_letter_reasons_are_each_reachable`

### 30.3 Leases — `test_runtime_lease.py`

`test_lease_acquisition_is_atomic` · `test_only_an_eligible_queued_task_can_be_leased` · `test_a_second_claimant_fails` · `test_an_expired_lease_is_reclaimed` · `test_a_live_lease_is_not_reclaimed_prematurely` · `test_a_lease_from_a_previous_run_is_reclaimed` · `test_a_claimed_task_with_no_lease_is_reclaimed` · `test_restart_recovers_an_expired_lease` · `test_the_lease_owner_is_auditable` · `test_lease_timestamps_are_canonical_utc` · `test_a_backward_clock_is_refused_before_any_append` · `test_lease_replay_is_idempotent` · `test_task_state_and_lease_projection_remain_consistent` · `test_a_result_is_refused_when_the_lease_generation_changed_mid_execution` · `test_lease_generation_is_monotonic_per_task` · `test_lease_columns_are_written_by_exactly_one_sql_statement`

### 30.4 Capabilities — extends `test_runtime_capability.py`

`test_the_second_capability_is_registered` · `test_its_failure_behaviour_is_deterministic` (100 runs) · `test_its_success_behaviour_is_deterministic` · `test_the_success_result_is_identical_for_every_attempt_that_succeeds` · `test_always_fail_mode_reaches_dead_letter_deterministically` · `test_effect_classification_is_enforced` · `test_registering_an_effectful_capability_is_refused_and_names_every_missing_precondition` · `test_every_a5_gate_precondition_is_false_in_this_build` · `test_a_pure_capability_remains_safe_at_crash_boundary_8` · `test_the_echo_capability_module_is_byte_identical_to_the_committed_version` · `test_the_echo_manifest_hash_is_unchanged` · `test_the_echo_result_hash_is_unchanged` · `test_an_undeclared_failure_class_is_a_violation_and_is_not_retryable` · `test_a_review_routing_failure_class_is_refused_at_registration`

### 30.5 Recovery — extends `test_runtime_recovery.py`

One test per new crash boundary 12–22, each spawning a child that `os._exit(70)`s: `test_boundary_12_crash_after_failure_append` … `test_boundary_22_crash_after_final_success_append`. Plus `test_repeated_restart_converges_to_the_same_terminal_state` · `test_no_boundary_produces_a_duplicate_attempt_or_duplicate_result` · `test_a_kill_inside_the_transaction_leaves_nothing_half_applied` · `test_recovery_never_releases_a_retry`.

### 30.6 Schema and migration — extends `test_runtime_store_schema.py`

`test_a_step_1_state_root_upgrades_and_replays_correctly` · `test_a_v1_log_rebuilds_into_a_v2_schema` · `test_a_future_schema_is_refused_without_modifying_the_database` · `test_migrations_are_ordered_contiguous_and_start_at_one` · `test_task_attempts_rejects_a_duplicate_attempt_number` · `test_append_only_triggers_cover_capability_violations` · `test_rebuild_reproduces_every_step_2_column_exactly`

### 30.7 End-to-end — extends `test_runtime_end_to_end.py`

One test per Primary Outcome 1–15: `test_primary_outcome_01_…` … `test_primary_outcome_15_…`, plus `test_no_release_precedes_its_eligibility_when_re_derived_from_the_log`.

### 30.8 Regression and protection — extends `test_platform_boundaries.py`

`test_all_step_1_tests_remain_passing` (the suite itself) · `test_campaign_c1_manifest_is_unchanged` · `test_protected_function_drift_is_zero` · `test_no_network_import_anywhere` · `test_no_subprocess_anywhere` · `test_no_scientific_write_is_expressible` · `test_no_connector_path_exists` · `test_no_trading_path_exists` · `test_runtime_writes_remain_confined` · `test_contracts_remain_io_free` · `test_runtime_state_root_is_git_ignored` · **`test_no_random_or_secrets_import_anywhere`** · **`test_clock_is_read_only_in_clock_py`** · **`test_capability_modules_read_no_clock_and_no_randomness`** · **`test_the_runtime_registers_exactly_two_capabilities`** (replaces the Step 1 "exactly one", with per-capability assertions on connectors, secrets, operation class and effect class).

---

## 31. Mutation-Test Plan

All 18 required mutations, each with the specific test that detects it. Protocol as Step 1: apply to committed source, **purge all bytecode**, run the full suite, revert, re-verify the file hash.

| # | Mutation | Detected by |
|---|---|---|
| 1 | mark policy denial retryable | `test_policy_blocked_never_retries` **and** `test_policy_denial_is_refused_even_if_the_table_says_retryable` |
| 2 | remove maximum-attempt enforcement | `test_the_attempt_limit_is_enforced_exactly`, `test_an_exhausted_retryable_task_becomes_dead_lettered` |
| 3 | fail to increment attempt count | `test_attempt_increments_exactly_once_per_execution` |
| 4 | increment attempt count twice | `test_attempt_increments_exactly_once_per_execution` **and** `test_task_attempts_rejects_a_duplicate_attempt_number` (UNIQUE constraint) |
| 5 | remove retry eligibility enforcement | `test_a_retry_is_not_released_before_its_eligibility` **and** `test_no_release_precedes_its_eligibility_when_re_derived_from_the_log` |
| 6 | change deterministic backoff output | `test_backoff_matches_the_independently_transcribed_table` |
| 7 | add random jitter | `test_no_random_or_secrets_import_anywhere` **and** `test_backoff_is_identical_for_identical_inputs` |
| 8 | allow a non-expired lease to be stolen | `test_a_live_lease_is_not_reclaimed_prematurely` |
| 9 | remove lease-owner verification | `test_a_result_is_refused_when_the_lease_generation_changed_mid_execution` |
| 10 | skip expired-lease recovery | `test_an_expired_lease_is_reclaimed`, `test_restart_recovers_an_expired_lease` |
| 11 | allow dead-lettered task to execute | `test_a_dead_lettered_task_is_never_dispatched_again` |
| 12 | make dead-letter transition SQLite-only | `test_the_dead_letter_transition_is_event_backed`, `test_rebuild_reproduces_dead_letter_state_exactly` |
| 13 | remove an event append before a state change | `test_rebuild_reproduces_every_step_2_column_exactly` (the state would not survive a rebuild) |
| 14 | register an effectful capability without the A-5 gate | `test_registering_an_effectful_capability_is_refused_and_names_every_missing_precondition` |
| 15 | treat unknown error classification as retryable | `test_an_unknown_error_class_is_not_retryable` |
| 16 | corrupt schema migration ordering | `test_migrations_are_ordered_contiguous_and_start_at_one`, `test_a_step_1_state_root_upgrades_and_replays_correctly` |
| 17 | allow replay to duplicate retry events | `test_lease_replay_is_idempotent`, `test_replaying_task_started_does_not_increment_the_attempt` |
| 18 | permit worker code to transition task state directly | `test_the_worker_receives_no_connection_and_no_log` (source-level), `test_only_the_orchestrator_appends_events` |

**Six additional mutations proposed beyond the required 18**, because each targets a Step 2 decision that would otherwise rest on a single test:

| # | Mutation | Detected by |
|---|---|---|
| 19 | accept a backward clock (remove the monotonic guard) | `test_a_backward_clock_is_refused_before_any_append` |
| 20 | recompute `eligibleAt` during projection instead of copying | `test_rebuild_reproduces_every_step_2_column_exactly` |
| 21 | default an absent `effectClass` to `effectful` | `test_effect_classification_is_enforced` |
| 22 | drop the `UNIQUE (task_id, attempt)` constraint | `test_task_attempts_rejects_a_duplicate_attempt_number` |
| 23 | let `run_once` select ineligible `retry_scheduled` tasks | `test_run_once_terminates_with_zero_backoff_and_a_high_attempt_limit` (hangs → fails) |
| 24 | reset `lease_generation` on reclaim | `test_lease_generation_is_monotonic_per_task` |

**Target: 24/24 detected, 24/24 reverted.** A mutation that survives is a genuine test gap and is closed with a new test before implementation is reported complete — the Step 1 protocol, which found three real gaps.

---

## 32. Protected-Boundary Verification

Unchanged from Step 1 in substance; extended in coverage.

| Boundary | Verification |
|---|---|
| `platform/**` → `evidence/` | AST scan: no prohibited literal outside `boundaries.py`; no write call with a prohibited argument |
| `platform/**` → `docs/campaigns/` | same |
| `platform/**` → `PREREG-*.md` | same |
| `platform/**` → `MOGO-003-VERIFIED-REPLAY-RECORD.md` | same |
| `platform/**` → `index.html` | same |
| `platform/**` → `hypothesis-registry.json` | same |
| `platform/**` → `scripts/trader_intelligence/` | import scan |
| network / subprocess | import scan, `REQUIRED_BANNED_IMPORTS` |
| **randomness** | **new** — `random`, `secrets` banned |
| **clock** | **new** — `datetime.now` / `time.time` / `time.monotonic` only in `clock.py` |
| runtime write confinement | every write site calls `assert_inside_state_root` |
| contracts I/O-free | no `open` at all in `contracts/**` |
| capability purity | **extended** — no I/O, no clock, no randomness in `capabilities/**` |
| runtime state git-ignored | `git check-ignore` on the database, log, tasks and quarantine |

**Campaign C1 (33/33) and protected-function drift (0)** are verified before *and* after implementation, and again before commit — the Step 1 protocol.

---

## 33. Validation Commands

Exact sequence, to be run in this order and reported verbatim.

```
 1  find . -name '__pycache__' -type d -prune -exec rm -rf {} +
 2  python3 -m compileall -q platform tests/platform
 3  python3 -W error  (import all 7 contracts + 16 runtime modules; print stdlib platform, event count)
 4  bash tests/run_platform_tests.sh                              → 14 suites, ~600 tests, 0/0/0
 5  MOGO_RUNTIME_STATE_ROOT=$TMP python3 platform/mogo_runtime.py demo --scenario all
 6  … run --simulate-crash-at during_retry_execution ; run        → recovered, no duplicate
 7  … run --simulate-crash-at before_dead_letter_apply ; run      → recovered, dead-lettered once
 8  … reset --rebuild-index ; verify                              → REBUILT; INTEGRITY OK
 9  … failures                                                     → grouped by class; gates CLOSED
10  bash tests/run_all.sh                                         → 17 suites, 947/947, 0 failed
11  python3 regression-baseline-tools.py                          → No drift: 63 fn, 4 const
12  Campaign C1 manifest verification                             → 33/33, 0/0/0
13  AST no-write-path over platform/**                            → 0 write-capable calls
14  AST no-network / no-subprocess / no-random / no-clock         → 0 / 0 / 0 / 1 (clock.py only)
15  sys.stdlib_module_names dependency check                      → third-party: 0
16  Step 1 state root upgrade v1 → v2 ; verify                    → migrated; INTEGRITY OK
17  git check-ignore on database, log, tasks/, quarantine/        → all ignored
18  mutation run: 24 mutations, bytecode purged between each      → 24/24 detected, 24/24 reverted
19  pre-existing Python suites                                    → the same 6 failures, unchanged
```

Every run uses a scratch `MOGO_RUNTIME_STATE_ROOT`, never the repository's own `platform/runtime/`. Every unit test uses `tempfile.TemporaryDirectory()`.

---

## 34. Rollback Strategy

**Before commit** — nothing is staged; delete the created files and `git checkout --` the modified ones:

```bash
rm -f platform/src/mogo_platform/runtime/{clock,retry,lease}.py \
      platform/src/mogo_platform/runtime/capabilities/fail_then_succeed.py \
      tests/platform/test_runtime_{retry,lease,dead_letter}.py
git checkout -- platform/README.md \
      platform/src/mogo_platform/contracts/vocabulary.py \
      platform/src/mogo_platform/runtime/{errors,schema,projection,registry,worker,orchestrator,audit,cli}.py \
      tests/platform/test_platform_{boundaries,envelopes}.py \
      tests/platform/test_runtime_{store_schema,projection,orchestrator,capability,recovery,end_to_end}.py \
      tests/run_platform_tests.sh
git status --porcelain            # expect: only the untracked report documents
```

**After commit, before push:**

```bash
git reset --hard c50f95ca839fd41f75e56f93997d82928261f0b3
```

**After push** — never rewrite published history:

```bash
git revert --no-edit <step-2-commit>
git push origin HEAD:mogo-main
```

**Runtime state rollback** — the reason no down-migration is needed (§20.3). The index is derived; the correct reversal is to discard and rebuild:

```bash
python3 platform/mogo_runtime.py reset --confirm          # delete the whole state root
# or, keeping the authoritative log:
rm -f platform/runtime/index/runtime.sqlite3
python3 platform/mogo_runtime.py init                     # recreate at the checked-out build's version
python3 platform/mogo_runtime.py reset --rebuild-index    # rebuild from the log alone
```

**Nothing in Step 2 can require a rollback of anything protected.** No protected function, no Campaign C1 artifact, no evidence file, no governance document and no scientific record is written, so there is nothing to restore.

---

## 35. Proposed Commit Boundary

**21 files — 7 created, 14 modified.** One commit, parent `c50f95ca839fd41f75e56f93997d82928261f0b3`.

Enumerated exactly in §27 and §28. Staged by explicit path; never `git add .`, `-A` or `--all`.

**Excluded:** all 14 MOGO report documents (including this plan) · the 4 legacy documents · `tests/run_all.sh` · `docs/TESTING.md` · `docs/KNOWN_ISSUES.md` · `regression-baseline*` · `index.html` · `evidence/**` · `docs/campaigns/**` · governance documents · root `.gitignore` · any package manifest or lock file · all runtime state except the already-committed `platform/runtime/.gitignore`.

**A two-commit split is available if the Release Gate prefers it**, and the seam is clean: commit A = `clock.py` + `retry.py` + `lease.py` + `schema.py` v2 + their three test suites (pure decision logic and persistence, no behaviour change); commit B = orchestrator, worker, registry, audit, cli, the second capability and the end-to-end suites. Commit A is independently green, which is what makes the split honest rather than cosmetic.

---

## 36. Risks and Ambiguities

| # | Risk | Severity | Disposition |
|---|---|---|---|
| **B-1** | **New event name `TaskRetryReleased`** | **Blocking** | **Operator approval required before implementation.** No alternative preserves ADR-012 D-05 (§6.2) |
| **B-2** | **`jitterMs = 0` vs Architecture §19 "backoff with jitter"** | **Medium** | Disclosed deviation. Field retained and governed; randomness structurally unimportable; deterministic jitter named as the future extension (§9.3). **Acknowledgment requested** |
| **B-3** | **Review-routing classes dead-lettered, not routed** | **Medium** | `failed → awaiting_review` does not exist in the committed contract. Prohibited at registration; fail-closed dead-letter at runtime (§7.4). **Acknowledgment requested** |
| **B-4** | **Risk A-5 resolved as Option A** | **High** | Determination required by the tasking. Enforced by a gate whose preconditions are data, all `False` (§17). **Ratification requested** |
| **B-5** | **`MAX_ATTEMPT_LIMIT = 10` runtime ceiling** | **Low** | Catalog §A sets no upper bound; Constitution §11 requires bounded retry. Auditable rejection (§8.4). **Acknowledgment requested** |
| C-1 | A capability could declare `pure` while being effectful | Medium | The **static** scan is the enforcement, not the declaration (§18.1). A lying manifest is caught by the AST test, which applies unconditionally |
| C-2 | Wall-clock dependence is new to the platform | Medium | Confined to one module; injected everywhere; monotonic guard fails closed; no time value ever recomputed on replay (§10) |
| C-3 | Boundary 20 consumes an attempt on a mid-execution crash | Low | Deliberate and stated (§24). The alternative permits unbounded retry |
| C-4 | Lease is genuinely useful but not load-bearing for exclusion | Low | Answered directly (§13.1). It does two jobs `flock` cannot; if it did none, it would be deferred |
| C-5 | `capabilities` and `runs` tables are not replayable | Low | Named honestly (§19.4) rather than papered over. Capability-lifecycle events deferred with the lifecycle transitions that would emit them |
| C-6 | Schema v2 sets migration precedent for the repository's first database | Medium | Additive `ALTER TABLE` only; one transaction; no down-migration by design; rebuild is the reversal |
| C-7 | ~600 tests is a large suite to keep fast | Low | All offline, all `tempfile`; Step 1's 450 run in seconds |
| **A-5** | **Carried unchanged from Step 1** | **High** | §17, §37 — preserved verbatim, unweakened |
| A-3, A-4, A-6, A-7, A-8 | Carried from Step 1 | Low–Medium | §37 |

---

## 37. Carried Items

**Risk A-5 — carried into Step 3 verbatim and unweakened:**

> **Crash boundary 8 — interrupted between execution and recording success — is safe ONLY because the capability is pure.** Re-execution after an interrupted run produces a byte-identical result, so it is indistinguishable from never having been interrupted. **That is a property of *this capability*, not of the kernel.** The moment a capability performs an external effect, this argument fails. An effectful capability requires output verification and an idempotency-keyed result store **before** it may be registered. This is a hard gate on Step 2, on the first connector, and on any future autonomous agent that acquires, writes, or calls out.

Step 2 makes the prohibition **mechanical** rather than documentary. It does not reduce the hazard.

**Also carried, unchanged from Step 1:** A-3 torn-tail truncation is the one place the log shortens · A-4 no approved event names a quarantined fragment · A-6 `fcntl` is POSIX-only · A-7 `targetCapability` canonical-form ambiguity · A-8 the first database sets schema precedent · `fsync` is asserted structurally only, an inherent limit of in-process testing.

**Deferred inside MOGO-011, with the condition that triggers each:**

| Deferred | Becomes necessary when |
|---|---|
| Lease renewal / heartbeat | any execution can exceed `leaseTtlMs / 2` — a long-running acquisition, an out-of-process worker, or a daemon |
| Deterministic jitter | a concurrent claimer exists |
| Capability-lifecycle events | a capability actually changes lifecycle state |
| `awaiting_review` routing | the review gate exists |
| Worker heartbeat and health | a worker outlives a single `run` |
| Cancellation (`any non-terminal → cancelled`) | an operator needs to stop a task; Catalog §L already permits it |
| Output verification, result store, duplicate-effect prevention | **the A-5 gate — before any effectful capability** |

**Deferred to later milestones:** the **policy gate** (Architecture §32 item 5 — required before **any** connector) · filesystem/operator-drop connector (D-15) · raw artifact registry · ingestion adapter · GitHub connector · YouTube (explicitly deferred).

**Repository-wide, unchanged:** package manifest (D-01) · canonical runner integration (D-12) · disposition of the four legacy documents · the six pre-existing Python failures · `push.default` / branch-naming policy.

---

## 38. Architecture Drift Check

Every Step 2 decision checked against the governing documents. **Three deviations, all disclosed; nothing silent.**

| Rule | Source | Step 2 | Verdict |
|---|---|---|---|
| Event log authoritative, state derived | ADR-012 D-05 | every new column copied from a payload; §19 proves it column by column | ✅ preserved |
| Every transition is an event before a state | Architecture §18.1 | drives the F-1 requirement | ✅ preserved |
| Only the orchestrator writes task state | Constitution §7 | worker still receives no connection | ✅ preserved |
| Workers never call workers | Constitution §4.4 | one callable, no dispatch | ✅ preserved |
| Retry bounded with backoff | Constitution §11 | `attemptLimit` + ceiling + exponential backoff | ✅ preserved |
| **Backoff with jitter** | **Architecture §19, §18.1, §26** | **`jitterMs = 0`; field retained and governed** | ⚠️ **DEVIATION — B-2, disclosed §9.3** |
| `policy_blocked` never retried | Constitution §11 | two independent guards | ✅ strengthened |
| Recovery from a **verified** checkpoint | Constitution §11 | lease predicate replaces Step 1's assumption | ✅ strengthened |
| Stale claims reclaimed on lease expiry | Constitution §11 | §15 | ✅ implemented |
| Dead-letters visible, not archived | Constitution §11 | `status`, `audit`, `failures` | ✅ implemented |
| Failures and retries remain visible | Constitution §4.18 | every one is an event | ✅ preserved |
| Every task reaches a terminal outcome | Constitution §6.5 | closes the Step 1 gap | ✅ **fixed** |
| Keys never from timestamps or attempts | Constitution §11 | §8.5, two tests | ✅ preserved |
| Operator answers what/when/why without code | Constitution §13 | `failures` subcommand | ✅ implemented |
| Only the lease holder writes results | Architecture §24 | §14.5, enforced | ✅ implemented |
| CAS on `(taskId, leaseGeneration)` | Architecture §18.1 | adopted verbatim | ✅ preserved |
| Dispatch only to enabled, compatible capability | Catalog §O, ADR-012 D-16 | unchanged, plus the A-5 gate | ✅ strengthened |
| **`failed → awaiting_review`** | **Catalog §L — does not exist** | **two §K classes dead-letter instead** | ⚠️ **GAP — B-3, disclosed §7.4** |
| **Catalog §K classes all handled** | **Catalog §K** | **`source_mutated`, `human_review_required` prohibited at registration** | ⚠️ **NARROWING — B-3, disclosed §7.4** |
| Policy gate before any connector | Architecture §32 item 5 | no connector; gate table printed | ✅ preserved |
| Additive-only schema evolution | ADR-012 D-11, Architecture §11 | 1 new event name, payload extensions only, `ALTER TABLE ADD` only | ✅ preserved |
| Zero third-party dependencies | ADR-012 D-01 | 0 | ✅ preserved |
| No write to protected paths | Architecture §7, Constitution §4.22 | confinement rule unchanged | ✅ preserved |
| Frozen campaigns immutable | Constitution §4.16 | C1 untouched; verified before and after | ✅ preserved |

**Task-state machine: zero drift.** `contracts/task_states.py` is not modified. Every Step 2 edge already exists in the committed contract with the correct authority — verified programmatically, not assumed.

---

## 39. MOGO-011 Progress Forecast

| Step | Scope | Status |
|---|---|---|
| **Step 1** | runtime kernel, durable task, events, crash recovery, one pure capability | ✅ **complete, committed `c50f95c`, pushed** |
| **Step 2** | retry, bounded attempts, deterministic backoff, dead-letter, leases, expired-lease recovery, second capability, failure observability, A-5 resolution | **this plan — awaiting 5 decisions** |
| Step 3 *(anticipated, not authorized)* | the **policy gate** — classification, Acquisition Authorization Records, enforcement tests | required before any connector |
| Step 4 *(anticipated)* | A-5 result store: idempotency-keyed results, output verification by re-hash, duplicate-effect prevention | required before any effectful capability |
| Step 5 *(anticipated)* | filesystem / operator-drop connector with fixtures, no network (D-15) | the first acquisition |

After Step 2, MOGO-011's original mandate — *"a dependable failure-handling execution platform"* — is met. What remains before the platform can do anything **outward-facing** is two gates, in this order: the **policy gate** (Architecture §32 item 5) and the **A-5 result store**. Neither is in Step 2, and Step 2 makes both mechanically unavoidable rather than merely documented.

**Estimated Step 2 shape:** ~21 files · ~1,700 lines of runtime source added · ~1,300 lines of test source added · 450 → ~600 tests · 24 mutations · zero new dependencies.

---

## 40. Final Recommendation

**Build Step 2 as specified, after five decisions.**

The design is smaller than Step 1 because MOGO-010 and Step 1 did the hard part correctly: every task-state edge Step 2 needs is already committed with the right authority, the error table is already committed with the right retryability, and the guarded UPDATE is already the exactly-once primitive that attempt counting and lease acquisition require. Step 2 is mostly wiring, and the parts that are not wiring are the three worth thinking about — the clock discipline (§10), the lease earning its keep (§13.1), and the A-5 gate that cannot be opened by accident (§17.3).

**Five decisions, one blocking:**

| | Decision | Type |
|---|---|---|
| **B-1** | Approve the additive event name **`TaskRetryReleased`** (39 → 40) | **BLOCKING — implementation cannot begin** |
| **B-2** | Acknowledge **`jitterMs = 0`**, deviating from Architecture §19's "backoff with jitter", with the field retained and randomness structurally unimportable | acknowledgment |
| **B-3** | Acknowledge that **`source_mutated` and `human_review_required` are prohibited at registration and dead-lettered at runtime**, because `failed → awaiting_review` does not exist and no review gate does either | acknowledgment |
| **B-4** | Ratify **Risk A-5 = Option A** — pure capabilities only, effectful registration mechanically prohibited | ratification |
| **B-5** | Acknowledge **`MAX_ATTEMPT_LIMIT = 10`** as a runtime ceiling on a Catalog-unbounded field | acknowledgment |

B-1 is blocking for the same reason F-2 was in Step 1: a closed, governed vocabulary cannot be extended by the implementer. Without it, `retry_scheduled → queued` has no event, task state stops being derivable from the log, and ADR-012 D-05 breaks. There is no viable alternative, which is why none is offered.

The other four are not blocking in the sense that a defensible default exists for each — but each decides how a governed rule is applied, and recording an operator decision costs less now than discovering an unrecorded assumption in Step 4.

Nothing has been implemented, staged, committed, tagged or pushed. The baseline is unchanged and verified.

**NOT READY — STEP 2 ARCHITECTURE OR GOVERNANCE DECISION REQUIRED**

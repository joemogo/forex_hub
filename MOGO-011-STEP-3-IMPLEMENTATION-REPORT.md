# MOGO-011 STEP 3 — IMPLEMENTATION REPORT

**Milestone:** MOGO-011 Step 3 — the Policy Gate (the authorization layer)
**Baseline:** `7b2c0aa940d185995305e45a209edf063050e10b` (`origin/mogo-main`)
**Governance:** all five decisions recorded in `MOGO-011-STEP-3-GOVERNANCE-RECORD.md` (C-1 … C-5)
**Status:** **implemented and validated — nothing staged, committed, tagged or pushed**
**Date:** 2026-08-08

---

## 1. Executive summary

The Policy Gate is built. No work executes without passing through it, and the decision it makes is
explicit, auditable, deterministic, reproducible, fail-closed, and structurally impossible to bypass.

**21 files: 6 created, 15 modified.** 622 → **740 tests**, 14 → **17 suites**, all passing.
Canonical gate 947/947. Campaign C1 33/33. Protected-function drift 0. Zero new dependencies.
**Zero vocabulary extension** — no new event name, no new command, no new state, and
`contracts/vocabulary.py` and `contracts/task_states.py` are both untouched.

**The most consequential change is a correction, not a feature.** Finding F-1 from the plan is fixed:
the committed runtime was recording an audit trail that stated the opposite of what happened.

---

## 2. The finding this step existed to fix

Before Step 3, an acquisition-class task produced:

```json
PolicyEvaluated {"decision": "not_applicable", "operationClass": null, "reason": "routed to failure"}
```
then `TaskClaimed` → `TaskStarted` → `TaskFailed` → `TaskDeadLettered`.

Three statements were false: the gate had not found the policy inapplicable (it refused because no
gate existed); the operation class was `acquisition`, recorded as `null`; and the claim and start
events asserted an execution **that never occurred**.

**Now:**

```json
PolicyEvaluated {"decision": "deny", "reason": "no_authorization_record",
                 "operationClass": "acquisition", "subjectSourceId": "SRC|…",
                 "policyStatus": …, "policyVersion": …, "decisionAuthority": …,
                 "authorizationRecordHash": …}
```
then `AcquisitionDenied` → `HumanReviewRequired`, and **nothing else**. No claim, no start, no
attempt row, `attempt` stays 0.

`TestTheAuditTrailIsTrue` is the regression class that keeps it fixed, and
`test_a_denied_task_emits_no_claim_and_no_start` is its sharpest assertion.

---

## 3. What was built

| Requirement | How it is met |
|---|---|
| **Explicit** | every decision is one `PolicyEvaluated` event carrying decision, reason, class, operations, subject, authorization, status, version, authority and record hash |
| **Auditable** | Constitution §4.20's *who, what, when, why, under which policy version* — each a named payload field, asserted field by field |
| **Deterministic** | `policy.evaluate` is pure: no clock, no connection, no I/O; 1,000-iteration determinism test |
| **Reproducible** | replay re-applies the recorded decision and never re-derives it — a spy asserts `evaluate` is **never called** during `rebuild()` |
| **Fail closed** | deny is reached by 12 distinct routes; a permit only by satisfying every rung |
| **Impossible to bypass** | six independent mechanisms, §5 |

**Three previously unreachable approved states are now used**: `blocked`, `awaiting_review`,
`suppressed`.

---

## 4. The decision, and the two traps in the Catalog

`policy.evaluate(operation_class, requested_operations, authorization, now_ms, resolution_problem)`
— pure, one call ladder, deny by default.

Two places where a careless reading of Catalog §M would have produced a permissive gate:

**`AS_RECORDED` is not an allowance.** `PERMITTED_EXPLICIT_LICENSE` and
`PERMITTED_DOCUMENTED_POLICY` mark *every* operation `AS_RECORDED`, which means "whatever the licence
says". Treating that as permission would have turned the two most nuanced statuses into the most
permissive ones. The gate requires the record to reference the licence (Architecture §20.1) and
denies otherwise.

**`discover` is governed exactly as `metadata`.** Catalog §M has no `discover` column, and the
tempting reading is that discovery is therefore unconstrained. Architecture §20.2 is explicit that
the minimum-metadata allowance exists *only before a classification is recorded* and "expires the
instant one is recorded" — a laxer rule for discovery afterwards would be precisely the drip-feed
loophole §20.2 closes.

**`UNKNOWN` gets two independent guards**, as Constitution §5.2 states its rule absolutely: the
committed table's `permitsAcquisition: False`, and a check made *before* the table is consulted. A
test monkeypatches the table to claim UNKNOWN permits acquisition and asserts the decision still
refuses.

---

## 5. Bypass impossibility — six mechanisms

| # | Mechanism | Test |
|---|---|---|
| 1 | `requested → queued` is not a legal Catalog §L edge | `test_requested_to_queued_is_not_a_legal_edge` |
| 2 | `policy_check` is the only entry to `queued` for a new task | `test_policy_check_is_the_only_entry_to_queued` |
| 3 | The decision has exactly two **named** call sites | `test_the_gate_is_called_only_from_the_two_authorized_places` |
| 4 | No other runtime module may consult the gate | `test_no_other_runtime_module_consults_the_gate` |
| 5 | No override argument, no environment variable | `test_the_gate_accepts_no_override_argument`, `test_no_environment_variable_can_permit` |
| 6 | Dispatch re-checks the recorded permit before claiming | `test_dispatch_refuses_an_acquisition_task_without_a_recorded_permit` |

Mechanism 3 asserts the call sites **by name** rather than by count, so a future edit consulting the
gate from a dispatch path or a CLI handler fails even though a count would still look plausible.

---

## 6. The disposition path (C-1)

```
policy_check --deny--> blocked --> awaiting_review --audited operator decision--> queued | suppressed
```

`legal_successors("blocked")` is `('awaiting_review', 'cancelled')` — there is no `blocked → queued`
and no `blocked → suppressed`, so the decision acts on `awaiting_review` under `review_gate`
authority, exactly as Option D specified.

**A human may un-block a task; only the gate may authorize the acquisition.** This is the design
point that emerged during implementation and it is the one worth reading twice. An approval
**re-evaluates the gate** and is refused while it still denies, so a reviewer can never stand in for
an Acquisition Authorization Record (Constitution §5.1). The permit that later allows dispatch is
the *gate's*, recorded with the governance authority and policy version — never the reviewer's
say-so.

Constitution §9 is enforced rather than documented: reviewer identity, decision, **reason**,
timestamp and policy version are all required; a bare approval is refused; and a worker or
capability naming itself as reviewer is refused (Catalog §N — no worker approves its own governed
output).

---

## 7. Files

### Created — 6

| Path | Lines | Purpose |
|---|---:|---|
| `runtime/policy.py` | 329 | the authorization decision — pure functions only |
| `runtime/authorizations.py` | 340 | Acquisition Authorization Records: validation, append-only store, supersession, resolution |
| `runtime/capabilities/policy_probe.py` | 112 | `research.policy.probe.v1` — acquisition-class, acquires nothing (C-2) |
| `tests/platform/test_runtime_policy_gate.py` | 758 (53 tests) | classification, the ladder, F-1 regression, bypass, replay |
| `tests/platform/test_runtime_authorization.py` | 316 (29 tests) | record shape, authority, storage, supersession, hashing |
| `tests/platform/test_runtime_review_disposition.py` | 370 (22 tests) | the audited operator decision and its refusals |

### Modified — 15

`runtime/{errors,schema,projection,registry,orchestrator,audit,cli}.py` · `platform/README.md` ·
`tests/platform/test_{platform_boundaries,runtime_capability,runtime_end_to_end,runtime_projection,runtime_store_schema,runtime_recovery}.py`
· `tests/run_platform_tests.sh`.

`test_runtime_recovery.py` gains **crash boundaries 23–26** across the authorization layer, added
after the first implementation report flagged them as argued rather than tested.

**Not modified, each for a stated reason:** **`contracts/vocabulary.py`** (no new name needed) ·
**`contracts/task_states.py`** (every state and edge already approved) ·
`contracts/{ids,errors,command,event,boundaries}.py` · `capabilities/echo.py` and
`capabilities/fail_then_succeed.py` (pinned by hash) ·
`runtime/{paths,store,event_log,clock,retry,lease,worker}.py` · `tests/run_all.sh` (ADR-012 D-12) ·
all protected paths.

**Schema v3**, additive only: 10 task columns, `commands.input_refs_json`,
`capabilities.acquisition_operations`, and two new tables —
`acquisition_authorizations` (append-only, governance input, **not replayable**) and
`policy_decisions` (derived, rebuildable).

---

## 8. Findings during implementation — four

### G-1 — the audit report showed the wrong edge *(real defect)*

`audit_report`'s timeline read `projection.TRANSITIONS`, which holds the *static* edge. For a
PolicyEvaluated denial it would have reported `policy_check → queued` — a transition that never
happened. **This is the same class of defect as F-1**, in the reporting layer rather than the write
layer. Found by `test_the_blocked_state_is_actually_visited`. Fixed by
`projection.resolved_transition()`, which resolves the payload-dependent edge and is now used by
every reader.

### G-2 — approval could never lead to execution *(real design gap)*

As first implemented, an approved task returned to `queued` carrying its original denial, so the
dispatch guard refused it forever. Approval that cannot lead to execution is not approval — it is a
misleading state change. Found by `test_approval_releases_the_task_and_it_then_executes`. Fixed by
re-evaluating the gate at approval and refusing the approval while it still denies (§6).

### G-3 — a refused dispatch would have spun the run loop *(real defect)*

A task the dispatch guard refuses stays in `queued`, and `run_once` would have re-selected it
forever. Found by reasoning about the loop immediately after writing the guard, and fixed by
excluding refused tasks from re-selection for the remainder of the run — the refusal is already
recorded as an anomaly, so the exclusion needs no persistence.

### G-4 — two mutation survivors, both genuine test gaps

Unlike Step 2's survivors, these were **not** mis-specified mutations:

- **M10** — mapping an unreadable policy decision to `queued` instead of `blocked` survived. The
  review-side equivalent was tested; the policy-side one was not. Closed.
- **M14** — removing the review reason requirement survived, because
  `test_a_bare_approval_is_refused` **passed for the wrong reason**: the gate re-evaluation refused
  the approval anyway, masking the missing check. Closed by testing a bare **rejection** (which does
  not re-evaluate, so the reason check is the only guard) and by testing bare approval *with* an
  authorization in place.

M14 is the more instructive of the two: a test that passes because a different guard fired is not
evidence of the guard it names.

### G-5 — a crash between the denial and the review request **stranded the task** *(real defect)*

**Found by writing the boundary-24 test**, which is exactly why the tests were added rather than
left as an argument.

A denial emits `AcquisitionDenied` and then `HumanReviewRequired` as two events. A crash between
them left the task in `blocked` — which is **not terminal**, was **not in the drivable set**, and
had **no route out at all**. It could neither be reviewed nor reach a terminal outcome: the
Constitution §6.5 stranding defect that Step 2 eliminated for failures, reintroduced on the policy
path.

Verified before fixing, by forcing the exact post-crash state and running `recover()` + `run_once()`:
the task stayed in `blocked` and `advanced` was empty.

**Fixed** by making `blocked` drivable and completing the interrupted transition through
`_request_review()`, which **re-states the durable decision and never re-makes it** — every field
falls back to the recorded task row. Mutations 19 and 20 now guard the fix.

### G-6 — `verify` reported a **false FATAL** for every suppressed task *(real defect)*

The Step 2 terminal-state check used a static map of event names
(`TaskSucceeded → succeeded`, `TaskDeadLettered → dead_lettered`). `suppressed` is reached by a
**payload-dependent** transition — `HumanReviewCompleted(rejected)` — which a static map cannot
express, so `verify` reported:

> `FATAL  task … is terminal in state 'suppressed' but no event in the log carries that transition`

**This was not a crash artefact.** Confirmed to occur in ordinary operation, with no crash involved,
for any rejected task. Found by the boundary-26 test's `verify` assertion.

**Fixed** by resolving the edge through `projection.resolved_transition()` — the same fix, and the
same reasoning, as G-1. Mutation 21 guards it.

---

## 9. Deviations from the plan — three, all disclosed

| | Deviation | Why |
|---|---|---|
| **J-1** | The plan estimated ~18 files and named `contracts/vocabulary.py` as unmodified; the actual count is 20 and the estimate held. **`commands.input_refs_json` was added**, which §6.6 did not list. | The gate resolves an acquisition's subject source from `inputRefs` (Catalog §A: identifiers only). Without projecting them, every acquisition would deny with `no_subject_source`. Copied from the payload like every other column. |
| **J-2** | The plan's §6.4 mechanism 2 said the decision has **one** call site; it has **two**. | Finding G-2. An approval must re-evaluate the gate or it can never lead to execution. The invariant is preserved in a stronger form: both call sites are asserted **by name**, and no other runtime module may consult the gate. |
| **J-3** | `registry.CONNECTOR_GATES` now marks `policy_gate` **satisfied**. | Step 3 delivered all three of its named requirements — classification, authorization records, enforcement tests. The remaining three gates stay unmet, and the test asserts them **by name** so a future step cannot quietly mark another one met. |
| **J-4** | `NON_TERMINAL_RESUMABLE` gains `blocked`, and the CLI gains `submit --demo-policy` and `review --simulate-crash-at`. | Finding G-5 required `blocked` to be drivable. The two CLI additions exist so the crash boundaries can be driven through **child processes with real `os._exit(70)` kills**, as every other boundary in this milestone is. |

---

## 10. Preservation of standing requirements

| Requirement | How |
|---|---|
| Deterministic execution | the decision is a pure function of recorded values |
| Replay determinism | `evaluate` is never called during `rebuild()`; whole-row equality after rebuilding with the clock advanced a year |
| Append-only event history | no new write path; every decision rides inside the existing `_emit` protocol |
| Immutable evidence | no scientific path exists; protected-path tests unchanged |
| Protected-function drift | **0** |
| Campaign C1 | **33/33**, untouched |
| Zero third-party dependencies | **0** — 14 import roots, all stdlib or `mogo_platform` |
| Offline execution | proven structurally: no network import, no subprocess, no socket anywhere |

**A policy change cannot rewrite history.** Every decision carries the authorization's content hash
as it stood at decision time, and a test records a decision, then supersedes the authorization, then
rebuilds — and asserts the recorded decision and hash are unchanged. Constitution §5.7, made
mechanical.

---

## 11. Risks

**A-5 unchanged, severity High, carried verbatim.** Step 3 registers no effectful capability and
opens none of the gate's four preconditions.

**Carried from Steps 1–2:** A-3, A-4, A-6, A-7, A-8, `fsync` structural only, wall-clock dependence,
boundary-20 attempt consumption, non-replayable observation tables.

**New and disclosed:** `acquisition_authorizations` is governance input and not replayable (named in
the schema; the *decision* is replayable and carries the record's hash) · schema v3 extends the
migration precedent · the policy-probe capability declares acquisition class while acquiring nothing
(a governance statement, not a behavioural one; the boundary tests continue to prove no acquisition
path exists) · policy re-evaluation on version change remains deferred with its trigger named (C-5).

---

## 12. Crash behaviour — now proven, not assumed

The first version of this report recorded the four Step 3 boundaries as *declared and reachable but
not tested*, carried on the argument that each gate transition is a single event under the unchanged
write protocol. **That argument was wrong in one place**, and the tests found it (G-5).

Boundaries 23–26, each exercised by a real `os._exit(70)` in a child process:

| # | Boundary | Kind | After recovery |
|---:|---|---|---|
| 23 | after the policy decision is appended | append | replay converges to `awaiting_review` (deny) or `succeeded` (permit); exactly one decision |
| 24 | between the denial and the review request | between events | completes `blocked → awaiting_review`; **the G-5 regression** |
| 25 | after the review request is appended | append | replay converges to `awaiting_review`; exactly one request |
| 26 | after the review decision is appended | append | replay converges to `suppressed` (reject) or `succeeded` (approve), carrying the gate's permit |

**Asserted at every boundary:** no fabricated authorization · no fabricated claim, start, success or
failure · `attempt` stays 0 · no `task_attempts` row · the gate is never bypassed · every recorded
transition is an approved Catalog §L edge · the log verifies · the index never claims history the log
does not have · a rebuild from the log alone reproduces the state and `verify` passes.

**Two properties are asserted across all boundaries at once:** `test_no_boundary_can_fabricate_an_authorization`
and `test_no_boundary_lets_unauthorized_work_execute`, plus
`test_repeated_restart_across_the_gate_converges` (five sequential kills).

**A distinction the tests make explicitly.** An *append* boundary leaves the index legitimately
behind the log, and `verify` must **say so** — it names the `log_sequence` and prescribes `recover`.
A *between-events* boundary leaves the index consistent. Neither is a contradiction; what would be
is a FATAL finding or an index claiming history the log lacks, and both are asserted absent.

---

## 13. State

Nothing staged. Nothing committed. Nothing tagged. Nothing pushed.
`HEAD` remains `7b2c0aa940d185995305e45a209edf063050e10b`.
21 files changed (6 created, 15 modified), 0 protected paths touched.

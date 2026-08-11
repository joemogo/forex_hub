# MOGO-011 STEP 2 — IMPLEMENTATION REPORT

**Milestone:** MOGO-011 Step 2 — retry, lease and dead-letter
**Baseline:** `c50f95ca839fd41f75e56f93997d82928261f0b3` (`origin/mogo-main`)
**Governance:** all five decisions recorded in `MOGO-011-STEP-2-GOVERNANCE-RECORD.md` (B-1 … B-5)
**Status:** **implemented and validated — nothing staged, committed, tagged or pushed**
**Date:** 2026-08-08

---

## 1. Executive summary

Step 2 is implemented as planned. The runtime now handles failure as a first-class outcome: a
retryable failure is scheduled under a deterministic backoff, released only once its eligibility
has provably elapsed, re-claimed under a fresh lease, and either succeeded or dead-lettered with a
complete, self-verifying history. Recovery no longer *assumes* the previous holder is gone — it
*verifies* it.

**27 files: 7 created, 20 modified** (+3,113 / −203 lines on the tracked files, plus 2,463 lines
created). 450 → **622 tests**, 11 → **14 suites**, all passing.
Canonical gate 947/947. Campaign C1 33/33. Protected-function drift 0. Zero new dependencies.

**The single most consequential change is not a feature.** Step 1 left a failing task in `failed`,
which is not terminal — a direct violation of Constitution §6.5. Every failure path now reaches a
visible terminal outcome, and a test asserts that over all thirteen error classifications.

**Five findings emerged during implementation that the plan did not anticipate.** Four were real
defects in the plan or in first-cut code, found by tests or by the real upgrade rehearsal; all are
fixed and disclosed in §4. None required a design change or a new governance decision.

---

## 2. What was built

| Capability | Where | Evidence |
|---|---|---|
| Bounded retry with deterministic backoff | `runtime/retry.py` | backoff table asserted against an independently transcribed table; 1,000-iteration determinism check |
| Eligibility enforced, never skipped | `orchestrator._release_eligible_retries` | re-derived **from the log alone** by `verify` and by two tests |
| Dead-letter as a terminal outcome | `orchestrator._dead_letter` | all 13 classifications reach a terminal state |
| Real leases with CAS on `(taskId, leaseGeneration)` | `runtime/lease.py`, `projection` | acquisition rides inside the one guarded UPDATE |
| Reclaim by **verified** predicate | `orchestrator.recover` R4 | four quadrants unit-tested; a live lease is left alone |
| Only the lease holder may write results | `orchestrator._holds_lease` | generation bumped mid-flight ⇒ no result appended |
| Clock discipline | `runtime/clock.py` | one module reads a clock; boundary test proves it |
| A-5 gate, closed by data | `registry.A5_EFFECTFUL_GATE` | four preconditions all `False`, asserted |
| Second pure capability | `capabilities/fail_then_succeed.py` | result attempt-invariant across attempts 2…10 |
| Failure observability | `audit.failures_report`, `failures` | what failed, when, why — plus the gates |
| Schema v2 | `runtime/schema.py` | genuine v1 root migrates in place, rehearsed end to end |

---

## 3. Files

### Created — 7

| # | Path | Lines | Purpose |
|---|---|---:|---|
| 1 | `platform/src/mogo_platform/runtime/clock.py` | 227 | `Clock` protocol, `SystemClock`, `ManualClock`, `MonotonicFloor`, ISO-8601 parse/format. The **only** module in `platform/**` permitted to read a clock. |
| 2 | `platform/src/mogo_platform/runtime/retry.py` | 334 | `classify_failure`, `backoff_ms`, `resolve_policy`, `is_eligible`, `MAX_ATTEMPT_LIMIT`. Pure functions only. |
| 3 | `platform/src/mogo_platform/runtime/lease.py` | 158 | `reclaim_reason`, `is_expired`, `is_held_by`, `lease_ttl_ms`. Pure predicates only. |
| 4 | `platform/src/mogo_platform/runtime/capabilities/fail_then_succeed.py` | 161 | `research.runtime.fail-then-succeed.v1` — pure, attempt-invariant result. |
| 5 | `tests/platform/test_runtime_retry.py` | 657 (55 tests) | retryability, attempt semantics, backoff, eligibility, clock discipline |
| 6 | `tests/platform/test_runtime_lease.py` | 449 (33 tests) | acquisition, expiry, four reclaim quadrants, holder authority |
| 7 | `tests/platform/test_runtime_dead_letter.py` | 477 (22 tests) | exhaustion, absorption, history, replay, schema guards |

*(7 files, matching the plan's §27 count exactly.)*

### Modified — 20

| # | Path | Change |
|---|---|---|
| 1 | `contracts/vocabulary.py` | **+1 event name** `TaskRetryReleased` (39 → 40), with the authorization recorded in-file |
| 2 | `contracts/boundaries.py` | **+`BANNED_NONDETERMINISM_IMPORTS`** (`random`, `secrets`) — see deviation I-1 |
| 3 | `runtime/errors.py` | `+CapabilityFailure`, `+ClockRollbackError`, `+EffectClassRefusedError`, `+RetryPolicyError`, `+fail_capability()` |
| 4 | `runtime/schema.py` | `SCHEMA_VERSION = 2`; `_migrate_v2`; `_V1_APPEND_ONLY_TABLES`; `capability_violations` append-only |
| 5 | `runtime/projection.py` | 3 new transitions; attempt increment; lease columns; retry columns; `task_attempts`; rebuild order |
| 6 | `runtime/registry.py` | `effectClass`, `failureClasses`, `requiresExecutionContext`, `retryPolicy`; `A5_EFFECTFUL_GATE`; `CONNECTOR_GATES` |
| 7 | `runtime/worker.py` | `CapabilityFailure` handling; declared-class validation; execution context |
| 8 | `runtime/orchestrator.py` | retry/dead-letter decision; lease acquire/verify/clear; `run_id`; R1b clock guard; R4 rewrite; R6 release; 11 crash boundaries; second capability |
| 9 | `runtime/audit.py` | attempts, retries, leases, dead letters, failures-by-class, gates; 4 new `verify` checks |
| 10 | `runtime/cli.py` | `failures` subcommand; `--now`; `--demo-retry`; demo scenarios; `_open_readonly` |
| 11 | `platform/README.md` | Step 2: failure as a first-class outcome, the lease's two jobs, clock discipline, the A-5 gate, the deferred table |
| 12 | `tests/platform/test_platform_boundaries.py` | two capabilities; randomness ban; clock confinement; capability purity |
| 13 | `tests/platform/test_platform_envelopes.py` | independently transcribed event list 39 → 40 |
| 14 | `tests/platform/test_runtime_store_schema.py` | v2 tables/indexes/version; genuine v1→v2 migration tests |
| 15 | `tests/platform/test_runtime_projection.py` | transition table 8 → 11 entries |
| 16 | `tests/platform/test_runtime_orchestrator.py` | worker signature |
| 17 | `tests/platform/test_runtime_capability.py` | two capabilities; second-capability suite; A-5 gate suite; echo pinned |
| 18 | `tests/platform/test_runtime_recovery.py` | boundaries 12–22, repeated-restart convergence |
| 19 | `tests/platform/test_runtime_end_to_end.py` | Step 2 Primary Outcomes; upgrade path through the CLI |
| 20 | `tests/run_platform_tests.sh` | 11 → 14 suites |

**Not modified, each for a stated reason:** `capabilities/echo.py` (pinned by hash — three tests
enforce it) · `runtime/{paths,store,event_log}.py` (need nothing) · **`contracts/task_states.py`**
(every Step 2 edge already exists with the correct authority) · `contracts/{ids,errors,command,event}.py`
· `tests/run_all.sh` (ADR-012 D-12) · all protected paths.

---

## 4. Findings during implementation

Five things the plan did not anticipate. Each is stated with what it was, how it was found, and
what was done.

### F-5 — an unknown error class cannot be recorded at all *(real contract finding)*

Plan §12.1 lists `unknown_error_class` as one of five reachable dead-letter reasons. It is not
reachable by the route the plan implies: `contracts/event.py` restricts the envelope's `errorClass`
to the Catalog §K vocabulary, so a `TaskFailed` carrying an unknown class is **refused by the event
validator** — and the failure would vanish, which Constitution §6.6 forbids.

**Found by:** `test_every_error_class_reaches_the_expected_terminal_state`, which drove all thirteen
classifications and died on the invented one.

**Resolution.** Two fail-closed normalizations, both recorded rather than silent:
- `_fail_task` normalizes a non-§K class to `deterministic_processing` (non-retryable) and writes a
  `capability_violations` row naming the original.
- `_dead_letter` keeps the observed class in the **payload** (`finalErrorClass`, free-form) and puts
  a valid classification in the **envelope**. Nothing is lost; nothing invalid is appended.

`unknown_error_class` survives as a live branch for the only remaining route — a class that reached
the derived index through corruption — and that route is now tested directly.

### F-6 — read-only commands queried v2 tables against a v1 database *(real defect)*

`status`, `audit`, `verify` and `failures` open the database without taking the process lock and
therefore never migrate. Against a genuine Step 1 state root they queried `task_attempts`, which
does not exist there, and crashed with a traceback.

**Found by:** rehearsing the upgrade for real — building a v1 state root with the *committed* Step 1
build (`git archive HEAD`) and opening it under Step 2. The in-suite migration test missed it
because it called `schema.initialize()` directly rather than going through the CLI.

**Resolution.** `cli._open_readonly` refuses a below-current schema with an actionable message
naming both versions and pointing at `init` — which is the one command that takes the lock and
therefore the only one that may migrate. Regression test added, using a genuine v1 database built
from the shipped v1 migration rather than a hand-degraded v2 one.

### F-7 — `rebuild()` violated a foreign key *(real defect)*

`task_attempts.task_id` references `tasks`, and the rebuild delete list deleted `tasks` first.
Foreign keys are on, so this raised `IntegrityError` rather than silently orphaning rows — the
correct direction, and how the order was established.

**Found by:** the first end-to-end `reset --rebuild-index` run. Fixed by deleting children first.

### F-8 — recovery did not refuse a rolled-back clock *(real gap against the plan)*

Plan §15.3 requires a rolled-back clock to abort recovery. As first implemented, the monotonic guard
lived only in `_emit`, so `recover()` with a backward clock simply found every expired lease "live",
declined to reclaim anything, and returned success — reasoning from a time that never happened
while appearing to work.

**Found by:** `test_a_backward_clock_cannot_make_an_expired_lease_look_live`.

**Resolution.** `_assert_clock_not_rolled_back()` runs at R1b in `recover()` and at the top of
`run_once()`, before either phase reasons from `now`, and records `clock_rollback_refused` in
`recovery_actions` rather than only raising.

### F-9 — plan §25.2 scenario 2 is not reachable with the plan's own manifest

Plan §25.2 shows a demo scenario submitting "with `backoffBaseMs=1000`" to display a retry being
withheld. Plan §16.1 fixes that capability's `backoffBaseMs` at **0**, and a command envelope carries
no retry policy (Catalog §A defines none), so there is no legal source for a non-zero backoff in the
demonstration. A zero backoff is eligible immediately and can never be withheld.

**Resolution — disclosed, not worked around.** The demo implements scenarios 1, 2 (dead-letter), 3, 4
and 5 faithfully and **states in its own output** why the withheld-retry scenario is not shown, and
where it is proved instead. Registering a third capability purely to make the demo print a wait would
be inventing a capability to satisfy a demonstration — which plan §16.3 explicitly rejects.

The rule itself is proved against a non-zero backoff with an injected clock:
`test_a_retry_is_not_released_before_its_eligibility` (clock unadvanced ⇒ nothing released) and
`test_a_retry_is_released_exactly_at_eligibility` (−1 ms withheld, exactly at eligibility released).

---

## 5. Deviations from the plan

Three, all disclosed. None changes a governed decision.

### I-1 — `contracts/boundaries.py` was modified, which §28 listed as unmodified

Plan §29 requires `random` and `secrets` to be added to `BANNED_RUNTIME_IMPORTS`, and §32 lists
randomness as a new boundary check. `BANNED_RUNTIME_IMPORTS` lives in `boundaries.py`. Plan §28's
"not modified" line for that file is inconsistent with §29 and §32, and its stated reason ("every
needed edge, class and field is already committed") is not true of the randomness ban.

§29 and §32 are the specific sections that reason about it, so they govern. The change is purely
additive — a new declaration tuple folded into the existing one — and alters no validator's
behaviour. **The alternative would have been to enforce decision B-2 by convention only, which is
the weaker of the two and contrary to the decision's own terms.**

### I-2 — `tasks.retry_policy` column added, not listed in plan §21

Plan §22.8 requires the retry policy **resolved at task creation** to govern that task, so that a
later change to a capability's declared defaults cannot retroactively alter a task already in flight.
§21's column list has no place to keep it. The column is populated exactly like every other — copied
from the `TaskRequested` payload, never computed — and is covered by the whole-row rebuild equality
test. `test_the_retry_policy_recorded_at_creation_is_used_later` proves the guarantee.

### I-3 — a non-zero `jitterMs` is refused rather than honoured

Plan §9.3 says the field is "retained and governed" at 0. Honouring a declared non-zero jitter would
put an ungoverned delay into a replayable schedule, so `validate_policy` refuses it and names
decision B-2. The field is retained, validated and recorded, as required; the enforcement is
stricter than the plan's wording and fail-closed.

---

## 6. Preservation of the five Step 1 properties

| Property | Preserved how |
|---|---|
| Write protocol P1 → P2 → P3 | Unchanged. Step 2 adds no transaction shape; every new fact rides inside the existing transaction of the event that implies it. |
| `_emit()` is the only append site | Unchanged. No second write path exists. |
| The guarded UPDATE is the exactly-once primitive | Extended, not replaced: attempt increment, lease columns and retry columns are additional `SET`/`WHERE` clauses on the **same** statement. `test_attempt_is_written_by_exactly_one_sql_statement_in_the_runtime` and `test_lease_columns_are_written_by_exactly_one_sql_statement` assert it by AST. |
| JSONL authoritative, SQLite derived | Every new column copied from a payload. `test_rebuild_reproduces_every_step_2_column_exactly` rebuilds with the clock advanced by a year and asserts whole-row equality. |
| Only the orchestrator writes task state | Worker still receives no connection and no log. |

---

## 7. Validation

Full results in `MOGO-011-STEP-2-VALIDATION-REPORT.md`. Headline:

| Gate | Result |
|---|---|
| Platform suite | **14 suites, 622 tests, 622 passed, 0 failures, 0 errors** |
| Canonical gate `tests/run_all.sh` | **17 suites, 947 fixtures, 947 passed, 0 failed** |
| Campaign C1 | **33 verified, 0 missing, 0 mismatched, 0 unlisted** |
| Protected-function drift | **63 functions, 4 constants, drift 0** |
| Third-party dependencies | **0** |
| Demo, crash boundaries, rebuild, verify | all pass |
| Genuine v1 → v2 upgrade (committed Step 1 build) | migrates, verifies, rebuilds |
| Mutation protocol | **27 applied, 27 detected, 0 survivors, 27 reverted byte-identical** |

Two mutations survived their **first** formulation and were re-run corrected. Neither was a test
gap: each removed only one of two independent guards, and the surviving guard did its job. The
corrected forms (`M05c`, `M11a`, `M11b`) are all detected. Detail in the validation report §4.1 —
it is recorded that way rather than as a clean 24/24 because the first result was real and the
reason for it matters.

---

## 8. Risks

**A-5 carried forward verbatim, severity unchanged (High).** Step 2 makes the prohibition
*mechanical* rather than documentary. It does not reduce the hazard, and it adds no output
verification, no result store and no duplicate-effect prevention, because it registers nothing that
needs them.

**New, non-blocking:** wall-clock dependence is new to the platform (confined to one module,
injected, monotonic guard fails closed) · a mid-execution crash consumes an attempt (deliberate;
the alternative permits unbounded retry) · the `capabilities` and `runs` tables are not replayable
(named in the schema, not papered over) · schema v2 sets migration precedent for the repository's
first database.

**Also carried unchanged from Step 1:** A-3, A-4, A-6, A-7, A-8, and `fsync` asserted structurally only.

---

## 9. State

Nothing staged. Nothing committed. Nothing tagged. Nothing pushed. `HEAD` remains
`c50f95ca839fd41f75e56f93997d82928261f0b3`. Every protected path is untouched and verified.

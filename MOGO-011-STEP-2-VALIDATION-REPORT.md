# MOGO-011 STEP 2 — VALIDATION REPORT

**Milestone:** MOGO-011 Step 2 — retry, lease and dead-letter
**Baseline:** `c50f95ca839fd41f75e56f93997d82928261f0b3` (`origin/mogo-main`) — **unchanged**
**Status:** **all gates pass — nothing staged, committed, tagged or pushed**
**Date:** 2026-08-08 · Python 3.14.6 · SQLite 3.53.3

---

## 1. Verdict

| | |
|---|---|
| Platform suite | **14 suites · 622 tests · 622 passed · 0 failures · 0 errors · 0 skipped** |
| Canonical repository gate | **17 suites · 947 fixtures · 947 passed · 0 failed** |
| Campaign C1 | **33 verified · 0 missing · 0 mismatched · 0 unlisted** |
| Protected-function drift | **63 functions · 4 constants · drift 0** |
| Mutation protocol | **27 applied · 27 detected · 0 survivors · 27 reverted, byte-verified** |
| Third-party dependencies | **0** |
| Protected paths modified | **0** |
| `HEAD` | `c50f95ca839fd41f75e56f93997d82928261f0b3` — unchanged |

---

## 2. Validation sequence, run in order

| # | Check | Result |
|---|---|---|
| 1 | Purge all bytecode | done before every run below |
| 2 | `python3 -m compileall -q platform tests/platform` | **OK** |
| 3 | Import all 7 contract + 16 runtime modules under `-W error` | **23 modules · 40 event names · schema version 2** |
| 4 | `bash tests/run_platform_tests.sh` | **14 suites, 622 tests, 622 passed, 0/0/0** |
| 5 | `demo` on a scratch state root | **exit 0**; 12 `TaskRetryReleased`/`TaskDeadLettered` events observed |
| 6 | `run --simulate-crash-at during_retry_execution` then `run` | **exit 70**, then recovered and completed; no duplicate |
| 7 | `run --simulate-crash-at before_dead_letter_apply` then `run` | **exit 70**, then dead-lettered exactly once |
| 8 | `reset --rebuild-index` then `verify` | **REBUILT 43 events, 31 transitions** · **INTEGRITY OK** |
| 9 | `failures` | grouped by class; A-5 gate **CLOSED**; 4 connector gates **UNMET** |
| 10 | `bash tests/run_all.sh` | **17 suites, 947 fixtures, 947 passed, 0 failed** |
| 11 | `python3 regression-baseline-tools.py` | **No drift: 63 functions, 4 constants** |
| 12 | Campaign C1 manifest verification | **33/33 by SHA-256; 0 missing, 0 mismatched, 0 unlisted** |
| 13 | AST write-path scan over `platform/**` | enforced by `test_platform_boundaries` — 0 offenders |
| 14 | AST no-network / no-subprocess / no-random / no-clock | **0 / 0 / 0 / clock.py only** |
| 15 | `sys.stdlib_module_names` dependency classification | **third-party: 0** |
| 16 | Genuine Step 1 state root upgrade v1 → v2 | refused by report commands, migrated by `init`, then `verify` **INTEGRITY OK** and rebuild clean |
| 17 | `git check-ignore` on database, log, tasks, quarantine | **all four ignored** |
| 18 | Mutation run: 27 mutations, bytecode purged between each | **27/27 detected, 27/27 reverted** |
| 19 | Protected paths (`evidence`, `docs/campaigns`, `index.html`, `hypothesis-registry.json`, replay record) | **0 modified** |

**Item 16 is worth naming.** The upgrade was rehearsed against a state root built by the
**committed Step 1 build** (`git archive HEAD` into a scratch tree), not by a hand-degraded Step 2
database. That is what surfaced finding F-6 — the report commands queried v2 tables against a v1
database — which the in-suite migration test had missed.

---

## 3. Test inventory

**450 → 622 tests. 11 → 14 suites.**

| Suite | Tests | Δ |
|---|---:|---:|
| `test_platform_identifiers` | 96 | — |
| `test_platform_envelopes` | 71 | — |
| `test_platform_task_states` | 66 | — |
| `test_platform_boundaries` | 47 | +4 |
| `test_runtime_store_schema` | 31 | +6 |
| `test_runtime_event_log` | 27 | — |
| `test_runtime_projection` | 22 | — |
| `test_runtime_orchestrator` | 25 | — |
| `test_runtime_capability` | 52 | +21 |
| **`test_runtime_retry`** | **55** | **new** |
| **`test_runtime_lease`** | **33** | **new** |
| **`test_runtime_dead_letter`** | **22** | **new** |
| `test_runtime_recovery` | 32 | +15 |
| `test_runtime_end_to_end` | 40 | +16 |
| **Total** | **622** | **+172** |

### The tests that carry the most weight

- `test_no_release_precedes_its_eligibility_when_re_derived_from_the_log` — re-derives the
  eligibility check by scanning the log, so it survives the deletion of every in-process assertion.
- `test_rebuild_reproduces_every_step_2_column_exactly` — advances the clock by a year, rebuilds,
  and asserts **whole-row** equality across `tasks`, `commands` and `task_attempts`. Any column
  computed from a clock at projection time fails it.
- `test_dead_letter_history_matches_the_history_re_derived_from_the_log` — the payload's attempt
  history is a second copy of a fact; this compares it against a history rebuilt independently from
  `TaskFailed` events.
- `test_a_live_lease_is_not_reclaimed_prematurely` — the case Step 1 could not express, and the one
  that makes the lease a verification rather than a rubber stamp.
- `test_a_result_is_refused_when_the_lease_generation_changed_mid_execution` — bumps the generation
  behind the executing code's back and asserts no `TaskSucceeded` is appended.
- `test_every_a5_gate_precondition_is_false_in_this_build` — a future step that opens the gate
  breaks a test named after it.
- `test_attempt_is_written_by_exactly_one_sql_statement_in_the_runtime` — AST, not text, so it
  cannot be satisfied by deleting the comment that explains the increment.

---

## 4. Mutation protocol

**Protocol:** apply the mutation to committed source → **purge all bytecode** → run the full
platform suite → revert → re-verify the file's SHA-256. Bounded at 300 s per suite run, because a
mutation that removes a termination guard makes the runtime loop rather than fail.

**Result: 27 applied, 27 detected, 0 survivors.** All 26 source files verified byte-identical to
their pre-mutation hashes after the run.

| # | Mutation | Outcome | Signal |
|---:|---|---|---|
| 1 | mark policy denial retryable | DETECTED | 16 failures |
| 2 | remove maximum-attempt enforcement | DETECTED | **non-termination** — retry never bounded |
| 3 | fail to increment attempt count | DETECTED | 30 failures, 58 errors |
| 4 | increment attempt count twice | DETECTED | 16 failures |
| 5 | remove retry eligibility enforcement *(first formulation)* | **survived — see §4.1** | — |
| 5c | remove retry eligibility enforcement *(both guards)* | DETECTED | 1 failure, 1 error |
| 6 | change deterministic backoff output | DETECTED | 6 failures |
| 7 | add random jitter | DETECTED | 4 failures |
| 8 | allow a non-expired lease to be stolen | DETECTED | 2 failures |
| 9 | remove lease-owner verification | DETECTED | 1 failure |
| 10 | skip expired-lease recovery | DETECTED | 4 failures, 1 error |
| 11 | allow a dead-lettered task to execute *(first formulation)* | **survived — see §4.1** | — |
| 11a | `dead_lettered` no longer marked terminal | DETECTED | 18 failures |
| 11b | dead-lettered task dispatched again *(all guards removed)* | DETECTED | 75 failures, 5 errors |
| 12 | make the dead-letter transition SQLite-only | DETECTED | **non-termination** |
| 13 | remove an event append before a state change | DETECTED | 48 failures, 2 errors |
| 14 | register an effectful capability without the A-5 gate | DETECTED | 1 failure |
| 15 | treat an unknown classification as retryable | DETECTED | 8 failures |
| 16 | corrupt schema migration ordering | DETECTED | 67 failures, 172 errors |
| 17 | allow replay to duplicate an applied transition | DETECTED | 16 failures, 27 errors |
| 18 | permit worker code to receive a connection | DETECTED | 1 failure |
| 19 | accept a backward clock | DETECTED | 4 failures |
| 20 | recompute `eligibleAt` during projection | DETECTED | 3 failures, 1 error |
| 21 | default an absent `effectClass` to effectful | DETECTED | 63 failures, 152 errors |
| 22 | drop `UNIQUE (task_id, attempt)` | DETECTED | 1 failure |
| 23 | select ineligible `retry_scheduled` tasks | DETECTED | 75 failures, 5 errors |
| 24 | reset `lease_generation` on reclaim | DETECTED | 14 failures |

### 4.1 The two survivors, and why they were not test gaps

Both survivors were **mis-specified mutations**, and reporting them any other way would overstate
the result. Each removed only **one of two independent guards**, and the surviving guard did
exactly its job.

- **M05.** Eligibility is enforced twice: once in the SQL filter (`retry_eligible_at <= :now`) and
  once by the pure predicate `retry.is_eligible` re-applied to every selected row. The mutation
  defeated only the SQL filter; the Python predicate still refused every ineligible release, so
  behaviour was unchanged and the suite was right to pass. **M05c** removes both, and is detected.
- **M11.** Terminal absorption is enforced twice: by the `terminal = 0` filter and by the state
  filter, which never lists `dead_lettered`. The mutation defeated only the first. **M11a** (drop
  the terminal flag) and **M11b** (defeat all three guards) are both detected.

The honest reading is that the redundancy is real and load-bearing, and that the first formulations
were too weak to test what they claimed. Both were re-run in corrected form rather than recorded as
passes.

### 4.2 A note on detection by non-termination

Three mutations are detected because the suite **hangs** rather than fails: removing the attempt
ceiling, removing the dead-letter transition, and making a terminal task drivable all leave
`run_once` with a task that never leaves the drivable set. That is a genuine detection — the suite
never reports success — and it is recorded distinctly from a failure, because "the tests proved the
mutation wrong" and "the mutation stopped the system making progress" are different facts.

---

## 5. Crash-recovery matrix

Step 1 boundaries 1–11 unchanged and still passing. Step 2 adds 12–22, each exercised by a real
`os._exit(70)` in a child process — no mocks, no unwinding, no flush.

| # | Boundary | Recovery | Duplicate work |
|---:|---|---|---|
| 12 | after `TaskFailed` append | replay → `failed`, decision re-reached | none |
| 13 | inside the `TaskFailed` transaction | identical to 12 | none |
| 14 | after `TaskRetryScheduled` append | replay → `retry_scheduled`, `eligibleAt` **copied** | none |
| 15 | before the retry projection | replay | none |
| 16 | after `TaskRetryReleased` append | replay → `queued` | none |
| 17 | after the lease claim | R4 `owner_gone` → reclaimed, generation bumped | none; attempt not consumed |
| 18 | after lease expiry, before reclaim | predicate re-evaluated over recorded state | none |
| 19 | before requeue | replay of the reclaim | none |
| 20 | during retry execution | reclaim → re-claim → next attempt | **the attempt is consumed — deliberate** |
| 21 | before the dead-letter is applied | replay → `dead_lettered` | exactly one `TaskDeadLettered` |
| 22 | after the dead-letter append | replay → terminal | exactly one |

`test_repeated_restart_converges_to_the_same_terminal_state` kills the runtime at five different
boundaries in sequence and asserts the final state is terminal, that at most one `TaskSucceeded` and
one `TaskDeadLettered` exist, and that `verify` passes afterwards.

**Boundary 20 is a decision, not a mechanism.** A crashed attempt was attempted. Decrementing on
reclaim would let a task that crashes the process every time retry forever, defeating Constitution
§11's bounded retry. Consuming the attempt is the fail-closed choice, it is recorded, and it is
stated so it is never mistaken for an off-by-one.

---

## 6. Boundary and isolation verification

| Boundary | Result |
|---|---|
| `platform/**` → `evidence/`, `docs/campaigns/`, `PREREG-*`, replay record, `index.html`, `hypothesis-registry.json` | no literal, no write argument — 0 offenders |
| network imports | 0 |
| subprocess / dynamic import | 0 |
| **randomness (`random`, `secrets`)** | **0 — and structurally banned** |
| **clock reads** | **`clock.py` only** |
| naive `datetime.now()` | 0 |
| capability purity (I/O, clock, randomness) | 0 offenders across `capabilities/**` |
| contracts layer I/O | 0 `open` calls of any kind |
| runtime write confinement | every write site guarded by `assert_inside_state_root` |
| runtime state git-ignored | database, log, tasks, quarantine — all ignored |
| capabilities registered | exactly 2, both `pure`, both non-acquisition, no connector, no secret, no permission |
| package manifest / lock file | none exists |

---

## 7. What is honestly not covered

Stated rather than left to be discovered.

- **`fsync` is asserted structurally only.** An in-process test cannot prove a physical flush. Carried
  from Step 1, unchanged.
- **The `capabilities` and `runs` tables are not replayable.** They hold registration and local run
  observations, not events. Named in the schema and in `§19.4` of the plan, not papered over.
- **Capability-lifecycle events are not implemented**, because no capability changes lifecycle state.
- **A retry being withheld is not shown in the `demo`** — the demonstration capability declares
  `backoffBaseMs = 0` by design, so a zero backoff is eligible at once. The rule is proved instead
  against a non-zero backoff with an injected clock. The demo says so in its own output. See
  implementation report F-9.
- **One pre-existing `ResourceWarning`** in `test_no_boundary_produces_a_duplicate_task_or_duplicate_success`
  (a Step 1 test that re-enters `setUp` inside a loop). Present at the baseline commit, unrelated to
  Step 2, and deliberately not modified — it is a warning, not a failure, and touching a passing
  Step 1 test that Step 2 did not break would be scope creep.

---

## 8. Risk position after validation

**A-5 unchanged, severity High, carried verbatim.** Step 2 makes the prohibition mechanical rather
than documentary; it adds no output verification, no result store and no duplicate-effect
prevention, because it registers nothing that needs them. The four gate preconditions are `False`
and a test asserts it, so the gate cannot be opened quietly.

**Also carried:** A-3 torn-tail truncation · A-4 no approved event names a quarantined fragment ·
A-6 `fcntl` is POSIX-only · A-7 `targetCapability` canonical-form ambiguity · A-8 first-database
precedent.

**New and disclosed:** wall-clock dependence (confined, injected, fails closed) · boundary 20
consumes an attempt · non-replayable observation tables · schema v2 migration precedent · a manifest
could declare `pure` while being effectful, which the **static** scan catches rather than the
registry.

---

## 9. State at the end of validation

Nothing staged. Nothing committed. Nothing tagged. Nothing pushed.
`HEAD` = `c50f95ca839fd41f75e56f93997d82928261f0b3`.
20 tracked files modified, 7 source/test files created, 0 protected paths touched.

**Next gate: human approval of the implementation before any commit.**

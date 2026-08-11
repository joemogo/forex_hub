# MOGO-011 STEP 1 — VALIDATION REPORT

**Milestone:** MOGO-011 Step 1 — Runtime Kernel · **Status:** all validations pass
**Baseline:** `766ee5c5374581adcce2afb3f6684a03ec3cb424` · **Date:** 2026-08-07
**Nothing staged, committed, tagged or pushed.**

---

## 1. Headline Results

| Gate | Required | Actual | Verdict |
|---|---|---|---|
| Platform suites | all pass | **450 tests, 450 passed, 0 failures, 0 errors, 0 skipped** (11 suites) | ✅ |
| Canonical gate `tests/run_all.sh` | 947 fixtures pass | **17 suites, 947 fixtures, 947 passed, 0 failed, 0 execution errors** | ✅ |
| Protected-function drift | zero | **63 functions, 4 constants, drift 0** | ✅ |
| Campaign C1 manifest | 33/33 | **33 verified, 0 missing, 0 mismatched, 0 unlisted** | ✅ |
| Pre-existing Python suites | same six failures | **451 tests, 6 failures — identical names, unchanged** | ✅ |
| Mutation verification | every mutation detected | **16/16 detected, 16/16 reverted** | ✅ |
| Third-party dependencies | zero | **0** | ✅ |
| Existing tracked files modified | only the 5 planned | **5** | ✅ |
| Staged files | 0 | **0** | ✅ |

## 2. Per-Suite Test Counts

| Suite | Tests | Fail | Error | Skip |
|---|---:|---:|---:|---:|
| `test_platform_identifiers` | 82 | 0 | 0 | 0 |
| `test_platform_envelopes` | 108 | 0 | 0 | 0 |
| `test_platform_task_states` | 36 | 0 | 0 | 0 |
| `test_platform_boundaries` | 52 | 0 | 0 | 0 |
| `test_runtime_store_schema` | 25 | 0 | 0 | 0 |
| `test_runtime_event_log` | 33 | 0 | 0 | 0 |
| `test_runtime_projection` | 17 | 0 | 0 | 0 |
| `test_runtime_orchestrator` | 25 | 0 | 0 | 0 |
| `test_runtime_capability` | 31 | 0 | 0 | 0 |
| `test_runtime_recovery` | 17 | 0 | 0 | 0 |
| `test_runtime_end_to_end` | 24 | 0 | 0 | 0 |
| **Total** | **450** | **0** | **0** | **0** |

MOGO-010 ended at 268 tests. MOGO-011 Step 1 adds **182**, of which 172 are new runtime tests and 10 extend the existing suites (boundary narrowing plus the vocabulary extension).

## 3. Validation Commands and Exact Results

```
1  python3 -m compileall -q platform tests/platform          → COMPILE OK
2  python3 -W error  (import all 7 contracts + 11 runtime)   → IMPORT OK
                                       stdlib platform: Darwin 3.14.6
                                       event types: 39 | capability: research.runtime.echo.v1
3  bash tests/run_platform_tests.sh                          → 11 suites, 450 tests, 0/0/0
4  python3 platform/mogo_runtime.py demo (pristine state)    → exit 0
5  python3 platform/mogo_runtime.py submit --demo            → DUPLICATE SUPPRESSED
                                       tasks created=0 events appended=0
6  run --simulate-crash-at … ; run ; verify                  → recovered; INTEGRITY OK
7  bash tests/run_all.sh                                     → 17 suites, 947/947, 0 failed
8  python3 regression-baseline-tools.py                      → No drift: 63 fn, 4 const
9  Campaign C1 manifest verification                         → 33/33, 0/0/0
10 AST no-write-path over platform/**                        → 0 write-capable calls
11 AST no-network / no-subprocess                            → 0 / 0
12 sys.stdlib_module_names dependency check                  → third-party: 0
13 reset --rebuild-index ; verify                            → REBUILT 9 events, INTEGRITY OK
14 git check-ignore on the database and log                  → both ignored
```

**Runtime state root used for command-line validation:** a scratch directory via `MOGO_RUNTIME_STATE_ROOT`, never the repository's own `platform/runtime/`. Every unit test uses a `tempfile.TemporaryDirectory()`.

## 4. The Twelve Milestone Outcomes — Each Demonstrated

`python3 platform/mogo_runtime.py demo`, verbatim transcript of the decisive lines:

```
capability CAP|research|runtime-echo    registered
  WorkflowStarted            seq=1 indexed only
  CommandAccepted            seq=2 indexed only
  TaskRequested              seq=3 created in requested
ACCEPTED command=… workflow=… task=…
idempotencyKey=38eab07be62acb92e04d5042be8763a57ba1f540918a7c88dbc213c153186073
  TaskPolicyCheckRequested   seq=4 requested -> policy_check
  PolicyEvaluated            seq=5 policy_check -> queued
  TaskClaimed                seq=6 queued -> claimed
  TaskStarted                seq=7 claimed -> running
  TaskSucceeded              seq=8 running -> succeeded
  WorkflowCompleted          seq=9 indexed only
advanced=3 succeeded=1 failed=0
DUPLICATE SUPPRESSED existing command=… task=…
tasks created=0 events appended=0
INTEGRITY  OK  every event parses, validates and hashes; sequences contiguous;
               index agrees with the log
```

| # | Outcome | Test |
|---|---|---|
| 1 | valid command submitted | `test_outcome_01_a_valid_command_is_submitted` |
| 2 | validated via MOGO-010 contracts | `test_outcome_02_command_is_validated_by_mogo010_contracts` |
| 3 | durable task created | `test_outcome_03_a_durable_task_is_created` |
| 4 | policy applied only as authorized | `test_outcome_04_policy_is_applied_only_as_authorized` |
| 5 | approved task states traversed | `test_outcome_05_task_moves_through_approved_states` |
| 6 | registered capability claims it | `test_outcome_06_a_registered_capability_claims_the_task` |
| 7 | harmless deterministic operation | `test_outcome_07_the_capability_performs_a_deterministic_operation` |
| 8 | events recorded durably | `test_outcome_08_operational_events_are_recorded_durably` |
| 9 | terminal state reached | `test_outcome_09_the_task_reaches_a_terminal_state` |
| 10 | re-run duplicates nothing | `test_outcome_10_rerunning_the_same_command_duplicates_nothing` |
| 11 | restart after interruption resumes | `test_outcome_11_restart_after_interruption_resumes_safely` |
| 12 | inspectable audit | `test_outcome_12_activity_is_inspectable_through_an_audit_report` |

## 5. Crash Recovery — Every Boundary, Real Process Kills

Each test spawns a **child process** that calls `os._exit(70)` at a named boundary: no unwinding, no `finally`, no flush, no database close. A mocked exception would unwind cleanly and prove nothing.

| Plan boundary | Test | Result |
|---|---|---|
| 2 — after command append, before index | `test_boundary_2_crash_after_the_command_append` | converges; 1 command, 1 task, 1 success |
| 3 — **command received, task not created** | `test_boundary_3_crash_between_command_receipt_and_task_creation` | index shows `commands=1, tasks=0`; recovery resumes; **exactly one** task |
| 6 — after claim | `test_boundary_6_crash_after_claim_reclaims_and_completes` | reaches `succeeded`, 1 task |
| 7 — mid execution | `test_boundary_7_crash_mid_execution_reclaims_and_completes` | reclaimed, re-executed, `succeeded` |
| 8 — **after execution, before success** | `test_boundary_8_crash_after_execution_yields_an_identical_result` | **identical `contentHash`** after re-execution |
| 9 — after success append | `test_boundary_9_crash_after_success_append_still_reaches_succeeded` | 1 success, not 2 |
| 10 — torn tail | `test_torn_tail_is_quarantined_and_the_run_completes` | fragment quarantined byte-for-byte; run completes |
| all | `test_no_boundary_produces_a_duplicate_task_or_duplicate_success` | 5 boundaries × (1 task, 1 success) |

Plus: `test_restart_does_not_repeat_completed_work` (3 restarts, identical counts), `test_recovery_is_deterministic_across_repeated_restarts`, `test_recover_is_idempotent`, `test_a_second_runner_is_refused_while_one_holds_the_lock` (exit 5, `BUSY`), `test_an_index_deleted_entirely_is_rebuilt_from_the_log`.

**Boundary 8 is safe only because the capability is pure.** Re-execution after an interrupted run produces a byte-identical result, so it is indistinguishable from never having been interrupted. The moment a capability performs an external effect, that argument fails and output verification is required first — recorded as the standing Step 2 gate.

## 6. Mutation Verification — 16/16

Sandbox outside the repository (`git archive HEAD` plus the working files), **bytecode purged before every run**.

| # | Mutation | Detected by |
|---|---|---|
| 1 | idempotency `UNIQUE` dropped | `test_database_refuses_a_second_command_for_one_key` |
| 2 | `from_state` guard removed | 19 tests |
| 3 | `last_log_sequence` replay guard removed | 13 tests |
| 4 | index/log divergence detector removed | `test_an_index_entry_with_no_log_line_is_reported_fatal` |
| 5 | `fsync` removed from the append | `test_append_calls_fsync_before_returning` |
| 6 | append-only triggers dropped | 5 tests |
| 7 | payload-hash verification skipped on read | 2 tests |
| 8 | disabled capability may dispatch | 2 tests |
| 9 | incompatible command version admitted | `test_incompatible_command_version_fails_closed` |
| 10 | capability made non-deterministic | `test_output_is_deterministic_across_100_runs` |
| 11 | torn fragment deleted, not quarantined | `test_torn_tail_is_quarantined_not_deleted` |
| 12 | mid-file mismatch truncates instead of halting | 4 tests |
| 13 | terminal guard removed | `test_from_state_none_on_a_terminal_task_records_an_anomaly` |
| 14 | process lock removed | `test_second_lock_cannot_be_acquired` |
| 15 | write confinement disabled | 4 tests |
| 16 | contracts no-I/O rule re-broadened to runtime | 4 tests |

**No mutation leaked:** `diff -r` between the repository and the fully-reverted sandbox reported **IDENTICAL** for `platform/` and `tests/platform/`. Sandbox and harness destroyed; scratchpad empty.

### 6.1 What the first mutation run found — recorded, not smoothed over

The first pass reported **5 of 16 undetected**. Two were harness defects and **three were genuine test gaps** — which is what the exercise is for.

| Finding | Nature | Resolution |
|---|---|---|
| M1 idempotency `UNIQUE` | **real gap** — only the `tasks` constraint was tested, never `commands` | added `test_database_refuses_a_second_command_for_one_key` |
| M4 "reverse the write order" | **harness defect** — the edit did not actually reverse anything | replaced with a mutation of the invariant's *detector*, plus a new direct test that an index entry with no log line is FATAL |
| M5 `fsync` | **harness defect** (anchor matched two functions) **and then a real limit** | see §6.2 |
| M10 non-determinism | **real gap** — the test reused one object, so `id()`-derived nondeterminism was invisible | test now builds a fresh, structurally equal object each iteration |
| M13 terminal guard | **real gap** — no `from_state` in the transition table is terminal, so ordinary traffic can never reach the guard | added a direct test calling `apply_transition(..., from_state=None)` on a terminal task |

### 6.2 One durability guarantee is asserted structurally, and why

Removing `os.fsync` **cannot** be detected by any in-process test. `os._exit()` leaves the page cache intact, so a log written without `fsync` still reads back correctly in every crash test here. Only power loss or a kernel crash distinguishes the two, and neither is inducible from Python.

The guarantee is real and load-bearing — `append()` promises that a returned `LogRecord` survives power loss — so it is asserted the only way it can be: **structurally**, by proving via AST that the call exists in the function making the promise. `test_append_calls_fsync_before_returning` and `test_quarantine_write_is_fsynced_before_the_log_is_truncated` do this, and both docstrings state the limitation plainly rather than implying behavioural coverage.

**A near-miss worth recording.** Those two tests were initially written with `inspect.getsource()` on a *method*, which returns class-indented source that `ast.parse` rejects — so they **errored** rather than asserted. In the mutation run that error registered as "mutation detected," which would have been a **false positive**. It was caught, fixed with `textwrap.dedent`, and mutation 5 was then re-verified in isolation: baseline green (33 tests pass), mutation applied → `FAIL: test_append_calls_fsync_before_returning`. That is a genuine detection.

## 7. Boundary and Safety Verification

| Check | Scope | Result |
|---|---|---|
| No `open()` of any kind | `contracts/**` | **0** — absolute rule retained |
| No filesystem mutation call | `contracts/**` | **0** |
| Every write site guarded by `assert_inside_state_root` | `runtime/**` | **all** |
| No absolute path literal | `runtime/**` | **0** |
| Write outside the state root refused | runtime, dynamic | `PathEscapeError` for repo root, `index.html`, `evidence/…`, `/tmp`, `..` traversal, and a symlink planted inside the root |
| Every §7 target is outside the state root | all six | confirmed |
| No §7 path or §H symbol literal | all `platform/**` except the declaration module | **0** |
| No network / subprocess import | all `platform/**` | **0** |
| No trading, acquisition or model marker | all `platform/**` except the declaration module | **0** |
| Imports are stdlib or `mogo_platform` | all `platform/**` | confirmed against `sys.stdlib_module_names` |
| `platform/__init__.py` absent | — | confirmed |
| stdlib `platform` functional | — | `Darwin` / `3.14.6`, resolved outside the repository |
| Runtime state git-ignored | `platform/runtime/**` | `git check-ignore` confirms database and log |
| Exactly one capability registered, no connectors, no secrets | registry | confirmed |

**The declaration module is exempt from the literal and marker scans** — it must name what it forbids. That exemption is one named file and is itself asserted (`test_the_declaration_module_is_the_only_exemption`).

## 8. Existing Test-Suite Results

**Canonical gate — unaffected:** 17 suites, 947 fixtures, 947 passed, 0 failed, 0 execution errors, zero drift. `tests/run_all.sh` is byte-identical (ADR-012 D-12 gate untouched).

**Pre-existing Python suites — 451 tests, the same six failures:**

`test_expected_node_and_edge_counts` · `test_production_evidence_tree_is_still_genuinely_empty` · `test_production_graph_unchanged_without_real_corpus` · `test_production_graph_unchanged_without_real_knowledge_library` · `test_delta_reports_the_unclosed_risk_gap` · `test_all_195_claims_are_inventoried`

**Identity identical. Count unchanged at 6. Not increased. Not decreased through unauthorized repair.** These predate MOGO-010 and live entirely outside `platform/**`.

## 9. Campaign C1 and Protected Functions

```
C1: verified=33 missing=0 mismatched=0 unlisted=0        → UNCHANGED
Drift: all 63 protected functions and 4 protected constants byte-identical
```

`git status` on `evidence/`, `docs/campaigns/`, the pre-registrations, the verified-replay record, `index.html`, `regression-baseline*`, `docs/TESTING.md`, `docs/KNOWN_ISSUES.md` and `.gitignore`: **empty**.

## 10. Working-Tree State

```
HEAD                     766ee5c5374581adcce2afb3f6684a03ec3cb424
tracked modified         5   (the five planned; see the implementation report)
staged                   0
tags at HEAD             0
untracked (new source)   23
untracked (reports)      11
```

Runtime state directories were removed after validation, so the working tree carries no generated data.

## 11. Pre-Commit Re-Verification (2026-08-07, at commit authorization)

Every validation was re-run immediately before staging. Nothing changed.

| Check | Result |
|---|---|
| Commit boundary == approved 28 files | ✅ **exact** — 0 missing, 0 unapproved, 0 additions |
| Compile | COMPILE OK |
| `-W error` import + stdlib collision guard | IMPORT OK · `Darwin 3.14.6` · 39 event types |
| Platform suites | **11 suites, 450 tests, 450 passed, 0/0/0** |
| Canonical gate | **17 suites, 947 fixtures, 947 passed, 0 failed** |
| Protected-function drift | **0** — 63 functions, 4 constants byte-identical |
| Campaign C1 | **33 verified, 0 missing, 0 mismatched, 0 unlisted** |
| Third-party dependencies | **0** — roots: `argparse, datetime, fcntl, hashlib, json, math, os, re, shutil, sqlite3, sys, types, uuid`, all confirmed against `sys.stdlib_module_names`, plus `mogo_platform` and relative imports |
| Protected paths | `git status` empty on all 11 |
| Staged before staging | 0 |

### 11.1 Deterministic behaviour — unchanged

The capability result hash is identical across three independent runs from a pristine state, identical again after an induced crash and restart, and equal to the value computed independently from the payload:

```
run 1                     result=4a45c52fd69e19841fe5f8b10be04cfbb85031fc516cff13308bab3b192dad5e
run 2                     result=4a45c52fd69e19841fe5f8b10be04cfbb85031fc516cff13308bab3b192dad5e
run 3                     result=4a45c52fd69e19841fe5f8b10be04cfbb85031fc516cff13308bab3b192dad5e
after crash + restart     result=4a45c52fd69e19841fe5f8b10be04cfbb85031fc516cff13308bab3b192dad5e
independently computed    result=4a45c52fd69e19841fe5f8b10be04cfbb85031fc516cff13308bab3b192dad5e
```

### 11.2 `runtime/errors.py` — conflict check, per the commit authorization

Retained. Checked for constitutional and architectural conflict before commit:

| Check | Result |
|---|---|
| Location | inside the approved `platform/` bounded context |
| Imports | `..contracts` only — no stdlib I/O, no network, no subprocess |
| I/O or process calls | **none** |
| Hierarchy | every class descends from `contracts.errors.PlatformError` — one tree |
| Classes | 13 |

**Verdict: no constitutional or architectural conflict. Retained as authorized.**

## 12. Verdict

**Every validation defined in the approved plan passes.** No known Step 1 defect remains within scope. Two items are disclosed rather than resolved: the structural-only `fsync` assertion (§6.2, an inherent limit of in-process testing) and the standing Step 2 gate on effectful capabilities (§5).

**Awaiting commit authorization.**

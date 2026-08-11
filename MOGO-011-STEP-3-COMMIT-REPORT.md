# MOGO-011 STEP 3 — COMMIT REPORT

**Milestone:** MOGO-011 Step 3 — the Policy Gate (the authorization layer)
**Status:** **COMMITTED — NOT PUSHED, NOT TAGGED**
**Date:** 2026-08-08

---

## 1. Commit identity

| | |
|---|---|
| **Commit hash** | `c7527a4b8c6dced08b6753667d8c76042fbfddac` |
| **Parent hash** | `7b2c0aa940d185995305e45a209edf063050e10b` |
| **Parent count** | **1** — linear, no merge |
| Tree hash | `c3800f5c13a6cf36d868e19b14076dd3a126dc87` |
| Subject | `MOGO-011 Step 3: the policy gate` |
| Author / committer | Joe Mogollon `<joemogollon025@gmail.com>` |
| Branch | `main`, upstream `origin/mogo-main` |
| Position | **1 commit ahead of `origin/mogo-main`, 0 behind** |
| Tags at HEAD | **0** — none created |
| Staged after commit | **0** |
| Tracked modifications after commit | **0** |
| `git fsck` | exit 0, no corruption |

The parent is exactly the pushed Step 2 commit. Nothing was amended, rebased, reset, force-created
or merged. History is linear and intact.

---

## 2. Exact file boundary — 21 files

**15 modified, 6 created. 3,921 insertions, 84 deletions.** Every path is under `platform/` (11) or
`tests/` (10). **No other top-level directory appears in the commit.**

| File | + | − |
|---|---:|---:|
| `platform/README.md` | 38 | 0 |
| `platform/src/mogo_platform/runtime/audit.py` | 161 | 7 |
| **`platform/src/mogo_platform/runtime/authorizations.py`** *(new)* | 340 | 0 |
| **`platform/src/mogo_platform/runtime/capabilities/policy_probe.py`** *(new)* | 112 | 0 |
| `platform/src/mogo_platform/runtime/cli.py` | 183 | 7 |
| `platform/src/mogo_platform/runtime/errors.py` | 40 | 0 |
| `platform/src/mogo_platform/runtime/orchestrator.py` | 409 | 28 |
| **`platform/src/mogo_platform/runtime/policy.py`** *(new)* | 329 | 0 |
| `platform/src/mogo_platform/runtime/projection.py` | 154 | 5 |
| `platform/src/mogo_platform/runtime/registry.py` | 86 | 5 |
| `platform/src/mogo_platform/runtime/schema.py` | 101 | 3 |
| `tests/platform/test_platform_boundaries.py` | 20 | 9 |
| **`tests/platform/test_runtime_authorization.py`** *(new)* | 316 | 0 |
| `tests/platform/test_runtime_capability.py` | 28 | 7 |
| `tests/platform/test_runtime_end_to_end.py` | 3 | 1 |
| **`tests/platform/test_runtime_policy_gate.py`** *(new)* | 758 | 0 |
| `tests/platform/test_runtime_projection.py` | 4 | 0 |
| `tests/platform/test_runtime_recovery.py` | 450 | 0 |
| **`tests/platform/test_runtime_review_disposition.py`** *(new)* | 370 | 0 |
| `tests/platform/test_runtime_store_schema.py` | 16 | 12 |
| `tests/run_platform_tests.sh` | 3 | 0 |

**Governed documentation in scope:** `platform/README.md` — the tracked repository documentation
describing the platform, updated with the policy gate, the disposition path, the classification
traps and the new operator commands. It is the only documentation file in the boundary.

**Staging method.** All 21 paths were passed to `git add` **explicitly and individually**. Neither
`git add .`, `-A` nor `--all` was used. Before committing: staged count verified as exactly **21**,
partially-staged files **0**, and staged paths outside `platform/`/`tests/` **0** — so the committed
content is byte-identical to the validated working tree.

---

## 3. What was deliberately excluded

**28 untracked documents remain uncommitted**, exactly as before:

| Excluded | Count |
|---|---:|
| MOGO-010 reports | 7 |
| MOGO-011 Step 1 reports | 5 |
| MOGO-011 Step 2 reports (plan, governance, implementation, validation, commit, push) | 6 |
| MOGO-011 Step 3 reports (plan, governance, implementation, validation) | 4 |
| MOGO-011 engineering notebook · repository config report | 2 |
| Legacy documents (2026-08-04, disposition still open) | 4 |

Also excluded: `tests/run_all.sh` (ADR-012 D-12) · `docs/TESTING.md` · `docs/KNOWN_ISSUES.md` ·
`regression-baseline*` · every protected path · any package manifest or lock file (none exists).

**Verified after the commit:** the commit's own file list contains **0** matches for report
documents, notebooks, `evidence/`, `docs/campaigns`, `index.html`, `hypothesis-registry.json`,
`run_all.sh` or `regression-baseline`.

---

## 4. Validation results

Every gate was run **immediately before** staging, and the principal gates re-run **after** the
commit against the committed tree. Bytecode was purged before each run.

### Confirmed as required

| Gate | Required | Result |
|---|---|---|
| Platform tests | 740/740 | ✅ **17 suites · 740 tests · 740 passed · 0 failures · 0 errors · 0 skipped** |
| Canonical regression | 947/947 | ✅ **17 suites · 947 fixtures · 947 passed · 0 failed · 0 execution errors** |
| Campaign C1 | 33/33 | ✅ **33 verified · 0 missing · 0 mismatched · 0 unlisted** |
| Protected-function drift | 0 | ✅ **63 functions · 4 constants · drift 0** |
| Mutation protocol | 21/21, 0 survivors | ✅ **21 applied · 21 detected · 0 survivors** |
| Deterministic replay/recovery | INTEGRITY OK | ✅ **REBUILT 55 events, 38 transitions · INTEGRITY OK** |
| Frozen C1 evidence modified | none | ✅ **0** |
| Unrelated repository files included | none | ✅ **0** |

### Post-commit, against the committed tree

| Gate | Result |
|---|---|
| Platform suite | **740/740**, 0/0/0 |
| Canonical gate | **947/947**, 0 failed |
| Campaign C1 | **33/33** |
| Protected-function drift | **0** |
| `demo` + `reset --rebuild-index` + `verify` | exit 0 · **REBUILT** · **INTEGRITY OK** |
| Frozen artifacts dirty / in commit | **0 / 0** |
| `git fsck` | exit 0 |

### Mutation protocol — source integrity

The 21 mutations were applied to committed source, bytecode purged between each, reverted, and every
file re-hashed. **All source files verified byte-identical to their pre-mutation hashes** after the
run; no leftover backup remained.

Three mutations exist specifically to guard the defects found by the crash-boundary tests:

| # | Mutation | Outcome |
|---:|---|---|
| 19 | strand a task in `blocked` (revert the G-5 fix) | DETECTED |
| 20 | drop the `blocked → awaiting_review` recovery path | DETECTED — **by non-termination** |
| 21 | let `verify` miss a terminal state with no event (revert the G-6 fix) | DETECTED |

---

## 5. The two defects the crash-boundary tests discovered

The previous implementation report recorded these four boundaries as *declared and reachable but not
tested*, carried on the argument that every gate transition is a single event under the unchanged
write protocol. **That argument was wrong in one place, and writing the tests is what proved it.**

### G-5 — a crash between the denial and the review request **stranded the task**

**Found by:** designing the boundary-24 test.

A denial emits `AcquisitionDenied` and then `HumanReviewRequired` as two events. A crash between them
left the task in `blocked` — which is **not terminal**, was **not in the drivable set**, and had **no
route out at all**. It could neither be reviewed nor reach a terminal outcome: the Constitution §6.5
stranding defect that Step 2 eliminated for failures, reintroduced on the policy path.

**Verified before fixing**, by forcing the exact post-crash state and running `recover()` +
`run_once()`: the task stayed in `blocked` and `advanced` was empty.

**Fix — in the runtime.** `blocked` was added to the drivable set, and `_request_review()` completes
the interrupted transition. It **re-states the durable decision and never re-makes it**: every field
falls back to the recorded task row, so recovery cannot reach a different answer than the one already
in the log. Confirmed by `test_boundary_24_recovery_restates_the_decision_it_does_not_remake_it`,
which records an authorization *after* the crash and asserts the decision remains the recorded denial.

### G-6 — `verify` reported a **false FATAL** for every suppressed task

**Found by:** the boundary-26 test's `verify` assertion.

The Step 2 terminal-state check used a static map of event names (`TaskSucceeded → succeeded`,
`TaskDeadLettered → dead_lettered`). `suppressed` is reached by a **payload-dependent** transition —
`HumanReviewCompleted(rejected)` — which a static map cannot express, so `verify` emitted:

> `FATAL  task … is terminal in state 'suppressed' but no event in the log carries that transition`

**This was not a crash artefact.** It was confirmed to occur in **ordinary operation**, with no crash
involved, for any rejected task — the crash test simply surfaced it.

**Fix — in the runtime.** The check now resolves the edge through
`projection.resolved_transition()`, the same fix and the same reasoning as finding G-1 in the audit
timeline.

---

## 6. Confirmation: the fixes corrected the underlying defects

**Confirmed. Neither defect was accommodated by weakening a test, and no governance constraint was
relaxed.**

| | G-5 | G-6 |
|---|---|---|
| Where the change was made | `runtime/orchestrator.py` | `runtime/audit.py` |
| Was a test assertion weakened? | **No** | **No** |
| Was a governance rule relaxed? | **No** — the fix *restores* Constitution §6.5 | **No** — the fix *restores* the check's intent |
| Guarded against regression by | mutations 19 and 20 | mutation 21 |
| Behavioural test | `test_boundary_24_crash_between_the_denial_and_the_review_request` | `test_boundary_26_crash_after_a_REJECTION_is_appended` |

**One test expectation of mine was corrected, and it was not a defect.** Two boundary-test failures
came from an assertion I had written incorrectly: I asserted `verify` is clean before recovery at
every boundary. That is wrong for an *append* boundary, where the index is legitimately behind the
log and `verify` **must** report the gap and prescribe `recover`. The test now distinguishes the two
kinds of boundary and asserts each one's actual property — a stronger assertion than the one it
replaced, because it also proves the runtime *reports* the gap rather than hiding it. No production
behaviour changed as a result.

### What boundaries 23–26 assert

Each is exercised by a real `os._exit(70)` in a child process — no mocks, no unwinding, no flush.
At every boundary, from the durable log and the rebuilt index:

- **no fabricated authorization** — `acquisition_authorizations` stays empty
- **no fabricated claim or execution** — none of `TaskClaimed`, `TaskStarted`, `TaskSucceeded`,
  `TaskFailed`, `AcquisitionAuthorized`; `attempt` stays 0; no `task_attempts` row
- **the gate is never bypassed** — the recorded decision remains a denial; the task remains blocked
- **no invalid state transition** — every recorded edge checked against `is_legal_transition`
- **the append-only history is never contradicted** — no FATAL; the index never claims history the
  log does not have
- **no unauthorized work executes** — re-asserted after running twice more
- **recovery is deterministic and auditable** — rebuild from the log alone, then `verify` clean

Plus five sequential kills converging to the same answer as an uninterrupted run.

---

## 7. Confirmation: Campaign C1 and protected scientific artifacts are unchanged

**Confirmed, three independent ways.**

1. **By content.** All 33 Campaign C1 artifacts were re-read and re-hashed against
   `docs/campaigns/C1/CAMPAIGN_C1_EVIDENCE_MANIFEST.md`, **before staging and again after the
   commit**: 33 verified, 0 missing, 0 mismatched, 0 unlisted.
2. **By working tree.** `git status` over `evidence/`, `docs/campaigns/`, `index.html`,
   `hypothesis-registry.json`, `docs/MOGO-003-VERIFIED-REPLAY-RECORD.md` and
   `docs/trader-intelligence/governance/` reports **0 modified**.
3. **By commit contents.** The commit's file list contains **0** paths under `evidence/` or
   `docs/campaigns/`, and no `index.html` or `hypothesis-registry.json`.

**Protected-function drift is 0** — 63 protected functions and 4 protected constants byte-identical
to the committed baseline, verified before and after the commit.

The platform still has **no write path** to any protected target: the boundary suite's AST scan
proves no prohibited literal appears as a write argument anywhere under `platform/**`, and every
runtime write site is confined by `assert_inside_state_root`.

---

## 8. Remaining carried items

**Risk A-5 — carried into Step 4 verbatim, severity unchanged (High).** Step 3 registers no effectful
capability and opens none of the gate's four preconditions; the gate test still asserts all four are
`False`.

**Connector gates after Step 3:**

| Gate | Status |
|---|---|
| `policy_gate` | ✅ **MET** — classification, authorization records, enforcement tests |
| `a5_result_store` | ❌ unmet |
| `first_connector_authorization` | ❌ unmet (ADR-012 D-15 approved in principle, not authorized) |
| `acquisition_authorization_record` | ❌ unmet — the mechanism exists; records for real sources do not |

**No connector may exist until the remaining three are met.**

**Deferred, with triggers named:** policy re-evaluation on version change (C-5 — first acquisition
producing a retained artifact) · lease renewal · deterministic jitter · capability-lifecycle events ·
cancellation · the review *workflow* of Architecture §22.

**Carried from Steps 1–2, unchanged:** A-3, A-4, A-6, A-7, A-8 · `fsync` asserted structurally only ·
wall-clock dependence · boundary-20 attempt consumption · non-replayable observation tables
(`capabilities`, `runs`, `acquisition_authorizations`).

**Repository-wide, still open:** package manifest (D-01) · canonical runner integration (D-12) ·
disposition of the four legacy untracked documents · branch-naming policy (`main` tracks `mogo-main`
while a separate `origin/main` exists) · the redundant local `user.name` in `.git/config`.

**Explicitly not touched, as instructed:** the separate evidence-export confirmation issue · ALEX
forward paper trading · MOGO-011 Step 4.

---

## 9. State

| | |
|---|---|
| Committed | ✅ `c7527a4b8c6dced08b6753667d8c76042fbfddac` |
| Pushed | ❌ **not pushed — `origin/mogo-main` is still at `7b2c0aa9…`** |
| Tagged | ❌ no tag created |
| Working tree | 0 tracked modifications · 0 staged · 28 untracked documents (29 with this report) |
| Next gate | **explicit push authorization** |

**Stopped here as instructed. No push was attempted. No tag was created. Step 4 has not begun.**

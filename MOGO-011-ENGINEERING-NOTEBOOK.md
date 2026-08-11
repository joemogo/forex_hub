# MOGO-011 — ENGINEERING NOTEBOOK

> **Living document.** Overwritten as the milestone progresses. Untracked, unstaged, excluded from every commit boundary unless separately authorized.

**Last updated:** 2026-08-09 · **Milestone:** MOGO-011 — Runtime Kernel and First Executable Automation
**Current gate:** Step 3 — ✅ **COMPLETE. Committed, validated in a fresh session, and pushed. Awaiting owner authorization for Step 4.**

---

## 1. Current pushed baseline

| | |
|---|---|
| Repository | `/Users/joemogollon/Desktop/Forex Hub` |
| Branch | `main` |
| HEAD | `c7527a4b8c6dced08b6753667d8c76042fbfddac` |
| Upstream | `origin/mogo-main` @ `c7527a4b8c6dced08b6753667d8c76042fbfddac` |
| Sync | **ahead 0, behind 0 — synchronized** |
| Working tree | **0 tracked modifications, 0 staged** — 29 untracked MOGO report documents only |
| Protected paths | clean — 0 modified |
| Runtime state | git-ignored; verified for database, log, tasks and quarantine |
| Tags at HEAD | **0** (19 pre-existing repository tags, none created this milestone) |
| Python | 3.14.6 · SQLite 3.53.3 · `fcntl` available · third-party dependencies **0** |

**Commit chain:** `766ee5c` (MOGO-010) → `c50f95c` (Step 1) → `7b2c0aa` (Step 2) → `c7527a4` (Step 3).
Linear, no merges, no rewrites after push.

---

## 2. Step 1 completion status — ✅ COMPLETE

Committed `c50f95c`, pushed to `origin/mogo-main`, fast-forward, history intact. Full record in
`MOGO-011-STEP-1-{PLAN, IMPLEMENTATION-REPORT, VALIDATION-REPORT, COMMIT-REPORT, PUSH-REPORT}.md`.

---

## 3. Step 2 completion status — ✅ COMPLETE

Committed `7b2c0aa`, pushed, fast-forward. Governance B-1 … B-5 all approved (2026-08-08); record in
`MOGO-011-STEP-2-GOVERNANCE-RECORD.md`. **27 files: 7 created, 20 modified.**

| Gate | Result |
|---|---|
| Platform suite | 14 suites · 622 tests · 622 passed · 0/0/0 |
| Canonical gate | 17 suites · 947 fixtures · 947 passed |
| Mutation protocol | 27 applied · 27 detected · 0 survivors |
| Crash boundaries 12–22 | all pass, real `os._exit(70)` |

**The change that mattered most was not a feature.** Step 1 left a failing task in `failed`, which is
not terminal — a direct violation of Constitution §6.5. Every failure path now reaches a visible
terminal outcome, over all thirteen error classifications.

Findings F-5 … F-9 and deviations I-1 … I-3 are recorded in `MOGO-011-STEP-2-IMPLEMENTATION-REPORT.md`
and `MOGO-011-STEP-2-VALIDATION-REPORT.md`.

---

## 4. Step 3 governance — ✅ ALL FIVE DECIDED (2026-08-08)

Recorded in full in `MOGO-011-STEP-3-GOVERNANCE-RECORD.md`.

| | Decision | Outcome |
|---|---|---|
| **C-1** | A denied task enters `blocked`; an explicit audited operator decision is required before it may proceed | ✅ APPROVED — the committed contract fixes the path: `legal_successors("blocked")` is `('awaiting_review', 'cancelled')`, so the decision acts on `awaiting_review` under `review_gate` authority |
| **C-2** | One acquisition-class capability that **acquires nothing**, so the gate's orchestrator integration is provable | ✅ APPROVED |
| **C-3** | Authorization records are governance **input** — append-only, non-replayable; the **decision** replays, carrying the record's content hash | ✅ APPROVED |
| **C-4** | `policy_blocked` reserved for runtime enforcement; a gate denial is a **state**, not an error class | ✅ APPROVED |
| **C-5** | Policy re-evaluation deferred, trigger named | ✅ APPROVED |

---

## 5. Step 3 implementation status — ✅ COMMITTED AND PUSHED

**21 files: 6 created, 15 modified. +3,921 / −84.** Zero new dependencies. Every path under
`platform/` (11) or `tests/` (10).

**No vocabulary extension.** Unlike Steps 1 and 2, no new event, command or state was needed —
`contracts/vocabulary.py` and `contracts/task_states.py` are **both untouched**. Three states
approved in MOGO-009 that no event had ever reached are now used: `blocked`, `awaiting_review`,
`suppressed`.

### 5.1 What Step 3 corrects

An acquisition-class task previously recorded `PolicyEvaluated {"decision": "not_applicable",
"operationClass": null, "reason": "routed to failure"}`, then `TaskClaimed → TaskStarted →
TaskFailed → TaskDeadLettered`. **Three statements were false.** The gate had not found the policy
inapplicable — it refused because no gate existed. The operation class was `acquisition`, recorded as
`null`. And the claim and start events asserted an execution **that never occurred**, emitted only to
reach `running` so a `TaskFailed` could be appended.

The outcome was fail-closed; the record of it was a fabrication. Constitution §4.20 requires every
governed decision to be auditable. **An audit trail that misstates the decision is worse than a
missing one, because it will be believed.**

### 5.2 Design points worth remembering

- `policy.evaluate()` is **pure** — no clock, no connection, no I/O. Deny is the default, reached by
  twelve distinct routes; a permit only by satisfying every rung.
- **`UNKNOWN` is guarded twice**, because Constitution §5.2 states its rule absolutely: once by the
  Catalog §M table, and once before the table is consulted.
- **`AS_RECORDED` is not an allowance.** `PERMITTED_EXPLICIT_LICENSE` and
  `PERMITTED_DOCUMENTED_POLICY` mark every operation `AS_RECORDED` — "whatever the licence says".
  Treating that as permission would have made the two most nuanced statuses the most permissive.
- **`discover` is governed exactly as `metadata`** (Architecture §20.2): the minimum-metadata
  allowance expires the instant a classification is recorded, and a laxer rule afterwards would be
  the drip-feed loophole that section exists to close.
- **Bypass is structurally impossible via six independent mechanisms:** `requested → queued` is not a
  legal edge; `policy_check` is the only entry to `queued` for a new task; the decision has exactly
  two **named** call sites; no other runtime module may consult it; it takes no override argument and
  reads no environment variable; and an acquisition-class task is re-checked against its own recorded
  permit immediately before it is claimed.
- **A human may un-block a task. Only the gate may authorize the acquisition.** An approval
  re-evaluates the gate and is refused while it still denies, so a reviewer can never stand in for an
  Acquisition Authorization Record (Constitution §5.1).

---

## 6. Step 3 findings — two defects, both fixed at source

| | Finding | Kind | Resolution |
|---|---|---|---|
| **G-5** | A crash between the denial and the review request **stranded the task in `blocked`** — not terminal, not drivable, no route out: the Constitution §6.5 defect Step 2 eliminated for failures, reintroduced on the policy path | real defect | `blocked` made drivable and the interrupted transition completed, which **re-states** the durable decision and never re-makes it |
| **G-6** | `verify` reported a **false FATAL for every suppressed task**. The terminal-state check used a static map of event names, and `suppressed` is reached by a payload-dependent transition. **Not a crash artefact — it occurred in ordinary operation** | real defect | Resolved the edge through `projection.resolved_transition()` |

**Both were fixed in the runtime. No test was weakened to accommodate either.** Both were found by
the crash-boundary tests, not by review.

---

## 7. Step 3 disclosed deviations — four

| | Deviation | Why |
|---|---|---|
| **J-1** | `commands.input_refs_json` added | The gate resolves an acquisition's subject source from `inputRefs` (Catalog §A: identifiers only) |
| **J-2** | The decision has **two** call sites, not one | An approval must re-evaluate the gate or it can never lead to execution. Both are asserted **by name** |
| **J-3** | `CONNECTOR_GATES` marks `policy_gate` satisfied | The other three remain unmet and are asserted unmet by name |
| **J-4** | `blocked` added to the drivable set, plus two test-only CLI hooks | Both required by finding G-5 |

---

## 8. Step 3 mutation protocol — 21/21, and the one worth reading

**21 applied · 21 detected · 0 survivors**, after two genuine gaps were found and closed and three
further mutations were added to guard the G-5/G-6 defects.

- **M10.** `_policy_target` resolves an unreadable decision to `blocked`, and nothing tested it. The
  review-side equivalent *was* tested; the policy-side one had simply been missed.
- **M14 is the instructive one.** `test_a_bare_approval_is_refused` existed and passed — **but for
  the wrong reason.** With the reason check removed, the approval was still refused, because the gate
  re-evaluation refused it first. The test named one guard and was actually exercising another.
  Closed by testing a bare **rejection**, which does not re-evaluate the gate.

  **A test that passes because a different guard fired is not evidence of the guard it names.** The
  mutation protocol surfaced that — the third time across this milestone it has found something
  review would not have.

**M20 is detected by non-termination** rather than by failure: dropping the `blocked →
awaiting_review` recovery path leaves `run_once` with a task that never leaves the drivable set.

---

## 9. Fresh-session verification and push (2026-08-09)

Step 3 was re-verified in a **fresh session that assumed no prior state**, then pushed. Full record in
`MOGO-011-STEP-3-PUSH-REPORT.md`.

| Gate | Pre-push | Post-push |
|---|---|---|
| Platform suite | **17 suites · 740 tests · 740 passed · 0/0/0** | **740/740** |
| Canonical gate `tests/run_all.sh` | **17 suites · 947 fixtures · 947 passed** | **947/947** |
| Campaign C1 | **33 verified · 0 missing · 0 mismatched · 0 unlisted** | **33/33** |
| Protected-function drift | **63 functions · 4 constants · drift 0** | **drift 0** |
| Mutation protocol | **21 applied · 21 detected · 0 survivors** | — |
| Deterministic replay | **REBUILT 55 events, 38 transitions · INTEGRITY OK** | — |
| Frozen C1 evidence (42 files) | SHA-256 snapshot taken | **byte-identical** |

C1 was verified by **re-hashing all 33 artifacts from disk** and re-parsing the manifest, not by
reading the validation report — 13,575,486 bytes, matching the manifest exactly. The mutation
protocol was **re-executed in full**, reproducing the original per-mutation failure counts. Replay
ran under an isolated scratchpad `--state-root`, touching no real runtime state.

Push: `git push origin HEAD:mogo-main` → `7b2c0aa..c7527a4` — **fast-forward, no force, no tags, no
rewrite.** Remote read back from the server with `git ls-remote`.

---

## 10. Risks

**A-5 — carried into Step 4, severity unchanged (High).** Step 3 **meets the policy-gate
precondition** and opens none of the other three. The commit asserts them unmet **by name**:

1. the A-5 result store (idempotency-keyed), output verification by re-hash, duplicate-effect
   prevention and the post-execution recovery rule — all four declared as data, all four `False`;
2. the first-connector authorization;
3. a governance-supplied Acquisition Authorization Record per real source.

**No connector may exist until all three land.** Step 3 adds no connector, no network, no source
registry, no artifact registry, no secrets, no ingestion adapter and no effectful capability.

**Also carried unchanged:** A-3 · A-4 · A-6 (`fcntl` is POSIX-only) · A-7 · A-8 · `fsync` asserted
structurally only · wall-clock dependence · a mid-execution crash consumes an attempt (deliberate) ·
`capabilities`, `runs` and `acquisition_authorizations` are not replayable (all named in the schema) ·
a manifest could declare `pure` while being effectful, which the **static** scan catches rather than
the registry.

---

## 11. Milestone progress

| Phase | Status |
|---|---|
| Step 1 — plan → gate → implement → validate → commit → push | ✅ complete |
| Step 2 — plan → gate (B-1 … B-5) → implement → validate → commit → push | ✅ complete |
| Step 3 — plan | ✅ complete |
| Step 3 — design gate (C-1 … C-5) | ✅ cleared 2026-08-08 |
| Step 3 — implementation | ✅ complete |
| Step 3 — validation | ✅ complete — all gates pass |
| Step 3 — implementation gate (human approval) | ✅ cleared |
| Step 3 — commit `c7527a4` | ✅ complete |
| Step 3 — **fresh-session verification and push** | ✅ **complete 2026-08-09** |
| Step 3 — tag | ⛔ **not created — not authorized** |
| **Step 4** | ⛔ **not started, not authorized** |

---

## 12. Exact next action

**Await owner authorization.** Nothing further is authorized: Step 4 has not been started, no tag has
been created, the separate 222-package evidence-export confirmation issue has not been investigated,
and ALEX forward paper trading remains disabled.

`origin/mogo-main` = `HEAD` = `c7527a4b8c6dced08b6753667d8c76042fbfddac`, 0 ahead / 0 behind.

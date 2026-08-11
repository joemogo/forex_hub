# MOGO-011 STEP 2 — GOVERNANCE DECISION RECORD

**Milestone:** MOGO-011 Step 2 — retry, lease and dead-letter
**Baseline at decision time:** `c50f95ca839fd41f75e56f93997d82928261f0b3` (`origin/mogo-main`, synchronized)
**Decision date:** 2026-08-08
**Decided by:** operator (owner), recorded verbatim by the implementer
**Source of the decisions:** `MOGO-011-STEP-2-PLAN.md` §40, decisions B-1 … B-5
**Status:** **ALL FIVE DECIDED. Design gate CLEARED. Implementation authorized.**

---

## 1. Repository verification performed before recording

Every check below was executed against the working tree, not assumed.

| # | Check | Result |
|---|---|---|
| 1 | `git rev-parse HEAD` | `c50f95ca839fd41f75e56f93997d82928261f0b3` ✅ |
| 2 | HEAD equals the authorized commit | ✅ exact match |
| 3 | `origin/mogo-main` remote ref | `c50f95ca839fd41f75e56f93997d82928261f0b3` ✅ identical |
| 4 | Current branch | `main`, upstream `origin/mogo-main` ✅ |
| 5 | Tracked modifications | **0** ✅ |
| 6 | Staged changes | **0** ✅ |
| 7 | Untracked | 18 documents (17 from the Step 2 plan inventory + this record) — no source file ✅ |
| 8 | Platform test suite | **11 suites, 450 tests, 450 passed, 0 failures, 0 errors, 0 skipped** ✅ |
| 9 | Canonical repository gate `tests/run_all.sh` | **17 suites, 947 fixtures, 947 passed, 0 failed** ✅ |
| 10 | Protected-function drift | **63 functions, 4 constants, drift 0** ✅ |

The repository matches the pushed commit exactly. No repair, reset, rebase, merge, amend, branch switch or configuration change was performed, and none was needed.

---

## 2. The five decisions, as recorded

### B-1 — `TaskRetryReleased` — **APPROVED** *(was BLOCKING)*

The event vocabulary is extended additively from **39 to 40** names with `TaskRetryReleased`, carrying the Catalog §L transition `retry_scheduled → queued` under **orchestrator** authority.

Nothing is renamed, removed or repurposed. The addition is recorded in `contracts/vocabulary.py` beside the MOGO-011 Step 1 F-2 extension, with the same form of authorization comment.

*Consequence of the approval:* task state remains derivable from the log alone, and ADR-012 D-05 is preserved. This was the one decision that blocked implementation; it is now cleared.

### B-2 — `jitterMs = 0` — **APPROVED**

The Architecture §19 / §18.1 / §26 instruction "backoff **with jitter**" is deviated from, deliberately and on the record. Step 2 sets `jitterMs = 0`.

Conditions carried with the approval, all of which the implementation must satisfy:

- the `jitterMs` field is **retained** in the retry policy, so Catalog §C's `retryPolicy` shape is unchanged and nothing is removed;
- the value is **governed** — declared per capability, validated at registration, and recorded in the `TaskRetryScheduled` payload so an auditor sees the value that was in force;
- randomness is made **structurally unavailable**: `random` and `secrets` are banned imports across `platform/**`;
- the future extension is named now, so a later step does not reach for `random`: deterministic jitter derived from the task identifier.

*Deviation is disclosed, not silent.* Recorded in the architecture drift check.

### B-3 — Review-routing class handling — **APPROVED**

`source_mutated` and `human_review_required` (Catalog §K: `retryable=False`, `terminal=False`, `routesToReview=True`) are handled as follows:

- **prohibited at registration** — a capability manifest declaring either class is refused, naming the missing review gate;
- **dead-lettered fail-closed at runtime** with `deadLetterReason = "requires_review_no_gate"`, the dead-letter event recording that a review gate would have been the correct destination.

The finding behind this decision stands on the committed contract, not on preference: `legal_successors("failed")` is `('cancelled', 'dead_lettered', 'retry_scheduled')` — **there is no `failed → awaiting_review` edge**, and no review gate exists behind one. Inventing the edge was rejected; stranding the task in `failed` was rejected as a direct violation of Constitution §6.5.

*This is a narrowing of Catalog §K coverage and is disclosed as such.* It is reversible by a future step that builds the review gate.

### B-4 — Risk A-5 = **Option A** — **RATIFIED**

Step 2 remains limited to **pure capabilities**. Registration of an effectful capability is **mechanically prohibited** by a registry gate whose four preconditions are declared as data and are all `False`:

```
idempotencyKeyedResultStore  = False
outputVerificationByRehash   = False
duplicateEffectPrevention    = False
postExecutionRecoveryRule    = False
```

A test asserts all four are `False`, so a future step that builds the result store **breaks a test named after the gate** and forces a conscious governance decision at the moment the gate opens.

*What ratification does not mean.* A-5 is closed by **prohibition**, not by construction. Step 2 adds no output verification, no result store and no duplicate-effect prevention. **The hazard is unchanged and carries forward to Step 3 verbatim, at severity High.**

### B-5 — `MAX_ATTEMPT_LIMIT = 10` — **APPROVED**

A runtime ceiling of 10 total attempts is enforced at submit. A command declaring more is **rejected**, with the reason recorded in `command_submissions` and a `CommandRejected` event appended.

Catalog §A sets no upper bound on `attemptLimit`; Constitution §11 requires retry to be *bounded*. The ceiling reconciles the two without contradicting the Catalog, and is a single named constant an operator can find.

---

## 3. What these decisions do **not** authorize

Recorded so the boundary of the authorization is unambiguous.

- No feature expansion beyond the plan's §27–§28 file inventory.
- No architectural redesign. `contracts/task_states.py` is **not** modified — every Step 2 edge already exists in the committed contract with the correct authority.
- No policy gate, no connector, no acquisition, no effectful capability, no second process, no daemon, no network of any kind.
- No change to any protected path, frozen campaign, evidence artifact, governance document or scientific record.
- No new third-party dependency, package manifest or lock file.

---

## 4. Standing requirements attached to the implementation

Carried from the authorization and binding on every step that follows:

1. **Deterministic replay preserved** — no time value is ever recomputed during projection; every one is copied from a payload written once.
2. **Scientific reproducibility preserved** — Campaign C1 and protected-function drift are verified before implementation, after implementation, and again before commit.
3. **Zero protected-function drift.**
4. **Campaign C1 integrity** — 33/33, untouched.
5. **No shortcuts.** Optimize only where behaviour is provably equivalent.

---

## 5. Gate status

| Gate | Status |
|---|---|
| Step 2 baseline verification | ✅ complete (§1) |
| Step 2 plan review | ✅ complete — read in full, 1,912 lines |
| **Step 2 design gate (B-1 … B-5)** | ✅ **CLEARED — all five decided** |
| Step 2 implementation | ▶ **authorized, proceeding** |
| Step 2 validation | ⏳ not reached |
| Step 2 implementation gate / commit / push | ⏳ not reached — requires human approval |

**Nothing was implemented, staged, committed, tagged or pushed before this record was written.**

# MOGO-011 STEP 3 — GOVERNANCE DECISION RECORD

**Milestone:** MOGO-011 Step 3 — the Policy Gate (the authorization layer)
**Baseline at decision time:** `7b2c0aa940d185995305e45a209edf063050e10b` (`origin/mogo-main`, synchronized)
**Decision date:** 2026-08-08
**Decided by:** operator (owner), recorded verbatim by the implementer
**Source:** `MOGO-011-STEP-3-PLAN.md` §5, decisions C-1 … C-5
**Status:** **ALL FIVE DECIDED. Design gate CLEARED. Implementation authorized.**

---

## 1. Repository verification performed before recording

| # | Check | Result |
|---|---|---|
| 1 | `git rev-parse HEAD` | `7b2c0aa940d185995305e45a209edf063050e10b` ✅ |
| 2 | `origin/mogo-main` | identical — **ahead 0, behind 0** ✅ |
| 3 | Tracked modifications | **0** ✅ |
| 4 | Staged | **0** ✅ |
| 5 | Platform suite | **14 suites · 622 tests · 622 passed** ✅ |
| 6 | Canonical gate | **17 suites · 947 fixtures · 947 passed** ✅ |
| 7 | Campaign C1 | **33 verified · 0 missing · 0 mismatched · 0 unlisted** ✅ |
| 8 | Protected-function drift | **63 functions · 4 constants · drift 0** ✅ |
| 9 | Third-party dependencies | **0** ✅ |

---

## 2. The five decisions, as recorded

### C-1 — Disposition of a blocked task — **APPROVED exactly as recommended (Option D)**

- A denied task enters **`blocked`**.
- An **explicit, audited operator decision** is required before the task may transition onward.
- Complete auditability and deterministic state transitions are preserved.

**The committed contract fixes the intermediate state, and the implementation follows it.**
`legal_successors("blocked")` is `('awaiting_review', 'cancelled')` — there is **no
`blocked → queued`** and **no `blocked → suppressed`** edge. The audited operator decision therefore
acts on `awaiting_review`, which is exactly the path Option D specified and which Catalog §L assigns
to the `review_gate` authority:

```
policy_check --deny--> blocked --> awaiting_review --operator decision--> queued | suppressed
```

Recorded explicitly because the approval text compresses the path to "blocked → queued or
suppressed"; the approval was "exactly as recommended", and Option D as written in the plan §5 routes
through `awaiting_review`. Taking the shortcut would require inventing a Catalog §L edge, which no
decision authorizes.

**Conditions carried with the approval:**

- The operator decision records **reviewer identity, decision, reason, timestamp and policy version**
  (Constitution §9). **A bare approval is invalid** — a missing reason is refused.
- The reviewer identity may **never** be a worker or a capability (Constitution §14, Catalog §N).
- `suppressed` is terminal, so **every denied task reaches a visible terminal outcome** or is
  explicitly released back to `queued` — Constitution §6.5 preserved.
- This is a **minimal disposition path, not a review system**: no queue, no assignment, no
  notification, no workflow. The review workflow of Architecture §22 remains deferred.

### C-2 — Acquisition-class demonstration capability — **APPROVED**

One capability declaring `operationClass: acquisition` and `effectClass: pure`, which **acquires
nothing**. Its sole purpose is to be classified as acquisition-class so the gate engages, making the
orchestrator integration provable end to end rather than only in unit tests.

It has no fetch path of any kind, and the boundary tests continue to prove that no module under
`platform/**` can reach a network, a subprocess, a clock outside `clock.py`, or any path outside the
runtime state root.

### C-3 — Authorization records are governance **input** — **APPROVED**

Acquisition Authorization Records are supplied by governance or legal review and are **recorded and
enforced** by the platform, never minted by it (Constitution §5.9, Architecture §20.1). They are
stored in an append-only table and are marked **non-replayable**, alongside `capabilities` and
`runs`.

**Replay determinism is preserved by recording the decision, not the input.** Every gate decision
event carries `authorizationId`, `policyStatus`, `policyVersion`, `decisionAuthority`, the permitted
operations in force, and **a content hash of the authorization record as it stood at decision time**.
Replay re-applies the recorded decision and never re-derives it, so a later edit to a record cannot
rewrite history — Constitution §5.7 made mechanical.

### C-4 — `policy_blocked` reserved for runtime enforcement — **APPROVED**

| Meaning | Mechanism | Outcome |
|---|---|---|
| The **gate denies authorization** at `policy_check` | a **state transition** | `policy_check → blocked` |
| A capability or connector attempts an operation **outside its authorization** during execution | the **error class** `policy_blocked` | `running → failed → dead_lettered`, never retried |

Both remain never-retryable. This changes the observable outcome of an acquisition-class task from
`dead_lettered` to `blocked` — a deliberate behaviour change, and the correction of finding F-1.

### C-5 — Policy re-evaluation deferred, trigger named — **APPROVED**

Architecture §20.3's re-evaluation task is deferred: Step 3 has no source registry and no retained
acquisitions to re-evaluate. **Trigger recorded: the first acquisition that produces a retained
artifact.** The gate records `policyVersion` on every decision precisely so re-evaluation remains
possible.

---

## 3. What these decisions do **not** authorize

- No connector of any kind. No network, no socket, no HTTP.
- No source discovery, source registry, educator registry or raw artifact registry.
- No transformation pipeline, ingestion adapter, or Research Acquisition Worker.
- No secrets or `secretRef` resolution (ADR-012 D-09 remains at option (d)).
- No retention policy (D-10), no scheduler, no daemon, no second process.
- No review queue or workflow system beyond the minimal disposition path of C-1.
- **No effectful capability** — risk A-5 remains closed by prohibition, and Step 3 opens none of its
  four preconditions.
- No scientific write of any kind; no change to any protected path.
- **No vocabulary extension** — `contracts/vocabulary.py` and `contracts/task_states.py` are not
  modified. Every state, edge, event and command Step 3 needs is already approved.

---

## 4. Standing requirements attached to the implementation

1. **Deterministic execution** — the gate decision is a pure function of recorded values.
2. **Replay determinism** — replay re-applies recorded decisions and never re-derives them.
3. **Append-only event history** — no new write path; every decision rides inside the existing
   `_emit` protocol.
4. **Immutable evidence** — no scientific path exists.
5. **Zero protected-function drift.**
6. **Campaign C1 integrity** — 33/33, verified before, during and after.
7. **Zero third-party dependencies.**
8. **Offline execution** — proven structurally, not asserted.

Every authorization decision must be **explicit, auditable, deterministic, reproducible,
fail-closed, and impossible to bypass.**

---

## 5. Gate status

| Gate | Status |
|---|---|
| Step 3 baseline verification | ✅ complete |
| Step 3 plan review | ✅ complete |
| **Step 3 design gate (C-1 … C-5)** | ✅ **CLEARED — all five decided** |
| Step 3 implementation | ▶ **authorized, proceeding** |
| Step 3 validation | ⏳ not reached |
| Commit / push | ⏳ not reached — each requires separate explicit authorization |

**Nothing was implemented, staged, committed, tagged or pushed before this record was written.**

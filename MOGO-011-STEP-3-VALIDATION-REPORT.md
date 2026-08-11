# MOGO-011 STEP 3 — VALIDATION REPORT

**Milestone:** MOGO-011 Step 3 — the Policy Gate
**Baseline:** `7b2c0aa940d185995305e45a209edf063050e10b` (`origin/mogo-main`) — **unchanged**
**Status:** **all gates pass — nothing staged, committed, tagged or pushed**
**Date:** 2026-08-08 · Python 3.14.6 · SQLite 3.53.3

---

## 1. Verdict

| | |
|---|---|
| Platform suite | **17 suites · 740 tests · 740 passed · 0 failures · 0 errors · 0 skipped** |
| Canonical repository gate | **17 suites · 947 fixtures · 947 passed · 0 failed · 0 execution errors** |
| Campaign C1 | **33 verified · 0 missing · 0 mismatched · 0 unlisted** |
| Protected-function drift | **63 functions · 4 constants · drift 0** |
| Mutation protocol | **21 applied · 21 detected · 0 survivors** (after closing two genuine gaps) |
| Third-party dependencies | **0** |
| Protected paths modified | **0** |
| `HEAD` | `7b2c0aa940d185995305e45a209edf063050e10b` — unchanged |

---

## 2. Validation sequence

| # | Check | Result |
|---|---|---|
| 1 | Purge all bytecode | done before every run below |
| 2 | `python3 -m compileall -q platform tests/platform` | **OK** |
| 3 | Import all 26 modules under `-W error` | **26 modules · 40 event names · schema version 3** |
| 4 | `bash tests/run_platform_tests.sh` | **17 suites, 740 tests, 740 passed, 0/0/0** |
| 5 | `demo --scenario all` | **exit 0** — denial, disposition, release and execution all visible |
| 6 | `reset --rebuild-index` then `verify` | **REBUILT 55 events, 38 transitions** · **INTEGRITY OK** |
| 7 | `policy` operator view | decisions, authorizations, blocked tasks, gates |
| 8 | `bash tests/run_all.sh` | **17 suites, 947 fixtures, 947 passed, 0 failed** |
| 9 | `python3 regression-baseline-tools.py` | **No drift: 63 functions, 4 constants** |
| 10 | Campaign C1 manifest verification | **33/33 by SHA-256; 0 missing, 0 mismatched, 0 unlisted** |
| 11 | AST no-network / no-subprocess / no-random / no-clock | **0 / 0 / 0 / clock.py only** |
| 12 | `sys.stdlib_module_names` dependency classification | **third-party: 0** |
| 13 | **Genuine v2 → v3 upgrade** against the committed build | report refused (rc 6), `init` migrated, `verify` **INTEGRITY OK**, rebuild clean |
| 14 | Mutation run: 21 mutations, bytecode purged between each | **21/21 detected** |
| 15 | **Crash boundaries 23–26**, real `os._exit(70)` in child processes | **all pass** |
| 16 | Protected paths | **0 modified** |
| 17 | Runtime state git-ignored | database and log both ignored |

**Item 13 was rehearsed for real**, as in Step 2: a v2 state root was built with the *committed*
build via `git archive HEAD`, then opened under Step 3. The report command correctly refused the
un-migrated schema, `init` migrated it, and the pre-existing task survived intact.

---

## 3. Test inventory

**622 → 740 tests. 14 → 17 suites.**

| Suite | Tests | Δ |
|---|---:|---:|
| `test_platform_identifiers` | 96 | — |
| `test_platform_envelopes` | 71 | — |
| `test_platform_task_states` | 66 | — |
| `test_platform_boundaries` | 47 | — |
| `test_runtime_store_schema` | 31 | — |
| `test_runtime_event_log` | 27 | — |
| `test_runtime_projection` | 22 | — |
| `test_runtime_orchestrator` | 25 | — |
| `test_runtime_capability` | 52 | — |
| `test_runtime_retry` | 55 | — |
| `test_runtime_lease` | 33 | — |
| `test_runtime_dead_letter` | 22 | — |
| **`test_runtime_policy_gate`** | **53** | **new** |
| **`test_runtime_authorization`** | **29** | **new** |
| **`test_runtime_review_disposition`** | **22** | **new** |
| `test_runtime_recovery` | **46** | **+14** |
| `test_runtime_end_to_end` | 40 | — |
| **Total** | **740** | **+118** |

### The tests that carry the most weight

- `test_a_denied_task_emits_no_claim_and_no_start` — the F-1 regression. The log must not say a task
  was claimed and started when it never ran.
- `test_unknown_is_refused_even_if_the_table_says_it_permits` — monkeypatches the committed table to
  claim `UNKNOWN` permits acquisition, and asserts the decision still refuses.
- `test_as_recorded_is_not_an_allowance` — the trap that would have made the two most nuanced
  statuses the most permissive.
- `test_discover_is_governed_exactly_as_metadata` — closes the drip-feed reading of Architecture
  §20.2, across all twelve statuses.
- `test_dispatch_refuses_an_acquisition_task_without_a_recorded_permit` — corrupts the index and
  proves execution is still refused.
- `test_rebuild_does_not_call_the_gate` — replay re-applies; it never re-decides.
- `test_editing_an_authorization_cannot_rewrite_a_past_decision` — Constitution §5.7, mechanical.
- `test_approval_is_refused_while_the_gate_still_denies` — a human may un-block a task; only the gate
  may authorize the acquisition.
- `test_every_status_and_operation_pair_is_decided` — 48 combinations, none undecided, none raising.

---

## 4. Mutation protocol

**Protocol as Steps 1 and 2:** apply to committed source → purge all bytecode → run the full suite →
revert → re-verify the file's SHA-256, bounded at 420 s per run.

**Result: 21 applied, 21 detected, 0 survivors** — after two genuine gaps were found and closed, and
three further mutations were added to guard the defects the crash-boundary tests uncovered.

| # | Mutation | Outcome |
|---:|---|---|
| 1 | make `UNKNOWN` acquirable | DETECTED |
| 2 | permit when no authorization record exists | DETECTED |
| 3 | ignore authorization expiry | DETECTED |
| 4 | ignore supersession | DETECTED |
| 5 | treat `AS_RECORDED` as permission | DETECTED |
| 6 | permit an operation the record does not list | DETECTED |
| 7 | default an indeterminate operation class to permit | DETECTED |
| 8 | treat a denied status as permitted | DETECTED |
| 9 | map a policy denial to `queued` instead of `blocked` | DETECTED (33 failures) |
| 10 | map an unreadable policy decision to `queued` | **survived → gap closed → DETECTED** |
| 11 | map an unreadable review decision to `queued` | DETECTED |
| 12 | remove the dispatch permit guard | DETECTED |
| 13 | let an approval skip re-evaluation of the gate | DETECTED |
| 14 | accept a bare approval with no reason | **survived → gap closed → DETECTED** |
| 15 | let a worker authorize an acquisition | DETECTED (7 errors) |
| 16 | accept a changed authorization record in place | DETECTED |
| 17 | resolve an ambiguous authorization by picking one | DETECTED |
| 18 | govern `discover` by a laxer column than `metadata` | DETECTED |
| 19 | **strand a task in `blocked`** (revert the G-5 fix) | DETECTED |
| 20 | **drop the `blocked → awaiting_review` recovery path** | DETECTED (**non-termination**) |
| 21 | **let `verify` miss a terminal state with no event** (revert the G-6 fix) | DETECTED |

### 4.1 The two survivors were real gaps, and one of them was instructive

Unlike Step 2's survivors — which were mis-specified mutations that removed only one of two
redundant guards — **both of these were genuine holes in the tests**, and are reported as such.

- **M10.** `_policy_target` resolves an unreadable decision to `blocked`, and nothing tested it. The
  review-side equivalent *was* tested; the policy-side one had simply been missed. A test now asserts
  the mapping across six unreadable values.

- **M14 is the one worth reading.** `test_a_bare_approval_is_refused` existed and passed — but it
  passed **for the wrong reason**. With the reason check removed, the approval was still refused,
  because the gate re-evaluation refused it first. The test named one guard and was actually
  exercising another.

  Closed by testing a bare **rejection**, which does not re-evaluate the gate and where the reason
  requirement is therefore the only thing that can refuse; and by testing bare approval *with* an
  authorization already recorded, then proving the same call succeeds once a reason is supplied.

  **A test that passes because a different guard fired is not evidence of the guard it names.** The
  mutation protocol is what surfaced that, and it is the third time across this milestone that it has
  found something review would not have.

---

## 5. Fail-closed matrix, as verified

| Situation | Outcome | Verified by |
|---|---|---|
| No authorization record | DENY | `test_no_authorization_record_denies` |
| `UNKNOWN` | DENY — identical to `PROHIBITED` | two independent guards |
| `PROHIBITED` / `RESTRICTED` / `AUTHENTICATION_REQUIRED` | DENY | `test_the_decision_ladder` |
| `HUMAN_REVIEW_REQUIRED` | DENY — no new acquisition | `test_human_review_required_permits_no_new_acquisition` |
| Expired | DENY | boundary tested at ±1 ms |
| Superseded | DENY | derived by query, never stamped |
| Operation outside `permittedOperations` | DENY | |
| Operation `DENIED` by the status | DENY even if granted | narrower of list and column governs |
| `AS_RECORDED` without a referenced licence | DENY | |
| `LOCATOR_ONLY` / `ALREADY_GATHERED_ONLY` | DENY for every operation | |
| Operation class absent, empty, misspelled | DENY — treated as acquisition-class | |
| No subject source | DENY | |
| Two live records for one source | DENY — ambiguous | a machine must not pick one |
| Malformed record | refused at registration | never silently ignored |
| Authority names automation | refused | Constitution §14, Catalog §N |
| Unreadable policy decision on replay | `blocked` | never `queued` |
| Unreadable review decision on replay | `suppressed` | never `queued` |

---

## 5a. Crash boundaries 23–26 — proven, and what they found

The previous version of this report listed these as **not covered**, carried on the argument that
every gate transition is a single event under the unchanged write protocol. **The argument was wrong
in one place.** Writing the tests found two real defects.

| # | Boundary | Kind | Verified outcome |
|---:|---|---|---|
| 23 | after the policy decision is appended | append | replay converges — `awaiting_review` on a denial, `succeeded` on a permit; exactly one decision, never re-decided |
| 24 | between the denial and the review request | between events | completes `blocked → awaiting_review`; **regression for defect G-5** |
| 25 | after the review request is appended | append | replay converges to `awaiting_review`; exactly one request |
| 26 | after the review decision is appended | append | replay converges to `suppressed` or `succeeded`, carrying the gate's permit through the crash |

**Asserted at every boundary**, from the durable log and the rebuilt index:

- **no fabricated authorization** — `acquisition_authorizations` stays empty
- **no fabricated claim or execution** — none of `TaskClaimed`, `TaskStarted`, `TaskSucceeded`,
  `TaskFailed`, `AcquisitionAuthorized`; `attempt` stays 0; no `task_attempts` row
- **the gate is never bypassed** — the recorded decision remains a denial, and the task remains in
  `blocked` or `awaiting_review`
- **no invalid state transition** — every recorded edge is checked against `is_legal_transition`
- **the append-only history is never contradicted** — no FATAL, and the index never claims history
  the log does not have
- **no unauthorized work executes** — re-asserted after running twice more
- **recovery is deterministic and auditable** — rebuild from the log alone, then `verify` clean

Plus `test_repeated_restart_across_the_gate_converges` (five sequential kills reach the same answer
as an uninterrupted run) and two cross-boundary properties asserted in a single test each.

**A distinction the tests make rather than smooth over.** An *append* boundary fires inside `_emit`,
between the fsync and the commit, so the index is legitimately **behind** — and `verify` must **say
so**, naming the `log_sequence` and prescribing `recover`. A *between-events* boundary leaves the
index consistent. Neither is a contradiction; a FATAL finding or an index claiming absent history
would be, and both are asserted absent.

---

## 6. What is honestly not covered

- **`acquisition_authorizations` is not replayable.** It holds governance input, not platform
  history. Named in the schema; the *decision* is replayable and carries the record's content hash.
- **Policy re-evaluation on version change is deferred** (C-5), with its trigger recorded: the first
  acquisition that produces a retained artifact.
- **One pre-existing `ResourceWarning`** in a Step 1 recovery test, unchanged and unrelated.
- **`fsync` remains structurally asserted only**, an inherent limit of in-process testing.

---

## 7. Risk position after validation

**A-5 unchanged, severity High.** Step 3 registers no effectful capability and opens none of the
gate's four preconditions; the A-5 gate test still asserts all four are `False`.

**Connector gates:** `policy_gate` is now **MET**. Three remain unmet — `a5_result_store`,
`first_connector_authorization`, `acquisition_authorization_record` — and the test asserts them by
name, so no future step can quietly mark another one met.

**All Step 1 and Step 2 carried items remain**, unchanged.

---

## 8. State at the end of validation

Nothing staged. Nothing committed. Nothing tagged. Nothing pushed.
`HEAD` = `7b2c0aa940d185995305e45a209edf063050e10b`.
21 files changed (6 created, 15 modified), 0 protected paths touched.

**Next gate: human approval of the implementation before any commit.**

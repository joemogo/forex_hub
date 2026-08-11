# MOGO-011 STEP 1 — IMPLEMENTATION REPORT

**Milestone:** MOGO-011 Step 1 — Runtime Kernel and First Executable Automation
**Baseline:** `766ee5c5374581adcce2afb3f6684a03ec3cb424` (`origin/mogo-main`)
**Status:** implemented and validated · **nothing staged, committed, tagged or pushed**
**Companion:** `MOGO-011-STEP-1-VALIDATION-REPORT.md` (exact results, mutation detail)

---

## 1. Executive Result

The runtime kernel is built and demonstrably works. **One command produces a durable task, drives it through six approved states, executes a registered capability, records nine operational events, reaches a terminal state, refuses to duplicate itself, survives a kill at any boundary, and can be audited afterwards.**

| | |
|---|---|
| Files created | **23** (16 runtime, 7 test suites) |
| Files modified | **5** (all planned) |
| Lines of runtime source | 2,646 |
| Lines of test source | 2,198 |
| Platform tests | **450 passed, 0 failures, 0 errors, 0 skipped** (was 268) |
| Canonical gate | 17 suites, **947/947 fixtures**, 0 failed |
| Protected-function drift | **0** (63 functions, 4 constants) |
| Campaign C1 | **33/33 verified** |
| Mutations detected | **16/16**, all reverted |
| New dependencies | **0** |

**Three approved decisions were implemented exactly as approved:** F-1 (JSONL authoritative, SQLite derived), F-2 (five additive event names), F-3 (boundary tests narrowed to the contracts layer, runtime gains a confinement rule).

**Four defects were found by the tests during implementation and fixed at the source** — none by weakening a test. Two more were found by the mutation run. All six are recorded in §11.

**One deviation from the plan's file list is disclosed:** a 23rd file, `runtime/errors.py`. The plan put `RuntimeBusyError` in `store.py`; implementation showed the runtime needs a *taxonomy*, and scattering nine exception types across the modules that happen to raise them would have been exactly the architectural debt this authorization forbids.

## 2. Approved Corrections Implemented

| Decision | Implementation | Evidence |
|---|---|---|
| **F-1** JSONL authoritative, SQLite derived | `event_log.py` is the only source of truth; `projection.py` derives everything; `reset --rebuild-index` reconstructs the database from the log alone | `test_rebuild_from_log_reproduces_the_database`, `test_an_index_deleted_entirely_is_rebuilt_from_the_log` |
| **F-2** Five additive event names | `EVENT_TYPES` 34 → 39: `CommandAccepted`, `CommandRejected`, `TaskRequested`, `TaskPolicyCheckRequested`, `TaskStarted`. Additive only — nothing renamed, removed or repurposed | `test_event_types_exactly` (independently transcribed), `test_nine_events_in_the_approved_order` |
| **F-3** Boundary narrowing | Absolute no-I/O scoped to `contracts/**`; new write-confinement rule for `runtime/**`; §7 and network/subprocess rules stay global | `test_contracts_layer_has_no_open_call_at_all`, `test_every_runtime_write_site_is_guarded_by_runtime_paths`, mutation 16 |

## 3. Architecture as Built

```
operator ─▶ platform/mogo_runtime.py         (exclusive flock held for the whole run)
              └▶ orchestrator                 the ONLY writer of task state
                   ├─ P1 append + fsync ─▶ operational-events.jsonl   AUTHORITATIVE
                   ├─ P2 BEGIN IMMEDIATE ─▶ runtime.sqlite3           DERIVED
                   ├─ P3 projection      ─▶ tasks/<state>/<id>.json   cosmetic
                   └─ dispatch (registered + enabled + compatible only)
                        └▶ worker ─▶ research.runtime.echo.v1   pure, deterministic
```

**The write order is the property that makes recovery possible.** The event is durable *before* it is a state (Architecture §18.1). A crash between P1 and P2 leaves the index behind the log and replay converges; the reverse order could commit a state change with no event, which is unrecoverable and violates Constitution §6.6.

**Exactly-once without bookkeeping.** Every transition is a guarded `UPDATE … WHERE task_id=? AND state=? AND last_log_sequence < ?`. `rowcount==1` means applied; `rowcount==0` is disambiguated by re-reading the row into *already applied* (a replay, not an error) or *illegal/late* (nothing mutated, anomaly recorded). Replay-safety is a property of the statement, not of a caller remembering to check.

**No lease, deliberately.** A lease rescues a claim held by a *concurrent* process that died. Step 1 has one process by construction — `fcntl.flock` held for the whole run, second runner exits 5 `BUSY`. With no concurrent claimer there is nothing to expire, and a crashed claimer is handled deterministically by recovery. A lease becomes necessary the moment a daemon or a second worker exists; that is a Step 2 gate.

## 4. Files Created — 23

**Runtime (16, 2,646 lines):**

| File | Lines | Role |
|---|---:|---|
| `platform/mogo_runtime.py` | 32 | Operator launcher; the `sys.path` bridge and nothing else |
| `platform/runtime/.gitignore` | 13 | Self-ignoring state root (ADR-012 D-06) |
| `runtime/__init__.py` | 4 | Package marker, docstring only |
| `runtime/paths.py` | 159 | State locations **and the write-confinement guard** |
| `runtime/errors.py` | 115 | Runtime error taxonomy (deviation, §11) |
| `runtime/store.py` | 154 | SQLite pragmas, `BEGIN IMMEDIATE`, `ProcessLock` |
| `runtime/schema.py` | 250 | 9 tables, 6 indexes, append-only triggers, migrations |
| `runtime/event_log.py` | 336 | **The authoritative log**: append+fsync, scan, torn-tail, quarantine |
| `runtime/projection.py` | 325 | log → index, idempotent; guarded transitions; rebuild |
| `runtime/registry.py` | 178 | Capability registration and the five §O dispatch conditions |
| `runtime/worker.py` | 66 | Execution; reports, never transitions |
| `runtime/orchestrator.py` | 622 | Receipt, transitions, dispatch, recovery |
| `runtime/audit.py` | 292 | Operator reports and integrity verification |
| `runtime/cli.py` | 315 | Eight argparse subcommands |
| `runtime/capabilities/__init__.py` | 4 | Package marker, docstring only |
| `runtime/capabilities/echo.py` | 95 | `research.runtime.echo.v1` — pure |

**Tests (7, 2,198 lines):** `test_runtime_store_schema` (282) · `test_runtime_event_log` (355) · `test_runtime_projection` (323) · `test_runtime_orchestrator` (278) · `test_runtime_capability` (284) · `test_runtime_recovery` (338) · `test_runtime_end_to_end` (338).

## 5. Files Modified — 5

```
platform/README.md                                  78 +++---
platform/src/mogo_platform/contracts/vocabulary.py  20 +-
tests/platform/test_platform_boundaries.py         211 +++++++--
tests/platform/test_platform_envelopes.py           11 +-
tests/run_platform_tests.sh                          7 +
5 files changed, 285 insertions(+), 42 deletions(-)
```

| File | Change |
|---|---|
| `contracts/vocabulary.py` | F-2: five event names added, with a comment recording the authorization and the reason |
| `test_platform_envelopes.py` | Independently transcribed expectation updated 34 → 39 |
| `test_platform_boundaries.py` | F-3 narrowing plus new runtime-confinement, escape-hatch and package-marker tests (34 → 52) |
| `tests/run_platform_tests.sh` | 4 → 11 suites |
| `platform/README.md` | Runtime layer, the two-layer rule table, the authority model, the CLI |

**Not modified:** `tests/run_all.sh` (D-12 gate) · `docs/TESTING.md` · `docs/KNOWN_ISSUES.md` · `regression-baseline*` · `index.html` · `evidence/**` · `docs/campaigns/**` · governance documents · root `.gitignore`.

## 6. Persistence Design

**Nine tables** — `schema_meta`, `event_index`, `commands`, `command_submissions`, `tasks`, `capabilities`, `log_cursor`, `transition_anomalies`, `recovery_actions` — with `UNIQUE(commands.idempotency_key)`, `UNIQUE(tasks.idempotency_key)`, `UNIQUE(event_index.event_id)` and `UNIQUE(event_index.workflow_id, sequence)`.

**Append-only is enforced by the database, not by convention.** `event_index`, `command_submissions` and `transition_anomalies` each carry `BEFORE UPDATE` and `BEFORE DELETE` triggers raising `ABORT`. A rule enforced only by careful code is the rule most likely to break under pressure (Constitution §16), so it is enforced one layer below the code that would break it.

**Pragmas:** `journal_mode=WAL`, `synchronous=FULL`, `foreign_keys=ON`, `busy_timeout=5000`. `FULL` is chosen over speed because a fast store that loses its last commit on power loss would make the index disagree with the log in exactly the situation recovery exists for.

**Global ordering without a contract change.** Events carry a per-workflow `sequence` (Catalog §B) but no global ordinal. Rather than add a field to a committed MOGO-010 envelope, the global order is the line's 1-based position in the log — a property of the log, not of the event.

**One notable implementation constraint:** `sqlite3.executescript()` issues an implicit `COMMIT`, which silently ended the `BEGIN IMMEDIATE` that `initialize()` opens. The DDL is therefore a tuple of explicit statements, executed one by one, so schema creation stays inside one transaction. Recorded because it is non-obvious and would recur.

## 7. Command Receipt and Idempotency

Validation is the unchanged MOGO-010 contract — `validate_command(envelope, payload=payload)` — fail-closed on unsupported major, malformed identifier, bad timestamp, non-JSON-shaped payload, non-finite float, non-string key, prohibited scientific reference and payload-hash mismatch.

The idempotency key uses the approved Catalog §I `transformation` composition, derived from the payload alone: no timestamp, no attempt number. A re-submission produces the same key by construction, and the constraint is enforced twice — application lookup and database `UNIQUE`.

**A duplicate appends no event and creates no task.** The fact is carried by the append-only `command_submissions` table, because no approved event names a suppressed duplicate and none was invented.

**Rejections are split deliberately: the class goes to the log, the detail goes to the table.** A validation message names the value that failed — and that value may be exactly what the boundary forbids. A command whose `inputRefs` point at a protected scientific path produces a message *containing that path*; copying it into an event payload would make the envelope validator (correctly) refuse to record the rejection, and a refused command would vanish silently, which Constitution §6.6 forbids. Keeping the classification in the log and the detail in the derived table satisfies both rules and loses no information. **This was found by a test, not by inspection.**

## 8. Capability Registry and the Demonstration Capability

Manifests are declared in code with a `manifest_hash` over their canonical form. Re-registering an identical manifest is a no-op; **a changed manifest under the same `capabilityId` is refused** — a changed capability is a new version and needs a new identity, or the audit trail would describe work performed by different code.

The five §O dispatch conditions are each enforced and each independently tested: registered · enabled · lifecycle ∈ {approved, production} · command type accepted · command version compatible. Every failure is fail-closed with a message naming the condition, and produces `TaskFailed(errorClass="validation")` rather than an execution.

`research.runtime.echo.v1` is a **pure function**: no file, socket, process, clock or randomness. Asserted behaviourally (100 runs over *distinct but structurally equal* objects) and structurally (AST: no I/O call, no absolute import). It declares no connectors and no secrets (ADR-012 D-09).

## 9. Recovery

Five ordered phases: acquire lock → torn-tail scan → replay past the cursor → reclaim tasks stranded in `claimed`/`running` → resume command lifecycles interrupted before task creation.

**Torn-tail handling is the one place the log is shortened, and it shortens no event.** An event is committed only when its complete newline-terminated line is durable, so a fragment failing that test never became history. The fragment is copied to `quarantine/` and fsynced *before* the truncation, matching Architecture §24's "quarantined, not deleted, and reported". **A hash mismatch anywhere other than the tail is corruption of committed history: the runtime halts and does not repair.**

All eleven crash-matrix boundaries are tested with **real process kills** (`os._exit(70)`, no unwinding). Results in the validation report §5.

## 10. Operator Surface

`init · submit · run · status · audit · verify · reset · demo`, argparse, non-zero exit on every refusal.

`audit` prints the event table, the state timeline with per-transition authority, **every submission attempt including suppressed duplicates and rejections**, transition anomalies, recovery actions, and an integrity verdict. Architecture §23: an operator must be able to answer "what failed, when, and why" without reading code.

`reset --rebuild-index` is the executable proof of ADR-012 D-05 — throw the index away, reconstruct it from the log, verify.

## 11. Defects Found and Fixed — all at the source

| # | Defect | Found by | Fix |
|---|---|---|---|
| 1 | `executescript()` implicitly committed, breaking the schema transaction | first smoke test | DDL as explicit statements |
| 2 | A faulty DDL extractor silently dropped six `CREATE TABLE` statements whose buffer began with a comment | schema introspection | rewrote the DDL block by hand rather than patch the extractor |
| 3 | `_open()` returned an already-opened runtime, so `with` took the process lock twice | demo run | `open()` made idempotent; `_open()` returns unopened |
| 4 | `TaskRequested` reported `APPLIED` on replay when its `INSERT OR IGNORE` did nothing, tripping the divergence guard | `test_apply_is_idempotent_under_replay` | outcome now reflects whether the row was new — **the guard was right; the outcome was wrong** |
| 5 | A rejection reason echoing a prohibited reference made `CommandRejected` unrecordable | `test_prohibited_scientific_reference_is_rejected` | class in the log, detail in the table (§7) |
| 6 | `verify` **crashed** on a corrupt log instead of reporting it — the one command meant to diagnose corruption died of it | `test_replay_halts_on_a_mid_file_hash_mismatch` | `verify_integrity` and `audit_report` now report and degrade gracefully |

**Three prohibited-literal violations in my own code** (`evidence/` and `scripts/trader_intelligence` in docstrings, a banned `__import__` in `cli.py`) were caught by the boundary tests and fixed in the source, never by relaxing a rule.

**Three genuine test gaps** were found by the mutation run and closed: the `commands` UNIQUE constraint was untested; the determinism test reused one object and so was blind to `id()`-derived nondeterminism; the terminal guard is unreachable through ordinary traffic and needed a direct test. Detail in the validation report §6.1.

**A near-miss worth naming:** two new structural tests initially *errored* (`inspect.getsource` on a method returns indented source), which the mutation harness read as "detected". That would have been a false positive. It was caught, fixed with `textwrap.dedent`, and mutation 5 re-verified in isolation.

## 12. Deviations from the Plan

| Deviation | Reason |
|---|---|
| **23 files created, not 22** — `runtime/errors.py` added | The plan put `RuntimeBusyError` in `store.py`. Nine distinct failure modes need a taxonomy; scattering them would be the architectural debt this authorization forbids. Every class descends from `contracts.errors.PlatformError`, so the two hierarchies are one tree |
| Commit boundary 27 → **28 files** | Consequence of the above |
| Mutation 4 replaced | "Reverse the write order" cannot be expressed as a single-anchor edit; the invariant's *detector* is mutated instead, backed by a new direct test |
| Mutation 5 asserted structurally | `fsync` is undetectable by in-process testing (validation report §6.2). Stated as a limit, not covered up |

**No higher-authority document required amendment.** The only deviation from an authoritative document is from Inventory §10's "*Recommended* platform location" sketch, which the approved plan already analysed: ADR-012 approval #2 names the top-level `platform/` bounded context, which is preserved exactly.

## 13. Deferred, and Not Simulated

Retry · backoff · dead-letter execution · leases · review workflow · second capability · **policy gate** (Architecture §32 item 5, required before any connector) · connectors of every kind · acquisition · transcripts · evidence candidates · hypothesis promotion · scientific writes · replay · paper/live trading · strategy optimization · model calls · multi-agent · distributed workers · package manifest (D-01) · canonical runner integration (D-12).

An **acquisition-class** operation is refused rather than guessed: `classify_policy_check` returns `requires_policy_gate` and the orchestrator declines to dispatch. Fail-closed by construction, not by omission.

## 14. Standing Risks

| # | Risk | Severity | Note |
|---|---|---|---|
| **A-5** | **Crash boundary 8 is safe only because the capability is pure** | **High for Step 2** | Re-execution after an interrupted run is safe *because* it is indistinguishable. An effectful capability needs output verification and an idempotency-keyed result store **before** registration |
| A-3 | Torn-tail truncation is the one place the log shortens | Medium | Quarantine-first, tail-only, never on a mid-file mismatch |
| A-4 | No approved event names a quarantined torn append | Low | Recorded in the recovery report and audit rather than misusing or inventing a name |
| A-6 | `fcntl` is POSIX-only | Low | Documented; `msvcrt` branch recorded, not built |
| A-7 | `targetCapability` canonical form still ambiguous | Low | Both attested forms accepted and mapped to one id; carried from MOGO-010 |
| A-8 | First database in the repository | Medium | Versioned from row one; no downgrade; ordered migrations |
| — | `fsync` asserted structurally only | Medium | Inherent limit of in-process testing; stated plainly in the test docstring |

## 15. Proposed Commit Boundary — 28 files

23 created + 5 modified. Runtime state is git-ignored; only `platform/runtime/.gitignore` is committed.

**Excluded:** all MOGO report documents (11 untracked) · the four legacy 2026-08-04 documents · `tests/run_all.sh` · `docs/TESTING.md` · `docs/KNOWN_ISSUES.md` · `regression-baseline*` · `index.html` · `evidence/**` · `docs/campaigns/**` · governance documents · any manifest or lock file.

**Unchanged prerequisite before any push:** `git push` still fails under `push.default=simple` because local `main` tracks `origin/mogo-main` (different names). `git push origin HEAD:mogo-main` works. A repository-policy decision remains open.

## 16. Pre-Commit Boundary Verification

Verified programmatically against the approved list immediately before staging:

```
APPROVED created  : 23   present as untracked: 23
APPROVED modified :  5   present as modified :  5
created missing   : none      created UNAPPROVED  : none
modified missing  : none      modified UNAPPROVED : none
boundary == approved 28 : True
```

**Exactly the approved 28 files. No additional file entered the commit.** The 11 MOGO report documents and the four legacy 2026-08-04 documents remain untracked and outside the boundary.

`runtime/errors.py` was checked for constitutional and architectural conflict as the authorization directs, and none was found (validation report §11.2). **Retained.**

## 17. Risk A-5 — Preserved Verbatim, By Instruction

> **Crash boundary 8 — interrupted between execution and recording success — is safe ONLY because the capability is pure.**
>
> Re-execution after an interrupted run produces a byte-identical result, so it is indistinguishable from never having been interrupted. That is a property of *this capability*, not of the kernel.
>
> **The moment a capability performs an external effect, this argument fails.** An effectful capability requires output verification and an idempotency-keyed result store **before** it may be registered. This is a hard gate on Step 2, on the first connector, and on any future autonomous agent that acquires, writes, or calls out.

This warning is not to be weakened or removed. It is expected to inform connector and autonomous-agent design.

## 18. Verdict

Implementation is complete. All validations pass. No known Step 1 defect remains within scope. The six pre-existing Python failures are unchanged and unrepaired, per instruction.

**Awaiting commit authorization.**

# MOGO-011 STEP 1 — RUNTIME KERNEL VERTICAL-SLICE PLAN

**Milestone:** MOGO-011 — Runtime Kernel and First Executable Automation · **Step:** 1
**Status:** plan only — no code written, nothing staged, committed, tagged or pushed
**Baseline:** `766ee5c5374581adcce2afb3f6684a03ec3cb424` (`origin/mogo-main`, synchronized)
**Governing document:** `AUTOMATION_PLATFORM_CONSTITUTION.md` v1.0 — senior to this plan

---

## 1. Executive Finding

The repository is at the approved baseline, clean, synchronized, and safe to plan against. A working runtime kernel is achievable in one bounded step. **Three findings must be resolved before implementation, and two of them change the preferred design.**

### F-1 — The preferred slice contradicts the approved storage architecture (BLOCKING, resolved here)

The tasking's preferred Step 1 begins *"SQLite-backed operational event log."* The approved architecture says the opposite:

| Source | Approved decision |
|---|---|
| ADR-012 approval **#6** | "**Append-only JSONL event log with derived SQLite index** as the initial durable model" |
| ADR-012 **D-04** | "(b) append-only JSONL in a distinct operational namespace, **with a derived SQLite index for queries**" |
| ADR-012 **D-07** | "**JSON records as the source of truth, SQLite as a derived index**" |
| ADR-012 approval **#7** / D-05 | "Event log authoritative; task state derived" |
| ADR-012 approval **#8** / D-03 | "SQLite + filesystem projection **for initial task delivery**" |

SQLite is approved for **task state, claims and query indexing** — never as the event store. Making SQLite the event log would invert D-04/D-07 and make the *derived* store authoritative, which D-05 forbids.

**Corrected slice: append-only JSONL is the authoritative event log; SQLite is a derived index plus the task/command read model.** Everything else in the preferred slice survives unchanged. This is the smallest equivalent executable slice and is what §5 specifies.

### F-2 — The approved event vocabulary cannot express the approved task lifecycle (REQUIRES OPERATOR APPROVAL)

Constitution §6.6 — *"No silent failures. A path that can end without an event is a defect."*
Architecture §18.1 — *"Every transition is persisted as an event before the state is considered changed."*
ADR-012 D-05 — the event log is authoritative; task state is **derived** from it.

Together these mean **every** task transition must have an event, or the state cannot be reconstructed. Catalog §J's 34 approved event names do not cover four required transitions and two command-lifecycle facts:

| Needed | Approved event exists? |
|---|---|
| command accepted (idempotency key claimed) | ❌ none |
| command rejected | ❌ none |
| task created → `requested` | ❌ none (`TaskRequested` appears in Architecture §9's diagram but is **absent from Catalog §J**) |
| `requested` → `policy_check` | ❌ none |
| `policy_check` → `queued` | ✅ `PolicyEvaluated` (authority: policy gate, per §L) |
| `queued` → `claimed` | ✅ `TaskClaimed` |
| `claimed` → `running` | ❌ none |
| `running` → `succeeded` / `failed` | ✅ `TaskSucceeded` / `TaskFailed` |
| reclaim after crash | ✅ `TaskReclaimed` |

Catalog §J itself states: *"Not finalized. Names and payloads are Step 3 work."* MOGO-011 **is** that step. Architecture §11 permits growth: *"additive-only within a major version… a breaking change is a **new event type**, not a new version."*

**Proposed additive extension — five names, no renames, no removals:**

| New event | Transition or fact | Authority (§L) |
|---|---|---|
| `CommandAccepted` | command validated, idempotency key claimed | orchestrator |
| `CommandRejected` | command failed validation | orchestrator |
| `TaskRequested` | task created in `requested` | orchestrator |
| `TaskPolicyCheckRequested` | `requested` → `policy_check` | orchestrator |
| `TaskStarted` | `claimed` → `running` | worker runtime |

**This requires explicit operator approval and is the single decision gating implementation.** The alternative — omitting events for un-named transitions — would make task state underivable from the log and violate D-05. It is not viable and is not offered.

### F-3 — The committed MOGO-010 boundary tests forbid all writes anywhere under `platform/**` (REQUIRES A NARROWING)

`tests/platform/test_platform_boundaries.py` currently asserts:

- `test_no_open_call_at_all_in_step_1` — **zero** `open()` calls anywhere under `platform/`
- `test_no_write_capable_open_call` — zero write-mode opens
- `test_no_filesystem_mutation_call` — zero `os.remove`/`rename`/`replace`/`mkdir`/…

Those were correct for a contracts-only step and are **deliberately stricter than the architecture**. Architecture §7 prohibits writes to **six named targets**, not writes in general. A runtime kernel must write.

**Required narrowing, and a strictly stronger replacement rule:**

| Rule | Scope after MOGO-011 Step 1 |
|---|---|
| No `open()` of any kind, no mutation calls | `platform/src/mogo_platform/contracts/**` — **unchanged, still absolute** |
| No write path to the six §7 targets | **all** of `platform/**` — unchanged |
| **NEW:** every write must resolve inside the runtime state root | `platform/src/mogo_platform/runtime/**` |
| No network / subprocess / dynamic-exec imports | **all** of `platform/**` — unchanged |

Net effect: the contracts layer keeps its absolute prohibition, and the runtime layer gains a *confinement* rule that did not exist before. Coverage increases.

### Verdict

The plan below is complete and implementable. **One decision (F-2) must be approved before code is written.** F-1 is resolved by adopting the architecture's storage model. F-3 is a planned, disclosed test modification.

---

## 2. Baseline and Repository Verification

| # | Check | Result |
|---|---|---|
| 1 | Repository path | `/Users/joemogollon/Desktop/Forex Hub` |
| 2 | Branch | `main` |
| 3 | HEAD | `766ee5c5374581adcce2afb3f6684a03ec3cb424` |
| 4 | HEAD == approved baseline | ✅ exact match |
| 5 | Upstream | `origin/mogo-main` |
| 6 | Local/remote synchronized | ✅ ahead 0, behind 0 |
| 7 | Tracked modifications | **0** |
| 8 | Staged files | **0** |
| 9 | Untracked files | 11 (7 MOGO reports + 4 legacy documents) |
| 10 | Protected-path status | **clean** — `git status` on 11 protected paths returned empty |
| 11 | Runtime/package structure | `mogo_platform` package at `platform/src/`; contracts only; no runtime layer |
| 12 | Python | **3.14.6** |
| 13 | Existing SQLite usage | **none anywhere in the repository** — this is the first |
| 14 | CLI conventions | `argparse` + `if __name__ == "__main__":`, flags such as `--apply`, `--dry-run`, `--status` (`scripts/trader_intelligence/ingest.py`) |
| 15 | Persistence conventions | JSON files; `pretty_json` for committed artifacts; canonical JSON for hashing |
| 16 | Transaction / recovery utilities | `graph_common.atomic_write_text()` — write-temp → `flush` → `fsync` → `os.replace`. **No transaction or recovery utility exists** |
| 17 | Canonical test runner | `tests/run_all.sh` globs `tests/run_*_tests.js` only, then the drift gate last and decisively. **Not modified by this step** (ADR-012 D-12 gate) |
| 18 | Prior process running | **none** (the `ps` matches were a stale Chrome test profile from 2026-08-04) |
| 19 | Safe to plan against | ✅ **yes** |

Runtime prerequisites confirmed: **SQLite 3.53.3**, `threadsafety=3`, `PRAGMA foreign_keys` supported, `fcntl.flock` available.

---

## 3. Authoritative Document Review

All twelve sources read. Governing extracts that shaped this plan:

| Source | Extract that constrains the design |
|---|---|
| Constitution §4.4/§4.5 | workers never call workers; coordination only through governed commands, workflows, events |
| Constitution §6.1–§6.8 | events immutable, append-only, correlation+causation, schema version, payload hash, **no silent failures**, separate namespace |
| Constitution §7 | *"A worker reports state; it does not transition state. Only the orchestrator writes task state."* |
| Constitution §11 | idempotency keys deterministic from semantic inputs; crash recovery resumes from the last **verified** checkpoint |
| Constitution §16 | a violation is a blocking defect; enforce mechanically |
| Architecture §7 | six prohibited write targets |
| Architecture §11 | additive-only evolution; a breaking change is a new event type |
| Architecture §18.1 | orchestrator alone writes task state; **every transition is an event before it is a state** |
| Architecture §24 | temp+fsync+rename; unrenamed temp = detected partial write; partial artifacts **quarantined, not deleted** |
| Architecture §25 | protected-boundary static test over `platform/**` |
| Catalog §A/§B | command and event envelope contracts (implemented in MOGO-010) |
| Catalog §L | 13 states, 25 transitions, per-edge authority — **authoritative over the §18.1 diagram** |
| Catalog §O | capability record fields; dispatch requires registered + enabled + compatible |
| ADR-012 D-03/04/05/06/07 | SQLite for tasks/claims; JSONL authoritative for events; state derived; git-ignored storage with committed manifests; JSON source of truth |
| ADR-012 D-09 | **no secrets in v1** — the first capability needs none |
| ADR-012 D-13 | subprocess isolation *"only if evidence later demands"*; no ambient network in tests |
| `platform/README.md` | narrow root-collision rule; `platform/src` is the one `sys.path` entry |

**Legacy untracked architecture documents were not consulted as authority.** `MOGO_AGENTIC_SYSTEM_BLUEPRINT.md` in particular contradicts Constitution §4.4/§4.5 and Catalog §H and is excluded by standing instruction.

---

## 4. Existing Runtime and Persistence Findings

| Finding | Consequence for Step 1 |
|---|---|
| No SQLite anywhere in the repository | Step 1 introduces the first database. Schema, migration and transaction discipline are set here and become precedent |
| No transaction or recovery utility exists | Both must be built; `atomic_write_text` is the only durability precedent and applies to whole-file writes, not to an append-only log |
| `atomic_write_text` = temp → flush → fsync → `os.replace` | Reused verbatim in spirit for the **task filesystem projection**; **not applicable to the append-only log**, which needs append+fsync semantics instead |
| MOGO-010 contracts are pure and side-effect free | The runtime layer sits **beside** contracts, never inside it; contracts keep their absolute no-I/O rule |
| `mogo_platform` package importable via one `sys.path` entry | The runtime reuses it; no new import convention |
| `tests/run_all.sh` excludes Python suites (D-12 gap) | Platform suites continue through `tests/run_platform_tests.sh`; runner integration remains ungoverned and out of scope |
| `evidence/.gitignore` self-ignoring pattern | Reused exactly for `platform/runtime/.gitignore` (D-06) |
| `sqlite3.version` removed in Python 3.14 | Use `sqlite3.sqlite_version` only; noted so no code depends on the removed attribute |

---

## 5. Proposed Executable Vertical Slice

**One process. One shot. One capability. Two stores, one authority.**

```
                 ┌──────────────────────────────────────────┐
  operator ─────▶│ platform/mogo_runtime.py  (CLI)          │
                 └──────────────┬───────────────────────────┘
                                │  holds exclusive flock for the whole run
                 ┌──────────────▼───────────────────────────┐
                 │ orchestrator  — the ONLY writer of state  │
                 └───┬───────────────────────────┬──────────┘
      append+fsync   │                           │ dispatch (registered+enabled only)
                     ▼                           ▼
   ┌─────────────────────────────┐   ┌──────────────────────────┐
   │ operational-events.jsonl    │   │ worker → capability      │
   │ APPEND-ONLY · AUTHORITATIVE │   │ research.runtime.echo.v1 │
   └──────────────┬──────────────┘   │ pure, deterministic      │
                  │ replay (idempotent)└──────────────────────────┘
                  ▼
   ┌─────────────────────────────┐
   │ runtime.sqlite3  — DERIVED  │  event_index · tasks · commands ·
   │ index + read model + claims │  capabilities · cursor · anomalies
   └─────────────────────────────┘
```

**Authority rule, stated once:** the JSONL log is the only source of truth. SQLite holds nothing that cannot be rebuilt by replaying the log. `reset --rebuild-index` deletes the database and reconstructs it from the log alone; a test asserts the rebuilt database is byte-equivalent.

### In scope

operational event persistence (JSONL) · derived SQLite index · durable task read model · command receipt with idempotency enforcement · legal transition application · capability registry with one capability · one-process orchestration · local worker execution · single-writer exclusion (no time-based lease) · crash-safe restart · deterministic recovery · append-only audit history · `research.runtime.echo.v1` · operator CLI · health and audit reports.

### Explicitly out of scope

external connectors · YouTube/web/GitHub acquisition · browser automation · artifact downloading · transcript processing · evidence-candidate creation · hypothesis promotion · scientific registry writes · replay · paper/live trading · strategy optimization · model calls · multi-agent · distributed workers · external engines/brokers · cloud · **time-based leases** (§12) · retry/backoff execution · dead-letter processing · review workflow · policy evaluation for acquisition-class operations.

---

## 6. End-to-End Demonstration

`python3 platform/mogo_runtime.py demo` runs the milestone's twelve required outcomes in order and prints a machine-checkable transcript.

| # | Milestone requirement | Demo action | Expected output |
|---|---|---|---|
| 1 | valid command submitted | `submit --demo` | `ACCEPTED command=<uuid> workflow=<uuid> idempotencyKey=<sha256>` |
| 2 | validated via MOGO-010 contracts | `contracts.command.validate_command` | `VALIDATED commandVersion=1 schema=mogo.platform.operational.command.v1` |
| 3 | durable task created | `TaskRequested` appended + applied | `TASK CREATED task=<uuid> state=requested` |
| 4 | policy applied only as authorized | `classify_policy_check("non_acquisition")` | `POLICY not_applicable -> queued` |
| 5 | approved task states traversed | transitions applied | `requested → policy_check → queued → claimed → running → succeeded` |
| 6 | registered capability claims it | registry lookup + `TaskClaimed` | `CLAIMED by CAP\|research\|runtime-echo (enabled, production)` |
| 7 | harmless deterministic operation | echo capability | `RESULT contentHash=<sha256>` |
| 8 | events recorded durably | JSONL + fsync | `EVENTS 9 appended, log bytes=<n>, fsync=9` |
| 9 | terminal state reached | `TaskSucceeded` | `TASK task=<uuid> state=succeeded terminal=yes` |
| 10 | re-run does not duplicate | `submit --demo` again | `DUPLICATE SUPPRESSED existing task=<same uuid>; tasks created=0; events appended=0` |
| 11 | restart after interruption resumes | `--simulate-crash-at <boundary>` then `run` | `RECOVERED: reclaimed 1 task; resumed; no duplicate result` |
| 12 | inspectable audit | `audit --workflow <id>` | full ordered event table + state timeline + integrity verdict |

**Determinism guarantee:** given the same command payload, `contentHash` is identical across runs, machines and restarts. The demo asserts this by comparing the hash from the first run against the hash after crash-recovery.

---

## 7. Runtime Authority Model

| Concern | Authority | Rebuildable? |
|---|---|---|
| **Operational events** | `operational-events.jsonl` — append-only | **No — this is the truth** |
| Event index | `event_index` table | Yes, by replay |
| Task state | `tasks` table | Yes, by replay |
| Command records | `commands` table | Yes, by replay |
| Submission attempts | `command_submissions` table | **No — local audit of attempts, append-only** |
| Capability registry | `capabilities` table | Yes, from the code-declared manifest |
| Replay position | `log_cursor` table | Yes, recomputed from the log |
| Task filesystem projection | `platform/runtime/tasks/<state>/<taskId>.json` | Yes — cosmetic, never read for correctness |

**Only the orchestrator writes task state** (Constitution §7). The worker returns a result; it never transitions a task and never appends an event under its own identity — the orchestrator appends `TaskSucceeded`/`TaskFailed` with `producer = "worker:WRK|research.runtime.echo.v1"` recorded in the payload as the *reporting* worker.

**Operational/scientific separation** is inherited unchanged from MOGO-010: distinct namespace `mogo.platform.operational`, distinct identifier space, envelope-level rejection of every §7 prohibited reference.

---

## 8. SQLite and Transaction Design

### 8.1 Connection settings (every connection, every time)

```
PRAGMA journal_mode = WAL;      -- crash-safe, survives process kill
PRAGMA synchronous = FULL;      -- durability over speed; this is an audit store
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;
```
Transactions use **`BEGIN IMMEDIATE`** — the write lock is taken at statement one, so a would-be second writer fails immediately rather than mid-transaction.

### 8.2 Exact schema — version 1

```sql
CREATE TABLE schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);   -- schema_version='1', created_at_utc, contract_namespace

CREATE TABLE event_index (               -- DERIVED. Rebuildable from the log.
    log_sequence   INTEGER PRIMARY KEY,  -- global monotonic, assigned by the log
    event_id       TEXT    NOT NULL UNIQUE,
    event_type     TEXT    NOT NULL,
    event_version  INTEGER NOT NULL,
    workflow_id    TEXT    NOT NULL,
    task_id        TEXT,
    correlation_id TEXT    NOT NULL,
    causation_id   TEXT    NOT NULL,
    producer       TEXT    NOT NULL,
    occurred_at    TEXT    NOT NULL,
    recorded_at    TEXT    NOT NULL,
    sequence       INTEGER NOT NULL,     -- per-workflow, monotonic
    payload_hash   TEXT    NOT NULL,
    byte_offset    INTEGER NOT NULL,
    byte_length    INTEGER NOT NULL,
    UNIQUE (workflow_id, sequence)
);
CREATE INDEX idx_event_workflow ON event_index (workflow_id, sequence);
CREATE INDEX idx_event_task     ON event_index (task_id, log_sequence);
CREATE INDEX idx_event_type     ON event_index (event_type, log_sequence);

CREATE TABLE commands (
    command_id            TEXT PRIMARY KEY,
    command_type          TEXT    NOT NULL,
    command_version       INTEGER NOT NULL,
    workflow_id           TEXT    NOT NULL,
    correlation_id        TEXT    NOT NULL,
    idempotency_key       TEXT    NOT NULL UNIQUE,   -- the duplicate gate
    target_capability     TEXT    NOT NULL,
    issued_at             TEXT    NOT NULL,
    issued_by             TEXT    NOT NULL,
    payload_hash          TEXT    NOT NULL,
    accepted_log_sequence INTEGER NOT NULL,
    task_id               TEXT
);

CREATE TABLE command_submissions (       -- APPEND-ONLY. Every attempt, forever.
    submission_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    submitted_at    TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    command_id      TEXT,
    outcome         TEXT NOT NULL CHECK (outcome IN
                      ('accepted','duplicate_suppressed','rejected')),
    reason          TEXT
);
CREATE INDEX idx_submissions_idem ON command_submissions (idempotency_key, submission_id);

CREATE TABLE tasks (                     -- DERIVED read model.
    task_id              TEXT PRIMARY KEY,
    workflow_id          TEXT    NOT NULL,
    correlation_id       TEXT    NOT NULL,
    command_id           TEXT    NOT NULL REFERENCES commands(command_id),
    capability_id        TEXT    NOT NULL,
    idempotency_key      TEXT    NOT NULL UNIQUE,
    state                TEXT    NOT NULL,
    attempt              INTEGER NOT NULL DEFAULT 0,
    created_log_sequence INTEGER NOT NULL,
    last_log_sequence    INTEGER NOT NULL,   -- exactly-once replay guard
    terminal             INTEGER NOT NULL DEFAULT 0,
    result_hash          TEXT,
    error_class          TEXT
);
CREATE INDEX idx_tasks_state ON tasks (state, task_id);

CREATE TABLE capabilities (              -- Catalog §O subset needed for dispatch
    capability_id     TEXT PRIMARY KEY,
    name              TEXT NOT NULL,
    version           TEXT NOT NULL,
    owner             TEXT NOT NULL,
    accepted_commands TEXT NOT NULL,     -- canonical JSON array
    emitted_events    TEXT NOT NULL,     -- canonical JSON array
    lifecycle_status  TEXT NOT NULL,
    enabled_state     INTEGER NOT NULL,
    compatibility     TEXT NOT NULL,     -- canonical JSON {commandType: [versions]}
    manifest_hash     TEXT NOT NULL,
    registered_at     TEXT NOT NULL
);

CREATE TABLE log_cursor (
    id                INTEGER PRIMARY KEY CHECK (id = 1),
    last_log_sequence INTEGER NOT NULL,
    last_byte_offset  INTEGER NOT NULL,
    last_event_id     TEXT
);

CREATE TABLE transition_anomalies (      -- APPEND-ONLY. Late transitions.
    anomaly_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    detected_at  TEXT NOT NULL,
    log_sequence INTEGER NOT NULL,
    task_id      TEXT NOT NULL,
    from_state   TEXT NOT NULL,
    to_state     TEXT NOT NULL,
    reason       TEXT NOT NULL
);
```

**Append-only enforced at the storage layer, not by convention:**

```sql
CREATE TRIGGER event_index_no_update BEFORE UPDATE ON event_index
  BEGIN SELECT RAISE(ABORT, 'event_index is append-only'); END;
CREATE TRIGGER event_index_no_delete BEFORE DELETE ON event_index
  BEGIN SELECT RAISE(ABORT, 'event_index is append-only'); END;
-- identical pairs on command_submissions and transition_anomalies
```

### 8.3 The write protocol — exact, and the reason for its order

**Every state change follows the same three phases, in this order, holding the process lock:**

```
P1  append the complete event line to the JSONL log, then os.fsync(fd)
P2  BEGIN IMMEDIATE
      INSERT INTO event_index (...)                       -- fails if replayed twice
      apply the transition (guarded UPDATE, see below)
      UPDATE log_cursor SET last_log_sequence=?, last_byte_offset=?
    COMMIT
P3  refresh the human-readable task projection (best-effort, never load-bearing)
```

**Why the log is written first.** Architecture §18.1: *"Every transition is persisted as an event before the state is considered changed."* If the process dies between P1 and P2, the event is durable and SQLite is merely behind — recovery replays and converges. If the order were reversed, a committed state change could exist with no event, which is unrecoverable and violates §6.6.

**The guarded update — the exactly-once primitive:**

```sql
UPDATE tasks
   SET state = :to_state,
       terminal = :terminal,
       last_log_sequence = :log_sequence
 WHERE task_id = :task_id
   AND state = :from_state
   AND last_log_sequence < :log_sequence;
```

`rowcount == 1` → applied. `rowcount == 0` → one of two cases, distinguished by re-reading the row:
- `last_log_sequence >= :log_sequence` → **already applied**; a replay; no-op, not an error.
- otherwise → **illegal or late transition**; nothing mutated; recorded in `transition_anomalies`.

This makes replay idempotent without any "have I seen this?" bookkeeping outside the row itself.

### 8.4 One event per transaction — no batching

Two events are never appended together. Batching would make a torn tail able to split a logically atomic pair, and detecting that would require adding batch fields to the MOGO-010 event envelope. Instead, **every multi-event sequence is made resumable** (§13), so no batch atomicity is needed. This is why the crash matrix in §13 has an entry for every intermediate point.

### 8.5 Schema migration

`schema_meta.schema_version` is written at creation. `MIGRATIONS = ((1, _create_v1),)` — an ordered tuple. Startup: read version; apply every migration with a higher number inside one `BEGIN IMMEDIATE`; refuse to run if the stored version is **higher** than this build supports (fail closed, no downgrade). `init` is idempotent: running it on an initialized database applies nothing and reports the current version.

---

## 9. Command and Idempotency Design

### 9.1 Receipt sequence

1. Load the command JSON. Reject a non-mapping.
2. **`contracts.command.validate_command(envelope, payload=payload)`** — the MOGO-010 contract, unchanged. Fail-closed on: unsupported major (distinct error), missing/typed field, malformed identifier, non-JSON-shaped value, non-string key, non-finite float, prohibited scientific reference, payload-hash mismatch.
3. On rejection: append `CommandRejected`, insert `command_submissions(outcome='rejected', reason=…)`, exit non-zero. **No task is created.**
4. On acceptance: look up `commands` by `idempotency_key`.
   - **found** → insert `command_submissions(outcome='duplicate_suppressed', command_id=<existing>)`; print the existing `task_id`; exit 0. **No event is appended and no task is created.**
   - **not found** → append `CommandAccepted`; apply (insert `commands`, insert `command_submissions(outcome='accepted')`).
5. Append `TaskRequested`; apply (insert `tasks` in `requested`, set `commands.task_id`).

### 9.2 Idempotency key

Computed by **`contracts.ids.idempotency_key()`**, unchanged from MOGO-010. Step 1 uses the approved `transformation` composition — `(inputHash, transformationId, transformationVersion)` — where `inputHash = content_hash_of(payload)`, `transformationId = "XF|runtime-echo"`, `transformationVersion = "1.0.0"`. No timestamp, no attempt number; a re-submission of the same payload produces the same key by construction.

The key is enforced twice: `UNIQUE(commands.idempotency_key)` and `UNIQUE(tasks.idempotency_key)`. Even a logic error cannot create a second task for one key — the database refuses.

### 9.3 Duplicate visibility

Constitution §4.18 — *"Failures, retries, rejections, suppressions and duplicates remain visible. Silence is a defect."* Every submission attempt writes a `command_submissions` row, including suppressed duplicates and rejections; the table is append-only by trigger, and `audit` prints all attempts. **No event is appended for a duplicate**, because no approved event names that fact and none is being proposed for it — the append-only submissions table carries it instead.

---

## 10. Task and Transition Design

Transitions are validated by **`contracts.task_states`**, unchanged: `assert_legal_transition(from, to)` raises `IllegalTaskTransitionError` and mutates nothing; `classify_late_transition` returns a `LateTransitionAnomaly` for a terminal source.

**Happy path — 9 events, 6 transitions:**

| # | Event | Transition | §L authority |
|---|---|---|---|
| 1 | `WorkflowStarted` | — | orchestrator |
| 2 | `CommandAccepted` *(new)* | — | orchestrator |
| 3 | `TaskRequested` *(new)* | → `requested` | orchestrator |
| 4 | `TaskPolicyCheckRequested` *(new)* | `requested` → `policy_check` | orchestrator |
| 5 | `PolicyEvaluated` | `policy_check` → `queued` | policy gate |
| 6 | `TaskClaimed` | `queued` → `claimed` | worker runtime |
| 7 | `TaskStarted` *(new)* | `claimed` → `running` | worker runtime |
| 8 | `TaskSucceeded` | `running` → `succeeded` | orchestrator |
| 9 | `WorkflowCompleted` | — | orchestrator |

Failure path replaces 8 with `TaskFailed` (`running` → `failed`) carrying an approved §K `errorClass`. **Retry and dead-letter are out of scope**: a failed task stops at `failed` and is reported; no `TaskRetryScheduled` is emitted.

**Policy is applied only to the extent authorized.** `classify_policy_check("non_acquisition")` returns `("queued","not_applicable")`. The echo capability declares `operationClass = "non_acquisition"` in its manifest. An `acquisition`-class operation returns `(None,"requires_policy_gate")` and the orchestrator **refuses to dispatch**, because no policy gate exists — fail closed. An unrecognised class returns `("blocked","operation_class_indeterminate")`.

---

## 11. Capability Registry Design

**Registration.** Each capability declares a manifest in code (Catalog §O fields). `init` inserts it into `capabilities` with `manifest_hash = content_hash_of(manifest)`. Re-running `init` with an unchanged manifest is a no-op; a changed manifest is a **new version** requiring a new `capability_id` — the registry never silently mutates a registered record.

**The one Step 1 capability:**

```
capabilityId     CAP|research|runtime-echo
name             research.runtime.echo.v1
version          1.0.0
owner            operator:mogo
acceptedCommands ["NormalizeArtifact"]          -- approved Catalog §J name
emittedEvents    ["TaskSucceeded","TaskFailed"]
lifecycleStatus  production
enabledState     true
compatibility    {"NormalizeArtifact": [1]}
operationClass   non_acquisition
resourceLimits   {wallClockMs: 5000, maxPayloadBytes: 65536}
requiredSecretReferences  []                     -- ADR-012 D-09: none in v1
requiredConnectors        []
```

**Eligibility check before dispatch** (Catalog §O dispatch rule) — all five must hold, else fail closed with no execution and a `TaskFailed(errorClass="validation")`:

1. `capability_id` is registered
2. `enabled_state = 1`
3. `lifecycle_status ∈ {approved, production}`
4. `command.commandType ∈ accepted_commands`
5. `command.commandVersion ∈ compatibility[commandType]`

`targetCapability` resolution accepts the two forms MOGO-010 admits (`CAP|…` composite and dotted name) and maps both to one `capability_id`. **The canonical-form ambiguity is carried, not resolved** (§25).

---

## 12. Worker and Execution Design

**No time-based lease in Step 1, and here is why.** A lease exists so that a *second* live process can take over from a claimer that died holding the claim. Step 1 has exactly one process by construction — enforced by an exclusive `fcntl.flock` on `platform/runtime/runtime.lock` held for the whole run. A second `run` fails immediately with `RuntimeBusyError`. With no concurrent claimer there is nothing to expire; a crashed claimer is handled deterministically by recovery (§13), which is strictly simpler and has no clock dependency. **A lease becomes necessary the moment a daemon or a second worker exists — that is a Step 2 concern and is recorded as such.**

Claiming is therefore a compare-and-set inside `BEGIN IMMEDIATE`, not a lease: `UPDATE tasks SET state='claimed' WHERE task_id=? AND state='queued'`.

**The capability contract** — `execute(payload) -> result`, a pure function:

```python
def execute(payload):
    """Deterministic, side-effect free. No I/O, no clock, no randomness."""
    normalized = ids.as_plain(payload)
    return {
        "normalizedPayload": normalized,
        "contentHash": ids.content_hash_of(normalized),
        "byteLength": len(ids.canonical_json_bytes(normalized)),
        "capabilityId": "CAP|research|runtime-echo",
        "capabilityVersion": "1.0.0",
    }
```

It reads no file, opens no socket, spawns no process, calls no clock and uses no randomness. A test asserts byte-identical output across 100 invocations and across a process restart. `resourceLimits.maxPayloadBytes` is enforced before execution; an oversized payload fails closed with `errorClass="validation"`.

The worker **reports**; the orchestrator **transitions** (Constitution §7).

---

## 13. Crash-Recovery Design

### 13.1 Startup recovery — five ordered phases

| Phase | Action | Failure behaviour |
|---|---|---|
| **R1** | Acquire the exclusive process lock | another runner holds it → exit non-zero, touch nothing |
| **R2** | **Torn-tail scan** of the JSONL log | see §13.2 |
| **R3** | **Replay** every line with `log_sequence > log_cursor.last_log_sequence` into SQLite, idempotently | payload-hash mismatch → **halt**, exit non-zero, mutate nothing |
| **R4** | **Reclaim** tasks stranded in `claimed` or `running` | append `TaskReclaimed`, apply → `queued` |
| **R5** | **Resume** incomplete command lifecycles | see §13.3 |

### 13.2 Torn-tail handling — the one place the log is truncated, and its justification

A crash mid-`write()` can leave a partial final line. Detection, in order: the file does not end with `\n`; **or** the final line fails JSON parse; **or** its `payloadHash` does not match `content_hash_of(payload)`.

**A torn fragment is not an event.** An event is committed only when its complete newline-terminated line is durable. Recovery therefore:

1. copies the fragment to `platform/runtime/quarantine/torn-<log_sequence>-<utc>.fragment`
2. truncates the log to the end of the last **valid** line
3. records the action in the recovery report and in `audit`

This truncates **no event** — only an uncommitted byte fragment — and destroys nothing, matching Architecture §24's *"partial artifacts are quarantined, not deleted, and reported."* Truncation happens **only** at the tail and **only** when the fragment fails validation; a hash mismatch anywhere earlier in the file is corruption and halts the runtime instead.

> **Ambiguity carried to governance:** no approved Catalog §J event names "a torn log append was quarantined". `PartialArtifactQuarantined` concerns artifacts, not the log. Rather than misuse an approved name or invent an unapproved one, Step 1 records this in the recovery report and audit output only. Flagged in §24.

### 13.3 The crash matrix — every boundary, precisely

| # | Crash point | Durable state after crash | Recovery action | Duplicate work? |
|---|---|---|---|---|
| 1 | before `CommandAccepted` is appended | nothing | none; re-submit is a fresh command | no |
| 2 | after `CommandAccepted` fsync, before SQLite apply | event durable, SQLite behind | R3 replays → `commands` row exists | no |
| 3 | **after command receipt, before task creation** | `commands` row with `task_id IS NULL` | R5 appends `TaskRequested`; a **new** `task_id` is minted — safe, because no task existed and the idempotency key is already claimed, so a re-submission still cannot create a second | no |
| 4 | after `TaskRequested` fsync, before apply | event durable | R3 replays → task appears in `requested` | no |
| 5 | task stuck in `requested` / `policy_check` / `queued` | consistent | R5 resumes forward from that state | no |
| 6 | **after claim, before execution** | task in `claimed` | R4 appends `TaskReclaimed` → `queued`; re-claimed and executed | no — the capability had not run |
| 7 | after `TaskStarted`, mid-execution | task in `running` | R4 reclaims → `queued` → re-executed | no observable duplicate: the capability is **pure**, so re-execution has no external effect and yields an identical `contentHash` |
| 8 | **after execution, before `TaskSucceeded` is appended** | task in `running`; result exists only in memory | R4 reclaims → re-executes → identical result → `TaskSucceeded` | no — determinism makes re-execution indistinguishable |
| 9 | after `TaskSucceeded` fsync, before apply | event durable | R3 replays → `succeeded` | no |
| 10 | mid-`write()` (torn tail) | partial line | §13.2 quarantine + truncate; the event is treated as never committed and is re-emitted | no |
| 11 | after `WorkflowCompleted` | terminal | nothing to do; a late event would be an anomaly (§13.4) | no |

Boundary 8 is the one that would be unsafe for an *effectful* capability. It is safe here **only because the capability is pure**, and that is precisely why the first capability is required to be pure. The moment a capability performs an external effect, Step 2 must add output verification and an idempotency-keyed result store before that capability is registered. Recorded in §24.

### 13.4 Late transitions

An event arriving for a task already `terminal = 1` is **recorded in the log** (immutable — it is a real fact) but **not applied**. `classify_late_transition` classifies it, a `transition_anomalies` row is written, and `audit` reports it. Catalog §C: *"logged as anomalies and not applied."*

### 13.5 Induced-interruption testing

`--simulate-crash-at <boundary>` raises `SimulatedCrash` at a named boundary and `os._exit(70)` without unwinding — no `finally`, no flush, no cleanup, which is what a real kill does. Boundaries: `after_command_append`, `before_task_create`, `after_claim`, `mid_execution`, `after_execution`, `before_success_append`, `after_success_append`, `mid_line_write`. The flag is refused unless `MOGO_RUNTIME_ALLOW_CRASH_SIM=1` is set, so it cannot fire in normal operation.

---

## 14. Audit and Operator Visibility

`audit [--workflow <id>] [--task <id>] [--json]` prints:

- **Event table** — `logSeq · seq · eventType · producer · occurredAt · taskId · payloadHash`
- **State timeline** — every transition with its authority and the event that caused it
- **Command history** — every submission attempt including suppressed duplicates and rejections
- **Integrity verdict** — per-workflow sequence monotonicity, global log-sequence contiguity, payload-hash verification for every event, cursor consistency, and index-vs-log agreement
- **Recovery history** — reclaims, quarantined fragments, anomalies

`status` prints task counts by state, oldest non-terminal task, event count, log size, schema version, and registry contents. `verify` runs the integrity checks alone and exits non-zero on any failure — this is the operator's "is the log trustworthy?" command.

Per Architecture §23: *"An operator must be able to answer 'what failed, when, and why' without reading code."*

---

## 15. Exact Files to Create

**Runtime package (13):**

| Path | Purpose | Public API |
|---|---|---|
| `platform/mogo_runtime.py` | Launcher; inserts `platform/src`, delegates to CLI | `main(argv=None) -> int` |
| `platform/runtime/.gitignore` | Self-ignoring state root (D-06 / `evidence/` precedent) | — |
| `platform/src/mogo_platform/runtime/__init__.py` | Package marker, docstring only | — |
| `.../runtime/paths.py` | State locations; creates the root | `RuntimePaths`, `default_paths()`, `ensure_state_root(paths)` |
| `.../runtime/store.py` | SQLite open, pragmas, transactions, process lock | `open_database(path)`, `immediate_transaction(conn)`, `ProcessLock(path)`, `RuntimeBusyError` |
| `.../runtime/schema.py` | DDL, triggers, migrations | `SCHEMA_VERSION`, `MIGRATIONS`, `initialize(conn)`, `current_version(conn)` |
| `.../runtime/event_log.py` | Append-only JSONL: append, scan, torn-tail, quarantine | `EventLog`, `.append(event) -> LogRecord`, `.scan(from_offset)`, `.verify()`, `.repair_torn_tail()` |
| `.../runtime/projection.py` | Apply events → SQLite, idempotently | `apply_event(conn, record) -> ApplyOutcome`, `rebuild(conn, log)` |
| `.../runtime/registry.py` | Capability registration and eligibility | `register(conn, manifest)`, `lookup(conn, ref)`, `assert_dispatchable(cap, command)` |
| `.../runtime/capabilities/__init__.py` | Package marker, docstring only | — |
| `.../runtime/capabilities/echo.py` | `research.runtime.echo.v1` | `MANIFEST`, `execute(payload) -> dict` |
| `.../runtime/orchestrator.py` | Command receipt, transitions, dispatch — **the only state writer** | `Orchestrator`, `.submit(envelope, payload)`, `.run_once()`, `.recover()` |
| `.../runtime/worker.py` | Claim + execute; reports, never transitions | `execute_task(capability, task, payload) -> WorkerResult` |
| `.../runtime/audit.py` | Reports and integrity verification | `status_report(conn)`, `audit_report(conn, log, workflow_id)`, `verify_integrity(conn, log)` |
| `.../runtime/cli.py` | `argparse` subcommands | `main(argv) -> int` |

**Tests (7):**

`tests/platform/test_runtime_store_schema.py` · `test_runtime_event_log.py` · `test_runtime_projection.py` · `test_runtime_orchestrator.py` · `test_runtime_capability.py` · `test_runtime_recovery.py` · `test_runtime_end_to_end.py`

**Total: 22 new files.**

---

## 16. Exact Files to Modify

| Path | Change | Why unavoidable | Gate |
|---|---|---|---|
| `platform/src/mogo_platform/contracts/vocabulary.py` | Add 5 event names to `EVENT_TYPES` (34 → 39), additive-only, alongside a comment recording the MOGO-011 authorization | F-2: the log cannot express the approved lifecycle without them | **Requires operator approval** |
| `tests/platform/test_platform_envelopes.py` | Update `EXPECTED_EVENT_TYPES` (independently transcribed) and the count assertion 34 → 39 | The test transcribes the contract; the contract changed | with F-2 |
| `tests/platform/test_platform_boundaries.py` | Narrow the absolute no-I/O rule to `contracts/**`; add runtime write-confinement; keep §7 and network/subprocess rules global | F-3: the runtime must write; §7 forbids six targets, not all writes | disclosed here |
| `tests/run_platform_tests.sh` | Add the 7 new suites | Our own runner, not D-12 gated | none |
| `platform/README.md` | Document the runtime layer, the state root, the authority model | Keeps documentation matching reality | none |

**Not modified:** `tests/run_all.sh` (D-12 gate) · `docs/TESTING.md` · `docs/KNOWN_ISSUES.md` · `regression-baseline*.{json,py}` · `index.html` · `evidence/**` · `docs/campaigns/**` · `docs/trader-intelligence/governance/**` · `docs/MOGO-003-VERIFIED-REPLAY-RECORD.md` · `hypothesis-registry.json` · root `.gitignore` (the nested `platform/runtime/.gitignore` is used instead).

---

## 17. Dependency Decision

**Zero new dependencies. Python 3.14 standard library only.**

| Need | Module | Why stdlib suffices |
|---|---|---|
| Database | `sqlite3` | 3.53.3, WAL, FULL sync, triggers — ADR-012 D-03/D-07 approved SQLite |
| Durability | `os.fsync`, `os.replace` | matches the existing `atomic_write_text` precedent |
| Single-writer | `fcntl.flock` | POSIX; documented platform constraint |
| Canonical JSON, hashing, identifiers, validation | `mogo_platform.contracts` | already committed |
| CLI | `argparse` | repository convention |
| Tests | `unittest`, `tempfile` | repository convention |

**No manifest is created.** ADR-012 D-01's manifest remains deferred: still no third-party dependency and still no installable surface. The `sys.path` bridge documented in `platform/README.md` is unchanged. Revisit when a real dependency appears.

**Platform constraint disclosed:** `fcntl` is POSIX-only. The repository is macOS/Linux (`darwin`, bash, `osascript`). If Windows support is ever required, the lock needs an `msvcrt` branch — recorded, not built.

---

## 18. Test Plan

Every item in the tasking's testing standard maps to a named test.

**`test_runtime_store_schema.py`** — `test_database_creation_is_deterministic` · `test_schema_version_is_recorded` · `test_initialize_is_idempotent` · `test_wal_and_full_synchronous_are_set` · `test_foreign_keys_enforced` · `test_event_index_rejects_update` · `test_event_index_rejects_delete` · `test_command_submissions_rejects_update_and_delete` · `test_transition_anomalies_rejects_update_and_delete` · `test_migration_refuses_newer_schema_version` · `test_second_process_cannot_acquire_the_lock`

**`test_runtime_event_log.py`** — `test_append_returns_monotonic_log_sequence` · `test_append_fsyncs_before_returning` · `test_event_identifiers_are_valid_uuid4` · `test_sequence_is_monotonic_within_a_workflow` · `test_payload_hash_verifies_for_every_event` · `test_scan_from_offset_matches_full_scan` · `test_torn_tail_is_detected` · `test_torn_tail_is_quarantined_not_deleted` · `test_torn_tail_truncation_preserves_every_valid_event` · `test_mid_file_hash_mismatch_halts_and_mutates_nothing` · `test_log_is_never_rewritten_in_place`

**`test_runtime_projection.py`** — `test_apply_is_idempotent_under_replay` · `test_legal_transition_applies` · `test_illegal_transition_fails_without_mutation` · `test_terminal_task_cannot_transition` · `test_late_transition_is_recorded_as_anomaly_and_not_applied` · `test_event_and_task_write_are_atomic` · `test_rollback_leaves_no_partial_state` · `test_rebuild_from_log_reproduces_the_database`

**`test_runtime_orchestrator.py`** — `test_command_validation_uses_mogo010_contracts` · `test_invalid_command_creates_no_task` · `test_unsupported_major_version_rejected_distinctly` · `test_prohibited_scientific_reference_rejected` · `test_non_json_shaped_payload_rejected` · `test_duplicate_semantic_command_creates_no_second_task` · `test_duplicate_command_appends_no_event` · `test_duplicate_attempt_is_recorded_and_visible` · `test_full_happy_path_reaches_succeeded` · `test_nine_events_in_approved_order` · `test_only_orchestrator_writes_task_state`

**`test_runtime_capability.py`** — `test_unknown_capability_fails_closed` · `test_disabled_capability_fails_closed` · `test_non_production_lifecycle_fails_closed` · `test_unaccepted_command_type_fails_closed` · `test_incompatible_command_version_fails_closed` · `test_only_registered_demonstration_capability_executes` · `test_capability_output_is_deterministic_across_100_runs` · `test_capability_output_is_deterministic_across_restart` · `test_capability_performs_no_io` (AST) · `test_oversized_payload_fails_closed` · `test_execution_failure_records_failed_state_and_event` · `test_failure_event_carries_an_approved_error_class`

**`test_runtime_recovery.py`** — one test per crash-matrix row (11) plus `test_restart_resumes_recoverable_work` · `test_restart_does_not_repeat_completed_work` · `test_reclaim_emits_TaskReclaimed` · `test_recovery_is_deterministic_across_repeated_restarts` · `test_recovery_halts_on_payload_hash_mismatch`

**`test_runtime_end_to_end.py`** — `test_demo_sequence_completes` · `test_demo_is_reproducible` · `test_audit_report_contains_every_event` · `test_verify_integrity_passes_on_clean_state` · `test_verify_integrity_fails_on_tampered_log` · `test_reset_restores_pristine_state`

**Boundary and safety (extending `test_platform_boundaries.py`)** — `test_contracts_layer_still_has_no_io_at_all` · `test_runtime_writes_are_confined_to_the_state_root` · `test_no_scientific_path_is_read_or_written` · `test_no_network_import_anywhere_in_platform` · `test_no_subprocess_or_process_execution_anywhere` · `test_no_trading_or_replay_path_is_reachable` · `test_runtime_state_root_is_git_ignored`

**Unchanged gates re-run:** all 268 existing platform tests · `tests/run_all.sh` (947 fixtures) · protected-function drift (63 + 4, zero) · Campaign C1 manifest (33/33).

All tests are offline, deterministic, and operate on a `tempfile.TemporaryDirectory()` state root — **never** the real `platform/runtime/`.

---

## 19. Mutation-Test Plan

Sandbox outside the repository, bytecode purged between runs (the stale-`.pyc` defect found in MOGO-010 makes this non-optional).

| # | Mutation | Must be caught by |
|---|---|---|
| 1 | Drop the `UNIQUE(commands.idempotency_key)` constraint | duplicate-suppression tests |
| 2 | Remove the `AND state = :from_state` guard | illegal-transition and atomicity tests |
| 3 | Remove `AND last_log_sequence < :log_sequence` | replay-idempotency tests |
| 4 | Reverse the write order (SQLite before log append) | crash-matrix rows 2, 4, 9 |
| 5 | Remove `os.fsync` after append | durability test |
| 6 | Drop the `event_index` append-only triggers | append-only tests |
| 7 | Skip payload-hash verification on replay | corruption-halt test |
| 8 | Allow dispatch to a disabled capability | fail-closed tests |
| 9 | Allow dispatch on an incompatible command version | compatibility test |
| 10 | Make the echo capability non-deterministic (append a counter) | determinism tests |
| 11 | Delete the torn fragment instead of quarantining it | quarantine test |
| 12 | Truncate the log on a mid-file hash mismatch | mid-file corruption test |
| 13 | Apply a late transition to a terminal task | terminal-absorption test |
| 14 | Remove the process lock | second-runner exclusion test |
| 15 | Let a runtime write escape the state root | write-confinement test |
| 16 | Re-broaden the contracts no-I/O rule to include `runtime/` | must fail loudly, proving the narrowing is deliberate and not accidental drift |

---

## 20. Protected-Boundary Verification

| Guarantee | Mechanism |
|---|---|
| No write to the six §7 targets | AST + literal scan over all of `platform/**` (unchanged) |
| **Runtime writes confined to the state root** | **new** — every `open(mode=w/a/x)`, `os.replace`, `os.makedirs`, `os.remove` in `runtime/**` must take a path derived from `RuntimePaths`; asserted statically and at runtime by a path-guard assertion |
| Contracts layer remains I/O-free | unchanged absolute rule, now scoped to `contracts/**` |
| No network capability | unchanged global import ban |
| No subprocess or process execution | unchanged global ban |
| No pipeline import | unchanged (`scripts/trader_intelligence` unreachable) |
| No trading or replay path | `index.html`, replay, paper/live trading literals forbidden |
| Campaign C1 unchanged | 33/33 manifest verification each run |
| Protected functions unchanged | drift gate, 63 + 4, zero |
| Runtime state never committed | `platform/runtime/.gitignore` (`*`, `!.gitignore`) + a test asserting `git check-ignore` covers the database and log |

---

## 21. Validation Commands

```bash
# 1  compile
python3 -m compileall -q platform tests/platform

# 2  warnings-as-errors import + stdlib-platform collision guard
python3 -W error -c "
import sys, os; sys.path.insert(0, os.path.join('platform','src'))
from mogo_platform.contracts import ids, command, event, task_states
from mogo_platform.runtime import store, schema, event_log, orchestrator, cli
import platform as sp; assert sp.system()
print('IMPORT OK', sp.system())"

# 3  platform suites (existing 268 + new runtime suites)
bash tests/run_platform_tests.sh

# 4  end-to-end demonstration, from a pristine state
python3 platform/mogo_runtime.py reset --confirm
python3 platform/mogo_runtime.py init
python3 platform/mogo_runtime.py demo

# 5  duplicate suppression
python3 platform/mogo_runtime.py submit --demo      # expect: DUPLICATE SUPPRESSED

# 6  induced interruption and recovery
MOGO_RUNTIME_ALLOW_CRASH_SIM=1 python3 platform/mogo_runtime.py run --simulate-crash-at after_claim
python3 platform/mogo_runtime.py run                 # expect: RECOVERED … no duplicate
python3 platform/mogo_runtime.py verify

# 7  audit
python3 platform/mogo_runtime.py audit --workflow <id>

# 8  index rebuild proves the log is authoritative
python3 platform/mogo_runtime.py reset --rebuild-index && \
python3 platform/mogo_runtime.py verify

# 9-12  unchanged gates
bash tests/run_all.sh
python3 regression-baseline-tools.py
#       Campaign C1 manifest verification (33/33)
git status --porcelain --untracked-files=all
git status --porcelain -- evidence/ docs/campaigns/ index.html \
    docs/trader-intelligence/governance/ docs/MOGO-003-VERIFIED-REPLAY-RECORD.md \
    tests/run_all.sh regression-baseline-tools.py regression-baseline.json \
    docs/TESTING.md docs/KNOWN_ISSUES.md

# 13  runtime state is git-ignored
git check-ignore -v platform/runtime/index/runtime.sqlite3 \
                    platform/runtime/events/operational-events.jsonl
```

---

## 22. Rollback Strategy

| Layer | Mechanism |
|---|---|
| Runtime data | `python3 platform/mogo_runtime.py reset --confirm` — deletes the state root only; refuses to touch any path outside it |
| New files | `rm -rf platform/src/mogo_platform/runtime platform/mogo_runtime.py platform/runtime tests/platform/test_runtime_*.py` |
| Modified files | 5 files, all committed at `766ee5c`: `git checkout -- platform/src/mogo_platform/contracts/vocabulary.py tests/platform/test_platform_envelopes.py tests/platform/test_platform_boundaries.py tests/run_platform_tests.sh platform/README.md` |
| Whole step | `git checkout -- .` then the `rm -rf` above → tree returns to `766ee5c` exactly |
| After commit | `git revert --no-edit <commit>` |

**No migration is irreversible**: the database and log are git-ignored and disposable; deleting them loses only demonstration data, and `reset --rebuild-index` proves the database can always be reconstructed from the log.

---

## 23. Proposed Commit Boundary

**27 files: 22 created, 5 modified.** One bounded commit, subject to the Release Gate.

Excluded, as always: all MOGO report documents · the four legacy documents · `tests/run_all.sh` · `docs/TESTING.md` · `docs/KNOWN_ISSUES.md` · `regression-baseline*` · `index.html` · `evidence/**` · `docs/campaigns/**` · governance documents · any manifest or lock file · **the runtime state itself** (git-ignored by `platform/runtime/.gitignore`, of which only the `.gitignore` is committed).

---

## 24. Risks and Ambiguities

| # | Risk / ambiguity | Severity | Handling |
|---|---|---|---|
| **A-1** | **Event vocabulary extension (F-2)** — 5 additive names required | **Blocking** | **Operator approval required before implementation.** No alternative preserves D-05 |
| **A-2** | Boundary-test narrowing (F-3) | Medium | Planned, disclosed; coverage increases; mutation 16 proves the narrowing is deliberate |
| **A-3** | Torn-tail truncation is the one place the log is shortened | Medium | Justified in §13.2; quarantine-first; tail-only; never on a mid-file mismatch. **Governance may prefer an explicit event name — flagged** |
| **A-4** | No approved event names a quarantined torn append | Low | Recorded in the recovery report and audit rather than misusing an approved name or inventing an unapproved one |
| **A-5** | Crash boundary 8 is safe **only because the capability is pure** | **High for Step 2** | Documented in §13.3. An effectful capability requires output verification and an idempotency-keyed result store **before** registration |
| **A-6** | `fcntl` is POSIX-only | Low | Documented; macOS/Linux only; `msvcrt` branch recorded, not built |
| **A-7** | `targetCapability` canonical form still ambiguous | Low | Carried from MOGO-010; both attested forms accepted; governance should fix one before the Capability Registry step |
| **A-8** | SQLite is the repository's first database | Medium | Schema, migration and transaction discipline set here become precedent; deliberately minimal and versioned from row one |
| **A-9** | No lease in Step 1 | Low by design | Justified in §12; becomes necessary with a daemon or a second worker — a Step 2 gate |
| **A-10** | 27 files is large for one step | Medium | It is a kernel, not a module. Split into two commits (persistence, then orchestration) if the Release Gate prefers |

---

## 25. Carried Items — do any block Step 1?

| # | Carried item | Blocks Step 1? | Reason |
|---|---|---|---|
| 1 | Six pre-existing Python test failures | **No** | Proven pre-existing at `bd6ff7c` with no `platform/` present; outside `platform/**`; not repaired here |
| 2 | `targetCapability` canonical-form ambiguity | **No** | Both attested forms accepted and mapped to one `capability_id`; recorded as A-7 |
| 3 | Two stale local branches | **No** | Neither tracks a remote; neither is checked out in this working tree |
| 4 | Stale branch touches `tests/run_all.sh` | **No** — but **watch** | Step 1 does not modify `run_all.sh`. It **would** collide if D-12 runner integration were attempted; disposition that branch first |
| 5 | `push.default` policy | **No** | Affects the Release Gate only. `git push origin HEAD:mogo-main` works today; a policy decision is recommended, not required |
| 6 | Report and legacy documents untracked | **No** | Unchanged handling; all excluded from the commit boundary |

**No carried item blocks Step 1.** Item 4 is the only one with a future collision path, and Step 1 stays clear of it.

---

## 26. Architecture Drift Check

| Requirement | Confirmation |
|---|---|
| Modular monolith, one process | ✅ one process, one shot, no daemon, no broker, no engine |
| New top-level `platform/` bounded context | ✅ runtime sits inside the approved package |
| Operational events separate from scientific evidence | ✅ namespace, identifier space and envelope rejection unchanged from MOGO-010 |
| Workers never call workers | ✅ one worker, invoked only by the orchestrator; no worker-to-worker path exists |
| Internal minimal orchestrator | ✅ no external engine |
| **Append-only JSONL event history** | ✅ **restored by F-1 — the preferred slice would have violated it** |
| **Event log authoritative, task state derived** | ✅ enforced and proven by `reset --rebuild-index` |
| SQLite + filesystem projection for task delivery | ✅ SQLite read model + human-readable projection |
| Git-ignored storage with committed manifest | ✅ `platform/runtime/.gitignore`, `evidence/` precedent |
| Machine-readable acquisition policy | ✅ untouched; no acquisition occurs |
| `UNKNOWN` behaves as `PROHIBITED` | ✅ untouched inert table |
| No connector may bypass the policy gate | ✅ no connector exists; acquisition-class operations refuse to dispatch |
| Filesystem/operator-drop is the first connector | ✅ **not built** — Step 1 proves the kernel before any connector, exactly as Architecture §32 sequences it |
| Capability Registry required | ✅ implemented as the dispatch authority (Catalog §O) |
| No automation component writes to protected scientific records | ✅ no write path to any §7 target; write-confinement rule added |
| Sequence discipline (Architecture §32) | ✅ items 1–4 of the approved sequence: contracts (done) → event log → task state machine → worker runtime. **Item 5, the policy gate, precedes any connector and is not reached here** |

**No drift.** Step 1 implements Architecture §32 items 2–4 and stops before item 5.

---

## 27. Milestone Progress Forecast

| Step | Content | Status |
|---|---|---|
| **1** | Runtime kernel: event log, projection, tasks, registry, one capability, CLI, recovery | **this plan** |
| 2 | Retry, backoff, dead-letter, leases; second capability; failure-path depth | forecast |
| 3 | Policy gate (Architecture §32 item 5) — **required before any connector** | forecast |
| 4 | Filesystem/operator-drop connector + raw artifact registry (D-15) | forecast |
| 5 | Ingestion adapter with lineage capture; observability views | forecast |

Step 1 closes the milestone's twelve non-negotiable outcomes. Everything after it is depth, not proof.

---

## 28. Final Recommendation

Implement the corrected slice in §5 — **JSONL authoritative, SQLite derived** — which is the smallest executable vertical slice the approved architecture permits, and which differs from the tasking's preferred slice only in that one respect.

**One decision must be made before code is written: approve or reject the five additive event names (F-2, A-1).** Without them the event log cannot express the approved task lifecycle, and task state cannot be derived from it as ADR-012 D-05 requires. There is no viable alternative, which is why none is offered.

Two further items are disclosed rather than assumed: the boundary-test narrowing (F-3, A-2) and torn-tail truncation (A-3). Both increase enforcement rather than relax it, and both are mutation-tested.

Everything else is settled: zero dependencies, no manifest, no lease, one process, pure capability, crash matrix closed at all eleven boundaries, and a rebuild path that proves the log — not the database — is the truth.

**READY FOR MOGO-011 STEP 1 IMPLEMENTATION REVIEW**

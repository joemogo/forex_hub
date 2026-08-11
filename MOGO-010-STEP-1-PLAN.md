# MOGO-010 STEP 1 — SESSION VERIFICATION AND IMPLEMENTATION PLAN

---

## 1. Executive Finding

The repository is at the approved MOGO-009 commit, clean, unmodified, and safe to plan against. Campaign C1 is intact and hash-verified; the protected-function gate reports zero drift. No implementation has started and no background process is active.

Three findings shape the plan.

**First — and this is the one that would have cost real time — the approved directory name `platform/` collides with a Python standard-library module, and I verified this empirically rather than assuming it.** With an `__init__.py`, a repo-root `platform/` package *shadows and breaks* stdlib `platform` (Python 3.14 even emits a rename hint). Without one, stdlib wins and `platform.contracts` is unimportable — `'platform' is not a package`. The approved name is still correct and requires **no architecture change**: the resolution is to add no `__init__.py` and import platform modules by bare name after a `sys.path` insert, which is precisely how `scripts/trader_intelligence/` already works (`import graph_common`). This is a constraint to design around, not a blocker, but it must be decided before the first file exists, not after.

**Second, Step 1 can be delivered with zero new dependencies and zero modifications to existing tracked files.** That gives a rollback story of three `rm` commands and a git-diff that contains only new paths.

**Third, one of the four legacy untracked documents materially contradicts the approved architecture.** `MOGO_AGENTIC_SYSTEM_BLUEPRINT.md` proposes agent-to-agent messaging and reuses `mogo.evidence-canon.v1` for automation hashing — both explicitly prohibited by the Constitution and the Contract Catalog. It sits in `docs/architecture/`, beside the authoritative specification. I have not touched it; its disposition is out of scope per your instruction, but it is a live trap and §12 records why.

Two scope items in your Step 1 list need your decision before implementation, not after: the test-runner integration is **D-12-gated** (Spec §33 lists "any change to `tests/run_all.sh`" as an approval gate), and Catalog §J declares the command/event vocabulary **"Not finalized… Step 3 work."** Both are addressed in §17 with recommendations.

---

## 2. Session Verification

| # | Check | Result |
|---|---|---|
| 1 | Repository path | `/Users/joemogollon/Desktop/Forex Hub` — matches expected; `git rev-parse --show-toplevel` agrees |
| 2 | Current branch | `main` |
| 3 | Current HEAD | `bd6ff7c8ccebe31431c4d58c345894d7effdb738` |
| 4 | **Matches approved MOGO-009 commit** | ✅ **Yes — exact match.** `git log -1 --decorate` → `bd6ff7c (HEAD -> main, origin/mogo-main) MOGO-009: approve automation platform architecture` |
| 5 | Remote configuration | `origin` → `https://github.com/joemogo/forex_hub.git` (fetch and push). Live `git ls-remote`: `refs/heads/mogo-main` = `bd6ff7c…` ✅ identical to HEAD; `refs/heads/main` = `abfc763…` (unrelated web-upload history) |
| 6 | Working-tree status | Clean. 0 tracked modifications, 0 deletions, 0 renames, 0 stash entries, no merge/rebase/cherry-pick/bisect in progress |
| 7 | Staged files | **None.** `git diff --cached --name-only` empty |
| 8 | Modified tracked files | **None.** `git diff --name-only` empty |
| 9 | Untracked files | Exactly 4, confirmed with `--untracked-files=all` (see below) |
| 10 | Four legacy documents still untracked | ✅ Yes — all four `??`, unmodified, unstaged |
| 11 | Build system / runtime / tests | See below |
| 12 | Background process or prior implementation | **None.** No process matching `ingest.py`, `trader_intelligence`, `run_all`, `platform/`, or `orchestrat`. `platform/`, `tests/platform/`, `docs/platform/` **do not exist** |
| 13 | Safe to plan against without altering state | ✅ **Yes.** Every command run this session was read-only; tree is byte-identical to session start |

**Untracked files (identified, untouched):**

```
?? docs/architecture/MOGO_AGENTIC_SYSTEM_BLUEPRINT.md          44,672 B  2026-08-04 21:34
?? docs/reports/MOGO-004-STEP-1-COMPLETION-REPORT.md           21,796 B  2026-08-04 18:01
?? docs/reports/MOGO-004-STEP-1-PILOT-EXECUTION-BLOCKED.md     13,504 B  2026-08-04 18:12
?? docs/reports/MOGO-RESEARCH-ACQUISITION-ARCHITECTURE.md      48,528 B  2026-08-04 07:57
```

**Item 11 — build system, package structure, runtime versions, test commands:**

| Aspect | Observed |
|---|---|
| Build system | **None.** No `Makefile`, `Dockerfile`, `docker-compose.yml`, `.github/` |
| Package manifest | **None.** No `package.json`, `requirements.txt`, `pyproject.toml`, `setup.py`, lock file |
| Package structure | **No `__init__.py` anywhere** in `scripts/` or `tests/`. Modules import siblings by bare name (`import graph_common`) after a `sys.path.insert` |
| Runtimes | Python **3.14.6**; Node **v24.18.0** (unused by tests); JXA via `osascript` (JS suites); bash 3.2.57 |
| Third-party Python deps | **Zero.** Every import across `scripts/` resolves to stdlib or a sibling repo module |
| Formatter / linter / type checker | **None present.** No black, ruff, flake8, mypy, or config for any |
| JS test command | `bash tests/run_all.sh` — globs `tests/run_*_tests.js` only, then runs the drift gate last and decisively |
| Python test command | `python3 -m unittest tests.trader_intelligence.test_graph tests.trader_intelligence.acquisition.test_acquisition …` (documented `docs/TESTING.md:502`); **8 suites, none in the canonical gate** |
| Drift gate | `python3 regression-baseline-tools.py` → *"No drift: all 63 protected functions and 4 protected constants are byte-identical"* |

---

## 3. Authoritative Document Review

All five read in full this session, at HEAD `bd6ff7c`.

| Document | Lines | Status verified |
|---|---|---|
| `docs/governance/AUTOMATION_PLATFORM_CONSTITUTION.md` | 215 | v1.0, Approved for MOGO Phase II, effective MOGO-009. §3 authority order confirmed: senior to ADR-012 and to both architecture documents |
| `docs/architecture/MOGO-009-AUTOMATION-PLATFORM-ARCHITECTURE.md` | 783 | **APPROVED** 2026-08-07 Step 2A. §34 exit criteria all checked. Header states *"Approval covers architecture only. No implementation is authorized by this document."* |
| `docs/architecture/MOGO-009-CONTRACT-CATALOG.md` | 361 | **APPROVED**, explicitly *"a tabular catalog, not executable schema"* |
| `docs/adr/ADR-012-automation-platform-architecture.md` | 361 | **Accepted**. 18 operator approvals recorded 2026-08-07. D-16 approved. Decision-identifier reconciliation note read and applied |
| `docs/reports/MOGO-009-AUTOMATION-PLATFORM-ARCHITECTURE-INVENTORY.md` | 561 | Step 1 historical record, retained unedited. ADR-012 header confirms its D-numbering is superseded |

**Authority order applied throughout this plan:** Constitution > ADR-012 > Specification > Contract Catalog > this plan. Where the Specification §18.1 diagram and Catalog §L differ on task transitions, **Catalog §L governs** — the Specification says so itself.

No other document is treated as authoritative. In particular the four untracked documents are **not** — see §12.

---

## 4. Repository Architecture Findings

### 4.1 Language and runtime

Python 3.14.6, standard library only. Confirmed by extracting every `import`/`from` across `scripts/` and resolving each: the complete non-stdlib set is sibling repo modules (`graph_common`, `evidence_common`, `acquisition_common`, …). The browser runtime (`index.html`, 18,954 lines) is a separate, unreachable world and is reference-only for Phase II.

### 4.2 Module boundaries and package-management approach

There is **no Python package structure**. Zero `__init__.py` files repo-wide. Modules under `scripts/trader_intelligence/` import each other by bare name, and tests reach them by inserting `SCRIPTS_DIR` into `sys.path`:

```python
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts", "trader_intelligence")
```

Test *suites* are addressed as dotted paths (`tests.trader_intelligence.acquisition.test_acquisition`), which works via PEP 420 implicit namespace packages.

**This convention is what makes the approved `platform/` name viable.** Empirically verified in an isolated scratch directory:

| Configuration | `import platform` resolves to | `from platform.contracts import x` |
|---|---|---|
| `platform/__init__.py` present | **the repo directory** — `platform.system()` raises `AttributeError`, stdlib broken | works, but stdlib is broken |
| No `__init__.py` (namespace pkg) | stdlib `platform.py` ✅ intact | **fails** — `'platform' is not a package` |
| No `__init__.py` + `sys.path` insert on the leaf dir | stdlib ✅ intact | **works** via bare-name `import platform_ids` |

Only the third configuration preserves both stdlib integrity and importability, and it is exactly the existing repo convention. **The plan therefore adds no `__init__.py` under `platform/` and uses bare-name imports after a `sys.path` insert.** Approved directory name preserved; no architecture deviation.

### 4.3 Existing validation libraries

**None.** No `jsonschema`, no `pydantic`, no `attrs`, no `dataclasses` usage anywhere, no `typing` imports in any of the 36 pipeline modules. Validation is hand-written functions raising typed exceptions. The 12 JSON Schema files under `docs/trader-intelligence/schema/` are **documentation artifacts**, not runtime-enforced — nothing loads them into a validator.

Consequence for Step 1: validated runtime types must be **plain dicts plus hand-written `validate_*` functions**, matching the codebase. Introducing `pydantic` would be the project's first supply chain for a problem the repo has already solved without one.

### 4.4 Existing identifier patterns

| Pattern | Location | Form |
|---|---|---|
| Pipe-delimited composite | `evidence_common.py:220` | `"EVSRC\|%s\|%s\|%03d" % (scope, date_str, seq)` |
| Pipe-delimited composite | `evidence_common.py:430` | `"HYP\|%s\|%03d" % (date_str, seq)` |
| Truncated content hash | `evidence_common.py:253` | `sha256_hex(...)[:12]` |
| Filename from hash | `evidence_common.py:258` | `sha256_hex(linkId)[:32] + ".json"` |

Catalog §H's `SRC|`, `EDU|`, `CONN|`, `WRK|` forms are a direct continuation of this house style — the platform inherits a convention rather than inventing one.

### 4.5 Canonicalization — and why the platform must re-implement it

`scripts/trader_intelligence/graph_common.py` provides the shared primitives:

```python
def canonical_json_bytes(obj):
    """Canonical serialization used ONLY for hashing: object keys sorted
    recursively, arrays never reordered (order may carry meaning), compact
    separators, UTF-8, no NaN/Infinity."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")
```

The platform **must not import this**. Spec §6.7: *"Adapters are the only permitted path into `scripts/trader_intelligence/`"* — and adapters are sequence item 8, not Step 1. Spec §17 resolves it precisely: the SHA-256 canonicalization discipline is *"**adapted** (same algorithm, new namespace)."* Step 1 re-implements the same four-line rule inside `platform/`, and a test asserts byte-identical output for a shared fixture corpus **without importing `graph_common`** — proving equivalence while preserving the boundary.

### 4.6 Existing event or task abstractions

| Abstraction | Reality |
|---|---|
| Operational events | **None.** Inventory §2.6: `worker`, `retry`, `backoff`, `checkpoint`, `resume`, `concurren`, `correlation`, `causation` each occur in **0** files under `scripts/` |
| Decision-event bus | `index.html:11429` / `:11502` — memory-only, browser-resident, trading-scoped. **Reference only; runtime never reused** (D-04) |
| State machine precedent | `acquisition_common.py:390` — `class IllegalTransitionError(ValueError)`, with *"Raises IllegalTransitionError and mutates nothing on any"* illegal transition. **This is the exact pattern Step 1's task-state module should follow** |
| Intake state machine | `intake/{pending,processing,completed,rejected}` — 1 pending, 1 processing, 12 completed, 3 rejected, 12 manifests |

### 4.7 Existing testing framework

Stdlib `unittest`, 8 suites, all offline and deterministic. Header of `test_acquisition.py`: *"Pure stdlib (unittest). Fully offline, deterministic."*

**A proven enforcement precedent exists and should be extended rather than reinvented** (`test_acquisition.py:775`):

```python
class TestNoNetworkImports(unittest.TestCase):
    BANNED = ("urllib.request", "http.client", "requests", "socket",
              "yt_dlp", "ftplib", "smtplib")
```

plus `TestNoRuntimeCoupling` (asserts `index.html` never references acquisition) and `TestKnowledgeGraphBoundary`. These are static, dependency-free boundary tests of exactly the kind Constitution §16 demands. Step 1's protected-boundary suite copies this shape.

### 4.8 Naming and directory conventions

- Python: `snake_case` modules, `<Domain>Error` exceptions deriving from `ValueError` (recoverable/validation) or `RuntimeError` (structural).
- JSON payload fields: `camelCase` (`sourceId`, `contentHash`, `acquisitionStatus`) — matches Catalog field names exactly.
- Docs: `SCREAMING-KEBAB.md` for governance/reports; `ADR-0NN-kebab.md` for ADRs.
- Tests: `tests/<area>/test_<name>.py`; JS runners `tests/run_*_tests.js`.

### 4.9 Relevant protected areas

Frozen (Inventory §8, Spec §7): `evidence/` (33 artifacts), `docs/campaigns/C1/` (8 documents), `PREREG-001`, `PREREG-002`, `docs/MOGO-003-VERIFIED-REPLAY-RECORD.md`, tags. Protected: 63 functions + 4 constants in `index.html` under `regression-baseline-tools.py`. Governed/additive-only: the 12 existing schemas, `hypothesis-registry.json`, `STATISTICAL-GOVERNANCE.md`.

`evidence/` is git-ignored via a **self-ignoring nested `evidence/.gitignore`** (`git check-ignore` → `evidence/.gitignore:10:*`), not via root `.gitignore`. This is the precedent D-06 tells the platform to follow later; Step 1 creates no artifact store and therefore touches neither.

---

## 5. Proposed Step 1 Scope

**In scope — contracts, identifiers, and their tests. Nothing executable.**

| Element | Authoritative source |
|---|---|
| Top-level `platform/` bounded-context structure (directories + README only) | Approval #2; Spec §10; Inventory §10 |
| Deterministic identifier utilities | Spec §17; Catalog §H, §I |
| Validated runtime contract types: command envelope, event envelope | Catalog §A, §B; Spec §10, §11 |
| Platform error taxonomy | Catalog §K; Constitution §16 |
| Task-state definitions and transition legality (**contracts only**) | Catalog §L; Spec §18.1 |
| Closed vocabularies as data tables | Catalog §J, §K, §M, §O |
| Standalone platform test runner | Spec §25 (runner *integration* deferred — see §17 D-3) |
| Protected-boundary tests | Spec §25 *"static test asserting `platform/**` contains no write path"*; Constitution §16 |
| Package/runtime manifest | **Not justified in Step 1** — see §8 |

**Explicitly out of scope**, confirmed absent from every proposed file: durable event persistence · SQLite projections · task orchestration · workers · connectors · filesystem/operator-drop acquisition · GitHub acquisition · YouTube acquisition · scraping · artifact downloading · transcript processing · rule extraction · hypothesis promotion · ingestion-pipeline adaptation · replay · paper trading · live trading · strategy optimization · scientific evidence writes.

**Structural guarantee:** Step 1 produces no I/O, no network capability, and no mutable state. There is no `open(..., "w")`, no `socket`, no `urllib` anywhere in the proposed code. Nothing can acquire, dispatch, or persist, because none of those code paths will exist.

---

## 6. Exact Files to Create

Eleven files. Every one is new; none overwrites anything.

### 6.1 `platform/README.md`

| | |
|---|---|
| **Purpose** | Bounded-context map, the §7 prohibited-write list in plain sight, and the mandatory import convention (no `__init__.py`; `sys.path` insert + bare-name import; the stdlib-collision rationale) |
| **Public surface** | Documentation only |
| **Why Step 1** | The import constraint must be written where the next implementer will hit it. Also carries the testing instructions that would otherwise force an edit to `docs/TESTING.md` |
| **Implements** | Spec §10; Inventory §10; Spec §7 |

### 6.2 `platform/contracts/platform_ids.py`

| | |
|---|---|
| **Purpose** | Deterministic identifier construction, validation, and idempotency-key composition |
| **Public functions** | `canonical_json_bytes(obj)` · `sha256_hex(b)` · `content_hash_of(obj)` · `new_uuid4(rng=None)` · `is_uuid4(s)` · `assert_uuid4(s, field)` · `is_sha256_hex(s)` · `assert_sha256_hex(s, field)` · `make_source_id(platform, normalized_url)` · `make_educator_id(slug)` · `make_connector_id(source_type, name)` · `make_worker_id(capability)` · `make_transformation_id(name)` · `make_capability_id(domain, name)` · `parse_composite_id(s)` · `validate_composite_id(s, expected_prefix)` · `idempotency_key(operation, **parts)` · `is_referenced_only_id(s)` |
| **Public constants** | `COMPOSITE_PREFIXES` · `IDEMPOTENCY_KEY_COMPOSITION` (the 10 rows of Catalog §I) · `REFERENCED_ONLY_ID_PREFIXES` |
| **Why Step 1** | Every other contract references an identifier; nothing can be validated before this exists. Spec §32 item 1 |
| **Implements** | Spec §17; Catalog §H (all five identifier classes, collision handling); Catalog §I (key composition) |

> **Deliberately absent:** any function that mints `hypothesisId`, `evidencePackageId`, or `replayPackageId`. Catalog §H: *"owned by governance; the platform never mints these."* A test asserts no such function exists.

### 6.3 `platform/contracts/platform_errors.py`

| | |
|---|---|
| **Purpose** | The Step 1 error taxonomy, plus the §K error-class vocabulary as an inert data table |
| **Public types** | `PlatformError(Exception)` → `ContractValidationError(PlatformError, ValueError)` · `UnsupportedContractVersionError` · `IdentifierError` · `InvariantViolationError` · `ProtectedBoundaryViolationError` · `ConfigurationError` · `InternalPlatformError` · `LateTransitionAnomaly` · `IllegalTaskTransitionError` |
| **Public constants** | `ERROR_CLASSES` — the 12 §K classes with `retryable` / `terminal` / `routes_to_review` flags, as a read-only mapping |
| **Why Step 1** | Validation cannot report failures without a taxonomy; the boundary test needs a distinct violation type |
| **Implements** | Catalog §K; Constitution §11, §16; repo convention `acquisition_common.IllegalTransitionError` |

> **No retry logic.** `ERROR_CLASSES` is data. Nothing reads it, schedules on it, or backs off. Retry behaviour is sequence item 9.

### 6.4 `platform/contracts/platform_vocabulary.py`

| | |
|---|---|
| **Purpose** | Closed vocabularies transcribed verbatim from the approved catalog |
| **Public constants** | `COMMAND_TYPES` (17, §J) · `EVENT_TYPES` (34, §J) · `LICENSING_STATUSES` (12, §M) with `permits_metadata` / `permits_transcript` / `permits_artifact` / `permits_acquisition` flags · `CAPABILITY_LIFECYCLE_STATES` (7, §O) · `OPERATIONAL_EVENT_NAMESPACE = "mogo.platform.operational"` · `PROHIBITED_SCIENTIFIC_NAMESPACES` |
| **Why Step 1** | Envelope validation needs closed enums. Encoding `UNKNOWN` with identical flags to `PROHIBITED` as *data* makes approval #12 mechanically true from the first commit rather than a rule someone remembers |
| **Implements** | Catalog §J, §M, §O; Constitution §5.2; Approvals #11, #12 |

> **Subject to approval — see §17 D-2 and D-4.** Catalog §J states the vocabulary is *"Not finalized… Step 3 work."* Including §M's statuses is defensible but is an operator call.

### 6.5 `platform/contracts/platform_command.py`

| | |
|---|---|
| **Purpose** | Command envelope construction and validation |
| **Public functions** | `build_command(**fields)` · `validate_command(env)` · `command_payload_hash(payload)` · `assert_payload_hash_matches(env)` |
| **Public constants** | `COMMAND_SCHEMA_VERSION = "mogo.platform.command.v1"` · `COMMAND_REQUIRED_FIELDS` · `COMMAND_OPTIONAL_FIELDS` · `COMMAND_DEFAULTS` (`priority=5`, `attemptLimit=3`) |
| **Why Step 1** | Catalog §A is a first-class approved contract and the unit every later component consumes |
| **Implements** | Catalog §A (all 18 fields, lifecycle, five validation checks, hash-mismatch rejection); Spec §10 |

> `validate_command` **rejects** on payload-hash mismatch, per §A: *"A hash mismatch is a rejection, and the rejection is an event."* Step 1 raises the typed error; **emitting the rejection event is Step 2** — the docstring says so explicitly.

### 6.6 `platform/contracts/platform_event.py`

| | |
|---|---|
| **Purpose** | Operational event envelope construction and validation, in a namespace structurally separate from scientific evidence |
| **Public functions** | `build_event(**fields)` · `validate_event(env)` · `event_payload_hash(payload)` · `assert_operational_namespace(env)` · `assert_no_scientific_reference(env)` |
| **Public constants** | `EVENT_SCHEMA_VERSION = "mogo.platform.event.v1"` · `EVENT_REQUIRED_FIELDS` (15) · `EVENT_OPTIONAL_FIELDS` (5) |
| **Why Step 1** | Catalog §B is approved, and the operational/scientific separation is the charter's central risk (Inventory R-16). Encoding it in the envelope validator is the cheapest place to make it structural |
| **Implements** | Catalog §B; Spec §11 (additive-only evolution); Constitution §6 (immutability, correlation/causation, schema version, payload hash); Approval #3 |

> Events are returned as **read-only mappings**. There is no mutator, no updater, no deleter — Constitution §6.1: *"never updated, never deleted."*

### 6.7 `platform/contracts/platform_task_states.py`

| | |
|---|---|
| **Purpose** | Task states and transition legality as validated contracts |
| **Public functions** | `is_terminal(state)` · `is_legal_transition(frm, to)` · `assert_legal_transition(frm, to)` · `transition_authority(frm, to)` · `legal_successors(state)` · `classify_late_transition(frm, to)` |
| **Public constants** | `TASK_STATES` (13) · `TERMINAL_STATES` (4) · `NON_TERMINAL_STATES` (9) · `LEGAL_TRANSITIONS` (25 edges) · `TRANSITION_AUTHORITY` |
| **Why Step 1** | Pure declarative data plus predicates — no executor required. Sequence item 3 needs it and cannot be written safely without it |
| **Implements** | **Catalog §L (authoritative)**; Spec §18.1 |

> **No orchestrator, no executor, no task object.** These functions answer *"is this transition legal, and who may make it?"* They cannot perform one — nothing here holds or mutates task state.

### 6.8 `platform/contracts/platform_boundaries.py`

| | |
|---|---|
| **Purpose** | The Spec §7 prohibited-write table as machine-readable data, consumed by the boundary test |
| **Public constants** | `PROHIBITED_WRITE_PATHS` (the 6 §7 entries) · `PROHIBITED_IMPORT_PREFIXES` · `BANNED_NETWORK_IMPORTS` · `PROHIBITED_SCIENTIFIC_SYMBOLS` (`mogo.evidence-canon.v1`, `mogo.evidence-package.v1`, `alexGStableHash`, `sourceTradeId`) |
| **Why Step 1** | Constitution §16: *"A rule that is only enforced by good intentions is the rule most likely to be broken under time pressure."* Landing the boundary data before there is code to police is the only ordering in which it is a gate |
| **Implements** | Spec §7, §25; Catalog §H reuse verdict; Constitution §4.22, §16 |

### 6.9–6.12 Test files

| File | Covers | Suite classes |
|---|---|---|
| `tests/platform/test_platform_identifiers.py` | §H, §I, §17 | `TestUuidIdentifiers`, `TestContentDerivedIdentifiers`, `TestCompositeIdentifiers`, `TestIdempotencyKeys`, `TestCollisionHandling`, `TestCanonicalizationEquivalence`, `TestNoMintingOfGovernanceIdentifiers` |
| `tests/platform/test_platform_envelopes.py` | §A, §B, §11 | `TestCommandEnvelopeValidation`, `TestEventEnvelopeValidation`, `TestPayloadHashRejection`, `TestContractVersionHandling`, `TestUnknownFieldBehavior`, `TestSerializationRoundTrip`, `TestOperationalScientificSeparation` |
| `tests/platform/test_platform_task_states.py` | §L | `TestTaskStateInventory`, `TestLegalTransitions`, `TestProhibitedTransitions`, `TestTerminalStateAbsorption`, `TestTransitionAuthority`, `TestCancellationRule` |
| `tests/platform/test_platform_boundaries.py` | §7, §25, §16 | `TestNoWritePathsInPlatform`, `TestNoNetworkImportsInPlatform`, `TestNoScientificImports`, `TestNoPipelineImportsOutsideAdapters`, `TestNoInitPyUnderPlatform`, `TestStdlibPlatformNotShadowed`, `TestNoUnauthorizedScientificWrites` |

All four: stdlib `unittest`, fully offline, deterministic, no fixtures copied from the repository tree.

### 6.13 `tests/run_platform_tests.sh`

| | |
|---|---|
| **Purpose** | Standalone runner for the four platform suites, reporting its own counts |
| **Why Step 1** | Delivers your "initial test-runner integration" **without touching `tests/run_all.sh`**, which is D-12/§33-gated |
| **Safety** | Named `.sh`, so `run_all.sh`'s `tests/run_*_tests.js` glob cannot pick it up — verified against the glob at `tests/run_all.sh:45` |

---

## 7. Exact Files to Modify

**None. Zero modifications to existing tracked files.**

This is a deliberate design goal, not an accident. Each candidate was considered and rejected:

| Candidate | Why not modified |
|---|---|
| `tests/run_all.sh` | **D-12 / Spec §33 gate:** *"Runner integration \| any change to `tests/run_all.sh`."* ADR-012 D-12 is *"Recommended"*, not approved, and §25 says *"not performed in Step 2."* A standalone runner delivers the capability without consuming the gate. Constitution §3 forbids a lower-level plan overriding a higher-level control |
| `docs/TESTING.md` | Would be the natural home for the new suite, but it is a tracked modification whose only benefit is documentation. `platform/README.md` carries it until D-12 authorization lands, at which point runner + TESTING.md change together as one coherent commit |
| `.gitignore` | Step 1 creates no artifact store and no build output. D-06's git-ignored storage is sequence item 7 |
| `docs/KNOWN_ISSUES.md` | No new known issue is introduced |
| `regression-baseline-tools.py` | Inventory §4: extend `FIXTURE_COUNTS` only when Phase II adds **fixture** suites to the gate. Step 1 adds none to the gate |
| `scripts/trader_intelligence/**` | Spec §6.7 — adapters only, and adapters are sequence item 8 |
| `index.html` | Protected. Spec §7 forbids the write path entirely |

**Result: `git diff --stat` after Step 1 contains only additions of new paths.** Nothing existing is renamed, moved, or deleted.

---

## 8. Dependency Decision

**Proposed new dependencies: none. Zero.**

| Question | Answer |
|---|---|
| Exact packages | **None** |
| Version strategy | N/A — Python 3.14.6 stdlib only (`json`, `hashlib`, `uuid`, `re`, `types.MappingProxyType`, `unittest`, `os`, `sys`) |
| Why stdlib is sufficient | Every Step 1 need has a stdlib answer: canonical JSON → `json.dumps(sort_keys=True, separators=(",",":"), ensure_ascii=False, allow_nan=False)`; hashing → `hashlib.sha256`; opaque ids → `uuid.uuid4`; validation → hand-written functions, exactly as all 36 existing pipeline modules do; immutability → `MappingProxyType` + frozen tuples; tests → `unittest`, the framework all 8 existing suites use |
| Security implications | None added. The repository's zero-supply-chain property is preserved for one more step. `pydantic`/`jsonschema` would each pull transitive dependencies into a project whose `.gitignore` states it *"has no build step and no package manager"* |
| Maintenance implications | None added |
| Licensing compatibility | N/A |
| Truly required in Step 1 | **No dependency is required** |

**On the package/runtime manifest (D-01).** ADR-012 approved *"Python-first with a manifest, stdlib-biased,"* but your Step 1 scope says *"only if justified."* It is **not justified in Step 1**, for three reasons: (a) a manifest with zero dependencies declares nothing but a Python floor; (b) packaging metadata would be actively misleading, because §4.2 establishes `platform/` **cannot be a Python package** — a `pyproject.toml` naming it would describe something that cannot exist; (c) deferring keeps the project's first supply chain unopened until a real dependency demands it. The Python floor is instead asserted **executably** by a test (`TestPythonVersionFloor`), which is stronger than a declaration nothing enforces.

**Recommendation: no manifest in Step 1.** This is a deviation from D-01's *timing*, not its substance, and it needs your confirmation — §17 D-1.

---

## 9. Contract and Identifier Design

### 9.1 Identifier categories (Catalog §H)

| Class | Identifiers | Form | Deterministic |
|---|---|---|---|
| Opaque random | `commandId`, `eventId`, `taskId`, `workflowId`, `correlationId`, `reviewId` | UUIDv4, lowercase, hyphenated | **No — by design.** §H: *"No meaning should be inferred from an execution identifier"* |
| Derived reference | `causationId` | the id of the causing event/command | Inherited |
| Content-derived | `idempotencyKey`, `payloadHash`, `artifactId`, `segmentId` | 64-char lowercase hex SHA-256 | **Yes — strictly** |
| Composite human-readable | `sourceId`, `educatorId`, `connectorId`, `workerId`, `transformationId`, `capabilityId`, `canonicalRuleId` | `PREFIX\|part\|part` | **Yes** |
| Referenced only | `hypothesisId`, `evidencePackageId`, `replayPackageId` | validated, **never minted** | N/A |

Composite forms exactly as §H specifies: `SRC|<platform>|<normalizedUrlHash12>`, `EDU|<slug>`, `CONN|<sourceType>|<name>`, `WRK|<capability>`, `XF|<name>`, `CAP|<domain>|<name>`, `RULE|<educator>|<slug>`.

### 9.2 Uniqueness

Content-derived and composite identifiers are unique by construction. For opaque identifiers, §H requires *"a uniqueness check against the event log; a duplicate is a hard failure"* — **the event log does not exist in Step 1.** `new_uuid4()` therefore accepts an optional `seen` callable defaulting to `None`, and its docstring states plainly that the uniqueness check is **not enforced until Step 2 wires the event log in**. The seam exists; the enforcement is honestly labelled absent. Silently pretending to check would be worse than not checking.

### 9.3 Determinism and timestamps

Constitution §11 and Spec §19: idempotency keys are *"derived from semantic inputs, never from timestamps or attempt numbers."*

- **No identifier function reads the clock.** Not one.
- `IDEMPOTENCY_KEY_COMPOSITION` encodes all 10 §I rows; `idempotency_key()` raises `IdentifierError` if given an unknown operation or a part set that does not match the declared composition. A caller *cannot* smuggle a timestamp into a key without failing validation.
- Envelope timestamps (`issuedAt`, `occurredAt`, `recordedAt`) are ISO-8601 UTC millisecond precision per the catalog conventions, supplied by the **caller**, never read ambiently. This makes every test deterministic without freezing time.

### 9.4 Serialization

Composite ids serialize as their own string. `|` is the separator, and any component containing `|` is rejected. Slugs match `^[a-z0-9][a-z0-9-]*$`; platform/source-type components match `^[a-z0-9_-]+$`; the URL-hash component is exactly 12 lowercase hex chars. `parse_composite_id` round-trips: `parse(make(x)) == x` for all valid inputs — asserted as a test.

### 9.5 Collision handling (Spec §17)

| Class | Behaviour |
|---|---|
| Content-derived | Same hash = same object (identity, not error). Same hash with **different bytes** → `InvariantViolationError` — a corruption alarm, never a rename |
| Opaque | Duplicate → `IdentifierError` (hard failure). Enforcement deferred to Step 2 (§9.2) |
| Composite | Collision = genuine identity conflict → `IdentifierError` carrying `routes_to_review=True`. **No review system exists in Step 1**; the flag is data the review gate will read at sequence item 7 |

### 9.6 Runtime contract design

**Representation.** Plain `dict` in, read-only mapping out. `validate_*` returns a **normalized copy**; it never mutates its argument. This matches the codebase (zero dataclasses, zero typing) and makes JSON round-trip exact by construction.

**Immutable vs mutable.**

| Object | Mutability |
|---|---|
| Event envelope | **Fully immutable.** Read-only mapping; no mutator exists anywhere (Constitution §6.1) |
| Command envelope | Immutable once built. §A lifecycle `issued → validated → {accepted, rejected}` is a *classification*, not a field edit |
| Task record | **Not created in Step 1.** Only states and transition legality are defined. Constitution §7: *"Only the orchestrator writes task state"* — and there is no orchestrator |

**Versioning.** `commandVersion` and `eventVersion` are integer majors; `schemaVersion` strings are `mogo.platform.<type>.v1`. Additive-only within a major; a breaking change is a **new type**, not a new version (Spec §11). `validate_*` raises `UnsupportedContractVersionError` — distinct from `ContractValidationError` — on an unknown major, so callers can tell "I don't speak this" from "this is malformed."

**Validation boundaries.** Validation is *structural only*: field presence, type, identifier well-formedness, closed-vocabulary membership, payload-hash match. It performs **no** policy evaluation, no dispatch, no persistence, no semantic interpretation.

**Unknown-field behaviour — a real design decision.** Catalog §B says *"consumers must ignore unknown fields."* Ignoring must not mean **dropping**: `payloadHash` is computed over the canonical payload, so a validator that silently discarded unknown fields would change the hash and break round-trip verification for any consumer running an older minor. **Unknown fields are therefore retained verbatim and included in the hash; they are ignored only for semantic purposes.** Asserted by `TestUnknownFieldBehavior` and `TestSerializationRoundTrip`.

**Backward compatibility.** A v1 validator accepts any v1 envelope carrying additional optional fields. `TestContractVersionHandling` proves an envelope with a future optional field validates, round-trips byte-identically, and preserves its hash.

**Prohibited scientific semantics.** `assert_no_scientific_reference` rejects any envelope whose `subjectRefs`, `inputRefs`, or payload references a Spec §7 prohibited path, a governance-owned identifier prefix, or the symbols `mogo.evidence-canon.v1` / `mogo.evidence-package.v1` / `alexGStableHash` / `sourceTradeId` (Catalog §H reuse verdict). This runs inside envelope validation, so an operational event **cannot be constructed** carrying a scientific write target.

**Operational/scientific separation.** Distinct namespace constant (`mogo.platform.operational`), distinct schema-version strings, distinct identifier space, and a test asserting the platform's event-type vocabulary shares **no** name with the browser decision-event types (`TRADE_CLOSED`, `CANDIDATE_REJECTED`, …). Constitution §6.8; Approval #3; Inventory R-16.

---

## 10. Error and Task-State Design

### 10.1 Error taxonomy

Rooted at `PlatformError(Exception)`. Validation-class errors additionally derive from `ValueError`, matching the repo convention (`EvidenceValidationError(ValueError)`, `IllegalTransitionError(ValueError)`), so existing `except ValueError` handlers keep working.

| Type | Raised when | Derives |
|---|---|---|
| `ContractValidationError` | required field missing, wrong type, closed-vocabulary violation, payload-hash mismatch | `PlatformError`, `ValueError` |
| `UnsupportedContractVersionError` | `commandVersion`/`eventVersion` major is unknown | `PlatformError`, `ValueError` |
| `IdentifierError` | malformed identifier, bad composite part, unknown idempotency operation, opaque duplicate, composite identity conflict | `PlatformError`, `ValueError` |
| `InvariantViolationError` | a rule that must hold structurally does not — e.g. same content hash over different bytes | `PlatformError`, `RuntimeError` |
| `ProtectedBoundaryViolationError` | a Spec §7 boundary is crossed | `PlatformError`, `RuntimeError` |
| `ConfigurationError` | platform configuration is absent, contradictory, or names an undeclared resource | `PlatformError`, `RuntimeError` |
| `InternalPlatformError` | a defect in the platform itself; never used for input validation | `PlatformError`, `RuntimeError` |
| `IllegalTaskTransitionError` | a transition absent from `LEGAL_TRANSITIONS` | `PlatformError`, `ValueError` |
| `LateTransitionAnomaly` | a transition arriving at an already-terminal task | `PlatformError`, `RuntimeError` |

`ERROR_CLASSES` carries the 12 §K operational classes as **inert data** with `retryable` / `terminal` / `routes_to_review` flags. `policy_blocked` is `retryable=False` and is asserted so by a dedicated test — Constitution §11: *"Retrying a policy denial is an attempt to launder it."* **No retry, backoff, or dead-letter logic is implemented.**

### 10.2 Task-state definitions

**13 states**, from Spec §18.1 and Catalog §L:

`requested` · `policy_check` · `blocked` · `awaiting_review` · `queued` · `claimed` · `running` · `failed` · `retry_scheduled` · `succeeded` · `dead_lettered` · `suppressed` · `cancelled`

**4 terminal:** `succeeded`, `dead_lettered`, `suppressed`, `cancelled`. **9 non-terminal:** the rest.

**25 legal transitions** — Catalog §L's 16 explicit edges plus the 9 `any non-terminal → cancelled` edges (§L is authoritative over the §18.1 diagram, which shows only 3 cancel edges "for legibility"):

| From | To | Authority |
|---|---|---|
| `requested` | `policy_check` | orchestrator |
| `policy_check` | `queued` | policy gate (permit **or** `not_applicable`) |
| `policy_check` | `blocked` | policy gate (deny / unknown / **class indeterminate**) |
| `blocked` | `awaiting_review` | orchestrator |
| `queued` | `claimed` | worker runtime (CAS lease) |
| `claimed` | `running` | worker runtime |
| `claimed` | `queued` | orchestrator (lease expired) |
| `running` | `queued` | orchestrator (lease expired) |
| `running` | `succeeded` | orchestrator |
| `running` | `awaiting_review` | orchestrator |
| `running` | `failed` | orchestrator |
| `failed` | `retry_scheduled` | orchestrator |
| `failed` | `dead_lettered` | orchestrator |
| `retry_scheduled` | `queued` | orchestrator |
| `awaiting_review` | `queued` | review gate (approved) |
| `awaiting_review` | `suppressed` | review gate (rejected) |
| *any non-terminal* (×9) | `cancelled` | operator (explicit, audited) |

Two rules encoded as data and tested:

- **Fail-closed policy default** — a task whose operation class cannot be determined is treated as acquisition-class and routed to `blocked`, mirroring the licensing default (§L footnote 2, Spec §18.1).
- **Terminal absorption** — transitions out of a terminal state are illegal; a transition *arriving* at an already-terminal task is a `LateTransitionAnomaly`, *"logged as anomalies and **not applied**"* (Catalog §C). Step 1 classifies it; **there is no logger yet**, and the docstring says so.

**No orchestrator, no executor, no task object, no persistence.** These are predicates over a constant table.

---

## 11. Testing Plan

All stdlib `unittest`, offline, deterministic. Estimated 85–110 assertions across 4 files.

### 11.1 `test_platform_identifiers.py`

| Required coverage | Tests |
|---|---|
| **Deterministic identifiers** | `test_content_hash_is_stable_across_calls` · `test_content_hash_is_key_order_independent` · `test_content_hash_is_array_order_sensitive` · `test_composite_id_round_trips_through_parse` · `test_idempotency_key_stable_across_simulated_retries` · `test_idempotency_key_ignores_attempt_number_and_timestamp` · `test_all_ten_catalog_I_operations_have_a_composition` |
| **Invalid identifier rejection** | `test_rejects_uppercase_sha256` · `test_rejects_short_sha256` · `test_rejects_non_uuid4_versions` · `test_rejects_pipe_inside_composite_component` · `test_rejects_empty_or_whitespace_component` · `test_rejects_unknown_composite_prefix` · `test_rejects_unknown_idempotency_operation` · `test_rejects_missing_required_key_part` |
| **Collision handling** | `test_same_bytes_same_hash_is_identity_not_error` · `test_same_hash_different_bytes_raises_invariant_violation` · `test_composite_identity_conflict_flags_routes_to_review` |
| **Canonicalization equivalence** | `test_platform_canonicalization_matches_documented_rule_without_importing_graph_common` (fixture corpus incl. nested objects, unicode, empty containers; asserts `graph_common` is **not** in `sys.modules`) · `test_rejects_nan_and_infinity` |
| **No unauthorized minting** | `test_module_exposes_no_hypothesis_id_minter` · `test_module_exposes_no_evidence_package_id_minter` · `test_module_exposes_no_replay_package_id_minter` (introspects the module's public surface) |

### 11.2 `test_platform_envelopes.py`

| Required coverage | Tests |
|---|---|
| **Command-envelope validation** | one `test_rejects_missing_<field>` per §A required field (14) · `test_accepts_minimal_valid_command` · `test_defaults_priority_5_and_attempt_limit_3` · `test_rejects_unregistered_command_type` · `test_rejects_malformed_correlation_id` |
| **Event-envelope validation** | one `test_rejects_missing_<field>` per §B required field (15) · `test_error_class_required_when_execution_result_is_failure` · `test_sequence_must_be_monotonic_int` · `test_event_mapping_is_read_only` · `test_no_mutator_exists_on_event_module` |
| **Contract-version handling** | `test_unknown_major_raises_unsupported_version_not_validation_error` · `test_v1_accepts_additive_optional_field` · `test_version_field_required` |
| **Prohibited-hash behaviour** | `test_payload_hash_mismatch_is_rejected` · `test_payload_hash_recomputes_identically` |
| **Unknown-field behaviour** | `test_unknown_fields_are_retained_not_dropped` · `test_unknown_fields_are_included_in_payload_hash` · `test_unknown_fields_do_not_affect_semantic_validation` |
| **Serialization round trips** | `test_command_json_round_trip_is_byte_identical` · `test_event_json_round_trip_is_byte_identical` · `test_round_trip_preserves_payload_hash` · `test_round_trip_preserves_unicode` |
| **Operational/scientific separation** | `test_event_namespace_is_operational` · `test_platform_event_types_disjoint_from_trading_decision_event_types` · `test_rejects_subject_ref_under_evidence_dir` · `test_rejects_subject_ref_under_docs_campaigns` · `test_rejects_prereg_reference` · `test_rejects_evidence_canon_symbol` · `test_rejects_evidence_package_symbol` |

### 11.3 `test_platform_task_states.py`

| Required coverage | Tests |
|---|---|
| **Task-state definitions** | `test_exactly_thirteen_states` · `test_exactly_four_terminal_states` · `test_state_names_match_catalog_L_verbatim` · `test_every_state_reachable_from_requested` |
| **Legal transitions** | `test_all_sixteen_explicit_catalog_L_edges_are_legal` · `test_every_non_terminal_may_be_cancelled` · `test_transition_count_is_twenty_five` · `test_authority_recorded_for_every_edge` |
| **Prohibited transitions** | `test_terminal_states_have_no_successors` · `test_queued_cannot_go_directly_to_succeeded` · `test_running_cannot_go_directly_to_dead_lettered` · `test_blocked_cannot_go_directly_to_queued` · `test_succeeded_to_failed_raises_illegal_transition` · exhaustive sweep: `test_every_pair_not_in_table_is_rejected` (13×13 = 169 pairs) |
| **Terminal absorption** | `test_late_transition_into_terminal_is_anomaly_not_applied` |
| **Fail-closed default** | `test_indeterminate_operation_class_routes_to_blocked` |

### 11.4 `test_platform_boundaries.py`

| Required coverage | Tests |
|---|---|
| **Protected-boundary enforcement** | `test_no_write_mode_open_in_platform_tree` (static scan for `open(...,'w'/'a'/'x')`, `os.remove`, `os.unlink`, `shutil.rmtree`, `Path.write_*`, `os.rename`) · `test_no_prohibited_path_literal_in_platform_tree` (all 6 §7 targets) |
| **Absence of unauthorized scientific writes** | `test_platform_never_references_evidence_dir` · `test_platform_never_references_docs_campaigns` · `test_platform_never_references_prereg` · `test_platform_never_references_verified_replay_record` · `test_platform_never_references_hypothesis_registry_for_write` · `test_platform_never_references_index_html` |
| **No network capability** | `test_no_banned_network_imports_in_platform_tree` — extends the proven `TestNoNetworkImports` pattern (`test_acquisition.py:775`) to `platform/**` |
| **Boundary integrity** | `test_platform_imports_no_trader_intelligence_module` (§6.7: adapters only, and none exist) · `test_platform_imports_no_scientific_symbols` |
| **Import-convention integrity** | `test_no_init_py_anywhere_under_platform` · `test_stdlib_platform_module_still_importable_and_functional` (asserts `platform.system()` works) |
| **Runtime floor** | `test_python_version_floor` (≥ 3.14) |

> `test_no_init_py_anywhere_under_platform` and `test_stdlib_platform_module_still_functional` are the mechanical guard against §4.2's collision. If a future contributor adds an `__init__.py`, the suite fails immediately with a message explaining why — rather than the whole repository breaking in a confusing way.

---

## 12. Protected-Boundary Verification

### 12.1 Paths and functions that must not be modified in Step 1

**Frozen — no modification of any kind:**

```
evidence/                                    (33 Campaign C1 artifacts)
docs/campaigns/C1/                           (8 documents)
docs/trader-intelligence/governance/PREREG-001-alex-multipair-2026-08-04.md
docs/trader-intelligence/governance/PREREG-002-alex-c1-execution-2026-08-05.md
docs/trader-intelligence/governance/STATISTICAL-GOVERNANCE.md
docs/MOGO-003-VERIFIED-REPLAY-RECORD.md
tags: campaign-c1-adjudication-complete, campaign-c1-pre-adjudication-frozen,
      mogo-002-complete, mogo-003-complete, v12.*
```

**Protected — drift-gated:**

```
index.html                                   (63 protected functions + 4 protected constants:
                                              WEIGHTS, ALERT_THRESHOLD, RULES, RULES_ALEXG)
regression-baseline-tools.py
regression-baseline.json
the replay engine, evidence-capture seam, mogo.evidence-canon.v1, mogo.evidence-package.v1
```

**Governed — additive-only, and not touched in Step 1:**

```
docs/trader-intelligence/schema/             (12 existing schemas)
docs/trader-intelligence/hypothesis-registry.json
scripts/trader_intelligence/                 (36 modules)
tests/run_all.sh                             (D-12 gated)
```

### 12.2 Confirmation

The proposed plan creates files under exactly two new roots — `platform/` and `tests/platform/` — plus one new file `tests/run_platform_tests.sh`. It modifies nothing. Therefore:

| Must not be altered | Status under this plan |
|---|---|
| Campaign C1 | ✅ Not touched. No proposed file reads or writes `evidence/` or `docs/campaigns/`; a test forbids even the path literal |
| Frozen evidence | ✅ Not touched. 33/33 artifacts re-verified this session against `CAMPAIGN_C1_EVIDENCE_MANIFEST.md` — 0 missing, 0 mismatched, 0 unlisted |
| Preregistration | ✅ Not touched. Path literal forbidden by test |
| Adjudication | ✅ Not touched |
| Scientific registries | ✅ Not touched. `hypothesis-registry.json` is read-only per Spec §7 and unreferenced |
| Trading execution | ✅ Not touched. No network capability exists; Constitution §4.14 (no live trading) is structurally satisfied |
| Replay execution | ✅ Not touched. Out of scope; no replay symbol appears |
| Protected strategy functions | ✅ Not touched. `index.html` is unreferenced; drift gate re-run as a validation command |
| Existing scientific evidence formats | ✅ Not touched. `mogo.evidence-canon.v1` and `mogo.evidence-package.v1` are **forbidden symbols** in `platform/`, enforced by test |

### 12.3 Legacy untracked documents — Git status and conflict assessment

All four are `??` (untracked), unmodified, unstaged, mtimes 2026-08-04 — predating MOGO-006, MOGO-008 and MOGO-009. **None is authoritative.** Disposition is not resolved here, per your instruction.

| Document | Conflicts with approved MOGO-009 architecture? |
|---|---|
| `docs/architecture/MOGO_AGENTIC_SYSTEM_BLUEPRINT.md` | **YES — material conflict.** Three specifics: (1) §7 "Agent Communication Model" has agents exchanging messages directly under a `mogo.agent-msg.v1` envelope — contradicting **Constitution §4.4** (*"Workers never directly call other workers"*) and **§4.5** (*"coordinated only through governed commands, workflows, and events"*). (2) That envelope sets `contentHashCanonicalization: "mogo.evidence-canon.v1"` — precisely the cross-domain coupling **Catalog §H** rejects (*"not reused — importing them would couple automation to trading"*). (3) Its `messageId: MSG\|<agent>\|<utc>\|<seq>` embeds a timestamp in an execution identifier, contradicting **Catalog §H** (execution ids are opaque UUIDv4). It also proposes eleven standalone agents, which is Inventory **R-01** (*"disconnected agent — highest-likelihood failure"*). The document self-labels *"PROPOSED — Phase 0… Nothing implemented"* and carries a prominent warning that it was written while the repository was **unreadable** due to a macOS TCC revocation. **Highest-risk item: it sits in `docs/architecture/` beside the authoritative specification and could be mistaken for current.** |
| `docs/reports/MOGO-RESEARCH-ACQUISITION-ARCHITECTURE.md` | **Partial conflict — superseded, not contradictory in principle.** Its central recommendation (close the discovery/acquisition gap next) predates and is overridden by **D-08** (policy gate before any connector) and **D-15** (filesystem connector first, YouTube deferred). Written at HEAD `f8004fe`, review-only. It contains one genuinely valuable, still-true finding: `DECISION\|MOGO\|20260725\|002` established a zero-network posture enforced by a permanent test, `test_no_banned_imports_in_any_acquisition_script` — **which I verified exists** (`test_acquisition.py:778`) and which §11.4 of this plan extends to `platform/**`. |
| `docs/reports/MOGO-004-STEP-1-COMPLETION-REPORT.md` | **No architectural conflict.** Historical MOGO-004 replay-pilot verification at HEAD `bb8498f`; concerns RUN-001 and the PRE-REG-001 gate. Superseded by MOGO-005–008 |
| `docs/reports/MOGO-004-STEP-1-PILOT-EXECUTION-BLOCKED.md` | **No architectural conflict.** Historical; records three unsatisfiable preconditions for a replay run. Its Rule 0 / browser-isolation constraints remain valid but are unrelated to Step 1 |

**Handling in Step 1: none.** They are not read as authority, not staged, not moved, not modified. The commit boundary (§15) excludes them explicitly.

---

## 13. Validation Commands

Run from the repository root, in order, after implementation.

**Honest note on tooling:** this repository has **no formatter, no linter, and no type checker** — none is installed and no config exists for any. Step 1 introduces none, because each would be the project's first dev dependency. Steps 1–2 below are the stdlib substitutes that actually apply here.

```bash
# ── 1. Syntax / compile check (stdlib substitute for a linter) ──────────────
python3 -m compileall -q platform tests/platform && echo "COMPILE OK"

# ── 2. Warnings-as-errors import check (catches deprecations, shadowing) ────
python3 -W error -c "
import sys, os
sys.path.insert(0, os.path.join('platform', 'contracts'))
import platform_ids, platform_errors, platform_vocabulary
import platform_command, platform_event, platform_task_states, platform_boundaries
import platform as stdlib_platform
assert stdlib_platform.system(), 'stdlib platform module was shadowed'
print('IMPORT OK — stdlib platform intact:', stdlib_platform.system())
"

# ── 3. New platform unit tests ─────────────────────────────────────────────
python3 -m unittest -v \
  tests.platform.test_platform_identifiers \
  tests.platform.test_platform_envelopes \
  tests.platform.test_platform_task_states \
  tests.platform.test_platform_boundaries

# ── 3b. Same, via the new standalone runner ────────────────────────────────
bash tests/run_platform_tests.sh

# ── 4. Existing Python suites must be unaffected (regression) ──────────────
python3 -m unittest \
  tests.trader_intelligence.test_graph \
  tests.trader_intelligence.acquisition.test_acquisition \
  tests.trader_intelligence.evidence.test_evidence \
  tests.trader_intelligence.evidence.test_phase1b \
  tests.trader_intelligence.evidence.test_phase7a \
  tests.knowledge_engineering.test_knowledge_engineering \
  tests.strategy_fidelity.test_strategy_fidelity \
  tests.strategy_fidelity.test_rule_evidence_join

# ── 5. Canonical gate — MUST still pass, and MUST be unmodified ────────────
bash tests/run_all.sh

# ── 6. Protected-function drift gate (also runs inside step 5) ─────────────
python3 regression-baseline-tools.py

# ── 7. Git diff review — expect ONLY new paths, zero modifications ─────────
git status --porcelain --untracked-files=all
git diff --stat                       # expect: empty
git diff --cached --stat              # expect: empty until staging
git diff --name-status HEAD           # expect: empty (no tracked file changed)

# ── 8. Protected-path verification — nothing frozen may have changed ───────
git status --porcelain -- evidence/ docs/campaigns/ index.html \
    docs/trader-intelligence/governance/ docs/MOGO-003-VERIFIED-REPLAY-RECORD.md \
    tests/run_all.sh regression-baseline-tools.py regression-baseline.json
# expect: no output

python3 - <<'PY'
import re, hashlib, os
man = open('docs/campaigns/C1/CAMPAIGN_C1_EVIDENCE_MANIFEST.md').read()
rows = re.findall(r'\|\s*\d+\s*\|\s*`([^`]+\.json)`\s*\|.*?`([0-9a-f]{64})`\s*\|', man)
bad = [n for n, h in rows
       if hashlib.sha256(open(os.path.join('evidence', n), 'rb').read()).hexdigest() != h]
print("C1 artifacts verified: %d/%d, mismatches: %s" % (len(rows) - len(bad), len(rows), bad or "none"))
assert not bad and len(rows) == 33
PY

# ── 9. Working-tree verification — only the intended new paths exist ───────
git status --porcelain --untracked-files=all | grep -v '^?? docs/' || true
git clean -nd platform tests/platform          # dry run: lists only intended new files
```

**Pass criteria:** steps 1–6 all green; step 5 reports the same suite/fixture counts as before Step 1 and zero drift; step 7 shows an **empty** `git diff` (no tracked file modified); step 8 outputs nothing and verifies 33/33; step 9 lists only `platform/**`, `tests/platform/**`, `tests/run_platform_tests.sh`.

---

## 14. Rollback Strategy

Step 1 is fully reversible because it is **purely additive** — it creates new paths and modifies nothing.

**Before commit:**

```bash
rm -rf platform tests/platform tests/run_platform_tests.sh
git status --porcelain --untracked-files=all   # back to the 4 legacy ?? entries
```

**After commit:**

```bash
git revert --no-edit <step-1-commit>           # preferred: preserves history
# or, if not yet pushed:
git reset --hard bd6ff7c8ccebe31431c4d58c345894d7effdb738
```

**Why rollback cannot affect existing MOGO behaviour or scientific records:**

| Property | Consequence for rollback |
|---|---|
| Zero modified tracked files | Nothing to restore. Reverting removes new paths and touches nothing else |
| Zero new dependencies | No install to undo, no lock file, no environment change |
| Not in the canonical gate | `tests/run_all.sh` is unmodified, so removing `platform/` cannot break the gate — verified: its glob is `tests/run_*_tests.js`, which never matched a `.sh` or a `tests/platform/*.py` file |
| No `__init__.py` under `platform/` | Nothing was ever added to any import path; stdlib `platform` was never shadowed (test-enforced) |
| No I/O of any kind | No file was created outside the repo, no database, no artifact store, no cache, no lock, no temp directory |
| No writes to protected paths | Structurally impossible — no write path exists in the code |
| `regression-baseline.json` untouched | Drift gate baseline unchanged; removing Step 1 cannot introduce drift |

**Residue after a full revert: none.** The repository returns byte-for-byte to `bd6ff7c`, with the same four untracked legacy documents.

---

## 15. Commit Boundary

**One bounded commit.**

**Exact scope — only these paths:**

```
platform/README.md
platform/contracts/platform_ids.py
platform/contracts/platform_errors.py
platform/contracts/platform_vocabulary.py
platform/contracts/platform_command.py
platform/contracts/platform_event.py
platform/contracts/platform_task_states.py
platform/contracts/platform_boundaries.py
tests/platform/test_platform_identifiers.py
tests/platform/test_platform_envelopes.py
tests/platform/test_platform_task_states.py
tests/platform/test_platform_boundaries.py
tests/run_platform_tests.sh
```

**Suggested commit message:**

```
MOGO-010 Step 1: platform contracts, identifiers and boundary tests

Creates the platform/ bounded context with contract-level definitions only.
No runtime, orchestrator, worker, connector, event store, or persistence is
introduced, and no acquisition path exists.

Implements, from the approved MOGO-009 architecture (ADR-012, HEAD bd6ff7c):
  - Identifier model and idempotency-key composition   (Spec §17; Catalog §H, §I)
  - Command envelope contract and validation           (Catalog §A)
  - Operational event envelope contract and validation (Catalog §B; Constitution §6)
  - Platform error taxonomy and §K error-class table   (Catalog §K)
  - Task states and transition legality, contracts only (Catalog §L)
  - Closed vocabularies                                 (Catalog §J, §M, §O)
  - Protected-boundary static tests                     (Spec §7, §25; Constitution §16)

Constraints honoured:
  - Zero new dependencies; Python 3.14 stdlib only (D-01 manifest deferred)
  - Zero modifications to existing tracked files
  - No __init__.py under platform/ -- a repo-root platform package would shadow
    and break the stdlib platform module; modules are imported by bare name after
    a sys.path insert, matching scripts/trader_intelligence/ convention
  - tests/run_all.sh unmodified (D-12 / Spec §33 approval gate not consumed);
    platform suites run via the standalone tests/run_platform_tests.sh
  - platform/ contains no write path to evidence/, docs/campaigns/, the
    pre-registrations, MOGO-003-VERIFIED-REPLAY-RECORD.md, or index.html
  - No network-capable import anywhere under platform/

Campaign C1 unchanged: 33/33 artifacts hash-verified against the manifest.
Protected-function drift gate: zero drift (63 functions, 4 constants).

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
```

**Files that must remain excluded from this commit:**

- All four legacy untracked documents (disposition deferred; §12.3)
- `tests/run_all.sh` — D-12 / Spec §33 gate
- `docs/TESTING.md`, `docs/KNOWN_ISSUES.md` — deferred to the D-12 change
- Any `pyproject.toml` / `requirements.txt` / lock file — §8
- `regression-baseline.json` — never `--update` reflexively (Inventory §4)
- `.gitignore` — no artifact store in Step 1

**Evidence required before commit approval:**

1. All 9 validation command groups (§13) green.
2. `bash tests/run_all.sh` — same suite and fixture counts as at `bd6ff7c`, zero drift, exit 0.
3. `python3 regression-baseline-tools.py` — *"No drift: all 63 protected functions and 4 protected constants are byte-identical."*
4. C1 manifest verification — **33/33**, 0 mismatches.
5. `git diff --name-status HEAD` — **empty** (proves zero tracked-file modification).
6. `git status --porcelain` shows only the 13 intended new paths plus the 4 pre-existing `??` documents.
7. All 8 pre-existing Python suites pass unchanged.
8. `test_stdlib_platform_module_still_importable_and_functional` passes.

---

## 16. Architecture Drift Check

| Requirement | Confirmation |
|---|---|
| **Every proposed file belongs to an approved bounded context** | ✅ All eight source files live in `platform/contracts/`, which is Inventory §10's approved `contracts/` sub-context (*"task/event/connector schemas (versioned)"*) inside the approved top-level `platform/` (Approval #2, Spec §10). Tests mirror the source tree in `tests/platform/`, exactly as Inventory §10 prescribes |
| **No isolated agent architecture is introduced** | ✅ No agent, no daemon, no standalone entry point, no `__main__`, no CLI. Every file is an importable definition module. Inventory R-01 and Spec §31 (*"Worker exists only as an orchestrator capability; no standalone entry point"*) are satisfied trivially, because no executable exists |
| **No worker-to-worker calls are introduced** | ✅ No worker exists. `platform/contracts/` contains no invocation, dispatch, subprocess, or import of any executing component. Constitution §4.4 |
| **No connector bypass is introduced** | ✅ No connector and no policy gate exist. The licensing vocabulary is inert data in which `UNKNOWN` carries flags **identical** to `PROHIBITED` (Constitution §5.2, Approval #12) — so the first gate implemented in sequence item 5 inherits a fail-closed table rather than defining one |
| **No external workflow engine is introduced** | ✅ Zero dependencies. No Temporal, Prefect, Airflow, or scheduler of any kind. D-02, Approval #5 |
| **No external message broker is introduced** | ✅ Zero dependencies. No Redis, Kafka, RabbitMQ, or queue runtime. D-03, Approval #8 |
| **Operational events remain distinct from scientific evidence** | ✅ Distinct namespace (`mogo.platform.operational`), distinct schema-version strings, distinct identifier space; envelope validation **rejects** any reference to `evidence/`, `docs/campaigns/`, the pre-registrations, or the `mogo.evidence-canon.v1` / `mogo.evidence-package.v1` symbols. Test-enforced. Constitution §6.8, Approval #3, Inventory R-16/R-17 |
| **No acquired material can become canonical knowledge** | ✅ Nothing can acquire anything — there is no connector, no network-capable import (test-enforced), and no I/O. Context 10 is neither referenced nor writable; the review gate (context 8) does not exist. Spec §6.6 |
| **No unauthorized scientific writes are enabled** | ✅ `platform/**` contains **no write path at all** — no `open(...,'w')`, no `os.remove`, no `shutil`, no `Path.write_*` — asserted by static test. Contexts 13 and 14 are read-only *and* unreferenced. Constitution §4.21, §4.22; Spec §7 |
| **Consistent with ADR-012** | ✅ Implements sequence item 1 (*"Contracts and identifiers — non-executable schemas, then the identifier library"*) and nothing beyond it. Honours D-04/D-05 (contracts shaped so the event log is authoritative and task state derived), D-07, D-11 (`schemaVersion`, additive-only), D-16 (`CAP\|` id form and lifecycle states as data). One deviation of **timing** on D-01's manifest, declared in §8 and raised for approval in §17 D-1 |
| **Consistent with the Automation Platform Constitution** | ✅ §3 authority order respected throughout (Catalog §L over the §18.1 diagram). §4.4/§4.5 satisfied structurally. §5.2 encoded as data. §6 immutability enforced by read-only mappings and the absence of mutators. §11 idempotency keys provably free of timestamps and attempt numbers. §12 no secret handling introduced. §16 boundary rules made mechanical — which is the specific thing the Constitution says is otherwise *"most likely to be broken under time pressure"* |

**Additional drift checks performed and passed:** no ingestion-pipeline import (Spec §6.7 — adapters only, none exist); no `index.html` reference; no browser symbol reuse (`alexGStableHash`, `sourceTradeId` — Catalog §H); no governance identifier minted (`hypothesisId`, `evidencePackageId`, `replayPackageId`).

---

## 17. Risks, Ambiguities, and Decisions Requiring Approval

### Decisions I need from you before implementation

**D-1 · Package/runtime manifest — recommend deferring.** ADR-012 D-01 approved *"Python-first with a manifest"* and was listed in your Step 1 scope as *"only if justified."* I assess it as **not justified in Step 1**: zero dependencies make it near-vacuous, and §4.2 establishes that `platform/` **cannot be a Python package**, so packaging metadata naming it would describe something that cannot exist. The Python floor is instead enforced executably by a test. *Recommendation: no manifest in Step 1; revisit when a real dependency first appears.* If you prefer D-01's letter, the alternative is a root `pyproject.toml` containing only `requires-python = ">=3.14"` and no `[project.dependencies]`.

**D-2 · Command/event vocabulary — recommend transcribing §J as v1, extensible.** Catalog §J lists 17 commands and 34 events but states: *"Not finalized. Names and payloads are Step 3 work."* Envelope validation needs a closed enum to validate against. *Recommendation: transcribe §J verbatim as `v1`, additive-only, with a docstring recording the §J caveat — names may still be added; the payloads remain unspecified in Step 1.* The alternative is an open `commandType` in Step 1, which weakens §A's *"targetCapability registered"* validation to nothing.

**D-3 · Test-runner integration — recommend a standalone runner.** Your scope asks for "initial test-runner integration," but Spec §33 lists *"any change to `tests/run_all.sh`"* as an approval gate, and D-12 is *"Recommended"*, not approved. Constitution §3 forbids this plan from overriding that. *Recommendation: ship `tests/run_platform_tests.sh` standalone in Step 1, and do the `run_all.sh` + `docs/TESTING.md` integration as one separately-authorized D-12 change.* If you authorize D-12 now, I would add a clearly-labelled "platform suites" section reporting its own counts, with the drift gate still running **last** and remaining decisive — never conditional on platform tests passing.

**D-4 · Licensing vocabulary in Step 1?** Catalog §M's 12 statuses are approved (Approvals #11, #12), and encoding `UNKNOWN` with flags identical to `PROHIBITED` as data costs nothing and makes the rule true from the first commit. But the policy **gate** is sequence item 5, and your scope list did not name licensing. *Recommendation: include the status table and its test; exclude anything that evaluates it.* Say the word and I drop it to `platform_vocabulary.py`'s later revision instead.

### Risks carried, not blocking

**R-1 · `platform/` shadows a stdlib module.** Empirically verified (§4.2). Mitigated by the no-`__init__.py` + `sys.path`-insert convention and two guard tests. **Residual risk:** a future contributor adds `__init__.py` and breaks stdlib `platform` repo-wide. The guard test fails loudly with an explanatory message, and `platform/README.md` states the rule at the top.

**R-2 · `MOGO_AGENTIC_SYSTEM_BLUEPRINT.md` sits in `docs/architecture/`.** It contradicts Constitution §4.4/§4.5 and Catalog §H (§12.3), and its location makes misreading it as current entirely plausible. Disposition is out of scope for this step per your instruction. **This is the highest-value open item after Step 1** — the cheapest fix is a superseded-by header or a move to `docs/archive/`, and it is your call, not mine.

**R-3 · Local `main` has no upstream; `origin/main` is unrelated history.** Carried from session initialization. `git push origin main` would target the wrong branch (`abfc763`, the web-upload line) rather than `origin/mogo-main`. Not blocking for a planning step, but it must be resolved **before the Step 1 commit is pushed.** Inventory §16 item 6 lists it as already open.

**R-4 · Two stale local branches.** `mogo-003-phase-1-evidence-platform` (`c638629`) and `claude/gracious-cohen-bd8041` (`4fb117e`, held open by a worktree). The latter's commit message is *"Add canonical repository test runner (tests/run_all.sh)"* — it touches the exact file D-12 gates, so it should be dispositioned **before** any runner work, not during it.

**R-5 · No linter, formatter, or type checker exists.** §13 substitutes `compileall` and `-W error`. Adding any of the three would be the project's first dev dependency and belongs in its own decision, not smuggled into Step 1.

**R-6 · Canonicalization is re-implemented, not shared.** Required by Spec §6.7 and §17 (*"adapted… new namespace"*), but two implementations can drift. Mitigated by `test_platform_canonicalization_matches_documented_rule_without_importing_graph_common`, which asserts byte-identical output over a shared fixture corpus while proving the import boundary held.

### Ambiguity resolved by authority order, recorded for transparency

Spec §18.1's diagram shows `cancelled` reachable from three states; Catalog §L says **any** non-terminal state may be cancelled. The Specification itself designates §L authoritative. This plan implements §L's broader rule — **25 transitions, not 19** — and a test asserts the count so the discrepancy cannot be silently reintroduced.

---

## 18. Final Recommendation

Proceed with Step 1 as scoped in §5–§6, subject to your rulings on D-1 through D-4.

The repository is verifiably at the approved commit, clean, and unaltered by this session. The proposed step implements exactly sequence item 1 of Spec §32 — contracts and identifiers — and nothing beyond it. It adds no dependency, modifies no existing file, creates no executable path, and can be removed with three `rm` commands.

Its most useful property is ordering: it lands the protected-boundary tests **before** there is any platform code for them to police. Constitution §16 names unenforced assumptions as the standing MOGO-004 lesson, and this is the only sequencing in which those tests function as a gate rather than as documentation of a boundary that has already been crossed.

Nothing was implemented, created, modified, staged, committed, or pushed during this step. The working tree is byte-identical to its state at session start: 0 tracked modifications, the same 4 pre-existing untracked documents.

**READY FOR STEP 1 IMPLEMENTATION APPROVAL**

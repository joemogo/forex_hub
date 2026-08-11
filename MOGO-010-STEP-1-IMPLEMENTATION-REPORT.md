# MOGO-010 STEP 1 — CORRECTED ZERO-KNOWN-DEFECT IMPLEMENTATION AND VALIDATION REPORT

**Milestone:** MOGO-010 Phase II, Step 1 (corrected) · **HEAD:** `bd6ff7c8ccebe31431c4d58c345894d7effdb738`
**Supersedes:** the pre-correction implementation report · **Date:** 2026-08-07
**Governing document:** `AUTOMATION_PLATFORM_CONSTITUTION.md` v1.0 — senior to everything here

---

## 1. Executive Result

All six approved corrections are implemented and validated. **15 files in the commit boundary, 0 existing tracked files modified, 0 dependencies, 268 platform tests passing, 19/19 mutations detected and reverted, Campaign C1 verified 33/33, zero protected-function drift.** The canonical gate `tests/run_all.sh` is byte-identical and still passes 947/947 fixtures. The six pre-existing Python failures remain exactly the same six, unrepaired.

Three things worth your attention.

**First, the migration was proven byte-preserving before anything was edited, and the proof survives to the end.** `vocabulary.py` still carries the exact SHA-256 it had as `platform_vocabulary.py` before the correction — `cd6e058f9e4f0513cba12ce7c6153ca1da097cc2138460db081e72ec0e575959`. Moving the two dependency-free files first, and requiring their hashes to match, isolated "did the move lose bytes?" from "did the edit break something?" before either question could contaminate the other.

**Second, mutation 17 escaped detection on the first run, and it revealed a test weakness rather than a code defect.** Unwiring the command-payload shape check did not fail any test — because `object()` and `NaN` are still rejected by canonical hashing, and a coerced `{1:"a"}` key then fails the hash comparison instead. Every case raised the right exception class for the wrong reason. I strengthened the test to assert the `$payload.x` path, which only the shape validator can produce, and added `test_command_payload_shape_is_checked_before_hashing`. The mutation is now caught by both. **No test was weakened to make a mutation pass; the test was made stricter to make the mutation fail.**

**Third, the correction fixed a rule that had been enforced by a test.** The previous `test_no_init_py_anywhere_under_platform` encoded an over-generalisation as policy. Removing it required replacing it with something stronger, not merely deleting it: the narrow root-only guard, a docstring-only assertion on the two package markers, and a retired-flat-module check. Nine layout guards now exist where one over-broad rule stood.

## 2. Authority and Scope

Authority order applied unchanged: **Constitution > ADR-012 > Architecture Specification > Contract Catalog > correction plan > this authorization.** No conflict with any higher-authority document was found, and none required amendment.

The one deviation from an authoritative document is from **Inventory §10**, titled "*Recommended* platform location", which sketches `platform/contracts/` directly. The src layout places contracts at `platform/src/mogo_platform/contracts/`. This does not conflict with any approved decision: ADR-012 approval #2 names the **top-level `platform/` bounded context**, which is preserved exactly, and Architecture §7/§25 constrain `platform/**`, which still covers everything. The Inventory is the superseded Step 1 historical record. An ADR-012 addendum recording the refinement remains optional and is the operator's call.

**Scope held.** No orchestration, worker, connector, event persistence, SQLite, filesystem queue, artifact acquisition, licensing-policy execution, Capability Registry behavior, retry execution, review workflow, adapter, scientific evidence write, replay, paper trading, live trading, or strategy optimization. No unrelated repair. No Step 2 work.

## 3. Approved Corrections Implemented

| # | Correction | Status | Evidence |
|---|---|---|---|
| **I-1** | Import and package architecture | ✅ | `mogo_platform` package under `platform/src/`; relative sibling imports; one `sys.path` entry, tests only; no flat module importable |
| **I-2** | Unsupported unknown-field values | ✅ | `object`, `set`, `frozenset`, `bytes`, `bytearray`, `complex` rejected at any depth in both envelopes and both payload paths |
| **I-3** | Non-finite floats | ✅ | `NaN`, `+Infinity`, `−Infinity` rejected at any depth via `math.isfinite` |
| **I-4** | Non-string mapping keys | ✅ | `int`, `bool`, `float`, `tuple`, `None` keys rejected; never coerced, never stringified |
| **I-5** | Idempotent validation | ✅ | `canonical_json_bytes` routes through `as_plain`; `validate(validate(x))` succeeds preserving values, unknown fields, payload hash and immutability |
| **I-6** | Dependency classification | ✅ | Regenerated review classifies against `sys.stdlib_module_names`; reports `platform` as standard library, `mogo_platform` as project code, third-party count **0** |

## 4. Final Directory and Package Architecture

```
platform/
  README.md
  src/                                   ← the ONE sys.path entry
    mogo_platform/
      __init__.py                        ← docstring only
      contracts/
        __init__.py                      ← docstring only
        ids.py  errors.py  vocabulary.py  command.py
        event.py  task_states.py  boundaries.py
tests/platform/                          ← 4 suites
tests/run_platform_tests.sh              ← unchanged
```

**`platform/__init__.py` does not exist and must never exist.** Package-internal imports are relative (`from . import errors`); external callers import `from mogo_platform.contracts import ids`.

## 5. Files Created

| Path | Bytes | Lines | Purpose |
|---|---:|---:|---|
| `platform/src/mogo_platform/__init__.py` | 1,428 | 28 | Package marker — docstring only |
| `platform/src/mogo_platform/contracts/__init__.py` | 1,321 | 28 | Package marker — docstring only |

Both contain exactly one statement (their docstring), AST-verified: no import, no re-export, no registration, no executable statement, no side effect.

## 6. Files Moved or Renamed

All seven were untracked, so these are filesystem moves of never-committed content.

| From | To | Bytes | Lines | SHA-256 | Edited? |
|---|---|---:|---:|---|---|
| `platform/contracts/platform_ids.py` | `.../contracts/ids.py` | 24,367 | 596 | `4e9c8467…` | yes — relative import, `math`, `as_plain` routing, `require_json_shaped` |
| `platform_errors.py` | `.../errors.py` | 8,885 | 218 | `68a3506e…` | one docstring line, after byte-preserving move proven |
| `platform_vocabulary.py` | `.../vocabulary.py` | 7,512 | 183 | `cd6e058f…` | **no — byte-identical to pre-move** |
| `platform_command.py` | `.../command.py` | 11,616 | 283 | `ab3265cd…` | yes — relative imports, two shape call sites |
| `platform_event.py` | `.../event.py` | 9,492 | 243 | `f95088b4…` | yes — relative imports, one shape call site |
| `platform_task_states.py` | `.../task_states.py` | 9,836 | 251 | `aaa78f98…` | yes — relative import |
| `platform_boundaries.py` | `.../boundaries.py` | 8,978 | 223 | `a9017193…` | yes — `DECLARATION_MODULE_BASENAME` |

**Byte-preserving proof, recorded at the moment of the move:**

```
MATCH  platform_errors.py     -> errors.py      258710f0f8af880c01ffe8a91308ebf4c74976756c43a3243100b80dbc07b151
MATCH  platform_vocabulary.py -> vocabulary.py  cd6e058f9e4f0513cba12ce7c6153ca1da097cc2138460db081e72ec0e575959
```

`vocabulary.py` still carries that hash in the final manifest — the migration was lossless end to end.

## 7. Files Deleted

```
platform/contracts/platform_ids.py
platform/contracts/platform_errors.py
platform/contracts/platform_vocabulary.py
platform/contracts/platform_command.py
platform/contracts/platform_event.py
platform/contracts/platform_task_states.py
platform/contracts/platform_boundaries.py
platform/contracts/                        (directory)
```

All untracked; nothing leaves git history because nothing entered it. `importlib.util.find_spec` returns `None` for all seven names — the generic top-level namespace is free.

## 8. Files Modified

| Path | Change |
|---|---|
| `platform/README.md` | Rewritten: the **narrow** root-only rule, the four-configuration evidence table, the src layout, the import convention, the contract-guarantee table, and a historical note recording why the broad rule was wrong so it is not re-broadened |
| `tests/platform/test_platform_identifiers.py` | `sys.path` → `platform/src`; imports; `ALL_PLATFORM_MODULES` dotted names; **added `TestJsonShapeValidator`** |
| `tests/platform/test_platform_envelopes.py` | same path/import edits; `math` import; **added `TestEnvelopeSerializability` and `TestIdempotentValidation`**; strengthened the payload test after mutation 17 |
| `tests/platform/test_platform_task_states.py` | path/import edits; `__module__` → `mogo_platform.contracts.task_states` |
| `tests/platform/test_platform_boundaries.py` | path/import edits; `DECLARATION_MODULE`; relative-import-aware scanner; **replaced the broad `__init__.py` rule with nine narrow guards** |

**`tests/run_platform_tests.sh` was not modified.** It invokes suites by dotted test-module name, none of which changed. Its hash is unchanged: `eb9973583e3401e6972d2cff0f3c4bc929b08a4f0ad806cd6002dd57e9072a07`.

## 9. JSON-Shape Validation

One pure validator in `ids.py`, three call sites.

```python
require_json_shaped(value, field="$")
```

**Accepts, exactly the JSON data model:** `None`, `bool`, `int`, finite `float`, `str`, mappings with string keys, `list`, `tuple`. Read-only mappings (`MappingProxyType`) and tuples are accepted so a validated envelope can be revalidated.

**Rejects, naming the precise JSON path:**

| Rejected | Example message |
|---|---|
| non-JSON types | `$event.f is of type set, which has no JSON representation` |
| non-finite floats | `$event.f is the non-finite float nan; JSON has no representation for NaN or Infinity` |
| non-string keys | `$event.f has the non-string key 1 of type int; JSON object keys must be strings and are never coerced` |
| nested cases | `$event.futureField.a[0].b is of type object, …` |

**Call sites and ordering:** after `require_mapping`, required-field presence and the version check — so an unsupported major still raises `UnsupportedContractVersionError` distinctly — and **before** per-field validation, prohibited-reference scanning, hashing and freezing.

```python
ids.require_json_shaped(normalized, "$command")     # command envelope
if payload is not None:
    ids.require_json_shaped(payload, "$payload")    # command payload argument
ids.require_json_shaped(normalized, "$event")       # event envelope (covers payload)
```

**Properties held:** returns the original object unchanged; mutates nothing; recurses through mappings, lists and tuples **only** — arbitrary object attributes are never traversed; performs no I/O and no serialization; standard library only.

## 10. Idempotent Validation

`canonical_json_bytes` now routes its input through `as_plain()` before `json.dumps`. `as_plain` converts `MappingProxyType` → `dict` and `tuple` → `list`, which changes no JSON output — so **no digest moves** — while making an already-frozen envelope hashable.

Verified:

```
event    revalidation OK | plain identical: True | payloadHash preserved: True
command  revalidation OK | plain identical: True | payloadHash preserved: True
```

Eight tests cover it: revalidation succeeds for both envelope types; the plain representation is identical across one, two and three passes; `payloadHash` is preserved and still equals the hash of the payload; unknown fields survive; the result remains deeply immutable; the original is not mutated; and the revalidated envelope is still strict-JSON serializable.

## 11. Package and Import Safety

| Property | Verified |
|---|---|
| `platform/__init__.py` absent | ✅ `os.path.exists` → `False` |
| stdlib `platform` functional | ✅ `platform.system()` → `Darwin`, `python_version()` → `3.14.6` |
| stdlib `platform` resolves outside the repository | ✅ `/usr/local/Cellar/python@3.14/…/platform.py` |
| `mogo_platform` imports normally | ✅ under `-W error` |
| Package-relative imports work | ✅ `command.ids is ids` → `True` |
| Exactly four modules use relative imports | ✅ `{ids.py, command.py, event.py, task_states.py}` — asserted as a set, not a threshold |
| Package markers docstring-only | ✅ AST: exactly one `Expr(Constant str)`, zero imports, zero calls |
| No retired flat module importable | ✅ all seven `find_spec` → `None` |
| `platform/contracts/` gone | ✅ |
| No suite inserts `platform/contracts` into `sys.path` | ✅ (the checking suite is the one named exemption, and it also asserts the directory does not exist) |
| Every suite adds only `platform/src` | ✅ |

## 12. Contract Behavior Preserved

No approved contract expectation changed. Every independently transcribed literal is unchanged and still asserted both directions plus an exact count:

| Contract | Count | Changed? |
|---|---:|---|
| Task states / terminal / non-terminal | 13 / 4 / 9 | no |
| Legal transitions with authority | 25 | no |
| Command types (Catalog §J) | 17 | no |
| Event types (Catalog §J) | 34 | no |
| Licensing statuses with 4 flags (Catalog §M) | 12 | no — `UNKNOWN` still identical to `PROHIBITED` |
| Error classes with 3 flags (Catalog §K) | 12 | no — `policy_blocked` still never retryable |
| Idempotency compositions (Catalog §I) | 10 | no |
| Composite prefixes (Catalog §H) | 7 | no |
| Capability lifecycle states (Catalog §O) | 7 | no |
| Prohibited write paths (Spec §7) | 6 | no |
| Prohibited scientific symbols (Catalog §H) | 4 | no |
| Envelope field lists (Catalog §A / §B) | 13+5 / 14+5 | no |

**No identifier digest changed.** `content_hash_of({})` still equals `44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a`. **No protected boundary was relaxed** — the boundary suite grew from 34 to 42 tests.

## 13. Tests Added and Modified

| Suite | Before | After | Δ |
|---|---:|---:|---:|
| `test_platform_identifiers.py` | 73 | 82 | +9 (`TestJsonShapeValidator`) |
| `test_platform_envelopes.py` | 75 | 108 | +33 (serializability 24, idempotency 8, ordering 1) |
| `test_platform_task_states.py` | 36 | 36 | 0 |
| `test_platform_boundaries.py` | 34 | 42 | +8 layout guards, −1 removed broad rule, +1 relative-import guard |
| **Total** | **218** | **268** | **+50** |

**Removed (1):** `test_no_init_py_anywhere_under_platform` — enforced a rule that was wrong.

**Added layout guards (9):** `test_no_init_py_at_platform_root`, `test_package_markers_exist`, `test_package_markers_are_docstring_only`, `test_no_retired_flat_module_is_importable`, `test_the_old_flat_contracts_directory_is_gone`, `test_no_test_inserts_platform_contracts_into_sys_path`, `test_every_suite_adds_only_the_src_directory`, `test_contract_modules_use_package_relative_sibling_imports`, `test_no_module_imports_a_retired_flat_module`. `test_platform_modules_are_importable_by_bare_name` became `test_platform_modules_are_package_qualified`.

**No test was weakened.** The only removal replaced an incorrect rule with a stricter set, and the only assertion change made a test stricter after a mutation exposed it.

## 14. Mutation Verification

19 mutations, sandbox outside the repository (`git archive HEAD` plus the Step 1 files), bytecode purged before every run.

| # | Mutation | Detected | Caught by |
|---|---|:---:|---|
| 1 | task state name | ✅ | 13 tests |
| 2 | terminal classification | ✅ | 9 tests |
| 3 | legal transition removed | ✅ | 6 tests |
| 4 | transition authority | ✅ | 2 tests |
| 5 | command vocabulary addition | ✅ | 2 tests |
| 6 | event vocabulary spelling drift | ✅ | 1 test |
| 7 | UNKNOWN licensing permissions | ✅ | 3 tests |
| 8 | idempotency composition | ✅ | 3 tests |
| 9 | payload-hash validation disabled | ✅ | 2 tests |
| 10 | prohibited-reference detection disabled | ✅ | 11 tests |
| 11 | root `platform/__init__.py` created | ✅ | `test_no_init_py_at_platform_root`, `test_stdlib_platform_module_is_importable_and_functional` |
| 12 | `require_json_shaped` disabled | ✅ | 21 tests |
| 13 | NaN permitted | ✅ | 5 tests |
| 14 | non-string key permitted | ✅ | 6 tests |
| 15 | idempotent plain conversion bypassed | ✅ | 8 tests |
| 16 | event envelope shape check unwired | ✅ | 16 tests |
| 17 | command payload shape check unwired | ✅ *(after fix)* | `test_command_payload_argument_receives_the_same_validation`, `test_command_payload_shape_is_checked_before_hashing` |
| 18 | executable code in a nested package marker | ✅ | `test_package_markers_are_docstring_only` |
| 19 | retired flat `platform_ids` restored | ✅ | `test_no_retired_flat_module_is_importable` |

**19/19 detected, 19/19 reverted.** Each reversion verified by restoring from an in-memory snapshot and re-running to green.

**Mutation 17's first run was UNDETECTED — recorded honestly.** Unwiring the command-payload shape check failed nothing, because canonical hashing rejects `object()` and `NaN` anyway, and a coerced `{1:"a"}` key then fails the hash comparison. The test asserted only the exception class. I strengthened it to assert the `$payload.x` path — producible only by the shape validator — and added an ordering test. The mutation is now caught twice.

**No leak:** `diff -r` between the repository and the fully-reverted sandbox reported **IDENTICAL** for `platform/` and `tests/platform/`. Sandbox and harness destroyed; scratchpad empty.

## 15. Validation Commands and Exact Results

| # | Check | Result |
|---|---|---|
| 1 | `python3 -m compileall -q platform tests/platform` | **COMPILE OK** |
| 2 | `python3 -W error` import of all 7 modules + collision guard | **IMPORT OK — stdlib platform: Darwin 3.14.6**, resolved to `/usr/local/Cellar/python@3.14/…/platform.py` |
| 3 | `python3 -m unittest` × 4 suites | **Ran 268 tests — OK** |
| 4 | `bash tests/run_platform_tests.sh` | **4 suites, 268 tests, 0 failures, 0 errors, 0 skipped** (82 + 108 + 36 + 42) |
| 5 | `bash tests/run_all.sh` | **17 suites, 0 execution errors, 947 fixtures, 947 passed, 0 failed** |
| 6 | 8 pre-existing Python suites | **Ran 451 tests in 279.9s — 6 failures** (identical six) |
| 7 | `python3 regression-baseline-tools.py` | **No drift: 63 protected functions, 4 protected constants byte-identical** |
| 8 | Campaign C1 manifest | **33 rows, 33 verified, 0 missing, 0 mismatched, 0 unlisted** |
| 9 | AST write-capable calls in `platform/**` | **0** |
| 10 | AST banned network imports | **0** |
| 11 | AST subprocess / process-execution calls | **0** |
| 12 | Scientific module imports | **0** — roots: `['.', 'datetime', 'hashlib', 'json', 'math', 're', 'types', 'uuid']` |
| 13 | Prohibited literals outside the declaration module | **0** |
| 14 | stdlib `platform` import | **Darwin** |
| 15 | `mogo_platform` package import | **OK** — `mogo_platform.contracts.ids` |
| 16 | `platform/__init__.py` exists | **False** |
| 17 | Package markers docstring-only | **True** |
| 18 | Retired flat modules importable | **none** |
| 19 | Third-party dependencies (`sys.stdlib_module_names`) | **0** |
| 20 | Strict JSON serialization of every validated envelope | **OK** — `allow_nan=False`, reparse equal |
| 21 | Idempotent command validation | **OK** — plain identical, hash preserved |
| 22 | Idempotent event validation | **OK** — plain identical, hash preserved |
| 23 | Mutation verification | **19/19 detected, 19/19 reverted** |
| 24 | Git diff and status | 23 untracked (15 commit + 8 excluded); **tracked modified 0; staged 0; tags 0** |
| 25 | Protected-path status | **empty** |

**Exact counts:** tests 268 · pass 268 · failure 0 · error 0 · skip 0 · duration 0.29 s · JS suites 17 / 947 fixtures / 947 pass / 0 fail · Python suites 451 tests / 6 pre-existing failures · C1 verified 33 / missing 0 / mismatch 0 / unlisted 0 · protected functions 63 · constants 4 · drift 0 · commit files 15 · modified tracked 0 · staged 0.

**No formatter, linter or type checker exists in this repository and the correction introduces none.** Checks 1 and 2 are the stdlib substitutes.

## 16. Existing Test-Suite Results

**Canonical gate — unaffected:** 17 suites, 947 fixtures, 947 passed, 0 failed, 0 execution errors, zero drift. `tests/run_all.sh` byte-identical.

**Python suites:** 451 tests, 6 failures — the same six, unchanged in identity and count.

## 17. Six Pre-Existing Python Failures

| Test | Status |
|---|---|
| `test_graph…test_expected_node_and_edge_counts` | unchanged |
| `test_evidence…test_production_evidence_tree_is_still_genuinely_empty` | unchanged |
| `test_phase1b…test_production_graph_unchanged_without_real_corpus` | unchanged |
| `test_phase7a…test_production_graph_unchanged_without_real_knowledge_library` | unchanged |
| `test_knowledge_engineering…test_delta_reports_the_unclosed_risk_gap` | unchanged |
| `test_knowledge_engineering…test_all_195_claims_are_inventoried` | unchanged |

**Identity: identical. Count: 6, unchanged. Not increased. Not decreased through unauthorized repair.** Proven pre-existing at HEAD with no `platform/` present (451 tests / 6 failures / same names). Full analysis remains in the correction plan's Appendix A. **A.6 still needs owner judgement and is not a test-hygiene item.**

## 18. Campaign C1 Integrity

```
rows=33 verified=33 missing=0 mismatched=0 unlisted=0
C1 INTEGRITY: UNCHANGED
```

`git status` on `evidence/`, `docs/campaigns/`, the pre-registrations and the verified-replay record: **empty**.

## 19. Protected-Function Drift

```
Known-good hash match: True
No drift: all 63 protected functions and 4 protected constants are byte-identical
to the committed baseline.
```

Run twice — standalone and as the final decisive stage of `tests/run_all.sh`. `regression-baseline.json` was not updated.

## 20. Dependency Classification

**Third-party dependencies: 0.**

The regenerated source review classifies against **`sys.stdlib_module_names`**. Import roots across all 11 Python files: `.` (package-relative), `ast`, `datetime`, `hashlib`, `importlib`, `json`, `math`, `os`, `platform`, `re`, `sys`, `types`, `unittest`, `uuid`, `mogo_platform`.

- **`platform` is Python standard library** — `'platform' in sys.stdlib_module_names` → `True`. It appears because `test_platform_boundaries.py` imports it deliberately, to prove the stdlib module is still functional. The previous generation flagged that guard as a dependency violation.
- **`mogo_platform` is project code.**
- **A hand-maintained allowlist is never used again**, because it cannot distinguish "not standard library" from "author forgot it".

## 21. Git Diff and Working-Tree Status

```
$ git rev-parse HEAD          bd6ff7c8ccebe31431c4d58c345894d7effdb738
$ git diff --name-status HEAD (empty)
$ git diff --cached --name-only (empty)
$ git tag --points-at HEAD    (empty)
$ git status --porcelain -- <10 protected paths>   (empty)
```

23 untracked entries: the 15 commit files, plus 4 MOGO-010 report documents and 4 pre-existing legacy documents, all excluded from the commit.

## 22. Deferred Behaviors

Unchanged from the pre-correction report; each declared in its module docstring and none simulated: opaque-identifier uniqueness · command rejection events · event persistence, ordering, `sequence` monotonicity, chain replay · capability registration · licensing evaluation · task-state application · late-transition logging · acquisition policy decision · payload semantics · retry, backoff, dead-letter, review routing · filesystem boundary enforcement · package manifest.

## 23. Deviations, Failures, or Ambiguities

**Mutation 17 escaped on the first run** (§14) — test weakness, fixed by strengthening the assertion.

**Four defects in my own correction, found by my own tests, fixed at source:** a stale `CONTRACTS_DIR` reference in the manifest test; an obsolete bare-name assertion; a relative-import threshold that was arbitrary (`>= 5`) where the correct assertion is an exact set of four; and a self-reference false positive where the new `platform/contracts` scan flagged the very file that declares the string. The last was resolved by exempting exactly one named file — the same declaration-module principle Correction A established — and pairing it with an assertion that the directory does not exist.

**One anchor mismatch during migration** — a docstring anchor did not match. The edit function is atomic per file, so `ids.py` was left untouched and its hash verified unchanged before retrying with the correct anchor.

**Contract ambiguity carried forward, unresolved:** Catalog §A types `targetCapability` as "string" without fixing its form; two forms are attested. Step 1 accepts exactly those two and invents no third. Governance should fix a canonical form before the Capability Registry step.

**Deviation from Inventory §10's layout sketch** — analysed in §2; no approved decision is contradicted.

## 24. Architecture Drift Check

| Requirement | Confirmation |
|---|---|
| Files in an approved bounded context | ✅ all under the approved top-level `platform/` |
| No isolated agent architecture | ✅ no agent, daemon, `__main__`, CLI or entry point |
| No worker-to-worker calls | ✅ no worker exists |
| No connector bypass | ✅ no connector, no gate; `UNKNOWN` still carries `PROHIBITED`'s flags |
| No external workflow engine | ✅ zero dependencies |
| No external message broker | ✅ zero dependencies |
| Operational events distinct from scientific evidence | ✅ namespace, schema ids, disjoint names, prohibited refs — all test-enforced |
| No acquired material can become canonical knowledge | ✅ nothing can acquire |
| No unauthorized scientific writes | ✅ zero write calls of any kind, AST-verified |
| Consistent with ADR-012 | ✅ sequence item 1 only |
| Consistent with the Constitution | ✅ §3, §4.4/4.5, §5.2, §6.1, §6.8, §11, §12, §16 |

## 25. Zero-Known-Defect Acceptance Checklist

| Confirmation | Status |
|---|---|
| No existing tracked file was modified | ✅ |
| No protected file was modified | ✅ |
| Nothing staged | ✅ |
| Nothing committed | ✅ |
| Nothing tagged | ✅ |
| Nothing pushed | ✅ |
| Standard-library `platform` remains functional | ✅ `Darwin` / `3.14.6` |
| `platform/__init__.py` does not exist | ✅ |
| `mogo_platform` imports normally | ✅ |
| No old flat contract module remains | ✅ all 7 `find_spec` → `None` |
| Validated envelopes are strict JSON | ✅ `allow_nan=False`, reparse equal |
| Command validation is idempotent | ✅ |
| Event validation is idempotent | ✅ |
| All temporary mutations reverted | ✅ 19/19; `diff -r` IDENTICAL; sandbox destroyed |
| Final tests passed after mutation reversion | ✅ 268/268 |
| Campaign C1 unchanged | ✅ 33/33 |
| No scientific write path exists | ✅ |
| No executable automation path exists | ✅ |
| No Step 2 work began | ✅ |
| **No known Step 1 defect remains** | ✅ — with the pre-existing, non-Step-1 condition in §17 disclosed |

## 26. Proposed Commit Boundary

**15 files, one bounded commit:**

```
platform/README.md
platform/src/mogo_platform/__init__.py
platform/src/mogo_platform/contracts/__init__.py
platform/src/mogo_platform/contracts/ids.py
platform/src/mogo_platform/contracts/errors.py
platform/src/mogo_platform/contracts/vocabulary.py
platform/src/mogo_platform/contracts/command.py
platform/src/mogo_platform/contracts/event.py
platform/src/mogo_platform/contracts/task_states.py
platform/src/mogo_platform/contracts/boundaries.py
tests/platform/test_platform_identifiers.py
tests/platform/test_platform_envelopes.py
tests/platform/test_platform_task_states.py
tests/platform/test_platform_boundaries.py
tests/run_platform_tests.sh
```

**Excluded:** the four MOGO-010 report documents, the four legacy 2026-08-04 documents, `tests/run_all.sh`, `docs/TESTING.md`, `docs/KNOWN_ISSUES.md`, `regression-baseline.json`, `.gitignore`, and any manifest or lock file.

**Unresolved before any push:** local `main` has **no upstream** and `origin/main` is unrelated history (`abfc763`). `git push origin main` would target the wrong branch. The authoritative branch is `origin/mogo-main`.

## 27. Final Recommendation

All six approved corrections are implemented, validated and mutation-tested. Every defect the source review found — and the four additional ones probing revealed — is closed. The layout migration was proven byte-preserving before any edit, and `vocabulary.py` still carries its pre-move hash as standing evidence. The one mutation that escaped exposed a weak assertion, which was made stricter rather than removed.

The corrected implementation is internally consistent, deterministic, auditable, fail-closed, reversible, and consistent with the approved MOGO-009 architecture. No higher-authority document required amendment, no tracked file changed, and no unrelated defect was repaired.

Two items remain for you, neither blocking this commit: the six pre-existing Python failures (§17, with A.6 needing owner judgement rather than test hygiene), and the `targetCapability` form ambiguity before the Capability Registry step.

Nothing was staged, committed, tagged or pushed. No Step 2 work began.

**READY FOR FINAL STEP 1 COMMIT REVIEW — ZERO KNOWN DEFECTS**

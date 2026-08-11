# MOGO-010 STEP 1 — CORRECTION PLAN

**Milestone:** MOGO-010 Phase II, Step 1 — pre-commit correction · **Status:** plan only, nothing implemented
**Prepared:** 2026-08-07 · **Branch:** `main` · **HEAD:** `bd6ff7c8ccebe31431c4d58c345894d7effdb738`
**Governing document:** [`AUTOMATION_PLATFORM_CONSTITUTION.md`](docs/governance/AUTOMATION_PLATFORM_CONSTITUTION.md) v1.0 — senior to this plan
**Inputs:** [ADR-012](docs/adr/ADR-012-automation-platform-architecture.md) · [Architecture](docs/architecture/MOGO-009-AUTOMATION-PLATFORM-ARCHITECTURE.md) · [Contract Catalog](docs/architecture/MOGO-009-CONTRACT-CATALOG.md) · [Inventory](docs/reports/MOGO-009-AUTOMATION-PLATFORM-ARCHITECTURE-INVENTORY.md) · [Source Review](MOGO-010-STEP-1-SOURCE-REVIEW.md)

> **No source code was modified to produce this plan. Nothing was staged, committed, tagged or pushed.**
> Every behavioural claim below was verified by executing the current code, not inferred from reading it.

---

## 1. Executive Summary

The independent source review, plus the diagnostic probes run while preparing this plan, identified **six issues**. Two were named by the review; four were found by probing the code the review pointed at. None is a scientific-validity issue, because Step 1 contains no write path, no persistence, no replay and no evidence interaction — a property re-verified in §4.

| # | Issue | Severity | Affects scientific validity? | Affects maintainability? |
|---|---|---|---|---|
| **I-1** | Import and package architecture: flat top-level module names (`platform_ids`) reached by a per-caller `sys.path` insert | **High** | **No** | **Yes — blocking.** Every future runtime, worker, connector and persistence module would inherit a flat global namespace |
| **I-2** | Validated envelopes are not guaranteed JSON-shaped: `object()`, `set`, `bytes` and nested unsupported values survive validation and freezing | **High** | **No** (nothing persists in Step 1) | **Yes** — breaks the declared additive-field, round-trip and durable-record contract properties |
| **I-3** | `NaN` / `±Infinity` in an unknown envelope field survive validation and serialize to bare `NaN` / `Infinity` — **not valid JSON** under RFC 8259 | **High** | **No** (today) | **Yes** — silent production of a malformed document is worse than a clean failure |
| **I-4** | Non-string mapping keys are silently coerced (`{1:"a"}` → `{"1":"a"}`); mixed-type keys crash only at serialization time | **Medium-High** | **No** | **Yes** — round-trip returns a *different* object; the crash is remote from its cause |
| **I-5** | Validation is not idempotent: `validate_event(validate_event(x))` raises *"Object of type mappingproxy is not JSON serializable"* | **Medium** | **No** | **Yes** — a validated envelope cannot be re-validated, which any pipeline stage would eventually attempt |
| **I-6** | The source-review dependency classifier misreported stdlib `platform` as an unexpected third-party dependency (`Third-party dependencies: 1`) | **Low** | **No** | **Reporting only** — no code defect; the correct count is 0 |

**Two of the six (I-1, I-6) were named by the review. Four (I-2 through I-5) were found by probing.** I-2 was named in outline; I-3, I-4 and I-5 are distinct failure modes the review did not identify, and I-3 is the most dangerous of the set because it fails silently rather than loudly.

**Scientific-validity assessment, stated once and precisely.** No issue in this table can affect scientific validity, and the reason is structural rather than fortunate: `platform/**` contains **zero write calls of any kind** (AST-verified — no `open()`, no `os.remove`, no `shutil`, no `Path.write_*`), **zero network-capable imports**, and **zero imports from `scripts/trader_intelligence/`**. Campaign C1 is verified 33/33 against its manifest and the protected-function drift gate reports zero drift across 63 functions and 4 constants. Nothing in Step 1 can reach an evidence record, a pre-registration, an adjudication artefact or a scientific registry, so no defect in it can corrupt one. These are contract-layer defects with maintainability and future-durability consequences only.

**Recommendation (detail in §8): proceed with implementation now.** All six corrections are bounded, reversible, and confined to untracked files. One sub-decision (§3.5) remains genuinely open and is flagged rather than assumed.

---

## 2. Root Cause Analysis

### 2.0 A correction to the framing: these did not survive previous milestones

The plan template asks why each issue "survived previous milestones." For I-1 through I-5 the honest answer is that **they did not survive anything — they were introduced in MOGO-010 Step 1, which is the first implementation milestone in the programme.** MOGO-001 through MOGO-009 produced governance, science and architecture; the MOGO-009 Step 1 inventory recorded that `worker`, `retry`, `backoff`, `checkpoint`, `resume`, `concurren`, `correlation` and `causation` each occurred in **zero** files across `scripts/`. There was no platform code to carry a defect forward.

The useful question is the adjacent one: **why did the approved architecture and the approved Step 1 plan not prevent them?** That question is answered per-issue below, and the answer differs meaningfully between I-1 and I-2.

### 2.1 — I-1 Import and package architecture

| | |
|---|---|
| **Why it exists** | A real collision was solved with an over-general rule. `platform/` at the repository root shares its name with the stdlib `platform` module. I established empirically that `platform/__init__.py` breaks stdlib `platform` repository-wide — Python 3.14 emits *"consider renaming … since it has the same name as the standard library module named 'platform' and prevents importing that standard library module."* I then generalised "no `__init__.py` at the root" into "no `__init__.py` **anywhere** under `platform/`", which does not follow. Only the root file causes shadowing. |
| **Where it exists** | The `sys.path` insert on `platform/contracts` in all four test suites; the bare-name imports (`import platform_errors as errors`) in five of the seven contract modules; and `test_no_init_py_anywhere_under_platform`, which encoded the over-generalisation as an enforced rule. |
| **Files involved** | `platform/contracts/platform_ids.py`, `platform_command.py`, `platform_event.py`, `platform_task_states.py` (bare-name imports); all four `tests/platform/test_*.py` (path insert); `tests/platform/test_platform_boundaries.py` (the defective rule test); `platform/README.md` (documents the wrong rule prominently) |
| **Why architecture did not prevent it** | The approved MOGO-009 documents specify **contracts, not packaging**. Architecture §7 and §25 constrain `platform/**` as a *path glob*; Inventory §10 sketches a *directory* layout ("Recommended platform location"). Neither says anything about Python import namespaces, package markers, or module naming — those are implementation concerns that first became real in Step 1. The gap is genuine and not a failure of the architecture. |
| **Why the Step 1 plan did not prevent it** | The plan surfaced the collision as its headline finding and proposed the bare-name convention as the resolution. It was reviewed and approved on that basis. The plan was right about the constraint and wrong about the least-cost way to satisfy it: it never considered that a *nested, differently-named* package is reached through a different `sys.path` entry and therefore cannot collide. |

**The deeper cause:** the collision was framed as "how do we avoid `__init__.py`?" instead of "how do we get a unique import namespace?" The first framing admits only degraded answers.

### 2.2 — I-2, I-3, I-4 Envelope serializability

| | |
|---|---|
| **Why it exists** | A **scope error in what gets validated**, compounded by a **default-argument asymmetry in the standard library**. Both validators check *named* fields against their contracts and copy *unknown* fields through untouched. Only `payload` ever reached a serializability-checking path (`content_hash_of` → `canonical_json_bytes`, which sets `allow_nan=False`). The envelope as a whole was never checked. For commands the hole is larger: `payload` is optional, so with no payload supplied **nothing** in the command was serializability-checked. |
| **Why I-3 is distinct and worse** | `canonical_json_bytes` sets `allow_nan=False`; a later consumer calling plain `json.dumps` gets `allow_nan=True` by default and emits bare `NaN`/`Infinity`. The envelope and its own hashing path therefore **disagree about what is representable**. The result is not a crash but a silently malformed document — the most damaging variant for an append-only log whose entire value is replayability. |
| **Why I-4 is distinct** | `json.dumps` silently stringifies non-string scalar keys, so an envelope can round-trip into a *different* object; and `sort_keys=True` over mixed-type keys raises `TypeError: '<' not supported between instances of 'str' and 'int'` at serialization time, far from the cause. |
| **Where it exists** | `validate_command()` and `validate_event()` — specifically the absence of any whole-envelope check between the version check and the per-field validation. |
| **Files involved** | `platform/contracts/platform_command.py`, `platform/contracts/platform_event.py`, and `platform/contracts/platform_ids.py` (which owns canonicalization and is where the missing validator belongs) |
| **Why `freeze()` did not catch it** | Correctly, and by design. `freeze()` converts mappings and sequences and passes everything else through unchanged. Freezing is not validation's job. The gap is that no other component did the job either. |
| **Why architecture did not prevent it** | Contract Catalog §B states *"consumers must ignore unknown fields"* and §A/§B define `payloadHash` as being over the canonical payload. Neither says unknown fields must be **admissible**. The Catalog specifies preservation, not a type domain. |
| **Why the Step 1 plan did not prevent it** | The approved plan §9.6 reasoned carefully about the *wrong half* of the property. It states: *"Unknown fields are therefore retained verbatim and included in the hash; they are ignored only for semantic purposes."* That decision is correct and is preserved by this correction. But it specified **preservation** and never **admissibility** — the prerequisite that an unknown field be JSON-shaped in the first place. |
| **Why the 218 tests did not catch it** | Same asymmetry, carried into the tests. `test_unknown_fields_are_retained_not_dropped`, `test_unknown_fields_are_included_in_the_payload_hash` and `test_unknown_fields_do_not_affect_semantic_validation` all pass **JSON-shaped** unknown values. Every one of them tests that a *valid* unknown field is preserved. Not one tests that an *invalid* unknown field is rejected. The property "additive fields are preserved" was verified; the property "additive fields are admissible" was assumed. |

### 2.3 — I-5 Non-idempotent validation

| | |
|---|---|
| **Why it exists** | `canonical_json_bytes` calls `json.dumps` directly on the value it is given. A validated envelope is deeply read-only — mappings are `MappingProxyType`, arrays are tuples — and `json.dumps` cannot serialize `MappingProxyType`. So re-validating a validated envelope fails inside hashing. |
| **Where it exists** | `platform_ids.canonical_json_bytes`, reached from `validate_event` → `event_payload_hash`. |
| **Files involved** | `platform/contracts/platform_ids.py` (the fix), `platform_event.py` (the observed failure path) |
| **Why nothing caught it** | No test re-validates an already-validated envelope. The round-trip tests serialize with `as_plain()` first, which is the correct usage — so the tests exercised the supported path and never the natural one a future pipeline stage would take. |

### 2.4 — I-6 Source-review dependency classifier

| | |
|---|---|
| **Why it exists** | The classifier compared root module names against a **hand-maintained set literal** — `STDLIB = {"hashlib", "json", "re", "uuid", "datetime", "types", "math", "os", "sys", "unittest", "ast", "shutil", "subprocess"}` — and anything absent fell through to `**UNEXPECTED**`. `platform` was omitted from that list. |
| **Where it exists** | The one-off generator that produced `MOGO-010-STEP-1-SOURCE-REVIEW.md`, at the lines that emitted `| `platform` | **UNEXPECTED** |` and `**Third-party dependencies: 1.**`. The generator has since been deleted from the scratchpad; the document retains the wrong output. |
| **Files involved** | `MOGO-010-STEP-1-SOURCE-REVIEW.md` (report content only — **not modified by this correction**, per instruction). No source file is affected. |
| **Why it survived** | It was written and run once, in a single pass, with no test. A hand-maintained allowlist cannot distinguish "not standard library" from "the author forgot it," and silently reports the second as the first. |
| **The irony worth recording** | The single import it misclassified — `import platform as stdlib_platform` in `test_platform_boundaries.py` — exists *precisely to prove that stdlib `platform` is not shadowed*. The classifier flagged the guard against I-1 as a dependency violation. |

---

## 3. Exact Code Changes

**No code is written in this document.** Each entry states the file, the function, the logic change, the expected behaviour, and backward compatibility.

### 3.1 — Package layout (corrects I-1)

**Target layout:**

```
platform/
  README.md
  src/                                  ← the ONE directory added to sys.path
    mogo_platform/
      __init__.py                       ← docstring only
      contracts/
        __init__.py                     ← docstring only
        ids.py  errors.py  vocabulary.py  command.py  event.py  task_states.py  boundaries.py
```

| File(s) | Function(s) | Exact logic to change | Expected behaviour after fix | Backward compatible? |
|---|---|---|---|---|
| `platform/src/mogo_platform/__init__.py` **(new)** | — | Docstring only. **No imports, no re-exports, no executable statement.** A re-export would create an import-time side effect and a second name for every symbol. | `import mogo_platform` succeeds with zero side effects | N/A — new |
| `platform/src/mogo_platform/contracts/__init__.py` **(new)** | — | Same: docstring only | `from mogo_platform.contracts import ids` succeeds | N/A — new |
| `ids.py` (from `platform_ids.py`) | module header | `import platform_errors as errors` → `from . import errors` | Relative import inside the package | **No** — module path changes. Acceptable: nothing outside Step 1 imports it, and nothing is committed |
| `command.py` (from `platform_command.py`) | module header | 4 bare imports → `from . import boundaries, errors, ids, vocabulary` | Same symbols, package-relative | **No** — same rationale |
| `event.py` (from `platform_event.py`) | module header | 4 bare imports → relative | Same | **No** |
| `task_states.py` (from `platform_task_states.py`) | module header | `import platform_errors as errors` → `from . import errors` | Same | **No** |
| `boundaries.py` (from `platform_boundaries.py`) | module constant | `DECLARATION_MODULE_BASENAME = "platform_boundaries.py"` → `"boundaries.py"` | The literal-scan exemption continues to name exactly one module | **No** |
| `errors.py`, `vocabulary.py` | — | **Move only.** Neither imports a sibling. `errors.py` has one docstring path reference to update | Byte-identical apart from the docstring line | **No** — path only |
| `platform/README.md` | — | Replace the "Never create an `__init__.py` anywhere under `platform/`" section with the **narrow** rule, the src layout, the import convention, and the empirical evidence table | Documents the rule that is actually load-bearing | N/A — documentation |
| all four `tests/platform/test_*.py` | module header | `sys.path` entry `platform/contracts` → `platform/src`; imports → `from mogo_platform.contracts import …` | Suites import through the unique namespace | **No** |
| `tests/platform/test_platform_identifiers.py` | `ALL_PLATFORM_MODULES` | Module name strings → `mogo_platform.contracts.*` | No-minting sweep still covers all seven modules | **No** |
| `tests/platform/test_platform_task_states.py` | `test_public_surface_is_exactly_the_declared_contract` | `__module__ == "platform_task_states"` → `"mogo_platform.contracts.task_states"` | Public surface still pinned to exactly 7 predicates | **No** |
| `tests/platform/test_platform_boundaries.py` | module constants | `CONTRACTS_DIR` → `platform/src`; `DECLARATION_MODULE` → `"boundaries.py"`; sibling prefix `platform_` → `mogo_platform` | AST and literal scans still cover every module under `platform/**` | **No** |
| `tests/run_platform_tests.sh` | — | **Unchanged.** It invokes suites by dotted test-module name; none changes | Identical output | Yes |

**Why the two nested `__init__.py` files cannot shadow stdlib `platform` — three independent reasons, each verified by execution:**

1. `platform/__init__.py` is never created, so `platform/` stays a PEP 420 namespace directory and the stdlib *regular module* wins. Verified: `import platform` → `/usr/local/Cellar/python@3.14/…/platform.py`; `platform.system()` → `Darwin`.
2. The `sys.path` entry is `platform/src`, which contains only `mogo_platform/`. Nothing named `platform` is importable through it.
3. `mogo_platform` is not a standard-library name — checked against `sys.stdlib_module_names`, not a hand-list: `'platform'` → `True`, `'mogo_platform'` → `False`, `'contracts'` → `False`.

Verified in the worst case, with the repository root **and** `platform/src` on `sys.path` simultaneously: absolute import works, relative import works, `platform.system()` → `Darwin`, `shadowed → False`, and `platform.contracts` remains unimportable. A control run re-adding `platform/__init__.py` immediately reproduced `AttributeError: module 'platform' has no attribute 'system'`, confirming the narrow rule is load-bearing and the broad one was not.

### 3.2 — Whole-envelope JSON-shape validation (corrects I-2, I-3, I-4)

| File | Function | Exact logic to change |
|---|---|---|
| `ids.py` | **new** `require_json_shaped(value, field="$")` | Depth-first proof that a value is JSON-shaped and canonically serializable. Raises `ContractValidationError` naming the JSON path of the first offending value. Returns the value unchanged; mutates nothing |
| `command.py` | `validate_command()` | Insert `ids.require_json_shaped(normalized, "$command")` immediately after the version check; and `ids.require_json_shaped(payload, "$payload")` when a payload is supplied |
| `event.py` | `validate_event()` | Insert `ids.require_json_shaped(normalized, "$event")` immediately after the version check |

**Accept:** `None`, `bool`, `int`, `str`, **finite** `float`, any mapping (duck-typed on `.keys()`, so `dict` and `MappingProxyType` both pass), any `list` / `tuple`.

**Reject, naming the JSON path and the offending type:**

| Rejected | Reason |
|---|---|
| `object()`, `set`, `bytes`, `complex`, any other type | not JSON-representable → corrects **I-2** |
| `float('nan')`, `float('inf')`, `float('-inf')` — tested with `math.isfinite` | not valid JSON → corrects **I-3** |
| any mapping key that is not exactly `str` (`bool` and `int` keys rejected even though `json.dumps` accepts them by coercion) | prevents silent coercion and the mixed-key `sort_keys` crash → corrects **I-4** |

**Ordering rationale.** After `require_mapping`, required-field presence and the version check — so an unsupported major still raises `UnsupportedContractVersionError` *distinctly* — and before per-field validation, the prohibited-reference scan and hashing. Placing it before hashing turns a generic serialization failure from deep inside `json` into a precise path-named contract error.

**Expected behaviour after the fix:** every envelope returned by `validate_command` or `validate_event` is guaranteed to serialize under `json.dumps(..., allow_nan=False)` and to reparse to an equal object. Unknown additive fields that are JSON-shaped are preserved byte-for-byte and continue to participate in the payload hash exactly as before.

**Backward compatibility:** **preserved for every valid envelope.** No digest changes, no field is dropped, no accepted value becomes rejected. The only envelopes whose behaviour changes are those that were already broken — they now fail at validation instead of at serialization, or instead of silently producing malformed JSON.

### 3.3 — Requirement traceability

| Requirement | Satisfied by |
|---|---|
| Validate the complete normalized envelope, not only the payload | single call on `normalized` in both validators |
| Reject non-JSON-compatible unknown fields | type allowlist, depth-first |
| Reject non-string mapping keys | exact `str` check, `bool` excluded |
| Reject NaN and ±Infinity anywhere in the envelope | `math.isfinite` on every float at every depth |
| Preserve valid unknown additive fields unchanged | validator is pure inspection |
| Preserve payload-hash semantics exactly | hashing untouched; no digest moves |
| No silent conversion of unsupported objects to strings | rejection, never coercion |
| No dropping of unknown fields | validator never removes; existing preservation tests still guard |
| No mutation of caller input | pure inspection; existing no-mutation tests still apply |
| Same deeply read-only representation returned | `freeze()` unchanged |

### 3.4 — Test-rule correction (corrects the enforced half of I-1)

| File | Function | Change |
|---|---|---|
| `tests/platform/test_platform_boundaries.py` | `test_no_init_py_anywhere_under_platform` | **Remove** — it enforces a rule that is wrong |
| same | **new** `test_no_init_py_at_platform_root` | Assert **only** that `platform/__init__.py` is absent, with a failure message explaining the collision |
| same | **new** `test_package_markers_exist_and_are_side_effect_free` | Assert both nested `__init__.py` files exist and contain no import statement and no executable statement (AST-checked) |
| same | `test_stdlib_platform_module_is_importable_and_functional` | **Retained unchanged.** This is the real guard, and it is what makes the narrow rule safe |

**No test is weakened.** The removed test enforced an incorrect rule; its replacements enforce the correct one plus a property the old rule made impossible to state.

### 3.5 — Open decision: idempotent validation (corrects I-5)

**This item was raised in the pre-commit correction plan and has not been answered. It is not assumed.**

| File | Function | Change |
|---|---|---|
| `ids.py` | `canonical_json_bytes()` | Route the value through `as_plain()` before `json.dumps`, so hashing accepts an already-frozen structure |

One line. Changes no digest for any value, because `as_plain` alters no JSON output — it only converts `MappingProxyType` → `dict` and `tuple` → `list`, both of which serialize identically.

**Recommendation: include it.** Without it, `require_json_shaped` must either reject frozen input (hostile to any caller re-validating a validated envelope) or accept input that hashing then refuses (incoherent). **If declined,** `require_json_shaped` will instead reject non-plain mappings, and I-5 remains open and documented rather than silently half-fixed.

---

## 4. Risk Assessment

Four risk dimensions per change. Three of the four are structurally zero for every change in this plan, and the reason is given rather than asserted.

### 4.1 — Why three risk dimensions are structurally zero

| Dimension | Why zero for every change below |
|---|---|
| **Replay determinism** | Step 1 contains no replay code, invokes no replay engine, and mints no `runId` or `datasetHash`. The replay engine lives in `index.html`, which no platform module references — enforced by a static test that rejects the literal. Replay is Architecture sequence item 12+, unimplemented |
| **Evidence integrity** | `platform/**` contains **zero write calls of any kind** — AST-verified: no `open()` (not even read-mode), no `os.remove/unlink/rename/replace`, no `shutil.rmtree`, no `Path.write_*`. Contexts 13 and 14 are unreferenced. Campaign C1 is verified 33/33 against its manifest and is git-ignored with committed hashes. A defect in a pure-function contract layer cannot reach a record it has no code path to |
| **Scientific validity** | No component in Step 1 can approve a rule, promote a hypothesis, alter a pre-registration, execute a replay, adjudicate, or write scientific evidence. The prohibited-reference detector rejects any envelope naming a §7 path or a §H not-reused symbol. Protected-function drift is zero across 63 functions and 4 constants |

### 4.2 — Per-change risk

| Change | Regression risk | Replay determinism | Evidence integrity | Scientific validity |
|---|---|---|---|---|
| **3.1 Package layout** — move 7 files, add 2 markers, rewrite imports | **Medium.** The largest mechanical surface in the plan: 7 moves and ~15 import edits. A missed reference produces an immediate `ImportError`, not a silent wrong answer — the failure mode is loud. Mitigated by hash-comparing the two unmodified files (`errors.py`, `vocabulary.py`) pre/post move, and by re-running all suites | **None** | **None** | **None** |
| **3.2 JSON-shape validation** — new validator, 3 call sites | **Low.** Purely additive rejection. No accepted value becomes rejected; no digest moves. The residual risk is over-rejection of something legitimate, bounded by the allowlist being exactly the JSON data model. The one judgement call — rejecting non-`str` keys that `json.dumps` would coerce — is the fail-closed reading and is explicitly required | **None** | **None** | **None** |
| **3.4 Test-rule correction** — remove 1 test, add 2 | **Low.** Narrows an over-broad rule to the load-bearing one and adds a guard the old rule prevented. The stdlib-shadowing guard is retained unchanged, so the property that actually matters keeps two independent enforcers | **None** | **None** | **None** |
| **3.5 Idempotent hashing** *(if approved)* | **Low.** `as_plain` on a plain structure returns an equal deep copy; JSON output is byte-identical, so every existing digest is preserved. Cost is one extra traversal per hash, irrelevant at Step 1 volumes | **None** | **None** | **None** |

### 4.3 — Risks specific to this correction

| Risk | Likelihood | Mitigation |
|---|---|---|
| Content lost during the 7-file move | Low | Every file's exact bytes and SHA-256 are recorded in `MOGO-010-STEP-1-SOURCE-REVIEW.md`. Post-move hashes of the two unmodified files must match their pre-move hashes **exactly**, and that comparison is a validation step, not an afterthought |
| A future contributor re-adds `platform/__init__.py` | Low | Two independent guards fail immediately — `test_no_init_py_at_platform_root` with an explanatory message, and `test_stdlib_platform_module_is_importable_and_functional` |
| The broad rule reappears out of caution | Medium | `platform/README.md` will state the narrow rule *and* why the broad one was wrong, including the empirical evidence table |
| `mogo_platform` collides with a future PyPI package | Very low | Not published, not installed, zero dependencies. Name availability should be verified before any future publication — noted, not acted on |
| Correction introduces a defect the 218 tests cannot see | Low | Mutation verification is re-run in full and extended from 11 to 13 mutations (adding: JSON-shape check disabled; root-`__init__` guard removed) |
| The six pre-existing Python failures are mistaken for regressions | Medium | They are proven pre-existing at HEAD with no `platform/` present, and are documented in Appendix A of the source review. They are **not repaired here**, per instruction. Post-correction runs must report the same six, unchanged |

---

## 5. Testing Plan

### 5.1 — Existing regression tests that protect the change

| Protection | Suite | What it would catch |
|---|---|---|
| 218 platform tests, all offline and deterministic | `tests/platform/` × 4 | Any behavioural change in identifiers, envelopes, task states or boundaries |
| Independently transcribed contract expectations — 13 states, 25 edges, 17 commands, 34 events, 12 licensing statuses, 12 error classes, 10 idempotency compositions, 6 prohibited paths, 4 prohibited symbols | all four suites | Any drift in an approved vocabulary or table introduced while moving files |
| AST boundary scans over `platform/**` | `test_platform_boundaries.py` | A write path, network import, subprocess, or pipeline import introduced by the move |
| Protected-function drift gate, 63 functions + 4 constants | `regression-baseline-tools.py` | Any change to `index.html` |
| Canonical gate, 17 JS suites / 947 fixtures | `tests/run_all.sh` | Any regression in the browser engine |
| 8 pre-existing Python suites, 451 tests | `tests/{trader_intelligence,knowledge_engineering,strategy_fidelity}/` | Any effect on the Phase I pipeline — expected result is the **same six pre-existing failures, unchanged** |

### 5.2 — New unit tests required

**Serializability — 14 tests**, covering all ten operator-specified cases:

| Test | Case |
|---|---|
| `test_command_rejects_unknown_field_containing_object` | `object()` in a command |
| `test_event_rejects_unknown_field_containing_object` | `object()` in an event |
| `test_rejects_unknown_field_containing_a_set` | `set` |
| `test_rejects_unknown_field_containing_bytes` | `bytes` |
| `test_rejects_unknown_field_containing_nan` | `NaN` |
| `test_rejects_unknown_field_containing_positive_infinity` | `+Inf` |
| `test_rejects_unknown_field_containing_negative_infinity` | `−Inf` |
| `test_rejects_nested_unknown_field_containing_unsupported_value` | nested unsupported |
| `test_rejects_mapping_with_non_string_key` | `{1: "a"}` |
| `test_rejects_mapping_with_bool_key` | the `bool`-is-an-`int` trap |
| `test_valid_nested_json_shaped_unknown_field_round_trips` | valid nested value preserved |
| `test_valid_unicode_unknown_field_round_trips` | valid Unicode preserved |
| `test_error_names_the_json_path_of_the_offending_value` | auditability of the failure |
| `test_command_payload_argument_is_also_shape_checked` | closes the command-payload hole |

**Validator unit coverage — `TestJsonShapeValidator`** in `test_platform_identifiers.py`: direct accept-list and reject-list coverage of `require_json_shaped`, plus:

- `test_every_validated_envelope_is_strict_json_serializable` — dumps with `allow_nan=False` and reparses. This is the property the whole fix exists to guarantee, asserted directly rather than inferred.
- `test_revalidation_of_a_validated_envelope_is_idempotent` — **only if §3.5 is approved.**

**Package-layout tests — 2 new, 1 removed** (detailed in §3.4).

### 5.3 — Integration tests required

Step 1 has no components to integrate — no orchestrator, worker, connector, event store or persistence exists. The nearest equivalents, both already present and both re-run:

- **Cross-module contract integration** — `TestEnvelopesRejectProhibitedTargets` exercises `command` + `event` + `boundaries` + `ids` together against all 10 prohibited targets and symbols.
- **Runner integration** — `bash tests/run_platform_tests.sh` exercises the four suites through the standalone runner exactly as an operator would.

A genuine integration test becomes possible at Architecture sequence item 11 (end-to-end vertical slice), which is not this step.

### 5.4 — Replay verification

**Not applicable, and deliberately so.** Step 1 implements no replay path, mints no `runId` / `datasetHash` / `configHash` / `paramsHash`, and never invokes the replay engine. Architecture §28 places replay preparation outside Step 1 and forbids the platform from executing replay or minting those identifiers at all.

**What is verified instead:** that no replay path was accidentally introduced. `test_platform_never_references_index_html` and the AST import scan both assert it, and the protected-function drift gate confirms the replay engine itself is byte-identical.

### 5.5 — Evidence verification

Run after implementation and again after mutation reversion:

1. **Campaign C1 manifest verification** — re-hash all 33 artefacts in the git-ignored `evidence/` tree against `CAMPAIGN_C1_EVIDENCE_MANIFEST.md`. Required: 33 verified, 0 missing, 0 mismatched, 0 unlisted.
2. **Protected-path git status** — `evidence/`, `docs/campaigns/`, `index.html`, `docs/trader-intelligence/governance/`, `docs/MOGO-003-VERIFIED-REPLAY-RECORD.md`, `tests/run_all.sh`, `regression-baseline-tools.py`, `regression-baseline.json`, `docs/TESTING.md`, `docs/KNOWN_ISSUES.md`. Required: **empty**.
3. **Protected-function drift** — zero drift across 63 functions and 4 constants.
4. **Write-path absence** — AST scan over `platform/**` confirming zero write calls after the move.
5. **Pre/post hash equality** for the two files moved without edits (`errors.py`, `vocabulary.py`), proving the move was lossless.

### 5.6 — Mutation verification

Re-run in full, in a sandbox **outside the repository**, with bytecode purged before every run — the stale-`.pyc` defect found during Step 1 validation makes that non-optional. Extended from 11 mutations to **13**:

| Original 11 | Plus |
|---|---|
| task state name · terminal classification · legal transition · transition authority · command vocabulary · event vocabulary · UNKNOWN licensing · idempotency composition · payload-hash validation · prohibited-reference detection · stdlib shadowing guard | **12.** JSON-shape check disabled → serializability tests must fail<br>**13.** root-`__init__` guard removed → layout tests must fail |

---

## 6. Implementation Order

Sequenced so that each step is independently verifiable and the riskiest mechanical change is proven before any behavioural change is layered on top of it.

| Step | Action | Verification gate before proceeding |
|---|---|---|
| **0** | Record pre-change SHA-256 of all 13 current files | 13 hashes captured (already recorded in the source-review package) |
| **1** | Create `platform/src/mogo_platform/` and `contracts/` with the two docstring-only `__init__.py` files | `import mogo_platform` succeeds; `platform.system()` still returns `Darwin`; `platform/__init__.py` absent |
| **2** | Move the two **unmodified** files first — `errors.py`, `vocabulary.py` | **Post-move SHA-256 must equal pre-move SHA-256 exactly.** Proves the move mechanism is lossless before anything is edited |
| **3** | Move the five files needing import edits — `ids.py`, `command.py`, `event.py`, `task_states.py`, `boundaries.py` — rewriting imports to relative and updating `DECLARATION_MODULE_BASENAME` | `python3 -m compileall`; all seven modules import under `-W error` |
| **4** | Delete the old `platform/contracts/` tree | Directory gone; no stale `.pyc`; no path in the repository still references it |
| **5** | Update all four test suites: `sys.path` entry, imports, module-name strings | **All 218 existing tests pass unchanged, minus the one removed.** This is the checkpoint that proves the layout change alone introduced no behavioural change |
| **6** | Replace the layout test rule (§3.4) | New guards pass; stdlib guard still passes |
| **7** | Add `require_json_shaped` to `ids.py` — **no call sites yet** | Unit tests for the validator pass in isolation |
| **8** | Wire the three call sites in `command.py` / `event.py` | 14 serializability tests pass; **all prior tests still pass** |
| **9** | Apply §3.5 idempotent hashing **if approved** | Idempotency test passes; every existing digest unchanged |
| **10** | Rewrite `platform/README.md` | Documentation matches implemented reality |
| **11** | Full validation battery (§5) | All gates green |
| **12** | Mutation verification, 13 mutations, sandbox outside repo | 13/13 detected, 13/13 reverted, `diff -r` identical |
| **13** | Regenerate the source-review package with a classifier built on `sys.stdlib_module_names` | Dependency count reads **0** |

**Why this order.** Step 2 before step 3 isolates "did the move lose bytes?" from "did the edit break imports?" Step 5 before step 7 isolates "did the layout change behaviour?" from "did the new validator change behaviour?" — so if something breaks at step 8, the layout is already exonerated. Step 7 before step 8 lets the validator be unit-tested before it can reject anything in production paths.

---

## 7. Rollback Plan

Four layers, strongest first.

| Layer | Mechanism | Scope |
|---|---|---|
| **1. Nothing is committed** | HEAD remains `bd6ff7c`. `git diff --name-status HEAD` is empty and stays empty | Complete abandonment: `rm -rf platform tests/platform tests/run_platform_tests.sh` returns the tree to the pre-Step-1 state — five pre-existing untracked documents |
| **2. Byte-exact restoration is already on disk** | `MOGO-010-STEP-1-SOURCE-REVIEW.md` contains the complete verbatim contents of all 13 current files together with their SHA-256 hashes. The pre-correction state can be reconstructed from it and **verified against the recorded hashes**. This was not designed as a backup; it functions as one | Return to the current, reviewed, 218-test-passing state |
| **3. Step-wise** | Each step in §6 is independently revertible. Steps 7–9 are additive: removing the `require_json_shaped` call sites restores prior validator behaviour exactly, since the function is otherwise unreferenced | Abandon the serializability fix while keeping the layout fix, or vice versa |
| **4. Per-file** | Every change is confined to two untracked roots. No tracked file is touched at any point | Nothing to revert in version control under any outcome |

**What rollback cannot affect, and why:** no dependency is installed (zero third-party), no manifest or lock file is created, no `sys.path` change escapes test-process scope, no protected or frozen path is written, and `regression-baseline.json` is never updated. **Residue after full abandonment: none** — the repository returns byte-for-byte to `bd6ff7c`.

**Trigger conditions for rollback rather than repair:** any mutation check not detected; any Campaign C1 hash mismatch; any nonzero protected-function drift; any change in the identity or count of the six pre-existing Python failures; any tracked file appearing in `git diff`; stdlib `platform` resolving inside the repository.

---

## 8. Recommendation

**Proceed with implementation now.** No further investigation is required for I-1 through I-4 or I-6.

The reasoning:

- **Every issue is understood at root-cause level**, and each root cause was verified by executing the current code rather than reading it. I-3, I-4 and I-5 were found precisely because the probes were run rather than assumed — a review that stopped at the two named defects would have shipped three more.
- **No issue touches scientific validity**, and that is structural rather than fortunate: `platform/**` has no write path, no network capability, no replay path, and no reference to any protected or frozen record. Campaign C1 is verified 33/33 and protected-function drift is zero.
- **Both corrections are bounded and reversible.** Nothing is committed, nothing tracked changes, and a byte-exact snapshot of the current state already exists with verifiable hashes.
- **The layout correction is verified, not proposed on theory.** The src layout was built in a sandbox and exercised with both the repository root and `platform/src` on `sys.path` simultaneously; the control case confirmed that only `platform/__init__.py` breaks stdlib `platform`.
- **The approved architecture is not obstructed.** ADR-012 approval #2 names the top-level `platform/` bounded context, which is preserved exactly; Architecture §7 and §25 constrain `platform/**`, which still covers everything. The only deviation is from Inventory §10, titled "**Recommended** platform location" and part of the superseded Step 1 historical record. **No higher-authority document must change**, though an optional ADR-012 addendum recording the refinement is available if governance wants the sketch updated.

**One decision remains genuinely open and is not assumed: §3.5**, the one-line change routing `canonical_json_bytes` through `as_plain` to make validation idempotent. I recommend including it — without it the shape validator must either reject frozen input or accept input that hashing then refuses. If it is declined, I-5 stays open and documented rather than half-fixed, and the implementation proceeds unchanged in every other respect.

**Two things this correction deliberately does not do:** it does not repair the six pre-existing Python test failures (out of scope by instruction, and proven to predate all Step 1 work), and it does not modify `MOGO-010-STEP-1-SOURCE-REVIEW.md` (§2.4 records the classifier defect instead, per instruction).

**Commit boundary after correction: 15 files, revised from 13** — 7 renamed in place, 2 added, 7 old paths deleted, all untracked. Still one bounded commit, still nothing outside `platform/` and `tests/platform/`.

---

**No source code was modified. Nothing was staged, committed, tagged or pushed. This document is the only file created.**


---

# APPENDIX — FINAL IMPLEMENTATION STATUS

**Added 2026-08-07 after implementation. The plan text above is unchanged: nothing in the
original reasoning was rewritten or removed.** This appendix records only what happened when
the plan was executed.

## Status of each issue

| # | Issue | Planned severity | Outcome |
|---|---|---|---|
| I-1 | Import and package architecture | High | ✅ implemented as planned — `mogo_platform` under `platform/src/` |
| I-2 | Unsupported unknown-field values | High | ✅ implemented — `require_json_shaped()` |
| I-3 | Non-finite floats | High | ✅ implemented — `math.isfinite` at every depth |
| I-4 | Non-string mapping keys | Medium-High | ✅ implemented — exact `str` check, `bool`/`int` rejected |
| I-5 | Idempotent validation | Medium | ✅ implemented — **approved and required by the operator**, no longer optional |
| I-6 | Dependency classifier | Low | ✅ regenerated review uses `sys.stdlib_module_names`; third-party count now **0** |

## Where implementation differed from the plan

| Planned | Actual | Why |
|---|---|---|
| §3.5 recorded as an **open decision** | **Approved and required** by the implementation authorization | Operator ruling; the plan's recommendation was accepted |
| "~233 tests expected" | **268** | The required-test list in the authorization was broader than the plan's estimate, particularly for serializability and layout guards |
| 13 mutations planned | **19 executed** | The authorization required seven additional mutation checks |
| Boundary suite "34 → ~36" | **34 → 42** | Nine layout guards replaced one over-broad rule |

## What the plan did not anticipate

**Mutation 17 escaped detection on its first run.** Unwiring the command-payload shape check failed no test, because canonical hashing already rejects `object()` and `NaN`, and a coerced `{1:"a"}` key then fails the hash comparison — the right exception class for the wrong reason. The plan assumed the payload tests would pin the shape validator; they asserted only the exception class. Fixed by asserting the `$payload.x` path, producible only by the shape validator, plus a new ordering test. **The test was made stricter; nothing was weakened to make a mutation pass.**

**Four self-inflicted defects surfaced during the correction**, each caught by the suite and fixed at source: a stale `CONTRACTS_DIR` reference; an obsolete bare-name assertion; an arbitrary `>= 5` relative-import threshold replaced by an exact four-module set; and a self-reference false positive where the new `platform/contracts` scan flagged the file that declares the string, resolved by one named exemption plus a directory-absence assertion.

**One anchor mismatch during migration** left `ids.py` untouched (the edit function is atomic per file); its hash was verified unchanged before retrying.

## Verification of the plan's own claims

| Plan claim | Verified? |
|---|---|
| Move can be made byte-preserving | ✅ `vocabulary.py` still carries its pre-move SHA-256 in the final manifest |
| Nested `__init__.py` cannot shadow stdlib `platform` | ✅ `platform.system()` → `Darwin`, resolved outside the repository |
| No higher-authority document must change | ✅ none amended |
| No existing tracked file must change | ✅ `git diff --name-status HEAD` empty throughout |
| Solution remains standard-library only | ✅ third-party count 0 |
| Step 1 remains non-executable | ✅ zero write calls, zero network imports, zero subprocess calls; package markers docstring-only |
| Replay / evidence / scientific-validity risk is structurally zero | ✅ C1 33/33, drift zero, no write path exists |

## Final state

**268 platform tests passing · 19/19 mutations detected and reverted · 947/947 canonical fixtures · zero drift · C1 33/33 · 0 tracked files modified · 15-file commit boundary · nothing staged, committed, tagged or pushed.**

The six pre-existing Python failures remain exactly the same six, unrepaired, per instruction. Appendix A's analysis stands unchanged — including that **A.6 requires owner judgement rather than mechanical repair.**

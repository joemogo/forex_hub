# MOGO-010 Step 1 — Release Notes

**Milestone:** MOGO-010 Phase II, Step 1 — Automation Platform contracts
**Base commit:** `bd6ff7c8ccebe31431c4d58c345894d7effdb738` (MOGO-009 architecture approval)
**Status:** implemented, corrected, validated — **not committed**
**Date:** 2026-08-07

---

## What Step 1 now implements

The contract layer of the Phase II Automation Platform, and nothing else. Seven modules under a uniquely named package, with 268 tests.

| Module | Implements |
|---|---|
| `contracts/ids.py` | Identifier model (Catalog §H), idempotency keys (§I), canonical JSON hashing, JSON-shape validation, collision handling |
| `contracts/errors.py` | Ten-type exception hierarchy, canonical raisers, inert §K error-class table |
| `contracts/vocabulary.py` | Closed vocabularies: 17 commands, 34 events, 12 licensing statuses, 7 capability lifecycle states |
| `contracts/command.py` | Command envelope contract (§A) — 13 required, 5 optional |
| `contracts/event.py` | Operational event envelope (§B) — 14 required, 5 optional, deeply immutable |
| `contracts/task_states.py` | 13 task states, 4 terminal, 25 transitions with authority (§L) |
| `contracts/boundaries.py` | Protected-boundary declarations (Architecture §7) and the single reference detector |

**Guarantees every validated envelope carries:**

- **Strictly JSON-shaped** — no `object`, `set`, `bytes`, `complex` or any non-JSON type at any depth
- **No `NaN` or `±Infinity`** anywhere — JSON cannot express them
- **No non-string mapping keys** — never coerced, never stringified
- **Additive fields preserved** verbatim and included in the payload hash
- **Deeply immutable** — `MappingProxyType` mappings, tuple arrays, no mutator anywhere
- **Idempotent** — `validate(validate(x))` succeeds, preserving values, unknown fields, payload hash and immutability
- **Free of prohibited references** — any Architecture §7 path or Catalog §H not-reused symbol is rejected

**Non-negotiables held:** zero third-party dependencies, no package manifest, no I/O of any kind (not even a read-mode `open()`), no network capability, no subprocess, no write path, and no import from `scripts/trader_intelligence/`.

## What was corrected before commit

Six issues, two named by the independent source review and four found by probing.

| # | Issue | Severity | Fix |
|---|---|---|---|
| **I-1** | Flat module names (`platform_ids`) reached by a per-caller `sys.path` insert; an over-broad "no `__init__.py` anywhere" rule enforced by a test | High | `mogo_platform` package under `platform/src/`; relative sibling imports; one path entry, tests only; rule narrowed to the single file that actually collides |
| **I-2** | `object()`, `set`, `bytes` survived validation and freezing, then failed at serialization | High | `require_json_shaped()` on the whole envelope |
| **I-3** | `NaN`/`±Infinity` survived and serialized to bare `NaN`/`Infinity` — **invalid JSON**, produced silently | High | `math.isfinite` at every depth |
| **I-4** | Non-string keys silently coerced (`{1:"a"}` → `{"1":"a"}`); mixed keys crashed at serialization | Medium-High | Exact `str` key check; `bool` and `int` rejected |
| **I-5** | Validation was not idempotent — revalidating a validated envelope raised *"mappingproxy is not JSON serializable"* | Medium | `canonical_json_bytes` routes through `as_plain`; no digest moves |
| **I-6** | Source-review classifier misreported stdlib `platform` as a third-party dependency | Low | Regenerated review classifies against `sys.stdlib_module_names` |

**Why the `platform/` name needed care.** `platform` is a standard-library module. A package marker at the repository-root `platform/` breaks it process-wide — Python 3.14 even suggests renaming the directory. The first implementation over-generalised that into "no `__init__.py` anywhere under `platform/`", which forced generic global module names and per-caller path manipulation. Only `platform/__init__.py` causes the collision; nested markers under `platform/src/mogo_platform/` cannot, because they are reached through a different path entry and carry a name that is not a standard-library name. Four guards now enforce the narrow rule.

## What remains deferred

None of these is simulated, stubbed or claimed:

| Deferred | Blocked on |
|---|---|
| Opaque-identifier uniqueness check | the operational event log |
| Command rejection **events** | an event store |
| Event persistence, ordering, `sequence` monotonicity, chain replay | the event log |
| Capability **registration** verification | the Capability Registry (ADR-012 D-16) |
| Licensing **evaluation** | the policy gate |
| Task-state **application** | the orchestrator |
| Late-transition **logging** | the event log |
| Review routing, retry, backoff, dead-letter execution | later, separately approved steps |
| Package manifest (ADR-012 D-01) | a genuine runtime dependency or installable surface |
| `tests/run_all.sh` integration (ADR-012 D-12) | separate governance authorization |

## Exact test results

| Suite | Tests | Failures | Errors | Skipped |
|---|---:|---:|---:|---:|
| `test_platform_identifiers.py` | 82 | 0 | 0 | 0 |
| `test_platform_envelopes.py` | 108 | 0 | 0 | 0 |
| `test_platform_task_states.py` | 36 | 0 | 0 | 0 |
| `test_platform_boundaries.py` | 42 | 0 | 0 | 0 |
| **Platform total** | **268** | **0** | **0** | **0** |

Runtime 0.29 s. Standard-library `unittest`, fully offline, deterministic, repeatable.

| Other gate | Result |
|---|---|
| `tests/run_all.sh` (canonical, unmodified) | 17 suites, 947 fixtures, **947 passed, 0 failed** |
| Protected-function drift | **zero** — 63 functions, 4 constants byte-identical |
| Campaign C1 manifest | **33/33 verified**, 0 missing, 0 mismatched, 0 unlisted |
| Mutation verification | **19/19 detected, 19/19 reverted** |
| Third-party dependencies | **0** |

## Known pre-existing issues (not introduced, not repaired)

Six Python tests fail at the base commit, independently of Step 1. Proven by running the same eight suites against a clean `git archive HEAD` extraction with no `platform/` present: identical 451 tests, 6 failures, same names.

| Test | Nature |
|---|---|
| `test_expected_node_and_edge_counts` | expired census — `TRADER` nodes 5 ≠ 3 |
| `test_production_evidence_tree_is_still_genuinely_empty` | expired emptiness — 12 ≠ 0 |
| `test_production_graph_unchanged_without_real_corpus` | expired emptiness — 815 nodes |
| `test_production_graph_unchanged_without_real_knowledge_library` | expired emptiness — 773 nodes |
| `test_all_195_claims_are_inventoried` | expired census — 226 ≠ 195 |
| `test_delta_reports_the_unclosed_risk_gap` | **⚠️ needs owner judgement** — `draftStopPlacementRules` 2 ≠ 0 |

Five are expired expectations of the exact kind `docs/TESTING.md` predicts (*"those assertions expire the first time real data is ingested, and they fail in a way that looks like a regression but is not"*). **The sixth is different:** a risk gap recorded as open may now be partly closed by two new stop-placement rules. That is a knowledge-engineering decision, not test hygiene, and its repair may touch generator code rather than test code.

These are **invisible to the canonical gate**, because `tests/run_all.sh` globs `tests/run_*_tests.js` only — the ADR-012 D-12 gap — and they are **not disclosed in `docs/KNOWN_ISSUES.md`. Recommended first remediation step: disclose them.**

## Proposed commit scope

**15 files, one bounded commit, all currently untracked:**

```
platform/README.md
platform/src/mogo_platform/__init__.py
platform/src/mogo_platform/contracts/__init__.py
platform/src/mogo_platform/contracts/{ids,errors,vocabulary,command,event,task_states,boundaries}.py
tests/platform/test_platform_{identifiers,envelopes,task_states,boundaries}.py
tests/run_platform_tests.sh
```

**Zero existing tracked files modified.** Excluded from the commit: the four MOGO-010 report documents, the four pre-existing 2026-08-04 legacy documents, `tests/run_all.sh`, `docs/TESTING.md`, `docs/KNOWN_ISSUES.md`, `regression-baseline.json`, and any manifest or lock file.

**Blocker before any push:** local `main` has no upstream and `origin/main` is unrelated history (`abfc763`). The authoritative branch is `origin/mogo-main`.

## Rollback summary

| Layer | Mechanism |
|---|---|
| Nothing committed | HEAD unchanged at `bd6ff7c`; `git diff --name-status HEAD` empty |
| Full abandonment | `rm -rf platform tests/platform tests/run_platform_tests.sh` |
| Byte-exact restoration | `MOGO-010-STEP-1-SOURCE-REVIEW.md` contains every file verbatim with SHA-256 hashes |
| Per-file | All changes confined to two untracked roots; nothing to revert in version control |

**Residue after full abandonment: none.** No dependency installed, no manifest, no lock file, no `sys.path` change outside test-process scope, no protected path written, no baseline updated.

---

**Nothing was staged, committed, tagged or pushed. No Step 2 work began.**

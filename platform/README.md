# MOGO Automation Platform

**Milestone:** MOGO-011 Step 1 · **Status:** contracts + runtime kernel — one executable demonstration
**Governing document:** [`AUTOMATION_PLATFORM_CONSTITUTION.md`](../docs/governance/AUTOMATION_PLATFORM_CONSTITUTION.md) v1.0 — senior to everything here
**Architecture:** [MOGO-009 specification](../docs/architecture/MOGO-009-AUTOMATION-PLATFORM-ARCHITECTURE.md) · [Contract Catalog](../docs/architecture/MOGO-009-CONTRACT-CATALOG.md) · [ADR-012](../docs/adr/ADR-012-automation-platform-architecture.md)

---

## ⛔ READ FIRST — the `platform` name collision, and the *narrow* rule

**Never create `platform/__init__.py`. That one file, and only that file, is the problem.**

`platform` is a Python standard-library module (`platform.system()`, `platform.python_version()`). This directory sits at the repository root, which is on `sys.path` whenever Python runs from here. A package marker **at this directory's root** would make the repository the `platform` package and break the stdlib module process-wide.

Nested package markers deeper in the tree are a different matter entirely, and the distinction is load-bearing. All four configurations were tested empirically on Python 3.14.6:

| Configuration | `import platform` resolves to | Package importable? |
|---|---|---|
| **`platform/__init__.py` present** | **this directory** — `platform.system()` raises `AttributeError`; **stdlib broken repository-wide** | yes, at the cost of breaking stdlib |
| No `__init__.py` (PEP 420 namespace) | stdlib `platform.py` ✅ | no — `'platform' is not a package` |
| No `__init__.py` + `sys.path` insert on a leaf directory | stdlib ✅ | only as flat, generic top-level modules |
| **`platform/src/mogo_platform/` + `sys.path` insert on `platform/src`** ✅ **current** | stdlib `platform.py` ✅ intact | yes — as a uniquely named package |

**Why the nested markers cannot shadow anything — three independent reasons:**

1. `platform/__init__.py` is never created, so this directory stays a namespace directory and the stdlib *regular module* wins over it.
2. The `sys.path` entry is `platform/src`, which contains only `mogo_platform/`. Nothing named `platform` is reachable through it.
3. `mogo_platform` is not a standard-library name — verified against `sys.stdlib_module_names`, not a hand-maintained list.

> **Historical note, recorded so the mistake is not repeated.** The first version of this file stated *"never create an `__init__.py` anywhere under `platform/`"*. That was an over-generalisation of a real constraint, and it was enforced by a test, which turned a wrong rule into policy. It blocked normal packaging, forced generic top-level module names (`platform_ids`), and required every caller to manipulate `sys.path`. MOGO-010 Step 1 correction I-1 narrowed the rule to the one file that actually causes the collision. **Do not re-broaden it.**

## Import convention

```python
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC_DIR = os.path.join(REPO_ROOT, "platform", "src")   # the ONE path entry
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from mogo_platform.contracts import ids, event         # noqa: E402
```

Inside the package, modules import each other **relatively**:

```python
from . import errors
from . import ids
```

The single `sys.path` insert is a bridge until a package manifest exists (ADR-012 D-01, deferred by operator ruling). Once a manifest lands, `mogo_platform` becomes installable and the insert disappears — the src layout is chosen precisely so that step requires no restructuring.

**Guards.** Four tests protect this permanently: `test_no_init_py_at_platform_root`, `test_stdlib_platform_module_is_importable_and_functional`, `test_package_markers_are_docstring_only`, and `test_no_retired_flat_module_is_importable`. If someone adds `platform/__init__.py`, the suite fails immediately with an explanatory message instead of the repository breaking in a confusing way.

---

## Layout

```
platform/
  README.md
  mogo_runtime.py               operator launcher (the sys.path bridge)
  runtime/                      RUNTIME STATE — git-ignored, disposable
  src/
    mogo_platform/
      __init__.py               docstring only — no imports, no side effects
      contracts/                MOGO-010 — pure, no I/O, ever
        ids.py · errors.py · vocabulary.py · command.py
        event.py · task_states.py · boundaries.py
      runtime/                  MOGO-011 — the execution kernel
        paths.py                state locations + the write-confinement guard
        errors.py               runtime error taxonomy
        store.py                SQLite connection, transactions, process lock
        schema.py               DDL, append-only triggers, migrations
        event_log.py            THE AUTHORITATIVE append-only JSONL log
        projection.py           log → derived index, idempotently
        registry.py             capability registry and dispatch eligibility
        worker.py               execution; reports, never transitions
        orchestrator.py         receipt, transitions, dispatch — the only writer
        audit.py                operator reports and integrity verification
        cli.py                  argparse subcommands
        capabilities/echo.py    research.runtime.echo.v1 — pure, deterministic
```

## Two layers, two different rules

| | contracts/ | runtime/ |
|---|---|---|
| I/O | **none, ever** — no `open()` even for reading | permitted, but **confined to the state root** |
| Purity | pure functions only | orchestrator writes; worker is pure; capability is pure |
| Enforcement | absolute no-I/O test | every write site calls `paths.assert_inside_state_root()` |
| Writes to the six §7 targets | prohibited | prohibited |
| Network / subprocess | prohibited | prohibited |

MOGO-010 applied the absolute no-I/O rule to all of `platform/**`. That was correct while the platform was contracts-only, but stricter than the architecture requires — Architecture §7 forbids writing to six named targets, not writing in general. MOGO-011 narrowed the absolute rule to the layer it belongs to and gave the runtime a **confinement** rule it did not previously have, so coverage increased.

## The runtime, in one paragraph

The **JSONL event log is the source of truth**; SQLite is a derived index and read model that can always be rebuilt from it (`reset --rebuild-index` proves this, and a test asserts the rebuild reproduces the database). Every state change is appended to the log and fsynced **before** it is applied to the index — so a crash between the two leaves the index merely behind, and replay converges, whereas the reverse order could commit a state change with no event. One process at a time, enforced by an exclusive `fcntl.flock`, which is why **no time-based lease is needed**. Task state is written only by the orchestrator; the worker reports.

```bash
python3 platform/mogo_runtime.py demo        # the full end-to-end demonstration
python3 platform/mogo_runtime.py status      # health snapshot
python3 platform/mogo_runtime.py audit       # complete ordered activity record
python3 platform/mogo_runtime.py verify      # integrity checks; non-zero on failure
python3 platform/mogo_runtime.py reset --rebuild-index   # proves the log is the truth
```

**Runtime state lives in `platform/runtime/` and is git-ignored** by a nested self-ignoring `.gitignore`, of which only the `.gitignore` itself is committed (ADR-012 D-06). Deleting the whole directory loses nothing but demonstration data.

## Contract guarantees

Every envelope returned by `validate_command()` or `validate_event()` is:

| Guarantee | Enforced by |
|---|---|
| **Strictly JSON-shaped** — no `object()`, `set`, `bytes`, `complex`, or any other non-JSON type, at any depth | `ids.require_json_shaped()` on the whole envelope |
| **Free of non-finite floats** — `NaN` and `±Infinity` rejected anywhere, because JSON cannot express them | same |
| **Free of non-string keys** — never coerced, never stringified; `bool` and `int` keys rejected | same |
| **Additive-field preserving** — a valid unknown field is retained verbatim and participates in the payload hash | validators never drop a field |
| **Deeply immutable** — mappings are `MappingProxyType`, arrays are tuples | `ids.freeze()` |
| **Idempotent** — `validate(validate(x))` succeeds and preserves values, unknown fields, payload hash and immutability | `canonical_json_bytes()` routes through `as_plain()` |
| **Free of prohibited references** — see below | `boundaries.find_prohibited_references()` |

## What is deliberately deferred

Each is declared in the relevant module docstring, and none is simulated:

| Deferred | Blocked on |
|---|---|
| Retry, backoff, dead-letter execution | a later, separately approved step |
| Time-based leases | a daemon or a second worker; unnecessary while single-writer |
| **Policy gate** (Architecture §32 item 5) | **required before any connector** |
| Connectors of every kind, acquisition, transcripts | the policy gate |
| Evidence candidates, hypothesis promotion, scientific writes | governance, and never automatic |
| Review workflow | a later step |
| Package manifest (ADR-012 D-01) | a genuine runtime dependency |
| `tests/run_all.sh` integration (ADR-012 D-12) | separate governance authorization |

An **acquisition-class** operation is refused rather than guessed: `classify_policy_check` returns `requires_policy_gate` and the orchestrator declines to dispatch, because no policy gate exists. Fail-closed, by construction.

## Prohibited boundaries

`platform/**` must never contain a write path to any of these (MOGO-009 Architecture §7):

```
evidence/
docs/campaigns/
docs/trader-intelligence/governance/PREREG-*.md
docs/MOGO-003-VERIFIED-REPLAY-RECORD.md
index.html
hypothesis-registry.json      (read-only; updates stay operator-driven)
```

It must also never reuse `mogo.evidence-canon.v1`, `mogo.evidence-package.v1`, `alexGStableHash`, or `sourceTradeId` (Contract Catalog §H reuse verdict), and must never import from `scripts/trader_intelligence/` — that tree is reachable only through adapters, and no adapter exists.

**`contracts/boundaries.py` is the single module permitted to contain those literals**, because it is the machine-readable declaration of the boundary. Enforcement distinguishes the two cases: the declaration module must contain the *complete* approved set with nothing omitted and nothing invented; every other `.py` module under `platform/` must contain none of them. The literal scan covers `.py` files only — this README documents the boundary and is intentionally outside that scan.

## Running the tests

```bash
bash tests/run_platform_tests.sh
```

or directly:

```bash
python3 -m unittest \
  tests.platform.test_platform_identifiers \
  tests.platform.test_platform_envelopes \
  tests.platform.test_platform_task_states \
  tests.platform.test_platform_boundaries
```

All suites are standard-library `unittest`, fully offline, deterministic, and repeatable. They require no network, no credentials, and no fixture copied from the repository tree.

`tests/run_all.sh` is **deliberately unmodified**: repository-wide runner integration is separately governed (ADR-012 D-12, Specification §33). Until that authorization lands, the platform suites run through their own runner.

## Dependencies

**None.** Python 3.14 standard library only. There is no `pyproject.toml`, `requirements.txt`, `setup.py`, or lock file, and Step 1 introduces none — deferred until a genuine runtime dependency or installable execution surface exists. The Python floor is enforced by a test rather than declared in a manifest nothing reads.

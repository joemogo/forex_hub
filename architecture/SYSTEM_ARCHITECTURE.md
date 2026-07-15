# System Architecture

## Physical structure

MOGO is a single static HTML file (`index.html`), one `<script>` tag, one global JavaScript
scope, no build step, no backend, no package manager. `localStorage` is the only persistence
layer (see [STORAGE.md](STORAGE.md)). `index-v2.9-KNOWN-GOOD.html` is a frozen reference file,
hash-checked by the regression tooling, never executed or modified.

## Ownership boundaries

```
┌───────────────────────────────────────────────────────────────────────┐
│                         MOGO TRADING OS  (core app)                    │
│                                                                          │
│   ┌─────────────────────┐        ┌──────────────────────────────────┐ │
│   │  STRATEGY REGISTRY    │──────▶│         STRATEGY SDK              │ │
│   │  (directory: id,      │ points │  (contract: Identity, accessors,  │ │
│   │  label, status,       │  to    │  journal adapter, performance,    │ │
│   │  panelId, module ref) │        │  playbook, mount point + optional │ │
│   └──────────┬────────────┘        │  lifecycle/diagnostics/AI/DNA)    │ │
│              │                     └───────────────┬────────────────────┘ │
│              │ iterated by                          │ implemented by     │
│              ▼                                      ▼                    │
│   ┌─────────────────────────────────────────────────────────────────┐  │
│   │                SHARED SERVICES  (core-owned, strategy-agnostic)  │  │
│   │  Dashboard · Unified Journal · Charts · Statistics aggregation   │  │
│   │  Scanner/poll host · AI shell (consumes required contract only)  │  │
│   │  Reports · Academy · Diagnostics host · Dev Tools host           │  │
│   │  Shared Utility Kernel: pipSize · pipValuePerLot · getSession    │  │
│   │  · getCandleCloseTime · isPreferredTradingDay  (frozen, pure)    │  │
│   └───────────┬───────────────────┬──────────────────┬──────────────┘  │
│               │ calls via SDK     │ calls via SDK     │ calls via SDK   │
│    ┌──────────┴────────┐ ┌────────┴──────────┐ ┌──────┴─────────────┐  │
│    │ STRATEGY MODULE     │ │ STRATEGY MODULE    │ │ STRATEGY MODULE     │  │
│    │ JVM                  │ │ Alex G S&R v1       │ │ (future: TJR/ICT/   │  │
│    │ (registered, v12.1.0)│ │ (registered, v12.0.0)│ │  Silver Bullet/...)  │  │
│    │ own state + keys     │ │ own state + keys    │ │ own state + keys     │  │
│    └──────────────────────┘ └──────────────────────┘ └──────────────────────┘  │
└───────────────────────────────────────────────────────────────────────┘
```

- **The core app** owns the Strategy Registry, the SDK contract, and every Shared Service. It
  never reaches into a strategy module's internal state directly.
- **Each strategy module** owns its own internal pipeline (scanning, qualification, trade
  construction, risk, trade management), its own state tree, and its own `localStorage`
  namespace. It talks to Shared Services only through the SDK boundary, plus the frozen Shared
  Utility Kernel it may call directly (see below).
- **The Shared Utility Kernel** is the one deliberate exception to "only talk through the SDK": a
  small set of pure, stateless, protected functions (`pipSize`, `pipValuePerLot`, `getSession`,
  `getCandleCloseTime`, `isPreferredTradingDay`) that any strategy may call directly. This is a
  real, audited dependency Alex already has on JVM's utilities — formalized as shared kernel API
  surface rather than an implicit cross-module call.

## Why strategy internals are not standardized

JVM's qualification model (a numeric confluence score against `WEIGHTS`/`ALERT_THRESHOLD`) and
Alex's (a categorical zone/touch/break state machine) are genuinely different shapes, not two
implementations of one abstract idea. The Strategy SDK deliberately does **not** impose a common
interface on Scanner/Qualification/Trade Construction/Risk/Trade Management — only on the handful
of things the *core app* actually needs to call generically (see
[STRATEGY_SDK.md](STRATEGY_SDK.md)). Forcing a shared internal pipeline shape would have traded
real accuracy for uniformity the app doesn't need — exactly the over-engineering this project's
guiding philosophy rejects (see [VISION.md](VISION.md)).

## The seam that actually needed a framework

A full codebase audit (pre-dating v12.0.0) found the two existing strategies' *internals* were
already well isolated by convention: separate state, separate storage keys, separate save/load,
separate function-name prefixes. The real coupling was confined to a small set of places where
the surrounding app hardcoded both strategies by name:

- `getUnifiedJournalRecords()` / `normalizeJournalRecord()` — the journal read path
- `renderDashboard()` — P&L/win-rate tiles and the running-trades table
- `showPanel()` — the page router's per-strategy init hook
- `applyDeveloperModeVisibility()` / `toggleDeveloperMode()` — Dev Tools card visibility
- `runDiagnostics()` — the per-strategy isolation self-test
- `renderMiniJournal()` / `getFilteredJournalRecords()` — strategy-labeled journal views
- Strategy Center's per-strategy tab content

v12.0.0 (Release 1) generalized these seams for ALEX specifically, wrapping its existing engine
through Manifest/Services references rather than rewriting it. v12.1.0 (Release 2) registered
JVM the same way — a real validation of the contract, not a repeat, since it required checking
JVM's actual needs against the existing SDK field by field (it turned out to need zero
extensions). Two of the seams above (`runDiagnostics()`'s isolation check, `renderMiniJournal()`)
remain ALEX-only, disclosed as deliberate: no genuine JVM-specific behavior exists to wrap for
either. Strategy Center's per-strategy tab content still hardcodes exactly two strategies —
correctly, for a two-strategy world — and generalizing it for N strategies is the explicit,
optional, deferred Release 3 scope (see [STRATEGY_REGISTRY.md](STRATEGY_REGISTRY.md) and
[../docs/adr/ADR-005-strategy-framework.md](../docs/adr/ADR-005-strategy-framework.md)).

## Testing as an architectural control, not an afterthought

`regression-baseline-tools.py` SHA-1-hashes the extracted source text of every
`PROTECTED_FUNCTIONS`/`PROTECTED_CONSTANTS` entry (63 functions, 4 constants as of v12.0.0) and
compares against a committed `regression-baseline.json`. None of the seam functions above are
themselves protected — meaning any Strategy Framework refactor of the seams can be mechanically
proven to leave trading logic untouched, without the baseline tool itself needing to change. This
is why the framework migration was judged low-risk: the proof mechanism already existed before
the framework did. See [../docs/TESTING.md](../docs/TESTING.md) for the full testing model.

# Strategy Registry

The Registry is a **directory**, not a contract and not an implementation. It tells the core app
which strategies exist and where to find each one's Manifest and Services. See
[STRATEGY_SDK.md](STRATEGY_SDK.md) for what a Manifest/Services pair must contain.

## What belongs in the Registry

Only routing/reference data the core app's shared seams actually need to dispatch calls
generically:

```
STRATEGY_REGISTRY = [
  { manifest: ALEX_MANIFEST, services: ALEX_SERVICES }
  // JVM is intentionally not registered yet — Release 1 scope was ALEX only.
]
```

Each entry is a `{ manifest, services }` pair — the Registry itself holds no logic, no computed
values, and no strategy-specific branching.

## Lookup functions

```
findStrategyEntry(id)     // returns the {manifest, services} pair, or null
getStrategyManifest(id)   // returns entry.manifest, or null
getStrategyServices(id)   // returns entry.services, or null
```

All three are pure, read-only, and return `null` rather than throwing when a strategy isn't
registered — every core-app call site built on them (see below) is required to handle that `null`
by falling back to its pre-framework behavior.

## What does NOT belong in the Registry

- **Engine logic.** Scanning, qualification, trade construction, risk, and trade management are
  internal to the strategy module — never inlined into the Registry.
- **DNA / descriptive metadata.** That's Manifest content (see [STRATEGY_SDK.md](STRATEGY_SDK.md)),
  not routing data — the Registry shouldn't need to change every time a strategy's descriptive
  copy changes.
- **Version history / changelog.** That belongs on the strategy's own Manifest `release` field.
- **Anything computed.** Performance stats, journal records, progress — the Registry stores a
  reference to the function that computes it, never the computed value, mirroring the read-only
  analytics principle applied everywhere else in the app
  ([ADR-004](../docs/adr/ADR-004-read-only-analytics-principle.md)).

This split exists so the Registry stays small and boring even as more strategies are added — it
is read on every render of every seam below, and must never become a second, driftable copy of
strategy state.

## Where the Registry is consulted today (v12.0.0)

Exactly the seams identified by the architecture audit as hardcoding ALEX by name, each with a
fallback to its pre-framework literal if the lookup returns `null`:

| Function | What it looks up |
|---|---|
| `getUnifiedJournalRecords()` | `Services.getJournal()` / `Services.normalize()` |
| `renderDashboard()` | `Services.getAccount()` (P&L/win-rate tile, running-trades table) |
| `showPanel()` | `Services.onOpen()` |
| `applyDeveloperModeVisibility()` | `Manifest.devToolsCardId` |
| `runDiagnostics()` | `Services.isolationCheck()` |
| `renderMiniJournal()` | `Manifest.inspectorCardId` |

`toggleDeveloperMode()` and `getFilteredJournalRecords()` needed no change — the former contains
no strategy-specific logic at all, and the latter already filtered purely on the already-normalized
`strategyLabel` field rather than a hardcoded literal.

## Adding a new strategy

Per the approved design, adding a future strategy (TJR, ICT, Silver Bullet, or otherwise) should
require only:

1. Its own state/storage/save-load pair, following the existing Alex pattern.
2. Its own engine functions, added to `PROTECTED_FUNCTIONS` once frozen.
3. One new `STRATEGY_REGISTRY` entry.

No further edits to Dashboard, the Journal, the panel router, Developer Mode, or Diagnostics
should be necessary — that is the entire point of having generalized the seams above instead of
adding a third hardcoded branch to each. This has not yet been exercised with a real second
strategy; JVM's own registration (Release 2) is the next, harder proof of this claim (see
[../docs/adr/ADR-005-strategy-framework.md](../docs/adr/ADR-005-strategy-framework.md)).

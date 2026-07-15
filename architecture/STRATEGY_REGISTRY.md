# Strategy Registry

The Registry is a **directory**, not a contract and not an implementation. It tells the core app
which strategies exist and where to find each one's Manifest and Services. See
[STRATEGY_SDK.md](STRATEGY_SDK.md) for what a Manifest/Services pair must contain.

## What belongs in the Registry

Only routing/reference data the core app's shared seams actually need to dispatch calls
generically:

```
STRATEGY_REGISTRY = [
  { manifest: JVM_MANIFEST, services: JVM_SERVICES },
  { manifest: ALEX_MANIFEST, services: ALEX_SERVICES }
]
```

Both strategies are registered as of v12.1.0 (Release 2). Order in the array carries no
semantic meaning — lookups are always by `manifest.id`, never by position.

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

## Where the Registry is consulted today (v12.1.0)

Every seam identified by the original architecture audit as hardcoding a strategy by name, with
what each strategy actually wired and a fallback to the pre-framework literal if the lookup
returns `null`:

| Function | What it looks up | ALEX | JVM |
|---|---|---|---|
| `getUnifiedJournalRecords()` | `Services.getJournal()` / `Services.normalize()` | ✓ (Release 1) | ✓ (Release 2) |
| `renderDashboard()` | `Services.getAccount()` (P&L/win-rate tile, running-trades table) | ✓ | ✓ |
| `showPanel()` | `Services.onOpen()` | ✓ | ✓ |
| `applyDeveloperModeVisibility()` | `Manifest.devToolsCardId` | ✓ | ✓ |
| `runDiagnostics()` | `Services.isolationCheck()` | ✓ | not wired — no genuine JVM-specific isolation check exists to extract |
| `renderMiniJournal()` | `Manifest.inspectorCardId` | ✓ | not wired — JVM's branch is confirmed dead code (see below) |

`toggleDeveloperMode()` and `getFilteredJournalRecords()` needed no change for either strategy —
the former contains no strategy-specific logic at all, and the latter already filtered purely on
the already-normalized `strategyLabel` field rather than a hardcoded literal.

**Two seams were deliberately left untouched for JVM, with why disclosed** (Release 2's
pre-implementation audit found these, but judged them out of scope):
- `renderMiniJournal()`'s JVM branch (`'paperTradeInspectorCard'`) is unreachable — the function
  is only ever called in the real app with `strategyLabel='ALEX'`; JVM's mini-journal uses its
  own dedicated `renderPaperMiniJournal()` (v9.0), deliberately not built on this shared function.
  Generalizing dead code isn't a genuine seam fix.
- Strategy Center (`renderRules()`/`setStrategyCenterTab()`) and `journalStrategyBadge()`'s
  2-color ternary hardcode a 2-strategy-count assumption, but not a JVM-specific
  misrepresentation — both already render JVM correctly today. Generalizing them for N strategies
  is the optional, deferred Release 3 scope named in
  [ADR-005](../docs/adr/ADR-005-strategy-framework.md), not required for JVM's own registration.

## Adding a new strategy

Per the approved design, adding a future strategy (TJR, ICT, Silver Bullet, or otherwise) should
require only:

1. Its own state/storage/save-load pair, following the existing Alex/JVM pattern.
2. Its own engine functions, added to `PROTECTED_FUNCTIONS` once frozen.
3. One new `STRATEGY_REGISTRY` entry.

No further edits to Dashboard, the Journal, the panel router, Developer Mode, or Diagnostics
should be necessary — that is the entire point of having generalized the seams above instead of
adding a third hardcoded branch to each. **This claim has now been exercised twice** (ALEX in
Release 1, JVM in Release 2) with zero SDK extensions required for either — a meaningful
validation of the original design, not just a repeat. A genuine third strategy remains the next,
harder proof (it would also be the point where the "N-strategy" seams named above, if still
hardcoded to 2, would need Release 3's generalization).

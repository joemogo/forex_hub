# Storage

This is an architectural summary of MOGO's data model. For the authoritative, field-by-field
reference (every key, every owning variable, every save/load function), see
[../docs/STORAGE_KEYS.md](../docs/STORAGE_KEYS.md) — this document explains the *shape* of the
model and why it's built this way, not every field.

## Persistence layer

`localStorage` only — no backend, no database, no sync. **24 keys** as of v12.0.0, verified to
match exactly between code and documentation with zero discrepancy. Each key belongs to exactly
one owning variable and is written by exactly one save path
([ADR-002](../docs/adr/ADR-002-isolated-strategy-and-feature-storage.md)) — no two keys are ever
merged, and no key is ever silently rebuilt from another key's data.

## Per-strategy isolation

JVM (12 keys, `fxhub_*`) and Alex (5 keys, `fxhub_alexg_*`) each own a fully separate state tree:
own account object, own journal array, own save/load function pair
(`save()`/`loadSaved()` vs. `saveAlexG()`/`loadAlexGSaved()`). Neither ever reads or writes the
other's keys — proven live on every Diagnostics run via a byte-identical-JSON swap test
(`alexGIsolationCheck()`, exposed through the Strategy SDK as `Services.isolationCheck()`).

`paperAccount` and a strategy's own account share the same top-level shape
(`{balance, openPositions, closedPositions}`) but materially different per-position schemas —
Alex's positions carry roughly 50 additional zone/setup/qualification/session/exit-forensics
fields that JVM's simpler position object doesn't have at all. Journal records diverge the same
way: JVM's carries `biasSummary`/`aoiSummary`/`triggerSummary`/`confluenceSummary`; Alex's carries
zone/reaction/psych-level context JVM has no equivalent for. Both feed into one shared,
defensively-defaulted normalized shape (`normalizeJournalRecord()`) for display — see
[DATA_FLOW.md](DATA_FLOW.md).

## Versioning fields (what actually guards compatibility today)

- **`fxhub_paper_version`** — a monotonic counter guarding `fxhub_paper` against a stale browser
  tab silently overwriting newer persisted data (`savePaperAccountGuarded()`).
- **`RULES_ALEXG.ruleVersion`** (`alex_g_sr_v1`) — frozen the moment any trade references it. Any
  future rule/config change mints a **new** version string; the old one is never mutated in place.
  This is the literal backbone the Strategy SDK's versioning model generalizes — see
  [STRATEGY_SDK.md](STRATEGY_SDK.md#versioning).
- **`CHART_DRAWING_SCHEMA_VERSION`** — stamped on every drawing record; not yet read/enforced
  anywhere else (a forward-compat placeholder).

There is **no generic `schemaVersion`** on `paperAccount`, a strategy's own account,
`journalEntries`, a strategy's own journal, `scanData`, or `academyProgress` — only the two fields
above and the chart-drawing stamp exist today.

## Explicit backward-compatibility invariants

These are enforced by code comments and, in several cases, by dedicated fixtures — not just
convention:

1. `RULES_ALEXG.config` is frozen — a behavior change requires a new `ruleVersion`, never an
   in-place edit.
2. `paperAccount`/`fxhub_paper` has exactly one writer path (`commitPaperLedger()` →
   `savePaperAccountGuarded()`) — this was itself the subject of a prior incident (see
   [../docs/INCIDENTS.md](../docs/INCIDENTS.md)) and is now a hard rule.
3. `paperResetHistory`, `tradeNotes`, and `paperReconciliationAudit` are deliberately never merged
   into the stores they annotate.
4. A journal close-update mutates the existing OPEN record in place — never replaces or
   recomputes entry-time fields.
5. Academy lesson ids are derived from `schoolId + moduleIndex`; a School rename (Track → School,
   v11.4.0) kept the five original school ids byte-identical specifically so every previously
   stored `completedLessonIds` entry keeps resolving correctly with zero migration.

## Why this matters for the Strategy Registry/SDK

The Registry/Manifest/Services layer introduced in v12.0.0 (see
[STRATEGY_REGISTRY.md](STRATEGY_REGISTRY.md)) is pure in-memory JavaScript — it holds *references*
to existing state, never a copy and never a new persisted shape. Registering ALEX added **zero**
new `localStorage` keys, and this is mechanically verified by a dedicated fixture. This was a
deliberate design constraint, not an accident: it's what makes the framework provably zero-drift
without any data migration, for this release and (by the same pattern) for any future strategy
registration.

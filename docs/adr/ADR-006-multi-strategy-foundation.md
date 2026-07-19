# ADR-006: Multi-Strategy Foundation (v12.2.0)

## Status

**Accepted and implemented in v12.2.0.** Approved with one required revision incorporated before
implementation began: display labels (`strategyLabel`) must not be treated as the permanent
identity of a strategy-owned record. This revision added a stable `strategyId` field, a 3-tier
resolution order, and explicit non-JVM-defaulting rules for unknown records. All seven identified
seams were generalized, verified with 30 new fixtures plus a fixture-only synthetic third
strategy, zero protected-function/constant drift, and live browser verification — see
[RELEASE_NOTES.md](../RELEASE_NOTES.md#v1220--multi-strategy-foundation) and the `v12.2.0`
`APP_VERSION_LOG` entry in `index.html` for the full as-shipped record. A pre-existing,
unrelated test fragility (four real-wall-clock-dependent fixtures in a different suite) was
discovered during this release's verification and is tracked as a documented follow-up in
[TESTING.md](../TESTING.md), not fixed under this ADR.

## Context

ADR-005 (v12.0.0/v12.1.0) built a `STRATEGY_REGISTRY`/Manifest/Services boundary and proved it
twice — once for ALEX, once for JVM — explicitly framing this as validating a *contract*, not
finishing the *scaling problem*. That scaling problem is still open. A direct audit of every
seam ADR-005 touched shows they were generalized from "hardcode ALEX" to "hardcode ALEX **and**
JVM by id," not to "iterate whatever is in the registry":

| Seam | File:line (approx.) | Current shape |
|---|---|---|
| Unified journal build | `getUnifiedJournalRecords()` | Two hardcoded branches, one per strategy id |
| Dashboard P&L/win-rate tiles + running-trades table | `renderDashboard()` ~12360 | Two hardcoded `getStrategyServices('current_strategy')` / `getStrategyServices('alex_g_sr_v1')` calls |
| Panel-open hook | `showPanel()` ~12297, ~12304 | Two hardcoded `if(name==='paper')`/`if(name==='alexg')` blocks, each with its own `getStrategyServices(id)` call |
| Developer Mode card visibility | `applyDeveloperModeVisibility()` ~10559 | Two hardcoded `getStrategyManifest(id)` calls, one per card |
| Mini-journal inspector card resolution | `renderMiniJournal()` 9744 | `strategyLabel==='ALEX' ? ... : 'paperTradeInspectorCard'` ternary |
| Journal strategy badge color | `journalStrategyBadge()` 9661 | `r.strategyLabel==='ALEX' ? purple : blue` ternary — **a third strategy silently renders JVM's own color, not a new one** |
| Strategy Center tabs/content | `renderRules()`/`setStrategyCenterTab()` ~11398 | Two hardcoded DOM ids (`scTabMogo`/`scTabAlex`, `scMogoContent`/`scAlexContent`), ALEX permanently wired to a static "Coming Soon" render |

Every one of these was **known and explicitly disclosed** as deferred scope in the v12.1.0
changelog ("the optional, deferred Release 3 scope named in ADR-005"). This ADR is that Release 3.

Adding TJR, ICT, Silver Bullet, or any further strategy today would require finding and manually
editing all seven of these locations again, by hand, per strategy — exactly the risk ADR-005's
own Context section named and asked future work to close.

## Decision

### 0. Record identity is `strategyId` (a registry id), never `strategyLabel` alone

A direct audit of the existing journal-record builders found the raw record already carries a
field close to what's needed: `buildJVMJournalOpenRecord()` sets `strategy:'current_strategy'`
and `buildAlexJournalOpenRecord()` sets `strategy:'alex_g_sr_v1'` — both are already exactly the
registry `id` value, just under the field name `strategy` rather than `strategyId`, and not yet
treated as the primary lookup key anywhere. `normalizeJournalRecord()` already does
`strategy:raw.strategy||storeStrategy` — meaning every record normalized through the existing
per-store call path (`journalEntries` via `'current_strategy'`, `alexGJournalEntries` via
`'alex_g_sr_v1'`) already resolves to a correct id today, since `storeStrategy` itself is supplied
by which array the record physically lives in and is never ambiguous.

This ADR makes that identity explicit and forward-looking rather than silently relying on which
array a record happens to live in:

- **New records** (both JVM's and ALEX's journal builders) additionally set `strategyId` equal to
  the same value already written to `strategy` (`'current_strategy'` / `'alex_g_sr_v1'`) — a pure
  addition, `strategy` is untouched and every existing reader of it keeps working.
- **`normalizeJournalRecord()`** gains one additive output field:
  `strategyId: raw.strategyId || raw.strategy || storeStrategy` — preferring an explicit
  `strategyId` if present, falling back to the legacy `strategy` field, falling back to the
  caller's own store context. No existing output field changes value.
- **Existing persisted records are never destructively rewritten.** No migration pass touches
  `fxhub_journal`/`fxhub_alexg_journal` on disk. A pre-v12.2.0 record with only `strategyLabel`
  (or only the legacy `strategy` field) keeps working exactly as it does today, resolved at read
  time by the mechanism below — the same non-destructive precedent `journalEntryId`'s v10.0
  backfill already established for this codebase.

**Resolution order, for any code that needs to go from a record to its registry entry** (a new
helper, `resolveStrategyEntryForRecord(record)`):

1. `record.strategyId` — exact match via `findStrategyEntry(id)`. Primary, stable, rename-proof.
2. `record.strategyLabel` — **legacy compatibility only** — via `findStrategyEntryByLabel(label)`.
3. Neither resolves → return `null`. Every caller must render a safe, neutral, non-strategy-specific
   fallback in this case — **never silently default to JVM's (or any other specific strategy's)
   styling.** This is the failure mode this revision exists to prevent.

`findStrategyEntryByLabel(label)` (`STRATEGY_REGISTRY.find(e=>e.manifest.label===label)`) is
explicitly documented in its own source comment as a **legacy compatibility helper, not the
primary long-term lookup mechanism** — it exists only so pre-`strategyId` records keep resolving
without a destructive rewrite, and it is expected to matter less over time as `strategyId`
propagates through new records. New code should prefer `record.strategyId` /
`resolveStrategyEntryForRecord()` wherever a record is available; `findStrategyEntry(id)` remains
the primary lookup when only a bare id is on hand (e.g. `showPanel()`'s registry-level lookups,
which never touch a record at all).

**Why a label-only record can legitimately become unresolvable**: if a strategy's
`manifest.label` is ever renamed in a later release, a record carrying only the *old* label no
longer matches the *current* registry entry's label and correctly falls through to the unknown
fallback (§0 rule 3) rather than silently mismatching or crashing. A record carrying `strategyId`
is immune to this — the id is never a display string and is never renamed. This is the concrete
illustration of "don't make display labels the permanent identity."

**UI ordering.** Every generalized seam renders registry entries in `STRATEGY_REGISTRY` array
order — first entry first, no separate sort/priority field. Today's array is
`[JVM_MANIFEST+services, ALEX_MANIFEST+services]`, so JVM continues to render before ALEX
everywhere (Dashboard tile order, Strategy Center tab order, Developer Mode card order) with zero
visual change. A future strategy is appended to the array's end and renders after JVM/ALEX unless
someone deliberately reorders the literal — no new ordering mechanism is introduced, matching this
project's stated bias against speculative configurability.

### 1. Generalize every seam from "hardcode each id" to "iterate `STRATEGY_REGISTRY`"

No seam listed above gets a third hardcoded branch. Each is rewritten once, this release, to loop
over `STRATEGY_REGISTRY` generically. Concretely:

- **`getUnifiedJournalRecords()`**: replace the two fixed branches with one loop building an array
  of `{manifest, services}` pairs and concatenating each strategy's normalized journal records.
- **`renderDashboard()`**: replace the two hardcoded tile/table blocks with one loop that renders
  one P&L/win-rate tile and contributes one section of the running-trades table per registry
  entry with `capabilities.paperTrading`. The Dashboard's CSS grid must tolerate a variable tile
  count without a layout regression for today's fixed 2 — this is a visual verification item for
  implementation, not a design change to the grid's own sizing rules.
- **`showPanel()`**: replace the two `if(name===...)` blocks with one lookup: find the registry
  entry whose `manifest.panelId===name`, call `.services.onOpen()` if present. Falls back to
  today's literal `if` behavior only if the registry is ever empty (matching ADR-005's existing
  graceful-fallback rule).
- **`applyDeveloperModeVisibility()`**: loop over the registry, toggle each entry's
  `manifest.devToolsCardId` element.
- **`renderMiniJournal()`**: replace the `strategyLabel==='ALEX'` ternary with
  `resolveStrategyEntryForRecord({strategyLabel})?.manifest.inspectorCardId`. If unresolved, this
  falls back to the existing shared, strategy-neutral `'tradeInspectorCard'` DOM id (already used
  elsewhere for records with no specific per-strategy inspector) — **not** either JVM's or ALEX's
  own card id. This also collapses JVM's own already-correct-but-separately-written branch into
  the same lookup, net-simplifying the function.
- **`journalStrategyBadge()`**: add a `badgeColor` field to the Manifest shape (see §2) and
  resolve via `resolveStrategyEntryForRecord(r)?.manifest.badgeColor`. Every registered strategy
  gets a real, distinct, intentional color. An unresolved record (§0 rule 3) renders a new,
  dedicated neutral/gray "Unknown" badge color — **not** JVM's blue, not any registered
  strategy's color — so an orphaned or unregistered-strategy record is visibly distinguishable
  from every real strategy, rather than silently misrepresented as JVM.
- **Strategy Center**: replace the two-DOM-id tab scheme with one generated tab per registry
  entry with a truthy `manifest.capabilities.strategyCenterContent` (a **new**, explicit
  capability flag — not inferred from anything else, since "has a real methodology page" isn't
  derivable from existing fields). A registry entry without this capability renders today's exact
  "Coming Soon" stub, unchanged. JVM's existing hero/thesis/architecture/etc. render functions
  become the content for JVM's generated tab, unchanged in every internal render function; only
  the tab-selection/DOM-id scaffolding around them is generalized.

`findStrategyEntryByLabel(label)` is a new, small helper (`STRATEGY_REGISTRY.find(e=>e.manifest.label===label)`)
— the missing piece today's `findStrategyEntry(id)` doesn't cover, since journal records store the
display `strategyLabel` ('JVM'/'ALEX'), not the manifest `id` ('current_strategy'/'alex_g_sr_v1').

### 2. Extend the Manifest shape — additively, no existing field changes

Two new fields, both required for every registry entry going forward:

- `badgeColor` (CSS color value) — closes the journal-badge gap above.
- `capabilities.strategyCenterContent` (boolean) — closes the Strategy Center gap above.

Existing `capabilities` keys (`scanning`, `paperTrading`, `automation`, `journal`, `statistics`,
`alerts`, `replay`, `backtesting`, `aiReview`, `aiCoaching`, `reports`, `academyContent`,
`diagnostics`, `settings`) are unchanged in meaning and requirement. `JVM_MANIFEST`/`ALEX_MANIFEST`
both gain the two new fields this release (JVM: real color + `strategyCenterContent:true`; ALEX:
real color + `strategyCenterContent:false`, matching its current "Coming Soon" state honestly).

No `Services` contract change is proposed. ADR-005's existing rule — every optional Service must
degrade gracefully to prior hardcoded behavior when absent — is unchanged and re-verified this
release for the two now-generalized seams above (mini-journal, badge, Strategy Center) exactly
like every prior seam already has fixtures for.

### 3. A synthetic third registry entry is how "genuinely N-strategy" gets proven

Since MOGO has no third real strategy yet, this release's test suite adds one **fixture-only**,
never-shipped-to-production synthetic manifest/services pair (e.g. `id:'test_strategy_zzz'`) to a
copy of the registry inside the offline harness, and proves every generalized seam renders it
correctly alongside JVM and ALEX with zero change to either's own output. This is the only way to
mechanically prove N>2 capability rather than just re-proving N=2 with nicer code — the same
principle ADR-005 itself used ("missing/unregistered strategy degrades gracefully" fixtures), run
in the opposite direction (an *extra*, present strategy renders correctly).

**Required fixture coverage** for this release, at minimum:

1. A newly created JVM record carries `strategyId:'current_strategy'`.
2. A newly created ALEX record carries `strategyId:'alex_g_sr_v1'`.
3. A legacy JVM record with only `strategyLabel:'JVM'` (no `strategyId`, no `strategy`) resolves
   correctly via the store-context fallback in `normalizeJournalRecord()`.
4. A legacy ALEX record with only `strategyLabel:'ALEX'` resolves the same way.
5. **Display-label rename resilience**: given a record with a real `strategyId`, changing the
   registry's `manifest.label` for that entry does not affect resolution (still resolves via id);
   given a label-only legacy record whose label no longer matches any current registry entry
   (simulating a post-rename orphan), it safely falls through to the unknown fallback rather than
   mismatching or throwing.
6. An unknown/unregistered-strategy record (neither `strategyId` nor `strategyLabel` resolves to
   any registry entry) renders the dedicated neutral badge color (not JVM's, not ALEX's) and the
   shared generic inspector card id (not JVM's, not ALEX's) at every seam that touches records.
7. The fixture-only synthetic third strategy renders correctly, in registry order, at all seven
   seams simultaneously with JVM and ALEX, with zero change to either's own output.

### 4. New-strategy onboarding is now a fixed, mechanical checklist

Once this release ships, adding a real future strategy (TJR or otherwise) requires exactly:

1. Its own state variable + `localStorage` key + save/load pair, following the ADR-002 isolation
   pattern ALEX/JVM already use (own account object, own journal array, own auto-trading state).
2. Its own engine functions, added to `PROTECTED_FUNCTIONS` in `regression-baseline-tools.py`
   once frozen (hand-curated review, unchanged from today's process).
3. One `<StrategyName>_MANIFEST` object and one `<StrategyName>_SERVICES` object, following the
   exact shape ALEX/JVM's already do, including the two new fields from §2.
4. One new entry appended to `STRATEGY_REGISTRY`.
5. **Zero edits** to `getUnifiedJournalRecords()`, `renderDashboard()`, `showPanel()`,
   `applyDeveloperModeVisibility()`, `renderMiniJournal()`, `journalStrategyBadge()`, or Strategy
   Center's tab scaffolding — this is the actual deliverable of this ADR, and every future
   strategy's onboarding release should be able to cite this list as proof it didn't have to
   touch any of them.

### Explicit non-goals

- **No dynamic or pluggable code loading.** MOGO remains a single static HTML file with no build
  step; every strategy's code ships compiled into that one file and is registered at top-level
  script execution, exactly like ALEX/JVM today. This ADR generalizes *consumption* of the
  registry, not *how strategies are shipped*.
- **No standardized internal engine pipeline**, unchanged from ADR-005 — JVM's numeric confluence
  model and ALEX's categorical zone/touch model remain legitimately different internal shapes;
  only the boundary the core app calls generically is touched.
- **No sandboxing, permissioning, or marketplace/discovery mechanism** — out of scope for an
  internal, developer-time extensibility pattern.
- **Building TJR/ICT/Silver Bullet's actual trading logic is not part of this release.** This ADR
  only proves the framework can hold a genuine third strategy; a separate, later release
  implements one using the now-generalized framework, following the checklist in §4.

## Rationale

- Every seam identified above was already flagged, by name, as deferred Release-3 scope in the
  v12.1.0 changelog — this is closing a known, disclosed gap, not discovering a new one.
- None of the seven seams touch a `PROTECTED_FUNCTIONS` entry — the same reason ADR-005 itself
  gave for why its migrations could be mechanically proven driftless applies unchanged here.
- Generalizing to "iterate the registry" instead of "hardcode a third id" is strictly less code
  than adding a third hardcoded branch would have been at each seam — this is a simplification
  under the project's own stated bias against premature abstraction, not an added layer: the
  abstraction (the registry array) already exists and is already iterated conceptually by two
  hand-written branches; this ADR just makes the iteration real.

## Consequences

- `regression-baseline-tools.py`'s `PROTECTED_FUNCTIONS`/`PROTECTED_CONSTANTS` stay hand-curated
  and strategy-specific, unchanged in process — a new strategy's protected functions are reviewed
  and added the same way ALEX's/JVM's were.
- `docs/STORAGE_KEYS.md`, `docs/ARCHITECTURE.md`, and this ADR itself are the durable record of
  the seam list — any future seam discovered to still be hardcoded-by-id should be treated as a
  gap in *this* ADR's coverage, not a new one-off fix.
- The two new Manifest fields (`badgeColor`, `capabilities.strategyCenterContent`) become
  required for all future registry entries; `docs/ARCHITECTURE.md`'s Strategy Framework section
  should be updated to state the full, current Manifest shape once this ships.
- A future strategy's own onboarding release can be scoped, reviewed, and estimated directly
  against the §4 checklist — making "how much work is a new strategy" a answerable, bounded
  question rather than an open-ended seam hunt.

# Strategy SDK

The SDK is the contract every strategy module must satisfy to register with MOGO. It governs only
the **boundary** between a strategy and the core app — never a strategy's internal pipeline (see
[SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) for why).

A strategy module is split into two parts:

- **Manifest** — static, lightweight, computed-performance-free metadata.
- **Services** — dynamic behavior, exposed as thin references to the strategy's own existing
  functions/state. Never new trading logic.

## Manifest

| Field | Purpose |
|---|---|
| `id` | Unique key. For Alex, read directly from `RULES_ALEXG.ruleVersion` rather than restated, so it can never drift out of sync with what's already stamped on every trade/journal record. |
| `family` | Groups related variants for discovery/UI (e.g. `alex_g_sr`) — see [Versioning](#versioning). |
| `version` | Display label (e.g. `v1`). |
| `label` | Short display name (e.g. `ALEX`). |
| `fullName`, `description` | Longer display strings. |
| `author`, `ownership` | `internal` today; reserves room for a future `community` tier. |
| `status` | `active \| experimental \| deprecated`. |
| `trustLevel` | `verified` today; reserves room for a future untrusted/community tier — **not yet enforced**, see [AI_ROADMAP.md](AI_ROADMAP.md) and Known Limitations below. |
| `capabilities` | Describes what the strategy's engine actually does today (`scanning`, `paperTrading`, `automation`, `journal`, `statistics`, `alerts`, `replay`, `backtesting`, `aiReview`, `aiCoaching`, `reports`, `academyContent`, `diagnostics`, `settings`) — booleans, reported honestly rather than aspirationally. A capability being `true` does not imply a Services hook is wired for it this release; it describes the engine, not the integration. |
| `dependencies` | Named services the strategy needs (e.g. `oandaPricing`, `candleData`, `browserStorage`, `sessionData`). |
| `dna` | Declared, author-provided descriptive metadata (style, difficulty, market type, preferred sessions, ideal/avoid conditions, strengths/weaknesses). **Deliberately excludes** empirical claims (avg hold time, typical R:R, trading frequency) — those must be computed from real performance data, never hand-authored, per [ADR-004](../docs/adr/ADR-004-read-only-analytics-principle.md). |
| `panelId`, `devToolsCardId`, `inspectorCardId` | DOM/routing ids the core app resolves through the Manifest instead of a hardcoded literal. |
| `academySchoolId` | Optional cross-link to a MOGO Academy School, if one exists for this strategy. |
| `release` | Release-metadata stamp (e.g. `registeredInVersion`). |

The Manifest must never contain a computed value (`balance`, `winRate`, `pnl`, etc.) — that always
belongs behind a Services accessor, computed on demand.

## Services

| Method | Required? | Purpose |
|---|---|---|
| `getAccount()` | Required | Returns the strategy's own live account/state object — a reference, not a copy. |
| `getJournal()` | Required | Returns the strategy's own live journal array — a reference, not a copy. |
| `normalize(raw)` | Required | Maps a raw journal record into the shared unified-journal shape (delegates to the existing `normalizeJournalRecord()`). |
| `onOpen()` | Optional | Fires when the strategy's panel is opened (delegates to the strategy's existing init function). |
| `isolationCheck()` | Optional | Returns `{name, pass, detail}` for the Diagnostics tab. |
| `health()` | Optional | One of `ready \| loading \| offline \| disabled \| updating \| error`. Reserved; not yet dynamic for any strategy, not yet surfaced in any UI. |
| `start()` / `stop()` | Optional | Polling lifecycle hooks. Not yet wired for Alex — its polling loop is still self-managed independently of the SDK. |
| `buildOpenRecord()` / `buildCloseRecord()` | Optional | Journal record builders. Not yet wired for Alex — no target seam calls them generically yet. |
| `getContextSnapshot()` / `getExplanation(tradeId)` | Optional | AI extension points — see [AI_ROADMAP.md](AI_ROADMAP.md). |
| `buildWeeklySummary()` | Optional | Reporting extension point. Falls back to a generic summary derived from `computePerformance()` when absent. |
| `computePerformance()` | Optional (aspirationally required) | A dedicated, honest, sample-gated statistics function. **Alex does not have one yet** — a disclosed, pre-existing gap, not fixed by the framework itself. |
| Settings/playbook access | Optional | Not yet wired for Alex; `RULES_ALEXG.config`/`experimentalParams` exist internally but are not exposed through Services. |

**A missing optional Service must always degrade gracefully** — the core app falls back to its
pre-framework hardcoded behavior rather than throwing or silently no-op'ing. This is tested
explicitly (six dedicated "fails safely when unregistered" fixtures in `tests/v120`).

## Versioning

Each concrete strategy implementation is version-locked by construction: `RULES_ALEXG.ruleVersion`
(`alex_g_sr_v1`) is frozen forever once any trade references it — any future rule change requires
a **new** `ruleVersion`, never an in-place edit (an invariant that predates the SDK and the SDK
simply generalizes). The Manifest's two-axis model:

- **`family`** groups variants for discovery (e.g. `alex_g_sr`, `jvm`) — not unique on its own.
- **`id`** (the `ruleVersion` pattern) is the actual unique registry key — `alex_g_sr_v1`,
  `alex_g_sr_v2`, `jvm_conservative`, `jvm_aggressive`. Each is a separate registry entry, never a
  mutation of an existing one, so historical trades against an older version stay fully readable
  and never get silently reinterpreted.

`status` (`active`/`experimental`/`deprecated`) is pure metadata filtering — it does not delete
anything or require special-case core-app code.

## Known limitations of the SDK as implemented today

- Both ALEX and JVM are registered as of v12.1.0 (Release 2). JVM's registration required zero
  SDK extensions — every field/method it needed already existed from Release 1, confirmed by a
  field-by-field pre-implementation audit, not assumed. `computePerformance()` is JVM's first
  real use of a slot the SDK reserved but ALEX couldn't exercise (ALEX has no live-performance
  function). A genuine third strategy remains the next test of the contract.
- `trustLevel`/`ownership` fields exist but are not enforced anywhere — there is no sandboxing or
  validation of strategy code today. This matters only if/when third-party strategies are ever
  allowed to execute in the same page; explicitly out of scope until that's a concrete plan (see
  [AI_ROADMAP.md](AI_ROADMAP.md) for the same caveat applied to AI features).
- `PROTECTED_FUNCTIONS`/`PROTECTED_CONSTANTS` in `regression-baseline-tools.py` remain a
  deliberately hand-curated flat list, not auto-generated from the Registry — preserving the
  reviewed-before-frozen property that makes the regression baseline trustworthy.

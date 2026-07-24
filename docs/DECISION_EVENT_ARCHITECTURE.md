# Decision Event Schema & Observability Foundation

**Status:** PROGRAM-001 Phase 2A, shipped in v12.5.0. Infrastructure only — no trading behavior
change. This document is the source of record for the schema, reason-code registry, evidence
model, identifier rules, immutability guarantee, and memory limits; the in-code
`APP_VERSION_LOG` entry is the condensed summary, this file is the full detail.

## Purpose

This is the foundation every future MOGO learning/observability system will build on: a
universal, versioned Decision Event that any strategy (JVM, ALEX, TJR, or a future strategy) can
eventually emit through, at every stage of its decision lifecycle — from a scan starting, through
a candidate being observed, evaluated, rejected or approved, to a trade opening, failing to open,
or closing. Phase 2A builds the schema, the registries, and the in-memory bus; it does **not**
yet emit most of these events, and does **not** analyze, log candidates, or judge trade quality —
that is explicitly reserved for later phases (see "Future Phase 2B" below).

## Schema — `mogo.decision-event.v1`

`DECISION_EVENT_SCHEMA_VERSION='mogo.decision-event.v1'` (`index.html`). `createDecisionEvent(fields)`
builds one event object with every one of the following fields always present — a value from
`fields` if the caller supplied one, otherwise an explicit `null`. Nothing is ever fabricated: no
field is silently `0`, `''`, `false`, or omitted when it isn't known.

| Field | Notes |
|---|---|
| `eventId` | Assigned by `createDecisionEvent()` via `generateDecisionEventId('EVT')`. |
| `schemaVersion` | Always `'mogo.decision-event.v1'`. |
| `eventType` | One of the 13 supported types (see below). |
| `occurredAt` | When the real-world decision happened (caller-supplied, or `recordedAt` if not given). |
| `recordedAt` | When the event object was actually constructed — always set by `createDecisionEvent()` itself. |
| `strategyId`, `strategyVersion`, `baselineId`, `applicationVersion` | Strategy/build identity. `applicationVersion` is always `APP_VERSION`, filled automatically. |
| `scanId`, `candidateId`, `tradeId` | Lifecycle identifiers (see Identifiers below). |
| `pair`, `direction`, `timeframe`, `session` | Market/setup context. |
| `source`, `engineMode`, `stage`, `decision` | Where/how the event was produced and what was decided. |
| `reasonCode`, `reasonText` | See Reason Code Registry below. |
| `ruleId`, `ruleVersion`, `ruleResult` | Per-rule evaluation detail (future use — `RULE_EVALUATED`). |
| `severity` | Free-form for now (e.g. `'ERROR'` on `ENGINE_ERROR`); not yet a closed enum. |
| `marketTimestamp`, `marketDataReference` | Provenance for whatever market data informed the event. |
| `context`, `metrics`, `diagnostics` | Free-form payload objects, subject to the payload-size limit below. |
| `parentEventId`, `correlationId` | Causal/lifecycle linkage. |
| `sequenceNumber` | **Never** set by `createDecisionEvent()` — only `emitDecisionEvent()` assigns it, and only to an event that passes validation. |
| `evidenceCompleteness` | One of `COMPLETE`/`PARTIAL`/`MINIMAL`/`UNKNOWN`; defaults to `UNKNOWN`, never a guessed `COMPLETE`. |
| `unknownFields` | Array, defaults to `[]`; a place for a future caller to record field names it knows it can't populate. |

### Supported event types

All 13 required types are defined in `DECISION_EVENT_TYPES` (frozen): `SCAN_STARTED`,
`SCAN_COMPLETED`, `SETUP_OBSERVED`, `CANDIDATE_CREATED`, `RULE_EVALUATED`, `CANDIDATE_REJECTED`,
`CANDIDATE_APPROVED`, `TRADE_OPEN_REQUESTED`, `TRADE_OPENED`, `TRADE_OPEN_FAILED`,
`TRADE_CLOSED`, `DATA_UNAVAILABLE`, `ENGINE_ERROR`. **Only `SCAN_STARTED`, `SCAN_COMPLETED`, and
`ENGINE_ERROR` are actually emitted as of v12.5.0** — the rest exist so a later phase can start
emitting them without a breaking schema change.

## Reason Code Registry

`REASON_CODE_REGISTRY` is the single source of truth for valid `reasonCode` values, across 14
categories (`REASON_CODE_CATEGORIES`): `DATA`, `SESSION`, `STRUCTURE`, `BIAS`, `AOI`,
`CONFLUENCE`, `ENTRY`, `RISK`, `SPREAD`, `EXECUTION`, `STATE`, `CONFIG`, `SYSTEM`, `UNKNOWN`.
`validateDecisionEvent()` rejects any `reasonCode` not present in this registry as an exact key —
this is a deliberate design choice: codes are validated against a closed, centralized set, not a
loose "starts with a category prefix" convention, so "codes must remain stable" is actually
enforced. A future phase adds a new code to this registry first, then uses it — never the
reverse. `reasonText` is independent, free-form human wording on an individual event; it is
**never** validated against any list, so a caller can always explain itself in plain language
without needing a new registry entry — but analytics and any future automated logic must depend
only on `reasonCode`, never parse `reasonText`.

Seeded codes as of v12.5.0 (illustrative coverage per category, not exhaustive —
`DATA_CANDLES_UNAVAILABLE`, `DATA_PRICE_UNAVAILABLE`, `SESSION_OUTSIDE_ALLOWED_WINDOW`,
`SESSION_OUTSIDE_PREFERRED_DAY`, `STRUCTURE_AOI_NOT_VALIDATED`, `STRUCTURE_ZONE_ALREADY_BROKEN`,
`BIAS_CONFLICT`, `BIAS_SPLIT`, `AOI_TOO_FAR`, `AOI_INSUFFICIENT_TOUCHES`,
`CONFLUENCE_BELOW_THRESHOLD`, `ENTRY_SIGNAL_NOT_PRESENT`, `ENTRY_RATIO_BELOW_MINIMUM`,
`RISK_OPEN_POSITION_LIMIT`, `RISK_ZERO_STOP_DISTANCE`, `SPREAD_UNAVAILABLE`, `SPREAD_EXPANDED`,
`EXECUTION_SPREAD_UNAVAILABLE`, `EXECUTION_LEDGER_REJECTED`, `STATE_ALREADY_TRADED_TODAY`,
`STATE_SIGNAL_ALREADY_DECIDED`, `STATE_SIGNAL_STALE`, `CONFIG_AUTOMATION_DISABLED`,
`SYSTEM_UNEXPECTED_ERROR`, `UNKNOWN_NOT_RECORDED`).

## Evidence Model

Two distinct, complementary concepts:

- **`EVIDENCE_COMPLETENESS_LEVELS`** (`COMPLETE`/`PARTIAL`/`MINIMAL`/`UNKNOWN`) — the *overall*
  level for one event, set on the event itself.
- **`EVIDENCE_FIELD_PROVENANCE`** (`OBSERVED`/`DERIVED`/`UNAVAILABLE`/`UNSAFE_TO_RECONSTRUCT`/
  `FUTURE_WORK`) — a taxonomy a future phase uses to tag *why* an individual field is what it is,
  once real per-field evidence tracking is built (not yet implemented in Phase 2A — this phase
  only defines the taxonomy).

**JVM and ALEX are never forced into artificial parity.** JVM has no per-trade rule snapshot and
no MAE/MFE tracking; ALEX has both. A JVM event honestly reporting lower evidence completeness
than an equivalent ALEX event is correct behavior, not an inconsistency to paper over.

## Identifiers

`generateDecisionEventId(prefix)` returns `` `${prefix}|${Date.now()}-${counter}` ``, where
`counter` is a single monotonically-increasing in-memory value. Timestamp alone cannot guarantee
uniqueness (two calls in the same millisecond would collide); combining it with the counter does
— proven directly by generating 200 IDs in a tight loop and confirming 200 unique values.
`sequenceNumber` is assigned only inside `emitDecisionEvent()`, only to an event that has already
passed `validateDecisionEvent()` — a rejected/invalid event never consumes a sequence number, so
the retained log's sequence numbers are always contiguous and reflect true emission order among
*accepted* events.

## Immutability

`emitDecisionEvent()` is the **only** function that ever appends to the in-memory log. It
`Object.freeze()`s the event object immediately before pushing it, so no caller holding a
reference to that event — including one obtained from `getDecisionEvents()` — can ever rewrite
one of its fields afterward; this is enforced by the JS engine, not merely a documented
convention. `getDecisionEvents()` additionally returns a defensive shallow copy of the log array
itself, so pushing/splicing/reordering the returned array can never affect the real log.
`clearDecisionEvents()` wipes the *entire* log — a distinct operation from "rewriting an event":
it never modifies any individual retained event, it only clears the whole append-only window
(used for dev/test reset, and functionally equivalent to what a real page reload already does,
since nothing here is persisted).

## Memory Limits

The entire event log (`decisionEventLog`) and validation-failure log
(`decisionEventValidationFailures`) are plain in-memory arrays, each bounded to
`DECISION_EVENT_MAX_LOG_SIZE=500` entries (oldest dropped first once full). A single event's
serialized JSON size is capped at `DECISION_EVENT_MAX_PAYLOAD_CHARS=8000` characters —
`validateDecisionEvent()` rejects anything larger rather than silently truncating it.

**Nothing in this layer is persisted to `localStorage` or anywhere else.** This is a deliberate
Phase 2A mandate, not an oversight: the entire Decision Event log is gone on every page reload.
This is a real, disclosed limitation (see below), not a bug.

## Failure Isolation

`emitDecisionEvent()` wraps its entire body in a try/catch that can never rethrow — an internal
bug in this brand-new layer (a malformed input, a circular-reference payload, anything) always
returns `{ok:false,errors:[...]}` rather than throwing into the caller. This is proven directly
with a deliberately circular `context` object in the test suite, not just asserted by code
reading. This matters because the only two places this layer is wired into real trading code —
`scanAll()` and `alexGLivePollTick()` — must never have their own scanning/trading behavior
interrupted by an observability bug.

## Instrumentation (what's actually wired, v12.5.0)

Only `SCAN_STARTED`, `SCAN_COMPLETED`, and `ENGINE_ERROR` are emitted, from exactly two call
sites — the genuine outer scan-tick boundaries for each engine:

- **JVM: `scanAll()`** (`index.html`) — confirmed **not** a protected function (cross-checked
  directly against `regression-baseline-tools.py`'s `PROTECTED_FUNCTIONS`, and against Phase 1's
  `BASELINE_JVM_FUNCTIONS` mirror of that same list).
- **ALEX: `alexGLivePollTick()`** (`index.html`) — confirmed **not** a protected function, same
  cross-check against `BASELINE_ALEX_FUNCTIONS`.

Both functions were edited **only** by wrapping their entire existing, unreordered body in a
try/catch, with an `emitDecisionEvent()` call added at the very start (`SCAN_STARTED`), one at
the very end of the success path (`SCAN_COMPLETED` — `alexGLivePollTick()` has an early-return
path when automation is off, so it has two `SCAN_COMPLETED` call sites, one per return path), and
one in the catch block (`ENGINE_ERROR`, followed by `throw e` to preserve the exact original
error-propagation behavior — nothing here swallows a real error that would previously have
surfaced). **No protected rule logic is touched or instrumented anywhere in this release** —
`checkAutoTrades`, `evaluateLiveTrigger`, `scoreConfluence`, `bestConfluence`, `computeAOI`,
`detectSignals`, `getBias`, `getSession`, `pipSize`, `pipValuePerLot`, and every `alexG*`
protected function are all still called from inside `scanAll()`/`alexGLivePollTick()` completely
unmodified, in the exact same order as before.

## Developer Mode Preview

`renderDecisionEventDiagnostics()` populates a small Diagnostics card (Developer-Mode-gated,
wired into the same three trigger points as the Baseline Registry card: the Diagnostics panel
load, the Developer Mode toggle, and its own Refresh button) showing: Schema Version, Event Bus
Status, Events in Memory, Last Event, Validation Failures, and Persistence Status (always "NOT
PERSISTED"). No dashboard, no charts, no Strategy Center changes.

## Known Limitations

- **Memory-only, by design.** The event log does not survive a page reload. This is the explicit
  Phase 2A mandate ("no persistent storage unless absolutely required") — persistence, if ever
  needed, is an explicit future decision requiring its own storage-key/retention/migration/
  corruption-handling/rollback proposal, not an assumption baked in here.
- **`SCAN_COMPLETED`/`ENGINE_ERROR` from `scanAll()`/`alexGLivePollTick()` could not be exercised
  end-to-end in the offline JXA test harness**, for the same documented, permanent reason
  `closePaperPosition()`/`alexGCloseLivePosition()` couldn't be in earlier releases (see
  `docs/TESTING.md`): both functions have a real internal `await` this harness cannot resolve.
  `SCAN_STARTED` specifically **was** proven with real execution (it's each function's literal
  first statement, before either function's first `await`); the remainder was verified live in a
  real browser instead (see the pre-commit report for this release).
- **Reason codes are a fixed, curated set for now**, not exhaustive — future phases will add
  codes to `REASON_CODE_REGISTRY` as real rule-evaluation logic starts emitting `RULE_EVALUATED`/
  `CANDIDATE_REJECTED` events with specific reasons.
- **Per-field evidence provenance (`EVIDENCE_FIELD_PROVENANCE`) is a defined taxonomy only** —
  nothing in Phase 2A actually tags an individual field with it yet, since no real candidate/rule
  evaluation exists yet to have fields worth tagging.

## Future Phase 2B (not started, not authorized by this release)

Phase 2A's own spec explicitly reserves the following for later, separately-authorized phases:
candidate/rejection logging, trade-failure analysis, missed-opportunity/counterfactual trades, a
market-context/regime engine, historical-candle retrieval, EMA/ATR/AOI reconstruction, an
Experiment Registry, shadow strategies, AI coaching, and any Trade Inspector or
`computeTiCompliance()` change. A natural Phase 2B would begin wiring `SETUP_OBSERVED`/
`CANDIDATE_CREATED`/`RULE_EVALUATED`/`CANDIDATE_REJECTED`/`CANDIDATE_APPROVED` from the actual
signal-detection/confluence-scoring layer (still without touching protected functions — likely by
wrapping their call sites the same way `scanAll()`/`alexGLivePollTick()` were wrapped here, not by
editing the protected functions themselves), and populating real `evidenceCompleteness`/
`EVIDENCE_FIELD_PROVENANCE` values once there is real per-candidate evidence to describe.

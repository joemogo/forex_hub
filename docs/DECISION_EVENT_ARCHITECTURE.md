# Decision Event Schema & Observability Foundation

**Status:** PROGRAM-001 Phase 2A (schema/bus, v12.5.0) plus Phase 2C Wave 1 (ALEX candidate
lifecycle instrumentation, v12.6.0). Infrastructure only — no trading behavior change in either
phase. This document is the source of record for the schema, reason-code registry, evidence
model, identifier rules, immutability guarantee, memory limits, and instrumentation coverage; the
in-code `APP_VERSION_LOG` entries are the condensed per-release summaries, this file is the full,
continuously-updated detail.

**JVM vs. ALEX coverage asymmetry (read this first):** JVM emits only `SCAN_STARTED`/
`SCAN_COMPLETED`/`ENGINE_ERROR`, exactly as it did in v12.5.0. ALEX additionally emits its full
candidate lifecycle as of v12.6.0. This is not an oversight or a temporary gap to be closed
symmetrically later — see "Why ALEX and not JVM" below. JVM and ALEX are deliberately never
forced into artificial observability parity.

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
`TRADE_CLOSED`, `DATA_UNAVAILABLE`, `ENGINE_ERROR`.

**As of v12.6.0:**
- **JVM** emits only `SCAN_STARTED`/`SCAN_COMPLETED`/`ENGINE_ERROR` — unchanged since v12.5.0.
- **ALEX** additionally emits `CANDIDATE_CREATED`, `RULE_EVALUATED`, `CANDIDATE_REJECTED`,
  `TRADE_OPEN_REQUESTED`, `CANDIDATE_APPROVED`, `TRADE_OPENED`, and `TRADE_OPEN_FAILED` — see
  "ALEX Candidate Lifecycle Instrumentation (Phase 2C Wave 1)" below.
- **Still never emitted, by anyone:** `SETUP_OBSERVED` (would require exposing ALEX's per-touch
  zone-engine rejection reasons, which are structurally discarded today — see Known Limitations)
  and `TRADE_CLOSED`/`DATA_UNAVAILABLE` (out of scope for this wave).

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

**Added in v12.6.0** (Phase 2C Wave 1, ALEX only): `CONFIG_BEFORE_ACTIVATION`,
`ENTRY_INVALID_ZONE_ROLE`, `ENTRY_INVALID_BROKEN_DIRECTION`, `ENTRY_UNSUPPORTED_SETUP_TYPE`,
`ENTRY_MOVED_TOO_FAR_FROM_SIGNAL`, `DATA_ATR_UNAVAILABLE`, `RISK_INVALID_STOP`,
`DATA_PIP_VALUE_UNAVAILABLE`. `RISK_OPEN_POSITION_LIMIT`, `EXECUTION_SPREAD_UNAVAILABLE`,
`STATE_SIGNAL_ALREADY_DECIDED`, `STATE_SIGNAL_STALE`, and `EXECUTION_LEDGER_REJECTED` were already
seeded in v12.5.0 and are now genuinely used, wired to real ALEX outcomes for the first time.

### ALEX construction-outcome mapping (`ALEXG_CONSTRUCTION_REASON_CODE_MAP`)

`alexGConstructLivePosition()` (protected, pure, never edited) returns one of a fixed set of real
`{status,reason}` outcomes. A new, exact one-to-one lookup table — defined once, alongside the
reason registry, never inline at the trading call site — relabels each real `reason` string to its
registry code; nothing here re-implements or approximates the protected function's own logic:

| Real `reason` (from `alexGConstructLivePosition`) | `reasonCode` |
|---|---|
| `INVALID_ZONE_ROLE_INSIDE` | `ENTRY_INVALID_ZONE_ROLE` |
| `INVALID_BROKEN_DIRECTION` | `ENTRY_INVALID_BROKEN_DIRECTION` |
| `UNSUPPORTED_SETUP_TYPE` | `ENTRY_UNSUPPORTED_SETUP_TYPE` |
| `EXISTING_OPEN_TRADE_SAME_PAIR_TIMEFRAME` | `RISK_OPEN_POSITION_LIMIT` |
| `ATR_UNAVAILABLE` | `DATA_ATR_UNAVAILABLE` |
| `LIVE_BID_ASK_UNAVAILABLE` | `EXECUTION_SPREAD_UNAVAILABLE` |
| `ENTRY_MOVED_TOO_FAR_FROM_SIGNAL` | `ENTRY_MOVED_TOO_FAR_FROM_SIGNAL` |
| `INVALID_STOP` | `RISK_INVALID_STOP` |
| `PIP_VALUE_UNAVAILABLE` | `DATA_PIP_VALUE_UNAVAILABLE` |
| `DUPLICATE` (either duplicate check; `reason` is `null` on this status) | `STATE_SIGNAL_ALREADY_DECIDED` (the one authorized, honest fit — not a fabrication, since the status itself already means "already decided") |

A `reason` string that somehow isn't in this table falls back to `UNKNOWN_NOT_RECORDED` rather
than being invented — this should never occur given the table's completeness against the real
function's full outcome set, verified directly against all 10 real outcomes in
`tests/v126_phase2c_wave1_tests.js`.

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

## ALEX Candidate Lifecycle Instrumentation (Phase 2C Wave 1, v12.6.0)

### Why ALEX and not JVM

The Phase 2B repository analysis (see the conversation history / prior pre-commit reports for the
full 15-section report) traced both engines' complete decision paths and found a structural
asymmetry, not a scope choice:

- **JVM's protected functions call each other directly.** `checkAutoTrades()` (protected) calls
  `evaluateLiveTrigger()` (protected) calls `openPaperPosition()` (protected). Both of the latter
  two already compute and return rich, structured rejection reasons — but `checkAutoTrades()`
  discards them before any non-protected code ever sees them. There is no safe external hook for
  JVM's candidate-level detail today.
- **ALEX's real gate is a pure function feeding a non-protected wrapper.**
  `alexGConstructLivePosition()` is protected but pure (zero side effects) and returns a complete,
  structured 10-outcome result to its caller, `alexGAttemptOpenLivePosition()` — which is **not**
  protected, and is the function that actually mutates `alexGAccount`. ALEX's entire
  candidate-approval outcome is achievable at SAFE instrumentation risk with zero protected-code
  edits.

Per the user's own explicit rule ("do not recommend implementing UNSAFE locations during the first
Phase 2C release"), this wave implements ALEX's full lifecycle and leaves JVM exactly as it was in
v12.5.0. Whether JVM ever gets deeper instrumentation is an open product decision (would require
either accepting a permanently coarse JVM signal, or authorizing a disclosed, minimal protected-
function edit) — not decided or implemented here.

### Where each ALEX event is emitted

All of the following live in `alexGEvaluatePairForLiveSetups()` and
`alexGAttemptOpenLivePosition()` — both confirmed **not** protected functions. Neither function's
original trading logic was reordered; every new statement is either a new `emitDecisionEvent()`
call or a new function parameter (`scanId`) threaded through.

| Event | Location | Real values used |
|---|---|---|
| `CANDIDATE_CREATED` | `alexGEvaluatePairForLiveSetups()`, immediately after the real `alexGRunSetupEngine()` call, once per setup whose `qualificationTimestamp` is strictly newer than this pair's real, pre-existing live boundary (see below) and not yet in the `decisionEventKnownCandidateIds` dedup set | `candidateId = setup.setupId`; full setup metadata in `context` |
| `RULE_EVALUATED` (`ALEX_ACTIVATION_CUTOFF`) | same function, at the existing call to `alexGIsSetupEligibleForLiveTrading()` | real `PASS`/`FAIL`, `reasonCode` only on `FAIL` |
| `CANDIDATE_REJECTED` (`CONFIG_BEFORE_ACTIVATION`) | same function, linked via `parentEventId` to the `RULE_EVALUATED` above, only on `FAIL` | — |
| `RULE_EVALUATED` (`ALEX_SIGNAL_STALENESS`) | same function, at the existing call to `alexGIsSetupSignalStale()` | real `PASS`/`FAIL` |
| `CANDIDATE_REJECTED` (`STATE_SIGNAL_STALE`) | same function, linked via `parentEventId`, only on `FAIL` | — |
| `CANDIDATE_REJECTED` (`STATE_SIGNAL_ALREADY_DECIDED`) | same function, at the existing `alexGLiveSetupStatuses` dedup check | — |
| `TRADE_OPEN_REQUESTED` | `alexGAttemptOpenLivePosition()`, immediately before the real `alexGConstructLivePosition()` call | `direction` intentionally `null` (`evidenceCompleteness:'PARTIAL'`) |
| `CANDIDATE_REJECTED` (`STATE_SIGNAL_ALREADY_DECIDED`) | same function, on a `DUPLICATE` construction result | — |
| `CANDIDATE_APPROVED` | same function, on a `TRADE OPENED` construction result | real `direction`, `tradeId` |
| `TRADE_OPEN_FAILED` | same function, on any other `BLOCKED_*` construction result | mapped via `ALEXG_CONSTRUCTION_REASON_CODE_MAP` |
| `TRADE_OPEN_FAILED` (`EXECUTION_LEDGER_REJECTED`) | same function, after the existing `commitAlexGLedger()` call, on failure | real `committed.reason` |
| `TRADE_OPENED` | same function, after `commitAlexGLedger()` succeeds | real `position` fields (entry/stop/target/positionSize/tradeId) |

### Identity and correlation

- `candidateId` = the real `setup.setupId` (already existed, deterministic, unique per zone/touch).
- `signalId` = `alexGLiveSignalId(setup)` (already existed) appears in event `context`.
- `tradeId` = the real `position.tradeId` once minted (already existed).
- The pre-existing `setupId → signalId → tradeId` linkage required no new plumbing — this release
  only reads and forwards identities the app already computes.
- `scanId`/`correlationId` are the real per-tick `__scanId` generated in `alexGLivePollTick()`
  (Phase 2A), threaded through as a new parameter on both instrumented functions:
  `alexGEvaluatePairForLiveSetups(oPair, scanId)` and
  `alexGAttemptOpenLivePosition(setup, datasets, evalMeta, scanId)`.

### Live-window classification: genuinely new vs. historical reconstruction

ALEX's zone/setup engine fully rebuilds `alexGSetupState` for a pair from 90 days of candles on
*every* poll — the same historical setup reappears every tick even once its trading fate is
permanently decided (that permanence is tracked separately, by the pre-existing
`alexGLiveSetupStatuses`, keyed by `signalId`). An earlier draft of this release deduped
`CANDIDATE_CREATED` using only a session-level `Set` keyed by `setupId` — but that meant "have I
already told someone about this setup," not "did this setup genuinely just become live," so the
very first poll after a page load (or reload) would emit a `CANDIDATE_CREATED` burst for every
historically-qualifying setup the 90-day reconstruction found. **This was corrected before
release.**

**The authoritative boundary:** `alexGEvaluatePairForLiveSetups()` now captures
`alexGLastEvaluatedCloseTime[pair].H1` — a real, pre-existing, non-protected value the frozen zone
engine itself already maintains (it is never persisted, and resets to `{}` on every real page
reload, exactly like the rest of ALEX's live-polling cursor state) — at the very start of the
function, *before* that same poll's rebuild advances it further. A setup is classified as
genuinely newly live only if its own real `qualificationTimestamp` is **strictly greater than**
that captured boundary. On a pair's very first-ever live evaluation this session (including the
first poll after a reload), the boundary is `null` — nothing a 90-day reconstruction finds on that
poll can be classified as live, so a cold start is never mistaken for genuine new activity.

The `decisionEventKnownCandidateIds` dedup `Set` (bounded,
`DECISION_EVENT_KNOWN_CANDIDATE_IDS_MAX=5000`, oldest evicted first — a plain JS `Set` preserves
insertion order, so evicting `.values().next().value` before inserting the newest entry once the
cap is hit is a deterministic FIFO policy) is retained as a **secondary** guard only, covering the
edge case where the same already-classified-live setup could otherwise be re-emitted twice within
one boundary (e.g. a retried call before the boundary itself advances) — it is never, by itself,
what decides live vs. historical. Reset only by the existing dev-only `clearDecisionEvents()`
action, which now also clears it.

**Boundary determinism:** exactly-at-boundary (`qualificationTimestamp === previousH1Boundary`) is
classified as historical, not live — the comparison is strict `>`. One millisecond after the
boundary is live; one millisecond before is historical. An invalid or missing
`qualificationTimestamp` (not a real possibility from the real engine, which always computes a
valid one via `getCandleCloseTime()`) can never fabricate a live classification either — the guard
also requires `typeof qualificationTimestamp === 'number' && isFinite(...)`.

**A historical setup's real trading treatment is completely unchanged.** `RULE_EVALUATED`
(activation/staleness), the existing `alexGLiveSetupStatuses` duplicate check, and the full
trade-open pipeline all still run for every setup regardless of its live/historical
classification — only the `CANDIDATE_CREATED` observability label is suppressed for a historical
one. This was verified directly, both offline and live: a historical (first-poll) setup still
produces `RULE_EVALUATED` PASS/PASS and a real `TRADE_OPENED`, with zero `CANDIDATE_CREATED`.

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
  corruption-handling/rollback proposal, not an assumption baked in here. Still true as of v12.6.0
  — zero new localStorage keys were added by this wave, confirmed directly.
- **`SCAN_COMPLETED`/`ENGINE_ERROR` from `scanAll()`/`alexGLivePollTick()` could not be exercised
  end-to-end in the offline JXA test harness for Phase 2A**, for the same documented, permanent
  reason `closePaperPosition()`/`alexGCloseLivePosition()` couldn't be in earlier releases (see
  `docs/TESTING.md`). By contrast, Phase 2C Wave 1's ALEX event chain — including the full
  `CANDIDATE_CREATED → … → TRADE_OPENED` lifecycle — **was** proven with genuinely real,
  end-to-end execution offline, by engineering an actual qualifying candle sequence and stubbing
  only the `fetch()` network boundary (never any application function) in OANDA's own response
  shapes; the same scenario was independently re-run live in a real Chrome tab for this release's
  pre-commit verification.
- **JVM candidate-level detail remains structurally unreachable** without either accepting a
  permanently coarse signal or authorizing a disclosed, minimal protected-function edit — see "Why
  ALEX and not JVM" above. Not a limitation of this release specifically; a standing architectural
  fact about JVM's protected-calls-protected call chain.
- **ALEX's own touch-level rejection detail is still unreachable.** `alexGEvaluateBreakRetest()`
  and `alexGEvaluateRepeatedReaction()` are protected-on-protected, and their `{qualifies:false}`
  return contract structurally discards *which* of several conditions failed — recovering that
  would require either editing a protected function or reimplementing its logic externally, both
  explicitly out of scope for this wave. Only "a candidate was/wasn't created" is observable today,
  not "why a touch didn't qualify."
- **Reason codes are a fixed, curated set**, not exhaustive — future work will add codes to
  `REASON_CODE_REGISTRY` as real rule-evaluation logic starts emitting more specific reasons (see
  above: 8 new codes were added in v12.6.0 for ALEX's construction outcomes, following the same
  add-before-use discipline).
- **Per-field evidence provenance (`EVIDENCE_FIELD_PROVENANCE`) is still a defined taxonomy only**
  — no event in either phase tags an individual field with it yet; every v12.6.0 ALEX event uses
  the simpler, event-level `evidenceCompleteness` (`COMPLETE` for nearly all fields, `PARTIAL` only
  for `TRADE_OPEN_REQUESTED`'s not-yet-resolved `direction`).

## Future Phase 2C Wave 2+ (not started, not authorized)

Explicitly deferred, per the Wave 1 authorization's own scope boundary:

- JVM candidate/rule/rejection/approval/failure instrumentation of any kind (blocked on the open
  product decision described above).
- ALEX touch-level `SETUP_OBSERVED` and the two rule-by-rule sub-evaluators' individual condition
  detail (blocked on the protected-on-protected structural issue described above).
- Any protected-function or protected-constant edit anywhere.
- Persistent Decision Event storage, missed-opportunity/counterfactual analytics, an Experiment
  Registry, shadow strategies, AI coaching, historical-candle retrieval/replay reconstruction, and
  any Trade Inspector or `computeTiCompliance()` change — all still out of scope, unchanged from
  Phase 2A's own reservation list.

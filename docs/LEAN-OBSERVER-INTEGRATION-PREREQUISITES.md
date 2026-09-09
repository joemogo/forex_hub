# Disabled observer: integration prerequisites

This is a developer handoff, not an instruction to enable observation or trading.
The application does not load the observer module or call its APIs.

Browser design and isolated synthetic testing are now authorized. See
`LEAN-OBSERVER-BROWSER-DESIGN.md` for the selected whole-session worker candidate;
production wiring, actual browser control, installation and activation remain
outside scope. The earlier design-authority gate is resolved, not the feasibility
and validation requirements below.

## Entry point

Future forward integration must use
`MogoLeanForwardObserver.alexGCreateFreshLeanEngineExportSession`, not the raw
synthetic-capable capture API. The returned session is frozen and inert until
explicit `enabled: true` invocation. Loading the module defines APIs only.

Required trusted dependencies: an isolated synchronous setup engine, the reviewed
v2 emitter and hash dependency, and a UTC-millisecond clock. Supply an explicit
positive integer `maxEndpointAgeMs` at most 3,600,000. This is a technical ceiling,
not a recommendation or an approved production latency policy.

Inputs are one pinned pair, H1 candles with an unclosed final sentinel, and the
identity/version/configuration/dataset metadata required by the emitter. The
capture derives setup, zone and retest facts from the supplied engine, not caller
snapshots. The first accepted snapshot primes the baseline and exports nothing.

## Before production use

- Review and approve an isolated engine-state boundary. Invoking the supplied
  engine may mutate its own state; do not point this API at the running scanner
  merely because the adapter has no trading calls.
- Validate the trusted clock and select a justified age limit. Recent candle
  timestamps do not prove a recent fetch or authenticate the provider.
- Resolve feed/session handling. H1 intervals must be exactly one hour and each
  update must retain the previous endpoint and an exact timestamp suffix.
  Weekend/holiday gaps currently refuse. Do not fabricate bars or automatically
  restart the session to hide discontinuity; restart would discard its baseline.
- Confirm source identities, versions, exact originating candles, permissions,
  and dataset hash for a separately authorized real capture.
- Verify in an isolated real browser and on the Mac. Node VM browser-like tests
  do not establish Chrome integration, CSP behavior, or access to the running app.
- Keep observation/export and paper-trading activation as separate decisions.
  No observer test establishes broker isolation, risk sizing, P&L accounting,
  position persistence, or trade-execution readiness.

## Refusals and recovery

### Cross-language synthetic coverage

The actual-engine downward and reflected upward exports pass the Python v2 CLI
with matching direction, case identity, bar count, retest and qualification
indices. Contradictory pre-break roles refuse. This is local Python adapter
evaluation, not cloud LEAN execution. Both mirrored fixtures match break index
42. The boundary now refuses a declared/evaluated break-index mismatch, in
addition to geometry validation; moving the declaration to 43 is refused in both
fixtures. Multi-confirmation timing and broader event parity remain unproven.
With confirmation counts 2 or 3, neither mirrored fixture generates a production
B&R; hypothetical Python requests refuse as unqualified. This is a recorded
limitation, not evidence of confirmed-break timing parity. The live/default
one-close configuration has not changed. Any protected strategy-rule repair
requires separate review/authorization; do not infer wider configuration support
from accepting an integer at the envelope boundary.
v135 requires python3 explicitly.

### Source-only H1 dependency boundary (synthetic proof)

The v135 fixture now runs the same prefix sequence in a second realm containing
only the 29 Phase 2/3 function declarations (`alexGFindSwingPoints` through
`alexGRunSetupEngine`), seven helpers, three copied constants, and three fresh
state objects. The complete JSON export matches the full-application harness.
This is a sufficient inventory for the exercised H1 path, not a minimal or
exhaustive dependency proof for every branch or market pattern.
The reflected upward-break fixture now matches between full and source-only
realms too, including pending-successor behavior and duplicate suppression.
Explicit expected direction/role checks supplement the parity comparison so
agreement alone cannot hide a shared direction reversal. This remains synthetic
H1 coverage, not a production or LEAN-engine parity claim.

- Helpers: `getCandleCloseTime`, `precomputeCloseTimes`, `calcATR`, `pipSize`,
  `getSession`, `isPreferredTradingDay`, `snapshotAlexGConfig`.
- Copied constants: `RULES_ALEXG`, `APP_VERSION`, `STRATEGY_ALEXG`.
- Owned mutable state: `alexGZoneState`, `alexGSetupState`,
  `alexGLastEvaluatedCloseTime`.
- Native Date is supplied; ordinary JavaScript built-ins belong to the realm.
  No DOM, storage, timers, fetch, scanner or application initialization is
  supplied to this second realm. `tests/lean_h1_source_factory.js` now extracts
  declarations directly from source without initializing the app. The full-app
  harness remains only an independent comparison control. A top-level throwing
  poison statement outside the selected declarations is never executed.
  Function text and constant values are compared with the reference harness.
  Extraction deliberately relies on reviewed declaration formatting and rejects
  missing/ambiguous declarations; it is not a general JavaScript parser or a
  security boundary for untrusted source. This helper is test-only, not shipped.
- H4/D/W inputs remain empty. `getCandleCloseTime` has a D/W dependency on
  `nyAlignedClose` that is deliberately absent: this is not a multi-timeframe
  extraction. No timezone/calendar behavior is proven by this H1 fixture.

Candidate: a build-time source-derived module with per-attempt owned state,
verified against protected source, instead of loading the application in an
iframe or resetting the live scanner. This remains a design direction only.
A worker would introduce asynchronous messaging while today's observer requires
a synchronous engine; it cannot be plugged in without a separately reviewed
contract change. Do not implement runtime eval/function-source extraction in the
application based on this test. Browser CSP, module loading, maximum-history
cost and complete strategy-path coverage remain unverified.

The synthetic actual-engine fixture now demonstrates one candidate ownership
model: a fresh VM realm and copied candles for each attempt. An injected failure
after engine mutation leaves a separate test engine and caller input unchanged;
discard/rebuild allows the pending export to recover once. This is test-only
state isolation, not a security sandbox or a production browser implementation.
The existing scanner must not be reset, swapped, or reused to emulate this proof.

Five independent test sessions now reproduce the complete exported JSON exactly.
The 15 fresh rebuilds of 53–55 synthetic candles measured a 2.633 ms median in one
Node v24.19.0 Linux x64 run (2.256–6.384 ms range). This includes realm creation,
input copying and engine evaluation, not observer/emitter latency. It is not a
browser benchmark or evidence for maximum supported history sizes. Keep owned
state as the candidate design; inspect actual engine dependencies before choosing
a browser boundary. No shared-state optimization or production wiring is justified
by this small-fixture measurement.

Stale/future timestamps, clock rollback, invalid cadence, changed closed OHLC,
and discontinuous windows refuse before engine execution. Rejected inputs do not
advance adapter state. A pending export may succeed when an intact fresh successor
arrives; repeated accepted snapshots do not re-export that setup. Engine failures
can still mutate engine-owned state and require an isolation/recovery design.

No UI wiring, recurring polling, storage, network transfer, deployment, merge,
paper positions, or live orders are authorized by this document.

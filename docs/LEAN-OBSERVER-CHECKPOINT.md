# Disabled LEAN observer checkpoint

## September 2, 2026 — actual-engine exports through Python v2

Based on published `ca2ad89`. The v135 fixture now passes both actual-engine
synthetic exports over stdin to the Python v2 CLI. Both qualify with the expected
sell/buy direction, exact case identity, bar count, retest and qualification
indices. Contradictory pre-break roles fail with REFUSE_ROLE_DIRECTION for both.
The test requires python3 and fails on missing interpreter, timeout or bad exit;
it does not silently skip. All request/response transfer stays in memory.

Executed: v135 14/14 fixture groups and Python v1/v2 31/31 unit tests.
Independent QA passed, including in-memory contradictory break-direction
mutations refused for both exports.
Other four observer suites and Mac/browser gates were not rerun. No runtime source changed.
This proves local Python adapter evaluation, not cloud LEAN execution or full
strategy parity. In particular, this test does not assert break-index equality.

Next bounded task: compare the declared production-engine break index with the
Python machine's derived index and document any semantic mismatch before claiming
event parity. The current Python boundary validates break geometry but does not
compare that declared index to its evaluated decision. Browser integration and
calendar handling remain unfinished. Paper readiness: not assessed.

## September 2, 2026 — direct-source test engine factory

Based on published `a61ec6d`. Added `tests/lean_h1_source_factory.js` to construct
owned H1 engine realms directly from reviewed declarations and constants,
without starting the app even for source retrieval. Both mirrored exports still
match the full-application reference. Tests verify exact function text/constant
values, missing-constant refusal, and that top-level poison outside selected
declarations is not executed. The factory is deliberately layout-specific,
test-only and not a general parser or untrusted-code sandbox.

v135: 13/13 fixture groups passed. Runtime code/protected source unchanged.
Independent QA verified declarations/constant values and the poison control.
Added its suggested automated positive control: full-script execution throws
on the poison while the direct-source factory succeeds.
Other four observer suites, Python contracts and real-browser/Mac checks were
not rerun in this test-helper-only increment. No install, enabling or trading.

Next bounded task: feed the actual-engine mirrored synthetic exports into the
Python v2 boundary to check cross-language compatibility for this exact path.
Browser integration and calendar handling remain open. Paper readiness: not assessed.

## September 1, 2026 — mirrored source-only H1 engine export

Based on published `d226b66`. Reflected synthetic OHLC prices (swapping high/low)
without injecting setup answers. Both the full-application and source-only
real-engine realms detect an upward B&R at prefix 54, retain it pending the
successor candle, export at 55 and suppress the duplicate. Their entire JSON
envelopes match. Explicit checks pin upward/resistance and downward/support
semantics; caller candles and separate engine state remain unchanged.

Focused checks: v132 19/19, v133 13/13, v134 4/4, v135 12/12, v136 24/24
(72 fixture groups, not assertions). Independent QA passed; forcing the mirrored
output direction downward in memory failed the explicit upward assertion.
No runtime source changed. Python contract
and Mac/real-browser gates were not run. This proves two mirrored synthetic H1
paths, not all strategy branches or actual LEAN execution.

Next bounded task: turn the proven dependency inventory into a test-only,
source-derived owned-engine factory that does not initialize the full app even
to retrieve declarations; verify it against these mirrored fixtures. No runtime
module, production wiring or protected-function changes are authorized by this
checkpoint. Browser validation and calendar handling remain open.
Paper-trading readiness: not assessed.

## September 1, 2026 — source-only H1 engine boundary

Based on published `9657686`. Audited the actual engine dependencies and added
a test-only second realm with 29 unchanged Phase 2/3 function declarations,
seven helpers, three copied constants and three fresh state objects. Without
application initialization or browser IO in that realm, prefixes 53/54/55 produce
the same complete JSON envelope as the full harness. The initial check caught
an omitted `STRATEGY_ALEXG` dependency; supplying its copied value fixed the test.

v135: 11/11 fixture groups pass. Independent QA passed; omitting the strategy
constant or suppressing the bare engine's results each failed the test in memory.
No runtime source changed. Other four observer
suites (previously 60 groups), Python and real-browser/Mac gates were not rerun
for this test/documentation-only increment. See the prerequisites document for
the exact inventory and limitations, including the unexercised D/W timezone
dependency and synchronous-engine versus asynchronous-worker mismatch.

Next bounded task: extend the source-only proof with a mirrored upward-break
synthetic fixture to check both directions before any extraction implementation.
Production integration still requires separate authorization. No real data,
trading, installation or enabling. Paper-trading readiness: not assessed.

## September 1, 2026 — independent rebuild repeatability and cost

Based on published `b075fb7`. Five fresh observer sessions each rebuild the real
engine at prefixes 53, 54 and 55. Every complete exported JSON envelope matches
the earlier recovery control byte-for-byte; caller candles and the separate
engine's tracked state remain unchanged. This adds one fixture group, not five.

Measured 15 rebuilds on Node v24.19.0, Linux x64: minimum 2.256 ms, median
2.633 ms, maximum 6.384 ms in the first run. Timing includes realm creation,
candle copying and engine evaluation; excludes observer/emitter work. These are
descriptive small-fixture measurements, not latency thresholds, browser results,
representative 10,000-bar costs or a production performance guarantee.

Focused checks: v132 19/19, v133 13/13, v134 4/4, v135 10/10, v136 24/24
(70 fixture groups, not assertion count). Runtime source remains unchanged.
Independent QA passed; an in-memory mutation changing the repeated envelope's
case ID failed the JSON equality assertion. Equality refers to JSON.stringify
output, not a separate wire-serialization implementation.
Full Mac/Chrome and Python contract tests were not run. Paper readiness: not assessed.

Decision: retain per-attempt owned engine state as the candidate design; this
small fixture supplies no reason to introduce shared-state reuse. No production
implementation boundary has been approved. Next bounded task: audit the actual
engine's source dependencies for an isolated browser execution boundary and
document the smallest feasible extraction without changing protected functions
or wiring production. Calendar handling and real-browser validation remain open.

## September 1, 2026 — test-only engine ownership and recovery proof

Based on published `8ae54ff`. Refactored the existing actual-engine test harness
into a realm factory. A new test-only dependency creates a fresh VM realm and
copies candles per invocation. After a real engine evaluation, a fault deliberately
changes the owned setup state and candle copy, then throws. The separate engine's
three tracked state structures and caller candles remain unchanged. Discarding
the failed realm and retrying the same pending successor produces the expected
export once; its repeated snapshot is suppressed.
Independent QA passed. Mutations reusing the separate engine realm or removing
the candle copy failed. This proves same-session retry/duplicate behavior only,
not global or process-restart delivery idempotence. The observer API does not
create an isolated engine itself; the test supplies that dependency explicitly.

Focused checks: v132 19/19, v133 13/13, v134 4/4, v135 9/9, v136 24/24
(69 fixture groups, not assertion count). No runtime source changed. This is
synthetic test evidence for a state-ownership design, not a browser deployment,
security sandbox, or proof that the existing running scanner is isolated.
Full Mac/Chrome and Python contract tests were not run. Paper readiness: not assessed.

Next bounded task: quantify the fresh-rebuild cost and verify repeated independent
engine attempts produce the same envelope before selecting an implementation
boundary. Production integration still needs separate authorization and a real
browser isolation plan; do not transplant the test harness into production.

## September 1, 2026 — browser-like boundary and integration handoff

Based on published `669492f`. Added a VM browser-like test for the fresh wrapper
using native Date candles, throwing browser-IO access traps, and no CommonJS
module. It verifies inert disabled invocation, successful explicit baseline
capture, stale refusal before further engine calls, and a frozen session.
Application construction of the freshness wrapper is now explicitly forbidden by
the isolation fixture. No runtime source changed.

Focused checks: v132 19/19, v133 13/13, v134 4/4, v135 8/8, v136 24/24
(68 groups). Real Chrome/Mac checks and the Python contract suite were not run.
Independent QA passed; removing browser API exposure or stale-data enforcement
was detected by in-memory mutation checks.
See `LEAN-OBSERVER-INTEGRATION-PREREQUISITES.md` for the intended API, dependencies,
refusals, and boundaries. This document does not authorize integration or trading.

Next: review isolated engine-state ownership and failure recovery before any
production connection. Real browser validation, calendar-aware continuity and
real capture remain unfinished. Paper-trading readiness remains not assessed.

## September 1, 2026 — explicit clock-based freshness gate

Based on published `747cd0b`. New standalone
`alexGCreateFreshLeanEngineExportSession` wraps the existing synchronous capture.
It requires a trusted `nowUtcMs` function and a positive integer
`maxEndpointAgeMs` no greater than 3,600,000. These are pinned at construction;
snapshot fields cannot override them. Disabled invocation does not read the clock.

Before engine invocation, the wrapper rejects invalid clocks, clock rollback
relative to the last accepted capture, future endpoint timestamps, and endpoint
age above the explicit policy. Age equality is accepted. Failed captures do not
advance its clock watermark. Timestamp ordering/cadence/overlap and OHLC guards
remain enforced by the wrapped capture. Tests use controlled clocks only.

Focused results: v132 19/19, v133 12/12, v134 4/4, v135 8/8, v136 24/24
(67 groups). Independent QA passed. Same-realm mutation controls detected removal
of future/stale/rollback checks and premature clock-watermark assignment; the
unmodified positive control passed. A real-engine synthetic pending setup survives stale-data refusal,
then exports once when a fresh successor is provided. `index.html` and protected
strategy code are unchanged. No application wiring, real data, trading, merge,
deployment, storage or network behavior added. Full Mac gate and Python contract
suite were not rerun. Paper-trading readiness: not assessed.

Limitations: raw synchronous capture remains synthetic-capable and has no clock
gate; a future integration must explicitly choose the fresh wrapper. The clock
and feed are trusted dependencies, not authenticated by this check. Endpoint age
does not prove the source was recently fetched. Calendar gaps still refuse.
Next bounded task: verify the wrapper's browser exposure and isolation as a
single operator-facing, disabled entry point; document prerequisites and remaining
production-integration boundary without loading it into the running application.

## September 1, 2026 — snapshot continuity guard

Based on published `dad2d78` (draft PR #1). A subsequent capture must retain an
exact timestamp suffix of the previous accepted window, including its endpoint.
Leading warmup eviction is allowed; deleted/interposed timestamps, prepended
history, and disjoint windows refuse before engine execution. State is updated
only after accepted capture; a rejected snapshot does not erase a pending export.

All H1 timestamp intervals must be exactly one hour, including the first capture
and appended bars. `REFUSE_OBSERVER_CAPTURE_UNSUPPORTED_GAP` deliberately includes
possible weekend/holiday closures: there is no validated market calendar here.
No candles are fabricated and no session is automatically reset. This policy is
conservative and not yet suitable for unattended production capture across market
closures. A continuity refusal is not proof that the feed itself is defective.

Focused checks: v132 19/19, v133 12/12, v134 4/4, v135 7/7, v136 21/21
(63 groups total). Actual-engine pending export survives a deleted-candle refusal
and succeeds on the intact successor snapshot. Independent QA passed. In-memory
mutations removing either the overlap or cadence guard failed the suite, while
the unmodified positive control passed (same-realm harness; initial cross-realm
harness failures were discarded as invalid mutation evidence).
Full Mac gate and Python contract
suite not rerun. No `index.html`, integration, real data, trading, merge,
or deployment changes. Paper-trading readiness remains not assessed.

Next bounded task: explicit wall-clock freshness/future-candle checks with a
test-controlled clock, without changing strategy rules or inventing market hours.
Calendar-aware continuity and authorized production integration remain open.

## September 1, 2026 — historical OHLC guard

Based on published branch tip `570a4d7` (draft PR #1).

The standalone H1 synchronous capture session now copies finite OHLC facts for
the closed candles in its last accepted window. A changed overlapping closed
candle refuses with `REFUSE_OBSERVER_CAPTURE_REVISED_HISTORY` before engine
invocation. Copies do not alias caller candle objects. Failed captures do not
advance these facts. The final unclosed sentinel can update until a successor
arrives. Matching rolling-window overlap survives warmup eviction.

Focused verification: v132 emitter 19/19, v133 observer 12/12, v134 end-to-end
4/4, v135 actual-engine integration 7/7, v136 delayed/capture session 19/19.
The actual-engine pending-export test rejects a historical revision, then
successfully exports on the unmodified successor snapshot.
Independent QA passed; removing the revision refusal in an in-memory mutation
caused the expected assertion failure.

No changes to `index.html` or protected strategy code. No application loading,
call site, trading, storage, evidence access, merge, or deployment added.
Tests use synthetic data only. Full Mac gate and Python contract suite were
not rerun for this JavaScript-only change. Paper-trading readiness: not assessed.

At this checkpoint this was a bounded overlapping-window guard, not complete feed provenance:
nonoverlapping windows, deleted/interposed timestamps, and history reintroduced
after eviction still need an explicit continuity policy. Wall-clock freshness,
production integration, real forward capture, and paper readiness remain open.
Next bounded task: define and test fail-closed snapshot overlap/continuity rules
without breaking supported warmup eviction or pending-export recovery.

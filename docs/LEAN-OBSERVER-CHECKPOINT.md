# Disabled LEAN observer checkpoint

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

# Disabled LEAN observer checkpoint

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

This is a bounded overlapping-window guard, not complete feed provenance:
nonoverlapping windows, deleted/interposed timestamps, and history reintroduced
after eviction still need an explicit continuity policy. Wall-clock freshness,
production integration, real forward capture, and paper readiness remain open.
Next bounded task: define and test fail-closed snapshot overlap/continuity rules
without breaking supported warmup eviction or pending-export recovery.

#!/usr/bin/env node
'use strict';
// ══════════════════════════════════════════════════════════════════════════════════════════════
// v12.42.0 — EXIT FIDELITY AND POLL RE-ENTRANCY
// ══════════════════════════════════════════════════════════════════════════════════════════════
//
// These fixtures drive the REAL alexGCheckLivePositions and alexGLivePollTickGuarded, extracted
// verbatim from index.html, together with the REAL protected alexGReconstructExitFromCandles.
// Nothing under test is reimplemented here; only the boundaries the functions call out to
// (candle fetch, the protected close, bid/ask, persistence) are stubbed, in the shapes the real
// callers return.
//
// WHY THE STUBS STOP WHERE THEY DO. alexGCloseLivePosition is a PROTECTED function and is stubbed
// rather than executed, because what these fixtures assert is what the CALLER does with its
// result -- the exact thing that was previously discarded. Stubbing it is what lets a rejected
// ledger commit be exercised at all: in the real function that outcome needs a second tab or a
// full quota, neither of which exists offline.
//
// Run:  node tests/run_v142_exit_fidelity_reentrancy_tests.js

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const SRC = fs.readFileSync(path.resolve(__dirname, '..', 'index.html'), 'utf8');

// Verbatim extraction by brace matching from the real file. A regex that grabbed to the next
// `\n}` would silently truncate at the first nested closing brace and test a fragment.
function extractFunction(name) {
  const decl = new RegExp('(?:async\\s+)?function\\s+' + name + '\\s*\\(');
  const m = decl.exec(SRC);
  if (!m) throw new Error('function not found in index.html: ' + name);
  let start = m.index;
  // Back up over a preceding `async ` the declaration regex may have matched from mid-token.
  const open = SRC.indexOf('{', m.index);
  let depth = 0, i = open;
  for (; i < SRC.length; i++) {
    const ch = SRC[i];
    if (ch === '{') depth++;
    else if (ch === '}') { depth--; if (depth === 0) break; }
  }
  if (depth !== 0) throw new Error('unbalanced braces extracting ' + name);
  return SRC.slice(start, i + 1);
}

const results = [];
function t(name, desc, fn) {
  let pass = false, detail = '';
  try { const r = fn(); pass = !!(r && r.pass); detail = (r && r.detail) || ''; }
  catch (e) { pass = false; detail = 'threw: ' + (e && e.stack ? e.stack.split('\n')[0] : String(e)); }
  results.push({ name, desc, pass, detail });
}
async function ta(name, desc, fn) {
  let pass = false, detail = '';
  try { const r = await fn(); pass = !!(r && r.pass); detail = (r && r.detail) || ''; }
  catch (e) { pass = false; detail = 'threw: ' + (e && e.stack ? e.stack.split('\n')[0] : String(e)); }
  results.push({ name, desc, pass, detail });
}
const near = function (a, b, eps) { return a != null && Math.abs(a - b) < (eps == null ? 1e-9 : eps); };

// ── Harness ───────────────────────────────────────────────────────────────────────────────────
//
// Each scenario gets a FRESH realm. Exit state is mutated on the position objects themselves, so
// leaking one scenario's account into the next would let a fixture pass on the previous
// scenario's cursor.
function makeRealm(opts) {
  const o = opts || {};
  const ctx = {
    console: console,
    Date: Date, Math: Math, JSON: JSON, isFinite: isFinite, Number: Number, Object: Object,
    Array: Array, String: String, Promise: Promise, setTimeout: setTimeout,
    // ── boundaries ──
    ALEXG_LIVE_CANDLE_DURATION_MS: 60000,
    pipSize: function (pair) { return /JPY/.test(pair) ? 0.01 : 0.0001; },
    openPositionGeometryQuarantined: function () { return false; },
    saveAlexG: function () {},
    saveAlexGRest: function () {},
    storeSet: function () {},
    localStorage: { setItem: function () {}, getItem: function () { return null; }, removeItem: function () {} },
    renderAlexGLivePanel: function () {},
    fetchBidAsk: async function () { return o.bidAsk || null; },
    alexGUpdatePositionExcursionAndCheckExit: function () { return { hitStop: false, hitTarget: false, exitVal: null }; },
    alexGFetchExecutableCandles: async function () { return o.candles === undefined ? null : o.candles; },
    // Records every call so a fixture can assert on the ARGUMENTS the caller passed, which is
    // where the booked-versus-executable distinction actually lives.
    __closeCalls: [],
    __errors: [],
    recordAlexGEngineError: function (msg, meta) { ctx.__errors.push({ msg: msg, meta: meta }); },
    alexGAccount: o.account || { openPositions: [], closedPositions: [], balance: 10000 }
  };
  ctx.alexGCloseLivePosition = function (tradeId, result, exitPrice, ba, meta) {
    const pos = ctx.alexGAccount.openPositions.filter(function (p) { return p.tradeId === tradeId; })[0] || null;
    ctx.__closeCalls.push({
      tradeId: tradeId, result: result, exitPrice: exitPrice, meta: meta,
      // Snapshot the provenance AT CLOSE TIME. The caller deletes these fields again on a
      // rejection, so reading them afterwards would prove nothing about what was passed.
      posAtClose: pos ? JSON.parse(JSON.stringify(pos)) : null
    });
    if (o.closeBlocked) return { error: 'STALE_VERSION', blocked: true };
    // A successful close removes the position, exactly as the real one does.
    ctx.alexGAccount.openPositions = ctx.alexGAccount.openPositions.filter(function (p) { return p.tradeId !== tradeId; });
    return undefined;
  };
  vm.createContext(ctx);
  vm.runInContext(extractFunction('alexGReconstructExitFromCandles'), ctx);
  vm.runInContext(extractFunction('alexGCheckLivePositions'), ctx);
  return ctx;
}

// A long from 1.10000 with a 1.09500 stop (50 pips risk) and a 1.11000 target.
function longPos(over) {
  return Object.assign({
    tradeId: 'T1', pair: 'EUR_USD', timeframe: 'H1', direction: 'buy',
    entry: 1.10000, stop: 1.09500, target: 1.11000, plannedRR: 2,
    openedAt: '2026-08-01T00:00:00.000Z', lastExitCheckTimestamp: 1000,
    mfePips: 0, maePips: 0, mfeR: 0, maeR: 0, positionSize: 0.2, pipValue: 10
  }, over || {});
}
// bid/ask candle in the shape alexGFetchExecutableCandles returns.
function candle(t, o, h, l, c) {
  const s = { o: o, h: h, l: l, c: c };
  return { t: t, bid: s, ask: s };
}

// ══ EXIT PRICING ══════════════════════════════════════════════════════════════════════════════

(async function () {

await ta('EXITFID-1', 'A GAP THROUGH THE STOP is recorded: the exit bar opens at 1.09400, below the '
  + '1.09500 stop, so 10 pips of gap are captured as exitGapPips and exitExecutablePrice is the open', async function () {
  const ctx = makeRealm({ account: { openPositions: [longPos()], closedPositions: [], balance: 10000 },
    candles: [candle(2000, 1.09400, 1.09450, 1.09300, 1.09350)] });
  await ctx.alexGCheckLivePositions('S1');
  const p = ctx.__closeCalls[0] && ctx.__closeCalls[0].posAtClose;
  return { pass: !!p && p.exitPriceBasis === 'candle_open_gap' && near(p.exitExecutablePrice, 1.09400)
      && near(p.exitGapPips, 10, 1e-6) && near(p.exitGapR, 0.2, 1e-6),
    detail: p ? p.exitPriceBasis + ' exec=' + p.exitExecutablePrice + ' gap=' + p.exitGapPips + 'p / ' + p.exitGapR + 'R' : 'no close' };
});

await ta('EXITFID-2', 'THE BOOKED PRICE IS STILL THE TRIGGER. The frozen fixed-R methodology is '
  + 'deliberately unchanged -- this release records the gap, it does not re-price the ledger', async function () {
  const ctx = makeRealm({ account: { openPositions: [longPos()], closedPositions: [], balance: 10000 },
    candles: [candle(2000, 1.09400, 1.09450, 1.09300, 1.09350)] });
  await ctx.alexGCheckLivePositions('S1');
  const c = ctx.__closeCalls[0];
  return { pass: !!c && near(c.exitPrice, 1.09500) && c.result === 'Loss' && near(c.meta.exitTriggerLevel, 1.09500),
    detail: c ? 'booked at ' + c.exitPrice + ' (' + c.result + ')' : 'no close' };
});

await ta('EXITFID-3', 'AN ORDINARY IN-BAR TOUCH is not mislabelled as a gap: a bar opening at '
  + '1.09800, inside the range, and only later dipping to the stop records basis trigger_level and 0 gap', async function () {
  const ctx = makeRealm({ account: { openPositions: [longPos()], closedPositions: [], balance: 10000 },
    candles: [candle(2000, 1.09800, 1.09850, 1.09450, 1.09500)] });
  await ctx.alexGCheckLivePositions('S1');
  const p = ctx.__closeCalls[0] && ctx.__closeCalls[0].posAtClose;
  return { pass: !!p && p.exitPriceBasis === 'trigger_level' && near(p.exitGapPips, 0) && near(p.exitExecutablePrice, 1.09500),
    detail: p ? p.exitPriceBasis + ' gap=' + p.exitGapPips : 'no close' };
});

await ta('EXITFID-4', 'NEGATIVE CONTROL: the recorded executable price can only ever move AGAINST '
  + 'the position. A bar opening ABOVE the stop is bounded back to the stop, never booked as a '
  + 'favourable fill -- otherwise this correction could flatter a loss', async function () {
  const ctx = makeRealm({ account: { openPositions: [longPos()], closedPositions: [], balance: 10000 },
    candles: [candle(2000, 1.09900, 1.09950, 1.09400, 1.09450)] });
  await ctx.alexGCheckLivePositions('S1');
  const p = ctx.__closeCalls[0] && ctx.__closeCalls[0].posAtClose;
  return { pass: !!p && near(p.exitExecutablePrice, 1.09500) && near(p.exitGapPips, 0),
    detail: p ? 'exec=' + p.exitExecutablePrice : 'no close' };
});

await ta('EXITFID-5', 'A SHORT gapping through its stop is captured symmetrically -- the bounded '
  + 'side flips with direction, so this is not a buy-only correction', async function () {
  const short = longPos({ direction: 'sell', entry: 1.10000, stop: 1.10500, target: 1.09000 });
  const ctx = makeRealm({ account: { openPositions: [short], closedPositions: [], balance: 10000 },
    candles: [candle(2000, 1.10700, 1.10800, 1.10600, 1.10750)] });
  await ctx.alexGCheckLivePositions('S1');
  const p = ctx.__closeCalls[0] && ctx.__closeCalls[0].posAtClose;
  return { pass: !!p && p.exitPriceBasis === 'candle_open_gap' && near(p.exitExecutablePrice, 1.10700)
      && near(p.exitGapPips, 20, 1e-6),
    detail: p ? 'exec=' + p.exitExecutablePrice + ' gap=' + p.exitGapPips : 'no close' };
});

// ══ EXCURSION ═════════════════════════════════════════════════════════════════════════════════

await ta('EXITFID-6', 'MFE DOES NOT ABSORB THE EXIT BAR. A long is stopped out on a bar that then '
  + 'spikes 60 pips up; the recorded mfeR stays at what the trade is KNOWN to have reached while '
  + 'open, and the spike is kept separately as an upper bound rather than booked as excursion', async function () {
  const ctx = makeRealm({ account: { openPositions: [longPos()], closedPositions: [], balance: 10000 },
    candles: [
      candle(2000, 1.10000, 1.10100, 1.09900, 1.10050),          // +10 pips favourable, no exit
      candle(2060, 1.09900, 1.10600, 1.09400, 1.10500)           // stop hit AND a 60-pip spike
    ] });
  await ctx.alexGCheckLivePositions('S1');
  const p = ctx.__closeCalls[0] && ctx.__closeCalls[0].posAtClose;
  // Pre-exit bar reached 1.10100 = +10 pips = 0.2R on a 50-pip stop. The exit bar's high of
  // 1.10600 would be +60 pips = 1.2R, and must NOT become the recorded figure.
  return { pass: !!p && near(p.mfePips, 10, 1e-6) && near(p.mfeR, 0.2, 1e-6)
      && near(p.mfeRUpperBound, 1.2, 1e-6) && p.excursionBoundedByExitBar === true,
    detail: p ? 'mfeR=' + p.mfeR + ' upper=' + p.mfeRUpperBound + ' bounded=' + p.excursionBoundedByExitBar : 'no close' };
});

await ta('EXITFID-7', 'POSITIVE CONTROL: excursion from bars strictly BEFORE the exit bar IS still '
  + 'counted -- the correction bounds the exit bar, it does not discard the trade\'s history', async function () {
  const ctx = makeRealm({ account: { openPositions: [longPos()], closedPositions: [], balance: 10000 },
    candles: [
      candle(2000, 1.10000, 1.10250, 1.09800, 1.10200),   // +25 pips fav, -20 pips adv
      candle(2060, 1.10200, 1.10300, 1.09400, 1.09450)    // exit bar
    ] });
  await ctx.alexGCheckLivePositions('S1');
  const p = ctx.__closeCalls[0] && ctx.__closeCalls[0].posAtClose;
  return { pass: !!p && near(p.mfePips, 25, 1e-6) && near(p.maePips, 20, 1e-6),
    detail: p ? 'mfe=' + p.mfePips + ' mae=' + p.maePips : 'no close' };
});

await ta('EXITFID-8', 'NEGATIVE CONTROL: when the exit bar reaches no FURTHER in favour than the '
  + 'bars before it, nothing is bounded and the flag is false -- so EXITFID-6 is a real detection '
  + 'rather than a flag that is always set', async function () {
  const ctx = makeRealm({ account: { openPositions: [longPos()], closedPositions: [], balance: 10000 },
    candles: [
      candle(2000, 1.10000, 1.10400, 1.09900, 1.10300),   // +40 pips fav
      candle(2060, 1.10300, 1.10350, 1.09400, 1.09450)    // exit bar tops out lower
    ] });
  await ctx.alexGCheckLivePositions('S1');
  const p = ctx.__closeCalls[0] && ctx.__closeCalls[0].posAtClose;
  return { pass: !!p && p.excursionBoundedByExitBar === false && near(p.mfeRUpperBound, 0.8, 1e-6),
    detail: p ? 'bounded=' + p.excursionBoundedByExitBar + ' upper=' + p.mfeRUpperBound : 'no close' };
});

// ══ REJECTED COMMIT ═══════════════════════════════════════════════════════════════════════════

await ta('EXITFID-9', 'A REJECTED LEDGER COMMIT RESTORES THE CURSOR. This is the defect that could '
  + 'book a losing trade as a winner: the cursor had already advanced past the exit bar, so the '
  + 'next tick would start after it, never see the exit again, and leave the position open', async function () {
  const pos = longPos({ lastExitCheckTimestamp: 1000 });
  const ctx = makeRealm({ account: { openPositions: [pos], closedPositions: [], balance: 10000 },
    candles: [candle(2000, 1.09800, 1.09850, 1.09400, 1.09450)], closeBlocked: true });
  await ctx.alexGCheckLivePositions('S1');
  return { pass: pos.lastExitCheckTimestamp === 1000 && ctx.alexGAccount.openPositions.length === 1,
    detail: 'cursor=' + pos.lastExitCheckTimestamp + ' (pre-tick 1000) openPositions=' + ctx.alexGAccount.openPositions.length };
});

await ta('EXITFID-10', 'POSITIVE CONTROL: a SUCCESSFUL close leaves the cursor advanced. Without '
  + 'this, EXITFID-9 would also pass on code that simply never advanced the cursor at all', async function () {
  const pos = longPos({ lastExitCheckTimestamp: 1000 });
  const ctx = makeRealm({ account: { openPositions: [pos], closedPositions: [], balance: 10000 },
    candles: [candle(2000, 1.09800, 1.09850, 1.09400, 1.09450)] });
  await ctx.alexGCheckLivePositions('S1');
  // The cursor advances to the exit bar's END: c.t (2000) + ALEXG_LIVE_CANDLE_DURATION_MS (60000).
  return { pass: pos.lastExitCheckTimestamp === 62000, detail: 'cursor=' + pos.lastExitCheckTimestamp };
});

await ta('EXITFID-11', 'a rejected close also rewinds the excursion it had already written and '
  + 'removes the provenance fields, so a retry next tick starts from the same state as this one', async function () {
  const pos = longPos({ lastExitCheckTimestamp: 1000, mfePips: 3, maePips: 4, mfeR: 0.06, maeR: 0.08 });
  const ctx = makeRealm({ account: { openPositions: [pos], closedPositions: [], balance: 10000 },
    candles: [candle(2000, 1.09800, 1.09850, 1.09400, 1.09450)], closeBlocked: true });
  await ctx.alexGCheckLivePositions('S1');
  return { pass: near(pos.mfePips, 3) && near(pos.maePips, 4) && near(pos.mfeR, 0.06) && near(pos.maeR, 0.08)
      && pos.exitPriceBasis === undefined && pos.exitGapPips === undefined
      && pos.mfeRUpperBound === undefined && pos.excursionBoundedByExitBar === undefined,
    detail: 'mfe=' + pos.mfePips + ' mae=' + pos.maePips + ' basis=' + pos.exitPriceBasis };
});

await ta('EXITFID-12', 'a rejected close is REPORTED, not swallowed -- a monitor that silently '
  + 'refuses to close positions is exactly the failure that has no other durable channel', async function () {
  const ctx = makeRealm({ account: { openPositions: [longPos()], closedPositions: [], balance: 10000 },
    candles: [candle(2000, 1.09800, 1.09850, 1.09400, 1.09450)], closeBlocked: true });
  await ctx.alexGCheckLivePositions('S1');
  const e = ctx.__errors[0];
  return { pass: !!e && /STALE_VERSION/.test(e.msg) && e.meta.stage === 'alexGCheckLivePositions.exitCommitRejected',
    detail: e ? e.meta.stage + ': ' + e.msg : 'no error recorded' };
});

await ta('EXITFID-13', 'a rejected close STOPS THE TICK. The real rollback replaces every object in '
  + 'openPositions with a deep clone, so the loop\'s remaining bindings are detached and their '
  + 'mutations would be silently discarded -- the second position must not be processed', async function () {
  const p1 = longPos({ tradeId: 'T1' });
  const p2 = longPos({ tradeId: 'T2', pair: 'GBP_USD', lastExitCheckTimestamp: 1000 });
  const ctx = makeRealm({ account: { openPositions: [p1, p2], closedPositions: [], balance: 10000 },
    candles: [candle(2000, 1.09800, 1.09850, 1.09400, 1.09450)], closeBlocked: true });
  await ctx.alexGCheckLivePositions('S1');
  return { pass: ctx.__closeCalls.length === 1 && p2.lastExitCheckTimestamp === 1000,
    detail: 'closes attempted=' + ctx.__closeCalls.length + ' second cursor=' + p2.lastExitCheckTimestamp };
});

await ta('EXITFID-14', 'POSITIVE CONTROL: with the close SUCCEEDING, both positions are processed -- '
  + 'so EXITFID-13 proves the rejection stopped the loop, not that the loop only ever runs once', async function () {
  const p1 = longPos({ tradeId: 'T1' });
  const p2 = longPos({ tradeId: 'T2', pair: 'GBP_USD', lastExitCheckTimestamp: 1000 });
  const ctx = makeRealm({ account: { openPositions: [p1, p2], closedPositions: [], balance: 10000 },
    candles: [candle(2000, 1.09800, 1.09850, 1.09400, 1.09450)] });
  await ctx.alexGCheckLivePositions('S1');
  return { pass: ctx.__closeCalls.length === 2, detail: 'closes attempted=' + ctx.__closeCalls.length };
});

await ta('EXITFID-15', 'a FAILED CANDLE FETCH still advances nothing and closes nothing -- the '
  + 'pre-existing ADR-011 contract is intact after this change', async function () {
  const pos = longPos({ lastExitCheckTimestamp: 1000 });
  const ctx = makeRealm({ account: { openPositions: [pos], closedPositions: [], balance: 10000 },
    candles: null });
  await ctx.alexGCheckLivePositions('S1');
  return { pass: pos.lastExitCheckTimestamp === 1000 && ctx.__closeCalls.length === 0,
    detail: 'cursor=' + pos.lastExitCheckTimestamp + ' closes=' + ctx.__closeCalls.length };
});

// ══ POLL RE-ENTRANCY ══════════════════════════════════════════════════════════════════════════
//
// These pin what tests/run_v1233_jvm_autotrade_reliability_tests.js JVMTMR-3..5 can no longer see
// now that the scheduled function is the wrapper: that the wrapper actually CALLS the tick, that
// it refuses an overlapping call, and that it releases its flag even when the tick throws.

function makePollRealm(tickImpl) {
  const ctx = {
    console: console, Date: Date, Promise: Promise, setTimeout: setTimeout, JSON: JSON,
    SCAN_PAIRS: ['EUR/USD', 'GBP/USD'],
    alexGAutoTrading: { enabled: true },
    __ticks: 0, __observations: [],
    generateDecisionEventId: function (p) { return p + '|' + (++ctx.__seq); }, __seq: 0,
    evidenceRecordForwardObservations: function (o) { ctx.__observations.push(o); }
  };
  ctx.alexGLivePollTick = tickImpl(ctx);
  vm.createContext(ctx);
  // The in-flight flag is module-level state the wrapper closes over, so it is taken VERBATIM
  // from index.html too. Seeding an equivalent here would let a renamed or wrongly-initialised
  // declaration pass -- and a flag that starts true would disable polling entirely.
  const decls = SRC.match(/^let alexGPollInFlight\s*=.*$/m);
  const decls2 = SRC.match(/^let alexGPollOverlapTotal\s*=.*$/m);
  if (!decls || !decls2) throw new Error('poll guard declarations not found in index.html');
  vm.runInContext(decls[0] + '\n' + decls2[0], ctx);
  vm.runInContext(extractFunction('alexGLivePollTickGuarded'), ctx);
  return ctx;
}

await ta('PRE-1', 'the guard CALLS THROUGH to the real tick -- without this, pointing JVMTMR-3..5 at '
  + 'the wrapper would prove only that something is scheduled, not that anything polls', async function () {
  const ctx = makePollRealm(function (c) { return async function () { c.__ticks++; }; });
  await ctx.alexGLivePollTickGuarded();
  return { pass: ctx.__ticks === 1, detail: 'ticks=' + ctx.__ticks };
});

await ta('PRE-2', 'A SECOND CALL WHILE THE FIRST IS STILL RUNNING DOES NOT RUN THE TICK. This is '
  + 'the defect: setInterval never awaited the async tick, so an overrunning tick overlapped the '
  + 'next one and they shared the account, the exit cursors and the evaluation cursor', async function () {
  let release;
  const gate = new Promise(function (r) { release = r; });
  const ctx = makePollRealm(function (c) { return async function () { c.__ticks++; await gate; }; });
  const first = ctx.alexGLivePollTickGuarded();
  await ctx.alexGLivePollTickGuarded();          // arrives while the first is suspended
  const during = ctx.__ticks;
  release(); await first;
  return { pass: during === 1, detail: 'ticks while first in flight=' + during };
});

await ta('PRE-3', 'the SKIPPED tick is RECORDED, not dropped. An overlap that never reaches the '
  + 'ledger is indistinguishable from downtime, and telling those apart is what the ledger is for', async function () {
  let release;
  const gate = new Promise(function (r) { release = r; });
  const ctx = makePollRealm(function (c) { return async function () { c.__ticks++; await gate; }; });
  const first = ctx.alexGLivePollTickGuarded();
  await ctx.alexGLivePollTickGuarded();
  release(); await first;
  const o = ctx.__observations[0];
  return { pass: ctx.__observations.length === 1 && o.poll.outcome === 'SKIPPED_POLL_IN_FLIGHT'
      && o.poll.evaluationAdvanced === false && o.poll.instrumentsConfigured === 2,
    detail: o ? o.poll.outcome + ' advanced=' + o.poll.evaluationAdvanced : 'nothing recorded' };
});

await ta('PRE-4', 'the skipped tick gets its OWN tickId. Reusing the running tick\'s id would write '
  + 'a second row under one natural key -- the exact duplicate-write defect fixed elsewhere in '
  + 'this release', async function () {
  let release;
  const gate = new Promise(function (r) { release = r; });
  const ctx = makePollRealm(function (c) { return async function () { c.__ticks++; await gate; }; });
  const first = ctx.alexGLivePollTickGuarded();
  await ctx.alexGLivePollTickGuarded();
  await ctx.alexGLivePollTickGuarded();
  release(); await first;
  const ids = ctx.__observations.map(function (o) { return o.poll.tickId; });
  return { pass: ids.length === 2 && ids[0] !== ids[1], detail: 'tickIds=' + JSON.stringify(ids) };
});

await ta('PRE-5', 'the flag is RELEASED after a normal completion, so the next tick runs', async function () {
  const ctx = makePollRealm(function (c) { return async function () { c.__ticks++; }; });
  await ctx.alexGLivePollTickGuarded();
  await ctx.alexGLivePollTickGuarded();
  return { pass: ctx.__ticks === 2 && ctx.__observations.length === 0,
    detail: 'ticks=' + ctx.__ticks + ' skips=' + ctx.__observations.length };
});

await ta('PRE-6', 'THE FLAG IS RELEASED EVEN WHEN THE TICK THROWS. A guard that leaked its flag on '
  + 'an exception would silently end live polling for the rest of the session -- strictly worse '
  + 'than the overlap it was added to prevent', async function () {
  let boom = true;
  const ctx = makePollRealm(function (c) {
    return async function () { c.__ticks++; if (boom) { boom = false; throw new Error('tick failed'); } };
  });
  try { await ctx.alexGLivePollTickGuarded(); } catch (e) { /* the throw is expected to propagate */ }
  await ctx.alexGLivePollTickGuarded();
  return { pass: ctx.__ticks === 2, detail: 'ticks after a throwing tick=' + ctx.__ticks };
});

await ta('PRE-7', 'the tick\'s own exception still PROPAGATES -- the guard must not become a second '
  + 'silent catch on the polling path', async function () {
  const ctx = makePollRealm(function (c) { return async function () { c.__ticks++; throw new Error('tick failed'); }; });
  let threw = null;
  try { await ctx.alexGLivePollTickGuarded(); } catch (e) { threw = e && e.message; }
  return { pass: threw === 'tick failed', detail: 'threw=' + threw };
});

results.forEach(function (r) {
  console.log((r.pass ? 'PASS' : 'FAIL') + ' -- ' + r.name + ': ' + r.desc + (r.detail ? '  [' + r.detail + ']' : ''));
});
const fails = results.filter(function (r) { return !r.pass; }).length;
console.log('---');
console.log(results.length + ' fixtures, ' + (results.length - fails) + ' PASS, ' + fails + ' FAIL');
process.exitCode = fails ? 1 : 0;

})();

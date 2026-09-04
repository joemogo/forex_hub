#!/usr/bin/env node
'use strict';
// ══════════════════════════════════════════════════════════════════════════════════════════════
// v12.44.0 — BASELINE TREND, THE CONTROL ARM
// ══════════════════════════════════════════════════════════════════════════════════════════════
//
// This strategy exists to be compared against ALEX, so the fixtures care about two things above
// correctness: that it is TRIVIAL (no hidden filter that would make it a second real strategy
// rather than a control), and that it CANNOT TRADE (registered, computable, and wired to nothing).
//
// Run:  node tests/run_v144_baseline_trend_tests.js

const fs = require('fs');
const path = require('path');
const vm = require('vm');
const SRC = fs.readFileSync(path.resolve(__dirname, '..', 'index.html'), 'utf8');

function extractFunction(name) {
  const m = new RegExp('(?:async\\s+)?function\\s+' + name + '\\s*\\(').exec(SRC);
  if (!m) throw new Error('not found: ' + name);
  const open = SRC.indexOf('{', m.index);
  let depth = 0, i = open;
  for (; i < SRC.length; i++) {
    if (SRC[i] === '{') depth++;
    else if (SRC[i] === '}') { depth--; if (depth === 0) break; }
  }
  return SRC.slice(m.index, i + 1);
}
function extractBlock(decl) {
  const i = SRC.indexOf(decl);
  if (i < 0) throw new Error('not found: ' + decl);
  const open = SRC.indexOf('{', i);
  let depth = 0, k = open;
  for (; k < SRC.length; k++) {
    if (SRC[k] === '{') depth++;
    else if (SRC[k] === '}') { depth--; if (depth === 0) break; }
  }
  return SRC.slice(i, k + 1) + ';';
}

const ctx = { console: console, Math: Math, JSON: JSON, isFinite: isFinite, Array: Array,
  Number: Number, Object: Object, String: String, Date: Date, Intl: Intl, isNaN: isNaN };
vm.createContext(ctx);
vm.runInContext(extractBlock('const RULES_BASELINE_TREND='), ctx);
vm.runInContext(extractFunction('baselineTrendSignal'), ctx);
vm.runInContext(extractFunction('baselineTrendGeometry'), ctx);
// The replay walker reuses ALEX's PROTECTED exit machinery verbatim, which is the whole point:
// the two arms must differ only at entry. Extracted, not stubbed, so a change to ALEX's exit
// resolution would show up here too.
vm.runInContext("const BASELINE_TREND_STRATEGY_ID='baseline_trend_v1';", ctx);
vm.runInContext(extractFunction('calcATR'), ctx);
vm.runInContext(extractFunction('getNYOffsetMinutes'), ctx);
vm.runInContext(extractFunction('nyAlignedClose'), ctx);
vm.runInContext(extractFunction('getCandleCloseTime'), ctx);
vm.runInContext(extractFunction('pipSize'), ctx);
vm.runInContext(extractFunction('alexGWalkOutcome'), ctx);
vm.runInContext(extractFunction('alexGComputeMAEMFE'), ctx);
vm.runInContext(extractFunction('baselineTrendReplayTrades'), ctx);
// RULES_BASELINE_TREND is already in this realm from the top of the file; only the two
// identifiers the package builder additionally reads are added here.
vm.runInContext("const APP_VERSION='test';const BASELINE_TREND_VERSION='baseline_trend_v1';", ctx);
vm.runInContext(extractFunction('baselineTrendBuildReplayPackage'), ctx);
const signal = vm.runInContext('baselineTrendSignal', ctx);
const geom = vm.runInContext('baselineTrendGeometry', ctx);
const CFG = vm.runInContext('RULES_BASELINE_TREND.config', ctx);
const replay = vm.runInContext('baselineTrendReplayTrades', ctx);
const buildPkg = vm.runInContext('baselineTrendBuildReplayPackage', ctx);

const results = [];
function t(name, desc, fn) {
  let pass = false, detail = '';
  try { const r = fn(); pass = !!(r && r.pass); detail = (r && r.detail) || ''; }
  catch (e) { pass = false; detail = 'threw: ' + (e && e.message ? e.message : String(e)); }
  results.push({ name, desc, pass, detail });
}
const near = function (a, b, eps) { return a != null && Math.abs(a - b) < (eps == null ? 1e-9 : eps); };

// A candle series whose only meaningful property is its closes.
function series(closes) {
  // `t` is a Date because getCandleCloseTime calls .getTime() on it.
  return closes.map(function (c, i) { return { t: new Date(1000 + i * 86400000), o: c, h: c, l: c, c: c }; });
}
// N+1 bars: the oldest at `from`, the newest at `to`, everything between irrelevant to the rule.
function ramp(from, to, n) {
  const out = [];
  for (let i = 0; i <= n; i++) out.push(from + (to - from) * (i / n));
  return series(out);
}
const LOOKBACK = CFG.lookbackBars;

// ══ THE SIGNAL IS TRIVIAL ═════════════════════════════════════════════════════════════════════

t('BT-1', 'a POSITIVE 3-month return is a buy, and the recorded return is the real one -- '
  + '1.1000 to 1.2100 over the lookback is +10%', function () {
  const s = signal(ramp(1.1, 1.21, LOOKBACK), CFG);
  return { pass: !!s && s.direction === 'buy' && near(s.lookbackReturn, 0.1, 1e-9)
      && s.lookbackBars === LOOKBACK,
    detail: s ? s.direction + ' ' + (s.lookbackReturn * 100).toFixed(2) + '%' : 'null' };
});

t('BT-2', 'a NEGATIVE return is a sell', function () {
  const s = signal(ramp(1.21, 1.1, LOOKBACK), CFG);
  return { pass: !!s && s.direction === 'sell' && s.lookbackReturn < 0,
    detail: s ? s.direction + ' ' + (s.lookbackReturn * 100).toFixed(2) + '%' : 'null' };
});

t('BT-3', 'EXACTLY FLAT is not a direction. A return of zero yields null, never a default buy -- '
  + 'a control arm that silently defaults would not be measuring what it claims to', function () {
  const s = signal(ramp(1.1, 1.1, LOOKBACK), CFG);
  return { pass: s === null, detail: JSON.stringify(s) };
});

t('BT-4', 'it reads ONLY the two endpoint closes. The path between them is irrelevant, so a wild '
  + 'series and a straight line with the same endpoints give the identical signal -- this is what '
  + 'makes it a control rather than a second strategy with hidden structure', function () {
  const straight = ramp(1.1, 1.21, LOOKBACK);
  const wild = straight.map(function (c, i) {
    if (i === 0 || i === straight.length - 1) return c;
    return { t: c.t, o: c.o, h: c.h, l: c.l, c: 1.5 - (i % 7) * 0.11 };  // nonsense in between
  });
  const a = signal(straight, CFG), b = signal(wild, CFG);
  return { pass: a.direction === b.direction && near(a.lookbackReturn, b.lookbackReturn, 1e-12),
    detail: a.direction + '/' + b.direction + ' ret ' + a.lookbackReturn.toFixed(6) + ' vs ' + b.lookbackReturn.toFixed(6) };
});

t('BT-5', 'BOUNDARY: exactly lookback+1 bars is enough, and one fewer is not. Off by one here '
  + 'would silently shift the horizon being tested', function () {
  const enough = signal(ramp(1.1, 1.21, LOOKBACK), CFG);
  const short = signal(ramp(1.1, 1.21, LOOKBACK).slice(1), CFG);
  return { pass: enough !== null && short === null,
    detail: 'n=' + (LOOKBACK + 1) + ' -> ' + (enough ? 'signal' : 'null') + ', n=' + LOOKBACK + ' -> ' + (short ? 'signal' : 'null') };
});

t('BT-6', 'unusable input yields null rather than a guess: no array, an empty array, a '
  + 'non-numeric close, and a non-positive prior price', function () {
  const bad = ramp(1.1, 1.21, LOOKBACK); bad[0].c = 0;
  const nan = ramp(1.1, 1.21, LOOKBACK); nan[nan.length - 1].c = 'x';
  return { pass: signal(null, CFG) === null && signal([], CFG) === null
      && signal(bad, CFG) === null && signal(nan, CFG) === null,
    detail: [signal(null, CFG), signal([], CFG), signal(bad, CFG), signal(nan, CFG)].join(',') };
});

// ══ GEOMETRY MATCHES ALEX'S RISK MODEL ════════════════════════════════════════════════════════

t('BT-7', 'a BUY puts the stop below and the target above, at exactly 2R. ATR 0.0010 at a 2x '
  + 'multiple is a 0.0020 risk distance, so from 1.1000 the stop is 1.0980 and the target 1.1040', function () {
  const g = geom('buy', 1.1000, 0.0010, CFG);
  return { pass: !!g && near(g.stop, 1.0980, 1e-9) && near(g.target, 1.1040, 1e-9)
      && near(g.riskDistance, 0.0020, 1e-9) && g.plannedRR === 2,
    detail: g ? 'stop=' + g.stop.toFixed(5) + ' target=' + g.target.toFixed(5) : 'null' };
});

t('BT-8', 'a SELL mirrors it exactly -- stop above, target below', function () {
  const g = geom('sell', 1.1000, 0.0010, CFG);
  return { pass: !!g && near(g.stop, 1.1020, 1e-9) && near(g.target, 1.0960, 1e-9),
    detail: g ? 'stop=' + g.stop.toFixed(5) + ' target=' + g.target.toFixed(5) : 'null' };
});

t('BT-9', 'the reward:risk is EXACTLY ALEX\'s 2R in both directions -- if these ever diverge the '
  + 'comparison stops being like-for-like and every conclusion drawn from it is invalid', function () {
  const b = geom('buy', 1.1, 0.001, CFG), s = geom('sell', 1.1, 0.001, CFG);
  const rrB = Math.abs(b.target - b.entry) / Math.abs(b.entry - b.stop);
  const rrS = Math.abs(s.target - s.entry) / Math.abs(s.entry - s.stop);
  return { pass: near(rrB, 2, 1e-9) && near(rrS, 2, 1e-9), detail: 'buy ' + rrB + ' sell ' + rrS };
});

t('BT-10', 'FAILS CLOSED on an unusable ATR. Zero, negative, non-finite and missing all yield '
  + 'null -- an invented stop is how a control arm quietly becomes a different experiment', function () {
  return { pass: geom('buy', 1.1, 0, CFG) === null && geom('buy', 1.1, -1, CFG) === null
      && geom('buy', 1.1, NaN, CFG) === null && geom('buy', 1.1, undefined, CFG) === null,
    detail: 'all null' };
});

t('BT-11', 'FAILS CLOSED on a bad direction or a bad entry price', function () {
  return { pass: geom('sideways', 1.1, 0.001, CFG) === null && geom(null, 1.1, 0.001, CFG) === null
      && geom('buy', 0, 0.001, CFG) === null && geom('buy', NaN, 0.001, CFG) === null,
    detail: 'all null' };
});

t('BT-12', 'the stop basis is RECORDED, not assumed. ALEX places its stop against a zone edge and '
  + 'this places it at an ATR multiple; that is the one disclosed difference between the arms and '
  + 'it must travel with every position rather than living only in a comment', function () {
  const g = geom('buy', 1.1, 0.001, CFG);
  return { pass: g.stopBasis === 'ATR_MULTIPLE_FROM_ENTRY' && g.stopATRMultiple === CFG.stopATRMultiple
      && near(g.atrAtEntry, 0.001),
    detail: g.stopBasis + ' x' + g.stopATRMultiple };
});

// ══ IT CANNOT TRADE ═══════════════════════════════════════════════════════════════════════════
//
// The whole safety story for this release. Promoting a strategy into PAPER is an operator
// governance boundary, and these fixtures are what make "it is only a control arm" checkable
// rather than a claim in a comment.

t('BT-13', 'the manifest declares paperTrading FALSE, along with automation and scanning. If a '
  + 'future edit flips any of these without the operator deciding to, this fails', function () {
  const m = /const BASELINE_TREND_MANIFEST=\{[\s\S]*?\n\};/.exec(SRC)[0];
  return { pass: /paperTrading:false/.test(m) && /automation:false/.test(m) && /scanning:false/.test(m),
    detail: (m.match(/capabilities:\{[\s\S]*?\}/) || [''])[0].slice(0, 120) };
});

t('BT-14', 'NO LIVE PATH REACHES IT. The replay walker legitimately calls the signal -- that is '
  + 'what it is for -- so the property worth asserting is not "nothing calls it" but that nothing '
  + 'on the TRADING path does. Every function that can open a real position is checked by name', function () {
  // Each of these is a real live-trading entry point. If a future edit wires the baseline into
  // any of them, a strategy the operator never promoted starts trading.
  const LIVE = ['alexGLivePollTick', 'alexGCheckLivePositions', 'alexGAttemptOpenLivePosition',
    'alexGEvaluatePairForLiveSetups', 'alexGConstructLivePosition', 'checkAutoTrades', 'scanAll'];
  const leaked = [];
  LIVE.forEach(function (name) {
    let body;
    try { body = extractFunction(name); } catch (e) { leaked.push(name + ' NOT FOUND — fixture is stale'); return; }
    ['baselineTrend', 'BASELINE_TREND'].forEach(function (needle) {
      if (body.indexOf(needle) >= 0) leaked.push(name + ' references ' + needle);
    });
  });
  return { pass: leaked.length === 0,
    detail: leaked.length ? leaked.join('; ') : LIVE.length + ' live entry points checked, none reference the baseline' };
});

t('BT-15', 'the strategy is REGISTERED, so it is visible and inspectable rather than dead code '
  + 'nobody knows about -- the point is a control arm that exists, not one that is hidden', function () {
  const reg = /const STRATEGY_REGISTRY=\[[\s\S]*?\];/.exec(SRC)[0];
  return { pass: /BASELINE_TREND_MANIFEST/.test(reg) && /BASELINE_TREND_SERVICES/.test(reg),
    detail: reg.replace(/\s+/g, ' ').slice(0, 160) };
});

t('BT-16', 'its services are INERT: no account, no journal, nothing to open. A control arm that '
  + 'returned a real account could accumulate state that later looks like trading history', function () {
  const svc = /const BASELINE_TREND_SERVICES=\{[\s\S]*?\n\};/.exec(SRC)[0];
  return { pass: /getAccount:\(\)=>null/.test(svc) && /getJournal:\(\)=>\[\]/.test(svc),
    detail: svc.replace(/\s+/g, ' ') };
});

t('BT-17', 'the lookback is the one that was chosen up front (63 daily bars, inside the 1-12 '
  + 'month range Moskowitz/Ooi/Pedersen document). Pinned because a lookback later tuned against '
  + 'MOGO outcomes would make the control as overfitted as the thing it controls for', function () {
  return { pass: CFG.lookbackBars === 63 && CFG.atrPeriod === 14 && CFG.targetRR === 2
      && CFG.riskPercent === 1 && CFG.stopATRMultiple === 2,
    detail: JSON.stringify(CFG) };
});

// ══ REPLAY: THE ANTI-LOOK-AHEAD PROPERTIES ═══════════════════════════════════════════════════
//
// A backtest that peeks is worse than no backtest, because it produces a confident wrong number.
// These are the fixtures that make "it does not peek" checkable.

// A series that rises for the lookback, then oscillates enough to hit stops and targets.
function replaySeries(n) {
  const out = [];
  let px = 1.0000;
  for (let i = 0; i < n; i++) {
    px = px + 0.0010;                                   // steady uptrend -> a buy signal
    const wiggle = 0.0040 * Math.sin(i / 3);            // enough range to resolve trades
    out.push({ t: new Date(1000 + i * 86400000),
      o: px, h: px + Math.abs(wiggle) + 0.0020, l: px - Math.abs(wiggle) - 0.0020, c: px });
  }
  return out;
}

t('BTR-1', 'NO LOOK-AHEAD, PROVEN BY TRUNCATION. Running the replay over the full series and over '
  + 'a series cut short must produce IDENTICAL trades for every decision made before the cut. If '
  + 'any future bar leaked into a signal, an entry or a stop, these would diverge', function () {
  const full = replaySeries(LOOKBACK + 120);
  const cut = full.slice(0, LOOKBACK + 60);
  const a = replay(full, CFG, { pair: 'EUR_USD' });
  const b = replay(cut, CFG, { pair: 'EUR_USD' });
  // Compare only the trades that both runs could have decided on: those whose ENTRY bar exists
  // in the short series, and which had already RESOLVED there (a trade still open at the cut is
  // legitimately unresolved in one run and resolved in the other).
  const resolvedInCut = b.trades.filter(function (x) { return !x.stillOpen; });
  const key = function (x) {
    return [x.signalBarIndex, x.entryBarIndex, x.direction, x.entry.toFixed(8),
      x.stop.toFixed(8), x.target.toFixed(8), x.exitBarIndex, x.result].join('|');
  };
  const aByEntry = {}; a.trades.forEach(function (x) { aByEntry[x.entryBarIndex] = x; });
  const mismatches = resolvedInCut.filter(function (x) {
    const m = aByEntry[x.entryBarIndex];
    return !m || key(m) !== key(x);
  });
  return { pass: resolvedInCut.length > 0 && mismatches.length === 0,
    detail: 'compared ' + resolvedInCut.length + ' resolved trade(s), ' + mismatches.length + ' mismatch(es)' };
});

t('BTR-2', 'ENTRY IS THE NEXT BAR\'S OPEN, never the signal bar\'s close. Deciding on a bar and '
  + 'filling inside it is the classic backtest lie and would flatter every number here', function () {
  const s = replaySeries(LOOKBACK + 40);
  const r = replay(s, CFG, { pair: 'EUR_USD' });
  const bad = r.trades.filter(function (x) {
    return x.entryBarIndex !== x.signalBarIndex + 1 || x.entry !== s[x.entryBarIndex].o;
  });
  const alsoNotTheClose = r.trades.filter(function (x) { return x.entry === s[x.signalBarIndex].c; });
  return { pass: r.trades.length > 0 && bad.length === 0 && alsoNotTheClose.length === 0,
    detail: r.trades.length + ' trade(s), ' + bad.length + ' with a wrong entry bar/price' };
});

t('BTR-3', 'the ATR is computed on the SAME prefix the signal saw -- an ATR that included future '
  + 'bars would size the stop with information the trade did not have', function () {
  const s = replaySeries(LOOKBACK + 40);
  const r = replay(s, CFG, { pair: 'EUR_USD' });
  const atrFn = vm.runInContext('calcATR', ctx);
  const bad = r.trades.filter(function (x) {
    const expected = atrFn(s.slice(0, x.signalBarIndex + 1), CFG.atrPeriod);
    return !near(x.atrAtEntry, expected, 1e-12);
  });
  return { pass: r.trades.length > 0 && bad.length === 0,
    detail: r.trades.length + ' trade(s), ' + bad.length + ' with an ATR off the wrong window' };
});

t('BTR-4', 'ONE POSITION AT A TIME. Trades never overlap -- the next entry is at or after the '
  + 'previous exit. Stacking would compound one directional bet and make the per-trade figures '
  + 'describe something other than what they claim', function () {
  const s = replaySeries(LOOKBACK + 200);
  const r = replay(s, CFG, { pair: 'EUR_USD' });
  let overlaps = 0;
  for (let i = 1; i < r.trades.length; i++) {
    if (r.trades[i].entryBarIndex <= r.trades[i - 1].exitBarIndex) overlaps++;
  }
  return { pass: r.trades.length > 1 && overlaps === 0,
    detail: r.trades.length + ' trade(s), ' + overlaps + ' overlap(s)' };
});

t('BTR-5', 'AMBIGUITY IS CONSERVATIVE. A bar that touches stop and target both is booked a Loss, '
  + 'because the walker is ALEX\'s own and resolves it the same way -- a difference in bookkeeping '
  + 'between the arms would show up as a difference in strategy', function () {
  // Build a clean uptrend, then make the bar after entry span both levels.
  const s = replaySeries(LOOKBACK + 5);
  const r0 = replay(s, CFG, { pair: 'EUR_USD' });
  if (!r0.trades.length) return { pass: false, detail: 'no baseline trade to perturb' };
  const e = r0.trades[0];
  const wide = s.slice();
  wide[e.entryBarIndex + 1] = { t: wide[e.entryBarIndex + 1].t, o: e.entry,
    h: e.target + 0.0050, l: e.stop - 0.0050, c: e.entry };
  const r = replay(wide, CFG, { pair: 'EUR_USD' });
  const first = r.trades[0];
  return { pass: !!first && first.ambiguous === true && first.result === 'Loss' && first.resultR === -1,
    detail: first ? first.result + ' ambiguous=' + first.ambiguous : 'no trade' };
});

t('BTR-6', 'A STILL-OPEN TRADE IS NEITHER A WIN NOR A LOSS. resultR is null, so it cannot be '
  + 'silently counted as either when the trades are totalled', function () {
  // A series that trends but never moves enough to resolve the final position.
  const s = replaySeries(LOOKBACK + 3);
  const flat = s.slice();
  for (let i = LOOKBACK + 1; i < flat.length; i++) {
    flat[i] = { t: flat[i].t, o: flat[i].o, h: flat[i].o + 0.00001, l: flat[i].o - 0.00001, c: flat[i].o };
  }
  const r = replay(flat, CFG, { pair: 'EUR_USD' });
  const open = r.trades.filter(function (x) { return x.stillOpen; });
  return { pass: open.length > 0 && open.every(function (x) { return x.resultR === null && x.result === 'Still open'; }),
    detail: open.length + ' still-open trade(s), resultR=' + (open[0] && open[0].resultR) };
});

t('BTR-7', 'the result DECLARES that friction is not modelled. ALEX\'s own replay threads spread '
  + 'and slippage as metadata with zero effect on outcomes, so charging it here would rig the '
  + 'comparison -- both arms are equally optimistic and the output has to say so', function () {
  const r = replay(replaySeries(LOOKBACK + 20), CFG, { pair: 'EUR_USD' });
  return { pass: r.frictionModelled === false && r.entryBasis === 'NEXT_BAR_OPEN'
      && r.ambiguousMode === 'conservative',
    detail: 'friction=' + r.frictionModelled + ' entry=' + r.entryBasis + ' ambiguity=' + r.ambiguousMode };
});

t('BTR-8', 'too little history yields no trades rather than a guess, and the loop terminates on '
  + 'degenerate input instead of spinning', function () {
  const tooShort = replay(replaySeries(LOOKBACK), CFG, { pair: 'EUR_USD' });
  const empty = replay([], CFG, { pair: 'EUR_USD' });
  const nonArray = replay(null, CFG, { pair: 'EUR_USD' });
  return { pass: tooShort.trades.length === 0 && empty.trades.length === 0 && nonArray.trades.length === 0,
    detail: [tooShort.trades.length, empty.trades.length, nonArray.trades.length].join(',') };
});

t('BTR-9', 'a bar that cannot produce geometry is RECORDED as skipped, not silently dropped -- a '
  + 'missing trade is a fact about coverage, and coverage is how a backtest quietly stops '
  + 'describing the period it claims to', function () {
  // A signal WITHOUT a usable ATR. One early jump makes the lookback return non-zero, then every
  // later bar has zero range, so the last `atrPeriod` true ranges are all 0 and the ATR is 0.
  // Geometry then refuses rather than inventing a stop -- and the refusal must be recorded.
  const flat = [];
  for (let i = 0; i < LOOKBACK + 12; i++) {
    const px = i < 6 ? 1.1 : 1.11;                 // the jump sits well outside the ATR window
    flat.push({ t: new Date(1000 + i * 86400000), o: px, h: px, l: px, c: px });
  }
  const r = replay(flat, CFG, { pair: 'EUR_USD' });
  return { pass: r.skipped.length > 0 && r.skipped.every(function (x) { return !!x.reason; }),
    detail: r.skipped.length + ' skipped, first reason=' + (r.skipped[0] && r.skipped[0].reason) };
});

t('BTR-10', 'JPY pips are handled -- risk in pips uses the instrument\'s own pip size, so a '
  + 'USD_JPY trade is not reported with a 100x risk distance', function () {
  const s = replaySeries(LOOKBACK + 40).map(function (c) {
    return { t: c.t, o: c.o * 145, h: c.h * 145, l: c.l * 145, c: c.c * 145 };
  });
  const eur = replay(replaySeries(LOOKBACK + 40), CFG, { pair: 'EUR_USD' });
  const jpy = replay(s, CFG, { pair: 'USD_JPY' });
  // Same shape scaled by 145, and JPY pips are 100x larger, so risk in PIPS lands in the same
  // ballpark rather than 100x apart.
  const ratio = jpy.trades[0].riskPips / eur.trades[0].riskPips;
  return { pass: jpy.trades.length > 0 && ratio > 0.5 && ratio < 2.5,
    detail: 'eur ' + eur.trades[0].riskPips.toFixed(1) + 'p vs jpy ' + jpy.trades[0].riskPips.toFixed(1) + 'p (ratio ' + ratio.toFixed(2) + ')' };
});

// ══ EXPORT: THE PACKAGE MUST BE UNMISTAKABLY A REPLAY ════════════════════════════════════════
//
// This project has already published a conclusion built by counting backtests as live trades. The
// export is the seam where that could happen again, so these fixtures are about labelling and
// about refusing to invent numbers the replay does not have.

function runFor(pair) {
  return replay(replaySeries(LOOKBACK + 200), CFG, { pair: pair || 'EUR_USD', timeframe: 'D' });
}

t('BTX-1', 'the package is stamped REPLAY_RUN and mode REPLAY at the top level. The analysis tool '
  + 'partitions on exactly this field, and a replay reaching a forward figure is the defect that '
  + 'produced a +20.97R claim where the real forward result was -7.04R', function () {
  const p = buildPkg([runFor('EUR_USD')], CFG, { stamp: 1 });
  return { pass: p.captureBasis === 'REPLAY_RUN' && p.identity.mode === 'REPLAY'
      && p.identity.strategyId === 'baseline_trend_v1',
    detail: p.captureBasis + ' / ' + p.identity.mode };
});

t('BTX-2', 'it uses the EXISTING evidence-package shape, so the existing analyser reads it with '
  + 'no change. A second format would mean a second reader, and a second place for a replay '
  + 'number to be mistaken for a forward one', function () {
  const p = buildPkg([runFor()], CFG, { stamp: 1 });
  const o = p.objects;
  return { pass: p.packageSchemaVersion === 'mogo.evidence-package.v1'
      && Array.isArray(o.positions) && Array.isArray(o.outcomes) && Array.isArray(o.qualifiedSetups)
      && o.positions.length > 0 && o.positions.length === o.outcomes.length,
    detail: o.positions.length + ' positions, ' + o.outcomes.length + ' outcomes' };
});

t('BTX-3', 'every position is joined to its outcome by positionId -- an unmatched pair would be '
  + 'silently dropped by the analyser and shrink the sample without saying so', function () {
  const p = buildPkg([runFor()], CFG, { stamp: 1 });
  const ids = {}; p.objects.outcomes.forEach(function (o) { ids[o.positionId] = 1; });
  const orphans = p.objects.positions.filter(function (x) { return !ids[x.positionId]; });
  return { pass: p.objects.positions.length > 0 && orphans.length === 0,
    detail: orphans.length + ' orphan(s) of ' + p.objects.positions.length };
});

t('BTX-4', 'STILL-OPEN TRADES ARE NOT EXPORTED as outcomes, and the count of what was withheld is '
  + 'stated. An outcome with a null R invites a reader to treat it as a zero', function () {
  const flat = replaySeries(LOOKBACK + 3);
  for (let i = LOOKBACK + 1; i < flat.length; i++) {
    flat[i] = { t: flat[i].t, o: flat[i].o, h: flat[i].o + 0.00001, l: flat[i].o - 0.00001, c: flat[i].o };
  }
  const run = replay(flat, CFG, { pair: 'EUR_USD' });
  const openCount = run.trades.filter(function (x) { return x.stillOpen; }).length;
  const p = buildPkg([run], CFG, { stamp: 1 });
  return { pass: openCount > 0 && p.replayDisclosures.stillOpenExcluded === openCount
      && p.objects.outcomes.every(function (o) { return o.realizedR !== null; }),
    detail: openCount + ' open, excluded=' + p.replayDisclosures.stillOpenExcluded };
});

t('BTX-5', 'SPREAD IS ABSENT, NOT ZERO. It is genuinely not modelled, and a recorded zero would '
  + 'be averaged into the analyser\'s spread statistics as a fiction rather than excluded as '
  + 'unknown', function () {
  const p = buildPkg([runFor()], CFG, { stamp: 1 });
  const withSpread = p.objects.positions.filter(function (x) { return x.entrySpreadPips !== undefined; });
  return { pass: p.objects.positions.length > 0 && withSpread.length === 0,
    detail: withSpread.length + ' position(s) carry a spread field' };
});

t('BTX-6', 'PNL IS ABSENT for the same reason -- there is no account, no position size and no '
  + 'friction here, so a currency figure would be invented', function () {
  const p = buildPkg([runFor()], CFG, { stamp: 1 });
  const withPnl = p.objects.outcomes.filter(function (x) { return x.pnl !== undefined; });
  return { pass: withPnl.length === 0, detail: withPnl.length + ' outcome(s) carry a pnl' };
});

t('BTX-7', 'the caveats travel WITH the file. Friction, entry basis, ambiguity handling, the '
  + 'look-ahead control and the shared exit engine are all recorded in the package, not left in '
  + 'someone\'s memory of the conversation where the numbers were produced', function () {
  const d = buildPkg([runFor()], CFG, { stamp: 1 }).replayDisclosures;
  return { pass: d.frictionModelled === false && /not charged/i.test(d.frictionNote)
      && d.entryBasis === 'NEXT_BAR_OPEN' && d.ambiguousMode === 'conservative'
      && /truncation/i.test(d.lookAheadControl) && /alexGWalkOutcome/.test(d.exitEngine),
    detail: Object.keys(d).join(',') };
});

t('BTX-8', 'R is carried on BOTH realizedR and recordedResultR and they agree -- the analyser '
  + 'prefers realizedR, and a package where the two disagreed would report a different sample '
  + 'depending on which field a reader happened to use', function () {
  const p = buildPkg([runFor()], CFG, { stamp: 1 });
  const bad = p.objects.outcomes.filter(function (o) { return o.realizedR !== o.recordedResultR; });
  const wins = p.objects.outcomes.filter(function (o) { return o.exitReasonCode === 'Win'; });
  return { pass: bad.length === 0 && wins.every(function (o) { return o.realizedR === CFG.targetRR; }),
    detail: bad.length + ' disagreement(s); ' + wins.length + ' win(s) all at +' + CFG.targetRR + 'R' };
});

t('BTX-9', 'multiple pairs merge into one package without colliding -- ids carry the instrument, '
  + 'so two pairs cannot overwrite each other\'s trades', function () {
  const p = buildPkg([runFor('EUR_USD'), runFor('USD_JPY')], CFG, { stamp: 1 });
  const ids = p.objects.positions.map(function (x) { return x.positionId; });
  const unique = {}; ids.forEach(function (i) { unique[i] = 1; });
  const instruments = {}; p.objects.positions.forEach(function (x) { instruments[x.instrument] = 1; });
  return { pass: ids.length === Object.keys(unique).length && Object.keys(instruments).length === 2,
    detail: ids.length + ' ids, ' + Object.keys(unique).length + ' unique, ' + Object.keys(instruments).length + ' instruments' };
});

t('BTX-10', 'an errored or empty run contributes nothing rather than throwing -- one pair failing '
  + 'to fetch must not lose the other eleven', function () {
  const p = buildPkg([{ pair: 'X', error: 'fetch failed' }, null, { pair: 'Y', trades: [] }, runFor()], CFG, { stamp: 1 });
  return { pass: p.objects.positions.length > 0,
    detail: p.objects.positions.length + ' position(s) survived a failed run in the list' };
});

t('BTX-11', 'the config used is snapshotted into the package, so a result can never be read '
  + 'against a lookback it was not produced with', function () {
  const p = buildPkg([runFor()], CFG, { stamp: 1 });
  return { pass: p.configSnapshot.config.lookbackBars === CFG.lookbackBars
      && p.configSnapshot.config.stopATRMultiple === CFG.stopATRMultiple
      && p.configSnapshotProvenance === 'OBSERVED',
    detail: JSON.stringify(p.configSnapshot.config) };
});

t('BTX-12', 'the workspace panel exists in the markup and the manifest points at it, so opening '
  + 'the strategy shows the control arm rather than routing nowhere', function () {
  const m = /const BASELINE_TREND_MANIFEST=\{[\s\S]*?\n\};/.exec(SRC)[0];
  return { pass: /panelId:'baselinetrend'/.test(m) && /navLabel:/.test(m)
      && SRC.indexOf('id="panel-baselinetrend"') >= 0,
    detail: 'panel present=' + (SRC.indexOf('id="panel-baselinetrend"') >= 0) };
});

results.forEach(function (r) {
  console.log((r.pass ? 'PASS' : 'FAIL') + ' -- ' + r.name + ': ' + r.desc + (r.detail ? '  [' + r.detail + ']' : ''));
});
const fails = results.filter(function (r) { return !r.pass; }).length;
console.log('---');
console.log(results.length + ' fixtures, ' + (results.length - fails) + ' PASS, ' + fails + ' FAIL');
process.exitCode = fails ? 1 : 0;

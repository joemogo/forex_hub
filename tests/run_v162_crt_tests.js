#!/usr/bin/env node
'use strict';
// ══════════════════════════════════════════════════════════════════════════════════════════════
// v12.61.0 — CANDLE RANGE THEORY, AND THE CONTROL THAT MAKES IT FALSIFIABLE
// ══════════════════════════════════════════════════════════════════════════════════════════════
//
// CRT states a three-bar pattern: candle 1 sets a range, candle 2 takes out one extreme, candle 3
// closes back inside. Stop beyond the swept extreme, target the opposite edge of candle 1.
//
// A profitable result would prove nothing on its own. Mean reversion after a probe at a recent
// extreme is not a claim unique to CRT, and an arm that only tests swept windows cannot tell the
// two apart. So the identical rule also runs on windows where candle 2 stayed INSIDE the range.
// CRT-C1..C6 are that control, and CRT-C4 is the fixture that matters most: the two arms must be
// capable of producing DIFFERENT results on the same bars, or the comparison is theatre.
//
// CRT-1 pins the look-ahead property by truncation: trades that opened AND closed inside a prefix
// must be byte-identical whether the walker was given the prefix or the whole series. If they are
// not, the arm is reading its own future and every figure it produces is worthless.
//
// CRT-R1..R4 are here because this arm breaks a convention every other MOGO arm follows. The
// target is the opposite range extreme, so planned R is NOT fixed at 2 -- and a sweep, by
// definition, pushes the stop further from the target and LOWERS planned R. That is a confound
// between the arms, not an edge, and it has to be visible in the output rather than discovered
// later by whoever reads the numbers.
//
// Run:  node tests/run_v162_crt_tests.js

const fs = require('fs');
const path = require('path');
const vm = require('vm');
const ROOT = path.resolve(__dirname, '..');
const SRC = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');

function fn(name) {
  const m = new RegExp('(?:async\\s+)?function\\s+' + name + '\\s*\\(').exec(SRC);
  if (!m) throw new Error('not found: ' + name);
  const open = SRC.indexOf('{', m.index);
  let d = 0, i = open;
  for (; i < SRC.length; i++) {
    if (SRC[i] === '{') d++;
    else if (SRC[i] === '}') { d--; if (d === 0) break; }
  }
  return SRC.slice(m.index, i + 1);
}
function constBlock(decl) {
  const i = SRC.indexOf(decl);
  if (i < 0) throw new Error('not found: ' + decl);
  let depth = 0, q = null, k = i;
  for (; k < SRC.length; k++) {
    const c = SRC[k], p = SRC[k - 1];
    if (q) { if (c === q && p !== '\\') q = null; continue; }
    if (c === '"' || c === "'" || c === '`') { q = c; continue; }
    if (c === '/' && SRC[k + 1] === '/') { while (k < SRC.length && SRC[k] !== '\n') k++; continue; }
    if (c === '(' || c === '[' || c === '{') depth++;
    else if (c === ')' || c === ']' || c === '}') depth--;
    else if (c === ';' && depth === 0) break;
  }
  return SRC.slice(i, k + 1);
}
// Strips `//` comments before a source assertion. Added after a v12.56.0 fixture matched its own
// explanatory comment and survived a mutation that broke the code it was guarding.
function codeOf(src) {
  return src.split('\n').map(function (ln) {
    const i = ln.indexOf('//');
    if (i < 0) return ln;
    const before = ln.slice(0, i);
    const q = (before.match(/'/g) || []).length, d = (before.match(/"/g) || []).length,
          b = (before.match(/`/g) || []).length;
    return (q % 2 || d % 2 || b % 2) ? ln : before;
  }).join('\n');
}

const ctx = { console: console, Math: Math, JSON: JSON, isFinite: isFinite, Array: Array,
  Number: Number, Object: Object, String: String, Date: Date, isNaN: isNaN };
vm.createContext(ctx);
vm.runInContext("const APP_VERSION='" + (/const APP_VERSION='([^']+)'/.exec(SRC)[1]) + "';", ctx);
vm.runInContext(constBlock("const CRT_STRATEGY_ID="), ctx);
vm.runInContext(constBlock("const CRT_VERSION="), ctx);
vm.runInContext(constBlock('const RULES_CRT='), ctx);
['pipSize', 'calcATR', 'getNYOffsetMinutes', 'nyAlignedClose', 'getCandleCloseTime',
  'alexGWalkOutcome', 'alexGComputeMAEMFE',
  'crtSignal', 'crtGeometry', 'crtReplayTrades', 'crtRunBothArms', 'crtCompareArms',
  'crtBuildReplayPackage']
  .forEach(function (n) { vm.runInContext(fn(n), ctx); });
const P = ctx;
const CFG = vm.runInContext('RULES_CRT.config', ctx);
const SWEPT = Object.assign({}, CFG, { requireSweep: true });
const CONTROL = Object.assign({}, CFG, { requireSweep: false });
const PIP = 0.0001;

// ── candle helpers ───────────────────────────────────────────────────────────────────────────
let T = 1700000000000;
// `t` is a Date, not a number: getCandleCloseTime calls start.getTime() on the LAST candle, so a
// numeric timestamp throws there and only there. Matching the real shape, not the passing one.
function bar(o, h, l, c) { const b = { t: new Date(T), o: o, h: h, l: l, c: c }; T += 4 * 3600000; return b; }
// A flat run that gives calcATR something to chew on without producing setups of its own.
function flat(n, base) {
  const out = [];
  for (let i = 0; i < n; i++) {
    const p = base + (i % 2 ? 0.00020 : -0.00020);
    out.push(bar(p, p + 0.00060, p - 0.00060, p));
  }
  return out;
}
// The three-bar window under test, appended to a flat prefix so the ATR is real.
function window3(c1, c2, c3) { return flat(30, 1.10000).concat([c1, c2, c3]); }
// Candle 1: a 40-pip range around 1.10000. Wide enough to clear minRangeATRMultiple by a margin,
// so a fixture never passes or fails on the degeneracy guard by accident.
const C1 = function () { return bar(1.10000, 1.10200, 1.09800, 1.10000); };
const RANGE_HIGH = 1.10200, RANGE_LOW = 1.09800;

const results = [];
function t(name, desc, f) {
  let pass = false, detail = '';
  try { const r = f(); pass = !!(r && r.pass); detail = (r && r.detail) || ''; }
  catch (e) { pass = false; detail = 'threw: ' + (e && e.message ? e.message : String(e)); }
  results.push({ name: name, desc: desc, pass: pass, detail: detail });
}

// ══ THE PATTERN ═══════════════════════════════════════════════════════════════════════════════

t('CRT-2', 'candle 2 sweeping the HIGH gives a SELL, anchored on the swept extreme and targeting '
  + 'the opposite edge of candle 1 -- the source-stated geometry, not a fixed 2R', function () {
  const s = P.crtSignal(window3(C1(), bar(1.10000, 1.10300, 1.10000, 1.10100),
    bar(1.10100, 1.10150, 1.10000, 1.10050)), SWEPT, PIP);
  return { pass: !!s && s.direction === 'sell' && s.swept === true
      && s.anchorExtreme === 1.10300 && s.targetLevel === RANGE_LOW,
    detail: s ? s.direction + ' anchor=' + s.anchorExtreme + ' target=' + s.targetLevel : 'no signal' };
});

t('CRT-3', 'candle 2 sweeping the LOW gives a BUY, mirrored exactly', function () {
  const s = P.crtSignal(window3(C1(), bar(1.10000, 1.10000, 1.09700, 1.09900),
    bar(1.09900, 1.10000, 1.09850, 1.09950)), SWEPT, PIP);
  return { pass: !!s && s.direction === 'buy' && s.swept === true
      && s.anchorExtreme === 1.09700 && s.targetLevel === RANGE_HIGH,
    detail: s ? s.direction + ' anchor=' + s.anchorExtreme + ' target=' + s.targetLevel : 'no signal' };
});

t('CRT-4', 'candle 2 taking BOTH extremes is refused. The pattern names one sweep; which side it '
  + 'implies is genuinely ambiguous, and a tie-break nobody stated would be invented', function () {
  const s = P.crtSignal(window3(C1(), bar(1.10000, 1.10300, 1.09700, 1.10000),
    bar(1.10000, 1.10100, 1.09900, 1.10000)), SWEPT, PIP);
  return { pass: s === null, detail: s ? 'RESOLVED to ' + s.direction : 'refused' };
});

t('CRT-5', 'candle 3 must close back INSIDE the range. A close beyond it is a break, and this arm '
  + 'does not trade breaks -- without this the rule is just "price swept an extreme"', function () {
  const outside = P.crtSignal(window3(C1(), bar(1.10000, 1.10300, 1.10000, 1.10250),
    bar(1.10250, 1.10300, 1.10210, 1.10260)), SWEPT, PIP);
  const inside = P.crtSignal(window3(C1(), bar(1.10000, 1.10300, 1.10000, 1.10250),
    bar(1.10250, 1.10300, 1.10000, 1.10050)), SWEPT, PIP);
  return { pass: outside === null && !!inside,
    detail: 'close outside -> ' + (outside ? 'ACCEPTED' : 'refused') + '; close inside -> '
      + (inside ? 'accepted' : 'REFUSED') };
});

t('CRT-6', 'a close exactly ON a range boundary is refused. Inside is asserted strictly, so a '
  + 'boundary close cannot be counted as a reclaim it did not achieve', function () {
  const s = P.crtSignal(window3(C1(), bar(1.10000, 1.10300, 1.10000, 1.10250),
    bar(1.10250, 1.10300, 1.10100, RANGE_HIGH)), SWEPT, PIP);
  return { pass: s === null, detail: s ? 'ACCEPTED a boundary close' : 'refused' };
});

t('CRT-7', 'a degenerate candle 1 is refused in BOTH arms. When the range collapses toward zero '
  + 'so do the stop and target distances, and the resulting R is arithmetic noise', function () {
  const tiny = bar(1.10000, 1.10004, 1.09996, 1.10000);
  const sw = P.crtSignal(flat(30, 1.10000).concat([tiny,
    bar(1.10000, 1.10010, 1.10000, 1.10005), bar(1.10000, 1.10002, 1.09998, 1.10000)]), SWEPT, PIP);
  const cn = P.crtSignal(flat(30, 1.10000).concat([tiny,
    bar(1.10000, 1.10003, 1.09997, 1.10000), bar(1.10000, 1.10002, 1.09998, 1.10000)]), CONTROL, PIP);
  return { pass: sw === null && cn === null,
    detail: 'swept -> ' + (sw ? 'ACCEPTED' : 'refused') + '; control -> ' + (cn ? 'ACCEPTED' : 'refused') };
});

// ══ THE CONTROL ═══════════════════════════════════════════════════════════════════════════════

t('CRT-C1', 'the control refuses a SWEPT window. If it accepted them the two arms would overlap '
  + 'and the difference between them would measure nothing', function () {
  const s = P.crtSignal(window3(C1(), bar(1.10000, 1.10300, 1.10000, 1.10100),
    bar(1.10100, 1.10150, 1.10000, 1.10050)), CONTROL, PIP);
  return { pass: s === null, detail: s ? 'control ACCEPTED a swept window' : 'refused' };
});

t('CRT-C2', 'the swept arm refuses an UNSWEPT window -- the same exclusion in the other direction',
  function () {
  const s = P.crtSignal(window3(C1(), bar(1.10000, 1.10180, 1.10000, 1.10100),
    bar(1.10100, 1.10150, 1.10000, 1.10050)), SWEPT, PIP);
  return { pass: s === null, detail: s ? 'swept arm ACCEPTED an unswept window' : 'refused' };
});

t('CRT-C3', 'the control takes its direction from the extreme candle 2 came NEAREST to, which is '
  + 'the closest analogue of "which side was probed" available without a breach', function () {
  const nearHigh = P.crtSignal(window3(C1(), bar(1.10000, 1.10180, 1.10000, 1.10100),
    bar(1.10100, 1.10150, 1.10000, 1.10050)), CONTROL, PIP);
  const nearLow = P.crtSignal(window3(C1(), bar(1.10000, 1.10000, 1.09820, 1.09900),
    bar(1.09900, 1.10000, 1.09850, 1.09950)), CONTROL, PIP);
  return { pass: !!nearHigh && nearHigh.direction === 'sell' && nearHigh.anchorExtreme === 1.10180
      && !!nearLow && nearLow.direction === 'buy' && nearLow.anchorExtreme === 1.09820,
    detail: 'near high -> ' + (nearHigh && nearHigh.direction) + '; near low -> ' + (nearLow && nearLow.direction) };
});

t('CRT-C4', 'THE ONE THAT MATTERS: on the same random series both arms produce trades, in numbers '
  + 'of the same order. An arm that is starved cannot falsify anything, and one that fires on '
  + 'everything is not a control', function () {
  let seed = 4242;
  const rnd = function () { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff; };
  const series = []; let px = 1.10000, tt = 1700000000000;
  for (let i = 0; i < 3000; i++) {
    const o = px, c2 = px + (rnd() - 0.5) * 0.0020;
    series.push({ t: new Date(tt), o: o, h: Math.max(o, c2) + rnd() * 0.0008,
      l: Math.min(o, c2) - rnd() * 0.0008, c: c2 });
    px = c2; tt += 4 * 3600000;
  }
  const both = P.crtRunBothArms(series, CFG, { pair: 'EUR_USD', timeframe: 'H4' });
  const a = both.swept.trades.length, b = both.control.trades.length;
  const ratio = Math.max(a, b) / Math.max(1, Math.min(a, b));
  return { pass: a > 0 && b > 0 && ratio <= 8,
    detail: 'swept ' + a + ' vs control ' + b + ' (ratio ' + ratio.toFixed(2) + ')' };
});

t('CRT-C5', 'a control window with candle 2 exactly equidistant from both extremes is refused. '
  + 'There is no nearer side, so there is no direction, and none is invented', function () {
  const s = P.crtSignal(window3(C1(), bar(1.10000, 1.10150, 1.09850, 1.10000),
    bar(1.10000, 1.10100, 1.09900, 1.10000)), CONTROL, PIP);
  return { pass: s === null, detail: s ? 'INVENTED direction ' + s.direction : 'refused' };
});

t('CRT-C6', 'both arms are walked over the SAME candles in one pass, and differ ONLY in '
  + 'requireSweep. A control compared against a different dataset is not a control', function () {
  const src = codeOf(fn('crtRunBothArms'));
  const onlySweepDiffers = /requireSweep:true/.test(src) && /requireSweep:false/.test(src)
    && (src.match(/Object\.assign\(\{\},base,\{/g) || []).length === 2;
  // Behavioural, not just textual: each arm run on its own over the identical candles must
  // reproduce what the paired run produced. barsScanned is deliberately NOT asserted equal --
  // an arm that opens a trade skips its index to the exit bar, so the arm that trades more
  // scans fewer bars, and pinning them equal would only pass while one arm was starved.
  let seed = 8181;
  const rnd = function () { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff; };
  const series = []; let px = 1.10000, tt = 1700000000000;
  for (let i = 0; i < 900; i++) {
    const o = px + (rnd() - 0.5) * 0.0004, c2 = o + (rnd() - 0.5) * 0.0020;
    series.push({ t: new Date(tt), o: o, h: Math.max(o, c2) + rnd() * 0.0008,
      l: Math.min(o, c2) - rnd() * 0.0008, c: c2 });
    px = c2; tt += 4 * 3600000;
  }
  const both = P.crtRunBothArms(series, CFG, { pair: 'EUR_USD', timeframe: 'H4' });
  const soloS = P.crtReplayTrades(series, SWEPT, { pair: 'EUR_USD', timeframe: 'H4' });
  const soloC = P.crtReplayTrades(series, CONTROL, { pair: 'EUR_USD', timeframe: 'H4' });
  const same = JSON.stringify(both.swept.trades) === JSON.stringify(soloS.trades)
    && JSON.stringify(both.control.trades) === JSON.stringify(soloC.trades);
  return { pass: onlySweepDiffers && both.sameCandles === true && same
      && both.candlesUsed === series.length && soloS.trades.length > 0 && soloC.trades.length > 0,
    detail: 'arms differ only in requireSweep; each reproduces its solo run over the same '
      + both.candlesUsed + ' candles' };
});

// ══ GEOMETRY ══════════════════════════════════════════════════════════════════════════════════

t('CRT-8', 'the stop sits BEYOND the anchor extreme on the correct side, buffered. A stop resting '
  + 'exactly on the wick tip is taken out by its own bar', function () {
  const sell = P.crtGeometry({ direction: 'sell', anchorExtreme: 1.10300, targetLevel: RANGE_LOW, atr: 0.0010 },
    1.10100, CFG);
  const buy = P.crtGeometry({ direction: 'buy', anchorExtreme: 1.09700, targetLevel: RANGE_HIGH, atr: 0.0010 },
    1.09900, CFG);
  const buf = CFG.stopBufferATRMultiple * 0.0010;
  return { pass: !!sell && Math.abs(sell.stop - (1.10300 + buf)) < 1e-12 && sell.stop > 1.10300
      && !!buy && Math.abs(buy.stop - (1.09700 - buf)) < 1e-12 && buy.stop < 1.09700,
    detail: 'sell stop ' + (sell && sell.stop) + ' > 1.10300; buy stop ' + (buy && buy.stop) + ' < 1.09700' };
});

t('CRT-9', 'the target is the opposite range extreme EXACTLY, not a multiple of the risk', function () {
  const g = P.crtGeometry({ direction: 'sell', anchorExtreme: 1.10300, targetLevel: RANGE_LOW, atr: 0.0010 },
    1.10100, CFG);
  return { pass: !!g && g.target === RANGE_LOW,
    detail: g ? 'target ' + g.target + ' (range low ' + RANGE_LOW + ')' : 'no geometry' };
});

t('CRT-10', 'geometry fails CLOSED when the next bar opened past its own stop -- that is not this '
  + 'trade with a poor R, it is not this trade at all', function () {
  const g = P.crtGeometry({ direction: 'sell', anchorExtreme: 1.10300, targetLevel: RANGE_LOW, atr: 0.0010 },
    1.10400, CFG);
  return { pass: g === null, detail: g ? 'INVENTED geometry with risk ' + (g.stop - 1.10400) : 'refused' };
});

t('CRT-11', 'geometry fails CLOSED when the next bar opened through its own target', function () {
  const g = P.crtGeometry({ direction: 'sell', anchorExtreme: 1.10300, targetLevel: RANGE_LOW, atr: 0.0010 },
    1.09700, CFG);
  return { pass: g === null, detail: g ? 'INVENTED geometry with reward ' + (1.09700 - RANGE_LOW) : 'refused' };
});

t('CRT-12', 'a non-finite or non-positive ATR yields null rather than a position with an invented '
  + 'stop. An invented stop is how a control arm quietly becomes a different experiment', function () {
  const bad = [0, -1, NaN, Infinity, null, undefined].map(function (a) {
    return P.crtGeometry({ direction: 'sell', anchorExtreme: 1.10300, targetLevel: RANGE_LOW, atr: a }, 1.10100, CFG);
  });
  return { pass: bad.every(function (x) { return x === null; }),
    detail: bad.filter(function (x) { return x !== null; }).length + ' bad ATRs produced geometry' };
});

// ══ PLANNED R IS NOT FIXED, AND THAT IS A CONFOUND ════════════════════════════════════════════

t('CRT-R1', 'planned R is COMPUTED from the geometry, not fixed at 2 the way every other MOGO arm '
  + 'fixes it. CRT states the target as the opposite range extreme, so R follows the bars', function () {
  const g = P.crtGeometry({ direction: 'sell', anchorExtreme: 1.10300, targetLevel: RANGE_LOW, atr: 0.0010 },
    1.10100, CFG);
  const risk = g.stop - 1.10100, reward = 1.10100 - RANGE_LOW;
  return { pass: !!g && Math.abs(g.plannedRR - reward / risk) < 1e-12 && Math.abs(g.plannedRR - 2) > 0.01,
    detail: 'plannedRR ' + g.plannedRR.toFixed(4) + ' = reward/risk, and is not 2' };
});

t('CRT-R2', 'planned R VARIES across setups. If it were constant in practice the confound would be '
  + 'harmless and the reporting below would be decoration', function () {
  const a = P.crtGeometry({ direction: 'sell', anchorExtreme: 1.10300, targetLevel: RANGE_LOW, atr: 0.0010 }, 1.10100, CFG);
  const b = P.crtGeometry({ direction: 'sell', anchorExtreme: 1.10230, targetLevel: RANGE_LOW, atr: 0.0010 }, 1.10100, CFG);
  return { pass: Math.abs(a.plannedRR - b.plannedRR) > 0.1,
    detail: 'two setups on the same range: R = ' + a.plannedRR.toFixed(3) + ' and ' + b.plannedRR.toFixed(3) };
});

t('CRT-R3', 'THE CONFOUND, STATED: a wider sweep pushes the stop further from the target and '
  + 'LOWERS planned R by itself. So the swept arm can differ from the control in R before it '
  + 'differs in edge', function () {
  const near = P.crtGeometry({ direction: 'sell', anchorExtreme: 1.10210, targetLevel: RANGE_LOW, atr: 0.0010 }, 1.10100, CFG);
  const far = P.crtGeometry({ direction: 'sell', anchorExtreme: 1.10400, targetLevel: RANGE_LOW, atr: 0.0010 }, 1.10100, CFG);
  return { pass: far.plannedRR < near.plannedRR,
    detail: 'shallow anchor R ' + near.plannedRR.toFixed(3) + ' > deep anchor R ' + far.plannedRR.toFixed(3) };
});

t('CRT-R4', 'so the comparison REPORTS mean planned R per arm. A reader who cannot see this cannot '
  + 'tell a geometry difference from an edge difference', function () {
  const cmp = P.crtCompareArms({
    swept: { trades: [{ resultR: 1.5, plannedRR: 1.5 }, { resultR: -1, plannedRR: 1.1 }], skipped: [], barsScanned: 9 },
    control: { trades: [{ resultR: 3.0, plannedRR: 3.0 }, { resultR: -1, plannedRR: 2.8 }], skipped: [], barsScanned: 9 }
  });
  return { pass: !!cmp && cmp.swept.meanPlannedRR != null && cmp.control.meanPlannedRR != null
      && Math.abs(cmp.plannedRRDifference - (1.3 - 2.9)) < 1e-9,
    detail: 'swept meanR ' + cmp.swept.meanPlannedRR.toFixed(2) + ', control ' + cmp.control.meanPlannedRR.toFixed(2)
      + ', difference ' + cmp.plannedRRDifference.toFixed(2) };
});

t('CRT-R5', 'a win is booked at its OWN planned R and a loss at exactly -1R. Booking wins at a '
  + 'flat 2R would pay this arm for reward it never had', function () {
  let seed = 77;
  const rnd = function () { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff; };
  const series = []; let px = 1.10000, tt = 1700000000000;
  for (let i = 0; i < 1500; i++) {
    const o = px, c2 = px + (rnd() - 0.5) * 0.0020;
    series.push({ t: new Date(tt), o: o, h: Math.max(o, c2) + rnd() * 0.0008,
      l: Math.min(o, c2) - rnd() * 0.0008, c: c2 });
    px = c2; tt += 4 * 3600000;
  }
  const r = P.crtReplayTrades(series, SWEPT, { pair: 'EUR_USD', timeframe: 'H4' });
  const closed = r.trades.filter(function (x) { return !x.stillOpen; });
  const wins = closed.filter(function (x) { return x.result === 'Win'; });
  const losses = closed.filter(function (x) { return x.result !== 'Win'; });
  const okW = wins.every(function (x) { return Math.abs(x.resultR - x.plannedRR) < 1e-12; });
  const okL = losses.every(function (x) { return x.resultR === -1; });
  const varied = new Set(wins.map(function (x) { return x.resultR.toFixed(3); })).size > 1;
  return { pass: closed.length > 20 && wins.length > 1 && okW && okL && varied,
    detail: closed.length + ' closed, ' + wins.length + ' wins booked at their own R ('
      + new Set(wins.map(function (x) { return x.resultR.toFixed(3); })).size + ' distinct), losses at -1R' };
});

// ══ LOOK-AHEAD ════════════════════════════════════════════════════════════════════════════════

t('CRT-1', 'THE ONE THAT INVALIDATES EVERYTHING IF IT FAILS: every trade the walker opened must '
  + 'be re-derivable from the prefix ENDING at its own signal bar. If the walker saw even one bar '
  + 'past the decision, the arm is trading its own future and every figure it produces is worthless',
  function () {
  // WHY THIS SHAPE. The first version of this fixture truncated the SERIES at a fixed index and
  // compared the trades that resolved inside it. That survived a mutation widening the signal
  // window to candles.slice(0,i+2) -- because the extra bar was still inside the truncated
  // series, so both runs read it and agreed with each other. Agreement between two runs that
  // BOTH cheat is not a look-ahead test. This re-derives each decision from the prefix that ends
  // at the decision bar, which is the only series that cannot contain the future.
  let seed = 20260906;
  const rnd = function () { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff; };
  const series = []; let px = 1.10000, tt = 1700000000000;
  for (let i = 0; i < 1200; i++) {
    const o = px + (rnd() - 0.5) * 0.0004, c2 = o + (rnd() - 0.5) * 0.0020;
    series.push({ t: new Date(tt), o: o, h: Math.max(o, c2) + rnd() * 0.0008,
      l: Math.min(o, c2) - rnd() * 0.0008, c: c2 });
    px = c2; tt += 4 * 3600000;
  }
  const run = P.crtReplayTrades(series, SWEPT, { pair: 'EUR_USD', timeframe: 'H4' });
  const bad = [];
  run.trades.forEach(function (x) {
    const prefix = series.slice(0, x.signalBarIndex + 1);   // ends AT the decision bar
    const sig = P.crtSignal(prefix, SWEPT, PIP);
    if (!sig) { bad.push(x.signalBarIndex + ':no signal from the prefix alone'); return; }
    if (sig.direction !== x.direction) bad.push(x.signalBarIndex + ':direction');
    if (sig.anchorExtreme !== x.anchorExtreme) bad.push(x.signalBarIndex + ':anchor');
    if (sig.targetLevel !== x.target) bad.push(x.signalBarIndex + ':target');
    if (sig.rangeHigh !== x.rangeHigh || sig.rangeLow !== x.rangeLow) bad.push(x.signalBarIndex + ':range');
  });
  return { pass: run.trades.length > 30 && bad.length === 0,
    detail: run.trades.length + ' trades, all re-derived from their own prefix'
      + (bad.length ? '; MISMATCHES: ' + bad.slice(0, 5).join(', ') : '') };
});

t('CRT-1b', 'and the ATR is bound by the same rule. A volatility figure computed over bars the '
  + 'decision could not have seen sizes every stop in the arm from the future', function () {
  let seed = 5150;
  const rnd = function () { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff; };
  const series = []; let px = 1.10000, tt = 1700000000000;
  for (let i = 0; i < 800; i++) {
    const o = px + (rnd() - 0.5) * 0.0004, c2 = o + (rnd() - 0.5) * 0.0020;
    series.push({ t: new Date(tt), o: o, h: Math.max(o, c2) + rnd() * 0.0008,
      l: Math.min(o, c2) - rnd() * 0.0008, c: c2 });
    px = c2; tt += 4 * 3600000;
  }
  const run = P.crtReplayTrades(series, SWEPT, { pair: 'EUR_USD', timeframe: 'H4' });
  const bad = run.trades.filter(function (x) {
    const sig = P.crtSignal(series.slice(0, x.signalBarIndex + 1), SWEPT, PIP);
    return !sig || Math.abs(sig.atr - x.atrAtEntry) > 1e-15;
  });
  // Non-vacuous: the ATR must actually MOVE across the run, or an equality check on a constant
  // would pass against any windowing at all.
  const spread = new Set(run.trades.map(function (x) { return x.atrAtEntry.toFixed(7); })).size;
  return { pass: run.trades.length > 20 && bad.length === 0 && spread > 10,
    detail: run.trades.length + ' trades, ' + spread + ' distinct ATRs, all prefix-derived' };
});

t('CRT-13', 'entry is the NEXT bar open, never candle 3 close. Entering at the close of the bar '
  + 'that produced the signal is reading the decision bar to trade it', function () {
  let seed = 31337;
  const rnd = function () { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff; };
  const series = []; let px = 1.10000, tt = 1700000000000;
  for (let i = 0; i < 900; i++) {
    // The open GAPS from the previous close. Without a gap every next-bar open equals the
    // previous close by construction, and the assertion below passes vacuously against a
    // walker that entered on the signal bar close instead.
    const o = px + (rnd() - 0.5) * 0.0004, c2 = o + (rnd() - 0.5) * 0.0020;
    series.push({ t: new Date(tt), o: o, h: Math.max(o, c2) + rnd() * 0.0008,
      l: Math.min(o, c2) - rnd() * 0.0008, c: c2 });
    px = c2; tt += 4 * 3600000;
  }
  const r = P.crtReplayTrades(series, SWEPT, { pair: 'EUR_USD', timeframe: 'H4' });
  const bad = r.trades.filter(function (x) {
    return x.entryBarIndex !== x.signalBarIndex + 1 || x.entry !== series[x.entryBarIndex].o;
  });
  const differs = r.trades.filter(function (x) { return x.entry !== series[x.signalBarIndex].c; });
  return { pass: r.trades.length > 10 && bad.length === 0 && differs.length > 0,
    detail: r.trades.length + ' trades, all entered at the next bar open; ' + differs.length
      + ' where that differs from the signal bar close', };
});

t('CRT-14', 'the walker holds ONE position at a time and always advances, so a pathological series '
  + 'cannot spin or double-count a bar', function () {
  const r = P.crtReplayTrades(flat(400, 1.10000), SWEPT, { pair: 'EUR_USD', timeframe: 'H4' });
  const src = codeOf(fn('crtReplayTrades'));
  return { pass: /guard>candles\.length\+2/.test(src) && /Math\.max\(w\.exitBarIndex,i\+1\)/.test(src)
      && r.barsScanned <= 400,
    detail: 'guard present, index advances monotonically, ' + r.barsScanned + ' bars scanned' };
});

// ══ WHAT THE OUTPUT IS ALLOWED TO CLAIM ═══════════════════════════════════════════════════════

t('CRT-15', 'the comparison returns NO verdict -- two records and the differences between them. '
  + 'Whether a difference is believable depends on the sample size, which this does not judge',
  function () {
  const cmp = P.crtCompareArms({
    swept: { trades: [{ resultR: 2, plannedRR: 2 }], skipped: [], barsScanned: 5 },
    control: { trades: [{ resultR: -1, plannedRR: 2 }], skipped: [], barsScanned: 5 }
  });
  const keys = Object.keys(cmp).concat(Object.keys(cmp.swept));
  const verdicty = keys.filter(function (k) { return /verdict|conclusion|significant|edge|works|proven|recommend/i.test(k); });
  const src = codeOf(fn('crtCompareArms'));
  return { pass: verdicty.length === 0 && !/significant|p-?value/i.test(src),
    detail: verdicty.length ? 'VERDICT FIELD: ' + verdicty.join(',') : 'differences only, no judgement' };
});

t('CRT-16', 'an arm with no closed trades reports winRate null, not 0%. A null is "nothing '
  + 'decisive closed"; a zero is "it lost every time", and they are different facts', function () {
  const cmp = P.crtCompareArms({
    swept: { trades: [{ stillOpen: true, resultR: null }], skipped: [], barsScanned: 5 },
    control: { trades: [{ resultR: -1, plannedRR: 2 }], skipped: [], barsScanned: 5 }
  });
  return { pass: cmp.swept.winRate === null && cmp.swept.n === 0 && cmp.swept.netR === null
      && cmp.comparable === false && cmp.perTradeDifference === null,
    detail: 'winRate ' + cmp.swept.winRate + ', comparable ' + cmp.comparable };
});

t('CRT-17', 'a still-open trade is NOT exported as an outcome, and the count of excluded ones is '
  + 'written into the package. A null realizedR in a file invites a reader to treat it as zero',
  function () {
  const pkg = P.crtBuildReplayPackage([{ pair: 'EUR_USD',
    swept: { trades: [
      { stillOpen: true, pair: 'EUR_USD', arm: 'SWEPT', resultR: null },
      { stillOpen: false, pair: 'EUR_USD', arm: 'SWEPT', result: 'Win', resultR: 1.4, plannedRR: 1.4,
        entry: 1.101, stop: 1.103, target: 1.098, direction: 'sell', timeframe: 'H4' }] },
    control: { trades: [] } }], CFG, { stamp: 1 });
  return { pass: pkg.objectCounts.outcomes === 1 && pkg.objectCounts.positions === 1
      && pkg.replayDisclosures.stillOpenExcluded === 1,
    detail: pkg.objectCounts.outcomes + ' outcome(s), ' + pkg.replayDisclosures.stillOpenExcluded + ' excluded' };
});

t('CRT-18', 'both arms export into ONE package, each trade carrying its own arm, so the swept and '
  + 'control results cannot drift into separate files compared across different runs', function () {
  const mk = function (arm) { return { stillOpen: false, pair: 'EUR_USD', arm: arm, result: 'Win',
    resultR: 1.4, plannedRR: 1.4, entry: 1.101, stop: 1.103, target: 1.098, direction: 'sell', timeframe: 'H4' }; };
  const pkg = P.crtBuildReplayPackage([{ pair: 'EUR_USD',
    swept: { trades: [mk('SWEPT')] }, control: { trades: [mk('UNSWEPT_CONTROL')] } }], CFG, { stamp: 1 });
  const types = pkg.objects.qualifiedSetups.map(function (s) { return s.setupType; }).sort();
  return { pass: pkg.objectCounts.outcomes === 2 && types.join(',') === 'crt_swept,crt_unswept_control'
      && pkg.objects.qualifiedSetups.every(function (s) { return s.structureRefs.arm; }),
    detail: 'one package, setup types: ' + types.join(' + ') };
});

t('CRT-19', 'the package declares REPLAY_RUN and its OWN version. A replay figure read as forward '
  + 'performance has already cost this project a published conclusion once', function () {
  const pkg = P.crtBuildReplayPackage([], CFG, { stamp: 1 });
  const V = vm.runInContext('CRT_VERSION', ctx);
  return { pass: pkg.captureBasis === 'REPLAY_RUN' && pkg.identity.mode === 'REPLAY'
      && pkg.identity.strategyVersion === V && pkg.identity.strategyId === 'crt_v1',
    detail: 'captureBasis ' + pkg.captureBasis + ', mode ' + pkg.identity.mode
      + ', version ' + pkg.identity.strategyVersion };
});

t('CRT-20', 'THE HONEST LIMIT, IN THE FILE: reference-candle selection is NOT implemented, and the '
  + 'package says so. Every source qualifies candle 1 as sitting at a liquidity zone and none '
  + 'defines that mechanically, so a null result here does not falsify CRT as practised', function () {
  const d = P.crtBuildReplayPackage([], CFG, { stamp: 1 }).replayDisclosures;
  const r = d.referenceCandleSelection || '';
  return { pass: /NOT IMPLEMENTED/.test(r) && /every 3-bar window|EVERY 3-bar window/i.test(r)
      && /weaker test/i.test(r) && d.paperTradingAuthorized === false,
    detail: r ? 'disclosed, ' + r.length + ' chars' : 'MISSING' };
});

t('CRT-21', 'spread is left ABSENT, not written as zero. A recorded zero spread and an unmodelled '
  + 'spread are different facts and the analyser treats them differently', function () {
  const pkg = P.crtBuildReplayPackage([{ pair: 'EUR_USD', swept: { trades: [
    { stillOpen: false, pair: 'EUR_USD', arm: 'SWEPT', result: 'Win', resultR: 1.4, plannedRR: 1.4,
      entry: 1.101, stop: 1.103, target: 1.098, direction: 'sell', timeframe: 'H4' }] },
    control: { trades: [] } }], CFG, { stamp: 1 });
  const p = pkg.objects.positions[0];
  return { pass: p.entrySpreadPips === undefined && pkg.replayDisclosures.frictionModelled === false
      && pkg.objects.outcomes[0].pnl === undefined,
    detail: 'spread absent, pnl absent, frictionModelled false' };
});

t('CRT-22', 'the entry deviation is disclosed. CRT traders enter DURING candle 3; this replay has '
  + 'no intrabar data and enters at candle 4 open, which is conservative but not the same thing',
  function () {
  const d = P.crtBuildReplayPackage([], CFG, { stamp: 1 }).replayDisclosures;
  return { pass: d.entryBasis === 'NEXT_BAR_OPEN' && /intrabar/i.test(d.entryNote || '')
      && /conservative/i.test(d.entryNote || ''),
    detail: d.entryBasis + ' — ' + (d.entryNote ? 'deviation disclosed' : 'NOT DISCLOSED') };
});

// ══ GOVERNANCE ════════════════════════════════════════════════════════════════════════════════

t('CRT-23', 'the manifest forbids paper trading, automation and scanning. Discovery is not '
  + 'authorisation, and this arm has produced no result yet at all', function () {
  const b = constBlock('const CRT_MANIFEST=');
  const c = {}; vm.createContext(c);
  vm.runInContext("const CRT_STRATEGY_ID='crt_v1';const CRT_VERSION='crt_v1';" + b, c);
  const m = vm.runInContext('CRT_MANIFEST', c);
  const cap = m.capabilities;
  return { pass: cap.paperTrading === false && cap.automation === false && cap.scanning === false
      && cap.alerts === false && cap.replay === true && m.trustLevel === 'unverified'
      && /[Nn]ot authorized to paper trade/.test(m.currentPhase),
    detail: 'replay only; ' + m.currentPhase };
});

t('CRT-24', 'the arm is registered so it is reachable and auditable, rather than living as dead '
  + 'code nobody can run', function () {
  const reg = SRC.slice(SRC.indexOf('const STRATEGY_REGISTRY='));
  return { pass: /\{manifest:CRT_MANIFEST,services:CRT_SERVICES\}/.test(reg.slice(0, 800))
      && SRC.indexOf('id="panel-crt"') !== -1,
    detail: 'registered in STRATEGY_REGISTRY with a panel' };
});

t('CRT-25', 'CRT touches no protected function and adds no trading path. It reuses the PROTECTED '
  + 'exit engine unmodified, which is why the arms can differ only at entry', function () {
  const reg = JSON.parse(fs.readFileSync(path.join(ROOT, 'regression-baseline.json'), 'utf8'));
  const names = Object.keys(reg.protectedFunctions || {});
  const body = fn('crtReplayTrades') + fn('crtSignal') + fn('crtGeometry');
  return { pass: names.indexOf('alexGWalkOutcome') !== -1 && /alexGWalkOutcome\(/.test(body)
      && !/openPaperPosition|checkAutoTrades|placeOrder/.test(body),
    detail: 'uses protected alexGWalkOutcome; opens no position' };
});

t('CRT-26', 'REGRESSION, fixed here: the round-level package was stamping the BASELINE arm version '
  + 'as its own identity. Two arms reporting one version is how replay evidence gets attributed to '
  + 'the wrong strategy', function () {
  const b = constBlock('function psychLevelBuildReplayPackage');
  const src = codeOf(fn('psychLevelBuildReplayPackage'));
  return { pass: /strategyVersion:PSYCH_LEVEL_VERSION/.test(src)
      && !/strategyVersion:BASELINE_TREND_VERSION/.test(src) && b.length > 0,
    detail: 'psych package now stamps PSYCH_LEVEL_VERSION' };
});

// ══ GUARDS ════════════════════════════════════════════════════════════════════════════════════

t('GUARD-1', 'the whole page script parses', function () {
  const m = SRC.match(/<script>([\s\S]*?)<\/script>/g) || [];
  let total = 0;
  m.forEach(function (b) {
    const js = b.replace(/^<script>/, '').replace(/<\/script>$/, '');
    if (!js.trim()) return; total += js.length; new Function(js);
  });
  return { pass: total > 100000, detail: 'parsed ' + total.toLocaleString() + ' chars' };
});

t('GUARD-2', 'no protected function or constant drifted', function () {
  const reg = JSON.parse(fs.readFileSync(path.join(ROOT, 'regression-baseline.json'), 'utf8'));
  const f = Object.keys(reg.protectedFunctions || {}).length;
  const c = Object.keys(reg.protectedConstants || {}).length;
  return { pass: f === 64 && c === 4, detail: f + ' functions, ' + c + ' constants in the baseline' };
});

let pass = 0;
results.forEach(function (r) {
  if (r.pass) pass++;
  console.log((r.pass ? '  PASS  ' : '  FAIL  ') + r.name + '  ' + r.desc);
  if (r.detail) console.log('          ' + r.detail);
});
console.log('\n  ' + pass + ' / ' + results.length + ' passed');
process.exit(pass === results.length ? 0 : 1);

#!/usr/bin/env node
'use strict';
// ══════════════════════════════════════════════════════════════════════════════════════════════
// v12.54.0 — ROUND-NUMBER LEVELS, AND THE CONTROL THAT MAKES THEM TESTABLE
// ══════════════════════════════════════════════════════════════════════════════════════════════
//
// Osler (NY Fed SR125) found, in 9,667 real orders, that take-profits cluster AT round numbers and
// stop-losses just beyond. This arm trades that claim directly: reach a round level, fail to close
// through it, fade the approach.
//
// A profitable result would prove nothing on its own, because a mean-reversion rule can profit on
// ANY evenly-spaced grid. So the identical rule also runs on a grid shifted half an interval --
// levels as regular and as arbitrary as the round ones. PSY-C1..C6 are that control, and PSY-C3 is
// the fixture that matters most: the two arms must be capable of producing DIFFERENT results on
// the same bars, or the comparison is theatre.
//
// PSY-L1..L4 pin the look-ahead property by truncation: a decision taken on a longer series must
// be identical when the series is cut off at the decision bar. If it is not, the signal is reading
// its own future and every figure the arm produces is worthless.
//
// Run:  node tests/run_v154_psych_level_tests.js

const fs = require('fs');
const path = require('path');
const vm = require('vm');
const SRC = fs.readFileSync(path.resolve(__dirname, '..', 'index.html'), 'utf8');

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

const ctx = { console: console, Math: Math, JSON: JSON, isFinite: isFinite, Array: Array,
  Number: Number, Object: Object, String: String, Date: Date, isNaN: isNaN };
vm.createContext(ctx);
vm.runInContext("const PSYCH_LEVEL_STRATEGY_ID='psych_level_v1';", ctx);
vm.runInContext(constBlock('const RULES_PSYCH_LEVEL='), ctx);
['pipSize', 'calcATR', 'getNYOffsetMinutes', 'nyAlignedClose', 'getCandleCloseTime',
  'alexGWalkOutcome', 'alexGComputeMAEMFE',
  'psychLevelControlOffsetPips', 'psychLevelNearest', 'psychLevelsTouched', 'psychLevelSignal',
  'psychLevelGeometry', 'psychLevelReplayTrades', 'psychLevelRunBothArms', 'psychLevelCompareArms']
  .forEach(function (n) { vm.runInContext(fn(n), ctx); });
const P = ctx;
const CFG = vm.runInContext('RULES_PSYCH_LEVEL.config', ctx);
const PIP = 0.0001;

// ── candle helpers ───────────────────────────────────────────────────────────────────────────
let T = 1700000000000;
// `t` is a Date, not a number. getCandleCloseTime calls start.getTime() on the LAST candle, so a
// numeric timestamp throws there and only there -- a series that never reaches its own end would
// have hidden it. Matching the real shape rather than the shape that happens to pass.
function bar(o, h, l, c) { const b = { t: new Date(T), o: o, h: h, l: l, c: c }; T += 4 * 3600000; return b; }
// A flat run that gives calcATR something to chew on without creating signals of its own.
function flat(n, base) {
  const out = [];
  for (let i = 0; i < n; i++) {
    const p = base + (i % 2 ? 0.00020 : -0.00020);
    out.push(bar(p, p + 0.00060, p - 0.00060, p));
  }
  return out;
}

const results = [];
function t(name, desc, f) {
  let pass = false, detail = '';
  try { const r = f(); pass = !!(r && r.pass); detail = (r && r.detail) || ''; }
  catch (e) { pass = false; detail = 'threw: ' + (e && e.message ? e.message : String(e)); }
  results.push({ name, desc, pass, detail });
}
const near = function (a, b, e) { return a != null && b != null && Math.abs(a - b) < (e || 1e-9); };

// ══ THE GRID ═════════════════════════════════════════════════════════════════════════════════

t('PSY-G1', 'the round grid lands on actual round numbers, and the control grid deliberately does '
  + 'not -- the control must be arbitrary, not merely different', function () {
  const round = { levelIntervalPips: 100, levelOffsetPips: 0 };
  const ctrl = { levelIntervalPips: 100, levelOffsetPips: 50 };
  const a = P.psychLevelNearest(1.10430, round, PIP);
  const b = P.psychLevelNearest(1.10430, ctrl, PIP);
  return { pass: near(a, 1.1000, 1e-9) && near(b, 1.1050, 1e-9),
    detail: 'round -> ' + a.toFixed(5) + ', control -> ' + b.toFixed(5) };
});

t('PSY-G2', 'the control offset is exactly half an interval, so the two grids have IDENTICAL '
  + 'spacing and differ only in where they sit', function () {
  const off = P.psychLevelControlOffsetPips(CFG);
  return { pass: off === CFG.levelIntervalPips / 2,
    detail: 'interval ' + CFG.levelIntervalPips + ' pips, control offset ' + off };
});

t('PSY-G3', 'levels touched by a bar are enumerated, in order, and a degenerate interval cannot '
  + 'spin the loop', function () {
  const c = { levelIntervalPips: 100, levelOffsetPips: 0 };
  const many = P.psychLevelsTouched(1.0990, 1.1210, c, PIP);
  const none = P.psychLevelsTouched(1.1010, 1.1040, c, PIP);
  const bad = P.psychLevelsTouched(1.10, 1.11, { levelIntervalPips: 0, levelOffsetPips: 0 }, PIP);
  const inverted = P.psychLevelsTouched(1.11, 1.10, c, PIP);
  return { pass: many.length === 3 && near(many[0], 1.10) && near(many[2], 1.12)
      && none.length === 0 && bad.length === 0 && inverted.length === 0,
    detail: 'span -> ' + many.length + ' levels; narrow -> 0; zero-interval -> 0; inverted -> 0' };
});

t('PSY-G4', 'JPY pairs use their own pip size, or every level would be off by a factor of a '
  + 'hundred on half the instruments', function () {
  const c = { levelIntervalPips: 100, levelOffsetPips: 0 };
  const jpyPip = P.pipSize('USD_JPY');
  const lvl = P.psychLevelNearest(157.43, c, jpyPip);
  return { pass: jpyPip === 0.01 && near(lvl, 157.00, 1e-9),
    detail: 'USD_JPY pip=' + jpyPip + ', nearest level ' + lvl.toFixed(2) };
});

// ══ THE SIGNAL ═══════════════════════════════════════════════════════════════════════════════

// Approaches 1.1000 from below and closes back under it.
function rejectionFromBelow() {
  const s = flat(20, 1.09500);
  s.push(bar(1.09600, 1.10040, 1.09580, 1.09930));
  return s;
}

t('PSY-S1', 'a bar that reaches the level from below and closes back beneath it produces a SELL -- '
  + 'the rule fades the approach, which is the mechanism being tested', function () {
  const sig = P.psychLevelSignal(rejectionFromBelow(), CFG, PIP);
  return { pass: !!sig && sig.direction === 'sell' && near(sig.level, 1.10, 1e-9)
      && sig.approachFromBelow === true,
    detail: sig ? sig.direction + ' at ' + sig.level.toFixed(4) : 'no signal' };
});

t('PSY-S2', 'a bar that closes THROUGH the level produces nothing. That is a break, and this arm '
  + 'does not trade breaks -- trading both directions on the same event would guarantee a signal '
  + 'either way and measure nothing', function () {
  const s = flat(20, 1.09500);
  s.push(bar(1.09600, 1.10120, 1.09580, 1.10080));   // closed above 1.1000
  return { pass: P.psychLevelSignal(s, CFG, PIP) === null, detail: 'close through the level -> no signal' };
});

t('PSY-S3', 'a bar spanning MORE than one level produces nothing -- price ran through, which is the '
  + 'opposite of stalling at a level', function () {
  const s = flat(20, 1.09500);
  s.push(bar(1.09600, 1.11050, 1.09580, 1.09900));   // spans 1.1000 and 1.1100
  return { pass: P.psychLevelSignal(s, CFG, PIP) === null, detail: 'two levels in range -> no signal' };
});

t('PSY-S4', 'a close far from the level produces nothing. A spike that collapses is a different '
  + 'event from a rejection, and the distance gate is measured in the bar\'s own ATR', function () {
  const s = flat(20, 1.09500);
  // Reaches 1.1000 but closes ~90 pips lower -- far more than maxCloseDistanceATR * ATR here.
  s.push(bar(1.09600, 1.10030, 1.09000, 1.09100));
  return { pass: P.psychLevelSignal(s, CFG, PIP) === null, detail: 'distant close -> no signal' };
});

t('PSY-S5', 'the approach side comes from the PREVIOUS close, so the signal bar cannot define the '
  + 'direction it is then traded against', function () {
  const body = fn('psychLevelSignal');
  return { pass: /const approachFromBelow=prev\.c<level;/.test(body)
      && /if\(prev\.c===level\) return null;/.test(body),
    detail: 'direction set by prev.c; an exact-touch previous close is refused' };
});

t('PSY-S6', 'a signal is impossible without a usable ATR, so geometry can never rest on a '
  + 'fabricated volatility figure', function () {
  const s = [bar(1.10, 1.1004, 1.0996, 1.0999), bar(1.0996, 1.10040, 1.09950, 1.09930)];
  return { pass: P.psychLevelSignal(s, CFG, PIP) === null, detail: 'too few bars for ATR -> no signal' };
});

// ══ NO LOOK-AHEAD, PROVED BY TRUNCATION ══════════════════════════════════════════════════════

t('PSY-L1', 'the decision on a bar is IDENTICAL whether or not later bars exist. If truncation '
  + 'changed the answer, the signal would be reading its own future', function () {
  const full = rejectionFromBelow();
  for (let k = 0; k < 25; k++) full.push(bar(1.098, 1.099, 1.097, 1.0985));
  const prefix = full.slice(0, 21);
  const a = P.psychLevelSignal(prefix, CFG, PIP);
  const b = P.psychLevelSignal(full.slice(0, 21), CFG, PIP);
  const onFull = P.psychLevelSignal(full, CFG, PIP);
  return { pass: !!a && JSON.stringify(a) === JSON.stringify(b) && (onFull === null || onFull.level !== a.level),
    detail: 'prefix decision stable; the full series decides its own last bar separately' };
});

t('PSY-L2', 'the walker hands the signal a PREFIX, never the whole series', function () {
  const body = fn('psychLevelReplayTrades');
  return { pass: /const window=candles\.slice\(0,i\+1\);/.test(body)
      && /psychLevelSignal\(window,c,pip\)/.test(body)
      && !/psychLevelSignal\(candles/.test(body),
    detail: 'signal sees candles[0..i] only' };
});

t('PSY-L3', 'entry is the NEXT bar\'s open -- a price that exists after the decision, never the '
  + 'close of the bar that made it', function () {
  const body = fn('psychLevelReplayTrades');
  return { pass: /const entryBarIndex=i\+1;/.test(body)
      && /const entry=\(entryBar&&typeof entryBar\.o==='number'\)\?entryBar\.o:null;/.test(body),
    detail: 'entry = open of bar i+1' };
});

t('PSY-L4', 'the loop always advances, so a degenerate series cannot hang the browser', function () {
  const body = fn('psychLevelReplayTrades');
  return { pass: /if\(\+\+guard>candles\.length\+2\) break;/.test(body)
      && /Math\.max\(w\.exitBarIndex,i\+1\)/.test(body),
    detail: 'guard plus a monotonic cursor' };
});

// ══ GEOMETRY ═════════════════════════════════════════════════════════════════════════════════

t('PSY-M1', 'the stop sits BEYOND the level, where the order study puts the stop cluster, and the '
  + 'target is the same 2R every other arm books at so the numbers compare', function () {
  const g = P.psychLevelGeometry('sell', 1.09930, 1.10, 0.00100, CFG);
  const expectedStop = 1.10 + CFG.stopATRMultiple * 0.00100;
  const risk = expectedStop - 1.09930;
  return { pass: !!g && near(g.stop, expectedStop, 1e-9)
      && near(g.target, 1.09930 - CFG.targetRR * risk, 1e-9) && g.plannedRR === CFG.targetRR,
    detail: 'stop ' + g.stop.toFixed(5) + ' beyond level, target ' + g.target.toFixed(5) };
});

t('PSY-M2', 'geometry FAILS CLOSED on every degenerate input rather than returning a trade with a '
  + 'nonsensical risk', function () {
  const bad = [
    P.psychLevelGeometry('sell', 1.10200, 1.10, 0.00100, CFG),   // entry already beyond its stop
    P.psychLevelGeometry('buy', 1.09, 1.10, 0.00100, CFG),       // ditto, other side
    P.psychLevelGeometry('sell', 1.0993, 1.10, 0, CFG),          // no ATR
    P.psychLevelGeometry('sell', 1.0993, 1.10, NaN, CFG),
    P.psychLevelGeometry(null, 1.0993, 1.10, 0.001, CFG),
    P.psychLevelGeometry('sell', NaN, 1.10, 0.001, CFG)
  ];
  return { pass: bad.every(function (g) { return g === null; }), detail: 'six degenerate inputs, six nulls' };
});

// ══ THE CONTROL — the reason this arm is worth running at all ════════════════════════════════

t('PSY-C1', 'both arms run over the SAME candles in one pass. A control compared against a '
  + 'different dataset is not a control', function () {
  const body = fn('psychLevelRunBothArms');
  return { pass: /psychLevelReplayTrades\(candles,round,opts\)/.test(body)
      && /psychLevelReplayTrades\(candles,control,opts\)/.test(body)
      && /sameCandles:true/.test(body),
    detail: 'one candle series, two grids' };
});

t('PSY-C2', 'the two arms differ ONLY in the grid offset. Any other difference would make the '
  + 'comparison meaningless', function () {
  const body = fn('psychLevelRunBothArms');
  const round = /Object\.assign\(\{\},base,\{levelOffsetPips:0\}\)/.test(body);
  const ctrl = /Object\.assign\(\{\},base,\{levelOffsetPips:psychLevelControlOffsetPips\(base\)\}\)/.test(body);
  return { pass: round && ctrl, detail: 'both configs cloned from the same base, offset alone changed' };
});

t('PSY-C3', 'THE FIXTURE THAT MATTERS: the two arms can produce DIFFERENT results on the same '
  + 'bars. If a rejection at 1.1000 and one at 1.1050 were indistinguishable, the experiment would '
  + 'be theatre and would always report "no effect"', function () {
  // A rejection at 1.1000 -- on the round grid, but nowhere near a level on the offset grid.
  const s = flat(20, 1.09500);
  s.push(bar(1.09600, 1.10040, 1.09580, 1.09930));
  for (let k = 0; k < 12; k++) s.push(bar(1.0985, 1.0990, 1.0975, 1.0980));
  const both = P.psychLevelRunBothArms(s, CFG, { pair: 'EUR_USD', timeframe: 'H4' });
  return { pass: both.round.trades.length > 0 && both.round.trades.length !== both.control.trades.length,
    detail: 'round arm ' + both.round.trades.length + ' trade(s), control arm ' + both.control.trades.length };
});

t('PSY-C4', 'each arm labels itself, so a trade can never be read against the wrong grid', function () {
  const s = flat(20, 1.09500);
  s.push(bar(1.09600, 1.10040, 1.09580, 1.09930));
  for (let k = 0; k < 12; k++) s.push(bar(1.0985, 1.0990, 1.0975, 1.0980));
  const both = P.psychLevelRunBothArms(s, CFG, { pair: 'EUR_USD', timeframe: 'H4' });
  return { pass: both.round.arm === 'ROUND' && both.control.arm === 'OFFSET_CONTROL'
      && both.round.trades.every(function (t2) { return t2.arm === 'ROUND'; }),
    detail: both.round.arm + ' vs ' + both.control.arm + ', and every trade carries its arm' };
});

t('PSY-C5', 'the comparison reports the DIFFERENCE between the arms, which is the experiment. Two '
  + 'separate results the reader has to hold in their head is not a comparison', function () {
  const cmp = P.psychLevelCompareArms({
    round: { trades: [{ resultR: 2 }, { resultR: -1 }, { resultR: 2 }], skipped: [], barsScanned: 10 },
    control: { trades: [{ resultR: -1 }, { resultR: -1 }], skipped: [], barsScanned: 10 }
  });
  return { pass: cmp.round.n === 3 && cmp.control.n === 2
      && near(cmp.round.perTrade, 1) && near(cmp.control.perTrade, -1)
      && near(cmp.perTradeDifference, 2) && cmp.comparable === true,
    detail: 'round ' + cmp.round.perTrade + 'R vs control ' + cmp.control.perTrade + 'R, difference '
      + cmp.perTradeDifference + 'R' };
});

t('PSY-C6', 'the comparison returns NO verdict. It reports two records and the gap between them; '
  + 'whether that gap means anything is a judgement about sample size, not arithmetic', function () {
  const cmp = P.psychLevelCompareArms({
    round: { trades: [{ resultR: 2 }], skipped: [], barsScanned: 5 },
    control: { trades: [{ resultR: -1 }], skipped: [], barsScanned: 5 }
  });
  const keys = Object.keys(cmp);
  const forbidden = keys.filter(function (k) { return /verdict|significant|works|proven|conclusion/i.test(k); });
  const body = fn('psychLevelCompareArms');
  return { pass: forbidden.length === 0 && !/significant|proven/i.test(body),
    detail: 'keys: ' + keys.join(', ') };
});

t('PSY-C7', 'an empty or one-sided run reports incomparable rather than a difference computed '
  + 'against nothing', function () {
  const none = P.psychLevelCompareArms({ round: { trades: [], skipped: [], barsScanned: 0 },
    control: { trades: [], skipped: [], barsScanned: 0 } });
  return { pass: none.comparable === false && none.perTradeDifference === null
      && P.psychLevelCompareArms(null) === null,
    detail: 'empty -> comparable=false, difference=null' };
});

// ══ IT CANNOT TRADE ══════════════════════════════════════════════════════════════════════════

t('PSY-X1', 'no live entry point references this arm. It is replay evidence, not a strategy that '
  + 'can open a position', function () {
  const live = ['alexGLivePollTick', 'alexGCheckLivePositions', 'alexGAttemptOpenLivePosition',
    'alexGEvaluatePairForLiveSetups', 'alexGConstructLivePosition', 'checkAutoTrades', 'scanAll'];
  const bad = live.filter(function (n) { return /psychLevel|PSYCH_LEVEL/.test(fn(n)); });
  return { pass: bad.length === 0,
    detail: bad.length ? 'referenced by: ' + bad.join(',') : live.length + ' live entry points are clean' };
});

t('PSY-X2', 'its results are labelled REPLAY_RUN at the source, so they can never be counted as '
  + 'forward performance', function () {
  const body = fn('runPsychLevelReplay');
  return { pass: /captureBasis:'REPLAY_RUN'/.test(body) && /population:'REPLAY'/.test(body),
    detail: 'labelled at the point of production' };
});

t('PSY-X3', 'the run states that no friction is modelled, matching every other replay arm, so its '
  + 'numbers are read as the frictionless upper bound they are', function () {
  const body = fn('psychLevelReplayTrades');
  return { pass: /frictionModelled:false/.test(body) && /entryBasis:'NEXT_BAR_OPEN'/.test(body),
    detail: 'friction and entry basis both declared on the result' };
});

t('PSY-X4', 'exits are resolved by the SAME protected walker ALEX uses, so the arms differ at '
  + 'entry and nowhere else', function () {
  const body = fn('psychLevelReplayTrades');
  const baseline = fn('baselineTrendReplayTrades');
  return { pass: /alexGWalkOutcome\(candles,entryBarIndex,g\.direction,g\.stop,g\.target,'conservative',timeframe\)/.test(body)
      && /alexGWalkOutcome\(candles,entryBarIndex,g\.direction,g\.stop,g\.target,'conservative',timeframe\)/.test(baseline),
    detail: 'identical exit call to the trend baseline' };
});

t('PSY-X5', 'skipped bars are recorded rather than silently dropped -- a skipped bar is a fact '
  + 'about coverage', function () {
  const body = fn('psychLevelReplayTrades');
  return { pass: /out\.skipped\.push\(\{barIndex:i,reason:/.test(body) && /skipped:\[\]/.test(body),
    detail: 'skips carry a bar index and a reason' };
});

// ══ THE CHECK THAT WOULD HAVE CAUGHT WHAT UNIT TESTS COULD NOT ══════════════════════════════

t('PSY-P1', 'the WHOLE page script parses. Every fixture above extracts one function into a fresh '
  + 'realm, so all 28 passed while the deployed page was dead on load with a duplicate top-level '
  + 'declaration. A per-function test cannot see a collision between functions', function () {
  const start = SRC.lastIndexOf('<script>');
  const end = SRC.lastIndexOf('</script>');
  const js = SRC.slice(start + 8, end);
  let err = null;
  try { new Function(js); } catch (e) { err = e.message; }
  return { pass: err === null && js.length > 100000,
    detail: err ? 'SYNTAX ERROR: ' + err : js.split('\n').length + ' lines parse cleanly' };
});

t('PSY-P2', 'no identifier this arm introduces collides with an existing top-level declaration', function () {
  const mine = ['PSYCH_LEVEL_STRATEGY_ID', 'PSYCH_LEVEL_VERSION', 'RULES_PSYCH_LEVEL',
    'PSYCH_LEVEL_MANIFEST', 'PSYCH_LEVEL_SERVICES', 'psychLevelLastRuns', 'psychLevelRunning'];
  const dupes = mine.filter(function (n) {
    const m = SRC.match(new RegExp('^(?:const|let|var)\\s+' + n + '\\b', 'gm'));
    return m && m.length > 1;
  });
  // ...and the arm it was cloned from must still be declared exactly once.
  const cloned = ['baselineTrendLastRuns', 'baselineTrendRunning'].filter(function (n) {
    const m = SRC.match(new RegExp('^let\\s+' + n + '\\b', 'gm'));
    return !m || m.length !== 1;
  });
  return { pass: dupes.length === 0 && cloned.length === 0,
    detail: (dupes.length ? 'duplicated: ' + dupes.join(',') : 'no duplicates')
      + (cloned.length ? ' | clone source damaged: ' + cloned.join(',') : '') };
});

t('PSY-P3', 'the arm is registered and reachable: registry entry, panel markup, and a workspace '
  + 'that opens it', function () {
  return { pass: /\{manifest:PSYCH_LEVEL_MANIFEST,services:PSYCH_LEVEL_SERVICES\}/.test(SRC)
      && SRC.indexOf('id="panel-psychlevel"') >= 0
      && /panelId:'psychlevel'/.test(SRC)
      && /onOpen:\(\)=>\{ try\{ initPsychLevelWorkspace\(\); \}catch\(e\)\{\} \}/.test(SRC),
    detail: 'registry, panel and onOpen all present' };
});

t('PSY-P4', 'the manifest refuses paper trading, and says so in the phase line rather than only in '
  + 'a capability flag a reader might not check', function () {
  const m = /const PSYCH_LEVEL_MANIFEST=\{[\s\S]*?\n\};/.exec(SRC)[0];
  return { pass: /paperTrading:false/.test(m) && /automation:false/.test(m)
      && /Not authorized to paper trade/.test(m) && /replay:true/.test(m),
    detail: 'replay only, stated twice' };
});

// ══ IS IT WORTH RUNNING AT ALL ═══════════════════════════════════════════════════════════════

t('PSY-V1', 'on a realistic random walk the arm produces a WORKABLE number of trades in both arms. '
  + 'A rule that fires three times in two years cannot answer anything, and a fixture suite full of '
  + 'hand-built single signals would never reveal that', function () {
  // Deterministic pseudo-random walk, so the fixture cannot pass or fail by luck of the draw.
  let seed = 12345;
  const rnd = function () { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff; };
  const series = [];
  let px = 1.10000, tt = 1700000000000;
  for (let i = 0; i < 3000; i++) {
    const drift = (rnd() - 0.5) * 0.0020;
    const o = px, c = px + drift;
    const h = Math.max(o, c) + rnd() * 0.0008, l = Math.min(o, c) - rnd() * 0.0008;
    series.push({ t: new Date(tt), o: o, h: h, l: l, c: c });
    px = c; tt += 4 * 3600000;
  }
  const both = P.psychLevelRunBothArms(series, CFG, { pair: 'EUR_USD', timeframe: 'H4' });
  const r = both.round.trades.length, c = both.control.trades.length;
  return { pass: r >= 10 && c >= 10,
    detail: '3000 bars -> round ' + r + ' trades, control ' + c + ' trades' };
});

t('PSY-V2', 'and neither arm is starved relative to the other. If the round grid fired ten times as '
  + 'often as its control, the comparison would be between different sample sizes rather than '
  + 'between grids', function () {
  let seed = 999;
  const rnd = function () { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff; };
  const series = [];
  let px = 1.10000, tt = 1700000000000;
  for (let i = 0; i < 3000; i++) {
    const drift = (rnd() - 0.5) * 0.0020;
    const o = px, c2 = px + drift;
    series.push({ t: new Date(tt), o: o, h: Math.max(o, c2) + rnd() * 0.0008,
      l: Math.min(o, c2) - rnd() * 0.0008, c: c2 });
    px = c2; tt += 4 * 3600000;
  }
  const both = P.psychLevelRunBothArms(series, CFG, { pair: 'EUR_USD', timeframe: 'H4' });
  const r = both.round.trades.length, c = both.control.trades.length;
  const ratio = Math.max(r, c) / Math.max(1, Math.min(r, c));
  return { pass: ratio <= 2.5 && r > 0 && c > 0,
    detail: 'round ' + r + ' vs control ' + c + ' (ratio ' + ratio.toFixed(2) + ')' };
});

results.forEach(function (r) {
  console.log((r.pass ? 'PASS' : 'FAIL') + ' -- ' + r.name + ': ' + r.desc + (r.detail ? '  [' + r.detail + ']' : ''));
});
const fails = results.filter(function (r) { return !r.pass; }).length;
console.log('---');
console.log(results.length + ' fixtures, ' + (results.length - fails) + ' PASS, ' + fails + ' FAIL');
process.exitCode = fails ? 1 : 0;

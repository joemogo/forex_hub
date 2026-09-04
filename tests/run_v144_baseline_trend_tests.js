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
  Number: Number, Object: Object, String: String };
vm.createContext(ctx);
vm.runInContext(extractBlock('const RULES_BASELINE_TREND='), ctx);
vm.runInContext(extractFunction('baselineTrendSignal'), ctx);
vm.runInContext(extractFunction('baselineTrendGeometry'), ctx);
const signal = vm.runInContext('baselineTrendSignal', ctx);
const geom = vm.runInContext('baselineTrendGeometry', ctx);
const CFG = vm.runInContext('RULES_BASELINE_TREND.config', ctx);

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
  return closes.map(function (c, i) { return { t: 1000 + i * 86400000, o: c, h: c, l: c, c: c }; });
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

t('BT-14', 'NOTHING CALLS IT. Neither pure function is referenced anywhere outside its own '
  + 'definition and this suite -- there is no path from the poll tick to a baseline position', function () {
  const calls = [];
  ['baselineTrendSignal', 'baselineTrendGeometry'].forEach(function (fn) {
    // Every occurrence that is not the declaration itself.
    const all = SRC.split(fn).length - 1;
    const decl = new RegExp('function\\s+' + fn + '\\s*\\(').test(SRC) ? 1 : 0;
    if (all - decl > 0) calls.push(fn + ' referenced ' + (all - decl) + ' extra time(s)');
  });
  return { pass: calls.length === 0, detail: calls.length ? calls.join('; ') : 'no call sites' };
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

results.forEach(function (r) {
  console.log((r.pass ? 'PASS' : 'FAIL') + ' -- ' + r.name + ': ' + r.desc + (r.detail ? '  [' + r.detail + ']' : ''));
});
const fails = results.filter(function (r) { return !r.pass; }).length;
console.log('---');
console.log(results.length + ' fixtures, ' + (results.length - fails) + ' PASS, ' + fails + ' FAIL');
process.exitCode = fails ? 1 : 0;

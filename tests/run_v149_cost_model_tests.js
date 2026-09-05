#!/usr/bin/env node
'use strict';
// ══════════════════════════════════════════════════════════════════════════════════════════════
// v12.49.0 — THE COST MODEL THAT WAS RECORDED AND NEVER APPLIED
// ══════════════════════════════════════════════════════════════════════════════════════════════
//
// alexGConstructTrade accepts spreadMode, fixedSpreadPips and slippagePips, stamps all three onto
// every trade record, and applies none of them: entry is setup.qualificationClose untouched, and
// alexGWalkOutcome takes no cost parameter at all. A run with fixedSpreadPips:2 therefore returns
// results IDENTICAL to a zero-cost run while asserting on each record that it accounted for 2 pips.
//
// A record that misstates its own basis is worse than a missing feature. Both functions are
// PROTECTED, so the arithmetic cannot be repaired here -- COST-1..COST-3 prove the defect is real
// from the source rather than asserting it, and COST-4..COST-8 pin the fail-closed response.
//
// The stress estimator (STRESS-*) exists because a frictionless backtest still has to be read
// somehow. Its numbers come from the forward corpus, not from assumption, and STRESS-9/10 pin the
// two things it must never be allowed to become: a claim of precision it does not have, and a
// figure computed over a silently shrinking denominator.
//
// Run:  node tests/run_v149_cost_model_tests.js

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

const ctx = { console: console, Math: Math, JSON: JSON, isFinite: isFinite, Array: Array,
  Number: Number, Object: Object, String: String, Date: Date, isNaN: isNaN };
vm.createContext(ctx);
vm.runInContext(constBlock('const ALEXG_REPLAY_COST_PARAMS='), ctx);
vm.runInContext(constBlock("const OBS_COST_SOURCE_NOTE="), ctx);
vm.runInContext(fn('alexGReplayIgnoredCostParams'), ctx);
vm.runInContext(fn('obsCostStress'), ctx);
const O = ctx;
// `const` in a vm context is a lexical binding, not a property of the context object -- only
// `function` declarations land on ctx. Reading it back by evaluating its name; asserting against
// O.OBS_COST_SOURCE_NOTE would silently test the string "undefined".
const COST_SOURCE_NOTE = vm.runInContext('OBS_COST_SOURCE_NOTE', ctx);

const CONSTRUCT = fn('alexGConstructTrade');
const WALK = fn('alexGWalkOutcome');
const DRIVER = fn('runAlexGReplay');

const results = [];
function t(name, desc, f) {
  let pass = false, detail = '';
  try { const r = f(); pass = !!(r && r.pass); detail = (r && r.detail) || ''; }
  catch (e) { pass = false; detail = 'threw: ' + (e && e.message ? e.message : String(e)); }
  results.push({ name, desc, pass, detail });
}
const close = function (a, b, e) { return a != null && b != null && Math.abs(a - b) < (e || 1e-9); };

// ══ THE DEFECT IS REAL — proved from the source, not asserted ════════════════════════════════

t('COST-1', 'the trade constructor STAMPS the cost parameters onto every record it produces', function () {
  return { pass: /spreadMode:opts\.spreadMode/.test(CONSTRUCT) && /spreadPips:/.test(CONSTRUCT)
      && /slippagePips:opts\.slippagePips/.test(CONSTRUCT),
    detail: 'spreadMode, spreadPips and slippagePips all written to the record' };
});

t('COST-2', '...and applies NONE of them. Entry is the qualification close untouched, and no cost '
  + 'term appears anywhere in the stop, target or risk arithmetic', function () {
  const entryLine = /const entry=setup\.qualificationClose;/.test(CONSTRUCT);
  // Everything before the record literal is the arithmetic. A cost term there would be a use.
  const arithmetic = CONSTRUCT.slice(0, CONSTRUCT.indexOf('spreadMode:opts.spreadMode'));
  const uses = /opts\.spreadMode|opts\.fixedSpreadPips|opts\.slippagePips/.test(arithmetic);
  return { pass: entryLine && !uses,
    detail: 'entry = qualificationClose; cost parameters referenced in the arithmetic: ' + uses };
});

t('COST-3', '...and the outcome walker has no cost parameter at all, so the stop and target it '
  + 'tests against were never adjusted either', function () {
  const sig = /function alexGWalkOutcome\(([^)]*)\)/.exec(WALK)[1];
  return { pass: !/spread|slippage|cost/i.test(sig),
    detail: 'signature: (' + sig + ')' };
});

t('COST-4', 'both functions are PROTECTED, which is WHY the response is refusal rather than repair', function () {
  const pf = JSON.parse(fs.readFileSync(path.join(ROOT, 'regression-baseline.json'), 'utf8')).protectedFunctions;
  return { pass: !!pf.alexGConstructTrade && !!pf.alexGWalkOutcome,
    detail: 'alexGConstructTrade and alexGWalkOutcome are both protected' };
});

// ══ FAIL CLOSED ══════════════════════════════════════════════════════════════════════════════

t('COST-5', 'a non-zero spread or slippage is REFUSED, and the refusal names every parameter that '
  + 'would have been ignored', function () {
  const a = O.alexGReplayIgnoredCostParams({ alexGSpreadMode: 'fixed', alexGFixedSpreadPips: 2, alexGSlippagePips: 1 });
  return { pass: a.length === 3 && a.indexOf('alexGSpreadMode') >= 0
      && a.indexOf('alexGFixedSpreadPips') >= 0 && a.indexOf('alexGSlippagePips') >= 0,
    detail: a.join(', ') };
});

t('COST-6', 'the zero-cost run the UI actually performs is ALLOWED. Refusing it would break the '
  + 'existing workflow to prevent a problem it does not have', function () {
  const shipped = /const replayParams=\{ambiguousMode,([^}]*)\}/.exec(SRC);
  const asShipped = { ambiguousMode: 'conservative', alexGSpreadMode: 'none',
    alexGFixedSpreadPips: 0, alexGSlippagePips: 0, startBalance: 10000 };
  return { pass: O.alexGReplayIgnoredCostParams(asShipped).length === 0
      && O.alexGReplayIgnoredCostParams({}).length === 0
      && O.alexGReplayIgnoredCostParams(null).length === 0
      && !!shipped && /alexGSpreadMode:'none'/.test(shipped[1]),
    detail: 'shipped params pass the guard; UI still sends none/0/0' };
});

t('COST-7', 'the guard runs BEFORE any candle is fetched, so a refusal costs nothing and cannot '
  + 'half-run', function () {
  const iGuard = DRIVER.indexOf('alexGReplayIgnoredCostParams');
  const iFetch = DRIVER.indexOf('fetchAlexGReplayDatasets');
  const iReset = DRIVER.indexOf('delete alexGZoneState');
  return { pass: iGuard >= 0 && iGuard < iFetch && iGuard < iReset,
    detail: 'guard at ' + iGuard + ', state reset at ' + iReset + ', fetch at ' + iFetch };
});

t('COST-8', 'the refusal explains WHY, rather than reading as an unsupported-feature error -- the '
  + 'operator needs to know the result would have been mislabelled, not merely unavailable', function () {
  const i = DRIVER.indexOf('costParamsIgnored');
  const msg = DRIVER.slice(DRIVER.indexOf('not implemented'), i);
  return { pass: /silently ignored/.test(msg) && /SAME result/.test(msg)
      && /frictionless upper bound/.test(msg),
    detail: 'names the silent-ignore, the identical result, and how to read a zero-cost run' };
});

// ══ THE STRESS ESTIMATOR ═════════════════════════════════════════════════════════════════════

function row(r, mae) { return { realizedR: r, maeR: mae }; }

t('STRESS-1', 'a win whose adverse excursion came within the cost of its stop is reclassified as a '
  + 'loss; one that never came close is untouched', function () {
  const rows = [row(2, 0.95), row(2, 0.10)];
  const s = O.obsCostStress(rows, 0.098);      // effective stop at 0.902R
  return { pass: s.wins === 2 && s.winsLost === 1 && s.stressedWins === 1
      && close(s.netR, 4) && close(s.stressedNetR, 1),
    detail: 'net ' + s.netR + 'R -> ' + s.stressedNetR + 'R, ' + s.winsLost + ' win reclassified' };
});

t('STRESS-2', 'a cost can only ever make an outcome worse. Losses stay losses and the stressed net '
  + 'is never above the original', function () {
  const rows = [row(2, 0.99), row(-1, 1.0), row(2, 0.2), row(-1, 1.0)];
  const bad = [0, 0.05, 0.098, 0.221, 0.5, 0.99].filter(function (c) {
    const s = O.obsCostStress(rows, c);
    return s.stressedNetR > s.netR || s.stressedWins > s.wins;
  });
  return { pass: bad.length === 0, detail: bad.length ? 'improved at cost ' + bad.join(',') : 'monotone across 6 cost levels' };
});

t('STRESS-3', 'a larger cost reclassifies at least as many wins -- the estimate is monotone in the '
  + 'cost, which is the property that makes two rows of the table comparable', function () {
  const rows = [row(2, 0.95), row(2, 0.85), row(2, 0.5), row(-1, 1.0)];
  const seq = [0.0, 0.05, 0.1, 0.2, 0.6].map(function (c) { return O.obsCostStress(rows, c).winsLost; });
  let ok = true;
  for (let i = 1; i < seq.length; i++) if (seq[i] < seq[i - 1]) ok = false;
  return { pass: ok, detail: 'wins lost by cost level: ' + seq.join(' -> ') };
});

t('STRESS-4', 'zero cost changes nothing except where excursion exactly reaches the stop, which is '
  + 'already a stop-out', function () {
  const rows = [row(2, 0.99), row(2, 0.5), row(-1, 1.0)];
  const s = O.obsCostStress(rows, 0);
  return { pass: close(s.netR, s.stressedNetR) && s.winsLost === 0,
    detail: 'net unchanged at ' + s.netR + 'R' };
});

t('STRESS-5', 'trades with no recorded excursion are EXCLUDED and counted, not assumed unaffected. '
  + 'A silently shrinking denominator is how a figure ends up describing a different sample', function () {
  const rows = [row(2, 0.95), { realizedR: 2, maeR: null }, { realizedR: -1 }, row(-1, 1.0)];
  const s = O.obsCostStress(rows, 0.098);
  return { pass: s.usable === 2 && s.total === 4 && close(s.coverage, 0.5),
    detail: s.usable + ' of ' + s.total + ' usable, coverage ' + (s.coverage * 100) + '%' };
});

t('STRESS-6', 'an empty or excursion-free sample returns nulls rather than a zero that would read '
  + 'as a result', function () {
  const empty = O.obsCostStress([], 0.098);
  const noExc = O.obsCostStress([{ realizedR: 2 }], 0.098);
  return { pass: empty.usable === 0 && empty.netR === null && empty.stressedNetR === null
      && noExc.usable === 0 && noExc.netR === null,
    detail: 'both return usable=0 with null figures' };
});

t('STRESS-7', 'an invalid or negative cost returns null rather than inventing a stress level', function () {
  return { pass: O.obsCostStress([row(2, 0.9)], null) === null
      && O.obsCostStress([row(2, 0.9)], -0.1) === null
      && O.obsCostStress([row(2, 0.9)], NaN) === null
      && O.obsCostStress([row(2, 0.9)], 'x') === null,
    detail: 'null, negative, NaN and non-numeric all refused' };
});

t('STRESS-8', 'the cost levels shown are the ones MEASURED on the forward corpus, and are labelled '
  + 'as measured rather than assumed', function () {
  const r = fn('obsRenderCostStress');
  return { pass: /c:0\.098/.test(r) && /c:0\.221/.test(r)
      && /OBS_COST_SOURCE_NOTE/.test(r) && /measured on the forward corpus, not assumed/.test(COST_SOURCE_NOTE),
    detail: '9.8% and 22.1%, both sourced to the corpus' };
});

t('STRESS-9', 'the panel states the estimate\'s limits: it does not move exit bars, and it cannot '
  + 'see setups the live path would have refused. Without those it reads as a re-run', function () {
  const r = fn('obsRenderCostStress');
  return { pass: /This is an estimate, not a re-run/.test(r)
      && /which bar an exit lands on/.test(r)
      && /refused to enter/.test(r)
      && /not a substitute for forward testing/.test(r),
    detail: 'all four limits disclosed' };
});

t('STRESS-10', 'the frictionless nature of replay is stated where the numbers are shown, not left '
  + 'to be inferred', function () {
  const r = fn('obsRenderCostStress');
  return { pass: /no spread and no slippage/.test(r) && /frictionless upper bound/.test(r)
      && /not a forecast/.test(r),
    detail: 'zero-cost basis disclosed in the panel' };
});

t('STRESS-11', 'the stress is shown for REPLAY only. Forward trades already paid these costs, and '
  + 'charging them twice would understate the live record', function () {
  const render = fn('renderObservatory');
  const i = render.indexOf('obsRenderCostStress');
  const repLine = render.slice(render.lastIndexOf('\n', i), render.indexOf('\n', i));
  return { pass: i > 0 && /rep\.sampleSize/.test(repLine) && /repRows/.test(repLine)
      && render.indexOf('obsRenderCostStress(fwdRows') === -1,
    detail: 'applied to replay rows only' };
});

t('STRESS-12', 'the excursions the estimator needs are carried onto the rows from the engine\'s own '
  + 'recorded values, never derived in the panel', function () {
  const rows = fn('obsRowsFromPackages');
  return { pass: /maeR:\(o&&typeof o\.maeR==='number'\)\?o\.maeR:null/.test(rows)
      && !/maeR:.*Math\./.test(rows),
    detail: 'maeR copied from the outcome, not computed' };
});

t('STRESS-13', 'the replay section is split BY STRATEGY. Replay now holds more than one strategy, '
  + 'and a single combined figure over two different strategies describes neither of them', function () {
  const render = fn('renderObservatory');
  const iSeg = render.indexOf("obsSegment(repRows,'strategyId')");
  const iStress = render.indexOf('obsRenderCostStress');
  return { pass: iSeg > 0 && iSeg < iStress,
    detail: 'replay segmented by strategyId before the stress table' };
});

results.forEach(function (r) {
  console.log((r.pass ? 'PASS' : 'FAIL') + ' -- ' + r.name + ': ' + r.desc + (r.detail ? '  [' + r.detail + ']' : ''));
});
const fails = results.filter(function (r) { return !r.pass; }).length;
console.log('---');
console.log(results.length + ' fixtures, ' + (results.length - fails) + ' PASS, ' + fails + ' FAIL');
process.exitCode = fails ? 1 : 0;

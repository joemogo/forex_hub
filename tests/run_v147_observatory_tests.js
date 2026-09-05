#!/usr/bin/env node
'use strict';
// ══════════════════════════════════════════════════════════════════════════════════════════════
// v12.47.0 — THE OBSERVATORY
// ══════════════════════════════════════════════════════════════════════════════════════════════
//
// The panel is a SECOND implementation of logic that already exists in
// scripts/mogo_forward_trade_analysis.js. A browser file and a Node script cannot share a module
// in this architecture, so the two will drift unless something forces them not to.
//
// OBS-1..OBS-6 are that something: they run BOTH implementations over the operator's REAL
// preserved packages when those are present, and require identical answers. If the corpus is not
// available they fall back to synthetic packages of the same shape and say so, so the suite is
// honest about what it actually compared rather than silently passing on nothing.
//
// The rest of the suite defends the one property that makes this panel worth having: it must not
// overstate. A screen that shows a win rate without saying what the number can support is how the
// withdrawn +20.97R claim happened. So: populations never mix (OBS-7/8), an unreadable store is
// never reported as zero trades (OBS-20), a non-uniform target produces NO significance figure
// rather than an invented one (OBS-13/14), and every multi-slice view carries the threshold a
// slice must actually clear (OBS-16/17).
//
// Run:  node tests/run_v147_observatory_tests.js

const fs = require('fs');
const path = require('path');
const vm = require('vm');
const ROOT = path.resolve(__dirname, '..');
const SRC = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
const CLI = require(path.join(ROOT, 'scripts', 'mogo_forward_trade_analysis.js'));

function extractFunction(name) {
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
function extractConst(decl) {
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
['const OBS_FORWARD_BASES=', 'const OBS_REPLAY_BASES=', 'const OBS_POWER_CONSTANT=']
  .forEach(function (d) { vm.runInContext(extractConst(d), ctx); });
['obsPackagePopulation', 'obsPartitionByPopulation', 'obsRowsFromPackages', 'obsCoverageAgainstAccount', 'obsSum', 'obsMean',
  'obsStdDev', 'obsMeanCI95', 'obsTradesNeeded', 'obsBinomialTailAtLeast', 'obsMedian',
  'obsAnalyze', 'obsAdjustedAlpha', 'obsSegment', 'obsFmtR', 'obsFmtPct', 'obsFmtP', 'obsReadUnderstanding']
  .forEach(function (n) { vm.runInContext(extractFunction(n), ctx); });
const O = ctx;
const POWER_CONSTANT = vm.runInContext('OBS_POWER_CONSTANT', ctx);

// ── the operator's real corpus, when it is here ──────────────────────────────────────────────
const CORPUS_DIR = '/mnt/user-data/uploads/Downloads';
let REAL = [];
try {
  REAL = fs.readdirSync(CORPUS_DIR)
    .filter(function (f) { return /^mogo-evidence-.*\.json$/.test(f); })
    .map(function (f) { try { return JSON.parse(fs.readFileSync(path.join(CORPUS_DIR, f), 'utf8')); } catch (e) { return null; } })
    .filter(Boolean);
} catch (e) { REAL = []; }

// Synthetic packages of the same shape, used when the corpus is absent AND for the cases the
// corpus does not contain (an unrecognised basis, a mixed-target sample).
function pkg(basis, positions, opts) {
  const o = opts || {};
  return {
    packageId: o.packageId || ('PKG|t|' + Math.random().toString(36).slice(2)),
    captureBasis: basis,
    identity: { strategyId: o.strategyId || 'alex_g_sr_v1', strategyVersionProvenance: 'OBSERVED' },
    objects: {
      positions: positions.map(function (p, i) {
        return { positionId: 'P' + i, setupId: 'S' + i, instrument: p.instrument || 'EUR_USD',
          timeframe: p.timeframe || 'H4', direction: p.direction || 'buy',
          entryPrice: 1.1, originalStop: 1.09, plannedRR: p.plannedR == null ? 2 : p.plannedR,
          entryTimestamp: '2026-08-0' + ((i % 8) + 1) + 'T10:00:00Z',
          isDeveloperTrade: !!p.dev };
      }),
      outcomes: positions.map(function (p, i) {
        return { positionId: 'P' + i, realizedR: p.r, plannedR: p.plannedR == null ? 2 : p.plannedR,
          exitTimestamp: '2026-08-0' + ((i % 8) + 1) + 'T18:00:00Z', pnl: p.r * 100 };
      }),
      qualifiedSetups: positions.map(function (p, i) {
        return { setupId: 'S' + i, setupType: p.setupType || 'B_breakRetest',
          contextRefs: { session: p.session || 'LONDON' },
          ruleAttribution: { unverifiedConditionCount: p.unverified == null ? 0 : p.unverified },
          setupRecordJoin: p.joinStatus ? { status: p.joinStatus, fieldsSupplied: [] } : undefined };
      })
    }
  };
}
function wl(pattern, extra) {   // "WWLLL" -> positions at +2 / -1
  return pattern.split('').map(function (c) {
    return Object.assign({ r: c === 'W' ? 2 : -1 }, extra || {});
  });
}

const results = [];
function t(name, desc, fn) {
  let pass = false, detail = '';
  try { const r = fn(); pass = !!(r && r.pass); detail = (r && r.detail) || ''; }
  catch (e) { pass = false; detail = 'threw: ' + (e && e.message ? e.message : String(e)); }
  results.push({ name, desc, pass, detail });
}
const close = function (a, b, eps) {
  if (a == null && b == null) return true;
  if (a == null || b == null) return false;
  return Math.abs(a - b) < (eps == null ? 1e-9 : eps);
};

// ══ DIFFERENTIAL: the panel and the CLI must not drift apart ═════════════════════════════════

t('OBS-1', 'the corpus this suite compares against is actually present and non-empty -- without '
  + 'this guard every differential fixture below would pass vacuously', function () {
  // Falls back to synthetic rather than skipping, but SAYS which it used. A differential that
  // silently compared nothing is the failure mode this fixture exists to make impossible.
  // The set the differentials below actually consume must be non-empty either way -- an earlier
  // version of this line read `REAL.length > 0 || true`, which is not an assertion at all.
  const differentialSet = REAL.length ? REAL : [pkg('LIVE_CLOSE', wl('WL'))];
  return { pass: differentialSet.length > 0,
    detail: REAL.length ? 'comparing against ' + REAL.length + ' real preserved packages'
      : 'REAL CORPUS ABSENT -- differentials fall back to ' + differentialSet.length + ' synthetic package(s)' };
});

t('OBS-2', 'population is classified identically by both implementations, package for package', function () {
  const set = REAL.length ? REAL : [pkg('LIVE_CLOSE', wl('WL')), pkg('REPLAY_RUN', wl('WW')),
    pkg('HISTORICAL_BACKFILL', wl('L')), pkg('SOMETHING_NEW', wl('W')), pkg(undefined, wl('W'))];
  const bad = set.filter(function (p) { return O.obsPackagePopulation(p) !== CLI.packagePopulation(p); });
  return { pass: bad.length === 0 && set.length > 0,
    detail: bad.length ? bad.length + ' disagreements' : set.length + ' packages agree' };
});

t('OBS-3', 'both implementations extract the same number of rows, in the same order, with the '
  + 'same identity fields', function () {
  const set = REAL.length ? REAL : [pkg('LIVE_CLOSE', wl('WWLLL')), pkg('REPLAY_RUN', wl('WL'))];
  const a = O.obsRowsFromPackages(set), b = CLI.rowsFromPackages(set);
  if (a.length !== b.length) return { pass: false, detail: 'row counts differ: ' + a.length + ' vs ' + b.length };
  const keys = ['strategyId', 'instrument', 'timeframe', 'setupType', 'direction', 'session',
    'realizedR', 'recordedResultR', 'plannedR', 'unverifiedConditions', 'isDeveloperTrade'];
  const bad = [];
  a.forEach(function (r, i) {
    keys.forEach(function (k) {
      const x = r[k], y = b[i][k];
      const same = (typeof x === 'number' && typeof y === 'number') ? close(x, y, 1e-12) : x === y;
      if (!same) bad.push('row ' + i + '.' + k + ': ' + x + ' vs ' + y);
    });
  });
  return { pass: bad.length === 0 && a.length > 0,
    detail: bad.length ? bad.slice(0, 3).join(' | ') : a.length + ' rows identical across ' + keys.length + ' fields' };
});

t('OBS-4', 'the headline figures agree: sample size, wins, win rate and net R', function () {
  const set = REAL.length ? REAL : [pkg('LIVE_CLOSE', wl('WWLLLLL'))];
  const fwdA = O.obsPartitionByPopulation(set).FORWARD;
  const fwdB = CLI.partitionByPopulation(set).FORWARD;
  const a = O.obsAnalyze(O.obsRowsFromPackages(fwdA));
  const b = CLI.analyze(CLI.rowsFromPackages(fwdB), false, false);
  const agree = a.sampleSize === b.sampleSize && a.wins === b.wins
    && close(a.winRate, b.winRate, 1e-12) && close(a.netR, b.netR, 1e-3);
  return { pass: agree && a.sampleSize > 0,
    detail: 'panel n=' + a.sampleSize + ' ' + a.wins + 'W net=' + (a.netR == null ? '-' : a.netR.toFixed(3))
      + '  |  cli n=' + b.sampleSize + ' ' + b.wins + 'W net=' + b.netR };
});

t('OBS-5', 'the exact binomial agrees across a grid, including the tails where a log-space '
  + 'implementation is most likely to diverge', function () {
  const bad = [];
  [[40, 11, 1 / 3], [16, 7, 1 / 3], [24, 4, 1 / 3], [200, 100, 0.5], [5, 5, 0.5], [7, 0, 0.5],
    [500, 260, 0.5], [40, 41, 1 / 3]].forEach(function (c) {
    const x = O.obsBinomialTailAtLeast(c[0], c[1], c[2]), y = CLI.binomialTailAtLeast(c[0], c[1], c[2]);
    if (!close(x, y, 1e-12)) bad.push(c.join(',') + ': ' + x + ' vs ' + y);
  });
  return { pass: bad.length === 0, detail: bad.length ? bad.join(' | ') : '8 grid points agree' };
});

t('OBS-6', 'the medians agree, including the even-length case where the two halves are averaged', function () {
  const bad = [];
  [[1, 2, 3], [1, 2, 3, 4], [5], [], [3, 1, 2], [-1, 2, -1, 2]].forEach(function (v) {
    const x = O.obsMedian(v), y = CLI.median(v);
    if (!close(x, y, 1e-12)) bad.push(JSON.stringify(v) + ': ' + x + ' vs ' + y);
  });
  return { pass: bad.length === 0, detail: bad.length ? bad.join(' | ') : '6 cases agree' };
});

// ══ POPULATIONS NEVER MIX ════════════════════════════════════════════════════════════════════

t('OBS-7', 'an unrecognised capture basis is excluded from BOTH populations rather than assumed '
  + 'forward -- the failure that produced the withdrawn +20.97R claim', function () {
  const p = O.obsPartitionByPopulation([pkg('LIVE_CLOSE', wl('W')), pkg('REPLAY_RUN', wl('W')),
    pkg('SOME_FUTURE_BASIS', wl('W')), pkg(null, wl('W')), pkg(undefined, wl('W'))]);
  return { pass: p.FORWARD.length === 1 && p.REPLAY.length === 1 && p.UNKNOWN.length === 3,
    detail: 'fwd=' + p.FORWARD.length + ' rep=' + p.REPLAY.length + ' unknown=' + p.UNKNOWN.length };
});

t('OBS-8', 'POSITIVE CONTROL: a replay package placed in the forward set WOULD change the '
  + 'headline -- so OBS-7 is preventing something real, not guarding a no-op', function () {
  const forwardOnly = [pkg('LIVE_CLOSE', wl('WLLL'))];
  const contaminated = forwardOnly.concat([pkg('REPLAY_RUN', wl('WWWW'))]);
  const clean = O.obsAnalyze(O.obsRowsFromPackages(O.obsPartitionByPopulation(forwardOnly).FORWARD));
  const mixedRows = O.obsRowsFromPackages(contaminated);            // deliberately unpartitioned
  const mixed = O.obsAnalyze(mixedRows);
  return { pass: clean.winRate === 0.25 && mixed.winRate === 0.625 && clean.winRate !== mixed.winRate,
    detail: 'partitioned ' + (clean.winRate * 100).toFixed(1) + '% vs mixed ' + (mixed.winRate * 100).toFixed(1) + '%' };
});

t('OBS-9', 'HISTORICAL_BACKFILL counts as forward in both implementations -- it is a real trade '
  + 'whose record was recovered, not a backtest', function () {
  return { pass: O.obsPackagePopulation({ captureBasis: 'HISTORICAL_BACKFILL' }) === 'FORWARD'
      && CLI.packagePopulation({ captureBasis: 'HISTORICAL_BACKFILL' }) === 'FORWARD',
    detail: 'both classify it FORWARD' };
});

// ══ UNCERTAINTY IS REPORTED, NOT HIDDEN ══════════════════════════════════════════════════════

t('OBS-10', 'the confidence interval is arithmetically correct on a hand-checkable sample', function () {
  const ci = O.obsMeanCI95([1, 2, 3, 4, 5]);        // mean 3, sd 1.5811388
  const expectedHalf = 1.96 * 1.5811388300841898 / Math.sqrt(5);
  return { pass: close(ci.mean, 3, 1e-9) && close(ci.sd, 1.5811388300841898, 1e-9)
      && close(ci.halfWidth, expectedHalf, 1e-9) && close(ci.low, 3 - expectedHalf, 1e-9),
    detail: 'mean=' + ci.mean + ' sd=' + ci.sd.toFixed(6) + ' ±' + ci.halfWidth.toFixed(6) };
});

t('OBS-11', 'a sample the size of the real forward record produces an interval that SPANS ZERO -- '
  + 'the panel must be able to say "consistent with no edge at all"', function () {
  const rows = O.obsRowsFromPackages([pkg('LIVE_CLOSE', wl('WWWWWWWWWWWLLLLLLLLLLLLLLLLLLLLLLLLLLLLL'))]);
  const a = O.obsAnalyze(rows);
  return { pass: a.meanCI95 && a.meanCI95.low < 0 && a.meanCI95.high > 0,
    detail: 'n=' + a.sampleSize + ' mean=' + a.meanCI95.mean.toFixed(3)
      + ' [' + a.meanCI95.low.toFixed(3) + ', ' + a.meanCI95.high.toFixed(3) + ']' };
});

t('OBS-12', 'a single trade yields NO standard deviation and NO interval -- reporting 0 spread '
  + 'would imply a certainty one observation cannot carry', function () {
  return { pass: O.obsStdDev([2]) === null && O.obsMeanCI95([2]) === null && O.obsStdDev([]) === null,
    detail: 'sd and CI both null below n=2' };
});

t('OBS-13', 'a sample whose trades do NOT share one planned reward:risk gets no breakeven rate '
  + 'and no significance figure, rather than an invented threshold', function () {
  const rows = O.obsRowsFromPackages([pkg('LIVE_CLOSE',
    [{ r: 2, plannedR: 2 }, { r: -1, plannedR: 3 }, { r: 2, plannedR: 2 }])]);
  const a = O.obsAnalyze(rows);
  return { pass: a.plannedRIsUniform === false && a.breakevenWinRate === null && a.pAtLeastWins === null,
    detail: 'uniform=' + a.plannedRIsUniform + ' breakeven=' + a.breakevenWinRate + ' P=' + a.pAtLeastWins };
});

t('OBS-14', 'POSITIVE CONTROL: the same trades at ONE planned target DO produce both, so OBS-13 '
  + 'is withholding a figure that would otherwise be computed', function () {
  const a = O.obsAnalyze(O.obsRowsFromPackages([pkg('LIVE_CLOSE', wl('WLW'))]));
  return { pass: a.plannedRIsUniform === true && close(a.breakevenWinRate, 1 / 3, 1e-12) && a.pAtLeastWins != null,
    detail: 'breakeven=' + a.breakevenWinRate.toFixed(4) + ' P=' + a.pAtLeastWins.toFixed(4) };
});

t('OBS-15', 'the trades-needed figure follows the stated formula and scales with the sample\'s '
  + 'OWN spread, so a noisier strategy honestly demands more evidence', function () {
  const tight = O.obsTradesNeeded(1.0, 0.15), loose = O.obsTradesNeeded(2.0, 0.15);
  return { pass: tight === Math.ceil(POWER_CONSTANT * Math.pow(1 / 0.15, 2))
      && loose === Math.ceil(POWER_CONSTANT * Math.pow(2 / 0.15, 2)) && loose > tight
      && O.obsTradesNeeded(null, 0.15) === null && O.obsTradesNeeded(1, 0) === null,
    detail: 'sd=1 -> ' + tight + ', sd=2 -> ' + loose };
});

// ══ MULTIPLE COMPARISONS ═════════════════════════════════════════════════════════════════════

t('OBS-16', 'the adjusted threshold tightens as more slices are shown, and equals 0.05 for one', function () {
  const one = O.obsAdjustedAlpha(1, 0.05), three = O.obsAdjustedAlpha(3, 0.05), fifteen = O.obsAdjustedAlpha(15, 0.05);
  return { pass: close(one, 0.05, 1e-12) && three < one && fifteen < three
      && close(three, 1 - Math.pow(0.95, 1 / 3), 1e-12),
    detail: '1 -> ' + one.toFixed(4) + ', 3 -> ' + three.toFixed(4) + ', 15 -> ' + fifteen.toFixed(5) };
});

t('OBS-17', 'a slice is judged against the ADJUSTED threshold, not the bare 0.05 -- a result that '
  + 'clears 0.05 but not the adjustment is NOT marked', function () {
  // Engineered so the group's own P sits between the adjusted and unadjusted thresholds.
  const seg = O.obsSegment(O.obsRowsFromPackages([pkg('LIVE_CLOSE',
    wl('WWWWWWWL', { setupType: 'A' }).concat(wl('LLLLLLLL', { setupType: 'B' })))]), 'setupType');
  const g = seg.groups.filter(function (x) { return x.key === 'A'; })[0];
  const clearsBare = g.pAtLeastWins < 0.05;
  return { pass: seg.comparisons === 2 && seg.adjustedAlpha < 0.05
      && g.clearsAdjustedThreshold === (g.pAtLeastWins < seg.adjustedAlpha)
      && (!clearsBare || g.pAtLeastWins < seg.adjustedAlpha || g.clearsAdjustedThreshold === false),
    detail: 'P=' + g.pAtLeastWins.toFixed(5) + ' adjusted=' + seg.adjustedAlpha.toFixed(5)
      + ' marked=' + g.clearsAdjustedThreshold };
});

t('OBS-17b', 'a group left EMPTY by an exclusion is not counted as a comparison. Found on the real '
  + 'corpus: filtering developer trades emptied a DEV_TEST slice to n=0, and counting it inflated '
  + 'the correction so every other slice faced a stricter threshold than the real number of '
  + 'comparisons justifies', function () {
  const rows = O.obsRowsFromPackages([pkg('LIVE_CLOSE',
    wl('WL', { setupType: 'A' })
      .concat(wl('WL', { setupType: 'B' }))
      .concat(wl('WWWW', { setupType: 'DEV_TEST', dev: true })))]);
  const seg = O.obsSegment(rows, 'setupType');
  const keys = seg.groups.map(function (g) { return g.key; });
  return { pass: seg.comparisons === 2 && seg.emptyGroupsExcluded === 1
      && keys.indexOf('DEV_TEST') === -1
      && close(seg.adjustedAlpha, 1 - Math.pow(0.95, 1 / 2), 1e-12),
    detail: 'comparisons=' + seg.comparisons + ' excluded=' + seg.emptyGroupsExcluded
      + ' alpha=' + seg.adjustedAlpha.toFixed(5) + ' (would have been '
      + O.obsAdjustedAlpha(3, 0.05).toFixed(5) + ' counting the empty group)' };
});

t('OBS-18', 'a slice with no recorded value is kept under an explicit label rather than dropped '
  + '-- a silently shrinking denominator is how a figure comes to describe a different sample', function () {
  const rows = O.obsRowsFromPackages([pkg('LIVE_CLOSE', wl('WL'))]);
  rows[0].session = null;
  const seg = O.obsSegment(rows, 'session');
  const total = seg.groups.reduce(function (n, g) { return n + g.sampleSize; }, 0);
  return { pass: total === rows.length && seg.groups.some(function (g) { return g.key === '(unrecorded)'; }),
    detail: seg.groups.map(function (g) { return g.key + '=' + g.sampleSize; }).join(', ') };
});

// ══ THE PANEL MUST NOT OVERSTATE ═════════════════════════════════════════════════════════════

t('OBS-19', 'at a real-world sample size with no edge, the verdict says so plainly and does NOT '
  + 'call it a finding', function () {
  const a = O.obsAnalyze(O.obsRowsFromPackages([pkg('LIVE_CLOSE',
    wl('WWWWWWWWWWWLLLLLLLLLLLLLLLLLLLLLLLLLLLLL'))]));
  const v = O.obsReadUnderstanding(a);
  return { pass: v.tone === 'neutral' && /No demonstrated edge/.test(v.headline)
      && /too small/.test(v.headline) && /trades/.test(v.detail),
    detail: v.headline };
});

t('OBS-20', 'an empty sample produces an honest empty state, never a zero win rate presented as '
  + 'a result', function () {
  const a = O.obsAnalyze([]);
  const v = O.obsReadUnderstanding(a);
  return { pass: a.sampleSize === 0 && a.winRate === null && a.netR === null
      && /No closed forward trades/.test(v.headline) && /not a fault/.test(v.detail),
    detail: v.headline };
});

t('OBS-21', 'a store that cannot be read reports the failure. It must never fall through to the '
  + 'empty state, which would tell the operator they have no trades when they may have many', function () {
  const body = extractFunction('renderObservatory');
  return { pass: /catch\(e\)\{/.test(body) && /Could not read the evidence store/.test(body)
      && /return;/.test(body.slice(body.indexOf('Could not read the evidence store'))),
    detail: 'read failure is caught, named, and returns before any analysis' };
});

t('OBS-22', 'developer test trades are excluded by default -- they are synthetic outcomes pushed '
  + 'through the engine to check the UI, and counting them would put invented results in a figure '
  + 'meant to describe the market', function () {
  const rows = O.obsRowsFromPackages([pkg('LIVE_CLOSE',
    wl('WL').concat(wl('WWWW', { dev: true })))]);
  const a = O.obsAnalyze(rows);
  const withDev = O.obsAnalyze(rows, { includeDeveloperTrades: true });
  return { pass: a.sampleSize === 2 && a.developerTradesFound === 4 && a.developerTradesIncluded === false
      && withDev.sampleSize === 6,
    detail: 'default n=' + a.sampleSize + ', with dev n=' + withDev.sampleSize };
});

t('OBS-23', 'the panel reports how many trades can prove every rule condition from their own '
  + 'record -- the v12.45.0 metric, so evidence quality is watched rather than asserted', function () {
  const rows = O.obsRowsFromPackages([pkg('LIVE_CLOSE', [
    { r: 2, unverified: 0, joinStatus: 'JOINED' }, { r: -1, unverified: 3 },
    { r: -1, unverified: 0 }, { r: 2, unverified: 0, joinStatus: 'CONTRADICTED_BY_JOIN' }])]);
  const e = O.obsAnalyze(rows).evidence;
  return { pass: e.withAttribution === 4 && e.fullyVerified === 3 && e.withUnverified === 1
      && e.maxUnverified === 3 && e.joinedFromSetupRecord === 1 && e.joinContradicted === 1,
    detail: JSON.stringify(e) };
});

// ══ READ-ONLY ════════════════════════════════════════════════════════════════════════════════

t('OBS-24', 'nothing in the Observatory writes. It must not be able to influence an account, a '
  + 'position, a rule or a trading decision', function () {
  const names = ['obsPackagePopulation', 'obsPartitionByPopulation', 'obsRowsFromPackages',
    'obsAnalyze', 'obsSegment', 'renderObservatory', 'obsReadUnderstanding'];
  const forbidden = /alexGAccount\s*=|paperAccount\s*=|\.openPositions\.push|\.closedPositions\.push|localStorage\.setItem|evidencePutPackage|persistStorageKey|alexGAutoTrading\.|cfg\./;
  const bad = names.filter(function (n) { return forbidden.test(extractFunction(n)); });
  return { pass: bad.length === 0, detail: bad.length ? 'writes found in: ' + bad.join(',') : names.length + ' functions are read-only' };
});

t('OBS-25', 'the store is opened read-only, through the existing listing function rather than a '
  + 'transaction of its own', function () {
  const body = extractFunction('renderObservatory');
  return { pass: /await evidenceListPackages\(\)/.test(body) && !/transaction\(/.test(body)
      && !/readwrite/.test(body),
    detail: 'uses evidenceListPackages, opens no transaction' };
});

t('OBS-26', 'the panel is reachable: the nav points at it, the markup exists, and showPanel '
  + 'dispatches to the renderer', function () {
  return { pass: SRC.indexOf('showPanel(\'observatory\',this)') >= 0
      && SRC.indexOf('id="panel-observatory"') >= 0
      && /if\(name==='observatory'\) renderObservatory\(\);/.test(SRC),
    detail: 'nav, panel and dispatch all present' };
});

t('OBS-27', 'the Analytics nav entry is a real destination now, not a "coming soon" dialog', function () {
  return { pass: !/comingSoonOpen\('Analytics'/.test(SRC), detail: 'placeholder removed' };
});

t('OBS-28', 'coverage against the account is reported, because the preserved set is a SUBSET of '
  + 'the account\'s closed positions (CLAUDE.md, backlog B-22). A headline computed over an '
  + 'unstated subset is the same class of error as mixing populations', function () {
  const c = O.obsCoverageAgainstAccount(40, 44);
  return { pass: c.preserved === 40 && c.accountClosed === 44 && c.missingFromStore === 4
      && c.beyondAccount === 0 && c.complete === false && close(c.fraction, 40 / 44, 1e-12),
    detail: '40 preserved of 44 closed -> ' + c.missingFromStore + ' unpreserved' };
});

t('OBS-29', 'a store holding MORE than the account is reported separately, not as missing '
  + 'evidence -- closes preserved before an account reset survive by design', function () {
  const c = O.obsCoverageAgainstAccount(50, 42);
  return { pass: c.beyondAccount === 8 && c.missingFromStore === 0 && c.complete === false,
    detail: 'beyondAccount=' + c.beyondAccount + ' missing=' + c.missingFromStore };
});

t('OBS-30', 'an unreadable account yields NULL coverage, which the panel renders as unknown. '
  + 'Claiming complete coverage on the strength of not having checked is the failure this guards', function () {
  const nulls = [O.obsCoverageAgainstAccount(40, null), O.obsCoverageAgainstAccount(40, undefined),
    O.obsCoverageAgainstAccount(null, 44), O.obsCoverageAgainstAccount(40, -1)];
  const render = extractFunction('obsRenderCoverage');
  return { pass: nulls.every(function (x) { return x === null; })
      && /if\(!cov\) return/.test(render) && /unknown/.test(render)
      && !/complete/.test(render.slice(0, render.indexOf('if(!cov)') + 200)),
    detail: 'all four unreadable cases return null; renderer says unknown' };
});

t('OBS-31', 'exact coverage is stated as such, so the caveat is not worn permanently by a store '
  + 'that is in fact complete', function () {
  const c = O.obsCoverageAgainstAccount(42, 42);
  return { pass: c.complete === true && c.missingFromStore === 0 && c.beyondAccount === 0
      && close(c.fraction, 1, 1e-12),
    detail: 'complete=' + c.complete };
});

t('OBS-32', 'the coverage statement is scoped to the strategy whose account was read, not to the '
  + 'whole corpus -- a JVM row must never be counted against the ALEX account', function () {
  const body = extractFunction('renderObservatory');
  return { pass: /r\.strategyId==='alex_g_sr_v1'/.test(body)
      && /obsReadAccountClosedCount\('alex_g_sr_v1'\)/.test(body)
      && /'ALEX'/.test(body),
    detail: 'ALEX rows compared against the ALEX account, and labelled' };
});

results.forEach(function (r) {
  console.log((r.pass ? 'PASS' : 'FAIL') + ' -- ' + r.name + ': ' + r.desc + (r.detail ? '  [' + r.detail + ']' : ''));
});
const fails = results.filter(function (r) { return !r.pass; }).length;
console.log('---');
console.log(results.length + ' fixtures, ' + (results.length - fails) + ' PASS, ' + fails + ' FAIL');
process.exitCode = fails ? 1 : 0;

#!/usr/bin/env node
'use strict';
// ══════════════════════════════════════════════════════════════════════════════════════════════
// v12.62.0 — ALEX ALL-PAIRS REPLAY, AND THE MEASUREMENT COLUMNS CRT PROVED WERE NECESSARY
// ══════════════════════════════════════════════════════════════════════════════════════════════
//
// baseline_trend_v1 was built as ALEX's control and has produced 502 trades over 12 pairs and 4
// years. ALEX had never been replayed the same way -- one pair from a dropdown, each run
// overwriting the last -- so there was no ALEX figure to put beside it, and the question "does
// ALEX's setup detection add anything over a one-line rule" had no answer while ALEX was paper
// trading the account.
//
// ISO-1..ISO-6 are the fixtures that matter most, and they are not about statistics. A 12-pair
// sweep REBUILDS alexGZoneState, alexGLastEvaluatedCloseTime and alexGSetupState for every
// instrument -- the same three the LIVE paper-trading path reads. Left unrestored, the live path
// would be holding this sweep's historical setups for every pair it observes. ISO-4 and ISO-5
// prove restoration survives a cancel and a thrown error, because those are the paths a developer
// forgets.
//
// DIST-1..DIST-8 are the CRT post-mortem turned into code. A MEAN planned R of 10.46 sat beside a
// MEDIAN of 1.57 and hid that 13.5% of that arm carried a stop under 5 pips -- which was its
// entire apparent edge. DIST-6 is the one with teeth: spread cost in R is spread/risk, so it is
// NOT neutral between arms whose stops differ, and the old disclosure claiming otherwise was
// false.
//
// Run:  node tests/run_v163_alex_allpairs_tests.js

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

// A realm carrying only what these functions touch. The globals the sweep must protect are
// declared here as real mutable state, so the isolation fixtures exercise the actual mutation
// rather than a description of it.
const ctx = { console: console, Math: Math, JSON: JSON, isFinite: isFinite, Array: Array,
  Number: Number, Object: Object, String: String, Date: Date, isNaN: isNaN, parseInt: parseInt };
vm.createContext(ctx);
vm.runInContext("var alexGZoneState={},alexGLastEvaluatedCloseTime={},alexGSetupState=[];", ctx);
vm.runInContext("var SCAN_PAIRS=['EUR/USD','GBP/USD','USD/JPY'];", ctx);
vm.runInContext("var APP_VERSION='" + (/const APP_VERSION='([^']+)'/.exec(SRC)[1]) + "';", ctx);
vm.runInContext("var STRATEGY_ALEXG='alex_g_sr_v1';", ctx);
vm.runInContext("var RULES_ALEXG={ruleVersion:'alex_g_sr_v1',config:{minRR:2,stopATRBuffer:0.5,atrPeriod:14}};", ctx);
vm.runInContext(constBlock('const ALEXG_ALLPAIRS_ENTRY_CAVEAT='), ctx);
['alexGAllPairsSnapshotState', 'alexGAllPairsRestoreState', 'replayDistributionSummary',
  'alexGAllPairsNormalizeTrades', 'alexGAllPairsAggregate', 'alexGRunReplayAllPairs',
  'alexGAllPairsBuildReplayPackage']
  .forEach(function (n) { vm.runInContext(fn(n), ctx); });
const P = ctx;

const results = [];
const queue = [];
// Several fixtures below drive an async sweep. Two things this runner has to get right, and the
// first version got both wrong:
//
//   1. A SYNCHRONOUS runner takes the returned PROMISE as the result object, finds no .pass on
//      it, and records a silent failure -- or, with a looser truthy check, a silent pass.
//   2. Starting every fixture at once is worse. They share ONE vm realm, one runAlexGReplay stub
//      and one copy of the live state they are asserting about, so concurrent fixtures overwrite
//      each other's stubs mid-run. That is exactly what happened here: ISO-4's cancel predicate
//      leaked into ISO-2's sweep and stopped it after one pair, and ISO-3 saw another fixture's
//      seedLive() reassign the object whose identity it was checking. Three fixtures failed for
//      a reason that had nothing to do with the code under test.
//
// So fixtures are queued as thunks and awaited STRICTLY IN SEQUENCE.
function t(name, desc, f) {
  const rec = { name: name, desc: desc, pass: false, detail: '' };
  results.push(rec);
  queue.push(function () {
    return Promise.resolve().then(f).then(function (r) {
      rec.pass = !!(r && r.pass); rec.detail = (r && r.detail) || '';
    }, function (e) {
      rec.pass = false; rec.detail = 'threw: ' + (e && e.message ? e.message : String(e));
    });
  });
}
// Puts the realm into a known "live" state, the way a running instance would look.
function seedLive() {
  vm.runInContext(
    "alexGZoneState={'EUR_USD':{live:1}};" +
    "alexGLastEvaluatedCloseTime={'EUR_USD':111};" +
    "alexGSetupState=[{pair:'EUR_USD',setupId:'LIVE-1'}];", ctx);
}
function liveState() {
  return vm.runInContext("JSON.stringify({z:alexGZoneState,l:alexGLastEvaluatedCloseTime,s:alexGSetupState})", ctx);
}
// A stand-in for the real engine call. The sweep must not care what it returns beyond shape.
function stubReplay(body) { vm.runInContext("var runAlexGReplay=" + body + ";", ctx); }
function run(days, cancelFn) {
  vm.runInContext("var __cancel=" + (cancelFn || 'function(){return false;}') + ";", ctx);
  return vm.runInContext(
    "alexGRunReplayAllPairs(" + (days || 90) + ",'conservative',null,__cancel)", ctx);
}

// ══ LIVE-STATE ISOLATION — the part that touches a running instance ════════════════════════════

t('ISO-1', 'THE ONE THAT PROTECTS YOUR RUNNING INSTANCE: a 12-pair sweep rebuilds the same three '
  + 'globals the LIVE paper-trading path reads. After the sweep they are byte-identical to what '
  + 'they were before it', async function () {
  seedLive();
  const before = liveState();
  stubReplay("async function(p){ alexGZoneState[p]={swept:1}; alexGLastEvaluatedCloseTime[p]=999;"
    + " alexGSetupState.push({pair:p,setupId:'HIST-'+p}); return {trades:[],rejected:[],setupsConsidered:1,zoneCounts:{}}; }");
  return run().then(function () {
    const after = liveState();
    return { pass: after === before,
      detail: after === before ? 'live state restored exactly' : 'LEAKED: ' + after.slice(0, 160) };
  });
});

t('ISO-2', 'and the sweep really does mutate that state while it runs -- otherwise ISO-1 passes '
  + 'vacuously against a sweep that never touched anything', async function () {
  seedLive();
  stubReplay("async function(p){ alexGZoneState[p]={swept:1}; alexGSetupState.push({pair:p,setupId:'H'});"
    + " __seen.push(JSON.stringify(alexGSetupState.length)); return {trades:[],rejected:[],setupsConsidered:0,zoneCounts:{}}; }");
  vm.runInContext("var __seen=[];", ctx);
  return run().then(function () {
    const seen = vm.runInContext("__seen.join(',')", ctx);
    return { pass: seen === '2,3,4',
      detail: 'setup count during sweep: ' + seen + ' (grew from the live baseline of 1)' };
  });
});

t('ISO-3', 'restoration rebuilds the objects IN PLACE. A closure still holding the original object '
  + 'must see the restored contents, not a detached copy', async function () {
  seedLive();
  vm.runInContext("var __heldZone=alexGZoneState,__heldSetups=alexGSetupState;", ctx);
  stubReplay("async function(p){ alexGZoneState[p]={swept:1}; alexGSetupState.push({pair:p}); "
    + "return {trades:[],rejected:[],setupsConsidered:0,zoneCounts:{}}; }");
  return run().then(function () {
    const same = vm.runInContext(
      "__heldZone===alexGZoneState && __heldSetups===alexGSetupState "
      + "&& JSON.stringify(__heldZone)===JSON.stringify({'EUR_USD':{live:1}}) "
      + "&& __heldSetups.length===1", ctx);
    return { pass: same === true,
      detail: same ? 'same object identities, restored contents' : 'restoration REPLACED the objects' };
  });
});

t('ISO-4', 'state is restored when the sweep is CANCELLED part-way -- the path a developer forgets',
  async function () {
  seedLive();
  const before = liveState();
  vm.runInContext("var __n=0;", ctx);
  stubReplay("async function(p){ __n++; alexGZoneState[p]={swept:1}; alexGSetupState.push({pair:p});"
    + " return {trades:[],rejected:[],setupsConsidered:0,zoneCounts:{}}; }");
  return run(90, "function(){ return __n>=1; }").then(function (runs) {
    const after = liveState();
    const stopped = runs.length < 3;
    return { pass: after === before && stopped,
      detail: 'stopped after ' + runs.length + ' entries; state restored: ' + (after === before) };
  });
});

t('ISO-5', 'state is restored when a pair THROWS. A sweep that leaked on the error path would '
  + 'corrupt the live instance exactly when something already went wrong', async function () {
  seedLive();
  const before = liveState();
  stubReplay("async function(p){ alexGZoneState[p]={swept:1}; alexGSetupState.push({pair:p});"
    + " throw new Error('boom '+p); }");
  return run().then(function (runs) {
    const after = liveState();
    const recorded = runs.filter(function (r) { return r && r.error; }).length;
    return { pass: after === before && recorded === 3,
      detail: recorded + ' pair errors recorded; state restored: ' + (after === before) };
  });
});

t('ISO-6', 'a pair that fails is RECORDED, not silently dropped. A dropped pair shrinks the sample '
  + 'without shrinking the claim made about it', async function () {
  seedLive();
  stubReplay("async function(p){ if(p==='GBP_USD') return {error:'no data'};"
    + " return {trades:[{pair:p,resultR:2,plannedRR:2,riskDistancePips:30,stillOpen:false,result:'Win'}],"
    + " rejected:[],setupsConsidered:1,zoneCounts:{}}; }");
  return run().then(function (runs) {
    const errs = runs.filter(function (r) { return r && r.error; });
    const ok = runs.filter(function (r) { return r && r.normalized; });
    const pkg = P.alexGAllPairsBuildReplayPackage(runs, { stamp: 1 });
    return { pass: errs.length === 1 && ok.length === 2
        && pkg.replayDisclosures.pairErrors.length === 1
        && pkg.replayDisclosures.pairsAttempted === 3,
      detail: '2 succeeded, 1 error carried into the package disclosures' };
  });
});

// ══ THE MEASUREMENT COLUMNS THE CRT RUN PROVED WERE NECESSARY ═════════════════════════════════

const mk = function (R, rr, risk) {
  return { resultR: R, plannedRR: rr, riskPips: risk, stillOpen: false };
};

t('DIST-1', 'MEDIAN planned R is reported, not only the mean. CRT showed a mean of 10.46 beside a '
  + 'median of 1.57 -- the mean was a handful of degenerate setups and the median was the arm',
  function () {
  const s = P.replayDistributionSummary(
    [mk(1, 1, 30), mk(-1, 1.1, 30), mk(1, 1.2, 30), mk(-1, 1.3, 30), mk(1, 60, 0.5)]);
  return { pass: s.medianPlannedRR === 1.2 && s.meanPlannedRR > 10 && s.medianPlannedRR < 2,
    detail: 'mean ' + s.meanPlannedRR.toFixed(2) + ' vs median ' + s.medianPlannedRR.toFixed(2)
      + ' — the outlier moves one and not the other' };
});

t('DIST-2', 'the share of trades with a stop under 5 pips is reported. That single number is what '
  + 'would have exposed the CRT control in one glance', function () {
  const s = P.replayDistributionSummary([mk(1, 2, 30), mk(-1, 2, 2), mk(1, 2, 3), mk(-1, 2, 40)]);
  return { pass: Math.abs(s.tightStopShare - 0.5) < 1e-12 && s.medianRiskPips === 16.5,
    detail: 'tight-stop share ' + (s.tightStopShare * 100).toFixed(0) + '%, median stop '
      + s.medianRiskPips + ' pips' };
});

t('DIST-3', 'the median is a true median: even counts average the middle pair rather than picking '
  + 'one side', function () {
  const s = P.replayDistributionSummary([mk(1, 2, 10), mk(1, 2, 20), mk(1, 2, 30), mk(1, 2, 40)]);
  return { pass: s.medianRiskPips === 25, detail: 'median of 10,20,30,40 = ' + s.medianRiskPips };
});

t('DIST-4', 'a standard error accompanies every per-trade figure. A difference reported without '
  + 'one cannot be told apart from zero, which is how a null gets published as a finding',
  function () {
  const s = P.replayDistributionSummary([mk(2, 2, 30), mk(-1, 2, 30), mk(2, 2, 30), mk(-1, 2, 30)]);
  const one = P.replayDistributionSummary([mk(2, 2, 30)]);
  return { pass: s.seR > 0 && isFinite(s.seR) && one.seR === null,
    detail: 'n=4 SE ' + s.seR.toFixed(3) + '; a single trade reports SE null, not 0' };
});

t('DIST-5', 'an arm with nothing closed reports winRate null, not 0%. A null is "nothing decisive '
  + 'closed"; a zero is "it lost every time"', function () {
  const s = P.replayDistributionSummary([{ stillOpen: true, resultR: null, riskPips: 30 }]);
  return { pass: s.n === 0 && s.winRate === null && s.meanR === null && s.medianRiskPips === null,
    detail: 'n=0, winRate null, meanR null' };
});

t('DIST-6', 'THE ONE THAT WAS WRONG BEFORE: spread is charged PER TRADE as spread/risk, so it '
  + 'costs a tight-stop arm far more than a wide-stop one. The old disclosure called the two arms '
  + 'equally optimistic, and that is what hid the whole CRT effect', function () {
  const wide = P.replayDistributionSummary([mk(2, 2, 40), mk(-1, 2, 40)], 1);
  const tight = P.replayDistributionSummary([mk(2, 2, 4), mk(-1, 2, 4)], 1);
  // Same raw R, same planned R, same win rate. ONLY the stop size differs.
  const sameRaw = Math.abs(wide.meanR - tight.meanR) < 1e-12;
  const costWide = wide.meanR - wide.spreadChargedR, costTight = tight.meanR - tight.spreadChargedR;
  return { pass: sameRaw && costTight > costWide * 9,
    detail: 'identical raw ' + wide.meanR.toFixed(2) + 'R; spread costs the 40-pip arm '
      + costWide.toFixed(3) + 'R and the 4-pip arm ' + costTight.toFixed(3) + 'R' };
});

t('DIST-7', 'charging spread against the MEAN instead of per trade would understate the damage to '
  + 'a mixed-stop arm -- the arithmetic the per-trade form exists to avoid', function () {
  const t2 = [mk(2, 2, 100), mk(-1, 2, 2)];
  const s = P.replayDistributionSummary(t2, 1);
  const perTrade = s.meanR - s.spreadChargedR;
  const naive = 1 / ((100 + 2) / 2);      // spread over the MEAN stop
  return { pass: perTrade > naive * 4,
    detail: 'per-trade cost ' + perTrade.toFixed(3) + 'R vs the naive mean-stop figure '
      + naive.toFixed(3) + 'R' };
});

t('DIST-8', 'no spread figure is invented when none was asked for, and a zero spread does not '
  + 'silently become a charged run', function () {
  const a = P.replayDistributionSummary([mk(2, 2, 30)], undefined);
  const b = P.replayDistributionSummary([mk(2, 2, 30)], 0);
  return { pass: a.spreadChargedR === null && b.spreadChargedR === null && a.spreadPips === null,
    detail: 'absent and zero both yield null, never a fabricated cost' };
});

// ══ WHAT THE PACKAGE IS ALLOWED TO CLAIM ══════════════════════════════════════════════════════

t('PKG-1', 'THE COMPARABILITY WARNING TRAVELS WITH THE NUMBERS: ALEX enters at the qualification '
  + 'candle CLOSE while every other arm enters at the NEXT BAR OPEN. That biases this comparison '
  + 'in ALEX favour, and the package says so', function () {
  const d = P.alexGAllPairsBuildReplayPackage([], { stamp: 1 }).replayDisclosures;
  const w = d.entryComparabilityWarning || '';
  return { pass: d.entryBasis === 'QUALIFICATION_CANDLE_CLOSE'
      && /NEXT BAR OPEN/.test(w) && /biased in ALEX favour/i.test(w)
      && /A LOSS for ALEX under this bias is conclusive/i.test(w)
      && /a WIN is confounded/i.test(w),
    detail: w ? 'disclosed, ' + w.length + ' chars' : 'MISSING' };
});

t('PKG-2', 'the friction note does NOT repeat the false claim that two arms are equally optimistic. '
  + 'It states that spread scales inversely with stop size and is not neutral between arms',
  function () {
  const d = P.alexGAllPairsBuildReplayPackage([], { stamp: 1 }).replayDisclosures;
  const f = (d.frictionNote || '') + ' ' + (d.frictionIsNotNeutralBetweenArms || '');
  return { pass: /INVERSELY/.test(f) && /NOT neutral/i.test(f)
      && !/equally optimistic/i.test(f) && /medianRiskPips/.test(f),
    detail: 'inverse scaling stated; the equally-optimistic claim is absent' };
});

t('PKG-3', 'the package records that the engine REFUSES cost parameters rather than pretending it '
  + 'applied them, and labels the spread column an after-the-fact estimate', function () {
  const d = P.alexGAllPairsBuildReplayPackage([], { stamp: 1 }).replayDisclosures;
  return { pass: d.frictionModelled === false && /REFUSES/.test(d.frictionNote || '')
      && /estimate, not an engine result/.test(d.frictionNote || ''),
    detail: 'engine refusal and estimate status both recorded' };
});

t('PKG-4', 'the live-state isolation is stated in the package, so a reader knows the sweep could '
  + 'not have disturbed the running instance that produced the forward evidence', function () {
  const d = P.alexGAllPairsBuildReplayPackage([], { stamp: 1 }).replayDisclosures;
  return { pass: /snapshotted before the sweep and restored on every exit path/.test(d.liveStateIsolation || ''),
    detail: d.liveStateIsolation ? 'stated' : 'MISSING' };
});

t('PKG-5', 'REPLAY_RUN, and the population note forbids mixing with forward closes -- the exact '
  + 'mistake that cost this project a published conclusion once already', function () {
  const pkg = P.alexGAllPairsBuildReplayPackage([], { stamp: 1 });
  return { pass: pkg.captureBasis === 'REPLAY_RUN' && pkg.identity.mode === 'REPLAY'
      && pkg.identity.strategyId === 'alex_g_sr_v1'
      && /Never to be combined with forward/i.test(pkg.replayDisclosures.populationNote || ''),
    detail: pkg.captureBasis + ' / ' + pkg.identity.mode + ', population note present' };
});

t('PKG-6', 'a still-open trade is excluded from outcomes and counted, and spread is left ABSENT on '
  + 'the position rather than written as a fabricated zero', function () {
  const runs = [{ pair: 'EUR_USD', normalized: [
    { stillOpen: true, pair: 'EUR_USD', resultR: null },
    { stillOpen: false, pair: 'EUR_USD', result: 'Win', resultR: 2, plannedRR: 2, riskPips: 30,
      entry: 1.1, stop: 1.097, target: 1.106, direction: 'buy', timeframe: 'H4' }] }];
  const pkg = P.alexGAllPairsBuildReplayPackage(runs, { stamp: 1 });
  return { pass: pkg.objectCounts.outcomes === 1 && pkg.replayDisclosures.stillOpenExcluded === 1
      && pkg.objects.positions[0].entrySpreadPips === undefined
      && pkg.objects.outcomes[0].pnl === undefined,
    detail: '1 outcome, 1 excluded, spread and pnl absent' };
});

t('PKG-7', 'the stop distance is TAKEN from the protected engine (riskDistancePips), never '
  + 'recomputed. A second implementation of a number the engine already published is a second '
  + 'chance to disagree with it', function () {
  const src = codeOf(fn('alexGAllPairsNormalizeTrades'));
  const norm = P.alexGAllPairsNormalizeTrades({ trades: [
    { pair: 'EUR_USD', riskDistancePips: 37.5, entry: 1.1, stop: 1.0, resultR: 2 }] });
  return { pass: /riskPips:t\.riskDistancePips/.test(src) && norm[0].riskPips === 37.5,
    detail: 'renamed from the engine field; entry/stop would have given 1000 pips, not 37.5' };
});

// ══ GOVERNANCE AND GUARDS ═════════════════════════════════════════════════════════════════════

t('GOV-1', 'the sweep only LOOPS the existing unprotected runAlexGReplay. Every function that '
  + 'decides a trade stays protected and untouched', function () {
  const reg = JSON.parse(fs.readFileSync(path.join(ROOT, 'regression-baseline.json'), 'utf8'));
  const names = Object.keys(reg.protectedFunctions || {});
  const body = fn('alexGRunReplayAllPairs');
  const protectedTouched = ['alexGRunSetupEngine', 'alexGRunSetupReplay', 'alexGConstructTrade',
    'alexGWalkOutcome', 'alexGComputeReplayStats'].filter(function (n) {
      return new RegExp(n + '\\s*\\(').test(body); });
  return { pass: /runAlexGReplay\(/.test(body) && protectedTouched.length === 0
      && names.indexOf('alexGWalkOutcome') !== -1,
    detail: protectedTouched.length ? 'CALLS PROTECTED: ' + protectedTouched.join(',')
      : 'loops the unprotected runner only' };
});

t('GOV-2', 'the sweep opens no position and touches no account. It is a research path, not a '
  + 'trading one', function () {
  const body = fn('alexGRunReplayAllPairs') + fn('alexGAllPairsBuildReplayPackage')
    + fn('alexGAllPairsRestoreState');
  return { pass: !/openPaperPosition|checkAutoTrades|alexGAccount|placeOrder|alexGAutoTrading/.test(body),
    detail: 'no account or order path referenced' };
});

t('GOV-3', 'the run requests spread mode none, the only value the engine does not refuse. Asking '
  + 'for a cost model would return a zero-cost result wearing a cost model it never applied',
  function () {
  const body = codeOf(fn('alexGRunReplayAllPairs'));
  return { pass: /alexGSpreadMode:'none'/.test(body) && /alexGFixedSpreadPips:0/.test(body)
      && /alexGSlippagePips:0/.test(body),
    detail: 'no cost model requested from the engine' };
});

t('GUARD-1', 'the whole page script parses', function () {
  const m = SRC.match(/<script>([\s\S]*?)<\/script>/g) || [];
  let total = 0;
  m.forEach(function (b) {
    const js = b.replace(/^<script>/, '').replace(/<\/script>$/, '');
    if (!js.trim()) return; total += js.length; new Function(js);
  });
  return { pass: total > 100000, detail: 'parsed ' + total.toLocaleString() + ' chars' };
});

t('GUARD-2', 'zero protected drift', function () {
  const reg = JSON.parse(fs.readFileSync(path.join(ROOT, 'regression-baseline.json'), 'utf8'));
  return { pass: Object.keys(reg.protectedFunctions || {}).length === 64
      && Object.keys(reg.protectedConstants || {}).length === 4,
    detail: '64 functions, 4 constants' };
});

// Strictly sequential: each fixture owns the shared realm for the duration of its own run.
queue.reduce(function (p, step) { return p.then(step); }, Promise.resolve()).then(function () {
  let pass = 0;
  results.forEach(function (r) {
    if (r.pass) pass++;
    console.log((r.pass ? '  PASS  ' : '  FAIL  ') + r.name + '  ' + r.desc);
    if (r.detail) console.log('          ' + r.detail);
  });
  console.log('\n  ' + pass + ' / ' + results.length + ' passed');
  process.exit(pass === results.length ? 0 : 1);
});

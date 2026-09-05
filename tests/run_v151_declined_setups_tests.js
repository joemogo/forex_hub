#!/usr/bin/env node
'use strict';
// ══════════════════════════════════════════════════════════════════════════════════════════════
// v12.51.0 — THE SETUPS MOGO DECLINED
// ══════════════════════════════════════════════════════════════════════════════════════════════
//
// MOGO recorded what it DID and nothing about what it DECLINED. Rejections were emitted as
// decision events into decisionEventLog -- an in-memory array, capped, never written to storage
// while 26 other keys are persisted -- and all 46 preserved forward packages carry zero decisions
// and zero candidates. Every declined setup died on the next page reload.
//
// DECL-1 and DECL-2 prove that from the source rather than asserting it, and they are the fixtures
// that would catch someone "helpfully" reverting the persistence later.
//
// The property this feature must never violate: a declined setup HAS NO OUTCOME. It was never
// traded. DECL-9 and DECL-10 exist because the single worst thing this could do is grow a win rate
// -- and the second worst is silently drop rows at its cap without saying so.
//
// Recording also must not be able to touch trading. DECL-11/12 pin that it runs after the
// protected constructor has already returned, and that it swallows its own failures.
//
// Run:  node tests/run_v151_declined_setups_tests.js

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

function realm(cap) {
  const c = { console: console, Math: Math, JSON: JSON, isFinite: isFinite, Array: Array,
    Number: Number, Object: Object, String: String, Date: Date, isNaN: isNaN, APP_VERSION: 'test' };
  vm.createContext(c);
  vm.runInContext('const ALEXG_DECLINED_MAX=' + (cap || 500) + ';', c);
  vm.runInContext('let alexGDeclinedSetups=[];', c);
  ['alexGDeclinedProjection', 'alexGRecordDeclinedSetup', 'alexGDeclinedSetupsSummary']
    .forEach(function (n) { vm.runInContext(fn(n), c); });
  return c;
}
function setup(over) {
  const s = { setupId: 'AGS|EUR_USD|H1|z1|B_breakRetest|r7', pair: 'EUR_USD', timeframe: 'H1',
    setupType: 'B_breakRetest', qualificationTimestamp: 1755600000000, qualificationClose: 1.1,
    zoneId: 'z1', zoneLow: 1.09, zoneHigh: 1.095 };
  if (over) Object.keys(over).forEach(function (k) { s[k] = over[k]; });
  return s;
}

const results = [];
function t(name, desc, f) {
  let pass = false, detail = '';
  try { const r = f(); pass = !!(r && r.pass); detail = (r && r.detail) || ''; }
  catch (e) { pass = false; detail = 'threw: ' + (e && e.message ? e.message : String(e)); }
  results.push({ name, desc, pass, detail });
}

// ══ THE DEFECT WAS REAL ══════════════════════════════════════════════════════════════════════

t('DECL-1', 'the decision-event log is still in-memory and capped -- this feature does not replace '
  + 'it, and a fixture that assumed it had become durable would be testing the wrong thing', function () {
  return { pass: /let decisionEventLog=\[\];/.test(SRC) && /const DECISION_EVENT_MAX_LOG_SIZE=\d+;/.test(SRC)
      && !/persistStorageKey\('fxhub_decision/.test(SRC),
    detail: 'decisionEventLog remains in-memory and capped' };
});

t('DECL-2', 'declined setups ARE now persisted and reloaded, using the same key mechanism as every '
  + 'other durable ALEX store. This is the fixture that catches a revert', function () {
  return { pass: /persistStorageKey\('fxhub_alexg_declined',JSON\.stringify\(alexGDeclinedSetups\)\)/.test(SRC)
      && /loadStoredKey\('fxhub_alexg_declined'/.test(SRC),
    detail: 'saved and loaded under fxhub_alexg_declined' };
});

t('DECL-3', 'the reload is defensive: a corrupt or non-array stored value leaves the in-memory list '
  + 'intact rather than replacing it with garbage', function () {
  // Matched to the end of the LINE, not to the first ";" -- the handler contains two statements,
  // so a [^;]+ capture stopped at "JSON.parse(v)" and never saw the guard that follows it.
  const i = SRC.indexOf("loadStoredKey('fxhub_alexg_declined'");
  const line = i < 0 ? '' : SRC.slice(i, SRC.indexOf('\n', i));
  return { pass: i >= 0 && /Array\.isArray\(a\)/.test(line) && /alexGDeclinedSetups=a/.test(line),
    detail: i < 0 ? 'load line not found' : 'guarded: ' + line.trim().slice(0, 96) };
});

// ══ WHAT IS RECORDED ═════════════════════════════════════════════════════════════════════════

t('DECL-4', 'the projection carries the identity a later replay needs to find the same setup again '
  + '-- the pair AND the qualification bar, not just a count', function () {
  const c = realm();
  const p = vm.runInContext('alexGDeclinedProjection(' + JSON.stringify(setup())
    + ',{status:"BLOCKED — ENTRY MOVED",reason:"ENTRY_MOVED_TOO_FAR_FROM_SIGNAL",direction:"buy"},"sig1","scan1")', c);
  return { pass: p.setupId === setup().setupId && p.pair === 'EUR_USD'
      && p.qualificationTimestamp === 1755600000000 && p.qualificationClose === 1.1
      && p.timeframe === 'H1' && p.zoneLow === 1.09 && p.zoneHigh === 1.095,
    detail: 'setupId, pair, timeframe, qualification bar and zone bounds all carried' };
});

t('DECL-5', 'the engine\'s own status and reason are recorded VERBATIM, never re-derived or '
  + 'softened -- the reason a trade did not happen is exactly as the engine stated it', function () {
  const c = realm();
  const p = vm.runInContext('alexGDeclinedProjection(' + JSON.stringify(setup())
    + ',{status:"BLOCKED — ENTRY MOVED",reason:"ENTRY_MOVED_TOO_FAR_FROM_SIGNAL",direction:"buy"},"s","x")', c);
  const body = fn('alexGDeclinedProjection');
  return { pass: p.status === 'BLOCKED — ENTRY MOVED' && p.reason === 'ENTRY_MOVED_TOO_FAR_FROM_SIGNAL'
      && !/REASON_MAP|friendly|label/i.test(body),
    detail: p.reason };
});

t('DECL-6', 'a setup declined AGAIN for the same reason is the same fact, not a new one -- without '
  + 'this every poll would re-record it and the counts would measure poll frequency', function () {
  const c = realm();
  const s = JSON.stringify(setup());
  const r = '{status:"BLOCKED — ENTRY MOVED",reason:"ENTRY_MOVED_TOO_FAR_FROM_SIGNAL",direction:"buy"}';
  vm.runInContext('alexGRecordDeclinedSetup(' + s + ',' + r + ',"sig","a")', c);
  vm.runInContext('alexGRecordDeclinedSetup(' + s + ',' + r + ',"sig","b")', c);
  vm.runInContext('alexGRecordDeclinedSetup(' + s + ',' + r + ',"sig","c")', c);
  return { pass: vm.runInContext('alexGDeclinedSetups.length', c) === 1,
    detail: '3 identical declines -> 1 row' };
});

t('DECL-7', 'the SAME setup declined for a DIFFERENT reason IS a new fact and is kept', function () {
  const c = realm();
  const s = JSON.stringify(setup());
  vm.runInContext('alexGRecordDeclinedSetup(' + s + ',{status:"a",reason:"ENTRY_MOVED_TOO_FAR_FROM_SIGNAL"},"g","x")', c);
  vm.runInContext('alexGRecordDeclinedSetup(' + s + ',{status:"b",reason:"EXISTING_OPEN_TRADE_SAME_PAIR_TIMEFRAME"},"g","x")', c);
  return { pass: vm.runInContext('alexGDeclinedSetups.length', c) === 2,
    detail: 'two distinct reasons -> 2 rows' };
});

t('DECL-8', 'a setup with no id is not recorded, and a malformed one does not throw -- recording '
  + 'runs inside the trading tick and must never be able to break it', function () {
  const c = realm();
  const r = '{status:"x",reason:"y"}';
  vm.runInContext('alexGRecordDeclinedSetup(null,' + r + ',"s","x")', c);
  vm.runInContext('alexGRecordDeclinedSetup({},' + r + ',"s","x")', c);
  vm.runInContext('alexGRecordDeclinedSetup(undefined,undefined,undefined,undefined)', c);
  vm.runInContext('alexGRecordDeclinedSetup({setupId:null,pair:"X"},' + r + ',"s","x")', c);
  return { pass: vm.runInContext('alexGDeclinedSetups.length', c) === 0,
    detail: 'four malformed calls recorded nothing and threw nothing' };
});

// ══ THE PROPERTY THAT MUST NEVER BREAK ═══════════════════════════════════════════════════════

t('DECL-9', 'the summary reports NO outcome of any kind. A declined setup was never traded, so a '
  + 'win rate, expectancy or R figure here would be invented -- the worst thing this could do', function () {
  const c = realm();
  const s = JSON.stringify(setup());
  vm.runInContext('alexGRecordDeclinedSetup(' + s + ',{status:"a",reason:"ENTRY_MOVED_TOO_FAR_FROM_SIGNAL"},"g","x")', c);
  const sum = vm.runInContext('alexGDeclinedSetupsSummary()', c);
  const keys = Object.keys(sum);
  const forbidden = keys.filter(function (k) { return /win|loss|expectancy|netR|pnl|result/i.test(k); });
  const body = fn('alexGDeclinedSetupsSummary');
  return { pass: forbidden.length === 0 && sum.outcomesKnown === false
      && !/realizedR|resultR|winRate/.test(body),
    detail: 'keys: ' + keys.join(', ') };
});

t('DECL-10', 'the cap drops the OLDEST and SAYS SO. A table silently losing rows would understate '
  + 'exactly the population it exists to measure', function () {
  const c = realm(3);
  for (let i = 0; i < 6; i++) {
    vm.runInContext('alexGRecordDeclinedSetup({setupId:"S' + i + '",pair:"P"},'
      + '{status:"a",reason:"R' + i + '"},"g' + i + '","x")', c);
  }
  const list = vm.runInContext('alexGDeclinedSetups.map(function(d){return d.setupId;})', c);
  const sum = vm.runInContext('alexGDeclinedSetupsSummary()', c);
  return { pass: list.length === 3 && list[0] === 'S3' && list[2] === 'S5'
      && sum.atCap === true && sum.cap === 3,
    detail: 'kept ' + list.join(',') + '; atCap=' + sum.atCap };
});

t('DECL-11', 'the panel states that no outcome is known, and that the question is answerable by '
  + 'replay -- otherwise a reader fills the gap with an assumption', function () {
  const r = fn('obsRenderDeclined');
  return { pass: /No outcome is shown, because none is known/.test(r)
      && /never traded/.test(r) && /inventing one/.test(r)
      && /replaying the same period/.test(r),
    detail: 'absence of outcome stated, and the route to one given' };
});

t('DECL-12', 'the panel says WHY this matters -- replay takes every qualifying setup and live does '
  + 'not, which is the untested explanation for the two disagreeing', function () {
  const r = fn('obsRenderDeclined');
  return { pass: /replay takes every qualifying setup and live does not/.test(r)
      && /could not be asked at all/.test(r),
    detail: 'the selection hypothesis is stated as the reason to look' };
});

// ══ RECORDING CANNOT TOUCH TRADING ═══════════════════════════════════════════════════════════

t('DECL-13', 'recording happens AFTER the protected constructor has already returned its verdict, '
  + 'inside the existing failure branch -- it cannot alter, delay or repeat a decision', function () {
  const attempt = fn('alexGAttemptOpenLivePosition');
  const iResult = attempt.indexOf('const result=');
  const iBranch = attempt.indexOf("if(result.status!=='TRADE OPENED')");
  const iRecord = attempt.indexOf('alexGRecordDeclinedSetup');
  return { pass: iResult >= 0 && iBranch > iResult && iRecord > iBranch,
    detail: 'construct at ' + iResult + ', failure branch at ' + iBranch + ', record at ' + iRecord };
});

t('DECL-14', 'recording swallows its own failures and returns, so a storage or serialisation fault '
  + 'can never propagate into the trading tick', function () {
  const body = fn('alexGRecordDeclinedSetup');
  return { pass: /try\{/.test(body) && /catch\(e\)\{ return null; \}/.test(body),
    detail: 'wrapped, returns null on any failure' };
});

t('DECL-15', 'nothing in this feature writes to an account, a position or the setup state', function () {
  const bodies = ['alexGDeclinedProjection', 'alexGRecordDeclinedSetup', 'alexGDeclinedSetupsSummary',
    'obsRenderDeclined'].map(fn).join('\n');
  const forbidden = /alexGAccount\s*=|\.openPositions|\.closedPositions|alexGSetupState\s*=|alexGAutoTrading\./;
  return { pass: !forbidden.test(bodies), detail: 'no account, position or setup-state writes' };
});

results.forEach(function (r) {
  console.log((r.pass ? 'PASS' : 'FAIL') + ' -- ' + r.name + ': ' + r.desc + (r.detail ? '  [' + r.detail + ']' : ''));
});
const fails = results.filter(function (r) { return !r.pass; }).length;
console.log('---');
console.log(results.length + ' fixtures, ' + (results.length - fails) + ' PASS, ' + fails + ' FAIL');
process.exitCode = fails ? 1 : 0;

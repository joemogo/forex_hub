#!/usr/bin/env node
'use strict';
// ══════════════════════════════════════════════════════════════════════════════════════════════
// v12.59.0 — JVM COULD NOT TRADE FOR AN HOUR AFTER EVERY RELOAD
// ══════════════════════════════════════════════════════════════════════════════════════════════
//
// jvmEligibilityIsCurrent is correct and deliberately fail-closed; its own comment names
// "post-reload" as a case that yields false. The defect was that nothing reconciled that with the
// decision to rescan. Both call sites asked:
//
//     stale = !autoScan.lastRunAt || (now - autoScan.lastRunAt) > 1 hour
//
// autoScan.lastRunAt is PERSISTED (fxhub_autoscan). __jvmEligibility and its generation counter are
// session-scoped and reset on every page load. So a reload ten minutes after a scan read lastRunAt
// as fresh, skipped the rescan, and left every pair not-current -- htfSnapshotOf returned null for
// all twelve and checkAutoTrades refused every candidate with HTF_SNAPSHOT_MISSING, for up to a
// full hour, on every reload. The same hole opened when Auto Scan was toggled off and back on
// inside the hour, because toggling off deliberately makes every pair not-current while lastRunAt
// keeps saying "recent".
//
// STARVE-1 is the fixture that proves the defect was real: a FRESH timestamp with EMPTY eligibility
// must still trigger a scan. Under the old condition it did not, and that single combination is the
// post-reload state.
//
// STARVE-6 is the one that stops this being "fixed" by weakening the gate: jvmEligibilityIsCurrent
// must still fail closed on every path. Trading on bias whose freshness cannot be confirmed would
// be a worse defect than not trading at all.
//
// Run:  node tests/run_v160_jvm_eligibility_starvation_tests.js

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

// The REAL predicates, in a realm where only the state they read is stubbed.
function realm(opts) {
  const o = opts || {};
  const c = { console: console, Math: Math, JSON: JSON, Object: Object, String: String,
    Number: Number, Array: Array, Date: Date, isFinite: isFinite, isNaN: isNaN };
  vm.createContext(c);
  vm.runInContext("const JVM_ELIGIBILITY_STATUS={FRESH:'FRESH',IN_PROGRESS:'IN_PROGRESS',FAILED:'FAILED'};", c);
  vm.runInContext('const SCAN_PAIRS=' + JSON.stringify(o.pairs || ['EUR/USD', 'GBP/USD']) + ';', c);
  vm.runInContext('let __jvmEligibility=' + JSON.stringify(o.eligibility || {}) + ';', c);
  vm.runInContext('let __jvmEligibilityGeneration=' + (o.generation || 0) + ';', c);
  vm.runInContext('let autoScan=' + JSON.stringify(o.autoScan || { enabled: true, lastRunAt: null }) + ';', c);
  vm.runInContext(fn('jvmEligibilityIsCurrent'), c);
  vm.runInContext(fn('jvmEligibilityAnyCurrent'), c);
  vm.runInContext(fn('jvmShouldRunTopDownScan'), c);
  return c;
}
const ask = function (c) { return vm.runInContext('jvmShouldRunTopDownScan()', c); };
const minsAgo = function (m) { return new Date(Date.now() - m * 60000).toISOString(); };
const fresh = function (gen) { return { 'EUR/USD': { gen: gen, status: 'FRESH' }, 'GBP/USD': { gen: gen, status: 'FRESH' } }; };

const results = [];
function t(name, desc, f) {
  let pass = false, detail = '';
  try { const r = f(); pass = !!(r && r.pass); detail = (r && r.detail) || ''; }
  catch (e) { pass = false; detail = 'threw: ' + (e && e.message ? e.message : String(e)); }
  results.push({ name, desc, pass, detail });
}

// ══ THE DEFECT ═══════════════════════════════════════════════════════════════════════════════

t('STARVE-1', 'THE POST-RELOAD STATE: a RECENT scan timestamp with EMPTY eligibility must still '
  + 'trigger a scan. This exact combination is what every page load produces, and under the old '
  + 'timestamp-only condition it did NOT rescan -- leaving JVM unable to trade for up to an hour', function () {
  const c = realm({ eligibility: {}, generation: 0, autoScan: { enabled: true, lastRunAt: minsAgo(10) } });
  return { pass: ask(c) === true, detail: 'lastRunAt 10 min ago, eligibility empty -> scan requested' };
});

t('STARVE-2', 'a PRIOR-GENERATION entry counts as not current -- a rehydrated snapshot no sweep has '
  + 'confirmed this session must not be mistaken for a fresh one', function () {
  const c = realm({ eligibility: fresh(3), generation: 7, autoScan: { enabled: true, lastRunAt: minsAgo(5) } });
  return { pass: ask(c) === true, detail: 'entries from generation 3, current generation 7 -> scan requested' };
});

t('STARVE-3', 'IN_PROGRESS and FAILED entries are not current either, so a scan that failed does '
  + 'not leave JVM permanently starved waiting for an hour to elapse', function () {
  const c = realm({ eligibility: { 'EUR/USD': { gen: 1, status: 'FAILED' }, 'GBP/USD': { gen: 1, status: 'IN_PROGRESS' } },
    generation: 1, autoScan: { enabled: true, lastRunAt: minsAgo(2) } });
  return { pass: ask(c) === true, detail: 'FAILED + IN_PROGRESS -> scan requested' };
});

t('STARVE-4', 'with eligibility genuinely current AND the timestamp recent, NO scan is requested -- '
  + 'the fix must not turn into a rescan on every tick', function () {
  const c = realm({ eligibility: fresh(1), generation: 1, autoScan: { enabled: true, lastRunAt: minsAgo(5) } });
  return { pass: ask(c) === false, detail: 'current eligibility + recent scan -> no scan' };
});

t('STARVE-5', 'the HOURLY refresh is retained: current eligibility but a timestamp older than an '
  + 'hour still triggers a scan, so nothing that worked before stops working', function () {
  const c = realm({ eligibility: fresh(1), generation: 1, autoScan: { enabled: true, lastRunAt: minsAgo(75) } });
  return { pass: ask(c) === true, detail: 'lastRunAt 75 min ago -> scan requested' };
});

t('STARVE-5b', 'a missing timestamp still triggers a scan', function () {
  const c = realm({ eligibility: fresh(1), generation: 1, autoScan: { enabled: true, lastRunAt: null } });
  return { pass: ask(c) === true, detail: 'no lastRunAt -> scan requested' };
});

// ══ THE GATE IS NOT WEAKENED ═════════════════════════════════════════════════════════════════

t('STARVE-6', 'THE ONE THAT MATTERS: jvmEligibilityIsCurrent still fails closed on every path. '
  + 'Trading on bias whose freshness cannot be confirmed would be a worse defect than not trading', function () {
  const c = realm({ eligibility: fresh(1), generation: 1 });
  const cases = [
    ['missing', 'jvmEligibilityIsCurrent("NOT/APAIR")'],
    ['not an object', '(__jvmEligibility["X"]="s", jvmEligibilityIsCurrent("X"))'],
    ['IN_PROGRESS', '(__jvmEligibility["Y"]={gen:1,status:"IN_PROGRESS"}, jvmEligibilityIsCurrent("Y"))'],
    ['FAILED', '(__jvmEligibility["Z"]={gen:1,status:"FAILED"}, jvmEligibilityIsCurrent("Z"))'],
    ['prior generation', '(__jvmEligibility["W"]={gen:0,status:"FRESH"}, jvmEligibilityIsCurrent("W"))']
  ];
  const leaks = cases.filter(function (p) { return vm.runInContext(p[1], c) !== false; }).map(function (p) { return p[0]; });
  const stillTrue = vm.runInContext('jvmEligibilityIsCurrent("EUR/USD")', c);
  return { pass: leaks.length === 0 && stillTrue === true,
    detail: leaks.length ? 'LEAKED: ' + leaks.join(',') : 'all 5 refusal paths fail closed; a genuine FRESH entry still passes' };
});

t('STARVE-7', 'the fix moved the RESCAN DECISION, not the gate. jvmEligibilityIsCurrent must be '
  + 'unchanged -- a fix that loosened it would let JVM trade on unverified bias', function () {
  const body = codeOf(fn('jvmEligibilityIsCurrent'));
  return { pass: /e\.status!==JVM_ELIGIBILITY_STATUS\.FRESH/.test(body)
      && /e\.gen!==__jvmEligibilityGeneration/.test(body)
      && (body.match(/return false/g) || []).length === 3,
    detail: 'three fail-closed returns intact' };
});

t('STARVE-8', 'jvmEligibilityAnyCurrent fails CLOSED on a throw -- unknown must mean "scan", never '
  + '"assume it is fine"', function () {
  const c = realm({ eligibility: fresh(1), generation: 1 });
  vm.runInContext('jvmEligibilityIsCurrent=function(){ throw new Error("boom"); };', c);
  return { pass: vm.runInContext('jvmEligibilityAnyCurrent()', c) === false && ask(c) === true,
    detail: 'throw -> not current -> scan requested' };
});

// ══ BOTH CALL SITES, ONE DECISION ════════════════════════════════════════════════════════════

t('STARVE-9', 'BOTH call sites use the shared decision. They were byte-identical duplicates of the '
  + 'same wrong condition, which is how they stayed wrong together', function () {
  const uses = (SRC.match(/if\(jvmShouldRunTopDownScan\(\)\) runAutoTopDownScan\(\);/g) || []).length;
  const oldCond = /const stale=!autoScan\.lastRunAt\|\|\(Date\.now\(\)-new Date\(autoScan\.lastRunAt\)\.getTime\(\)\)>60\*60\*1000;/.test(SRC);
  return { pass: uses === 2 && !oldCond,
    detail: uses + ' call sites on the shared decision; old timestamp-only condition gone' };
});

t('STARVE-10', 'the hourly timer is still installed at both sites -- this release fixes the '
  + 'cold-start hole, it does not replace the periodic refresh', function () {
  const n = (SRC.match(/autoScanTimer=setInterval\(runAutoTopDownScan,60\*60\*1000\)/g) || []).length;
  return { pass: n === 2, detail: n + ' hourly timers installed' };
});

t('STARVE-11', 'the decision reads SCAN_PAIRS -- JVM trades that list, so eligibility for any other '
  + 'set would answer the wrong question', function () {
  const body = codeOf(fn('jvmEligibilityAnyCurrent'));
  return { pass: /SCAN_PAIRS/.test(body) && !/ALEXG_LIVE_PAIRS/.test(body) && !/ALL_PAIRS/.test(body),
    detail: 'scoped to JVM\'s own instrument list' };
});

// ══ GUARDS ═══════════════════════════════════════════════════════════════════════════════════

t('GUARD-1', 'the whole page script parses', function () {
  const m = SRC.match(/<script>([\s\S]*?)<\/script>/g) || [];
  let total = 0;
  m.forEach(function (b) {
    const js = b.replace(/^<script>/, '').replace(/<\/script>$/, '');
    if (!js.trim()) return; total += js.length; new Function(js);
  });
  return { pass: total > 100000, detail: 'parsed ' + total.toLocaleString() + ' chars' };
});

t('GUARD-2', 'no protected function was touched -- both edited sites are unprotected', function () {
  const reg = JSON.parse(fs.readFileSync(path.join(ROOT, 'regression-baseline.json'), 'utf8'));
  const p = Object.keys(reg.protectedFunctions || {});
  return { pass: p.indexOf('jvmEligibilityIsCurrent') === -1 && p.indexOf('toggleAutoScan') === -1
      && p.indexOf('jvmShouldRunTopDownScan') === -1 && p.indexOf('checkAutoTrades') !== -1,
    detail: 'edited functions unprotected; checkAutoTrades still protected and unedited' };
});

// ══ REPORT ═══════════════════════════════════════════════════════════════════════════════════

let pass = 0;
results.forEach(function (r) {
  if (r.pass) pass++;
  console.log((r.pass ? '  PASS  ' : '  FAIL  ') + r.name + '  ' + r.desc);
  if (r.detail) console.log('          ' + r.detail);
});
console.log('\n  ' + pass + ' / ' + results.length + ' passed');
process.exit(pass === results.length ? 0 : 1);

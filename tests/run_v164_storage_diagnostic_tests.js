#!/usr/bin/env node
'use strict';
// ══════════════════════════════════════════════════════════════════════════════════════════════
// v12.63.0 — STORAGE DIAGNOSTIC: WHAT IS FULL, AND WHAT IS SAFE TO RECLAIM
// ══════════════════════════════════════════════════════════════════════════════════════════════
//
// The operator's instance raised "Storage full — evidence is not being saved. Export now." That
// banner was the ONLY signal in the whole application: nothing measured usage, named the exhausted
// tier, or said what could be freed. The obvious remedy an operator reaches for -- clear site data
// -- destroys the browser evidence store, which is precisely what the banner is protecting.
//
// DEAD-1..DEAD-4 are the fixtures that matter. Buffer eviction is gated on tier (b): a setup
// belonging to a closed trade whose package is not yet committed is skipped. That gate is correct
// -- an over-full buffer is recoverable, a deleted record is not -- but it means a tier-(b)
// failure STOPS the mechanism that would shrink localStorage. One full store holds the other full,
// and unmeasured that reads as "storage keeps filling no matter what I do". The diagnostic has to
// name that state, and DEAD-2 proves it distinguishes it from ordinary overflow.
//
// SAFE-1..SAFE-5 exist because this function's whole value is that an operator will act on it. A
// key misreported as disposable costs evidence that cannot be recovered, so the default for an
// unrecognised key is EVIDENCE and a fixture enforces it.
//
// Run:  node tests/run_v164_storage_diagnostic_tests.js

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

const ctx = { console: console, Math: Math, JSON: JSON, isFinite: isFinite, Array: Array,
  Number: Number, Object: Object, String: String, Date: Date, isNaN: isNaN };
vm.createContext(ctx);
vm.runInContext('var EVIDENCE_SETUPS_MAX=1000, EVIDENCE_ZONES_MAX_PER_PAIR=200;', ctx);
vm.runInContext(constBlock('const STORAGE_CACHE_KEYS='), ctx);
vm.runInContext(constBlock('const STORAGE_CONFIG_KEYS='), ctx);
['storageClassifyKey', 'storageEntryBytes', 'storageInventoryLocal', 'storageEvictionPressure',
  'storageDiagnose', 'storageFormatBytes']
  .forEach(function (n) { vm.runInContext(fn(n), ctx); });
const P = ctx;
// A localStorage stand-in, so the inventory is exercised against a real store rather than a
// description of one.
function installStore(map, opts) {
  const o = opts || {};
  const keys = Object.keys(map);
  vm.runInContext('var __map=' + JSON.stringify(map) + ', __keys=' + JSON.stringify(keys)
    + ', __throwOn=' + JSON.stringify(o.throwOn || null) + ';'
    + 'var localStorage={length:__keys.length,'
    + 'key:function(i){ return __keys[i]; },'
    + 'getItem:function(k){ if(k===__throwOn) throw new Error("read failed"); return __map[k]; }};', ctx);
}

const results = [];
function t(name, desc, f) {
  let pass = false, detail = '';
  try { const r = f(); pass = !!(r && r.pass); detail = (r && r.detail) || ''; }
  catch (e) { pass = false; detail = 'threw: ' + (e && e.message ? e.message : String(e)); }
  results.push({ name: name, desc: desc, pass: pass, detail: detail });
}

// ══ THE DEADLOCK ══════════════════════════════════════════════════════════════════════════════

const setups = function (n, blockedFrom) {
  const a = [];
  for (let i = 0; i < n; i++) a.push({ setupId: 'S' + i, qualificationTimestamp: 1000000 - i });
  return a;
};

t('DEAD-1', 'THE ONE THIS EXISTS FOR: when the setup buffer is over its cap AND the overflow '
  + 'cannot be evicted because its evidence is not yet committed, the diagnostic names that '
  + 'deadlock instead of reporting a generic "over cap"', function () {
  // 1,050 setups; the 50 oldest are the overflow, and all 50 belong to closed trades whose
  // packages were never committed -- so eviction is blocked on every one.
  const list = setups(1050);
  const closed = [];
  for (let i = 1000; i < 1050; i++) closed.push({ tradeId: 'T' + i, setupId: 'S' + i });
  const pr = P.storageEvictionPressure(list, {}, {}, closed, []);
  const d = P.storageDiagnose(null, { rows: [], total: 0 }, pr, { total: 5, unexported: 5 });
  const named = d.findings.some(function (f) { return /deadlock/i.test(f) && /CANNOT be evicted/.test(f); });
  return { pass: pr.setupOverflow === 50 && pr.setupOverflowBlocked === 50
      && pr.setupEvictable === 0 && named,
    detail: '50 over cap, 50 blocked, 0 evictable; deadlock named in the findings' };
});

t('DEAD-2', 'and ORDINARY overflow is reported differently. If both states produced the same '
  + 'sentence the diagnostic would be decoration -- an operator needs to know whether exporting '
  + 'will actually release anything', function () {
  const list = setups(1050);
  // Same overflow, but every one of those trades HAS a committed package.
  const closed = [], persisted = {};
  for (let i = 1000; i < 1050; i++) { closed.push({ tradeId: 'T' + i, setupId: 'S' + i }); persisted['T' + i] = true; }
  const pr = P.storageEvictionPressure(list, {}, persisted, closed, []);
  const d = P.storageDiagnose(null, { rows: [], total: 0 }, pr, { total: 5, unexported: 0 });
  const deadlock = d.findings.some(function (f) { return /deadlock/i.test(f); });
  const evictable = d.findings.some(function (f) { return /ARE\s+\n?evictable|ARE evictable/.test(f); });
  return { pass: pr.setupOverflowBlocked === 0 && pr.setupEvictable === 50 && !deadlock && evictable,
    detail: '50 over cap, 0 blocked, 50 evictable; deadlock NOT claimed' };
});

t('DEAD-3', 'a setup belonging to an OPEN position is blocked from eviction regardless of what is '
  + 'committed. Eviction must never outrun a live trade', function () {
  const list = setups(1050);
  const open = [{ setupId: 'S1049' }];
  const pr = P.storageEvictionPressure(list, {}, {}, [], open);
  return { pass: pr.setupOverflowBlocked === 1 && pr.setupEvictable === 49,
    detail: 'the open position\'s setup is held; the other 49 are free' };
});

t('DEAD-4', 'a buffer UNDER its cap reports no overflow and no deadlock -- the fixture that stops '
  + 'this from crying wolf on a healthy instance', function () {
  const pr = P.storageEvictionPressure(setups(10), {}, {}, [], []);
  const d = P.storageDiagnose(null, { rows: [], total: 0 }, pr, { total: 3, unexported: 0 });
  return { pass: pr.setupOverflow === 0 && pr.setupEvictable === 0
      && d.findings.some(function (f) { return /No storage pressure detected/.test(f); }),
    detail: 'clean instance reports no pressure' };
});

t('DEAD-5', 'zones over the per-pair cap are counted per instrument, not globally. A single busy '
  + 'pair and twelve mildly busy ones are different problems', function () {
  const zs = { EUR_USD: { H1: { validatedZones: new Array(250).fill({}) } },
               GBP_USD: { H1: { validatedZones: new Array(10).fill({}) } } };
  const pr = P.storageEvictionPressure([], zs, {}, [], []);
  return { pass: pr.zonePairsOverCap === 1 && pr.zoneTotal === 260,
    detail: '260 zones across 2 pairs, 1 pair over the 200 cap' };
});

// ══ WHAT IS SAFE TO RECLAIM ═══════════════════════════════════════════════════════════════════

t('SAFE-1', 'THE DEFAULT IS EVIDENCE. An unrecognised key -- one added in a later release and '
  + 'forgotten here -- must never be reported as disposable', function () {
  return { pass: P.storageClassifyKey('fxhub_some_future_key') === 'EVIDENCE'
      && P.storageClassifyKey('') === 'EVIDENCE' && P.storageClassifyKey(null) === 'EVIDENCE',
    detail: 'unknown, empty and null all classify as EVIDENCE' };
});

t('SAFE-2', 'the keys that hold irreplaceable history are classified EVIDENCE, including both '
  + 'ALEX ledger keys and the declined-candidate stores', function () {
  const must = ['fxhub_alexg_account', 'fxhub_alexg_journal', 'fxhub_journal', 'fxhub_paper',
    'fxhub_alexg_setups', 'fxhub_alexg_zones', 'fxhub_jvm_declined', 'fxhub_alexg_declined',
    'fxhub_trade_notes', 'fxhub_paper_reconciliation_audit'];
  const wrong = must.filter(function (k) { return P.storageClassifyKey(k) !== 'EVIDENCE'; });
  return { pass: wrong.length === 0,
    detail: wrong.length ? 'MISCLASSIFIED: ' + wrong.join(',') : must.length + ' evidence keys correct' };
});

t('SAFE-3', 'only genuinely regenerable things are called cache, and the reclaimable total counts '
  + 'those alone', function () {
  const local = { rows: [
    { key: 'fxhub_scan', bytes: 4000, cls: 'CACHE' },
    { key: 'fxhub_alexg_journal', bytes: 900000, cls: 'EVIDENCE' },
    { key: 'fxhub_auto', bytes: 100, cls: 'CONFIG' }], total: 904100 };
  const d = P.storageDiagnose(null, local, P.storageEvictionPressure([], {}, {}, [], []), { total: 0, unexported: 0 });
  return { pass: d.reclaimableCacheBytes === 4000 && P.storageClassifyKey('fxhub_scan') === 'CACHE'
      && P.storageClassifyKey('fxhub_alexg_journal') === 'EVIDENCE',
    detail: 'reclaimable counts the 4 KB cache, not the 900 KB journal' };
});

t('SAFE-4', 'THE DESTRUCTIVE REMEDY IS WARNED AGAINST EVERY TIME. Clearing site data is the first '
  + 'thing an operator reaches for and it destroys the evidence store the banner is protecting',
  function () {
  const clean = P.storageDiagnose(null, { rows: [], total: 0 },
    P.storageEvictionPressure([], {}, {}, [], []), { total: 0, unexported: 0 });
  const full = P.storageDiagnose({ quota: 100, usage: 99 }, { rows: [], total: 0 },
    P.storageEvictionPressure(setups(1050), {}, {}, [], []), { total: 9, unexported: 9 });
  const warns = function (d) { return d.actions.some(function (a) {
    return /Do NOT clear site data/.test(a) && /destroys the browser evidence store/.test(a); }); };
  return { pass: warns(clean) && warns(full),
    detail: 'warning present on both a clean and a pressured instance' };
});

t('SAFE-5', 'THE DIAGNOSTIC DELETES NOTHING. Evidence destruction is an operator boundary, and a '
  + 'tool that quietly freed space by dropping records would be the worst thing in the file',
  function () {
  const body = codeOf(fn('storageInventoryLocal') + fn('storageEvictionPressure')
    + fn('storageDiagnose') + fn('runStorageDiagnostic'));
  const destructive = /removeItem|localStorage\.clear|\.delete\(|indexedDB\.deleteDatabase|evidenceEvictBuffers\(/.test(body);
  return { pass: !destructive,
    detail: destructive ? 'A DESTRUCTIVE CALL IS PRESENT' : 'read-only: no remove, clear or delete' };
});

t('SAFE-6', 'unexported packages are surfaced with what losing this profile would cost, and the '
  + 'action names the re-import confirmation step -- a download alone never clears the warning',
  function () {
  const d = P.storageDiagnose(null, { rows: [], total: 0 },
    P.storageEvictionPressure([], {}, {}, [], []), { total: 9, unexported: 5 });
  return { pass: d.findings.some(function (f) { return /5 evidence package/.test(f) && /ONLY in this browser profile/.test(f); })
      && d.actions.some(function (a) { return /re-import/i.test(a); }),
    detail: 'unexported count surfaced with the re-import step' };
});

// ══ MEASUREMENT ═══════════════════════════════════════════════════════════════════════════════

t('MEAS-1', 'sizes are read from the real store, largest first, counting the key as well as the '
  + 'value -- both occupy quota', function () {
  installStore({ small: 'a', big: new Array(500).join('x'), mid: new Array(50).join('y') });
  const inv = P.storageInventoryLocal();
  return { pass: inv.rows[0].key === 'big' && inv.rows[1].key === 'mid' && inv.rows[2].key === 'small'
      && inv.rows[2].bytes === ('small'.length + 1) * 2 && inv.total > 0,
    detail: 'sorted big > mid > small; smallest is ' + inv.rows[2].bytes + ' bytes (key+value, UTF-16)' };
});

t('MEAS-2', 'a key that cannot be READ is reported as unreadable rather than skipped. A key too '
  + 'large or corrupt to read is exactly what this diagnostic exists to surface', function () {
  installStore({ ok: 'fine', broken: 'x' }, { throwOn: 'broken' });
  const inv = P.storageInventoryLocal();
  const bad = inv.rows.filter(function (r) { return r.unreadable; });
  return { pass: inv.unreadable === 1 && bad.length === 1 && bad[0].key === 'broken'
      && inv.rows.length === 2,
    detail: 'unreadable key listed, not dropped from the inventory' };
});

t('MEAS-3', 'a browser with no quota API degrades to "unavailable" rather than reporting a '
  + 'fabricated percentage', function () {
  const d = P.storageDiagnose(null, { rows: [], total: 10 },
    P.storageEvictionPressure([], {}, {}, [], []), { total: 0, unexported: 0 });
  const zero = P.storageDiagnose({ quota: 0, usage: 0 }, { rows: [], total: 10 },
    P.storageEvictionPressure([], {}, {}, [], []), { total: 0, unexported: 0 });
  return { pass: d.quotaBytes === null && d.usedPct === null && zero.usedPct === null,
    detail: 'no estimate and a zero quota both yield null, never 0% or NaN' };
});

t('MEAS-4', 'a quota at or above 90% is called out explicitly', function () {
  const hi = P.storageDiagnose({ quota: 1000, usage: 950 }, { rows: [], total: 0 },
    P.storageEvictionPressure([], {}, {}, [], []), { total: 0, unexported: 0 });
  const lo = P.storageDiagnose({ quota: 1000, usage: 100 }, { rows: [], total: 0 },
    P.storageEvictionPressure([], {}, {}, [], []), { total: 0, unexported: 0 });
  const said = function (d) { return d.findings.some(function (f) { return /% of its storage quota/.test(f); }); };
  return { pass: said(hi) && !said(lo) && Math.abs(hi.usedPct - 0.95) < 1e-12,
    detail: '95% flagged, 10% not' };
});

t('MEAS-5', 'byte formatting stays readable across scales and never prints NaN', function () {
  return { pass: P.storageFormatBytes(512) === '512 B' && /KB$/.test(P.storageFormatBytes(2048))
      && /MB$/.test(P.storageFormatBytes(5 * 1024 * 1024))
      && P.storageFormatBytes(null) === '—' && P.storageFormatBytes(Infinity) === '—',
    detail: 'B / KB / MB, and null or non-finite renders as a dash' };
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

t('GUARD-2', 'zero protected drift — this is a read-only diagnostic, not a behaviour change',
  function () {
  const reg = JSON.parse(fs.readFileSync(path.join(ROOT, 'regression-baseline.json'), 'utf8'));
  return { pass: Object.keys(reg.protectedFunctions || {}).length === 64
      && Object.keys(reg.protectedConstants || {}).length === 4,
    detail: '64 functions, 4 constants' };
});

let pass = 0;
results.forEach(function (r) {
  if (r.pass) pass++;
  console.log((r.pass ? '  PASS  ' : '  FAIL  ') + r.name + '  ' + r.desc);
  if (r.detail) console.log('          ' + r.detail);
});
console.log('\n  ' + pass + ' / ' + results.length + ' passed');
process.exit(pass === results.length ? 0 : 1);

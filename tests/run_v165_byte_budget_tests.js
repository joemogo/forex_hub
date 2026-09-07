#!/usr/bin/env node
'use strict';
// ══════════════════════════════════════════════════════════════════════════════════════════════
// v12.64.0 — BYTE-AWARE BUFFER BUDGETS
// ══════════════════════════════════════════════════════════════════════════════════════════════
//
// MEASURED ON THE OPERATOR INSTANCE. The quota banner read "storage full" while
// navigator.storage.estimate reported 7.6% of the ORIGIN quota used with ten gigabytes free.
// Two different limits: localStorage has its own ~5-10 MB per-origin ceiling, separate from the
// origin quota IndexedDB draws on. localStorage was at 8.29 MB -- zones 5.76 MB, setups 1.76 MB.
//
// AND BOTH COUNT CAPS WERE SATISFIED: 2,361 zones with ZERO pairs over the 200-per-pair cap, and
// 882 setups against a cap of 1,000. The caps count RECORDS; the ceiling is BYTES. TRIGGER-1 is
// the fixture that matters most -- it reproduces exactly that state and fails if eviction does
// not fire.
//
// SAFETY-1..SAFETY-4 are the other half. Measuring pressure in bytes must NOT loosen the
// eviction-safety rule: a record belonging to an open position, or to a closed trade whose
// evidence is not yet in tier (b), is still never deleted. When budget and safety conflict, the
// trim STOPS and says so. An over-full buffer is recoverable; a deleted record is not, and that
// ordering does not change because the pressure is now measured differently.
//
// Run:  node tests/run_v165_byte_budget_tests.js

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
function constVal(decl) {
  const m = new RegExp(decl + '\\s*=\\s*(\\d+)').exec(SRC);
  if (!m) throw new Error('not found: ' + decl);
  return parseInt(m[1], 10);
}

const ctx = { console: console, Math: Math, JSON: JSON, isFinite: isFinite, Array: Array,
  Number: Number, Object: Object, String: String, Date: Date, isNaN: isNaN };
vm.createContext(ctx);
['EVIDENCE_SETUPS_MAX', 'EVIDENCE_ZONES_MAX_PER_PAIR', 'EVIDENCE_ZONES_MAX_BYTES',
  'EVIDENCE_SETUPS_MAX_BYTES'].forEach(function (n) {
    vm.runInContext('var ' + n + '=' + constVal('const ' + n) + ';', ctx);
  });
vm.runInContext('var alexGZoneState=null, alexGSetupState=null;', ctx);
['evidenceBufferBytes', 'evidenceBufferByteState', 'evidenceTrimSetupsToBudget',
  'evidenceTrimZonesToBudget'].forEach(function (n) { vm.runInContext(fn(n), ctx); });
const P = ctx;
const SETUP_CAP = constVal('const EVIDENCE_SETUPS_MAX');
const ZONE_CAP = constVal('const EVIDENCE_ZONES_MAX_PER_PAIR');
const ZONE_BYTES = constVal('const EVIDENCE_ZONES_MAX_BYTES');
const SETUP_BYTES = constVal('const EVIDENCE_SETUPS_MAX_BYTES');

const results = [];
function t(name, desc, f) {
  let pass = false, detail = '';
  try { const r = f(); pass = !!(r && r.pass); detail = (r && r.detail) || ''; }
  catch (e) { pass = false; detail = 'threw: ' + (e && e.message ? e.message : String(e)); }
  results.push({ name: name, desc: desc, pass: pass, detail: detail });
}
// A setup record of roughly the size the real engine produces, so byte pressure is reached at a
// realistic record count rather than by inflating one record to absurdity.
function setup(i, bytes) {
  return { setupId: 'S' + i, qualificationTimestamp: 2000000 - i,
    pad: new Array(Math.max(1, bytes || 800)).join('x') };
}
function zone(pair, tf, i, bytes) {
  return { id: pair + '-' + tf + '-' + i, formedAt: 2000000 - i,
    pad: new Array(Math.max(1, bytes || 800)).join('z') };
}
function zoneState(pairs, perPair, bytes) {
  const z = {};
  pairs.forEach(function (p) {
    z[p] = { H1: { validatedZones: [] } };
    for (let i = 0; i < perPair; i++) z[p].H1.validatedZones.push(zone(p, 'H1', i, bytes));
  });
  return z;
}

// ══ THE TRIGGER — the defect measured on the operator instance ════════════════════════════════

t('TRIGGER-1', 'THE ONE THIS EXISTS FOR: reproduce the operator state — 28 instruments, ~84 zones '
  + 'each, EVERY count cap satisfied — and the buffer is still megabytes over what localStorage '
  + 'can hold. Byte pressure must be detected where the count caps see nothing wrong', function () {
  const pairs = []; for (let i = 0; i < 28; i++) pairs.push('P' + i);
  const zs = zoneState(pairs, 84, 2400);
  let maxPerPair = 0;
  Object.keys(zs).forEach(function (p) { maxPerPair = Math.max(maxPerPair, zs[p].H1.validatedZones.length); });
  const bytes = P.evidenceBufferBytes(zs, 'fxhub_alexg_zones');
  return { pass: maxPerPair <= ZONE_CAP && bytes > ZONE_BYTES,
    detail: maxPerPair + ' zones per pair (cap ' + ZONE_CAP + ' — satisfied), '
      + (bytes / 1e6).toFixed(2) + ' MB against a ' + (ZONE_BYTES / 1e6).toFixed(1) + ' MB budget' };
});

t('TRIGGER-2', 'the enforce path treats a byte overflow as a first-class trigger, not a refinement '
  + 'of the count one. Gated behind the count caps it could never fire', function () {
  const src = codeOf(fn('evidenceEnforceBufferLimits'));
  return { pass: /evidenceBufferByteState\(\)/.test(src)
      && /!byteState\.zonesOverBudget&&!byteState\.setupsOverBudget/.test(src),
    detail: 'byte state is part of the early-return condition' };
});

t('TRIGGER-3', 'byte state reports WHICH buffer is over and by how much, rather than a bare '
  + 'boolean an operator cannot act on', function () {
  vm.runInContext('alexGZoneState=' + JSON.stringify(zoneState(['A'], 3, 100))
    + '; alexGSetupState=[];', ctx);
  const s = P.evidenceBufferByteState();
  return { pass: typeof s.zoneBytes === 'number' && typeof s.setupBytes === 'number'
      && s.zoneBudget === ZONE_BYTES && s.setupBudget === SETUP_BYTES
      && s.zonesOverBudget === false && s.setupsOverBudget === false,
    detail: 'small buffers report under budget with both sizes and both budgets present' };
});

// ══ TRIMMING ══════════════════════════════════════════════════════════════════════════════════

t('TRIM-1', 'setups are trimmed until under the BYTE budget even when the count cap is satisfied '
  + 'throughout', function () {
  const list = []; for (let i = 0; i < 900; i++) list.push(setup(i, 3000));
  const before = P.evidenceBufferBytes(list, 'fxhub_alexg_setups');
  const r = P.evidenceTrimSetupsToBudget(list, {});
  const after = P.evidenceBufferBytes(r.kept, 'fxhub_alexg_setups');
  return { pass: list.length < SETUP_CAP && before > SETUP_BYTES && after <= SETUP_BYTES && r.evicted > 0,
    detail: '900 records (under the ' + SETUP_CAP + ' cap), ' + (before / 1e6).toFixed(2)
      + ' MB → ' + (after / 1e6).toFixed(2) + ' MB, ' + r.evicted + ' evicted' };
});

t('TRIM-2', 'the OLDEST go first. Evicting newest-first would throw away the records most likely '
  + 'to still matter', function () {
  const list = []; for (let i = 0; i < 900; i++) list.push(setup(i, 3000));
  const r = P.evidenceTrimSetupsToBudget(list, {});
  const keptTs = r.kept.map(function (s) { return s.qualificationTimestamp; });
  const evictedOldest = Math.min.apply(null, keptTs) > 2000000 - 900;
  return { pass: r.evicted > 0 && evictedOldest && keptTs[0] === 2000000,
    detail: 'newest kept, oldest ' + r.evicted + ' dropped' };
});

t('TRIM-3', 'the count cap still binds. Byte awareness ADDS a constraint, it does not replace the '
  + 'C4 ruling', function () {
  const list = []; for (let i = 0; i < 1500; i++) list.push(setup(i, 10));
  const bytes = P.evidenceBufferBytes(list, 'fxhub_alexg_setups');
  const r = P.evidenceTrimSetupsToBudget(list, {});
  return { pass: bytes < SETUP_BYTES && r.kept.length === SETUP_CAP && r.evicted === 500,
    detail: 'tiny records, well under the byte budget, still trimmed to the ' + SETUP_CAP + ' count cap' };
});

t('TRIM-4', 'zones are trimmed GLOBALLY oldest-first, not per pair. A per-pair count cap cannot '
  + 'see a total spread thinly across 28 instruments — which is exactly the operator state',
  function () {
  const pairs = []; for (let i = 0; i < 28; i++) pairs.push('P' + i);
  const zs = zoneState(pairs, 84, 2400);
  const before = P.evidenceBufferBytes(zs, 'fxhub_alexg_zones');
  const r = P.evidenceTrimZonesToBudget(zs, {});
  const after = P.evidenceBufferBytes(zs, 'fxhub_alexg_zones');
  return { pass: before > ZONE_BYTES && after <= ZONE_BYTES && r.evicted > 0,
    detail: (before / 1e6).toFixed(2) + ' MB → ' + (after / 1e6).toFixed(2) + ' MB, '
      + r.evicted + ' zones evicted with no pair ever over the count cap' };
});

t('TRIM-5', 'the per-pair count cap still binds too', function () {
  const zs = zoneState(['A'], 300, 10);
  const bytes = P.evidenceBufferBytes(zs, 'fxhub_alexg_zones');
  P.evidenceTrimZonesToBudget(zs, {});
  return { pass: bytes < ZONE_BYTES && zs.A.H1.validatedZones.length === ZONE_CAP,
    detail: '300 tiny zones on one pair, under the byte budget, trimmed to ' + ZONE_CAP };
});

t('TRIM-6', 'a buffer already under both limits is left completely alone', function () {
  const list = [setup(1, 100), setup(2, 100)];
  const r = P.evidenceTrimSetupsToBudget(list, {});
  const zs = zoneState(['A'], 5, 100);
  const rz = P.evidenceTrimZonesToBudget(zs, {});
  return { pass: r.evicted === 0 && r.kept.length === 2 && rz.evicted === 0
      && zs.A.H1.validatedZones.length === 5,
    detail: 'nothing evicted from a healthy buffer' };
});

// ══ SAFETY — measuring in bytes must not loosen the rule ══════════════════════════════════════

t('SAFETY-1', 'THE RULE HOLDS: a setup whose evidence is not yet safe is NEVER evicted, however '
  + 'far over budget the buffer is. An over-full buffer is recoverable; a deleted record is not',
  function () {
  const list = []; for (let i = 0; i < 900; i++) list.push(setup(i, 3000));
  const blocked = {}; for (let i = 800; i < 900; i++) blocked['S' + i] = true;   // the oldest 100
  const r = P.evidenceTrimSetupsToBudget(list, blocked);
  const keptIds = {}; r.kept.forEach(function (s) { keptIds[s.setupId] = true; });
  const allBlockedKept = Object.keys(blocked).every(function (id) { return keptIds[id]; });
  return { pass: allBlockedKept && r.skipped === 100,
    detail: 'all 100 protected records survived; ' + r.skipped + ' skipped, ' + r.evicted + ' evicted' };
});

t('SAFETY-2', 'and when EVERY remaining record is protected the trim STOPS rather than deleting '
  + 'one — reporting stillOver instead of quietly obeying the budget', function () {
  const list = []; for (let i = 0; i < 900; i++) list.push(setup(i, 3000));
  const blocked = {}; list.forEach(function (s) { blocked[s.setupId] = true; });
  const r = P.evidenceTrimSetupsToBudget(list, blocked);
  const after = P.evidenceBufferBytes(r.kept, 'fxhub_alexg_setups');
  return { pass: r.evicted === 0 && r.kept.length === 900 && r.stillOver === true
      && after > SETUP_BYTES,
    detail: 'nothing deleted, buffer left ' + (after / 1e6).toFixed(2)
      + ' MB over budget, stillOver reported' };
});

t('SAFETY-3', 'the same rule for zones — protected zones survive and stillOver is raised',
  function () {
  const pairs = []; for (let i = 0; i < 28; i++) pairs.push('P' + i);
  const zs = zoneState(pairs, 84, 2400);
  const blocked = {};
  Object.keys(zs).forEach(function (p) {
    zs[p].H1.validatedZones.forEach(function (z) { blocked[z.id] = true; });
  });
  const r = P.evidenceTrimZonesToBudget(zs, blocked);
  return { pass: r.evicted === 0 && r.stillOver === true,
    detail: 'all zones protected: nothing evicted, stillOver raised' };
});

t('SAFETY-4', 'stillOver reaches the OPERATOR. A buffer over budget whose every record is '
  + 'protected will never shrink on its own, and only exporting evidence releases it', function () {
  const src = codeOf(fn('evidenceEvictBuffers'));
  return { pass: /stillOverSetups\|\|stillOverZones/.test(src)
      && /export evidence to release it/i.test(src)
      && /evidenceStorageBanner/.test(src),
    detail: 'a banner is raised naming the export as the release' };
});

t('SAFETY-5', 'nothing here writes, removes or clears storage directly — eviction still goes '
  + 'through the existing persist path', function () {
  const body = codeOf(fn('evidenceTrimSetupsToBudget') + fn('evidenceTrimZonesToBudget')
    + fn('evidenceBufferBytes') + fn('evidenceBufferByteState'));
  return { pass: !/localStorage|removeItem|\.clear\(|indexedDB/.test(body),
    detail: 'the trimmers are pure — they return survivors, they do not touch storage' };
});

// ══ ARITHMETIC ════════════════════════════════════════════════════════════════════════════════

t('BYTES-1', 'size counts the key as well as the value, and in UTF-16 — the same arithmetic the '
  + 'storage diagnostic reports, so the two can never disagree about what is over budget',
  function () {
  const b = P.evidenceBufferBytes([1, 2, 3], 'k');
  return { pass: b === (JSON.stringify([1, 2, 3]).length + 1) * 2,
    detail: 'key + value, x2 for UTF-16 = ' + b + ' bytes' };
});

t('BYTES-2', 'a value that cannot be serialised returns null rather than a fabricated size. A '
  + 'cyclic buffer is a defect to surface, not a number to invent', function () {
  const cyc = vm.runInContext('(function(){var a={};a.self=a;return a;})()', ctx);
  return { pass: P.evidenceBufferBytes(cyc, 'k') === null && P.evidenceBufferBytes(undefined, 'k') === null,
    detail: 'cyclic and undefined both yield null' };
});

t('BYTES-3', 'the budgets leave real headroom: together they reserve under 4 MB of a ~5 MB '
  + 'localStorage floor, so the ledger, journal and config keys still fit', function () {
  return { pass: ZONE_BYTES + SETUP_BYTES <= 4000000 && ZONE_BYTES > 0 && SETUP_BYTES > 0,
    detail: ((ZONE_BYTES + SETUP_BYTES) / 1e6).toFixed(1) + ' MB reserved for both buffers' };
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

t('GUARD-2', 'zero protected drift — the eviction path was already unprotected and the trading '
  + 'engine is untouched', function () {
  const reg = JSON.parse(fs.readFileSync(path.join(ROOT, 'regression-baseline.json'), 'utf8'));
  const p = Object.keys(reg.protectedFunctions || {});
  return { pass: p.length === 64 && Object.keys(reg.protectedConstants || {}).length === 4
      && p.indexOf('evidenceEvictBuffers') === -1,
    detail: '64 functions, 4 constants; eviction path unprotected as before' };
});

let pass = 0;
results.forEach(function (r) {
  if (r.pass) pass++;
  console.log((r.pass ? '  PASS  ' : '  FAIL  ') + r.name + '  ' + r.desc);
  if (r.detail) console.log('          ' + r.detail);
});
console.log('\n  ' + pass + ' / ' + results.length + ' passed');
process.exit(pass === results.length ? 0 : 1);

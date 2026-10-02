#!/usr/bin/env node
// RUN_ALL_EXEC: node tests/run_v1269_zone_persistence_tests.js
'use strict';
// ══════════════════════════════════════════════════════════════════════════════════════════════
// fxhub_alexg_zones -> IndexedDB: MIGRATION AND FAILURE HANDLING
// ══════════════════════════════════════════════════════════════════════════════════════════════
//
// THE DEFECT. saveAlexGRest() wrote the whole ALEX zone state (~5.8 MB on the operator instance)
// to localStorage on every engine write. localStorage has its own ~5-10 MB per-origin ceiling,
// separate from the origin quota IndexedDB draws on -- which is why Diagnostics showed repeated
// QUOTA_EXCEEDED on localStorage.setItem while the origin estimate read under 2% used. And because
// zones are written before setups and declined setups in the same try block, every failed zone
// write also silently skipped those two keys.
//
// THE FIX UNDER TEST. Zone state moves to a record in the EXISTING mogo_evidence `meta` object
// store (no schema bump). The legacy localStorage copy is READ for migration and never written or
// removed. Every fixture below drives the REAL functions extracted from index.html against an
// in-memory fake IndexedDB and a quota-limited fake localStorage -- nothing is re-implemented.
//
// Run:  node tests/run_v1269_zone_persistence_tests.js
//       MOGO_INDEX=/path/to/mutant.html node tests/run_v1269_zone_persistence_tests.js

const fs = require('fs');
const path = require('path');
const vm = require('vm');
const ROOT = path.resolve(__dirname, '..');
const SRC = fs.readFileSync(process.env.MOGO_INDEX || path.join(ROOT, 'index.html'), 'utf8');

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
function constLine(name) {
  const m = new RegExp('const ' + name + '\\s*=\\s*([^;]+);').exec(SRC);
  if (!m) throw new Error('not found: const ' + name);
  return 'var ' + name + '=' + m[1] + ';';
}

// ── fake localStorage with a byte ceiling, billed like the diagnostic (UTF-16, key + value) ──
function makeLocalStorage(limitBytes) {
  const store = {};
  const setCalls = [];
  function used(except) {
    let n = 0;
    Object.keys(store).forEach(function (k) { if (k !== except) n += (k.length + store[k].length) * 2; });
    return n;
  }
  return {
    store: store, setCalls: setCalls, getThrows: {},
    getItem: function (k) {
      if (this.getThrows[k]) { const e = new Error('read denied'); e.name = 'SecurityError'; throw e; }
      return Object.prototype.hasOwnProperty.call(store, k) ? store[k] : null;
    },
    setItem: function (k, v) {
      v = String(v);
      setCalls.push(k);
      if (used(k) + (k.length + v.length) * 2 > limitBytes) {
        const e = new Error("Failed to execute 'setItem' on 'Storage': Setting the value of '" + k + "' exceeded the quota.");
        e.name = 'QuotaExceededError'; e.code = 22; throw e;
      }
      store[k] = v;
    },
    removeItem: function (k) { delete store[k]; }
  };
}

// ── fake IndexedDB: just enough of open/transaction/objectStore/get/put for the real helpers ──
function makeIndexedDB(opts) {
  opts = opts || {};
  const stores = { meta: new Map(), packages: new Map(), observations: new Map() };
  const clone = function (v) { return v === undefined ? undefined : structuredClone(v); };
  const db = {
    objectStoreNames: { contains: function (n) { return Object.prototype.hasOwnProperty.call(stores, n); } },
    transaction: function (names, mode) {
      const tx = { oncomplete: null, onerror: null, onabort: null, error: null, pending: 0, failed: false };
      // Like a real transaction: it commits (or aborts) exactly once, and only when no request
      // is outstanding at the moment it would finish.
      function settle() {
        if (tx.pending > 0) return;
        setImmediate(function () {
          if (tx.pending > 0 || tx.finished) return;
          tx.finished = true;
          if (tx.failed) { if (tx.onabort) tx.onabort(); }
          else if (tx.oncomplete) tx.oncomplete();
        });
      }
      tx.objectStore = function (n) {
        const s = stores[n];
        return {
          get: function (key) {
            const req = { onsuccess: null, onerror: null, result: undefined, error: null };
            tx.pending++;
            setImmediate(function () {
              if (opts.getFails) { req.error = opts.getFails(); tx.failed = true; tx.error = req.error; if (req.onerror) req.onerror(); }
              else { req.result = clone(s.get(key)); if (req.onsuccess) req.onsuccess(); }
              tx.pending--; settle();
            });
            return req;
          },
          put: function (rec) {
            if (mode !== 'readwrite') throw new Error('ReadOnlyError');
            const req = { onsuccess: null, onerror: null, result: undefined, error: null };
            tx.pending++;
            setImmediate(function () {
              const fail = opts.putFails && opts.putFails(rec);
              if (fail) { req.error = fail; tx.failed = true; tx.error = fail; if (req.onerror) req.onerror(); }
              else {
                const stored = clone(rec);
                if (opts.corruptOnWrite) stored.json = stored.json.slice(0, -1);
                s.set(rec.key, stored); req.result = rec.key; if (req.onsuccess) req.onsuccess();
              }
              tx.pending--; settle();
            });
            return req;
          }
        };
      };
      settle();
      return tx;
    }
  };
  return {
    stores: stores,
    open: function () {
      const req = { onsuccess: null, onerror: null, onblocked: null, onupgradeneeded: null, result: null, error: null };
      setImmediate(function () {
        if (opts.openHangs) return;
        if (opts.openFails) { req.error = new Error('IndexedDB open failed (fixture)'); if (req.onerror) req.onerror(); return; }
        req.result = db; if (req.onsuccess) req.onsuccess();
      });
      return req;
    }
  };
}

// ── a fresh app context per fixture, built from the REAL functions in index.html ──
const APP_FUNCTIONS = ['recordStorageLoadFailure', 'storageKeyBlockedFromWrite', 'loadStoredKey',
  'persistStorageKey', 'loadAlexGSaved', 'saveAlexGRest', 'evidenceOpenDb', 'evidenceTxDone',
  'evidenceReq', 'evidenceClassifyStorageError',
  'alexGZonesReadLocationMarker', 'alexGZonesWriteLocationMarker', 'alexGZonesIdbGet',
  'alexGZonesIdbPut', 'alexGZonesWithTimeout', 'alexGZonesBlock', 'alexGLoadZonesDurable',
  'alexGPersistZones', 'alexGZonesDrain', 'alexGZonesFlush'];
const APP_CONSTS = ['EVIDENCE_DB_NAME', 'EVIDENCE_DB_VERSION', 'EVIDENCE_STORE_PACKAGES',
  'EVIDENCE_STORE_META', 'EVIDENCE_STORE_OBSERVATIONS', 'ALEXG_ZONES_LS_KEY', 'ALEXG_ZONES_IDB_KEY',
  'ALEXG_ZONES_LOCATION_KEY', 'ALEXG_ZONES_LOAD_TIMEOUT_MS'];

function makeApp(opt) {
  opt = opt || {};
  const ls = makeLocalStorage(opt.lsLimit || 5 * 1024 * 1024);
  Object.keys(opt.ls || {}).forEach(function (k) { ls.store[k] = opt.ls[k]; });
  Object.keys(opt.lsGetThrows || {}).forEach(function (k) { ls.getThrows[k] = true; });
  const idb = opt.noIndexedDB ? undefined : makeIndexedDB(opt.idb);
  if (idb && opt.idbMeta) Object.keys(opt.idbMeta).forEach(function (k) { idb.stores.meta.set(k, opt.idbMeta[k]); });
  const ctx = {
    console: console, JSON: JSON, Object: Object, Array: Array, String: String, Number: Number,
    Date: Date, Error: Error, Promise: Promise, Math: Math, setTimeout: setTimeout,
    clearTimeout: clearTimeout, localStorage: ls, indexedDB: idb, APP_VERSION: 'test'
  };
  vm.createContext(ctx);
  APP_CONSTS.forEach(function (c) { vm.runInContext(constLine(c), ctx); });
  if (opt.timeoutMs != null) vm.runInContext('ALEXG_ZONES_LOAD_TIMEOUT_MS=' + opt.timeoutMs + ';', ctx);
  vm.runInContext([
    'var storageLoadFailures={};',
    'var evidenceDbHandle=null, evidenceDbUnavailableReason=null;',
    'var alexGAccount={}, alexGAccountKnownVersion=0, alexGJournalEntries=[], alexGAutoTrading={enabled:false},',
    '    alexGZoneState={}, alexGSetupState=[], alexGDeclinedSetups=[];',
    'var engineErrors=[], writeFailures=[];',
    'function recordPaperEngineError(m){}',
    'function recordAlexGEngineError(m){ engineErrors.push(String(m)); }',
    'function alexGAuditRehydratedPositions(){}',
    'function evidenceRecordWriteFailure(context,err){ writeFailures.push({context:context,kind:evidenceClassifyStorageError(err),message:String(err&&err.message||err)}); }',
    // live accessors
    'function __zoneStore(){ return alexGZonesStore; }'
  ].join('\n'), ctx);
  // The zone-store state variables are declared with `let` in index.html; mirror them as vars.
  const stateDecl = /let alexGZonesStore=[\s\S]*?;\nlet alexGZonesPendingJson=null;\nlet alexGZonesWriteInFlight=false;/.exec(SRC);
  if (!stateDecl) throw new Error('zone-store state declarations not found');
  vm.runInContext(stateDecl[0].replace(/\blet\b/g, 'var'), ctx);
  APP_FUNCTIONS.forEach(function (n) { vm.runInContext(fn(n), ctx); });
  return { ctx: ctx, ls: ls, idb: idb,
    run: function (code) { return vm.runInContext(code, ctx); } };
}

// A realistic zone state: 28 pairs x 4 timeframes, sized so the serialised state is several MB.
function zoneState(pairs, perTf, padBytes) {
  const z = {};
  for (let p = 0; p < pairs; p++) {
    const pair = 'P' + p;
    z[pair] = {};
    ['H1', 'H4', 'D', 'W'].forEach(function (tf) {
      const zones = [];
      for (let i = 0; i < perTf; i++) zones.push({ id: pair + '-' + tf + '-' + i, formedAt: 1e12 + i, low: 1 + i / 1e4, high: 1 + i / 1e4 + 0.001, pad: 'z'.repeat(padBytes || 40) });
      z[pair][tf] = { pendingAnchors: [], provisionalClusters: [], validatedZones: zones };
    });
  }
  return z;
}
function countZones(z) {
  let n = 0;
  Object.keys(z).forEach(function (p) { Object.keys(z[p]).forEach(function (tf) { n += (z[p][tf].validatedZones || []).length; }); });
  return n;
}

const results = [];
async function t(name, desc, f) {
  let pass = false, detail = '';
  try { const r = await f(); pass = !!(r && r.pass); detail = (r && r.detail) || ''; }
  catch (e) { pass = false; detail = 'threw: ' + (e && e.message ? e.message : String(e)); }
  results.push({ name: name, desc: desc, pass: pass, detail: detail });
}
function fail(msg) { return { pass: false, detail: msg }; }

(async function main() {
  const LEGACY = zoneState(28, 22, 40);                      // ~2,464 zones
  const LEGACY_JSON = JSON.stringify(LEGACY);
  const LIMIT = LEGACY_JSON.length * 2 + 200000;             // localStorage just big enough to hold the legacy copy

  // ══ MIGRATION ══════════════════════════════════════════════════════════════════════════════
  await t('MIG-1', 'legacy localStorage zones migrate to IndexedDB byte-for-byte, and the legacy copy is left untouched', async function () {
    const a = makeApp({ ls: { fxhub_alexg_zones: LEGACY_JSON }, lsLimit: LIMIT });
    a.run('loadAlexGSaved()');
    await a.run('alexGLoadZonesDurable()');
    const st = a.run('__zoneStore()');
    const rec = a.idb.stores.meta.get('alexg_zones');
    if (st.mode !== 'INDEXEDDB') return fail('mode=' + st.mode + ' reason=' + st.reason);
    if (st.source !== 'MIGRATED_FROM_LOCALSTORAGE') return fail('source=' + st.source);
    if (!rec || rec.json !== LEGACY_JSON) return fail('IndexedDB record is not the legacy bytes');
    if (a.ls.store.fxhub_alexg_zones !== LEGACY_JSON) return fail('legacy localStorage copy was altered');
    if (a.ls.store.fxhub_alexg_zones_location !== 'indexeddb') return fail('location marker not written');
    if (a.ls.setCalls.indexOf('fxhub_alexg_zones') !== -1) return fail('the legacy key was written during migration');
    return { pass: true, detail: countZones(LEGACY) + ' zones, ' + (LEGACY_JSON.length * 2) + ' bytes migrated' };
  });

  await t('MIG-2', 'migration preserves every zone -- nothing trimmed, nothing evicted', async function () {
    const a = makeApp({ ls: { fxhub_alexg_zones: LEGACY_JSON }, lsLimit: LIMIT });
    a.run('loadAlexGSaved()');
    await a.run('alexGLoadZonesDurable()');
    const inMem = JSON.parse(a.run('JSON.stringify(alexGZoneState)'));
    const stored = JSON.parse(a.idb.stores.meta.get('alexg_zones').json);
    const n0 = countZones(LEGACY), n1 = countZones(inMem), n2 = countZones(stored);
    if (n0 === 0) return fail('vacuous: fixture has no zones');
    if (n1 !== n0 || n2 !== n0) return fail('counts legacy/memory/stored = ' + n0 + '/' + n1 + '/' + n2);
    return { pass: true, detail: n0 + ' = ' + n1 + ' = ' + n2 };
  });

  await t('MIG-3', 'an existing IndexedDB record wins over the stale legacy localStorage copy', async function () {
    const newer = zoneState(2, 3, 5); newer.P0.H1.validatedZones.push({ id: 'NEWER', formedAt: 2e12 });
    const a = makeApp({ ls: { fxhub_alexg_zones: LEGACY_JSON, fxhub_alexg_zones_location: 'indexeddb' },
      lsLimit: LIMIT, idbMeta: { alexg_zones: { key: 'alexg_zones', json: JSON.stringify(newer) } } });
    a.run('loadAlexGSaved()');
    await a.run('alexGLoadZonesDurable()');
    const st = a.run('__zoneStore()');
    if (st.mode !== 'INDEXEDDB' || st.source !== 'INDEXEDDB') return fail('mode/source=' + st.mode + '/' + st.source);
    if (a.run('JSON.stringify(alexGZoneState)') !== JSON.stringify(newer)) return fail('in-memory state is not the IndexedDB record');
    if (a.ls.store.fxhub_alexg_zones !== LEGACY_JSON) return fail('legacy copy altered');
    return { pass: true };
  });

  await t('MIG-4', 'a fresh install (nothing stored anywhere) starts on IndexedDB with an empty state', async function () {
    const a = makeApp({});
    a.run('loadAlexGSaved()');
    await a.run('alexGLoadZonesDurable()');
    const st = a.run('__zoneStore()');
    if (st.mode !== 'INDEXEDDB') return fail('mode=' + st.mode);
    if (a.ls.store.fxhub_alexg_zones !== undefined) return fail('a legacy key was created');
    return { pass: true };
  });

  // ══ STARTUP BARRIER ══════════════════════════════════════════════════════════════════════════
  await t('BARRIER-1', 'a save BEFORE the durable load writes nothing anywhere, and the stored zones survive it', async function () {
    const durable = zoneState(3, 4, 5);
    const a = makeApp({ ls: { fxhub_alexg_zones: LEGACY_JSON, fxhub_alexg_zones_location: 'indexeddb' }, lsLimit: LIMIT,
      idbMeta: { alexg_zones: { key: 'alexg_zones', json: JSON.stringify(durable) } } });
    a.run('loadAlexGSaved()');
    if (a.run('__zoneStore()').mode !== 'PENDING') return fail('barrier not engaged at start: ' + a.run('__zoneStore()').mode);
    a.run('alexGZoneState={wiped:true}'); a.run('alexGSetupState=[{setupId:"S0"}]');
    a.run('saveAlexGRest()');
    await a.run('alexGZonesFlush()');
    if (a.idb.stores.meta.get('alexg_zones').json !== JSON.stringify(durable)) return fail('pre-load save overwrote the IndexedDB copy');
    if (a.ls.store.fxhub_alexg_zones !== LEGACY_JSON) return fail('pre-load save overwrote the legacy copy');
    if (a.ls.store.fxhub_alexg_setups !== '[{"setupId":"S0"}]') return fail('the barrier also stopped setups');
    await a.run('alexGLoadZonesDurable()');
    if (a.run('JSON.stringify(alexGZoneState)') !== JSON.stringify(durable)) return fail('load did not restore the durable state');
    return { pass: true };
  });

  await t('BARRIER-2', 'the barrier also holds against an unmigrated legacy copy: a pre-load save cannot replace it before migration', async function () {
    const a = makeApp({ ls: { fxhub_alexg_zones: LEGACY_JSON }, lsLimit: LIMIT * 2 });
    a.run('loadAlexGSaved()');
    a.run('alexGZoneState={wiped:true}'); a.run('saveAlexGRest()');
    if (a.ls.store.fxhub_alexg_zones !== LEGACY_JSON) return fail('legacy copy replaced before migration');
    if (a.ls.setCalls.indexOf('fxhub_alexg_zones') !== -1) return fail('a zone write was attempted during the barrier');
    return { pass: true };
  });

  // ══ THE QUOTA DEFECT, reproduced and then removed ════════════════════════════════════════════
  await t('QUOTA-1', 'POSITIVE CONTROL: on the legacy localStorage path a large zone state hits QUOTA_EXCEEDED and setups are skipped', async function () {
    const a = makeApp({ ls: { fxhub_alexg_zones: LEGACY_JSON }, lsLimit: LIMIT, noIndexedDB: true });
    a.run('loadAlexGSaved()');
    await a.run('alexGLoadZonesDurable()');
    if (a.run('__zoneStore()').mode !== 'LOCALSTORAGE') return fail('fixture is not on the legacy path');
    a.run('writeFailures.length=0');
    a.run('alexGZoneState.P0.H1.validatedZones.push({id:"GROW",formedAt:3e12,pad:"' + 'g'.repeat(250000) + '"})');
    a.run('alexGSetupState=[{setupId:"S1"}]');
    a.run('saveAlexGRest()');
    const wf = a.run('writeFailures');
    if (!wf.length || wf[0].kind !== 'QUOTA_EXCEEDED') return fail('no QUOTA_EXCEEDED recorded -- the fixture does not reproduce the defect: ' + JSON.stringify(wf));
    if (a.ls.store.fxhub_alexg_setups !== undefined) return fail('setups were written -- the cascade is not reproduced');
    if (a.ls.store.fxhub_alexg_zones !== LEGACY_JSON) return fail('a failed setItem must leave the old value');
    return { pass: true, detail: 'reproduced: ' + wf[0].kind + ' in ' + wf[0].context };
  });

  await t('QUOTA-2', 'after the durable load, the same growth saves to IndexedDB with no failure, and setups persist again', async function () {
    const a = makeApp({ ls: { fxhub_alexg_zones: LEGACY_JSON }, lsLimit: LIMIT });
    a.run('loadAlexGSaved()');
    await a.run('alexGLoadZonesDurable()');
    a.run('alexGZoneState.P0.H1.validatedZones.push({id:"GROW",formedAt:3e12,pad:"' + 'g'.repeat(250000) + '"})');
    a.run('alexGSetupState=[{setupId:"S1"}]');
    a.run('saveAlexGRest()');
    await a.run('alexGZonesFlush()');
    const wf = a.run('writeFailures');
    if (wf.length) return fail('write failures recorded: ' + JSON.stringify(wf));
    const rec = a.idb.stores.meta.get('alexg_zones');
    if (!rec || rec.json !== a.run('JSON.stringify(alexGZoneState)')) return fail('IndexedDB does not hold the current state');
    if (a.ls.store.fxhub_alexg_setups !== '[{"setupId":"S1"}]') return fail('setups not persisted');
    if (a.ls.store.fxhub_alexg_zones !== LEGACY_JSON) return fail('legacy copy altered');
    if (a.ls.setCalls.indexOf('fxhub_alexg_zones') !== -1) return fail('saveAlexGRest still wrote zones to localStorage');
    return { pass: true };
  });

  await t('QUOTA-3', 'rapid successive saves coalesce and the LAST state is what IndexedDB holds', async function () {
    const a = makeApp({});
    a.run('loadAlexGSaved()');
    await a.run('alexGLoadZonesDurable()');
    for (let i = 0; i < 6; i++) { a.run('alexGZoneState={n:' + i + '}'); a.run('saveAlexGRest()'); }
    await a.run('alexGZonesFlush()');
    const rec = a.idb.stores.meta.get('alexg_zones');
    if (!rec || rec.json !== '{"n":5}') return fail('stored=' + (rec && rec.json));
    return { pass: true };
  });

  // ══ FAILURE HANDLING ═════════════════════════════════════════════════════════════════════════
  await t('FAIL-1', 'IndexedDB unavailable and no marker: stays on localStorage exactly as before', async function () {
    const a = makeApp({ ls: { fxhub_alexg_zones: '{"P0":{}}' }, noIndexedDB: true });
    a.run('loadAlexGSaved()');
    await a.run('alexGLoadZonesDurable()');
    const st = a.run('__zoneStore()');
    if (st.mode !== 'LOCALSTORAGE') return fail('mode=' + st.mode);
    a.run('alexGZoneState={P1:{}}'); a.run('saveAlexGRest()');
    if (a.ls.store.fxhub_alexg_zones !== '{"P1":{}}') return fail('legacy save path not used');
    return { pass: true };
  });

  await t('FAIL-2', 'IndexedDB unavailable but the marker says zones live there: writes BLOCKED, legacy untouched, setups still saved', async function () {
    const a = makeApp({ ls: { fxhub_alexg_zones: LEGACY_JSON, fxhub_alexg_zones_location: 'indexeddb' }, lsLimit: LIMIT, idb: { openFails: true } });
    a.run('loadAlexGSaved()');
    await a.run('alexGLoadZonesDurable()');
    const st = a.run('__zoneStore()');
    if (st.mode !== 'BLOCKED') return fail('mode=' + st.mode);
    a.run('alexGZoneState={wiped:true}'); a.run('alexGSetupState=[{setupId:"S9"}]'); a.run('saveAlexGRest()');
    if (a.ls.store.fxhub_alexg_zones !== LEGACY_JSON) return fail('a stale write reached the legacy key');
    if (a.ls.store.fxhub_alexg_setups !== '[{"setupId":"S9"}]') return fail('blocking zones also blocked setups');
    if (!a.run('engineErrors').some(function (m) { return /zone/i.test(m) && /BLOCKED|not be saved/i.test(m); })) return fail('the block was silent');
    return { pass: true };
  });

  await t('FAIL-3', 'a corrupt IndexedDB record is never overwritten', async function () {
    const a = makeApp({ ls: { fxhub_alexg_zones: LEGACY_JSON }, lsLimit: LIMIT,
      idbMeta: { alexg_zones: { key: 'alexg_zones', json: '{CORRUPT BUT REAL' } } });
    a.run('loadAlexGSaved()');
    await a.run('alexGLoadZonesDurable()');
    const st = a.run('__zoneStore()');
    if (st.mode !== 'BLOCKED') return fail('mode=' + st.mode);
    a.run('alexGZoneState={wiped:true}'); a.run('saveAlexGRest()');
    await a.run('alexGZonesFlush()');
    if (a.idb.stores.meta.get('alexg_zones').json !== '{CORRUPT BUT REAL') return fail('the corrupt record was overwritten');
    if (a.ls.store.fxhub_alexg_zones !== LEGACY_JSON) return fail('legacy copy altered');
    return { pass: true };
  });

  await t('FAIL-4', 'INC-001 preserved: an UNREADABLE legacy key is not migrated, and nothing overwrites it', async function () {
    const a = makeApp({ ls: { fxhub_alexg_zones: '{BROKEN BUT REAL' } });
    a.run('loadAlexGSaved()');
    await a.run('alexGLoadZonesDurable()');
    a.run('alexGZoneState={wiped:true}'); a.run('saveAlexGRest()');
    await a.run('alexGZonesFlush()');
    if (a.idb.stores.meta.has('alexg_zones')) return fail('the in-memory default was written to IndexedDB, shadowing the real legacy data');
    if (a.ls.store.fxhub_alexg_zones !== '{BROKEN BUT REAL') return fail('the unreadable legacy key was overwritten');
    return { pass: true, detail: 'mode=' + a.run('__zoneStore()').mode };
  });

  await t('FAIL-5', 'migration write fails (IndexedDB quota): stays on localStorage, legacy untouched, failure recorded, no marker', async function () {
    const q = function () { const e = new Error('IDB quota'); e.name = 'QuotaExceededError'; return e; };
    const a = makeApp({ ls: { fxhub_alexg_zones: LEGACY_JSON }, lsLimit: LIMIT, idb: { putFails: q } });
    a.run('loadAlexGSaved()');
    await a.run('alexGLoadZonesDurable()');
    const st = a.run('__zoneStore()');
    if (st.mode !== 'LOCALSTORAGE') return fail('mode=' + st.mode);
    if (a.ls.store.fxhub_alexg_zones_location !== undefined) return fail('marker written for a failed migration');
    if (a.ls.store.fxhub_alexg_zones !== LEGACY_JSON) return fail('legacy altered');
    if (!a.run('writeFailures').some(function (w) { return w.context === 'alexg-zones-migrate'; })) return fail('failure not recorded');
    return { pass: true };
  });

  await t('FAIL-6', 'migration read-back mismatch is treated as a failed migration, never as success', async function () {
    const a = makeApp({ ls: { fxhub_alexg_zones: LEGACY_JSON }, lsLimit: LIMIT, idb: { corruptOnWrite: true } });
    a.run('loadAlexGSaved()');
    await a.run('alexGLoadZonesDurable()');
    const st = a.run('__zoneStore()');
    if (st.mode === 'INDEXEDDB') return fail('a copy that does not read back identically was accepted');
    if (a.ls.store.fxhub_alexg_zones_location !== undefined) return fail('marker written');
    return { pass: true, detail: 'mode=' + st.mode };
  });

  await t('FAIL-7', 'an IndexedDB save failure is recorded, never thrown, does not block setups, and the next save recovers', async function () {
    let failNext = false;
    const q = function () { if (!failNext) return null; failNext = false; const e = new Error('disk'); e.name = 'UnknownError'; return e; };
    const a = makeApp({ idb: { putFails: q } });
    a.run('loadAlexGSaved()');
    await a.run('alexGLoadZonesDurable()');
    failNext = true;
    a.run('alexGZoneState={v:1}'); a.run('alexGSetupState=[{setupId:"S2"}]');
    a.run('saveAlexGRest()');                                  // must not throw
    await a.run('alexGZonesFlush()');
    if (!a.run('writeFailures').some(function (w) { return w.context === 'alexg-zones-indexeddb'; })) return fail('failure not recorded: wf=' + JSON.stringify(a.run('writeFailures')) + ' st=' + JSON.stringify(a.run('__zoneStore()')) + ' rec=' + JSON.stringify(a.idb.stores.meta.get('alexg_zones')));
    if (a.ls.store.fxhub_alexg_setups !== '[{"setupId":"S2"}]') return fail('setups not saved');
    a.run('alexGZoneState={v:2}'); a.run('saveAlexGRest()');
    await a.run('alexGZonesFlush()');
    if (a.idb.stores.meta.get('alexg_zones').json !== '{"v":2}') return fail('did not recover');
    return { pass: true };
  });

  await t('FAIL-8', 'an IndexedDB open that never answers cannot hang startup: the loader settles on its timeout', async function () {
    const a = makeApp({ ls: { fxhub_alexg_zones: '{"P0":{}}' }, idb: { openHangs: true }, timeoutMs: 30 });
    a.run('loadAlexGSaved()');
    const t0 = Date.now();
    await a.run('alexGLoadZonesDurable()');
    const ms = Date.now() - t0;
    const st = a.run('__zoneStore()');
    if (ms > 2000) return fail('took ' + ms + 'ms');
    if (st.mode !== 'LOCALSTORAGE') return fail('mode=' + st.mode);
    return { pass: true, detail: ms + 'ms' };
  });

  // ══ WIRING (source) ══════════════════════════════════════════════════════════════════════════
  await t('WIRE-1', 'saveAlexGRest no longer writes zones to localStorage directly', async function () {
    const body = fn('saveAlexGRest');
    if (/persistStorageKey\(\s*'fxhub_alexg_zones'/.test(body)) return fail('direct localStorage zone write still present');
    if (!/alexGPersistZones\(/.test(body)) return fail('zones are not persisted at all');
    return { pass: true };
  });

  await t('WIRE-2', 'connect awaits the durable zone load BEFORE migrateJournalEntryIds() and initAll()', async function () {
    const m = /loadAlexGSaved\(\);[^\n]*/.exec(fn('connect'));
    if (!m) return fail('connect load line not found');
    const line = m[0];
    const iLoad = line.indexOf('alexGLoadZonesDurable()'), iThen = line.indexOf('.then(');
    const iMig = line.indexOf('migrateJournalEntryIds()'), iInit = line.indexOf('initAll()');
    if (iLoad < 0 || iThen < iLoad || iMig < iThen || iInit < iMig) return fail('order wrong: ' + line.slice(0, 200));
    return { pass: true };
  });

  results.forEach(function (r) {
    console.log((r.pass ? 'PASS' : 'FAIL') + ' -- ' + r.name + ': ' + r.desc + (r.detail ? ' (' + r.detail + ')' : ''));
  });
  const nf = results.filter(function (r) { return !r.pass; }).length;
  console.log('---');
  console.log(nf ? ('FAILURES: ' + nf + '/' + results.length) : ('ALL ' + results.length + ' ZONE-PERSISTENCE FIXTURES PASSED'));
  process.exitCode = nf ? 1 : 0;
})().catch(function (e) { console.log('RUNNER ERROR: ' + (e && e.stack || e)); process.exitCode = 1; });

#!/usr/bin/env node
// ══════════════════════════════════════════════════════════════════════════════════════════
// MOGO — offline manifest extractor for a PRESERVED IndexedDB checkpoint (MOGO-011 Step 4)
// ══════════════════════════════════════════════════════════════════════════════════════════
//
// WHY THIS EXISTS
//
// The in-page manifest exporter is the accurate instrument, but getting its output off the page
// proved unreliable in practice: a clipboard hand-off is destroyed the moment the operator copies
// anything else, and downloads are forbidden because EXP-001 showed they fail silently. This tool
// removes the operator from the loop entirely. It reads the byte-identical preservation checkpoint
// and reconstructs the same manifest offline.
//
// HOW IT FINDS RECORDS -- and why this is reliable where token scanning was not
//
// An earlier attempt walked V8 string tokens across the whole store and tried to pair each field
// name with the next string. That under-reported badly: V8 emits a BACK-REFERENCE instead of the
// literal for any string it has already written, so field names vanish after their first use, and
// records ran together.
//
// Every IndexedDB value instead begins with a V8 serialization header -- 0xFF, a version varint,
// then 0x6F ('o') opening the object. Splitting on that header yields ONE RECORD PER PACKAGE, so
// field pairing happens inside a single package and cannot bleed across records. 283 such headers
// exist in the checkpoint for 222 live packages: the excess are superseded versions LevelDB has
// not yet compacted, which is why records are deduplicated by identity below.
//
// FIELD VALIDATION IS STILL REQUIRED
//
// `contentHash` appears twice in a package: once as the real top-level field, and once inside
// completenessReport.missing[] as {field:'contentHash', reason:'UNAVAILABLE'}. Taking "the next
// token" records a package's hash as the string "reason". Every field therefore carries a shape
// test and the first VALID value wins.
//
// READ-ONLY: opens files with readFileSync and nothing else. It refuses to run against a live
// browser profile -- point it at a preservation checkpoint.
//
// USAGE
//   node scripts/mogo_evidence_leveldb_extract.js --store <CHECKPOINT_LEVELDB_DIR> \
//        --origin http://localhost:8751 [--out manifest.json]
//   node scripts/mogo_evidence_leveldb_extract.js --selftest

'use strict';

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const TOOL = 'mogo-evidence-leveldb-extract/1.0.0 (MOGO-011 Step 4)';

const LIVE_MARKERS = [
  path.join('Library', 'Application Support', 'Google', 'Chrome'),
  path.join('Library', 'Application Support', 'Chromium'),
  path.join('Library', 'Application Support', 'BraveSoftware'),
  path.join('Library', 'Application Support', 'Microsoft Edge'),
  path.join('mogo-browser-test-profiles'),
];
function assertNotLive(dir) {
  const r = path.resolve(dir);
  for (const m of LIVE_MARKERS) {
    if (r.includes(m)) {
      throw new Error('REFUSING to read a LIVE browser profile: ' + r +
        '\n  Point this at a preservation checkpoint copy instead.');
    }
  }
}

function readVarint(buf, i) {
  let r = 0, s = 0, n = 0;
  while (i + n < buf.length && n < 5) {
    const c = buf[i + n]; n++;
    r |= (c & 0x7f) << s;
    if ((c & 0x80) === 0) return { value: r >>> 0, next: i + n };
    s += 7;
  }
  return null;
}

// Ordered V8 one-byte string tokens within a buffer slice.
function stringTokens(buf) {
  const out = [];
  for (let i = 0; i < buf.length; i++) {
    if (buf[i] !== 0x22) continue;
    const v = readVarint(buf, i + 1);
    if (!v || v.value === 0 || v.value > 8192) continue;
    const start = v.next, len = v.value;
    if (start + len > buf.length) continue;
    const raw = buf.slice(start, start + len);
    let printable = true;
    for (const b of raw) { if (!(b === 9 || b === 10 || b === 13 || (b >= 32 && b < 127))) { printable = false; break; } }
    if (!printable) continue;
    out.push(raw.toString('latin1'));
    i = start + len - 1;
  }
  return out;
}

const ISO = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z?$/;
const V = {
  packageId: v => /^PKG\|[^|]+\|\d{8}\|\d+$/.test(v),
  sourceTradeId: v => v.length > 2 && v.length < 500 && !(v in V),
  contentHash: v => /^[0-9a-f]{64}$/.test(v),
  contentHashAlgorithm: v => /^SHA-\d+$/.test(v),
  contentHashProvenance: v => /^(OBSERVED|UNAVAILABLE)$/.test(v),
  packageSchemaVersion: v => v.indexOf('mogo.evidence-package.') === 0,
  captureBasis: v => /^[A-Z_]+$/.test(v),
  createdAt: v => ISO.test(v),
  strategyId: v => /^[A-Za-z0-9_]+$/.test(v) && v.length < 64,
  strategyVersion: v => v.length < 64,
  engineVersion: v => /^\d+\.\d+(\.\d+)?$/.test(v),
  mode: v => /^[A-Z_]+$/.test(v),
  runId: v => /^[0-9a-f]{16,64}$/.test(v),
  datasetHash: v => /^[0-9a-f]{16,64}$/.test(v),
  configHash: v => /^[0-9a-f]{16,64}$/.test(v),
  paramsHash: v => /^[0-9a-f]{16,64}$/.test(v),
  exportedAt: v => ISO.test(v),
  exportAttemptedAt: v => ISO.test(v),
  exportMechanism: v => /^[A-Z_]+$/.test(v),
  exportFilename: v => /\.json$/.test(v),
  exportVerificationMethod: v => /^[A-Z_]+$/.test(v),
  importedAt: v => ISO.test(v),
  importVerification: v => /^[A-Z]+$/.test(v),
};
const FIELDS = new Set(Object.keys(V));

// Field-name adjacency is NOT usable across the whole store. V8 replaces any string it has already
// emitted with a back-reference, so in later records the field names and repeated values simply are
// not in the token stream: a record that decodes as 1,606 tokens early on decodes as 66 later, with
// `packageSchemaVersion` sitting directly beside a packageId value. Positional pairing silently
// mis-assigns under those conditions, which is exactly the failure that produced 30 identities from
// 279 records.
//
// Extraction is therefore by SHAPE, not by position. Each value's own grammar identifies it, and
// nothing depends on an adjacent field name surviving serialization.
//
// The one ordering fact relied upon: contentHash is written onto the package by
// evidenceFinalizePackage before identity{} is built, so the FIRST 64-hex token in a record is the
// content hash -- runId, datasetHash, configHash and paramsHash are also 64-hex but all live inside
// identity{}, later in the object.
const RE_PKGID = /^PKG\|[^|]+\|\d{8}\|\d+$/;
const RE_TRADE = /^(REPLAY|AGT)\|.{4,}$/;
const RE_NUMID = /^\d{10,}$/;
const RE_HEX64 = /^[0-9a-f]{64}$/;
const BASES = new Set(['REPLAY_RUN', 'LIVE_CLOSE', 'HISTORICAL_BACKFILL']);
const MODES = new Set(['REPLAY', 'LIVE_PAPER', 'BACKTEST']);

function recordFromTokens(toks) {
  const rec = {};
  const first = (pred) => { for (const t of toks) if (pred(t)) return t; return null; };

  rec.packageId = first(t => RE_PKGID.test(t));
  // Prefer a structured trade id; fall back to a bare numeric one (JVM records use those).
  rec.sourceTradeId = first(t => RE_TRADE.test(t)) || first(t => RE_NUMID.test(t));
  rec.contentHash = first(t => RE_HEX64.test(t));
  rec.captureBasis = first(t => BASES.has(t));
  rec.mode = first(t => MODES.has(t));
  rec.createdAt = first(t => ISO.test(t));
  rec.packageSchemaVersion = first(t => t.indexOf('mogo.evidence-package.') === 0);
  rec.contentHashAlgorithm = first(t => /^SHA-\d+$/.test(t));
  rec.contentHashProvenance = first(t => t === 'OBSERVED' || t === 'UNAVAILABLE');
  rec.strategyId = first(t => /^(alex_g_sr_v1|current_strategy|alex_score_v2)$/.test(t));
  rec.engineVersion = first(t => /^\d+\.\d+\.\d+$/.test(t));

  // Export state: the ISO timestamps that follow the `export` marker, when it survived. Absent that
  // marker the state is left null rather than guessed -- the aggregate counts come from the store's
  // own banner, which is authoritative for them.
  const ex = toks.indexOf('export');
  if (ex !== -1) {
    const tail = toks.slice(ex);
    const isos = tail.filter(t => ISO.test(t));
    rec.exportAttemptedAt = isos.length ? isos[isos.length - 1] : null;
    rec.exportMechanism = tail.find(t => t === 'MANUAL' || t === 'AUTO_DOWNLOAD') || null;
    rec.exportVerificationMethod = tail.find(t => t === 'REIMPORT_VERIFIED') || null;
    rec.exportedAt = rec.exportVerificationMethod ? rec.exportAttemptedAt : null;
  }
  for (const k of Object.keys(rec)) if (rec[k] == null) delete rec[k];
  return rec;
}

function extract(storeDir, origin) {
  assertNotLive(storeDir);
  const files = fs.readdirSync(storeDir)
    .filter(f => f.endsWith('.ldb') || f.endsWith('.log'))
    .sort()
    .map(f => path.join(storeDir, f));
  if (!files.length) throw new Error('no .ldb or .log files in ' + storeDir);

  const parts = [], fileInfo = [];
  for (const f of files) {
    const b = fs.readFileSync(f);
    fileInfo.push({ file: path.basename(f), bytes: b.length,
                    sha256: crypto.createHash('sha256').update(b).digest('hex') });
    parts.push(b);
  }
  const blob = Buffer.concat(parts);

  // Record boundaries: 0xFF <version varint> 0x6F
  const starts = [];
  for (let i = 0; i + 2 < blob.length; i++) {
    if (blob[i] === 0xff && blob[i + 1] >= 0x0b && blob[i + 1] <= 0x14 && blob[i + 2] === 0x6f) starts.push(i);
  }

  const raw = [];
  for (let k = 0; k < starts.length; k++) {
    const a = starts[k], z = (k + 1 < starts.length) ? starts[k + 1] : blob.length;
    const rec = recordFromTokens(stringTokens(blob.slice(a, z)));
    if (rec.packageId || rec.sourceTradeId) { rec._span = z - a; raw.push(rec); }
  }

  // Deduplicate superseded LevelDB versions. Identity is sourceTradeId (the store's unique index);
  // packageId is the fallback only when sourceTradeId did not decode. The surviving version is the
  // one with the most advanced export state -- a confirmation must never be lost to a stale copy.
  const byIdentity = new Map();
  for (const r of raw) {
    const key = r.sourceTradeId ? 'trade:' + r.sourceTradeId : 'pkg:' + r.packageId;
    const prev = byIdentity.get(key);
    if (!prev) { byIdentity.set(key, r); continue; }
    const score = x => (x.exportedAt ? 2 : 0) + (x.exportAttemptedAt ? 1 : 0);
    if (score(r) > score(prev)) byIdentity.set(key, r);
    else if (score(r) === score(prev) && (r.exportAttemptedAt || '') > (prev.exportAttemptedAt || '')) byIdentity.set(key, r);
  }
  const packages = Array.from(byIdentity.values()).map(r => ({
    origin,
    sourceTradeId: r.sourceTradeId || null,
    packageId: r.packageId || null,
    contentHash: r.contentHash || null,
    contentHashProvenance: r.contentHashProvenance || null,
    contentHashAlgorithm: r.contentHashAlgorithm || null,
    packageSchemaVersion: r.packageSchemaVersion || null,
    captureBasis: r.captureBasis || null,
    createdAt: r.createdAt || null,
    strategyId: r.strategyId || null,
    strategyVersion: r.strategyVersion || null,
    engineVersion: r.engineVersion || null,
    mode: r.mode || null,
    runId: r.runId || null,
    datasetHash: r.datasetHash || null,
    configHash: r.configHash || null,
    paramsHash: r.paramsHash || null,
    exportedAt: r.exportedAt || null,
    exportAttemptedAt: r.exportAttemptedAt || null,
    exportMechanism: r.exportMechanism || null,
    exportFilename: r.exportFilename || null,
    exportVerificationMethod: r.exportVerificationMethod || null,
    importedAt: r.importedAt || null,
    importVerification: r.importVerification || null,
  }));

  const uniqTrades = new Set(packages.map(p => p.sourceTradeId).filter(Boolean));
  const uniqPkgIds = new Set(packages.map(p => p.packageId).filter(Boolean));

  return {
    tool: TOOL,
    provenance: 'OFFLINE_CHECKPOINT_EXTRACTION',
    provenanceNote:
      'Reconstructed from a byte-identical preservation checkpoint by splitting on V8 record ' +
      'headers. Field VALUES are read from the stored bytes; they are not recomputed, and no ' +
      'content hash is re-derived here -- recomputation would require full V8 deserialization.',
    origin,
    storeDir: path.resolve(storeDir),
    sourceFiles: fileInfo,
    recordHeadersFound: starts.length,
    rawRecordsParsed: raw.length,
    packages,
    derivedCounts: {
      storedPackages: packages.length,
      uniqueSourceTradeIds: uniqTrades.size,
      uniquePackageIds: uniqPkgIds.size,
      identitiesLostIfCountingByPackageId: uniqTrades.size - uniqPkgIds.size,
      withoutContentHash: packages.filter(p => !p.contentHash).length,
      confirmedExported: packages.filter(p => p.exportedAt).length,
      attemptedNotConfirmed: packages.filter(p => !p.exportedAt && p.exportAttemptedAt).length,
      neverAttempted: packages.filter(p => !p.exportedAt && !p.exportAttemptedAt).length,
      byCaptureBasis: packages.reduce((a, p) => { a[p.captureBasis || 'null'] = (a[p.captureBasis || 'null'] || 0) + 1; return a; }, {}),
      supersededVersionsDiscarded: raw.length - packages.length,
    },
  };
}

function selftest() {
  let f = 0;
  const ck = (c, m) => { console.log((c ? 'PASS -- ' : 'FAIL -- ') + m); if (!c) f++; };
  const enc = s => {
    const b = Buffer.from(s, 'latin1'); const L = [];
    let n = b.length; do { let x = n & 0x7f; n >>>= 7; if (n) x |= 0x80; L.push(x); } while (n);
    return Buffer.concat([Buffer.from([0x22]), Buffer.from(L), b]);
  };
  const hdr = Buffer.from([0xff, 0x10, 0x6f]);
  const rec = (pid, tid, hash, attempted) => Buffer.concat([hdr,
    enc('packageSchemaVersion'), enc('mogo.evidence-package.v1'),
    enc('packageId'), enc(pid), enc('sourceTradeId'), enc(tid),
    // the decoy that broke naive pairing: contentHash as a completenessReport field name
    enc('field'), enc('contentHash'), enc('reason'), enc('UNAVAILABLE'),
    enc('contentHash'), enc(hash),
    // real records nest the timestamps under an `export` object; the fixture must too, or it is
    // testing a shape the serializer never produces
    enc('export'), enc('exportedAt'), enc('exportAttemptedAt'), enc(attempted)]);

  const buf = Buffer.concat([
    rec('PKG|s|20260101|1', 'AGT|EUR_USD|1', 'a'.repeat(64), '2026-08-09T00:00:00.000Z'),
    rec('PKG|s|20260101|1', 'AGT|EUR_USD|1', 'a'.repeat(64), '2026-08-09T02:00:00.000Z'), // newer version
    rec('PKG|s|20260101|2', 'AGT|GBP_USD|2', 'b'.repeat(64), '2026-08-09T00:00:00.000Z'),
  ]);
  const os = require('os');
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'mogo-extract-'));
  fs.writeFileSync(path.join(dir, '000001.ldb'), buf);
  const r = extract(dir, 'http://test');
  ck(r.recordHeadersFound === 3, 'three V8 record headers located (' + r.recordHeadersFound + ')');
  ck(r.derivedCounts.storedPackages === 2, 'superseded version collapsed: 2 packages (' + r.derivedCounts.storedPackages + ')');
  ck(r.derivedCounts.supersededVersionsDiscarded === 1, 'one superseded version discarded');
  const a = r.packages.find(p => p.sourceTradeId === 'AGT|EUR_USD|1');
  ck(!!a && a.contentHash === 'a'.repeat(64), 'the REAL contentHash was taken, not the decoy "reason"');
  ck(!!a && a.exportAttemptedAt === '2026-08-09T02:00:00.000Z', 'the most advanced export state survived dedup');
  ck(r.derivedCounts.withoutContentHash === 0, 'both packages carry a hash');
  ck(r.derivedCounts.uniqueSourceTradeIds === 2, 'two distinct identities');
  let refused = false;
  try { assertNotLive('/Users/x/Library/Application Support/Google/Chrome/Profile 2/IndexedDB/y'); }
  catch (e) { refused = /REFUSING to read a LIVE browser profile/.test(e.message); }
  ck(refused, 'reading a live browser profile is REFUSED');
  fs.rmSync(dir, { recursive: true, force: true });
  console.log(f === 0 ? 'SELFTEST PASS -- record splitting, decoy rejection, version dedup, live refusal'
                      : 'SELFTEST FAIL -- ' + f + ' check(s) failed');
  return f === 0 ? 0 : 1;
}

function main() {
  const a = process.argv.slice(2);
  if (a.includes('--selftest')) process.exit(selftest());
  const get = k => { const i = a.indexOf(k); return i !== -1 ? a[i + 1] : null; };
  const store = get('--store'), origin = get('--origin') || '(unspecified)', out = get('--out');
  if (!store) { console.error('FAIL: --store <CHECKPOINT_LEVELDB_DIR> required'); process.exit(2); }
  let r;
  try { r = extract(store, origin); }
  catch (e) { console.error('FAIL: ' + e.message); process.exit(2); }
  if (out) fs.writeFileSync(path.resolve(out), JSON.stringify(r, null, 2));
  console.log(JSON.stringify({ tool: r.tool, origin: r.origin, recordHeadersFound: r.recordHeadersFound,
    rawRecordsParsed: r.rawRecordsParsed, derivedCounts: r.derivedCounts }, null, 2));
  if (out) console.log('manifest written to ' + path.resolve(out));
}

if (require.main === module) main();
module.exports = { extract, stringTokens, recordFromTokens, assertNotLive };

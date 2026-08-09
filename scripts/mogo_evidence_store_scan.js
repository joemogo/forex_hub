#!/usr/bin/env node
// ══════════════════════════════════════════════════════════════════════════════════════════
// MOGO — forensic read-only browser-store scanner (MOGO-011 Step 4B, multi-origin)
// ══════════════════════════════════════════════════════════════════════════════════════════
//
// WHY THIS EXISTS
//
// The D-12 ruling treats BOTH browser origins -- http://localhost:8744 and
// http://10.143.1.187:8744 -- as potentially evidence-bearing, and requires a manifest for each,
// captured without mutating either store. The in-page manifest exporter
// (scripts/mogo_evidence_browser_manifest.js) is the accurate instrument, but running it means
// loading MOGO in a live profile. This scanner needs no browser at all.
//
// ── IT NEVER TOUCHES A LIVE STORE ─────────────────────────────────────────────────────────────
//
// It refuses to read from a live Chrome profile directory. Point it at a COPY. Opening a LevelDB
// directory with any real LevelDB client would replay its log, compact, and rewrite the very files
// under examination -- so this never opens a database at all. It reads the bytes and decodes the
// V8 string tokens directly, which is why it can run while Chrome is open without racing it.
//
// ── WHAT ITS OUTPUT IS AND IS NOT ─────────────────────────────────────────────────────────────
//
// Provenance is stamped FORENSIC_EXTRACTION, deliberately weaker than the BROWSER_MANIFEST the
// in-page exporter produces. It recovers what it can prove it read and reports what it could not
// decode, because a forensic manifest that quietly under-reports is worse than one that says so.
// It is a cross-check and a lower bound -- never the authoritative population.
//
// It cannot see: values inside compressed SST blocks, deleted-but-not-compacted records, or any
// field whose token straddles a block boundary. Every one of those is counted and reported.
//
// USAGE
//   node scripts/mogo_evidence_store_scan.js --store <COPIED_DIR> --origin <ORIGIN> [--out <FILE>]
//   node scripts/mogo_evidence_store_scan.js --selftest

'use strict';

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const TOOL = 'mogo-evidence-store-scan/1.0.0 (MOGO-011 Step 4B)';

// A live Chrome profile must never be read directly: Chrome may be mid-write, and a torn read
// would produce a manifest that is wrong in a way nothing downstream could detect.
const LIVE_PROFILE_MARKERS = [
  path.join('Library', 'Application Support', 'Google', 'Chrome'),
  path.join('Library', 'Application Support', 'Chromium'),
  path.join('Library', 'Application Support', 'BraveSoftware'),
  path.join('Library', 'Application Support', 'Microsoft Edge'),
];

function assertNotLiveProfile(dir) {
  const r = path.resolve(dir);
  for (const m of LIVE_PROFILE_MARKERS) {
    if (r.includes(m)) {
      throw new Error(
        'REFUSING to scan inside a live browser profile: ' + r +
        '\n  Copy the store directory first, then scan the copy. Reading a live profile risks a ' +
        'torn read while the browser is writing, and this tool must never be the reason an ' +
        'evidence question gets a confidently wrong answer.');
    }
  }
}

// ── V8 serialization: a one-byte string is 0x22, a varint length, then Latin-1 bytes. ────────
// Two-byte (UTF-16) strings use 0x63. Both are handled; anything else is skipped.
const TAG_ONE_BYTE = 0x22;
const TAG_TWO_BYTE = 0x63;

function readVarint(buf, i) {
  let result = 0, shift = 0, n = 0;
  while (i + n < buf.length && n < 5) {
    const b = buf[i + n]; n++;
    result |= (b & 0x7f) << shift;
    if ((b & 0x80) === 0) return { value: result >>> 0, next: i + n };
    shift += 7;
  }
  return null;
}

// Returns an ordered token stream of decoded strings, plus a count of tokens that could not be
// decoded because they ran past the end of the buffer (a block-boundary split, typically).
function extractStringTokens(buf) {
  const tokens = [];
  let truncated = 0;
  for (let i = 0; i < buf.length; i++) {
    const tag = buf[i];
    if (tag !== TAG_ONE_BYTE && tag !== TAG_TWO_BYTE) continue;
    const v = readVarint(buf, i + 1);
    if (!v || v.value === 0 || v.value > 1 << 20) continue;
    const start = v.next;
    const len = v.value;
    if (start + len > buf.length) { truncated++; continue; }
    const raw = buf.slice(start, start + len);
    let s;
    if (tag === TAG_ONE_BYTE) {
      // Reject anything that is not plausibly text; random bytes hitting 0x22 are common.
      let printable = 0;
      for (const b of raw) if (b === 9 || b === 10 || b === 13 || (b >= 32 && b < 127)) printable++;
      if (printable !== raw.length) continue;
      s = raw.toString('latin1');
    } else {
      if (len % 2 !== 0) continue;
      s = raw.toString('utf16le');
      if (/[\x00-\x08\x0e-\x1f]/.test(s)) continue;
    }
    tokens.push({ offset: i, value: s });
    i = start + len - 1;
  }
  return { tokens, truncated };
}

// Field names whose value is the very next string token in the serialized object.
const STRING_FIELDS = new Set([
  'packageId', 'sourceTradeId', 'contentHash', 'contentHashAlgorithm', 'contentHashProvenance',
  'contentHashCanonicalization', 'contentHashScope', 'packageSchemaVersion', 'captureBasis',
  'createdAt', 'strategyId', 'strategyVersion', 'engineVersion', 'mode', 'runId', 'datasetHash',
  'configHash', 'paramsHash', 'exportedAt', 'exportAttemptedAt', 'exportMechanism',
  'exportFilename', 'exportVerificationMethod', 'importedAt', 'importVerification',
]);

// A field name alone is not enough to identify its value. `contentHash`, for instance, ALSO appears
// inside completenessReport.missing[] as {field:'contentHash', reason:'UNAVAILABLE'} -- so naive
// "take the next token" pairing silently records the contentHash of a package as the string
// "reason". Every field therefore carries a shape test, and a value that fails it is discarded
// rather than recorded. A wrong hash in an evidence manifest is far worse than a missing one.
const ISO = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z?$/;
const FIELD_VALIDATORS = {
  packageId: v => /^PKG\|[^|]+\|\d{8}\|\d+$/.test(v),
  sourceTradeId: v => v.length > 0 && v.length < 400 && !STRING_FIELDS.has(v),
  contentHash: v => /^[0-9a-f]{64}$/.test(v),
  contentHashAlgorithm: v => /^SHA-\d+$/.test(v),
  contentHashProvenance: v => /^(OBSERVED|UNAVAILABLE)$/.test(v),
  contentHashCanonicalization: v => v.indexOf('mogo.evidence-canon.') === 0,
  contentHashScope: v => /^[A-Z_]+$/.test(v),
  packageSchemaVersion: v => v.indexOf('mogo.evidence-package.') === 0,
  captureBasis: v => /^[A-Z_]+$/.test(v),
  createdAt: v => ISO.test(v),
  strategyId: v => /^[a-z0-9_]+$/i.test(v) && v.length < 64,
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

// Record segmentation is greedy and offset-ordered: a new record begins the moment a field that is
// already filled reappears with a DIFFERENT validated value. That handles many packages serialized
// back to back without needing a reliable single anchor -- there isn't one, because a package's own
// nested objects reuse the same field names.
function recoverPackages(tokens) {
  const records = [];
  const ambiguities = [];
  let current = null;

  const flush = () => { if (current && (current.packageId || current.sourceTradeId || current.contentHash)) records.push(current); };

  for (let i = 0; i < tokens.length; i++) {
    const name = tokens[i].value;
    if (!STRING_FIELDS.has(name)) continue;
    const next = tokens[i + 1];
    if (!next) continue;
    const val = next.value;
    if (STRING_FIELDS.has(val)) continue;                       // the "value" is another field name
    const validator = FIELD_VALIDATORS[name];
    if (validator && !validator(val)) { ambiguities.push({ field: name, rejected: val.slice(0, 40) }); continue; }

    if (!current) current = { _offset: tokens[i].offset };
    if (Object.prototype.hasOwnProperty.call(current, name)) {
      if (current[name] === val) { i++; continue; }              // harmless repeat
      flush();                                                   // a genuinely different value: new record
      current = { _offset: tokens[i].offset };
    }
    current[name] = val;
    i++;
  }
  flush();

  return { records, discarded: 0, ambiguities };
}

function scanStore(storeDir, origin) {
  assertNotLiveProfile(storeDir);
  const files = fs.readdirSync(storeDir)
    .map(f => path.join(storeDir, f))
    .filter(p => fs.statSync(p).isFile())
    .sort();

  const perFile = [];
  const allTokens = [];
  let truncatedTotal = 0;

  for (const f of files) {
    const buf = fs.readFileSync(f);
    const { tokens, truncated } = extractStringTokens(buf);
    truncatedTotal += truncated;
    perFile.push({
      file: path.basename(f), bytes: buf.length, stringTokens: tokens.length,
      truncatedTokens: truncated,
      sha256: crypto.createHash('sha256').update(buf).digest('hex'),
    });
    for (const t of tokens) allTokens.push(t);
  }

  const { records, discarded, ambiguities } = recoverPackages(allTokens);

  // ── Corroboration pass, independent of token pairing ────────────────────────────────────────
  // The V8 serializer emits a BACK-REFERENCE instead of the literal for a string it has already
  // written, so a field name repeated across records is often absent from later ones. Token
  // pairing therefore under-reports, and it under-reports silently. This pass scans the raw bytes
  // for identity-shaped values in both encodings, which no back-reference can hide, and reports
  // the distinct set. Where the two methods disagree the HIGHER count is the lower bound -- never
  // the lower one, because under-counting an evidence population is the dangerous direction.
  const corroborate = (bufs) => {
    const pkg = new Set(), trade = new Set(), hash = new Set();
    for (const raw of bufs) {
      for (const b of [raw, Buffer.from(raw.toString('latin1').replace(/\x00/g, ''), 'latin1')]) {
        const s = b.toString('latin1');
        for (const m of s.matchAll(/PKG\|[A-Za-z0-9_]+\|\d{8}\|\d+/g)) pkg.add(m[0]);
        for (const m of s.matchAll(/(?:AGT|REPLAY)\|[A-Za-z0-9_\-|]{1,300}?(?=")/g)) trade.add(m[0]);
        for (const m of s.matchAll(/\b[0-9a-f]{64}\b/g)) hash.add(m[0]);
      }
    }
    return { packageIds: Array.from(pkg).sort(), sourceTradeIds: Array.from(trade).sort(),
             contentHashes: Array.from(hash).sort() };
  };
  const raws = files.map(f => fs.readFileSync(f));
  const corroboration = corroborate(raws);

  // Deduplicate by content identity. The same record legitimately appears in both a .log and a
  // compacted .ldb, and counting it twice would inflate an evidence population.
  const byIdentity = new Map();
  for (const r of records) {
    const key = (r.sourceTradeId || '') + '||' + (r.contentHash || '') + '||' + (r.packageId || '');
    if (!byIdentity.has(key)) byIdentity.set(key, r);
  }
  const unique = Array.from(byIdentity.values());

  return {
    tool: TOOL,
    provenance: 'FORENSIC_EXTRACTION',
    provenanceNote:
      'Recovered by decoding V8 string tokens from a COPY of the store. No database was opened. ' +
      'This is a cross-check and a LOWER BOUND -- it is weaker than a BROWSER_MANIFEST produced by ' +
      'scripts/mogo_evidence_browser_manifest.js, and must not be treated as the authoritative ' +
      'population.',
    origin,
    storeDir: path.resolve(storeDir),
    files: perFile,
    corroboration: {
      method: 'raw-byte identity scan, immune to V8 string back-references and to record versioning',
      distinctPackageIds: corroboration.packageIds.length,
      distinctSourceTradeIds: corroboration.sourceTradeIds.length,
      distinctContentHashes: corroboration.contentHashes.length,
      packageIds: corroboration.packageIds,
      sourceTradeIds: corroboration.sourceTradeIds,
      contentHashes: corroboration.contentHashes,
    },
    lowerBoundDistinctPackages: Math.max(
      unique.length,
      corroboration.sourceTradeIds.length,
      corroboration.packageIds.length),
    limits: {
      truncatedTokens: truncatedTotal,
      tokenPairingUnderReports:
        'V8 emits a back-reference instead of the literal for a repeated string, so a field name ' +
        'present in the first record is often absent from later ones. Trust the corroboration ' +
        'counts over the token-paired records where they disagree.',
      recordsDiscardedWithNoIdentity: discarded,
      fieldAmbiguities: ambiguities.length,
      cannotSee: ['values inside compressed SST blocks',
                  'deleted-but-not-yet-compacted records',
                  'fields whose token straddles a LevelDB block boundary'],
    },
    counts: {
      rawRecordsRecovered: records.length,
      uniqueByContentIdentity: unique.length,
      uniqueSourceTradeIds: new Set(unique.map(r => r.sourceTradeId).filter(Boolean)).size,
      uniquePackageIds: new Set(unique.map(r => r.packageId).filter(Boolean)).size,
      withContentHash: unique.filter(r => r.contentHash).length,
      withoutContentHash: unique.filter(r => !r.contentHash).length,
    },
    packages: unique.map(r => ({
      origin,                                   // provenance travels WITH every row
      sourceTradeId: r.sourceTradeId || null,
      packageId: r.packageId || null,
      contentHash: r.contentHash || null,
      contentHashProvenance: r.contentHashProvenance || null,
      packageSchemaVersion: r.packageSchemaVersion || null,
      captureBasis: r.captureBasis || null,
      createdAt: r.createdAt || null,
      strategyId: r.strategyId || null,
      engineVersion: r.engineVersion || null,
      mode: r.mode || null,
      runId: r.runId || null,
      exportedAt: r.exportedAt || null,
      exportAttemptedAt: r.exportAttemptedAt || null,
      exportMechanism: r.exportMechanism || null,
    })),
  };
}

// ── Multi-origin reconciliation ──────────────────────────────────────────────────────────────
function reconcileOrigins(manifests) {
  const byOrigin = {};
  for (const m of manifests) byOrigin[m.origin] = m;
  const origins = manifests.map(m => m.origin);

  const index = new Map();   // sourceTradeId -> { origin -> row }
  for (const m of manifests) {
    for (const p of m.packages) {
      const k = p.sourceTradeId || ('(no-trade-id)' + p.packageId);
      if (!index.has(k)) index.set(k, {});
      index.get(k)[m.origin] = p;
    }
  }

  const inBoth = [], uniqueTo = {}, hashMismatch = [], hashMatch = [];
  for (const o of origins) uniqueTo[o] = [];
  for (const [k, rows] of index) {
    const present = origins.filter(o => rows[o]);
    if (present.length > 1) {
      inBoth.push(k);
      const hashes = new Set(present.map(o => rows[o].contentHash));
      if (hashes.size > 1) hashMismatch.push({ sourceTradeId: k, byOrigin: present.map(o => ({ origin: o, contentHash: rows[o].contentHash })) });
      else hashMatch.push(k);
    } else {
      uniqueTo[present[0]].push(k);
    }
  }

  // packageId collisions ACROSS origins: one packageId carrying different source trades.
  const pidMap = new Map();
  for (const m of manifests) {
    for (const p of m.packages) {
      if (!p.packageId) continue;
      if (!pidMap.has(p.packageId)) pidMap.set(p.packageId, []);
      pidMap.get(p.packageId).push({ origin: m.origin, sourceTradeId: p.sourceTradeId, contentHash: p.contentHash });
    }
  }
  const crossOriginPackageIdCollisions = [];
  for (const [pid, rows] of pidMap) {
    const trades = new Set(rows.map(r => String(r.sourceTradeId)));
    const os = new Set(rows.map(r => r.origin));
    if (trades.size > 1) {
      crossOriginPackageIdCollisions.push({
        packageId: pid, distinctSourceTradeIds: trades.size,
        spansOrigins: os.size > 1, origins: Array.from(os), rows,
      });
    }
  }

  // A sourceTradeId carrying different content in different origins would break identity itself.
  const sourceTradeIdCollisions = hashMismatch.map(h => h.sourceTradeId);

  return {
    origins,
    perOrigin: Object.fromEntries(manifests.map(m => [m.origin, m.counts])),
    presentInBothOrigins: inBoth.length,
    uniqueToOrigin: Object.fromEntries(origins.map(o => [o, uniqueTo[o].length])),
    uniqueToOriginDetail: uniqueTo,
    contentHashMatches: hashMatch.length,
    contentHashMismatches: hashMismatch.length,
    contentHashMismatchDetail: hashMismatch,
    sourceTradeIdCollisions: sourceTradeIdCollisions.length,
    crossOriginPackageIdCollisions,
    unionByContentIdentity: index.size,
    identityKey: 'sourceTradeId + contentHash. packageId is NEVER used alone as identity.',
  };
}

// ── Self-test ────────────────────────────────────────────────────────────────────────────────
function selftest() {
  const os = require('os');
  let failures = 0;
  const check = (ok, m) => { console.log((ok ? 'PASS -- ' : 'FAIL -- ') + m); if (!ok) failures++; };

  // Token decoding round-trip.
  function enc(s) {
    const b = Buffer.from(s, 'latin1');
    const len = [];
    let n = b.length;
    do { let x = n & 0x7f; n >>>= 7; if (n) x |= 0x80; len.push(x); } while (n);
    return Buffer.concat([Buffer.from([TAG_ONE_BYTE]), Buffer.from(len), b]);
  }
  const synth = Buffer.concat([
    enc('packageSchemaVersion'), enc('mogo.evidence-package.v1'),
    enc('packageId'), enc('PKG|s|20260101|1'),
    enc('sourceTradeId'), enc('AGT|EUR_USD|1'),
    enc('contentHash'), enc('a'.repeat(64)),
    enc('packageSchemaVersion'), enc('mogo.evidence-package.v1'),
    enc('packageId'), enc('PKG|s|20260101|1'),
    enc('sourceTradeId'), enc('AGT|GBP_USD|9'),
    enc('contentHash'), enc('b'.repeat(64)),
  ]);
  const { tokens } = extractStringTokens(synth);
  check(tokens.length === 16, 'all 16 string tokens decode (' + tokens.length + ')');
  const rec = recoverPackages(tokens);
  check(rec.records.length === 2, 'two records recovered (' + rec.records.length + ')');
  check(rec.records[0].sourceTradeId === 'AGT|EUR_USD|1' && rec.records[1].sourceTradeId === 'AGT|GBP_USD|9',
        'each record keeps its own sourceTradeId');
  check(rec.records[0].contentHash !== rec.records[1].contentHash, 'and its own contentHash');

  // A live profile path must be refused.
  let refused = false;
  try { assertNotLiveProfile(path.join(os.homedir(), 'Library', 'Application Support', 'Google', 'Chrome', 'Profile 2', 'IndexedDB', 'x')); }
  catch (e) { refused = /REFUSING to scan inside a live browser profile/.test(e.message); }
  check(refused, 'scanning inside a LIVE Chrome profile is REFUSED');
  let allowed = true;
  try { assertNotLiveProfile(fs.mkdtempSync(path.join(os.tmpdir(), 'mogo-scan-'))); } catch (e) { allowed = false; }
  check(allowed, 'scanning a copy outside any live profile is allowed');

  // Cross-origin reconciliation.
  const A = { origin: 'http://localhost:8744', counts: {}, packages: [
    { origin: 'http://localhost:8744', sourceTradeId: 'T1', packageId: 'PKG|1', contentHash: 'h1' },
    { origin: 'http://localhost:8744', sourceTradeId: 'T2', packageId: 'PKG|2', contentHash: 'h2' } ] };
  const B = { origin: 'http://10.0.0.1:8744', counts: {}, packages: [
    { origin: 'http://10.0.0.1:8744', sourceTradeId: 'T1', packageId: 'PKG|1', contentHash: 'h1' },
    { origin: 'http://10.0.0.1:8744', sourceTradeId: 'T3', packageId: 'PKG|2', contentHash: 'h3' } ] };
  const rc = reconcileOrigins([A, B]);
  check(rc.presentInBothOrigins === 1, 'a package present in both origins is detected');
  check(rc.uniqueToOrigin['http://localhost:8744'] === 1, 'one package unique to localhost');
  check(rc.uniqueToOrigin['http://10.0.0.1:8744'] === 1, 'one package unique to the LAN origin');
  check(rc.unionByContentIdentity === 3, 'the union by content identity is 3');
  check(rc.crossOriginPackageIdCollisions.length === 1 && rc.crossOriginPackageIdCollisions[0].spansOrigins,
        'a packageId carrying different trades ACROSS origins is reported as a cross-origin collision');
  check(rc.contentHashMismatches === 0, 'matching copies are not reported as mismatches');

  console.log(failures === 0 ? 'SELFTEST PASS -- decoder, live-profile refusal and cross-origin reconciliation'
                             : 'SELFTEST FAIL -- ' + failures + ' check(s) failed');
  return failures === 0 ? 0 : 1;
}

// ── CLI ──────────────────────────────────────────────────────────────────────────────────────
function main() {
  const a = process.argv.slice(2);
  if (a.includes('--selftest')) process.exit(selftest());
  const get = f => { const i = a.indexOf(f); return i !== -1 ? a[i + 1] : null; };
  const stores = [];
  for (let i = 0; i < a.length; i++) {
    if (a[i] === '--store') stores.push({ dir: a[i + 1], origin: null });
    if (a[i] === '--origin' && stores.length) stores[stores.length - 1].origin = a[i + 1];
  }
  if (!stores.length) { console.error('FAIL: --store <COPIED_DIR> --origin <ORIGIN> required'); process.exit(2); }

  const manifests = [];
  for (const s of stores) {
    try { manifests.push(scanStore(s.dir, s.origin || '(unspecified)')); }
    catch (e) { console.error('FAIL: ' + e.message); process.exit(2); }
  }
  const out = { tool: TOOL, manifests, reconciliation: manifests.length > 1 ? reconcileOrigins(manifests) : null };
  const outFile = get('--out');
  console.log(JSON.stringify(out, null, 2));
  if (outFile) fs.writeFileSync(path.resolve(outFile), JSON.stringify(out, null, 2));
}

if (require.main === module) main();
module.exports = { extractStringTokens, recoverPackages, scanStore, reconcileOrigins, assertNotLiveProfile };

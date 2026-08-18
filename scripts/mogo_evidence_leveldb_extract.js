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

// ══════════════════════════════════════════════════════════════════════════════════════════
// M-7 / M-6: FULL RECONSTRUCTION AND INDEPENDENT HASH RE-DERIVATION
// ══════════════════════════════════════════════════════════════════════════════════════════
//
// Everything above reads FIELD VALUES out of the stored bytes. That answers "what does the store
// say", which is not the same question as "is what the store says true". This section answers the
// second one: it rebuilds each package as a real JavaScript object and RE-DERIVES its content hash
// from scratch, so the hash is confirmed rather than quoted.
//
// Step 4 recorded this as blocked -- "requires full V8 deserialization of ~27 KB objects". It is
// not blocked; it needs three things the earlier reader lacked.
//
//   1. THE CONTAINER. Values do not lie loose in the file. A .log is a write-ahead log framed in
//      32 KB blocks with 7-byte record headers, and a .ldb is an SSTable whose data blocks are
//      Snappy-compressed. Scanning raw bytes therefore finds only the records that happen to sit
//      uncompressed and unfragmented -- which is why the earlier reader saw a fraction of them.
//   2. SNAPPY. Implemented here in ~30 lines rather than taken as a dependency; an evidence tool
//      should not acquire a supply chain.
//   3. A V8 VERSION BRIDGE. Chrome writes ValueSerializer format 16; Node reads up to 15. For the
//      pure-data payloads a package consists of, the two wire formats are identical, so the
//      version byte is retargeted.
//
// THE VERSION BRIDGE REQUIRES NO TRUST, AND THIS IS THE WHOLE ARGUMENT. If retargeting were
// wrong -- by one byte, anywhere -- the reconstructed object would canonicalize differently and
// its SHA-256 would not match the hash the browser stored. A match is not evidence that the
// reconstruction is probably right; it is proof that it is exactly right.
//
// CANONICALIZATION IS NOT REIMPLEMENTED, for the same reason mogo_evidence_verify.js refuses to:
// a second implementation is a second source of truth, and the first time they disagree the
// evidence chain has two answers and no authority. The EXACT source text of
// EVIDENCE_HASH_EXCLUDED_FIELDS, evidenceCanonValue and evidenceCanonicalize is extracted from
// index.html and evaluated.

// ── Snappy raw-block decompression ───────────────────────────────────────────────────────────
function snappyUncompress(buf) {
  let i = 0, len = 0, s = 0;
  for (;;) { const c = buf[i++]; len |= (c & 0x7f) << s; if (!(c & 0x80)) break; s += 7; }
  const out = Buffer.alloc(len);
  let o = 0;
  while (i < buf.length && o < len) {
    const tag = buf[i++], t = tag & 0x03;
    if (t === 0) {
      let n = tag >> 2;
      if (n < 60) n += 1;
      else { const nb = n - 59; let v = 0; for (let k = 0; k < nb; k++) v |= buf[i + k] << (8 * k); i += nb; n = v + 1; }
      buf.copy(out, o, i, i + n); i += n; o += n;
    } else {
      let n, off;
      if (t === 1) { n = 4 + ((tag >> 2) & 0x07); off = ((tag >> 5) << 8) | buf[i]; i += 1; }
      else if (t === 2) { n = (tag >> 2) + 1; off = buf.readUInt16LE(i); i += 2; }
      else { n = (tag >> 2) + 1; off = buf.readUInt32LE(i); i += 4; }
      // Overlapping copies are legal and common in Snappy -- this must stay a byte loop.
      let p = o - off;
      for (let k = 0; k < n; k++) out[o++] = out[p++];
    }
  }
  return out.subarray(0, o);
}

function lvVarint(buf, i) { let r = 0, s = 0; for (;;) { const c = buf[i++]; r |= (c & 0x7f) << s; if (!(c & 0x80)) break; s += 7; } return [r, i]; }

// ── LevelDB write-ahead log: 32 KB blocks, records [crc:4][len:2 LE][type:1][payload] ────────
function readWal(buf) {
  const BLOCK = 32768, out = [];
  let frag = null;
  for (let off = 0; off < buf.length; off += BLOCK) {
    const end = Math.min(off + BLOCK, buf.length);
    let p = off;
    while (p + 7 <= end) {
      const len = buf.readUInt16LE(p + 4), type = buf[p + 6];
      if (type === 0 || len === 0 || p + 7 + len > end) break;
      const payload = buf.subarray(p + 7, p + 7 + len);
      if (type === 1) out.push(payload);
      else if (type === 2) frag = [payload];
      else if (type === 3) { if (frag) frag.push(payload); }
      else if (type === 4) { if (frag) { frag.push(payload); out.push(Buffer.concat(frag)); frag = null; } }
      p += 7 + len;
    }
  }
  return out;
}

// ── LevelDB SSTable: footer -> index block -> data blocks (Snappy where flagged) ─────────────
const SST_MAGIC = '57fb808b247547db';
function readBlockEntries(block) {
  const n = block.readUInt32LE(block.length - 4);
  const dataEnd = block.length - 4 - 4 * n;
  const out = [];
  let i = 0, prev = Buffer.alloc(0);
  while (i < dataEnd) {
    let shared, nonshared, vlen;
    [shared, i] = lvVarint(block, i); [nonshared, i] = lvVarint(block, i); [vlen, i] = lvVarint(block, i);
    const key = Buffer.concat([prev.subarray(0, shared), block.subarray(i, i + nonshared)]);
    i += nonshared;
    out.push({ key, val: block.subarray(i, i + vlen) });
    i += vlen;
    prev = key;
  }
  return out;
}
function readSst(buf) {
  const footer = buf.subarray(buf.length - 48);
  if (footer.subarray(40).toString('hex') !== SST_MAGIC) return { values: [], err: 'bad SSTable magic' };
  let i = 0, a, b, io, is;
  [a, i] = lvVarint(footer, i); [b, i] = lvVarint(footer, i); [io, i] = lvVarint(footer, i); [is, i] = lvVarint(footer, i);
  const block = (off, size) => ({ raw: buf.subarray(off, off + size), comp: buf[off + size] });
  const idx = block(io, is);
  let idxRaw;
  try { idxRaw = idx.comp === 0 ? idx.raw : snappyUncompress(idx.raw); }
  catch (e) { return { values: [], err: 'index block unreadable: ' + e.message }; }
  let handles;
  try {
    handles = readBlockEntries(idxRaw).map(e => { let x, y, j = 0;[x, j] = lvVarint(e.val, 0);[y, j] = lvVarint(e.val, j); return { off: x, size: y }; });
  } catch (e) { return { values: [], err: 'index block malformed: ' + e.message }; }
  const values = [];
  let blockFail = 0, entryFail = 0;
  for (const h of handles) {
    const bl = block(h.off, h.size);
    let raw;
    try { raw = bl.comp === 0 ? bl.raw : snappyUncompress(bl.raw); }
    catch (e) { blockFail++; continue; }
    try { for (const e of readBlockEntries(raw)) values.push(e.val); }
    catch (e) { entryFail++; }
  }
  return { values, handles: handles.length, blockFail, entryFail };
}

// ── V8 reconstruction ────────────────────────────────────────────────────────────────────────
function deserializePackage(valueBytes) {
  const v8 = require('v8');
  for (let k = 0; k + 2 < valueBytes.length; k++) {
    if (valueBytes[k] === 0xFF && valueBytes[k + 2] === 0x6F) {
      const b = Buffer.from(valueBytes.subarray(k));
      if (b[1] > 0x0F) b[1] = 0x0F;                 // format 16 -> 15; see the note above
      try {
        const o = v8.deserialize(b);
        if (o && typeof o === 'object' && o.packageId) return o;
      } catch (e) { /* not a package, or damaged -- counted by the caller */ }
      return null;
    }
  }
  return null;
}

// ── The committed canonicalizer, extracted verbatim (never reimplemented) ────────────────────
function loadCommittedCanonicalizer(indexHtmlPath) {
  const src = fs.readFileSync(indexHtmlPath, 'utf8');
  const grab = (re, label) => {
    const m = src.match(re);
    if (!m) throw new Error('could not extract ' + label + ' from ' + indexHtmlPath);
    return m[0];
  };
  const parts = [
    grab(/const EVIDENCE_HASH_EXCLUDED_FIELDS=Object\.freeze\(\[[^\]]*\]\);/, 'EVIDENCE_HASH_EXCLUDED_FIELDS'),
    grab(/function evidenceCanonValue\(v,seen\)\{[\s\S]*?\n\}/, 'evidenceCanonValue'),
    grab(/function evidenceCanonicalize\(pkg\)\{[\s\S]*?\n\}/, 'evidenceCanonicalize'),
  ];
  const g = {};
  new Function('g', parts.join('\n') + '\ng.canonicalize=evidenceCanonicalize;g.excluded=EVIDENCE_HASH_EXCLUDED_FIELDS;')(g);
  return g;
}

// ── Reconstruct every package in a checkpoint store and re-derive its hash ───────────────────
function verifyStore(storeDir, indexHtmlPath) {
  assertNotLive(storeDir);
  const canon = loadCommittedCanonicalizer(indexHtmlPath);
  const candidates = [];
  const containers = [];
  for (const f of fs.readdirSync(storeDir).sort()) {
    const p = path.join(storeDir, f);
    if (!fs.statSync(p).isFile()) continue;
    const buf = fs.readFileSync(p);
    if (/\.log$/.test(f)) { const r = readWal(buf); containers.push({ file: f, kind: 'WAL', records: r.length }); candidates.push(...r); }
    else if (/\.ldb$/.test(f)) { const r = readSst(buf); containers.push({ file: f, kind: 'SST', values: r.values.length, handles: r.handles, blockFail: r.blockFail, entryFail: r.entryFail, err: r.err }); candidates.push(...r.values); }
  }
  const pkgs = new Map();
  let withHeader = 0, undeserializable = 0;
  for (const c of candidates) {
    let hasHeader = false;
    for (let k = 0; k + 2 < c.length; k++) { if (c[k] === 0xFF && c[k + 2] === 0x6F) { hasHeader = true; break; } }
    if (!hasHeader) continue;
    withHeader++;
    const o = deserializePackage(c);
    if (!o) { undeserializable++; continue; }
    if (!pkgs.has(o.packageId)) pkgs.set(o.packageId, o);
  }
  let verified = 0, mismatched = 0, noHash = 0;
  const mismatches = [], hashes = [];
  for (const [id, p] of pkgs) {
    if (!p.contentHash) { noHash++; continue; }
    let canonical;
    try { canonical = canon.canonicalize(p); }
    catch (e) { mismatched++; mismatches.push({ packageId: id, error: e.message }); continue; }
    const h = crypto.createHash('sha256').update(Buffer.from(canonical, 'utf8')).digest('hex');
    if (h === p.contentHash) { verified++; hashes.push(h); }
    else { mismatched++; mismatches.push({ packageId: id, stored: p.contentHash, recomputed: h }); }
  }
  hashes.sort();
  const rollup = crypto.createHash('sha256').update(hashes.join('\n'), 'utf8').digest('hex');
  return {
    storeDir: path.resolve(storeDir),
    containers,
    recordsWithV8Header: withHeader,
    undeserializableRecords: undeserializable,
    packagesRecovered: pkgs.size,
    verified, mismatched, noHash,
    mismatches: mismatches.slice(0, 20),
    uniqueSourceTradeIds: new Set([...pkgs.values()].map(p => p.sourceTradeId)).size,
    schemas: [...new Set([...pkgs.values()].map(p => p.packageSchemaVersion))],
    canonicalizations: [...new Set([...pkgs.values()].map(p => p.contentHashCanonicalization))],
    algorithms: [...new Set([...pkgs.values()].map(p => p.contentHashAlgorithm))],
    packageHashes: hashes,
    hashRollup: rollup,
    // Only packages whose stored hash RE-DERIVED from the bytes. A package that
    // failed verification is deliberately absent: the import path must never be
    // fed a payload this tool could not prove it read correctly.
    verifiedPackages: [...pkgs.values()].filter(
      p => p.contentHash && hashes.includes(p.contentHash)),
  };
}

// ── Committed hash baseline ──────────────────────────────────────────────────────────────────
// The baseline is taken over the PRESERVED corpus, which is frozen and will never legitimately
// change. A live evidence store changes on every trade close and cannot have a committed content
// baseline -- rolling per-checkpoint manifests cover that, written by mogo_evidence_checkpoint.sh.
const BASELINE_VERSION = 'mogo.evidence-baseline.v1';

function buildBaseline(storeDir, indexHtmlPath, origin, checkpointLabel) {
  const v = verifyStore(storeDir, indexHtmlPath);
  const storeFiles = fs.readdirSync(storeDir).sort()
    .filter(f => fs.statSync(path.join(storeDir, f)).isFile())
    .map(f => {
      const b = fs.readFileSync(path.join(storeDir, f));
      return { file: f, bytes: b.length, sha256: crypto.createHash('sha256').update(b).digest('hex') };
    });
  return {
    baselineVersion: BASELINE_VERSION,
    tool: TOOL,
    origin: origin || null,
    checkpoint: checkpointLabel || null,
    canonicalization: v.canonicalizations,
    hashAlgorithm: v.algorithms,
    packageSchema: v.schemas,
    storeFiles,
    packagesRecovered: v.packagesRecovered,
    verified: v.verified,
    mismatched: v.mismatched,
    undeserializableRecords: v.undeserializableRecords,
    uniqueSourceTradeIds: v.uniqueSourceTradeIds,
    hashRollup: v.hashRollup,
    packageHashes: v.packageHashes,
  };
}

// FAIL CLOSED. Every discrepancy is a failure; nothing is tolerated as "close enough".
function verifyAgainstBaseline(baseline, storeDir, indexHtmlPath) {
  const problems = [];
  if (baseline.baselineVersion !== BASELINE_VERSION) problems.push('baseline version is ' + baseline.baselineVersion + ', expected ' + BASELINE_VERSION);
  const v = verifyStore(storeDir, indexHtmlPath);
  if (v.mismatched !== 0) problems.push(v.mismatched + ' package(s) failed hash re-derivation');
  if (v.verified !== baseline.verified) problems.push('verified count ' + v.verified + ' != baseline ' + baseline.verified);
  if (v.hashRollup !== baseline.hashRollup) problems.push('hash rollup ' + v.hashRollup + ' != baseline ' + baseline.hashRollup);
  const have = new Set(v.packageHashes);
  const missing = baseline.packageHashes.filter(h => !have.has(h));
  if (missing.length) problems.push(missing.length + ' baseline package hash(es) absent from the store');
  const byFile = new Map(v.containers.map(c => [c.file, c]));
  for (const sf of baseline.storeFiles || []) {
    const p = path.join(storeDir, sf.file);
    if (!fs.existsSync(p)) { problems.push('store file missing: ' + sf.file); continue; }
    const b = fs.readFileSync(p);
    const h = crypto.createHash('sha256').update(b).digest('hex');
    if (h !== sf.sha256) problems.push('store file altered: ' + sf.file);
  }
  void byFile;
  return { ok: problems.length === 0, problems, observed: { verified: v.verified, mismatched: v.mismatched, recovered: v.packagesRecovered, hashRollup: v.hashRollup } };
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

  // ── M-7: the reconstruction and re-derivation layer ────────────────────────────────────────
  // Snappy is exercised against a payload with an OVERLAPPING back-reference, because that is the
  // case a naive implementation using a bulk copy silently corrupts.
  (function () {
    const lit = s => Buffer.concat([Buffer.from([(s.length - 1) << 2]), Buffer.from(s, 'latin1')]);
    const body = Buffer.concat([lit('abcd'), Buffer.from([(1 << 2) | 2, 0x02, 0x00])]); // copy len 2 off 2 ... overlapping
    const comp = Buffer.concat([Buffer.from([8]), lit('abcd'), Buffer.from([((6 - 4) << 2) | 1 | (0 << 5), 0x04])]);
    void body;
    const outp = snappyUncompress(comp);
    ck(outp.toString('latin1') === 'abcdabcd', 'snappy decodes an overlapping copy correctly (' + outp.toString('latin1') + ')');
  })();

  (function () {
    // A round trip through the REAL committed canonicalizer, so the extraction path is proven.
    const repo = path.resolve(__dirname, '..');
    const idx = path.join(repo, 'index.html');
    if (!fs.existsSync(idx)) { ck(false, 'index.html reachable for canonicalizer extraction'); return; }
    let canon;
    try { canon = loadCommittedCanonicalizer(idx); }
    catch (e) { ck(false, 'canonicalizer extracted from committed index.html (' + e.message + ')'); return; }
    ck(typeof canon.canonicalize === 'function', 'canonicalizer extracted from committed index.html');
    ck(canon.excluded.indexOf('export') !== -1 && canon.excluded.indexOf('contentHash') !== -1,
      'the excluded-field list came with it');
    // K3: key order must be insignificant; K4: array order must be significant.
    const a = canon.canonicalize({ b: 1, a: [1, 2] });
    const b = canon.canonicalize({ a: [1, 2], b: 1 });
    const c = canon.canonicalize({ a: [2, 1], b: 1 });
    ck(a === b, 'object key order is insignificant (K3)');
    ck(a !== c, 'array order IS significant (K4)');
    // The excluded block must not affect the hash -- this is what lets an export be recorded.
    const withExport = canon.canonicalize({ a: 1, export: { exportedAt: 'x' }, contentHash: 'y' });
    ck(withExport === canon.canonicalize({ a: 1 }), 'export and contentHash are excluded from the canonical form');
  })();

  (function () {
    // A REAL V8-serialized package, framed in a REAL SSTable-style block, must reconstruct and
    // re-derive. This proves the container + V8 + canonicalizer chain end to end offline.
    const v8 = require('v8');
    const repo = path.resolve(__dirname, '..');
    const idx = path.join(repo, 'index.html');
    if (!fs.existsSync(idx)) { ck(false, 'index.html reachable for round-trip'); return; }
    const canon = loadCommittedCanonicalizer(idx);
    const pkg = { packageSchemaVersion: 'mogo.evidence-package.v1', packageId: 'PKG|s|20260101|1',
      sourceTradeId: 'AGT|EUR_USD|1', objects: { a: [1, 2, 3] }, createdAt: '2026-01-01T00:00:00.000Z' };
    pkg.contentHash = crypto.createHash('sha256').update(Buffer.from(canon.canonicalize(pkg), 'utf8')).digest('hex');
    const ser = v8.serialize(pkg);
    const back = deserializePackage(ser);
    ck(!!back && back.packageId === pkg.packageId, 'a V8-serialized package is reconstructed');
    const rehash = crypto.createHash('sha256').update(Buffer.from(canon.canonicalize(back), 'utf8')).digest('hex');
    ck(rehash === pkg.contentHash, 'and its content hash re-derives exactly');
    // A tampered package must NOT verify -- the check has to be able to fail.
    const tampered = Object.assign({}, back, { sourceTradeId: 'AGT|EUR_USD|999' });
    const th = crypto.createHash('sha256').update(Buffer.from(canon.canonicalize(tampered), 'utf8')).digest('hex');
    ck(th !== pkg.contentHash, 'a tampered package FAILS re-derivation (the check can fail)');
  })();

  (function () {
    // verifyAgainstBaseline must FAIL CLOSED on every discrepancy class.
    const base = { baselineVersion: BASELINE_VERSION, verified: 2, hashRollup: 'deadbeef',
      packageHashes: ['a'.repeat(64), 'b'.repeat(64)], storeFiles: [] };
    const wrongVersion = Object.assign({}, base, { baselineVersion: 'mogo.evidence-baseline.v0' });
    let sawVersionProblem = false;
    try {
      const r = verifyAgainstBaseline(wrongVersion, path.join(__dirname), path.resolve(__dirname, '..', 'index.html'));
      sawVersionProblem = r.problems.some(p => /baseline version/.test(p));
    } catch (e) { sawVersionProblem = false; }
    ck(sawVersionProblem, 'a baseline with the wrong version is REFUSED');
  })();

  (function () {
    // verifyStore must EXPOSE the verified payloads, and must expose only those.
    // The --packages mode feeds the observation import path, so a package whose
    // hash did not re-derive must never appear in it -- otherwise an unverifiable
    // record reaches an append-only evidence store.
    const v8 = require('v8');
    const repo = path.resolve(__dirname, '..');
    const idx = path.join(repo, 'index.html');
    if (!fs.existsSync(idx)) { ck(false, 'index.html reachable for --packages check'); return; }
    const canon = loadCommittedCanonicalizer(idx);
    const good = { packageSchemaVersion: 'mogo.evidence-package.v1', packageId: 'PKG|s|20260101|1',
      sourceTradeId: 'AGT|EUR_USD|1', objects: { positions: [{ pnl: 1 }] },
      createdAt: '2026-01-01T00:00:00.000Z' };
    good.contentHash = crypto.createHash('sha256')
      .update(Buffer.from(canon.canonicalize(good), 'utf8')).digest('hex');
    // Same shape, but its stored hash is a lie.
    const bad = Object.assign({}, good, { packageId: 'PKG|s|20260101|2',
      sourceTradeId: 'AGT|EUR_USD|2', contentHash: 'deadbeef'.repeat(8) });

    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'mogo-pkgmode-'));
    try {
      // Frame both as WAL records so verifyStore reads them from a store directory.
      const walRecord = buf => {
        const head = Buffer.alloc(7);
        head.writeUInt16LE(buf.length, 4);
        head.writeUInt8(1, 6);
        return Buffer.concat([head, buf]);
      };
      fs.writeFileSync(path.join(dir, '000001.log'),
        Buffer.concat([walRecord(v8.serialize(good)), walRecord(v8.serialize(bad))]));
      const r = verifyStore(dir, idx);
      ck(Array.isArray(r.verifiedPackages), 'verifyStore exposes verifiedPackages');
      const ids = (r.verifiedPackages || []).map(p => p.packageId);
      ck(ids.includes('PKG|s|20260101|1'), 'a package whose hash re-derives IS exposed');
      ck(!ids.includes('PKG|s|20260101|2'),
         'a package whose hash does NOT re-derive is withheld (fail closed)');
      const exposed = (r.verifiedPackages || [])[0];
      ck(!!exposed && !!exposed.objects,
         'the exposed payload carries `objects` -- the trade fields the import path needs');
    } finally { fs.rmSync(dir, { recursive: true, force: true }); }
  })();

  console.log(f === 0 ? 'SELFTEST PASS -- record splitting, decoy rejection, version dedup, live refusal, '
                      + 'snappy, canonicalizer extraction, V8 round trip, fail-closed baseline'
                      : 'SELFTEST FAIL -- ' + f + ' check(s) failed');
  return f === 0 ? 0 : 1;
}

function main() {
  const a = process.argv.slice(2);
  if (a.includes('--selftest')) process.exit(selftest());
  const get = k => { const i = a.indexOf(k); return i !== -1 ? a[i + 1] : null; };
  const store = get('--store'), origin = get('--origin') || '(unspecified)', out = get('--out');
  const indexHtml = get('--index-html') || path.resolve(__dirname, '..', 'index.html');

  // ── --packages <file>: write the full, hash-VERIFIED package payloads ─────────────────────
  // The manifest mode above emits package METADATA only -- packageId, contentHash, sourceTradeId
  // and friends -- which is enough to detect that a close happened but NOT enough to import an
  // observation, because the trade fields live in `objects`. That gap is why forward capture
  // still needed a live browser read. Full deserialization already exists here for --verify, so
  // this reuses it rather than adding a second parser.
  //
  // FAIL CLOSED: a package whose stored hash does not re-derive from the bytes is never written.
  // Feeding the import path a payload this tool could not prove it read correctly would put an
  // unverifiable record into an append-only evidence store.
  const packagesOut = get('--packages');
  if (packagesOut) {
    if (!store) { console.error('FAIL: --store <CHECKPOINT_LEVELDB_DIR> required'); process.exit(2); }
    let r;
    try { r = verifyStore(store, indexHtml); }
    catch (e) { console.error('FAIL: ' + e.message); process.exit(2); }
    if (r.mismatched !== 0) {
      console.error('FAIL CLOSED: ' + r.mismatched + ' package(s) failed hash re-derivation; refusing to write.');
      process.exit(1);
    }
    if (r.verifiedPackages.length === 0) {
      console.error('FAIL CLOSED: no verified packages recovered from ' + store);
      process.exit(1);
    }
    const dest = path.resolve(packagesOut);
    fs.mkdirSync(path.dirname(dest), { recursive: true });
    fs.writeFileSync(dest, JSON.stringify(r.verifiedPackages, null, 2) + '\n');
    console.log(JSON.stringify({
      storeDir: r.storeDir,
      packagesRecovered: r.packagesRecovered,
      verified: r.verified,
      mismatched: r.mismatched,
      uniqueSourceTradeIds: r.uniqueSourceTradeIds,
      hashRollup: r.hashRollup,
      written: dest,
    }, null, 2));
    process.exit(0);
  }

  // ── --verify: reconstruct and re-derive every package hash ────────────────────────────────
  if (a.includes('--verify')) {
    if (!store) { console.error('FAIL: --store <CHECKPOINT_LEVELDB_DIR> required'); process.exit(2); }
    let r;
    try { r = verifyStore(store, indexHtml); }
    catch (e) { console.error('FAIL: ' + e.message); process.exit(2); }
    const { packageHashes, verifiedPackages, ...summary } = r;
    console.log(JSON.stringify(summary, null, 2));
    if (out) { fs.writeFileSync(path.resolve(out), JSON.stringify(r, null, 2)); console.log('written to ' + path.resolve(out)); }
    if (r.mismatched !== 0) { console.error('FAIL CLOSED: ' + r.mismatched + ' package(s) failed hash re-derivation.'); process.exit(1); }
    console.log('VERIFIED ' + r.verified + ' package(s), 0 mismatched.');
    process.exit(0);
  }

  // ── --baseline write|verify ───────────────────────────────────────────────────────────────
  const baselineMode = get('--baseline');
  if (baselineMode) {
    const file = get('--baseline-file') || path.resolve(__dirname, '..', 'docs', 'evidence', 'EVIDENCE_BASELINE.json');
    if (baselineMode === 'write') {
      if (!store) { console.error('FAIL: --store required'); process.exit(2); }
      let b;
      try { b = buildBaseline(store, indexHtml, origin, get('--checkpoint')); }
      catch (e) { console.error('FAIL: ' + e.message); process.exit(2); }
      if (b.mismatched !== 0) { console.error('FAIL CLOSED: refusing to write a baseline with ' + b.mismatched + ' mismatch(es).'); process.exit(1); }
      fs.mkdirSync(path.dirname(file), { recursive: true });
      fs.writeFileSync(file, JSON.stringify(b, null, 2) + '\n');
      console.log('baseline written: ' + file);
      console.log('  verified ' + b.verified + ' package(s), rollup ' + b.hashRollup);
      process.exit(0);
    }
    if (baselineMode === 'verify') {
      if (!store) { console.error('FAIL: --store required'); process.exit(2); }
      if (!fs.existsSync(file)) { console.error('FAIL CLOSED: baseline not found: ' + file); process.exit(1); }
      const b = JSON.parse(fs.readFileSync(file, 'utf8'));
      let r;
      try { r = verifyAgainstBaseline(b, store, indexHtml); }
      catch (e) { console.error('FAIL: ' + e.message); process.exit(2); }
      console.log(JSON.stringify(r, null, 2));
      if (!r.ok) { console.error('FAIL CLOSED: baseline verification failed.'); process.exit(1); }
      console.log('BASELINE VERIFIED — ' + r.observed.verified + ' package(s) re-derived, rollup matches.');
      process.exit(0);
    }
    console.error('FAIL: --baseline must be write or verify'); process.exit(2);
  }

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
module.exports = { extract, stringTokens, recordFromTokens, assertNotLive,
  snappyUncompress, readWal, readSst, deserializePackage, loadCommittedCanonicalizer,
  verifyStore, buildBaseline, verifyAgainstBaseline, BASELINE_VERSION };

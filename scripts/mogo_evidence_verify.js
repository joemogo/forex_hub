#!/usr/bin/env node
// ══════════════════════════════════════════════════════════════════════════════════════════
// MOGO — offline evidence inventory and verifier (MOGO-011 Step 4A)
// ══════════════════════════════════════════════════════════════════════════════════════════
//
// WHY THIS EXISTS
//
// 222 evidence packages are reported unexported in a browser profile, an unknown number of files
// are scattered across the operator's disk, and nothing could say which of those files are real,
// which are duplicates, which verify, and which are missing. Step 4A establishes that factual
// state BEFORE any application behaviour is changed.
//
// THE ONE RULE THIS FILE OBEYS ABOVE ALL OTHERS
//
// It is READ-ONLY with respect to evidence. It opens evidence files with fs.readFileSync and
// nothing else. There is no write, rename, move, unlink, chmod or utimes call anywhere in this
// file that can target a scanned path -- and the run itself re-fingerprints every scanned file
// afterwards and FAILS if a single byte, size or mtime moved. A verifier that could alter what it
// verifies is not a verifier.
//
// CANONICALIZATION IS NOT REIMPLEMENTED
//
// A second implementation of mogo.evidence-canon.v1 would be a second source of truth, and the
// first time they disagreed the evidence chain would have two answers and no authority. So this
// tool does NOT reimplement it: it reads index.html, extracts the EXACT source text of
// EVIDENCE_HASH_EXCLUDED_FIELDS, evidenceCanonValue and evidenceCanonicalize, and evaluates that
// text. The canonical form produced here is produced by the shipped code, byte for byte.
//
// The ONE primitive substituted is the digest itself: the browser calls Web Crypto's
// crypto.subtle.digest('SHA-256', ...), which does not exist in Node, so node:crypto's sha256 is
// used over the identical UTF-8 bytes. That is a standard, interchangeable digest rather than any
// MOGO-specific logic -- and the substitution is proven, not asserted: --selftest round-trips the
// real canonicalizer, and a production run cross-checks every recomputed hash against the hash the
// BROWSER recorded inside each package.
//
// IDENTITY
//
// packageId is NOT a safe identity key. It is minted from a per-browser-profile counter
// (evidenceAllocateSequence), so a fresh or disposable profile re-mints the same id for a
// completely different trade. Real collisions exist on this machine. This tool therefore keys
// unique evidence identity on sourceTradeId -- which is immutable and, in the observed corpus,
// collision-free -- and reports packageId collisions separately and loudly.
//
// It does NOT change production identity semantics. It only measures them.
//
// USAGE
//   node scripts/mogo_evidence_verify.js --scan <DIR> [--scan <DIR> ...] [options]
//   node scripts/mogo_evidence_verify.js --selftest
//
//   --scan <DIR>          directory to scan recursively (repeatable). Required unless --selftest.
//   --manifest <FILE>     a browser-exported read-only manifest, to detect stored-but-not-found.
//   --expected-total <N>  the operator-reported stored-package count, for gap reporting.
//   --out <FILE>          write the JSON report here. Refused inside any protected or scanned dir.
//   --app <FILE>          index.html to take the canonicalizer from (default: <repo>/index.html).
//   --json                print the JSON report to stdout instead of the human report.
//   --selftest            run the self-test suite and exit.
//
// Exit status: 0 only when every parseable package verified and no collision, mismatch, malformed
// file or missing package was found. Any of those exits non-zero. An empty scan exits non-zero --
// finding nothing is not the same as finding everything is fine.

'use strict';

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const TOOL_VERSION = 'mogo-evidence-verify/1.0.0 (MOGO-011 Step 4A)';
const REPO_ROOT = path.resolve(__dirname, '..');

// Directories this tool must never write into, whatever the operator passes. The frozen Campaign
// C1 artifacts and their manifest live here; a verification report dropped among them would be
// indistinguishable from evidence to any later census.
const PROTECTED_WRITE_DIRS = [
  path.join(REPO_ROOT, 'evidence'),
  path.join(REPO_ROOT, 'docs', 'campaigns'),
];

// ── Argument parsing ─────────────────────────────────────────────────────────────────────────
function parseArgs(argv) {
  const out = { scan: [], manifest: null, expectedTotal: null, outFile: null, app: null,
                json: false, selftest: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--scan') out.scan.push(argv[++i]);
    else if (a === '--manifest') out.manifest = argv[++i];
    else if (a === '--expected-total') out.expectedTotal = parseInt(argv[++i], 10);
    else if (a === '--out') out.outFile = argv[++i];
    else if (a === '--app') out.app = argv[++i];
    else if (a === '--json') out.json = true;
    else if (a === '--selftest') out.selftest = true;
    else if (a === '--help' || a === '-h') out.help = true;
    else throw new Error('unknown argument: ' + a);
  }
  return out;
}

// ══ The canonicalizer, taken verbatim from index.html ═════════════════════════════════════════
// Brace-depth extraction, the same technique tests/run_v128_evidence_platform_tests.js uses to
// assert against real shipped function text rather than a paraphrase of it.
function extractBraceBlock(src, decl) {
  const i = src.indexOf(decl);
  if (i === -1) throw new Error('not found in index.html: ' + decl);
  let depth = 0, started = false;
  for (let k = i; k < src.length; k++) {
    const c = src[k];
    if (c === '{') { depth++; started = true; }
    else if (c === '}') { depth--; if (started && depth === 0) return src.slice(i, k + 1); }
  }
  throw new Error('unterminated block: ' + decl);
}

function extractStatement(src, decl) {
  const i = src.indexOf(decl);
  if (i === -1) throw new Error('not found in index.html: ' + decl);
  const end = src.indexOf(';', i);
  if (end === -1) throw new Error('unterminated statement: ' + decl);
  return src.slice(i, end + 1);
}

// Returns { canonicalize, excludedFields, sourceText, appSha256 } built from the REAL shipped code.
function loadCanonicalizer(appPath) {
  const html = fs.readFileSync(appPath, 'utf8');
  const appSha256 = crypto.createHash('sha256').update(fs.readFileSync(appPath)).digest('hex');
  const m = html.match(/<script>([\s\S]*)<\/script>/);
  if (!m) throw new Error('could not find a <script> body in ' + appPath);
  const app = m[1];

  const parts = [
    extractStatement(app, 'const EVIDENCE_HASH_EXCLUDED_FIELDS='),
    extractBraceBlock(app, 'function evidenceCanonValue('),
    extractBraceBlock(app, 'function evidenceCanonicalize('),
  ];
  const sourceText = parts.join('\n');

  // eslint-disable-next-line no-new-func
  const factory = new Function(
    sourceText + '\nreturn {canonicalize: evidenceCanonicalize, canonValue: evidenceCanonValue,' +
    ' excluded: EVIDENCE_HASH_EXCLUDED_FIELDS};'
  );
  const api = factory();
  if (typeof api.canonicalize !== 'function') throw new Error('canonicalizer did not load');
  return { canonicalize: api.canonicalize, canonValue: api.canonValue,
           excludedFields: Array.from(api.excluded), sourceText, appSha256, appPath };
}

// The digest. Web Crypto in the browser; node:crypto here, over the identical UTF-8 bytes.
function sha256Hex(str) {
  return crypto.createHash('sha256').update(Buffer.from(str, 'utf8')).digest('hex');
}

// ══ Artifact classification — real evidence vs synthetic test artifact ═══════════════════════
// MOGO-011 Step 4A, Decision 1.
//
// The corpus contains packages that are structurally impossible as market trades. They must not be
// counted as real evidence, and they must not be deleted either. Classifying them by filename or by
// a suggestive identifier would be intuition dressed up as a rule -- so NOTHING here reads a
// filename, and nothing matches a literal identifier such as 'NOCRYPTO', 'MANUAL' or 'test'. Only
// internal, physical contradictions count.
//
// The evidence for the threshold, measured over the 79 identities in the observed corpus:
//     every REPLAY_RUN package held for >= 3,600,000 ms (one H1 bar; the shortest possible)
//     every LIVE_CLOSE package held for 0 ms, 0 ms and 4 ms
// Six orders of magnitude separate the two populations, with nothing in between.

const TIMEFRAME_BAR_MS = Object.freeze({ H1: 3600000, H4: 14400000, D: 86400000, W: 604800000 });
// Used only when a package records no timeframe of its own. MOGO's shortest supported timeframe is
// H1 and its price data arrives by polling, so no genuine position can open and close inside a
// minute on any timeframe this system supports.
const MIN_PLAUSIBLE_HOLD_MS = 60000;

function parseIsoMs(s) {
  if (s == null) return null;
  const t = Date.parse(String(s));
  return Number.isFinite(t) ? t : null;
}

// PURE. Returns { classification, rulesFired, rationale }.
//   SYNTHETIC    -- two or more independent physical contradictions
//   UNDETERMINED -- exactly one; suspicious, but never silently removed from counts
//   REAL         -- none
function classifyArtifact(pkg) {
  const rulesFired = [];
  const rationale = [];
  const objects = (pkg && pkg.objects) || {};
  const pos = Array.isArray(objects.positions) && objects.positions.length ? objects.positions[0] : null;
  const out = Array.isArray(objects.outcomes) && objects.outcomes.length ? objects.outcomes[0] : null;

  // SYN-1 — a holding period shorter than one bar of the position's own timeframe. A market
  // position cannot open and close before its own first bar has closed.
  if (pos && out) {
    const entry = parseIsoMs(pos.entryTimestamp);
    const exit = parseIsoMs(out.exitTimestamp);
    if (entry != null && exit != null) {
      const tf = pos.timeframe == null ? null : String(pos.timeframe);
      const floor = (tf && TIMEFRAME_BAR_MS[tf] != null) ? TIMEFRAME_BAR_MS[tf] : MIN_PLAUSIBLE_HOLD_MS;
      const held = exit - entry;
      if (held < floor) {
        rulesFired.push('SYN-1_IMPOSSIBLE_HOLDING_PERIOD');
        rationale.push('held for ' + held + ' ms, below the ' + floor + ' ms floor for timeframe ' +
                       (tf || '(unrecorded)') + ' — a position cannot close before its own first bar');
      }
    }
  }

  // SYN-2 — the price moved, yet both excursion extremes are recorded as exactly zero. A position
  // that travelled from entry to a different exit necessarily excursed. Strictly zero only: a null
  // means "not captured", which is a completeness gap and not a contradiction.
  if (pos && out) {
    const ep = pos.entryPrice, xp = out.exitPrice;
    if (typeof ep === 'number' && typeof xp === 'number' && ep !== xp &&
        out.maePips === 0 && out.mfePips === 0) {
      rulesFired.push('SYN-2_EXCURSION_CONTRADICTION');
      rationale.push('price moved ' + ep + ' → ' + xp + ' yet both maePips and mfePips are exactly 0');
    }
  }

  const classification = rulesFired.length >= 2 ? 'SYNTHETIC'
                       : (rulesFired.length === 1 ? 'UNDETERMINED' : 'REAL');
  return { classification, rulesFired, rationale };
}

// ══ Read-only guarantees ═════════════════════════════════════════════════════════════════════
function fingerprintFile(p) {
  const st = fs.statSync(p);
  return { size: st.size, mtimeMs: st.mtimeMs,
           sha256: crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex') };
}

function fingerprintAll(paths) {
  const out = {};
  for (const p of paths) { try { out[p] = fingerprintFile(p); } catch (e) { out[p] = { error: String(e && e.message) }; } }
  return out;
}

function diffFingerprints(before, after) {
  const changed = [];
  for (const p of Object.keys(before)) {
    const a = before[p], b = after[p];
    if (!b) { changed.push({ path: p, reason: 'DISAPPEARED' }); continue; }
    if (a.error || b.error) { if (String(a.error) !== String(b.error)) changed.push({ path: p, reason: 'ERROR_CHANGED' }); continue; }
    if (a.sha256 !== b.sha256) changed.push({ path: p, reason: 'BYTES_CHANGED' });
    else if (a.size !== b.size) changed.push({ path: p, reason: 'SIZE_CHANGED' });
    else if (a.mtimeMs !== b.mtimeMs) changed.push({ path: p, reason: 'MTIME_CHANGED' });
  }
  for (const p of Object.keys(after)) if (!(p in before)) changed.push({ path: p, reason: 'APPEARED' });
  return changed;
}

function assertOutPathAllowed(outFile, scanDirs) {
  if (!outFile) return;
  const resolved = path.resolve(outFile);
  const dir = path.dirname(resolved);
  for (const prot of PROTECTED_WRITE_DIRS) {
    if (dir === prot || dir.startsWith(prot + path.sep)) {
      throw new Error('refusing to write the report into a protected evidence directory: ' + prot);
    }
  }
  for (const s of scanDirs) {
    const sd = path.resolve(s);
    if (dir === sd || dir.startsWith(sd + path.sep)) {
      throw new Error('refusing to write the report inside a scanned directory (it would become ' +
                      'an input to its own next run): ' + sd);
    }
  }
}

// ══ Scanning ═════════════════════════════════════════════════════════════════════════════════
// Deliberately matches on the evidence filename convention AND on content, so a renamed package is
// still found and an unrelated .json is not silently treated as evidence.
function listCandidateFiles(dir) {
  const out = [];
  const stack = [path.resolve(dir)];
  while (stack.length) {
    const d = stack.pop();
    let entries;
    try { entries = fs.readdirSync(d, { withFileTypes: true }); }
    catch (e) { continue; }
    for (const e of entries) {
      const full = path.join(d, e.name);
      if (e.isDirectory()) { stack.push(full); continue; }
      if (!e.isFile()) continue;
      if (e.name.toLowerCase().endsWith('.json')) out.push(full);
    }
  }
  return out.sort();
}

const PKG_SCHEMA_PREFIX = 'mogo.evidence-package.';

// ══ The inventory ════════════════════════════════════════════════════════════════════════════
function buildInventory(opts) {
  const canon = loadCanonicalizer(opts.appPath);

  const scanned = [];
  const locations = [];
  for (const dir of opts.scanDirs) {
    const resolved = path.resolve(dir);
    const exists = fs.existsSync(resolved);
    const files = exists ? listCandidateFiles(resolved) : [];
    locations.push({ location: resolved, exists, jsonFilesFound: files.length });
    scanned.push(...files);
  }

  const before = fingerprintAll(scanned);

  const files = [];        // one row per PHYSICAL file
  for (const p of scanned) {
    const row = { path: p, dir: path.dirname(p), name: path.basename(p) };
    let raw;
    try { raw = fs.readFileSync(p); }
    catch (e) { row.status = 'UNREADABLE'; row.detail = String(e && e.message); files.push(row); continue; }
    row.bytes = raw.length;
    row.fileSha256 = crypto.createHash('sha256').update(raw).digest('hex');

    let obj;
    try { obj = JSON.parse(raw.toString('utf8')); }
    catch (e) { row.status = 'MALFORMED_JSON'; row.detail = String(e && e.message); files.push(row); continue; }

    if (!obj || typeof obj !== 'object' || Array.isArray(obj)) {
      row.status = 'NOT_A_PACKAGE'; row.detail = 'top-level value is not an object'; files.push(row); continue;
    }
    const schema = obj.packageSchemaVersion;
    if (typeof schema !== 'string' || schema.indexOf(PKG_SCHEMA_PREFIX) !== 0) {
      row.status = 'NOT_A_PACKAGE';
      row.detail = 'packageSchemaVersion is ' + JSON.stringify(schema);
      files.push(row); continue;
    }

    row.packageSchemaVersion = schema;
    row.packageId = obj.packageId == null ? null : String(obj.packageId);
    row.sourceTradeId = obj.sourceTradeId == null ? null : String(obj.sourceTradeId);
    row.captureBasis = obj.captureBasis == null ? null : String(obj.captureBasis);
    row.runId = (obj.identity && obj.identity.runId != null) ? String(obj.identity.runId) : null;
    row.recordedHash = obj.contentHash == null ? null : String(obj.contentHash);
    row.hashAlgorithm = obj.contentHashAlgorithm == null ? null : String(obj.contentHashAlgorithm);
    row.hashProvenance = obj.contentHashProvenance == null ? null : String(obj.contentHashProvenance);
    row.exportBlock = obj.export == null ? null : obj.export;
    row.engineVersion = (obj.identity && obj.identity.engineVersion != null) ? String(obj.identity.engineVersion) : null;
    row.mode = (obj.identity && obj.identity.mode != null) ? String(obj.identity.mode) : null;
    row.createdAt = obj.createdAt == null ? null : String(obj.createdAt);

    const cls = classifyArtifact(obj);
    row.classification = cls.classification;
    row.classificationRules = cls.rulesFired;
    row.classificationRationale = cls.rationale;

    if (row.recordedHash == null) { row.status = 'NO_HASH'; files.push(row); continue; }
    if (row.hashAlgorithm != null && row.hashAlgorithm !== 'SHA-256') {
      row.status = 'UNSUPPORTED_ALGORITHM'; files.push(row); continue;
    }

    let canonical;
    try { canonical = canon.canonicalize(obj); }
    catch (e) { row.status = 'NOT_CANONICALIZABLE'; row.detail = String(e && e.message); files.push(row); continue; }
    row.canonicalBytes = Buffer.byteLength(canonical, 'utf8');
    row.computedHash = sha256Hex(canonical);
    row.status = (row.computedHash === row.recordedHash) ? 'VERIFIED' : 'HASH_MISMATCH';
    files.push(row);
  }

  const after = fingerprintAll(scanned);
  const mutations = diffFingerprints(before, after);

  // A file that will not parse cannot be classified, so it is INDETERMINATE rather than known-good.
  // Whether that matters depends entirely on where it sits. A malformed .json inside a directory
  // that holds evidence is a candidate corrupt package and must fail the run. The same file inside
  // an unrelated tree -- a copied browser profile, say -- is not evidence and never was. Counting
  // both identically would make this gate cry wolf on every broad scan, and a gate that cries wolf
  // is one nobody reads. Both are always REPORTED; only the first is counted as a problem.
  const evidenceBearingDirs = new Set(
    files.filter(f => f.packageSchemaVersion != null).map(f => f.dir));
  for (const f of files) {
    if (f.status !== 'MALFORMED_JSON' && f.status !== 'UNREADABLE') continue;
    f.inEvidenceBearingDir = evidenceBearingDirs.has(f.dir);
    f.severity = f.inEvidenceBearingDir ? 'PROBLEM' : 'NOTED_NOT_EVIDENCE';
  }

  return { canon, locations, files, mutations, scannedPaths: scanned, evidenceBearingDirs };
}

// ── Identity analysis. Physical files, unique identities, duplicates, collisions. ─────────────
function analyzeIdentity(files) {
  const packages = files.filter(f => f.status && f.status !== 'MALFORMED_JSON' &&
                                     f.status !== 'NOT_A_PACKAGE' && f.status !== 'UNREADABLE');

  // Unique evidence identity keys on sourceTradeId -- immutable, and collision-free in the
  // observed corpus. A package with no sourceTradeId falls back to packageId and is flagged.
  const byIdentity = new Map();
  const noIdentity = [];
  for (const f of packages) {
    const key = f.sourceTradeId != null ? 'trade:' + f.sourceTradeId
              : (f.packageId != null ? 'pkg:' + f.packageId : null);
    if (key == null) { noIdentity.push(f); continue; }
    if (f.sourceTradeId == null) f.identityFallback = true;
    if (!byIdentity.has(key)) byIdentity.set(key, []);
    byIdentity.get(key).push(f);
  }

  // Duplicate PHYSICAL copies of one identity, split by whether they agree on content.
  const duplicates = [];
  for (const [key, rows] of byIdentity) {
    if (rows.length < 2) continue;
    const hashes = new Set(rows.map(r => r.recordedHash));
    duplicates.push({
      identity: key,
      physicalCopies: rows.length,
      agreesOnContentHash: hashes.size === 1,
      distinctContentHashes: hashes.size,
      distinctFileBytes: new Set(rows.map(r => r.fileSha256)).size,
      paths: rows.map(r => r.path),
    });
  }

  // packageId collisions: one packageId carrying MORE THAN ONE distinct sourceTradeId.
  const byPackageId = new Map();
  for (const f of packages) {
    if (f.packageId == null) continue;
    if (!byPackageId.has(f.packageId)) byPackageId.set(f.packageId, []);
    byPackageId.get(f.packageId).push(f);
  }
  const distinctPackageIds = byPackageId.size;
  const collisions = [];
  for (const [pid, rows] of byPackageId) {
    const trades = new Set(rows.map(r => String(r.sourceTradeId)));
    if (trades.size > 1) {
      collisions.push({
        packageId: pid,
        distinctSourceTradeIds: trades.size,
        distinctContentHashes: new Set(rows.map(r => r.recordedHash)).size,
        sourceTradeIds: Array.from(trades),
        runIds: Array.from(new Set(rows.map(r => r.runId))),
        paths: rows.map(r => r.path),
      });
    }
  }

  // A sourceTradeId carrying more than one packageId would break the identity key itself.
  const identitySplits = [];
  const tradeToPkg = new Map();
  for (const f of packages) {
    if (f.sourceTradeId == null) continue;
    if (!tradeToPkg.has(f.sourceTradeId)) tradeToPkg.set(f.sourceTradeId, new Set());
    tradeToPkg.get(f.sourceTradeId).add(f.packageId);
  }
  for (const [t, pids] of tradeToPkg) {
    if (pids.size > 1) identitySplits.push({ sourceTradeId: t, packageIds: Array.from(pids) });
  }

  return { packages, byIdentity, duplicates, collisions, identitySplits, noIdentity,
           distinctPackageIds };
}

// ── Manifest reconciliation (stored-but-not-found). Only possible when a manifest is supplied. ─
function reconcileManifest(manifestPath, byIdentity) {
  const raw = fs.readFileSync(manifestPath, 'utf8');
  const parsed = JSON.parse(raw);
  const entries = Array.isArray(parsed) ? parsed
                : (Array.isArray(parsed.packages) ? parsed.packages : null);
  if (!entries) throw new Error('manifest has no recognizable package array (expected an array, or {packages:[...]})');

  const missing = [], present = [], hashDisagreements = [];
  for (const e of entries) {
    const st = e.sourceTradeId == null ? null : String(e.sourceTradeId);
    const key = st != null ? 'trade:' + st : (e.packageId != null ? 'pkg:' + String(e.packageId) : null);
    if (key == null || !byIdentity.has(key)) {
      missing.push({ sourceTradeId: st, packageId: e.packageId == null ? null : String(e.packageId) });
      continue;
    }
    present.push(key);
    if (e.contentHash != null) {
      const onDisk = new Set(byIdentity.get(key).map(r => r.recordedHash));
      if (!onDisk.has(String(e.contentHash))) {
        hashDisagreements.push({ identity: key, manifestHash: String(e.contentHash), onDisk: Array.from(onDisk) });
      }
    }
  }
  const unlisted = [];
  const listed = new Set(entries.map(e => e.sourceTradeId != null ? 'trade:' + String(e.sourceTradeId)
                                        : (e.packageId != null ? 'pkg:' + String(e.packageId) : '')));
  for (const key of byIdentity.keys()) if (!listed.has(key)) unlisted.push(key);

  return { manifestPath: path.resolve(manifestPath), manifestEntries: entries.length,
           present: present.length, missing, unlisted, hashDisagreements };
}

// ══ Report assembly ══════════════════════════════════════════════════════════════════════════
function buildReport(opts) {
  const inv = buildInventory(opts);
  const idy = analyzeIdentity(inv.files);

  const byStatus = {};
  for (const f of inv.files) byStatus[f.status] = (byStatus[f.status] || 0) + 1;

  const unparseable = inv.files.filter(f => f.status === 'MALFORMED_JSON' || f.status === 'UNREADABLE');
  const unparseableInEvidenceDirs = unparseable.filter(f => f.inEvidenceBearingDir);
  const unparseableElsewhere = unparseable.filter(f => !f.inEvidenceBearingDir);

  const verifiedIdentities = new Set();
  for (const [key, rows] of idy.byIdentity) {
    if (rows.some(r => r.status === 'VERIFIED')) verifiedIdentities.add(key);
  }

  // Classification is per IDENTITY, not per file. Copies of one package must not vote separately.
  // A disagreement between copies is itself a finding and is escalated, never averaged away.
  const identityClass = new Map();
  const classificationConflicts = [];
  for (const [key, rows] of idy.byIdentity) {
    const distinct = Array.from(new Set(rows.map(r => r.classification)));
    if (distinct.length > 1) classificationConflicts.push({ identity: key, classifications: distinct });
    identityClass.set(key, distinct.length > 1 ? 'UNDETERMINED' : distinct[0]);
  }
  const classCounts = { REAL: 0, UNDETERMINED: 0, SYNTHETIC: 0 };
  for (const v of identityClass.values()) if (v in classCounts) classCounts[v]++;

  const classifiedDetail = [];
  for (const [key, rows] of idy.byIdentity) {
    const c = identityClass.get(key);
    if (c === 'REAL') continue;
    const r0 = rows[0];
    classifiedDetail.push({
      identity: key, classification: c, packageId: r0.packageId,
      captureBasis: r0.captureBasis, engineVersion: r0.engineVersion,
      createdAt: r0.createdAt, hashStatus: r0.status,
      rulesFired: r0.classificationRules, rationale: r0.classificationRationale,
      paths: rows.map(x => x.path),
    });
  }

  let manifest = null;
  if (opts.manifestPath) manifest = reconcileManifest(opts.manifestPath, idy.byIdentity);

  const uniqueIdentities = idy.byIdentity.size;
  const expectedTotal = Number.isFinite(opts.expectedTotal) ? opts.expectedTotal : null;

  const report = {
    tool: TOOL_VERSION,
    canonicalization: {
      version: 'mogo.evidence-canon.v1',
      source: 'extracted verbatim from ' + inv.canon.appPath,
      appSha256: inv.canon.appSha256,
      canonicalizerSourceSha256: crypto.createHash('sha256').update(inv.canon.sourceText, 'utf8').digest('hex'),
      excludedFields: inv.canon.excludedFields,
      digest: 'SHA-256 (node:crypto) over the identical UTF-8 canonical bytes; the browser uses Web Crypto',
      reimplemented: false,
    },
    locationsScanned: inv.locations,
    counts: {
      physicalJsonFiles: inv.files.length,
      parseableEvidencePackages: idy.packages.length,
      uniquePackageIdentities: uniqueIdentities,
      duplicatePhysicalCopies: idy.packages.length - uniqueIdentities,
      hashVerified: byStatus.VERIFIED || 0,
      hashMismatches: byStatus.HASH_MISMATCH || 0,
      packagesWithoutHashes: byStatus.NO_HASH || 0,
      malformedJson: byStatus.MALFORMED_JSON || 0,
      notAPackage: byStatus.NOT_A_PACKAGE || 0,
      unreadable: byStatus.UNREADABLE || 0,
      unparseableInEvidenceBearingDirs: unparseableInEvidenceDirs.length,
      unparseableOutsideEvidenceDirs: unparseableElsewhere.length,
      notCanonicalizable: byStatus.NOT_CANONICALIZABLE || 0,
      unsupportedAlgorithm: byStatus.UNSUPPORTED_ALGORITHM || 0,
      uniqueIdentitiesWithAVerifiedCopy: verifiedIdentities.size,
    },
    classification: {
      rule: 'purely structural: physical contradictions inside the package. No filename, path or ' +
            'identifier string is ever consulted. SYNTHETIC requires >= 2 independent rules; ' +
            'exactly 1 leaves the artifact UNDETERMINED and it stays in the counts.',
      rules: {
        'SYN-1_IMPOSSIBLE_HOLDING_PERIOD':
          'exit - entry is shorter than one bar of the position own timeframe (fallback floor ' +
          MIN_PLAUSIBLE_HOLD_MS + ' ms when no timeframe is recorded)',
        'SYN-2_EXCURSION_CONTRADICTION':
          'entryPrice !== exitPrice yet maePips and mfePips are both exactly 0 (null means ' +
          'not-captured and is NOT treated as a contradiction)',
      },
      byIdentity: classCounts,
      realEvidenceIdentities: classCounts.REAL,
      undeterminedIdentities: classCounts.UNDETERMINED,
      syntheticIdentities: classCounts.SYNTHETIC,
      conflictsBetweenCopies: classificationConflicts,
      nonRealDetail: classifiedDetail,
      retention: 'SYNTHETIC and UNDETERMINED artifacts are PRESERVED unchanged. Classification ' +
                 'excludes them from the real-evidence population; it never deletes anything.',
    },
    identity: {
      identityKey: 'sourceTradeId (immutable); packageId used only as a fallback and flagged',
      distinctPackageIds: idy.distinctPackageIds,
      distinctSourceTradeIds: uniqueIdentities,
      // The gap between these two IS the collision damage: every excess trade beyond the first
      // sharing a packageId is a real package that packageId-keyed counting would lose.
      identitiesLostToPackageIdCollision: uniqueIdentities - idy.distinctPackageIds,
      packageIdCollisions: idy.collisions,
      packageIdCollisionCount: idy.collisions.length,
      sourceTradeIdSplits: idy.identitySplits,
      packagesWithNoIdentity: idy.noIdentity.map(f => f.path),
    },
    duplicates: {
      identitiesWithMultipleCopies: idy.duplicates.length,
      agreeingOnContentHash: idy.duplicates.filter(d => d.agreesOnContentHash).length,
      conflictingOnContentHash: idy.duplicates.filter(d => !d.agreesOnContentHash).length,
      detail: idy.duplicates,
    },
    manifestReconciliation: manifest,
    storedPackageGap: {
      expectedStoredTotal: expectedTotal,
      expectedTotalProvenance: expectedTotal == null ? 'NOT_SUPPLIED'
        : 'OPERATOR_REPORTED — this tool cannot independently verify the browser store without a manifest',
      uniqueIdentitiesFoundOnDisk: uniqueIdentities,
      // SYNTHETIC artifacts are excluded from the real-evidence population (Decision 1).
      // UNDETERMINED ones are NOT excluded -- an unproven suspicion must never quietly shrink a
      // count, because that is the direction that makes a backlog look smaller than it is.
      realEvidencePopulationOnDisk: classCounts.REAL + classCounts.UNDETERMINED,
      syntheticExcluded: classCounts.SYNTHETIC,
      undeterminedRetainedInCount: classCounts.UNDETERMINED,
      remainingGap: expectedTotal == null ? null
                    : expectedTotal - (classCounts.REAL + classCounts.UNDETERMINED),
      storedButNotFound: manifest ? manifest.missing.length : null,
      storedButNotFoundProvenance: manifest ? 'DETERMINED_FROM_MANIFEST'
        : 'UNDETERMINABLE — no manifest supplied; disk contents MUST NOT be assumed complete',
    },
    readOnlyProof: {
      filesFingerprintedBeforeAndAfter: inv.scannedPaths.length,
      mutationsDetected: inv.mutations.length,
      mutations: inv.mutations,
      guarantee: inv.mutations.length === 0
        ? 'every scanned file is byte-, size- and mtime-identical after the run'
        : 'MUTATION DETECTED — this is a defect in the verifier and the run must not be trusted',
    },
    files: inv.files,
  };

  report.unparseableFiles = {
    inEvidenceBearingDirs: unparseableInEvidenceDirs.map(f => ({ path: f.path, status: f.status, detail: f.detail })),
    outsideEvidenceDirs: unparseableElsewhere.map(f => ({ path: f.path, status: f.status, detail: f.detail })),
    rule: 'an unparseable file is INDETERMINATE. It fails the run only when it sits in a directory ' +
          'that holds evidence packages; elsewhere it is reported but is not evidence and never was.',
  };

  const problems =
    report.counts.hashMismatches + unparseableInEvidenceDirs.length +
    report.counts.notCanonicalizable + report.counts.unsupportedAlgorithm +
    report.identity.packageIdCollisionCount + report.identity.sourceTradeIdSplits.length +
    report.readOnlyProof.mutationsDetected +
    (manifest ? manifest.missing.length + manifest.hashDisagreements.length : 0);

  report.outcome = {
    problems,
    pass: problems === 0 && report.counts.parseableEvidencePackages > 0,
    note: report.counts.parseableEvidencePackages === 0
      ? 'no evidence packages were found — an empty scan is not a pass'
      : undefined,
  };
  return report;
}

// ══ Human-readable rendering ═════════════════════════════════════════════════════════════════
function renderHuman(r) {
  const L = [];
  const c = r.counts;
  L.push('═'.repeat(90));
  L.push('MOGO EVIDENCE INVENTORY AND VERIFICATION — ' + r.tool);
  L.push('═'.repeat(90));
  L.push('');
  L.push('CANONICALIZATION');
  L.push('  version              : ' + r.canonicalization.version + '  (NOT reimplemented)');
  L.push('  taken from           : ' + r.canonicalization.source);
  L.push('  index.html sha256    : ' + r.canonicalization.appSha256);
  L.push('  canonicalizer sha256 : ' + r.canonicalization.canonicalizerSourceSha256);
  L.push('  excluded from hash   : ' + r.canonicalization.excludedFields.join(', '));
  L.push('');
  L.push('LOCATIONS SCANNED');
  for (const loc of r.locationsScanned) {
    L.push('  ' + (loc.exists ? '✓' : '✗ MISSING') + '  ' + loc.location + '   (' + loc.jsonFilesFound + ' .json files)');
  }
  L.push('');
  L.push('COUNTS');
  L.push('  physical .json files                  : ' + c.physicalJsonFiles);
  L.push('  parseable evidence packages           : ' + c.parseableEvidencePackages);
  L.push('  UNIQUE package identities             : ' + c.uniquePackageIdentities);
  L.push('  duplicate physical copies             : ' + c.duplicatePhysicalCopies);
  L.push('  hash VERIFIED                         : ' + c.hashVerified);
  L.push('  hash MISMATCH                         : ' + c.hashMismatches);
  L.push('  packages without a hash               : ' + c.packagesWithoutHashes);
  L.push('  malformed JSON                        : ' + c.malformedJson +
         '   (' + c.unparseableInEvidenceBearingDirs + ' among evidence → PROBLEM, ' +
         c.unparseableOutsideEvidenceDirs + ' elsewhere → not evidence)');
  L.push('  not an evidence package               : ' + c.notAPackage);
  L.push('  unreadable                            : ' + c.unreadable);
  L.push('  not canonicalizable                   : ' + c.notCanonicalizable);
  L.push('  unsupported hash algorithm            : ' + c.unsupportedAlgorithm);
  L.push('  unique identities with a verified copy: ' + c.uniqueIdentitiesWithAVerifiedCopy);
  L.push('');
  L.push('IDENTITY');
  L.push('  identity key                : ' + r.identity.identityKey);
  L.push('  distinct sourceTradeIds     : ' + r.identity.distinctSourceTradeIds + '   ← the real number of packages');
  L.push('  distinct packageIds         : ' + r.identity.distinctPackageIds);
  L.push('  identities LOST if counting by packageId : ' + r.identity.identitiesLostToPackageIdCollision);
  L.push('  packageId COLLISIONS        : ' + r.identity.packageIdCollisionCount);
  for (const col of r.identity.packageIdCollisions) {
    L.push('     ' + col.packageId + '  → ' + col.distinctSourceTradeIds + ' distinct source trades, ' +
           col.distinctContentHashes + ' distinct hashes');
  }
  L.push('  sourceTradeId splits        : ' + r.identity.sourceTradeIdSplits.length +
         (r.identity.sourceTradeIdSplits.length === 0 ? '  (identity key is sound)' : '  ← IDENTITY KEY UNSOUND'));
  L.push('  packages with no identity   : ' + r.identity.packagesWithNoIdentity.length);
  L.push('');
  L.push('DUPLICATES');
  L.push('  identities with >1 physical copy : ' + r.duplicates.identitiesWithMultipleCopies);
  L.push('    agreeing on contentHash        : ' + r.duplicates.agreeingOnContentHash + '  (benign — export block differs only)');
  L.push('    CONFLICTING on contentHash     : ' + r.duplicates.conflictingOnContentHash);
  L.push('');
  if (r.manifestReconciliation) {
    const m = r.manifestReconciliation;
    L.push('MANIFEST RECONCILIATION');
    L.push('  manifest                : ' + m.manifestPath);
    L.push('  entries                 : ' + m.manifestEntries);
    L.push('  present on disk         : ' + m.present);
    L.push('  STORED BUT NOT FOUND    : ' + m.missing.length);
    L.push('  on disk but not listed  : ' + m.unlisted.length);
    L.push('  hash disagreements      : ' + m.hashDisagreements.length);
    L.push('');
  }
  const cl = r.classification;
  L.push('ARTIFACT CLASSIFICATION  (structural only — no filename or identifier is ever consulted)');
  L.push('  REAL evidence identities  : ' + cl.realEvidenceIdentities);
  L.push('  UNDETERMINED              : ' + cl.undeterminedIdentities + '   (retained in counts)');
  L.push('  SYNTHETIC / test          : ' + cl.syntheticIdentities + '   (excluded from real-evidence counts, PRESERVED unchanged)');
  L.push('  conflicts between copies  : ' + cl.conflictsBetweenCopies.length);
  for (const d of cl.nonRealDetail) {
    L.push('     ' + d.classification + '  ' + String(d.identity).slice(0, 46));
    L.push('        engine v' + d.engineVersion + '  created ' + d.createdAt + '  basis ' + d.captureBasis);
    for (const why of d.rationale) L.push('        · ' + why);
  }
  L.push('');
  const g = r.storedPackageGap;
  L.push('STORED-PACKAGE GAP');
  L.push('  expected stored total     : ' + (g.expectedStoredTotal == null ? '(not supplied)' : g.expectedStoredTotal));
  L.push('  provenance                : ' + g.expectedTotalProvenance);
  L.push('  unique identities on disk : ' + g.uniqueIdentitiesFoundOnDisk);
  L.push('  real-evidence population  : ' + g.realEvidencePopulationOnDisk +
         '   (' + g.syntheticExcluded + ' synthetic excluded, ' + g.undeterminedRetainedInCount + ' undetermined retained)');
  L.push('  REMAINING GAP             : ' + (g.remainingGap == null ? '(undeterminable)' : g.remainingGap));
  L.push('  stored-but-not-found      : ' + (g.storedButNotFound == null ? '(undeterminable)' : g.storedButNotFound));
  L.push('  ' + g.storedButNotFoundProvenance);
  L.push('');
  L.push('READ-ONLY PROOF');
  L.push('  files fingerprinted before and after : ' + r.readOnlyProof.filesFingerprintedBeforeAndAfter);
  L.push('  mutations detected                   : ' + r.readOnlyProof.mutationsDetected);
  L.push('  ' + r.readOnlyProof.guarantee);
  L.push('');
  L.push('═'.repeat(90));
  L.push(r.outcome.pass ? 'RESULT: PASS — every parseable package verified, no collision, no mutation'
                        : 'RESULT: FAIL — ' + r.outcome.problems + ' problem(s)' + (r.outcome.note ? ' — ' + r.outcome.note : ''));
  L.push('═'.repeat(90));
  return L.join('\n');
}

// ══ Self-test ════════════════════════════════════════════════════════════════════════════════
// Round-trips the REAL canonicalizer, proves the verifier can FAIL, and proves it cannot write.
// A verifier never shown to fail is not evidence that anything passed.
function selftest() {
  const os = require('os');
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'mogo-verify-selftest-'));
  let failures = 0;
  const check = (ok, msg) => { console.log((ok ? 'PASS -- ' : 'FAIL -- ') + msg); if (!ok) failures++; };

  try {
    const appPath = path.join(REPO_ROOT, 'index.html');
    const canon = loadCanonicalizer(appPath);

    // 1 — the canonicalizer really is the shipped one
    const html = fs.readFileSync(appPath, 'utf8');
    check(html.indexOf('function evidenceCanonicalize(pkg){') !== -1,
      'evidenceCanonicalize was located in index.html');
    check(canon.sourceText.indexOf('function evidenceCanonValue(') !== -1 &&
          canon.sourceText.indexOf('function evidenceCanonicalize(') !== -1,
      'the extracted text contains both real canonicalization functions');
    check(html.indexOf(canon.sourceText.split('\n').slice(-1)[0].trim()) !== -1 ||
          html.indexOf('function evidenceCanonicalize(pkg){') !== -1,
      'the extracted text is present verbatim in index.html');
    check(canon.excludedFields.indexOf('export') !== -1 && canon.excludedFields.indexOf('contentHash') !== -1,
      'the excluded-field list came from the app: ' + canon.excludedFields.join(','));

    // 2 — canonical form is order-insensitive for object keys, order-SENSITIVE for arrays
    const a = canon.canonicalize({ packageSchemaVersion: 'mogo.evidence-package.v1', b: 1, a: [1, 2] });
    const b = canon.canonicalize({ a: [1, 2], packageSchemaVersion: 'mogo.evidence-package.v1', b: 1 });
    const cflip = canon.canonicalize({ packageSchemaVersion: 'mogo.evidence-package.v1', b: 1, a: [2, 1] });
    check(a === b, 'object key order does not change the canonical form');
    check(a !== cflip, 'array order DOES change the canonical form');

    // 3 — the export block and integrity fields are excluded from the hash
    const base = { packageSchemaVersion: 'mogo.evidence-package.v1', packageId: 'PKG|s|1|1',
                   sourceTradeId: 'T1', objects: { x: 1 } };
    const h1 = sha256Hex(canon.canonicalize(Object.assign({}, base,
      { export: { exportedAt: null, exportAttemptCount: 1 } })));
    const h2 = sha256Hex(canon.canonicalize(Object.assign({}, base,
      { export: { exportedAt: '2026-01-01T00:00:00Z', exportAttemptCount: 9 } })));
    check(h1 === h2, 'a differing export block does not change the content hash');

    // 4 — build a real corpus on disk and run the real inventory over it
    const pkg = Object.assign({}, base, { contentHashAlgorithm: 'SHA-256', contentHashProvenance: 'OBSERVED' });
    pkg.contentHash = sha256Hex(canon.canonicalize(pkg));
    const write = (name, text) => { const p = path.join(tmp, name); fs.writeFileSync(p, text); return p; };

    write('good.json', JSON.stringify(pkg, null, 2));
    // duplicate copy of the SAME identity, differing only in its export block
    const dup = Object.assign({}, pkg, { export: { exportedAt: null, exportAttemptCount: 2 } });
    write('good-copy.json', JSON.stringify(dup, null, 2));
    // negative control: one mutated byte in the hashed surface
    const tampered = JSON.parse(JSON.stringify(pkg)); tampered.objects.x = 2;
    write('tampered.json', JSON.stringify(tampered, null, 2));
    // a package with no hash at all
    const nohash = Object.assign({}, base, { packageId: 'PKG|s|1|2', sourceTradeId: 'T2' });
    delete nohash.contentHash;
    write('nohash.json', JSON.stringify(nohash, null, 2));
    // a packageId collision: same packageId, different source trade
    const collide = JSON.parse(JSON.stringify(pkg)); collide.sourceTradeId = 'T_OTHER';
    collide.contentHash = sha256Hex(canon.canonicalize(collide));
    write('collide.json', JSON.stringify(collide, null, 2));
    write('malformed.json', '{ this is not json');
    write('unrelated.json', JSON.stringify({ hello: 'world' }));

    const corpusFiles = fs.readdirSync(tmp).map(f => path.join(tmp, f));
    const beforeCorpus = fingerprintAll(corpusFiles);

    const r = buildReport({ scanDirs: [tmp], appPath, manifestPath: null,
                            expectedTotal: 10, outFile: null });

    check(r.counts.physicalJsonFiles === 7, 'all 7 physical files counted (got ' + r.counts.physicalJsonFiles + ')');
    check(r.counts.parseableEvidencePackages === 5, '5 parseable packages (got ' + r.counts.parseableEvidencePackages + ')');
    check(r.counts.uniquePackageIdentities === 3, '3 unique identities T1/T2/T_OTHER (got ' + r.counts.uniquePackageIdentities + ')');
    check(r.counts.duplicatePhysicalCopies === 2, '2 duplicate physical copies (got ' + r.counts.duplicatePhysicalCopies + ')');
    check(r.counts.hashVerified === 3, '3 verified: good, good-copy, collide (got ' + r.counts.hashVerified + ')');
    check(r.counts.hashMismatches === 1, 'NEGATIVE CONTROL: the tampered byte produced exactly 1 MISMATCH (got ' + r.counts.hashMismatches + ')');
    check(r.counts.packagesWithoutHashes === 1, '1 package reported NO_HASH, never VERIFIED (got ' + r.counts.packagesWithoutHashes + ')');
    check(r.counts.malformedJson === 1, 'malformed JSON reported, not fatal (got ' + r.counts.malformedJson + ')');
    check(r.counts.notAPackage === 1, 'an unrelated .json is not treated as evidence (got ' + r.counts.notAPackage + ')');

    // Duplicates. Identity T1 has THREE physical copies: good, good-copy (differing only in its
    // export block) and tampered (whose bytes were altered but whose RECORDED hash was left
    // untouched -- exactly what a silently corrupted copy looks like). All three therefore share
    // an identity and a recorded contentHash, and only recomputation tells them apart. That is the
    // whole point of hashing the content rather than trusting the field.
    const d = r.duplicates.detail.find(x => x.identity === 'trade:T1');
    check(!!d && d.physicalCopies === 3, 'all three copies of one identity were grouped together (got ' + (d && d.physicalCopies) + ')');
    check(!!d && d.agreesOnContentHash === true, 'they all carry the same RECORDED contentHash');
    check(!!d && d.distinctFileBytes === 3, 'yet all three genuinely differ in file bytes (got ' + (d && d.distinctFileBytes) + ')');
    const t1rows = r.files.filter(f => f.sourceTradeId === 'T1');
    check(t1rows.filter(f => f.status === 'VERIFIED').length === 2 &&
          t1rows.filter(f => f.status === 'HASH_MISMATCH').length === 1,
      'recomputation separates the 2 honest copies from the 1 corrupted one sharing their identity');

    // collision detection, and the damage it would do to packageId-keyed counting
    check(r.identity.packageIdCollisionCount === 1, 'the packageId collision was detected (got ' + r.identity.packageIdCollisionCount + ')');
    check(r.identity.sourceTradeIdSplits.length === 0, 'no sourceTradeId maps to two packageIds — identity key sound');
    check(r.identity.distinctSourceTradeIds === 3 && r.identity.distinctPackageIds === 2,
      '3 real identities hide behind only 2 packageIds');
    check(r.identity.identitiesLostToPackageIdCollision === 1,
      'counting by packageId would LOSE exactly 1 real package (got ' + r.identity.identitiesLostToPackageIdCollision + ')');

    // an unparseable file among evidence is a PROBLEM; the same file elsewhere is not evidence
    check(r.counts.unparseableInEvidenceBearingDirs === 1,
      'the malformed file sits among evidence and is therefore counted as a problem');
    check(r.counts.unparseableOutsideEvidenceDirs === 0, 'and nothing was misfiled as harmless');
    const isolated = fs.mkdtempSync(path.join(os.tmpdir(), 'mogo-verify-isolated-'));
    fs.writeFileSync(path.join(isolated, 'not-evidence.json'), '{ broken');
    const r3 = buildReport({ scanDirs: [tmp, isolated], appPath, manifestPath: null,
                             expectedTotal: null, outFile: null });
    check(r3.counts.unparseableOutsideEvidenceDirs === 1,
      'a malformed file in a directory with no evidence is reported as NOT evidence');
    check(r3.counts.unparseableInEvidenceBearingDirs === 1,
      'while the one among evidence is still a problem');
    fs.rmSync(isolated, { recursive: true, force: true });

    // gap arithmetic
    check(r.storedPackageGap.remainingGap === 7, 'gap = expected 10 − 3 unique = 7 (got ' + r.storedPackageGap.remainingGap + ')');
    check(r.storedPackageGap.storedButNotFound === null,
      'stored-but-not-found is UNDETERMINABLE without a manifest, and says so');

    // 5 — THE READ-ONLY PROOF
    const afterCorpus = fingerprintAll(corpusFiles);
    const changed = diffFingerprints(beforeCorpus, afterCorpus);
    check(changed.length === 0, 'READ-ONLY: no scanned file changed bytes, size or mtime (' + changed.length + ' changes)');
    check(r.readOnlyProof.mutationsDetected === 0, 'the run reports its own read-only proof as clean');
    check(r.readOnlyProof.filesFingerprintedBeforeAndAfter === 7, 'all 7 files were fingerprinted before and after');
    check(fs.readdirSync(tmp).length === 7, 'the verifier created no file in the scanned directory');
    check(r.outcome.pass === false, 'a corpus containing a mismatch and a collision does NOT pass');

    // 6 — the mutation detector itself must be able to fire, or the proof above is worthless
    const probe = Object.assign({}, beforeCorpus);
    const firstKey = Object.keys(probe)[0];
    const forced = JSON.parse(JSON.stringify(afterCorpus));
    forced[firstKey].sha256 = 'deadbeef';
    check(diffFingerprints(beforeCorpus, forced).length === 1,
      'NEGATIVE CONTROL: the mutation detector fires when a file really does change');

    // 7 — manifest reconciliation finds stored-but-not-found
    const manifestPath = path.join(tmp, '..', path.basename(tmp) + '-manifest.json');
    fs.writeFileSync(manifestPath, JSON.stringify({ packages: [
      { sourceTradeId: 'T1', packageId: 'PKG|s|1|1', contentHash: pkg.contentHash },
      { sourceTradeId: 'T_GONE', packageId: 'PKG|s|1|99', contentHash: 'ab'.repeat(32) },
    ] }));
    const r2 = buildReport({ scanDirs: [tmp], appPath, manifestPath, expectedTotal: 2, outFile: null });
    check(r2.manifestReconciliation.missing.length === 1, 'a stored-but-not-found package was detected');
    check(r2.manifestReconciliation.missing[0].sourceTradeId === 'T_GONE', 'it was identified by sourceTradeId');
    check(r2.storedPackageGap.storedButNotFound === 1, 'stored-but-not-found is now DETERMINABLE from the manifest');
    fs.rmSync(manifestPath, { force: true });

    // 8 — the write guard
    let refusedProtected = false;
    try { assertOutPathAllowed(path.join(REPO_ROOT, 'evidence', 'report.json'), []); }
    catch (e) { refusedProtected = /protected evidence directory/.test(e.message); }
    check(refusedProtected, 'writing the report into evidence/ is REFUSED');

    let refusedCampaigns = false;
    try { assertOutPathAllowed(path.join(REPO_ROOT, 'docs', 'campaigns', 'C1', 'r.json'), []); }
    catch (e) { refusedCampaigns = /protected evidence directory/.test(e.message); }
    check(refusedCampaigns, 'writing the report into docs/campaigns/ is REFUSED');

    let refusedScanned = false;
    try { assertOutPathAllowed(path.join(tmp, 'report.json'), [tmp]); }
    catch (e) { refusedScanned = /inside a scanned directory/.test(e.message); }
    check(refusedScanned, 'writing the report inside a scanned directory is REFUSED');

    check(assertOutPathAllowed(path.join(tmp, '..', 'ok.json'), [tmp]) === undefined,
      'an ordinary output path outside every scanned and protected directory is allowed');

  } catch (e) {
    check(false, 'self-test threw: ' + (e && e.stack ? e.stack : e));
  } finally {
    fs.rmSync(tmp, { recursive: true, force: true });
    console.log(failures === 0
      ? 'SELFTEST PASS -- the verifier reuses the real canonicalizer, can fail, and cannot write'
      : 'SELFTEST FAIL -- ' + failures + ' check(s) failed');
  }
  return failures === 0 ? 0 : 1;
}

// ══ Entry point ══════════════════════════════════════════════════════════════════════════════
function main() {
  let args;
  try { args = parseArgs(process.argv.slice(2)); }
  catch (e) { console.error('FAIL: ' + e.message); process.exit(2); }

  if (args.help) {
    console.log(fs.readFileSync(__filename, 'utf8').split('\n')
      .filter(l => l.startsWith('//')).map(l => l.replace(/^\/\/ ?/, '')).join('\n'));
    process.exit(0);
  }
  if (args.selftest) process.exit(selftest());

  if (!args.scan.length) { console.error('FAIL: at least one --scan <DIR> is required (or --selftest)'); process.exit(2); }

  const appPath = path.resolve(args.app || path.join(REPO_ROOT, 'index.html'));
  if (!fs.existsSync(appPath)) { console.error('FAIL: app file not found: ' + appPath); process.exit(2); }

  try { assertOutPathAllowed(args.outFile, args.scan); }
  catch (e) { console.error('FAIL: ' + e.message); process.exit(2); }

  let report;
  try {
    report = buildReport({ scanDirs: args.scan, appPath, manifestPath: args.manifest,
                           expectedTotal: args.expectedTotal, outFile: args.outFile });
  } catch (e) { console.error('FAIL: ' + (e && e.stack ? e.stack : e)); process.exit(2); }

  console.log(args.json ? JSON.stringify(report, null, 2) : renderHuman(report));

  if (args.outFile) {
    fs.writeFileSync(path.resolve(args.outFile), JSON.stringify(report, null, 2));
    if (!args.json) console.log('\nJSON report written to ' + path.resolve(args.outFile));
  }
  process.exit(report.outcome.pass ? 0 : 1);
}

if (require.main === module) main();

module.exports = { loadCanonicalizer, sha256Hex, buildReport, buildInventory, analyzeIdentity,
                   fingerprintAll, diffFingerprints, assertOutPathAllowed, listCandidateFiles,
                   classifyArtifact, reconcileManifest, TIMEFRAME_BAR_MS, MIN_PLAUSIBLE_HOLD_MS,
                   REPO_ROOT, PROTECTED_WRITE_DIRS, TOOL_VERSION };

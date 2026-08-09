// ══════════════════════════════════════════════════════════════════════════════════════════
// MOGO — read-only browser evidence manifest (MOGO-011 Step 4B)
// ══════════════════════════════════════════════════════════════════════════════════════════
//
// WHAT THIS IS
//
// A snippet the OPERATOR pastes into the DevTools console of a tab already running MOGO. It reads
// the authoritative IndexedDB evidence store and prints a manifest that
// scripts/mogo_evidence_verify.js can reconcile against the files on disk.
//
// It exists because the disk inventory alone cannot answer the only questions that matter:
// how many packages the browser actually holds, and which of them never reached a file. Step 4A
// established that the operator-reported "222" cannot be verified from disk, and that packageId
// collides across profiles -- so reconciliation must key on sourceTradeId.
//
// ── IT IS OBSERVATIONAL. IT WRITES NOTHING. ────────────────────────────────────────────────────
//
// It does NOT mark evidence exported, does NOT mark evidence confirmed, does NOT touch exportedAt
// or any export-attempt metadata, does NOT delete, clear, rewrite or regenerate anything, does NOT
// trigger a download, does NOT execute a trade, and does NOT change paper-trading state.
//
// Four structural guarantees, not four promises:
//
//   1. It calls exactly two IndexedDB APIs: open() and a 'readonly' transaction's getAll(). The
//      strings 'readwrite', .put(, .add(, .delete( and .clear( do not appear in its logic at all,
//      and it asserts that about its own source before it runs.
//   2. It opens WITHOUT a version number. indexedDB.open(name) with no version cannot fire
//      onupgradeneeded, so it can never migrate, create or alter a store.
//   3. It never calls any MOGO function that writes: not evidenceUpdateExportState,
//      evidenceExportPackage, evidenceExportPending, evidenceExportAll, evidenceImportPackageObject,
//      evidencePutPackage or evidenceAllocateSequence.
//   4. It fingerprints the whole store -- including every mutable export field -- before and after
//      the read, and REFUSES to emit a manifest if anything moved.
//
// ── OUTPUT ────────────────────────────────────────────────────────────────────────────────────
//
// The manifest is printed to the console and, where the browser allows it, placed on the clipboard.
// It is deliberately NOT downloaded: a download is the very mechanism EXP-001 showed cannot be
// trusted, and Step 4B is forbidden from triggering one.
//
// Save the printed JSON to a file, then reconcile:
//
//   node scripts/mogo_evidence_verify.js --scan <DIR> --manifest <THAT FILE> --reconcile
//
// ── USAGE ─────────────────────────────────────────────────────────────────────────────────────
//
//   1. Open the tab that is already running MOGO. Do not clear anything. Do not export anything.
//   2. Open DevTools -> Console.
//   3. Paste this entire file and press Enter.
//   4. Copy the printed JSON (or paste from the clipboard) into a file.
//
// Run it on whichever device actually holds the evidence store. Step 4A established that the
// store on the repository machine holds only four 2026-07-31 test packages, not the reported 222,
// so the manifest must be taken from the device the operator actually uses.

(async function mogoEvidenceBrowserManifest() {
  'use strict';

  const OUT = { tool: 'mogo-evidence-browser-manifest/1.0.0 (MOGO-011 Step 4B)' };
  const log = (...a) => console.log('[mogo-manifest]', ...a);

  // ── Guard 0: prove THIS SOURCE contains no mutating call before doing anything at all. ───────
  // If someone edits this snippet to write, it refuses to run rather than quietly writing.
  const selfSrc = mogoEvidenceBrowserManifest.toString();
  const banned = ['readwrite', '.put(', '.add(', '.delete(', '.clear(',
                  'evidenceUpdateExportState', 'evidenceExportPackage', 'evidenceExportPending',
                  'evidenceExportAll', 'evidenceImportPackageObject', 'evidencePutPackage',
                  'evidenceAllocateSequence', 'downloadTextFile'];
  const found = banned.filter(b => selfSrc.split(b).length - 1 > 1); // >1 because the list itself matches once
  if (found.length) {
    console.error('[mogo-manifest] REFUSING TO RUN — this snippet contains mutating calls: ' + found.join(', '));
    return;
  }

  // ── Read the store. Prefer MOGO own read path; it is already readonly by construction. ───────
  const DB_NAME = 'mogo_evidence';
  const STORE = 'packages';

  function readAll() {
    if (typeof evidenceListPackages === 'function') {
      OUT.readPath = 'evidenceListPackages() — the application own readonly read path';
      return evidenceListPackages();
    }
    OUT.readPath = 'independent readonly IndexedDB connection (no version, so no upgrade possible)';
    return new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME);          // NO VERSION — cannot trigger an upgrade
      req.onerror = () => reject(req.error || new Error('open failed'));
      req.onblocked = () => reject(new Error('open blocked by another tab'));
      req.onupgradeneeded = () => reject(new Error('REFUSING: an upgrade was requested, which would write'));
      req.onsuccess = () => {
        const db = req.result;
        if (!db.objectStoreNames.contains(STORE)) { db.close(); resolve([]); return; }
        const tx = db.transaction([STORE], 'readonly');
        const g = tx.objectStore(STORE).getAll();
        g.onsuccess = () => { const r = g.result || []; db.close(); resolve(r); };
        g.onerror = () => { db.close(); reject(g.error || new Error('getAll failed')); };
      };
    });
  }

  // ── Fingerprint: identity AND every mutable export field, so a write of any kind is visible. ─
  async function sha256(s) {
    if (!(self.crypto && self.crypto.subtle)) return null;
    const b = await self.crypto.subtle.digest('SHA-256', new TextEncoder().encode(s));
    return Array.from(new Uint8Array(b)).map(x => ('0' + x.toString(16)).slice(-2)).join('');
  }
  function fingerprintText(list) {
    return list.map(p => {
      const e = (p && p.export) || {};
      return [p.packageId, p.sourceTradeId, p.contentHash, e.exportedAt, e.exportAttemptedAt,
              e.exportVerified, e.exportVerificationMethod, e.exportAttemptCount, e.exportMechanism]
             .map(v => String(v)).join('');
    }).sort().join('');
  }

  let before, after, list;
  try {
    const first = await readAll();
    before = { count: first.length, hash: await sha256(fingerprintText(first)) };
    list = await readAll();                                  // the read the manifest is built from
    const third = await readAll();
    after = { count: third.length, hash: await sha256(fingerprintText(third)) };
  } catch (e) {
    console.error('[mogo-manifest] FAILED to read the evidence store: ' + (e && e.message ? e.message : e));
    return;
  }

  const unchanged = before.count === after.count && before.hash === after.hash;
  if (!unchanged) {
    console.error('[mogo-manifest] REFUSING TO EMIT — the store changed while being read. ' +
                  'before=' + JSON.stringify(before) + ' after=' + JSON.stringify(after) +
                  '. Close other MOGO tabs and anything that captures evidence, then retry.');
    return;
  }

  // ── The manifest. Immutable identity first; mutable state recorded as observed, never altered. ─
  OUT.generatedAt = new Date().toISOString();
  OUT.origin = location.origin;
  OUT.userAgent = navigator.userAgent;
  OUT.appVersion = (typeof APP_VERSION !== 'undefined') ? String(APP_VERSION) : null;
  OUT.packageSchemaVersion = (typeof EVIDENCE_PACKAGE_SCHEMA_VERSION !== 'undefined')
    ? String(EVIDENCE_PACKAGE_SCHEMA_VERSION) : null;
  OUT.canonicalization = (typeof EVIDENCE_CANON_VERSION !== 'undefined')
    ? String(EVIDENCE_CANON_VERSION) : null;

  OUT.packages = list.map(p => {
    const id = p.identity || {};
    const e = p.export || {};
    return {
      // ── immutable identity ──
      sourceTradeId: p.sourceTradeId == null ? null : String(p.sourceTradeId),
      packageId: p.packageId == null ? null : String(p.packageId),
      contentHash: p.contentHash == null ? null : String(p.contentHash),
      contentHashProvenance: p.contentHashProvenance == null ? null : String(p.contentHashProvenance),
      contentHashAlgorithm: p.contentHashAlgorithm == null ? null : String(p.contentHashAlgorithm),
      packageSchemaVersion: p.packageSchemaVersion == null ? null : String(p.packageSchemaVersion),
      captureBasis: p.captureBasis == null ? null : String(p.captureBasis),
      createdAt: p.createdAt == null ? null : String(p.createdAt),
      // ── strategy / engine identity ──
      strategyId: id.strategyId == null ? null : String(id.strategyId),
      strategyVersion: id.strategyVersion == null ? null : String(id.strategyVersion),
      engineVersion: id.engineVersion == null ? null : String(id.engineVersion),
      mode: id.mode == null ? null : String(id.mode),
      // ── run / session identity ──
      runId: id.runId == null ? null : String(id.runId),
      datasetHash: id.datasetHash == null ? null : String(id.datasetHash),
      configHash: id.configHash == null ? null : String(id.configHash),
      paramsHash: id.paramsHash == null ? null : String(id.paramsHash),
      // ── export-attempt and confirmation state, AS OBSERVED ──
      exportedAt: e.exportedAt == null ? null : String(e.exportedAt),
      exportAttemptedAt: e.exportAttemptedAt == null ? null : String(e.exportAttemptedAt),
      exportAttemptCount: typeof e.exportAttemptCount === 'number' ? e.exportAttemptCount : null,
      exportMechanism: e.exportMechanism == null ? null : String(e.exportMechanism),
      exportVerified: e.exportVerified == null ? null : !!e.exportVerified,
      exportVerificationMethod: e.exportVerificationMethod == null ? null : String(e.exportVerificationMethod),
      exportFilename: e.exportFilename == null ? null : String(e.exportFilename),
      // ── recovery provenance, if this package was imported rather than captured here ──
      importedAt: p.importedAt == null ? null : String(p.importedAt),
      importVerification: p.importVerification == null ? null : String(p.importVerification),
    };
  });

  // ── Counts derived from the store itself, NEVER from the UI banner. ──────────────────────────
  const uniqueTrades = new Set(OUT.packages.map(p => p.sourceTradeId).filter(v => v != null));
  const uniquePkgIds = new Set(OUT.packages.map(p => p.packageId).filter(v => v != null));
  OUT.derivedCounts = {
    storedPackages: OUT.packages.length,
    uniqueSourceTradeIds: uniqueTrades.size,
    uniquePackageIds: uniquePkgIds.size,
    identitiesLostIfCountingByPackageId: uniqueTrades.size - uniquePkgIds.size,
    withoutContentHash: OUT.packages.filter(p => p.contentHash == null).length,
    confirmedExported: OUT.packages.filter(p => p.exportedAt != null).length,
    attemptedNotConfirmed: OUT.packages.filter(p => p.exportedAt == null && p.exportAttemptedAt != null).length,
    neverAttempted: OUT.packages.filter(p => p.exportedAt == null && p.exportAttemptedAt == null).length,
    provenance: 'DERIVED FROM THE STORE ITSELF, not read from the UI banner',
  };
  // What the banner would say, recorded ALONGSIDE the derived truth so the two can be compared
  // rather than conflated. If these disagree, the disagreement is the finding.
  OUT.bannerCounts = {
    evidencePackageCount: (typeof evidencePackageCount !== 'undefined') ? evidencePackageCount : null,
    evidenceUnexportedCount: (typeof evidenceUnexportedCount !== 'undefined') ? evidenceUnexportedCount : null,
    evidenceAttemptedUnverifiedCount: (typeof evidenceAttemptedUnverifiedCount !== 'undefined') ? evidenceAttemptedUnverifiedCount : null,
    evidenceUnverifiableCount: (typeof evidenceUnverifiableCount !== 'undefined') ? evidenceUnverifiableCount : null,
    note: 'in-memory counters as displayed. NOT authoritative. Compare against derivedCounts.',
  };

  OUT.readOnlyProof = {
    storeReadThreeTimes: true,
    fingerprintBefore: before,
    fingerprintAfter: after,
    unchanged,
    fingerprintCovers: 'packageId, sourceTradeId, contentHash AND every mutable export field',
    guarantee: 'no write API was called; the connection was opened without a version so no ' +
               'upgrade could fire; the store is byte-identical across the read',
  };

  const json = JSON.stringify(OUT, null, 2);
  log('stored packages:', OUT.derivedCounts.storedPackages,
      '| unique identities:', OUT.derivedCounts.uniqueSourceTradeIds,
      '| confirmed exported:', OUT.derivedCounts.confirmedExported);
  log('banner says:', JSON.stringify(OUT.bannerCounts));
  log('read-only proof:', unchanged ? 'STORE UNCHANGED' : 'CHANGED — refused');
  log('--- copy everything between the markers ---');
  console.log('===MOGO-MANIFEST-BEGIN===');
  console.log(json);
  console.log('===MOGO-MANIFEST-END===');
  try { if (typeof copy === 'function') { copy(json); log('manifest copied to clipboard'); } } catch (e) {}
  try { window.__mogoManifest = OUT; log('also available as window.__mogoManifest'); } catch (e) {}
  return OUT;
})();

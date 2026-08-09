#!/usr/bin/env node
// MOGO-011 Step 4A — fixture suite for the offline evidence inventory and verifier.
//
// WHY THIS SUITE RUNS UNDER NODE RATHER THAN osascript
//
// Every other permanent suite in this repository runs under `osascript -l JavaScript`. This one
// cannot: the behaviour under test IS filesystem and cryptographic behaviour -- reading real files,
// recomputing SHA-256, and proving that nothing on disk moved -- and JXA provides neither `fs` nor
// `crypto`. Asserting those properties against stubs would prove nothing about them.
//
// So the suite runs under Node, and tests/run_v131_evidence_verifier_tests.js is a thin JXA shim
// that locates Node, executes this file, and relays its PASS/FAIL lines so tests/run_all.sh counts
// them exactly like every other suite. This is the same constraint already accepted for
// scripts/mogo_evidence_receiver.js, whose --selftest is its verification for the same reason --
// but unlike the receiver, this suite IS wired into the canonical gate.
//
// CANONICALIZATION IS NEVER REIMPLEMENTED HERE.
// Every fixture calls the REAL functions the verifier extracts verbatim from index.html. There is
// no second canonicalizer in this file and no hardcoded expected hash: the hashes asserted below
// are the ones the BROWSER wrote into real evidence packages.
//
// Run directly:  node tests/v131_evidence_verifier_tests.js
// Or via the canonical gate:  tests/run_all.sh

'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');
const crypto = require('crypto');

const REPO = path.resolve(__dirname, '..');
const V = require(path.join(REPO, 'scripts', 'mogo_evidence_verify.js'));

let pass = 0, fail = 0;
function ok(cond, name, detail) {
  if (cond) { pass++; console.log('PASS -- ' + name + (detail ? ' (' + detail + ')' : '')); }
  else { fail++; console.log('FAIL -- ' + name + (detail ? ' (' + detail + ')' : '')); }
}
function eq(a, b, name) { ok(a === b, name, a === b ? '' : 'expected ' + JSON.stringify(b) + ', got ' + JSON.stringify(a)); }

const APP = path.join(REPO, 'index.html');

// ── A minimal but genuinely shaped package, hashed with the REAL canonicalizer ────────────────
const canon = V.loadCanonicalizer(APP);
function makePackage(over) {
  const p = {
    packageSchemaVersion: 'mogo.evidence-package.v1',
    packageId: 'PKG|alex_g_sr_v1|20260501|1',
    sourceTradeId: 'AGT|EUR_USD|1',
    captureBasis: 'REPLAY_RUN',
    createdAt: '2026-05-01T00:00:00.000Z',
    identity: { strategyId: 'alex_g_sr_v1', engineVersion: '12.19.0', mode: 'REPLAY',
                runId: 'a'.repeat(64) },
    objects: {
      positions: [{ positionId: 'AGT|EUR_USD|1', instrument: 'EUR_USD', timeframe: 'H1',
                    entryPrice: 1.1, entryTimestamp: '2026-05-01T00:00:00.000Z' }],
      outcomes: [{ positionId: 'AGT|EUR_USD|1', exitPrice: 1.11, maePips: 5, mfePips: 100,
                   exitTimestamp: '2026-05-01T06:00:00.000Z' }],
    },
    contentHashAlgorithm: 'SHA-256',
    contentHashCanonicalization: 'mogo.evidence-canon.v1',
    contentHashProvenance: 'OBSERVED',
    contentHashScope: 'INTEGRITY_ONLY_NOT_AUTHENTICITY',
  };
  if (over) Object.keys(over).forEach(k => { p[k] = over[k]; });
  p.contentHash = V.sha256Hex(canon.canonicalize(p));
  return p;
}

function withTmp(fn) {
  const d = fs.mkdtempSync(path.join(os.tmpdir(), 'mogo-v131-'));
  try { return fn(d); } finally { fs.rmSync(d, { recursive: true, force: true }); }
}
function write(dir, name, obj) {
  const p = path.join(dir, name);
  fs.writeFileSync(p, typeof obj === 'string' ? obj : JSON.stringify(obj, null, 2));
  return p;
}

console.log('--- MOGO-011 Step 4A evidence verifier fixtures ---');

// ══ GROUP 1 — the canonicalizer is the shipped one, not a copy ═══════════════════════════════
(function () {
  const html = fs.readFileSync(APP, 'utf8');
  ok(canon.sourceText.indexOf('function evidenceCanonValue(') !== -1 &&
     canon.sourceText.indexOf('function evidenceCanonicalize(') !== -1,
     'V1 both real canonicalization functions were extracted from index.html');
  ok(html.indexOf(canon.sourceText.slice(canon.sourceText.indexOf('function evidenceCanonicalize('))) !== -1,
     'V2 the extracted canonicalize() text appears VERBATIM in index.html');
  ok(canon.excludedFields.indexOf('export') !== -1,
     'V3 the export block is excluded from the hash, per the app own constant');
  eq(canon.excludedFields.length, 6, 'V4 exactly six fields are excluded, as shipped');
  // The strongest form of "no second implementation": take the function object the fixtures below
  // actually execute, read its own source back out of the running process, and find that exact text
  // inside index.html. A copy living in this file, or in the verifier, could not satisfy this.
  ok(html.indexOf(canon.canonicalize.toString()) !== -1,
     'V5 the EXECUTING canonicalize() function source is found verbatim inside index.html');
  ok(html.indexOf(canon.canonValue.toString()) !== -1,
     'V5b the EXECUTING canonValue() function source is found verbatim inside index.html');
})();

// ══ GROUP 2 — valid evidence verifies; tampered evidence fails ═══════════════════════════════
(function () {
  withTmp(dir => {
    const good = makePackage();
    write(dir, 'good.json', good);
    const tampered = JSON.parse(JSON.stringify(good));
    tampered.objects.outcomes[0].exitPrice = 1.12;   // one field, hash left untouched
    write(dir, 'tampered.json', tampered);

    const r = V.buildReport({ scanDirs: [dir], appPath: APP, manifestPath: null,
                              expectedTotal: null, outFile: null });
    eq(r.counts.hashVerified, 1, 'V6 VALID EVIDENCE VERIFIES');
    eq(r.counts.hashMismatches, 1, 'V7 TAMPERED EVIDENCE FAILS');
    const t = r.files.find(f => f.name === 'tampered.json');
    ok(t && t.computedHash !== t.recordedHash,
       'V8 the mismatch is a genuine recomputation difference, not a flag');
    ok(t && /^[0-9a-f]{64}$/.test(t.computedHash), 'V9 a full SHA-256 was actually computed');
  });
})();

// ══ GROUP 3 — canonical hash recomputation matches the BROWSER-generated hash ═════════════════
// The strongest available proof that node:crypto over mogo.evidence-canon.v1 reproduces Web Crypto:
// real packages, hashed inside a browser, recompute identically here. Uses the operator corpus when
// it is present, and never fails the suite merely because a personal directory is absent.
(function () {
  const corpora = [
    path.join(os.homedir(), 'Desktop', 'MOGO-Evidence'),
    path.join(os.homedir(), 'Downloads'),
  ].filter(d => fs.existsSync(d));

  if (!corpora.length) {
    console.log('PASS -- V10 (skipped: no operator evidence corpus on this machine)');
    pass++;
    return;
  }
  const r = V.buildReport({ scanDirs: corpora, appPath: APP, manifestPath: null,
                            expectedTotal: null, outFile: null });
  const browserHashed = r.files.filter(f => f.status === 'VERIFIED' || f.status === 'HASH_MISMATCH');
  if (!browserHashed.length) {
    console.log('PASS -- V10 (skipped: corpus present but holds no hashed packages)');
    pass++;
    return;
  }
  eq(r.counts.hashMismatches, 0,
     'V10 CANONICAL RECOMPUTATION MATCHES THE BROWSER-GENERATED HASH on ' + browserHashed.length + ' real packages');
  ok(browserHashed.every(f => f.computedHash === f.recordedHash),
     'V11 every browser-written contentHash was reproduced byte-for-byte offline');
})();

// ══ GROUP 4 — duplicate physical copies do not become new evidence identities ════════════════
(function () {
  withTmp(dir => {
    const p = makePackage();
    write(dir, 'copy-a.json', p);
    // Same package, different export block. contentHash is unchanged because export is excluded.
    const b = Object.assign({}, p, { export: { exportedAt: null, exportAttemptCount: 3 } });
    write(dir, 'copy-b.json', b);
    // A third copy differing only in JSON whitespace -- different file bytes, same content.
    fs.writeFileSync(path.join(dir, 'copy-c.json'), JSON.stringify(p));

    const r = V.buildReport({ scanDirs: [dir], appPath: APP, manifestPath: null,
                              expectedTotal: null, outFile: null });
    eq(r.counts.physicalJsonFiles, 3, 'V12 three physical files are counted as three');
    eq(r.counts.uniquePackageIdentities, 1, 'V13 DUPLICATE COPIES DO NOT BECOME NEW IDENTITIES');
    eq(r.counts.duplicatePhysicalCopies, 2, 'V14 the two extra copies are reported as duplicates');
    const d = r.duplicates.detail.find(x => x.identity === 'trade:AGT|EUR_USD|1');
    ok(d && d.agreesOnContentHash === true, 'V15 the copies agree on contentHash');
    eq(d ? d.distinctFileBytes : -1, 3, 'V16 yet all three genuinely differ in file bytes');
    eq(r.counts.hashVerified, 3, 'V17 all three copies verify independently');
  });
})();

// ══ GROUP 5 — packageId collisions are detected ══════════════════════════════════════════════
(function () {
  withTmp(dir => {
    const a = makePackage();
    const b = makePackage({ sourceTradeId: 'AGT|GBP_USD|9' });   // SAME packageId, different trade
    write(dir, 'a.json', a);
    write(dir, 'b.json', b);

    const r = V.buildReport({ scanDirs: [dir], appPath: APP, manifestPath: null,
                              expectedTotal: null, outFile: null });
    eq(r.identity.packageIdCollisionCount, 1, 'V18 PACKAGEID COLLISIONS ARE DETECTED');
    eq(r.identity.distinctSourceTradeIds, 2, 'V19 two real identities are present');
    eq(r.identity.distinctPackageIds, 1, 'V20 hiding behind a single packageId');
    eq(r.identity.identitiesLostToPackageIdCollision, 1,
       'V21 counting by packageId would LOSE one real package');
    eq(r.identity.sourceTradeIdSplits.length, 0, 'V22 sourceTradeId remains a sound identity key');
    ok(r.outcome.pass === false, 'V23 a corpus containing a collision does not pass');
  });
})();

// ══ GROUP 6 — source files remain unchanged; verification cannot mutate evidence ═════════════
(function () {
  withTmp(dir => {
    write(dir, 'p1.json', makePackage());
    write(dir, 'p2.json', makePackage({ packageId: 'PKG|alex_g_sr_v1|20260501|2', sourceTradeId: 'AGT|EUR_USD|2' }));
    write(dir, 'broken.json', '{ not json');

    const paths = fs.readdirSync(dir).map(f => path.join(dir, f));
    const before = V.fingerprintAll(paths);
    const beforeNames = fs.readdirSync(dir).sort().join(',');

    // Run the verifier twice -- a second pass would expose any first-pass side effect.
    V.buildReport({ scanDirs: [dir], appPath: APP, manifestPath: null, expectedTotal: null, outFile: null });
    const r = V.buildReport({ scanDirs: [dir], appPath: APP, manifestPath: null, expectedTotal: null, outFile: null });

    const after = V.fingerprintAll(paths);
    const changed = V.diffFingerprints(before, after);
    eq(changed.length, 0, 'V24 SOURCE FILES REMAIN UNCHANGED across two full runs');
    eq(r.readOnlyProof.mutationsDetected, 0, 'V25 the run self-reports its read-only proof as clean');
    eq(fs.readdirSync(dir).sort().join(','), beforeNames, 'V26 VERIFICATION CANNOT MUTATE EVIDENCE — no file created or removed');
    ok(paths.every(p => before[p].mtimeMs === after[p].mtimeMs), 'V27 not even mtime moved');

    // The read-only detector must be able to fire, or V24-V27 prove nothing.
    const forced = JSON.parse(JSON.stringify(after));
    forced[paths[0]].sha256 = 'f'.repeat(64);
    eq(V.diffFingerprints(before, forced).length, 1, 'V28 NEGATIVE CONTROL: the mutation detector fires on a real change');

    // And the tool refuses to write where evidence lives.
    let refused = 0;
    for (const bad of [path.join(REPO, 'evidence', 'x.json'), path.join(REPO, 'docs', 'campaigns', 'x.json')]) {
      try { V.assertOutPathAllowed(bad, []); } catch (e) { refused++; }
    }
    eq(refused, 2, 'V29 writing a report into evidence/ or docs/campaigns/ is refused');
  });
})();

// ══ GROUP 7 — artifact classification (Decision 1), structural only ══════════════════════════
(function () {
  // A real replay trade: held six hours, real excursion.
  const real = makePackage();
  eq(V.classifyArtifact(real).classification, 'REAL', 'V30 a plausible trade classifies REAL');

  // SYN-1 only: zero-duration, but excursion values present and consistent.
  const shortHold = makePackage({
    objects: { positions: [{ positionId: 'X', instrument: 'EUR_USD', timeframe: 'H1',
                             entryPrice: 1.1, entryTimestamp: '2026-05-01T00:00:00.000Z' }],
               outcomes: [{ positionId: 'X', exitPrice: 1.11, maePips: 5, mfePips: 100,
                            exitTimestamp: '2026-05-01T00:00:00.000Z' }] },
  });
  const s1 = V.classifyArtifact(shortHold);
  eq(s1.classification, 'UNDETERMINED', 'V31 ONE contradiction leaves the artifact UNDETERMINED, never SYNTHETIC');
  eq(s1.rulesFired.length, 1, 'V32 and exactly one rule fired');

  // SYN-1 + SYN-2: zero duration AND a price move with zero excursion.
  const synth = makePackage({
    objects: { positions: [{ positionId: 'X', instrument: 'EUR_USD', timeframe: 'H1',
                             entryPrice: 1.1, entryTimestamp: '2026-05-01T00:00:00.000Z' }],
               outcomes: [{ positionId: 'X', exitPrice: 1.09, maePips: 0, mfePips: 0,
                            exitTimestamp: '2026-05-01T00:00:00.000Z' }] },
  });
  const s2 = V.classifyArtifact(synth);
  eq(s2.classification, 'SYNTHETIC', 'V33 TWO independent contradictions classify SYNTHETIC');
  eq(s2.rulesFired.length, 2, 'V34 both rules fired');

  // Null excursions are a completeness gap, NOT a contradiction.
  const nullExc = makePackage({
    objects: { positions: [{ positionId: 'X', instrument: 'EUR_USD', timeframe: 'H1',
                             entryPrice: 1.1, entryTimestamp: '2026-05-01T00:00:00.000Z' }],
               outcomes: [{ positionId: 'X', exitPrice: 1.09, maePips: null, mfePips: null,
                            exitTimestamp: '2026-05-01T06:00:00.000Z' }] },
  });
  eq(V.classifyArtifact(nullExc).classification, 'REAL',
     'V35 a null excursion is a completeness gap, not evidence of fabrication');

  // A held-to-target H4 trade shorter than one H4 bar is still impossible.
  const h4 = makePackage({
    objects: { positions: [{ positionId: 'X', instrument: 'EUR_USD', timeframe: 'H4',
                             entryPrice: 1.1, entryTimestamp: '2026-05-01T00:00:00.000Z' }],
               outcomes: [{ positionId: 'X', exitPrice: 1.11, maePips: 3, mfePips: 9,
                            exitTimestamp: '2026-05-01T01:00:00.000Z' }] },
  });
  eq(V.classifyArtifact(h4).rulesFired[0], 'SYN-1_IMPOSSIBLE_HOLDING_PERIOD',
     'V36 the holding floor follows the position OWN timeframe, not a constant');

  // THE POINT OF DECISION 1: classification must not depend on names.
  const disguised = makePackage({ sourceTradeId: 'AGT|TOTALLY-REAL-TRADE|1',
    objects: synth.objects });
  eq(V.classifyArtifact(disguised).classification, 'SYNTHETIC',
     'V37 an innocent-looking identifier does not rescue a structurally impossible artifact');
  const honest = makePackage({ sourceTradeId: 'AGT|NOCRYPTO-TEST-FAKE|1' });
  eq(V.classifyArtifact(honest).classification, 'REAL',
     'V38 a suspicious-looking identifier does NOT by itself condemn a plausible artifact');
  const selfSrc = fs.readFileSync(path.join(REPO, 'scripts', 'mogo_evidence_verify.js'), 'utf8');
  const clsSrc = selfSrc.slice(selfSrc.indexOf('function classifyArtifact('),
                               selfSrc.indexOf('// ══ Read-only guarantees'));
  ok(clsSrc.indexOf('NOCRYPTO') === -1 && clsSrc.indexOf('MANUAL') === -1 &&
     clsSrc.indexOf('.name') === -1 && clsSrc.indexOf('path') === -1,
     'V39 the classifier source reads no filename, path or literal identifier');

  // Preservation: classification never deletes.
  withTmp(dir => {
    write(dir, 'synth.json', synth);
    const nBefore = fs.readdirSync(dir).length;
    const r = V.buildReport({ scanDirs: [dir], appPath: APP, manifestPath: null,
                              expectedTotal: 10, outFile: null });
    eq(fs.readdirSync(dir).length, nBefore, 'V40 a SYNTHETIC artifact is PRESERVED, never removed');
    eq(r.classification.syntheticIdentities, 1, 'V41 it is reported as synthetic');
    eq(r.storedPackageGap.realEvidencePopulationOnDisk, 0, 'V42 and excluded from the real-evidence population');
    eq(r.storedPackageGap.syntheticExcluded, 1, 'V43 with the exclusion stated explicitly');
  });

  // UNDETERMINED must stay in the count.
  withTmp(dir => {
    write(dir, 'u.json', shortHold);
    const r = V.buildReport({ scanDirs: [dir], appPath: APP, manifestPath: null,
                              expectedTotal: 10, outFile: null });
    eq(r.storedPackageGap.realEvidencePopulationOnDisk, 1,
       'V44 an UNDETERMINED artifact is NOT silently removed from the counts');
    eq(r.storedPackageGap.undeterminedRetainedInCount, 1, 'V45 and its retention is stated');
  });
})();

// ══ GROUP 8 — manifest reconciliation keys on sourceTradeId ══════════════════════════════════
(function () {
  withTmp(dir => {
    const a = makePackage();
    write(dir, 'a.json', a);
    const mf = path.join(dir, '..', path.basename(dir) + '-manifest.json');
    fs.writeFileSync(mf, JSON.stringify({ packages: [
      { sourceTradeId: 'AGT|EUR_USD|1', packageId: a.packageId, contentHash: a.contentHash },
      { sourceTradeId: 'AGT|MISSING|7', packageId: 'PKG|alex_g_sr_v1|20260501|1', contentHash: 'cd'.repeat(32) },
    ] }));
    try {
      const r = V.buildReport({ scanDirs: [dir], appPath: APP, manifestPath: mf,
                                expectedTotal: 2, outFile: null });
      eq(r.manifestReconciliation.missing.length, 1, 'V46 a stored-but-not-found package is detected');
      eq(r.manifestReconciliation.missing[0].sourceTradeId, 'AGT|MISSING|7',
         'V47 identified by sourceTradeId even though its packageId IS present on disk');
      eq(r.storedPackageGap.storedButNotFound, 1, 'V48 stored-but-not-found becomes determinable');
    } finally { fs.rmSync(mf, { force: true }); }
  });
})();

console.log('---');
console.log(fail === 0
  ? 'ALL MOGO-011 STEP 4A VERIFIER FIXTURES PASSED (' + pass + ' executed)'
  : 'FAILURES: ' + fail + '/' + (pass + fail) + ' executed');
process.exit(fail === 0 ? 0 : 1);

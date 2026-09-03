#!/usr/bin/env node
'use strict';
// Fixtures for the C1 attestation refresh preflight (scripts/mogo_c1_refresh.js).
//
// The preflight's policy half is pure and is exercised here directly with hand-built fact objects,
// so the whole decision surface is testable on a machine that holds NO evidence corpus -- which is
// the only kind of machine an agent ever runs on. The side-effecting half (spawning the verifier,
// writing the attestation) is deliberately NOT exercised: it needs the operator's own evidence
// directory, and faking one would prove nothing about the real path.
//
// Every fixture asserts a RELATIONSHIP, never a pinned snapshot count: the committed attestation's
// timestamp goes stale by the hour by design, so an assertion on its literal age would be a
// self-breaking test of exactly the kind this repository's own testing notes warn about.
//
// Run:  node tests/run_v137_c1_refresh_preflight_tests.js

const fs = require('fs');
const path = require('path');
const { evaluateRefresh, pinnedManifestSha, maxAgeMsFromSource, manifestArtifactFiles } =
  require(path.resolve(__dirname, '..', 'scripts', 'mogo_c1_refresh.js'));

const results = [];
function t(name, desc, fn) {
  let pass = false, detail = '';
  try { const r = fn(); pass = !!(r && r.pass); detail = (r && r.detail) || ''; }
  catch (e) { pass = false; detail = 'threw: ' + (e && e.message ? e.message : String(e)); }
  results.push({ name, desc, pass, detail });
}
const codes = function (v) { return v.blockers.map(function (b) { return b.code; }); };
const has = function (v, c) { return codes(v).indexOf(c) >= 0; };

const SHA = 'c23e72e070e4e6e841e9e9cb77952a426743e666600e010c9bb14ca27fcee666';
const DAY = 24 * 60 * 60 * 1000;
const T0 = Date.parse('2026-08-24T23:02:14.350Z');

// The healthy shape every negative control below mutates exactly one field of.
function healthy(over) {
  return Object.assign({
    evidenceDirPresent: true, manifestArtifactCount: 33, artifactsPresentCount: 33,
    verifierRan: true, verifierExitCode: 0,
    verdict: 'VERIFIED', missingFiles: [],
    attestationManifestSha: SHA, pinnedManifestSha: SHA,
    maxAgeMs: DAY,
    generatedAtMs: T0, nowMs: T0 + 60000
  }, over || {});
}

t('C1P-1', 'POSITIVE CONTROL: a fresh, verified, hash-matching attestation is READY', function () {
  const v = evaluateRefresh(healthy());
  return { pass: v.ok === true && v.blockers.length === 0, detail: 'blockers=' + JSON.stringify(codes(v)) };
});

t('C1P-2', 'no evidence directory REFUSES', function () {
  const v = evaluateRefresh(healthy({ evidenceDirPresent: false, artifactsPresentCount: 0 }));
  return { pass: !v.ok && has(v, 'NO_EVIDENCE_DIR'), detail: codes(v).join(',') };
});

t('C1P-3', 'THE CI CASE: a directory that EXISTS but holds none of the artifacts still refuses -- '
  + 'this is the exact shape a clean checkout has, and the first version of the guard passed it', function () {
  const v = evaluateRefresh(healthy({ artifactsPresentCount: 0 }));
  return { pass: !v.ok && has(v, 'ARTIFACTS_NOT_ON_THIS_MACHINE') && !has(v, 'NO_EVIDENCE_DIR'),
    detail: codes(v).join(',') };
});

t('C1P-3b', 'a PARTIAL corpus refuses too -- 32 of 33 present is not "present"', function () {
  const v = evaluateRefresh(healthy({ artifactsPresentCount: 32 }));
  return { pass: !v.ok && has(v, 'ARTIFACTS_NOT_ON_THIS_MACHINE'), detail: codes(v).join(',') };
});

t('C1P-4', 'the verifier’s nonzero exit blocks even when the parsed verdict looks acceptable', function () {
  const v = evaluateRefresh(healthy({ verifierExitCode: 1 }));
  return { pass: !v.ok && has(v, 'VERIFIER_NONZERO_EXIT'), detail: codes(v).join(',') };
});

t('C1P-5', 'a FAILED verdict with missing artifacts raises BOTH faults, not one merged one', function () {
  const v = evaluateRefresh(healthy({ verdict: 'FAILED', verifierExitCode: 1, missingFiles: ['a', 'b'] }));
  return {
    pass: !v.ok && has(v, 'VERDICT_NOT_VERIFIED') && has(v, 'MISSING_ARTIFACTS'),
    detail: codes(v).join(',')
  };
});

t('C1P-6', 'THE FORGOTTEN CHECK: a VERIFIED attestation whose manifest hash moved is still refused', function () {
  const v = evaluateRefresh(healthy({ attestationManifestSha: 'd'.repeat(64) }));
  return { pass: !v.ok && has(v, 'MANIFEST_MISMATCH'), detail: codes(v).join(',') };
});

t('C1P-7', '...and that refusal does NOT depend on the verdict being bad -- the verdict is VERIFIED here', function () {
  const v = evaluateRefresh(healthy({ attestationManifestSha: 'd'.repeat(64) }));
  return { pass: !has(v, 'VERDICT_NOT_VERIFIED') && has(v, 'MANIFEST_MISMATCH'), detail: codes(v).join(',') };
});

t('C1P-8', 'an unreadable pinned hash blocks rather than being treated as “no constraint”', function () {
  const v = evaluateRefresh(healthy({ pinnedManifestSha: null }));
  return { pass: !v.ok && has(v, 'NO_PINNED_HASH'), detail: codes(v).join(',') };
});

t('C1P-9', 'an attestation already past the window is reported stale at generation time', function () {
  const v = evaluateRefresh(healthy({ nowMs: T0 + DAY + 1000 }));
  return { pass: !v.ok && has(v, 'ALREADY_STALE'), detail: codes(v).join(',') };
});

t('C1P-10', 'age exactly equal to the policy window is NOT stale -- the app accepts equality too', function () {
  const v = evaluateRefresh(healthy({ nowMs: T0 + DAY }));
  return { pass: v.ok === true, detail: 'blockers=' + JSON.stringify(codes(v)) };
});

t('C1P-11', 'the deadline is generatedAt + the policy window, and the remaining minutes agree with it', function () {
  const v = evaluateRefresh(healthy({ nowMs: T0 + 60 * 60000 }));
  const expectedExpiry = T0 + DAY;
  return {
    pass: v.expiresAtMs === expectedExpiry && v.minutesRemaining === (24 * 60 - 60),
    detail: 'expires=' + new Date(v.expiresAtMs).toISOString() + ' remaining=' + v.minutesRemaining
  };
});

t('C1P-12', 'a missing generatedAt blocks instead of defaulting to “fresh”', function () {
  const v = evaluateRefresh(healthy({ generatedAtMs: null }));
  return { pass: !v.ok && has(v, 'NO_TIMESTAMP'), detail: codes(v).join(',') };
});

t('C1P-13', 'an empty fact object blocks -- an absent fact is never a pass', function () {
  const v = evaluateRefresh({});
  return { pass: !v.ok && v.blockers.length >= 4, detail: codes(v).join(',') };
});

t('C1P-19', 'this tool reads the SAME artifact set the verifier reads: the manifest rows it parses '
  + 'number exactly what the committed attestation reports as artifacts.total', function () {
  const man = fs.readFileSync(path.resolve(__dirname, '..', 'docs', 'campaigns', 'C1',
    'CAMPAIGN_C1_EVIDENCE_MANIFEST.md'), 'utf8');
  const att = JSON.parse(fs.readFileSync(path.resolve(__dirname, '..', 'docs', 'campaigns', 'C1',
    'C1_INTEGRITY_ATTESTATION.json'), 'utf8'));
  const files = manifestArtifactFiles(man);
  return { pass: files.length > 0 && files.length === att.artifacts.total,
    detail: 'parsed=' + files.length + ' attestation.total=' + att.artifacts.total };
});

t('C1P-20', 'and every parsed name looks like a campaign artifact rather than a stray table cell', function () {
  const man = fs.readFileSync(path.resolve(__dirname, '..', 'docs', 'campaigns', 'C1',
    'CAMPAIGN_C1_EVIDENCE_MANIFEST.md'), 'utf8');
  const files = manifestArtifactFiles(man);
  const bad = files.filter(function (f) { return !/^C1-\d\d-[A-Z_]+-[A-Z]+\.json$/.test(f); });
  return { pass: files.length > 0 && bad.length === 0, detail: 'bad=' + JSON.stringify(bad.slice(0, 3)) };
});

// ── The two source readers, against the REAL index.html ───────────────────────────────────────
const indexSource = fs.readFileSync(path.resolve(__dirname, '..', 'index.html'), 'utf8');

t('C1P-14', 'the pinned manifest hash is read from index.html rather than duplicated in this tool', function () {
  const s = pinnedManifestSha(indexSource);
  return { pass: typeof s === 'string' && /^[0-9a-f]{64}$/.test(s), detail: String(s).slice(0, 16) + '…' };
});

t('C1P-15', 'the committed attestation names exactly that pinned manifest -- so C1 is not mismatched today', function () {
  const att = JSON.parse(fs.readFileSync(
    path.resolve(__dirname, '..', 'docs', 'campaigns', 'C1', 'C1_INTEGRITY_ATTESTATION.json'), 'utf8'));
  return { pass: att.manifestSha256 === pinnedManifestSha(indexSource), detail: att.manifestSha256.slice(0, 16) + '…' };
});

t('C1P-16', 'the policy window is read from index.html and is the 24 hours the app enforces', function () {
  const ms = maxAgeMsFromSource(indexSource);
  return { pass: ms === DAY, detail: String(ms) };
});

t('C1P-17', 'a reader handed source without the constant returns null rather than a plausible default', function () {
  return {
    pass: pinnedManifestSha('var x=1;') === null && maxAgeMsFromSource('var x=1;') === null,
    detail: 'both null'
  };
});

t('C1P-18', 'a non-literal max-age expression is refused rather than evaluated', function () {
  const ms = maxAgeMsFromSource("const EVIDENCE_C1_ATTESTATION_MAX_AGE_MS=doSomething();");
  return { pass: ms === null, detail: String(ms) };
});

results.forEach(function (r) {
  console.log((r.pass ? 'PASS' : 'FAIL') + ' -- ' + r.name + ': ' + r.desc + (r.detail ? '  [' + r.detail + ']' : ''));
});
const fails = results.filter(function (r) { return !r.pass; }).length;
console.log('---');
console.log(results.length + ' fixtures, ' + (results.length - fails) + ' PASS, ' + fails + ' FAIL');
process.exitCode = fails ? 1 : 0;

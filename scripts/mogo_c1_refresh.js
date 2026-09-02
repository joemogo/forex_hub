#!/usr/bin/env node
'use strict';
// ══════════════════════════════════════════════════════════════════════════════════════════
// MOGO — C1 attestation refresh preflight (OPERATOR TOOL, runs on the operator's machine)
// ══════════════════════════════════════════════════════════════════════════════════════════
//
// WHY THIS EXISTS
//
// Turning ALEX forward-PAPER trading ON requires evidenceForwardPaperPreflight() to pass, and one
// of its blockers -- CAMPAIGN_C1 -- is unconditional: it fires unless the attestation served from
// the app's own origin is intact AND was generated within EVIDENCE_C1_ATTESTATION_MAX_AGE_MS
// (24 hours). The attestation is a committed static file, so keeping it fresh is a deliberate
// operator act, not something the app can do for itself.
//
// WHY IT CANNOT BE AUTOMATED IN CI, AND WHY TRYING WOULD BE WORSE THAN DOING NOTHING
//
// verifyCampaignC1() reads the 33 campaign artifacts from <repo>/evidence, which is gitignored by
// design and exists only on the operator's machine. A CI job running from a clean checkout finds
// none of them and writes a verdict of FAILED with 33 missing artifacts -- and the browser refuses
// harder on that than on a stale one: VERDICT_NOT_VERIFIED, MISSING_ARTIFACTS,
// INCOMPLETE_VERIFICATION and CONTRADICTORY_MISSING_LIST all fire at once, and no timer clears
// them. Automating this naively converts a self-clearing delay into a permanent refusal. So this
// tool is a preflight for a human, not a scheduler.
//
// WHAT IT CHECKS, IN ORDER, FAILING CLOSED AT EACH STEP
//
//   1. every artifact the manifest names is actually present where the verifier will look. A
//      directory that merely EXISTS is not enough -- a clean checkout has an evidence/ holding
//      only a .gitignore, which is how the first version of this guard let the verifier run in CI
//      and overwrite the committed attestation with a FAILED one. Presence is checked against the
//      manifest's own rows, using the verifier's own flat lookup, and no artifact is opened.
//   2. the verifier's own verdict is VERIFIED -- its nonzero exit is honoured, never reinterpreted
//   3. the regenerated manifestSha256 still equals EVIDENCE_C1_MANIFEST_SHA256 as pinned in
//      index.html. This is the check a human forgets: a perfectly VERIFIED attestation whose
//      manifest hash has moved is refused by the browser as MANIFEST_MISMATCH, so committing and
//      pushing it accomplishes nothing and the failure only shows up at the toggle.
//   4. the freshness window is reported as a wall-clock deadline, because everything downstream --
//      commit, push, Pages deploy, hard refresh, toggle -- has to happen inside it.
//
// WHAT IT DELIBERATELY DOES NOT DO
//
// It does not commit, does not push, does not touch the working tree beyond the attestation file
// the verifier itself writes, and never reads, copies, moves or prints the contents of any
// evidence file. Publication is an operator decision; this prints the exact commands and stops.
//
// Usage, from the repository root:
//   node scripts/mogo_c1_refresh.js            # regenerate and check
//   node scripts/mogo_c1_refresh.js --check    # check the COMMITTED attestation, regenerate nothing

const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const REPO_ROOT = path.resolve(__dirname, '..');
const INDEX = path.join(REPO_ROOT, 'index.html');
const EVIDENCE_DIR = path.join(REPO_ROOT, 'evidence');
const ATTESTATION = path.join(REPO_ROOT, 'docs', 'campaigns', 'C1', 'C1_INTEGRITY_ATTESTATION.json');
const MANIFEST = path.join(REPO_ROOT, 'docs', 'campaigns', 'C1', 'CAMPAIGN_C1_EVIDENCE_MANIFEST.md');
const VERIFIER = path.join(REPO_ROOT, 'scripts', 'mogo_evidence_verify.js');

// ── PURE POLICY ───────────────────────────────────────────────────────────────────────────────
// Separated from every side effect so it is testable without an evidence corpus, the same split
// evidenceEvaluateForwardPaperGate uses. It evaluates the facts it is handed and never gathers
// them, so a caller that skipped a step cannot make it report success.

// The app's pinned manifest hash, read from source rather than duplicated here -- a second copy
// of this constant is a second source of truth, and the first time they disagreed this tool would
// vouch for an attestation the browser refuses.
function pinnedManifestSha(indexSource) {
  const m = /^const EVIDENCE_C1_MANIFEST_SHA256='([0-9a-f]{64})';/m.exec(indexSource);
  return m ? m[1] : null;
}
function maxAgeMsFromSource(indexSource) {
  const m = /^const EVIDENCE_C1_ATTESTATION_MAX_AGE_MS=([^;]+);/m.exec(indexSource);
  if (!m) return null;
  // Only an arithmetic literal is accepted; anything else is refused rather than guessed at.
  if (!/^[\d*+\s]+$/.test(m[1])) return null;
  return Function('"use strict";return (' + m[1] + ')')();
}

// The filenames the manifest names. This row pattern must stay identical to verifyCampaignC1's,
// or this tool would vouch for a set the verifier does not read; fixture C1P-19 pins the two
// together against the real manifest rather than asserting they agree.
function manifestArtifactFiles(manifestSource) {
  const rowRe = /^\|\s*(\d+)\s*\|\s*`([^`]+)`\s*\|.*?\|\s*([\d,]+)\s*\|\s*\S+\s*\|\s*`([0-9a-f]{64})`\s*\|/gm;
  const files = [];
  let m;
  while ((m = rowRe.exec(manifestSource)) !== null) files.push(m[2]);
  return files;
}

function evaluateRefresh(facts) {
  const f = facts || {};
  const blockers = [];
  const add = function (code, detail) { blockers.push({ code: code, detail: detail }); };

  if (f.evidenceDirPresent !== true) {
    add('NO_EVIDENCE_DIR', 'There is no evidence directory for the verifier to read.');
  }
  if (!(f.manifestArtifactCount > 0)) {
    add('NO_MANIFEST_ROWS', 'The manifest named no artifacts, so presence cannot be established.');
  } else if (f.artifactsPresentCount !== f.manifestArtifactCount) {
    add('ARTIFACTS_NOT_ON_THIS_MACHINE', (f.manifestArtifactCount - f.artifactsPresentCount) + ' of '
      + f.manifestArtifactCount + ' manifest artifacts are not where the verifier looks. Regenerating '
      + 'here would overwrite the committed attestation with a FAILED one, which the browser refuses '
      + 'harder than a stale one and which no timer ever clears.');
  }
  if (f.verifierRan !== true) add('VERIFIER_DID_NOT_RUN', 'The verifier did not complete, so it did not pass.');
  else {
    if (f.verifierExitCode !== 0) add('VERIFIER_NONZERO_EXIT', 'The verifier exited ' + f.verifierExitCode
      + '. Its exit status is authoritative and is never reinterpreted here.');
    if (f.verdict !== 'VERIFIED') add('VERDICT_NOT_VERIFIED', 'Attestation verdict is ' + String(f.verdict) + '.');
    if (Array.isArray(f.missingFiles) && f.missingFiles.length) {
      add('MISSING_ARTIFACTS', f.missingFiles.length + ' artifact(s) named in the manifest were not found.');
    }
  }
  if (!f.pinnedManifestSha) add('NO_PINNED_HASH', 'EVIDENCE_C1_MANIFEST_SHA256 could not be read from index.html.');
  else if (f.attestationManifestSha !== f.pinnedManifestSha) {
    add('MANIFEST_MISMATCH', 'The attestation names manifest ' + String(f.attestationManifestSha).slice(0, 12)
      + '… but index.html pins ' + f.pinnedManifestSha.slice(0, 12) + '…. The browser refuses this, '
      + 'so committing it would not unblock activation.');
  }
  if (!(f.maxAgeMs > 0)) add('NO_MAX_AGE', 'EVIDENCE_C1_ATTESTATION_MAX_AGE_MS could not be read from index.html.');
  if (f.generatedAtMs == null || isNaN(f.generatedAtMs)) add('NO_TIMESTAMP', 'The attestation carries no parseable generatedAt.');

  const ageMs = (f.generatedAtMs != null && f.nowMs != null) ? (f.nowMs - f.generatedAtMs) : null;
  const expiresAtMs = (f.generatedAtMs != null && f.maxAgeMs > 0) ? (f.generatedAtMs + f.maxAgeMs) : null;
  if (ageMs != null && f.maxAgeMs > 0 && ageMs > f.maxAgeMs) {
    add('ALREADY_STALE', 'This attestation is already older than the policy window.');
  }
  return {
    ok: blockers.length === 0,
    blockers: blockers,
    ageMs: ageMs,
    expiresAtMs: expiresAtMs,
    minutesRemaining: expiresAtMs == null || f.nowMs == null ? null
      : Math.floor((expiresAtMs - f.nowMs) / 60000)
  };
}

module.exports = { evaluateRefresh, pinnedManifestSha, maxAgeMsFromSource, manifestArtifactFiles };

// ── SIDE EFFECTS ──────────────────────────────────────────────────────────────────────────────
if (require.main === module) {
  const checkOnly = process.argv.includes('--check');
  const indexSource = fs.readFileSync(INDEX, 'utf8');

  let evidenceDirPresent = false;
  try { evidenceDirPresent = fs.statSync(EVIDENCE_DIR).isDirectory(); }
  catch (e) { evidenceDirPresent = false; }

  // Presence only -- existsSync, never a read. This tool must not open an evidence file.
  let manifestArtifacts = [];
  try { manifestArtifacts = manifestArtifactFiles(fs.readFileSync(MANIFEST, 'utf8')); }
  catch (e) { manifestArtifacts = []; }
  const artifactsPresentCount = manifestArtifacts
    .filter(function (f) { return fs.existsSync(path.join(EVIDENCE_DIR, f)); }).length;

  let verifierRan = false, verifierExitCode = null;
  if (!checkOnly) {
    if (!manifestArtifacts.length || artifactsPresentCount !== manifestArtifacts.length) {
      // Refuse BEFORE running: the verifier writes its FAILED record over the committed file, and
      // that record is worse than the stale one it replaced.
      console.log('REFUSED: ' + (manifestArtifacts.length - artifactsPresentCount) + ' of '
        + manifestArtifacts.length + ' manifest artifacts are not present under ' + EVIDENCE_DIR + '.');
      console.log('Regenerating here would overwrite the committed attestation with a FAILED one.');
      console.log('Run this on the machine that holds the campaign artifacts, or use --check.');
      process.exit(2);
    }
    const r = spawnSync(process.execPath, [VERIFIER, '--campaign-c1-attest'],
      { cwd: REPO_ROOT, encoding: 'utf8' });
    verifierRan = r.status !== null;
    verifierExitCode = r.status;
    if (r.stderr) process.stderr.write(r.stderr);
  } else {
    verifierRan = true; verifierExitCode = 0; // not run by design; the committed file is the subject
  }

  let att = null;
  try { att = JSON.parse(fs.readFileSync(ATTESTATION, 'utf8')); } catch (e) { att = null; }

  const nowMs = Date.now();
  const facts = {
    evidenceDirPresent,
    manifestArtifactCount: manifestArtifacts.length, artifactsPresentCount,
    verifierRan, verifierExitCode,
    verdict: att ? att.verdict : null,
    missingFiles: att ? att.missingFiles : null,
    attestationManifestSha: att ? att.manifestSha256 : null,
    pinnedManifestSha: pinnedManifestSha(indexSource),
    maxAgeMs: maxAgeMsFromSource(indexSource),
    generatedAtMs: att && att.generatedAt ? Date.parse(att.generatedAt) : null,
    nowMs
  };
  const v = evaluateRefresh(facts);

  const hrs = function (ms) { return ms == null ? 'n/a' : (ms / 3600000).toFixed(2) + ' h'; };
  console.log('C1 attestation ' + (checkOnly ? 'check' : 'refresh') + ' — ' + new Date(nowMs).toISOString());
  console.log('  manifest artifacts  : ' + artifactsPresentCount + '/' + manifestArtifacts.length
    + ' present' + (evidenceDirPresent ? '' : '  (no evidence directory)'));
  console.log('  verdict             : ' + (att ? att.verdict : '(no attestation readable)'));
  console.log('  generatedAt         : ' + (att ? att.generatedAt : 'n/a'));
  console.log('  age                 : ' + hrs(v.ageMs) + '   (policy max ' + hrs(facts.maxAgeMs) + ')');
  console.log('  manifest hash       : ' + (facts.attestationManifestSha === facts.pinnedManifestSha
    ? 'matches the hash pinned in index.html' : 'DOES NOT MATCH index.html'));
  if (v.expiresAtMs != null) {
    console.log('  window closes       : ' + new Date(v.expiresAtMs).toISOString()
      + '  (' + v.minutesRemaining + ' minutes from now)');
  }

  if (!v.ok) {
    console.log('\nNOT READY — activation would still be refused:');
    v.blockers.forEach(function (b) { console.log('  • ' + b.code + ': ' + b.detail); });
    process.exit(1);
  }

  console.log('\nREADY. Everything below must finish before the window closes above.');

  // WHAT BRANCH THIS WOULD LAND ON. `git push origin HEAD:mogo-main` publishes the WHOLE of HEAD,
  // not just the attestation commit. Run this from a branch carrying unrelated work and a
  // one-file refresh silently deploys everything else with it, to the branch GitHub Pages serves.
  // Reported rather than assumed, and never auto-corrected: the safe branch is an operator choice.
  const git = function (args) {
    const r = spawnSync('git', args, { cwd: REPO_ROOT, encoding: 'utf8' });
    return (r.status === 0 && typeof r.stdout === 'string') ? r.stdout.trim() : null;
  };
  const branch = git(['rev-parse', '--abbrev-ref', 'HEAD']);
  const ahead = git(['rev-list', '--count', 'origin/mogo-main..HEAD']);
  const aheadN = ahead === null ? null : Number(ahead);

  if (aheadN === null) {
    console.log('  ! origin/mogo-main is not known locally. Run `git fetch origin` first, so the');
    console.log('    size of the push can be established before you make it.');
  } else if (aheadN > 0) {
    console.log('  ! HEAD (' + branch + ') is ' + aheadN + ' commit(s) ahead of origin/mogo-main.');
    console.log('    Pushing HEAD:mogo-main would publish all ' + aheadN + ' of them plus this refresh,');
    console.log('    to the branch GitHub Pages serves. For a refresh alone, commit it on a branch');
    console.log('    started from origin/mogo-main instead:');
    console.log('      git stash && git checkout -b c1-refresh origin/mogo-main && git stash pop');
  }

  console.log('\n  git add docs/campaigns/C1/C1_INTEGRITY_ATTESTATION.json');
  console.log('  git commit -m "C1: regenerate the campaign integrity attestation (operator-authorized)"');
  console.log('  git push origin HEAD:mogo-main      # the branch GitHub Pages serves');
  console.log('  # wait for the Pages deploy, hard-refresh MOGO, then toggle ALEX ON');
  console.log('\nNothing was committed or pushed. Publication is your decision.');
  process.exit(0);
}

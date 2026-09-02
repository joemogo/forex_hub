#!/usr/bin/env node
'use strict';
// ── ALEX forward-PAPER activation probe (READ-ONLY DIAGNOSTIC) ────────────────────────────────
//
// WHAT THIS ANSWERS, AND ONLY THIS: given the repository artifacts as they stand, would
// toggleAlexGLiveTrading()'s OFF->ON evidence preflight refuse, and for which stated blocker?
//
// It answers that WITHOUT starting the application, without IndexedDB, without network, without
// touching the operator's browser profile, storage, evidence corpus or ledgers. It does not open,
// close, enable or disable anything. Nothing is written anywhere.
//
// HOW IT AVOIDS RESTATING THE APP. The two policy functions are not reimplemented here; their
// declaration text is extracted verbatim from index.html and executed, together with the real
// pinned constants, in a bare VM realm with no globals. If the app's policy changes, this probe
// changes with it or fails loudly -- it cannot drift into describing a policy that no longer
// exists. This is the same source-only-extraction discipline tests/lean_h1_source_factory.js uses.
//
// WHAT IT CANNOT ESTABLISH. The operator's running instance may be served from an origin whose
// docs/campaigns/C1/C1_INTEGRITY_ATTESTATION.json differs from this checkout's, and the browser's
// wall clock is its own. It also evaluates ONLY the campaign-C1 half of the gate: the store-read,
// reconciliation and hash-verification facts live in the operator's IndexedDB and are unavailable
// offline by construction. A PASS here therefore means "C1 does not block"; it never means the
// preflight passes. Paper-trading readiness: not assessed.
//
// Usage:  node scripts/alexg_paper_activation_probe.js [--at <ISO8601>] [--json]

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.resolve(__dirname, '..');
const INDEX = path.join(ROOT, 'index.html');
const ATTESTATION = path.join(ROOT, 'docs/campaigns/C1/C1_INTEGRITY_ATTESTATION.json');

function fail(msg) { console.error('PROBE ERROR: ' + msg); process.exit(2); }

// Extract one `function NAME(` declaration by brace balance. Deliberately layout-specific and
// diagnostic-only: this is not a general JavaScript parser, and it refuses rather than guessing.
function extractFunction(src, name) {
  const needle = 'function ' + name + '(';
  const start = src.indexOf(needle);
  if (start < 0) fail('declaration not found: ' + name);
  if (src.indexOf(needle, start + 1) >= 0) fail('declaration is not unique: ' + name);
  let i = src.indexOf('{', start);
  if (i < 0) fail('no body for: ' + name);
  let depth = 0;
  for (let j = i; j < src.length; j++) {
    const c = src[j];
    if (c === '{') depth++;
    else if (c === '}') { depth--; if (depth === 0) return src.slice(start, j + 1); }
  }
  fail('unbalanced body for: ' + name);
}

// Extract one single-line `const NAME=<literal>;` declaration verbatim (trailing line comment
// included, harmlessly). Refuses on absence or on more than one declaration of the same name.
function extractConst(src, name) {
  const re = new RegExp('^const ' + name + '=.*$', 'mg');
  const all = src.match(re);
  if (!all || !all.length) fail('constant not found: ' + name);
  if (all.length > 1) fail('constant is not uniquely declared: ' + name);
  return all[0];
}

const argv = process.argv.slice(2);
const asJson = argv.includes('--json');
const atIdx = argv.indexOf('--at');
const nowMs = atIdx >= 0 && argv[atIdx + 1] ? Date.parse(argv[atIdx + 1]) : Date.now();
if (!isFinite(nowMs)) fail('--at is not a parseable ISO 8601 timestamp');

const src = fs.readFileSync(INDEX, 'utf8');

const parts = [
  extractConst(src, 'EVIDENCE_C1_ATTESTATION_VERSION'),
  extractConst(src, 'EVIDENCE_C1_MANIFEST_SHA256'),
  extractConst(src, 'EVIDENCE_C1_ATTESTATION_MAX_AGE_MS'),
  extractConst(src, 'EVIDENCE_C1_ATTESTATION_FUTURE_SKEW_MS'),
  extractConst(src, 'EVIDENCE_PREFLIGHT_NAMED_EXCEPTIONS'),
  extractFunction(src, 'evidenceEvaluateCampaignC1Attestation'),
  extractFunction(src, 'evidenceEvaluateForwardPaperGate')
];

// A bare realm: no require, no fetch, no document, no storage. Anything the extracted policy
// needed beyond its own declarations would throw here rather than silently resolve.
const sandbox = { result: null };
vm.createContext(sandbox);
vm.runInContext(parts.join('\n') + '\n', sandbox, { filename: 'index.html:extracted' });

let att = null, attReadError = null;
try { att = JSON.parse(fs.readFileSync(ATTESTATION, 'utf8')); }
catch (e) { attReadError = e.message; }

sandbox.__att = att;
sandbox.__now = nowMs;
vm.runInContext('result = evidenceEvaluateCampaignC1Attestation(__att, __now);', sandbox);
const c1 = sandbox.result;

// The campaign-C1 half of the gate, evaluated on facts that are honestly ABSENT offline. The
// store-derived blockers below are expected and are NOT evidence about the operator's corpus.
sandbox.__facts = {
  checkedAt: new Date(nowMs).toISOString(),
  campaignC1: c1,
  campaignC1Intact: c1.intact
};
vm.runInContext('result = evidenceEvaluateForwardPaperGate(__facts);', sandbox);
const gate = sandbox.result;

const c1Blocker = (gate.blockers || []).filter(function (b) { return b.code === 'CAMPAIGN_C1'; });
const offlineUnknowable = ['NO_RECONCILIATION', 'NO_HASH_VERIFICATION', 'STORE_READ_UNCONFIRMED'];
const otherBlockers = (gate.blockers || []).filter(function (b) {
  return b.code !== 'CAMPAIGN_C1' && offlineUnknowable.indexOf(b.code) < 0;
});

const ageMs = (att && att.generatedAt) ? nowMs - Date.parse(att.generatedAt) : null;
const report = {
  evaluatedAt: new Date(nowMs).toISOString(),
  attestationPath: path.relative(ROOT, ATTESTATION),
  attestationReadError: attReadError,
  attestationGeneratedAt: att ? (att.generatedAt || null) : null,
  attestationAgeHours: ageMs == null ? null : +(ageMs / 3600000).toFixed(2),
  maxAgeHours: vm.runInContext('EVIDENCE_C1_ATTESTATION_MAX_AGE_MS/3600000', sandbox),
  campaignC1Intact: c1.intact,
  campaignC1Reasons: c1.reasons,
  campaignC1BlocksActivation: c1Blocker.length > 0,
  otherOfflineDecidableBlockers: otherBlockers,
  storeFactsNotEvaluatedOffline: offlineUnknowable
};

if (asJson) { console.log(JSON.stringify(report, null, 2)); }
else {
  console.log('ALEX forward-PAPER activation probe (read-only)');
  console.log('  evaluated at            : ' + report.evaluatedAt);
  console.log('  attestation generatedAt : ' + report.attestationGeneratedAt);
  console.log('  attestation age         : ' + report.attestationAgeHours + ' h (policy max ' + report.maxAgeHours + ' h)');
  console.log('  campaign C1 intact      : ' + report.campaignC1Intact);
  console.log('  campaign C1 reasons     : ' + (c1.reasons.length ? c1.reasons.join(', ') : '(none)'));
  console.log('  C1 blocks OFF->ON       : ' + report.campaignC1BlocksActivation);
  console.log('  other offline blockers  : ' + (otherBlockers.length ? otherBlockers.map(function (b) { return b.code; }).join(', ') : '(none)'));
  console.log('  NOT evaluated here      : ' + offlineUnknowable.join(', ') + ' (operator IndexedDB only)');
  console.log('');
  console.log(report.campaignC1BlocksActivation
    ? 'VERDICT: from THIS checkout\'s artifacts, turning ALEX ON would be refused by the evidence'
      + '\n         preflight at CAMPAIGN_C1 before any strategy code runs. This is the gate behaving'
      + '\n         as written, not a defect. Paper-trading readiness: not assessed.'
    : 'VERDICT: campaign C1 does not block. The remaining preflight facts are store-derived and'
      + '\n         cannot be evaluated offline. Paper-trading readiness: not assessed.');
}
process.exit(0);

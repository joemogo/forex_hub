#!/usr/bin/env node
'use strict';
// ══════════════════════════════════════════════════════════════════════════════════════════════
// v12.43.0 — C1 STALENESS IS A WARNING; C1 FAILURE STILL BLOCKS
// ══════════════════════════════════════════════════════════════════════════════════════════════
//
// The change these pin is a DELIBERATE RELAXATION of a safety gate, made at the operator's
// explicit request, so the fixtures are written to catch it relaxing further than intended. Every
// one of the reasons that means "something is wrong with the evidence corpus right now" must still
// block, and the only reason allowed to become advisory is age.
//
// The real functions are extracted verbatim from index.html.
//
// Run:  node tests/run_v143_c1_staleness_policy_tests.js

const fs = require('fs');
const path = require('path');
const vm = require('vm');
const SRC = fs.readFileSync(path.resolve(__dirname, '..', 'index.html'), 'utf8');

function extractFunction(name) {
  const m = new RegExp('(?:async\\s+)?function\\s+' + name + '\\s*\\(').exec(SRC);
  if (!m) throw new Error('not found: ' + name);
  const open = SRC.indexOf('{', m.index);
  let depth = 0, i = open;
  for (; i < SRC.length; i++) {
    if (SRC[i] === '{') depth++;
    else if (SRC[i] === '}') { depth--; if (depth === 0) break; }
  }
  return SRC.slice(m.index, i + 1);
}
function extractConst(name) {
  const re = new RegExp('^const\\s+' + name + '\\s*=.*$', 'm');
  const m = re.exec(SRC);
  if (!m) throw new Error('const not found: ' + name);
  return m[0];
}

const ctx = { console: console, Date: Date, Math: Math, JSON: JSON, isFinite: isFinite,
  Number: Number, Object: Object, Array: Array, String: String };
vm.createContext(ctx);
['EVIDENCE_C1_ATTESTATION_VERSION', 'EVIDENCE_C1_MANIFEST_SHA256',
 'EVIDENCE_C1_ATTESTATION_MAX_AGE_MS', 'EVIDENCE_C1_STALENESS_BLOCKS_TRADING',
 'EVIDENCE_C1_ATTESTATION_HARD_MAX_AGE_MS', 'EVIDENCE_C1_ADVISORY_REASONS',
 'EVIDENCE_C1_ATTESTATION_FUTURE_SKEW_MS', 'EVIDENCE_PREFLIGHT_NAMED_EXCEPTIONS']
  .forEach(function (n) { vm.runInContext(extractConst(n), ctx); });
vm.runInContext(extractFunction('evidenceEvaluateCampaignC1Attestation'), ctx);
vm.runInContext(extractFunction('evidenceEvaluateForwardPaperGate'), ctx);
vm.runInContext(extractFunction('evidenceForwardPaperGateText'), ctx);

const results = [];
function t(name, desc, fn) {
  let pass = false, detail = '';
  try { const r = fn(); pass = !!(r && r.pass); detail = (r && r.detail) || ''; }
  catch (e) { pass = false; detail = 'threw: ' + (e && e.message ? e.message : String(e)); }
  results.push({ name, desc, pass, detail });
}

const HOUR = 3600000, DAY = 24 * HOUR;
const PIN = vm.runInContext('EVIDENCE_C1_MANIFEST_SHA256', ctx);
const VER = vm.runInContext('EVIDENCE_C1_ATTESTATION_VERSION', ctx);
const NOW = Date.parse('2026-09-04T12:00:00Z');

// A healthy attestation, parameterised only by age. Everything else is exactly what the real
// verifier writes on a clean pass.
function att(ageMs, over) {
  return Object.assign({
    attestationVersion: VER, manifestSha256: PIN, verdict: 'VERIFIED',
    artifacts: { total: 33, verified: 33, missing: 0, mismatched: 0, unlisted: 0 },
    missingFiles: [], mismatchedFiles: [], unlistedFiles: [],
    generatedAt: new Date(NOW - ageMs).toISOString(), tool: 'test'
  }, over || {});
}
const evalC1 = function (a, now) { return vm.runInContext('evidenceEvaluateCampaignC1Attestation', ctx)(a, now == null ? NOW : now); };
// The gate needs a reconciliation fact to get past its own unrelated blockers; these fixtures
// only ever assert on the CAMPAIGN_C1 blocker, so the rest is made minimally satisfiable.
function gateWith(c1Eval) {
  const facts = { checkedAt: 'x', reconciliation: { uniqueSourceTrades: 0 },
    hashVerification: { verified: 0, mismatched: 0 }, namedExceptions: [],
    campaignC1: c1Eval, campaignC1Intact: c1Eval.intact, campaignC1Blocking: c1Eval.blocks === true };
  return vm.runInContext('evidenceEvaluateForwardPaperGate', ctx)(facts);
}
const c1Blocked = function (v) { return (v.blockers || []).some(function (b) { return b.code === 'CAMPAIGN_C1'; }); };

// ══ THE CHANGE ════════════════════════════════════════════════════════════════════════════════

t('C1AGE-1', 'A FRESH, PASSING attestation blocks nothing and warns about nothing', function () {
  const e = evalC1(att(1 * HOUR));
  return { pass: e.intact === true && e.blocks === false && e.advisoryReasons.length === 0
      && !c1Blocked(gateWith(e)),
    detail: 'intact=' + e.intact + ' blocks=' + e.blocks + ' advisories=' + e.advisoryReasons.length };
});

t('C1AGE-2', 'THE OPERATOR-REQUESTED CHANGE: an attestation that PASSED but is 3 days old no '
  + 'longer stops trading. It reports STALE_ATTESTATION as an advisory instead', function () {
  const e = evalC1(att(3 * DAY));
  const v = gateWith(e);
  return { pass: e.reasons.indexOf('STALE_ATTESTATION') >= 0 && e.blocks === false
      && e.advisoryReasons.join(',') === 'STALE_ATTESTATION' && !c1Blocked(v)
      && (v.advisories || []).some(function (a) { return a.code === 'STALE_ATTESTATION'; }),
    detail: 'blocks=' + e.blocks + ' advisories=' + e.advisoryReasons.join(',')
      + ' gateBlocked=' + c1Blocked(v) };
});

t('C1AGE-3', 'and `intact` KEEPS ITS ORIGINAL MEANING -- every condition satisfied. A stale '
  + 'attestation is still not intact; the split is additive, so nothing that read this before '
  + 'changed meaning underneath it', function () {
  const e = evalC1(att(3 * DAY));
  return { pass: e.intact === false, detail: 'intact=' + e.intact };
});

t('C1AGE-4', 'THE WARNING IS SHOWN. A pass carrying an advisory says so in the operator text -- a '
  + 'warning nobody sees is not a warning', function () {
  const txt = vm.runInContext('evidenceForwardPaperGateText', ctx)(
    { pass: true, advisories: [{ code: 'STALE_ATTESTATION', detail: 'x' }] });
  return { pass: /PASS/.test(txt) && /STALE_ATTESTATION/.test(txt) && /warning/i.test(txt),
    detail: txt.split('\n')[0] };
});

// ══ WHAT MUST STILL BLOCK ═════════════════════════════════════════════════════════════════════
//
// One fixture per failure mode. These are the whole reason the relaxation is safe, and a future
// edit that widened the advisory list would kill them.

const HARD_FAILURES = [
  ['a MISSING artifact', { artifacts: { total: 33, verified: 32, missing: 1, mismatched: 0, unlisted: 0 } }],
  ['a MISMATCHED hash', { artifacts: { total: 33, verified: 32, missing: 0, mismatched: 1, unlisted: 0 } }],
  ['an UNLISTED artifact', { artifacts: { total: 33, verified: 33, missing: 0, mismatched: 0, unlisted: 1 } }],
  ['a verdict that is not VERIFIED', { verdict: 'FAILED' }],
  ['a manifest that is not the pinned one', { manifestSha256: 'deadbeef' }],
  ['an unsupported attestation version', { attestationVersion: 'mogo.c1-attestation.v0' }],
  ['an EMPTY manifest', { artifacts: { total: 0, verified: 0, missing: 0, mismatched: 0, unlisted: 0 } }],
  ['a VERIFIED verdict contradicted by its own missing list', { missingFiles: ['a.json'] }],
  ['a malformed timestamp', { generatedAt: 'not-a-date' }]
];
HARD_FAILURES.forEach(function (pair, i) {
  t('C1AGE-5.' + (i + 1), 'STILL BLOCKS: ' + pair[0] + ' -- this means something is wrong with the '
    + 'corpus NOW, which is a different fact from the check being old', function () {
    const e = evalC1(att(1 * HOUR, pair[1]));
    return { pass: e.blocks === true && e.advisoryReasons.length === 0 && c1Blocked(gateWith(e)),
      detail: 'blocks=' + e.blocks + ' reasons=' + e.blockingReasons.join(',') };
  });
});

t('C1AGE-6', 'STILL BLOCKS: a FUTURE-DATED attestation. Deliberately not advisory -- that is a '
  + 'broken or forged clock, and it is the one direction that could buy unlimited freshness', function () {
  const e = evalC1(att(-2 * HOUR));
  return { pass: e.blocks === true && e.blockingReasons.indexOf('FUTURE_DATED_ATTESTATION') >= 0
      && e.advisoryReasons.length === 0,
    detail: 'blocking=' + e.blockingReasons.join(',') };
});

t('C1AGE-7', 'STILL BLOCKS: no attestation at all. A fetch that did not happen is never a fact '
  + 'that did', function () {
  const e = evalC1(null);
  return { pass: e.intact === false && (e.blocks === true || e.reasons.indexOf('NO_ATTESTATION') >= 0),
    detail: JSON.stringify(e.reasons) };
});

t('C1AGE-8', 'THE BACKSTOP: past the hard maximum age, staleness blocks again. "Warn instead of '
  + 'block" must not decay into "never checked", and an attestation from months ago is not '
  + 'evidence about anything', function () {
  const hard = vm.runInContext('EVIDENCE_C1_ATTESTATION_HARD_MAX_AGE_MS', ctx);
  const inside = evalC1(att(hard - HOUR));
  const beyond = evalC1(att(hard + HOUR));
  return { pass: inside.blocks === false && beyond.blocks === true
      && beyond.beyondHardMaxAge === true && beyond.blockingReasons.indexOf('STALE_ATTESTATION') >= 0,
    detail: 'inside blocks=' + inside.blocks + ' beyond blocks=' + beyond.blocks };
});

t('C1AGE-9', 'STALENESS PLUS A REAL FAILURE STILL BLOCKS. The advisory path must never rescue an '
  + 'attestation that also has something genuinely wrong with it', function () {
  const e = evalC1(att(3 * DAY, { artifacts: { total: 33, verified: 32, missing: 1, mismatched: 0, unlisted: 0 } }));
  return { pass: e.blocks === true && e.blockingReasons.indexOf('MISSING_ARTIFACTS') >= 0
      && c1Blocked(gateWith(e)),
    detail: 'blocking=' + e.blockingReasons.join(',') + ' advisory=' + e.advisoryReasons.join(',') };
});

t('C1AGE-10', 'ONLY age is ever advisory. If a future edit widens the advisory list, this fails', function () {
  const list = vm.runInContext('EVIDENCE_C1_ADVISORY_REASONS', ctx);
  return { pass: Array.isArray(list) && list.length === 1 && list[0] === 'STALE_ATTESTATION',
    detail: JSON.stringify(list) };
});

t('C1AGE-11', 'THE FLAG REALLY REVERSES IT. Setting EVIDENCE_C1_STALENESS_BLOCKS_TRADING back to '
  + 'true restores the old behaviour exactly -- so this is one constant to change, not a rewrite', function () {
  const alt = { console: console, Date: Date, Math: Math, JSON: JSON, isFinite: isFinite,
    Number: Number, Object: Object, Array: Array, String: String };
  vm.createContext(alt);
  ['EVIDENCE_C1_ATTESTATION_VERSION', 'EVIDENCE_C1_MANIFEST_SHA256',
   'EVIDENCE_C1_ATTESTATION_MAX_AGE_MS', 'EVIDENCE_C1_ATTESTATION_HARD_MAX_AGE_MS',
   'EVIDENCE_C1_ADVISORY_REASONS', 'EVIDENCE_C1_ATTESTATION_FUTURE_SKEW_MS']
    .forEach(function (n) { vm.runInContext(extractConst(n), alt); });
  vm.runInContext('const EVIDENCE_C1_STALENESS_BLOCKS_TRADING=true;', alt);
  vm.runInContext(extractFunction('evidenceEvaluateCampaignC1Attestation'), alt);
  const e = vm.runInContext('evidenceEvaluateCampaignC1Attestation', alt)(att(3 * DAY), NOW);
  return { pass: e.blocks === true && e.advisoryReasons.length === 0
      && e.blockingReasons.indexOf('STALE_ATTESTATION') >= 0,
    detail: 'blocks=' + e.blocks + ' advisories=' + e.advisoryReasons.length };
});

t('C1AGE-12', 'BACKWARD COMPATIBILITY: a caller that supplies only campaignC1Intact -- every '
  + 'fixture and call site written before this split -- gets the OLD rule unchanged, so the '
  + 'relaxation reaches only callers that positively opt in', function () {
  const g = vm.runInContext('evidenceEvaluateForwardPaperGate', ctx);
  const base = { checkedAt: 'x', reconciliation: { uniqueSourceTrades: 0 },
    hashVerification: { verified: 0, mismatched: 0 }, namedExceptions: [] };
  const oldFalse = g(Object.assign({}, base, { campaignC1Intact: false }));
  const oldTrue = g(Object.assign({}, base, { campaignC1Intact: true }));
  return { pass: c1Blocked(oldFalse) === true && c1Blocked(oldTrue) === false,
    detail: 'intact:false blocked=' + c1Blocked(oldFalse) + ' intact:true blocked=' + c1Blocked(oldTrue) };
});

results.forEach(function (r) {
  console.log((r.pass ? 'PASS' : 'FAIL') + ' -- ' + r.name + ': ' + r.desc + (r.detail ? '  [' + r.detail + ']' : ''));
});
const fails = results.filter(function (r) { return !r.pass; }).length;
console.log('---');
console.log(results.length + ' fixtures, ' + (results.length - fails) + ' PASS, ' + fails + ' FAIL');
process.exitCode = fails ? 1 : 0;

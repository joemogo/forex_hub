#!/usr/bin/env node
'use strict';
// Engine-provenance binding: every NEW evidence package records the exact engine artefact that
// produced it. Runs under Node (real crypto.subtle); the osascript suites cannot hash at all.
//
//   node tests/engine_provenance_tests.js            (from the project root)
//
// The browser hands an inline <script>'s text to document.currentScript.textContent while that
// script executes; this harness reproduces that by setting currentScript to the extracted body
// before evaluating it. Whether a REAL browser's textContent equals this extraction is not proven
// here (no browser is driven); scripts/engine_provenance.py states the same assumption.
const fs = require('fs');
const crypto = require('crypto');

const html = fs.readFileSync('./index.html', 'utf8');
const m = html.match(/<script>([\s\S]*?)<\/script>/);
if (!m) { console.log('FAIL -- no inline <script> body in index.html'); process.exit(1); }
const body = m[1];

function stub() {
  return { innerHTML: '', textContent: '', value: '', className: '', style: {}, options: [], width: 100, height: 100,
    disabled: false, checked: false, classList: { add() {}, remove() {}, contains() { return false; }, toggle() {} },
    getContext: () => new Proxy({}, { get: () => () => ({ width: 0 }) }), appendChild() {}, addEventListener() {},
    focus() {}, setSelectionRange() {}, click() {}, files: [], getBoundingClientRect: () => ({ top: 0, left: 0, width: 0, height: 0 }) };
}
function load(currentScript) {
  const els = {}, ls = {};
  globalThis.document = { getElementById: id => (els[id] = els[id] || stub()), querySelector: () => null,
    querySelectorAll: () => [], createElement: () => stub(), addEventListener() {}, visibilityState: 'visible',
    body: { appendChild() {}, removeChild() {} }, activeElement: null, currentScript };
  globalThis.window = { devicePixelRatio: 1 };
  globalThis.localStorage = { getItem: k => (k in ls ? ls[k] : null), setItem: (k, v) => { ls[k] = String(v); },
    removeItem: k => { delete ls[k]; } };
  globalThis.alert = () => {}; globalThis.confirm = () => true;
  globalThis.setTimeout = () => 0; globalThis.clearTimeout = () => {};
  globalThis.setInterval = () => 0; globalThis.clearInterval = () => {};
  globalThis.ResizeObserver = function () { return { observe() {}, disconnect() {} }; };
  globalThis.LightweightCharts = { LineStyle: { Solid: 0, Dashed: 1, Dotted: 2 }, CrosshairMode: { Normal: 0 } };
  globalThis.Notification = undefined; globalThis.indexedDB = undefined;
  globalThis.fetch = () => { throw new Error('no network'); };
  const g = {};
  new Function('g', body + '\n' +
    'g.finalize=evidenceFinalizePackage;g.verify=evidenceVerifyPackageHash;g.validate=evidenceValidatePackage;' +
    'g.provenance=mogoEngineProvenance;g.cfg=RULES_ALEXG.config;g.METHOD=MOGO_ENGINE_PROVENANCE_METHOD;')(g);
  return g;
}

let failures = 0, run = 0;
function check(name, ok, detail) {
  run++;
  console.log((ok ? 'PASS' : 'FAIL') + ' -- ' + name);
  if (!ok) { failures++; console.log('    ' + JSON.stringify(detail)); }
}
const sha = s => crypto.createHash('sha256').update(Buffer.from(s, 'utf8')).digest('hex');
const HEX = /^[0-9a-f]{64}$/;
const epErrors = errs => errs.filter(e => e.indexOf('engineProvenance') === 0);

(async () => {
  // ---- in a browser-like context: the running script is known
  const g = load({ textContent: body });
  const pkg = await g.finalize({ packageId: 'PKG|TEST|1', payload: { a: 1 } });
  const ep = pkg.engineProvenance || {};
  check('P1 a new package records the engine artefact: sha256 of the running inline script text',
    ep.scriptSha256 === sha(body) && ep.scriptProvenance === 'OBSERVED' && ep.method === g.METHOD, ep);
  check('P2 the live configuration identity is recorded (canonical, 64-hex) with its scope',
    HEX.test(String(ep.configSha256)) && ep.configProvenance === 'OBSERVED'
    && JSON.stringify(ep.configScope) === '["RULES_ALEXG.config","RULES_ALEXG_V11.v11Config"]', ep);
  check('P3 the page never claims a commit it cannot know',
    ep.sourceCommit === null && ep.sourceCommitProvenance === 'NOT_KNOWABLE_IN_BROWSER', ep);
  const v = await g.verify(pkg);
  check('P4 the content hash covers the provenance: the finalized package verifies', v.status === 'VERIFIED', v);
  const forged = JSON.parse(JSON.stringify(pkg));
  forged.engineProvenance.scriptSha256 = 'f'.repeat(64);
  const vf = await g.verify(forged);
  check('P5 ...and a provenance edited after finalization no longer verifies', vf.status !== 'VERIFIED', vf);
  const pre = { packageId: 'PKG|TEST|2', engineProvenance: { method: 'KEEP' } };
  await g.finalize(pre);
  check('P6 finalization never overwrites a provenance already present', pre.engineProvenance.method === 'KEEP', pre);
  const before = (await g.provenance()).configSha256;
  const old = g.cfg.minRR; g.cfg.minRR = old + 1;
  const after = (await g.provenance()).configSha256;
  g.cfg.minRR = old;
  check('P7 the configuration identity is taken per package, so a runtime change shows', before !== after && HEX.test(after),
    [before, after]);
  check('P8 a well-formed provenance raises no engineProvenance validation error', epErrors(g.validate(pkg).errors).length === 0,
    g.validate(pkg).errors);
  const bad = (patch) => epErrors(g.validate(Object.assign({}, pkg, { engineProvenance: Object.assign({}, ep, patch) })).errors);
  check('P9 validation refuses a malformed artefact hash', bad({ scriptSha256: 'abc' }).length > 0, bad({ scriptSha256: 'abc' }));
  check('P10 validation refuses a claimed source commit', bad({ sourceCommit: 'af757d30' }).length > 0, bad({ sourceCommit: 'x' }));
  check('P11 validation refuses a provenance label that disagrees with the hash',
    bad({ scriptProvenance: 'UNAVAILABLE' }).length > 0, bad({ scriptProvenance: 'UNAVAILABLE' }));
  check('P12 validation refuses an unknown method', bad({ method: 'GUESS' }).length > 0, bad({ method: 'GUESS' }));
  const legacy = Object.assign({}, pkg); delete legacy.engineProvenance;
  check('P13 a package captured before this release (no provenance) raises no provenance error',
    epErrors(g.validate(legacy).errors).length === 0, g.validate(legacy).errors);

  // ---- where the running script cannot be named (e.g. an offline harness): honest absence
  const h = load(undefined);
  const p2 = await h.finalize({ packageId: 'PKG|TEST|3' });
  check('P14 with no running script the artefact is UNAVAILABLE, never guessed',
    p2.engineProvenance.scriptSha256 === null && p2.engineProvenance.scriptProvenance === 'UNAVAILABLE'
    && epErrors(h.validate(p2).errors).length === 0, p2.engineProvenance);

  // ---- the real call-site condition: a browser sets document.currentScript to null once the
  // inline engine script has finished executing, long before any package is finalized. The artefact
  // must therefore be captured at load; a capture moved to call time would find nothing here.
  const cs = { textContent: body };
  const late = load(cs);
  globalThis.document.currentScript = null;
  const p3 = await late.finalize({ packageId: 'PKG|TEST|4', payload: { b: 2 } });
  check('P15 currentScript cleared after load, before finalization: the stamp still matches the engine script',
    p3.engineProvenance.scriptSha256 === sha(body) && p3.engineProvenance.scriptProvenance === 'OBSERVED'
    && (await late.verify(p3)).status === 'VERIFIED', p3.engineProvenance);

  console.log('---');
  console.log(failures ? 'FAILURES: ' + failures + '/' + run + ' executed'
    : 'ALL ENGINE-PROVENANCE FIXTURES PASSED (' + run + ' executed)');
  process.exit(failures ? 1 : 0);
})().catch(e => { console.log('FAIL -- raised ' + e.stack); process.exit(1); });

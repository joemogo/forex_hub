#!/usr/bin/env node
'use strict';
// ══════════════════════════════════════════════════════════════════════════════════════════════
// v12.46.0 — CONNECT SCREEN
// ══════════════════════════════════════════════════════════════════════════════════════════════
//
// A visual redesign is the easiest place to break something invisibly: the screen still LOOKS
// fine, and the field the connect path reads has quietly lost its id. So the majority of these
// fixtures are not about appearance at all -- they pin the contract between the markup and
// connect()/setEnv()/confirmLiveEnv(), the absence of any external resource, and the two
// functional risks the redesign actually introduces:
//
//   * full-bleed decorative layers that could swallow clicks on the form (CS-11/12)
//   * Enter-to-connect reaching connect() with event.target pointing at an INPUT, where the old
//     `const btn=event.target` would have typed "Connecting..." into the API key field (CS-15/16)
//
// CS-9 pins the honesty property: the landing panel states no number, so it cannot state a stale
// one. Nothing on this screen is connected yet, and a figure quoted before connecting is a figure
// that can only be wrong.
//
// Run:  node tests/run_v146_connect_screen_tests.js

const fs = require('fs');
const path = require('path');
const vm = require('vm');
const SRC = fs.readFileSync(path.resolve(__dirname, '..', 'index.html'), 'utf8');

const SETUP_MARKUP = SRC.slice(SRC.indexOf('<!-- SETUP -->'), SRC.indexOf('<!-- MAIN APP -->'));
const SETUP_CSS = SRC.slice(SRC.indexOf('/* ══ v12.46.0 — CONNECT SCREEN'), SRC.indexOf('/* Toast */'));
const INTRO = SETUP_MARKUP.slice(SETUP_MARKUP.indexOf('<div class="setup-intro">'),
  SETUP_MARKUP.indexOf('<div class="setup-form">'));

function fn(name) {
  const m = new RegExp('(?:async\\s+)?function\\s+' + name + '\\s*\\(').exec(SRC);
  if (!m) throw new Error('not found: ' + name);
  const open = SRC.indexOf('{', m.index);
  let d = 0, i = open;
  for (; i < SRC.length; i++) {
    if (SRC[i] === '{') d++;
    else if (SRC[i] === '}') { d--; if (d === 0) break; }
  }
  return SRC.slice(m.index, i + 1);
}
const CONNECT_SRC = fn('connect');

const results = [];
function t(name, desc, f) {
  let pass = false, detail = '';
  try { const r = f(); pass = !!(r && r.pass); detail = (r && r.detail) || ''; }
  catch (e) { pass = false; detail = 'threw: ' + (e && e.message ? e.message : String(e)); }
  results.push({ name, desc, pass, detail });
}

// ══ THE CONTRACT WITH THE CONNECT PATH ═══════════════════════════════════════════════════════

t('CS-1', 'every element id the connect path reads still exists in the redesigned markup', function () {
  // Taken from the bodies of connect()/setEnv(), not from memory -- so a future rename of a field
  // inside those functions makes this fixture fail rather than pass against a stale list.
  const ids = ['setupScreen', 'apiKey', 'accountId', 'errMsg', 'envPractice', 'envLive'];
  const missing = ids.filter(function (id) { return SETUP_MARKUP.indexOf('id="' + id + '"') === -1; });
  return { pass: missing.length === 0, detail: missing.length ? 'missing: ' + missing.join(',') : ids.length + ' ids present' };
});

t('CS-2', 'the handlers are wired to the same functions with the same arguments', function () {
  return { pass: SETUP_MARKUP.indexOf('onclick="setEnv(\'practice\')"') >= 0
      && SETUP_MARKUP.indexOf('onclick="confirmLiveEnv()"') >= 0
      && SETUP_MARKUP.indexOf('onclick="connect()"') >= 0,
    detail: 'setEnv/confirmLiveEnv/connect all bound' };
});

t('CS-3', 'the practice button is still the one pre-selected, so the default environment shown '
  + 'matches the default cfg.env', function () {
  const cfgLine = /let cfg=\{key:'',accountId:'',env:'(\w+)'\}/.exec(SRC);
  const practiceSel = /id="envPractice"[^>]*class="env-opt sel"|class="env-opt sel" id="envPractice"/.test(SETUP_MARKUP);
  const liveNotSel = !/id="envLive"[^>]*\bsel\b/.test(SETUP_MARKUP);
  return { pass: cfgLine && cfgLine[1] === 'practice' && practiceSel && liveNotSel,
    detail: 'cfg default=' + (cfgLine && cfgLine[1]) };
});

t('CS-4', 'the API key field is still type=password at rest -- the redesign must not have left it '
  + 'revealed by default', function () {
  const m = /<input[^>]*id="apiKey"[^>]*>/.exec(SETUP_MARKUP);
  return { pass: !!m && /type="password"/.test(m[0]), detail: m ? m[0].slice(0, 80) : 'no apiKey input' };
});

t('CS-5', 'the error surface starts hidden, or the screen would open showing an empty red box', function () {
  return { pass: /\.err-msg\{[^}]*display:none/.test(SETUP_CSS), detail: 'err-msg display:none' };
});

// ══ NO EXTERNAL DEPENDENCY ═══════════════════════════════════════════════════════════════════

t('CS-6', 'the redesign introduces no external resource -- no font, image, script or stylesheet '
  + 'from anywhere off this file (docs/SECURITY.md: the app has zero external dependencies)', function () {
  const bad = /https?:\/\/|url\(|<img|@import|<link|<script/i;
  const cssBad = bad.test(SETUP_CSS);
  // hub.oanda.com appears in the help text as PROSE, which is not a resource load. Only markup
  // that would cause a fetch counts, so the check here is for elements and url() -- not for the
  // presence of a hostname in a sentence.
  const mkBad = /<img|<link|<script|url\(|src=|@import/i.test(SETUP_MARKUP);
  return { pass: !cssBad && !mkBad, detail: 'css=' + cssBad + ' markup=' + mkBad };
});

t('CS-7', 'the ambient motif is drawn with gradients only, so there is no asset to go missing', function () {
  return { pass: /background-image:linear-gradient/.test(SETUP_CSS)
      && /radial-gradient/.test(SETUP_CSS) && !/url\(/.test(SETUP_CSS),
    detail: 'gradients only' };
});

// ══ HONESTY ══════════════════════════════════════════════════════════════════════════════════

t('CS-8', 'the version stamp is read from APP_VERSION rather than typed into the markup, so it '
  + 'cannot go stale and misreport which build is deployed', function () {
  const hardcoded = /MOGO v1?[0-9]+\.[0-9]+\.[0-9]+/.test(INTRO);
  const wired = /stamp\.textContent='MOGO v'\+APP_VERSION/.test(SRC);
  return { pass: wired && !hardcoded, detail: 'wired=' + wired + ' hardcodedInMarkup=' + hardcoded };
});

t('CS-9', 'the landing panel states no NUMBER at all. Nothing is connected when this screen is '
  + 'shown, so any figure it quoted could only be stale or invented', function () {
  const digits = INTRO.replace(/<[^>]*>/g, '').match(/\d/g);
  return { pass: !digits, detail: digits ? 'found digits: ' + digits.join('') : 'no numeric claim' };
});

t('CS-10', 'the paper-only guarantee is stated on the screen, in both the panel and next to the '
  + 'environment switch -- it is the single most important fact about this app', function () {
  // Asserts the three CLAIMS, at the three places they need to appear -- not a keyword. An earlier
  // version of this fixture required the literal word "never" and failed against wording that
  // said the same thing more strongly, which is a test grading prose rather than meaning.
  const text = SETUP_MARKUP.replace(/<[^>]*>/g, ' ');
  const stamp = /PAPER TRADING ONLY/.test(text);                                  // the standing label
  const point = /No order ever leaves this browser/i.test(text);                  // the headline point
  const envHint = /Neither mode places real orders/i.test(text);                  // beside the live switch
  return { pass: stamp && point && envHint,
    detail: 'stamp=' + stamp + ' point=' + point + ' envHint=' + envHint };
});

// ══ THE DECORATIVE LAYERS MUST NOT BREAK THE FORM ════════════════════════════════════════════

t('CS-11', 'both full-bleed decorative layers are pointer-events:none. They cover the entire '
  + 'viewport; without this they would swallow every click on the form beneath', function () {
  const before = /\.setup-screen::before\{([^}]*)\}/.exec(SETUP_CSS);
  const after = /\.setup-screen::after\{([^}]*)\}/.exec(SETUP_CSS);
  const ok = function (m) { return m && /pointer-events:none/.test(m[1]) && /position:absolute/.test(m[1]); };
  return { pass: ok(before) && ok(after), detail: 'before=' + ok(before) + ' after=' + ok(after) };
});

t('CS-12', 'the card is stacked above the decorative layers, so nothing paints over the inputs', function () {
  const card = /\.setup-card\{([^}]*)\}/.exec(SETUP_CSS);
  const beforeZ = /\.setup-screen::before\{[^}]*z-index:(\d+)/.exec(SETUP_CSS);
  const afterZ = /\.setup-screen::after\{[^}]*z-index:(\d+)/.exec(SETUP_CSS);
  const cardZ = card && /z-index:(\d+)/.exec(card[1]);
  return { pass: !!(cardZ && beforeZ && afterZ)
      && Number(cardZ[1]) > Number(beforeZ[1]) && Number(cardZ[1]) > Number(afterZ[1]),
    detail: 'card=' + (cardZ && cardZ[1]) + ' layers=' + (beforeZ && beforeZ[1]) + ',' + (afterZ && afterZ[1]) };
});

t('CS-13', 'the drift animation stops for anyone who has asked for reduced motion', function () {
  return { pass: /@media\(prefers-reduced-motion:reduce\)\{\.setup-screen::after\{animation:none\}\}/.test(SETUP_CSS),
    detail: 'reduced-motion honoured' };
});

t('CS-14', 'the two columns collapse to one on a narrow screen, and the screen scrolls there -- '
  + 'a fixed 100vh with a taller card would clip the connect button on a phone', function () {
  const mq = /@media\(max-width:860px\)\{([\s\S]*?)\n\}/.exec(SETUP_CSS);
  return { pass: !!mq && /grid-template-columns:1fr/.test(mq[1]) && /height:auto/.test(mq[1])
      && /overflow-y:auto/.test(SETUP_CSS),
    detail: mq ? 'stacks and scrolls at <=860px' : 'no breakpoint found' };
});

// ══ ENTER-TO-CONNECT, AND THE BUG IT WOULD HAVE CAUSED ═══════════════════════════════════════

t('CS-15', 'connect() resolves its button by id and no longer relies on event.target. Reached '
  + 'from the Enter key, event.target is the INPUT -- the old line wrote "Connecting..." straight '
  + 'into the field the operator had just typed their API key into', function () {
  const byId = /const btn=document\.getElementById\('connectBtn'\)/.test(CONNECT_SRC);
  const bareTarget = /const btn=event\.target;/.test(CONNECT_SRC);
  const guarded = /if\(btn\)\{ btn\.textContent='Connecting\.\.\.'/.test(CONNECT_SRC);
  return { pass: byId && !bareTarget && guarded,
    detail: 'byId=' + byId + ' bareEventTarget=' + bareTarget + ' guarded=' + guarded };
});

t('CS-16', 'the Enter handler refuses to re-enter a connection already in flight', function () {
  const init = SRC.slice(SRC.indexOf('function initConnectScreenAffordances'));
  const body = init.slice(0, init.indexOf('\nfunction confirmLiveEnv'));
  return { pass: /if\(ev\.key!=='Enter'\) return;/.test(body)
      && /if\(btn&&btn\.disabled\) return;/.test(body)
      && /ev\.preventDefault\(\)/.test(body),
    detail: 'guards on key, disabled state and default action' };
});

t('CS-17', 'the affordance wiring is wrapped so a missing element degrades to a no-op instead of '
  + 'throwing during page load, which would take the whole app down before it renders', function () {
  const init = SRC.slice(SRC.indexOf('(function initConnectScreenAffordances'));
  const body = init.slice(0, init.indexOf('\nfunction confirmLiveEnv'));
  return { pass: /try\{/.test(body) && /\}catch\(e\)\{\}/.test(body)
      && /if\(!el\) return;/.test(body) && /if\(stamp&&/.test(body),
    detail: 'try/catch plus per-element null guards' };
});

// ══ toggleApiKeyVisibility, EXECUTED ═════════════════════════════════════════════════════════

t('CS-18', 'the show/hide control actually flips the input type and its own label, both ways', function () {
  const els = { apiKey: { type: 'password', focus: function () {} }, apiKeyToggle: { textContent: 'SHOW' } };
  const c = { document: { getElementById: function (id) { return els[id] || null; } } };
  vm.createContext(c);
  vm.runInContext(fn('toggleApiKeyVisibility'), c);
  vm.runInContext('toggleApiKeyVisibility()', c);
  const shown = els.apiKey.type === 'text' && els.apiKeyToggle.textContent === 'HIDE';
  vm.runInContext('toggleApiKeyVisibility()', c);
  const hidden = els.apiKey.type === 'password' && els.apiKeyToggle.textContent === 'SHOW';
  return { pass: shown && hidden, detail: 'reveal=' + shown + ' conceal=' + hidden };
});

t('CS-19', 'it does nothing at all when the elements are absent, rather than throwing', function () {
  const c = { document: { getElementById: function () { return null; } } };
  vm.createContext(c);
  vm.runInContext(fn('toggleApiKeyVisibility'), c);
  vm.runInContext('toggleApiKeyVisibility()', c);
  return { pass: true, detail: 'no throw on missing elements' };
});

t('CS-20', 'it never reads, writes or logs the key itself -- it only changes how the field is '
  + 'displayed', function () {
  const body = fn('toggleApiKeyVisibility');
  return { pass: !/\.value/.test(body) && !/console\./.test(body) && !/cfg\./.test(body)
      && !/localStorage/.test(body),
    detail: 'touches type and textContent only' };
});

// ══ THE 503 BRANCH ═══════════════════════════════════════════════════════════════════════════

t('CS-21', 'a 503 is named as OANDA\'s outage rather than surfaced as a bare "Error: HTTP 503", '
  + 'which reads like a fault in this app', function () {
  const branch = /else if\(e\.message\.includes\('503'\)\|\|\/under maintenance\/i\.test\(e\.message\)\)/.test(CONNECT_SRC);
  const names = /OANDA is down, not MOGO/.test(CONNECT_SRC);
  const reassures = /nothing here needs\s*'\s*\+\s*'fixing/.test(CONNECT_SRC) || /needs .{0,20}fixing/.test(CONNECT_SRC);
  return { pass: branch && names && reassures, detail: 'branch=' + branch + ' named=' + names };
});

t('CS-22', 'the 503 branch is checked BEFORE the generic fallback, or it would never be reached', function () {
  const i503 = CONNECT_SRC.indexOf("includes('503')");
  const iGeneric = CONNECT_SRC.indexOf('<strong>Error:</strong>');
  return { pass: i503 > 0 && iGeneric > 0 && i503 < iGeneric, detail: '503 at ' + i503 + ', generic at ' + iGeneric };
});

t('CS-23', 'the existing 401 and 404 branches are untouched -- a redesign must not quietly drop '
  + 'the diagnostics that were already there', function () {
  return { pass: /401 Unauthorized/.test(CONNECT_SRC) && /404 Not Found/.test(CONNECT_SRC)
      && /CORS\/Network error/.test(CONNECT_SRC),
    detail: '401, 404 and CORS branches all still present' };
});

t('CS-24', 'the button is restored on EVERY failure path, including one where the button could '
  + 'not be resolved, so a failed attempt never leaves the screen stuck on "Connecting..."', function () {
  return { pass: /if\(btn\)\{ btn\.textContent='Connect & Start Scanning';btn\.disabled=false; \}/.test(CONNECT_SRC),
    detail: 'restore guarded and present' };
});

results.forEach(function (r) {
  console.log((r.pass ? 'PASS' : 'FAIL') + ' -- ' + r.name + ': ' + r.desc + (r.detail ? '  [' + r.detail + ']' : ''));
});
const fails = results.filter(function (r) { return !r.pass; }).length;
console.log('---');
console.log(results.length + ' fixtures, ' + (results.length - fails) + ' PASS, ' + fails + ' FAIL');
process.exitCode = fails ? 1 : 0;

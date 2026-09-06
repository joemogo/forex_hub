#!/usr/bin/env node
'use strict';
// ══════════════════════════════════════════════════════════════════════════════════════════════
// v12.55.0 — WIDENING ALEX'S LIVE INSTRUMENT SET, WITHOUT WIDENING ANYTHING ELSE
// ══════════════════════════════════════════════════════════════════════════════════════════════
//
// Measured: ALEX produces 0.44 forward trades per pair-week (31 LIVE_CLOSE trades / 41 days /
// 12 pairs). Sample size is what blocks every open question in this project, and instrument count
// scales the rate near-linearly because ALEX's only concurrency limit is one open trade per
// pair+timeframe. 12 pairs puts a decisive sample ~2.3 years out; 28 puts it near 1.
//
// The obvious change -- edit SCAN_PAIRS -- is the wrong one, and PAIRS-7..9 and PAIRS-11 exist to
// stop it being made later. SCAN_PAIRS is read by THREE other consumers that must not grow:
//   * JVM auto-trading (0% win rate, losing money -- widening it multiplies a loss)
//   * the manual Scan tab (one operator-graded row per pair; a hand-entry task)
//   * every "replay all pairs" loop (2.3x slower runs; replay is not sample-starved)
//
// So this release adds a SEPARATE list and rewires only ALEX's live path to it. These fixtures
// pin the split in both directions: the live path MUST have moved, and the other three MUST NOT.
//
// PAIRS-3 is the one that catches a typo turning into a silent no-trade instrument: a pair not
// present in ALL_PAIRS is not a valid OANDA identifier, and would fail fetch forever while the
// ledger counted it as configured -- inflating the denominator of every coverage figure.
//
// PAIRS-14 parses the WHOLE page script. v12.54.0 shipped 28 passing fixtures over a page that
// was dead on load, because every other fixture extracts one function into a fresh realm and a
// collision BETWEEN declarations is invisible to all of them.
//
// Run:  node tests/run_v155_alexg_live_pairs_tests.js

const fs = require('fs');
const path = require('path');
const vm = require('vm');
const ROOT = path.resolve(__dirname, '..');
const SRC = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');

// Read an array/object `const` as a VALUE in a fresh realm. A `const` in a vm context is a lexical
// binding, NOT a property of the context object -- reading ctx.NAME returns undefined, and a regex
// then tests the string "undefined" and passes vacuously. This defect was hit twice this cycle
// (v145, v149); vm.runInContext is the only correct read.
function constValue(decl, name) {
  const i = SRC.indexOf(decl);
  if (i < 0) throw new Error('not found: ' + decl);
  let depth = 0, q = null, k = i;
  for (; k < SRC.length; k++) {
    const c = SRC[k], p = SRC[k - 1];
    if (q) { if (c === q && p !== '\\') q = null; continue; }
    if (c === '"' || c === "'" || c === '`') { q = c; continue; }
    if (c === '/' && SRC[k + 1] === '/') { while (k < SRC.length && SRC[k] !== '\n') k++; continue; }
    if (c === '(' || c === '[' || c === '{') depth++;
    else if (c === ')' || c === ']' || c === '}') depth--;
    else if (c === ';' && depth === 0) break;
  }
  const ctx = {}; vm.createContext(ctx);
  vm.runInContext(SRC.slice(i, k + 1), ctx);
  return vm.runInContext(name, ctx);
}

const LIVE = constValue('const ALEXG_LIVE_PAIRS=', 'ALEXG_LIVE_PAIRS');
const SCAN = constValue('const SCAN_PAIRS=', 'SCAN_PAIRS');
const ALL = constValue('const ALL_PAIRS=', 'ALL_PAIRS');

const EXOTICS = ['USD_SGD', 'USD_NOK', 'USD_SEK', 'USD_DKK', 'USD_MXN', 'USD_ZAR', 'USD_TRY'];
const u = function (p) { return String(p).replace('/', '_'); };

const results = [];
function t(name, desc, f) {
  let pass = false, detail = '';
  try { const r = f(); pass = !!(r && r.pass); detail = (r && r.detail) || ''; }
  catch (e) { pass = false; detail = 'threw: ' + (e && e.message ? e.message : String(e)); }
  results.push({ name, desc, pass, detail });
}

// ══ THE LIST ITSELF ══════════════════════════════════════════════════════════════════════════

t('PAIRS-1', 'the live set is a STRICT SUPERSET of SCAN_PAIRS -- every instrument ALEX traded '
  + 'before it must still trade, or this release silently drops live coverage while claiming to '
  + 'add it', function () {
  const missing = SCAN.filter(function (p) { return LIVE.indexOf(p) === -1; });
  return { pass: missing.length === 0 && LIVE.length > SCAN.length,
    detail: missing.length ? 'DROPPED: ' + missing.join(',') : SCAN.length + ' -> ' + LIVE.length + ' pairs, none dropped' };
});

t('PAIRS-2', 'exotics are excluded. Entry spread already costs a measured 9.8% of risk on majors '
  + 'and is materially worse on these -- they would add cost drag, not information', function () {
  const found = LIVE.filter(function (p) { return EXOTICS.indexOf(u(p)) !== -1; });
  return { pass: found.length === 0, detail: found.length ? 'PRESENT: ' + found.join(',') : 'none of the 7 exotics present' };
});

t('PAIRS-3', 'every entry maps to an identifier that actually exists in ALL_PAIRS. A typo here is '
  + 'not a crash -- it is an instrument that fails fetch forever while the ledger counts it as '
  + 'configured, inflating the denominator of every coverage figure', function () {
  const bad = LIVE.filter(function (p) { return ALL.indexOf(u(p)) === -1; });
  return { pass: bad.length === 0, detail: bad.length ? 'NOT IN ALL_PAIRS: ' + bad.join(',') : 'all ' + LIVE.length + ' resolve' };
});

t('PAIRS-4', 'no duplicates -- a repeated pair would be evaluated twice per tick and double-count '
  + 'in instrumentsConfigured', function () {
  const seen = {}, dup = [];
  LIVE.forEach(function (p) { if (seen[p]) dup.push(p); seen[p] = 1; });
  return { pass: dup.length === 0, detail: dup.length ? 'DUPLICATES: ' + dup.join(',') : LIVE.length + ' unique' };
});

t('PAIRS-5', 'the list uses the SLASH form SCAN_PAIRS uses, because every consumer calls '
  + '.replace("/","_") on it -- an underscore-form entry would silently stay underscored and miss', function () {
  const bad = LIVE.filter(function (p) { return String(p).indexOf('/') === -1; });
  return { pass: bad.length === 0, detail: bad.length ? 'NOT SLASH FORM: ' + bad.join(',') : 'all slash-form' };
});

t('PAIRS-6', 'the widened set is materially larger -- a change that added one or two pairs would '
  + 'not move the sample-size problem and is not what this release claims', function () {
  const ratio = LIVE.length / SCAN.length;
  return { pass: LIVE.length >= 24 && ratio >= 2.0,
    detail: LIVE.length + ' pairs, ' + ratio.toFixed(2) + 'x the scanned set' };
});

// ══ ALEX'S LIVE PATH MOVED ═══════════════════════════════════════════════════════════════════

t('PAIRS-7', 'the live poll loop iterates the WIDENED set. This is the single line that produces '
  + 'the extra trades; everything else in this release is bookkeeping around it', function () {
  return { pass: /for\(const pair of ALEXG_LIVE_PAIRS\)\{/.test(SRC)
      && !/for\(const pair of SCAN_PAIRS\)\{[\s\S]{0,400}alexGEvaluatePairForLiveSetups/.test(SRC),
    detail: 'alexGLivePollTick iterates ALEXG_LIVE_PAIRS' };
});

t('PAIRS-8', 'BOTH poll-ledger sites report the widened count. A tick that evaluates 28 and '
  + 'reports 12 configured makes every coverage percentage wrong by a factor of 2.3', function () {
  const n = (SRC.match(/instrumentsConfigured:ALEXG_LIVE_PAIRS\.length/g) || []).length;
  const old = (SRC.match(/instrumentsConfigured:SCAN_PAIRS\.length/g) || []).length;
  return { pass: n === 2 && old === 0, detail: n + ' sites on the live set, ' + old + ' left on SCAN_PAIRS' };
});

t('PAIRS-9', 'the NOT_REACHED_THIS_TICK sweep accounts for the widened set, or the 16 added pairs '
  + 'would be neither evaluated nor recorded as skipped -- they would simply vanish from the ledger', function () {
  const i = SRC.indexOf('__obsAccounted[x.pair]=1;');
  const after = i < 0 ? '' : SRC.slice(i, i + 260);
  return { pass: i >= 0 && /ALEXG_LIVE_PAIRS\.forEach/.test(after) && /NOT_REACHED_THIS_TICK/.test(after),
    detail: i < 0 ? 'sweep not found' : 'sweep iterates ALEXG_LIVE_PAIRS' };
});

t('PAIRS-10', 'the ALEX manifest declares what ALEX actually trades. The manifest is the '
  + 'strategy\'s public statement of its own instrument set and must not describe the old one', function () {
  const i = SRC.indexOf("strategyName:'ALEX'");
  const blk = i < 0 ? '' : SRC.slice(i, i + 700);
  return { pass: i >= 0 && /instruments:ALEXG_LIVE_PAIRS\.slice\(\)/.test(blk),
    detail: i < 0 ? 'ALEX manifest not found' : 'declares ALEXG_LIVE_PAIRS' };
});

// ══ EVERYTHING ELSE STAYED PUT -- THE FIXTURES THAT CATCH THE TEMPTING CHANGE ════════════════

t('PAIRS-11', 'JVM auto-trade eligibility still filters SCAN_PAIRS. JVM is at a 0% win rate and '
  + 'losing money -- widening its instrument set would multiply a known loss and teach nothing. '
  + 'This is the most important negative fixture in the file', function () {
  const i = SRC.indexOf('const eligible=SCAN_PAIRS.filter(pair=>{');
  const blk = i < 0 ? '' : SRC.slice(i, i + 300);
  return { pass: i >= 0 && /paperAccount\.openPositions/.test(blk),
    detail: i < 0 ? 'JVM eligibility NOT on SCAN_PAIRS -- it was widened' : 'JVM still on SCAN_PAIRS' };
});

t('PAIRS-12', 'the JVM manifest still declares SCAN_PAIRS, matching what JVM actually trades', function () {
  const i = SRC.indexOf('logicFingerprint:jvmLogic.hash');
  const blk = i < 0 ? '' : SRC.slice(i, i + 400);
  return { pass: i >= 0 && /instruments:SCAN_PAIRS\.slice\(\)/.test(blk),
    detail: i < 0 ? 'JVM manifest not found' : 'JVM manifest still SCAN_PAIRS' };
});

t('PAIRS-13', 'the manual Scan tab still renders one row per SCAN_PAIRS entry. These are graded by '
  + 'hand -- more than doubling that table is a chore the operator did not ask for', function () {
  return { pass: /document\.getElementById\('scan-tbody'\)\.innerHTML=SCAN_PAIRS\.map/.test(SRC),
    detail: 'scan-tbody still renders SCAN_PAIRS' };
});

t('PAIRS-14', 'the replay-all loops still iterate SCAN_PAIRS. Replay is not sample-starved -- '
  + 'forward trading is -- so widening replay buys nothing and makes every run 2.3x longer', function () {
  const n = (SRC.match(/SCAN_PAIRS\.length/g) || []).length;
  return { pass: /for\(let p=0;p<SCAN_PAIRS\.length;p\+\+\)/.test(SRC)
      && /for\(let i=0;i<SCAN_PAIRS\.length;i\+\+\)/.test(SRC) && n >= 4,
    detail: 'replay-all loops unchanged; ' + n + ' SCAN_PAIRS.length reads remain' };
});

// ══ THE WHOLE PAGE STILL PARSES ══════════════════════════════════════════════════════════════

t('PAIRS-15', 'the ENTIRE page script parses. v12.54.0 shipped 28 green fixtures over a page that '
  + 'was dead on load -- a duplicate top-level declaration is invisible to every fixture that '
  + 'extracts one function into its own realm', function () {
  const m = SRC.match(/<script>([\s\S]*?)<\/script>/g) || [];
  let total = 0;
  m.forEach(function (blk) {
    const js = blk.replace(/^<script>/, '').replace(/<\/script>$/, '');
    if (!js.trim()) return;
    total += js.length;
    new Function(js); // throws on a duplicate declaration or a syntax error
  });
  return { pass: total > 100000, detail: 'parsed ' + m.length + ' script block(s), ' + total.toLocaleString() + ' chars' };
});

t('PAIRS-16', 'the live set is declared BEFORE the poll tick that reads it. A const read before '
  + 'its lexical declaration is a TDZ ReferenceError at runtime, and would kill every tick', function () {
  const decl = SRC.indexOf('const ALEXG_LIVE_PAIRS=');
  const use = SRC.indexOf('for(const pair of ALEXG_LIVE_PAIRS)');
  return { pass: decl >= 0 && use > decl, detail: 'declared at ' + decl + ', first loop use at ' + use };
});

// ══ REPORT ═══════════════════════════════════════════════════════════════════════════════════

let pass = 0;
results.forEach(function (r) {
  if (r.pass) pass++;
  console.log((r.pass ? '  PASS  ' : '  FAIL  ') + r.name + '  ' + r.desc);
  if (r.detail) console.log('          ' + r.detail);
});
console.log('\n  ' + pass + ' / ' + results.length + ' passed');
process.exit(pass === results.length ? 0 : 1);

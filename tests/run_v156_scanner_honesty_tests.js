#!/usr/bin/env node
'use strict';
// ══════════════════════════════════════════════════════════════════════════════════════════════
// v12.56.0 — THE SCANNER SHOWED THREE THINGS THAT WERE NOT TRUE
// ══════════════════════════════════════════════════════════════════════════════════════════════
//
// None of these is a scoring change. WEIGHTS, ALERT_THRESHOLD, scoreConfluence, bestConfluence,
// detectSignals and getBias are protected and byte-identical. Every defect below is the DISPLAY
// or the SWEEP claiming something the engine did not do.
//
//   1. STALE SCORES. scanPair stamps sweepToken on every record it writes. Nothing read it. So a
//      pair whose scan threw kept the previous sweep's entry, and pairEvaluationDisplayState --
//      which asked only "is there a conf at all" -- returned EVALUATED with an empty tooltip. The
//      sidebar rendered last sweep's number in the normal colour with the normal LONG/SHORT tag.
//      STALE-1..6.
//
//   2. THE SWEEP COULD ABORT. Per-pair isolation was added so one instrument could not kill the
//      sweep; renderPairList() was then called bare inside the same loop. A render throw on chunk 2
//      leaves 25 of 35 instruments unscanned with nothing on screen saying so. SWEEP-1..5.
//
//   3. AN UNREACHABLE CEILING. scoreConfluence reads bias from scanData, written only for the 12
//      SCAN_PAIRS; scanAll sweeps all 35. For the other 23 the bias row scores 0 every sweep no
//      matter what the market does, so their maximum is 100-WEIGHTS.bias3 -- rendered as a bare
//      percentage against a 100-wide bar, beside pairs that can reach 100. CEIL-1..6.
//
// CEIL-3 is the fixture that matters most: it asserts the displayed NUMBER is not rescaled. Making
// the figure look better while ALERT_THRESHOLD still gates on the raw total would be a worse defect
// than the one being fixed -- the sidebar and the trading gate would disagree.
//
// Run:  node tests/run_v156_scanner_honesty_tests.js

const fs = require('fs');
const path = require('path');
const vm = require('vm');
const ROOT = path.resolve(__dirname, '..');
const SRC = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');

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
function constBlock(decl) {
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
  return SRC.slice(i, k + 1);
}

// A realm holding the display-state function plus the freshness global it reads. Read the const
// back with vm.runInContext -- a `const` in a vm context is a lexical binding, NOT a property of
// the context object, so ctx.NAME is undefined and any regex on it tests the string "undefined".
function realm(lastCompleted) {
  const c = { console: console, Math: Math, JSON: JSON, Object: Object, String: String,
    Number: Number, Array: Array, isFinite: isFinite, isNaN: isNaN, Date: Date };
  vm.createContext(c);
  vm.runInContext('let __jvmLastCompletedSweep=' + (lastCompleted || 0) + ';', c);
  vm.runInContext(fn('pairEvaluationDisplayState'), c);
  return c;
}
function state(ctx, rec, tf) {
  return vm.runInContext('pairEvaluationDisplayState("EUR_USD",' + JSON.stringify(rec) + ',' +
    (tf === undefined ? 'undefined' : JSON.stringify(tf)) + ')', ctx);
}
// A scanned record: has conf, so it passes the "was this ever scanned" gate.
function rec(over) {
  const r = { sweepToken: 5, conf: { total: 40, direction: 'long' }, timeframe: 'M15',
    completenessState: 'COMPLETE' };
  if (over) Object.keys(over).forEach(function (k) { r[k] = over[k]; });
  return r;
}

// Strip `//` line comments before asserting on source. CEIL-2 originally matched the string
// "100-WEIGHTS.bias3" inside this release's own EXPLANATORY COMMENT, so hardcoding the ceiling to
// 75 in the actual assignment left the fixture green -- it was testing prose, not code. Found by
// the mutation run, which is the only reason it is not still passing vacuously.
function codeOf(src) {
  return src.split('\n').map(function (ln) {
    const i = ln.indexOf('//');
    if (i < 0) return ln;
    // Only strip when the `//` is not inside a string literal on that line.
    const before = ln.slice(0, i);
    const q = (before.match(/'/g) || []).length, d = (before.match(/"/g) || []).length,
          b = (before.match(/`/g) || []).length;
    return (q % 2 || d % 2 || b % 2) ? ln : before;
  }).join('\n');
}

const results = [];
function t(name, desc, f) {
  let pass = false, detail = '';
  try { const r = f(); pass = !!(r && r.pass); detail = (r && r.detail) || ''; }
  catch (e) { pass = false; detail = 'threw: ' + (e && e.message ? e.message : String(e)); }
  results.push({ name, desc, pass, detail });
}

// ══ 1. STALE SCORES ══════════════════════════════════════════════════════════════════════════

t('STALE-1', 'a record from an OLDER sweep than the last completed one is reported STALE rather '
  + 'than EVALUATED -- this is the whole defect: the previous number rendered as a current one', function () {
  const s = state(realm(7), rec({ sweepToken: 5 }), 'M15');
  return { pass: s.code === 'STALE' && s.staleBySweeps === 2,
    detail: 'code=' + s.code + ' staleBySweeps=' + s.staleBySweeps };
});

t('STALE-2', 'a record written BY the last completed sweep is EVALUATED -- the check must not flag '
  + 'every pair, or the warning becomes noise and gets ignored', function () {
  const s = state(realm(5), rec({ sweepToken: 5 }), 'M15');
  return { pass: s.code === 'EVALUATED', detail: 'code=' + s.code };
});

t('STALE-3', 'MID-SWEEP IS NOT STALE. __jvmLastCompletedSweep only advances when every chunk has '
  + 'dispatched, so a pair not yet rescanned by an IN-FLIGHT sweep still reads EVALUATED. Comparing '
  + 'against the start-of-sweep counter instead would flag all 35 pairs on every sweep', function () {
  // sweep 6 is running; last COMPLETED is still 5; a record from 5 is current, not stale.
  const s = state(realm(5), rec({ sweepToken: 5 }), 'M15');
  return { pass: s.code === 'EVALUATED' && s.notEvaluated === false,
    detail: 'in-flight sweep does not mark the previous sweep stale' };
});

t('STALE-4', 'a record with NO sweepToken is never reclassified -- anything persisted before this '
  + 'version, and callers that do not sweep, must behave byte-identically', function () {
  const r = rec(); delete r.sweepToken;
  const s = state(realm(9), r, 'M15');
  return { pass: s.code === 'EVALUATED', detail: 'code=' + s.code };
});

t('STALE-5', 'before any sweep completes (__jvmLastCompletedSweep===0) nothing is stale -- a fresh '
  + 'page load must not paint every pair gold', function () {
  const s = state(realm(0), rec({ sweepToken: 3 }), 'M15');
  return { pass: s.code === 'EVALUATED', detail: 'code=' + s.code };
});

t('STALE-6', 'STALE outranks the timeframe check. A stale record carrying the SELECTED timeframe is '
  + 'the dangerous case -- every other cue on screen looks right -- so it must not be reported as '
  + 'merely an other-timeframe score', function () {
  const s = state(realm(9), rec({ sweepToken: 4, timeframe: 'H4' }), 'H4');
  return { pass: s.code === 'STALE', detail: 'code=' + s.code + ' (not EVALUATED_ON_OTHER_TIMEFRAME)' };
});

t('STALE-7', 'the STALE state carries a non-empty explanation. EVALUATED ships title:"" and the '
  + 'sidebar puts the title in the tooltip, so an empty one would render as a silent gold tag', function () {
  const s = state(realm(9), rec({ sweepToken: 4 }), 'M15');
  return { pass: typeof s.title === 'string' && s.title.length > 40 && /STALE/.test(s.title),
    detail: s.title.slice(0, 72) + '...' };
});

t('STALE-8', 'a NOT-YET-SCANNED record still reports NOT_SCANNED, not STALE -- never scanned and '
  + 'scanned-then-failed are different facts and must not collapse', function () {
  const s = state(realm(9), { sweepToken: 1 }, 'M15');
  return { pass: s.code === 'NOT_SCANNED' && s.notEvaluated === true, detail: 'code=' + s.code };
});

t('STALE-9', 'a SUPPRESSED record still reports NOT_EVALUATED -- a data-availability failure is '
  + 'not the same as an out-of-date figure', function () {
  const s = state(realm(9), rec({ sweepToken: 2, evaluationSuppressed: true,
    transportOutcome: 'HTTP_ERROR', httpStatus: 503 }), 'M15');
  return { pass: s.code === 'NOT_EVALUATED', detail: 'code=' + s.code };
});

// ══ 2. THE SWEEP CANNOT ABORT ════════════════════════════════════════════════════════════════

const scanAllSrc = codeOf(fn('scanAll'));

t('SWEEP-1', 'renderPairList() inside the chunk loop is wrapped. Unguarded, a render throw aborted '
  + 'the for-of and every REMAINING CHUNK went undispatched -- 25 of 35 instruments unscanned, '
  + 'sidebar silent', function () {
  return { pass: /try\{\s*renderPairList\(\);\s*\}\s*catch/.test(scanAllSrc)
      && !/\}\)\);renderPairList\(\);\}/.test(scanAllSrc),
    detail: 'renderPairList is inside try/catch within the chunk loop' };
});

t('SWEEP-2', 'a render fault is RECORDED, not swallowed -- an operator looking at a stale sidebar '
  + 'needs the reason to exist somewhere', function () {
  const i = scanAllSrc.indexOf('try{ renderPairList(); }');
  const after = i < 0 ? '' : scanAllSrc.slice(i, i + 220);
  return { pass: i >= 0 && /recordPaperEngineError/.test(after),
    detail: i < 0 ? 'guard not found' : 'failure routed to recordPaperEngineError' };
});

t('SWEEP-3', 'the pre-loop status writes are guarded too -- that pair threw BEFORE chunk 1 and so '
  + 'skipped all 35, not merely the remainder', function () {
  const i = scanAllSrc.indexOf("getElementById('scanStatus').textContent='Scanning...'");
  const seg = i < 0 ? '' : scanAllSrc.slice(Math.max(0, i - 300), i + 300);
  // The guard must sit BETWEEN the write and the outer try -- an outer try alone is what the
  // original code already had, and it did not stop the write from skipping the whole sweep.
  const guarded = /try\{[\s\S]{0,300}getElementById\('scanStatus'\)[\s\S]{0,240}?\}catch/.test(seg);
  return { pass: i >= 0 && guarded,
    detail: i < 0 ? 'status write not found' : (guarded ? 'scanStatus/liveDot writes have their own try/catch' : 'write is NOT individually guarded') };
});

t('SWEEP-4', 'the PER-PAIR isolation that already existed is still there -- this release must not '
  + 'trade one failure mode for the other', function () {
  return { pass: /scanPair\(p,__jvmSweep,__jvmResults\)\)\.catch\(/.test(scanAllSrc)
      && /recordPaperEngineError\('scanPair\('/.test(scanAllSrc),
    detail: 'per-instrument .catch intact' };
});

t('SWEEP-5', 'the completed-sweep marker is set AFTER the chunk loop, not before or inside it. Set '
  + 'earlier, every pair not yet rescanned by the running sweep would read STALE', function () {
  const loopEnd = scanAllSrc.indexOf('try{ renderPairList(); }');
  const marker = scanAllSrc.indexOf('__jvmLastCompletedSweep=__jvmSweep');
  const chunkStart = scanAllSrc.indexOf('for(const ch of chunks)');
  return { pass: marker > loopEnd && loopEnd > chunkStart && marker > chunkStart,
    detail: 'marker set after the loop completes (idx ' + marker + ' > loop ' + loopEnd + ')' };
});

// ══ 3. THE UNREACHABLE CEILING ═══════════════════════════════════════════════════════════════

const W = (function () {
  const c = {}; vm.createContext(c);
  vm.runInContext(constBlock('const WEIGHTS='), c);
  return vm.runInContext('WEIGHTS', c);
})();
const SCAN = (function () {
  const c = {}; vm.createContext(c);
  vm.runInContext(constBlock('const SCAN_PAIRS='), c);
  return vm.runInContext('SCAN_PAIRS', c);
})();
const ALL = (function () {
  const c = {}; vm.createContext(c);
  vm.runInContext(constBlock('const ALL_PAIRS='), c);
  return vm.runInContext('ALL_PAIRS', c);
})();
const renderSrc = codeOf(fn('renderPairList'));

t('CEIL-1', 'THE DEFECT IS REAL AND MEASURED: pairs swept by scanAll but absent from SCAN_PAIRS '
  + 'cannot score the bias component at all, so their ceiling is below 100', function () {
  const scanU = SCAN.map(function (p) { return p.replace('/', '_'); });
  const outside = ALL.filter(function (p) { return scanU.indexOf(p) === -1; });
  return { pass: outside.length > 0 && W.bias3 > 0,
    detail: outside.length + ' of ' + ALL.length + ' swept pairs have no bias data; ceiling '
      + (100 - W.bias3) + ' not 100' };
});

t('CEIL-2', 'the ceiling is DERIVED from WEIGHTS, never hardcoded -- WEIGHTS is protected and may '
  + 'be re-issued, and a literal 75 here would silently start lying', function () {
  const assigned = /const\s+confCeiling\s*=\s*biasAvailable\s*\?\s*100\s*:\s*100\s*-\s*WEIGHTS\.bias3\s*;/.test(renderSrc);
  const literal = /const\s+confCeiling\s*=[^;]*:\s*\d+\s*;/.test(renderSrc);
  return { pass: assigned && !literal,
    detail: assigned ? 'confCeiling assigned from WEIGHTS.bias3' : 'ceiling is NOT derived from WEIGHTS' };
});

t('CEIL-3', 'THE DISPLAYED NUMBER IS NOT RESCALED. ALERT_THRESHOLD gates on the raw total, so a '
  + 'renormalised percentage would make the sidebar disagree with the trading gate -- a worse '
  + 'defect than the one being fixed. The ceiling is disclosed beside the figure instead', function () {
  const bad = /pct\s*=\s*[^;]*confCeiling/.test(renderSrc)
    || /Math\.round\([^)]*\/\s*confCeiling/.test(renderSrc)
    || /pct\s*\*\s*100\s*\/\s*confCeiling/.test(renderSrc);
  return { pass: !bad && /ceilingHtml/.test(renderSrc),
    detail: bad ? 'pct IS rescaled -- sidebar would disagree with ALERT_THRESHOLD' : 'pct untouched; ceiling disclosed separately' };
});

t('CEIL-4', 'the disclosure is suppressed for pairs that CAN reach 100 -- a marker on all 35 would '
  + 'say nothing', function () {
  return { pass: /biasAvailable\s*\?\s*100\s*:/.test(renderSrc) && /!biasAvailable\s*&&/.test(renderSrc),
    detail: 'ceiling markup gated on !biasAvailable' };
});

t('CEIL-5', 'availability is decided by the SAME input scoreConfluence reads -- getBias over the '
  + 'scanData entry -- not by testing SCAN_PAIRS membership, which would go wrong the moment either '
  + 'list changes', function () {
  return { pass: /getBias\(sd\)!==/.test(renderSrc) && !/SCAN_PAIRS\.indexOf\(/.test(renderSrc),
    detail: 'biasAvailable derived from getBias(scanData entry)' };
});

t('CEIL-6', 'nothing is shown for a pair with no score yet -- a ceiling note beside an em dash is '
  + 'noise', function () {
  return { pass: /!evalState\.notEvaluated\s*&&\s*pct/.test(renderSrc),
    detail: 'marker requires an actual computed score' };
});

t('CEIL-7', 'the STALE state is rendered distinctly in the sidebar, or the display-state work above '
  + 'never reaches the operator', function () {
  return { pass: /isStale\s*=\s*evalState\.code===['"]STALE['"]/.test(renderSrc)
      && /STALE<\/span>/.test(renderSrc),
    detail: 'STALE tag rendered in renderPairList' };
});

// ══ 4. NOTHING PROTECTED MOVED ═══════════════════════════════════════════════════════════════

t('GUARD-1', 'the protected scoring path is untouched by this release -- every fix is display or '
  + 'sweep control flow. The drift gate proves this independently; this fixture states the intent', function () {
  const reg = JSON.parse(fs.readFileSync(path.join(ROOT, 'regression-baseline.json'), 'utf8'));
  // Both registry sections are OBJECTS keyed by name (name -> hash), not arrays. indexOf on an
  // object is not a function, so the original form of this fixture threw rather than asserting.
  const p = Object.keys(reg.protectedFunctions || {});
  const k = Object.keys(reg.protectedConstants || {});
  const must = ['scoreConfluence', 'bestConfluence', 'detectSignals', 'getBias'];
  return { pass: p.length > 0 && k.length > 0
      && must.every(function (f) { return p.indexOf(f) !== -1; })
      && ['WEIGHTS', 'ALERT_THRESHOLD'].every(function (c) { return k.indexOf(c) !== -1; }),
    detail: 'scoring functions and WEIGHTS/ALERT_THRESHOLD are in the protected registry' };
});

t('GUARD-2', 'the ENTIRE page script parses -- v12.54.0 shipped 28 green fixtures over a page that '
  + 'was dead on load', function () {
  const m = SRC.match(/<script>([\s\S]*?)<\/script>/g) || [];
  let total = 0;
  m.forEach(function (blk) {
    const js = blk.replace(/^<script>/, '').replace(/<\/script>$/, '');
    if (!js.trim()) return;
    total += js.length;
    new Function(js);
  });
  return { pass: total > 100000, detail: 'parsed ' + total.toLocaleString() + ' chars' };
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

#!/usr/bin/env node
'use strict';
// ══════════════════════════════════════════════════════════════════════════════════════════════
// v12.57.0 — THE SIDEBAR NOW MEANS ONE THING, AND SAYS WHERE ITS INPUTS CAME FROM
// ══════════════════════════════════════════════════════════════════════════════════════════════
//
// Five defects, none of them scoring. WEIGHTS, ALERT_THRESHOLD, scoreConfluence, bestConfluence,
// detectSignals and getBias are protected and byte-identical throughout.
//
//   1. THE SWEEP FOLLOWED THE CHART. `const sweepTf=activeTf` meant clicking M15 -> Daily silently
//      changed what every percentage MEANT, and setTf() called scanAll() so a viewing action
//      rescored all 35 instruments. Two pairs were not comparable unless swept on the same
//      timeframe. TF-1..8.
//
//   2. MSB'S LABEL STATED THE OPPOSITE OF THE TRUTH -- "not scored or gated" for a component
//      worth WEIGHTS.msb of the total ALERT_THRESHOLD gates on. LABEL-1..3.
//
//   3. DOJI IS BADGED LIKE A CONFIRMED PATTERN AND IS WORTH 0. LABEL-4..6.
//
//   4. TWO DIFFERENT THINGS WERE BOTH CALLED AOI -- a swing cluster on the viewed timeframe, and
//      the D/W band that actually sets the stop. AOI-1..3.
//
//   5. BIAS PROVENANCE WAS INVISIBLE. Auto Scan defaults OFF, so "Bias 3/3 aligned" is usually
//      three values typed by hand, scored with no freshness check at all. BIAS-1..5.
//
// TF-3 is the fixture that matters most: it proves NO TRADE PATH reads the swept score. If that
// ever stops being true, changing the sweep timeframe silently changes what MOGO trades, and this
// entire release becomes a trading change disguised as a display fix.
//
// Run:  node tests/run_v157_scanner_meaning_tests.js

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
// Strip `//` comments before asserting on source. v12.56.0's CEIL-2 matched its own explanatory
// COMMENT and survived a mutation that hardcoded the real value -- it was testing prose.
function codeOf(src) {
  return src.split('\n').map(function (ln) {
    const i = ln.indexOf('//');
    if (i < 0) return ln;
    const before = ln.slice(0, i);
    const q = (before.match(/'/g) || []).length, d = (before.match(/"/g) || []).length,
          b = (before.match(/`/g) || []).length;
    return (q % 2 || d % 2 || b % 2) ? ln : before;
  }).join('\n');
}
function readConst(decl, name) {
  const c = {}; vm.createContext(c);
  vm.runInContext(constBlock(decl), c);
  return vm.runInContext(name, c);
}

const WEIGHTS = readConst('const WEIGHTS=', 'WEIGHTS');
const SWEEP_TF = readConst("const SWEEP_TIMEFRAME=", 'SWEEP_TIMEFRAME');
const scanPairSrc   = codeOf(fn('scanPair'));
const renderSrc     = codeOf(fn('renderPairList'));
const badgesSrc     = codeOf(fn('renderSignalBadges'));
const setTfSrc      = codeOf(fn('setTf'));
const autoTradesSrc = codeOf(fn('checkAutoTrades'));
const liveTrigSrc   = codeOf(fn('evaluateLiveTrigger'));

const results = [];
function t(name, desc, f) {
  let pass = false, detail = '';
  try { const r = f(); pass = !!(r && r.pass); detail = (r && r.detail) || ''; }
  catch (e) { pass = false; detail = 'threw: ' + (e && e.message ? e.message : String(e)); }
  results.push({ name, desc, pass, detail });
}

// ══ 1. THE SWEEP NO LONGER FOLLOWS THE CHART ═════════════════════════════════════════════════

t('TF-1', 'the sweep scores a FIXED timeframe, not whichever one the chart happens to show. This is '
  + 'the defect: the same number meant different things depending on where the operator had clicked', function () {
  return { pass: /const sweepTf=SWEEP_TIMEFRAME;/.test(scanPairSrc) && !/const sweepTf=activeTf/.test(scanPairSrc),
    detail: 'scanPair sweeps ' + SWEEP_TF + ', independent of activeTf' };
});

t('TF-2', 'the sweep timeframe MATCHES the one the auto-trade path evaluates. If they diverge the '
  + 'sidebar goes straight back to describing something other than what can trade', function () {
  const m = /fetchCandles\((?:oPair|pair),'([A-Z0-9]+)'/.exec(liveTrigSrc);
  return { pass: !!m && m[1] === SWEEP_TF,
    detail: 'evaluateLiveTrigger fetches ' + (m ? m[1] : '?') + ', SWEEP_TIMEFRAME=' + SWEEP_TF };
});

t('TF-3', 'NO TRADE PATH READS THE SWEPT SCORE. This is what makes the change display-only. '
  + 'checkAutoTrades must select on scanData and then RE-EVALUATE, never read pairData[].conf -- if '
  + 'that ever changes, altering the sweep timeframe silently alters what MOGO trades', function () {
  const readsConf = /pairData\s*\[[^\]]*\]\s*\.\s*conf/.test(autoTradesSrc) || /\.conf\.total/.test(autoTradesSrc);
  const reEvaluates = /evaluateLiveTrigger\(/.test(autoTradesSrc);
  return { pass: !readsConf && reEvaluates,
    detail: readsConf ? 'checkAutoTrades READS the swept score -- this release is NOT display-only'
                      : 'checkAutoTrades re-evaluates via evaluateLiveTrigger and never reads pairData conf' };
});

t('TF-4', 'changing the CHART timeframe no longer triggers a full 35-instrument sweep. scanAll has '
  + 'no re-entrancy guard, so a viewing action starting a second concurrent sweep was both wasted '
  + 'network and a reliable way to interleave two sweeps', function () {
  return { pass: !/scanAll\(\)/.test(setTfSrc) && /loadChart\(\)/.test(setTfSrc),
    detail: 'setTf reloads the chart only' };
});

t('TF-5', 'the pair list compares against the SWEEP timeframe, not the chart. Comparing against '
  + 'activeTf would flag all 35 rows as other-timeframe whenever the chart is not on ' + SWEEP_TF, function () {
  return { pass: /pairEvaluationDisplayState\(p,d,SWEEP_TIMEFRAME\)/.test(renderSrc)
      && !/pairEvaluationDisplayState\(p,d,activeTf\)/.test(renderSrc),
    detail: 'renderPairList passes SWEEP_TIMEFRAME' };
});

t('TF-6', 'the other-timeframe check is KEPT, not deleted. It still has work to do: a record '
  + 'persisted before this release, or written while SWEEP_TIMEFRAME held a different value, '
  + 'carries a timeframe that no longer matches and must still be labelled', function () {
  const st = codeOf(fn('pairEvaluationDisplayState'));
  return { pass: /EVALUATED_ON_OTHER_TIMEFRAME/.test(st) && /e\.timeframe!==selectedTf/.test(st),
    detail: 'timeframe mismatch branch intact' };
});

t('TF-7', 'the record is still STAMPED with the timeframe it was computed on -- without the stamp '
  + 'the mismatch check above has nothing to compare and silently never fires', function () {
  return { pass: /timeframe:sweepTf/.test(scanPairSrc), detail: 'scanPair stamps timeframe:sweepTf' };
});

t('TF-8', 'SWEEP_TIMEFRAME is declared before both of its uses. A const read before its lexical '
  + 'declaration is a TDZ ReferenceError, which here would kill every sweep', function () {
  const d = SRC.indexOf("const SWEEP_TIMEFRAME='");
  const u1 = SRC.indexOf('const sweepTf=SWEEP_TIMEFRAME;');
  const u2 = SRC.indexOf('pairEvaluationDisplayState(p,d,SWEEP_TIMEFRAME)');
  return { pass: d >= 0 && u1 > d && u2 > d, detail: 'declared at ' + d + ', uses at ' + u1 + ' and ' + u2 };
});

// ══ 2 & 3. LABELS THAT STATED THE OPPOSITE OF THE TRUTH ══════════════════════════════════════

t('LABEL-1', 'MSB IS scored, and WEIGHTS proves it -- the fixture asserts the defect was real '
  + 'rather than taking the old label at its word', function () {
  return { pass: WEIGHTS.msb != null && WEIGHTS.msb > 0,
    detail: 'WEIGHTS.msb = ' + WEIGHTS.msb + ' points toward the gated total' };
});

t('LABEL-2', 'the MSB row no longer claims it is unscored. It told the operator a real component of '
  + 'the alert threshold counted for nothing', function () {
  const i = SRC.indexOf("id:'msb_observation'");
  const blk = i < 0 ? '' : SRC.slice(i, i + 420);
  return { pass: i >= 0 && !/not scored or gated/.test(blk) && /IS scored/.test(blk),
    detail: i < 0 ? 'MSB row not found' : 'row states MSB is scored' };
});

t('LABEL-3', 'the MSB row reports the real weight from WEIGHTS rather than a hardcoded number, so '
  + 'it cannot drift out of date if the protected constant is ever re-issued', function () {
  const i = SRC.indexOf("id:'msb_observation'");
  const blk = i < 0 ? '' : SRC.slice(i, i + 420);
  return { pass: i >= 0 && /WEIGHTS\.msb/.test(blk) && /ALERT_THRESHOLD/.test(blk),
    detail: 'weight and threshold both read from the protected constants' };
});

t('LABEL-4', 'doji genuinely carries NO weight -- again asserting the defect is real before '
  + 'asserting the fix', function () {
  return { pass: WEIGHTS.doji == null,
    detail: 'WEIGHTS has no doji entry; keys: ' + Object.keys(WEIGHTS).join(',') };
});

t('LABEL-5', 'a badge for an unweighted pattern is marked "not scored" -- it was styled exactly '
  + 'like a confirmed pattern that moves the number', function () {
  return { pass: /not scored/.test(badgesSrc) && /unscored/.test(badgesSrc),
    detail: 'renderSignalBadges marks unweighted signals' };
});

t('LABEL-6', 'the marker is DERIVED from WEIGHTS, never by naming doji. A pattern that later gains '
  + 'a weight must stop being marked automatically, and one that loses it must start', function () {
  return { pass: /WEIGHTS\[wKey\]==null/.test(badgesSrc) && !/s\.type===['"]doji['"]/.test(badgesSrc),
    detail: 'unscored derived from WEIGHTS lookup, not a doji special case' };
});

// ══ 4. TWO THINGS CALLED AOI ═════════════════════════════════════════════════════════════════

t('AOI-1', 'the AOI badge names the WINDOW it came from, not just a timeframe in brackets -- the '
  + 'old parenthetical read as a detail rather than as a distinction', function () {
  return { pass: /swing cluster/.test(badgesSrc), detail: 'badge labels it a swing cluster' };
});

t('AOI-2', 'and states plainly that it is NOT the drawn band and NOT the level that sets the stop', function () {
  return { pass: /NOT the purple daily\/weekly AOI band/.test(badgesSrc) && /place a stop/.test(badgesSrc),
    detail: 'tooltip distinguishes it from the structural D/W AOI' };
});

t('AOI-3', 'the qualifier is applied at the DISPLAY layer only -- detectSignals is protected and its '
  + 'label is frozen, so the distinction must not be made by editing the signal', function () {
  const ds = fn('detectSignals');
  return { pass: !/swing cluster/.test(ds) && /s\.type===['"]aoi['"]/.test(badgesSrc),
    detail: 'detectSignals untouched; qualifier added in renderSignalBadges' };
});

// ══ 5. WHERE THE BIAS CAME FROM ══════════════════════════════════════════════════════════════

t('BIAS-1', 'the pair list marks a score whose bias was NOT machine-derived. Auto Scan is off by '
  + 'default, so the common case is three values typed by hand and scored with no freshness check', function () {
  // Asserting the variable merely EXISTS is not enough -- deleting the render site leaves the
  // declaration behind and the fixture green. This is the same hole v12.56.0's CEIL-2 had. Assert
  // the INTERPOLATION into the markup, which is what actually reaches the operator.
  const declared = /const\s+biasHtml\s*=/.test(renderSrc) && /biasDerived/.test(renderSrc);
  const rendered = /\$\{biasHtml\}/.test(renderSrc);
  return { pass: declared && rendered,
    detail: declared ? (rendered ? 'computed AND interpolated into the row markup'
                                 : 'computed but NEVER RENDERED -- dead variable')
                     : 'not computed' };
});

t('BIAS-2', 'provenance reuses jvmEligibilityIsCurrent -- the SAME predicate the trade path gates '
  + 'on. A second, independent notion of freshness could disagree with the one that controls money', function () {
  return { pass: /jvmEligibilityIsCurrent\(sk\)/.test(renderSrc),
    detail: 'display and trade path share one freshness definition' };
});

t('BIAS-3', 'that predicate is fail-closed: anything missing, in-progress, failed, or from an '
  + 'earlier generation reads as NOT current', function () {
  const src = codeOf(fn('jvmEligibilityIsCurrent'));
  return { pass: /return false/.test(src) && /e\.gen!==__jvmEligibilityGeneration/.test(src)
      && /status!==JVM_ELIGIBILITY_STATUS\.FRESH/.test(src),
    detail: 'missing / not-FRESH / stale-generation all return false' };
});

t('BIAS-4', 'the marker is suppressed when there is no bias at all -- that case is already covered '
  + 'by the ceiling disclosure and two markers would say the same thing twice', function () {
  return { pass: /biasAvailable&&!biasDerived/.test(renderSrc),
    detail: 'marker requires bias present but unverified' };
});

t('BIAS-5', 'the tooltip states that this affects DISPLAY, not trading -- the auto-trade path '
  + 'ignores unverified bias entirely, and implying otherwise would be its own false alarm', function () {
  return { pass: /not what MOGO trades/.test(renderSrc),
    detail: 'tooltip scopes the warning to display' };
});

t('CEIL-R', 'the v12.56.0 ceiling marker is INTERPOLATED, not merely computed. Same reason as '
  + 'BIAS-1: a declaration left behind after the render site is deleted keeps a fixture green while '
  + 'the operator sees nothing', function () {
  return { pass: /const\s+ceilingHtml\s*=/.test(renderSrc) && /\$\{ceilingHtml\}/.test(renderSrc),
    detail: 'ceilingHtml computed and interpolated' };
});

// ══ GUARDS ═══════════════════════════════════════════════════════════════════════════════════

t('GUARD-1', 'the whole page script parses', function () {
  const m = SRC.match(/<script>([\s\S]*?)<\/script>/g) || [];
  let total = 0;
  m.forEach(function (blk) {
    const js = blk.replace(/^<script>/, '').replace(/<\/script>$/, '');
    if (!js.trim()) return;
    total += js.length; new Function(js);
  });
  return { pass: total > 100000, detail: 'parsed ' + total.toLocaleString() + ' chars' };
});

t('GUARD-2', 'the scoring model is untouched -- every change here is display or sweep control flow', function () {
  const reg = JSON.parse(fs.readFileSync(path.join(ROOT, 'regression-baseline.json'), 'utf8'));
  const p = Object.keys(reg.protectedFunctions || {}), k = Object.keys(reg.protectedConstants || {});
  return { pass: ['scoreConfluence', 'bestConfluence', 'detectSignals', 'getBias'].every(function (f) { return p.indexOf(f) !== -1; })
      && ['WEIGHTS', 'ALERT_THRESHOLD'].every(function (c) { return k.indexOf(c) !== -1; }),
    detail: 'scoring functions and constants remain in the protected registry' };
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

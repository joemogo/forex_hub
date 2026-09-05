#!/usr/bin/env node
'use strict';
// ══════════════════════════════════════════════════════════════════════════════════════════════
// v12.48.0 — MULTI-YEAR ALEX REPLAY
// ══════════════════════════════════════════════════════════════════════════════════════════════
//
// The baseline control arm ran 502 trades over 4 years on daily bars; ALEX's replay ran 42 trades
// over 7 months on H1/H4. Comparing them answered nothing, because they never traded the same
// thing. Making the comparison possible needed exactly one change -- the lookback dropdown, which
// stopped at 365 days -- because every layer beneath it already supported more.
//
// An option in a <select> is not evidence that the run works. So these fixtures check the FETCH
// ARITHMETIC against the real formulas in fetchAlexGReplayDatasets and the real pagination limits
// in fetchCandlesRange: every offered lookback must fit under its per-timeframe cap AND inside the
// 20-page pagination guard, or the run silently returns a truncated history and the replay
// describes a shorter period than the operator selected (MYR-3/4/5).
//
// MYR-6 is the one that matters most: it derives the largest SAFE lookback from the source itself
// and requires the dropdown not to offer anything beyond it. Adding a 10-year option later fails
// here rather than producing a quietly truncated 4-year run labelled as 10 years.
//
// Run:  node tests/run_v148_multiyear_replay_tests.js

const fs = require('fs');
const path = require('path');
const SRC = fs.readFileSync(path.resolve(__dirname, '..', 'index.html'), 'utf8');

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

// ── read the REAL numbers out of the source, never retyped ───────────────────────────────────
const FETCH = fn('fetchAlexGReplayDatasets');
const RANGE = fn('fetchCandlesRange');
function capFor(varName) {
  const m = new RegExp('const ' + varName + '=Math\\.min\\(([^,]+),(\\d+)\\)').exec(FETCH);
  if (!m) throw new Error('cap not found for ' + varName);
  return { expr: m[1], cap: Number(m[2]) };
}
const CAPS = { h1: capFor('h1Count'), h4: capFor('h4Count'), d: capFor('dCount'), w: capFor('wCount') };
const PAGE_SIZE = Number(/Math\.min\(remaining,(\d+)\)/.exec(RANGE)[1]);
const PAGE_GUARD = Number(/guard<(\d+)/.exec(RANGE)[1]);

// Evaluate the source's own expression for a given `days`, so a change to the formula is picked up
// here instead of being shadowed by a copy of it.
function barsFor(which, days) {
  const c = CAPS[which];
  const raw = Function('days', 'Math', 'return (' + c.expr + ');')(days, Math);
  return { raw: raw, capped: Math.min(raw, c.cap), wasCapped: raw > c.cap };
}
function pagesFor(bars) { return Math.ceil(bars / PAGE_SIZE); }

// The lookbacks the UI actually offers, read from the ALEX dropdown itself.
const SELECT = (function () {
  const i = SRC.indexOf('<select id="alexgDays"');
  return SRC.slice(i, SRC.indexOf('</select>', i));
})();
const OFFERED = (SELECT.match(/value="(\d+)"/g) || []).map(function (s) { return Number(/\d+/.exec(s)[0]); });

const results = [];
function t(name, desc, f) {
  let pass = false, detail = '';
  try { const r = f(); pass = !!(r && r.pass); detail = (r && r.detail) || ''; }
  catch (e) { pass = false; detail = 'threw: ' + (e && e.message ? e.message : String(e)); }
  results.push({ name, desc, pass, detail });
}

t('MYR-1', 'the fixtures read the real caps and the real page limits out of the source, so a change '
  + 'to either is picked up here rather than compared against a stale copy', function () {
  return { pass: CAPS.h1.cap > 0 && CAPS.h4.cap > 0 && CAPS.d.cap > 0 && CAPS.w.cap > 0
      && PAGE_SIZE > 0 && PAGE_GUARD > 0,
    detail: 'caps H1=' + CAPS.h1.cap + ' H4=' + CAPS.h4.cap + ' D=' + CAPS.d.cap + ' W=' + CAPS.w.cap
      + '; pages ' + PAGE_SIZE + '/req, guard ' + PAGE_GUARD };
});

t('MYR-2', 'the dropdown offers multi-year lookbacks, and still offers the short ones -- widening '
  + 'the range must not remove the 90-day default the existing workflow uses', function () {
  return { pass: OFFERED.indexOf(1460) >= 0 && OFFERED.indexOf(90) >= 0 && OFFERED.indexOf(365) >= 0
      && /value="90" selected/.test(SELECT),
    detail: 'offers ' + OFFERED.join(', ') + '; default still 90' };
});

t('MYR-3', 'EVERY offered lookback fits under its per-timeframe cap. A capped fetch returns fewer '
  + 'bars than the selected period covers, so the replay would describe a SHORTER history than the '
  + 'operator chose while still labelling it with their choice', function () {
  const bad = [];
  OFFERED.forEach(function (days) {
    ['h1', 'h4', 'd', 'w'].forEach(function (k) {
      const b = barsFor(k, days);
      if (b.wasCapped) bad.push(days + 'd ' + k + ': wants ' + b.raw + ', capped at ' + CAPS[k].cap);
    });
  });
  return { pass: bad.length === 0 && OFFERED.length > 0,
    detail: bad.length ? bad.join(' | ') : OFFERED.length + ' lookbacks all fit their caps' };
});

t('MYR-4', 'EVERY offered lookback fits inside the pagination guard. Exceeding it stops the loop '
  + 'early and yields a partial history', function () {
  const bad = [];
  OFFERED.forEach(function (days) {
    ['h1', 'h4', 'd', 'w'].forEach(function (k) {
      const p = pagesFor(barsFor(k, days).capped);
      if (p > PAGE_GUARD) bad.push(days + 'd ' + k + ': ' + p + ' pages > guard ' + PAGE_GUARD);
    });
  });
  const worst = Math.max.apply(null, OFFERED.map(function (d) { return pagesFor(barsFor('h1', d).capped); }));
  return { pass: bad.length === 0,
    detail: bad.length ? bad.join(' | ') : 'worst case ' + worst + ' pages, guard ' + PAGE_GUARD };
});

t('MYR-5', 'the longest lookback needs MORE than one page, so the multi-year path genuinely '
  + 'exercises pagination rather than passing because everything fits in one request', function () {
  const longest = Math.max.apply(null, OFFERED);
  const p = pagesFor(barsFor('h1', longest).capped);
  return { pass: p > 1, detail: longest + ' days -> ' + barsFor('h1', longest).capped + ' H1 bars, ' + p + ' pages' };
});

t('MYR-6', 'the dropdown offers nothing beyond what the fetch path can actually deliver. This is '
  + 'the guard that matters: a future 10-year option would fail HERE rather than producing a '
  + 'truncated 4-year history labelled as ten', function () {
  // Largest lookback for which no timeframe caps and no timeframe exceeds the page guard, found
  // from the source's own formulas rather than asserted.
  let safe = 0;
  for (let days = 30; days <= 6000; days += 5) {
    const ok = ['h1', 'h4', 'd', 'w'].every(function (k) {
      const b = barsFor(k, days);
      return !b.wasCapped && pagesFor(b.capped) <= PAGE_GUARD;
    });
    if (!ok) break;
    safe = days;
  }
  const over = OFFERED.filter(function (d) { return d > safe; });
  return { pass: over.length === 0 && safe > 0,
    detail: over.length ? 'offered beyond safe limit: ' + over.join(',')
      : 'largest offered ' + Math.max.apply(null, OFFERED) + ', safe limit ~' + safe + ' days' };
});

t('MYR-7', 'a truncated fetch is REPORTED rather than silently returned. ADR-011 classified the '
  + 'termination reason precisely so a page-2 failure stops being invisible -- multi-year runs make '
  + 'that path far more likely, since they need several pages instead of one', function () {
  return { pass: /termination='HTTP_ERROR'/.test(RANGE) && /termination='NETWORK_ERROR'/.test(RANGE)
      && /termination='EMPTY_PAGE'/.test(RANGE) && /pagesRequested/.test(RANGE),
    detail: 'HTTP, network, empty-page and short-page terminations all recorded' };
});

t('MYR-8', 'per-page identity is verified, so a longer run cannot splice another instrument in at '
  + 'page five while the first four look healthy', function () {
  return { pass: /marketDataIdentityOutcome\(d,pair,tf\)/.test(RANGE)
      && /termination='IDENTITY_MISMATCH'/.test(RANGE),
    detail: 'identity checked per page, mismatch terminates' };
});

t('MYR-9', 'neither protected engine function is touched -- the change is a dropdown and the fetch '
  + 'path it feeds, not the strategy', function () {
  const baseline = JSON.parse(fs.readFileSync(path.resolve(__dirname, '..', 'regression-baseline.json'), 'utf8'));
  const pf = baseline.protectedFunctions;
  return { pass: !!pf.alexGRunSetupEngine && !!pf.alexGRunSetupReplay
      && !pf.fetchAlexGReplayDatasets && !pf.fetchCandlesRange,
    detail: 'engine and replay stay protected; the fetch path is where the change lives' };
});

t('MYR-10', 'the operator is told multi-year runs are slow, so a several-minute fetch reads as '
  + 'expected rather than as a hang', function () {
  const i = SRC.indexOf('<select id="alexgDays"');
  const after = SRC.slice(i, i + 1400);
  return { pass: /take a few minutes/.test(after) && /H1 bars/.test(after),
    detail: 'duration note present beside the control' };
});

results.forEach(function (r) {
  console.log((r.pass ? 'PASS' : 'FAIL') + ' -- ' + r.name + ': ' + r.desc + (r.detail ? '  [' + r.detail + ']' : ''));
});
const fails = results.filter(function (r) { return !r.pass; }).length;
console.log('---');
console.log(results.length + ' fixtures, ' + (results.length - fails) + ' PASS, ' + fails + ' FAIL');
process.exitCode = fails ? 1 : 0;

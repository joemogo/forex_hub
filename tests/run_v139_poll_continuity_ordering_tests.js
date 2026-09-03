#!/usr/bin/env node
'use strict';
// ══════════════════════════════════════════════════════════════════════════════════════════
// Characterization: why the forward-observation continuity figures cannot be trusted
// ══════════════════════════════════════════════════════════════════════════════════════════
//
// WHAT THIS IS. Not a repair. It reproduces, against the REAL evidenceSummarizeObservations
// extracted verbatim from index.html, the mechanism behind the operator-visible
// "N interval(s) ran BACKWARDS -- the recorded timeline is not trustworthy for continuity
// arithmetic" warning, and measures what that same mechanism does to the missed-interval count
// sitting beside it.
//
// THE CHAIN, EACH LINK READ FROM SOURCE
//
//   1. startAlexGLivePollingIfNeeded uses setInterval(alexGLivePollTick, 60000) and there is no
//      in-flight guard anywhere -- the missing poll re-entrancy guard already on the backlog.
//   2. alexGLivePollTick stamps __obsStartedAt at ENTRY and writes its POLL record from the
//      `finally` block, at COMPLETION.
//   3. evidencePutObservation allocates `seq` at WRITE time
//      (const seq = await evidenceAllocateObservationSeq()), so seq is completion order.
//   4. evidenceSummarizeObservations SORTS BY seq and then DIFFERENCES startedAt.
//
// So a tick slower than its own 60 s period finishes after a later tick, the two records are
// written out of start-time order, and differencing start times along write order yields a
// NEGATIVE interval. The app counts those honestly. What it cannot do is un-inflate the positive
// gap on the other side of the swap, and that gap is counted as missed intervals -- which is the
// finding these fixtures exist to pin.
//
// Run:  node tests/run_v139_poll_continuity_ordering_tests.js

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const INDEX = path.resolve(__dirname, '..', 'index.html');
const src = fs.readFileSync(INDEX, 'utf8');

// Extracted verbatim, never reimplemented: a second copy of this arithmetic would be a second
// source of truth, and the first time they disagreed this file would be describing a function the
// application does not have.
function extractFunction(name) {
  const needle = 'function ' + name + '(';
  const start = src.indexOf(needle);
  if (start < 0) throw new Error('declaration not found: ' + name);
  if (src.indexOf(needle, start + 1) >= 0) throw new Error('declaration not unique: ' + name);
  let depth = 0;
  for (let j = src.indexOf('{', start); j < src.length; j++) {
    if (src[j] === '{') depth++;
    else if (src[j] === '}') { depth--; if (depth === 0) return src.slice(start, j + 1); }
  }
  throw new Error('unbalanced body: ' + name);
}
function extractConst(name) {
  const m = src.match(new RegExp('^const ' + name + '=.*$', 'm'));
  if (!m) throw new Error('constant not found: ' + name);
  return m[0];
}

const sandbox = {};
vm.createContext(sandbox);
vm.runInContext([
  extractConst('EVIDENCE_POLL_EXPECTED_INTERVAL_MS'),
  extractFunction('evidenceSummarizeObservations')
].join('\n'), sandbox, { filename: 'index.html:extracted' });

const MINUTE = 60000;
const T0 = Date.parse('2026-09-01T00:00:00.000Z');
const summarize = function (records, nowMs) {
  sandbox.__recs = records; sandbox.__now = nowMs;
  return vm.runInContext('evidenceSummarizeObservations(__recs, __now)', sandbox);
};
// A POLL record carrying only what the continuity arithmetic reads.
const poll = function (seq, startedAtMs, outcome) {
  return { kind: 'POLL', seq: seq, outcome: outcome || 'OK',
    startedAt: new Date(startedAtMs).toISOString(), instrumentsEvaluated: [] };
};

const results = [];
function t(name, desc, fn) {
  let pass = false, detail = '';
  try { const r = fn(); pass = !!(r && r.pass); detail = (r && r.detail) || ''; }
  catch (e) { pass = false; detail = 'threw: ' + (e && e.message ? e.message : String(e)); }
  results.push({ name, desc, pass, detail });
}

t('PCO-1', 'the extracted function is the real one -- it reads the app’s own 1-minute expected interval', function () {
  const v = vm.runInContext('EVIDENCE_POLL_EXPECTED_INTERVAL_MS', sandbox);
  return { pass: v === MINUTE, detail: String(v) };
});

t('PCO-2', 'POSITIVE CONTROL: ten ticks a minute apart, written in start order, report a clean '
  + 'timeline -- 0 backwards, 0 missed', function () {
  const recs = []; for (let i = 0; i < 10; i++) recs.push(poll(i + 1, T0 + i * MINUTE));
  const s = summarize(recs, T0 + 9 * MINUTE);
  return { pass: s.negativeIntervals === 0 && s.missedIntervals === 0 && s.polls === 10,
    detail: 'neg=' + s.negativeIntervals + ' missed=' + s.missedIntervals };
});

t('PCO-3', 'a genuine outage IS real downtime: one 60-minute gap reports 59 missed intervals and '
  + 'no backwards interval', function () {
  const recs = [poll(1, T0), poll(2, T0 + 60 * MINUTE)];
  const s = summarize(recs, T0 + 60 * MINUTE);
  return { pass: s.negativeIntervals === 0 && s.missedIntervals === 59,
    detail: 'neg=' + s.negativeIntervals + ' missed=' + s.missedIntervals };
});

t('PCO-4', 'THE MECHANISM: one slow tick finishing after the next -- identical start times, only '
  + 'the write order swapped -- turns a clean timeline into a backwards interval', function () {
  // Ticks start at 0,1,2,3 min. Tick #2 is slow and completes after tick #3, so #3 is written
  // first and takes the lower seq. No start time is altered; only completion order differs.
  const clean = [poll(1, T0), poll(2, T0 + MINUTE), poll(3, T0 + 2 * MINUTE), poll(4, T0 + 3 * MINUTE)];
  const swapped = [poll(1, T0), poll(2, T0 + MINUTE), poll(4, T0 + 2 * MINUTE), poll(3, T0 + 3 * MINUTE)];
  const a = summarize(clean, T0 + 3 * MINUTE), b = summarize(swapped, T0 + 3 * MINUTE);
  return {
    pass: a.negativeIntervals === 0 && b.negativeIntervals === 1,
    detail: 'clean neg=' + a.negativeIntervals + ' -> swapped neg=' + b.negativeIntervals
  };
});

t('PCO-5', 'THE FINDING: the same swap also INFLATES the missed-interval count, because the '
  + 'negative gap is clamped to zero while the oversized positive gap beside it is counted in full', function () {
  const clean = [poll(1, T0), poll(2, T0 + MINUTE), poll(3, T0 + 2 * MINUTE), poll(4, T0 + 3 * MINUTE)];
  const swapped = [poll(1, T0), poll(2, T0 + MINUTE), poll(4, T0 + 2 * MINUTE), poll(3, T0 + 3 * MINUTE)];
  const a = summarize(clean, T0 + 3 * MINUTE), b = summarize(swapped, T0 + 3 * MINUTE);
  // Swapped, the seq walk sees startedAt 0 -> 1 -> 3 -> 2 min: a 2-minute gap (1 missed) then a
  // -1 minute gap (clamped to 0). Hand-computed: clean 0 missed, swapped 1 missed.
  return {
    pass: a.missedIntervals === 0 && b.missedIntervals === 1,
    detail: 'clean missed=' + a.missedIntervals + ' -> swapped missed=' + b.missedIntervals
      + '  (downtime invented by reordering alone)'
  };
});

t('PCO-6', 'the wider the reordering, the larger the invented downtime -- a tick displaced by ten '
  + 'positions manufactures ten missed intervals from a perfectly regular timeline', function () {
  const recs = []; for (let i = 0; i < 12; i++) recs.push(poll(i + 1, T0 + i * MINUTE));
  // Move the record started at minute 1 to the END of the write order; every start time is
  // unchanged and the real timeline still has no gap at all.
  const displaced = recs.slice();
  const moved = displaced.splice(1, 1)[0];
  displaced.push({ kind: 'POLL', seq: 99, outcome: 'OK', startedAt: moved.startedAt, instrumentsEvaluated: [] });
  const a = summarize(recs, T0 + 11 * MINUTE), b = summarize(displaced, T0 + 11 * MINUTE);
  return {
    pass: a.missedIntervals === 0 && b.missedIntervals >= 10 && b.negativeIntervals === 1,
    detail: 'clean missed=' + a.missedIntervals + ' -> displaced missed=' + b.missedIntervals
      + ', neg=' + b.negativeIntervals
  };
});

t('PCO-7', 'sorting the SAME records by start time instead of write order removes both symptoms -- '
  + 'evidence that the records themselves are intact and only the ordering is wrong', function () {
  const displaced = [poll(1, T0), poll(4, T0 + MINUTE), poll(2, T0 + 2 * MINUTE), poll(3, T0 + 3 * MINUTE)];
  const byStart = displaced.slice().sort(function (x, y) { return Date.parse(x.startedAt) - Date.parse(y.startedAt); })
    .map(function (r, i) { return Object.assign({}, r, { seq: i + 1 }); });
  const a = summarize(displaced, T0 + 3 * MINUTE), b = summarize(byStart, T0 + 3 * MINUTE);
  return {
    pass: a.negativeIntervals === 1 && b.negativeIntervals === 0 && b.missedIntervals === 0,
    detail: 'as-written neg=' + a.negativeIntervals + ' missed=' + a.missedIntervals
      + '  |  by start time neg=' + b.negativeIntervals + ' missed=' + b.missedIntervals
  };
});

t('PCO-8', 'the trailing term is unaffected by reordering -- an ONGOING outage is still measured '
  + 'from the newest start time to now, so this finding does not hide a live outage', function () {
  const recs = [poll(1, T0), poll(3, T0 + MINUTE), poll(2, T0 + 2 * MINUTE)];
  const s = summarize(recs, T0 + 2 * MINUTE + 30 * MINUTE);
  return { pass: s.trailingMissedIntervals >= 29 && s.ongoingOutage === true,
    detail: 'trailingMissed=' + s.trailingMissedIntervals + ' ongoing=' + s.ongoingOutage };
});

results.forEach(function (r) {
  console.log((r.pass ? 'PASS' : 'FAIL') + ' -- ' + r.name + ': ' + r.desc + (r.detail ? '  [' + r.detail + ']' : ''));
});
const fails = results.filter(function (r) { return !r.pass; }).length;
console.log('---');
console.log(results.length + ' fixtures, ' + (results.length - fails) + ' PASS, ' + fails + ' FAIL');
console.log('\nCharacterization only. No production behaviour is changed by this file, and the');
console.log('operator-visible warning is CORRECT: the recorded timeline genuinely is unreliable');
console.log('for continuity arithmetic. What these fixtures add is that the missed-interval count');
console.log('reported beside it inherits the same fault and overstates downtime.');
process.exitCode = fails ? 1 : 0;

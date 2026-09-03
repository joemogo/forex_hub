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

t('PCO-5', 'REPAIRED (v12.42.0): the swap no longer inflates the missed-interval count. This '
  + 'fixture previously asserted the INFLATION -- clean 0 missed, swapped 1 -- and its failure '
  + 'against the repaired code is the proof the repair does something', function () {
  const clean = [poll(1, T0), poll(2, T0 + MINUTE), poll(3, T0 + 2 * MINUTE), poll(4, T0 + 3 * MINUTE)];
  const swapped = [poll(1, T0), poll(2, T0 + MINUTE), poll(4, T0 + 2 * MINUTE), poll(3, T0 + 3 * MINUTE)];
  const a = summarize(clean, T0 + 3 * MINUTE), b = summarize(swapped, T0 + 3 * MINUTE);
  // The seq walk still sees startedAt 0 -> 1 -> 3 -> 2 min. What changed is that BOTH members of
  // the inversion are marked, so the oversized 2-minute gap BEFORE it -- the half that was being
  // counted in full -- is excluded along with the negative half it pairs with.
  return {
    pass: a.missedIntervals === 0 && b.missedIntervals === 0 && b.maxGapMs === MINUTE,
    detail: 'clean missed=' + a.missedIntervals + ' -> swapped missed=' + b.missedIntervals
      + ', maxGap=' + b.maxGapMs + ' (was 1 missed / 120000)'
  };
});

t('PCO-5b', 'THE SIGNAL SURVIVES THE REPAIR. Excluding the disordered pairs must not make the '
  + 'disorder itself invisible -- it is a real fact about the system, and the operator warning '
  + 'depends on it', function () {
  const swapped = [poll(1, T0), poll(2, T0 + MINUTE), poll(4, T0 + 2 * MINUTE), poll(3, T0 + 3 * MINUTE)];
  const b = summarize(swapped, T0 + 3 * MINUTE);
  return {
    pass: b.negativeIntervals === 1 && b.seqTimeDisagreements === 1
      && b.intervalPairsExcludedAsDisordered > 0,
    detail: 'neg=' + b.negativeIntervals + ' disagreements=' + b.seqTimeDisagreements
      + ' excluded=' + b.intervalPairsExcludedAsDisordered
  };
});

t('PCO-6', 'PARTIALLY REPAIRED, STATED HONESTLY: a tick displaced by ten positions used to '
  + 'manufacture ten missed intervals. Most of that is gone, but a residue remains and this '
  + 'fixture pins the residue rather than claiming a clean fix', function () {
  const recs = []; for (let i = 0; i < 12; i++) recs.push(poll(i + 1, T0 + i * MINUTE));
  const displaced = recs.slice();
  const moved = displaced.splice(1, 1)[0];
  displaced.push({ kind: 'POLL', seq: 99, outcome: 'OK', startedAt: moved.startedAt, instrumentsEvaluated: [] });
  const a = summarize(recs, T0 + 11 * MINUTE), b = summarize(displaced, T0 + 11 * MINUTE);
  // The record started at minute 1 is written LAST, so the walk reads 0 -> 2 min as its first
  // step. That pair touches no inversion -- the inversion is eleven positions later -- so one
  // invented interval survives. Recovering it would mean re-deriving the true order, which is
  // exactly the reconstruction this repository prefers a diagnostic to.
  return {
    pass: a.missedIntervals === 0 && b.missedIntervals === 1 && b.seqTimeDisagreements === 1,
    detail: 'clean missed=' + a.missedIntervals + ' -> displaced missed=' + b.missedIntervals
      + ' (was >=10), disagreements=' + b.seqTimeDisagreements
  };
});

t('PCO-6b', 'AND THE TRAILING TERM NO LONGER INVENTS A LIVE OUTAGE. Most of that displaced '
  + 'count was the trailing term measuring from the LAST-WRITTEN poll, which after a reordering '
  + 'is an OLDER tick -- so a running loop was reported as ten minutes dead. It now measures '
  + 'from the NEWEST start time', function () {
  const recs = []; for (let i = 0; i < 12; i++) recs.push(poll(i + 1, T0 + i * MINUTE));
  const displaced = recs.slice();
  const moved = displaced.splice(1, 1)[0];
  displaced.push({ kind: 'POLL', seq: 99, outcome: 'OK', startedAt: moved.startedAt, instrumentsEvaluated: [] });
  const b = summarize(displaced, T0 + 11 * MINUTE);
  return {
    pass: b.ongoingOutage === false && b.trailingMissedIntervals === 0
      && b.trailingSince === new Date(T0 + 11 * MINUTE).toISOString(),
    detail: 'ongoing=' + b.ongoingOutage + ' trailingMissed=' + b.trailingMissedIntervals
      + ' since=' + b.trailingSince
  };
});

t('PCO-6c', 'POSITIVE CONTROL: a REAL ongoing outage is still reported. The trailing fix must '
  + 'not have turned the outage detector off -- that would be a far worse failure than the '
  + 'false positive it removes', function () {
  const recs = []; for (let i = 0; i < 5; i++) recs.push(poll(i + 1, T0 + i * MINUTE));
  const b = summarize(recs, T0 + 34 * MINUTE);   // 30 minutes past the last tick
  return {
    pass: b.ongoingOutage === true && b.trailingMissedIntervals === 29,
    detail: 'ongoing=' + b.ongoingOutage + ' trailingMissed=' + b.trailingMissedIntervals
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
console.log('\nCharacterized in v12.41.0, REPAIRED in v12.42.0. The operator-visible warning is');
console.log('still CORRECT -- a disordered timeline genuinely is unreliable for continuity');
console.log('arithmetic, and PCO-5b proves that signal survives. What changed is that the');
console.log('missed-interval count beside it no longer INHERITS the fault: the pairs touching an');
console.log('inversion are excluded and counted, and the trailing term measures from the newest');
console.log('start time rather than the last-written poll. PCO-6 pins the residue that remains on');
console.log('a widely displaced record, because a partial repair reported as a clean one is the');
console.log('same class of error as the defect itself.');
process.exitCode = fails ? 1 : 0;

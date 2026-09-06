#!/usr/bin/env node
'use strict';
// ══════════════════════════════════════════════════════════════════════════════════════════════
// v12.58.0 — JVM RECORDED WHY IT REFUSED EVERY TRADE, AND THREW IT AWAY
// ══════════════════════════════════════════════════════════════════════════════════════════════
//
// jvmRecordCandidateRejected already computed the right answer: the engine's own reason, mapped to
// a real reason code, on every refused candidate. It emitted that into decisionEventLog -- an
// in-memory array, capped at 500, never written to storage while 27 other keys are persisted. So
// every JVM refusal died on the next page reload, and after months of forward operation the
// preserved evidence holds 2 JVM closes and nothing whatsoever about what was declined.
//
// That is the same defect v12.51.0 fixed for ALEX, and it is why the question "why does JVM only
// have 2 closes" could not be answered from evidence. The answer was computed every minute and
// discarded. JVMD-1 and JVMD-2 prove the gap was real and that it is now closed; they are the
// fixtures that catch a revert.
//
// JVMD-9 is the property that matters most: a DECLINED candidate has no outcome. It was never
// traded, so there is no win, no loss and no R. The single worst thing this store could do is grow
// a win-rate field, because it would be a performance figure for trades that never existed.
//
// JVMD-6 pins the dedup key including the DAY. checkAutoTrades sweeps every 60 seconds and a pair
// outside the Mon-Wed window is refused on every tick, so without a key the store would measure
// poll frequency rather than market behaviour and reach its cap in under a day -- but collapsing
// separate DAYS would hide the very frequency the store exists to reveal.
//
// Run:  node tests/run_v159_jvm_declined_tests.js

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

// A realm holding the real functions. persistStorageKey is captured, not stubbed away, so a
// fixture can assert the write actually happened rather than that the code merely calls something.
function realm(cap) {
  const written = {};
  const c = { console: console, Math: Math, JSON: JSON, Object: Object, String: String,
    Number: Number, Array: Array, isFinite: isFinite, isNaN: isNaN, Date: Date,
    persistStorageKey: function (k, v) { written[k] = v; } };
  vm.createContext(c);
  vm.runInContext('const JVM_DECLINED_MAX=' + (cap || 500) + ';', c);
  vm.runInContext('let jvmDeclinedCandidates=[];', c);
  vm.runInContext('let __jvmCurrentScanId=null;', c);
  vm.runInContext(fn('jvmLiveTriggerReasonCode'), c);
  vm.runInContext(fn('jvmDeclinedProjection'), c);
  vm.runInContext(fn('jvmRecordDeclinedCandidate'), c);
  vm.runInContext(fn('jvmDeclinedSummary'), c);
  c.__written = written;
  return c;
}
function decline(ctx, pair, result, scanId) {
  return vm.runInContext('jvmRecordDeclinedCandidate(' + JSON.stringify(pair) + ',' +
    JSON.stringify(result) + ',' + JSON.stringify(scanId || null) + ')', ctx);
}
function rows(ctx) { return vm.runInContext('jvmDeclinedCandidates', ctx); }

const results = [];
function t(name, desc, f) {
  let pass = false, detail = '';
  try { const r = f(); pass = !!(r && r.pass); detail = (r && r.detail) || ''; }
  catch (e) { pass = false; detail = 'threw: ' + (e && e.message ? e.message : String(e)); }
  results.push({ name, desc, pass, detail });
}

// ══ THE GAP WAS REAL, AND IS NOW CLOSED ══════════════════════════════════════════════════════

t('JVMD-1', 'the decision-event log is STILL in-memory and capped -- this feature does not replace '
  + 'it, and a fixture that assumed it had become durable would be testing the wrong thing', function () {
  return { pass: /let decisionEventLog=\[\];/.test(SRC)
      && /const DECISION_EVENT_MAX_LOG_SIZE=\d+;/.test(SRC)
      && !/persistStorageKey\('fxhub_decision/.test(SRC),
    detail: 'decisionEventLog remains in-memory and capped' };
});

t('JVMD-2', 'JVM declines ARE now persisted and reloaded. This is the fixture that catches a '
  + 'revert, and the reason months of JVM refusals left no trace', function () {
  return { pass: /persistStorageKey\('fxhub_jvm_declined',JSON\.stringify\(jvmDeclinedCandidates\)\)/.test(SRC)
      && /loadStoredKey\('fxhub_jvm_declined'/.test(SRC),
    detail: 'saved and loaded under fxhub_jvm_declined' };
});

t('JVMD-3', 'the reload is defensive: a corrupt or non-array stored value leaves the in-memory list '
  + 'intact rather than replacing it with garbage', function () {
  const i = SRC.indexOf("loadStoredKey('fxhub_jvm_declined'");
  const line = i < 0 ? '' : SRC.slice(i, SRC.indexOf('\n', i));
  return { pass: i >= 0 && /Array\.isArray\(a\)/.test(line) && /jvmDeclinedCandidates=a/.test(line),
    detail: i < 0 ? 'load line not found' : 'guarded' };
});

t('JVMD-4', 'the store is rehydrated by JVM\'s OWN loader. Loading a JVM store from the ALEX loader '
  + 'also works today and would silently stop the moment ALEX loading became conditional', function () {
  const saved = codeOf(fn('loadSaved'));
  const alexSaved = codeOf(fn('loadAlexGSaved'));
  return { pass: /fxhub_jvm_declined/.test(saved) && !/fxhub_jvm_declined/.test(alexSaved),
    detail: 'loaded in loadSaved(), absent from loadAlexGSaved()' };
});

// ══ WHAT IS RECORDED ═════════════════════════════════════════════════════════════════════════

t('JVMD-5', 'the engine\'s OWN reason is recorded verbatim, and the code comes from the existing '
  + 'centralized mapper -- never re-derived here and never softened', function () {
  const c = realm();
  decline(c, 'EUR_USD', { fires: false, reason: 'HTF alignment not satisfied — HTF_SNAPSHOT_MISSING' });
  const r = rows(c)[0];
  const body = codeOf(fn('jvmDeclinedProjection'));
  return { pass: r.reason === 'HTF alignment not satisfied — HTF_SNAPSHOT_MISSING'
      && r.reasonCode === 'STRUCTURE_HTF_ALIGNMENT_NOT_SATISFIED'
      && /jvmLiveTriggerReasonCode\(r\.reason\)/.test(body),
    detail: r.reasonCode };
});

t('JVMD-6', 'deduped by (pair, reason, DAY). checkAutoTrades sweeps every 60s and an out-of-window '
  + 'pair is refused on every tick, so without a key this measures poll frequency -- but collapsing '
  + 'separate DAYS would hide the frequency the store exists to reveal', function () {
  const c = realm();
  const res = { fires: false, reason: 'Outside Mon-Wed preferred entry window' };
  decline(c, 'EUR_USD', res); decline(c, 'EUR_USD', res); decline(c, 'EUR_USD', res);
  const one = rows(c);
  const keyed = /const key=row\.pair\+'\|'\+row\.reasonCode\+'\|'\+day;/.test(codeOf(fn('jvmRecordDeclinedCandidate')));
  return { pass: one.length === 1 && one[0].occurrences === 3 && keyed,
    detail: '3 identical declines -> 1 row, occurrences=' + one[0].occurrences + '; day is part of the key' };
});

t('JVMD-7', 'the SAME pair refused for a DIFFERENT reason is a new fact and is kept -- that '
  + 'distinction is the entire diagnostic value of the store', function () {
  const c = realm();
  decline(c, 'EUR_USD', { fires: false, reason: 'Outside Mon-Wed preferred entry window' });
  decline(c, 'EUR_USD', { fires: false, reason: 'Confluence below threshold' });
  return { pass: rows(c).length === 2, detail: 'two distinct reasons -> 2 rows' };
});

t('JVMD-8', 'confluence is recorded when the engine computed one, and NULL when it short-circuited '
  + 'earlier -- 0 would assert a measured miss that never happened', function () {
  const c = realm();
  decline(c, 'EUR_USD', { fires: false, reason: 'Confluence below threshold', conf: { total: 42, direction: 'long' } });
  decline(c, 'GBP_USD', { fires: false, reason: 'Outside Mon-Wed preferred entry window' });
  const withConf = rows(c).find(function (r) { return r.pair === 'EUR_USD'; });
  const without = rows(c).find(function (r) { return r.pair === 'GBP_USD'; });
  return { pass: withConf.confluence === 42 && withConf.direction === 'long' && without.confluence === null,
    detail: 'computed=42, short-circuited=null (not 0)' };
});

// ══ NO OUTCOME. EVER. ════════════════════════════════════════════════════════════════════════

t('JVMD-9', 'THE ONE THAT MATTERS: a declined candidate has NO outcome. It was never traded, so '
  + 'there is no win, no loss and no R. A win-rate field here would be a performance figure for '
  + 'trades that never existed', function () {
  const c = realm();
  decline(c, 'EUR_USD', { fires: false, reason: 'Confluence below threshold', conf: { total: 42 } });
  const s = vm.runInContext('jvmDeclinedSummary(jvmDeclinedCandidates)', c);
  const r = rows(c)[0];
  const bad = ['winRate', 'wins', 'losses', 'result', 'outcome', 'pnl', 'resultR', 'netR'];
  const onRow = bad.filter(function (k) { return Object.prototype.hasOwnProperty.call(r, k); });
  const onSummary = bad.filter(function (k) { return Object.prototype.hasOwnProperty.call(s, k); });
  return { pass: onRow.length === 0 && onSummary.length === 0 && s.outcomesKnown === false,
    detail: onRow.length || onSummary.length ? 'LEAKED: ' + onRow.concat(onSummary).join(',')
      : 'no outcome field on the row or the summary; outcomesKnown=false' };
});

t('JVMD-10', 'the summary SAYS when it is at the cap, rather than quietly shrinking the population '
  + 'it exists to measure', function () {
  const c = realm(3);
  ['A_B', 'C_D', 'E_F', 'G_H'].forEach(function (p) {
    decline(c, p, { fires: false, reason: 'Confluence below threshold' });
  });
  const s = vm.runInContext('jvmDeclinedSummary(jvmDeclinedCandidates)', c);
  return { pass: rows(c).length === 3 && s.atCap === true, detail: 'capped at 3, atCap reported' };
});

t('JVMD-11', 'the summary ranks reasons by how often they actually fired, which is the question '
  + 'the store exists to answer: WHERE does JVM lose its candidates', function () {
  const c = realm();
  const mon = { fires: false, reason: 'Outside Mon-Wed preferred entry window' };
  decline(c, 'EUR_USD', mon); decline(c, 'EUR_USD', mon); decline(c, 'GBP_USD', mon);
  decline(c, 'USD_JPY', { fires: false, reason: 'Confluence below threshold' });
  const s = vm.runInContext('jvmDeclinedSummary(jvmDeclinedCandidates)', c);
  return { pass: s.reasons[0].reasonCode === 'SESSION_OUTSIDE_PREFERRED_DAY'
      && s.reasons[0].occurrences === 3 && s.reasons[0].pairs === 2 && s.totalOccurrences === 4,
    detail: s.reasons.map(function (r) { return r.reasonCode + '=' + r.occurrences; }).join(' ') };
});

// ══ IT CANNOT BREAK TRADING ══════════════════════════════════════════════════════════════════

t('JVMD-12', 'a malformed candidate does not throw -- recording runs inside the trading tick and '
  + 'must never be able to break it', function () {
  const c = realm();
  decline(c, null, { fires: false, reason: 'x' });
  decline(c, '', null);
  decline(c, 'EUR_USD', undefined);
  return { pass: true, detail: 'no throw on null pair, empty pair or missing result' };
});

t('JVMD-13', 'the whole recorder is wrapped, and its result is never read by the caller', function () {
  const body = fn('jvmRecordDeclinedCandidate');
  const caller = fn('jvmRecordCandidateRejected');
  return { pass: /catch\(e\)\{/.test(body) && /jvmRecordDeclinedCandidate\(oPair,result,__jvmCurrentScanId\);/.test(caller)
      && !/=\s*jvmRecordDeclinedCandidate\(/.test(caller),
    detail: 'wrapped; called as a statement, return value unused' };
});

t('JVMD-14', 'a persistence failure does not lose the in-memory row or throw', function () {
  const c = realm();
  vm.runInContext('persistStorageKey=function(){ throw new Error("quota"); };', c);
  decline(c, 'EUR_USD', { fires: false, reason: 'Confluence below threshold' });
  return { pass: rows(c).length === 1, detail: 'row kept in memory despite a throwing persist' };
});

t('JVMD-15', 'the durable record is written BEFORE the event-bus emit, so a failure in the bus '
  + 'cannot cost the record', function () {
  const caller = codeOf(fn('jvmRecordCandidateRejected'));
  const rec = caller.indexOf('jvmRecordDeclinedCandidate(');
  const emit = caller.indexOf('emitDecisionEvent(');
  return { pass: rec >= 0 && emit > rec, detail: 'durable write at ' + rec + ', emit at ' + emit };
});

t('JVMD-16', 'an unknown reason becomes UNKNOWN_NOT_RECORDED rather than a plausible guess', function () {
  const c = realm();
  decline(c, 'EUR_USD', { fires: false, reason: 'something the map has never seen' });
  return { pass: rows(c)[0].reasonCode === 'UNKNOWN_NOT_RECORDED', detail: rows(c)[0].reasonCode };
});

// ══ THE VIEW ═════════════════════════════════════════════════════════════════════════════════
//
// A store nobody can see is a store that answers nothing. v12.51.0 shipped the ALEX decline store
// WITH its Observatory band; this release must not ship the JVM store without one, or the question
// it exists to answer stays reachable only by exporting and analysing offline -- which is the
// friction that leaves a question unanswered for months.

t('JVMD-17', 'the JVM decline summary is actually RENDERED. Building the store without a view would '
  + 'leave it accumulating invisibly', function () {
  const render = codeOf(fn('obsRenderJvmDeclined'));
  const called = /h\+=obsRenderJvmDeclined\(\);/.test(codeOf(SRC));
  return { pass: /jvmDeclinedSummary\(/.test(render) && called,
    detail: called ? 'obsRenderJvmDeclined defined and called from the Observatory' : 'DEFINED BUT NEVER CALLED' };
});

t('JVMD-18', 'the empty state says declines only exist from this version onward, and that a '
  + 'persistently empty table is ITSELF a finding rather than a blank', function () {
  const render = fn('obsRenderJvmDeclined');
  return { pass: /v12\.58\.0 onward/.test(render) && /itself a finding/.test(render),
    detail: 'empty state is explanatory, not blank' };
});

t('JVMD-19', 'the view reports pair-days AND occurrences separately -- 3 rows and 40 hits are '
  + 'different facts and showing only one misrepresents the frequency', function () {
  const render = fn('obsRenderJvmDeclined');
  return { pass: /Pair-days/.test(render) && /Times hit/.test(render)
      && /r\.rows/.test(render) && /r\.occurrences/.test(render),
    detail: 'both columns rendered from the summary' };
});

t('JVMD-20', 'the view states that JVM stops at the FIRST failed gate, so a reason recorded here '
  + 'does not mean the later gates passed -- without that the table reads as a ranking of faults '
  + 'rather than a funnel', function () {
  const render = fn('obsRenderJvmDeclined');
  return { pass: /FIRST gate/.test(render) && /never evaluated/.test(render),
    detail: 'short-circuit semantics explained in the view' };
});

t('JVMD-21', 'the view carries the no-outcome statement too. The store refusing to hold an outcome '
  + 'is worth nothing if the surface implies one', function () {
  const render = fn('obsRenderJvmDeclined');
  return { pass: /No outcome is shown/.test(render) && /never happened/.test(render)
      && !/win rate.{0,20}%/.test(render.replace(/win rate here would/, '')),
    detail: 'no-outcome stated in the rendered band' };
});

// ══ GUARDS ═══════════════════════════════════════════════════════════════════════════════════

t('GUARD-1', 'the whole page script parses', function () {
  const m = SRC.match(/<script>([\s\S]*?)<\/script>/g) || [];
  let total = 0;
  m.forEach(function (b) {
    const js = b.replace(/^<script>/, '').replace(/<\/script>$/, '');
    if (!js.trim()) return; total += js.length; new Function(js);
  });
  return { pass: total > 100000, detail: 'parsed ' + total.toLocaleString() + ' chars' };
});

t('GUARD-2', 'no protected function was touched to add this -- the hook already existed at a '
  + 'non-protected call site', function () {
  const reg = JSON.parse(fs.readFileSync(path.join(ROOT, 'regression-baseline.json'), 'utf8'));
  const p = Object.keys(reg.protectedFunctions || {});
  return { pass: p.indexOf('jvmRecordCandidateRejected') === -1
      && p.indexOf('jvmRecordDeclinedCandidate') === -1 && p.indexOf('checkAutoTrades') !== -1,
    detail: 'recorder is unprotected; checkAutoTrades stays protected and unedited' };
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

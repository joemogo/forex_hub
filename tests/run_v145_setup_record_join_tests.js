#!/usr/bin/env node
'use strict';
// ══════════════════════════════════════════════════════════════════════════════════════════════
// v12.45.0 — SETUP-RECORD JOIN
// ══════════════════════════════════════════════════════════════════════════════════════════════
//
// The defect these fixtures pin was MEASURED on the 86 preserved packages, not hypothesised:
// every REPLAY_RUN package verifies every condition, and EVERY forward package leaves at least
// one unverified -- A_repeatedReaction 1, B_breakRetest 3, including the condition that decides
// trade direction. alexGCreateSetupRecord stores the fields; alexGConstructLivePosition does not
// copy them; replay reads the setup record directly, which is why only replay ever verified.
//
// Two properties matter more than any individual assertion here:
//
//   1. THE JOIN CANNOT MANUFACTURE PROVENANCE. Every way the identity check can fail supplies
//      NOTHING, and the package stays honestly INDETERMINATE. SJ-2..SJ-9 are that boundary.
//   2. THE JOIN CANNOT DESTROY EVIDENCE. A contradiction that appears only once the join supplied
//      fields falls back to the pre-v12.45.0 attribution and records the disagreement, rather than
//      failing capture and losing the trade. SJ-28..SJ-30. A trade that contradicts its own rules
//      on its OWN stored fields still fails capture, unchanged (SJ-29).
//
// Every "the gap closes" fixture is paired with a positive control that mutates the supplied data
// and requires the condition to notice -- otherwise the fixture would pass over a mirror that had
// stopped reading the field at all. SJ-21/SJ-22 and SJ-26 are those controls.
//
// Run:  node tests/run_v145_setup_record_join_tests.js

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
// Reads a top-level `const X = ...;` declaration of ANY shape -- a bare string, an Object.freeze
// of an object, or an Object.freeze of an array of functions -- by scanning to the first ";" that
// sits at bracket depth zero and outside any string or comment. Written generically on purpose:
// the previous version guessed the opening bracket and silently swallowed the NEXT declaration.
function extractBlock(decl) {
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

const ctx = {
  console: console, Math: Math, JSON: JSON, isFinite: isFinite, Array: Array,
  Number: Number, Object: Object, String: String, Date: Date, isNaN: isNaN
};
vm.createContext(ctx);

vm.runInContext(extractBlock("const ALEX_RULE_ATTRIBUTION_MIRROR_VERSION="), ctx);
vm.runInContext(extractBlock('const ALEX_ATTRIBUTION_RULE_IDS='), ctx);
vm.runInContext(extractBlock('const ALEX_ATTRIBUTION_CONDITIONS='), ctx);
vm.runInContext(extractBlock('const ALEX_SETUP_JOIN_FIELDS='), ctx);
vm.runInContext(extractBlock('const EVIDENCE_SETUP_JOIN_STATUSES='), ctx);
vm.runInContext(extractFunction('alexGBuildRuleAttribution'), ctx);
vm.runInContext(extractFunction('alexGEmptySetupJoin'), ctx);
vm.runInContext(extractFunction('alexGFindSetupRecordForTrade'), ctx);
vm.runInContext(extractFunction('alexGCountBreakCycleSetups'), ctx);
vm.runInContext(extractFunction('alexGResolveAttributionInputs'), ctx);

// `const` in a vm context is a lexical binding, not a property of the context object -- only
// `function` declarations show up on ctx. Frozen constants have to be read back by evaluating
// their name, or a fixture asserting against them silently compares undefined to undefined.
function read(name) { return vm.runInContext(name, ctx); }
const JOIN_STATUSES = read('EVIDENCE_SETUP_JOIN_STATUSES');
const MIRROR_VERSION = read('ALEX_RULE_ATTRIBUTION_MIRROR_VERSION');
const JOIN_FIELDS = read('ALEX_SETUP_JOIN_FIELDS');

const results = [];
function t(name, desc, fn) {
  let pass = false, detail = '';
  try { const r = fn(); pass = !!(r && r.pass); detail = (r && r.detail) || ''; }
  catch (e) { pass = false; detail = 'threw: ' + (e && e.message ? e.message : String(e)); }
  results.push({ name, desc, pass, detail });
}
const F = ctx;

// ── shapes that mirror what the real engine produces ─────────────────────────────────────────
const QT = 1755600000000;
// Exactly the field set alexGConstructLivePosition copies onto a booked B_breakRetest position.
// Deliberately NOT a convenience object: if the constructor ever starts copying more, this fixture
// data becomes wrong and the "gap closes" fixtures will show it by going green without the join.
function bookedBreakRetest(over) {
  const p = {
    tradeId: 'AGT|1', setupId: 'AGS|EUR_USD|H4|z1|B_breakRetest|r9', qualificationTimestamp: QT,
    setupType: 'B_breakRetest', zoneTouchNumber: 5,
    zoneQualityAtQualification: 'clean', zoneRoleAtQualification: 'resistance',
    breakCycleId: 'BC|1', brokenDirection: 'downThroughSupport', barsSinceBreak: 3
  };
  if (over) Object.keys(over).forEach(function (k) { p[k] = over[k]; });
  return p;
}
function bookedRepeated(over) {
  const p = {
    tradeId: 'AGT|2', setupId: 'AGS|EUR_USD|H4|z2|A_repeatedReaction|r4', qualificationTimestamp: QT,
    setupType: 'A_repeatedReaction', zoneTouchNumber: 6,
    zoneQualityAtQualification: 'clean', zoneRoleAtQualification: 'support',
    breakCycleId: null, brokenDirection: null, barsSinceBreak: null
  };
  if (over) Object.keys(over).forEach(function (k) { p[k] = over[k]; });
  return p;
}
function setupFor(trade, over) {
  const s = {
    setupId: trade.setupId, qualificationTimestamp: trade.qualificationTimestamp,
    setupType: trade.setupType, zoneId: 'z1', breakCycleId: trade.breakCycleId,
    zoneStatusAtQualification: trade.setupType === 'B_breakRetest' ? 'broken' : 'validated',
    reactionSwingType: 'high', reactionFromSide: 'below',
    brokenAtBar: 40, brokenAt: QT - 3 * 14400000,
    brokenDirection: trade.brokenDirection, barsSinceBreak: trade.barsSinceBreak,
    zoneTouchNumber: trade.zoneTouchNumber
  };
  if (over) Object.keys(over).forEach(function (k) { s[k] = over[k]; });
  return s;
}
const CFG = { maxBarsBetweenBreakAndRetest: 10 };
function attribute(trade, joinRes, breakCycleSetupCount) {
  const r = F.alexGResolveAttributionInputs(trade, joinRes ? joinRes.record : null,
    joinRes ? joinRes.status : 'NOT_ATTEMPTED');
  const ctxArg = { breakCycleSetupCount: (breakCycleSetupCount === undefined ? null : breakCycleSetupCount) };
  return { attr: F.alexGBuildRuleAttribution(r.record, trade.setupType, CFG, ctxArg), join: r.join };
}
function unverifiedIds(attr) {
  return attr.triggeredConditions.filter(function (c) { return c.satisfied === null; })
    .map(function (c) { return c.conditionId; }).sort();
}
function conditionById(attr, id) {
  return attr.triggeredConditions.filter(function (c) { return c.conditionId === id; })[0] || null;
}

// ══ THE IDENTITY CHECK — every failure mode must supply NOTHING ═══════════════════════════════

t('SJ-1', 'a setup whose setupId AND qualificationTimestamp both match the booked trade joins', function () {
  const tr = bookedBreakRetest();
  const r = F.alexGFindSetupRecordForTrade(tr, [setupFor(tr)]);
  return { pass: r.status === 'JOINED' && r.record !== null, detail: r.status };
});

t('SJ-2', 'the SAME setupId qualifying on a DIFFERENT bar is refused -- the setup state has moved '
  + 'on and joining it would attribute one qualification event to another', function () {
  const tr = bookedBreakRetest();
  const r = F.alexGFindSetupRecordForTrade(tr, [setupFor(tr, { qualificationTimestamp: QT + 14400000 })]);
  return { pass: r.status === 'QUALIFICATION_TIMESTAMP_MISMATCH' && r.record === null, detail: r.status };
});

t('SJ-3', 'a position carrying no setupId at all -- a JVM trade -- is refused before it can be '
  + 'matched against ALEX setup state', function () {
  const tr = bookedBreakRetest({ setupId: null });
  const r = F.alexGFindSetupRecordForTrade(tr, [setupFor(bookedBreakRetest())]);
  return { pass: r.status === 'TRADE_HAS_NO_SETUP_ID' && r.record === null, detail: r.status };
});

t('SJ-4', 'a setup that has aged out of the rebuilt state is SETUP_NOT_FOUND, never the nearest '
  + 'other setup', function () {
  const tr = bookedBreakRetest();
  const other = setupFor(bookedRepeated());
  const r = F.alexGFindSetupRecordForTrade(tr, [other]);
  return { pass: r.status === 'SETUP_NOT_FOUND' && r.record === null, detail: r.status };
});

t('SJ-5', 'empty setup state joins nothing rather than throwing', function () {
  const r = F.alexGFindSetupRecordForTrade(bookedBreakRetest(), []);
  return { pass: r.status === 'SETUP_STATE_EMPTY' && r.record === null, detail: r.status };
});

t('SJ-6', 'a trade with no qualificationTimestamp cannot be identity-checked, so it does not join '
  + '-- absence of the evidence is not agreement', function () {
  const tr = bookedBreakRetest({ qualificationTimestamp: null });
  const r = F.alexGFindSetupRecordForTrade(tr, [setupFor(bookedBreakRetest())]);
  return { pass: r.status === 'QUALIFICATION_TIMESTAMP_UNAVAILABLE' && r.record === null, detail: r.status };
});

t('SJ-7', 'the same holds when it is the SETUP record missing the timestamp', function () {
  const tr = bookedBreakRetest();
  const r = F.alexGFindSetupRecordForTrade(tr, [setupFor(tr, { qualificationTimestamp: null })]);
  return { pass: r.status === 'QUALIFICATION_TIMESTAMP_UNAVAILABLE' && r.record === null, detail: r.status };
});

t('SJ-8', 'the same instant stored as a string on one side and a number on the other still names '
  + 'one qualification event, so it joins', function () {
  const tr = bookedBreakRetest();
  const r = F.alexGFindSetupRecordForTrade(tr, [setupFor(tr, { qualificationTimestamp: String(QT) })]);
  return { pass: r.status === 'JOINED', detail: r.status };
});

t('SJ-9', 'a non-array setup state -- storage never loaded -- returns a status, never a throw', function () {
  const a = F.alexGFindSetupRecordForTrade(bookedBreakRetest(), null);
  const b = F.alexGFindSetupRecordForTrade(bookedBreakRetest(), undefined);
  const c = F.alexGFindSetupRecordForTrade(null, [setupFor(bookedBreakRetest())]);
  return { pass: a.record === null && b.record === null && c.record === null
      && JOIN_STATUSES.indexOf(a.status) >= 0
      && JOIN_STATUSES.indexOf(c.status) >= 0,
    detail: [a.status, b.status, c.status].join(',') };
});

// ══ THE OVERLAY — the booked trade always wins ════════════════════════════════════════════════

t('SJ-10', 'the join supplies exactly the fields alexGConstructLivePosition drops, and no others', function () {
  const tr = bookedBreakRetest();
  const r = F.alexGResolveAttributionInputs(tr, setupFor(tr), 'JOINED');
  return { pass: r.join.fieldsSupplied.join(',') === 'brokenAt,brokenAtBar,reactionFromSide,reactionSwingType,zoneStatusAtQualification',
    detail: r.join.fieldsSupplied.join(',') };
});

t('SJ-11', 'a value the trade already carries is NEVER overwritten by the setup record -- the '
  + 'booked position is the authority on its own fields', function () {
  const tr = bookedBreakRetest({ brokenDirection: 'upThroughResistance' });
  const r = F.alexGResolveAttributionInputs(tr, setupFor(tr, { brokenDirection: 'downThroughSupport' }), 'JOINED');
  return { pass: r.record.brokenDirection === 'upThroughResistance'
      && r.join.fieldsSupplied.indexOf('brokenDirection') === -1,
    detail: 'record=' + r.record.brokenDirection };
});

t('SJ-12', 'the overlay never mutates the trade object the ledger still holds', function () {
  const tr = bookedBreakRetest();
  F.alexGResolveAttributionInputs(tr, setupFor(tr), 'JOINED');
  return { pass: !('reactionSwingType' in tr) && !('zoneStatusAtQualification' in tr),
    detail: 'trade keys: ' + Object.keys(tr).length };
});

t('SJ-13', 'a null on the setup record is not a value -- it is not supplied, and the condition '
  + 'stays honestly unverified', function () {
  const tr = bookedBreakRetest();
  const r = F.alexGResolveAttributionInputs(tr, setupFor(tr, { reactionSwingType: null }), 'JOINED');
  return { pass: r.join.fieldsSupplied.indexOf('reactionSwingType') === -1 && r.record.reactionSwingType == null,
    detail: r.join.fieldsSupplied.join(',') };
});

t('SJ-14', 'fieldsSupplied is sorted, so two packages that supplied the same inputs canonicalize '
  + 'to the same bytes regardless of declaration order', function () {
  const tr = bookedBreakRetest();
  const r = F.alexGResolveAttributionInputs(tr, setupFor(tr), 'JOINED');
  const sorted = r.join.fieldsSupplied.slice().sort();
  return { pass: JSON.stringify(r.join.fieldsSupplied) === JSON.stringify(sorted), detail: r.join.fieldsSupplied.join(',') };
});

t('SJ-15', 'a setup record handed in with a status that is NOT "JOINED" supplies nothing -- the '
  + 'status is the gate, not the presence of a record', function () {
  const tr = bookedBreakRetest();
  const bad = ['SETUP_NOT_FOUND', 'QUALIFICATION_TIMESTAMP_MISMATCH', 'NOT_ATTEMPTED'];
  const ok = bad.every(function (s) {
    const r = F.alexGResolveAttributionInputs(tr, setupFor(tr), s);
    return r.join.fieldsSupplied.length === 0 && r.record === tr;
  });
  return { pass: ok, detail: bad.join(',') };
});

// ══ THE MEASURED GAP, AND THAT IT CLOSES ═════════════════════════════════════════════════════

t('SJ-16', 'WITHOUT the join a booked B_breakRetest leaves exactly the three conditions the real '
  + 'corpus shows unverified -- this fixture reproduces the defect', function () {
  const a = attribute(bookedBreakRetest(), null).attr;
  const ids = unverifiedIds(a);
  return { pass: ids.length === 3
      && ids.indexOf('ALEX_SR_V1_B_ZONE_STATUS_BROKEN') >= 0
      && ids.indexOf('ALEX_SR_V1_B_REACTION_SIDE_MATCHES_BREAK') >= 0
      && ids.indexOf('ALEX_SR_V1_B_FIRST_RETEST_IN_BREAK_CYCLE') >= 0
      && a.verdict === 'INDETERMINATE',
    detail: ids.join(' ') };
});

t('SJ-17', 'WITH the join the same trade verifies every condition', function () {
  const tr = bookedBreakRetest();
  const j = F.alexGFindSetupRecordForTrade(tr, [setupFor(tr)]);
  const a = attribute(tr, j, 1).attr;
  return { pass: unverifiedIds(a).length === 0
      && a.attribution.unverifiedConditionCount === 0
      && a.verdict === 'AGREES_WITH_RECORDED_CLASSIFICATION',
    detail: a.verdict + ' unverified=' + a.attribution.unverifiedConditionCount };
});

t('SJ-18', 'WITHOUT the join a booked A_repeatedReaction leaves exactly the one condition the real '
  + 'corpus shows unverified', function () {
  const a = attribute(bookedRepeated(), null).attr;
  const ids = unverifiedIds(a);
  return { pass: ids.length === 1 && ids[0] === 'ALEX_SR_V1_A_ZONE_STATUS_VALIDATED', detail: ids.join(' ') };
});

t('SJ-19', 'WITH the join the repeated-reaction trade verifies every condition', function () {
  const tr = bookedRepeated();
  const j = F.alexGFindSetupRecordForTrade(tr, [setupFor(tr)]);
  const a = attribute(tr, j).attr;
  return { pass: unverifiedIds(a).length === 0 && a.verdict === 'AGREES_WITH_RECORDED_CLASSIFICATION',
    detail: a.verdict };
});

t('SJ-20', 'the direction-deciding condition specifically becomes checkable, and reports the '
  + 'expected and observed sides rather than a bare true', function () {
  const tr = bookedBreakRetest();
  const j = F.alexGFindSetupRecordForTrade(tr, [setupFor(tr)]);
  const c = conditionById(attribute(tr, j, 1).attr, 'ALEX_SR_V1_B_REACTION_SIDE_MATCHES_BREAK');
  return { pass: c && c.satisfied === true && c.provenance === 'OBSERVED'
      && c.observed.expectedSwingType === 'high' && c.observed.expectedFromSide === 'below'
      && c.observed.reactionSwingType === 'high' && c.observed.reactionFromSide === 'below',
    detail: JSON.stringify(c && c.observed) };
});

// ══ POSITIVE CONTROLS — the condition must actually READ what the join supplies ═══════════════

t('SJ-21', 'POSITIVE CONTROL: a reaction side that does NOT match the break makes the condition '
  + 'FAIL -- proving SJ-20 is checking the data, not passing vacuously', function () {
  const tr = bookedBreakRetest();
  const j = F.alexGFindSetupRecordForTrade(tr, [setupFor(tr, { reactionSwingType: 'low', reactionFromSide: 'above' })]);
  const a = attribute(tr, j, 1).attr;
  const c = conditionById(a, 'ALEX_SR_V1_B_REACTION_SIDE_MATCHES_BREAK');
  return { pass: c && c.satisfied === false && a.verdict === 'CONTRADICTS_RECORDED_CLASSIFICATION'
      && a.attribution.failedConditionIds.indexOf('ALEX_SR_V1_B_REACTION_SIDE_MATCHES_BREAK') >= 0,
    detail: a.verdict };
});

t('SJ-22', 'MUTATION CONTROL: that same mismatched data is INVISIBLE without the join -- which is '
  + 'exactly what every forward package captured so far could not see', function () {
  const tr = bookedBreakRetest();
  const a = attribute(tr, null).attr;
  const c = conditionById(a, 'ALEX_SR_V1_B_REACTION_SIDE_MATCHES_BREAK');
  return { pass: c && c.satisfied === null && c.provenance === 'UNAVAILABLE', detail: String(c && c.provenance) };
});

t('SJ-23', 'a zone status that contradicts the recorded setup type is caught once joined', function () {
  const tr = bookedBreakRetest();
  const j = F.alexGFindSetupRecordForTrade(tr, [setupFor(tr, { zoneStatusAtQualification: 'validated' })]);
  const c = conditionById(attribute(tr, j, 1).attr, 'ALEX_SR_V1_B_ZONE_STATUS_BROKEN');
  return { pass: c && c.satisfied === false, detail: JSON.stringify(c && c.observed) };
});

// ══ THE BREAK-CYCLE COUNT — a fact no single record can carry ═════════════════════════════════

t('SJ-24', 'the count is taken over zoneId AND breakCycleId AND setupType, so a retest in another '
  + 'zone or another cycle is not counted against this one', function () {
  const tr = bookedBreakRetest();
  const s = setupFor(tr);
  const others = [
    s,
    setupFor(tr, { setupId: 'x1', zoneId: 'z9' }),                       // different zone
    setupFor(tr, { setupId: 'x2', breakCycleId: 'BC|2' }),               // different cycle
    setupFor(tr, { setupId: 'x3', setupType: 'A_repeatedReaction' })     // different setup type
  ];
  return { pass: F.alexGCountBreakCycleSetups(s, others) === 1, detail: String(F.alexGCountBreakCycleSetups(s, others)) };
});

t('SJ-25', 'a record missing either half of the key counts NOTHING rather than counting over the '
  + 'wrong population', function () {
  const tr = bookedBreakRetest();
  const noCycle = F.alexGCountBreakCycleSetups(setupFor(tr, { breakCycleId: null }), [setupFor(tr)]);
  const noZone = F.alexGCountBreakCycleSetups(setupFor(tr, { zoneId: null }), [setupFor(tr)]);
  return { pass: noCycle === null && noZone === null, detail: noCycle + ',' + noZone };
});

t('SJ-26', 'POSITIVE CONTROL: a second retest in the same break cycle makes the first-retest '
  + 'condition FAIL, so SJ-17 is not passing on an unread number', function () {
  const tr = bookedBreakRetest();
  const j = F.alexGFindSetupRecordForTrade(tr, [setupFor(tr)]);
  const c = conditionById(attribute(tr, j, 2).attr, 'ALEX_SR_V1_B_FIRST_RETEST_IN_BREAK_CYCLE');
  return { pass: c && c.satisfied === false && c.observed.breakCycleSetupCount === 2, detail: JSON.stringify(c && c.observed) };
});

t('SJ-27', 'a null count leaves the condition unverified rather than assuming one', function () {
  const tr = bookedBreakRetest();
  const j = F.alexGFindSetupRecordForTrade(tr, [setupFor(tr)]);
  const c = conditionById(attribute(tr, j, null).attr, 'ALEX_SR_V1_B_FIRST_RETEST_IN_BREAK_CYCLE');
  return { pass: c && c.satisfied === null, detail: String(c && c.satisfied) };
});

// ══ SHAPE AND BACKWARD COMPATIBILITY ═════════════════════════════════════════════════════════

t('SJ-28', 'a caller that supplies nothing gets the pre-v12.45.0 attribution unchanged, and a join '
  + 'block that says so -- replay and every other seam are untouched until they opt in', function () {
  const tr = bookedBreakRetest();
  const r = F.alexGResolveAttributionInputs(tr, null, undefined);
  const a = F.alexGBuildRuleAttribution(r.record, tr.setupType, CFG, { breakCycleSetupCount: null });
  return { pass: r.record === tr && r.join.status === 'NOT_ATTEMPTED'
      && r.join.fieldsSupplied.length === 0 && r.join.breakCycleSetupCountSupplied === false
      && a.attribution.unverifiedConditionCount === 3,
    detail: r.join.status + ' unverified=' + a.attribution.unverifiedConditionCount };
});

t('SJ-29', 'every status the join can emit is enumerated, so a package can never carry one that '
  + 'no code path produces', function () {
  const emitted = ['NOT_ATTEMPTED', 'SETUP_STATE_EMPTY', 'TRADE_HAS_NO_SETUP_ID', 'SETUP_NOT_FOUND',
    'QUALIFICATION_TIMESTAMP_UNAVAILABLE', 'QUALIFICATION_TIMESTAMP_MISMATCH', 'JOINED'];
  const missing = emitted.filter(function (s) { return JOIN_STATUSES.indexOf(s) === -1; });
  return { pass: missing.length === 0 && JOIN_STATUSES.indexOf('CONTRADICTED_BY_JOIN') >= 0,
    detail: missing.length ? 'missing: ' + missing.join(',') : 'all ' + JOIN_STATUSES.length + ' enumerated' };
});

t('SJ-30', 'the join block always carries the same key set, whether it joined or not, so the '
  + 'canonical form does not change shape between packages', function () {
  const tr = bookedBreakRetest();
  const a = F.alexGResolveAttributionInputs(tr, null, 'NOT_ATTEMPTED').join;
  const b = F.alexGResolveAttributionInputs(tr, setupFor(tr), 'JOINED').join;
  return { pass: JSON.stringify(Object.keys(a).sort()) === JSON.stringify(Object.keys(b).sort()),
    detail: Object.keys(a).sort().join(',') };
});

t('SJ-31', 'the mirror version travels with the join, so a package states which mirror produced '
  + 'its attribution', function () {
  const j = F.alexGEmptySetupJoin('NOT_ATTEMPTED');
  return { pass: j.mirrorVersion === MIRROR_VERSION && !!j.mirrorVersion,
    detail: String(j.mirrorVersion) };
});

// ══ SOURCE-LEVEL: the protected constructor is NOT the repair site ════════════════════════════

t('SJ-32', 'neither protected function is touched -- the repair lives at capture time, where both '
  + 'the setup record and the closed trade are already in hand', function () {
  const ctor = /function alexGConstructLivePosition\(/.test(SRC);
  const ctorBody = SRC.slice(SRC.indexOf('function alexGConstructLivePosition('));
  const ctorPos = ctorBody.slice(0, ctorBody.indexOf('\nfunction '));
  // The constructor must STILL not copy these -- if it starts to, this join becomes dead code and
  // someone must delete it rather than leave two paths claiming the same provenance.
  const copies = /reactionSwingType:setup\.|reactionFromSide:setup\.|zoneStatusAtQualification:setup\./.test(ctorPos);
  return { pass: ctor && !copies, detail: copies ? 'constructor now copies the fields -- the join is redundant' : 'constructor unchanged' };
});

t('SJ-33', 'the capture seam performs the join read-only over alexGSetupState and forwards the '
  + 'count, rather than reaching into the engine to recompute one', function () {
  const seam = SRC.slice(SRC.indexOf('async function evidenceCaptureClosedTradesAsync'));
  const body = seam.slice(0, seam.indexOf('\n// v12.8.4'));
  return { pass: /alexGFindSetupRecordForTrade\(trade,__setups\)/.test(body)
      && /setupRecordJoinStatus:__sj\.status/.test(body)
      && /alexGCountBreakCycleSetups\(__sj\.record,__setups\)/.test(body)
      && !/alexGSetupState\s*=/.test(body) && !/\.push\(/.test(body),
    detail: 'seam joins and forwards without writing to setup state' };
});

t('SJ-34', 'the package builder consults the join rather than the raw trade for attribution '
  + 'inputs, and still emits the join block for readers', function () {
  const b = SRC.slice(SRC.indexOf('function evidenceBuildPackageFromTrade('));
  const body = b.slice(0, b.indexOf('\nfunction evidenceComputeCompleteness') >= 0
    ? b.indexOf('\nfunction evidenceComputeCompleteness') : 40000);
  return { pass: /alexGResolveAttributionInputs\(trade,o\.setupRecord/.test(body)
      && /alexGBuildRuleAttribution\(__joined\.record/.test(body)
      && /setupRecordJoin:setupRecordJoin/.test(body),
    detail: 'builder wired' };
});

t('SJ-35', 'a join-induced contradiction falls back to the un-joined attribution instead of '
  + 'throwing, so a stale setup record can never destroy a trade record', function () {
  const b = SRC.slice(SRC.indexOf('function evidenceBuildPackageFromTrade('));
  const body = b.slice(0, 40000);
  const guard = /if\(attribution\.verdict==='CONTRADICTS_RECORDED_CLASSIFICATION'&&setupRecordJoin\.status==='JOINED'/.test(body);
  const fallback = /const __bare=alexGBuildRuleAttribution\(trade,/.test(body)
    && /attribution=__bare;/.test(body)
    && /status:'CONTRADICTED_BY_JOIN'/.test(body);
  // and the ORIGINAL throw must still be there for a trade that contradicts its own stored fields
  const stillThrows = /throw new Error\('EVIDENCE_RULE_ATTRIBUTION_MISMATCH/.test(body);
  return { pass: guard && fallback && stillThrows,
    detail: 'guard=' + guard + ' fallback=' + fallback + ' throwKept=' + stillThrows };
});

t('SJ-36', 'validation accepts a package with no join block at all -- the 86 preserved packages '
  + 'predate it and must still validate, import and verify', function () {
  const v = SRC.slice(SRC.indexOf('function evidenceValidatePackage('));
  const body = v.slice(0, 20000);
  return { pass: /'setupRecordJoin' in qs&&qs\.setupRecordJoin!==null/.test(body), detail: 'present-only' };
});

t('SJ-37', 'validation rejects a carried join that names a field the join does not supply, or a '
  + 'status no code path produces', function () {
  const v = SRC.slice(SRC.indexOf('function evidenceValidatePackage('));
  const body = v.slice(0, 20000);
  return { pass: /EVIDENCE_SETUP_JOIN_STATUSES\.indexOf\(sj\.status\)===-1/.test(body)
      && /ALEX_SETUP_JOIN_FIELDS\.indexOf\(f\)===-1/.test(body)
      && /reports supplied inputs but its status is/.test(body),
    detail: 'status, field and consistency checks all present' };
});

results.forEach(function (r) {
  console.log((r.pass ? 'PASS' : 'FAIL') + ' -- ' + r.name + ': ' + r.desc + (r.detail ? '  [' + r.detail + ']' : ''));
});
const fails = results.filter(function (r) { return !r.pass; }).length;
console.log('---');
console.log(results.length + ' fixtures, ' + (results.length - fails) + ' PASS, ' + fails + ' FAIL');
process.exitCode = fails ? 1 : 0;

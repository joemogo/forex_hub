#!/usr/bin/env node
'use strict';
// ══════════════════════════════════════════════════════════════════════════════════════════════
// v12.57.2 — THE ASSISTANT COULD NOT SEE THE STRATEGY WITH ALL THE EVIDENCE
// ══════════════════════════════════════════════════════════════════════════════════════════════
//
// buildAiContext read paperAccount, journalEntries and scanData -- all JVM. ALEX has its own
// account, its own journal and its own instrument set, and has produced 261 preserved closes to
// JVM's 2. So the assistant was blind to the only strategy with a usable forward record while
// answering questions about "how am I doing" from a two-trade sample, with equal confidence.
//
// AI-1..6 pin that both strategies are present and kept apart. AI-7..12 pin the honesty rules,
// and AI-8 is the one that matters most: winRate must be reported as NOT COMPUTABLE rather than
// as 0% when nothing decisive has closed. This release exists partly because a 0%-win-rate figure
// was quoted for JVM for days -- it came from an ACCOUNT total carrying unrealised losses on open
// positions, compared against closed-trade evidence. A context builder that derives its own
// percentage would reintroduce that exact falsehood into the one surface whose output is prose the
// operator may act on.
//
// Run:  node tests/run_v158_ai_context_tests.js

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

// Build a realm holding buildAiContext plus the real computeCanonicalPerformance, and stub only
// the STATE it reads -- never the logic. The performance figures below are produced by the app's
// own function, so a fixture cannot pass by agreeing with a reimplementation.
function ctxWith(opts) {
  const o = opts || {};
  const c = { console: console, Math: Math, JSON: JSON, Object: Object, String: String,
    Number: Number, Array: Array, isFinite: isFinite, isNaN: isNaN, Date: Date };
  vm.createContext(c);
  vm.runInContext('const SCAN_PAIRS=' + JSON.stringify(o.scanPairs || ['EUR/USD', 'GBP/USD']) + ';', c);
  vm.runInContext('const ALEXG_LIVE_PAIRS=' + JSON.stringify(o.livePairs || ['EUR/USD', 'GBP/USD', 'USD/JPY']) + ';', c);
  vm.runInContext("const SWEEP_TIMEFRAME='M15';", c);
  vm.runInContext('let paperAccount=' + JSON.stringify(o.paperAccount ||
    { balance: 10000, openPositions: [] }) + ';', c);
  vm.runInContext('let journalEntries=' + JSON.stringify(o.journalEntries || []) + ';', c);
  vm.runInContext('let alexGAccount=' + JSON.stringify(o.alexAccount ||
    { balance: 10000, openPositions: [] }) + ';', c);
  vm.runInContext('let alexGJournalEntries=' + JSON.stringify(o.alexJournal || []) + ';', c);
  vm.runInContext('let scanData=' + JSON.stringify(o.scanData || {}) + ';', c);
  vm.runInContext('let pairData=' + JSON.stringify(o.pairData || {}) + ';', c);
  vm.runInContext(fn('computeCanonicalPerformance'), c);
  vm.runInContext(fn('buildAiContext'), c);
  return vm.runInContext('buildAiContext()', c);
}
const win = function (n) { const a = []; for (let i = 0; i < n; i++) a.push({ result: 'Win', resultR: 2, pnl: 200, pair: 'EUR/USD', dir: 'buy' }); return a; };
const loss = function (n) { const a = []; for (let i = 0; i < n; i++) a.push({ result: 'Loss', resultR: -1, pnl: -100, pair: 'EUR/USD', dir: 'buy' }); return a; };

const results = [];
function t(name, desc, f) {
  let pass = false, detail = '';
  try { const r = f(); pass = !!(r && r.pass); detail = (r && r.detail) || ''; }
  catch (e) { pass = false; detail = 'threw: ' + (e && e.message ? e.message : String(e)); }
  results.push({ name, desc, pass, detail });
}

// ══ BOTH STRATEGIES ARE VISIBLE, AND KEPT APART ══════════════════════════════════════════════

t('AI-1', 'ALEX appears at all. This is the whole defect: the assistant could not see the strategy '
  + 'holding 261 of the 263 preserved closes', function () {
  const s = ctxWith({ alexJournal: win(3).concat(loss(2)) });
  return { pass: /ALEX/.test(s) && /alex_g_sr_v1/.test(s), detail: 'ALEX named in the context' };
});

t('AI-2', 'ALEX performance is reported from its OWN journal, not JVM\'s -- reading the wrong one '
  + 'would produce a confident answer about the wrong strategy', function () {
  const s = ctxWith({ journalEntries: loss(10), alexJournal: win(4) });
  const alexLine = (s.match(/ALEX: [^\n]*/) || [''])[0];
  return { pass: /ALEX: 4 closed/.test(alexLine) && /100% win rate/.test(alexLine),
    detail: alexLine.slice(0, 90) };
});

t('AI-3', 'JVM performance still comes from JVM\'s journal -- this release must not fix one '
  + 'blindness by introducing the mirror image', function () {
  const s = ctxWith({ journalEntries: win(1).concat(loss(1)), alexJournal: win(50) });
  const jvmLine = (s.match(/JVM: [^\n]*/) || [''])[0];
  return { pass: /JVM: 2 closed/.test(jvmLine) && /50% win rate/.test(jvmLine),
    detail: jvmLine.slice(0, 90) };
});

t('AI-4', 'both accounts and both open-position sets are reported separately', function () {
  const s = ctxWith({
    paperAccount: { balance: 9500, openPositions: [{ pair: 'EUR/USD', dir: 'buy', entry: 1.1, stop: 1.09, target: 1.12 }] },
    alexAccount: { balance: 10800, openPositions: [{ pair: 'GBP/JPY', direction: 'sell', timeframe: 'H4', entry: 180, stop: 181, target: 178 }] } });
  return { pass: /JVM balance \$9500/.test(s) && /ALEX balance \$10800/.test(s)
      && /GBP\/JPY sell H4/.test(s) && /EUR\/USD buy/.test(s),
    detail: 'separate balances and open positions present' };
});

t('AI-5', 'the two instrument sets are stated and are not conflated', function () {
  const s = ctxWith({ scanPairs: ['EUR/USD', 'GBP/USD'], livePairs: ['A', 'B', 'C', 'D'] });
  return { pass: /Trades 2 pairs/.test(s) && /Trades 4 instruments/.test(s),
    detail: 'JVM 2 pairs, ALEX 4 instruments' };
});

t('AI-6', 'the model is told the two strategies are independent and their rules must not be mixed', function () {
  const s = ctxWith({});
  return { pass: /Do not mix their rules/.test(s) && /SEPARATE account and journal/.test(s),
    detail: 'independence stated explicitly' };
});

// ══ THE HONESTY RULES ════════════════════════════════════════════════════════════════════════

t('AI-7', 'a strategy with NO closed trades is reported as having none -- not as a zero record', function () {
  const s = ctxWith({ alexJournal: [] });
  return { pass: /ALEX: no closed trades yet/.test(s) && !/ALEX: 0 closed, 0% win rate/.test(s),
    detail: (s.match(/ALEX: [^\n]*/) || [''])[0].slice(0, 80) };
});

t('AI-8', 'THE ONE THAT MATTERS: with closes but nothing DECISIVE, win rate is reported as not '
  + 'computable, never as 0%. A quoted "0% win rate" for a strategy that had simply not closed a '
  + 'decisive trade is the exact falsehood this release corrects elsewhere', function () {
  const s = ctxWith({ alexJournal: [{ result: 'Break even', resultR: 0, pnl: 0 }] });
  const line = (s.match(/ALEX: [^\n]*/) || [''])[0];
  return { pass: /not computable/.test(line) && !/0% win rate/.test(line), detail: line.slice(0, 110) };
});

t('AI-9', 'a small sample is LABELLED as too small in the same line as the figure, where it cannot '
  + 'be read separately from it', function () {
  const s = ctxWith({ alexJournal: win(2).concat(loss(1)) });
  const line = (s.match(/ALEX: [^\n]*/) || [''])[0];
  return { pass: /SAMPLE TOO SMALL/.test(line), detail: line.slice(0, 110) };
});

t('AI-10', 'and a large sample is NOT labelled that way -- otherwise the caveat is decoration and '
  + 'carries no information', function () {
  const s = ctxWith({ alexJournal: win(20).concat(loss(20)) });
  const line = (s.match(/ALEX: [^\n]*/) || [''])[0];
  return { pass: !/SAMPLE TOO SMALL/.test(line) && /40 closed/.test(line), detail: line.slice(0, 110) };
});

t('AI-11', 'the model is told preserved evidence is a SUBSET of account closes, so it reports a '
  + 'floor rather than a census', function () {
  const s = ctxWith({});
  return { pass: /SUBSET/.test(s) && /floor, not a census/.test(s), detail: 'coverage caveat present' };
});

t('AI-12', 'replay and forward are named as different populations that must not be pooled -- the '
  + 'single easiest way to manufacture a false result in this project', function () {
  const s = ctxWith({});
  return { pass: /different populations/.test(s) && /never be pooled/.test(s),
    detail: 'population separation stated' };
});

t('AI-13', 'the model is told what a decisive sample would be, so it cannot call a strategy good '
  + 'or bad off a handful of trades', function () {
  const s = ctxWith({});
  return { pass: /600\+/.test(s) && /consistent with chance/.test(s), detail: 'power context stated' };
});

t('AI-14', 'the confluence score is attributed to JVM and to one timeframe, so the model cannot '
  + 'quote it as an ALEX figure', function () {
  const s = ctxWith({});
  return { pass: /is a JVM figure/.test(s) && /says nothing about ALEX/.test(s) && /M15/.test(s),
    detail: 'confluence attributed correctly' };
});

t('AI-15', 'the existing refusal to report a fabricated confluence for a suppressed pair survives '
  + 'this rewrite -- it was added because an LLM cannot recover the distinction from a bare 0%', function () {
  const body = codeOf(fn('buildAiContext'));
  return { pass: /evaluationSuppressed/.test(body) && /NOT EVALUATED/.test(body),
    detail: 'suppressed-pair guard intact' };
});

t('AI-16', 'the performance figures come from computeCanonicalPerformance, not from arithmetic '
  + 'written here. A second implementation could disagree with the dashboard about the same trades', function () {
  const body = codeOf(fn('buildAiContext'));
  const usesCanonical = (body.match(/computeCanonicalPerformance\(/g) || []).length >= 2;
  const rollsOwn = /filter\([^)]*result===['"]Win['"]\)\.length/.test(body);
  return { pass: usesCanonical && !rollsOwn,
    detail: usesCanonical ? 'both strategies scored by the shared function' : 'NOT using the shared function' };
});

t('AI-17', 'the paper-only boundary is stated to the model', function () {
  const s = ctxWith({});
  return { pass: /PAPER trading only/.test(s) && /never live money/.test(s), detail: 'paper-only stated' };
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

t('GUARD-2', 'the context stays a reasonable size -- it is a system prompt sent on every message, '
  + 'and an unbounded one costs the operator tokens on every turn', function () {
  const s = ctxWith({ journalEntries: win(50), alexJournal: win(50),
    alexAccount: { balance: 1, openPositions: win(5).map(function (x, i) { return { pair: 'P' + i, direction: 'buy', entry: 1, stop: 1, target: 1 }; }) } });
  return { pass: s.length < 6000, detail: s.length + ' chars with both journals full' };
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

#!/usr/bin/env node
'use strict';
// ══════════════════════════════════════════════════════════════════════════════════════════
// fetchCandlesAroundWindow — the last unguarded candle fetcher
// ══════════════════════════════════════════════════════════════════════════════════════════
//
// WHAT THIS COVERS. ADR-011 separated transport failure from end-of-history everywhere it
// mattered for the SIGNAL path: fetchCandlesRange records why its walk stopped and classifies the
// result, so a page-2 HTTP 429 can no longer masquerade as "the broker has no more history".
// fetchCandlesAroundWindow — the fetch behind "show this trade on the chart" — never got that
// treatment. docs/KNOWN_ISSUES.md records it as "also unguarded and returns a bare array with no
// completeness at all -- display-only, lower concern".
//
// Lower concern is not no concern. The array it returns is written straight into
// currentChartCandles and drawn, with the trade's own entry, stop and target lines on top. A
// failed page therefore produces a trade-review chart that is quietly missing bars and looks
// exactly like a healthy one — while the operator uses it to judge whether a trade was good.
//
// These fixtures drive the REAL function, extracted verbatim from index.html, against a stubbed
// fetch. They do not reimplement it: a second copy of the walk would be a second source of truth.
//
// Run:  node tests/run_v140_focus_window_fetch_tests.js

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const INDEX = path.resolve(__dirname, '..', 'index.html');
const src = fs.readFileSync(INDEX, 'utf8');

function extractFunction(name) {
  const needle = 'function ' + name + '(';
  let start = src.indexOf(needle);
  if (start < 0) throw new Error('declaration not found: ' + name);
  if (src.indexOf(needle, start + 1) >= 0) throw new Error('declaration not unique: ' + name);
  // `function f(` is a substring of `async function f(`. Matching the inner one drops the async
  // keyword and yields a synchronous body full of `await`, which fails to compile -- and would
  // otherwise read as nine failing fixtures rather than one broken extractor.
  const ASYNC = 'async ';
  if (src.slice(start - ASYNC.length, start) === ASYNC) start -= ASYNC.length;
  let depth = 0;
  for (let j = src.indexOf('{', start); j < src.length; j++) {
    if (src[j] === '{') depth++;
    else if (src[j] === '}') { depth--; if (depth === 0) return src.slice(start, j + 1); }
  }
  throw new Error('unbalanced body: ' + name);
}
function extractConst(name) {
  const all = src.match(new RegExp('^const ' + name + '=.*$', 'mg'));
  if (!all || !all.length) throw new Error('constant not found: ' + name);
  if (all.length > 1) throw new Error('constant not unique: ' + name);
  return all[0];
}

const HOUR = 3600000;
// Anchored RELATIVE TO NOW, and far enough back that a full 5000-bar first page still lands in the
// past. A fixed calendar date does not work here: the walk stops at min(toMs, Date.now()), so
// 5000 hourly bars from a fixed start run past today, the loop exits at the window end, and an
// injected second-page failure is never reached -- the fixture would then pass while testing
// nothing. Every window below therefore ends at most at `now`.
const NOW = Date.now();
const T0 = NOW - 7000 * HOUR;

// A page of OANDA-shaped candles. `complete:false` on the last bar of the newest page mirrors a
// still-forming candle, which the function filters out.
function page(startMs, count, opts) {
  const o = opts || {};
  const candles = [];
  for (let i = 0; i < count; i++) {
    const t = new Date(startMs + i * HOUR).toISOString();
    const base = 1.1 + i * 0.0001;
    candles.push({
      time: t,
      complete: (o.lastIncomplete && i === count - 1) ? false : true,
      mid: { o: base.toFixed(5), h: (base + 0.0005).toFixed(5), l: (base - 0.0005).toFixed(5), c: (base + 0.0002).toFixed(5) }
    });
  }
  return { candles: candles };
}

// Builds a realm holding the real function plus the smallest dependency set it actually reads.
function makeHarness(responses) {
  const calls = [];
  const sandbox = {
    apiBase: function () { return 'https://api.example.invalid'; },
    cfg: { key: 'TEST_KEY_NOT_A_REAL_CREDENTIAL' },
    console: console,
    Date: Date, Math: Math, JSON: JSON, Promise: Promise,
    parseFloat: parseFloat, encodeURIComponent: encodeURIComponent,
    Object: Object, Array: Array, Error: Error,
    fetch: function (url) {
      calls.push(url);
      const r = responses[calls.length - 1];
      if (!r) return Promise.resolve({ ok: true, status: 200, json: function () { return Promise.resolve({ candles: [] }); } });
      if (r.throws) return Promise.reject(new Error('network down'));
      return Promise.resolve({
        ok: r.ok !== false, status: r.status || (r.ok === false ? 500 : 200),
        json: function () { return Promise.resolve(r.body || { candles: [] }); }
      });
    }
  };
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);
  // marketDataAttachCompleteness is pulled in because the repaired function uses it; it is a
  // no-op decorator on an array, so the fixtures below run identically before and after.
  let prelude = '';
  try { prelude = extractConst('MARKET_DATA_COMPLETENESS') + '\n' + extractFunction('marketDataAttachCompleteness') + '\n'; }
  catch (e) { prelude = ''; }
  vm.runInContext(prelude + extractFunction('fetchCandlesAroundWindow'), sandbox, { filename: 'index.html:extracted' });
  return {
    calls: calls,
    run: function (fromMs, toMs) {
      sandbox.__from = fromMs; sandbox.__to = toMs;
      return vm.runInContext('fetchCandlesAroundWindow("EUR_USD","H1",__from,__to)', sandbox);
    }
  };
}

const results = [];
function t(name, desc, fn) {
  results.push({ name: name, desc: desc, fn: fn });
}
const facts = function (arr) {
  return {
    completenessState: arr && arr.completenessState,
    termination: arr && arr.paginationTerminationReason,
    httpStatus: arr && arr.httpStatus,
    pagesReceived: arr && arr.pagesReceived
  };
};

t('FWF-1', 'POSITIVE CONTROL: a healthy bounded window returns the closed candles and reports COMPLETE', async function () {
  const h = makeHarness([{ body: page(T0, 10) }]);
  const out = await h.run(T0, T0 + 10 * HOUR);
  return { pass: out.length === 10 && out[0].o > 0 && facts(out).completenessState === 'COMPLETE',
    detail: 'n=' + out.length + ' ' + JSON.stringify(facts(out)) };
});

t('FWF-2', 'the still-forming last candle is excluded, as it is on every other fetch path', async function () {
  const h = makeHarness([{ body: page(T0, 10, { lastIncomplete: true }) }]);
  const out = await h.run(T0, T0 + 10 * HOUR);
  return { pass: out.length === 9, detail: 'n=' + out.length };
});

t('FWF-3', 'genuine exhaustion — an empty second page — is COMPLETE, not a failure', async function () {
  const h = makeHarness([{ body: page(T0, 5000) }, { body: { candles: [] } }]);
  const out = await h.run(T0, NOW);
  return { pass: out.length === 5000 && facts(out).completenessState === 'COMPLETE',
    detail: 'n=' + out.length + ' ' + JSON.stringify(facts(out)) };
});

t('FWF-4', 'THE DEFECT: an HTTP failure on page two must NOT be reportable as a complete window — '
  + 'the caller has to be able to tell a truncated chart from a whole one', async function () {
  const h = makeHarness([{ body: page(T0, 5000) }, { ok: false, status: 500 }]);
  const out = await h.run(T0, NOW);
  const f = facts(out);
  return {
    pass: out.length === 5000 && f.completenessState !== 'COMPLETE' && f.termination === 'HTTP_ERROR'
      && f.httpStatus === 500,
    detail: 'n=' + out.length + ' ' + JSON.stringify(f)
  };
});

t('FWF-5', '...and the partial bars are KEPT, not discarded — the operator loses the window, not the data', async function () {
  const h = makeHarness([{ body: page(T0, 5000) }, { ok: false, status: 429 }]);
  const out = await h.run(T0, NOW);
  return { pass: out.length === 5000 && facts(out).httpStatus === 429,
    detail: 'n=' + out.length + ' status=' + facts(out).httpStatus };
});

t('FWF-6', 'a NETWORK throw mid-walk is likewise reported, and no longer collapses the whole '
  + 'window to an empty array', async function () {
  const h = makeHarness([{ body: page(T0, 5000) }, { throws: true }]);
  const out = await h.run(T0, NOW);
  const f = facts(out);
  return { pass: out.length === 5000 && f.termination === 'NETWORK_ERROR' && f.completenessState !== 'COMPLETE',
    detail: 'n=' + out.length + ' ' + JSON.stringify(f) };
});

t('FWF-7', 'a throw on the FIRST page yields an empty window that still says why', async function () {
  const h = makeHarness([{ throws: true }]);
  const out = await h.run(T0, T0 + 10 * HOUR);
  const f = facts(out);
  return { pass: out.length === 0 && f.termination === 'NETWORK_ERROR',
    detail: 'n=' + out.length + ' ' + JSON.stringify(f) };
});

t('FWF-8', 'DISCRIMINATOR: exhaustion and HTTP failure produce the same bar count but different '
  + 'states — collapsing the two is the defect itself', async function () {
  const a = makeHarness([{ body: page(T0, 5000) }, { body: { candles: [] } }]);
  const b = makeHarness([{ body: page(T0, 5000) }, { ok: false, status: 503 }]);
  const outA = await a.run(T0, NOW);
  const outB = await b.run(T0, NOW);
  return {
    pass: outA.length === outB.length
      && facts(outA).completenessState === 'COMPLETE'
      && facts(outB).completenessState !== 'COMPLETE',
    detail: 'both n=' + outA.length + '  exhausted=' + facts(outA).completenessState
      + '  http=' + facts(outB).completenessState
  };
});

t('FWF-9', 'a cursor that does not advance still terminates rather than spinning to the guard limit', async function () {
  // Every page returns the same single bar, so lastTime never moves past the cursor.
  const same = { body: page(T0, 1) };
  const h = makeHarness([same, same, same, same, same]);
  const out = await h.run(T0, NOW);
  return { pass: h.calls.length <= 2, detail: 'fetches=' + h.calls.length + ' n=' + out.length };
});

// ── The CALLER: a guard nothing consults is not a guard ───────────────────────────────────────
// focusChartOnTradeWindow is extracted verbatim too, with only the browser surfaces it touches
// stubbed. What is asserted is the DECISION -- did it draw, or did it refuse and say why.
function makeCaller(responses) {
  const drawn = { setData: null, overlay: 0, alerts: [] };
  const sandbox = {
    apiBase: function () { return 'https://api.example.invalid'; },
    cfg: { key: 'TEST_KEY_NOT_A_REAL_CREDENTIAL' },
    console: console, Date: Date, Math: Math, JSON: JSON, Promise: Promise,
    parseFloat: parseFloat, encodeURIComponent: encodeURIComponent,
    Object: Object, Array: Array, Error: Error,
    activePair: 'EUR_USD', activeTf: 'H1',
    lwChart: { timeScale: function () { return { setVisibleLogicalRange: function () {} }; } },
    candleSeries: { setData: function (d) { drawn.setData = d; } },
    drawTradeOverlay: function () { drawn.overlay++; },
    applyFitVisible: function () {},
    alert: function (m) { drawn.alerts.push(String(m)); },
    fetch: function (url) {
      const r = responses[sandbox.__n = (sandbox.__n || 0) + 1, sandbox.__n - 1];
      if (!r) return Promise.resolve({ ok: true, status: 200, json: function () { return Promise.resolve({ candles: [] }); } });
      if (r.throws) return Promise.reject(new Error('network down'));
      return Promise.resolve({ ok: r.ok !== false, status: r.status || (r.ok === false ? 500 : 200),
        json: function () { return Promise.resolve(r.body || { candles: [] }); } });
    }
  };
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);
  vm.runInContext([
    extractConst('MARKET_DATA_COMPLETENESS'),
    extractConst('CHART_FOCUS_PRE_CANDLES'),
    extractConst('CHART_TF_MS'),
    extractFunction('marketDataAttachCompleteness'),
    extractFunction('marketDataCompletenessOf'),
    extractFunction('fetchCandlesAroundWindow'),
    extractFunction('focusChartOnTradeWindow')
  ].join('\n'), sandbox, { filename: 'index.html:extracted' });
  return {
    drawn: drawn,
    show: function (fromMs) {
      sandbox.__rec = { pair: 'EUR_USD', entry: 1.1, stop: 1.09, target: 1.12,
        qualificationTimestamp: fromMs, closedAt: new Date(NOW).toISOString() };
      return vm.runInContext('focusChartOnTradeWindow(__rec)', sandbox);
    }
  };
}

t('FWF-10', 'CALLER, POSITIVE CONTROL: a COMPLETE window is drawn and the overlay is applied', async function () {
  const c = makeCaller([{ body: page(T0, 200) }]);
  await c.show(T0 + 100 * HOUR);
  return { pass: c.drawn.setData !== null && c.drawn.overlay === 1 && c.drawn.alerts.length === 0,
    detail: 'bars=' + (c.drawn.setData ? c.drawn.setData.length : 'none') + ' overlay=' + c.drawn.overlay
      + ' alerts=' + c.drawn.alerts.length };
});

t('FWF-11', 'CALLER: a PARTIAL window is NOT drawn, and the operator is told why -- the chart is '
  + 'never left showing a silently truncated market with this trade’s lines on it', async function () {
  const c = makeCaller([{ body: page(T0, 5000) }, { ok: false, status: 503 }]);
  await c.show(T0 + 100 * HOUR);
  return {
    pass: c.drawn.setData === null && c.drawn.overlay === 0 && c.drawn.alerts.length === 1
      && /HTTP_ERROR/.test(c.drawn.alerts[0]) && /503/.test(c.drawn.alerts[0]),
    detail: 'drew=' + (c.drawn.setData !== null) + ' overlay=' + c.drawn.overlay
      + ' alert=' + (c.drawn.alerts[0] || '(none)').slice(0, 90)
  };
});

t('FWF-12', 'CALLER: the refusal is driven by the completeness state, not by the bar count -- the '
  + 'refused window here holds MORE bars than the accepted one above', async function () {
  const ok = makeCaller([{ body: page(T0, 200) }]);
  const bad = makeCaller([{ body: page(T0, 5000) }, { ok: false, status: 503 }]);
  await ok.show(T0 + 100 * HOUR); await bad.show(T0 + 100 * HOUR);
  return { pass: ok.drawn.setData.length === 200 && bad.drawn.setData === null,
    detail: 'accepted 200 bars, refused a 5000-bar PARTIAL window' };
});

(async function () {
  for (const r of results) {
    try { const v = await r.fn(); r.pass = !!(v && v.pass); r.detail = (v && v.detail) || ''; }
    catch (e) { r.pass = false; r.detail = 'threw: ' + (e && e.message ? e.message : String(e)); }
  }
  results.forEach(function (r) {
    console.log((r.pass ? 'PASS' : 'FAIL') + ' -- ' + r.name + ': ' + r.desc + (r.detail ? '  [' + r.detail + ']' : ''));
  });
  const fails = results.filter(function (r) { return !r.pass; }).length;
  console.log('---');
  console.log(results.length + ' fixtures, ' + (results.length - fails) + ' PASS, ' + fails + ' FAIL');
  process.exitCode = fails ? 1 : 0;
})();

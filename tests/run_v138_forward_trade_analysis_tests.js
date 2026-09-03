#!/usr/bin/env node
'use strict';
// Fixtures for scripts/mogo_forward_trade_analysis.js.
//
// Every expected figure below is computed BY HAND in this file from packages designed so the
// arithmetic is derivable on paper -- never by calling the function under test a second way. The
// sample deliberately includes a WINNING strategy as well as a losing one: a tool only ever
// exercised against losses can hide a sign error that would flatter a profitable sample.
//
// Run:  node tests/run_v138_forward_trade_analysis_tests.js

const path = require('path');
const { rowsFromPackages, analyze, concurrentExposures, pipSizeFor, median } =
  require(path.resolve(__dirname, '..', 'scripts', 'mogo_forward_trade_analysis.js'));

const results = [];
function t(name, desc, fn) {
  let pass = false, detail = '';
  try { const r = fn(); pass = !!(r && r.pass); detail = (r && r.detail) || ''; }
  catch (e) { pass = false; detail = 'threw: ' + (e && e.message ? e.message : String(e)); }
  results.push({ name, desc, pass, detail });
}
const near = function (a, b, eps) { return a != null && Math.abs(a - b) < (eps == null ? 1e-9 : eps); };

// A minimal package builder. Only the fields the analyser reads are populated, so a fixture that
// passes because of an unrelated field cannot exist.
let hashSeq = 0;
function pkg(o) {
  o = o || {};
  return {
    packageSchemaVersion: 'mogo.evidence-package.v1',
    packageId: o.packageId || ('PKG|test|' + (++hashSeq)),
    contentHash: o.contentHash || ('hash' + hashSeq),
    identity: {
      strategyId: o.strategyId || 'test_strategy',
      strategyVersionProvenance: o.versionProvenance || 'OBSERVED'
    },
    objects: {
      candidates: [], decisions: [], marketContexts: [],
      qualifiedSetups: o.noSetup ? [] : [{
        setupId: 'S1', setupType: o.setupType || 'B_breakRetest',
        ruleAttribution: { unverifiedConditionCount: o.unverified == null ? 0 : o.unverified },
        contextRefs: { session: o.session || 'London', trendContext: 'UPTREND',
          atrAtEntry: o.atr == null ? undefined : o.atr }
      }],
      positions: [{
        positionId: 'P1', setupId: 'S1',
        instrument: o.instrument || 'EUR_USD', timeframe: o.timeframe || 'H1',
        direction: o.direction || 'buy',
        entryPrice: o.entryPrice == null ? 1.1 : o.entryPrice,
        originalStop: o.stop == null ? 1.09 : o.stop,
        entryTimestamp: o.entry || '2026-08-01T00:00:00.000Z',
        entrySpreadPips: o.spread,          // deliberately undefined when not supplied
        isDeveloperTrade: o.isDeveloperTrade === true,
        plannedRR: o.plannedR == null ? 2 : o.plannedR
      }],
      outcomes: [{
        outcomeId: 'O1', positionId: 'P1',
        recordedResultR: o.recordedResultR,
        exitTimestamp: o.exit || '2026-08-01T05:00:00.000Z',
        exitReasonCode: o.realizedR > 0 ? 'Win' : 'Loss',
        plannedR: o.plannedR == null ? 2 : o.plannedR,
        realizedR: o.realizedR,
        pnl: o.pnl,
        maeR: o.maeR, mfeR: o.mfeR,
        realizedRBasis: o.riskDistance == null ? undefined : { riskDistance: o.riskDistance }
      }]
    }
  };
}

// ── Arithmetic ────────────────────────────────────────────────────────────────────────────────

t('FTA-1', 'POSITIVE CONTROL: a PROFITABLE sample reports positive expectancy and a win rate '
  + 'above breakeven -- the tool is not wired to report loss', function () {
  // 2 wins at +2R, 2 losses at -1R => net +2R over 4 trades => +0.5R each. WR 50% vs 33.3%.
  const a = analyze(rowsFromPackages([
    pkg({ realizedR: 2, pnl: 200 }), pkg({ realizedR: 2, pnl: 200 }),
    pkg({ realizedR: -1, pnl: -100 }), pkg({ realizedR: -1, pnl: -100 })
  ]));
  return {
    pass: a.sampleSize === 4 && a.wins === 2 && near(a.netR, 2) && near(a.expectancyR, 0.5)
      && near(a.winRate, 0.5) && near(a.breakevenWinRate, 1 / 3, 1e-6)
      && a.winRateMarginVsBreakeven > 0 && a.netPnl === 200,
    detail: 'netR=' + a.netR + ' exp=' + a.expectancyR + ' wr=' + a.winRate + ' margin=' + a.winRateMarginVsBreakeven
  };
});

t('FTA-2', 'a LOSING sample at 25% over 2R targets reports the hand-computed −0.25R per trade', function () {
  // 1 win +2R, 3 losses -1R => net -1R over 4 => -0.25R each. WR 25% < 33.3%.
  const a = analyze(rowsFromPackages([
    pkg({ realizedR: 2, pnl: 200 }), pkg({ realizedR: -1, pnl: -100 }),
    pkg({ realizedR: -1, pnl: -100 }), pkg({ realizedR: -1, pnl: -100 })
  ]));
  return {
    pass: near(a.netR, -1) && near(a.expectancyR, -0.25) && near(a.winRate, 0.25)
      && a.winRateMarginVsBreakeven < 0 && a.netPnl === -100,
    detail: 'netR=' + a.netR + ' exp=' + a.expectancyR + ' pnl=' + a.netPnl
  };
});

t('FTA-3', 'breakeven win rate is 1/(1+R) -- checked at a DIFFERENT R:R so it is not a 33.3% literal', function () {
  const a = analyze(rowsFromPackages([
    pkg({ plannedR: 3, realizedR: 3, pnl: 300 }), pkg({ plannedR: 3, realizedR: -1, pnl: -100 })
  ]));
  return { pass: near(a.breakevenWinRate, 0.25, 1e-9) && a.medianPlannedR === 3,
    detail: 'breakeven=' + a.breakevenWinRate };
});

t('FTA-4', 'a MIXED-target sample refuses to report a breakeven rate rather than inventing one', function () {
  const a = analyze(rowsFromPackages([
    pkg({ plannedR: 2, realizedR: -1 }), pkg({ plannedR: 3, realizedR: -1 })
  ]));
  return { pass: a.breakevenWinRate === null && a.plannedRIsUniform === false
      && a.winRateMarginVsBreakeven === null,
    detail: 'breakeven=' + a.breakevenWinRate };
});

t('FTA-5', 'a trade with no outcome R is EXCLUDED from the sample rather than counted as zero', function () {
  const a = analyze(rowsFromPackages([
    pkg({ realizedR: -1, pnl: -100 }), pkg({ realizedR: undefined })
  ]));
  return { pass: a.sampleSize === 1 && a.openOrUnresolved === 1 && near(a.expectancyR, -1),
    detail: 'n=' + a.sampleSize + ' unresolved=' + a.openOrUnresolved };
});

// ── Spread and pip size ───────────────────────────────────────────────────────────────────────

t('FTA-6', 'spread ÷ risk is computed from the recorded risk distance -- 4.9 pips on a 13.957-pip '
  + 'stop is 35.1%, the GBP_CAD case from the real corpus', function () {
  const a = analyze(rowsFromPackages([
    pkg({ instrument: 'GBP_CAD', riskDistance: 0.0013957142857141669, spread: 4.9, realizedR: -1, pnl: -93.71 })
  ]));
  return { pass: near(a.spreadOverRisk.max, 0.351, 0.001) && a.spreadOverRisk.worstInstrument === 'GBP_CAD',
    detail: 'ratio=' + a.spreadOverRisk.max };
});

t('FTA-7', 'an UNRECORDED spread is excluded, never treated as a zero-spread entry', function () {
  const a = analyze(rowsFromPackages([
    pkg({ riskDistance: 0.001, spread: 2, realizedR: -1 }),
    pkg({ riskDistance: 0.001, realizedR: -1 })   // no spread field at all
  ]));
  return { pass: a.spreadOverRisk.n === 1 && near(a.spreadOverRisk.median, 0.2, 1e-9),
    detail: 'n=' + a.spreadOverRisk.n + ' median=' + a.spreadOverRisk.median };
});

t('FTA-8', 'JPY pairs use a 0.01 pip -- a 0.7577 risk distance on USD_JPY is 75.77 pips, not 7577', function () {
  return { pass: pipSizeFor('USD_JPY') === 0.01 && pipSizeFor('EUR_USD') === 0.0001,
    detail: 'USD_JPY=' + pipSizeFor('USD_JPY') + ' EUR_USD=' + pipSizeFor('EUR_USD') };
});

t('FTA-9', 'risk distance falls back to |entry − stop| when the outcome carries no basis', function () {
  const rows = rowsFromPackages([pkg({ entryPrice: 1.1, stop: 1.09, realizedR: -1 })]);
  return { pass: near(rows[0].riskPips, 100, 1e-6), detail: 'riskPips=' + rows[0].riskPips };
});

// ── Concurrency ───────────────────────────────────────────────────────────────────────────────

t('FTA-10', 'two SAME-instrument positions whose windows overlap are reported, with combined cost', function () {
  const rows = rowsFromPackages([
    pkg({ instrument: 'GBP_CAD', timeframe: 'H4', direction: 'buy',
      entry: '2026-08-26T05:00:00.000Z', exit: '2026-08-27T09:02:00.000Z', realizedR: -1.008, pnl: -94.46 }),
    pkg({ instrument: 'GBP_CAD', timeframe: 'H1', direction: 'buy',
      entry: '2026-08-26T10:00:00.000Z', exit: '2026-08-26T12:29:00.000Z', realizedR: -1, pnl: -93.71 })
  ]);
  const c = concurrentExposures(rows);
  // Overlap is 10:00 -> 12:29 = 2 h 29 min = 2.4833 h, rounded to 2.48.
  return { pass: c.length === 1 && c[0].instrument === 'GBP_CAD' && c[0].sameDirection === true
      && near(c[0].overlapHours, 2.48, 0.005) && near(c[0].combinedPnl, -188.17, 0.01),
    detail: JSON.stringify(c[0] || {}) };
});

t('FTA-11', 'NEGATIVE CONTROL: positions on the same instrument that do NOT overlap are not reported', function () {
  const rows = rowsFromPackages([
    pkg({ instrument: 'GBP_CAD', entry: '2026-08-26T05:00:00.000Z', exit: '2026-08-26T06:00:00.000Z', realizedR: -1 }),
    pkg({ instrument: 'GBP_CAD', entry: '2026-08-26T07:00:00.000Z', exit: '2026-08-26T08:00:00.000Z', realizedR: -1 })
  ]);
  return { pass: concurrentExposures(rows).length === 0, detail: 'n=' + concurrentExposures(rows).length };
});

t('FTA-12', 'NEGATIVE CONTROL: overlapping positions on DIFFERENT instruments are not reported', function () {
  const rows = rowsFromPackages([
    pkg({ instrument: 'GBP_CAD', entry: '2026-08-26T05:00:00.000Z', exit: '2026-08-26T12:00:00.000Z', realizedR: -1 }),
    pkg({ instrument: 'EUR_USD', entry: '2026-08-26T06:00:00.000Z', exit: '2026-08-26T11:00:00.000Z', realizedR: -1 })
  ]);
  return { pass: concurrentExposures(rows).length === 0, detail: 'n=' + concurrentExposures(rows).length };
});

t('FTA-13', 'opposite-direction overlap is reported but NOT flagged as same-direction', function () {
  const rows = rowsFromPackages([
    pkg({ instrument: 'GBP_CAD', direction: 'buy', entry: '2026-08-26T05:00:00.000Z', exit: '2026-08-26T12:00:00.000Z', realizedR: -1 }),
    pkg({ instrument: 'GBP_CAD', direction: 'sell', entry: '2026-08-26T06:00:00.000Z', exit: '2026-08-26T11:00:00.000Z', realizedR: 2 })
  ]);
  const c = concurrentExposures(rows);
  return { pass: c.length === 1 && c[0].sameDirection === false, detail: JSON.stringify(c[0] || {}) };
});

// ── Excursion ─────────────────────────────────────────────────────────────────────────────────

t('FTA-14', 'a loser whose MFE reached half its planned target is counted; one at 0.49 of it is not', function () {
  const a = analyze(rowsFromPackages([
    pkg({ plannedR: 2, realizedR: -1, mfeR: 1.0 }),    // exactly half of 2R -> counted
    pkg({ plannedR: 2, realizedR: -1, mfeR: 0.99 })    // just under -> not counted
  ]));
  return { pass: a.excursion.losersReachingHalfTarget === 1,
    detail: 'count=' + a.excursion.losersReachingHalfTarget };
});

t('FTA-15', 'losers that never moved 0.1R in favour are counted separately from those that did', function () {
  const a = analyze(rowsFromPackages([
    pkg({ realizedR: -1, mfeR: 0.079 }), pkg({ realizedR: -1, mfeR: 0.086 }),
    pkg({ realizedR: -1, mfeR: 1.843 })
  ]));
  return { pass: a.excursion.losersWithNoMeaningfulMove === 2 && a.excursion.nWithMfe === 3,
    detail: 'noMove=' + a.excursion.losersWithNoMeaningfulMove };
});

t('FTA-16', 'a sample with no MAE/MFE recorded reports null rather than 0', function () {
  const a = analyze(rowsFromPackages([pkg({ realizedR: -1 })]));
  return { pass: a.excursion.medianMfeR === null && a.excursion.medianMaeR === null,
    detail: 'mfe=' + a.excursion.medianMfeR + ' mae=' + a.excursion.medianMaeR };
});

// ── Provenance ────────────────────────────────────────────────────────────────────────────────

t('FTA-17', 'trades carrying unverified rule conditions are counted, with the worst count kept', function () {
  const a = analyze(rowsFromPackages([
    pkg({ realizedR: -1, unverified: 3 }), pkg({ realizedR: -1, unverified: 0 })
  ]));
  return { pass: a.provenance.tradesWithUnverifiedConditions === 1 && a.provenance.maxUnverifiedConditions === 3,
    detail: JSON.stringify(a.provenance) };
});

t('FTA-18', 'a DERIVED strategyVersion is counted as an identity concern; OBSERVED is not', function () {
  const a = analyze(rowsFromPackages([
    pkg({ realizedR: -1, versionProvenance: 'DERIVED' }),
    pkg({ realizedR: -1, versionProvenance: 'OBSERVED' })
  ]));
  return { pass: a.provenance.derivedStrategyVersion === 1, detail: JSON.stringify(a.provenance) };
});

// ── Helpers ───────────────────────────────────────────────────────────────────────────────────

t('FTA-19', 'median handles odd and even counts, and returns null on an empty set', function () {
  return { pass: median([3, 1, 2]) === 2 && median([1, 2, 3, 4]) === 2.5 && median([]) === null
      && median([null, undefined, NaN]) === null,
    detail: 'ok' };
});

t('FTA-20', 'a package with no qualified setup still yields its trade row -- JVM packages carry none', function () {
  const rows = rowsFromPackages([pkg({ noSetup: true, realizedR: -1.0176, pnl: -101.74, instrument: 'USD_JPY' })]);
  return { pass: rows.length === 1 && rows[0].setupType === null && near(rows[0].realizedR, -1.0176),
    detail: 'setupType=' + rows[0].setupType };
});

// ── Backfilled / MINIMAL packages ─────────────────────────────────────────────────────────────
// A backfilled trade goes through the SAME builder as a live capture, so the shape matches; what
// differs is which fields a legacy record could populate. Its outcome can carry the engine's
// recordedResultR while realizedR stays null, because realizedR is computed from an observed exit
// the old record never stored. These fix that boundary in place.

t('FTA-21', 'THE BACKFILL TRAP: a trade with recordedResultR but no realizedR is EXCLUDED by '
  + 'default and reported, never silently dropped from the denominator', function () {
  const rows = rowsFromPackages([
    pkg({ realizedR: -1, pnl: -100 }),
    pkg({ realizedR: undefined, recordedResultR: -1, pnl: -100 })
  ]);
  const a = analyze(rows);
  return {
    pass: a.sampleSize === 1 && a.coverage.recordedResultROnly === 1
      && a.coverage.withObservedRealizedR === 1 && a.coverage.recordedResultRIncluded === false,
    detail: JSON.stringify(a.coverage)
  };
});

t('FTA-22', '...and INCLUDED, with the mix reported, when the caller opts in explicitly', function () {
  const rows = rowsFromPackages([
    pkg({ realizedR: 2, pnl: 200 }),
    pkg({ realizedR: undefined, recordedResultR: -1, pnl: -100 })
  ]);
  const a = analyze(rows, true);
  // 1 win at +2R and 1 recorded loss at -1R => net +1R over 2 trades => +0.5R each.
  return {
    pass: a.sampleSize === 2 && near(a.netR, 1) && near(a.expectancyR, 0.5)
      && a.coverage.recordedResultRIncluded === true && a.coverage.recordedResultROnly === 1,
    detail: 'n=' + a.sampleSize + ' netR=' + a.netR + ' ' + JSON.stringify(a.coverage)
  };
});

t('FTA-23', 'recordedResultR is never merged into realizedR on the row itself -- the two stay '
  + 'separate fields so provenance is not laundered', function () {
  const rows = rowsFromPackages([pkg({ realizedR: undefined, recordedResultR: -1 })]);
  return { pass: rows[0].realizedR === null && rows[0].recordedResultR === -1,
    detail: 'realizedR=' + rows[0].realizedR + ' recorded=' + rows[0].recordedResultR };
});

t('FTA-24', 'a trade with NO R of any kind is counted as uncountable, distinct from a '
  + 'recorded-only one', function () {
  const a = analyze(rowsFromPackages([
    pkg({ realizedR: -1 }), pkg({ realizedR: undefined, recordedResultR: -1 }), pkg({ realizedR: undefined })
  ]));
  return { pass: a.coverage.noRAtAll === 1 && a.coverage.recordedResultROnly === 1,
    detail: JSON.stringify(a.coverage) };
});

t('FTA-25', 'a MINIMAL backfilled package -- no setup, no spread, no excursion -- still yields a '
  + 'countable trade, and drops out of only the statistics it cannot support', function () {
  const a = analyze(rowsFromPackages([
    pkg({ noSetup: true, realizedR: -1, pnl: -100, instrument: 'GBP_CAD' }),   // no spread, no MFE
    pkg({ realizedR: -1, pnl: -100, spread: 2, riskDistance: 0.001, mfeR: 0.5, maeR: 1.0 })
  ]));
  return {
    pass: a.sampleSize === 2 && a.spreadOverRisk.n === 1 && a.excursion.nWithMfe === 1
      && near(a.expectancyR, -1),
    detail: 'n=' + a.sampleSize + ' spreadN=' + a.spreadOverRisk.n + ' mfeN=' + a.excursion.nWithMfe
  };
});

t('FTA-26', 'DEVELOPER TEST TRADES are excluded from every figure by default, and reported -- a '
  + 'fabricated +$200 win must never enter a win rate', function () {
  const a = analyze(rowsFromPackages([
    pkg({ realizedR: -1, pnl: -100 }),
    pkg({ realizedR: 2, pnl: 200, isDeveloperTrade: true })
  ]));
  return {
    pass: a.sampleSize === 1 && a.wins === 0 && near(a.expectancyR, -1)
      && a.coverage.developerTradesFound === 1 && a.coverage.developerTradesIncluded === false,
    detail: 'n=' + a.sampleSize + ' wins=' + a.wins + ' ' + JSON.stringify(a.coverage)
  };
});

t('FTA-27', '...and included only on an explicit opt-in, with the count still reported', function () {
  const a = analyze(rowsFromPackages([
    pkg({ realizedR: -1, pnl: -100 }),
    pkg({ realizedR: 2, pnl: 200, isDeveloperTrade: true })
  ]), false, true);
  return { pass: a.sampleSize === 2 && a.wins === 1 && a.coverage.developerTradesIncluded === true,
    detail: 'n=' + a.sampleSize + ' wins=' + a.wins };
});

t('FTA-28', 'a package with no isDeveloperTrade field is treated as a real trade, not excluded', function () {
  const rows = rowsFromPackages([pkg({ realizedR: -1 })]);
  return { pass: rows[0].isDeveloperTrade === false, detail: String(rows[0].isDeveloperTrade) };
});

results.forEach(function (r) {
  console.log((r.pass ? 'PASS' : 'FAIL') + ' -- ' + r.name + ': ' + r.desc + (r.detail ? '  [' + r.detail + ']' : ''));
});
const fails = results.filter(function (r) { return !r.pass; }).length;
console.log('---');
console.log(results.length + ' fixtures, ' + (results.length - fails) + ' PASS, ' + fails + ' FAIL');
process.exitCode = fails ? 1 : 0;

#!/usr/bin/env node
'use strict';
// ══════════════════════════════════════════════════════════════════════════════════════════
// MOGO — forward evidence analysis (READ-ONLY DIAGNOSTIC)
// ══════════════════════════════════════════════════════════════════════════════════════════
//
// WHY THIS EXISTS
//
// Reading a handful of exported evidence packages by hand answers a question once. The same
// questions recur every time the corpus grows -- is the win rate above the breakeven threshold
// its own R:R requires, where is spread eating the risk distance, did two positions on one
// instrument overlap, how far did losers actually travel in favour before stopping out. This
// computes those from the packages themselves so the answer is reproducible rather than
// re-derived, per the repository's "prefer a diagnostic to a reconstruction" rule.
//
// WHAT IT DOES NOT DO
//
// It states no causes and recommends no rule change. Expectancy, breakeven win rate and MFE
// distributions are arithmetic over a sample; whether that sample is large enough to conclude
// anything is a judgement this tool deliberately leaves to the reader, and it prints the sample
// size next to every figure so the two cannot be separated. It never writes to the corpus, never
// touches the running app, and never opens anything outside the directory it is given.
//
// DUPLICATES ARE COLLAPSED BY CONTENT HASH. A manual export can write the same package twice
// (the browser's "(1)" copy). Counting both would inflate every total silently, so packages are
// keyed by contentHash and a repeat is reported rather than counted.
//
// Usage:
//   node scripts/mogo_forward_trade_analysis.js <dir> [--json] [--strategy <id>]

const fs = require('fs');
const path = require('path');

// ── PURE ANALYSIS ─────────────────────────────────────────────────────────────────────────────
// Separated from all IO so every figure below is testable against hand-built packages.

function pipSizeFor(instrument) {
  // Matches the app's own convention: JPY pairs quote to 0.01, everything else to 0.0001.
  return /JPY$/.test(String(instrument || '')) ? 0.01 : 0.0001;
}

// One flat row per trade, built only from fields the package actually carries. A field that is
// absent stays null and is excluded from its statistic rather than defaulted to zero -- a zero
// spread and an unrecorded spread are not the same fact.
function rowsFromPackages(packages) {
  const rows = [];
  packages.forEach(function (pkg) {
    const positions = (pkg.objects && pkg.objects.positions) || [];
    const outcomes = (pkg.objects && pkg.objects.outcomes) || [];
    const setups = (pkg.objects && pkg.objects.qualifiedSetups) || [];
    const byPosition = {};
    outcomes.forEach(function (o) { if (o && o.positionId) byPosition[o.positionId] = o; });

    positions.forEach(function (p) {
      const o = byPosition[p.positionId] || null;
      const setup = setups.find(function (s) { return s && s.setupId === p.setupId; }) || null;
      const pip = pipSizeFor(p.instrument);
      const riskDistance = (o && o.realizedRBasis && typeof o.realizedRBasis.riskDistance === 'number')
        ? o.realizedRBasis.riskDistance
        : ((typeof p.entryPrice === 'number' && typeof p.originalStop === 'number')
          ? Math.abs(p.entryPrice - p.originalStop) : null);
      const riskPips = riskDistance == null ? null : riskDistance / pip;
      const spreadPips = typeof p.entrySpreadPips === 'number' ? p.entrySpreadPips : null;

      rows.push({
        strategyId: (pkg.identity && pkg.identity.strategyId) || null,
        packageId: pkg.packageId || null,
        instrument: p.instrument || null,
        timeframe: p.timeframe || null,
        setupType: setup ? setup.setupType : null,
        direction: p.direction || null,
        entryMs: p.entryTimestamp ? Date.parse(p.entryTimestamp) : null,
        exitMs: (o && o.exitTimestamp) ? Date.parse(o.exitTimestamp) : null,
        plannedR: (o && typeof o.plannedR === 'number') ? o.plannedR
          : (typeof p.plannedRR === 'number' ? p.plannedRR : null),
        realizedR: (o && typeof o.realizedR === 'number') ? o.realizedR : null,
        // The engine's own stored R, kept BESIDE realizedR and never merged into it. The app
        // refuses to copy one into the other because "provenance would then be a lie", and this
        // tool holds the same line: a backfilled trade whose exit inputs were absent has a
        // recordedResultR and no realizedR, and which of the two a figure rests on must stay
        // visible in the output rather than being decided silently here.
        recordedResultR: (o && typeof o.recordedResultR === 'number') ? o.recordedResultR : null,
        exitReasonCode: o ? (o.exitReasonCode || null) : null,
        pnl: (o && typeof o.pnl === 'number') ? o.pnl : null,
        exitReason: o ? (o.exitReasonCode || null) : null,
        riskPips: riskPips,
        spreadPips: spreadPips,
        spreadOverRisk: (riskPips && spreadPips != null && riskPips > 0) ? spreadPips / riskPips : null,
        maeR: (o && typeof o.maeR === 'number') ? o.maeR : null,
        mfeR: (o && typeof o.mfeR === 'number') ? o.mfeR : null,
        atrAtEntry: setup && setup.contextRefs && typeof setup.contextRefs.atrAtEntry === 'number'
          ? setup.contextRefs.atrAtEntry : null,
        stopOverAtr: (setup && setup.contextRefs && typeof setup.contextRefs.atrAtEntry === 'number'
          && riskDistance != null && setup.contextRefs.atrAtEntry > 0)
          ? riskDistance / setup.contextRefs.atrAtEntry : null,
        session: setup && setup.contextRefs ? (setup.contextRefs.session || null) : null,
        trendContext: setup && setup.contextRefs ? (setup.contextRefs.trendContext || null) : null,
        unverifiedConditions: setup && setup.ruleAttribution
          && typeof setup.ruleAttribution.unverifiedConditionCount === 'number'
          ? setup.ruleAttribution.unverifiedConditionCount : null,
        strategyVersionProvenance: (pkg.identity && pkg.identity.strategyVersionProvenance) || null,
        // The builder LABELS fabricated trades on purpose -- "so a consumer can exclude them".
        // This is that consumer. Developer test trades are synthetic BUY/SELL/WIN/LOSS records
        // pushed through the real engine to check the UI; counting them would put invented
        // outcomes inside a figure meant to describe the market.
        isDeveloperTrade: !!(p && p.isDeveloperTrade)
      });
    });
  });
  return rows;
}

function median(values) {
  const v = values.filter(function (x) { return typeof x === 'number' && isFinite(x); }).slice().sort(function (a, b) { return a - b; });
  if (!v.length) return null;
  const mid = Math.floor(v.length / 2);
  return v.length % 2 ? v[mid] : (v[mid - 1] + v[mid]) / 2;
}
function sum(values) {
  return values.filter(function (x) { return typeof x === 'number' && isFinite(x); })
    .reduce(function (a, b) { return a + b; }, 0);
}

// Two positions on the SAME instrument whose open intervals overlap. The app's own guard is
// scoped to pair AND timeframe (EXISTING_OPEN_TRADE_SAME_PAIR_TIMEFRAME), so same-instrument
// exposure across two timeframes is permitted by design; this reports where it actually happened
// and what it cost, without asserting that it should have been prevented.
function concurrentExposures(rows, includeDeveloperTrades) {
  // Fabricated test trades are fired seconds apart on one instrument by design, so leaving them
  // in manufactures "concurrent exposure" events that never involved the market. They are excluded
  // here for the same reason they are excluded from every other figure -- and this was found by
  // running the tool, not by reading it: five of six reported overlaps were four TEST trades
  // opened within seven seconds of each other.
  if (!includeDeveloperTrades) rows = rows.filter(function (r) { return !r.isDeveloperTrade; });
  const out = [];
  const withTimes = rows.filter(function (r) { return r.entryMs != null && r.exitMs != null && r.instrument; });
  for (let i = 0; i < withTimes.length; i++) {
    for (let j = i + 1; j < withTimes.length; j++) {
      const a = withTimes[i], b = withTimes[j];
      if (a.instrument !== b.instrument) continue;
      const overlapStart = Math.max(a.entryMs, b.entryMs);
      const overlapEnd = Math.min(a.exitMs, b.exitMs);
      if (overlapEnd <= overlapStart) continue;
      out.push({
        instrument: a.instrument,
        timeframes: [a.timeframe, b.timeframe],
        directions: [a.direction, b.direction],
        sameDirection: a.direction === b.direction,
        overlapMs: overlapEnd - overlapStart,
        overlapHours: +((overlapEnd - overlapStart) / 3600000).toFixed(2),
        combinedRealizedR: (a.realizedR != null && b.realizedR != null) ? +(a.realizedR + b.realizedR).toFixed(3) : null,
        combinedPnl: (a.pnl != null && b.pnl != null) ? +(a.pnl + b.pnl).toFixed(2) : null
      });
    }
  }
  return out;
}

// `useRecordedR` opts a run into counting trades that carry only the engine's recordedResultR.
// It is off by default: including them silently would mix two provenances under one number. When
// on, every affected trade is counted AND reported, so the reader always knows the mix.
function analyze(rows, useRecordedR, includeDeveloperTrades) {
  const developerTrades = rows.filter(function (r) { return r.isDeveloperTrade; });
  if (!includeDeveloperTrades) rows = rows.filter(function (r) { return !r.isDeveloperTrade; });
  const observed = rows.filter(function (r) { return r.realizedR != null; });
  const recordedOnly = rows.filter(function (r) { return r.realizedR == null && r.recordedResultR != null; });
  const closed = useRecordedR
    ? observed.concat(recordedOnly.map(function (r) {
        return Object.assign({}, r, { realizedR: r.recordedResultR, rFromRecorded: true }); }))
    : observed;
  const wins = closed.filter(function (r) { return r.realizedR > 0; });
  const losses = closed.filter(function (r) { return r.realizedR <= 0; });
  const winRate = closed.length ? wins.length / closed.length : null;

  // Breakeven win rate for the sample's own planned reward:risk: 1 / (1 + R). Reported against
  // the MEDIAN plannedR, and only when every closed trade shares it -- a mixed-target sample has
  // no single threshold, and inventing one would be the kind of derived-figure-as-fact this
  // repository refuses.
  const plannedRs = closed.map(function (r) { return r.plannedR; })
    .filter(function (x) { return typeof x === 'number'; });
  const uniquePlanned = Array.from(new Set(plannedRs));
  const medianPlannedR = median(plannedRs);
  const breakevenWinRate = (uniquePlanned.length === 1 && uniquePlanned[0] > 0)
    ? 1 / (1 + uniquePlanned[0]) : null;

  const netR = closed.length ? sum(closed.map(function (r) { return r.realizedR; })) : null;
  const expectancyR = (closed.length && netR != null) ? netR / closed.length : null;

  const spreadRatios = closed.map(function (r) { return r.spreadOverRisk; })
    .filter(function (x) { return typeof x === 'number'; });

  return {
    sampleSize: closed.length,
    openOrUnresolved: rows.length - closed.length,
    // Coverage, always reported: how many trades the headline figures actually rest on, and how
    // many were left out for want of an observed exit. A silent denominator is how an expectancy
    // figure ends up describing a different sample than the reader believes.
    coverage: {
      withObservedRealizedR: observed.length,
      recordedResultROnly: recordedOnly.length,
      recordedResultRIncluded: !!useRecordedR,
      noRAtAll: rows.length - observed.length - recordedOnly.length,
      developerTradesFound: developerTrades.length,
      developerTradesIncluded: !!includeDeveloperTrades
    },
    wins: wins.length,
    losses: losses.length,
    winRate: winRate,
    medianPlannedR: medianPlannedR,
    plannedRIsUniform: uniquePlanned.length === 1,
    breakevenWinRate: breakevenWinRate,
    winRateMarginVsBreakeven: (winRate != null && breakevenWinRate != null)
      ? winRate - breakevenWinRate : null,
    netR: netR == null ? null : +netR.toFixed(3),
    expectancyR: expectancyR == null ? null : +expectancyR.toFixed(4),
    netPnl: +sum(closed.map(function (r) { return r.pnl; })).toFixed(2),
    spreadOverRisk: {
      n: spreadRatios.length,
      median: spreadRatios.length ? +median(spreadRatios).toFixed(4) : null,
      max: spreadRatios.length ? +Math.max.apply(null, spreadRatios).toFixed(4) : null,
      worstInstrument: spreadRatios.length
        ? (closed.filter(function (r) { return r.spreadOverRisk != null; })
          .sort(function (a, b) { return b.spreadOverRisk - a.spreadOverRisk; })[0] || {}).instrument || null
        : null
    },
    excursion: {
      nWithMfe: closed.filter(function (r) { return r.mfeR != null; }).length,
      medianMfeR: (function (m) { return m == null ? null : +m.toFixed(3); })(median(closed.map(function (r) { return r.mfeR; }))),
      medianMaeR: (function (m) { return m == null ? null : +m.toFixed(3); })(median(closed.map(function (r) { return r.maeR; }))),
      // Losers that travelled most of the way to target before reversing. Counted, never
      // interpreted: this number is an input to a stop-management question, not an answer to it.
      losersReachingHalfTarget: losses.filter(function (r) {
        return r.mfeR != null && r.plannedR != null && r.mfeR >= r.plannedR / 2;
      }).length,
      losersWithNoMeaningfulMove: losses.filter(function (r) {
        return r.mfeR != null && r.mfeR < 0.1;
      }).length
    },
    provenance: {
      tradesWithUnverifiedConditions: rows.filter(function (r) { return r.unverifiedConditions > 0; }).length,
      maxUnverifiedConditions: rows.reduce(function (m, r) {
        return Math.max(m, r.unverifiedConditions || 0); }, 0),
      derivedStrategyVersion: rows.filter(function (r) {
        return r.strategyVersionProvenance && r.strategyVersionProvenance !== 'OBSERVED'; }).length
    }
  };
}

function groupBy(rows, key) {
  const out = {};
  rows.forEach(function (r) {
    const k = r[key] == null ? '(none)' : String(r[key]);
    (out[k] = out[k] || []).push(r);
  });
  return out;
}

module.exports = { rowsFromPackages, analyze, concurrentExposures, pipSizeFor, median };

// ── SIDE EFFECTS ──────────────────────────────────────────────────────────────────────────────
if (require.main === module) {
  const args = process.argv.slice(2);
  const dir = args.find(function (a) { return !a.startsWith('--'); });
  const asJson = args.includes('--json');
  const useRecordedR = args.includes('--include-recorded-r');
  const includeDev = args.includes('--include-developer-trades');
  const sIdx = args.indexOf('--strategy');
  const onlyStrategy = sIdx >= 0 ? args[sIdx + 1] : null;

  if (!dir) {
    console.error('usage: node scripts/mogo_forward_trade_analysis.js <dir> [--json] [--strategy <id>]');
    process.exit(2);
  }

  const files = fs.readdirSync(dir).filter(function (f) { return /\.json$/i.test(f); });
  const seen = {}, packages = [];
  let duplicates = 0, unreadable = 0;
  files.forEach(function (f) {
    let pkg;
    try { pkg = JSON.parse(fs.readFileSync(path.join(dir, f), 'utf8')); }
    catch (e) { unreadable++; return; }
    if (!pkg || pkg.packageSchemaVersion !== 'mogo.evidence-package.v1') return;
    const key = pkg.contentHash || pkg.packageId || f;
    if (seen[key]) { duplicates++; return; }
    seen[key] = true;
    packages.push(pkg);
  });

  let rows = rowsFromPackages(packages);
  if (onlyStrategy) rows = rows.filter(function (r) { return r.strategyId === onlyStrategy; });

  const byStrategy = groupBy(rows, 'strategyId');
  const report = {
    directory: path.resolve(dir),
    filesScanned: files.length,
    packagesAccepted: packages.length,
    duplicatesCollapsed: duplicates,
    unreadableFiles: unreadable,
    strategies: {}
  };
  Object.keys(byStrategy).forEach(function (sid) {
    report.strategies[sid] = analyze(byStrategy[sid], useRecordedR, includeDev);
    report.strategies[sid].concurrentSameInstrument = concurrentExposures(byStrategy[sid], includeDev);
    report.strategies[sid].byInstrument = {};
    const inst = groupBy(byStrategy[sid], 'instrument');
    Object.keys(inst).forEach(function (i) {
      const a = analyze(inst[i], useRecordedR, includeDev);
      report.strategies[sid].byInstrument[i] = {
        n: a.sampleSize, wins: a.wins, netR: a.netR, netPnl: a.netPnl,
        medianSpreadOverRisk: a.spreadOverRisk.median
      };
    });
  });

  if (asJson) { console.log(JSON.stringify(report, null, 2)); process.exit(0); }

  const pct = function (x) { return x == null ? 'n/a' : (x * 100).toFixed(1) + '%'; };
  console.log('MOGO forward evidence analysis — ' + report.packagesAccepted + ' packages ('
    + report.duplicatesCollapsed + ' duplicate file(s) collapsed'
    + (report.unreadableFiles ? ', ' + report.unreadableFiles + ' unreadable' : '') + ')');

  Object.keys(report.strategies).forEach(function (sid) {
    const a = report.strategies[sid];
    console.log('\n── ' + sid + ' ──');
    console.log('  closed trades       : ' + a.sampleSize + (a.openOrUnresolved ? '  (' + a.openOrUnresolved + ' unresolved)' : ''));
    if (a.coverage.developerTradesFound) {
      console.log('  ! developer trades  : ' + a.coverage.developerTradesFound + ' synthetic test trade(s) '
        + (a.coverage.developerTradesIncluded
          ? 'INCLUDED (--include-developer-trades) — these are fabricated outcomes'
          : 'EXCLUDED from every figure above'));
    }
    if (a.coverage.recordedResultROnly) {
      console.log('  ! coverage          : ' + a.coverage.recordedResultROnly
        + ' trade(s) carry only the engine\'s recordedResultR, with no observed-exit realizedR'
        + (a.coverage.recordedResultRIncluded
          ? ' — INCLUDED in the figures above (--include-recorded-r)'
          : ' — EXCLUDED. Re-run with --include-recorded-r to count them.'));
    }
    if (a.coverage.noRAtAll) {
      console.log('  ! coverage          : ' + a.coverage.noRAtAll + ' trade(s) carry no R of any kind and cannot be counted');
    }
    console.log('  win rate            : ' + pct(a.winRate) + '  (' + a.wins + 'W / ' + a.losses + 'L)');
    if (a.breakevenWinRate != null) {
      console.log('  breakeven at ' + a.medianPlannedR + 'R      : ' + pct(a.breakevenWinRate)
        + '   margin ' + (a.winRateMarginVsBreakeven >= 0 ? '+' : '') + pct(a.winRateMarginVsBreakeven));
    } else {
      console.log('  breakeven win rate  : not computed — planned R:R is not uniform across the sample');
    }
    console.log('  net                 : ' + a.netR + 'R   $' + a.netPnl
      + '   (' + a.expectancyR + 'R per trade)');
    console.log('  spread ÷ risk       : median ' + pct(a.spreadOverRisk.median)
      + ', worst ' + pct(a.spreadOverRisk.max)
      + (a.spreadOverRisk.worstInstrument ? ' on ' + a.spreadOverRisk.worstInstrument : '')
      + '   [n=' + a.spreadOverRisk.n + ' of ' + a.sampleSize + ']');
    console.log('  excursion (losers)  : ' + a.excursion.losersReachingHalfTarget + ' reached ≥ half target, '
      + a.excursion.losersWithNoMeaningfulMove + ' never moved ≥ 0.1R'
      + '   [n=' + a.excursion.nWithMfe + ' of ' + a.sampleSize + ']');
    console.log('  median MFE / MAE    : ' + (a.excursion.medianMfeR == null ? 'not recorded'
      : a.excursion.medianMfeR + 'R / ' + a.excursion.medianMaeR + 'R'));
    if (a.provenance.tradesWithUnverifiedConditions) {
      console.log('  ! provenance        : ' + a.provenance.tradesWithUnverifiedConditions
        + ' trade(s) carry up to ' + a.provenance.maxUnverifiedConditions + ' unverified rule condition(s)');
    }
    if (a.provenance.derivedStrategyVersion) {
      console.log('  ! identity          : ' + a.provenance.derivedStrategyVersion
        + ' trade(s) carry a strategyVersion that was DERIVED, not observed');
    }
    if (a.concurrentSameInstrument.length) {
      console.log('  ! concurrent same-instrument exposure:');
      a.concurrentSameInstrument.forEach(function (c) {
        console.log('      ' + c.instrument + ' ' + c.timeframes.join(' + ')
          + (c.sameDirection ? ' SAME direction (' + c.directions[0] + ')' : ' opposite directions')
          + ', overlapped ' + c.overlapHours + ' h'
          + (c.combinedPnl != null ? ', combined $' + c.combinedPnl + ' / ' + c.combinedRealizedR + 'R' : ''));
      });
    }
    const insts = Object.keys(a.byInstrument);
    if (insts.length > 1) {
      console.log('  by instrument       :');
      insts.sort(function (x, y) { return (a.byInstrument[x].netR || 0) - (a.byInstrument[y].netR || 0); })
        .forEach(function (i) {
          const b = a.byInstrument[i];
          console.log('      ' + i.padEnd(9) + ' n=' + String(b.n).padStart(3) + '  ' + b.wins + 'W  '
            + String(b.netR).padStart(7) + 'R  $' + b.netPnl
            + (b.medianSpreadOverRisk != null ? '   spread/risk ' + pct(b.medianSpreadOverRisk) : ''));
        });
    }
  });
  console.log('\nFigures are arithmetic over this sample only. Whether the sample supports a');
  console.log('conclusion about the strategy is not something this tool decides.');
  process.exit(0);
}

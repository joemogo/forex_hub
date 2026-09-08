#!/usr/bin/env node
'use strict';
// ══════════════════════════════════════════════════════════════════════════════════════════════
// v12.69.0 — AOI CLOSE, AND THE SHIFTED ZONES THAT MAKE IT FALSIFIABLE
// ══════════════════════════════════════════════════════════════════════════════════════════════
//
// The arm is pre-registered in full at
// docs/trader-intelligence/rule-registers/preregistration-aoi_close_v1.md, written before any of
// this code existed and amended in §10 before the first run. These fixtures exist to hold the
// implementation to that document, not to demonstrate that it runs.
//
// The four that matter most:
//
//   AOI-1   LOOK-AHEAD, BY TRUNCATION. A trade that opened AND closed inside a prefix must be
//           identical whether the walker was given the prefix or the whole series. If it is not,
//           the arm is reading its own future and every figure it produces is worthless.
//   AOI-F1  FIRING RATE. Both the real arm and the shifted control must fire a workable and
//           BALANCED number of times on the same deterministic random walk. A control that almost
//           never fires cannot falsify anything, and a comparison against it is theatre.
//   AOI-T1  NEAREST, NOT MOST RECENT. §10.3 supersedes §3 row 6, and the fixture uses a series
//           where the two selections DISAGREE -- a positive control, so it cannot pass vacuously.
//   AOI-Z4  NO OVERLAP, FIRST-FORMED WINS. The rule that stops the zone builder from carpeting
//           the chart with bands, tested against a candidate that genuinely would have overlapped.
//
// Run:  node tests/run_v170_aoi_close_tests.js

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
// Strips `//` comments before any source assertion, so a fixture can never match its own
// explanatory prose and survive a mutation that broke the code it guards.
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

const ctx = { console: console, Math: Math, JSON: JSON, isFinite: isFinite, Array: Array,
  Number: Number, Object: Object, String: String, Date: Date, isNaN: isNaN, parseFloat: parseFloat };
vm.createContext(ctx);
vm.runInContext("const APP_VERSION='" + (/const APP_VERSION='([^']+)'/.exec(SRC)[1]) + "';", ctx);
['const AOI_CLOSE_STRATEGY_ID=', 'const AOI_CLOSE_VERSION=',
 'const AOI_CLOSE_SPREAD_FALLBACK_RISK_SHARE=', 'const RULES_AOI_CLOSE=',
 'const AOI_CLOSE_WINDOW_FROM_MS=', 'const AOI_CLOSE_WINDOW_TO_MS=',
 'const AOI_CLOSE_DAILY_FROM_MS=', 'const AOI_CLOSE_MANIFEST=']
  .forEach(function (d) { vm.runInContext(constBlock(d), ctx); });
['pipSize', 'getNYOffsetMinutes', 'nyAlignedClose', 'getCandleCloseTime',
 'alexGFindSwingPoints', 'alexGZoneRole', 'alexGWalkOutcome', 'alexGComputeMAEMFE',
 'alexGComputeTrendContext', 'carryMaxDrawdown',
 'aoiCloseExpiryMs', 'aoiCloseTouchCandidates', 'aoiCloseZoneId', 'aoiCloseFormZones',
 'aoiCloseShiftZones', 'aoiCloseMarkBreaks', 'aoiCloseActiveZones',
 'aoiCloseSignal', 'aoiCloseTarget', 'aoiCloseGeometry', 'aoiCloseHtfBiasPass',
 'aoiCloseReplayTrades', 'aoiCloseSummary', 'aoiCloseEquityCurves',
 'aoiCloseTwoSidedP', 'aoiCloseCompareArms', 'aoiCloseEvaluateCriteria',
 'aoiCloseRunAllArms', 'aoiCloseAggregate', 'aoiCloseBuildReplayPackage']
  .forEach(function (n) { vm.runInContext(fn(n), ctx); });
const P = ctx;
const CFG = vm.runInContext('RULES_AOI_CLOSE.config', ctx);
const PIP = 0.0001;
const PAIR = 'EUR_USD';

// ── candle builders ──────────────────────────────────────────────────────────────────────────
// `t` is a Date, not a number: getCandleCloseTime calls start.getTime() on the LAST candle, so a
// numeric timestamp throws there and only there. Matching the real shape, not the passing one.
const D0 = Date.UTC(2021, 0, 4, 0, 0, 0);
function dailySeries(n, base) {
  const out = [];
  for (let i = 0; i < n; i++) {
    // A HALF-pip wick, deliberately. The peaks below sit a full pip above their own body, so a
    // baseline wick any taller would out-top them and alexGFindSwingPoints would return no swing
    // at all -- which is exactly how the first draft of this file passed nothing.
    out.push({ t: new Date(D0 + i * 86400000), o: base, h: base + 0.5 * PIP, l: base - 0.5 * PIP, c: base });
  }
  return out;
}
// Turns bar `i` into a strict swing HIGH whose BODY TOP sits exactly at `price`. The wick goes a
// pip higher so the body edge, not the wick, is what the zone builder must read -- that
// distinction is the whole of §3 row 1 and a fixture that let them coincide would prove nothing.
function makeSwingHigh(bars, i, price) {
  bars[i] = { t: bars[i].t, o: price, h: price + 1 * PIP, l: bars[i].l, c: price };
  return bars;
}
function makeSwingLow(bars, i, price) {
  bars[i] = { t: bars[i].t, o: price, h: bars[i].h, l: price - 1 * PIP, c: price };
  return bars;
}
function h1Series(n, startMs, priceAt) {
  const out = [];
  for (let i = 0; i < n; i++) {
    const p = priceAt(i);
    out.push({ t: new Date(startMs + i * 3600000), o: p, h: p + 1 * PIP, l: p - 1 * PIP, c: p });
  }
  return out;
}

const results = [];
function t(name, desc, f) {
  let pass = false, detail = '';
  try { const r = f(); pass = !!(r && r.pass); detail = (r && r.detail) || ''; }
  catch (e) { pass = false; detail = 'threw: ' + (e && e.message ? e.message : String(e)); }
  results.push({ name: name, desc: desc, pass: pass, detail: detail });
}

// ══ ZONE CONSTRUCTION (§10.1) ═════════════════════════════════════════════════════════════════

t('AOI-Z1', 'a zone forms from THREE swing body edges inside 60 pips, and not from two. '
  + '"Touched at least three times" is the source rule and the count is not negotiable', function () {
  let bars = dailySeries(30, 1.1000);
  bars = makeSwingHigh(bars, 5, 1.1000);
  bars = makeSwingHigh(bars, 10, 1.1002);
  const two = P.aoiCloseFormZones(bars, CFG, PIP, PAIR);
  bars = makeSwingHigh(bars, 15, 1.1004);
  const three = P.aoiCloseFormZones(bars, CFG, PIP, PAIR);
  return { pass: two.length === 0 && three.length === 1,
    detail: 'two edges -> ' + two.length + ' zones, three edges -> ' + three.length };
});

t('AOI-Z2', 'the band is the hull of the touching BODY edges, not of the wicks. Alex uses bodies '
  + 'for everything and a wick-built band would be a different rule wearing the same name', function () {
  let bars = dailySeries(30, 1.1000);
  bars = makeSwingHigh(bars, 5, 1.1000);
  bars = makeSwingHigh(bars, 10, 1.1002);
  bars = makeSwingHigh(bars, 15, 1.1010);
  const z = P.aoiCloseFormZones(bars, CFG, PIP, PAIR)[0];
  // Wick tops sit one pip above each body top; a wick-built band would end at 1.1011.
  return { pass: z && Math.abs(z.low - 1.1000) < 1e-9 && Math.abs(z.high - 1.1010) < 1e-9,
    detail: z ? ('band ' + z.low.toFixed(5) + '..' + z.high.toFixed(5) + ' (wick top was 1.10110)') : 'no zone' };
});

t('AOI-Z3', 'a band narrower than 5 pips is expanded SYMMETRICALLY about its midpoint, per '
  + '§10.1(3). An asymmetric expansion would move the far edge and therefore every stop', function () {
  let bars = dailySeries(30, 1.1000);
  bars = makeSwingHigh(bars, 5, 1.1000);
  bars = makeSwingHigh(bars, 10, 1.1002);
  bars = makeSwingHigh(bars, 15, 1.1004);
  const z = P.aoiCloseFormZones(bars, CFG, PIP, PAIR)[0];
  if (!z) return { pass: false, detail: 'no zone formed' };
  const mid = (z.low + z.high) / 2, w = (z.high - z.low) / PIP;
  return { pass: Math.abs(w - 5) < 1e-6 && Math.abs(mid - 1.1002) < 1e-9,
    detail: 'width ' + w.toFixed(3) + ' pips, midpoint ' + mid.toFixed(6) + ' (hull midpoint was 1.100200)' };
});

t('AOI-Z4', 'NO OVERLAP, FIRST-FORMED WINS. A later candidate band that would overlap a live zone '
  + 'creates nothing and is recorded as a TOUCH of the incumbent, whose band does not move. '
  + 'POSITIVE CONTROL: the same edges placed far away DO form a second zone', function () {
  let bars = dailySeries(60, 1.1000);
  bars = makeSwingHigh(bars, 5, 1.1000);
  bars = makeSwingHigh(bars, 10, 1.1002);
  bars = makeSwingHigh(bars, 15, 1.1004);
  // Three more edges a pip away from the first band -- they must NOT create a second zone.
  let over = bars.slice();
  over = makeSwingHigh(over, 25, 1.1005);
  over = makeSwingHigh(over, 30, 1.1006);
  over = makeSwingHigh(over, 35, 1.1007);
  const zo = P.aoiCloseFormZones(over, CFG, PIP, PAIR);
  // The positive control: the same three edges 200 pips away DO form a second zone.
  let far = bars.slice();
  far = makeSwingHigh(far, 25, 1.1200);
  far = makeSwingHigh(far, 30, 1.1202);
  far = makeSwingHigh(far, 35, 1.1204);
  const zf = P.aoiCloseFormZones(far, CFG, PIP, PAIR);
  const first = zo[0];
  const widened = first && Math.abs((first.high - first.low) / PIP - 5) > 1e-6;
  return { pass: zo.length === 1 && zf.length === 2 && !widened,
    detail: 'overlapping -> ' + zo.length + ' zone, far away -> ' + zf.length + ' zones, incumbent band unchanged: ' + !widened };
});

t('AOI-Z5', 'edges spanning MORE than 60 pips form nothing. §10.2: 60 pips is a FORMATION '
  + 'CONSTRAINT, never a post-hoc clip, so no band is ever silently narrowed to fit', function () {
  let bars = dailySeries(30, 1.1000);
  bars = makeSwingHigh(bars, 5, 1.1000);
  bars = makeSwingHigh(bars, 10, 1.1030);
  bars = makeSwingHigh(bars, 15, 1.1070);
  const z = P.aoiCloseFormZones(bars, CFG, PIP, PAIR);
  return { pass: z.length === 0, detail: '70-pip span -> ' + z.length + ' zones' };
});

t('AOI-Z6', 'formation is stamped at the CONFIRMATION bar of the third touch, three daily bars '
  + 'after the swing itself. Stamping the swing bar would let a zone exist before the market had '
  + 'finished making it -- the look-ahead §10.1(5) exists to disclose', function () {
  let bars = dailySeries(30, 1.1000);
  bars = makeSwingHigh(bars, 5, 1.1000);
  bars = makeSwingHigh(bars, 10, 1.1002);
  bars = makeSwingHigh(bars, 15, 1.1004);
  const z = P.aoiCloseFormZones(bars, CFG, PIP, PAIR)[0];
  if (!z) return { pass: false, detail: 'no zone' };
  const confirmMs = P.getCandleCloseTime(bars, 18, 'D').getTime();
  const swingMs = P.getCandleCloseTime(bars, 15, 'D').getTime();
  return { pass: z.formationMs === confirmMs && z.formationMs !== swingMs && z.formationBarIndex === 18,
    detail: 'formed at bar ' + z.formationBarIndex + ' (swing was bar 15, lookback ' + CFG.swingLookback + ')' };
});

t('AOI-Z7', 'expiry runs 2 CALENDAR years from formation and is never extended by a later touch. '
  + 'Extending it would quietly make every zone immortal in a busy area', function () {
  let bars = dailySeries(30, 1.1000);
  bars = makeSwingHigh(bars, 5, 1.1000);
  bars = makeSwingHigh(bars, 10, 1.1002);
  bars = makeSwingHigh(bars, 15, 1.1004);
  const z = P.aoiCloseFormZones(bars, CFG, PIP, PAIR)[0];
  if (!z) return { pass: false, detail: 'no zone' };
  const f = new Date(z.formationMs), e = new Date(z.expiryMs);
  const calendar = e.getUTCFullYear() - f.getUTCFullYear() === 2
    && e.getUTCMonth() === f.getUTCMonth() && e.getUTCDate() === f.getUTCDate();
  const active = P.aoiCloseActiveZones([z], z.expiryMs - 1, CFG).length;
  const dead = P.aoiCloseActiveZones([z], z.expiryMs, CFG).length;
  return { pass: calendar && active === 1 && dead === 0,
    detail: 'calendar +2y: ' + calendar + ', live just before expiry: ' + active + ', at expiry: ' + dead };
});

t('AOI-Z8', 'a touch is the swing bar\'s BODY edge on the SWING SIDE -- max(open,close) for a '
  + 'swing high, min(open,close) for a swing low. Reading the wrong edge would shift every band', function () {
  const bars = dailySeries(20, 1.1000);
  bars[8] = { t: bars[8].t, o: 1.1000, h: 1.1020, l: 1.0990, c: 1.1010 };  // swing high, body top 1.1010
  const cands = P.aoiCloseTouchCandidates(bars, CFG);
  const hi = cands.filter(function (c) { return c.swingSide === 'high'; });
  return { pass: hi.length === 1 && Math.abs(hi[0].price - 1.1010) < 1e-9 && hi[0].edge === 'BODY_HIGH',
    detail: hi.length ? ('body edge ' + hi[0].price.toFixed(5) + ' (wick was 1.10200)') : 'no swing-high candidate' };
});

t('AOI-Z9', 'ALEX\'s ATR clusterer is NOT imported anywhere in this arm. §10.1 refuses it by name '
  + 'because it groups WICK anchors on an EXPERIMENTAL multiplier, and importing it would rest '
  + 'the whole result on an untuned parameter', function () {
  const body = codeOf(fn('aoiCloseFormZones') + fn('aoiCloseTouchCandidates') + fn('aoiCloseReplayTrades'));
  return { pass: !/alexGAcceptReaction|alexGAssignCluster|zoneClusterATRMultiplier|calcATR/.test(body)
      && /alexGFindSwingPoints\(/.test(body),
    detail: 'no ATR clustering; uses alexGFindSwingPoints' };
});

// ── a real scenario: a zone built from three swing LOWS, plus one far swing high to target ────
// Baseline sits ABOVE the zone prices so the three lows are strict local minima; the lone high is
// the only daily swing above entry, which is what makes the target fixtures unambiguous.
function zoneDaily(extraHighPrice) {
  let bars = dailySeries(40, 1.1020);
  bars = makeSwingLow(bars, 5, 1.1000);
  bars = makeSwingLow(bars, 10, 1.1002);
  bars = makeSwingLow(bars, 15, 1.1004);
  if (extraHighPrice != null) bars = makeSwingHigh(bars, 22, extraHighPrice);
  return bars;
}
// The mirror image, for the sell side: the same band built from three swing HIGHS with the
// baseline BELOW it, so the only daily swing LOW in the series is the far one the target uses.
// Built separately rather than reusing zoneDaily because there the zone's own three lows sit one
// pip under the entry and cap every sell at ~0.1R -- the trade is then skipped for poor reward and
// the direction fixture passes vacuously by never producing a trade at all.
function zoneDailyFromHighs(extraLowPrice) {
  let bars = dailySeries(40, 1.0980);
  bars = makeSwingHigh(bars, 5, 1.1000);
  bars = makeSwingHigh(bars, 10, 1.1002);
  bars = makeSwingHigh(bars, 15, 1.1004);
  if (extraLowPrice != null) bars = makeSwingLow(bars, 22, extraLowPrice);
  return bars;
}
const H1_START = D0 + 30 * 86400000;   // comfortably after the zone forms at daily bar 18
function h1Bars(list) {
  return list.map(function (b, i) {
    return { t: new Date(H1_START + i * 3600000), o: b.o, h: b.h, l: b.l, c: b.c };
  });
}
// Approaches the zone from ABOVE (so the zone is support and the trade is a buy), closes inside on
// bar 1, enters at bar 2's open, then runs far enough to resolve.
function buyScenarioH1() {
  return h1Bars([
    { o: 1.1010, h: 1.1012, l: 1.1008, c: 1.1010 },   // 0: prior close ABOVE the zone
    { o: 1.1008, h: 1.1009, l: 1.1001, c: 1.1002 },   // 1: FIRST close inside -> signal
    { o: 1.1002, h: 1.1005, l: 1.1000, c: 1.1003 },   // 2: entry at this open
    { o: 1.1003, h: 1.1015, l: 1.1002, c: 1.1014 },
    { o: 1.1014, h: 1.1045, l: 1.1013, c: 1.1040 },   // reaches a 4R target
    { o: 1.1040, h: 1.1042, l: 1.1038, c: 1.1040 }
  ]);
}
function runOne(daily, h1, cfgOverrides) {
  const c = Object.assign({}, CFG, cfgOverrides || {});
  const pip = PIP;
  const zones = P.aoiCloseFormZones(daily, c, pip, PAIR);
  return { zones: zones,
    run: P.aoiCloseReplayTrades(h1, daily, [], zones, c, { pair: PAIR, timeframe: 'H1' }) };
}

// ══ SIGNAL AND APPROACH DIRECTION (§3 row 3, §10.5) ═══════════════════════════════════════════

t('AOI-S1', 'the FIRST close inside a zone approached from ABOVE is a BUY -- the zone is support. '
  + 'Direction comes from the close BEFORE the qualifying one, which is the only thing that makes '
  + '"buy at support, sell at resistance" mechanical', function () {
  const r = runOne(zoneDaily(1.1100), buyScenarioH1());
  const tr = r.run.trades[0];
  return { pass: r.run.trades.length === 1 && tr.direction === 'buy' && tr.approachSide === 'support'
      && tr.signalBarIndex === 1 && tr.entryBarIndex === 2,
    detail: tr ? (tr.direction + ' from ' + tr.approachSide + ', signal bar ' + tr.signalBarIndex) : 'no trade' };
});

t('AOI-S2', 'approached from BELOW the same zone is a SELL. POSITIVE CONTROL for AOI-S1: the '
  + 'identical zone and identical qualifying close produce the OPPOSITE direction when only the '
  + 'prior close moves', function () {
  const h1 = h1Bars([
    { o: 1.0990, h: 1.0992, l: 1.0988, c: 1.0990 },   // prior close BELOW the zone
    { o: 1.0992, h: 1.1001, l: 1.0991, c: 1.1000 },   // first close inside
    { o: 1.1000, h: 1.1002, l: 1.0998, c: 1.0999 },
    { o: 1.0999, h: 1.1000, l: 1.0960, c: 1.0965 },
    { o: 1.0965, h: 1.0966, l: 1.0960, c: 1.0962 }
  ]);
  const r = runOne(zoneDailyFromHighs(1.0900), h1);
  const tr = r.run.trades[0];
  return { pass: !!tr && tr.direction === 'sell' && tr.approachSide === 'resistance',
    detail: tr ? (tr.direction + ' from ' + tr.approachSide) : 'no trade' };
});

t('AOI-S3', '§10.5: a prior close sitting EXACTLY on a zone edge reads as inside via the protected '
  + 'alexGZoneRole, so there is no approach direction and NO TRADE. POSITIVE CONTROL: moving that '
  + 'close one pip outside produces the trade', function () {
  const d = zoneDaily(1.1100);
  const z = P.aoiCloseFormZones(d, CFG, PIP, PAIR)[0];
  const onEdge = h1Bars([
    { o: z.high, h: z.high + PIP, l: z.high - PIP, c: z.high },        // exactly ON the edge
    { o: 1.1003, h: 1.1004, l: 1.1001, c: 1.1002 },
    { o: 1.1002, h: 1.1005, l: 1.1000, c: 1.1003 },
    { o: 1.1003, h: 1.1045, l: 1.1002, c: 1.1040 }
  ]);
  const outside = h1Bars([
    { o: z.high + PIP, h: z.high + 2 * PIP, l: z.high, c: z.high + PIP },  // one pip OUTSIDE
    { o: 1.1003, h: 1.1004, l: 1.1001, c: 1.1002 },
    { o: 1.1002, h: 1.1005, l: 1.1000, c: 1.1003 },
    { o: 1.1003, h: 1.1045, l: 1.1002, c: 1.1040 }
  ]);
  const a = runOne(d, onEdge).run.trades.length, b = runOne(d, outside).run.trades.length;
  return { pass: a === 0 && b === 1,
    detail: 'close on the edge -> ' + a + ' trades; one pip outside -> ' + b };
});

t('AOI-S4', 'a SECOND consecutive close inside is not a signal. "First candle that closes inside" '
  + 'is the rule, and without this the arm would re-enter every bar it spent in a zone', function () {
  const h1 = h1Bars([
    { o: 1.1010, h: 1.1012, l: 1.1008, c: 1.1010 },
    { o: 1.1008, h: 1.1009, l: 1.1001, c: 1.1002 },   // first inside
    { o: 1.1002, h: 1.1004, l: 1.1001, c: 1.1003 },   // still inside -- must NOT signal again
    { o: 1.1003, h: 1.1004, l: 1.1002, c: 1.1003 },
    { o: 1.1003, h: 1.1045, l: 1.1002, c: 1.1040 }
  ]);
  const r = runOne(zoneDaily(1.1100), h1);
  const sigBars = r.run.trades.map(function (x) { return x.signalBarIndex; });
  return { pass: r.run.trades.length === 1 && sigBars[0] === 1,
    detail: 'signal bars: [' + sigBars.join(',') + ']' };
});

// ══ TARGET (§10.3, supersedes §3 row 6) ═══════════════════════════════════════════════════════

t('AOI-T1', 'THE AMENDMENT ITSELF. Target is the NEAREST-IN-PRICE daily swing beyond entry, not '
  + 'the MOST RECENT. The fixture uses a series where the two DISAGREE -- a nearer swing high '
  + 'formed earlier and a further one formed later -- so it cannot pass under the superseded rule', function () {
  let d = dailySeries(40, 1.1020);
  d = makeSwingLow(d, 5, 1.1000); d = makeSwingLow(d, 10, 1.1002); d = makeSwingLow(d, 15, 1.1004);
  d = makeSwingHigh(d, 22, 1.1060);   // NEARER in price, EARLIER in time  (wick 1.10610)
  d = makeSwingHigh(d, 28, 1.1200);   // FURTHER in price, MORE RECENT     (wick 1.12010)
  const tgt = P.aoiCloseTarget(d, 'buy', 1.1002, CFG);
  return { pass: Math.abs(tgt - 1.1061) < 1e-9,
    detail: 'chose ' + tgt.toFixed(5) + ' (nearest 1.10610, most recent 1.12010)' };
});

t('AOI-T1b', 'A SWING POINT IS THE WICK EXTREME; A TOUCH IS A BODY EDGE. §10.1 reads bodies for '
  + 'zone construction and §10.3 reads alexGFindSwingPoints for the target, and that function '
  + 'reports c.h / c.l. Conflating the two would move every target by the wick length', function () {
  let d = dailySeries(20, 1.1020);
  d = makeSwingHigh(d, 10, 1.1060);                    // body top 1.10600, wick top 1.10610
  const tgt = P.aoiCloseTarget(d, 'buy', 1.1000, CFG);
  const touch = P.aoiCloseTouchCandidates(d, CFG).filter(function (x) { return x.swingSide === 'high'; })[0];
  return { pass: Math.abs(tgt - 1.1061) < 1e-9 && Math.abs(touch.price - 1.1060) < 1e-9,
    detail: 'target reads the wick ' + tgt.toFixed(5) + ', touch reads the body ' + touch.price.toFixed(5) };
});

t('AOI-T2', 'a swing that is not BEYOND the entry is not a target, in either direction', function () {
  let d = dailySeries(40, 1.1020);
  d = makeSwingHigh(d, 10, 1.1060);
  const above = P.aoiCloseTarget(d, 'buy', 1.1100, CFG);   // the only swing high is BELOW entry
  const ok = P.aoiCloseTarget(d, 'buy', 1.1000, CFG);
  return { pass: above === null && Math.abs(ok - 1.1061) < 1e-9,
    detail: 'entry above the swing -> ' + above + '; entry below -> ' + (ok && ok.toFixed(5)) };
});

// ══ GEOMETRY (§3 row 4, §2 rule 6) ════════════════════════════════════════════════════════════

t('AOI-G1', 'the stop sits EXACTLY 5 pips beyond the FAR edge -- zone low for a buy, zone high '
  + 'for a sell -- so risk is (entry - far edge) + 5 pips and never the near edge', function () {
  const d = zoneDaily(1.1100);
  const z = P.aoiCloseFormZones(d, CFG, PIP, PAIR)[0];
  const gBuy = P.aoiCloseGeometry(z, 'buy', 1.1002, 1.1100, CFG, PIP);
  const gSell = P.aoiCloseGeometry(z, 'sell', 1.1000, 1.0900, CFG, PIP);
  return { pass: Math.abs(gBuy.stop - (z.low - 5 * PIP)) < 1e-9
      && Math.abs(gSell.stop - (z.high + 5 * PIP)) < 1e-9
      && gBuy.farEdge === z.low && gSell.farEdge === z.high,
    detail: 'buy stop ' + gBuy.stop.toFixed(5) + ' vs zone low ' + z.low.toFixed(5)
      + '; sell stop ' + gSell.stop.toFixed(5) + ' vs zone high ' + z.high.toFixed(5) };
});

t('AOI-G2', 'planned R under 2 is SKIPPED, not taken at poor reward. POSITIVE CONTROL: the same '
  + 'geometry with a further target is accepted', function () {
  const d = zoneDaily(1.1100);
  const z = P.aoiCloseFormZones(d, CFG, PIP, PAIR)[0];
  const near = P.aoiCloseGeometry(z, 'buy', 1.1002, 1.1010, CFG, PIP);   // ~1.1R
  const far = P.aoiCloseGeometry(z, 'buy', 1.1002, 1.1030, CFG, PIP);
  return { pass: near && near.skipped === 'BELOW_MIN_RR' && far && !far.skipped && far.plannedRR >= 2,
    detail: 'near -> ' + (near && near.skipped) + ' (R ' + (near && near.plannedRR.toFixed(2))
      + '); far -> R ' + (far && far.plannedRR.toFixed(2)) };
});

t('AOI-G3', 'planned R over 4 moves the TARGET to exactly 4R rather than skipping or recording a '
  + 'larger R. The cap is on the target price, so the exit walk resolves against the capped level', function () {
  const d = zoneDaily(1.1100);
  const z = P.aoiCloseFormZones(d, CFG, PIP, PAIR)[0];
  const g = P.aoiCloseGeometry(z, 'buy', 1.1002, 1.1500, CFG, PIP);
  const risk = 1.1002 - g.stop;
  return { pass: g.capped === true && Math.abs(g.plannedRR - 4) < 1e-9
      && Math.abs(g.target - (1.1002 + 4 * risk)) < 1e-9,
    detail: 'R ' + g.plannedRR.toFixed(4) + ', target ' + g.target.toFixed(5)
      + ' (uncapped would have been 1.15000)' };
});

t('AOI-G4', 'by construction no stop is under 5 pips, because the band is at least 5 pips wide and '
  + 'the stop adds 5 more. §8 requires the share to be PRINTED anyway -- a non-zero value here '
  + 'means the zone builder produced a band it should never have produced', function () {
  const r = runOne(zoneDaily(1.1100), buyScenarioH1());
  const s = P.aoiCloseSummary(r.run.trades);
  return { pass: s.n > 0 && s.tightStopShare === 0 && s.medianRiskPips >= 5,
    detail: 'n=' + s.n + ', stops under 5 pips: ' + s.tightStopShare + ', median stop '
      + s.medianRiskPips.toFixed(2) + ' pips' };
});

// ── a deterministic random walk, used by the truncation and firing-rate fixtures ──────────────
// No Math.random anywhere: the same seed must give the same bars on every machine, or a failure
// here could never be reproduced.
function lcg(seed) { let s = seed >>> 0; return function () { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; }; }
function walkH1(n, seed, base) {
  const rnd = lcg(seed); let p = base; const out = [];
  for (let i = 0; i < n; i++) {
    const o = p; p = p + (rnd() - 0.5) * 8 * PIP;
    out.push({ t: new Date(H1_START + i * 3600000), o: o,
      h: Math.max(o, p) + rnd() * 2 * PIP, l: Math.min(o, p) - rnd() * 2 * PIP, c: p });
  }
  return out;
}
function dailyFromH1(h1) {
  const out = [];
  for (let i = 0; i + 24 <= h1.length; i += 24) {
    const g = h1.slice(i, i + 24);
    out.push({ t: g[0].t, o: g[0].o,
      h: Math.max.apply(null, g.map(function (x) { return x.h; })),
      l: Math.min.apply(null, g.map(function (x) { return x.l; })),
      c: g[g.length - 1].c });
  }
  return out;
}

// ══ LOOK-AHEAD, THE FIXTURE THAT MATTERS MOST ═════════════════════════════════════════════════

t('AOI-1', 'LOOK-AHEAD, PROVED BY TRUNCATION. Every trade that opened AND closed inside a prefix '
  + 'must be identical whether the walker was given the prefix or the whole series -- zones, '
  + 'target and geometry included. If it is not, the arm is reading its own future and every '
  + 'figure it produces is worthless', function () {
  const full = walkH1(6000, 20260908, 1.1000);
  const K = 4000;
  const trunc = full.slice(0, K);
  const rFull = P.aoiCloseReplayTrades(full, dailyFromH1(full), [],
    P.aoiCloseFormZones(dailyFromH1(full), CFG, PIP, PAIR), CFG, { pair: PAIR, timeframe: 'H1' });
  const rTrunc = P.aoiCloseReplayTrades(trunc, dailyFromH1(trunc), [],
    P.aoiCloseFormZones(dailyFromH1(trunc), CFG, PIP, PAIR), CFG, { pair: PAIR, timeframe: 'H1' });
  // A day of margin: only the boundary bar's own close time can differ between the two runs,
  // and nothing that resolved a day earlier may depend on it.
  const cut = K - 24;
  const pick = function (r) {
    return r.trades.filter(function (x) { return x.exitBarIndex < cut; })
      .map(function (x) { return JSON.stringify(x); });
  };
  const a = pick(rFull), b = pick(rTrunc);
  // ASSERT THE FILTER IS NON-EMPTY, or this passes vacuously on zero trades.
  return { pass: a.length > 0 && a.length === b.length && a.every(function (s, i) { return s === b[i]; }),
    detail: a.length + ' completed trades inside the prefix, byte-identical: '
      + (a.length > 0 && a.every(function (s, i) { return s === b[i]; })) };
});

t('AOI-1b', 'POSITIVE CONTROL FOR AOI-1: the truncation comparison is capable of FAILING. Feeding '
  + 'the walker a series whose future bars differ produces different trades, so AOI-1 is testing '
  + 'something rather than comparing a run against itself', function () {
  const full = walkH1(6000, 20260908, 1.1000);
  const other = walkH1(6000, 20260909, 1.1000);
  const run = function (h) {
    return P.aoiCloseReplayTrades(h, dailyFromH1(h), [],
      P.aoiCloseFormZones(dailyFromH1(h), CFG, PIP, PAIR), CFG, { pair: PAIR, timeframe: 'H1' });
  };
  const a = JSON.stringify(run(full).trades), b = JSON.stringify(run(other).trades);
  return { pass: a !== b && a.length > 2, detail: 'different bars -> different trades: ' + (a !== b) };
});

// ══ FIRING RATE -- WITHOUT THIS THE CONTROL IS THEATRE ════════════════════════════════════════

t('AOI-F1', 'BOTH ARMS FIRE, AND FIRE COMPARABLY, on a deterministic random walk. A shifted '
  + 'control that almost never triggers cannot falsify anything, and §5 P3 would then be decided '
  + 'by sample size rather than by edge', function () {
  const h1 = walkH1(9000, 424242, 1.1000);
  const daily = dailyFromH1(h1);
  const zones = P.aoiCloseFormZones(daily, CFG, PIP, PAIR);
  const base = P.aoiCloseReplayTrades(h1, daily, [], zones, CFG, { pair: PAIR, timeframe: 'H1' });
  const ctrl = P.aoiCloseReplayTrades(h1, daily, [], P.aoiCloseShiftZones(zones, PIP), CFG,
    { pair: PAIR, timeframe: 'H1' });
  const a = base.trades.length, b = ctrl.trades.length;
  const ratio = (a && b) ? Math.max(a, b) / Math.min(a, b) : Infinity;
  return { pass: a >= 5 && b >= 5 && ratio <= 3,
    detail: 'real ' + a + ' trades, shifted control ' + b + ', ratio ' + ratio.toFixed(2)
      + ' (zones: ' + zones.length + ')' };
});

t('AOI-F2', 'the control keeps the real arm\'s zone COUNT and WIDTHS exactly and moves only their '
  + 'LOCATION, by half each zone\'s own width. A control that differed in count or width would '
  + 'confound location with geometry', function () {
  const daily = dailyFromH1(walkH1(9000, 424242, 1.1000));
  const z = P.aoiCloseFormZones(daily, CFG, PIP, PAIR);
  const s = P.aoiCloseShiftZones(z, PIP);
  const sameCount = z.length === s.length && z.length > 0;
  const sameWidths = z.every(function (x, i) { return Math.abs((x.high - x.low) - (s[i].high - s[i].low)) < 1e-12; });
  const moved = z.every(function (x, i) { return Math.abs((s[i].low - x.low) - (x.high - x.low) / 2) < 1e-12; });
  const allMoved = z.length > 0 && z.every(function (x, i) { return s[i].low !== x.low; });
  return { pass: sameCount && sameWidths && moved && allMoved,
    detail: z.length + ' zones, widths identical: ' + sameWidths + ', each moved by half its own width: ' + moved };
});

// ══ COSTS (§4) ════════════════════════════════════════════════════════════════════════════════

t('AOI-C1', 'spread is charged PER TRADE against that trade\'s OWN risk, never against the mean. '
  + 'This repository has already had one arm\'s result hidden by a mean-level charge, so the '
  + 'fixture checks the arithmetic trade by trade', function () {
  const h1 = walkH1(9000, 424242, 1.1000);
  const daily = dailyFromH1(h1);
  const r = P.aoiCloseReplayTrades(h1, daily, [], P.aoiCloseFormZones(daily, CFG, PIP, PAIR), CFG,
    { pair: PAIR, timeframe: 'H1', spreadPipsAt: function () { return 1.0; } });
  const decided = r.trades.filter(function (x) { return typeof x.resultR === 'number'; });
  const perTrade = decided.every(function (x) {
    return Math.abs(x.netR - (x.resultR - 1.0 / x.riskPips)) < 1e-12;
  });
  const risks = decided.map(function (x) { return x.riskPips; });
  const varied = Math.max.apply(null, risks) - Math.min.apply(null, risks) > 1;
  return { pass: decided.length >= 5 && perTrade && varied,
    detail: decided.length + ' trades, risk spread ' + Math.min.apply(null, risks).toFixed(1) + '-'
      + Math.max.apply(null, risks).toFixed(1) + ' pips, per-trade charge exact: ' + perTrade };
});

t('AOI-C2', 'a bar with no bid/ask is charged the measured forward-corpus median and FLAGGED -- '
  + 'never silently zero. POSITIVE CONTROL: supplying a real spread clears the flag', function () {
  const h1 = walkH1(4000, 424242, 1.1000);
  const daily = dailyFromH1(h1);
  const zones = P.aoiCloseFormZones(daily, CFG, PIP, PAIR);
  const none = P.aoiCloseReplayTrades(h1, daily, [], zones, CFG, { pair: PAIR, timeframe: 'H1' });
  const real = P.aoiCloseReplayTrades(h1, daily, [], zones, CFG,
    { pair: PAIR, timeframe: 'H1', spreadPipsAt: function () { return 0.8; } });
  const share = vm.runInContext('AOI_CLOSE_SPREAD_FALLBACK_RISK_SHARE', ctx);
  const flagged = none.trades.length > 0 && none.trades.every(function (x) {
    return x.spreadEstimated === true && Math.abs(x.spreadPips - x.riskPips * share) < 1e-12 && x.spreadPips > 0;
  });
  const clean = real.trades.every(function (x) { return x.spreadEstimated === false; });
  return { pass: flagged && clean && none.spreadFallbackCount === none.trades.length,
    detail: 'fallback charged on ' + none.spreadFallbackCount + '/' + none.trades.length
      + ' at ' + (share * 100) + '% of risk; real spread clears the flag: ' + clean };
});

// ══ EQUITY AND DRAWDOWN (§10.4) ═══════════════════════════════════════════════════════════════

t('AOI-E1', 'the DECIDING drawdown is daily mark-to-market and it is STRICTLY DEEPER than the '
  + 'closed-trade-only line on a path that dips while the position is open. That gap is the whole '
  + 'reason §10.4 chose mark-to-market -- it is the drawdown an operator actually sits through', function () {
  // One winner that spends three days deeply underwater before resolving.
  const trade = { stillOpen: false, netR: 2, spreadR: 0, riskPips: 10,
    mtm: [{ date: '2022-01-03', r: 0 }, { date: '2022-01-04', r: -0.9 },
          { date: '2022-01-05', r: -0.95 }, { date: '2022-01-06', r: 2 }] };
  const e = P.aoiCloseEquityCurves([trade], CFG);
  return { pass: e.markToMarketDrawdown > 0 && e.closedOnlyDrawdown === 0
      && e.markToMarketDrawdown > e.closedOnlyDrawdown,
    detail: 'mark-to-market ' + (e.markToMarketDrawdown * 100).toFixed(3) + '%, closed-only '
      + (e.closedOnlyDrawdown * 100).toFixed(3) + '%' };
});

t('AOI-E2', 'sizing is 0.5% of the HIGH-WATER MARK as of each trade\'s own open, and the drawdown '
  + 'scales with it. A fixed-fraction-of-start version would report the same number at every risk '
  + 'level and P4 would be measuring nothing', function () {
  const trades = [
    { stillOpen: false, netR: -1, spreadR: 0, riskPips: 10,
      mtm: [{ date: '2022-01-03', r: 0 }, { date: '2022-01-04', r: -1 }] },
    { stillOpen: false, netR: -1, spreadR: 0, riskPips: 10,
      mtm: [{ date: '2022-01-05', r: 0 }, { date: '2022-01-06', r: -1 }] }
  ];
  const half = P.aoiCloseEquityCurves(trades, Object.assign({}, CFG, { riskPercentHWM: 0.5 }));
  const two = P.aoiCloseEquityCurves(trades, Object.assign({}, CFG, { riskPercentHWM: 2.0 }));
  return { pass: two.closedOnlyDrawdown > half.closedOnlyDrawdown * 3.5
      && half.riskPercentHWM === 0.5,
    detail: '0.5% -> ' + (half.closedOnlyDrawdown * 100).toFixed(3) + '%, 2.0% -> '
      + (two.closedOnlyDrawdown * 100).toFixed(3) + '%' };
});

t('AOI-E3', 'both drawdowns go through the UNMODIFIED carryMaxDrawdown rather than a second '
  + 'implementation of the same statistic, which is how two figures that should agree start '
  + 'disagreeing', function () {
  const body = codeOf(fn('aoiCloseEquityCurves'));
  const reg = JSON.parse(fs.readFileSync(path.join(ROOT, 'regression-baseline.json'), 'utf8'));
  const calls = (body.match(/carryMaxDrawdown\(/g) || []).length;
  return { pass: calls === 2 && !/function\s+aoiClose\w*Drawdown/.test(SRC),
    detail: 'carryMaxDrawdown called ' + calls + ' times; no private drawdown implementation'
      + (reg.protectedFunctions ? '' : '') };
});

// ══ REPORT ════════════════════════════════════════════════════════════════════════════════════
let passed = 0, failed = 0;
results.forEach(function (r) {
  if (r.pass) { passed++; console.log('  PASS  ' + r.name + '  ' + r.desc); }
  else { failed++; console.log('  FAIL  ' + r.name + '  ' + r.desc); }
  if (r.detail) console.log('          ' + r.detail);
});
console.log('\n  ' + passed + ' / ' + (passed + failed) + ' passed');
process.exit(failed ? 1 : 0);

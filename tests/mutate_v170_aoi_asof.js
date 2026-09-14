// RUN_ALL_EXEC: node tests/mutate_v170_aoi_asof.js
//
// MUTATION COVER FOR THE AS-OF REPAIR (AOI-1c / AOI-1d / AOI-1e).
//
// A passing fixture is not evidence until breaking the mechanism makes it fail. The as-of
// filter on zoneTouchCount is one short expression, and every plausible way of getting it
// wrong is a SMALL edit to that expression -- the raw length back, the comparison reversed,
// the wrong clock, or a fallback that quietly restores the completed count. Each of these is
// VALID JavaScript: a syntax error would fail the suite for the wrong reason and prove nothing.
//
// Anchored on the expression itself. index.html is restored in a `finally`, so an interrupted
// run cannot leave a mutated production file behind.
const fs = require('fs'), cp = require('child_process'), path = require('path');
const SRC = path.resolve(__dirname, '..', 'index.html');
const SUITE = path.resolve(__dirname, 'run_v170_aoi_close_tests.js');
const original = fs.readFileSync(SRC, 'utf8');

const ASOF = "zoneTouchCount:(sig.zone.touches||[]).filter(function(__t){ return __t.confirmedAtMs<=nowMs; }).length,";
const PRED = "return __t.confirmedAtMs<=nowMs;";

const M = [
  ['A1  the raw completed touches.length restored (the original look-ahead)',
   ASOF, 'zoneTouchCount:(sig.zone.touches||[]).length,'],
  ['A2  the as-of comparison reversed: counts only touches confirmed AT OR AFTER the signal bar',
   PRED, 'return __t.confirmedAtMs>=nowMs;'],
  ['A3  the wrong clock: counted as of the trade\'s EXIT, which is the future at decision time',
   PRED, 'return __t.confirmedAtMs<=w.exitTimestamp;'],
  ['A4  the wrong clock: counted as of the ENTRY bar, one bar after the decision was made',
   PRED, 'return __t.confirmedAtMs<=h1Ms[entryBarIndex];'],
  ['A5  an empty as-of result falls back to the completed array length',
   ASOF, 'zoneTouchCount:((sig.zone.touches||[]).filter(function(__t){ return __t.confirmedAtMs<=nowMs; }).length||(sig.zone.touches||[]).length),'],
];

let caught = 0; const surv = [];
try {
  for (const [n, f, r] of M) {
    if (!original.includes(f)) { console.log('SKIP (anchor) ' + n); surv.push(n + ' [ANCHOR MISSING]'); continue; }
    if (original.split(f).length - 1 !== 1) { console.log('SKIP (ambiguous anchor) ' + n); surv.push(n + ' [AMBIGUOUS]'); continue; }
    const mutated = original.replace(f, r);
    if (mutated === original) { surv.push(n + ' [NO-OP]'); console.log('SURVIVED ' + n); continue; }
    fs.writeFileSync(SRC, mutated);
    let failed = false;
    try { cp.execSync('node ' + JSON.stringify(SUITE), { stdio: 'pipe' }); } catch (e) { failed = true; }
    if (failed) { caught++; console.log('CAUGHT   ' + n); }
    else { surv.push(n); console.log('SURVIVED ' + n); }
  }
} finally {
  fs.writeFileSync(SRC, original);
}
if (fs.readFileSync(SRC, 'utf8') !== original) { console.log('FAIL -- index.html not restored'); process.exit(1); }
console.log('\ncaught ' + caught + '  survived ' + surv.length + '  of ' + M.length);
if (surv.length) { console.log('\nSURVIVORS:'); surv.forEach(s => console.log('  - ' + s)); process.exit(1); }
console.log('PASS -- all ' + caught + ' mutations caught');

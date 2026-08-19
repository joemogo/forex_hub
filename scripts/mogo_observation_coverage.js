// ══════════════════════════════════════════════════════════════════════════════════════════
// MOGO — is the engine actually observing every configured instrument? (MOGO-022)
// ══════════════════════════════════════════════════════════════════════════════════════════
//
// WHY THIS EXISTS
//
// The standing self-check asks whether MOGO is DOING the mission rather than reporting that
// it is: are all configured instruments covered, is the observation cadence healthy, are
// there unexplained gaps. Nothing answered that offline. The evidence extractor reconstructs
// PACKAGES (closed trades) and deliberately ignores everything else, so a store holding
// 16,000 forward observations reported "41 packages" and nothing about coverage.
//
// HOW IT READS THEM
//
// Not by deserializing. Observation records do not survive `deserializePackage`, which
// filters to package-shaped objects. This reads the V8 STRING TOKENS instead -- the same
// primitive the extractor already exports -- and counts instrument symbols and timestamps.
// That is weaker than deserialization and the limit is stated rather than hidden: it proves
// an instrument APPEARS in the store, not that a specific evaluation succeeded.
//
// THE UNIFORM-COUNT TELL
//
// Symbols outside the scan universe appear too, because each record embeds a config
// snapshot listing them. They are distinguishable without guessing: they occur an IDENTICAL
// number of times as each other, while genuinely observed instruments vary. The report
// separates the two and says which is which.
//
// READ-ONLY. Refuses a live profile directory. NO NETWORK ACCESS.
//
// USAGE
//   node scripts/mogo_observation_coverage.js --store <CHECKPOINT_LEVELDB_DIR> [--json]
//   node scripts/mogo_observation_coverage.js --selftest
'use strict';

const fs = require('fs');
const path = require('path');
const ex = require('./mogo_evidence_leveldb_extract.js');

const INSTRUMENT_RE = /^[A-Z]{3}_[A-Z]{3}$/;
const STAMP_RE = /^20\d\d-\d\d-\d\dT\d\d:\d\d/;

function configuredInstruments(indexHtmlPath) {
  const src = fs.readFileSync(indexHtmlPath, 'utf8');
  const line = src.split('\n').find(l => l.startsWith('const SCAN_PAIRS='));
  if (!line) return [];
  return (line.match(/'([A-Z]{3}\/[A-Z]{3})'/g) || [])
    .map(s => s.replace(/'/g, '').replace('/', '_'));
}

function scanStore(storeDir) {
  const counts = new Map();
  const stamps = [];
  for (const f of fs.readdirSync(storeDir).sort()) {
    const p = path.join(storeDir, f);
    if (!fs.statSync(p).isFile()) continue;
    const buf = fs.readFileSync(p);
    let values = [];
    if (/\.log$/.test(f)) values = ex.readWal(buf);
    else if (/\.ldb$/.test(f)) values = ex.readSst(buf).values;
    for (const v of values) {
      for (const t of ex.stringTokens(v)) {
        if (INSTRUMENT_RE.test(t)) counts.set(t, (counts.get(t) || 0) + 1);
        else if (STAMP_RE.test(t)) stamps.push(t);
      }
    }
  }
  stamps.sort();
  return { counts, stamps };
}

function report(storeDir, indexHtmlPath) {
  ex.assertNotLive(storeDir);
  const { counts, stamps } = scanStore(storeDir);
  const configured = configuredInstruments(indexHtmlPath);
  const seen = [...counts.keys()].sort();
  const covered = configured.filter(p => counts.has(p));
  const missing = configured.filter(p => !counts.has(p));

  // Symbols that are not configured AND share one identical count are the embedded
  // config-snapshot universe, not observations. Reported separately so the coverage
  // numbers are not quietly inflated by them.
  const others = seen.filter(p => !configured.includes(p));
  const otherCounts = new Set(others.map(p => counts.get(p)));
  const uniformNonConfigured = others.length > 1 && otherCounts.size === 1;

  return {
    generated: true,
    schemaVersion: 'mogo.observation-coverage.v1',
    storeDir: path.resolve(storeDir),
    configuredCount: configured.length,
    coveredCount: covered.length,
    missingInstruments: missing,
    perConfiguredInstrument: Object.fromEntries(
      configured.map(p => [p, counts.get(p) || 0])),
    nonConfiguredSymbols: others.length,
    nonConfiguredAreUniform: uniformNonConfigured,
    nonConfiguredCount: uniformNonConfigured ? [...otherCounts][0] : null,
    earliestTimestamp: stamps[0] || null,
    latestTimestamp: stamps[stamps.length - 1] || null,
    // Stated, not implied: this proves presence in the store, not that any particular
    // evaluation completed.
    provesOnly: 'that each instrument APPEARS in the observation store, and how recently '
      + 'the store was written. It does not prove a specific evaluation succeeded.',
  };
}

function render(r) {
  const lines = ['OBSERVATION COVERAGE -- derived, read-only',
    `  store: ${r.storeDir}`,
    `  configured instruments covered: ${r.coveredCount} of ${r.configuredCount}`];
  if (r.missingInstruments.length) {
    lines.push(`  MISSING: ${r.missingInstruments.join(', ')}`);
  } else {
    lines.push('  MISSING: none');
  }
  for (const [k, v] of Object.entries(r.perConfiguredInstrument)) {
    lines.push(`     ${k.padEnd(9)} ${String(v).padStart(7)}`);
  }
  lines.push(`  non-configured symbols: ${r.nonConfiguredSymbols}`
    + (r.nonConfiguredAreUniform
      ? ` (all exactly ${r.nonConfiguredCount} -- an embedded config snapshot, not observations)`
      : ' (NOT uniform -- inspect, these may be real observations)'));
  lines.push(`  observation window: ${r.earliestTimestamp} -> ${r.latestTimestamp}`);
  lines.push(`  proves only ${r.provesOnly}`);
  return lines.join('\n');
}

function selftest() {
  let f = 0;
  const ck = (c, m) => { console.log((c ? 'PASS -- ' : 'FAIL -- ') + m); if (!c) f++; };
  const os = require('os');
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'mogo-cov-'));
  const idx = path.join(dir, 'index.html');
  fs.writeFileSync(idx, "const SCAN_PAIRS=['GBP/USD','EUR/USD'];\n");
  ck(JSON.stringify(configuredInstruments(idx)) === '["GBP_USD","EUR_USD"]',
     'the configured universe is read from SCAN_PAIRS and normalised to OANDA form');

  const enc = s => {
    const b = Buffer.from(s, 'latin1'); const L = [];
    let n = b.length; do { let x = n & 0x7f; n >>>= 7; if (n) x |= 0x80; L.push(x); } while (n);
    return Buffer.concat([Buffer.from([0x22]), Buffer.from(L), b]);
  };
  const walRecord = buf => {
    const head = Buffer.alloc(7);
    head.writeUInt16LE(buf.length, 4); head.writeUInt8(1, 6);
    return Buffer.concat([head, buf]);
  };
  const store = path.join(dir, 'store');
  fs.mkdirSync(store);
  const body = Buffer.concat([
    Buffer.from([0xff, 0x10, 0x6f]),
    enc('GBP_USD'), enc('GBP_USD'), enc('EUR_USD'),
    enc('USD_TRY'), enc('USD_ZAR'),
    enc('2026-08-19T11:59:05.482Z'), enc('2026-08-19T10:00:00.000Z'),
  ]);
  fs.writeFileSync(path.join(store, '000001.log'), walRecord(body));

  const r = report(store, idx);
  ck(r.coveredCount === 2 && r.missingInstruments.length === 0,
     'every configured instrument present is reported as covered');
  ck(r.perConfiguredInstrument.GBP_USD === 2,
     'per-instrument counts reflect the store, not a constant');
  ck(r.nonConfiguredSymbols === 2 && r.nonConfiguredAreUniform === true
     && r.nonConfiguredCount === 1,
     'non-configured symbols with one identical count are flagged as a config snapshot');
  ck(r.latestTimestamp === '2026-08-19T11:59:05.482Z',
     'the newest timestamp is reported, not the first seen');
  ck(r.earliestTimestamp === '2026-08-19T10:00:00.000Z', 'and the oldest');

  // A configured instrument absent from the store must be REPORTED, or the check is decorative.
  fs.writeFileSync(idx, "const SCAN_PAIRS=['GBP/USD','EUR/USD','AUD/JPY'];\n");
  const r2 = report(store, idx);
  ck(r2.missingInstruments.length === 1 && r2.missingInstruments[0] === 'AUD_JPY',
     'a configured instrument MISSING from the store is reported (the check can fail)');
  ck(r2.coveredCount === 2 && r2.configuredCount === 3, 'and the covered ratio reflects it');

  let refused = false;
  try {
    ex.assertNotLive(path.join(os.homedir(), 'Library', 'Application Support',
                               'Google', 'Chrome', 'Profile 2'));
  } catch (e) { refused = true; }
  ck(refused, 'a LIVE profile directory is REFUSED');

  fs.rmSync(dir, { recursive: true, force: true });
  console.log(f === 0
    ? 'SELFTEST PASS -- configured universe, coverage, missing detection, uniform-snapshot tell, live refusal'
    : 'SELFTEST FAIL -- ' + f + ' check(s) failed');
  return f === 0 ? 0 : 1;
}

function main() {
  const a = process.argv.slice(2);
  if (a.includes('--selftest')) process.exit(selftest());
  const get = k => { const i = a.indexOf(k); return i !== -1 ? a[i + 1] : null; };
  const store = get('--store');
  const idx = get('--index-html') || path.resolve(__dirname, '..', 'index.html');
  if (!store) { console.error('FAIL: --store <CHECKPOINT_LEVELDB_DIR> required'); process.exit(2); }
  const r = report(store, idx);
  console.log(a.includes('--json') ? JSON.stringify(r, null, 2) : render(r));
  process.exit(r.missingInstruments.length ? 1 : 0);
}

if (require.main === module) main();
module.exports = { report, configuredInstruments, scanStore };

// ══════════════════════════════════════════════════════════════════════════════════════════
// MOGO — preserve the PAPER account ledger from a read-only copy of localStorage (B-22 step 1)
// ══════════════════════════════════════════════════════════════════════════════════════════
//
// WHY THIS EXISTS
//
// B-22's nine missing trades exist in exactly ONE place: the `fxhub_alexg_account` key in one
// Chrome profile's localStorage, with no tracked backup anywhere. That is the same class of
// artifact whose IndexedDB twin was already destroyed once, on 2026-08-17. The authorized B-22
// sequence therefore preserves and verifies the ledger BEFORE the backfill runs, so the
// before/after comparison is grounded in something durable rather than in a live read that
// cannot be repeated.
//
// SCOPE — deliberately narrow
//
// Chrome's Local Storage LevelDB is a SINGLE database shared by every origin in the profile.
// This reads a COPY, extracts only the MOGO app origin's own `fxhub_alexg_*` keys, and writes
// only the closed-trade ledger. No other origin's data is parsed, reported, or written. The
// account blob also carries no credential material -- `fxhub_ai_key` is a separate key and is
// never read here.
//
// READ-ONLY WITH RESPECT TO THE SOURCE. Refuses to run against a live profile directory.
//
// USAGE
//   node scripts/preserve_paper_ledger.js --store <COPIED_LOCAL_STORAGE_LEVELDB_DIR> --out <FILE>
//   node scripts/preserve_paper_ledger.js --selftest
'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');
const crypto = require('crypto');
const ex = require('./mogo_evidence_leveldb_extract.js');

const LEDGER_VERSION = 'mogo.paper-ledger-preservation.v1';

// Chrome stores localStorage values as UTF-16LE with a 0x00 prefix byte, or Latin-1 with 0x01.
function decodeValue(buf) {
  if (!buf || buf.length === 0) return '';
  const tag = buf[0];
  const body = buf.subarray(1);
  if (tag === 0x00) return body.toString('utf16le');
  if (tag === 0x01) return body.toString('latin1');
  return buf.toString('utf8');
}

function candidateValues(storeDir) {
  const out = [];
  for (const f of fs.readdirSync(storeDir).sort()) {
    const p = path.join(storeDir, f);
    if (!fs.statSync(p).isFile()) continue;
    const buf = fs.readFileSync(p);
    if (/\.log$/.test(f)) out.push(...ex.readWal(buf));
    else if (/\.ldb$/.test(f)) out.push(...ex.readSst(buf).values);
  }
  return out;
}

// The account blob is the LARGEST value that parses as JSON carrying closedPositions.
// Chosen by content rather than by key, because a LevelDB value record does not carry its key
// in a form this reader reconstructs reliably -- and picking by shape cannot silently select a
// different origin's data, since no other origin has this schema.
function extractAccount(storeDir) {
  let best = null;
  for (const value of candidateValues(storeDir)) {
    const text = decodeValue(value);
    if (text.indexOf('closedPositions') === -1) continue;
    const start = text.indexOf('{');
    if (start === -1) continue;
    let parsed = null;
    try { parsed = JSON.parse(text.slice(start)); } catch (e) { continue; }
    if (!parsed || !Array.isArray(parsed.closedPositions)) continue;
    if (!best || parsed.closedPositions.length > best.closedPositions.length) best = parsed;
  }
  return best;
}

function sha256(text) {
  return crypto.createHash('sha256').update(Buffer.from(text, 'utf8')).digest('hex');
}

// Canonical per-trade identity. Sorted keys so the hash is stable against key order.
function tradeIdentity(trade) {
  return { tradeId: trade.tradeId != null ? String(trade.tradeId) : null,
            pair: trade.pair || null,
            closedAt: trade.closedAt || null,
            pnl: trade.pnl != null ? trade.pnl : null,
            hash: sha256(JSON.stringify(trade, Object.keys(trade).sort())) };
}

function buildPreservation(account, windowSize) {
  const closed = account.closedPositions || [];
  // newest-first, which is what makes slice(0,N) the NEWEST N -- the property that
  // determined WHICH trades B-22 lost.
  const identities = closed.map(tradeIdentity);
  const inWindow = identities.slice(0, windowSize);
  const outsideWindow = identities.slice(windowSize);
  const isDev = t => /^AGT\|TEST\|/.test(t.tradeId || '');
  return {
    generated: true,
    schemaVersion: LEDGER_VERSION,
    windowSize,
    balance: account.balance != null ? account.balance : null,
    openPositions: Array.isArray(account.openPositions) ? account.openPositions.length : null,
    closedTotal: closed.length,
    closedReal: identities.filter(t => !isDev(t)).length,
    closedDeveloperTest: identities.filter(isDev).length,
    withinAutomaticReMintWindow: inWindow.length,
    outsideAutomaticReMintWindow: outsideWindow.length,
    outsideWindowReal: outsideWindow.filter(t => !isDev(t)).length,
    identities,
    // One hash over the whole ordered ledger: any change to any trade, or to their
    // order, changes it. This is what a later run compares against.
    ledgerRollup: sha256(identities.map(t => t.hash).join('\n')),
  };
}

function main() {
  const a = process.argv.slice(2);
  if (a.includes('--selftest')) process.exit(selftest());
  const get = k => { const i = a.indexOf(k); return i !== -1 ? a[i + 1] : null; };
  const store = get('--store'), out = get('--out');
  const windowSize = parseInt(get('--window') || '25', 10);
  if (!store) { console.error('FAIL: --store required'); process.exit(2); }
  ex.assertNotLive(store);
  const account = extractAccount(store);
  if (!account) { console.error('FAIL: no PAPER account blob found in ' + store); process.exit(1); }
  const preservation = buildPreservation(account, windowSize);
  const { identities, ...summary } = preservation;
  console.log(JSON.stringify(summary, null, 2));
  if (out) {
    fs.mkdirSync(path.dirname(path.resolve(out)), { recursive: true });
    fs.writeFileSync(path.resolve(out), JSON.stringify(preservation, null, 2) + '\n');
    console.log('written to ' + path.resolve(out));
  }
  process.exit(0);
}

function selftest() {
  let f = 0;
  const ck = (c, m) => { console.log((c ? 'PASS -- ' : 'FAIL -- ') + m); if (!c) f++; };

  const account = { balance: 1000, openPositions: [{}], closedPositions: [
    { tradeId: 'AGT|EUR_USD|3', pair: 'EUR_USD', closedAt: '2026-03-03T00:00:00Z', pnl: 3 },
    { tradeId: 'AGT|EUR_USD|2', pair: 'EUR_USD', closedAt: '2026-02-02T00:00:00Z', pnl: 2 },
    { tradeId: 'AGT|TEST|9',    pair: 'EUR_USD', closedAt: '2026-01-05T00:00:00Z', pnl: 0 },
    { tradeId: 'AGT|EUR_USD|1', pair: 'EUR_USD', closedAt: '2026-01-01T00:00:00Z', pnl: 1 },
  ]};

  const p = buildPreservation(account, 2);
  ck(p.closedTotal === 4, 'every closed trade is counted');
  ck(p.closedReal === 3 && p.closedDeveloperTest === 1, 'developer TEST trades are counted separately');
  ck(p.withinAutomaticReMintWindow === 2 && p.outsideAutomaticReMintWindow === 2,
     'the window split matches slice(0,N) on a newest-first array');
  ck(p.outsideWindowReal === 1,
     'REAL trades outside the window are reported -- these are what a store loss would not re-mint');
  ck(p.identities[0].tradeId === 'AGT|EUR_USD|3', 'order is preserved (newest first)');

  // The rollup must be able to FAIL, or it proves nothing.
  const same = buildPreservation(JSON.parse(JSON.stringify(account)), 2);
  ck(same.ledgerRollup === p.ledgerRollup, 'the rollup is stable across identical input');
  const reordered = JSON.parse(JSON.stringify(account));
  reordered.closedPositions.reverse();
  ck(buildPreservation(reordered, 2).ledgerRollup !== p.ledgerRollup,
     'reordering the ledger CHANGES the rollup (order is identity here)');
  const mutated = JSON.parse(JSON.stringify(account));
  mutated.closedPositions[0].pnl = 999;
  ck(buildPreservation(mutated, 2).ledgerRollup !== p.ledgerRollup,
     'changing one trade CHANGES the rollup');

  // Key-order independence: the same trade written with different key order is the same trade.
  const reKeyed = JSON.parse(JSON.stringify(account));
  const t = reKeyed.closedPositions[0];
  reKeyed.closedPositions[0] = { pnl: t.pnl, closedAt: t.closedAt, pair: t.pair, tradeId: t.tradeId };
  ck(buildPreservation(reKeyed, 2).ledgerRollup === p.ledgerRollup,
     'JSON key order does NOT change the rollup');

  // Live-directory refusal must still hold through this entry point.
  let refused = false;
  try { ex.assertNotLive(path.join(os.homedir(), 'Library', 'Application Support', 'Google', 'Chrome', 'Profile 2')); }
  catch (e) { refused = true; }
  ck(refused, 'a LIVE profile directory is REFUSED');

  console.log(f === 0 ? 'SELFTEST PASS -- window split, dev-trade separation, rollup sensitivity, live refusal'
                       : 'SELFTEST FAIL -- ' + f + ' check(s) failed');
  return f === 0 ? 0 : 1;
}

if (require.main === module) main();
module.exports = { buildPreservation, tradeIdentity, decodeValue, extractAccount, LEDGER_VERSION };

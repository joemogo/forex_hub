#!/usr/bin/env node
// ══════════════════════════════════════════════════════════════════════════════════════════
// MOGO — evidence egress receiver (MOGO-005 B-3)
// ══════════════════════════════════════════════════════════════════════════════════════════
//
// WHY THIS EXISTS
//
// `browser_test_profile.sh` creates a disposable, verifiably empty Chrome profile for browser
// verification. It deliberately provides no way to get anything back OUT of that profile, and
// until now nothing else did either -- so the repository mandated a capture path it did not
// contain.
//
// The browser's own export path cannot be relied on. During the MOGO-004 Step 1 pilot an export
// produced no file AND no error: Chrome's `downloads` table for the test profile held ZERO rows
// and the profile's Preferences carried no download keys. Nothing distinguished "export
// succeeded" from "export never happened", and 50 evidence packages sat in IndexedDB for a day
// while the run was believed to have produced nothing. That defect is unfixed and is recorded in
// docs/KNOWN_ISSUES.md. This receiver is the supported workaround.
//
// WHAT IT DOES, AND POINTEDLY DOES NOT DO
//
// It accepts a POSTed body and writes those bytes to disk. It does not parse, re-encode, re-hash,
// reformat or interpret them. Evidence package contentHash values are computed INSIDE the browser
// by Web Crypto BEFORE transmission; this process only ever sees an opaque buffer. That property
// is what makes it safe to sit in an evidence chain of custody, and it is why the write is a bare
// fs.writeFileSync of the received buffer -- verbatim, with no transformation whatsoever.
//
// It never sends anything back into the page beyond an acknowledgement, and it has no route that
// reads or serves anything. It is write-only from the browser's perspective.
//
// ⚠️ POST TO http://127.0.0.1:<PORT> -- NEVER http://localhost:<PORT>
//
// This server binds IPv4 127.0.0.1. Chrome resolves `localhost` to ::1 (IPv6) on this platform --
// the app's own access log records every browser hit as ::1 -- so a POST to `localhost` is
// refused while a POST to 127.0.0.1 succeeds. The bind is deliberately left IPv4-only rather than
// "fixed": this file is adopted verbatim from the artifact that already moved ~2.7 MB of pilot
// evidence with byte-exact fidelity (50/50 packages hash-verified afterwards), and documenting a
// constraint costs nothing while changing a proven listener costs re-verification.
//
// USAGE
//   node scripts/mogo_evidence_receiver.js [--port <PORT>] [--out <DIR>] [--selftest]
//
// Defaults to port 8752 and <repo>/evidence/. That directory's contents are git-ignored: evidence
// is captured there, then preserved deliberately -- it is never committed as a side effect.
//
// VERIFY IT BEFORE TRUSTING IT WITH A RUN
//   node scripts/mogo_evidence_receiver.js --selftest
// which round-trips a payload through the real server and asserts the bytes written are identical
// to the bytes sent. There is no osascript fixture suite for this file: tests/run_all.sh invokes
// every tests/run_*_tests.js under `osascript -l JavaScript`, which cannot run a Node HTTP server.
// The self-test is the verification, and it exercises the real code path rather than a stub.

const http = require('http');
const fs = require('fs');
const path = require('path');

// ── Arguments. No dependencies, no framework -- this must run from a bare clone. ─────────────
const argv = process.argv.slice(2);
function argValue(flag, fallback) {
  const i = argv.indexOf(flag);
  return (i !== -1 && argv[i + 1] != null) ? argv[i + 1] : fallback;
}
const SELFTEST = argv.indexOf('--selftest') !== -1;
const PORT = parseInt(argValue('--port', '8752'), 10);
const DEFAULT_OUT = path.resolve(__dirname, '..', 'evidence');
const OUT = path.resolve(argValue('--out', DEFAULT_OUT));

if (!Number.isFinite(PORT) || PORT <= 0 || PORT > 65535) {
  console.error('FAIL: --port must be a valid port number, got ' + argValue('--port', '8752'));
  process.exit(2);
}

fs.mkdirSync(OUT, { recursive: true });

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, X-Filename',
  'Access-Control-Max-Age': '86400',
};

// ── The server. Body is adopted verbatim from the artifact proven during MOGO-004 recovery. ──
function createReceiver(outDir) {
  return http.createServer((req, res) => {
    if (req.method === 'OPTIONS') { res.writeHead(204, CORS); return res.end(); }
    if (req.method !== 'POST') { res.writeHead(405, CORS); return res.end('POST only'); }

    // filename from header or query, sanitized to a bare basename
    const url = new URL(req.url, 'http://localhost');
    const raw = req.headers['x-filename'] || url.searchParams.get('name') || 'payload.json';
    const name = path.basename(String(raw)).replace(/[^A-Za-z0-9._-]/g, '_');

    const chunks = [];
    req.on('data', c => chunks.push(c));
    req.on('end', () => {
      const buf = Buffer.concat(chunks);
      const dest = path.join(outDir, name);
      try {
        fs.writeFileSync(dest, buf);                       // VERBATIM -- never transform evidence
        const line = `[recv] ${new Date().toISOString()}  ${name}  ${buf.length} bytes`;
        console.log(line);
        res.writeHead(200, { ...CORS, 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ ok: true, name, bytes: buf.length }));
      } catch (e) {
        console.log(`[FAIL] ${name}: ${e.message}`);
        res.writeHead(500, { ...CORS, 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ ok: false, error: e.message }));
      }
    });
  });
}

// ── Self-test: round-trip real bytes through the real server, into a scratch directory. ──────
// Asserts byte-exact fidelity, which is the only property this process is trusted for.
if (SELFTEST) {
  const tmpOut = fs.mkdtempSync(path.join(require('os').tmpdir(), 'mogo-receiver-selftest-'));
  const server = createReceiver(tmpOut);
  let failures = 0;
  const check = (ok, msg) => { console.log((ok ? 'PASS -- ' : 'FAIL -- ') + msg); if (!ok) failures++; };

  server.listen(0, '127.0.0.1', async () => {
    const port = server.address().port;
    try {
      // A payload with non-ASCII and nested structure -- if anything re-encodes, this changes.
      const payload = JSON.stringify({ packages: [{ id: 'PKG|alex_g_sr_v1|20260501|1', note: 'é—✓', n: 1.5 }] });
      const sent = Buffer.from(payload, 'utf8');

      const r = await fetch(`http://127.0.0.1:${port}/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Filename': '../../etc/evil name.json' },
        body: sent
      });
      const j = await r.json();

      check(r.status === 200, 'a POST is accepted (status ' + r.status + ')');
      check(j.ok === true, 'the receiver acknowledges the write');
      // path.basename() discards the directory components BEFORE the charset replace runs, so
      // '../../etc/evil name.json' reduces to 'evil name.json' and then 'evil_name.json'. The
      // traversal prefix is dropped entirely rather than escaped into the filename.
      check(j.name === 'evil_name.json', 'the filename is reduced to a sanitized bare basename: ' + j.name);
      check(!j.name.includes('/') && !j.name.includes('..'), 'no separator and no traversal component survives');
      check(j.bytes === sent.length, 'reported byte count matches sent (' + j.bytes + ')');

      const written = fs.readFileSync(path.join(tmpOut, j.name));
      check(written.length === sent.length, 'written byte count matches sent');
      check(written.equals(sent), 'WRITTEN BYTES ARE IDENTICAL TO SENT BYTES -- verbatim, no transform');

      const opt = await fetch(`http://127.0.0.1:${port}/`, { method: 'OPTIONS' });
      check(opt.status === 204, 'OPTIONS preflight returns 204 so a cross-origin POST is permitted');
      const get = await fetch(`http://127.0.0.1:${port}/`);
      check(get.status === 405, 'GET is refused -- this endpoint is write-only');
    } catch (e) {
      check(false, 'self-test threw: ' + e.message);
    } finally {
      server.close();
      fs.rmSync(tmpOut, { recursive: true, force: true });
      console.log(failures === 0
        ? 'SELFTEST PASS -- receiver preserves evidence byte-for-byte'
        : `SELFTEST FAIL -- ${failures} check(s) failed`);
      process.exit(failures === 0 ? 0 : 1);
    }
  });
} else {
  createReceiver(OUT).listen(PORT, '127.0.0.1', () => {
    console.log('MOGO evidence receiver listening on http://127.0.0.1:' + PORT + ' -> ' + OUT);
    console.log('POST to http://127.0.0.1:' + PORT + ' -- NOT http://localhost:' + PORT + ' (resolves to ::1, refused).');
  });
}

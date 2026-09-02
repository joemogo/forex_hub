#!/usr/bin/env node
'use strict';
// ── Run an existing JXA fixture suite under Node, unchanged ───────────────────────────────────
//
// WHY. 36 of this repository's 41 runners are written for macOS JXA
// (`osascript -l JavaScript`). Every fixture inside them is ordinary JavaScript -- the only
// macOS-specific surface in a runner is `ObjC.import('Foundation')` and a `readFile` built from
// `$.NSString`. That tiny surface is what makes the gate unrunnable anywhere except the
// operator's Mac, which in turn means any agent working off-Mac cannot verify its own repair.
//
// WHAT THIS DOES. It supplies just enough of the JXA host object model -- `ObjC.import`,
// `ObjC.unwrap`, and `$.NSString.stringWithContentsOfFileEncodingError` -- for an unmodified
// runner file to execute under Node, then evaluates that runner in a context carrying Node's
// own globals. The runner files are NOT edited: they stay byte-identical and keep working under
// osascript exactly as before. This is a second way to execute the same suite, never a
// replacement for it, and a suite that behaves differently under the two hosts is itself a
// finding worth reporting rather than papering over.
//
// WHAT IT DOES NOT DO. It is not a general JXA emulator. Anything beyond reading a UTF-8 file --
// `Application(...)`, `delay()`, ObjC bridging of any other class -- is deliberately absent and
// throws loudly rather than returning a plausible-looking value. It grants no network, and the
// suites stub `fetch` and `localStorage` themselves.
//
// Usage, from the project root:
//   node tests/run_under_node.js tests/run_v1239_chart_aoi_fidelity_tests.js
//   node tests/run_under_node.js --all            # every runner that is not already Node-native

const fs = require('fs');
const path = require('path');
const vm = require('vm');
const { execFileSync } = require('child_process');

function jxaHost() {
  const NSUTF8StringEncoding = 4;
  const wrapped = new WeakMap();
  const $ = {
    NSUTF8StringEncoding,
    NSString: {
      // The one Foundation call the runners actually use. A missing or unreadable file yields a
      // null handle, exactly as Foundation does, so a runner's own error path is exercised
      // rather than bypassed by a thrown Node exception.
      stringWithContentsOfFileEncodingError: function (p, enc, _err) {
        try {
          const box = { __jxaString: fs.readFileSync(p, 'utf8') };
          wrapped.set(box, true);
          return box;
        } catch (e) { return null; }
      }
    }
  };
  const ObjC = {
    import: function () { /* Foundation is implicit here */ },
    unwrap: function (v) {
      if (v === null || v === undefined) return null;
      if (typeof v === 'object' && typeof v.__jxaString === 'string') return v.__jxaString;
      throw new Error('run_under_node: ObjC.unwrap called on an unsupported value — this shim '
        + 'only models string file reads. Port the runner or extend the shim deliberately.');
    }
  };
  return { $, ObjC };
}

function runOne(runnerPath) {
  const src = fs.readFileSync(runnerPath, 'utf8');
  const host = jxaHost();
  const lines = [];
  const sandbox = {
    ObjC: host.ObjC,
    $: host.$,
    console: {
      log: function () {
        const s = Array.prototype.map.call(arguments, String).join(' ');
        lines.push(s);
        process.stdout.write(s + '\n');
      },
      error: function () { console.error.apply(console, arguments); }
    },
    Promise, Date, Math, JSON, Object, Array, String, Number, Boolean, RegExp, Error,
    TypeError, RangeError, Set, Map, WeakMap, WeakSet, Symbol, isNaN, isFinite,
    parseInt, parseFloat, encodeURIComponent, decodeURIComponent, encodeURI, decodeURI,
    setTimeout, clearTimeout, setInterval, clearInterval, queueMicrotask,
    TextEncoder, TextDecoder, URL, URLSearchParams, structuredClone, ArrayBuffer,
    Uint8Array, Int32Array, Float64Array, DataView, Proxy, Reflect, BigInt, Intl
  };
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(src, sandbox, { filename: runnerPath });
  return lines;
}

function verdictOf(lines) {
  const fails = lines.filter(function (l) { return /^FAIL /.test(l); }).length;
  const runnerErr = lines.filter(function (l) { return /^RUNNER ERROR/.test(l); });
  const summary = lines.filter(function (l) {
    return /ALL .*PASSED|FAILURES:/.test(l);
  }).pop() || null;
  return { fails, runnerError: runnerErr.length ? runnerErr[0] : null, summary };
}

const args = process.argv.slice(2);
if (!args.length) {
  console.error('usage: node tests/run_under_node.js <runner.js> | --all');
  process.exit(2);
}

let targets;
if (args[0] === '--all') {
  targets = fs.readdirSync('tests')
    .filter(function (f) { return /^run_.*\.js$/.test(f) && f !== 'run_under_node.js'; })
    .map(function (f) { return path.join('tests', f); })
    .filter(function (p) { return /ObjC\.import/.test(fs.readFileSync(p, 'utf8')); });
} else {
  targets = args;
}

// A single target runs IN THIS PROCESS, so a suite that finishes from a resolved Promise still
// prints -- Node exits only once the microtask queue drains. A batch runs each target in its OWN
// child process for exactly that reason: reading a suite's verdict requires waiting for its async
// tail, and one suite's stubbed globals must never leak into the next suite's realm.
let bad = 0;

if (targets.length === 1) {
  try { runOne(targets[0]); }
  catch (e) { console.log('RUNNER ERROR: ' + ((e && e.message) ? e.message : String(e))); bad = 1; }
  process.exitCode = bad;
} else {
  const rows = [];
  targets.forEach(function (t) {
    const started = Date.now();
    let out = '', thrown = null;
    try {
      out = execFileSync(process.execPath, [__filename, t],
        { encoding: 'utf8', timeout: 300000, maxBuffer: 64 * 1024 * 1024 });
    } catch (e) {
      out = (e.stdout || '') + (e.stderr || '');
      thrown = e.status === null ? 'timed out or killed' : null;
    }
    const v = verdictOf(out.split('\n'));
    rows.push({ runner: t, ms: Date.now() - started, thrown: thrown, fails: v.fails,
      runnerError: v.runnerError, summary: v.summary });
    if (thrown || v.runnerError || v.fails || !v.summary) bad++;
  });
  console.log('=== summary: ' + rows.length + ' JXA suites executed under Node ===');
  rows.forEach(function (r) {
    const state = r.thrown ? 'THREW' : (r.runnerError ? 'RUNNER_ERROR'
      : (r.fails ? 'FAIL' : (r.summary ? 'ok' : 'NO_SUMMARY')));
    console.log([state.padEnd(12), (r.ms + 'ms').padStart(8), r.runner,
      r.summary || r.thrown || r.runnerError || '(no summary line)'].join('  '));
  });
  const okCount = rows.filter(function (r) { return !r.thrown && !r.runnerError && !r.fails && r.summary; }).length;
  console.log('--- ' + okCount + '/' + rows.length + ' suites ran clean under Node ---');
  process.exitCode = bad ? 1 : 0;
}

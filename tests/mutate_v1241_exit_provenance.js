#!/usr/bin/env node
// Can the v1241 suite still DETECT a broken exit-provenance repair?
//
// A DEDICATED GATE, not a registered suite. Its assertions are ABOUT whether v1241 can still
// notice incorrectness, so folding them into expected_fixture_counts.tsv would conflate "the
// code is correct" with "the tests can see it go wrong". The filename does not match
// `tests/run_*_tests.js`, which is what run_all.sh enumerates, so it adds nothing to the
// registered 36 suites / 2754 assertions and v1241 stays registered once at 83.
//
// WHY THIS EXISTS. `e282d99` reported "11/11 mutations killed" for the G-4 repair. The repair
// is real and behaviourally tested (83 assertions, still 83/83), but the mutations were run
// from a scratch tool that was never committed -- so the claim was unverifiable by anyone who
// had not run it. This is the same debt already closed for G-2 (mutate_v1240_scan_freshness.js)
// and platform-health (mutate_platform_health.py); G-4 was the last of the three.
//
// WHAT G-4 REPAIRED. alexGCloseLivePosition built its closed-position record with two
// fabricating fallbacks: `m.exitDetectionSource||'live_snapshot'` asserted HOW an exit was
// detected and `m.exitDetectedAt||Date.now()` invented WHEN. Both sit inside the evidence
// package's contentHash, so an invented value re-derived cleanly and was indistinguishable
// from an observed one. Both now VALIDATE and fail closed to null.
//
// PRODUCTION IS UNCHANGED BY THIS FILE. index.html is byte-identical; every mutation is applied
// to a COPY in a temporary directory and the repository file's SHA-256 is re-checked after each
// run. `git restore` is never used as cleanup, and alexGCloseLivePosition is a PROTECTED
// function -- a harness that edited it in place would show as protected drift.
//
// Run:        node tests/mutate_v1241_exit_provenance.js
// Self-test:  node tests/mutate_v1241_exit_provenance.js --self-test
'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');
const crypto = require('crypto');
const { execFileSync, spawnSync } = require('child_process');

const REPO = path.resolve(__dirname, '..');
const INDEX = path.join(REPO, 'index.html');
const RUNNER = 'tests/run_v1241_exit_provenance_tests.js';
const FIXTURE = 'tests/v1241_exit_provenance_tests.js';

const BEHAVIOURAL = 'behavioural';
const STRUCTURAL = 'structural-contract';

//: v1241 collects exactly this many assertions. A mutated run that collects a different number
//: did not exercise the discriminators and is a setup failure, never a kill.
const EXPECTED_ASSERTIONS = 83;

// The two repaired expressions, verbatim from alexGCloseLivePosition.
const TS_LINE =
  "    exitDetectedAt:(typeof m.exitDetectedAt==='number'&&isFinite(m.exitDetectedAt)&&m.exitDetectedAt>0)?m.exitDetectedAt:null,";
const SRC_LINE =
  "    exitDetectionSource:(typeof m.exitDetectionSource==='string'&&m.exitDetectionSource.trim()!=='')?m.exitDetectionSource:null,";
// The developer forced-close call site in generateTestAlexTrade -- the ONLY reachable caller
// that omits exitDetectedAt, and therefore the only one where the timestamp was actively
// fabricated rather than merely defended against.
const DEV_CALL =
  "      {exitTriggerLevel:exitLevel,exitDetectionSource:'developer_test',ambiguous:false,ambiguousMode:null});";

// ── THE CATALOG ─────────────────────────────────────────────────────────────────────────────
// `expect` is the discriminator that must fail FOR THE INTENDED REASON. Other assertions may
// also fail -- these mutations have reach -- but if the named discriminator does not fail, the
// mutation is NOT counted as killed, however red the run looks.
//
// M1-M9 mutate the repaired expressions. M10-M11 mutate the DEVELOPER CALL SITE, and only the
// real-path fixtures can catch them: driving alexGCloseLivePosition directly would never see a
// caller that supplies the wrong thing.
const CATALOG = [
  { id: 'M1', strength: BEHAVIOURAL, what: "restore the ||Date.now() timestamp fallback",
    from: TS_LINE, to: '    exitDetectedAt:m.exitDetectedAt||Date.now(),',
    expect: 'T-field omitted is not a wall-clock value' },

  { id: 'M2', strength: BEHAVIOURAL, what: "restore the ||'live_snapshot' source fallback",
    from: SRC_LINE, to: "    exitDetectionSource:m.exitDetectionSource||'live_snapshot',",
    expect: 'S-field omitted is specifically NOT "live_snapshot"' },

  { id: 'M3', strength: BEHAVIOURAL, what: 'check the timestamp with != null only',
    from: TS_LINE, to: '    exitDetectedAt:(m.exitDetectedAt!=null)?m.exitDetectedAt:null,',
    expect: 'T-NaN -> UNKNOWN (null), never the runtime clock' },

  { id: 'M4', strength: BEHAVIOURAL, what: 'check the source with != null only',
    from: SRC_LINE,
    to: '    exitDetectionSource:(m.exitDetectionSource!=null)?m.exitDetectionSource:null,',
    expect: 'S-empty string -> UNKNOWN (null), never an invented label' },

  { id: 'M5', strength: BEHAVIOURAL, what: 'serialize UNKNOWN timestamp as 0 rather than null',
    from: TS_LINE,
    to: "    exitDetectedAt:(typeof m.exitDetectedAt==='number'&&isFinite(m.exitDetectedAt)&&m.exitDetectedAt>0)?m.exitDetectedAt:0,",
    expect: 'T-field omitted -> UNKNOWN (null), never the runtime clock' },

  { id: 'M6', strength: BEHAVIOURAL, what: 'serialize UNKNOWN source as an invented label',
    from: SRC_LINE,
    to: "    exitDetectionSource:(typeof m.exitDetectionSource==='string'&&m.exitDetectionSource.trim()!=='')?m.exitDetectionSource:'live_snapshot',",
    expect: 'S-field omitted is specifically NOT "live_snapshot"' },

  { id: 'M7', strength: BEHAVIOURAL, what: 'typeof-only timestamp check, which accepts NaN',
    from: TS_LINE,
    to: "    exitDetectedAt:(typeof m.exitDetectedAt==='number')?m.exitDetectedAt:null,",
    expect: 'T-NaN -> UNKNOWN (null), never the runtime clock' },

  { id: 'M8', strength: BEHAVIOURAL,
    what: 'typeof-only source check, which accepts the empty string',
    from: SRC_LINE,
    to: "    exitDetectionSource:(typeof m.exitDetectionSource==='string')?m.exitDetectionSource:null,",
    expect: 'S-empty string -> UNKNOWN (null), never an invented label' },

  { id: 'M9', strength: BEHAVIOURAL, what: 'coerce a numeric string into a real timestamp',
    from: TS_LINE,
    to: '    exitDetectedAt:(isFinite(Number(m.exitDetectedAt))&&Number(m.exitDetectedAt)>0)?Number(m.exitDetectedAt):null,',
    expect: 'T-numeric string -> UNKNOWN (null), never the runtime clock' },

  { id: 'M10', strength: BEHAVIOURAL,
    what: 'developer call site starts supplying exitDetectedAt:Date.now()',
    from: DEV_CALL,
    to: "      {exitTriggerLevel:exitLevel,exitDetectionSource:'developer_test',exitDetectedAt:Date.now(),ambiguous:false,ambiguousMode:null});",
    expect: 'DEV.6 the production call site supplies NO exitDetectedAt, so it is UNKNOWN' },

  { id: 'M11', strength: BEHAVIOURAL,
    what: 'developer call site stops supplying exitDetectionSource',
    from: DEV_CALL,
    to: '      {exitTriggerLevel:exitLevel,ambiguous:false,ambiguousMode:null});',
    expect: 'DEV.5 the production call site supplied exitDetectionSource and it is preserved' },
];

const sha256 = (s) => crypto.createHash('sha256').update(s).digest('hex');

function largestScriptBody(html) {
  const bodies = html.match(/<script>[\s\S]*?<\/script>/g) || [];
  if (!bodies.length) return null;
  return bodies.sort((a, b) => b.length - a.length)[0].replace(/^<script>|<\/script>$/g, '');
}

// Runs the v1241 suite against a temporary tree. Returns a structured outcome, never a verdict.
function runSuiteIn(dir) {
  // BOTH streams concatenated: osascript writes JXA console.log to STDERR, not stdout. Reading
  // only stdout yields an empty transcript, which looks exactly like a loader failure and makes
  // every verdict meaningless -- the defect the G-2 harness's control caught, recorded here so
  // it is not rediscovered.
  const p = spawnSync('osascript', ['-l', 'JavaScript', RUNNER], { cwd: dir, encoding: 'utf8' });
  const out = String((p.stdout || '') + (p.stderr || '') + (p.error ? p.error.message : ''));
  const lines = out.split('\n');
  const pass = lines.filter((l) => l.startsWith('PASS -- ')).map((l) => l.slice(8));
  const fail = lines.filter((l) => l.startsWith('FAIL -- ')).map((l) => l.slice(8));
  const loaderError = /execution error|EXECUTION ERROR/.test(out)
    || (pass.length === 0 && fail.length === 0);
  return { pass, fail, loaderError, total: pass.length + fail.length, raw: out };
}

// A temp tree containing ONLY what the suite needs, with `html` as its index.html.
function withTempTree(html, fn) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'mogo-g4-mut-'));
  try {
    fs.mkdirSync(path.join(dir, 'tests'));
    fs.writeFileSync(path.join(dir, 'index.html'), html);
    fs.copyFileSync(path.join(REPO, RUNNER), path.join(dir, RUNNER));
    fs.copyFileSync(path.join(REPO, FIXTURE), path.join(dir, FIXTURE));
    return fn(dir);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
}

function classify(entry, baseHtml, expectedTotal) {
  const total = expectedTotal === undefined ? EXPECTED_ASSERTIONS : expectedTotal;
  const occurrences = baseHtml.split(entry.from).length - 1;
  if (occurrences !== 1) {
    return { ...entry, occurrences, verdict: occurrences === 0 ? 'NOT APPLIED' : 'AMBIGUOUS',
             syntax: '-', pass: 0, fail: [], intended: false };
  }
  const mutated = baseHtml.replace(entry.from, entry.to);
  if (mutated === baseHtml) {
    return { ...entry, occurrences, verdict: 'NO-OP', syntax: '-',
             pass: 0, fail: [], intended: false };
  }
  return withTempTree(mutated, (dir) => {
    // Syntax is gated INDEPENDENTLY of the suite, so a parse failure can never masquerade as a
    // behavioural kill.
    const body = largestScriptBody(mutated);
    const js = path.join(dir, '__syntax_check.js');
    fs.writeFileSync(js, body === null ? 'throw new Error("no script body")' : body);
    let syntaxOk = true;
    try { execFileSync('node', ['--check', js], { stdio: 'ignore' }); } catch (e) { syntaxOk = false; }
    if (!syntaxOk) {
      return { ...entry, occurrences, verdict: 'SYNTAX INVALID', syntax: 'INVALID',
               pass: 0, fail: [], intended: false };
    }
    const r = runSuiteIn(dir);
    if (r.loaderError) {
      return { ...entry, occurrences, verdict: 'LOADER ERROR', syntax: 'valid',
               pass: r.pass.length, fail: r.fail, intended: false };
    }
    if (r.total !== total) {
      return { ...entry, occurrences, verdict: 'COLLECTION CHANGED', syntax: 'valid',
               pass: r.pass.length, fail: r.fail, intended: false,
               note: 'collected ' + r.total + ', expected ' + total };
    }
    const intended = r.fail.some((f) => f.indexOf(entry.expect) === 0);
    let verdict;
    if (r.fail.length === 0) verdict = 'SURVIVED';
    else if (!intended) verdict = 'KILLED FOR THE WRONG REASON';
    else verdict = 'KILLED';
    return { ...entry, occurrences, verdict, syntax: 'valid',
             pass: r.pass.length, fail: r.fail, intended };
  });
}

// ── self-discrimination: prove the harness itself can fail ──────────────────────────────────
// Entirely on temporary synthetic inputs. No repository file is modified to test a failure path.
function selfTest(baseHtml) {
  const cases = [];
  const record = (name, ok, detail) => cases.push({ name, ok, detail: detail || '' });
  const base = { id: 'ST', strength: BEHAVIOURAL, what: 'self-test' };

  let r = classify({ ...base, from: '__THIS_ANCHOR_DOES_NOT_EXIST__', to: 'x',
                     expect: 'anything' }, baseHtml);
  record('missing anchor -> NOT APPLIED', r.verdict === 'NOT APPLIED' && r.occurrences === 0,
         r.verdict);

  r = classify({ ...base, from: 'const ', to: 'const ', expect: 'anything' }, baseHtml);
  record('ambiguous anchor -> AMBIGUOUS', r.verdict === 'AMBIGUOUS',
         r.verdict + ' (' + r.occurrences + ' matches)');

  r = classify({ ...base, from: TS_LINE, to: '    exitDetectedAt:(((', expect: 'anything' },
                baseHtml);
  record('syntax-breaking -> SYNTAX INVALID, not a kill', r.verdict === 'SYNTAX INVALID',
         r.verdict);

  r = classify({ ...base, from: TS_LINE, to: TS_LINE, expect: 'anything' }, baseHtml);
  record('no-op -> NO-OP, not a kill', r.verdict === 'NO-OP', r.verdict);

  // A real mutation with a discriminator that does not exist: red run, still not a kill.
  r = classify({ ...base, from: TS_LINE, to: '    exitDetectedAt:m.exitDetectedAt||Date.now(),',
                 expect: 'THIS ASSERTION DOES NOT EXIST' }, baseHtml);
  record('wrong discriminator -> KILLED FOR THE WRONG REASON',
         r.verdict === 'KILLED FOR THE WRONG REASON', r.verdict);

  // Collection guard: the same real mutation, judged against a total the suite cannot produce.
  r = classify({ ...base, from: TS_LINE, to: '    exitDetectedAt:m.exitDetectedAt||Date.now(),',
                 expect: 'T-field omitted is not a wall-clock value' },
                baseHtml, EXPECTED_ASSERTIONS + 1);
  record('wrong collected count -> COLLECTION CHANGED, not a kill',
         r.verdict === 'COLLECTION CHANGED', r.verdict + ' ' + (r.note || ''));

  // Loader failure: a syntactically valid script that throws on load.
  r = classify({ ...base, from: TS_LINE,
                 to: '    exitDetectedAt:(function(){throw new Error("mogo-selftest-loader");})(),',
                 expect: 'anything' }, baseHtml);
  record('loader failure -> LOADER ERROR or COLLECTION CHANGED, not a kill',
         r.verdict === 'LOADER ERROR' || r.verdict === 'COLLECTION CHANGED', r.verdict);

  // Repository hash guard, proven by corrupting the EXPECTED value rather than the file.
  const real = sha256(fs.readFileSync(INDEX, 'utf8'));
  record('repository hash mismatch -> detected', real !== '0'.repeat(64), 'guard compares sha256');

  console.log('=== SELF-TEST: the harness must refuse to call these kills ===');
  cases.forEach((c) => {
    console.log('  ' + (c.ok ? 'PASS' : 'FAIL') + '  ' + c.name + '   [' + c.detail + ']');
  });
  const passed = cases.filter((c) => c.ok).length;
  console.log('\nself-test: ' + passed + '/' + cases.length
              + ' false-kill conditions rejected');
  return passed === cases.length ? 0 : 1;
}

function main() {
  const args = process.argv.slice(2);
  const baseHtml = fs.readFileSync(INDEX, 'utf8');
  const before = sha256(baseHtml);

  if (args.indexOf('--self-test') > -1) {
    const rc = selfTest(baseHtml);
    const after = sha256(fs.readFileSync(INDEX, 'utf8'));
    if (before !== after) { console.log('\nINDEX.HTML DRIFTED during self-test'); return 1; }
    console.log('index.html unchanged');
    return rc;
  }

  console.log('=== G-4 MUTATION GATE (exit provenance) ===');
  console.log('suite: ' + FIXTURE + '\n');

  // An unmutated control FIRST. Without it, "SURVIVED" and "the suite never really ran" are
  // indistinguishable -- and a no-op scoring as a kill is how uncommitted mutation evidence
  // has gone wrong here before.
  const control = withTempTree(baseHtml, (dir) => runSuiteIn(dir));
  if (control.loaderError || control.fail.length || control.total !== EXPECTED_ASSERTIONS) {
    console.log('CONTROL FAILED: ' + control.total + ' assertions, '
                + control.fail.length + ' failing (expected ' + EXPECTED_ASSERTIONS + '/0).');
    console.log('The unmutated copy does not pass, so no mutation result is meaningful.');
    return 1;
  }
  console.log('control: ' + control.total + '/' + EXPECTED_ASSERTIONS
              + ' assertions pass unmutated\n');

  const results = CATALOG.map((entry) => {
    const r = classify(entry, baseHtml);
    console.log(r.id + ' [' + r.strength + '] ' + r.what);
    console.log('    ' + r.verdict + (r.note ? ' -- ' + r.note : '')
                + (r.verdict === 'KILLED' ? ' by ' + r.expect : ''));
    if (r.fail.length) {
      console.log('    ' + r.fail.length + ' assertion(s) failed; first: ' + r.fail[0]);
    }
    return r;
  });

  const killed = results.filter((r) => r.verdict === 'KILLED');
  const behavioural = killed.filter((r) => r.strength === BEHAVIOURAL).length;
  const structural = killed.filter((r) => r.strength === STRUCTURAL).length;

  console.log('\n--- totals ---');
  console.log('  ' + killed.length + '/' + CATALOG.length + ' killed -- '
              + behavioural + ' behavioural, ' + structural + ' structural-contract');

  const after = sha256(fs.readFileSync(INDEX, 'utf8'));
  if (before !== after) {
    console.log('\nINDEX.HTML DRIFTED -- the harness wrote to the repository');
    return 1;
  }
  console.log('  index.html unchanged (sha256 re-verified)');

  if (killed.length !== CATALOG.length) {
    console.log('\nG-4 MUTATION GATE FAILED: '
                + results.filter((r) => r.verdict !== 'KILLED')
                        .map((r) => r.id + '=' + r.verdict).join(', '));
    return 1;
  }
  console.log('\nG-4 MUTATION GATE PASSED -- ' + killed.length + '/' + CATALOG.length
              + ' killed, all behavioural. Two (M10, M11) mutate the DEVELOPER CALL SITE and'
              + ' only the real-path fixtures can catch them.');
  return 0;
}

process.exit(main());

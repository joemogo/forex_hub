#!/usr/bin/env node
// G-2 MUTATION GATE — makes the scan-eligibility mutation evidence reproducible.
//
// WHY THIS EXISTS. The G-2 repair (7339bec) was reported as "8/8 mutations killed", but those
// mutations were run from an ad-hoc shell function and never committed. The repair was real and
// tested; its mutation evidence was not reproducible from a fresh checkout, which makes the
// claim unverifiable by anyone but the person who ran it. This file is that evidence, committed.
//
// KILL STRENGTH IS NOT UNIFORM, AND THIS GATE REFUSES TO PRETEND OTHERWISE.
// runAutoTopDownScan() is async and the JXA fixture harness cannot resolve a genuine await --
// the same permanent limitation recorded for runDiagnostics() (v12.1.1) and
// simulateTrueMTFReplay() (v12.1.2). Three mutations therefore live at a call site no
// behavioural fixture can reach, and are killed by v1240's G2.10 SOURCE-ORDER assertions
// instead. That is a genuine kill -- a named assertion fails for the intended reason -- but it
// is weaker evidence than an end-to-end behavioural kill, so every row is labelled and the
// totals are reported separately. This is NOT full end-to-end mutation coverage.
//
// NON-DESTRUCTIVE BY CONSTRUCTION. index.html is never edited in place and never restored from
// a backup: each mutation is written to a COPY inside a fresh temporary directory, the suite is
// redirected there by cwd, and the directory is removed in a finally. The repository file's
// SHA-256 is recorded before the run and re-checked after every mutation -- a mismatch aborts.
//
// USAGE (from the repository root):
//     node tests/mutate_v1240_scan_freshness.js
//     node tests/mutate_v1240_scan_freshness.js --self-test
//
// Exit: 0 only when all 10 mutations are VALIDLY killed. Non-zero on anything else, including
// a mutation that is unapplied, ambiguous, syntax-invalid, killed by a loader error, killed for
// an unintended reason, or that survives.
'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');
const crypto = require('crypto');
const { execFileSync, spawnSync } = require('child_process');

const REPO = path.resolve(__dirname, '..');
const INDEX = path.join(REPO, 'index.html');
const RUNNER = 'tests/run_v1240_scan_freshness_tests.js';
const FIXTURE = 'tests/v1240_scan_freshness_tests.js';

const BEHAVIOURAL = 'behavioural';
const STRUCTURAL = 'structural-contract';

// ── THE CATALOG ─────────────────────────────────────────────────────────────────────────────
// `expect` is the discriminator that must fail FOR THE INTENDED REASON. Other assertions may
// also fail -- a mutation with reach usually breaks several -- but if the named discriminator
// does not fail, the mutation is NOT counted as killed, however red the run looks.
const CATALOG = [
  { id: 'H1', set: 'historical', strength: STRUCTURAL,
    what: 'remove the sweep-start generation bump',
    from: 'const __eligGen=jvmBeginEligibilityGeneration();',
    to:   'const __eligGen=__jvmEligibilityGeneration;',
    expect: 'G2.10 the sweep begins a generation' },

  { id: 'H2', set: 'historical', strength: STRUCTURAL,
    what: 'mark eligibility FRESH before the complete refresh finishes',
    from: 'SCAN_PAIRS.forEach(function(p){ jvmMarkEligibilityInProgress(p,__eligGen); });',
    to:   'SCAN_PAIRS.forEach(function(p){ jvmMarkEligibilityFresh(p,__eligGen); });',
    expect: 'G2.10 the sweep marks pairs IN_PROGRESS' },

  { id: 'H3', set: 'historical', strength: BEHAVIOURAL,
    what: 'ignore generation mismatch in jvmEligibilityIsCurrent',
    from: '  if(e.gen!==__jvmEligibilityGeneration) return false;             // produced by a prior generation\n',
    to:   '',
    expect: 'G2.5 the SAME scanData is refused in the next generation' },

  { id: 'H4', set: 'historical', strength: BEHAVIOURAL,
    what: 'ignore FAILED status',
    from: '  if(e.status!==JVM_ELIGIBILITY_STATUS.FRESH) return false;        // IN_PROGRESS or FAILED\n',
    to:   '',
    expect: 'G2.1 failed refresh yields NO snapshot' },

  { id: 'H5', set: 'historical', strength: BEHAVIOURAL,
    what: 'make FAILED sticky so a later successful refresh cannot recover the pair',
    from: 'function jvmMarkEligibilityFresh(pair,gen){ __jvmEligibility[pair]={gen:gen,status:JVM_ELIGIBILITY_STATUS.FRESH}; }',
    to:   'function jvmMarkEligibilityFresh(pair,gen){ if(__jvmEligibility[pair]&&__jvmEligibility[pair].status===JVM_ELIGIBILITY_STATUS.FAILED) return; __jvmEligibility[pair]={gen:gen,status:JVM_ELIGIBILITY_STATUS.FRESH}; }',
    expect: 'G2.3 marking FRESH clears a FAILED pair' },

  { id: 'H6', set: 'historical', strength: BEHAVIOURAL,
    what: 'remove the jvmEligibilityIsCurrent predicate from htfSnapshotOf',
    from: '  if(!jvmEligibilityIsCurrent(sk)) return null;\n',
    to:   '',
    expect: 'G2.1 failed refresh yields NO snapshot' },

  { id: 'H7', set: 'historical', strength: STRUCTURAL,
    what: "one pair's catch invalidates every pair",
    from: 'try{ jvmMarkEligibilityFailed(pair,__eligGen); }catch(e4){}',
    to:   'try{ jvmInvalidateAllEligibility(); }catch(e4){}',
    expect: 'G2.10 the per-pair catch does NOT invalidate every pair' },

  { id: 'H8', set: 'historical', strength: BEHAVIOURAL,
    what: 'jvmEligibilityIsCurrent returns true unconditionally',
    from: 'function jvmEligibilityIsCurrent(pair){',
    to:   'function jvmEligibilityIsCurrent(pair){ return true;',
    expect: 'G2.1 failed refresh yields NO snapshot' },

  // ADDITIONAL -- not part of the historical 8, and labelled so the original claim is not
  // silently expanded. A2 matters most: the original eight never covered Auto Scan OFF, which
  // is the exact scenario that exposed G-2.
  { id: 'A1', set: 'additional', strength: BEHAVIOURAL,
    what: 'reuse the same generation across sweeps (generation never advances)',
    from: 'function jvmBeginEligibilityGeneration(){ __jvmEligibilityGeneration++; return __jvmEligibilityGeneration; }',
    to:   'function jvmBeginEligibilityGeneration(){ return __jvmEligibilityGeneration; }',
    expect: 'G2.1 generations advanced' },

  { id: 'A2', set: 'additional', strength: BEHAVIOURAL,
    what: 'Auto Scan OFF no longer invalidates eligibility',
    from: '    jvmInvalidateAllEligibility();\n  }\n  updateAutoScanStatus();',
    to:   '  }\n  updateAutoScanStatus();',
    expect: 'G2.8 switching Auto Scan OFF invalidates eligibility immediately' },
];

// ── mechanics ───────────────────────────────────────────────────────────────────────────────
const sha256 = (s) => crypto.createHash('sha256').update(s).digest('hex');

function largestScriptBody(html) {
  const bodies = html.match(/<script>[\s\S]*?<\/script>/g) || [];
  if (!bodies.length) return null;
  return bodies.sort((a, b) => b.length - a.length)[0].replace(/^<script>|<\/script>$/g, '');
}

// Runs the v1240 suite against a temporary tree. Returns a structured outcome, never a verdict.
function runSuiteIn(dir) {
  // spawnSync, and BOTH streams concatenated: osascript writes the JXA console.log results to
  // STDERR, not stdout. Reading only stdout yields an empty transcript, which would look
  // exactly like a loader failure and make every verdict below meaningless. Found by the
  // control refusing to pass in the temporary tree -- which is what the control is for.
  const p = spawnSync('osascript', ['-l', 'JavaScript', RUNNER],
                      { cwd: dir, encoding: 'utf8' });
  const out = String((p.stdout || '') + (p.stderr || '') + (p.error ? p.error.message : ''));
  const lines = out.split('\n');
  const pass = lines.filter((l) => l.startsWith('PASS -- ')).map((l) => l.slice(8));
  const fail = lines.filter((l) => l.startsWith('FAIL -- ')).map((l) => l.slice(8));
  const loaderError = /execution error|EXECUTION ERROR/.test(out) || (pass.length === 0 && fail.length === 0);
  return { pass, fail, loaderError, raw: out };
}

// Builds a temp tree containing ONLY what the suite needs, with `html` as its index.html.
function withTempTree(html, fn) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'mogo-g2-mut-'));
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

function classify(entry, baseHtml) {
  const occurrences = baseHtml.split(entry.from).length - 1;
  if (occurrences !== 1) {
    return { ...entry, occurrences, verdict: occurrences === 0 ? 'NOT APPLIED' : 'AMBIGUOUS',
             syntax: '-', pass: 0, fail: [], intended: false };
  }
  const mutated = baseHtml.replace(entry.from, entry.to);
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
// Entirely on temporary synthetic inputs. No repository file is read for mutation or written.
function selfTest(baseHtml) {
  const cases = [];
  const record = (name, ok, detail) => cases.push({ name, ok, detail: detail || '' });

  let r = classify({ id: 'ST1', set: 'self', strength: BEHAVIOURAL, what: 'missing anchor',
                     from: '__THIS_ANCHOR_DOES_NOT_EXIST__', to: 'x', expect: 'anything' }, baseHtml);
  record('missing anchor -> NOT APPLIED', r.verdict === 'NOT APPLIED' && r.occurrences === 0, r.verdict);

  const dup = 'let __selftest_dup=1;';
  r = classify({ id: 'ST2', set: 'self', strength: BEHAVIOURAL, what: 'ambiguous anchor',
                 from: 'const ', to: 'const ', expect: 'anything' }, baseHtml);
  record('ambiguous anchor -> AMBIGUOUS', r.verdict === 'AMBIGUOUS' && r.occurrences > 1,
         r.verdict + ' (' + r.occurrences + ' matches)');

  r = classify({ id: 'ST3', set: 'self', strength: BEHAVIOURAL, what: 'syntax-breaking mutation',
                 from: 'function jvmEligibilityIsCurrent(pair){',
                 to: 'function jvmEligibilityIsCurrent(pair){ ((( ',
                 expect: 'G2.1 failed refresh yields NO snapshot' }, baseHtml);
  record('syntax-breaking -> SYNTAX INVALID, not KILLED',
         r.verdict === 'SYNTAX INVALID' && r.verdict !== 'KILLED', r.verdict);

  r = classify({ id: 'ST4', set: 'self', strength: BEHAVIOURAL, what: 'no-op mutation',
                 from: 'function jvmEligibilityStatusOf(pair){',
                 to: 'function jvmEligibilityStatusOf(pair){',
                 expect: 'G2.1 failed refresh yields NO snapshot' }, baseHtml);
  record('no-op mutation -> SURVIVED', r.verdict === 'SURVIVED', r.verdict);

  // Loader failure: a tree whose index.html carries no script body at all.
  const loader = withTempTree('<html><body>no script here</body></html>', (dir) => runSuiteIn(dir));
  record('missing script body -> loader error, not a kill', loader.loaderError === true,
         'pass=' + loader.pass.length + ' fail=' + loader.fail.length);

  r = classify({ id: 'ST6', set: 'self', strength: BEHAVIOURAL, what: 'wrong expected failure name',
                 from: 'function jvmEligibilityIsCurrent(pair){',
                 to: 'function jvmEligibilityIsCurrent(pair){ return true;',
                 expect: 'G2.99 an assertion that does not exist' }, baseHtml);
  record('wrong discriminator -> KILLED FOR THE WRONG REASON, not a valid kill',
         r.verdict === 'KILLED FOR THE WRONG REASON', r.verdict);

  // Repository hash guard: a changed source must abort. Proven on a synthetic pair of hashes
  // rather than by touching the repository.
  record('repository hash mismatch is detected',
         sha256(baseHtml) !== sha256(baseHtml + '\n'), 'differing content hashes differ');

  cases.forEach((c) => console.log('  ' + (c.ok ? 'PASS' : 'FAIL') + ' -- ' + c.name +
                                   (c.detail ? '  [' + c.detail + ']' : '')));
  const bad = cases.filter((c) => !c.ok).length;
  console.log('---');
  console.log(bad === 0
    ? 'HARNESS SELF-DISCRIMINATION PASSED -- ' + cases.length + ' invalid conditions all rejected'
    : 'HARNESS SELF-DISCRIMINATION FAILED -- ' + bad + '/' + cases.length);
  return bad === 0 ? 0 : 1;
}

// ── main ────────────────────────────────────────────────────────────────────────────────────
function main() {
  if (!fs.existsSync(INDEX)) {
    console.error('FAIL: index.html not found -- run this from the repository root.');
    return 2;
  }
  const baseHtml = fs.readFileSync(INDEX, 'utf8');
  const baseHash = sha256(baseHtml);

  if (process.argv.indexOf('--self-test') !== -1) {
    const rc = selfTest(baseHtml);
    if (sha256(fs.readFileSync(INDEX, 'utf8')) !== baseHash) {
      console.error('ABORT: index.html changed during the self-test.');
      return 1;
    }
    return rc;
  }

  console.log('G-2 MUTATION GATE -- tests/v1240_scan_freshness_tests.js');
  console.log('index.html sha256 (before): ' + baseHash);

  // CONTROL. An unmutated copy in the temp tree must reproduce 42/42. Without this, a
  // "SURVIVED" could equally mean the suite silently loaded the real index.html, or that the
  // redirection never worked at all.
  const control = withTempTree(baseHtml, (dir) => runSuiteIn(dir));
  if (control.loaderError || control.fail.length !== 0 || control.pass.length === 0) {
    console.error('ABORT: the unmutated control did not pass in the temporary tree ' +
                  '(pass=' + control.pass.length + ' fail=' + control.fail.length +
                  ' loaderError=' + control.loaderError + '). The suite is not being ' +
                  'redirected to the temporary copy, so no verdict below would be trustworthy.');
    return 1;
  }
  console.log('control (unmutated copy, temp tree): ' + control.pass.length +
              ' pass / 0 fail -- redirection proven\n');

  const results = [];
  for (const entry of CATALOG) {
    results.push(classify(entry, baseHtml));
    const now = sha256(fs.readFileSync(INDEX, 'utf8'));
    if (now !== baseHash) {
      console.error('ABORT: repository index.html changed during ' + entry.id + '.');
      return 1;
    }
  }

  const pad = (s, n) => String(s).padEnd(n);
  console.log(pad('ID', 4) + pad('SET', 12) + pad('STRENGTH', 20) + pad('SYNTAX', 9) +
              pad('SUITE', 16) + pad('VERDICT', 30) + 'DISCRIMINATOR');
  for (const r of results) {
    console.log(pad(r.id, 4) + pad(r.set, 12) + pad(r.strength, 20) + pad(r.syntax, 9) +
                pad(r.pass + ' pass / ' + r.fail.length + ' fail', 16) +
                pad(r.verdict, 30) + (r.intended ? r.expect : '(not observed)'));
  }

  console.log('\nfull failure sets:');
  for (const r of results) {
    if (r.fail.length) console.log('  ' + r.id + ': ' + r.fail.map((f) => f.split('  [')[0]).join(' | '));
  }

  const killed = results.filter((r) => r.verdict === 'KILLED');
  const hist = killed.filter((r) => r.set === 'historical').length;
  const addl = killed.filter((r) => r.set === 'additional').length;
  const beh = killed.filter((r) => r.strength === BEHAVIOURAL).length;
  const str = killed.filter((r) => r.strength === STRUCTURAL).length;
  const histTotal = CATALOG.filter((c) => c.set === 'historical').length;
  const addlTotal = CATALOG.filter((c) => c.set === 'additional').length;

  console.log('\n--- totals ---');
  console.log('  historical original : ' + hist + '/' + histTotal + ' killed');
  console.log('  additional          : ' + addl + '/' + addlTotal + ' killed');
  console.log('  combined            : ' + killed.length + '/' + CATALOG.length + ' killed');
  console.log('  behavioural kills   : ' + beh);
  console.log('  structural-contract : ' + str +
              '  (call sites inside the async runAutoTopDownScan, unreachable by the JXA' +
              ' behavioural harness -- weaker evidence, and not end-to-end coverage)');

  const finalHash = sha256(fs.readFileSync(INDEX, 'utf8'));
  console.log('\nindex.html sha256 (after) : ' + finalHash);
  if (finalHash !== baseHash) { console.error('ABORT: repository index.html changed.'); return 1; }
  console.log('repository index.html byte-identical: yes');

  if (killed.length !== CATALOG.length) {
    console.error('\nFAIL: ' + (CATALOG.length - killed.length) + ' mutation(s) not validly killed.');
    return 1;
  }
  console.log('\nG-2 MUTATION GATE PASSED -- ' + hist + '/' + histTotal + ' historical, ' +
              addl + '/' + addlTotal + ' additional, ' + killed.length + '/' + CATALOG.length +
              ' combined (' + beh + ' behavioural, ' + str + ' structural-contract)');
  return 0;
}

process.exit(main());

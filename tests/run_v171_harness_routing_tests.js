#!/usr/bin/env node
'use strict';
// RUN_ALL_EXEC: node tests/run_v171_harness_routing_tests.js
//
// ══════════════════════════════════════════════════════════════════════════════════════════════
// v171 — HARNESS ROUTING, AND THE GUARDS THAT MAKE A DEAD SUITE VISIBLE
// ══════════════════════════════════════════════════════════════════════════════════════════════
//
// THE DEFECT THIS EXISTS TO PREVENT RECURRING. 25 suites (v137..v165) are Node programs. The
// canonical runner only sends a suite to Node when the file declares `// RUN_ALL_EXEC:`;
// otherwise it uses `osascript -l JavaScript`, where `require` is undefined. All 25 therefore
// died before executing a single assertion -- 601 real fixtures that never ran. The runner
// itself behaved correctly: zero fixtures is an execution error, never a pass. But nothing
// asserted that a Node suite must carry the declaration, so the condition persisted across
// releases and sat on origin/mogo-main unnoticed.
//
// This suite asserts the routing invariant and the fail-closed guards that make a broken suite
// impossible to mistake for a passing one. It reads files; it starts no process, touches no
// network, and evaluates no strategy code.
//
// WHAT IT DELIBERATELY DOES NOT DO: it does not execute the 25 suites. Their assertions are
// their own business and are run by the canonical gate. Re-running them here would double every
// fixture and make the totals stop meaning one-run-per-suite -- the exact property HR-6 exists
// to protect.

const fs = require('fs');
const path = require('path');
const ROOT = path.resolve(__dirname, '..');

const AFFECTED = [
  'v137_c1_refresh_preflight', 'v138_forward_trade_analysis', 'v139_poll_continuity_ordering',
  'v140_focus_window_fetch', 'v142_exit_fidelity_reentrancy', 'v143_c1_staleness_policy',
  'v144_baseline_trend', 'v145_setup_record_join', 'v146_connect_screen', 'v147_observatory',
  'v148_multiyear_replay', 'v149_cost_model', 'v151_declined_setups', 'v154_psych_level',
  'v155_alexg_live_pairs', 'v156_scanner_honesty', 'v157_scanner_meaning', 'v158_ai_context',
  'v159_jvm_declined', 'v160_jvm_eligibility_starvation', 'v161_dashboard_opportunities',
  'v162_crt', 'v163_alex_allpairs', 'v164_storage_diagnostic', 'v165_byte_budget',
].map(function (s) { return 'run_' + s + '_tests.js'; });

const results = [];
function t(name, desc, fn) {
  let pass = false, detail = '';
  try { const r = fn(); pass = !!r.pass; detail = r.detail || ''; }
  catch (e) { pass = false; detail = 'threw: ' + (e && e.message); }
  results.push({ name: name, desc: desc, pass: pass, detail: detail });
}

const runnerSrc = fs.readFileSync(path.join(ROOT, 'tests', 'run_all.sh'), 'utf8');
const allRunners = fs.readdirSync(path.join(ROOT, 'tests'))
  .filter(function (f) { return /^run_.*_tests\.js$/.test(f); }).sort();

function read(f) { return fs.readFileSync(path.join(ROOT, 'tests', f), 'utf8'); }
// The runner's OWN extraction, replicated exactly from run_all.sh:
//   grep -m1 '^// RUN_ALL_EXEC: ' "$runner" | sed 's|^// RUN_ALL_EXEC: ||'
function execLineOf(src) {
  const m = /^\/\/ RUN_ALL_EXEC: (.*)$/m.exec(src);
  return m ? m[1].trim() : '';
}
function isNodeProgram(src) { return /^#!\/usr\/bin\/env node/.test(src); }

// ── 1. every affected suite selects Node ──────────────────────────────────────────────────────
t('HR-1', 'all 25 affected suites exist and declare RUN_ALL_EXEC. Without the declaration the '
  + 'runner sends a Node program to osascript, where require is undefined and the suite dies '
  + 'before asserting anything', function () {
  const missing = AFFECTED.filter(function (f) {
    return !fs.existsSync(path.join(ROOT, 'tests', f)) || !execLineOf(read(f));
  });
  return { pass: AFFECTED.length === 25 && missing.length === 0,
    detail: AFFECTED.length + ' suites checked, ' + missing.length + ' missing a declaration' };
});

t('HR-2', 'every affected declaration selects NODE and none selects osascript. A declaration '
  + 'that named osascript would re-create the original defect while looking repaired', function () {
  const bad = AFFECTED.filter(function (f) {
    const e = execLineOf(read(f));
    return !/^node\s/.test(e) || /osascript/i.test(e);
  });
  return { pass: bad.length === 0, detail: bad.length ? 'not routed to node: ' + bad.join(', ')
    : 'all 25 begin with "node " and none mentions osascript' };
});

t('HR-3', 'THE GENERAL INVARIANT, not just these 25: no Node-shebang suite anywhere under tests/ '
  + 'may lack a RUN_ALL_EXEC declaration. This is what stops the defect returning with the next '
  + 'suite somebody adds', function () {
  const offenders = allRunners.filter(function (f) {
    const s = read(f); return isNodeProgram(s) && !execLineOf(s);
  });
  return { pass: allRunners.length > 0 && offenders.length === 0,
    detail: allRunners.length + ' runners scanned, ' + offenders.length + ' undeclared'
      + (offenders.length ? ': ' + offenders.join(', ') : '') };
});

// ── 2. exactly once ───────────────────────────────────────────────────────────────────────────
t('HR-4', 'each affected suite declares RUN_ALL_EXEC exactly ONCE. Two declarations would be '
  + 'ambiguous, and the runner takes the first (-m1) -- a second could silently disagree', function () {
  const bad = AFFECTED.filter(function (f) {
    return (read(f).match(/^\/\/ RUN_ALL_EXEC: /gm) || []).length !== 1;
  });
  return { pass: bad.length === 0, detail: bad.length ? bad.join(', ') : 'exactly one each' };
});

t('HR-5', 'the runner EVALUATES the declaration, so the extracted command must be non-empty for '
  + 'each suite under the runner\'s own -m1/sed extraction. ASSERT THE FILTER IS NON-EMPTY, or '
  + 'this passes vacuously', function () {
  const lines = AFFECTED.map(function (f) { return execLineOf(read(f)); });
  return { pass: lines.length === 25 && lines.every(function (l) { return l.length > 0; }),
    detail: lines.length + ' commands extracted, shortest ' + Math.min.apply(null, lines.map(function (l) { return l.length; })) + ' chars' };
});

t('HR-6', 'each declaration targets THE SUITE ITSELF, exactly one file that exists. A declaration '
  + 'pointing at a second program would run a different file, or run something twice', function () {
  const bad = [];
  AFFECTED.forEach(function (f) {
    const e = execLineOf(read(f));
    const parts = e.split(/\s+/);
    const target = parts[1];
    if (parts.length !== 2 || parts[0] !== 'node') { bad.push(f + ' (shape: ' + e + ')'); return; }
    if (target !== 'tests/' + f) { bad.push(f + ' -> ' + target); return; }
    if (!fs.existsSync(path.join(ROOT, target))) bad.push(f + ' target missing');
  });
  return { pass: bad.length === 0, detail: bad.length ? bad.join('; ') : 'all 25 are `node tests/<self>`' };
});

// ── 3. fixture totals are captured ────────────────────────────────────────────────────────────
function tsvRows() {
  const raw = fs.readFileSync(path.join(ROOT, 'tests', 'expected_fixture_counts.tsv'), 'utf8');
  const rows = {};
  raw.split('\n').forEach(function (l) {
    if (!l.trim() || l.startsWith('#')) return;
    const i = l.indexOf('\t'); rows[l.slice(0, i)] = l.slice(i + 1).trim();
  });
  return rows;
}

t('HR-7', 'every affected suite has a registered fixture count that is a POSITIVE integer. An '
  + 'unregistered suite fails the gate; a count of zero would register the dead state as correct', function () {
  const rows = tsvRows();
  const bad = AFFECTED.filter(function (f) {
    const v = rows[f]; return !v || !/^\d+$/.test(v) || Number(v) <= 0;
  });
  return { pass: bad.length === 0 && Object.keys(rows).length > 0,
    detail: Object.keys(rows).length + ' rows registered, ' + bad.length + ' affected suites bad' };
});

t('HR-8', 'EVERY runner in the glob is registered, not merely the 25. An unregistered suite is a '
  + 'gate failure by design, and this keeps that true for the whole directory', function () {
  const rows = tsvRows();
  const unregistered = allRunners.filter(function (f) { return !(f in rows); });
  return { pass: allRunners.length > 0 && unregistered.length === 0,
    detail: allRunners.length + ' runners, ' + unregistered.length + ' unregistered'
      + (unregistered.length ? ': ' + unregistered.join(', ') : '') };
});

t('HR-9', 'v142 stays registered at its REAL fixture total including its failing fixtures. '
  + 'Lowering this count would hide genuine failures behind a smaller expectation', function () {
  const rows = tsvRows();
  return { pass: rows['run_v142_exit_fidelity_reentrancy_tests.js'] === '32',
    detail: 'v142 registered at ' + rows['run_v142_exit_fidelity_reentrancy_tests.js'] + ' (expected 32)' };
});

// ── 4. the fail-closed guards in run_all.sh ───────────────────────────────────────────────────
// These assert the runner still CANNOT report a broken suite as passing. Each is mutation-tested:
// deleting the guard from run_all.sh makes the corresponding fixture fail.
function guard(re) { return re.test(runnerSrc); }

// Scope a guard to ITS OWN `if ... ; then ... fi` block before asking whether it sets
// OVERALL_EXIT. An earlier version of these fixtures searched a fixed character window after the
// condition, which matched an OVERALL_EXIT=1 belonging to a NEIGHBOURING block -- so deleting the
// wiring from the guard under test left the fixture green. Mutation M5 and M6 both survived.
// Slicing to the block's own closing `fi` is what makes the assertion mean what it says.
function blockOf(startRe) {
  const m = startRe.exec(runnerSrc);
  if (!m) return null;
  const from = m.index;
  // Stop at the branch's OWN end: `fi`, or the next `elif`/`else` of the same chain. Slicing
  // only to `fi` swallowed sibling branches, so deleting the wiring from an `if` branch still
  // found the `elif` branch's OVERALL_EXIT=1 -- mutation M10 survived exactly there.
  const ends = ['\n  fi\n', '\n  elif ', '\n  else\n']
    .map(function (tok) { return runnerSrc.indexOf(tok, from); })
    .filter(function (i) { return i !== -1; });
  if (!ends.length) return null;
  return runnerSrc.slice(from, Math.min.apply(null, ends));
}
function blockSetsExit(startRe) {
  const b = blockOf(startRe);
  return b !== null && /OVERALL_EXIT=1/.test(b);
}

t('HR-10', 'ZERO-FIXTURE RUNS FAIL CLOSED. A suite that emits no PASS/FAIL line has not passed, '
  + 'it has failed to run -- and it must set OVERALL_EXIT regardless of interpreter exit code', function () {
  const re = /if \[ \$\(\(NP \+ NF\)\) -eq 0 \]; then/;
  const has = guard(re), wired = blockSetsExit(re);
  return { pass: has && wired, detail: 'guard=' + has + ' block_sets_OVERALL_EXIT=' + wired };
});

t('HR-11', 'RUNNER ERRORS REMAIN ERRORS. A suite that reports an internal error after emitting '
  + 'some fixtures is still untrustworthy and must fail the run', function () {
  const re = /if \[ "\$RE" -gt 0 \]; then/;
  const has = guard(/grep -c '\^RUNNER ERROR'/) && guard(re), wired = blockSetsExit(re);
  return { pass: has && wired, detail: 'guard=' + has + ' block_sets_OVERALL_EXIT=' + wired };
});

t('HR-12', 'A NONZERO INTERPRETER EXIT cannot be masked, even when fixtures were emitted. This is '
  + 'the guard that keeps v142\'s exit 1 visible', function () {
  const re = /if \[ "\$EC" -ne 0 \]; then/;
  const has = guard(re), wired = blockSetsExit(re);
  return { pass: has && wired, detail: 'guard=' + has + ' block_sets_OVERALL_EXIT=' + wired };
});

t('HR-13', 'REAL ASSERTION FAILURES REMAIN FAILURES: a nonzero FAIL count sets OVERALL_EXIT', function () {
  const re = /if \[ "\$NF" -gt 0 \]; then/;
  const has = guard(re), wired = blockSetsExit(re);
  return { pass: has && wired, detail: 'guard=' + has + ' block_sets_OVERALL_EXIT=' + wired };
});

t('HR-14', 'AN UNREGISTERED SUITE fails the run, so a new suite cannot join the gate silently', function () {
  const re = /if \[ -z "\$EXPECTED" \]; then/;
  const has = guard(/NO EXPECTED FIXTURE COUNT registered/) && guard(re);
  const b = blockOf(re);
  const wired = b !== null && /NO EXPECTED FIXTURE COUNT registered/.test(b) && /OVERALL_EXIT=1/.test(b);
  return { pass: has && wired, detail: 'guard=' + has + ' block_sets_OVERALL_EXIT=' + wired };
});

t('HR-15', 'A SUITE THAT RUNS SHORT OR LONG fails: the count-mismatch guard is what notices '
  + 'fixtures vanishing into a swallowed exception', function () {
  const re = /elif \[ "\$ACTUAL" -ne "\$EXPECTED" \]; then/;
  const has = guard(/FIXTURE COUNT MISMATCH/) && guard(re);
  const b = blockOf(re);
  const wired = b !== null && /FIXTURE COUNT MISMATCH/.test(b) && /OVERALL_EXIT=1/.test(b);
  return { pass: has && wired, detail: 'guard=' + has + ' block_sets_OVERALL_EXIT=' + wired };
});

t('HR-16', 'THE VERDICT IS DERIVED FROM OVERALL_EXIT, so the summary block cannot render green '
  + 'above a red exit code', function () {
  return { pass: /if \[ "\$OVERALL_EXIT" -eq 0 \]; then[\s\S]{0,200}?VERDICT:\s*PASS/.test(runnerSrc)
      && /exit \$OVERALL_EXIT/.test(runnerSrc),
    detail: 'verdict derived from OVERALL_EXIT and the script exits with it' };
});

// ── 5. positive controls: the detectors above can actually fire ───────────────────────────────
t('HR-17', 'POSITIVE CONTROL for HR-3: the undeclared-Node-suite detector FIRES on a synthetic '
  + 'Node program with no declaration. Without this, HR-3 could pass because it never matches', function () {
  const synthetic = "#!/usr/bin/env node\n'use strict';\nconst x = require('fs');\n";
  return { pass: isNodeProgram(synthetic) && !execLineOf(synthetic),
    detail: 'synthetic undeclared node suite correctly identified as an offender' };
});

t('HR-18', 'POSITIVE CONTROL for HR-2: an osascript declaration is REJECTED. This is the mutation '
  + 'that would silently restore the original defect', function () {
  const bad = '#!/usr/bin/env node\n// RUN_ALL_EXEC: osascript -l JavaScript tests/x.js\n';
  const e = execLineOf(bad);
  return { pass: e.length > 0 && (!/^node\s/.test(e) || /osascript/i.test(e)),
    detail: 'osascript routing correctly rejected by the HR-2 predicate' };
});

t('HR-19', 'POSITIVE CONTROL for HR-6: a declaration pointing at a DIFFERENT file is rejected, '
  + 'which is the duplicate-execution shape', function () {
  const e = execLineOf('#!/usr/bin/env node\n// RUN_ALL_EXEC: node tests/some_other_program.js\n');
  const parts = e.split(/\s+/);
  return { pass: parts.length === 2 && parts[1] !== 'tests/run_v171_harness_routing_tests.js',
    detail: 'mismatched target correctly distinguishable from `node tests/<self>`' };
});

t('HR-20', 'NON-VACUITY: the inputs this suite reads are real and non-empty -- run_all.sh, the '
  + 'runner glob and the manifest. Every assertion above is worthless if these are empty', function () {
  const rows = Object.keys(tsvRows()).length;
  return { pass: runnerSrc.length > 5000 && allRunners.length >= 25 && rows >= 25,
    detail: 'run_all.sh ' + runnerSrc.length + ' bytes, ' + allRunners.length + ' runners, ' + rows + ' manifest rows' };
});

// ══ REPORT ════════════════════════════════════════════════════════════════════════════════════
let passed = 0, failed = 0;
results.forEach(function (r) {
  if (r.pass) { passed++; console.log('PASS -- ' + r.name + ' ' + r.desc); }
  else { failed++; console.log('FAIL -- ' + r.name + ' ' + r.desc); }
  if (r.detail) console.log('          ' + r.detail);
});
console.log('\n  ' + passed + ' / ' + (passed + failed) + ' passed');
process.exit(failed ? 1 : 0);

// Runner for the MOGO-011 Step 4A evidence-verifier fixture suite.
//
// WHY THIS RUNNER IS A SHIM RATHER THAN A FIXTURE HOST
//
// Every other permanent suite here executes its fixtures inside osascript. This one cannot. The
// behaviour under test IS filesystem and cryptographic behaviour: reading real evidence files,
// recomputing SHA-256 with the canonicalizer extracted from index.html, and proving that not one
// byte or mtime moved. JXA has neither `fs` nor `crypto`, and asserting those properties against
// stubs would prove nothing whatsoever about them.
//
// So the fixtures live in tests/v131_evidence_verifier_tests.js and run under Node. This shim finds
// Node, runs them, and relays their PASS/FAIL lines verbatim so tests/run_all.sh counts them
// exactly like every other suite.
//
// IF NODE CANNOT BE FOUND THIS SUITE FAILS LOUDLY. It never reports success it did not observe --
// a suite that silently passes when it could not run is worse than no suite at all.
//
//   cd "Forex Hub" && osascript -l JavaScript tests/run_v131_evidence_verifier_tests.js
//   tests/run_all.sh   (discovers and runs this automatically)
//
// SANDBOX: THIS SHIM CANNOT RUN UNDER THE BASH SANDBOX, AND THE DIRECTIVE BELOW IS WHY.
//
// The shim reaches Node through AppleScript's `doShellScript`, which needs the Mach bootstrap
// port. Inside the sandbox that registration is denied --
//     CFMessagePort: bootstrap_register(): failed 'Permission denied'
//     doShellScript FAILED: Message not understood.
// -- and `doShellScript` is used for BOTH steps here: locating Node AND executing the suite. So
// repairing only the lookup would fix nothing; the whole shim is unusable under the sandbox.
//
// The FIXTURES themselves are unaffected: `node tests/v131_evidence_verifier_tests.js` runs all
// 73 assertions cleanly inside the sandbox. Only this launcher was broken.
//
// The line below tells tests/run_all.sh to execute the Node suite DIRECTLY, moving the
// process-launch out of AppleScript and into the shell harness that already has a working one.
// The assertions are untouched, the count stays 73, and this shim remains the fallback for a
// non-sandboxed environment where `doShellScript` still works.
//
// RUN_ALL_EXEC: node tests/v131_evidence_verifier_tests.js

ObjC.import('Foundation');

function sh(cmd) {
  const app = Application.currentApplication();
  app.includeStandardAdditions = true;
  // `; exit 0` keeps doShellScript from throwing on a nonzero status, so a failing fixture run is
  // reported through its own PASS/FAIL lines rather than as a runner error.
  try { return app.doShellScript(cmd + ' 2>&1; exit 0'); }
  catch (e) { return 'SHELL_ERROR: ' + (e && e.message ? e.message : String(e)); }
}

// Node is commonly installed outside the minimal PATH that doShellScript inherits -- under nvm, for
// instance. Look in the usual places rather than assuming, and prefer whatever `command -v` finds.
function findNode() {
  const probe = sh(
    'command -v node || ' +
    'ls -1 /opt/homebrew/bin/node /usr/local/bin/node /usr/bin/node 2>/dev/null | head -1 || ' +
    "ls -1d \"$HOME\"/.nvm/versions/node/*/bin/node 2>/dev/null | sort -V | tail -1"
  );
  const line = String(probe).split('\n').map(s => s.trim()).filter(Boolean)[0] || '';
  return /\/node$/.test(line) ? line : null;
}

function q(s) { return "'" + String(s).replace(/'/g, "'\\''") + "'"; }

(function main() {
  const cwd = ObjC.unwrap($.NSFileManager.defaultManager.currentDirectoryPath);
  const suite = cwd + '/tests/v131_evidence_verifier_tests.js';

  if (!$.NSFileManager.defaultManager.fileExistsAtPath(suite)) {
    console.log('FAIL -- Step 4A verifier suite not found at ' + suite +
                ' (run this from the project root)');
    console.log('---');
    console.log('FAILURES: 1/1 executed');
    return;
  }

  const node = findNode();
  if (!node) {
    console.log('FAIL -- Node.js could not be located, so the Step 4A evidence-verifier fixtures ' +
                'could NOT be executed. This suite tests real filesystem and SHA-256 behaviour and ' +
                'cannot run under osascript. Install Node or put it on PATH.');
    console.log('---');
    console.log('FAILURES: 1/1 executed');
    return;
  }

  const out = sh('cd ' + q(cwd) + ' && ' + q(node) + ' ' + q(suite));
  // doShellScript returns AppleScript-style CR-separated text, not LF. Splitting on '\n' alone
  // collapses the whole run into one line and every result is lost.
  const lines = String(out).split(/\r\n|\r|\n/);

  var sawResult = false;
  for (var i = 0; i < lines.length; i++) {
    const l = lines[i];
    if (/^(PASS|FAIL) -- /.test(l)) sawResult = true;
    if (l.length) console.log(l);
  }

  if (!sawResult) {
    console.log('FAIL -- the Step 4A fixture process produced no PASS/FAIL results. Raw output above.');
    console.log('---');
    console.log('FAILURES: 1/1 executed');
  }
})();

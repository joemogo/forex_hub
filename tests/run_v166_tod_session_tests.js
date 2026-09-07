// Runner shim for the tod_session_v1 fixture suite (v12.65.0).
//
// A SHIM RATHER THAN A FIXTURE HOST, for the same reason as v131: these fixtures exercise the arm's
// pure logic under Node rather than driving the DOM, and the run_all harness -- which already has a
// working shell -- launches Node directly via the declaration below instead of routing the process
// launch through AppleScript.
//
// RUN_ALL_EXEC: node tests/v166_tod_session_tests.js

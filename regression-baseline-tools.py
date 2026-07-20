#!/usr/bin/env python3
"""
MOGO regression baseline tools -- lives in the project directory (not the
scratchpad) so it survives between sessions, unlike the earlier ad-hoc
phase1_baseline/pre_script.js files this project relied on before, which were
found missing on two separate occasions (v6.0, v8.0) because the scratchpad is
not durable storage.

Usage:
  python3 regression-baseline-tools.py --update
      Re-extracts the protected function source, known-good hash, strategy
      constants, and fixture counts from the CURRENT index.html and
      index-v2.9-KNOWN-GOOD.html, and overwrites regression-baseline.json.
      Only run this deliberately, after a release's protected-function diff
      has already been reviewed and accepted -- it redefines "known good".

  python3 regression-baseline-tools.py
      (no flag) Re-extracts from the CURRENT index.html and compares against
      the committed regression-baseline.json, printing exactly which
      protected functions changed and whether any strategy constant changed.
      Exit code 0 = identical, 1 = drift detected. This is the command a
      future release's verification step should run.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
INDEX_HTML = PROJECT_DIR / "index.html"
KNOWN_GOOD_HTML = PROJECT_DIR / "index-v2.9-KNOWN-GOOD.html"
BASELINE_JSON = PROJECT_DIR / "regression-baseline.json"

# Every function whose behavior is FROZEN trading methodology -- current/JVM
# strategy plus the entire ALEX G S&R engine. This list is itself part of the
# baseline: if a future release needs to add a name here, that addition should
# be a deliberate, disclosed part of that release's own report.
PROTECTED_FUNCTIONS = [
    # JVM / current strategy ("Idiot Strategy")
    "openPaperPosition", "closePaperPosition", "checkPaperPositions", "checkAutoTrades",
    "evaluateLiveTrigger", "scoreConfluence", "bestConfluence", "computeAOI",
    "computeAOIWithTouches", "findSwingPoints", "detectSignals", "getBias", "getSession",
    "pipSize", "pipValuePerLot",
    # ALEX G S&R (alex_g_sr_v1)
    "alexGAcceptReaction", "alexGAssignCluster", "alexGBreakCycleId", "alexGCheckSwingAt",
    "alexGClassifyTouch", "alexGCloseLivePosition", "alexGClusterId", "alexGComputeATRAtEntry",
    "alexGComputeMAEMFE", "alexGComputePsychLevels", "alexGComputeReplayStats",
    "alexGComputeSessionMetadata", "alexGComputeTrendContext", "alexGConstructLivePosition",
    "alexGConstructTrade", "alexGCorrectedQuality", "alexGCreateSetupRecord",
    "alexGDetermineFromSide", "alexGDetermineTradeDirection", "alexGEnrichPenetrationEvents",
    "alexGEnsureZoneState", "alexGEvaluateBreakRetest", "alexGEvaluateRepeatedReaction",
    "alexGFindSwingPoints", "alexGInferPriorZoneRole", "alexGIsSameInteraction",
    "alexGIsSetupEligibleForLiveTrading", "alexGIsSetupSignalStale", "alexGLivePollingShouldRun",
    "alexGLiveSignalId", "alexGPenetrationId", "alexGProcessTimeframeCandle",
    "alexGProcessTimeframeCandleWithSetups", "alexGReactionId", "alexGReconstructExitFromCandles",
    "alexGRecordLiveSetupStatus", "alexGResolvePenetrationForTouch", "alexGRunSetupEngine",
    "alexGRunSetupReplay", "alexGRunZoneEngine", "alexGSetupId", "alexGSetupSortComparator",
    "alexGTradeId", "alexGUpdatePositionExcursionAndCheckExit", "alexGValidateTradeNoLookahead",
    "alexGWalkOutcome", "alexGZoneId", "alexGZoneRole",
]

# Strategy constants captured verbatim (source text, not re-evaluated) so a
# silent edit to any of them is visible in the diff even if no protected
# function's own text changed.
PROTECTED_CONSTANTS = ["WEIGHTS", "ALERT_THRESHOLD", "RULES", "RULES_ALEXG"]

# Fixture counts by suite, as of this baseline. A future release should update
# this list (via --update) whenever it adds a new suite or new fixtures to an
# existing one -- the total is the number every release's regression run
# should reproduce exactly (or exceed, with the excess explained).
FIXTURE_COUNTS = {
    "run_tests.js (Phase 1 unit tests)": 24,
    "run_phase2_tests.js": 15,
    "run_phase3_tests.js": 26,
    "run_correction_tests.js (v3.6.1)": 17,
    "run_phase4_tests.js": 32,
    "run_role_correction_tests.js (v4.0.1)": 18,
    "run_live_paper_tests.js (v4.2)": 32,
    "run_v421_tests.js": 24,
    "run_v422_tests.js": 4,
    "run_v43_tests.js": 19,
    "run_v50_tests.js": 16,
    "run_v60_tests.js": 20,
    "run_v61_tests.js": 31,
    "run_v80_tests.js (Academy/Strategy Center isolation)": 15,
    "run_v90_tests.js (JVM journal classification / reset audit)": 20,
    "run_v100_tests.js (Trade Inspector foundation)": 22,
    "run_v110_tests.js (Paper Ledger Integrity / stale-save guard)": 17,
    "run_v111_tests.js (paper-ledger transaction commit/rollback)": 15,
    "run_v112_tests.js (chart saved-view self-heal)": 17,
    "run_v113_tests.js (timeframe-aware chart display history)": 18,
    "run_v114_tests.js (Pre-Trade Checklist badge text + future-state prep)": 19,
    "run_v115_tests.js (MOGO Academy lesson engine foundation)": 55,
    "run_v120_tests.js (Strategy Framework foundation, Release 1 -- ALEX registration)": 28,
    "run_v1211_tests.js": 13,
    "run_v1212_tests.js (Manual Review Eligible + TRUE MTF Replay Diagnostics)": 53,
    "run_v1213_tests.js (Security Baseline)": 50,
    "run_v121_tests.js (Strategy Framework, Release 2 -- JVM registration)": 30,
    "run_v122_tests.js (Multi-Strategy Foundation, ADR-006)": 30,
    "run_v123_tests.js (TJR_SLR Phase 1 -- Session and Zone Engine)": 48,
    "run_v1231_tests.js (Strategy Workspace Framework + dedicated TJR workspace)": 31,
}


def extract_script_body(html_text):
    m = re.search(r"<script>(.*)</script>", html_text, re.S)
    if not m:
        raise RuntimeError("Could not find <script>...</script> body in index.html")
    return m.group(1)


def extract_function_source(script_src, name):
    """Brace-depth extraction, tolerant of an optional 'async ' prefix."""
    m = re.search(r"(?:async\s+)?function\s+" + re.escape(name) + r"\s*\([^)]*\)\s*\{", script_src)
    if not m:
        return None
    start = m.end() - 1
    depth = 0
    i = start
    while i < len(script_src):
        if script_src[i] == "{":
            depth += 1
        elif script_src[i] == "}":
            depth -= 1
            if depth == 0:
                return script_src[m.start():i + 1]
        i += 1
    return None


def extract_const_source(script_src, name):
    """Extracts a top-level `const NAME = ...;` declaration's exact text,
    tracking brace/bracket depth so multi-line object/array literals are
    captured whole."""
    m = re.search(r"const\s+" + re.escape(name) + r"\s*=\s*", script_src)
    if not m:
        return None
    i = m.end()
    depth = 0
    started = False
    start = i
    while i < len(script_src):
        c = script_src[i]
        if c in "{[(":
            depth += 1
            started = True
        elif c in "}])":
            depth -= 1
        elif c == ";" and depth == 0 and started:
            return script_src[m.start():i + 1]
        elif c == ";" and depth == 0 and not started:
            # a simple scalar const, e.g. const ALERT_THRESHOLD=55;
            return script_src[m.start():i + 1]
        i += 1
    return None


def sha1_text(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def build_baseline():
    html_text = INDEX_HTML.read_text()
    script_src = extract_script_body(html_text)

    functions = {}
    missing_functions = []
    for name in PROTECTED_FUNCTIONS:
        src = extract_function_source(script_src, name)
        if src is None:
            missing_functions.append(name)
        else:
            functions[name] = {"sha1": sha1_text(src), "length": len(src)}

    constants = {}
    missing_constants = []
    for name in PROTECTED_CONSTANTS:
        src = extract_const_source(script_src, name)
        if src is None:
            missing_constants.append(name)
        else:
            constants[name] = {"sha1": sha1_text(src), "source": src}

    known_good_hash = None
    if KNOWN_GOOD_HTML.exists():
        known_good_hash = hashlib.sha1(KNOWN_GOOD_HTML.read_bytes()).hexdigest()

    app_version_match = re.search(r"const APP_VERSION='([^']+)'", script_src)

    return {
        "generatedFromAppVersion": app_version_match.group(1) if app_version_match else None,
        "knownGoodHtmlSha1": known_good_hash,
        "protectedFunctionCount": len(PROTECTED_FUNCTIONS),
        "protectedFunctions": functions,
        "missingFunctions": missing_functions,
        "protectedConstants": constants,
        "missingConstants": missing_constants,
        "fixtureCounts": FIXTURE_COUNTS,
        "totalFixtureCount": sum(FIXTURE_COUNTS.values()),
    }


def cmd_update():
    baseline = build_baseline()
    BASELINE_JSON.write_text(json.dumps(baseline, indent=2, sort_keys=False) + "\n")
    print(f"Wrote {BASELINE_JSON} (app version {baseline['generatedFromAppVersion']}, "
          f"{baseline['protectedFunctionCount']} protected functions, "
          f"{baseline['totalFixtureCount']} known fixtures)")
    if baseline["missingFunctions"]:
        print("WARNING -- functions not found in index.html:", baseline["missingFunctions"])
    if baseline["missingConstants"]:
        print("WARNING -- constants not found in index.html:", baseline["missingConstants"])


def cmd_compare():
    if not BASELINE_JSON.exists():
        print(f"No baseline found at {BASELINE_JSON} -- run with --update first.")
        return 1
    committed = json.loads(BASELINE_JSON.read_text())
    current = build_baseline()

    drift = []
    for name, meta in committed.get("protectedFunctions", {}).items():
        cur = current["protectedFunctions"].get(name)
        if cur is None:
            drift.append(f"REMOVED: {name}")
        elif cur["sha1"] != meta["sha1"]:
            drift.append(f"CHANGED: {name}")
    for name in current["protectedFunctions"]:
        if name not in committed.get("protectedFunctions", {}):
            drift.append(f"NEW (not in committed baseline): {name}")

    for name, meta in committed.get("protectedConstants", {}).items():
        cur = current["protectedConstants"].get(name)
        if cur is None:
            drift.append(f"REMOVED CONSTANT: {name}")
        elif cur["sha1"] != meta["sha1"]:
            drift.append(f"CHANGED CONSTANT: {name}")

    hash_match = current["knownGoodHtmlSha1"] == committed.get("knownGoodHtmlSha1")

    print(f"Known-good hash match: {hash_match}")
    print(f"Committed baseline app version: {committed.get('generatedFromAppVersion')}")
    print(f"Current index.html app version: {current.get('generatedFromAppVersion')}")
    if drift:
        print(f"DRIFT DETECTED in {len(drift)} protected item(s):")
        for d in drift:
            print("  -", d)
        return 1
    print(f"No drift: all {len(committed.get('protectedFunctions', {}))} protected functions "
          f"and {len(committed.get('protectedConstants', {}))} protected constants are byte-identical "
          f"to the committed baseline.")
    return 0 if hash_match else 1


if __name__ == "__main__":
    if "--update" in sys.argv:
        cmd_update()
        sys.exit(0)
    sys.exit(cmd_compare())

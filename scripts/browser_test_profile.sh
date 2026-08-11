#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════════════════════
# MOGO — disposable Chrome test-profile launcher (INC-004 mandatory isolation control)
# ══════════════════════════════════════════════════════════════════════════════════════════
#
# WHY THIS EXISTS
#
# On 2026-07-31, browser verification for MOGO-003 Phase 1 issued a browser storage-clearing call
# three times against http://localhost:8744 inside the operator's ACTIVE Chrome Profile 2. That
# origin was the live MOGO origin. Real ALEX and JVM paper-trading data was destroyed and had to be
# restored from a Time Machine backup. See docs/INCIDENTS.md INC-004 for the full account.
#
# The root cause was not code. It was an unverified assumption: the operator's origin was inferred
# from .claude/launch.json (port 8743), port 8744 was chosen as "isolated", and that assumption was
# never checked. It was wrong.
#
# THE RULE THIS ENFORCES
#
#   Browser testing NEVER touches the operator's Chrome profile. Ever. Under any circumstance.
#
# Every browser test launches a DISPOSABLE Chrome user-data directory created fresh under the
# scratchpad. It starts empty, it holds no operator data, and destroying it costs nothing.
#
# FAIL CLOSED
#
# If isolation cannot be POSITIVELY verified, this script exits non-zero and launches nothing.
# It never falls back to the default profile, and never guesses. An unlaunched test is a nuisance;
# an overwritten ledger is an incident.
#
# USAGE
#   scripts/browser_test_profile.sh --origin http://localhost:<PORT-CONFIRMED-WITH-THE-OPERATOR> \
#       [--profile-root <dir>] [--launch]
#
# The port is deliberately NOT shown as a literal here. Any example port would be copy-pasted, and a
# copy-pasted origin is an inferred origin -- the exact failure mode of INC-004. Ask the operator,
# every time. 8744 and 8899 are refused outright by GUARD 1b below.
#
# The caller is responsible for serving the app. This script only creates and verifies the
# disposable profile and prints the launch command for review.
#
# ── THIS SCRIPT IS FOR TESTING ONLY. IT IS NOT FOR EVIDENCE-BEARING RUNS. (M-7 / D-15) ────────
#
# Everything below is deliberately DISPOSABLE: a fresh profile under a temporary directory, thrown
# away after use. That is correct for testing and catastrophic for evidence. 222 evidence packages
# accumulated inside one of these profiles and macOS purged the directory; the corpus survived only
# because it had been hand-copied days earlier. See D-15.
#
# For forward paper trading, campaigns, or anything else that CAPTURES EVIDENCE, use:
#
#     scripts/mogo_evidence_profile.sh --origin http://localhost:<PORT> --launch
#
# which refuses temporary directories, pins one origin, checkpoints before every launch, and keeps
# its profile under $HOME where it survives reboots and temp purges.

set -euo pipefail

ORIGIN=""
PROFILE_ROOT="${TMPDIR:-/tmp}/mogo-browser-test-profiles"
LAUNCH=0

while [ $# -gt 0 ]; do
  case "$1" in
    --origin)       ORIGIN="${2:-}"; shift 2 ;;
    --profile-root) PROFILE_ROOT="${2:-}"; shift 2 ;;
    --launch)       LAUNCH=1; shift ;;
    *) echo "FAIL: unknown argument '$1'" >&2; exit 2 ;;
  esac
done

fail() { echo "FAIL (isolation not verified — nothing launched): $*" >&2; exit 1; }

# ── GUARD 1: an explicit origin is mandatory. Never inferred, never defaulted. ────────────────
# Inferring the origin from a config file is exactly what caused INC-004.
[ -n "$ORIGIN" ] || fail "--origin is required and must never be inferred from a config file (INC-004)."
case "$ORIGIN" in
  http://localhost:*|http://127.0.0.1:*) ;;
  *) fail "origin '$ORIGIN' is not a local test origin." ;;
esac

# ── GUARD 1b: refuse origins known to hold real or contaminated operator data. ────────────────
#
# This is a DENYLIST and only a denylist. It can refuse an origin; it can never approve one.
#
# READ THIS BEFORE USING IT FOR ANYTHING ELSE: the absence of a port from this list proves
# NOTHING. It does not mean the port is free, empty, disposable or safe. INC-004 happened because
# 8744 was assumed isolated on exactly that reasoning -- "not the one in the config, therefore a
# different origin, therefore safe." The origin must still be confirmed with the operator every
# time. This guard exists solely to make the two known-bad answers impossible to give by accident.
#
#   8744  the operator's LIVE MOGO origin. Proven by INC-004: paper-trading data was destroyed
#         at this origin and reappeared at it after a Time Machine restore.
#   8899  a CONTAMINATED test origin. Holds the INC-005 hand-seeded record AGT|MANUAL-B|1, whose
#         ALEX account reads balance 10200. Quarantined from every statistic but never corrected,
#         so any evidence captured here would be measured against a known-false stored balance.
#
# A port is added here when it is proven to hold operator or contaminated data -- never on
# suspicion, and never removed merely because a port looks unused today.
NON_DISPOSABLE_PORTS="8744 8899"
for _port in $NON_DISPOSABLE_PORTS; do
  case "$ORIGIN" in
    *:"$_port"|*:"$_port"/*)
      fail "origin '$ORIGIN' is a known non-disposable origin (port $_port). Serve the test build on a port confirmed with the operator." ;;
  esac
done

# ── GUARD 2: the profile root must never resolve inside the operator's Chrome data. ───────────
OPERATOR_CHROME="$HOME/Library/Application Support/Google/Chrome"
case "$PROFILE_ROOT" in
  "$OPERATOR_CHROME"*) fail "profile root resolves inside the operator's Chrome directory." ;;
  "$HOME/Library/Application Support/Google"*) fail "profile root resolves inside Google application support." ;;
esac
case "$PROFILE_ROOT" in
  /tmp/*|/private/tmp/*|/var/folders/*) ;;
  *) fail "profile root must live under a temporary directory, got '$PROFILE_ROOT'." ;;
esac

# ── GUARD 3: create a FRESH, EMPTY, uniquely-named profile. Never reuse one. ──────────────────
STAMP="$(date -u +%Y%m%dT%H%M%SZ)-$$"
PROFILE_DIR="$PROFILE_ROOT/profile-$STAMP"
[ -e "$PROFILE_DIR" ] && fail "profile directory already exists — refusing to reuse: $PROFILE_DIR"
mkdir -p "$PROFILE_DIR"

# ── GUARD 4: prove the new profile is empty and is not the operator's. ───────────────────────
ENTRIES="$(find "$PROFILE_DIR" -mindepth 1 | wc -l | tr -d ' ')"
[ "$ENTRIES" = "0" ] || fail "new profile is not empty ($ENTRIES entries) — refusing to launch."
[ "$PROFILE_DIR" != "$OPERATOR_CHROME" ] || fail "profile path equals the operator's Chrome directory."
find "$PROFILE_DIR" -name "*.leveldb" -o -name "Local Storage" 2>/dev/null | grep -q . \
  && fail "new profile already contains browser storage — refusing to launch."

# ── GUARD 5: record the four facts the Authority requires BEFORE any destructive test. ────────
# A pre-clear inventory of a freshly created profile is, by construction, empty -- and recording
# that fact is the point. INC-004's most damaging step was a clear with NO inventory at all.
MANIFEST="$PROFILE_DIR/mogo-isolation-manifest.txt"
{
  echo "MOGO browser-test isolation manifest"
  echo "created_utc:            $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "test_profile_path:      $PROFILE_DIR"
  echo "test_origin:            $ORIGIN"
  echo "operator_chrome_path:   $OPERATOR_CHROME"
  echo "is_operator_profile:    NO (verified: profile root is outside the operator's Chrome directory)"
  echo "pre_clear_inventory:    EMPTY (freshly created disposable profile, 0 entries verified)"
  echo "disposable:             YES (delete this directory to reset completely)"
} > "$MANIFEST"

CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
CMD="\"$CHROME\" --user-data-dir=\"$PROFILE_DIR\" --no-first-run --no-default-browser-check \"$ORIGIN\""

echo "ISOLATION VERIFIED"
cat "$MANIFEST"
echo ""
echo "DISPOSABLE PROFILE — FOR TESTING ONLY."
echo "  This directory lives under a temporary path and WILL be purged. Do not capture evidence"
echo "  here (D-15). For forward paper trading or any evidence-bearing run, use:"
echo "    scripts/mogo_evidence_profile.sh --origin <ORIGIN> --launch"
echo ""
echo "launch command:"
echo "  $CMD"

if [ "$LAUNCH" = "1" ]; then
  [ -x "$CHROME" ] || fail "Chrome not found at $CHROME"
  exec "$CHROME" --user-data-dir="$PROFILE_DIR" --no-first-run --no-default-browser-check "$ORIGIN"
fi

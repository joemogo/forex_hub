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
#   scripts/browser_test_profile.sh --origin http://localhost:8744 [--profile-root <dir>]
#
# The caller is responsible for serving the app. This script only creates and verifies the
# disposable profile and prints the launch command for review.

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
echo "launch command:"
echo "  $CMD"

if [ "$LAUNCH" = "1" ]; then
  [ -x "$CHROME" ] || fail "Chrome not found at $CHROME"
  exec "$CHROME" --user-data-dir="$PROFILE_DIR" --no-first-run --no-default-browser-check "$ORIGIN"
fi

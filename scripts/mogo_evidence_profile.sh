#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════════════════════
# MOGO — DURABLE evidence profile launcher (MOGO-011 M-7, closes D-15)
# ══════════════════════════════════════════════════════════════════════════════════════════
#
# WHY THIS EXISTS, AND WHY IT IS A SECOND SCRIPT RATHER THAN A FLAG
#
# MOGO has exactly two kinds of browser run, and conflating them destroyed data once already:
#
#   BROWSER TESTING        disposable, throwaway, must never hold anything real.
#                          scripts/browser_test_profile.sh. Unchanged by M-7. INC-004's rule --
#                          "browser testing NEVER touches the operator's Chrome profile" -- stands
#                          exactly as written.
#
#   EVIDENCE-BEARING RUNS  forward paper trading and real campaigns. Produce records that exist
#                          ONCE. THIS script.
#
# Adding an --evidence flag to the test launcher would have put both behind one command where a
# missing flag silently downgrades a real run into a disposable one. Two scripts cannot be
# confused by omission.
#
# WHAT WENT WRONG (D-15)
#
# 222 evidence packages accumulated inside a DISPOSABLE test profile at
# $TMPDIR/mogo-browser-test-profiles/profile-20260805T230552Z-48568 -- a directory whose stated
# purpose is to be thrown away, in a location macOS purges. On 2026-08-10 that directory was
# confirmed GONE. The corpus survived only because it had been hand-copied to a preservation
# checkpoint days earlier. 220 of those packages have since been independently hash-verified.
#
# The disposable profile was never the wrong tool. It was the right tool used for the wrong job.
#
# THE ASYMMETRY THAT JUSTIFIES ALL OF THIS
#
# Replay evidence is regenerable -- re-run the campaign. FORWARD PAPER-TRADING EVIDENCE IS NOT.
# It is a record of something that happened once, at a time that will not come again. Losing it
# is not an inconvenience; it is the permanent loss of a scientific observation.
#
# WHAT THIS SCRIPT GUARANTEES
#
#   1. The profile lives under $HOME, NOT under any temporary directory. It survives reboots and
#      macOS temp purges.
#   2. The profile is REUSED across runs, deliberately, so evidence accumulates in one known
#      place instead of a new directory per launch.
#   3. It is never the operator's Chrome profile (INC-004 guards, carried over verbatim).
#   4. The origin must be a SECURE CONTEXT, so Web Crypto is available and evidence can actually
#      be hashed (D-14).
#   5. Every launch appends to an audit log and refreshes a manifest, so evidence-origin identity
#      is explicit and auditable rather than remembered.
#   6. It checkpoints BEFORE launching, so a run can never be the only thing standing between the
#      corpus and loss.
#
# FAIL CLOSED. If any of that cannot be positively verified, this exits non-zero and launches
# nothing.
#
# USAGE
#   scripts/mogo_evidence_profile.sh --origin http://localhost:<PORT-CONFIRMED-WITH-THE-OPERATOR> \
#       [--profile-root <dir>] [--no-checkpoint] [--launch]
#
# The port is deliberately not shown as a literal. A copy-pasted origin is an inferred origin --
# the exact failure mode of INC-004. Confirm it with the operator every time.

set -euo pipefail

ORIGIN=""
PROFILE_ROOT="$HOME/MOGO-EVIDENCE-PROFILE"
LAUNCH=0
CHECKPOINT=1

# ── SELFTEST ─────────────────────────────────────────────────────────────────────────────────
# Every guard is exercised by invoking this script and asserting the exit status. A guard nobody
# has seen refuse is a guard nobody knows works -- and these guards exist because the last set of
# assumptions about isolation cost real data (INC-004) and a real corpus (D-15).
if [ "${1:-}" = "--selftest" ]; then
  SELF="${BASH_SOURCE[0]}"
  TESTROOT="$(mktemp -d "${TMPDIR:-/tmp}/mogo-m7-selftest-XXXXXX")"
  DURABLE_ROOT="$HOME/.mogo-m7-selftest-$$"
  fails=0
  ck() { # ck <expect-pass|expect-fail> <description> <args...>
    local want="$1"; shift
    local desc="$1"; shift
    set +e; out="$("$SELF" "$@" --no-checkpoint 2>&1)"; rc=$?; set -e
    if [ "$want" = "pass" ] && [ "$rc" -eq 0 ]; then echo "PASS -- $desc"
    elif [ "$want" = "fail" ] && [ "$rc" -ne 0 ]; then echo "PASS -- $desc"
    else echo "FAIL -- $desc (exit $rc)"; echo "$out" | sed 's/^/        /' | head -4; fails=$((fails+1)); fi
  }
  ck fail "no --origin is REFUSED (never inferred, INC-004)"                 --profile-root "$DURABLE_ROOT"
  ck fail "a LAN origin is REFUSED -- not a secure context (D-14)"           --origin "http://10.143.1.187:8744" --profile-root "$DURABLE_ROOT"
  ck fail "a non-localhost host is REFUSED (D-14)"                           --origin "http://192.168.1.50:8751" --profile-root "$DURABLE_ROOT"
  ck fail "the live operator origin 8744 is REFUSED (INC-004)"               --origin "http://localhost:8744" --profile-root "$DURABLE_ROOT"
  ck fail "the contaminated origin 8899 is REFUSED (INC-005)"                --origin "http://localhost:8899" --profile-root "$DURABLE_ROOT"
  ck fail "a TMPDIR profile root is REFUSED -- this is D-15 itself"          --origin "http://localhost:8751" --profile-root "$TESTROOT/x"
  ck fail "a /tmp profile root is REFUSED (D-15)"                            --origin "http://localhost:8751" --profile-root "/tmp/mogo-x"
  ck fail "the operator's Chrome directory is REFUSED (INC-004)"             --origin "http://localhost:8751" --profile-root "$HOME/Library/Application Support/Google/Chrome"
  ck fail "\$HOME itself is REFUSED"                                          --origin "http://localhost:8751" --profile-root "$HOME"
  ck fail "a relative profile root is REFUSED"                               --origin "http://localhost:8751" --profile-root "relative/path"
  ck pass "a durable localhost profile is ACCEPTED"                          --origin "http://localhost:8751" --profile-root "$DURABLE_ROOT"
  ck pass "127.0.0.1 is accepted (also a secure context)"                    --origin "http://127.0.0.1:8751" --profile-root "$DURABLE_ROOT-b"
  # Origin pinning: the second launch against a DIFFERENT origin must be refused (D-12).
  ck fail "re-pointing a pinned profile at another origin is REFUSED (D-12)" --origin "http://localhost:8752" --profile-root "$DURABLE_ROOT"
  ck pass "relaunching against the SAME pinned origin is accepted"           --origin "http://localhost:8751" --profile-root "$DURABLE_ROOT"
  # Durability proof: the profile must still exist and be outside every temp directory.
  if [ -d "$DURABLE_ROOT/profile" ]; then
    case "$DURABLE_ROOT" in
      /tmp/*|/private/tmp/*|/var/folders/*) echo "FAIL -- the accepted profile is in a temp directory"; fails=$((fails+1)) ;;
      *) echo "PASS -- the accepted profile persists outside every temporary directory" ;;
    esac
  else echo "FAIL -- the accepted profile was not created"; fails=$((fails+1)); fi
  [ -f "$DURABLE_ROOT/EVIDENCE_ORIGIN" ] && echo "PASS -- the evidence origin is recorded on disk (auditable)" \
    || { echo "FAIL -- no origin pin written"; fails=$((fails+1)); }
  [ -f "$DURABLE_ROOT/mogo-evidence-profile-audit.log" ] && echo "PASS -- every launch appends to an audit log" \
    || { echo "FAIL -- no audit log"; fails=$((fails+1)); }
  rm -rf "$TESTROOT" "$DURABLE_ROOT" "$DURABLE_ROOT-b"
  [ "$fails" = "0" ] && { echo "SELFTEST PASS -- all evidence-profile guards refuse and accept correctly"; exit 0; }
  echo "SELFTEST FAIL -- $fails check(s) failed"; exit 1
fi

while [ $# -gt 0 ]; do
  case "$1" in
    --origin)        ORIGIN="${2:-}"; shift 2 ;;
    --profile-root)  PROFILE_ROOT="${2:-}"; shift 2 ;;
    --no-checkpoint) CHECKPOINT=0; shift ;;
    --launch)        LAUNCH=1; shift ;;
    *) echo "FAIL: unknown argument '$1'" >&2; exit 2 ;;
  esac
done

fail() { echo "FAIL (evidence profile not verified — nothing launched): $*" >&2; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── GUARD 1: an explicit origin is mandatory. Never inferred, never defaulted. ────────────────
[ -n "$ORIGIN" ] || fail "--origin is required and must never be inferred from a config file (INC-004)."

# ── GUARD 2: the origin MUST be a secure context. This is what closes D-14. ───────────────────
#
# Web Crypto (crypto.subtle) is unavailable outside a secure context. Only localhost and 127.0.0.1
# qualify among plain-http origins; a LAN address such as http://10.143.1.187:8744 does NOT.
# MOGO degrades honestly there -- it stores the package with contentHash null and provenance
# UNAVAILABLE rather than inventing a weak digest -- but unhashable evidence cannot be verified,
# and evidence that cannot be verified is not evidence. So it is refused at the door.
case "$ORIGIN" in
  http://localhost:*|http://127.0.0.1:*|https://localhost:*|https://127.0.0.1:*) ;;
  http://*|https://*)
    fail "origin '$ORIGIN' is NOT a secure context. Web Crypto is unavailable there, so evidence
       captured at this origin CANNOT be hashed (D-14). Use http://localhost:<port>." ;;
  *) fail "origin '$ORIGIN' is not a recognised local origin." ;;
esac

# ── GUARD 3: refuse origins known to hold real or contaminated operator data. ─────────────────
# Carried over from scripts/browser_test_profile.sh. This is a DENYLIST and only a denylist: it
# can refuse an origin and can never approve one. The absence of a port proves nothing.
#   8744  the operator's LIVE MOGO origin (INC-004).
#   8899  a CONTAMINATED test origin holding the INC-005 hand-seeded record (INC-005).
NON_DISPOSABLE_PORTS="8744 8899"
for _port in $NON_DISPOSABLE_PORTS; do
  case "$ORIGIN" in
    *:"$_port"|*:"$_port"/*)
      fail "origin '$ORIGIN' is a known non-disposable origin (port $_port). Serve the evidence build on a port confirmed with the operator." ;;
  esac
done

# ── GUARD 4: the profile must be DURABLE. This is the inversion of the test launcher. ─────────
# browser_test_profile.sh REQUIRES a temp directory. This script REFUSES one. That is the whole
# point of D-15: a temp directory is exactly where the corpus was lost.
case "$PROFILE_ROOT" in
  /tmp/*|/private/tmp/*|/var/folders/*)
    fail "evidence profile root '$PROFILE_ROOT' is inside a temporary directory. macOS purges
       these, and that is precisely how the 222-package corpus was lost (D-15). Use a durable
       path under \$HOME." ;;
esac
case "$PROFILE_ROOT" in
  /*) ;;
  *) fail "evidence profile root must be an absolute path, got '$PROFILE_ROOT'." ;;
esac

# ── GUARD 5: never the operator's Chrome data (INC-004, carried over verbatim). ───────────────
OPERATOR_CHROME="$HOME/Library/Application Support/Google/Chrome"
case "$PROFILE_ROOT" in
  "$OPERATOR_CHROME"*) fail "profile root resolves inside the operator's Chrome directory." ;;
  "$HOME/Library/Application Support/Google"*) fail "profile root resolves inside Google application support." ;;
  "$HOME/Library/Application Support/Chromium"*|"$HOME/Library/Application Support/BraveSoftware"*|"$HOME/Library/Application Support/Microsoft Edge"*)
    fail "profile root resolves inside another browser's application support directory." ;;
esac
[ "$PROFILE_ROOT" != "$HOME" ] || fail "profile root must not be \$HOME itself."

# ── GUARD 6: the profile is REUSED, not recreated. Reuse is the feature. ──────────────────────
PROFILE_DIR="$PROFILE_ROOT/profile"
FIRST_RUN=0
if [ ! -d "$PROFILE_DIR" ]; then
  FIRST_RUN=1
  mkdir -p "$PROFILE_DIR"
fi
[ -d "$PROFILE_DIR" ] || fail "could not establish evidence profile directory: $PROFILE_DIR"
[ -w "$PROFILE_DIR" ] || fail "evidence profile directory is not writable: $PROFILE_DIR"

# ── GUARD 7: origin identity is PINNED to the profile. A profile serves ONE origin, forever. ──
#
# Evidence fragmented across three origins with separate stores and separate sequence counters is
# D-12. IndexedDB is partitioned by origin, so pointing this profile at a second origin would
# start a second, empty store inside the same profile and silently split the corpus again. The
# first origin used is recorded and every later launch must match it.
ORIGIN_PIN="$PROFILE_ROOT/EVIDENCE_ORIGIN"
if [ -f "$ORIGIN_PIN" ]; then
  PINNED="$(cat "$ORIGIN_PIN")"
  [ "$PINNED" = "$ORIGIN" ] || fail "this evidence profile is PINNED to origin '$PINNED', but
       '$ORIGIN' was requested. IndexedDB is partitioned by origin: launching against a second
       origin would start a second empty store and split the corpus (D-12). To retire this
       profile, archive it deliberately -- never by re-pointing it."
else
  printf '%s' "$ORIGIN" > "$ORIGIN_PIN"
fi

# ── GUARD 8: checkpoint BEFORE the run, so a launch is never the only copy. ───────────────────
CHECKPOINT_SCRIPT="$SCRIPT_DIR/mogo_evidence_checkpoint.sh"
if [ "$CHECKPOINT" = "1" ] && [ "$FIRST_RUN" = "0" ]; then
  [ -x "$CHECKPOINT_SCRIPT" ] || [ -f "$CHECKPOINT_SCRIPT" ] || \
    fail "checkpoint script missing: $CHECKPOINT_SCRIPT (pass --no-checkpoint only with a reason)."
  echo "── pre-launch checkpoint ─────────────────────────────────────────────"
  bash "$CHECKPOINT_SCRIPT" --profile "$PROFILE_DIR" --origin "$ORIGIN" \
    || fail "pre-launch checkpoint FAILED. Refusing to launch: a run must never be the only thing
       standing between the corpus and loss."
  echo ""
fi

# ── GUARD 9: record the facts, every launch, in an append-only audit log. ─────────────────────
NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
MANIFEST="$PROFILE_ROOT/mogo-evidence-profile-manifest.txt"
AUDIT="$PROFILE_ROOT/mogo-evidence-profile-audit.log"
IDB_DIR="$PROFILE_DIR/Default/IndexedDB"
STORE_COUNT=0
[ -d "$IDB_DIR" ] && STORE_COUNT="$(find "$IDB_DIR" -maxdepth 1 -name '*.indexeddb.leveldb' | wc -l | tr -d ' ')"
STORE_BYTES=0
[ -d "$IDB_DIR" ] && STORE_BYTES="$(du -sk "$IDB_DIR" 2>/dev/null | cut -f1)"

{
  echo "MOGO DURABLE evidence profile manifest"
  echo "updated_utc:            $NOW"
  echo "evidence_profile_path:  $PROFILE_DIR"
  echo "evidence_origin:        $ORIGIN  (PINNED)"
  echo "secure_context:         YES (verified: localhost/127.0.0.1 -- Web Crypto available)"
  echo "durable:                YES (verified: not under any temporary directory)"
  echo "operator_chrome_path:   $OPERATOR_CHROME"
  echo "is_operator_profile:    NO (verified: outside every known browser profile directory)"
  echo "disposable:             NO -- THIS PROFILE HOLDS REAL EVIDENCE. Never delete it to 'reset'."
  echo "indexeddb_stores:       $STORE_COUNT"
  echo "indexeddb_kilobytes:    $STORE_BYTES"
  echo "first_run:              $([ "$FIRST_RUN" = "1" ] && echo YES || echo NO)"
} > "$MANIFEST"

echo "$NOW  launch  origin=$ORIGIN  profile=$PROFILE_DIR  stores=$STORE_COUNT  kb=$STORE_BYTES" >> "$AUDIT"

CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
CMD="\"$CHROME\" --user-data-dir=\"$PROFILE_DIR\" --no-first-run --no-default-browser-check \"$ORIGIN\""

echo "DURABLE EVIDENCE PROFILE VERIFIED"
cat "$MANIFEST"
echo ""
echo "launch command:"
echo "  $CMD"

if [ "$LAUNCH" = "1" ]; then
  [ -x "$CHROME" ] || fail "Chrome not found at $CHROME"
  exec "$CHROME" --user-data-dir="$PROFILE_DIR" --no-first-run --no-default-browser-check "$ORIGIN"
fi

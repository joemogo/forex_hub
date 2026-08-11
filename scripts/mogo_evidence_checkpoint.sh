#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════════════════════
# MOGO — automatic evidence checkpointing (MOGO-011 M-7, closes D-15)
# ══════════════════════════════════════════════════════════════════════════════════════════
#
# WHY THIS EXISTS
#
# The 222-package corpus survived only because someone remembered to copy it by hand, once, days
# before macOS purged the directory it lived in. That is not a control -- it is luck with a
# procedure attached. This makes the copy automatic and self-verifying.
#
# WHAT A CHECKPOINT IS
#
# A timestamped, byte-identical copy of the browser IndexedDB tree, plus a SHA-256 manifest of
# every file copied, verified AFTER the copy by re-hashing the copy itself. A copy nobody verified
# is a copy nobody can rely on.
#
# READ-ONLY WITH RESPECT TO THE SOURCE
#
# The source profile is only ever read: `cp` reads it, `shasum` reads it, nothing writes to it. It
# never opens the LevelDB database -- doing so with a real client would replay the log, compact,
# and rewrite the very files being preserved. It copies bytes.
#
# THE TORN-COPY PROBLEM, STATED HONESTLY
#
# Chrome may be running while this executes, so a copy can in principle be taken mid-write. This
# is detected rather than assumed away: the source tree is fingerprinted BEFORE and AFTER the copy,
# and a checkpoint whose source moved underneath it is marked TORN and is not blessed. It is still
# KEPT -- a torn copy of irreplaceable evidence is worth far more than no copy -- but it is never
# recorded as verified, and the exit status says so.
#
# IDEMPOTENT BY CONTENT
#
# If the store has not changed since the last checkpoint, no new checkpoint is written. Checkpoints
# are cheap, but a directory of thousands of identical copies is its own kind of data loss.
#
# USAGE
#   scripts/mogo_evidence_checkpoint.sh --profile <CHROME_PROFILE_DIR> [--origin <ORIGIN>]
#                                       [--root <CHECKPOINT_ROOT>] [--verify-only]
#
# Exit status: 0 verified · 1 failed · 2 usage · 3 taken but TORN (kept, not blessed)

set -uo pipefail

PROFILE=""
ORIGIN=""
ROOT="$HOME/MOGO-EVIDENCE-PRESERVED"
VERIFY_ONLY=0

# ── SELFTEST ─────────────────────────────────────────────────────────────────────────────────
if [ "${1:-}" = "--selftest" ]; then
  SELF="${BASH_SOURCE[0]}"
  T="$(mktemp -d "${TMPDIR:-/tmp}/mogo-ckpt-selftest-XXXXXX")"
  DROOT="$HOME/.mogo-ckpt-selftest-$$"
  fails=0
  ck() { if [ "$1" = "1" ]; then echo "PASS -- $2"; else echo "FAIL -- $2"; fails=$((fails+1)); fi; }
  mkdir -p "$T/profile/Default/IndexedDB/http_localhost_1.indexeddb.leveldb"
  printf 'alpha' > "$T/profile/Default/IndexedDB/http_localhost_1.indexeddb.leveldb/000001.ldb"

  set +e
  out="$("$SELF" --profile "$T/profile" --root "$T/ckpt" 2>&1)"; rc=$?
  set -e
  ck "$([ $rc -ne 0 ] && echo 1 || echo 0)" "a checkpoint root inside a temp directory is REFUSED (D-15)"

  set +e; out="$("$SELF" --profile "$T/nope" --root "$DROOT" 2>&1)"; rc=$?; set -e
  ck "$([ $rc -ne 0 ] && echo 1 || echo 0)" "a missing profile directory is REFUSED"

  set +e; out="$("$SELF" --profile "$T/profile" --root "$DROOT" 2>&1)"; rc=$?; set -e
  ck "$([ $rc -eq 0 ] && echo 1 || echo 0)" "a clean checkpoint VERIFIES"
  STAMP="$(ls "$DROOT" | head -1)"
  ck "$([ -f "$DROOT/$STAMP/CHECKPOINT-MANIFEST.txt" ] && echo 1 || echo 0)" "a per-file SHA-256 manifest is written"
  ck "$(grep -q 'status:           VERIFIED' "$DROOT/$STAMP/CHECKPOINT-MANIFEST.txt" && echo 1 || echo 0)" "the manifest records status VERIFIED"
  ck "$([ -f "$DROOT/$STAMP/IndexedDB/http_localhost_1.indexeddb.leveldb/000001.ldb" ] && echo 1 || echo 0)" "the store bytes were actually copied"

  set +e; out="$("$SELF" --profile "$T/profile" --root "$DROOT" 2>&1)"; rc=$?; set -e
  ck "$(echo "$out" | grep -q 'UNCHANGED' && echo 1 || echo 0)" "an unchanged store writes NO second copy (idempotent)"

  printf 'beta' >> "$T/profile/Default/IndexedDB/http_localhost_1.indexeddb.leveldb/000001.ldb"
  set +e; out="$("$SELF" --profile "$T/profile" --root "$DROOT" 2>&1)"; rc=$?; set -e
  ck "$([ $rc -eq 0 ] && echo 1 || echo 0)" "a CHANGED store produces a new verified checkpoint"
  ck "$([ "$(ls -1 "$DROOT" | grep -c '^2' )" = "2" ] && echo 1 || echo 0)" "exactly two checkpoints now exist"

  # The source must be untouched by all of the above -- a preserver that alters what it preserves
  # is not a preserver.
  ck "$([ "$(cat "$T/profile/Default/IndexedDB/http_localhost_1.indexeddb.leveldb/000001.ldb")" = "alphabeta" ] && echo 1 || echo 0)" \
     "the SOURCE store is byte-unchanged by checkpointing (read-only)"

  rm -rf "$T" "$DROOT"
  [ "$fails" = "0" ] && { echo "SELFTEST PASS -- refusal, verification, manifest, idempotence, read-only source"; exit 0; }
  echo "SELFTEST FAIL -- $fails check(s) failed"; exit 1
fi

while [ $# -gt 0 ]; do
  case "$1" in
    --profile)     PROFILE="${2:-}"; shift 2 ;;
    --origin)      ORIGIN="${2:-}"; shift 2 ;;
    --root)        ROOT="${2:-}"; shift 2 ;;
    --verify-only) VERIFY_ONLY=1; shift ;;
    *) echo "FAIL: unknown argument '$1'" >&2; exit 2 ;;
  esac
done

fail() { echo "CHECKPOINT FAIL: $*" >&2; exit 1; }

[ -n "$PROFILE" ] || fail "--profile is required."
[ -d "$PROFILE" ] || fail "profile directory does not exist: $PROFILE"

SRC="$PROFILE/Default/IndexedDB"
if [ ! -d "$SRC" ]; then
  echo "CHECKPOINT SKIPPED: no IndexedDB tree yet at $SRC (nothing has been captured)."
  exit 0
fi

# ── Refuse to checkpoint INTO a temporary directory. ──────────────────────────────────────────
# A checkpoint stored where the original was lost preserves nothing.
case "$ROOT" in
  /tmp/*|/private/tmp/*|/var/folders/*)
    fail "checkpoint root '$ROOT' is inside a temporary directory. That is where the corpus was
       lost (D-15). Use a durable path under \$HOME." ;;
esac

# ── Fingerprint the SOURCE tree: every file's path, size and SHA-256. ─────────────────────────
fingerprint() {
  local dir="$1"
  ( cd "$dir" && find . -type f -print0 | sort -z | xargs -0 shasum -a 256 2>/dev/null )
}

BEFORE="$(fingerprint "$SRC")"
[ -n "$BEFORE" ] || fail "source tree produced no readable files: $SRC"
BEFORE_ROLLUP="$(printf '%s' "$BEFORE" | shasum -a 256 | cut -d' ' -f1)"
FILE_COUNT="$(printf '%s\n' "$BEFORE" | grep -c . || true)"

echo "source        : $SRC"
echo "files         : $FILE_COUNT"
echo "source rollup : $BEFORE_ROLLUP"

# ── Idempotence: has anything changed since the most recent checkpoint? ───────────────────────
mkdir -p "$ROOT" || fail "cannot create checkpoint root: $ROOT"
LAST_ROLLUP_FILE="$ROOT/.last-rollup"
if [ -f "$LAST_ROLLUP_FILE" ] && [ "$(cat "$LAST_ROLLUP_FILE")" = "$BEFORE_ROLLUP" ]; then
  echo "UNCHANGED since the last checkpoint — no new copy written (idempotent)."
  exit 0
fi

if [ "$VERIFY_ONLY" = "1" ]; then
  echo "VERIFY-ONLY: the store has CHANGED since the last checkpoint (rollup differs)."
  exit 0
fi

# ── Take the checkpoint. ─────────────────────────────────────────────────────────────────────
# Checkpoint directories are named by UTC timestamp at ONE-SECOND resolution, so two checkpoints
# taken inside the same second collide. Overwriting is never acceptable -- a checkpoint is the only
# copy of something irreplaceable -- but neither is failing, because the launcher refuses to start
# when its pre-launch checkpoint fails (GUARD 8). A hard failure here would block an evidence run
# over a naming detail. So a free name is found instead; the existing checkpoint is never touched.
# (Found by this script's own selftest, which began failing once the machine was fast enough to
# complete two checkpoints within the same second.)
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEST="$ROOT/$STAMP"
if [ -e "$DEST" ]; then
  _n=2
  while [ -e "$ROOT/$STAMP-$_n" ] && [ "$_n" -lt 100 ]; do _n=$((_n+1)); done
  [ -e "$ROOT/$STAMP-$_n" ] && fail "cannot find a free checkpoint name under $ROOT/$STAMP"
  DEST="$ROOT/$STAMP-$_n"
fi
mkdir -p "$DEST" || fail "cannot create checkpoint directory: $DEST"

cp -R "$SRC" "$DEST/IndexedDB" || fail "copy failed into $DEST"

# ── Re-fingerprint the SOURCE. If it moved, the copy may be torn. ────────────────────────────
AFTER="$(fingerprint "$SRC")"
AFTER_ROLLUP="$(printf '%s' "$AFTER" | shasum -a 256 | cut -d' ' -f1)"

# ── Fingerprint the COPY and require it to equal the source. ─────────────────────────────────
COPY="$(fingerprint "$DEST/IndexedDB")"
COPY_ROLLUP="$(printf '%s' "$COPY" | shasum -a 256 | cut -d' ' -f1)"

TORN=0
[ "$BEFORE_ROLLUP" = "$AFTER_ROLLUP" ] || TORN=1

STATUS="VERIFIED"
[ "$TORN" = "1" ] && STATUS="TORN"
[ "$COPY_ROLLUP" = "$BEFORE_ROLLUP" ] || STATUS="COPY_MISMATCH"

{
  echo "MOGO evidence checkpoint manifest"
  echo "created_utc:      $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "source_profile:   $PROFILE"
  echo "source_tree:      $SRC"
  echo "evidence_origin:  ${ORIGIN:-(not stated)}"
  echo "files:            $FILE_COUNT"
  echo "source_rollup_before: $BEFORE_ROLLUP"
  echo "source_rollup_after:  $AFTER_ROLLUP"
  echo "copy_rollup:          $COPY_ROLLUP"
  echo "status:           $STATUS"
  echo ""
  echo "# per-file SHA-256 of the COPY (paths relative to IndexedDB/)"
  printf '%s\n' "$COPY"
} > "$DEST/CHECKPOINT-MANIFEST.txt"

echo "checkpoint    : $DEST"
echo "copy rollup   : $COPY_ROLLUP"
echo "status        : $STATUS"

if [ "$STATUS" = "COPY_MISMATCH" ]; then
  fail "the copy does not match the source it was taken from. The checkpoint at $DEST is KEPT for
       inspection but must NOT be treated as a preserved copy."
fi

if [ "$STATUS" = "TORN" ]; then
  echo ""
  echo "WARNING: the source tree CHANGED while the copy was being taken, so this checkpoint may be"
  echo "torn. It has been KEPT -- a torn copy of irreplaceable evidence beats no copy -- but it is"
  echo "NOT recorded as the last verified checkpoint. Re-run with the browser closed."
  exit 3
fi

printf '%s' "$BEFORE_ROLLUP" > "$LAST_ROLLUP_FILE"
echo "CHECKPOINT VERIFIED"
exit 0

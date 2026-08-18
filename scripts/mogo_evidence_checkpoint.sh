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

  # ── Profile-path resolution. ────────────────────────────────────────────────────────────────
  # The live MOGO instance runs in `Profile 2` of the operator's own Chrome, not in a `Default`
  # profile of a dedicated user-data directory. Appending `Default` unconditionally resolved to
  # the wrong store, or to nothing at all -- and "nothing at all" exited 0, which reads as
  # success. All three outcomes are pinned here.
  mkdir -p "$T/profile2/IndexedDB/https_joemogo.github.io_0.indexeddb.leveldb"
  printf 'gamma' > "$T/profile2/IndexedDB/https_joemogo.github.io_0.indexeddb.leveldb/000001.ldb"
  set +e; out="$("$SELF" --profile "$T/profile2" --root "$DROOT" 2>&1)"; rc=$?; set -e
  ck "$([ $rc -eq 0 ] && echo 1 || echo 0)" "a PROFILE directory holding IndexedDB directly is checkpointed"
  ck "$(echo "$out" | grep -q "profile2/IndexedDB" && echo 1 || echo 0)" \
     "it copies the profile's OWN store, not a sibling Default profile's"

  # A user-data directory whose Default profile has the store must still resolve -- and must not
  # be shadowed by a sibling profile.
  mkdir -p "$T/udd/Default/IndexedDB/http_localhost_1.indexeddb.leveldb" "$T/udd/Profile 2/IndexedDB"
  printf 'delta' > "$T/udd/Default/IndexedDB/http_localhost_1.indexeddb.leveldb/000001.ldb"
  set +e; out="$("$SELF" --profile "$T/udd" --root "$DROOT" 2>&1)"; rc=$?; set -e
  ck "$([ $rc -eq 0 ] && echo 1 || echo 0)" "a user-data directory still resolves via Default (back-compatible)"

  # The defect this replaced: a path with no store exited 0, so a scheduled run reported healthy
  # while preserving nothing.
  mkdir -p "$T/notaprofile"
  set +e; out="$("$SELF" --profile "$T/notaprofile" --root "$DROOT" 2>&1)"; rc=$?; set -e
  ck "$([ $rc -eq 2 ] && echo 1 || echo 0)" "a path with no store and no Preferences is a usage ERROR, not a silent skip"
  ck "$([ $rc -ne 0 ] && echo 1 || echo 0)" "-- and specifically does not exit 0 (the old silent-success defect)"

  # A real profile that genuinely has not written IndexedDB yet is still a legitimate skip.
  mkdir -p "$T/fresh"; printf '{}' > "$T/fresh/Preferences"
  set +e; out="$("$SELF" --profile "$T/fresh" --root "$DROOT" 2>&1)"; rc=$?; set -e
  ck "$([ $rc -eq 0 ] && echo 1 || echo 0)" "a real profile with no store yet is still a clean SKIP"
  ck "$(echo "$out" | grep -q 'SKIPPED' && echo 1 || echo 0)" "-- and says SKIPPED rather than claiming a checkpoint"

  # ── Origin scoping. ─────────────────────────────────────────────────────────────────────────
  # `--origin` used to be recorded and ignored. The live instance now shares the operator's own
  # Chrome profile with ~100 unrelated origins, so an unscoped copy is an over-collection of
  # personal data. These pin that the flag actually restricts the copy.
  mkdir -p "$T/multi/IndexedDB/https_joemogo.github.io_0.indexeddb.leveldb" \
           "$T/multi/IndexedDB/https_bank.example.com_0.indexeddb.leveldb"
  printf 'mogo' > "$T/multi/IndexedDB/https_joemogo.github.io_0.indexeddb.leveldb/000001.ldb"
  printf 'private' > "$T/multi/IndexedDB/https_bank.example.com_0.indexeddb.leveldb/000001.ldb"

  SROOT="$DROOT-scoped"
  set +e; out="$("$SELF" --profile "$T/multi" --origin https://joemogo.github.io --root "$SROOT" 2>&1)"; rc=$?; set -e
  ck "$([ $rc -eq 0 ] && echo 1 || echo 0)" "an origin-scoped checkpoint VERIFIES"
  SCOPED="$(ls -1d "$SROOT"/*/IndexedDB 2>/dev/null | tail -1)"
  ck "$([ -n "$SCOPED" ] && echo 1 || echo 0)" "-- and actually produced a checkpoint to inspect (guards the two checks below)"
  ck "$([ -d "$SCOPED/https_joemogo.github.io_0.indexeddb.leveldb" ] && echo 1 || echo 0)" \
     "the named origin's store IS copied"
  ck "$([ ! -e "$SCOPED/https_bank.example.com_0.indexeddb.leveldb" ] && echo 1 || echo 0)" \
     "an UNRELATED origin's store is NOT copied (over-collection refused)"

  set +e; out="$("$SELF" --profile "$T/multi" --origin https://typo.example.org --root "$SROOT" 2>&1)"; rc=$?; set -e
  # Assert the REFUSAL MESSAGE, not merely a nonzero status. Without the message check this
  # passes for the wrong reason: `${SCOPE[*]}` on an empty array under `set -u` aborts bash 3.2
  # by itself, so removing the guard entirely still exits nonzero -- and the guard would look
  # tested while doing nothing. Found by mutating the guard away and watching the check survive.
  ck "$([ $rc -ne 0 ] && echo 1 || echo 0)" "an origin matching no store FAILS rather than preserving nothing quietly"
  ck "$(echo "$out" | grep -q 'matched no store' && echo 1 || echo 0)" "-- and refuses by name, not by an unbound-variable crash"

  mkdir -p "$T/ported/IndexedDB/http_localhost_8744.indexeddb.leveldb"
  printf 'p' > "$T/ported/IndexedDB/http_localhost_8744.indexeddb.leveldb/000001.ldb"
  set +e; out="$("$SELF" --profile "$T/ported" --origin http://localhost:8744 --root "$DROOT-ported" 2>&1)"; rc=$?; set -e
  ck "$([ $rc -eq 0 ] && echo 1 || echo 0)" "an origin WITH an explicit port resolves (no spurious _0 suffix)"

  rm -rf "$T" "$DROOT" "$DROOT-scoped" "$DROOT-ported"
  [ "$fails" = "0" ] && { echo "SELFTEST PASS -- refusal, resolution, scoping, verification, manifest, idempotence, read-only source"; exit 0; }
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

# ── Resolve the IndexedDB tree. ───────────────────────────────────────────────────────────────
# `--profile` is accepted BOTH as a Chrome profile directory (".../Chrome/Profile 2") and, for
# back-compatibility, as a user-data directory whose Default profile holds the store -- which is
# what the dedicated capture profiles looked like when this was written.
#
# The profile directory is tried FIRST, deliberately. Appending `Default` unconditionally is what
# made the old behaviour dangerous: the live MOGO instance now runs in `Profile 2` of the
# operator's own Chrome, so pointing at that Chrome resolved to a DIFFERENT profile's storage --
# which would have been copied and reported VERIFIED. Preserving the wrong store is worse than
# preserving nothing, because it looks like success.
#
# And a path that is neither is now a usage ERROR rather than a silent skip. Exit 0 on a
# mismatched path is how a scheduled checkpoint reports healthy while preserving nothing.
if [ -d "$PROFILE/IndexedDB" ]; then
  SRC="$PROFILE/IndexedDB"
elif [ -d "$PROFILE/Default/IndexedDB" ]; then
  SRC="$PROFILE/Default/IndexedDB"
elif [ -f "$PROFILE/Preferences" ] || [ -f "$PROFILE/Default/Preferences" ]; then
  echo "CHECKPOINT SKIPPED: no IndexedDB tree yet under $PROFILE (nothing has been captured)."
  exit 0
else
  echo "CHECKPOINT FAIL: '$PROFILE' holds no IndexedDB tree and does not look like a Chrome" >&2
  echo "  profile. Looked for: $PROFILE/IndexedDB, $PROFILE/Default/IndexedDB, and a" >&2
  echo "  Preferences file. Pass the profile directory itself, e.g. '.../Chrome/Profile 2'." >&2
  exit 2
fi

# ── Refuse to checkpoint INTO a temporary directory. ──────────────────────────────────────────
# A checkpoint stored where the original was lost preserves nothing.
case "$ROOT" in
  /tmp/*|/private/tmp/*|/var/folders/*)
    fail "checkpoint root '$ROOT' is inside a temporary directory. That is where the corpus was
       lost (D-15). Use a durable path under \$HOME." ;;
esac

# ── Scope the checkpoint to ONE origin when asked. ────────────────────────────────────────────
# `--origin` used to be recorded in the manifest and nothing else: every origin in the profile was
# copied regardless of it. That was harmless while MOGO ran in a dedicated capture profile that
# held a single origin. It is not harmless now. The live instance runs in the operator's OWN
# Chrome profile, alongside ~100 unrelated origins -- banking, tax, medical, retail -- and copying
# those into a durable evidence directory would be a serious over-collection of personal data for
# zero research benefit. The flag now restricts what is copied, which is what it always read as.
SCOPE=()
if [ -n "$ORIGIN" ]; then
  # Chrome names a store directory after the origin: `https://joemogo.github.io` becomes
  # `https_joemogo.github.io_0`, where the trailing field is the port and 0 means the default.
  # Either the origin URL or that encoded prefix is accepted.
  case "$ORIGIN" in
    *://*)
      PREFIX="$(printf '%s' "$ORIGIN" | sed -e 's#/*$##' -e 's#://#_#' -e 's#:#_#')"
      case "$ORIGIN" in *://*:*) ;; *) PREFIX="${PREFIX}_0" ;; esac ;;
    *) PREFIX="$ORIGIN" ;;
  esac
  for entry in "$SRC/$PREFIX".indexeddb.*; do
    [ -e "$entry" ] || continue
    SCOPE[${#SCOPE[@]}]="$(basename "$entry")"
  done
  [ ${#SCOPE[@]} -gt 0 ] || fail "origin '$ORIGIN' matched no store under $SRC
       (looked for ${PREFIX}.indexeddb.*). Refusing: preserving nothing because a flag was
       mistyped is precisely the silent failure this script exists to prevent."
  echo "scope         : $ORIGIN -> ${SCOPE[*]}"
else
  echo "scope         : ENTIRE profile ($(ls -1 "$SRC" | grep -c . || true) origins)"
  echo "                pass --origin to copy one origin only"
fi

# ── Fingerprint the SOURCE tree: every file's path, size and SHA-256. ─────────────────────────
# Honours the scope, so the before/after/copy comparison is over exactly what was preserved.
fingerprint() {
  local dir="$1"
  if [ ${#SCOPE[@]} -eq 0 ]; then
    ( cd "$dir" && find . -type f -print0 | sort -z | xargs -0 shasum -a 256 2>/dev/null )
  else
    ( cd "$dir" && for e in "${SCOPE[@]}"; do
        [ -e "./$e" ] && find "./$e" -type f -print0
      done | sort -z | xargs -0 shasum -a 256 2>/dev/null )
  fi
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

if [ ${#SCOPE[@]} -eq 0 ]; then
  cp -R "$SRC" "$DEST/IndexedDB" || fail "copy failed into $DEST"
else
  mkdir -p "$DEST/IndexedDB" || fail "cannot create $DEST/IndexedDB"
  for e in "${SCOPE[@]}"; do
    cp -R "$SRC/$e" "$DEST/IndexedDB/$e" || fail "copy failed for '$e' into $DEST"
  done
fi

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

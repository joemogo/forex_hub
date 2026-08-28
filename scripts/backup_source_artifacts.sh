#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════════════════════
# MOGO — encrypted backup of the source-evidence artifacts (ADR-010 amendment A4)
# ══════════════════════════════════════════════════════════════════════════════════════════
#
# WHY THIS EXISTS RATHER THAN A GIT COMMIT
#
# The capture artifacts contain OANDA-derived market data. OANDA's API licence limits that
# data to Internal Use and prohibits transmitting, publishing, disseminating or otherwise
# providing OANDA Trading System Rates to third parties. Committing them would put them on
# GitHub, so ADR-010's original rejection stands and option A3 was withdrawn.
#
# What Git keeps is ARTIFACT_INDEX.json: paths, sizes, counts and hashes. A SHA-256 is not
# rates and cannot reconstruct them, so the verification chain can be public while the data
# stays entirely operator-local. That split is the whole design.
#
# NO PLAINTEXT ARCHIVE IS EVER WRITTEN
#
# The obvious implementation -- tar the artifacts, then encrypt the tar -- writes a complete
# unencrypted copy of every candle to disk first. This does not do that. It creates an EMPTY
# encrypted image, attaches it, and copies the seventeen literal paths INTO it. Plaintext
# exists only inside the attached encrypted volume, which is unavoidable for any encryption
# scheme, and never as a file this script created outside one.
#
# THE PASSWORD
#
# Read from the terminal with `read -s`, passed to hdiutil on STDIN via -stdinpass, and never
# anywhere else. Not in argv (visible in `ps` to every process on the machine), not in an
# environment variable, not in a file, not in a receipt, not in shell history, not in the
# Keychain. Losing it means losing the archive; that is the trade, and it is deliberate.
#
# WHAT IT NEVER DOES
#
# Commit, push, stage, upload, e-mail, synchronise, or make any network call. Install
# anything. Run from a hook, a timer, or forward_capture.sh. Touch Time Machine's managed
# structure. Overwrite an existing evidence file. Delete a completed backup.
#
# USAGE -- every mode needs an exact destination AND --confirm, and prompts interactively
#   scripts/backup_source_artifacts.sh --backup  --dest /Volumes/MOGOTH/<folder> --confirm
#   scripts/backup_source_artifacts.sh --verify  --dest /Volumes/MOGOTH/<folder>/<img>.dmg --confirm [--deep]
#   scripts/backup_source_artifacts.sh --restore --dest /Volumes/MOGOTH/<folder>/<img>.dmg --confirm
#
# Exit: 0 success · 1 refused or failed · 2 usage
# ══════════════════════════════════════════════════════════════════════════════════════════
set -uo pipefail
umask 077                       # receipts and images are operator-only from the moment of creation

# ── Tracing is neutralised before anything else happens ──────────────────────────────────────
# `set -x` in an ancestor shell, or SHELLOPTS=xtrace inherited from the environment, would
# echo every expanded command -- including the pipeline that feeds the passphrase to hdiutil.
# bash applies an inherited SHELLOPTS at startup, so refusing to run is not enough: it must be
# turned OFF here, and never turned back on. BASH_XTRACEFD is unset for the same reason.
set +x
set +o xtrace 2>/dev/null || true
set +v
unset BASH_XTRACEFD 2>/dev/null || true
{ export -n SHELLOPTS; } 2>/dev/null || true   # readonly in bash; set +x above is what disables it

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT" || { echo "FAIL: cannot reach repository root" >&2; exit 1; }

INDEX="docs/trader-intelligence/evidence/ledger-preservation/ARTIFACT_INDEX.json"
RECEIPT_DIR="evidence/.backup-receipts"
VOLNAME="MOGO-EVIDENCE"
MOUNT_POINT=""                  # set when an image is attached; used by the trap

say()  { echo "[backup] $*"; }
fail() { echo "REFUSED: $*" >&2; exit 1; }

MODE=""; DEST=""; CONFIRM=0; DEEP=0; LABEL=""
while [ $# -gt 0 ]; do
  case "$1" in
    --backup)  MODE="backup";  shift ;;
    --verify)  MODE="verify";  shift ;;
    --restore) MODE="restore"; shift ;;
    --dest)    DEST="${2:-}";  shift 2 ;;
    --label)   LABEL="${2:-}"; shift 2 ;;
    --confirm) CONFIRM=1;      shift ;;
    --deep)    DEEP=1;         shift ;;
    # A password can never arrive as an argument. Named explicitly so the refusal is a
    # message rather than an "unknown argument", and so nobody adds one later.
    --password|--pass|--passphrase|-p)
      fail "a password must never be passed as a command-line argument -- it is visible in \`ps\` to every process on this machine. Run without it and enter it at the prompt." ;;
    *) echo "FAIL: unknown argument '$1'" >&2; exit 2 ;;
  esac
done

[ -n "$MODE" ] || { echo "usage: $0 --backup|--verify|--restore --dest <path> --confirm" >&2; exit 2; }
[ -n "$DEST" ] || fail "every mode requires an exact --dest path"
[ "$CONFIRM" = "1" ] || fail "every mode requires --confirm. This is never automatic."

# ── Destination sanity, shared by every mode ─────────────────────────────────────────────────
# Deliberately BEFORE the terminal requirement. Validating an argument is not performing an
# operation, and a bad path should report why it is bad rather than "no terminal" -- which
# would also make every refusal untestable without allocating a pty.
case "$DEST" in
  *'*'*|*'?'*|*'['*) fail "'$DEST' looks like a glob; pass one exact path" ;;
  *..*)              fail "'$DEST' contains '..'; refusing to traverse" ;;
  /*)                : ;;
  *)                 fail "'$DEST' must be an absolute path" ;;
esac
[ -L "$DEST" ] && fail "'$DEST' is a symlink; pass the real path"

# Time Machine's managed structure is off limits. TM owns those directories, prunes them on
# its own schedule, and a file placed inside one is a file TM may remove without telling us.
case "$DEST" in
  */Backups.backupdb/*|*/Backups.backupdb|*/.timemachine/*|*/.timemachine|*/.Spotlight-V100/*|*/.TemporaryItems/*|*/.fseventsd/*)
    fail "'$DEST' is inside a Time Machine or system-managed directory. Choose a plain folder on the volume instead." ;;
esac

VOLUME_ROOT="$(printf '%s\n' "$DEST" | awk -F/ '/^\/Volumes\//{print "/"$2"/"$3}')"
if [ -n "$VOLUME_ROOT" ]; then
  [ "$DEST" = "$VOLUME_ROOT" ] && fail "'$DEST' is the volume root. Use a dedicated folder on it, not the top level."
  [ -d "$VOLUME_ROOT" ] || fail "volume '$VOLUME_ROOT' is not mounted"
  if diskutil info "$VOLUME_ROOT" 2>/dev/null | grep -qE 'Volume Read-Only:[[:space:]]*Yes'; then
    fail "'$VOLUME_ROOT' is mounted read-only"
  fi
  if tmutil destinationinfo 2>/dev/null | grep -qF "$VOLUME_ROOT"; then
    say "NOTE: $VOLUME_ROOT is also a Time Machine destination."
    say "      This backup therefore shares one physical device with your system backup."
    say "      It improves resilience; it is NOT an independent offline copy. One drive"
    say "      failure loses both. See ADR-010 amendment A4 for the second-device plan."
  fi
fi

# ── The canonicalizer, extracted verbatim from the committed index.html ──────────────────────
# Never reimplemented: a second implementation is free to drift into agreement with whatever
# it is checking.
verify_packages_in() {
  ARTIFACT="$1" node -e '
    const fs=require("fs"),crypto=require("crypto");
    const src=fs.readFileSync("index.html","utf8");
    const grab=(re,l)=>{const m=src.match(re); if(!m) throw new Error("cannot extract "+l); return m[0];};
    const parts=[
      grab(/const EVIDENCE_HASH_EXCLUDED_FIELDS=Object\.freeze\(\[[^\]]*\]\);/,"EVIDENCE_HASH_EXCLUDED_FIELDS"),
      grab(/function evidenceCanonValue\(v,seen\)\{[\s\S]*?\n\}/,"evidenceCanonValue"),
      grab(/function evidenceCanonicalize\(pkg\)\{[\s\S]*?\n\}/,"evidenceCanonicalize")];
    const g={}; new Function("g",parts.join("\n")+"\ng.canonicalize=evidenceCanonicalize;")(g);
    const doc=JSON.parse(fs.readFileSync(process.env.ARTIFACT,"utf8"));
    const pkgs=Array.isArray(doc)?doc:(doc.packages||[]);
    if(!pkgs.length){ console.error("no packages in "+process.env.ARTIFACT); process.exit(1); }
    let bad=0;
    for(const p of pkgs){
      const h=crypto.createHash("sha256").update(g.canonicalize(p),"utf8").digest("hex");
      if(h!==p.contentHash){ console.error("package hash mismatch in "+process.env.ARTIFACT+": "+p.packageId); bad++; }
    }
    if(bad) process.exit(1);
    console.log(pkgs.length);
  '
}

# ── The artifact list comes from the INDEX, never from a directory listing ───────────────────
# A glob over evidence/ would pick up whatever happens to be lying there. The index is the
# declaration of what this backup is for, and anything not in it is an unexpected file.
read_index_paths() { python3 -c '
import json,sys
d=json.load(open(sys.argv[1],encoding="utf-8"))
for a in d["artifacts"]: print(a["path"])
' "$INDEX"; }

index_field() { python3 -c '
import json,sys
d=json.load(open(sys.argv[1],encoding="utf-8"))
for a in d["artifacts"]:
    if a["path"]==sys.argv[2]: print(a[sys.argv[3]]); break
' "$INDEX" "$1" "$2"; }

file_sha256() { shasum -a 256 "$1" | cut -d' ' -f1; }

# ── Verify every declared artifact, before anything is created or copied ─────────────────────
verify_all_artifacts() {
  local n=0 pk=0
  [ -f "$INDEX" ] || fail "artifact index not found: $INDEX"
  while IFS= read -r rel; do
    [ -n "$rel" ] || continue
    case "$rel" in
      evidence/*-PACKAGES.json) : ;;
      *) fail "index entry '$rel' is not an evidence capture artifact" ;;
    esac
    [ -e "$rel" ] || fail "declared artifact is missing: $rel"
    [ -L "$rel" ] && fail "declared artifact is a symlink: $rel"
    [ -f "$rel" ] || fail "declared artifact is not a regular file: $rel"
    local want got count
    want="$(index_field "$rel" sha256)"
    got="$(file_sha256 "$rel")"
    [ "$want" = "$got" ] || fail "whole-file hash mismatch for $rel (index $want, actual $got)"
    count="$(verify_packages_in "$rel")" || fail "package verification failed for $rel"
    [ "$count" = "$(index_field "$rel" packageCount)" ] || fail "package count disagrees with the index for $rel"
    n=$((n+1)); pk=$((pk+count))
  done <<EOF
$(read_index_paths)
EOF
  [ "$n" -gt 0 ] || fail "the index declared no artifacts; refusing to back up nothing"
  say "verified $n artifact(s), $pk package(s) -- whole-file and canonical hashes both agree"
  VERIFIED_COUNT="$n"; VERIFIED_PACKAGES="$pk"
}

# ── Always detach on the way out, however we leave ───────────────────────────────────────────
# SIGNALLED exists because a trap cannot read the exit status of a run that has not exited.
# On SIGTERM during `hdiutil create`, `$?` inside the trap was 0 -- the status of the last
# COMPLETED command -- so cleanup concluded the run had succeeded and kept the half-written
# image. Found by interrupting a real creation; the structural test that asserted the trap
# and the marker both existed passed against exactly this behaviour.
SIGNALLED=0
on_signal() { SIGNALLED=1; exit 130; }
trap on_signal INT TERM

cleanup() {
  local rc=$?
  [ "$SIGNALLED" = "1" ] && rc=130
  if [ -n "$MOUNT_POINT" ] && [ -d "$MOUNT_POINT" ]; then
    hdiutil detach "$MOUNT_POINT" -quiet 2>/dev/null || hdiutil detach "$MOUNT_POINT" -force -quiet 2>/dev/null
    MOUNT_POINT=""
  fi
  # A partial image from a failed CREATE is removed; a previously completed backup never is.
  if [ "$rc" -ne 0 ] && [ "${PARTIAL_IMAGE:-}" != "" ] && [ -f "${PARTIAL_IMAGE}" ]; then
    rm -f -- "${PARTIAL_IMAGE}"
    echo "[backup] removed the partial image left by the failure: ${PARTIAL_IMAGE}" >&2
  fi
  exit "$rc"
}
trap cleanup EXIT

read_password_twice() {
  # Belt and braces: even if something re-enabled tracing between entry and here, the
  # passphrase must not reach a trace stream. Never re-enabled afterwards.
  set +x
  set +o xtrace 2>/dev/null || true
  local a b
  printf 'Encryption passphrase (not echoed, never stored): ' >&2
  IFS= read -rs a; printf '\n' >&2
  printf 'Re-enter to confirm: ' >&2
  IFS= read -rs b; printf '\n' >&2
  [ -n "$a" ] || fail "empty passphrase"
  [ "$a" = "$b" ] || fail "passphrases did not match"
  PASSWORD="$a"
}

confirm_prompt() {
  local answer
  printf '%s\nType YES to proceed: ' "$1" >&2
  IFS= read -r answer
  [ "$answer" = "YES" ] || fail "not confirmed at the prompt"
}

# ══ BACKUP ═══════════════════════════════════════════════════════════════════════════════════
do_backup() {
  [ -d "$DEST" ] || fail "destination folder does not exist: $DEST (create it yourself; this script does not)"
  [ -w "$DEST" ] || fail "destination folder is not writable: $DEST"

  verify_all_artifacts

  local bytes need_mb avail_kb
  bytes="$(python3 -c '
import json,sys
d=json.load(open(sys.argv[1],encoding="utf-8"))
print(sum(a["bytes"] for a in d["artifacts"]))' "$INDEX")"
  # Filesystem overhead plus the receipt; 64 MB floor so a tiny corpus still gets a valid image.
  need_mb=$(( (bytes / 1048576) * 2 + 64 ))
  avail_kb="$(df -k "$DEST" | awk 'NR==2{print $4}')"
  [ "$avail_kb" -gt $(( need_mb * 1024 * 2 )) ] \
    || fail "not enough free space at $DEST: need ~$(( need_mb * 2 )) MB headroom, have $(( avail_kb / 1024 )) MB"

  local stamp img
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  img="$DEST/mogo-evidence-$stamp.dmg"
  [ -e "$img" ] && fail "an image already exists at $img; refusing to overwrite"

  confirm_prompt "About to create an AES-256 encrypted image at:
  $img
containing $VERIFIED_COUNT artifact(s) / $VERIFIED_PACKAGES package(s).
Nothing is uploaded, committed, or transmitted. The passphrase is never stored."

  read_password_twice

  PARTIAL_IMAGE="$img"
  say "creating the encrypted image (empty -- no plaintext archive is ever written)"
  printf '%s' "$PASSWORD" | hdiutil create \
      -size "${need_mb}m" -fs "APFS" -volname "$VOLNAME" \
      -encryption AES-256 -stdinpass -type UDIF -quiet "$img" \
    || fail "hdiutil could not create the image"

  say "attaching"
  MOUNT_POINT="$(printf '%s' "$PASSWORD" | hdiutil attach -stdinpass -nobrowse -owners on \
      -mountpoint "/Volumes/$VOLNAME" -quiet "$img" >/dev/null 2>&1 && echo "/Volumes/$VOLNAME")"
  [ -n "$MOUNT_POINT" ] && [ -d "$MOUNT_POINT" ] || fail "could not attach the image just created"

  mkdir -p "$MOUNT_POINT/evidence" || fail "cannot create the payload folder inside the image"
  local copied=0
  while IFS= read -r rel; do
    [ -n "$rel" ] || continue
    cp -- "$rel" "$MOUNT_POINT/evidence/$(basename "$rel")" || fail "copy failed for $rel"
    [ "$(file_sha256 "$MOUNT_POINT/evidence/$(basename "$rel")")" = "$(index_field "$rel" sha256)" ] \
      || fail "the copy of $rel inside the image does not match its index hash"
    copied=$((copied+1))
  done <<EOF
$(read_index_paths)
EOF
  [ "$copied" = "$VERIFIED_COUNT" ] || fail "copied $copied of $VERIFIED_COUNT artifacts"
  say "copied and re-verified $copied artifact(s) inside the image"

  # Receipt inside the image. The archive's own hash cannot be known yet, so it is recorded
  # only in the local receipt written after detach -- stated rather than left as a puzzle.
  write_receipt "$MOUNT_POINT/BACKUP_RECEIPT.json" "$stamp" "" "PENDING_DETACH"
  cp -- "$INDEX" "$MOUNT_POINT/ARTIFACT_INDEX.json" || fail "could not place the index inside the image"

  say "detaching"
  hdiutil detach "$MOUNT_POINT" -quiet || fail "could not detach cleanly"
  MOUNT_POINT=""

  local archive_hash
  archive_hash="$(file_sha256 "$img")"
  mkdir -p "$RECEIPT_DIR"
  write_receipt "$RECEIPT_DIR/receipt-$stamp.json" "$stamp" "$archive_hash" "VERIFIED_ON_CREATE"
  PARTIAL_IMAGE=""            # the backup is complete; it must never be removed by cleanup

  say "done."
  echo
  echo "  image        : $img"
  echo "  archive sha256: $archive_hash"
  echo "  local receipt: $RECEIPT_DIR/receipt-$stamp.json  (gitignored)"
  echo "  Nothing was uploaded, committed, pushed, or transmitted."
  echo "  Verify later:  $0 --verify --dest \"$img\" --confirm"
}

# `label` is operator-chosen and describes the destination in words, never a path.
write_receipt() {
  local out="$1" stamp="$2" archive_hash="$3" verdict="$4"
  OUT="$out" STAMP="$stamp" ARCHIVE_HASH="$archive_hash" VERDICT="$verdict" \
  LABEL="${LABEL:-unlabelled}" INDEX="$INDEX" python3 - <<'PY'
import json, os, subprocess

def tool(cmd, args):
    try:
        r = subprocess.run([cmd] + args, capture_output=True, text=True, timeout=30)
        return (r.stdout + r.stderr).strip().split("\n")[0][:120]
    except Exception:
        return "unavailable"

index = json.load(open(os.environ["INDEX"], encoding="utf-8"))
receipt = {
    "schemaVersion": "mogo.backup-receipt.v1",
    "backupUTC": os.environ["STAMP"],
    "destinationLabel": os.environ["LABEL"],
    "archiveSha256": os.environ["ARCHIVE_HASH"] or None,
    "verificationResult": os.environ["VERDICT"],
    "artifactCount": len(index["artifacts"]),
    "packageCount": sum(a["packageCount"] for a in index["artifacts"]),
    "artifactHashes": {a["path"]: a["sha256"] for a in index["artifacts"]},
    "indexSchemaVersion": index["schemaVersion"],
    "toolVersions": {
        "hdiutil": tool("hdiutil", ["version"]),
        "shasum": tool("shasum", ["--version"]),
        "sw_vers": tool("sw_vers", ["-productVersion"]),
        "node": tool("node", ["--version"]),
    },
    "notice": ("Operator-internal record. Contains hashes and counts only -- no candles, "
               "no OHLC values, no prices, no account identifiers, no credentials, and no "
               "passphrase. The archive holds OANDA-derived market data restricted to "
               "Internal Use; it must never be transmitted, published, disseminated or "
               "provided to any third party."),
}
with open(os.environ["OUT"], "w", encoding="utf-8") as handle:
    json.dump(receipt, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
  [ -f "$out" ] || fail "receipt was not written: $out"
}

# ══ VERIFY ═══════════════════════════════════════════════════════════════════════════════════
do_verify() {
  [ -f "$DEST" ] || fail "no image at $DEST"
  local stamp receipt want got
  stamp="$(basename "$DEST" .dmg)"; stamp="${stamp#mogo-evidence-}"
  receipt="$RECEIPT_DIR/receipt-$stamp.json"
  [ -f "$receipt" ] || fail "no local receipt for this image at $receipt"

  want="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1],encoding="utf-8"))["archiveSha256"] or "")' "$receipt")"
  [ -n "$want" ] || fail "the receipt records no archive hash"
  got="$(file_sha256 "$DEST")"
  say "archive sha256 (no decryption performed)"
  echo "  receipt: $want"
  echo "  actual : $got"
  [ "$want" = "$got" ] || fail "ARCHIVE CORRUPTED OR ALTERED -- hashes differ"
  say "archive hash MATCHES the receipt."

  [ "$DEEP" = "1" ] || { say "shallow verify only. Add --deep to mount read-only and check every file."; return 0; }

  confirm_prompt "Deep verify will ATTACH the image READ-ONLY and re-hash every file inside it.
It will be detached again before this command returns."
  read_password_twice
  MOUNT_POINT="$(printf '%s' "$PASSWORD" | hdiutil attach -stdinpass -readonly -nobrowse \
      -mountpoint "/Volumes/$VOLNAME" -quiet "$DEST" >/dev/null 2>&1 && echo "/Volumes/$VOLNAME")"
  [ -n "$MOUNT_POINT" ] && [ -d "$MOUNT_POINT" ] || fail "could not attach read-only (wrong passphrase, or the image is damaged)"

  local n=0
  while IFS= read -r rel; do
    [ -n "$rel" ] || continue
    local inside="$MOUNT_POINT/evidence/$(basename "$rel")"
    [ -f "$inside" ] || fail "missing inside the image: $(basename "$rel")"
    [ "$(file_sha256 "$inside")" = "$(index_field "$rel" sha256)" ] \
      || fail "hash mismatch inside the image for $(basename "$rel")"
    n=$((n+1))
  done <<EOF
$(read_index_paths)
EOF
  [ "$n" -gt 0 ] || fail "verified nothing; the index declared no artifacts"
  hdiutil detach "$MOUNT_POINT" -quiet || fail "could not detach after verification"
  MOUNT_POINT=""
  say "deep verify PASSED -- $n file(s) match the index. Image detached."
}

# ══ RESTORE ══════════════════════════════════════════════════════════════════════════════════
do_restore() {
  [ -f "$DEST" ] || fail "no image at $DEST"
  confirm_prompt "RESTORE will attach the image READ-ONLY and copy back ONLY artifacts that are
currently MISSING. It will never overwrite or alter an existing evidence file."
  read_password_twice

  MOUNT_POINT="$(printf '%s' "$PASSWORD" | hdiutil attach -stdinpass -readonly -nobrowse \
      -mountpoint "/Volumes/$VOLNAME" -quiet "$DEST" >/dev/null 2>&1 && echo "/Volumes/$VOLNAME")"
  [ -n "$MOUNT_POINT" ] && [ -d "$MOUNT_POINT" ] || fail "could not attach read-only"

  local restored=() skipped=0 rel inside want
  while IFS= read -r rel; do
    [ -n "$rel" ] || continue
    if [ -e "$rel" ]; then
      skipped=$((skipped+1)); say "present already, refusing to overwrite: $rel"; continue
    fi
    inside="$MOUNT_POINT/evidence/$(basename "$rel")"
    [ -f "$inside" ] || fail "the image does not contain $(basename "$rel")"
    cp -- "$inside" "$rel" || fail "restore copy failed for $rel"
    want="$(index_field "$rel" sha256)"
    if [ "$(file_sha256 "$rel")" != "$want" ]; then
      say "restored file failed verification; rolling back everything restored in this run"
      rm -f -- "$rel"
      local r; for r in "${restored[@]:-}"; do [ -n "$r" ] && rm -f -- "$r"; done
      fail "restore aborted: $rel did not match the index after copying"
    fi
    restored+=("$rel"); say "restored and verified: $rel"
  done <<EOF
$(read_index_paths)
EOF

  hdiutil detach "$MOUNT_POINT" -quiet || fail "could not detach after restore"
  MOUNT_POINT=""
  say "restore complete -- ${#restored[@]} restored, $skipped left untouched because they already existed."
}

# ── Interactive only ─────────────────────────────────────────────────────────────────────────
# A backup that can run unattended is a backup that can run from a hook. Requiring a terminal
# is the enforcement; a comment saying "do not automate this" is not. Checked here, after
# argument validation and immediately before anything is actually performed.
[ -t 0 ] || fail "no terminal on stdin. This tool is interactive by design and must never run from a hook, a timer, or another script."

case "$MODE" in
  backup)  do_backup ;;
  verify)  do_verify ;;
  restore) do_restore ;;
esac

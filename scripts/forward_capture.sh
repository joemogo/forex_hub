#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════════════════════
# MOGO — forward evidence capture, end to end and offline (MOGO-022)
# ══════════════════════════════════════════════════════════════════════════════════════════
#
# WHAT THIS IS
#
#   detect → preserve → recover → import → reconcile
#
# Every step already existed as a separate tool and was being run by hand in sequence. This
# composes them, so forward capture is one reproducible command rather than a procedure
# somebody has to remember at the right moment. Forward evidence is perishable: a package can
# exist only in the uncompacted write-ahead log, and compaction runs within hours.
#
# WHY IT CAN RUN OFFLINE NOW
#
# The manifest extractor emits package METADATA only -- enough to detect that a close happened,
# not enough to import it, because the trade fields live in `objects`. That gap is why capture
# previously needed a live browser read. `--packages` re-uses the deserialization that already
# backed `--verify` and writes the full payloads, so nothing here touches the running app.
#
# READ-ONLY WITH RESPECT TO THE RUNNING INSTANCE
#
# The live profile is only ever READ, and only its own origin (see the checkpoint script's
# --origin handling -- the operator's profile holds ~100 unrelated origins). Nothing reloads,
# navigates, or drives the browser. INC-004 stands.
#
# FAIL CLOSED
#
# A package whose stored content hash does not re-derive from the preserved bytes is never
# written and never imported. Import is DRY RUN unless --write is passed.
#
# USAGE
#   scripts/forward_capture.sh [--profile <CHROME_PROFILE_DIR>] [--origin <ORIGIN>] [--write]
#
# Exit: 0 captured or nothing new · 1 failure · 2 usage

set -uo pipefail

PROFILE="$HOME/Library/Application Support/Google/Chrome/Profile 2"
ORIGIN="https://joemogo.github.io"
WRITE=0

while [ $# -gt 0 ]; do
  case "$1" in
    --profile) PROFILE="${2:-}"; shift 2 ;;
    --origin)  ORIGIN="${2:-}"; shift 2 ;;
    --write)   WRITE=1; shift ;;
    *) echo "FAIL: unknown argument '$1'" >&2; exit 2 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT" || { echo "FAIL: cannot reach repository root" >&2; exit 1; }

say() { echo "[forward-capture] $*"; }

# ── 1. DETECT ────────────────────────────────────────────────────────────────────────────────
# Cheap: fingerprints the store and compares against the last checkpoint. Costs nothing when
# the market is idle, which is most of the time.
say "detect: has the evidence store changed since the last checkpoint?"
DETECT="$(scripts/mogo_evidence_checkpoint.sh --profile "$PROFILE" --origin "$ORIGIN" --verify-only 2>&1)"
DETECT_RC=$?
echo "$DETECT" | sed 's/^/    /'
if [ $DETECT_RC -ne 0 ]; then
  echo "FAIL: detection step failed" >&2; exit 1
fi
if echo "$DETECT" | grep -q 'UNCHANGED'; then
  say "nothing new since the last checkpoint. Done."
  exit 0
fi

# ── 2. PRESERVE ──────────────────────────────────────────────────────────────────────────────
# A verified, byte-identical copy, taken BEFORE anything is parsed. If the rest of this script
# fails, the evidence still survives -- that ordering is the whole point.
say "preserve: taking a verified checkpoint"
CKPT_OUT="$(scripts/mogo_evidence_checkpoint.sh --profile "$PROFILE" --origin "$ORIGIN" 2>&1)"
CKPT_RC=$?
echo "$CKPT_OUT" | sed 's/^/    /'
if [ $CKPT_RC -ne 0 ] && [ $CKPT_RC -ne 3 ]; then
  echo "FAIL: checkpoint failed" >&2; exit 1
fi
[ $CKPT_RC -eq 3 ] && say "WARNING: checkpoint is TORN (source moved mid-copy). Kept, not blessed."

CKPT_DIR="$(echo "$CKPT_OUT" | awk '/^checkpoint    :/ {print $3}')"
if [ -z "$CKPT_DIR" ]; then
  say "no new checkpoint directory was written; using the most recent one"
  CKPT_DIR="$(ls -1dt "$HOME"/MOGO-EVIDENCE-PRESERVED/2026* 2>/dev/null | head -1)"
fi
STORE="$(ls -1d "$CKPT_DIR"/IndexedDB/*.indexeddb.leveldb 2>/dev/null | head -1)"
[ -n "$STORE" ] || { echo "FAIL: no leveldb store inside $CKPT_DIR" >&2; exit 1; }

# ── 3. RECOVER ───────────────────────────────────────────────────────────────────────────────
# Full payloads, and ONLY those whose stored hash re-derives from the preserved bytes.
STAMP="$(basename "$CKPT_DIR")"
PKG_FILE="evidence/FWD-${STAMP}-PACKAGES.json"
say "recover: reconstructing hash-verified packages from the checkpoint"
if ! node scripts/mogo_evidence_leveldb_extract.js --store "$STORE" --packages "$PKG_FILE" 2>&1 | sed 's/^/    /'; then
  echo "FAIL: package recovery failed or a hash did not re-derive" >&2; exit 1
fi

# ── 4. IS ANY OF IT ACTUALLY NEW? ────────────────────────────────────────────────────────────
# Keyed on contentHash, never packageId: the ordinal in a packageId only counts within one
# capture run, so packageId is not a global identity and de-duplicating on it silently drops
# real records.
NEW_COUNT="$(python3 - "$PKG_FILE" <<'PY'
import json, glob, sys
packages = json.load(open(sys.argv[1]))
live = {p["contentHash"] for p in packages if p.get("contentHash")}
known = set()
for path in glob.glob("docs/trader-intelligence/evidence/observations/*.json"):
    record = json.load(open(path))
    if record.get("sourceContentHash"):
        known.add(record["sourceContentHash"])
print(len(live - known))
PY
)"
say "recovered $(python3 -c "import json,sys; print(len(json.load(open('$PKG_FILE'))))") package(s); $NEW_COUNT not yet preserved as observations"

if [ "$NEW_COUNT" = "0" ]; then
  # Keeping a capture file that adds nothing just accumulates noise; the checkpoint is the
  # durable artifact and it has already been taken.
  rm -f "$PKG_FILE"
  say "no new forward evidence to import. Checkpoint retained. Done."
  exit 0
fi

# ── 5. IMPORT + RECONCILE ────────────────────────────────────────────────────────────────────
say "import: converting packages to TradeObservations ($([ $WRITE -eq 1 ] && echo WRITE || echo 'DRY RUN'))"
if [ $WRITE -eq 1 ]; then
  python3 scripts/trader_intelligence/import_mogo_observations.py --write 2>&1 | tail -20 | sed 's/^/    /'
  IMPORT_RC=${PIPESTATUS[0]}
else
  python3 scripts/trader_intelligence/import_mogo_observations.py 2>&1 | tail -20 | sed 's/^/    /'
  IMPORT_RC=${PIPESTATUS[0]}
  say "DRY RUN -- nothing written. Re-run with --write to import."
fi
[ "${IMPORT_RC:-0}" -eq 0 ] || { echo "FAIL: import step failed" >&2; exit 1; }

if [ $WRITE -eq 1 ]; then
  say "reconcile: forward population and balance relation"
  python3 -m unittest tests.trader_intelligence.test_import_mogo_observations 2>&1 | tail -3 | sed 's/^/    /'
fi

say "done."

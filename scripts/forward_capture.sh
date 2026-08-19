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

# ── ASSIMILATE ───────────────────────────────────────────────────────────────────────────────
# Called before EVERY exit, not only when new evidence arrived. Preservation and import were
# already automatic; assimilation was not, so a close became a stored record and stopped there.
#
# Unconditional on purpose. It is exactly-once by construction (the corpus fingerprint is the
# key), so on a quiet run it costs one read and records nothing -- and if a PREVIOUS run was
# interrupted between import and assimilation, this is what repairs it. Gating it on "did we
# import something this run" would leave that interruption permanently unassimilated, which is
# precisely the failure mode the exactly-once design exists to survive.
assimilate_then() {
  say "assimilate: updating research state and recording what changed"
  python3 scripts/trader_intelligence/research_assimilation.py --write 2>&1 | sed 's/^/    /'
  local rc=${PIPESTATUS[0]}
  [ "${rc:-0}" -eq 0 ] || { echo "FAIL: assimilation failed" >&2; exit 1; }
  say "done."
  exit "${1:-0}"
}

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
# "The store has not changed" is NOT "there is nothing to import". Those came apart
# the first time a DRY RUN preceded a --write run: the dry run's preserve step
# advanced the checkpoint marker, so the very next --write saw UNCHANGED, exited
# here, and never imported a close it had itself just reported as new. The cheap
# detect still earns its keep -- it decides whether a new CHECKPOINT is needed --
# but it no longer decides whether there is work to do.
UNCHANGED=0
if echo "$DETECT" | grep -q 'UNCHANGED'; then
  UNCHANGED=1
fi

# ── 2. PRESERVE ──────────────────────────────────────────────────────────────────────────────
# A verified, byte-identical copy, taken BEFORE anything is parsed. If the rest of this script
# fails, the evidence still survives -- that ordering is the whole point.
if [ $UNCHANGED -eq 1 ]; then
  say "preserve: store unchanged; reusing the most recent checkpoint"
  CKPT_DIR="$(ls -1dt "$HOME"/MOGO-EVIDENCE-PRESERVED/2026* 2>/dev/null | head -1)"
  if [ -z "$CKPT_DIR" ]; then
    say "no checkpoint exists yet and the store is unchanged; nothing to do."
    assimilate_then 0
  fi
else
  say "preserve: taking a verified checkpoint"
  CKPT_OUT="$(scripts/mogo_evidence_checkpoint.sh --profile "$PROFILE" --origin "$ORIGIN" 2>&1)"
  CKPT_RC=$?
  echo "$CKPT_OUT" | sed 's/^/    /'
  if [ $CKPT_RC -ne 0 ] && [ $CKPT_RC -ne 3 ]; then
    echo "FAIL: checkpoint failed" >&2; exit 1
  fi
  [ $CKPT_RC -eq 3 ] && say "WARNING: checkpoint is TORN (source moved mid-copy). Kept, not blessed."
  CKPT_DIR="$(echo "$CKPT_OUT" | awk '/^checkpoint    :/ {print $3}')"
fi
if [ -z "$CKPT_DIR" ]; then
  say "no new checkpoint directory was written; using the most recent one"
  CKPT_DIR="$(ls -1dt "$HOME"/MOGO-EVIDENCE-PRESERVED/2026* 2>/dev/null | head -1)"
fi
STORE="$(ls -1d "$CKPT_DIR"/IndexedDB/*.indexeddb.leveldb 2>/dev/null | head -1)"
[ -n "$STORE" ] || { echo "FAIL: no leveldb store inside $CKPT_DIR" >&2; exit 1; }

# ── 3. RECOVER ─────────────────────────────────────────────
# Full payloads, and ONLY those whose stored hash re-derives from the preserved bytes.
# Recovered to SCRATCH first. The whole store is reconstructed on every run, so writing that
# straight into evidence/ re-presents every already-preserved package as though it were a fresh
# capture. Not a duplicate-observation risk -- the importer keys on contentHash and skips them --
# but it breaks the corpus invariant that a package appears in exactly ONE capture file, and it
# grows every capture file to the size of the entire store. Caught by
# test_content_hash_is_unique_across_every_package, which is how this was found.
STAMP="$(basename "$CKPT_DIR")"
SCRATCH="${TMPDIR:-/tmp}/mogo-fwd-$$.json"
say "recover: reconstructing hash-verified packages from the checkpoint"
if ! node scripts/mogo_evidence_leveldb_extract.js --store "$STORE" --packages "$SCRATCH" 2>&1 | sed 's/^/    /'; then
  echo "FAIL: package recovery failed or a hash did not re-derive" >&2; rm -f "$SCRATCH"; exit 1
fi

# ── 4. IS ANY OF IT ACTUALLY NEW? ──────────────────────────────────
# Keyed on contentHash, never packageId: the ordinal in a packageId only counts within one
# capture run, so packageId is not a global identity and de-duplicating on it silently drops
# real records.
PKG_FILE="evidence/FWD-${STAMP}-PACKAGES.json"
# The novelty rule lives in scripts/trader_intelligence/forward_novelty.py rather
# than inline here. It used to be a heredoc, where nothing could test it, and it
# carried two defects that both reached live use. It now has its own fixtures and
# mutation coverage.
NOVELTY="$(python3 scripts/trader_intelligence/forward_novelty.py "$SCRATCH" --out "$PKG_FILE")"
NOVELTY_RC=$?
rm -f "$SCRATCH"
if [ $NOVELTY_RC -ne 0 ]; then
  echo "FAIL: novelty check refused; nothing imported" >&2; exit 1
fi
NEW_COUNT="$(echo "$NOVELTY" | awk '{print $1}')"
PENDING_COUNT="$(echo "$NOVELTY" | awk '{print $2}')"
say "store reconstructed; $NEW_COUNT fresh, $PENDING_COUNT already staged but not yet imported"

# PENDING counts as work. A package staged by a run whose import did not complete is
# invisible to a fresh-only check -- it is neither new (it is staged) nor done (it is
# not an observation) -- so every later run reported "0 new", skipped the import, and
# left a real forward close sitting in evidence/ with nothing left to notice it.
# Observed exactly once, on a GBP/JPY close.
if [ "$NEW_COUNT" = "0" ] && [ "$PENDING_COUNT" = "0" ]; then
  say "no new forward evidence to import. Checkpoint retained."
  assimilate_then 0
fi
if [ $WRITE -eq 0 ]; then
  # A dry run reports and leaves NOTHING behind. Leaving the capture file was how
  # the same package came to be staged twice.
  rm -f "$PKG_FILE"
  say "DRY RUN -- $NEW_COUNT fresh + $PENDING_COUNT pending would be imported. Nothing written."
  say "Re-run with --write to capture them."
  assimilate_then 0
fi
say "wrote $NEW_COUNT new package(s) to $PKG_FILE"

# ── 5. IMPORT + RECONCILE ────────────────────────────────────────────────────────────────────
say "import: converting packages to TradeObservations (WRITE)"
python3 scripts/trader_intelligence/import_mogo_observations.py --write 2>&1 | tail -20 | sed 's/^/    /'
IMPORT_RC=${PIPESTATUS[0]}
[ "${IMPORT_RC:-0}" -eq 0 ] || { echo "FAIL: import step failed" >&2; exit 1; }

if [ $WRITE -eq 1 ]; then
  say "reconcile: forward population and balance relation"
  python3 -m unittest tests.trader_intelligence.test_import_mogo_observations 2>&1 | tail -3 | sed 's/^/    /'
fi

assimilate_then 0

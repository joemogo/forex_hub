#!/usr/bin/env bash
#
# MOGO-016 -- install, inspect and DISABLE bounded scheduled research collection.
#
# The schedule is repository-managed: this script is the only supported way the
# launchd agent comes into existence, so the installed plist always has a
# committed origin instead of being an undocumented machine setting.
#
#   mogo_schedule.sh install                install the PRODUCTION schedule
#   mogo_schedule.sh install --at HH:MM,...  install an explicit schedule
#   mogo_schedule.sh disable                stop autonomous collection NOW
#   mogo_schedule.sh status                 is it loaded, when does it next run
#   mogo_schedule.sh logs [n]               the last n lines of both log files
#   mogo_schedule.sh validate               preflight, changing nothing
#
# `disable` is the one an operator may need in a hurry, so it is a single word,
# it needs no arguments, and it is safe to run when nothing is installed.

set -uo pipefail

LABEL="com.mogo.research.collect"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TEMPLATE="$SCRIPT_DIR/${LABEL}.plist.template"
SPEC="$SCRIPT_DIR/approved-collection.json"
AGENT_DIR="$HOME/Library/LaunchAgents"
AGENT_PLIST="$AGENT_DIR/${LABEL}.plist"
LOG_DIR="$REPO_ROOT/platform/runtime/logs"
DOMAIN="gui/$(id -u)"

# The platform floor is Python >= 3.14 and is enforced by a test. launchd's
# default PATH finds /usr/bin/python3 (3.9) first, so the interpreter is pinned
# absolutely and its version is CHECKED rather than assumed.
PYTHON="/usr/local/bin/python3"

# The production cadence, in minutes, and the wall-clock times it fires at.
# 6 hours -- justified in MOGO_016_BOUNDED_SCHEDULED_AUTONOMOUS_RESEARCH_COLLECTION.md.
PRODUCTION_TIMES="00:00,06:00,12:00,18:00"

die() { echo "ERROR: $*" >&2; exit 1; }

require_python() {
  [ -x "$PYTHON" ] || die "interpreter $PYTHON is missing or not executable.
  The launchd job names it absolutely, so a broken path here is a broken schedule."
  "$PYTHON" - <<'PY' || die "$PYTHON does not meet the platform floor (>= 3.14)."
import sys
sys.exit(0 if sys.version_info[:2] >= (3, 14) else 1)
PY
}

# MOGO-018 Step 3B: the spec is a bounded SET of entries. The installer needs ONE
# window to check against the schedule cadence, so it refuses a set whose entries
# disagree -- the same rule validate_collection_set() enforces, applied here too
# because the installer runs before the runtime ever loads the file.
spec_window_seconds() {
  "$PYTHON" -c '
import json, sys
with open(sys.argv[1], "r", encoding="utf-8") as handle:
    entries = json.load(handle).get("entries")
if not isinstance(entries, list) or not entries:
    sys.exit("collection set declares no entries")
windows = sorted({e.get("collectionWindowSeconds") for e in entries})
if len(windows) != 1:
    sys.exit("collection entries disagree on collectionWindowSeconds: %s" % (windows,))
print(windows[0])
' "$SPEC"
}

# Smallest gap, in seconds, between consecutive firings of a HH:MM list, treating
# the list as cyclic over a day.
cadence_seconds() {
  "$PYTHON" -c '
import sys
times = sorted({t.strip() for t in sys.argv[1].split(",") if t.strip()})
if not times:
    sys.exit("no times given")
minutes = []
for value in times:
    hour, _, minute = value.partition(":")
    hour, minute = int(hour), int(minute)
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        sys.exit("time %r is not a valid HH:MM" % (value,))
    minutes.append(hour * 60 + minute)
if len(minutes) == 1:
    print(24 * 60 * 60)
else:
    gaps = [b - a for a, b in zip(minutes, minutes[1:])]
    gaps.append(minutes[0] + 24 * 60 - minutes[-1])
    print(min(gaps) * 60)
' "$1"
}

calendar_entries() {
  "$PYTHON" -c '
import sys
for value in sorted({t.strip() for t in sys.argv[1].split(",") if t.strip()}):
    hour, _, minute = value.partition(":")
    print("        <dict><key>Hour</key><integer>%d</integer>"
          "<key>Minute</key><integer>%d</integer></dict>"
          % (int(hour), int(minute)))
' "$1"
}

cmd_validate() {
  local times="${1:-$PRODUCTION_TIMES}"
  echo "MOGO-016 scheduled collection -- preflight"
  echo "  repository   : $REPO_ROOT"
  require_python
  echo "  interpreter  : $PYTHON ($("$PYTHON" -V 2>&1))"
  [ -f "$TEMPLATE" ] || die "missing plist template $TEMPLATE"
  [ -f "$SPEC" ] || die "missing approved collection spec $SPEC"
  [ -f "$REPO_ROOT/platform/mogo_runtime.py" ] || \
    die "missing runtime entry point $REPO_ROOT/platform/mogo_runtime.py"

  local window cadence
  window="$(spec_window_seconds)" || die "could not read collectionWindowSeconds"
  cadence="$(cadence_seconds "$times")" || die "invalid schedule: $times"
  echo "  schedule     : $times  (cadence ${cadence}s)"
  echo "  window       : ${window}s"

  # COHERENCE. A collection window WIDER than the cadence guarantees that some
  # firings fall inside a window already collected and self-suppress -- a
  # schedule that silently does less than it says. Refused rather than
  # installed, because a schedule an operator cannot trust is worse than none.
  [ "$window" -le "$cadence" ] || die \
    "collectionWindowSeconds ($window) exceeds the schedule cadence ($cadence).
  Every firing inside one window is the same request, so this schedule would
  self-suppress. Widen the schedule or narrow the window."

  # Proves the spec validates, the destination derives, and the command builds
  # -- WITHOUT submitting anything and WITHOUT touching the network.
  echo "  dry run      :"
  "$PYTHON" "$REPO_ROOT/platform/mogo_runtime.py" collect --dry-run \
    | sed 's/^/    /' || die "the approved collection command does not build"

  # The runtime must already be initialised and authorized. The scheduled job
  # deliberately does neither -- setup is an operator act, so a wiped state root
  # fails visibly instead of being silently recreated by an unattended job.
  if [ ! -f "$REPO_ROOT/platform/runtime/index/runtime.sqlite3" ]; then
    echo "  WARNING: runtime state root is not initialised."
    echo "           Run, once, from $REPO_ROOT:"
    echo "             $PYTHON platform/mogo_runtime.py init"
    echo "             $PYTHON platform/mogo_runtime.py authorize --file \\"
    echo "               docs/trader-intelligence/authorizations/AUTH-fxalexg-metadata.json"
  fi
  echo "PREFLIGHT OK"
}

cmd_install() {
  local times="$PRODUCTION_TIMES"
  if [ "${1:-}" = "--at" ]; then
    [ -n "${2:-}" ] || die "--at needs a comma-separated HH:MM list"
    times="$2"
  elif [ -n "${1:-}" ]; then
    die "unknown argument ${1}; use: install [--at HH:MM,HH:MM,...]"
  fi

  cmd_validate "$times" || exit 1

  mkdir -p "$LOG_DIR" "$AGENT_DIR" || die "could not create $LOG_DIR"

  local calendar
  calendar="$(calendar_entries "$times")" || die "could not build the schedule"

  # Written via a temp file and moved into place, so a partial write can never
  # be loaded as a plist.
  local tmp="${AGENT_PLIST}.tmp"
  "$PYTHON" -c '
import sys
template, python, repo, logdir, calendar, out = sys.argv[1:]
with open(template, "r", encoding="utf-8") as handle:
    body = handle.read()
body = (body.replace("@@PYTHON@@", python).replace("@@REPO@@", repo)
            .replace("@@LOGDIR@@", logdir).replace("@@CALENDAR@@", calendar))
with open(out, "w", encoding="utf-8") as handle:
    handle.write(body)
' "$TEMPLATE" "$PYTHON" "$REPO_ROOT" "$LOG_DIR" "$calendar" "$tmp" \
    || die "could not render the plist"

  plutil -lint "$tmp" >/dev/null || { rm -f "$tmp"; die "rendered plist is malformed"; }
  mv "$tmp" "$AGENT_PLIST"

  launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null
  launchctl bootstrap "$DOMAIN" "$AGENT_PLIST" || die "launchctl bootstrap failed"
  launchctl enable "$DOMAIN/$LABEL" 2>/dev/null

  echo "INSTALLED $LABEL"
  echo "  plist    : $AGENT_PLIST"
  echo "  schedule : $times"
  echo "  logs     : $LOG_DIR"
  echo "  disable  : $SCRIPT_DIR/mogo_schedule.sh disable"
}

cmd_disable() {
  # Safe to run when nothing is installed; the point is that an operator who
  # wants collection stopped gets it stopped, not an error message.
  launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null
  if [ -f "$AGENT_PLIST" ]; then
    rm -f "$AGENT_PLIST"
    echo "DISABLED $LABEL -- unloaded and plist removed"
  else
    echo "DISABLED $LABEL -- nothing was installed"
  fi
  if launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1; then
    echo "WARNING: launchd still reports the job. Re-run disable." >&2
    exit 1
  fi
  echo "verified: launchd no longer knows this job; no further autonomous"
  echo "          submissions can occur. Already-collected research is untouched."
}

cmd_status() {
  echo "== schedule =="
  if [ -f "$AGENT_PLIST" ]; then
    echo "plist present: $AGENT_PLIST"
  else
    echo "plist ABSENT -- autonomous collection is not installed"
  fi
  if launchctl print "$DOMAIN/$LABEL" 2>/dev/null | \
       grep -E "state =|last exit code|runs =|program =" ; then
    :
  else
    echo "launchd: job not loaded"
  fi
  echo ""
  echo "== last scheduled run (stdout tail) =="
  [ -f "$LOG_DIR/scheduled-collection.out.log" ] \
    && tail -n 20 "$LOG_DIR/scheduled-collection.out.log" \
    || echo "(no stdout log yet)"
  echo ""
  echo "== stderr tail =="
  [ -f "$LOG_DIR/scheduled-collection.err.log" ] \
    && tail -n 20 "$LOG_DIR/scheduled-collection.err.log" \
    || echo "(no stderr log yet)"
}

cmd_logs() {
  local lines="${1:-80}"
  for name in out err; do
    echo "== scheduled-collection.${name}.log (last $lines) =="
    [ -f "$LOG_DIR/scheduled-collection.${name}.log" ] \
      && tail -n "$lines" "$LOG_DIR/scheduled-collection.${name}.log" \
      || echo "(none yet)"
    echo ""
  done
}

case "${1:-}" in
  install)  shift; cmd_install "$@" ;;
  disable|uninstall) cmd_disable ;;
  status)   cmd_status ;;
  logs)     shift; cmd_logs "$@" ;;
  validate) shift; cmd_validate "$@" ;;
  *)
    echo "usage: mogo_schedule.sh {install [--at HH:MM,...] | disable | status | logs [n] | validate}"
    exit 2
    ;;
esac

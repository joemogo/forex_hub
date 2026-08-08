#!/usr/bin/env python3
"""MOGO Automation Platform -- runtime state locations and the write guard.

AUTHORITY
    Automation Platform Constitution v1.0 (senior) -- sections 4.22, 16
    ADR-012 (accepted 2026-08-07)                  -- D-06 git-ignored storage
    MOGO-009 Architecture, section 7               -- prohibited write targets
    MOGO-011 Step 1 plan, sections 7 and 20

THE CONFINEMENT RULE
    The contracts layer performs no I/O at all and never will. The runtime
    layer is the first code in the platform permitted to write, and its licence
    is narrow: **every write must resolve inside the runtime state root.**

    Architecture section 7 forbids writing to six named targets. That rule is
    necessary but not sufficient for a runtime, because a path that is merely
    "not one of the six" could still be anywhere in the repository. This module
    inverts the test into an allowlist: a path is writable only if it resolves
    inside the state root, and every write site in the runtime calls
    assert_inside_state_root() before touching the filesystem.

    Symlinks and `..` are defeated by comparing os.path.realpath() of both the
    candidate and the root, so a symlink planted inside the state root cannot
    be used to escape it.

STATE LAYOUT
    <root>/                       default: <repo>/platform/runtime
      events/operational-events.jsonl   APPEND-ONLY, AUTHORITATIVE
      index/runtime.sqlite3             DERIVED -- rebuildable from the log
      tasks/<state>/<taskId>.json       human-readable projection, cosmetic
      quarantine/                       torn log fragments, never deleted
      runtime.lock                      single-writer exclusion

    Everything except the committed .gitignore is git-ignored (ADR-012 D-06,
    following the same nested self-ignoring pattern the campaign artifact
    directory already uses).
"""

import os

from . import errors as runtime_errors  # noqa: E402

STATE_ROOT_ENV = "MOGO_RUNTIME_STATE_ROOT"

EVENTS_DIRNAME = "events"
INDEX_DIRNAME = "index"
TASKS_DIRNAME = "tasks"
QUARANTINE_DIRNAME = "quarantine"

EVENT_LOG_FILENAME = "operational-events.jsonl"
DATABASE_FILENAME = "runtime.sqlite3"
LOCK_FILENAME = "runtime.lock"


class RuntimePaths(object):
    """Every filesystem location the runtime is permitted to touch.

    Constructed from a single root. Nothing outside `root` is addressable
    through this object, which is what makes the confinement rule checkable by
    inspection rather than by trust.
    """

    def __init__(self, root):
        self.root = os.path.abspath(root)
        self.events_dir = os.path.join(self.root, EVENTS_DIRNAME)
        self.index_dir = os.path.join(self.root, INDEX_DIRNAME)
        self.tasks_dir = os.path.join(self.root, TASKS_DIRNAME)
        self.quarantine_dir = os.path.join(self.root, QUARANTINE_DIRNAME)
        self.event_log = os.path.join(self.events_dir, EVENT_LOG_FILENAME)
        self.database = os.path.join(self.index_dir, DATABASE_FILENAME)
        self.lock_file = os.path.join(self.root, LOCK_FILENAME)

    def __repr__(self):
        return "RuntimePaths(root=%r)" % (self.root,)

    def all_directories(self):
        return (self.root, self.events_dir, self.index_dir, self.tasks_dir,
                self.quarantine_dir)

    def task_state_dir(self, state):
        """Projection directory for one task state. Validated against escape."""
        if not state or "/" in state or "\\" in state or state.startswith("."):
            runtime_errors.fail(
                "task state %r is not a safe directory component" % (state,),
                runtime_errors.PathEscapeError,
            )
        return os.path.join(self.tasks_dir, state)

    def task_projection_file(self, state, task_id):
        if not task_id or "/" in task_id or "\\" in task_id or task_id.startswith("."):
            runtime_errors.fail(
                "task id %r is not a safe filename component" % (task_id,),
                runtime_errors.PathEscapeError,
            )
        return os.path.join(self.task_state_dir(state), task_id + ".json")

    def quarantine_file(self, label):
        if not label or "/" in label or "\\" in label or label.startswith("."):
            runtime_errors.fail(
                "quarantine label %r is not a safe filename component" % (label,),
                runtime_errors.PathEscapeError,
            )
        return os.path.join(self.quarantine_dir, label)

    # -- the confinement rule ------------------------------------------------

    def is_inside_state_root(self, candidate):
        """True when `candidate` resolves inside the state root.

        Compares realpath() of both sides so that `..` traversal and symlinks
        planted inside the root cannot be used to escape it.
        """
        root_real = os.path.realpath(self.root)
        candidate_real = os.path.realpath(os.path.abspath(candidate))
        if candidate_real == root_real:
            return True
        return candidate_real.startswith(root_real + os.sep)

    def assert_inside_state_root(self, candidate, purpose="write"):
        """Raise PathEscapeError unless `candidate` is inside the state root.

        Called at EVERY write site in the runtime. Fail-closed: an unresolvable
        or outside path raises rather than being repaired or normalised.
        """
        if not self.is_inside_state_root(candidate):
            runtime_errors.fail(
                "refusing to %s outside the runtime state root: %r is not inside %r"
                % (purpose, os.path.abspath(candidate), self.root),
                runtime_errors.PathEscapeError,
            )
        return candidate


def default_root(repo_root=None):
    """The default state root: <repo>/platform/runtime.

    Overridable with MOGO_RUNTIME_STATE_ROOT, which is how every test points
    the runtime at a temporary directory instead of the real state.
    """
    override = os.environ.get(STATE_ROOT_ENV)
    if override:
        return os.path.abspath(override)
    if repo_root is None:
        # runtime/paths.py -> runtime -> mogo_platform -> src -> platform -> repo
        here = os.path.dirname(os.path.abspath(__file__))
        repo_root = os.path.abspath(os.path.join(here, "..", "..", "..", ".."))
    return os.path.join(repo_root, "platform", "runtime")


def default_paths(repo_root=None):
    return RuntimePaths(default_root(repo_root))


def ensure_state_root(paths):
    """Create the state directories. Idempotent; creates nothing outside root."""
    for directory in paths.all_directories():
        paths.assert_inside_state_root(directory, purpose="create")
        os.makedirs(directory, exist_ok=True)
    return paths

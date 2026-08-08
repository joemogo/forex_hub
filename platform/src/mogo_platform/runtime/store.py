#!/usr/bin/env python3
"""MOGO Automation Platform -- SQLite connection, transactions, process lock.

AUTHORITY
    Automation Platform Constitution v1.0 (senior) -- sections 6, 7, 11
    ADR-012 (accepted 2026-08-07)                  -- D-03, D-07 SQLite
    MOGO-011 Step 1 plan, sections 8 and 12

WHAT THIS DATABASE IS, AND IS NOT
    It is a DERIVED index and read model. It is NOT the source of truth. Every
    row in it can be reconstructed by replaying the authoritative JSONL event
    log, and `reset --rebuild-index` proves it by doing exactly that. ADR-012
    D-05: the event log is authoritative and task state is derived.

    Two tables are the exception and are marked as such: command_submissions
    and transition_anomalies record LOCAL OBSERVATIONS of attempts and
    anomalies rather than replayable facts. Both are append-only by trigger.

PRAGMAS, AND WHY THESE
    journal_mode = WAL     survives process kill; readers never block the writer
    synchronous  = FULL    durability over speed -- this is an audit store, and
                           a fast store that loses the last commit on power
                           loss would make the derived index disagree with the
                           log in exactly the situation recovery exists for
    foreign_keys = ON      tasks.command_id must reference a real command
    busy_timeout = 5000    a courtesy only; single-writer makes contention a bug

TRANSACTIONS
    Every write uses BEGIN IMMEDIATE, which takes the write lock at statement
    one. The alternative (deferred) upgrades mid-transaction and can fail after
    work has been done, which is precisely the shape of bug this kernel exists
    to avoid.

SINGLE WRITER
    An exclusive fcntl.flock on <root>/runtime.lock is held for the whole run.
    This is what makes a time-based lease unnecessary in Step 1 (plan section
    12): a lease rescues a claim held by a CONCURRENT process that died, and
    there can be no concurrent process. POSIX only -- documented constraint.
"""

import fcntl
import os
import sqlite3

from . import errors as runtime_errors  # noqa: E402

CONNECTION_PRAGMAS = (
    ("journal_mode", "WAL"),
    ("synchronous", "FULL"),
    ("foreign_keys", "ON"),
    ("busy_timeout", "5000"),
)


class ProcessLock(object):
    """Exclusive, non-blocking, whole-run lock on the runtime state root.

    Held for the entire lifetime of a runtime operation. Released by the OS if
    the process dies, which is what lets recovery assume no live claimer.
    """

    def __init__(self, paths):
        self._paths = paths
        self._path = paths.lock_file
        self._fd = None

    def acquire(self):
        self._paths.assert_inside_state_root(self._path, purpose="lock")
        fd = os.open(self._path, os.O_CREAT | os.O_RDWR, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(fd)
            runtime_errors.fail(
                "another MOGO runtime process holds %s; Step 1 is single-writer "
                "by design" % (self._path,),
                runtime_errors.RuntimeBusyError,
            )
        self._fd = fd
        return self

    def release(self):
        if self._fd is None:
            return
        try:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
        finally:
            os.close(self._fd)
            self._fd = None

    @property
    def held(self):
        return self._fd is not None

    def __enter__(self):
        return self.acquire()

    def __exit__(self, exc_type, exc, tb):
        self.release()
        return False


def open_database(paths, create=True):
    """Open the derived index with the runtime's pragmas applied.

    `create=False` refuses to bring a database into existence, which is how
    read-only commands (status, audit, verify) avoid silently creating an empty
    store and reporting "0 events" for a state root that was never initialised.
    """
    paths.assert_inside_state_root(paths.database, purpose="open database")
    if not create and not os.path.exists(paths.database):
        runtime_errors.fail(
            "no runtime database at %s -- run `init` first" % (paths.database,),
            runtime_errors.RuntimeError_,
        )
    os.makedirs(os.path.dirname(paths.database), exist_ok=True)
    connection = sqlite3.connect(paths.database, isolation_level=None)
    connection.row_factory = sqlite3.Row
    for name, value in CONNECTION_PRAGMAS:
        connection.execute("PRAGMA %s = %s" % (name, value))
    return connection


class ImmediateTransaction(object):
    """`BEGIN IMMEDIATE` … `COMMIT`, rolling back on any exception.

    Rollback is unconditional on failure. Combined with the write protocol --
    log append and fsync BEFORE the transaction -- a rolled-back transaction
    leaves the database merely behind the log, which recovery converges. It can
    never leave a half-applied transition.
    """

    def __init__(self, connection):
        self._connection = connection

    def __enter__(self):
        self._connection.execute("BEGIN IMMEDIATE")
        return self._connection

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self._connection.execute("COMMIT")
        else:
            self._connection.execute("ROLLBACK")
        return False


def immediate_transaction(connection):
    return ImmediateTransaction(connection)


def pragma(connection, name):
    row = connection.execute("PRAGMA %s" % (name,)).fetchone()
    return None if row is None else row[0]

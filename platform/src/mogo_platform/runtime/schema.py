#!/usr/bin/env python3
"""MOGO Automation Platform -- derived-index schema, triggers and migrations.

AUTHORITY
    Automation Platform Constitution v1.0 (senior) -- section 6 (append-only)
    ADR-012 (accepted 2026-08-07)                  -- D-03, D-05, D-07
    MOGO-009 Contract Catalog, sections B, C, L, O
    MOGO-011 Step 1 plan, section 8.2

APPEND-ONLY IS ENFORCED BY THE DATABASE, NOT BY CONVENTION
    event_index, command_submissions and transition_anomalies each carry
    BEFORE UPDATE and BEFORE DELETE triggers that RAISE(ABORT). Constitution
    section 6.1 says operational events are "never updated, never deleted";
    a rule enforced only by careful code is the rule most likely to break under
    time pressure (Constitution section 16), so it is enforced one layer below
    the code that would break it.

    event_index is additionally rebuildable: if it were ever lost entirely, the
    authoritative log reconstructs it. The triggers protect it from ACCIDENT,
    the log protects it from LOSS. Those are different problems.

MIGRATIONS
    MIGRATIONS is an ordered tuple of (version, callable). Startup applies every
    migration numbered above the stored version inside one BEGIN IMMEDIATE, and
    REFUSES to run when the stored version is higher than this build supports --
    a downgrade could silently drop a column a newer build depends on. Failing
    closed on an unknown-future database is the only safe direction.
"""

from . import errors as runtime_errors  # noqa: E402
from . import store  # noqa: E402

SCHEMA_VERSION = 1

# Tables whose contents may never be updated or deleted, enforced by trigger.
APPEND_ONLY_TABLES = ("event_index", "command_submissions", "transition_anomalies")

# DDL as explicit statements, not one script.
# sqlite3.executescript() issues an implicit COMMIT before running, which would
# silently end the BEGIN IMMEDIATE that initialize() opens and leave schema
# creation outside the transaction meant to make it atomic. Executing statement
# by statement keeps the whole of schema creation inside one transaction.
_CREATE_V1_STATEMENTS = (
    """CREATE TABLE schema_meta (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )""",

    # DERIVED from the authoritative JSONL log; fully rebuildable by replay.
    # log_sequence is the 1-based ordinal position of the line in the log. It is
    # NOT a field of the event envelope, so no MOGO-010 contract was changed in
    # order to obtain a global ordering.
    """CREATE TABLE event_index (
        log_sequence   INTEGER PRIMARY KEY,
        event_id       TEXT    NOT NULL UNIQUE,
        event_type     TEXT    NOT NULL,
        event_version  INTEGER NOT NULL,
        workflow_id    TEXT    NOT NULL,
        task_id        TEXT,
        correlation_id TEXT    NOT NULL,
        causation_id   TEXT    NOT NULL,
        producer       TEXT    NOT NULL,
        occurred_at    TEXT    NOT NULL,
        recorded_at    TEXT    NOT NULL,
        sequence       INTEGER NOT NULL,
        payload_hash   TEXT    NOT NULL,
        byte_offset    INTEGER NOT NULL,
        byte_length    INTEGER NOT NULL,
        UNIQUE (workflow_id, sequence)
    )""",
    """CREATE INDEX idx_event_workflow ON event_index (workflow_id, sequence)""",
    """CREATE INDEX idx_event_task ON event_index (task_id, log_sequence)""",
    """CREATE INDEX idx_event_type ON event_index (event_type, log_sequence)""",

    """CREATE TABLE commands (
        command_id            TEXT PRIMARY KEY,
        command_type          TEXT    NOT NULL,
        command_version       INTEGER NOT NULL,
        workflow_id           TEXT    NOT NULL,
        correlation_id        TEXT    NOT NULL,
        idempotency_key       TEXT    NOT NULL UNIQUE,
        target_capability     TEXT    NOT NULL,
        issued_at             TEXT    NOT NULL,
        issued_by             TEXT    NOT NULL,
        payload_hash          TEXT    NOT NULL,
        payload_json          TEXT    NOT NULL,
        accepted_log_sequence INTEGER NOT NULL,
        task_id               TEXT
    )""",
    """CREATE INDEX idx_commands_idem ON commands (idempotency_key)""",

    # APPEND-ONLY local observation: every submission attempt, including those
    # suppressed as duplicates or rejected outright. Constitution section 4.18 --
    # duplicates and rejections remain visible; silence is a defect.
    """CREATE TABLE command_submissions (
        submission_id   INTEGER PRIMARY KEY AUTOINCREMENT,
        submitted_at    TEXT NOT NULL,
        idempotency_key TEXT NOT NULL,
        command_id      TEXT,
        outcome         TEXT NOT NULL
            CHECK (outcome IN ('accepted', 'duplicate_suppressed', 'rejected')),
        reason          TEXT
    )""",
    """CREATE INDEX idx_submissions_idem
        ON command_submissions (idempotency_key, submission_id)""",

    # DERIVED read model. last_log_sequence is the exactly-once replay guard: an
    # event whose log_sequence is not greater has already been applied, which
    # makes replay idempotent without any external bookkeeping.
    """CREATE TABLE tasks (
        task_id              TEXT PRIMARY KEY,
        workflow_id          TEXT    NOT NULL,
        correlation_id       TEXT    NOT NULL,
        command_id           TEXT    NOT NULL REFERENCES commands (command_id),
        capability_id        TEXT    NOT NULL,
        idempotency_key      TEXT    NOT NULL UNIQUE,
        state                TEXT    NOT NULL,
        attempt              INTEGER NOT NULL DEFAULT 0,
        created_log_sequence INTEGER NOT NULL,
        last_log_sequence    INTEGER NOT NULL,
        terminal             INTEGER NOT NULL DEFAULT 0,
        result_hash          TEXT,
        error_class          TEXT
    )""",
    """CREATE INDEX idx_tasks_state ON tasks (state, task_id)""",

    # Catalog section O subset required for the dispatch decision.
    """CREATE TABLE capabilities (
        capability_id     TEXT PRIMARY KEY,
        name              TEXT NOT NULL,
        version           TEXT NOT NULL,
        owner             TEXT NOT NULL,
        accepted_commands TEXT NOT NULL,
        emitted_events    TEXT NOT NULL,
        lifecycle_status  TEXT NOT NULL,
        enabled_state     INTEGER NOT NULL,
        compatibility     TEXT NOT NULL,
        operation_class   TEXT NOT NULL,
        resource_limits   TEXT NOT NULL,
        manifest_hash     TEXT NOT NULL,
        registered_at     TEXT NOT NULL
    )""",

    """CREATE TABLE log_cursor (
        id                INTEGER PRIMARY KEY CHECK (id = 1),
        last_log_sequence INTEGER NOT NULL,
        last_byte_offset  INTEGER NOT NULL,
        last_event_id     TEXT
    )""",

    # APPEND-ONLY. Catalog section C: a transition arriving at a terminal task is
    # "logged as an anomaly and NOT applied".
    """CREATE TABLE transition_anomalies (
        anomaly_id   INTEGER PRIMARY KEY AUTOINCREMENT,
        detected_at  TEXT NOT NULL,
        log_sequence INTEGER NOT NULL,
        task_id      TEXT NOT NULL,
        from_state   TEXT NOT NULL,
        to_state     TEXT NOT NULL,
        reason       TEXT NOT NULL
    )""",

    # Recovery actions, for the audit report.
    """CREATE TABLE recovery_actions (
        action_id   INTEGER PRIMARY KEY AUTOINCREMENT,
        detected_at TEXT NOT NULL,
        action      TEXT NOT NULL,
        subject     TEXT,
        detail      TEXT
    )""",
)

_TRIGGER_TEMPLATES = (
    """CREATE TRIGGER %(table)s_no_update BEFORE UPDATE ON %(table)s
BEGIN
    SELECT RAISE(ABORT, '%(table)s is append-only');
END""",
    """CREATE TRIGGER %(table)s_no_delete BEFORE DELETE ON %(table)s
BEGIN
    SELECT RAISE(ABORT, '%(table)s is append-only');
END""",
)


def append_only_trigger_statements(table):
    """The two statements that make one table refuse UPDATE and DELETE."""
    return tuple(template % {"table": table} for template in _TRIGGER_TEMPLATES)


def _create_v1(connection):
    for statement in _CREATE_V1_STATEMENTS:
        connection.execute(statement)
    for table in APPEND_ONLY_TABLES:
        for statement in append_only_trigger_statements(table):
            connection.execute(statement)
    connection.execute(
        "INSERT INTO log_cursor (id, last_log_sequence, last_byte_offset, last_event_id) "
        "VALUES (1, 0, 0, NULL)"
    )


MIGRATIONS = ((1, _create_v1),)


def current_version(connection):
    """Stored schema version, or 0 when the database has never been initialised."""
    row = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_meta'"
    ).fetchone()
    if row is None:
        return 0
    value = connection.execute(
        "SELECT value FROM schema_meta WHERE key='schema_version'"
    ).fetchone()
    return 0 if value is None else int(value[0])


def initialize(connection, now):
    """Bring the database to SCHEMA_VERSION. Idempotent.

    Returns (previous_version, current_version). Applying nothing is a normal,
    reportable outcome -- `init` on an initialised state root is a no-op, not an
    error, so an operator can run it freely.
    """
    version = current_version(connection)
    if version > SCHEMA_VERSION:
        runtime_errors.fail(
            "database schema version %d is newer than this build supports (%d); "
            "refusing to operate on it" % (version, SCHEMA_VERSION),
            runtime_errors.SchemaVersionError,
        )
    if version == SCHEMA_VERSION:
        return (version, version)
    with store.immediate_transaction(connection):
        for target, migrate in MIGRATIONS:
            if target > version:
                migrate(connection)
        connection.execute(
            "INSERT OR REPLACE INTO schema_meta (key, value) VALUES (?, ?)",
            ("schema_version", str(SCHEMA_VERSION)),
        )
        connection.execute(
            "INSERT OR REPLACE INTO schema_meta (key, value) VALUES (?, ?)",
            ("created_at_utc", now),
        )
        connection.execute(
            "INSERT OR REPLACE INTO schema_meta (key, value) VALUES (?, ?)",
            ("contract_namespace", "mogo.platform.operational"),
        )
    return (version, SCHEMA_VERSION)

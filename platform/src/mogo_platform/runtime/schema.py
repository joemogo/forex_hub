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

SCHEMA_VERSION = 3

# Tables whose contents may never be updated or deleted, enforced by trigger.
APPEND_ONLY_TABLES = ("event_index", "command_submissions", "transition_anomalies",
                      "capability_violations", "acquisition_authorizations")

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


# The append-only tables that exist AT v1. Deliberately not APPEND_ONLY_TABLES:
# that tuple names every append-only table in the CURRENT schema, and a
# migration must create only the triggers for tables that exist at its own
# version. Reusing the current list here would make v1 creation fail the moment
# a later version added an append-only table -- a migration reaching forward
# into a schema it predates.
_V1_APPEND_ONLY_TABLES = ("event_index", "command_submissions",
                          "transition_anomalies")


def _create_v1(connection):
    for statement in _CREATE_V1_STATEMENTS:
        connection.execute(statement)
    for table in _V1_APPEND_ONLY_TABLES:
        for statement in append_only_trigger_statements(table):
            connection.execute(statement)
    connection.execute(
        "INSERT INTO log_cursor (id, last_log_sequence, last_byte_offset, last_event_id) "
        "VALUES (1, 0, 0, NULL)"
    )


# ---------------------------------------------------------------------------
# v2 -- MOGO-011 Step 2: retry, lease and dead-letter
# ---------------------------------------------------------------------------
# ADDITIVE ONLY. Every change below is an `ALTER TABLE ... ADD COLUMN` with a
# constant DEFAULT (supported, O(1) on this SQLite, preserves every existing
# row) or a fresh CREATE. Nothing is dropped, renamed or retyped, so a v1 state
# root upgrades in place and a v1 log replays into a v2 schema unchanged.
#
# NO DOWN-MIGRATION IS PROVIDED, DELIBERATELY. The correct rollback for a
# DERIVED index is not to un-migrate it -- it is to delete it and rebuild it
# from the authoritative log under the older build. That is stronger than a
# down-migration because it cannot half-apply, and it is the executable proof
# of ADR-012 D-05 that already exists as `reset --rebuild-index`. A
# down-migration would additionally have to drop columns, which is the one
# SQLite operation most likely to lose data on a partial failure.

_MIGRATE_V2_STATEMENTS = (
    # Catalog section C field names adopted verbatim where the Catalog names
    # them (leaseHolder, leaseExpiresAt) and Architecture section 18.1 where it
    # does (leaseGeneration). lease_acquired_at and lease_ttl_ms are added so
    # an auditor can verify an expiry decision from the log alone, without
    # knowing which build's TTL default was in force.
    "ALTER TABLE tasks ADD COLUMN attempt_limit    INTEGER NOT NULL DEFAULT 3",
    "ALTER TABLE tasks ADD COLUMN retry_policy     TEXT    NOT NULL DEFAULT '{}'",
    "ALTER TABLE tasks ADD COLUMN retry_eligible_at TEXT",
    "ALTER TABLE tasks ADD COLUMN backoff_ms       INTEGER",
    "ALTER TABLE tasks ADD COLUMN lease_holder     TEXT",
    "ALTER TABLE tasks ADD COLUMN lease_generation INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE tasks ADD COLUMN lease_acquired_at TEXT",
    "ALTER TABLE tasks ADD COLUMN lease_expires_at TEXT",
    "ALTER TABLE tasks ADD COLUMN lease_ttl_ms     INTEGER",
    "ALTER TABLE tasks ADD COLUMN dead_letter_reason TEXT",

    "ALTER TABLE commands ADD COLUMN attempt_limit INTEGER NOT NULL DEFAULT 3",

    # Restrictive defaults, so echo's committed manifest stays valid and
    # byte-identical: `pure` grants nothing, an empty failure-class list grants
    # no retryability, and no execution context means the capability receives
    # LESS information rather than more. Making any of these required would
    # change echo's manifest hash and break upgrade of every existing state root.
    "ALTER TABLE capabilities ADD COLUMN effect_class    TEXT NOT NULL DEFAULT 'pure'",
    "ALTER TABLE capabilities ADD COLUMN failure_classes TEXT NOT NULL DEFAULT '[]'",
    "ALTER TABLE capabilities ADD COLUMN requires_execution_context "
    "                                                    INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE capabilities ADD COLUMN retry_policy    TEXT NOT NULL DEFAULT '{}'",

    # DERIVED and rebuildable: one row per completed execution, inserted whole
    # when the outcome event is applied. UNIQUE (task_id, attempt) is not
    # decoration -- it is a second, INDEPENDENT guard against an attempt being
    # recorded twice, so a double count cannot be silent even if its test were
    # removed.
    """CREATE TABLE task_attempts (
        attempt_id            INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id               TEXT    NOT NULL REFERENCES tasks (task_id),
        attempt               INTEGER NOT NULL,
        lease_generation      INTEGER NOT NULL,
        started_log_sequence  INTEGER NOT NULL,
        finished_log_sequence INTEGER NOT NULL,
        outcome               TEXT    NOT NULL
            CHECK (outcome IN ('succeeded', 'failed')),
        error_class           TEXT,
        result_hash           TEXT,
        started_at            TEXT    NOT NULL,
        finished_at           TEXT    NOT NULL,
        UNIQUE (task_id, attempt)
    )""",

    # LOCAL OBSERVATION, not replayable truth: which run held which lease.
    # Useful for audit, meaningless to replay. Named here rather than quietly
    # counted as rebuildable -- a table holding non-rebuildable truth while the
    # design claimed full rebuildability is exactly the drift ADR-012 D-05
    # exists to prevent.
    """CREATE TABLE runs (
        run_id     TEXT PRIMARY KEY,
        started_at TEXT NOT NULL,
        ended_at   TEXT,
        pid        INTEGER NOT NULL
    )""",

    # APPEND-ONLY local observation. Constitution section 7: a worker may not
    # emit an event it has not declared. A capability raising an undeclared
    # failure class is recorded here and the task fails non-retryably.
    """CREATE TABLE capability_violations (
        violation_id  INTEGER PRIMARY KEY AUTOINCREMENT,
        detected_at   TEXT NOT NULL,
        capability_id TEXT NOT NULL,
        task_id       TEXT,
        violation     TEXT NOT NULL,
        detail        TEXT
    )""",

    "CREATE INDEX idx_tasks_retry    ON tasks (state, retry_eligible_at)",
    "CREATE INDEX idx_tasks_lease    ON tasks (lease_expires_at)",
    "CREATE INDEX idx_attempts_task  ON task_attempts (task_id, attempt)",
    "CREATE INDEX idx_attempts_error ON task_attempts (error_class, attempt_id)",
)


def _migrate_v2(connection):
    for statement in _MIGRATE_V2_STATEMENTS:
        connection.execute(statement)
    for statement in append_only_trigger_statements("capability_violations"):
        connection.execute(statement)


# ---------------------------------------------------------------------------
# v3 -- MOGO-011 Step 3: the policy gate
# ---------------------------------------------------------------------------
# ADDITIVE ONLY, on the same terms as v2. Every task column below is COPIED
# from an event payload, never computed at projection time, so the whole index
# stays rebuildable from the log alone.
#
# acquisition_authorizations is the one exception, and it is named rather than
# hidden: it holds governance INPUT, not platform history, so it is a LOCAL
# OBSERVATION alongside `capabilities` and `runs`. Replay determinism is
# preserved by recording the DECISION -- every gate decision event carries the
# authorization's identity, status, policy version, authority and content hash
# as they stood at decision time, so a later edit cannot rewrite history.

_MIGRATE_V3_STATEMENTS = (
    # The gate's verdict, as recorded. `policy_decision` is the value the
    # dispatch guard reads before an acquisition-class task may be claimed, so
    # a hand-corrupted index row still cannot execute unauthorized acquisition.
    "ALTER TABLE tasks ADD COLUMN policy_decision   TEXT",
    "ALTER TABLE tasks ADD COLUMN policy_reason     TEXT",
    "ALTER TABLE tasks ADD COLUMN policy_status     TEXT",
    "ALTER TABLE tasks ADD COLUMN policy_version    TEXT",
    "ALTER TABLE tasks ADD COLUMN authorization_id  TEXT",
    "ALTER TABLE tasks ADD COLUMN operation_class   TEXT",
    "ALTER TABLE tasks ADD COLUMN subject_source_id TEXT",
    "ALTER TABLE tasks ADD COLUMN review_decision   TEXT",
    "ALTER TABLE tasks ADD COLUMN review_reason     TEXT",
    "ALTER TABLE tasks ADD COLUMN reviewer_identity TEXT",

    # Catalog section A: inputRefs carries identifiers only, "never inline
    # payloads". The policy gate resolves the subject source from here, so it
    # must be projected rather than re-read from the log on every decision.
    "ALTER TABLE commands ADD COLUMN input_refs_json TEXT NOT NULL DEFAULT '[]'",

    # Restrictive default: a capability that declares no acquisition operations
    # can acquire nothing, which is the safe direction for every manifest that
    # predates this column.
    "ALTER TABLE capabilities ADD COLUMN acquisition_operations "
    "                                              TEXT NOT NULL DEFAULT '[]'",

    # APPEND-ONLY. Governance input. Never updated, never deleted: a correction
    # is a NEW record naming the one it replaces, which is Constitution section
    # 6.7's discipline. Supersession is DERIVED by query, never stamped, which
    # is what lets this table stay append-only while still expressing
    # replacement.
    """CREATE TABLE acquisition_authorizations (
        authorization_id           TEXT PRIMARY KEY,
        source_id                  TEXT NOT NULL,
        policy_status              TEXT NOT NULL,
        policy_version             TEXT NOT NULL,
        decision_authority         TEXT NOT NULL,
        decided_at                 TEXT NOT NULL,
        permitted_operations       TEXT NOT NULL,
        expires_at                 TEXT,
        supersedes_authorization_id TEXT,
        record_json                TEXT NOT NULL,
        record_hash                TEXT NOT NULL,
        recorded_at                TEXT NOT NULL
    )""",

    # DERIVED and rebuildable: one row per gate decision, reconstructed from
    # PolicyEvaluated events. This is what lets an operator answer "what was
    # blocked, when, and under which policy version" without reading the log by
    # hand -- Constitution section 13.
    """CREATE TABLE policy_decisions (
        decision_id      INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id          TEXT    NOT NULL REFERENCES tasks (task_id),
        log_sequence     INTEGER NOT NULL,
        decided_at       TEXT    NOT NULL,
        decision         TEXT    NOT NULL
            CHECK (decision IN ('permit', 'not_applicable', 'deny')),
        reason           TEXT    NOT NULL,
        operation_class  TEXT,
        requested_operations TEXT,
        subject_source_id TEXT,
        authorization_id TEXT,
        policy_status    TEXT,
        policy_version   TEXT,
        record_hash      TEXT,
        UNIQUE (task_id, log_sequence)
    )""",

    "CREATE INDEX idx_authorizations_source ON acquisition_authorizations (source_id)",
    "CREATE INDEX idx_authorizations_super  ON acquisition_authorizations "
    "                                          (supersedes_authorization_id)",
    "CREATE INDEX idx_policy_decisions_task ON policy_decisions (task_id, log_sequence)",
    "CREATE INDEX idx_policy_decisions_kind ON policy_decisions (decision, reason)",
    "CREATE INDEX idx_tasks_policy          ON tasks (policy_decision, state)",
)


def _migrate_v3(connection):
    for statement in _MIGRATE_V3_STATEMENTS:
        connection.execute(statement)
    for statement in append_only_trigger_statements("acquisition_authorizations"):
        connection.execute(statement)


MIGRATIONS = ((1, _create_v1), (2, _migrate_v2), (3, _migrate_v3))


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

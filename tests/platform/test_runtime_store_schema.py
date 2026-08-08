#!/usr/bin/env python3
"""MOGO-011 Step 1 -- store, schema, triggers and process-lock tests.

Pure stdlib (unittest). Fully offline, deterministic, repeatable. Every test
operates on a tempfile state root and NEVER on the real platform/runtime.

Run with:
    python3 -m unittest tests.platform.test_runtime_store_schema -v
"""

import os
import sqlite3
import sys
import tempfile
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC_DIR = os.path.join(REPO_ROOT, "platform", "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from mogo_platform.runtime import errors as runtime_errors  # noqa: E402
from mogo_platform.runtime import paths as paths_module  # noqa: E402
from mogo_platform.runtime import schema as schema_module  # noqa: E402
from mogo_platform.runtime import store  # noqa: E402

# Independently transcribed from the Step 1 plan section 8.2.
EXPECTED_TABLES = (
    "capabilities", "command_submissions", "commands", "event_index",
    "log_cursor", "recovery_actions", "schema_meta", "tasks",
    "transition_anomalies",
)
EXPECTED_APPEND_ONLY_TABLES = ("event_index", "command_submissions",
                               "transition_anomalies")
EXPECTED_INDEXES = (
    "idx_commands_idem", "idx_event_task", "idx_event_type", "idx_event_workflow",
    "idx_submissions_idem", "idx_tasks_state",
)


class RuntimeStateCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.paths = paths_module.ensure_state_root(
            paths_module.RuntimePaths(os.path.join(self._tmp.name, "state")))

    def tearDown(self):
        self._tmp.cleanup()

    def open(self):
        connection = store.open_database(self.paths)
        schema_module.initialize(connection, "2026-08-07T00:00:00.000Z")
        return connection


class TestDatabaseCreation(RuntimeStateCase):
    def test_database_creation_is_deterministic(self):
        first = self.open()
        names = sorted(r[0] for r in first.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%'"))
        first.close()
        os.remove(self.paths.database)
        second = self.open()
        again = sorted(r[0] for r in second.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%'"))
        second.close()
        self.assertEqual(names, again)
        self.assertEqual(tuple(names), EXPECTED_TABLES)

    def test_every_expected_index_exists(self):
        connection = self.open()
        names = sorted(r[0] for r in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND name NOT LIKE 'sqlite_%'"))
        connection.close()
        self.assertEqual(tuple(names), EXPECTED_INDEXES)

    def test_schema_version_is_recorded(self):
        connection = self.open()
        value = connection.execute(
            "SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()[0]
        connection.close()
        self.assertEqual(int(value), schema_module.SCHEMA_VERSION)
        self.assertEqual(schema_module.SCHEMA_VERSION, 1)

    def test_initialize_is_idempotent(self):
        connection = self.open()
        before, after = schema_module.initialize(connection, "2026-08-07T00:00:00.000Z")
        self.assertEqual((before, after), (1, 1))
        count = connection.execute("SELECT COUNT(*) FROM log_cursor").fetchone()[0]
        connection.close()
        self.assertEqual(count, 1)

    def test_migration_refuses_a_newer_schema_version(self):
        connection = self.open()
        connection.execute(
            "UPDATE schema_meta SET value='99' WHERE key='schema_version'")
        with self.assertRaises(runtime_errors.SchemaVersionError):
            schema_module.initialize(connection, "2026-08-07T00:00:00.000Z")
        connection.close()

    def test_current_version_is_zero_before_initialization(self):
        connection = store.open_database(self.paths)
        self.assertEqual(schema_module.current_version(connection), 0)
        connection.close()

    def test_pragmas_are_applied(self):
        connection = self.open()
        self.assertEqual(str(store.pragma(connection, "journal_mode")).lower(), "wal")
        self.assertEqual(int(store.pragma(connection, "synchronous")), 2)  # FULL
        self.assertEqual(int(store.pragma(connection, "foreign_keys")), 1)
        connection.close()

    def test_open_database_refuses_to_create_when_asked_not_to(self):
        with self.assertRaises(runtime_errors.RuntimeError_):
            store.open_database(self.paths, create=False)


class TestAppendOnlyTriggers(RuntimeStateCase):
    def _seed_event(self, connection):
        connection.execute(
            "INSERT INTO event_index (log_sequence, event_id, event_type,"
            " event_version, workflow_id, task_id, correlation_id, causation_id,"
            " producer, occurred_at, recorded_at, sequence, payload_hash,"
            " byte_offset, byte_length) VALUES (1,'e','T',1,'w',NULL,'c','c',"
            "'orchestrator','t','t',0,'h',0,10)")

    def test_append_only_table_list_matches_the_plan(self):
        self.assertEqual(tuple(sorted(schema_module.APPEND_ONLY_TABLES)),
                         tuple(sorted(EXPECTED_APPEND_ONLY_TABLES)))

    def test_event_index_rejects_update(self):
        connection = self.open()
        self._seed_event(connection)
        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute("UPDATE event_index SET event_type='X'")
        connection.close()

    def test_event_index_rejects_delete(self):
        connection = self.open()
        self._seed_event(connection)
        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute("DELETE FROM event_index")
        connection.close()

    def test_command_submissions_rejects_update_and_delete(self):
        connection = self.open()
        connection.execute(
            "INSERT INTO command_submissions (submitted_at, idempotency_key,"
            " command_id, outcome, reason) VALUES ('t','k',NULL,'accepted',NULL)")
        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute("UPDATE command_submissions SET outcome='rejected'")
        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute("DELETE FROM command_submissions")
        connection.close()

    def test_transition_anomalies_rejects_update_and_delete(self):
        connection = self.open()
        connection.execute(
            "INSERT INTO transition_anomalies (detected_at, log_sequence, task_id,"
            " from_state, to_state, reason) VALUES ('t',1,'x','a','b','r')")
        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute("UPDATE transition_anomalies SET reason='z'")
        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute("DELETE FROM transition_anomalies")
        connection.close()

    def test_command_submissions_rejects_an_unapproved_outcome(self):
        connection = self.open()
        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO command_submissions (submitted_at, idempotency_key,"
                " command_id, outcome, reason) VALUES ('t','k',NULL,'maybe',NULL)")
        connection.close()


class TestTransactions(RuntimeStateCase):
    def test_rollback_leaves_no_partial_state(self):
        connection = self.open()
        try:
            with store.immediate_transaction(connection):
                connection.execute(
                    "INSERT INTO capabilities (capability_id, name, version, owner,"
                    " accepted_commands, emitted_events, lifecycle_status,"
                    " enabled_state, compatibility, operation_class, resource_limits,"
                    " manifest_hash, registered_at) VALUES "
                    "('CAP|a|b','n','1','o','[]','[]','production',1,'{}','x','{}',"
                    "'h','t')")
                raise ValueError("induced")
        except ValueError:
            pass
        count = connection.execute("SELECT COUNT(*) FROM capabilities").fetchone()[0]
        connection.close()
        self.assertEqual(count, 0)

    def test_commit_persists(self):
        connection = self.open()
        with store.immediate_transaction(connection):
            connection.execute(
                "INSERT INTO recovery_actions (detected_at, action, subject, detail)"
                " VALUES ('t','a','s','d')")
        count = connection.execute(
            "SELECT COUNT(*) FROM recovery_actions").fetchone()[0]
        connection.close()
        self.assertEqual(count, 1)


class TestProcessLock(RuntimeStateCase):
    def test_lock_is_acquired_and_released(self):
        lock = store.ProcessLock(self.paths)
        lock.acquire()
        self.assertTrue(lock.held)
        lock.release()
        self.assertFalse(lock.held)

    def test_second_lock_cannot_be_acquired(self):
        first = store.ProcessLock(self.paths).acquire()
        try:
            with self.assertRaises(runtime_errors.RuntimeBusyError):
                store.ProcessLock(self.paths).acquire()
        finally:
            first.release()

    def test_lock_is_reusable_after_release(self):
        store.ProcessLock(self.paths).acquire().release()
        second = store.ProcessLock(self.paths).acquire()
        self.assertTrue(second.held)
        second.release()


class TestPathConfinement(RuntimeStateCase):
    def test_paths_inside_the_root_are_accepted(self):
        for candidate in self.paths.all_directories() + (
                self.paths.event_log, self.paths.database, self.paths.lock_file):
            self.assertTrue(self.paths.is_inside_state_root(candidate), candidate)

    def test_paths_outside_the_root_are_refused(self):
        for candidate in ("/etc/passwd", REPO_ROOT,
                          os.path.join(REPO_ROOT, "index.html"),
                          os.path.join(self.paths.root, "..", "escape.txt")):
            with self.subTest(candidate=candidate):
                self.assertFalse(self.paths.is_inside_state_root(candidate))
                with self.assertRaises(runtime_errors.PathEscapeError):
                    self.paths.assert_inside_state_root(candidate)

    def test_dot_dot_traversal_cannot_escape(self):
        with self.assertRaises(runtime_errors.PathEscapeError):
            self.paths.assert_inside_state_root(
                os.path.join(self.paths.events_dir, "..", "..", "outside"))

    def test_symlink_inside_the_root_cannot_escape(self):
        outside = os.path.join(os.path.dirname(self.paths.root), "outside")
        os.makedirs(outside, exist_ok=True)
        link = os.path.join(self.paths.root, "sneaky")
        os.symlink(outside, link)
        with self.assertRaises(runtime_errors.PathEscapeError):
            self.paths.assert_inside_state_root(os.path.join(link, "f.txt"))

    def test_unsafe_component_is_refused(self):
        for bad in ("../evil", "a/b", ".hidden", ""):
            with self.subTest(bad=bad):
                with self.assertRaises(runtime_errors.PathEscapeError):
                    self.paths.task_projection_file("queued", bad)
                with self.assertRaises(runtime_errors.PathEscapeError):
                    self.paths.task_state_dir(bad)

    def test_state_root_env_override_is_honoured(self):
        previous = os.environ.get(paths_module.STATE_ROOT_ENV)
        os.environ[paths_module.STATE_ROOT_ENV] = self.paths.root
        try:
            self.assertEqual(paths_module.default_paths().root, self.paths.root)
        finally:
            if previous is None:
                del os.environ[paths_module.STATE_ROOT_ENV]
            else:
                os.environ[paths_module.STATE_ROOT_ENV] = previous


if __name__ == "__main__":
    unittest.main(verbosity=2)

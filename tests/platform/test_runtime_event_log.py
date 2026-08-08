#!/usr/bin/env python3
"""MOGO-011 Step 1 -- authoritative event-log tests.

Pure stdlib (unittest). Offline, deterministic, repeatable. Operates on a
tempfile state root and never on the real platform/runtime.

The log is the source of truth, so these are the most consequential tests in
the step: durability, append-only behaviour, ordering, hash verification, and
the precise distinction between an interrupted append (recoverable) and
corruption of committed history (halt).

Run with:
    python3 -m unittest tests.platform.test_runtime_event_log -v
"""

import json
import os
import sys
import tempfile
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC_DIR = os.path.join(REPO_ROOT, "platform", "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from mogo_platform.contracts import ids  # noqa: E402
from mogo_platform.runtime import errors as runtime_errors  # noqa: E402
from mogo_platform.runtime import event_log as event_log_module  # noqa: E402
from mogo_platform.runtime import paths as paths_module  # noqa: E402

UUIDS = ("3f2504e0-4f89-41d3-9a0c-0305e82c3301",
         "7d444840-9dc0-41d2-b1a6-6f1d1d1a1a1a",
         "16fd2706-8baf-433b-82eb-8c7fada847da",
         "1b4e28ba-2fa1-489f-a9fd-2b0e6b6f7c33",
         "886313e1-3b8a-45f6-8dd5-9a1b2c3d4e5f")
STAMP = "2026-08-07T12:34:56.789Z"


def make_event(sequence, workflow=UUIDS[1], event_type="TaskSucceeded",
               payload=None, event_id=None):
    payload = {"n": sequence} if payload is None else payload
    return {
        "eventId": event_id or ids.new_uuid4(),
        "eventType": event_type,
        "eventVersion": 1,
        "workflowId": workflow,
        "correlationId": UUIDS[2],
        "causationId": UUIDS[3],
        "producer": "orchestrator",
        "producerVersion": "1.0.0",
        "occurredAt": STAMP,
        "recordedAt": STAMP,
        "subjectRefs": [],
        "payload": payload,
        "payloadHash": ids.content_hash_of(payload),
        "sequence": sequence,
    }


class EventLogCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.paths = paths_module.ensure_state_root(
            paths_module.RuntimePaths(os.path.join(self._tmp.name, "state")))
        self.log = event_log_module.EventLog(self.paths)

    def tearDown(self):
        self._tmp.cleanup()

    def append_many(self, count, workflow=UUIDS[1]):
        return [self.log.append(make_event(index, workflow))
                for index in range(count)]


class TestAppend(EventLogCase):
    def test_append_returns_monotonic_log_sequence(self):
        records = self.append_many(5)
        self.assertEqual([r.log_sequence for r in records], [1, 2, 3, 4, 5])

    def test_append_writes_one_newline_terminated_line_each(self):
        self.append_many(3)
        with open(self.log.path, "rb") as handle:
            raw = handle.read()
        self.assertTrue(raw.endswith(b"\n"))
        self.assertEqual(raw.count(b"\n"), 3)

    def test_appended_line_is_canonical_json(self):
        record = self.log.append(make_event(0))
        with open(self.log.path, "rb") as handle:
            line = handle.read().rstrip(b"\n")
        self.assertEqual(line, ids.canonical_json_bytes(record.event))

    def test_append_validates_through_the_mogo010_contract(self):
        broken = make_event(0)
        del broken["payloadHash"]
        with self.assertRaises(runtime_errors.ContractValidationError):
            self.log.append(broken)
        self.assertEqual(self.log.size_bytes(), 0)

    def test_append_rejects_a_bad_payload_hash_before_writing(self):
        broken = make_event(0)
        broken["payloadHash"] = "c" * 64
        with self.assertRaises(runtime_errors.ContractValidationError):
            self.log.append(broken)
        self.assertEqual(self.log.size_bytes(), 0)

    def test_append_rejects_a_prohibited_scientific_reference(self):
        with self.assertRaises(runtime_errors.PlatformError):
            self.log.append(make_event(0, payload={"target": "evidence/x.json"}))
        self.assertEqual(self.log.size_bytes(), 0)

    def test_append_calls_fsync_before_returning(self):
        """STRUCTURAL, and deliberately so -- state the limit rather than fake it.

        fsync only matters when the machine loses power or the kernel dies. A
        Python test cannot induce either: os._exit() leaves the page cache
        intact, so a log written WITHOUT fsync still reads back correctly in
        every crash test in this repository. Behavioural testing therefore
        cannot distinguish a durable append from a merely-written one.

        The durability guarantee is real and load-bearing -- append() promises
        that a returned LogRecord survives power loss -- so it is asserted the
        only way it can be: structurally, by proving the call is present in the
        function that makes the promise. A mutation run confirmed that without
        this test, deleting os.fsync passes every other test in the suite.
        """
        import ast
        import inspect
        import textwrap
        # getsource() on a METHOD returns it at class indentation, which
        # ast.parse rejects. dedent first, or the test errors instead of
        # asserting -- which would make it look like it was catching things.
        tree = ast.parse(textwrap.dedent(
            inspect.getsource(event_log_module.EventLog.append)))
        fsync_calls = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "fsync"
        ]
        self.assertEqual(len(fsync_calls), 1,
                         "EventLog.append must fsync exactly once before returning")

    def test_quarantine_write_is_fsynced_before_the_log_is_truncated(self):
        """Same reasoning: the copy must be durable BEFORE the log shortens."""
        import ast
        import inspect
        import textwrap
        source = textwrap.dedent(
            inspect.getsource(event_log_module.EventLog.repair_torn_tail))
        tree = ast.parse(source)
        calls = [n for n in ast.walk(tree)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)]
        names = [n.func.attr for n in calls]
        self.assertIn("fsync", names)
        self.assertIn("replace", names)
        self.assertIn("ftruncate", names)
        # The quarantine copy is renamed into place before the truncation.
        self.assertLess(names.index("replace"), names.index("ftruncate"))

    def test_byte_offsets_are_contiguous(self):
        records = self.append_many(4)
        expected = 0
        for record in records:
            self.assertEqual(record.byte_offset, expected)
            expected += record.byte_length
        self.assertEqual(expected, self.log.size_bytes())


class TestScanAndVerify(EventLogCase):
    def test_scan_returns_every_record_in_order(self):
        self.append_many(6)
        result = self.log.scan()
        self.assertEqual(len(result.records), 6)
        self.assertEqual([r.log_sequence for r in result.records], list(range(1, 7)))
        self.assertIsNone(result.torn_fragment)

    def test_scan_on_a_missing_log_is_empty(self):
        self.assertEqual(self.log.scan().records, [])

    def test_event_identifiers_are_valid_uuid4(self):
        self.append_many(3)
        for record in self.log.scan().records:
            self.assertTrue(ids.is_uuid4(record.event_id))

    def test_payload_hash_verifies_for_every_event(self):
        self.append_many(3)
        for record in self.log.scan().records:
            self.assertEqual(ids.content_hash_of(record.event["payload"]),
                             record.event["payloadHash"])

    def test_verify_is_clean_for_a_well_formed_log(self):
        self.append_many(4)
        self.assertEqual(self.log.verify(), [])

    def test_sequence_must_be_monotonic_within_a_workflow(self):
        self.log.append(make_event(0))
        self.log.append(make_event(1))
        self.log.append(make_event(5))          # gap
        findings = self.log.verify()
        self.assertTrue(any("expected sequence" in f["finding"] for f in findings))

    def test_two_workflows_have_independent_sequences(self):
        self.log.append(make_event(0, workflow=UUIDS[1]))
        self.log.append(make_event(0, workflow=UUIDS[4]))
        self.log.append(make_event(1, workflow=UUIDS[1]))
        self.assertEqual(self.log.verify(), [])

    def test_duplicate_event_id_is_reported(self):
        shared = ids.new_uuid4()
        self.log.append(make_event(0, event_id=shared))
        self.log.append(make_event(1, event_id=shared))
        findings = self.log.verify()
        self.assertTrue(any("duplicate eventId" in f["finding"] for f in findings))

    def test_next_sequence_for_workflow(self):
        self.append_many(3)
        self.assertEqual(self.log.next_sequence_for_workflow(UUIDS[1]), 3)
        self.assertEqual(self.log.next_sequence_for_workflow(UUIDS[4]), 0)


class TestCorruptionHalts(EventLogCase):
    """Committed history is never skipped, repaired or truncated."""

    def _corrupt_line(self, index, replacement):
        with open(self.log.path, "rb") as handle:
            lines = handle.read().split(b"\n")
        lines[index] = replacement
        with open(self.log.path, "wb") as handle:
            handle.write(b"\n".join(lines))

    def test_mid_file_unparsable_line_halts(self):
        self.append_many(4)
        self._corrupt_line(1, b"{not json")
        with self.assertRaises(runtime_errors.LogCorruptionError):
            self.log.scan()

    def test_mid_file_payload_hash_mismatch_halts(self):
        self.append_many(4)
        with open(self.log.path, "rb") as handle:
            lines = handle.read().split(b"\n")
        event = json.loads(lines[1].decode("utf-8"))
        event["payload"] = {"tampered": True}      # hash no longer matches
        self._corrupt_line(1, ids.canonical_json_bytes(event))
        with self.assertRaises(runtime_errors.LogCorruptionError):
            self.log.scan()

    def test_mid_file_corruption_mutates_nothing(self):
        self.append_many(4)
        self._corrupt_line(1, b"{not json")
        before = self.log.size_bytes()
        with self.assertRaises(runtime_errors.LogCorruptionError):
            self.log.repair_torn_tail("2026-08-07T00:00:00.000Z")
        self.assertEqual(self.log.size_bytes(), before)

    def test_verify_reports_corruption_as_fatal(self):
        self.append_many(3)
        self._corrupt_line(0, b"{not json")
        findings = self.log.verify()
        self.assertEqual(findings[0]["severity"], "FATAL")


class TestTornTail(EventLogCase):
    """An interrupted append is not corruption: it never became an event."""

    def _tear(self, fragment=b'{"eventId": "partial'):
        with open(self.log.path, "ab") as handle:
            handle.write(fragment)

    def test_torn_tail_is_detected(self):
        self.append_many(3)
        self._tear()
        result = self.log.scan()
        self.assertIsNotNone(result.torn_fragment)
        self.assertEqual(len(result.records), 3)

    def test_torn_tail_is_reported_by_verify_as_a_warning_not_a_fatal(self):
        self.append_many(2)
        self._tear()
        findings = self.log.verify()
        self.assertEqual([f["severity"] for f in findings], ["WARNING"])

    def test_torn_tail_is_quarantined_not_deleted(self):
        self.append_many(2)
        self._tear(b'{"partial": tru')
        target = self.log.repair_torn_tail("2026-08-07T00:00:00.000Z")
        self.assertIsNotNone(target)
        self.assertTrue(os.path.exists(target))
        with open(target, "rb") as handle:
            self.assertEqual(handle.read(), b'{"partial": tru')

    def test_quarantine_lands_inside_the_state_root(self):
        self.append_many(1)
        self._tear()
        target = self.log.repair_torn_tail("2026-08-07T00:00:00.000Z")
        self.assertTrue(self.paths.is_inside_state_root(target))

    def test_truncation_preserves_every_valid_event(self):
        records = self.append_many(3)
        digests = [r.event_id for r in records]
        self._tear()
        self.log.repair_torn_tail("2026-08-07T00:00:00.000Z")
        after = self.log.scan()
        self.assertEqual([r.event_id for r in after.records], digests)
        self.assertIsNone(after.torn_fragment)

    def test_repair_is_a_no_op_on_a_clean_log(self):
        self.append_many(2)
        self.assertIsNone(self.log.repair_torn_tail("2026-08-07T00:00:00.000Z"))

    def test_a_complete_but_invalid_final_line_is_treated_as_torn(self):
        self.append_many(2)
        with open(self.log.path, "ab") as handle:
            handle.write(b'{"eventId": "not-a-uuid"}\n')
        result = self.log.scan()
        self.assertIsNotNone(result.torn_fragment)
        self.assertEqual(len(result.records), 2)

    def test_a_log_that_is_only_a_fragment_yields_no_records(self):
        with open(self.log.path, "wb") as handle:
            handle.write(b'{"partial"')
        result = self.log.scan()
        self.assertEqual(result.records, [])
        self.assertIsNotNone(result.torn_fragment)

    def test_appending_after_repair_continues_the_sequence(self):
        self.append_many(2)
        self._tear()
        self.log.repair_torn_tail("2026-08-07T00:00:00.000Z")
        record = self.log.append(make_event(2))
        self.assertEqual(record.log_sequence, 3)
        self.assertEqual(self.log.verify(), [])


class TestLogIsNeverRewritten(EventLogCase):
    def test_earlier_bytes_are_never_modified_by_later_appends(self):
        self.log.append(make_event(0))
        with open(self.log.path, "rb") as handle:
            first_line = handle.read()
        self.append_many(3)
        with open(self.log.path, "rb") as handle:
            self.assertTrue(handle.read().startswith(first_line))

    def test_module_exposes_no_delete_or_update_helper(self):
        forbidden = ("delete", "update", "rewrite", "remove", "patch", "edit")
        offenders = [name for name in dir(event_log_module)
                     if not name.startswith("_")
                     and callable(getattr(event_log_module, name))
                     and any(word in name.lower() for word in forbidden)]
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)

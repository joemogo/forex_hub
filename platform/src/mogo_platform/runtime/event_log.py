#!/usr/bin/env python3
"""MOGO Automation Platform -- the authoritative append-only event log.

AUTHORITY
    Automation Platform Constitution v1.0 (senior) -- section 6 in full
    ADR-012 (accepted 2026-08-07)                  -- D-04, D-05, D-07
    MOGO-009 Architecture, sections 11, 18.1, 24
    MOGO-011 Step 1 plan, sections 7, 8.3, 13.2

THIS FILE IS THE SOURCE OF TRUTH
    Everything in the SQLite index is derived from this log and can be rebuilt
    from it. Nothing here is derived from anything. ADR-012 approval 6 and D-04
    chose append-only JSONL over a database for exactly this property: the
    history is greppable, archivable, and cannot be silently rewritten by a
    query.

DURABILITY CONTRACT
    An event is COMMITTED when, and only when, its complete newline-terminated
    line is durable on disk. append() performs one os.write() of the whole line
    followed by os.fsync(), and returns only after both succeed. A caller that
    receives a LogRecord may rely on the event surviving power loss.

    That definition is what makes torn-tail handling honest: a fragment that
    was never newline-terminated never became an event, so quarantining and
    truncating it destroys no history. See repair_torn_tail().

GLOBAL ORDERING WITHOUT A CONTRACT CHANGE
    Events carry a per-workflow `sequence` (Catalog section B) but no global
    ordinal. Rather than add a field to a committed MOGO-010 envelope, the
    global order is the line's 1-based position in this file. Position is a
    property of the log, not of the event, so the contract is untouched and the
    ordering is impossible to forge independently of the bytes.

WHAT THIS MODULE WILL NOT DO
    It will not rewrite a line, reorder lines, delete a committed line, or
    truncate anywhere except an unterminated tail. A hash mismatch or parse
    failure away from the tail raises LogCorruptionError and the runtime halts.
"""

import os

from ..contracts import event as event_contract  # noqa: E402
from ..contracts import ids  # noqa: E402
from . import errors as runtime_errors  # noqa: E402


class LogRecord(object):
    """One committed event, with its position in the log.

    `log_sequence` is the 1-based line ordinal and is assigned by the log, not
    carried in the envelope.
    """

    __slots__ = ("log_sequence", "byte_offset", "byte_length", "event")

    def __init__(self, log_sequence, byte_offset, byte_length, event):
        self.log_sequence = log_sequence
        self.byte_offset = byte_offset
        self.byte_length = byte_length
        self.event = event

    @property
    def event_id(self):
        return self.event["eventId"]

    @property
    def event_type(self):
        return self.event["eventType"]

    def __repr__(self):
        return "LogRecord(seq=%d, type=%s, id=%s)" % (
            self.log_sequence, self.event_type, self.event_id)


class ScanResult(object):
    """Outcome of reading the whole log.

    `torn_fragment` is the trailing bytes that never became an event, or None.
    """

    __slots__ = ("records", "torn_fragment", "valid_byte_length")

    def __init__(self, records, torn_fragment, valid_byte_length):
        self.records = records
        self.torn_fragment = torn_fragment
        self.valid_byte_length = valid_byte_length


class EventLog(object):
    """Append-only JSONL event log."""

    def __init__(self, paths):
        self._paths = paths
        self._path = paths.event_log

    @property
    def path(self):
        return self._path

    def exists(self):
        return os.path.exists(self._path)

    def size_bytes(self):
        return os.path.getsize(self._path) if os.path.exists(self._path) else 0

    # -- writing -------------------------------------------------------------

    def append(self, envelope):
        """Validate, append and fsync one event. Returns its LogRecord.

        The envelope is validated through the MOGO-010 contract FIRST, so a
        malformed event can never reach the log. There is no unchecked write
        path: this is the only method that writes, and it always validates.

        One os.write() of the complete line, then os.fsync(). Returns only
        after both succeed, so a returned LogRecord means "durable".
        """
        validated = event_contract.validate_event(envelope)
        plain = ids.as_plain(validated)
        line = ids.canonical_json_bytes(plain) + b"\n"

        self._paths.assert_inside_state_root(self._path, purpose="append event")
        os.makedirs(os.path.dirname(self._path), exist_ok=True)

        fd = os.open(self._path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        try:
            byte_offset = os.lseek(fd, 0, os.SEEK_END)
            written = os.write(fd, line)
            if written != len(line):
                # A short write leaves a torn tail. Do not retry into the same
                # file: the next scan detects and quarantines the fragment.
                runtime_errors.fail(
                    "short write appending event %s: %d of %d bytes"
                    % (validated["eventId"], written, len(line)),
                    runtime_errors.TornTailError,
                )
            os.fsync(fd)
        finally:
            os.close(fd)

        log_sequence = self._count_lines_upto(byte_offset) + 1
        return LogRecord(log_sequence, byte_offset, len(line), plain)

    def _count_lines_upto(self, byte_offset):
        if byte_offset == 0 or not os.path.exists(self._path):
            return 0
        count = 0
        with open(self._path, "rb") as handle:
            remaining = byte_offset
            while remaining > 0:
                chunk = handle.read(min(65536, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                count += chunk.count(b"\n")
        return count

    # -- reading -------------------------------------------------------------

    def scan(self, verify=True):
        """Read the entire log into ordered LogRecords.

        Raises LogCorruptionError for any defect that is NOT in the final line:
        unparsable JSON, a failed contract validation, or a payload hash that
        does not match its payload. Committed history is never skipped or
        repaired -- the runtime halts and an operator decides.

        A defect in the FINAL line, or a missing trailing newline, is reported
        as `torn_fragment` instead. That is an interrupted append, not
        corruption of committed history.
        """
        if not os.path.exists(self._path):
            return ScanResult([], None, 0)

        with open(self._path, "rb") as handle:
            raw = handle.read()
        if not raw:
            return ScanResult([], None, 0)

        torn = None
        body = raw
        if not raw.endswith(b"\n"):
            cut = raw.rfind(b"\n")
            if cut == -1:
                return ScanResult([], raw, 0)
            torn = raw[cut + 1:]
            body = raw[:cut + 1]

        records = []
        offset = 0
        line_number = 0
        lines = body.split(b"\n")
        if lines and lines[-1] == b"":
            lines = lines[:-1]

        for index, payload_bytes in enumerate(lines):
            line_number += 1
            length = len(payload_bytes) + 1
            is_last = (index == len(lines) - 1) and torn is None
            try:
                record = self._decode(payload_bytes, line_number, offset, length,
                                      verify=verify)
            except (runtime_errors.LogCorruptionError,
                    runtime_errors.ContractValidationError,
                    runtime_errors.IdentifierError,
                    ValueError) as exc:
                if is_last:
                    # A complete-looking but invalid final line is still an
                    # interrupted append: the bytes landed, the commit did not.
                    torn = payload_bytes
                    body = body[:offset]
                    break
                runtime_errors.fail(
                    "event log corruption at line %d (byte offset %d): %s"
                    % (line_number, offset, exc),
                    runtime_errors.LogCorruptionError,
                )
            records.append(record)
            offset += length

        return ScanResult(records, torn, offset)

    def _decode(self, payload_bytes, line_number, offset, length, verify):
        import json
        try:
            event = json.loads(payload_bytes.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            runtime_errors.fail("unparsable line: %s" % (exc,),
                                runtime_errors.LogCorruptionError)
        if verify:
            # Full MOGO-010 revalidation on every read: identifier formats,
            # closed vocabularies, JSON-shape, prohibited references AND the
            # payload hash. Reading is therefore an integrity check, not a
            # parse.
            event = ids.as_plain(event_contract.validate_event(event))
        return LogRecord(line_number, offset, length, event)

    def verify(self):
        """Integrity verdict for the whole log. Returns a findings list.

        Empty list means: every line parses, every envelope validates, every
        payload hash matches, and per-workflow sequences are strictly
        increasing from 1 with no gap.
        """
        findings = []
        try:
            result = self.scan(verify=True)
        except runtime_errors.LogCorruptionError as exc:
            return [{"severity": "FATAL", "finding": str(exc)}]

        if result.torn_fragment is not None:
            findings.append({
                "severity": "WARNING",
                "finding": "torn trailing append of %d byte(s); run `recover`"
                           % (len(result.torn_fragment),),
            })

        expected = {}
        for record in result.records:
            workflow = record.event["workflowId"]
            sequence = record.event["sequence"]
            want = expected.get(workflow, 0)
            if sequence != want:
                findings.append({
                    "severity": "ERROR",
                    "finding": "workflow %s: expected sequence %d, found %d at "
                               "log_sequence %d" % (workflow, want, sequence,
                                                    record.log_sequence),
                })
            expected[workflow] = max(want, sequence) + 1

        seen = set()
        for record in result.records:
            if record.event_id in seen:
                findings.append({
                    "severity": "ERROR",
                    "finding": "duplicate eventId %s at log_sequence %d"
                               % (record.event_id, record.log_sequence),
                })
            seen.add(record.event_id)
        return findings

    # -- torn-tail repair ----------------------------------------------------

    def repair_torn_tail(self, now):
        """Quarantine an interrupted append, then truncate to the last valid line.

        This is the ONLY place the log is shortened, and it shortens no event.
        An event is committed only when its complete newline-terminated line is
        durable (see the module docstring), so a fragment that fails that test
        never became history. Architecture section 24 requires partial artifacts
        to be "quarantined, not deleted, and reported" -- the fragment is copied
        out before the truncation and reported by `audit`.

        Returns the quarantine path, or None when there was nothing to repair.
        Corruption away from the tail is NOT repaired here: scan() raises first.
        """
        result = self.scan(verify=True)
        if result.torn_fragment is None:
            return None

        label = "torn-%d-%s.fragment" % (
            len(result.records) + 1, now.replace(":", "").replace(".", ""))
        target = self._paths.quarantine_file(label)
        self._paths.assert_inside_state_root(target, purpose="quarantine fragment")
        os.makedirs(os.path.dirname(target), exist_ok=True)

        # Write-temp-then-rename, matching the repository's atomic_write_text
        # precedent: the quarantine copy must be durable BEFORE the log is
        # shortened, or a crash between the two would lose the fragment.
        temporary = target + ".tmp"
        self._paths.assert_inside_state_root(temporary, purpose="quarantine fragment")
        with open(temporary, "wb") as handle:
            handle.write(result.torn_fragment)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)

        self._paths.assert_inside_state_root(self._path, purpose="truncate torn tail")
        fd = os.open(self._path, os.O_WRONLY)
        try:
            os.ftruncate(fd, result.valid_byte_length)
            os.fsync(fd)
        finally:
            os.close(fd)
        return target

    def next_sequence_for_workflow(self, workflow_id, records=None):
        """Next per-workflow sequence number (Catalog section B ordering)."""
        if records is None:
            records = self.scan(verify=False).records
        highest = -1
        for record in records:
            if record.event["workflowId"] == workflow_id:
                highest = max(highest, record.event["sequence"])
        return highest + 1

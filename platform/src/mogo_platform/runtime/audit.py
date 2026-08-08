#!/usr/bin/env python3
"""MOGO Automation Platform -- operator reports and integrity verification.

AUTHORITY
    Automation Platform Constitution v1.0 (senior) -- sections 4.18, 13, 20
    MOGO-009 Architecture, section 23
    MOGO-011 Step 1 plan, section 14

THE STANDARD THIS MODULE HAS TO MEET
    Architecture section 23: "An operator must be able to answer 'what failed,
    when, and why' without reading code." Every report here is written to that
    bar -- a rejected command, a suppressed duplicate, a reclaimed task and a
    late transition all appear by name, with their reason, in output an
    operator can read.

    Constitution section 4.18: failures, retries, rejections, suppressions and
    duplicates remain visible. Silence is a defect. That is why `audit` prints
    every submission attempt rather than only the accepted ones.

VERIFICATION IS INDEPENDENT OF THE INDEX
    verify_integrity() re-reads the authoritative log and re-derives what it
    expects, then compares. It never asks the index to confirm itself. A
    disagreement between log and index is reported as a finding rather than
    resolved silently in either direction.
"""

from ..contracts import ids  # noqa: E402
from . import errors as runtime_errors  # noqa: E402
from . import projection  # noqa: E402

SEVERITY_ORDER = {"FATAL": 0, "ERROR": 1, "WARNING": 2, "INFO": 3}


def _rows(connection, sql, args=()):
    return connection.execute(sql, args).fetchall()


def status_report(connection, log, paths):
    """Health snapshot: counts by state, backlog age, log size, registry."""
    states = _rows(connection,
                   "SELECT state, COUNT(*) AS count FROM tasks "
                   "GROUP BY state ORDER BY state")
    oldest = connection.execute(
        "SELECT task_id, state, created_log_sequence FROM tasks "
        "WHERE terminal = 0 ORDER BY created_log_sequence LIMIT 1").fetchone()
    events = connection.execute("SELECT COUNT(*) AS count FROM event_index").fetchone()
    capabilities = _rows(connection,
                         "SELECT capability_id, name, lifecycle_status, enabled_state "
                         "FROM capabilities ORDER BY capability_id")
    version = connection.execute(
        "SELECT value FROM schema_meta WHERE key = 'schema_version'").fetchone()
    submissions = _rows(connection,
                        "SELECT outcome, COUNT(*) AS count FROM command_submissions "
                        "GROUP BY outcome ORDER BY outcome")
    cursor_sequence, cursor_offset, _cursor_event = projection.cursor_position(connection)

    return {
        "schemaVersion": version["value"] if version else None,
        "stateRoot": paths.root,
        "eventLogPath": log.path,
        "eventLogBytes": log.size_bytes(),
        "eventCount": events["count"] if events else 0,
        "cursorLogSequence": cursor_sequence,
        "cursorByteOffset": cursor_offset,
        "tasksByState": [(row["state"], row["count"]) for row in states],
        "oldestNonTerminalTask": (
            None if oldest is None
            else {"taskId": oldest["task_id"], "state": oldest["state"]}),
        "submissionsByOutcome": [(row["outcome"], row["count"]) for row in submissions],
        "capabilities": [
            {"capabilityId": row["capability_id"], "name": row["name"],
             "lifecycleStatus": row["lifecycle_status"],
             "enabled": bool(row["enabled_state"])}
            for row in capabilities],
    }


def verify_integrity(connection, log):
    """Full integrity verdict. Returns a findings list; empty means clean.

    Checks, in order of how badly each would matter:
      1. the log itself parses, validates and hashes correctly end to end
      2. per-workflow sequences are contiguous from zero
      3. no duplicate event identifier
      4. the derived index agrees with the log, event for event
      5. the replay cursor is consistent with the index
      6. every task's state is a legal Catalog section L state
    """
    findings = list(log.verify())

    try:
        scanned = log.scan(verify=True)
    except runtime_errors.LogCorruptionError as exc:
        # `verify` exists to TELL an operator the log is untrustworthy. Letting
        # the corruption exception escape would make the one command designed to
        # diagnose the problem die of it, printing a traceback instead of a
        # verdict. The runtime still halts elsewhere; here we report.
        findings.append({"severity": "FATAL", "finding": str(exc)})
        findings.sort(key=lambda f: SEVERITY_ORDER.get(f["severity"], 9))
        return findings
    indexed = _rows(connection,
                    "SELECT log_sequence, event_id, payload_hash FROM event_index "
                    "ORDER BY log_sequence")
    by_sequence = {row["log_sequence"]: row for row in indexed}

    for record in scanned.records:
        row = by_sequence.get(record.log_sequence)
        if row is None:
            findings.append({
                "severity": "ERROR",
                "finding": "log_sequence %d is in the log but not in the index; "
                           "run `recover`" % (record.log_sequence,)})
            continue
        if row["event_id"] != record.event_id:
            findings.append({
                "severity": "FATAL",
                "finding": "log_sequence %d: index has eventId %s, log has %s"
                           % (record.log_sequence, row["event_id"], record.event_id)})
        recomputed = ids.content_hash_of(record.event["payload"])
        if recomputed != record.event["payloadHash"]:
            findings.append({
                "severity": "FATAL",
                "finding": "log_sequence %d: payload hash does not verify"
                           % (record.log_sequence,)})

    extra = set(by_sequence) - {r.log_sequence for r in scanned.records}
    for sequence in sorted(extra):
        findings.append({
            "severity": "FATAL",
            "finding": "log_sequence %d is indexed but absent from the log; the "
                       "index claims history the log does not have" % (sequence,)})

    cursor_sequence = projection.cursor_position(connection)[0]
    highest = max([r.log_sequence for r in scanned.records], default=0)
    if cursor_sequence > highest:
        findings.append({
            "severity": "ERROR",
            "finding": "replay cursor is at %d but the log ends at %d"
                       % (cursor_sequence, highest)})

    from ..contracts import task_states
    for row in _rows(connection, "SELECT task_id, state FROM tasks"):
        if row["state"] not in task_states.TASK_STATES:
            findings.append({
                "severity": "FATAL",
                "finding": "task %s is in unapproved state %r"
                           % (row["task_id"], row["state"])})

    findings.sort(key=lambda f: SEVERITY_ORDER.get(f["severity"], 9))
    return findings


def audit_report(connection, log, workflow_id=None, task_id=None):
    """Complete, ordered activity record for an operator."""
    try:
        scanned = log.scan(verify=True)
    except runtime_errors.LogCorruptionError:
        # Report what can still be read from the derived index, and let the
        # integrity section carry the verdict.
        return {"events": [], "timeline": [], "submissions": [], "anomalies": [],
                "recoveryActions": [], "tasks": [], "tornFragmentPresent": False,
                "integrity": verify_integrity(connection, log)}
    records = scanned.records
    if workflow_id:
        records = [r for r in records if r.event["workflowId"] == workflow_id]
    if task_id:
        records = [r for r in records if r.event.get("taskId") == task_id]

    events = [{
        "logSequence": r.log_sequence,
        "sequence": r.event["sequence"],
        "eventType": r.event["eventType"],
        "producer": r.event["producer"],
        "occurredAt": r.event["occurredAt"],
        "taskId": r.event.get("taskId"),
        "executionResult": r.event.get("executionResult"),
        "errorClass": r.event.get("errorClass"),
        "payloadHash": r.event["payloadHash"],
    } for r in records]

    timeline = []
    for r in records:
        transition = projection.TRANSITIONS.get(r.event["eventType"])
        if transition is None:
            continue
        from_state, to_state = transition
        timeline.append({
            "logSequence": r.log_sequence,
            "taskId": r.event.get("taskId"),
            "from": from_state,
            "to": to_state,
            "authority": r.event["producer"],
            "causedBy": r.event["eventType"],
        })

    submissions = _rows(connection,
                        "SELECT * FROM command_submissions ORDER BY submission_id")
    anomalies = _rows(connection,
                      "SELECT * FROM transition_anomalies ORDER BY anomaly_id")
    recoveries = _rows(connection,
                       "SELECT * FROM recovery_actions ORDER BY action_id")
    tasks = _rows(connection, "SELECT * FROM tasks ORDER BY created_log_sequence")

    return {
        "events": events,
        "timeline": timeline,
        "submissions": [{k: row[k] for k in row.keys()} for row in submissions],
        "anomalies": [{k: row[k] for k in row.keys()} for row in anomalies],
        "recoveryActions": [{k: row[k] for k in row.keys()} for row in recoveries],
        "tasks": [{k: row[k] for k in row.keys()} for row in tasks],
        "tornFragmentPresent": scanned.torn_fragment is not None,
        "integrity": verify_integrity(connection, log),
    }


def render_status(report):
    lines = ["MOGO runtime status",
             "  state root      : %s" % report["stateRoot"],
             "  schema version  : %s" % report["schemaVersion"],
             "  event log       : %s (%d bytes)" % (report["eventLogPath"],
                                                    report["eventLogBytes"]),
             "  events indexed  : %d (cursor at log_sequence %d)"
             % (report["eventCount"], report["cursorLogSequence"]),
             "  tasks by state  : %s" % (
                 ", ".join("%s=%d" % pair for pair in report["tasksByState"]) or "none"),
             "  submissions     : %s" % (
                 ", ".join("%s=%d" % pair for pair in report["submissionsByOutcome"])
                 or "none")]
    oldest = report["oldestNonTerminalTask"]
    lines.append("  oldest open     : %s" % (
        "none" if oldest is None else "%s (%s)" % (oldest["taskId"], oldest["state"])))
    lines.append("  capabilities    :")
    for capability in report["capabilities"]:
        lines.append("      %s  %s  %s  %s"
                     % (capability["capabilityId"], capability["name"],
                        capability["lifecycleStatus"],
                        "enabled" if capability["enabled"] else "DISABLED"))
    return "\n".join(lines)


def render_audit(report):
    lines = ["MOGO runtime audit", "", "EVENTS"]
    lines.append("  %-4s %-4s %-26s %-34s %-24s %s"
                 % ("log", "seq", "eventType", "producer", "occurredAt", "taskId"))
    for event in report["events"]:
        lines.append("  %-4d %-4d %-26s %-34s %-24s %s"
                     % (event["logSequence"], event["sequence"], event["eventType"],
                        event["producer"], event["occurredAt"],
                        event["taskId"] or "-"))

    lines += ["", "STATE TIMELINE"]
    for step in report["timeline"]:
        lines.append("  log %-4d %-14s -> %-16s by %-16s (%s)"
                     % (step["logSequence"], step["from"] or "(none)", step["to"],
                        step["authority"], step["causedBy"]))

    lines += ["", "COMMAND SUBMISSIONS (every attempt, including suppressed)"]
    for row in report["submissions"]:
        lines.append("  #%-3d %-22s %-14s %s"
                     % (row["submission_id"], row["submitted_at"], row["outcome"],
                        row["reason"] or ""))

    lines += ["", "TASKS"]
    for row in report["tasks"]:
        lines.append("  %s  state=%-12s terminal=%s result=%s error=%s"
                     % (row["task_id"], row["state"], bool(row["terminal"]),
                        row["result_hash"] or "-", row["error_class"] or "-"))

    if report["anomalies"]:
        lines += ["", "TRANSITION ANOMALIES (recorded, not applied)"]
        for row in report["anomalies"]:
            lines.append("  log %-4d task %s  %s -> %s : %s"
                         % (row["log_sequence"], row["task_id"], row["from_state"],
                            row["to_state"], row["reason"]))

    if report["recoveryActions"]:
        lines += ["", "RECOVERY ACTIONS"]
        for row in report["recoveryActions"]:
            lines.append("  %-22s %-24s %s %s"
                         % (row["detected_at"], row["action"], row["subject"] or "",
                            row["detail"] or ""))

    lines += ["", "INTEGRITY"]
    if report["tornFragmentPresent"]:
        lines.append("  WARNING torn trailing append present; run `recover`")
    if not report["integrity"]:
        lines.append("  OK  every event parses, validates and hashes; sequences "
                     "contiguous; index agrees with the log")
    else:
        for finding in report["integrity"]:
            lines.append("  %-8s %s" % (finding["severity"], finding["finding"]))
    return "\n".join(lines)

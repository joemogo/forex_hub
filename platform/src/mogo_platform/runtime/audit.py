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

import json  # noqa: E402

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
                         "SELECT * FROM capabilities ORDER BY capability_id")
    version = connection.execute(
        "SELECT value FROM schema_meta WHERE key = 'schema_version'").fetchone()
    submissions = _rows(connection,
                        "SELECT outcome, COUNT(*) AS count FROM command_submissions "
                        "GROUP BY outcome ORDER BY outcome")
    cursor_sequence, cursor_offset, _cursor_event = projection.cursor_position(connection)

    from . import registry

    attempts = connection.execute(
        "SELECT COUNT(*) AS total,"
        " SUM(CASE WHEN outcome = 'failed' THEN 1 ELSE 0 END) AS failed "
        "FROM task_attempts").fetchone()
    retries_scheduled = connection.execute(
        "SELECT COUNT(*) AS count FROM event_index "
        "WHERE event_type = 'TaskRetryScheduled'").fetchone()
    retries_released = connection.execute(
        "SELECT COUNT(*) AS count FROM event_index "
        "WHERE event_type = 'TaskRetryReleased'").fetchone()
    dead_letters = _rows(connection,
                         "SELECT dead_letter_reason AS reason, COUNT(*) AS count "
                         "FROM tasks WHERE state = 'dead_lettered' "
                         "GROUP BY dead_letter_reason ORDER BY reason")
    oldest_retry = connection.execute(
        "SELECT task_id, retry_eligible_at FROM tasks "
        "WHERE state = 'retry_scheduled' AND retry_eligible_at IS NOT NULL "
        "ORDER BY retry_eligible_at LIMIT 1").fetchone()
    held = _rows(connection,
                 "SELECT task_id, lease_holder, lease_generation, lease_expires_at "
                 "FROM tasks WHERE lease_holder IS NOT NULL "
                 "ORDER BY lease_expires_at")

    policy_counts = _rows(connection,
                          "SELECT decision, COUNT(*) AS count FROM policy_decisions "
                          "GROUP BY decision ORDER BY decision")
    blocked_now = connection.execute(
        "SELECT COUNT(*) AS count FROM tasks "
        "WHERE state IN ('blocked', 'awaiting_review')").fetchone()
    authorization_count = connection.execute(
        "SELECT COUNT(*) AS count FROM acquisition_authorizations").fetchone()

    return {
        "policyDecisionsByOutcome": [(row["decision"], row["count"])
                                     for row in policy_counts],
        "tasksAwaitingDisposition": blocked_now["count"] if blocked_now else 0,
        "authorizationsRecorded": (authorization_count["count"]
                                   if authorization_count else 0),
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
             "enabled": bool(row["enabled_state"]),
             "effectClass": row["effect_class"],
             "failureClasses": list(registry.declared_failure_classes(row)),
             "retryPolicy": registry.declared_retry_policy(row)}
            for row in capabilities],
        "attemptsRecorded": (attempts["total"] if attempts else 0) or 0,
        "attemptsFailed": (attempts["failed"] if attempts else 0) or 0,
        "retriesScheduled": retries_scheduled["count"] if retries_scheduled else 0,
        "retriesReleased": retries_released["count"] if retries_released else 0,
        "deadLettersByReason": [(row["reason"], row["count"]) for row in dead_letters],
        "oldestScheduledRetry": (
            None if oldest_retry is None
            else {"taskId": oldest_retry["task_id"],
                  "eligibleAt": oldest_retry["retry_eligible_at"]}),
        "leasesHeld": [
            {"taskId": row["task_id"], "holder": row["lease_holder"],
             "generation": row["lease_generation"],
             "expiresAt": row["lease_expires_at"]} for row in held],
        "a5GateOpen": not registry.unmet_a5_preconditions(),
        "a5GateUnmet": list(registry.unmet_a5_preconditions()),
        "connectorGatesUnmet": [gate["gate"] for gate in registry.CONNECTOR_GATES
                                if not gate["satisfied"]],
    }


def policy_report(connection, log):
    """The policy gate's own operator view.

    Constitution section 13: an operator must be able to answer "what was
    blocked, when, and why" without reading code. Everything the gate decided
    is here, together with the authorizations in force and the tasks a human
    now has to dispose of.
    """
    from . import authorizations as authorizations_module
    from . import registry

    decisions = _rows(connection,
                      "SELECT decision, reason, COUNT(*) AS count "
                      "FROM policy_decisions GROUP BY decision, reason "
                      "ORDER BY decision, count DESC, reason")

    blocked = [
        {"taskId": row["task_id"], "state": row["state"],
         "reason": row["policy_reason"], "operationClass": row["operation_class"],
         "subjectSourceId": row["subject_source_id"],
         "policyStatus": row["policy_status"],
         "policyVersion": row["policy_version"],
         "authorizationId": row["authorization_id"]}
        for row in _rows(connection,
                         "SELECT * FROM tasks WHERE policy_decision = 'deny' "
                         "ORDER BY created_log_sequence")]

    awaiting = [entry for entry in blocked
                if entry["state"] in ("blocked", "awaiting_review")]

    disposed = [
        {"taskId": row["task_id"], "state": row["state"],
         "decision": row["review_decision"], "reason": row["review_reason"],
         "reviewer": row["reviewer_identity"]}
        for row in _rows(connection,
                         "SELECT * FROM tasks WHERE review_decision IS NOT NULL "
                         "ORDER BY created_log_sequence")]

    superseded = authorizations_module.superseded_ids(connection)
    records = [
        {"authorizationId": row["authorization_id"], "sourceId": row["source_id"],
         "policyStatus": row["policy_status"], "policyVersion": row["policy_version"],
         "decisionAuthority": row["decision_authority"],
         "decidedAt": row["decided_at"], "expiresAt": row["expires_at"],
         "permittedOperations": json.loads(row["permitted_operations"]),
         "supersededBy": row["authorization_id"] in superseded,
         "recordHash": row["record_hash"]}
        for row in authorizations_module.all_authorizations(connection)]

    return {
        "decisionsByOutcome": [(row["decision"], row["reason"], row["count"])
                               for row in decisions],
        "blockedTasks": blocked,
        "awaitingDisposition": awaiting,
        "disposedTasks": disposed,
        "authorizations": records,
        "connectorGates": [dict(gate) for gate in registry.CONNECTOR_GATES],
    }


def render_policy(report):
    lines = ["POLICY DECISIONS",
             "  %-16s %-36s %s" % ("decision", "reason", "count")]
    if not report["decisionsByOutcome"]:
        lines.append("  (none)")
    for decision, reason, count in report["decisionsByOutcome"]:
        lines.append("  %-16s %-36s %d" % (decision, reason, count))

    lines += ["", "ACQUISITION AUTHORIZATIONS (governance input; never minted here)",
              "  %-38s %-28s %-12s %-24s %s"
              % ("sourceId", "policyStatus", "operations", "authority", "state")]
    if not report["authorizations"]:
        lines.append("  (none recorded)")
    for entry in report["authorizations"]:
        lines.append("  %-38s %-28s %-12s %-24s %s"
                     % (entry["sourceId"], entry["policyStatus"],
                        ",".join(entry["permittedOperations"]) or "-",
                        entry["decisionAuthority"],
                        "SUPERSEDED" if entry["supersededBy"] else "in force"))

    lines += ["", "BLOCKED BY POLICY",
              "  %-38s %-16s %-34s %s"
              % ("taskId", "state", "reason", "subjectSource")]
    if not report["blockedTasks"]:
        lines.append("  (none)")
    for entry in report["blockedTasks"]:
        lines.append("  %-38s %-16s %-34s %s"
                     % (entry["taskId"], entry["state"], entry["reason"] or "-",
                        entry["subjectSourceId"] or "-"))

    lines += ["", "AWAITING OPERATOR DISPOSITION"]
    if not report["awaitingDisposition"]:
        lines.append("  (none)")
    for entry in report["awaitingDisposition"]:
        lines.append("  %s  %s  -- a human decision is required to release or "
                     "suppress this task" % (entry["taskId"], entry["reason"]))

    if report["disposedTasks"]:
        lines += ["", "DISPOSED BY REVIEW"]
        for entry in report["disposedTasks"]:
            lines.append("  %-38s %-12s %-24s %s"
                         % (entry["taskId"], entry["decision"], entry["reviewer"],
                            entry["reason"]))

    lines += ["", "CONNECTOR GATES"]
    for gate in report["connectorGates"]:
        lines.append("  %-34s %s   %s"
                     % (gate["gate"], "MET   " if gate["satisfied"] else "UNMET ",
                        gate["requires"]))
    unmet = [g for g in report["connectorGates"] if not g["satisfied"]]
    lines.append("  %d gate(s) still unmet -- no connector may exist until they are"
                 % (len(unmet),))
    return "\n".join(lines)


def failures_report(connection, log):
    """Architecture section 23's Failures view, as data.

    Constitution section 13: an operator must be able to answer "what failed,
    when, and why" WITHOUT READING CODE. Everything needed to answer it is
    here, and so is the thing an operator most needs to know about this
    platform -- what it is not yet allowed to do, and why.
    """
    from ..contracts import errors as contract_errors
    from . import registry

    by_class = _rows(connection,
                     "SELECT error_class, COUNT(*) AS count,"
                     "       MAX(finished_at) AS last_at "
                     "FROM task_attempts WHERE outcome = 'failed' "
                     "GROUP BY error_class ORDER BY count DESC, error_class")
    failures = []
    for row in by_class:
        last = connection.execute(
            "SELECT task_id, attempt FROM task_attempts "
            "WHERE outcome = 'failed' AND error_class IS ? "
            "ORDER BY finished_at DESC, attempt_id DESC LIMIT 1",
            (row["error_class"],)).fetchone()
        record = contract_errors.ERROR_CLASSES.get(row["error_class"])
        failures.append({
            "errorClass": row["error_class"],
            "count": row["count"],
            "retryable": None if record is None else bool(record["retryable"]),
            "lastOccurrence": row["last_at"],
            "lastTaskId": None if last is None else last["task_id"],
            "lastAttempt": None if last is None else last["attempt"],
        })

    dead_letters = [
        {"taskId": row["task_id"], "reason": row["dead_letter_reason"],
         "attempts": row["attempt"], "attemptLimit": row["attempt_limit"],
         "finalErrorClass": row["error_class"]}
        for row in _rows(connection,
                         "SELECT task_id, dead_letter_reason, attempt,"
                         "       attempt_limit, error_class FROM tasks "
                         "WHERE state = 'dead_lettered' "
                         "ORDER BY created_log_sequence")]

    attempts = [{k: row[k] for k in row.keys()}
                for row in _rows(connection,
                                 "SELECT * FROM task_attempts "
                                 "ORDER BY task_id, attempt")]

    leases = [
        {"taskId": row["task_id"], "holder": row["lease_holder"],
         "generation": row["lease_generation"],
         "acquiredAt": row["lease_acquired_at"],
         "expiresAt": row["lease_expires_at"], "state": row["state"]}
        for row in _rows(connection,
                         "SELECT task_id, lease_holder, lease_generation,"
                         "       lease_acquired_at, lease_expires_at, state "
                         "FROM tasks WHERE lease_holder IS NOT NULL "
                         "ORDER BY lease_expires_at")]

    retries = [
        {"taskId": row["task_id"], "attempt": row["attempt"],
         "attemptLimit": row["attempt_limit"],
         "eligibleAt": row["retry_eligible_at"], "backoffMs": row["backoff_ms"]}
        for row in _rows(connection,
                         "SELECT task_id, attempt, attempt_limit,"
                         "       retry_eligible_at, backoff_ms FROM tasks "
                         "WHERE state = 'retry_scheduled' "
                         "ORDER BY retry_eligible_at")]

    violations = [{k: row[k] for k in row.keys()}
                  for row in _rows(connection,
                                   "SELECT * FROM capability_violations "
                                   "ORDER BY violation_id")]

    return {
        "failuresByErrorClass": failures,
        "deadLetters": dead_letters,
        "attempts": attempts,
        "leases": leases,
        "scheduledRetries": retries,
        "capabilityViolations": violations,
        "a5Gate": {"open": not registry.unmet_a5_preconditions(),
                   "unmet": list(registry.unmet_a5_preconditions())},
        "connectorGates": [dict(gate) for gate in registry.CONNECTOR_GATES],
    }


def render_failures(report):
    lines = ["FAILURES BY ERROR CLASS",
             "  %-24s %6s %10s  %-24s %s"
             % ("errorClass", "count", "retryable", "last occurrence",
                "last task")]
    if not report["failuresByErrorClass"]:
        lines.append("  (none)")
    for entry in report["failuresByErrorClass"]:
        lines.append("  %-24s %6d %10s  %-24s %s"
                     % (entry["errorClass"] or "(unclassified)", entry["count"],
                        "-" if entry["retryable"] is None
                        else ("yes" if entry["retryable"] else "no"),
                        entry["lastOccurrence"] or "-",
                        entry["lastTaskId"] or "-"))

    lines += ["", "DEAD LETTERS",
              "  %-38s %-28s %-9s %s"
              % ("taskId", "reason", "attempts", "finalClass")]
    if not report["deadLetters"]:
        lines.append("  (none)")
    for entry in report["deadLetters"]:
        lines.append("  %-38s %-28s %-9s %s"
                     % (entry["taskId"], entry["reason"] or "-",
                        "%s/%s" % (entry["attempts"], entry["attemptLimit"]),
                        entry["finalErrorClass"] or "-"))

    lines += ["", "ATTEMPT HISTORY",
              "  %-38s %7s %6s %-10s %-24s %s"
              % ("taskId", "attempt", "lease", "outcome", "started", "errorClass")]
    if not report["attempts"]:
        lines.append("  (none recorded)")
    for row in report["attempts"]:
        lines.append("  %-38s %7d %6d %-10s %-24s %s"
                     % (row["task_id"], row["attempt"], row["lease_generation"],
                        row["outcome"], row["started_at"],
                        row["error_class"] or "-"))

    lines += ["", "SCHEDULED RETRIES (waiting out their backoff)"]
    if not report["scheduledRetries"]:
        lines.append("  (none)")
    for entry in report["scheduledRetries"]:
        lines.append("  %-38s attempt %s/%s  eligible at %s  (backoff %s ms)"
                     % (entry["taskId"], entry["attempt"], entry["attemptLimit"],
                        entry["eligibleAt"], entry["backoffMs"]))

    lines += ["", "LEASES"]
    if not report["leases"]:
        lines.append("  (none held)")
    for entry in report["leases"]:
        lines.append("  %-38s %-46s gen %-4d %-12s expires %s"
                     % (entry["taskId"], entry["holder"], entry["generation"],
                        entry["state"], entry["expiresAt"]))

    if report["capabilityViolations"]:
        lines += ["", "CAPABILITY VIOLATIONS (declared-contract breaches)"]
        for row in report["capabilityViolations"]:
            lines.append("  %-24s %-46s %s %s"
                         % (row["detected_at"], row["capability_id"],
                            row["violation"], row["detail"] or ""))

    lines += ["", "GATES"]
    gate = report["a5Gate"]
    lines.append("  A-5 effectful-capability gate   %s   %s"
                 % ("OPEN" if gate["open"] else "CLOSED",
                    ", ".join(gate["unmet"]) or "-"))
    unmet = [g for g in report["connectorGates"] if not g["satisfied"]]
    lines.append("  connector gates                 %d UNMET"
                 % (len(unmet),))
    for entry in unmet:
        lines.append("      %-34s %s" % (entry["gate"], entry["requires"]))
    lines.append("  no effectful capability may register, and no connector may "
                 "exist, until these are met")
    return "\n".join(lines)


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

    findings.extend(_verify_step_2_invariants(connection, scanned.records))

    findings.sort(key=lambda f: SEVERITY_ORDER.get(f["severity"], 9))
    return findings


def _verify_step_2_invariants(connection, records):
    """Four checks re-derived FROM THE LOG, not from the code that wrote it.

    Every one of these could be asserted in-process at the moment the event is
    produced, and every one of those assertions could be deleted by a future
    edit. Deriving them from the durable log instead means the evidence
    survives the deletion of the code that created it -- which is the whole
    reason `verify` reads the log rather than asking the index to confirm
    itself.
    """
    findings = []
    from ..contracts import task_states

    # 1. No release precedes its eligibility. The single check that proves
    #    backoff is ENFORCED rather than skipped, and it holds even if every
    #    in-process assertion were removed.
    scheduled = {}
    for record in records:
        event = record.event
        task_id = event.get("taskId")
        if event["eventType"] == "TaskRetryScheduled":
            scheduled.setdefault(task_id, []).append(
                (record.log_sequence, event["payload"].get("eligibleAtUtc")))
        elif event["eventType"] == "TaskRetryReleased":
            payload = event["payload"]
            observed = payload.get("observedAtUtc")
            eligible = payload.get("scheduledEligibleAtUtc")
            if observed is None or eligible is None:
                findings.append({
                    "severity": "ERROR",
                    "finding": "log_sequence %d: a retry release records no "
                               "eligibility, so it cannot be shown to have "
                               "waited" % (record.log_sequence,)})
                continue
            if observed < eligible:
                findings.append({
                    "severity": "FATAL",
                    "finding": "log_sequence %d: retry for task %s released at "
                               "%s, before its eligibility at %s"
                               % (record.log_sequence, task_id, observed,
                                  eligible)})
            known = [value for _sequence, value in scheduled.get(task_id, [])]
            if eligible not in known:
                findings.append({
                    "severity": "FATAL",
                    "finding": "log_sequence %d: retry for task %s claims "
                               "eligibility %s, which no TaskRetryScheduled "
                               "for that task recorded"
                               % (record.log_sequence, task_id, eligible)})
            # A forward clock jump is not an error -- it can only make a
            # backoff elapse earlier than intended -- but a large one is worth
            # seeing, so it is reported as INFO rather than hidden.
            backoff = payload.get("scheduledBackoffMs") or 0
            waited = payload.get("waitedMs")
            if backoff and isinstance(waited, int) and waited > 10 * backoff:
                findings.append({
                    "severity": "INFO",
                    "finding": "log_sequence %d: retry for task %s waited %d ms "
                               "against a scheduled backoff of %d ms; the clock "
                               "may have jumped forward"
                               % (record.log_sequence, task_id, waited, backoff)})

    # 2. No attempt is recorded twice. The schema's UNIQUE (task_id, attempt)
    #    catches it at write time; this catches it in history.
    seen_attempts = set()
    for record in records:
        event = record.event
        if event["eventType"] not in ("TaskSucceeded", "TaskFailed"):
            continue
        attempt = event["payload"].get("attempt")
        if attempt is None:
            continue                       # a Step 1 event: no attempt recorded
        key = (event.get("taskId"), attempt)
        if key in seen_attempts:
            findings.append({
                "severity": "FATAL",
                "finding": "log_sequence %d: attempt %d of task %s reaches an "
                           "outcome twice"
                           % (record.log_sequence, attempt, event.get("taskId"))})
        seen_attempts.add(key)

    # 3. Lease generations are monotonic per task. A reset generation would let
    #    a stale execution's generation match a fresh lease and defeat the
    #    holder verification entirely.
    highest_generation = {}
    for record in records:
        event = record.event
        if event["eventType"] != "TaskClaimed":
            continue
        generation = event["payload"].get("leaseGeneration")
        if generation is None:
            continue                       # a Step 1 claim: no lease
        task_id = event.get("taskId")
        previous = highest_generation.get(task_id)
        if previous is not None and generation <= previous:
            findings.append({
                "severity": "FATAL",
                "finding": "log_sequence %d: task %s claimed at lease "
                           "generation %d, which does not exceed the previous "
                           "%d" % (record.log_sequence, task_id, generation,
                                   previous)})
        highest_generation[task_id] = generation

    # 4. Every terminal task reached its terminal state through an event.
    #    Constitution section 6.5 and 6.6 together: a task that is terminal in
    #    the index but has no terminal event in the log is a state change the
    #    log cannot reproduce.
    # RESOLVED, not looked up in a static map. A terminal state can be reached
    # by a PAYLOAD-DEPENDENT transition -- HumanReviewCompleted(rejected)
    # carries awaiting_review -> suppressed -- and a static map silently omits
    # those, which made `verify` report a FALSE FATAL for every suppressed task
    # in ordinary operation. Asking the projection which edge an event actually
    # carries is the same fix, and the same reasoning, as the audit timeline.
    terminal_events = {}
    for record in records:
        transition = projection.resolved_transition(record)
        if transition is None:
            continue
        target = transition[1]
        if target in task_states.TERMINAL_STATES:
            terminal_events.setdefault(record.event.get("taskId"), set()).add(target)
    for row in _rows(connection,
                     "SELECT task_id, state, terminal FROM tasks WHERE terminal = 1"):
        reached = terminal_events.get(row["task_id"], set())
        if row["state"] in task_states.TERMINAL_STATES and row["state"] not in reached:
            findings.append({
                "severity": "FATAL",
                "finding": "task %s is terminal in state %r but no event in the "
                           "log carries that transition"
                           % (row["task_id"], row["state"])})

    return findings


# Retained for reference and for callers that want the STATIC mapping. The
# verify check above deliberately does NOT use it: a terminal state can also be
# reached by a payload-dependent transition, and a static list of event names
# cannot express that. See the comment at the check itself.
TERMINAL_EVENT_STATES = {
    "TaskSucceeded": "succeeded",
    "TaskDeadLettered": "dead_lettered",
    "HumanReviewCompleted": "suppressed",   # when the payload records a rejection
}


def audit_report(connection, log, workflow_id=None, task_id=None):
    """Complete, ordered activity record for an operator."""
    try:
        scanned = log.scan(verify=True)
    except runtime_errors.LogCorruptionError:
        # Report what can still be read from the derived index, and let the
        # integrity section carry the verdict.
        return {"events": [], "timeline": [], "submissions": [], "anomalies": [],
                "recoveryActions": [], "tasks": [], "attempts": [],
                "capabilityViolations": [], "runs": [],
                "tornFragmentPresent": False,
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
        # The RESOLVED edge, not the table's default one. A PolicyEvaluated
        # denial carries policy_check -> blocked, and reporting the table's
        # `-> queued` instead would put a transition in the operator's timeline
        # that never happened.
        transition = projection.resolved_transition(r)
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
    attempts = _rows(connection,
                     "SELECT * FROM task_attempts ORDER BY task_id, attempt")
    violations = _rows(connection,
                       "SELECT * FROM capability_violations ORDER BY violation_id")
    runs = _rows(connection, "SELECT * FROM runs ORDER BY started_at")

    return {
        "events": events,
        "timeline": timeline,
        "submissions": [{k: row[k] for k in row.keys()} for row in submissions],
        "anomalies": [{k: row[k] for k in row.keys()} for row in anomalies],
        "recoveryActions": [{k: row[k] for k in row.keys()} for row in recoveries],
        "tasks": [{k: row[k] for k in row.keys()} for row in tasks],
        "attempts": [{k: row[k] for k in row.keys()} for row in attempts],
        "capabilityViolations": [{k: row[k] for k in row.keys()}
                                 for row in violations],
        "runs": [{k: row[k] for k in row.keys()} for row in runs],
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
    lines.append("  policy          : %s"
                 % (", ".join("%s=%d" % pair
                              for pair in report["policyDecisionsByOutcome"])
                    or "no decisions yet"))
    lines.append("  awaiting review : %d task(s) blocked by policy"
                 % (report["tasksAwaitingDisposition"],))
    lines.append("  authorizations  : %d recorded"
                 % (report["authorizationsRecorded"],))
    lines.append("  attempts        : %d recorded, %d failed"
                 % (report["attemptsRecorded"], report["attemptsFailed"]))
    lines.append("  retries         : %d scheduled, %d released"
                 % (report["retriesScheduled"], report["retriesReleased"]))
    lines.append("  dead letters    : %s" % (
        ", ".join("%s=%d" % (reason or "unrecorded", count)
                  for reason, count in report["deadLettersByReason"]) or "none"))
    pending = report["oldestScheduledRetry"]
    lines.append("  oldest retry    : %s" % (
        "none" if pending is None
        else "%s eligible at %s" % (pending["taskId"], pending["eligibleAt"])))
    lines.append("  leases held     : %s" % (
        ", ".join("%s gen %d expires %s"
                  % (entry["taskId"], entry["generation"], entry["expiresAt"])
                  for entry in report["leasesHeld"]) or "none"))
    lines.append("  capabilities    :")
    for capability in report["capabilities"]:
        lines.append("      %s  %s  %s  %s  effect=%s  failureClasses=%s"
                     % (capability["capabilityId"], capability["name"],
                        capability["lifecycleStatus"],
                        "enabled" if capability["enabled"] else "DISABLED",
                        capability["effectClass"],
                        ",".join(capability["failureClasses"]) or "none"))
    # Printed in the ordinary health snapshot, deliberately. What the platform
    # is not yet allowed to do is health information, not a footnote.
    lines.append("  A-5 gate        : %s%s"
                 % ("OPEN" if report["a5GateOpen"] else "CLOSED",
                    "" if report["a5GateOpen"]
                    else " (%d preconditions unmet: %s)"
                         % (len(report["a5GateUnmet"]),
                            ", ".join(report["a5GateUnmet"]))))
    lines.append("  connector gates : %d unmet%s"
                 % (len(report["connectorGatesUnmet"]),
                    (" -- " + ", ".join(report["connectorGatesUnmet"]))
                    if report["connectorGatesUnmet"] else ""))
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
        lines.append("  %s  state=%-16s terminal=%-5s attempt=%s/%s result=%s "
                     "error=%s%s"
                     % (row["task_id"], row["state"], bool(row["terminal"]),
                        row["attempt"], row["attempt_limit"],
                        row["result_hash"] or "-", row["error_class"] or "-",
                        "" if not row["dead_letter_reason"]
                        else " deadLetter=%s" % (row["dead_letter_reason"],)))

    lines += ["", "ATTEMPTS"]
    if not report["attempts"]:
        # A task created before schema v2 has no attempt history, and saying so
        # is better than printing a zero that would read as "never tried".
        lines.append("  none recorded (a pre-v2 task records no attempt history)")
    for row in report["attempts"]:
        lines.append("  %s  attempt=%-3d lease=%-3d %-10s %-24s -> %-24s %s"
                     % (row["task_id"], row["attempt"], row["lease_generation"],
                        row["outcome"], row["started_at"], row["finished_at"],
                        row["error_class"] or row["result_hash"] or "-"))

    if report["capabilityViolations"]:
        lines += ["", "CAPABILITY VIOLATIONS"]
        for row in report["capabilityViolations"]:
            lines.append("  %-24s %-46s %s %s"
                         % (row["detected_at"], row["capability_id"],
                            row["violation"], row["detail"] or ""))

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

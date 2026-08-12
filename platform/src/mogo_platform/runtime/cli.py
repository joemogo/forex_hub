#!/usr/bin/env python3
"""MOGO Automation Platform -- operator command line.

AUTHORITY
    MOGO-009 Architecture, section 23 (observability)
    MOGO-011 Step 1 plan, sections 6, 14, 21

CONVENTION
    argparse subcommands with `if __name__` entry points, matching the
    convention the repository's existing operator tools already use. Exit code 0
    on success, non-zero on any refusal -- so the demonstration sequence can be
    driven from a shell script and a failure cannot be mistaken for success.

SUBCOMMANDS
    init      create the state root and database, register capabilities, and
              migrate an older state root -- the ONE command that migrates,
              because it is the one that takes the single-writer lock
    submit    accept one command (--demo, or --demo-retry N for the
              fail-then-succeed demonstration)
    collect   MOGO-016: submit AND run the ONE fixed approved scheduled
              collection, in a single process lock. The only subcommand a host
              schedule is permitted to invoke; it takes no source, URL or
              capability argument, so there is nothing to inject
    run       recover, release eligible retries, then drive every non-terminal
              task to a terminal state
    status    health snapshot, including attempts, retries, leases and gates
    audit     complete ordered activity record
    failures  what failed, when, and why -- Architecture section 23's operator
              view, plus the A-5 and connector gates
    library   MOGO-018 Step 2: the DERIVED research library index (read-only)
    corpus    MOGO-018 Step 3D: what the autonomous research system possesses,
              by source and strategy family -- counts and timestamps only, no
              verdict, no network, no acquisition, no write
    verify    integrity checks alone; non-zero exit on any finding
    reset     delete runtime state, or rebuild the index from the log alone
    demo      the end-to-end demonstration required by MOGO-011

EXIT CODES
    0 success · 2 rejected · 3 a task reached a TERMINAL failure (dead-letter)
    4 integrity findings · 5 another runtime holds the lock · 6 refused

    A task that failed and was rescheduled has NOT failed the run. Treating an
    intermediate `failed` as a run failure would report every successful retry
    as an error, and the exit code is a signal an operator has to be able to
    trust.
"""

import argparse
import json
import os
import shutil
import sys

from ..contracts import ids  # noqa: E402
from . import audit as audit_module  # noqa: E402
from . import clock as clock_module  # noqa: E402
from . import errors as runtime_errors  # noqa: E402
from . import event_log as event_log_module  # noqa: E402
from . import orchestrator as orchestrator_module  # noqa: E402
from . import paths as paths_module  # noqa: E402
from . import projection  # noqa: E402
from . import authorizations as authorizations_module  # noqa: E402
from . import policy as policy_module  # noqa: E402
from . import registry  # noqa: E402
from . import research_library  # noqa: E402
from . import schema as schema_module  # noqa: E402
from . import scheduled_collection  # noqa: E402
from . import store  # noqa: E402
from .capabilities import echo as echo_capability  # noqa: E402
from .capabilities import fail_then_succeed as fail_then_succeed_capability  # noqa: E402
from .capabilities import policy_probe as policy_probe_capability  # noqa: E402

CLOCK_OVERRIDE_ENV = orchestrator_module.CLOCK_OVERRIDE_ENV

DEMO_PAYLOAD = {
    "note": "MOGO-011 Step 1 runtime kernel demonstration",
    "values": [1, 2, 3],
    "nested": {"unicode": "é中文", "flag": True, "nothing": None},
}


def build_demo_command(payload=None, uuid_factory=None, clock=None):
    """The canonical demonstration command, built through MOGO-010 contracts.

    The idempotency key is derived from the payload alone via the approved
    Catalog section I `transformation` composition, so re-running `submit
    --demo` with the same payload produces the same key and is suppressed as a
    duplicate -- which is milestone outcome 10.
    """
    payload = DEMO_PAYLOAD if payload is None else payload
    clock = clock or orchestrator_module.utc_now
    mint = (lambda: ids.new_uuid4(uuid_factory=uuid_factory))
    correlation_id = mint()
    key = ids.idempotency_key("transformation", {
        "inputHash": ids.content_hash_of(payload),
        "transformationId": "XF|runtime-echo",
        "transformationVersion": echo_capability.CAPABILITY_VERSION,
    })
    envelope = {
        "commandId": mint(),
        "commandType": "NormalizeArtifact",
        "commandVersion": 1,
        "workflowId": mint(),
        "correlationId": correlation_id,
        "causationId": correlation_id,
        "idempotencyKey": key,
        "issuedAt": clock(),
        "issuedBy": "operator:mogo",
        "targetCapability": echo_capability.CAPABILITY_ID,
        "inputRefs": ["XF|runtime-echo"],
        "policyContext": {"authorizationId": None, "policyVersion": "0",
                          "permittedOperations": []},
        "payloadHash": ids.content_hash_of(payload),
    }
    return envelope, payload


def build_retry_demo_command(fail_until_attempt, note, uuid_factory=None,
                             clock=None):
    """A demonstration command for the fail-then-succeed capability.

    `failUntilAttempt` is part of the SEMANTIC payload, so it participates in
    the idempotency key -- which is why the retry demonstration and the
    dead-letter demonstration are naturally different tasks with different
    keys, rather than one task with a mode flag.
    """
    clock = clock or orchestrator_module.utc_now
    mint = (lambda: ids.new_uuid4(uuid_factory=uuid_factory))
    payload = {"note": note, "failUntilAttempt": fail_until_attempt}
    correlation_id = mint()
    key = ids.idempotency_key("transformation", {
        "inputHash": ids.content_hash_of(payload),
        "transformationId": "XF|runtime-fail-then-succeed",
        "transformationVersion": fail_then_succeed_capability.CAPABILITY_VERSION,
    })
    envelope = {
        "commandId": mint(),
        "commandType": "NormalizeArtifact",
        "commandVersion": 1,
        "workflowId": mint(),
        "correlationId": correlation_id,
        "causationId": correlation_id,
        "idempotencyKey": key,
        "issuedAt": clock(),
        "issuedBy": "operator:mogo",
        "targetCapability": fail_then_succeed_capability.CAPABILITY_ID,
        "inputRefs": ["XF|runtime-fail-then-succeed"],
        "policyContext": {"authorizationId": None, "policyVersion": "0",
                          "permittedOperations": []},
        "payloadHash": ids.content_hash_of(payload),
    }
    return envelope, payload


def build_policy_demo_command(source_id, note, uuid_factory=None, clock=None):
    """A demonstration command for the policy-gate probe.

    `inputRefs` carries the subject source as an identifier -- Catalog section A:
    references only, never inline payloads. The gate resolves the authorization
    for exactly this source.
    """
    clock = clock or orchestrator_module.utc_now
    mint = (lambda: ids.new_uuid4(uuid_factory=uuid_factory))
    payload = {"note": note, "sourceId": source_id}
    correlation_id = mint()
    key = ids.idempotency_key("metadata_acquisition", {
        "sourceId": source_id,
        "connectorVersion": policy_probe_capability.CAPABILITY_VERSION,
    })
    envelope = {
        "commandId": mint(),
        "commandType": "AcquireSourceMetadata",
        "commandVersion": 1,
        "workflowId": mint(),
        "correlationId": correlation_id,
        "causationId": correlation_id,
        "idempotencyKey": key,
        "issuedAt": clock(),
        "issuedBy": "operator:mogo",
        "targetCapability": policy_probe_capability.CAPABILITY_ID,
        "inputRefs": [source_id],
        "policyContext": {"authorizationId": None, "policyVersion": "0",
                          "permittedOperations": []},
        "payloadHash": ids.content_hash_of(payload),
    }
    return envelope, payload


def _paths_from(args):
    root = getattr(args, "state_root", None)
    return paths_module.RuntimePaths(root) if root else paths_module.default_paths()


def _clock_from(args):
    """A manual clock when --now was given and explicitly permitted.

    Gated by an environment variable for the same reason crash simulation is:
    an operator tool that can rewrite what time the runtime believes it is must
    not be reachable by accident. With the gate unset the flag is refused
    rather than ignored -- ignoring it would silently produce a run stamped
    with a different time than the operator asked for.
    """
    now = getattr(args, "now", None)
    if not now:
        return None
    if os.environ.get(CLOCK_OVERRIDE_ENV) != "1":
        runtime_errors.fail(
            "--now was given but %s is not set to 1; the runtime refuses to "
            "operate on an overridden clock unless that is explicit"
            % (CLOCK_OVERRIDE_ENV,),
            runtime_errors.RuntimeError_,
        )
    return clock_module.ManualClock(now)


def _open_readonly(args):
    """A connection for a report command, refused unless the schema is current.

    status, audit, verify and failures deliberately do NOT take the process
    lock, so they must not migrate: a migration outside the single-writer lock
    could run concurrently with a live runtime. Reading a pre-v2 database
    instead would mean querying tables that do not exist there.

    So the read commands FAIL CLOSED with an actionable message, in the same
    shape `open_database` already uses for an absent database. `init` takes the
    lock and migrates; these commands do not pretend to.
    """
    paths = _paths_from(args)
    connection = store.open_database(paths, create=False)
    try:
        version = schema_module.current_version(connection)
    except Exception:
        connection.close()
        raise
    if version < schema_module.SCHEMA_VERSION:
        connection.close()
        runtime_errors.fail(
            "runtime state at %s is schema version %d; this build reads version "
            "%d. Run `init` to migrate it -- that path takes the single-writer "
            "lock, which a report command deliberately does not."
            % (paths.root, version, schema_module.SCHEMA_VERSION),
            runtime_errors.SchemaVersionError,
        )
    return paths, connection


def _open(args, create=True):
    """An UNOPENED runtime. The caller's `with` opens and closes it exactly once."""
    return orchestrator_module.Orchestrator(
        paths=_paths_from(args),
        clock=_clock_from(args),
        crash_at=getattr(args, "simulate_crash_at", None),
        create=create)


def cmd_init(args):
    with _open(args) as runtime:
        outcomes = runtime.register_builtin_capabilities()
        print("initialized state root : %s" % runtime.paths.root)
        print("schema version         : %d" % schema_module.SCHEMA_VERSION)
        for manifest in orchestrator_module.BUILTIN_CAPABILITIES:
            capability_id = manifest["capabilityId"]
            policy = registry.resolve_retry_policy(manifest)
            print("capability %-46s %-11s effect=%s  retry=base%dms x%d "
                  "cap%dms jitter%dms limit%d"
                  % (capability_id, outcomes.get(capability_id, "unknown"),
                     manifest.get("effectClass", registry.DEFAULT_EFFECT_CLASS),
                     policy["backoffBaseMs"], policy["backoffMultiplier"],
                     policy["backoffCapMs"], policy["jitterMs"],
                     policy["attemptLimit"]))
    return 0


def cmd_submit(args):
    with _open(args) as runtime:
        runtime.recover()
        if getattr(args, "demo_policy", None):
            source_id = ids.make_source_id(
                "example", "https://example.test/%s" % (args.demo_policy,))
            envelope, payload = build_policy_demo_command(
                source_id, "policy-gate demonstration: %s" % (args.demo_policy,))
            print("sourceId=%s" % (source_id,))
        elif getattr(args, "demo_retry", None) is not None:
            envelope, payload = build_retry_demo_command(
                args.demo_retry,
                "MOGO-011 Step 2 retry demonstration, failUntilAttempt=%d"
                % (args.demo_retry,))
        elif args.demo:
            envelope, payload = build_demo_command()
        else:
            with open(args.command_file, "r", encoding="utf-8") as handle:
                document = json.load(handle)
            envelope, payload = document["command"], document["payload"]
        outcome = runtime.submit(envelope, payload)
        for line in runtime.trace:
            print("  " + line)
        if outcome.status == "accepted":
            print("ACCEPTED command=%s workflow=%s task=%s"
                  % (outcome.command_id, outcome.workflow_id, outcome.task_id))
            print("idempotencyKey=%s" % outcome.idempotency_key)
            return 0
        if outcome.status == "duplicate_suppressed":
            print("DUPLICATE SUPPRESSED existing command=%s task=%s"
                  % (outcome.command_id, outcome.task_id))
            print("tasks created=0 events appended=0")
            return 0
        print("REJECTED %s" % outcome.reason)
        return 2


def cmd_run(args):
    with _open(args, create=False) as runtime:
        recovery = runtime.recover()
        if recovery["quarantined"]:
            print("RECOVERED quarantined torn append -> %s" % recovery["quarantined"])
        if recovery["replayed"]:
            print("RECOVERED replayed %d event(s)" % recovery["replayed"])
        if recovery["reclaimed"]:
            print("RECOVERED reclaimed %d task(s): %s"
                  % (len(recovery["reclaimed"]),
                     ", ".join("%s (%s)"
                               % (task_id,
                                  recovery["reclaim_reasons"].get(task_id, "?"))
                               for task_id in recovery["reclaimed"])))
        if recovery["live_leases_kept"]:
            print("RECOVERED left %d task(s) alone -- lease still live"
                  % len(recovery["live_leases_kept"]))
        if recovery["resumed_commands"]:
            print("RECOVERED resumed %d command(s) with no task"
                  % len(recovery["resumed_commands"]))
        report = runtime.run_once()
        for line in runtime.trace:
            print("  " + line)
        pending = _pending_retries(runtime.connection)
        for task_id, eligible_at, remaining in pending:
            print("  RETRY NOT RELEASED task %s eligible at %s (%d ms remaining)"
                  % (task_id, eligible_at, remaining))
        print("advanced=%d succeeded=%d failed=%d retried=%d released=%d "
              "deadLettered=%d"
              % (len(report["advanced"]), len(report["succeeded"]),
                 len(report["failed"]), len(report["retried"]),
                 len(report["released"]), len(report["dead_lettered"])))
        # The exit code reflects TERMINAL failure only. A task that failed and
        # was rescheduled has not failed the run -- treating an intermediate
        # `failed` as a run failure would report every successful retry as an
        # error, which is exactly the signal an operator must be able to trust.
        return 0 if not report["dead_lettered"] else 3


def _pending_retries(connection):
    """Scheduled retries not yet eligible, with the time still to wait.

    Printed so that the backoff being ENFORCED is visible in ordinary operator
    output rather than only in a test assertion.
    """
    now_ms = clock_module.SystemClock().now_ms()
    rows = connection.execute(
        "SELECT task_id, retry_eligible_at FROM tasks "
        "WHERE state = 'retry_scheduled' AND terminal = 0 "
        "AND retry_eligible_at IS NOT NULL ORDER BY retry_eligible_at").fetchall()
    pending = []
    for row in rows:
        eligible_ms = clock_module.parse_iso8601_ms(row["retry_eligible_at"],
                                                    "retryEligibleAt")
        pending.append((row["task_id"], row["retry_eligible_at"],
                        max(0, eligible_ms - now_ms)))
    return pending


# ---------------------------------------------------------------------------
# MOGO-016 -- the one command a host schedule is permitted to invoke
# ---------------------------------------------------------------------------
# Resolved from this file's own location, never from an absolute literal, an
# argument or an environment variable. A scheduled job therefore cannot be
# pointed at a different spec by editing a plist.
_CLI_DIR = os.path.dirname(os.path.abspath(__file__))
APPROVED_COLLECTION_SPEC = os.path.join(
    _CLI_DIR, "..", "..", "..", "scheduling", "approved-collection.json")


def load_approved_collection_entries():
    """The committed collection set, validated IN FULL. Read-only.

    The whole set is validated before this returns, so a malformed or
    unapproved entry refuses the window before a single acquisition is issued.
    """
    with open(os.path.abspath(APPROVED_COLLECTION_SPEC), "r",
              encoding="utf-8") as handle:
        document = json.load(handle)
    return scheduled_collection.validate_collection_set(document)


def cmd_collect(args):
    """One bounded, scheduled, governed research collection window.

    THE ENTIRE SURFACE A HOST SCHEDULE TOUCHES. It takes no source, no URL, no
    resource and no capability -- there is nothing to pass, so there is nothing
    to inject. The entries are the committed file above, and every destination
    is derived by the connector gate from the source identity in each one.

    MOGO-018 Step 3B: the file is a bounded SET, and this iterates it. The
    invariant an operator should be able to state in one line:

        one window issues AT MOST ONE acquisition per committed entry.

    Nothing is discovered, nothing is added at runtime, and no link inside
    acquired content is ever followed -- so N is decided entirely by the
    committed file. Entries are processed in committed order, sequentially, and
    the WHOLE SET is validated before any of it is submitted.

    Submit and run share ONE process lock for the whole window rather than
    taking it per entry, which closes the gap in which a second scheduled
    invocation could slip between an accepted command and its execution.

    `--dry-run` builds and validates every entry and prints its identity WITHOUT
    submitting anything and WITHOUT touching the network -- the safe way for an
    operator to inspect what the schedule will do.
    """
    entries = load_approved_collection_entries()
    clock = _clock_from(args) or clock_module.SystemClock()
    now_ms, now_iso = clock.now_ms(), clock.now_iso()

    built = []
    for entry in entries:
        envelope, payload, window = scheduled_collection.build_command(
            entry, now_ms, now_iso)
        built.append((entry, envelope, payload, window))

    print("COLLECT WINDOW -- %d approved entr%s, at most one acquisition each"
          % (len(built), "y" if len(built) == 1 else "ies"))
    for entry, envelope, _payload, window in built:
        print("  %s / %s  operation=%s"
              % (entry["sourceId"], entry["resourceId"], entry["operation"]))
        print("      capability=%s" % (entry["capabilityId"],))
        print("      window=%s (%d s)" % (window,
                                          entry["collectionWindowSeconds"]))
        print("      idempotencyKey=%s" % (envelope["idempotencyKey"],))
        print("      issuedBy=%s issuedAt=%s"
              % (envelope["issuedBy"], envelope["issuedAt"]))

    if getattr(args, "dry_run", False):
        print("DRY RUN -- nothing was submitted, nothing was acquired")
        return 0

    rejected = False
    with _open(args, create=False) as runtime:
        runtime.recover()
        for entry, envelope, payload, _window in built:
            stream = "%s / %s" % (entry["sourceId"], entry["resourceId"])
            outcome = runtime.submit(envelope, payload)
            for line in runtime.trace:
                print("  " + line)
            if outcome.status == "duplicate_suppressed":
                # The window did its job: a catch-up run after wake, a second
                # firing, or a manual kickstart inside one collection occasion
                # is the SAME REQUEST, and the source is not contacted again.
                print("DUPLICATE SUPPRESSED %s -- same collection window, no "
                      "acquisition performed (existing command=%s task=%s)"
                      % (stream, outcome.command_id, outcome.task_id))
            elif outcome.status == "accepted":
                print("ACCEPTED %s command=%s workflow=%s task=%s"
                      % (stream, outcome.command_id, outcome.workflow_id,
                         outcome.task_id))
            else:
                print("REJECTED %s %s" % (stream, outcome.reason))
                rejected = True

        # ONE run drives every task this window queued. The orchestrator already
        # executes them sequentially under the lock it is holding, so no batch
        # runner, worker pool or queue architecture is needed or wanted.
        report = runtime.run_once()
        for line in runtime.trace:
            print("  " + line)
        print("advanced=%d succeeded=%d failed=%d retried=%d released=%d "
              "deadLettered=%d"
              % (len(report["advanced"]), len(report["succeeded"]),
                 len(report["failed"]), len(report["retried"]),
                 len(report["released"]), len(report["dead_lettered"])))
        if report["dead_lettered"]:
            return 3
    return 2 if rejected else 0


def cmd_corpus(args):
    """MOGO-018 Step 3D: what the autonomous research system possesses.

    A READ, and nothing else. No network, no acquisition, no trading action, no
    write -- generating this report cannot change what it describes, and running
    it twice over unchanged evidence produces identical output.

    IT REPORTS FACTS AND MAKES NO JUDGEMENT. Counts, timestamps and presence
    checks only. Nothing here says a corpus is ready, mature, valid, good, bad
    or profitable, and there is no field in which such a verdict could be put.
    """
    with open(os.path.abspath(research_library.ATTRIBUTION_PATH), "r",
              encoding="utf-8") as handle:
        attribution = json.load(handle)
    paths, connection = _open_readonly(args)
    try:
        report = research_library.corpus_report(connection, attribution)
        if getattr(args, "json", False):
            print(json.dumps(report, indent=2, sort_keys=True))
            return 0

        print("MOGO autonomous research corpus -- READ-ONLY OBSERVABILITY")
        print("  lane=%s  promotionStatus=%s" % (report["lane"],
                                                 report["promotionStatus"]))
        totals = report["totals"]
        print("  streams=%d (attributed %d, unattributed %d)  "
              "acceptedObservations=%d  immutableArtifacts=%d"
              % (totals["streams"], totals["attributedStreams"],
                 totals["unattributedStreams"], totals["acceptedObservations"],
                 totals["artifacts"]))

        print("\n  ── BY STRATEGY FAMILY (deterministic counts, not a verdict) ──")
        for bucket in report["corpora"]:
            print("  %s   trader=%s" % (bucket["strategyFamilyId"],
                                        bucket["traderId"] or "(none)"))
            print("      approved resources=%d  accepted observations=%d  "
                  "immutable artifacts=%d  distinct content identities=%d"
                  % (bucket["distinctApprovedResources"],
                     bucket["acceptedObservations"], bucket["artifacts"],
                     bucket["distinctContentIdentities"]))
            print("      first=%d  unchanged=%d  changed=%d  "
                  "classification not recorded=%d"
                  % (bucket["firstObservationCount"],
                     bucket["unchangedObservations"],
                     bucket["changedObservations"],
                     bucket["classificationNotRecorded"]))
            print("      observed %s -> %s" % (bucket["observedFrom"] or "(none)",
                                               bucket["observedTo"] or "(none)"))
            print("      acquisition provenance: complete=%d incomplete=%d   "
                  "integrity=%s"
                  % (bucket["provenanceCompleteObservations"],
                     bucket["provenanceIncompleteObservations"],
                     bucket["integrityStatus"]))

        print("\n  ── BY STREAM ──")
        for stream in report["streams"]:
            print("  %s / %s" % (stream["sourceId"], stream["resourceId"]))
            print("      trader=%s  families=%s  [%s]"
                  % (stream["traderId"] or "(none)",
                     ",".join(stream["strategyFamilyIds"]) or "(none)",
                     stream["attributionStatus"]))
            auth = stream["authorization"]
            print("      authorization=%s%s  operations=%s"
                  % (auth["status"],
                     "" if auth["problem"] is None else " (%s)" % auth["problem"],
                     ",".join(auth["permittedOperations"]) or "none"))
            obs = stream["observations"]
            print("      observations: recorded=%d accepted=%d notAccepted=%d"
                  % (obs["recorded"], obs["accepted"], obs["notAccepted"]))
            counts = stream["classifications"]
            print("      classifications: FIRST_OBSERVATION=%d UNCHANGED=%d "
                  "CHANGED=%d NOT_RECORDED=%d"
                  % (counts["FIRST_OBSERVATION"], counts["UNCHANGED"],
                     counts["CHANGED"],
                     counts[research_library.CLASSIFICATION_NOT_RECORDED]))
            print("      latest: %s at %s"
                  % (stream["latestClassification"] or "(not recorded)",
                     stream["lastAcceptedAt"] or "(none)"))
            print("      latest content identity=%s (%s)"
                  % ((stream["latestContentIdentity"] or "(none)")[:16] + "...",
                     stream["contentIdentityBasis"]))
            print("      immutable artifacts=%d  %s"
                  % (stream["artifactCount"],
                     ",".join(stream["artifactIds"]) or "(none)"))
            prov = stream["acquisitionProvenance"]
            print("      acquisition provenance: complete=%d incomplete=%d "
                  "networkAccess=%d"
                  % (prov["completeObservations"], prov["incompleteObservations"],
                     prov["networkAccessObservations"]))
            if prov["missingFields"]:
                print("        missing on some observations: %s"
                      % (", ".join(prov["missingFields"]),))
            integrity = stream["integrity"]
            print("      integrity=%s  comparisonStreamMismatches=%d  "
                  "historyChainBreaks=%d  acceptedWithoutArtifact=%d"
                  % (integrity["status"], integrity["comparisonStreamMismatches"],
                     integrity["historyChainBreaks"],
                     integrity["acceptedObservationsWithoutArtifact"]))

        print("\n  NOTE ON PROVENANCE. Acquisition provenance above is derived "
              "from the authoritative")
        print("  acquisition records, NOT from the research-artifact wrapper. "
              "The wrapper carries")
        print("  acquisitionPerformed=false / networkAccessPerformed=false "
              "because those fields")
        print("  describe the INGEST step; they are not a statement about "
              "whether the governed")
        print("  acquisition opened a socket. See MOGO-018 Step 3D.")
        print("\n  presence in a corpus is ORGANIZATION, NOT VALIDATION -- no "
              "number above is a")
        print("  claim that any strategy is ready, valid or profitable.")
        return 0
    finally:
        connection.close()


def cmd_library(args):
    """MOGO-018: the derived research library index.

    A READ. It writes nothing, and running it twice on unchanged input produces
    identical output -- the index is derived state, never a source of truth, so
    there is deliberately no `rebuild` to run.
    """
    with open(os.path.abspath(research_library.ATTRIBUTION_PATH), "r",
              encoding="utf-8") as handle:
        attribution = json.load(handle)
    paths, connection = _open_readonly(args)
    try:
        index = research_library.entries(connection, attribution)
        summary = research_library.corpus_summary(connection, attribution)
        if getattr(args, "json", False):
            print(json.dumps({"entries": index, "corpusSummary": summary},
                             indent=2, sort_keys=True))
            return 0
        print("MOGO research library (DERIVED -- organization, not validation)")
        print("  entries : %d" % (len(index),))
        for entry in index:
            print("  %s / %s" % (entry["sourceId"], entry["resourceId"]))
            print("      trader=%s  families=%s  [%s]"
                  % (entry["traderId"] or "(none)",
                     ",".join(entry["strategyFamilyIds"]) or "(none)",
                     entry["attributionStatus"]))
            print("      artifact=%s" % (entry["artifactId"],))
            print("      acceptedContentIdentity=%s (%s)"
                  % (entry["acceptedContentIdentity"][:16] + "...",
                     entry["acceptedContentIdentityBasis"]))
            print("      accepted observations=%d  distinct identities=%d  last=%s"
                  % (entry["acceptedObservationCount"],
                     entry["distinctAcceptedContentIdentities"],
                     entry["lastClassification"] or "(none)"))
        print("  corpus by strategy family:")
        for bucket in summary:
            print("      %-34s streams=%d observations=%d identities=%d"
                  % (bucket["strategyFamilyId"], bucket["streams"],
                     bucket["acceptedObservations"],
                     bucket["distinctContentIdentities"]))
        print("  lane=RESEARCH  promotionStatus=NOT_A_TRADING_RULE -- presence in "
              "a corpus is NOT a claim of validity")
        return 0
    finally:
        connection.close()


def cmd_authorize(args):
    """Record one governance-supplied Acquisition Authorization Record.

    The platform records and enforces decisions supplied by governance or legal
    review; it never makes one (Constitution section 5.9). This command is the
    only way a record enters the runtime.
    """
    with open(args.file, "r", encoding="utf-8") as handle:
        record = json.load(handle)
    with _open(args, create=False) as runtime:
        outcome = runtime.record_authorization(record)
        print("AUTHORIZATION %s  %s  %s  status=%s  operations=%s"
              % (outcome.upper(), record.get("authorizationId"),
                 record.get("sourceId"), record.get("policyStatus"),
                 ",".join(record.get("permittedOperations") or []) or "none"))
    return 0


def cmd_review(args):
    """The audited operator decision that disposes of a policy-blocked task.

    Constitution section 9: reviewer identity, decision, reason, timestamp and
    policy version are all recorded, and a bare approval is refused.
    """
    with _open(args, create=False) as runtime:
        runtime.recover()
        runtime.record_review_decision(args.task, args.decision, args.reason,
                                       args.reviewer, args.policy_version)
        for line in runtime.trace:
            print("  " + line)
        row = runtime.connection.execute(
            "SELECT state, terminal FROM tasks WHERE task_id = ?",
            (args.task,)).fetchone()
        print("REVIEW %s task=%s -> state=%s terminal=%s by %s"
              % (args.decision.upper(), args.task, row["state"],
                 bool(row["terminal"]), args.reviewer))
    return 0


def cmd_policy(args):
    """What the policy gate decided, what is authorized, and what is blocked."""
    paths, connection = _open_readonly(args)
    try:
        log = event_log_module.EventLog(paths)
        report = audit_module.policy_report(connection, log)
        if getattr(args, "json", False):
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            print(audit_module.render_policy(report))
        return 0
    finally:
        connection.close()


def cmd_failures(args):
    """Architecture section 23's Failures view: what failed, when, and why.

    Constitution section 13 requires an operator to answer that WITHOUT READING
    CODE. This is the command that has to meet the bar.
    """
    paths, connection = _open_readonly(args)
    try:
        log = event_log_module.EventLog(paths)
        report = audit_module.failures_report(connection, log)
        if getattr(args, "json", False):
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            print(audit_module.render_failures(report))
        return 0
    finally:
        connection.close()


def cmd_status(args):
    paths, connection = _open_readonly(args)
    try:
        log = event_log_module.EventLog(paths)
        print(audit_module.render_status(
            audit_module.status_report(connection, log, paths)))
    finally:
        connection.close()
    return 0


def cmd_audit(args):
    paths, connection = _open_readonly(args)
    try:
        log = event_log_module.EventLog(paths)
        report = audit_module.audit_report(connection, log, args.workflow, args.task)
        if args.json:
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            print(audit_module.render_audit(report))
        return 0 if not [f for f in report["integrity"]
                         if f["severity"] in ("FATAL", "ERROR")] else 4
    finally:
        connection.close()


def cmd_verify(args):
    paths, connection = _open_readonly(args)
    try:
        log = event_log_module.EventLog(paths)
        findings = audit_module.verify_integrity(connection, log)
        if not findings:
            print("INTEGRITY OK -- log parses, validates, hashes; index agrees")
            return 0
        for finding in findings:
            print("%-8s %s" % (finding["severity"], finding["finding"]))
        return 4
    finally:
        connection.close()


def cmd_reset(args):
    paths = _paths_from(args)
    if args.rebuild_index:
        # The executable proof of ADR-012 D-05: throw the index away and
        # reconstruct it from the log alone. If this works, the log is the truth.
        with orchestrator_module.Orchestrator(paths=paths, create=False) as rt:
            result = projection.rebuild(rt.connection, rt.log, rt.paths.root)
            print("REBUILT index from the log alone: %d event(s) scanned, "
                  "%d transition(s) applied" % (result["scanned"], result["applied"]))
        return 0
    if not args.confirm:
        print("refusing to delete runtime state without --confirm")
        return 2
    paths.assert_inside_state_root(paths.root, purpose="reset")
    for name in (paths.events_dir, paths.index_dir, paths.tasks_dir,
                 paths.quarantine_dir):
        paths.assert_inside_state_root(name, purpose="reset")
        if os.path.isdir(name):
            shutil.rmtree(name)
    if os.path.exists(paths.lock_file):
        paths.assert_inside_state_root(paths.lock_file, purpose="reset")
        os.remove(paths.lock_file)
    paths_module.ensure_state_root(paths)
    print("RESET runtime state under %s" % paths.root)
    return 0


def _submit_args(args, demo=False, demo_retry=None, demo_policy=None):
    return argparse.Namespace(
        demo=demo, demo_retry=demo_retry, demo_policy=demo_policy,
        command_file=None, state_root=getattr(args, "state_root", None),
        simulate_crash_at=None, now=None)


def _run_args(args):
    return argparse.Namespace(state_root=getattr(args, "state_root", None),
                              simulate_crash_at=None, now=None)


def _scenario_step_1(args):
    """Retryable failure, backoff, release, success on a later attempt."""
    print("\n-- SCENARIO 1: retryable failure -> retry -> success on attempt 2 --")
    rc = cmd_submit(_submit_args(args, demo_retry=1))
    return rc or cmd_run(_run_args(args))


def _scenario_step_2(args):
    """Attempts exhausted -> dead-letter, with a complete history."""
    print("\n-- SCENARIO 2: attempts exhausted -> dead-letter --")
    rc = cmd_submit(_submit_args(args, demo_retry=9))
    if rc:
        return rc
    # A dead-lettered task is a TERMINAL FAILURE and `run` reports it as one,
    # so a non-zero exit here is the correct outcome of the scenario rather
    # than a fault in it.
    cmd_run(_run_args(args))
    return 0


def _scenario_step_3(args):
    """The same semantic command must still duplicate nothing.

    Submitted, driven to completion, then submitted AGAIN. The second
    submission carries fresh identifiers and an identical semantic payload, so
    its idempotency key is identical -- which is the property Step 2 must not
    have weakened, because the key is computed from the payload alone and
    never from an attempt number or a timestamp.
    """
    print("\n-- SCENARIO 3: re-running a semantic command duplicates nothing --")
    rc = cmd_submit(_submit_args(args, demo=True))
    if rc:
        return rc
    rc = cmd_run(_run_args(args))
    if rc:
        return rc
    print("   ... now submitting the identical semantic command a second time:")
    return cmd_submit(_submit_args(args, demo=True))


def _scenario_step_policy(args):
    """The policy gate: denied, blocked, disposed of by an audited human."""
    print("\n-- SCENARIO 4: acquisition is IMPOSSIBLE without authorization --")
    source = ids.make_source_id("example", "https://example.test/mogo-011-step-3")
    envelope, payload = build_policy_demo_command(
        source, "MOGO-011 Step 3 policy gate demonstration")
    root = getattr(args, "state_root", None)

    with orchestrator_module.Orchestrator(paths=_paths_from(args),
                                          create=False) as runtime:
        runtime.recover()
        outcome = runtime.submit(envelope, payload)
        runtime.run_once()
        for line in runtime.trace:
            print("  " + line)
        row = runtime.connection.execute(
            "SELECT state, policy_decision, policy_reason FROM tasks "
            "WHERE task_id = ?", (outcome.task_id,)).fetchone()
        print("  DENIED  state=%s  reason=%s" % (row["state"], row["policy_reason"]))
        print("          nothing was claimed, nothing executed, nothing acquired")

    print("\n-- SCENARIO 5: governance authorizes, a human releases, work runs --")
    with orchestrator_module.Orchestrator(paths=_paths_from(args),
                                          create=False) as runtime:
        runtime.record_authorization({
            "authorizationId": ids.new_uuid4(),
            "sourceId": source,
            "policyStatus": "PERMITTED_PUBLIC_METADATA",
            "policyVersion": "1.0",
            "decisionAuthority": "governance:mogo-legal",
            "decidedAt": orchestrator_module.utc_now(),
            "permittedOperations": ["metadata"],
        })
        runtime.record_review_decision(
            outcome.task_id, "approved",
            "authorization recorded by governance after review", "operator:mogo")
        runtime.run_once()
        for line in runtime.trace:
            print("  " + line)
        row = runtime.connection.execute(
            "SELECT state, policy_decision, policy_status FROM tasks "
            "WHERE task_id = ?", (outcome.task_id,)).fetchone()
        print("  RELEASED state=%s  policy=%s  status=%s"
              % (row["state"], row["policy_decision"], row["policy_status"]))
    return 0


def _scenario_step_4(args):
    """The log is the truth: throw the index away and rebuild it."""
    print("\n-- SCENARIO 6: the log is the truth --")
    rc = cmd_reset(argparse.Namespace(
        state_root=getattr(args, "state_root", None),
        confirm=False, rebuild_index=True))
    if rc:
        return rc
    return cmd_verify(argparse.Namespace(
        state_root=getattr(args, "state_root", None)))


def _scenario_step_5(args):
    """What failed, when, and why -- without reading code."""
    print("\n-- OPERATOR VIEW: policy decisions, authorizations and gates --")
    cmd_policy(argparse.Namespace(state_root=getattr(args, "state_root", None),
                                  json=False))
    print("\n-- OPERATOR VIEW: failures, leases and gates --")
    return cmd_failures(argparse.Namespace(
        state_root=getattr(args, "state_root", None), json=False))


DEMO_SCENARIOS = {
    "retry": (_scenario_step_1,),
    "dead-letter": (_scenario_step_2,),
    "policy": (_scenario_step_policy,),
    "all": (_scenario_step_1, _scenario_step_2, _scenario_step_3,
            _scenario_step_policy, _scenario_step_4, _scenario_step_5),
}


def cmd_demo(args):
    """The MOGO-011 Step 2 outcomes, in order, in one command."""
    scenario = getattr(args, "scenario", None) or "all"
    print("=" * 72)
    print("MOGO-011 Step 2 -- retry, lease and dead-letter demonstration")
    print("=" * 72)
    rc = cmd_init(args)
    if rc:
        return rc
    for step in DEMO_SCENARIOS[scenario]:
        rc = step(args)
        if rc:
            return rc
    if scenario == "all":
        print("\n-- AUDIT --")
        rc = cmd_audit(argparse.Namespace(
            workflow=None, task=None, json=False,
            state_root=getattr(args, "state_root", None)))
        print(
            "\nNOT SHOWN HERE, AND WHY:"
            "\n  * Restart after an induced interruption is exercised by "
            "tests/platform/test_runtime_recovery.py and by "
            "`run --simulate-crash-at <boundary>`."
            "\n  * A retry being WITHHELD until its backoff elapses cannot be "
            "shown by this demonstration: the fail-then-succeed capability "
            "declares backoffBaseMs=0 by design, so that the demonstration "
            "needs no clock manipulation, and a zero backoff is eligible at "
            "once. Registering a third capability solely to make the demo "
            "print a wait would be inventing a capability to satisfy a "
            "demonstration. The rule is proved instead against a non-zero "
            "backoff with an injected clock, in "
            "tests/platform/test_runtime_retry.py.")
    return rc


def build_parser():
    parser = argparse.ArgumentParser(
        prog="mogo_runtime",
        description="MOGO Automation Platform runtime kernel (MOGO-011 Step 1).")
    parser.add_argument("--state-root", help="override the runtime state root")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init", help="create state root, schema and registry")

    submit = subparsers.add_parser("submit", help="accept one governed command")
    group = submit.add_mutually_exclusive_group(required=True)
    group.add_argument("--demo", action="store_true",
                       help="submit the canonical demonstration command")
    group.add_argument("--demo-retry", type=int, metavar="FAIL_UNTIL_ATTEMPT",
                       help="submit a fail-then-succeed command that fails every "
                            "attempt up to and including this one")
    group.add_argument("--demo-policy", metavar="LABEL",
                       help="submit an acquisition-class command for the policy "
                            "gate; the subject source is derived from LABEL and "
                            "printed as sourceId=")
    group.add_argument("--command-file",
                       help="JSON file with {\"command\": ..., \"payload\": ...}")
    submit.add_argument("--simulate-crash-at",
                        help="test-only induced interruption boundary")

    run = subparsers.add_parser("run", help="recover, then drive tasks to terminal")
    run.add_argument("--simulate-crash-at",
                     help="test-only induced interruption boundary")
    run.add_argument("--now", metavar="ISO8601",
                     help="test-only clock override; requires %s=1"
                          % (CLOCK_OVERRIDE_ENV,))

    subparsers.add_parser("status", help="health snapshot")

    audit_parser = subparsers.add_parser("audit", help="complete activity record")
    audit_parser.add_argument("--workflow")
    audit_parser.add_argument("--task")
    audit_parser.add_argument("--json", action="store_true")

    failures = subparsers.add_parser(
        "failures", help="what failed, when, and why -- plus leases and gates")
    failures.add_argument("--json", action="store_true")

    collect = subparsers.add_parser(
        "collect",
        help="one bounded scheduled governed collection from the FIXED approved "
             "source; takes no source, URL or capability argument")
    collect.add_argument("--dry-run", action="store_true",
                         help="build and validate the command, print its "
                              "identity, submit nothing and acquire nothing")
    collect.add_argument("--now", metavar="ISO8601",
                         help="test-only clock override; requires %s=1"
                              % (CLOCK_OVERRIDE_ENV,))

    authorize = subparsers.add_parser(
        "authorize",
        help="record a governance-supplied Acquisition Authorization Record")
    authorize.add_argument("--file", required=True,
                           help="JSON file holding one authorization record")

    review = subparsers.add_parser(
        "review", help="audited operator disposition of a policy-blocked task")
    review.add_argument("--task", required=True)
    review.add_argument("--decision", required=True,
                        choices=("approved", "rejected"))
    review.add_argument("--reason", required=True,
                        help="required -- a decision without a reason is invalid")
    review.add_argument("--reviewer", required=True,
                        help="operator:<id> | governance:<role> | legal:<role>")
    review.add_argument("--policy-version", dest="policy_version")
    review.add_argument("--simulate-crash-at",
                        help="test-only induced interruption boundary")

    policy_parser = subparsers.add_parser(
        "policy", help="policy decisions, authorizations, and what is blocked")
    policy_parser.add_argument("--json", action="store_true")

    library = subparsers.add_parser(
        "library", help="the DERIVED research library index (read-only)")
    library.add_argument("--json", action="store_true")

    corpus = subparsers.add_parser(
        "corpus", help="what the autonomous research system possesses, by "
                       "source and strategy family (read-only)")
    corpus.add_argument("--json", action="store_true")

    subparsers.add_parser("verify", help="integrity checks only")

    reset = subparsers.add_parser("reset", help="delete state, or rebuild the index")
    reset.add_argument("--confirm", action="store_true")
    reset.add_argument("--rebuild-index", action="store_true",
                       help="drop the derived index and rebuild it from the log")

    demo = subparsers.add_parser("demo", help="run the full end-to-end demonstration")
    demo.add_argument("--scenario", choices=sorted(DEMO_SCENARIOS),
                      default="all")
    return parser


HANDLERS = {
    "init": cmd_init, "submit": cmd_submit, "run": cmd_run, "status": cmd_status,
    "audit": cmd_audit, "verify": cmd_verify, "reset": cmd_reset, "demo": cmd_demo,
    "failures": cmd_failures, "authorize": cmd_authorize, "review": cmd_review,
    "policy": cmd_policy, "collect": cmd_collect, "library": cmd_library,
    "corpus": cmd_corpus,
}


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return HANDLERS[args.command](args)
    except runtime_errors.RuntimeBusyError as exc:
        print("BUSY %s" % exc, file=sys.stderr)
        return 5
    except runtime_errors.PlatformError as exc:
        print("%s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        return 6

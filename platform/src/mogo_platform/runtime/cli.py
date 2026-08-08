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
    init     create the state root and database, register capabilities
    submit   accept one command (--demo builds the canonical demonstration one)
    run      recover, then drive every non-terminal task to a terminal state
    status   health snapshot
    audit    complete ordered activity record
    verify   integrity checks alone; non-zero exit on any finding
    reset    delete runtime state, or rebuild the index from the log alone
    demo     the full end-to-end demonstration required by MOGO-011
"""

import argparse
import json
import os
import shutil
import sys

from ..contracts import ids  # noqa: E402
from . import audit as audit_module  # noqa: E402
from . import errors as runtime_errors  # noqa: E402
from . import event_log as event_log_module  # noqa: E402
from . import orchestrator as orchestrator_module  # noqa: E402
from . import paths as paths_module  # noqa: E402
from . import projection  # noqa: E402
from . import schema as schema_module  # noqa: E402
from . import store  # noqa: E402
from .capabilities import echo as echo_capability  # noqa: E402

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


def _paths_from(args):
    root = getattr(args, "state_root", None)
    return paths_module.RuntimePaths(root) if root else paths_module.default_paths()


def _open(args, create=True):
    """An UNOPENED runtime. The caller's `with` opens and closes it exactly once."""
    return orchestrator_module.Orchestrator(
        paths=_paths_from(args),
        crash_at=getattr(args, "simulate_crash_at", None),
        create=create)


def cmd_init(args):
    with _open(args) as runtime:
        outcomes = runtime.register_builtin_capabilities()
        print("initialized state root : %s" % runtime.paths.root)
        print("schema version         : %d" % schema_module.SCHEMA_VERSION)
        for capability_id, outcome in sorted(outcomes.items()):
            print("capability %-28s %s" % (capability_id, outcome))
    return 0


def cmd_submit(args):
    with _open(args) as runtime:
        runtime.recover()
        if args.demo:
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
                  % (len(recovery["reclaimed"]), ", ".join(recovery["reclaimed"])))
        if recovery["resumed_commands"]:
            print("RECOVERED resumed %d command(s) with no task"
                  % len(recovery["resumed_commands"]))
        report = runtime.run_once()
        for line in runtime.trace:
            print("  " + line)
        print("advanced=%d succeeded=%d failed=%d"
              % (len(report["advanced"]), len(report["succeeded"]),
                 len(report["failed"])))
        return 0 if not report["failed"] else 3


def cmd_status(args):
    paths = _paths_from(args)
    connection = store.open_database(paths, create=False)
    try:
        log = event_log_module.EventLog(paths)
        print(audit_module.render_status(
            audit_module.status_report(connection, log, paths)))
    finally:
        connection.close()
    return 0


def cmd_audit(args):
    paths = _paths_from(args)
    connection = store.open_database(paths, create=False)
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
    paths = _paths_from(args)
    connection = store.open_database(paths, create=False)
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


def cmd_demo(args):
    """The twelve MOGO-011 outcomes, in order, in one command."""
    print("=" * 72)
    print("MOGO-011 Step 1 -- runtime kernel end-to-end demonstration")
    print("=" * 72)
    rc = cmd_init(args)
    if rc:
        return rc
    print("\n-- 1..9  submit, validate, create, policy, claim, execute, succeed --")
    rc = cmd_submit(argparse.Namespace(demo=True, command_file=None,
                                       state_root=getattr(args, "state_root", None),
                                       simulate_crash_at=None))
    if rc:
        return rc
    rc = cmd_run(argparse.Namespace(state_root=getattr(args, "state_root", None),
                                    simulate_crash_at=None))
    if rc:
        return rc
    print("\n-- 10  re-running the same semantic command must duplicate nothing --")
    rc = cmd_submit(argparse.Namespace(demo=True, command_file=None,
                                       state_root=getattr(args, "state_root", None),
                                       simulate_crash_at=None))
    if rc:
        return rc
    print("\n-- 12  audit --")
    rc = cmd_audit(argparse.Namespace(workflow=None, task=None, json=False,
                                      state_root=getattr(args, "state_root", None)))
    print("\n(outcome 11, restart after induced interruption, is exercised by "
          "tests/platform/test_runtime_recovery.py and by "
          "`run --simulate-crash-at`)")
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
    group.add_argument("--command-file",
                       help="JSON file with {\"command\": ..., \"payload\": ...}")
    submit.add_argument("--simulate-crash-at",
                        help="test-only induced interruption boundary")

    run = subparsers.add_parser("run", help="recover, then drive tasks to terminal")
    run.add_argument("--simulate-crash-at",
                     help="test-only induced interruption boundary")

    subparsers.add_parser("status", help="health snapshot")

    audit_parser = subparsers.add_parser("audit", help="complete activity record")
    audit_parser.add_argument("--workflow")
    audit_parser.add_argument("--task")
    audit_parser.add_argument("--json", action="store_true")

    subparsers.add_parser("verify", help="integrity checks only")

    reset = subparsers.add_parser("reset", help="delete state, or rebuild the index")
    reset.add_argument("--confirm", action="store_true")
    reset.add_argument("--rebuild-index", action="store_true",
                       help="drop the derived index and rebuild it from the log")

    subparsers.add_parser("demo", help="run the full end-to-end demonstration")
    return parser


HANDLERS = {
    "init": cmd_init, "submit": cmd_submit, "run": cmd_run, "status": cmd_status,
    "audit": cmd_audit, "verify": cmd_verify, "reset": cmd_reset, "demo": cmd_demo,
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

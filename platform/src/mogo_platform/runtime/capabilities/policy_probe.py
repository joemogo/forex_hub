#!/usr/bin/env python3
"""MOGO Automation Platform -- research.policy.probe.v1.

AUTHORITY
    Automation Platform Constitution v1.0 (senior) -- sections 4, 5, 7, 14
    MOGO-009 Contract Catalog, sections L, M, O
    MOGO-011 Step 3 plan, section 4 · governance decision C-2

WHAT THIS IS, AND WHAT IT IS EMPHATICALLY NOT
    This capability declares `operationClass: acquisition` SO THAT THE POLICY
    GATE ENGAGES. That declaration is its entire reason for existing.

    IT ACQUIRES NOTHING. It opens no socket, resolves no locator, reads no file,
    spawns no process and reaches no network. It performs the same local,
    deterministic normalization the other two capabilities perform, and it is
    `effectClass: pure` like both of them.

    The distinction the declaration expresses is a GOVERNANCE one, not a
    behavioural one: it is the class of work that REQUIRES AUTHORIZATION BEFORE
    IT MAY RUN. Without a capability in that class, the gate's integration with
    the orchestrator could only be unit-tested, and the orchestrator is exactly
    where MOGO-011 Step 3's finding F-1 lived -- a policy path that recorded
    decisions that had not been made and executions that had not happened.

    The same reasoning that justified Step 2's `fail_then_succeed`: the
    parameter under test is real, the capability is inert.

WHY THIS IS SAFE TO EXIST BEFORE ANY CONNECTOR
    Architecture section 32 item 5 places the policy gate BEFORE every
    connector, so that no acquisition path can exist before the control that
    governs it. This capability is the reverse of a connector: it is subject to
    the control while having no acquisition path at all. The boundary tests
    continue to prove -- structurally, over every module under `platform/**` --
    that no network import, no subprocess, no randomness, no clock outside
    `clock.py` and no write outside the state root exists anywhere.

PROHIBITED, RESTATED
    It does not acquire internet data, modify scientific evidence, perform
    replay, paper trade, live trade, modify strategies, ingest educator
    knowledge, or call an external model. It cannot: no such code path exists
    anywhere in the runtime, and the boundary tests prove it.
"""

from ...contracts import ids  # noqa: E402
from .. import errors as runtime_errors  # noqa: E402

CAPABILITY_ID = "CAP|research|policy-probe"
CAPABILITY_NAME = "research.policy.probe.v1"
CAPABILITY_VERSION = "1.0.0"

MAX_PAYLOAD_BYTES = 65536

# The one operation this capability would need authorization for. Declared
# narrowly on purpose: an authorization permitting `metadata` does not permit
# `transcript` or `artifact`, and the gate enforces the difference.
DECLARED_ACQUISITION_OPERATION = "metadata"

MANIFEST = {
    "capabilityId": CAPABILITY_ID,
    "name": CAPABILITY_NAME,
    "version": CAPABILITY_VERSION,
    "owner": "operator:mogo",
    "description": (
        "Policy-gate probe. Declares the acquisition operation class so that "
        "the policy gate evaluates it, and performs NO acquisition of any "
        "kind: it normalizes its payload locally and deterministically, exactly "
        "as the echo capability does. Exists to prove that authorization is "
        "required, recorded and unbypassable before work executes."
    ),
    "acceptedCommands": ["AcquireSourceMetadata"],
    "emittedEvents": ["TaskSucceeded", "TaskFailed"],
    "requiredPermissions": [],
    "requiredConnectors": [],
    "requiredSecretReferences": [],
    "resourceLimits": {"wallClockMs": 5000, "maxPayloadBytes": MAX_PAYLOAD_BYTES},
    "lifecycleStatus": "approved",
    "enabledState": True,
    "compatibility": {"AcquireSourceMetadata": [1]},
    "operationClass": "acquisition",
    "acquisitionOperations": [DECLARED_ACQUISITION_OPERATION],
    "effectClass": "pure",
    "failureClasses": [],
    "requiresExecutionContext": False,
}


def execute(payload):
    """Normalize a JSON-shaped payload and hash it. Pure and deterministic.

    Identical in behaviour to the echo capability. The only thing that
    distinguishes this capability is its declared operation class, which is a
    statement about what governance must approve, not about what this function
    does.
    """
    ids.require_json_shaped(payload, "$capabilityPayload")

    normalized = ids.as_plain(payload)
    canonical = ids.canonical_json_bytes(normalized)
    if len(canonical) > MAX_PAYLOAD_BYTES:
        runtime_errors.fail(
            "payload is %d canonical bytes, exceeding the declared limit of %d"
            % (len(canonical), MAX_PAYLOAD_BYTES),
            runtime_errors.ContractValidationError,
        )

    return {
        "normalizedPayload": normalized,
        "contentHash": ids.sha256_hex(canonical),
        "byteLength": len(canonical),
        "capabilityId": CAPABILITY_ID,
        "capabilityVersion": CAPABILITY_VERSION,
    }

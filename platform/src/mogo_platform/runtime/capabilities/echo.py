#!/usr/bin/env python3
"""MOGO Automation Platform -- research.runtime.echo.v1, the first capability.

AUTHORITY
    Automation Platform Constitution v1.0 (senior) -- sections 4, 7, 14
    ADR-012 (accepted 2026-08-07)                  -- D-09 no secrets in v1
    MOGO-009 Contract Catalog, section O
    MOGO-011 Step 1 plan, section 12

PURPOSE
    Prove the runtime kernel, not obtain anything. This capability exists so
    that a task can be claimed, executed and completed with a result that is
    identical on every run, on every machine, before and after a crash. Its
    determinism is what makes crash boundary 8 -- interrupted between execution
    and recording the success -- safe to resolve by simply running it again.

PURITY IS A CONTRACT, NOT A STYLE CHOICE
    execute() reads no file, opens no socket, spawns no process, reads no clock
    and uses no randomness. It is a function of its argument alone. A test
    asserts byte-identical output across 100 invocations and across a process
    restart, and a static test asserts the module contains no I/O call at all.

    The moment a capability stops being pure, the recovery argument for
    boundary 8 stops holding, and that capability may not be registered until
    output verification and an idempotency-keyed result store exist. That is
    recorded as risk A-5 in the Step 1 plan and is a Step 2 gate.

PROHIBITED, RESTATED
    It does not acquire internet data, modify scientific evidence, perform
    replay, paper trade, live trade, modify strategies, ingest educator
    knowledge, or call an external model. It cannot: no such code path exists
    anywhere in the runtime, and the boundary tests prove it.
"""

from ...contracts import ids  # noqa: E402
from .. import errors as runtime_errors  # noqa: E402

CAPABILITY_ID = "CAP|research|runtime-echo"
CAPABILITY_NAME = "research.runtime.echo.v1"
CAPABILITY_VERSION = "1.0.0"

MAX_PAYLOAD_BYTES = 65536

# Catalog section O record. Every field the dispatch decision reads.
MANIFEST = {
    "capabilityId": CAPABILITY_ID,
    "name": CAPABILITY_NAME,
    "version": CAPABILITY_VERSION,
    "owner": "operator:mogo",
    "description": (
        "Deterministic echo/normalize capability. Returns the canonical form of "
        "its payload and that form's SHA-256. Exists to prove the runtime "
        "kernel end to end; acquires nothing and writes nothing."
    ),
    "acceptedCommands": ["NormalizeArtifact"],
    "emittedEvents": ["TaskSucceeded", "TaskFailed"],
    "requiredPermissions": [],
    "requiredConnectors": [],
    "requiredSecretReferences": [],
    "resourceLimits": {"wallClockMs": 5000, "maxPayloadBytes": MAX_PAYLOAD_BYTES},
    "lifecycleStatus": "production",
    "enabledState": True,
    "compatibility": {"NormalizeArtifact": [1]},
    "operationClass": "non_acquisition",
}


def execute(payload):
    """Normalize a JSON-shaped payload and hash it. Pure and deterministic.

    Returns a mapping with the canonical form, its SHA-256, the canonical byte
    length, and the identity of the capability that produced it -- so a result
    can always be attributed without consulting anything else.

    Fails closed, before doing any work, when the payload is not JSON-shaped or
    exceeds the declared resource limit.
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

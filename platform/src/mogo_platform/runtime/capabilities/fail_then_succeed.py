#!/usr/bin/env python3
"""MOGO Automation Platform -- research.runtime.fail-then-succeed.v1.

AUTHORITY
    Automation Platform Constitution v1.0 (senior) -- sections 4, 7, 11, 14
    MOGO-009 Contract Catalog, sections K and O
    MOGO-011 Step 2 plan, section 16

PURPOSE
    Prove the failure-handling kernel, not obtain anything. This capability
    fails a declared, classified, retryable failure on its early attempts and
    succeeds on a later one, so that a retry can be scheduled under a verified
    backoff, released, re-claimed under a fresh lease, and completed -- with the
    whole sequence reconstructable from the log alone.

    The same capability, given failUntilAttempt >= attemptLimit, fails every
    attempt and dead-letters deterministically. A SECOND always-fail capability
    was considered and rejected: failUntilAttempt is an ordinary declared
    parameter exercised at a different value, not a special mode, and inventing
    a capability to satisfy a test is the failure mode this milestone's design
    principles name explicitly.

THE INVARIANT, AND IT IS THE WHOLE DESIGN
    The DECISION to fail depends on `attempt`. The RESULT CONTENT does not.
    Attempt 2 and attempt 5 produce byte-identical output.

    That is what keeps crash boundary 8 -- interrupted between execution and
    recording success -- safe for this capability under the same argument that
    keeps it safe for echo: re-execution after an interrupted run is
    indistinguishable from never having been interrupted. Were the result to
    carry the attempt number, a crash would become visible in the output and
    the recovery argument would collapse.

    `failUntilAttempt` is part of the SEMANTIC payload and therefore
    participates in the idempotency key, which is why the retry scenario and
    the dead-letter scenario are naturally different tasks with different keys.
    `attempt` arrives in the EXECUTION CONTEXT, which is deliberately not part
    of the payload and never part of the key (Constitution section 11: keys are
    never derived from timestamps or attempt numbers).

PURITY IS A CONTRACT, NOT A STYLE CHOICE
    execute() reads no file, opens no socket, spawns no process, reads no clock
    and uses no randomness. A static AST scan over the capabilities package
    enforces all five, and a test asserts byte-identical output across 100
    invocations and across every attempt that succeeds.

PROHIBITED, RESTATED
    It does not acquire internet data, modify scientific evidence, perform
    replay, paper trade, live trade, modify strategies, ingest educator
    knowledge, or call an external model. It cannot: no such code path exists
    anywhere in the runtime, and the boundary tests prove it.
"""

from ...contracts import ids  # noqa: E402
from .. import errors as runtime_errors  # noqa: E402

CAPABILITY_ID = "CAP|research|runtime-fail-then-succeed"
CAPABILITY_NAME = "research.runtime.fail-then-succeed.v1"
CAPABILITY_VERSION = "1.0.0"

MAX_PAYLOAD_BYTES = 65536

# The one class this capability may report. Declared here and in the manifest,
# and the worker accepts no other from it.
DECLARED_FAILURE_CLASS = "transient"

# The semantic field that decides how many attempts fail. Excluded from the
# result so that the result is attempt-invariant AND parameter-independent in
# shape -- see the module docstring.
FAIL_UNTIL_FIELD = "failUntilAttempt"

DEFAULT_FAIL_UNTIL_ATTEMPT = 1

MANIFEST = {
    "capabilityId": CAPABILITY_ID,
    "name": CAPABILITY_NAME,
    "version": CAPABILITY_VERSION,
    "owner": "operator:mogo",
    "description": (
        "Deterministic fail-then-succeed capability. Reports a declared "
        "retryable failure while the attempt number is at or below its "
        "declared threshold, and otherwise returns the canonical form of its "
        "payload and that form's SHA-256. Exists to prove retry, backoff, "
        "lease and dead-letter handling end to end; acquires nothing and "
        "writes nothing."
    ),
    "acceptedCommands": ["NormalizeArtifact"],
    "emittedEvents": ["TaskSucceeded", "TaskFailed"],
    "requiredPermissions": [],
    "requiredConnectors": [],
    "requiredSecretReferences": [],
    "resourceLimits": {"wallClockMs": 5000, "maxPayloadBytes": MAX_PAYLOAD_BYTES},
    # `approved` rather than `production`: this is an approved demonstration
    # capability, not production work. Saying so honestly also exercises the
    # second dispatchable lifecycle state, which Step 1 never did -- echo is
    # `production`. Coverage gained by being accurate.
    "lifecycleStatus": "approved",
    "enabledState": True,
    "compatibility": {"NormalizeArtifact": [1]},
    "operationClass": "non_acquisition",
    "effectClass": "pure",
    "failureClasses": [DECLARED_FAILURE_CLASS],
    "requiresExecutionContext": True,
    # backoffBaseMs 0 makes the demonstration complete in a single `run` with no
    # sleeping and no clock manipulation. The eligibility rule is enforced
    # identically -- `now >= eligibleAt` with a zero delay is still a real
    # check -- and the tests use a non-zero base with a manual clock to prove
    # the rule bites. Both are real; neither is a shortcut.
    "retryPolicy": {"attemptLimit": 3, "backoffBaseMs": 0, "backoffMultiplier": 2,
                    "backoffCapMs": 60000, "jitterMs": 0},
}


def execute(payload, context=None):
    """Fail while the attempt is at or below the threshold; otherwise normalize.

    Fails closed, before doing any work, when the payload is not JSON-shaped,
    when the threshold is not a non-negative integer, or when the canonical
    payload exceeds the declared resource limit.
    """
    ids.require_json_shaped(payload, "$capabilityPayload")

    plain = ids.as_plain(payload)
    fail_until = plain.get(FAIL_UNTIL_FIELD, DEFAULT_FAIL_UNTIL_ATTEMPT)
    if isinstance(fail_until, bool) or not isinstance(fail_until, int) \
            or fail_until < 0:
        runtime_errors.fail(
            "%s must be a non-negative integer, got %r"
            % (FAIL_UNTIL_FIELD, fail_until),
            runtime_errors.ContractValidationError,
        )

    attempt = 0 if context is None else context.get("attempt", 0)
    if attempt <= fail_until:
        runtime_errors.fail_capability(
            DECLARED_FAILURE_CLASS,
            "declared deterministic failure on attempt %d of at most %d"
            % (attempt, fail_until),
        )

    # The threshold is removed from the result, so the success output is
    # identical for every attempt that reaches it AND carries no trace of the
    # failure history. Attempt-invariance is asserted directly by test across
    # attempts 2 through 10.
    semantic = {key: value for key, value in plain.items()
                if key != FAIL_UNTIL_FIELD}
    canonical = ids.canonical_json_bytes(semantic)
    if len(canonical) > MAX_PAYLOAD_BYTES:
        runtime_errors.fail(
            "payload is %d canonical bytes, exceeding the declared limit of %d"
            % (len(canonical), MAX_PAYLOAD_BYTES),
            runtime_errors.ContractValidationError,
        )

    return {
        "normalizedPayload": semantic,
        "contentHash": ids.sha256_hex(canonical),
        "byteLength": len(canonical),
        "capabilityId": CAPABILITY_ID,
        "capabilityVersion": CAPABILITY_VERSION,
    }

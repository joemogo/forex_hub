#!/usr/bin/env python3
"""MOGO Automation Platform -- idempotency-keyed capability result store.

AUTHORITY
    Constitution section 11 -- idempotency keys are never derived from
    timestamps or attempt numbers
    MOGO-011 Step 1 plan, risk A-5
    MOGO-014 Step 2 authorization

WHY THIS EXISTS

    Crash boundary 8 is the interruption between performing an effect and
    recording that it succeeded. Until MOGO-014 that boundary was safe for one
    reason only, stated in registry.py: every registered capability was pure, so
    re-running it after a crash could not do anything twice. An effectful
    capability destroys that argument -- which is exactly why `a5_result_store`
    gated effectful registration.

    This module is the replacement argument. A capability result is recorded
    under the idempotency key of the command that produced it. A second
    execution with the same key does not repeat the effect: it returns the
    recorded result. Recovery after a crash is therefore "look up the key",
    not "run it again and hope it was idempotent".

WHAT MAKES IT TRUSTWORTHY RATHER THAN MERELY PRESENT

    Storing a result proves nothing if the stored bytes are never checked. So
    the row carries the SHA-256 of the canonical form of the result, and
    `verify()` re-derives that hash from what was actually stored and compares.
    A row whose recomputed hash disagrees with its recorded hash is reported as
    CORRUPT and is never returned as a replayable result -- a corrupted result
    must not be able to masquerade as a successful prior execution.

APPEND-ONLY

    Results are inserted, never updated. The idempotency key is UNIQUE, so a
    second insert for the same key is refused by the database rather than by
    remembering to check first. Structural, not procedural.
"""

import json

from ..contracts import ids  # noqa: E402
from . import errors as runtime_errors  # noqa: E402

TABLE = "capability_results"

# Recorded verbatim alongside the other runtime tables. `recorded_at` is
# informational only -- it is never part of identity, per Constitution 11.
SCHEMA_STATEMENTS = (
    """CREATE TABLE capability_results (
        idempotency_key TEXT    NOT NULL UNIQUE,
        capability_id   TEXT    NOT NULL,
        result_json     TEXT    NOT NULL,
        result_hash     TEXT    NOT NULL,
        recorded_at     TEXT    NOT NULL
    )""",
    """CREATE INDEX idx_results_capability ON capability_results (capability_id)""",
)


def result_hash(result):
    """SHA-256 of the canonical form of a result mapping.

    Canonical form, not raw JSON: key order must not change identity, for the
    same reason the evidence platform canonicalizes before hashing.
    """
    return ids.sha256_hex(ids.canonical_json_bytes(ids.as_plain(result)))


def record(connection, idempotency_key, capability_id, result, now):
    """Record one successful result. Returns the stored hash.

    Refuses an empty key outright: a result stored under no key is a result
    nobody can ever find again, which is worse than not storing it.
    """
    if not idempotency_key:
        runtime_errors.fail(
            "a capability result requires an idempotency key; refusing to "
            "record a result that could never be looked up",
            runtime_errors.ContractValidationError)
    digest = result_hash(result)
    connection.execute(
        "INSERT INTO capability_results "
        "(idempotency_key, capability_id, result_json, result_hash, recorded_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (idempotency_key, capability_id,
         json.dumps(ids.as_plain(result), sort_keys=True, separators=(",", ":")),
         digest, now))
    return digest


def lookup(connection, idempotency_key):
    """The recorded result for a key, or None.

    Returns (result, verification) where verification is 'verified' or
    'corrupt'. A CORRUPT result is returned with its flag rather than silently
    dropped, so the caller can refuse it AND report why -- a missing result and
    a corrupted one are different facts and must not look identical.
    """
    if not idempotency_key:
        return (None, None)
    row = connection.execute(
        "SELECT result_json, result_hash, capability_id FROM capability_results "
        "WHERE idempotency_key = ?", (idempotency_key,)).fetchone()
    if row is None:
        return (None, None)
    try:
        stored = json.loads(row["result_json"])
    except (ValueError, TypeError):
        return (None, "corrupt")
    # RE-DERIVE, never trust the recorded hash on its own. This is the check
    # that makes the store evidence rather than an assertion.
    if result_hash(stored) != row["result_hash"]:
        return (None, "corrupt")
    return (stored, "verified")


def verify(connection, idempotency_key=None):
    """Re-derive and compare every stored result, or one.

    Returns {checked, verified, corrupt, corruptKeys}. Used by tests and by the
    operator; never by the dispatch path, which uses lookup().
    """
    if idempotency_key:
        rows = connection.execute(
            "SELECT idempotency_key, result_json, result_hash FROM "
            "capability_results WHERE idempotency_key = ?",
            (idempotency_key,)).fetchall()
    else:
        rows = connection.execute(
            "SELECT idempotency_key, result_json, result_hash FROM "
            "capability_results ORDER BY idempotency_key").fetchall()
    checked = verified = corrupt = 0
    corrupt_keys = []
    for row in rows:
        checked += 1
        try:
            stored = json.loads(row["result_json"])
        except (ValueError, TypeError):
            corrupt += 1
            corrupt_keys.append(row["idempotency_key"])
            continue
        if result_hash(stored) == row["result_hash"]:
            verified += 1
        else:
            corrupt += 1
            corrupt_keys.append(row["idempotency_key"])
    return {"checked": checked, "verified": verified, "corrupt": corrupt,
            "corruptKeys": corrupt_keys}

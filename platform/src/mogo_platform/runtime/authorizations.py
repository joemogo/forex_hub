#!/usr/bin/env python3
"""MOGO Automation Platform -- Acquisition Authorization Records.

AUTHORITY
    Automation Platform Constitution v1.0 (senior) -- sections 5, 9, 14
    ADR-012 (accepted 2026-08-07)                  -- D-08
    MOGO-009 Architecture, section 20.3
    MOGO-009 Contract Catalog, section M -- record fields (AUTHORITATIVE)
    MOGO-011 Step 3 plan, section 6.2 · governance decision C-3

THE PLATFORM RECORDS THESE; IT NEVER MAKES THEM
    Constitution section 5.9 and Architecture section 20.1: this architecture
    makes NO legal determination. It records and enforces classifications
    supplied by project governance or legal review.

    An Acquisition Authorization Record is therefore an INPUT -- exactly like a
    capability manifest -- and the platform has no code path that mints one.
    `decisionAuthority` must name a human or governance role; a worker or a
    capability naming itself is refused, because a component that could
    authorize its own acquisition would make the whole gate ornamental
    (Constitution section 14, Catalog section N).

APPEND-ONLY, AND CORRECTED BY SUPERSESSION
    Records are never updated and never deleted -- the append-only triggers the
    event index uses are applied to this table too. A correction is a NEW record
    naming the one it replaces via `supersedesAuthorizationId`, which is
    Constitution section 6.7's discipline and the same one the pre-registrations
    use.

    Supersession is therefore DERIVED, never stamped: a record is superseded iff
    some other record names it. That is a query, not a mutation, which is what
    lets the table stay append-only while still expressing replacement.

NOT REPLAYABLE, AND SAID SO
    This table holds governance input, not platform history, so it is a LOCAL
    OBSERVATION alongside `capabilities` and `runs`. Replay determinism is
    preserved by recording the DECISION rather than the input: every gate
    decision event carries the authorizationId, status, policy version,
    authority, permitted operations, and a content hash of the record as it
    stood at decision time. A later edit therefore cannot rewrite history --
    Constitution section 5.7 made mechanical.
"""

import json

from ..contracts import ids  # noqa: E402
from ..contracts import vocabulary  # noqa: E402
from . import clock as clock_module  # noqa: E402
from . import errors as runtime_errors  # noqa: E402
from . import policy  # noqa: E402

# Contract Catalog section M / Architecture section 20.3, adopted verbatim.
REQUIRED_FIELDS = (
    "authorizationId", "sourceId", "policyStatus", "policyVersion",
    "decisionAuthority", "decidedAt", "permittedOperations",
)

OPTIONAL_FIELDS = (
    "sourceTermsSnapshotRef", "retentionRestrictions", "deletionRequirements",
    "redistributionRestrictions", "modelTrainingRestrictions", "expiresAt",
    "supersedesAuthorizationId", "auditHistory",
)

RECORD_FIELDS = REQUIRED_FIELDS + OPTIONAL_FIELDS

# Catalog section N: reviewer identity is "a human or governance role -- never a
# worker". The same rule governs who may authorize an acquisition.
AUTHORITY_PREFIXES = ("operator:", "governance:", "legal:")

# Prefixes that name machinery rather than a person or a role. A record whose
# authority begins with one of these is refused outright.
PROHIBITED_AUTHORITY_PREFIXES = ("worker:", "orchestrator", "capability:",
                                 "CAP|", "WRK|", "policyGate", "reviewGate")


def validate_record(record):
    """Fail-closed structural validation. Returns the record unchanged.

    Every refusal happens BEFORE any write, so a malformed record never reaches
    the store and can never be resolved by the gate.
    """
    if not hasattr(record, "keys"):
        runtime_errors.fail(
            "an authorization record must be a mapping, got %s"
            % (type(record).__name__,),
            runtime_errors.ContractValidationError,
        )

    for field in REQUIRED_FIELDS:
        if field not in record or record[field] is None:
            runtime_errors.fail(
                "authorization record is missing required field %s" % (field,),
                runtime_errors.ContractValidationError,
            )

    unknown = sorted(set(record) - set(RECORD_FIELDS))
    if unknown:
        runtime_errors.fail(
            "authorization record declares unknown field(s) %s; the Catalog "
            "section M fields are %s" % (unknown, list(RECORD_FIELDS)),
            runtime_errors.ContractValidationError,
        )

    ids.require_json_shaped(record, "$authorizationRecord")
    ids.require_uuid4(record["authorizationId"], "authorizationId")
    ids.require_composite_id(record["sourceId"], "SRC", "sourceId")
    ids.require_iso8601_utc_ms(record["decidedAt"], "decidedAt")

    if record["policyStatus"] not in vocabulary.LICENSING_STATUSES:
        runtime_errors.fail(
            "policyStatus %r is not one of the %d approved Catalog section M "
            "classifications" % (record["policyStatus"],
                                 len(vocabulary.LICENSING_STATUSES)),
            runtime_errors.ContractValidationError,
        )

    version = record["policyVersion"]
    if not isinstance(version, str) or not version.strip():
        runtime_errors.fail(
            "policyVersion must be a non-empty string; Constitution section 5.6 "
            "requires the policy version in force to be recorded",
            runtime_errors.ContractValidationError,
        )

    _validate_authority(record["decisionAuthority"])
    _validate_operations(record["permittedOperations"])

    if record.get("expiresAt") is not None:
        ids.require_iso8601_utc_ms(record["expiresAt"], "expiresAt")
        if clock_module.parse_iso8601_ms(record["expiresAt"], "expiresAt") <= \
                clock_module.parse_iso8601_ms(record["decidedAt"], "decidedAt"):
            runtime_errors.fail(
                "expiresAt %s is not after decidedAt %s; an authorization that "
                "expires before it was decided authorizes nothing"
                % (record["expiresAt"], record["decidedAt"]),
                runtime_errors.ContractValidationError,
            )

    if record.get("supersedesAuthorizationId") is not None:
        ids.require_uuid4(record["supersedesAuthorizationId"],
                          "supersedesAuthorizationId")
        if record["supersedesAuthorizationId"] == record["authorizationId"]:
            runtime_errors.fail(
                "an authorization record may not supersede itself",
                runtime_errors.ContractValidationError,
            )

    if record.get("auditHistory") is not None \
            and not isinstance(record["auditHistory"], (list, tuple)):
        runtime_errors.fail(
            "auditHistory must be an array when present",
            runtime_errors.ContractValidationError,
        )
    return record


def _validate_authority(authority):
    """Who decided. Never a worker, never the platform itself."""
    if not isinstance(authority, str) or not authority.strip():
        runtime_errors.fail(
            "decisionAuthority must name the human or governance role that made "
            "the decision; Constitution section 5.6",
            runtime_errors.ContractValidationError,
        )
    for prefix in PROHIBITED_AUTHORITY_PREFIXES:
        if authority.startswith(prefix) or prefix in authority:
            runtime_errors.fail(
                "decisionAuthority %r names automation. An acquisition may be "
                "authorized only by a human or a governance role -- a component "
                "that could authorize its own acquisition would make the policy "
                "gate ornamental (Constitution section 14, Catalog section N)"
                % (authority,),
                runtime_errors.AuthorizationRefusedError,
            )
    if not any(authority.startswith(prefix) for prefix in AUTHORITY_PREFIXES):
        runtime_errors.fail(
            "decisionAuthority %r must begin with one of %s so that the deciding "
            "authority is unambiguous in the audit trail"
            % (authority, list(AUTHORITY_PREFIXES)),
            runtime_errors.ContractValidationError,
        )
    return authority


def _validate_operations(operations):
    if not isinstance(operations, (list, tuple)):
        runtime_errors.fail(
            "permittedOperations must be an array, got %s"
            % (type(operations).__name__,),
            runtime_errors.ContractValidationError,
        )
    for operation in operations:
        if operation not in policy.ACQUISITION_OPERATIONS:
            runtime_errors.fail(
                "permittedOperations contains %r, which is not one of %s"
                % (operation, list(policy.ACQUISITION_OPERATIONS)),
                runtime_errors.ContractValidationError,
            )
    if len(set(operations)) != len(operations):
        runtime_errors.fail(
            "permittedOperations contains a duplicate entry",
            runtime_errors.ContractValidationError,
        )
    return tuple(operations)


def record_hash(record):
    """Content hash of the record exactly as it stands.

    Carried in every gate decision event so that a later edit to the record is
    detectable and inert: the decision remains attributable to the bytes that
    were actually in force when it was made.
    """
    return ids.content_hash_of(record)


def register(connection, record, now):
    """Store one governance-supplied record. Idempotent for identical content.

    Raises when the same authorizationId is presented with different content --
    a changed authorization is a NEW decision and needs a new record that
    supersedes the old one, or the audit trail would silently describe an
    acquisition permitted under terms that no longer exist.
    """
    validate_record(record)
    digest = record_hash(record)
    authorization_id = record["authorizationId"]

    existing = connection.execute(
        "SELECT record_hash FROM acquisition_authorizations "
        "WHERE authorization_id = ?", (authorization_id,)).fetchone()
    if existing is not None:
        if existing["record_hash"] == digest:
            return "unchanged"
        runtime_errors.fail(
            "authorization %s is already recorded with different content "
            "(%s != %s). A changed authorization is a new governance decision: "
            "record a new authorization that supersedes this one, rather than "
            "altering history" % (authorization_id, existing["record_hash"],
                                  digest),
            runtime_errors.AuthorizationRefusedError,
        )

    superseded = record.get("supersedesAuthorizationId")
    if superseded is not None:
        prior = connection.execute(
            "SELECT source_id FROM acquisition_authorizations "
            "WHERE authorization_id = ?", (superseded,)).fetchone()
        if prior is None:
            runtime_errors.fail(
                "authorization %s claims to supersede %s, which is not recorded"
                % (authorization_id, superseded),
                runtime_errors.AuthorizationRefusedError,
            )
        if prior["source_id"] != record["sourceId"]:
            runtime_errors.fail(
                "authorization %s supersedes a record for a different source "
                "(%s != %s)" % (authorization_id, prior["source_id"],
                                record["sourceId"]),
                runtime_errors.AuthorizationRefusedError,
            )

    expires_at = record.get("expiresAt")
    connection.execute(
        "INSERT INTO acquisition_authorizations ("
        " authorization_id, source_id, policy_status, policy_version,"
        " decision_authority, decided_at, permitted_operations, expires_at,"
        " supersedes_authorization_id, record_json, record_hash, recorded_at"
        ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (authorization_id, record["sourceId"], record["policyStatus"],
         record["policyVersion"], record["decisionAuthority"],
         record["decidedAt"],
         json.dumps(list(record["permittedOperations"]), sort_keys=True,
                    separators=(",", ":")),
         expires_at, superseded,
         ids.canonical_json_bytes(record).decode("utf-8"), digest, now),
    )
    return "recorded"


def _row_to_record(row, superseded_by=None):
    """The stored record, as the gate sees it.

    `expiresAtMs` and `supersededBy` are DERIVED presentation fields -- the gate
    takes epoch milliseconds and a supersession flag rather than re-parsing or
    re-querying, so `policy.evaluate` can stay a pure function of its arguments.
    """
    record = json.loads(row["record_json"])
    record = dict(record)
    record["expiresAtMs"] = (
        None if not row["expires_at"]
        else clock_module.parse_iso8601_ms(row["expires_at"], "expiresAt"))
    record["supersededBy"] = superseded_by
    record["recordHash"] = row["record_hash"]
    return record


def resolve(connection, source_id):
    """The authorization in force for one source, or the problem preventing it.

    Returns (record, problem). Exactly one is non-None.

    A record is superseded iff another record names it -- derived by query, so
    the table never needs updating and stays append-only. More than one
    surviving record for a source is AMBIGUOUS and denies: two live governance
    decisions for the same source is a conflict a machine must not resolve by
    picking one.
    """
    if not source_id:
        return (None, policy.REASON_NO_SUBJECT_SOURCE)

    rows = connection.execute(
        "SELECT * FROM acquisition_authorizations WHERE source_id = ? "
        "AND authorization_id NOT IN ("
        "  SELECT supersedes_authorization_id FROM acquisition_authorizations "
        "  WHERE supersedes_authorization_id IS NOT NULL"
        ") ORDER BY decided_at DESC, authorization_id",
        (source_id,)).fetchall()

    if not rows:
        # Distinguish "never authorized" from "authorized and then superseded by
        # nothing that survives" -- both deny, but the operator needs to know
        # which. A source with only superseded records is still `no record`,
        # because no record is in force.
        return (None, policy.REASON_NO_RECORD)
    if len(rows) > 1:
        return (None, policy.REASON_AMBIGUOUS_RECORDS)
    return (_row_to_record(rows[0]), None)


def all_authorizations(connection):
    return connection.execute(
        "SELECT * FROM acquisition_authorizations "
        "ORDER BY source_id, decided_at, authorization_id").fetchall()


def superseded_ids(connection):
    return {row[0] for row in connection.execute(
        "SELECT supersedes_authorization_id FROM acquisition_authorizations "
        "WHERE supersedes_authorization_id IS NOT NULL")}

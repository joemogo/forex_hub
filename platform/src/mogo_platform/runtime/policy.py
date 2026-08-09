#!/usr/bin/env python3
"""MOGO Automation Platform -- the policy gate decision. Pure functions only.

AUTHORITY
    Automation Platform Constitution v1.0 (senior) -- sections 5, 4.20, 14
    ADR-012 (accepted 2026-08-07)                  -- D-08, highest priority
    MOGO-009 Architecture, section 20 -- licensing-policy architecture
    MOGO-009 Contract Catalog, section M -- licensing classification (AUTHORITATIVE)
    MOGO-009 Contract Catalog, section L -- policy_check -> queued | blocked
    MOGO-011 Step 3 plan, sections 6.1, 7

THE ONE SENTENCE THAT DEFINES THIS MODULE
    The gate answers "is this permitted?" from recorded facts. It never answers
    "go and get it."

    There is no fetch, no locator resolution, no socket, no filesystem read.
    Nothing here can acquire anything, which is what makes it safe to build
    before any connector exists -- Architecture section 32 item 5: the policy
    gate precedes every connector, so no acquisition path can exist before the
    control that governs it.

NOTHING HERE TOUCHES THE WORLD
    No connection, no log, no clock, no I/O. `now_ms` is always an ARGUMENT.
    Every decision is a pure function of recorded values, so the whole gate is
    exhaustively unit-testable without a database or a process, and precisely
    mutation-testable. The same split Step 2 used for retry.py and lease.py.

ONE CLASSIFICATION TABLE, NEVER A SECOND
    contracts.vocabulary.LICENSING_STATUSES is the Catalog section M
    transcription committed in MOGO-010, inert until now. This module is its
    first consumer and it does not copy it: permission is read from that mapping
    and from nowhere else. No status name is re-typed here as a permission
    decision -- with exactly one exception, UNKNOWN, which the Constitution
    singles out and which therefore gets a second, independent guard.

DENY IS THE DEFAULT, NOT THE FALL-THROUGH
    A permit is reached only by satisfying every rung of the ladder in
    `evaluate`. Every earlier exit denies, and every state the ladder did not
    anticipate denies. Constitution section 5.2: absence of a known permission
    is not permission.
"""

from types import MappingProxyType

from ..contracts import vocabulary  # noqa: E402
from . import errors as runtime_errors  # noqa: E402

# ---------------------------------------------------------------------------
# Operation vocabulary -- Contract Catalog section F
# ---------------------------------------------------------------------------

OPERATION_DISCOVER = "discover"
OPERATION_METADATA = "metadata"
OPERATION_TRANSCRIPT = "transcript"
OPERATION_ARTIFACT = "artifact"

ACQUISITION_OPERATIONS = (OPERATION_DISCOVER, OPERATION_METADATA,
                          OPERATION_TRANSCRIPT, OPERATION_ARTIFACT)

# Which column of the Catalog section M table governs each operation.
#
# `discover` maps to the METADATA column deliberately. Discovery gathers
# metadata, and Architecture section 20.2 is explicit that the
# minimum-metadata allowance exists ONLY in the window before a classification
# is recorded and "expires the instant one is recorded". Once an authorization
# record exists, discovery is governed exactly as metadata is -- there is no
# separate, laxer rule for it, because that rule would be the drip-feed
# loophole section 20.2 exists to close.
OPERATION_PERMISSION_COLUMN = MappingProxyType({
    OPERATION_DISCOVER: "metadata",
    OPERATION_METADATA: "metadata",
    OPERATION_TRANSCRIPT: "transcript",
    OPERATION_ARTIFACT: "artifact",
})

# ---------------------------------------------------------------------------
# Operation classes -- Contract Catalog section L footnote 2
# ---------------------------------------------------------------------------

OPERATION_CLASS_ACQUISITION = "acquisition"
OPERATION_CLASS_NON_ACQUISITION = "non_acquisition"
OPERATION_CLASSES = (OPERATION_CLASS_ACQUISITION, OPERATION_CLASS_NON_ACQUISITION)

# ---------------------------------------------------------------------------
# Decisions and reasons
# ---------------------------------------------------------------------------

DECISION_PERMIT = "permit"
DECISION_NOT_APPLICABLE = "not_applicable"
DECISION_DENY = "deny"

# Constitution section 5.2 singles this status out: "UNKNOWN behaves exactly as
# PROHIBITED. Absence of a known permission is not permission." It is therefore
# the ONE status name that appears here as a literal, checked independently of
# the table -- so a mutation that flips its table row to permit acquisition is
# still refused. The same belt-and-braces Step 2 gave `policy_blocked`.
NEVER_ACQUIRABLE = ("UNKNOWN",)

REASON_NOT_APPLICABLE = "not_applicable"
REASON_AUTHORIZED = "authorized"

REASON_INDETERMINATE_CLASS = "operation_class_indeterminate"
REASON_NO_OPERATIONS_DECLARED = "no_acquisition_operations_declared"
REASON_NO_SUBJECT_SOURCE = "no_subject_source"
REASON_NO_RECORD = "no_authorization_record"
REASON_AMBIGUOUS_RECORDS = "ambiguous_authorization_records"
REASON_UNKNOWN_STATUS = "unknown_policy_status"
REASON_STATUS_DENIES = "policy_status_denies_acquisition"
REASON_EXPIRED = "authorization_expired"
REASON_SUPERSEDED = "authorization_superseded"
REASON_OPERATION_NOT_PERMITTED = "operation_not_permitted"
REASON_OPERATION_DENIED_BY_STATUS = "operation_denied_by_status"
REASON_LICENCE_SILENT = "licence_does_not_state_operation"

DENY_REASONS = (
    REASON_INDETERMINATE_CLASS,
    REASON_NO_OPERATIONS_DECLARED,
    REASON_NO_SUBJECT_SOURCE,
    REASON_NO_RECORD,
    REASON_AMBIGUOUS_RECORDS,
    REASON_UNKNOWN_STATUS,
    REASON_STATUS_DENIES,
    REASON_EXPIRED,
    REASON_SUPERSEDED,
    REASON_OPERATION_NOT_PERMITTED,
    REASON_OPERATION_DENIED_BY_STATUS,
    REASON_LICENCE_SILENT,
)

# Resolution problems a caller may have hit BEFORE a record could be evaluated.
# Passed in rather than raised, so the whole decision stays one pure function
# with one exit shape.
RESOLUTION_PROBLEMS = (REASON_NO_RECORD, REASON_AMBIGUOUS_RECORDS,
                       REASON_NO_SUBJECT_SOURCE)


class Decision(object):
    """The authorization verdict, and the reason recorded for it.

    `reason` is carried into the event payload either way, so the audit trail
    states WHY a task was permitted or blocked without an operator inferring it
    from surrounding events -- Constitution section 4.20.
    """

    __slots__ = ("permitted", "decision", "reason")

    def __init__(self, permitted, decision, reason):
        self.permitted = permitted
        self.decision = decision
        self.reason = reason

    def __eq__(self, other):
        return (isinstance(other, Decision)
                and self.permitted == other.permitted
                and self.decision == other.decision
                and self.reason == other.reason)

    def __hash__(self):
        return hash((self.permitted, self.decision, self.reason))

    def __repr__(self):
        return ("Decision(permitted=%r, decision=%r, reason=%r)"
                % (self.permitted, self.decision, self.reason))


def _deny(reason):
    return Decision(False, DECISION_DENY, reason)


def permits_acquisition(policy_status):
    """True only if the committed Catalog section M table says so.

    Two independent guards, because Constitution section 5.2 states the rule in
    absolute terms:

      1. UNKNOWN is refused BEFORE the table is consulted, so a mutation that
         flips its row still cannot grant acquisition.
      2. Every other status is decided by the table's own `permitsAcquisition`,
         never by a list of names re-typed here.

    An unrecognised status is refused: absence of a known permission is not
    permission.
    """
    if policy_status in NEVER_ACQUIRABLE:
        return False
    record = vocabulary.LICENSING_STATUSES.get(policy_status)
    if record is None:
        return False
    return bool(record["permitsAcquisition"])


def operation_permission(policy_status, operation):
    """The Catalog section M permission value for one operation, or None.

    None means the status or the operation is unrecognised -- which every
    caller treats as a denial.
    """
    record = vocabulary.LICENSING_STATUSES.get(policy_status)
    column = OPERATION_PERMISSION_COLUMN.get(operation)
    if record is None or column is None:
        return None
    return record[column]


def is_expired(expires_at_ms, now_ms):
    """True when an authorization has run out. Pure.

    `>=`: an authorization is not in force during the millisecond it expires.
    An absent expiry means the record does not expire, which is legitimate --
    an authorization with no stated end date is common and is recorded as such.
    """
    if expires_at_ms is None:
        return False
    return now_ms >= expires_at_ms


def evaluate(operation_class, requested_operations, authorization, now_ms,
             resolution_problem=None):
    """The single authorization decision. Pure: no clock, no connection, no I/O.

    Returns a Decision. A permit is reached ONLY by falling through every rung
    below; every earlier exit denies, and so does anything the ladder did not
    anticipate.

    `authorization` is the resolved Acquisition Authorization Record as a plain
    mapping, or None. `resolution_problem` is set when the caller could not
    resolve one at all -- passed in rather than raised so that a lookup failure
    and a policy denial produce the same shape of recorded outcome.
    """
    # 1. Non-acquisition work is not what this gate governs. Catalog section L
    #    footnote 2: every task passes through policy_check, but the gate
    #    evaluates only acquisition-class operations. Routing all tasks through
    #    one state is what makes "was this checked?" answerable from the log for
    #    EVERY task rather than only the ones someone remembered to route.
    if operation_class == OPERATION_CLASS_NON_ACQUISITION:
        return Decision(True, DECISION_NOT_APPLICABLE, REASON_NOT_APPLICABLE)

    # 2. Anything else -- absent, empty, misspelled, or a class this build does
    #    not know -- is treated as acquisition-class and blocked. Architecture
    #    section 18.1: the same fail-closed default the licensing model uses.
    if operation_class != OPERATION_CLASS_ACQUISITION:
        return _deny(REASON_INDETERMINATE_CLASS)

    # 3. A resolution problem is a denial, not an exception.
    if resolution_problem is not None:
        if resolution_problem not in RESOLUTION_PROBLEMS:
            return _deny(REASON_NO_RECORD)
        return _deny(resolution_problem)

    # 4. An acquisition capability declaring no operations can do nothing. It
    #    is refused rather than silently permitted to do "nothing in
    #    particular".
    operations = tuple(requested_operations or ())
    if not operations:
        return _deny(REASON_NO_OPERATIONS_DECLARED)

    # 5. No record is a denial. Constitution section 5.1: no fetch without an
    #    Acquisition Authorization Record.
    if authorization is None:
        return _deny(REASON_NO_RECORD)

    policy_status = authorization.get("policyStatus")

    # 6. An unrecognised status cannot be reasoned about.
    if policy_status not in vocabulary.LICENSING_STATUSES:
        return _deny(REASON_UNKNOWN_STATUS)

    # 7. UNKNOWN, PROHIBITED, RESTRICTED, AUTHENTICATION_REQUIRED and
    #    HUMAN_REVIEW_REQUIRED all stop here.
    if not permits_acquisition(policy_status):
        return _deny(REASON_STATUS_DENIES)

    # 8. An expired authorization is not an authorization.
    if is_expired(authorization.get("expiresAtMs"), now_ms):
        return _deny(REASON_EXPIRED)

    # 9. A superseded record has been replaced by a later governance decision.
    if authorization.get("supersededBy"):
        return _deny(REASON_SUPERSEDED)

    permitted = tuple(authorization.get("permittedOperations") or ())

    # 10. Every requested operation must clear BOTH the record's own permitted
    #     list and the status's column. Either alone is insufficient: the list
    #     is what governance granted, the column is what the classification
    #     allows, and the narrower of the two governs.
    for operation in operations:
        if operation not in ACQUISITION_OPERATIONS:
            return _deny(REASON_OPERATION_NOT_PERMITTED)
        if operation not in permitted:
            return _deny(REASON_OPERATION_NOT_PERMITTED)

        permission = operation_permission(policy_status, operation)
        if permission is None:
            return _deny(REASON_UNKNOWN_STATUS)

        if permission == vocabulary.ALLOWED:
            continue

        if permission == vocabulary.AS_RECORDED:
            # PERMITTED_EXPLICIT_LICENSE and PERMITTED_DOCUMENTED_POLICY mark
            # every operation AS_RECORDED, which is NOT an allowance -- it means
            # "whatever the licence says". Treating it as permission would turn
            # the two most nuanced statuses into the most permissive ones.
            # Architecture section 20.1 requires the licence to be REFERENCED,
            # so a record that does not reference one has not stated anything.
            if not authorization.get("sourceTermsSnapshotRef"):
                return _deny(REASON_LICENCE_SILENT)
            continue

        # DENIED, LOCATOR_ONLY and ALREADY_GATHERED_ONLY all mean no new
        # acquisition of this kind. LOCATOR_ONLY stores a locator and retrieves
        # nothing; ALREADY_GATHERED_ONLY refers to metadata gathered before the
        # classification existed and permits no further fetch.
        return _deny(REASON_OPERATION_DENIED_BY_STATUS)

    return Decision(True, DECISION_PERMIT, REASON_AUTHORIZED)


def assert_decision_is_recognised(decision):
    """Guard against a decision this build cannot route. Fail closed."""
    if decision.decision not in (DECISION_PERMIT, DECISION_NOT_APPLICABLE,
                                DECISION_DENY):
        runtime_errors.fail(
            "policy decision %r is not a decision this build can route"
            % (decision.decision,),
            runtime_errors.PolicyGateError,
        )
    return decision

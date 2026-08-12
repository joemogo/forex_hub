#!/usr/bin/env python3
"""MOGO Automation Platform -- the research change-detection CONTRACT.

MOGO-017 Step 2B. THE CONTRACT ONLY. NOT THE DETECTOR.

WHAT THIS IS, AND WHAT IT IS DELIBERATELY NOT

    This module freezes the semantics MOGO-017's future detector must obey, as
    executable, testable code. It is a PURE decision function over values the
    caller already holds.

    It contains NO history query, NO event emission, NO storage, NO clock and NO
    production call site. Nothing in the running system imports it yet, and that
    absence is the point: Step 2B was authorised to fix the contract, not to
    start classifying real acquisitions. Wiring it up is Step 2C's job, and it
    must be a visible edit rather than something that quietly began working.

THE ONE SENTENCE

    A change is a difference between two pieces of ACCEPTED content for the same
    source and resource -- and nothing that failed can ever be accepted.

WHY `ACCEPTED` IS THE LOAD-BEARING WORD

    A transport success is not scientific acceptance. Bytes can arrive with HTTP
    200 and still be refused by ingestion as empty, oversized, non-UTF-8 or
    unstorable. If such bytes were allowed to become the comparison baseline,
    then a single truncated or hostile response would silently redefine "what
    this source says", and the NEXT genuine acquisition would be reported as a
    mutation. Worse, the corruption would persist as the new normal.

    So the baseline advances only on content that was acquired successfully AND
    validated AND durably stored under a verified content identity. Everything
    else leaves the previous baseline exactly where it was.

CONTENT IDENTITY IS THE RAW EXTERNAL BYTE HASH, AND THIS MATTERS

    `connector_transport.content_hash(raw)` is SHA-256 over the exact response
    body, hashed before interpretation. Nothing local participates: not headers,
    not the acquisition timestamp, not the request or execution identity, not the
    URL, and not a JSON re-serialization -- the transport parses the body only to
    VALIDATE it and discards the parsed value.

    The research ARTIFACT hash is a different number and must NOT be used here.
    It is the hash of a wrapper document that embeds the acquisition record, and
    that record carries `acquiredAt`, `decidedAt` and a decision `requestedUrl`.
    Those are null today only because the capability never passes a clock -- a
    provenance gap, not a design guarantee. The moment anyone fixes that gap, the
    wrapper hash would change on EVERY acquisition and every scheduled run would
    report a mutation. Comparing raw bytes is immune to that by construction, and
    the contract tests pin it so the gap can be fixed later without breaking
    change detection.

CHANGED IS AN OBSERVATION, NOT A CONCLUSION

    `CHANGED` means exactly: previously accepted validated content for this
    approved source and resource differs from newly accepted validated content.

    It does NOT mean the difference is useful, meaningful, or strategy-relevant.
    It authorises no interpretation, no hypothesis, no rule, no promotion and no
    change to ALEX or to any trading behaviour. RESEARCH CHANGE IS NOT TRADING
    CHANGE, and nothing downstream of this module may treat it as such.

A MUTATION IS NOT A FAILURE

    `contracts/errors.py` declares a `source_mutated` error class, and it is NOT
    used here. `registry._validate_failure_classes()` refuses it at registration
    anyway (it routes to review with no terminal path), but the deeper reason is
    semantic: a source that changed is information the system wanted. Modelling
    it as an execution failure would dead-letter a successful acquisition and
    lose the very observation the milestone exists to make.
"""

from ..contracts import ids  # noqa: E402
from . import errors as runtime_errors  # noqa: E402

CONTRACT_VERSION = "mogo.research-change-detection.v1"

# ---------------------------------------------------------------------------
# Classifications -- the complete, closed set
# ---------------------------------------------------------------------------

FIRST_OBSERVATION = "FIRST_OBSERVATION"
UNCHANGED = "UNCHANGED"
CHANGED = "CHANGED"
ACQUISITION_FAILURE = "ACQUISITION_FAILURE"
VALIDATION_FAILURE = "VALIDATION_FAILURE"

CLASSIFICATIONS = (FIRST_OBSERVATION, UNCHANGED, CHANGED,
                   ACQUISITION_FAILURE, VALIDATION_FAILURE)

# The classifications that establish or move the accepted baseline. UNCHANGED is
# here because it re-affirms the SAME identity -- writing it back is a no-op, and
# excluding it would make "the baseline is whatever survived" depend on which of
# two identical values was stored.
BASELINE_ADVANCING = (FIRST_OBSERVATION, UNCHANGED, CHANGED)

# The classifications that must leave the previous baseline untouched.
BASELINE_PRESERVING = (ACQUISITION_FAILURE, VALIDATION_FAILURE)

# `CHANGED_BYTES_THAT_FAIL_VALIDATION` is deliberately NOT a classification of
# its own. It is VALIDATION_FAILURE, because the bytes never became accepted
# content and therefore never entered the comparison at all. Giving it a separate
# name would imply a mutation was observed and then set aside, when in fact no
# comparison was ever legitimate. A test pins this reading.

# Ingestion's own vocabulary, consumed rather than restated. `duplicateStatus`
# is deliberately absent from every acceptance test below: it answers "have these
# exact bytes been stored before", which is a STORAGE question, not a question
# about whether this source changed.
VALIDATION_STATUS_VALID = "VALID"


# ---------------------------------------------------------------------------
# Same-source identity
# ---------------------------------------------------------------------------

def comparison_key(source_id, resource_id):
    """The identity of ONE comparison stream. Pure.

    `(sourceId, resourceId)`, and both are required.

    sourceId alone is insufficient and the reason is concrete: this connector
    acquires metadata FOR ONE RESOURCE, so two different videos under the
    approved channel would otherwise share a history and each acquisition would
    read as a mutation of the other. Catalog section I's metadata row omits the
    resource because it addresses a source as a whole; this contract does not.

    Returned as a tuple rather than a joined string so no separator can ever be
    smuggled through an identifier to make two distinct streams collide.
    """
    ids.require_composite_id(source_id, "SRC", "sourceId")
    if not isinstance(resource_id, str) or not resource_id.strip():
        runtime_errors.fail(
            "resourceId is required to identify a comparison stream; a source "
            "with no resource would merge every resource's history into one",
            runtime_errors.ContractValidationError)
    return (source_id, resource_id)


# ---------------------------------------------------------------------------
# Accepted content
# ---------------------------------------------------------------------------

def accepted_content_identity(acquisition_ok, ingestion_result):
    """The content identity eligible to enter mutation history, or None. Pure.

    Returns the SHA-256 raw-byte content hash when, and only when, every one of
    these holds:

      * the acquisition itself succeeded (which already implies the connector
        gate permitted it, the destination was the authorized one, the status was
        acceptable, the content type matched, the body was within the cap and the
        body parsed as UTF-8 JSON -- all enforced in connector_transport before
        an ok outcome exists);
      * ingestion reported validationStatus VALID;
      * ingestion reported storedVerified -- the artifact was re-read from disk
        and its hash re-derived, so "stored" means stored, not attempted;
      * a well-formed content hash is present.

    `ingested` is NOT required, and that is the subtle part. A repeat
    acquisition of identical bytes reports `ingested=false` with
    `duplicateStatus=DUPLICATE_ALREADY_INGESTED` because the artifact already
    exists -- the content is accepted, the storage was simply a no-op. Requiring
    `ingested` would make every UNCHANGED observation look like a failure.
    """
    if not acquisition_ok:
        return None
    if not isinstance(ingestion_result, dict):
        return None
    if ingestion_result.get("validationStatus") != VALIDATION_STATUS_VALID:
        return None
    if not ingestion_result.get("storedVerified"):
        return None
    content_hash = ingestion_result.get("contentHash")
    if not ids.is_sha256_hex(content_hash):
        return None
    return content_hash


# ---------------------------------------------------------------------------
# The decision
# ---------------------------------------------------------------------------

class Classification(object):
    """The verdict, and everything an audit record would need to carry.

    `priorContentIdentity` and `currentContentIdentity` are both preserved --
    including on CHANGED, which is the case where a later reader most needs to
    see what was replaced by what.
    """

    __slots__ = ("classification", "priorContentIdentity",
                 "currentContentIdentity", "advancesBaseline", "reason")

    def __init__(self, classification, prior, current, advances, reason):
        # Explicit assignment, never setattr() in a loop -- the platform boundary
        # suite forbids dynamic attribute writes in the runtime.
        self.classification = classification
        self.priorContentIdentity = prior
        self.currentContentIdentity = current
        self.advancesBaseline = advances
        self.reason = reason

    def __eq__(self, other):
        return (isinstance(other, Classification)
                and self.classification == other.classification
                and self.priorContentIdentity == other.priorContentIdentity
                and self.currentContentIdentity == other.currentContentIdentity
                and self.advancesBaseline == other.advancesBaseline)

    def __hash__(self):
        return hash((self.classification, self.priorContentIdentity,
                     self.currentContentIdentity, self.advancesBaseline))

    def __repr__(self):
        return ("Classification(classification=%r, prior=%r, current=%r, "
                "advancesBaseline=%r)"
                % (self.classification, self.priorContentIdentity,
                   self.currentContentIdentity, self.advancesBaseline))

    def as_record(self):
        return {name: getattr(self, name) for name in self.__slots__}


REASON_NO_ACQUISITION = "acquisition_did_not_succeed"
REASON_NOT_VALIDATED = "content_did_not_pass_validation"
REASON_NO_PRIOR = "no_prior_accepted_content_for_this_source_and_resource"
REASON_IDENTICAL = "content_identity_equals_the_prior_accepted_identity"
REASON_DIFFERS = "content_identity_differs_from_the_prior_accepted_identity"


def classify(prior_content_identity, acquisition_ok, ingestion_result):
    """THE CLASSIFICATION. Pure: no clock, no connection, no I/O, no history.

    History is an ARGUMENT -- `prior_content_identity` is the immediately prior
    ACCEPTED identity for this comparison stream, or None if there is none. The
    same split policy.py and retry.py use, and for the same reason: every
    transition is exhaustively testable without a database, a process or a wait.

    A permit-shaped ladder, where every earlier rung exits and only the last two
    can reach a comparison.
    """
    # 1. Acquisition failure. No classification of the source's content is
    #    possible, because no content was obtained. A failed fetch is not
    #    evidence that the source is stable.
    if not acquisition_ok:
        return Classification(ACQUISITION_FAILURE, prior_content_identity,
                              None, False, REASON_NO_ACQUISITION)

    # 2. Validation failure -- INCLUDING the case where the bytes genuinely
    #    differed from the baseline. Different-but-invalid is NOT a mutation: the
    #    content never became accepted, so there was never a legitimate
    #    comparison to make, and the baseline stays exactly where it was.
    current = accepted_content_identity(acquisition_ok, ingestion_result)
    if current is None:
        return Classification(VALIDATION_FAILURE, prior_content_identity,
                              None, False, REASON_NOT_VALIDATED)

    # 3. No prior accepted content. This establishes a baseline and is NOT a
    #    mutation -- reporting a source's first ever observation as a change
    #    would make every new source look like it had just mutated.
    if prior_content_identity is None:
        return Classification(FIRST_OBSERVATION, None, current, True,
                              REASON_NO_PRIOR)

    if not ids.is_sha256_hex(prior_content_identity):
        runtime_errors.fail(
            "prior content identity %r is not a SHA-256 hex digest; a malformed "
            "baseline would make every comparison against it meaningless"
            % (prior_content_identity,),
            runtime_errors.ContractValidationError)

    # 4. The comparison itself. Byte identity, nothing else. A new request
    #    identity, a new acquisition timestamp and changed transport metadata all
    #    reach this rung with an unchanged `current`, and therefore all resolve
    #    to UNCHANGED.
    if current == prior_content_identity:
        return Classification(UNCHANGED, prior_content_identity, current, True,
                              REASON_IDENTICAL)

    return Classification(CHANGED, prior_content_identity, current, True,
                          REASON_DIFFERS)


def next_baseline(prior_content_identity, classification):
    """The accepted baseline AFTER this observation. Pure.

    Stated as its own function rather than left implicit at the call site,
    because "a failure must not advance the baseline" is the single rule most
    likely to be got wrong by a future caller writing it inline.
    """
    if not isinstance(classification, Classification):
        runtime_errors.fail(
            "next_baseline requires a Classification, got %s"
            % (type(classification).__name__,),
            runtime_errors.ContractValidationError)
    if not classification.advancesBaseline:
        return prior_content_identity
    return classification.currentContentIdentity

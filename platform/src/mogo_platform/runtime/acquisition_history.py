#!/usr/bin/env python3
"""MOGO Automation Platform -- the prior ACCEPTED acquisition for one stream.

MOGO-017 Step 2C.

WHAT THIS IS

    The one query change detection needs: "what content did this source and
    resource last legitimately give us?"

    It reads `capability_results`, which already holds every recorded acquisition
    result, and applies the Step 2B acceptance predicate to each candidate. It
    invents no storage: there is NO separate baseline table, and that absence is
    a design decision rather than an omission.

WHY THERE IS NO SEPARATE BASELINE STORE

    A second store holding "the current accepted hash" would be a second source
    of truth that can disagree with the acquisition history it summarises, and
    the failure mode is nasty: a crash between recording an acquisition and
    updating the baseline leaves the two permanently inconsistent, with nothing
    able to say which is right.

    Deriving the baseline from the history makes that class impossible. The
    baseline is not a value anyone maintains; it is the newest accepted row, and
    a run that recorded no accepted row simply does not appear.

WHY A FAILURE CANNOT POISON THE BASELINE

    Three independent reasons, in order of how early they stop it:

      1. The orchestrator records a result only for a task that SUCCEEDED. A
         failed acquisition never reaches `result_store.record` at all.
      2. Ingestion raises on empty, oversized, non-UTF-8 or unstorable content,
         so a validation failure fails the task and, again, records nothing.
      3. Even so, every row this module returns is re-checked against the Step 2B
         acceptance predicate before it is allowed to be a baseline. Belt and
         braces, because a row that somehow recorded a non-VALID status must
         never become "what this source says".

ORDERING

    `recorded_at` descending, with the implicit rowid as the tiebreak. The
    orchestrator stamps `recorded_at` from a clock guarded by a monotonic floor
    that ABORTS rather than record a time earlier than the event it follows, so
    it is a durable, repository-native ordering rather than a hopeful one. The
    rowid tiebreak makes two results recorded in the same millisecond
    deterministic instead of arbitrary.

SCALABILITY, RECORDED HONESTLY FOR A LATER MILESTONE

    `capability_results` has no `source_id` column and no index on one, so this
    scans the rows for one capability and filters in Python. At the current
    volume -- single digits -- that is free, and adding an index now would be
    optimising a table that fits in a cache line. If scheduled collection ever
    grows to thousands of acquisitions per source, the right change is a
    generated column plus an index, or a narrow projection table; it is NOT to
    weaken the acceptance filter, which is the part that must stay exact.
"""

import json

from . import change_detection  # noqa: E402
from . import errors as runtime_errors  # noqa: E402

# Ordered newest-first. `rowid` is SQLite's implicit insertion order and breaks a
# same-millisecond tie deterministically.
_NEWEST_FIRST = (
    "SELECT idempotency_key, result_json, recorded_at, rowid AS row_id "
    "FROM capability_results WHERE capability_id = ? "
    "ORDER BY recorded_at DESC, rowid DESC")


class PriorAcceptedAcquisition(object):
    """The newest accepted acquisition for one comparison stream."""

    __slots__ = ("contentIdentity", "idempotencyKey", "recordedAt")

    def __init__(self, content_identity, idempotency_key, recorded_at):
        # Explicit assignment, never setattr() in a loop -- the platform boundary
        # suite forbids dynamic attribute writes in the runtime.
        self.contentIdentity = content_identity
        self.idempotencyKey = idempotency_key
        self.recordedAt = recorded_at

    def __repr__(self):
        return ("PriorAcceptedAcquisition(contentIdentity=%r, "
                "idempotencyKey=%r, recordedAt=%r)"
                % (self.contentIdentity, self.idempotencyKey, self.recordedAt))


def _stream_of(result):
    """The (sourceId, resourceId) a recorded acquisition result belongs to."""
    if not isinstance(result, dict):
        return None
    source_id = result.get("sourceId")
    resource_id = result.get("resourceId")
    if not source_id or not resource_id:
        return None
    return (source_id, resource_id)


def prior_accepted(connection, capability_id, source_id, resource_id,
                   exclude_idempotency_key=None):
    """The immediately prior ACCEPTED acquisition for this stream, or None.

    `exclude_idempotency_key` omits the acquisition currently being classified,
    so a run never compares against itself. It is a required discipline rather
    than a convenience: the current result may already have been recorded by a
    replay before classification runs.
    """
    stream = change_detection.comparison_key(source_id, resource_id)
    rows = connection.execute(_NEWEST_FIRST, (capability_id,)).fetchall()
    for row in rows:
        if exclude_idempotency_key is not None \
                and row["idempotency_key"] == exclude_idempotency_key:
            continue
        try:
            result = json.loads(row["result_json"])
        except (ValueError, TypeError):
            # A row that cannot be parsed is not evidence of anything and is
            # skipped rather than treated as a baseline. result_store.verify()
            # is the place that reports corruption; this is not that place.
            continue
        if _stream_of(result) != stream:
            continue
        identity = change_detection.accepted_identity_from_acquisition(result)
        if identity is None:
            # Recorded, but not ACCEPTED. It is not what this source says.
            continue
        return PriorAcceptedAcquisition(identity, row["idempotency_key"],
                                        row["recorded_at"])
    return None


def classify_acquisition(connection, capability_id, result,
                         exclude_idempotency_key=None):
    """Classify one acquisition result against this stream's history.

    Returns (Classification, PriorAcceptedAcquisition or None). The comparison
    itself stays in the pure Step 2B contract; this function only supplies the
    history it needs.
    """
    stream = _stream_of(result)
    if stream is None:
        runtime_errors.fail(
            "an acquisition result must name both sourceId and resourceId to be "
            "classified; without both there is no comparison stream",
            runtime_errors.ContractValidationError)
    prior = prior_accepted(connection, capability_id, stream[0], stream[1],
                           exclude_idempotency_key)
    verdict = change_detection.classify_acquisition_result(
        None if prior is None else prior.contentIdentity, result)
    return (verdict, prior)

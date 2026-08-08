#!/usr/bin/env python3
"""MOGO Automation Platform -- lease predicates. Pure functions only.

AUTHORITY
    Automation Platform Constitution v1.0 (senior) -- section 11
    MOGO-009 Architecture, section 18.1 -- claims are compare-and-set on
                                           (taskId, leaseGeneration)
    MOGO-009 Architecture, section 24   -- only the lease holder may write results
    MOGO-009 Contract Catalog, section C -- leaseHolder, leaseExpiresAt
    MOGO-011 Step 2 plan, sections 13, 14, 15

WHY THIS LEASE IS NOT CEREMONIAL
    The lease is NOT what provides mutual exclusion here. `fcntl.flock` does,
    and it does it better. A lease that were only a timestamp column nobody
    consults would be exactly the speculative abstraction the design principles
    forbid, and the right call would be to defer it. It earns its place by
    doing two jobs flock cannot:

    JOB 1 -- it turns Step 1's ASSUMPTION into a VERIFIED FACT.
        Step 1's recovery reclaimed every task in claimed/running, justified by
        "single-writer, so the previous holder is gone". That is true, and it is
        an assumption, and Constitution section 11 requires recovery to resume
        from a verified checkpoint, "never from an assumed one". With a lease,
        reclaim becomes a checked predicate over recorded facts: a task is
        reclaimable iff its lease is held by a PROVABLY ABSENT owner or has
        PROVABLY EXPIRED. "Provably absent" is decidable here -- we hold the
        exclusive flock, so no other runtime can be executing, and a lease
        stamped with a different runId therefore belongs to a process that
        cannot act. A task that is neither is LEFT ALONE rather than swept up.

    JOB 2 -- it makes writing a result without authority impossible rather than
        merely unlikely. Architecture section 24 becomes a check immediately
        before the result append instead of a sentence in a document.

    Both jobs exist today, with one process. That is the test the lease had to
    pass before being built.

OWNER IDENTITY
    `runner:<runId>`, where runId is a UUIDv4 minted once per run. Not a PID
    (reused, OS state rather than log state, meaningless after a reboot) and
    not a hostname (single-host by construction; adding one would imply a
    distribution model that does not exist). Recorded in the TaskClaimed
    payload, so replay reproduces it exactly.

NO CLOCK IN THIS MODULE
    `now_ms` is always an argument. Every predicate below is a pure function of
    recorded values and is unit-tested without a database or a process.
"""

from . import errors as runtime_errors  # noqa: E402

# A lease must outlive the execution it protects. Twice the declared wall-clock
# limit, floored, so that an execution bounded at the declared limit finishes
# with at least as much time again in hand.
LEASE_TTL_FLOOR_MS = 30000
LEASE_TTL_SAFETY_FACTOR = 2

HOLDER_PREFIX = "runner:"

# Reasons a lease may be reclaimed. Recorded in the TaskReclaimed payload, so
# an abandonment and an expiry are distinguishable in the audit trail.
REASON_OWNER_GONE = "owner_gone"
REASON_LEASE_EXPIRED = "lease_expired"
REASON_NO_LEASE = "no_lease"

RECLAIM_REASONS = (REASON_OWNER_GONE, REASON_LEASE_EXPIRED, REASON_NO_LEASE)


def holder_for_run(run_id):
    """The owner identity a run stamps on every lease it acquires."""
    if not isinstance(run_id, str) or not run_id.strip():
        runtime_errors.fail(
            "a lease holder needs a run identifier, got %r" % (run_id,),
            runtime_errors.ContractValidationError,
        )
    return HOLDER_PREFIX + run_id


def lease_ttl_ms(wall_clock_ms):
    """TTL for a capability declaring `wall_clock_ms` as its resource limit.

    Execution in this runtime is synchronous, in-process, single-threaded and
    bounded by the declared limit, so a lease at twice that limit cannot expire
    while its own execution is running under any normal condition.

    RENEWAL IS DELIBERATELY NOT IMPLEMENTED. It exists to keep a lease alive
    across an execution longer than its TTL, and no such execution can occur
    here -- building a heartbeat now would mean building a code path with no
    caller, which is a code path with no test. The condition that makes renewal
    necessary is named so a future step does not have to rediscover it: any
    execution that can exceed lease_ttl_ms / 2, which means a long-running
    acquisition, an out-of-process worker, or a daemon.
    """
    if isinstance(wall_clock_ms, bool) or not isinstance(wall_clock_ms, int):
        return LEASE_TTL_FLOOR_MS
    return max(LEASE_TTL_SAFETY_FACTOR * wall_clock_ms, LEASE_TTL_FLOOR_MS)


def lease_expiry_ms(acquired_at_ms, ttl_ms):
    """When a lease acquired at `acquired_at_ms` expires. Computed ONCE.

    Written into the TaskClaimed payload and copied from there forever after,
    never recomputed during projection. Same rule as the retry eligibility, for
    the same reason: a recomputed expiry would be a different deadline, and
    rebuild() would stop reproducing the state it rebuilt from.
    """
    return acquired_at_ms + ttl_ms


def is_expired(lease_expires_at_ms, now_ms):
    """True when a lease has run out. Pure.

    `>=`: a lease is not held during the millisecond it expires. Evaluated only
    after the monotonic clock guard has passed, so a backward clock cannot make
    an expired lease look live -- the runtime refuses to act at all first.
    """
    if lease_expires_at_ms is None:
        return True
    return now_ms >= lease_expires_at_ms


def is_held_by(lease_holder, lease_generation, expected_holder, expected_generation):
    """True when the lease is exactly the one this execution claimed with.

    The generation comparison is what makes this meaningful. Comparing only the
    holder would accept "some current lease of ours"; comparing the generation
    captured AT CLAIM TIME detects a reclaim that bumped the generation
    mid-flight, which is precisely the case Architecture section 24 exists to
    refuse.
    """
    return (lease_holder is not None
            and lease_holder == expected_holder
            and lease_generation == expected_generation)


def reclaim_reason(lease_holder, lease_expires_at_ms, now_ms, current_holder):
    """None means DO NOT RECLAIM. Otherwise the reason, for the record.

    Four quadrants, all unit-tested without a database:

      holder is another run  -> owner_gone      (provably absent: we hold the
                                                 exclusive flock, so the holder
                                                 cannot be executing)
      holder is ours, expired -> lease_expired
      holder is ours, live    -> None           <- the case Step 1 could not
                                                   express, and the one that
                                                   makes this a verification
                                                   rather than a rubber stamp
      no holder at all        -> no_lease       (a pre-Step-2 row; the upgrade
                                                 path is a first-class case)
    """
    if lease_holder is None:
        return REASON_NO_LEASE
    if lease_holder != current_holder:
        return REASON_OWNER_GONE
    if is_expired(lease_expires_at_ms, now_ms):
        return REASON_LEASE_EXPIRED
    return None

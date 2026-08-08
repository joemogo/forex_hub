#!/usr/bin/env python3
"""MOGO Automation Platform -- the only module permitted to read a clock.

AUTHORITY
    Automation Platform Constitution v1.0 (senior) -- sections 4.20, 11
    ADR-012 (accepted 2026-08-07)                  -- D-05 state is derived
    MOGO-009 Contract Catalog, conventions         -- ISO-8601 UTC millisecond
    MOGO-011 Step 2 plan, section 10

THE WHOLE RULE, IN ONE SENTENCE
    The clock is consulted only when producing a NEW event -- never when
    applying an old one.

    That sentence is what keeps replay deterministic. Every time value in the
    index is COPIED from an event payload that was written once; not one is
    derived during projection. Rebuild the index a year later and every row is
    byte-identical, because nothing in the rebuild path can ask what time it is.

WHY REAL TIME, AND NOT A LOGICAL TICK
    Two Step 2 facts are inherently temporal: "backoff elapsed" (Catalog
    section L) and "lease expired" (Constitution section 11). A logical counter
    would satisfy the tests and be useless in production -- a lease measured in
    log records does not expire when a machine is switched off, and a backoff
    measured in log records elapses instantly when the queue is busy and never
    when it is idle. Step 2 uses real UTC time and makes it deterministic by
    INJECTION rather than by avoidance.

    Tests never sleep, because the runtime never waits: `run` is one-shot and
    releases whatever is eligible now. A test that wants to observe a release
    advances a ManualClock and calls `run` again -- instant, deterministic, and
    exercising exactly the production code path.

MONOTONIC FLOOR -- FAIL CLOSED, NO TOLERANCE
    The runtime tracks the highest recordedAt in the log and refuses to append
    an event stamped earlier. The comparison is >=, not >, because many events
    inside one millisecond is normal and must stay legal. No skew window is
    granted and no forward clamp is applied: both would write a timestamp the
    clock never produced. See errors.ClockRollbackError.
"""

from datetime import datetime, timezone

from ..contracts import ids  # noqa: E402
from . import errors as runtime_errors  # noqa: E402

# Catalog conventions: YYYY-MM-DDTHH:MM:SS.mmmZ, literal Z, exactly three
# fractional digits. The committed regex in contracts/ids.py admits no offset,
# no naive value and no sub-millisecond precision, so timezone ambiguity is
# eliminated structurally rather than by convention.
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)

MILLISECONDS_PER_SECOND = 1000


def format_iso8601_ms(moment):
    """A timezone-aware datetime as the one format this platform produces."""
    if moment.tzinfo is None:
        runtime_errors.fail(
            "refusing to format a naive datetime; every platform timestamp is "
            "UTC-aware by construction",
            runtime_errors.ContractValidationError,
        )
    moment = moment.astimezone(timezone.utc)
    return "%s.%03dZ" % (moment.strftime("%Y-%m-%dT%H:%M:%S"),
                         moment.microsecond // 1000)


def parse_iso8601_ms(value, field="timestamp"):
    """Epoch milliseconds for a canonical timestamp. Refuses anything else.

    Validation is delegated to the committed contract, so a string this
    function accepts is exactly a string the event envelope would accept.
    """
    ids.require_iso8601_utc_ms(value, field)
    moment = datetime(
        int(value[0:4]), int(value[5:7]), int(value[8:10]),
        int(value[11:13]), int(value[14:16]), int(value[17:19]),
        int(value[20:23]) * 1000, tzinfo=timezone.utc,
    )
    return int((moment - _EPOCH).total_seconds() * MILLISECONDS_PER_SECOND)


def format_ms(epoch_ms):
    """Epoch milliseconds back to the canonical string. Inverse of the above."""
    if isinstance(epoch_ms, bool) or not isinstance(epoch_ms, int):
        runtime_errors.fail(
            "epoch milliseconds must be an integer, got %s"
            % (type(epoch_ms).__name__,),
            runtime_errors.ContractValidationError,
        )
    seconds, milliseconds = divmod(epoch_ms, MILLISECONDS_PER_SECOND)
    moment = datetime.fromtimestamp(seconds, tz=timezone.utc)
    return "%s.%03dZ" % (moment.strftime("%Y-%m-%dT%H:%M:%S"), milliseconds)


def elapsed_ms(from_iso, to_iso):
    """Whole milliseconds between two canonical timestamps. May be negative."""
    return parse_iso8601_ms(to_iso, "from") - parse_iso8601_ms(from_iso, "to")


class Clock(object):
    """The protocol every runtime component takes instead of reading time.

    Two methods, deliberately: an ISO string for the log and epoch
    milliseconds for arithmetic. Deriving one from the other at every call site
    is where rounding disagreements come from, so both are produced from one
    reading and cannot disagree.
    """

    def now_iso(self):
        raise NotImplementedError

    def now_ms(self):
        raise NotImplementedError

    def __call__(self):
        """Callable form, so a Clock is a drop-in for the Step 1 `clock()`."""
        return self.now_iso()


class SystemClock(Clock):
    """The only real clock read in `platform/**`.

    `datetime.now(timezone.utc)` -- aware and UTC by construction, so there is
    no local-time path anywhere in the platform to get wrong.
    """

    def now_iso(self):
        return format_iso8601_ms(datetime.now(timezone.utc))

    def now_ms(self):
        return parse_iso8601_ms(self.now_iso(), "now")


class ManualClock(Clock):
    """A clock that advances only when told. Tests and `run --now`.

    Not a fake in the sense of replacing the property under test: the runtime
    compares `now >= eligibleAt` identically whichever clock supplied `now`.
    What this removes is the WAITING, not the check.
    """

    def __init__(self, start="1970-01-01T00:00:00.000Z"):
        self._now_ms = (start if isinstance(start, int)
                        else parse_iso8601_ms(start, "start"))

    def now_iso(self):
        return format_ms(self._now_ms)

    def now_ms(self):
        return self._now_ms

    def advance_ms(self, delta):
        """Move forward. Refuses to move backward -- see the module docstring."""
        if isinstance(delta, bool) or not isinstance(delta, int):
            runtime_errors.fail(
                "clock advance must be an integer number of milliseconds, got %s"
                % (type(delta).__name__,),
                runtime_errors.ContractValidationError,
            )
        if delta < 0:
            runtime_errors.fail(
                "refusing to advance the clock by %d ms; a manual clock models "
                "the passage of time, not its reversal. To test a backward "
                "clock, set_to() an earlier value explicitly so the intent is "
                "visible at the call site." % (delta,),
                runtime_errors.ClockRollbackError,
            )
        self._now_ms += delta
        return self

    def set_to(self, value):
        """Set the clock, in either direction. Used to TEST rollback refusal."""
        self._now_ms = (value if isinstance(value, int)
                        else parse_iso8601_ms(value, "value"))
        return self


class MonotonicFloor(object):
    """The append-time guard: no event may be stamped before the last one.

    Holds the highest recordedAt observed, in epoch milliseconds. `check`
    raises BEFORE the caller appends anything, which is what makes a refusal
    leave the log untouched rather than partially written.
    """

    def __init__(self, floor_ms=None):
        self._floor_ms = floor_ms

    @property
    def floor_ms(self):
        return self._floor_ms

    @property
    def floor_iso(self):
        return None if self._floor_ms is None else format_ms(self._floor_ms)

    def observe(self, iso_timestamp):
        """Raise the floor to `iso_timestamp` if it is higher. Never lowers."""
        value = parse_iso8601_ms(iso_timestamp, "recordedAt")
        if self._floor_ms is None or value > self._floor_ms:
            self._floor_ms = value
        return self._floor_ms

    def check(self, iso_timestamp):
        """Raise ClockRollbackError if `iso_timestamp` precedes the floor.

        Returns the epoch milliseconds of the accepted timestamp. Equality is
        accepted: nine events inside one millisecond is normal and legal.
        """
        value = parse_iso8601_ms(iso_timestamp, "now")
        if self._floor_ms is not None and value < self._floor_ms:
            runtime_errors.fail(
                "clock returned %s but the log already records %s; refusing to "
                "append an event stamped %d ms in the past. No skew tolerance "
                "is granted and no forward clamp is applied -- both would write "
                "a timestamp the clock never produced. Fix the clock."
                % (iso_timestamp, self.floor_iso, self._floor_ms - value),
                runtime_errors.ClockRollbackError,
            )
        return value

    def accept(self, iso_timestamp):
        """check() then observe(). The only sequence the append path uses."""
        value = self.check(iso_timestamp)
        self.observe(iso_timestamp)
        return value

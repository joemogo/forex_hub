"""RFC3339 parsing for OANDA timestamps (up to nanosecond precision), UTC only."""
import datetime
import re

_RFC3339 = re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,9}))?Z$")


def parse_rfc3339(value):
    """An aware UTC datetime, or None for anything that is not a Z-suffixed RFC3339 string."""
    if not isinstance(value, str):
        return None
    m = _RFC3339.match(value)
    if not m:
        return None
    frac = (m.group(7) or "0").ljust(9, "0")
    try:
        return datetime.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                                 int(m.group(4)), int(m.group(5)), int(m.group(6)),
                                 int(frac[:6]), tzinfo=datetime.timezone.utc)
    except ValueError:
        return None


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc)

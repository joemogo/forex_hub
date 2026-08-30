"""Genuinely synthetic bars, constructed from documented arithmetic rules.

NOT derived from OANDA data in any way -- not transformed, shifted, resampled, rounded or
disguised. Every price here is produced by the closed-form rules below from an integer bar
index, and the file contains no market observation of any kind. That is the whole point: the
engine smoke test must be runnable and publishable without touching licensed data.

THE GENERATOR, stated so a reader can reproduce every bar by hand:

    zone_low       = 100.00, zone_high = 100.50 a SUPPORT zone, fixed and declared
    bar i close    = piecewise, by segment (below)
    open           = close        each bar opens at its own close
    high           = close + 0.05
    low            = close - 0.05
    timestamp      = 2020-01-01T00:00:00Z + i days

    open == close is deliberate. It makes high and low PURE FUNCTIONS OF THE CLOSE, so the
    swing-low geometry the machine looks for can be constructed exactly and read off the close
    series by hand. With open = previous close, a bar's low is pinned by its predecessor and two
    adjacent bars can be forced to share a low, which silently destroys the strict swing the
    machine requires -- measured while building this file.

  THE MACHINE'S SUPPORT-ZONE SEMANTICS, read from br_machine.py rather than assumed:
    zone_role 'support' => direction UP => a BREAK is a confirmed close ABOVE zone_high, and the
    RETEST is a strict swing LOW whose low sits inside [zone_low, zone_high]. An earlier draft of
    this generator had it inverted (break downward) and produced no decision in either case.

TWO CASES, deliberately constructed:

  SYN-QUALIFY   price builds history below the zone, BREAKS UP with confirmed closes above
                zone_high, pulls back into the zone forming a strict swing LOW inside it, then
                displaces upward. Built to satisfy the machine's documented rules end to end.

  SYN-REJECT    the same zone and the SAME break, but price never returns into the zone -- it
                continues upward and away. No retest can form, so the machine reaches BROKEN
                and stays there, producing NO decision.

Neither case encodes an expected ENTRY/STOP/TARGET. The smoke test asserts that a decision was
or was not produced and that the engine delivered every bar once, in order -- it does NOT
assert strategy geometry, and it is not a parity test. The historical 15-case parity corpus is
untouched and lives elsewhere.
"""

BASE = 100.0
STEP = 0.10
ZONE_LOW = 100.00
ZONE_HIGH = 100.50
ZONE_ROLE = 'support'
ZONE_FROM_INDEX = 20          # zone is declared available from this bar onward
N_BARS = 120

EPOCH_DAY_MS = 86400 * 1000
EPOCH_START = 1577836800000   # 2020-01-01T00:00:00Z, in ms


#: The retest dip, given as an explicit table so the strict swing low at index 52 can be
#: verified by eye: every neighbouring close is strictly higher, and low = close - 0.05.
_DIP = {46: 100.70, 47: 100.60, 48: 100.50, 49: 100.42, 50: 100.36, 51: 100.31,
        52: 100.27,                                    # <- the swing low; low = 100.22, in zone
        53: 100.33, 54: 100.40, 55: 100.48}


def _close_qualify(i):
    """Segment rules for the qualifying case."""
    if i < 30:                      # 1. build ATR history well BELOW the zone
        return 99.00 + (i % 5) * 0.04
    if i < 40:                      # 2. approach the zone from below
        return 99.20 + (i - 30) * 0.10
    if i < 46:                      # 3. BREAK UP: confirmed closes above zone_high
        return ZONE_HIGH + 0.25 + (i - 40) * 0.05
    if i < 56:                      # 4. RETEST: pull back into the zone, swing low at 52
        return _DIP[i]
    if i < 62:                      # 5. DISPLACE upward away from the zone
        return ZONE_HIGH + 0.20 + (i - 56) * 0.25
    return ZONE_HIGH + 1.70 + (i - 62) * 0.05         # 6. continuation


def _close_reject(i):
    """Same zone and the SAME break, but price never returns into the zone."""
    if i < 30:
        return 99.00 + (i % 5) * 0.04
    if i < 40:
        return 99.20 + (i - 30) * 0.10
    if i < 46:
        return ZONE_HIGH + 0.25 + (i - 40) * 0.05
    # straight up and away: the low never re-enters [zone_low, zone_high], so no retest exists
    return ZONE_HIGH + 0.55 + (i - 46) * 0.08


def _ohlc(prev_close, close):
    """open == close; high and low are pure functions of the close. See the module docstring."""
    return (round(close, 5), round(close + 0.05, 5),
            round(close - 0.05, 5), round(close, 5))


def series(case):
    """[(index, epoch_ms, o, h, l, c)] for 'qualify' or 'reject'. Pure and deterministic."""
    fn = _close_qualify if case == 'qualify' else _close_reject
    out, prev = [], None
    for i in range(N_BARS):
        c = round(fn(i), 5)
        o, h, l, c = _ohlc(prev, c)
        out.append((i, EPOCH_START + i * EPOCH_DAY_MS, o, h, l, c))
        prev = c
    return out


def csv_text(case):
    """The exact CSV the LEAN custom-data reader parses. One header line, then one bar per line."""
    lines = ['index,timestamp,open,high,low,close']
    for i, ms, o, h, l, c in series(case):
        lines.append('%d,%d,%.5f,%.5f,%.5f,%.5f' % (i, ms, o, h, l, c))
    return '\n'.join(lines) + '\n'


CASES = ('qualify', 'reject')

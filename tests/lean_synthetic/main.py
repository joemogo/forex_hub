"""MOGO synthetic Mode B ENGINE SMOKE TEST — both cases, one backtest.

WHAT THIS PROVES, if it passes: LEAN delivers bars through its OWN event-driven subscription
path into `on_data`, and the reviewed break-retest state machine consumes each delivered bar
exactly once, in order, with no bar arriving before its own EndTime -- for a QUALIFYING case
that must produce a decision and a REJECTING case that must produce none.

WHAT IT DOES NOT PROVE. Not parity with MOGO. Not strategy validation. Not profitability. It
says NOTHING about the historical 15 cases or the five break-cycle divergences. It places no
orders, adds no broker and holds nothing.

WHY IT IS SEPARATE. Mode A ran inside LEAN but "adds no securities and subscribes to no data
feed" and read embedded bars -- 14 data points -- so it never established event-driven
delivery. That is the single gap this closes, kept apart from the parity work.

DATA. Two synthetic CSVs generated from documented arithmetic in synthetic_bars.py. No market
observation of any kind. Served from a REVISION-PINNED gist URL, because the mutable raw URL
has no revision SHA.

EXPECTED ANSWERS LIVE HERE, IN VALIDATION CODE -- never inside br_machine.py, which is
byte-identical to the reviewed state machine (sha256 29e29578...) and knows nothing about them.
"""

QUALIFY_URL = 'https://gist.githubusercontent.com/joemogo/849a3ef9d9d13d7e7d74045428fbbdb7/raw/9e73b2341a80526530b11d4c29f6ca1cac8f312e/mogo_synthetic_qualify.csv'
REJECT_URL  = 'https://gist.githubusercontent.com/joemogo/849a3ef9d9d13d7e7d74045428fbbdb7/raw/9e73b2341a80526530b11d4c29f6ca1cac8f312e/mogo_synthetic_reject.csv'

#: Declared cases. A symbol not in here is NEVER served a fixture and NEVER parsed.
CASE_TICKERS = ('SYNQUAL', 'SYNREJ')

#: The case contract, asserted by the algorithm and justified by the documented rules:
#: a support zone is BROKEN by a confirmed close above zone_high, and the RETEST is a strict
#: swing LOW inside [zone_low, zone_high]. QUALIFY constructs one; REJECT never re-enters the
#: zone, so no retest can form.
EXPECT = {
    'SYNQUAL': {'bars': 120, 'first': 0, 'last': 119, 'state': 'LOCKED',
                'decision': True, 'locked_at': 55},
    'SYNREJ':  {'bars': 120, 'first': 0, 'last': 119, 'state': 'BROKEN',
                'decision': False, 'locked_at': None},
}

ZONE_LOW, ZONE_HIGH, ZONE_ROLE, ZONE_FROM_INDEX = 100.00, 100.50, 'support', 20

CONFIG = {
    'breakConfirmationCloses': 1, 'maxBarsBetweenBreakAndRetest': 50,
    'stopATRBuffer': 0.25, 'atrPeriod': 14, 'minRR': 2.0, 'trendSwingLookback': 3,
    'rejectionConfirmWithinBars': 1, 'rejectionDisplacementATRMultiplier': 0.25,
}

try:
    from AlgorithmImports import *
    IN_LEAN = True
except ImportError:                                # pragma: no cover - local inspection only
    IN_LEAN = False
    # Offline shim, so GetSource/Reader routing can be regression-tested without the engine.
    # Never used under LEAN, where the real classes are imported above.
    from datetime import datetime, timedelta

    class PythonData(object):
        """Stand-in for LEAN's PythonData indexer, modelling its TYPE STRICTNESS.

        A permissive dict would have accepted `row['BarIndex'] = int(...)` and the mock would
        have stayed green through the exact failure that killed two cloud runs. LEAN's setter
        is `value is double ? ... : value` over a .NET `object` parameter, and pythonnet finds
        no binding for a Python int -- so this shim refuses int the same way, deliberately.
        bool is refused too: it is an int subclass and would otherwise slip through.
        """

        def __init__(self):
            self._fields = {}

        def __setitem__(self, key, value):
            if not isinstance(key, str):
                raise TypeError('set_item index must be str, got %s' % type(value).__name__)
            if isinstance(value, bool) or isinstance(value, int):
                raise TypeError('No method matches given arguments for set_item: '
                                '(%r, %r)' % (str, type(value)))
            self._fields[key] = value

        def __getitem__(self, key):
            return self._fields[key]

    class SubscriptionTransportMedium(object):
        RemoteFile = 'RemoteFile'

    class SubscriptionDataSource(object):
        def __init__(self, source, transport):
            self.Source, self.TransportMedium = source, transport

from br_machine import BreakRetestMachine, Bar, S_LOCKED


class _SyntheticBarBase(PythonData):
    """One synthetic bar. ONE class per case, each serving ONE hard-coded URL.

    WHY NOT A DICTIONARY LOOKUP ON config.Symbol.Value. The first cloud run
    (project 35863117, `Hyper Active Red Orange Termite`, LEAN 2.5.0.0.18041) died in
    Initialize with:

        KeyError: 'QC-UNIVERSE-USERDEFINED-USA-BASE'   at GetSource

    `AddData` registers the security AND a user-defined universe, and LEAN builds the
    universe's config by COPY-CONSTRUCTING the security's subscription with the universe
    symbol substituted and isInternalFeed:true --

        new SubscriptionDataConfig(subscription, symbol: universeSymbol,
                                   isInternalFeed: true, fillForward: false, ...)

    -- so the universe config carries THIS SAME DATA TYPE with a different Symbol, and
    GetSource is called with it. A dict lookup therefore raises before any bar is fetched.

    A `.get()` guard alone would not be the right repair: it would still have to decide what
    to serve an unrecognised symbol, and serving it a case fixture is exactly the misrouting
    that must not happen. Splitting the type per case removes the decision entirely -- each
    class has exactly one URL and can only ever serve its own -- and `Reader` refuses any line
    whose config symbol is not a declared case, so the internal universe subscription parses
    nothing rather than being quietly fed a case's bars.
    """

    URL = None                                  # set by the per-case subclasses below

    def GetSource(self, config, date, isLive):
        # No lookup, no branch, no KeyError -- for the security symbol or the universe symbol.
        return SubscriptionDataSource(self.URL, SubscriptionTransportMedium.RemoteFile)

    def Reader(self, config, line, date, isLive):
        # The explicit refusal. Not a swallowed error: an unexpected symbol yields NO data,
        # and the algorithm separately counts anything that still reaches OnData.
        if config.Symbol.Value not in CASE_TICKERS:
            return None
        if not line or line[0].isalpha():
            return None
        parts = line.split(',')
        if len(parts) != 6:
            return None
        row = type(self)()
        row.Symbol = config.Symbol
        epoch_ms = int(parts[1])
        row.Time = datetime(1970, 1, 1) + timedelta(milliseconds=epoch_ms)
        row.EndTime = row.Time + timedelta(days=1)
        row.Value = float(parts[5])
        # EVERY custom field is stored as a Python float, and integers are recovered with
        # int() in OnData. This is not cosmetic and it is not "convert everything to float":
        #
        #   Muscular Red Orange Fly (algorithm c89520ff9658ee55535bb8c960133ae0,
        #   LEAN 2.5.0.0.18041) failed on EVERY row with
        #     No method matches given arguments for set_item: (<class 'str'>, <class 'int'>)
        #
        #   LEAN's PythonData string indexer (Common/Python/PythonData.cs) is
        #     set { SetProperty(index, value is double ? value.ConvertInvariant<decimal>()
        #                                             : value); }
        #   -- the setter's anticipated numeric type is DOUBLE, which it converts to decimal.
        #   A Python int has no binding, so the FIRST set_item call in this Reader
        #   (row['BarIndex'] = int(...)) raised before any of the float fields were reached.
        #   The OHLC assignments below were already floats, which is why they never surfaced.
        #
        # EXACTNESS IS PRESERVED, NOT TRADED AWAY. A float64 represents every integer up to
        # 2**53 exactly, and decimal carries 28-29 significant digits, so the bar index and a
        # millisecond epoch (~1.58e12, exact until the year 287396) both round-trip byte for
        # byte. That is ASSERTED below rather than assumed: a value that does not round-trip
        # is refused, never silently stored lossy.
        index_i = int(parts[0])
        if float(index_i) != index_i or float(epoch_ms) != epoch_ms:
            raise ValueError('synthetic row %r is not exactly representable as a float; '
                             'refusing rather than storing a lossy index or epoch' % parts[0])
        row['BarIndex'] = float(index_i)
        # The epoch is carried VERBATIM as a value, never re-derived from row.Time:
        # row.Time is a NAIVE datetime, so .timestamp() would reinterpret it in the HOST's
        # local timezone -- wrong by whole hours anywhere off UTC.
        row['EpochMs'] = float(epoch_ms)
        row['Open'], row['High'] = float(parts[2]), float(parts[3])
        row['Low'], row['Close'] = float(parts[4]), float(parts[5])
        return row


class SyntheticBarQualify(_SyntheticBarBase):
    URL = QUALIFY_URL


class SyntheticBarReject(_SyntheticBarBase):
    URL = REJECT_URL


CASE_TYPES = {'SYNQUAL': SyntheticBarQualify, 'SYNREJ': SyntheticBarReject}


class CaseState(object):
    """Per-case isolation, so one case cannot contaminate the other's evidence."""

    def __init__(self):
        self.delivered, self.seen = [], set()
        self.duplicates = self.out_of_order = self.lookahead = 0
        self.locked_at = None
        self.machine = BreakRetestMachine(CONFIG, ZONE_LOW, ZONE_HIGH, ZONE_ROLE,
                                          ZONE_FROM_INDEX)


class MogoSyntheticSmoke(QCAlgorithm if IN_LEAN else object):

    def Initialize(self):
        self.SetStartDate(2019, 12, 31)
        self.SetEndDate(2020, 6, 1)
        self.SetCash(100000)
        self.cases = {}
        self.by_symbol = {}
        self.unexpected_symbols = 0        # anything delivered that is not a declared case
        for ticker in CASE_TICKERS:
            sym = self.AddData(CASE_TYPES[ticker], ticker, Resolution.Daily).Symbol
            self.cases[ticker] = CaseState()
            self.by_symbol[sym] = ticker

    def OnData(self, data):
        for delivered_sym in list(data.Keys):
            if delivered_sym not in self.by_symbol:
                self.unexpected_symbols += 1
        for sym, ticker in self.by_symbol.items():
            if sym not in data:
                continue
            row = data[sym]
            st = self.cases[ticker]
            # Stored as float, recovered as int. LEAN hands these back as decimal; int()
            # is exact for both, and the Reader already refused anything that would not
            # round-trip.
            idx = int(row['BarIndex'])
            if idx in st.seen:
                st.duplicates += 1
                continue                          # never feed the machine twice
            if st.delivered and idx <= st.delivered[-1]:
                st.out_of_order += 1
            if row.EndTime > self.Time:           # a bar must not arrive before it has ended
                st.lookahead += 1
            st.seen.add(idx)
            st.delivered.append(idx)
            st.machine.on_bar(Bar(idx, int(row['EpochMs']),
                                  float(row['Open']), float(row['High']),
                                  float(row['Low']), float(row['Close'])))
            if st.machine.state == S_LOCKED and st.locked_at is None:
                st.locked_at = idx

    def OnEndOfAlgorithm(self):
        overall = []
        for ticker in ('SYNQUAL', 'SYNREJ'):
            st, exp = self.cases[ticker], EXPECT[ticker]
            d = st.machine.decision
            got_first = st.delivered[0] if st.delivered else None
            got_last = st.delivered[-1] if st.delivered else None
            checks = [
                ('delivered_event_count', len(st.delivered) == exp['bars'],
                 '%d of %d' % (len(st.delivered), exp['bars'])),
                ('first_index', got_first == exp['first'], str(got_first)),
                ('last_index', got_last == exp['last'], str(got_last)),
                ('strictly_increasing', st.out_of_order == 0, '%d' % st.out_of_order),
                ('each_bar_once', st.duplicates == 0, '%d' % st.duplicates),
                ('no_lookahead', st.lookahead == 0, '%d' % st.lookahead),
                ('machine_consumed_all', st.machine.bars_seen == len(st.delivered),
                 '%d vs %d' % (st.machine.bars_seen, len(st.delivered))),
                ('terminal_state', st.machine.state == exp['state'],
                 '%s want %s' % (st.machine.state, exp['state'])),
                ('decision_presence', bool(d) == exp['decision'],
                 'got %s want %s' % (bool(d), exp['decision'])),
                ('locked_at', st.locked_at == exp['locked_at'],
                 '%s want %s' % (st.locked_at, exp['locked_at'])),
            ]
            failed = [n for n, ok, _ in checks if not ok]
            for n, ok, detail in checks:
                self.Log('SMOKE-CHECK %-8s %-24s %-4s %s'
                         % (ticker, n, 'PASS' if ok else 'FAIL', detail))
            self.Log('SMOKE-CASE %s %s bars=%d state=%s decision=%s locked_at=%s failed=%s'
                     % (ticker, 'PASS' if not failed else 'FAIL', len(st.delivered),
                        st.machine.state, bool(d), st.locked_at, ','.join(failed) or 'none'))
            overall += failed
        # Per-case isolation: the two machines must be distinct objects with distinct evidence.
        iso = self.cases['SYNQUAL'].machine is not self.cases['SYNREJ'].machine
        self.Log('SMOKE-CHECK GLOBAL   case_state_isolated       %s %s'
                 % ('PASS' if iso else 'FAIL', iso))
        if not iso:
            overall.append('case_state_isolated')
        # The internal universe subscription must never deliver into OnData.
        clean = self.unexpected_symbols == 0
        self.Log('SMOKE-CHECK GLOBAL   no_unexpected_symbols     %s %d'
                 % ('PASS' if clean else 'FAIL', self.unexpected_symbols))
        if not clean:
            overall.append('no_unexpected_symbols')
        self.Log('SMOKE-VERDICT %s engine=%s failed=%s'
                 % ('PASS' if not overall else 'FAIL',
                    'LEAN' if IN_LEAN else 'plain-python', ','.join(overall) or 'none'))

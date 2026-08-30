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

URLS = {'SYNQUAL': QUALIFY_URL, 'SYNREJ': REJECT_URL}

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

from br_machine import BreakRetestMachine, Bar, S_LOCKED


class SyntheticBar(PythonData if IN_LEAN else object):
    """One synthetic bar, parsed by LEAN's own subscription reader. The URL is chosen by the
    SYMBOL, so both cases share one reviewed reader and cannot diverge in parsing."""

    def GetSource(self, config, date, isLive):
        return SubscriptionDataSource(URLS[config.Symbol.Value],
                                      SubscriptionTransportMedium.RemoteFile)

    def Reader(self, config, line, date, isLive):
        if not line or line[0].isalpha():
            return None
        parts = line.split(',')
        if len(parts) != 6:
            return None
        row = SyntheticBar()
        row.Symbol = config.Symbol
        row.Time = datetime(1970, 1, 1) + timedelta(milliseconds=int(parts[1]))
        row.EndTime = row.Time + timedelta(days=1)
        row.Value = float(parts[5])
        row['BarIndex'] = int(parts[0])
        row['Open'], row['High'] = float(parts[2]), float(parts[3])
        row['Low'], row['Close'] = float(parts[4]), float(parts[5])
        return row


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
        for ticker in ('SYNQUAL', 'SYNREJ'):
            sym = self.AddData(SyntheticBar, ticker, Resolution.Daily).Symbol
            self.cases[ticker] = CaseState()
            self.by_symbol[sym] = ticker

    def OnData(self, data):
        for sym, ticker in self.by_symbol.items():
            if sym not in data:
                continue
            row = data[sym]
            st = self.cases[ticker]
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
            st.machine.on_bar(Bar(idx, int(row.Time.timestamp() * 1000),
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
        self.Log('SMOKE-VERDICT %s engine=%s failed=%s'
                 % ('PASS' if not overall else 'FAIL',
                    'LEAN' if IN_LEAN else 'plain-python', ','.join(overall) or 'none'))

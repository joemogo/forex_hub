# region imports
# MOGO -> LEAN  Mode B  ALEX Break & Retest  EVENT-DRIVEN STATE MACHINE
#
# ============================================================================================
# THIS MODULE IS THE DECISION PATH. IT IS INFORMATION-ISOLATED BY CONSTRUCTION.
# ============================================================================================
#
# It has NO imports of any project module and NO imports at all beyond the standard library
# name below. It cannot reach:
#     * the case collection (CASES / vectors_part*)
#     * any expected-answer block
#     * any recorded entry / stop / target / retest / break answer
#     * any comparison or scoring result
#     * any bar that has not yet been delivered to on_bar()
#
# The machine receives ONE Bar at a time and never a container of bars. It retains a BOUNDED
# window of bars -- 2*trendSwingLookback + 1 -- which is the exact span the swing test needs.
# It therefore cannot look ahead (the bars do not exist yet) and cannot look far back (the
# bars have been dropped). test_mode_b.py asserts this bound by walking the machine's reachable
# object graph after a full run, so the property is checked mechanically, not asserted in prose.
#
# Moving logic into on_data() does NOT by itself make look-ahead impossible. What makes it
# impossible here is that the decision path is never handed the array in the first place.
# endregion

from collections import deque

UP, DOWN = 'upThroughResistance', 'downThroughSupport'

# states
S_AWAIT_ZONE = 'AWAIT_ZONE'      # zone geometry not yet available at this bar index
S_WATCH      = 'WATCH'           # zone live, no confirmed break yet
S_BROKEN     = 'BROKEN'          # >=1 confirmed break, hunting a qualifying retest
S_LOCKED     = 'LOCKED'          # decision produced and frozen; later bars cannot change it


class Bar(object):
    """One delivered bar. Immutable-by-convention, __slots__ so nothing can be attached to it,
    and deliberately carrying NO back-reference to whatever produced it."""
    __slots__ = ('index', 't', 'o', 'h', 'l', 'c')

    def __init__(self, index, t, o, h, l, c):
        self.index = index
        self.t = t
        self.o = float(o)
        self.h = float(h)
        self.l = float(l)
        self.c = float(c)

    def __repr__(self):
        return 'Bar(%d,%s)' % (self.index, self.t)


class BreakRetestMachine(object):
    """Incremental ALEX Break & Retest. One bar in, one ledger record out.

    Constructor arguments are the ONLY information the decision path ever receives beyond the
    bar stream: frozen strategy parameters, and the supplied zone geometry/role gated by the
    bar index from which that geometry is treated as available.
    """

    def __init__(self, config, zone_low, zone_high, zone_role, zone_available_from_index):
        cfg = dict(config)
        self._need = cfg['breakConfirmationCloses']
        self._lb = cfg['trendSwingLookback']
        self._period = cfg['atrPeriod']
        self._max_bars = cfg['maxBarsBetweenBreakAndRetest']
        self._buf = cfg['stopATRBuffer']
        self._rr = cfg['minRR']
        self._confirm = cfg['rejectionConfirmWithinBars']
        self._disp_mult = cfg['rejectionDisplacementATRMultiplier']

        self._zl = float(zone_low)
        self._zh = float(zone_high)
        self._role = zone_role
        self._zone_from = zone_available_from_index

        # direction is derived from the SUPPLIED role, never from a recorded answer
        if zone_role == 'support':
            self._dir = UP
        elif zone_role == 'resistance':
            self._dir = DOWN
        else:
            self._dir = None
        self._want = 'low' if self._dir == UP else 'high'

        # ---- bounded state, all derived from bars already delivered ----
        self._win = deque(maxlen=2 * self._lb + 1)   # the only bars retained, ever
        self._trs = deque(maxlen=self._period)       # true ranges for the ATR mean
        self._atr = deque(maxlen=self._lb + 1)       # ATR at the last lookback+1 bars
        self._prev_close = None
        self._prev_beyond = False
        self._run = 0
        self._n = 0                                  # bars delivered so far
        self._crossings = []                         # (position, barIndex) of confirmed breaks
        self._state = S_AWAIT_ZONE
        self._decision = None                        # frozen once set

    # ---------------------------------------------------------------- read-only accessors
    @property
    def state(self):
        return self._state

    @property
    def decision(self):
        """The locked decision, or None. Returned as a fresh dict so a caller -- including the
        audit layer -- cannot mutate machine state through it."""
        return dict(self._decision) if self._decision else None

    @property
    def bars_seen(self):
        return self._n

    @property
    def retained_bar_count(self):
        """Used by the structural test: how many Bar objects the machine is holding."""
        return len(self._win)

    # ---------------------------------------------------------------- internals
    def _atr_now(self):
        """Arithmetic mean of the last `period` true ranges. None until enough bars exist.
        Mirrors production calcATR: simple mean, not Wilder smoothing."""
        if self._n < self._period + 1:
            return None
        if len(self._trs) < self._period:
            return None
        return sum(self._trs) / len(self._trs)

    def _swing_at_centre(self):
        """Strict on BOTH sides, `lookback` bars each way, evaluated at the window centre.
        The window is exactly wide enough and no wider."""
        lb = self._lb
        if len(self._win) < 2 * lb + 1:
            return None
        w = list(self._win)
        c = w[lb]
        if all(w[lb - k].h < c.h and w[lb + k].h < c.h for k in range(1, lb + 1)):
            return 'high'
        if all(w[lb - k].l > c.l and w[lb + k].l > c.l for k in range(1, lb + 1)):
            return 'low'
        return None

    # ---------------------------------------------------------------- the event handler
    def on_bar(self, bar):
        """Consume exactly one bar. Returns a ledger record describing the transition.

        Every branch below reads only: this bar, bounded state derived from earlier bars, the
        frozen parameters, and the supplied zone. Nothing else is in scope.
        """
        state_before = self._state
        p = self._n
        self._n += 1

        # ---- true range and ATR (positions >= 1 contribute a true range, as in calcATR)
        if p >= 1:
            pc = self._prev_close
            self._trs.append(max(bar.h - bar.l, abs(bar.h - pc), abs(bar.l - pc)))
        self._prev_close = bar.c
        self._win.append(bar)
        self._atr.append(self._atr_now())

        zone_live = bar.index >= self._zone_from
        event = 'BAR'
        brk_candidate = None
        ret_candidate = None

        if self._dir is None:
            self._state = S_AWAIT_ZONE
            return self._record(bar, state_before, 'NO_SUPPLIED_ZONE_ROLE', zone_live, None, None)

        if not zone_live:
            self._state = S_AWAIT_ZONE
            return self._record(bar, state_before, 'ZONE_NOT_YET_AVAILABLE', zone_live, None, None)

        if self._state == S_AWAIT_ZONE:
            self._state = S_WATCH

        # ---- break detection: a confirmed close through the zone, in the supplied direction
        beyond = (bar.c > self._zh) if self._dir == UP else (bar.c < self._zl)
        prev_inside = (p == 0) or (not self._prev_beyond)
        self._run = self._run + 1 if beyond else 0
        if self._run >= self._need and prev_inside:
            self._crossings.append((p, bar.index))
            brk_candidate = bar.index
            event = 'BREAK_CONFIRMED'
            if self._state == S_WATCH:
                self._state = S_BROKEN
        self._prev_beyond = beyond

        # ---- once locked, later bars update nothing. This is what the poison control exercises.
        if self._decision is not None:
            self._state = S_LOCKED
            return self._record(bar, state_before, 'POST_LOCK_BAR', zone_live, brk_candidate, None)

        # ---- retest evaluation at the anchor that this bar completes
        lb = self._lb
        a = p - lb
        if a < 0 or not self._crossings:
            return self._record(bar, state_before, event, zone_live, brk_candidate, None)

        prior = [x for x in self._crossings if x[0] < a]
        if not prior:
            return self._record(bar, state_before, event, zone_live, brk_candidate, None)
        b_pos, b_index = max(prior)

        if self._swing_at_centre() != self._want:
            return self._record(bar, state_before, event, zone_live, brk_candidate, None)

        w = list(self._win)
        anchor = w[lb]
        price = anchor.l if self._want == 'low' else anchor.h
        if not (self._zl <= price <= self._zh):
            return self._record(bar, state_before, event, zone_live, brk_candidate, None)

        atr_a = self._atr[0] if len(self._atr) == lb + 1 else None
        if atr_a is None:
            return self._record(bar, state_before, event, zone_live, brk_candidate, None)

        wend = min(p, a + self._confirm)
        seg = w[lb + 1: lb + (wend - a) + 1]
        if not seg:
            return self._record(bar, state_before, event, zone_live, brk_candidate, None)
        disp = (max(x.h for x in seg) - price) if self._want == 'low' else (price - min(x.l for x in seg))
        if disp < self._disp_mult * atr_a:
            return self._record(bar, state_before, event, zone_live, brk_candidate, None)

        bsb = bar.index - b_index
        if not (1 <= bsb <= self._max_bars):
            return self._record(bar, state_before, event, zone_live, brk_candidate, None)

        # ---- QUALIFIED. Geometry is computed from THIS bar and the supplied zone edges only.
        ret_candidate = bar.index
        entry = bar.c
        atr = self._atr[-1]
        if atr is None:
            return self._record(bar, state_before, 'INSUFFICIENT_BARS_FOR_ATR', zone_live,
                                brk_candidate, ret_candidate)
        if self._dir == UP:
            stop = self._zl - self._buf * atr
            target = entry + self._rr * (entry - stop)
            direction = 'buy'
        else:
            stop = self._zh + self._buf * atr
            target = entry - self._rr * (stop - entry)
            direction = 'sell'
        risk = abs(entry - stop)

        self._decision = {
            'qualifies': True,
            'direction': direction,
            'brokenDirection': self._dir,
            'breakBarIndex': b_index,
            'retestBarIndex': bar.index,
            'anchorBarIndex': anchor.index,
            'barsSinceBreak': bsb,
            'entryPrice': entry,
            'originalStop': stop,
            'target': target,
            'atrAtQualification': atr,
            'plannedRR': (abs(target - entry) / risk) if risk > 0 else 0.0,
            'lockedAtBarIndex': bar.index,
            'barsConsumedAtLock': self._n,
        }
        self._state = S_LOCKED
        return self._record(bar, state_before, 'QUALIFIED', zone_live, brk_candidate, ret_candidate)

    # ---------------------------------------------------------------- ledger
    def _record(self, bar, state_before, event, zone_live, brk_candidate, ret_candidate):
        d = self._decision
        return {
            'barIndex': bar.index,
            'timestamp': bar.t,
            'stateBefore': state_before,
            'event': event,
            'stateAfter': self._state,
            'zoneAvailable': bool(zone_live),
            'breakCandidate': brk_candidate,
            'breakCyclesSeen': len(self._crossings),
            'retestCandidate': ret_candidate,
            # the break cycle the machine SELECTED as owning this retest. This is the field the
            # unresolved 10/15 divergence lives in, so the ledger names it explicitly.
            'selectedBreakBarIndex': d['breakBarIndex'] if d else None,
            'anchorBarIndex': d['anchorBarIndex'] if d else None,
            'qualified': d is not None,
            'direction': d['brokenDirection'] if d else None,
            'entry': d['entryPrice'] if d else None,
            'stop': d['originalStop'] if d else None,
            'target': d['target'] if d else None,
        }

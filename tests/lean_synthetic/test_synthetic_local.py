#!/usr/bin/env python3
"""LOCAL validation of the synthetic smoke package. THIS IS NOT AN ENGINE RUN.

Everything here runs in plain python. It proves the package is internally consistent and that
the state machine behaves as the smoke test will assert -- it says NOTHING about whether LEAN
delivers the bars, which is the entire question the engine run exists to answer.
"""
import hashlib, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import synthetic_bars as sb
from br_machine import BreakRetestMachine, Bar, S_LOCKED, S_BROKEN

CONFIG = {'breakConfirmationCloses': 1, 'maxBarsBetweenBreakAndRetest': 50,
          'stopATRBuffer': 0.25, 'atrPeriod': 14, 'minRR': 2.0, 'trendSwingLookback': 3,
          'rejectionConfirmWithinBars': 1, 'rejectionDisplacementATRMultiplier': 0.25}

fails = []
def check(ok, msg, detail=''):
    print('%s  %s%s' % ('PASS' if ok else 'FAIL', msg, ('  [%s]' % detail) if detail else ''))
    if not ok:
        fails.append(msg)

def run(case):
    m = BreakRetestMachine(CONFIG, sb.ZONE_LOW, sb.ZONE_HIGH, sb.ZONE_ROLE, sb.ZONE_FROM_INDEX)
    for i, ms, o, h, l, c in sb.series(case):
        m.on_bar(Bar(i, ms, o, h, l, c))
    return m

print('=== 1. the data is synthetic and reproducible ===')
a, b = sb.csv_text('qualify'), sb.csv_text('qualify')
check(a == b, 'the generator is deterministic across calls')
check(len(sb.series('qualify')) == 120, 'qualify case is 120 bars')
check(len(sb.series('reject')) == 120, 'reject case is 120 bars')
# CODE ONLY, not prose. The first draft searched the whole file and matched the word "OANDA"
# in the generator's own disclaimer -- the same comment-satisfies-the-assertion trap that a
# run_all fixture hit earlier in this sprint. The claim is about what the generator READS, so
# it is asserted against imports, file opens and string literals in executable positions.
import ast as _ast
_tree = _ast.parse(open(os.path.join(HERE, 'synthetic_bars.py'), encoding='utf-8').read())
_names = []
for _n in _ast.walk(_tree):
    if isinstance(_n, _ast.Import):
        _names += [a.name for a in _n.names]
    elif isinstance(_n, _ast.ImportFrom):
        _names.append(_n.module or '')
    elif isinstance(_n, _ast.Call) and getattr(_n.func, 'id', '') in ('open', 'load'):
        _names.append('OPEN_CALL')
    elif isinstance(_n, _ast.Constant) and isinstance(_n.value, str):
        if _n is not getattr(_tree, 'body', [None])[0] or True:
            _names.append(_n.value if len(_n.value) < 120 else '')
_blob = ' '.join(_names)
_doc = _ast.get_docstring(_tree) or ''
_blob = _blob.replace(_doc, '')
check(not re.search(r'oanda|OANDA|MBR\d|vectors_part|\.csv', _blob)
      and 'OPEN_CALL' not in _names,
      'the generator imports nothing, opens no file, and names no OANDA source, corpus file '
      'or historical vector in code')
for i, ms, o, h, l, c in sb.series('qualify'):
    if not (l <= o <= h and l <= c <= h):
        check(False, 'bar %d is not well-formed OHLC' % i); break
else:
    check(True, 'every bar is well-formed OHLC (low <= open,close <= high)')

print('\n=== 2. the QUALIFY case produces a decision ===')
q = run('qualify')
check(q.state == S_LOCKED, 'state is LOCKED', q.state)
d = q.decision
check(bool(d) and d.get('qualifies') is True, 'a qualifying setup is produced')
check(d and d['breakBarIndex'] < d['anchorBarIndex'] < d['retestBarIndex'],
      'break precedes the anchor precedes the retest',
      d and '%s < %s < %s' % (d['breakBarIndex'], d['anchorBarIndex'], d['retestBarIndex']))
check(d and d['lockedAtBarIndex'] < 119, 'the decision locks before the final bar',
      d and str(d['lockedAtBarIndex']))
anchor_low = round(sb._DIP[52] - 0.05, 5)
check(sb.ZONE_LOW <= anchor_low <= sb.ZONE_HIGH,
      'the constructed swing low sits INSIDE the zone', str(anchor_low))

print('\n=== 3. the REJECT case produces NO decision -- and not vacuously ===')
r = run('reject')
check(r.state == S_BROKEN, 'state is BROKEN: the break happened', r.state)
check(r.decision is None, 'but no decision is produced')
check(q.decision is not None and r.decision is None,
      'the two cases DIFFER, so the reject case is not passing because nothing ever qualifies')

print('\n=== 4. single consumption, ordering, and no future bar ===')
m = BreakRetestMachine(CONFIG, sb.ZONE_LOW, sb.ZONE_HIGH, sb.ZONE_ROLE, sb.ZONE_FROM_INDEX)
seen, order_ok = set(), True
for i, ms, o, h, l, c in sb.series('qualify'):
    if i in seen:
        order_ok = False
    seen.add(i)
    m.on_bar(Bar(i, ms, o, h, l, c))
check(order_ok and len(seen) == 120, 'each bar index is consumed exactly once')
check(m.bars_seen == 120, 'the machine counted every delivered bar', str(m.bars_seen))
ts = [x[1] for x in sb.series('qualify')]
check(all(ts[i] < ts[i + 1] for i in range(len(ts) - 1)), 'timestamps are strictly increasing')

print('\n=== 5. truncation control: the decision uses only bars up to the lock ===')
lock = q.decision['barsConsumedAtLock']
tm = BreakRetestMachine(CONFIG, sb.ZONE_LOW, sb.ZONE_HIGH, sb.ZONE_ROLE, sb.ZONE_FROM_INDEX)
for i, ms, o, h, l, c in sb.series('qualify')[:lock]:
    tm.on_bar(Bar(i, ms, o, h, l, c))
check(tm.decision == q.decision,
      'truncating the feed AT the lock bar reproduces the identical decision -- no later bar '
      'contributed to it')
pm = BreakRetestMachine(CONFIG, sb.ZONE_LOW, sb.ZONE_HIGH, sb.ZONE_ROLE, sb.ZONE_FROM_INDEX)
poisoned = list(sb.series('qualify'))
for k in range(lock, len(poisoned)):                      # corrupt every bar AFTER the lock
    i, ms, o, h, l, c = poisoned[k]
    poisoned[k] = (i, ms, o + 50, h + 50, l + 50, c + 50)
for i, ms, o, h, l, c in poisoned:
    pm.on_bar(Bar(i, ms, o, h, l, c))
check(pm.decision == q.decision, 'poisoning every bar AFTER the lock changes nothing')
pm2 = BreakRetestMachine(CONFIG, sb.ZONE_LOW, sb.ZONE_HIGH, sb.ZONE_ROLE, sb.ZONE_FROM_INDEX)
poisoned2 = list(sb.series('qualify'))
for k in range(lock - 6, len(poisoned2)):                 # corrupt FROM before the lock
    i, ms, o, h, l, c = poisoned2[k]
    poisoned2[k] = (i, ms, o + 50, h + 50, l + 50, c + 50)
for i, ms, o, h, l, c in poisoned2:
    pm2.on_bar(Bar(i, ms, o, h, l, c))
check(pm2.decision != q.decision,
      'poisoning FROM BEFORE the lock DOES move the decision -- the control is not vacuous')

print('\n=== 6. package integrity ===')
for name in ('synthetic_bars.py', 'br_machine.py', 'main.py'):
    p = os.path.join(HERE, name)
    check(os.path.exists(p), 'present: %s' % name,
          hashlib.sha256(open(p, 'rb').read()).hexdigest()[:16])
main_src = open(os.path.join(HERE, 'main.py'), encoding='utf-8').read()
check('SubscriptionTransportMedium.RemoteFile' in main_src,
      'the algorithm uses the only transport measured to deliver into on_data')
check('SMOKE-VERDICT' in main_src, 'the algorithm emits a single machine-readable verdict line')
check('REPLACE-ME' not in main_src, 'no placeholder URL remains')
check(main_src.count('gist.githubusercontent.com') == 2,
      'both cases point at published fixtures')
import re as _re
pinned = _re.findall(r'/raw/([0-9a-f]{40})/', main_src)
check(len(pinned) == 2 and len(set(pinned)) == 1,
      'both URLs are REVISION-PINNED to the same gist revision, not mutable raw links',
      (pinned[0][:12] if pinned else 'none'))

print('\n=== 7. the algorithm asserts BOTH cases, and expectations live OUTSIDE the machine ===')
check("'SYNQUAL'" in main_src and "'SYNREJ'" in main_src, 'both cases are wired')
check('EXPECT = {' in main_src, 'expected answers are declared in the algorithm validation block')
machine_src = open(os.path.join(HERE, 'br_machine.py'), encoding='utf-8').read()
check(not _re.search(r'SYNQUAL|SYNREJ|EXPECT|locked_at', machine_src),
      'the DECISION-MAKING state machine knows nothing about the cases or expected answers')
for case, want_state, want_dec in (('qualify', S_LOCKED, True), ('reject', S_BROKEN, False)):
    m = run(case)
    check(m.state == want_state and bool(m.decision) is want_dec,
          'local %s case matches the expectation the algorithm asserts' % case,
          '%s decision=%s' % (m.state, bool(m.decision)))
q_lock = run('qualify').decision['lockedAtBarIndex']
check(("'locked_at': %d" % q_lock) in main_src,
      'the algorithm expects the locked_at the machine actually produces', str(q_lock))

print('\n' + '=' * 78)
if fails:
    print('RESULT: FAIL -- %d check(s): %s' % (len(fails), '; '.join(fails)))
else:
    print('RESULT: PASS -- package is internally consistent and the state machine behaves as')
    print('        the engine smoke test will assert.')
    print('        THIS IS NOT AN ENGINE RUN. It says NOTHING about whether LEAN delivers')
    print('        the bars -- that is the entire question main.py exists to answer.')
sys.exit(1 if fails else 0)

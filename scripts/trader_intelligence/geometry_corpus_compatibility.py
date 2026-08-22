"""Replay every preserved trade observation through MOGO's canonical trade-geometry contract.

Answers one bounded question: does the guard installed at MOGO's execution boundaries reject
anything MOGO has ever actually done? Run it before changing MIN_RISK_PIPS or validateTradeGeometry,
and after importing new forward evidence.

This is a faithful port of validateTradeGeometry() from index.html. If the two ever disagree this
script is wrong, not the engine -- re-derive it from the source rather than adjusting the corpus.

Populations are kept DISTINGUISHABLE (CLAUDE.md): replay observations measure the IMPLEMENTATION
alex_g_sr_v1, never the trader ALEX_G, and are never merged into a forward figure.

Usage:  python3 scripts/trader_intelligence/geometry_corpus_compatibility.py
Exit 1 if any preserved observation would be refused by the contract.
"""
import json,glob,math,collections
MIN=1.0
def pip_size(pair): return 0.01 if 'JPY' in pair else 0.0001
def validate(d,entry,stop,target,pip,floor=MIN):
    for v in (entry,stop,pip):
        if not isinstance(v,(int,float)) or isinstance(v,bool) or not math.isfinite(v): return('NON_FINITE',None)
    if not pip>0: return('NON_FINITE',None)
    if target is not None and not(isinstance(target,(int,float)) and not isinstance(target,bool) and math.isfinite(target)): return('NON_FINITE',None)
    if d not in('buy','sell'): return('NON_FINITE',None)
    sr=(entry-stop) if d=='buy' else (stop-entry)
    if not sr>0: return('STOP_WRONG_SIDE',sr/pip)
    rp=sr/pip
    if rp<floor-1e-9: return('RISK_TOO_SMALL',rp)
    if target is not None:
        rw=(target-entry) if d=='buy' else (entry-target)
        if not rw>0: return('TARGET_WRONG_SIDE',rp)
    return('VALID',rp)

by=collections.defaultdict(lambda: collections.Counter())
tight=collections.defaultdict(list)
bad=[]
n=0
for f in sorted(glob.glob('docs/trader-intelligence/evidence/observations/*.json')):
    o=json.load(open(f)); n+=1
    sid=o.get('strategyId') or 'UNKNOWN'
    lane='replay' if 'sourceType=replay_observation' in (o.get('notes') or '') else 'forward'
    key=(sid,lane)
    pip=pip_size(o.get('instrument',''))
    st,rp=validate(o.get('direction'),o.get('entry'),o.get('stop'),o.get('target'),pip)
    by[key][st]+=1
    if rp is not None and st=='VALID': tight[key].append((rp,o['observationId'],o.get('instrument')))
    if st!='VALID': bad.append((o['observationId'],sid,lane,st,rp,o.get('direction'),o.get('entry'),o.get('stop'),o.get('target')))
print(f"observations scanned: {n}")
for key in sorted(by):
    c=by[key]; t=sorted(tight[key])[:3]
    print(f"\n  strategyId={key[0]}  population={key[1]}  n={sum(c.values())}")
    for k,v in c.most_common(): print(f"     {k}: {v}")
    if t: print(f"     tightest risk (pips): "+", ".join(f"{r:.3f} [{i} {p}]" for r,i,p in t))
print("\nNON-VALID records:", len(bad))
for b in bad: print("   ",b)

import sys
sys.exit(1 if bad else 0)

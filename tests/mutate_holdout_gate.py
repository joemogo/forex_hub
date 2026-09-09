import re, subprocess, sys, tempfile, os, shutil
src = open('scripts/holdout_gate.py').read()

MUTS = [
 ("M1 stability: hash the position, not the id",
  'h = hashlib.sha256((str(seed) + "\\x00" + str(record_id)).encode("utf-8")).hexdigest()',
  'h = hashlib.sha256((str(seed)).encode("utf-8")).hexdigest()'),
 ("M2 tamper: manifest hash is constant",
  'return hashlib.sha256(json.dumps(locked, sort_keys=True).encode("utf-8")).hexdigest()',
  'return "constant"'),
 ("M3 run-once: forget that it already ran",
  'if m.get("runs"):\n        problems.append(f"ALREADY RUN {len(m[\'runs\'])} time(s). The holdout is spent.")',
  'if False:\n        problems.append("never")'),
 ("M4 population: stop hashing the ids",
  'ids = sorted(str(r.get(id_field)) for r in records)',
  'ids = []'),
 ("M5 verdict: pass regardless of the checks",
  '"passed": all(checks.values())',
  '"passed": True'),
 ("M6 duplicate ids tolerated",
  'raise ValueError(f"duplicate id {rid!r}: a record could land on both sides")',
  'pass'),
 ("M7 seed ignored in the split",
  'return "HOLDOUT" if _bucket(seed, record_id) < holdout_ratio * BUCKETS else "TRAIN"',
  'return "HOLDOUT" if _bucket("fixed", record_id) < holdout_ratio * BUCKETS else "TRAIN"'),
 ("M8 empty freeze allowed",
  'raise ValueError("cannot freeze an empty population")',
  'records = [{"tradeId":"z","side":"kept","realizedR":0.0},{"tradeId":"y","side":"rejected","realizedR":0.0}]'),
]
d = tempfile.mkdtemp()
shutil.copy('scripts/candidate_power.py', d)
bad = 0
for name, old, new in MUTS:
    if old not in src:
        print(f"ANCHOR MISS -- {name}"); bad += 1; continue
    if src.count(old) != 1:
        print(f"ANCHOR NOT UNIQUE ({src.count(old)}x) -- {name}"); bad += 1; continue
    p = os.path.join(d, 'holdout_gate.py')
    open(p,'w').write(src.replace(old, new))
    r = subprocess.run([sys.executable, p, '--selftest'], capture_output=True, text=True)
    caught = r.returncode != 0
    print(f"{'caught  ' if caught else 'SURVIVED'} -- {name}")
    if not caught:
        bad += 1
        print("   ", (r.stdout+r.stderr).strip().splitlines()[-1:])
print("\nmutation harness:", "PASS" if bad==0 else f"FAIL ({bad})")
sys.exit(1 if bad else 0)

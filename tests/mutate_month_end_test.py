#!/usr/bin/env python3
"""Can the month_end_test fixtures fail? Break the module and check.

This harness matters more than most. month_end_test.py decides a candidate, and every one
of the mutations below produces a plausible-looking number rather than an error -- an
inverted sign, a calendar-day window, an averaged instead of summed window. Those are the
failures that get believed.
"""
import os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SRC = open(os.path.join(REPO, "scripts", "month_end_test.py")).read()

MUTATIONS = [
    ("M1 sign inverted: falling yields read as losses",
     "out.append((d1, -duration * (y1 - y0) * 100.0))",
     "out.append((d1, duration * (y1 - y0) * 100.0))"),
    ("M2 window averaged instead of summed (reports ~1/3 the effect as decay)",
     "mean = sum(events) / n",
     "mean = sum(events) / n / 3.0"),
    ("M3 month boundary ignored: one global window at the end of the series",
     "by_month.setdefault((d.year, d.month), []).append(i)",
     "by_month.setdefault(('all',), []).append(i)"),
    ("M4 window off by one: last 2 trading days instead of 3",
     "for i in idxs[-window:]:", "for i in idxs[-(window - 1):]:"),
    ("M5 holidays read as zero yield instead of dropped",
     "            except ValueError:\n                continue                      # \".\" -- market holiday, genuinely absent",
     "            except ValueError:\n                y = 0.0"),
    ("M6 significance hardcoded true",
     '"positive_and_significant": (se is not None) and (mean / se) > Z95,',
     '"positive_and_significant": True,'),
    ("M7 decay floor never binds",
     '"above_decay_floor": mean > DECAY_FLOOR_BP,', '"above_decay_floor": True,'),
    ("M8 degenerate sample returns a number instead of refusing",
     'if n < 2:\n        return {"ok": False, "reason": "TOO_FEW_MONTHS", "n_events": n}',
     'if False:\n        return {"ok": False, "reason": "x", "n_events": n}'),
    ("M9 zero window accepted",
     'if window <= 0:\n        raise ValueError("window must be positive")',
     'if False:\n        raise ValueError("x")'),
    ("M10 detection floor always cleared",
     '"above_detection_floor": (floor is not None) and abs(mean) > floor,',
     '"above_detection_floor": True,'),
]


def main():
    tmp = tempfile.mkdtemp()
    shutil.copy(os.path.join(REPO, "scripts", "candidate_power.py"), tmp)
    target = os.path.join(tmp, "month_end_test.py")
    bad = 0

    open(target, "w").write(SRC)
    ctl = subprocess.run([sys.executable, target, "--selftest"], capture_output=True, text=True)
    if ctl.returncode != 0:
        print("CONTROL FAILED -- unmutated selftest does not pass; nothing below means anything")
        print((ctl.stdout + ctl.stderr).strip()); return 1
    print("control  -- unmutated selftest passes")

    for name, old, new in MUTATIONS:
        if old not in SRC:
            print(f"ANCHOR MISS   -- {name}"); bad += 1; continue
        if SRC.count(old) != 1:
            print(f"ANCHOR x{SRC.count(old)}    -- {name}"); bad += 1; continue
        open(target, "w").write(SRC.replace(old, new))
        for pyc in ("__pycache__",):
            shutil.rmtree(os.path.join(tmp, pyc), ignore_errors=True)
        r = subprocess.run([sys.executable, target, "--selftest"], capture_output=True, text=True)
        print(("caught   -- " if r.returncode != 0 else "SURVIVED -- ") + name)
        if r.returncode == 0:
            bad += 1

    print()
    print(f"mutation harness: {'PASS' if not bad else f'FAIL ({bad})'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

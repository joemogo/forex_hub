#!/usr/bin/env python3
"""Can the bond_carry_test fixtures fail? Break the module and check.

This harness carries more weight than most: bond carry is the last candidate standing out of
twenty screened, and every mutation below produces a plausible number rather than an error.
An inverted signal, a look-ahead position, a union instead of an intersection -- those are the
failures that get believed.
"""
import os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SRC = open(os.path.join(REPO, "scripts", "bond_carry_test.py")).read()

MUTATIONS = [
    ("M1 signal inverted: hold long when the curve is INVERTED",
     "pos = 1 if carry > 0 else -1", "pos = -1 if carry > 0 else 1"),
    ("M2 look-ahead: decide the position on the month it is applied to",
     "carry = y0 - s0", "carry = y1 - s0"),
    ("M3 price sign flipped: rising yields read as gains for a long",
     "total_bp = (y0 / 12.0) * 100.0 - duration * (y1 - y0) * 100.0",
     "total_bp = (y0 / 12.0) * 100.0 + duration * (y1 - y0) * 100.0"),
    ("M4 carry term dropped entirely",
     "total_bp = (y0 / 12.0) * 100.0 - duration", "total_bp = (0.0) * 100.0 - duration"),
    ("M5 excess return never nets the short rate",
     "excess_bp = total_bp - (s0 / 12.0) * 100.0", "excess_bp = total_bp"),
    ("M6 cost charged on EVERY month, not only on a switch",
     "if pos != prev_pos:\n            r -= cost_bp", "if True:\n            r -= cost_bp"),
    ("M7 cost never charged at all",
     "            r -= cost_bp", "            r -= 0.0"),
    ("M8 holidays read as a zero interest rate",
     "            except ValueError:\n                continue\n            if math.isfinite(v):",
     "            except ValueError:\n                v = 0.0\n            if math.isfinite(v):"),
    ("M9 months unioned instead of intersected",
     "keys = sorted(set(L) & set(S))", "keys = sorted(set(L) | set(S))"),
    ("M10 significance hardcoded true",
     '"positive": (se is not None) and (m / se) > Z95}', '"positive": True}'),
    ("M11 retention floor never binds",
     '"retained_half": (ret is not None) and ret >= DECAY_FLOOR_FRACTION,',
     '"retained_half": True,'),
    ("M12 degenerate sample returns a number instead of refusing",
     'if n < 24:\n        return {"ok": False, "reason": "TOO_FEW_MONTHS", "n": n}',
     'if False:\n        return {"ok": False, "reason": "x", "n": n}'),
    ("M13 month-end picks the FIRST observation of the month, not the last",
     "if k not in out or d > out[k][0]:", "if k not in out:"),
    ("M14 detection floor always cleared",
     '"oos_above_floor": abs(oos["mean_bp"]) > oos["detection_floor_bp"],',
     '"oos_above_floor": True,'),
]


def main():
    tmp = tempfile.mkdtemp()
    shutil.copy(os.path.join(REPO, "scripts", "candidate_power.py"), tmp)
    target = os.path.join(tmp, "bond_carry_test.py")
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
        shutil.rmtree(os.path.join(tmp, "__pycache__"), ignore_errors=True)
        r = subprocess.run([sys.executable, target, "--selftest"], capture_output=True, text=True)
        print(("caught   -- " if r.returncode != 0 else "SURVIVED -- ") + name)
        if r.returncode == 0:
            bad += 1

    print()
    print(f"mutation harness: {'PASS' if not bad else f'FAIL ({bad})'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

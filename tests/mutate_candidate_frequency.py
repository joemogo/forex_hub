#!/usr/bin/env python3
"""Can the candidate_frequency fixtures actually fail? Break the module eight ways and check.

A passing selftest is not evidence until breaking the mechanism makes it fail. This project
has twice shipped a fixture that could not fail -- GUARD-1/2 searched the whole file for a
phrase that appeared in three places, and a median-markup fixture whose two answers were
identical sorted or unsorted. Both looked green. Neither was checking anything.
"""
import os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SRC = open(os.path.join(REPO, "scripts", "candidate_frequency.py")).read()

MUTATIONS = [
    ("M1 horizon: everything fits in a human lifetime",
     "HUMAN_HORIZON_YEARS = 5.0", "HUMAN_HORIZON_YEARS = 1e9"),
    ("M2 frequency ignored: rare effects look as good as frequent ones",
     "return n / per_year", "return n / 1000000.0"),
    ("M3 zero frequency accepted instead of refused",
     "if per_year is None or not (per_year > 0):\n        return None",
     "if False:\n        return None"),
    ("M4 forward-confirmable regardless of the horizon",
     '"confirmable_forward": (yrs is not None) and yrs <= HUMAN_HORIZON_YEARS,',
     '"confirmable_forward": True,'),
    ("M5 cost never charged",
     "net = effect - cost", "net = effect"),
    ("M6 history always sufficient",
     'out["confirmable_from_history"] = (n_needed is not None) and avail >= n_needed',
     'out["confirmable_from_history"] = True'),
    ("M7 cost floor always passes",
     '"clears_cost": net > 0,', '"clears_cost": True,'),
    ("M8 history sample count ignores frequency",
     "avail = history_years * per_year", "avail = history_years * 1000"),
]


def main():
    tmp = tempfile.mkdtemp()
    shutil.copy(os.path.join(REPO, "scripts", "candidate_power.py"), tmp)
    target = os.path.join(tmp, "candidate_frequency.py")
    bad = 0

    # Control: the unmutated module must PASS, or every "caught" below is meaningless.
    open(target, "w").write(SRC)
    ctl = subprocess.run([sys.executable, target, "--selftest"],
                         capture_output=True, text=True)
    if ctl.returncode != 0:
        print("CONTROL FAILED -- the unmutated selftest does not pass; nothing below means anything")
        print((ctl.stdout + ctl.stderr).strip())
        return 1
    print("control  -- unmutated selftest passes")

    for name, old, new in MUTATIONS:
        if old not in SRC:
            print(f"ANCHOR MISS   -- {name}"); bad += 1; continue
        if SRC.count(old) != 1:
            print(f"ANCHOR x{SRC.count(old)}    -- {name}"); bad += 1; continue
        open(target, "w").write(SRC.replace(old, new))
        r = subprocess.run([sys.executable, target, "--selftest"],
                           capture_output=True, text=True)
        if r.returncode != 0:
            print(f"caught   -- {name}")
        else:
            print(f"SURVIVED -- {name}"); bad += 1

    print()
    print(f"mutation harness: {'PASS' if not bad else f'FAIL ({bad})'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

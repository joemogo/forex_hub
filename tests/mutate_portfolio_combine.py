#!/usr/bin/env python3
"""Can the portfolio_combine fixtures fail?

This harness guards the most dangerous tool in the project. Every other gate REJECTS
candidates; this one can make four weak effects look like one strong one. A broken version
would manufacture an edge out of noise and every downstream decision would inherit it.
"""
import os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SRC = open(os.path.join(REPO, "scripts", "portfolio_combine.py")).read()

MUTATIONS = [
    ("M1 diversification benefit applied even at perfect correlation",
     "denom = 1.0 + (k - 1) * rho\n    if denom <= 0:\n        return None\n    return math.sqrt(k / denom)",
     "denom = 1.0\n    if denom <= 0:\n        return None\n    return math.sqrt(k / denom)"),
    ("M2 sqrt dropped: benefit scales with k instead of sqrt(k)",
     "return math.sqrt(k / denom)", "return k / denom"),
    ("M3 ZEROS produce a positive combined Sharpe (the misuse)",
     "mean_s = sum(sharpes) / k", "mean_s = (sum(sharpes) / k) + 0.4"),
    ("M4 a non-positive Sharpe is given a finite horizon anyway",
     "years = ((Z95 / combined) ** 2) if combined > 0 else None",
     "years = ((Z95 / abs(combined)) ** 2) if combined != 0 else None"),
    ("M5 an impossible correlation is accepted instead of refused",
     "if rho > 1.0 or rho < -1.0 / (k - 1) + 1e-12:\n        return None",
     "if False:\n        return None"),
    ("M6 optimal weighting can come out BELOW the best component alone",
     "quad = a * sum_sq + b * (sum_s * sum_s - sum_sq)",
     "quad = a * sum_sq * 0.5 + b * (sum_s * sum_s - sum_sq)"),
    # M7 RETIRED. It mutated the `quad <= 0` guard in combine_optimal. That branch is
    # unreachable for any valid input: C is positive definite for every valid equicorrelation
    # rho, so s'C^-1 s > 0 for all non-zero s (brute-forced over 400,000 draws, minimum
    # 2.9e-04), and the all-zeros vector gets the same 0.0 from sqrt(0) either way. A fixture
    # for a branch no input can distinguish is a test that cannot fail, which is the exact
    # thing this harness exists to prevent. Retired with the reason rather than papered over.
    ("M8 optimal off-diagonal sign flipped (correlation rewarded, not penalised)",
     "b = -rho / denom", "b = rho / denom"),
    ("M9 an unknown component Sharpe is treated as zero instead of refusing",
     "    if any(s is None for s in sharpes):\n        return {\"ok\": False, \"reason\": \"COMPONENT_SHARPE_UNKNOWN\"}\n    k = len(sharpes)\n    mult",
     "    if False:\n        return {\"ok\": False, \"reason\": \"COMPONENT_SHARPE_UNKNOWN\"}\n    k = len(sharpes)\n    mult"),
    ("M10 the human horizon is made infinite, so everything is confirmable",
     "HUMAN_HORIZON_YEARS = 15.0", "HUMAN_HORIZON_YEARS = 1e9"),
    ("M11 k=1 gets a phantom diversification benefit",
     "    if k == 1:\n        return 1.0 if -1.0 <= rho <= 1.0 else None",
     "    if k == 1:\n        return 2.0 if -1.0 <= rho <= 1.0 else None"),
    ("M12 beats_best_alone hardcoded true",
     '"beats_best_alone": combined > max(sharpes)}', '"beats_best_alone": True}'),
]


def main():
    tmp = tempfile.mkdtemp()
    shutil.copy(os.path.join(REPO, "scripts", "candidate_power.py"), tmp)
    target = os.path.join(tmp, "portfolio_combine.py")
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

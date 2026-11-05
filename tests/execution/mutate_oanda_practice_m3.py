#!/usr/bin/env python3
"""Mutation gate for the M3 read-only boundary: every guard, deleted, must turn the M3 suite red.

Same discipline as mutate_oanda_practice.py: each mutant replaces one exact
snippet (which must occur exactly once), clears __pycache__, runs
tests/execution/test_oanda_practice_m3.py, requires a non-zero exit, restores
the file in a finally block, and the run ends by checking every mutated file's
bytes against the hashes taken before the first mutant.

    python3 tests/execution/mutate_oanda_practice_m3.py
"""
import hashlib
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
SUITES = ["tests.execution.test_oanda_practice_m3"]

RO = "execution/oanda_practice_m3/readonly.py"
PF = "execution/oanda_practice_m3/preflight.py"
CLI = "execution/mogo_practice_preflight.py"
FILES = (RO, PF, CLI)

MUTANTS = [
    ("R1 GET only", [(RO, '        if method != "GET":\n', "        if False:\n")]),
    ("R2 no body", [(RO, '        if body is not None:\n            raise ReadOnlyRefused("a read-only', '        if False:\n            raise ReadOnlyRefused("a read-only')]),
    ("R3 practice host", [(RO, 'raise ReadOnlyRefused("the request is not to the practice host")', "pass")]),
    ("R4 configured account", [(RO, 'raise ReadOnlyRefused("the request is not for the configured account")', "pass")]),
    ("R5 path escape", [(RO, ' or ".." in parts.path or "//" in parts.path', "")]),
    ("R6 header injection", [(RO, 'raise ReadOnlyRefused("malformed headers")', "pass")]),
    ("R7 redirect refused", [(RO, "            if 300 <= status < 400:\n", "            if False:\n")]),
    ("R8 loopback proxy only", [(RO, 'raise ProxyRefused("only an http proxy on a loopback address with an explicit port is allowed")', "pass")]),
    ("R9 tunnel to the practice host", [(RO, "conn.set_tunnel(cfg.PRACTICE_HOST, 443,", "conn.set_tunnel(host, port,")]),
    ("R10 TLS verification", [(RO, "ssl_context or ssl.create_default_context()", "ssl_context or ssl._create_unverified_context()")]),
    ("R11 transport read allow-list", [(RO, 'raise ReadOnlyRefused("operation %r is not a read" % (operation,))', "pass")]),
    ("R12 transport takes only the read-only opener", [(RO, "        if not isinstance(opener, ReadOnlyHttpsOpener):\n", "        if False:\n")]),
    ("P1 credentials-rejected stop", [(PF, '        if status in (401, 403):\n            raise PreflightStop("CREDENTIALS_REJECTED")\n', "")]),
    ("P2 configured-account stop", [(PF, ' or account.get("id") != account_id:', ":")]),
    ("P3 account masking", [(PF, '    return "%s-***-****-%s" % (groups[0], groups[3])', "    return account_id")]),
    ("P4 cap blocker", [(PF, '            if history["capped_or_paged"]:\n', "            if False:\n")]),
    ("P5 currency blocker", [(PF, '        if account.get("currency") != instrument[-3:]:\n', "        if False:\n")]),
    ("P6 sign model compares", [(PF, 'row["agreed" if previous + effect == stated else "disagreed"] += 1', 'row["agreed"] += 1')]),
    ("P7 redirect is a boundary stop", [(PF, '"BOUNDARY_RedirectRefused" if "RedirectRefused" in str(exc)', '"BOUNDARY_RedirectRefused" if False')]),
    ("C1 A2 required", [(CLI, '    if args.authorization != "A2":\n', "    if False:\n")]),
]


def clear_pycache():
    for root in (os.path.join(REPO, "execution"), HERE):
        for dp, dns, _ in os.walk(root):
            for d in list(dns):
                if d == "__pycache__":
                    shutil.rmtree(os.path.join(dp, d), ignore_errors=True)


def snapshot():
    return {f: hashlib.sha256(open(os.path.join(REPO, f), "rb").read()).hexdigest() for f in FILES}


def run_suite():
    clear_pycache()
    return subprocess.run([sys.executable, "-m", "unittest"] + SUITES, cwd=REPO,
                          capture_output=True, text=True).returncode


def apply_and_run(edits):
    originals = {}
    try:
        for fname, old, new in edits:
            path = os.path.join(REPO, fname)
            current = open(path, encoding="utf-8").read()
            originals.setdefault(fname, current)
            if current.count(old) != 1:
                return None
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(current.replace(old, new))
        return run_suite()
    finally:
        for fname, text in originals.items():
            with open(os.path.join(REPO, fname), "w", encoding="utf-8") as handle:
                handle.write(text)
        clear_pycache()


def main():
    before = snapshot()
    if run_suite() != 0:
        print("FAIL: the unmutated suite does not pass; mutation results would be meaningless")
        return 1
    killed, survived, unapplied = [], [], []
    for name, edits in MUTANTS:
        rc = apply_and_run(edits)
        bucket = unapplied if rc is None else (killed if rc != 0 else survived)
        bucket.append(name)
        print("%-9s %s" % ({None: "UNAPPLIED"}.get(rc, "KILLED" if rc else "SURVIVED"), name))
    restored = before == snapshot()
    print("RESULT: %d/%d killed, %d survived, %d unapplied; sources restored: %s"
          % (len(killed), len(MUTANTS), len(survived), len(unapplied), restored))
    ok = not survived and not unapplied and restored
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

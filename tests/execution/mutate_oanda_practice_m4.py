#!/usr/bin/env python3
"""Mutation gate for M4 (the A3 write path and the first-trade guards): each guard, deleted,
must turn the execution suites red.

Same discipline as the M1/M2 and M3 gates: each mutant replaces exact snippets (each
must occur exactly once), clears __pycache__, runs the M1, M2, M3 and M4 suites,
requires a non-zero exit, restores in a finally block, and the run ends by checking
every mutated file's bytes against the hashes taken before the first mutant.
DEFENCE-IN-DEPTH pairs (the CLI's CloseGrant and the executor both check a close
authorization's account and validity window) are mutated together.

    python3 tests/execution/mutate_oanda_practice_m4.py
"""
import hashlib
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
SUITES = ["tests.execution.test_oanda_practice", "tests.execution.test_oanda_practice_m2",
          "tests.execution.test_oanda_practice_m3", "tests.execution.test_oanda_practice_m4"]

RISK = "execution/oanda_practice/risk.py"
AUTH = "execution/oanda_practice/authorization.py"
EXE = "execution/oanda_practice/executor.py"
ADP = "execution/oanda_practice/adapter.py"
JRN = "execution/oanda_practice/journal.py"
A3 = "execution/oanda_practice_m4/a3.py"
CLI = "execution/mogo_practice_trade.py"
FILES = (RISK, AUTH, EXE, ADP, JRN, A3, CLI)

MUTANTS = [
    # the broker's constraints, proven before the entry
    ("K1 constraints are assessed", [(EXE, "        codes += risk.assess_constraints(auth, quote, account, spec)\n", "")]),
    ("K2 pending orders refuse", [(RISK, "    elif account.pending_order_count != 0:\n", "    elif False:\n")]),
    ("K3 an unstated pending count is not zero", [(RISK, "    if account.pending_order_count is None:\n", "    if False:\n")]),
    ("K4 pendingOrderCount is parsed, not assumed", [(ADP, "pending_order_count=pending if isinstance(pending, int)\n                              and not isinstance(pending, bool) else None)", "pending_order_count=0)")]),
    ("K5 broker minimum units", [(RISK, "    if units < spec.minimum_trade_size:\n", "    if False:\n")]),
    ("K6 broker maximum units", [(RISK, "    if units > spec.maximum_order_units:\n", "    if False:\n")]),
    ("K7 stop price precision", [(RISK, "    if _decimals(auth.stop_loss_price) > spec.display_precision:\n", "    if False:\n")]),
    ("K8 price bound precision", [(RISK, "    if _decimals(price_bound(auth, quote)) > spec.display_precision:\n", "    if False:\n")]),
    ("K9 stop distance pip floor", [(RISK, "distance < MIN_STOP_DISTANCE_PIPS * pip or ", "")]),
    ("K10 stop distance spread floor", [(RISK, " or distance < MIN_STOP_SPREAD_MULTIPLE * (quote.ask - quote.bid)", "")]),
    ("K11 five-dollar ceiling", [(AUTH, 'HARD_MAX_LOSS = Decimal("5")', 'HARD_MAX_LOSS = Decimal("10")')]),
    ("K12 fill price is the trade's own", [(ADP, '    price = _decimal(opened.get("price"))\n    if price is None:\n        price = _decimal(fill.get("price"))', '    price = _decimal(fill.get("price"))')]),
    # the separate close authorization
    ("K13 executor checks the close authorization", [(EXE, '            authz.check_close_current(close_auth, self.config, self._clock(), pos, intent["client_order_id"])\n', "            pass\n")]),
    ("K14 the close names this trade", [(AUTH, '    if close_auth.trade_id != position["trade_id"] or close_auth.client_order_id != client_order_id:\n', "    if False:\n")]),
    ("K15 close account (both layers)", [(AUTH, '    if close_auth.account_id != config.account_id:\n        raise AuthorizationRefused("close authorization names a different account")\n', ""),
                                         (A3, '        if close_auth.account_id != config.account_id:\n            raise A3Refused("the close authorization names a different account")\n', "")]),
    ("K16 close validity window (both layers)", [(AUTH, '    if not close_auth.issued_at <= now < close_auth.expires_at:\n        raise AuthorizationRefused("close authorization is not valid at this time")\n', ""),
                                                 (A3, '        if not close_auth.issued_at <= when < close_auth.expires_at:\n            raise A3Refused("the close authorization is not valid at this time")\n', "")]),
    ("K17 close authorization spent once (both layers)", [(EXE, '        if self.journal.close_authorization_used(close_auth.close_authorization_id):\n            raise OrderRefused(["CLOSE_AUTHORIZATION_ALREADY_USED"])\n', ""),
                                                          (JRN, '                except sqlite3.IntegrityError:\n                    raise JournalRefused(["CLOSE_AUTHORIZATION_ALREADY_USED"])', '                except sqlite3.IntegrityError:\n                    pass')]),
    ("K18 close authorization mode", [(AUTH, '    if data["mode"] != cfg.MODE:\n        raise AuthorizationRefused("close authorization mode', '    if False:\n        raise AuthorizationRefused("close authorization mode')]),
    ("K19 close authorization lifetime", [(AUTH, 'auth.expires_at - auth.issued_at > HARD_MAX_LIFETIME:\n        raise AuthorizationRefused("close authorization lifetime', 'False:\n        raise AuthorizationRefused("close authorization lifetime')]),
    ("K20 close authorizations are append-only", [(JRN, '"broker_transactions", "close_authorizations")', '"broker_transactions")')]),
    # the A3 write opener and its grants
    ("A1 no grant, no write opener", [(A3, "        if not isinstance(grant, (EntryGrant, CloseGrant)):\n", "        if False:\n")]),
    ("A2 a spent grant refuses", [(A3, "        if self.writes:\n", "        if False:\n")]),
    ("A3 spent before the socket", [(A3, "        self.writes += 1                       # spent BEFORE the socket: never sent twice\n", "")]),
    ("A4 entry is POST orders only", [(A3, '        if method != "POST" or parts.path != prefix + "orders" or parts.query:\n', "        if False:\n")]),
    ("A5 no unauthorized order fields", [(A3, " or set(order) != _ENTRY_ORDER_KEYS", "")]),
    ("A6 the authorized order", [(A3, "        if any(order.get(k) != v for k, v in wanted.items()):\n", "        if False:\n")]),
    ("A7 the authorized stop", [(A3, '        if not isinstance(stop, dict) or _positive_decimal(stop.get("price")) != a.stop_loss_price:\n', "        if False:\n")]),
    ("A8 the authorized client id", [(A3, 'raise A3Refused("the entry order does not carry the authorized client order id")', "pass")]),
    ("A9 a price bound", [(A3, 'raise A3Refused("the entry order has no price bound")', "pass")]),
    ("A10 the entry grant needs a current authorization", [(A3, "        authz.check_current(auth, config, now or timeutil.utc_now())\n", "")]),
    ("A11 close is PUT on its trade only", [(A3, 'raise A3Refused("the close grant permits only PUT close for the authorized trade")', "pass")]),
    ("A12 close is full only", [(A3, '        if payload != {"units": "ALL"}:\n', "        if False:\n")]),
    ("A13 GETs keep the read-only checks", [(A3, "            return super().__call__(method, url, headers, body, timeout)\n", "            return self._send(method, self.check_target(url, headers), headers, body, timeout)\n")]),
    # the operator command
    ("C1 submit needs A3", [(CLI, '    if args.command == "submit" and args.authorization != "A3":\n', "    if False:\n")]),
    ("C2 submit verifies protection at once", [(CLI, '                result["reconcile"] = executor.reconcile()\n', "                pass\n")]),
    ("C3 an unprotected position needs the operator", [(CLI, '            return (3 if _attention(result["position"], (jn.PROTECTED,)) else 0), result\n', "            return 0, result\n")]),
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
        print("%-9s %s" % ({None: "UNAPPLIED"}.get(rc, "KILLED" if rc else "SURVIVED"), name), flush=True)
    restored = before == snapshot()
    print("RESULT: %d/%d killed, %d survived, %d unapplied; sources restored: %s"
          % (len(killed), len(MUTANTS), len(survived), len(unapplied), restored))
    ok = not survived and not unapplied and restored
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Mutation gate for the M1 practice executor: every guard, deleted, must turn the suite red.

Each mutant replaces one exact snippet (which must occur exactly once) in one
file of execution/oanda_practice/, clears __pycache__, runs
tests/execution/test_oanda_practice.py, and requires a non-zero exit. The file is
restored in a finally block, and the run ends by checking every source file's
bytes against the hashes taken before the first mutant.

The two DEFENCE-IN-DEPTH pairs (a check made both in submit() and again inside
the journal's atomic reserve()) are mutated TOGETHER as well as singly: removing
one layer alone is caught by the other by design, so the single mutants are
listed in EXPECTED_SURVIVORS and the paired mutants must die.

    python3 tests/execution/mutate_oanda_practice.py
"""
import hashlib
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
PKG = os.path.join(REPO, "execution", "oanda_practice")
SUITE = os.path.join(HERE, "test_oanda_practice.py")

T, C, A, R, J, E, D, K = ("transport.py", "config.py", "authorization.py", "risk.py",
                          "journal.py", "executor.py", "adapter.py", "kill.py")

MUTANTS = [
    # transport
    ("T1 host re-assert", [(T, "if parts.scheme != \"https\" or parts.hostname != cfg.PRACTICE_HOST or parts.port is not None:", "if False:")]),
    ("T2 operation allow-list", [(T, "if operation not in OPERATIONS:\n", "if False:\n")]),
    ("T3 parameter shapes", [(T, "if not isinstance(value, str) or not _PARAM_SHAPES[name].match(value):", "if not isinstance(value, str):")]),
    ("T4 caller cannot set account", [(T, "        if \"account\" in params:\n            raise TransportRefused(\"the account is fixed by configuration\")\n", "")]),
    ("T5 kill at send time", [(T, "if is_write and self._kill is not None and self._kill.engaged():", "if False:")]),
    ("T6 send failure is UNCERTAIN", [(T, "raise SendUncertain(\"%s: %s\" % (operation, type(exc).__name__))", "raise NotSent(\"x\")")]),
    ("T7 default opener sends nothing", [(T, "        raise NotSent(\"network access is disabled in M1\")", "        return 200, b\"{}\"")]),
    # config
    ("C1 forbidden keys", [(C, "        if key in _FORBIDDEN_KEYS:\n", "        if False:\n")]),
    ("C2 live-family refusal", [(C, "if key != \"token\" and _LIVE_MARKER in json.dumps(value).lower():", "if False:")]),
    ("C3 file permissions", [(C, "if info.st_mode & (stat.S_IRWXG | stat.S_IRWXO):", "if False:")]),
    ("C4 redacted repr", [(C, "        return \"Secret(<redacted>)\"", "        return \"Secret(%s)\" % self._value")]),
    ("C5 no pickling", [(C, "        raise TypeError(\"a Secret cannot be pickled\")", "        return (Secret, (self._value,))")]),
    # authorization
    ("A1 mode", [(A, "if data[\"mode\"] != cfg.MODE:", "if False:")]),
    ("A2 hard max units", [(A, "not 1 <= units <= HARD_MAX_UNITS:", "not 1 <= units:")]),
    ("A3 hard max loss", [(A, "if auth.max_loss > HARD_MAX_LOSS:", "if False:")]),
    ("A4 max lifetime", [(A, "auth.expires_at - auth.issued_at > HARD_MAX_LIFETIME:", "False:")]),
    ("A5 account match", [(A, "if auth.account_id != config.account_id:", "if False:")]),
    ("A6 validity window", [(A, "if not auth.issued_at <= now < auth.expires_at:", "if False:")]),
    ("A7 deterministic identity", [(A, "(\"MOGO-PRACTICE|\" + self.authorization_id)", "(\"MOGO-PRACTICE|\" + self.authorization_id + str(id(self)))")]),
    ("A8 quote-age ceiling", [(A, "not 1 <= age <= HARD_MAX_QUOTE_AGE_SECONDS:", "not 1 <= age:")]),
    # risk
    ("R1 account currency", [(R, "if account.currency != auth.instrument.split(\"_\")[1]:", "if False:")]),
    ("R2 tradeable", [(R, "if quote.tradeable is not True:", "if False:")]),
    ("R3 stale quote", [(R, "if age > auth.max_quote_age_seconds:", "if False:")]),
    ("R4 future skew", [(R, "if age < -MAX_FUTURE_SKEW_SECONDS:", "if False:")]),
    ("R5 spread", [(R, "elif quote.ask - quote.bid > auth.max_spread:", "elif False:")]),
    ("R6 BUY stop side", [(R, "if auth.direction == \"BUY\" and not auth.stop_loss_price < quote.bid:", "if False:")]),
    ("R7 SELL stop side", [(R, "if auth.direction == \"SELL\" and not auth.stop_loss_price > quote.ask:", "if False:")]),
    ("R8 max loss at stop", [(R, "if worst_case_loss(auth, quote) > auth.max_loss:", "if False:")]),
    ("R9 broker open trades", [(R, "if account.open_trade_count != 0 or broker_open_trades:", "if False:")]),
    ("R10 price bound direction", [(R, "        return quote.ask + auth.max_slippage", "        return quote.ask - auth.max_slippage")]),
    ("R11 invalid quote", [(R, "if not quote.bid > 0 or not quote.ask >= quote.bid:", "if False:")]),
    # journal
    ("J1 reserve: authorization used", [(J, "            if self.authorization_used(auth.authorization_id):\n                codes.append", "            if False:\n                codes.append")]),
    ("J2 reserve: open exposure", [(J, "            if self.has_open_exposure():\n", "            if False:\n")]),
    ("J3 reserve: halt", [(J, "            if self.active_halts():\n", "            if False:\n")]),
    ("J4 UNIQUE authorization", [(J, "authorization_id TEXT NOT NULL UNIQUE,", "authorization_id TEXT NOT NULL,")]),
    ("J5 append-only triggers", [(J, "        for table in _APPEND_ONLY:\n", "        for table in ():\n")]),
    ("J6 transition validation", [(J, "if to_state not in TRANSITIONS.get(row[\"state\"], ()):", "if False:")]),
    ("J7 FILLED counts as exposure", [(J, "OPEN_EXPOSURE_STATES = (SUBMITTING, UNCERTAIN, FILLED)", "OPEN_EXPOSURE_STATES = (SUBMITTING, UNCERTAIN)")]),
    ("J8 halt clearance needs who/why", [(J, "        if not by or not reason:\n", "        if False:\n")]),
    # executor
    ("E1 first kill check", [(E, "        if self.kill.engaged():\n            self._refuse(auth_id, [\"KILL_SWITCH_ENGAGED\"])", "        pass")]),
    ("E2 kill check before send", [(E, "        if self.kill.engaged():\n            self.journal.transition(auth.intent_id, jn.ABORTED_BEFORE_SEND", "        if False:\n            self.journal.transition(auth.intent_id, jn.ABORTED_BEFORE_SEND")]),
    ("E3 authorization validity", [(E, "            authz.check_current(auth, self.config, now)\n", "            pass\n")]),
    ("E4 unresolved intents gate", [(E, "        if self.journal.intents(jn.UNRESOLVED_STATES):\n", "        if False:\n")]),
    ("E5 read failure refuses", [(E, "        except BrokerReadFailed:\n            self._refuse(auth_id, [\"BROKER_READ_FAILED\"])", "        except ZeroDivisionError:\n            pass")]),
    ("E6 other account refuses", [(E, "        if account.account_id not in (None, self.config.account_id):", "        if False:")]),
    ("E7 dry run stops before reserve", [(E, "        if dry_run:\n", "        if False:\n")]),
    ("E8 mandatory stop check", [(E, "    if not stop.get(\"price\"):\n", "    if False:\n")]),
    ("E9 stop in the request", [(E, "        \"stopLossOnFill\": {\"price\": str(auth.stop_loss_price), \"timeInForce\": \"GTC\"},\n", "")]),
    ("E10 FOK", [(E, "\"timeInForce\": \"FOK\",", "\"timeInForce\": \"GTC\",")]),
    ("E11 write-ahead reserve", [(E, "            self.journal.reserve(auth, auth.signed_units, bound, account.last_transaction_id,\n                                 request_bytes, [account.raw, quote.raw])", "            pass")]),
    ("E12 unknown MOGO trade halts", [(E, "                self.journal.halt(reason)\n", "")]),
    ("E13 NotSent is ABORTED_BEFORE_SEND", [(E, "            self.journal.transition(auth.intent_id, jn.ABORTED_BEFORE_SEND, reason=\"NOT_SENT:\" + str(exc))", "            self.journal.transition(auth.intent_id, jn.UNCERTAIN, reason=\"x\")")]),
    ("E15 authorization reuse in submit gate", [(E, "        if self.journal.authorization_used(auth_id):\n", "        if False:\n")]),
    ("E14 state dir separation", [(E, "        if real == root or real.startswith(root + os.sep):", "        if False:")]),
    # adapter
    ("D1 fill needs the opened trade", [(D, "    if not isinstance(opened, dict) or not opened.get(\"tradeID\"):", "    if not isinstance(opened, dict):\n        return SubmitOutcome(FILLED, raw=raw)\n    if not opened.get(\"tradeID\"):")]),
    ("D2 fill units must match", [(D, "    if units != Decimal(expected_units):", "    if False:")]),
    ("D3 fill for another client id", [(D, "    if fill.get(\"clientOrderID\") not in (None, expected_client_id):", "    if False:")]),
    ("D4 5xx is not definitive", [(D, "DEFINITIVE_NO_ORDER_STATUSES = (400, 401, 403, 404, 405)", "DEFINITIVE_NO_ORDER_STATUSES = (400, 401, 403, 404, 405, 500)")]),
    ("D5 created-only is uncertain", [(D, "            return SubmitOutcome(UNCERTAIN, reason=\"CREATED_WITHOUT_FILL_OR_CANCEL\", raw=raw)", "            return SubmitOutcome(CANCELLED, reason=\"x\", raw=raw)")]),
    ("D6 absence needs both sources", [(D, "            if mine:\n", "            if False:\n")]),
    ("D7 resolved fill needs one fill txn", [(D, "            if len(fills) != 1:", "            if len(fills) > 1:")]),
    ("D8 order and fill agree on trade", [(D, "if outcome.kind == FILLED and outcome.trade_id != order.get(\"tradeOpenedID\"):", "if False:")]),
    ("D9 lookup returns our order", [(D, "        if (order.get(\"clientExtensions\") or {}).get(\"id\") != client_id:", "        if False:")]),
    ("D10 pending is not resolved", [(D, "        return SubmitOutcome(UNCERTAIN, reason=\"ORDER_STATE_%s\" % state, raw=raw)", "        return SubmitOutcome(\"ABSENT\", raw=raw)")]),
    ("D11 quote needs a time", [(D, "or when is None \\\n", "or False \\\n")]),
    # kill
    ("K1 missing state dir reads engaged", [(K, " or not os.path.isdir(os.path.dirname(self.path))", "")]),
    ("K2 release needs confirm", [(K, "        if confirm is not True:\n", "        if False:\n")]),
    # defence in depth, mutated together
    ("P1 open-exposure: risk + reserve", [(R, "    if journal_open_exposure:\n", "    if False:\n"), (J, "            if self.has_open_exposure():\n", "            if False:\n")]),
    ("P2 authorization reuse: submit gate + reserve + UNIQUE", [
        (E, "        if self.journal.authorization_used(auth_id):\n", "        if False:\n"),
        (J, "            if self.authorization_used(auth.authorization_id):\n                codes.append", "            if False:\n                codes.append"),
        (J, "authorization_id TEXT NOT NULL UNIQUE,", "authorization_id TEXT NOT NULL,")]),
    ("P3 halt: submit gate + reserve", [(E, "        if self.journal.active_halts():\n", "        if False:\n"), (J, "            if self.active_halts():\n", "            if False:\n")]),
]

#: Single layers of a defence-in-depth pair: expected to survive alone (their pair must die).
EXPECTED_SURVIVORS = {
    "S1 open-exposure in risk only": [(R, "    if journal_open_exposure:\n", "    if False:\n")],
    "S3 halt in submit gate only": [(E, "        if self.journal.active_halts():\n", "        if False:\n")],
}


def clear_pycache():
    for root in (PKG, HERE):
        for dp, dns, _ in os.walk(root):
            for d in list(dns):
                if d == "__pycache__":
                    shutil.rmtree(os.path.join(dp, d), ignore_errors=True)


def snapshot():
    return {f: hashlib.sha256(open(os.path.join(PKG, f), "rb").read()).hexdigest()
            for f in sorted(os.listdir(PKG)) if f.endswith(".py")}


def run_suite():
    clear_pycache()
    return subprocess.run([sys.executable, "-m", "unittest", SUITE], cwd=REPO,
                          capture_output=True, text=True).returncode


def apply_and_run(edits):
    originals = {}
    try:
        for fname, old, new in edits:
            path = os.path.join(PKG, fname)
            text = originals.get(fname) or open(path, encoding="utf-8").read()
            originals.setdefault(fname, text)
            current = open(path, encoding="utf-8").read()
            if current.count(old) != 1:
                return None
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(current.replace(old, new))
        return run_suite()
    finally:
        for fname, text in originals.items():
            with open(os.path.join(PKG, fname), "w", encoding="utf-8") as handle:
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
    unexpected_kills = []
    for name, edits in EXPECTED_SURVIVORS.items():
        rc = apply_and_run(edits)
        if rc is None:
            unapplied.append(name)
        print("%-9s %s (expected: the other layer catches it)" % ("survived" if rc == 0 else "killed", name))
    after = snapshot()
    restored = before == after
    print("RESULT: %d/%d killed, %d survived, %d unapplied; sources restored: %s"
          % (len(killed), len(MUTANTS), len(survived), len(unapplied), restored))
    ok = not survived and not unapplied and restored
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

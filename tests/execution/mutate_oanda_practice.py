#!/usr/bin/env python3
"""Mutation gate for the practice executor (M1 + M2): every guard, deleted, must turn the suites red.

Each mutant replaces one exact snippet (which must occur exactly once) in one
file of execution/oanda_practice/, clears __pycache__, runs
tests/execution/test_oanda_practice.py and test_oanda_practice_m2.py, and requires a non-zero exit. The file is
restored in a finally block, and the run ends by checking every source file's
bytes against the hashes taken before the first mutant.

The DEFENCE-IN-DEPTH pairs (a check made both in submit() and again inside the
journal's atomic reserve()) are mutated TOGETHER, and the paired mutants must
die. Their single layers are also run, as information only: one layer alone may
be caught by the other by design, so a single-layer survivor is not a failure.

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
SUITES = ["tests.execution.test_oanda_practice", "tests.execution.test_oanda_practice_m2"]

T, C, A, R, J, E, D, K, N = ("transport.py", "config.py", "authorization.py", "risk.py",
                             "journal.py", "executor.py", "adapter.py", "kill.py", "accounting.py")

MUTANTS = [
    # transport
    ("T1 host re-assert", [(T, "if parts.scheme != \"https\" or parts.hostname != cfg.PRACTICE_HOST or parts.port is not None:", "if False:")]),
    ("T2 operation allow-list", [(T, "if operation not in OPERATIONS:\n", "if False:\n")]),
    ("T3 parameter shapes", [(T, "if not isinstance(value, str) or not _PARAM_SHAPES[name].match(value):", "if not isinstance(value, str):")]),
    ("T4 caller cannot set account", [(T, "        if \"account\" in params:\n            raise TransportRefused(\"the account is fixed by configuration\")\n", "")]),
    ("T5 kill at send time", [(T, "if OPERATIONS[operation][3] and self._kill is not None and self._kill.engaged():", "if False:")]),
    ("T8 a close is not kill-gated", [(T, '"CLOSE_TRADE": ("PUT", "/v3/accounts/{account}/trades/{trade_id}/close", True, False),', '"CLOSE_TRADE": ("PUT", "/v3/accounts/{account}/trades/{trade_id}/close", True, True),')]),
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
    ("E11 write-ahead reserve", [(E, "            self.journal.reserve(auth, auth.signed_units, bound, account.last_transaction_id,\n                                 request_bytes, [account.raw, quote.raw], balance_before=account.balance)", "            pass")]),
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
    ("E16 SELL compares signed units (M1 fix)", [(E, "submit_market_order(body, auth.client_order_id, auth.signed_units)", "submit_market_order(body, auth.client_order_id, auth.units)")]),
    # ---- M2 ----
    # accounting
    ("N1 realized vs fill prices", [(N, "    if abs(realized - (exit_price - entry_price) * Decimal(signed_units)) > half_unit:", "    if False:")]),
    ("N2 tolerance is half a reported unit", [(N, "    half_unit = Decimal(1).scaleb(realized.as_tuple().exponent) / 2", "    half_unit = Decimal(1).scaleb(realized.as_tuple().exponent) * 5")]),
    ("N3 fill pl equals trade realizedPL", [(N, "    if _dec(close.get(\"pl\")) != realized:", "    if False:")]),
    ("N4 foreign balance activity", [(N, "        if not ours:\n            codes.append(\"FOREIGN_BALANCE_ACTIVITY_%s\"", "        if False:\n            codes.append(\"FOREIGN_BALANCE_ACTIVITY_%s\"")]),
    ("N5 unsupported transactions", [(N, "            if txn.get(\"type\") not in BALANCE_NEUTRAL_TYPES and not ours:", "            if False:")]),
    ("N6 balance continuity", [(N, "        if running != stated:", "        if False:")]),
    ("N7 summary balance", [(N, "    elif summary_balance != running:", "    elif False:")]),
    ("N8 summary and window aligned", [(N, "    if summary_last_id != window_last_id:", "    if False:")]),
    ("N9 exactly one entry fill", [(N, "    if len(entry) != 1:", "    if False:")]),
    ("N10 exactly one full close", [(N, "    if len(closes) != 1 or closing_entry(closes[0], trade_id)[0] != \"CLOSED\":", "    if len(closes) != 1:")]),
    ("N11 sign of commission", [(N, "            - parts.get(\"commission\", zero) - parts.get(\"guaranteedExecutionFee\", zero))", "            + parts.get(\"commission\", zero) - parts.get(\"guaranteedExecutionFee\", zero))")]),
    ("N12 a fill states every component", [(N, "    if txn.get(\"type\") == \"ORDER_FILL\" and not {\"pl\", \"financing\", \"commission\"} <= set(parts):", "    if False:")]),
    ("N13 net decomposes", [(N, "    if net != realized + financing - commission - fees:", "    if False:")]),
    # journal (positions)
    ("J9 positions never deleted", [(J, "        for table in (\"intents\", \"positions\"):", "        for table in (\"intents\",):")]),
    ("J10 broker transactions append-only", [(J, "_APPEND_ONLY = (\"events\", \"raw\", \"refusals\", \"halts\", \"broker_transactions\")", "_APPEND_ONLY = (\"events\", \"raw\", \"refusals\", \"halts\")")]),
    ("J11 position transition validation", [(J, "            if to_state not in POSITION_TRANSITIONS.get(row[\"state\"], ()):", "            if False:")]),
    ("J12 only RECONCILED releases exposure", [(J, "\"WHERE i.state IN (%s) AND (p.state IS NULL OR p.state != ?)\"", "\"WHERE i.state IN (%s) AND (p.state IS NULL OR p.state NOT IN (?, 'CLOSED'))\"")]),
    ("J13 rewritten transaction detected", [(J, "            elif row[0] != digest:", "            elif False:")]),
    ("J14 balance before recorded", [(J, "                 None if balance_before is None else str(balance_before)))", "                 None))")]),
    # adapter (positions)
    ("D12 contiguous history", [(D, "        if ids != expected:", "        if False:")]),
    ("D13 partial close is not a close", [(D, "    if kind == \"REDUCED\":", "    if False:")]),
    ("D14 close units must match", [(D, "    if units != -Decimal(expected_trade_units):", "    if False:")]),
    # executor (positions)
    ("X1 stop at the authorised price", [(E, "        if not stop or stop.get(\"state\") != \"PENDING\" or stop.get(\"price\") != want \\", "        if not stop or stop.get(\"state\") != \"PENDING\" \\")]),
    ("X2 stop must be PENDING", [(E, "        if not stop or stop.get(\"state\") != \"PENDING\" or stop.get(\"price\") != want \\", "        if not stop or stop.get(\"price\") != want \\")]),
    ("X3 stop corroborated by its transaction", [(E, "        return stop.get(\"id\") if len(created) == 1 else None", "        return stop.get(\"id\")")]),
    ("X4 units unchanged", [(E, "            if trade.current_units != Decimal(pos[\"signed_units\"]):", "            if False:")]),
    ("X5 trade missing at broker", [(E, "        if trade is None:\n            return self._halt", "        if False:\n            return self._halt")]),
    ("X6 closed needs close evidence", [(E, "        if not closes:\n", "        if False:\n")]),
    ("X7 accounting gates RECONCILED", [(E, "        if not result.ok:\n", "        if False:\n")]),
    ("X8 close is write-ahead", [(E, "        self.journal.transition_position(intent_id, jn.CLOSING, reason=\"CLOSE_REQUESTED\", raw=request,", "        (lambda *a, **k: None)(intent_id, jn.CLOSING, reason=\"CLOSE_REQUESTED\", raw=request,")]),
    ("X9 open trade + close fill halts", [(E, "                if any(closing_entry(t, pos[\"trade_id\"])[0] for t in txns if t.get(\"type\") == \"ORDER_FILL\"):", "                if False:")]),
    ("X10 rewritten transaction halts", [(E, "        if rewritten:\n", "        if False:\n")]),
    ("X11 only an open position closes", [(E, "        if pos is None or pos[\"state\"] not in jn.POSITION_OPEN_STATES:", "        if pos is None:")]),
    ("X13 multiple close fills halt", [(E, "        if len(closes) != 1:\n            return self._halt(report, \"MULTIPLE_CLOSE_FILLS", "        if False:\n            return self._halt(report, \"MULTIPLE_CLOSE_FILLS")]),
    ("X12 unprotected position halts", [(E, "            if stop_id is None:\n                return self._halt", "            if False:\n                return self._halt")]),
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

#: Single layers of a defence-in-depth pair: informational (their pair must die).
SINGLE_LAYERS = {
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
    return subprocess.run([sys.executable, "-m", "unittest"] + SUITES, cwd=REPO,
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
    for name, edits in SINGLE_LAYERS.items():
        rc = apply_and_run(edits)
        if rc is None:
            unapplied.append(name)
        print("%-9s %s (single layer, informational)" % ("survived" if rc == 0 else "killed", name))
    after = snapshot()
    restored = before == after
    print("RESULT: %d/%d killed, %d survived, %d unapplied; sources restored: %s"
          % (len(killed), len(MUTANTS), len(survived), len(unapplied), restored))
    ok = not survived and not unapplied and restored
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

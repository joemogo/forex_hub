#!/usr/bin/env python3
"""M2 offline: fills, protection, closing, fill-derived accounting, restart-safe reconcile.

Same zero-network discipline as the M1 suite: this module reuses its socket
patches and audit hook, and every test asserts no attempt was made.

The properties under test:
  * EXIT AND P&L COME FROM BROKER FILLS. A gapped stop exits at the fill price,
    not at the authorised stop. accounting.reconcile_trade() cannot take a stop,
    a target or a quote at all (its signature is asserted).
  * THREE VIEWS MUST AGREE: the fills, the transaction stream walked balance by
    balance, and the account summary. Any disagreement halts and keeps the
    exposure open; nothing is booked on a partial match.
  * PROTECTION IS VERIFIED AT THE BROKER: a stop at exactly the authorised
    price, PENDING, with the transaction that created it. Otherwise it halts.
  * CLOSING IS WRITE-AHEAD AND NEVER RETRIED. An unknown close is resolved from
    the trade's state and the transaction stream.
  * RECONCILE IS IDEMPOTENT and restart-safe: a second pass changes nothing.
"""
import copy
import datetime
import inspect
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "execution"))
sys.path.insert(0, HERE)

import test_oanda_practice as m1                 # noqa: E402  (fixtures and the network guard)
import demo_offline_lifecycle as demo            # noqa: E402
from oanda_practice import accounting            # noqa: E402
from oanda_practice import executor as ex        # noqa: E402
from oanda_practice import journal as jn         # noqa: E402
from oanda_practice.errors import OrderRefused   # noqa: E402

setUpModule = m1.setUpModule
tearDownModule = m1.tearDownModule
make_auth = m1.make_auth


class Base(m1.Harness):
    def open_protected(self, **over):
        auth = make_auth(**over)
        self.assertEqual(self.ex.submit(auth)["state"], jn.FILLED)
        self.ex.reconcile()
        return auth

    def pos(self, auth):
        return self.ex.journal.position(auth.intent_id)

    def halts(self):
        return [h["reason"] for h in self.ex.journal.active_halts()]


# ---- the demonstration ----------------------------------------------------------------
class TestTheCompleteLifecycle(Base):
    def test_DEMO_intent_ack_fill_protected_close_reconciled_and_deterministic(self):
        runs = []
        for _ in range(2):
            state_dir = tempfile.mkdtemp(prefix="mogo_demo_")
            try:
                runs.append(json.dumps(demo.run(state_dir), sort_keys=True))
            finally:
                shutil.rmtree(state_dir, ignore_errors=True)
        self.assertEqual(runs[0], runs[1], "the offline lifecycle is not deterministic")
        steps = {s["step"]: s for s in json.loads(runs[0])}
        self.assertEqual(steps["2-3 broker ack + entry fill"]["intent"], "FILLED")
        self.assertEqual(steps["4 protected position"]["position"], "PROTECTED")
        final = steps["6 P&L reconciliation"]
        self.assertEqual(final["position"], "RECONCILED")
        # realized (1.10250 - 1.10010) x 1000 = 2.40; financing -0.01 close, -0.02 daily; commission 0.05
        self.assertEqual((final["realizedPl"], final["financing"], final["commission"], final["netPl"]),
                         ("2.4000", "-0.0300", "0.0500", "2.3200"))
        self.assertEqual(final["balanceAfter"], final["brokerBalance"])
        self.assertEqual([e[1] for e in steps["journal events"]["events"]],
                         ["SUBMITTING", "FILLED", "OPEN_UNVERIFIED", "PROTECTED", "CLOSING", "CLOSED",
                          "RECONCILED"])

    def test_a_reconciled_trade_releases_the_exposure_and_only_then(self):
        auth = self.open_protected()
        second = make_auth(authorizationId="AUTH-20261103-0002")
        self.assertRefused("JOURNAL_HAS_OPEN_OR_UNRESOLVED_INTENT", self.ex.submit, second)
        self.ex.close_position(auth.intent_id, m1.make_close_auth(self.ex, auth))
        self.assertRefused("JOURNAL_HAS_OPEN_OR_UNRESOLVED_INTENT", self.ex.submit, second)   # CLOSED, not reconciled
        self.ex.reconcile()
        self.assertEqual(self.pos(auth)["state"], jn.RECONCILED)
        self.assertEqual(self.ex.submit(second)["state"], jn.FILLED)

    def test_a_SELL_fills_protects_closes_and_reconciles(self):
        # The M1 defect fixed in M2: a SELL fill (negative units) used to read as a units mismatch.
        auth = self.open_protected(direction="SELL", stopLossPrice="1.10200")
        self.assertEqual(self.ex.journal.intent(auth.intent_id)["fill_units"], "-1000")
        self.assertEqual(self.pos(auth)["state"], jn.PROTECTED)
        self.fake.prices["EUR_USD"].update(bid="1.09900", ask="1.09910")
        self.ex.close_position(auth.intent_id, m1.make_close_auth(self.ex, auth))
        self.ex.reconcile()
        p = self.pos(auth)
        self.assertEqual((p["state"], p["exit_price"], p["net_pl"]), (jn.RECONCILED, "1.09910", "0.9000"))


# ---- exits come from fills ---------------------------------------------------------------
class TestExitsComeFromFills(Base):
    def test_a_stop_hit_at_the_broker_is_booked_at_its_fill(self):
        auth = self.open_protected()
        self.fake.trigger_stop(self.pos(auth)["trade_id"])
        self.ex.reconcile()
        p = self.pos(auth)
        self.assertEqual((p["state"], p["close_reason"], p["exit_price"], p["net_pl"]),
                         (jn.RECONCILED, "STOP_LOSS_ORDER", "1.09800", "-2.1000"))

    def test_a_GAPPED_stop_exits_at_the_fill_not_at_the_authorised_stop(self):
        auth = self.open_protected()
        self.fake.trigger_stop(self.pos(auth)["trade_id"], gap=Decimal("0.00050"))
        self.ex.reconcile()
        p = self.pos(auth)
        self.assertEqual(p["exit_price"], "1.09750")
        self.assertNotEqual(p["exit_price"], p["stop_loss_price"])
        self.assertEqual(p["net_pl"], "-2.6000")          # beyond the -2.10 the stop alone implies

    def test_accounting_cannot_be_given_a_planned_price(self):
        params = set(inspect.signature(accounting.reconcile_trade).parameters)
        self.assertEqual(params, {"trade_id", "signed_units", "balance_before", "window_txns",
                                  "summary_balance", "summary_last_id", "window_last_id"})
        source = inspect.getsource(accounting)
        for planned in ("stop_loss_price", "stopLossPrice", "target", "quote", "LIVE_PAPER", "alexG"):
            self.assertNotIn(planned, source.split('"""', 2)[2])     # code, excluding the module docstring

    def test_reported_precision_is_honoured_and_nothing_wider(self):
        # 1 unit: realized -0.00007 is reported as -0.0001 (4 dp); that is within half a reported unit.
        auth = self.open_protected(units=1, maxLoss="1")
        self.fake.prices["EUR_USD"].update(bid="1.10003", ask="1.10013")
        self.ex.close_position(auth.intent_id, m1.make_close_auth(self.ex, auth))
        self.ex.reconcile()
        self.assertEqual(self.pos(auth)["state"], jn.RECONCILED)                # positive control
        window = self.fake.transactions
        closing = [t for t in window if t.get("reason") == "MARKET_ORDER_TRADE_CLOSE"][0]
        bad = copy.deepcopy(window)
        for t in bad:
            if t["id"] == closing["id"]:
                t["tradesClosed"][0]["realizedPL"] = "-0.0002"   # one reported unit off
                t["pl"] = "-0.0002"
        result = accounting.reconcile_trade(self.pos(auth)["trade_id"], 1, Decimal("1000.0000"),
                                            [t for t in bad if int(t["id"]) > 100], Decimal("999.9999"),
                                            str(self.fake.next_id), str(self.fake.next_id))
        self.assertIn("REALIZED_PL_INCONSISTENT_WITH_FILL_PRICES", result.codes)


# ---- accounting fails closed ------------------------------------------------------------
class TestAccountingFailsClosed(Base):
    def close_and_reconcile(self, prepare):
        auth = self.open_protected()
        prepare(auth)
        self.ex.close_position(auth.intent_id, m1.make_close_auth(self.ex, auth))
        report = self.ex.reconcile()
        return auth, report

    def assertHaltedAndBlocking(self, auth, needle):
        self.assertTrue(any(needle in h for h in self.halts()), self.halts())
        self.assertNotEqual(self.pos(auth)["state"], jn.RECONCILED)
        self.assertRefused("HALT_ACTIVE", self.ex.submit, make_auth(authorizationId="AUTH-20261103-0007"))

    def test_POSITIVE_CONTROL_the_untampered_trade_reconciles(self):
        auth, report = self.close_and_reconcile(lambda a: None)
        self.assertEqual((self.pos(auth)["state"], report["halted"]), (jn.RECONCILED, []))

    def test_a_broker_balance_that_does_not_follow_from_its_transactions_halts(self):
        def lie(_auth):
            self.fake.balance_report_skew = Decimal("0.0100")
        auth, _ = self.close_and_reconcile(lie)
        self.assertHaltedAndBlocking(auth, "BALANCE_DISCONTINUITY")

    def test_a_summary_balance_that_disagrees_with_the_stream_halts(self):
        def skew(_auth):
            self.fake.summary_balance_skew = Decimal("-0.0100")
        auth, _ = self.close_and_reconcile(skew)
        self.assertHaltedAndBlocking(auth, "BALANCE_MISMATCH_WITH_ACCOUNT_SUMMARY")

    def test_foreign_balance_activity_in_the_window_halts(self):
        auth, _ = self.close_and_reconcile(lambda a: self.fake.transfer("50"))
        self.assertHaltedAndBlocking(auth, "FOREIGN_BALANCE_ACTIVITY_TRANSFER_FUNDS")

    def test_an_unsupported_transaction_in_the_window_halts(self):
        def mystery(_auth):
            self.fake.transactions.append({"id": self.fake._id(), "type": "MYSTERY_EVENT"})
        auth, _ = self.close_and_reconcile(mystery)
        self.assertHaltedAndBlocking(auth, "UNSUPPORTED_TRANSACTION_MYSTERY_EVENT")

    def test_a_gap_in_the_transaction_history_moves_nothing(self):
        auth = self.open_protected()
        self.ex.close_position(auth.intent_id, m1.make_close_auth(self.ex, auth))
        fin = self.fake.daily_financing("-0.0100")
        self.fake.hide_transaction_ids = {fin["id"]}
        report = self.ex.reconcile()
        self.assertEqual(self.pos(auth)["state"], jn.CLOSED)
        self.assertTrue(any("INCOMPLETE_TRANSACTION_HISTORY" in u["reason"] for u in report["unresolved"]))
        self.fake.hide_transaction_ids = set()
        self.ex.reconcile()
        self.assertEqual((self.pos(auth)["state"], self.pos(auth)["net_pl"]), (jn.RECONCILED, "-0.1100"))   # (1.10000 - 1.10010) x 1000 - 0.01
        self.assertEqual(Decimal(self.pos(auth)["balance_after"]), self.fake.balance)

    def test_a_rewritten_broker_transaction_halts(self):
        auth = self.open_protected()
        fill = [t for t in self.fake.transactions if t["type"] == "ORDER_FILL"][0]
        fill["price"] = "1.10011"
        self.ex.reconcile()
        self.assertTrue(any(h.startswith("TRANSACTION_REWRITTEN") for h in self.halts()))

    def test_a_missing_entry_balance_halts_rather_than_guessing(self):
        auth = make_auth()
        self.ex.journal.reserve(auth, 1000, "1.10020", "100", b"{}", [])        # no balance_before
        self.fake.submit_behavior = "fill"
        body = ex.build_order_body(auth, Decimal("1.10020"))
        outcome = self.ex.adapter.submit_market_order(body, auth.client_order_id, auth.signed_units)
        self.ex._apply(auth.intent_id, outcome)
        self.ex.reconcile()
        self.ex.close_position(auth.intent_id, m1.make_close_auth(self.ex, auth))
        self.ex.reconcile()
        self.assertTrue(any("MISSING_BALANCE_BEFORE_ENTRY" in h for h in self.halts()))
        self.assertEqual(self.pos(auth)["state"], jn.CLOSED)

    def test_accounting_codes_in_isolation(self):
        tid = "102"
        entry = {"id": "102", "type": "ORDER_FILL", "pl": "0.0000", "financing": "0.0000",
                 "commission": "0.0000", "accountBalance": "1000.0000",
                 "tradeOpened": {"tradeID": tid, "units": "1000", "price": "1.10010"}}
        close = {"id": "104", "type": "ORDER_FILL", "pl": "2.4000", "financing": "0.0000",
                 "commission": "0.0000", "accountBalance": "1002.4000",
                 "tradesClosed": [{"tradeID": tid, "units": "-1000", "price": "1.10250",
                                   "realizedPL": "2.4000", "financing": "0.0000"}]}
        stop = {"id": "103", "type": "STOP_LOSS_ORDER", "tradeID": tid, "price": "1.09800"}

        def run(txns, balance="1002.4000", before=Decimal("1000.0000")):
            return accounting.reconcile_trade(tid, 1000, before, txns, Decimal(balance), "104", "104").codes

        self.assertEqual(run([entry, stop, close]), [])                                # positive control
        self.assertIn("ENTRY_FILL_NOT_EXACTLY_ONE", run([stop, close]))
        self.assertIn("CLOSE_FILL_NOT_EXACTLY_ONE_FULL_CLOSE", run([entry, stop]))
        reduced = dict(close, tradesClosed=None, tradeReduced=close["tradesClosed"][0])
        self.assertIn("CLOSE_FILL_NOT_EXACTLY_ONE_FULL_CLOSE", run([entry, stop, reduced]))
        self.assertIn("FILL_PL_DISAGREES_WITH_TRADE_REALIZED_PL", run([entry, stop, dict(close, pl="2.3000",
                                                                                          accountBalance="1002.3000")],
                                                                       balance="1002.3000"))
        no_commission = {k: v for k, v in close.items() if k != "commission"}
        self.assertIn("BALANCE_FIELDS_MISSING_ON_104", run([entry, stop, no_commission]))
        self.assertIn("MISSING_BALANCE_BEFORE_ENTRY", run([entry, stop, close], before=None))
        # An entry fill with its own P&L: every balance agrees, but net no longer decomposes.
        odd_entry = dict(entry, pl="0.0100", accountBalance="1000.0100")
        self.assertEqual(run([odd_entry, stop, dict(close, accountBalance="1002.4100")], balance="1002.4100"),
                         ["NET_PL_DOES_NOT_DECOMPOSE"])
        self.assertIn("SUMMARY_AND_WINDOW_AT_DIFFERENT_TRANSACTIONS",
                      accounting.reconcile_trade(tid, 1000, Decimal("1000"), [entry, stop, close],
                                                 Decimal("1002.4000"), "105", "104").codes)


# ---- protection --------------------------------------------------------------------------
class TestProtectionIsVerifiedAtTheBroker(Base):
    def test_a_missing_or_wrong_stop_halts_and_the_position_stays_unverified(self):
        for behavior in ("missing", "wrong_price"):
            with self.subTest(stop=behavior):
                self.tearDown()
                self.setUp()
                self.fake.stop_behavior = behavior
                auth = make_auth()
                self.ex.submit(auth)
                self.ex.reconcile()
                self.assertEqual(self.pos(auth)["state"], jn.OPEN_UNVERIFIED)
                self.assertTrue(any(h.startswith("UNPROTECTED_POSITION") for h in self.halts()))

    def test_a_stop_the_transaction_stream_does_not_corroborate_halts(self):
        self.fake.stop_behavior = "attach"
        auth = make_auth()
        self.ex.submit(auth)
        stop_txn = [t for t in self.fake.transactions if t["type"] == "STOP_LOSS_ORDER"][0]
        stop_txn["price"] = "1.09700"            # the order book says 1.09800; its creation says otherwise
        self.ex.reconcile()
        self.assertEqual(self.pos(auth)["state"], jn.OPEN_UNVERIFIED)
        self.assertTrue(any(h.startswith("UNPROTECTED_POSITION") for h in self.halts()))

    def test_a_stop_moved_at_the_broker_after_protection_halts(self):
        auth = self.open_protected()
        self.fake.trades[0]["stopLossOrder"]["price"] = "1.09500"   # its creation record still says 1.09800
        self.ex.reconcile()
        self.assertTrue(any(h.startswith("UNPROTECTED_POSITION") for h in self.halts()))

    def test_a_stop_that_disappears_after_protection_halts(self):
        auth = self.open_protected()
        self.fake.trades[0]["stopLossOrder"]["state"] = "CANCELLED"
        self.ex.reconcile()
        self.assertTrue(any(h.startswith("UNPROTECTED_POSITION") for h in self.halts()))

    def test_units_changed_at_the_broker_halts(self):
        auth = self.open_protected()
        self.fake.trades[0]["currentUnits"] = "600"
        self.ex.reconcile()
        self.assertTrue(any(h.startswith("UNITS_CHANGED") for h in self.halts()))

    def test_a_trade_the_broker_does_not_know_halts(self):
        auth = self.open_protected()
        self.fake.trades.clear()
        self.ex.reconcile()
        self.assertTrue(any(h.startswith("TRADE_MISSING_AT_BROKER") for h in self.halts()))

    def test_two_close_fills_for_one_trade_halt_and_book_nothing(self):
        auth = self.open_protected()
        tid = self.pos(auth)["trade_id"]
        self.fake.trigger_stop(tid)
        first = [t for t in self.fake.transactions if t.get("reason") == "STOP_LOSS_ORDER"][0]
        second = dict(first, id=self.fake._id(), accountBalance=first["accountBalance"],
                      pl="0.0000", financing="0.0000", commission="0.0000")
        self.fake.transactions.append(second)        # a second fill claiming to close the same trade
        self.ex.reconcile()
        self.assertTrue(any(h.startswith("MULTIPLE_CLOSE_FILLS %s" % tid) for h in self.halts()))
        self.assertEqual(self.pos(auth)["state"], jn.PROTECTED)          # nothing booked
        self.assertRefused("HALT_ACTIVE", self.ex.submit, make_auth(authorizationId="AUTH-20261104-0001"))

    def test_a_closed_trade_without_close_evidence_halts(self):
        auth = self.open_protected()
        trade = self.fake.trades.pop()
        trade["state"] = "CLOSED"
        self.fake.closed_trades.append(trade)
        self.ex.reconcile()
        self.assertTrue(any(h.startswith("MISSING_CLOSE_EVIDENCE") for h in self.halts()))


# ---- closing -----------------------------------------------------------------------------
class TestClosingIsWriteAheadAndNeverRetried(Base):
    def test_the_close_is_journaled_before_it_is_sent(self):
        auth = self.open_protected()
        seen = []
        self.fake.on_request = lambda m, path: seen.append((m, self.pos(auth)["state"])) if m == "PUT" else None
        self.ex.close_position(auth.intent_id, m1.make_close_auth(self.ex, auth))
        self.assertEqual(seen, [("PUT", jn.CLOSING)])

    def test_a_close_fill_for_the_wrong_units_is_not_a_close(self):
        from oanda_practice.adapter import classify_close_fill
        fill = {"type": "ORDER_FILL", "reason": "MARKET_ORDER_TRADE_CLOSE",
                "tradesClosed": [{"tradeID": "102", "units": "-1000", "price": "1.1", "realizedPL": "0"}]}
        self.assertEqual(classify_close_fill(fill, "102", 1000, None).kind, "CLOSED")   # positive control
        fill["tradesClosed"][0]["units"] = "-500"
        out = classify_close_fill(fill, "102", 1000, None)
        self.assertEqual((out.kind, out.reason), ("UNCERTAIN", "CLOSE_UNITS_MISMATCH"))
        self.assertEqual(classify_close_fill(fill, "999", 1000, None).reason, "CLOSE_FILL_DOES_NOT_NAME_OUR_TRADE")

    def test_a_refused_or_cancelled_close_returns_to_protected(self):
        for behavior, reason in (("reject", "CLOSE_REFUSED:NO_SUCH_TRADE"), ("cancel", "CLOSE_REFUSED:MARKET_HALTED")):
            with self.subTest(close=behavior):
                self.tearDown()
                self.setUp()
                auth = self.open_protected()
                self.fake.close_behavior = behavior
                p = self.ex.close_position(auth.intent_id, m1.make_close_auth(self.ex, auth))
                self.assertEqual((p["state"], p["reason"], self.fake.close_puts), (jn.PROTECTED, reason, 1))

    def test_a_close_committed_then_lost_resolves_from_the_broker_without_a_second_close(self):
        for behavior in ("timeout_after_commit", "http500_after_commit"):
            with self.subTest(close=behavior):
                self.tearDown()
                self.setUp()
                auth = self.open_protected()
                self.fake.close_behavior = behavior
                self.assertEqual(self.ex.close_position(auth.intent_id, m1.make_close_auth(self.ex, auth))["state"], jn.CLOSE_UNCERTAIN)
                self.ex.close()
                self.ex = self.new_executor()                                  # and a restart
                self.ex.reconcile()
                self.assertEqual(self.pos(auth)["state"], jn.RECONCILED)
                self.assertEqual(self.fake.close_puts, 1)

    def test_a_close_that_never_reached_the_broker_re_verifies_protection(self):
        auth = self.open_protected()
        self.fake.close_behavior = "timeout_before_commit"
        self.assertEqual(self.ex.close_position(auth.intent_id, m1.make_close_auth(self.ex, auth))["state"], jn.CLOSE_UNCERTAIN)
        self.ex.reconcile()
        p = self.pos(auth)
        self.assertEqual((p["state"], self.fake.close_puts), (jn.PROTECTED, 1))
        self.assertIn(("OPEN_UNVERIFIED", "PROTECTED"),
                      [(e["from_state"], e["to_state"]) for e in self.ex.journal.events(auth.intent_id)][-1:])

    def test_a_partial_close_is_not_a_close(self):
        auth = self.open_protected()
        self.fake.close_behavior = "partial"
        p = self.ex.close_position(auth.intent_id, m1.make_close_auth(self.ex, auth))
        self.assertEqual((p["state"], p["reason"]), (jn.CLOSE_UNCERTAIN, "PARTIAL_CLOSE"))
        self.ex.reconcile()
        # The trade is still open, yet a fill reduced it: neither "closed" nor "not executed".
        self.assertTrue(any(h.startswith("TRADE_OPEN_BUT_CLOSE_FILL_PRESENT") for h in self.halts()))
        self.assertEqual(self.pos(auth)["state"], jn.CLOSE_UNCERTAIN)
        self.assertRefused("HALT_ACTIVE", self.ex.submit, make_auth(authorizationId="AUTH-20261103-0006"))

    def test_a_crash_between_the_close_record_and_the_send_never_sends(self):
        auth = self.open_protected()
        self.ex.journal.transition_position(auth.intent_id, jn.CLOSING, reason="CLOSE_REQUESTED",
                                            consume_close=m1.make_close_auth(self.ex, auth))  # then crash
        self.ex.close()
        self.ex = self.new_executor()
        self.ex.reconcile()
        self.assertEqual((self.pos(auth)["state"], self.fake.close_puts), (jn.PROTECTED, 0))

    def test_closing_is_allowed_under_the_kill_switch_and_opening_is_not(self):
        auth = self.open_protected()
        self.ex.kill.engage("flatten")
        self.assertRefused("KILL_SWITCH_ENGAGED", self.ex.submit, make_auth(authorizationId="AUTH-20261103-0008"))
        self.assertEqual(self.ex.close_position(auth.intent_id, m1.make_close_auth(self.ex, auth))["state"], jn.CLOSED)

    def test_only_an_open_position_can_be_closed(self):
        auth = self.open_protected()
        self.ex.close_position(auth.intent_id, m1.make_close_auth(self.ex, auth))
        with self.assertRaises(OrderRefused) as ctx:
            self.ex.close_position(auth.intent_id, m1.make_close_auth(self.ex, auth))
        self.assertEqual(ctx.exception.codes, ["POSITION_NOT_OPEN"])
        self.assertEqual(self.fake.close_puts, 1)


# ---- restart and idempotency ---------------------------------------------------------------
class TestReconcileIsIdempotentAndRestartSafe(Base):
    def test_a_second_reconcile_changes_nothing(self):
        auth = self.open_protected()
        self.ex.close_position(auth.intent_id, m1.make_close_auth(self.ex, auth))
        self.ex.reconcile()
        db = self.ex.journal._db
        snapshot = lambda: [db.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
                            for t in ("events", "broker_transactions", "halts", "positions")]
        before = snapshot()
        self.ex.reconcile()
        self.ex.close()
        self.ex = self.new_executor()
        self.ex.reconcile()
        db = self.ex.journal._db
        self.assertEqual(snapshot(), before)

    def test_an_entry_lost_on_timeout_becomes_exactly_one_position_after_restart(self):
        self.fake.submit_behavior = "timeout_after_commit"
        auth = make_auth()
        self.ex.submit(auth)
        self.ex.close()
        self.ex = self.new_executor()
        self.ex.reconcile()
        self.ex.reconcile()
        self.assertEqual((self.fake.posts, len(self.ex.journal.positions())), (1, 1))
        self.assertEqual(self.pos(auth)["state"], jn.PROTECTED)

    def test_an_M1_journal_opened_by_M2_gains_its_position(self):
        auth = make_auth()
        self.ex.submit(auth)
        self.ex.journal._db.execute("PRAGMA foreign_keys=OFF")
        # Simulate an M1-era journal: FILLED entry, no position row (drop the trigger guard first).
        self.ex.journal._db.execute("DROP TRIGGER positions_no_delete")
        self.ex.journal._db.execute("DELETE FROM positions")
        self.ex.close()
        self.ex = self.new_executor()
        self.ex.reconcile()
        self.assertEqual(self.pos(auth)["state"], jn.PROTECTED)

    def test_position_history_is_append_only_and_transitions_are_validated(self):
        auth = self.open_protected()
        self.ex.close_position(auth.intent_id, m1.make_close_auth(self.ex, auth))
        self.ex.reconcile()
        db = self.ex.journal._db
        for sql in ("DELETE FROM positions", "DELETE FROM broker_transactions",
                    "UPDATE broker_transactions SET type='x'"):
            with self.subTest(sql=sql), self.assertRaises(sqlite3.DatabaseError):
                db.execute(sql)
        with self.assertRaises(ValueError):
            self.ex.journal.transition_position(auth.intent_id, jn.CLOSED)
        with self.assertRaises(ValueError):
            self.ex.journal.transition_position(auth.intent_id, jn.RECONCILED, bogus=1)


if __name__ == "__main__":
    unittest.main()

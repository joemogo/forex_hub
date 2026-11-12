#!/usr/bin/env python3
"""M4 offline: the first practice trade's write path, A3-gated, through the operator's commands.

ZERO NETWORK: the M1 socket patches and audit hook are reused, and every test
asserts no attempt was made. Where a refusal must be shown to precede any socket,
the REAL http.client stack is used (no fake connection): a refused request that
slipped through would be recorded by the guard. The positive control shows a
granted write through the same real stack does reach the socket layer.

Everything else runs execution/mogo_practice_trade.py's run() against
fake_oanda.FakeOanda behind fake_oanda.FakeHttpsConnection, so the A3 opener, its
grants and the read-only opener's checks execute for real.
"""
import contextlib
import datetime
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "execution"))
sys.path.insert(0, HERE)

import test_oanda_practice as m1                  # noqa: E402  (fixtures and the network guard)
import demo_m4_practice_trade as demo             # noqa: E402
import mogo_practice_trade as trade_cli           # noqa: E402
from oanda_practice import accounting             # noqa: E402
from oanda_practice import adapter as ad          # noqa: E402
from oanda_practice import authorization as authz  # noqa: E402
from oanda_practice import config as cfg          # noqa: E402
from oanda_practice import executor as ex         # noqa: E402
from oanda_practice import journal as jn          # noqa: E402
from oanda_practice import risk                   # noqa: E402
from oanda_practice import transport as tp        # noqa: E402
from oanda_practice.errors import AuthorizationRefused, NotSent, SendUncertain  # noqa: E402
from oanda_practice.kill import KillSwitch        # noqa: E402
from oanda_practice_m3.readonly import READ_OPERATIONS, ReadOnlyHttpsOpener  # noqa: E402
from oanda_practice_m4 import a3                  # noqa: E402
from fake_oanda import FakeOanda, https_factory   # noqa: E402

setUpModule = m1.setUpModule
tearDownModule = m1.tearDownModule

ACCOUNT = demo.ACCOUNT
NOW = demo.NOW
BASE = "https://" + cfg.PRACTICE_HOST + "/v3/accounts/%s/" % ACCOUNT
with open(os.path.join(HERE, "fixtures", "oanda_v20_documented_shapes.json"), encoding="utf-8") as _h:
    V20 = json.load(_h)


def order_auth(**over):
    return authz.parse_authorization(json.dumps(dict(demo.ORDER_AUTHORIZATION, **over)).encode())


class Base(unittest.TestCase):
    def setUp(self):
        self.net_before = len(m1.NET_ATTEMPTS)
        self.work = tempfile.mkdtemp(prefix="mogo_m4_")
        self.state = os.path.join(self.work, "state")
        os.makedirs(self.state)
        self.broker = FakeOanda(ACCOUNT)
        self.opened = []

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)
        self.assertEqual(m1.NET_ATTEMPTS[self.net_before:], [], "a test attempted network access")

    def order_file(self, **over):
        return demo.write_json(os.path.join(self.work, "order-%d.json" % len(os.listdir(self.work))),
                               dict(demo.ORDER_AUTHORIZATION, **over))

    def close_file(self, pos=None, **over):
        pos = pos or self.position()
        data = dict(demo.CLOSE_AUTHORIZATION, clientOrderId=pos["clientOrderId"], tradeId=pos["trade_id"],
                    closeAuthorizationId="CLOSE-M4-TEST-%04d" % len(os.listdir(self.work)))
        data.update(over)
        return demo.write_json(os.path.join(self.work, "close-%d.json" % len(os.listdir(self.work))), data)

    def cmd(self, *argv, clock=lambda: NOW):
        return demo.command(self.broker, list(argv) + ["--state-dir", self.state], self.opened, clock)

    def submit(self, order=None):
        return self.cmd("submit", "--order-authorization", order or self.order_file(), "--authorization", "A3")

    def close(self, close_file):
        return self.cmd("close", "--close-authorization", close_file)

    def position(self):
        code, out = self.cmd("reconcile")
        journal = jn.Journal(os.path.join(self.state, "journal.sqlite3"))
        try:
            rows = journal.positions()
            intent = journal.intent(rows[-1]["intent_id"]) if rows else None
            return {"clientOrderId": intent["client_order_id"] if intent else None,
                    "trade_id": rows[-1]["trade_id"] if rows else None,
                    "state": rows[-1]["state"] if rows else None}
        finally:
            journal.close()

    def writes(self):
        return [(r[0], r[1]) for c in self.opened for r in c.requests if r[0] != "GET"]


# ---- acceptance: the deterministic lifecycle ------------------------------------------------
class TestTheFirstTradeLifecycle(Base):
    def test_DEMO_dryrun_submit_fill_stop_close_reconcile_and_deterministic(self):
        runs = []
        for _ in range(2):
            work = tempfile.mkdtemp(prefix="mogo_m4_demo_")
            try:
                runs.append(json.dumps(demo.run(work)[0], sort_keys=True, default=str))
            finally:
                shutil.rmtree(work, ignore_errors=True)
        self.assertEqual(runs[0], runs[1], "the M4 lifecycle is not deterministic")
        steps = {s["step"][:1]: s for s in json.loads(runs[0])}
        self.assertEqual((steps["1"]["exit"], steps["1"]["posts"]), (0, 0))
        self.assertEqual((steps["2"]["exit"], steps["2"]["intent"], steps["2"]["position"], steps["2"]["posts"]),
                         (0, "FILLED", "PROTECTED", 1))
        final = steps["3"]
        self.assertEqual((final["exit"], final["position"], final["closePuts"], final["halts"]),
                         (0, "RECONCILED", 1, []))
        # fill-based: (1.10250 - 1.10010) x 1 unit = 0.0024, and the broker's balance agrees
        self.assertEqual((final["entryPrice"], final["exitPrice"], final["realizedPl"]),
                         ("1.10010", "1.10250", "0.0024"))
        self.assertEqual(final["balanceAfter"], final["brokerBalance"])
        wire = steps["w"]
        self.assertEqual(wire["writes"], [["POST", "orders"], ["PUT", "close"]])
        self.assertEqual(wire["hosts"], [cfg.PRACTICE_HOST])

    def test_dry_run_sends_no_write_and_records_no_intent(self):
        code, out = self.cmd("dry-run", "--order-authorization", self.order_file())
        self.assertEqual((code, self.writes(), self.broker.posts), (0, [], 0))
        self.assertEqual(out["request"]["order"]["stopLossOnFill"]["price"], "1.09800")
        self.assertLessEqual(Decimal(out["worstCaseLoss"]), Decimal("5"))
        self.assertEqual(self.position()["state"], None)


# ---- without A3, nothing writes -------------------------------------------------------------
class TestWithoutA3NothingWrites(Base):
    def test_submit_without_A3_refuses_before_reading_credentials(self):
        original = cfg.load_config
        cfg.load_config = lambda *a, **k: self.fail("credentials were read without A3")
        try:
            for flag in ("A2", "a3", "A3 ", "yes"):
                with self.subTest(flag=flag):
                    out = io.StringIO()
                    with contextlib.redirect_stdout(out):
                        rc = trade_cli.main(["submit", "--state-dir", self.state, "--order-authorization",
                                             self.order_file(), "--authorization", flag])
                    self.assertEqual(rc, 2)
                    self.assertIn("NOT_AUTHORIZED", out.getvalue())
        finally:
            cfg.load_config = original

    def test_the_read_only_commands_cannot_write_even_when_asked(self):
        opener = ReadOnlyHttpsOpener(ACCOUNT)                       # the real stack
        for method, path, body in (("POST", "orders", b"{}"), ("PUT", "trades/1/close", b'{"units":"ALL"}')):
            with self.subTest(method=method):
                with self.assertRaises(NotSent):
                    opener(method, BASE + path, {}, body, 1)
        self.assertEqual(opener.sent, 0)

    def test_the_write_opener_cannot_exist_without_a_grant(self):
        for grant in (None, "A3", order_auth(), object()):
            with self.subTest(grant=type(grant).__name__):
                with self.assertRaises(a3.A3Refused):
                    a3.A3WriteOpener(ACCOUNT, grant)

    def test_a_grant_needs_a_current_authorization_for_this_account(self):
        config = demo.config()
        with self.assertRaises(AuthorizationRefused):
            a3.EntryGrant(order_auth(), config, datetime.datetime(2026, 11, 3, 18, 0, 0, tzinfo=datetime.timezone.utc))
        with self.assertRaises(AuthorizationRefused):
            a3.EntryGrant(order_auth(accountId="101-004-7654321-001"), config, NOW)
        close = authz.parse_close_authorization(json.dumps(dict(
            demo.CLOSE_AUTHORIZATION, clientOrderId="MOGO-ec130cb3d50bc908", tradeId="6369")).encode())
        with self.assertRaises(a3.A3Refused):
            a3.CloseGrant(close, config, datetime.datetime(2026, 11, 4, tzinfo=datetime.timezone.utc))


class TestTheGrantAdmitsExactlyOneAuthorizedWrite(Base):
    """Every request here goes through the REAL http.client stack: a slip would reach the guard."""

    def entry_opener(self, **over):
        return a3.A3WriteOpener(ACCOUNT, a3.EntryGrant(order_auth(**over), demo.config(), NOW))

    def body(self, **order_over):
        auth = order_auth()
        order = {"type": "MARKET", "instrument": "EUR_USD", "units": "1", "timeInForce": "FOK",
                 "positionFill": "OPEN_ONLY", "priceBound": "1.10020",
                 "stopLossOnFill": {"price": "1.09800", "timeInForce": "GTC"},
                 "clientExtensions": {"id": auth.client_order_id, "tag": "MOGO_BROKER_PRACTICE"},
                 "tradeClientExtensions": {"id": auth.client_order_id, "tag": "MOGO_BROKER_PRACTICE"}}
        for k, v in order_over.items():
            if v is None:
                order.pop(k)
            else:
                order[k] = v
        return json.dumps({"order": order}).encode()

    def assert_refused(self, opener, method, url, body):
        with self.assertRaises(a3.A3Refused if url.startswith(BASE) else NotSent):
            opener(method, url, {"Content-Type": "application/json"}, body, 1)

    def test_POSITIVE_CONTROL_the_granted_entry_reaches_the_socket_layer(self):
        before = len(m1.NET_ATTEMPTS)
        opener = self.entry_opener()
        with self.assertRaises(OSError):
            opener("POST", BASE + "orders", {"Content-Type": "application/json"}, self.body(), 1)
        attempts = m1.NET_ATTEMPTS[before:]
        del m1.NET_ATTEMPTS[before:]
        self.assertTrue(attempts, "the guard did not see the granted write: the zeros below would be vacuous")
        self.assertEqual(opener.writes, 1)

    def test_any_other_entry_is_refused_before_a_socket(self):
        cases = {"units": {"units": "2"}, "direction": {"units": "-1"}, "instrument": {"instrument": "GBP_USD"},
                 "stop price": {"stopLossOnFill": {"price": "1.09700", "timeInForce": "GTC"}},
                 "no stop": {"stopLossOnFill": None}, "no bound": {"priceBound": None},
                 "zero bound": {"priceBound": "0"}, "not FOK": {"timeInForce": "IOC"},
                 "may reduce": {"positionFill": "DEFAULT"}, "limit order": {"type": "LIMIT"},
                 "client id": {"clientExtensions": {"id": "MOGO-0000000000000000"}},
                 "trade client id": {"tradeClientExtensions": {"id": "MOGO-0000000000000000"}},
                 "extra field": {"takeProfitOnFill": {"price": "1.2"}}}
        for name, over in cases.items():
            with self.subTest(case=name):
                opener = self.entry_opener()
                self.assert_refused(opener, "POST", BASE + "orders", self.body(**over))
                self.assertEqual(opener.writes, 0)
        for name, (method, url, body) in {
                "PUT under an entry grant": ("PUT", BASE + "trades/6369/close", b'{"units":"ALL"}'),
                "DELETE": ("DELETE", BASE + "orders", self.body()),
                "PATCH": ("PATCH", BASE + "orders", self.body()),
                "another account": ("POST", BASE.replace("1234567", "7654321") + "orders", self.body()),
                "another host": ("POST", "https://example.com/v3/accounts/%s/orders" % ACCOUNT, self.body()),
                "the live host family": ("POST", "https://api-fx" + "trade.oanda.com/v3/accounts/%s/orders" % ACCOUNT, self.body()),
                "plain http": ("POST", BASE.replace("https", "http") + "orders", self.body()),
                "a port": ("POST", BASE.replace(".com/", ".com:443/") + "orders", self.body()),
                "a query": ("POST", BASE + "orders?x=1", self.body()),
                "not JSON": ("POST", BASE + "orders", b"{not json")}.items():
            with self.subTest(case=name):
                self.assert_refused(self.entry_opener(), method, url, body)

    def test_a_bound_beyond_the_limit_is_refused_and_one_at_it_reaches_the_socket(self):
        opener = self.entry_opener()
        self.assert_refused(opener, "POST", BASE + "orders", self.body(priceBound="1.10031"))
        self.assertEqual(opener.writes, 0)
        before = len(m1.NET_ATTEMPTS)
        with self.assertRaises(OSError):
            self.entry_opener()("POST", BASE + "orders", {"Content-Type": "application/json"},
                                self.body(priceBound="1.10030"), 1)
        self.assertTrue(m1.NET_ATTEMPTS[before:], "positive control: the bound at the limit is sent")
        del m1.NET_ATTEMPTS[before:]

    def test_a_sell_bound_below_its_limit_is_refused(self):
        auth = authz.parse_authorization(json.dumps(sell_data()).encode())
        opener = a3.A3WriteOpener(ACCOUNT, a3.EntryGrant(auth, demo.config(), NOW))
        body = json.loads(self.body(units="-1", priceBound="1.09979",
                                    stopLossOnFill={"price": "1.10200", "timeInForce": "GTC"}))
        for key in ("clientExtensions", "tradeClientExtensions"):
            body["order"][key]["id"] = auth.client_order_id
        self.assert_refused(opener, "POST", BASE + "orders", json.dumps(body).encode())
        self.assertEqual(opener.writes, 0)

    def test_a_spent_grant_refuses_a_second_write(self):
        opener = a3.A3WriteOpener(ACCOUNT, a3.EntryGrant(order_auth(), demo.config(), NOW),
                                  connection_factory=https_factory(self.broker, self.opened))
        status, _ = opener("POST", BASE + "orders", {"Content-Type": "application/json"}, self.body(), 1)
        self.assertEqual(status, 201)
        with self.assertRaises(a3.A3Refused):
            opener("POST", BASE + "orders", {"Content-Type": "application/json"}, self.body(), 1)
        self.assertEqual((self.broker.posts, opener.writes), (1, 1))

    def test_the_close_grant_admits_only_a_full_close_of_its_trade(self):
        close = authz.parse_close_authorization(json.dumps(dict(
            demo.CLOSE_AUTHORIZATION, clientOrderId="MOGO-ec130cb3d50bc908", tradeId="6369")).encode())
        for name, (method, url, body) in {
                "another trade": ("PUT", BASE + "trades/6370/close", b'{"units":"ALL"}'),
                "a partial close": ("PUT", BASE + "trades/6369/close", b'{"units":"1"}'),
                "an extra field": ("PUT", BASE + "trades/6369/close", b'{"units":"ALL","x":1}'),
                "an entry": ("POST", BASE + "orders", self.body()),
                "another host": ("PUT", "https://example.com/v3/accounts/%s/trades/6369/close" % ACCOUNT,
                                 b'{"units":"ALL"}')}.items():
            with self.subTest(case=name):
                opener = a3.A3WriteOpener(ACCOUNT, a3.CloseGrant(close, demo.config(), NOW))
                self.assert_refused(opener, method, url, body)
                self.assertEqual(opener.writes, 0)

    def test_reads_still_pass_the_read_only_checks(self):
        opener = a3.A3WriteOpener(ACCOUNT, a3.EntryGrant(order_auth(), demo.config(), NOW))
        with self.assertRaises(NotSent):
            opener("GET", BASE.replace("1234567", "7654321") + "summary", {}, None, 1)
        with self.assertRaises(NotSent):
            opener("GET", BASE + "summary", {}, b"{}", 1)


# ---- duplicate and uncertain submissions ----------------------------------------------------
class TestNoSecondOrder(Base):
    def test_the_same_authorization_never_sends_twice(self):
        order = self.order_file()
        self.assertEqual(self.submit(order)[0], 0)
        with self.assertRaises(Exception) as caught:
            self.submit(order)
        self.assertIn("AUTHORIZATION_ALREADY_USED", str(caught.exception))
        self.assertEqual((self.broker.posts, self.writes()), (1, [("POST", "/v3/accounts/%s/orders" % ACCOUNT)]))

    def test_an_uncertain_submit_blocks_everything_until_broker_evidence_resolves_it(self):
        self.broker.submit_behavior = "timeout_after_commit"
        code, out = self.submit()
        self.assertEqual((code, out["submit"]["state"]), (3, jn.UNCERTAIN))
        self.broker.submit_behavior = "fill"
        with self.assertRaises(Exception) as caught:
            self.submit(self.order_file(authorizationId="AUTH-M4-DEMO-0002"))
        self.assertIn("UNRESOLVED_INTENT_RECONCILE_FIRST", str(caught.exception))
        self.assertEqual(self.broker.posts, 1)
        self.assertEqual(self.position()["state"], jn.PROTECTED)      # resolved from the broker's own records
        self.assertEqual(self.broker.posts, 1)

    def test_a_timeout_before_the_broker_saw_it_resolves_absent_and_never_retries(self):
        self.broker.submit_behavior = "timeout_before_commit"
        code, out = self.submit()
        self.assertEqual((code, out["submit"]["state"]), (3, jn.UNCERTAIN))
        code, report = self.cmd("reconcile")
        self.assertEqual(report["resolved"][0]["state"], jn.NOT_SUBMITTED)
        self.assertEqual(self.broker.posts, 1)


# ---- broker answers that are not a clean fill ----------------------------------------------
class TestRejectionsPartialsAndStops(Base):
    def test_a_rejection_or_a_FOK_cancel_leaves_no_position(self):
        for behaviour, state in (("reject", jn.REJECTED), ("cancel", jn.CANCELLED)):
            with self.subTest(behaviour=behaviour):
                self.broker = FakeOanda(ACCOUNT)
                self.broker.submit_behavior = behaviour
                shutil.rmtree(self.state)
                os.makedirs(self.state)
                code, out = self.submit()
                self.assertEqual((code, out["submit"]["state"]), (1, state))
                self.assertIsNone(out["position"].get("state"))

    def test_a_partial_fill_is_never_accepted_as_the_authorized_position(self):
        self.broker.submit_behavior = "partial"
        code, out = self.submit(self.order_file(units=4))
        self.assertEqual((code, out["submit"]["state"], out["submit"]["reason"]),
                         (3, jn.UNCERTAIN, "FILL_UNITS_MISMATCH"))
        with self.assertRaises(Exception):
            self.submit(self.order_file(authorizationId="AUTH-M4-DEMO-0003"))
        self.assertEqual(self.broker.posts, 1)

    def test_a_missing_or_wrong_stop_halts_and_the_position_can_still_be_closed(self):
        for behaviour in ("missing", "wrong_price"):
            with self.subTest(behaviour=behaviour):
                self.broker = FakeOanda(ACCOUNT)
                self.broker.stop_behavior = behaviour
                shutil.rmtree(self.state)
                os.makedirs(self.state)
                code, out = self.submit()
                self.assertEqual(code, 3)
                self.assertEqual(out["position"]["state"], jn.OPEN_UNVERIFIED)
                self.assertTrue(any(h.startswith("UNPROTECTED_POSITION") for h in out["position"]["activeHalts"]))
                code, out = self.close(self.close_file(out["position"]))
                self.assertEqual(out["close"]["state"], jn.CLOSED)
                self.assertEqual(self.broker.trades, [])


# ---- constraints proven immediately before the entry ----------------------------------------
class TestPreEntryConstraints(Base):
    def assert_refused(self, code_wanted, order=None):
        with self.assertRaises(Exception) as caught:
            self.submit(order)
        self.assertIn(code_wanted, str(caught.exception))
        self.assertEqual((self.broker.posts, self.writes()), (0, []))

    def test_size_precision_distance_and_pending_orders(self):
        spec = self.broker.instrument_specs["EUR_USD"]
        cases = [
            ("UNITS_BELOW_BROKER_MINIMUM", lambda: spec.update(minimumTradeSize="10"), {}),
            ("UNITS_ABOVE_BROKER_MAXIMUM", lambda: spec.update(maximumOrderUnits="5"), {"units": 10}),
            ("STOP_PRICE_PRECISION_EXCEEDED", None, {"stopLossPrice": "1.098001"}),
            ("PRICE_BOUND_PRECISION_EXCEEDED", None, {"maxSlippage": "0.000101"}),
            ("STOP_TOO_CLOSE_TO_MARKET", None, {"stopLossPrice": "1.09960"}),
            # 7 pips clears the 5-pip floor but not twice a 4-pip spread: only the spread floor refuses
            ("STOP_TOO_CLOSE_TO_MARKET", lambda: self.broker.prices["EUR_USD"].update(bid="1.10000", ask="1.10040"),
             {"stopLossPrice": "1.09930", "maxSpread": "0.00050"}),
            ("BROKER_ACCOUNT_HAS_PENDING_ORDERS", lambda: setattr(self.broker, "pending_order_count", 1), {}),
            ("BROKER_READ_FAILED", lambda: self.broker.fail_reads.add("INSTRUMENT_DETAILS"), {}),
            ("SPREAD_TOO_WIDE", lambda: self.broker.prices["EUR_USD"].update(ask="1.10030"), {}),
            ("INSTRUMENT_NOT_TRADEABLE", lambda: self.broker.prices["EUR_USD"].update(tradeable=False), {}),
            ("QUOTE_STALE", lambda: self.broker.prices["EUR_USD"].update(time="2026-11-03T11:59:00.000000000Z"), {}),
            ("BROKER_ACCOUNT_HAS_OPEN_TRADES", lambda: self.broker.trades.append({"id": "9"}), {}),
        ]
        for code_wanted, mutate, over in cases:
            with self.subTest(code=code_wanted, over=over):
                self.broker = FakeOanda(ACCOUNT)
                spec = self.broker.instrument_specs["EUR_USD"]
                if mutate:
                    mutate()
                self.assert_refused(code_wanted, self.order_file(
                    authorizationId="AUTH-M4-C-%04d" % len(os.listdir(self.work)), **over))

    def test_an_unstated_pending_order_count_is_not_zero(self):
        account = ad.AccountSummary(ACCOUNT, "USD", "1", 0, b"", balance=Decimal("1"))
        quote = ad.Quote("EUR_USD", Decimal("1.10000"), Decimal("1.10010"), NOW, True, b"")
        self.assertIn("PENDING_ORDERS_NOT_PROVEN_ZERO", risk.assess_constraints(order_auth(), quote, account, None))
        self.assertIn("INSTRUMENT_CONSTRAINTS_UNPROVEN", risk.assess_constraints(order_auth(), quote, account, None))

    def test_the_first_trade_risk_cap_is_five_dollars(self):
        self.assertEqual(authz.HARD_MAX_LOSS, Decimal("5"))
        with self.assertRaises(AuthorizationRefused):
            order_auth(maxLoss="5.01")
        self.assert_refused("LOSS_AT_STOP_EXCEEDS_MAX_LOSS",
                            self.order_file(units=1000, stopLossPrice="1.09000", maxLoss="5"))


# ---- the close is its own authorization -----------------------------------------------------
class TestTheSeparateCloseAuthorization(Base):
    def open(self):
        self.assertEqual(self.submit()[0], 0)
        return self.position()

    def test_a_close_authorization_must_name_this_trade_account_and_moment(self):
        pos = self.open()
        cases = {"another trade": {"tradeId": "999"}, "another client id": {"clientOrderId": "MOGO-0000000000000000"},
                 "another account": {"accountId": "101-004-7654321-001"},
                 "expired": {"issuedAt": "2026-11-03T08:00:00Z", "expiresAt": "2026-11-03T09:00:00Z"}}
        for name, over in cases.items():
            with self.subTest(case=name):
                with self.assertRaises(Exception):
                    self.close(self.close_file(pos, **over))
                self.assertEqual(self.broker.close_puts, 0)
        self.assertEqual(self.position()["state"], jn.PROTECTED)

    def test_a_close_authorization_is_spent_once_even_if_the_broker_refused(self):
        pos = self.open()
        self.broker.close_behavior = "cancel"
        once = self.close_file(pos)
        code, out = self.close(once)
        self.assertEqual(out["close"]["state"], jn.PROTECTED)          # broker cancelled: back to protected
        self.broker.close_behavior = "fill"
        with self.assertRaises(Exception) as caught:
            self.close(once)
        self.assertIn("CLOSE_AUTHORIZATION_ALREADY_USED", str(caught.exception))
        self.assertEqual(self.broker.close_puts, 1)
        code, out = self.close(self.close_file(pos))                  # a NEW close authorization
        self.assertEqual((code, out["position"]["state"]), (0, jn.RECONCILED))

    def test_closing_is_allowed_under_the_kill_switch_and_entering_is_not(self):
        pos = self.open()
        KillSwitch(self.state).engage("emergency")
        code, out = self.close(self.close_file(pos))
        self.assertEqual((code, out["position"]["state"]), (0, jn.RECONCILED))
        with self.assertRaises(Exception) as caught:
            self.submit(self.order_file(authorizationId="AUTH-M4-DEMO-0009"))
        self.assertIn("KILL_SWITCH_ENGAGED", str(caught.exception))
        self.assertEqual(self.broker.posts, 1)

    def test_a_close_authorization_file_is_strict(self):
        good = dict(demo.CLOSE_AUTHORIZATION, clientOrderId="MOGO-ec130cb3d50bc908", tradeId="6369")
        authz.parse_close_authorization(json.dumps(good).encode())            # positive control
        cases = {"another mode": {"mode": "LIVE"}, "longer than 24h": {"expiresAt": "2026-11-04T11:00:01Z"},
                 "ends before it starts": {"expiresAt": "2026-11-03T10:00:00Z"},
                 "a trade id that is not a number": {"tradeId": "6369; DROP"},
                 "a client id MOGO never makes": {"clientOrderId": "MOGO-XYZ"}, "no operator": {"issuedBy": " "},
                 "an extra field": {"units": "ALL"}}
        for name, over in cases.items():
            with self.subTest(case=name):
                with self.assertRaises(AuthorizationRefused):
                    authz.parse_close_authorization(json.dumps(dict(good, **over)).encode())

    def test_close_authorizations_are_append_only(self):
        pos = self.open()
        self.assertEqual(self.close(self.close_file(pos))[0], 0)
        journal = jn.Journal(os.path.join(self.state, "journal.sqlite3"))
        try:
            self.assertEqual(journal._db.execute("SELECT COUNT(*) FROM close_authorizations").fetchone()[0], 1)
            for sql in ("DELETE FROM close_authorizations", "UPDATE close_authorizations SET trade_id='1'"):
                with self.subTest(sql=sql):
                    with self.assertRaises(Exception):
                        journal._db.execute(sql)
        finally:
            journal.close()

    def test_the_executor_refuses_a_close_without_a_close_authorization(self):
        pos = self.open()
        from oanda_practice import executor as ex
        transport = tp.Transport(demo.config(), opener=self.broker)
        executor = ex.Executor(demo.config(), ad.OandaPracticeAdapter(transport), self.state, clock=lambda: NOW)
        try:
            # No grant layer here: the executor's own check is the only thing in the way.
            def close_auth(**over):
                data = dict(demo.CLOSE_AUTHORIZATION, clientOrderId=pos["clientOrderId"], tradeId=pos["trade_id"])
                data.update(over)
                return authz.parse_close_authorization(json.dumps(data).encode())
            for name, bad in (("none", None), ("an entry authorization", order_auth()),
                              ("another trade", close_auth(tradeId="999")),
                              ("another client id", close_auth(clientOrderId="MOGO-0000000000000000"))):
                with self.subTest(bad=name):
                    with self.assertRaises(Exception) as caught:
                        executor.close_position(pos["clientOrderId"][len("MOGO-"):], bad)
                    self.assertIn("CLOSE_AUTHORIZATION_REFUSED", str(caught.exception))
        finally:
            executor.close()
        self.assertEqual(self.broker.close_puts, 0)


# ---- documented v20 shapes ----------------------------------------------------------------
class _Canned(object):
    def __init__(self, responses):
        self.responses = responses

    def request(self, operation, body=None, **params):
        status, data = self.responses[operation]
        return tp.Response(status, json.dumps(data).encode())


class TestDocumentedV20Shapes(unittest.TestCase):
    cid = V20["client_id"]

    def adapter(self, **responses):
        return ad.OandaPracticeAdapter(_Canned(responses))

    def test_entry_fill_reject_and_FOK_cancel(self):
        out = self.adapter(CREATE_ORDER=(201, V20["entry_fill_201"])).submit_market_order({}, self.cid, 1)
        self.assertEqual((out.kind, out.trade_id, out.fill_price, out.fill_units), (ad.FILLED, "6369",
                                                                                     Decimal("1.10010"), Decimal("1")))
        out = self.adapter(CREATE_ORDER=(400, V20["entry_reject_400"])).submit_market_order({}, self.cid, 1)
        self.assertEqual((out.kind, out.reason), (ad.REJECTED, "STOP_LOSS_ON_FILL_LOSS"))
        out = self.adapter(CREATE_ORDER=(201, V20["entry_fok_cancel_201"])).submit_market_order({}, self.cid, 1)
        self.assertEqual((out.kind, out.reason), (ad.CANCELLED, "BOUNDS_VIOLATION"))

    def test_a_fill_without_the_deprecated_price_field_is_still_FILLED_at_the_trade_price(self):
        data = json.loads(json.dumps(V20["entry_fill_201"]))
        del data["orderFillTransaction"]["price"]
        out = self.adapter(CREATE_ORDER=(201, data)).submit_market_order({}, self.cid, 1)
        self.assertEqual((out.kind, out.fill_price), (ad.FILLED, Decimal("1.10010")))

    def test_trade_details_carry_the_pending_stop(self):
        trade = self.adapter(TRADE_DETAILS=(200, V20["trade_open_200"])).trade("6369")
        self.assertEqual((trade.state, trade.current_units, trade.stop_order["state"], trade.stop_order["price"]),
                         ("OPEN", Decimal("1"), "PENDING", Decimal("1.09800")))

    def test_full_and_partial_close(self):
        out = self.adapter(CLOSE_TRADE=(200, V20["close_200"])).close_trade("6369", 1)
        self.assertEqual((out.kind, out.fill_price), ("CLOSED", Decimal("1.10250")))
        out = self.adapter(CLOSE_TRADE=(200, V20["partial_close_200"])).close_trade("6369", 1)
        self.assertEqual((out.kind, out.reason), (ad.UNCERTAIN, "PARTIAL_CLOSE"))

    def test_instrument_constraints_parse(self):
        spec = self.adapter(INSTRUMENT_DETAILS=(200, V20["instrument_200"])).instrument_spec("EUR_USD")
        self.assertEqual((spec.minimum_trade_size, spec.display_precision, spec.pip_location,
                          spec.trade_units_precision), (Decimal("1"), 5, -4, 0))
        broken = json.loads(json.dumps(V20["instrument_200"]))
        del broken["instruments"][0]["minimumTradeSize"]
        with self.assertRaises(Exception):
            self.adapter(INSTRUMENT_DETAILS=(200, broken)).instrument_spec("EUR_USD")

    def test_the_documented_window_reconciles_on_fills_stream_and_balance(self):
        window = [V20["entry_fill_201"]["orderCreateTransaction"], V20["entry_fill_201"]["orderFillTransaction"],
                  V20["stop_loss_order_txn"], V20["close_200"]["orderCreateTransaction"],
                  V20["close_200"]["orderFillTransaction"], V20["linked_stop_cancel_txn"]]
        result = accounting.reconcile_trade("6369", 1, Decimal("100000.0000"), window, Decimal("100000.0024"),
                                            "6376", "6376")
        self.assertTrue(result.ok, result.codes)
        self.assertEqual((result.figures["realized_pl"], result.figures["net_pl"]),
                         (Decimal("0.0024"), Decimal("0.0024")))


# ---- repair A: the practice API answers 404 for a CLOSED trade ------------------------------
with open(os.path.join(HERE, "fixtures", "oanda_practice_observed_first_trade_20261109.json"),
          encoding="utf-8") as _h:
    OBSERVED = json.load(_h)


class TestAClosedTrade404ReconcilesOnlyFromCloseEvidence(Base):
    """Through the CLI against the fake, which now answers 404 for a closed trade as OANDA did."""

    def test_POSITIVE_the_fake_models_the_observed_404_and_the_close_reconciles(self):
        self.assertEqual(self.submit()[0], 0)
        pos = self.position()
        code, out = self.close(self.close_file(pos))
        status, body = self.broker("GET", BASE + "trades/%s" % pos["trade_id"], {}, None, 1)
        self.assertEqual((status, json.loads(body)["errorCode"]), (404, "NO_SUCH_TRADE"))
        self.assertEqual((code, out["position"]["state"], out["position"]["activeHalts"]), (0, jn.RECONCILED, []))
        # fill-based: entry 1.10010 (ask), exit 1.10000 (bid), 1 unit: -0.0001
        self.assertEqual((out["position"]["entry_price"], out["position"]["exit_price"],
                          out["position"]["net_pl"]), ("1.10010", "1.10000", "-0.0001"))

    def test_a_404_with_no_close_fill_still_halts_as_missing(self):
        self.assertEqual(self.submit()[0], 0)
        self.broker.trades.clear()                     # gone, and the history shows no close
        code, out = self.cmd("reconcile")
        self.assertEqual(code, 3)
        self.assertEqual(out["halted"], ["TRADE_MISSING_AT_BROKER %s" % self.position()["trade_id"]])
        self.assertEqual(self.position()["state"], jn.PROTECTED)

    def test_a_stop_that_fired_then_404_reconciles_from_the_stop_fill(self):
        self.assertEqual(self.submit()[0], 0)
        pos = self.position()
        self.broker.trigger_stop(pos["trade_id"])
        code, out = self.cmd("reconcile")
        self.assertEqual((code, self.position()["state"]), (0, jn.RECONCILED))


class TestTheObservedFirstTradeReplay(unittest.TestCase):
    """The REAL 2026-11-09 broker evidence, replayed into a journal in the state the live one was
    left in (CLOSED after a CLOSE_FILLED close). Reads only: the canned adapter has no write."""

    def setUp(self):
        self.net_before = len(m1.NET_ATTEMPTS)
        self.work = tempfile.mkdtemp(prefix="mogo_m4_obs_")
        self.asked = []

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)
        self.assertEqual(m1.NET_ATTEMPTS[self.net_before:], [], "a test attempted network access")

    def seed(self, state):
        journal = jn.Journal(os.path.join(state, "journal.sqlite3"))
        try:
            auth = order_auth(authorizationId=OBSERVED["authorization_id"], stopLossPrice="1.11757",
                              maxEntryPrice="1.12036", maxSpread="0.00030")
            self.assertEqual(auth.client_order_id, OBSERVED["client_id"])
            journal.reserve(auth, 1, Decimal("1.12036"), OBSERVED["last_transaction_id_before"], b"{}", [],
                            balance_before=Decimal(OBSERVED["balance_before"]))
            journal.transition(auth.intent_id, jn.FILLED, broker_order_id="4", broker_trade_id="5",
                               fill_price=Decimal("1.12032"), fill_units=Decimal("1"))
            journal.open_position(auth.intent_id, "5", "EUR_USD", 1, "1.11757")   # as the executor passes it
            journal.transition_position(auth.intent_id, jn.PROTECTED, reason="STOP_VERIFIED", stop_order_id="6")
            close = authz.parse_close_authorization(json.dumps(dict(
                demo.CLOSE_AUTHORIZATION, clientOrderId=OBSERVED["client_id"], tradeId="5")).encode())
            journal.transition_position(auth.intent_id, jn.CLOSING, reason="CLOSE_REQUESTED", consume_close=close,
                                        last_transaction_id_before_close="6")
            journal.transition_position(auth.intent_id, jn.CLOSED, reason="CLOSE_FILLED",
                                        exit_price=Decimal("1.11911"), close_reason="MARKET_ORDER_TRADE_CLOSE")
            return auth.intent_id
        finally:
            journal.close()

    def reconcile(self, window=None, summary=None):
        state = os.path.join(self.work, "state-%d" % len(os.listdir(self.work)))
        os.makedirs(state)
        intent_id = self.seed(state)
        window = window or OBSERVED["transactions_since_3"]
        summary = dict(OBSERVED["summary_after_close"], **(summary or {}))
        summary["lastTransactionID"] = window["lastTransactionID"]
        canned = _Canned({"ACCOUNT_SUMMARY": (200, {"account": summary, "lastTransactionID": window["lastTransactionID"]}),
                          "TRADE_DETAILS": (404, OBSERVED["closed_trade_details_404"]),
                          "TRANSACTIONS_SINCE": (200, window), "OPEN_TRADES": (200, {"trades": []})})
        canned_request = canned.request

        def recording(operation, body=None, **params):
            self.asked.append(operation)
            return canned_request(operation, body, **params)
        canned.request = recording
        executor = ex.Executor(demo.config(), ad.OandaPracticeAdapter(canned), state, clock=lambda: NOW)
        try:
            report = executor.reconcile()
            return report, executor.journal.position(intent_id), [h["reason"] for h in executor.journal.active_halts()]
        finally:
            executor.close()

    def window_with(self, edit):
        window = json.loads(json.dumps(OBSERVED["transactions_since_3"]))
        edit(window["transactions"])
        return window

    @staticmethod
    def close_fill(txns):
        return next(t for t in txns if t["id"] == "8")

    def test_POSITIVE_the_real_evidence_reaches_RECONCILED_on_broker_figures(self):
        report, pos, halts = self.reconcile()
        self.assertEqual((pos["state"], halts, report["halted"]), (jn.RECONCILED, [], []))
        self.assertEqual({k: pos[k] for k in ("entry_fill_id", "entry_price", "close_fill_id", "exit_price",
                                              "realized_pl", "financing", "commission", "net_pl", "balance_after")},
                         {"entry_fill_id": "5", "entry_price": "1.12032", "close_fill_id": "8",
                          "exit_price": "1.11911", "realized_pl": "-0.0012", "financing": "0",
                          "commission": "0", "net_pl": "-0.0012", "balance_after": "99999.9988"})
        self.assertTrue(self.asked and set(self.asked) <= READ_OPERATIONS, self.asked)

    def assert_halted_unbooked(self, prefix, **kw):
        report, pos, halts = self.reconcile(**kw)
        self.assertTrue(any(h.startswith(prefix) for h in halts), halts)
        self.assertNotEqual(pos["state"], jn.RECONCILED)
        self.assertEqual((pos["net_pl"], pos["balance_after"], pos["realized_pl"]), (None, None, None))

    def test_a_404_whose_close_fill_names_another_trade_halts_as_missing(self):
        def other(txns):
            self.close_fill(txns)["tradesClosed"][0]["tradeID"] = "99"
        self.assert_halted_unbooked("TRADE_MISSING_AT_BROKER 5", window=self.window_with(other))

    def test_a_404_with_only_a_partial_close_halts(self):
        def partial(txns):
            fill = self.close_fill(txns)
            fill["tradeReduced"] = fill.pop("tradesClosed")[0]
        self.assert_halted_unbooked("CLOSE_EVIDENCE_INVALID 5", window=self.window_with(partial))

    def test_a_404_whose_close_quantity_disagrees_halts(self):
        def units(txns):
            self.close_fill(txns)["tradesClosed"][0]["units"] = "-2"
        self.assert_halted_unbooked("CLOSE_EVIDENCE_INVALID 5", window=self.window_with(units))

    def test_a_404_with_two_close_fills_halts_and_books_nothing(self):
        window = self.window_with(lambda txns: txns.append(dict(self.close_fill(txns), id="10")))
        window["lastTransactionID"] = "10"
        self.assert_halted_unbooked("MULTIPLE_CLOSE_FILLS 5", window=window)

    def test_a_404_whose_balance_disagrees_with_the_fills_halts(self):
        self.assert_halted_unbooked("ACCOUNTING_MISMATCH 5", summary={"balance": "99999.9900"})


# ---- repair B: the operator's absolute entry limit -----------------------------------------
def entry_data(**over):
    data = dict(demo.ORDER_AUTHORIZATION, **over)
    return {k: v for k, v in data.items() if v is not None}


def sell_data(**over):
    return entry_data(**dict({"direction": "SELL", "stopLossPrice": "1.10200", "maxEntryPrice": None,
                              "minEntryPrice": "1.09980"}, **over))


class TestTheApprovedEntryLimitIsEnforced(Base):
    def parse(self, data):
        return authz.parse_authorization(json.dumps(data).encode())

    def test_a_legacy_or_misnamed_authorization_is_refused(self):
        refused = {"legacy BUY without a limit": entry_data(maxEntryPrice=None),
                   "legacy SELL without a limit": sell_data(minEntryPrice=None),
                   "BUY carrying minEntryPrice": entry_data(maxEntryPrice=None, minEntryPrice="1.10030"),
                   "SELL carrying maxEntryPrice": sell_data(minEntryPrice=None, maxEntryPrice="1.09980"),
                   "both limits": entry_data(minEntryPrice="1.09980"),
                   "not a decimal": entry_data(maxEntryPrice="market"),
                   "a number, not a string": entry_data(maxEntryPrice=1.1003),
                   "zero": entry_data(maxEntryPrice="0"),
                   "BUY limit at the stop": entry_data(maxEntryPrice="1.09800"),
                   "BUY limit below the stop": entry_data(maxEntryPrice="1.09700"),
                   "SELL limit at the stop": sell_data(minEntryPrice="1.10200"),
                   "SELL limit above the stop": sell_data(minEntryPrice="1.10300")}
        for name, data in refused.items():
            with self.subTest(case=name):
                with self.assertRaises(AuthorizationRefused):
                    self.parse(data)
        self.assertEqual(self.parse(entry_data()).entry_price_limit, Decimal("1.10030"))
        self.assertEqual(self.parse(sell_data()).entry_price_limit, Decimal("1.09980"))

    def test_the_first_trades_file_shape_is_refused_by_the_cli_and_nothing_is_sent(self):
        legacy = self.order_file(**{"maxEntryPrice": None})
        with open(legacy) as h:
            data = {k: v for k, v in json.load(h).items() if v is not None}
        demo.write_json(legacy, data)
        with self.assertRaises(AuthorizationRefused):
            self.submit(legacy)
        self.assertEqual((self.broker.posts, self.writes()), (0, []))

    def assert_refused(self, order, code_wanted="PRICE_BOUND_BEYOND_APPROVED_ENTRY_LIMIT"):
        with self.assertRaises(Exception) as caught:
            self.submit(order)
        self.assertIn(code_wanted, str(caught.exception))
        self.assertEqual((self.broker.posts, self.writes()), (0, []))

    def test_the_first_trade_replayed_under_its_approved_limit_is_refused_before_any_write(self):
        # 13:56Z on 2026-11-09: ask 1.12026 + 1 pip slippage = 1.12036, above the approved 1.11980.
        self.broker.prices["EUR_USD"].update(bid="1.12010", ask="1.12026")
        self.assert_refused(self.order_file(stopLossPrice="1.11757", maxEntryPrice="1.11980", maxSpread="0.00030"))

    def test_a_buy_whose_bound_would_pass_the_limit_is_refused_and_one_at_it_fills(self):
        self.broker.prices["EUR_USD"].update(bid="1.10011", ask="1.10021")     # bound 1.10031 > 1.10030
        self.assert_refused(self.order_file())
        self.broker = FakeOanda(ACCOUNT)
        self.broker.prices["EUR_USD"].update(bid="1.10010", ask="1.10020")     # bound 1.10030 == limit
        code, out = self.submit(self.order_file(authorizationId="AUTH-M4-LIMIT-0002"))
        self.assertEqual((code, out["submit"]["state"]), (0, jn.FILLED))
        self.assertEqual(self.broker.posts, 1)

    def test_a_sell_whose_bound_would_pass_the_limit_is_refused(self):
        self.broker.prices["EUR_USD"].update(bid="1.09989", ask="1.09999")     # bound 1.09979 < 1.09980
        order = demo.write_json(os.path.join(self.work, "sell.json"), sell_data())
        self.assert_refused(order)

    def test_the_limit_must_fit_the_broker_price_precision(self):
        self.assert_refused(self.order_file(maxEntryPrice="1.100301"), "ENTRY_LIMIT_PRECISION_EXCEEDED")

    def test_the_dry_run_shows_the_approved_limit(self):
        code, out = self.cmd("dry-run", "--order-authorization", self.order_file())
        self.assertEqual((code, out["approvedEntryLimit"]), (0, {"maxEntryPrice": "1.10030"}))


if __name__ == "__main__":
    unittest.main()

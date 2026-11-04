#!/usr/bin/env python3
"""M1 offline practice executor: refusals, identity, kill switch, uncertainty, restart, secrecy.

ZERO NETWORK. setUpModule replaces socket connect/create_connection/getaddrinfo
with recorders that raise; every test asserts no attempt was made, and
TestTheNetworkGuard proves the guard catches an attempt (positive control).
The broker is tests/execution/fake_oanda.py, injected as the transport's opener.

Every refusal test also counts the fake's create-order requests: a refusal
that still sent an order is the failure this suite exists to catch. Each
refusal has a positive control (the unmodified fixture is approved).
"""
import ast
import contextlib
import datetime
import io
import json
import os
import pickle
import shutil
import socket
import sqlite3
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
EXEC_DIR = os.path.join(REPO_ROOT, "execution")
sys.path.insert(0, EXEC_DIR)
sys.path.insert(0, HERE)

from oanda_practice import adapter as ad          # noqa: E402
from oanda_practice import authorization as authz  # noqa: E402
from oanda_practice import config as cfg          # noqa: E402
from oanda_practice import executor as ex         # noqa: E402
from oanda_practice import journal as jn          # noqa: E402
from oanda_practice import transport as tp        # noqa: E402
from oanda_practice.errors import (AuthorizationRefused, ConfigRefused, NotSent,  # noqa: E402
                                   OrderRefused, PracticeExecutionError, TransportRefused)
from fake_oanda import FakeOanda                  # noqa: E402
import mogo_practice_executor as cli              # noqa: E402

ACCOUNT = "101-004-1234567-001"
TOKEN = "tok-" + "7f3c9a1e5b2d4f6a8c0e1b3d5f7a9c2e"
NOW = datetime.datetime(2026, 11, 3, 12, 0, 1, tzinfo=datetime.timezone.utc)
LIVE_MARKER = "fx" + "trade"

# ---- the network guard --------------------------------------------------------
NET_ATTEMPTS = []
_ORIGINALS = {}


def _blocked(name):
    def guard(*args, **kwargs):
        NET_ATTEMPTS.append(name)
        raise OSError("network blocked by test guard: %s" % name)
    return guard


def _audit(event, args):
    # Interpreter-level: fires for C-level socket creation and connects too, so a path that
    # bypassed the patched functions below would still be recorded.
    if event.startswith("socket.") and _AUDIT_ARMED:
        NET_ATTEMPTS.append("audit:" + event)


_AUDIT_ARMED = False
sys.addaudithook(_audit)


def setUpModule():
    global _AUDIT_ARMED
    _AUDIT_ARMED = True
    _ORIGINALS.update(connect=socket.socket.connect, connect_ex=socket.socket.connect_ex,
                      create_connection=socket.create_connection, getaddrinfo=socket.getaddrinfo)
    socket.socket.connect = _blocked("socket.connect")
    socket.socket.connect_ex = _blocked("socket.connect_ex")
    socket.create_connection = _blocked("create_connection")
    socket.getaddrinfo = _blocked("getaddrinfo")


def tearDownModule():
    global _AUDIT_ARMED
    _AUDIT_ARMED = False
    socket.socket.connect = _ORIGINALS["connect"]
    socket.socket.connect_ex = _ORIGINALS["connect_ex"]
    socket.create_connection = _ORIGINALS["create_connection"]
    socket.getaddrinfo = _ORIGINALS["getaddrinfo"]


# ---- fixtures -----------------------------------------------------------------
def read_text(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def auth_data(**over):
    data = {"authorizationId": "AUTH-20261103-0001", "mode": "BROKER_PRACTICE", "accountId": ACCOUNT,
            "instrument": "EUR_USD", "direction": "BUY", "units": 1000, "stopLossPrice": "1.09800",
            "maxSlippage": "0.00010", "maxSpread": "0.00020", "maxLoss": "5",
            "maxQuoteAgeSeconds": 10, "issuedAt": "2026-11-03T11:00:00Z",
            "expiresAt": "2026-11-03T18:00:00Z", "issuedBy": "operator"}
    data.update(over)
    return data


def make_auth(**over):
    return authz.parse_authorization(json.dumps(auth_data(**over)).encode())


class Harness(unittest.TestCase):
    """A fresh state dir, fake broker and executor per test; asserts zero network."""

    def setUp(self):
        self._net_before = len(NET_ATTEMPTS)
        self.dir = tempfile.mkdtemp(prefix="mogo_practice_test_")
        self.config = cfg.config_from_mapping({"accountId": ACCOUNT, "token": TOKEN})
        self.fake = FakeOanda(ACCOUNT)
        self.ex = self.new_executor()

    def new_executor(self, opener=None):
        kill = ex.KillSwitch(self.dir)
        transport = tp.Transport(self.config, opener=opener or self.fake, kill_switch=kill)
        return ex.Executor(self.config, ad.OandaPracticeAdapter(transport), self.dir, clock=lambda: NOW)

    def tearDown(self):
        self.ex.close()
        shutil.rmtree(self.dir, ignore_errors=True)
        self.assertEqual(NET_ATTEMPTS[self._net_before:], [], "a test attempted network access")

    def assertRefused(self, code, fn, *args, **kwargs):
        posts = self.fake.posts
        with self.assertRaises(OrderRefused) as ctx:
            fn(*args, **kwargs)
        self.assertTrue(any(c.startswith(code) for c in ctx.exception.codes),
                        "%s not in %s" % (code, ctx.exception.codes))
        self.assertEqual(self.fake.posts, posts, "a refused order still reached the broker")
        return ctx.exception.codes

    def state(self, auth):
        return self.ex.journal.intent(auth.intent_id)["state"]


# ---- T-NET ----------------------------------------------------------------------
class TestTheNetworkGuard(Harness):
    def test_POSITIVE_CONTROL_the_guard_catches_a_real_connection_attempt(self):
        before = len(NET_ATTEMPTS)
        with self.assertRaises(OSError):
            socket.create_connection(("127.0.0.1", 9))
        self.assertEqual(NET_ATTEMPTS[before:], ["create_connection"])
        del NET_ATTEMPTS[before:]

    def test_POSITIVE_CONTROL_the_audit_hook_sees_socket_creation(self):
        before = len(NET_ATTEMPTS)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.close()
        self.assertIn("audit:socket.__new__", NET_ATTEMPTS[before:])
        del NET_ATTEMPTS[before:]

    def test_no_package_module_imports_a_network_or_process_library(self):
        banned = {"socket", "ssl", "http", "urllib.request", "requests", "asyncio", "subprocess", "ftplib"}
        files = [os.path.join(dp, f) for dp, _, fs in os.walk(EXEC_DIR) for f in fs if f.endswith(".py")]
        self.assertGreater(len(files), 5)
        for path in files:
            tree = ast.parse(read_text(path))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module] + [node.module + "." + a.name for a in node.names]
                for name in names:
                    with self.subTest(file=os.path.relpath(path, REPO_ROOT), name=name):
                        self.assertFalse(name in banned or name.split(".")[0] in banned - {"urllib"})

    def test_the_default_opener_sends_nothing_and_a_submit_refuses(self):
        executor = self.new_executor(opener=tp.NetworkDisabledOpener())
        try:
            self.assertRefused("BROKER_READ_FAILED", executor.submit, make_auth())
        finally:
            executor.close()
        transport = tp.Transport(self.config)
        with self.assertRaises(NotSent):
            transport.request("CREATE_ORDER", body={"order": {}})


# ---- T-HOST ---------------------------------------------------------------------
class TestOnlyThePracticeHostIsReachable(Harness):
    def test_every_allowed_operation_resolves_to_the_practice_host(self):
        t = tp.Transport(self.config, opener=self.fake)
        params = {"PRICING": {"instrument": "EUR_USD"},
                  "ORDER_BY_CLIENT_ID": {"client_id": "MOGO-0123456789abcdef"},
                  "TRANSACTIONS_SINCE": {"transaction_id": "100"},
                  "TRADE_DETAILS": {"trade_id": "102"}, "CLOSE_TRADE": {"trade_id": "102"}}
        self.assertEqual(set(tp.OPERATIONS), {"ACCOUNT_SUMMARY", "PRICING", "OPEN_TRADES",
                                              "ORDER_BY_CLIENT_ID", "TRANSACTIONS_SINCE", "CREATE_ORDER",
                                              "TRADE_DETAILS", "CLOSE_TRADE"})
        # Exactly one operation may OPEN exposure, so it is the only one the kill switch gates.
        self.assertEqual([op for op, spec in tp.OPERATIONS.items() if spec[3]], ["CREATE_ORDER"])
        for op in tp.OPERATIONS:
            with self.subTest(op=op):
                _m, url, _w = t.url_for(op, **params.get(op, {}))
                self.assertTrue(url.startswith("https://api-fxpractice.oanda.com/v3/accounts/%s/" % ACCOUNT))

    def test_no_source_file_names_the_live_host_family(self):
        roots = [EXEC_DIR, HERE]
        files = [os.path.join(dp, f) for r in roots for dp, _, fs in os.walk(r) for f in fs
                 if f.endswith((".py", ".json", ".md"))]
        self.assertGreater(len(files), 5)
        for path in files:
            with self.subTest(file=os.path.relpath(path, REPO_ROOT)):
                self.assertNotIn(LIVE_MARKER, read_text(path).lower())

    def test_config_cannot_set_a_host_or_environment_or_name_the_live_family(self):
        cfg.config_from_mapping({"accountId": ACCOUNT, "token": TOKEN})          # positive control
        for key in ("host", "url", "baseUrl", "environment", "env", "live"):
            with self.subTest(key=key), self.assertRaises(ConfigRefused):
                cfg.config_from_mapping({"accountId": ACCOUNT, "token": TOKEN, key: "x"})
        with self.assertRaises(ConfigRefused):
            cfg.config_from_mapping({"accountId": ACCOUNT, "token": TOKEN,
                                     "note": "api-" + LIVE_MARKER + ".oanda.com"})

    def test_parameters_cannot_redirect_or_inject(self):
        t = tp.Transport(self.config, opener=self.fake)
        bad = [("PRICING", {"instrument": "EUR_USD@evil.example"}),
               ("PRICING", {"instrument": "EUR_USD&x=1"}),
               ("ORDER_BY_CLIENT_ID", {"client_id": "../../orders"}),
               ("TRANSACTIONS_SINCE", {"transaction_id": "1;2"}),
               ("ACCOUNT_SUMMARY", {"account": "001-001-1-001"}),
               ("CLOSE_TRADE", {}), ("DELETE_EVERYTHING", {})]
        for op, params in bad:
            with self.subTest(op=op, params=params), self.assertRaises(TransportRefused):
                t.url_for(op, **params)
        self.assertEqual(self.fake.requests, [])

    def test_the_final_host_check_refuses_even_if_the_base_url_were_changed(self):
        t = tp.Transport(self.config, opener=self.fake)
        t.url_for("ACCOUNT_SUMMARY")                                              # positive control
        original = cfg.PRACTICE_BASE_URL
        try:
            for base in ("https://api-other.example", "http://api-fxpractice.oanda.com",
                         "https://api-fxpractice.oanda.com:8443"):
                cfg.PRACTICE_BASE_URL = base
                with self.subTest(base=base), self.assertRaises(TransportRefused):
                    t.url_for("ACCOUNT_SUMMARY")
        finally:
            cfg.PRACTICE_BASE_URL = original

    def test_a_summary_for_another_account_refuses(self):
        self.fake.summary_account_id = "101-004-7654321-001"
        self.assertRefused("BROKER_RETURNED_ANOTHER_ACCOUNT", self.ex.submit, make_auth())

    def test_credentials_file_permissions_are_enforced(self):
        path = os.path.join(self.dir, "creds.json")
        with open(path, "w") as handle:
            json.dump({"accountId": ACCOUNT, "token": TOKEN}, handle)
        os.chmod(path, 0o600)
        self.assertEqual(cfg.load_config(path).account_id, ACCOUNT)            # positive control
        for mode in (0o640, 0o604, 0o644):
            os.chmod(path, mode)
            with self.subTest(mode=oct(mode)), self.assertRaises(ConfigRefused):
                cfg.load_config(path)
        with self.assertRaises(ConfigRefused):
            cfg.load_config(os.path.join(self.dir, "absent.json"))


# ---- T-AUTH ---------------------------------------------------------------------
class TestAuthorization(Harness):
    def test_POSITIVE_CONTROL_the_fixture_authorization_is_approved_and_filled(self):
        auth = make_auth()
        row = self.ex.submit(auth)
        self.assertEqual(row["state"], jn.FILLED)
        self.assertEqual(self.fake.posts, 1)

    def test_malformed_authorizations_are_refused(self):
        cases = {"wrong mode": {"mode": "LIVE"}, "units over hard max": {"units": 1001},
                 "units not int": {"units": "1000"}, "units bool": {"units": True},
                 "zero units": {"units": 0}, "direction": {"direction": "LONG"},
                 "maxLoss over ceiling": {"maxLoss": "10.01"}, "negative stop": {"stopLossPrice": "-1"},
                 "lifetime over 24h": {"expiresAt": "2026-11-04T11:00:01Z"},
                 "expires before issue": {"expiresAt": "2026-11-03T10:00:00Z"},
                 "quote age over ceiling": {"maxQuoteAgeSeconds": 31}, "no issuer": {"issuedBy": " "},
                 "bad id": {"authorizationId": "x"}, "bad time": {"issuedAt": "2026-11-03 11:00"},
                 "instrument shape": {"instrument": "EURUSD"}}
        for name, over in cases.items():
            with self.subTest(case=name), self.assertRaises(AuthorizationRefused):
                make_auth(**over)
        data = auth_data()
        data["extra"] = 1
        with self.assertRaises(AuthorizationRefused):
            authz.parse_authorization(json.dumps(data).encode())
        del data["extra"], data["maxLoss"]
        with self.assertRaises(AuthorizationRefused):
            authz.parse_authorization(json.dumps(data).encode())
        with self.assertRaises(AuthorizationRefused):
            authz.parse_authorization(b"not json")

    def test_expired_not_yet_valid_and_other_account_are_refused_before_any_read(self):
        for over, _name in (({"issuedAt": "2026-11-03T12:00:02Z", "expiresAt": "2026-11-03T13:00:00Z"}, "future"),
                            ({"issuedAt": "2026-11-03T10:00:00Z", "expiresAt": "2026-11-03T12:00:01Z"}, "expired"),
                            ({"accountId": "101-004-7654321-001"}, "account")):
            with self.subTest(case=_name):
                self.assertRefused("AUTHORIZATION_REFUSED", self.ex.submit, make_auth(**over))
        self.assertEqual(self.fake.requests, [])

    def test_an_authorization_places_at_most_one_order_ever(self):
        auth = make_auth()
        self.ex.submit(auth)
        self.fake.trades.clear()   # even with the broker flat again...
        self.assertRefused("AUTHORIZATION_ALREADY_USED", self.ex.submit, auth)
        self.assertEqual(self.fake.posts, 1)


# ---- T-RISK and T-PRICE ---------------------------------------------------------
class TestRiskAndQuotes(Harness):
    def test_POSITIVE_CONTROL_risk_approves_the_fixture(self):
        self.assertEqual(self.ex.submit(make_auth(), dry_run=True)["journalWrites"], 0)

    def test_loss_at_the_stop_over_max_loss_is_refused(self):
        # (1.10020 bound - 1.09500) * 1000 = 5.20 > 5
        self.assertRefused("LOSS_AT_STOP_EXCEEDS_MAX_LOSS", self.ex.submit, make_auth(stopLossPrice="1.09500"))

    def test_stop_on_the_wrong_side_is_refused_both_directions(self):
        self.assertRefused("STOP_ON_WRONG_SIDE", self.ex.submit, make_auth(stopLossPrice="1.10005"))
        self.assertRefused("STOP_ON_WRONG_SIDE", self.ex.submit,
                           make_auth(direction="SELL", stopLossPrice="1.10005"))
        sell = make_auth(direction="SELL", stopLossPrice="1.10200", authorizationId="AUTH-20261103-SELL")
        self.assertEqual(self.ex.submit(sell, dry_run=True)["request"]["order"]["units"], "-1000")

    def test_stale_untradeable_wide_skewed_or_invalid_quotes_are_refused(self):
        p = self.fake.prices["EUR_USD"]
        cases = [("QUOTE_STALE", {"time": "2026-11-03T11:59:50.000000000Z"}),
                 ("INSTRUMENT_NOT_TRADEABLE", {"tradeable": False}),
                 ("SPREAD_TOO_WIDE", {"ask": "1.10030"}),
                 ("QUOTE_FROM_THE_FUTURE_CLOCK_SKEW", {"time": "2026-11-03T12:00:07.000000000Z"}),
                 ("QUOTE_INVALID", {"bid": "1.10020"}),
                 ("BROKER_READ_FAILED", {"time": None}),
                 ("BROKER_READ_FAILED", {"bid": "abc"})]
        original = dict(p)
        for code, over in cases:
            with self.subTest(code=code, over=over):
                p.clear()
                p.update(original, **over)
                self.assertRefused(code, self.ex.submit, make_auth())
        p.clear()
        p.update(original)
        self.ex.submit(make_auth(), dry_run=True)                                 # positive control

    def test_quote_currency_must_be_the_account_currency(self):
        self.fake.prices["EUR_GBP"] = dict(self.fake.prices["EUR_USD"])
        self.assertRefused("QUOTE_CURRENCY_IS_NOT_ACCOUNT_CURRENCY", self.ex.submit,
                           make_auth(instrument="EUR_GBP"))

    def test_existing_broker_trades_block_a_new_order(self):
        self.fake.trades.append({"id": "9", "instrument": "EUR_USD", "currentUnits": "1"})
        self.assertRefused("BROKER_ACCOUNT_HAS_OPEN_TRADES", self.ex.submit, make_auth())

    def test_a_failed_read_refuses_without_sending(self):
        for op in ("ACCOUNT_SUMMARY", "PRICING", "OPEN_TRADES"):
            with self.subTest(op=op):
                self.fake.fail_reads = {op}
                self.assertRefused("BROKER_READ_FAILED", self.ex.submit, make_auth())
        self.fake.fail_reads = set()

    def test_refusals_are_journaled_and_do_not_consume_the_authorization(self):
        auth = make_auth()
        self.fake.prices["EUR_USD"]["tradeable"] = False
        self.assertRefused("INSTRUMENT_NOT_TRADEABLE", self.ex.submit, auth)
        self.assertEqual(self.ex.journal.refusals()[-1]["authorization_id"], auth.authorization_id)
        self.fake.prices["EUR_USD"]["tradeable"] = True
        self.assertEqual(self.ex.submit(auth)["state"], jn.FILLED)


# ---- the order and its identity -----------------------------------------------------
class TestTheOrderLifecycle(Harness):
    def test_a_fill_is_journaled_write_ahead_with_complete_broker_evidence(self):
        auth = make_auth()
        seen = []
        self.fake.on_request = lambda m, p: seen.append(
            (m, self.ex.journal.intent(auth.intent_id) and self.ex.journal.intent(auth.intent_id)["state"]))
        row = self.ex.submit(auth)
        self.assertIn(("POST", jn.SUBMITTING), seen)            # SUBMITTING was on disk before the send
        self.assertEqual((row["state"], row["fill_units"], row["fill_price"]), (jn.FILLED, "1000", "1.10010"))
        self.assertTrue(row["broker_trade_id"])
        self.assertEqual([e["to_state"] for e in self.ex.journal.events(auth.intent_id)],
                         [jn.SUBMITTING, jn.FILLED, jn.OPEN_UNVERIFIED])           # M2: the fill opens a position
        order = json.loads(self.ex.journal._db.execute("SELECT bytes FROM raw WHERE sha256=?",
                                                       (row["request_sha256"],)).fetchone()[0])["order"]
        self.assertEqual((order["type"], order["timeInForce"], order["positionFill"]), ("MARKET", "FOK", "OPEN_ONLY"))
        self.assertEqual(order["stopLossOnFill"]["price"], "1.09800")
        self.assertEqual(order["priceBound"], "1.10020")
        self.assertEqual(order["clientExtensions"]["id"], auth.client_order_id)
        self.assertEqual(order["tradeClientExtensions"]["id"], auth.client_order_id)
        self.assertEqual(make_auth().client_order_id, auth.client_order_id)   # deterministic identity

    def test_cancel_and_reject_are_definitive_and_never_retried(self):
        for behavior, state in (("cancel", jn.CANCELLED), ("reject", jn.REJECTED)):
            with self.subTest(behavior=behavior):
                self.fake.submit_behavior = behavior
                auth = make_auth(authorizationId="AUTH-%s-0001" % behavior)
                posts = self.fake.posts
                self.assertEqual(self.ex.submit(auth)["state"], state)
                self.assertEqual(self.fake.posts, posts + 1)

    def test_the_stop_is_mandatory_in_the_request(self):
        body = ex.build_order_body(make_auth(), make_auth().stop_loss_price)
        del body["order"]["stopLossOnFill"]
        with self.assertRaises(OrderRefused):
            ex._require_stop(body)

    def test_a_dry_run_writes_nothing_sends_nothing_and_consumes_nothing(self):
        auth = make_auth()
        plan = self.ex.submit(auth, dry_run=True)
        self.assertEqual((plan["journalWrites"], self.fake.posts, self.ex.journal.intents()), (0, 0, []))
        self.assertEqual(plan["request"]["order"]["clientExtensions"]["id"], auth.client_order_id)
        self.assertEqual(self.ex.submit(auth)["state"], jn.FILLED)


# ---- T-DUP ----------------------------------------------------------------------
class TestDuplicateProtection(Harness):
    def test_an_open_fill_blocks_every_further_order(self):
        self.ex.submit(make_auth())
        self.fake.trades.clear()
        self.assertRefused("JOURNAL_HAS_OPEN_OR_UNRESOLVED_INTENT", self.ex.submit,
                           make_auth(authorizationId="AUTH-20261103-0002"))
        self.assertEqual(self.fake.posts, 1)

    def test_two_processes_cannot_both_reserve(self):
        a, b = make_auth(), make_auth(authorizationId="AUTH-20261103-0002")
        other = jn.Journal(os.path.join(self.dir, "journal.sqlite3"))
        try:
            self.ex.journal.reserve(a, 1000, "1.1", "100", b"{}", [])
            with self.assertRaises(jn.JournalRefused) as ctx:
                other.reserve(b, 1000, "1.1", "100", b"{}", [])
            self.assertIn("JOURNAL_HAS_OPEN_OR_UNRESOLVED_INTENT", ctx.exception.codes)
        finally:
            other.close()

    def test_reserve_itself_refuses_a_used_authorization_and_an_active_halt(self):
        a = make_auth()
        self.ex.journal.reserve(a, 1000, "1.1", "100", b"{}", [])
        self.ex.journal.transition(a.intent_id, jn.REJECTED, reason="test")
        with self.assertRaises(jn.JournalRefused) as ctx:
            self.ex.journal.reserve(a, 1000, "1.1", "100", b"{}", [])
        self.assertEqual(ctx.exception.codes, ["AUTHORIZATION_ALREADY_USED"])
        self.ex.journal.halt("test")
        with self.assertRaises(jn.JournalRefused) as ctx:
            self.ex.journal.reserve(make_auth(authorizationId="AUTH-20261103-0005"), 1000, "1.1", "100", b"{}", [])
        self.assertEqual(ctx.exception.codes, ["HALT_ACTIVE"])

    def test_the_schema_itself_refuses_a_second_order_for_one_authorization(self):
        a = make_auth()
        self.ex.journal.reserve(a, 1000, "1.1", "100", b"{}", [])
        with self.assertRaises(sqlite3.IntegrityError):
            self.ex.journal._db.execute(
                "INSERT INTO intents (intent_id, authorization_id, client_order_id, authorization_sha256,"
                " instrument, signed_units, stop_loss_price, price_bound, last_transaction_id_before,"
                " request_sha256, state, created_at, updated_at) VALUES ('x',?,'y','h','EUR_USD',1,'1','1','1','r',"
                "'SUBMITTING','t','t')", (a.authorization_id,))


# ---- T-KILL ---------------------------------------------------------------------
class TestKillSwitch(Harness):
    def test_engaged_kill_refuses_before_any_request(self):
        self.ex.kill.engage("test")
        self.assertRefused("KILL_SWITCH_ENGAGED", self.ex.submit, make_auth())
        self.assertEqual(self.fake.requests, [])

    def test_kill_engaged_after_the_checks_still_stops_the_send(self):
        auth = make_auth()
        self.fake.on_request = lambda m, p: self.ex.kill.engage("race") if p.endswith("/openTrades") else None
        self.assertRefused("KILL_SWITCH_ENGAGED_BEFORE_SEND", self.ex.submit, auth)
        self.assertEqual(self.state(auth), jn.ABORTED_BEFORE_SEND)

    def test_the_transport_refuses_a_write_under_kill_even_when_called_directly(self):
        kill = ex.KillSwitch(self.dir)
        kill.engage("direct")
        t = tp.Transport(self.config, opener=self.fake, kill_switch=kill)
        with self.assertRaises(NotSent):
            t.request("CREATE_ORDER", body={"order": {}})
        self.assertEqual(self.fake.posts, 0)
        t.request("ACCOUNT_SUMMARY")                                              # reads still allowed

    def test_a_kill_at_send_time_is_recorded_as_provably_unsent(self):
        # The executor's own two checks pass; the transport's last-moment check fires.
        class EngagedAtSend(object):
            def engaged(self):
                return True
        self.ex.close()
        transport = tp.Transport(self.config, opener=self.fake, kill_switch=EngagedAtSend())
        self.ex = ex.Executor(self.config, ad.OandaPracticeAdapter(transport), self.dir, clock=lambda: NOW)
        auth = make_auth()
        self.assertRefused("NOT_SENT", self.ex.submit, auth)
        self.assertEqual(self.state(auth), jn.ABORTED_BEFORE_SEND)

    def test_a_missing_state_dir_reads_as_engaged_and_release_needs_confirm(self):
        ghost = ex.KillSwitch(os.path.join(self.dir, "no-such-dir"))
        self.assertTrue(ghost.engaged())
        self.ex.kill.engage()
        with self.assertRaises(ValueError):
            self.ex.kill.release()
        self.ex.kill.release(confirm=True)
        self.assertFalse(self.ex.kill.engaged())


# ---- T-UNCERT and restart ----------------------------------------------------------
class TestUncertainOutcomesFailClosed(Harness):
    def submit_uncertain(self, behavior):
        self.fake.submit_behavior = behavior
        auth = make_auth()
        row = self.ex.submit(auth)
        self.assertEqual(row["state"], jn.UNCERTAIN, behavior)
        self.assertRefused("UNRESOLVED_INTENT_RECONCILE_FIRST", self.ex.submit,
                           make_auth(authorizationId="AUTH-20261103-0009"))
        return auth

    def test_committed_then_unknown_outcomes_resolve_to_FILLED_with_exactly_one_post(self):
        for behavior in ("timeout_after_commit", "http500_after_commit", "malformed_after_commit",
                         "created_only", "fill_missing_trade"):
            with self.subTest(behavior=behavior):
                self.tearDown()
                self.setUp()
                auth = self.submit_uncertain(behavior)
                if behavior == "fill_missing_trade":
                    # the broker's own transaction lacks the trade: still not provable -> stays UNCERTAIN
                    report = self.ex.reconcile()
                    self.assertEqual(self.state(auth), jn.UNCERTAIN)
                    self.assertEqual(len(report["unresolved"]), 1)
                    continue
                report = self.ex.reconcile()
                self.assertEqual(self.state(auth), jn.FILLED, report)
                self.assertEqual(self.fake.posts, 1)

    def test_an_order_that_never_reached_the_broker_resolves_to_NOT_SUBMITTED(self):
        for behavior in ("timeout_before_commit", "http500_no_commit"):
            with self.subTest(behavior=behavior):
                self.tearDown()
                self.setUp()
                auth = self.submit_uncertain(behavior)
                self.ex.reconcile()
                self.assertEqual(self.state(auth), jn.NOT_SUBMITTED)
                self.assertRefused("AUTHORIZATION_ALREADY_USED", self.ex.submit, auth)
                fresh = make_auth(authorizationId="AUTH-20261103-0003")
                self.fake.submit_behavior = "fill"
                self.assertEqual(self.ex.submit(fresh)["state"], jn.FILLED)

    def test_a_partial_fill_is_not_a_fill(self):
        auth = self.submit_uncertain("partial")
        row = self.ex.journal.intent(auth.intent_id)
        self.assertEqual((row["reason"], row["fill_units"]), ("FILL_UNITS_MISMATCH", "500"))
        self.ex.reconcile()
        self.assertEqual(self.state(auth), jn.UNCERTAIN)

    def test_unreachable_broker_leaves_it_UNCERTAIN_and_blocking(self):
        auth = self.submit_uncertain("timeout_after_commit")
        for op in ("ORDER_BY_CLIENT_ID", "TRANSACTIONS_SINCE"):
            with self.subTest(op=op):
                self.fake.fail_reads = {op}
                self.assertEqual(len(self.ex.reconcile()["unresolved"]), 1)
                self.assertEqual(self.state(auth), jn.UNCERTAIN)
        self.fake.fail_reads = set()
        self.ex.reconcile()
        self.assertEqual(self.state(auth), jn.FILLED)

    def test_reconcile_moves_nothing_when_the_broker_evidence_disagrees(self):
        cases = {
            "no fill transaction": lambda f, a: f.transactions.__setitem__(
                slice(None), [t for t in f.transactions if t["type"] != "ORDER_FILL"]),
            "order and fill name different trades": lambda f, a: f.orders[a.client_order_id].__setitem__(
                "tradeOpenedID", "4242"),
            "lookup returns another order": lambda f, a: f.orders[a.client_order_id].__setitem__(
                "clientExtensions", {"id": "MOGO-0000000000000000"}),
            "order still pending": lambda f, a: f.orders[a.client_order_id].__setitem__("state", "PENDING"),
        }
        for name, corrupt in cases.items():
            with self.subTest(case=name):
                self.tearDown()
                self.setUp()
                auth = self.submit_uncertain("timeout_after_commit")
                corrupt(self.fake, auth)
                self.ex.reconcile()
                self.assertEqual(self.state(auth), jn.UNCERTAIN)
        self.tearDown()
        self.setUp()
        auth = self.submit_uncertain("timeout_after_commit")                   # positive control
        self.ex.reconcile()
        self.assertEqual(self.state(auth), jn.FILLED)

    def test_a_fill_reported_for_another_client_id_is_not_a_fill(self):
        self.fake.fill_client_id_override = "MOGO-0000000000000000"
        auth = self.submit_uncertain("fill")
        self.assertEqual(self.ex.journal.intent(auth.intent_id)["reason"], "FILL_FOR_ANOTHER_CLIENT_ID")

    def test_absence_needs_both_sources_to_agree(self):
        auth = self.submit_uncertain("timeout_before_commit")
        self.fake.lookup_extra_transactions = [{"id": "999", "type": "MARKET_ORDER",
                                                "clientExtensions": {"id": auth.client_order_id}}]
        self.ex.reconcile()
        self.assertEqual(self.state(auth), jn.UNCERTAIN)
        self.assertEqual(self.ex.journal.intent(auth.intent_id)["reason"], "LOOKUP_ABSENT_BUT_TRANSACTIONS_PRESENT")


class TestRestart(Harness):
    def test_a_crash_between_reserve_and_send_blocks_until_reconciled_and_never_sends(self):
        auth = make_auth()
        self.ex.journal.reserve(auth, auth.signed_units, "1.10020", "100", b"{}", [])   # then "crash"
        self.ex.close()
        self.ex = self.new_executor()
        self.assertRefused("UNRESOLVED_INTENT_RECONCILE_FIRST", self.ex.submit,
                           make_auth(authorizationId="AUTH-20261103-0004"))
        self.ex.reconcile()
        self.assertEqual(self.state(auth), jn.NOT_SUBMITTED)
        self.assertEqual(self.fake.posts, 0)

    def test_a_crash_after_the_broker_committed_resolves_without_resubmitting(self):
        self.fake.submit_behavior = "timeout_after_commit"
        auth = make_auth()
        self.ex.submit(auth)
        self.ex.close()
        self.ex = self.new_executor()
        self.ex.reconcile()
        self.assertEqual(self.state(auth), jn.FILLED)
        self.assertEqual(self.fake.posts, 1)

    def test_an_unknown_MOGO_trade_at_the_broker_halts_submission(self):
        self.fake.trades.append({"id": "77", "clientExtensions": {"id": "MOGO-ffffffffffffffff"}})
        report = self.ex.reconcile()
        self.assertEqual(len(report["halted"]), 1)
        self.fake.trades.clear()
        self.assertRefused("HALT_ACTIVE", self.ex.submit, make_auth())
        halt = self.ex.journal.active_halts()[0]
        for who, why in (("", "investigated"), ("operator", ""), (None, None)):
            with self.subTest(who=who, why=why), self.assertRaises(ValueError):
                self.ex.journal.clear_halt(halt["seq"], who, why)
        self.assertEqual(len(self.ex.journal.active_halts()), 1)
        self.ex.journal.clear_halt(halt["seq"], "operator", "investigated")
        self.assertEqual(self.ex.submit(make_auth())["state"], jn.FILLED)


# ---- journal integrity and mode separation -------------------------------------------
class TestJournalAndModes(Harness):
    def test_history_is_append_only_and_transitions_are_validated(self):
        auth = make_auth()
        self.ex.submit(auth)
        self.ex.journal.record_refusal("AUTH-X", ["TEST"])
        self.ex.journal.halt("test halt")
        db = self.ex.journal._db
        for table in ("events", "raw", "refusals", "halts", "intents"):     # non-vacuous: rows exist
            self.assertGreater(db.execute("SELECT COUNT(*) FROM %s" % table).fetchone()[0], 0)
        for sql in ("UPDATE events SET reason='x'", "DELETE FROM events", "DELETE FROM intents",
                    "DELETE FROM raw", "UPDATE refusals SET codes='[]'", "DELETE FROM halts"):
            with self.subTest(sql=sql), self.assertRaises(sqlite3.DatabaseError):
                db.execute(sql)
        with self.assertRaises(ValueError):
            self.ex.journal.transition(auth.intent_id, jn.CANCELLED)
        with self.assertRaises(ValueError):
            self.ex.journal.transition(auth.intent_id, jn.FILLED, bogus_field=1)

    def test_state_may_not_live_with_research_or_simulated_evidence(self):
        for rel in ("docs", os.path.join("docs", "trader-intelligence", "evidence"), "evidence"):
            target = os.path.join(REPO_ROOT, rel)
            if not os.path.isdir(target):
                continue
            with self.subTest(dir=rel), self.assertRaises(PracticeExecutionError):
                ex.check_state_dir(target)
        self.assertEqual(ex.check_state_dir(self.dir), os.path.realpath(self.dir))   # positive control

    def test_the_package_does_not_touch_the_research_corpus_or_the_simulator(self):
        for dp, _, fs in os.walk(EXEC_DIR):
            for f in fs:
                if f.endswith(".py"):
                    text = read_text(os.path.join(dp, f))
                    with self.subTest(file=f):
                        for needle in ("trader_intelligence", "trade_observation", "index.html",
                                       "import_mogo_observations"):
                            self.assertNotIn(needle, text)
        self.assertEqual(cfg.MODE, "BROKER_PRACTICE")
        self.assertEqual(ex.ORDER_TAG, "MOGO_BROKER_PRACTICE")


# ---- T-SECRET -----------------------------------------------------------------------
class TestTheTokenNeverLeaks(Harness):
    def test_the_token_is_absent_from_every_output_and_artifact(self):
        captured, errors = io.StringIO(), []
        with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
            scenarios = [("fill", "A"), ("reject", "B"), ("timeout_after_commit", "C"),
                         ("timeout_before_commit", "D")]
            for behavior, tag in scenarios:
                self.fake.submit_behavior = behavior
                self.fake.trades.clear()
                try:
                    self.ex.submit(make_auth(authorizationId="AUTH-SECRET-000" + tag))
                except PracticeExecutionError as exc:
                    errors.append(repr(exc) + str(exc))
                self.ex.reconcile()
            self.fake.fail_reads = {"PRICING"}
            for _ in range(2):
                try:
                    self.ex.submit(make_auth(authorizationId="AUTH-SECRET-000E"))
                except PracticeExecutionError as exc:
                    errors.append(repr(exc) + str(exc))
            print(json.dumps(self.ex.status()))
            cli.main(["status", "--state-dir", self.dir])
            print(repr(self.config), str(self.config.token), "%s" % self.config.token)
        self.assertTrue(errors)                                                     # failures were exercised
        self.assertTrue(any("Bearer " + TOKEN == h["Authorization"] for h in self.fake.seen_headers))
        with open(os.path.join(self.dir, "journal.sqlite3"), "rb") as handle:
            db_bytes = handle.read()
        for name, blob in (("stdout/stderr", captured.getvalue()), ("exceptions", "".join(errors)),
                           ("journal file", db_bytes.decode("latin-1"))):
            with self.subTest(where=name):
                self.assertNotIn(TOKEN, blob)
                self.assertNotIn(TOKEN[4:], blob)

    def test_a_secret_cannot_be_displayed_or_pickled(self):
        s = cfg.Secret(TOKEN)
        for shown in (repr(s), str(s), "%s" % s, "{}".format(s), repr(self.config)):
            self.assertNotIn(TOKEN, shown)
        with self.assertRaises(TypeError):
            pickle.dumps(s)


# ---- the CLI ------------------------------------------------------------------------
class TestTheOfflineCli(Harness):
    def run_cli(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(list(argv))
        return code, out.getvalue()

    def test_kill_status_release_and_check_authorization(self):
        self.assertEqual(self.run_cli("kill", "--state-dir", self.dir)[0], 0)
        self.assertTrue(json.loads(self.run_cli("status", "--state-dir", self.dir)[1])["killSwitch"])
        self.assertEqual(self.run_cli("release-kill", "--state-dir", self.dir)[0], 2)
        self.assertTrue(self.ex.kill.engaged())
        self.assertEqual(self.run_cli("release-kill", "--state-dir", self.dir, "--confirm")[0], 0)
        self.assertFalse(self.ex.kill.engaged())
        path = os.path.join(self.dir, "auth.json")
        with open(path, "w") as handle:
            json.dump(auth_data(), handle)
        code, out = self.run_cli("check-authorization", path)
        self.assertEqual((code, json.loads(out)["clientOrderId"]), (0, make_auth().client_order_id))
        with open(path, "w") as handle:
            json.dump(auth_data(units=5000), handle)
        self.assertEqual(self.run_cli("check-authorization", path)[0], 2)

    def test_there_is_no_submit_command(self):
        with self.assertRaises(SystemExit):
            with contextlib.redirect_stderr(io.StringIO()):
                cli.main(["submit", "--state-dir", self.dir])


if __name__ == "__main__":
    unittest.main()

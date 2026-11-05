#!/usr/bin/env python3
"""M3 offline: the read-only boundary, and the preflight's sanitised report, with zero network.

The boundary under test (execution/oanda_practice_m3/readonly.py) is the only
code that can open a socket to the broker. Every prohibited request must be
refused BEFORE a socket exists, and the proof is counted two ways: the socket
module's connect/create_connection/getaddrinfo are replaced by recorders that
raise, and an interpreter audit hook records every socket event. The positive
control (a permitted GET through the REAL http.client stack) shows both
recorders do see an attempt, so a zero is a measured zero.

The preflight runs against tests/execution/fake_oanda.py behind a fake
connection; its report must carry no token, no full account id and no balance.
"""
import json
import os
import socket
import ssl
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
EXEC_DIR = os.path.join(REPO_ROOT, "execution")
sys.path.insert(0, EXEC_DIR)
sys.path.insert(0, HERE)

from oanda_practice import config as cfg            # noqa: E402
from oanda_practice import transport as tp          # noqa: E402
from oanda_practice.errors import NotSent, SendUncertain, TransportRefused  # noqa: E402
from oanda_practice_m3 import preflight             # noqa: E402
from oanda_practice_m3 import readonly as ro        # noqa: E402
from fake_oanda import FakeOanda                    # noqa: E402
import mogo_practice_preflight as cli               # noqa: E402

ACCOUNT = "101-004-1234567-001"
OTHER_ACCOUNT = "101-004-7654321-001"
TOKEN = "tok-" + "0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e"
BASE = "https://" + cfg.PRACTICE_HOST
GOOD_URL = BASE + "/v3/accounts/%s/summary" % ACCOUNT
HEADERS = {"Authorization": "Bearer " + TOKEN}

# ---- the network guard --------------------------------------------------------
NET_ATTEMPTS = []
_ORIGINALS = {}
_AUDIT_ARMED = False


def _blocked(name):
    def guard(*args, **kwargs):
        NET_ATTEMPTS.append(name)
        raise OSError("network blocked by test guard: %s" % name)
    return guard


def _audit(event, args):
    if event.startswith("socket.") and _AUDIT_ARMED:
        NET_ATTEMPTS.append("audit:" + event)


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
def config():
    return cfg.config_from_mapping({"accountId": ACCOUNT, "token": TOKEN})


class FakeConnection(object):
    """Stands in for http.client.HTTPSConnection; serves a FakeOanda, never opens a socket."""

    instances = []

    def __init__(self, host, port, timeout=None, context=None, handler=None, redirect=False):
        self.host, self.port, self.context = host, port, context
        self.tunnel = None
        self.requests = []
        self.handler = handler
        self.redirect = redirect
        self.closed = False
        FakeConnection.instances.append(self)

    def set_tunnel(self, host, port=None, headers=None):
        self.tunnel = (host, port, headers)

    def request(self, method, target, headers=None):
        self.requests.append((method, target, dict(headers or {})))

    def getresponse(self):
        method, target, headers = self.requests[-1]
        if self.redirect:
            return FakeResponse(302, b"")
        status, body = self.handler(method, BASE + target, headers, None, 10)
        return FakeResponse(status, body)

    def close(self):
        self.closed = True


class FakeResponse(object):
    def __init__(self, status, body):
        self.status, self._body = status, body

    def read(self, n=-1):
        return self._body if n < 0 else self._body[:n]


def factory(handler=None, redirect=False):
    def make(host, port, timeout=None, context=None):
        return FakeConnection(host, port, timeout, context, handler=handler, redirect=redirect)
    return make


def seeded_fake():
    """A small account history: CREATE (1), a funding transfer (2), one financing (3)."""
    fake = FakeOanda(ACCOUNT)
    fake.next_id = 1
    fake.transactions.append({"id": "1", "type": "CREATE"})
    fake.balance = cfg_decimal("0")
    fake.transfer("1000")
    fake.daily_financing("-0.5")
    return fake


def cfg_decimal(text):
    from decimal import Decimal
    return Decimal(text)


class Base(unittest.TestCase):
    def setUp(self):
        self.net_before = len(NET_ATTEMPTS)
        FakeConnection.instances = []

    def tearDown(self):
        self.assertEqual(NET_ATTEMPTS[self.net_before:], [], "a test attempted network access")

    def opener(self, **kw):
        kw.setdefault("connection_factory", factory(handler=FakeOanda(ACCOUNT)))
        return ro.ReadOnlyHttpsOpener(ACCOUNT, **kw)


# ---- the guard itself ---------------------------------------------------------
class TestTheGuardSeesARealAttempt(unittest.TestCase):
    def test_POSITIVE_CONTROL_a_permitted_GET_through_real_http_client_reaches_the_socket_layer(self):
        before = len(NET_ATTEMPTS)
        opener = ro.ReadOnlyHttpsOpener(ACCOUNT)          # the real HTTPSConnection
        with self.assertRaises(OSError):
            opener("GET", GOOD_URL, dict(HEADERS), None, 1)
        attempts = NET_ATTEMPTS[before:]
        del NET_ATTEMPTS[before:]
        self.assertTrue(attempts, "the guard did not see a permitted GET: zero counts below would be vacuous")
        self.assertEqual(opener.sent, 1)


# ---- barrier 2: the opener ----------------------------------------------------
class TestTheOpenerRefusesBeforeAnySocket(Base):
    def assert_refused_with_real_stack(self, method, url, body=None, headers=None):
        opener = ro.ReadOnlyHttpsOpener(ACCOUNT)          # the real stack: any slip would reach a socket
        with self.assertRaises(ro.ReadOnlyRefused):
            opener(method, url, dict(headers or HEADERS), body, 1)
        self.assertEqual(opener.sent, 0)

    def test_write_methods_open_zero_sockets(self):
        for method in ("POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "get", "TRACE"):
            with self.subTest(method=method):
                self.assert_refused_with_real_stack(method, GOOD_URL, body=b"{}" if method in ("POST", "PUT", "PATCH") else None)

    def test_a_GET_with_a_body_is_refused(self):
        self.assert_refused_with_real_stack("GET", GOOD_URL, body=b"{}")

    def test_other_hosts_schemes_ports_and_userinfo_are_refused(self):
        bad = ["http://%s/v3/accounts/%s/summary" % (cfg.PRACTICE_HOST, ACCOUNT),
               "https://example.com/v3/accounts/%s/summary" % ACCOUNT,
               "https://%s:8443/v3/accounts/%s/summary" % (cfg.PRACTICE_HOST, ACCOUNT),
               "https://%s:443/v3/accounts/%s/summary" % (cfg.PRACTICE_HOST, ACCOUNT),
               "https://user@%s/v3/accounts/%s/summary" % (cfg.PRACTICE_HOST, ACCOUNT),
               "https://%s.evil.example/v3/accounts/%s/summary" % (cfg.PRACTICE_HOST, ACCOUNT),
               "https://api-fx" + "trade.oanda.com/v3/accounts/%s/summary" % ACCOUNT,
               GOOD_URL + "#frag", None]
        for url in bad:
            with self.subTest(url=url):
                self.assert_refused_with_real_stack("GET", url)

    def test_another_account_or_a_path_escape_is_refused(self):
        for path in ("/v3/accounts/%s/summary" % OTHER_ACCOUNT, "/v3/accounts", "/v3/users/x",
                     "/v3/accounts/%s/../%s/summary" % (ACCOUNT, OTHER_ACCOUNT),
                     "/v3/accounts/%s//summary" % ACCOUNT,
                     "/v3/accounts/%s-002/summary" % ACCOUNT):
            with self.subTest(path=path):
                self.assert_refused_with_real_stack("GET", BASE + path)

    def test_header_injection_is_refused(self):
        self.assert_refused_with_real_stack("GET", GOOD_URL, headers={"X": "a\r\nHost: evil"})

    def test_refusal_is_NotSent_and_names_no_secret(self):
        opener = self.opener()
        with self.assertRaises(NotSent) as caught:
            opener("POST", GOOD_URL, dict(HEADERS), b"{}", 1)
        self.assertNotIn(TOKEN, str(caught.exception))
        self.assertNotIn(ACCOUNT, str(caught.exception))
        self.assertEqual(FakeConnection.instances, [])

    def test_a_redirect_is_never_followed(self):
        opener = ro.ReadOnlyHttpsOpener(ACCOUNT, connection_factory=factory(redirect=True))
        with self.assertRaises(ro.RedirectRefused):
            opener("GET", GOOD_URL, dict(HEADERS), None, 1)
        self.assertEqual(len(FakeConnection.instances), 1)
        self.assertEqual(len(FakeConnection.instances[0].requests), 1)
        self.assertTrue(FakeConnection.instances[0].closed)

    def test_a_permitted_GET_goes_to_the_practice_host_on_443_with_path_only(self):
        opener = self.opener()
        status, body = opener("GET", GOOD_URL, dict(HEADERS), None, 1)
        self.assertEqual(status, 200)
        conn = FakeConnection.instances[0]
        self.assertEqual((conn.host, conn.port, conn.tunnel), (cfg.PRACTICE_HOST, 443, None))
        self.assertEqual(conn.requests[0][:2], ("GET", "/v3/accounts/%s/summary" % ACCOUNT))

    def test_tls_verifies_certificate_and_hostname(self):
        opener = self.opener()
        opener("GET", GOOD_URL, dict(HEADERS), None, 1)
        ctx = FakeConnection.instances[0].context
        self.assertEqual(ctx.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(ctx.check_hostname)


class TestTheProxyIsLoopbackOnlyAndTunnelled(Base):
    def test_non_loopback_or_non_http_proxies_are_refused(self):
        for url in ("http://10.0.0.1:3128", "http://proxy.example:3128", "https://localhost:3128",
                    "http://localhost", "socks5://127.0.0.1:1080"):
            with self.subTest(url=url):
                with self.assertRaises(ro.ProxyRefused):
                    ro.ReadOnlyHttpsOpener(ACCOUNT, proxy_url=url)

    def test_a_loopback_proxy_carries_only_a_CONNECT_to_the_practice_host(self):
        opener = self.opener(proxy_url="http://u:p@localhost:50065")
        self.assertTrue(opener.uses_proxy)
        opener("GET", GOOD_URL, dict(HEADERS), None, 1)
        conn = FakeConnection.instances[0]
        self.assertEqual((conn.host, conn.port), ("localhost", 50065))
        host, port, tunnel_headers = conn.tunnel
        self.assertEqual((host, port), (cfg.PRACTICE_HOST, 443))
        self.assertEqual(set(tunnel_headers), {"Proxy-Authorization"})
        self.assertNotIn(TOKEN, json.dumps(tunnel_headers))
        self.assertEqual(conn.requests[0][2]["Authorization"], "Bearer " + TOKEN)


# ---- barrier 1: the transport -------------------------------------------------
class TestTheReadOnlyTransport(Base):
    def test_write_operations_are_refused_before_the_opener(self):
        t = ro.ReadOnlyTransport(config(), self.opener())
        for op, kw in (("CREATE_ORDER", {"body": {"order": {}}}),
                       ("CLOSE_TRADE", {"body": {"units": "ALL"}, "trade_id": "5"})):
            with self.subTest(op=op):
                with self.assertRaises(ro.ReadOnlyRefused):
                    t.request(op, **kw)
        self.assertEqual(FakeConnection.instances, [])

    def test_write_operations_die_at_the_transport_even_if_the_opener_would_accept(self):
        # Barrier 2 disabled on purpose: an opener whose check lets everything through.
        class Permissive(ro.ReadOnlyHttpsOpener):
            def check(self, method, url, headers, body):
                return __import__("urllib.parse").parse.urlsplit(url)
        opener = Permissive(ACCOUNT, connection_factory=factory(handler=FakeOanda(ACCOUNT)))
        t = ro.ReadOnlyTransport(config(), opener)
        for op, kw in (("CREATE_ORDER", {"body": {"order": {}}}),
                       ("CLOSE_TRADE", {"body": {"units": "ALL"}, "trade_id": "5"})):
            with self.subTest(op=op):
                with self.assertRaises(ro.ReadOnlyRefused):
                    t.request(op, **kw)
        self.assertEqual((opener.sent, FakeConnection.instances), (0, []))

    def test_every_read_operation_is_a_GET_in_the_core_table(self):
        self.assertTrue(ro.READ_OPERATIONS)
        for op in ro.READ_OPERATIONS:
            with self.subTest(op=op):
                self.assertEqual(tp.OPERATIONS[op][0], "GET")
                self.assertFalse(tp.OPERATIONS[op][2])

    def test_a_write_reaching_the_opener_still_dies_there(self):
        # Barrier 1 bypassed on purpose: the core Transport with the read-only opener.
        t = tp.Transport(config(), opener=self.opener())
        with self.assertRaises(NotSent):
            t.request("CREATE_ORDER", body={"order": {}})
        self.assertEqual(FakeConnection.instances, [])

    def test_the_account_cannot_be_overridden(self):
        t = ro.ReadOnlyTransport(config(), self.opener())
        with self.assertRaises(TransportRefused):
            t.request("ACCOUNT_SUMMARY", account=OTHER_ACCOUNT)
        self.assertEqual(FakeConnection.instances, [])

    def test_only_the_read_only_opener_is_accepted(self):
        for opener in (tp.NetworkDisabledOpener(), FakeOanda(ACCOUNT), None):
            with self.subTest(opener=type(opener).__name__):
                with self.assertRaises(TransportRefused):
                    ro.ReadOnlyTransport(config(), opener)

    def test_a_redirect_surfaces_as_a_boundary_stop_in_the_preflight(self):
        t = ro.ReadOnlyTransport(config(), ro.ReadOnlyHttpsOpener(ACCOUNT, connection_factory=factory(redirect=True)))
        with self.assertRaises(SendUncertain):
            t.request("ACCOUNT_SUMMARY")
        report = preflight.run(t, ACCOUNT)
        self.assertEqual(report["stop"], "BOUNDARY_RedirectRefused")
        self.assertEqual(report["requests"], 1)


# ---- the preflight ------------------------------------------------------------
class TestThePreflight(Base):
    def run_preflight(self, fake, **kw):
        opener = ro.ReadOnlyHttpsOpener(ACCOUNT, connection_factory=factory(handler=fake))
        report = preflight.run(ro.ReadOnlyTransport(config(), opener), ACCOUNT, **kw)
        return report, opener

    def test_a_clean_account_passes_with_GETs_only_and_at_most_seven_requests(self):
        fake = seeded_fake()
        report, opener = self.run_preflight(fake, now=lambda: __import__("datetime").datetime(
            2026, 11, 3, 12, 0, 1, tzinfo=__import__("datetime").timezone.utc))
        self.assertIsNone(report["stop"], report)
        self.assertTrue(report["ok"], [c for c in report["checks"] if not c["ok"]])
        self.assertEqual(report["blockers"], [])
        self.assertEqual({m for m, _p in fake.requests}, {"GET"})
        self.assertEqual(report["requests"], opener.sent)
        self.assertLessEqual(opener.sent, 7)
        self.assertEqual(fake.posts + fake.close_puts, 0)
        h = report["observed"]["history"]
        self.assertEqual((h["returned"], h["expected_if_uncapped"], h["capped_or_paged"]), (2, 2, False))
        self.assertEqual(h["sign_model"]["DAILY_FINANCING"]["agreed"], 1)
        self.assertEqual(report["observed"]["pricing"]["quote_age_seconds"], 1.0)

    def test_the_report_carries_no_token_account_id_or_balance(self):
        fake = seeded_fake()
        report, _ = self.run_preflight(fake)
        text = json.dumps(report)
        for secret in (TOKEN, ACCOUNT, "1234567", "999.5", "1000.0000", "1.10000", "1.10010"):
            with self.subTest(secret=secret):
                self.assertNotIn(secret, text)
        self.assertEqual(report["account"], "101-***-****-001")

    def test_rejected_credentials_stop_after_one_request(self):
        def rejecting(method, url, headers, body, timeout):
            return 401, b'{"errorMessage":"Insufficient authorization to perform request."}'
        report, opener = self.run_preflight(rejecting)
        self.assertEqual((report["stop"], report["requests"], opener.sent), ("CREDENTIALS_REJECTED", 1, 1))
        self.assertEqual(report["stop_http_status"], 401)
        self.assertFalse(report["ok"])

    def test_a_summary_for_another_account_stops_after_one_request(self):
        fake = seeded_fake()
        fake.summary_account_id = OTHER_ACCOUNT
        report, opener = self.run_preflight(fake)
        self.assertEqual((report["stop"], opener.sent), ("NOT_THE_CONFIGURED_PRACTICE_ACCOUNT", 1))

    def test_a_wrong_sign_model_is_detected(self):
        fake = seeded_fake()
        fake.balance_report_skew = cfg_decimal("0.01")
        fake.daily_financing("-0.25")
        report, _ = self.run_preflight(fake)
        self.assertFalse(report["ok"])
        self.assertIn("sign model agrees on every checkable balance change",
                      [c["check"] for c in report["checks"] if not c["ok"]])

    def test_a_capped_history_is_reported_as_a_blocker(self):
        fake = seeded_fake()
        fake.hide_transaction_ids = {"3"}
        report, _ = self.run_preflight(fake)
        self.assertIn("TRANSACTIONS_SINCE_RETURNED_1_OF_2", report["blockers"])
        self.assertTrue(report["observed"]["history"]["capped_or_paged"])

    def test_a_non_USD_account_is_a_blocker_for_EUR_USD(self):
        fake = seeded_fake()
        fake.currency = "EUR"
        report, _ = self.run_preflight(fake)
        self.assertIn("ACCOUNT_CURRENCY_EUR_IS_NOT_THE_QUOTE_CURRENCY_OF_EUR_USD", report["blockers"])

    def test_the_missing_order_resolves_ABSENT_from_both_sources(self):
        report, _ = self.run_preflight(seeded_fake())
        by = {c["check"]: c for c in report["checks"]}
        self.assertTrue(by["M2 resolution classifies the missing order ABSENT on real data"]["ok"])
        self.assertEqual(report["observed"]["missing_order_lookup"]["status"], 404)


class TestTheCommand(Base):
    def test_without_A2_it_refuses_before_reading_credentials(self):
        original = cfg.load_config
        cfg.load_config = lambda *a, **k: self.fail("credentials were read without A2")
        try:
            import contextlib
            import io
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = cli.main(["--authorization", "A3"])
        finally:
            cfg.load_config = original
        self.assertEqual(rc, 2)
        self.assertIn("NOT_AUTHORIZED", out.getvalue())

    def test_an_explicit_cafile_still_verifies_certificate_and_hostname(self):
        bundle = ssl.get_default_verify_paths().openssl_cafile
        for cafile in [None] + ([p for p in ("/etc/ssl/cert.pem",) if os.path.exists(p)]):
            with self.subTest(cafile=cafile):
                ctx = ro.verifying_context(cafile)
                self.assertEqual(ctx.verify_mode, ssl.CERT_REQUIRED)
                self.assertTrue(ctx.check_hostname)
        self.assertTrue(bundle)

    def test_only_the_readonly_module_imports_a_network_library(self):
        import ast
        net = {"socket", "ssl", "http", "urllib", "requests", "asyncio", "subprocess"}
        pkg = os.path.join(EXEC_DIR, "oanda_practice_m3")
        files = [f for f in os.listdir(pkg) if f.endswith(".py")]
        self.assertGreaterEqual(len(files), 3)
        for f in files:
            with open(os.path.join(pkg, f), encoding="utf-8") as handle:
                tree = ast.parse(handle.read())
            names = {(a.name if isinstance(n, ast.Import) else n.module or "").split(".")[0]
                     for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom)) for a in
                     (n.names if isinstance(n, ast.Import) else [n])}
            with self.subTest(file=f):
                if f == "readonly.py":
                    self.assertTrue({"http", "ssl"} <= names)
                else:
                    self.assertFalse(names & net, names & net)


if __name__ == "__main__":
    unittest.main()

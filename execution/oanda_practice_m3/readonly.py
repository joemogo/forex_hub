"""The read-only opener and transport: GET to the practice host for the configured account, nothing else.

THREE BARRIERS, each checked BEFORE any socket is created:

  1. ReadOnlyTransport refuses every operation outside READ_OPERATIONS (so
     CREATE_ORDER and CLOSE_TRADE never reach url_for, let alone an opener);
  2. ReadOnlyHttpsOpener.check() refuses any method other than GET, any body,
     any URL that is not https on the practice host with no port, userinfo or
     fragment, and any path that is not under /v3/accounts/<configured account>/;
  3. the core Transport's own allow-list, parameter shapes and host re-assert
     (unchanged from M1).

Every refusal raises ReadOnlyRefused, a NotSent: it is provable that nothing
left the process.

REDIRECTS are never followed. http.client does not follow them, and any 3xx
status raises RedirectRefused instead of being returned.

TLS: the default context (certificate and hostname verification on), always
to the practice host. A proxy is used only when one is passed in explicitly
and it is http on a loopback address. The request goes through it as a CONNECT
tunnel, so TLS stays end-to-end to the practice host and the proxy never sees
the request, the token or the response. HTTPS_PROXY is never read implicitly.

No message raised here carries a URL, header, token, account id or body.
"""
import base64
import http.client
import ssl
from urllib.parse import urlsplit, unquote

from oanda_practice import config as cfg
from oanda_practice import transport as tp
from oanda_practice.errors import NotSent, TransportRefused

#: The only operations M3 can issue. All are GET in tp.OPERATIONS; that is re-checked below.
READ_OPERATIONS = frozenset(("ACCOUNT_SUMMARY", "PRICING", "OPEN_TRADES", "ORDER_BY_CLIENT_ID",
                             "TRANSACTIONS_SINCE", "TRADE_DETAILS", "INSTRUMENT_DETAILS"))
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
_LOOPBACK = ("localhost", "127.0.0.1", "::1")


class ReadOnlyRefused(NotSent):
    """Refused by the read-only boundary before any socket. Nothing was sent."""


class RedirectRefused(Exception):
    """The broker answered with a redirect; it was not followed."""


class ProxyRefused(Exception):
    """The proxy given is not an http proxy on a loopback address."""


def parse_proxy(proxy_url):
    """(host, port, proxy_authorization_header_or_None) for a loopback http proxy; None for no proxy."""
    if proxy_url is None:
        return None
    parts = urlsplit(proxy_url)
    if parts.scheme != "http" or parts.hostname not in _LOOPBACK or parts.port is None:
        raise ProxyRefused("only an http proxy on a loopback address with an explicit port is allowed")
    auth = None
    if parts.username is not None:
        pair = "%s:%s" % (unquote(parts.username), unquote(parts.password or ""))
        auth = "Basic " + base64.b64encode(pair.encode("utf-8")).decode("ascii")
    return parts.hostname, parts.port, auth


def verifying_context(cafile):
    """The default context, optionally trusting an explicit CA bundle. Never unverified."""
    context = ssl.create_default_context(cafile=cafile) if cafile else ssl.create_default_context()
    if context.verify_mode != ssl.CERT_REQUIRED or not context.check_hostname:
        raise ProxyRefused("refusing an unverified TLS context")
    return context


class ReadOnlyHttpsOpener(object):
    """An opener for tp.Transport that can only GET the configured practice account."""

    def __init__(self, account_id, proxy_url=None, connection_factory=None, ssl_context=None):
        if not isinstance(account_id, str) or not account_id:
            raise ReadOnlyRefused("the read-only opener needs the configured account")
        self._prefix = "/v3/accounts/%s/" % account_id
        self._proxy = parse_proxy(proxy_url)
        self._factory = connection_factory or http.client.HTTPSConnection
        self._context = ssl_context or ssl.create_default_context()
        self.sent = 0

    @property
    def uses_proxy(self):
        return self._proxy is not None

    def check(self, method, url, headers, body):
        """Raise ReadOnlyRefused unless this is a body-less GET to the configured practice account."""
        if method != "GET":
            raise ReadOnlyRefused("only GET is permitted (got a %s)" % (method if method in (
                "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS") else "non-GET method"))
        if body is not None:
            raise ReadOnlyRefused("a read-only request carries no body")
        return self.check_target(url, headers)

    def check_target(self, url, headers):
        """The practice host, the configured account, clean headers. Shared with the M4 A3 opener."""
        if not isinstance(url, str):
            raise ReadOnlyRefused("the request has no URL")
        parts = urlsplit(url)
        if parts.scheme != "https" or parts.hostname != cfg.PRACTICE_HOST or parts.port is not None \
                or parts.username is not None or parts.password is not None or parts.fragment \
                or parts.netloc != cfg.PRACTICE_HOST:
            raise ReadOnlyRefused("the request is not to the practice host")
        if not parts.path.startswith(self._prefix) or ".." in parts.path or "//" in parts.path:
            raise ReadOnlyRefused("the request is not for the configured account")
        if not isinstance(headers, dict) or any("\r" in str(k) + str(v) or "\n" in str(k) + str(v)
                                               for k, v in headers.items()):
            raise ReadOnlyRefused("malformed headers")
        return parts

    def __call__(self, method, url, headers, body, timeout):
        parts = self.check(method, url, headers, body)
        return self._send("GET", parts, headers, None, timeout)

    def _send(self, method, parts, headers, body, timeout):
        """Only ever called after a check; the method and body are the checked ones."""
        target = parts.path + ("?" + parts.query if parts.query else "")
        if self._proxy is None:
            conn = self._factory(cfg.PRACTICE_HOST, 443, timeout=timeout, context=self._context)
        else:
            host, port, auth = self._proxy
            conn = self._factory(host, port, timeout=timeout, context=self._context)
            conn.set_tunnel(cfg.PRACTICE_HOST, 443,
                            headers={"Proxy-Authorization": auth} if auth else None)
        try:
            self.sent += 1
            conn.request(method, target, body=body, headers=headers)
            response = conn.getresponse()
            status = response.status
            if 300 <= status < 400:
                raise RedirectRefused("the broker answered %d; redirects are never followed" % status)
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise RedirectRefused("response larger than the read-only cap")
            return status, raw
        finally:
            conn.close()


class ReadOnlyTransport(tp.Transport):
    """tp.Transport restricted to READ_OPERATIONS, and only with a ReadOnlyHttpsOpener."""

    def __init__(self, config, opener, timeout=tp.DEFAULT_TIMEOUT_SECONDS):
        if not isinstance(opener, ReadOnlyHttpsOpener):
            raise TransportRefused("the M3 transport takes only the read-only opener")
        super().__init__(config, opener=opener, kill_switch=None, timeout=timeout)

    def request(self, operation, body=None, **params):
        if operation not in READ_OPERATIONS or tp.OPERATIONS.get(operation, ("",))[0] != "GET" \
                or body is not None:
            raise ReadOnlyRefused("operation %r is not a read" % (operation,))
        return super().request(operation, body=body, **params)

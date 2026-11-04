"""The only place a broker request is formed. Modelled on mogo_platform's
connector_transport: callers name an OPERATION, never a URL.

WHAT IT ENFORCES
  * an operation allow-list: method and path template are data, below;
  * every path parameter is shape-checked before it is substituted;
  * the URL is the practice base URL plus that path, and is re-parsed and
    asserted to be https on the practice host immediately before use;
  * a write operation re-checks the kill switch at the last moment;
  * the token reaches the Authorization header and nowhere else. No error
    message carries a URL, header or body.

THE OPENER is injected: opener(method, url, headers, body_bytes, timeout)
returns (status, body_bytes), raises NotSent when it can prove nothing left the
process, and anything else it raises means the outcome is unknown. M1 ships no
network opener: NetworkDisabledOpener raises NotSent for every request, so the
package cannot reach any host. A real opener is M3 and needs operator
authorization A2.
"""
import json
import re
from urllib.parse import quote, urlsplit   # parsing only; urllib.request is never imported

from . import config as cfg
from .errors import NotSent, SendUncertain, TransportRefused

_PARAM_SHAPES = {
    "account": re.compile(r"^[0-9]{3}-[0-9]{3}-[0-9]{5,12}-[0-9]{3}$"),
    "instrument": re.compile(r"^[A-Z]{3}_[A-Z]{3}$"),
    "client_id": re.compile(r"^MOGO-[0-9a-f]{16}$"),
    "transaction_id": re.compile(r"^[0-9]{1,18}$"),
}

#: operation -> (method, path template, is_write). Nothing outside this table can be sent.
OPERATIONS = {
    "ACCOUNT_SUMMARY": ("GET", "/v3/accounts/{account}/summary", False),
    "PRICING": ("GET", "/v3/accounts/{account}/pricing?instruments={instrument}", False),
    "OPEN_TRADES": ("GET", "/v3/accounts/{account}/openTrades", False),
    "ORDER_BY_CLIENT_ID": ("GET", "/v3/accounts/{account}/orders/@{client_id}", False),
    "TRANSACTIONS_SINCE": ("GET", "/v3/accounts/{account}/transactions/sinceid?id={transaction_id}", False),
    "CREATE_ORDER": ("POST", "/v3/accounts/{account}/orders", True),
}

DEFAULT_TIMEOUT_SECONDS = 10


class NetworkDisabledOpener(object):
    """M1's only real opener. It sends nothing, ever."""

    def __call__(self, method, url, headers, body, timeout):
        raise NotSent("network access is disabled in M1")


class RecordingOpener(object):
    """For dry runs: records what WOULD be sent and refuses to send it."""

    def __init__(self):
        self.recorded = []

    def __call__(self, method, url, headers, body, timeout):
        self.recorded.append({"method": method, "url": url, "body": body})
        raise NotSent("dry run: request recorded, not sent")


class Response(object):
    __slots__ = ("status", "body", "data")

    def __init__(self, status, body):
        self.status = status
        self.body = body
        try:
            self.data = json.loads(body.decode("utf-8")) if body else None
        except (UnicodeDecodeError, ValueError):
            self.data = None


class Transport(object):
    def __init__(self, config, opener=None, kill_switch=None, timeout=DEFAULT_TIMEOUT_SECONDS):
        if not isinstance(config, cfg.PracticeConfig):
            raise TransportRefused("transport requires a PracticeConfig")
        self._config = config
        self._opener = opener or NetworkDisabledOpener()
        self._kill = kill_switch
        self._timeout = timeout

    def url_for(self, operation, **params):
        if operation not in OPERATIONS:
            raise TransportRefused("operation %r is not allowed" % (operation,))
        method, template, is_write = OPERATIONS[operation]
        if "account" in params:
            raise TransportRefused("the account is fixed by configuration")
        params = dict(params, account=self._config.account_id)
        names = re.findall(r"{(\w+)}", template)
        if set(params) != set(names):
            raise TransportRefused("%s takes exactly %s" % (operation, sorted(names)))
        for name in names:
            value = params[name]
            if not isinstance(value, str) or not _PARAM_SHAPES[name].match(value):
                raise TransportRefused("%s parameter %r has the wrong shape" % (operation, name))
        path = template.format(**{n: quote(params[n], safe="") for n in names})
        url = cfg.PRACTICE_BASE_URL + path
        parts = urlsplit(url)
        if parts.scheme != "https" or parts.hostname != cfg.PRACTICE_HOST or parts.port is not None:
            raise TransportRefused("refusing a request that is not to the practice host")
        return method, url, is_write

    def request(self, operation, body=None, **params):
        method, url, is_write = self.url_for(operation, **params)
        if is_write != (body is not None):
            raise TransportRefused("%s %s a body" % (operation, "requires" if is_write else "takes no"))
        payload = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8") if is_write else None
        if is_write and self._kill is not None and self._kill.engaged():
            raise NotSent("kill switch engaged at send time")
        headers = {"Authorization": "Bearer " + self._config.token.reveal(),
                   "Accept-Datetime-Format": "RFC3339"}
        if is_write:
            headers["Content-Type"] = "application/json"
        try:
            status, raw = self._opener(method, url, headers, payload, self._timeout)
        except NotSent:
            raise
        except Exception as exc:  # noqa: BLE001 -- any other failure: outcome unknown
            raise SendUncertain("%s: %s" % (operation, type(exc).__name__))
        if not isinstance(status, int) or not isinstance(raw, (bytes, bytearray)):
            raise SendUncertain("%s: opener returned a malformed response" % operation)
        return Response(status, bytes(raw))

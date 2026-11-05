"""The A3 write opener: one broker write, exactly the one the operator authorized.

A GRANT is built from a parsed, current operator authorization, and it names the
only write the opener will send:

  EntryGrant  (A3)    exactly one POST /v3/accounts/<account>/orders whose body is
                      the market order for THAT authorization: its client order id,
                      instrument, signed units and stop price; FOK; OPEN_ONLY; a
                      priceBound; a stopLossOnFill; and no other field.
  CloseGrant          exactly one PUT /v3/accounts/<account>/trades/<trade>/close
                      for THAT trade, with the body {"units": "ALL"}.

Every check runs BEFORE any socket, and a refusal raises A3Refused, a NotSent.
The grant is spent before the request is handed to the socket, so this process
can send it at most once even if the send fails; the journal (authorizationId and
closeAuthorizationId consumed write-ahead) makes it at most once, ever.

GET requests go through the inherited read-only checks unchanged. The host, the
account, TLS verification, the loopback-only proxy and redirect refusal are the
read-only opener's own: there is one network path, and it has no live host.
"""
import json
from decimal import Decimal, InvalidOperation

from oanda_practice import authorization as authz
from oanda_practice import timeutil
from oanda_practice.errors import NotSent
from oanda_practice_m3.readonly import ReadOnlyHttpsOpener

_ENTRY_ORDER_KEYS = {"type", "instrument", "units", "timeInForce", "positionFill", "priceBound",
                     "stopLossOnFill", "clientExtensions", "tradeClientExtensions"}


class A3Refused(NotSent):
    """Refused by the A3 boundary before any socket. Nothing was sent."""


def _positive_decimal(value):
    try:
        d = Decimal(value) if isinstance(value, str) else None
    except InvalidOperation:
        return None
    return d if d is not None and d.is_finite() and d > 0 else None


class EntryGrant(object):
    """A3: permission for the single market entry one authorization describes."""

    def __init__(self, auth, config, now=None):
        if not isinstance(auth, authz.Authorization):
            raise A3Refused("an entry grant needs a parsed operator authorization")
        authz.check_current(auth, config, now or timeutil.utc_now())
        self.auth = auth

    def check(self, method, parts, body, prefix):
        a = self.auth
        if method != "POST" or parts.path != prefix + "orders" or parts.query:
            raise A3Refused("the entry grant permits only POST orders")
        try:
            order = json.loads(body.decode("utf-8"))["order"]
        except (AttributeError, UnicodeDecodeError, ValueError, KeyError, TypeError):
            raise A3Refused("the entry body is not an order")
        if not isinstance(order, dict) or set(order) != _ENTRY_ORDER_KEYS:
            raise A3Refused("the entry order carries other fields than the authorized ones")
        stop = order.get("stopLossOnFill") or {}
        wanted = {"type": "MARKET", "instrument": a.instrument, "units": str(a.signed_units),
                  "timeInForce": "FOK", "positionFill": "OPEN_ONLY"}
        if any(order.get(k) != v for k, v in wanted.items()):
            raise A3Refused("the entry order is not the authorized order")
        if not isinstance(stop, dict) or _positive_decimal(stop.get("price")) != a.stop_loss_price:
            raise A3Refused("the entry order does not carry the authorized protective stop")
        if (order.get("clientExtensions") or {}).get("id") != a.client_order_id \
                or (order.get("tradeClientExtensions") or {}).get("id") != a.client_order_id:
            raise A3Refused("the entry order does not carry the authorized client order id")
        if _positive_decimal(order.get("priceBound")) is None:
            raise A3Refused("the entry order has no price bound")


class CloseGrant(object):
    """Permission to close one identified trade, from its own close authorization."""

    def __init__(self, close_auth, config, now=None):
        if not isinstance(close_auth, authz.CloseAuthorization):
            raise A3Refused("a close grant needs a parsed close authorization")
        if close_auth.account_id != config.account_id:
            raise A3Refused("the close authorization names a different account")
        when = now or timeutil.utc_now()
        if not close_auth.issued_at <= when < close_auth.expires_at:
            raise A3Refused("the close authorization is not valid at this time")
        self.close_auth = close_auth

    def check(self, method, parts, body, prefix):
        if method != "PUT" or parts.path != "%strades/%s/close" % (prefix, self.close_auth.trade_id) \
                or parts.query:
            raise A3Refused("the close grant permits only PUT close for the authorized trade")
        try:
            payload = json.loads(body.decode("utf-8"))
        except (AttributeError, UnicodeDecodeError, ValueError):
            raise A3Refused("the close body is not JSON")
        if payload != {"units": "ALL"}:
            raise A3Refused("the close grant permits only a full close")


class A3WriteOpener(ReadOnlyHttpsOpener):
    """GETs as the read-only opener; plus exactly one write, the one its grant names."""

    def __init__(self, account_id, grant, **kw):
        if not isinstance(grant, (EntryGrant, CloseGrant)):
            raise A3Refused("the write opener needs an entry or close grant")
        super().__init__(account_id, **kw)
        self._grant = grant
        self.writes = 0

    def __call__(self, method, url, headers, body, timeout):
        if method == "GET":
            return super().__call__(method, url, headers, body, timeout)
        parts = self.check_target(url, headers)
        if self.writes:
            raise A3Refused("this grant has already been spent")
        self._grant.check(method, parts, body, self._prefix)
        self.writes += 1                       # spent BEFORE the socket: never sent twice
        return self._send(method, parts, headers, body, timeout)

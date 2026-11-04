"""The narrow broker interface, and its OANDA v20 practice implementation.

BrokerAdapter is what the executor depends on; a later adapter (another
broker, a LEAN bridge) implements the same methods. Everything returned is
normalised and carries the raw response bytes so the journal can preserve them.

CLASSIFYING A SUBMIT IS THE SAFETY-CRITICAL PART, and it is deliberately
asymmetric. An outcome is DEFINITIVE only when the broker's own transaction
says so: an ORDER_FILL carrying the opened trade, its price and its units
(FILLED); an ORDER_CANCEL (CANCELLED); an order-reject transaction or an
authentication/validation status for which the broker documents that no order
was created (REJECTED). Every other shape -- a 5xx, a 429, an unparseable body,
a fill missing its trade, a fill for different units -- is UNCERTAIN, because
treating it as "nothing happened" is how an order gets placed twice.

M1 does not interpret fills beyond identity, price and units: realized P&L,
financing, closes and balance reconciliation are M2 (close_trade and the
accounting methods are declared here and refuse until then).
"""
from decimal import Decimal, InvalidOperation

from .errors import BrokerReadFailed, NotSent, SendUncertain
from . import timeutil

FILLED, CANCELLED, REJECTED, UNCERTAIN = "FILLED", "CANCELLED", "REJECTED", "UNCERTAIN"

#: HTTP statuses for which a create-order request is documented to create nothing.
DEFINITIVE_NO_ORDER_STATUSES = (400, 401, 403, 404, 405)


class Quote(object):
    __slots__ = ("instrument", "bid", "ask", "time", "tradeable", "raw")

    def __init__(self, instrument, bid, ask, time, tradeable, raw):
        self.instrument, self.bid, self.ask = instrument, bid, ask
        self.time, self.tradeable, self.raw = time, tradeable, raw


class AccountSummary(object):
    __slots__ = ("account_id", "currency", "last_transaction_id", "open_trade_count", "raw")

    def __init__(self, account_id, currency, last_transaction_id, open_trade_count, raw):
        self.account_id, self.currency = account_id, currency
        self.last_transaction_id, self.open_trade_count = last_transaction_id, open_trade_count
        self.raw = raw


class SubmitOutcome(object):
    __slots__ = ("kind", "reason", "order_id", "trade_id", "fill_price", "fill_units", "raw")

    def __init__(self, kind, reason=None, order_id=None, trade_id=None, fill_price=None,
                 fill_units=None, raw=None):
        self.kind, self.reason, self.order_id, self.trade_id = kind, reason, order_id, trade_id
        self.fill_price, self.fill_units, self.raw = fill_price, fill_units, raw


class BrokerAdapter(object):
    """Interface. M1 uses the first five; M2 implements the last two."""

    def account_summary(self):
        raise NotImplementedError

    def quote(self, instrument):
        raise NotImplementedError

    def open_trades(self):
        raise NotImplementedError

    def submit_market_order(self, order_body, expected_client_id, expected_units):
        raise NotImplementedError

    def resolve_client_order(self, client_id, since_transaction_id, expected_units):
        raise NotImplementedError

    def close_trade(self, trade_id):
        raise NotImplementedError("M2: closing is not implemented in M1")

    def transactions_for_accounting(self, since_transaction_id):
        raise NotImplementedError("M2: accounting is not implemented in M1")


def _decimal(value):
    if not isinstance(value, str):
        return None
    try:
        result = Decimal(value)
    except InvalidOperation:
        return None
    return result if result.is_finite() else None


def _read(transport, operation, **params):
    try:
        response = transport.request(operation, **params)
    except (SendUncertain, NotSent) as exc:
        raise BrokerReadFailed("%s failed: %s" % (operation, exc))
    if response.status != 200 or not isinstance(response.data, dict):
        raise BrokerReadFailed("%s returned HTTP %s" % (operation, response.status))
    return response


def classify_fill(fill, expected_client_id, expected_units, raw):
    """FILLED only on complete evidence; anything less is UNCERTAIN with a reason."""
    opened = fill.get("tradeOpened") if isinstance(fill, dict) else None
    if not isinstance(opened, dict) or not opened.get("tradeID"):
        return SubmitOutcome(UNCERTAIN, reason="FILL_WITHOUT_TRADE_OPENED", raw=raw)
    price = _decimal(fill.get("price"))
    units = _decimal(opened.get("units"))
    if price is None or units is None:
        return SubmitOutcome(UNCERTAIN, reason="FILL_MISSING_PRICE_OR_UNITS", raw=raw)
    if units != Decimal(expected_units):
        return SubmitOutcome(UNCERTAIN, reason="FILL_UNITS_MISMATCH", trade_id=opened["tradeID"],
                             fill_price=price, fill_units=units, raw=raw)
    if fill.get("clientOrderID") not in (None, expected_client_id):
        return SubmitOutcome(UNCERTAIN, reason="FILL_FOR_ANOTHER_CLIENT_ID", raw=raw)
    return SubmitOutcome(FILLED, order_id=fill.get("orderID"), trade_id=opened["tradeID"],
                         fill_price=price, fill_units=units, raw=raw)


class OandaPracticeAdapter(BrokerAdapter):
    def __init__(self, transport):
        self._t = transport

    def account_summary(self):
        response = _read(self._t, "ACCOUNT_SUMMARY")
        account = response.data.get("account")
        if not isinstance(account, dict):
            raise BrokerReadFailed("ACCOUNT_SUMMARY has no account object")
        last = response.data.get("lastTransactionID") or account.get("lastTransactionID")
        count = account.get("openTradeCount")
        if not isinstance(account.get("currency"), str) or not isinstance(last, str) \
                or not isinstance(count, int):
            raise BrokerReadFailed("ACCOUNT_SUMMARY is missing currency, lastTransactionID or openTradeCount")
        return AccountSummary(account.get("id"), account["currency"], last, count, response.body)

    def quote(self, instrument):
        response = _read(self._t, "PRICING", instrument=instrument)
        prices = response.data.get("prices")
        if not isinstance(prices, list) or len(prices) != 1 or not isinstance(prices[0], dict):
            raise BrokerReadFailed("PRICING did not return exactly one price")
        p = prices[0]
        try:
            bid = _decimal(p["bids"][0]["price"])
            ask = _decimal(p["asks"][0]["price"])
        except (KeyError, IndexError, TypeError):
            bid = ask = None
        when = timeutil.parse_rfc3339(p.get("time"))
        tradeable = p.get("tradeable")
        if p.get("instrument") != instrument or bid is None or ask is None or when is None \
                or not isinstance(tradeable, bool):
            raise BrokerReadFailed("PRICING is missing instrument, bid, ask, time or tradeable")
        return Quote(instrument, bid, ask, when, tradeable, response.body)

    def open_trades(self):
        response = _read(self._t, "OPEN_TRADES")
        trades = response.data.get("trades")
        if not isinstance(trades, list):
            raise BrokerReadFailed("OPEN_TRADES has no trades list")
        return trades

    def submit_market_order(self, order_body, expected_client_id, expected_units):
        """Raises NotSent if provably unsent; otherwise always returns an outcome."""
        try:
            response = self._t.request("CREATE_ORDER", body=order_body)
        except SendUncertain as exc:
            return SubmitOutcome(UNCERTAIN, reason="SEND_UNCERTAIN:" + str(exc))
        data, raw = response.data, response.body
        if response.status == 201 and isinstance(data, dict):
            if "orderFillTransaction" in data:
                return classify_fill(data["orderFillTransaction"], expected_client_id,
                                     expected_units, raw)
            cancel = data.get("orderCancelTransaction")
            if isinstance(cancel, dict):
                return SubmitOutcome(CANCELLED, reason=cancel.get("reason") or "UNSTATED",
                                     order_id=cancel.get("orderID"), raw=raw)
            return SubmitOutcome(UNCERTAIN, reason="CREATED_WITHOUT_FILL_OR_CANCEL", raw=raw)
        if response.status in DEFINITIVE_NO_ORDER_STATUSES:
            reason = None
            if isinstance(data, dict):
                reject = data.get("orderRejectTransaction") or {}
                reason = reject.get("rejectReason") or data.get("errorCode")
            return SubmitOutcome(REJECTED, reason=reason or "HTTP_%d" % response.status, raw=raw)
        return SubmitOutcome(UNCERTAIN, reason="HTTP_%d" % response.status, raw=raw)

    def resolve_client_order(self, client_id, since_transaction_id, expected_units):
        """Prove what happened to an order whose submit outcome is unknown.

        Two independent sources must agree: the order looked up by client id,
        and the account's transactions since the id recorded BEFORE the submit.
        ABSENT requires the order lookup to say it does not exist AND no
        transaction since to mention the client id. Any read failure raises
        BrokerReadFailed, and the caller keeps the intent UNCERTAIN.
        """
        try:
            lookup = self._t.request("ORDER_BY_CLIENT_ID", client_id=client_id)
        except (SendUncertain, NotSent) as exc:
            raise BrokerReadFailed("ORDER_BY_CLIENT_ID failed: %s" % exc)
        txns = _read(self._t, "TRANSACTIONS_SINCE", transaction_id=since_transaction_id)
        transactions = txns.data.get("transactions")
        if not isinstance(transactions, list):
            raise BrokerReadFailed("TRANSACTIONS_SINCE has no transactions list")
        mine = [t for t in transactions if isinstance(t, dict) and client_id in (
            (t.get("clientExtensions") or {}).get("id"), t.get("clientOrderID"))]
        raw = lookup.body + b"\n" + txns.body

        if lookup.status == 404:
            if mine:
                return SubmitOutcome(UNCERTAIN, reason="LOOKUP_ABSENT_BUT_TRANSACTIONS_PRESENT", raw=raw)
            return SubmitOutcome("ABSENT", raw=raw)
        if lookup.status != 200 or not isinstance(lookup.data, dict) \
                or not isinstance(lookup.data.get("order"), dict):
            raise BrokerReadFailed("ORDER_BY_CLIENT_ID returned HTTP %s" % lookup.status)
        order = lookup.data["order"]
        if (order.get("clientExtensions") or {}).get("id") != client_id:
            return SubmitOutcome(UNCERTAIN, reason="LOOKUP_RETURNED_ANOTHER_ORDER", raw=raw)
        state = order.get("state")
        if state == "FILLED":
            fills = [t for t in transactions if isinstance(t, dict) and t.get("type") == "ORDER_FILL"
                     and t.get("orderID") == order.get("id")]
            if len(fills) != 1:
                return SubmitOutcome(UNCERTAIN, reason="FILLED_ORDER_WITHOUT_ONE_FILL_TRANSACTION", raw=raw)
            outcome = classify_fill(fills[0], client_id, expected_units, raw)
            if outcome.kind == FILLED and outcome.trade_id != order.get("tradeOpenedID"):
                return SubmitOutcome(UNCERTAIN, reason="ORDER_AND_FILL_DISAGREE_ON_TRADE", raw=raw)
            return outcome
        if state == "CANCELLED":
            return SubmitOutcome(CANCELLED, reason="RESOLVED_CANCELLED", order_id=order.get("id"), raw=raw)
        return SubmitOutcome(UNCERTAIN, reason="ORDER_STATE_%s" % state, raw=raw)

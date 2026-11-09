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

M2 adds the position side: trade details, a contiguous transaction history,
and closing. A close is classified with the same asymmetry: CLOSED only on an
ORDER_FILL whose tradesClosed entry names our trade for its full units.
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
    __slots__ = ("account_id", "currency", "last_transaction_id", "open_trade_count", "balance", "raw",
                 "pending_order_count")

    def __init__(self, account_id, currency, last_transaction_id, open_trade_count, raw, balance=None,
                 pending_order_count=None):
        self.account_id, self.currency = account_id, currency
        self.last_transaction_id, self.open_trade_count = last_transaction_id, open_trade_count
        self.balance, self.raw = balance, raw
        self.pending_order_count = pending_order_count     # None: not stated, so not proven zero


class InstrumentSpec(object):
    """The broker's own order constraints for one instrument (GET instruments)."""
    __slots__ = ("instrument", "minimum_trade_size", "maximum_order_units", "trade_units_precision",
                 "display_precision", "pip_location", "raw")

    def __init__(self, instrument, minimum_trade_size, maximum_order_units, trade_units_precision,
                 display_precision, pip_location, raw):
        self.instrument = instrument
        self.minimum_trade_size, self.maximum_order_units = minimum_trade_size, maximum_order_units
        self.trade_units_precision, self.display_precision = trade_units_precision, display_precision
        self.pip_location, self.raw = pip_location, raw


class TradeState(object):
    """A broker trade as GET trades/{id} reports it."""
    __slots__ = ("trade_id", "state", "instrument", "open_price", "current_units",
                 "stop_order", "raw")

    def __init__(self, trade_id, state, instrument, open_price, current_units, stop_order, raw):
        self.trade_id, self.state, self.instrument = trade_id, state, instrument
        self.open_price, self.current_units = open_price, current_units
        self.stop_order, self.raw = stop_order, raw


class TransactionWindow(object):
    """Every transaction after `since`, proven contiguous up to `last_id`."""
    __slots__ = ("since", "last_id", "transactions", "raw")

    def __init__(self, since, last_id, transactions, raw):
        self.since, self.last_id, self.transactions, self.raw = since, last_id, transactions, raw


class SubmitOutcome(object):
    __slots__ = ("kind", "reason", "order_id", "trade_id", "fill_price", "fill_units", "raw")

    def __init__(self, kind, reason=None, order_id=None, trade_id=None, fill_price=None,
                 fill_units=None, raw=None):
        self.kind, self.reason, self.order_id, self.trade_id = kind, reason, order_id, trade_id
        self.fill_price, self.fill_units, self.raw = fill_price, fill_units, raw


class BrokerAdapter(object):
    """Interface. Kept narrow: these eight calls are the whole broker surface."""

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

    def trade(self, trade_id):
        raise NotImplementedError

    def transactions_since(self, since_transaction_id):
        raise NotImplementedError

    def close_trade(self, trade_id, expected_trade_units):
        raise NotImplementedError

    def instrument_spec(self, instrument):
        raise NotImplementedError


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
    """FILLED only on complete evidence; anything less is UNCERTAIN with a reason.

    expected_units is SIGNED (negative for a sell), as OANDA reports tradeOpened.units.
    """
    opened = fill.get("tradeOpened") if isinstance(fill, dict) else None
    if not isinstance(opened, dict) or not opened.get("tradeID"):
        return SubmitOutcome(UNCERTAIN, reason="FILL_WITHOUT_TRADE_OPENED", raw=raw)
    # The trade's own open price is authoritative. The fill's top-level `price` is deprecated
    # in the v20 schema; it is only a fallback, so a fill that omits it is not left UNCERTAIN.
    price = _decimal(opened.get("price"))
    if price is None:
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
        balance = _decimal(account.get("balance"))
        if not isinstance(account.get("currency"), str) or not isinstance(last, str) \
                or not isinstance(count, int) or balance is None:
            raise BrokerReadFailed("ACCOUNT_SUMMARY is missing currency, balance, lastTransactionID "
                                   "or openTradeCount")
        pending = account.get("pendingOrderCount")
        return AccountSummary(account.get("id"), account["currency"], last, count, response.body,
                              balance=balance,
                              pending_order_count=pending if isinstance(pending, int)
                              and not isinstance(pending, bool) else None)

    def instrument_spec(self, instrument):
        response = _read(self._t, "INSTRUMENT_DETAILS", instrument=instrument)
        found = response.data.get("instruments")
        if not isinstance(found, list) or len(found) != 1 or not isinstance(found[0], dict) \
                or found[0].get("name") != instrument:
            raise BrokerReadFailed("INSTRUMENT_DETAILS did not return exactly the instrument asked for")
        i = found[0]
        ints = [i.get(k) for k in ("tradeUnitsPrecision", "displayPrecision", "pipLocation")]
        minimum, maximum = _decimal(i.get("minimumTradeSize")), _decimal(i.get("maximumOrderUnits"))
        if minimum is None or maximum is None or not all(isinstance(v, int) and not isinstance(v, bool)
                                                          for v in ints):
            raise BrokerReadFailed("INSTRUMENT_DETAILS is missing a size, precision or pip field")
        return InstrumentSpec(instrument, minimum, maximum, ints[0], ints[1], ints[2], response.body)

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

    # ---- M2: the position side -------------------------------------------------------
    def trade(self, trade_id):
        """The trade, or None when the broker says it does not exist (404)."""
        try:
            response = self._t.request("TRADE_DETAILS", trade_id=trade_id)
        except (SendUncertain, NotSent) as exc:
            raise BrokerReadFailed("TRADE_DETAILS failed: %s" % exc)
        if response.status == 404:
            return None
        if response.status != 200 or not isinstance(response.data, dict) \
                or not isinstance(response.data.get("trade"), dict):
            raise BrokerReadFailed("TRADE_DETAILS returned HTTP %s" % response.status)
        t = response.data["trade"]
        units = _decimal(t.get("currentUnits"))
        price = _decimal(t.get("price"))
        if t.get("id") != trade_id or t.get("state") not in ("OPEN", "CLOSED", "CLOSE_WHEN_TRADEABLE") \
                or units is None or price is None:
            raise BrokerReadFailed("TRADE_DETAILS is missing id, state, price or currentUnits")
        stop = t.get("stopLossOrder")
        stop_order = None
        if isinstance(stop, dict):
            stop_order = {"id": stop.get("id"), "state": stop.get("state"),
                          "price": _decimal(stop.get("price")), "tradeID": stop.get("tradeID")}
        return TradeState(trade_id, t["state"], t.get("instrument"), price, units, stop_order,
                          response.body)

    def transactions_since(self, since_transaction_id):
        """All transactions after `since`, or BrokerReadFailed if the history is not contiguous.

        A gap (a page limit, a dropped transaction) would let a balance-changing event
        go unseen, so an incomplete window is refused rather than reconciled.
        """
        response = _read(self._t, "TRANSACTIONS_SINCE", transaction_id=since_transaction_id)
        txns = response.data.get("transactions")
        last = response.data.get("lastTransactionID")
        if not isinstance(txns, list) or not isinstance(last, str) or not last.isdigit():
            raise BrokerReadFailed("TRANSACTIONS_SINCE has no transactions list or lastTransactionID")
        ids = []
        for t in txns:
            tid = t.get("id") if isinstance(t, dict) else None
            if not isinstance(tid, str) or not tid.isdigit():
                raise BrokerReadFailed("TRANSACTIONS_SINCE carries a transaction without an id")
            ids.append(int(tid))
        expected = list(range(int(since_transaction_id) + 1, int(last) + 1))
        if ids != expected:
            raise BrokerReadFailed("INCOMPLETE_TRANSACTION_HISTORY: ids %s.. do not run "
                                   "contiguously from %s to %s" % (ids[:3], since_transaction_id, last))
        return TransactionWindow(since_transaction_id, last, txns, response.body)

    def close_trade(self, trade_id, expected_trade_units):
        """Close ALL of one trade. Raises NotSent if provably unsent; otherwise an outcome."""
        try:
            response = self._t.request("CLOSE_TRADE", body={"units": "ALL"}, trade_id=trade_id)
        except SendUncertain as exc:
            return SubmitOutcome(UNCERTAIN, reason="SEND_UNCERTAIN:" + str(exc))
        data, raw = response.data, response.body
        if response.status == 200 and isinstance(data, dict):
            fill = data.get("orderFillTransaction")
            if isinstance(fill, dict):
                return classify_close_fill(fill, trade_id, expected_trade_units, raw)
            cancel = data.get("orderCancelTransaction")
            if isinstance(cancel, dict):
                return SubmitOutcome(CANCELLED, reason=cancel.get("reason") or "UNSTATED", raw=raw)
            return SubmitOutcome(UNCERTAIN, reason="CLOSE_WITHOUT_FILL_OR_CANCEL", raw=raw)
        if response.status in DEFINITIVE_NO_ORDER_STATUSES:
            reason = data.get("errorCode") if isinstance(data, dict) else None
            return SubmitOutcome(REJECTED, reason=reason or "HTTP_%d" % response.status, raw=raw)
        return SubmitOutcome(UNCERTAIN, reason="HTTP_%d" % response.status, raw=raw)


def closing_entry(fill, trade_id):
    """(kind, entry) for our trade in a fill: 'CLOSED', 'REDUCED' or (None, None)."""
    for kind, key in (("CLOSED", "tradesClosed"), ("REDUCED", "tradeReduced")):
        entries = fill.get(key)
        entries = [entries] if isinstance(entries, dict) else (entries or [])
        for entry in entries:
            if isinstance(entry, dict) and entry.get("tradeID") == trade_id:
                return kind, entry
    return None, None


def classify_close_fill(fill, trade_id, expected_trade_units, raw):
    """CLOSED only when the fill closes our trade for its full units, with price and P&L."""
    kind, entry = closing_entry(fill, trade_id)
    if kind is None:
        return SubmitOutcome(UNCERTAIN, reason="CLOSE_FILL_DOES_NOT_NAME_OUR_TRADE", raw=raw)
    if kind == "REDUCED":
        return SubmitOutcome(UNCERTAIN, reason="PARTIAL_CLOSE", raw=raw)
    units, price = _decimal(entry.get("units")), _decimal(entry.get("price"))
    if units is None or price is None or _decimal(entry.get("realizedPL")) is None:
        return SubmitOutcome(UNCERTAIN, reason="CLOSE_FILL_MISSING_UNITS_PRICE_OR_PL", raw=raw)
    if units != -Decimal(expected_trade_units):
        return SubmitOutcome(UNCERTAIN, reason="CLOSE_UNITS_MISMATCH", raw=raw)
    return SubmitOutcome("CLOSED", reason=fill.get("reason"), order_id=fill.get("orderID"),
                         trade_id=trade_id, fill_price=price, fill_units=units, raw=raw)

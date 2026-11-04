"""An in-process fake of the OANDA v20 endpoints the practice executor uses.

It is an OPENER (the transport's injected send function), so no socket is ever
involved. Response shapes follow the v20 REST schema for the fields the adapter
reads; everything else is omitted. Transaction ids are consecutive integers, as
on a real account, and every balance-changing transaction carries
accountBalance. The fake applies the sign model pl + financing - commission -
guaranteedExecutionFee, which is the assumption accounting.py tests.

Scripted behaviour (M1):
    submit_behavior  fill | cancel | reject | partial | fill_missing_trade |
                     created_only | malformed_after_commit | http500_after_commit |
                     http500_no_commit | timeout_after_commit | timeout_before_commit
    fail_reads       set of operation names whose GET raises ConnectionError
    on_request       optional hook(method, path) called before each response
Position side (M2):
    close_behavior   fill | reject | cancel | partial | timeout_after_commit |
                     timeout_before_commit | http500_after_commit
    stop_behavior    attach | missing | wrong_price
    close_commission, close_financing   Decimal amounts booked on the close fill
    balance_report_skew   added to the NEXT reported accountBalance (a lying broker)
    summary_balance_skew  added to the summary balance
    hide_transaction_ids  ids omitted from TRANSACTIONS_SINCE (a gap)
    trigger_stop(trade_id, gap), daily_financing(amount), transfer(amount)

`posts` counts create-order requests that reached the fake; `committed` counts
orders it actually created; `close_puts` counts close requests.
"""
import json
from decimal import Decimal, ROUND_HALF_EVEN
from urllib.parse import urlsplit, parse_qs

CENT4 = Decimal("0.0001")


def money(value):
    return str(Decimal(value).quantize(CENT4, rounding=ROUND_HALF_EVEN))


class FakeOanda(object):
    def __init__(self, account_id, currency="USD", now_iso="2026-11-03T12:00:00.000000000Z"):
        self.account_id = account_id
        self.currency = currency
        self.now_iso = now_iso
        self.prices = {"EUR_USD": {"bid": "1.10000", "ask": "1.10010", "time": now_iso, "tradeable": True}}
        self.balance = Decimal("1000.0000")
        self.submit_behavior = "fill"
        self.close_behavior = "fill"
        self.stop_behavior = "attach"
        self.close_commission = Decimal("0")
        self.close_financing = Decimal("0")
        self.balance_report_skew = Decimal("0")
        self.summary_balance_skew = Decimal("0")
        self.hide_transaction_ids = set()
        self.fail_reads = set()
        self.on_request = None
        self.lookup_extra_transactions = []
        self.next_id = 100
        self.orders = {}          # client id -> order
        self.transactions = []
        self.trades = []          # OPEN trades (M1 tests append and clear this list directly)
        self.closed_trades = []
        self.requests = []
        self.posts = 0
        self.close_puts = 0
        self.committed = 0
        self.seen_headers = []
        self.summary_account_id = None
        self.fill_client_id_override = None

    # ---- plumbing --------------------------------------------------------------------
    def _id(self):
        self.next_id += 1
        return str(self.next_id)

    @staticmethod
    def _ok(status, payload):
        return status, json.dumps(payload).encode("utf-8")

    def _book(self, txn, effect):
        """Apply a balance effect and stamp accountBalance (optionally lying once)."""
        self.balance += effect
        txn["accountBalance"] = money(self.balance + self.balance_report_skew)
        self.balance_report_skew = Decimal("0")
        self.transactions.append(txn)
        return txn

    def __call__(self, method, url, headers, body, timeout):
        parts = urlsplit(url)
        path = parts.path
        self.requests.append((method, path))
        self.seen_headers.append(dict(headers))
        if self.on_request:
            self.on_request(method, path)
        prefix = "/v3/accounts/%s" % self.account_id
        if not path.startswith(prefix):
            return self._ok(404, {"errorMessage": "Invalid value specified for 'accountID'"})
        rest = path[len(prefix):]
        query = parse_qs(parts.query)
        if method == "GET":
            return self._get(rest, query)
        if method == "POST" and rest == "/orders":
            return self._post_order(json.loads(body.decode("utf-8")))
        if method == "PUT" and rest.startswith("/trades/") and rest.endswith("/close"):
            return self._close(rest[len("/trades/"):-len("/close")], json.loads(body.decode("utf-8")))
        return self._ok(405, {"errorMessage": "method not allowed"})

    def _trade(self, trade_id):
        for t in self.trades + self.closed_trades:
            if t.get("id") == trade_id:
                return t
        return None

    # ---- reads ---------------------------------------------------------------------
    def _get(self, rest, query):
        op = {"/summary": "ACCOUNT_SUMMARY", "/pricing": "PRICING", "/openTrades": "OPEN_TRADES",
              "/transactions/sinceid": "TRANSACTIONS_SINCE"}.get(rest)
        if rest.startswith("/orders/@"):
            op = "ORDER_BY_CLIENT_ID"
        elif rest.startswith("/trades/"):
            op = "TRADE_DETAILS"
        if op in self.fail_reads:
            raise ConnectionError("fake: read failed")
        last = str(self.next_id)
        if op == "ACCOUNT_SUMMARY":
            return self._ok(200, {"account": {"id": self.summary_account_id or self.account_id,
                                              "currency": self.currency,
                                              "balance": money(self.balance + self.summary_balance_skew),
                                              "lastTransactionID": last, "openTradeCount": len(self.trades)},
                                  "lastTransactionID": last})
        if op == "PRICING":
            inst = query.get("instruments", [""])[0]
            p = self.prices.get(inst)
            if p is None:
                return self._ok(200, {"prices": []})
            price = {"instrument": inst, "bids": [{"price": p["bid"], "liquidity": 1000000}],
                     "asks": [{"price": p["ask"], "liquidity": 1000000}], "tradeable": p["tradeable"]}
            if p.get("time") is not None:
                price["time"] = p["time"]
            return self._ok(200, {"prices": [price], "time": p.get("time")})
        if op == "OPEN_TRADES":
            return self._ok(200, {"trades": self.trades, "lastTransactionID": last})
        if op == "ORDER_BY_CLIENT_ID":
            order = self.orders.get(rest[len("/orders/@"):])
            if order is None:
                return self._ok(404, {"errorMessage": "The Order specified does not exist",
                                      "errorCode": "NO_SUCH_ORDER"})
            return self._ok(200, {"order": order, "lastTransactionID": last})
        if op == "TRADE_DETAILS":
            trade = self._trade(rest[len("/trades/"):])
            if trade is None:
                return self._ok(404, {"errorMessage": "The Trade specified does not exist",
                                      "errorCode": "NO_SUCH_TRADE"})
            return self._ok(200, {"trade": trade, "lastTransactionID": last})
        if op == "TRANSACTIONS_SINCE":
            since = int(query["id"][0])
            txns = [t for t in self.transactions if int(t["id"]) > since
                    and t["id"] not in self.hide_transaction_ids] + self.lookup_extra_transactions
            return self._ok(200, {"transactions": txns, "lastTransactionID": last})
        return self._ok(404, {"errorMessage": "unknown path"})

    # ---- the entry order ---------------------------------------------------------------
    def _post_order(self, body):
        self.posts += 1
        b = self.submit_behavior
        order = body["order"]
        cid = order["clientExtensions"]["id"]
        if b == "timeout_before_commit":
            raise TimeoutError("fake: timed out before the broker saw it")
        if b == "http500_no_commit":
            return self._ok(500, {"errorMessage": "internal error"})
        if b == "reject":
            return self._ok(400, {"orderRejectTransaction": {"id": self._id(), "type": "MARKET_ORDER_REJECT",
                                                             "rejectReason": "STOP_LOSS_ON_FILL_PRICE_INVALID"},
                                  "errorCode": "STOP_LOSS_ON_FILL_PRICE_INVALID"})
        create = {"id": self._id(), "type": "MARKET_ORDER", "instrument": order["instrument"],
                  "units": order["units"], "clientExtensions": order["clientExtensions"]}
        self.transactions.append(create)
        self.committed += 1
        if b == "cancel":
            cancel = {"id": self._id(), "type": "ORDER_CANCEL", "orderID": create["id"],
                      "clientOrderID": cid, "reason": "MARKET_HALTED"}
            self.transactions.append(cancel)
            self.orders[cid] = {"id": create["id"], "state": "CANCELLED", "clientExtensions": order["clientExtensions"],
                                "cancellingTransactionID": cancel["id"]}
            return self._ok(201, {"orderCreateTransaction": create, "orderCancelTransaction": cancel})
        units = order["units"]
        if b == "partial":
            units = str(int(units) // 2 or 1) if abs(int(units)) > 1 else "0"
        price = self.prices[order["instrument"]]["ask" if int(order["units"]) > 0 else "bid"]
        trade_id = self._id()
        fill = {"id": trade_id, "type": "ORDER_FILL", "orderID": create["id"],
                "clientOrderID": self.fill_client_id_override or cid, "reason": "MARKET_ORDER",
                "instrument": order["instrument"], "units": units, "price": price,
                "pl": "0.0000", "financing": "0.0000", "commission": "0.0000", "guaranteedExecutionFee": "0.0000",
                "tradeOpened": {"tradeID": trade_id, "units": units, "price": price,
                                "clientExtensions": order.get("tradeClientExtensions")}}
        if b == "fill_missing_trade":
            del fill["tradeOpened"]
        self._book(fill, Decimal("0"))
        trade = {"id": trade_id, "instrument": order["instrument"], "price": price, "openTime": self.now_iso,
                 "state": "OPEN", "initialUnits": units, "currentUnits": units, "realizedPL": "0.0000",
                 "financing": "0.0000", "clientExtensions": order.get("tradeClientExtensions")}
        stop_spec = order.get("stopLossOnFill")
        if stop_spec and self.stop_behavior != "missing":
            stop_price = stop_spec["price"]
            if self.stop_behavior == "wrong_price":
                stop_price = str(Decimal(stop_price) - Decimal("0.00100"))
            stop = {"id": self._id(), "type": "STOP_LOSS_ORDER", "tradeID": trade_id, "price": stop_price,
                    "timeInForce": "GTC", "reason": "ON_FILL"}
            self.transactions.append(stop)
            trade["stopLossOrder"] = {"id": stop["id"], "type": "STOP_LOSS", "tradeID": trade_id,
                                      "price": stop_price, "state": "PENDING"}
        self.orders[cid] = {"id": create["id"], "state": "FILLED", "clientExtensions": order["clientExtensions"],
                            "fillingTransactionID": fill["id"], "tradeOpenedID": trade_id}
        self.trades.append(trade)
        if b == "created_only":
            return self._ok(201, {"orderCreateTransaction": create})
        if b == "malformed_after_commit":
            return 201, b"{not json"
        if b == "http500_after_commit":
            return self._ok(500, {"errorMessage": "internal error"})
        if b == "timeout_after_commit":
            raise TimeoutError("fake: committed, then the connection dropped")
        return self._ok(201, {"orderCreateTransaction": create, "orderFillTransaction": fill,
                              "lastTransactionID": str(self.next_id)})

    # ---- closing -----------------------------------------------------------------------
    def _execute_close(self, trade, price, reason, order_id, units_closed=None):
        open_units = Decimal(trade["currentUnits"])
        closing = open_units if units_closed is None else Decimal(units_closed)
        realized = Decimal(money((Decimal(price) - Decimal(trade["price"])) * closing))
        fin, comm = self.close_financing, self.close_commission
        entry = {"tradeID": trade["id"], "units": str(-closing), "price": price, "realizedPL": money(realized),
                 "financing": money(fin), "guaranteedExecutionFee": "0.0000"}
        fill = {"id": self._id(), "type": "ORDER_FILL", "orderID": order_id, "reason": reason,
                "instrument": trade["instrument"], "units": str(-closing), "price": price,
                "pl": money(realized), "financing": money(fin), "commission": money(comm),
                "guaranteedExecutionFee": "0.0000"}
        if units_closed is None:
            fill["tradesClosed"] = [entry]
        else:
            fill["tradeReduced"] = entry
        self._book(fill, realized + fin - comm)
        if units_closed is None:
            stop = trade.get("stopLossOrder")
            if stop and stop["state"] == "PENDING" and reason != "STOP_LOSS_ORDER":
                stop["state"] = "CANCELLED"
                self.transactions.append({"id": self._id(), "type": "ORDER_CANCEL", "orderID": stop["id"],
                                          "reason": "LINKED_TRADE_CLOSED"})
            trade.update(state="CLOSED", currentUnits="0", realizedPL=money(realized))
            self.trades.remove(trade)
            self.closed_trades.append(trade)
        else:
            trade["currentUnits"] = str(open_units - closing)
        return fill

    def _close(self, trade_id, body):
        self.close_puts += 1
        b = self.close_behavior
        trade = self._trade(trade_id)
        if b == "timeout_before_commit":
            raise TimeoutError("fake: close timed out before the broker saw it")
        if trade is None or trade["state"] != "OPEN" or b == "reject":
            return self._ok(404, {"errorMessage": "The Trade specified does not exist",
                                  "errorCode": "NO_SUCH_TRADE"})
        create = {"id": self._id(), "type": "MARKET_ORDER", "instrument": trade["instrument"],
                  "units": str(-Decimal(trade["currentUnits"])),
                  "tradeClose": {"tradeID": trade_id, "units": body.get("units")}}
        self.transactions.append(create)
        if b == "cancel":
            cancel = {"id": self._id(), "type": "ORDER_CANCEL", "orderID": create["id"], "reason": "MARKET_HALTED"}
            self.transactions.append(cancel)
            return self._ok(200, {"orderCreateTransaction": create, "orderCancelTransaction": cancel})
        p = self.prices[trade["instrument"]]
        price = p["bid"] if Decimal(trade["currentUnits"]) > 0 else p["ask"]
        partial = Decimal(trade["currentUnits"]) / 2 if b == "partial" else None
        fill = self._execute_close(trade, price, "MARKET_ORDER_TRADE_CLOSE", create["id"], partial)
        if b == "timeout_after_commit":
            raise TimeoutError("fake: close committed, then the connection dropped")
        if b == "http500_after_commit":
            return self._ok(500, {"errorMessage": "internal error"})
        return self._ok(200, {"orderCreateTransaction": create, "orderFillTransaction": fill,
                              "lastTransactionID": str(self.next_id)})

    # ---- broker-side events a test can script ---------------------------------------------
    def trigger_stop(self, trade_id, gap=Decimal("0")):
        """The stop fires at the broker. `gap` moves the fill beyond the stop (adverse)."""
        trade = self._trade(trade_id)
        stop = trade["stopLossOrder"]
        long_ = Decimal(trade["currentUnits"]) > 0
        price = str(Decimal(stop["price"]) - gap if long_ else Decimal(stop["price"]) + gap)
        stop["state"] = "FILLED"
        return self._execute_close(trade, price, "STOP_LOSS_ORDER", stop["id"])

    def daily_financing(self, amount):
        return self._book({"id": self._id(), "type": "DAILY_FINANCING", "financing": money(amount)},
                          Decimal(amount))

    def transfer(self, amount):
        return self._book({"id": self._id(), "type": "TRANSFER_FUNDS", "amount": money(amount)},
                          Decimal(amount))

"""An in-process fake of the OANDA v20 endpoints the M1 executor uses.

It is an OPENER (the transport's injected send function), so no socket is ever
involved. Response shapes follow the v20 REST schema for the fields the
adapter reads; everything else is omitted. Behaviour is scripted per test:

    submit_behavior  fill | cancel | reject | partial | fill_missing_trade |
                     created_only | malformed_after_commit | http500_after_commit |
                     http500_no_commit | timeout_after_commit | timeout_before_commit
    fail_reads       set of operation names whose GET raises ConnectionError
    on_request       optional hook(method, path) called before each response

`posts` counts create-order requests that reached the fake; `committed` counts
orders the fake actually created. The two differ exactly when a test needs them to.
"""
import json
import re
from urllib.parse import urlsplit, parse_qs


class FakeOanda(object):
    def __init__(self, account_id, currency="USD", now_iso="2026-11-03T12:00:00.000000000Z"):
        self.account_id = account_id
        self.currency = currency
        self.prices = {"EUR_USD": {"bid": "1.10000", "ask": "1.10010", "time": now_iso, "tradeable": True}}
        self.submit_behavior = "fill"
        self.fail_reads = set()
        self.on_request = None
        self.lookup_extra_transactions = []
        self.next_id = 100
        self.orders = {}          # client id -> order
        self.transactions = []
        self.trades = []          # open trades
        self.requests = []        # (method, path) for every request
        self.posts = 0
        self.committed = 0
        self.seen_headers = []
        self.summary_account_id = None      # set to make the summary name another account
        self.fill_client_id_override = None

    def _id(self):
        self.next_id += 1
        return str(self.next_id)

    @staticmethod
    def _ok(status, payload):
        return status, json.dumps(payload).encode("utf-8")

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
        return self._ok(405, {"errorMessage": "method not allowed"})

    # ---- reads ---------------------------------------------------------------
    def _get(self, rest, query):
        op = {"/summary": "ACCOUNT_SUMMARY", "/pricing": "PRICING", "/openTrades": "OPEN_TRADES",
              "/transactions/sinceid": "TRANSACTIONS_SINCE"}.get(rest)
        if rest.startswith("/orders/@"):
            op = "ORDER_BY_CLIENT_ID"
        if op in self.fail_reads:
            raise ConnectionError("fake: read failed")
        last = str(self.next_id)
        if op == "ACCOUNT_SUMMARY":
            return self._ok(200, {"account": {"id": self.summary_account_id or self.account_id, "currency": self.currency,
                                              "balance": "1000.0000", "lastTransactionID": last,
                                              "openTradeCount": len(self.trades)},
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
            cid = rest[len("/orders/@"):]
            order = self.orders.get(cid)
            if order is None:
                return self._ok(404, {"errorMessage": "The Order specified does not exist",
                                      "errorCode": "NO_SUCH_ORDER"})
            return self._ok(200, {"order": order, "lastTransactionID": last})
        if op == "TRANSACTIONS_SINCE":
            since = int(query["id"][0])
            txns = [t for t in self.transactions if int(t["id"]) > since] + self.lookup_extra_transactions
            return self._ok(200, {"transactions": txns, "lastTransactionID": last})
        return self._ok(404, {"errorMessage": "unknown path"})

    # ---- the order -------------------------------------------------------------
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
                "clientOrderID": self.fill_client_id_override or cid,
                "instrument": order["instrument"], "units": units, "price": price,
                "tradeOpened": {"tradeID": trade_id, "units": units, "price": price,
                                "clientExtensions": order.get("tradeClientExtensions")}}
        if b == "fill_missing_trade":
            del fill["tradeOpened"]
        self.transactions.append(fill)
        self.orders[cid] = {"id": create["id"], "state": "FILLED", "clientExtensions": order["clientExtensions"],
                            "fillingTransactionID": fill["id"], "tradeOpenedID": trade_id}
        self.trades.append({"id": trade_id, "instrument": order["instrument"], "currentUnits": units,
                            "price": price, "clientExtensions": order.get("tradeClientExtensions")})
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

"""The M3 read-only preflight: observe the real practice account's response shapes, reveal no values.

It issues only READ_OPERATIONS through a ReadOnlyTransport, compares what comes
back against the shapes M1/M2 assume, and returns a REPORT THAT CARRIES NO
SECRET AND NO ACCOUNT VALUE: the account id is masked, and balances, prices,
transaction ids, trade ids and raw bodies are reduced to types, counts, formats
and agree/disagree verdicts. The raw responses are never written anywhere.

STOPS (no further request is made):
  * CREDENTIALS_REJECTED: the summary answers 401 or 403;
  * NOT_THE_CONFIGURED_PRACTICE_ACCOUNT: the summary names another account,
    or anything other than 200 comes back for the configured one;
  * BOUNDARY: anything ReadOnlyRefused or RedirectRefused.

Requests, in order (seven at most):
  1. ACCOUNT_SUMMARY            identity, currency, summary shape
  2. PRICING <instrument>       time format, tradeable, bid/ask types, quote age
  3. OPEN_TRADES                list shape, count
  4. TRANSACTIONS_SINCE id=1    the whole history if uncapped: pagination or a cap,
                                contiguity, the sign model on real balance changes
  5. ORDER_BY_CLIENT_ID         a random MOGO id that cannot exist: the 404 shape
  6. TRANSACTIONS_SINCE id=last  with 5, M2's two-source ABSENT resolution on real data
  7. ACCOUNT_SUMMARY            only if the history ended at a different transaction than
                                summary 1, so the final balance can be compared at one point
"""
import os
import re

from oanda_practice import adapter as ad
from oanda_practice import timeutil
from oanda_practice.accounting import balance_effect, _dec
from oanda_practice.errors import BrokerReadFailed, NotSent, SendUncertain

from .readonly import ReadOnlyRefused, RedirectRefused

_FRACTION = re.compile(r"\.(\d+)Z$")


class PreflightStop(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def mask_account(account_id):
    """Keep the first and last group only: 101-***-****-001."""
    groups = account_id.split("-")
    if len(groups) != 4:
        return "<masked>"
    return "%s-***-****-%s" % (groups[0], groups[3])


def type_name(value):
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, str):
        if re.match(r"^-?\d+\.\d+$", value):
            return "decimal-string"
        if value.isdigit():
            return "digit-string"
        return "string"
    return type(value).__name__


class Replay(object):
    """Serves responses already fetched, so the M2 adapter parses real bodies without a second request."""

    def __init__(self):
        self.responses = {}

    @staticmethod
    def key(operation, params):
        return operation, tuple(sorted(params.items()))

    def request(self, operation, body=None, **params):
        try:
            return self.responses[self.key(operation, params)]
        except KeyError:
            raise NotSent("replay: %s was not fetched" % operation)


def _sign_model(txns):
    """Check each balance change against the stated sign model, without reporting any value."""
    by_type = {}
    previous = None
    for t in txns:
        stated = _dec(t.get("accountBalance"))
        if stated is None:
            continue
        kind = t.get("type")
        row = by_type.setdefault(kind, {"checked": 0, "agreed": 0, "disagreed": 0, "unmodelled": 0})
        if previous is None:
            previous = stated
            row["unmodelled"] += 1          # the first balance has nothing before it to check against
            continue
        if kind == "TRANSFER_FUNDS":
            effect = _dec(t.get("amount"))
        else:
            effect = balance_effect(t)
        if effect is None:
            row["unmodelled"] += 1
        else:
            row["checked"] += 1
            row["agreed" if previous + effect == stated else "disagreed"] += 1
        previous = stated
    return by_type, previous


def _fill_keys(txns):
    """Which M2-assumed ORDER_FILL keys real fills carry (presence only)."""
    fills = [t for t in txns if t.get("type") == "ORDER_FILL"]
    keys = ("price", "pl", "financing", "commission", "guaranteedExecutionFee", "accountBalance",
            "tradeOpened", "tradesClosed", "tradeReduced", "clientOrderID", "orderID", "reason")
    return {"count": len(fills),
            "present": {k: sum(1 for f in fills if k in f) for k in keys},
            "tradeOpened_units_type": sorted({type_name((f.get("tradeOpened") or {}).get("units"))
                                              for f in fills if f.get("tradeOpened")}),
            "tradesClosed_entry_keys": sorted({k for f in fills for c in (f.get("tradesClosed") or [])
                                               if isinstance(c, dict) for k in c})}


def run(transport, account_id, instrument="EUR_USD", now=timeutil.utc_now):
    report = {"account": mask_account(account_id), "requests": 0, "checks": [], "stop": None,
              "blockers": [], "observed": {}}
    checks, observed = report["checks"], report["observed"]

    def check(name, ok, detail=""):
        checks.append({"check": name, "ok": bool(ok), "detail": detail})
        return ok

    replay = Replay()
    adapter = ad.OandaPracticeAdapter(replay)

    def get(operation, **params):
        report["requests"] += 1
        try:
            response = transport.request(operation, **params)
        except (ReadOnlyRefused, RedirectRefused) as exc:
            raise PreflightStop("BOUNDARY_%s" % type(exc).__name__)
        except SendUncertain as exc:
            # the transport wraps opener failures; a refused redirect is a boundary stop, not a read failure
            raise PreflightStop("BOUNDARY_RedirectRefused" if "RedirectRefused" in str(exc)
                                else "READ_FAILED_%s" % operation)
        except NotSent:
            raise PreflightStop("READ_FAILED_%s" % operation)
        replay.responses[Replay.key(operation, params)] = response
        return response.status, response.data

    def parsed(name, call):
        try:
            value = call()
            check(name, True)
            return value
        except BrokerReadFailed as exc:
            check(name, False, "INCOMPLETE_TRANSACTION_HISTORY" if "INCOMPLETE" in str(exc) else "refused")
            return None

    try:
        # 1. identity
        status, data = get("ACCOUNT_SUMMARY")
        if status in (401, 403):
            report["stop_http_status"] = status     # 401: token not accepted; 403: token valid, account not its
            raise PreflightStop("CREDENTIALS_REJECTED")
        account = (data or {}).get("account") if isinstance(data, dict) else None
        if status != 200 or not isinstance(account, dict) or account.get("id") != account_id:
            raise PreflightStop("NOT_THE_CONFIGURED_PRACTICE_ACCOUNT")
        check("summary 200 for the configured account on the practice host", True)
        observed["summary_field_types"] = {k: type_name(account.get(k)) for k in (
            "id", "currency", "balance", "lastTransactionID", "openTradeCount", "openPositionCount",
            "pendingOrderCount", "hedgingEnabled", "marginRate")}
        observed["summary_top_level_keys"] = sorted(data)
        observed["currency"] = account.get("currency")
        observed["open_trade_count"] = account.get("openTradeCount")
        observed["pending_order_count"] = account.get("pendingOrderCount")
        observed["hedging_enabled"] = account.get("hedgingEnabled")
        summary = parsed("adapter.account_summary accepts the real summary", adapter.account_summary)
        if account.get("currency") != instrument[-3:]:
            report["blockers"].append("ACCOUNT_CURRENCY_%s_IS_NOT_THE_QUOTE_CURRENCY_OF_%s"
                                      % (account.get("currency"), instrument))
        if account.get("openTradeCount") not in (0, None) or account.get("pendingOrderCount") not in (0, None):
            report["blockers"].append("ACCOUNT_HAS_OPEN_TRADES_OR_PENDING_ORDERS")

        # 2. pricing
        status, data = get("PRICING", instrument=instrument)
        prices = (data or {}).get("prices") if isinstance(data, dict) else None
        p = prices[0] if isinstance(prices, list) and len(prices) == 1 and isinstance(prices[0], dict) else {}
        when = timeutil.parse_rfc3339(p.get("time"))
        frac = _FRACTION.search(p.get("time") or "")
        observed["pricing"] = {
            "status": status, "price_keys": sorted(p),
            "time_rfc3339_z": when is not None,
            "time_fraction_digits": len(frac.group(1)) if frac else 0,
            "tradeable_type": type_name(p.get("tradeable")), "tradeable": p.get("tradeable"),
            "bid_type": type_name(((p.get("bids") or [{}])[0] or {}).get("price")),
            "ask_type": type_name(((p.get("asks") or [{}])[0] or {}).get("price")),
            "quote_age_seconds": round((now() - when).total_seconds(), 1) if when else None,
        }
        parsed("adapter.quote accepts the real price", lambda: adapter.quote(instrument))

        # 3. open trades
        status, data = get("OPEN_TRADES")
        trades = (data or {}).get("trades") if isinstance(data, dict) else None
        check("openTrades returns a trades list", status == 200 and isinstance(trades, list))
        observed["open_trades_listed"] = len(trades) if isinstance(trades, list) else None

        # 4. history from the start
        status, data = get("TRANSACTIONS_SINCE", transaction_id="1")
        txns = (data or {}).get("transactions") if isinstance(data, dict) else None
        last = (data or {}).get("lastTransactionID") if isinstance(data, dict) else None
        history = {"status": status, "top_level_keys": sorted(data) if isinstance(data, dict) else None,
                   "lastTransactionID_type": type_name(last)}
        if status == 200 and isinstance(txns, list) and isinstance(last, str) and last.isdigit():
            ids = [int(t["id"]) for t in txns if isinstance(t, dict) and str(t.get("id", "")).isdigit()]
            expected = max(int(last) - 1, 0)
            history.update({"returned": len(txns), "expected_if_uncapped": expected,
                            "ids_all_digit_strings": len(ids) == len(txns),
                            "contiguous_from_2": ids == list(range(2, 2 + len(ids))),
                            "reaches_lastTransactionID": (ids[-1] == int(last)) if ids else expected == 0,
                            "types": sorted({t.get("type") for t in txns if isinstance(t, dict)})})
            history["capped_or_paged"] = history["returned"] < expected
            if history["capped_or_paged"]:
                report["blockers"].append("TRANSACTIONS_SINCE_RETURNED_%d_OF_%d"
                                          % (history["returned"], expected))
            sign, final_balance = _sign_model(txns)
            history["sign_model"] = sign
            history["order_fills"] = _fill_keys(txns)
            disagreed = sum(r["disagreed"] for r in sign.values())
            checked = sum(r["checked"] for r in sign.values())
            check("sign model agrees on every checkable balance change", disagreed == 0,
                  "%d checked, %d disagreed" % (checked, disagreed))
            # final stated balance vs the summary, at the same transaction
            if final_balance is not None and summary is not None:
                if summary.last_transaction_id != last:
                    get("ACCOUNT_SUMMARY")
                    summary = parsed("adapter.account_summary accepts the second summary",
                                     adapter.account_summary) or summary
                if summary.last_transaction_id == last:
                    check("last stated accountBalance equals the summary balance at the same transaction",
                          summary.balance == final_balance)
                else:
                    check("last stated accountBalance equals the summary balance at the same transaction",
                          False, "the account moved between reads")
        else:
            check("transactions/sinceid?id=1 returns a list and lastTransactionID", False,
                  "HTTP %s" % status)
        observed["history"] = history

        # 5 + 6. a client id that cannot exist, through M2's two-source resolution
        client_id = "MOGO-" + os.urandom(8).hex()
        status, data = get("ORDER_BY_CLIENT_ID", client_id=client_id)
        observed["missing_order_lookup"] = {"status": status,
                                            "keys": sorted(data) if isinstance(data, dict) else None,
                                            "errorCode": (data or {}).get("errorCode") if isinstance(data, dict) else None}
        check("a non-existent client order id answers 404", status == 404)
        if summary is not None:
            get("TRANSACTIONS_SINCE", transaction_id=summary.last_transaction_id)
            outcome = parsed("M2 resolution reads the real lookup and window", lambda: adapter.resolve_client_order(
                client_id, summary.last_transaction_id, 1))
            check("M2 resolution classifies the missing order ABSENT on real data",
                  outcome is not None and outcome.kind == "ABSENT", outcome.kind if outcome else "")
            parsed("adapter.transactions_since accepts the real window since the summary",
                   lambda: adapter.transactions_since(summary.last_transaction_id))
    except PreflightStop as stop:
        report["stop"] = stop.code
    except BrokerReadFailed:
        report["stop"] = "READ_FAILED"
    report["ok"] = report["stop"] is None and all(c["ok"] for c in checks)
    return report

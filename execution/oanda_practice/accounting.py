"""Fill-derived accounting for one practice trade. Pure: everything is passed in.

WHERE THE NUMBERS COME FROM. Entry price, exit price and P&L are read from the
broker's own transactions: the entry ORDER_FILL and the closing ORDER_FILL's
tradesClosed entry for our trade. Nothing here reads the authorised stop, a
target, a quote, or the simulated paper ledger, and nothing is computed from a
planned price.

THREE INDEPENDENT VIEWS MUST AGREE (Decimal throughout):

  1. the fills: realizedPL on the close equals (exit - entry) x signed units,
     to the precision the broker reports realizedPL in. The only tolerance
     anywhere is half a unit of that reported value's last digit, because the
     broker rounds a home-currency amount and the product of two prices is
     exact. No conversion rate is involved: M1/M2 only trade instruments quoted
     in the account currency;
  2. the transaction stream: walking every balance-changing transaction in the
     window from the balance recorded before the entry, each transaction's
     accountBalance equals the running balance plus its own effect;
  3. the account: the final balance equals the account summary's balance at
     the same lastTransactionID.

THE SIGN MODEL is one function, balance_effect(). It assumes the v20 convention
that a transaction's balance change is pl + financing - commission -
guaranteedExecutionFee. That is stated in the v20 schema, but it has not been
observed on the real practice account. View 2 tests exactly this assumption, so
a wrong model halts rather than producing a plausible figure. M3's read-only
preflight confirms it against real transactions.

The window may contain only our own activity. Our entry fill, our close fill,
our protective-order transactions, DAILY_FINANCING (attributable because the
executor refuses to trade while any other trade is open) and balance-neutral
bookkeeping are allowed. Anything else that moves the balance, such as a
transfer or another trade's fill, is FOREIGN_BALANCE_ACTIVITY, and nothing is
attributed.
"""
from decimal import Decimal, InvalidOperation

from .adapter import closing_entry

#: Transaction types that may appear in a trade's window without moving the balance.
BALANCE_NEUTRAL_TYPES = frozenset((
    "MARKET_ORDER", "STOP_LOSS_ORDER", "TAKE_PROFIT_ORDER", "ORDER_CANCEL",
    "TRADE_CLIENT_EXTENSIONS_MODIFY", "ORDER_CLIENT_EXTENSIONS_MODIFY",
))


class AccountingResult(object):
    def __init__(self, codes, **figures):
        self.codes = list(codes)
        self.figures = figures

    @property
    def ok(self):
        return not self.codes


def _dec(value):
    if not isinstance(value, str):
        return None
    try:
        d = Decimal(value)
    except InvalidOperation:
        return None
    return d if d.is_finite() else None


def balance_effect(txn):
    """The sign model, in one place: pl + financing - commission - guaranteedExecutionFee."""
    parts = {}
    for key in ("pl", "financing", "commission", "guaranteedExecutionFee"):
        if key in txn:
            parts[key] = _dec(txn[key])
            if parts[key] is None:
                return None
    if txn.get("type") == "ORDER_FILL" and not {"pl", "financing", "commission"} <= set(parts):
        return None                      # a fill must state every component; none is assumed 0
    if txn.get("type") == "DAILY_FINANCING" and "financing" not in parts:
        return None
    zero = Decimal(0)
    return (parts.get("pl", zero) + parts.get("financing", zero)
            - parts.get("commission", zero) - parts.get("guaranteedExecutionFee", zero))


def reconcile_trade(trade_id, signed_units, balance_before, window_txns, summary_balance,
                    summary_last_id, window_last_id):
    """Check one closed trade's accounting. Returns AccountingResult; codes empty means agreed."""
    codes = []
    if balance_before is None:
        return AccountingResult(["MISSING_BALANCE_BEFORE_ENTRY"])
    entry = [t for t in window_txns if t.get("type") == "ORDER_FILL"
             and (t.get("tradeOpened") or {}).get("tradeID") == trade_id]
    closes = [t for t in window_txns if t.get("type") == "ORDER_FILL"
              and closing_entry(t, trade_id)[0] is not None]
    if len(entry) != 1:
        codes.append("ENTRY_FILL_NOT_EXACTLY_ONE")
    if len(closes) != 1 or closing_entry(closes[0], trade_id)[0] != "CLOSED":
        codes.append("CLOSE_FILL_NOT_EXACTLY_ONE_FULL_CLOSE")
    if codes:
        return AccountingResult(codes)
    entry, close = entry[0], closes[0]
    _kind, closed = closing_entry(close, trade_id)

    entry_price = _dec(entry["tradeOpened"].get("price"))
    exit_price = _dec(closed.get("price"))
    realized = _dec(closed.get("realizedPL"))
    trade_financing = _dec(closed.get("financing", "0"))
    if None in (entry_price, exit_price, realized, trade_financing):
        return AccountingResult(["FILL_FIELDS_MISSING_OR_MALFORMED"])

    # View 1: the fills against themselves, to the broker's reported precision.
    half_unit = Decimal(1).scaleb(realized.as_tuple().exponent) / 2
    if abs(realized - (exit_price - entry_price) * Decimal(signed_units)) > half_unit:
        codes.append("REALIZED_PL_INCONSISTENT_WITH_FILL_PRICES")
    if _dec(close.get("pl")) != realized:
        codes.append("FILL_PL_DISAGREES_WITH_TRADE_REALIZED_PL")

    # View 2: the stream, transaction by transaction.
    running = balance_before
    financing = commission = fees = Decimal(0)
    last_balance_id = None
    for txn in window_txns:
        moves = "accountBalance" in txn
        ours = txn is entry or txn is close or txn.get("type") == "DAILY_FINANCING"
        if not moves:
            if txn.get("type") not in BALANCE_NEUTRAL_TYPES and not ours:
                codes.append("UNSUPPORTED_TRANSACTION_%s" % txn.get("type"))
            continue
        if not ours:
            codes.append("FOREIGN_BALANCE_ACTIVITY_%s" % txn.get("type"))
            continue
        effect = balance_effect(txn)
        stated = _dec(txn.get("accountBalance"))
        if effect is None or stated is None:
            codes.append("BALANCE_FIELDS_MISSING_ON_%s" % txn.get("id"))
            continue
        running += effect
        if running != stated:
            codes.append("BALANCE_DISCONTINUITY_AT_%s" % txn.get("id"))
            running = stated
        financing += _dec(txn.get("financing", "0")) or Decimal(0)
        commission += _dec(txn.get("commission", "0")) or Decimal(0)
        fees += _dec(txn.get("guaranteedExecutionFee", "0")) or Decimal(0)
        last_balance_id = txn.get("id")

    # View 3: the account itself, at the same point in the stream.
    if summary_last_id != window_last_id:
        codes.append("SUMMARY_AND_WINDOW_AT_DIFFERENT_TRANSACTIONS")
    elif summary_balance != running:
        codes.append("BALANCE_MISMATCH_WITH_ACCOUNT_SUMMARY")

    net = running - balance_before
    if net != realized + financing - commission - fees:
        codes.append("NET_PL_DOES_NOT_DECOMPOSE")
    return AccountingResult(codes, entry_price=entry_price, exit_price=exit_price,
                            realized_pl=realized, financing=financing, commission=commission,
                            fees=fees, net_pl=net, balance_before=balance_before,
                            balance_after=running, entry_fill_id=entry.get("id"),
                            close_fill_id=close.get("id"), close_reason=close.get("reason"),
                            last_balance_txn=last_balance_id)

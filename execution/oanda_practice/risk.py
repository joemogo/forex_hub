"""Pre-trade risk approval. Pure: every input is passed in, nothing is fetched.

Returns the list of refusal codes; an empty list approves. Every check runs,
so a refusal reports everything that was wrong, not merely the first thing.
The worst-case entry is the price bound (the order cannot fill beyond it), so
loss at the stop is computed from the bound, not from the quote. A stop can
gap; that residual is disclosed, not hidden, and is what M2's fill-derived
accounting measures.
"""
from decimal import Decimal

MAX_FUTURE_SKEW_SECONDS = 5
#: M4. The broker publishes no minimum distance for an ordinary stop-loss-on-fill, so the stop
#: must clear BOTH floors below, measured from the price it would trigger against. Too close a
#: stop is rejected by the broker at best and filled at once at worst; neither is a test of
#: anything. Raising either floor is safe; lowering one is a code change.
MIN_STOP_DISTANCE_PIPS = 5
MIN_STOP_SPREAD_MULTIPLE = 2


def price_bound(auth, quote):
    if auth.direction == "BUY":
        return quote.ask + auth.max_slippage
    return quote.bid - auth.max_slippage


def worst_case_loss(auth, quote):
    return abs(price_bound(auth, quote) - auth.stop_loss_price) * auth.units


def assess(auth, quote, account, broker_open_trades, journal_open_exposure, now):
    codes = []
    if account.currency != auth.instrument.split("_")[1]:
        codes.append("QUOTE_CURRENCY_IS_NOT_ACCOUNT_CURRENCY")
    if quote.instrument != auth.instrument:
        codes.append("QUOTE_FOR_ANOTHER_INSTRUMENT")
    if quote.tradeable is not True:
        codes.append("INSTRUMENT_NOT_TRADEABLE")
    age = (now - quote.time).total_seconds()
    if age > auth.max_quote_age_seconds:
        codes.append("QUOTE_STALE")
    if age < -MAX_FUTURE_SKEW_SECONDS:
        codes.append("QUOTE_FROM_THE_FUTURE_CLOCK_SKEW")
    if not quote.bid > 0 or not quote.ask >= quote.bid:
        codes.append("QUOTE_INVALID")
    elif quote.ask - quote.bid > auth.max_spread:
        codes.append("SPREAD_TOO_WIDE")
    bound = price_bound(auth, quote)
    if auth.direction == "BUY" and not auth.stop_loss_price < quote.bid:
        codes.append("STOP_ON_WRONG_SIDE")
    if auth.direction == "SELL" and not auth.stop_loss_price > quote.ask:
        codes.append("STOP_ON_WRONG_SIDE")
    if not bound > 0:
        codes.append("PRICE_BOUND_INVALID")
    if worst_case_loss(auth, quote) > auth.max_loss:
        codes.append("LOSS_AT_STOP_EXCEEDS_MAX_LOSS")
    if account.open_trade_count != 0 or broker_open_trades:
        codes.append("BROKER_ACCOUNT_HAS_OPEN_TRADES")
    if journal_open_exposure:
        codes.append("JOURNAL_HAS_OPEN_OR_UNRESOLVED_INTENT")
    return codes


def _decimals(value):
    return max(0, -value.as_tuple().exponent)


def assess_constraints(auth, quote, account, spec):
    """M4: the broker's own constraints, proven immediately before an entry. Fail closed.

    `spec` is the adapter's InstrumentSpec, or None when it could not be read, which refuses.
    """
    codes = []
    if account.pending_order_count is None:
        codes.append("PENDING_ORDERS_NOT_PROVEN_ZERO")
    elif account.pending_order_count != 0:
        codes.append("BROKER_ACCOUNT_HAS_PENDING_ORDERS")
    if spec is None or spec.instrument != auth.instrument:
        codes.append("INSTRUMENT_CONSTRAINTS_UNPROVEN")
        return codes
    units = Decimal(auth.units)
    if units < spec.minimum_trade_size:
        codes.append("UNITS_BELOW_BROKER_MINIMUM")
    if units > spec.maximum_order_units:
        codes.append("UNITS_ABOVE_BROKER_MAXIMUM")
    if _decimals(units) > spec.trade_units_precision:
        codes.append("UNITS_PRECISION_EXCEEDED")
    if _decimals(auth.stop_loss_price) > spec.display_precision:
        codes.append("STOP_PRICE_PRECISION_EXCEEDED")
    if _decimals(price_bound(auth, quote)) > spec.display_precision:
        codes.append("PRICE_BOUND_PRECISION_EXCEEDED")
    trigger = quote.bid if auth.direction == "BUY" else quote.ask
    distance = abs(trigger - auth.stop_loss_price)
    pip = Decimal(1).scaleb(spec.pip_location)
    if distance < MIN_STOP_DISTANCE_PIPS * pip or distance < MIN_STOP_SPREAD_MULTIPLE * (quote.ask - quote.bid):
        codes.append("STOP_TOO_CLOSE_TO_MARKET")
    return codes


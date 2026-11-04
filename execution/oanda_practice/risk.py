"""Pre-trade risk approval. Pure: every input is passed in, nothing is fetched.

Returns the list of refusal codes; an empty list approves. Every check runs,
so a refusal reports everything that was wrong, not merely the first thing.
The worst-case entry is the price bound (the order cannot fill beyond it), so
loss at the stop is computed from the bound, not from the quote. A stop can
gap; that residual is disclosed, not hidden, and is what M2's fill-derived
accounting measures.
"""
MAX_FUTURE_SKEW_SECONDS = 5


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


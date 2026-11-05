"""The operator's one-shot authorization for one practice order.

Nothing is submitted without one. It names the account, the instrument, the
direction, the exact units, the protective stop and the limits, and it expires.
Its authorizationId is consumed by the journal at the moment an order is
recorded as SUBMITTING, so the same file can never place a second order --
not after a crash, not after a refusal-then-retry, not ever.

M1 accepts only instruments whose QUOTE currency equals the account currency,
so loss at the stop is units x price distance exactly, with no conversion rate
(the MOGO-024 D1 cross-rate pip-value defect class cannot arise).
"""
import datetime
import hashlib
import json
import re
from decimal import Decimal, InvalidOperation

from . import config as cfg
from . import timeutil
from .errors import AuthorizationRefused

#: Hard ceilings, independent of any authorization. Raising them is a code change.
HARD_MAX_UNITS = 1000
HARD_MAX_LOSS = Decimal("5")       # M4: the first practice trade's fixed virtual-risk cap
HARD_MAX_LIFETIME = datetime.timedelta(hours=24)
HARD_MAX_QUOTE_AGE_SECONDS = 30

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{7,63}$")
_INSTRUMENT_RE = re.compile(r"^[A-Z]{3}_[A-Z]{3}$")
_FIELDS = ("authorizationId", "mode", "accountId", "instrument", "direction", "units",
           "stopLossPrice", "maxSlippage", "maxSpread", "maxLoss", "maxQuoteAgeSeconds",
           "issuedAt", "expiresAt", "issuedBy")


def _dec(data, key):
    value = data.get(key)
    if not isinstance(value, str):
        raise AuthorizationRefused("%s must be a decimal string" % key)
    try:
        result = Decimal(value)
    except InvalidOperation:
        raise AuthorizationRefused("%s is not a decimal" % key)
    if not result.is_finite() or result <= 0:
        raise AuthorizationRefused("%s must be positive" % key)
    return result


class Authorization(object):
    def __init__(self, data, raw_bytes):
        self.data = data
        self.raw_sha256 = hashlib.sha256(raw_bytes).hexdigest()
        self.authorization_id = data["authorizationId"]
        self.account_id = data["accountId"]
        self.instrument = data["instrument"]
        self.direction = data["direction"]
        self.units = data["units"]
        self.stop_loss_price = _dec(data, "stopLossPrice")
        self.max_slippage = _dec(data, "maxSlippage")
        self.max_spread = _dec(data, "maxSpread")
        self.max_loss = _dec(data, "maxLoss")
        self.max_quote_age_seconds = data["maxQuoteAgeSeconds"]
        self.issued_at = timeutil.parse_rfc3339(data["issuedAt"])
        self.expires_at = timeutil.parse_rfc3339(data["expiresAt"])

    @property
    def intent_id(self):
        """Deterministic: the same authorization always maps to the same order identity."""
        return hashlib.sha256(("MOGO-PRACTICE|" + self.authorization_id).encode()).hexdigest()[:16]

    @property
    def client_order_id(self):
        return "MOGO-" + self.intent_id

    @property
    def signed_units(self):
        return self.units if self.direction == "BUY" else -self.units


def parse_authorization(raw_bytes):
    try:
        data = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise AuthorizationRefused("authorization is not JSON")
    if not isinstance(data, dict):
        raise AuthorizationRefused("authorization must be an object")
    unknown = sorted(set(data) - set(_FIELDS))
    missing = sorted(set(_FIELDS) - set(data))
    if unknown or missing:
        raise AuthorizationRefused("authorization fields: missing %s, unknown %s" % (missing, unknown))
    if data["mode"] != cfg.MODE:
        raise AuthorizationRefused("authorization mode must be %s" % cfg.MODE)
    if not isinstance(data["authorizationId"], str) or not _ID_RE.match(data["authorizationId"]):
        raise AuthorizationRefused("authorizationId has the wrong shape")
    if not isinstance(data["instrument"], str) or not _INSTRUMENT_RE.match(data["instrument"]):
        raise AuthorizationRefused("instrument has the wrong shape")
    if data["direction"] not in ("BUY", "SELL"):
        raise AuthorizationRefused("direction must be BUY or SELL")
    units = data["units"]
    if not isinstance(units, int) or isinstance(units, bool) or not 1 <= units <= HARD_MAX_UNITS:
        raise AuthorizationRefused("units must be an integer in [1, %d]" % HARD_MAX_UNITS)
    age = data["maxQuoteAgeSeconds"]
    if not isinstance(age, int) or isinstance(age, bool) or not 1 <= age <= HARD_MAX_QUOTE_AGE_SECONDS:
        raise AuthorizationRefused("maxQuoteAgeSeconds must be in [1, %d]" % HARD_MAX_QUOTE_AGE_SECONDS)
    if not isinstance(data["issuedBy"], str) or not data["issuedBy"].strip():
        raise AuthorizationRefused("issuedBy must name the operator")
    auth = Authorization(data, raw_bytes)
    if auth.issued_at is None or auth.expires_at is None:
        raise AuthorizationRefused("issuedAt/expiresAt must be RFC3339 UTC")
    if auth.expires_at <= auth.issued_at or auth.expires_at - auth.issued_at > HARD_MAX_LIFETIME:
        raise AuthorizationRefused("authorization lifetime must be positive and at most 24h")
    if auth.max_loss > HARD_MAX_LOSS:
        raise AuthorizationRefused("maxLoss exceeds the hard ceiling %s" % HARD_MAX_LOSS)
    return auth


def check_current(auth, config, now):
    """The checks that depend on the moment and the configured account."""
    if auth.account_id != config.account_id:
        raise AuthorizationRefused("authorization names a different account")
    if not auth.issued_at <= now < auth.expires_at:
        raise AuthorizationRefused("authorization is not valid at this time")


# ---- M4: the separate close authorization ------------------------------------------------
_CLOSE_FIELDS = ("closeAuthorizationId", "mode", "accountId", "clientOrderId", "tradeId",
                 "issuedAt", "expiresAt", "issuedBy")
_CLIENT_ID_RE = re.compile(r"^MOGO-[0-9a-f]{16}$")
_TRADE_ID_RE = re.compile(r"^[0-9]{1,18}$")


class CloseAuthorization(object):
    """The operator's one-shot authorization to close ONE identified practice trade.

    It names the trade twice -- by MOGO's client order id and by the broker's trade
    id -- and both must match the journal's position. Consumed by the journal when
    the close is recorded as CLOSING, so it closes at most once.
    """

    def __init__(self, data, raw_bytes):
        self.data = data
        self.raw_sha256 = hashlib.sha256(raw_bytes).hexdigest()
        self.close_authorization_id = data["closeAuthorizationId"]
        self.account_id = data["accountId"]
        self.client_order_id = data["clientOrderId"]
        self.trade_id = data["tradeId"]
        self.issued_at = timeutil.parse_rfc3339(data["issuedAt"])
        self.expires_at = timeutil.parse_rfc3339(data["expiresAt"])


def parse_close_authorization(raw_bytes):
    try:
        data = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise AuthorizationRefused("close authorization is not JSON")
    if not isinstance(data, dict):
        raise AuthorizationRefused("close authorization must be an object")
    unknown = sorted(set(data) - set(_CLOSE_FIELDS))
    missing = sorted(set(_CLOSE_FIELDS) - set(data))
    if unknown or missing:
        raise AuthorizationRefused("close authorization fields: missing %s, unknown %s" % (missing, unknown))
    if data["mode"] != cfg.MODE:
        raise AuthorizationRefused("close authorization mode must be %s" % cfg.MODE)
    if not isinstance(data["closeAuthorizationId"], str) or not _ID_RE.match(data["closeAuthorizationId"]):
        raise AuthorizationRefused("closeAuthorizationId has the wrong shape")
    if not isinstance(data["clientOrderId"], str) or not _CLIENT_ID_RE.match(data["clientOrderId"]):
        raise AuthorizationRefused("clientOrderId has the wrong shape")
    if not isinstance(data["tradeId"], str) or not _TRADE_ID_RE.match(data["tradeId"]):
        raise AuthorizationRefused("tradeId has the wrong shape")
    if not isinstance(data["issuedBy"], str) or not data["issuedBy"].strip():
        raise AuthorizationRefused("issuedBy must name the operator")
    auth = CloseAuthorization(data, raw_bytes)
    if auth.issued_at is None or auth.expires_at is None:
        raise AuthorizationRefused("issuedAt/expiresAt must be RFC3339 UTC")
    if auth.expires_at <= auth.issued_at or auth.expires_at - auth.issued_at > HARD_MAX_LIFETIME:
        raise AuthorizationRefused("close authorization lifetime must be positive and at most 24h")
    return auth


def check_close_current(close_auth, config, now, position, client_order_id):
    """The close authorization must name this account, this moment, and exactly this position."""
    if not isinstance(close_auth, CloseAuthorization):
        raise AuthorizationRefused("closing needs a close authorization")
    if close_auth.account_id != config.account_id:
        raise AuthorizationRefused("close authorization names a different account")
    if not close_auth.issued_at <= now < close_auth.expires_at:
        raise AuthorizationRefused("close authorization is not valid at this time")
    if close_auth.trade_id != position["trade_id"] or close_auth.client_order_id != client_order_id:
        raise AuthorizationRefused("close authorization names a different trade")

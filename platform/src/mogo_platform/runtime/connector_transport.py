#!/usr/bin/env python3
"""MOGO Automation Platform -- bounded outbound transport (MOGO-015 Step 3).

AUTHORITY
    MOGO-015 Step 2 (connector authorization gate, commit a811127)
    Step 3 authorization
    Architecture section 32 item 5 -- the policy gate precedes ANY connector

THIS MODULE IS SUBORDINATE, NOT ADJACENT

    It is the only place in MOGO that opens an outbound socket, and it cannot
    be asked to fetch anything. `acquire()` takes a REQUEST -- a source identity
    and a resource identifier -- calls the Step 2 gate, and opens a connection
    only if the gate returns a permit. The URL it fetches is the one the PERMIT
    carries, never one an argument supplied.

    There is deliberately no function here that accepts a URL. Adding one would
    turn this module into the generic fetch primitive the whole design exists to
    prevent, so the absence is the safety property and a test asserts it.

WHAT IT ENFORCES, ALL FROM THE PERMIT

    https only · the derived destination · redirects refused by a handler that
    raises rather than follows · a hard timeout · a response read that STOPS at
    the permitted byte count rather than reading and then checking · the
    permitted content type · an explicit status allow-list · a bounded
    User-Agent that identifies MOGO honestly.

FAILURE CLASSIFICATION IS PART OF THE CONTRACT

    Transient (retryable): connection failure, timeout, 5xx, 429.
    Permanent (never retried): authorization denial, 4xx other than 429,
    oversized response, wrong content type, malformed body, redirect attempt.

    A permanent failure that retried would hammer an external service for no
    possible benefit; a transient one that did not would make MOGO fragile. The
    split is data, below, so it can be read without tracing code.
"""

import hashlib
import json
import os
import socket
import ssl
import urllib.error
import urllib.request

from . import connector_authorization as gate  # noqa: E402
from . import errors as runtime_errors  # noqa: E402

TRANSPORT_VERSION = "1.0.0"

# Identifies MOGO honestly and carries no tracking. Bounded and constant: a
# caller-controlled User-Agent is a caller-controlled request header.
USER_AGENT = "MOGO-research/1.0 (governed research acquisition; contact: operator)"

DEFAULT_TIMEOUT_SECONDS = 10
MAX_TIMEOUT_SECONDS = 30

ACCEPTABLE_STATUSES = (200,)

# Failure classes. Data, not scattered conditionals.
TRANSIENT = "transient"
PERMANENT = "permanent"

TRANSIENT_STATUSES = (429, 500, 502, 503, 504, 507, 508, 509)

REASON_NOT_PERMITTED = "authorization_denied"
REASON_REDIRECT_ATTEMPTED = "redirect_attempted"
REASON_OVERSIZED = "response_exceeded_permitted_size"
REASON_WRONG_CONTENT_TYPE = "unexpected_content_type"
REASON_BAD_STATUS = "unacceptable_http_status"
REASON_MALFORMED_BODY = "malformed_response_body"
REASON_CONNECTION_FAILED = "connection_failed"
REASON_TIMEOUT = "request_timed_out"


class AcquisitionOutcome(object):
    """One acquisition attempt, successful or not."""

    __slots__ = ("ok", "failureClass", "reason", "detail", "sourceId",
                 "authorizationId", "connectorId", "transportVersion",
                 "requestedUrl", "finalUrl", "httpStatus", "contentType",
                 "byteLength", "contentHash", "rawBytes", "acquiredAt",
                 "decision")

    def __init__(self, ok, **fields):
        self.ok = ok
        self.failureClass = fields.get("failureClass")
        self.reason = fields.get("reason")
        self.detail = fields.get("detail")
        self.sourceId = fields.get("sourceId")
        self.authorizationId = fields.get("authorizationId")
        self.connectorId = fields.get("connectorId")
        self.transportVersion = TRANSPORT_VERSION
        self.requestedUrl = fields.get("requestedUrl")
        self.finalUrl = fields.get("finalUrl")
        self.httpStatus = fields.get("httpStatus")
        self.contentType = fields.get("contentType")
        self.byteLength = fields.get("byteLength")
        self.contentHash = fields.get("contentHash")
        self.rawBytes = fields.get("rawBytes")
        self.acquiredAt = fields.get("acquiredAt")
        self.decision = fields.get("decision")

    def as_record(self, include_raw=False):
        """Auditable record. Raw bytes are excluded unless asked for, so a log
        line never accidentally carries a payload."""
        record = {name: getattr(self, name) for name in self.__slots__
                  if name != "rawBytes"}
        record["decision"] = (self.decision.as_record()
                              if self.decision is not None else None)
        if include_raw:
            record["rawBytes"] = self.rawBytes
        return record


class _NoRedirects(urllib.request.HTTPRedirectHandler):
    """Refuses every redirect by raising.

    Not `followRedirects=False` on a client that might quietly return the 3xx --
    a handler that RAISES, so a redirect can never be mistaken for a body. The
    Step 2 gate re-validates redirect destinations and currently permits none.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(
            req.full_url, code,
            "redirect to %r refused: this connector authorizes no redirects"
            % (newurl,), headers, fp)


# TLS trust. This Python build ships no CA bundle, so verification must be
# pointed at the system store EXPLICITLY. It is never disabled: an unverified
# TLS connection to a research source would make every provenance claim about
# that source worthless, and `ssl._create_unverified_context` appears nowhere in
# this file by design.
SYSTEM_CA_BUNDLES = ("/etc/ssl/cert.pem", "/private/etc/ssl/cert.pem")


def _tls_context():
    context = ssl.create_default_context()
    if context.get_ca_certs():
        return context                      # the build already trusts a store
    for bundle in SYSTEM_CA_BUNDLES:
        if os.path.exists(bundle):
            return ssl.create_default_context(cafile=bundle)
    # No trust store: FAIL rather than fall back to an unverified connection.
    runtime_errors.fail(
        "no CA trust store is available; refusing to open an unverified TLS "
        "connection", runtime_errors.ContractValidationError)


def _opener():
    """An opener with NO redirect handling and no proxy/auth handlers."""
    return urllib.request.build_opener(
        _NoRedirects, urllib.request.HTTPSHandler(context=_tls_context()))


def content_hash(raw):
    """Deterministic identity of the acquired bytes. Never a timestamp."""
    return hashlib.sha256(raw).hexdigest()


def _fail(outcome_fields, failure_class, reason, detail=None):
    fields = dict(outcome_fields)
    fields.update({"failureClass": failure_class, "reason": reason,
                   "detail": detail})
    return AcquisitionOutcome(False, **fields)


def acquire(request, now_iso=None, opener=None, timeout_seconds=None):
    """THE ONLY OUTBOUND PATH. Authorization first; transport only on a permit.

    `opener` exists so tests can substitute a double. It is never used to change
    WHERE the request goes -- the URL still comes from the permit.
    """
    decision = gate.evaluate(request)
    base = {"sourceId": decision.sourceId,
            "authorizationId": decision.authorizationId,
            "connectorId": decision.connectorId,
            "requestedUrl": decision.approvedUrl,
            "decision": decision,
            "acquiredAt": now_iso}

    # ── NO PERMIT, NO NETWORK. Returns before any opener exists. ──
    if not decision.permitted:
        return _fail(base, PERMANENT, REASON_NOT_PERMITTED, decision.reason)

    limits = decision.limits or {}
    max_bytes = int(limits.get("maxResponseBytes") or 0)
    expected_type = limits.get("expectedContentType")

    timeout = timeout_seconds if timeout_seconds is not None else DEFAULT_TIMEOUT_SECONDS
    if not isinstance(timeout, (int, float)) or timeout <= 0 or timeout > MAX_TIMEOUT_SECONDS:
        runtime_errors.fail(
            "timeout %r is outside the permitted 0 < t <= %d seconds"
            % (timeout, MAX_TIMEOUT_SECONDS),
            runtime_errors.ContractValidationError)

    url = decision.approvedUrl          # from the PERMIT, never from an argument
    http_request = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": expected_type or "application/json",
    })

    use_opener = opener if opener is not None else _opener()
    try:
        response = use_opener.open(http_request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        status = getattr(exc, "code", None)
        if "redirect" in str(exc).lower():
            return _fail(dict(base, httpStatus=status), PERMANENT,
                         REASON_REDIRECT_ATTEMPTED, str(exc))
        klass = TRANSIENT if status in TRANSIENT_STATUSES else PERMANENT
        return _fail(dict(base, httpStatus=status), klass, REASON_BAD_STATUS,
                     "HTTP %s" % (status,))
    except (urllib.error.URLError, socket.timeout, TimeoutError) as exc:
        reason = REASON_TIMEOUT if isinstance(exc, (socket.timeout, TimeoutError)) \
            else REASON_CONNECTION_FAILED
        if isinstance(exc, urllib.error.URLError) and isinstance(
                getattr(exc, "reason", None), (socket.timeout, TimeoutError)):
            reason = REASON_TIMEOUT
        return _fail(base, TRANSIENT, reason, str(exc))

    try:
        status = getattr(response, "status", None)
        if status is None:
            status = response.getcode()
        headers = response.headers
        content_type = (headers.get("Content-Type") or "").split(";")[0].strip()
        final_url = getattr(response, "url", None) or url

        # The destination must still be the authorized one after the fact. A
        # transport double, or a future client that silently followed a hop,
        # cannot change where the bytes came from without being caught here.
        if final_url != url:
            return _fail(dict(base, httpStatus=status, finalUrl=final_url),
                         PERMANENT, REASON_REDIRECT_ATTEMPTED,
                         "final URL %r is not the authorized destination" % (final_url,))

        if status not in ACCEPTABLE_STATUSES:
            klass = TRANSIENT if status in TRANSIENT_STATUSES else PERMANENT
            return _fail(dict(base, httpStatus=status, finalUrl=final_url),
                         klass, REASON_BAD_STATUS, "HTTP %s" % (status,))

        if expected_type and content_type != expected_type:
            return _fail(dict(base, httpStatus=status, finalUrl=final_url,
                              contentType=content_type),
                         PERMANENT, REASON_WRONG_CONTENT_TYPE, content_type)

        # STOP at the cap rather than reading everything and then measuring.
        # One extra byte is requested purely to detect truncation.
        raw = response.read(max_bytes + 1) if max_bytes else response.read()
        if max_bytes and len(raw) > max_bytes:
            return _fail(dict(base, httpStatus=status, finalUrl=final_url,
                              contentType=content_type, byteLength=len(raw)),
                         PERMANENT, REASON_OVERSIZED,
                         "response exceeded %d bytes" % (max_bytes,))
        if not raw:
            return _fail(dict(base, httpStatus=status, finalUrl=final_url,
                              contentType=content_type, byteLength=0),
                         PERMANENT, REASON_MALFORMED_BODY, "empty body")
        try:
            json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            return _fail(dict(base, httpStatus=status, finalUrl=final_url,
                              contentType=content_type, byteLength=len(raw)),
                         PERMANENT, REASON_MALFORMED_BODY, str(exc))
    finally:
        try:
            response.close()
        except Exception:                    # noqa: BLE001
            pass

    return AcquisitionOutcome(
        True, sourceId=decision.sourceId, authorizationId=decision.authorizationId,
        connectorId=decision.connectorId, requestedUrl=url, finalUrl=final_url,
        httpStatus=status, contentType=content_type, byteLength=len(raw),
        contentHash=content_hash(raw), rawBytes=raw, acquiredAt=now_iso,
        decision=decision)

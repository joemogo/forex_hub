#!/usr/bin/env python3
"""MOGO-015 Step 3 -- the bounded outbound transport.

Every failure and retry proof uses a test double. The live external service is
contacted exactly once, in the controlled Step 3 proof, and never from here.
"""

import io
import json
import os
import socket
import sys
import unittest
import urllib.error

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "platform", "src"))

from mogo_platform.runtime import connector_authorization as ca   # noqa: E402
from mogo_platform.runtime import connector_transport as ct       # noqa: E402
from mogo_platform.runtime import errors as runtime_errors        # noqa: E402

APPROVED_SOURCE = "SRC|youtube-channel|UCgPeeHdxYRal0HTNeAkjqLg"
GOOD_AUTH = "9e24aa04-c7b5-4438-acaf-c709cd8796b5"
GOOD_VIDEO = "hb7ot1_szWI"
BODY = json.dumps({"title": "x", "author_name": "fxalexg "}).encode("utf-8")


def request(**over):
    base = {"sourceId": APPROVED_SOURCE, "authorizationId": GOOD_AUTH,
            "capabilityId": "CAP|research|acquire-approved-source-metadata",
            "capabilityVersion": "1.0.0", "operation": "metadata",
            "resourceId": GOOD_VIDEO, "decidedAt": "2026-08-11T00:00:00.000Z"}
    base.update(over)
    return base


class FakeResponse(object):
    def __init__(self, body=BODY, status=200, content_type="application/json",
                 url=None):
        self._stream = io.BytesIO(body)
        self.status = status
        self.headers = {"Content-Type": content_type}
        self.url = url if url is not None else ct.gate.derive_destination(
            APPROVED_SOURCE, GOOD_VIDEO)[0]

    def read(self, size=-1):
        return self._stream.read(size) if size and size > 0 else self._stream.read()

    def getcode(self):
        return self.status

    def close(self):
        pass


class SpyOpener(object):
    """Records every call. Raises on demand to model failures."""

    def __init__(self, response=None, raises=None, sequence=None):
        self.calls = []
        self._response = response
        self._raises = raises
        self._sequence = list(sequence or [])

    def open(self, request_obj, timeout=None):
        self.calls.append({"url": request_obj.full_url, "timeout": timeout,
                           "headers": dict(request_obj.headers)})
        if self._sequence:
            nxt = self._sequence.pop(0)
            if isinstance(nxt, Exception):
                raise nxt
            return nxt
        if self._raises is not None:
            raise self._raises
        return self._response if self._response is not None else FakeResponse()


class TestAuthorizationPrecedesTransport(unittest.TestCase):

    def test_no_permit_means_no_transport_call(self):
        denied = [request(sourceId="SRC|evil|x"), request(authorizationId=None),
                  request(authorizationId="nope"), request(operation="transcript"),
                  request(resourceId="../../etc/passwd"),
                  request(requestedUrl="https://evil.example/steal"),
                  request(followRedirects=True), request(sourceId=None)]
        for req in denied:
            with self.subTest(request=req):
                spy = SpyOpener()
                outcome = ct.acquire(req, opener=spy)
                self.assertFalse(outcome.ok)
                self.assertEqual(outcome.reason, ct.REASON_NOT_PERMITTED)
                self.assertEqual(outcome.failureClass, ct.PERMANENT,
                                 "a denial must never be retried")
                self.assertEqual(spy.calls, [], "TRANSPORT WAS INVOKED")

    def test_a_valid_permit_can_reach_the_transport(self):
        spy = SpyOpener()
        outcome = ct.acquire(request(), opener=spy)
        self.assertTrue(outcome.ok, outcome.reason)
        self.assertEqual(len(spy.calls), 1)
        self.assertTrue(spy.calls[0]["url"].startswith(
            "https://www.youtube.com/oembed"))

    def test_the_transport_exposes_no_url_accepting_entry_point(self):
        """The absence of a fetch(url) function IS the safety property."""
        import inspect
        for name, obj in vars(ct).items():
            if not inspect.isfunction(obj) or name.startswith("_"):
                continue
            params = list(inspect.signature(obj).parameters)
            with self.subTest(function=name):
                self.assertNotIn("url", params,
                                 "no public transport function may accept a URL")


class TestDestinationCannotBeSubstituted(unittest.TestCase):

    def test_the_fetched_url_comes_from_the_permit(self):
        spy = SpyOpener()
        ct.acquire(request(), opener=spy)
        derived, _ = ca.derive_destination(APPROVED_SOURCE, GOOD_VIDEO)
        self.assertEqual(spy.calls[0]["url"], derived)

    def test_a_final_url_that_moved_is_rejected_after_the_fact(self):
        spy = SpyOpener(response=FakeResponse(url="https://evil.example/x"))
        outcome = ct.acquire(request(), opener=spy)
        self.assertFalse(outcome.ok)
        self.assertEqual(outcome.reason, ct.REASON_REDIRECT_ATTEMPTED)
        self.assertEqual(outcome.failureClass, ct.PERMANENT)

    def test_a_redirect_raises_rather_than_being_followed(self):
        handler = ct._NoRedirects()
        with self.assertRaises(urllib.error.HTTPError):
            handler.redirect_request(
                urllib.request.Request("https://www.youtube.com/oembed"),
                None, 302, "Found", {}, "https://evil.example/")


class TestBoundedTransport(unittest.TestCase):

    def test_the_timeout_is_bounded_and_passed_to_the_transport(self):
        spy = SpyOpener()
        ct.acquire(request(), opener=spy)
        self.assertEqual(spy.calls[0]["timeout"], ct.DEFAULT_TIMEOUT_SECONDS)
        self.assertLessEqual(ct.DEFAULT_TIMEOUT_SECONDS, ct.MAX_TIMEOUT_SECONDS)
        for bad in (0, -1, 600, ct.MAX_TIMEOUT_SECONDS + 1, "ten", None):
            if bad is None:
                continue
            with self.subTest(timeout=bad):
                with self.assertRaises(runtime_errors.ContractValidationError):
                    ct.acquire(request(), opener=SpyOpener(),
                               timeout_seconds=bad)

    def test_an_oversized_response_is_rejected(self):
        limits = ca.evaluate(request()).limits
        oversized = b"{" + b"x" * (limits["maxResponseBytes"] + 10) + b"}"
        outcome = ct.acquire(request(),
                             opener=SpyOpener(response=FakeResponse(body=oversized)))
        self.assertFalse(outcome.ok)
        self.assertEqual(outcome.reason, ct.REASON_OVERSIZED)
        self.assertEqual(outcome.failureClass, ct.PERMANENT)

    def test_an_incorrect_content_type_is_rejected(self):
        for bad in ("text/html", "application/xml", "text/plain", ""):
            with self.subTest(contentType=bad):
                outcome = ct.acquire(request(), opener=SpyOpener(
                    response=FakeResponse(content_type=bad)))
                self.assertFalse(outcome.ok)
                self.assertEqual(outcome.reason, ct.REASON_WRONG_CONTENT_TYPE)
                self.assertEqual(outcome.failureClass, ct.PERMANENT)

    def test_a_malformed_or_empty_body_is_rejected(self):
        for body in (b"", b"not json", b"{unclosed", b"\xff\xfe"):
            with self.subTest(body=body):
                outcome = ct.acquire(request(),
                                     opener=SpyOpener(response=FakeResponse(body=body)))
                self.assertFalse(outcome.ok)
                self.assertEqual(outcome.reason, ct.REASON_MALFORMED_BODY)
                self.assertEqual(outcome.failureClass, ct.PERMANENT)

    def test_the_user_agent_is_bounded_and_honest(self):
        spy = SpyOpener()
        ct.acquire(request(), opener=spy)
        agent = spy.calls[0]["headers"].get("User-agent") or \
            spy.calls[0]["headers"].get("User-Agent")
        self.assertIn("MOGO-research", agent)
        self.assertLess(len(agent), 200)


class TestFailureClassification(unittest.TestCase):

    def test_permanent_http_failures_are_not_retryable(self):
        for status in (400, 401, 403, 404, 410, 451):
            with self.subTest(status=status):
                err = urllib.error.HTTPError(
                    "https://www.youtube.com/oembed", status, "no", {}, None)
                outcome = ct.acquire(request(), opener=SpyOpener(raises=err))
                self.assertFalse(outcome.ok)
                self.assertEqual(outcome.failureClass, ct.PERMANENT,
                                 "a 4xx must never be retried forever")

    def test_transient_statuses_are_retryable(self):
        for status in (429, 500, 502, 503, 504):
            with self.subTest(status=status):
                err = urllib.error.HTTPError(
                    "https://www.youtube.com/oembed", status, "busy", {}, None)
                outcome = ct.acquire(request(), opener=SpyOpener(raises=err))
                self.assertFalse(outcome.ok)
                self.assertEqual(outcome.failureClass, ct.TRANSIENT)

    def test_connection_failure_and_timeout_are_transient(self):
        for exc, reason in ((urllib.error.URLError("refused"), ct.REASON_CONNECTION_FAILED),
                            (socket.timeout("slow"), ct.REASON_TIMEOUT),
                            (urllib.error.URLError(socket.timeout("slow")), ct.REASON_TIMEOUT)):
            with self.subTest(exc=type(exc).__name__):
                outcome = ct.acquire(request(), opener=SpyOpener(raises=exc))
                self.assertFalse(outcome.ok)
                self.assertEqual(outcome.failureClass, ct.TRANSIENT)
                self.assertEqual(outcome.reason, reason)

    def test_a_transient_failure_then_success_models_bounded_retry(self):
        """The runtime owns retry; this proves the transport reports a class the
        runtime can act on, and that a retry succeeds without special casing."""
        spy = SpyOpener(sequence=[urllib.error.URLError("refused"), FakeResponse()])
        first = ct.acquire(request(), opener=spy)
        self.assertFalse(first.ok)
        self.assertEqual(first.failureClass, ct.TRANSIENT)
        second = ct.acquire(request(), opener=spy)
        self.assertTrue(second.ok, second.reason)
        self.assertEqual(len(spy.calls), 2, "exactly two attempts, not a loop")


class TestRawBytesAndIdentity(unittest.TestCase):

    def test_raw_bytes_and_deterministic_hash_are_preserved(self):
        import hashlib
        outcome = ct.acquire(request(), opener=SpyOpener(response=FakeResponse()))
        self.assertTrue(outcome.ok)
        self.assertEqual(outcome.rawBytes, BODY)
        self.assertEqual(outcome.byteLength, len(BODY))
        self.assertEqual(outcome.contentHash, hashlib.sha256(BODY).hexdigest())

    def test_identity_is_content_not_time(self):
        a = ct.acquire(request(), opener=SpyOpener(response=FakeResponse()),
                       now_iso="2026-01-01T00:00:00.000Z")
        b = ct.acquire(request(), opener=SpyOpener(response=FakeResponse()),
                       now_iso="2099-12-31T23:59:59.000Z")
        self.assertEqual(a.contentHash, b.contentHash,
                         "identical bytes must hash identically regardless of time")
        changed = ct.acquire(request(), opener=SpyOpener(
            response=FakeResponse(body=b'{"title":"different"}')))
        self.assertNotEqual(a.contentHash, changed.contentHash,
                            "changed content must be new content, not a duplicate")

    def test_the_audit_record_excludes_raw_bytes_by_default(self):
        record = ct.acquire(request(), opener=SpyOpener()).as_record()
        self.assertNotIn("rawBytes", record)
        for field in ("sourceId", "authorizationId", "connectorId",
                      "transportVersion", "requestedUrl", "finalUrl",
                      "httpStatus", "contentType", "byteLength", "contentHash"):
            self.assertIn(field, record)
        self.assertIn("rawBytes", ct.acquire(
            request(), opener=SpyOpener()).as_record(include_raw=True))


class TestScientificFirewall(unittest.TestCase):

    def test_the_transport_references_nothing_in_the_trading_lane(self):
        path = os.path.join(REPO_ROOT, "platform", "src", "mogo_platform",
                            "runtime", "connector_transport.py")
        with open(path, "r", encoding="utf-8") as handle:
            source = handle.read()
        for forbidden in ("index.html", "alexG", "localStorage", "indexedDB",
                          "paperAccount", "alexGAutoTrading"):
            self.assertNotIn(forbidden, source)

    def test_the_transport_calls_the_gate_before_anything_else(self):
        import ast
        path = os.path.join(REPO_ROOT, "platform", "src", "mogo_platform",
                            "runtime", "connector_transport.py")
        with open(path, "r", encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        acquire_fn = next(node for node in ast.walk(tree)
                          if isinstance(node, ast.FunctionDef)
                          and node.name == "acquire")
        body = list(acquire_fn.body)
        if (isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)):
            body.pop(0)          # the docstring is not a statement that acts
        first = body[0]
        self.assertIsInstance(first, ast.Assign)
        self.assertIn("gate.evaluate", ast.unparse(first.value),
                      "the FIRST statement of acquire() must be the gate call")


if __name__ == "__main__":
    unittest.main()

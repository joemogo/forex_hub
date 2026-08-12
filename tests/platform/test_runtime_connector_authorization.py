#!/usr/bin/env python3
"""MOGO-015 Step 2 -- the connector authorization gate.

The property under test is not "the gate returns sensible values". It is that
NO NETWORK EFFECT CAN OCCUR WITHOUT A PERMIT, and that a caller cannot turn an
approved source identity into an arbitrary fetch.
"""

import os
import sys
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "platform", "src"))

from mogo_platform.runtime import connector_authorization as ca  # noqa: E402
from mogo_platform.runtime import errors as runtime_errors       # noqa: E402

APPROVED_SOURCE = "SRC|youtube|c785970cc458"
GOOD_AUTH = "9e24aa04-c7b5-4438-acaf-c709cd8796b5"
GOOD_VIDEO = "hb7ot1_szWI"


def request(**over):
    base = {"sourceId": APPROVED_SOURCE,
            "authorizationId": GOOD_AUTH,
            "capabilityId": "CAP|research|acquire-approved-source-metadata",
            "capabilityVersion": "1.0.0",
            "operation": "metadata",
            "resourceId": GOOD_VIDEO,
            "decidedAt": "2026-08-11T00:00:00.000Z"}
    base.update(over)
    return base


class TestTheApprovedSourceIsEligible(unittest.TestCase):

    def test_the_repository_verified_alex_g_source_is_permitted(self):
        decision = ca.evaluate(request())
        self.assertTrue(decision.permitted, decision.reason)
        self.assertEqual(decision.decision, ca.DECISION_PERMIT)
        self.assertEqual(decision.reason, ca.REASON_PERMITTED)

    def test_the_decision_records_everything_needed_to_audit_it(self):
        record = ca.evaluate(request()).as_record()
        for field in ("connectorId", "connectorVersion", "capabilityId",
                      "capabilityVersion", "sourceId", "authorizationId",
                      "operation", "scheme", "host", "approvedUrl",
                      "decidedAt", "decision", "reason"):
            self.assertIsNotNone(record[field], field)
        self.assertEqual(record["scheme"], "https")
        self.assertEqual(record["host"], "www.youtube.com")

    def test_exactly_one_external_source_is_approved(self):
        """Adding a second source must be a visible edit, not a config change."""
        self.assertEqual(ca.approved_source_ids(), (APPROVED_SOURCE,))


class TestUnauthorizedDestinationsFailClosed(unittest.TestCase):

    def test_an_unauthorized_host_or_source_is_rejected(self):
        for bad in ("SRC|youtube-channel|SOMEONEELSE", "SRC|evil|x",
                    "SRC|youtube-channel|", "not-a-source"):
            with self.subTest(sourceId=bad):
                decision = ca.evaluate(request(sourceId=bad))
                self.assertFalse(decision.permitted)
                self.assertEqual(decision.reason, ca.REASON_SOURCE_NOT_APPROVED)

    def test_a_missing_source_identity_is_rejected(self):
        for bad in (None, "", 0, [], {}):
            with self.subTest(sourceId=bad):
                decision = ca.evaluate(request(sourceId=bad))
                self.assertFalse(decision.permitted)
                self.assertEqual(decision.reason, ca.REASON_NO_SOURCE)

    def test_forbidden_schemes_are_refused_by_the_boundary(self):
        """The registry holds https only; these must be refused if one ever
        appeared there through a bad edit."""
        for scheme in ("file", "ftp", "gopher", "data", "blob", "ws", "http"):
            with self.subTest(scheme=scheme):
                self.assertIn(scheme, ca.FORBIDDEN_SCHEMES)
        self.assertEqual(ca.APPROVED_SCHEMES, ("https",))

    def test_loopback_and_private_destinations_are_forbidden(self):
        for fragment in ("localhost", "127.", "0.0.0.0", "::1", "169.254.",
                         "10.", "192.168.", "172.16."):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, ca.FORBIDDEN_HOST_FRAGMENTS)

    def test_no_approved_destination_is_local_or_insecure(self):
        for source_id, entry in ca.APPROVED_DESTINATIONS.items():
            with self.subTest(source=source_id):
                self.assertEqual(entry["scheme"], "https")
                lowered = entry["host"].lower()
                for fragment in ca.FORBIDDEN_HOST_FRAGMENTS:
                    self.assertFalse(lowered.startswith(fragment))


class TestAuthorizationIdentityIsRequired(unittest.TestCase):

    def test_a_missing_authorization_identity_is_rejected(self):
        for bad in (None, ""):
            with self.subTest(authorizationId=bad):
                decision = ca.evaluate(request(authorizationId=bad))
                self.assertFalse(decision.permitted)
                self.assertEqual(decision.reason, ca.REASON_NO_AUTHORIZATION)

    def test_a_malformed_authorization_identity_is_rejected(self):
        for bad in ("not-a-uuid", "9e24aa04", 12345, [],
                    "ZZZZZZZZ-c7b5-4438-acaf-c709cd8796b5",
                    "9e24aa04c7b54438acafc709cd8796b5"):
            with self.subTest(authorizationId=bad):
                decision = ca.evaluate(request(authorizationId=bad))
                self.assertFalse(decision.permitted)
                self.assertEqual(decision.reason,
                                 ca.REASON_MALFORMED_AUTHORIZATION)


class TestArbitraryUrlSubstitutionIsImpossible(unittest.TestCase):
    """The core anti-SSRF property."""

    def test_an_approved_source_cannot_carry_someone_elses_url(self):
        for hostile in ("https://evil.example/steal",
                        "http://localhost:8751/index.html",
                        "file:///etc/passwd",
                        "https://www.youtube.com/oembed?url=https://evil.example",
                        "https://169.254.169.254/latest/meta-data/"):
            with self.subTest(requestedUrl=hostile):
                decision = ca.evaluate(request(requestedUrl=hostile))
                self.assertFalse(decision.permitted)
                self.assertEqual(decision.reason, ca.REASON_URL_SUBSTITUTION)

    def test_a_matching_url_is_permitted_because_it_was_derived(self):
        derived, _entry = ca.derive_destination(APPROVED_SOURCE, GOOD_VIDEO)
        decision = ca.evaluate(request(requestedUrl=derived))
        self.assertTrue(decision.permitted, decision.reason)

    def test_the_destination_is_derived_and_never_supplied(self):
        """A caller supplies an identity; the gate produces the URL."""
        derived, entry = ca.derive_destination(APPROVED_SOURCE, GOOD_VIDEO)
        self.assertTrue(derived.startswith("https://www.youtube.com/oembed"))
        self.assertIn(GOOD_VIDEO, derived)
        self.assertEqual(entry["host"], "www.youtube.com")
        # and it refuses to derive anything for an unapproved source
        with self.assertRaises(runtime_errors.ContractValidationError):
            ca.derive_destination("SRC|evil|x", GOOD_VIDEO)

    def test_a_crafted_resource_identifier_cannot_escape_the_template(self):
        for hostile in ("../../etc/passwd", "x&url=https://evil.example",
                        "hb7ot1_szW", "hb7ot1_szWII", "hb7ot1 szWI",
                        "hb7ot1/szWI", "hb7ot1?szWI", "", None, 11):
            with self.subTest(resourceId=hostile):
                decision = ca.evaluate(request(resourceId=hostile))
                self.assertFalse(decision.permitted)
                self.assertEqual(decision.reason, ca.REASON_MALFORMED_VIDEO_ID)
                with self.assertRaises(runtime_errors.ContractValidationError):
                    ca.derive_destination(APPROVED_SOURCE, hostile)

    def test_the_operation_must_be_the_one_the_connector_exists_for(self):
        for bad in ("transcript", "artifact", "discover", "", None):
            with self.subTest(operation=bad):
                decision = ca.evaluate(request(operation=bad))
                self.assertFalse(decision.permitted)
                self.assertEqual(decision.reason,
                                 ca.REASON_OPERATION_NOT_PERMITTED)


class TestRedirectsAreNotAuthorized(unittest.TestCase):

    def test_requesting_redirects_is_refused(self):
        decision = ca.evaluate(request(followRedirects=True))
        self.assertFalse(decision.permitted)
        self.assertEqual(decision.reason, ca.REASON_REDIRECT_NOT_PERMITTED)

    def test_a_redirect_destination_is_revalidated_and_denied(self):
        for location in ("https://www.youtube.com/oembed?x=1",
                         "https://evil.example/", "http://127.0.0.1/"):
            with self.subTest(location=location):
                decision = ca.evaluate_redirect(APPROVED_SOURCE, location)
                self.assertFalse(decision.permitted)
                self.assertEqual(decision.reason,
                                 ca.REASON_REDIRECT_NOT_PERMITTED)

    def test_the_permit_carries_the_transport_limits(self):
        limits = ca.evaluate(request()).limits
        self.assertIs(limits["followRedirects"], False)
        self.assertEqual(limits["expectedContentType"], "application/json")
        self.assertLessEqual(limits["maxResponseBytes"], 1_000_000)


class TestRejectionHappensBeforeAnyNetworkEffect(unittest.TestCase):
    """The requirement this whole step exists to satisfy.

    Proven two ways: statically, that the gate module contains no transport at
    all; and dynamically, that evaluating a denied request never reaches a
    transport spy.
    """

    def test_the_gate_module_imports_no_network_client(self):
        import ast
        path = os.path.join(REPO_ROOT, "platform", "src", "mogo_platform",
                            "runtime", "connector_authorization.py")
        with open(path, "r", encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        for forbidden in ("socket", "ssl", "http", "urllib", "requests",
                          "httpx", "asyncio", "aiohttp", "subprocess"):
            self.assertNotIn(forbidden, imported,
                             "the authorization gate must contain no transport")

    def test_a_denied_request_never_reaches_the_transport(self):
        """A spy standing in for the future transport must never be called.

        This models the Step 3 call order: evaluate FIRST, and only a permit may
        reach the fetch. The spy raises if invoked, so a denial that leaked
        through would fail loudly rather than silently.
        """
        calls = []

        def transport_spy(url, limits):
            calls.append(url)
            raise AssertionError("transport invoked for a DENIED request")

        def acquire(req):
            decision = ca.evaluate(req)
            if not decision.permitted:
                return decision                    # <-- no transport, ever
            return transport_spy(decision.approvedUrl, decision.limits)

        denied = [
            request(sourceId="SRC|evil|x"),
            request(sourceId=None),
            request(authorizationId=None),
            request(authorizationId="not-a-uuid"),
            request(operation="transcript"),
            request(resourceId="../../etc/passwd"),
            request(requestedUrl="https://evil.example/steal"),
            request(followRedirects=True),
            {},
            None,
        ]
        for req in denied:
            with self.subTest(request=req):
                outcome = acquire(req)
                self.assertFalse(outcome.permitted)
        self.assertEqual(calls, [],
                         "the transport was invoked despite a denial")

    def test_a_permitted_request_would_reach_the_transport(self):
        """The gate must be capable of permitting -- a gate that always denies
        proves nothing about the one that will guard Step 3."""
        seen = []

        def transport_spy(url, limits):
            seen.append(url)
            return "would-fetch"

        decision = ca.evaluate(request())
        self.assertTrue(decision.permitted)
        transport_spy(decision.approvedUrl, decision.limits)
        self.assertEqual(len(seen), 1)
        self.assertTrue(seen[0].startswith("https://www.youtube.com/oembed"))


class TestScientificFirewall(unittest.TestCase):

    def test_the_gate_references_nothing_in_the_trading_lane(self):
        path = os.path.join(REPO_ROOT, "platform", "src", "mogo_platform",
                            "runtime", "connector_authorization.py")
        with open(path, "r", encoding="utf-8") as handle:
            source = handle.read()
        for forbidden in ("index.html", "alexG", "localStorage", "indexedDB",
                          "paperAccount", "alexGAutoTrading"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------------------
# MOGO-018 Step 3A -- the resource-id rule is PER DESTINATION, and fails closed
# ---------------------------------------------------------------------------

class TestPerDestinationResourceIdBoundary(unittest.TestCase):
    """The rule moved OFF the module and ONTO each approved destination.

    This narrows the boundary. Before, one 11-character YouTube rule was applied
    to every destination, so a future destination would have inherited a rule
    written for someone else. Now a destination that does not declare what it
    accepts accepts NOTHING.
    """

    ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"

    def entry(self, **over):
        """A local, test-only destination declaration.

        Deliberately NOT a second real source: proving per-destination behaviour
        must not require authorizing anyone.
        """
        base = {"resourceIdAlphabet": self.ALPHABET, "resourceIdLength": 11}
        base.update(over)
        return base

    # -- the approved source is unchanged ----------------------------------

    def test_the_approved_source_declares_its_own_constraint(self):
        entry = ca.APPROVED_DESTINATIONS[APPROVED_SOURCE]
        self.assertEqual(entry["resourceIdAlphabet"], self.ALPHABET)
        self.assertEqual(entry["resourceIdLength"], 11)

    def test_the_approved_source_still_accepts_its_exact_valid_form(self):
        self.assertTrue(ca.evaluate(request()).permitted)
        url, _entry = ca.derive_destination(APPROVED_SOURCE, GOOD_VIDEO)
        self.assertIn(GOOD_VIDEO, url)

    def test_invalid_length_remains_denied(self):
        for bad in ("", "a", GOOD_VIDEO[:-1], GOOD_VIDEO + "a", "a" * 64):
            with self.subTest(resourceId=bad):
                self.assertEqual(ca.evaluate(request(resourceId=bad)).reason,
                                 ca.REASON_MALFORMED_VIDEO_ID)

    def test_invalid_alphabet_remains_denied(self):
        for bad in ("hb7ot1_szW!", "hb7ot1 szWI", "hb7ot1/szWI", "hb7ot1.szWI",
                    "hb7ot1%szWI", "hb7ot1\tszWI", "hb7ot1észWI"):
            with self.subTest(resourceId=bad):
                self.assertEqual(ca.evaluate(request(resourceId=bad)).reason,
                                 ca.REASON_MALFORMED_VIDEO_ID)

    def test_an_unknown_source_remains_denied_before_any_resource_check(self):
        decision = ca.evaluate(request(sourceId="SRC|web|0123456789ab"))
        self.assertEqual(decision.reason, ca.REASON_SOURCE_NOT_APPROVED)
        with self.assertRaises(runtime_errors.PlatformError):
            ca.derive_destination("SRC|web|0123456789ab", GOOD_VIDEO)

    # -- fail closed on a destination that does not declare a rule ----------

    def test_a_destination_with_no_constraint_accepts_nothing(self):
        """The property that makes this a NARROWING rather than a widening."""
        for missing in ({}, {"urlTemplate": "https://example.test/{videoId}"},
                        self.entry(resourceIdAlphabet=None),
                        self.entry(resourceIdLength=None)):
            with self.subTest(entry=missing):
                self.assertFalse(ca._valid_resource_id(missing, GOOD_VIDEO))

    def test_a_malformed_constraint_accepts_nothing(self):
        for bad in (self.entry(resourceIdAlphabet=""),
                    self.entry(resourceIdAlphabet=11),
                    self.entry(resourceIdAlphabet=["a", "b"]),
                    self.entry(resourceIdLength=0),
                    self.entry(resourceIdLength=-1),
                    self.entry(resourceIdLength="11"),
                    self.entry(resourceIdLength=True),
                    self.entry(resourceIdLength=11.0)):
            with self.subTest(entry=bad):
                self.assertFalse(ca._valid_resource_id(bad, GOOD_VIDEO))

    def test_an_absent_entry_accepts_nothing(self):
        for entry in (None, "not-an-entry", 17, []):
            with self.subTest(entry=entry):
                self.assertFalse(ca._valid_resource_id(entry, GOOD_VIDEO))

    def test_a_non_string_resource_id_accepts_nothing(self):
        for value in (None, 17, [], {}, b"hb7ot1_szWI"):
            with self.subTest(value=value):
                self.assertFalse(
                    ca._valid_resource_id(self.entry(), value))

    # -- one destination's rule does not apply to another ------------------

    def test_a_resource_valid_for_one_constraint_is_not_valid_for_another(self):
        """The point of localizing: constraints do not leak between entries."""
        eleven = self.entry()
        six = self.entry(resourceIdLength=6)
        digits = self.entry(resourceIdAlphabet="0123456789")
        self.assertTrue(ca._valid_resource_id(eleven, GOOD_VIDEO))
        self.assertFalse(ca._valid_resource_id(six, GOOD_VIDEO))
        self.assertFalse(ca._valid_resource_id(digits, GOOD_VIDEO))
        self.assertTrue(ca._valid_resource_id(six, "abc123"))
        self.assertFalse(ca._valid_resource_id(eleven, "abc123"))
        self.assertTrue(ca._valid_resource_id(digits, "01234567890"))
        # ...and the REAL entry is unaffected by any of the above.
        self.assertTrue(
            ca._valid_resource_id(ca.APPROVED_DESTINATIONS[APPROVED_SOURCE],
                                  GOOD_VIDEO))

    def test_every_approved_destination_declares_a_usable_constraint(self):
        """No entry may ship without one -- otherwise it would fetch nothing."""
        for source_id, entry in ca.APPROVED_DESTINATIONS.items():
            with self.subTest(source=source_id):
                self.assertIsInstance(entry["resourceIdAlphabet"], str)
                self.assertTrue(entry["resourceIdAlphabet"])
                self.assertIsInstance(entry["resourceIdLength"], int)
                self.assertGreater(entry["resourceIdLength"], 0)

    # -- the authorization boundary is otherwise untouched ------------------

    def test_no_caller_controlled_url_is_accepted(self):
        for hostile in ("https://evil.example/x", "file:///etc/passwd",
                        "http://169.254.169.254/", "https://www.youtube.com/x"):
            with self.subTest(url=hostile):
                self.assertEqual(
                    ca.evaluate(request(requestedUrl=hostile)).reason,
                    ca.REASON_URL_SUBSTITUTION)

    def test_destination_derivation_remains_registry_controlled(self):
        url, entry = ca.derive_destination(APPROVED_SOURCE, GOOD_VIDEO)
        self.assertEqual(url, entry["urlTemplate"].format(videoId=GOOD_VIDEO))
        self.assertTrue(url.startswith("https://www.youtube.com/oembed"))
        self.assertEqual(ca.approved_source_ids(), (APPROVED_SOURCE,),
                         "Step 3A authorized no new source")

    def test_the_acceptance_boundary_is_identical_to_the_global_rule(self):
        """Compatibility, proved rather than asserted.

        The previous GLOBAL rule is reconstructed here and compared against the
        new per-entry rule across every single-character substitution at every
        position, every length 0..15, and hostile shapes. Not one identifier
        changed status in either direction.
        """
        def old_rule(value):
            if not isinstance(value, str) or len(value) != 11:
                return False
            return all(c in self.ALPHABET for c in value)

        entry = ca.APPROVED_DESTINATIONS[APPROVED_SOURCE]
        cases = ["a" * length for length in range(16)]
        for code in list(range(32, 127)) + [9, 10, 0]:
            for position in range(11):
                cases.append("a" * position + chr(code) + "a" * (10 - position))
        cases += ["../../etc/passwd", "x&url=https://evil.example", GOOD_VIDEO,
                  "", "hb7ot1 szWI", "hb7ot1/szWI", "hb7ot1.szWI", "é" * 11]
        for value in cases:
            with self.subTest(resourceId=value):
                self.assertEqual(ca._valid_resource_id(entry, value),
                                 old_rule(value))

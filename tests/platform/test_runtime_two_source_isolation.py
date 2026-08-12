#!/usr/bin/env python3
"""MOGO-018 Step 3C -- the first genuine TWO-SOURCE research configuration.

The property under test is NOT "a second source can be added". It is that
adding one changed nothing about the first, and that the two corpora are
SCIENTIFICALLY ISOLATED:

  * Alex G history cannot advance TJR history, and TJR history cannot advance
    Alex G's. The comparison baseline is keyed on (sourceId, resourceId), so a
    TJR acquisition is never compared against an Alex G observation.
  * Neither educator's artifact can enter the other's corpus. Attribution is
    explicit and per-source; there is no fallback, no inference and no default.
  * Sharing a rule is not inheriting one. Both destinations are YouTube and
    legitimately accept the same resource shape -- so each DECLARES that shape,
    and removing either declaration must break only that destination.
  * The bound did not move. Two committed entries means at most two acquisitions
    in a window, and the cap, the cadence and the launchd model are untouched.

ORGANIZATION IS NOT VALIDATION. Attributing TJR material to the TJR corpus says
the material was collected for that corpus and NOTHING else -- not that TJR is
profitable, validated, accepted, ready for reconstruction, ready for backtesting
or ready for paper trading, and never that TJR may influence ALEX.

The acquisition harness is REUSED from the MOGO-017 Step 2C suite rather than
duplicated: it drives the REAL Orchestrator, the REAL connector gate and the
REAL transport with only the socket and the corpus doubled.
"""

import json
import os
import sys
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "platform", "src"))

from mogo_platform.contracts import ids                                # noqa: E402
from mogo_platform.runtime import change_detection as cd               # noqa: E402
from mogo_platform.runtime import connector_authorization as ca        # noqa: E402
from mogo_platform.runtime import errors as runtime_errors             # noqa: E402
from mogo_platform.runtime import research_library as library          # noqa: E402
from mogo_platform.runtime import scheduled_collection as sched        # noqa: E402

from tests.platform.test_runtime_change_detection_wiring import (      # noqa: E402
    ChangeDetectionWiringCase, APPROVED_SOURCE, APPROVED_RESOURCE,
    AUTHORIZATION_ID)

# ── the second educator, REUSED from committed repository evidence ─────────
# docs/trader-intelligence/evidence/sources/EVSRC_TJR_20260727_002.json
#   -> channelUrl https://www.youtube.com/@TJRTrades, youtubeVideoId 8qwEmE1DwYw
# docs/trader-intelligence/traders/tjr/profile.json
#   -> traderId TJR, strategyFamilyIds [SF|TJR|SESSION_ZONE_REACTION]
# Nothing here was invented for the test.
TJR_SOURCE = "SRC|youtube|11cd2542b5b0"
TJR_RESOURCE = "8qwEmE1DwYw"
TJR_AUTH = "3008510b-6c34-4a46-ba26-1c90bb9c728a"
TJR_CHANNEL_URL = "https://www.youtube.com/@TJRTrades"

ALEX_FAMILY = "SF|ALEX_G|SUPPORT_RESISTANCE_V1"
TJR_FAMILY = "SF|TJR|SESSION_ZONE_REACTION"

SPEC_PATH = os.path.join(REPO_ROOT, "platform", "scheduling",
                         "approved-collection.json")

# Per-stream bodies, so an observation belonging to one educator is
# distinguishable from the other's by content alone.
ALEX_BODY_1 = b'{"mogoFixture":"3c-alex-1","title":"ALEX ONE","provider_name":"T"}'
ALEX_BODY_2 = b'{"mogoFixture":"3c-alex-2","title":"ALEX TWO","provider_name":"T"}'
TJR_BODY_1 = b'{"mogoFixture":"3c-tjr-1","title":"TJR ONE","provider_name":"T"}'
TJR_BODY_2 = b'{"mogoFixture":"3c-tjr-2","title":"TJR TWO","provider_name":"T"}'

ALEX_HASH_1 = ids.sha256_hex(ALEX_BODY_1)
ALEX_HASH_2 = ids.sha256_hex(ALEX_BODY_2)
TJR_HASH_1 = ids.sha256_hex(TJR_BODY_1)
TJR_HASH_2 = ids.sha256_hex(TJR_BODY_2)


def read_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def committed_entries():
    return sched.validate_collection_set(read_json(SPEC_PATH))


def committed_attribution():
    return read_json(library.ATTRIBUTION_PATH)


# ---------------------------------------------------------------------------
# The authorization surface -- exactly two, and no third
# ---------------------------------------------------------------------------

class TestExactlyTwoApprovedSources(unittest.TestCase):

    def test_exactly_two_sources_are_approved_after_step_3c(self):
        self.assertEqual(set(ca.approved_source_ids()),
                         {APPROVED_SOURCE, TJR_SOURCE})

    def test_exactly_two_production_collection_entries_exist(self):
        entries = committed_entries()
        self.assertEqual(len(entries), 2)
        self.assertEqual([(e["sourceId"], e["resourceId"]) for e in entries],
                         [(APPROVED_SOURCE, APPROVED_RESOURCE),
                          (TJR_SOURCE, TJR_RESOURCE)],
                         "committed order is the processing order")

    def test_an_unauthorized_third_source_is_still_refused(self):
        """ICT and CRT were NOT authorized by this step, nor was anything else."""
        for stranger in ("SRC|youtube|ICTICTICTIC", "SRC|youtube|CRTCRTCRTCR",
                         "SRC|youtube|000000000000", "SRC|evil|deadbeefcafe"):
            with self.subTest(source=stranger):
                self.assertNotIn(stranger, ca.APPROVED_DESTINATIONS)
                decision = ca.evaluate({
                    "sourceId": stranger, "authorizationId": TJR_AUTH,
                    "operation": "metadata", "resourceId": TJR_RESOURCE})
                self.assertFalse(decision.permitted)
                self.assertEqual(decision.reason, ca.REASON_SOURCE_NOT_APPROVED)
                with self.assertRaises(runtime_errors.PlatformError):
                    ca.derive_destination(stranger, TJR_RESOURCE)

    def test_the_alex_g_entry_is_unchanged_in_effective_behaviour(self):
        """Step 3C added a neighbour. It must not have edited the incumbent."""
        entry = ca.APPROVED_DESTINATIONS[APPROVED_SOURCE]
        self.assertEqual(entry["channelUrl"], "https://www.youtube.com/@fxalexg__")
        self.assertEqual(entry["channelId"], "UCgPeeHdxYRal0HTNeAkjqLg")
        self.assertEqual(entry["resourceIdAlphabet"], ca.VIDEO_ID_PATTERN)
        self.assertEqual(entry["resourceIdLength"], 11)
        self.assertEqual(entry["maxResponseBytes"], 65536)
        self.assertIs(entry["followRedirects"], False)
        url, _entry = ca.derive_destination(APPROVED_SOURCE, APPROVED_RESOURCE)
        self.assertEqual(
            url,
            "https://www.youtube.com/oembed?url=https://www.youtube.com/"
            "watch%3Fv%3Dhb7ot1_szWI&format=json")

    def test_the_tjr_destination_derives_its_own_exact_url(self):
        """Pinned in full, so the duplicated template cannot drift unnoticed."""
        url, _entry = ca.derive_destination(TJR_SOURCE, TJR_RESOURCE)
        self.assertEqual(
            url,
            "https://www.youtube.com/oembed?url=https://www.youtube.com/"
            "watch%3Fv%3D8qwEmE1DwYw&format=json")

    def test_the_tjr_entry_claims_no_channel_id_it_cannot_evidence(self):
        """The repository has no UC-form id for TJR, so the entry declares none."""
        self.assertNotIn("channelId", ca.APPROVED_DESTINATIONS[TJR_SOURCE])
        self.assertEqual(ca.APPROVED_DESTINATIONS[TJR_SOURCE]["channelUrl"],
                         TJR_CHANNEL_URL)


# ---------------------------------------------------------------------------
# The per-destination resource rule -- declared by TJR, not inherited
# ---------------------------------------------------------------------------

class TestTjrDeclaresItsOwnResourceRule(unittest.TestCase):

    def test_tjr_declares_its_resource_constraint_explicitly(self):
        entry = ca.APPROVED_DESTINATIONS[TJR_SOURCE]
        self.assertEqual(entry["resourceIdAlphabet"], ca.VIDEO_ID_PATTERN)
        self.assertEqual(entry["resourceIdLength"], 11)

    def test_a_shared_rule_is_still_two_independent_declarations(self):
        """THE Step 3A property, re-proved with a real second source.

        Both destinations accept the same shape. That must be because each SAYS
        so -- not because a global rule reached them. Strip the declaration from
        a copy of the TJR entry and TJR accepts NOTHING, while the real Alex G
        entry is entirely unaffected.
        """
        stripped = {k: v for k, v in ca.APPROVED_DESTINATIONS[TJR_SOURCE].items()
                    if k not in ("resourceIdAlphabet", "resourceIdLength")}
        for value in (TJR_RESOURCE, APPROVED_RESOURCE, "aaaaaaaaaaa"):
            with self.subTest(resourceId=value):
                self.assertFalse(ca._valid_resource_id(stripped, value))
        self.assertTrue(ca._valid_resource_id(
            ca.APPROVED_DESTINATIONS[APPROVED_SOURCE], APPROVED_RESOURCE))

    def test_a_malformed_tjr_identifier_fails_closed(self):
        for bad in ("", "8qwEmE1DwY", "8qwEmE1DwYww", "8qwEmE1Dw Y",
                    "8qwEmE1Dw/Y", "../../etc/passwd", None, 11, [], True,
                    "8qwEmE1DwY&url=https://evil.example"):
            with self.subTest(resourceId=bad):
                self.assertFalse(ca._valid_resource_id(
                    ca.APPROVED_DESTINATIONS[TJR_SOURCE], bad))
                decision = ca.evaluate({
                    "sourceId": TJR_SOURCE, "authorizationId": TJR_AUTH,
                    "operation": "metadata", "resourceId": bad})
                self.assertFalse(decision.permitted)
                self.assertEqual(decision.reason, ca.REASON_MALFORMED_VIDEO_ID)
                with self.assertRaises(runtime_errors.PlatformError):
                    ca.derive_destination(TJR_SOURCE, bad)

    def test_an_identifier_valid_for_one_source_does_not_reach_the_other(self):
        """Shape is not authorization, and it is not a destination.

        Alex G's resource id is well-formed for TJR's declared rule -- both are
        11-character YouTube ids -- so the shape check alone cannot keep the
        corpora apart. What does is that the destination is derived PER SOURCE:
        the same identifier under a different sourceId produces a different URL,
        and the committed set never pairs them.
        """
        alex_under_tjr, _ = ca.derive_destination(TJR_SOURCE, APPROVED_RESOURCE)
        alex_under_alex, _ = ca.derive_destination(APPROVED_SOURCE,
                                                   APPROVED_RESOURCE)
        tjr_under_alex, _ = ca.derive_destination(APPROVED_SOURCE, TJR_RESOURCE)
        tjr_under_tjr, _ = ca.derive_destination(TJR_SOURCE, TJR_RESOURCE)
        self.assertEqual(alex_under_tjr, alex_under_alex,
                         "the URL follows the RESOURCE; the source authorizes it")
        self.assertNotEqual(tjr_under_tjr, alex_under_alex)
        self.assertNotEqual(tjr_under_alex, alex_under_alex)
        # And neither cross pairing is in the committed production set.
        committed = {(e["sourceId"], e["resourceId"]) for e in committed_entries()}
        self.assertNotIn((TJR_SOURCE, APPROVED_RESOURCE), committed)
        self.assertNotIn((APPROVED_SOURCE, TJR_RESOURCE), committed)

    def test_caller_url_substitution_is_refused_for_both_sources(self):
        hostile = ("https://evil.example/x", "file:///etc/passwd",
                   "http://169.254.169.254/", "https://www.youtube.com/x")
        for source, resource in ((APPROVED_SOURCE, APPROVED_RESOURCE),
                                 (TJR_SOURCE, TJR_RESOURCE)):
            for url in hostile:
                with self.subTest(source=source, url=url):
                    decision = ca.evaluate({
                        "sourceId": source,
                        "authorizationId": AUTHORIZATION_ID,
                        "operation": "metadata", "resourceId": resource,
                        "requestedUrl": url})
                    self.assertFalse(decision.permitted)
                    self.assertEqual(decision.reason, ca.REASON_URL_SUBSTITUTION)

    def test_one_source_cannot_borrow_the_others_approved_url(self):
        """The exact substitution a two-source registry newly makes possible."""
        alex_url, _ = ca.derive_destination(APPROVED_SOURCE, APPROVED_RESOURCE)
        decision = ca.evaluate({
            "sourceId": TJR_SOURCE, "authorizationId": TJR_AUTH,
            "operation": "metadata", "resourceId": TJR_RESOURCE,
            "requestedUrl": alex_url})
        self.assertFalse(decision.permitted)
        self.assertEqual(decision.reason, ca.REASON_URL_SUBSTITUTION)


# ---------------------------------------------------------------------------
# Attribution -- explicit, per-source, and never inferred
# ---------------------------------------------------------------------------

class TestStrategyFamilyAttribution(unittest.TestCase):

    def setUp(self):
        self.resolved = library.resolve_attribution(committed_attribution())

    def test_alex_g_attribution_is_unchanged(self):
        self.assertEqual(self.resolved[APPROVED_SOURCE],
                         {"traderId": "ALEX_G",
                          "strategyFamilyIds": [ALEX_FAMILY]})

    def test_tjr_maps_only_to_the_canonical_tjr_strategy_family(self):
        self.assertEqual(self.resolved[TJR_SOURCE],
                         {"traderId": "TJR", "strategyFamilyIds": [TJR_FAMILY]})

    def test_the_tjr_family_is_the_one_already_declared_in_the_profile(self):
        """Reused identity, not a second one minted for the platform lane."""
        profile = read_json(os.path.join(
            REPO_ROOT, "docs", "trader-intelligence", "traders", "tjr",
            "profile.json"))
        self.assertEqual(profile["traderId"], "TJR")
        self.assertIn(TJR_FAMILY, profile["strategyFamilyIds"])

    def test_neither_corpus_carries_the_others_family(self):
        self.assertNotIn(TJR_FAMILY,
                         self.resolved[APPROVED_SOURCE]["strategyFamilyIds"])
        self.assertNotIn(ALEX_FAMILY,
                         self.resolved[TJR_SOURCE]["strategyFamilyIds"])

    def test_the_tjr_source_id_is_recomputed_from_its_channel_url(self):
        """Verified, not pasted -- the loader refuses a mismatch."""
        self.assertEqual(ids.make_source_id("youtube", TJR_CHANNEL_URL),
                         TJR_SOURCE)

    def test_a_swapped_channel_url_under_an_unchanged_id_fails_closed(self):
        """The contamination this check exists to stop: one educator's id
        pointing at another educator's channel."""
        document = committed_attribution()
        for record in document["attributions"]:
            if record["sourceId"] == TJR_SOURCE:
                record["sourceIdDerivation"]["channelUrl"] = \
                    "https://www.youtube.com/@fxalexg__"
        with self.assertRaises(runtime_errors.PlatformError):
            library.resolve_attribution(document)


# ---------------------------------------------------------------------------
# The bounded window -- two entries, at most two requests
# ---------------------------------------------------------------------------

class TestTheWindowRemainsBounded(unittest.TestCase):

    NOW_MS = 1_786_000_000_000
    ISSUED_AT = "2026-08-12T00:00:00.000Z"

    def test_two_entries_build_exactly_two_distinct_requests(self):
        keys, streams = set(), []
        for entry in committed_entries():
            envelope, payload, window = sched.build_command(
                entry, self.NOW_MS, self.ISSUED_AT)
            keys.add(envelope["idempotencyKey"])
            streams.append((payload["sourceId"], payload["resourceId"]))
            self.assertEqual(window, "W|21600|%d"
                             % (self.NOW_MS // (21600 * 1000),))
        self.assertEqual(len(keys), 2, "two streams are two distinct requests")
        self.assertEqual(streams, [(APPROVED_SOURCE, APPROVED_RESOURCE),
                                   (TJR_SOURCE, TJR_RESOURCE)])

    def test_each_command_carries_its_own_identity_and_authorization(self):
        by_source = {}
        for entry in committed_entries():
            envelope, payload, _ = sched.build_command(
                entry, self.NOW_MS, self.ISSUED_AT)
            by_source[payload["sourceId"]] = (envelope, payload)
        alex_env, alex_payload = by_source[APPROVED_SOURCE]
        tjr_env, tjr_payload = by_source[TJR_SOURCE]
        self.assertEqual(alex_payload["authorizationId"], AUTHORIZATION_ID)
        self.assertEqual(tjr_payload["authorizationId"], TJR_AUTH)
        self.assertNotEqual(alex_payload["authorizationId"],
                            tjr_payload["authorizationId"])
        self.assertEqual(alex_env["inputRefs"], [APPROVED_SOURCE])
        self.assertEqual(tjr_env["inputRefs"], [TJR_SOURCE])

    def test_the_same_window_repeated_is_the_same_two_requests(self):
        """Re-running the window must not double the request count."""
        first = {sched.build_command(e, self.NOW_MS, self.ISSUED_AT)[0]
                 ["idempotencyKey"] for e in committed_entries()}
        later = {sched.build_command(e, self.NOW_MS + 60_000, self.ISSUED_AT)[0]
                 ["idempotencyKey"] for e in committed_entries()}
        self.assertEqual(first, later)
        self.assertEqual(len(first), 2)

    def test_the_bound_and_the_cadence_did_not_move(self):
        """Adding an educator must not have touched the schedule.

        The cadence is declared in the INSTALLER (the plist template carries a
        @@CALENDAR@@ placeholder), so that is where it is checked.
        """
        self.assertEqual(sched.MAX_COLLECTION_ENTRIES, 25)
        self.assertTrue(all(e["collectionWindowSeconds"] == 21600
                            for e in committed_entries()))
        with open(os.path.join(REPO_ROOT, "platform", "scheduling",
                               "mogo_schedule.sh"), "r",
                  encoding="utf-8") as handle:
            installer = handle.read()
        self.assertIn('PRODUCTION_TIMES="00:00,06:00,12:00,18:00"', installer)
        template = os.path.join(REPO_ROOT, "platform", "scheduling",
                                "com.mogo.research.collect.plist.template")
        with open(template, "r", encoding="utf-8") as handle:
            text = handle.read()
        self.assertEqual(text.count("<string>collect</string>"), 1,
                         "one job, one collect -- no per-source scheduler")
        self.assertIn("@@CALENDAR@@", text)


# ---------------------------------------------------------------------------
# The live proof: two streams through the REAL runtime, kept apart
# ---------------------------------------------------------------------------

class TwoSourceCase(ChangeDetectionWiringCase):
    """Extends the MOGO-017 harness with a SECOND approved stream."""

    def setUp(self):
        super(TwoSourceCase, self).setUp()
        # Route the doubled socket by resource id, so each stream genuinely
        # returns its own content rather than sharing one body.
        self.bodies = {APPROVED_RESOURCE: ALEX_BODY_1,
                       TJR_RESOURCE: TJR_BODY_1}
        opener = self.opener
        outer = self

        def routed(request, timeout=None):
            url = request.full_url if hasattr(request, "full_url") else request
            for resource, body in outer.bodies.items():
                if resource in url:
                    outer.box["body"] = body
                    break
            return opener.__class__.open(opener, request, timeout)

        self.opener.open = routed

    def initialise_both(self):
        self.initialise()                      # records the Alex G authorization
        with self.runtime() as rt:
            rt.record_authorization({
                "authorizationId": TJR_AUTH,
                "sourceId": TJR_SOURCE,
                "policyStatus": "PERMITTED_PUBLIC_METADATA",
                "policyVersion": "1.0",
                "decisionAuthority": "operator:test-fixture",
                "decidedAt": "2026-08-12T00:00:00.000Z",
                "permittedOperations": ["metadata"],
            })

    def acquire_for(self, source_id, resource_id, authorization_id, label):
        spec = {
            "schemaVersion": sched.SPEC_SCHEMA_VERSION,
            "capabilityId": "CAP|research|acquire-approved-source-metadata",
            "commandType": "AcquireSourceMetadata", "commandVersion": 1,
            "sourceId": source_id, "resourceId": resource_id,
            "authorizationId": authorization_id, "operation": "metadata",
            "connectorId": "CONN|research|approved-source-metadata",
            "connectorVersion": "1.0.0", "policyVersion": "1.0",
            "collectionWindowSeconds": 120,
        }
        envelope, payload, _ = sched.build_command(
            spec, 1_786_000_000_000, "2026-08-12T00:00:00.000Z")
        envelope["idempotencyKey"] = ids.content_hash_of(
            {"fixtureRequest": label, "source": source_id,
             "resource": resource_id})
        payload = dict(payload)
        payload["collectionWindow"] = label
        envelope["payloadHash"] = ids.content_hash_of(payload)
        with self.runtime() as rt:
            rt.recover()
            outcome = rt.submit(envelope, payload)
            report = rt.run_once()
        return outcome, report

    def results_for(self, source_id, resource_id):
        return [r for r in self.recorded_results()
                if r.get("sourceId") == source_id
                and r.get("resourceId") == resource_id]

    def library_entries(self):
        with self.runtime() as rt:
            return library.entries(rt.connection, committed_attribution())

    def corpus_summary(self):
        with self.runtime() as rt:
            return library.corpus_summary(rt.connection, committed_attribution())


class TestTheTwoStreamsAreIsolated(TwoSourceCase):

    def test_each_stream_keeps_its_own_identity_and_history(self):
        """THE Step 3C proof, end to end through the real runtime.

        Alex G is observed twice with identical bytes; TJR is then observed for
        the FIRST time. If the histories were shared, TJR's first observation
        would be compared against Alex G's content and misreported as CHANGED.
        """
        self.initialise_both()

        _o, report = self.acquire_for(APPROVED_SOURCE, APPROVED_RESOURCE,
                                      AUTHORIZATION_ID, "alex-1")
        self.assertEqual(len(report["succeeded"]), 1, report)
        _o, report = self.acquire_for(APPROVED_SOURCE, APPROVED_RESOURCE,
                                      AUTHORIZATION_ID, "alex-2")
        self.assertEqual(len(report["succeeded"]), 1, report)
        _o, report = self.acquire_for(TJR_SOURCE, TJR_RESOURCE, TJR_AUTH,
                                      "tjr-1")
        self.assertEqual(len(report["succeeded"]), 1, report)

        alex = self.results_for(APPROVED_SOURCE, APPROVED_RESOURCE)
        tjr = self.results_for(TJR_SOURCE, TJR_RESOURCE)
        self.assertEqual(len(alex), 2)
        self.assertEqual(len(tjr), 1)

        self.assertEqual([self.classification_of(r) for r in alex],
                         [cd.FIRST_OBSERVATION, cd.UNCHANGED])
        self.assertEqual(self.classification_of(tjr[0]), cd.FIRST_OBSERVATION,
                         "TJR's first acquisition must not be compared against "
                         "Alex G's accepted content")
        self.assertIsNone(tjr[0]["changeDetection"]["priorContentIdentity"])
        self.assertEqual(tjr[0]["contentHash"], TJR_HASH_1)
        self.assertEqual(alex[0]["contentHash"], ALEX_HASH_1)
        self.assertNotEqual(alex[0]["contentHash"], tjr[0]["contentHash"])

    def test_a_change_in_one_stream_does_not_disturb_the_other(self):
        self.initialise_both()
        self.acquire_for(APPROVED_SOURCE, APPROVED_RESOURCE, AUTHORIZATION_ID,
                         "alex-1")
        self.acquire_for(TJR_SOURCE, TJR_RESOURCE, TJR_AUTH, "tjr-1")

        # Only TJR's content changes.
        self.bodies[TJR_RESOURCE] = TJR_BODY_2
        self.acquire_for(TJR_SOURCE, TJR_RESOURCE, TJR_AUTH, "tjr-2")
        # Alex G is observed again with its ORIGINAL content.
        self.acquire_for(APPROVED_SOURCE, APPROVED_RESOURCE, AUTHORIZATION_ID,
                         "alex-2")

        tjr = self.results_for(TJR_SOURCE, TJR_RESOURCE)
        alex = self.results_for(APPROVED_SOURCE, APPROVED_RESOURCE)
        self.assertEqual([self.classification_of(r) for r in tjr],
                         [cd.FIRST_OBSERVATION, cd.CHANGED])
        self.assertEqual(tjr[1]["changeDetection"]["priorContentIdentity"],
                         TJR_HASH_1)
        self.assertEqual(tjr[1]["changeDetection"]["currentContentIdentity"],
                         TJR_HASH_2)
        self.assertEqual([self.classification_of(r) for r in alex],
                         [cd.FIRST_OBSERVATION, cd.UNCHANGED],
                         "a TJR mutation must not make Alex G look changed")

    def test_the_reverse_direction_holds_too(self):
        """Contamination is checked BOTH ways, not once and assumed symmetric."""
        self.initialise_both()
        self.acquire_for(TJR_SOURCE, TJR_RESOURCE, TJR_AUTH, "tjr-1")
        self.acquire_for(APPROVED_SOURCE, APPROVED_RESOURCE, AUTHORIZATION_ID,
                         "alex-1")
        self.bodies[APPROVED_RESOURCE] = ALEX_BODY_2
        self.acquire_for(APPROVED_SOURCE, APPROVED_RESOURCE, AUTHORIZATION_ID,
                         "alex-2")
        self.acquire_for(TJR_SOURCE, TJR_RESOURCE, TJR_AUTH, "tjr-2")

        alex = self.results_for(APPROVED_SOURCE, APPROVED_RESOURCE)
        tjr = self.results_for(TJR_SOURCE, TJR_RESOURCE)
        self.assertEqual([self.classification_of(r) for r in alex],
                         [cd.FIRST_OBSERVATION, cd.CHANGED])
        self.assertEqual(alex[1]["changeDetection"]["currentContentIdentity"],
                         ALEX_HASH_2)
        self.assertEqual([self.classification_of(r) for r in tjr],
                         [cd.FIRST_OBSERVATION, cd.UNCHANGED])

    def test_a_failure_in_one_stream_does_not_advance_the_other(self):
        """MOGO-017's rule, re-proved across sources: nothing that failed is
        ever accepted, and a failure must not touch a neighbour's baseline."""
        self.initialise_both()
        self.acquire_for(APPROVED_SOURCE, APPROVED_RESOURCE, AUTHORIZATION_ID,
                         "alex-1")
        self.bodies[TJR_RESOURCE] = b'{"broken":'          # not valid JSON
        self.acquire_for(TJR_SOURCE, TJR_RESOURCE, TJR_AUTH, "tjr-bad")
        self.bodies[TJR_RESOURCE] = TJR_BODY_1
        self.acquire_for(TJR_SOURCE, TJR_RESOURCE, TJR_AUTH, "tjr-good")

        tjr = self.results_for(TJR_SOURCE, TJR_RESOURCE)
        accepted = [r for r in tjr if self.classification_of(r) is not None]
        self.assertEqual([self.classification_of(r) for r in accepted],
                         [cd.FIRST_OBSERVATION],
                         "the refused body must not have become a baseline")
        alex = self.results_for(APPROVED_SOURCE, APPROVED_RESOURCE)
        self.assertEqual([self.classification_of(r) for r in alex],
                         [cd.FIRST_OBSERVATION])

    def test_dedupe_is_per_stream(self):
        """One stream's duplicate suppression must not suppress the other."""
        self.initialise_both()
        first, _ = self.acquire_for(APPROVED_SOURCE, APPROVED_RESOURCE,
                                    AUTHORIZATION_ID, "shared-label")
        repeat, _ = self.acquire_for(APPROVED_SOURCE, APPROVED_RESOURCE,
                                     AUTHORIZATION_ID, "shared-label")
        other, _ = self.acquire_for(TJR_SOURCE, TJR_RESOURCE, TJR_AUTH,
                                    "shared-label")
        self.assertEqual(first.status, "accepted")
        self.assertEqual(repeat.status, "duplicate_suppressed")
        self.assertEqual(other.status, "accepted",
                         "the same window label under a DIFFERENT stream is a "
                         "different request")
        self.assertNotEqual(first.idempotency_key, other.idempotency_key)
        self.assertEqual(len(self.results_for(APPROVED_SOURCE,
                                              APPROVED_RESOURCE)), 1)
        self.assertEqual(len(self.results_for(TJR_SOURCE, TJR_RESOURCE)), 1)


class TestTheBridgeReportsBothCorpora(TwoSourceCase):

    def test_the_bridge_reports_both_streams_with_correct_attribution(self):
        self.initialise_both()
        self.acquire_for(APPROVED_SOURCE, APPROVED_RESOURCE, AUTHORIZATION_ID,
                         "alex-1")
        self.acquire_for(TJR_SOURCE, TJR_RESOURCE, TJR_AUTH, "tjr-1")

        entries = self.library_entries()
        self.assertEqual(len(entries), 2)
        by_source = {e["sourceId"]: e for e in entries}
        self.assertEqual(by_source[APPROVED_SOURCE]["traderId"], "ALEX_G")
        self.assertEqual(by_source[APPROVED_SOURCE]["strategyFamilyIds"],
                         [ALEX_FAMILY])
        self.assertEqual(by_source[TJR_SOURCE]["traderId"], "TJR")
        self.assertEqual(by_source[TJR_SOURCE]["strategyFamilyIds"],
                         [TJR_FAMILY])
        for entry in entries:
            with self.subTest(source=entry["sourceId"]):
                self.assertEqual(entry["attributionStatus"], "ATTRIBUTED")
                self.assertEqual(entry["lane"], "RESEARCH")
                self.assertEqual(entry["promotionStatus"], "NOT_A_TRADING_RULE")
                self.assertEqual(entry["acceptedContentIdentityBasis"],
                                 library.CONTENT_IDENTITY_BASIS)
                self.assertNotIn("contentHash", entry,
                                 "Lane A's transcript hash must never appear "
                                 "under Lane B's name")

    def test_no_artifact_appears_in_the_other_educators_corpus(self):
        self.initialise_both()
        self.acquire_for(APPROVED_SOURCE, APPROVED_RESOURCE, AUTHORIZATION_ID,
                         "alex-1")
        self.acquire_for(TJR_SOURCE, TJR_RESOURCE, TJR_AUTH, "tjr-1")

        by_source = {e["sourceId"]: e for e in self.library_entries()}
        alex, tjr = by_source[APPROVED_SOURCE], by_source[TJR_SOURCE]
        self.assertEqual(alex["acceptedContentIdentity"], ALEX_HASH_1)
        self.assertEqual(tjr["acceptedContentIdentity"], TJR_HASH_1)
        self.assertNotEqual(alex["artifactId"], tjr["artifactId"])
        self.assertNotEqual(alex["artifactPath"], tjr["artifactPath"])
        self.assertEqual(alex["authorizationId"], AUTHORIZATION_ID)
        self.assertEqual(tjr["authorizationId"], TJR_AUTH)

    def test_the_corpus_summary_separates_the_two_families(self):
        self.initialise_both()
        self.acquire_for(APPROVED_SOURCE, APPROVED_RESOURCE, AUTHORIZATION_ID,
                         "alex-1")
        self.acquire_for(APPROVED_SOURCE, APPROVED_RESOURCE, AUTHORIZATION_ID,
                         "alex-2")
        self.acquire_for(TJR_SOURCE, TJR_RESOURCE, TJR_AUTH, "tjr-1")

        summary = {b["strategyFamilyId"]: b for b in self.corpus_summary()}
        self.assertEqual(set(summary), {ALEX_FAMILY, TJR_FAMILY})
        self.assertEqual(summary[ALEX_FAMILY]["traderId"], "ALEX_G")
        self.assertEqual(summary[TJR_FAMILY]["traderId"], "TJR")
        self.assertEqual(summary[ALEX_FAMILY]["streams"], 1)
        self.assertEqual(summary[TJR_FAMILY]["streams"], 1)
        self.assertEqual(summary[ALEX_FAMILY]["acceptedObservations"], 2)
        self.assertEqual(summary[TJR_FAMILY]["acceptedObservations"], 1,
                         "Alex G's second observation must not be counted "
                         "toward the TJR corpus")
        for bucket in summary.values():
            self.assertEqual(bucket["promotionStatus"], "NOT_A_TRADING_RULE")

    def test_the_bridge_writes_nothing_and_stays_derived(self):
        self.initialise_both()
        self.acquire_for(APPROVED_SOURCE, APPROVED_RESOURCE, AUTHORIZATION_ID,
                         "alex-1")
        self.acquire_for(TJR_SOURCE, TJR_RESOURCE, TJR_AUTH, "tjr-1")
        first = json.dumps(self.library_entries(), sort_keys=True)
        second = json.dumps(self.library_entries(), sort_keys=True)
        self.assertEqual(first, second, "two reads must be byte-identical")


if __name__ == "__main__":
    unittest.main()

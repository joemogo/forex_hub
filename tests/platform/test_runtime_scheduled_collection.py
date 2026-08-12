#!/usr/bin/env python3
"""MOGO-016 -- bounded scheduled autonomous research collection.

The properties under test are not "the adapter builds a command". They are:

  * A HOST SCHEDULE CANNOT WIDEN WHAT MOGO IS ALLOWED TO ACQUIRE. The scheduled
    surface takes no source, no URL and no capability, and the committed spec
    has no field one could arrive in.
  * REPEATED SCHEDULING IS SAFE. Two invocations inside one collection window
    are the same request by construction, which is what makes a post-sleep
    catch-up run, a duplicate firing and a manual kickstart collapse into one
    acquisition instead of hammering the source.
  * REQUEST IDENTITY IS STILL NOT CONTENT IDENTITY.
  * THE AUTHORIZATION GATE IS UNCHANGED. `acquisition_authorization_record` was
    flipped in this milestone; these tests prove the enforcement behind it
    rather than trusting the flip.
"""

import ast
import json
import os
import sys
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "platform", "src"))

from mogo_platform.contracts import command as command_contract  # noqa: E402
from mogo_platform.contracts import ids                          # noqa: E402
from mogo_platform.runtime import connector_authorization as ca   # noqa: E402
from mogo_platform.runtime import errors as runtime_errors        # noqa: E402
from mogo_platform.runtime import policy                          # noqa: E402
from mogo_platform.runtime import registry                        # noqa: E402
from mogo_platform.runtime import scheduled_collection as sched    # noqa: E402
from mogo_platform.runtime import authorizations                  # noqa: E402

SCHEDULING_DIR = os.path.join(REPO_ROOT, "platform", "scheduling")
SPEC_PATH = os.path.join(SCHEDULING_DIR, "approved-collection.json")
TEMPLATE_PATH = os.path.join(SCHEDULING_DIR,
                             "com.mogo.research.collect.plist.template")
SCRIPT_PATH = os.path.join(SCHEDULING_DIR, "mogo_schedule.sh")
ADAPTER_PATH = os.path.join(REPO_ROOT, "platform", "src", "mogo_platform",
                            "runtime", "scheduled_collection.py")
AUTHORIZATION_DIR = os.path.join(REPO_ROOT, "docs", "trader-intelligence",
                                 "authorizations")
AUTH_RECORD_PATH = os.path.join(AUTHORIZATION_DIR, "AUTH-fxalexg-metadata.json")
TJR_AUTH_RECORD_PATH = os.path.join(AUTHORIZATION_DIR, "AUTH-tjr-metadata.json")

APPROVED_SOURCE = "SRC|youtube|c785970cc458"
APPROVED_RESOURCE = "hb7ot1_szWI"
APPROVED_AUTH = "96fc2793-b13b-467a-89a8-f31a76ec6d4c"

# MOGO-018 Step 3C -- the second approved educator, reused from committed
# evidence (docs/trader-intelligence/evidence/sources/EVSRC_TJR_20260727_002.json
# and docs/trader-intelligence/traders/tjr/profile.json), never invented here.
TJR_SOURCE = "SRC|youtube|11cd2542b5b0"
TJR_RESOURCE = "8qwEmE1DwYw"
TJR_AUTH = "3008510b-6c34-4a46-ba26-1c90bb9c728a"

# A fixed instant, as milliseconds. Never read from a clock: every function
# under test takes `now_ms` as an argument, so no test here waits for anything.
NOW_MS = 1_786_000_000_000
ISSUED_AT = "2026-08-11T00:00:00.000Z"


def read_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def read_text(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def committed_entries():
    """MOGO-018 Step 3B: the committed file is a SET; the entries live under it."""
    return read_json(SPEC_PATH)["entries"]


def spec(**over):
    base = dict(committed_entries()[0])
    base.update(over)
    return base


# ---------------------------------------------------------------------------
# The committed spec itself
# ---------------------------------------------------------------------------

class TestTheCommittedSpecIsTheApprovedOne(unittest.TestCase):

    def test_the_committed_spec_validates(self):
        for entry in committed_entries():
            sched.validate_spec(entry)
        sched.validate_collection_set(read_json(SPEC_PATH))

    def test_it_names_the_one_approved_source_and_capability(self):
        document = committed_entries()[0]
        self.assertEqual(document["sourceId"], APPROVED_SOURCE)
        self.assertEqual(document["resourceId"], APPROVED_RESOURCE)
        self.assertEqual(document["authorizationId"], APPROVED_AUTH)
        self.assertEqual(document["operation"], ca.OPERATION_METADATA)
        self.assertEqual(document["connectorId"], ca.CONNECTOR_ID)

    def test_the_spec_has_no_field_that_could_carry_a_destination(self):
        """The anti-injection property, asserted against the schema itself.

        There is no url/host/scheme/endpoint field to fill in, and an unknown
        field is refused rather than ignored -- so a destination cannot be
        introduced by editing this file either.
        """
        for forbidden in ("url", "uri", "host", "scheme", "endpoint",
                          "destination", "baseUrl", "channelUrl"):
            self.assertNotIn(forbidden, sched.SPEC_FIELDS)

    def test_the_spec_source_is_in_the_connector_registry(self):
        for entry in committed_entries():
            self.assertIn(entry["sourceId"], ca.APPROVED_DESTINATIONS)


# ---------------------------------------------------------------------------
# Fail-closed spec validation
# ---------------------------------------------------------------------------

class TestAnUnapprovedScheduleIsRefused(unittest.TestCase):

    def refused(self, **over):
        with self.assertRaises(runtime_errors.PlatformError):
            sched.validate_spec(spec(**over))

    def test_an_unapproved_source_is_refused(self):
        self.refused(sourceId="SRC|youtube|000000000000")

    def test_a_second_educators_source_cannot_be_scheduled(self):
        self.refused(sourceId="SRC|web|0123456789ab")

    def test_a_malformed_source_id_is_refused(self):
        self.refused(sourceId="UCgPeeHdxYRal0HTNeAkjqLg")

    def test_an_unknown_field_is_refused_not_ignored(self):
        """This is how a URL would arrive. It does not arrive."""
        self.refused(url="https://evil.example/whatever")

    def test_a_second_capability_cannot_be_scheduled(self):
        self.refused(capabilityId="CAP|research|ingest-local-artifact")

    def test_transcript_acquisition_cannot_be_scheduled(self):
        self.refused(operation="transcript")

    def test_discovery_cannot_be_scheduled(self):
        self.refused(operation="discover")

    def test_a_different_connector_is_refused(self):
        self.refused(connectorId="CONN|research|something-else")

    def test_a_different_connector_version_is_refused(self):
        self.refused(connectorVersion="9.9.9")

    def test_an_unaccepted_command_type_is_refused(self):
        self.refused(commandType="AcquireTranscript")

    def test_an_unadmitted_command_version_is_refused(self):
        self.refused(commandVersion=2)

    def test_a_crafted_resource_identifier_is_refused(self):
        for crafted in ("../../etc/passwd", "hb7ot1_szW", "hb7ot1_szWI!",
                        "x&url=https://evil.example", "", None):
            with self.subTest(resourceId=crafted):
                self.refused(resourceId=crafted)

    def test_a_malformed_authorization_id_is_refused(self):
        self.refused(authorizationId="not-a-uuid")

    def test_a_wrong_schema_version_is_refused(self):
        self.refused(schemaVersion="mogo.scheduled-collection.v2")

    def test_a_missing_required_field_is_refused(self):
        for field in sched.SPEC_REQUIRED_FIELDS:
            with self.subTest(missing=field):
                broken = spec()
                del broken[field]
                with self.assertRaises(runtime_errors.PlatformError):
                    sched.validate_spec(broken)

    def test_a_window_outside_the_approved_range_is_refused(self):
        for window in (0, 1, 59, sched.MAX_COLLECTION_WINDOW_SECONDS + 1,
                       -3600, "3600", 3600.0, True):
            with self.subTest(window=window):
                self.refused(collectionWindowSeconds=window)

    def test_a_non_mapping_spec_is_refused(self):
        for value in ([], "spec", 7, None):
            with self.subTest(value=value):
                with self.assertRaises(runtime_errors.PlatformError):
                    sched.validate_spec(value)


# ---------------------------------------------------------------------------
# The collection window
# ---------------------------------------------------------------------------

class TestTheCollectionWindow(unittest.TestCase):

    WINDOW = 21600

    def test_every_instant_inside_one_window_yields_one_label(self):
        first = sched.collection_window(NOW_MS, self.WINDOW)
        for offset in (0, 1, 999, 60_000, self.WINDOW * 1000 - 1):
            aligned = (NOW_MS // (self.WINDOW * 1000)) * self.WINDOW * 1000
            with self.subTest(offset=offset):
                self.assertEqual(
                    sched.collection_window(aligned + offset, self.WINDOW),
                    first)

    def test_the_next_window_is_a_different_label(self):
        self.assertNotEqual(
            sched.collection_window(NOW_MS, self.WINDOW),
            sched.collection_window(NOW_MS + self.WINDOW * 1000, self.WINDOW))

    def test_the_window_is_a_bucket_not_an_instant(self):
        """No wall-clock value appears in the label -- only width and index."""
        label = sched.collection_window(NOW_MS, self.WINDOW)
        self.assertEqual(label.split("|")[0], "W")
        self.assertNotIn(str(NOW_MS), label)

    def test_a_window_width_outside_the_approved_range_is_refused(self):
        for width in (0, 59, sched.MAX_COLLECTION_WINDOW_SECONDS + 1):
            with self.subTest(width=width):
                with self.assertRaises(runtime_errors.PlatformError):
                    sched.collection_window(NOW_MS, width)

    def test_a_non_integer_instant_is_refused(self):
        for value in ("now", 1.5, None, True, -1):
            with self.subTest(value=value):
                with self.assertRaises(runtime_errors.PlatformError):
                    sched.collection_window(value, self.WINDOW)


# ---------------------------------------------------------------------------
# Request identity
# ---------------------------------------------------------------------------

class TestScheduledRequestIdentity(unittest.TestCase):

    def key_at(self, now_ms, window=21600):
        document = spec(collectionWindowSeconds=window)
        return sched.scheduled_idempotency_key(
            document, sched.collection_window(now_ms, window))

    def test_two_runs_in_one_window_are_the_same_request(self):
        """The property that makes a post-wake catch-up run harmless."""
        self.assertEqual(self.key_at(NOW_MS), self.key_at(NOW_MS + 60_000))

    def test_the_next_window_is_a_new_request(self):
        self.assertNotEqual(self.key_at(NOW_MS),
                            self.key_at(NOW_MS + 21600 * 1000))

    def test_the_key_is_a_sha256(self):
        self.assertTrue(ids.is_sha256_hex(self.key_at(NOW_MS)))

    def test_it_differs_from_the_unwindowed_catalog_key(self):
        """Otherwise the scheduler would collide with a manual acquisition."""
        catalog = ids.idempotency_key("metadata_acquisition", {
            "sourceId": APPROVED_SOURCE, "connectorVersion": "1.0.0"})
        self.assertNotEqual(self.key_at(NOW_MS), catalog)

    def test_a_different_resource_is_a_different_request(self):
        """Catalog section I's metadata row omits the resource, so two videos
        would collide on one key. The scheduled composition includes it."""
        window = sched.collection_window(NOW_MS, 21600)
        one = sched.scheduled_idempotency_key(spec(), window)
        other = sched.scheduled_idempotency_key(
            spec(resourceId="dQw4w9WgXcQ"), window)
        self.assertNotEqual(one, other)


class TestTheIdempotencyExtensionIsDeclaredNotSmuggled(unittest.TestCase):

    def test_the_catalog_transcription_is_untouched(self):
        self.assertEqual(len(ids.IDEMPOTENCY_KEY_COMPOSITION), 10)
        self.assertNotIn(sched.IDEMPOTENCY_OPERATION,
                         ids.IDEMPOTENCY_KEY_COMPOSITION)

    def test_exactly_one_extension_exists_and_it_is_this_one(self):
        self.assertEqual(tuple(ids.IDEMPOTENCY_KEY_EXTENSIONS),
                         (sched.IDEMPOTENCY_OPERATION,))

    def test_the_extension_declares_no_timestamp_or_attempt_part(self):
        forbidden = ("timestamp", "issuedat", "occurredat", "recordedat",
                     "attempt", "attemptnumber", "retry", "now", "nonce")
        for parts in ids.IDEMPOTENCY_KEY_EXTENSIONS.values():
            for part in parts:
                with self.subTest(part=part):
                    self.assertNotIn(part.lower(), forbidden)

    def test_an_undeclared_part_is_still_refused(self):
        with self.assertRaises(Exception):
            ids.idempotency_key(sched.IDEMPOTENCY_OPERATION, {
                "sourceId": APPROVED_SOURCE, "resourceId": APPROVED_RESOURCE,
                "connectorVersion": "1.0.0", "collectionWindow": "W|60|1",
                "extra": "smuggled"})

    def test_an_unknown_operation_is_still_refused(self):
        with self.assertRaises(Exception):
            ids.idempotency_key("invented_operation", {})


# ---------------------------------------------------------------------------
# The built command
# ---------------------------------------------------------------------------

class TestTheScheduledCommand(unittest.TestCase):

    def build(self, **over):
        return sched.build_command(spec(**over), NOW_MS, ISSUED_AT)

    def test_it_validates_through_the_ordinary_command_contract(self):
        envelope, payload, _window = self.build()
        command_contract.validate_command(envelope, payload=payload)

    def test_it_carries_exactly_one_subject_source(self):
        """Zero or two SRC| refs both deny at the policy gate."""
        envelope, _payload, _window = self.build()
        sources = [ref for ref in envelope["inputRefs"]
                   if ref.startswith("SRC|")]
        self.assertEqual(sources, [APPROVED_SOURCE])

    def test_it_does_not_claim_to_be_an_operator(self):
        """No human is present when this runs; the audit trail must say so."""
        envelope, _payload, _window = self.build()
        self.assertEqual(envelope["issuedBy"],
                         "workflow:scheduled-research-collection")
        self.assertFalse(envelope["issuedBy"].startswith("operator:"))

    def test_no_url_appears_anywhere_in_the_command(self):
        envelope, payload, _window = self.build()
        blob = json.dumps([envelope, payload])
        for fragment in ("http://", "https://", "youtube.com", "oembed"):
            with self.subTest(fragment=fragment):
                self.assertNotIn(fragment, blob)

    def test_it_targets_the_one_approved_capability(self):
        envelope, _payload, _window = self.build()
        self.assertEqual(envelope["targetCapability"],
                         "CAP|research|acquire-approved-source-metadata")

    def test_the_policy_context_names_the_authorization_and_one_operation(self):
        envelope, _payload, _window = self.build()
        context = envelope["policyContext"]
        self.assertEqual(context["authorizationId"], APPROVED_AUTH)
        self.assertEqual(context["permittedOperations"], ["metadata"])

    def test_the_payload_hash_is_the_hash_of_the_payload(self):
        envelope, payload, _window = self.build()
        self.assertEqual(envelope["payloadHash"], ids.content_hash_of(payload))

    def test_every_invocation_mints_fresh_identifiers(self):
        first, _p1, _w1 = self.build()
        second, _p2, _w2 = self.build()
        self.assertNotEqual(first["commandId"], second["commandId"])
        self.assertNotEqual(first["workflowId"], second["workflowId"])
        # ...but the REQUEST IDENTITY is unchanged inside one window.
        self.assertEqual(first["idempotencyKey"], second["idempotencyKey"])

    def test_an_unapproved_spec_never_produces_a_command(self):
        with self.assertRaises(runtime_errors.PlatformError):
            sched.build_command(spec(sourceId="SRC|web|0123456789ab"),
                                NOW_MS, ISSUED_AT)


# ---------------------------------------------------------------------------
# The adapter reaches nothing
# ---------------------------------------------------------------------------

class TestTheAdapterReachesNothing(unittest.TestCase):

    BANNED = ("socket", "ssl", "http", "urllib", "requests", "httpx",
              "asyncio", "aiohttp", "subprocess", "shutil")

    def test_it_imports_no_network_client_and_no_process_launcher(self):
        tree = ast.parse(read_text(ADAPTER_PATH))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        for banned in self.BANNED:
            with self.subTest(module=banned):
                self.assertNotIn(banned, imported)

    def test_it_performs_no_file_or_clock_access(self):
        """`now_ms` is always an argument, and the spec is read by the CLI."""
        source = read_text(ADAPTER_PATH)
        tree = ast.parse(source)
        called = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                target = node.func
                if isinstance(target, ast.Name):
                    called.add(target.id)
                elif isinstance(target, ast.Attribute):
                    called.add(target.attr)
        for forbidden in ("open", "time", "now", "utcnow", "monotonic",
                          "makedirs", "remove", "replace", "system", "popen"):
            with self.subTest(call=forbidden):
                self.assertNotIn(forbidden, called)


# ---------------------------------------------------------------------------
# acquisition_authorization_record -- the flip, and the enforcement behind it
# ---------------------------------------------------------------------------

class TestTheAcquisitionAuthorizationRecordGate(unittest.TestCase):

    def gate(self, name):
        return {entry["gate"]: entry
                for entry in registry.CONNECTOR_GATES}[name]

    def test_the_record_the_gate_describes_actually_exists(self):
        """The gate previously said the records did not exist. This is the one
        that disproved it, and it is validated by the real validator."""
        record = read_json(AUTH_RECORD_PATH)
        authorizations.validate_record(record)
        self.assertEqual(record["sourceId"], APPROVED_SOURCE)
        self.assertEqual(record["authorizationId"], APPROVED_AUTH)
        self.assertEqual(list(record["permittedOperations"]), ["metadata"])

    def test_the_record_was_decided_by_a_human_not_by_automation(self):
        record = read_json(AUTH_RECORD_PATH)
        self.assertTrue(record["decisionAuthority"].startswith("operator:"))
        for prefix in authorizations.PROHIBITED_AUTHORITY_PREFIXES:
            with self.subTest(prefix=prefix):
                self.assertNotIn(prefix, record["decisionAuthority"])

    def test_every_real_approved_source_has_such_a_record(self):
        """The gate's standing obligation, checked rather than asserted.

        Step 3C makes this test do real work for the first time. With one source
        it could compare a tuple; with two it has to READ the committed
        authorization records and prove the set they cover is exactly the set of
        approved sources. A third destination added without a record now fails
        here, which is the whole point of the obligation.
        """
        records = [read_json(AUTH_RECORD_PATH), read_json(TJR_AUTH_RECORD_PATH)]
        for record in records:
            with self.subTest(source=record["sourceId"]):
                authorizations.validate_record(record)
                self.assertEqual(list(record["permittedOperations"]),
                                 ["metadata"])
        self.assertEqual({record["sourceId"] for record in records},
                         set(ca.approved_source_ids()))

    def test_the_tjr_record_authorizes_metadata_only_and_names_its_evidence(self):
        """TJR is authorized for the SAME narrow operation as Alex G.

        The archived TJR transcript is `restricted_third_party`; this record
        must not be readable as authorizing it.
        """
        record = read_json(TJR_AUTH_RECORD_PATH)
        authorizations.validate_record(record)
        self.assertEqual(record["sourceId"], TJR_SOURCE)
        self.assertEqual(record["authorizationId"], TJR_AUTH)
        self.assertEqual(list(record["permittedOperations"]), ["metadata"])
        self.assertEqual(record["policyStatus"], "PERMITTED_PUBLIC_METADATA")
        self.assertTrue(record["decisionAuthority"].startswith("operator:"))
        # It cites the committed evidence the channel identity came from,
        # rather than asserting a channel on its own authority.
        self.assertTrue(os.path.exists(
            os.path.join(REPO_ROOT, record["sourceTermsSnapshotRef"])))

    def test_all_four_connector_gates_are_now_satisfied(self):
        self.assertEqual(len(registry.CONNECTOR_GATES), 4)
        for entry in registry.CONNECTOR_GATES:
            with self.subTest(gate=entry["gate"]):
                self.assertIs(entry["satisfied"], True)
                self.assertTrue(entry["authority"].strip())
                self.assertTrue(entry["requires"].strip())

    def test_the_gate_no_longer_claims_the_records_do_not_exist(self):
        self.assertNotIn("the records do not",
                         self.gate("acquisition_authorization_record")["requires"])

    def test_flipping_it_changed_no_enforcement_a_missing_record_still_denies(self):
        """The flip is a DISCLOSURE correction. Authorization is enforced by
        policy.evaluate(), and it denies exactly as before."""
        decision = policy.evaluate(
            policy.OPERATION_CLASS_ACQUISITION, ("metadata",), None, NOW_MS,
            resolution_problem=policy.REASON_NO_RECORD)
        self.assertFalse(decision.permitted)
        self.assertEqual(decision.reason, policy.REASON_NO_RECORD)

    def test_an_unauthorized_operation_still_denies(self):
        record = dict(read_json(AUTH_RECORD_PATH))
        record["expiresAtMs"] = None
        record["supersededBy"] = None
        decision = policy.evaluate(policy.OPERATION_CLASS_ACQUISITION,
                                   ("transcript",), record, NOW_MS)
        self.assertFalse(decision.permitted)
        self.assertEqual(decision.reason, policy.REASON_OPERATION_NOT_PERMITTED)

    def test_the_approved_operation_is_still_permitted(self):
        """A gate that always denies proves nothing about a gate that governs."""
        record = dict(read_json(AUTH_RECORD_PATH))
        record["expiresAtMs"] = None
        record["supersededBy"] = None
        decision = policy.evaluate(policy.OPERATION_CLASS_ACQUISITION,
                                   ("metadata",), record, NOW_MS)
        self.assertTrue(decision.permitted, decision.reason)


# ---------------------------------------------------------------------------
# The host schedule artifacts
# ---------------------------------------------------------------------------

class TestTheLaunchdArtifacts(unittest.TestCase):

    def test_the_template_and_installer_are_committed(self):
        for path in (TEMPLATE_PATH, SCRIPT_PATH, SPEC_PATH):
            with self.subTest(path=os.path.basename(path)):
                self.assertTrue(os.path.isfile(path))

    def test_the_job_can_invoke_only_the_collect_subcommand(self):
        """Its arguments are the interpreter, the entry point, and `collect`.

        `collect` takes no source, URL, resource or capability argument, so
        there is nothing in this plist that could become a fetch target.
        """
        template = read_text(TEMPLATE_PATH)
        arguments = template.split("<key>ProgramArguments</key>")[1]
        arguments = arguments.split("</array>")[0]
        self.assertIn("<string>collect</string>", arguments)
        for forbidden in ("submit", "--command-file", "reset", "review",
                          "authorize", "http", "youtube"):
            with self.subTest(fragment=forbidden):
                self.assertNotIn(forbidden, arguments)

    def test_the_template_carries_no_secret(self):
        """Scanned over the plist BODY. The comment above it is allowed to say
        the word `secrets` -- it is the paragraph explaining why there are none.
        """
        body = read_text(TEMPLATE_PATH).split("<plist version=")[1].lower()
        for marker in ("password", "secret", "token", "api_key", "apikey",
                       "authorization:", "bearer", "credential"):
            with self.subTest(marker=marker):
                self.assertNotIn(marker, body)

    def test_the_job_does_not_run_at_load(self):
        """A job that fires when installed makes 'the scheduler triggered this'
        unprovable."""
        template = read_text(TEMPLATE_PATH)
        block = template.split("<key>RunAtLoad</key>")[1].split("<key>")[0]
        self.assertIn("<false/>", block)

    def test_the_schedule_uses_the_wake_coalescing_key(self):
        """StartCalendarInterval catches up ONCE after sleep; StartInterval
        would silently drop every missed window."""
        template = read_text(TEMPLATE_PATH)
        self.assertIn("<key>StartCalendarInterval</key>", template)
        self.assertNotIn("<key>StartInterval</key>", template)

    def test_the_installer_pins_an_interpreter_meeting_the_platform_floor(self):
        script = read_text(SCRIPT_PATH)
        self.assertIn('PYTHON="/usr/local/bin/python3"', script)
        self.assertIn("(3, 14)", script)

    def test_the_installer_offers_a_one_word_disable(self):
        script = read_text(SCRIPT_PATH)
        self.assertIn("disable|uninstall)", script)
        self.assertIn("bootout", script)

    def test_the_installer_refuses_a_window_wider_than_the_cadence(self):
        """A schedule that would self-suppress is refused, not installed."""
        script = read_text(SCRIPT_PATH)
        self.assertIn('[ "$window" -le "$cadence" ]', script)


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------------------
# MOGO-018 Step 3B -- the bounded multi-entry collection set
# ---------------------------------------------------------------------------

class TestBoundedCollectionSet(unittest.TestCase):
    """The invariant: one window issues AT MOST ONE acquisition per entry.

    N is decided entirely by the committed file. Nothing is discovered, nothing
    is added at runtime, and no link inside acquired content is followed -- so
    the set IS the bound.

    Multi-entry behaviour is proved with LOCAL TEST-ONLY entries. No second real
    educator is authorized, because proving the collector can iterate must not
    require widening what it may collect.
    """

    def document(self, entries=None, **over):
        base = {"schemaVersion": sched.SET_SCHEMA_VERSION,
                "entries": committed_entries() if entries is None else entries}
        base.update(over)
        return base

    def local_entry(self, **over):
        """A second entry for the SAME approved source, different resource.

        Deliberately not a second source: the connector registry still holds
        exactly one, and this suite must not change that.
        """
        entry = dict(committed_entries()[0])
        entry["resourceId"] = "dQw4w9WgXcQ"
        entry.update(over)
        return entry

    def refused(self, document):
        with self.assertRaises(runtime_errors.PlatformError):
            sched.validate_collection_set(document)

    # -- current production compatibility ----------------------------------

    def test_the_committed_production_set_has_exactly_two_entries(self):
        """Step 3C added TJR. The Alex G entry is unchanged and still FIRST.

        Committed order is the processing order, so pinning the index is
        pinning behaviour, not formatting.
        """
        entries = sched.validate_collection_set(read_json(SPEC_PATH))
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["sourceId"], APPROVED_SOURCE)
        self.assertEqual(entries[0]["resourceId"], APPROVED_RESOURCE)
        self.assertEqual(entries[1]["sourceId"], TJR_SOURCE)
        self.assertEqual(entries[1]["resourceId"], TJR_RESOURCE)
        self.assertEqual(ca.approved_source_ids(), (TJR_SOURCE, APPROVED_SOURCE))

    def test_a_one_entry_set_builds_the_same_command_as_before(self):
        """Compatibility: the entry schema and command build are UNCHANGED."""
        entry = sched.validate_collection_set(read_json(SPEC_PATH))[0]
        envelope, payload, window = sched.build_command(entry, NOW_MS, ISSUED_AT)
        direct, _payload, direct_window = sched.build_command(
            sched.validate_spec(spec()), NOW_MS, ISSUED_AT)
        self.assertEqual(window, direct_window)
        self.assertEqual(envelope["idempotencyKey"], direct["idempotencyKey"])
        self.assertEqual(envelope["targetCapability"], entry["capabilityId"])
        self.assertEqual(payload["sourceId"], APPROVED_SOURCE)

    # -- N entries produce at most N requests ------------------------------

    def test_two_entries_produce_exactly_two_distinct_requests(self):
        entries = sched.validate_collection_set(
            self.document([committed_entries()[0], self.local_entry()]))
        self.assertEqual(len(entries), 2)
        keys = [sched.build_command(e, NOW_MS, ISSUED_AT)[0]["idempotencyKey"]
                for e in entries]
        self.assertEqual(len(set(keys)), 2, "each entry is its own request")

    def test_n_entries_produce_exactly_n_requests_never_more(self):
        for count in (1, 2, 3, 5, sched.MAX_COLLECTION_ENTRIES):
            with self.subTest(entries=count):
                built = [self.local_entry(resourceId="res%08d" % index)
                         for index in range(count)]
                entries = sched.validate_collection_set(self.document(built))
                self.assertEqual(len(entries), count)
                keys = {sched.build_command(e, NOW_MS, ISSUED_AT)[0]
                        ["idempotencyKey"] for e in entries}
                self.assertEqual(len(keys), count,
                                 "one window issues at most one request per entry")

    def test_the_entry_count_is_bounded(self):
        """A fat-fingered file must not quietly become a crawler."""
        too_many = [self.local_entry(resourceId="res%08d" % index)
                    for index in range(sched.MAX_COLLECTION_ENTRIES + 1)]
        self.refused(self.document(too_many))

    def test_processing_order_is_the_committed_file_order(self):
        """Deterministic, and reviewable: what you read is what runs."""
        built = [self.local_entry(resourceId="res%08d" % index)
                 for index in range(4)]
        for _ in range(3):
            entries = sched.validate_collection_set(self.document(built))
            self.assertEqual([e["resourceId"] for e in entries],
                             ["res%08d" % index for index in range(4)])

    def test_each_entry_keeps_its_own_source_and_resource_identity(self):
        built = [committed_entries()[0], self.local_entry()]
        entries = sched.validate_collection_set(self.document(built))
        identities = [(e["sourceId"], e["resourceId"]) for e in entries]
        self.assertEqual(identities,
                         [(APPROVED_SOURCE, APPROVED_RESOURCE),
                          (APPROVED_SOURCE, "dQw4w9WgXcQ")])
        for entry, identity in zip(entries, identities):
            _envelope, payload, _window = sched.build_command(
                entry, NOW_MS, ISSUED_AT)
            self.assertEqual((payload["sourceId"], payload["resourceId"]),
                             identity)

    def test_streams_do_not_share_a_request_identity(self):
        """Requirements 6, 7 and 8 at the request layer.

        Different streams get different idempotency keys, so UNCHANGED, CHANGED
        and duplicate suppression all remain per-stream -- one entry can never
        suppress, advance or contaminate another's history.
        """
        first, second = sched.validate_collection_set(
            self.document([committed_entries()[0], self.local_entry()]))
        key_a = sched.build_command(first, NOW_MS, ISSUED_AT)[0]["idempotencyKey"]
        key_b = sched.build_command(second, NOW_MS, ISSUED_AT)[0]["idempotencyKey"]
        self.assertNotEqual(key_a, key_b)
        # ...and within one stream, the same window is still the same request.
        repeat = sched.build_command(first, NOW_MS + 1000, ISSUED_AT)[0]
        self.assertEqual(repeat["idempotencyKey"], key_a)

    # -- fail closed, for the WHOLE window ---------------------------------

    def test_one_malformed_entry_refuses_the_whole_set(self):
        """Preferred model: refuse the window rather than partly execute it.

        Silently skipping the bad entry would make the schedule do less than the
        committed file says, and nobody would be told.
        """
        for broken in ({**self.local_entry(), "sourceId": "SRC|web|0123456789ab"},
                       {**self.local_entry(), "operation": "transcript"},
                       {**self.local_entry(), "url": "https://evil.example/x"},
                       {**self.local_entry(), "resourceId": "../../etc/passwd"},
                       {**self.local_entry(), "capabilityId": "CAP|research|ingest-local-artifact"}):
            with self.subTest(entry=broken.get("sourceId")):
                self.refused(self.document([committed_entries()[0], broken]))

    def test_a_missing_entry_field_refuses_the_whole_set(self):
        broken = dict(self.local_entry())
        del broken["authorizationId"]
        self.refused(self.document([committed_entries()[0], broken]))

    def test_a_malformed_set_document_is_refused(self):
        self.refused({"schemaVersion": sched.SET_SCHEMA_VERSION})       # no entries
        self.refused(self.document([]))                                  # empty
        self.refused(self.document("not-a-list"))
        self.refused(self.document(entries=[committed_entries()[0]],
                                   schemaVersion="mogo.scheduled-collection.v1"))
        self.refused({"entries": committed_entries()})                   # no version
        for value in (None, [], "set", 17):
            with self.subTest(document=value):
                self.refused(value)

    def test_an_unknown_document_field_is_refused(self):
        """A URL cannot arrive at the document level either."""
        self.refused(self.document(url="https://evil.example/x"))
        self.refused(self.document(discover=True))

    def test_a_duplicated_stream_is_refused(self):
        """Two entries for one stream would collapse into one request."""
        self.refused(self.document([committed_entries()[0],
                                    dict(committed_entries()[0])]))

    def test_entries_must_agree_on_the_collection_window(self):
        """The installer checks ONE window against the cadence."""
        self.refused(self.document([committed_entries()[0],
                                    self.local_entry(collectionWindowSeconds=120)]))

    def test_validation_happens_before_any_command_is_built(self):
        """No acquisition can begin for a window the set does not pass."""
        source = read_text(os.path.join(REPO_ROOT, "platform", "src",
                                        "mogo_platform", "runtime", "cli.py"))
        collect = source[source.index("def cmd_collect"):source.index("def cmd_library")]
        load_at = collect.index("load_approved_collection_entries()")
        build_at = collect.index("scheduled_collection.build_command")
        submit_at = collect.index("runtime.submit(")
        self.assertLess(load_at, build_at)
        self.assertLess(build_at, submit_at)

    # -- the schedule and its surface are unchanged ------------------------

    def test_the_installer_reads_one_window_from_the_set(self):
        script = read_text(SCRIPT_PATH)
        self.assertIn("disagree on collectionWindowSeconds", script)
        self.assertIn('[ "$window" -le "$cadence" ]', script)

    def test_the_launchd_job_still_invokes_one_collect_per_window(self):
        """One scheduler invocation processes the whole bounded list."""
        template = read_text(TEMPLATE_PATH)
        arguments = template.split("<key>ProgramArguments</key>")[1]
        arguments = arguments.split("</array>")[0]
        self.assertEqual(arguments.count("<string>collect</string>"), 1)
        self.assertIn("<key>StartCalendarInterval</key>", template)

    def test_exactly_two_real_sources_are_authorized_and_no_third(self):
        """Step 3C: Alex G and TJR. ICT and CRT remain unauthorized."""
        self.assertEqual(ca.approved_source_ids(), (TJR_SOURCE, APPROVED_SOURCE))
        self.assertEqual({e["sourceId"] for e in committed_entries()},
                         {APPROVED_SOURCE, TJR_SOURCE})

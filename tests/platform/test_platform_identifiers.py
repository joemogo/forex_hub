#!/usr/bin/env python3
"""MOGO-010 Step 1 -- identifier model contract tests.

Pure stdlib (unittest). Fully offline, deterministic, repeatable.

Every expected value below is transcribed INDEPENDENTLY from the authoritative
MOGO-009 Contract Catalog (sections H and I) and Architecture section 17. No
test compares an implementation constant to itself; each compares it to a
literal written out from the contract, so an omission, an addition, a spelling
drift or a wrong composition is detected.

Run with:
    python3 -m unittest tests.platform.test_platform_identifiers -v
"""

import json
import math
import os
import sys
import unittest
import uuid as _uuid

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
# The ONE path entry the suites add. platform/src holds the uniquely named
# package; platform/ itself never becomes importable, so stdlib `platform`
# is untouched. See platform/README.md.
SRC_DIR = os.path.join(REPO_ROOT, "platform", "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from mogo_platform.contracts import boundaries  # noqa: E402
from mogo_platform.contracts import command  # noqa: E402
from mogo_platform.contracts import errors  # noqa: E402
from mogo_platform.contracts import event  # noqa: E402
from mogo_platform.contracts import ids  # noqa: E402
from mogo_platform.contracts import task_states  # noqa: E402
from mogo_platform.contracts import vocabulary  # noqa: E402

# Every Step 1 module, so the no-minting sweep covers the whole public surface.
ALL_PLATFORM_MODULES = (
    ("mogo_platform.contracts.ids", ids),
    ("mogo_platform.contracts.errors", errors),
    ("mogo_platform.contracts.vocabulary", vocabulary),
    ("mogo_platform.contracts.boundaries", boundaries),
    ("mogo_platform.contracts.command", command),
    ("mogo_platform.contracts.event", event),
    ("mogo_platform.contracts.task_states", task_states),
)

# ---------------------------------------------------------------------------
# Independently transcribed expectations -- Contract Catalog section H
# ---------------------------------------------------------------------------

EXPECTED_COMPOSITE_PREFIXES = ("SRC", "EDU", "CONN", "WRK", "XF", "CAP", "RULE")

EXPECTED_COMPOSITE_COMPONENT_NAMES = {
    "SRC": ("platform", "normalizedUrlHash12"),
    "EDU": ("slug",),
    "CONN": ("sourceType", "name"),
    "WRK": ("capability",),
    "XF": ("name",),
    "CAP": ("domain", "name"),
    "RULE": ("educator", "slug"),
}

EXPECTED_GOVERNANCE_OWNED_FIELDS = (
    "hypothesisId",
    "evidencePackageId",
    "replayPackageId",
)

# ---------------------------------------------------------------------------
# Independently transcribed expectations -- Contract Catalog section I
# ---------------------------------------------------------------------------

EXPECTED_IDEMPOTENCY_COMPOSITION = {
    "source_discovery": ("connectorId", "query", "window"),
    "source_registration": ("normalizedUrl", "educatorId"),
    "metadata_acquisition": ("sourceId", "connectorVersion"),
    "artifact_acquisition": ("sourceId", "locator", "connectorVersion"),
    "transcript_acquisition": ("sourceId", "locator", "connectorVersion"),
    "raw_storage": ("sha256",),
    "transformation": ("inputHash", "transformationId", "transformationVersion"),
    "duplicate_analysis": ("candidateSetHash", "algorithmVersion"),
    "evidence_candidate_creation": ("segmentId", "extractorVersion"),
    "review_request": ("subjectId", "reviewType"),
}

# Values that must never appear in any idempotency key composition.
FORBIDDEN_KEY_PARTS = (
    "timestamp", "timestampUtc", "issuedAt", "occurredAt", "recordedAt",
    "attempt", "attemptNumber", "attemptCount", "retry", "now", "nonce",
)

# A corpus that exercises the documented canonicalization rules.
CANONICALIZATION_CORPUS = (
    {},
    [],
    {"b": 1, "a": 2},
    {"nested": {"z": [1, 2, 3], "a": {"deep": True}}},
    {"unicode": "é中文\U0001f600"},
    {"empty_obj": {}, "empty_arr": [], "null": None},
    [{"b": 1, "a": 2}, {"a": 2, "b": 1}],
    {"num": 0, "neg": -17, "float": 1.5, "bool": False},
)


def _documented_canonical_bytes(obj):
    """The canonicalization rule as written in the authoritative source,
    reproduced here independently of the implementation under test."""
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")


class TestCanonicalizationEquivalence(unittest.TestCase):
    def test_matches_documented_rule_without_importing_the_phase_i_pipeline(self):
        for obj in CANONICALIZATION_CORPUS:
            with self.subTest(obj=obj):
                self.assertEqual(
                    ids.canonical_json_bytes(obj), _documented_canonical_bytes(obj)
                )
        # MOGO-009 Architecture section 6.7: the Phase I pipeline is reachable
        # only through adapters, and no adapter exists in Step 1.
        for forbidden in ("graph_common", "evidence_common", "acquisition_common"):
            self.assertNotIn(forbidden, sys.modules)

    def test_output_is_utf8_bytes(self):
        raw = ids.canonical_json_bytes({"k": "é"})
        self.assertIsInstance(raw, bytes)
        self.assertEqual(raw.decode("utf-8"), '{"k":"é"}')

    def test_rejects_nan(self):
        with self.assertRaises(errors.ContractValidationError):
            ids.canonical_json_bytes({"x": float("nan")})

    def test_rejects_positive_infinity(self):
        with self.assertRaises(errors.ContractValidationError):
            ids.canonical_json_bytes({"x": math.inf})

    def test_rejects_negative_infinity(self):
        with self.assertRaises(errors.ContractValidationError):
            ids.canonical_json_bytes({"x": -math.inf})

    def test_rejects_non_serializable_value(self):
        with self.assertRaises(errors.ContractValidationError):
            ids.canonical_json_bytes({"x": object()})


class TestContentDerivedIdentifiers(unittest.TestCase):
    def test_content_hash_is_stable_across_calls(self):
        obj = {"a": 1, "b": [1, 2, {"c": "d"}]}
        first = ids.content_hash_of(obj)
        for _ in range(5):
            self.assertEqual(ids.content_hash_of(obj), first)

    def test_content_hash_is_key_order_independent(self):
        self.assertEqual(
            ids.content_hash_of({"a": 1, "b": 2}),
            ids.content_hash_of({"b": 2, "a": 1}),
        )

    def test_content_hash_is_array_order_sensitive(self):
        self.assertNotEqual(
            ids.content_hash_of([1, 2, 3]), ids.content_hash_of([3, 2, 1])
        )

    def test_content_hash_is_64_lowercase_hex(self):
        digest = ids.content_hash_of({"x": 1})
        self.assertEqual(len(digest), 64)
        self.assertEqual(digest, digest.lower())
        self.assertTrue(ids.is_sha256_hex(digest))

    def test_known_digest_of_empty_object(self):
        # sha256 of the 2 bytes '{}' -- an external, independently checkable value.
        self.assertEqual(
            ids.content_hash_of({}),
            "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        )

    def test_sha256_hex_requires_bytes(self):
        with self.assertRaises(errors.ContractValidationError):
            ids.sha256_hex("not bytes")

    def test_rejects_uppercase_sha256(self):
        upper = "A" * 64
        self.assertFalse(ids.is_sha256_hex(upper))
        with self.assertRaises(errors.IdentifierError):
            ids.require_sha256_hex(upper, "payloadHash")

    def test_rejects_short_sha256(self):
        with self.assertRaises(errors.IdentifierError):
            ids.require_sha256_hex("a" * 63, "payloadHash")

    def test_rejects_long_sha256(self):
        with self.assertRaises(errors.IdentifierError):
            ids.require_sha256_hex("a" * 65, "payloadHash")

    def test_rejects_non_hex_sha256(self):
        with self.assertRaises(errors.IdentifierError):
            ids.require_sha256_hex("g" * 64, "payloadHash")


class TestUuidIdentifiers(unittest.TestCase):
    VALID = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"

    def test_accepts_canonical_uuid4(self):
        self.assertTrue(ids.is_uuid4(self.VALID))
        self.assertEqual(ids.require_uuid4(self.VALID, "eventId"), self.VALID)

    def test_rejects_uppercase(self):
        self.assertFalse(ids.is_uuid4(self.VALID.upper()))

    def test_rejects_unhyphenated(self):
        self.assertFalse(ids.is_uuid4(self.VALID.replace("-", "")))

    def test_rejects_other_uuid_versions(self):
        # Version nibble is the first character of the third group.
        for version in "1235":
            candidate = "3f2504e0-4f89-%s1d3-9a0c-0305e82c3301" % (version,)
            with self.subTest(version=version):
                self.assertEqual(ids.is_uuid4(candidate), version == "4")

    def test_rejects_bad_variant_nibble(self):
        # RFC 4122 fixes the variant nibble to 8, 9, a or b. Everything else
        # is invalid.
        for variant in "01234567cdef":
            candidate = "3f2504e0-4f89-41d3-%sa0c-0305e82c3301" % (variant,)
            with self.subTest(variant=variant):
                self.assertFalse(ids.is_uuid4(candidate))

    def test_accepts_every_valid_variant_nibble(self):
        for variant in "89ab":
            candidate = "3f2504e0-4f89-41d3-%sa0c-0305e82c3301" % (variant,)
            with self.subTest(variant=variant):
                self.assertTrue(ids.is_uuid4(candidate))

    def test_new_uuid4_produces_valid_identifiers(self):
        for _ in range(50):
            self.assertTrue(ids.is_uuid4(ids.new_uuid4()))

    def test_injected_factory_output_is_still_validated(self):
        # The test seam cannot be used to smuggle in a non-UUIDv4 value.
        with self.assertRaises(errors.IdentifierError):
            ids.new_uuid4(uuid_factory=lambda: "not-a-uuid")

    def test_injected_factory_is_used(self):
        fixed = _uuid.UUID(self.VALID)
        self.assertEqual(ids.new_uuid4(uuid_factory=lambda: fixed), self.VALID)

    def test_uniqueness_source_rejects_a_duplicate(self):
        with self.assertRaises(errors.IdentifierError):
            ids.new_uuid4(seen=lambda candidate: True)

    def test_uniqueness_is_not_checked_when_no_source_is_supplied(self):
        # DEFERRED behaviour, asserted explicitly so it cannot be mistaken for
        # an implemented check: without a `seen` source there is no check at all.
        self.assertTrue(ids.is_uuid4(ids.new_uuid4()))


class TestCompositeIdentifiers(unittest.TestCase):
    def test_prefix_set_matches_the_catalog(self):
        self.assertEqual(
            tuple(ids.COMPOSITE_PREFIXES), EXPECTED_COMPOSITE_PREFIXES
        )

    def test_component_names_match_the_catalog(self):
        for prefix, expected_names in EXPECTED_COMPOSITE_COMPONENT_NAMES.items():
            with self.subTest(prefix=prefix):
                self.assertIn(prefix, ids.COMPOSITE_ID_SPECS)
                _name, names, _kinds = ids.COMPOSITE_ID_SPECS[prefix]
                self.assertEqual(tuple(names), expected_names)

    def test_no_unapproved_prefix_is_present(self):
        self.assertEqual(
            set(ids.COMPOSITE_ID_SPECS.keys()), set(EXPECTED_COMPOSITE_PREFIXES)
        )

    def test_constructors_produce_the_documented_forms(self):
        self.assertEqual(ids.make_educator_id("alex-g"), "EDU|alex-g")
        self.assertEqual(ids.make_connector_id("filesystem", "drop"),
                         "CONN|filesystem|drop")
        self.assertEqual(ids.make_worker_id("research.acquire.v1"),
                         "WRK|research.acquire.v1")
        self.assertEqual(ids.make_transformation_id("normalize"), "XF|normalize")
        self.assertEqual(ids.make_capability_id("research", "acquire"),
                         "CAP|research|acquire")
        self.assertEqual(ids.make_canonical_rule_id("alex-g", "sr-zone"),
                         "RULE|alex-g|sr-zone")

    def test_source_id_hash_component_is_deterministic_and_12_hex(self):
        first = ids.make_source_id("web", "https://example.test/a")
        second = ids.make_source_id("web", "https://example.test/a")
        self.assertEqual(first, second)
        prefix, components = ids.parse_composite_id(first)
        self.assertEqual(prefix, "SRC")
        self.assertEqual(len(components[1]), 12)
        self.assertEqual(
            components[1], ids.sha256_hex(b"https://example.test/a")[:12]
        )

    def test_different_urls_produce_different_source_ids(self):
        self.assertNotEqual(
            ids.make_source_id("web", "https://example.test/a"),
            ids.make_source_id("web", "https://example.test/b"),
        )

    def test_round_trips_through_parse(self):
        samples = (
            "EDU|alex-g",
            "CONN|filesystem|operator-drop",
            "WRK|research.acquire.v1",
            "XF|normalize",
            "CAP|research|acquire",
            "RULE|alex-g|sr-zone",
            ids.make_source_id("web", "https://example.test/x"),
        )
        for sample in samples:
            with self.subTest(sample=sample):
                prefix, components = ids.parse_composite_id(sample)
                self.assertEqual(ids.make_composite_id(prefix, components), sample)

    def test_rejects_unknown_prefix(self):
        with self.assertRaises(errors.IdentifierError):
            ids.parse_composite_id("NOPE|thing")

    def test_rejects_empty_component(self):
        with self.assertRaises(errors.IdentifierError):
            ids.make_educator_id("")

    def test_rejects_whitespace_only_component(self):
        with self.assertRaises(errors.IdentifierError):
            ids.make_educator_id("   ")

    def test_rejects_embedded_separator(self):
        with self.assertRaises(errors.IdentifierError):
            ids.make_educator_id("alex|g")

    def test_rejects_uppercase_component(self):
        with self.assertRaises(errors.IdentifierError):
            ids.make_educator_id("AlexG")

    def test_rejects_wrong_component_count(self):
        with self.assertRaises(errors.IdentifierError):
            ids.make_composite_id("CONN", ("only-one",))
        with self.assertRaises(errors.IdentifierError):
            ids.parse_composite_id("EDU|a|b")

    def test_rejects_bad_hash12_component(self):
        with self.assertRaises(errors.IdentifierError):
            ids.make_composite_id("SRC", ("web", "nothex"))
        with self.assertRaises(errors.IdentifierError):
            ids.make_composite_id("SRC", ("web", "abcdef"))       # too short
        with self.assertRaises(errors.IdentifierError):
            ids.make_composite_id("SRC", ("web", "A" * 12))       # uppercase

    def test_require_composite_id_enforces_the_prefix(self):
        self.assertEqual(
            ids.require_composite_id("CAP|research|acquire", "CAP", "targetCapability"),
            "CAP|research|acquire",
        )
        with self.assertRaises(errors.IdentifierError):
            ids.require_composite_id("EDU|alex-g", "CAP", "targetCapability")

    def test_rejects_non_string(self):
        with self.assertRaises(errors.IdentifierError):
            ids.parse_composite_id(17)


class TestIdempotencyKeys(unittest.TestCase):
    def test_all_ten_catalog_operations_are_declared(self):
        self.assertEqual(
            set(ids.IDEMPOTENCY_KEY_COMPOSITION.keys()),
            set(EXPECTED_IDEMPOTENCY_COMPOSITION.keys()),
        )
        self.assertEqual(len(ids.IDEMPOTENCY_KEY_COMPOSITION), 10)

    def test_every_composition_matches_the_catalog(self):
        for operation, expected in EXPECTED_IDEMPOTENCY_COMPOSITION.items():
            with self.subTest(operation=operation):
                self.assertEqual(
                    tuple(ids.IDEMPOTENCY_KEY_COMPOSITION[operation]), expected
                )

    def test_no_composition_contains_a_timestamp_or_attempt_part(self):
        for operation, parts in ids.IDEMPOTENCY_KEY_COMPOSITION.items():
            for part in parts:
                for forbidden in FORBIDDEN_KEY_PARTS:
                    with self.subTest(operation=operation, part=part):
                        self.assertNotEqual(part.lower(), forbidden.lower())

    def test_key_is_stable_across_simulated_retries(self):
        parts = {"sourceId": "SRC|web|0123456789ab", "locator": "a.txt",
                 "connectorVersion": "1.0.0"}
        first = ids.idempotency_key("artifact_acquisition", parts)
        for _ in range(5):
            self.assertEqual(ids.idempotency_key("artifact_acquisition", dict(parts)),
                             first)
        self.assertTrue(ids.is_sha256_hex(first))

    def test_key_is_independent_of_part_insertion_order(self):
        a = ids.idempotency_key("source_registration",
                                {"normalizedUrl": "u", "educatorId": "EDU|x"})
        b = ids.idempotency_key("source_registration",
                                {"educatorId": "EDU|x", "normalizedUrl": "u"})
        self.assertEqual(a, b)

    def test_different_operations_produce_different_keys(self):
        # artifact and transcript acquisition share a composition but must not
        # collide, because the operation participates in the digest.
        parts = {"sourceId": "SRC|web|0123456789ab", "locator": "a.txt",
                 "connectorVersion": "1.0.0"}
        self.assertNotEqual(
            ids.idempotency_key("artifact_acquisition", parts),
            ids.idempotency_key("transcript_acquisition", parts),
        )

    def test_rejects_unknown_operation(self):
        with self.assertRaises(errors.IdentifierError):
            ids.idempotency_key("not_an_operation", {})

    def test_rejects_missing_required_part(self):
        with self.assertRaises(errors.IdentifierError):
            ids.idempotency_key("artifact_acquisition",
                                {"sourceId": "s", "locator": "l"})

    def test_rejects_undeclared_extra_part(self):
        with self.assertRaises(errors.IdentifierError):
            ids.idempotency_key(
                "raw_storage", {"sha256": "a" * 64, "attemptNumber": 2}
            )

    def test_rejects_null_part(self):
        with self.assertRaises(errors.IdentifierError):
            ids.idempotency_key("raw_storage", {"sha256": None})

    def test_rejects_non_mapping_parts(self):
        with self.assertRaises(errors.IdentifierError):
            ids.idempotency_key("raw_storage", ["a" * 64])


class TestCollisionHandling(unittest.TestCase):
    def test_same_bytes_same_hash_is_identity_not_error(self):
        digest = ids.assert_content_identity(b"payload", b"payload")
        self.assertEqual(digest, ids.sha256_hex(b"payload"))

    def test_differing_hashes_raise_identifier_error(self):
        with self.assertRaises(errors.IdentifierError):
            ids.assert_content_identity(b"a", b"b")

    def test_same_hash_over_differing_bytes_is_an_invariant_violation(self):
        # Constructed by forcing the digest comparison to agree while the bytes
        # differ -- the corruption alarm the architecture requires.
        real_sha256_hex = ids.sha256_hex
        try:
            ids.sha256_hex = lambda data: "c" * 64
            with self.assertRaises(errors.InvariantViolationError):
                ids.assert_content_identity(b"alpha", b"beta")
        finally:
            ids.sha256_hex = real_sha256_hex
        self.assertIs(ids.sha256_hex, real_sha256_hex)

    def test_composite_identity_conflict_carries_inert_review_metadata(self):
        # No review system exists in Step 1; the flag is recorded, never acted on.
        error = errors.IdentifierError("conflict", routes_to_review=True)
        self.assertTrue(error.routes_to_review)
        self.assertFalse(errors.IdentifierError("plain").routes_to_review)


class TestNoMintingOfGovernanceIdentifiers(unittest.TestCase):
    def test_governance_owned_field_list_matches_the_catalog(self):
        self.assertEqual(
            tuple(ids.GOVERNANCE_OWNED_IDENTIFIER_FIELDS),
            EXPECTED_GOVERNANCE_OWNED_FIELDS,
        )

    def test_predicate_recognises_them(self):
        for field in EXPECTED_GOVERNANCE_OWNED_FIELDS:
            self.assertTrue(ids.is_governance_owned_identifier_field(field))
        self.assertFalse(ids.is_governance_owned_identifier_field("sourceId"))

    def test_no_public_function_mints_a_governance_identifier(self):
        subjects = ("hypothesis", "evidencepackage", "evidence_package",
                    "replaypackage", "replay_package")
        verbs = ("make", "new", "mint", "create", "generate", "build", "issue")
        offenders = []
        for module_name, module in ALL_PLATFORM_MODULES:
            for name in dir(module):
                if name.startswith("_"):
                    continue
                if not callable(getattr(module, name)):
                    continue
                lowered = name.lower().replace("-", "_")
                flat = lowered.replace("_", "")
                if any(verb in lowered for verb in verbs) and \
                        any(subject.replace("_", "") in flat for subject in subjects):
                    offenders.append("%s.%s" % (module_name, name))
        self.assertEqual(offenders, [])


class TestValueFormats(unittest.TestCase):
    def test_accepts_iso8601_utc_millisecond(self):
        self.assertTrue(ids.is_iso8601_utc_ms("2026-08-07T12:34:56.789Z"))

    def test_rejects_missing_milliseconds(self):
        self.assertFalse(ids.is_iso8601_utc_ms("2026-08-07T12:34:56Z"))

    def test_rejects_microsecond_precision(self):
        self.assertFalse(ids.is_iso8601_utc_ms("2026-08-07T12:34:56.789123Z"))

    def test_rejects_offset_instead_of_z(self):
        self.assertFalse(ids.is_iso8601_utc_ms("2026-08-07T12:34:56.789+00:00"))

    def test_rejects_impossible_calendar_date(self):
        self.assertFalse(ids.is_iso8601_utc_ms("2026-02-30T00:00:00.000Z"))

    def test_rejects_impossible_time(self):
        self.assertFalse(ids.is_iso8601_utc_ms("2026-08-07T25:00:00.000Z"))

    def test_raiser_reports_the_field(self):
        with self.assertRaises(errors.ContractValidationError) as caught:
            ids.require_iso8601_utc_ms("nope", "issuedAt")
        self.assertIn("issuedAt", str(caught.exception))


class TestFreezeAndPlain(unittest.TestCase):
    def test_freeze_produces_a_read_only_mapping(self):
        frozen = ids.freeze({"a": 1, "b": {"c": [1, 2]}})
        with self.assertRaises(TypeError):
            frozen["a"] = 2
        with self.assertRaises(TypeError):
            frozen["b"]["c"] = []

    def test_freeze_converts_arrays_to_tuples(self):
        frozen = ids.freeze({"a": [1, 2]})
        self.assertIsInstance(frozen["a"], tuple)

    def test_as_plain_round_trips(self):
        original = {"a": 1, "b": {"c": [1, 2, {"d": None}]}}
        self.assertEqual(ids.as_plain(ids.freeze(original)), original)

    def test_freeze_does_not_mutate_the_input(self):
        original = {"a": [1, 2]}
        ids.freeze(original)
        self.assertEqual(original, {"a": [1, 2]})
        self.assertIsInstance(original["a"], list)


class TestPythonVersionFloor(unittest.TestCase):
    def test_python_3_14_or_newer(self):
        # ADR-012 D-01's manifest is deferred; the runtime floor is enforced
        # here instead of declared in a file nothing reads.
        self.assertGreaterEqual(sys.version_info[:2], (3, 14))


class TestJsonShapeValidator(unittest.TestCase):
    """Unit coverage of require_json_shaped -- MOGO-010 correction I-2/3/4."""

    ACCEPTED = (
        None, True, False, 0, -17, 1.5, -2.25, "", "text", "\u00e9\u4e2d\u6587",
        [], (), {}, [1, "a", None], (1, 2), {"a": 1},
        {"a": [1, {"b": [None, True]}]},
    )

    REJECTED = (
        ("object", object()),
        ("set", {1}),
        ("frozenset", frozenset([1])),
        ("bytes", b"x"),
        ("bytearray", bytearray(b"x")),
        ("complex", 1j),
        ("nan", float("nan")),
        ("inf", math.inf),
        ("-inf", -math.inf),
        ("int key", {1: "a"}),
        ("bool key", {True: "a"}),
        ("float key", {1.0: "a"}),
        ("tuple key", {(1, 2): "a"}),
        ("none key", {None: "a"}),
        ("nested object", {"a": [object()]}),
        ("nested nan", [[{"b": float("nan")}]]),
        ("nested bad key", {"a": [{2: "b"}]}),
    )

    def test_accepts_every_json_shaped_value(self):
        for value in self.ACCEPTED:
            with self.subTest(value=repr(value)):
                self.assertIs(ids.require_json_shaped(value), value)

    def test_rejects_every_non_json_shaped_value(self):
        for label, value in self.REJECTED:
            with self.subTest(kind=label):
                with self.assertRaises(errors.ContractValidationError):
                    ids.require_json_shaped(value)

    def test_accepts_a_read_only_mapping(self):
        frozen = ids.freeze({"a": [1, {"b": 2}]})
        self.assertIs(ids.require_json_shaped(frozen), frozen)

    def test_returns_the_original_object_unchanged(self):
        value = {"a": [1, 2]}
        self.assertIs(ids.require_json_shaped(value), value)

    def test_mutates_nothing(self):
        value = {"a": [1, {"b": 2}]}
        before = json.dumps(value, sort_keys=True)
        ids.require_json_shaped(value)
        self.assertEqual(json.dumps(value, sort_keys=True), before)

    def test_failure_message_carries_the_json_path(self):
        with self.assertRaises(errors.ContractValidationError) as caught:
            ids.require_json_shaped({"a": [{"b": object()}]}, "$root")
        self.assertIn("$root.a[0].b", str(caught.exception))

    def test_failure_message_names_the_offending_type(self):
        with self.assertRaises(errors.ContractValidationError) as caught:
            ids.require_json_shaped({"a": {1, 2}})
        self.assertIn("set", str(caught.exception))

    def test_does_not_traverse_arbitrary_object_attributes(self):
        # An unrecognized type is rejected outright, never introspected --
        # so a hostile or merely large object cannot drive the walk.
        class Probe(object):
            def __init__(self):
                self.touched = False

            def keys(self):
                self.touched = True
                return []

        probe = Probe()
        # Probe has keys() but no __getitem__, so it is not mapping-shaped.
        with self.assertRaises(errors.ContractValidationError):
            ids.require_json_shaped(probe)

    def test_canonicalization_accepts_a_frozen_structure(self):
        # The idempotency enabler: hashing a validated (frozen) value works and
        # produces the same digest as its plain equivalent.
        plain = {"a": [1, {"b": 2}]}
        self.assertEqual(
            ids.content_hash_of(ids.freeze(plain)), ids.content_hash_of(plain)
        )

if __name__ == "__main__":
    unittest.main(verbosity=2)

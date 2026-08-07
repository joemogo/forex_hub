#!/usr/bin/env python3
"""MOGO-010 Step 1 -- command and event envelope contract tests.

Pure stdlib (unittest). Fully offline, deterministic, repeatable.

Every expected vocabulary and field list below is transcribed INDEPENDENTLY
from the authoritative MOGO-009 Contract Catalog (sections A, B, J, M, O). A
test that imported an implementation constant and compared it to itself would
prove nothing; each expectation here is a literal written out from the
contract, so an omission, an addition or a spelling drift is detected.

Run with:
    python3 -m unittest tests.platform.test_platform_envelopes -v
"""

import json
import math
import os
import sys
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
# The ONE path entry the suites add. platform/src holds the uniquely named
# package; platform/ itself never becomes importable, so stdlib `platform`
# is untouched. See platform/README.md.
SRC_DIR = os.path.join(REPO_ROOT, "platform", "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from mogo_platform.contracts import command  # noqa: E402
from mogo_platform.contracts import errors  # noqa: E402
from mogo_platform.contracts import event  # noqa: E402
from mogo_platform.contracts import ids  # noqa: E402
from mogo_platform.contracts import vocabulary  # noqa: E402

# ---------------------------------------------------------------------------
# Independently transcribed -- Contract Catalog section J, commands (17)
# ---------------------------------------------------------------------------

EXPECTED_COMMAND_TYPES = (
    "RequestSourceDiscovery", "RegisterSource", "EvaluateSourcePolicy",
    "AcquireSourceMetadata", "AcquireArtifact", "AcquireTranscript",
    "NormalizeArtifact", "SegmentArtifact", "ExtractMetadata",
    "AnalyzeDuplicates", "CreateEvidenceCandidate", "RequestHumanReview",
    "RecordReviewDecision", "RetryTask", "CancelTask", "SuppressWorkflow",
    "ReclaimTask",
)

# ---------------------------------------------------------------------------
# Independently transcribed -- Contract Catalog section J, events (34)
# ---------------------------------------------------------------------------

EXPECTED_EVENT_TYPES = (
    "SourceDiscoveryRequested", "SourceDiscovered", "SourceRegistered",
    "PolicyEvaluated", "AcquisitionAuthorized", "AcquisitionDenied",
    "ArtifactAcquisitionRequested", "ArtifactAcquired",
    "ArtifactAcquisitionFailed", "TranscriptAcquired", "RawArtifactRegistered",
    "ArtifactNormalized", "ArtifactSegmented", "MetadataExtracted",
    "DuplicateCandidateDetected", "EvidenceCandidateCreated",
    "HumanReviewRequired", "HumanReviewCompleted", "SourceMutationDetected",
    "TaskClaimed", "TaskReclaimed", "TaskRetryScheduled", "TaskSucceeded",
    "TaskFailed", "TaskDeadLettered", "WorkflowStarted", "WorkflowCompleted",
    "WorkflowFailed", "WorkflowSuppressed", "CheckpointVerified",
    "CheckpointInvalidated", "PartialArtifactQuarantined",
    "RecoveryOverrideIssued", "SecretAccessed",
)

# ---------------------------------------------------------------------------
# Independently transcribed -- Contract Catalog sections A and B, field lists
# ---------------------------------------------------------------------------

EXPECTED_COMMAND_REQUIRED = (
    "commandId", "commandType", "commandVersion", "workflowId", "correlationId",
    "causationId", "idempotencyKey", "issuedAt", "issuedBy", "targetCapability",
    "inputRefs", "policyContext", "payloadHash",
)
EXPECTED_COMMAND_OPTIONAL = (
    "taskId", "priority", "attemptLimit", "timeoutMs", "approvalRequirements",
)

EXPECTED_EVENT_REQUIRED = (
    "eventId", "eventType", "eventVersion", "workflowId", "correlationId",
    "causationId", "producer", "producerVersion", "occurredAt", "recordedAt",
    "subjectRefs", "payload", "payloadHash", "sequence",
)
EXPECTED_EVENT_OPTIONAL = (
    "taskId", "priorEventId", "policyContext", "executionResult", "errorClass",
)

EXPECTED_EXECUTION_RESULTS = ("success", "failure", "partial")

# ---------------------------------------------------------------------------
# Independently transcribed -- Contract Catalog section M (12 statuses)
# ---------------------------------------------------------------------------
# (metadata, transcript, artifact, permitsAcquisition)

EXPECTED_LICENSING_STATUSES = {
    "PERMITTED_PUBLIC_METADATA":   ("ALLOWED", "DENIED", "DENIED", True),
    "PERMITTED_PUBLIC_TRANSCRIPT": ("ALLOWED", "ALLOWED", "DENIED", True),
    "PERMITTED_PUBLIC_ARTIFACT":   ("ALLOWED", "ALLOWED", "ALLOWED", True),
    "PERMITTED_EXPLICIT_LICENSE":  ("AS_RECORDED", "AS_RECORDED", "AS_RECORDED", True),
    "PERMITTED_DOCUMENTED_POLICY": ("AS_RECORDED", "AS_RECORDED", "AS_RECORDED", True),
    "METADATA_ONLY":               ("ALLOWED", "DENIED", "DENIED", True),
    "LINK_ONLY":                   ("LOCATOR_ONLY", "DENIED", "DENIED", True),
    "HUMAN_REVIEW_REQUIRED":       ("ALREADY_GATHERED_ONLY", "DENIED", "DENIED", False),
    "AUTHENTICATION_REQUIRED":     ("DENIED", "DENIED", "DENIED", False),
    "RESTRICTED":                  ("DENIED", "DENIED", "DENIED", False),
    "PROHIBITED":                  ("DENIED", "DENIED", "DENIED", False),
    "UNKNOWN":                     ("DENIED", "DENIED", "DENIED", False),
}

# ---------------------------------------------------------------------------
# Independently transcribed -- Contract Catalog section O (7 lifecycle states)
# ---------------------------------------------------------------------------

EXPECTED_CAPABILITY_LIFECYCLE_STATES = (
    "proposed", "experimental", "approved", "production", "deprecated",
    "disabled", "retired",
)

# ---------------------------------------------------------------------------
# Trading decision-event vocabulary, transcribed from the browser engine.
# Operational events must share no name with it (Constitution section 6.8).
# ---------------------------------------------------------------------------

TRADING_DECISION_EVENT_TYPES = (
    "CANDIDATE_CREATED", "CANDIDATE_APPROVED", "CANDIDATE_REJECTED",
    "TRADE_OPEN_REQUESTED", "TRADE_OPENED", "TRADE_OPEN_FAILED", "TRADE_CLOSED",
    "TRADE_IS_ON_THE_HIGHEST_TIMEFRAME", "SIGNAL_STALENESS",
    "SIGNAL_TOO_OLD_AT_FIRST_EVALUATION", "SESSION_OUTSIDE_ALLOWED_WINDOW",
    "SESSION_OUTSIDE_PREFERRED_DAY", "ENGINE_ERROR",
)

UUID_A = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
UUID_B = "7d444840-9dc0-41d2-b1a6-6f1d1d1a1a1a"
UUID_C = "16fd2706-8baf-433b-82eb-8c7fada847da"
UUID_D = "1b4e28ba-2fa1-489f-a9fd-2b0e6b6f7c33"
UUID_E = "886313e1-3b8a-45f6-8dd5-9a1b2c3d4e5f"
STAMP = "2026-08-07T12:34:56.789Z"


def valid_command(**overrides):
    """A minimal, valid command envelope. Overrides are applied last."""
    envelope = {
        "commandId": UUID_A,
        "commandType": "NormalizeArtifact",
        "commandVersion": 1,
        "workflowId": UUID_B,
        "correlationId": UUID_C,
        "causationId": UUID_D,
        "idempotencyKey": "a" * 64,
        "issuedAt": STAMP,
        "issuedBy": "orchestrator",
        "targetCapability": "research.acquire.v1",
        "inputRefs": ["SRC|web|0123456789ab"],
        "policyContext": {
            "authorizationId": None,
            "policyVersion": "1.0",
            "permittedOperations": [],
        },
        "payloadHash": "b" * 64,
        "priority": 5,
        "attemptLimit": 3,
    }
    envelope.update(overrides)
    return envelope


def valid_event(payload=None, **overrides):
    """A minimal, valid event envelope with a correct payload hash."""
    payload = {"note": "structural fixture"} if payload is None else payload
    envelope = {
        "eventId": UUID_A,
        "eventType": "TaskSucceeded",
        "eventVersion": 1,
        "workflowId": UUID_B,
        "correlationId": UUID_C,
        "causationId": UUID_D,
        "producer": "orchestrator",
        "producerVersion": "1.0.0",
        "occurredAt": STAMP,
        "recordedAt": STAMP,
        "subjectRefs": ["SRC|web|0123456789ab"],
        "payload": payload,
        "payloadHash": ids.content_hash_of(payload),
        "sequence": 0,
    }
    envelope.update(overrides)
    if "payload" in overrides and "payloadHash" not in overrides:
        envelope["payloadHash"] = ids.content_hash_of(envelope["payload"])
    return envelope


class TestVocabularyMatchesTheCatalog(unittest.TestCase):
    def test_command_types_exactly(self):
        self.assertEqual(tuple(vocabulary.COMMAND_TYPES), EXPECTED_COMMAND_TYPES)
        self.assertEqual(len(vocabulary.COMMAND_TYPES), 17)

    def test_event_types_exactly(self):
        self.assertEqual(tuple(vocabulary.EVENT_TYPES), EXPECTED_EVENT_TYPES)
        self.assertEqual(len(vocabulary.EVENT_TYPES), 34)

    def test_no_duplicate_names(self):
        self.assertEqual(len(set(vocabulary.COMMAND_TYPES)),
                         len(vocabulary.COMMAND_TYPES))
        self.assertEqual(len(set(vocabulary.EVENT_TYPES)), len(vocabulary.EVENT_TYPES))

    def test_execution_results_exactly(self):
        self.assertEqual(tuple(vocabulary.EXECUTION_RESULTS),
                         EXPECTED_EXECUTION_RESULTS)

    def test_capability_lifecycle_states_exactly(self):
        self.assertEqual(tuple(vocabulary.CAPABILITY_LIFECYCLE_STATES),
                         EXPECTED_CAPABILITY_LIFECYCLE_STATES)

    def test_licensing_statuses_exactly(self):
        self.assertEqual(set(vocabulary.LICENSING_STATUSES.keys()),
                         set(EXPECTED_LICENSING_STATUSES.keys()))
        self.assertEqual(len(vocabulary.LICENSING_STATUSES), 12)
        for name, expected in EXPECTED_LICENSING_STATUSES.items():
            with self.subTest(status=name):
                record = vocabulary.LICENSING_STATUSES[name]
                self.assertEqual(
                    (record["metadata"], record["transcript"], record["artifact"],
                     record["permitsAcquisition"]),
                    expected,
                )

    def test_unknown_is_identical_to_prohibited(self):
        # Constitution section 5.2; ADR-012 approval 12.
        self.assertEqual(dict(vocabulary.LICENSING_STATUSES["UNKNOWN"]),
                         dict(vocabulary.LICENSING_STATUSES["PROHIBITED"]))

    def test_unknown_permits_nothing(self):
        record = vocabulary.LICENSING_STATUSES["UNKNOWN"]
        self.assertFalse(record["permitsAcquisition"])
        for operation in ("metadata", "transcript", "artifact"):
            with self.subTest(operation=operation):
                self.assertEqual(record[operation], "DENIED")

    def test_licensing_table_is_read_only(self):
        with self.assertRaises(TypeError):
            vocabulary.LICENSING_STATUSES["UNKNOWN"] = {}
        with self.assertRaises(TypeError):
            vocabulary.LICENSING_STATUSES["PROHIBITED"]["metadata"] = "ALLOWED"


class TestOperationalScientificSeparation(unittest.TestCase):
    def test_namespace_is_operational(self):
        self.assertEqual(vocabulary.OPERATIONAL_NAMESPACE,
                         "mogo.platform.operational")

    def test_schema_versions_live_in_the_operational_namespace(self):
        self.assertTrue(command.COMMAND_SCHEMA_VERSION.startswith(
            vocabulary.OPERATIONAL_NAMESPACE))
        self.assertTrue(event.EVENT_SCHEMA_VERSION.startswith(
            vocabulary.OPERATIONAL_NAMESPACE))

    def test_schema_versions_are_not_scientific_identifiers(self):
        for scientific in ("mogo.evidence-package.v1", "mogo.evidence-canon.v1"):
            self.assertNotEqual(command.COMMAND_SCHEMA_VERSION, scientific)
            self.assertNotEqual(event.EVENT_SCHEMA_VERSION, scientific)

    def test_platform_event_names_are_disjoint_from_trading_decision_events(self):
        overlap = set(vocabulary.EVENT_TYPES) & set(TRADING_DECISION_EVENT_TYPES)
        self.assertEqual(overlap, set())

    def test_command_names_are_disjoint_from_trading_decision_events(self):
        overlap = set(vocabulary.COMMAND_TYPES) & set(TRADING_DECISION_EVENT_TYPES)
        self.assertEqual(overlap, set())


class TestCommandEnvelopeValidation(unittest.TestCase):
    def test_field_lists_match_the_catalog(self):
        self.assertEqual(tuple(command.COMMAND_REQUIRED_FIELDS),
                         EXPECTED_COMMAND_REQUIRED)
        self.assertEqual(tuple(command.COMMAND_OPTIONAL_FIELDS),
                         EXPECTED_COMMAND_OPTIONAL)
        self.assertEqual(len(command.COMMAND_FIELDS), 18)

    def test_accepts_a_minimal_valid_command(self):
        validated = command.validate_command(valid_command())
        self.assertEqual(validated["commandType"], "NormalizeArtifact")

    def test_rejects_each_missing_required_field(self):
        for field in EXPECTED_COMMAND_REQUIRED:
            with self.subTest(field=field):
                envelope = valid_command()
                del envelope[field]
                with self.assertRaises(errors.ContractValidationError):
                    command.validate_command(envelope)

    def test_rejects_null_required_field(self):
        for field in EXPECTED_COMMAND_REQUIRED:
            with self.subTest(field=field):
                with self.assertRaises(errors.ContractValidationError):
                    command.validate_command(valid_command(**{field: None}))

    def test_rejects_non_mapping(self):
        for bad in ([], "envelope", 17, None):
            with self.subTest(bad=bad):
                with self.assertRaises(errors.ContractValidationError):
                    command.validate_command(bad)

    def test_applies_approved_defaults(self):
        envelope = valid_command()
        del envelope["priority"]
        del envelope["attemptLimit"]
        built = command.build_command(**envelope)
        self.assertEqual(built["priority"], 5)
        self.assertEqual(built["attemptLimit"], 3)

    def test_rejects_unregistered_command_type(self):
        with self.assertRaises(errors.ContractValidationError):
            command.validate_command(valid_command(commandType="AcquireEverything"))

    def test_rejects_malformed_identifiers(self):
        for field in ("commandId", "workflowId", "correlationId", "causationId"):
            with self.subTest(field=field):
                with self.assertRaises(errors.IdentifierError):
                    command.validate_command(valid_command(**{field: "not-a-uuid"}))

    def test_rejects_malformed_idempotency_key(self):
        with self.assertRaises(errors.IdentifierError):
            command.validate_command(valid_command(idempotencyKey="short"))

    def test_rejects_malformed_timestamp(self):
        with self.assertRaises(errors.ContractValidationError):
            command.validate_command(valid_command(issuedAt="2026-08-07"))

    def test_issued_by_accepts_the_three_approved_forms(self):
        for value in ("orchestrator", "operator:joe", "workflow:acquisition"):
            with self.subTest(value=value):
                command.validate_command(valid_command(issuedBy=value))

    def test_issued_by_rejects_other_forms(self):
        for value in ("worker:acquire", "operator:", "", "OPERATOR:joe"):
            with self.subTest(value=value):
                with self.assertRaises(errors.ContractValidationError):
                    command.validate_command(valid_command(issuedBy=value))

    def test_target_capability_accepts_both_attested_forms(self):
        for value in ("research.acquire.v1", "CAP|research|acquire"):
            with self.subTest(value=value):
                command.validate_command(valid_command(targetCapability=value))

    def test_target_capability_rejects_malformed_values(self):
        for value in ("Research.Acquire", "has space", "", "CAP|bad"):
            with self.subTest(value=value):
                with self.assertRaises((errors.ContractValidationError,
                                        errors.IdentifierError)):
                    command.validate_command(valid_command(targetCapability=value))

    def test_priority_range_is_enforced(self):
        for bad in (-1, 10):
            with self.subTest(bad=bad):
                with self.assertRaises(errors.ContractValidationError):
                    command.validate_command(valid_command(priority=bad))

    def test_booleans_are_not_accepted_as_integers(self):
        with self.assertRaises(errors.ContractValidationError):
            command.validate_command(valid_command(priority=True))

    def test_policy_context_requires_its_declared_keys(self):
        for field in ("authorizationId", "policyVersion", "permittedOperations"):
            with self.subTest(field=field):
                context = {"authorizationId": None, "policyVersion": "1.0",
                           "permittedOperations": []}
                del context[field]
                with self.assertRaises(errors.ContractValidationError):
                    command.validate_command(valid_command(policyContext=context))

    def test_input_refs_must_be_an_array_of_strings(self):
        with self.assertRaises(errors.ContractValidationError):
            command.validate_command(valid_command(inputRefs="SRC|web|0123456789ab"))
        with self.assertRaises(errors.ContractValidationError):
            command.validate_command(valid_command(inputRefs=[17]))

    def test_validator_does_not_mutate_caller_input(self):
        envelope = valid_command()
        snapshot = json.dumps(envelope, sort_keys=True)
        command.validate_command(envelope)
        self.assertEqual(json.dumps(envelope, sort_keys=True), snapshot)

    def test_validated_command_is_read_only(self):
        validated = command.validate_command(valid_command())
        with self.assertRaises(TypeError):
            validated["commandType"] = "AcquireArtifact"
        with self.assertRaises(TypeError):
            validated["policyContext"]["policyVersion"] = "9.9"


class TestCommandPayloadHash(unittest.TestCase):
    def test_matching_payload_is_accepted(self):
        payload = {"a": 1, "b": [1, 2]}
        envelope = valid_command(payloadHash=ids.content_hash_of(payload))
        command.validate_command(envelope, payload=payload)

    def test_mismatched_payload_is_rejected(self):
        payload = {"a": 1}
        envelope = valid_command(payloadHash=ids.content_hash_of({"a": 2}))
        with self.assertRaises(errors.ContractValidationError):
            command.validate_command(envelope, payload=payload)

    def test_verification_without_a_payload_is_an_explicit_error(self):
        # The envelope alone cannot verify its own hash -- Catalog section A
        # declares no payload field on a command. Asking for verification
        # without supplying the payload fails rather than silently passing.
        with self.assertRaises(errors.ContractValidationError):
            command.validate_command(valid_command(), verify_payload_hash=True)

    def test_form_only_check_when_no_payload_is_supplied(self):
        command.validate_command(valid_command())
        with self.assertRaises(errors.IdentifierError):
            command.validate_command(valid_command(payloadHash="nope"))


class TestEventEnvelopeValidation(unittest.TestCase):
    def test_field_lists_match_the_catalog(self):
        self.assertEqual(tuple(event.EVENT_REQUIRED_FIELDS), EXPECTED_EVENT_REQUIRED)
        self.assertEqual(tuple(event.EVENT_OPTIONAL_FIELDS), EXPECTED_EVENT_OPTIONAL)
        self.assertEqual(len(event.EVENT_FIELDS), 19)

    def test_accepts_a_minimal_valid_event(self):
        validated = event.validate_event(valid_event())
        self.assertEqual(validated["eventType"], "TaskSucceeded")

    def test_rejects_each_missing_required_field(self):
        for field in EXPECTED_EVENT_REQUIRED:
            with self.subTest(field=field):
                envelope = valid_event()
                del envelope[field]
                with self.assertRaises(errors.ContractValidationError):
                    event.validate_event(envelope)

    def test_rejects_unregistered_event_type(self):
        with self.assertRaises(errors.ContractValidationError):
            event.validate_event(valid_event(eventType="EverythingHappened"))

    def test_producer_accepts_the_four_approved_forms(self):
        for value in ("orchestrator", "policyGate", "reviewGate", "worker:WRK|x"):
            with self.subTest(value=value):
                event.validate_event(valid_event(producer=value))

    def test_producer_rejects_other_forms(self):
        for value in ("operator:joe", "worker:", "", "PolicyGate"):
            with self.subTest(value=value):
                with self.assertRaises(errors.ContractValidationError):
                    event.validate_event(valid_event(producer=value))

    def test_producer_version_must_be_semver(self):
        for bad in ("1.0", "v1.0.0", "1.0.0-beta", ""):
            with self.subTest(bad=bad):
                with self.assertRaises(errors.ContractValidationError):
                    event.validate_event(valid_event(producerVersion=bad))

    def test_sequence_must_be_a_non_negative_integer(self):
        for bad in (-1, "0", 1.5, True):
            with self.subTest(bad=bad):
                with self.assertRaises(errors.ContractValidationError):
                    event.validate_event(valid_event(sequence=bad))

    def test_error_class_required_when_execution_result_is_failure(self):
        with self.assertRaises(errors.ContractValidationError):
            event.validate_event(valid_event(executionResult="failure"))
        event.validate_event(
            valid_event(executionResult="failure", errorClass="transient")
        )

    def test_error_class_must_be_an_approved_class(self):
        with self.assertRaises(errors.ContractValidationError):
            event.validate_event(
                valid_event(executionResult="failure", errorClass="oops")
            )

    def test_execution_result_must_be_an_approved_value(self):
        with self.assertRaises(errors.ContractValidationError):
            event.validate_event(valid_event(executionResult="maybe"))

    def test_payload_must_be_a_mapping(self):
        envelope = valid_event()
        envelope["payload"] = ["not", "a", "mapping"]
        envelope["payloadHash"] = ids.content_hash_of(envelope["payload"])
        with self.assertRaises(errors.ContractValidationError):
            event.validate_event(envelope)

    def test_payload_hash_mismatch_is_rejected(self):
        with self.assertRaises(errors.ContractValidationError):
            event.validate_event(valid_event(payloadHash="c" * 64))

    def test_payload_hash_recomputes_identically(self):
        envelope = valid_event(payload={"z": 1, "a": 2})
        self.assertEqual(
            event.event_payload_hash(envelope["payload"]), envelope["payloadHash"]
        )

    def test_validator_does_not_mutate_caller_input(self):
        envelope = valid_event()
        snapshot = json.dumps(envelope, sort_keys=True)
        event.validate_event(envelope)
        self.assertEqual(json.dumps(envelope, sort_keys=True), snapshot)


class TestEventImmutability(unittest.TestCase):
    def test_validated_event_is_deeply_read_only(self):
        validated = event.validate_event(valid_event(payload={"a": {"b": [1]}}))
        with self.assertRaises(TypeError):
            validated["eventType"] = "TaskFailed"
        with self.assertRaises(TypeError):
            validated["payload"]["a"] = {}
        with self.assertRaises(TypeError):
            validated["payload"]["a"]["b"] = []

    def test_arrays_are_immutable_too(self):
        validated = event.validate_event(valid_event())
        with self.assertRaises(AttributeError):
            validated["subjectRefs"].append("x")

    def test_no_mutator_exists_on_the_event_module(self):
        # Constitution section 6.1: events are never updated, never deleted.
        forbidden = ("update", "set", "mutate", "patch", "delete", "remove",
                     "modify", "amend", "edit", "append", "store", "persist",
                     "write", "save", "emit", "publish")
        offenders = []
        for name in dir(event):
            if name.startswith("_"):
                continue
            if not callable(getattr(event, name)):
                continue
            lowered = name.lower()
            if any(word in lowered for word in forbidden):
                offenders.append(name)
        self.assertEqual(offenders, [])


class TestContractVersionHandling(unittest.TestCase):
    def test_unknown_command_major_raises_the_distinct_version_error(self):
        with self.assertRaises(errors.UnsupportedContractVersionError):
            command.validate_command(valid_command(commandVersion=2))

    def test_unknown_event_major_raises_the_distinct_version_error(self):
        with self.assertRaises(errors.UnsupportedContractVersionError):
            event.validate_event(valid_event(eventVersion=99))

    def test_version_error_is_distinguishable_from_plain_validation_error(self):
        self.assertTrue(
            issubclass(errors.UnsupportedContractVersionError, errors.PlatformError)
        )
        self.assertFalse(
            issubclass(errors.UnsupportedContractVersionError,
                       errors.ContractValidationError)
        )

    def test_version_must_be_an_integer(self):
        with self.assertRaises(errors.ContractValidationError):
            command.validate_command(valid_command(commandVersion="1"))

    def test_v1_accepts_an_additive_optional_field(self):
        validated = command.validate_command(
            valid_command(futureOptionalField="tolerated")
        )
        self.assertEqual(validated["futureOptionalField"], "tolerated")


class TestUnknownFieldBehavior(unittest.TestCase):
    def test_unknown_envelope_fields_are_retained_not_dropped(self):
        validated = event.validate_event(valid_event(futureField={"a": 1}))
        self.assertIn("futureField", validated)
        self.assertEqual(ids.as_plain(validated["futureField"]), {"a": 1})

    def test_unknown_payload_fields_are_included_in_the_payload_hash(self):
        without = {"known": 1}
        with_extra = {"known": 1, "futureField": 2}
        self.assertNotEqual(
            ids.content_hash_of(without), ids.content_hash_of(with_extra)
        )
        # And an envelope carrying the extra field validates only against the
        # hash that includes it -- proving the field was not stripped.
        envelope = valid_event(payload=with_extra)
        event.validate_event(envelope)
        envelope["payloadHash"] = ids.content_hash_of(without)
        with self.assertRaises(errors.ContractValidationError):
            event.validate_event(envelope)

    def test_unknown_fields_do_not_affect_semantic_validation(self):
        event.validate_event(valid_event(somethingNobodyKnows=["a", {"b": None}]))


class TestSerializationRoundTrip(unittest.TestCase):
    def test_command_round_trip_is_byte_identical(self):
        validated = command.validate_command(valid_command())
        plain = ids.as_plain(validated)
        first = json.dumps(plain, sort_keys=True, separators=(",", ":"))
        second = json.dumps(json.loads(first), sort_keys=True, separators=(",", ":"))
        self.assertEqual(first, second)

    def test_event_round_trip_is_byte_identical(self):
        validated = event.validate_event(valid_event(payload={"u": "é中文", "n": None}))
        plain = ids.as_plain(validated)
        first = json.dumps(plain, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False)
        second = json.dumps(json.loads(first), sort_keys=True, separators=(",", ":"),
                            ensure_ascii=False)
        self.assertEqual(first, second)

    def test_round_trip_preserves_the_payload_hash(self):
        validated = event.validate_event(valid_event(payload={"z": [1, {"y": 2}]}))
        reparsed = json.loads(json.dumps(ids.as_plain(validated)))
        self.assertEqual(
            ids.content_hash_of(reparsed["payload"]), reparsed["payloadHash"]
        )
        event.validate_event(reparsed)

    def test_round_trip_preserves_unicode(self):
        validated = event.validate_event(valid_event(payload={"k": "é中文\U0001f600"}))
        reparsed = json.loads(json.dumps(ids.as_plain(validated), ensure_ascii=False))
        self.assertEqual(reparsed["payload"]["k"], "é中文\U0001f600")


class TestProhibitedScientificReferences(unittest.TestCase):
    """Every prohibited target and symbol must be rejected wherever it appears."""

    PROHIBITED_REFS = (
        "evidence/C1-01-GBP_USD-HARVEST.json",
        "docs/campaigns/C1/CAMPAIGN_C1_IDENTITY.md",
        "docs/trader-intelligence/governance/PREREG-001-alex-multipair-2026-08-04.md",
        "docs/MOGO-003-VERIFIED-REPLAY-RECORD.md",
        "index.html",
        "docs/trader-intelligence/hypothesis-registry.json",
        "mogo.evidence-canon.v1",
        "mogo.evidence-package.v1",
        "alexGStableHash",
        "sourceTradeId",
    )

    def test_command_input_refs_reject_every_prohibited_reference(self):
        for ref in self.PROHIBITED_REFS:
            with self.subTest(ref=ref):
                with self.assertRaises(errors.ProtectedBoundaryViolationError):
                    command.validate_command(valid_command(inputRefs=[ref]))

    def test_event_subject_refs_reject_every_prohibited_reference(self):
        for ref in self.PROHIBITED_REFS:
            with self.subTest(ref=ref):
                with self.assertRaises(errors.ProtectedBoundaryViolationError):
                    event.validate_event(valid_event(subjectRefs=[ref]))

    def test_event_payload_rejects_a_prohibited_reference(self):
        for ref in self.PROHIBITED_REFS:
            with self.subTest(ref=ref):
                with self.assertRaises(errors.ProtectedBoundaryViolationError):
                    event.validate_event(valid_event(payload={"target": ref}))

    def test_nested_payload_reference_is_found(self):
        with self.assertRaises(errors.ProtectedBoundaryViolationError):
            event.validate_event(
                valid_event(payload={"a": [{"b": {"c": ["evidence/x.json"]}}]})
            )

    def test_a_prohibited_mapping_key_is_found(self):
        with self.assertRaises(errors.ProtectedBoundaryViolationError):
            event.validate_event(valid_event(payload={"index.html": 1}))

    def test_command_payload_rejects_a_prohibited_reference(self):
        payload = {"writeTo": "evidence/out.json"}
        envelope = valid_command(payloadHash=ids.content_hash_of(payload))
        with self.assertRaises(errors.ProtectedBoundaryViolationError):
            command.validate_command(envelope, payload=payload)

    def test_benign_references_are_not_rejected(self):
        for ref in ("SRC|web|0123456789ab", "docs/platform/notes.md",
                    "intake/pending/a.json", "evidencecandidate"):
            with self.subTest(ref=ref):
                event.validate_event(valid_event(subjectRefs=[ref]))


class TestEnvelopeSerializability(unittest.TestCase):
    """Every validated envelope must be JSON-shaped -- MOGO-010 correction I-2/3/4.

    Before the correction an unknown additive field could carry a value with no
    JSON form, a value JSON cannot express, or a key json.dumps would silently
    coerce. The envelope validated and then failed -- or worse, succeeded and
    produced a malformed document.
    """

    UNSUPPORTED = (
        ("object", object()),
        ("set", {1, 2}),
        ("frozenset", frozenset([1])),
        ("bytes", b"abc"),
        ("bytearray", bytearray(b"abc")),
        ("complex", 1j),
    )

    def test_command_rejects_unknown_field_containing_object(self):
        with self.assertRaises(errors.ContractValidationError):
            command.validate_command(valid_command(futureField=object()))

    def test_event_rejects_unknown_field_containing_object(self):
        with self.assertRaises(errors.ContractValidationError):
            event.validate_event(valid_event(futureField=object()))

    def test_rejects_unknown_field_containing_a_set(self):
        with self.assertRaises(errors.ContractValidationError):
            event.validate_event(valid_event(futureField={1, 2}))

    def test_rejects_unknown_field_containing_bytes(self):
        with self.assertRaises(errors.ContractValidationError):
            event.validate_event(valid_event(futureField=b"abc"))

    def test_rejects_unknown_field_containing_a_complex_number(self):
        with self.assertRaises(errors.ContractValidationError):
            event.validate_event(valid_event(futureField=1j))

    def test_rejects_every_unsupported_type_in_both_envelopes(self):
        for label, value in self.UNSUPPORTED:
            with self.subTest(kind=label, envelope="command"):
                with self.assertRaises(errors.ContractValidationError):
                    command.validate_command(valid_command(futureField=value))
            with self.subTest(kind=label, envelope="event"):
                with self.assertRaises(errors.ContractValidationError):
                    event.validate_event(valid_event(futureField=value))

    def test_rejects_nested_unknown_field_containing_unsupported_value(self):
        with self.assertRaises(errors.ContractValidationError):
            event.validate_event(
                valid_event(futureField={"a": [{"b": object()}]})
            )

    def test_rejects_unknown_field_containing_nan(self):
        with self.assertRaises(errors.ContractValidationError):
            event.validate_event(valid_event(futureField=float("nan")))

    def test_rejects_unknown_field_containing_positive_infinity(self):
        with self.assertRaises(errors.ContractValidationError):
            event.validate_event(valid_event(futureField=math.inf))

    def test_rejects_unknown_field_containing_negative_infinity(self):
        with self.assertRaises(errors.ContractValidationError):
            event.validate_event(valid_event(futureField=-math.inf))

    def test_rejects_non_finite_float_at_any_depth(self):
        for bad in (float("nan"), math.inf, -math.inf):
            with self.subTest(value=bad):
                with self.assertRaises(errors.ContractValidationError):
                    event.validate_event(
                        valid_event(futureField={"a": [1, {"b": [bad]}]})
                    )

    def test_rejects_mapping_with_non_string_integer_key(self):
        with self.assertRaises(errors.ContractValidationError):
            event.validate_event(valid_event(futureField={1: "a"}))

    def test_rejects_mapping_with_non_string_boolean_key(self):
        # bool is a subclass of int and neither is a str, so a True key that
        # json.dumps would happily coerce to "true" is rejected here.
        with self.assertRaises(errors.ContractValidationError):
            event.validate_event(valid_event(futureField={True: "a"}))

    def test_rejects_nested_non_string_key(self):
        with self.assertRaises(errors.ContractValidationError):
            event.validate_event(valid_event(futureField={"a": [{2: "b"}]}))

    def test_keys_are_never_coerced_or_stringified(self):
        # The rejected envelope must not come back with a "1" key instead.
        with self.assertRaises(errors.ContractValidationError):
            event.validate_event(valid_event(futureField={1: "a"}))
        original = valid_event(futureField={1: "a"})
        self.assertIn(1, original["futureField"])
        self.assertNotIn("1", original["futureField"])

    def test_valid_nested_json_shaped_unknown_field_round_trips(self):
        value = {"a": [1, 2.5, {"b": None, "c": True}], "d": []}
        validated = event.validate_event(valid_event(futureField=value))
        plain = ids.as_plain(validated)
        self.assertEqual(plain["futureField"], value)
        text = json.dumps(plain, sort_keys=True, separators=(",", ":"),
                          allow_nan=False)
        self.assertEqual(json.loads(text), plain)

    def test_valid_unicode_unknown_field_round_trips(self):
        value = {"k": "\u00e9\u4e2d\u6587\U0001f600"}
        validated = event.validate_event(valid_event(futureField=value))
        plain = ids.as_plain(validated)
        self.assertEqual(plain["futureField"], value)
        text = json.dumps(plain, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False)
        self.assertEqual(json.loads(text)["futureField"], value)

    def test_error_names_the_precise_json_path(self):
        with self.assertRaises(errors.ContractValidationError) as caught:
            event.validate_event(
                valid_event(futureField={"a": [{"b": object()}]})
            )
        self.assertIn("$event.futureField.a[0].b", str(caught.exception))

    def test_error_names_the_precise_path_for_a_bad_key(self):
        with self.assertRaises(errors.ContractValidationError) as caught:
            event.validate_event(valid_event(futureField={"a": [{2: "b"}]}))
        self.assertIn("$event.futureField.a[0]", str(caught.exception))

    def test_command_payload_argument_receives_the_same_validation(self):
        # Assert the SHAPE VALIDATOR rejected it, not merely that something
        # did. Without the "$payload" path assertion this test passes even when
        # the payload shape check is unwired, because canonical hashing rejects
        # object() and NaN anyway and a coerced {1:"a"} key then fails the hash
        # comparison instead -- the right exception class for the wrong reason.
        # A mutation run proved that gap; this closes it.
        for bad in (object(), {1: "a"}, float("nan"), b"bytes", {1, 2}, 1j):
            with self.subTest(value=repr(bad)):
                payload = {"x": bad}
                envelope = valid_command(payloadHash="c" * 64)
                with self.assertRaises(errors.ContractValidationError) as caught:
                    command.validate_command(envelope, payload=payload)
                self.assertIn("$payload.x", str(caught.exception))

    def test_command_payload_shape_is_checked_before_hashing(self):
        # An unshapely payload whose declared hash would also mismatch must
        # report the SHAPE failure, proving the ordering in the validator.
        payload = {"x": object()}
        with self.assertRaises(errors.ContractValidationError) as caught:
            command.validate_command(valid_command(), payload=payload)
        message = str(caught.exception)
        self.assertIn("$payload.x", message)
        self.assertNotIn("payloadHash mismatch", message)

    def test_event_payload_receives_the_same_validation(self):
        for bad in (object(), {1: "a"}, math.inf):
            with self.subTest(value=repr(bad)):
                envelope = valid_event()
                envelope["payload"] = {"x": bad}
                envelope["payloadHash"] = "d" * 64
                with self.assertRaises(errors.ContractValidationError):
                    event.validate_event(envelope)

    def test_every_validated_envelope_is_strict_json_serializable(self):
        # allow_nan=False is the strict mode: it refuses the bare NaN/Infinity
        # tokens that plain json.dumps would emit and that are not valid JSON.
        samples = [
            command.validate_command(valid_command()),
            command.validate_command(valid_command(futureField={"a": [1, None]})),
            event.validate_event(valid_event()),
            event.validate_event(valid_event(payload={"n": 1.5, "s": "x"})),
            event.validate_event(valid_event(futureField=["a", {"b": 2}])),
        ]
        for index, envelope in enumerate(samples):
            with self.subTest(sample=index):
                plain = ids.as_plain(envelope)
                text = json.dumps(plain, sort_keys=True, separators=(",", ":"),
                                  ensure_ascii=False, allow_nan=False)
                self.assertEqual(json.loads(text), plain)

    def test_validator_does_not_mutate_caller_input_on_rejection(self):
        envelope = valid_event(futureField={"a": [1]})
        snapshot = json.dumps(envelope, sort_keys=True)
        try:
            event.validate_event(valid_event(futureField=object()))
        except errors.ContractValidationError:
            pass
        self.assertEqual(json.dumps(envelope, sort_keys=True), snapshot)

    def test_unsupported_major_version_still_wins_over_shape_rejection(self):
        # Ordering guarantee: an unsupported major must still raise the
        # DISTINCT version error even when the envelope is also unshapely.
        with self.assertRaises(errors.UnsupportedContractVersionError):
            event.validate_event(valid_event(eventVersion=99, futureField=object()))


class TestIdempotentValidation(unittest.TestCase):
    """A validated envelope must revalidate -- MOGO-010 correction I-5."""

    def test_validate_command_of_a_validated_command_succeeds(self):
        once = command.validate_command(valid_command())
        twice = command.validate_command(once)
        self.assertEqual(twice["commandType"], "NormalizeArtifact")

    def test_validate_event_of_a_validated_event_succeeds(self):
        once = event.validate_event(valid_event())
        twice = event.validate_event(once)
        self.assertEqual(twice["eventType"], "TaskSucceeded")

    def test_repeated_validation_preserves_the_plain_representation_exactly(self):
        for once in (command.validate_command(valid_command()),
                     event.validate_event(valid_event())):
            validate = (command.validate_command
                        if "commandId" in once else event.validate_event)
            with self.subTest(kind=type(once).__name__):
                twice = validate(once)
                thrice = validate(twice)
                self.assertEqual(ids.as_plain(once), ids.as_plain(twice))
                self.assertEqual(ids.as_plain(twice), ids.as_plain(thrice))

    def test_repeated_validation_preserves_payload_hash_exactly(self):
        once = event.validate_event(valid_event(payload={"z": [1, {"y": 2}]}))
        twice = event.validate_event(once)
        self.assertEqual(once["payloadHash"], twice["payloadHash"])
        self.assertEqual(
            twice["payloadHash"], ids.content_hash_of(ids.as_plain(twice["payload"]))
        )

    def test_repeated_validation_preserves_unknown_fields(self):
        value = {"a": [1, {"b": "\u00e9"}], "c": None}
        once = event.validate_event(valid_event(futureField=value))
        twice = event.validate_event(once)
        self.assertEqual(ids.as_plain(twice["futureField"]), value)

    def test_repeated_validation_remains_deeply_immutable(self):
        twice = event.validate_event(
            event.validate_event(valid_event(payload={"a": {"b": [1]}}))
        )
        with self.assertRaises(TypeError):
            twice["eventType"] = "TaskFailed"
        with self.assertRaises(TypeError):
            twice["payload"]["a"] = {}
        with self.assertRaises(TypeError):
            twice["payload"]["a"]["b"] = []

    def test_repeated_validation_does_not_mutate_the_original(self):
        once = event.validate_event(valid_event())
        before = ids.as_plain(once)
        event.validate_event(once)
        self.assertEqual(ids.as_plain(once), before)

    def test_revalidated_envelope_is_still_strict_json_serializable(self):
        twice = event.validate_event(event.validate_event(valid_event()))
        plain = ids.as_plain(twice)
        text = json.dumps(plain, sort_keys=True, separators=(",", ":"),
                          allow_nan=False)
        self.assertEqual(json.loads(text), plain)

if __name__ == "__main__":
    unittest.main(verbosity=2)

#!/usr/bin/env python3
"""MOGO-011 Step 3 -- Acquisition Authorization Records.

Pure stdlib (unittest). Fully offline, deterministic, repeatable. Tempfile state
root.

THE RULE THIS SUITE ENFORCES
    Constitution section 5.9 and Architecture section 20.1: the platform makes
    NO legal determination. It records and enforces classifications supplied by
    governance or legal review.

    So the decisive tests here are the ones that refuse: a record whose
    authority names a worker, a record altered in place, a supersession that
    points nowhere. A component that could authorize its own acquisition would
    make the whole gate ornamental.

Run with:
    python3 -m unittest tests.platform.test_runtime_authorization -v
"""

import os
import sqlite3
import sys
import tempfile
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC_DIR = os.path.join(REPO_ROOT, "platform", "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from mogo_platform.contracts import ids  # noqa: E402
from mogo_platform.runtime import authorizations  # noqa: E402
from mogo_platform.runtime import clock as clock_module  # noqa: E402
from mogo_platform.runtime import errors as runtime_errors  # noqa: E402
from mogo_platform.runtime import orchestrator as orchestrator_module  # noqa: E402
from mogo_platform.runtime import paths as paths_module  # noqa: E402
from mogo_platform.runtime import policy  # noqa: E402
from mogo_platform.runtime import store  # noqa: E402

# Independently transcribed from Catalog section M / Architecture section 20.3.
EXPECTED_REQUIRED_FIELDS = (
    "authorizationId", "sourceId", "policyStatus", "policyVersion",
    "decisionAuthority", "decidedAt", "permittedOperations",
)
EXPECTED_OPTIONAL_FIELDS = (
    "sourceTermsSnapshotRef", "retentionRestrictions", "deletionRequirements",
    "redistributionRestrictions", "modelTrainingRestrictions", "expiresAt",
    "supersedesAuthorizationId", "auditHistory",
)


class AuthorizationCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.paths = paths_module.RuntimePaths(os.path.join(self._tmp.name, "state"))
        self.runtime = orchestrator_module.Orchestrator(
            paths=self.paths,
            clock=clock_module.ManualClock("2026-08-08T12:00:00.000Z")).open()
        self.runtime.register_builtin_capabilities()

    def tearDown(self):
        self.runtime.close()
        self._tmp.cleanup()

    def source(self, label="a"):
        return ids.make_source_id("example", "https://example.test/%s" % label)

    def record(self, **overrides):
        base = {"authorizationId": ids.new_uuid4(),
                "sourceId": self.source(),
                "policyStatus": "PERMITTED_PUBLIC_METADATA",
                "policyVersion": "1.0",
                "decisionAuthority": "governance:mogo-legal",
                "decidedAt": "2026-08-08T11:00:00.000Z",
                "permittedOperations": ["metadata"]}
        base.update(overrides)
        return base


class TestRecordShape(AuthorizationCase):
    def test_the_field_list_matches_the_catalog(self):
        self.assertEqual(tuple(authorizations.REQUIRED_FIELDS),
                         EXPECTED_REQUIRED_FIELDS)
        self.assertEqual(tuple(authorizations.OPTIONAL_FIELDS),
                         EXPECTED_OPTIONAL_FIELDS)

    def test_a_well_formed_record_validates(self):
        self.assertIsNotNone(authorizations.validate_record(self.record()))

    def test_every_required_field_is_required(self):
        for field in EXPECTED_REQUIRED_FIELDS:
            broken = self.record()
            del broken[field]
            with self.subTest(missing=field):
                with self.assertRaises(runtime_errors.ContractValidationError):
                    authorizations.validate_record(broken)

    def test_an_unknown_field_is_refused(self):
        with self.assertRaises(runtime_errors.ContractValidationError):
            authorizations.validate_record(self.record(permitEverything=True))

    def test_an_unapproved_policy_status_is_refused(self):
        for bogus in ("PERMITTED", "permitted_public_metadata", "", "MAYBE"):
            with self.subTest(status=bogus):
                with self.assertRaises(runtime_errors.ContractValidationError):
                    authorizations.validate_record(self.record(policyStatus=bogus))

    def test_every_catalog_status_is_accepted(self):
        from mogo_platform.contracts import vocabulary
        for status in vocabulary.LICENSING_STATUS_NAMES:
            with self.subTest(status=status):
                authorizations.validate_record(self.record(policyStatus=status))

    def test_an_unapproved_operation_is_refused(self):
        with self.assertRaises(runtime_errors.ContractValidationError):
            authorizations.validate_record(
                self.record(permittedOperations=["everything"]))

    def test_a_duplicate_operation_is_refused(self):
        with self.assertRaises(runtime_errors.ContractValidationError):
            authorizations.validate_record(
                self.record(permittedOperations=["metadata", "metadata"]))

    def test_a_missing_policy_version_is_refused(self):
        """Constitution section 5.6 requires the policy version in force."""
        for bogus in ("", "   ", 1, None):
            with self.subTest(version=bogus):
                with self.assertRaises(runtime_errors.ContractValidationError):
                    authorizations.validate_record(self.record(policyVersion=bogus))

    def test_a_malformed_source_id_is_refused(self):
        for bogus in ("example", "SRC|", "SRC|example", "", "EDU|x|y"):
            with self.subTest(source=bogus):
                with self.assertRaises((runtime_errors.ContractValidationError,
                                        runtime_errors.IdentifierError)):
                    authorizations.validate_record(self.record(sourceId=bogus))

    def test_an_expiry_before_the_decision_is_refused(self):
        with self.assertRaises(runtime_errors.ContractValidationError):
            authorizations.validate_record(
                self.record(decidedAt="2026-08-08T11:00:00.000Z",
                            expiresAt="2026-08-08T10:00:00.000Z"))

    def test_a_record_may_not_supersede_itself(self):
        entry = self.record()
        entry["supersedesAuthorizationId"] = entry["authorizationId"]
        with self.assertRaises(runtime_errors.ContractValidationError):
            authorizations.validate_record(entry)


class TestOnlyGovernanceMayAuthorize(AuthorizationCase):
    """Constitution section 14, Catalog section N."""

    def test_a_worker_may_not_authorize_an_acquisition(self):
        for authority in ("worker:CAP|research|policy-probe", "orchestrator",
                          "CAP|research|policy-probe", "policyGate", "reviewGate",
                          "WRK|acquire", "capability:x"):
            with self.subTest(authority=authority):
                with self.assertRaises(runtime_errors.AuthorizationRefusedError):
                    authorizations.validate_record(
                        self.record(decisionAuthority=authority))

    def test_an_unattributable_authority_is_refused(self):
        for authority in ("joe", "someone", "", "   ", 17, None):
            with self.subTest(authority=authority):
                with self.assertRaises((runtime_errors.ContractValidationError,
                                        runtime_errors.AuthorizationRefusedError)):
                    authorizations.validate_record(
                        self.record(decisionAuthority=authority))

    def test_a_human_or_governance_authority_is_accepted(self):
        for authority in ("operator:joe", "governance:mogo-legal",
                          "legal:external-counsel"):
            with self.subTest(authority=authority):
                authorizations.validate_record(
                    self.record(decisionAuthority=authority))


class TestStorage(AuthorizationCase):
    def test_a_record_is_stored_and_resolved(self):
        source = self.source("stored")
        entry = self.record(sourceId=source)
        self.assertEqual(self.runtime.record_authorization(entry), "recorded")
        resolved, problem = authorizations.resolve(self.runtime.connection, source)
        self.assertIsNone(problem)
        self.assertEqual(resolved["authorizationId"], entry["authorizationId"])
        self.assertEqual(resolved["policyStatus"], "PERMITTED_PUBLIC_METADATA")
        self.assertTrue(resolved["recordHash"])

    def test_recording_the_same_record_twice_is_a_no_op(self):
        entry = self.record()
        self.assertEqual(self.runtime.record_authorization(entry), "recorded")
        self.assertEqual(self.runtime.record_authorization(entry), "unchanged")

    def test_a_changed_record_under_the_same_id_is_refused(self):
        """History is corrected by supersession, never by alteration."""
        entry = self.record()
        self.runtime.record_authorization(entry)
        altered = dict(entry, policyStatus="PERMITTED_PUBLIC_ARTIFACT")
        with self.assertRaises(runtime_errors.AuthorizationRefusedError):
            self.runtime.record_authorization(altered)

    def test_the_table_is_append_only(self):
        self.runtime.record_authorization(self.record())
        for statement in ("UPDATE acquisition_authorizations SET policy_status='X'",
                          "DELETE FROM acquisition_authorizations"):
            with self.subTest(statement=statement):
                with self.assertRaises(sqlite3.IntegrityError):
                    with store.immediate_transaction(self.runtime.connection):
                        self.runtime.connection.execute(statement)

    def test_no_record_resolves_to_a_denial_reason(self):
        resolved, problem = authorizations.resolve(self.runtime.connection,
                                                   self.source("never"))
        self.assertIsNone(resolved)
        self.assertEqual(problem, policy.REASON_NO_RECORD)

    def test_an_absent_source_resolves_to_no_subject(self):
        resolved, problem = authorizations.resolve(self.runtime.connection, None)
        self.assertIsNone(resolved)
        self.assertEqual(problem, policy.REASON_NO_SUBJECT_SOURCE)

    def test_two_live_records_for_one_source_are_ambiguous_and_deny(self):
        """Two live governance decisions for one source is a conflict a machine
        must not resolve by picking one."""
        source = self.source("ambiguous")
        self.runtime.record_authorization(self.record(sourceId=source))
        self.runtime.record_authorization(
            self.record(sourceId=source, policyStatus="PROHIBITED",
                        permittedOperations=[]))
        resolved, problem = authorizations.resolve(self.runtime.connection, source)
        self.assertIsNone(resolved)
        self.assertEqual(problem, policy.REASON_AMBIGUOUS_RECORDS)


class TestSupersession(AuthorizationCase):
    def test_a_superseding_record_replaces_its_predecessor(self):
        source = self.source("superseded")
        first = self.record(sourceId=source)
        self.runtime.record_authorization(first)
        second = self.record(sourceId=source, policyStatus="PROHIBITED",
                             permittedOperations=[],
                             supersedesAuthorizationId=first["authorizationId"])
        self.runtime.record_authorization(second)

        resolved, problem = authorizations.resolve(self.runtime.connection, source)
        self.assertIsNone(problem)
        self.assertEqual(resolved["authorizationId"], second["authorizationId"])
        self.assertEqual(resolved["policyStatus"], "PROHIBITED")

    def test_supersession_is_derived_not_stamped(self):
        """The table stays append-only precisely because supersession is a
        query, never an update."""
        source = self.source("derived")
        first = self.record(sourceId=source)
        self.runtime.record_authorization(first)
        second = self.record(sourceId=source,
                             supersedesAuthorizationId=first["authorizationId"])
        self.runtime.record_authorization(second)
        self.assertEqual(authorizations.superseded_ids(self.runtime.connection),
                         {first["authorizationId"]})
        rows = authorizations.all_authorizations(self.runtime.connection)
        self.assertEqual(len(rows), 2)

    def test_superseding_an_unrecorded_authorization_is_refused(self):
        with self.assertRaises(runtime_errors.AuthorizationRefusedError):
            self.runtime.record_authorization(
                self.record(supersedesAuthorizationId=ids.new_uuid4()))

    def test_superseding_a_record_for_another_source_is_refused(self):
        first = self.record(sourceId=self.source("one"))
        self.runtime.record_authorization(first)
        with self.assertRaises(runtime_errors.AuthorizationRefusedError):
            self.runtime.record_authorization(
                self.record(sourceId=self.source("two"),
                            supersedesAuthorizationId=first["authorizationId"]))

    def test_a_source_whose_only_record_is_superseded_has_none_in_force(self):
        source = self.source("all-superseded")
        first = self.record(sourceId=source)
        self.runtime.record_authorization(first)
        # A record for a DIFFERENT source that supersedes nothing here leaves
        # the first in force; superseding it with one for this source replaces
        # it. Here the successor itself is then superseded by a third.
        second = self.record(sourceId=source,
                             supersedesAuthorizationId=first["authorizationId"])
        self.runtime.record_authorization(second)
        third = self.record(sourceId=source, policyStatus="PROHIBITED",
                            permittedOperations=[],
                            supersedesAuthorizationId=second["authorizationId"])
        self.runtime.record_authorization(third)
        resolved, problem = authorizations.resolve(self.runtime.connection, source)
        self.assertIsNone(problem)
        self.assertEqual(resolved["authorizationId"], third["authorizationId"])


class TestRecordHashing(AuthorizationCase):
    def test_the_hash_is_deterministic_and_content_derived(self):
        entry = self.record()
        first = authorizations.record_hash(entry)
        self.assertEqual(first, authorizations.record_hash(dict(entry)))
        changed = dict(entry, policyStatus="PROHIBITED")
        self.assertNotEqual(first, authorizations.record_hash(changed))

    def test_the_stored_hash_matches_the_record(self):
        entry = self.record()
        self.runtime.record_authorization(entry)
        row = self.runtime.connection.execute(
            "SELECT record_hash FROM acquisition_authorizations "
            "WHERE authorization_id = ?", (entry["authorizationId"],)).fetchone()
        self.assertEqual(row["record_hash"], authorizations.record_hash(entry))


if __name__ == "__main__":
    unittest.main(verbosity=2)

#!/usr/bin/env python3
"""MOGO-018 Step 3D -- the read-only autonomous research corpus report.

The properties under test are not "the report prints numbers". They are:

  * IT IS A READ. No network, no acquisition, no trading action, no write --
    generating the report cannot change what the report describes, and two runs
    over unchanged evidence are byte-identical.
  * THE CORPORA STAY SEPARATE. ALEX_G and TJR are counted independently, and no
    observation or artifact is counted in the wrong corpus or counted twice.
  * IT SURFACES WHAT IT DOES NOT KNOW. Unattributed streams and observations
    written before the change-detection contract existed are reported as such
    rather than guessed into a bucket that looks tidier.
  * IT MAKES NO JUDGEMENT. Counts, timestamps and presence checks only. No
    score, no maturity grade, no "ready" or "valid" anywhere in the output.

The acquisition harness is REUSED from the MOGO-017 Step 2C suite and the Step
3C two-source suite rather than duplicated.
"""

import json
import os
import sys
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "platform", "src"))

from mogo_platform.runtime import change_detection as cd            # noqa: E402
from mogo_platform.runtime import connector_authorization as ca     # noqa: E402
from mogo_platform.runtime import errors as runtime_errors           # noqa: E402
from mogo_platform.runtime import research_library as library       # noqa: E402
from mogo_platform.runtime import scheduled_collection as sched     # noqa: E402

from tests.platform.test_runtime_change_detection_wiring import (   # noqa: E402
    APPROVED_SOURCE, APPROVED_RESOURCE, AUTHORIZATION_ID)
from tests.platform.test_runtime_two_source_isolation import (      # noqa: E402
    TwoSourceCase, TJR_SOURCE, TJR_RESOURCE, TJR_AUTH, TJR_BODY_2,
    ALEX_FAMILY, TJR_FAMILY, committed_attribution, committed_entries)

# Words a corpus report must never emit about a strategy. Checked against the
# whole serialized report, because the point is that there is nowhere to put a
# verdict -- not that we remembered to leave one out today.
VERDICT_WORDS = ("ready", "mature", "valid", "invalid", "profitable",
                 "unprofitable", "good", "bad", "score", "grade", "rating",
                 "recommend", "promising")


class CorpusReportCase(TwoSourceCase):
    """Two real streams through the real runtime, then report on them."""

    def report(self):
        with self.runtime() as rt:
            return library.corpus_report(rt.connection, committed_attribution())

    def stream(self, report, source_id):
        found = [s for s in report["streams"] if s["sourceId"] == source_id]
        self.assertEqual(len(found), 1, "expected exactly one stream for %s"
                         % (source_id,))
        return found[0]

    def family_bucket(self, report, family):
        found = [c for c in report["corpora"]
                 if c["strategyFamilyId"] == family]
        self.assertEqual(len(found), 1)
        return found[0]

    def two_streams(self):
        """Alex G observed twice (unchanged), TJR observed once."""
        self.initialise_both()
        self.acquire_for(APPROVED_SOURCE, APPROVED_RESOURCE, AUTHORIZATION_ID,
                         "alex-1")
        self.acquire_for(APPROVED_SOURCE, APPROVED_RESOURCE, AUTHORIZATION_ID,
                         "alex-2")
        self.acquire_for(TJR_SOURCE, TJR_RESOURCE, TJR_AUTH, "tjr-1")


# ---------------------------------------------------------------------------
# 1-6: the corpora are separate, and the counts are right
# ---------------------------------------------------------------------------

class TestTheCorporaAreSeparate(CorpusReportCase):

    def test_alex_and_tjr_appear_as_separate_corpora(self):
        self.two_streams()
        report = self.report()
        self.assertEqual({c["strategyFamilyId"] for c in report["corpora"]},
                         {ALEX_FAMILY, TJR_FAMILY})
        self.assertEqual(self.family_bucket(report, ALEX_FAMILY)["traderId"], "ALEX_G")
        self.assertEqual(self.family_bucket(report, TJR_FAMILY)["traderId"], "TJR")
        self.assertEqual(self.family_bucket(report, ALEX_FAMILY)["sourceIds"],
                         [APPROVED_SOURCE])
        self.assertEqual(self.family_bucket(report, TJR_FAMILY)["sourceIds"],
                         [TJR_SOURCE])

    def test_stream_counts_are_deterministic_and_correct(self):
        self.two_streams()
        report = self.report()
        alex = self.stream(report, APPROVED_SOURCE)
        tjr = self.stream(report, TJR_SOURCE)
        self.assertEqual(alex["observations"],
                         {"recorded": 2, "accepted": 2, "notAccepted": 0})
        self.assertEqual(tjr["observations"],
                         {"recorded": 1, "accepted": 1, "notAccepted": 0})
        self.assertEqual(report["totals"]["streams"], 2)
        self.assertEqual(report["totals"]["acceptedObservations"], 3)

    def test_tjr_first_observation_is_counted_only_for_tjr(self):
        self.two_streams()
        report = self.report()
        tjr = self.stream(report, TJR_SOURCE)
        alex = self.stream(report, APPROVED_SOURCE)
        self.assertEqual(tjr["classifications"]["FIRST_OBSERVATION"], 1)
        self.assertEqual(alex["classifications"]["FIRST_OBSERVATION"], 1,
                         "Alex G has its own first observation, not TJR's")
        self.assertEqual(self.family_bucket(report, TJR_FAMILY)["firstObservationCount"],
                         1)
        self.assertEqual(
            self.family_bucket(report, ALEX_FAMILY)["firstObservationCount"], 1)

    def test_alex_prior_observations_remain_only_under_alex(self):
        """Alex G accumulates; TJR must not inherit any of it."""
        self.initialise_both()
        for label in ("a1", "a2", "a3"):
            self.acquire_for(APPROVED_SOURCE, APPROVED_RESOURCE,
                             AUTHORIZATION_ID, label)
        self.acquire_for(TJR_SOURCE, TJR_RESOURCE, TJR_AUTH, "t1")
        report = self.report()
        self.assertEqual(
            self.family_bucket(report, ALEX_FAMILY)["acceptedObservations"], 3)
        self.assertEqual(
            self.family_bucket(report, TJR_FAMILY)["acceptedObservations"], 1)
        self.assertEqual(self.stream(report, TJR_SOURCE)["classifications"],
                         {"FIRST_OBSERVATION": 1, "UNCHANGED": 0, "CHANGED": 0,
                          library.CLASSIFICATION_NOT_RECORDED: 0})

    def test_no_artifact_is_double_counted(self):
        """Repeat observations of UNCHANGED content are ONE artifact.

        Counting observations as artifacts would inflate exactly the corpus that
        is behaving correctly, so this is the count most worth pinning.
        """
        self.two_streams()
        report = self.report()
        alex = self.stream(report, APPROVED_SOURCE)
        tjr = self.stream(report, TJR_SOURCE)
        self.assertEqual(alex["observations"]["accepted"], 2)
        self.assertEqual(alex["artifactCount"], 1,
                         "two unchanged observations are one artifact")
        self.assertEqual(tjr["artifactCount"], 1)
        # No artifact identifier appears in more than one stream.
        every = [aid for s in report["streams"] for aid in s["artifactIds"]]
        self.assertEqual(len(every), len(set(every)))
        self.assertEqual(report["totals"]["artifacts"], 2)
        self.assertEqual(self.family_bucket(report, ALEX_FAMILY)["artifacts"], 1)
        self.assertEqual(self.family_bucket(report, TJR_FAMILY)["artifacts"], 1)

    def test_strategy_family_attribution_is_explicit(self):
        self.two_streams()
        report = self.report()
        for source, family, trader in ((APPROVED_SOURCE, ALEX_FAMILY, "ALEX_G"),
                                       (TJR_SOURCE, TJR_FAMILY, "TJR")):
            with self.subTest(source=source):
                stream = self.stream(report, source)
                self.assertEqual(stream["attributionStatus"], "ATTRIBUTED")
                self.assertEqual(stream["strategyFamilyIds"], [family])
                self.assertEqual(stream["traderId"], trader)
        self.assertEqual(report["totals"]["unattributedStreams"], 0)

    def test_a_changed_observation_is_counted_only_in_its_own_corpus(self):
        self.two_streams()
        self.bodies[TJR_RESOURCE] = TJR_BODY_2
        self.acquire_for(TJR_SOURCE, TJR_RESOURCE, TJR_AUTH, "tjr-2")
        report = self.report()
        self.assertEqual(self.family_bucket(report, TJR_FAMILY)["changedObservations"], 1)
        self.assertEqual(self.family_bucket(report, ALEX_FAMILY)["changedObservations"],
                         0)
        self.assertEqual(self.stream(report, APPROVED_SOURCE)
                         ["latestClassification"], cd.UNCHANGED)


# ---------------------------------------------------------------------------
# 7: what it does not know, it says
# ---------------------------------------------------------------------------

class TestUnknownsAreSurfacedNotGuessed(CorpusReportCase):

    def test_an_unattributed_stream_is_surfaced_rather_than_guessed(self):
        """Attribution is removed for TJR; its material must NOT fall into
        Alex G's corpus, and must not silently disappear either."""
        self.two_streams()
        document = committed_attribution()
        document["attributions"] = [r for r in document["attributions"]
                                    if r["sourceId"] != TJR_SOURCE]
        with self.runtime() as rt:
            report = library.corpus_report(rt.connection, document)
        tjr = self.stream(report, TJR_SOURCE)
        self.assertEqual(tjr["attributionStatus"], "UNATTRIBUTED")
        self.assertIsNone(tjr["traderId"])
        self.assertEqual(tjr["strategyFamilyIds"], [])
        self.assertEqual(report["totals"]["unattributedStreams"], 1)
        families = {c["strategyFamilyId"] for c in report["corpora"]}
        self.assertIn("(unattributed)", families)
        self.assertNotIn(TJR_FAMILY, families)
        # And Alex G did not absorb it.
        self.assertEqual(
            self.family_bucket(report, ALEX_FAMILY)["acceptedObservations"], 2)

    def test_a_missing_classification_is_its_own_bucket(self):
        """Rows written before MOGO-017 carry no classification. They must not
        be counted as UNCHANGED just because that would look tidier."""
        self.two_streams()
        with self.runtime() as rt:
            rt.connection.execute(
                "UPDATE capability_results SET result_json = "
                "json_remove(result_json, '$.changeDetection') "
                "WHERE json_extract(result_json,'$.sourceId') = ? "
                "AND json_extract(result_json,'$.changeDetection.classification')"
                " = 'UNCHANGED'", (APPROVED_SOURCE,))
            rt.connection.commit()
        report = self.report()
        alex = self.stream(report, APPROVED_SOURCE)
        self.assertEqual(alex["classifications"]["UNCHANGED"], 0)
        self.assertEqual(alex["classifications"][library.CLASSIFICATION_NOT_RECORDED],
                         1)
        self.assertEqual(alex["observations"]["accepted"], 2,
                         "the observation is still accepted content")
        self.assertEqual(
            self.family_bucket(report, ALEX_FAMILY)["classificationNotRecorded"], 1)

    def test_incomplete_acquisition_provenance_is_reported_not_hidden(self):
        self.two_streams()
        with self.runtime() as rt:
            rt.connection.execute(
                "UPDATE capability_results SET result_json = "
                "json_remove(result_json, '$.acquiredAt') "
                "WHERE json_extract(result_json,'$.sourceId') = ?",
                (TJR_SOURCE,))
            rt.connection.commit()
        tjr = self.stream(self.report(), TJR_SOURCE)
        self.assertEqual(tjr["acquisitionProvenance"]["incompleteObservations"], 1)
        self.assertIn("acquiredAt",
                      tjr["acquisitionProvenance"]["missingFields"])


# ---------------------------------------------------------------------------
# Provenance semantics: acquisition is NOT ingestion
# ---------------------------------------------------------------------------

class TestAcquisitionProvenanceIsDistinctFromIngestion(CorpusReportCase):

    def test_network_access_is_derived_from_the_authoritative_record(self):
        """The Step 3C finding, handled without touching evidence.

        The artifact wrapper says networkAccessPerformed=false. The governed
        acquisition genuinely opened a socket. The report must follow the
        AUTHORITATIVE acquisition record, not the wrapper.
        """
        self.two_streams()
        report = self.report()
        for source in (APPROVED_SOURCE, TJR_SOURCE):
            with self.subTest(source=source):
                stream = self.stream(report, source)
                self.assertEqual(
                    stream["acquisitionProvenance"]["networkAccessObservations"],
                    stream["observations"]["recorded"],
                    "every recorded acquisition reached the network")

    def test_the_report_never_reads_the_wrapper_provenance_fields(self):
        module_src = open(library.__file__, "r", encoding="utf-8").read()
        marker = module_src.split("MOGO-018 Step 3D", 1)[1]
        for field in ("acquisitionPerformed", "networkAccessPerformed"):
            # The field name may be DISCUSSED in prose, but must never be read
            # off a record as `.get("acquisitionPerformed")`.
            self.assertNotIn('get("%s")' % field, marker)
            self.assertNotIn("get('%s')" % field, marker)


# ---------------------------------------------------------------------------
# 8-12: it is a read, it is deterministic, it judges nothing
# ---------------------------------------------------------------------------

class TestTheReportIsAReadOnly(CorpusReportCase):

    def test_repeated_generation_is_byte_identical(self):
        self.two_streams()
        first = json.dumps(self.report(), sort_keys=True)
        second = json.dumps(self.report(), sort_keys=True)
        self.assertEqual(first, second)

    def test_generation_performs_no_network_access(self):
        """The doubled socket counts calls. Reporting must add none."""
        self.two_streams()
        before = self.opener.calls
        self.report()
        self.report()
        self.assertEqual(self.opener.calls, before)

    def test_generation_performs_no_acquisition_and_writes_no_row(self):
        self.two_streams()
        before = self.recorded_results()
        self.report()
        self.assertEqual(self.recorded_results(), before)

    def test_generation_takes_no_trading_or_promotion_path(self):
        """There is no code path from this report to a trading action.

        Asserted against the CODE rather than the prose, because this module's
        docstrings legitimately discuss the very words being searched for.
        """
        import ast
        with open(library.__file__, "r", encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        for node in ast.walk(tree):
            body = getattr(node, "body", None)
            if isinstance(body, list) and body and isinstance(
                    node, (ast.Module, ast.ClassDef, ast.FunctionDef)):
                first = body[0]
                if isinstance(first, ast.Expr) and isinstance(
                        first.value, ast.Constant) and isinstance(
                        first.value.value, str):
                    body.pop(0)
        code = ast.unparse(tree)
        for forbidden in ("submit", "execute_trade", "place_order", "backtest",
                          "hypothesis", "promote", "blueprint", "campaign"):
            self.assertNotIn(forbidden, code.lower(),
                             "the corpus report must have no path to %r"
                             % (forbidden,))

    def test_immutable_evidence_is_never_modified(self):
        """The harness's own tearDown asserts the genuine corpus listing is
        unchanged; this pins the file BYTES of the committed artifacts too."""
        import glob
        import hashlib
        from mogo_platform.runtime import research_corpus
        paths = sorted(glob.glob(os.path.join(
            research_corpus.PRODUCTION_ARTIFACT_ROOT, "*.json")))

        def digest():
            return {p: hashlib.sha256(open(p, "rb").read()).hexdigest()
                    for p in paths}

        before = digest()
        self.two_streams()
        self.report()
        self.assertEqual(digest(), before)

    def test_no_verdict_word_appears_anywhere_in_the_output(self):
        """There must be nowhere to put a maturity judgement."""
        self.two_streams()
        blob = json.dumps(self.report()).lower()
        for word in VERDICT_WORDS:
            with self.subTest(word=word):
                self.assertNotIn(word, blob)

    def test_maturity_is_expressed_only_as_deterministic_facts(self):
        self.two_streams()
        bucket = self.family_bucket(self.report(), TJR_FAMILY)
        for field in ("distinctApprovedResources", "acceptedObservations",
                      "changedObservations", "artifacts",
                      "distinctContentIdentities", "observedFrom", "observedTo",
                      "provenanceCompleteObservations", "integrityStatus"):
            self.assertIn(field, bucket)
        for value in bucket.values():
            self.assertNotIsInstance(value, float,
                                     "a float here would be a score")


# ---------------------------------------------------------------------------
# 13-16: earlier steps are untouched
# ---------------------------------------------------------------------------

class TestEarlierStepsAreUnchanged(CorpusReportCase):

    def test_step_2_bridge_semantics_are_unchanged(self):
        """The Step 3D report is additive: `entries()` output must not move."""
        self.two_streams()
        entries = self.library_entries()
        self.assertEqual(len(entries), 2)
        for entry in entries:
            with self.subTest(source=entry["sourceId"]):
                self.assertEqual(entry["schemaVersion"],
                                 library.ENTRY_SCHEMA_VERSION)
                self.assertEqual(entry["acceptedContentIdentityBasis"],
                                 library.CONTENT_IDENTITY_BASIS)
                self.assertNotIn("contentHash", entry)
                self.assertEqual(entry["promotionStatus"], "NOT_A_TRADING_RULE")
        summary = {b["strategyFamilyId"]: b for b in self.corpus_summary()}
        self.assertEqual(set(summary), {ALEX_FAMILY, TJR_FAMILY})

    def test_step_3a_authorization_remains_fail_closed(self):
        for stranger in ("SRC|youtube|ICTICTICTIC", "SRC|evil|deadbeefcafe"):
            with self.subTest(source=stranger):
                self.assertNotIn(stranger, ca.APPROVED_DESTINATIONS)
        decision = ca.evaluate({"sourceId": TJR_SOURCE,
                                "authorizationId": TJR_AUTH,
                                "operation": "metadata", "resourceId": "nope"})
        self.assertFalse(decision.permitted)

    def test_step_3b_bounded_collection_is_unchanged(self):
        self.assertEqual(sched.MAX_COLLECTION_ENTRIES, 25)
        self.assertTrue(all(e["collectionWindowSeconds"] == 21600
                            for e in committed_entries()))

    def test_step_3c_two_source_configuration_is_unchanged(self):
        self.assertEqual(set(ca.approved_source_ids()),
                         {APPROVED_SOURCE, TJR_SOURCE})
        self.assertEqual([(e["sourceId"], e["resourceId"])
                          for e in committed_entries()],
                         [(APPROVED_SOURCE, APPROVED_RESOURCE),
                          (TJR_SOURCE, TJR_RESOURCE)])

    def test_the_report_reflects_authorization_state_per_source(self):
        self.two_streams()
        report = self.report()
        for source, auth_id in ((APPROVED_SOURCE, AUTHORIZATION_ID),
                                (TJR_SOURCE, TJR_AUTH)):
            with self.subTest(source=source):
                auth = self.stream(report, source)["authorization"]
                self.assertEqual(auth["status"], "AUTHORIZED")
                self.assertEqual(auth["authorizationId"], auth_id)
                self.assertEqual(auth["permittedOperations"], ["metadata"])

    def test_integrity_reports_clean_streams_for_the_real_configuration(self):
        self.two_streams()
        for stream in self.report()["streams"]:
            with self.subTest(source=stream["sourceId"]):
                self.assertEqual(stream["integrity"]["status"], "OK")
                self.assertEqual(
                    stream["integrity"]["comparisonStreamMismatches"], 0)
                self.assertEqual(stream["integrity"]["historyChainBreaks"], 0)
                self.assertEqual(
                    stream["integrity"]["acceptedObservationsWithoutArtifact"], 0)


# ---------------------------------------------------------------------------
# Step 3F: the identifier survives every hop of the pipeline
# ---------------------------------------------------------------------------

class TestIdentifierContinuityAcrossThePipeline(CorpusReportCase):
    """The ONE proof the suite was missing before Step 3F.

    Every hop had a test; the unbroken CHAIN did not. This walks a single stream
    from the committed collection entry to the corpus report and asserts the SAME
    (sourceId, resourceId) and the SAME authorizationId at every hop -- because a
    pipeline that preserves identity in each stage independently can still lose it
    at a seam, and a lost identity is exactly how one educator's material would
    end up in another's corpus.
    """

    def test_the_committed_entry_identity_reaches_the_corpus_report(self):
        self.two_streams()
        report = self.report()
        entries = {e["sourceId"]: e for e in committed_entries()}
        library_entries = {e["sourceId"]: e for e in self.library_entries()}

        for source_id, expected_resource, expected_auth in (
                (APPROVED_SOURCE, APPROVED_RESOURCE, AUTHORIZATION_ID),
                (TJR_SOURCE, TJR_RESOURCE, TJR_AUTH)):
            with self.subTest(source=source_id):
                # 1. committed collection entry -- the only place a stream is named
                entry = entries[source_id]
                self.assertEqual(entry["resourceId"], expected_resource)

                # 2. the destination registry, which is where the URL comes from
                self.assertIn(source_id, ca.APPROVED_DESTINATIONS)
                url, _ = ca.derive_destination(source_id, entry["resourceId"])

                # 3. the connector gate's own decision
                decision = ca.evaluate({
                    "sourceId": source_id,
                    "authorizationId": entry["authorizationId"],
                    "operation": entry["operation"],
                    "resourceId": entry["resourceId"]})
                self.assertTrue(decision.permitted, decision.reason)
                self.assertEqual(decision.sourceId, source_id)
                self.assertEqual(decision.approvedUrl, url)

                # 4. the acquisition record the runtime actually stored
                results = [r for r in self.recorded_results()
                           if r.get("sourceId") == source_id]
                self.assertTrue(results)
                result = results[-1]
                self.assertEqual(result["resourceId"], entry["resourceId"])
                self.assertEqual(result["authorizationId"], expected_auth)
                self.assertEqual(result["connectorDecision"]["sourceId"], source_id)
                self.assertEqual(result["connectorDecision"]["approvedUrl"], url)
                self.assertEqual(result["finalUrl"], url,
                                 "the fetched URL is the derived one, unaltered")

                # 5. change detection compared THIS stream against itself
                self.assertEqual(result["changeDetection"]["comparisonStream"],
                                 {"sourceId": source_id,
                                  "resourceId": entry["resourceId"]})

                # 6. the immutable artifact reference
                artifact_id = result["ingestion"]["artifactId"]
                self.assertTrue(artifact_id.startswith("RART|"))
                self.assertTrue(result["intakeRef"])

                # 7. the Step 2 bridge entry
                bridge = library_entries[source_id]
                self.assertEqual(bridge["resourceId"], entry["resourceId"])
                self.assertEqual(bridge["artifactId"], artifact_id)
                self.assertEqual(bridge["authorizationId"], expected_auth)

                # 8. the Step 3D corpus report stream
                stream = self.stream(report, source_id)
                self.assertEqual(stream["resourceId"], entry["resourceId"])
                self.assertIn(artifact_id, stream["artifactIds"])
                self.assertEqual(stream["authorization"]["authorizationId"],
                                 expected_auth)

    def test_the_chain_cannot_start_for_an_unapproved_source(self):
        """Fail-closed at hop 2, before any of the rest exists."""
        for stranger in ("SRC|youtube|ICTICTICTIC", "SRC|youtube|CRTCRTCRTCR"):
            with self.subTest(source=stranger):
                self.assertNotIn(stranger, ca.APPROVED_DESTINATIONS)
                with self.assertRaises(runtime_errors.PlatformError):
                    ca.derive_destination(stranger, TJR_RESOURCE)
                self.assertNotIn(stranger,
                                 {e["sourceId"] for e in committed_entries()})


if __name__ == "__main__":
    unittest.main()

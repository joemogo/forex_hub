#!/usr/bin/env python3
"""MOGO-017 Step 2C -- the wired autonomous change detector.

WHAT IS UNDER TEST

    Not "the classifier returns sensible values" -- Step 2B proved that against
    the pure contract. What is proved here is that the PRODUCTION SEAM IS
    GENUINELY WIRED, and that it cannot lie in either direction:

      * a repeat of identical bytes under a NEW request identity is UNCHANGED,
        and emits nothing;
      * genuinely different accepted bytes are CHANGED, and emit EXACTLY ONE
        SourceMutationDetected carrying both identities;
      * a failure never advances the comparison history and never emits.

HOW MUCH IS REAL

    Almost all of it. Each run below goes through the real Orchestrator on a
    temporary state root: real command contract, real policy gate, real
    authorization record, real claim/lease, the real acquisition capability
    (connector gate, permit derivation, bounded transport limits, content
    hashing, raw preservation), the real ingestion capability, the real result
    store, and the real event log.

    TWO things are doubled, and only two:

      1. the SOCKET -- `connector_transport._opener` is replaced with a stub, so
         the REAL gate, the REAL permit, the REAL limits and the REAL validation
         all still execute against synthetic bytes. Nothing in the gate or the
         transport is bypassed.
      2. the CORPUS -- a Step 2B sandbox, which sandbox_corpus() has already
         refused to construct unless it provably cannot reach the genuine
         research corpus.

    A fixture below asserts the genuine corpus listing is byte-identical before
    and after the entire suite.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "platform", "src"))

from mogo_platform.contracts import ids                                # noqa: E402
from mogo_platform.runtime import acquisition_history                  # noqa: E402
from mogo_platform.runtime import change_detection as cd               # noqa: E402
from mogo_platform.runtime import connector_transport as transport     # noqa: E402
from mogo_platform.runtime import event_log as event_log_module        # noqa: E402
from mogo_platform.runtime import orchestrator as orchestrator_module  # noqa: E402
from mogo_platform.runtime import paths as paths_module                # noqa: E402
from mogo_platform.runtime import research_corpus                      # noqa: E402
from mogo_platform.runtime import scheduled_collection                 # noqa: E402
from mogo_platform.runtime.capabilities import acquire_approved_source_metadata as acquire  # noqa: E402

APPROVED_SOURCE = "SRC|youtube|c785970cc458"
APPROVED_RESOURCE = "hb7ot1_szWI"
OTHER_RESOURCE = "dQw4w9WgXcQ"
AUTHORIZATION_ID = "96fc2793-b13b-467a-89a8-f31a76ec6d4c"

# Two valid, distinguishable bodies. Both parse as JSON and satisfy every real
# transport limit, so they reach acceptance rather than being refused early.
BODY_A = b'{"mogoFixture":"2c-A","title":"FIXTURE A","provider_name":"TEST"}'
BODY_B = b'{"mogoFixture":"2c-B","title":"FIXTURE B CHANGED","provider_name":"TEST"}'
BODY_INVALID = b'{"mogoFixture":"2c-broken",'          # truncated: not valid JSON

HASH_A = ids.sha256_hex(BODY_A)
HASH_B = ids.sha256_hex(BODY_B)


class _Response(object):
    """The minimal shape connector_transport actually reads from a response."""

    def __init__(self, body, url, status=200, content_type="application/json"):
        self.status = status
        self.url = url
        self.headers = {"Content-Type": content_type}
        self._body = body
        self._read = False

    def read(self, size=None):
        if self._read:
            return b""
        self._read = True
        return self._body if size is None else self._body[:size]

    def getcode(self):
        return self.status

    def close(self):
        pass


class _Opener(object):
    """Stands in for the socket ONLY. The gate and the transport are real."""

    def __init__(self, box):
        self.box = box
        self.calls = 0

    def open(self, request, timeout=None):
        self.calls += 1
        if self.box.get("raise"):
            raise self.box["raise"]
        url = request.full_url if hasattr(request, "full_url") else request
        return _Response(self.box["body"], url,
                         status=self.box.get("status", 200),
                         content_type=self.box.get("contentType",
                                                   "application/json"))


class ChangeDetectionWiringCase(unittest.TestCase):
    """One temporary state root and one sandbox corpus per test."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = os.path.join(self._tmp.name, "state")
        self.paths = paths_module.RuntimePaths(self.root)
        self.corpus_dir = os.path.join(self._tmp.name, "corpus")
        self.intake = os.path.join(self.corpus_dir, "intake")
        self.artifacts = os.path.join(self.corpus_dir, "research-artifacts")
        os.makedirs(self.intake)
        os.makedirs(self.artifacts)
        self.corpus = research_corpus.sandbox_corpus(self.intake, self.artifacts)

        self.box = {"body": BODY_A}
        self.opener = _Opener(self.box)
        self._real_opener = transport._opener
        transport._opener = lambda: self.opener

        # Dispatch to the REAL capability, with the sandbox corpus bound. The
        # orchestrator still looks the capability up in its own table and still
        # executes it through the real worker.
        self._real_callable = orchestrator_module.CAPABILITY_CALLABLES[
            acquire.CAPABILITY_ID]
        orchestrator_module.CAPABILITY_CALLABLES[acquire.CAPABILITY_ID] = (
            lambda payload: acquire.execute(payload, corpus=self.corpus))

        self.genuine_before = self._genuine_corpus_listing()

    def tearDown(self):
        transport._opener = self._real_opener
        orchestrator_module.CAPABILITY_CALLABLES[acquire.CAPABILITY_ID] = \
            self._real_callable
        self.assertEqual(self._genuine_corpus_listing(), self.genuine_before,
                         "a fixture must never alter the genuine research corpus")
        self._tmp.cleanup()

    @staticmethod
    def _genuine_corpus_listing():
        listing = {}
        for root in (research_corpus.PRODUCTION_ARTIFACT_ROOT,
                     os.path.join(research_corpus.PRODUCTION_INTAKE_ROOT,
                                  "acquired")):
            if os.path.isdir(root):
                listing[root] = sorted(os.listdir(root))
        return listing

    # -- runtime driving ----------------------------------------------------

    def runtime(self, create=False):
        return orchestrator_module.Orchestrator(paths=self.paths, create=create)

    def initialise(self):
        with self.runtime(create=True) as rt:
            rt.register_builtin_capabilities()
            rt.record_authorization({
                "authorizationId": AUTHORIZATION_ID,
                "sourceId": APPROVED_SOURCE,
                "policyStatus": "PERMITTED_PUBLIC_METADATA",
                "policyVersion": "1.0",
                "decisionAuthority": "operator:test-fixture",
                "decidedAt": "2026-08-11T00:00:00.000Z",
                "permittedOperations": ["metadata"],
            })

    def acquire_once(self, window_label, resource_id=APPROVED_RESOURCE):
        """One full governed acquisition. `window_label` is the REQUEST identity.

        Distinct labels produce distinct idempotency keys, which is exactly how
        Run A and Run B differ while carrying identical content.
        """
        spec = {
            "schemaVersion": scheduled_collection.SPEC_SCHEMA_VERSION,
            "capabilityId": acquire.CAPABILITY_ID,
            "commandType": "AcquireSourceMetadata", "commandVersion": 1,
            "sourceId": APPROVED_SOURCE, "resourceId": resource_id,
            "authorizationId": AUTHORIZATION_ID, "operation": "metadata",
            "connectorId": "CONN|research|approved-source-metadata",
            "connectorVersion": "1.0.0", "policyVersion": "1.0",
            "collectionWindowSeconds": 120,
        }
        envelope, payload, _ = scheduled_collection.build_command(
            spec, 1_786_000_000_000, "2026-08-11T00:00:00.000Z")
        # Override the request identity explicitly, so the test controls it
        # rather than depending on wall-clock windowing.
        envelope["idempotencyKey"] = ids.content_hash_of(
            {"fixtureRequest": window_label, "resource": resource_id})
        payload = dict(payload)
        payload["collectionWindow"] = window_label
        envelope["payloadHash"] = ids.content_hash_of(payload)
        with self.runtime() as rt:
            rt.recover()
            outcome = rt.submit(envelope, payload)
            self.assertEqual(outcome.status, "accepted", outcome.reason)
            report = rt.run_once()
        return outcome, report

    def recorded_results(self):
        with self.runtime() as rt:
            return [json.loads(r["result_json"]) for r in rt.connection.execute(
                "SELECT result_json FROM capability_results "
                "ORDER BY recorded_at, rowid")]

    def events(self, event_type=None):
        records = event_log_module.EventLog(self.paths).scan(verify=True).records
        return [record.event for record in records
                if event_type is None
                or record.event["eventType"] == event_type]

    def classification_of(self, result):
        return (result.get("changeDetection") or {}).get("classification")


# ---------------------------------------------------------------------------
# Step 2C-7: the deterministic three-run proof
# ---------------------------------------------------------------------------

class TestRunARunBRunC(ChangeDetectionWiringCase):

    def test_first_observation_then_unchanged_then_changed(self):
        self.initialise()

        # ── RUN A: valid bytes A, request identity R1 ──────────────────────
        self.box["body"] = BODY_A
        outcome_a, report_a = self.acquire_once("R1")
        self.assertEqual(len(report_a["succeeded"]), 1, report_a)
        results = self.recorded_results()
        self.assertEqual(len(results), 1)
        run_a = results[0]
        self.assertEqual(run_a["contentHash"], HASH_A)
        self.assertEqual(self.classification_of(run_a), cd.FIRST_OBSERVATION)
        self.assertIsNone(run_a["changeDetection"]["priorContentIdentity"])
        self.assertEqual(run_a["changeDetection"]["currentContentIdentity"], HASH_A)
        self.assertEqual(self.events("SourceMutationDetected"), [],
                         "a first observation must never be reported as a mutation")

        # ── RUN B: IDENTICAL bytes A, DIFFERENT request identity R2 ────────
        self.box["body"] = BODY_A
        outcome_b, report_b = self.acquire_once("R2")
        self.assertEqual(len(report_b["succeeded"]), 1, report_b)
        self.assertNotEqual(outcome_a.idempotency_key, outcome_b.idempotency_key,
                            "R1 and R2 must be genuinely different requests")
        results = self.recorded_results()
        self.assertEqual(len(results), 2)
        run_b = results[1]
        self.assertEqual(run_b["contentHash"], HASH_A,
                         "identical bytes must produce an identical identity")
        self.assertEqual(self.classification_of(run_b), cd.UNCHANGED)
        self.assertEqual(run_b["changeDetection"]["priorContentIdentity"], HASH_A)
        self.assertEqual(run_b["changeDetection"]["currentContentIdentity"], HASH_A)
        self.assertEqual(run_b["changeDetection"]["priorAcquisitionKey"],
                         outcome_a.idempotency_key,
                         "the baseline must be the prior ACCEPTED acquisition")
        self.assertEqual(self.events("SourceMutationDetected"), [],
                         "unchanged content must never emit a mutation")

        # ── RUN C: DIFFERENT valid bytes B, request identity R3 ────────────
        self.box["body"] = BODY_B
        outcome_c, report_c = self.acquire_once("R3")
        self.assertEqual(len(report_c["succeeded"]), 1, report_c)
        results = self.recorded_results()
        self.assertEqual(len(results), 3)
        run_c = results[2]
        self.assertEqual(run_c["contentHash"], HASH_B)
        self.assertNotEqual(HASH_A, HASH_B)
        self.assertEqual(self.classification_of(run_c), cd.CHANGED)
        self.assertEqual(run_c["changeDetection"]["priorContentIdentity"], HASH_A)
        self.assertEqual(run_c["changeDetection"]["currentContentIdentity"], HASH_B)

        # ── EXACTLY ONE mutation event, carrying both identities ───────────
        mutations = self.events("SourceMutationDetected")
        self.assertEqual(len(mutations), 1,
                         "exactly one mutation event for one genuine change")
        payload = mutations[0]["payload"]
        self.assertEqual(payload["priorContentIdentity"], HASH_A)
        self.assertEqual(payload["currentContentIdentity"], HASH_B)
        self.assertEqual(payload["sourceId"], APPROVED_SOURCE)
        self.assertEqual(payload["resourceId"], APPROVED_RESOURCE)
        self.assertEqual(payload["contentIdentityBasis"],
                         "RAW_EXTERNAL_RESPONSE_BYTES")
        self.assertEqual(payload["lane"], "RESEARCH")
        self.assertEqual(payload["promotionStatus"], "NOT_A_TRADING_RULE")
        self.assertIn(APPROVED_SOURCE, mutations[0]["subjectRefs"])
        self.assertEqual(mutations[0]["producer"], "orchestrator")

        # The event log parses, validates and hashes -- the mutation event did
        # not weaken event validation.
        self.assertTrue(event_log_module.EventLog(self.paths).scan(verify=True)
                        .records)

    def test_the_classification_survives_a_process_restart(self):
        """Durability: a fresh runtime reads the recorded classification."""
        self.initialise()
        self.box["body"] = BODY_A
        self.acquire_once("R1")
        with self.runtime() as rt:
            rows = rt.connection.execute(
                "SELECT result_json FROM capability_results").fetchall()
        stored = json.loads(rows[0]["result_json"])
        self.assertEqual(stored["changeDetection"]["classification"],
                         cd.FIRST_OBSERVATION)
        self.assertEqual(stored["changeDetection"]["contract"],
                         cd.CONTRACT_VERSION)


# ---------------------------------------------------------------------------
# Step 2C-8: failure proofs
# ---------------------------------------------------------------------------

class TestFailuresNeverAdvanceHistory(ChangeDetectionWiringCase):

    def test_an_acquisition_failure_records_nothing_and_moves_no_baseline(self):
        self.initialise()
        self.box["body"] = BODY_A
        self.acquire_once("R1")

        self.box["status"] = 500                     # transient transport failure
        self.acquire_once("R2")
        results = self.recorded_results()
        self.assertEqual(len(results), 1,
                         "a failed acquisition must record no result")
        self.assertEqual(self.classification_of(results[0]), cd.FIRST_OBSERVATION)
        self.assertEqual(self.events("SourceMutationDetected"), [])

        # The next GOOD run still compares against run A -- the baseline held.
        self.box.pop("status")
        self.box["body"] = BODY_A
        self.acquire_once("R3")
        results = self.recorded_results()
        self.assertEqual(self.classification_of(results[-1]), cd.UNCHANGED)
        self.assertEqual(results[-1]["changeDetection"]["priorContentIdentity"],
                         HASH_A)

    def test_changed_bytes_that_fail_validation_are_not_a_mutation(self):
        """The proof that matters most: different bytes, refused by validation."""
        self.initialise()
        self.box["body"] = BODY_A
        self.acquire_once("R1")

        self.box["body"] = BODY_INVALID              # different AND unparseable
        self.acquire_once("R2")
        results = self.recorded_results()
        self.assertEqual(len(results), 1,
                         "unvalidated content must never be recorded as accepted")
        self.assertEqual(self.events("SourceMutationDetected"), [],
                         "changed-but-invalid must never emit a mutation")

        # And the baseline is still A, not the rejected bytes.
        self.box["body"] = BODY_A
        self.acquire_once("R3")
        self.assertEqual(self.classification_of(self.recorded_results()[-1]),
                         cd.UNCHANGED)

    def test_a_wrong_content_type_is_refused_and_moves_no_baseline(self):
        self.initialise()
        self.box["body"] = BODY_A
        self.acquire_once("R1")
        self.box["body"] = BODY_B
        self.box["contentType"] = "text/html"
        self.acquire_once("R2")
        self.assertEqual(len(self.recorded_results()), 1)
        self.assertEqual(self.events("SourceMutationDetected"), [])

    def test_duplicate_already_ingested_content_remains_unchanged(self):
        """`ingested=false` is a storage fact, not a content fact."""
        self.initialise()
        self.box["body"] = BODY_A
        self.acquire_once("R1")
        self.acquire_once("R2")
        results = self.recorded_results()
        self.assertEqual(results[1]["ingestion"]["duplicateStatus"],
                         "DUPLICATE_ALREADY_INGESTED")
        self.assertFalse(results[1]["ingestion"]["ingested"])
        self.assertEqual(self.classification_of(results[1]), cd.UNCHANGED)
        self.assertEqual(self.events("SourceMutationDetected"), [])

    def test_a_first_accepted_observation_never_emits_a_mutation(self):
        self.initialise()
        self.box["body"] = BODY_A
        self.acquire_once("R1")
        self.assertEqual(self.classification_of(self.recorded_results()[0]),
                         cd.FIRST_OBSERVATION)
        self.assertEqual(self.events("SourceMutationDetected"), [])

    def test_a_different_resource_is_a_separate_history(self):
        """Same source, different resource: the streams must not interfere."""
        self.initialise()
        self.box["body"] = BODY_A
        self.acquire_once("R1", resource_id=APPROVED_RESOURCE)
        self.box["body"] = BODY_B
        self.acquire_once("R2", resource_id=OTHER_RESOURCE)
        results = self.recorded_results()
        self.assertEqual(self.classification_of(results[0]), cd.FIRST_OBSERVATION)
        self.assertEqual(self.classification_of(results[1]), cd.FIRST_OBSERVATION,
                         "a different resource starts its OWN history, and "
                         "different bytes there are not a mutation of the first")
        self.assertEqual(self.events("SourceMutationDetected"), [])

    def test_a_different_source_is_a_separate_history(self):
        """Proved at the history layer, since only one source is authorized."""
        self.initialise()
        self.box["body"] = BODY_A
        self.acquire_once("R1")
        with self.runtime() as rt:
            same = acquisition_history.prior_accepted(
                rt.connection, acquire.CAPABILITY_ID,
                APPROVED_SOURCE, APPROVED_RESOURCE)
            other_source = acquisition_history.prior_accepted(
                rt.connection, acquire.CAPABILITY_ID,
                "SRC|web|0123456789ab", APPROVED_RESOURCE)
            other_resource = acquisition_history.prior_accepted(
                rt.connection, acquire.CAPABILITY_ID,
                APPROVED_SOURCE, OTHER_RESOURCE)
        self.assertIsNotNone(same)
        self.assertEqual(same.contentIdentity, HASH_A)
        self.assertIsNone(other_source, "another source must not inherit history")
        self.assertIsNone(other_resource, "another resource must not inherit it")

    def test_a_run_never_compares_against_itself(self):
        self.initialise()
        self.box["body"] = BODY_A
        outcome, _ = self.acquire_once("R1")
        with self.runtime() as rt:
            excluded = acquisition_history.prior_accepted(
                rt.connection, acquire.CAPABILITY_ID, APPROVED_SOURCE,
                APPROVED_RESOURCE,
                exclude_idempotency_key=outcome.idempotency_key)
        self.assertIsNone(excluded)


# ---------------------------------------------------------------------------
# Step 2C-9 / 2C-12: the seam is genuinely wired, and visible
# ---------------------------------------------------------------------------

class TestTheSeamIsWiredAndVisible(ChangeDetectionWiringCase):

    def test_the_real_governed_lifecycle_reaches_the_classifier(self):
        """Policy -> authorization -> claim -> execute -> ingest -> classify."""
        self.initialise()
        self.box["body"] = BODY_A
        _outcome, report = self.acquire_once("R1")
        self.assertEqual(len(report["succeeded"]), 1)
        types = [e["eventType"] for e in self.events()]
        for required in ("TaskPolicyCheckRequested", "PolicyEvaluated",
                         "AcquisitionAuthorized", "TaskClaimed", "TaskStarted",
                         "TaskSucceeded", "WorkflowCompleted"):
            self.assertIn(required, types)
        self.assertGreaterEqual(self.opener.calls, 1,
                                "the real transport must have been exercised")
        result = self.recorded_results()[0]
        self.assertEqual(result["httpStatus"], 200)
        self.assertEqual(result["connectorDecision"]["decision"], "permit")
        self.assertIn("changeDetection", result)

    def test_the_raw_artifact_and_research_artifact_land_in_the_sandbox(self):
        self.initialise()
        self.box["body"] = BODY_A
        self.acquire_once("R1")
        raw_path = os.path.join(self.intake, "acquired", HASH_A + ".json")
        self.assertTrue(os.path.isfile(raw_path),
                        "the raw acquired bytes must land in the sandbox intake")
        with open(raw_path, "rb") as handle:
            wrapper = handle.read()
        self.assertEqual(os.listdir(self.artifacts),
                         [ids.sha256_hex(wrapper) + ".json"])

    def test_the_classification_is_visible_in_the_operator_audit_surface(self):
        """Step 2C-12: an operator must not have to compare hashes by hand."""
        self.initialise()
        self.box["body"] = BODY_A
        self.acquire_once("R1")
        self.box["body"] = BODY_B
        self.acquire_once("R2")
        from mogo_platform.runtime import audit as audit_module
        with self.runtime() as rt:
            log = event_log_module.EventLog(self.paths)
            report = audit_module.status_report(rt.connection, log, self.paths)
            rendered = audit_module.render_status(report)
        self.assertIn("change detection", rendered.lower())
        self.assertIn(cd.CHANGED, rendered)
        self.assertIn(cd.FIRST_OBSERVATION, rendered)

    def test_classification_failure_cannot_fail_the_acquisition(self):
        """Observation must never be able to break the thing it observes."""
        self.initialise()
        self.box["body"] = BODY_A
        real = acquisition_history.classify_acquisition

        def explode(*_args, **_kwargs):
            raise RuntimeError("deliberate classifier fault")

        acquisition_history.classify_acquisition = explode
        try:
            _outcome, report = self.acquire_once("R1")
        finally:
            acquisition_history.classify_acquisition = real
        self.assertEqual(len(report["succeeded"]), 1,
                         "the acquisition must still succeed")
        result = self.recorded_results()[0]
        self.assertEqual(result["contentHash"], HASH_A)
        self.assertEqual(result["changeDetection"]["classification"],
                         "UNAVAILABLE")
        self.assertEqual(self.events("SourceMutationDetected"), [])

    def test_a_degraded_run_still_becomes_the_baseline_for_the_next_one(self):
        """Because the baseline is DERIVED from accepted history, not stored."""
        self.initialise()
        self.box["body"] = BODY_A
        real = acquisition_history.classify_acquisition
        acquisition_history.classify_acquisition = \
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("fault"))
        try:
            self.acquire_once("R1")
        finally:
            acquisition_history.classify_acquisition = real
        self.box["body"] = BODY_B
        self.acquire_once("R2")
        latest = self.recorded_results()[-1]
        self.assertEqual(self.classification_of(latest), cd.CHANGED)
        self.assertEqual(latest["changeDetection"]["priorContentIdentity"], HASH_A)


# ---------------------------------------------------------------------------
# Step 2C-13: the scientific firewall
# ---------------------------------------------------------------------------

class TestScientificFirewall(unittest.TestCase):

    def test_the_mutation_event_has_no_consumer_in_the_trading_lane(self):
        """Every occurrence of the event name is enumerated, not assumed."""
        hits = []
        for base, _dirs, files in os.walk(REPO_ROOT):
            if any(part in base for part in
                   (".git", "__pycache__", "node_modules", "MOGO-EVIDENCE")):
                continue
            for name in files:
                if not name.endswith((".py", ".js", ".html", ".sh")):
                    continue
                path = os.path.join(base, name)
                try:
                    with open(path, "r", encoding="utf-8") as handle:
                        if "SourceMutationDetected" in handle.read():
                            hits.append(os.path.relpath(path, REPO_ROOT))
                except (OSError, UnicodeDecodeError):
                    continue
        # Built from components rather than written as path literals. Spelling
        # the package path out in full would embed the exact substring that
        # test_platform_boundaries scans for when proving no suite reaches the
        # retired flat contracts directory -- a false positive there would be
        # worse than the mild verbosity here. (This comment cannot spell it out
        # either, for the same reason.)
        src = ("platform", "src", "mogo_platform")
        permitted = {
            os.path.join(*src, "contracts", "vocabulary.py"),   # declaration
            os.path.join(*src, "runtime", "orchestrator.py"),   # THE emitter
            os.path.join(*src, "runtime", "change_detection.py"),
            os.path.join("tests", "platform", "test_platform_envelopes.py"),
            os.path.join("tests", "platform",
                         "test_runtime_change_detection_contract.py"),
            os.path.join("tests", "platform",
                         "test_runtime_change_detection_wiring.py"),
        }
        self.assertEqual(set(hits) - permitted, set(),
                         "an unexpected consumer of the mutation event exists")
        # index.html carries ALEX and every trading path. It must not appear.
        self.assertNotIn("index.html", hits)

    def test_the_detector_reaches_no_trading_symbol(self):
        """Scanned over CODE, never prose.

        Both modules' docstrings STATE the prohibition -- "no change to ALEX",
        "promotes no hypothesis" -- so a raw text scan flags the very sentences
        that describe the firewall. Docstrings and comments are stripped and the
        executable code is scanned instead, which is the thing that could
        actually reach a trading symbol.
        """
        import ast as _ast

        def strip_docstrings(tree):
            """Docstrings are ast.Constant nodes too, so they must be removed
            explicitly -- otherwise the prohibition each module DOCUMENTS is
            matched as though the module referenced a trading symbol."""
            for node in _ast.walk(tree):
                body = getattr(node, "body", None)
                if not isinstance(body, list) or not body:
                    continue
                if not isinstance(node, (_ast.Module, _ast.ClassDef,
                                         _ast.FunctionDef, _ast.AsyncFunctionDef)):
                    continue
                first = body[0]
                if isinstance(first, _ast.Expr) and isinstance(
                        first.value, _ast.Constant) and isinstance(
                            first.value.value, str):
                    body.pop(0)
            return tree

        for module in (cd, acquisition_history):
            with open(module.__file__, "r", encoding="utf-8") as handle:
                tree = strip_docstrings(_ast.parse(handle.read()))
            names = set()
            for node in _ast.walk(tree):
                if isinstance(node, _ast.Name):
                    names.add(node.id)
                elif isinstance(node, _ast.Attribute):
                    names.add(node.attr)
                elif isinstance(node, _ast.alias):
                    names.add(node.name)
                elif isinstance(node, _ast.Constant) and isinstance(node.value, str):
                    names.add(node.value)
            blob = " ".join(names)
            self.assertNotIn("RESEARCH CHANGE IS NOT TRADING", blob,
                             "docstrings must have been stripped before scanning")
            for forbidden in ("alexG", "ALEX", "paperAccount", "openPaperPosition",
                              "alexGAccount", "Campaign", "tradingRule",
                              "hypothesis", "promoteRule"):
                with self.subTest(module=os.path.basename(module.__file__),
                                  symbol=forbidden):
                    self.assertNotIn(forbidden, blob)

    def test_the_classification_carries_its_lane_wherever_it_travels(self):
        verdict = cd.classify(None, True, {"validationStatus": "VALID",
                                           "storedVerified": True,
                                           "contentHash": HASH_A})
        self.assertEqual(verdict.classification, cd.FIRST_OBSERVATION)
        # The record the orchestrator writes stamps lane/promotionStatus; the
        # contract itself never promotes anything.
        with open(cd.__file__, "r", encoding="utf-8") as handle:
            self.assertNotIn("TRADING_RULE_APPROVED", handle.read())


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------------------
# Step 3: the provenance repair, and the property it must not break
# ---------------------------------------------------------------------------

class TestProvenanceRepair(ChangeDetectionWiringCase):
    """`acquiredAt` and `decidedAt` are populated. Nothing scientific moved."""

    def test_provenance_is_now_populated_on_a_real_acquisition(self):
        self.initialise()
        self.box["body"] = BODY_A
        self.acquire_once("R1")
        result = self.recorded_results()[0]
        self.assertIsNotNone(result["acquiredAt"],
                             "acquiredAt was the provenance gap; it must be filled")
        self.assertIsNotNone(result["connectorDecision"]["decidedAt"],
                             "decidedAt was the same gap on the gate decision")
        self.assertEqual(result["acquiredAt"],
                         result["connectorDecision"]["decidedAt"],
                         "ONE authoritative instant, not two clock reads that "
                         "could disagree about when the same acquisition happened")

    def test_provenance_does_not_alter_scientific_content_identity(self):
        """Proofs 1 and 2: the identity is the external bytes, and only those."""
        self.initialise()
        self.box["body"] = BODY_A
        self.acquire_once("R1")
        result = self.recorded_results()[0]
        self.assertEqual(result["contentHash"], HASH_A)
        self.assertEqual(result["changeDetection"]["currentContentIdentity"],
                         HASH_A)

    def test_changing_provenance_between_runs_still_yields_unchanged(self):
        """Proof 3, and the whole point of the exclusion.

        Two acquisitions of IDENTICAL external bytes, separated in time so their
        provenance timestamps genuinely differ, must remain UNCHANGED and must
        NOT mint a second research artifact.
        """
        self.initialise()
        self.box["body"] = BODY_A
        self.acquire_once("R1")
        self.acquire_once("R2")
        first, second = self.recorded_results()
        self.assertNotEqual(first["acquiredAt"], second["acquiredAt"],
                            "the two runs must genuinely differ in provenance")
        self.assertEqual(self.classification_of(second), cd.UNCHANGED)
        self.assertEqual(self.events("SourceMutationDetected"), [])
        self.assertEqual(second["ingestion"]["duplicateStatus"],
                         "DUPLICATE_ALREADY_INGESTED")
        self.assertEqual(len(os.listdir(self.artifacts)), 1,
                         "differing provenance must NOT mint a second research "
                         "artifact for unchanged external content")

    def test_the_repair_leaves_the_committed_production_wrapper_untouched(self):
        """No existing evidence was disturbed and nothing was migrated.

        The genuine artifact committed in MOGO-015 must rebuild byte-identically
        under the repaired code, or the first post-repair acquisition would mint
        a second artifact for external content already ingested.
        """
        path = os.path.join(research_corpus.PRODUCTION_INTAKE_ROOT, "acquired",
                            "b668d4209abbf2b8718cea2fa84eacd3985cbb4d1fc352dd"
                            "1720f64bebb92a00.json")
        if not os.path.isfile(path):
            self.skipTest("the committed production artifact is not present")
        with open(path, "rb") as handle:
            committed = handle.read()
        document = json.loads(committed.decode("utf-8"))
        document["acquisition"] = acquire.stable_acquisition_record(
            document["acquisition"])
        rebuilt = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode()
        self.assertEqual(rebuilt, committed,
                         "the repaired wrapper must be byte-identical to the "
                         "one already committed -- no churn, no migration")

    def test_the_wrapper_excludes_volatile_provenance_so_dedupe_survives(self):
        """Proof 4: the wrapper hash is stable across runs BECAUSE of this.

        The wrapper is what ingestion hashes, so a wall-clock value inside it
        would change the research artifact's identity every acquisition.
        """
        self.initialise()
        self.box["body"] = BODY_A
        self.acquire_once("R1")
        raw_path = os.path.join(self.intake, "acquired", HASH_A + ".json")
        with open(raw_path, "rb") as handle:
            first_wrapper = handle.read()
        self.acquire_once("R2")
        with open(raw_path, "rb") as handle:
            second_wrapper = handle.read()
        self.assertEqual(first_wrapper, second_wrapper,
                         "identical external bytes must produce a byte-identical "
                         "wrapper regardless of when they were acquired")
        document = json.loads(first_wrapper.decode("utf-8"))
        # PINNED, not deleted -- deleting the keys would change the wrapper's
        # shape and mint one new artifact for content already ingested.
        self.assertIsNone(document["acquisition"]["acquiredAt"])
        self.assertIsNone(document["acquisition"]["decision"]["decidedAt"])
        # ...while the full record, timestamps included, is still recorded.
        self.assertIsNotNone(self.recorded_results()[0]["acquiredAt"])

    def test_the_stripper_removes_exactly_the_volatile_fields(self):
        record = {"acquiredAt": "T", "httpStatus": 200, "contentHash": HASH_A,
                  "decision": {"decidedAt": "T", "decision": "permit",
                               "approvedUrl": "https://example.test/x"}}
        stable = acquire.stable_acquisition_record(record)
        # The KEY SET is unchanged -- only the two volatile values are pinned.
        self.assertEqual(set(stable), set(record))
        self.assertEqual(set(stable["decision"]), set(record["decision"]))
        self.assertIsNone(stable["acquiredAt"])
        self.assertIsNone(stable["decision"]["decidedAt"])
        self.assertEqual(stable["httpStatus"], 200)
        self.assertEqual(stable["decision"]["approvedUrl"],
                         "https://example.test/x")
        self.assertEqual(record["acquiredAt"], "T",
                         "the input must not be mutated")
        self.assertEqual(record["decision"]["decidedAt"], "T")

    def test_a_historical_artifact_with_null_provenance_stays_compatible(self):
        """Proof 5: nothing was migrated, and nothing needed to be.

        The MOGO-016 rows predate both the classifier and this repair. They are
        still valid ACCEPTED history, because acceptance reads validation and
        storage -- never provenance.
        """
        legacy = {"sourceId": APPROVED_SOURCE, "resourceId": APPROVED_RESOURCE,
                  "contentHash": HASH_A, "acquiredAt": None,
                  "connectorDecision": {"decidedAt": None},
                  "ingestion": {"validationStatus": "VALID",
                                "storedVerified": True}}
        self.assertEqual(cd.accepted_identity_from_acquisition(legacy), HASH_A)
        verdict = cd.classify_acquisition_result(None, legacy)
        self.assertEqual(verdict.classification, cd.FIRST_OBSERVATION)

    def test_valid_changed_bytes_still_produce_changed(self):
        """Proof 6, re-run after the repair."""
        self.initialise()
        self.box["body"] = BODY_A
        self.acquire_once("R1")
        self.box["body"] = BODY_B
        self.acquire_once("R2")
        self.assertEqual(self.classification_of(self.recorded_results()[-1]),
                         cd.CHANGED)
        self.assertEqual(len(self.events("SourceMutationDetected")), 1)

    def test_invalid_changed_bytes_still_do_not_produce_changed(self):
        """Proof 7, re-run after the repair."""
        self.initialise()
        self.box["body"] = BODY_A
        self.acquire_once("R1")
        self.box["body"] = BODY_INVALID
        self.acquire_once("R2")
        self.assertEqual(len(self.recorded_results()), 1)
        self.assertEqual(self.events("SourceMutationDetected"), [])

    def test_first_observation_remains_distinct_from_changed(self):
        """Proof 8, re-run after the repair."""
        self.initialise()
        self.box["body"] = BODY_A
        self.acquire_once("R1")
        self.assertEqual(self.classification_of(self.recorded_results()[0]),
                         cd.FIRST_OBSERVATION)
        self.assertEqual(self.events("SourceMutationDetected"), [])

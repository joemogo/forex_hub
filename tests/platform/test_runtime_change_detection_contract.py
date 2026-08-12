#!/usr/bin/env python3
"""MOGO-017 Step 2B -- the change-detection CONTRACT and its isolation boundary.

Two properties are under test, and neither is "the classifier returns sensible
values":

  * NOTHING THAT FAILED CAN BECOME THE BASELINE. A failed acquisition, a failed
    validation, and -- the subtle one -- bytes that genuinely CHANGED but failed
    validation must all leave the previous accepted identity exactly where it
    was. Otherwise one truncated or hostile response silently redefines what the
    source says, and the next genuine acquisition reads as a mutation.

  * A SYNTHETIC FIXTURE CANNOT REACH THE GENUINE RESEARCH CORPUS. Not "does not"
    -- CANNOT. sandbox_corpus() refuses to construct a corpus that overlaps the
    real one, so the fixtures below are physically unable to write there, and
    that is asserted rather than assumed.

The production detector does not exist yet and is not tested here. Nothing in
the running system imports change_detection, which a fixture below pins.
"""

import ast
import json
import os
import shutil
import sys
import tempfile
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "platform", "src"))

from mogo_platform.contracts import ids                              # noqa: E402
from mogo_platform.runtime import change_detection as cd             # noqa: E402
from mogo_platform.runtime import connector_transport as transport   # noqa: E402
from mogo_platform.runtime import errors as runtime_errors           # noqa: E402
from mogo_platform.runtime import research_corpus                    # noqa: E402
from mogo_platform.runtime.capabilities import ingest_local_artifact as ingest  # noqa: E402

APPROVED_SOURCE = "SRC|youtube|c785970cc458"
APPROVED_RESOURCE = "hb7ot1_szWI"

# Two fixed, distinguishable bodies. Deliberately shaped so no genuine oEmbed
# response could be mistaken for either, and so a stray artifact would be
# obviously synthetic rather than plausibly real.
BODY_A = b'{"mogoFixture":"step2b-A","title":"FIXTURE A","n":1}'
BODY_B = b'{"mogoFixture":"step2b-B","title":"FIXTURE B","n":2}'


def read_text(path):
    """Read a source file for a static assertion, closing it deterministically.

    unittest surfaces an unclosed handle as a ResourceWarning, and a suite that
    emits warnings trains a reader to ignore them.
    """
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def ok_ingestion(content_hash, **over):
    result = {"validationStatus": "VALID", "storedVerified": True,
              "contentHash": content_hash, "ingested": True,
              "duplicateStatus": "NEW"}
    result.update(over)
    return result


# ---------------------------------------------------------------------------
# Content identity -- what is actually hashed
# ---------------------------------------------------------------------------

class TestContentIdentityIsTheRawExternalBytes(unittest.TestCase):
    """Proof 1, 2 and 3."""

    def test_it_is_sha256_over_the_exact_bytes(self):
        import hashlib
        self.assertEqual(transport.content_hash(BODY_A),
                         hashlib.sha256(BODY_A).hexdigest())
        self.assertTrue(ids.is_sha256_hex(transport.content_hash(BODY_A)))

    def test_identical_bytes_under_different_request_identities_are_identical(self):
        """Proof 1. Request identity is not content identity."""
        first = transport.content_hash(BODY_A)
        for _ in range(5):
            self.assertEqual(transport.content_hash(bytes(BODY_A)), first)

    def test_genuinely_different_bytes_produce_different_identities(self):
        """Proof 3."""
        self.assertNotEqual(transport.content_hash(BODY_A),
                            transport.content_hash(BODY_B))

    def test_one_flipped_byte_changes_the_identity(self):
        mutated = bytearray(BODY_A)
        mutated[-2] = mutated[-2] ^ 0x01
        self.assertNotEqual(transport.content_hash(BODY_A),
                            transport.content_hash(bytes(mutated)))

    def test_no_volatile_metadata_participates_in_the_hash(self):
        """Proof 2, asserted against the source rather than by inference.

        content_hash takes ONE argument -- the bytes -- so no timestamp, header,
        URL, request id or acquisition record can reach it.
        """
        source = ast.parse(read_text(transport.__file__))
        found = None
        for node in ast.walk(source):
            if isinstance(node, ast.FunctionDef) and node.name == "content_hash":
                found = node
        self.assertIsNotNone(found, "content_hash must exist to be pinned")
        args = [a.arg for a in found.args.args]
        self.assertEqual(args, ["raw"])
        self.assertEqual(found.args.kwonlyargs, [])
        self.assertIsNone(found.args.vararg)
        self.assertIsNone(found.args.kwarg)

    def test_the_body_is_hashed_not_a_json_reserialization(self):
        """The transport parses the body only to VALIDATE it and discards the
        result, so key order and whitespace are preserved in the identity."""
        compact = b'{"a":1,"b":2}'
        spaced = b'{"a": 1, "b": 2}'
        reordered = b'{"b":2,"a":1}'
        self.assertEqual(json.loads(compact), json.loads(spaced))
        self.assertEqual(json.loads(compact), json.loads(reordered))
        self.assertNotEqual(transport.content_hash(compact),
                            transport.content_hash(spaced))
        self.assertNotEqual(transport.content_hash(compact),
                            transport.content_hash(reordered))

    def test_the_artifact_wrapper_hash_is_a_different_number_and_is_not_used(self):
        """The reason the contract names the raw hash explicitly.

        MOGO-017 Step 3 populated acquiredAt/decidedAt. This fixture is the
        measurement that decided HOW: writing them into the wrapper would change
        its hash on every acquisition, so unchanged content would mint a new
        research artifact every six hours. The repair therefore excludes exactly
        those two fields from the wrapper and keeps them on the full record.

        The assertion below is unchanged and still true -- it is precisely the
        hazard the exclusion avoids.
        """
        raw_identity = transport.content_hash(BODY_A)
        wrapper_now = ids.content_hash_of(
            {"rawContent": BODY_A.decode("utf-8"),
             "acquisition": {"acquiredAt": None}})
        wrapper_later = ids.content_hash_of(
            {"rawContent": BODY_A.decode("utf-8"),
             "acquisition": {"acquiredAt": "2026-08-11T23:24:07.921Z"}})
        self.assertNotEqual(wrapper_now, wrapper_later,
                            "a populated acquiredAt must change the wrapper hash "
                            "-- this is exactly the trap the contract avoids")
        self.assertEqual(raw_identity, transport.content_hash(BODY_A),
                         "the raw identity is unaffected by that field entirely")
        self.assertNotEqual(raw_identity, wrapper_now)


# ---------------------------------------------------------------------------
# Same-source identity
# ---------------------------------------------------------------------------

class TestComparisonStreamPartitioning(unittest.TestCase):
    """Proof 4."""

    def test_the_key_is_source_and_resource(self):
        self.assertEqual(cd.comparison_key(APPROVED_SOURCE, APPROVED_RESOURCE),
                         (APPROVED_SOURCE, APPROVED_RESOURCE))

    def test_two_resources_under_one_source_are_different_streams(self):
        self.assertNotEqual(cd.comparison_key(APPROVED_SOURCE, APPROVED_RESOURCE),
                            cd.comparison_key(APPROVED_SOURCE, "dQw4w9WgXcQ"))

    def test_two_sources_are_different_streams(self):
        self.assertNotEqual(cd.comparison_key(APPROVED_SOURCE, APPROVED_RESOURCE),
                            cd.comparison_key("SRC|web|0123456789ab", APPROVED_RESOURCE))

    def test_the_key_is_a_tuple_so_no_separator_can_be_smuggled_in(self):
        """A joined string would let a crafted identifier collide two streams."""
        key = cd.comparison_key(APPROVED_SOURCE, APPROVED_RESOURCE)
        self.assertIsInstance(key, tuple)
        self.assertEqual(len(key), 2)

    def test_a_missing_or_malformed_identity_is_refused(self):
        for source, resource in (
                (None, APPROVED_RESOURCE), ("", APPROVED_RESOURCE),
                ("not-a-source-id", APPROVED_RESOURCE),
                (APPROVED_SOURCE, None), (APPROVED_SOURCE, ""),
                (APPROVED_SOURCE, "   ")):
            with self.subTest(source=source, resource=resource):
                with self.assertRaises(runtime_errors.PlatformError):
                    cd.comparison_key(source, resource)


# ---------------------------------------------------------------------------
# Accepted content
# ---------------------------------------------------------------------------

class TestAcceptedContent(unittest.TestCase):

    def setUp(self):
        self.hash_a = transport.content_hash(BODY_A)

    def test_a_successful_validated_stored_acquisition_is_accepted(self):
        self.assertEqual(
            cd.accepted_content_identity(True, ok_ingestion(self.hash_a)),
            self.hash_a)

    def test_a_duplicate_is_still_accepted_content(self):
        """`ingested=false` means storage was a no-op, not that content failed.

        Requiring `ingested` would make every UNCHANGED observation -- the normal
        case for a stable source -- look like a failure.
        """
        self.assertEqual(
            cd.accepted_content_identity(True, ok_ingestion(
                self.hash_a, ingested=False,
                duplicateStatus="DUPLICATE_ALREADY_INGESTED")),
            self.hash_a)

    def test_a_failed_acquisition_is_never_accepted(self):
        self.assertIsNone(
            cd.accepted_content_identity(False, ok_ingestion(self.hash_a)))

    def test_unvalidated_content_is_never_accepted(self):
        for over in ({"validationStatus": "INVALID"},
                     {"validationStatus": None},
                     {"validationStatus": "valid"}):     # case matters
            with self.subTest(over=over):
                self.assertIsNone(cd.accepted_content_identity(
                    True, ok_ingestion(self.hash_a, **over)))

    def test_unverified_storage_is_never_accepted(self):
        for over in ({"storedVerified": False}, {"storedVerified": None}):
            with self.subTest(over=over):
                self.assertIsNone(cd.accepted_content_identity(
                    True, ok_ingestion(self.hash_a, **over)))

    def test_a_malformed_or_absent_content_hash_is_never_accepted(self):
        for value in (None, "", "not-a-hash", "abc", 17, self.hash_a[:-1]):
            with self.subTest(value=value):
                self.assertIsNone(cd.accepted_content_identity(
                    True, ok_ingestion(self.hash_a, contentHash=value)))

    def test_a_non_mapping_ingestion_result_is_never_accepted(self):
        for value in (None, [], "VALID", 0):
            with self.subTest(value=value):
                self.assertIsNone(cd.accepted_content_identity(True, value))


# ---------------------------------------------------------------------------
# The classification ladder
# ---------------------------------------------------------------------------

class TestClassificationSemantics(unittest.TestCase):
    """Proofs 5, 6, 7 and 8."""

    def setUp(self):
        self.hash_a = transport.content_hash(BODY_A)
        self.hash_b = transport.content_hash(BODY_B)

    def test_first_observation_when_there_is_no_prior(self):
        verdict = cd.classify(None, True, ok_ingestion(self.hash_a))
        self.assertEqual(verdict.classification, cd.FIRST_OBSERVATION)
        self.assertIsNone(verdict.priorContentIdentity)
        self.assertEqual(verdict.currentContentIdentity, self.hash_a)
        self.assertTrue(verdict.advancesBaseline)

    def test_first_observation_is_semantically_distinct_from_changed(self):
        """Proof 8. A source's first ever observation is not a mutation."""
        first = cd.classify(None, True, ok_ingestion(self.hash_a))
        changed = cd.classify(self.hash_a, True, ok_ingestion(self.hash_b))
        self.assertNotEqual(first.classification, changed.classification)
        self.assertEqual(first.classification, cd.FIRST_OBSERVATION)
        self.assertEqual(changed.classification, cd.CHANGED)
        self.assertIsNone(first.priorContentIdentity)
        self.assertIsNotNone(changed.priorContentIdentity)

    def test_unchanged_when_the_identity_matches(self):
        verdict = cd.classify(self.hash_a, True, ok_ingestion(self.hash_a))
        self.assertEqual(verdict.classification, cd.UNCHANGED)
        self.assertEqual(verdict.priorContentIdentity, self.hash_a)
        self.assertEqual(verdict.currentContentIdentity, self.hash_a)

    def test_a_fresh_request_returning_identical_content_is_unchanged(self):
        """A new request identity does not make a new observation a change."""
        verdict = cd.classify(self.hash_a, True, ok_ingestion(
            self.hash_a, ingested=False,
            duplicateStatus="DUPLICATE_ALREADY_INGESTED"))
        self.assertEqual(verdict.classification, cd.UNCHANGED)

    def test_changed_when_the_identity_differs(self):
        verdict = cd.classify(self.hash_a, True, ok_ingestion(self.hash_b))
        self.assertEqual(verdict.classification, cd.CHANGED)
        self.assertEqual(verdict.priorContentIdentity, self.hash_a)
        self.assertEqual(verdict.currentContentIdentity, self.hash_b)

    def test_changed_preserves_both_identities_for_audit(self):
        record = cd.classify(self.hash_a, True, ok_ingestion(self.hash_b)).as_record()
        self.assertEqual(record["priorContentIdentity"], self.hash_a)
        self.assertEqual(record["currentContentIdentity"], self.hash_b)
        self.assertEqual(record["classification"], cd.CHANGED)

    def test_acquisition_failure_cannot_become_accepted_state(self):
        """Proof 5."""
        verdict = cd.classify(self.hash_a, False, ok_ingestion(self.hash_b))
        self.assertEqual(verdict.classification, cd.ACQUISITION_FAILURE)
        self.assertFalse(verdict.advancesBaseline)
        self.assertEqual(cd.next_baseline(self.hash_a, verdict), self.hash_a)

    def test_validation_failure_cannot_become_accepted_state(self):
        """Proof 6."""
        verdict = cd.classify(self.hash_a, True,
                              ok_ingestion(self.hash_b, validationStatus="INVALID"))
        self.assertEqual(verdict.classification, cd.VALIDATION_FAILURE)
        self.assertFalse(verdict.advancesBaseline)
        self.assertEqual(cd.next_baseline(self.hash_a, verdict), self.hash_a)

    def test_changed_bytes_that_fail_validation_cannot_become_accepted_state(self):
        """Proof 7 -- the one most likely to be got wrong.

        The bytes genuinely differ from the baseline. They are still NOT a
        mutation, because they never became accepted content, so no legitimate
        comparison was ever available. The baseline must not move.
        """
        for over in ({"validationStatus": "INVALID"},
                     {"storedVerified": False},
                     {"contentHash": None}):
            with self.subTest(over=over):
                verdict = cd.classify(self.hash_a, True,
                                      ok_ingestion(self.hash_b, **over))
                self.assertEqual(verdict.classification, cd.VALIDATION_FAILURE)
                self.assertNotEqual(verdict.classification, cd.CHANGED)
                self.assertFalse(verdict.advancesBaseline)
                self.assertEqual(cd.next_baseline(self.hash_a, verdict), self.hash_a)

    def test_a_failure_never_reports_a_current_identity(self):
        for ok, ingestion in ((False, ok_ingestion(self.hash_b)),
                              (True, ok_ingestion(self.hash_b, storedVerified=False))):
            with self.subTest(ok=ok):
                self.assertIsNone(cd.classify(self.hash_a, ok, ingestion)
                                  .currentContentIdentity)

    def test_the_baseline_advances_only_on_accepted_content(self):
        first = cd.classify(None, True, ok_ingestion(self.hash_a))
        self.assertEqual(cd.next_baseline(None, first), self.hash_a)
        changed = cd.classify(self.hash_a, True, ok_ingestion(self.hash_b))
        self.assertEqual(cd.next_baseline(self.hash_a, changed), self.hash_b)
        unchanged = cd.classify(self.hash_b, True, ok_ingestion(self.hash_b))
        self.assertEqual(cd.next_baseline(self.hash_b, unchanged), self.hash_b)

    def test_a_full_sequence_behaves_as_the_contract_states(self):
        """FIRST -> UNCHANGED -> CHANGED -> failure (no move) -> UNCHANGED."""
        baseline = None
        seen = []
        steps = ((True, self.hash_a, None), (True, self.hash_a, None),
                 (True, self.hash_b, None), (False, self.hash_a, None),
                 (True, self.hash_b, None))
        for ok, digest, _ in steps:
            verdict = cd.classify(baseline, ok, ok_ingestion(digest))
            seen.append(verdict.classification)
            baseline = cd.next_baseline(baseline, verdict)
        self.assertEqual(seen, [cd.FIRST_OBSERVATION, cd.UNCHANGED, cd.CHANGED,
                                cd.ACQUISITION_FAILURE, cd.UNCHANGED])
        self.assertEqual(baseline, self.hash_b,
                         "the failure must not have moved the baseline")

    def test_a_malformed_prior_baseline_is_refused_rather_than_compared(self):
        with self.assertRaises(runtime_errors.PlatformError):
            cd.classify("not-a-hash", True, ok_ingestion(self.hash_a))

    def test_the_classification_set_is_closed_and_partitioned(self):
        self.assertEqual(set(cd.CLASSIFICATIONS),
                         set(cd.BASELINE_ADVANCING) | set(cd.BASELINE_PRESERVING))
        self.assertEqual(set(cd.BASELINE_ADVANCING) & set(cd.BASELINE_PRESERVING),
                         set())

    def test_source_mutated_is_not_used_as_a_failure_class(self):
        """A mutation is information, not an execution failure."""
        source = read_text(cd.__file__)
        code = "\n".join(line for line in source.splitlines()
                         if not line.strip().startswith("#"))
        body = code.split('"""', 2)[-1]
        self.assertNotIn("source_mutated", body)


# ---------------------------------------------------------------------------
# Synthetic test isolation
# ---------------------------------------------------------------------------

class TestResearchCorpusIsolation(unittest.TestCase):
    """Proofs 9, 10 and 11."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="mogo-2b-")
        self.intake = os.path.join(self.tmp, "intake")
        self.artifacts = os.path.join(self.tmp, "research-artifacts")
        os.makedirs(os.path.join(self.intake, "acquired"))
        os.makedirs(self.artifacts)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def sandbox(self):
        return research_corpus.sandbox_corpus(self.intake, self.artifacts)

    # -- production defaults ------------------------------------------------

    def test_production_defaults_are_unchanged(self):
        """Proof 10. The seam must not have moved the real corpus."""
        production = research_corpus.production_corpus()
        self.assertTrue(production.production)
        self.assertEqual(production.intakeRoot,
                         os.path.join(REPO_ROOT, "docs", "trader-intelligence",
                                      "intake"))
        self.assertEqual(production.artifactRoot,
                         os.path.join(REPO_ROOT, "docs", "trader-intelligence",
                                      "research-artifacts"))

    def test_the_capability_constants_still_name_the_production_roots(self):
        self.assertEqual(ingest.INTAKE_ROOT,
                         research_corpus.PRODUCTION_INTAKE_ROOT)
        self.assertEqual(ingest.ARTIFACT_ROOT,
                         research_corpus.PRODUCTION_ARTIFACT_ROOT)

    def test_omitting_the_corpus_resolves_to_production(self):
        """`corpus=None` must mean exactly one thing, everywhere."""
        resolved = research_corpus.resolve_corpus(None)
        self.assertTrue(resolved.production)
        self.assertEqual(resolved.artifactRoot,
                         research_corpus.PRODUCTION_ARTIFACT_ROOT)

    def test_no_environment_variable_can_redirect_the_corpus(self):
        """A variable that can silently move evidence is one that will."""
        source = read_text(research_corpus.__file__)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                self.assertNotEqual(node.attr, "environ")
            if isinstance(node, ast.Name):
                self.assertNotEqual(node.id, "getenv")

    # -- fail closed --------------------------------------------------------

    def test_a_sandbox_overlapping_the_real_corpus_is_refused(self):
        """Proof 11. The dangerous mistake is believing you are sandboxed."""
        real_intake = research_corpus.PRODUCTION_INTAKE_ROOT
        real_artifacts = research_corpus.PRODUCTION_ARTIFACT_ROOT
        unsafe = (
            (real_intake, self.artifacts),
            (self.intake, real_artifacts),
            (real_intake, real_artifacts),
            (os.path.join(real_intake, "acquired"), self.artifacts),
            (self.intake, os.path.join(real_artifacts, "nested")),
            (os.path.dirname(real_artifacts), self.artifacts),
            (os.path.join(real_artifacts, "..", "research-artifacts"), self.artifacts),
        )
        for intake, artifacts in unsafe:
            with self.subTest(intake=intake, artifacts=artifacts):
                with self.assertRaises(runtime_errors.PlatformError):
                    research_corpus.sandbox_corpus(intake, artifacts)

    def test_a_relative_sandbox_root_is_refused(self):
        with self.assertRaises(runtime_errors.PlatformError):
            research_corpus.sandbox_corpus("relative/intake", self.artifacts)

    def test_an_empty_or_absent_sandbox_root_is_refused(self):
        for intake in (None, "", "   ", 17):
            with self.subTest(intake=intake):
                with self.assertRaises(runtime_errors.PlatformError):
                    research_corpus.sandbox_corpus(intake, self.artifacts)

    def test_a_sandbox_whose_two_roots_overlap_is_refused(self):
        with self.assertRaises(runtime_errors.PlatformError):
            research_corpus.sandbox_corpus(self.tmp, self.artifacts)

    def test_a_non_corpus_object_is_refused(self):
        for value in ("/tmp", {"artifactRoot": "/tmp"}, 17):
            with self.subTest(value=value):
                with self.assertRaises(runtime_errors.PlatformError):
                    research_corpus.resolve_corpus(value)

    # -- the real ingestion path, sandboxed ---------------------------------

    def write_intake(self, name, body):
        path = os.path.join(self.intake, "acquired", name)
        with open(path, "wb") as handle:
            handle.write(body)
        return "acquired/" + name

    def test_the_real_ingestion_path_writes_only_inside_the_sandbox(self):
        """Proof 9. The REAL capability runs; the genuine corpus is untouched."""
        before = sorted(os.listdir(research_corpus.PRODUCTION_ARTIFACT_ROOT))
        ref = self.write_intake("fixture-a.json", BODY_A)
        result = ingest.execute({"artifactRef": ref, "sourceId": APPROVED_SOURCE},
                                corpus=self.sandbox())
        self.assertEqual(result["validationStatus"], "VALID")
        self.assertTrue(result["storedVerified"])
        self.assertTrue(result["ingested"])
        written = os.listdir(self.artifacts)
        self.assertEqual(written, [result["contentHash"] + ".json"])
        self.assertEqual(sorted(os.listdir(research_corpus.PRODUCTION_ARTIFACT_ROOT)),
                         before, "the genuine research corpus must be untouched")

    def test_a_sandboxed_ingestion_produces_the_accepted_identity(self):
        """The seam and the contract agree: the real path yields the raw hash of
        the intake file, which is what the classifier consumes."""
        ref = self.write_intake("fixture-a.json", BODY_A)
        result = ingest.execute({"artifactRef": ref, "sourceId": APPROVED_SOURCE},
                                corpus=self.sandbox())
        self.assertEqual(result["contentHash"], ids.sha256_hex(BODY_A))
        self.assertEqual(cd.accepted_content_identity(True, result),
                         ids.sha256_hex(BODY_A))

    def test_a_sandboxed_change_sequence_classifies_correctly(self):
        """FIRST -> UNCHANGED -> CHANGED, driven by the REAL ingestion path."""
        corpus = self.sandbox()
        baseline = None
        seen = []
        for name, body in (("a1.json", BODY_A), ("a2.json", BODY_A),
                           ("b1.json", BODY_B)):
            ref = self.write_intake(name, body)
            result = ingest.execute(
                {"artifactRef": ref, "sourceId": APPROVED_SOURCE}, corpus=corpus)
            verdict = cd.classify(baseline, True, result)
            seen.append(verdict.classification)
            baseline = cd.next_baseline(baseline, verdict)
        self.assertEqual(seen, [cd.FIRST_OBSERVATION, cd.UNCHANGED, cd.CHANGED])
        self.assertEqual(baseline, ids.sha256_hex(BODY_B))
        self.assertEqual(len(os.listdir(self.artifacts)), 2,
                         "identical content must not create a second artifact")

    def test_invalid_bytes_are_refused_by_the_real_validator_in_the_sandbox(self):
        """Changed-but-invalid, end to end: ingestion refuses, so no identity
        exists and the baseline cannot move."""
        ref = self.write_intake("empty.json", b"")
        with self.assertRaises(runtime_errors.PlatformError):
            ingest.execute({"artifactRef": ref, "sourceId": APPROVED_SOURCE},
                           corpus=self.sandbox())
        baseline = ids.sha256_hex(BODY_A)
        verdict = cd.classify(baseline, True, None)
        self.assertEqual(verdict.classification, cd.VALIDATION_FAILURE)
        self.assertEqual(cd.next_baseline(baseline, verdict), baseline)

    def test_the_sandbox_confinement_rule_is_as_strict_as_production(self):
        """A sandbox must not be a hole in the traversal check."""
        for hostile in ("../escape.json", "/etc/passwd", "acquired/../../x.json"):
            with self.subTest(ref=hostile):
                with self.assertRaises(runtime_errors.PlatformError):
                    ingest.resolve_intake_path(hostile, self.sandbox())


# ---------------------------------------------------------------------------
# The contract is not wired to production
# ---------------------------------------------------------------------------

class TestTheDetectorIsNotYetWired(unittest.TestCase):

    RUNTIME_DIR = os.path.join(REPO_ROOT, "platform", "src", "mogo_platform",
                               "runtime")

    def test_only_the_named_seams_import_change_detection(self):
        """Step 2B froze the contract and asserted NOTHING imported it.

        MOGO-017 Step 2C wired it, so this assertion had to be edited -- in a
        commit, with a reason -- rather than quietly starting to pass. That is
        the whole point of having written it as a hard emptiness check.

        It is now an ALLOW-LIST rather than a prohibition, so a THIRD consumer
        still breaks the test. The contract is meant to have exactly two callers:
        the history lookup that supplies its argument, and the orchestrator that
        acts on its verdict.
        """
        # MOGO-018 added research_library.py, which REUSES the acceptance
        # predicate rather than restating it -- so the library and the detector
        # can never disagree about what counts as accepted content. Still an
        # allow-list: a fourth consumer breaks this test.
        permitted = {"acquisition_history.py", "orchestrator.py",
                     "research_library.py"}
        importers = set()
        for root, _dirs, files in os.walk(self.RUNTIME_DIR):
            if "__pycache__" in root:
                continue
            for name in files:
                if not name.endswith(".py") or name == "change_detection.py":
                    continue
                # Real IMPORTS, via the AST -- not a substring scan. audit.py
                # legitimately reads the recorded `changeDetection` field and
                # names a helper after it WITHOUT importing the contract, and
                # conflating "mentions the words" with "depends on the module"
                # would make this assertion mean something weaker than it says.
                tree = ast.parse(read_text(os.path.join(root, name)))
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom):
                        if any(a.name == "change_detection" for a in node.names):
                            importers.add(name)
                    elif isinstance(node, ast.Import):
                        if any(a.name.endswith("change_detection")
                               for a in node.names):
                            importers.add(name)
        self.assertEqual(importers, permitted)

    def test_no_capability_imports_change_detection(self):
        """Classification is the ORCHESTRATOR's job, not a capability's.

        A capability receives {attempt, taskId, leaseGeneration} and NO database
        handle, so it cannot read history -- and widening that boundary to let it
        would be a far larger change than this milestone permits.
        """
        capability_dir = os.path.join(self.RUNTIME_DIR, "capabilities")
        for name in sorted(os.listdir(capability_dir)):
            if not name.endswith(".py"):
                continue
            with self.subTest(capability=name):
                self.assertNotIn("change_detection",
                                 read_text(os.path.join(capability_dir, name)))

    def test_change_detection_performs_no_io_and_reads_no_clock(self):
        tree = ast.parse(read_text(cd.__file__))
        called = set()
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
            elif isinstance(node, ast.Call):
                target = node.func
                if isinstance(target, ast.Name):
                    called.add(target.id)
                elif isinstance(target, ast.Attribute):
                    called.add(target.attr)
        for banned in ("socket", "ssl", "http", "urllib", "sqlite3", "time",
                       "datetime", "random", "subprocess", "os"):
            with self.subTest(module=banned):
                self.assertNotIn(banned, imported)
        for banned in ("open", "now", "utcnow", "time", "execute", "emit"):
            with self.subTest(call=banned):
                self.assertNotIn(banned, called)

    def test_the_event_type_is_already_approved_and_needs_no_contract_change(self):
        """Step 1 flagged a manifest-hash risk. This is the resolution."""
        from mogo_platform.contracts import vocabulary
        self.assertIn("SourceMutationDetected", vocabulary.EVENT_TYPES)

    def test_orchestrator_produced_events_need_no_manifest_declaration(self):
        """The smallest future-safe emitter, established by precedent.

        Every capability manifest declares only TaskSucceeded/TaskFailed, yet the
        orchestrator already emits the whole acquisition lifecycle --
        PolicyEvaluated, AcquisitionAuthorized, AcquisitionDenied -- and none of
        those appears in any manifest. `emittedEvents` is stored at registration
        and never consulted at emit time, so emitting SourceMutationDetected from
        the ORCHESTRATOR needs no manifest edit, no capabilityId bump, and no
        weakening of registration validation.

        Emitting it from the CAPABILITY would instead require changing its
        manifest, which changes its hash, which register() refuses under an
        unchanged capabilityId -- by design.
        """
        from mogo_platform.runtime import orchestrator as orch
        capability_dir = os.path.join(self.RUNTIME_DIR, "capabilities")
        declared = set()
        for manifest in orch.BUILTIN_CAPABILITIES:
            declared.update(manifest["emittedEvents"])
        self.assertEqual(declared, {"TaskSucceeded", "TaskFailed"})
        for lifecycle in ("PolicyEvaluated", "AcquisitionAuthorized",
                          "AcquisitionDenied"):
            with self.subTest(event=lifecycle):
                self.assertNotIn(lifecycle, declared)
                self.assertIn(lifecycle,
                              read_text(os.path.join(self.RUNTIME_DIR,
                                                     "orchestrator.py")))
        for name in sorted(os.listdir(capability_dir)):
            if not name.endswith(".py"):
                continue
            with self.subTest(capability=name):
                self.assertNotIn("SourceMutationDetected",
                                 read_text(os.path.join(capability_dir, name)))

    def test_the_orchestrator_is_the_only_emitter_of_the_mutation_event(self):
        """Step 2B asserted NOTHING emitted it. Step 2C made the orchestrator
        the one emitter, for the reason this suite already established: an
        orchestrator-produced event needs no manifest declaration, so no
        capabilityId bump and no weakening of registration validation.

        An allow-list again, so a second emitter -- especially a capability --
        still breaks this test.
        """
        emitters = set()
        for root, _dirs, files in os.walk(self.RUNTIME_DIR):
            if "__pycache__" in root:
                continue
            for name in files:
                if not name.endswith(".py"):
                    continue
                if "SourceMutationDetected" in read_text(os.path.join(root, name)):
                    emitters.add(name)
        self.assertEqual(emitters, {"orchestrator.py"},
                         "the orchestrator is the one and only emitter")


if __name__ == "__main__":
    unittest.main()

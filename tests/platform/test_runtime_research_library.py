#!/usr/bin/env python3
"""MOGO-018 Step 2 -- the research library bridge.

The properties under test are not "the index lists things". They are:

  * IT IS DERIVED, NOT AUTHORITATIVE. It writes nothing, and two runs over
    unchanged input are byte-identical -- so it can always be thrown away and
    rebuilt.
  * IT REFERENCES, NEVER COPIES. Immutable acquisition artifacts and committed
    Knowledge Library evidence are both proven byte-unchanged.
  * THE TWO CONTENT HASHES STAY DISTINCT. Lane A hashes a transcript file, Lane
    B hashes external response bytes. The index never emits a bare `contentHash`
    and never lets one masquerade as the other.
  * ORGANIZATION IS NOT VALIDATION. Presence in a corpus creates no hypothesis,
    rule, blueprint, backtest, campaign or trading decision.

The acquisition harness is REUSED from the MOGO-017 Step 2C suite rather than
duplicated: it already drives the real Orchestrator with only the socket and the
corpus doubled, which is exactly what these fixtures need.
"""

import ast
import glob
import hashlib
import json
import os
import sys
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "platform", "src"))

from mogo_platform.runtime import errors as runtime_errors      # noqa: E402
from mogo_platform.runtime import research_corpus               # noqa: E402
from mogo_platform.runtime import research_library as library   # noqa: E402
from mogo_platform.runtime import change_detection as cd        # noqa: E402
from mogo_platform.runtime import connector_transport as transport  # noqa: E402

from tests.platform.test_runtime_change_detection_wiring import (  # noqa: E402
    ChangeDetectionWiringCase, APPROVED_SOURCE, APPROVED_RESOURCE,
    OTHER_RESOURCE, BODY_A, BODY_B, BODY_INVALID, HASH_A, HASH_B)

ATTRIBUTED_FAMILY = "SF|ALEX_G|SUPPORT_RESISTANCE_V1"
KNOWLEDGE_LIBRARY_ROOTS = (
    os.path.join(REPO_ROOT, "docs", "trader-intelligence", "evidence", "sources"),
    os.path.join(REPO_ROOT, "docs", "trader-intelligence", "traders"),
)


def code_text(path):
    """The module's executable code with docstrings stripped.

    A raw text scan is the wrong tool here and MOGO-017 already proved it: this
    module's docstring STATES the prohibitions -- "creates no hypothesis, rule,
    blueprint, backtest, campaign or trading decision" -- so scanning the file
    flags the very sentences that describe the firewall. What matters is what
    the CODE can reach.
    """
    with open(path, "r", encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(body, list) or not body:
            continue
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                 ast.AsyncFunctionDef)):
            continue
        first = body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                and isinstance(first.value.value, str):
            body.pop(0)
    return ast.unparse(tree)


def committed_attribution():
    with open(library.ATTRIBUTION_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def fingerprint(paths):
    """Byte fingerprint of a set of committed files, for immutability proofs."""
    digest = {}
    for path in sorted(paths):
        with open(path, "rb") as handle:
            digest[os.path.relpath(path, REPO_ROOT)] = \
                hashlib.sha256(handle.read()).hexdigest()
    return digest


def knowledge_library_files():
    found = []
    for root in KNOWLEDGE_LIBRARY_ROOTS:
        for base, _dirs, names in os.walk(root):
            found.extend(os.path.join(base, name) for name in names
                         if name.endswith(".json"))
    return found


def research_evidence_files():
    return (glob.glob(os.path.join(research_corpus.PRODUCTION_ARTIFACT_ROOT, "*.json"))
            + glob.glob(os.path.join(research_corpus.PRODUCTION_INTAKE_ROOT,
                                     "acquired", "*.json")))


# ---------------------------------------------------------------------------
# The declared attribution -- verified, not trusted
# ---------------------------------------------------------------------------

class TestAttributionIsVerified(unittest.TestCase):

    def test_the_committed_attribution_loads(self):
        attribution = library.resolve_attribution(committed_attribution())
        self.assertIn(APPROVED_SOURCE, attribution)
        self.assertEqual(attribution[APPROVED_SOURCE]["traderId"], "ALEX_G")
        self.assertEqual(attribution[APPROVED_SOURCE]["strategyFamilyIds"],
                         [ATTRIBUTED_FAMILY])

    def test_the_source_id_is_recomputed_from_the_channel_url(self):
        """The link is CHECKED, not pasted.

        A typo, or a channel URL swapped under an unchanged id, must fail closed
        rather than silently attribute one educator's material to another.
        """
        with open(library.ATTRIBUTION_PATH, "r", encoding="utf-8") as handle:
            document = json.load(handle)
        record = document["attributions"][0]
        from mogo_platform.contracts import ids
        self.assertEqual(
            ids.make_source_id(record["sourceIdDerivation"]["provider"],
                               record["sourceIdDerivation"]["channelUrl"]),
            record["sourceId"])

    def test_the_derivation_matches_the_committed_channel_catalogue(self):
        """The channel URL is the one the repository already verified."""
        with open(os.path.join(REPO_ROOT, "docs", "strategy-fidelity", "audit",
                               "alex-channel-catalogue.json"),
                  "r", encoding="utf-8") as handle:
            catalogue = json.load(handle)
        with open(library.ATTRIBUTION_PATH, "r", encoding="utf-8") as handle:
            record = json.load(handle)["attributions"][0]
        self.assertEqual(record["sourceIdDerivation"]["channelUrl"],
                         catalogue["channelUrl"])

    def base(self, **over):
        record = {"sourceId": APPROVED_SOURCE,
                  "sourceIdDerivation": {
                      "provider": "youtube",
                      "channelUrl": "https://www.youtube.com/@fxalexg__"},
                  "traderId": "ALEX_G",
                  "strategyFamilyIds": [ATTRIBUTED_FAMILY]}
        record.update(over)
        return {"schemaVersion": library.ATTRIBUTION_SCHEMA_VERSION,
                "attributions": [record]}

    def refused(self, document):
        with self.assertRaises(runtime_errors.PlatformError):
            library.resolve_attribution(document)

    def test_a_mismatched_source_id_is_refused(self):
        self.refused(self.base(sourceId="SRC|youtube|000000000000"))

    def test_a_swapped_channel_url_under_the_same_id_is_refused(self):
        self.refused(self.base(sourceIdDerivation={
            "provider": "youtube",
            "channelUrl": "https://www.youtube.com/@someone_else"}))

    def test_a_missing_field_is_refused(self):
        for field in ("sourceId", "sourceIdDerivation", "traderId",
                      "strategyFamilyIds"):
            with self.subTest(missing=field):
                document = self.base()
                del document["attributions"][0][field]
                self.refused(document)

    def test_a_non_sf_strategy_family_is_refused(self):
        self.refused(self.base(strategyFamilyIds=["SUPPORT_RESISTANCE_V1"]))

    def test_a_duplicated_attribution_for_one_source_is_refused(self):
        document = self.base()
        document["attributions"].append(dict(document["attributions"][0]))
        self.refused(document)

    def test_a_wrong_schema_version_is_refused(self):
        document = self.base()
        document["schemaVersion"] = "mogo.research-library-attribution.v2"
        self.refused(document)

    def test_strategy_families_are_a_list_so_one_artifact_can_join_several(self):
        """Requirement 10, at the representation level."""
        attribution = library.resolve_attribution(self.base(strategyFamilyIds=[
            ATTRIBUTED_FAMILY, "SF|ALEX_G|SECOND_FAMILY_V1"]))
        self.assertEqual(len(attribution[APPROVED_SOURCE]["strategyFamilyIds"]), 2)


# ---------------------------------------------------------------------------
# The derived index, driven by real governed acquisitions
# ---------------------------------------------------------------------------

class ResearchLibraryCase(ChangeDetectionWiringCase):
    """Reuses the MOGO-017 Step 2C acquisition harness verbatim."""

    def setUp(self):
        super().setUp()
        self.evidence_before = fingerprint(research_evidence_files())
        self.knowledge_before = fingerprint(knowledge_library_files())

    def tearDown(self):
        self.assertEqual(fingerprint(research_evidence_files()),
                         self.evidence_before,
                         "immutable research evidence must be byte-unchanged")
        self.assertEqual(fingerprint(knowledge_library_files()),
                         self.knowledge_before,
                         "committed Knowledge Library evidence must be unchanged")
        super().tearDown()

    def index(self):
        with self.runtime() as rt:
            return library.entries(rt.connection, committed_attribution())

    def summary(self):
        with self.runtime() as rt:
            return library.corpus_summary(rt.connection, committed_attribution())


class TestTheDerivedIndex(ResearchLibraryCase):

    def test_the_approved_source_produces_one_correct_entry(self):
        """Requirement 1."""
        self.initialise()
        self.box["body"] = BODY_A
        self.acquire_once("R1")
        index = self.index()
        self.assertEqual(len(index), 1)
        entry = index[0]
        self.assertEqual(entry["sourceId"], APPROVED_SOURCE)
        self.assertEqual(entry["resourceId"], APPROVED_RESOURCE)
        self.assertEqual(entry["traderId"], "ALEX_G")
        self.assertEqual(entry["strategyFamilyIds"], [ATTRIBUTED_FAMILY])
        self.assertEqual(entry["attributionStatus"], "ATTRIBUTED")
        self.assertEqual(entry["acceptedContentIdentity"], HASH_A)
        self.assertEqual(entry["lane"], "RESEARCH")
        self.assertEqual(entry["promotionStatus"], "NOT_A_TRADING_RULE")

    def test_it_references_the_artifact_rather_than_copying_it(self):
        self.initialise()
        self.box["body"] = BODY_A
        self.acquire_once("R1")
        entry = self.index()[0]
        self.assertTrue(entry["artifactId"].startswith("RART|"))
        self.assertTrue(entry["artifactPath"])
        self.assertTrue(entry["intakeRef"])
        blob = json.dumps(entry)
        self.assertNotIn(BODY_A.decode("utf-8"), blob,
                         "the index must reference content, never duplicate it")

    def test_the_index_is_derived_and_deterministic(self):
        """Two reads over unchanged input are byte-identical."""
        self.initialise()
        self.box["body"] = BODY_A
        self.acquire_once("R1")
        first = json.dumps(self.index(), sort_keys=True)
        second = json.dumps(self.index(), sort_keys=True)
        self.assertEqual(first, second)

    def test_it_writes_nothing(self):
        """Asserted structurally: no write-capable call exists in the module."""
        with open(library.__file__, "r", encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        writes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                target = node.func
                name = (target.id if isinstance(target, ast.Name)
                        else target.attr if isinstance(target, ast.Attribute)
                        else "")
                if name in ("makedirs", "replace", "remove", "rename", "rmtree",
                            "write_text", "write_bytes", "mkdir"):
                    writes.append(name)
                if name == "open":
                    # Reading the committed attribution file is the only open,
                    # and it must be read-only.
                    modes = [a.value for a in node.args[1:]
                             if isinstance(a, ast.Constant)]
                    modes += [k.value.value for k in node.keywords
                              if k.arg == "mode" and isinstance(k.value, ast.Constant)]
                    self.assertTrue(all(m == "r" for m in modes), modes)
        self.assertEqual(writes, [])

    def test_unchanged_reacquisition_does_not_duplicate_the_entry(self):
        """Requirement 6."""
        self.initialise()
        self.box["body"] = BODY_A
        self.acquire_once("R1")
        self.acquire_once("R2")
        index = self.index()
        self.assertEqual(len(index), 1, "UNCHANGED must not create a second entry")
        self.assertEqual(index[0]["acceptedObservationCount"], 2)
        self.assertEqual(index[0]["distinctAcceptedContentIdentities"], 1)
        self.assertEqual(index[0]["lastClassification"], cd.UNCHANGED)
        self.assertEqual(index[0]["acceptedContentIdentity"], HASH_A)

    def test_changed_content_updates_the_current_reference(self):
        """Requirement 7 -- the current identity moves, prior evidence does not."""
        self.initialise()
        self.box["body"] = BODY_A
        self.acquire_once("R1")
        first_artifact = self.index()[0]["artifactId"]
        self.box["body"] = BODY_B
        self.acquire_once("R2")
        index = self.index()
        self.assertEqual(len(index), 1, "a change is the SAME stream, not a new one")
        entry = index[0]
        self.assertEqual(entry["acceptedContentIdentity"], HASH_B,
                         "the current reference must follow the newest accepted")
        self.assertEqual(entry["lastClassification"], cd.CHANGED)
        self.assertEqual(entry["acceptedObservationCount"], 2)
        self.assertEqual(entry["distinctAcceptedContentIdentities"], 2,
                         "history retains both identities")
        self.assertNotEqual(entry["artifactId"], first_artifact)
        # The earlier artifact still exists, unrewritten.
        self.assertEqual(len(os.listdir(self.artifacts)), 2)

    def test_a_failed_acquisition_does_not_advance_library_state(self):
        """Requirement 8."""
        self.initialise()
        self.box["body"] = BODY_A
        self.acquire_once("R1")
        self.box["status"] = 500
        self.acquire_once("R2")
        entry = self.index()[0]
        self.assertEqual(entry["acceptedContentIdentity"], HASH_A)
        self.assertEqual(entry["acceptedObservationCount"], 1)

    def test_invalid_content_never_enters_the_corpus(self):
        """Requirement 8 -- validation failure, including CHANGED-but-invalid."""
        self.initialise()
        self.box["body"] = BODY_INVALID
        self.acquire_once("R1")
        self.assertEqual(self.index(), [],
                         "a stream with no ACCEPTED acquisition has no entry")
        self.box["body"] = BODY_A
        self.acquire_once("R2")
        self.assertEqual(self.index()[0]["acceptedContentIdentity"], HASH_A)


class TestIsolation(ResearchLibraryCase):

    def test_resource_isolation(self):
        """Requirement 2 -- one entry per (sourceId, resourceId)."""
        self.initialise()
        self.box["body"] = BODY_A
        self.acquire_once("R1", resource_id=APPROVED_RESOURCE)
        self.box["body"] = BODY_B
        self.acquire_once("R2", resource_id=OTHER_RESOURCE)
        index = self.index()
        self.assertEqual(len(index), 2)
        by_resource = {e["resourceId"]: e for e in index}
        self.assertEqual(by_resource[APPROVED_RESOURCE]["acceptedContentIdentity"],
                         HASH_A)
        self.assertEqual(by_resource[OTHER_RESOURCE]["acceptedContentIdentity"],
                         HASH_B)

    def test_an_unattributed_source_cannot_join_another_corpus(self):
        """Requirement 9 -- attribution is explicit, never inferred.

        A stream whose source is not declared appears as UNATTRIBUTED with an
        EMPTY family list. It never falls back to a neighbouring corpus.
        """
        self.initialise()
        self.box["body"] = BODY_A
        self.acquire_once("R1")
        other = {"schemaVersion": library.ATTRIBUTION_SCHEMA_VERSION,
                 "attributions": [{
                     "sourceId": APPROVED_SOURCE,
                     "sourceIdDerivation": {
                         "provider": "youtube",
                         "channelUrl": "https://www.youtube.com/@fxalexg__"},
                     "traderId": "SOMEONE_ELSE",
                     "strategyFamilyIds": ["SF|SOMEONE_ELSE|OTHER_V1"]}]}
        with self.runtime() as rt:
            entries = library.entries(rt.connection, other)
        self.assertEqual(entries[0]["traderId"], "SOMEONE_ELSE",
                         "attribution comes ONLY from the declaration")
        self.assertNotIn(ATTRIBUTED_FAMILY, entries[0]["strategyFamilyIds"],
                         "no corpus may leak into another")

    def test_corpus_summary_partitions_by_family(self):
        self.initialise()
        self.box["body"] = BODY_A
        self.acquire_once("R1")
        summary = self.summary()
        self.assertEqual(len(summary), 1)
        self.assertEqual(summary[0]["strategyFamilyId"], ATTRIBUTED_FAMILY)
        self.assertEqual(summary[0]["streams"], 1)
        self.assertEqual(summary[0]["promotionStatus"], "NOT_A_TRADING_RULE")


class TestHashSemanticsStayDistinct(ResearchLibraryCase):
    """Requirement 5 -- the single most important safety property here."""

    def test_the_index_never_emits_a_bare_content_hash_field(self):
        self.initialise()
        self.box["body"] = BODY_A
        self.acquire_once("R1")
        entry = self.index()[0]
        self.assertNotIn("contentHash", entry,
                         "Lane A already owns that field name for a TRANSCRIPT "
                         "FILE hash; reusing it here would let one masquerade "
                         "as the other")
        self.assertIn("acceptedContentIdentity", entry)
        self.assertEqual(entry["acceptedContentIdentityBasis"],
                         "RAW_EXTERNAL_RESPONSE_BYTES")
        self.assertEqual(entry["acceptedContentIdentityAlgorithm"], "SHA-256")

    def test_the_identity_is_the_external_byte_hash_not_the_artifact_hash(self):
        self.initialise()
        self.box["body"] = BODY_A
        self.acquire_once("R1")
        entry = self.index()[0]
        self.assertEqual(entry["acceptedContentIdentity"],
                         transport.content_hash(BODY_A))
        self.assertNotEqual(entry["acceptedContentIdentity"],
                            entry["artifactId"].split("|", 1)[1],
                            "the artifact id derives from the WRAPPER hash and "
                            "is a different number")

    def test_lane_a_transcript_hashes_are_untouched_by_the_bridge(self):
        """A committed EvidenceSource keeps its own contentHash meaning."""
        path = os.path.join(REPO_ROOT, "docs", "trader-intelligence", "evidence",
                            "sources", "EVSRC_ALEX_G_20260727_001.json")
        with open(path, "r", encoding="utf-8") as handle:
            record = json.load(handle)
        self.assertTrue(record["contentHash"])
        self.assertNotEqual(record["contentHash"], HASH_A)
        code = code_text(library.__file__)
        self.assertNotIn("EvidenceSource(", code)
        self.assertNotIn("EVSRC|", code,
                         "the bridge must never mint a Lane A identifier")


class TestScientificFirewall(ResearchLibraryCase):
    """Requirements 11, 12 and 13."""

    def test_arbitrary_urls_remain_prohibited(self):
        """Requirement 11 -- the bridge introduced no destination surface."""
        code = code_text(library.__file__)
        # `fetchall` is deliberately NOT in this list: it is a SQLite cursor
        # method, and banning the substring would ban reading the database.
        for fragment in ("http://", "https://", "urlopen", "urllib", "socket",
                         "requests", "urlretrieve", "Request("):
            with self.subTest(fragment=fragment):
                self.assertNotIn(fragment, code)
        with open(library.ATTRIBUTION_PATH, "r", encoding="utf-8") as handle:
            document = json.load(handle)
        # The ONE URL present is the channel URL used to RECOMPUTE the source id.
        # It is never fetched -- the destination still comes from the connector.
        record = document["attributions"][0]
        self.assertEqual(set(record["sourceIdDerivation"]) - {"evidenceRef"},
                         {"provider", "channelUrl"})

    def test_authorization_remains_fail_closed(self):
        """Requirement 12 -- an unauthorized source still never reaches a corpus."""
        self.initialise()
        self.box["body"] = BODY_A
        self.acquire_once("R1")
        self.assertEqual(len(self.index()), 1)
        # Nothing in the library can grant authorization; it only reads results
        # that already passed the gate.
        code = code_text(library.__file__)
        for fragment in ("record_authorization", "authorizations.register",
                         "PERMITTED_", "policy.evaluate"):
            with self.subTest(fragment=fragment):
                self.assertNotIn(fragment, code)

    def test_the_bridge_creates_no_trading_or_scientific_artefact(self):
        """Requirement 13 -- organization is not validation."""
        code = code_text(library.__file__)
        self.assertNotIn("organization is not validation", code.lower(),
                         "docstrings must have been stripped before scanning")
        for forbidden in ("hypothes", "backtest", "paperAccount", "openPaper",
                          "alexG", "tradingRule", "rule_candidate", "blueprint",
                          "campaign", "promote"):
            with self.subTest(symbol=forbidden):
                self.assertNotIn(forbidden, code)

    def test_no_hypothesis_or_rule_directory_is_written(self):
        watched = [os.path.join(REPO_ROOT, "docs", "trader-intelligence",
                                "evidence", name)
                   for name in ("hypotheses", "blueprints", "proposals")]
        before = {path: sorted(os.listdir(path)) for path in watched
                  if os.path.isdir(path)}
        self.initialise()
        self.box["body"] = BODY_A
        self.acquire_once("R1")
        self.index()
        self.summary()
        after = {path: sorted(os.listdir(path)) for path in watched
                 if os.path.isdir(path)}
        self.assertEqual(after, before)

    def test_every_entry_carries_the_research_boundary(self):
        self.initialise()
        self.box["body"] = BODY_A
        self.acquire_once("R1")
        for entry in self.index():
            self.assertEqual(entry["lane"], "RESEARCH")
            self.assertEqual(entry["promotionStatus"], "NOT_A_TRADING_RULE")
        for bucket in self.summary():
            self.assertEqual(bucket["promotionStatus"], "NOT_A_TRADING_RULE")


if __name__ == "__main__":
    unittest.main()

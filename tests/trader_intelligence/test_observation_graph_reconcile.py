"""The reconciliation diagnostic had ZERO tests (B-32.3).

Adversarial verification deleted its record-derived orphan floor outright, and
separately removed its empty-corpus vacuity guard, and the entire suite stayed
green both times. Every check three rounds of repair added to this script was
verified only by running it against a corpus that happened to be clean -- which
is the same mistake, one layer out, as testing a copy of a check instead of the
check.

Everything here builds a scratch corpus the test writes itself.
"""
import datetime
import json
import os
import shutil
import sys
import tempfile
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts", "trader_intelligence"))

import observation_graph_reconcile as ogr   # noqa: E402
import graph_common as gc                   # noqa: E402


class ReconcileCase(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="mogo_reconcile_")
        self.ti_root = os.path.join(self.root, "docs", "trader-intelligence")
        self.evidence = os.path.join(self.ti_root, "evidence")
        for name in ("sources", "observations", "items"):
            os.makedirs(os.path.join(self.evidence, name))
        os.makedirs(os.path.join(self.ti_root, "graph", "decisions"))
        self._saved = (ogr.TI_ROOT, ogr.GRAPH_ROOT, ogr.REPO_ROOT)
        ogr.TI_ROOT = self.ti_root
        ogr.GRAPH_ROOT = os.path.join(self.ti_root, "graph")
        ogr.REPO_ROOT = self.root

    def tearDown(self):
        ogr.TI_ROOT, ogr.GRAPH_ROOT, ogr.REPO_ROOT = self._saved
        shutil.rmtree(self.root, ignore_errors=True)

    def write(self, collection, name, record):
        with open(os.path.join(self.evidence, collection, name + ".json"),
                  "w", encoding="utf-8") as handle:
            json.dump(record, handle)

    def source(self, sid="EVSRC|MOGO|20260819|001", source_type="replay_observation"):
        # Carries the attribution metadata a real capture source carries. Without it
        # the observation citing it makes a strategy claim nothing can corroborate,
        # which MISSING_SOURCE_ATTRIBUTION correctly reports -- the fixture was
        # modelling a source MOGO's importer never produces.
        self.write("sources", sid.replace("|", "_"), {
            "sourceId": sid, "sourceType": source_type, "title": "capture",
            "storageLocationType": "repository", "provenanceStatus": "owner_supplied",
            "createdAt": "2026-08-19T00:00:00Z",
            "metadata": {"captureBasis": "REPLAY_RUN",
                         "engineStrategyId": "alex_g_sr_v1"}})

    def observation(self, oid="TOBS|MOGO|20260819|001",
                    sid="EVSRC|MOGO|20260819|001", basis="REPLAY_RUN",
                    minted="replay_observation", **extra):
        rec = {"observationId": oid, "sourceId": sid, "instrument": "GBP/USD",
               "createdAt": "2026-08-19T00:00:00Z", "strategyId": "alex_g_sr_v1",
               "notes": "captureBasis=%s sourceType=%s" % (basis, minted)}
        rec.update(extra)
        self.write("observations", oid.replace("|", "_"), rec)

    def run_reconcile(self):
        return ogr.reconcile()

    def healthy(self):
        self.source()
        self.observation()


class TestTheVacuityGuard(ReconcileCase):
    """Eight checks over zero rows are all true. That is not a clean run."""

    def test_an_empty_corpus_is_a_FAILURE_not_a_clean_run(self):
        _report, problems = self.run_reconcile()
        self.assertTrue(any("no preserved observations" in p for p in problems))

    def test_sources_without_observations_is_also_reported(self):
        self.source()
        _report, problems = self.run_reconcile()
        self.assertTrue(any("no preserved observations" in p for p in problems))

    def test_POSITIVE_CONTROL_a_populated_corpus_is_not_flagged_vacuous(self):
        self.healthy()
        _report, problems = self.run_reconcile()
        self.assertFalse(any("vacuous" in p for p in problems), problems)


class TestTheRecordDerivedOrphanFloor(ReconcileCase):
    """The floor exists because the production check and the in-script witness
    recount the same rule over the same edges, so disarming both makes them agree
    and both be wrong. This one reads the RECORDS, which no graph edit can move."""

    def test_a_source_referenced_by_nothing_is_counted(self):
        self.healthy()
        self.source("EVSRC|MOGO|20260819|002")     # cited by nobody
        report, _problems = self.run_reconcile()
        self.assertEqual(report["sourcesUnreferencedByAnyRecord"], 1)

    def test_a_source_cited_by_an_observation_is_NOT_counted(self):
        self.healthy()
        report, _problems = self.run_reconcile()
        self.assertEqual(report["sourcesUnreferencedByAnyRecord"], 0)

    def test_a_source_referenced_only_by_an_EVIDENCE_ITEM_is_NOT_counted(self):
        # Items reference sources too; counting those as unreferenced would make the
        # floor fire constantly and train everyone to ignore it.
        self.healthy()
        self.source("EVSRC|MOGO|20260819|002")
        self.write("items", "item", {"evidenceId": "EV|MOGO|1",
                                     "sourceId": "EVSRC|MOGO|20260819|002"})
        report, _problems = self.run_reconcile()
        self.assertEqual(report["sourcesUnreferencedByAnyRecord"], 0)

    def test_the_floor_fires_when_the_graph_fails_to_report_a_real_orphan(self):
        self.healthy()
        self.source("EVSRC|MOGO|20260819|002")
        original = ogr.validate_graph.check_orphans
        try:
            # Disarm the production check AND the witness would follow it -- the floor
            # is the layer that must survive.
            ogr.validate_graph.check_orphans = lambda nodes, edges, findings: None
            report, problems = self.run_reconcile()
        finally:
            ogr.validate_graph.check_orphans = original
        self.assertEqual(report["orphansTheGraphFailedToReport"], 1)
        self.assertTrue(any("referenced by NO observation" in p for p in problems), problems)

    def test_POSITIVE_CONTROL_the_floor_is_silent_on_a_healthy_corpus(self):
        self.healthy()
        report, _problems = self.run_reconcile()
        self.assertEqual(report["orphansTheGraphFailedToReport"], 0)


class TestPopulationFindingsDoNotAbortTheRun(ReconcileCase):
    """It passed `now=""` into a helper that calls `now.strftime(...)`, so the first
    population finding raised AttributeError at check 4 and checks 5-8 never ran --
    the orphan floor, the witness, the fabricated-edge check, determinism."""

    def test_a_rebinding_is_counted_and_later_checks_still_run(self):
        self.source(source_type="paper_trade")
        self.observation(basis="REPLAY_RUN", minted="replay_observation")
        report, problems = self.run_reconcile()
        self.assertGreaterEqual(report["populationRebindings"], 1)
        for later in ("orphansTheGraphFailedToReport", "rebuildIsDeterministic",
                      "nonProvenanceEdgesTouchingObservations", "danglingEdges"):
            self.assertIn(later, report,
                          "check after the population step did not run: %s" % later)
        self.assertTrue(problems)


class TestStructuralChecks(ReconcileCase):

    def test_an_observation_whose_source_is_absent_has_no_provenance(self):
        self.observation(sid="EVSRC|MOGO|20260819|999")
        report, problems = self.run_reconcile()
        self.assertEqual(report["provenanceMissing"], 1)
        self.assertTrue(problems)

    def test_a_healthy_corpus_reconciles(self):
        self.healthy()
        report, problems = self.run_reconcile()
        self.assertEqual(problems, [])
        self.assertEqual(report["preservedObservations"], report["observationNodes"])
        self.assertEqual(report["provenanceCovered"], report["preservedObservations"])
        self.assertTrue(report["rebuildIsDeterministic"])

    def test_the_hash_check_is_INDEPENDENT_of_the_function_it_verifies(self):
        # Comparing gc.content_hash_of against itself proves only that both sides
        # called the same function; a gutted content_hash_of passed that check.
        self.healthy()
        original = gc.content_hash_of
        try:
            gc.content_hash_of = lambda obj: gc.sha256_hex(b"constant")
            report, problems = self.run_reconcile()
        finally:
            gc.content_hash_of = original
        self.assertGreater(report["contentHashMismatches"], 0)
        self.assertTrue(problems)


if __name__ == "__main__":
    unittest.main()

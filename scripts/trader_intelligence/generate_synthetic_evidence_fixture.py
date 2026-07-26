#!/usr/bin/env python3
"""One-off generator for the PROGRAM-006 Phase 1A synthetic demo fixture
(ADR-008, Deliverable 14). Run once to (re)produce the static JSON files
checked in under tests/trader_intelligence/evidence/fixtures/synthetic_demo/.

Not part of the runtime or the test suite's import graph -- the test suite
loads the already-generated static files, exactly like PROGRAM-003's
tests/trader_intelligence/fixtures/happy_path/*.json are static, checked-in
files rather than something regenerated on every test run.

SYNTHETIC TEST DATA / NOT REAL TJR RESEARCH / NOT VALIDATED TRADING
KNOWLEDGE / NOT A PRODUCTION RULE. Every string below is invented for
demonstration purposes only.
"""
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import evidence_registry as reg  # noqa: E402

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT_ROOT = os.path.join(REPO_ROOT, "tests", "trader_intelligence", "evidence", "fixtures", "synthetic_demo")

MARKER = "SYNTHETIC TEST DATA / NOT REAL TJR RESEARCH / NOT VALIDATED TRADING KNOWLEDGE / NOT A PRODUCTION RULE"
NOW = datetime(2026, 7, 26, 9, 0, 0, tzinfo=timezone.utc)


def main():
    dirs = {name: os.path.join(OUT_ROOT, name) for name in
            ("sources", "items", "claims", "links", "contradictions", "lifecycle")}
    for d in dirs.values():
        os.makedirs(d, exist_ok=True)

    source = reg.register_source(
        dirs["sources"], dirs["lifecycle"], "transcript", "fixture_generator", NOW,
        traderId="TJR", title="%s -- example displacement-after-sweep discussion" % MARKER,
        provenanceStatus="unverified")

    item_primary = reg.register_evidence_item(
        dirs["items"], dirs["sources"], dirs["lifecycle"], source["sourceId"],
        "explicit_statement", "high", "fixture_generator", NOW,
        exactExcerpt="%s: 'Displacement must follow the liquidity sweep before I consider the setup valid.'" % MARKER,
        timeframe="5m")

    item_corroborating_original = reg.register_evidence_item(
        dirs["items"], dirs["sources"], dirs["lifecycle"], source["sourceId"],
        "demonstrated_behavior", "high", "fixture_generator", NOW,
        exactExcerpt="%s: chart example (draft wording, superseded below)." % MARKER,
        timeframe="5m")

    # Demonstrates provenance/correction: never edit in place, supersede instead.
    item_corroborating_corrected = reg.correct_evidence_item(
        dirs["items"], dirs["sources"], dirs["lifecycle"], item_corroborating_original["evidenceId"],
        "fixture_generator", NOW,
        exactExcerpt="%s: chart example (corrected wording) showing displacement immediately after the sweep." % MARKER,
        timeframe="5m")

    source_corroborating = reg.register_source(
        dirs["sources"], dirs["lifecycle"], "owner_observation", "fixture_generator", NOW,
        traderId="TJR", title="%s -- independent corroborating owner note" % MARKER)

    item_independent = reg.register_evidence_item(
        dirs["items"], dirs["sources"], dirs["lifecycle"], source_corroborating["sourceId"],
        "explicit_statement", "high", "fixture_generator", NOW,
        exactExcerpt="%s: owner confirms the same displacement-after-sweep pattern from a separate session review." % MARKER,
        timeframe="5m")

    item_contradicting = reg.register_evidence_item(
        dirs["items"], dirs["sources"], dirs["lifecycle"], source_corroborating["sourceId"],
        "opinion", "low", "fixture_generator", NOW,
        exactExcerpt="%s: 'Some traders skip waiting for the sweep entirely.'" % MARKER,
        timeframe="5m")

    claim_supported = reg.register_claim(
        dirs["claims"], dirs["lifecycle"], "entry_rule",
        "%s claim: Displacement occurs after a liquidity sweep." % MARKER,
        "fixture_generator", NOW, traderId="TJR", timeframe="5m")

    claim_contradicted = reg.register_claim(
        dirs["claims"], dirs["lifecycle"], "entry_rule",
        "%s claim: Entries do not require waiting for a liquidity sweep." % MARKER,
        "fixture_generator", NOW, traderId="TJR", timeframe="5m")

    reg.link_evidence_to_claim(dirs["links"], dirs["items"], dirs["claims"], dirs["lifecycle"],
                                item_primary["evidenceId"], claim_supported["claimId"], "supports",
                                "fixture_generator", NOW)
    reg.link_evidence_to_claim(dirs["links"], dirs["items"], dirs["claims"], dirs["lifecycle"],
                                item_corroborating_corrected["evidenceId"], claim_supported["claimId"], "supports",
                                "fixture_generator", NOW)
    reg.link_evidence_to_claim(dirs["links"], dirs["items"], dirs["claims"], dirs["lifecycle"],
                                item_independent["evidenceId"], claim_supported["claimId"], "supports",
                                "fixture_generator", NOW)
    reg.link_evidence_to_claim(dirs["links"], dirs["items"], dirs["claims"], dirs["lifecycle"],
                                item_contradicting["evidenceId"], claim_contradicted["claimId"], "contradicts",
                                "fixture_generator", NOW)

    contradiction = reg.create_contradiction(
        dirs["contradictions"], dirs["claims"], dirs["lifecycle"],
        claim_supported["claimId"], claim_contradicted["claimId"], "DIRECTIONAL", "material",
        "fixture_generator", NOW,
        rationale="%s: the two claims take opposing positions on whether a sweep is required." % MARKER)

    print("Generated fixture under %s" % OUT_ROOT)
    print("source=%s" % source["sourceId"])
    print("items=%s" % [item_primary["evidenceId"], item_corroborating_original["evidenceId"],
                        item_corroborating_corrected["evidenceId"], item_independent["evidenceId"],
                        item_contradicting["evidenceId"]])
    print("claims=%s (supported), %s (contradicted)" % (claim_supported["claimId"], claim_contradicted["claimId"]))
    print("contradiction=%s" % contradiction["contradictionId"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

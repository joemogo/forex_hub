#!/usr/bin/env python3
"""Do the preserved TradeObservations and the graph agree? (B-32)

WHY THIS EXISTS

B-32 made TradeObservation a first-class graph node so that MOGO's own preserved
evidence participates in one lineage instead of sitting in a parallel store. That
creates a standing obligation: the graph is DERIVED, so it can silently drift from
the records it derives from -- a discovery glob that stops matching, a rename, a
half-written build -- and a derived view that disagrees with its source is worse
than no view, because it still answers questions.

This answers one bounded question: does every preserved observation appear exactly
once in the graph, linked to the source it actually names?

It is READ-ONLY. It reads the preserved records and rebuilds the graph in memory;
it writes nothing and never repairs anything.

    python3 scripts/trader_intelligence/observation_graph_reconcile.py

Exit: 0 reconciled - 1 discrepancy.
"""
import glob
import glob as globmod
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)

import graph_common as gc          # noqa: E402
import validate_evidence as ve     # noqa: E402
import validate_graph              # noqa: E402
import trade_observation as to     # noqa: E402

TI_ROOT = os.path.join(REPO_ROOT, "docs", "trader-intelligence")
GRAPH_ROOT = os.path.join(TI_ROOT, "graph")


def _independent_hash(entity):
    """sha256 of canonical JSON, computed WITHOUT gc.content_hash_of. See the note
    at its call site for why the duplication is deliberate."""
    return hashlib.sha256(
        json.dumps(entity, sort_keys=True, separators=(",", ":"),
                   ensure_ascii=False).encode("utf-8")).hexdigest()


def load_preserved():
    observations, sources = {}, {}
    for path in sorted(glob.glob(os.path.join(TI_ROOT, "evidence", "observations", "*.json"))):
        with open(path, "r", encoding="utf-8") as handle:
            rec = json.load(handle)
        observations[rec["observationId"]] = rec
    for path in sorted(glob.glob(os.path.join(TI_ROOT, "evidence", "sources", "*.json"))):
        with open(path, "r", encoding="utf-8") as handle:
            rec = json.load(handle)
        sources[rec["sourceId"]] = rec
    return observations, sources


def reconcile():
    observations, sources = load_preserved()
    nodes, edges, findings, _raw = gc.build_nodes_and_edges(REPO_ROOT, TI_ROOT, GRAPH_ROOT)

    obs_nodes = [n for n in nodes if n["nodeType"] == "TRADE_OBSERVATION"]
    src_nodes = [n for n in nodes if n["nodeType"] == "EVIDENCE_SOURCE"]
    node_ids = {n["nodeId"] for n in nodes}

    # A corpus that loaded NOTHING passes every check below -- eight comparisons
    # over zero rows, all true. That is the exact anti-pattern this repository has
    # been bitten by repeatedly ("assert filters are non-empty, or the loop passes
    # vacuously"), and it was live here: emptying evidence/observations/ printed
    # RECONCILED and exited 0, which is what a discovery glob that stops matching
    # looks like from the outside.
    report = {"preservedObservations": len(observations),
              "observationNodes": len(obs_nodes),
              "preservedSources": len(sources),
              "sourceNodes": len(src_nodes)}
    problems = []
    if not observations:
        problems.append("no preserved observations were loaded at all -- every check "
                        "below would pass vacuously, so this is reported as a failure "
                        "rather than a clean run")
    if not sources:
        problems.append("no EvidenceSources were loaded at all")

    # 1. One node per preserved record, and no node without a record.
    preserved_ids = set(observations)
    node_entity_ids = [n["entityId"] for n in obs_nodes]
    report["duplicateObservationNodes"] = len(node_entity_ids) - len(set(node_entity_ids))
    if report["duplicateObservationNodes"]:
        problems.append("the graph holds duplicate TRADE_OBSERVATION nodes")
    missing = preserved_ids - set(node_entity_ids)
    invented = set(node_entity_ids) - preserved_ids
    report["preservedButNotInGraph"] = len(missing)
    report["inGraphButNotPreserved"] = len(invented)
    if missing:
        problems.append("%d preserved observation(s) produced no node: %s"
                        % (len(missing), sorted(missing)[:3]))
    if invented:
        problems.append("%d graph node(s) correspond to no preserved record: %s"
                        % (len(invented), sorted(invented)[:3]))

    # 2. Identity and content are the PRESERVED ones, not re-derived.
    #
    # Hashed INDEPENDENTLY of gc.content_hash_of on purpose. Comparing the node's
    # hash against gc.content_hash_of(record) puts the same function on both sides,
    # so it proves only that the builder called what this script calls -- an
    # independent verifier once gutted content_hash_of to drop every list- and
    # dict-valued field and every "hash matches" assertion in this repository
    # stayed green. This recomputes canonically here instead.
    mismatched = [n["entityId"] for n in obs_nodes
                  if n["contentHash"] != _independent_hash(observations[n["entityId"]])]
    report["contentHashMismatches"] = len(mismatched)
    if mismatched:
        problems.append("%d node hash(es) do not match the preserved record" % len(mismatched))

    # 3. Provenance coverage: every observation links to the source IT names.
    by_from = {}
    for edge in edges:
        if edge["edgeType"] == "DERIVED_FROM":
            by_from.setdefault(edge["fromNodeId"], []).append(edge["toNodeId"])
    covered = wrong = uncovered = 0
    for node in obs_nodes:
        want = observations[node["entityId"]].get("sourceId")
        targets = by_from.get(node["nodeId"], [])
        if not targets:
            uncovered += 1
        elif targets == [gc.make_node_id("EVIDENCE_SOURCE", want)]:
            covered += 1
        else:
            wrong += 1
    report["provenanceCovered"] = covered
    report["provenanceWrongTarget"] = wrong
    report["provenanceMissing"] = uncovered
    if wrong:
        problems.append("%d observation(s) link to a source they do not name -- a crossed "
                        "edge silently reclassifies evidence between populations" % wrong)
    if uncovered:
        problems.append("%d observation(s) have no provenance edge" % uncovered)

    # 4. Populations, derived the sanctioned way (never denormalised onto a node).
    counts = {}
    for oid, rec in observations.items():
        counts[to.observation_population(rec, sources)] = counts.get(
            to.observation_population(rec, sources), 0) + 1
    report["populations"] = counts
    leaked = [n["entityId"] for n in obs_nodes
              if "population" in n or "population" in (n.get("metadata") or {})]
    report["populationDenormalisedOntoNode"] = len(leaked)
    if leaked:
        problems.append("population was copied onto %d node(s); it must stay derived from "
                        "the source's sourceType" % len(leaked))

    # Populations above are a SNAPSHOT, and a snapshot cannot tell you an observation
    # moved between populations -- the totals simply read differently and nothing
    # objects. Repointing one replay observation at a paper_trade source shifted
    # 221/29/9 to 220/30/9 while this script printed RECONCILED. The authoritative
    # check is the validator's, called here rather than restated.
    rebinding = []
    ve.check_observation_population_rebinding(
        list(observations.values()), list(sources.values()), rebinding, "")
    report["populationRebindings"] = len(rebinding)
    if rebinding:
        problems.append("%d observation(s) no longer point at the source they were MINTED "
                        "from, which moves them between evidence populations: %s"
                        % (len(rebinding), [f["entityId"] for f in rebinding][:3]))

    # 5. Orphans, split into the two kinds. The FALSE ones are what B-32 removed;
    #    the genuine ones must survive, or the check has been disarmed.
    #
    # The PRODUCTION check answers, and an independent recount CROSS-CHECKS it.
    #
    # This script used to reimplement orphan detection outright, which is a second
    # thing that can be right while the real one is wrong. Merely calling the
    # production check instead is not enough either: an adversarial verifier
    # disarmed `check_orphans` and this script still printed RECONCILED, because it
    # faithfully reported the disarmed answer. So both are computed and compared --
    # the production check is the ANSWER, the recount is a WITNESS, and disagreement
    # between them is itself the finding. Neither alone can be quietly switched off.
    orphan_findings = []
    validate_graph.check_orphans(nodes, edges, orphan_findings)
    orphan_node_ids = {f["affectedIds"][0] for f in orphan_findings
                       if f.get("category") == "ORPHAN_NODE"}
    orphan_sources = [n["entityId"] for n in src_nodes if n["nodeId"] in orphan_node_ids]

    touched_nodes = {e["fromNodeId"] for e in edges} | {e["toNodeId"] for e in edges}
    witness = {n["nodeId"] for n in nodes
               if n["nodeId"] not in touched_nodes and n["nodeType"] != "TRADER"}
    report["orphanCheckDisagreement"] = len(witness ^ orphan_node_ids)
    if witness != orphan_node_ids:
        problems.append(
            "the production orphan check and an independent recount disagree on %d "
            "node(s); one of them is wrong and a disarmed orphan check looks exactly "
            "like a clean corpus" % len(witness ^ orphan_node_ids))

    # A FLOOR derived from the RECORDS, not from the graph.
    #
    # The witness above recounts the same rule over the same edge set, so it is a
    # second implementation rather than a second opinion: adversarial verification
    # disarmed the production check and the witness together, and both agreed that
    # 30 real orphans were 0 while `orphanCheckDisagreement` read 0.
    #
    # This asks a question the graph cannot answer for itself. A source that no
    # observation cites and no evidence item references HAS no relationship to
    # represent, so it MUST come out orphaned however the graph was built. Reading
    # the records directly means an edit to the graph layer cannot move it.
    item_referenced = set()
    for path in sorted(globmod.glob(os.path.join(TI_ROOT, "evidence", "items", "*.json"))):
        with open(path, "r", encoding="utf-8") as handle:
            item = json.load(handle)
        if isinstance(item.get("sourceId"), str):
            item_referenced.add(item["sourceId"])
    cited_by_observations = {rec.get("sourceId") for rec in observations.values()}
    unreferenced = {sid for sid in sources
                    if sid not in cited_by_observations and sid not in item_referenced}
    report["sourcesUnreferencedByAnyRecord"] = len(unreferenced)
    missed = {sid for sid in unreferenced
              if gc.make_node_id("EVIDENCE_SOURCE", sid) not in orphan_node_ids}
    report["orphansTheGraphFailedToReport"] = len(missed)
    if missed:
        problems.append(
            "%d source(s) are referenced by NO observation and NO evidence item, yet "
            "the orphan check does not report them (%s). Derived from the records "
            "rather than the graph, so a disarmed graph-side check cannot hide it."
            % (len(missed), sorted(missed)[:3]))
    cited = {rec.get("sourceId") for rec in observations.values()}
    report["orphanSources"] = len(orphan_sources)
    report["orphanSourcesAlsoUncitedByAnyObservation"] = sum(
        1 for s in orphan_sources if s not in cited)
    falsely_orphaned = [s for s in orphan_sources if s in cited]
    report["falselyOrphanedSources"] = len(falsely_orphaned)
    if falsely_orphaned:
        problems.append("%d source(s) are cited by an observation yet still orphaned -- the "
                        "provenance edge is not being derived" % len(falsely_orphaned))

    # 6. No fabricated relationships: an observation states exactly one, its source.
    other = []
    obs_node_ids = {n["nodeId"] for n in obs_nodes}
    for edge in edges:
        if edge["edgeType"] == "DERIVED_FROM":
            continue
        if edge["fromNodeId"] in obs_node_ids or edge["toNodeId"] in obs_node_ids:
            other.append(edge["edgeType"])
    report["nonProvenanceEdgesTouchingObservations"] = len(other)
    if other:
        problems.append("observations carry edge type(s) %s that no preserved record states"
                        % sorted(set(other)))

    # 7. Dangling edges.
    dangling = [e["edgeId"] for e in edges
                if e["fromNodeId"] not in node_ids or e["toNodeId"] not in node_ids]
    report["danglingEdges"] = len(dangling)
    if dangling:
        problems.append("%d edge(s) reference a node that does not exist" % len(dangling))

    # 8. Determinism: the same inputs must produce the same graph.
    n2, e2, _f2, _r2 = gc.build_nodes_and_edges(REPO_ROOT, TI_ROOT, GRAPH_ROOT)
    same = (sorted(n["nodeId"] + n["contentHash"] for n in nodes)
            == sorted(n["nodeId"] + n["contentHash"] for n in n2)
            and sorted(e["edgeId"] for e in edges) == sorted(e["edgeId"] for e in e2))
    report["rebuildIsDeterministic"] = same
    if not same:
        problems.append("a second build of the same inputs produced a different graph")

    report["buildErrors"] = sum(1 for f in findings if f.get("severity") in ("ERROR", "FATAL"))
    if report["buildErrors"]:
        problems.append("%d build finding(s) at ERROR or above" % report["buildErrors"])

    return report, problems


def main():
    report, problems = reconcile()
    print("OBSERVATION <-> GRAPH RECONCILIATION -- derived, read-only, repairs nothing")
    for key in sorted(report):
        print("  %-42s %s" % (key, report[key]))
    if problems:
        print("\nDISCREPANCIES:")
        for p in problems:
            print("  - " + p)
        return 1
    print("\nRECONCILED (STRUCTURE ONLY): every observation record ON DISK appears once in "
          "the graph, linked to the source it names, and carries no relationship it does "
          "not state.")
    print("This is NOT a soundness verdict on the evidence. It compares the graph against "
          "the records; it cannot tell you a record was DELETED, or that an outcome or "
          "rMultiple inside one was altered -- both were demonstrated to pass. Those are "
          "questions for the corpus fingerprint and git history, not for a structural "
          "reconciliation.")
    print("Note: orphanSources counts sources no observation cites. Those are GENUINE and "
          "must stay visible -- suppressing them was the defect B-32 fixed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

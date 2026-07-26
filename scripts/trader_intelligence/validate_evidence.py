#!/usr/bin/env python3
"""PROGRAM-006 Phase 1A -- Evidence Intelligence Engine integrity validator
(ADR-008, Deliverable 11).

Pure Python standard library. NO NETWORK ACCESS. Strictly read-only against
every evidence record and (optionally) the built Knowledge Graph -- this
module never edits, corrects, or deletes anything. It only ever reports.

Mirrors validate_graph.py's report shape (one wrapper document embedding a
findings array) per evidence-integrity-report.schema.json, rather than
introducing a redundant standalone IntegrityFinding entity type.
"""
import argparse
import glob as globmod
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import graph_common as gc            # noqa: E402
import evidence_common as evc        # noqa: E402
import evidence_confidence as conf   # noqa: E402

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TI_ROOT = os.path.join(REPO_ROOT, "docs", "trader-intelligence")
EVIDENCE_ROOT = os.path.join(TI_ROOT, "evidence")


def _load_dir(dir_path, id_field):
    records = []
    if not os.path.isdir(dir_path):
        return records
    for path in sorted(globmod.glob(os.path.join(dir_path, "*.json"))):
        with open(path, "r", encoding="utf-8") as f:
            record = json.load(f)
        records.append(record)
    return records


def _finding(findings, finding_type, severity, entity_type, entity_id, message, now, metadata=None):
    findings.append({
        "findingId": "EVF%04d" % (len(findings) + 1),
        "severity": severity,
        "findingType": finding_type,
        "entityType": entity_type,
        "entityId": entity_id,
        "message": message,
        "detectedAt": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "resolutionStatus": "open",
        "resolutionNotes": None,
        "metadata": metadata or {},
    })


# ---------------------------------------------------------------------------
# 1. Orphans (ORPHANED_EVIDENCE / ORPHANED_LINK / ORPHANED_CLAIM)
# ---------------------------------------------------------------------------

def check_orphans(sources, items, claims, links, findings, now):
    source_ids = {s["sourceId"] for s in sources}
    item_ids = {i["evidenceId"] for i in items}
    claim_ids = {c["claimId"] for c in claims}

    for item in items:
        if item["sourceId"] not in source_ids:
            _finding(findings, "ORPHANED_EVIDENCE", "ERROR", "EVIDENCE_ITEM", item["evidenceId"],
                      "EvidenceItem references nonexistent sourceId %r." % (item["sourceId"],), now)

    for link in links:
        if link["evidenceId"] not in item_ids:
            _finding(findings, "ORPHANED_LINK", "ERROR", "EVIDENCE_CLAIM_LINK", link["linkId"],
                      "Link references nonexistent evidenceId %r." % (link["evidenceId"],), now)
        if link["claimId"] not in claim_ids:
            _finding(findings, "ORPHANED_LINK", "ERROR", "EVIDENCE_CLAIM_LINK", link["linkId"],
                      "Link references nonexistent claimId %r." % (link["claimId"],), now)

    links_by_claim = {}
    for link in links:
        links_by_claim.setdefault(link["claimId"], []).append(link)
    for claim in claims:
        if claim["evidenceCount"] > 0 and not links_by_claim.get(claim["claimId"]):
            _finding(findings, "ORPHANED_CLAIM", "ERROR", "CLAIM", claim["claimId"],
                      "Claim reports evidenceCount=%d but no matching EvidenceClaimLink records exist." % (
                          claim["evidenceCount"],), now)


# ---------------------------------------------------------------------------
# 2. Duplicate IDs (DUPLICATE_ID)
# ---------------------------------------------------------------------------

def check_duplicate_ids(sources, items, claims, links, contradictions, findings, now):
    for label, records, id_field in (
        ("EVIDENCE_SOURCE", sources, "sourceId"), ("EVIDENCE_ITEM", items, "evidenceId"),
        ("CLAIM", claims, "claimId"), ("EVIDENCE_CLAIM_LINK", links, "linkId"),
        ("CONTRADICTION_RECORD", contradictions, "contradictionId"),
    ):
        seen = {}
        for r in records:
            rid = r[id_field]
            seen[rid] = seen.get(rid, 0) + 1
        for rid, count in seen.items():
            if count > 1:
                _finding(findings, "DUPLICATE_ID", "FATAL", label, rid,
                          "%s appears %d times across stored records (expected exactly once)." % (rid, count), now)


# ---------------------------------------------------------------------------
# 3. Duplicate immutable content (DUPLICATE_IMMUTABLE_CONTENT)
# ---------------------------------------------------------------------------

def check_duplicate_immutable_content(items, findings, now):
    by_source_hash = {}
    for item in items:
        if item.get("evidenceStatus") == "superseded" or not item.get("contentHash"):
            continue
        key = (item["sourceId"], item["contentHash"])
        by_source_hash.setdefault(key, []).append(item["evidenceId"])
    for (source_id, content_hash), ids in by_source_hash.items():
        if len(ids) > 1:
            _finding(findings, "DUPLICATE_IMMUTABLE_CONTENT", "WARNING", "EVIDENCE_ITEM", ids[0],
                      "Evidence items %r from source %s share identical content hash %s but neither "
                      "supersedes the other -- likely an unintentional duplicate registration." % (
                          ids, source_id, content_hash), now, metadata={"allEvidenceIds": ids})


# ---------------------------------------------------------------------------
# 4. Inconsistent hash (INCONSISTENT_HASH)
# ---------------------------------------------------------------------------

def check_inconsistent_hash(items, findings, now):
    for item in items:
        expected = None
        if item.get("exactExcerpt") or item.get("normalizedObservation"):
            expected = gc.content_hash_of({
                "exactExcerpt": item.get("exactExcerpt"),
                "normalizedObservation": item.get("normalizedObservation"),
            })
        stored = item.get("contentHash")
        if stored != expected:
            _finding(findings, "INCONSISTENT_HASH", "ERROR", "EVIDENCE_ITEM", item["evidenceId"],
                      "Stored contentHash %r does not match hash recomputed from exactExcerpt/"
                      "normalizedObservation (%r) -- content may have been edited in place, which is "
                      "prohibited (corrections must supersede, never edit)." % (stored, expected), now)


# ---------------------------------------------------------------------------
# 5. Malformed provenance (MALFORMED_PROVENANCE)
# ---------------------------------------------------------------------------

def check_malformed_provenance(sources, items, findings, now):
    for source in sources:
        if source.get("storageLocationType") == "external" and not (
            source.get("externalAssetReference") and source.get("canonicalReference")
        ):
            _finding(findings, "MALFORMED_PROVENANCE", "ERROR", "EVIDENCE_SOURCE", source["sourceId"],
                      "storageLocationType='external' requires both externalAssetReference and "
                      "canonicalReference to be set.", now)
        if source.get("provenanceStatus") not in evc.PROVENANCE_STATUSES:
            _finding(findings, "MALFORMED_PROVENANCE", "ERROR", "EVIDENCE_SOURCE", source["sourceId"],
                      "Unknown provenanceStatus %r." % (source.get("provenanceStatus"),), now)

    for item in items:
        if not (item.get("exactExcerpt") or item.get("normalizedObservation")):
            _finding(findings, "MALFORMED_PROVENANCE", "WARNING", "EVIDENCE_ITEM", item["evidenceId"],
                      "EvidenceItem carries neither exactExcerpt nor normalizedObservation -- no "
                      "traceable content is recorded for this item.", now)


# ---------------------------------------------------------------------------
# 6. Lifecycle sequence validity (INVALID_LIFECYCLE_SEQUENCE)
# ---------------------------------------------------------------------------

_GENESIS_EVENT_TYPE_BY_ENTITY_TYPE = {
    "EVIDENCE_CLAIM_LINK": "linked",  # a link's genesis event is "linked", not "created"
}


def _lifecycle_seq(event):
    # eventId always ends "...|%03d" with a monotonic per-entity sequence
    # (evidence_common.next_lifecycle_event_id) -- more reliable than
    # timestamp string comparison when two events share the same second.
    return int(event["eventId"].rsplit("|", 1)[1])


def check_lifecycle_sequences(lifecycle_events, known_ids_by_type, findings, now):
    by_entity = {}
    for event in lifecycle_events:
        by_entity.setdefault((event["entityType"], event["entityId"]), []).append(event)

    for (entity_type, entity_id), events in by_entity.items():
        events.sort(key=lambda e: (e["timestamp"], _lifecycle_seq(e)))
        expected_genesis = _GENESIS_EVENT_TYPE_BY_ENTITY_TYPE.get(entity_type, "created")
        if events[0]["eventType"] != expected_genesis:
            _finding(findings, "INVALID_LIFECYCLE_SEQUENCE", "ERROR", entity_type, entity_id,
                      "First lifecycle event for %s is %r, expected %r." % (
                          entity_id, events[0]["eventType"], expected_genesis), now)
        known = known_ids_by_type.get(entity_type)
        if known is not None and entity_id not in known:
            _finding(findings, "INVALID_LIFECYCLE_SEQUENCE", "WARNING", entity_type, entity_id,
                      "Lifecycle events reference %s %r which no longer has a stored record." % (
                          entity_type, entity_id), now)


# ---------------------------------------------------------------------------
# 7. Confidence/count mismatch (CONFIDENCE_COUNT_MISMATCH)
# ---------------------------------------------------------------------------

def check_confidence_count_mismatch(claims, links, items, findings, now):
    items_by_id = {i["evidenceId"]: i for i in items}
    links_by_claim = {}
    for link in links:
        links_by_claim.setdefault(link["claimId"], []).append(dict(link))

    for claim in claims:
        claim_links = links_by_claim.get(claim["claimId"], [])
        state, score, counts, _explanation = conf.compute_confidence(claim_links, items_by_id)
        for field, expected in counts.items():
            if claim.get(field) != expected:
                _finding(findings, "CONFIDENCE_COUNT_MISMATCH", "ERROR", "CLAIM", claim["claimId"],
                          "Stored %s=%r does not match recomputed value %r from current links." % (
                              field, claim.get(field), expected), now)
        if claim.get("confidenceState") != state:
            _finding(findings, "CONFIDENCE_COUNT_MISMATCH", "ERROR", "CLAIM", claim["claimId"],
                      "Stored confidenceState=%r does not match recomputed state %r -- confidence "
                      "appears stale (was recompute_claim_confidence run after the last link change?)." % (
                          claim.get("confidenceState"), state), now)
        elif claim.get("confidenceScore") != score:
            _finding(findings, "CONFIDENCE_COUNT_MISMATCH", "WARNING", "CLAIM", claim["claimId"],
                      "Stored confidenceScore=%r does not match recomputed score %r." % (
                          claim.get("confidenceScore"), score), now)


# ---------------------------------------------------------------------------
# 8. Unresolved supersession chains (UNRESOLVED_SUPERSESSION_CHAIN)
# ---------------------------------------------------------------------------

def check_unresolved_supersession_chains(items, findings, now):
    superseded_by = {}
    for item in items:
        if item.get("supersedesEvidenceId"):
            superseded_by[item["supersedesEvidenceId"]] = item["evidenceId"]

    for item in items:
        if item.get("evidenceStatus") == "superseded" and item["evidenceId"] not in superseded_by:
            _finding(findings, "UNRESOLVED_SUPERSESSION_CHAIN", "ERROR", "EVIDENCE_ITEM", item["evidenceId"],
                      "EvidenceItem is marked evidenceStatus='superseded' but no other item's "
                      "supersedesEvidenceId points back to it -- the supersession chain is broken.", now)


# ---------------------------------------------------------------------------
# 9/10. Circular derivation / supersession (CIRCULAR_DERIVATION / CIRCULAR_SUPERSESSION)
# ---------------------------------------------------------------------------

def _find_cycle(adjacency):
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {node: WHITE for node in adjacency}
    cycles = []

    def visit(node, stack):
        color[node] = GRAY
        stack.append(node)
        for nxt in adjacency.get(node, []):
            if color.get(nxt, WHITE) == GRAY:
                cycles.append(stack[stack.index(nxt):] + [nxt])
            elif color.get(nxt, WHITE) == WHITE:
                visit(nxt, stack)
        stack.pop()
        color[node] = BLACK

    for node in list(adjacency.keys()):
        if color.get(node, WHITE) == WHITE:
            visit(node, [])
    return cycles


def check_circular_derivation(items, findings, now):
    adjacency = {i["evidenceId"]: ([i["parentEvidenceId"]] if i.get("parentEvidenceId") else []) for i in items}
    for cycle in _find_cycle(adjacency):
        _finding(findings, "CIRCULAR_DERIVATION", "FATAL", "EVIDENCE_ITEM", cycle[0],
                  "Circular parentEvidenceId chain: %s" % (" -> ".join(cycle),), now, metadata={"cycle": cycle})


def check_circular_supersession(items, findings, now):
    adjacency = {i["evidenceId"]: ([i["supersedesEvidenceId"]] if i.get("supersedesEvidenceId") else []) for i in items}
    for cycle in _find_cycle(adjacency):
        _finding(findings, "CIRCULAR_SUPERSESSION", "FATAL", "EVIDENCE_ITEM", cycle[0],
                  "Circular supersedesEvidenceId chain: %s" % (" -> ".join(cycle),), now, metadata={"cycle": cycle})


# ---------------------------------------------------------------------------
# 11. Invalid contradiction records (INVALID_CONTRADICTION_RECORD)
# ---------------------------------------------------------------------------

def check_contradiction_records(contradictions, claims, findings, now):
    claim_ids = {c["claimId"] for c in claims}
    for cr in contradictions:
        cid = cr["contradictionId"]
        if cr["claimAId"] == cr["claimBId"]:
            _finding(findings, "INVALID_CONTRADICTION_RECORD", "FATAL", "CONTRADICTION_RECORD", cid,
                      "ContradictionRecord references the same claim (%r) as both sides." % (cr["claimAId"],), now)
        if cr["claimAId"] not in claim_ids:
            _finding(findings, "INVALID_CONTRADICTION_RECORD", "ERROR", "CONTRADICTION_RECORD", cid,
                      "claimAId %r does not exist." % (cr["claimAId"],), now)
        if cr["claimBId"] not in claim_ids:
            _finding(findings, "INVALID_CONTRADICTION_RECORD", "ERROR", "CONTRADICTION_RECORD", cid,
                      "claimBId %r does not exist." % (cr["claimBId"],), now)
        if cr.get("contradictionType") not in evc.CONTRADICTION_TYPES:
            _finding(findings, "INVALID_CONTRADICTION_RECORD", "ERROR", "CONTRADICTION_RECORD", cid,
                      "Unknown contradictionType %r." % (cr.get("contradictionType"),), now)
        if cr.get("severity") not in evc.CONTRADICTION_SEVERITIES:
            _finding(findings, "INVALID_CONTRADICTION_RECORD", "ERROR", "CONTRADICTION_RECORD", cid,
                      "Unknown severity %r." % (cr.get("severity"),), now)
        if cr.get("status") not in evc.CONTRADICTION_STATUSES:
            _finding(findings, "INVALID_CONTRADICTION_RECORD", "ERROR", "CONTRADICTION_RECORD", cid,
                      "Unknown status %r." % (cr.get("status"),), now)


# ---------------------------------------------------------------------------
# 12. Invalid claim scope (INVALID_CLAIM_SCOPE)
# ---------------------------------------------------------------------------

def check_claim_scope(claims, findings, now):
    for claim in claims:
        if claim.get("claimType") not in evc.CLAIM_TYPES:
            _finding(findings, "INVALID_CLAIM_SCOPE", "ERROR", "CLAIM", claim["claimId"],
                      "Unknown claimType %r." % (claim.get("claimType"),), now)
        if claim.get("confidenceState") not in evc.CONFIDENCE_STATES:
            _finding(findings, "INVALID_CLAIM_SCOPE", "ERROR", "CLAIM", claim["claimId"],
                      "Unknown confidenceState %r." % (claim.get("confidenceState"),), now)
        expected_fingerprint = evc.compute_claim_fingerprint(
            claim.get("normalizedClaim"), claim.get("traderId"), claim.get("strategyFamilyId"),
            claim.get("timeframe"), claim.get("session"), claim.get("marketCondition"))
        if claim.get("normalizedFingerprint") != expected_fingerprint:
            _finding(findings, "INVALID_CLAIM_SCOPE", "ERROR", "CLAIM", claim["claimId"],
                      "Stored normalizedFingerprint does not match the hash recomputed from this claim's "
                      "own normalizedClaim + scope fields -- either the claim text/scope changed after "
                      "creation (prohibited) or the fingerprint was computed inconsistently.", now)


# ---------------------------------------------------------------------------
# 13. Unsupported schema versions (UNSUPPORTED_SCHEMA_VERSION)
# ---------------------------------------------------------------------------

def check_schema_versions(sources, items, claims, links, contradictions, findings, now):
    for label, records, id_field in (
        ("EVIDENCE_SOURCE", sources, "sourceId"), ("EVIDENCE_ITEM", items, "evidenceId"),
        ("CLAIM", claims, "claimId"), ("EVIDENCE_CLAIM_LINK", links, "linkId"),
        ("CONTRADICTION_RECORD", contradictions, "contradictionId"),
    ):
        for r in records:
            v = r.get("schemaVersion")
            if not isinstance(v, int) or v > evc.SCHEMA_VERSION:
                _finding(findings, "UNSUPPORTED_SCHEMA_VERSION", "ERROR", label, r[id_field],
                          "Record has schemaVersion=%r; this validator supports up to %d." % (
                              v, evc.SCHEMA_VERSION), now)


# ---------------------------------------------------------------------------
# 14. Graph relationship checks (MISSING_GRAPH_RELATIONSHIP / GRAPH_REFERENCES_NONEXISTENT_EVIDENCE)
# ---------------------------------------------------------------------------

def _iter_strategy_rule_paths(ti_root):
    return sorted(globmod.glob(os.path.join(ti_root, "traders", "*", "rules", "*.json")))


def check_graph_relationships(repo_root, ti_root, links, claims, findings, now):
    claim_ids = {c["claimId"] for c in claims}
    for path in _iter_strategy_rule_paths(ti_root):
        with open(path, "r", encoding="utf-8") as f:
            rule = json.load(f)
        for cid in rule.get("originatingClaimIds", []) or []:
            if cid not in claim_ids:
                _finding(findings, "GRAPH_REFERENCES_NONEXISTENT_EVIDENCE", "ERROR", "STRATEGY_RULE",
                          rule.get("ruleId", path), "originatingClaimIds references nonexistent claimId %r." % (cid,), now)

    try:
        graph_root = os.path.join(ti_root, "graph")
        nodes, edges, _construction_findings, _raw = gc.build_nodes_and_edges(repo_root, ti_root, graph_root)
    except Exception as exc:  # pragma: no cover - defensive only, graph build has its own tests
        _finding(findings, "MISSING_GRAPH_RELATIONSHIP", "WARNING", "KNOWLEDGE_GRAPH", "n/a",
                  "Could not build the Knowledge Graph to cross-check evidence links: %s" % (exc,), now)
        return

    node_by_entity_id = {n["entityId"]: n["nodeId"] for n in nodes}
    edge_pairs = {(e["fromNodeId"], e["toNodeId"], e["edgeType"]) for e in edges}
    relationship_to_edge_type = {
        "supports": "SUPPORTS", "exemplifies": "EXEMPLIFIES", "contradicts": "CONTRADICTS",
        "weakens": "WEAKENS", "contextualizes": "CONTEXTUALIZES", "qualifies": "QUALIFIES",
        "supersedes": "SUPERSEDES", "unresolved": "UNRESOLVED",
    }
    for link in links:
        from_node = node_by_entity_id.get(link["evidenceId"])
        to_node = node_by_entity_id.get(link["claimId"])
        edge_type = relationship_to_edge_type.get(link["relationshipType"])
        if from_node is None or to_node is None or edge_type is None:
            continue
        if (from_node, to_node, edge_type) not in edge_pairs:
            _finding(findings, "MISSING_GRAPH_RELATIONSHIP", "ERROR", "EVIDENCE_CLAIM_LINK", link["linkId"],
                      "Link exists in evidence storage but no corresponding %s edge was found in the "
                      "built Knowledge Graph -- run build_graph.py to regenerate." % (edge_type,), now)


# ---------------------------------------------------------------------------
# 15. Production rule linkage without approval (PRODUCTION_RULE_LINKAGE_WITHOUT_APPROVAL)
# ---------------------------------------------------------------------------

def check_production_rule_linkage(ti_root, findings, now):
    decisions_dir = os.path.join(ti_root, "graph", "decisions")
    decisions_by_affected = {}
    for path in sorted(globmod.glob(os.path.join(decisions_dir, "*.json"))):
        with open(path, "r", encoding="utf-8") as f:
            decision = json.load(f)
        for affected in decision.get("affectedEntityIds", []) or []:
            decisions_by_affected.setdefault(affected, []).append(decision)

    for path in _iter_strategy_rule_paths(ti_root):
        with open(path, "r", encoding="utf-8") as f:
            rule = json.load(f)
        if not rule.get("originatingClaimIds"):
            continue
        state = rule.get("promotionState")
        if state is None or state not in getattr(gc, "PROMOTION_STATES", []):
            continue
        idx = gc.PROMOTION_STATES.index(state)
        if idx >= gc.PROMOTION_STATES.index("IMPLEMENTATION_APPROVED"):
            decisions = decisions_by_affected.get(rule.get("ruleId"), [])
            if not any(d.get("status") == "active" and d.get("implementationAuthorization") for d in decisions):
                _finding(findings, "PRODUCTION_RULE_LINKAGE_WITHOUT_APPROVAL", "FATAL", "STRATEGY_RULE",
                          rule.get("ruleId", path),
                          "Rule has originatingClaimIds linked and promotionState=%s with no active "
                          "OwnerDecision granting implementationAuthorization -- claim linkage must never "
                          "itself authorize promotion." % (state,), now)


# ---------------------------------------------------------------------------
# 16. Mislabeled synthetic fixtures (MISLABELED_SYNTHETIC_FIXTURE)
# ---------------------------------------------------------------------------

def check_synthetic_leakage(sources, items, claims, findings, now, is_production):
    if not is_production:
        return
    for label, records, id_field, text_fields in (
        ("EVIDENCE_SOURCE", sources, "sourceId", ("title", "transcriptReference")),
        ("EVIDENCE_ITEM", items, "evidenceId", ("exactExcerpt", "normalizedObservation")),
        ("CLAIM", claims, "claimId", ("normalizedClaim",)),
    ):
        for r in records:
            blob = " ".join(str(r.get(f) or "") for f in text_fields) + " " + json.dumps(r.get("metadata") or {})
            if evc.contains_synthetic_markers(blob):
                _finding(findings, "MISLABELED_SYNTHETIC_FIXTURE", "FATAL", label, r[id_field],
                          "Record stored under the production evidence tree contains synthetic-fixture "
                          "markers (%r) -- synthetic test data must never be mistaken for real evidence." % (
                              evc.SYNTHETIC_MARKERS,), now)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def run_integrity_checks(evidence_root, repo_root=None, ti_root=None, is_production=True):
    now = datetime.now(timezone.utc)
    sources = _load_dir(os.path.join(evidence_root, "sources"), "sourceId")
    items = _load_dir(os.path.join(evidence_root, "items"), "evidenceId")
    claims = _load_dir(os.path.join(evidence_root, "claims"), "claimId")
    links = _load_dir(os.path.join(evidence_root, "links"), "linkId")
    contradictions = _load_dir(os.path.join(evidence_root, "contradictions"), "contradictionId")
    lifecycle_events = _load_dir(os.path.join(evidence_root, "lifecycle"), "eventId")

    findings = []
    check_orphans(sources, items, claims, links, findings, now)
    check_duplicate_ids(sources, items, claims, links, contradictions, findings, now)
    check_duplicate_immutable_content(items, findings, now)
    check_inconsistent_hash(items, findings, now)
    check_malformed_provenance(sources, items, findings, now)
    known_ids_by_type = {
        "EVIDENCE_SOURCE": {s["sourceId"] for s in sources}, "EVIDENCE_ITEM": {i["evidenceId"] for i in items},
        "CLAIM": {c["claimId"] for c in claims}, "EVIDENCE_CLAIM_LINK": {l["linkId"] for l in links},
        "CONTRADICTION_RECORD": {c["contradictionId"] for c in contradictions},
    }
    check_lifecycle_sequences(lifecycle_events, known_ids_by_type, findings, now)
    check_confidence_count_mismatch(claims, links, items, findings, now)
    check_unresolved_supersession_chains(items, findings, now)
    check_circular_derivation(items, findings, now)
    check_circular_supersession(items, findings, now)
    check_contradiction_records(contradictions, claims, findings, now)
    check_claim_scope(claims, findings, now)
    check_schema_versions(sources, items, claims, links, contradictions, findings, now)
    check_synthetic_leakage(sources, items, claims, findings, now, is_production)

    if repo_root and ti_root:
        check_graph_relationships(repo_root, ti_root, links, claims, findings, now)
        check_production_rule_linkage(ti_root, findings, now)

    summary = {"INFO": 0, "WARNING": 0, "ERROR": 0, "FATAL": 0}
    for f in findings:
        summary[f["severity"]] += 1

    seq = 1
    report = {
        "generated": True,
        "integrityReportId": evc.make_integrity_report_id(now, seq),
        "generatedAt": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "validatorVersion": "1.0.0",
        "findings": findings,
        "summary": summary,
    }
    return report


def main():
    parser = argparse.ArgumentParser(description="Validate PROGRAM-006 Evidence Intelligence Engine data integrity.")
    parser.add_argument("--repo-root", default=REPO_ROOT)
    parser.add_argument("--ti-root", default=None)
    parser.add_argument("--evidence-root", default=None)
    parser.add_argument("--no-graph-check", action="store_true", help="Skip cross-checking against the built Knowledge Graph.")
    parser.add_argument("--allow-synthetic", action="store_true", help="Do not flag synthetic-fixture markers (use only against a test fixture tree).")
    args = parser.parse_args()

    repo_root = os.path.abspath(args.repo_root)
    ti_root = args.ti_root or os.path.join(repo_root, "docs", "trader-intelligence")
    evidence_root = args.evidence_root or os.path.join(ti_root, "evidence")

    report = run_integrity_checks(
        evidence_root,
        repo_root=None if args.no_graph_check else repo_root,
        ti_root=None if args.no_graph_check else ti_root,
        is_production=not args.allow_synthetic,
    )

    out_path = os.path.join(evidence_root, "reports", "integrity-report.json")
    gc.atomic_write_text(out_path, gc.pretty_json(report))
    print("Wrote %s" % out_path)
    print("Summary: %r" % (report["summary"],))
    return 0 if report["summary"]["FATAL"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

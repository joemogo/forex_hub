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
import re
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


def _check_missing_artifact(findings, source, rel, sources_by_id, now):
    """A repository source whose artifact is gone -- resolvable, or not.

    A missing artifact is not always lost evidence. The real case (B-28): a DRY RUN
    wrote a capture file, a source was registered for it, the dry-run cleanup deleted
    the file, and the --write run 27 seconds later produced a BYTE-IDENTICAL artifact
    registered under a different sourceId. The observation citing the first source is
    undamaged and its evidence demonstrably survives -- at another path.

    Recording that with `artifactSupersededBy` keeps provenance walkable without
    rewriting anything: the original repositoryPath still says what this source
    described, and the supersession is a new fact ABOUT the record.

    But a supersession field is also a new way to LAUNDER broken provenance -- point a
    dangling source at any healthy one and the warning disappears. So the claim is
    never taken at its word. It resolves only when the named source exists, ITS artifact
    exists, and the two contentHashes are equal, which is what makes "the same artifact
    survives elsewhere" a checkable fact rather than an assertion.

    A supersession that fails any of those is an ERROR, not a warning, and deliberately
    louder than the plain missing artifact it replaced: a dangling path is a visible
    gap, while a false supersession is a gap wearing a resolution.
    """
    superseded_by = source.get("artifactSupersededBy")
    if not superseded_by:
        _finding(findings, "UNRESOLVABLE_ARTIFACT", "WARNING", "EVIDENCE_SOURCE",
                  source["sourceId"],
                  "repositoryPath %r does not exist, so this source cannot be "
                  "walked back to the artifact it describes." % (rel,), now)
        return

    target = sources_by_id.get(superseded_by)
    if target is None:
        _finding(findings, "UNVERIFIED_SUPERSESSION", "ERROR", "EVIDENCE_SOURCE",
                  source["sourceId"],
                  "artifactSupersededBy names %r, which is not a registered "
                  "EvidenceSource." % (superseded_by,), now)
        return

    target_rel = target.get("repositoryPath")
    if not target_rel or not os.path.exists(os.path.join(REPO_ROOT, target_rel)):
        _finding(findings, "UNVERIFIED_SUPERSESSION", "ERROR", "EVIDENCE_SOURCE",
                  source["sourceId"],
                  "artifactSupersededBy names %s, whose own artifact %r is missing -- "
                  "the supersession resolves to nothing."
                  % (superseded_by, target_rel), now)
        return

    own_hash = source.get("contentHash")
    target_hash = target.get("contentHash")
    if not own_hash or not target_hash or own_hash != target_hash:
        _finding(findings, "UNVERIFIED_SUPERSESSION", "ERROR", "EVIDENCE_SOURCE",
                  source["sourceId"],
                  "artifactSupersededBy names %s, but the contentHashes differ (%s vs "
                  "%s), so the surviving artifact is NOT the one this source described."
                  % (superseded_by, (own_hash or "unset")[:12],
                     (target_hash or "unset")[:12]), now)
        return
    # Resolved: identical content exists at a recorded path. No finding.


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

def check_observation_population_rebinding(observations, sources, findings, now):
    """Does an observation still point at the source it was MINTED from?

    Population -- HISTORICAL / FORWARD / RECONSTRUCTED -- is derived from the
    source's `sourceType` and deliberately never stored on the observation. That
    keeps one source of truth, and it has a consequence nothing was checking:
    repointing an observation's `sourceId` at a source of a different type silently
    MOVES it between populations. A replay trade becomes a forward trade, forward
    performance statistics absorb simulated fills, and every diagnostic stays green
    because each one individually is still self-consistent.

    Demonstrated, not hypothesised: repointing one replay observation at a
    paper_trade source moved populations from 221/29/9 to 220/30/9 while the graph
    reconciliation printed RECONCILED and this validator reported zero findings.

    The cross-check is the observation's OWN record. The importer stamps
    `notes: "captureBasis=... sourceType=..."` at mint time, so the record carries
    what its source was WHEN THE OBSERVATION WAS CREATED -- present on all 259
    preserved records. If that disagrees with the source's type today, one of them
    changed after the fact, and which one is not knowable from here.

    ERROR, not WARNING: this is the corpus's most consequential silent failure, and
    it is reported rather than repaired. Nothing here rewrites `sourceId`, `notes`
    or any source record -- a mismatch is a contradiction for a human to resolve,
    not something to normalise away.

    Absent or unparseable `notes` is NOT reported. It is a pre-existing,
    schema-permitted state, and inventing a mint-time type for a record that never
    recorded one would be the fabrication this check exists to catch.
    """
    by_id = {s["sourceId"]: s for s in sources if s.get("sourceId")}
    for obs in observations:
        match = _MINTED_SOURCE_TYPE_RE.search(obs.get("notes") or "")
        if not match:
            continue
        minted = match.group(1)
        source = by_id.get(obs.get("sourceId"))
        if source is None:
            continue          # already reported as a missing reference elsewhere
        actual = source.get("sourceType")
        if actual and actual != minted:
            _finding(findings, "POPULATION_REBINDING", "ERROR", "TRADE_OBSERVATION",
                      obs.get("observationId"),
                      "Observation was minted from a %r source but its sourceId now names "
                      "%s, whose sourceType is %r. Population is derived from sourceType, so "
                      "this moves the observation between evidence populations."
                      % (minted, obs.get("sourceId"), actual), now)


#: The importer stamps "captureBasis=<basis> sourceType=<type>" into notes at
#: mint time. That string is the only record of what the source was WHEN the
#: observation was created, which is what makes the rebinding check possible.
_MINTED_SOURCE_TYPE_RE = re.compile(r"sourceType=([A-Za-z_]+)")


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

def check_duplicate_ids(sources, items, claims, links, contradictions, findings, now, extra=None):
    for label, records, id_field in (
        ("EVIDENCE_SOURCE", sources, "sourceId"), ("EVIDENCE_ITEM", items, "evidenceId"),
        ("CLAIM", claims, "claimId"), ("EVIDENCE_CLAIM_LINK", links, "linkId"),
        ("CONTRADICTION_RECORD", contradictions, "contradictionId"),
    ) + tuple(extra or ()):
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
    # Needed to verify an artifactSupersededBy claim against the source it names.
    sources_by_id = {src["sourceId"]: src for src in sources if src.get("sourceId")}
    for source in sources:
        if source.get("storageLocationType") == "external" and not (
            source.get("externalAssetReference") and source.get("canonicalReference")
        ):
            _finding(findings, "MALFORMED_PROVENANCE", "ERROR", "EVIDENCE_SOURCE", source["sourceId"],
                      "storageLocationType='external' requires both externalAssetReference and "
                      "canonicalReference to be set.", now)
        # A repository-stored source whose artifact is GONE. The validator never
        # looked at repositoryPath, so a source pointing at a deleted or renamed
        # capture file passed cleanly -- and one did: EVSRC|MOGO|20260818|015 cites
        # a file removed during a duplicate cleanup, while the observation that
        # cites it is intact. Provenance that cannot be walked back to an artifact
        # is not provenance, and WARNING rather than ERROR because the observation
        # itself is undamaged and its content survives under another path.
        # Only a path that is SET but missing is reported. An absent repositoryPath
        # is a pre-existing, schema-permitted state that several fixtures rely on;
        # turning it into an error here would be changing a rule while fixing a
        # different one.
        if source.get("storageLocationType") == "repository":
            rel = source.get("repositoryPath")
            if rel and not os.path.exists(os.path.join(REPO_ROOT, rel)):
                _check_missing_artifact(findings, source, rel, sources_by_id, now)
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
    # MOGO-020: EvidenceQuestions are created WITHOUT a lifecycle event --
    # evidence_questions.create_question() has never emitted one, and MOGO-020
    # deliberately did not start backdating a synthetic "created" event onto the
    # 281 existing records. A question's first lifecycle event is therefore its
    # first human adjudication, whose eventType is "reviewed".
    "EVIDENCE_QUESTION": "reviewed",
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

# ---------------------------------------------------------------------------
# PROGRAM-006 Phase 1B (ADR-009, Deliverable 19) additive integrity checks
# ---------------------------------------------------------------------------

def check_orphaned_segments(intakes, segments, findings, now):
    intake_ids = {m["intakeId"] for m in intakes}
    for seg in segments:
        if seg["intakeId"] not in intake_ids:
            _finding(findings, "ORPHANED_SEGMENT", "ERROR", "TRANSCRIPT_SEGMENT", seg["segmentId"],
                      "TranscriptSegment references nonexistent intakeId %r." % (seg["intakeId"],), now)


def check_missing_transcript_locator(items, findings, now):
    for item in items:
        if item.get("extractionMethod") == "manual_transcription" and not item.get("sourceLocator"):
            _finding(findings, "MISSING_TRANSCRIPT_LOCATOR", "WARNING", "EVIDENCE_ITEM", item["evidenceId"],
                      "extractionMethod='manual_transcription' but sourceLocator is null -- transcript-derived "
                      "evidence should preserve its originating segment locator.", now)


def check_annotation_references(annotations, intakes, segments, findings, now):
    intake_ids = {m["intakeId"] for m in intakes}
    segment_ids = {s["segmentId"] for s in segments}
    for a in annotations:
        if a["intakeId"] not in intake_ids:
            _finding(findings, "INVALID_ANNOTATION_REFERENCE", "ERROR", "MANUAL_ANNOTATION", a["annotationId"],
                      "Annotation references nonexistent intakeId %r." % (a["intakeId"],), now)
        if a["segmentId"] not in segment_ids:
            _finding(findings, "INVALID_ANNOTATION_REFERENCE", "ERROR", "MANUAL_ANNOTATION", a["annotationId"],
                      "Annotation references nonexistent segmentId %r." % (a["segmentId"],), now)


def check_directness_and_certainty_present(items, findings, now):
    for item in items:
        has_directness = item.get("directness") is not None
        has_certainty = item.get("extractionCertainty") is not None
        if has_directness != has_certainty:
            _finding(findings, "MISSING_DIRECTNESS_OR_CERTAINTY", "WARNING", "EVIDENCE_ITEM", item["evidenceId"],
                      "directness=%r but extractionCertainty=%r -- Phase 1B evidence should set both together, "
                      "or leave both null (Phase 1A legacy record)." % (
                          item.get("directness"), item.get("extractionCertainty")), now)


def check_claim_candidate_without_evidence(claims, links, findings, now):
    links_by_claim = {}
    for l in links:
        links_by_claim.setdefault(l["claimId"], []).append(l)
    for c in claims:
        if c["claimStatus"] == "pending_review" and not links_by_claim.get(c["claimId"]):
            _finding(findings, "CLAIM_CANDIDATE_WITHOUT_EVIDENCE", "ERROR", "CLAIM", c["claimId"],
                      "claimStatus='pending_review' but no EvidenceClaimLink references this claim.", now)


def check_rule_candidate_proposals(proposals, claims, findings, now):
    claim_ids = {c["claimId"] for c in claims}
    for p in proposals:
        if not p.get("originatingClaimIds"):
            _finding(findings, "RULE_CANDIDATE_WITHOUT_CLAIM", "FATAL", "RULE_CANDIDATE_PROPOSAL", p["proposalId"],
                      "originatingClaimIds is empty.", now)
        else:
            missing = [cid for cid in p["originatingClaimIds"] if cid not in claim_ids]
            if missing:
                _finding(findings, "RULE_CANDIDATE_WITHOUT_CLAIM", "ERROR", "RULE_CANDIDATE_PROPOSAL", p["proposalId"],
                          "originatingClaimIds references nonexistent claims %r." % (missing,), now)
        if p.get("status") not in evc.RULE_CANDIDATE_STATUSES:
            _finding(findings, "RULE_CANDIDATE_INCORRECTLY_ACTIVE", "FATAL", "RULE_CANDIDATE_PROPOSAL", p["proposalId"],
                      "status=%r is not one of the non-executable values %r -- a RuleCandidateProposal must "
                      "never claim an execution-implying status." % (p.get("status"), evc.RULE_CANDIDATE_STATUSES), now)


def check_questions_reference_existing_claims(questions, claims, findings, now):
    claim_ids = {c["claimId"] for c in claims}
    for q in questions:
        if q.get("claimId") and q["claimId"] not in claim_ids:
            _finding(findings, "QUESTION_REFERENCES_NONEXISTENT_CLAIM", "ERROR", "EVIDENCE_QUESTION", q["questionId"],
                      "claimId %r does not exist." % (q["claimId"],), now)


def check_review_queue_references(queue_entries, known_ids_by_entity_type, findings, now):
    for e in queue_entries:
        known = known_ids_by_entity_type.get(e["entityType"])
        if known is not None and e["entityId"] not in known:
            _finding(findings, "REVIEW_QUEUE_REFERENCES_NONEXISTENT_ENTITY", "ERROR", "REVIEW_QUEUE_ENTRY", e["queueEntryId"],
                      "References nonexistent %s %r." % (e["entityType"], e["entityId"]), now)


def check_approved_intake_findings(intakes, findings, now):
    for m in intakes:
        if m["intakeStatus"] == "approved" and m.get("warnings"):
            _finding(findings, "APPROVED_INTAKE_WITH_UNRESOLVED_FINDINGS", "WARNING", "INTAKE_MANIFEST", m["intakeId"],
                      "intakeStatus='approved' but warnings list is still non-empty: %r." % (m["warnings"],), now)


def check_approved_source_licensing(intakes, findings, now):
    for m in intakes:
        if m["intakeStatus"] == "approved" and m.get("licensingStatus") in ("unknown", "restricted_third_party"):
            _finding(findings, "APPROVED_SOURCE_WITH_UNRESOLVED_LICENSING", "FATAL", "INTAKE_MANIFEST", m["intakeId"],
                      "intakeStatus='approved' but licensingStatus=%r is still unresolved." % (m["licensingStatus"],), now)


def check_segment_hashes(segments, findings, now):
    for seg in segments:
        expected = evc.text_sha256(seg["rawText"])
        if seg.get("textHash") != expected:
            _finding(findings, "SEGMENT_HASH_MISMATCH", "ERROR", "TRANSCRIPT_SEGMENT", seg["segmentId"],
                      "Stored textHash does not match the hash recomputed from rawText -- content may have "
                      "been edited in place, which is prohibited.", now)


def check_intake_content_hash(intakes, findings, now):
    for m in intakes:
        if m.get("contentHash") is not None and not isinstance(m["contentHash"], str):
            _finding(findings, "TRANSCRIPT_HASH_MISMATCH", "ERROR", "INTAKE_MANIFEST", m["intakeId"],
                      "contentHash is set but is not a string hash value.", now)


def check_segment_sequence_and_line_ranges(segments, findings, now):
    by_intake = {}
    for seg in segments:
        by_intake.setdefault(seg["intakeId"], []).append(seg)
    for intake_id, segs in sorted(by_intake.items()):
        seqs = sorted(s["sequenceNumber"] for s in segs)
        if seqs != list(range(1, len(seqs) + 1)):
            _finding(findings, "SEGMENT_SEQUENCE_GAP", "ERROR", "INTAKE_MANIFEST", intake_id,
                      "Segment sequence numbers are not a contiguous 1..N run: found %r." % (seqs,), now)
        seen_timestamps = {}
        for s in segs:
            if s.get("startTimestamp"):
                seen_timestamps.setdefault(s["startTimestamp"], []).append(s["segmentId"])
        for ts, ids in sorted(seen_timestamps.items()):
            if len(ids) > 1:
                _finding(findings, "OVERLAPPING_SEGMENT_TIMESTAMPS", "WARNING", "TRANSCRIPT_SEGMENT", sorted(ids)[0],
                          "Segments %r in intake %r share identical startTimestamp %r." % (sorted(ids), intake_id, ts), now)
    for seg in segments:
        if seg.get("lineStart") is not None and seg.get("lineEnd") is not None and seg["lineStart"] > seg["lineEnd"]:
            _finding(findings, "IMPOSSIBLE_LINE_RANGE", "ERROR", "TRANSCRIPT_SEGMENT", seg["segmentId"],
                      "lineStart=%r is greater than lineEnd=%r." % (seg["lineStart"], seg["lineEnd"]), now)


def check_explanation_provenance(claims, links, findings, now):
    links_by_claim = {}
    for l in links:
        links_by_claim.setdefault(l["claimId"], []).append(l)
    for c in claims:
        if c["evidenceCount"] > 0 and not links_by_claim.get(c["claimId"]):
            _finding(findings, "EXPLANATION_WITHOUT_PROVENANCE", "ERROR", "CLAIM", c["claimId"],
                      "evidenceCount>0 but no linked evidence exists -- any explanation generated for this "
                      "claim would have counts with nothing to cite.", now)


# ---------------------------------------------------------------------------
# PROGRAM-007 Phase 7A (Deliverable 8/19) -- Knowledge Library integrity
# ---------------------------------------------------------------------------

def check_blueprint_claim_references(blueprints, claims, findings, now):
    claim_ids = {c["claimId"] for c in claims}
    for bp in blueprints:
        for cid in (bp.get("sourceLineage") or {}).get("claimIds", []) or []:
            if cid not in claim_ids:
                _finding(findings, "BLUEPRINT_REFERENCES_NONEXISTENT_CLAIM", "ERROR", "STRATEGY_BLUEPRINT",
                          bp["blueprintId"], "sourceLineage.claimIds references nonexistent claimId %r." % (cid,), now)


def check_gap_blueprint_references(gaps, blueprints, findings, now):
    blueprint_ids = {bp["blueprintId"] for bp in blueprints}
    for gap in gaps:
        bid = gap.get("blueprintId")
        if bid and bid not in blueprint_ids:
            _finding(findings, "GAP_REFERENCES_NONEXISTENT_BLUEPRINT", "ERROR", "KNOWLEDGE_GAP", gap["gapId"],
                      "blueprintId references nonexistent blueprintId %r." % (bid,), now)


def check_hypothesis_claim_references(hypotheses, claims, findings, now):
    claim_ids = {c["claimId"] for c in claims}
    for h in hypotheses:
        for cid in h.get("sourceClaimIds", []) or []:
            if cid not in claim_ids:
                _finding(findings, "HYPOTHESIS_REFERENCES_NONEXISTENT_CLAIM", "ERROR", "HYPOTHESIS",
                          h["hypothesisId"], "sourceClaimIds references nonexistent claimId %r." % (cid,), now)


def check_no_executable_blueprint_linkage(ti_root, findings, now):
    """Structural proof that a StrategyRule -- the one thing that IS
    executable -- never names a Blueprint as its origin. A Blueprint is
    research output only; nothing may cite one as authorization for a rule."""
    for path in _iter_strategy_rule_paths(ti_root):
        with open(path, "r", encoding="utf-8") as f:
            rule = json.load(f)
        for value in rule.values():
            values = value if isinstance(value, list) else [value]
            for v in values:
                if isinstance(v, str) and v.startswith("BLUEPRINT|"):
                    _finding(findings, "EXECUTABLE_LINKAGE_FROM_RESEARCH_BLUEPRINT", "FATAL", "STRATEGY_RULE",
                              rule.get("ruleId", path),
                              "StrategyRule references %r -- a research-only StrategyBlueprint must never "
                              "be cited as authorization for an executable rule." % (v,), now)


def check_duplicate_canonical_trader_identity(profiles, findings, now):
    """Multiple TraderProfile snapshots for the same traderId are expected
    (each build is a new immutable snapshot) -- but they must always agree
    on canonicalName. Disagreement means two conflicting canonical identities
    exist for one traderId, which Deliverable 8 requires this validator to
    catch."""
    names_by_trader = {}
    for p in profiles:
        names_by_trader.setdefault(p["traderId"], set()).add(p["canonicalName"])
    for trader_id, names in names_by_trader.items():
        if len(names) > 1:
            _finding(findings, "DUPLICATE_CANONICAL_TRADER_IDENTITY", "ERROR", "TRADER_PROFILE", trader_id,
                      "TraderProfile snapshots for traderId %r disagree on canonicalName: %s." % (
                          trader_id, sorted(names)), now)


def run_integrity_checks(evidence_root, repo_root=None, ti_root=None, is_production=True):
    now = datetime.now(timezone.utc)
    sources = _load_dir(os.path.join(evidence_root, "sources"), "sourceId")
    items = _load_dir(os.path.join(evidence_root, "items"), "evidenceId")
    claims = _load_dir(os.path.join(evidence_root, "claims"), "claimId")
    links = _load_dir(os.path.join(evidence_root, "links"), "linkId")
    contradictions = _load_dir(os.path.join(evidence_root, "contradictions"), "contradictionId")
    lifecycle_events = _load_dir(os.path.join(evidence_root, "lifecycle"), "eventId")
    # PROGRAM-006 Phase 1B (ADR-009):
    intakes = _load_dir(os.path.join(evidence_root, "intake"), "intakeId")
    segments = _load_dir(os.path.join(evidence_root, "segments"), "segmentId")
    annotations = _load_dir(os.path.join(evidence_root, "annotations"), "annotationId")
    questions = _load_dir(os.path.join(evidence_root, "questions"), "questionId")
    proposals = _load_dir(os.path.join(evidence_root, "proposals"), "proposalId")
    queue_entries = _load_dir(os.path.join(evidence_root, "review-queue"), "queueEntryId")
    # PROGRAM-007 Phase 7A (Knowledge Library vertical slice):
    profiles = _load_dir(os.path.join(evidence_root, "profiles"), "profileId")
    blueprints = _load_dir(os.path.join(evidence_root, "blueprints"), "blueprintId")
    gaps = _load_dir(os.path.join(evidence_root, "gaps"), "gapId")
    hypotheses = _load_dir(os.path.join(evidence_root, "hypotheses"), "hypothesisId")
    observations = _load_dir(os.path.join(evidence_root, "observations"), "observationId")

    findings = []
    check_orphans(sources, items, claims, links, findings, now)
    check_observation_population_rebinding(observations, sources, findings, now)
    check_duplicate_ids(sources, items, claims, links, contradictions, findings, now, extra=[
        ("TRANSCRIPT_SEGMENT", segments, "segmentId"), ("INTAKE_MANIFEST", intakes, "intakeId"),
        ("MANUAL_ANNOTATION", annotations, "annotationId"), ("EVIDENCE_QUESTION", questions, "questionId"),
        ("RULE_CANDIDATE_PROPOSAL", proposals, "proposalId"), ("REVIEW_QUEUE_ENTRY", queue_entries, "queueEntryId"),
        ("TRADER_PROFILE", profiles, "profileId"), ("STRATEGY_BLUEPRINT", blueprints, "blueprintId"),
        ("KNOWLEDGE_GAP", gaps, "gapId"), ("HYPOTHESIS", hypotheses, "hypothesisId"),
    ])
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

    # PROGRAM-006 Phase 1B (ADR-009, Deliverable 19):
    check_orphaned_segments(intakes, segments, findings, now)
    check_missing_transcript_locator(items, findings, now)
    check_annotation_references(annotations, intakes, segments, findings, now)
    check_directness_and_certainty_present(items, findings, now)
    check_claim_candidate_without_evidence(claims, links, findings, now)
    check_rule_candidate_proposals(proposals, claims, findings, now)
    check_questions_reference_existing_claims(questions, claims, findings, now)
    check_review_queue_references(queue_entries, {
        "EVIDENCE_SOURCE": {s["sourceId"] for s in sources}, "EVIDENCE_ITEM": {i["evidenceId"] for i in items},
        "CLAIM": {c["claimId"] for c in claims}, "CONTRADICTION_RECORD": {c["contradictionId"] for c in contradictions},
        "EVIDENCE_QUESTION": {q["questionId"] for q in questions}, "RULE_CANDIDATE_PROPOSAL": {p["proposalId"] for p in proposals},
        "INTAKE_MANIFEST": {m["intakeId"] for m in intakes}, "TRANSCRIPT_SEGMENT": {s["segmentId"] for s in segments},
    }, findings, now)
    check_approved_intake_findings(intakes, findings, now)
    check_approved_source_licensing(intakes, findings, now)
    check_segment_hashes(segments, findings, now)
    check_intake_content_hash(intakes, findings, now)
    check_segment_sequence_and_line_ranges(segments, findings, now)
    check_explanation_provenance(claims, links, findings, now)

    # PROGRAM-007 Phase 7A (Deliverable 8/19):
    check_blueprint_claim_references(blueprints, claims, findings, now)
    check_gap_blueprint_references(gaps, blueprints, findings, now)
    check_hypothesis_claim_references(hypotheses, claims, findings, now)
    check_duplicate_canonical_trader_identity(profiles, findings, now)
    for label, records, id_field in (
        ("TRADER_PROFILE", profiles, "profileId"), ("STRATEGY_BLUEPRINT", blueprints, "blueprintId"),
        ("KNOWLEDGE_GAP", gaps, "gapId"), ("HYPOTHESIS", hypotheses, "hypothesisId"),
    ):
        for r in records:
            v = r.get("schemaVersion")
            if not isinstance(v, int) or v > evc.SCHEMA_VERSION:
                _finding(findings, "UNSUPPORTED_SCHEMA_VERSION", "ERROR", label, r[id_field],
                          "Record has schemaVersion=%r; this validator supports up to %d." % (
                              v, evc.SCHEMA_VERSION), now)

    if repo_root and ti_root:
        check_graph_relationships(repo_root, ti_root, links, claims, findings, now)
        check_production_rule_linkage(ti_root, findings, now)
        check_no_executable_blueprint_linkage(ti_root, findings, now)

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

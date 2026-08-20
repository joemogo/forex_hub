"""Shared deterministic-graph utilities for PROGRAM-003 Phase 1 (Knowledge Graph Core Foundation).

Pure Python standard library. No network access. No third-party packages.

This module only READS authoritative Trader Intelligence records (under
docs/trader-intelligence/traders/** and docs/trader-intelligence/graph/decisions/**).
It never writes to them and never becomes a second source of truth for anything
they say -- everything it produces (GraphNode/GraphEdge records) is a generated,
derived artifact.
"""
import glob as globmod
import hashlib
import json
import os

BUILDER_VERSION = "1.0.0"

NODE_TYPES = [
    "TRADER", "STRATEGY_FAMILY", "RESEARCH_SOURCE", "SOURCE_SEGMENT",
    "STRATEGY_ASSERTION", "CHART_EXAMPLE", "RULE_EVIDENCE", "STRATEGY_RULE",
    "RULE_VERSION", "RULE_CONTRADICTION", "UNRESOLVED_QUESTION",
    "RESEARCH_INTAKE_REPORT", "OWNER_DECISION",
    # PROGRAM-006 (ADR-008) additive node types:
    "EVIDENCE_SOURCE", "EVIDENCE_ITEM", "CLAIM", "CONTRADICTION_RECORD",
    # PROGRAM-006 Phase 1B (ADR-009) additive node types. EVIDENCE_QUESTION is
    # deliberately not named UNRESOLVED_QUESTION -- see ADR-009 sec. 12 for why
    # that would collide with the pre-existing Wave-1 entity above.
    # ResearchReport-equivalent output (TJR research reports) is deliberately
    # NOT a node type here, mirroring the existing convention that generated
    # reports (GraphIntegrityReport, AcquisitionReports) are documents, not
    # graph entities.
    "TRANSCRIPT_SEGMENT", "INTAKE_MANIFEST", "EVIDENCE_QUESTION", "REVIEW_QUEUE_ENTRY",
    "RULE_CANDIDATE_PROPOSAL",
    # PROGRAM-007 Phase 7A (Knowledge Library vertical slice) additive node
    # types. No Concept node type is added -- PROFILE_REFERENCES_CONCEPT
    # (suggested in the milestone) would require a Concept Registry, already
    # explicitly deferred in ADR-008; concept values stay plain labeled
    # strings on TraderProfile until that registry exists. No BlueprintStage
    # node type either -- workflow stages stay embedded array fields on
    # StrategyBlueprint (queryable via the blueprint itself); giving them
    # independent node identity isn't needed for this vertical slice and
    # would proliferate node types without a concrete cross-blueprint query
    # that requires it.
    "TRADER_PROFILE", "STRATEGY_BLUEPRINT", "KNOWLEDGE_GAP", "HYPOTHESIS",
    # B-32: MOGO's own preserved TradeObservations. Before this they were a
    # PARALLEL evidence store -- validated by validate_evidence.py, invisible to
    # the graph -- so the 17 EvidenceSources they cite surfaced as ORPHAN_NODE
    # warnings because the entities citing them were not here. That buried the
    # real signal: those 17 sat among 30 GENUINELY uncited sources, and a new
    # provenance gap arriving as the 48th warning could not be told from them.
    #
    # (The arithmetic matters and was got wrong once: 48 warnings before = 47
    # EVIDENCE_SOURCE + 1 OWNER_DECISION. Of the 47, only 17 were false and were
    # removed by representing this relationship; 30 remain and are real. "47 false
    # orphans removed" is impossible on its face -- 47 + 30 exceeds the 59 sources
    # that exist.)
    #
    # No Outcome node type is added. `outcome` is a field on the observation
    # (Win/Loss), not an entity with independent identity, and giving it one
    # would proliferate 259 nodes carrying a single enum -- the same reasoning
    # that keeps blueprint workflow stages as embedded fields above.
    "TRADE_OBSERVATION",
]

EDGE_TYPES = [
    "BELONGS_TO_TRADER", "BELONGS_TO_STRATEGY_FAMILY", "DERIVED_FROM", "SEGMENT_OF",
    "ASSERTED_IN", "SUPPORTS", "EVIDENCES", "CONTRADICTS", "IMPLEMENTS",
    "SUPERSEDES", "REFERENCES", "BLOCKS", "RESOLVES", "PARTIALLY_RESOLVES",
    "REQUIRES_OWNER_DECISION", "VERSION_OF", "VALIDATES",
    # PROGRAM-006 (ADR-008) additive edge types -- SUPPORTS/CONTRADICTS/SUPERSEDES/
    # DERIVED_FROM/BELONGS_TO_TRADER/BELONGS_TO_STRATEGY_FAMILY above are reused
    # as-is for the evidence layer rather than duplicated (ADR-008 sec. "use
    # existing graph conventions"); only genuinely new relationships are added:
    "WEAKENS", "CONTEXTUALIZES", "EXEMPLIFIES", "QUALIFIES", "UNRESOLVED", "CANDIDATE_FOR_RULE",
    # PROGRAM-006 Phase 1B (ADR-009) additive edge types. SEGMENT_OF above is
    # reused for TRANSCRIPT_SEGMENT -> INTAKE_MANIFEST. GENERATED_CLAIM,
    # EXPLAINED_BY, and INCLUDED_IN_REPORT (suggested in the milestone) were
    # deliberately not added -- explanations and reports are computed output,
    # not persisted graph-worthy entities, and "generated this claim" is
    # already covered by the existing evidence-to-claim relationship edges.
    "EVIDENCE_FROM_SEGMENT", "RAISES_QUESTION", "REQUIRES_REVIEW", "PROPOSES_RULE",
    "BLOCKED_BY", "RESOLVED_BY_EVIDENCE",
    # PROGRAM-007 Phase 7A (Knowledge Library vertical slice) additive edge
    # types. TRADER_HAS_PROFILE / TRADER_HAS_DRAFT_BLUEPRINT (suggested in the
    # milestone) are deliberately NOT added -- BELONGS_TO_TRADER already
    # connects any node type carrying a truthy traderId to its TRADER node
    # generically, and TRADER_PROFILE/STRATEGY_BLUEPRINT/KNOWLEDGE_GAP all
    # have traderId, so adding a second, narrower edge type would just
    # duplicate an existing relationship. PROFILE_DERIVED_FROM_SOURCE is
    # covered by the existing DERIVED_FROM edge (already generic across
    # entity types). BLUEPRINT_CONTAINS_STAGE is not added -- workflow stages
    # are embedded fields on STRATEGY_BLUEPRINT, not separate nodes.
    "BLUEPRINT_DERIVED_FROM_CLAIM", "BLUEPRINT_HAS_GAP", "GAP_GENERATES_RESEARCH_QUESTION",
    "CLAIM_SUPPORTS_HYPOTHESIS", "CLAIM_CONTRADICTS_HYPOTHESIS",
]

PROMOTION_STATES = [
    "DISCOVERED", "ASSERTION_SUPPORTED", "RESEARCH_REVIEWED", "MODELED",
    "IMPLEMENTATION_APPROVED", "CODED", "IMPLEMENTATION_VERIFIED",
    "REPLAY_ELIGIBLE", "REPLAY_VALIDATED", "SHADOW_ELIGIBLE", "SHADOW_VALIDATED",
    "PAPER_ELIGIBLE", "PAPER_APPROVED", "PAPER_VALIDATED",
    "PRODUCTION_REVIEW", "PRODUCTION_APPROVED", "LIVE_REVIEW", "LIVE_APPROVED",
]

_EDGE_ID_MAX_LEN = 200
_LABEL_MAX_LEN = 120


# ---------------------------------------------------------------------------
# Canonical serialization / hashing / deterministic IDs
# ---------------------------------------------------------------------------

def canonical_json_bytes(obj):
    """Canonical serialization used ONLY for hashing: object keys sorted
    recursively, arrays never reordered (order may carry meaning), compact
    separators, UTF-8, no NaN/Infinity. Not the same as the pretty-printed
    form written to committed artifacts -- see pretty_json()."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                       allow_nan=False).encode("utf-8")


def sha256_hex(data_bytes):
    return hashlib.sha256(data_bytes).hexdigest()


def content_hash_of(obj):
    """SHA-256 over the canonical serialization of one source entity."""
    return sha256_hex(canonical_json_bytes(obj))


def file_hash(path):
    with open(path, "rb") as f:
        return sha256_hex(f.read())


def pretty_json(obj):
    """Deterministic, git-diff-friendly form for committed artifacts. Same
    key-sort/array-order rules as canonical_json_bytes, but indented for
    human review. Always ends with exactly one trailing newline."""
    return json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def atomic_write_text(path, text):
    """Write-to-temp-then-rename. Never partially overwrites an existing file.
    If anything raises before the rename, the original file (if any) is left
    completely untouched."""
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, path)


def make_node_id(node_type, entity_id):
    if node_type not in NODE_TYPES:
        raise ValueError("Unknown nodeType: %r" % (node_type,))
    return "NODE|%s|%s" % (node_type, entity_id)


def make_edge_id(edge_type, from_entity_id, to_entity_id):
    """Format: EDGE|{EDGE_TYPE}|{fromEntityId}|{toEntityId}. If the raw id
    would exceed 200 characters, each entity id is truncated to its first 40
    characters and a deterministic 12-hex-char SHA-256 suffix (over the full,
    untruncated edgeType|fromEntityId|toEntityId string) is appended, keeping
    the id readable while remaining collision-resistant and fully
    reproducible from the same two inputs."""
    if edge_type not in EDGE_TYPES:
        raise ValueError("Unknown edgeType: %r" % (edge_type,))
    raw = "EDGE|%s|%s|%s" % (edge_type, from_entity_id, to_entity_id)
    if len(raw) <= _EDGE_ID_MAX_LEN:
        return raw
    digest = sha256_hex(("%s|%s|%s" % (edge_type, from_entity_id, to_entity_id)).encode("utf-8"))[:12]
    return "EDGE|%s|%s|%s~%s" % (edge_type, from_entity_id[:40], to_entity_id[:40], digest)


def make_build_id(date_str, sequence):
    return "BUILD|%s|%03d" % (date_str, sequence)


def make_integrity_report_id(build_id):
    return "INTEGRITY|%s" % (build_id,)


def truncate_label(text):
    if text is None:
        return ""
    text = str(text)
    if len(text) <= _LABEL_MAX_LEN:
        return text
    return text[: _LABEL_MAX_LEN - 1].rstrip() + "…"


# ---------------------------------------------------------------------------
# Entity discovery
# ---------------------------------------------------------------------------
# Each entry: node_type -> {id_field, label_field(s), status_field, glob}
# label/status use a fallback chain: first present+non-null field wins.

NODE_TYPE_FIELD_MAP = {
    "TRADER": {"id_field": "traderId", "label_fields": ["displayName"], "status_fields": ["repositoryModelStatus"]},
    "STRATEGY_FAMILY": {"id_field": "strategyFamilyId", "label_fields": ["name"], "status_fields": ["status"]},
    "RESEARCH_SOURCE": {"id_field": "sourceId", "label_fields": ["title"], "status_fields": ["processingStatus"]},
    "SOURCE_SEGMENT": {"id_field": "segmentId", "label_fields": ["segmentSummary", "rawExcerpt"], "status_fields": ["processingStatus"]},
    "STRATEGY_ASSERTION": {"id_field": "assertionId", "label_fields": ["normalizedMeaning", "exactQuoteOrFaithfulParaphrase"], "status_fields": ["reviewerStatus"]},
    "CHART_EXAMPLE": {"id_field": "chartExampleId", "label_fields": ["describedOutcome", "imageReference"], "status_fields": []},
    "RULE_EVIDENCE": {"id_field": "evidenceId", "label_fields": ["supportStrength"], "status_fields": ["supportStrength"]},
    "STRATEGY_RULE": {"id_field": "ruleId", "label_fields": ["name"], "status_fields": ["modelingStatus"]},
    "RULE_VERSION": {"id_field": "ruleVersionId", "label_fields": ["changeSummary"], "status_fields": []},
    "RULE_CONTRADICTION": {"id_field": "contradictionId", "label_fields": ["contradictionType"], "status_fields": ["status"]},
    "UNRESOLVED_QUESTION": {"id_field": "questionId", "label_fields": ["question"], "status_fields": ["status"]},
    "RESEARCH_INTAKE_REPORT": {"id_field": "reportId", "label_fields": ["reportId"], "status_fields": []},
    "OWNER_DECISION": {"id_field": "decisionId", "label_fields": ["question"], "status_fields": ["status"]},
    # PROGRAM-006 (ADR-008):
    "EVIDENCE_SOURCE": {"id_field": "sourceId", "label_fields": ["title"], "status_fields": ["lifecycleStatus"]},
    "EVIDENCE_ITEM": {"id_field": "evidenceId", "label_fields": ["normalizedObservation", "exactExcerpt"], "status_fields": ["evidenceStatus"]},
    "CLAIM": {"id_field": "claimId", "label_fields": ["normalizedClaim"], "status_fields": ["claimStatus"]},
    "CONTRADICTION_RECORD": {"id_field": "contradictionId", "label_fields": ["contradictionType"], "status_fields": ["status"]},
    # PROGRAM-006 Phase 1B (ADR-009):
    "TRANSCRIPT_SEGMENT": {"id_field": "segmentId", "label_fields": ["sectionTitle", "rawText"], "status_fields": ["segmentType"]},
    "INTAKE_MANIFEST": {"id_field": "intakeId", "label_fields": ["title"], "status_fields": ["intakeStatus"]},
    "EVIDENCE_QUESTION": {"id_field": "questionId", "label_fields": ["questionText"], "status_fields": ["researchStatus"]},
    "REVIEW_QUEUE_ENTRY": {"id_field": "queueEntryId", "label_fields": ["reason"], "status_fields": ["reviewStatus"]},
    "RULE_CANDIDATE_PROPOSAL": {"id_field": "proposalId", "label_fields": ["proposalRationale"], "status_fields": ["status"]},
    # PROGRAM-007 Phase 7A (Knowledge Library vertical slice):
    "TRADER_PROFILE": {"id_field": "profileId", "label_fields": ["canonicalName"], "status_fields": ["reviewStatus"]},
    "STRATEGY_BLUEPRINT": {"id_field": "blueprintId", "label_fields": ["strategyName"], "status_fields": ["status"]},
    "KNOWLEDGE_GAP": {"id_field": "gapId", "label_fields": ["question"], "status_fields": ["answerStatus"]},
    "HYPOTHESIS": {"id_field": "hypothesisId", "label_fields": ["statement"], "status_fields": ["status"]},
    # B-32. status_fields is deliberately EMPTY: `outcome` (Win/Loss) is a
    # result, not a lifecycle status, and surfacing it as node["status"] would
    # let a graph reader treat "Loss" as a workflow state.
    "TRADE_OBSERVATION": {"id_field": "observationId", "label_fields": ["instrument"], "status_fields": []},
}


def _sorted_glob(root, *parts):
    return sorted(globmod.glob(os.path.join(root, *parts)))


def _relpath(path, repo_root):
    return os.path.relpath(path, repo_root).replace(os.sep, "/")


def _load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# B-32. The authoritative list of evidence record collections that become graph
# entities. Lifted to module level because it had been duplicated by hand into
# three test scratch-tree cleaners, and adding TRADE_OBSERVATION to discovery
# without adding it to all three seeded every fixture with 259 production
# observations whose sources had just been deleted. Tests now DERIVE the entity
# part of that list from here, so a new collection cannot be forgotten again.
EVIDENCE_ENTITY_SPEC = [
        ("EVIDENCE_SOURCE", ("sources", "*.json")),
        ("EVIDENCE_ITEM", ("items", "*.json")),
        ("CLAIM", ("claims", "*.json")),
        ("CONTRADICTION_RECORD", ("contradictions", "*.json")),
        # PROGRAM-006 Phase 1B (ADR-009):
        ("TRANSCRIPT_SEGMENT", ("segments", "*.json")),
        ("INTAKE_MANIFEST", ("intake", "*.json")),
        ("EVIDENCE_QUESTION", ("questions", "*.json")),
        ("REVIEW_QUEUE_ENTRY", ("review-queue", "*.json")),
        ("RULE_CANDIDATE_PROPOSAL", ("proposals", "*.json")),
        # PROGRAM-007 Phase 7A (Knowledge Library vertical slice):
        ("TRADER_PROFILE", ("profiles", "*.json")),
        ("STRATEGY_BLUEPRINT", ("blueprints", "*.json")),
        ("KNOWLEDGE_GAP", ("gaps", "*.json")),
        ("HYPOTHESIS", ("hypotheses", "*.json")),
        # B-32: the same authoritative records validate_evidence.py checks. The
        # graph DERIVES from them and never becomes a second source of truth --
        # nothing here writes an observation, and observationIds/hashes are read
        # exactly as preserved.
        ("TRADE_OBSERVATION", ("observations", "*.json")),
    ]

#: Just the directory names, for callers that only need those.
EVIDENCE_ENTITY_COLLECTIONS = tuple(parts[0] for _t, parts in EVIDENCE_ENTITY_SPEC)


def discover_entities(repo_root, ti_root, graph_root):
    """Yields (node_type, entity_dict, source_file_relpath) for every
    authoritative entity found under ti_root (docs/trader-intelligence) and
    graph_root/decisions (docs/trader-intelligence/graph/decisions).

    UNRESOLVED_QUESTION is a special case: the real cross-reference file
    holds an array of question records under one JSON key rather than one
    file per question. Each array item is still treated as one independent
    entity with its own contentHash, sharing the same sourceFile.
    """
    simple = [
        ("TRADER", ("traders", "*", "profile.json")),
        ("STRATEGY_FAMILY", ("traders", "*", "strategy-families", "*.json")),
        ("RESEARCH_SOURCE", ("traders", "*", "sources", "*.json")),
        ("SOURCE_SEGMENT", ("traders", "*", "segments", "*.json")),
        ("STRATEGY_ASSERTION", ("traders", "*", "assertions", "*.json")),
        ("CHART_EXAMPLE", ("traders", "*", "chart-examples", "*.json")),
        ("RULE_EVIDENCE", ("traders", "*", "rule-evidence", "*.json")),
        ("STRATEGY_RULE", ("traders", "*", "rules", "*.json")),
        ("RULE_VERSION", ("traders", "*", "rule-versions", "*.json")),
        ("RULE_CONTRADICTION", ("traders", "*", "contradictions", "*.json")),
        ("RESEARCH_INTAKE_REPORT", ("traders", "*", "intake-reports", "*.json")),
    ]
    for node_type, parts in simple:
        for path in _sorted_glob(ti_root, *parts):
            yield node_type, _load_json(path), _relpath(path, repo_root)

    # UNRESOLVED_QUESTION: array-in-one-file special case.
    for path in _sorted_glob(ti_root, "traders", "*", "open-questions", "*.json"):
        doc = _load_json(path)
        rel = _relpath(path, repo_root)
        for item in doc.get("unresolvedQuestions", []):
            yield "UNRESOLVED_QUESTION", item, rel

    # OWNER_DECISION: lives under graph/decisions/, not traders/.
    for path in _sorted_glob(graph_root, "decisions", "*.json"):
        yield "OWNER_DECISION", _load_json(path), _relpath(path, repo_root)

    # PROGRAM-006 (ADR-008): evidence entities live under ti_root/evidence/,
    # a sibling of traders/ and graph/, not nested under either.
    evidence_root = os.path.join(ti_root, "evidence")
    evidence_simple = EVIDENCE_ENTITY_SPEC
    for node_type, parts in evidence_simple:
        for path in _sorted_glob(evidence_root, *parts):
            yield node_type, _load_json(path), _relpath(path, repo_root)


def discover_evidence_links(ti_root, repo_root):
    """EvidenceClaimLink records (docs/trader-intelligence/evidence/links/*.json)
    are not Knowledge Graph nodes -- they ARE the edges between EVIDENCE_ITEM and
    CLAIM nodes, with relationshipType mapping directly onto an edge type.
    Yields (link_dict, source_file_relpath)."""
    evidence_root = os.path.join(ti_root, "evidence")
    for path in _sorted_glob(evidence_root, "links", "*.json"):
        yield _load_json(path), _relpath(path, repo_root)


# ---------------------------------------------------------------------------
# Node construction
# ---------------------------------------------------------------------------

def build_node(node_type, entity, source_file):
    field_map = NODE_TYPE_FIELD_MAP[node_type]
    entity_id = entity[field_map["id_field"]]
    label = ""
    for f in field_map["label_fields"]:
        v = entity.get(f)
        if v:
            label = truncate_label(v)
            break
    status = "active"
    for f in field_map["status_fields"]:
        v = entity.get(f)
        if v:
            status = v
            break
    node = {
        "generated": True,
        "nodeId": make_node_id(node_type, entity_id),
        "nodeType": node_type,
        "entityId": entity_id,
        "traderId": entity.get("traderId"),
        "strategyFamilyId": entity.get("strategyFamilyId"),
        "label": label,
        "status": status,
        "sourceFile": source_file,
        "contentHash": content_hash_of(entity),
        "createdAt": entity.get("createdAt") or "",
        "updatedAt": entity.get("updatedAt"),
        "metadata": {},
    }
    if node_type == "UNRESOLVED_QUESTION" and entity.get("externalRef"):
        node["metadata"]["externalRef"] = entity["externalRef"]
    return node


# ---------------------------------------------------------------------------
# Edge construction
# ---------------------------------------------------------------------------

def _edge(edge_type, from_node_id, to_node_id, from_entity_id, to_entity_id, source_file,
          created_at, evidence_ids=None, confidence_dimensions=None, metadata=None):
    return {
        "generated": True,
        "edgeId": make_edge_id(edge_type, from_entity_id, to_entity_id),
        "edgeType": edge_type,
        "fromNodeId": from_node_id,
        "toNodeId": to_node_id,
        "traderId": None,
        "strategyFamilyId": None,
        "evidenceIds": evidence_ids or [],
        "confidenceDimensions": confidence_dimensions,
        "status": "active",
        "sourceFile": source_file,
        "createdAt": created_at,
        "supersedesEdgeId": None,
        "metadata": metadata or {},
    }


def build_nodes_and_edges(repo_root, ti_root, graph_root):
    """Returns (nodes, edges, missing_reference_findings).

    missing_reference_findings is a list of dicts describing every real
    field that pointed at an entity id with no corresponding node -- these
    become MISSING_REFERENCE findings in the integrity report. No edge is
    ever created to a non-existent node, and no placeholder node is ever
    synthesized to hide the gap.
    """
    nodes = []
    raw_by_entity_id = {}   # entityId -> (node_type, raw entity dict, source_file)
    node_id_by_entity_id = {}  # entityId -> nodeId
    seen_node_ids = set()
    findings = []

    entities = list(discover_entities(repo_root, ti_root, graph_root))

    # PROGRAM-007 Phase 7A: precomputed once (not per-HYPOTHESIS) so a
    # Hypothesis's contradictingEvidenceIds can be traced back to the claim(s)
    # that evidence actually contradicts, reusing the existing EvidenceClaimLink
    # data rather than adding a new persisted relationship for the same fact.
    _evidence_to_contradicted_claims = {}
    for _link, _link_source_file in discover_evidence_links(ti_root, repo_root):
        if _link.get("relationshipType") == "contradicts" and _link.get("evidenceId") and _link.get("claimId"):
            _evidence_to_contradicted_claims.setdefault(_link["evidenceId"], []).append(_link["claimId"])

    for node_type, entity, source_file in entities:
        node = build_node(node_type, entity, source_file)
        if node["nodeId"] in seen_node_ids:
            findings.append({
                "category": "DUPLICATE_NODE_ID", "severity": "FATAL",
                "message": "Duplicate nodeId %s produced by %s" % (node["nodeId"], source_file),
                "affectedIds": [node["nodeId"]],
            })
            continue
        seen_node_ids.add(node["nodeId"])
        nodes.append(node)
        raw_by_entity_id[node["entityId"]] = (node_type, entity, source_file)
        node_id_by_entity_id[node["entityId"]] = node["nodeId"]

    def resolve(entity_id, edge_type, from_entity_id, category="MISSING_REFERENCE"):
        target = node_id_by_entity_id.get(entity_id)
        if target is None:
            findings.append({
                "category": category, "severity": "ERROR",
                "message": "%s references %s (via %s) but no matching node was generated for it." % (
                    from_entity_id, entity_id, edge_type),
                "affectedIds": [from_entity_id, entity_id],
            })
        return target

    edges = []
    seen_edge_ids = set()

    def add_edge(edge_type, from_node_id, to_node_id, from_entity_id, to_entity_id, source_file,
                 created_at, evidence_ids=None, confidence_dimensions=None, metadata=None):
        e = _edge(edge_type, from_node_id, to_node_id, from_entity_id, to_entity_id, source_file,
                   created_at, evidence_ids, confidence_dimensions, metadata)
        if e["edgeId"] in seen_edge_ids:
            findings.append({
                "category": "DUPLICATE_EDGE_ID", "severity": "ERROR",
                "message": "Duplicate edgeId %s" % (e["edgeId"],),
                "affectedIds": [e["edgeId"]],
            })
            return
        seen_edge_ids.add(e["edgeId"])
        edges.append(e)

    for node_type, entity, source_file in entities:
        eid = entity[NODE_TYPE_FIELD_MAP[node_type]["id_field"]]
        from_node_id = node_id_by_entity_id[eid]
        created_at = entity.get("createdAt") or ""

        trader_id = entity.get("traderId")
        family_id = entity.get("strategyFamilyId")

        # TRADE_OBSERVATION is excluded as a BUILDER RULE, not left to a data
        # assumption. Every preserved observation happens to carry no traderId, so
        # the generic rule below produced no trader edge and the fabrication
        # guarantee looked airtight -- but it held only because of what the records
        # happen to contain. Adding `traderId: "ALEX_G"` to ONE record built a real
        # BELONGS_TO_TRADER edge and put MOGO's own paper trades three hops from a
        # human trader's evidence, which is exactly the contamination this whole
        # design exists to prevent.
        #
        # An observation is MOGO's execution record. It never belongs to a human
        # trader, whatever a record claims, so the builder refuses rather than
        # trusting the field to be absent.
        if node_type not in ("OWNER_DECISION", "TRADER", "TRADE_OBSERVATION") and trader_id:
            target = resolve(trader_id, "BELONGS_TO_TRADER", eid, category="INVALID_TRADER_REFERENCE")
            if target:
                add_edge("BELONGS_TO_TRADER", from_node_id, target, eid, trader_id, source_file, created_at)

        if node_type in ("STRATEGY_ASSERTION", "CHART_EXAMPLE", "STRATEGY_RULE", "UNRESOLVED_QUESTION",
                         "EVIDENCE_SOURCE", "EVIDENCE_ITEM", "CLAIM") and family_id:
            target = resolve(family_id, "BELONGS_TO_STRATEGY_FAMILY", eid, category="INVALID_STRATEGY_FAMILY_REFERENCE")
            if target:
                add_edge("BELONGS_TO_STRATEGY_FAMILY", from_node_id, target, eid, family_id, source_file, created_at)

        # B-32. The ONLY relationship a TradeObservation actually states.
        #
        # `sourceId` is present on all 259 preserved records and names the
        # EvidenceSource the observation was minted from, so this edge is read
        # from the record rather than inferred. It is also what makes those 47
        # sources genuinely referenced instead of merely un-warned.
        #
        # Deliberately NOT derived, and this is the substantive decision here:
        #
        #   strategyId -> STRATEGY_FAMILY. 257 observations carry
        #   strategyId=alex_g_sr_v1 (the other 2 carry `current_strategy`), and
        #   SF|ALEX_G|SUPPORT_RESISTANCE_V1 exists as a node.
        #   Joining them would assert that MOGO's IMPLEMENTATION and the human
        #   trader's stated method are the same subject. They are not:
        #   alex_g_sr_v1 is MOGO's code, ALEX_G is a person, and replaying the
        #   former measures the implementation rather than whether the trader's
        #   rule holds. That edge would let a query walk from MOGO's own paper
        #   trades to a human trader's evidence and count one as evidence for
        #   the other -- OBSERVED data silently answering a SOURCE_STATED
        #   question. The ids do not match anyway; making them match would be
        #   fabricating the relationship, not discovering it.
        #
        #   Trader/Claim/Hypothesis links. No observation record carries a
        #   traderId, claimId or hypothesisId. Nothing states those relations,
        #   so nothing derives them. They stay UNKNOWN rather than guessed.
        if node_type == "TRADE_OBSERVATION":
            src = entity.get("sourceId")
            if src:
                target = resolve(src, "DERIVED_FROM", eid)
                if target:
                    add_edge("DERIVED_FROM", from_node_id, target, eid, src, source_file, created_at)

        if node_type == "SOURCE_SEGMENT":
            src = entity.get("sourceId")
            if src:
                target = resolve(src, "SEGMENT_OF", eid)
                if target:
                    add_edge("SEGMENT_OF", from_node_id, target, eid, src, source_file, created_at)

        if node_type == "STRATEGY_ASSERTION":
            src = entity.get("sourceId")
            if src:
                target = resolve(src, "DERIVED_FROM", eid)
                if target:
                    add_edge("DERIVED_FROM", from_node_id, target, eid, src, source_file, created_at)
            seg = entity.get("sourceSegmentId")
            if seg:
                target = resolve(seg, "ASSERTED_IN", eid)
                if target:
                    add_edge("ASSERTED_IN", from_node_id, target, eid, seg, source_file, created_at)
            supersedes = entity.get("supersedesAssertionId")
            if supersedes:
                target = resolve(supersedes, "SUPERSEDES", eid)
                if target:
                    add_edge("SUPERSEDES", from_node_id, target, eid, supersedes, source_file, created_at)

        if node_type == "CHART_EXAMPLE":
            src = entity.get("sourceId")
            if src:
                target = resolve(src, "DERIVED_FROM", eid)
                if target:
                    add_edge("DERIVED_FROM", from_node_id, target, eid, src, source_file, created_at)

        if node_type == "RESEARCH_INTAKE_REPORT":
            for src in entity.get("sourceIds", []):
                target = resolve(src, "DERIVED_FROM", eid)
                if target:
                    add_edge("DERIVED_FROM", from_node_id, target, eid, src, source_file, created_at)

        if node_type == "RULE_EVIDENCE":
            rule_id = entity.get("ruleId")
            assertion_ids = entity.get("assertionIds", [])
            chart_ids = entity.get("chartExampleIds", [])
            if rule_id:
                target = resolve(rule_id, "EVIDENCES", eid)
                if target:
                    add_edge("EVIDENCES", from_node_id, target, eid, rule_id, source_file, created_at,
                              evidence_ids=list(assertion_ids) + list(chart_ids))
                for a_id in assertion_ids:
                    a_target = resolve(a_id, "SUPPORTS", a_id)
                    if a_target and rule_id in node_id_by_entity_id:
                        a_node_id = node_id_by_entity_id[a_id]
                        rule_node_id = node_id_by_entity_id[rule_id]
                        _, a_entity, a_source = raw_by_entity_id[a_id]
                        conf = {"interpretationConfidence": a_entity.get("interpretationConfidence")} \
                            if a_entity.get("interpretationConfidence") else None
                        add_edge("SUPPORTS", a_node_id, rule_node_id, a_id, rule_id, a_source, created_at,
                                  evidence_ids=[eid], confidence_dimensions=conf)

        if node_type == "STRATEGY_RULE":
            avid = entity.get("activeRuleVersionId")
            # VERSION_OF edges are generated from RULE_VERSION entities below,
            # not here, to keep one canonical direction of derivation.

        if node_type == "RULE_VERSION":
            rule_id = entity.get("ruleId")
            if rule_id:
                target = resolve(rule_id, "VERSION_OF", eid)
                if target:
                    is_active = raw_by_entity_id.get(rule_id, (None, {}, None))[1].get("activeRuleVersionId") == eid
                    add_edge("VERSION_OF", from_node_id, target, eid, rule_id, source_file, created_at,
                              metadata={"isActiveVersion": is_active})
            supersedes = entity.get("supersedesRuleVersionId")
            if supersedes:
                target = resolve(supersedes, "SUPERSEDES", eid)
                if target:
                    add_edge("SUPERSEDES", from_node_id, target, eid, supersedes, source_file, created_at)

        if node_type == "RULE_CONTRADICTION":
            supporting = entity.get("supportingAssertionIds", [])
            conflicting = entity.get("conflictingAssertionIds", [])
            for rule_id in entity.get("relatedRuleIds", []):
                target = resolve(rule_id, "CONTRADICTS", eid)
                if target:
                    add_edge("CONTRADICTS", from_node_id, target, eid, rule_id, source_file, created_at,
                              evidence_ids=list(supporting) + list(conflicting),
                              metadata={"supportingAssertionIds": supporting, "conflictingAssertionIds": conflicting})

        if node_type == "UNRESOLVED_QUESTION":
            for rule_id in entity.get("relatedRuleIds", []):
                target = resolve(rule_id, "BLOCKS", eid)
                if target:
                    add_edge("BLOCKS", from_node_id, target, eid, rule_id, source_file, created_at)
            if not entity.get("relatedRuleIds"):
                # Fall back to the most specific real link available: the
                # family if named, else the trader. Never invented -- only
                # ever derived from a field that is actually present.
                if family_id and family_id in node_id_by_entity_id:
                    add_edge("BLOCKS", from_node_id, node_id_by_entity_id[family_id], eid, family_id,
                              source_file, created_at)
                elif trader_id and trader_id in node_id_by_entity_id:
                    add_edge("BLOCKS", from_node_id, node_id_by_entity_id[trader_id], eid, trader_id,
                              source_file, created_at)
            status = entity.get("status")
            res_ids = entity.get("resolutionAssertionIds", [])
            if res_ids and status in ("resolved", "partially_resolved"):
                edge_type = "RESOLVES" if status == "resolved" else "PARTIALLY_RESOLVES"
                for a_id in res_ids:
                    target = resolve(a_id, edge_type, eid)
                    if target:
                        add_edge(edge_type, target, from_node_id, a_id, eid, source_file, created_at)

        if node_type == "OWNER_DECISION":
            for affected_id in entity.get("affectedEntityIds", []):
                target = node_id_by_entity_id.get(affected_id)
                if target:
                    add_edge("REFERENCES", from_node_id, target, eid, affected_id, source_file, created_at)
                # Unlike other reference fields, an OwnerDecision's
                # affectedEntityIds is allowed to name entities that don't
                # exist as graph nodes yet (e.g. a not-yet-modeled rule) --
                # that is not a data-quality error the way a broken
                # sourceId/ruleId reference would be, so no finding is
                # recorded for a miss here.
            supersedes = entity.get("supersedesDecisionId")
            if supersedes:
                target = resolve(supersedes, "SUPERSEDES", eid)
                if target:
                    add_edge("SUPERSEDES", from_node_id, target, eid, supersedes, source_file, created_at)

        # --- PROGRAM-006 (ADR-008) additive node-type edge derivation ---

        if node_type == "EVIDENCE_ITEM":
            src = entity.get("sourceId")
            if src:
                target = resolve(src, "DERIVED_FROM", eid)
                if target:
                    add_edge("DERIVED_FROM", from_node_id, target, eid, src, source_file, created_at)
            parent = entity.get("parentEvidenceId")
            if parent:
                target = resolve(parent, "DERIVED_FROM", eid)
                if target:
                    add_edge("DERIVED_FROM", from_node_id, target, eid, parent, source_file, created_at,
                              metadata={"relationship": "parentEvidence"})
            supersedes = entity.get("supersedesEvidenceId")
            if supersedes:
                target = resolve(supersedes, "SUPERSEDES", eid)
                if target:
                    add_edge("SUPERSEDES", from_node_id, target, eid, supersedes, source_file, created_at)
            # PROGRAM-006 Phase 1B (ADR-009): sourceLocator only sometimes
            # holds a TranscriptSegment id (Phase 1A manual-entry records use
            # it for arbitrary free-text locations) -- only attempt this edge,
            # and only then risk a MISSING_REFERENCE finding via resolve(),
            # when it is actually shaped like a segment id.
            locator = entity.get("sourceLocator")
            if locator and locator.startswith("TSEG|"):
                target = resolve(locator, "EVIDENCE_FROM_SEGMENT", eid)
                if target:
                    add_edge("EVIDENCE_FROM_SEGMENT", from_node_id, target, eid, locator, source_file, created_at,
                              evidence_ids=[eid])

        if node_type == "TRANSCRIPT_SEGMENT":
            intake_ref = entity.get("intakeId")
            if intake_ref:
                target = resolve(intake_ref, "SEGMENT_OF", eid)
                if target:
                    add_edge("SEGMENT_OF", from_node_id, target, eid, intake_ref, source_file, created_at)

        if node_type == "EVIDENCE_QUESTION":
            claim_ref = entity.get("claimId")
            if claim_ref:
                target = resolve(claim_ref, "RAISES_QUESTION", eid)
                if target:
                    add_edge("RAISES_QUESTION", target, from_node_id, claim_ref, eid, source_file, created_at)
            for answer_evidence_id in entity.get("answerEvidenceIds", []) or []:
                target = resolve(answer_evidence_id, "RESOLVED_BY_EVIDENCE", eid)
                if target:
                    add_edge("RESOLVED_BY_EVIDENCE", from_node_id, target, eid, answer_evidence_id, source_file, created_at)

        if node_type == "REVIEW_QUEUE_ENTRY":
            entity_ref = entity.get("entityId")
            if entity_ref:
                target = resolve(entity_ref, "REQUIRES_REVIEW", eid)
                if target:
                    add_edge("REQUIRES_REVIEW", target, from_node_id, entity_ref, eid, source_file, created_at)

        if node_type == "RULE_CANDIDATE_PROPOSAL":
            for claim_ref in entity.get("originatingClaimIds", []) or []:
                target = resolve(claim_ref, "PROPOSES_RULE", eid)
                if target:
                    add_edge("PROPOSES_RULE", target, from_node_id, claim_ref, eid, source_file, created_at)
            if entity.get("contradictionStatus") == "open_contradiction":
                for claim_ref in entity.get("originatingClaimIds", []) or []:
                    for cr_node in [n for n in nodes if n["nodeType"] == "CONTRADICTION_RECORD"]:
                        cr_entity = raw_by_entity_id.get(cr_node["entityId"], (None, {}, None))[1]
                        if cr_entity.get("claimAId") == claim_ref or cr_entity.get("claimBId") == claim_ref:
                            add_edge("BLOCKED_BY", from_node_id, cr_node["nodeId"], eid, cr_node["entityId"],
                                      source_file, created_at)
            for question_ref in entity.get("unresolvedQuestionIds", []) or []:
                target = node_id_by_entity_id.get(question_ref)
                if target:
                    add_edge("BLOCKED_BY", from_node_id, target, eid, question_ref, source_file, created_at)

        if node_type == "CONTRADICTION_RECORD":
            for claim_ref in (entity.get("claimAId"), entity.get("claimBId")):
                if claim_ref:
                    target = resolve(claim_ref, "CONTRADICTS", eid)
                    if target:
                        # The ContradictionRecord itself is the evidence for this
                        # disagreement (it carries contradictionType/rationale),
                        # so it satisfies the evidentiary-edge provenance check.
                        add_edge("CONTRADICTS", from_node_id, target, eid, claim_ref, source_file, created_at,
                                  evidence_ids=[eid])

        if node_type == "STRATEGY_RULE":
            for claim_ref in entity.get("originatingClaimIds", []):
                target = resolve(claim_ref, "CANDIDATE_FOR_RULE", eid)
                if target:
                    claim_node_id = node_id_by_entity_id[claim_ref]
                    add_edge("CANDIDATE_FOR_RULE", claim_node_id, from_node_id, claim_ref, eid, source_file, created_at)

        # --- PROGRAM-007 Phase 7A (Knowledge Library vertical slice) additive
        # node-type edge derivation ---

        if node_type == "STRATEGY_BLUEPRINT":
            claim_ids = (entity.get("sourceLineage") or {}).get("claimIds", []) or []
            for claim_ref in claim_ids:
                target = resolve(claim_ref, "BLUEPRINT_DERIVED_FROM_CLAIM", eid)
                if target:
                    # The blueprint's own sourceLineage IS the assembled
                    # evidence trail for this derivation, so citing the
                    # blueprint's claimIds as evidenceIds is not circular --
                    # it records exactly which claims produced this edge.
                    add_edge("BLUEPRINT_DERIVED_FROM_CLAIM", from_node_id, target, eid, claim_ref, source_file,
                              created_at, evidence_ids=[claim_ref])

        if node_type == "KNOWLEDGE_GAP":
            blueprint_ref = entity.get("blueprintId")
            if blueprint_ref:
                target = resolve(blueprint_ref, "BLUEPRINT_HAS_GAP", eid)
                if target:
                    add_edge("BLUEPRINT_HAS_GAP", target, from_node_id, blueprint_ref, eid, source_file, created_at)
            eq_ref = (entity.get("provenance") or {}).get("evidenceQuestionId")
            if eq_ref:
                target = resolve(eq_ref, "GAP_GENERATES_RESEARCH_QUESTION", eid)
                if target:
                    add_edge("GAP_GENERATES_RESEARCH_QUESTION", from_node_id, target, eid, eq_ref, source_file, created_at)

        if node_type == "HYPOTHESIS":
            for claim_ref in entity.get("sourceClaimIds", []) or []:
                target = resolve(claim_ref, "CLAIM_SUPPORTS_HYPOTHESIS", eid)
                if target:
                    add_edge("CLAIM_SUPPORTS_HYPOTHESIS", target, from_node_id, claim_ref, eid, source_file,
                              created_at, evidence_ids=entity.get("supportingEvidenceIds") or [])
            for evidence_ref in entity.get("contradictingEvidenceIds", []) or []:
                for claim_ref in _evidence_to_contradicted_claims.get(evidence_ref, []):
                    target = node_id_by_entity_id.get(claim_ref)
                    if target:
                        add_edge("CLAIM_CONTRADICTS_HYPOTHESIS", target, from_node_id, claim_ref, eid, source_file,
                                  created_at, evidence_ids=[evidence_ref])

    # PROGRAM-006 (ADR-008): EvidenceClaimLink records are edges, not nodes --
    # relationshipType maps directly onto an existing or additive edge type.
    _LINK_RELATIONSHIP_TO_EDGE_TYPE = {
        "supports": "SUPPORTS", "contradicts": "CONTRADICTS", "weakens": "WEAKENS",
        "contextualizes": "CONTEXTUALIZES", "exemplifies": "EXEMPLIFIES",
        "qualifies": "QUALIFIES", "supersedes": "SUPERSEDES", "unresolved": "UNRESOLVED",
    }
    for link, link_source_file in discover_evidence_links(ti_root, repo_root):
        evidence_ref = link.get("evidenceId")
        claim_ref = link.get("claimId")
        relationship = link.get("relationshipType")
        edge_type = _LINK_RELATIONSHIP_TO_EDGE_TYPE.get(relationship)
        if not (evidence_ref and claim_ref and edge_type):
            continue
        from_target = resolve(evidence_ref, edge_type, link.get("linkId", "?"))
        to_target = resolve(claim_ref, edge_type, link.get("linkId", "?"))
        if from_target and to_target:
            # The EvidenceItem the edge originates from IS the evidence being
            # cited, so evidenceIds is trivially and correctly [evidence_ref]
            # (satisfies the same evidentiary-edge provenance check that
            # STRATEGY_ASSERTION-derived SUPPORTS/CONTRADICTS edges must meet).
            add_edge(edge_type, from_target, to_target, evidence_ref, claim_ref, link_source_file,
                      link.get("linkedAt", ""), evidence_ids=[evidence_ref],
                      confidence_dimensions={"relevanceWeight": link.get("relevanceWeight")} if link.get("relevanceWeight") is not None else None,
                      metadata={"linkId": link.get("linkId"), "independenceGroup": link.get("independenceGroup")})

    nodes.sort(key=lambda n: n["nodeId"])
    edges.sort(key=lambda e: e["edgeId"])
    return nodes, edges, findings, raw_by_entity_id

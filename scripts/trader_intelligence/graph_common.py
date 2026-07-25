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
]

EDGE_TYPES = [
    "BELONGS_TO_TRADER", "BELONGS_TO_STRATEGY_FAMILY", "DERIVED_FROM", "SEGMENT_OF",
    "ASSERTED_IN", "SUPPORTS", "EVIDENCES", "CONTRADICTS", "IMPLEMENTS",
    "SUPERSEDES", "REFERENCES", "BLOCKS", "RESOLVES", "PARTIALLY_RESOLVES",
    "REQUIRES_OWNER_DECISION", "VERSION_OF", "VALIDATES",
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
}


def _sorted_glob(root, *parts):
    return sorted(globmod.glob(os.path.join(root, *parts)))


def _relpath(path, repo_root):
    return os.path.relpath(path, repo_root).replace(os.sep, "/")


def _load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


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

        if node_type not in ("OWNER_DECISION", "TRADER") and trader_id:
            target = resolve(trader_id, "BELONGS_TO_TRADER", eid, category="INVALID_TRADER_REFERENCE")
            if target:
                add_edge("BELONGS_TO_TRADER", from_node_id, target, eid, trader_id, source_file, created_at)

        if node_type in ("STRATEGY_ASSERTION", "CHART_EXAMPLE", "STRATEGY_RULE", "UNRESOLVED_QUESTION") and family_id:
            target = resolve(family_id, "BELONGS_TO_STRATEGY_FAMILY", eid, category="INVALID_STRATEGY_FAMILY_REFERENCE")
            if target:
                add_edge("BELONGS_TO_STRATEGY_FAMILY", from_node_id, target, eid, family_id, source_file, created_at)

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

    nodes.sort(key=lambda n: n["nodeId"])
    edges.sort(key=lambda e: e["edgeId"])
    return nodes, edges, findings, raw_by_entity_id

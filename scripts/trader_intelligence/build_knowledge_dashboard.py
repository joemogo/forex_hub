#!/usr/bin/env python3
"""MOGO Trader Intelligence -- Knowledge Dashboard generator.

Pure Python standard library. NO NETWORK ACCESS. NO LLM. READ-ONLY over every
authoritative record: this script opens the evidence store, the graph build,
and the decision log for reading, and writes exactly one file --
docs/trader-intelligence/KNOWLEDGE-DASHBOARD.md.

It never creates, edits, or deletes an EvidenceItem, Claim, Link, Intake,
Blueprint, Profile, Gap, Hypothesis, Question, ContradictionRecord, or
OwnerDecision. It never touches index.html, any protected function, or any
trading state. Regenerating it is always safe and always idempotent for a
given repository state.

Run after every ingestion (Operator Playbook, Stage 8b):

    python3 scripts/trader_intelligence/build_knowledge_dashboard.py
"""
import glob as globmod
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import graph_common as gc      # noqa: E402
import query_evidence as qe    # noqa: E402

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TI_ROOT = os.path.join(REPO_ROOT, "docs", "trader-intelligence")
EVIDENCE_ROOT = os.path.join(TI_ROOT, "evidence")
OUT_PATH = os.path.join(TI_ROOT, "KNOWLEDGE-DASHBOARD.md")

# Confidence states in ascending order of support, for the distribution table.
_CONFIDENCE_ORDER = [
    "insufficient_evidence", "tentative", "emerging", "supported", "strongly_supported",
    "contested", "weakened", "contradicted", "unresolved",
]

# A source is "promotable-capable" only once a claim can exceed `emerging`,
# which requires more than one independence group. Kept as a named constant so
# the dashboard explains the ceiling rather than merely reporting it.
_SUPPORTED_THRESHOLD = 45.0
_POINTS_PER_GROUP = 22.0


def _load_json_dir(path, id_field):
    out = {}
    if not os.path.isdir(path):
        return out
    for p in sorted(globmod.glob(os.path.join(path, "*.json"))):
        with open(p, "r", encoding="utf-8") as f:
            record = json.load(f)
        out[record[id_field]] = record
    return out


def _pending_sources(idx):
    """Transcripts sitting in the intake queue awaiting work.

    `intake/pending/` is the real queue: `ingest.py` moves a file out of it at
    the start of phase 1. `intake/processing/` is also reported, because a file
    left there means an ingestion was started and never applied -- outstanding
    work that would otherwise be invisible.

    Deliberately does NOT scan `imports/`: everything there is either a raw
    archive or a normalized derivative of an already-registered source."""
    pending = []
    for queue in ("pending", "processing"):
        d = os.path.join(TI_ROOT, "intake", queue)
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            if name.startswith(".") or name == "README.md" or name.endswith(".rejected.txt"):
                continue
            pending.append("%s (%s)" % (
                os.path.relpath(os.path.join(d, name), REPO_ROOT), queue))
    return pending


def _graph_summary():
    nodes_path = os.path.join(TI_ROOT, "graph", "build", "nodes.json")
    edges_path = os.path.join(TI_ROOT, "graph", "build", "edges.json")
    manifest_path = os.path.join(TI_ROOT, "graph", "build", "manifest.json")
    if not os.path.exists(nodes_path):
        return None
    def _read(p):
        with open(p, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, list) else (d.get("nodes") or d.get("edges") or [])
    nodes, edges = _read(nodes_path), _read(edges_path)
    build_id = None
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            build_id = json.load(f).get("buildId")
    by_type = {}
    for n in nodes:
        by_type[n["nodeType"]] = by_type.get(n["nodeType"], 0) + 1
    return {"buildId": build_id, "nodes": len(nodes), "edges": len(edges), "byType": by_type}


def _integrity(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f).get("summary")


def build_dashboard():
    idx = qe.EvidenceIndex.load(EVIDENCE_ROOT)
    traders = _load_json_dir_traders()
    decisions = _load_json_dir(os.path.join(TI_ROOT, "graph", "decisions"), "decisionId")
    pending = _pending_sources(idx)
    graph = _graph_summary()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    conf = {}
    for c in idx.claims.values():
        conf[c["confidenceState"]] = conf.get(c["confidenceState"], 0) + 1

    claims_by_type = {}
    for c in idx.claims.values():
        claims_by_type[c["claimType"]] = claims_by_type.get(c["claimType"], 0) + 1

    open_contradictions = [x for x in idx.contradictions.values() if x["status"] == "open"]
    open_questions = [q for q in idx.questions.values() if q.get("researchStatus") == "open"]
    blocking_questions = [q for q in open_questions
                          if q.get("blockingStatus") in ("blocks_promotion", "blocks_rule_candidate")]
    open_queue = [e for e in idx.queue_entries.values() if e.get("reviewStatus") == "open"]

    L = []
    L.append("# Knowledge Dashboard")
    L.append("")
    L.append("_Generated %s by `scripts/trader_intelligence/build_knowledge_dashboard.py`._" % now)
    L.append("_Read-only: regenerate after every ingestion. Never edit by hand — edits are lost._")
    L.append("")

    # --- Headline -------------------------------------------------------
    L.append("## At a glance")
    L.append("")
    L.append("| | Count |")
    L.append("|---|---|")
    L.append("| Registered sources | **%d** |" % len(idx.sources))
    L.append("| Completed ingestions | **%d** |" % len(idx.intakes))
    L.append("| **Transcripts awaiting work (intake queue)** | **%d** |" % len(pending))
    L.append("| Claims | %d |" % len(idx.claims))
    L.append("| Evidence items | %d |" % len(idx.items))
    L.append("| Transcript segments | %d |" % len(idx.segments))
    L.append("| Open contradictions | %d |" % len(open_contradictions))
    L.append("| Open questions (blocking) | %d (%d) |" % (len(open_questions), len(blocking_questions)))
    L.append("| Knowledge gaps | %d |" % len(idx.gaps))
    L.append("| Hypotheses | %d |" % len(idx.hypotheses))
    L.append("| Draft blueprints | %d |" % len(idx.blueprints))
    L.append("| Rule candidates | %d |" % len(idx.proposals))
    L.append("| **StrategyRules promoted** | **0** (none exist; promotion is human-only) |")
    L.append("| Open review-queue entries | %d |" % len(open_queue))
    L.append("| Owner decisions on record | %d |" % len(decisions))
    L.append("")

    if pending:
        L.append("> ⏳ **%d transcript(s) awaiting work:**" % len(pending))
        for p in pending:
            L.append(">   - `%s`" % p)
        L.append(">")
        L.append("> Anything in `processing` means an ingestion was started and never applied.")
        L.append("")
    else:
        L.append("> ✅ **Intake queue empty.** The ingestion pipeline is idle and awaiting input.")
        L.append("> Drop a transcript in `docs/trader-intelligence/intake/pending/` and run")
        L.append("> `ingest.py <file> --trader X` — see the [Operator Playbook](OPERATOR-PLAYBOOK.md).")
        L.append("")

    # --- Trader coverage ------------------------------------------------
    L.append("## Trader coverage")
    L.append("")
    L.append("| Trader | Sources | Claims | External research | MOGO implementation |")
    L.append("|---|---|---|---|---|")
    for tid in sorted(traders):
        t = traders[tid]
        n_src = len([s for s in idx.sources.values() if s.get("traderId") == tid])
        n_claims = len(idx.claims_for_trader(tid))
        L.append("| %s | %d | %d | `%s` | `%s` |" % (
            t.get("displayName") or tid, n_src, n_claims,
            t.get("externalResearchStatus"), t.get("repositoryModelStatus")))
    L.append("")

    # --- Confidence -----------------------------------------------------
    L.append("## Confidence distribution")
    L.append("")
    if not idx.claims:
        L.append("_No claims yet._")
    else:
        L.append("| State | Claims |")
        L.append("|---|---|")
        for state in _CONFIDENCE_ORDER:
            if conf.get(state):
                L.append("| `%s` | %d |" % (state, conf[state]))
        # Count only SUPPORTING/exemplifying links: contextual, qualifying and
        # unresolved links create an independence group but contribute nothing
        # to the score, so counting them would overstate the ceiling.
        def _support_groups(c):
            return {idx.items[l["evidenceId"]]["sourceId"]
                    for l in idx.links_for_claim(c["claimId"])
                    if l["evidenceId"] in idx.items
                    and l["relationshipType"] in ("supports", "exemplifies")}
        max_groups = max([1] + [len(_support_groups(c)) for c in idx.claims.values()])
        n_multi = sum(1 for c in idx.claims.values() if len(_support_groups(c)) >= 2)
        L.append("")
        L.append("**Ceiling:** the largest number of independent sources *supporting* any single "
                 "claim is **%d**; **%d claim(s)** have 2 or more. At ~%.0f points per independent "
                 "group against a %.0f-point `supported` threshold, %s" % (
                     max_groups, n_multi, _POINTS_PER_GROUP, _SUPPORTED_THRESHOLD,
                     "no claim can currently exceed `emerging` — this is by design, not a defect. "
                     "Note that trader-scoped claims never merge, so agreement BETWEEN educators "
                     "does not raise confidence (see CROSS-STRATEGY-ANALYSIS.md §6)."
                     if max_groups < 2 else
                     "claims backed by 2+ supporting groups can reach `supported`."))
    L.append("")

    L.append("### Claims by type")
    L.append("")
    if claims_by_type:
        L.append("| Type | Count |")
        L.append("|---|---|")
        for k in sorted(claims_by_type, key=lambda x: (-claims_by_type[x], x)):
            L.append("| `%s` | %d |" % (k, claims_by_type[k]))
    else:
        L.append("_None._")
    L.append("")

    # --- Blockers -------------------------------------------------------
    L.append("## Open contradictions")
    L.append("")
    if open_contradictions:
        L.append("| ID | Type | Severity | Claims |")
        L.append("|---|---|---|---|")
        for cr in sorted(open_contradictions, key=lambda x: x["contradictionId"]):
            L.append("| `%s` | %s | **%s** | `%s` vs `%s` |" % (
                cr["contradictionId"], cr["contradictionType"], cr["severity"],
                cr["claimAId"], cr["claimBId"]))
        L.append("")
        L.append("_An open contradiction blocks rule candidacy for every claim it touches._")
    else:
        L.append("_None._")
    L.append("")

    L.append("## Blocking open questions")
    L.append("")
    if blocking_questions:
        order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        for q in sorted(blocking_questions, key=lambda x: (order.get(x.get("priority"), 9), x["questionId"])):
            L.append("- **[%s]** %s" % (q.get("priority"), q["questionText"]))
    else:
        L.append("_None._")
    L.append("")

    # --- Knowledge gaps -------------------------------------------------
    L.append("## Knowledge gaps")
    L.append("")
    if idx.gaps:
        L.append("| Category | Priority | Answer status |")
        L.append("|---|---|---|")
        order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        for g in sorted(idx.gaps.values(), key=lambda x: (order.get(x["researchPriority"], 9), x["category"])):
            L.append("| `%s` | **%s** | %s |" % (g["category"], g["researchPriority"], g["answerStatus"]))
    else:
        L.append("_None._")
    L.append("")

    # --- Graph and integrity --------------------------------------------
    L.append("## Knowledge Graph")
    L.append("")
    if graph:
        L.append("Build `%s` — **%d nodes, %d edges**." % (graph["buildId"], graph["nodes"], graph["edges"]))
        L.append("")
        L.append("| Node type | Count |")
        L.append("|---|---|")
        for k in sorted(graph["byType"], key=lambda x: (-graph["byType"][x], x)):
            L.append("| `%s` | %d |" % (k, graph["byType"][k]))
    else:
        L.append("_Graph not built._")
    L.append("")

    L.append("## Integrity")
    L.append("")
    ev = _integrity(os.path.join(EVIDENCE_ROOT, "reports", "integrity-report.json"))
    gr = _integrity(os.path.join(TI_ROOT, "graph", "reports", "integrity-report.json"))
    L.append("| Report | FATAL | ERROR | WARNING | INFO |")
    L.append("|---|---|---|---|---|")
    for label, s in (("Evidence", ev), ("Graph", gr)):
        if s:
            L.append("| %s | %d | %d | %d | %d |" % (
                label, s.get("FATAL", 0), s.get("ERROR", 0), s.get("WARNING", 0), s.get("INFO", 0)))
        else:
            L.append("| %s | – | – | – | – |" % label)
    L.append("")

    # --- Governance ------------------------------------------------------
    L.append("## Governance")
    L.append("")
    L.append("| Decision | Type | Scope | Replay | Status |")
    L.append("|---|---|---|---|---|")
    for d in sorted(decisions.values(), key=lambda x: x["decisionId"]):
        L.append("| `%s` | %s | %s | %s | %s |" % (
            d["decisionId"], d["decisionType"], d["approvalScope"],
            "✅" if d.get("replayAuthorization") else "❌", d["status"]))
    L.append("")
    L.append("**Standing constraints:** no claim promotes on a single source · contradictions are "
             "recorded, not resolved · confidence rises only via independent corroboration, replay, "
             "paper trading, or historical testing · all educators hold equal evidentiary standing · "
             "third-party material is internal-research only and must never be redistributed.")
    L.append("")

    # --- Next review ------------------------------------------------------
    n_intakes = len(idx.intakes)
    next_review_at = ((n_intakes // 10) + 1) * 10
    L.append("## Review cadence")
    L.append("")
    L.append("Completed ingestions: **%d**. Next Trader Intelligence Review due at **%d** "
             "(%d more to go). See [`TRADER-INTELLIGENCE-REVIEW.md`](TRADER-INTELLIGENCE-REVIEW.md)."
             % (n_intakes, next_review_at, next_review_at - n_intakes))
    L.append("")
    return "\n".join(L) + "\n"


def _load_json_dir_traders():
    out = {}
    root = os.path.join(TI_ROOT, "traders")
    if not os.path.isdir(root):
        return out
    for path in sorted(globmod.glob(os.path.join(root, "*", "profile.json"))):
        with open(path, "r", encoding="utf-8") as f:
            record = json.load(f)
        out[record["traderId"]] = record
    return out


def main():
    content = build_dashboard()
    gc.atomic_write_text(OUT_PATH, content)
    print("Wrote %s (%d bytes)" % (os.path.relpath(OUT_PATH, REPO_ROOT), len(content.encode("utf-8"))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

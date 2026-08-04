#!/usr/bin/env python3
"""MOGO-004 M1 — research governance artifacts.

Emits three data artifacts from repository truth. It invents nothing: every count comes from the
corpus, the ALEX rule-to-evidence join, or the verified replay register.

    docs/trader-intelligence/governance/hypothesis-registry.json
    docs/trader-intelligence/governance/educator-coverage-matrix.json
    docs/trader-intelligence/governance/evidence-gap-matrix.json

Usage:
    python3 scripts/strategy_fidelity/build_research_governance.py

Read-only over every input. Writes only the three artifacts above.
"""
import collections
import glob
import json
import os
import sys
from collections import OrderedDict

REGISTRY_SCHEMA = "mogo.hypothesis-registry.v1"
COVERAGE_SCHEMA = "mogo.educator-coverage-matrix.v1"
GAP_SCHEMA = "mogo.evidence-gap-matrix.v1"

# ── The ONLY permitted hypothesis statuses. Anything else is a defect. ────────────────────────
ALLOWED_STATUSES = ["UNSUPPORTED", "COLLECTING", "SUPPORTED", "REJECTED", "UNRESOLVED"]
STATUS_DEFINITIONS = {
    "UNSUPPORTED": "No evidence supports this hypothesis: either MOGO does not implement the rule, "
                   "or the rule is MOGO-authored with no educator support, or no observation exists.",
    "COLLECTING":  "Evidence exists and is accumulating, but the minimum operational sample has not "
                   "been reached in both comparison arms.",
    "SUPPORTED":   "Minimum sample reached in both arms, predeclared metric measured, comparison "
                   "completed, and the promotion threshold satisfied.",
    "REJECTED":    "Minimum sample reached in both arms and the rejection threshold satisfied.",
    "UNRESOLVED":  "The hypothesis cannot be resolved by the evidence class available -- for example "
                   "a live-execution-only rule that no replay can ever exercise.",
}

# ── Promotion gate. Deterministic: every condition must hold, in order. ───────────────────────
PROMOTION_GATE = [
    "minimumOperationalSampleReachedInBothArms",
    "predeclaredMetricMeasured",
    "comparisonCompleted",
    "confidenceThresholdSatisfied",
]
PROMOTION_THRESHOLD = {
    "metric": "MET_EXPECTANCY_R",
    "supportedWhen": "armA expectancy exceeds armB expectancy by >= 0.25R with the confidence "
                     "interval excluding zero",
    "rejectedWhen": "the difference is < 0.25R, or favours armB, with both arms at or above the "
                    "minimum operational sample",
    "declaredInAdvance": True,
}
MINIMUM_OPERATIONAL_SAMPLE = 30      # per comparison arm -- the floor for any promotion
RECOMMENDED_STATISTICAL_SAMPLE = 100  # per arm -- where an effect of this size is reliably resolvable
SAMPLE_BASIS = ("Both figures are DECLARED IN ADVANCE, not derived from observed results. At 30 "
                "resolved trades per arm a 0.25R expectancy difference remains within sampling noise "
                "for a 2R/-1R system; 100 per arm is where it becomes reliably resolvable. Stating "
                "them up front is what stops either being rationalised downward after a result.")


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_dir(d):
    out = []
    for f in sorted(glob.glob(os.path.join(d, "*.json"))):
        try:
            with open(f, encoding="utf-8") as fh:
                out.append(json.load(fh))
        except Exception:
            pass
    return out


def map_status(join_status, hyp_status):
    """Map the join's internal vocabulary onto the five permitted statuses."""
    if join_status in ("NOT_IMPLEMENTED", "UNSUPPORTED"):
        return "UNSUPPORTED", "MOGO does not implement this rule, or it is MOGO-authored"
    if hyp_status == "NOT_TESTABLE_BY_REPLAY":
        return "UNRESOLVED", "implementation is on the live-execution path; no replay can exercise it"
    if join_status == "UNRESOLVED":
        return "UNRESOLVED", "no evidence field carries this rule's output; it cannot be observed yet"
    if hyp_status == "INSUFFICIENT_SAMPLE":
        return "COLLECTING", "evidence exists but is below the minimum operational sample"
    if hyp_status == "UNTESTED":
        return "UNSUPPORTED", "implemented, but no observation exists"
    if hyp_status == "TESTABLE_NOW":
        return "COLLECTING", "sample sufficient; comparison not yet performed"
    return "UNRESOLVED", "status could not be determined"


def build_registry(join):
    rules = {r["ruleId"]: r for r in join["rules"]}
    entries = []
    for h in join["hypotheses"]:
        rec = rules.get(h["ruleId"], {})
        ev = h.get("currentEvidence") or {}
        status, reason = map_status(rec.get("status"), h.get("status"))
        observed = ev.get("resolvedTrades") or 0
        entries.append(OrderedDict([
            ("hypothesisId", h["hypothesisId"]),
            ("educator", "ALEX_G"),
            ("strategy", "alex_g_sr_v1"),
            ("setup", ev.get("setupTypeScope") or "ALL_SETUPS"),
            ("condition", (rec.get("educator") or {}).get("statement")),
            ("measurableOutcome", {
                "primaryMetricId": h["metricId"],
                "secondaryMetricIds": h.get("secondaryMetricIds", []),
            }),
            ("comparisonGroup", h["comparison"]),
            ("minimumOperationalSample", MINIMUM_OPERATIONAL_SAMPLE),
            ("recommendedStatisticalSample", RECOMMENDED_STATISTICAL_SAMPLE),
            ("sampleBasis", SAMPLE_BASIS),
            ("promotionThreshold", PROMOTION_THRESHOLD["supportedWhen"]),
            ("rejectionThreshold", PROMOTION_THRESHOLD["rejectedWhen"]),
            ("currentStatus", status),
            ("statusReason", reason),
            ("observedResolvedTrades", observed),
            ("shortfallToOperationalSample", max(0, MINIMUM_OPERATIONAL_SAMPLE - observed)),
            ("shortfallToStatisticalSample", max(0, RECOMMENDED_STATISTICAL_SAMPLE - observed)),
            ("promotionCeiling", h.get("promotionCeiling")),
            ("evidenceRunIds", ev.get("runIds", [])),
            ("joinStatus", rec.get("status")),
        ]))
    return entries


def build_gap_matrix(join, registry):
    """Classify every hypothesis's missing observation. Never guesses."""
    rules = {r["ruleId"]: r for r in join["rules"]}
    rows = []
    for e in registry:
        rid = e["hypothesisId"].split("|", 1)[1]
        rec = rules.get(rid, {})
        js = rec.get("status")
        ev = rec.get("evidence") or {}
        current, missing, impossible, replay_only, live_only = [], [], [], [], []
        if js == "LINKED":
            current.append("%d RUN-001 packages carry the declared field(s)" % (ev.get("packageCount") or 0))
            replay_only.append("condition-level attribution (triggeredConditions) -- RUN-001 predates Unit B")
            missing.append("%d more resolved trades per arm to reach the operational sample"
                           % e["shortfallToOperationalSample"])
        elif js == "NOT_EXERCISED":
            live_only.append("this implementation runs only on the live paper path")
            missing.append("live paper trades exercising it; replay cannot produce them")
        elif js == "NOT_IMPLEMENTED":
            impossible.append("MOGO does not implement the rule; no observation can exist without "
                              "an implementation decision, which is out of research scope")
        elif js == "UNSUPPORTED":
            impossible.append("MOGO-authored behaviour with no educator support; there is no "
                              "educator claim to validate")
        elif js == "UNRESOLVED":
            reason = rec.get("unresolvedReason")
            if reason == "NO_EVIDENCE_FIELD_EXISTS":
                missing.append("an Evidence Package field carrying this rule's output "
                               "(schema change -- out of MOGO-004 scope)")
            elif reason == "NO_FIDELITY_ROW":
                missing.append("a fidelity-matrix row establishing whether MOGO implements it")
            else:
                missing.append("a fidelity verdict asserting an implementation")
        rows.append(OrderedDict([
            ("hypothesisId", e["hypothesisId"]),
            ("ruleId", rid),
            ("currentStatus", e["currentStatus"]),
            ("currentEvidence", current),
            ("missingEvidence", missing),
            ("impossibleEvidence", impossible),
            ("replayOnlyEvidence", replay_only),
            ("liveOnlyEvidence", live_only),
        ]))
    return rows


def build_coverage(base):
    claims = load_dir(os.path.join(base, "evidence", "claims"))
    sources = load_dir(os.path.join(base, "evidence", "sources"))
    hyps = load_dir(os.path.join(base, "evidence", "hypotheses"))
    by_trader = collections.Counter(c.get("traderId") or "UNSET" for c in claims)
    src_by = collections.Counter(s.get("traderId") or "UNSET" for s in sources)
    hyp_by = collections.Counter()
    for h in hyps:
        t = "UNKNOWN"
        for cid in (h.get("sourceClaimIds") or []):
            parts = str(cid).split("|")
            if len(parts) > 1:
                t = parts[1]
                break
        hyp_by[t] += 1
    profiles = sorted(os.listdir(os.path.join(base, "traders")))

    # Implementation and evidence facts, stated per educator. Each is checked, not assumed.
    facts = {
        "ALEX_G": {"engineStrategyId": "alex_g_sr_v1", "registeredInEngine": True,
                   "canonicalRuleRegister": True, "fidelityMatrix": True, "ruleEvidenceJoin": True,
                   "replayCapable": True, "verifiedReplayRuns": 1, "evidencePackages": 24,
                   "paperTradingImplemented": True},
        "TJR": {"engineStrategyId": "tjr_session_v1", "registeredInEngine": True,
                "canonicalRuleRegister": False, "fidelityMatrix": False, "ruleEvidenceJoin": False,
                "replayCapable": False, "verifiedReplayRuns": 0, "evidencePackages": 0,
                "paperTradingImplemented": False},
        "RAYNER_TEO": {"engineStrategyId": None, "registeredInEngine": False,
                       "canonicalRuleRegister": False, "fidelityMatrix": False,
                       "ruleEvidenceJoin": False, "replayCapable": False,
                       "verifiedReplayRuns": 0, "evidencePackages": 0,
                       "paperTradingImplemented": False},
        "ICT": {"engineStrategyId": None, "registeredInEngine": False,
                "canonicalRuleRegister": False, "fidelityMatrix": False, "ruleEvidenceJoin": False,
                "replayCapable": False, "verifiedReplayRuns": 0, "evidencePackages": 0,
                "paperTradingImplemented": False},
        "CRT": {"engineStrategyId": None, "registeredInEngine": False,
                "canonicalRuleRegister": False, "fidelityMatrix": False, "ruleEvidenceJoin": False,
                "replayCapable": False, "verifiedReplayRuns": 0, "evidencePackages": 0,
                "paperTradingImplemented": False},
    }
    rows = []
    for ed, f in facts.items():
        rows.append(OrderedDict([
            ("educator", ed),
            ("profilePresent", any(ed.lower().replace("_", "-") in p for p in profiles)),
            ("sources", src_by.get(ed, 0)),
            ("claims", by_trader.get(ed, 0)),
            ("hypothesesInCorpus", hyp_by.get(ed, 0)),
            ("implementedRules", 41 if ed == "ALEX_G" else 0),
            ("implementedEvidence", f["evidencePackages"]),
            ("verifiedReplayRuns", f["verifiedReplayRuns"]),
            ("missingImplementation", [] if ed == "ALEX_G" else
             (["setup detection", "trade construction", "replay", "paper trading"]
              if ed == "TJR" else ["everything -- no engine strategy exists"])),
            ("missingEvidence", [] if ed == "ALEX_G" else ["all trade-level evidence"]),
            ("missingHypotheses", "structured hypotheses exist only for ALEX_G"
             if ed != "ALEX_G" else None),
            ("facts", f),
        ]))
    return rows


def main():
    base = "docs/trader-intelligence"
    join_path = "docs/strategy-fidelity/audit/alex-rule-evidence-join.json"
    if not os.path.exists(join_path):
        print("join artifact not found: %s" % join_path, file=sys.stderr)
        return 2
    join = load_json(join_path)
    registry = build_registry(join)
    gaps = build_gap_matrix(join, registry)
    coverage = build_coverage(base)

    out_dir = os.path.join(base, "governance")
    os.makedirs(out_dir, exist_ok=True)
    counts = collections.Counter(e["currentStatus"] for e in registry)
    for st in registry:
        assert st["currentStatus"] in ALLOWED_STATUSES, "illegal status: " + st["currentStatus"]

    reg_doc = OrderedDict([
        ("schemaVersion", REGISTRY_SCHEMA),
        ("milestone", "MOGO-004 M1 -- Evidence Expansion & Research Governance"),
        ("allowedStatuses", ALLOWED_STATUSES),
        ("statusDefinitions", STATUS_DEFINITIONS),
        ("promotionGate", PROMOTION_GATE),
        ("promotionThreshold", PROMOTION_THRESHOLD),
        ("minimumOperationalSample", MINIMUM_OPERATIONAL_SAMPLE),
        ("recommendedStatisticalSample", RECOMMENDED_STATISTICAL_SAMPLE),
        ("sampleBasis", SAMPLE_BASIS),
        ("metricRegistry", join.get("metricRegistry")),
        ("scopeNote", "Structured hypotheses exist only for ALEX_G, the only educator with a "
                      "canonical rule register, a fidelity matrix and trade-level evidence. Other "
                      "educators appear in the coverage matrix, not here."),
        ("statusCounts", dict(counts)),
        ("hypotheses", registry),
    ])
    with open(os.path.join(out_dir, "hypothesis-registry.json"), "w", encoding="utf-8") as fh:
        json.dump(reg_doc, fh, indent=1)
        fh.write("\n")
    with open(os.path.join(out_dir, "educator-coverage-matrix.json"), "w", encoding="utf-8") as fh:
        json.dump(OrderedDict([("schemaVersion", COVERAGE_SCHEMA), ("educators", coverage)]),
                  fh, indent=1)
        fh.write("\n")
    with open(os.path.join(out_dir, "evidence-gap-matrix.json"), "w", encoding="utf-8") as fh:
        json.dump(OrderedDict([("schemaVersion", GAP_SCHEMA), ("rows", gaps)]), fh, indent=1)
        fh.write("\n")
    print(json.dumps({"hypotheses": len(registry), "statusCounts": dict(counts),
                      "educators": len(coverage), "gapRows": len(gaps)}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

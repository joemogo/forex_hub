"""MOGO-002.6 Phases 7-10 + 12 — draft specification, spec delta, coverage, review queue, reports.

Deterministic: identical inputs produce byte-identical artifacts.
Writes ONLY to docs/knowledge-engineering/ and docs/reports/. The evidence store,
index.html, and the alex_g_sr_v1 production specification are never written to.
"""
import os
import sys
from collections import Counter, defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "..", "strategy_fidelity"))
import ke_model as ke        # noqa: E402
import ke_inventory as kinv  # noqa: E402
import ke_analysis as kan    # noqa: E402

REPO_ROOT = kinv.REPO_ROOT
KE_DIR = os.path.join(REPO_ROOT, "docs", "knowledge-engineering")
REPORT_DIR = os.path.join(REPO_ROOT, "docs", "reports")
DRAFT_STRATEGY_ID = "alex_g_educator_v2_draft"
DRAFT_VERSION = "v2.0.0-draft"


# --- Phase 7: draft specification -------------------------------------------

def build_draft(rules, inventory, contradictions, candidates, deferred):
    by_domain = defaultdict(list)
    for r in rules:
        by_domain[r["category"]].append(r)
    claims_by_domain = Counter(c["category"] for c in inventory["claims"])
    cand_by_domain = Counter(c["category"] for c in candidates)
    contra_by_domain = Counter(x["affectedCategory"] for x in contradictions)
    elig = {cl["claimId"] for cl in inventory["classifications"] if cl["candidateRuleEligible"]}
    unresolved_claims = Counter(c["category"] for c in inventory["claims"]
                                if c["claimId"] not in elig)

    reports, refs = [], []
    for domain in ke.STRATEGY_DOMAINS:
        drules = sorted(by_domain.get(domain, []), key=lambda r: r["ruleId"])
        refs += [ke.strategy_rule_reference(r["ruleId"], r["version"], domain) for r in drules]
        n_claims = claims_by_domain.get(domain, 0)
        det = len([r for r in drules if r["deterministic"]])
        with_unres = len([r for r in drules if r["unresolvedElements"]])

        if n_claims == 0:
            coverage, conf = "NONE", "NONE"
        elif not drules:
            coverage, conf = "CLAIMS_ONLY_NO_RULES", "NONE"
        elif det == 0:
            coverage, conf = "RULES_BUT_NONE_DETERMINISTIC", "LOW"
        elif with_unres > det:
            coverage, conf = "PARTIAL", "LOW"
        else:
            coverage, conf = "PARTIAL", "MEDIUM"

        missing = []
        if n_claims == 0:
            missing.append("No educator claim in the library addresses this domain at all.")
        if drules and with_unres:
            missing.append("%d of %d rules carry an unresolved parameter the source never states."
                           % (with_unres, len(drules)))
        if domain == "EXIT":
            missing.append("No claim describes closing a position on a market condition.")
        if domain == "RISK":
            missing.append("Risk SIZING is present; STOP PLACEMENT is absent -- position size "
                           "cannot be computed from these rules alone.")

        reports.append({
            "domain": domain,
            "claimsReviewed": n_claims,
            "candidateRules": cand_by_domain.get(domain, 0),
            "normalizedRules": len(drules),
            "deterministicRules": det,
            "rulesWithUnresolvedElements": with_unres,
            "unresolvedClaims": unresolved_claims.get(domain, 0),
            "contradictions": contra_by_domain.get(domain, 0),
            "coverageLevel": coverage,
            "confidenceLevel": conf,
            "missingSourceEvidence": missing,
        })

    return ke.strategy_specification_draft(
        strategy_id=DRAFT_STRATEGY_ID, draft_version=DRAFT_VERSION,
        title="ALEX (educator-derived) — DRAFT Strategy Specification v2",
        rule_references=refs, domain_reports=reports,
        provenance_note=(
            "Derived from the ALEX_G educator claim library (195 claims, 8 source artifacts) "
            "under Engineering Authority decision OD-1 (approved with modification). This draft "
            "is SEPARATE from and does NOT modify alex_g_sr_v1, which remains the production "
            "specification. Every rule references normalized rules by id rather than copying "
            "them, and every normalized rule carries its originating claim and verbatim excerpt."),
        derived_from_educator="ALEX_G")


# --- Phase 8: specification delta -------------------------------------------

def build_delta(rules, inventory):
    """Knowledge comparison against the production spec. Neither is declared correct."""
    try:
        import alex_specification as aspec
        prod = aspec.build_specification()
        prod_rules = prod["rules"]
        prod_available = True
    except Exception as exc:            # pragma: no cover - reported, never silent
        prod_rules, prod_available = [], False
        prod_err = str(exc)

    draft_by_domain = Counter(r["category"] for r in rules)
    prod_by_domain = Counter(r["category"] for r in prod_rules)

    shared, educator_additions, mogo_authored = [], [], []
    domains = sorted(set(list(draft_by_domain) + list(prod_by_domain)))
    for d in domains:
        p, q = prod_by_domain.get(d, 0), draft_by_domain.get(d, 0)
        if p and q:
            shared.append({"domain": d, "productionRules": p, "draftRules": q})
        elif q and not p:
            educator_additions.append({
                "domain": d, "draftRules": q,
                "note": "The educator library covers this domain; the production specification "
                        "has no rule in it."})
        elif p and not q:
            mogo_authored.append({
                "domain": d, "productionRules": p,
                "note": "The production specification covers this domain; the educator library "
                        "yields no normalized rule for it."})

    lineage = [{
        "issue": "Two unrelated bodies of Alex knowledge",
        "evidence": "DECISION|MOGO|20260727|004 and traders/alex-g/profile.json state that "
                    "alex_g_sr_v1's rules come from MOGO's own implementation, NOT this "
                    "educator's published material. The two specifications share a name and an "
                    "educator label but not a lineage.",
        "impact": "A domain appearing in both is NOT evidence that the production rule came from "
                  "the educator. Overlap here is convergence, not derivation.",
        "resolution": "OD-1 already ruled: alex_g_sr_v1 remains production; this draft is source "
                      "material for a future governed milestone.",
    }]

    risk_rules = [r for r in rules if r["category"] == "RISK"]
    stop_rules = [r for r in risk_rules if "stop" in (r["canonicalStatement"] or "").lower()]
    tm_rules = [r for r in rules if r["category"] == "TRADE_MANAGEMENT"]
    exit_rules = [r for r in rules if r["category"] == "EXIT"]

    return {
        "modelVersion": ke.KE_MODEL_VERSION,
        "productionSpecification": "alex_g_sr_v1",
        "draftSpecification": DRAFT_STRATEGY_ID,
        "productionSpecificationAvailable": prod_available,
        "productionRuleCount": len(prod_rules),
        "draftRuleCount": len(rules),
        "sharedDomains": shared,
        "educatorSupportedAdditions": educator_additions,
        "mogoAuthoredOnlyDomains": mogo_authored,
        "lineageConflicts": lineage,
        "riskGap": {
            "draftRiskRules": len(risk_rules),
            "draftStopPlacementRules": len(stop_rules),
            "productionRiskRules": prod_by_domain.get("RISK", 0),
            "finding": ("The educator library supplies %d RISK rules -- all of them SIZING. "
                        "Stop PLACEMENT rules: %d. The production specification supplies %d risk "
                        "rules. Neither body of knowledge states where the stop goes, so the "
                        "MOGO-002.5 finding GAP-RISK-001 is NOT closed by this draft."
                        % (len(risk_rules), len(stop_rules), prod_by_domain.get("RISK", 0))),
        },
        "tradeManagementGap": {
            "draftRules": len(tm_rules),
            "productionRules": prod_by_domain.get("TRADE_MANAGEMENT", 0),
            "finding": ("The educator library supplies %d trade-management rules against %d in "
                        "production. This is the one domain where the draft adds materially."
                        % (len(tm_rules), prod_by_domain.get("TRADE_MANAGEMENT", 0))),
        },
        "exitGap": {
            "draftRules": len(exit_rules),
            "productionRules": prod_by_domain.get("EXIT", 0),
            "finding": "Neither specification contains a single EXIT rule. Exit behaviour in the "
                       "shipped engine is entirely MOGO-authored.",
        },
        "note": "This is a KNOWLEDGE comparison. Neither specification is declared correct, and "
                "nothing here proposes an implementation change.",
    }


# --- Phase 9: coverage ------------------------------------------------------

def build_coverage(inventory, groups, contradictions, candidates, rules, deferred, draft):
    totals = kinv.classification_totals(inventory)
    elig = [cl for cl in inventory["classifications"] if cl["candidateRuleEligible"]]
    return {
        "modelVersion": ke.KE_MODEL_VERSION,
        "generatorVersion": ke.KE_GENERATOR_VERSION,
        "educatorId": inventory["educatorId"],
        "totals": {
            "sourceArtifacts": inventory["sourceArtifactCount"],
            "claims": inventory["claimCount"],
            "candidateRuleEligibleClaims": {"n": len(elig), "of": inventory["claimCount"]},
            "candidateRules": len(candidates),
            "normalizedRules": len(rules),
            "deferredCandidates": len(deferred),
            "duplicateGroups": len(groups),
            "contradictions": len(contradictions),
            "approvedRules": {"n": 0, "of": len(rules),
                              "note": "MOGO-002.6 may not approve any rule (OD-1 mod. 6)."},
            "draftRules": {"n": len(rules), "of": len(rules)},
        },
        "claimsByCategory": totals["byClassification"],
        "claimsByExplicitness": totals["byExplicitness"],
        "claimsByStrategyDomain": totals["byStrategyDomain"],
        "claimsBySource": totals["bySource"],
        "confidenceDistribution": {
            "claims": totals["byConfidence"],
            "normalizedRules": dict(sorted(Counter(r["confidence"] for r in rules).items())),
        },
        "coverageByDomain": [
            {"domain": d["domain"],
             "claims": d["claimsReviewed"],
             "normalizedRules": "%d / %d candidates" % (d["normalizedRules"], d["candidateRules"]),
             "deterministic": "%d / %d rules" % (d["deterministicRules"], d["normalizedRules"]),
             "coverageLevel": d["coverageLevel"], "confidenceLevel": d["confidenceLevel"]}
            for d in draft["domainReports"]],
        "sourceTraceability": {
            "claimsWithSourceReference": {"n": inventory["claimCount"], "of": inventory["claimCount"]},
            "rulesWithSourceMapping": {"n": len([r for r in rules if r["sourceMappings"]]),
                                       "of": len(rules)},
            "rulesWithVerbatimExcerpt": {
                "n": len([r for r in rules
                          if any(m.get("exactExcerpt") for m in r["sourceMappings"])]),
                "of": len(rules)},
        },
        "unresolvedItems": {
            "rulesWithUnresolvedElements": {"n": len([r for r in rules if r["unresolvedElements"]]),
                                            "of": len(rules)},
            "nonDeterministicRules": {"n": len([r for r in rules if not r["deterministic"]]),
                                      "of": len(rules)},
        },
        "highestPriorityMissingKnowledge": [
            "STOP PLACEMENT — zero rules across 195 claims and 8 sources. Position size is not "
            "computable without it, so no risk rule here can be implemented.",
            "EXIT — zero claims and zero rules in the entire library.",
            "SESSION WINDOWS — session rules exist and are prescriptive, but their hours are "
            "shown on-screen and never spoken, so they are absent from every transcript.",
            "INDICATOR SETTINGS — the EMA is load-bearing in two sources and its period is never "
            "stated.",
            "SWING SIGNIFICANCE — the parameter that decides which highs and lows count is "
            "undefined and is contradicted across educators.",
        ],
        "recommendedNextSourceMaterial": [
            "An ALEX_G source that states stop placement (BACKLOG-002/A1-STOP). Highest leverage "
            "single acquisition: it would make the 13 risk rules implementable.",
            "Further LIVE sessions (BACKLOG-002/A2-LIVE) — one live session produced three "
            "filters absent from six instructional sources.",
            "Any source in which the session-hours graphic is read aloud.",
        ],
        "note": "Coverage is reported as numerator/denominator per domain. No single composite "
                "score is emitted: one number would conceal that EXIT is zero and RISK has no "
                "stop rule.",
    }


# --- Phase 10: human review queue -------------------------------------------

_PRIORITY_DOMAIN_RANK = {
    "NO_TRADE_CONDITIONS": 1, "SETUP": 1, "ENTRY": 2, "RISK": 3,
    "TRADE_MANAGEMENT": 6, "EXIT": 7, "SESSION_RESTRICTIONS": 4,
    "INVALIDATION": 2, "TIMEFRAMES": 5, "MARKET_STRUCTURE": 5,
    "LIQUIDITY": 5, "DIRECTIONAL_BIAS": 5, "MARKET_CONDITIONS": 8,
    "DISCRETIONARY_ELEMENTS": 9, "UNRESOLVED_QUESTIONS": 10,
}


def build_review_queue(rules, contradictions, deferred, inventory):
    items, n = [], 0

    # 1. High-severity contradictions first -- they can invalidate a rule outright.
    for x in sorted(contradictions, key=lambda c: (
            {"blocking": 0, "material": 1, "minor": 2}.get(c["severity"], 3), c["contradictionId"])):
        if x["severity"] == "minor":
            continue
        n += 1
        items.append(ke.human_review_state(
            review_id="KEREV|%03d" % n,
            issue="[%s] %s" % (x["severity"].upper(), x["normalizedIssueStatement"][:220]),
            source_evidence=[x["originRecord"]], affected_claims=x["claimIds"],
            candidate_rule_id=None,
            impact="Affects %s. A normalized rule in this domain cannot be trusted while the "
                   "contradiction is open." % x["affectedCategory"],
            interpretations=x["possibleInterpretations"],
            recommendation=x["recommendedCompletionPath"],
            smallest_decision="Record which interpretation governs, or defer pending %s."
                              % ("replay" if x["replayCouldHelp"] else "further source acquisition"),
            priority_rank=_PRIORITY_DOMAIN_RANK.get(x["affectedCategory"], 9)))

    # 2. Rules that gate whether a trade is taken AND carry an unresolved parameter.
    gating = [r for r in rules
              if r["category"] in ("NO_TRADE_CONDITIONS", "SETUP", "ENTRY", "INVALIDATION")
              and r["required"] and r["unresolvedElements"]]
    for r in sorted(gating, key=lambda r: r["ruleId"]):
        n += 1
        items.append(ke.human_review_state(
            review_id="KEREV|%03d" % n,
            issue="Required %s rule with an unresolved parameter: %s"
                  % (r["category"], (r["canonicalStatement"] or "")[:160]),
            source_evidence=[m["sourceId"] for m in r["sourceMappings"]],
            affected_claims=[m["claimId"] for m in r["sourceMappings"]],
            candidate_rule_id=r["ruleId"].replace("KERULE", "KECAND"),
            impact="This rule decides whether a trade is taken, and the source does not supply "
                   "the parameter it depends on: %s" % "; ".join(r["unresolvedElements"]),
            interpretations=[
                "Acquire source material that states the parameter, then normalize.",
                "Defer the rule until replay can establish a defensible value empirically.",
                "Reject the rule as unimplementable from this educator's published material.",
            ],
            recommendation="Defer. MOGO must not choose the parameter -- doing so would author a "
                           "rule and attribute it to the educator.",
            smallest_decision="Decide whether this rule is DEFERRED or REJECTED for v2.",
            priority_rank=_PRIORITY_DOMAIN_RANK.get(r["category"], 9)))

    # 3. Deferred candidates.
    for d in deferred:
        n += 1
        items.append(ke.human_review_state(
            review_id="KEREV|%03d" % n,
            issue="Candidate not normalized: %s" % d["candidateRuleId"],
            source_evidence=[], affected_claims=[], candidate_rule_id=d["candidateRuleId"],
            impact=d["reason"],
            interpretations=["Normalize with the unresolved parameter explicitly carried.",
                             "Leave deferred until the contradiction is settled."],
            recommendation="Leave deferred; normalizing would require picking a side.",
            smallest_decision="Confirm deferral.", priority_rank=2))

    # 4. The structural decisions this milestone surfaces.
    for issue, impact, interps, rec, smallest, rank in [
        ("Stop placement is absent from the entire educator library",
         "13 RISK rules describe sizing only. Position size = risk / stop distance, so none of "
         "them is implementable. This is the same gap MOGO-002.5 recorded as GAP-RISK-001.",
         ["Acquire an ALEX_G source that states stop placement.",
          "Accept that this educator's published material cannot support a risk implementation.",
          "Permit MOGO-authored stop placement, recorded explicitly as MOGO-authored."],
         "Acquire, or formally accept the limitation. Do not permit an unlabelled MOGO-authored "
         "stop to enter a rule attributed to the educator.",
         "Decide whether stop placement is acquired, accepted as absent, or MOGO-authored.", 3),
        ("The draft duplicates production coverage in some domains without shared lineage",
         "Overlap between alex_g_sr_v1 and the draft is convergence, not derivation "
         "(DECISION|MOGO|20260727|004). Treating overlap as corroboration would be a lineage error.",
         ["Keep the two specifications permanently separate.",
          "Plan a future milestone that reconciles them under explicit approval."],
         "Keep separate for now; reconciliation is its own governed milestone.",
         "Confirm the two specifications remain separate.", 1),
    ]:
        n += 1
        items.append(ke.human_review_state(
            review_id="KEREV|%03d" % n, issue=issue, source_evidence=["MOGO-002.5", "MOGO-002.6"],
            affected_claims=[], candidate_rule_id=None, impact=impact,
            interpretations=interps, recommendation=rec, smallest_decision=smallest,
            priority_rank=rank))

    items.sort(key=lambda i: (i["priorityRank"], i["reviewId"]))
    return items


# --- Writers ----------------------------------------------------------------

def _md_table(headers, rows):
    out = ["| " + " | ".join(str(h) for h in headers) + " |",
           "|" + "|".join(["---"] * len(headers)) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(out)


def generate_all():
    inv = kinv.build_inventory()
    ev = kinv.load_evidence()
    groups = kan.build_duplicate_groups(inv)
    contradictions = kan.build_contradictions(inv, ev)
    candidates = kan.build_candidate_rules(inv, groups, contradictions)
    rules, decisions, deferred = kan.normalize(candidates, inv)
    draft = build_draft(rules, inv, contradictions, candidates, deferred)
    delta = build_delta(rules, inv)
    coverage = build_coverage(inv, groups, contradictions, candidates, rules, deferred, draft)
    queue = build_review_queue(rules, contradictions, deferred, inv)

    gaps = [
        ke.knowledge_gap("KEGAP-001", "RISK",
                         "No stop-placement rule exists anywhere in the educator library.",
                         "195 claims, 8 sources, 0 stop_rule claims. 13 RISK rules are all sizing.",
                         "Position size is not computable; no risk rule is implementable.",
                         "Acquire a source stating stop placement (BACKLOG-002/A1-STOP), or record "
                         "that the educator's published material cannot support one.",
                         priority="CRITICAL", blocking=True),
        ke.knowledge_gap("KEGAP-002", "EXIT",
                         "No claim in the library addresses closing a position on a market condition.",
                         "0 claims classified EXIT across all 8 sources.",
                         "Exit behaviour cannot be specified from this educator at all.",
                         "Source acquisition. No amount of re-analysis of existing claims can "
                         "produce an exit rule that was never stated.",
                         priority="CRITICAL", blocking=True),
        ke.knowledge_gap("KEGAP-003", "SESSION_RESTRICTIONS",
                         "Session rules are prescriptive but their hours are never spoken.",
                         "Session windows are displayed on an on-screen map; the transcript "
                         "carries the rule and not its parameter.",
                         "Session rules cannot be implemented as stated.",
                         "Acquire a source that reads the hours aloud, or capture them from the "
                         "video frame under a separate approved method.",
                         priority="HIGH", blocking=True),
        ke.knowledge_gap("KEGAP-004", "MARKET_STRUCTURE",
                         "Swing-point significance is undefined and cross-educator contradicted.",
                         "ALEX_G: any body close counts, no minimum. RAYNER_TEO: only major "
                         "swings. Recorded as XCONTRA|20260729|001.",
                         "Determines which highs and lows count, therefore every structure rule.",
                         "Replay sensitivity sweep (RC-29), which requires replay authorization.",
                         priority="HIGH", blocking=False),
    ]

    os.makedirs(KE_DIR, exist_ok=True)
    paths = {}
    for name, obj in [
        ("claim-inventory.json", {"inventory": inv, "totals": kinv.classification_totals(inv)}),
        ("duplicate-groups.json", {"groups": groups, "count": len(groups)}),
        ("contradiction-register.json", {"contradictions": contradictions, "count": len(contradictions)}),
        ("candidate-rules.json", {"candidates": candidates, "count": len(candidates)}),
        ("normalized-rules.json", {"rules": rules, "count": len(rules)}),
        ("normalization-decisions.json", {"decisions": decisions, "deferred": deferred}),
        ("claim-to-rule-mapping.json", {"mappings": [m for r in rules for m in r["sourceMappings"]]}),
        ("alex-strategy-specification-v2-draft.json", draft),
        ("specification-delta.json", delta),
        ("knowledge-coverage.json", coverage),
        ("human-review-queue.json", {"items": queue, "count": len(queue)}),
        ("knowledge-gaps.json", {"gaps": gaps, "count": len(gaps)}),
    ]:
        paths[name] = ke.write(os.path.join(KE_DIR, name), obj)

    ctx = dict(inv=inv, groups=groups, contradictions=contradictions, candidates=candidates,
               rules=rules, decisions=decisions, deferred=deferred, draft=draft, delta=delta,
               coverage=coverage, queue=queue, gaps=gaps, paths=paths)
    return ctx


if __name__ == "__main__":
    ctx = generate_all()
    print("claims=%d candidates=%d normalized=%d deferred=%d groups=%d contradictions=%d reviews=%d"
          % (ctx["inv"]["claimCount"], len(ctx["candidates"]), len(ctx["rules"]),
             len(ctx["deferred"]), len(ctx["groups"]), len(ctx["contradictions"]),
             len(ctx["queue"])))
    for k, v in sorted(ctx["paths"].items()):
        print("  %s" % os.path.relpath(v, REPO_ROOT))

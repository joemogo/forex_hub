"""MOGO-002.5 Phase 4 — deterministic StrategySpecification vs StrategyImplementationManifest comparison.

DESIGN RULE THAT OVERRIDES EVERYTHING ELSE HERE
-----------------------------------------------
    Uncertainty is preserved. It is never resolved into a MATCH.

Concretely, the classification of the RULE is consulted BEFORE the
implementation status, because a rule the source never pinned down cannot be
"correctly implemented" no matter what the code does:

    UNRESOLVED      -> AMBIGUOUS       (always -- the spec itself is unclear)
    DISCRETIONARY   -> NOT_APPLICABLE  (always -- the source declined to mandate it)
    INFERRED        -> UNVERIFIABLE    (unless a test pins the behaviour)

Only once a rule is EXPLICIT or IMPLIED does the implementation status decide
the verdict. This ordering is the whole point of the engine: it is what stops a
confident-looking implementation of an ambiguous rule from scoring as fidelity.

Determinism: given the same spec and manifest, output is byte-identical. Rules
are processed in specification order; findings never depend on dict iteration.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fidelity_model as fm  # noqa: E402

COMPARISON_ENGINE_VERSION = "1.0.0"


def _finding(rule, status, rationale, mapping=None):
    return fm.strategy_fidelity_finding(
        rule_id=rule["id"],
        status=status,
        category=rule["category"],
        classification=rule["classification"],
        required=rule["required"],
        deterministic=rule["deterministic"],
        rationale=rationale,
        implementation_status=(mapping or {}).get("implementationStatus"),
        implementation_references=(mapping or {}).get("implementationReferences") or [],
        tests=(mapping or {}).get("tests") or [],
        limitations=(mapping or {}).get("knownLimitations") or [])


def compare_rule(rule, mapping):
    """One rule -> one finding. Pure; no I/O; no global state."""
    cls = rule["classification"]
    status = (mapping or {}).get("implementationStatus")

    if mapping is None:
        return _finding(
            rule, "UNVERIFIABLE",
            "No manifest mapping exists for this rule, so no claim about the implementation "
            "can be made. Absence of a mapping is NOT evidence of absence of code.")

    # --- Spec-side uncertainty dominates ------------------------------------
    if cls == "UNRESOLVED":
        return _finding(
            rule, "AMBIGUOUS",
            "The specification is UNRESOLVED for this rule, so there is no definite statement to "
            "compare code against. The implementation is recorded as %s, but that cannot be "
            "scored as fidelity in either direction." % status, mapping)

    if cls == "DISCRETIONARY":
        return _finding(
            rule, "NOT_APPLICABLE",
            "The source explicitly leaves this to trader judgement, so neither implementing nor "
            "omitting it can be a fidelity failure. Implementation status is %s." % status, mapping)

    if cls == "INFERRED":
        if status in ("IMPLEMENTED", "APPROXIMATED") and mapping.get("tests"):
            return _finding(
                rule, "APPROXIMATED",
                "Rule is INFERRED rather than stated by the source. A code path exists and is "
                "test-covered, so behaviour is pinned -- but fidelity to the SOURCE remains "
                "unestablished because the source never stated the rule.", mapping)
        return _finding(
            rule, "UNVERIFIABLE",
            "Rule is INFERRED and not pinned by a test, so there is nothing authoritative to "
            "compare against.", mapping)

    # --- EXPLICIT / IMPLIED: the implementation status decides ---------------
    if status == "IMPLEMENTED":
        if not mapping.get("inspected"):
            return _finding(
                rule, "UNVERIFIABLE",
                "Manifest claims IMPLEMENTED but the code path was not inspected.", mapping)
        return _finding(
            rule, "MATCH",
            "Stated rule; an inspected code path implements it as written. %s"
            % (mapping.get("implementationNotes") or ""), mapping)

    if status == "APPROXIMATED":
        return _finding(
            rule, "APPROXIMATED",
            "A code path exists but substitutes a parameter or behaviour the source does not "
            "state. %s" % (mapping.get("approximationDetail") or ""), mapping)

    if status == "NOT_IMPLEMENTED":
        return _finding(
            rule, "MISSING_IMPLEMENTATION",
            "The source states this rule and no code path implements it.", mapping)

    if status == "UNSUPPORTED":
        return _finding(
            rule, "IMPLEMENTATION_DIFFERS",
            "The rule cannot be implemented in the current architecture, so behaviour necessarily "
            "differs from the specification.", mapping)

    # UNKNOWN
    return _finding(
        rule, "UNVERIFIABLE",
        "Implementation status is UNKNOWN -- the code path has not been inspected. This is "
        "deliberately NOT reported as missing: absence of inspection is not absence of code.",
        mapping)


def compare(specification, manifest):
    """Full comparison. Returns findings + category summaries + coverage metrics."""
    if specification["strategyId"] != manifest["strategyId"]:
        raise fm.FidelityModelError(
            "strategyId mismatch: spec %r vs manifest %r"
            % (specification["strategyId"], manifest["strategyId"]))

    spec_version_mismatch = (
        specification["specificationVersion"] != manifest["specificationVersion"])

    by_rule = {m["ruleId"]: m for m in manifest["mappings"]}
    findings = []
    for rule in specification["rules"]:          # specification order == deterministic
        findings.append(compare_rule(rule, by_rule.get(rule["id"])))

    # Mappings that reference a rule the specification does not contain.
    spec_ids = {r["id"] for r in specification["rules"]}
    orphan_mappings = sorted(rid for rid in by_rule if rid not in spec_ids)
    for rid in orphan_mappings:
        findings.append(fm.strategy_fidelity_finding(
            rule_id=rid, status="EXTRA_IMPLEMENTATION_RULE",
            category="DISCRETIONARY_ELEMENTS", classification="INFERRED",
            required=False, deterministic=False,
            rationale="The manifest maps this ruleId but the specification does not define it.",
            implementation_status=by_rule[rid]["implementationStatus"],
            implementation_references=by_rule[rid]["implementationReferences"]))

    # Declared extra implementation rules -- code behaviour with no spec rule.
    for extra in manifest.get("extraImplementationRules", []):
        findings.append(fm.strategy_fidelity_finding(
            rule_id=extra["id"], status="EXTRA_IMPLEMENTATION_RULE",
            category=extra["category"], classification="INFERRED",
            required=False, deterministic=False,
            rationale="%s (origin: %s; affects trading behaviour: %s)"
                      % (extra["description"], extra["origin"],
                         "YES" if extra["affectsTradingBehavior"] else "no"),
            implementation_status="IMPLEMENTED",
            implementation_references=extra["implementationReferences"],
            tests=extra["tests"]))

    return {
        "comparisonEngineVersion": COMPARISON_ENGINE_VERSION,
        "specificationVersionMismatch": spec_version_mismatch,
        "findings": findings,
        "categorySummaries": summarize_by_category(findings),
        "coverage": coverage_metrics(specification, findings),
    }


def summarize_by_category(findings):
    """Per-category counts. Every category the taxonomy defines is emitted, even
    when empty -- an absent category reads as 'nothing to say', which is
    indistinguishable from 'no rules exist here', and those are different facts."""
    out = []
    for cat in fm.RULE_CATEGORIES:
        rows = [f for f in findings if f["category"] == cat]
        counts = {s: 0 for s in fm.FINDING_STATUSES}
        for f in rows:
            counts[f["status"]] += 1
        out.append({
            "category": cat,
            "ruleCount": len(rows),
            "statusCounts": counts,
            # Deliberately no composite score. The brief forbids relying on one,
            # and a single number would hide the difference between an ambiguous
            # rule and an unimplemented one.
            "specifiedRuleCount": len([f for f in rows
                                       if f["status"] != "EXTRA_IMPLEMENTATION_RULE"]),
            "extraImplementationCount": len([f for f in rows
                                             if f["status"] == "EXTRA_IMPLEMENTATION_RULE"]),
        })
    return out


def coverage_metrics(specification, findings):
    """Coverage reported as explicit numerator/denominator pairs, never as a
    lone percentage -- '80%' hides whether the denominator was 5 or 500."""
    spec_findings = [f for f in findings if f["status"] != "EXTRA_IMPLEMENTATION_RULE"]
    by_id = {f["ruleId"]: f for f in spec_findings}

    def frac(pred_rule):
        rules = [r for r in specification["rules"] if pred_rule(r)]
        matched = [r for r in rules if by_id.get(r["id"], {}).get("status") == "MATCH"]
        return {"matched": len(matched), "total": len(rules),
                "ruleIds": sorted(r["id"] for r in rules),
                "unmatchedRuleIds": sorted(r["id"] for r in rules
                                           if by_id.get(r["id"], {}).get("status") != "MATCH")}

    risk_rules = frac(lambda r: r["category"] == "RISK")
    tm_rules = frac(lambda r: r["category"] == "TRADE_MANAGEMENT")

    return {
        "explicitRuleCoverage": frac(lambda r: r["classification"] == "EXPLICIT"),
        "requiredRuleCoverage": frac(lambda r: r["required"]),
        "deterministicRuleFidelity": frac(lambda r: r["deterministic"]),
        "riskFidelity": risk_rules,
        "tradeManagementFidelity": tm_rules,
        "statusTotals": {s: len([f for f in spec_findings if f["status"] == s])
                         for s in fm.FINDING_STATUSES},
        "extraImplementationRuleCount": len([f for f in findings
                                             if f["status"] == "EXTRA_IMPLEMENTATION_RULE"]),
        "sourceTraceability": {
            "rulesWithSourceReference": len([r for r in specification["rules"]
                                             if r["sourceReferences"]]),
            "total": len(specification["rules"]),
        },
        "testCoverage": {
            "rulesWithNamedTest": len([f for f in spec_findings if f["tests"]]),
            "total": len(spec_findings),
        },
    }

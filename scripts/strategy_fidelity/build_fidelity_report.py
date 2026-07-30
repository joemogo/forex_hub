"""MOGO-002.5 Phase 7 — generate the ALEX StrategyFidelityReport.

Emits a deterministic JSON report and a human-readable Markdown companion.

TWO STATUSES ARE HARD-CODED TO THE SAFE VALUE AND CANNOT BE RAISED HERE
----------------------------------------------------------------------
  profitabilityStatus = UNVALIDATED  -- always. This milestone measures whether
      the code does what the specification says, which is orthogonal to whether
      the specification makes money. No input to this generator could justify
      any other value.

  executionReadiness  -- computed from real criteria and defaults to
      NOT_VERIFIED. It can only reach VERIFIED if every criterion genuinely
      passes; each criterion is reported individually so a single number never
      hides which one failed.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fidelity_model as fm         # noqa: E402
import fidelity_compare as fc       # noqa: E402
import alex_specification as aspec  # noqa: E402
import alex_manifest as amanifest   # noqa: E402

REPORT_VERSION = "1.0.0"
REPO_ROOT = aspec.REPO_ROOT
REPORT_DIR = os.path.join(REPO_ROOT, "docs", "strategy-fidelity", "reports")
MANIFEST_DIR = os.path.join(REPO_ROOT, "docs", "strategy-fidelity", "manifests")


def _execution_readiness(coverage, comparison, manifest):
    """Every criterion is a named boolean with its evidence. NOT_VERIFIED unless
    all pass -- and in this repository several genuinely do not."""
    req = coverage["requiredRuleCoverage"]
    crit = [
        {"criterion": "All required specification rules MATCH",
         "passed": req["matched"] == req["total"] and req["total"] > 0,
         "evidence": "%d/%d required rules matched; unmatched=%s"
                     % (req["matched"], req["total"], req["unmatchedRuleIds"])},
        {"criterion": "No ambiguous rules remain",
         "passed": coverage["statusTotals"]["AMBIGUOUS"] == 0,
         "evidence": "%d ambiguous" % coverage["statusTotals"]["AMBIGUOUS"]},
        {"criterion": "No unverifiable rules remain",
         "passed": coverage["statusTotals"]["UNVERIFIABLE"] == 0,
         "evidence": "%d unverifiable" % coverage["statusTotals"]["UNVERIFIABLE"]},
        {"criterion": "No missing implementations",
         "passed": coverage["statusTotals"]["MISSING_IMPLEMENTATION"] == 0,
         "evidence": "%d missing" % coverage["statusTotals"]["MISSING_IMPLEMENTATION"]},
        {"criterion": "Specification contains risk rules",
         "passed": coverage["riskFidelity"]["total"] > 0,
         "evidence": "specification defines %d RISK-category rules"
                     % coverage["riskFidelity"]["total"]},
        {"criterion": "Specification contains trade-management rules",
         "passed": coverage["tradeManagementFidelity"]["total"] > 0,
         "evidence": "specification defines %d TRADE_MANAGEMENT rules"
                     % coverage["tradeManagementFidelity"]["total"]},
        {"criterion": "No behaviour-affecting extra implementation rules",
         "passed": not any(e["affectsTradingBehavior"]
                           for e in manifest.get("extraImplementationRules", [])),
         "evidence": "%d extra rules affect trading behaviour"
                     % len([e for e in manifest.get("extraImplementationRules", [])
                            if e["affectsTradingBehavior"]])},
        {"criterion": "All manifest code references verify",
         "passed": manifest.get("referenceVerification", {}).get("problemCount", 1) == 0,
         "evidence": "%d reference problems"
                     % manifest.get("referenceVerification", {}).get("problemCount", -1)},
        {"criterion": "Specification and manifest agree on specification version",
         "passed": not comparison["specificationVersionMismatch"],
         "evidence": "mismatch=%s" % comparison["specificationVersionMismatch"]},
        {"criterion": "Replay validation has been performed",
         "passed": False,
         "evidence": "MOGO-002.5 explicitly does not begin replay engineering; "
                     "replayAuthorization is false on all six OwnerDecision records."},
    ]
    return {
        "status": "VERIFIED" if all(c["passed"] for c in crit) else "NOT_VERIFIED",
        "criteria": crit,
        "failedCount": len([c for c in crit if not c["passed"]]),
    }


def build_report(path=None):
    spec = aspec.build_specification(path)
    manifest = amanifest.build_manifest(path)
    comparison = fc.compare(spec, manifest)
    coverage = comparison["coverage"]

    version_ref = fm.strategy_version_reference(
        strategy_id=spec["strategyId"],
        specification_version=spec["specificationVersion"],
        implementation_version=manifest["implementationVersion"],
        engine_version=manifest["engineVersion"],
        rule_set_hash=spec["ruleSetHash"],
        configuration_hash=manifest["manifestHash"],
        decision_trace_version="mogo.decision-event.v1")

    findings = comparison["findings"]

    def of(status):
        return [f for f in findings if f["status"] == status]

    report = {
        "modelVersion": fm.FIDELITY_MODEL_VERSION,
        "reportGeneratorVersion": REPORT_VERSION,
        "comparisonEngineVersion": comparison["comparisonEngineVersion"],
        "specExtractorVersion": aspec.SPEC_EXTRACTOR_VERSION,
        "versionReference": version_ref,

        "profitabilityStatus": "UNVALIDATED",
        "profitabilityNote": (
            "This milestone verifies STRATEGY FIDELITY only -- whether the code does what the "
            "specification says. It makes no claim whatsoever about whether the specification is "
            "profitable, and no input to this generator can change this value."),

        "executionReadiness": _execution_readiness(coverage, comparison, manifest),

        "coverage": coverage,
        "categorySummaries": comparison["categorySummaries"],

        "findingsByStatus": {
            "verifiedMatches": of("MATCH"),
            "missingImplementation": of("MISSING_IMPLEMENTATION"),
            "differingImplementation": of("IMPLEMENTATION_DIFFERS"),
            "approximations": of("APPROXIMATED"),
            "extraImplementationLogic": of("EXTRA_IMPLEMENTATION_RULE"),
            "ambiguousRules": of("AMBIGUOUS"),
            "unverifiableRules": of("UNVERIFIABLE"),
            "notApplicable": of("NOT_APPLICABLE"),
        },

        "missingStrategyKnowledge": _knowledge_gaps(spec, coverage, manifest),
        "findings": findings,
        "specification": spec,
        "manifest": manifest,
    }
    return report


def _knowledge_gaps(spec, coverage, manifest):
    """Gaps in the SPECIFICATION, with a completion path each.

    The brief requires that incomplete source knowledge be reported with an
    import/completion path rather than guessed at."""
    gaps = []
    if coverage["riskFidelity"]["total"] == 0:
        gaps.append({
            "id": "GAP-RISK-001",
            "area": "RISK",
            "gap": "The specification contains ZERO risk rules, yet the implementation trades a "
                   "complete risk model (stopATRBuffer 0.25, riskPercent 1.0, minRR 2.0).",
            "evidence": "RULES_ALEXG.hubTestStandardizations states the stop-loss/take-profit/"
                        "risk/R:R mechanism is '100% unaddressed by the source'.",
            "impact": "Every ALEX paper trade's stop, target and position size derive from rules "
                      "with no source authority. Risk fidelity is not merely unverified -- it is "
                      "undefined, because there is nothing to verify against.",
            "completionPath": "Acquire and approve source material that states Alex's stop "
                              "placement, target selection and position sizing, then extend "
                              "RULES_ALEXG.originalAlexConcepts. Do NOT back-fill from the "
                              "Trader Intelligence ALEX_G claim library -- see GAP-PROV-001.",
        })
    if coverage["tradeManagementFidelity"]["total"] == 0:
        gaps.append({
            "id": "GAP-TM-001",
            "area": "TRADE_MANAGEMENT",
            "gap": "The specification contains ZERO trade-management rules (no partials, no "
                   "break-even, no trailing, no time-based exit).",
            "evidence": "No originalAlexConcepts entry addresses managing an open position.",
            "impact": "Exit behaviour (alexGUpdatePositionExcursionAndCheckExit, "
                      "alexGReconstructExitFromCandles) is entirely unspecified.",
            "completionPath": "Same as GAP-RISK-001; trade management would need its own approved "
                              "source concepts before exit fidelity can be assessed.",
        })
    gaps.append({
        "id": "GAP-AMBIG-001",
        "area": "SETUP",
        "gap": "Zone tightness (ALEX_SR_008) is required by the method but has no computable "
               "definition in the source.",
        "evidence": "RULES_ALEXG.originalAlexConcepts: 'demonstrated visually, no formula given'. "
                    "The implementation substitutes zoneClusterATRMultiplier=0.5, flagged "
                    "EXPERIMENTAL and 'not tuned against outcomes'.",
        "impact": "The single most load-bearing undefined parameter: it determines which reactions "
                  "group into one zone, and therefore the touch count that every setup depends on.",
        "completionPath": "Controlled sensitivity testing across the declared range "
                          "[0.25, 0.5, 0.75, 1.0]. Requires replay authorization -- out of scope "
                          "for MOGO-002.5.",
    })
    gaps.append({
        "id": "GAP-PROV-001",
        "area": "MARKET_CONDITIONS",
        "gap": "Two unrelated bodies of 'Alex' knowledge exist in this repository and must not be "
               "merged without an Engineering Authority decision.",
        "evidence": "(a) RULES_ALEXG.originalAlexConcepts -- 13 concepts, protected, the basis of "
                    "the shipped engine. (b) docs/trader-intelligence/ -- 195 ALEX_G claims from "
                    "the educator, all at 'emerging' confidence with zero rule candidates. "
                    "DECISION|MOGO|20260727|004 and traders/alex-g/profile.json both state that "
                    "the engine's rules come from MOGO's own implementation, NOT the educator's "
                    "published material.",
        "impact": "Using (b) as this engine's specification would fabricate a lineage the "
                  "repository explicitly denies, and would import 195 unvalidated claims into a "
                  "fidelity baseline.",
        "completionPath": "An Engineering Authority decision on whether alex_g_sr_v1 should be "
                          "re-specified against the educator library. If yes, that is a new "
                          "milestone with its own approval, not a fidelity fix.",
    })
    return gaps


# --- Markdown rendering ------------------------------------------------------

def _md_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join(["---"] * len(headers)) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(out)


def render_markdown(report):
    vr = report["versionReference"]
    cov = report["coverage"]
    er = report["executionReadiness"]
    L = []
    A = L.append

    A("# ALEX Strategy Fidelity Report")
    A("")
    A("**Generated by** MOGO-002.5 Strategy Fidelity Audit · "
      "**read-only analysis** — this report never alters trading behaviour.")
    A("")
    A(_md_table(["Field", "Value"], [
        ["Strategy", "`%s`" % vr["strategyId"]],
        ["Specification version", "`%s`" % vr["specificationVersion"]],
        ["Implementation version", "`%s`" % vr["implementationVersion"]],
        ["Engine version", "`%s`" % vr["engineVersion"]],
        ["Report generator version", "`%s`" % report["reportGeneratorVersion"]],
        ["Comparison engine version", "`%s`" % report["comparisonEngineVersion"]],
        ["Rule-set hash", "`%s`" % vr["ruleSetHash"][:16]],
        ["Decision trace version", "`%s`" % vr["decisionTraceVersion"]],
    ]))
    A("")
    A("## Headline statuses")
    A("")
    A("| | |")
    A("|---|---|")
    A("| **Profitability status** | **`UNVALIDATED`** — and unconditionally so. This milestone "
      "measures fidelity, not performance. |")
    A("| **Execution readiness** | **`%s`** — %d of %d criteria failed. |"
      % (er["status"], er["failedCount"], len(er["criteria"])))
    A("")
    A("### Execution-readiness criteria")
    A("")
    A(_md_table(["Criterion", "Result", "Evidence"],
                [[c["criterion"], "✅ pass" if c["passed"] else "❌ fail", c["evidence"]]
                 for c in er["criteria"]]))
    A("")
    A("## Coverage")
    A("")
    A("Reported as numerator/denominator, never as a bare percentage — a lone score would hide "
      "whether a denominator is 5 or 500, and would let an ambiguous rule look like a failure "
      "or a match depending on rounding.")
    A("")
    rows = []
    for key, label in [("explicitRuleCoverage", "Explicit-rule coverage"),
                       ("requiredRuleCoverage", "Required-rule coverage"),
                       ("deterministicRuleFidelity", "Deterministic-rule fidelity"),
                       ("riskFidelity", "Risk fidelity"),
                       ("tradeManagementFidelity", "Trade-management fidelity")]:
        c = cov[key]
        unmatched = ", ".join("`%s`" % r for r in c["unmatchedRuleIds"]) or "—"
        rows.append([label, "%d / %d" % (c["matched"], c["total"]), unmatched])
    st = cov["sourceTraceability"]
    rows.append(["Source traceability", "%d / %d" % (st["rulesWithSourceReference"], st["total"]),
                 "every rule cites RULES_ALEXG"])
    tc = cov["testCoverage"]
    rows.append(["Test coverage (named tests)", "%d / %d" % (tc["rulesWithNamedTest"], tc["total"]), "—"])
    A(_md_table(["Metric", "Value", "Unmatched / note"], rows))
    A("")
    A("## Finding totals")
    A("")
    A(_md_table(["Status", "Count"],
                [[k, v] for k, v in sorted(cov["statusTotals"].items()) if True]
                + [["EXTRA_IMPLEMENTATION_RULE (declared)", cov["extraImplementationRuleCount"]]]))
    A("")
    A("## Findings by status")
    for label, key in [("Verified matches", "verifiedMatches"),
                       ("Missing implementation", "missingImplementation"),
                       ("Differing implementation", "differingImplementation"),
                       ("Approximations", "approximations"),
                       ("Ambiguous rules", "ambiguousRules"),
                       ("Unverifiable rules", "unverifiableRules"),
                       ("Not applicable", "notApplicable"),
                       ("Extra implementation logic", "extraImplementationLogic")]:
        rows = report["findingsByStatus"][key]
        A("")
        A("### %s — %d" % (label, len(rows)))
        if not rows:
            A("")
            A("_None._")
            continue
        A("")
        A(_md_table(["Rule", "Category", "Class", "Req", "Rationale"],
                    [["`%s`" % f["ruleId"], f["category"], f["classification"],
                      "yes" if f["required"] else "no",
                      (f["rationale"] or "").strip()[:230]] for f in rows]))
    A("")
    A("## Category summaries")
    A("")
    A(_md_table(["Category", "Spec rules", "Extra impl", "Match", "Approx", "Ambig", "Missing"],
                [[c["category"], c["specifiedRuleCount"], c["extraImplementationCount"],
                  c["statusCounts"]["MATCH"], c["statusCounts"]["APPROXIMATED"],
                  c["statusCounts"]["AMBIGUOUS"], c["statusCounts"]["MISSING_IMPLEMENTATION"]]
                 for c in report["categorySummaries"]]))
    A("")
    A("## Missing strategy knowledge")
    for g in report["missingStrategyKnowledge"]:
        A("")
        A("### %s — %s (%s)" % (g["id"], g["gap"].split(".")[0], g["area"]))
        A("")
        A("- **Evidence:** %s" % g["evidence"])
        A("- **Impact:** %s" % g["impact"])
        A("- **Completion path:** %s" % g["completionPath"])
    A("")
    return "\n".join(L) + "\n"


def main(argv=None):
    argv = argv or sys.argv[1:]
    report = build_report()
    os.makedirs(REPORT_DIR, exist_ok=True)
    os.makedirs(MANIFEST_DIR, exist_ok=True)

    man_path = os.path.join(MANIFEST_DIR, "alex_g_sr_v1.implementation-manifest.json")
    fm.write(man_path, report["manifest"])

    spec_path = os.path.join(MANIFEST_DIR, "alex_g_sr_v1.specification.json")
    fm.write(spec_path, report["specification"])

    json_path = os.path.join(REPORT_DIR, "alex_g_sr_v1.fidelity-report.json")
    fm.write(json_path, report)

    md_path = os.path.join(REPORT_DIR, "ALEX-FIDELITY-REPORT.md")
    import graph_common as gc
    gc.atomic_write_text(md_path, render_markdown(report))

    print("specification : %s (%d rules)" % (os.path.relpath(spec_path, REPO_ROOT),
                                             report["specification"]["ruleCount"]))
    print("manifest      : %s (%d mappings, %d extra rules)"
          % (os.path.relpath(man_path, REPO_ROOT), report["manifest"]["mappingCount"],
             len(report["manifest"]["extraImplementationRules"])))
    print("report (json) : %s" % os.path.relpath(json_path, REPO_ROOT))
    print("report (md)   : %s" % os.path.relpath(md_path, REPO_ROOT))
    print("execution readiness: %s (%d criteria failed)"
          % (report["executionReadiness"]["status"], report["executionReadiness"]["failedCount"]))
    print("profitability      : %s" % report["profitabilityStatus"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

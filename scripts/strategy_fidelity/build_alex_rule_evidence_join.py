#!/usr/bin/env python3
"""
ALEX rule-to-evidence join — MOGO-003 Phase 2, milestone 1.

WHAT THIS JOINS

    educator rule (AXR-*)            docs/strategy-fidelity/audit/alex-canonical-rule-register.json
        |  via the fidelity matrix's own codeLocation + fidelityStatus
        v                            docs/strategy-fidelity/audit/alex-implementation-fidelity-matrix.json
    MOGO implementation (function)
        |  via FUNCTION_EVIDENCE_MAP below -- a DECLARED map, one entry per function,
        |  each naming the exact Evidence Package field that function's output lands in
        v
    replay evidence (RUN-001)        Evidence Packages produced by the MOGO-003 evidence platform

WHAT THIS REFUSES TO DO

  * It never links on name similarity. Every link cites the matrix row that supplied the code
    location and the package field that carried the value. A rule whose implementation cannot be
    anchored to a package field is UNRESOLVED, not guessed.
  * It never merges the three bodies of knowledge. Educator statements, MOGO implementation
    behaviour and replay observations stay in separate fields of every record, exactly as the
    fidelity matrix's own lineage warning requires (agreement is CONVERGENCE, NOT DERIVATION).
  * It never writes, mutates or re-hashes an Evidence Package. Packages are opened read-only.

USAGE
    python3 scripts/strategy_fidelity/build_alex_rule_evidence_join.py \
        --evidence-dir ~/Desktop/MOGO-Evidence/<run-dir> [--out-dir docs/strategy-fidelity/audit]

The absolute evidence path is NEVER written into the output; only the runId and package ids are.
"""
import argparse
import json
import os
import sys
from collections import OrderedDict

JOIN_SCHEMA_VERSION = "mogo.alex-rule-evidence-join.v1"
GENERATOR_VERSION = "1.0.0"

# ── The declared function -> evidence-field map ──────────────────────────────────────────────
# One entry per MOGO function that the fidelity matrix cites as a code location. `fields` names
# the Evidence Package paths that function's output actually lands in, and `introducedBy` records
# which release put them there, so a reviewer can audit the claim rather than take it on trust.
# A function absent from this map produces UNRESOLVED — never a guessed link.
FUNCTION_EVIDENCE_MAP = {
    "alexGEvaluateBreakRetest": {
        "fields": ["objects.qualifiedSetups[].structureRefs.breakCycleId",
                   "objects.qualifiedSetups[].structureRefs.brokenDirection",
                   "objects.qualifiedSetups[].structureRefs.barsSinceBreak",
                   "objects.qualifiedSetups[].triggeredConditions[conditionId^=ALEX_SR_V1_B_]"],
        "conditionPrefix": "ALEX_SR_V1_B_",
        "setupTypeScope": "B_breakRetest",
        "introducedBy": "v12.10.0 (Unit A structureRefs) + v12.11.0 (Unit B attribution)",
    },
    "alexGEvaluateRepeatedReaction": {
        "fields": ["objects.qualifiedSetups[].structureRefs.zoneTouchNumber",
                   "objects.qualifiedSetups[].triggeredConditions[conditionId^=ALEX_SR_V1_A_]"],
        "conditionPrefix": "ALEX_SR_V1_A_",
        "setupTypeScope": "A_repeatedReaction",
        "introducedBy": "v12.11.0 (Unit B attribution)",
    },
    "alexGClassifyTouch": {
        "fields": ["objects.qualifiedSetups[].setupType",
                   "objects.qualifiedSetups[].ruleAttribution.precedenceApplied",
                   "objects.qualifiedSetups[].triggeredConditions[conditionId=ALEX_SR_V1_TOUCH_INDEX_MIN]"],
        "conditionPrefix": "ALEX_SR_V1_TOUCH_INDEX_MIN",
        "introducedBy": "v12.11.0 (Unit B attribution)",
    },
    "alexGCreateSetupRecord": {
        "fields": ["objects.qualifiedSetups[].setupId",
                   "objects.qualifiedSetups[].structureRefs.breakCandleRef",
                   "objects.qualifiedSetups[].structureRefs.retestCandleRef"],
        "introducedBy": "v12.10.0 (Unit A candle refs)",
    },
    "alexGConstructTrade": {
        "fields": ["objects.positions[].entryPrice", "objects.positions[].originalStop",
                   "objects.positions[].target", "objects.positions[].plannedRR",
                   "objects.positions[].positionSize", "objects.positions[].riskAmount"],
        "introducedBy": "v12.8.0 (Evidence Package v1)",
    },
    "alexGDetermineTradeDirection": {
        "fields": ["objects.positions[].direction"],
        "introducedBy": "v12.8.0 (Evidence Package v1)",
    },
    "alexGWalkOutcome": {
        "fields": ["objects.outcomes[].exitReasonCode", "objects.outcomes[].exitPrice",
                   "objects.outcomes[].exitTimestamp"],
        "introducedBy": "v12.8.0 (Evidence Package v1)",
    },
    "alexGComputeMAEMFE": {
        "fields": ["objects.outcomes[].maePips", "objects.outcomes[].mfePips",
                   "objects.outcomes[].timeToMFE", "objects.outcomes[].timeToMAE"],
        "introducedBy": "v12.8.0 (extremes) + v12.12.0 (Unit C1 timing)",
    },
    "alexGComputeTrendContext": {
        "fields": ["objects.qualifiedSetups[].contextRefs.trendContext"],
        "introducedBy": "v12.8.0 (Evidence Package v1)",
    },
    "alexGComputeSessionMetadata": {
        "fields": ["objects.qualifiedSetups[].contextRefs.session",
                   "objects.qualifiedSetups[].contextRefs.dayOfWeek",
                   "objects.qualifiedSetups[].contextRefs.hourOfDay"],
        "introducedBy": "v12.8.0 (Evidence Package v1)",
    },
    "alexGComputePsychLevels": {
        "fields": ["objects.qualifiedSetups[].contextRefs.nearestPsych500Level",
                   "objects.qualifiedSetups[].contextRefs.distanceToPsych500Pips",
                   "objects.qualifiedSetups[].contextRefs.nearestPsych100Level",
                   "objects.qualifiedSetups[].contextRefs.distanceToPsych100Pips"],
        "introducedBy": "v12.8.0 (Evidence Package v1)",
    },
    "alexGComputeATRAtEntry": {
        "fields": ["objects.qualifiedSetups[].contextRefs.atrAtEntry"],
        "introducedBy": "v12.8.0 (Evidence Package v1)",
    },
    "alexGZoneRole": {
        "fields": ["objects.qualifiedSetups[].structureRefs.zoneRoleAtQualification"],
        "introducedBy": "v12.8.0 (Evidence Package v1)",
    },
    "alexGCorrectedQuality": {
        "fields": ["objects.qualifiedSetups[].structureRefs.zoneQualityAtQualification"],
        "introducedBy": "v12.8.0 (Evidence Package v1)",
    },
    "alexGProcessTimeframeCandle": {
        "fields": ["objects.qualifiedSetups[].structureRefs.zoneId",
                   "objects.qualifiedSetups[].structureRefs.zoneLow",
                   "objects.qualifiedSetups[].structureRefs.zoneHigh",
                   "objects.qualifiedSetups[].structureRefs.zoneStrength"],
        "introducedBy": "v12.8.0 (Evidence Package v1)",
    },
}
# Config parameters are evidence too: snapshotAlexGConfig() copies RULES_ALEXG.config verbatim onto
# every package. A rule whose implementation IS a parameter is linked to the parameter's own field.
CONFIG_EVIDENCE_MAP = {
    "minRR": {"fields": ["configSnapshot.config.minRR", "objects.positions[].plannedRR"],
              "introducedBy": "v12.8.0 (configSnapshot) "},
    "riskPercent": {"fields": ["configSnapshot.config.riskPercent", "objects.positions[].riskPercent"],
                    "introducedBy": "v12.8.0 (configSnapshot)"},
    "*": {"fields": ["configSnapshot.config"], "introducedBy": "v12.8.0 (configSnapshot)"},
}
# Functions on the LIVE paper-execution path. RUN-001 is a REPLAY: these were never executed, so the
# honest status is NOT_EXERCISED -- the implementation exists, this run simply did not reach it.
LIVE_ONLY_FUNCTIONS = {
    "alexGConstructLivePosition",
    "alexGUpdatePositionExcursionAndCheckExit",
    "alexGCloseLivePosition",
    "alexGAttemptOpenLivePosition",
    "alexGEvaluatePairForLiveSetups",
}

# Aliases for code locations the matrix names slightly differently from the shipped symbol.
FUNCTION_ALIASES = {
    "alexGRunZoneEngine": "alexGProcessTimeframeCandle",
    "alexGProcessTimeframeCandleWithSetups": "alexGClassifyTouch",
    "alexGRunSetupEngine": "alexGClassifyTouch",
}

# Fidelity statuses that mean MOGO does not implement the educator rule at all.
NOT_IMPLEMENTED_STATUSES = {"MISSING_FROM_MOGO", "NON_IMPLEMENTABLE_DISCRETION", "NOT_APPLICABLE"}
# Fidelity statuses that mean MOGO implements something the educator library does not support.
UNSUPPORTED_STATUSES = {"IMPLEMENTED_WITHOUT_EDUCATOR_SUPPORT", "MOGO_AUTHORED_PARAMETER"}
# Fidelity statuses that mean an implementation genuinely exists to look for in evidence.
IMPLEMENTED_STATUSES = {"EXACT_MATCH", "FUNCTIONAL_MATCH", "PARTIAL_MATCH", "PRESENT_BUT_DIFFERENT",
                        "MOGO_ENHANCEMENT"}



# ══ METRIC REGISTRY ═══════════════════════════════════════════════════════════════════════════
# A metric is defined ONCE here and referenced by id. A hypothesis that names a metric inherits
# this definition rather than restating it, so two hypotheses can never disagree about what
# "win rate" means. Every definition names the Evidence Package field it is computed from.
METRIC_REGISTRY = {
    "MET_WIN_RATE": {
        "name": "Win rate", "unit": "percent",
        "formula": "wins / (wins + losses) * 100",
        "sourceFields": ["objects.outcomes[].exitReasonCode"],
        "betterWhen": "higher",
    },
    "MET_NET_R": {
        "name": "Net R", "unit": "R",
        "formula": "sum(recordedResultR) over resolved trades",
        "sourceFields": ["objects.outcomes[].recordedResultR"],
        "betterWhen": "higher",
    },
    "MET_EXPECTANCY_R": {
        "name": "Expectancy per trade", "unit": "R",
        "formula": "netR / resolved trade count",
        "sourceFields": ["objects.outcomes[].recordedResultR"],
        "betterWhen": "higher",
    },
    "MET_PROFIT_FACTOR": {
        "name": "Profit factor", "unit": "ratio",
        "formula": "gross positive R / abs(gross negative R)",
        "sourceFields": ["objects.outcomes[].recordedResultR"],
        "betterWhen": "higher",
    },
    "MET_MAE_PIPS": {
        "name": "Maximum adverse excursion", "unit": "pips",
        "formula": "mean(maePips) over resolved trades",
        "sourceFields": ["objects.outcomes[].maePips"],
        "betterWhen": "lower",
    },
    "MET_MFE_PIPS": {
        "name": "Maximum favourable excursion", "unit": "pips",
        "formula": "mean(mfePips) over resolved trades",
        "sourceFields": ["objects.outcomes[].mfePips"],
        "betterWhen": "higher",
    },
}

# The minimum sample per comparison arm. This is a DECLARED threshold, not a derived one: it is
# stated up front so it cannot be rationalised downward after seeing a result. Recording the basis
# matters more than the number -- a reader can disagree with 30 only because 30 is stated.
MINIMUM_SAMPLE_PER_ARM = 30
MINIMUM_SAMPLE_BASIS = ("Declared in advance, not derived from these results. Below roughly 30 "
                        "resolved trades per arm, a 2R/-1R system's win-rate estimate is dominated "
                        "by variance and no difference between arms is distinguishable from noise.")

# The ceiling replay evidence alone can reach. Replay cannot promote a rule past this: it observes
# one engine over one dataset, and agreement with the engine is not independent confirmation.
PROMOTION_CEILING_REPLAY_ONLY = "REPLAY_EVIDENCE_ONLY"

HYPOTHESIS_STATUSES = [
    "UNTESTED",                 # implemented, but no evidence observes it yet
    "INSUFFICIENT_SAMPLE",      # evidence exists, below the declared minimum
    "TESTABLE_NOW",             # both arms meet the declared minimum
    "NOT_TESTABLE_BY_REPLAY",   # the implementation is on the live path only
    "NOT_APPLICABLE",           # the rule is not implemented, or is MOGO-authored without educator support
]


def _resolved_outcomes(pkgs):
    """Per-setupType outcome measurements, straight from the packages. No placeholder text."""
    out = {}
    for p in pkgs:
        qs = (p.get("objects", {}).get("qualifiedSetups") or [{}])[0]
        oc = (p.get("objects", {}).get("outcomes") or [{}])[0]
        st = qs.get("setupType") or "UNKNOWN"
        b = out.setdefault(st, {"trades": 0, "wins": 0, "losses": 0, "netR": 0.0,
                                "maePips": [], "mfePips": [], "packageIds": []})
        b["trades"] += 1
        b["packageIds"].append(p.get("packageId"))
        res = str(oc.get("exitReasonCode") or "").lower()
        if res == "win":
            b["wins"] += 1
        elif res == "loss":
            b["losses"] += 1
        r = oc.get("recordedResultR")
        if isinstance(r, (int, float)):
            b["netR"] += r
        for k in ("maePips", "mfePips"):
            v = oc.get(k)
            if isinstance(v, (int, float)):
                b[k].append(v)
    for st, b in out.items():
        decided = b["wins"] + b["losses"]
        b["decided"] = decided
        b["winRate"] = round(100.0 * b["wins"] / decided, 2) if decided else None
        b["netR"] = round(b["netR"], 4)
        b["expectancyR"] = round(b["netR"] / decided, 4) if decided else None
        pos = sum(x for x in [b["netR"]] if x > 0)
        b["meanMaePips"] = round(sum(b["maePips"]) / len(b["maePips"]), 2) if b["maePips"] else None
        b["meanMfePips"] = round(sum(b["mfePips"]) / len(b["mfePips"]), 2) if b["mfePips"] else None
        del b["maePips"], b["mfePips"]
    return out


def build_hypotheses(records, outcomes_by_setup, run_ids):
    """One testable hypothesis per rule that MOGO actually implements.

    Each carries a metric, a comparison, a declared threshold, a minimum sample and a
    falsification condition -- replacing the corpus's placeholder 'compare outcomes' text.
    Status is computed from evidence that exists TODAY, so a rule with no observations says
    UNTESTED rather than implying it has been checked."""
    hyps = []
    for rec in records:
        rid = rec["ruleId"]
        status_join = rec["status"]
        ev = rec.get("evidence") or {}
        scope = None
        impl = rec.get("implementation") or {}
        fn = (impl.get("resolvedFunction") or "")
        if "BreakRetest" in fn:
            scope = "B_breakRetest"
        elif "RepeatedReaction" in fn:
            scope = "A_repeatedReaction"
        observed = outcomes_by_setup.get(scope) if scope else None
        if not observed:
            # a rule that is not setup-scoped is measured against the whole run
            merged = {"trades": 0, "wins": 0, "losses": 0, "decided": 0, "netR": 0.0, "packageIds": []}
            for st, b in outcomes_by_setup.items():
                merged["trades"] += b["trades"]; merged["wins"] += b["wins"]
                merged["losses"] += b["losses"]; merged["decided"] += b["decided"]
                merged["netR"] += b["netR"]; merged["packageIds"] += b["packageIds"]
            merged["netR"] = round(merged["netR"], 4)
            merged["winRate"] = (round(100.0 * merged["wins"] / merged["decided"], 2)
                                 if merged["decided"] else None)
            merged["expectancyR"] = (round(merged["netR"] / merged["decided"], 4)
                                     if merged["decided"] else None)
            observed = merged
        if status_join in ("NOT_IMPLEMENTED", "UNSUPPORTED"):
            status = "NOT_APPLICABLE"
        elif status_join == "NOT_EXERCISED" and (ev.get("reason") or "").startswith("cited implementation is on the LIVE"):
            status = "NOT_TESTABLE_BY_REPLAY"
        elif status_join == "UNRESOLVED":
            status = "UNTESTED"
        elif observed["decided"] == 0:
            status = "UNTESTED"
        elif observed["decided"] < MINIMUM_SAMPLE_PER_ARM:
            status = "INSUFFICIENT_SAMPLE"
        else:
            status = "TESTABLE_NOW"
        hyps.append(OrderedDict([
            ("hypothesisId", "HYP|" + rid),
            ("ruleId", rid),
            ("statement", "Trades qualifying under " + rid + " differ measurably in outcome from "
                          "those qualifying without it."),
            ("metricId", "MET_EXPECTANCY_R"),
            ("secondaryMetricIds", ["MET_WIN_RATE", "MET_NET_R", "MET_MAE_PIPS", "MET_MFE_PIPS"]),
            ("comparison", {
                "armA": "resolved trades where the rule's condition held",
                "armB": "resolved trades where it did not",
                "basis": "same strategy, same engine version, same dataset hash",
            }),
            ("threshold", {"metric": "MET_EXPECTANCY_R", "minimumDifference": 0.25,
                           "unit": "R", "declaredInAdvance": True}),
            ("minimumSamplePerArm", MINIMUM_SAMPLE_PER_ARM),
            ("minimumSampleBasis", MINIMUM_SAMPLE_BASIS),
            ("falsificationCondition",
             "The hypothesis is REFUTED if, with both arms at or above the minimum sample, the "
             "expectancy difference is smaller than the declared threshold or favours arm B."),
            ("currentEvidence", {
                "runIds": run_ids,
                "setupTypeScope": scope,
                "resolvedTrades": observed["decided"],
                "wins": observed["wins"], "losses": observed["losses"],
                "winRate": observed.get("winRate"), "netR": observed.get("netR"),
                "expectancyR": observed.get("expectancyR"),
                "meanMaePips": observed.get("meanMaePips"),
                "meanMfePips": observed.get("meanMfePips"),
                "packageIds": observed.get("packageIds", [])[:10],
            }),
            ("status", status),
            ("promotionCeiling", PROMOTION_CEILING_REPLAY_ONLY),
            ("shortfall", (MINIMUM_SAMPLE_PER_ARM - observed["decided"])
             if status in ("INSUFFICIENT_SAMPLE", "UNTESTED") else 0),
        ]))
    return hyps


def parse_code_location(loc):
    """'alexGZoneRole (index.html:2735)' -> ('alexGZoneRole', 'index.html:2735')."""
    if not loc or not isinstance(loc, str):
        return None, None
    name = loc.split("(")[0].strip()
    ref = loc.split("(")[1].rstrip(")").strip() if "(" in loc else None
    return (name or None), ref


def load_packages(evidence_dir):
    pkgs = []
    for fn in sorted(os.listdir(evidence_dir)):
        if not (fn.startswith("mogo-evidence-") and fn.endswith(".json")):
            continue
        with open(os.path.join(evidence_dir, fn), "r", encoding="utf-8") as fh:
            pkgs.append(json.load(fh))
    return pkgs


def field_present(pkg, path):
    """Is a declared field path actually populated in this package? Conservative: a null,
    an empty list or a missing key all count as ABSENT, so 'exercised' means observed."""
    if path.startswith("objects.qualifiedSetups[]"):
        items, rest = pkg.get("objects", {}).get("qualifiedSetups", []), path[len("objects.qualifiedSetups[]."):]
    elif path.startswith("objects.positions[]"):
        items, rest = pkg.get("objects", {}).get("positions", []), path[len("objects.positions[]."):]
    elif path.startswith("objects.outcomes[]"):
        items, rest = pkg.get("objects", {}).get("outcomes", []), path[len("objects.outcomes[]."):]
    elif path.startswith("configSnapshot"):
        cur = pkg
        for part in path.split("."):
            if not isinstance(cur, dict) or part not in cur:
                return False
            cur = cur[part]
        return cur not in (None, [], {}, "")
    else:
        return False
    if rest.startswith("triggeredConditions["):
        return None  # handled separately by condition matching
    for it in items:
        cur = it
        ok = True
        for part in rest.split("."):
            if not isinstance(cur, dict) or part not in cur:
                ok = False
                break
            cur = cur[part]
        if ok and cur not in (None, [], {}, ""):
            return True
    return False


def conditions_in(pkg, prefix):
    out = []
    for qs in pkg.get("objects", {}).get("qualifiedSetups", []):
        for c in qs.get("triggeredConditions", []) or []:
            cid = c.get("conditionId")
            if cid and cid.startswith(prefix):
                out.append(cid)
    return out


def refs_for(pkg):
    qs = (pkg.get("objects", {}).get("qualifiedSetups") or [{}])[0]
    po = (pkg.get("objects", {}).get("positions") or [{}])[0]
    oc = (pkg.get("objects", {}).get("outcomes") or [{}])[0]
    return {
        "packageId": pkg.get("packageId"),
        "setupId": qs.get("setupId"),
        "setupType": qs.get("setupType"),
        "positionId": po.get("positionId"),
        "outcomeId": oc.get("outcomeId"),
        "sourceTradeId": pkg.get("sourceTradeId"),
    }


def build(register, matrix, pkgs, run_dir_name):
    by_educator = {r.get("educatorRuleId"): r for r in matrix.get("rows", [])}
    run_ids = sorted({(p.get("identity") or {}).get("runId") for p in pkgs if (p.get("identity") or {}).get("runId")})
    records = []
    for rule in register.get("rules", []):
        rid = rule.get("ruleId")
        row = by_educator.get(rid)
        basis = []
        rec = OrderedDict()
        rec["ruleId"] = rid
        rec["domain"] = rule.get("domain")
        rec["educator"] = {
            "statement": rule.get("normalizedStatement"),
            "evidenceClass": rule.get("evidenceClass"),
            "authorship": rule.get("authorship"),
            "deterministic": rule.get("deterministic"),
            "confidenceStatus": rule.get("confidenceStatus"),
            "distinctSourceCount": rule.get("distinctSourceCount"),
            "supportingClaimIds": rule.get("supportingClaimIds", []),
        }
        if row is None:
            rec["implementation"] = None
            rec["evidence"] = {"status": "UNRESOLVED", "packageIds": [], "conditionIds": []}
            rec["status"] = "UNRESOLVED"
            rec["unresolvedReason"] = "NO_FIDELITY_ROW"
            rec["linkBasis"] = ["no fidelity-matrix row exists for this educator rule"]
            records.append(rec)
            continue

        fn_name, code_ref = parse_code_location(row.get("codeLocation"))
        resolved_fn = FUNCTION_ALIASES.get(fn_name, fn_name)
        mapping = FUNCTION_EVIDENCE_MAP.get(resolved_fn)
        basis.append("fidelity matrix row educatorRuleId=%s fidelityStatus=%s" % (rid, row.get("fidelityStatus")))
        rec["implementation"] = {
            "fidelityStatus": row.get("fidelityStatus"),
            "mogoRuleId": row.get("mogoRuleId"),
            "codeLocation": row.get("codeLocation"),
            "resolvedFunction": resolved_fn,
            "implementationBehaviour": row.get("implementationBehaviour"),
            "lineageNote": row.get("lineageNote"),
        }

        status_f = row.get("fidelityStatus")
        if status_f in UNSUPPORTED_STATUSES:
            rec["evidence"] = {"status": "NOT_ASSESSED", "packageIds": [], "conditionIds": []}
            rec["status"] = "UNSUPPORTED"
            basis.append("fidelityStatus is in the MOGO-authored/unsupported set")
            rec["linkBasis"] = basis
            records.append(rec)
            continue
        if status_f in NOT_IMPLEMENTED_STATUSES:
            rec["evidence"] = {"status": "NOT_ASSESSED", "packageIds": [], "conditionIds": []}
            rec["status"] = "NOT_IMPLEMENTED"
            basis.append("fidelityStatus states MOGO does not implement this rule")
            rec["linkBasis"] = basis
            records.append(rec)
            continue
        if status_f not in IMPLEMENTED_STATUSES:
            rec["evidence"] = {"status": "NOT_ASSESSED", "packageIds": [], "conditionIds": []}
            rec["status"] = "UNRESOLVED"
            rec["unresolvedReason"] = "FIDELITY_STATUS_UNRESOLVED"
            basis.append("fidelityStatus '%s' does not assert an implementation" % status_f)
            rec["linkBasis"] = basis
            records.append(rec)
            continue

        # An implementation that only the LIVE path runs cannot be exercised by a replay.
        if resolved_fn in LIVE_ONLY_FUNCTIONS:
            rec["evidence"] = {"status": "NOT_EXERCISED", "runIds": run_ids, "packageIds": [],
                               "conditionIds": [],
                               "reason": "cited implementation is on the LIVE paper-execution path; "
                                         "RUN-001 is a replay and never executed it"}
            rec["status"] = "NOT_EXERCISED"
            basis.append("codeLocation -> %s, which is live-execution-only" % resolved_fn)
            rec["linkBasis"] = basis
            records.append(rec)
            continue

        # A rule whose implementation is a configuration parameter links to that parameter's field.
        if mapping is None and fn_name and fn_name.startswith("RULES_ALEXG.config"):
            param = fn_name.split(".")[-1] if fn_name.count(".") >= 2 else "*"
            cfg = CONFIG_EVIDENCE_MAP.get(param, CONFIG_EVIDENCE_MAP["*"])
            mapping = {"fields": cfg["fields"], "introducedBy": cfg["introducedBy"]}
            basis.append("implementation is configuration parameter '%s'; snapshotAlexGConfig() "
                         "copies RULES_ALEXG.config verbatim onto every package" % param)
            resolved_fn = fn_name

        # An implementation exists. Can it be anchored to an evidence field?
        if mapping is None:
            rec["evidence"] = {"status": "NOT_ASSESSED", "packageIds": [], "conditionIds": []}
            rec["status"] = "UNRESOLVED"
            rec["unresolvedReason"] = ("NO_EVIDENCE_FIELD_EXISTS" if fn_name
                                       else "NO_CODE_LOCATION_SYMBOL")
            basis.append("code location '%s' has no declared evidence-field mapping -- "
                         "not guessed" % (row.get("codeLocation") or "none"))
            rec["linkBasis"] = basis
            records.append(rec)
            continue

        basis.append("codeLocation -> %s (%s)" % (resolved_fn, code_ref))
        basis.append("FUNCTION_EVIDENCE_MAP declares fields: %s" % "; ".join(mapping["fields"]))
        hit_pkgs, cond_ids = [], set()
        scope = mapping.get("setupTypeScope")
        for p in pkgs:
            # An evaluator can only have produced the setups of its own type. Without this the
            # RZR evaluator would "link" to Break & Retest packages merely because a shared field
            # (zoneTouchNumber, written by the setup-record creator) is populated on both.
            if scope:
                types = {qs.get("setupType") for qs in p.get("objects", {}).get("qualifiedSetups", [])}
                if scope not in types:
                    continue
            hit = False
            for path in mapping["fields"]:
                if "triggeredConditions[" in path:
                    continue
                if field_present(p, path):
                    hit = True
                    break
            if mapping.get("conditionPrefix"):
                cs = conditions_in(p, mapping["conditionPrefix"])
                if cs:
                    hit = True
                    cond_ids.update(cs)
            if hit:
                hit_pkgs.append(p)

        if hit_pkgs:
            rec["evidence"] = {
                "status": "LINKED",
                "runIds": run_ids,
                "runDirectory": run_dir_name,
                "packageCount": len(hit_pkgs),
                "packageIds": [p.get("packageId") for p in hit_pkgs],
                "conditionIds": sorted(cond_ids),
                "references": [refs_for(p) for p in hit_pkgs[:3]],
                "fieldsObserved": [f for f in mapping["fields"] if "triggeredConditions[" not in f],
                "introducedBy": mapping["introducedBy"],
            }
            rec["status"] = "LINKED"
            basis.append("observed populated in %d/%d RUN-001 packages" % (len(hit_pkgs), len(pkgs)))
        else:
            rec["evidence"] = {"status": "NOT_EXERCISED", "runIds": run_ids, "packageIds": [],
                               "conditionIds": [], "fieldsChecked": mapping["fields"],
                               "introducedBy": mapping["introducedBy"]}
            rec["status"] = "NOT_EXERCISED"
            basis.append("declared fields present in 0/%d packages" % len(pkgs))
        rec["linkBasis"] = basis
        records.append(rec)
    return records, run_ids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence-dir", required=True)
    ap.add_argument("--out-dir", default="docs/strategy-fidelity/audit")
    ap.add_argument("--register", default="docs/strategy-fidelity/audit/alex-canonical-rule-register.json")
    ap.add_argument("--matrix", default="docs/strategy-fidelity/audit/alex-implementation-fidelity-matrix.json")
    ap.add_argument("--generated-at", default=None, help="ISO timestamp; omitted keeps output deterministic")
    a = ap.parse_args()

    ev = os.path.expanduser(a.evidence_dir)
    if not os.path.isdir(ev):
        print("evidence dir not found: %s" % ev, file=sys.stderr)
        return 2
    register = json.load(open(a.register, encoding="utf-8"))
    matrix = json.load(open(a.matrix, encoding="utf-8"))
    pkgs = load_packages(ev)
    if not pkgs:
        print("no evidence packages found in %s" % ev, file=sys.stderr)
        return 2

    records, run_ids = build(register, matrix, pkgs, os.path.basename(ev.rstrip("/")))
    outcomes = _resolved_outcomes(pkgs)
    # Every rule now references MEASURED outcomes, never placeholder prose.
    for rec in records:
        impl = rec.get("implementation") or {}
        fn = impl.get("resolvedFunction") or ""
        scope = ("B_breakRetest" if "BreakRetest" in fn
                 else ("A_repeatedReaction" if "RepeatedReaction" in fn else None))
        rec["measurableEvidence"] = (outcomes.get(scope) if scope else None) or {
            "scope": "RUN_WIDE",
            "trades": sum(b["trades"] for b in outcomes.values()),
            "decided": sum(b["decided"] for b in outcomes.values()),
        }
    hypotheses = build_hypotheses(records, outcomes, run_ids)
    counts = OrderedDict()
    for st in ["LINKED", "NOT_EXERCISED", "NOT_IMPLEMENTED", "UNSUPPORTED", "UNRESOLVED"]:
        counts[st] = sum(1 for r in records if r["status"] == st)

    out = OrderedDict()
    out["joinSchemaVersion"] = JOIN_SCHEMA_VERSION
    out["generatorVersion"] = GENERATOR_VERSION
    if a.generated_at:
        out["generatedAt"] = a.generated_at
    out["milestone"] = "MOGO-003 Phase 2 -- ALEX rule-to-evidence join"
    out["scope"] = ("ALEX only. Educator rules, MOGO implementation behaviour and replay observations "
                    "are kept in separate fields and are never merged.")
    out["lineageWarning"] = matrix.get("⚠️lineageWarning")
    out["evidenceRunIds"] = run_ids
    out["evidencePackageCount"] = len(pkgs)
    any_conditions = any(conditions_in(p, "ALEX_SR_V1_") for p in pkgs)
    out["attributionAvailability"] = {
        "triggeredConditionsPresentInRun": any_conditions,
        "note": ("Unit B (v12.11.0) added ruleIds/triggeredConditions to newly captured packages. "
                 "RUN-001 was captured on engine 12.9.0 and carries none, so condition-level joins "
                 "are unavailable for this run and every conditionIds list below is empty. "
                 "Field-level joins are unaffected."),
    }
    out["ruleCount"] = len(records)
    out["statusCounts"] = counts
    out["statusVocabulary"] = {
        "LINKED": "MOGO implements this rule and at least one RUN-001 package carries the declared evidence field.",
        "NOT_EXERCISED": "MOGO implements this rule but no RUN-001 package carries the declared field populated.",
        "NOT_IMPLEMENTED": "The fidelity matrix records that MOGO does not implement this educator rule.",
        "UNSUPPORTED": "MOGO implements behaviour the educator library does not support (MOGO-authored).",
        "UNRESOLVED": "No fidelity row, no declared evidence mapping, or a fidelity status that asserts no implementation.",
    }
    out["metricRegistry"] = METRIC_REGISTRY
    out["hypothesisStatuses"] = HYPOTHESIS_STATUSES
    out["minimumSamplePerArm"] = MINIMUM_SAMPLE_PER_ARM
    out["minimumSampleBasis"] = MINIMUM_SAMPLE_BASIS
    out["promotionCeiling"] = PROMOTION_CEILING_REPLAY_ONLY
    out["outcomesBySetupType"] = outcomes
    out["hypothesisStatusCounts"] = {
        st: sum(1 for h in hypotheses if h["status"] == st) for st in HYPOTHESIS_STATUSES}
    out["rules"] = records
    out["hypotheses"] = hypotheses
    os.makedirs(a.out_dir, exist_ok=True)
    path = os.path.join(a.out_dir, "alex-rule-evidence-join.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, sort_keys=False)
        fh.write("\n")
    print(json.dumps({"written": path, "statusCounts": counts,
                      "hypothesisStatusCounts": out["hypothesisStatusCounts"],
                      "packages": len(pkgs), "runIds": run_ids}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

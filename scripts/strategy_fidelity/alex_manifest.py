"""MOGO-002.5 — ALEX StrategyImplementationManifest.

Every mapping below was produced by ACTUALLY READING the cited code path in
index.html during this milestone. `inspected=True` is a factual claim about that
reading, and fidelity_model.py refuses IMPLEMENTED/APPROXIMATED without it.

Line numbers are stated as `index.html:<line>` and are verified at build time by
`verify_references()`, which re-reads the file and confirms the named symbol is
actually at (or adjacent to) the cited line. A manifest whose references have
rotted is worse than no manifest, because it looks authoritative.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fidelity_model as fm            # noqa: E402
import alex_specification as aspec     # noqa: E402

REPO_ROOT = aspec.REPO_ROOT
INDEX_HTML = aspec.INDEX_HTML
MANIFEST_VERSION = "alex_g_sr_v1.impl.1"

# Protected per regression-baseline.json. Recorded so the report can explain WHY
# certain limitations are structural rather than unfixed work.
PROTECTED_NOTE = ("PROTECTED function (regression-baseline.json). It cannot be edited "
                  "or instrumented without baseline drift, so its internal rule detail "
                  "is not externally observable.")

_M = fm.implementation_rule_mapping


def _ref(symbol, detail=None):
    """A code reference by SYMBOL, not by line number.

    Line numbers rot the moment anything above them changes -- MOGO-002.5's own
    Phase 5 edit invalidated 26 of them in one commit, which `verify_references()`
    caught. The symbol is the stable identity; the line is RESOLVED at build time
    by `resolve_references()` so the emitted manifest always carries a correct,
    checkable locator without anyone maintaining it by hand."""
    return {"symbol": symbol, "detail": detail, "locator": None}


def build_mappings():
    return [
        _M("ALEX_SR_001", "IMPLEMENTED", inspected=True,
           implementation_references=[_ref("alexGZoneRole")],
           evaluators=["alexGZoneRole"],
           tests=["tests/v_paper_trading_audit_tests.js", "tests/v126_phase2c_wave1_tests.js"],
           implementation_notes=(
               "Role is derived positionally: price above the zone -> 'support', below -> "
               "'resistance', within -> 'inside'. That is a faithful mechanisation of the "
               "definitional concept."),
           known_limitations=["Definitional rule; there is no behavioural assertion to test directly."]),

        _M("ALEX_SR_002", "IMPLEMENTED", inspected=True,
           implementation_references=[_ref("alexGCreateSetupRecord"), _ref("alexGZoneRole")],
           evaluators=["alexGCreateSetupRecord", "alexGZoneRole"],
           tests=["tests/v126_phase2c_wave1_tests.js"],
           implementation_notes=(
               "The single `zone` object carries both roles over time via lastKnownRole; there is "
               "no separate support-object and resistance-object, which is what the concept requires."),
           known_limitations=[]),

        _M("ALEX_SR_003", "IMPLEMENTED", inspected=True,
           implementation_references=[_ref("alexGDetermineTradeDirection")],
           evaluators=["alexGDetermineTradeDirection"],
           tests=["tests/v126_phase2c_wave1_tests.js"],
           implementation_notes=(
               "support -> buy, resistance -> sell, and an 'inside' role returns "
               "{direction:null, rejectionReason:'INVALID_ZONE_ROLE_INSIDE'}, which the caller "
               "surfaces as reason code ENTRY_INVALID_ZONE_ROLE. The prohibition is enforced by "
               "construction: there is no code path that produces a trade against the role."),
           known_limitations=[PROTECTED_NOTE]),

        _M("ALEX_SR_004", "IMPLEMENTED", inspected=True,
           implementation_references=[_ref("alexGDetermineFromSide"), _ref("alexGAcceptReaction")],
           evaluators=["alexGDetermineFromSide", "alexGAcceptReaction"],
           tests=["tests/v126_phase2c_wave1_tests.js"],
           implementation_notes=(
               "fromSide is resolved to 'above' or 'below' from the pre-anchor close, and both "
               "feed one shared zone.touches array -- a single bidirectional tally, as specified."),
           known_limitations=[PROTECTED_NOTE]),

        _M("ALEX_SR_005", "IMPLEMENTED", inspected=True,
           implementation_references=[_ref("alexGEvaluateRepeatedReaction")],
           evaluators=["alexGEvaluateRepeatedReaction"],
           tests=["tests/v126_phase2c_wave1_tests.js"],
           implementation_notes=(
               "Two independent guards enforce it exactly: `touchIndex<3 -> {qualifies:false}` "
               "(0-based, so the 4th reaction is the first eligible) and "
               "`zone.touches.length<4 -> {qualifies:false}`. Also requires status 'validated' and "
               "a non-choppy corrected quality."),
           known_limitations=[
               PROTECTED_NOTE,
               "The {qualifies:false} return contract discards WHICH of the four conditions "
               "failed, so a rejection cannot be attributed to a specific rule in a trace."]),

        _M("ALEX_SR_006", "IMPLEMENTED", inspected=True,
           implementation_references=[_ref("alexGAcceptReaction", "zoneStrength assignment")],
           evaluators=["alexGAcceptReaction"],
           tests=["tests/v_paper_trading_audit_tests.js"],
           implementation_notes=(
               "Exact ternary: `touches.length<3 ? 'weak' : ===3 ? 'valid' : 'strong'`. The three "
               "named tiers and their boundaries match the concept literally."),
           known_limitations=[PROTECTED_NOTE]),

        _M("ALEX_SR_007", "APPROXIMATED", inspected=True,
           implementation_references=[_ref("alexGAcceptReaction", "zoneStrength assignment")],
           evaluators=["alexGAcceptReaction"],
           tests=[],
           approximation_detail=(
               "The concept says more touches are ALWAYS better with NO CEILING. The strength tier "
               "saturates at 'strong' for 4 or more touches, so a 12-touch zone and a 4-touch zone "
               "are indistinguishable to every consumer of zoneStrength. The raw count survives in "
               "zone.touches.length and zoneTouchNumber, so the information is retained -- but no "
               "decision uses it beyond the tier."),
           implementation_notes="Faithful up to 4 touches; flat thereafter.",
           known_limitations=["No consumer ranks two 'strong' zones against each other."]),

        _M("ALEX_SR_008", "APPROXIMATED", inspected=True,
           implementation_references=[_ref("alexGAssignCluster"), _ref("RULES_ALEXG.config.zoneClusterATRMultiplier")],
           evaluators=["alexGAssignCluster"],
           tests=[],
           approximation_detail=(
               "The source gives NO formula -- RULES_ALEXG itself records 'demonstrated visually, "
               "no formula given'. The implementation substitutes an ATR-proportional grouping "
               "tolerance (zoneClusterATRMultiplier = 0.5), which RULES_ALEXG.experimentalParams "
               "flags as EXPERIMENTAL and 'not tuned against outcomes'. This is a chosen "
               "standardization, not a reconstruction of a stated rule."),
           implementation_notes=(
               "Nearest-cluster assignment with a deterministic tie-break cascade "
               "(nearest centre -> earlier creation -> lower id)."),
           known_limitations=[
               "The specification is UNRESOLVED here, so no comparison can establish whether 0.5 "
               "ATR is faithful. Sensitivity range [0.25, 0.5, 0.75, 1.0] is declared but untested."]),

        _M("ALEX_SR_009", "IMPLEMENTED", inspected=True,
           implementation_references=[_ref("alexGEnsureZoneState"), _ref("alexGRunZoneEngine"),
                                      _ref("alexGRunSetupEngine"),
                                      _ref("RULES_ALEXG.config.zoneTimeframes")],
           evaluators=["alexGEnsureZoneState", "alexGRunZoneEngine", "alexGRunSetupEngine"],
           tests=["tests/v126_phase2c_wave1_tests.js"],
           implementation_notes=(
               "The traded behaviour is correct -- exactly H1, H4, D and W are processed. "
               "DISCREPANCY: the three real loops use the HARDCODED array literal "
               "['H1','H4','D','W'] and never read RULES_ALEXG.config.zoneTimeframes, which is "
               "therefore a dead configuration key. Behaviourally faithful today; a future edit to "
               "the config would silently have no effect."),
           known_limitations=[
               "config.zoneTimeframes is declared but unread -- see FIDELITY-DISC-001."]),

        _M("ALEX_SR_010", "IMPLEMENTED", inspected=True,
           implementation_references=[_ref("alexGSetupSortComparator", "htfPriority"), _ref("RULES_ALEXG.config.htfPriority")],
           evaluators=["alexGSetupSortComparator"],
           tests=["tests/v_paper_trading_audit_tests.js"],
           implementation_notes=(
               "htfPriority {W:4, D:3, H4:2, H1:1} is read from config and used to order competing "
               "setups so a higher-timeframe zone is preferred."),
           known_limitations=[
               "Priority affects ORDERING only. The concept says higher-timeframe zones are 'more "
               "respected'; the implementation never uses that to gate, weight or size a trade, so "
               "the two are only partially comparable."]),

        _M("ALEX_SR_011", "IMPLEMENTED", inspected=True,
           implementation_references=[_ref("alexGEvaluateBreakRetest")],
           evaluators=["alexGEvaluateBreakRetest", "alexGBreakCycleId"],
           tests=["tests/v126_phase2c_wave1_tests.js"],
           implementation_notes=(
               "The full ordered sequence is enforced: zone.status must be 'broken', the retest bar "
               "must be strictly after brokenAtBar, the swing type and fromSide must match the "
               "post-break side, and only the first qualifying retest per breakCycleId is taken. "
               "The role flip is carried by brokenDirection -> direction in "
               "alexGDetermineTradeDirection."),
           known_limitations=[
               PROTECTED_NOTE,
               "maxBarsBetweenBreakAndRetest = 50 is a Hub standardization; the source states no "
               "time limit on the retest."]),

        _M("ALEX_SR_012", "APPROXIMATED", inspected=True,
           implementation_references=[_ref("alexGComputePsychLevels")],
           evaluators=["alexGComputePsychLevels"],
           tests=[],
           approximation_detail=(
               "The concept calls round numbers 'additional, non-mandatory confluence'. The "
               "implementation computes and records RAW DISTANCES ONLY and deliberately does not "
               "treat them as confluence -- the proximity boolean was removed in v3.6.1 as an "
               "unsupported standardization. So the rule is recorded but never acts as confluence "
               "anywhere in the decision path."),
           implementation_notes="Record-only metadata; pair-aware via the frozen pipSize().",
           known_limitations=["No consumer reads psych-level distance to influence a decision."]),

        _M("ALEX_SR_013", "IMPLEMENTED", inspected=True,
           implementation_references=[_ref("alexGComputeTrendContext"), _ref("buildAlexJournalOpenRecord", "trendContext recorded")],
           evaluators=["alexGComputeTrendContext"],
           tests=["tests/v_paper_trading_audit_tests.js"],
           implementation_notes=(
               "Structural trend (UPTREND / DOWNTREND / RANGE_MIXED / INSUFFICIENT_DATA) is computed "
               "from confirmed swing structure and recorded on the setup and journal record. It "
               "never gates, scores, sizes or alters a trade -- which is FAITHFUL, because the "
               "source never stated it as a requirement."),
           known_limitations=[
               "Because the rule is DISCRETIONARY, no fidelity verdict is possible either way; see "
               "the NOT_APPLICABLE finding."]),
    ]


def build_extra_rules():
    """Behaviour in code that the specification does not contain.

    Sourced from RULES_ALEXG.hubTestStandardizations -- the artifact's own,
    already-approved list of what MOGO chose rather than what Alex stated. Only
    the entries that actually affect the traded decision path are enumerated
    individually; the artifact's full list is carried in the report."""
    E = fm.extra_implementation_rule
    return [
        E("ALEX_X_001", "Entire stop-loss / take-profit / risk / R:R mechanism",
          "RISK",
          "RULES_ALEXG.hubTestStandardizations states this is '100% unaddressed by the source'. "
          "The implementation nonetheless trades a complete risk model: stopATRBuffer 0.25, "
          "riskPercent 1.0, minRR 2.0. Every ALEX trade's stop, target and size come from rules "
          "the specification does not contain.",
          [_ref("RULES_ALEXG.config.stopATRBuffer"),
           _ref("alexGConstructLivePosition")],
          evaluators=["alexGConstructLivePosition", "alexGComputeATRAtEntry"],
          tests=["tests/v_paper_trading_audit_tests.js"],
          origin="hub_standardization", affects_trading_behavior=True),

        E("ALEX_X_002", "Live entry-delay gate (maxLiveEntryDelayPips)",
          "ENTRY",
          "A live-only gate rejecting a fill more than 5 pips from the qualification close "
          "(ENTRY_MOVED_TOO_FAR_FROM_SIGNAL). The artifact states 'the source never addresses live "
          "execution latency at all'.",
          [_ref("RULES_ALEXG.config.maxLiveEntryDelayPips"), _ref("alexGConstructLivePosition")],
          evaluators=["alexGConstructLivePosition"],
          tests=["tests/v126_phase2c_wave1_tests.js"],
          origin="engineering_necessity", affects_trading_behavior=True),

        E("ALEX_X_003", "Signal staleness gate (maxLiveSignalAgeMinutes)",
          "ENTRY",
          "One bar-period per timeframe; a setup first evaluated later than that is IGNORED — "
          "STALE SIGNAL. Emitted as ruleId ALEX_SIGNAL_STALENESS. The artifact states the source "
          "never addresses signal age.",
          [_ref("RULES_ALEXG.config.maxLiveSignalAgeMinutes"), _ref("alexGIsSetupSignalStale")],
          evaluators=["alexGIsSetupSignalStale"],
          tests=["tests/v126_phase2c_wave1_tests.js"],
          origin="engineering_necessity", affects_trading_behavior=True),

        E("ALEX_X_004", "Activation cutoff gate",
          "NO_TRADE_CONDITIONS",
          "Setups qualifying before the account's activation timestamp are rejected "
          "(CONFIG_BEFORE_ACTIVATION). Emitted as ruleId ALEX_ACTIVATION_CUTOFF. Not a source concept.",
          [_ref("alexGIsSetupEligibleForLiveTrading")],
          evaluators=["alexGIsSetupEligibleForLiveTrading"],
          tests=["tests/v126_phase2c_wave1_tests.js"],
          origin="engineering_necessity", affects_trading_behavior=True),

        E("ALEX_X_005", "Choppy-zone penetration filter",
          "SETUP",
          "A zone with >=3 counted penetrations in a 50-bar lookback is flagged 'choppy' and "
          "disqualified. The source states no such filter.",
          [_ref("alexGCorrectedQuality"), _ref("RULES_ALEXG.config.maxPenetrationsBeforeChoppyFlag")],
          evaluators=["alexGCorrectedQuality"],
          tests=["tests/v126_phase2c_wave1_tests.js"],
          origin="hub_standardization", affects_trading_behavior=True),

        E("ALEX_X_006", "Rejection-confirmation window and displacement threshold",
          "SETUP",
          "A reaction only counts if confirmed within rejectionConfirmWithinBars=1 and displaces "
          "at least 0.25 ATR. The source describes reactions qualitatively with no threshold.",
          [_ref("RULES_ALEXG.config.rejectionConfirmWithinBars"),
           _ref("RULES_ALEXG.config.rejectionDisplacementATRMultiplier"),
           _ref("alexGAcceptReaction")],
          evaluators=["alexGAcceptReaction"],
          tests=["tests/v126_phase2c_wave1_tests.js"],
          origin="hub_standardization", affects_trading_behavior=True),

        E("ALEX_X_007", "Zero session / day / news filtering",
          "SESSION_RESTRICTIONS",
          "The artifact records this as 'a deliberate design choice, not a source gap'. Session and "
          "day metadata ARE computed and recorded but never restrict entry.",
          [_ref("alexGComputeSessionMetadata")],
          evaluators=["alexGComputeSessionMetadata"],
          tests=["tests/v_paper_trading_audit_tests.js"],
          origin="hub_standardization", affects_trading_behavior=False),

        E("ALEX_X_008", "ALEX_SCORE_V2 — a second, parallel Alex strategy",
          "SETUP",
          "A separate research strategy (strategyId ALEX_SCORE_V2, version 1.0.0-research) with its "
          "own weighted-score rule hierarchy: higher-timeframe trend, area of interest, price-action "
          "confirmation, 50 EMA confluence. It is shadow-mode only (alexV2AutoTrading.enabled is "
          "false and nothing flips it) and fully isolated in its own state and storage keys, so it "
          "does NOT execute paper trades and is out of scope for this fidelity comparison. It is "
          "recorded here because it is a second implementation claiming the Alex name.",
          [_ref("ALEX_V2_META"), _ref("saveAlexV2")],
          evaluators=["alexV2ComputeTrendState", "alexV2FindStructuralAOI", "alexV2DetectEntrySignal"],
          tests=[],
          origin="experimental", affects_trading_behavior=False),
    ]


def _function_spans(lines):
    """Map every top-level `function NAME(` to its declaration line."""
    out = {}
    for i, line in enumerate(lines, start=1):
        m = re.match(r"\s*function\s+([A-Za-z0-9_$]+)\s*\(", line)
        if m:
            out.setdefault(m.group(1), i)
    return out


def _const_lines(lines):
    """Map `const NAME=` / `const NAME =` to its declaration line."""
    out = {}
    for i, line in enumerate(lines, start=1):
        m = re.match(r"\s*const\s+([A-Za-z0-9_$]+)\s*=", line)
        if m:
            out.setdefault(m.group(1), i)
    return out


def _config_key_lines(lines):
    """Map each RULES_ALEXG.config key to the line it is declared on."""
    out, in_block = {}, False
    for i, line in enumerate(lines, start=1):
        if "const RULES_ALEXG={" in line:
            in_block = True
        elif in_block and re.match(r"^\};\s*$", line):
            break
        if in_block:
            m = re.match(r"\s{4}([A-Za-z][A-Za-z0-9_]*)\s*:", line)
            if m:
                out.setdefault(m.group(1), i)
    return out


def resolve_references(mappings, extras, path=None):
    """Resolve every symbol reference to a real, current line in index.html.

    Mutates each reference's `locator` in place and returns the list of symbols
    that could not be resolved. Resolving at BUILD TIME rather than storing hand-
    written line numbers is what stops the manifest from rotting silently: if a
    symbol is renamed or deleted, this reports it instead of pointing at whatever
    code happens to occupy that line now."""
    with open(path or INDEX_HTML, encoding="utf-8") as f:
        lines = f.read().split("\n")
    fns = _function_spans(lines)
    consts = _const_lines(lines)
    cfg_keys = _config_key_lines(lines)

    problems = []
    all_refs = []
    for m in mappings:
        all_refs += [(m["ruleId"], r) for r in m["implementationReferences"]]
    for e in extras:
        all_refs += [(e["id"], r) for r in e["implementationReferences"]]

    for owner, ref in all_refs:
        sym = ref["symbol"]
        key = sym.split(".")[-1].strip()
        line = fns.get(key) or consts.get(key) or cfg_keys.get(key)
        if line is None:
            problems.append("%s: symbol %r not found in index.html" % (owner, sym))
            ref["locator"] = None
        else:
            ref["locator"] = "index.html:%d" % line
    return problems


def verify_references(mappings, extras, path=None):
    """Back-compat alias: resolution IS verification under the symbol-based model."""
    return resolve_references(mappings, extras, path)


def build_manifest(path=None, app_version=None):
    mappings = build_mappings()
    extras = build_extra_rules()
    problems = resolve_references(mappings, extras, path)
    spec = aspec.build_specification(path)
    man = fm.strategy_implementation_manifest(
        strategy_id="alex_g_sr_v1",
        implementation_version=MANIFEST_VERSION,
        specification_version=spec["specificationVersion"],
        mappings=mappings,
        engine_version=app_version or _read_app_version(path),
        extra_implementation_rules=extras,
        notes=("Every mapping was produced by reading the cited code path during MOGO-002.5. "
               "48 of the 63 protected functions in regression-baseline.json are ALEX functions, "
               "so several rules are implemented inside code that cannot be instrumented without "
               "baseline drift; those limitations are stated per mapping rather than hidden."))
    man["referenceVerification"] = {
        "checked": True,
        "method": "symbol_resolution_at_build_time",
        "problemCount": len(problems),
        "problems": problems,
        "note": ("Locators are RESOLVED from symbols each time the manifest is built, never "
                 "stored by hand. A renamed or deleted symbol is reported here rather than "
                 "silently pointing at unrelated code."),
    }
    return man


def _read_app_version(path=None):
    try:
        with open(path or INDEX_HTML, encoding="utf-8") as f:
            text = f.read()
        m = re.search(r"APP_VERSION\s*=\s*'([^']+)'", text)
        return m.group(1) if m else None
    except OSError:
        return None


if __name__ == "__main__":
    print(fm.dumps(build_manifest()))

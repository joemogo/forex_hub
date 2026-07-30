"""MOGO-002.5 — Strategy Fidelity domain model.

Provider-independent, versioned model for comparing an APPROVED STRATEGY
SPECIFICATION against an ACTUAL REPOSITORY IMPLEMENTATION.

Pure Python standard library. NO NETWORK ACCESS ANYWHERE IN THIS MODULE.

WHY THIS LIVES IN scripts/ AND NOT IN index.html
------------------------------------------------
`RULES_ALEXG` and 48 ALEX functions -- including `alexGConstructLivePosition`,
`alexGRunSetupEngine`, `alexGEvaluateBreakRetest` and `alexGEvaluateRepeatedReaction`
-- are PROTECTED FUNCTIONS/CONSTANTS in regression-baseline.json. A fidelity
auditor implemented inside the application would either have to touch protected
code or sit beside it and drift. This module is an OFFLINE AUDIT TOOL: it reads
the repository as data and writes reports. It never executes, alters, or is
imported by trading code, so it cannot change ALEX's behaviour by construction.

It reuses graph_common.py's canonical JSON/hash/atomic-write utilities rather
than duplicating them -- the same convention evidence_common.py and
acquisition_common.py already follow.

MODEL VERSIONING
----------------
`FIDELITY_MODEL_VERSION` changes when the SHAPE of a record changes.
`REPORT_GENERATOR_VERSION` changes when comparison LOGIC changes, because the
same inputs may then legitimately produce different findings. Both are stamped
into every report so an old report can never be silently reinterpreted under
new rules -- the same reasoning behind `snapshotAlexGConfig()` in index.html.
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "trader_intelligence"))
import graph_common as gc  # noqa: E402

FIDELITY_MODEL_VERSION = "mogo.strategy-fidelity.v1"
REPORT_GENERATOR_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Controlled vocabularies
# ---------------------------------------------------------------------------

# How firmly the SOURCE states the rule. Deliberately the same five the
# MOGO-002.5 brief names. Note DISCRETIONARY is NOT a weaker EXPLICIT: it means
# the source states a decision point but leaves the decision to the trader, so
# it can never be "missing implementation" -- see NOT_APPLICABLE below.
RULE_CLASSIFICATIONS = [
    "EXPLICIT",       # stated outright by the source
    "IMPLIED",        # follows necessarily from what the source states
    "INFERRED",       # reconstructed by analysis; the source does not state it
    "DISCRETIONARY",  # the source explicitly leaves this to trader judgement
    "UNRESOLVED",     # the source is ambiguous or silent and it matters
]

# Category taxonomy. Ordered coarse-to-fine along the decision path so
# category summaries read in the order a trade is actually made.
RULE_CATEGORIES = [
    "MARKET_CONDITIONS",
    "TIMEFRAMES",
    "DIRECTIONAL_BIAS",
    "MARKET_STRUCTURE",
    "LIQUIDITY",
    "SETUP",
    "ENTRY",
    "INVALIDATION",
    "RISK",
    "TRADE_MANAGEMENT",
    "EXIT",
    "SESSION_RESTRICTIONS",
    "NO_TRADE_CONDITIONS",
    "DISCRETIONARY_ELEMENTS",
]

IMPLEMENTATION_STATUSES = [
    "IMPLEMENTED",      # a named code path implements the rule as stated
    "NOT_IMPLEMENTED",  # no code path implements it, and that is established
    "APPROXIMATED",     # implemented, but with a substituted/standardized parameter
    "UNSUPPORTED",      # cannot be implemented in this architecture
    "UNKNOWN",          # not yet inspected -- NEVER assume from absence of evidence
]

FINDING_STATUSES = [
    "MATCH",
    "MISSING_IMPLEMENTATION",
    "IMPLEMENTATION_DIFFERS",
    "EXTRA_IMPLEMENTATION_RULE",
    "APPROXIMATED",
    "AMBIGUOUS",
    "UNVERIFIABLE",
    "NOT_APPLICABLE",
]

VALIDATION_STATUSES = [
    "UNVALIDATED",          # default. No replay, no paper evidence.
    "SOURCE_VERIFIED",      # traceable to a source reference, nothing more
    "IMPLEMENTATION_VERIFIED",  # a code path was actually inspected
    "TEST_COVERED",         # a named test exercises it
    "REPLAY_VALIDATED",     # reserved -- requires replay authorization
]

CONFIDENCE_LEVELS = ["NONE", "LOW", "MEDIUM", "HIGH"]

TRACE_RESULTS = ["PASS", "FAIL", "SKIPPED", "NOT_EVALUATED", "ERROR"]


class FidelityModelError(ValueError):
    """Raised when a record violates the model. Never caught-and-continued by
    the report generator: a malformed record must not become a silent MATCH."""


def _require(cond, msg):
    if not cond:
        raise FidelityModelError(msg)


def _vocab(value, vocab, field):
    _require(value in vocab, "%s=%r is not one of %r" % (field, value, vocab))
    return value


# ---------------------------------------------------------------------------
# StrategyVersionReference
# ---------------------------------------------------------------------------

def strategy_version_reference(strategy_id, specification_version,
                               implementation_version=None, engine_version=None,
                               rule_set_hash=None, configuration_hash=None,
                               decision_trace_version=None):
    """Identity of a specific (spec, implementation) pair.

    Every field is explicit-None rather than defaulted, because a fabricated
    version is worse than an absent one -- the same rule the Decision Event
    schema already applies ("a missing value is always an explicit null")."""
    _require(bool(strategy_id), "strategyId is required")
    _require(bool(specification_version), "specificationVersion is required")
    return {
        "strategyId": strategy_id,
        "specificationVersion": specification_version,
        "implementationVersion": implementation_version,
        "engineVersion": engine_version,
        "ruleSetHash": rule_set_hash,
        "configurationHash": configuration_hash,
        "decisionTraceVersion": decision_trace_version,
    }


# ---------------------------------------------------------------------------
# RuleSourceReference
# ---------------------------------------------------------------------------

def rule_source_reference(kind, locator, excerpt=None, note=None):
    """Where a rule came from.

    `kind` distinguishes the two evidence classes the governance requires be
    kept separate:
      repository_constant -- an approved in-repo artifact (e.g. RULES_ALEXG)
      evidence_claim      -- a Trader Intelligence claim (educator material)
      derived             -- MOGO analysis, not the source's own words
    Mixing these silently is precisely what DECISION|MOGO|20260727|004 forbids.
    """
    _require(kind in ("repository_constant", "repository_code", "evidence_claim",
                      "document", "derived"),
             "unknown source reference kind %r" % (kind,))
    _require(bool(locator), "locator is required")
    return {"kind": kind, "locator": locator, "excerpt": excerpt, "note": note}


# ---------------------------------------------------------------------------
# StrategyRule
# ---------------------------------------------------------------------------

def strategy_rule(rule_id, version, title, normalized_statement, classification,
                  category, required, deterministic, source_references,
                  dependencies=None, confidence="NONE",
                  validation_status="UNVALIDATED", notes=None):
    _require(bool(rule_id), "rule id is required")
    _require(bool(version), "rule version is required")
    _require(bool(title), "rule title is required")
    _require(bool(normalized_statement), "normalizedStatement is required")
    _vocab(classification, RULE_CLASSIFICATIONS, "classification")
    _vocab(category, RULE_CATEGORIES, "category")
    _require(isinstance(required, bool), "required must be a bool")
    _require(isinstance(deterministic, bool), "deterministic must be a bool")
    _require(isinstance(source_references, list) and source_references,
             "at least one sourceReference is required for rule %s" % rule_id)
    _vocab(confidence, CONFIDENCE_LEVELS, "confidence")
    _vocab(validation_status, VALIDATION_STATUSES, "validationStatus")

    # A DISCRETIONARY rule that is also `required` is incoherent: the source
    # cannot simultaneously mandate an outcome and leave it to judgement.
    _require(not (classification == "DISCRETIONARY" and required),
             "rule %s is DISCRETIONARY and required=True -- contradictory" % rule_id)
    # An UNRESOLVED rule cannot be deterministic: if the source is ambiguous
    # there is nothing definite to implement deterministically.
    _require(not (classification == "UNRESOLVED" and deterministic),
             "rule %s is UNRESOLVED and deterministic=True -- contradictory" % rule_id)

    return {
        "id": rule_id,
        "version": version,
        "title": title,
        "normalizedStatement": normalized_statement,
        "classification": classification,
        "category": category,
        "required": required,
        "deterministic": deterministic,
        "sourceReferences": source_references,
        "dependencies": list(dependencies or []),
        "confidence": confidence,
        "validationStatus": validation_status,
        "notes": notes,
    }


# ---------------------------------------------------------------------------
# StrategySpecification
# ---------------------------------------------------------------------------

def strategy_specification(strategy_id, specification_version, title, rules,
                           provenance_note=None, extracted_from=None):
    _require(bool(strategy_id), "strategyId is required")
    _require(bool(specification_version), "specificationVersion is required")
    _require(isinstance(rules, list), "rules must be a list")
    ids = [r["id"] for r in rules]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    _require(not dupes, "duplicate rule ids in specification: %r" % dupes)
    known = set(ids)
    for r in rules:
        for dep in r["dependencies"]:
            _require(dep in known,
                     "rule %s depends on unknown rule %r" % (r["id"], dep))
    spec = {
        "modelVersion": FIDELITY_MODEL_VERSION,
        "strategyId": strategy_id,
        "specificationVersion": specification_version,
        "title": title,
        "provenanceNote": provenance_note,
        "extractedFrom": extracted_from,
        "ruleCount": len(rules),
        "rules": rules,
    }
    spec["ruleSetHash"] = gc.content_hash_of(
        [{k: r[k] for k in ("id", "version", "normalizedStatement",
                            "classification", "category", "required",
                            "deterministic")} for r in rules])
    return spec


# ---------------------------------------------------------------------------
# ImplementationRuleMapping / StrategyImplementationManifest
# ---------------------------------------------------------------------------

def implementation_rule_mapping(rule_id, implementation_status,
                                implementation_references=None,
                                evaluators=None, tests=None,
                                implementation_notes=None,
                                known_limitations=None,
                                inspected=False,
                                approximation_detail=None):
    """Maps ONE specification rule onto real code.

    `inspected` is deliberately separate from `implementation_status`. The brief
    says "Do not claim a rule is implemented unless the code path has been
    inspected" -- so IMPLEMENTED/APPROXIMATED without inspected=True is a model
    error, not a warning. UNKNOWN is the honest default."""
    _vocab(implementation_status, IMPLEMENTATION_STATUSES, "implementationStatus")
    _require(isinstance(inspected, bool), "inspected must be a bool")
    refs = list(implementation_references or [])
    if implementation_status in ("IMPLEMENTED", "APPROXIMATED"):
        _require(inspected,
                 "rule %s claims %s without inspected=True" % (rule_id, implementation_status))
        _require(refs, "rule %s claims %s with no implementation reference"
                 % (rule_id, implementation_status))
    if implementation_status == "APPROXIMATED":
        _require(bool(approximation_detail),
                 "rule %s is APPROXIMATED but states no approximationDetail" % rule_id)
    return {
        "ruleId": rule_id,
        "implementationStatus": implementation_status,
        "implementationReferences": refs,
        "evaluators": list(evaluators or []),
        "tests": list(tests or []),
        "implementationNotes": implementation_notes,
        "knownLimitations": list(known_limitations or []),
        "inspected": inspected,
        "approximationDetail": approximation_detail,
    }


def strategy_implementation_manifest(strategy_id, implementation_version,
                                     specification_version, mappings,
                                     engine_version=None,
                                     extra_implementation_rules=None,
                                     notes=None):
    """`extraImplementationRules` are behaviours the CODE has that the
    SPECIFICATION does not. They are first-class, not an afterthought: in this
    repository they are the majority finding, and hiding them would make the
    implementation look more faithful than it is."""
    _require(isinstance(mappings, list), "mappings must be a list")
    ids = [m["ruleId"] for m in mappings]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    _require(not dupes, "duplicate ruleIds in manifest: %r" % dupes)
    man = {
        "modelVersion": FIDELITY_MODEL_VERSION,
        "strategyId": strategy_id,
        "implementationVersion": implementation_version,
        "specificationVersion": specification_version,
        "engineVersion": engine_version,
        "mappingCount": len(mappings),
        "mappings": mappings,
        "extraImplementationRules": list(extra_implementation_rules or []),
        "notes": notes,
    }
    man["manifestHash"] = gc.content_hash_of(
        [{k: m[k] for k in ("ruleId", "implementationStatus", "implementationReferences",
                            "evaluators")} for m in mappings])
    return man


def extra_implementation_rule(rule_id, title, category, description,
                              implementation_references, evaluators=None,
                              tests=None, origin="hub_standardization",
                              affects_trading_behavior=True):
    """A behaviour present in code but absent from the specification.

    `origin` distinguishes an honest engineering standardization (the source was
    silent and something had to be chosen) from an unexplained divergence."""
    _vocab(category, RULE_CATEGORIES, "category")
    _require(origin in ("hub_standardization", "engineering_necessity",
                        "experimental", "unexplained"),
             "unknown extra-rule origin %r" % (origin,))
    _require(bool(implementation_references),
             "extra rule %s must cite implementation references" % rule_id)
    return {
        "id": rule_id,
        "title": title,
        "category": category,
        "description": description,
        "implementationReferences": list(implementation_references),
        "evaluators": list(evaluators or []),
        "tests": list(tests or []),
        "origin": origin,
        "affectsTradingBehavior": bool(affects_trading_behavior),
    }


# ---------------------------------------------------------------------------
# StrategyFidelityFinding / StrategyFidelityReport
# ---------------------------------------------------------------------------

def strategy_fidelity_finding(rule_id, status, category, classification,
                              required, deterministic, rationale,
                              implementation_status=None,
                              implementation_references=None,
                              tests=None, limitations=None):
    _vocab(status, FINDING_STATUSES, "status")
    _vocab(category, RULE_CATEGORIES, "category")
    _require(bool(rationale), "every finding must carry a rationale")
    return {
        "ruleId": rule_id,
        "status": status,
        "category": category,
        "classification": classification,
        "required": required,
        "deterministic": deterministic,
        "implementationStatus": implementation_status,
        "implementationReferences": list(implementation_references or []),
        "tests": list(tests or []),
        "limitations": list(limitations or []),
        "rationale": rationale,
    }


def rule_evaluation_trace(rule_id, rule_version, result, evaluator, timestamp,
                          observed_input=None, reason=None, required=None,
                          confidence=None, version_reference=None,
                          market_data_reference=None):
    """One rule's evaluation during a real decision.

    `marketDataReference` is a POINTER (pair/timeframe/candle time), never the
    candle payload -- the brief forbids duplicating large market payloads, and
    the Decision Event schema already made the same choice."""
    _vocab(result, TRACE_RESULTS, "result")
    _require(bool(rule_id), "ruleId is required")
    _require(bool(evaluator), "evaluator is required")
    if confidence is not None:
        _vocab(confidence, CONFIDENCE_LEVELS, "confidence")
    return {
        "ruleId": rule_id,
        "ruleVersion": rule_version,
        "observedInput": observed_input,
        "result": result,
        "reason": reason,
        "required": required,
        "confidence": confidence,
        "evaluator": evaluator,
        "timestamp": timestamp,
        "versionReference": version_reference,
        "marketDataReference": market_data_reference,
    }


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def dumps(obj):
    """Stable, deterministic text form. Sorted keys + fixed separators, so two
    runs over identical inputs are byte-identical and diffable."""
    return gc.pretty_json(obj)


def loads(text):
    import json
    return json.loads(text)


def write(path, obj):
    gc.atomic_write_text(path, dumps(obj))
    return path

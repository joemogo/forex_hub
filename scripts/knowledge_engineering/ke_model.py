"""MOGO-002.6 — Knowledge Engineering domain model.

Transforms unstructured educator claims into traceable, normalized, machine-readable
strategy rules. Pure Python standard library. NO NETWORK ACCESS.

WHY THIS IS A SEPARATE STORE, NOT NEW RECORDS IN evidence/
----------------------------------------------------------
An approved `RuleCandidateProposal` model already exists (ADR-009 sec. 8,
`scripts/trader_intelligence/rule_candidate_proposals.py`). It is NOT reused as the
write target here, for a specific and checkable reason:

  `extraction_pipeline.run_post_annotation_pipeline()` creates a proposal only for a
  claim that has reached `supported`. All 195 ALEX_G claims sit at `emerging`.
  Writing proposals into `evidence/proposals/` would therefore either require
  lowering that gate -- violating POLICY-001 -- or bypassing the pipeline, which
  would make KNOWLEDGE-DASHBOARD.md report a non-zero "rule candidates" count and
  imply confidence movement that has not happened.

So: this module READS the evidence store and writes derived artifacts to its own
location. The evidence store is never mutated. Its vocabularies, ID conventions and
canonical-JSON utilities ARE reused rather than reinvented.

APPROVAL CEILING
----------------
`assert_no_unapproved_promotion()` enforces the Engineering Authority's OD-1
modification: no rule created in this milestone may exceed NEEDS_REVIEW. It is a
hard error, not a lint.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "trader_intelligence"))
import graph_common as gc      # noqa: E402  canonical JSON / hashing / atomic write
import evidence_common as evc  # noqa: E402  existing vocabularies

KE_MODEL_VERSION = "mogo.knowledge-engineering.v1"
KE_GENERATOR_VERSION = "1.0.0"

# --- Vocabularies -----------------------------------------------------------

CLAIM_CLASSIFICATIONS = [
    "TRADING_RULE", "DEFINITION", "MARKET_CONTEXT", "ENTRY", "EXIT", "RISK",
    "TRADE_MANAGEMENT", "SESSION", "TIMEFRAME", "MARKET_STRUCTURE", "LIQUIDITY",
    "INVALIDATION", "NO_TRADE_CONDITION", "DISCRETIONARY_GUIDANCE", "EXAMPLE",
    "PSYCHOLOGY", "OPINION", "MARKETING", "EDUCATIONAL_COMMENTARY", "UNKNOWN",
]

CLAIM_EXPLICITNESS = ["EXPLICIT", "IMPLIED", "INFERRED", "DISCRETIONARY", "UNRESOLVED"]

RULE_MATURITY = [
    "OBSERVED", "EXTRACTED", "CANDIDATE", "NORMALIZED", "SPECIFIED",
    "IMPLEMENTED", "REPLAY_TESTED", "PAPER_VALIDATED", "PRODUCTION_READY", "ARCHIVED",
]

APPROVAL_STATUSES = ["DRAFT", "NEEDS_REVIEW", "APPROVED", "REJECTED", "DEFERRED"]

# The ceiling this milestone may not exceed (OD-1, modification 6).
MAX_APPROVAL_THIS_MILESTONE = "NEEDS_REVIEW"
_APPROVAL_RANK = {s: i for i, s in enumerate(["DRAFT", "NEEDS_REVIEW", "APPROVED"])}

# Strategy domains, ordered along the decision path. Shared with MOGO-002.5's
# fidelity categories so the two milestones' reports are directly comparable.
STRATEGY_DOMAINS = [
    "MARKET_CONDITIONS", "TIMEFRAMES", "DIRECTIONAL_BIAS", "MARKET_STRUCTURE",
    "LIQUIDITY", "SETUP", "ENTRY", "INVALIDATION", "RISK", "TRADE_MANAGEMENT",
    "EXIT", "SESSION_RESTRICTIONS", "NO_TRADE_CONDITIONS", "DISCRETIONARY_ELEMENTS",
    "UNRESOLVED_QUESTIONS",
]

CONFIDENCE_LEVELS = ["NONE", "LOW", "MEDIUM", "HIGH"]
REVIEW_STATES = ["NOT_REVIEWED", "PENDING_REVIEW", "REVIEWED_ACCEPTED", "REVIEWED_REJECTED", "DEFERRED"]
OVERLAP_DEGREES = ["IDENTICAL", "NEAR_DUPLICATE", "SAME_CONCEPT_DIFFERENT_DETAIL", "RELATED_NOT_DUPLICATE"]
MERGE_RECOMMENDATIONS = ["MERGE", "MERGE_WITH_CAVEATS", "DO_NOT_MERGE", "NEEDS_REVIEW"]
CONTRADICTION_TYPES = list(evc.CONTRADICTION_TYPES)          # reuse, do not redefine
CONTRADICTION_SEVERITIES = list(evc.CONTRADICTION_SEVERITIES)


class KEModelError(ValueError):
    """Raised on any model violation. Never caught-and-continued by the generators:
    a malformed record must not become a silently plausible draft rule."""


def _req(cond, msg):
    if not cond:
        raise KEModelError(msg)


def _vocab(v, vocab, field):
    _req(v in vocab, "%s=%r not in %r" % (field, v, vocab))
    return v


def assert_no_unapproved_promotion(record):
    """OD-1 modification 6, enforced. A record may not claim APPROVED (or any
    maturity beyond NORMALIZED) unless it carries an explicit repository approval
    reference -- and this milestone issues none."""
    ap = record.get("approvalStatus")
    if ap in ("APPROVED",) and not record.get("approvalReference"):
        raise KEModelError(
            "%s claims approvalStatus=APPROVED with no approvalReference. "
            "MOGO-002.6 may not promote beyond %s."
            % (record.get("ruleId") or record.get("candidateRuleId"), MAX_APPROVAL_THIS_MILESTONE))
    mat = record.get("maturity")
    if mat and RULE_MATURITY.index(mat) > RULE_MATURITY.index("NORMALIZED"):
        raise KEModelError(
            "%s claims maturity=%s. MOGO-002.6 produces nothing beyond NORMALIZED."
            % (record.get("ruleId"), mat))
    return record


# --- SourceArtifact / SourceReference ---------------------------------------

def source_artifact(source_id, educator_id, source_type, title, reference,
                    content_hash, ingestion_date, provenance_status,
                    publication_date=None, transcript_version=None,
                    quality_notes=None):
    _req(bool(source_id), "sourceId required")
    _req(bool(educator_id), "educatorId required")
    _vocab(provenance_status, evc.PROVENANCE_STATUSES, "provenanceStatus")
    return {
        "sourceId": source_id, "educatorId": educator_id, "sourceType": source_type,
        "title": title, "reference": reference,
        "publicationDate": publication_date,      # explicit None, never fabricated
        "ingestionDate": ingestion_date, "transcriptVersion": transcript_version,
        "contentHash": content_hash, "provenanceStatus": provenance_status,
        "sourceQualityNotes": list(quality_notes or []),
    }


def source_reference(source_id, evidence_id=None, segment_id=None, exact_excerpt=None):
    _req(bool(source_id), "sourceId required on a source reference")
    return {"sourceId": source_id, "evidenceId": evidence_id,
            "segmentId": segment_id, "exactExcerpt": exact_excerpt}


# --- EducatorClaim ----------------------------------------------------------

def educator_claim(claim_id, educator_id, source_references, source_text,
                   normalized_paraphrase, category, classification, explicitness,
                   confidence, context=None, timeframe_references=None,
                   session_references=None, instrument_references=None,
                   dependencies=None, contradictions=None,
                   review_status="NOT_REVIEWED", notes=None,
                   origin_claim_type=None, origin_confidence_state=None):
    """`sourceText` is the educator's own words, carried through unchanged.
    `normalizedParaphrase` is MOGO's restatement. The two are kept in separate
    fields precisely so a paraphrase can never be mistaken for a quotation."""
    _req(bool(claim_id), "claimId required")
    _req(isinstance(source_references, list) and source_references,
         "claim %s has no sourceReferences -- provenance is mandatory" % claim_id)
    _vocab(classification, CLAIM_CLASSIFICATIONS, "classification")
    _vocab(explicitness, CLAIM_EXPLICITNESS, "explicitness")
    _vocab(confidence, CONFIDENCE_LEVELS, "confidence")
    _vocab(review_status, REVIEW_STATES, "reviewStatus")
    return {
        "claimId": claim_id, "educatorId": educator_id,
        "sourceReferences": source_references,
        "sourceText": source_text,
        "normalizedParaphrase": normalized_paraphrase,
        "category": category, "classification": classification,
        "explicitness": explicitness, "confidence": confidence,
        "context": context,
        "timeframeReferences": list(timeframe_references or []),
        "sessionReferences": list(session_references or []),
        "instrumentReferences": list(instrument_references or []),
        "dependencies": list(dependencies or []),
        "contradictions": list(contradictions or []),
        "reviewStatus": review_status, "notes": notes,
        "originClaimType": origin_claim_type,
        "originConfidenceState": origin_confidence_state,
    }


def claim_classification(claim_id, classification, explicitness, rationale,
                         candidate_rule_eligible, derived_from):
    """A first-class record of WHY a claim was classified as it was, and whether it
    is eligible to become a rule. `derivedFrom` names the existing evidence fields
    the decision came from, so no classification is unattributable."""
    _vocab(classification, CLAIM_CLASSIFICATIONS, "classification")
    _vocab(explicitness, CLAIM_EXPLICITNESS, "explicitness")
    _req(bool(rationale), "every classification must carry a rationale")
    _req(isinstance(candidate_rule_eligible, bool), "candidateRuleEligible must be bool")
    return {
        "claimId": claim_id, "classification": classification,
        "explicitness": explicitness, "rationale": rationale,
        "candidateRuleEligible": candidate_rule_eligible,
        "derivedFrom": list(derived_from),
    }


# --- CandidateRule ----------------------------------------------------------

def candidate_rule(candidate_rule_id, originating_claim_ids, proposed_statement,
                   category, required, deterministic, proposed_conditions=None,
                   proposed_action=None, dependencies=None,
                   unresolved_parameters=None, source_support=None,
                   contradiction_references=None, normalization_confidence="LOW",
                   review_status="PENDING_REVIEW", notes=None):
    _req(bool(candidate_rule_id), "candidateRuleId required")
    _req(isinstance(originating_claim_ids, list) and originating_claim_ids,
         "candidate %s must originate from at least one claim" % candidate_rule_id)
    _vocab(category, STRATEGY_DOMAINS, "category")
    _vocab(normalization_confidence, CONFIDENCE_LEVELS, "normalizationConfidence")
    _vocab(review_status, REVIEW_STATES, "reviewStatus")
    _req(isinstance(required, bool), "required must be bool")
    _req(isinstance(deterministic, bool), "deterministic must be bool")
    return {
        "candidateRuleId": candidate_rule_id,
        "originatingClaimIds": list(originating_claim_ids),
        "proposedCanonicalStatement": proposed_statement,
        "category": category, "required": required, "deterministic": deterministic,
        "proposedConditions": list(proposed_conditions or []),
        "proposedAction": proposed_action,
        "dependencies": list(dependencies or []),
        "unresolvedParameters": list(unresolved_parameters or []),
        "sourceSupport": source_support or {},
        "contradictionReferences": list(contradiction_references or []),
        "normalizationConfidence": normalization_confidence,
        "reviewStatus": review_status, "notes": notes,
        "maturity": "CANDIDATE", "approvalStatus": "DRAFT",
    }


# --- NormalizedRule ---------------------------------------------------------

def normalized_rule(rule_id, version, educator_id, canonical_statement, category,
                    classification, required, deterministic, conditions=None,
                    outputs=None, exclusions=None, dependencies=None,
                    source_mappings=None, contradiction_references=None,
                    unresolved_elements=None, confidence="LOW",
                    maturity="NORMALIZED", validation_status="UNVALIDATED",
                    approval_status="NEEDS_REVIEW", notes=None,
                    approval_reference=None):
    _req(bool(rule_id), "ruleId required")
    _vocab(category, STRATEGY_DOMAINS, "category")
    _vocab(classification, CLAIM_EXPLICITNESS, "classification")
    _vocab(confidence, CONFIDENCE_LEVELS, "confidence")
    _vocab(maturity, RULE_MATURITY, "maturity")
    _vocab(approval_status, APPROVAL_STATUSES, "approvalStatus")
    _req(isinstance(source_mappings, list) and source_mappings,
         "normalized rule %s must carry at least one source mapping" % rule_id)
    # A DISCRETIONARY or UNRESOLVED rule cannot be deterministic -- the same
    # coherence guard MOGO-002.5 applies, kept identical on purpose.
    _req(not (classification in ("DISCRETIONARY", "UNRESOLVED") and deterministic),
         "rule %s is %s and deterministic=True -- contradictory" % (rule_id, classification))
    rec = {
        "ruleId": rule_id, "version": version, "educatorId": educator_id,
        "canonicalStatement": canonical_statement, "category": category,
        "classification": classification, "required": required,
        "deterministic": deterministic,
        "conditions": list(conditions or []), "outputs": list(outputs or []),
        "exclusions": list(exclusions or []), "dependencies": list(dependencies or []),
        "sourceMappings": list(source_mappings),
        "contradictionReferences": list(contradiction_references or []),
        "unresolvedElements": list(unresolved_elements or []),
        "confidence": confidence, "maturity": maturity,
        "validationStatus": validation_status, "approvalStatus": approval_status,
        "approvalReference": approval_reference, "notes": notes,
    }
    return assert_no_unapproved_promotion(rec)


def rule_source_mapping(rule_id, claim_id, source_id, relationship, exact_excerpt=None):
    _req(relationship in ("primary", "supporting", "contextual", "excluded"),
         "unknown mapping relationship %r" % relationship)
    return {"ruleId": rule_id, "claimId": claim_id, "sourceId": source_id,
            "relationship": relationship, "exactExcerpt": exact_excerpt}


# --- Duplicate / contradiction / gap ----------------------------------------

def duplicate_claim_group(group_id, member_claim_ids, proposed_concept,
                          overlap_degree, meaningful_differences,
                          source_chronology, merge_recommendation, confidence,
                          review_status="PENDING_REVIEW", blocking_reasons=None):
    _req(len(member_claim_ids) >= 2, "group %s needs >=2 members" % group_id)
    _vocab(overlap_degree, OVERLAP_DEGREES, "overlapDegree")
    _vocab(merge_recommendation, MERGE_RECOMMENDATIONS, "mergeRecommendation")
    _vocab(confidence, CONFIDENCE_LEVELS, "confidence")
    return {
        "groupId": group_id, "memberClaimIds": sorted(member_claim_ids),
        "proposedCanonicalConcept": proposed_concept,
        "overlapDegree": overlap_degree,
        "meaningfulDifferences": list(meaningful_differences or []),
        "sourceChronology": list(source_chronology or []),
        "mergeRecommendation": merge_recommendation, "confidence": confidence,
        "reviewStatus": review_status,
        "blockingReasons": list(blocking_reasons or []),
    }


def rule_contradiction(contradiction_id, claim_ids, issue_statement, conflict_type,
                       severity, affected_category, interpretations,
                       source_chronology=None, resolution_status="OPEN",
                       completion_path=None, replay_could_help=False,
                       further_source_required=False, origin_record=None):
    _vocab(conflict_type, CONTRADICTION_TYPES, "conflictType")
    _vocab(severity, CONTRADICTION_SEVERITIES, "severity")
    _vocab(affected_category, STRATEGY_DOMAINS, "affectedCategory")
    _req(len(claim_ids) >= 2, "a contradiction needs >=2 claims")
    _req(len(interpretations) >= 2,
         "contradiction %s must offer >=2 interpretations -- offering one is resolving it"
         % contradiction_id)
    return {
        "contradictionId": contradiction_id, "claimIds": sorted(claim_ids),
        "normalizedIssueStatement": issue_statement, "conflictType": conflict_type,
        "severity": severity, "affectedCategory": affected_category,
        "possibleInterpretations": list(interpretations),
        "sourceChronology": list(source_chronology or []),
        "resolutionStatus": resolution_status,
        "recommendedCompletionPath": completion_path,
        "replayCouldHelp": bool(replay_could_help),
        "furtherSourceAcquisitionRequired": bool(further_source_required),
        "originRecord": origin_record,
    }


def knowledge_gap(gap_id, domain, gap, evidence, impact, completion_path,
                  priority="MEDIUM", blocking=False):
    _vocab(domain, STRATEGY_DOMAINS, "domain")
    _req(priority in ("LOW", "MEDIUM", "HIGH", "CRITICAL"), "bad priority")
    _req(bool(completion_path), "gap %s must state a completion path" % gap_id)
    return {"gapId": gap_id, "domain": domain, "gap": gap, "evidence": evidence,
            "impact": impact, "completionPath": completion_path,
            "priority": priority, "blocking": bool(blocking)}


# --- NormalizationDecision / HumanReviewState -------------------------------

def normalization_decision(decision_id, rule_id, source_claims_used,
                           claims_excluded, duplicate_handling,
                           contradiction_handling, meaning_retained,
                           assumptions_avoided, unresolved_elements, confidence,
                           determinism_rationale, requirement_rationale,
                           draft_rationale):
    """The audit trail for one normalization. Every field is mandatory: a rule
    whose construction cannot be explained is not reviewable, and this milestone's
    entire output is meant for review."""
    for name, val in (("meaningRetained", meaning_retained),
                      ("determinismRationale", determinism_rationale),
                      ("requirementRationale", requirement_rationale),
                      ("draftRationale", draft_rationale)):
        _req(bool(val), "normalization decision %s missing %s" % (decision_id, name))
    _vocab(confidence, CONFIDENCE_LEVELS, "confidence")
    return {
        "decisionId": decision_id, "ruleId": rule_id,
        "sourceClaimsUsed": list(source_claims_used),
        "claimsExcluded": list(claims_excluded or []),
        "duplicateHandling": duplicate_handling,
        "contradictionHandling": contradiction_handling,
        "exactMeaningRetained": meaning_retained,
        "assumptionsAvoided": list(assumptions_avoided or []),
        "unresolvedElements": list(unresolved_elements or []),
        "confidence": confidence,
        "determinismRationale": determinism_rationale,
        "requirementRationale": requirement_rationale,
        "draftRationale": draft_rationale,
    }


def human_review_state(review_id, issue, source_evidence, affected_claims,
                       candidate_rule_id, impact, interpretations,
                       recommendation, smallest_decision, priority_rank,
                       status="PENDING_REVIEW"):
    _vocab(status, REVIEW_STATES, "status")
    _req(bool(smallest_decision), "review %s must state the smallest decision" % review_id)
    _req(len(interpretations) >= 2,
         "review %s must offer >=2 interpretations" % review_id)
    return {
        "reviewId": review_id, "issue": issue,
        "sourceEvidence": list(source_evidence), "affectedClaims": list(affected_claims),
        "candidateRuleId": candidate_rule_id, "impact": impact,
        "availableInterpretations": list(interpretations),
        "recommendation": recommendation, "smallestDecisionRequired": smallest_decision,
        "priorityRank": priority_rank, "status": status,
    }


# --- StrategySpecificationDraft ---------------------------------------------

def strategy_rule_reference(rule_id, version, domain):
    """The draft REFERENCES normalized rules; it never copies them. One rule, one
    definition -- a copy would drift from its source the first time either changed."""
    return {"ruleId": rule_id, "version": version, "domain": domain}


def strategy_specification_draft(strategy_id, draft_version, title, rule_references,
                                 domain_reports, provenance_note,
                                 derived_from_educator, status_flags=None):
    _req(bool(strategy_id), "strategyId required")
    _req(strategy_id != "alex_g_sr_v1",
         "the draft must NOT reuse the production strategyId alex_g_sr_v1")
    flags = status_flags or {}
    for f in ("NOT_PRODUCTION", "NOT_IMPLEMENTED", "NOT_REPLAY_VALIDATED",
              "NOT_PAPER_VALIDATED", "PROFITABILITY_UNVALIDATED",
              "ENGINEERING_AUTHORITY_APPROVAL_REQUIRED"):
        flags[f] = True     # not negotiable, and not computed from anything
    draft = {
        "modelVersion": KE_MODEL_VERSION,
        "strategyId": strategy_id, "draftVersion": draft_version, "title": title,
        "statusFlags": flags,
        "provenanceNote": provenance_note,
        "derivedFromEducator": derived_from_educator,
        "ruleReferenceCount": len(rule_references),
        "ruleReferences": list(rule_references),
        "domainReports": list(domain_reports),
        "approvalStatus": "NEEDS_REVIEW",
    }
    draft["draftRuleSetHash"] = gc.content_hash_of(
        sorted([(r["ruleId"], r["version"]) for r in rule_references]))
    return assert_no_unapproved_promotion(draft)


# --- Serialization ----------------------------------------------------------

def dumps(obj):
    return gc.pretty_json(obj)


def write(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    gc.atomic_write_text(path, dumps(obj))
    return path


def loads(text):
    import json
    return json.loads(text)

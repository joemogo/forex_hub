#!/usr/bin/env python3
"""MOGO-019 Step 2 -- the derived research-understanding view.

Pure Python standard library. NO NETWORK ACCESS. READ-ONLY: this module opens
no file for writing, creates no record, and mutates nothing it reads. Running it
twice over an unchanged corpus produces byte-identical output.

WHAT THIS IS

    A DERIVED VIEW over records that already exist -- Claim, EvidenceItem,
    EvidenceClaimLink, EvidenceQuestion, ContradictionRecord, Hypothesis. It
    creates no new record type, no store, no graph and no ontology, and it does
    NOT populate RuleCandidateProposal. It answers, for one strategy corpus:
    what did the educator explicitly say, what did MOGO infer, which rule
    categories have support, which are missing, and what is still ambiguous or
    contradictory.

THE CATEGORY VOCABULARY IS READ FROM THE SCHEMA, NOT RETYPED

    `RULE_CATEGORIES` is loaded from rule-candidate-proposal.schema.json at
    import time. That file is already the repository's authoritative statement
    of which claim types may become a mechanical rule, so restating the list
    here would create a second copy free to drift from it. A claim whose type is
    NOT in that enum is reported under `nonRuleClaims` rather than being forced
    into a category -- the corpus is described, never reshaped to look tidier.

SOURCE FACT AND INFERENCE ARE NEVER SUMMED

    Every evidence item is classified from its EXISTING `directness` value into
    SOURCE_SAID / SOURCE_IMPLIED / MOGO_INFERRED / OPERATOR_OBSERVED /
    UNRESOLVED, and the raw `directness` is carried alongside so the mapping can
    always be audited. The counts are reported per class and never added
    together, because "9 supporting items" would hide whether MOGO or the
    educator said it.

CORPUS ISOLATION FAILS CLOSED

    A corpus is selected by `Claim.traderId`, which is populated on every claim
    in the live library. Questions and contradictions are attached by RESOLVING
    their claim identifiers back to that claim set -- never by string matching,
    which would pull one educator's records into another's view (an ALEX
    question quoting "TJR" is an ALEX question).

    Cross-corpus objects are real and are surfaced, but never as corpus-internal:
    a contradiction between an ALEX claim and a TJR claim appears in the TJR view
    under `crossCorpusContradictions` with the other trader NAMED and the foreign
    claim identified BUT NOT EXPANDED. No foreign claim text, evidence or
    hypothesis ever enters the view.

NOTHING HERE IS A VERDICT

    Sufficiency is reported as explicit facts -- categories present, categories
    missing, unresolved questions, open blocking contradictions. There is no
    score, no percentage and no readiness judgement, and no field in which one
    could be recorded. Presence in a corpus is organization, not validation.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from query_evidence import EvidenceIndex             # noqa: E402

REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
EVIDENCE_ROOT = os.path.join(REPO_ROOT, "docs", "trader-intelligence", "evidence")
_PROPOSAL_SCHEMA = os.path.join(EVIDENCE_ROOT, "schema",
                                "rule-candidate-proposal.schema.json")

VIEW_SCHEMA_VERSION = "mogo.research-understanding-view.v1"


def _rule_categories(schema_path=_PROPOSAL_SCHEMA):
    """The claim types that may become a mechanical rule -- from the schema."""
    with open(schema_path, "r", encoding="utf-8") as handle:
        schema = json.load(handle)
    return tuple(schema["properties"]["claimType"]["enum"])


RULE_CATEGORIES = _rule_categories()

# Existing `directness` values, grouped. The vocabulary is NOT redefined here --
# these are the values evidence-item.schema.json already declares, mapped onto
# the distinction MOGO-019 has to make mechanically visible.
SOURCE_SAID = "SOURCE_SAID"
SOURCE_IMPLIED = "SOURCE_IMPLIED"
MOGO_INFERRED = "MOGO_INFERRED"
OPERATOR_OBSERVED = "OPERATOR_OBSERVED"
UNRESOLVED = "UNRESOLVED"

_DIRECTNESS_CLASS = {
    "direct_explicit": SOURCE_SAID,
    "direct_demonstrated": SOURCE_SAID,
    "indirect_implied": SOURCE_IMPLIED,
    "inferred_from_context": MOGO_INFERRED,
    "derived_from_analysis": MOGO_INFERRED,
    "owner_observation": OPERATOR_OBSERVED,
    "unresolved": UNRESOLVED,
}
EVIDENCE_CLASSES = (SOURCE_SAID, SOURCE_IMPLIED, MOGO_INFERRED,
                    OPERATOR_OBSERVED, UNRESOLVED)


def classify_directness(directness):
    """Map an EXISTING directness value onto the source/inference distinction.

    An unknown or absent value becomes UNRESOLVED rather than being guessed into
    a class -- a provenance gap must look like a provenance gap.
    """
    return _DIRECTNESS_CLASS.get(directness, UNRESOLVED)


class CorpusAmbiguous(Exception):
    """Raised when corpus identity cannot be established. Never resolved by
    picking one -- an ambiguous corpus is refused."""


def _claim_owners(idx):
    return {cid: claim.get("traderId") for cid, claim in idx.claims.items()}


def corpus_view(idx, trader_id):
    """The derived research-understanding view for ONE trader corpus.

    Pure and deterministic: same records and same trader produce byte-identical
    output. Writes nothing.
    """
    if not trader_id or not isinstance(trader_id, str):
        raise CorpusAmbiguous("a trader identifier is required")

    owners = _claim_owners(idx)
    corpus_ids = {cid for cid, owner in owners.items() if owner == trader_id}
    if not corpus_ids:
        raise CorpusAmbiguous(
            "no claims are attributed to trader %r; refusing to build a view "
            "for a corpus that cannot be identified" % (trader_id,))

    # FAIL CLOSED. A claim with no owner cannot be proven to belong to anyone,
    # so its presence makes every corpus boundary in this library unprovable.
    unattributed = sorted(cid for cid, owner in owners.items() if not owner)
    if unattributed:
        raise CorpusAmbiguous(
            "%d claim(s) carry no traderId (e.g. %s); corpus isolation cannot "
            "be proven, so the view is refused rather than guessed"
            % (len(unattributed), unattributed[0]))

    # ── evidence, reached only through this corpus's claims ──
    by_claim = {}
    for link in idx.links.values():
        if link.get("claimId") in corpus_ids:
            by_claim.setdefault(link["claimId"], []).append(link)

    def evidence_for(claim_id):
        rows = []
        for link in sorted(by_claim.get(claim_id, []), key=lambda l: l["linkId"]):
            item = idx.items.get(link["evidenceId"])
            if item is None:
                rows.append({"evidenceId": link["evidenceId"],
                             "present": False,
                             "class": UNRESOLVED,
                             "directness": None,
                             "extractionCertainty": None,
                             "extractionMethod": None,
                             "relationshipType": link.get("relationshipType"),
                             "sourceId": None,
                             "exactExcerpt": None})
                continue
            rows.append({
                "evidenceId": item["evidenceId"],
                "present": True,
                "class": classify_directness(item.get("directness")),
                "directness": item.get("directness"),
                "extractionCertainty": item.get("extractionCertainty"),
                "extractionMethod": item.get("extractionMethod"),
                "relationshipType": link.get("relationshipType"),
                "sourceId": item.get("sourceId"),
                "exactExcerpt": item.get("exactExcerpt"),
            })
        return rows

    # ── questions and contradictions, attached by RESOLVING identifiers ──
    questions_by_claim = {}
    for question in idx.questions.values():
        cid = question.get("claimId")
        if cid in corpus_ids:
            questions_by_claim.setdefault(cid, []).append(question)

    internal_contradictions, cross_contradictions = [], []
    for record in sorted(idx.contradictions.values(),
                         key=lambda r: r["contradictionId"]):
        a, b = record.get("claimAId"), record.get("claimBId")
        in_a, in_b = a in corpus_ids, b in corpus_ids
        if in_a and in_b:
            internal_contradictions.append(record)
        elif in_a or in_b:
            foreign = b if in_a else a
            cross_contradictions.append({
                "contradictionId": record["contradictionId"],
                "corpusClaimId": a if in_a else b,
                # NAMED but NOT EXPANDED: the foreign claim's text, evidence and
                # hypotheses never enter this view.
                "foreignClaimId": foreign,
                "foreignTraderId": owners.get(foreign),
                "contradictionType": record.get("contradictionType"),
                "severity": record.get("severity"),
                "status": record.get("status"),
            })

    # ── hypotheses: corpus-only vs cross-trader, never merged ──
    corpus_hypotheses, cross_hypotheses = [], []
    for hypothesis in sorted(idx.hypotheses.values(),
                             key=lambda h: h["hypothesisId"]):
        cited = list(hypothesis.get("sourceClaimIds") or [])
        if not any(cid in corpus_ids for cid in cited):
            continue
        traders = {owners.get(cid) for cid in cited}
        row = {"hypothesisId": hypothesis["hypothesisId"],
               "status": hypothesis.get("status"),
               "confidence": hypothesis.get("confidence"),
               "statement": hypothesis.get("statement"),
               "sourceClaimIds": cited}
        if traders == {trader_id}:
            corpus_hypotheses.append(row)
        else:
            row["otherTraderIds"] = sorted(t for t in traders if t != trader_id)
            cross_hypotheses.append(row)

    # ── claims, grouped by their EXISTING claimType ──
    categories, non_rule = {}, {}
    for claim_id in sorted(corpus_ids):
        claim = idx.claims[claim_id]
        evidence = evidence_for(claim_id)
        counts = {name: 0 for name in EVIDENCE_CLASSES}
        for row in evidence:
            counts[row["class"]] += 1
        questions = sorted(questions_by_claim.get(claim_id, []),
                           key=lambda q: q["questionId"])
        entry = {
            "claimId": claim_id,
            "claimType": claim.get("claimType"),
            "normalizedClaim": claim.get("normalizedClaim"),
            "claimStatus": claim.get("claimStatus"),
            "confidenceState": claim.get("confidenceState"),
            "traderId": claim.get("traderId"),
            "strategyFamilyId": claim.get("strategyFamilyId"),
            "session": claim.get("session"),
            "timeframe": claim.get("timeframe"),
            "evidence": evidence,
            "evidenceClassCounts": counts,
            # The load-bearing flag: a claim standing only on MOGO's inference
            # is not a thing the educator said, and must never read as one.
            "hasSourceSaidSupport": counts[SOURCE_SAID] > 0,
            "interpretationDependent": (counts[SOURCE_SAID] == 0
                                        and counts[MOGO_INFERRED] > 0),
            "unresolvedQuestions": [
                {"questionId": q["questionId"],
                 "questionType": q.get("questionType"),
                 "questionText": q.get("questionText"),
                 "blockingStatus": q.get("blockingStatus"),
                 "answerStatus": q.get("answerStatus"),
                 "researchStatus": q.get("researchStatus")}
                for q in questions if q.get("answerStatus") != "answered"],
        }
        bucket = (categories if claim.get("claimType") in RULE_CATEGORIES
                  else non_rule)
        bucket.setdefault(claim.get("claimType"), []).append(entry)

    return {
        "schemaVersion": VIEW_SCHEMA_VERSION,
        "traderId": trader_id,
        "lane": "RESEARCH",
        "promotionStatus": "NOT_A_TRADING_RULE",
        "ruleCategories": {name: categories.get(name, [])
                           for name in RULE_CATEGORIES},
        "nonRuleClaims": {name: non_rule[name] for name in sorted(non_rule)},
        "internalContradictions": [
            {"contradictionId": r["contradictionId"],
             "claimAId": r.get("claimAId"), "claimBId": r.get("claimBId"),
             "contradictionType": r.get("contradictionType"),
             "severity": r.get("severity"), "status": r.get("status")}
            for r in internal_contradictions],
        "crossCorpusContradictions": cross_contradictions,
        "corpusHypotheses": corpus_hypotheses,
        "crossTraderHypotheses": cross_hypotheses,
        "sufficiency": _sufficiency(categories, non_rule, internal_contradictions,
                                    cross_contradictions),
    }


def _sufficiency(categories, non_rule, internal_contradictions,
                 cross_contradictions):
    """Facts only. No score, no percentage, no readiness verdict."""
    present, missing = [], []
    for name in RULE_CATEGORIES:
        (present if categories.get(name) else missing).append(name)

    classes = {name: 0 for name in EVIDENCE_CLASSES}
    unresolved_questions, blocking_questions, provenance_gaps = [], [], 0
    for entries in list(categories.values()) + list(non_rule.values()):
        for entry in entries:
            for name in EVIDENCE_CLASSES:
                classes[name] += entry["evidenceClassCounts"][name]
            for question in entry["unresolvedQuestions"]:
                unresolved_questions.append(question["questionId"])
                if question["blockingStatus"] in ("blocks_rule_candidate",
                                                  "blocks_promotion"):
                    blocking_questions.append(question["questionId"])
            provenance_gaps += sum(1 for row in entry["evidence"]
                                   if not row["present"]
                                   or row["directness"] in (None, "unresolved"))

    def blocking(records):
        return sorted(r["contradictionId"] for r in records
                      if r.get("severity") == "blocking"
                      and r.get("status") == "open")

    return {
        "categoriesPresent": present,
        "categoriesMissing": missing,
        "nonRuleClaimTypes": sorted(non_rule),
        "claimCount": sum(len(v) for v in categories.values())
                      + sum(len(v) for v in non_rule.values()),
        "ruleCategoryClaimCount": sum(len(v) for v in categories.values()),
        "nonRuleClaimCount": sum(len(v) for v in non_rule.values()),
        "evidenceClassCounts": classes,
        "unresolvedQuestionCount": len(unresolved_questions),
        "unresolvedQuestionIds": sorted(unresolved_questions),
        "blockingQuestionIds": sorted(set(blocking_questions)),
        "openBlockingInternalContradictionIds": blocking(internal_contradictions),
        "openBlockingCrossCorpusContradictionIds": blocking(cross_contradictions),
        "provenanceGapCount": provenance_gaps,
    }


# ---------------------------------------------------------------------------
# Operator view
# ---------------------------------------------------------------------------

def render(view):
    """Deterministic plain-text rendering. Returns a list of lines."""
    out = ["MOGO research understanding -- DERIVED, READ-ONLY",
           "  trader=%s  lane=%s  promotionStatus=%s"
           % (view["traderId"], view["lane"], view["promotionStatus"])]
    s = view["sufficiency"]
    out.append("  claims=%d (rule-category %d, non-rule %d)"
               % (s["claimCount"], s["ruleCategoryClaimCount"],
                  s["nonRuleClaimCount"]))
    counts = s["evidenceClassCounts"]
    out.append("  evidence by class: " + "  ".join(
        "%s=%d" % (name, counts[name]) for name in EVIDENCE_CLASSES))
    out.append("    (SOURCE_SAID and MOGO_INFERRED are reported separately and "
               "are never summed)")

    out.append("\n  ── RULE CATEGORIES WITH SUPPORT ──")
    for name in RULE_CATEGORIES:
        entries = view["ruleCategories"][name]
        if not entries:
            continue
        out.append("  %s  (%d claim%s)"
                   % (name, len(entries), "" if len(entries) == 1 else "s"))
        for entry in entries:
            flag = ("SOURCE_SAID" if entry["hasSourceSaidSupport"]
                    else ("MOGO_INFERRED ONLY" if entry["interpretationDependent"]
                          else "NO DIRECT SUPPORT"))
            out.append("      %s  [%s]" % (entry["claimId"], flag))
            out.append("        %s" % (entry["normalizedClaim"] or "(no text)",))
            for row in entry["evidence"]:
                out.append("          %s %s/%s  %s"
                           % (row["evidenceId"], row["class"],
                              row["directness"], row["extractionCertainty"]))
            for question in entry["unresolvedQuestions"]:
                out.append("          ? %s %s [%s/%s]"
                           % (question["questionId"], question["questionType"],
                              question["blockingStatus"],
                              question["answerStatus"]))

    out.append("\n  ── CATEGORIES MISSING (no claim of this type exists) ──")
    out.append("  " + (", ".join(s["categoriesMissing"]) or "(none)"))

    out.append("\n  ── CLAIMS OUTSIDE THE RULE VOCABULARY (not forced into a category) ──")
    for name in sorted(view["nonRuleClaims"]):
        out.append("  %s: %d" % (name, len(view["nonRuleClaims"][name])))

    out.append("\n  ── CONTRADICTIONS ──")
    for record in view["internalContradictions"]:
        out.append("  internal  %s %s/%s  %s vs %s"
                   % (record["contradictionId"], record["severity"],
                      record["status"], record["claimAId"], record["claimBId"]))
    for record in view["crossCorpusContradictions"]:
        out.append("  CROSS-CORPUS %s %s/%s  %s vs %s (trader %s) "
                   "-- foreign claim NOT expanded into this corpus"
                   % (record["contradictionId"], record["severity"],
                      record["status"], record["corpusClaimId"],
                      record["foreignClaimId"], record["foreignTraderId"]))

    out.append("\n  ── HYPOTHESES (MOGO interpretation, NOT source fact) ──")
    out.append("  corpus-only=%d  cross-trader=%d (cross-trader are NOT corpus "
               "evidence)" % (len(view["corpusHypotheses"]),
                              len(view["crossTraderHypotheses"])))

    out.append("\n  ── UNRESOLVED ──")
    out.append("  unresolved questions=%d  of which blocking=%d"
               % (s["unresolvedQuestionCount"], len(s["blockingQuestionIds"])))
    out.append("  open BLOCKING contradictions: internal=%s cross-corpus=%s"
               % (s["openBlockingInternalContradictionIds"] or "none",
                  s["openBlockingCrossCorpusContradictionIds"] or "none"))
    out.append("  provenance gaps=%d" % (s["provenanceGapCount"],))
    out.append("\n  This view organizes existing research. It is NOT a claim "
               "that any strategy is")
    out.append("  valid, complete, approved or tradable, and it creates no "
               "rule, hypothesis or")
    out.append("  specification. Categories missing and questions unresolved "
               "are stated as facts.")
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Derived, read-only research-understanding view for one "
                    "strategy corpus (MOGO-019 Step 2).")
    parser.add_argument("--trader", default="TJR")
    parser.add_argument("--evidence-root", default=EVIDENCE_ROOT)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--eligibility", action="store_true",
                        help="derived reconstruction-eligibility (MOGO-019 "
                             "Step 3): what blocks a FUTURE reconstruction "
                             "draft. Informational only -- authorizes nothing.")
    args = parser.parse_args(argv)

    idx = EvidenceIndex.load(args.evidence_root)
    try:
        view = corpus_view(idx, args.trader)
    except CorpusAmbiguous as exc:
        print("REFUSED: %s" % (exc,))
        return 2
    payload = eligibility(view) if args.eligibility else view
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif args.eligibility:
        print("\n".join(render_eligibility(payload)))
    else:
        print("\n".join(render(view)))
    return 0



# ---------------------------------------------------------------------------
# MOGO-019 Step 3 -- reconstruction eligibility, derived and informational
# ---------------------------------------------------------------------------
# Answers ONE question: what specifically prevents this corpus from being
# eligible for a FUTURE mechanical reconstruction draft? It resolves nothing,
# answers no question, and authorizes nothing. Eligibility here is a statement
# about EVIDENCE, never about a strategy's merit.

ELIGIBLE = "ELIGIBLE_FOR_RECONSTRUCTION_DRAFT"
BLOCKED = "BLOCKED"

# Per-category status, in the precedence order they are evaluated.
MISSING = "MISSING"
PROVENANCE_GAP = "PROVENANCE_GAP"
CONFLICTED = "CONFLICTED"
AMBIGUOUS = "AMBIGUOUS"
INFERENCE_ONLY = "INFERENCE_ONLY"
SUPPORTED = "SUPPORTED"

# WHICH CATEGORIES ARE REQUIRED IS NOT INVENTED HERE.
#
# `knowledge_gaps._category_spec()` already assigns a researchPriority to every
# gap category, and marks exactly six `critical` -- each with a stated reason of
# the form "without this, the strategy cannot be replayed/tested/sized". Those
# six ARE the repository's existing statement of mechanical necessity, so this
# table maps them onto the claim types that same module already pairs them with
# (`_related_claims(claims_by_type, "stop_rule")` and friends). A test asserts
# these keys still equal the `critical` set, so the requirement cannot drift
# away from its source.
#
# `execution_timeframe` and `entry_trigger` are both paired with `entry_rule`
# there, and `setup_sequence` with `setup_requirement`; that is why five claim
# types cover six critical categories.
REQUIRED_BY_GAP_CATEGORY = {
    "entry_trigger": "entry_rule",
    "execution_timeframe": "entry_rule",
    "setup_sequence": "setup_requirement",
    "invalidation": "invalidation_rule",
    "stop_placement": "stop_rule",
    "risk_percentage": "risk_rule",
}
REQUIRED_RULE_CATEGORIES = tuple(sorted(set(REQUIRED_BY_GAP_CATEGORY.values())))

_BLOCKING_QUESTION_STATUSES = ("blocks_rule_candidate", "blocks_promotion")

# What a blocker tells a FUTURE research process to look for. Reuses the
# existing questionType/gap vocabulary rather than inventing a second one.
_RESEARCH_NEED = {
    "entry_rule": "an explicit statement of the condition that triggers entry, "
                  "and the timeframe it is executed on",
    "setup_requirement": "an explicit walk-through of what constitutes a valid setup",
    "invalidation_rule": "an explicit statement of what invalidates the setup",
    "stop_rule": "an explicit statement of where the stop is placed",
    "risk_rule": "an explicit statement of risk per trade",
}


def _category_status(entries, blocking_question_ids, conflicted_claim_ids):
    """Deterministic status for one rule category. Precedence is fixed.

    MISSING first (a category with no claims cannot have any other condition),
    then provenance, then conflict, then ambiguity, then inference-only.
    """
    if not entries:
        return MISSING, []
    reasons = []

    broken = [e["claimId"] for e in entries
              if any(not row["present"] or row["directness"] in (None, "unresolved")
                     for row in e["evidence"]) or not e["evidence"]]
    if broken:
        return PROVENANCE_GAP, broken

    conflicted = [e["claimId"] for e in entries
                  if e["claimId"] in conflicted_claim_ids]
    if conflicted:
        return CONFLICTED, conflicted

    ambiguous = [e["claimId"] for e in entries
                 if any(q["questionId"] in blocking_question_ids
                        for q in e["unresolvedQuestions"])]
    if ambiguous:
        return AMBIGUOUS, ambiguous

    if not any(e["hasSourceSaidSupport"] for e in entries):
        # Conservative, and consistent with the blueprint's own separation of
        # statedRiskRules from inferredRiskRules: mechanical behaviour resting
        # only on MOGO's inference is not something the educator said.
        return INFERENCE_ONLY, [e["claimId"] for e in entries]

    return SUPPORTED, reasons


def eligibility(view):
    """Derived reconstruction-eligibility for a Step 2 corpus view. Pure.

    INFORMATIONAL ONLY. `ELIGIBLE_FOR_RECONSTRUCTION_DRAFT` means the evidence
    contains no known blocker -- it does NOT mean a specification is frozen, a
    strategy is approved, or that any backtest, paper or live activity is
    authorized. Each of those remains a separate, explicit operator decision
    that this function cannot make and does not represent.
    """
    # Blocking questions, by identifier -- never by text.
    blocking_questions = {}
    for entries in list(view["ruleCategories"].values()) \
            + list(view["nonRuleClaims"].values()):
        for entry in entries:
            for question in entry["unresolvedQuestions"]:
                if question["blockingStatus"] in _BLOCKING_QUESTION_STATUSES:
                    blocking_questions[question["questionId"]] = dict(
                        question, affectedClaimId=entry["claimId"],
                        affectedCategory=entry["claimType"])
    blocking_question_ids = set(blocking_questions)

    # Blocking contradictions. A cross-corpus record names the foreign claim and
    # its trader for reporting; NO foreign evidence is read or imported.
    blocking_contradictions, conflicted_claim_ids = [], set()
    for record in view["internalContradictions"]:
        if record["severity"] == "blocking" and record["status"] == "open":
            blocking_contradictions.append(dict(record, scope="INTERNAL"))
            conflicted_claim_ids.update({record["claimAId"], record["claimBId"]})
    for record in view["crossCorpusContradictions"]:
        if record["severity"] == "blocking" and record["status"] == "open":
            blocking_contradictions.append(dict(record, scope="CROSS_CORPUS"))
            conflicted_claim_ids.add(record["corpusClaimId"])

    categories, blockers = {}, []
    for name in RULE_CATEGORIES:
        entries = view["ruleCategories"][name]
        status, claim_ids = _category_status(entries, blocking_question_ids,
                                             conflicted_claim_ids)
        required = name in REQUIRED_RULE_CATEGORIES
        categories[name] = {
            "status": status,
            "required": required,
            "claimCount": len(entries),
            "claimIds": [e["claimId"] for e in entries],
            "implicatedClaimIds": claim_ids,
            "sourceSaidClaimCount": sum(1 for e in entries
                                        if e["hasSourceSaidSupport"]),
            "requiredBecause": sorted(
                gap for gap, claim_type in REQUIRED_BY_GAP_CATEGORY.items()
                if claim_type == name),
        }
        if required and status != SUPPORTED:
            blockers.append({
                "blockerType": "REQUIRED_CATEGORY_%s" % (status,),
                "ruleCategory": name,
                "status": status,
                "implicatedClaimIds": claim_ids,
                "requiredBecause": categories[name]["requiredBecause"],
                "researchNeed": _RESEARCH_NEED.get(name),
            })

    for question_id in sorted(blocking_questions):
        question = blocking_questions[question_id]
        blockers.append({
            "blockerType": "BLOCKING_QUESTION",
            "questionId": question_id,
            "questionType": question["questionType"],
            "affectedClaimId": question["affectedClaimId"],
            "ruleCategory": question["affectedCategory"],
            "blockingStatus": question["blockingStatus"],
            "answerStatus": question["answerStatus"],
            "whyItBlocks": "an unanswered question carrying blockingStatus %s "
                           "leaves this claim without one unique mechanical "
                           "reading" % (question["blockingStatus"],),
            "researchNeed": question["questionText"],
        })

    for record in blocking_contradictions:
        blockers.append({
            "blockerType": "BLOCKING_CONTRADICTION",
            "contradictionId": record["contradictionId"],
            "scope": record["scope"],
            "severity": record["severity"],
            "status": record["status"],
            "corpusClaimId": record.get("corpusClaimId")
                             or record.get("claimAId"),
            "foreignClaimId": record.get("foreignClaimId"),
            "foreignTraderId": record.get("foreignTraderId"),
            "whyItBlocks": "two claims cannot both hold without qualification, "
                           "so no single mechanical reading exists",
            "researchNeed": "an operator decision or further evidence "
                            "qualifying the scope of the conflicting claims",
        })

    return {
        "schemaVersion": ELIGIBILITY_SCHEMA_VERSION,
        "traderId": view["traderId"],
        "lane": "RESEARCH",
        "promotionStatus": "NOT_A_TRADING_RULE",
        "eligibility": BLOCKED if blockers else ELIGIBLE,
        "informationalOnly": True,
        "meaning": "Eligibility describes the EVIDENCE only. It authorizes no "
                   "reconstruction, no specification freeze, no backtest, no "
                   "paper trading and no live trading; each remains a separate "
                   "explicit operator decision.",
        "requiredRuleCategories": list(REQUIRED_RULE_CATEGORIES),
        "requiredCategorySource": "knowledge_gaps._category_spec() "
                                  "researchPriority == 'critical'",
        "categories": categories,
        "blockers": blockers,
        "blockerCount": len(blockers),
    }


ELIGIBILITY_SCHEMA_VERSION = "mogo.reconstruction-eligibility.v1"


def render_eligibility(result):
    out = ["MOGO reconstruction eligibility -- DERIVED, READ-ONLY, INFORMATIONAL",
           "  trader=%s  result=%s  blockers=%d"
           % (result["traderId"], result["eligibility"], result["blockerCount"]),
           "  required categories: %s" % (", ".join(result["requiredRuleCategories"]),),
           "  required-category source: %s" % (result["requiredCategorySource"],),
           "", "  ── CATEGORY STATUS ──"]
    for name in RULE_CATEGORIES:
        row = result["categories"][name]
        out.append("  %-24s %-15s %s claims=%d sourceSaid=%d"
                   % (name, row["status"],
                      "[REQUIRED]" if row["required"] else "[optional]",
                      row["claimCount"], row["sourceSaidClaimCount"]))
    out.append("\n  ── BLOCKERS ──")
    if not result["blockers"]:
        out.append("  (none)")
    for blocker in result["blockers"]:
        head = blocker["blockerType"]
        detail = (blocker.get("ruleCategory") or blocker.get("contradictionId")
                  or blocker.get("questionId") or "")
        out.append("  %-32s %s" % (head, detail))
        for key in ("questionId", "contradictionId", "scope", "affectedClaimId",
                    "foreignClaimId", "foreignTraderId", "status"):
            if blocker.get(key):
                out.append("      %-16s %s" % (key, blocker[key]))
        if blocker.get("whyItBlocks"):
            out.append("      why             %s" % (blocker["whyItBlocks"],))
        if blocker.get("researchNeed"):
            out.append("      research need   %s" % (blocker["researchNeed"],))
    out.append("\n  " + result["meaning"])
    return out

if __name__ == "__main__":
    sys.exit(main())

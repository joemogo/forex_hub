#!/usr/bin/env python3
"""MOGO-019 Step 8 -- exception-queue triage and review packets.

Pure Python standard library. NO NETWORK ACCESS. READ-ONLY: writes nothing,
creates no record, adjudicates nothing. Deterministic.

WHAT THIS IS

    A composition of three views that already exist -- the Step 7 Rule-2
    conformance report, the Step 2 corpus view and the Step 3 eligibility
    predicate. It adds no new analysis of the evidence itself. It answers one
    question about work already done:

        of the claims Step 7 flagged, which ones are worth a human's time,
        and in what order?

    It optimizes for FEWER WASTED REVIEWS, never for fewer flags. Nothing here
    removes a claim from the queue on a guess: a flag is downgraded to
    LIKELY_MECHANICAL_FALSE_POSITIVE only when the reason can be DEMONSTRATED
    from the text, and even then the claim stays in the queue at lower priority.

WHAT IT DOES NOT DO

    It does not adjudicate a claim, answer an EvidenceQuestion, settle a
    contradiction, create a proposal, or change any eligibility result. It does
    not alter the meaning of CLEAN_MECHANICAL_MATCH, which continues to mean
    only "no discrepancy detectable by the Step 7 checks" and never approval.

THE LOAD-BEARING FINDING THIS ENCODES

    Blockers derive from EvidenceQuestions and ContradictionRecords. A Rule-2
    review decides whether a PARAPHRASE overreached. Those are different
    questions, so reviewing a flagged claim can CLARIFY a blocker but cannot
    ANSWER one. `REVIEW_CAN_RESOLVE` is defined and computed, and on the current
    corpus it is correctly empty -- that is a result, not an omission.
"""

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import research_understanding as ru                  # noqa: E402
import rule_conformance as rc                        # noqa: E402
from query_evidence import EvidenceIndex             # noqa: E402

TRIAGE_SCHEMA_VERSION = "mogo.exception-triage.v1"

CRITICAL_RULE_MEANING = "CRITICAL_RULE_MEANING"
BLOCKER_RELEVANT = "BLOCKER_RELEVANT"
MODAL_OR_QUANTIFIER_ESCALATION = "MODAL_OR_QUANTIFIER_ESCALATION"
NUMERIC_OR_TIME_CHANGE = "NUMERIC_OR_TIME_CHANGE"
INSTRUMENT_OR_DIRECTION_CHANGE = "INSTRUMENT_OR_DIRECTION_CHANGE"
LIKELY_MECHANICAL_FALSE_POSITIVE = "LIKELY_MECHANICAL_FALSE_POSITIVE"
GENERAL_SEMANTIC_REVIEW = "GENERAL_SEMANTIC_REVIEW"

# Review order. A fixed position in a list, never a computed number: the queue
# must be reproducible and explainable without tracing arithmetic.
PRIORITY_ORDER = (
    BLOCKER_RELEVANT,
    CRITICAL_RULE_MEANING,
    MODAL_OR_QUANTIFIER_ESCALATION,
    NUMERIC_OR_TIME_CHANGE,
    INSTRUMENT_OR_DIRECTION_CHANGE,
    GENERAL_SEMANTIC_REVIEW,
    LIKELY_MECHANICAL_FALSE_POSITIVE,
)
_RANK = {name: index for index, name in enumerate(PRIORITY_ORDER)}

REVIEW_CAN_RESOLVE = "REVIEW_CAN_RESOLVE"
REVIEW_CAN_CLARIFY_BUT_NOT_RESOLVE = "REVIEW_CAN_CLARIFY_BUT_NOT_RESOLVE"
REVIEW_CANNOT_RESOLVE = "REVIEW_CANNOT_RESOLVE"

# Ordinal words whose digit form is the SAME fact. Used ONLY to demonstrate a
# false positive, never to suppress a flag silently.
_ORDINALS = {"first": "1", "second": "2", "third": "3", "fourth": "4",
             "fifth": "5", "one": "1", "two": "2", "three": "3", "four": "4",
             "five": "5"}


def _demonstrable_false_positive(row):
    """Reasons a flag is demonstrably mechanical, each PROVED from the text.

    Returns a list of (token, reason). An empty list means nothing could be
    demonstrated -- which is NOT the same as "the flag is real", and the claim
    stays in the queue either way.
    """
    claim_text = (row.get("normalizedClaim") or "").casefold()
    excerpts = " ".join((entry.get("exactExcerpt") or "").casefold()
                        for entry in row["supportingEvidence"])
    shown = []
    for name, tokens in row["discrepancies"].items():
        for token in tokens:
            if name == rc.REVIEW_NUMERIC:
                # A MOGO-authored sequence label: the number labels the step, it
                # is not a quantity the source stated.
                if re.search(r"\bstep\s*%s\b" % re.escape(token), claim_text):
                    shown.append((token, "MOGO 'Step N' sequence label"))
                    continue
                word = next((w for w, digit in _ORDINALS.items()
                             if digit == token and re.search(r"\b%s\b" % w, excerpts)),
                            None)
                if word:
                    shown.append((token, "ordinal word %r present in excerpt" % word))
                    continue
            if name == rc.REVIEW_TIME:
                stem = token.rstrip("sly").rstrip("i")
                if len(stem) > 2 and re.search(r"\b%s" % re.escape(stem), excerpts):
                    shown.append((token, "morphological variant of %r in excerpt" % stem))
    return shown


def triage_row(row, rule_categories, required_categories):
    """Triage classes for ONE flagged claim. Pure."""
    classes = []
    claim_type = row.get("claimType")
    flagged = set(row["flaggedClasses"])

    if row["blockingQuestionIds"] or row["contradictionIds"]:
        classes.append(BLOCKER_RELEVANT)
    if claim_type in rule_categories:
        classes.append(CRITICAL_RULE_MEANING)
    if rc.REVIEW_QUANTIFIER in flagged:
        classes.append(MODAL_OR_QUANTIFIER_ESCALATION)
    if flagged & {rc.REVIEW_NUMERIC, rc.REVIEW_TIME}:
        classes.append(NUMERIC_OR_TIME_CHANGE)
    if flagged & {rc.REVIEW_INSTRUMENT, rc.REVIEW_DIRECTION}:
        classes.append(INSTRUMENT_OR_DIRECTION_CHANGE)

    demonstrated = _demonstrable_false_positive(row)
    # A claim is only downgraded when EVERY flagged token was demonstrated
    # mechanical. One unexplained token keeps the claim in the real queue.
    total_tokens = sum(len(v) for v in row["discrepancies"].values())
    fully_explained = bool(demonstrated) and len(demonstrated) == total_tokens
    if fully_explained:
        classes.append(LIKELY_MECHANICAL_FALSE_POSITIVE)
    if not classes:
        classes.append(GENERAL_SEMANTIC_REVIEW)

    # Priority is the strongest (lowest-rank) class present, EXCEPT that a fully
    # demonstrated false positive sinks to the bottom unless it also touches a
    # blocker -- a blocker-relevant claim is never demoted on formatting grounds.
    if fully_explained and BLOCKER_RELEVANT not in classes:
        priority = LIKELY_MECHANICAL_FALSE_POSITIVE
    else:
        priority = min((c for c in classes), key=lambda c: _RANK[c])

    return {
        "claimId": row["claimId"],
        "traderId": row["traderId"],
        "claimType": claim_type,
        "isRuleCategory": claim_type in rule_categories,
        "isRequiredCategory": claim_type in required_categories,
        "normalizedClaim": row["normalizedClaim"],
        "classification": row["classification"],
        "flaggedClasses": row["flaggedClasses"],
        "discrepancies": row["discrepancies"],
        "supportingEvidence": row["supportingEvidence"],
        "blockingQuestionIds": row["blockingQuestionIds"],
        "contradictionIds": row["contradictionIds"],
        "triageClasses": sorted(classes),
        "reviewPriority": priority,
        "demonstratedMechanicalReasons": [
            {"token": token, "reason": reason} for token, reason in demonstrated],
    }


def blocker_impact(eligibility_result, view, flagged_ids):
    """For each Step 3 blocker: could reviewing a flagged claim resolve it?

    A blocker exists because of an unanswered EvidenceQuestion, an open
    ContradictionRecord, or an absent/limited claim set. A Rule-2 review decides
    only whether a paraphrase overreached. It therefore CANNOT answer a
    question, settle a contradiction, or bring a missing claim into existence --
    so `REVIEW_CAN_RESOLVE` is reachable only if a blocker's entire cause is the
    claim text itself, which the current model never produces.
    """
    rows = []
    for blocker in eligibility_result["blockers"]:
        kind = blocker["blockerType"]
        category = blocker.get("ruleCategory")
        if kind.startswith("REQUIRED_CATEGORY_"):
            related = [e["claimId"] for e in view["ruleCategories"].get(category, [])]
            identifier = "REQUIRED_CATEGORY|%s" % (category,)
        elif kind == "BLOCKING_QUESTION":
            related = [blocker["affectedClaimId"]]
            identifier = blocker["questionId"]
        else:
            related = [blocker.get("corpusClaimId")]
            identifier = blocker["contradictionId"]
        related = [c for c in related if c]
        hit = sorted(set(related) & flagged_ids)

        if kind == "REQUIRED_CATEGORY_MISSING":
            impact, why = (REVIEW_CANNOT_RESOLVE,
                           "no claim of this type exists; there is nothing to review")
        elif hit:
            impact, why = (REVIEW_CAN_CLARIFY_BUT_NOT_RESOLVE,
                           "review can establish whether the paraphrase overreached, "
                           "but cannot answer the question or settle the conflict")
        else:
            impact, why = (REVIEW_CANNOT_RESOLVE,
                           "no related claim is flagged; nothing for Rule-2 review "
                           "to examine")

        rows.append({
            "blockerId": identifier,
            "blockerType": kind,
            "ruleCategory": category,
            "requiredCategory": category in ru.REQUIRED_RULE_CATEGORIES,
            "status": blocker.get("status"),
            "relatedClaimIds": related,
            "flaggedClaimIds": hit,
            "cleanClaimIds": sorted(set(related) - flagged_ids),
            "reviewImpact": impact,
            "why": why,
            "stillRequiresNewEvidence": kind != "BLOCKING_CONTRADICTION",
            "stillRequiresTraderClarification":
                kind == "BLOCKING_QUESTION" or kind.startswith("REQUIRED_CATEGORY_"),
            "stillRequiresOperatorRuling": kind == "BLOCKING_CONTRADICTION",
        })
    return rows


def triage(idx, trader_id):
    """The full triage view for ONE corpus. A READ. Writes nothing."""
    conformance = rc.conformance_report(idx, trader_id)
    view = ru.corpus_view(idx, trader_id)
    eligibility_result = ru.eligibility(view)

    rule_categories = set(ru.RULE_CATEGORIES)
    required = set(ru.REQUIRED_RULE_CATEGORIES)
    flagged_rows = [r for r in conformance["claims"]
                    if r["classification"] != rc.CLEAN]
    items = [triage_row(row, rule_categories, required) for row in flagged_rows]
    items.sort(key=lambda i: (_RANK[i["reviewPriority"]], i["claimId"]))
    flagged_ids = {i["claimId"] for i in items}

    counts = {}
    for item in items:
        counts[item["reviewPriority"]] = counts.get(item["reviewPriority"], 0) + 1
    class_counts = {}
    for item in items:
        for name in item["triageClasses"]:
            class_counts[name] = class_counts.get(name, 0) + 1

    impact = blocker_impact(eligibility_result, view, flagged_ids)
    # The MINIMUM set whose review could change eligibility: only claims on
    # blockers where review can do anything at all.
    minimum = sorted({claim_id for row in impact
                      if row["reviewImpact"] != REVIEW_CANNOT_RESOLVE
                      for claim_id in row["flaggedClaimIds"]})

    total = conformance["totalClaims"]
    rule_flagged = [i for i in items if i["isRuleCategory"]]
    return {
        "schemaVersion": TRIAGE_SCHEMA_VERSION,
        "traderId": trader_id,
        "lane": "RESEARCH",
        "promotionStatus": "NOT_A_TRADING_RULE",
        "adjudicatesNothing": True,
        "cleanMeaning": conformance["cleanMeaning"],
        "totalClaims": total,
        "cleanCount": conformance["cleanCount"],
        "flaggedCount": len(items),
        "ruleCategoryFlaggedCount": len(rule_flagged),
        "requiredCategoryFlaggedCount": sum(1 for i in items
                                            if i["isRequiredCategory"]),
        "blockerRelevantCount": sum(1 for i in items
                                    if BLOCKER_RELEVANT in i["triageClasses"]),
        "demonstrableFalsePositiveCount":
            counts.get(LIKELY_MECHANICAL_FALSE_POSITIVE, 0),
        "countsByPriority": counts,
        "countsByTriageClass": class_counts,
        "items": items,
        "blockerImpact": impact,
        "minimumReviewSet": minimum,
        "eligibility": eligibility_result["eligibility"],
        "blockerCount": eligibility_result["blockerCount"],
    }


def render_packets(result, limit=None):
    """The human review packet. One block per claim needing judgment."""
    out = ["MOGO exception triage -- DERIVED, READ-ONLY, ADJUDICATES NOTHING",
           "  trader=%s  claims=%d  clean=%d  flagged=%d"
           % (result["traderId"], result["totalClaims"], result["cleanCount"],
              result["flaggedCount"]),
           "  CLEAN means: %s" % (result["cleanMeaning"],),
           "", "  ── REVIEW PRIORITY ──"]
    for name in PRIORITY_ORDER:
        out.append("  %-34s %d" % (name, result["countsByPriority"].get(name, 0)))
    out.append("\n  rule-category flagged=%d  required-category flagged=%d  "
               "blocker-relevant=%d"
               % (result["ruleCategoryFlaggedCount"],
                  result["requiredCategoryFlaggedCount"],
                  result["blockerRelevantCount"]))
    out.append("  minimum review set (could change eligibility): %d claims"
               % (len(result["minimumReviewSet"]),))

    out.append("\n  ── REVIEW PACKETS ──")
    for index, item in enumerate(result["items"], start=1):
        if limit and index > limit:
            out.append("  ... %d more" % (len(result["items"]) - limit,))
            break
        out.append("")
        out.append("  [%d] %s   priority=%s" % (index, item["claimId"],
                                                item["reviewPriority"]))
        out.append("      STRATEGY IMPACT : claimType=%s%s%s"
                   % (item["claimType"],
                      "  [RULE CATEGORY]" if item["isRuleCategory"] else "",
                      "  [REQUIRED]" if item["isRequiredCategory"] else ""))
        if item["blockingQuestionIds"]:
            out.append("                        blocking questions: %s"
                       % (", ".join(item["blockingQuestionIds"]),))
        if item["contradictionIds"]:
            out.append("                        open contradictions: %s"
                       % (", ".join(item["contradictionIds"]),))
        for entry in item["supportingEvidence"]:
            out.append("      SOURCE          : %r" % (entry["exactExcerpt"],))
            out.append("                        (%s  %s/%s)"
                       % (entry["evidenceId"], entry["directness"],
                          entry["extractionCertainty"]))
        out.append("      MOGO INTERPRETATION: %s" % (item["normalizedClaim"],))
        for name, tokens in sorted(item["discrepancies"].items()):
            out.append("      WHY FLAGGED     : %s -- %s absent from every "
                       "supporting excerpt"
                       % (name, ", ".join(repr(t) for t in tokens)))
        for shown in item["demonstratedMechanicalReasons"]:
            out.append("                        (demonstrated mechanical: %r -- %s)"
                       % (shown["token"], shown["reason"]))
        out.append("      HUMAN DECISION  : [ ] faithful   [ ] not faithful   "
                   "[ ] uncertain / needs more evidence")

    out.append("\n  ── BLOCKER IMPACT ──")
    for row in result["blockerImpact"]:
        out.append("  %-34s %-36s %s"
                   % (row["blockerId"], row["reviewImpact"],
                      "flagged=%d" % len(row["flaggedClaimIds"])))
    out.append("\n  Reviewing a flagged claim decides whether a PARAPHRASE "
               "overreached. It cannot")
    out.append("  answer an EvidenceQuestion, settle a contradiction, or create "
               "a missing claim.")
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Exception-queue triage and review packets (MOGO-019 "
                    "Step 8). Read-only. Adjudicates nothing.")
    parser.add_argument("--trader", default="TJR")
    parser.add_argument("--evidence-root", default=rc.EVIDENCE_ROOT)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args(argv)

    idx = EvidenceIndex.load(args.evidence_root)
    try:
        result = triage(idx, args.trader)
    except (ValueError, ru.CorpusAmbiguous) as exc:
        print("REFUSED: %s" % (exc,))
        return 2
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("\n".join(render_packets(result, limit=args.limit)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

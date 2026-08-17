#!/usr/bin/env python3
"""MOGO-022 -- decision-difference classification over an existing ContradictionRecord.

Pure Python standard library. NO NETWORK ACCESS. READ-ONLY by default: derives a
view, adjudicates nothing, promotes nothing, creates no Claim, Link, Hypothesis
or Proposal. Deterministic. Writing is opt-in and lands only in
`evidence/reports/`, which already holds DERIVED reports, never primary records.

WHAT THIS IS

    The thin missing layer over machinery that already exists. The corpus
    already records THAT two positions disagree (`ContradictionRecord`, 16 of
    them, with `contradictionType` describing the SHAPE of the disagreement:
    DIRECTIONAL, DEFINITIONAL, NUMERIC_THRESHOLD ...). What no record answers is
    the operational question:

        Why did one decider take this trade and the other not --
        and is that difference a matter of RULE, of DATA, of TIMING,
        of IMPLEMENTATION, or is any explanation of it MOGO's own reading?

    `contradictionType` answers "how do the two statements clash?".
    `classification` here answers "what would have to change for them to agree?".
    They are different questions and this module does not conflate them: the
    contradiction record is an INPUT, quoted, never edited or superseded.

WHAT IT DOES NOT DO

    It does not resolve a contradiction, change a claim's status, alter
    eligibility, propose a rule, or grant permission to change strategy rules. A
    human/MOGO disagreement is research evidence. `promotionStatus` is pinned to
    NOT_A_TRADING_RULE on every record this module can produce.

THE LOAD-BEARING CONSERVATISM

    RULE_DIFFERENCE, DATA_DIFFERENCE and TIMING_DIFFERENCE each require a
    DEMONSTRABLE dimension -- a scope field that BOTH sides state and on which
    they differ (or agree, for RULE_DIFFERENCE). When neither side states the
    dimension, the difference is real but nothing in the corpus separates the two
    positions, so any account of why they differ is an inference MOGO supplied.
    That is INTERPRETATION_HYPOTHESIS, and it is the honest answer, not a
    fallback for "unclassified".

    INSUFFICIENT_EVIDENCE dominates everything: if either side cannot be walked
    back to a verbatim excerpt attributable to its actor (SPEC-provenance P6-P10),
    no classification is offered at all. Fail closed.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import research_understanding as ru                  # noqa: E402
from query_evidence import EvidenceIndex             # noqa: E402

EVIDENCE_ROOT = ru.EVIDENCE_ROOT
DECISION_DIFFERENCE_SCHEMA_VERSION = "mogo.decision-difference.v1"

# The six classifications. Not a severity ordering -- a taxonomy of CAUSE.
IMPLEMENTATION_DIFFERENCE = "IMPLEMENTATION_DIFFERENCE"
RULE_DIFFERENCE = "RULE_DIFFERENCE"
DATA_DIFFERENCE = "DATA_DIFFERENCE"
TIMING_DIFFERENCE = "TIMING_DIFFERENCE"
INTERPRETATION_HYPOTHESIS = "INTERPRETATION_HYPOTHESIS"
INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"

CLASSIFICATIONS = (
    INSUFFICIENT_EVIDENCE,
    DATA_DIFFERENCE,
    TIMING_DIFFERENCE,
    IMPLEMENTATION_DIFFERENCE,
    RULE_DIFFERENCE,
    INTERPRETATION_HYPOTHESIS,
)

CLASSIFICATION_MEANING = {
    INSUFFICIENT_EVIDENCE:
        "At least one position cannot be walked back to a verbatim excerpt "
        "attributable to its actor. No cause is offered.",
    DATA_DIFFERENCE:
        "Both sides state a market-input dimension and the stated values differ: "
        "the two deciders were not looking at the same input.",
    TIMING_DIFFERENCE:
        "Both sides state a time dimension and the stated values differ, or the "
        "recorded contradiction is TEMPORAL_DRIFT: same rule, observed at "
        "different moments.",
    IMPLEMENTATION_DIFFERENCE:
        "Same rule intent, different mechanization -- a threshold or parameter "
        "differs while the governing rule category is shared.",
    RULE_DIFFERENCE:
        "Both positions are rule-bearing, share a demonstrably stated scope, and "
        "still disagree: the rules themselves differ.",
    INTERPRETATION_HYPOTHESIS:
        "The disagreement is real and both sides are provenance-complete, but no "
        "dimension either actor STATED separates them. Any reconciliation is "
        "MOGO's reading, not either actor's statement.",
}

# Scope dimensions, split by what a difference on them would MEAN. Names are the
# existing authoritative Claim fields (claim.schema.json) -- no new vocabulary.
DATA_DIMENSIONS = ("marketSymbol", "marketCondition")
TIMING_DIMENSIONS = ("timeframe", "session")
SCOPE_DIMENSIONS = DATA_DIMENSIONS + TIMING_DIMENSIONS + ("strategyFamilyId",)

# Directness classes that attribute a statement to its ACTOR. A position resting
# only on MOGO_INFERRED or UNRESOLVED evidence is not the actor's position.
_ATTRIBUTABLE = (ru.SOURCE_SAID, ru.SOURCE_IMPLIED, ru.OPERATOR_OBSERVED)

_SUPPORTING = ("supports", "exemplifies")


class DecisionDifferenceRefused(Exception):
    """Raised when the inputs cannot be identified. Never resolved by guessing."""


def _scope_of(claim):
    """The authoritative, queryable scope tuple. Free-form `scope` is ignored on
    purpose: claim.schema.json names the flat fields as authoritative."""
    return {name: claim.get(name) for name in SCOPE_DIMENSIONS}


def build_position(idx, claim_id, side):
    """One side of a decision difference, walked back to source bytes.

    Pure with respect to `idx`. Never invents a field; every value is copied from
    an existing record or derived from one by a named rule.
    """
    claim = idx.claims.get(claim_id)
    if claim is None:
        return {
            "side": side, "claimId": claim_id, "actorId": None, "claimType": None,
            "isRuleCategory": False, "normalizedClaim": None,
            "claimStatus": None, "decisionScope": {name: None for name in SCOPE_DIMENSIONS},
            "statedDimensions": [], "evidence": [], "evidenceIds": [], "sourceIds": [],
            "provenanceComplete": False,
            "provenanceGaps": ["CLAIM_NOT_IN_CORPUS"],
        }

    evidence = []
    gaps = []
    for link in sorted(idx.links_for_claim(claim_id),
                       key=lambda l: (l.get("evidenceId") or "")):
        if link.get("relationshipType") not in _SUPPORTING:
            continue
        item = idx.items.get(link.get("evidenceId"))
        if item is None:
            gaps.append("LINK_TO_MISSING_EVIDENCE|%s" % (link.get("evidenceId"),))
            continue
        directness_class = ru.classify_directness(item.get("directness"))
        entry = {
            "evidenceId": item["evidenceId"],
            "relationshipType": link["relationshipType"],
            "exactExcerpt": item.get("exactExcerpt"),
            "sourceLocator": item.get("sourceLocator"),
            "sourceId": item.get("sourceId"),
            "evidenceType": item.get("evidenceType"),
            "directness": item.get("directness"),
            "directnessClass": directness_class,
            "extractionCertainty": item.get("extractionCertainty"),
        }
        if not entry["exactExcerpt"]:
            gaps.append("NO_VERBATIM_EXCERPT|%s" % (entry["evidenceId"],))
        if not entry["sourceLocator"]:
            gaps.append("NO_SOURCE_LOCATOR|%s" % (entry["evidenceId"],))
        if not entry["sourceId"]:
            gaps.append("NO_SOURCE_ID|%s" % (entry["evidenceId"],))
        evidence.append(entry)

    if not evidence:
        gaps.append("NO_SUPPORTING_EVIDENCE")
    elif not any(e["directnessClass"] in _ATTRIBUTABLE for e in evidence):
        # Every supporting item is MOGO's own inference. The position exists, but
        # it is not the ACTOR's position, so it cannot explain the actor's trade.
        gaps.append("NOT_ATTRIBUTABLE_TO_ACTOR")

    scope = _scope_of(claim)
    return {
        "side": side,
        "claimId": claim_id,
        "actorId": claim.get("traderId"),
        "claimType": claim.get("claimType"),
        "isRuleCategory": claim.get("claimType") in ru.RULE_CATEGORIES,
        "normalizedClaim": claim.get("normalizedClaim"),
        "claimStatus": claim.get("claimStatus"),
        "decisionScope": scope,
        "statedDimensions": sorted(k for k, v in scope.items() if v is not None),
        "evidence": evidence,
        "evidenceIds": sorted(e["evidenceId"] for e in evidence),
        "sourceIds": sorted({e["sourceId"] for e in evidence if e["sourceId"]}),
        "provenanceComplete": not gaps,
        "provenanceGaps": sorted(set(gaps)),
    }


def _shared_dimensions(a, b, names):
    """Dimensions BOTH sides state, split into differing and agreeing."""
    differ, agree = [], []
    for name in names:
        left, right = a["decisionScope"].get(name), b["decisionScope"].get(name)
        if left is None or right is None:
            continue
        (differ if left != right else agree).append(
            {"dimension": name, "a": left, "b": right})
    return differ, agree


def classify(position_a, position_b, contradiction_type=None):
    """The decision procedure. Ordered, mechanical, and self-documenting.

    Returns (classification, basis) where `basis` lists every test that ran, in
    order, with what it found -- so a reader can audit the verdict without
    re-deriving it. Pure: takes positions, touches no index.
    """
    basis = []

    def note(test, fired, detail):
        basis.append({"test": test, "fired": fired, "detail": detail})
        return fired

    # 1. Fail closed. Dominates every other signal.
    gaps = sorted(set(position_a["provenanceGaps"]) | set(position_b["provenanceGaps"]))
    if note("PROVENANCE_COMPLETE_BOTH_SIDES", bool(gaps),
            "gaps: %s" % (", ".join(gaps) if gaps else "none",)):
        return INSUFFICIENT_EVIDENCE, basis

    data_differ, _ = _shared_dimensions(position_a, position_b, DATA_DIMENSIONS)
    time_differ, _ = _shared_dimensions(position_a, position_b, TIMING_DIMENSIONS)
    _, scope_agree = _shared_dimensions(position_a, position_b, SCOPE_DIMENSIONS)

    # 2. Different inputs beat everything downstream: two deciders looking at
    #    different data are not disagreeing about a rule at all.
    if note("STATED_DATA_DIMENSION_DIFFERS", bool(data_differ),
            json.dumps(data_differ, sort_keys=True)):
        return DATA_DIFFERENCE, basis

    # 3. Same inputs, different moment.
    temporal = contradiction_type == "TEMPORAL_DRIFT"
    if note("STATED_TIMING_DIMENSION_DIFFERS_OR_TEMPORAL_DRIFT",
            bool(time_differ) or temporal,
            json.dumps({"differing": time_differ, "contradictionType": contradiction_type},
                       sort_keys=True)):
        return TIMING_DIFFERENCE, basis

    # 4. Same rule intent, different number. The recorded contradiction type is
    #    what makes this demonstrable -- MOGO does not re-parse the text for it.
    threshold = contradiction_type == "NUMERIC_THRESHOLD"
    both_rule = position_a["isRuleCategory"] and position_b["isRuleCategory"]
    if note("NUMERIC_THRESHOLD_ON_RULE_BEARING_POSITIONS",
            threshold and both_rule,
            json.dumps({"contradictionType": contradiction_type,
                        "bothRuleCategory": both_rule}, sort_keys=True)):
        return IMPLEMENTATION_DIFFERENCE, basis

    # 5. Rule-bearing on BOTH sides and a scope dimension both sides state and
    #    agree on. Without that shared stated scope the two may simply be talking
    #    about different unstated contexts -- which is test 6, not this one.
    if note("BOTH_RULE_BEARING_WITH_SHARED_STATED_SCOPE",
            both_rule and bool(scope_agree),
            json.dumps({"bothRuleCategory": both_rule, "agreeingDimensions": scope_agree},
                       sort_keys=True)):
        return RULE_DIFFERENCE, basis

    # 6. Real, auditable, and unexplained by anything either actor stated.
    note("NO_STATED_DIMENSION_SEPARATES_THE_POSITIONS", True,
         json.dumps({"statedByA": position_a["statedDimensions"],
                     "statedByB": position_b["statedDimensions"],
                     "bothRuleCategory": both_rule}, sort_keys=True))
    return INTERPRETATION_HYPOTHESIS, basis


def _difference_id(contradiction_id):
    """XDD|{YYYYMMDD}|{seq}, derived from the contradiction it explains so the
    two are trivially cross-referenced and the id is never invented."""
    parts = contradiction_id.split("|")
    if len(parts) != 3 or parts[0] != "XCONTRA":
        raise DecisionDifferenceRefused(
            "unrecognized contradictionId %r" % (contradiction_id,))
    return "XDD|%s|%s" % (parts[1], parts[2])


def decision_difference(idx, contradiction_id):
    """The full decision-difference view for ONE recorded contradiction. A READ."""
    record = idx.contradictions.get(contradiction_id)
    if record is None:
        raise DecisionDifferenceRefused(
            "no ContradictionRecord %r in the corpus" % (contradiction_id,))

    position_a = build_position(idx, record["claimAId"], "A")
    position_b = build_position(idx, record["claimBId"], "B")
    classification, basis = classify(position_a, position_b,
                                     record.get("contradictionType"))

    # Neutral by construction: which side would have TAKEN the trade is not
    # mechanically derivable from two claims, so the question never asserts it.
    question = ("Why do %s and %s reach different decisions here, and what would "
                "have to change for them to agree?"
                % (position_a["actorId"], position_b["actorId"]))

    return {
        "schemaVersion": DECISION_DIFFERENCE_SCHEMA_VERSION,
        "decisionDifferenceId": _difference_id(contradiction_id),
        "question": question,
        "derivedFrom": {
            "contradictionId": record["contradictionId"],
            "contradictionType": record.get("contradictionType"),
            "severity": record.get("severity"),
            "status": record.get("status"),
            "scopeOverlap": record.get("scopeOverlap"),
            "recordedRationale": record.get("rationale"),
        },
        "positionA": position_a,
        "positionB": position_b,
        "classification": classification,
        "classificationMeaning": CLASSIFICATION_MEANING[classification],
        "classificationBasis": basis,
        "reconciliationIsMogoReading": classification == INTERPRETATION_HYPOTHESIS,
        "provenanceComplete": (position_a["provenanceComplete"]
                               and position_b["provenanceComplete"]),
        "citedClaimIds": sorted({position_a["claimId"], position_b["claimId"]}),
        "citedEvidenceIds": sorted(set(position_a["evidenceIds"])
                                   | set(position_b["evidenceIds"])),
        "citedSourceIds": sorted(set(position_a["sourceIds"])
                                 | set(position_b["sourceIds"])),
        # Governance pins. Present on EVERY record this module can emit.
        "lane": "RESEARCH",
        "promotionStatus": "NOT_A_TRADING_RULE",
        "adjudicatesNothing": True,
        "changesNoStrategyRule": True,
    }


def decision_differences(idx):
    """Every recorded contradiction, classified. Deterministic order."""
    return [decision_difference(idx, cid) for cid in sorted(idx.contradictions)]


def render(result):
    """The human-readable form. Same content, no extra analysis."""
    out = ["MOGO decision difference -- DERIVED, READ-ONLY, ADJUDICATES NOTHING",
           "  %s   from %s (%s / %s)"
           % (result["decisionDifferenceId"],
              result["derivedFrom"]["contradictionId"],
              result["derivedFrom"]["contradictionType"],
              result["derivedFrom"]["severity"]),
           "  QUESTION: %s" % (result["question"],),
           ""]
    for key in ("positionA", "positionB"):
        position = result[key]
        out.append("  ── POSITION %s : %s ──" % (position["side"], position["actorId"]))
        out.append("      %s  [%s%s]" % (position["claimId"], position["claimType"],
                                         ", RULE CATEGORY" if position["isRuleCategory"]
                                         else ""))
        out.append("      POSITION        : %s" % (position["normalizedClaim"],))
        for entry in position["evidence"]:
            out.append("      SOURCE          : %r" % (entry["exactExcerpt"],))
            out.append("                        (%s  %s/%s  %s)"
                       % (entry["evidenceId"], entry["directness"],
                          entry["extractionCertainty"], entry["sourceLocator"]))
        out.append("      STATED SCOPE    : %s"
                   % (", ".join(position["statedDimensions"]) or "none stated",))
        if position["provenanceGaps"]:
            out.append("      PROVENANCE GAPS : %s"
                       % (", ".join(position["provenanceGaps"]),))
        out.append("")
    out.append("  ── CLASSIFICATION : %s ──" % (result["classification"],))
    out.append("      %s" % (result["classificationMeaning"],))
    out.append("")
    out.append("  ── HOW IT WAS REACHED ──")
    for step in result["classificationBasis"]:
        out.append("      [%s] %-48s %s"
                   % ("X" if step["fired"] else " ", step["test"], step["detail"]))
    out.append("")
    out.append("  lane=%s  promotionStatus=%s  adjudicatesNothing=%s"
               % (result["lane"], result["promotionStatus"],
                  result["adjudicatesNothing"]))
    out.append("  A disagreement is research evidence. It is never permission to "
               "change a strategy rule.")
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Classify a recorded contradiction as a decision difference "
                    "(MOGO-022). Read-only unless --out is given; adjudicates nothing.")
    parser.add_argument("--contradiction", default=None,
                        help="ContradictionRecord id, e.g. 'XCONTRA|20260728|001'. "
                             "Omit to classify every recorded contradiction.")
    parser.add_argument("--evidence-root", default=EVIDENCE_ROOT)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--out", default=None,
                        help="Write the JSON record to this path. Derived output "
                             "only -- reports/, never a primary evidence record.")
    args = parser.parse_args(argv)

    idx = EvidenceIndex.load(args.evidence_root)
    try:
        if args.contradiction:
            result = decision_difference(idx, args.contradiction)
        else:
            result = {"schemaVersion": DECISION_DIFFERENCE_SCHEMA_VERSION,
                      "records": decision_differences(idx)}
    except DecisionDifferenceRefused as exc:
        print("REFUSED: %s" % (exc,))
        return 2

    payload = json.dumps(result, indent=2, sort_keys=True)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(payload + "\n")
        print("wrote %s" % (args.out,))
    if args.json or not args.contradiction:
        print(payload)
    else:
        print("\n".join(render(result)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

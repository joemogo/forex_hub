#!/usr/bin/env python3
"""MOGO-019 Step 10 -- governed candidate-evidence search.

Pure Python standard library. NO NETWORK ACCESS. READ-ONLY: writes nothing,
links nothing, answers nothing. Deterministic.

WHAT THIS ANSWERS, AND WHAT IT DOES NOT

    ANSWERS:      "What governed evidence should a human review for this
                   unanswered question?"
    DOES NOT:     "Does this evidence resolve the question?"

    That distinction is the whole point. Retrieval is NOMINATION. Every result
    is labelled CANDIDATE_ONLY / NOT_ANSWERED / NOT_ADJUDICATED, and deciding
    whether a candidate actually answers a question stays human -- the MOGO-019
    Step 6 finding that semantic adjudication is human-governed is unchanged by
    this module.

WHY IT EXISTS

    MOGO-019 Step 9 searched TJR's corpus BY HAND and found four blockers whose
    answers were already sitting in governed evidence, unlinked -- every one of
    the 12 blocking questions carries `answerEvidenceIds: (none)`. This makes
    that first, cheapest branch of the research loop executable. It makes no
    other branch executable.

THE SEARCH BOUNDARY IS THE CORPUS, NOT THE VOCABULARY

    A question about TJR searches TJR evidence and nothing else. Two educators
    teaching "liquidity sweeps" share terminology, not evidence, and terminology
    overlap must never pull one corpus into another's result set. The corpus is
    resolved from governed identifiers -- the question's claim, or its declared
    sources -- and a question whose corpus cannot be resolved UNIQUELY is
    refused rather than searched broadly.

RANKING IS GOVERNED RELATIONSHIPS FIRST, LEXICAL LAST

    A stated relationship in the evidence store is stronger evidence of
    relevance than a shared word, so the tiers run from explicit linkage down to
    token overlap. Within a tier, ordering is by matched-token count and then by
    identifier -- both stable, both inspectable. There is no opaque score: every
    result carries the exact reasons and the exact tokens that produced it.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import research_understanding as ru                  # noqa: E402
import rule_conformance as rc                        # noqa: E402
from query_evidence import EvidenceIndex             # noqa: E402

SEARCH_SCHEMA_VERSION = "mogo.candidate-evidence-search.v1"

CANDIDATE_ONLY = "CANDIDATE_ONLY"
NOT_ANSWERED = "NOT_ANSWERED"
NOT_ADJUDICATED = "NOT_ADJUDICATED"

# Ranking tiers, strongest governed relationship first. A tier is a position in
# this tuple -- never a computed weight.
EXPLICITLY_RELATED = "EXPLICITLY_RELATED"
SUPPORTS_RELATED_CLAIM = "SUPPORTS_RELATED_CLAIM"
SAME_RULE_CATEGORY = "SAME_RULE_CATEGORY"
DISTINCTIVE_TOKEN_OVERLAP = "DISTINCTIVE_TOKEN_OVERLAP"
NORMALIZED_TOKEN_OVERLAP = "NORMALIZED_TOKEN_OVERLAP"

TIERS = (EXPLICITLY_RELATED, SUPPORTS_RELATED_CLAIM, SAME_RULE_CATEGORY,
         DISTINCTIVE_TOKEN_OVERLAP, NORMALIZED_TOKEN_OVERLAP)
_TIER_RANK = {name: index for index, name in enumerate(TIERS)}

# A token is DISTINCTIVE when it appears in at most this fraction of the
# corpus's evidence items. Corpus-relative rather than a fixed count, so the
# notion survives a corpus of 86 items and one of 8,600. Stated as a constant so
# the threshold is reviewable rather than buried.
DISTINCTIVE_MAX_DOCUMENT_FRACTION = 0.25

MIN_TOKEN_LENGTH = 3

# Ordinary English and question-scaffolding words carry no retrieval signal.
# Explicit and short by design -- this is a stop list, not a language model.
STOPWORDS = frozenset("""
a an and are as at be been but by can could did do does for from had has have
how if in into is it its of on orped that the their them then there these they
this those to was were what when where which who why will with would you your
does not any all one two only ever never each every some such than
claim claims rule rules trade trades trading price level levels
""".split())


class SearchRefused(Exception):
    """Corpus or question identity could not be established. Never guessed."""


def _tokens(text):
    normalized = rc._normalize(text)          # reuse: one normalization, not two
    return {token for token in normalized.split()
            if len(token) >= MIN_TOKEN_LENGTH and token not in STOPWORDS}


def resolve_corpus(idx, question):
    """The trader whose corpus this question belongs to. Fails closed.

    Resolved from GOVERNED IDENTIFIERS -- the question's claim first, then its
    declared sources -- never from the words in the question text.
    """
    traders = set()
    claim = idx.claims.get(question.get("claimId"))
    if claim is not None and claim.get("traderId"):
        traders.add(claim["traderId"])
    for source_id in question.get("sourceIds") or []:
        source = idx.sources.get(source_id)
        if source is not None and source.get("traderId"):
            traders.add(source["traderId"])
    if not traders:
        raise SearchRefused(
            "question %r resolves to no trader through its claim or sources; "
            "refusing to search a corpus that cannot be identified"
            % (question.get("questionId"),))
    if len(traders) > 1:
        raise SearchRefused(
            "question %r resolves to %d traders %s; ambiguous corpus attribution "
            "is refused rather than resolved by picking one"
            % (question.get("questionId"), len(traders), sorted(traders)))
    return traders.pop()


def search(idx, question_id, limit=None):
    """Candidate evidence for ONE unanswered question. A READ. Writes nothing."""
    question = idx.questions.get(question_id)
    if question is None:
        raise SearchRefused("no EvidenceQuestion %r exists" % (question_id,))
    if question.get("answerStatus") == "answered":
        raise SearchRefused(
            "question %r is already answered; candidate search is for unanswered "
            "questions" % (question_id,))

    trader_id = resolve_corpus(idx, question)

    # ── THE BOUNDARY. Only this trader's sources, only their evidence. ──
    corpus_sources = {source_id for source_id, source in idx.sources.items()
                      if source.get("traderId") == trader_id}
    corpus_items = {evidence_id: item for evidence_id, item in idx.items.items()
                    if item.get("sourceId") in corpus_sources}
    if not corpus_items:
        raise SearchRefused("trader %r has no governed evidence to search"
                            % (trader_id,))

    corpus_claims = {claim_id: claim for claim_id, claim in idx.claims.items()
                     if claim.get("traderId") == trader_id}

    supporting = {}
    for link in idx.links.values():
        if (link.get("relationshipType") in rc.SUPPORTING_RELATIONSHIPS
                and link.get("claimId") in corpus_claims
                and link.get("evidenceId") in corpus_items):
            supporting.setdefault(link["evidenceId"], []).append(link["claimId"])

    # ── governed-relationship signals ──
    explicit = set(question.get("evidenceIds") or [])
    explicit |= set(question.get("answerEvidenceIds") or [])
    explicit &= set(corpus_items)                 # never leave the corpus

    subject_claim = question.get("claimId")
    subject_type = (corpus_claims.get(subject_claim) or {}).get("claimType")
    same_category_claims = {claim_id for claim_id, claim in corpus_claims.items()
                            if subject_type and claim.get("claimType") == subject_type}

    # ── lexical signals, corpus-relative ──
    question_tokens = _tokens(question.get("questionText") or "")
    item_tokens = {evidence_id: _tokens(item.get("exactExcerpt") or "")
                   for evidence_id, item in corpus_items.items()}
    total = len(corpus_items)
    frequency = {}
    for tokens in item_tokens.values():
        for token in tokens:
            frequency[token] = frequency.get(token, 0) + 1
    distinctive = {token for token in question_tokens
                   if frequency.get(token, 0) > 0
                   and frequency[token] <= total * DISTINCTIVE_MAX_DOCUMENT_FRACTION}

    results = []
    for evidence_id in sorted(corpus_items):
        item = corpus_items[evidence_id]
        claims_supported = sorted(supporting.get(evidence_id, []))
        overlap = sorted(question_tokens & item_tokens[evidence_id])
        distinctive_hits = sorted(distinctive & item_tokens[evidence_id])

        reasons, tier = [], None
        if evidence_id in explicit:
            reasons.append("named in the question's own evidence references")
            tier = EXPLICITLY_RELATED
        if subject_claim and subject_claim in claims_supported:
            reasons.append("supports the question's subject claim %s" % (subject_claim,))
            tier = tier or SUPPORTS_RELATED_CLAIM
        if not tier and same_category_claims & set(claims_supported):
            reasons.append("supports a claim of the same type (%s)" % (subject_type,))
            tier = SAME_RULE_CATEGORY
        if not tier and distinctive_hits:
            reasons.append("distinctive token overlap: %s" % (", ".join(distinctive_hits),))
            tier = DISTINCTIVE_TOKEN_OVERLAP
        if not tier and overlap:
            reasons.append("token overlap: %s" % (", ".join(overlap),))
            tier = NORMALIZED_TOKEN_OVERLAP
        if tier is None:
            continue

        results.append({
            "questionId": question_id,
            "evidenceId": evidence_id,
            "traderId": trader_id,
            "sourceId": item.get("sourceId"),
            "exactExcerpt": item.get("exactExcerpt"),
            "directness": item.get("directness"),
            "extractionCertainty": item.get("extractionCertainty"),
            "relatedClaimIds": claims_supported,
            "tier": tier,
            "reasons": reasons,
            "matchedTokens": overlap,
            "distinctiveTokens": distinctive_hits,
            # Labels on EVERY result, not just the envelope.
            "status": CANDIDATE_ONLY,
            "answerStatus": NOT_ANSWERED,
            "adjudicationStatus": NOT_ADJUDICATED,
        })

    # Governed relationship first; then more distinctive matches; then more
    # matches; then the identifier. Every component is stable and inspectable.
    results.sort(key=lambda r: (_TIER_RANK[r["tier"]],
                                -len(r["distinctiveTokens"]),
                                -len(r["matchedTokens"]),
                                r["evidenceId"]))
    for index, result in enumerate(results, start=1):
        result["rank"] = index
    if limit:
        results = results[:limit]

    return {
        "schemaVersion": SEARCH_SCHEMA_VERSION,
        "questionId": question_id,
        "questionType": question.get("questionType"),
        "questionText": question.get("questionText"),
        "blockingStatus": question.get("blockingStatus"),
        "traderId": trader_id,
        "subjectClaimId": subject_claim,
        "subjectClaimType": subject_type,
        "requiredCategory": subject_type in ru.REQUIRED_RULE_CATEGORIES,
        "corpusEvidenceCount": total,
        "candidateCount": len(results),
        "status": CANDIDATE_ONLY,
        "answerStatus": NOT_ANSWERED,
        "adjudicationStatus": NOT_ADJUDICATED,
        "meaning": "Candidate evidence for HUMAN review. This search nominates; "
                   "it does not answer the question, link evidence, or "
                   "adjudicate anything.",
        "candidates": results,
    }


def render(result):
    out = ["MOGO candidate-evidence search -- READ-ONLY, NOMINATION ONLY",
           "  question : %s  [%s]" % (result["questionId"], result["questionType"]),
           "  corpus   : %s  (%d governed evidence items)"
           % (result["traderId"], result["corpusEvidenceCount"]),
           "  subject  : %s  type=%s%s"
           % (result["subjectClaimId"], result["subjectClaimType"],
              "  [REQUIRED CATEGORY]" if result["requiredCategory"] else ""),
           "  blocking : %s" % (result["blockingStatus"],),
           "",
           "  Q: %s" % (result["questionText"],),
           "",
           "  ── %d CANDIDATES (%s / %s / %s) ──"
           % (result["candidateCount"], result["status"], result["answerStatus"],
              result["adjudicationStatus"])]
    for candidate in result["candidates"]:
        out.append("  [%d] %s   tier=%s"
                   % (candidate["rank"], candidate["evidenceId"], candidate["tier"]))
        out.append("      source   : %s  (%s/%s)"
                   % (candidate["sourceId"], candidate["directness"],
                      candidate["extractionCertainty"]))
        out.append("      excerpt  : %r" % (candidate["exactExcerpt"],))
        for reason in candidate["reasons"]:
            out.append("      why      : %s" % (reason,))
        if candidate["relatedClaimIds"]:
            out.append("      supports : %s" % (", ".join(candidate["relatedClaimIds"]),))
    out.append("\n  %s" % (result["meaning"],))
    return out


# ---------------------------------------------------------------------------
# MOGO-019 Step 11 -- claim-level candidate search
# ---------------------------------------------------------------------------
# The sibling of `search()`. Step 10 proved that some questions are answered one
# abstraction level up: EQ|013 asks what invalidates an entry rule, and the
# corpus already holds an `invalidation_rule` claim -- at a DIFFERENT timeframe.
# Searching evidence excerpts could never surface that, because the fact lives in
# a Claim's category and scope, not in any excerpt's words.
#
# It shares this module's corpus resolution, tokenizer and labels rather than
# restating them: one normalization, one boundary, one refusal path.

NOT_LINKED = "NOT_LINKED"

# Claim-nomination tiers, structural before lexical.
WANTED_CATEGORY = "WANTED_CATEGORY"
SAME_CATEGORY_AS_SUBJECT = "SAME_CATEGORY_AS_SUBJECT"
SHARED_SCOPE = "SHARED_SCOPE"

CLAIM_TIERS = (WANTED_CATEGORY, SAME_CATEGORY_AS_SUBJECT, SHARED_SCOPE,
               DISTINCTIVE_TOKEN_OVERLAP, NORMALIZED_TOKEN_OVERLAP)
_CLAIM_TIER_RANK = {name: index for index, name in enumerate(CLAIM_TIERS)}

# WHICH CLAIM CATEGORY A QUESTION IS ASKING FOR.
#
# STEP 11'S OWN DERIVATION, documented as such: `EvidenceQuestion` carries no
# "wanted category" field. The mapping is read straight off the questionType's
# own name -- a `missing_invalidation` question is asking for an
# `invalidation_rule` -- and every value is a member of the existing claimType
# vocabulary. A questionType with no obvious category maps to nothing rather
# than to a guess, and those questions simply fall through to the weaker tiers.
WANTED_CATEGORY_BY_QUESTION_TYPE = {
    "missing_invalidation": "invalidation_rule",
    "missing_stop_placement": "stop_rule",
    "missing_target_logic": "target_rule",
    "unruled_exception": "exception",
}

# The only scope fields the corpus actually populates. `marketSymbol`,
# `marketCondition`, `scope`, `subjectEntityType` and `strategyFamilyId` are
# defined by the schema but empty on every TJR claim, so designing around them
# would be designing around nothing.
SCOPE_FIELDS = ("timeframe", "session")


def _scope_comparison(subject, candidate):
    """Governed scope side by side, with differences NAMED, never resolved."""
    comparison, differences = {}, []
    for field in SCOPE_FIELDS:
        subject_value = None if subject is None else subject.get(field)
        candidate_value = candidate.get(field)
        comparison[field] = {"subject": subject_value,
                             "candidate": candidate_value}
        if subject_value != candidate_value:
            differences.append(field)
    return comparison, differences


def search_claims(idx, question_id, limit=None):
    """Candidate CLAIMS for one unanswered question. A READ. Writes nothing.

    Nominates claims that may bear on the question. It does NOT decide whether a
    candidate answers it, and it does NOT decide whether a scope difference is
    acceptable -- differences are exposed and labelled, never resolved.
    """
    question = idx.questions.get(question_id)
    if question is None:
        raise SearchRefused("no EvidenceQuestion %r exists" % (question_id,))
    if question.get("answerStatus") == "answered":
        raise SearchRefused(
            "question %r is already answered; candidate search is for unanswered "
            "questions" % (question_id,))

    trader_id = resolve_corpus(idx, question)
    corpus_claims = {claim_id: claim for claim_id, claim in idx.claims.items()
                     if claim.get("traderId") == trader_id}
    if not corpus_claims:
        raise SearchRefused("trader %r has no governed claims to search"
                            % (trader_id,))

    subject_id = question.get("claimId")
    subject = corpus_claims.get(subject_id)
    subject_type = None if subject is None else subject.get("claimType")
    wanted = WANTED_CATEGORY_BY_QUESTION_TYPE.get(question.get("questionType"))

    corpus_sources = {source_id for source_id, source in idx.sources.items()
                      if source.get("traderId") == trader_id}
    supporting = {}
    for link in idx.links.values():
        item = idx.items.get(link.get("evidenceId"))
        if (link.get("relationshipType") in rc.SUPPORTING_RELATIONSHIPS
                and link.get("claimId") in corpus_claims
                and item is not None
                and item.get("sourceId") in corpus_sources):
            supporting.setdefault(link["claimId"], []).append(item)

    question_tokens = _tokens(question.get("questionText") or "")
    claim_tokens = {claim_id: _tokens(claim.get("normalizedClaim") or "")
                    for claim_id, claim in corpus_claims.items()}
    total = len(corpus_claims)
    frequency = {}
    for tokens in claim_tokens.values():
        for token in tokens:
            frequency[token] = frequency.get(token, 0) + 1
    distinctive = {token for token in question_tokens
                   if 0 < frequency.get(token, 0)
                   <= total * DISTINCTIVE_MAX_DOCUMENT_FRACTION}

    results = []
    for claim_id in sorted(corpus_claims):
        if claim_id == subject_id:
            continue                    # the subject is what is being questioned
        claim = corpus_claims[claim_id]
        claim_type = claim.get("claimType")
        overlap = sorted(question_tokens & claim_tokens[claim_id])
        distinctive_hits = sorted(distinctive & claim_tokens[claim_id])
        comparison, differences = _scope_comparison(subject, claim)

        reasons, tier = [], None
        if wanted and claim_type == wanted:
            reasons.append("category %r is what a %r question asks for"
                           % (wanted, question.get("questionType")))
            tier = WANTED_CATEGORY
        elif subject_type and claim_type == subject_type:
            reasons.append("same category as the subject claim (%s)" % (subject_type,))
            tier = SAME_CATEGORY_AS_SUBJECT
        elif (subject is not None and overlap and any(
                claim.get(field) is not None
                and claim.get(field) == subject.get(field)
                for field in SCOPE_FIELDS)):
            # Shared scope ALONE is too weak to nominate on: nine TJR claims
            # share `session`, and surfacing all of them for any question would
            # be noise wearing a structural label. Scope must coincide with at
            # least some lexical relation before it counts.
            reasons.append("shares governed scope with the subject claim "
                           "and overlaps its wording")
            tier = SHARED_SCOPE
        elif distinctive_hits:
            reasons.append("distinctive token overlap: %s"
                           % (", ".join(distinctive_hits),))
            tier = DISTINCTIVE_TOKEN_OVERLAP
        elif overlap:
            reasons.append("token overlap: %s" % (", ".join(overlap),))
            tier = NORMALIZED_TOKEN_OVERLAP
        if tier is None:
            continue

        if differences:
            # NAMED, NOT RESOLVED. Whether a 5m rule governs a 1m entry is a
            # scope judgement this module must not make.
            reasons.append("scope differs on %s -- NOT resolved here"
                           % (", ".join(differences),))

        evidence = supporting.get(claim_id, [])
        results.append({
            "questionId": question_id,
            "claimId": claim_id,
            "traderId": trader_id,
            "claimType": claim_type,
            "normalizedClaim": claim.get("normalizedClaim"),
            "claimStatus": claim.get("claimStatus"),
            "confidenceState": claim.get("confidenceState"),
            "scopeComparison": comparison,
            "scopeDifferences": differences,
            "supportingEvidenceIds": sorted(i["evidenceId"] for i in evidence),
            "sourceIds": sorted({i.get("sourceId") for i in evidence}),
            "directness": sorted({i.get("directness") for i in evidence}),
            "extractionCertainty": sorted({i.get("extractionCertainty")
                                           for i in evidence}),
            "tier": tier,
            "reasons": reasons,
            "matchedTokens": overlap,
            "distinctiveTokens": distinctive_hits,
            "status": CANDIDATE_ONLY,
            "answerStatus": NOT_ANSWERED,
            "adjudicationStatus": NOT_ADJUDICATED,
            "linkStatus": NOT_LINKED,
        })

    results.sort(key=lambda r: (_CLAIM_TIER_RANK[r["tier"]],
                                -len(r["distinctiveTokens"]),
                                -len(r["matchedTokens"]),
                                r["claimId"]))
    for index, result in enumerate(results, start=1):
        result["rank"] = index
    if limit:
        results = results[:limit]

    return {
        "schemaVersion": CLAIM_SEARCH_SCHEMA_VERSION,
        "questionId": question_id,
        "questionType": question.get("questionType"),
        "questionText": question.get("questionText"),
        "blockingStatus": question.get("blockingStatus"),
        "traderId": trader_id,
        "subjectClaimId": subject_id,
        "subjectClaimType": subject_type,
        "wantedCategory": wanted,
        "requiredCategory": subject_type in ru.REQUIRED_RULE_CATEGORIES,
        "corpusClaimCount": total,
        "candidateCount": len(results),
        "status": CANDIDATE_ONLY,
        "answerStatus": NOT_ANSWERED,
        "adjudicationStatus": NOT_ADJUDICATED,
        "linkStatus": NOT_LINKED,
        "meaning": "Candidate CLAIMS for HUMAN review. This search nominates; it "
                   "does not answer the question, link anything, adjudicate, or "
                   "decide whether a scope difference is acceptable.",
        "candidates": results,
    }


CLAIM_SEARCH_SCHEMA_VERSION = "mogo.candidate-claim-search.v1"


def render_claims(result):
    out = ["MOGO candidate-CLAIM search -- READ-ONLY, NOMINATION ONLY",
           "  question : %s  [%s]" % (result["questionId"], result["questionType"]),
           "  corpus   : %s  (%d governed claims)"
           % (result["traderId"], result["corpusClaimCount"]),
           "  subject  : %s  type=%s%s"
           % (result["subjectClaimId"], result["subjectClaimType"],
              "  [REQUIRED CATEGORY]" if result["requiredCategory"] else ""),
           "  wanted   : %s" % (result["wantedCategory"] or "(none derivable)",),
           "", "  Q: %s" % (result["questionText"],), "",
           "  ── %d CANDIDATES (%s / %s / %s / %s) ──"
           % (result["candidateCount"], result["status"], result["answerStatus"],
              result["adjudicationStatus"], result["linkStatus"])]
    for candidate in result["candidates"]:
        out.append("  [%d] %s   tier=%s   type=%s"
                   % (candidate["rank"], candidate["claimId"], candidate["tier"],
                      candidate["claimType"]))
        out.append("      claim    : %s" % (candidate["normalizedClaim"],))
        for reason in candidate["reasons"]:
            out.append("      why      : %s" % (reason,))
        scope = candidate["scopeComparison"]
        out.append("      scope    : " + "  ".join(
            "%s subject=%r candidate=%r" % (field, scope[field]["subject"],
                                            scope[field]["candidate"])
            for field in SCOPE_FIELDS))
        if candidate["supportingEvidenceIds"]:
            out.append("      evidence : %s"
                       % (", ".join(candidate["supportingEvidenceIds"]),))
    out.append("\n  %s" % (result["meaning"],))
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Governed candidate search (MOGO-019 Steps 10/11). "
                    "Read-only. Nominates candidates; answers nothing.")
    parser.add_argument("question", help="EvidenceQuestion id, e.g. 'EQ|20260727|013'")
    parser.add_argument("--evidence-root", default=rc.EVIDENCE_ROOT)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--claims", action="store_true",
                        help="search candidate CLAIMS (Step 11) instead of "
                             "evidence items (Step 10)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    idx = EvidenceIndex.load(args.evidence_root)
    finder, renderer = ((search_claims, render_claims) if args.claims
                        else (search, render))
    try:
        result = finder(idx, args.question, limit=args.limit)
    except SearchRefused as exc:
        print("REFUSED: %s" % (exc,))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True) if args.json
          else "\n".join(renderer(result)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

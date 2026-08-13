#!/usr/bin/env python3
"""MOGO-019 Step 7 -- Rule-2 conformance, review-by-exception.

Pure Python standard library. NO NETWORK ACCESS. READ-ONLY: opens no file for
writing, creates no record, mutates nothing. Two runs over an unchanged corpus
produce byte-identical output.

WHAT THIS IS

    STANDARDS-extraction.md Rule 2 says a claim "restates; it never adds" -- it
    may not introduce a threshold, instrument, timeframe, condition or causal
    link the excerpt does not contain. Rule 1 (verbatim excerpt) is already
    machine-enforced by ingest.py. Rule 2 is not, and MOGO-019 Step 6 measured
    the consequence: only 1 of 295 claims is verbatim-identical to its supporting
    excerpt, so 294 rest on a human paraphrase judgment nothing checks.

    This analyzer does not check Rule 2. It checks a DETERMINISTIC SHADOW of
    Rule 2: concrete tokens -- numbers, times, instruments, directions,
    quantifiers -- that appear in the claim and in NONE of its supporting
    excerpts. Those are the places a paraphrase most often adds something.

WHAT IT CAN AND CANNOT PROVE

    CAN prove: a specific token in the claim occurs in no supporting excerpt.
    That is a lexical fact, checked by exact comparison after conservative
    normalization.

    CANNOT prove: that a claim is faithful, correct, approved, or semantically
    equivalent to its evidence. A paraphrase can violate Rule 2 using only words
    that appear in the excerpt, and this analyzer will not see it.

    `CLEAN_MECHANICAL_MATCH` therefore means EXACTLY ONE THING: no discrepancy
    was detectable by the checks implemented here. IT DOES NOT MEAN THE CLAIM IS
    APPROVED, CORRECT OR REVIEWED. The human semantic-review requirement in
    ingest.py remains authoritative and is untouched.

SUPPORTING EVIDENCE ONLY

    Only `supports` and `exemplifies` links are read -- the same
    `_SUPPORTING_RELATIONSHIPS` set `evidence_common` already defines. A
    `contextualizes` link is background, not support, and treating it as support
    is a real error: MOGO-019 Step 6's first pass did exactly that and
    misread CLAIM|TJR|20260727|003 as a Rule-2 violation, because its
    contextualizing excerpt discusses the 9:30 open while its SUPPORTING excerpt
    is the verbatim sentence. Relationships are resolved by identifier and type,
    never by substring.

FAIL CLOSED

    Missing support, an unresolvable evidence reference, an unknown trader, a
    malformed record or incomplete provenance produce MISSING_SUPPORT,
    AMBIGUOUS_SUPPORT or PROVENANCE_FAILURE -- never CLEAN_MECHANICAL_MATCH.
"""

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from query_evidence import EvidenceIndex             # noqa: E402
import evidence_common as evc                        # noqa: E402

REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
EVIDENCE_ROOT = os.path.join(REPO_ROOT, "docs", "trader-intelligence", "evidence")

REPORT_SCHEMA_VERSION = "mogo.rule2-conformance.v1"

# Reused, not redefined: evidence_common already declares which relationships
# count as support for confidence computation, and conformance must use the
# same definition or the two would disagree about what supports a claim.
SUPPORTING_RELATIONSHIPS = frozenset(evc._SUPPORTING_RELATIONSHIPS)

CLEAN = "CLEAN_MECHANICAL_MATCH"
REVIEW_NUMERIC = "REVIEW_NUMERIC"
REVIEW_TIME = "REVIEW_TIME"
REVIEW_INSTRUMENT = "REVIEW_INSTRUMENT"
REVIEW_DIRECTION = "REVIEW_DIRECTION"
REVIEW_QUANTIFIER = "REVIEW_QUANTIFIER"
REVIEW_MULTIPLE = "REVIEW_MULTIPLE"
MISSING_SUPPORT = "MISSING_SUPPORT"
AMBIGUOUS_SUPPORT = "AMBIGUOUS_SUPPORT"
PROVENANCE_FAILURE = "PROVENANCE_FAILURE"

# What CLEAN does NOT mean. Carried on every report so no reader can shorten it.
CLEAN_MEANING = ("no discrepancy detectable by the deterministic checks "
                 "implemented here; NOT a statement that the claim is approved, "
                 "correct, faithful or reviewed")

# ── the five checks ────────────────────────────────────────────────────────
# Each returns a set of NORMALIZED tokens. A token is flagged when it appears in
# the claim and in NONE of the supporting excerpts.

_NUMBER = re.compile(r"\d+(?:\.\d+)?%?")
_CLOCK = re.compile(r"\b\d{1,2}:\d{2}\s*(?:a\.?m\.?|p\.?m\.?)?", re.I)
_TIMEFRAME = re.compile(r"\b[mhdw]\d{1,3}\b", re.I)
_TIME_WORD = re.compile(
    r"\b(?:second|seconds|minute|minutes|hour|hours|day|daily|days|week|weekly|"
    r"weeks|month|monthly|session|sessions|am|pm|a\.m\.|p\.m\.)\b", re.I)
_PAIR = re.compile(r"\b([a-z]{3})\s*[/\-]?\s*([a-z]{3})\b", re.I)
_INSTRUMENT_WORD = re.compile(
    r"\b(?:nasdaq|s&p|sp500|dow|dax|ftse|nikkei|gold|silver|oil|xau|xag|"
    r"btc|eth|us30|us100|us500|nas100|spx|ndx)\b", re.I)
_DIRECTION = re.compile(
    r"\b(?:long|longs|short|shorts|buy|buys|buying|sell|sells|selling|"
    r"bullish|bearish|upside|downside)\b", re.I)
_QUANTIFIER = re.compile(
    r"\b(?:always|never|every|only|must|exactly|all|none|any|no)\b", re.I)

# Currency codes, so `_PAIR` does not match ordinary three-letter words. The
# pair check would otherwise fire on phrases like "the low was".
_CURRENCIES = frozenset((
    "usd", "eur", "gbp", "jpy", "chf", "aud", "nzd", "cad", "sek", "nok",
    "dkk", "try", "zar", "mxn", "sgd", "hkd", "cnh", "pln", "xau", "xag"))


def _normalize(text):
    """CONSERVATIVE normalization only.

    Case-fold, collapse whitespace, drop thousands separators inside numbers,
    and turn punctuation into spaces so tokens can be compared. NOTHING here
    resolves meaning: no synonym table, no stemming, no ordinal expansion. If
    two forms are not mechanically identical after this, the difference is
    SURFACED rather than assumed equivalent.
    """
    if not isinstance(text, str):
        return ""
    lowered = text.casefold()
    lowered = re.sub(r"(?<=\d),(?=\d{3}\b)", "", lowered)   # 1,000 -> 1000
    lowered = re.sub(r"[^\w:./&%-]+", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def _pairs(text):
    found = set()
    for a, b in _PAIR.findall(text):
        if a.casefold() in _CURRENCIES and b.casefold() in _CURRENCIES:
            # EURUSD / EUR-USD / EUR/USD all normalize to one token, which is a
            # FORMATTING equivalence the repository already relies on -- not a
            # semantic one.
            found.add((a + b).casefold())
    return found


def _tokens(text):
    """Every checked token class for one piece of text."""
    norm = _normalize(text)
    return {
        REVIEW_NUMERIC: set(_NUMBER.findall(norm)),
        REVIEW_TIME: (set(t.strip() for t in _CLOCK.findall(norm))
                      | {t.casefold() for t in _TIMEFRAME.findall(norm)}
                      | {t.casefold() for t in _TIME_WORD.findall(norm)}),
        REVIEW_INSTRUMENT: (_pairs(norm)
                            | {t.casefold() for t in _INSTRUMENT_WORD.findall(norm)}),
        REVIEW_DIRECTION: {t.casefold() for t in _DIRECTION.findall(norm)},
        REVIEW_QUANTIFIER: {t.casefold() for t in _QUANTIFIER.findall(norm)},
    }


CHECK_CLASSES = (REVIEW_NUMERIC, REVIEW_TIME, REVIEW_INSTRUMENT,
                 REVIEW_DIRECTION, REVIEW_QUANTIFIER)


def analyze_claim(claim, supporting_items):
    """Deterministic conformance result for ONE claim. Pure.

    `supporting_items` are the resolved EvidenceItems of the claim's SUPPORT
    relationships only.
    """
    if not supporting_items:
        return {"classification": MISSING_SUPPORT, "discrepancies": {},
                "flaggedClasses": []}

    excerpts = [item.get("exactExcerpt") for item in supporting_items]
    if any(not isinstance(text, str) or not text.strip() for text in excerpts):
        return {"classification": PROVENANCE_FAILURE, "discrepancies": {},
                "flaggedClasses": []}

    text = claim.get("normalizedClaim")
    if not isinstance(text, str) or not text.strip():
        return {"classification": PROVENANCE_FAILURE, "discrepancies": {},
                "flaggedClasses": []}

    claim_tokens = _tokens(text)
    evidence_tokens = {name: set() for name in CHECK_CLASSES}
    for excerpt in excerpts:
        for name, values in _tokens(excerpt).items():
            evidence_tokens[name] |= values

    discrepancies = {}
    for name in CHECK_CLASSES:
        missing = sorted(claim_tokens[name] - evidence_tokens[name])
        if missing:
            discrepancies[name] = missing

    flagged = sorted(discrepancies)
    if not flagged:
        classification = CLEAN
    elif len(flagged) > 1:
        classification = REVIEW_MULTIPLE
    else:
        classification = flagged[0]
    return {"classification": classification, "discrepancies": discrepancies,
            "flaggedClasses": flagged}


def conformance_report(idx, trader_id):
    """Review-by-exception report for ONE corpus. A READ. Writes nothing."""
    if not trader_id or not isinstance(trader_id, str):
        raise ValueError("a trader identifier is required")

    corpus = {cid: claim for cid, claim in idx.claims.items()
              if claim.get("traderId") == trader_id}
    if not corpus:
        raise ValueError("no claims are attributed to trader %r; refusing to "
                         "report on a corpus that cannot be identified"
                         % (trader_id,))

    supporting = {}
    ambiguous = set()
    for link in idx.links.values():
        claim_id = link.get("claimId")
        if claim_id not in corpus:
            continue
        relationship = link.get("relationshipType")
        if relationship not in evc.RELATIONSHIP_TYPES:
            ambiguous.add(claim_id)          # unknown relationship: fail closed
            continue
        if relationship in SUPPORTING_RELATIONSHIPS:
            supporting.setdefault(claim_id, []).append(link)

    rows = []
    for claim_id in sorted(corpus):
        claim = corpus[claim_id]
        links = sorted(supporting.get(claim_id, []), key=lambda l: l["linkId"])
        items, broken, foreign = [], False, False
        for link in links:
            item = idx.items.get(link["evidenceId"])
            if item is None:
                broken = True
                continue
            # ISOLATION: an evidence item reached from this corpus must belong
            # to this corpus's own sources. Checked, not assumed.
            source = idx.sources.get(item.get("sourceId"))
            if source is None or source.get("traderId") != trader_id:
                foreign = True
                continue
            items.append(item)

        if claim_id in ambiguous:
            result = {"classification": AMBIGUOUS_SUPPORT, "discrepancies": {},
                      "flaggedClasses": []}
        elif broken or foreign:
            result = {"classification": PROVENANCE_FAILURE, "discrepancies": {},
                      "flaggedClasses": []}
        else:
            result = analyze_claim(claim, items)

        rows.append({
            "claimId": claim_id,
            "traderId": trader_id,
            "claimType": claim.get("claimType"),
            "normalizedClaim": claim.get("normalizedClaim"),
            "classification": result["classification"],
            "flaggedClasses": result["flaggedClasses"],
            "discrepancies": result["discrepancies"],
            "supportingEvidence": [
                {"evidenceId": item["evidenceId"],
                 "relationshipType": next(
                     l["relationshipType"] for l in links
                     if l["evidenceId"] == item["evidenceId"]),
                 "exactExcerpt": item.get("exactExcerpt"),
                 "directness": item.get("directness"),
                 "extractionCertainty": item.get("extractionCertainty"),
                 "extractionMethod": item.get("extractionMethod"),
                 "sourceId": item.get("sourceId")}
                for item in items],
            "blockingQuestionIds": sorted(
                q["questionId"] for q in idx.questions.values()
                if q.get("claimId") == claim_id
                and q.get("blockingStatus") in ("blocks_rule_candidate",
                                                "blocks_promotion")
                and q.get("answerStatus") != "answered"),
            "contradictionIds": sorted(
                record["contradictionId"] for record in idx.contradictions.values()
                if claim_id in (record.get("claimAId"), record.get("claimBId"))
                and record.get("status") == "open"),
        })

    counts, class_counts = {}, {name: 0 for name in CHECK_CLASSES}
    for row in rows:
        counts[row["classification"]] = counts.get(row["classification"], 0) + 1
        for name in row["flaggedClasses"]:
            class_counts[name] += 1
    flagged_rows = [r for r in rows if r["classification"] != CLEAN]

    directness = {"clean": {}, "flagged": {}}
    for row in rows:
        bucket = "clean" if row["classification"] == CLEAN else "flagged"
        for item in row["supportingEvidence"]:
            key = item["directness"]
            directness[bucket][key] = directness[bucket].get(key, 0) + 1

    return {
        "schemaVersion": REPORT_SCHEMA_VERSION,
        "traderId": trader_id,
        "lane": "RESEARCH",
        "promotionStatus": "NOT_A_TRADING_RULE",
        "cleanMeaning": CLEAN_MEANING,
        "totalClaims": len(rows),
        "cleanCount": counts.get(CLEAN, 0),
        "reviewCount": len(flagged_rows),
        "countsByClassification": counts,
        "countsByDiscrepancyClass": class_counts,
        "multipleDiscrepancyClaims": sum(1 for r in rows
                                         if len(r["flaggedClasses"]) > 1),
        "directnessDistribution": directness,
        "claims": rows,
    }


def render(report, only_flagged=True):
    out = ["MOGO Rule-2 conformance -- DERIVED, READ-ONLY, REVIEW-BY-EXCEPTION",
           "  trader=%s  claims=%d  clean=%d  needing review=%d"
           % (report["traderId"], report["totalClaims"], report["cleanCount"],
              report["reviewCount"]),
           "  CLEAN_MECHANICAL_MATCH means: %s" % (report["cleanMeaning"],),
           "", "  ── COUNTS ──"]
    for name in sorted(report["countsByClassification"]):
        out.append("  %-26s %d" % (name, report["countsByClassification"][name]))
    out.append("  claims with >1 discrepancy class: %d"
               % (report["multipleDiscrepancyClaims"],))
    out.append("\n  ── REVIEW QUEUE ──")
    for row in report["claims"]:
        if only_flagged and row["classification"] == CLEAN:
            continue
        out.append("  %s  [%s]  %s"
                   % (row["claimId"], row["classification"], row["claimType"]))
        out.append("      claim   : %s" % (row["normalizedClaim"],))
        for name, tokens in sorted(row["discrepancies"].items()):
            out.append("      FLAG %-18s absent from every supporting excerpt: %s"
                       % (name, ", ".join(repr(t) for t in tokens)))
        for item in row["supportingEvidence"]:
            out.append("      support : %s [%s/%s] %s"
                       % (item["evidenceId"], item["relationshipType"],
                          item["directness"], item["extractionCertainty"]))
            out.append("          %r" % (item["exactExcerpt"],))
        if row["blockingQuestionIds"]:
            out.append("      blocking questions: %s"
                       % (", ".join(row["blockingQuestionIds"]),))
        if row["contradictionIds"]:
            out.append("      open contradictions: %s"
                       % (", ".join(row["contradictionIds"]),))
    out.append("\n  This analyzer checks a DETERMINISTIC SHADOW of Rule 2. It "
               "cannot prove a claim is")
    out.append("  faithful, correct or approved, and a paraphrase can violate "
               "Rule 2 using only words")
    out.append("  present in the excerpt. The human semantic-review requirement "
               "remains authoritative.")
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Rule-2 conformance review-by-exception (MOGO-019 Step 7). "
                    "Read-only. Approves nothing.")
    parser.add_argument("--trader", default="TJR")
    parser.add_argument("--evidence-root", default=EVIDENCE_ROOT)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--all", action="store_true",
                        help="include CLEAN_MECHANICAL_MATCH claims too")
    args = parser.parse_args(argv)

    idx = EvidenceIndex.load(args.evidence_root)
    try:
        report = conformance_report(idx, args.trader)
    except ValueError as exc:
        print("REFUSED: %s" % (exc,))
        return 2
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("\n".join(render(report, only_flagged=not args.all)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

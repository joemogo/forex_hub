#!/usr/bin/env python3
"""Review by exception for the acquisition queue (MOGO-022).

THE PROBLEM THIS SOLVES -- AND THE ONE IT DELIBERATELY DOES NOT
---------------------------------------------------------------
58 candidates sit in OWNER_REVIEW. That is not a backlog of 58 decisions: it is a
handful of real decisions wearing 58 records. `prioritize_sources.py` advances
EVERY candidate to OWNER_REVIEW unconditionally -- it is the pipeline's terminal
automatic state, not a judgement -- and nothing in the repository performs the exit,
because governance forbids performing it automatically:

    "APPROVED_FOR_ACQUISITION, APPROVED_FOR_RESEARCH_INTAKE, and REJECTED may only
     be reached via an active OwnerDecision -- never automatically."
        -- docs/trader-intelligence/acquisition/schema/acquisition-status.schema.json

So the operator dependency that can legitimately be removed is "the operator must
personally page through 58 records", NOT "the operator must approve". This tool
removes the first and touches nothing about the second.

WHAT IT MAY DO, per docs/trader-intelligence/acquisition/README.md:
    "This layer may: register research candidates ... support owner review, and
     report what should be researched next."

STRICTLY READ-ONLY OVER CANDIDATES. It writes one report and mutates no candidate
field -- not acquisitionStatus, not ownerReviewStatus, not authenticityStatus, not
duplicateStatus. Every record stays exactly where it is. Modelled on
`exception_triage.py`, whose guardrail applies here verbatim: optimize for FEWER
WASTED REVIEWS, never for fewer flags.

NO NETWORK ACCESS.
"""
import argparse
import glob as globmod
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acquisition_common as ac        # noqa: E402

REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
CANDIDATES_GLOB = os.path.join(
    REPO_ROOT, "docs", "trader-intelligence", "acquisition", "candidates", "*.json")
REPORT_PATH = os.path.join(
    REPO_ROOT, "docs", "trader-intelligence", "acquisition", "reports", "triage-report.json")

SCHEMA_VERSION = "mogo.acquisition-triage.v1"

# Buckets. Every one of these is DERIVED from record fields, never from a list of
# candidate ids -- an id list would be a snapshot that silently stops matching as
# soon as the corpus grows.
AWAITING_OWNER_ACQUISITION = "AWAITING_OWNER_ACQUISITION_DECISION"
NO_EXPANSION_CONNECTOR = "NOT_ACQUIRABLE_NO_EXPANSION_CONNECTOR"
DURABLE_NEGATIVE_RECORD = "DURABLE_NEGATIVE_RECORD_UNATTRIBUTED"

BUCKET_MEANING = {
    AWAITING_OWNER_ACQUISITION:
        "A real acquisition decision. The gate sits BEFORE content exists by design, "
        "so these are decidable now -- approving attributes nothing and creates no "
        "evidence. Grouped by trader, because the decision is per-trader effort "
        "allocation rather than per-video.",
    NO_EXPANSION_CONNECTOR:
        "A population handle -- a playlist or sitemap, not an acquirable document. "
        "Approving it would authorise an expansion step that does not exist "
        "(per-item expansion needs a connector that was never built). It sits in "
        "OWNER_REVIEW because the pipeline has one terminal state, not because a "
        "judgement is pending.",
    DURABLE_NEGATIVE_RECORD:
        "Registered deliberately WITHOUT a claimed trader, so the attribution trap "
        "itself is durable. The adjudication is already recorded; the queue simply "
        "has no state meaning 'kept as a negative record, never to be acquired'.",
}


def load_candidates(pattern=None):
    out = []
    for path in sorted(globmod.glob(pattern or CANDIDATES_GLOB)):
        with open(path, "r", encoding="utf-8") as handle:
            out.append(json.load(handle))
    return out


def bucket_of(candidate):
    """Derived, in priority order. Pure."""
    if not candidate.get("claimedTraderId"):
        return DURABLE_NEGATIVE_RECORD
    if candidate.get("sourceType") == "PLAYLIST":
        return NO_EXPANSION_CONNECTOR
    url = (candidate.get("normalizedUrl") or candidate.get("url") or "").lower()
    if url.endswith(".xml") or "sitemap" in url:
        return NO_EXPANSION_CONNECTOR
    return AWAITING_OWNER_ACQUISITION


def triage(candidates=None, pattern=None):
    """Partition the queue. Read-only; returns a report, writes nothing."""
    candidates = load_candidates(pattern) if candidates is None else candidates
    in_review = [c for c in candidates
                 if c.get("acquisitionStatus") == ac.STATUS_OWNER_REVIEW] \
        if hasattr(ac, "STATUS_OWNER_REVIEW") else \
        [c for c in candidates if c.get("acquisitionStatus") == "OWNER_REVIEW"]

    buckets = {}
    for candidate in in_review:
        bucket = bucket_of(candidate)
        entry = buckets.setdefault(bucket, {"count": 0, "byTrader": {}, "candidateIds": []})
        entry["count"] += 1
        trader = candidate.get("claimedTraderId") or "(unattributed)"
        entry["byTrader"][trader] = entry["byTrader"].get(trader, 0) + 1
        entry["candidateIds"].append(candidate["candidateId"])

    for bucket in buckets.values():
        bucket["candidateIds"].sort()

    decisions = sorted(
        buckets.get(AWAITING_OWNER_ACQUISITION, {}).get("byTrader", {}).items())
    return {
        "generated": True,
        "schemaVersion": SCHEMA_VERSION,
        "lane": "RESEARCH",
        "adjudicates": False,
        "mutatesCandidates": False,
        "candidatesInOwnerReview": len(in_review),
        "buckets": {name: {k: v for k, v in bucket.items()}
                     for name, bucket in sorted(buckets.items())},
        "bucketMeaning": {name: BUCKET_MEANING[name] for name in sorted(buckets)},
        # The headline: how many DECISIONS, against how many records.
        "distinctAcquisitionDecisions": len(decisions),
        "acquisitionDecisionsByTrader": dict(decisions),
        "note": ("Every candidate remains in OWNER_REVIEW. Governance requires an "
                  "active OwnerDecision to leave it, and this tool neither writes one "
                  "nor advances any status."),
    }


def render(report):
    lines = ["ACQUISITION TRIAGE -- read-only, adjudicates nothing, mutates nothing",
             "  candidates in OWNER_REVIEW: %d" % report["candidatesInOwnerReview"],
             "  distinct acquisition decisions: %d (against %d records)"
             % (report["distinctAcquisitionDecisions"], report["candidatesInOwnerReview"])]
    for name, bucket in report["buckets"].items():
        lines.append("  %-40s %3d  %s" % (name, bucket["count"],
                                           dict(sorted(bucket["byTrader"].items()))))
    lines.append("  " + report["note"])
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--write", action="store_true", help="write the report file")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = triage()
    print(json.dumps(report, indent=2, sort_keys=True) if args.json else render(report))
    if args.write:
        os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
        with open(REPORT_PATH, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, sort_keys=True)
            handle.write("\n")
        print("written to %s" % REPORT_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

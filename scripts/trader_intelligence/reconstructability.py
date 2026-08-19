#!/usr/bin/env python3
"""Which candidates could a strategy actually be REBUILT from? (MOGO-022)

WHY
---
Research effort is meant to be ranked by

    expected information value x evidence quality x reconstructability / cost

and none of those were computable. The candidate registry records what a source IS
-- title, publisher, dates, duration, attribution -- and nothing about whether its
content could support rebuilding a mechanical strategy. So "prioritise by
reconstructability" had no operand.

WHAT THIS IS NOT
----------------
Not a second registry. The registry in `docs/trader-intelligence/acquisition/` stays
authoritative; this DERIVES an assessment from it and writes one report. It creates
no candidate, mutates no record, and advances no status.

THE HONEST ANSWER COMES FIRST
-----------------------------
Reconstructability is a property of CONTENT. A candidate whose content was never
acquired cannot be assessed on it, and the assessment says UNKNOWN rather than
guessing from a title -- a video called "Stop Losses" is not evidence that it states
a stop rule. Where every candidate is metadata-only, the correct output is that the
binding constraint is ACQUISITION, not analysis, and the ranking cannot yet
discriminate. That is a finding, not a failure.

READ-ONLY. NO NETWORK ACCESS.
"""
import argparse
import glob as globmod
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
CANDIDATES_GLOB = os.path.join(
    REPO_ROOT, "docs", "trader-intelligence", "acquisition", "candidates", "*.json")
REPORT_PATH = os.path.join(
    REPO_ROOT, "docs", "trader-intelligence", "acquisition", "reports",
    "reconstructability-report.json")

SCHEMA_VERSION = "mogo.reconstructability.v1"

# The trade-level facts a mechanical reconstruction needs. Every one is a property
# of the CONTENT, so none can be established from registry metadata alone.
TRADE_FACTS = ("entry", "stop", "target", "outcome", "direction", "instrument",
               "timeframe", "timestamp")

# Assessment verdicts, most-blocking first.
CONTENT_NOT_ACQUIRED = "UNKNOWN_CONTENT_NOT_ACQUIRED"
CONTENT_NOT_RETRIEVABLE = "NOT_RECONSTRUCTABLE_CONTENT_UNRETRIEVABLE"
NO_TRADE_LEVEL_DETAIL = "NOT_RECONSTRUCTABLE_NO_TRADE_LEVEL_DETAIL"
PARTIAL = "PARTIALLY_RECONSTRUCTABLE"
RECONSTRUCTABLE = "RECONSTRUCTABLE"

VERDICT_MEANING = {
    CONTENT_NOT_ACQUIRED:
        "The content was never acquired, so reconstructability is UNKNOWN. It is not "
        "low -- it is unmeasured, and inferring it from a title would be exactly the "
        "mistake this assessment exists to avoid.",
    CONTENT_NOT_RETRIEVABLE:
        "Acquisition was attempted and the content cannot be retrieved by any "
        "available lawful route, so no amount of analysis will make this "
        "reconstructable.",
    NO_TRADE_LEVEL_DETAIL:
        "Content exists and states no trade-level facts -- no entry, stop, target or "
        "outcome that could anchor a mechanical rule.",
    PARTIAL:
        "Some trade-level facts are present and others are absent. Reconstruction "
        "would require inventing the missing ones, which is not permitted.",
    RECONSTRUCTABLE:
        "Enough trade-level fact is present to attempt a mechanical specification.",
}


def load_candidates(pattern=None):
    out = []
    for path in sorted(globmod.glob(pattern or CANDIDATES_GLOB)):
        with open(path, "r", encoding="utf-8") as handle:
            out.append(json.load(handle))
    return out


def content_acquired(candidate):
    """Has the content itself been obtained, as opposed to metadata about it?

    Deliberately conservative: METADATA_ONLY storage or an absent contentHash both
    mean no content is held, whatever else the record says.
    """
    if candidate.get("storagePolicy") == "METADATA_ONLY":
        return False
    return bool(candidate.get("contentHash"))


def assess(candidate):
    """One candidate. Pure. Returns (verdict, known_facts, unknown_facts)."""
    if not content_acquired(candidate):
        # Every trade-level fact is UNKNOWN, and stays that way. Nothing about a
        # title, duration or publish date bears on whether a stop rule is stated.
        return CONTENT_NOT_ACQUIRED, [], list(TRADE_FACTS)

    known, unknown = [], []
    facts = candidate.get("tradeFactsPresent") or {}
    for fact in TRADE_FACTS:
        (known if facts.get(fact) else unknown).append(fact)

    if not known:
        return NO_TRADE_LEVEL_DETAIL, known, unknown
    anchors = {"entry", "stop", "target", "outcome"}
    if anchors.issubset(set(known)):
        return RECONSTRUCTABLE, known, unknown
    return PARTIAL, known, unknown


def report(candidates=None, pattern=None):
    candidates = load_candidates(pattern) if candidates is None else candidates
    by_verdict, by_trader = {}, {}
    rows = []
    for candidate in candidates:
        verdict, known, unknown = assess(candidate)
        by_verdict[verdict] = by_verdict.get(verdict, 0) + 1
        trader = candidate.get("claimedTraderId") or "(unattributed)"
        by_trader.setdefault(trader, {}).setdefault(verdict, 0)
        by_trader[trader][verdict] += 1
        rows.append({"candidateId": candidate.get("candidateId"),
                     "claimedTraderId": candidate.get("claimedTraderId"),
                     "verdict": verdict,
                     "knownTradeFacts": known,
                     "unknownTradeFacts": unknown})

    assessable = sum(count for verdict, count in by_verdict.items()
                     if verdict != CONTENT_NOT_ACQUIRED)
    return {
        "generated": True,
        "schemaVersion": SCHEMA_VERSION,
        "lane": "RESEARCH",
        "adjudicates": False,
        "mutatesCandidates": False,
        "candidates": len(candidates),
        "byVerdict": dict(sorted(by_verdict.items())),
        "byTrader": {k: dict(sorted(v.items())) for k, v in sorted(by_trader.items())},
        "verdictMeaning": {v: VERDICT_MEANING[v] for v in sorted(by_verdict)},
        "assessableOnContent": assessable,
        # The operative sentence. Where nothing is assessable, ranking by
        # reconstructability cannot discriminate between candidates, and saying so is
        # more useful than emitting a spurious ordering.
        "bindingConstraint": (
            "ACQUISITION -- %d of %d candidates hold no acquired content, so "
            "reconstructability is UNKNOWN for them and cannot rank them. Analysis "
            "effort cannot change this; only obtaining content can."
            % (by_verdict.get(CONTENT_NOT_ACQUIRED, 0), len(candidates))
            if assessable == 0 else
            "ANALYSIS -- %d candidate(s) hold content and can be assessed on it."
            % assessable),
        "rows": rows,
    }


def render(r):
    lines = ["RECONSTRUCTABILITY -- derived, read-only, mutates nothing",
             "  candidates: %d" % r["candidates"]]
    for verdict, count in r["byVerdict"].items():
        lines.append("    %-44s %d" % (verdict, count))
    lines.append("  assessable on acquired content: %d" % r["assessableOnContent"])
    lines.append("  binding constraint: %s" % r["bindingConstraint"])
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--write", action="store_true", help="write the report file")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    r = report()
    print(json.dumps(r, indent=2, sort_keys=True) if args.json else render(r))
    if args.write:
        os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
        with open(REPORT_PATH, "w", encoding="utf-8") as handle:
            json.dump(r, handle, indent=2, sort_keys=True)
            handle.write("\n")
        print("written to %s" % REPORT_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

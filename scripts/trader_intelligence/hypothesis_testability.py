#!/usr/bin/env python3
"""Which hypotheses can actually be TESTED, and against what evidence (MOGO-022).

WHY
---
The corpus holds 641 hypotheses. Every one has `proposedReplayTest`,
`proposedPaperTest`, `independentVariables` and `dependentVariables` populated, and
every one is still `PROPOSED_UNVALIDATED`. Read as a table, that looks like 641
experiments waiting to be run.

They are not, and this module measures why rather than asserting it.

THE TWO THINGS THAT MAKE A HYPOTHESIS TESTABLE
----------------------------------------------
1. A test specification that describes THIS hypothesis. A specification shared
   verbatim by many hypotheses cannot discriminate between them -- running it
   against one tells you nothing you would not equally have "learned" about the
   other five hundred. This is detected by MEASUREMENT, not by a hardcoded list of
   known boilerplate: a spec is non-discriminating when the corpus itself repeats
   it. That definition keeps working when the templates change.

2. An evidence population appropriate to the question. A hypothesis derived from a
   human trader's CLAIMS is not tested by replaying MOGO's own implementation --
   that measures whether the implementation exhibits the property, which is a
   different question with a different answer. Where the only available evidence
   is MOGO's, this module says so instead of counting it as support.

WHAT IT DOES NOT DO
-------------------
It does not write, rewrite, or "improve" any hypothesis. Generating more specific
test text would manufacture the appearance of testability without adding evidence,
which is the precise failure it exists to detect. It classifies, and it states what
each hypothesis would NEED.

READ-ONLY. NO NETWORK ACCESS.
"""
import argparse
import collections
import glob as globmod
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trade_observation as to      # noqa: E402

REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
EVIDENCE_ROOT = to.EVIDENCE_ROOT
HYPOTHESES_GLOB = os.path.join(EVIDENCE_ROOT, "hypotheses", "*.json")

SCHEMA_VERSION = "mogo.hypothesis-testability.v1"

# Verdicts. Ordered most-blocking first; the first that applies is reported, so a
# hypothesis is never described as merely under-specified when its evidence does
# not exist either.
NO_EVIDENCE_POPULATION = "NOT_TESTABLE_NO_EVIDENCE_POPULATION"
UNRESOLVED_CONTRADICTION = "NOT_TESTABLE_UNRESOLVED_CONTRADICTION"
NON_DISCRIMINATING_TEST = "NOT_TESTABLE_NON_DISCRIMINATING_TEST"
TESTABLE_AGAINST_IMPLEMENTATION = "TESTABLE_AGAINST_IMPLEMENTATION_ONLY"
TESTABLE = "TESTABLE"

VERDICTS = (NO_EVIDENCE_POPULATION, UNRESOLVED_CONTRADICTION,
            NON_DISCRIMINATING_TEST, TESTABLE_AGAINST_IMPLEMENTATION, TESTABLE)

VERDICT_MEANING = {
    NO_EVIDENCE_POPULATION:
        "No trade observations exist for the actor whose claims produced this "
        "hypothesis. There is nothing to test it against, at any quality.",
    UNRESOLVED_CONTRADICTION:
        "Derived from a ContradictionRecord that is still open. Which of the two "
        "readings is being tested is not yet decided, and that is an owner decision.",
    NON_DISCRIMINATING_TEST:
        "The proposed test is shared verbatim with other hypotheses, so it does not "
        "describe an experiment specific to this one.",
    TESTABLE_AGAINST_IMPLEMENTATION:
        "Evidence exists, but only MOGO's own replay of its implementation. Running "
        "it measures whether the IMPLEMENTATION exhibits the property -- not whether "
        "the trader's stated rule holds. A result must not be reported as the latter.",
    TESTABLE:
        "A discriminating test specification and an appropriate evidence population "
        "both exist.",
}


def load_hypotheses(pattern=None):
    out = {}
    for path in sorted(globmod.glob(pattern or HYPOTHESES_GLOB)):
        with open(path, "r", encoding="utf-8") as handle:
            record = json.load(handle)
        out[record["hypothesisId"]] = record
    return out


def claim_actors(hypothesis):
    """The actors whose claims produced this hypothesis, read from claim ids."""
    actors = set()
    for claim_id in hypothesis.get("sourceClaimIds") or []:
        parts = claim_id.split("|")
        if len(parts) > 1:
            actors.add(parts[1])
    return actors


def _spec_of(hypothesis):
    """The fields that are supposed to make this hypothesis an experiment."""
    return json.dumps({
        "replay": hypothesis.get("proposedReplayTest"),
        "paper": hypothesis.get("proposedPaperTest"),
        "independent": hypothesis.get("independentVariables"),
        "dependent": hypothesis.get("dependentVariables"),
    }, sort_keys=True)


def discriminating_specs(hypotheses):
    """Specs that belong to exactly ONE hypothesis.

    Measured from the corpus rather than matched against known boilerplate: if two
    hypotheses carry the same specification, that specification does not identify
    an experiment for either of them, whatever its wording.
    """
    counts = collections.Counter(_spec_of(h) for h in hypotheses.values())
    return {spec for spec, n in counts.items() if n == 1}


def observation_actors(observations, sources):
    """Which actors/strategies we hold trade observations for, by population."""
    out = {}
    for record in (observations or {}).values():
        population = to.observation_population(record, sources)
        key = record.get("strategyId") or record.get("traderId") or record["actor"]
        out.setdefault(key, set()).add(population)
    return out


def assess(hypothesis, unique_specs, evidence_actors, human_actors):
    """Classify one hypothesis. Pure. Returns (primary verdict, blockers, actors).

    EVERY blocking condition is collected, not just the first. A TJR hypothesis is
    typically blocked BOTH by having no TJR trade evidence and by carrying a shared
    test specification; reporting only one would understate what it needs, and
    fixing that one would leave it exactly as untestable as before.
    """
    actors = claim_actors(hypothesis)
    blockers = []

    # Is there evidence for the actor this hypothesis is actually about? A human
    # trader's hypothesis needs that trader's trades; MOGO replaying its own engine
    # is a different actor answering a different question.
    human_evidence = any(a in evidence_actors for a in actors)
    if not human_evidence:
        blockers.append({
            "blocker": NO_EVIDENCE_POPULATION,
            "detail": "no trade observations for %s"
                      % (", ".join(sorted(actors)) or "an unattributed actor")})

    # An open contradiction is an owner decision, not a testing problem.
    for limitation in hypothesis.get("limitations") or []:
        if "ContradictionRecord" in limitation or "XCONTRA" in limitation:
            blockers.append({"blocker": UNRESOLVED_CONTRADICTION,
                             "detail": limitation})
            break

    # Does the test specification describe THIS hypothesis?
    if _spec_of(hypothesis) not in unique_specs:
        blockers.append({
            "blocker": NON_DISCRIMINATING_TEST,
            "detail": "test specification is shared verbatim with other hypotheses"})

    if not blockers:
        return TESTABLE, blockers, sorted(actors)

    # Evidence exists but only as MOGO's own implementation: reportable, with the
    # caveat that it measures the implementation rather than the trader's rule.
    only_evidence_kind = (len(blockers) == 1
                          and blockers[0]["blocker"] == NO_EVIDENCE_POPULATION
                          and bool(evidence_actors))
    if only_evidence_kind:
        return TESTABLE_AGAINST_IMPLEMENTATION, blockers, sorted(actors)

    for verdict in (NO_EVIDENCE_POPULATION, UNRESOLVED_CONTRADICTION,
                    NON_DISCRIMINATING_TEST):
        if any(b["blocker"] == verdict for b in blockers):
            return verdict, blockers, sorted(actors)
    return TESTABLE, blockers, sorted(actors)


def triage(hypotheses=None, observations=None, sources=None):
    """Classify every hypothesis. Read-only; writes nothing."""
    hypotheses = load_hypotheses() if hypotheses is None else hypotheses
    sources = to.load_sources() if sources is None else sources
    observations = to.load_observations() if observations is None else observations

    unique_specs = discriminating_specs(hypotheses)
    evidence_actors = observation_actors(observations, sources)
    human_actors = {a for h in hypotheses.values() for a in claim_actors(h)}

    results = {}
    for hypothesis_id in sorted(hypotheses):
        verdict, blockers, actors = assess(
            hypotheses[hypothesis_id], unique_specs, evidence_actors, human_actors)
        results[hypothesis_id] = {
            "hypothesisId": hypothesis_id,
            "verdict": verdict,
            "verdictMeaning": VERDICT_MEANING[verdict],
            "claimActors": actors,
            "blockers": blockers,
            "blockerCount": len(blockers),
        }
    return results


def what_is_still_required(hypotheses=None, observations=None, sources=None):
    """The MOGO-022 priority-7 question, answered from the corpus.

    What evidence would have to exist before these hypotheses could be tested?
    """
    hypotheses = load_hypotheses() if hypotheses is None else hypotheses
    sources = to.load_sources() if sources is None else sources
    observations = to.load_observations() if observations is None else observations
    results = triage(hypotheses, observations, sources)

    by_verdict = collections.Counter(r["verdict"] for r in results.values())
    # Counted from ALL blockers, not just the primary verdict: a hypothesis blocked
    # on both missing evidence and a shared spec needs both fixed.
    by_blocker = collections.Counter(
        b["blocker"] for r in results.values() for b in r["blockers"])
    missing_evidence_for = collections.Counter()
    for result in results.values():
        if any(b["blocker"] == NO_EVIDENCE_POPULATION for b in result["blockers"]):
            for actor in result["claimActors"] or ["UNATTRIBUTED"]:
                missing_evidence_for[actor] += 1

    evidence_actors = observation_actors(observations, sources)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "lane": "RESEARCH",
        "adjudicates": False,
        "hypotheses": len(hypotheses),
        "byVerdict": dict(by_verdict),
        "byBlocker": dict(by_blocker),
        "discriminatingSpecifications": len(discriminating_specs(hypotheses)),
        "tradeObservationsHeldFor": {
            actor: sorted(pops) for actor, pops in sorted(evidence_actors.items())},
        "hypothesesBlockedOnMissingActorEvidence": dict(missing_evidence_for),
    }


def render(summary):
    lines = ["HYPOTHESIS TESTABILITY -- derived, read-only, adjudicates nothing",
             "  hypotheses: %d" % summary["hypotheses"],
             "  test specifications unique to one hypothesis: %d of %d"
             % (summary["discriminatingSpecifications"], summary["hypotheses"]),
             "  by verdict:"]
    for verdict, count in sorted(summary["byVerdict"].items(),
                                 key=lambda kv: (-kv[1], kv[0])):
        lines.append("    %-42s %d" % (verdict, count))
    lines.append("  by blocker (a hypothesis may carry more than one):")
    for blocker, count in sorted(summary["byBlocker"].items(),
                                 key=lambda kv: (-kv[1], kv[0])):
        lines.append("    %-42s %d" % (blocker, count))
    lines.append("  trade observations held for:")
    for actor, pops in summary["tradeObservationsHeldFor"].items():
        lines.append("    %-24s %s" % (actor, ", ".join(pops)))
    if summary["hypothesesBlockedOnMissingActorEvidence"]:
        lines.append("  blocked purely on missing evidence for that actor:")
        for actor, count in sorted(
                summary["hypothesesBlockedOnMissingActorEvidence"].items(),
                key=lambda kv: (-kv[1], kv[0])):
            lines.append("    %-24s %d" % (actor, count))
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--json", action="store_true", help="machine-readable")
    args = parser.parse_args(argv)
    summary = what_is_still_required()
    print(json.dumps(summary, indent=2, sort_keys=True) if args.json
          else render(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

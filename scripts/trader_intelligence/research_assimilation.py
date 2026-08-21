#!/usr/bin/env python3
"""What does MOGO know after this trade that it could not know before? (MOGO-022)

THE GAP THIS CLOSES
-------------------
Preservation and import were automatic; ASSIMILATION was not. `import_mogo_observations`
imports only `trade_observation`, `evidence_common` and `graph_common` -- it never
reaches `population_fidelity`, `hypothesis_testability` or `decision_difference`. So a
close became a stored record and stopped there, and every statement about what the
corpus now supports was produced by hand. Storage is not learning.

WHAT THIS IS NOT
----------------
Not a research engine. It ORCHESTRATES the existing analyzers and records what their
output was, and how it changed. Every number here is computed by a module that already
existed and is already tested; nothing new is inferred.

EXACTLY-ONCE SCIENTIFIC EFFECT
------------------------------
Processing may happen any number of times; the scientific effect happens once. The
corpus fingerprint -- the sorted set of observation ids and their source content hashes
-- is the key. Re-running against an unchanged corpus writes no ledger record at all,
so a retry, a restart, or a double invocation cannot double-count.

"NOTHING CHANGED" IS A RESULT
-----------------------------
A close that moves no statistic and touches no hypothesis is recorded as
NO_SCIENTIFIC_CHANGE. MOGO must never manufacture a lesson because a trade occurred.

READ-ONLY over the corpus. Writes only its own derived state and its own append-only
ledger. NO NETWORK ACCESS.
"""
import argparse
import copy
import glob as globmod
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trade_observation as to            # noqa: E402
import population_fidelity as pf          # noqa: E402
import hypothesis_testability as ht       # noqa: E402

REPO_ROOT = to.REPO_ROOT if hasattr(to, "REPO_ROOT") else os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
STATE_ROOT = os.path.join(REPO_ROOT, "docs", "trader-intelligence", "research-state")
CURRENT_STATE = os.path.join(STATE_ROOT, "current-state.json")
LEDGER_DIR = os.path.join(STATE_ROOT, "ledger")

SCHEMA_VERSION = "mogo.research-assimilation.v1"
LANE = "RESEARCH"

# The learning classification. Lettered to match the milestone definition; a record
# may carry several. NO_SCIENTIFIC_CHANGE is an acceptable and expected outcome.
UPDATES_DESCRIPTIVE_STATISTICS = "A_UPDATES_DESCRIPTIVE_STATISTICS"
CHANGES_COHORT = "B_CHANGES_COMPARISON_COHORT"
SUPPORTS_HYPOTHESIS = "C_SUPPORTS_HYPOTHESIS"
CONTRADICTS_HYPOTHESIS = "D_CONTRADICTS_HYPOTHESIS"
CHANGES_CONFIDENCE = "E_CHANGES_CONFIDENCE"
LEAVES_HYPOTHESES_UNCHANGED = "F_LEAVES_HYPOTHESES_UNCHANGED"
GENERATES_CANDIDATE_QUESTION = "G_GENERATES_CANDIDATE_QUESTION"
REVEALS_EVIDENCE_DEFICIENCY = "H_REVEALS_EVIDENCE_DEFICIENCY"
WINNER_LOSER_EVIDENCE = "I_WINNER_LOSER_EVIDENCE"
NO_SCIENTIFIC_CHANGE = "J_NO_SCIENTIFIC_CHANGE"


class AssimilationRefused(Exception):
    """Raised rather than guessing."""


def _canonical(obj):
    """Canonical bytes for hashing: keys sorted recursively, arrays left alone."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def corpus_fingerprint(observations, sources):
    """Identity of the evidence set. Changes when ANY of it changes.

    Hashes each observation RECORD IN FULL, plus the source record its population
    is derived from. Both halves were learned the hard way.

    The first version hashed the id, the stored `sourceContentHash`, and the derived
    population. That looked sufficient and was not: `sourceContentHash` is a COPY of
    the upstream package's hash, not a hash of the observation, so editing
    `rMultiple`, `outcome` or `pnl` in place left the fingerprint identical. Worse
    than a missed detection -- the `already_recorded` short-circuit then OVERRODE
    classify(), so a real computed change was actively suppressed and the ledger
    asserted "no change" while forward meanR moved from -0.149302 to +0.172127.
    Demonstrated on the real corpus by an independent verifier.

    That is not hypothetical: `import_mogo_observations.backfill_mapped_fields`
    performs exactly this class of edit, and its widening-only guard REQUIRES
    `sourceContentHash` to be unchanged.

    The source record is folded in because population is derived from it -- a source
    retyped within its own class changes what the evidence means without touching
    any observation.
    """
    parts = []
    for observation_id in sorted(observations or {}):
        record = observations[observation_id]
        source = (sources or {}).get(record.get("sourceId")) or {}
        parts.append(b"|".join([
            observation_id.encode("utf-8"),
            hashlib.sha256(_canonical(record)).hexdigest().encode("utf-8"),
            hashlib.sha256(_canonical(source)).hexdigest().encode("utf-8"),
            to.observation_population(record, sources).encode("utf-8"),
        ]))
    return hashlib.sha256(b"\n".join(parts)).hexdigest()


def _population_stats(records):
    """Descriptive only, and only over fields actually present."""
    r_multiples = [r["rMultiple"] for r in records if r.get("rMultiple") is not None]
    outcomes = {}
    unknown_fields = {}
    for record in records:
        outcome = record.get("outcome")
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
        for field in record.get("unknowns") or []:
            unknown_fields[field] = unknown_fields.get(field, 0) + 1
    stats = {
        "n": len(records),
        "byOutcome": outcomes,
        "rMultipleCount": len(r_multiples),
        "unknownFieldCounts": unknown_fields,
    }
    if r_multiples:
        stats["meanR"] = round(sum(r_multiples) / len(r_multiples), 6)
        stats["worstR"] = min(r_multiples)
        stats["bestR"] = max(r_multiples)
        wins = [v for v in r_multiples if v > 0]
        stats["winCount"] = len(wins)
        # Deliberately not called "win rate": it is the rate over the PRESERVED
        # subset, which is not the account (backlog B-22).
        stats["winShareOfPreserved"] = round(len(wins) / len(r_multiples), 6)
    return stats


def research_state(observations=None, sources=None):
    """The full derived research state. Pure; writes nothing."""
    sources = to.load_sources() if sources is None else sources
    observations = to.load_observations() if observations is None else observations

    by_population = {}
    by_strategy = {}
    for record in observations.values():
        population = to.observation_population(record, sources)
        by_population.setdefault(population, []).append(record)
        key = record.get("strategyId") or record.get("traderId") or record.get("actor")
        by_strategy.setdefault((key, population), []).append(record)

    fidelity = {}
    for strategy in sorted({k for k, _p in by_strategy}):
        if not strategy:
            continue
        report = pf.compare(observations, sources, strategy)
        fidelity[strategy] = {
            "populationsPresent": report["populationsPresent"],
            "findings": sorted(f["code"] for f in report["findings"]),
            "agreements": sorted(a["code"] for a in report.get("agreements") or []),
        }

    testability = ht.what_is_still_required(observations=observations, sources=sources)

    return {
        "schemaVersion": SCHEMA_VERSION,
        "lane": LANE,
        "adjudicates": False,
        "corpusFingerprint": corpus_fingerprint(observations, sources),
        "observationTotal": len(observations),
        "byPopulation": {population: _population_stats(records)
                          for population, records in sorted(by_population.items())},
        "byStrategyAndPopulation": {
            "%s|%s" % (strategy, population): len(records)
            for (strategy, population), records in sorted(
                by_strategy.items(), key=lambda kv: (str(kv[0][0]), kv[0][1]))},
        "fidelity": fidelity,
        "hypotheses": {
            "total": testability["hypotheses"],
            "byVerdict": testability["byVerdict"],
            "byBlocker": testability["byBlocker"],
            "discriminatingSpecifications": testability["discriminatingSpecifications"],
            "evidenceHeldFor": testability["tradeObservationsHeldFor"],
        },
    }


def _diff_numbers(before, after, path=""):
    """Every leaf that changed, as path -> (before, after). Order-independent."""
    changes = {}
    keys = set(before or {}) | set(after or {})
    # Sorted by a TOTAL order. Plain `sorted` raises TypeError the moment a group
    # key is None -- which happens whenever the corpus holds a record with no
    # `outcome`, because the statistics group by it. That crash escaped
    # `run_integrity_checks` before the report was written, leaving the previous
    # run's clean report on disk for other tooling to read: the same
    # crash-leaves-a-stale-all-clear shape as the NaN case (B-32.18).
    for key in sorted(keys, key=lambda k: (k is None, str(k))):
        here = "%s.%s" % (path, key) if path else str(key)
        b, a = (before or {}).get(key), (after or {}).get(key)
        if isinstance(b, dict) or isinstance(a, dict):
            changes.update(_diff_numbers(b or {}, a or {}, here))
        elif b != a:
            changes[here] = {"before": b, "after": a}
    return changes


def classify(before, after):
    """Which kinds of learning this change represents. Evidence-driven, not narrative.

    A classification is asserted only where the state actually moved. If nothing
    moved, the answer is NO_SCIENTIFIC_CHANGE and that is a legitimate result.
    """
    if before is None:
        # First run has no prior state to compare against, so it establishes a
        # baseline rather than demonstrating a change.
        return ["BASELINE_ESTABLISHED"], {}

    changes = _diff_numbers(before, after)
    changes.pop("corpusFingerprint", None)
    if not changes:
        return [NO_SCIENTIFIC_CHANGE], {}

    kinds = []
    populations_changed = any(k.startswith("byPopulation.") for k in changes)
    cohort_changed = any(k.startswith("byStrategyAndPopulation") for k in changes)
    fidelity_changed = any(k.startswith("fidelity.") for k in changes)
    verdicts_changed = any(k.startswith("hypotheses.byVerdict") for k in changes)
    blockers_changed = any(k.startswith("hypotheses.byBlocker") for k in changes)
    unknowns_grew = any(".unknownFieldCounts." in k and
                        (changes[k]["after"] or 0) > (changes[k]["before"] or 0)
                        for k in changes)
    outcomes_changed = any(".byOutcome." in k for k in changes)

    if populations_changed:
        kinds.append(UPDATES_DESCRIPTIVE_STATISTICS)
    if cohort_changed:
        kinds.append(CHANGES_COHORT)
    if outcomes_changed:
        kinds.append(WINNER_LOSER_EVIDENCE)
    if fidelity_changed:
        # A fidelity finding appearing or disappearing is a claim about the
        # instrument, which is exactly the kind of thing worth a question.
        kinds.append(GENERATES_CANDIDATE_QUESTION)
    if verdicts_changed:
        kinds.append(CHANGES_CONFIDENCE)
    if blockers_changed:
        kinds.append(CHANGES_CONFIDENCE)
    if unknowns_grew:
        kinds.append(REVEALS_EVIDENCE_DEFICIENCY)
    if not verdicts_changed and not blockers_changed:
        # Stated explicitly rather than left implicit: new evidence that moves no
        # hypothesis is the ordinary case here, and saying so is the honest result.
        kinds.append(LEAVES_HYPOTHESES_UNCHANGED)

    seen, ordered = set(), []
    for kind in kinds:
        if kind not in seen:
            seen.add(kind)
            ordered.append(kind)
    return ordered, changes


def load_current_state(path=None):
    path = path or CURRENT_STATE
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def ledger_records(ledger_dir=None):
    out = []
    for path in sorted(globmod.glob(os.path.join(ledger_dir or LEDGER_DIR, "*.json"))):
        with open(path, "r", encoding="utf-8") as handle:
            out.append(json.load(handle))
    return out


def assimilate(now, observations=None, sources=None, write=False,
               state_path=None, ledger_dir=None):
    """Compute the state, compare it to the last one, and record the difference.

    Returns the learning record. Writes only when `write` is set AND the corpus
    fingerprint actually moved -- that conjunction is the exactly-once guarantee.
    """
    if now is None:
        raise AssimilationRefused("a timestamp is required; assimilation is dated")
    state_path = state_path or CURRENT_STATE
    ledger_dir = ledger_dir or LEDGER_DIR

    # `before` is read FIRST. Computing `after` first opened a window in which a
    # concurrent run could record and update the state, leaving this run to compare
    # a fresh `after` against a newer `before` and emit a ledger record asserting
    # the forward cohort SHRANK -- a transition that never happened.
    before = load_current_state(state_path)
    after = research_state(observations, sources)

    already_recorded = bool(before) and before.get("corpusFingerprint") == after["corpusFingerprint"]
    kinds, changes = ([NO_SCIENTIFIC_CHANGE], {}) if already_recorded else classify(before, after)

    record = {
        "generated": True,
        "schemaVersion": SCHEMA_VERSION,
        "lane": LANE,
        "adjudicates": False,
        "assimilatedAt": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "corpusFingerprintBefore": (before or {}).get("corpusFingerprint"),
        "corpusFingerprintAfter": after["corpusFingerprint"],
        "corpusChanged": not already_recorded,
        "observationTotalBefore": (before or {}).get("observationTotal"),
        "observationTotalAfter": after["observationTotal"],
        "learningKinds": kinds,
        "changedState": changes,
        # What may now be claimed, and what may not. Both are recorded, because a
        # result that only lists what improved reads as though every trade taught
        # something.
        "legitimateConclusion": _conclusion(before, after, kinds, changes),
        "nonConclusion": _non_conclusion(after),
    }

    if write and not already_recorded:
        os.makedirs(ledger_dir, exist_ok=True)
        # NAMED BY THE TRANSITION IT RECORDS, not by a counter. Two consequences,
        # both of which were real defects in the counter version:
        #
        #  * Interruption cannot double-record. The old order wrote the ledger
        #    first and current-state.json second; crashing between them left the
        #    scientific effect recorded and the suppressor absent, so the retry
        #    wrote a SECOND record asserting the same transition. Verified. A
        #    content-derived name makes the retry land on the same file.
        #  * `len(glob(...)) + 1` was computed non-atomically, so two same-day runs
        #    picked the same sequence and the second silently replaced the first --
        #    falsifying "append-only" -- and removing any file reused a name.
        name = "LEARN_%s_%s.json" % (now.strftime("%Y%m%d"),
                                      after["corpusFingerprint"][:12])
        with open(os.path.join(ledger_dir, name), "w", encoding="utf-8") as handle:
            json.dump(record, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.makedirs(os.path.dirname(state_path), exist_ok=True)
        with open(state_path, "w", encoding="utf-8") as handle:
            json.dump(after, handle, indent=2, sort_keys=True)
            handle.write("\n")
        record["ledgerRecord"] = name
    return record


def _conclusion(before, after, kinds, changes):
    if NO_SCIENTIFIC_CHANGE in kinds:
        return ("No change to the evidence set, so nothing may be claimed that could "
                "not be claimed before.")
    if "BASELINE_ESTABLISHED" in kinds:
        return ("Baseline established. No prior state existed to compare against, so "
                "this run asserts no learning.")
    forward = after["byPopulation"].get(to.FORWARD, {})
    claims = ["Forward observations: %d." % forward.get("n", 0)]
    if UPDATES_DESCRIPTIVE_STATISTICS in kinds:
        claims.append("Descriptive statistics over the PRESERVED forward subset moved.")
    if LEAVES_HYPOTHESES_UNCHANGED in kinds:
        claims.append("No hypothesis changed verdict: the corpus still holds no "
                      "trade evidence for any human trader, which is what blocks them.")
    return " ".join(claims)


def _non_conclusion(after):
    return [
        "Forward statistics describe the PRESERVED subset, not the account: the "
        "oldest closes minted no evidence package (backlog B-22).",
        "Nothing here is evidence about any human trader. `alex_g_sr_v1` is MOGO's "
        "implementation of a published method, not the person who published it.",
        "A change in descriptive statistics is not a finding about strategy "
        "performance; no strategy rule is altered by any observation.",
    ]


def render(record):
    lines = ["RESEARCH ASSIMILATION -- derived, read-only, adjudicates nothing",
             "  corpus changed: %s" % record["corpusChanged"],
             "  observations: %s -> %s" % (record["observationTotalBefore"],
                                            record["observationTotalAfter"]),
             "  learning:"]
    for kind in record["learningKinds"]:
        lines.append("    %s" % kind)
    if record["changedState"]:
        lines.append("  state that moved (%d leaf changes):" % len(record["changedState"]))
        for path in sorted(record["changedState"])[:12]:
            change = record["changedState"][path]
            lines.append("    %-52s %s -> %s" % (path, change["before"], change["after"]))
        if len(record["changedState"]) > 12:
            lines.append("    ... and %d more" % (len(record["changedState"]) - 12))
    lines.append("  conclusion: %s" % record["legitimateConclusion"])
    lines.append("  NOT supported:")
    for item in record["nonConclusion"]:
        lines.append("    - %s" % item)
    if record.get("ledgerRecord"):
        lines.append("  written: %s" % record["ledgerRecord"])
    return "\n".join(lines)


def main(argv=None):
    import datetime
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--write", action="store_true",
                        help="record the learning and update the durable state")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    now = datetime.datetime.now(datetime.timezone.utc)
    record = assimilate(now, write=args.write)
    print(json.dumps(record, indent=2, sort_keys=True) if args.json else render(record))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

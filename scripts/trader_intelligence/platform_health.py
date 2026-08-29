#!/usr/bin/env python3
"""Is MOGO actually operating correctly? ONE auditable answer. (MOGO-023)

WHY THIS EXISTS
---------------
MOGO's health was spread across `forward_capture.sh`, `mogo_observation_coverage.js`,
three validators, `observation_graph_reconcile.py`, `forward_coverage.py` and
`observation_integrity.py`. Each answers one question well. **Nothing answered the whole
question**, so establishing "is MOGO operating correctly?" meant a human running seven
tools and holding the result in their head -- which is exactly the state INC-006 exposed,
where a total provider outage looked like a quiet market for as long as nobody looked.

THE RULE THAT SHAPES EVERYTHING HERE
------------------------------------
**A green indicator must mean an invariant was POSITIVELY ESTABLISHED, never that no
exception was thrown.** So this module has four states, not two, and the fourth is
load-bearing:

  GREEN    the invariant was checked and holds
  YELLOW   degraded, but the affected surface is isolated and the rest stays valid
  RED      a critical function cannot be trusted
  UNKNOWN  health could not be established

**UNKNOWN NEVER AGGREGATES TO GREEN.** A check that cannot run reports UNKNOWN and the
overall verdict absorbs it. This is deliberate and is the single property most worth
protecting here: the failure mode being designed against is a dashboard that reads GREEN
because a probe silently did nothing.

WHAT IT DELIBERATELY DOES NOT CLAIM
-----------------------------------
This is a HOST-SIDE authority. It reads the repository, the corpus, and filesystem
metadata. It does **not** read the live engine: MOGO is a browser application, CDP is not
exposed, and INC-004 forbids driving the operator's profile. Anything that can only be
established inside the running tab -- whether authenticated candle acquisition is
currently succeeding, whether a sweep evaluated this minute -- is reported **UNKNOWN with
the reason**, not assumed. Reporting UNKNOWN honestly is the point; guessing GREEN there
would reproduce the exact defect this file exists to prevent.

Network probes are OFF by default and produce UNKNOWN until `--network` is passed, so an
offline run can never silently claim the provider is fine.

READ-ONLY. Writes nothing unless --write. Never touches the corpus.
"""
import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trade_observation as to          # noqa: E402
import observation_integrity as oi      # noqa: E402

REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
REPORT_PATH = os.path.join(REPO_ROOT, "docs", "trader-intelligence", "evidence",
                           "reports", "platform-health-report.json")
SCHEMA_VERSION = "mogo.platform-health.v1"

GREEN, YELLOW, RED, UNKNOWN = "GREEN", "YELLOW", "RED", "UNKNOWN"

#: Severity order for aggregation. RED outranks UNKNOWN because an established failure is
#: more actionable than an unestablished one -- but UNKNOWN outranks YELLOW and GREEN, so
#: an unrunnable check can never be smoothed away by healthy neighbours.
_RANK = {GREEN: 0, YELLOW: 1, UNKNOWN: 2, RED: 3}

#: The live MOGO origin store. Only its filesystem METADATA is read (existence, mtime) --
#: never its contents, which would cross the privacy boundary declined in MOGO-022.
LIVE_STORE = os.path.expanduser(
    "~/Library/Application Support/Google/Chrome/Profile 2/IndexedDB/"
    "https_joemogo.github.io_0.indexeddb.leveldb")

#: Beyond this, a store that is not being written is worth surfacing. Not a failure on its
#: own: an operator-initiated shutdown is KNOWN DOWNTIME, not an engine fault, and the
#: FX market is closed all weekend. So this yields YELLOW and says which it cannot tell.
STORE_STALE_AFTER_HOURS = 12.0


def _check(name, state, summary, evidence=None, remedy=None):
    return {"check": name, "state": state, "summary": summary,
            "evidence": evidence or {}, "remedy": remedy}


def _now(clock=None):
    return clock if clock is not None else datetime.datetime.now(datetime.timezone.utc)


# ---------------------------------------------------------------------------
# Checks. Each returns exactly one _check(). A check that CANNOT establish its
# invariant returns UNKNOWN -- never GREEN, and never a silent pass.
# ---------------------------------------------------------------------------

def check_observation_population(observations, sources):
    """The corpus loads, and every observation is classifiable into a population."""
    try:
        if not observations:
            return _check("observation_population", RED,
                          "no observations loaded from the corpus",
                          remedy="verify docs/trader-intelligence/evidence/observations/")
        counts = {}
        unknown_pop = []
        for record in observations.values():
            pop = to.observation_population(record, sources)
            counts[pop] = counts.get(pop, 0) + 1
            if pop not in (to.FORWARD, to.HISTORICAL, to.RECONSTRUCTED):
                unknown_pop.append(record.get("observationId"))
        if unknown_pop:
            return _check("observation_population", RED,
                          "%d observation(s) cannot be classified into a population"
                          % len(unknown_pop),
                          {"unclassifiable": unknown_pop[:10], "counts": counts},
                          "an unclassifiable observation cannot be attributed to replay "
                          "or forward evidence and must not enter any population")
        return _check("observation_population", GREEN,
                      "%d observations, all classified" % len(observations),
                      {"counts": counts})
    except Exception as exc:                                       # noqa: BLE001
        return _check("observation_population", UNKNOWN,
                      "the population check itself failed: %s" % type(exc).__name__)


def check_strategy_attribution(observations):
    """Every observation names a strategy. An unattributed record is never guessed."""
    try:
        composition = {}
        for record in observations.values():
            composition[oi.__dict__.get("_x") or _strategy(record)] = \
                composition.get(_strategy(record), 0) + 1
        unattributed = composition.get(UNATTRIBUTED_KEY, 0)
        if unattributed:
            return _check("strategy_attribution", RED,
                          "%d observation(s) carry no strategy identity" % unattributed,
                          {"composition": composition},
                          "an unattributed record cannot be excluded from another "
                          "strategy's population, so no strategy figure is safe")
        return _check("strategy_attribution", GREEN,
                      "all observations attributed across %d strateg%s"
                      % (len(composition), "y" if len(composition) == 1 else "ies"),
                      {"composition": composition})
    except Exception as exc:                                       # noqa: BLE001
        return _check("strategy_attribution", UNKNOWN,
                      "the attribution check itself failed: %s" % type(exc).__name__)


UNATTRIBUTED_KEY = "UNATTRIBUTED"


def _strategy(record):
    value = (record or {}).get("strategyId")
    return value if isinstance(value, str) and value else UNATTRIBUTED_KEY


def check_observation_integrity(observations, sources):
    """No preserved observation contradicts itself.

    A violation is YELLOW, not RED: the record is isolated and excluded from the
    authoritative population, and every remaining figure stays valid. Calling it RED
    would create pressure to 'fix' preserved evidence, which must never happen.
    """
    try:
        report = oi.report(observations, sources, population=to.FORWARD)
        excluded = report["excludedFromAuthoritative"]["n"]
        if excluded:
            return _check("observation_integrity", YELLOW,
                          "%d forward observation(s) excluded from the authoritative "
                          "population" % excluded,
                          {"raw": report["rawPreservedPopulation"],
                           "authoritative": report["authoritativeVerifiedPopulation"],
                           "findings": [f["observationId"] for f in report["findings"]]},
                          "quote the authoritative figure, never the raw one, and never "
                          "repair the record to make the count tidy")
        return _check("observation_integrity", GREEN,
                      "no field-consistency violations in the forward population",
                      {"authoritative": report["authoritativeVerifiedPopulation"]})
    except Exception as exc:                                       # noqa: BLE001
        return _check("observation_integrity", UNKNOWN,
                      "the integrity check itself failed: %s" % type(exc).__name__)


def check_live_store(store_path=None, clock=None, stale_hours=None):
    """Is the MOGO origin store present, and is it being written?

    Reads filesystem METADATA ONLY -- existence and mtime. Never opens the store.
    """
    path = LIVE_STORE if store_path is None else store_path
    stale_hours = STORE_STALE_AFTER_HOURS if stale_hours is None else stale_hours
    try:
        if not os.path.isdir(path):
            return _check("live_store", UNKNOWN,
                          "the MOGO origin store is not present at the expected path",
                          {"path": path},
                          "this machine may not be the operator's, or Chrome's profile "
                          "layout changed. Absence here is NOT evidence the engine is down")
        mtime = datetime.datetime.fromtimestamp(os.path.getmtime(path),
                                                datetime.timezone.utc)
        age_h = (_now(clock) - mtime).total_seconds() / 3600.0
        evidence = {"path": path, "mtimeUtc": mtime.isoformat(),
                    "ageHours": round(age_h, 3)}
        if age_h > stale_hours:
            return _check("live_store", YELLOW,
                          "the origin store has not been written for %.1f hours" % age_h,
                          evidence,
                          "cannot distinguish operator-initiated downtime (known, valid) "
                          "from a closed tab. Confirm the tab before treating as a fault")
        return _check("live_store", GREEN,
                      "origin store written %.2f hours ago" % age_h, evidence)
    except Exception as exc:                                       # noqa: BLE001
        return _check("live_store", UNKNOWN,
                      "the live-store check itself failed: %s" % type(exc).__name__)


def check_provider(enabled=False, url=None, timeout=15):
    """Provider transport reachability. OFF unless explicitly enabled.

    Establishes ONLY that the host answers. A 401 to an unauthenticated probe means the
    origin is healthy -- it does NOT mean authenticated candle acquisition is working, and
    this check must never be read as saying so. INC-006's 520 is exactly what it catches.
    """
    if not enabled:
        return _check("provider_transport", UNKNOWN,
                      "not probed (pass --network to enable)",
                      remedy="an unprobed provider is UNKNOWN, never GREEN")
    target = url or ("https://api-fxpractice.oanda.com/v3/instruments/"
                     "EUR_USD/candles?count=220&granularity=H1&price=M")
    try:
        out = subprocess.run(
            ["curl", "-s", "-o", os.devnull, "-w", "%{http_code}",
             "--max-time", str(timeout), target],
            capture_output=True, text=True, timeout=timeout + 10)
        code = (out.stdout or "").strip()
    except Exception as exc:                                       # noqa: BLE001
        return _check("provider_transport", RED,
                      "the provider probe could not run: %s" % type(exc).__name__)
    evidence = {"httpStatus": code, "probe": "unauthenticated"}
    if code in ("401", "403"):
        return _check("provider_transport", GREEN,
                      "provider answered %s to an unauthenticated probe -- origin healthy"
                      % code, evidence,
                      "this does NOT establish that authenticated candle acquisition "
                      "succeeds; that is only observable inside the running engine")
    if code == "000":
        return _check("provider_transport", RED,
                      "no response from the provider", evidence)
    if code.startswith("5"):
        return _check("provider_transport", RED,
                      "provider origin error HTTP %s -- this is the INC-006 signature"
                      % code, evidence,
                      "fail closed. Do NOT weaken the candle contract or fail over to "
                      "the live host to restore evaluations")
    return _check("provider_transport", UNKNOWN,
                  "unexpected probe status HTTP %s" % code, evidence)


def check_engine_evaluation():
    """Is the engine evaluating right now? NOT ESTABLISHABLE from the host.

    Present deliberately. Omitting it would make the report look complete while the single
    most operationally important question went unasked -- and an unasked question rendering
    as health is the defect this module exists to prevent.
    """
    return _check("engine_evaluation", UNKNOWN,
                  "not observable from the host",
                  {"reason": "MOGO is a browser application; CDP is not exposed and "
                             "INC-004 forbids driving the operator's profile"},
                  "confirm in the UI: the ADR-011 suppression banner names the transport "
                  "reason per pair since v12.40.0")


CHECKS_REQUIRING_CORPUS = (check_observation_population, check_strategy_attribution,
                           check_observation_integrity)


def overall(checks):
    """Worst state wins. UNKNOWN can never be smoothed into GREEN by healthy neighbours."""
    if not checks:
        return UNKNOWN
    return max((c["state"] for c in checks), key=lambda s: _RANK.get(s, _RANK[UNKNOWN]))


def report(observations=None, sources=None, network=False, store_path=None, clock=None):
    sources = to.load_sources() if sources is None else sources
    observations = to.load_observations() if observations is None else observations

    checks = [check_observation_population(observations, sources),
              check_strategy_attribution(observations),
              check_observation_integrity(observations, sources),
              check_live_store(store_path=store_path, clock=clock),
              check_provider(enabled=network),
              check_engine_evaluation()]

    state = overall(checks)
    return {
        "generated": True,
        "schemaVersion": SCHEMA_VERSION,
        "lane": "RESEARCH",
        "adjudicates": False,
        "overall": state,
        "checks": checks,
        "counts": {s: sum(1 for c in checks if c["state"] == s)
                   for s in (GREEN, YELLOW, RED, UNKNOWN)},
        "doesNotSupport": [
            "GREEN here means the checks BELOW were established, not that MOGO is "
            "trading correctly. Whether the engine is evaluating this minute is "
            "UNKNOWN from the host and is reported as such.",
            "A provider answering an unauthenticated probe is transport reachability "
            "ONLY. It does not establish authenticated candle acquisition.",
            "This report is derived from the corpus and filesystem metadata. It reads "
            "no browser storage contents and drives no browser.",
        ],
    }


def render(r):
    icon = {GREEN: "GREEN  ", YELLOW: "YELLOW ", RED: "RED    ", UNKNOWN: "UNKNOWN"}
    lines = ["MOGO PLATFORM HEALTH -- derived, read-only, adjudicates nothing",
             "  OVERALL: %s   (%s)"
             % (r["overall"],
                ", ".join("%s %d" % (s, r["counts"][s])
                          for s in (GREEN, YELLOW, RED, UNKNOWN) if r["counts"][s]))]
    for c in r["checks"]:
        lines.append("  [%s] %-24s %s" % (icon.get(c["state"], "?"), c["check"],
                                          c["summary"]))
        if c.get("remedy"):
            lines.append("      -> %s" % c["remedy"])
    return "\n".join(lines)


def selftest():
    """Prove each check CAN fail. A health monitor nobody has seen go red is a decoration.

    Bounded failure injection, in-process, touching nothing on disk.
    """
    results = []

    def t(name, ok, detail=""):
        results.append((name, bool(ok), detail))

    src = {"S|F": {"sourceId": "S|F", "sourceType": "paper_trade"}}

    def obs(oid, **kw):
        base = {"observationId": oid, "sourceId": "S|F", "actor": "MOGO",
                "strategyId": "alex_g_sr_v1", "openedAt": "2026-08-06T10:00:00Z",
                "closedAt": "2026-08-06T12:00:00Z", "entry": 1.10, "stop": 1.09,
                "target": 1.12, "exitPrice": 1.11, "direction": "buy",
                "outcome": "Win", "rMultiple": 1.0}
        base.update(kw)
        return base

    healthy = {"a": obs("a")}
    t("population GREEN on a healthy corpus",
      check_observation_population(healthy, src)["state"] == GREEN)
    t("population RED on an empty corpus",
      check_observation_population({}, src)["state"] == RED)

    t("attribution GREEN when every record names a strategy",
      check_strategy_attribution(healthy)["state"] == GREEN)
    t("attribution RED on an unattributed record",
      check_strategy_attribution({"a": obs("a", strategyId=None)})["state"] == RED)

    t("integrity GREEN on a consistent corpus",
      check_observation_integrity(healthy, src)["state"] == GREEN)
    t("integrity YELLOW on a self-contradicting record",
      check_observation_integrity(
          {"a": obs("a", closedAt="2026-08-06T10:00:00.004Z", exitPrice=1.12,
                    rMultiple=2.0)}, src)["state"] == YELLOW)

    # ── live store: CONTROLLED fixtures, not the repository ─────────────────────────────────
    # These three cases used REPO_ROOT as a stand-in store. The YELLOW case injected a clock and
    # was therefore deterministic; the GREEN case injected nothing, so it read the real wall
    # clock against the repository directory's mtime and DECAYED into a failure once the repo
    # had not been written for STORE_STALE_AFTER_HOURS. It passed for a week and then failed
    # with no code change -- a test that reports on the calendar rather than on the code.
    #
    # Both sides of the age calculation are now controlled: a temporary store outside the
    # repository, and an injected clock anchored to that store's own mtime. Nothing here reads
    # the current date, the repository's age, the local timezone, or elapsed execution time,
    # and no repository path is created, touched or re-stamped.
    #
    # check_live_store itself is UNCHANGED -- only the inputs it is handed.
    t("live store UNKNOWN when absent (absence is not a fault)",
      check_live_store(store_path="/nonexistent/mogo/store")["state"] == UNKNOWN)
    _store_tmp = tempfile.mkdtemp(prefix="mogo-health-selftest-")
    try:
        _store = os.path.join(_store_tmp, "store")
        os.makedirs(_store)
        # Anchor every assertion to the fixture's OWN mtime, so the arithmetic is exact
        # regardless of filesystem timestamp granularity.
        _mt = datetime.datetime.fromtimestamp(os.path.getmtime(_store),
                                              datetime.timezone.utc)
        _at = lambda hours: check_live_store(
            store_path=_store, clock=_mt + datetime.timedelta(hours=hours))["state"]
        t("live store GREEN when freshly written",
          _at(0.0) == GREEN)
        t("live store YELLOW when stale",
          _at(STORE_STALE_AFTER_HOURS + 400 * 24) == YELLOW)
        # The boundary the production operator actually defines: `age_h > stale_hours`, so
        # EXACTLY at the threshold is still GREEN. A one-second epsilon is used rather than a
        # sub-microsecond one so the result cannot turn on filesystem timestamp precision.
        t("live store boundary: exactly at the threshold is GREEN (the operator is >)",
          _at(STORE_STALE_AFTER_HOURS) == GREEN)
        t("live store boundary: one second past the threshold is YELLOW",
          _at(STORE_STALE_AFTER_HOURS + 1.0 / 3600.0) == YELLOW)
    finally:
        shutil.rmtree(_store_tmp, ignore_errors=True)

    t("provider UNKNOWN when not probed",
      check_provider(enabled=False)["state"] == UNKNOWN)

    t("engine evaluation is always UNKNOWN from the host",
      check_engine_evaluation()["state"] == UNKNOWN)

    # The property this whole module exists for.
    t("UNKNOWN never aggregates to GREEN",
      overall([_check("a", GREEN, ""), _check("b", UNKNOWN, "")]) == UNKNOWN)
    t("RED outranks UNKNOWN",
      overall([_check("a", UNKNOWN, ""), _check("b", RED, "")]) == RED)
    t("UNKNOWN outranks YELLOW",
      overall([_check("a", YELLOW, ""), _check("b", UNKNOWN, "")]) == UNKNOWN)
    t("an empty check list is UNKNOWN, not GREEN", overall([]) == UNKNOWN)

    failed = [x for x in results if not x[1]]
    for name, ok, _d in results:
        print("  %-58s %s" % (name, "PASS" if ok else "FAIL"))
    if failed:
        print("SELFTEST FAILED: %d of %d" % (len(failed), len(results)))
        return 1
    print("SELFTEST PASS -- %d injected conditions, every check proven able to fail"
          % len(results))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--network", action="store_true",
                        help="probe provider transport (off by default; unprobed is UNKNOWN)")
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    r = report(network=args.network)
    print(json.dumps(r, indent=2, sort_keys=True) if args.json else render(r))
    if args.write:
        os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
        with open(REPORT_PATH, "w", encoding="utf-8") as handle:
            json.dump(r, handle, indent=2, sort_keys=True)
            handle.write("\n")
        print("written to %s" % REPORT_PATH)
    # RED is the only state that fails the process. UNKNOWN does not: it means "not
    # established", and turning that into a build failure would push toward removing the
    # check rather than establishing the fact.
    return 1 if r["overall"] == RED else 0


if __name__ == "__main__":
    raise SystemExit(main())

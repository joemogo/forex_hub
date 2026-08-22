# MOGO Reliability Contract — R1

**Purpose.** Convert "MOGO is reliable" into conditions a machine can check. This file is the
durable statement of those conditions; the checkers that enforce them live in
`scripts/trader_intelligence/platform_health.py`, `tests/run_all.sh` and the fixture suites named
per invariant.

**NO LIVE-MONEY AUTHORITY EXISTS. PAPER SIMULATION ONLY.**

---

## 0. The architectural fact that shapes everything below

**MOGO is a single-file browser application.** There is no server, no worker process, no scheduler,
no daemon, and no CI runner. Scanning, evaluation, AOI detection, charting and paper execution all
happen inside a Chrome tab on the operator's machine. CDP is not exposed, and **INC-004** forbids
driving that profile.

Three consequences that no amount of engineering removes, and that any honest contract must state:

1. **Host-side checks cannot observe the engine.** Whether a sweep evaluated *this minute* is not
   establishable from outside the tab. It is reported **UNKNOWN**, permanently, by design.
2. **There is no process to run a recurring probe in.** A "15-minute cadence" has no scheduler to
   fire it. `platform_health.py` is runnable and exits non-zero on RED — scheduling it is an
   operator action (a `launchd`/cron entry), not something the codebase can grant itself.
3. **"Release gating" means `tests/run_all.sh`.** There is no CI. The gate is enforced by being run,
   which is a human act.

Anything in this contract that presupposes a server is marked **NOT APPLICABLE (no runtime)** rather
than being simulated. A contract that claims coverage it cannot deliver is worse than one that
admits the gap.

---

## 1. State vocabulary

| State | Meaning |
|---|---|
| **GREEN** | The invariant was **positively established** by recent evidence. |
| **YELLOW** | Degraded, but the affected surface is explicitly isolated and every remaining output stays valid. |
| **RED** | A critical function cannot be trusted. |
| **UNKNOWN** | Health could not be established. |

**Three rules that are load-bearing:**

- **UNKNOWN is not GREEN**, and never aggregates into it. `_RANK` in `platform_health.py` places
  UNKNOWN above YELLOW so an unrunnable check cannot be smoothed away by healthy neighbours. An
  empty check list is UNKNOWN — a report that ran nothing must not congratulate itself.
- **A process being alive is not GREEN.** GREEN requires semantic evidence that useful work
  *completed correctly*.
- **"No exception was thrown" is not GREEN.** Absence of an error is not presence of a result.

---

## 2. Market-data acquisition

**What must be true.** No dataset is classified `COMPLETE` unless it satisfies identity, structural
and ordering integrity — and **the forward and paginated paths enforce the same standard.**

| | |
|---|---|
| **Measured by** | `marketDataClassify`, `marketDataCandleIntegrity`, `marketDataIdentityOutcome` at the acquisition boundary |
| **Evidence** | `completenessState`, `integrityOutcome`, `identityVerified`, `transportOutcome`, `httpStatus` attached to every returned series |
| **GREEN** | `completenessState === COMPLETE` and `integrityOutcome === OK` |
| **YELLOW** | `PARTIAL` — the request was not fully satisfied, but what arrived is structurally valid |
| **RED** | `UNAVAILABLE` from an integrity or identity failure |
| **UNKNOWN** | `identityVerified === false` — the provider sent no identity fields, so the check could not run. **Recorded, never inferred as agreement.** |
| **Remediation** | None automatic. Fail closed and report. Do **not** retry-storm a failing origin, substitute stale candles, or relax the lookback. |
| **Regression** | `tests/v130_...js` — `INTEG-1..13`, `RANGE-1..10`, `BEHAVIOUR-1/2/2b`, `SAFETY-1..4`, `CONTRACT-1..3` |

**Enforced checks:** instrument identity, granularity identity, finite and positive OHLC,
`h ≥ max(o,c)`, `l ≤ min(o,c)`, `h ≥ l`, strictly ascending timestamps (which subsumes duplicates
and reordering), on the raw *and* filtered series, per page *and* across the combined accumulator.

**Deliberately NOT enforced:** a `missingCandles` count. Session, weekend, holiday and liquidity
gaps are legitimate market structure, so requested-minus-received is unsound as a measure of missing
data. This is an ADR-011 decision, and re-adding such a field is a contract violation, not an
improvement.

**Identity comparison is normalization-tolerant** (case, `_`/`/`, whitespace) because OANDA does not
guarantee a byte-identical echo — published examples show `DE30_EUR` answered with `DE30/EUR`. A
strict comparison here is a single point that takes all 35 pairs dark in one sweep. Tolerance costs
no detection power: `GBP_JPY` never normalizes to `EUR_USD`. Control: `INTEG-12`.

---

## 3. Historical context and audit horizon

**What must be true.** History is expressed in **calendar time**, not in an arbitrary candle count,
and the achieved horizon is reported from the candles that actually arrived.

| | |
|---|---|
| **Measured by** | `CHART_AUDIT_HORIZON_DAYS` (28), `chartCandlesForHorizon`, `chartHorizonDaysForCandles` |
| **Evidence** | The chart states "History shown: N days (M candles)" and flags a short window |
| **GREEN** | Achieved horizon ≥ 90 % of target |
| **YELLOW** | Below that — surfaced in amber, never silent |
| **RED** | No candles at all |
| **Regression** | `HIST-1..7`, including `HIST-3`, the dated July-29 case |

**Why a count is the wrong unit:** "is 400 enough to review last month?" is unanswerable; "28 days"
is. The counts are *derived* from the horizon so the table cannot drift from the requirement it
serves, and the derivation is **strictly non-reducing** — `max(legacy, derived)` — so no timeframe
can lose history to this rule.

**Known structural limit, disclosed:** the chart has **no back-history pagination**.
`subscribeVisibleLogicalRangeChange` saves the view and redraws drawings; nothing fetches older
candles. The horizon is therefore a hard edge, not a starting point. It is reported *because* it is
a hard edge.

---

## 4. Scanner

| | |
|---|---|
| **What must be true** | Every configured pair reaches an explicit terminal state each sweep |
| **Measured by** | `scanAll`'s `finally` → `instrumentsEvaluated` / `instrumentsSkipped` with reason codes |
| **Evidence** | `pairData[pair].completenessState` / `evaluationSuppressed` / `transportOutcome`; the forward-observation ledger |
| **GREEN** | `completenessState === COMPLETE`, evaluation ran |
| **YELLOW** | Suppressed with a named reason |
| **UNKNOWN** | Not reached this sweep |
| **Regression** | `ROW-1..4`, `VISIBILITY-1..3` |

**Open gap (recorded, not closed):** the four skip reason codes are written to a durable ledger that
**nothing reads**, and there is **no per-pair evaluation timestamp**, so staleness of a pair's last
successful evaluation is invisible on every screen. See `docs/KNOWN_ISSUES.md`.

---

## 5. AOI

**What must be true.** *Every applicable chart has a validated AOI determination.* Emphatically
**not** that every chart has an AOI — a chart with no qualifying structure is a correct result.

The distinction the system must never lose:

- **VALIDATED_NO_AOI** — data was valid, history sufficient, the logic ran, nothing qualified.
- **AOI_NOT_EVALUATED** — the determination never happened.

`getStructuralAOI` computes this correctly and its own comment forbids the collapse. The Manual
Review classifier previously reported a D/W outage as the strategy verdict `no AOI`; it now reports
`AOI NOT EVALUATED` and still fails closed.

**Open gap (recorded):** the chart AOI overlay still drops `incomplete` — on a D/W outage no band is
drawn and nothing says why, visually identical to a pair with no structure.

---

## 6. Paper execution

| | |
|---|---|
| **What must be true** | Exactly-once for order intent, position, close, outcome, evidence package |
| **Evidence** | Durable dedup keys: position absent from `openPositions` (committed atomically with balance and journal); `bySourceTradeId` IndexedDB index for packages |
| **GREEN** | Ledger and journal reconcile; no duplicate or impossible state |
| **Verified** | Traced end-to-end; crash-before-commit retries once, crash-after finds `idx === -1`; `STALE_VERSION` compare-and-swap refuses a second session; non-finite values refused **before** writing |
| **UNKNOWN handling** | Rollback failure sets `integrityCompromised` with a FATAL naming the failed step — it does **not** blindly replay |

**Residual, disclosed [P3]:** the three `localStorage` keys are individually atomic but **not atomic
as a group**; a process kill between them can desynchronise the journal from the ledger. It cannot
duplicate a PAPER action.

---

## 7. Evidence, provenance, reconciliation

| | |
|---|---|
| **GREEN** | `validate_evidence` ERROR 0; `validate_graph` ERROR 0; `observation_graph_reconcile` RECONCILED; every observation classifiable and attributed |
| **YELLOW** | A record excluded from the authoritative population by `observation_integrity.py` |
| **RED** | An unclassifiable or unattributed observation |
| **Rule** | Preserved evidence is **never** rewritten to tidy a count. A suspect record is partitioned out of the authoritative population and kept. |

**RAW vs AUTHORITATIVE is mandatory in reporting.** Both are quoted together with the quantitative
effect of the exclusion, because quoting one alone is how a 2.0R record silently flattered a
29-trade sample.

---

## 8. Strategy isolation

**What must be true.** No strategy silently contributes to another's performance population, and
strategy identity survives specification → evaluation → decision → PAPER action → close → evidence →
aggregation → reporting.

- Enforced at minting: `strategyId` is **required and explicit** — an unattributable trade produces
  **no package** rather than a mislabelled one.
- Enforced in aggregation: `forward_coverage.py` scopes both arms and declares `strategyMixing`;
  `population_fidelity.py` refuses to run unscoped.
- Attribution is **never guessed**: no usable `strategyId` ⇒ `UNATTRIBUTED`, excluded from every
  scoped reading.

**Regression:** `test_forward_coverage.py` (21), `test_observation_integrity.py` (20).

---

## 9. Health monitoring, and its own health

| | |
|---|---|
| **Authority** | `scripts/trader_intelligence/platform_health.py` — one auditable verdict |
| **Self-test** | `--selftest` injects 15 failure conditions, driving every check to its failure state; wired into `run_all.sh` |
| **Exit** | Non-zero only on RED. UNKNOWN does **not** fail the process — turning "not established" into a build failure pushes toward deleting the check rather than establishing the fact. |

**Current live verdict: `OVERALL: UNKNOWN`** — and that is the correct answer, not a shortfall.
`engine_evaluation` is not observable from the host (§0).

**NOT APPLICABLE (no runtime):** fast/deep probe cadence, telemetry heartbeat, stale-GREEN
expiry, live "current activity". These require a process MOGO does not have. `platform_health.py`
is scheduler-*ready*; scheduling it is an operator action.

---

## 10. Autonomous recovery

**Deliberately minimal, and that is a finding rather than an omission.** MOGO has no server, no
workers and no services, so the narrow-recovery ladder (request → connection → worker → service) has
almost no surface to act on. For the failure class that actually occurred — a provider outage — the
correct recovery is **fail closed, report why, verify on return**, which is implemented and tested.

Recovery must never: fabricate market data, weaken the candle contract, hide a provider failure,
rewrite evidence, duplicate a PAPER action, change frozen strategy semantics, or convert UNKNOWN
into GREEN.

---

## 11. What GREEN is forbidden from meaning

GREEN is not permitted while any of these hold: stale health evidence; unknown engine state; an
unaccounted pair/timeframe; insufficient history not explicitly quarantined; a scanner hole; an
unknown AOI state; a data-integrity failure; an unresolved critical incident; an evidence-persistence
failure; an unreconciled paper ledger.

**"Tests passed yesterday" is not current GREEN.**

---

## 12. Contract maintenance

This file is normative. A change to market-data acquisition, the scanner, AOI, historical fetch, a
strategy engine, execution, evidence or health **must** update the relevant section and run the named
regression suites. The canonical gate is `bash tests/run_all.sh`, exit 0 required, and its summary
VERDICT line is derived from the exit code so the two cannot disagree.

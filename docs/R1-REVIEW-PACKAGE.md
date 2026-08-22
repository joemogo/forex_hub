# MOGO Reliability Gate R1 — Independent Review Package

**For a second model family to challenge this work without reconstructing months of context.**
Self-contained. No secrets. Everything below is measured against the repository at the commits named
in §9.

**Verdict claimed: R1 INCOMPLETE.** See §8 for exactly which criteria are met, which are not, and
which cannot be met by construction. Challenge that verdict first — if R1 is being scored more
favourably than the evidence supports, that is the most valuable thing you can find.

---

## 1. What MOGO is, architecturally — this determines what R1 can prove

**A single-file browser application.** `index.html`, ~22,000 lines, ~1.9 MB, served from GitHub
Pages, running in one Chrome tab on the operator's machine.

**There is no server, no worker process, no scheduler, no daemon, and no CI.** Scanning, evaluation,
AOI detection, charting and paper execution all happen inside that tab. CDP is not exposed, and
**INC-004** forbids driving the operator's profile.

Two Python/JS toolchains sit beside it, host-side and offline:
- `scripts/trader_intelligence/*.py` — evidence corpus, validators, health authority
- `tests/*.js` — fixture suites run under `osascript -l JavaScript`, which **eval the real
  application code** with only `globalThis.fetch` scripted. No production function is stubbed.

**Consequence you should test the honesty of:** anything requiring a recurring process — probe
cadence, telemetry heartbeat, stale-GREEN expiry, live activity, release gating — has nothing to run
in. R1 marks these **NOT APPLICABLE (no runtime)**. *Is that an honest classification, or an excuse?*

---

## 2. Execution path, forward (the trading path)

```
OANDA /v3/instruments/{pair}/candles
  → fetchCandlesDiagnosed()          identity + integrity + completeness   [HARDENED, R1]
  → fetchCandles()                   thin wrapper, returns array | null
  → scanPair(pair, sweepTf)          requests 220 on the active timeframe
  → marketDataCompletenessOf()       THE sole evaluation gate (ADR-011)
  → detectSignals / bestConfluence   PROTECTED; receive null when not COMPLETE
  → pairData[pair]                   in-memory, no timestamp
  → checkAutoTrades()                iterates SCAN_PAIRS (12), narrows to 'Active watch'
  → evaluateLiveTrigger()            PROTECTED; fetches M15/60
  → openPaperPosition()              PROTECTED; sizing via pipValuePerLot()  [DEFECT, §5]
  → checkPaperPositions()            stop/target from a live price only
  → closePaperPosition()             exit from fetchBidAsk(); never from target
  → commitPaperLedger()              3 localStorage keys, compare-and-swap on version
  → evidencePersistTradePackage()    strategyId REQUIRED; unattributable ⇒ NO package
  → IndexedDB (origin store)
  → scripts/forward_capture.sh       host-side: detect → preserve → recover → import
  → docs/trader-intelligence/evidence/   the committed corpus IS the preservation
```

## 3. Execution path, historical / replay

```
fetchCandlesRange(pair, tf, totalCount)      paginates backwards via the `to` cursor
  → per-page identity + integrity            [ADDED IN R1]
  → combined accumulator integrity           [ADDED IN R1 — catches seams]
  → consumers: fetchAlexGReplayDatasets, runBacktest, fetchAllPairCandles, fetchReplayDatasets
fetchCandlesAroundWindow()                   display-only; STILL UNGUARDED
loadChart()                                  ONE fixed window; NO back-history pagination
```

---

## 4. The Reliability Contract

`docs/MOGO-RELIABILITY-CONTRACT.md`. States per invariant: what must be true, how measured, evidence,
GREEN/YELLOW/RED/UNKNOWN, remediation, regression suite.

Three rules that carry the weight:
- **UNKNOWN never aggregates to GREEN.** `_RANK` places UNKNOWN above YELLOW; an empty check list is
  UNKNOWN.
- **A live process is not GREEN.** GREEN needs semantic evidence that work *completed correctly*.
- **"No exception thrown" is not GREEN.**

---

## 5. Findings — verified, with the ones NOT repaired stated first

### D1 — `pipValuePerLot` substitutes the wrong conversion rate. **P1. PROTECTED. NOT REPAIRED.**

```js
const rate=(pairData['USD_'+quote]&&pairData['USD_'+quote].price)||(pairData[pair]&&pairData[pair].price);
if(rate) return (pip*lotUnits)/rate;
return null;    // unreachable whenever the pair itself has a price
```

Second operand is the rate of the pair being **sized**, not `USD/quote`. Correct only when
`base==='USD'`, where the branch is redundant. The `||` fires **before** the `return null` guard
written to prevent this exact fabrication.

**Measured:** `GBP_CHF` → **9.0090** vs correct **11.3636** (21 % error) in pip value, lot size and
realized P&L. Frozen at entry as `pipValueAtEntry`, reused at close.

**Structural, not just transient:** no `USD_GBP`/`USD_AUD`/`USD_NZD` in `ALL_PAIRS`, so **6 pairs are
permanently on the fallback**: `EUR_GBP, EUR_AUD, EUR_NZD, GBP_AUD, GBP_NZD, AUD_NZD`.

*Challenge this:* is 21 % right? Are there more than 6? Does the transient path really reach
`SCAN_PAIRS`? Is there a non-protected interception point I missed?

### D2 — `pipD = last.c < 10 ? 0.0001 : 0.01` replaces `pipSize()`. **P2. 2 of 3 sites PROTECTED.**

Canonical is `pipSize(pair){return pair.includes('JPY')?0.01:0.0001;}`. The heuristic gives a **100×
pip size** to `USD_MXN, USD_ZAR, USD_TRY, USD_SEK, USD_NOK` — all configured.

### D3 — AOI runs on a shorter window than it declares. **REPORTED, NOT REPAIRED (governance).**

`findAOIs` = `computeAOI(candles,100,3)` — a 100-bar window. Supplied: `evaluateLiveTrigger` M15/60
(~59 usable), `getStructuralAOI` weekly 60 (~59). **This is deliberate** — `computeAOI` floors at 20
and its comment says it "should still try with whatever it has". Raising the fetch would produce more
AOIs ⇒ more trades ⇒ a protected-semantics change.

Also: **`COMPLETE` ≠ "N candles available"** — classification compares `rawCount` *before* the
`c.complete` filter, so a healthy fetch of N yields ~N−1 usable.

### R1 — ALEX exit-monitor timer survived `disconnect()`. **REPAIRED.**

`disconnect()` cleared three timers but not `alexGLiveInterval` — the one that closes open ALEX
positions. `stopAlexGLivePollingIfDone()` couldn't retire it (predicate reads
`alexGAutoTrading.enabled || openPositions.length`, neither touched by disconnect). It kept firing
against credentials cleared on the next line; both failure paths return `null` and `continue`
**silently** while the poll ledger recorded `outcome:'OK'`. Fixed symmetrically with `autoScanTimer`;
`initAll()` restarts on reconnect. Regression `LEAK-1`.

### Reported by review, NOT yet investigated by me — treat as unverified leads

No directional/minimum-distance validation on a JVM entry (stale D/W AOI vs live price ⇒ inverted
stop, unbounded size); ALEX exit monitor's two silent `null` returns have no failure counter; Manual
Review retains a stale candidate on a thrown classification while the modal hardcodes "Data age:
live"; a fired trigger that fails to size is dropped with no record; poll-continuity summary merges
both strategies' streams so one loop dying reads healthy; `loadChart` has no generation token;
`persistStorageKey`'s refusal is discarded by all 11 callers; no cache invalidation on env/account
switch.

**These are the highest-value target for you.** I verified the four above and ran out of run before
these. Several look serious.

---

## 6. What was built in R1

| Area | Deliverable |
|---|---|
| §4 paginated integrity | Per-page identity + integrity; **combined accumulator** check for seams |
| §5 history | `historySufficiency()` — SUFFICIENT / REDUCED_WINDOW / INSUFFICIENT / UNKNOWN + shortfall |
| §2 contract | `docs/MOGO-RELIABILITY-CONTRACT.md` |
| §28 fault injection | `RANGE-1..10` — wrong instrument (incl. page N), wrong granularity, reversed, malformed, duplicate boundary, overlap, truncation, forward/replay equivalence |
| §29 | Silent-failure hunt → D1/D2/R1 above |

**Fixture families:** `INTEG-1..13`, `RANGE-1..10`, `HIST-1..13`, `ROW-1..4`, `LEAK-1`,
`DEFECT-1..3`, plus pre-existing `BEHAVIOUR/SAFETY/CONTRACT/VISIBILITY/CHART/AOI`.

---

## 7. Ways to falsify this work — please try these

1. **Find a way GREEN could be claimed while an invariant is unproven.** `platform_health.py`
   currently returns `OVERALL: UNKNOWN`. Can any input make it GREEN without engine evidence?
2. **Find a pair/timeframe that avoids evaluation without producing an incident.** The four skip
   reason codes are written to a ledger **nothing reads**, and there is no per-pair evaluation
   timestamp.
3. **Find a path where insufficient history still becomes "NO AOI".** `historySufficiency` classifies
   it, but is it *wired* to every AOI surface? (Known: the chart overlay still drops `incomplete`.)
4. **Find data replay accepts that forward would reject.** `RANGE-10` asserts equivalence for one
   body shape. `fetchCandlesAroundWindow` is still unguarded.
5. **Break the integrity checks with legitimate OANDA data.** A false positive here is an outage
   across all 35 pairs. Prior review found the identity check needed normalization tolerance
   (`DE30_EUR` → `DE30/EUR`); is the OHLC/ordering side equally safe?
6. **Check whether `DEFECT-1..3` actually pin the defects**, or merely assert arithmetic that would
   still pass after a wrong fix.

---

## 8. R1 criteria — honest scoring

**MET:** market-data integrity enforced on forward *and* paginated paths · `fetchCandlesRange`
hardened · forward/historical standards equivalent · historical depth measured · insufficient history
explicit (as a classifier) · July-29 regression permanent (`HIST-3`, dated) · fault-injection suite
exists and passes · strategy engines match frozen specs (zero drift) · evidence persistence healthy ·
ledger reconciles · research library measurable · independent adversarial review completed (3 rounds).

**NOT MET:** Health Center UI does not exist · incidents are not automatically created · no
autonomous recovery beyond fail-closed · scanner coverage is not *proven* per pair/timeframe (no
per-pair timestamp; skip codes unread) · AOI accuracy has no known-answer regression · no evaluation
state machine · GREEN staleness cannot expire.

**NOT APPLICABLE (no runtime):** fast/deep probe cadence · telemetry heartbeat · live activity ·
CI release gating · health self-monitoring as a process.

**BLOCKED ON OPERATOR:** D1 and D2 (protected functions) · D3 history-supply decision · scheduling
`platform_health.py`.

---

## 9. How to reproduce

```bash
cd "/Users/joemogollon/Desktop/Forex Hub"
git log --oneline R1-BASELINE..HEAD          # R1's commits
bash tests/run_all.sh                        # canonical gate, exit 0 required
osascript -l JavaScript tests/run_v130_candle_completeness_regression_tests.js
python3 scripts/trader_intelligence/platform_health.py --selftest
python3 scripts/trader_intelligence/platform_health.py --network
python3 regression-baseline-tools.py         # protected-function drift
```

Baseline tag: `R1-BASELINE`. Rollback: `git revert` the R1 commits — every change is additive, no
migration, no evidence rewritten.

**Read alongside:** `docs/MOGO-RELIABILITY-CONTRACT.md`, `docs/KNOWN_ISSUES.md`, `docs/INCIDENTS.md`
(INC-006), `docs/MOGO-023-TO-024-HANDOFF.md`, `docs/adr/ADR-011-*`.

# Data Flow

## JVM: market data → journal → dashboard

This is the verified, actual call chain (confirmed by direct code trace, not assumed):

```
initAll()
 └─ scanAll()  — fires immediately, then every 60s via scanInterval
     ├─ per pair: scanPair(pair)
     │    ├─ fetchCandles() / fetchPrice()        (OANDA REST)
     │    ├─ detectSignals()
     │    ├─ bestConfluence() → scoreConfluence()  (uses WEIGHTS / ALERT_THRESHOLD)
     │    ├─ pairData[pair] = {candles, price, signals, conf}
     │    └─ addAlert() if conf.total >= ALERT_THRESHOLD
     ├─ checkPaperPositions()   — stop/target hit check against pairData, may closePaperPosition()
     └─ checkAutoTrades()
          ├─ eligible pairs = not-already-open ∩ not-traded-today ∩ scanData[pair].bucket === 'Active watch'
          ├─ evaluateLiveTrigger(oPair)
          │    ├─ isPreferredTradingDay() gate (Mon–Wed)
          │    ├─ fetchCandles(M15) → detectSignals() → bestConfluence()
          │    ├─ confluence ≥ 55, a fresh matching engulf required
          │    ├─ getStructuralAOI() → stop/target with a buffer
          │    ├─ fetchBidAsk()  (spread-aware fill)
          │    └─ R:R ≥ 1.99 gate
          └─ openPaperPosition(oPair, dir, entry, stop, target, 'auto')
               ├─ pipValuePerLot()  (fixed 1% risk sizing)
               ├─ paperAccount.openPositions.push(pos)
               ├─ journalNoteOpenJVM(pos) → buildJVMJournalOpenRecord + upsertJournalOpenRecord
               └─ commitPaperLedger()  — atomic, version-guarded persistence

(independently, hourly) runAutoTopDownScan() → scanData[pair].bucket = 'Active watch'
                                                 (feeds checkAutoTrades' eligibility gate)
(on stop/target hit) closePaperPosition() → fetchBidAsk() → journalNoteCloseJVM() → commitPaperLedger()

(read side, every render)
getUnifiedJournalRecords() → normalizeJournalRecord(raw, storeStrategy)
   → Journal tab / renderDashboard() / computePerformance-style stats / Trade Inspector / chart overlay
```

Two independent timers drive the app: `scanInterval` (60s — scan, exit-check, auto-trade) and
`autoScanTimer` (60min — top-down bias / Active Watch computation).

## Alex: the parallel flow

Structurally mirrors JVM, on its own independent 60s timer (`alexGLiveInterval`, self-starting/
stopping via `alexGLivePollingShouldRun()`/`stopAlexGLivePollingIfDone()` rather than always
running):

```
alexGLivePollTick()
 ├─ alexGCheckLivePositions()          — exit monitoring, runs first every tick
 └─ (if alexGAutoTrading.enabled) new-setup search, gated on an H1-candle-boundary check
      ├─ zone engine (alexGRunZoneEngine → alexGFindSwingPoints/alexGAssignCluster/alexGAcceptReaction)
      ├─ setup engine (alexGRunSetupEngine → alexGCreateSetupRecord)
      ├─ trade construction (alexGConstructLivePosition → alexGAttemptOpenLivePosition)
      │    └─ calls the shared kernel: pipSize(), pipValuePerLot(), getSession(),
      │       getCandleCloseTime(), isPreferredTradingDay()  (see SYSTEM_ARCHITECTURE.md)
      └─ journalNoteOpenAlex(pos)

(on exit condition) alexGReconstructExitFromCandles() → alexGCloseLivePosition() → journalNoteCloseAlex()
```

Alex has no numeric confluence score — qualification is a rule-based zone/touch/break state
machine (`alexGCorrectedQuality`, `alexGEvaluateBreakRetest`, `alexGEvaluateRepeatedReaction`,
`alexGClassifyTouch`), not a variant of JVM's scoring.

## The unified read path (shared, strategy-agnostic)

Both strategies' raw journal records are mapped into one shared shape and merged for every
downstream consumer (Journal tab, Dashboard's recent-activity table, Trade Inspector, chart trade
overlay):

```
getUnifiedJournalRecords()
  journalEntries.map(e => normalizeJournalRecord(e, 'current_strategy'))
    .concat( <ALEX journal>.map(e => normalizeJournalRecord(e, 'alex_g_sr_v1')) )
    .sort(by timestamp)
```

As of v12.0.0, the ALEX side of this concat is sourced through the Strategy Registry
(`getStrategyServices('alex_g_sr_v1').getJournal()`/`.normalize()`) rather than reading
`alexGJournalEntries`/calling `normalizeJournalRecord()` directly — see
[STRATEGY_REGISTRY.md](STRATEGY_REGISTRY.md). The JVM side is unchanged and unregistered.

`drawTradeOverlay(rec)` (the chart's trade overlay) consumes this same normalized shape and is
null-guard-driven rather than strategy-flag-driven — it draws whichever fields a given record
actually has (entry/stop/target always; zone lines only if `zoneLow`/`zoneHigh` are present, which
only Alex records populate). This is a clean example of the normalizer making a downstream
consumer genuinely strategy-agnostic without an explicit `if (strategy === ...)` branch.

## What is NOT part of this flow

The Strategy Center's per-strategy tab, the Academy, AI Assistant, and the Diagnostics page are
Shared Services that *read* the state produced by the flow above (via the unified journal, or
directly via `paperAccount`/a strategy's own account) — none of them sit in the trade-execution
path itself.

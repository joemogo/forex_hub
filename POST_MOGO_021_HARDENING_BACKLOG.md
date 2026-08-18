# POST-MOGO-021 HARDENING BACKLOG

Deferred P2/P3 items. **None of these blocks CORE GREEN or safe PAPER operation.**
Each was found by independent adversarial verification during MOGO-021, classified under the
risk-based convergence policy, and deliberately deferred rather than fixed.

Kept separate from MOGO-021 readiness on purpose: these can be worked incrementally while MOGO
accumulates forward PAPER evidence.

---

## P2 — Operational / observability

| # | Item | Why deferred |
|---|---|---|
| B-1 | **MOGO-013 observation ledger has no behavioural coverage.** `evidencePutObservation` and `evidenceEnforceObservationRetention` are never called on any path the gate observes; eight behaviour-changing mutations survive, including eviction that deletes nothing while the RETENTION marker records "evicted, NOT recoverable". | Research corpus, not trade evidence. Cannot alter a trading decision, a paper position, or the trade-evidence packages (which are covered by PTE2E-EVCAP.*). |
| B-2 | **`setTimeout` never fires in the JS harness.** 14 production sites are unexercised, including the boot sequence and four `await new Promise(res=>setTimeout(res,0))` yields that would hang the harness if reached. A timer-deferred cross-strategy leak survives ISO. | Isolation is verified for synchronous and microtask-deferred writes at any depth. No production route defers a cross-strategy write by timer. Making `setTimeout` real risks hanging four suites — a change that needs its own verification budget. |
| B-3 | **26 JPY `toFixed(5)` render sites**, including the manual-review confirm modal and an editable R:R input. `alexPx()` already exists. | Values are correct; only the precision display is wrong (`150.12300` vs `150.123`). Cannot change a trading decision or a booked number. |
| B-4 | **JVM `WRITE_FAILED` is not classified.** `savePaperAccountGuarded`'s JVM branch omits `evidenceClassifyStorageError`/`evidenceRecordWriteFailure`; the ALEX twin has them. On a quota-exhausted commit the operator is told "a newer version may exist in another tab", which is a different remedy. Also `ROLLBACK_FAILED` lacks them on both arms, and the ALEX reporting that does exist is itself unpinned. | The commit is still refused fail-closed, so no durable corruption. The operator is misinformed about the cause, not about the outcome. |
| B-5 | **`commitPaperLedger` flattens the refusal reason.** `LOAD_INTEGRITY_BLOCKED` and `blockedKeys` from `savePaperAccountGuarded` are replaced by the generic blocking-banner text, so a caller cannot distinguish an INC-001 refusal from an ordinary stale-version rejection. | Diagnostic detail. The refusal itself is correct and now pinned (PTE2E-INC001.1). |
| B-6 | **`evidenceHasPackageForTrade(null)` returns a match**, so a trade with no id would be treated as already captured. | No production path produces a null tradeId; the id is minted before capture. |
| B-7 | **Backfill and auto-export are ALEX-only.** `evidenceBackfillFromLocalStorage` reads only the ALEX stores, so a JVM-only operator gets "Examined: 0" with no explanation; `evidenceExportPending('AUTO_DOWNLOAD')` has one call site, inside the ALEX seam. | Feature asymmetry, not a defect. JVM trades are captured live by their own seam. |
| B-8 | **`runHistoricalDataDiagnostic` has no termination-reason field.** `requestCount:20` reads identically for "needed 20 pages" and "hit the page ceiling mid-history", and the UI labels the truncated boundary "Actual earliest candle". | Diagnostic reporting. Does not feed trading logic. |
| B-9 | **`alexGAutoTrading.log` has no reader.** The ALEX per-setup rejection audit trail exists only in localStorage; no UI renders it. | Missing surface, not wrong information. Forward PAPER operation will make the need concrete. |
| B-10 | **`alexV2AutoTrading` snapshot asymmetry.** Present in `snapshotJvmStores`, absent from `snapshotAlexStores` and from the reset, so an in-memory ALEX→alexV2 mutation without a save passes both. | alexV2 is research/shadow and gates nothing. A persisted leak is still caught by the `fxhub_alex*` key comparison. |
| B-11 | **`currentChartCandles` is not cleared** on `loadChart`'s empty-fetch early return, so the module briefly holds the previous pair's candles under the new pair's identity. | Latent: `destroyChart()` nulls `lwChart`/`candleSeries` and all six consumers are gated on them. Protection is incidental, so worth making explicit — but not reachable today. |
| B-12 | **A JVM package carries `strategyVersion:"alex_g_sr_v1 (inferred, unstamped)"`.** | Explicitly labelled inferred and unstamped; `identity.strategyId` is correct and pinned (PTE2E-EVCAP.8). Odd, not wrong. |

## P3 — Test / maintenance

| # | Item |
|---|---|
| B-13 | ~264 source-text assertions in `tests/v128_evidence_platform_tests.js` (`String(fn).indexOf(...)`). Non-behavioural and inverted-risk: a behaviour-preserving refactor breaks them, a behaviour-changing edit that keeps the phrase passes. Several evidence-layer claims rest only on these. |
| B-14 | The in-memory IndexedDB stub still does not model: transaction isolation (writes visible before commit), `TransactionInactiveError`, key coercion/`DataError`, cursor `delete()`, `count()`/`openCursor()` ranges, `versionchange` blocking, or a failing `open()`. |
| B-15 | No end-to-end fixture composes *real close → canonicalise → SHA-256 → store → verify*: the e2e runner has no `crypto.subtle`, so packages are stored with `contentHash:null`. v128/v131 supply crypto but drive the builder with synthetic trades. |
| B-16 | The ALEX tradeId duplicate guard's `closedPositions` half is unwatched. Production is correct and the disclosure that it was "redundant" was refuted — reaching it in a fixture needs `fxhub_alexg_setups` to load-fail while `closedPositions` survives. |
| B-17 | `exitDetectedAt` unpinned; `evidenceCaptureClosedPaperTrades`' 25-record window boundary unpinned at N-1. |
| B-18 | `calcBiasFromCandles` rule DETAILS undiscriminated: the 55-bar history floor lowered to 25, and both EMA20-vs-EMA50 legs dropped, all survive. Its output IS asserted (a label swap and a bias suppression both kill) and its production consumer is now pinned by AUTOADMIT.1-3; only the internal thresholds are unwatched. |
| B-19 | `v1211_diagnostics_integrity_tests.js` counts `placePaperTrade` among "real production functions exercised", which overstates what it asserts (it uses the function as a vehicle to dirty state). Now separately covered by PTE2E-PLACE.0-5. |
| B-20 | `findAOIsWide` window and `hasAOIOverlap` tolerance are unpinned, but reachable only from `simulateBacktest` — research/backtest, never the live trade path. Classified EQUIVALENT/NON-CRITICAL by the final sweep. |
| B-21 | **Per-tick exit-monitoring state is never persisted.** `alexGCheckLivePositions` mutates `pos.lastExitCheckTimestamp` (index.html:5470) and MAE/MFE (5354-5355) then calls `saveAlexG()` (5494), but `saveAlexG()`→`saveAlexGRest()` writes only `fxhub_alexg_auto`/`_zones`/`_setups`; `alexGAccount` is persisted solely by `commitAlexGLedger()` on open/close. Observed live 2026-08-17: the on-disk exit cursor sat frozen at `openedAt` and MAE/MFE at 0 for two hours on a healthy open position. **Not a money defect** — on reload the cursor reverts to `openedAt` and re-walks from open, which is conservative and self-healing — but disk is not a valid observability channel for exit monitoring. The error half of this gap is now closed (see EXITERR-1/2, v12.39.2); persisting the cursor itself is the remaining item and changes what a reload re-walks, so it needs owner sign-off. |
| B-22 | **9 of 34 real closed ALEX trades have no evidence package** — a contiguous oldest block, 2026-07-13→07-17. The evidence IndexedDB logged `Creating DB … since it was missing` at 08:56:04 on 2026-08-17, so all 25 existing packages were re-minted then and the oldest 9 could not be. Historical only; no forward capture gap (both of that day's closes were captured within ~1s). Backfill would need the source trades re-canonicalised. |

| B-23 | **Five Python suites assert a corpus snapshot instead of an invariant.** `test_graph.test_expected_node_and_edge_counts` and `test_research_understanding.test_all_twelve_blocking_questions_surface_with_their_identity` pin absolute counts; `test_evidence.test_production_evidence_tree_is_still_genuinely_empty`, `test_phase1b.test_production_graph_unchanged_without_real_corpus` and `test_phase7a.test_production_graph_unchanged_without_real_knowledge_library` assert the production evidence tree is EMPTY. That premise was deliberately falsified by MOGO-022's own authorised import — 248 TradeObservations and 641 hypotheses now exist — so the three "empty" assertions are reporting the intended state as a failure. All five are the corpus-frozen-oracle anti-pattern documented in `CLAUDE.md`: an absolute snapshot standing in for "this operation changed nothing", which is strictly weaker than the before/after comparison each sits beside. No production behaviour is implicated. The repair is to rewrite each oracle as a relation (build twice, compare; assert the delta, not the total), which is real work in five files and was deliberately not started here. |

## Governance decisions — deferred, none blocking PAPER

| # | Decision | Blocks paper? |
|---|---|---|
| G-1 | **Widen the protected-function list.** `getStructuralAOI`, `clusterLevels`, `alexGFetchExecutableCandles`, `fetchCandlesAroundWindow`, `runAutoTopDownScan` and the trade-ID seeders all set or gate real prices and sit outside the 63. | No |
| G-2 | **Auto-trade eligibility staleness.** `scanData[pair].bucket` has no age bound; with Auto Trading ON and Auto Scan OFF a days-old `Active watch` still authorises a trade. A TTL changes which trades are taken — frozen semantics. | No — current behaviour preserved |
| G-3 | **Paginator contradiction.** `runHistoricalDataDiagnostic` treats a short page as exhaustion while `fetchCandlesRange` documents that it is not; fixture MDHIST-2 currently blesses the truncation. | No — diagnostics only |
| G-4 | **`exitDetectedAt` fabrication.** `alexGCloseLivePosition` stamps `m.exitDetectedAt||Date.now()`, inventing a plausible detection time when none was supplied. One-line fix, but the function is PROTECTED. Applied, drift tripped, reverted byte-for-byte. | No — evidence timestamp fidelity |

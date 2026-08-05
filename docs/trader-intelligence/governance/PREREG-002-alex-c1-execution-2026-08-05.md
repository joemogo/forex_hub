# PREREG-002 — ALEX Campaign C1 execution set

**Successor to `PREREG-001-alex-multipair-2026-08-04.md`.** PREREG-001 §10 states: *"Amendment — a
successor document only. This one is never edited."* PREREG-001 has not been modified. This document
adds only what PREREG-001 deliberately left to authorization time, and inherits everything else.

| | |
|---|---|
| **Campaign ID** | `CAMP\|ALEX\|C1\|2026-08-05` |
| **Parent pre-registration** | `PREREG-001-alex-multipair-2026-08-04.md` |
| **Declared at** | `2026-08-05T20:00:16Z` |
| **Repository HEAD at declaration** | `bb8498f` (this document and the v12.19.0 change are uncommitted at time of writing) |
| **Engine version for every run** | `APP_VERSION` **12.19.0** |
| **Operator approval** | Granted by the operator on 2026-08-05, in session, authorizing the 11-pair execution set below and the v12.19.0 evidence change that precedes it |
| **Instrument** | ALEX `alex_g_sr_v1`, replay mode, OANDA **practice** data |
| **Lookback control** | 90 days per run (a control label, not a sample boundary — PREREG-001 §6) |
| **Ambiguous mode** | `conservative` |
| **Runs authorized** | 11 — one per pair, no repeats |

---

## 1. Pre-registered execution set and order

Declared **before any C1 observation exists**. Pairs are named here, not chosen after seeing another
pair's result (PREREG-001 §8).

| # | Pair | Run label |
|---|---|---|
| 1 | GBP/USD | `C1-01` |
| 2 | GBP/JPY | `C1-02` |
| 3 | AUD/USD | `C1-03` |
| 4 | USD/JPY | `C1-04` |
| 5 | GBP/CHF | `C1-05` |
| 6 | GBP/CAD | `C1-06` |
| 7 | NZD/USD | `C1-07` |
| 8 | AUD/JPY | `C1-08` |
| 9 | EUR/JPY | `C1-09` |
| 10 | USD/CAD | `C1-10` |
| 11 | USD/CHF | `C1-11` |

**EUR/USD is not part of this set.** It is the completed MOGO-004 Step 1 pilot, whose record is
`runId 2d5004cba59bed9cf0cbd0ea6d28b4db4baaef6e4a8fa090760234f10bc047e0`. The pilot is not a C1 run
and its 25 trades are not C1 observations.

**Execution order is pre-registered and is the order above.** It is recorded so that a later reader
can verify no pair was reordered, substituted or dropped after a result was seen. A pair that fails
to execute is recorded as a failed run, not silently replaced.

## 2. Declared run identity hashes

`snapshotAlexGConfig()` reads only the frozen `RULES_ALEXG` constant, and `replayParams` varies only
with `ambiguousMode`. Both hashes are therefore **campaign constants**, identical across all 11 runs,
and can be declared in advance. Any C1 package whose `identity.configHash` or `identity.paramsHash`
differs from these values was produced off-protocol and is not a C1 observation.

| Field | Declared value |
|---|---|
| `configHash` | `dbbb29b690f6692ae4d44a6833876193435ad66cc13c6e7226031e5f462c5adb` |
| `paramsHash` (`ambiguousMode: conservative`) | `8fe841e602be86cd335c9aa6804a8f30c76c57cac229a50b349194d821c6cae5` |
| `ruleVersion` | `alex_g_sr_v1` |
| Replay parameters hashed | `{ambiguousMode:'conservative', alexGSpreadMode:'none', alexGFixedSpreadPips:0, alexGSlippagePips:0, startBalance:10000}` |

> **⚠️ PROVENANCE OF THESE TWO VALUES — read before relying on them.**
> They were computed **offline**, by porting `evidenceCanonicalize` to Node and applying SHA-256 to
> `{config: snapshotAlexGConfig()}` and `{params: …}` using `RULES_ALEXG` extracted verbatim from
> `index.html`. That port is the same one that independently reproduces all 24 RUN-001 `contentHash`
> values, so it is validated — but these two hashes have **not yet been confirmed against the live
> engine**, and a pre-registration must not enshrine a hash the engine might not reproduce.
> **Status: DECLARED, CONFIRMATION PENDING.** They are confirmed by §5 step 2 before run `C1-01`.
> If the live engine disagrees, this document is wrong and a successor corrects it — it is not edited.

`runId` and `datasetHash` cannot be declared in advance: `datasetHash` covers every observed candle,
and the observation window is discovered backward from run time (PREREG-001 §6, gate item **B2**).
They are recorded per run, after the fact.

## 3. What is inherited unchanged from PREREG-001

Nothing below is altered by this document:

- **Hypotheses** — the declared family of 12 (§2), unchanged.
- **Metric and arms** — `MET_EXPECTANCY_R` primary, R-space only (§3).
- **Thresholds** — 30 resolved trades per arm minimum, promotion at ≥ 0.25R with CI excluding zero,
  Holm–Bonferroni across the family of 12, effect-size floor 0.10R (§4).
- **Promotion ceiling** — `REPLAY_EVIDENCE_ONLY` (§5).
- **Stopping rule** — adjudicate once, after the declared runs. No run may be added to reach a
  threshold; no interim look may trigger a stop (§7).
- **Censoring** — the full `alexGReplayRejected` record per run, and every reported figure states its
  suppression rate (§9).
- **Open gate items** — R4, R8, B2 and §3.4 remain open and uncleared (§11).

## 4. Declared limitations carried into C1

From `docs/reports/MOGO-004-STEP-1-PILOT-RECOVERY-REPORT.md` §4. These are properties of the
instrument, declared before observation rather than explained after it.

| ID | Limitation | Status for C1 |
|---|---|---|
| **L1** | Window is discovered from run time; two runs at different times are not window-comparable | Unresolved by design (B2). Each run records its own absolute window. |
| **L2** | `configHash`/`paramsHash` were computed but never persisted | **Resolved in v12.19.0.** Both are now persisted into `identity`. Unrecoverable for RUN-001 and the pilot. |
| **L3** | `alexGReplayRejected` is memory-only and survives exactly one run | **Binding operational constraint** — see §5. |
| **L4** | Browser export fails silently; egress is via the local receiver on `127.0.0.1` | Unresolved. Receiver path is the supported egress. |
| **L5** | `commitHash` is `null`/`UNAVAILABLE` in packages | Recorded externally per run. |
| **L6** | Export-verification by re-import not performed | Open for the pilot; required per PREREG-001 §8.5 for C1. |

## 5. Per-run protocol — binding

**L3 makes ordering load-bearing.** `alexGReplayRejected` is reassigned on every run. Eleven runs
executed back-to-back would retain one rejection record and lose ten, making PREREG-001 §9
unsatisfiable for ten of eleven pairs. This is not a theoretical risk: it is exactly how the pilot's
first run lost its rejection record permanently.

1. **Before `C1-01` only —** launch a **fresh** disposable profile via
   `scripts/browser_test_profile.sh --origin http://localhost:<PORT> --launch`, preserve the printed
   isolation manifest, and connect OANDA **practice** credentials in that window. A fresh profile is
   required: the pilot profile already contains pilot packages, and commingling two campaigns in one
   evidence store is what produced the pilot's two-partition problem.
2. **Before `C1-01` only —** confirm `APP_VERSION === '12.19.0'` and confirm the two declared hashes
   in §2 against the live engine. **If either hash disagrees, stop and do not run C1.**
3. **For each pair, in the order declared in §1:** run the replay **once**.
4. **Immediately after each run, before the next begins:** capture that run's `alexGReplayRejected`
   and its packages to the receiver. **Not after several runs. After each one.**
5. **Per run, record:** `runId`, `datasetHash`, `configHash`, `paramsHash`, the observed absolute UTC
   window, per-timeframe candle counts, ADR-011 completeness, `APP_VERSION`, repository commit, and
   the rejection record with suppression rate.
6. **After all 11:** verify every package independently (clean-room canonicalization and hash
   recomputation), partition by `runId`, then adjudicate **once** per PREREG-001 §7.

## 6. What this document does not do

- **It does not adjudicate anything.** No hypothesis has been tested. PREREG-001 §7 permits
  adjudication once, after the declared runs complete; zero C1 runs have executed.
- **It does not clear R4, R8, B2 or §3.4.** All remain open.
- **It does not approve live execution.** The ceiling remains `REPLAY_EVIDENCE_ONLY`, RZR remains
  suspended, and no strategy is approved for live trading.
- **It does not predict an outcome.**

---

**Declared before any C1 observation exists. If any part of this document proves wrong, it stays
wrong and a successor corrects it.**

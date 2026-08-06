# MOGO-003 — Verified Replay Record

**Purpose:** the authoritative register of ALEX replay runs whose identity, dataset and Evidence
Packages were captured and verified end-to-end. A run appears here only if its `runId` recomputes from
its own stored inputs and its packages were verified against bytes read back off disk.

**Standing rule of this register:** entries here are **verified replay evidence**. Live forward-paper
observations are a *different evidence class* and are never merged, averaged, or compared line-for-line
with entries in this file. See §0.

---

## 0. Evidence classes — and why they are never mixed

| | Verified replay evidence (this register) | Live-paper observation |
|---|---|---|
| Persistence | Evidence Packages: IndexedDB + disk export, SHA-256 content hash | browser `localStorage` only |
| Identity | deterministic `runId` over strategy + pair + absolute UTC window + `datasetHash` + `configHash` + `paramsHash` | none |
| Reproducible | dataset fingerprinted; re-running identical inputs yields the identical `runId` | not reproducible |
| Verification | re-import proof: parse + schema + identity + SHA-256 + canonical byte equality | none available |
| MOGO-003 §9 tier | citable run-level evidence | Tier 1 initial behavioural observation |
| Execution gate value | may inform research direction | may justify an *operational* change only |

Neither class validates a setup on its own. Sample size governs that, and no ALEX setup is validated.

---

## RUN-001 — ALEX EUR_USD, 90-day lookback

**Executed:** 2026-08-03 · **Authorization:** single authorized replay, operator-initiated ·
**Mode:** `REPLAY` · **No paper or live execution. No OANDA writes. Practice data retrieval only.**

### Identity and hashes

| Field | Value |
|---|---|
| `runId` | `3d7c3dc1af7fea769af06fda26f08da73a4c605d931bbde0947021f3aa5ab806` |
| `datasetHash` | `d8728233d78fc73c2475958e1e4e4f0569fee913b93b1f8091c5108874395041` |
| `configHash` | `dbbb29b690f6692ae4d44a6833876193435ad66cc13c6e7226031e5f462c5adb` |
| `paramsHash` | `8fe841e602be86cd335c9aa6804a8f30c76c57cac229a50b349194d821c6cae5` |
| Strategy ID / rule version | `alex_g_sr_v1` / `alex_g_sr_v1` |
| Engine build | `APP_VERSION` 12.9.0 · repository commit `65c9444` |
| Instrument | EUR_USD (single pair) |
| Requested lookback | 90 days |
| **Observed absolute window** | **2026-03-25T23:00:00Z → 2026-08-03T10:00:00Z** |
| Observed candle counts | W 73 · D 150 · H4 600 · H1 2,220 |
| Dataset completeness (ADR-011) | W/D/H4/H1 all `COMPLETE` |
| Replay params | `ambiguousMode: conservative`, spread `none`/0, slippage 0, start balance 10,000 |
| Zones detected | H1 64 · H4 17 · D 2 · W 1 |

`runId` was independently recomputed from the stored window, `datasetHash`, `configHash` and
`paramsHash` and reproduces exactly.

**Window caveat, recorded rather than smoothed over:** the control is labelled "90 days", but datasets
are fetched **by candle count per timeframe**, so the observed H1 window spans ~131 calendar days and
the D/W context reaches substantially further back. The identity records the true absolute window,
which is what makes this visible. "90 days" is a control label, not the sample boundary.

### Authoritative results

**Overall:** 39 setups qualified → 24 trades, 15 suppressed · **6W / 18L** · **−6.00R** ·
expectancy **−0.25R** · profit factor 0.67 · max drawdown 9R · 0 unresolved · 0 ambiguous.

| Setup (canonical) | Internal id | Trades | W | L | BE | Unresolved | Win rate | Total R | Expectancy | Profit factor |
|---|---|---|---|---|---|---|---|---|---|---|
| Repeated Zone Reaction (RZR) | `A_repeatedReaction` | 16 | 5 | 11 | 0 | 0 | 31.25% | −1.00R | −0.0625R | 0.909 |
| Break & Retest | `B_breakRetest` | 8 | 1 | 7 | 0 | 0 | 12.50% | −5.00R | −0.6250R | 0.286 |

All 15 suppressions were `EXISTING_OPEN_TRADE_SAME_PAIR_TIMEFRAME` (10 RZR, 5 B&R) — a
one-position-per-pair-per-timeframe portfolio constraint, not a strategy rejection. **The sample is
conditioned on that constraint**, and those setups' outcomes are unobserved.

Direction split: RZR sell 8 / buy 8 · B&R sell 5 / buy 3. The 3 Break & Retest buys confirm the
v4.0.1 zone-role correction is in force; the pre-v4.0.1 "every B&R trade is a SELL" direction-lock no
longer applies from engine 12.9.0 onward.

### Naming — one setup, one canonical name

"Repeated Reaction" and "Repeated Zone Reaction" are **the same setup category**, not two setups.
Canonical usage from this record forward:

- **Canonical name:** Repeated Zone Reaction · **abbreviation:** RZR · **internal id:**
  `A_repeatedReaction` · **stored display label:** `REPEATED ZONE REACTION`
- "Repeated Reaction" is a deprecated informal alias and should not appear in new records.

Mapping is deterministic in source at `index.html:3525` and was confirmed in 24/24 packages.

### Evidence Packages

24 packages, one per resolved trade, schema `mogo.evidence-package.v1`, all `mode: REPLAY` under the
single `runId`, all completeness `PARTIAL`, all carrying a SHA-256 `contentHash`
(`contentHashProvenance: OBSERVED`, zero unverifiable). IDs run
`PKG|alex_g_sr_v1|20260406|1` … `PKG|alex_g_sr_v1|20260728|1` (two dates carry a `|2`: `20260513`,
`20260617`). Replay trade IDs are namespaced `REPLAY|3d7c3dc1af7f|…` so a setup observed both live and
in replay cannot collide.

**Durable location (outside the repository, deliberately):**
`~/Desktop/MOGO-Evidence/alex_g_sr_v1-EUR_USD-90d-3d7c3dc1af7f/` — 24 packages + 4 harvest JSONs.

**Export verification:** the first export attempt silently wrote only 10 of 24 files — exactly the
EXP-001 failure mode — and the engine correctly refused to mark those exported. Re-import verification
(parse + schema + identity match + SHA-256 + canonical byte equality against the stored package) then
confirmed each file, and re-attempting only the still-unverified packages converged at **24/24
`EXPORT_VERIFIED_BY_REIMPORT`**. Zero write failures, zero storage banners.

> The `exportVerified` stamp is written to the package record *after* the file bytes are produced, so
> the exported **files** carry `exportedAt: null`. That is by design — the content hash excludes the
> export block. The verification outcome for this run is preserved in
> `RUN-HARVEST-harvest_final.json` in the same directory (`VERIFIED_ON_DISK: 24`).

### Which rules actually executed

**`alex_g_sr_v1` executed detection, classification and trade construction. `alex_g_sr_v1_1` did not
participate**, and the string `alex_g_sr_v1_1` appears in 0 of 24 packages. Traced, not inferred:

- `RULES_ALEXG.ruleVersion = 'alex_g_sr_v1'` (`index.html:2364`, protected constant) → setup record
  (`3523`) → trade (`3792`) → `identity.strategyVersion`, provenance `OBSERVED` (`11930-11948`).
- Both v1.1 gates — `alexGV11EntryDayEligible` (`4583`) and `alexGV11SetupTypePermitted` (`4619`) —
  live inside `alexGEvaluatePairForLiveSetups`, the **live-paper path only**, unreachable from
  `runAlexGReplay` / `alexGRunSetupReplay` / `alexGConstructTrade` / `alexGWalkOutcome`.
- Confirmed behaviourally: entries occur on Thu (3) and Fri (5), which v1.1 `ALEX_V11_001`
  (Mon–Wed) would have blocked; 16 RZR trades exist, which v1.1 `ALEX_V11_006` (RZR suspension)
  would have blocked in live paper.

This matches the repository's own note at `index.html:2681-2686`: `strategySpecificationVersion`
remains `alex_g_sr_v1` because v1.1 changes no engine parameter; `ALEX_V11_RULE_VERSION` is a
*release* label.

### Independent classification verification

Every package was re-classified from **stored structure alone** (break-cycle evidence present → Break &
Retest; touch ≥ 4 with `breakCycleId`/`brokenDirection`/`barsSinceBreak` all null → RZR), ignoring the
stored `setupType`:

- 8/8 Break & Retest packages carry break-cycle evidence; 0/16 RZR packages do.
- 24/24 `setupId` tokens agree with `setupType`; 24/24 labels map correctly; no touch < 4.
- **Zero classification conflicts.**

Classification precedence (`alexGClassifyTouch`, `index.html:3554-3572`): touch < 4 → no setup; Break &
Retest evaluated first and exclusively; RZR only if B&R does not qualify; `setupEligibility` written
once, never overwritten. Therefore a stored **RZR implies B&R was tested and failed** (derivable),
while a stored **B&R says nothing about whether RZR would also have qualified** (not derivable). This
one-directional ambiguity affects no row in RUN-001.

### Trustworthiness of RUN-001 evidence

| Use | Verdict |
|---|---|
| Overall performance | **Trustworthy** — recomputed independently from the packages |
| Setup-level performance | **Trustworthy** — 24/24 classifications independently confirmed |
| Rule-level attribution | **Partial** — version chain is `OBSERVED`; per-rule attribution absent from the schema |
| Loss forensics | **Partial** — geometry, R, MAE/MFE, zone refs and context present; break/retest candles, market context, decision chain and excursion timing absent |

> **RUN-001's ceiling is fixed, 2026-08-03.** Later units improved what *future* runs capture, and
> none of it can be retro-filled into these 24 immutable packages: **v12.10.0 (Unit A)** added the
> version split, `realizedR` and break/retest candle references; **v12.11.0 (Unit B)** added rule
> attribution; **v12.12.0 (Unit C1)** added excursion timing (`timeToMFE`/`timeToMAE`) and a
> populated `exitPathCandleRefs`; **v12.13.0 (Unit C2-M1)** added a bounded own-timeframe
> market-context window and evidence lineage; **v12.14.0 (Unit C2-M2)** added higher-timeframe
> context anchored at the entry candle's close. **RUN-001 predates all five** — it was captured on engine 12.9.0
> and carries none of them, and nothing has been or will be backfilled. Untraded-candidate context,
> the content-addressed candle store and decision chains remain unimplemented for every run, and
> browser verification of timing- and context-bearing packages is still pending.

**A package cannot re-derive its own classification.** Internal consistency is checkable; reproduction
still requires the source code plus a dataset matching `datasetHash`. See
`docs/MOGO-003-EVIDENCE-SCHEMA-CORRECTIONS.md`.

### Conclusions

1. **Neither setup is validated.** Break & Retest is **not validated**. RZR is **not validated** and
   **remains suspended from paper and live execution**. No strategy is approved for live execution.
2. **No rule, threshold or classification change is proposed from this run.** 8 and 16 trades cannot
   distinguish a real edge from variance, in either direction.
3. RUN-001 is **valid** and remains the authoritative ALEX sample. No package requires correction or
   invalidation.
4. The MOGO-002.8B live-paper figures are a **different, unverified sample** and are annotated as such
   in that document. They are not superseded by RUN-001 — they are simply not comparable to it.

---

## Register

| Run | Date | Strategy | Instrument | Window | runId (12) | Packages | Status |
|---|---|---|---|---|---|---|---|
| RUN-001 | 2026-08-03 | `alex_g_sr_v1` | EUR_USD | 2026-03-25 → 2026-08-03 | `3d7c3dc1af7f` | 24 | Verified · authoritative |
| MOGO-004 pilot | 2026-08-04 | `alex_g_sr_v1` | EUR_USD | 2026-03-27 → 2026-08-04 | `2d5004cba59b` | 25 | Verified · pilot of record |
| C1-01 | 2026-08-06 | `alex_g_sr_v1` | GBP_USD | 2026-03-31 → 2026-08-06 | `f230a04976d4` | 24 | Verified |
| C1-02 | 2026-08-06 | `alex_g_sr_v1` | GBP_JPY | 2026-03-31 → 2026-08-06 | `915bc83f587d` | 12 | Verified |
| C1-03 | 2026-08-06 | `alex_g_sr_v1` | AUD_USD | 2026-03-31 → 2026-08-06 | `88d924c0be04` | 20 | Verified |
| C1-04 | 2026-08-06 | `alex_g_sr_v1` | USD_JPY | 2026-03-31 → 2026-08-06 | `4689c3d17f80` | 24 | Verified |
| C1-05 | 2026-08-06 | `alex_g_sr_v1` | GBP_CHF | 2026-03-31 → 2026-08-06 | `ff5dd403ea8d` | 24 | Verified |
| C1-06 | 2026-08-06 | `alex_g_sr_v1` | GBP_CAD | 2026-03-31 → 2026-08-06 | `ca6c0038a27b` | 24 | Verified |
| C1-07 | 2026-08-06 | `alex_g_sr_v1` | NZD_USD | 2026-03-31 → 2026-08-06 | `80a17b22e3f8` | 17 | Verified |
| C1-08 | 2026-08-06 | `alex_g_sr_v1` | AUD_JPY | 2026-03-31 → 2026-08-06 | `3b36727d5694` | 17 | Verified |
| C1-09 | 2026-08-06 | `alex_g_sr_v1` | EUR_JPY | 2026-03-31 → 2026-08-06 | `8f70d403fae1` | 21 | Verified |
| C1-10 | 2026-08-06 | `alex_g_sr_v1` | USD_CAD | 2026-03-31 → 2026-08-06 | `367dd27fd6b8` | 19 | Verified |
| C1-11 | 2026-08-06 | `alex_g_sr_v1` | USD_CHF | 2026-03-31 → 2026-08-06 | `81b566549f6a` | 19 | Verified |

---

## Campaign C1 — completion entry (PREREG-001 §8 item 7)

**This section records completion of the declared runs. It adjudicates nothing.** PREREG-001 §7
permits adjudication once, after the declared runs complete; that step has not begun and no result,
interpretation or conclusion about strategy performance appears anywhere in this entry.

| | |
|---|---|
| Campaign | `CAMP\|ALEX\|C1\|2026-08-05` (PREREG-002) |
| Declared runs | 11 · **executed 11** · in the pre-registered order, no substitutions |
| Completed | 2026-08-06 |
| Engine | `APP_VERSION` **12.19.0** on all 221 packages |
| Repository commit | `f7f0c40` |
| Strategy | `alex_g_sr_v1`, unmodified throughout |

### Campaign-level verification

| Property | Result |
|---|---|
| Campaign packages (`mode == REPLAY`) | **221** |
| Hash verification | **221 / 221 PASS**, 0 FAIL — independent re-canonicalization under `mogo.evidence-canon.v1` (K1–K8) and SHA-256 recomputation |
| Distinct `runId`s | **11** — one per declared run, no duplicates, no commingling |
| Distinct `configHash` | **1** — `dbbb29b690f6…62c5adb`, matches PREREG-002 §2 |
| Distinct `paramsHash` | **1** — `8fe841e602be…21c6cae5`, matches PREREG-002 §2 |
| `datasetHash` | 11 distinct, one per instrument, as expected |
| ADR-011 completeness | `COMPLETE` on W/D/H4/H1 for all 11 runs |
| Gate fields | `triggeredConditions`, `timeToMFE`, `timeToMAE`, market context populated on **216 / 221**; the 5 exceptions are explained below |
| Rejection records (§9) | Captured for **all 11** runs, every record carrying a reason |

The single `configHash` and single `paramsHash` across 221 observations and eleven instruments is the
pre-registration's central control: every package is verifiably the same configuration and the same
replay parameters, declared in advance and confirmed against the live engine before the first run.

### Censoring (PREREG-001 §9)

| | |
|---|---|
| Trades created | 226 |
| Suppressed | 128 — all `EXISTING_OPEN_TRADE_SAME_PAIR_TIMEFRAME` |
| Considered | 354 |
| **Campaign suppression rate** | **36.2%** (per-run range 24.2% – 58.6%) |

**The 221 observations are a biased draw from 354, not a smaller unbiased sample.** Any figure
computed on this evidence must state its suppression rate.

### Explained nulls — 5 of 221 (2.3%)

Five packages carry a null excursion-timing field. In every case the recomputation returned
`AGREES` with `matchesEngineExtremes: true` and no data-quality flag, and the null is present because
the excursion itself was zero — not because capture failed.

| Run | Field | Cause | Outcome |
|---|---|---|---|
| C1-03 | `timeToMFE` | `mfePips` 0 | Loss — no favourable movement |
| C1-04 | `timeToMFE` | `mfePips` 0 | Loss — no favourable movement |
| C1-07 | `timeToMFE` | `mfePips` 0 | Loss — no favourable movement |
| C1-11 | `timeToMFE` | `mfePips` 0 | Loss — no favourable movement |
| C1-06 | `timeToMAE` | `maePips` 0 | Win — no adverse movement |

These are nulls because the event did not occur, and must not be treated as missing data.

### Evidence set

| | |
|---|---|
| Location | `<repo>/evidence/` (git-ignored; evidence is never committed) |
| Artifacts | 33 — eleven runs × `PACKAGES` / `REJECTED` / `HARVEST` |
| Backup | `~/Desktop/MOGO-Evidence-C1/` with `MANIFEST.txt` and the receiver transcript; all 33 verified byte-identical by SHA-256 manifest comparison |

**One handling note for anyone analysing this set:** `C1-01-GBP_USD-PACKAGES.json` contains **25**
packages — 24 campaign packages plus one `LIVE_CLOSE` package, `PKG|current_strategy|20260806|1`,
written by the paper engine into the same profile. C1-01's capture posted the whole store; every
capture from C1-02 onward posted only the isolated run. **Filter `mode == "REPLAY"` on that file.**
The package is recorded rather than deleted, and is excluded from every figure above.

### Open items

- **§8 item 4** — `commitHash` is `null`/`UNAVAILABLE` in every package (limitation L5). Satisfied
  externally: the repository commit for all eleven runs is `f7f0c40`.
- **§8 item 5** — export-verification by re-import (limitation L6) remains **not performed** for any
  campaign run.

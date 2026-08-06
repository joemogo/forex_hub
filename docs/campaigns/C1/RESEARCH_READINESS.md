# RESEARCH_READINESS.md — Campaign C1

**Campaign:** `CAMP|ALEX|C1|2026-08-05` · **Assessed:** 2026-08-06 · **Engine:** 12.19.0

This document answers five questions about what this evidence set can and cannot support. It
performs no statistical analysis, forms no arms, and draws no conclusion about strategy performance.

---

## 1. Is this campaign suitable for statistical analysis?

**Yes — with three conditions that are not optional.**

What makes it suitable: 221 hash-verified observations across eleven instruments, one engine version,
one `configHash`, one `paramsHash`, a complete censoring record, rule-level attribution
(`triggeredConditions`) on every package, excursion timing, and market context. The comparison
surface — R-space — is reproducible. The hypotheses, thresholds, metric, arms, multiplicity
correction and stopping rule were all declared before any observation existed.

The three conditions:

1. **Every figure must state its suppression rate.** 128 of 354 considered setups were suppressed by
   a non-random mechanism. PREREG-001 §9 is explicit: *a result computed on a censored sample that
   does not report the censoring is not a result.*
2. **R-space only.** Money-space values are flagged `DERIVED` with `LIVE_DATA_DEPENDENCY` because
   `pipValuePerLot()` reads live pair data. `pnl` is recorded `UNAVAILABLE` rather than reconstructed.
   Money-space is not reproducible across runs and must not be analysed.
3. **The declared family and correction must be applied as pre-registered** — Holm–Bonferroni across
   the family of 12, the 30-resolved-per-arm floor, the 0.10R effect-size floor. Whether any arm
   reaches its floor is an adjudication question and is deliberately not answered here.

**Not suitable for:** anything described as out-of-sample (see Q2), money-space performance, or
live-trading inference — replay is not the live rule set (PREREG-001 §3.4, open).

## 2. Is the evidence reproducible?

**The evidence is verifiable. The runs are not reproducible. These are different things, and the
distinction matters.**

| | |
|---|---|
| **Verifiable** | ✅ Yes. Every package is self-checking: canonicalize under `mogo.evidence-canon.v1`, SHA-256, compare to `contentHash`. 221/221 pass. This requires only the files. |
| **Reproducible (re-running to regenerate the same evidence)** | ❌ **No, and it cannot be made so.** |

The blocker is structural, not an oversight. `fetchCandlesRange` paginates backward from **run time**
by candle count — there is no from/to control (gate item **B2**, open). Re-running any pair today
observes a different window, produces a different `datasetHash`, and therefore a different `runId`.
It would be a different run, not a reproduction.

**Consequence:** the eleven `datasetHash` values in `CAMPAIGN_C1_IDENTITY.md` are the only surviving
fingerprint of the exact candle data used. The candles themselves were not archived — only their
hash. A future researcher can prove two datasets differ; they cannot reconstruct this one.

## 3. Can another researcher independently verify it?

**Yes for integrity. Partially for classification. No for capture.**

| Layer | Independently verifiable? | How |
|---|---|---|
| **Artifact integrity** | ✅ Fully | `shasum -a 256` against the manifest |
| **Package integrity** | ✅ Fully | Re-canonicalize + SHA-256 vs `contentHash`; needs only the files and ~40 lines of code implementing K1–K8 |
| **Identity conformance** | ✅ Fully | Compare each package's `configHash`/`paramsHash` to PREREG-002 §2, committed before the runs |
| **Pre-registration precedence** | ✅ Fully | `git log` — PREREG-002 is in `b71f016`, tag `v12.19.0`, pushed to `origin` before any C1 run |
| **Rule classification** | ⚠️ Partially | `triggeredConditions` records requirement, observed value and `satisfied` per condition, so internal consistency is checkable. **A package cannot re-derive its own classification** — that needs the source plus a matching dataset |
| **The capture act** | ❌ No | Evidence was read from a live browser session via an operator-pasted console script, requiring an OANDA practice credential |

A third party given only `evidence/` and the two pre-registrations can confirm that these packages
are internally consistent, unaltered, and conform to constants declared in advance. They cannot
confirm the packages describe real OANDA data without the credential and the engine.

## 4. Can every reported statistic be regenerated?

**Yes, from the packages alone — and that is the stronger claim.**

Every R-space quantity needed for adjudication is a recorded field on the packages: `plannedR`,
`recordedResultR`, `realizedR` with provenance and basis, `maeR`, `mfeR`, `timeToMFE`, `timeToMAE`,
`exitReasonCode`, `setupType`, `timeframe`, `instrument`, `triggeredConditions`, and market context.
Suppression counts and reasons come from the `REJECTED` artifacts.

Three caveats:

- **The `HARVEST` `stats` blocks are engine-computed convenience figures, not the source of truth.**
  They should be *recomputed* from packages during adjudication, not cited. Where a harvest figure and
  a package-derived figure disagree, the packages win.
- **Money-space cannot be regenerated** and must not be analysed (Q1, condition 2).
- **Trades that produced no package cannot be analysed.** Five still-open trades across the campaign
  produced no package by design; they exist in the harvest trade arrays only.

## 5. Is anything missing before adjudication?

**One pre-registration requirement is unmet, and three things need deciding. None is a blocker to
starting, but all should be recorded before conclusions are drawn.**

### Unmet

- **PREREG-001 §8 item 5 — export-verification by re-import (L6).** Not performed for any campaign
  run. Every `export` block reads all-null; packages were recovered by direct read, not through the
  export path. This is the only §8 requirement genuinely unsatisfied, and it is unsatisfied for all
  eleven runs.

### Needs a decision before adjudication, not during it

- **Arm construction is declared but not operationalized.** PREREG-001 §3 defines arms as *resolved
  trades where the rule's condition held* (A) versus *did not hold* (B), on the basis of same
  strategy, engine version and dataset hash. Since `datasetHash` differs per instrument, whether arms
  pool across pairs or are formed within them changes the answer and must be settled from the
  pre-registration's text **before** any figure is computed.
- **The 30-resolved-per-arm floor** applies per arm, not per campaign. Whether it is met is an
  adjudication finding; deciding how arms are formed determines it.
- **The C1-01 filter.** `C1-01-GBP_USD-PACKAGES.json` carries one non-campaign `LIVE_CLOSE` package.
  Any analysis must filter `mode == "REPLAY"`. Documented in the manifest, the certificate (B6) and
  the §8.7 record.

### Present and sufficient

Hash verification, censoring records, gate fields, identity conformance, pre-registration precedence,
backup, and a clean repository. Nothing in this list blocks adjudication from beginning.

---

## Summary

| Question | Answer |
|---|---|
| Suitable for statistical analysis? | **Yes**, under three mandatory conditions |
| Evidence reproducible? | **Verifiable yes; re-runnable no** — structurally impossible (B2) |
| Independently verifiable? | **Yes** for integrity and conformance; **no** for the capture act |
| Every statistic regenerable? | **Yes** from packages, in R-space, recomputed not cited |
| Anything missing? | **One unmet §8 item (L6)**; arm construction needs settling first |

**No adjudication has begun. No statistic has been computed. No conclusion about strategy performance
appears in this document.**

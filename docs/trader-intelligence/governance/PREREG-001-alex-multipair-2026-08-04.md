# PREREG-001 — ALEX multi-pair replay campaign

**Pre-registration id:** `PREREG-001`
**Declared:** 2026-08-04
**Declared by:** Joe Mogollon (Engineering Authority)
**Strategy:** `alex_g_sr_v1` · **Engine at declaration:** `APP_VERSION` 12.18.0 · **HEAD:** `f8004fe`
**Status:** **DECLARED — no observation for these questions exists at the time of writing.**

---

> ## ⛔ THIS DOCUMENT IS IMMUTABLE
>
> **It is evidence, not a plan.** Its entire value is that it existed, in this form, **before** the
> data it governs. A pre-registration that can be edited after results are seen is not a
> pre-registration — it is a story told afterwards.
>
> **It is never edited. Not to fix a typo, not to add a hypothesis, not to adjust a threshold.**
> If anything here must change, a **successor** is written (`PREREG-002`) that names this document as
> its predecessor and states what changed and why. This one stays exactly as it is, including any
> error, because the error is part of the record.
>
> **Any analysis using a threshold, metric, arm definition or stopping rule different from what
> appears below is exploratory by definition, and can never be promotion-eligible** — regardless of
> how well-founded the change may be.
>
> Immutability is enforced by git, not by intent: see §10.

---

## 1. Why this campaign exists

MOGO holds **one** verified replay run. RUN-001 produced 24 resolved trades on a single pair over a
single window: RZR 16 trades at −1.00R, Break & Retest 8 trades at −5.00R. **Neither sample settles
anything in either direction**, and RUN-001 predates the engine units that record rule attribution,
excursion timing and market context, so it cannot answer a rule-level question at all.

Twelve ALEX hypotheses are `COLLECTING` — implemented, observed, and short only of sample. This
campaign exists to move them to an adjudicated state. **Any adjudicated state.**

**The expected outcome is `INSUFFICIENT` or `INCONCLUSIVE` for most of them.** That is recorded here,
in advance, so that reporting it later is not a disappointment to be argued around.

## 2. Hypotheses under test — the declared family

**Family size: 12.** These are the twelve hypotheses at `currentStatus: COLLECTING` in
`governance/hypothesis-registry.json` as of this date. **No hypothesis may be added to this family
after this document is declared.**

| # | Hypothesis | Setup scope | Resolved trades today | Shortfall to 30/arm |
|---|---|---|---|---|
| 1 | `HYP\|AXR-001` | ALL_SETUPS | 24 | 6 |
| 2 | `HYP\|AXR-002` | ALL_SETUPS | 24 | 6 |
| 3 | `HYP\|AXR-003` | `B_breakRetest` | 8 | 22 |
| 4 | `HYP\|AXR-004` | `B_breakRetest` | 8 | 22 |
| 5 | `HYP\|AXR-005` | `A_repeatedReaction` | 16 | 14 |
| 6 | `HYP\|AXR-007` | ALL_SETUPS | 24 | 6 |
| 7 | `HYP\|AXR-030` | ALL_SETUPS | 24 | 6 |
| 8 | `HYP\|AXR-041` | ALL_SETUPS | 24 | 6 |
| 9 | `HYP\|AXR-043` | ALL_SETUPS | 24 | 6 |
| 10 | `HYP\|AXR-051` | ALL_SETUPS | 24 | 6 |
| 11 | `HYP\|AXR-071` | ALL_SETUPS | 24 | 6 |
| 12 | `HYP\|AXR-090` | ALL_SETUPS | 24 | 6 |

Each hypothesis's condition, arms, metric and thresholds are those already recorded against its id in
`hypothesis-registry.json` at HEAD `f8004fe`. **This document does not restate them and does not
redefine them** — restating a definition is how two analyses come to disagree.

**Explicitly outside this family and not testable by this campaign:** the 19 `UNSUPPORTED`
hypotheses (MOGO does not implement the rule, or the rule is MOGO-authored), and the 10 `UNRESOLVED`
(4 produce no evidence field at all, 4 run only on the live path, 2 have unresolved fidelity status).
**No replay campaign of any size can advance these.**

## 3. Metric and comparison

| | |
|---|---|
| **Primary metric** | `MET_EXPECTANCY_R` — net R ÷ resolved trades |
| **Secondary** | `MET_WIN_RATE`, `MET_NET_R`, `MET_MAE_PIPS`, `MET_MFE_PIPS` |
| **Arms** | **A:** resolved trades where the rule's condition held · **B:** resolved trades where it did not |
| **Arm basis** | same strategy, same engine version, same dataset hash |
| **Comparison surface** | **R-space only** |

**Money-space figures are recorded and never compared.** `pipValuePerLot()` reads live `pairData`
(`index.html:15031`), so money-space is not reproducible across runs. This is gate item R4 and it is
open. Declared here so no later analysis can treat a money figure as comparable.

**All figures reported in this campaign are gross of transaction costs.** Spread and slippage have
zero effect by design and commission does not exist (gate item R8, open). At 1–2 pips against a 20–40
pip stop this is roughly 3–10% of risk per round turn — **enough to move a marginal expectancy across
zero.** Any near-zero result must state this.

## 4. Thresholds — declared in advance

Taken from `STATISTICAL-GOVERNANCE.md` and `hypothesis-registry.json`. **Not derived from any observed
result. Not lowerable.**

| Threshold | Value |
|---|---|
| Minimum operational sample | **30 resolved trades per arm** — the floor below which no promotion may occur |
| Recommended statistical sample | **100 resolved trades per arm** |
| Promotion | armA expectancy exceeds armB by **≥ 0.25R** with the confidence interval **excluding zero** |
| Rejection | difference **< 0.25R**, or favours armB, **with both arms at or above 30** |
| Interval method | Wilson for proportions; mean ± 1.96 × SE of per-trade R for expectancy |
| Multiplicity | **Holm–Bonferroni across the declared family of 12** |
| Effect-size floor | < 0.10R is indistinguishable and is not reported as an effect |

**If a threshold is found to be wrong, it is corrected in a successor pre-registration governing
future evidence — never applied retroactively to evidence already collected under this one.**

## 5. Promotion ceiling

# `REPLAY_EVIDENCE_ONLY`

**No hypothesis in this family may be promoted above `REPLAY_EVIDENCE_ONLY` on the strength of this
campaign, at any sample size, however large.** Replay observes one mechanism over one dataset;
agreement with the engine that produced the trades is not independent confirmation. **The ceiling is
categorical, not a confidence discount.** Escaping it requires a different evidence modality, not
more replay.

## 6. Campaign design

**Campaign C1** of `REPLAY-CAMPAIGN-PLAN.md`, preceded by a verification pilot.

| | Pilot | C1 |
|---|---|---|
| Purpose | **Verify capture**, not collect evidence | Collect evidence |
| Instrument | EUR_USD | 11 additional majors |
| Runs | 1 | 11 |
| Lookback parameter | 90 days | 90 days |
| Expected yield | ~24 trades | ~264 trades |

**Pilot gate — declared in advance.** The pilot proceeds to C1 **only if** the captured packages
carry populated `triggeredConditions`, `timeToMFE`/`timeToMAE`, and market context. **If they do not,
C1 does not run.** The pilot exists to be allowed to fail; nothing since engine 12.9.0 has been
exercised in a browser, and C1 would otherwise spend eleven authorizations on unverified capture.

**Pairs are named at authorization time**, in the run record, before each run — not chosen after
seeing another pair's result.

### ⚠️ The window is discovered, not chosen — stated plainly

`fetchCandlesRange(pair, tf, totalCount)` (`index.html:5937`) paginates **backward from run time by
candle count**. There is no `from`/`to` control. This is gate item **B2** and it is open.

**Consequences, recorded now rather than explained later:**

- *"90 days"* is a **control label, not a sample boundary.** RUN-001's requested 90 days produced an
  observed H1 window spanning ~131 calendar days, with D/W context reaching substantially further.
- The absolute window of every run in this campaign will be **recorded after the fact** from the
  observed candles, never declared beforehand — because it cannot be.
- **What is pre-declared is the parameter (90 days) and the instrument list — not the dates.**
- The campaign therefore **cannot** satisfy true in-sample / out-of-sample partitioning, and **no
  result from it may be described as out-of-sample.**

## 7. Stopping rule

**Declared in advance. This is not "collect until it resolves."**

> **Run the pilot, then the 11 C1 runs. Then adjudicate whatever the evidence says.**

- Adjudication happens **once**, after the declared runs complete.
- **No additional run may be added to reach a threshold.** If an arm falls short of 30, the outcome is
  `INSUFFICIENT` — a recorded result, not a prompt for more data under this pre-registration.
- **No interim look may trigger a stop.** Results are not adjudicated run-by-run; optional stopping is
  how a null effect eventually crosses any threshold.
- Extending coverage is legitimate, but only under a **successor** pre-registration declared before
  those runs execute.

## 8. Required per-run record

Every run in this campaign records, without exception:

1. `runId`, `datasetHash`, `configHash`, `paramsHash`
2. The **observed absolute UTC window** and per-timeframe candle counts
3. ADR-011 `completenessState` per timeframe
4. Engine `APP_VERSION` and repository commit
5. Hash-verified Evidence Packages, export-verified by re-import
6. **`alexGReplayRejected` in full** — see §9
7. An entry in `MOGO-003-VERIFIED-REPLAY-RECORD.md`

## 9. Censoring — the unobserved must be recorded

**RUN-001 qualified 39 setups and traded 24. Fifteen were suppressed** as
`EXISTING_OPEN_TRADE_SAME_PAIR_TIMEFRAME` — a one-position-per-pair-per-timeframe portfolio
constraint. **Those outcomes are unobserved, and the suppression is not random**: it correlates with
setup clustering, which correlates with market structure.

**The 24 observed trades are therefore a biased draw from 39, not a smaller unbiased sample.** No
sample size corrects this. It is informative censoring.

**Mandatory for every run in this campaign:** the full contents of the `alexGReplayRejected` global
(`index.html:4119` — populated after every run, non-protected UI layer) are saved alongside that run's
packages, per setup, with reason.

**Mandatory for adjudication:** every reported figure states the suppression rate for its sample.
**A result computed on a censored sample that does not report the censoring is not a result.**

## 10. Immutability — how it is enforced

| Property | Mechanism |
|---|---|
| **Content fixed** | SHA-256 of this file recorded in its own commit message |
| **Time fixed** | The git commit timestamp and parent hash. **This is the falsifiable anchor** — it cannot be backdated without rewriting history, which changes every subsequent hash |
| **Precedence provable** | This commit precedes the first observation commit of the campaign. Anyone can verify the ordering with `git log` |
| **Amendment** | A successor document only. This one is never edited |
| **Detection** | Any later edit shows as a diff against this commit, permanently |

**This is not an editable planning document.** `REPLAY-CAMPAIGN-PLAN.md` and `RESEARCH-ROADMAP.md`
are planning documents and may be revised freely. **This one may not.** The distinction is the whole
point: a plan describes what you intend to do, and a pre-registration is evidence about what you
committed to before you knew the answer.

## 11. What this document does not do

- **It does not authorize any replay run.** Authorization is a separate, explicit instruction. This
  declares what a campaign *would* test if authorized.
- **It does not approve `MOGO-RESEARCH-VALIDATION-STANDARD-V1.md`**, which remains proposed.
- It does not clear open gate items **R4**, **R8**, **B2**, or §3.4 (replay ≠ live rule set). Each is
  disclosed above as a stated limit on what the evidence can support.
- **It does not predict an outcome, and it is not a hypothesis that the strategy works.** RZR remains
  suspended from paper and live execution. No strategy is approved for live trading, and nothing in
  this campaign can approve one.

---

**Declared before any observation exists. If any part of this document proves wrong, it stays wrong
and a successor corrects it.**

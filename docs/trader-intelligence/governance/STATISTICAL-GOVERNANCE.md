# MOGO-004 — Statistical Governance

**Purpose:** one policy so every strategy is measured the same way. **Consistency, not optimization.**
Where this document and a convenient interpretation disagree, this document wins.

---

## 1. Acceptable metrics

Metrics are defined once in the metric registry (`MET_*`) and referenced by id. Restating a
definition inline is forbidden — that is how two analyses come to disagree about "win rate".

| Metric | Definition | Better when | Notes |
|---|---|---|---|
| `MET_EXPECTANCY_R` | net R ÷ resolved trades | higher | **the primary metric for every promotion** |
| `MET_NET_R` | Σ recorded R over resolved trades | higher | scale-dependent; never compare across different sample sizes |
| `MET_WIN_RATE` | wins ÷ (wins + losses) | higher | meaningless without R:R; never quoted alone |
| `MET_PROFIT_FACTOR` | gross positive R ÷ \|gross negative R\| | higher | **undefined with zero losses** — reported as null, never as infinity |
| `MET_MAE_PIPS` | mean maximum adverse excursion | lower | stop-placement evidence |
| `MET_MFE_PIPS` | mean maximum favourable excursion | higher | target-placement evidence |
| Drawdown (R) | worst peak-to-trough on the chronological equity walk | lower | current and maximum reported separately |

**R-space is the comparison surface.** Money-space figures depend on live pair data and are not
reproducible across runs; they are reported but never compared.

## 2. Confidence intervals

Every promotion-relevant figure must be reported **with an interval, not as a point estimate**. For a
proportion (win rate) use a Wilson interval; for expectancy use the mean ± 1.96 × SE of per-trade R.
**A difference whose interval includes zero is not a difference.**

## 3. Minimum sample policy

| Threshold | Value | Meaning |
|---|---|---|
| Minimum operational sample | **30 resolved trades per arm** | the floor below which no promotion may occur |
| Recommended statistical sample | **100 resolved trades per arm** | where a 0.25R effect is reliably resolvable |

Both are **declared in advance**. Neither may be lowered after a result is seen; if a sample is
insufficient, the conclusion is *"insufficient"*, which is a finding, not a failure.

## 4. Multiple-comparison handling

Testing 41 hypotheses at a 5% threshold produces roughly two false positives by construction.
Therefore:

1. **Pre-register.** A hypothesis must exist in the registry with its metric and thresholds *before*
   the evidence that tests it is analysed.
2. **Correct for family size.** Apply Holm–Bonferroni across the hypotheses tested in a campaign.
3. **Report the family.** A promoted hypothesis must state how many were tested alongside it.
4. **No post-hoc hypotheses.** A pattern noticed in existing data becomes a *new pre-registered*
   hypothesis awaiting *new* evidence — never a conclusion drawn from the data that suggested it.

## 5. Effect-size interpretation

| Expectancy difference | Interpretation |
|---|---|
| < 0.10R | indistinguishable; do not report as an effect |
| 0.10–0.25R | suggestive only; never sufficient for promotion |
| ≥ 0.25R | promotable **if** sample and interval conditions hold |
| ≥ 0.50R | large; treat with suspicion and check for a data artifact before believing it |

Statistical significance without a material effect size is not a result.

## 6. Evidence-class ceilings

| Evidence class | Maximum promotion |
|---|---|
| Replay only | `REPLAY_EVIDENCE_ONLY` — never `SUPPORTED` on its own |
| Replay + live paper | `SUPPORTED` permitted when both satisfy the gate |
| Live paper only | Tier 1 observation; may justify an operational change, never a validation claim |

Replay observes one engine over one dataset; agreement with the engine that produced the trades is
not independent confirmation.

## 7. Prohibited practices

Lowering a threshold after seeing results · quoting win rate without R:R · reporting profit factor as
infinity · comparing money-space figures across runs · promoting on a point estimate · deriving a
hypothesis from the same data used to test it · treating "not yet refuted" as support.

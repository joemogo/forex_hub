# Duplicate and Semantic Overlap Report

**MOGO-002.6 Phase 4** · **4 groups** detected at a 0.40 Jaccard threshold within a domain.

> Very few true duplicates survive to this stage: the **ingestion** pipeline already deduplicated at claim level via `compute_claim_fingerprint()`, and **36 of 195** ALEX_G claims already aggregate more than one evidence item. What remains is semantic near-overlap — and most of it is correctly `DO_NOT_MERGE`.

## KEDUP|ALEX_G|001 — SAME_CONCEPT_DIFFERENT_DETAIL / MERGE_WITH_CAVEATS

**Members:** `CLAIM|ALEX_G|20260727|012`, `CLAIM|ALEX_G|20260727|013`

**Concept:** A bullish market is a series of higher highs and higher lows.

**Differences:**

- 012 [definition/EXPLICIT]: A bullish market is a series of higher highs and higher lows.
- 013 [definition/EXPLICIT]: A bearish market is a series of lower highs and lower lows.

**Source chronology:** EVSRC|ALEX_G|20260727|001, EVSRC|ALEX_G|20260728|001, EVSRC|ALEX_G|20260728|003

_No merge blockers detected._

## KEDUP|ALEX_G|002 — RELATED_NOT_DUPLICATE / DO_NOT_MERGE

**Members:** `CLAIM|ALEX_G|20260728|023`, `CLAIM|ALEX_G|20260728|121`

**Concept:** Alex G states retail traders make up 3% of the market. No source is given for this figure.

**Differences:**

- 023 [performance_hypothesis/EXPLICIT]: Alex G states retail traders make up 3% of the market. No source is given for this figure.
- 121 [performance_hypothesis/EXPLICIT]: Alex G states 99% of traders lose money. No source is given for the figure.

**Source chronology:** EVSRC|ALEX_G|20260728|002, EVSRC|ALEX_G|20260728|005

**Merge blockers (governance):**

- 023 vs 121: thresholds differ (['3'] vs ['99'])

## KEDUP|ALEX_G|003 — RELATED_NOT_DUPLICATE / DO_NOT_MERGE

**Members:** `CLAIM|ALEX_G|20260728|104`, `CLAIM|ALEX_G|20260728|107`, `CLAIM|ALEX_G|20260728|111`

**Concept:** Conservative risk is 0.5 to 1% of the account per trade.

**Differences:**

- 104 [risk_rule/EXPLICIT]: Conservative risk is 0.5 to 1% of the account per trade.
- 107 [risk_rule/EXPLICIT]: The recommended risk, described as the industry standard, is 1 to 2% of the account per tr
- 111 [risk_rule/EXPLICIT]: The high-risk band is 3 to 5% of the account per trade.

**Source chronology:** EVSRC|ALEX_G|20260728|005

**Merge blockers (governance):**

- 104 vs 107: thresholds differ (['0.5 ', '1'] vs ['1 ', '2'])
- 104 vs 111: thresholds differ (['0.5 ', '1'] vs ['3 ', '5'])
- 107 vs 111: thresholds differ (['1 ', '2'] vs ['3 ', '5'])

## KEDUP|ALEX_G|004 — RELATED_NOT_DUPLICATE / DO_NOT_MERGE

**Members:** `CLAIM|ALEX_G|20260728|110`, `CLAIM|ALEX_G|20260728|113`

**Concept:** A 1:2 risk-to-reward ratio is used as the worked example. It is illustrative arithmetic, not stated as a required minimum.

**Differences:**

- 110 [target_rule/UNRESOLVED]: A 1:2 risk-to-reward ratio is used as the worked example. It is illustrative arithmetic, n
- 113 [target_rule/UNRESOLVED]: A second worked ratio: 5% risk at 1:3 reward produces 15% on a single trade. Again illustr

**Source chronology:** EVSRC|ALEX_G|20260728|005

**Merge blockers (governance):**

- 110 vs 113: thresholds differ (['1', '2 '] vs ['1', '15', '3 ', '5'])


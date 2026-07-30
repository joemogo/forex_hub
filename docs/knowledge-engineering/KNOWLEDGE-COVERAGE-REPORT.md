# ALEX Knowledge Coverage Report

**MOGO-002.6 Phase 9.** Numerator/denominator throughout — no single composite score, because one number would conceal that EXIT is zero and RISK has no stop rule.

## Totals

| Metric | Value |
|---|---|
| Source artifacts | 8 |
| Claims | 195 |
| Candidate-rule eligible | 115 / 195 |
| Candidate rules | 115 |
| Normalized rules | 111 |
| Deferred candidates | 4 |
| Duplicate groups | 4 |
| Contradictions | 11 |
| **Approved rules** | **0 / 111** |
| Draft rules | 111 / 111 |

## Coverage by domain

| Domain | Claims | Normalized | Deterministic | Coverage | Confidence |
|---|---|---|---|---|---|
| MARKET_CONDITIONS | 18 | 0 / 0 candidates | 0 / 0 rules | CLAIMS_ONLY_NO_RULES | NONE |
| TIMEFRAMES | 3 | 3 / 3 candidates | 0 / 3 rules | RULES_BUT_NONE_DETERMINISTIC | LOW |
| DIRECTIONAL_BIAS | 0 | 0 / 0 candidates | 0 / 0 rules | NONE | NONE |
| MARKET_STRUCTURE | 12 | 0 / 0 candidates | 0 / 0 rules | CLAIMS_ONLY_NO_RULES | NONE |
| LIQUIDITY | 5 | 2 / 2 candidates | 1 / 2 rules | PARTIAL | MEDIUM |
| SETUP | 23 | 21 / 23 candidates | 13 / 21 rules | PARTIAL | MEDIUM |
| ENTRY | 29 | 27 / 29 candidates | 0 / 27 rules | RULES_BUT_NONE_DETERMINISTIC | LOW |
| INVALIDATION | 9 | 9 / 9 candidates | 0 / 9 rules | RULES_BUT_NONE_DETERMINISTIC | LOW |
| RISK | 13 | 13 / 13 candidates | 11 / 13 rules | PARTIAL | MEDIUM |
| TRADE_MANAGEMENT | 8 | 8 / 8 candidates | 4 / 8 rules | PARTIAL | MEDIUM |
| EXIT | 0 | 0 / 0 candidates | 0 / 0 rules | NONE | NONE |
| SESSION_RESTRICTIONS | 7 | 7 / 7 candidates | 0 / 7 rules | RULES_BUT_NONE_DETERMINISTIC | LOW |
| NO_TRADE_CONDITIONS | 14 | 14 / 14 candidates | 12 / 14 rules | PARTIAL | MEDIUM |
| DISCRETIONARY_ELEMENTS | 39 | 7 / 7 candidates | 0 / 7 rules | RULES_BUT_NONE_DETERMINISTIC | LOW |
| UNRESOLVED_QUESTIONS | 15 | 0 / 0 candidates | 0 / 0 rules | CLAIMS_ONLY_NO_RULES | NONE |

## Source traceability

| Metric | Value |
|---|---|
| claimsWithSourceReference | 195 / 195 |
| rulesWithSourceMapping | 111 / 111 |
| rulesWithVerbatimExcerpt | 111 / 111 |

## Unresolved

| Metric | Value |
|---|---|
| rulesWithUnresolvedElements | 66 / 111 |
| nonDeterministicRules | 70 / 111 |

## Highest-priority missing knowledge

1. STOP PLACEMENT — zero rules across 195 claims and 8 sources. Position size is not computable without it, so no risk rule here can be implemented.
2. EXIT — zero claims and zero rules in the entire library.
3. SESSION WINDOWS — session rules exist and are prescriptive, but their hours are shown on-screen and never spoken, so they are absent from every transcript.
4. INDICATOR SETTINGS — the EMA is load-bearing in two sources and its period is never stated.
5. SWING SIGNIFICANCE — the parameter that decides which highs and lows count is undefined and is contradicted across educators.

## Recommended next source material

1. An ALEX_G source that states stop placement (BACKLOG-002/A1-STOP). Highest leverage single acquisition: it would make the 13 risk rules implementable.
2. Further LIVE sessions (BACKLOG-002/A2-LIVE) — one live session produced three filters absent from six instructional sources.
3. Any source in which the session-hours graphic is read aloud.

<!-- SYNTHETIC TEST DATA / NOT A REAL TJR TRANSCRIPT / NOT VALIDATED TRADING KNOWLEDGE / NOT A PRODUCTION STRATEGY / DO NOT USE FOR TRADING -->

# TJR Research Report: INTAKE|TJR|20260726|001

_Generated 2026-07-26T15:00:00Z. reportSchemaVersion=1._

**No production behavior changed while generating this report.**

## 1. Source Overview
- Title: SYNTHETIC TEST DATA / NOT A REAL TJR TRANSCRIPT / NOT VALIDATED TRADING KNOWLEDGE / NOT A PRODUCTION STRATEGY / DO NOT USE FOR TRADING -- synthetic multi-topic session
- Trader: TJR
- Source type: transcript
- Intake status: extracted

## 2. Provenance
- Canonical reference: None
- Licensing status: owner_authored
- Source provenance status: unverified

## 3. Transcript Quality
- Format: timestamped_text
- Completeness: complete
- Warnings: none

## 4. Extraction Status
- completed

## 5. Segments Analyzed
- Count: 15

## 6. Evidence Extracted
- Count: 14 (from 14 annotations)

## 7. Explicit Statements
- EV|EVSRC|TJR|20260726|001|001: Displacement must always follow a liquidity sweep before I consider an entry valid.
- EV|EVSRC|TJR|20260726|001|002: Displacement must always follow a liquidity sweep before I consider an entry valid.
- EV|EVSRC|TJR|20260726|001|005: On the 15 minute chart, displacement must always follow a liquidity sweep before I consider an entry valid.
- EV|EVSRC|TJR|20260726|001|007: Sometimes I skip the confirmation candle if the displacement is really strong.
- EV|EVSRC|TJR|20260726|001|009: Except when the news just came out, then I ignore the sweep requirement entirely.
- EV|EVSRC|TJR|20260726|001|011: My stop management is honestly discretionary, it depends on the day.
- EV|EVSRC|TJR|20260726|001|014: Risk-wise, I never risk more than one percent per trade.

## 8. Demonstrated Behavior
- EV|EVSRC|TJR|20260726|001|003: Here is a chart example where price swept the high and then displaced down hard, that is the setup.
- EV|EVSRC|TJR|20260726|001|012: This trade worked out well, displacement carried price straight to target.
- EV|EVSRC|TJR|20260726|001|013: This other trade failed because the displacement reversed right after entry.

## 9. Inferred Observations
- EV|EVSRC|TJR|20260726|001|008: I think a confirmation candle is usually a good idea but it is not a hard rule for me.
- EV|EVSRC|TJR|20260726|001|010: Maybe the stop should go above the sweep high, or maybe below the previous structure, I have not fully decided.

## 10. Opinions and Unsupported Statements
- EV|EVSRC|TJR|20260726|001|008: I think a confirmation candle is usually a good idea but it is not a hard rule for me.
- EV|EVSRC|TJR|20260726|001|010: Maybe the stop should go above the sweep high, or maybe below the previous structure, I have not fully decided.

## 11. Claims Generated
- CLAIM|TJR|20260726|001: Displacement occurs after a liquidity sweep.
- CLAIM|TJR|20260726|002: Displacement occurs after a liquidity sweep.
- CLAIM|TJR|20260726|003: A confirmation candle is required before entry.
- CLAIM|TJR|20260726|004: The liquidity-sweep requirement is waived immediately after high-impact news.
- CLAIM|TJR|20260726|006: Stop placement follows a single well-defined rule.
- CLAIM|TJR|20260726|007: Trade management follows a fixed, non-discretionary rule.
- CLAIM|TJR|20260726|008: Displacement-based entries reliably reach target once the setup criteria are met.
- CLAIM|TJR|20260726|009: Risk per trade should not exceed one percent.

## 12. Claim Confidence
- CLAIM|TJR|20260726|001: supported (score=46.77)
- CLAIM|TJR|20260726|002: emerging (score=22.0)
- CLAIM|TJR|20260726|003: contested (score=0.0)
- CLAIM|TJR|20260726|004: emerging (score=22.0)
- CLAIM|TJR|20260726|006: emerging (score=22.0)
- CLAIM|TJR|20260726|007: emerging (score=22.0)
- CLAIM|TJR|20260726|008: contradicted (score=0.0)
- CLAIM|TJR|20260726|009: emerging (score=22.0)

## 13. Contradictions
- XCONTRA|20260726|001: CLAIM|TJR|20260726|003 vs CLAIM|TJR|20260726|004

## 14. Exceptions
- EV|EVSRC|TJR|20260726|001|007: Sometimes I skip the confirmation candle if the displacement is really strong.
- EV|EVSRC|TJR|20260726|001|009: Except when the news just came out, then I ignore the sweep requirement entirely.
- EV|EVSRC|TJR|20260726|001|011: My stop management is honestly discretionary, it depends on the day.

## 15. Unresolved Questions
- [high] Entry rule 'CLAIM|TJR|20260726|001' has no companion invalidation_rule claim in the same scope -- what invalidates this setup?
- [low] Claim 'CLAIM|TJR|20260726|001' looks well-supported by evidence but has no paper-trading validation yet -- has it been tested live without capital risk?
- [low] Claim 'CLAIM|TJR|20260726|001' looks well-supported by evidence but has no replay validation yet -- does it hold up against historical price action?
- [medium] Claim 'CLAIM|TJR|20260726|001' has no session recorded -- does this rule apply in every session or only specific ones?
- [medium] Claim 'CLAIM|TJR|20260726|001' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- [high] Entry rule 'CLAIM|TJR|20260726|002' has no companion invalidation_rule claim in the same scope -- what invalidates this setup?
- [medium] Claim 'CLAIM|TJR|20260726|002' has no session recorded -- does this rule apply in every session or only specific ones?
- [medium] Claim 'CLAIM|TJR|20260726|003' has no session recorded -- does this rule apply in every session or only specific ones?
- [medium] Claim 'CLAIM|TJR|20260726|003' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- [high] Claim 'CLAIM|TJR|20260726|003' has supporting and contradicting evidence from the same source (EVSRC|TJR|20260726|001) -- did this source contradict itself, or state an exception?
- [high] Stop rule 'CLAIM|TJR|20260726|006' has no direct (explicit or demonstrated) supporting evidence -- is stop placement actually well-defined, or discretionary/ambiguous?
- [medium] Claim 'CLAIM|TJR|20260726|006' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- [medium] Evidence for trade-management claim 'CLAIM|TJR|20260726|007' describes discretionary judgment rather than a fixed rule -- should this remain discretionary, or is there a more precise rule underneath it?
- [high] Claim 'CLAIM|TJR|20260726|008' has supporting and contradicting evidence from the same source (EVSRC|TJR|20260726|001) -- did this source contradict itself, or state an exception?

## 16. Rule Candidates
- RCPROP|20260726|001 (claimType=entry_rule, status=proposed)

## 17. Missing Strategy Components
- Claim 'CLAIM|TJR|20260726|001' has no session recorded -- does this rule apply in every session or only specific ones?
- Claim 'CLAIM|TJR|20260726|001' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- Claim 'CLAIM|TJR|20260726|002' has no session recorded -- does this rule apply in every session or only specific ones?
- Claim 'CLAIM|TJR|20260726|003' has no session recorded -- does this rule apply in every session or only specific ones?
- Claim 'CLAIM|TJR|20260726|003' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- Claim 'CLAIM|TJR|20260726|006' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- Entry rule 'CLAIM|TJR|20260726|001' has no companion invalidation_rule claim in the same scope -- what invalidates this setup?
- Entry rule 'CLAIM|TJR|20260726|002' has no companion invalidation_rule claim in the same scope -- what invalidates this setup?
- Stop rule 'CLAIM|TJR|20260726|006' has no direct (explicit or demonstrated) supporting evidence -- is stop placement actually well-defined, or discretionary/ambiguous?

## 18. Replay Hypotheses
_None._

## 19. Paper-Trading Hypotheses
_None._

## 20. What MOGO Learned
- Displacement occurs after a liquidity sweep. (supported, score=46.77)

## 21. What MOGO Still Does Not Know
- Entry rule 'CLAIM|TJR|20260726|001' has no companion invalidation_rule claim in the same scope -- what invalidates this setup?
- Claim 'CLAIM|TJR|20260726|001' looks well-supported by evidence but has no paper-trading validation yet -- has it been tested live without capital risk?
- Claim 'CLAIM|TJR|20260726|001' looks well-supported by evidence but has no replay validation yet -- does it hold up against historical price action?
- Claim 'CLAIM|TJR|20260726|001' has no session recorded -- does this rule apply in every session or only specific ones?
- Claim 'CLAIM|TJR|20260726|001' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- Entry rule 'CLAIM|TJR|20260726|002' has no companion invalidation_rule claim in the same scope -- what invalidates this setup?
- Claim 'CLAIM|TJR|20260726|002' has no session recorded -- does this rule apply in every session or only specific ones?
- Claim 'CLAIM|TJR|20260726|003' has no session recorded -- does this rule apply in every session or only specific ones?
- Claim 'CLAIM|TJR|20260726|003' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- Claim 'CLAIM|TJR|20260726|003' has supporting and contradicting evidence from the same source (EVSRC|TJR|20260726|001) -- did this source contradict itself, or state an exception?
- Stop rule 'CLAIM|TJR|20260726|006' has no direct (explicit or demonstrated) supporting evidence -- is stop placement actually well-defined, or discretionary/ambiguous?
- Claim 'CLAIM|TJR|20260726|006' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- Evidence for trade-management claim 'CLAIM|TJR|20260726|007' describes discretionary judgment rather than a fixed rule -- should this remain discretionary, or is there a more precise rule underneath it?
- Claim 'CLAIM|TJR|20260726|008' has supporting and contradicting evidence from the same source (EVSRC|TJR|20260726|001) -- did this source contradict itself, or state an exception?

## 22. Recommended Next Source
Resolve open items on this intake (see ownerReviewItems) before moving to a new source.

## 23. Owner-Review Items
- [contested_claims] CLAIM|TJR|20260726|003 (confidenceState='contested'.)

## 24. Processing Warnings
_None._

## 25. Production Behavior Changed
False

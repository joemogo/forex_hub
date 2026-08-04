# Knowledge Library Report: TJR

_Generated 2026-07-27T22:26:37Z. reportSchemaVersion=1._

> **This report is research output only. Nothing in it has been validated, is executable, or carries any profitability claim. Every rule-like statement here requires replay validation and paper-trading validation before it could ever be considered for live or paper execution -- and even then, only through the existing StrategyRule promotion pipeline, never automatically from this report.**

## 1. Source Summary
- EVSRC|TJR|20260727|001 (transcript): TJR -- session-based liquidity-sweep strategy walkthrough (YouTube transcript)
- EVSRC|TJR|20260727|002 (transcript): TJR — Day 3 (working title; actual YouTube title unverified)

## 2. Extraction Statistics
- Evidence: 86, Observations: 10, Claims: 69
- Contradictions: 2, Unresolved questions: 14, Hypotheses: 23
- Sources: 2, Extraction status: completed

## 3. Trader Profile
- Canonical name: TJR (traderId=TJR)
- Profile ID: PROFILE|TJR|20260727|001, schemaVersion=1
- Review status: pending

## 4. Draft Strategy Blueprint
- Blueprint ID: BLUEPRINT|TJR|20260727|001, status=DRAFT_RESEARCH_ONLY (research-only, never executable)
- Strategy name: TJR Trading Strategy (Draft)
- Validation status: research=draft, replay=not_available, paperTrading=not_available, production=not_applicable

## 5. Explicit Rules
- [CLAIM|TJR|20260727|001] The strategy is applied to US index instruments, specifically the S&P 500 and NASDAQ. (confidence=emerging)
- [CLAIM|TJR|20260727|002] Trades are always taken around the New York Stock Exchange open. (confidence=emerging)
- [CLAIM|TJR|20260727|003] New York pre-market starts at 8:30. (confidence=emerging)
- [CLAIM|TJR|20260727|004] Trades are taken on the leading index, never on the lagging index. (confidence=emerging)
- [CLAIM|TJR|20260727|005] The leading index is the one closer to the draw on liquidity, or in a bullish SMT the one that makes the higher low. (confidence=emerging)
- [CLAIM|TJR|20260727|006] The strategy is based on liquidity sweeps. (confidence=emerging)
- [CLAIM|TJR|20260727|007] A liquidity sweep is price taking out a prior high or low, which fills orders in the opposite direction. (confidence=emerging)
- [CLAIM|TJR|20260727|008] Step 1 of the setup is to identify a liquidity sweep. (confidence=emerging)
- [CLAIM|TJR|20260727|009] Draws on liquidity are taken from 1-hour highs and lows, 4-hour highs and lows, or session highs and lows. (confidence=emerging)
- [CLAIM|TJR|20260727|010] The first daily preparation step is to mark out the session opens. (confidence=emerging)
- [CLAIM|TJR|20260727|012] Step 2 requires a five-minute confirmation confluence after the liquidity sweep. (confidence=emerging)
- [CLAIM|TJR|20260727|013] The confirmation confluences are break of structure, inverse fair value gap, SMT divergence, and a 79% Fibonacci extension closure. (confidence=emerging)
- [CLAIM|TJR|20260727|014] Only one confirmation confluence is required; all four are not needed. (confidence=emerging)
- [CLAIM|TJR|20260727|015] A break of structure to the downside is price closing underneath the most recent low within the uptrend. (confidence=emerging)
- [CLAIM|TJR|20260727|016] An SMT divergence is when one index makes a higher high and the other a lower high, or one makes a lower low and the other a higher low. (confidence=emerging)
- [CLAIM|TJR|20260727|017] The 79% extension confluence is a candlestick closure beyond the 79% Fibonacci extension measured from the low to the high of the move. (confidence=emerging)
- [CLAIM|TJR|20260727|018] Step 2B: when the liquidity sweep happens during pre-market, a low-timeframe manipulation is required before proceeding. (confidence=emerging)
- [CLAIM|TJR|20260727|019] Step 2B exists because new money entering at the New York open manipulates price again after a pre-market sweep. (confidence=emerging)
- [CLAIM|TJR|20260727|020] Skipping step 2B after a pre-market sweep and entering on the continuation confluence alone would have resulted in the trade being stopped out. (confidence=emerging)
- [CLAIM|TJR|20260727|021] When there is no pre-market sweep, step 2B is skipped and only the confirmation confluences apply. (confidence=emerging)
- [CLAIM|TJR|20260727|022] After the five-minute manipulation the setup remains valid only while price stays in the trend established by the confirmation confluence. (confidence=emerging)
- [CLAIM|TJR|20260727|023] Step 3 requires a five-minute continuation confluence via equilibrium or a fair value gap. (confidence=emerging)
- [CLAIM|TJR|20260727|024] Continuation confluences are limited to equilibrium and fair value gaps. (confidence=emerging)
- [CLAIM|TJR|20260727|025] When step 2B is active, an SMT divergence may be used as the continuation confluence in addition to equilibrium and fair value gap. (confidence=emerging)
- [CLAIM|TJR|20260727|026] After a five-minute manipulation beyond a high or low there is no equilibrium or fair value gap left to trade into, so SMT divergence is the only continuation confluence available. (confidence=emerging)
- [CLAIM|TJR|20260727|027] Step 4 requires a one-minute confirmation confluence before entry. (confidence=emerging)
- [CLAIM|TJR|20260727|028] Stops are placed beyond the swing extreme the entry is taken against -- underneath the low for a long entry, above the highs for a short entry. (confidence=emerging)
- [CLAIM|TJR|20260727|029] Targets are the previous draws on liquidity in the direction of the trade. (confidence=emerging)
- [CLAIM|TJR|20260727|030] Profits are taken in partials across multiple take-profit levels and the remaining position is left to stop out at break even. (confidence=emerging)
- [CLAIM|TJR|20260727|031] When the price action after the confirmation confluence looks unreliable, the step-two-into-step-three sequence is restarted instead of entering. (confidence=emerging)
- [CLAIM|TJR|20260727|032] If the stated continuation confluence is not hit but strong draws on liquidity and a good risk-to-reward remain, the trade is still taken. (confidence=emerging)
- [CLAIM|TJR|20260727|034] The liquidity sweep is expected because new money entering a session manipulates a high or low before moving price in its intended direction. (confidence=emerging)
- [CLAIM|TJR|20260727|035] It is assumed that a new session open more often than not produces a manipulation move before price travels in its intended direction. (confidence=emerging)
- [CLAIM|TJR|20260727|036] It is assumed that market makers sweep highs and lows specifically to fill large positions in the opposite direction. (confidence=emerging)
- [CLAIM|TJR|20260727|037] TJR explicitly disclaims that the strategy carries any fixed high win rate. (confidence=emerging)
- [CLAIM|TJR|20260727|038] Order blocks and breaker blocks were removed from the strategy and have not been used for the last six months. (confidence=emerging)
- [CLAIM|TJR|20260727|039] A custom indicator built by TJR and his team is used to highlight session highs and lows. (confidence=emerging)
- [CLAIM|TJR|20260727|041] TJR stopped trading during the week of the government shutdown. (confidence=emerging)
- [CLAIM|TJR|20260727|042] TJR asserts a six-month trading profit transcribed as $1,47,984 (figure as transcribed; the digit grouping is malformed and the true value is unverified). (confidence=emerging)
- [CLAIM|TJR|20260727|043] TJR asserts a September monthly P&L of $491,000. (confidence=emerging)
- [CLAIM|TJR|20260727|044] TJR asserts an average winning trade of $22,000 against an average losing trade of $11,000 over the six-month period. (confidence=emerging)
- [CLAIM|TJR|20260727|045] The demonstrated short example is described as reaching a risk-to-reward ratio transcribed as 'one two 3.63' before the remainder stopped out at break even (figure as transcribed; ambiguous). (confidence=emerging)
- [CLAIM|TJR|20260727|046] The demonstrated long example is described as reaching a risk-to-reward ratio transcribed as '124.27' (figure as transcribed; ambiguous). (confidence=emerging)
- [CLAIM|TJR|20260727|047] TJR states that his published P&L figures are not exact because broker fees are not subtracted by the reporting dashboard. (confidence=emerging)
- [CLAIM|TJR|20260727|048] TJR identifies as a technical-analysis trader who trades primarily from what the chart and price show. (confidence=emerging)
- [CLAIM|TJR|20260727|049] Day trading as TJR frames it is buying low and selling high, or selling high and buying back low. (confidence=emerging)
- [CLAIM|TJR|20260727|050] TJR defines trading as predicting where price wants to go with high probability on a daily basis. (confidence=emerging)
- [CLAIM|TJR|20260727|051] TradingView is the only charting platform TJR uses for active live charting. (confidence=emerging)
- [CLAIM|TJR|20260727|052] Indicators are never used to take trades; they are used only to mark out confluences. (confidence=emerging)
- [CLAIM|TJR|20260727|053] TJR uses neutral chart colours (blue and black) rather than green and red candles. (confidence=emerging)
- [CLAIM|TJR|20260727|054] Green and red candle colours are asserted to harm trading psychology by associating candles with making and losing money. (confidence=emerging)
- [CLAIM|TJR|20260727|055] Charts must be set to New York (Eastern) time regardless of the trader's physical location. (confidence=emerging)
- [CLAIM|TJR|20260727|056] Charts are set to Eastern time because session opens and closes are defined in the market's own time zone. (confidence=emerging)
- [CLAIM|TJR|20260727|057] The New York Stock Exchange regular session opens at 9:30 a.m. Eastern time. (confidence=emerging)
- [CLAIM|TJR|20260727|059] Japanese candlesticks are preferred because they convey four price points for each period. (confidence=emerging)
- [CLAIM|TJR|20260727|060] The selected chart timeframe determines the period of price action each candlestick represents. (confidence=emerging)
- [CLAIM|TJR|20260727|061] On an up candle the body's bottom is the open and its top is the close; the top of the upper wick is the high and the bottom of the lower wick is the low. (confidence=emerging)
- [CLAIM|TJR|20260727|062] On a down candle the open is the top of the body and the close is the bottom; high and low remain the wick extremes. (confidence=emerging)
- [CLAIM|TJR|20260727|063] A high is a move up followed by a move down; a low is a move down followed by a move up. (confidence=emerging)
- [CLAIM|TJR|20260727|064] A high is identified as an up candle followed by a down candle; a low as a down candle followed by an up candle. (confidence=emerging)
- [CLAIM|TJR|20260727|065] A high is marked at the highest wick of the two candles forming it; a low at the lowest wick of the two forming it. (confidence=emerging)
- [CLAIM|TJR|20260727|066] The market moves in exactly three states: uptrend, downtrend, or consolidation (sideways). (confidence=emerging)
- [CLAIM|TJR|20260727|067] An uptrend is a series of higher highs and higher lows. (confidence=emerging)
- [CLAIM|TJR|20260727|068] A downtrend is a series of lower highs and lower lows. (confidence=emerging)
- [CLAIM|TJR|20260727|069] Trend direction alone is not a trade signal, because trends can break and change. (confidence=emerging)

## 6. Implied or Inferred Rules
- [CLAIM|TJR|20260727|011] A session high or low that has already been swept without producing a reaction is not marked or used as a draw on liquidity. (confidence=emerging)
- [CLAIM|TJR|20260727|033] Entry timing inside the setup is discretionary; TJR describes his own entries as more aggressive than the patient version of the same rules. (confidence=emerging)
- [CLAIM|TJR|20260727|040] The trading day is checked for high-impact news before the setup is applied. (confidence=emerging)
- [CLAIM|TJR|20260727|058] Marking session levels with charts set to a non-Eastern time zone places them at the wrong times and makes the strategy appear not to work. (confidence=emerging)

## 7. Contradictions
- XCONTRA|20260727|001: CLAIM|TJR|20260727|023 vs CLAIM|TJR|20260727|032 (sections: Confirmation, exception)
- XCONTRA|20260727|002: CLAIM|TJR|20260727|024 vs CLAIM|TJR|20260727|025 (sections: Setup Identification, exception)

## 8. Knowledge Gaps
- [higher_timeframe_bias/high] Is a higher-timeframe bias required before taking this setup? -> Trades are taken on the leading index, never on the lagging index. (answer: partially_answered)
- [entry_trigger/critical] What exact condition triggers an entry? -> Step 4 requires a one-minute confirmation confluence before entry. (answer: partially_answered)
- [risk_percentage/critical] What percentage of account equity is risked per trade? -> unanswered (answer: unanswered)
- [spread_handling/low] Does spread affect entry, stop, or target placement? -> unanswered (answer: unanswered)
- [volatility_handling/medium] Does this strategy adjust for high or low volatility conditions? -> unanswered (answer: unanswered)
- [no_trade_conditions/medium] Are there explicit conditions under which no trade should be taken? -> unanswered (answer: unanswered)

## 9. Proposed Hypotheses
- [PROPOSED_UNVALIDATED/emerging] Trades are taken on the leading index, never on the lagging index may be required before a valid entry.
- [PROPOSED_UNVALIDATED/emerging] The strategy is based on liquidity sweeps may be required before a valid entry.
- [PROPOSED_UNVALIDATED/emerging] Step 1 of the setup is to identify a liquidity sweep may be required before a valid entry.
- [PROPOSED_UNVALIDATED/emerging] Draws on liquidity are taken from 1-hour highs and lows, 4-hour highs and lows, or session highs and lows may be required before a valid entry.
- [PROPOSED_UNVALIDATED/emerging] The first daily preparation step is to mark out the session opens may be required before a valid entry.
- [PROPOSED_UNVALIDATED/emerging] A session high or low that has already been swept without producing a reaction is not marked or used as a draw on liquidity may be required before a valid entry.
- [PROPOSED_UNVALIDATED/emerging] Step 2 requires a five-minute confirmation confluence after the liquidity sweep may only be required on the execution timeframe.
- [PROPOSED_UNVALIDATED/emerging] The confirmation confluences are break of structure, inverse fair value gap, SMT divergence, and a 79% Fibonacci extension closure may only be required on the execution timeframe.
- [PROPOSED_UNVALIDATED/emerging] Only one confirmation confluence is required; all four are not needed may only be required on the execution timeframe.
- [PROPOSED_UNVALIDATED/emerging] Step 2B: when the liquidity sweep happens during pre-market, a low-timeframe manipulation is required before proceeding may only be required on the execution timeframe.
- [PROPOSED_UNVALIDATED/emerging] When there is no pre-market sweep, step 2B is skipped and only the confirmation confluences apply may only be required on the execution timeframe.
- [PROPOSED_UNVALIDATED/emerging] After the five-minute manipulation the setup remains valid only while price stays in the trend established by the confirmation confluence may serve as the primary invalidation condition.
- [PROPOSED_UNVALIDATED/emerging] Step 3 requires a five-minute continuation confluence via equilibrium or a fair value gap may only be required on the execution timeframe.
- [PROPOSED_UNVALIDATED/emerging] Step 4 requires a one-minute confirmation confluence before entry may be required before a valid entry.
- [PROPOSED_UNVALIDATED/emerging] Stops are placed beyond the swing extreme the entry is taken against -- underneath the low for a long entry, above the highs for a short entry may be the preferred stop-placement approach, pending further evidence.
- [PROPOSED_UNVALIDATED/emerging] Targets are the previous draws on liquidity in the direction of the trade may be the preferred target-selection approach, pending further evidence.
- [PROPOSED_UNVALIDATED/emerging] Profits are taken in partials across multiple take-profit levels and the remaining position is left to stop out at break even may apply only in certain trade-management contexts.
- [PROPOSED_UNVALIDATED/emerging] The trading day is checked for high-impact news before the setup is applied may be required before a valid entry.
- [PROPOSED_UNVALIDATED/emerging] Charts must be set to New York (Eastern) time regardless of the trader's physical location may be required before a valid entry.
- [PROPOSED_UNVALIDATED/emerging] A high is marked at the highest wick of the two candles forming it; a low at the lowest wick of the two forming it may be required before a valid entry.
- [PROPOSED_UNVALIDATED/contested] Step 3 requires a five-minute continuation confluence via equilibrium or a fair value gap may be preferred rather than mandatory, given conflicting evidence from a contradicting claim (CLAIM|TJR|20260727|032).
- [PROPOSED_UNVALIDATED/contested] Continuation confluences are limited to equilibrium and fair value gaps may be preferred rather than mandatory, given conflicting evidence from a contradicting claim (CLAIM|TJR|20260727|025).
- [PROPOSED_UNVALIDATED/insufficient_evidence] Volatility conditions may materially affect this strategy's setup validity.

## 10. Items Requiring Human Review
- Claim pending review: CLAIM|TJR|20260727|001
- Claim pending review: CLAIM|TJR|20260727|002
- Claim pending review: CLAIM|TJR|20260727|003
- Claim pending review: CLAIM|TJR|20260727|004
- Claim pending review: CLAIM|TJR|20260727|005
- Claim pending review: CLAIM|TJR|20260727|006
- Claim pending review: CLAIM|TJR|20260727|007
- Claim pending review: CLAIM|TJR|20260727|008
- Claim pending review: CLAIM|TJR|20260727|009
- Claim pending review: CLAIM|TJR|20260727|010
- Claim pending review: CLAIM|TJR|20260727|011
- Claim pending review: CLAIM|TJR|20260727|012
- Claim pending review: CLAIM|TJR|20260727|013
- Claim pending review: CLAIM|TJR|20260727|014
- Claim pending review: CLAIM|TJR|20260727|015
- Claim pending review: CLAIM|TJR|20260727|016
- Claim pending review: CLAIM|TJR|20260727|017
- Claim pending review: CLAIM|TJR|20260727|018
- Claim pending review: CLAIM|TJR|20260727|019
- Claim pending review: CLAIM|TJR|20260727|020
- Claim pending review: CLAIM|TJR|20260727|021
- Claim pending review: CLAIM|TJR|20260727|022
- Claim pending review: CLAIM|TJR|20260727|023
- Claim pending review: CLAIM|TJR|20260727|024
- Claim pending review: CLAIM|TJR|20260727|025
- Claim pending review: CLAIM|TJR|20260727|026
- Claim pending review: CLAIM|TJR|20260727|027
- Claim pending review: CLAIM|TJR|20260727|028
- Claim pending review: CLAIM|TJR|20260727|029
- Claim pending review: CLAIM|TJR|20260727|030
- Claim pending review: CLAIM|TJR|20260727|031
- Claim pending review: CLAIM|TJR|20260727|032
- Claim pending review: CLAIM|TJR|20260727|033
- Claim pending review: CLAIM|TJR|20260727|034
- Claim pending review: CLAIM|TJR|20260727|035
- Claim pending review: CLAIM|TJR|20260727|036
- Claim pending review: CLAIM|TJR|20260727|037
- Claim pending review: CLAIM|TJR|20260727|038
- Claim pending review: CLAIM|TJR|20260727|039
- Claim pending review: CLAIM|TJR|20260727|040
- Claim pending review: CLAIM|TJR|20260727|041
- Claim pending review: CLAIM|TJR|20260727|042
- Claim pending review: CLAIM|TJR|20260727|043
- Claim pending review: CLAIM|TJR|20260727|044
- Claim pending review: CLAIM|TJR|20260727|045
- Claim pending review: CLAIM|TJR|20260727|046
- Claim pending review: CLAIM|TJR|20260727|047
- Claim pending review: CLAIM|TJR|20260727|048
- Claim pending review: CLAIM|TJR|20260727|049
- Claim pending review: CLAIM|TJR|20260727|050
- Claim pending review: CLAIM|TJR|20260727|051
- Claim pending review: CLAIM|TJR|20260727|052
- Claim pending review: CLAIM|TJR|20260727|053
- Claim pending review: CLAIM|TJR|20260727|054
- Claim pending review: CLAIM|TJR|20260727|055
- Claim pending review: CLAIM|TJR|20260727|056
- Claim pending review: CLAIM|TJR|20260727|057
- Claim pending review: CLAIM|TJR|20260727|058
- Claim pending review: CLAIM|TJR|20260727|059
- Claim pending review: CLAIM|TJR|20260727|060
- Claim pending review: CLAIM|TJR|20260727|061
- Claim pending review: CLAIM|TJR|20260727|062
- Claim pending review: CLAIM|TJR|20260727|063
- Claim pending review: CLAIM|TJR|20260727|064
- Claim pending review: CLAIM|TJR|20260727|065
- Claim pending review: CLAIM|TJR|20260727|066
- Claim pending review: CLAIM|TJR|20260727|067
- Claim pending review: CLAIM|TJR|20260727|068
- Claim pending review: CLAIM|TJR|20260727|069
- Open question [high]: Stop placement is only ever given chart-relatively ('underneath this low', 'above these highs'). Which exact swing does the stop reference, and is any buffer applied?
- Open question [high]: The worked examples use four take-profit levels (TP1-TP4) but the transcript never defines how those four levels are chosen or sized. How is the take-profit ladder constructed?
- Open question [high]: The intake filename describes a 'forex session strategy', but the transcript states the instruments are US indexes (S&P 500 and NASDAQ) and no forex pair is mentioned anywhere. Is this transcript mis-filed, or is the strategy intended to be transferred to FX?
- Open question [low]: The six-month profit figure is transcribed as '$1,47,984', which is not a valid US digit grouping. What is the actual figure?
- Open question [low]: The two risk-to-reward figures are transcribed as 'one two 3.63' and '124.27'. What are the actual ratios?
- Open question [medium]: TJR checks for high-impact news before applying the setup, but never states what he does when high-impact news IS present. Does news block the trade, delay it, or only change sizing?
- Open question [medium]: At the long entry TJR refers to price needing 'One extra point down to hit our special little number that we wanted'. What is that number, and is it part of the entry rule?
- Open question [medium]: TJR states that step ordering 'can be variable' when 2B activates. What is the exact ordering of steps 2B, 3 and 4 when 2B is active?
- Open question [medium]: Claim 'CLAIM|TJR|20260727|002' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- Open question [high]: Entry rule 'CLAIM|TJR|20260727|027' has no companion invalidation_rule claim in the same scope -- what invalidates this setup?
- Open question [medium]: Claim 'CLAIM|TJR|20260727|029' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- Open question [medium]: Consolidation is named as one of the three market states but is never defined or given identification criteria, unlike uptrend and downtrend.
- Open question [medium]: The two-candle rule for identifying a high or low has no minimum-size or significance filter. Does every up-then-down candle pair qualify as a high?
- Open question [high]: Trends can break and change, but this source never defines what constitutes a break of trend. How is a trend break identified?

## 11. Replay Recommendations
- Replay historical price action segmented by volatility_handling and compare outcomes.
- Replay historical price action under both interpretations and compare outcomes.
- Replay historical price action with and without this condition and compare outcomes.
- replay test against historical price action

## 12. Paper-Trading Recommendations
- Paper-trade across varying volatility_handling conditions and compare results.
- Paper-trade both interpretations and compare results.
- Paper-trade both variants (with/without this condition) and compare results.

## 13. Limitations
- 14 unresolved question(s) remain open for this trader.
- 2 contradiction(s) remain unresolved for this trader.
- CLAIM|TJR|20260727|033: "And like I said before, I'm a little bit more aggressive. I would like to say that I probably would have entered right here."
- No risk_rule claim found -- risk sizing is unknown.
- One or more claims are still pending_review and have not been confirmed by a human.

## 14. Full Lineage Summary
- Profile sources: EVSRC|TJR|20260727|001, EVSRC|TJR|20260727|002
- Profile claims: CLAIM|TJR|20260727|001, CLAIM|TJR|20260727|002, CLAIM|TJR|20260727|003, CLAIM|TJR|20260727|004, CLAIM|TJR|20260727|005, CLAIM|TJR|20260727|006, CLAIM|TJR|20260727|007, CLAIM|TJR|20260727|008, CLAIM|TJR|20260727|009, CLAIM|TJR|20260727|010, CLAIM|TJR|20260727|011, CLAIM|TJR|20260727|012, CLAIM|TJR|20260727|013, CLAIM|TJR|20260727|014, CLAIM|TJR|20260727|015, CLAIM|TJR|20260727|016, CLAIM|TJR|20260727|017, CLAIM|TJR|20260727|018, CLAIM|TJR|20260727|019, CLAIM|TJR|20260727|020, CLAIM|TJR|20260727|021, CLAIM|TJR|20260727|022, CLAIM|TJR|20260727|023, CLAIM|TJR|20260727|024, CLAIM|TJR|20260727|025, CLAIM|TJR|20260727|026, CLAIM|TJR|20260727|027, CLAIM|TJR|20260727|028, CLAIM|TJR|20260727|029, CLAIM|TJR|20260727|030, CLAIM|TJR|20260727|031, CLAIM|TJR|20260727|032, CLAIM|TJR|20260727|033, CLAIM|TJR|20260727|034, CLAIM|TJR|20260727|035, CLAIM|TJR|20260727|036, CLAIM|TJR|20260727|037, CLAIM|TJR|20260727|038, CLAIM|TJR|20260727|039, CLAIM|TJR|20260727|040, CLAIM|TJR|20260727|041, CLAIM|TJR|20260727|042, CLAIM|TJR|20260727|043, CLAIM|TJR|20260727|044, CLAIM|TJR|20260727|045, CLAIM|TJR|20260727|046, CLAIM|TJR|20260727|047, CLAIM|TJR|20260727|048, CLAIM|TJR|20260727|049, CLAIM|TJR|20260727|050, CLAIM|TJR|20260727|051, CLAIM|TJR|20260727|052, CLAIM|TJR|20260727|053, CLAIM|TJR|20260727|054, CLAIM|TJR|20260727|055, CLAIM|TJR|20260727|056, CLAIM|TJR|20260727|057, CLAIM|TJR|20260727|058, CLAIM|TJR|20260727|059, CLAIM|TJR|20260727|060, CLAIM|TJR|20260727|061, CLAIM|TJR|20260727|062, CLAIM|TJR|20260727|063, CLAIM|TJR|20260727|064, CLAIM|TJR|20260727|065, CLAIM|TJR|20260727|066, CLAIM|TJR|20260727|067, CLAIM|TJR|20260727|068, CLAIM|TJR|20260727|069
- Blueprint sources: EVSRC|TJR|20260727|001, EVSRC|TJR|20260727|002
- Blueprint segments: TSEG|INTAKE|TJR|20260727|001|001, TSEG|INTAKE|TJR|20260727|001|003, TSEG|INTAKE|TJR|20260727|001|004, TSEG|INTAKE|TJR|20260727|001|005, TSEG|INTAKE|TJR|20260727|001|006, TSEG|INTAKE|TJR|20260727|001|008, TSEG|INTAKE|TJR|20260727|001|009, TSEG|INTAKE|TJR|20260727|001|010, TSEG|INTAKE|TJR|20260727|001|011, TSEG|INTAKE|TJR|20260727|001|012, TSEG|INTAKE|TJR|20260727|001|013, TSEG|INTAKE|TJR|20260727|001|014, TSEG|INTAKE|TJR|20260727|001|015, TSEG|INTAKE|TJR|20260727|001|017, TSEG|INTAKE|TJR|20260727|001|018, TSEG|INTAKE|TJR|20260727|001|019, TSEG|INTAKE|TJR|20260727|001|020, TSEG|INTAKE|TJR|20260727|001|021, TSEG|INTAKE|TJR|20260727|001|022, TSEG|INTAKE|TJR|20260727|001|023, TSEG|INTAKE|TJR|20260727|002|001, TSEG|INTAKE|TJR|20260727|002|002, TSEG|INTAKE|TJR|20260727|002|003, TSEG|INTAKE|TJR|20260727|002|004, TSEG|INTAKE|TJR|20260727|002|005, TSEG|INTAKE|TJR|20260727|002|007, TSEG|INTAKE|TJR|20260727|002|008, TSEG|INTAKE|TJR|20260727|002|009, TSEG|INTAKE|TJR|20260727|002|010, TSEG|INTAKE|TJR|20260727|002|013, TSEG|INTAKE|TJR|20260727|002|014, TSEG|INTAKE|TJR|20260727|002|015, TSEG|INTAKE|TJR|20260727|002|016, TSEG|INTAKE|TJR|20260727|002|017, TSEG|INTAKE|TJR|20260727|002|018, TSEG|INTAKE|TJR|20260727|002|019
- Blueprint evidence: EV|EVSRC|TJR|20260727|001|001, EV|EVSRC|TJR|20260727|001|002, EV|EVSRC|TJR|20260727|001|003, EV|EVSRC|TJR|20260727|001|004, EV|EVSRC|TJR|20260727|001|005, EV|EVSRC|TJR|20260727|001|006, EV|EVSRC|TJR|20260727|001|007, EV|EVSRC|TJR|20260727|001|008, EV|EVSRC|TJR|20260727|001|009, EV|EVSRC|TJR|20260727|001|010, EV|EVSRC|TJR|20260727|001|011, EV|EVSRC|TJR|20260727|001|012, EV|EVSRC|TJR|20260727|001|013, EV|EVSRC|TJR|20260727|001|014, EV|EVSRC|TJR|20260727|001|015, EV|EVSRC|TJR|20260727|001|016, EV|EVSRC|TJR|20260727|001|017, EV|EVSRC|TJR|20260727|001|018, EV|EVSRC|TJR|20260727|001|019, EV|EVSRC|TJR|20260727|001|020, EV|EVSRC|TJR|20260727|001|021, EV|EVSRC|TJR|20260727|001|022, EV|EVSRC|TJR|20260727|001|023, EV|EVSRC|TJR|20260727|001|024, EV|EVSRC|TJR|20260727|001|025, EV|EVSRC|TJR|20260727|001|026, EV|EVSRC|TJR|20260727|001|027, EV|EVSRC|TJR|20260727|001|028, EV|EVSRC|TJR|20260727|001|029, EV|EVSRC|TJR|20260727|001|030, EV|EVSRC|TJR|20260727|001|031, EV|EVSRC|TJR|20260727|001|032, EV|EVSRC|TJR|20260727|001|033, EV|EVSRC|TJR|20260727|001|034, EV|EVSRC|TJR|20260727|001|035, EV|EVSRC|TJR|20260727|001|036, EV|EVSRC|TJR|20260727|001|037, EV|EVSRC|TJR|20260727|001|038, EV|EVSRC|TJR|20260727|001|039, EV|EVSRC|TJR|20260727|001|040, EV|EVSRC|TJR|20260727|001|041, EV|EVSRC|TJR|20260727|001|042, EV|EVSRC|TJR|20260727|001|043, EV|EVSRC|TJR|20260727|001|044, EV|EVSRC|TJR|20260727|001|045, EV|EVSRC|TJR|20260727|001|046, EV|EVSRC|TJR|20260727|001|047, EV|EVSRC|TJR|20260727|001|048, EV|EVSRC|TJR|20260727|001|049, EV|EVSRC|TJR|20260727|001|050, EV|EVSRC|TJR|20260727|001|051, EV|EVSRC|TJR|20260727|001|052, EV|EVSRC|TJR|20260727|001|053, EV|EVSRC|TJR|20260727|001|054, EV|EVSRC|TJR|20260727|001|055, EV|EVSRC|TJR|20260727|001|056, EV|EVSRC|TJR|20260727|001|057, EV|EVSRC|TJR|20260727|001|058, EV|EVSRC|TJR|20260727|001|059, EV|EVSRC|TJR|20260727|001|060, EV|EVSRC|TJR|20260727|001|061, EV|EVSRC|TJR|20260727|001|062, EV|EVSRC|TJR|20260727|002|001, EV|EVSRC|TJR|20260727|002|002, EV|EVSRC|TJR|20260727|002|003, EV|EVSRC|TJR|20260727|002|004, EV|EVSRC|TJR|20260727|002|005, EV|EVSRC|TJR|20260727|002|006, EV|EVSRC|TJR|20260727|002|007, EV|EVSRC|TJR|20260727|002|008, EV|EVSRC|TJR|20260727|002|009, EV|EVSRC|TJR|20260727|002|010, EV|EVSRC|TJR|20260727|002|011, EV|EVSRC|TJR|20260727|002|012, EV|EVSRC|TJR|20260727|002|013, EV|EVSRC|TJR|20260727|002|014, EV|EVSRC|TJR|20260727|002|015, EV|EVSRC|TJR|20260727|002|016, EV|EVSRC|TJR|20260727|002|017, EV|EVSRC|TJR|20260727|002|018, EV|EVSRC|TJR|20260727|002|019, EV|EVSRC|TJR|20260727|002|020, EV|EVSRC|TJR|20260727|002|021, EV|EVSRC|TJR|20260727|002|022, EV|EVSRC|TJR|20260727|002|023, EV|EVSRC|TJR|20260727|002|024
- Blueprint claims: CLAIM|TJR|20260727|001, CLAIM|TJR|20260727|002, CLAIM|TJR|20260727|003, CLAIM|TJR|20260727|004, CLAIM|TJR|20260727|005, CLAIM|TJR|20260727|006, CLAIM|TJR|20260727|007, CLAIM|TJR|20260727|008, CLAIM|TJR|20260727|009, CLAIM|TJR|20260727|010, CLAIM|TJR|20260727|011, CLAIM|TJR|20260727|012, CLAIM|TJR|20260727|013, CLAIM|TJR|20260727|014, CLAIM|TJR|20260727|015, CLAIM|TJR|20260727|016, CLAIM|TJR|20260727|017, CLAIM|TJR|20260727|018, CLAIM|TJR|20260727|019, CLAIM|TJR|20260727|020, CLAIM|TJR|20260727|021, CLAIM|TJR|20260727|022, CLAIM|TJR|20260727|023, CLAIM|TJR|20260727|024, CLAIM|TJR|20260727|025, CLAIM|TJR|20260727|026, CLAIM|TJR|20260727|027, CLAIM|TJR|20260727|028, CLAIM|TJR|20260727|029, CLAIM|TJR|20260727|030, CLAIM|TJR|20260727|031, CLAIM|TJR|20260727|032, CLAIM|TJR|20260727|033, CLAIM|TJR|20260727|034, CLAIM|TJR|20260727|035, CLAIM|TJR|20260727|036, CLAIM|TJR|20260727|037, CLAIM|TJR|20260727|038, CLAIM|TJR|20260727|039, CLAIM|TJR|20260727|040, CLAIM|TJR|20260727|041, CLAIM|TJR|20260727|042, CLAIM|TJR|20260727|043, CLAIM|TJR|20260727|044, CLAIM|TJR|20260727|045, CLAIM|TJR|20260727|046, CLAIM|TJR|20260727|047, CLAIM|TJR|20260727|048, CLAIM|TJR|20260727|049, CLAIM|TJR|20260727|050, CLAIM|TJR|20260727|051, CLAIM|TJR|20260727|052, CLAIM|TJR|20260727|053, CLAIM|TJR|20260727|054, CLAIM|TJR|20260727|055, CLAIM|TJR|20260727|056, CLAIM|TJR|20260727|057, CLAIM|TJR|20260727|058, CLAIM|TJR|20260727|059, CLAIM|TJR|20260727|060, CLAIM|TJR|20260727|061, CLAIM|TJR|20260727|062, CLAIM|TJR|20260727|063, CLAIM|TJR|20260727|064, CLAIM|TJR|20260727|065, CLAIM|TJR|20260727|066, CLAIM|TJR|20260727|067, CLAIM|TJR|20260727|068, CLAIM|TJR|20260727|069

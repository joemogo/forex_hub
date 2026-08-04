# Knowledge Dashboard

_Generated 2026-07-29T23:48:47Z by `scripts/trader_intelligence/build_knowledge_dashboard.py`._
_Read-only: regenerate after every ingestion. Never edit by hand — edits are lost._

## At a glance

| | Count |
|---|---|
| Registered sources | **12** |
| Completed ingestions | **12** |
| **Transcripts awaiting work (intake queue)** | **0** |
| Claims | 341 |
| Evidence items | 416 |
| Transcript segments | 197 |
| Open contradictions | 16 |
| Open questions (blocking) | 281 (261) |
| Knowledge gaps | 110 |
| Hypotheses | 641 |
| Draft blueprints | 11 |
| Rule candidates | 0 |
| **StrategyRules promoted** | **0** (none exist; promotion is human-only) |
| Open review-queue entries | 325 |
| Owner decisions on record | 6 |

> ✅ **Intake queue empty.** The ingestion pipeline is idle and awaiting input.
> Drop a transcript in `docs/trader-intelligence/intake/pending/` and run
> `ingest.py <file> --trader X` — see the [Operator Playbook](OPERATOR-PLAYBOOK.md).

## Trader coverage

| Trader | Sources | Claims | External research | MOGO implementation |
|---|---|---|---|---|
| ALEX G | 9 | 226 | `partial` | `operational_implementation` |
| ICT (Inner Circle Trader) | 0 | 0 | `not_started` | `not_implemented` |
| JVM | 0 | 0 | `not_started` | `operational_implementation` |
| Rayner Teo | 1 | 46 | `partial` | `no_implementation` |
| TJR | 2 | 69 | `partial` | `session_zone_engine_only` |

## Confidence distribution

| State | Claims |
|---|---|
| `emerging` | 341 |

**Ceiling:** the largest number of independent sources *supporting* any single claim is **3**; **28 claim(s)** have 2 or more. At ~22 points per independent group against a 45-point `supported` threshold, claims backed by 2+ supporting groups can reach `supported`.

### Claims by type

| Type | Count |
|---|---|
| `definition` | 50 |
| `behavioral_observation` | 41 |
| `setup_requirement` | 40 |
| `entry_rule` | 28 |
| `performance_hypothesis` | 26 |
| `causal_hypothesis` | 25 |
| `failure_condition` | 23 |
| `confirmation_rule` | 21 |
| `risk_rule` | 17 |
| `invalidation_rule` | 13 |
| `exception` | 11 |
| `session_rule` | 10 |
| `stop_rule` | 9 |
| `target_rule` | 8 |
| `timeframe_rule` | 8 |
| `trade_management_rule` | 6 |
| `other` | 3 |
| `marketCondition` | 2 |

## Open contradictions

| ID | Type | Severity | Claims |
|---|---|---|---|
| `XCONTRA|20260727|001` | CONDITIONAL_SCOPE | **material** | `CLAIM|TJR|20260727|023` vs `CLAIM|TJR|20260727|032` |
| `XCONTRA|20260727|002` | DEFINITIONAL | **minor** | `CLAIM|TJR|20260727|024` vs `CLAIM|TJR|20260727|025` |
| `XCONTRA|20260727|003` | DEFINITIONAL | **material** | `CLAIM|ALEX_G|20260727|020` vs `CLAIM|TJR|20260727|065` |
| `XCONTRA|20260728|001` | DIRECTIONAL | **blocking** | `CLAIM|ALEX_G|20260728|025` vs `CLAIM|TJR|20260727|006` |
| `XCONTRA|20260728|002` | DEFINITIONAL | **material** | `CLAIM|ALEX_G|20260728|022` vs `CLAIM|TJR|20260727|036` |
| `XCONTRA|20260728|003` | DIRECTIONAL | **material** | `CLAIM|ALEX_G|20260728|047` vs `CLAIM|ALEX_G|20260728|028` |
| `XCONTRA|20260728|004` | CONDITIONAL_SCOPE | **material** | `CLAIM|ALEX_G|20260728|087` vs `CLAIM|ALEX_G|20260728|082` |
| `XCONTRA|20260728|005` | DIRECTIONAL | **material** | `CLAIM|ALEX_G|20260728|064` vs `CLAIM|ALEX_G|20260728|028` |
| `XCONTRA|20260728|006` | SCOPE_MISMATCH | **material** | `CLAIM|ALEX_G|20260728|089` vs `CLAIM|ALEX_G|20260728|100` |
| `XCONTRA|20260728|007` | TEMPORAL_DRIFT | **minor** | `CLAIM|ALEX_G|20260728|116` vs `CLAIM|ALEX_G|20260728|090` |
| `XCONTRA|20260728|008` | CONDITIONAL_SCOPE | **material** | `CLAIM|ALEX_G|20260728|136` vs `CLAIM|ALEX_G|20260728|068` |
| `XCONTRA|20260728|009` | NUMERIC_THRESHOLD | **minor** | `CLAIM|ALEX_G|20260728|150` vs `CLAIM|ALEX_G|20260728|100` |
| `XCONTRA|20260729|001` | CONDITIONAL_SCOPE | **material** | `CLAIM|RAYNER_TEO|20260729|019` vs `CLAIM|ALEX_G|20260728|008` |
| `XCONTRA|20260729|002` | DEFINITIONAL | **minor** | `CLAIM|RAYNER_TEO|20260729|037` vs `CLAIM|TJR|20260727|036` |
| `XCONTRA|20260729|003` | NUMERIC_THRESHOLD | **minor** | `CLAIM|ALEX_G|20260729|027` vs `CLAIM|ALEX_G|20260728|100` |
| `XCONTRA|20260729|004` | CONDITIONAL_SCOPE | **material** | `CLAIM|ALEX_G|20260729|023` vs `CLAIM|ALEX_G|20260728|145` |

_An open contradiction blocks rule candidacy for every claim it touches._

## Blocking open questions

- **[critical]** No risk-per-trade sizing rule of any kind appears in this transcript. What percentage of account equity (or fixed dollar risk) does TJR risk per trade?
- **[critical]** No stop-loss rule, take-profit rule, position size or risk percentage appears anywhere in this source, though stop-loss and take-profit are named as things a wrong structure read would ruin. What are Alex G's risk and exit rules?
- **[critical]** The 60-75% accuracy claim has no supporting evidence: no sample size, date range, instrument, timeframe, trade log, or definition of what 'accuracy' measures. What verifiable record supports it?
- **[critical]** Lower timeframes are said to inform 'how long can we have on our stop-loss on a takeprofit', but no stop rule, target rule, risk percentage or position sizing appears in either Alex G source. What are the actual rules?
- **[critical]** Alex G says no strategy can trade liquidity sweeps, yet describes his own live AUDCHF position as 'entering a trade technically after the liquidity sweep'. Is the objection to anticipating sweeps only, or to using them at all?
- **[critical]** Three Alex G sources now contain zero stop-loss, take-profit, position-size or risk-percentage rules, despite this source opening with a story about a stop-loss being hit. What are they?
- **[critical]** Does Alex G's method permit entry on an incomplete structure point, or require confirmation first?
- **[critical]** Are the $60,000 and $50,000 single-day results verifiable, and were they produced by this method?
- **[critical]** Where is the stop placed, what is the target, and what is risked per trade?
- **[critical]** Which exact hours are the high-volume windows Alex G will trade?
- **[critical]** Is the ~70% next-day continuation figure measurable, and on what sample?
- **[critical]** Is the daily-income figure $500 or $1000, and on what capital?
- **[critical]** Does Alex G's method permit anticipating a setup, or require a closed candle first?
- **[critical]** Where does the stop go?
- **[critical]** Where is the stop placed? Risk sizing without stop placement cannot produce a position size.
- **[critical]** Is the $50,000-$100,000 per day figure verifiable, and on what account size?
- **[critical]** Is the 100K / 27-28% / $28,000 payout result verifiable?
- **[critical]** What proportion of students reach $1,000-$1,500 per week, and what happens to the rest?
- **[critical]** Where is the stop placed?
- **[critical]** What is the evaluation pass rate, and what happens to the fee when a trader fails?
- **[critical]** Where is the stop placed?
- **[critical]** How far beyond the rejection structure is the stop placed? The rule is stated as invariant ('the same thing every single time your stop-loss is right under it') but no buffer is given in any unit - no pips, no ATR multiple, no percentage, and no statement that it sits flush against the structure. Position size = risk / stop distance, so the sizing rules remain non-computable without this number.
- **[high]** Stop placement is only ever given chart-relatively ('underneath this low', 'above these highs'). Which exact swing does the stop reference, and is any buffer applied?
- **[high]** The worked examples use four take-profit levels (TP1-TP4) but the transcript never defines how those four levels are chosen or sized. How is the take-profit ladder constructed?
- **[high]** The intake filename describes a 'forex session strategy', but the transcript states the instruments are US indexes (S&P 500 and NASDAQ) and no forex pair is mentioned anywhere. Is this transcript mis-filed, or is the strategy intended to be transferred to FX?
- **[high]** Every claim in the TJR Knowledge Library currently derives from this single transcript, so no claim can exceed 'emerging' confidence. What second independent source should be acquired?
- **[high]** Entry rule 'CLAIM|TJR|20260727|027' has no companion invalidation_rule claim in the same scope -- what invalidates this setup?
- **[high]** Canonical URL supplied 2026-07-27: https://www.youtube.com/watch?v=8qwEmE1DwYw . REMAINING: the video's actual YouTube title is still unverified — the current title is a working title derived from transcript content. What is the published title?
- **[high]** Trends can break and change, but this source never defines what constitutes a break of trend. How is a trend break identified?
- **[high]** Top-down analysis produces an 'overall score' across timeframes, but no scoring method, weighting or threshold is given. How is the score computed and what value constitutes alignment?
- **[high]** An area of interest needs 'a decent amount of rejections'. How many rejections, and what counts as a rejection?
- **[high]** The 'snake trick' locates a structure point at 'a sharp turn'. What quantitatively counts as a turn? No pivot strength, minimum swing size, lookback window or bar count is given, so the procedure is discretionary rather than algorithmic.
- **[high]** Any body close beyond a structure level counts as a shift regardless of size. How are false breaks, noise and immediate reversals handled? No minimum displacement, ATR filter or confirmation-bar requirement is stated.
- **[high]** 'Trading at the right times' is named as one of the four requirements for profitability but is never defined anywhere in either Alex G source. What are the right times?
- **[high]** 'Retail traders only make up 3% of the market' is offered as the load-bearing premise for rejecting the institutional-sweep narrative. What is the source of the 3% figure, and 3% of what — volume, participants, notional?
- **[high]** A confirmation is 'a bearish candlestick confirming that it's going in that direction', with engulfing, morning star and pin bar named. Is any candle in the intended direction sufficient, or only these named patterns? Must it close inside the zone?
- **[high]** What is the maximum of the timeframe-confluence scale, and is 20 a passing threshold or just the score of this example?
- **[high]** Which two timeframes must be in sync, and does an opposing intermediate timeframe reduce the grade?
- **[high]** Which sessions are 'the proper session' for entry?
- **[high]** What is the cost of waiting for the session, measured rather than asserted?
- **[high]** Is 80-100 pips a target-selection rule, or a description of past averages?
- **[high]** Must the engulfing candle's body engulf the prior body, or the prior candle's full range?
- **[high]** On which timeframe is the trend that the confirmation must agree with?
- **[high]** Do the 1:2 / 1:3 ratios here and the 80-100 pip target from source #5 jointly imply a stop distance?
- **[high]** Is 8-10% per month sustainable, and at what drawdown?
- **[high]** Are November-March materially better than June-August for this method?
- **[high]** How close must price come to a level for the setup to count?
- **[high]** Which EMA period is used, and on which timeframe?
- **[high]** What is on the written confluence list, and how many confluences are required?
- **[high]** Is the take-profit ever moved for a market reason, and if so on what signal?
- **[high]** Which monthly return figure is the claim - 7-10%, 8-10%, or 7/12/15%?
- **[high]** Does the ATR-buffer stop rule generalise beyond this educator's setups?
- **[high]** What makes a swing point 'major' enough to count?
- **[high]** What exactly is 'it' / 'this point'? Three readings are each consistent with the words and the chart narration: (a) the low of the final rejection/engulfing candle, (b) the low of the whole Morning Star formation, (c) the far boundary of the retested zone. The three give materially different stop distances on the same setup.
- **[high]** 1:2 is stated as a MINIMUM. How is the actual target chosen when structure would allow more? Existing ALEX_G sources record 1:3 and 1:4 as observations and an 80-100 pip personal average, none as a selection procedure.
- **[high]** Zone width is stated to be unconstrained ('doesn't matter the size of the box') subject to leaving 'enough room' for 'multiple Taps'. How much room, and how many touches? The same source quantifies a different requirement precisely ('a minimum of one structure point'), so the omission here is unlikely to be an oversight.
- **[medium]** TJR checks for high-impact news before applying the setup, but never states what he does when high-impact news IS present. Does news block the trade, delay it, or only change sizing?
- **[medium]** At the long entry TJR refers to price needing 'One extra point down to hit our special little number that we wanted'. What is that number, and is it part of the entry rule?
- **[medium]** TJR states that step ordering 'can be variable' when 2B activates. What is the exact ordering of steps 2B, 3 and 4 when 2B is active?
- **[medium]** No no-trade condition is stated anywhere. TJR stopped trading during the government shutdown week but gave no rule. Under what conditions should the strategy not be traded at all?
- **[medium]** Claim 'CLAIM|TJR|20260727|002' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|TJR|20260727|029' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Consolidation is named as one of the three market states but is never defined or given identification criteria, unlike uptrend and downtrend.
- **[medium]** The two-candle rule for identifying a high or low has no minimum-size or significance filter. Does every up-then-down candle pair qualify as a high?
- **[medium]** The stated procedure runs weekly through 15-minute, but in practice the directional pass stops after the 4-hour. Are the 2h/1h/30m/15m timeframes part of the directional score or not?
- **[medium]** 'Multiple dojis' is given as an entry signal. How many dojis, and must they be consecutive?
- **[medium]** Claim 'CLAIM|ALEX_G|20260727|005' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260727|006' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260727|007' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260727|007' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260727|017' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260727|018' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260727|018' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260727|022' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260727|026' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260727|026' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260727|028' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260727|028' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260727|029' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260727|029' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260727|030' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260727|030' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260727|031' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260727|031' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260727|032' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260727|032' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260727|034' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260727|034' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** A retracement is preferred over chasing an extreme, but no retracement depth, measurement method or invalidation point is given. How far back must price come, and what invalidates the wait?
- **[medium]** Structure is said to exist inside any range, however tight. At what point does a range become too small for structure to be meaningful, given that no minimum displacement applies?
- **[medium]** Claim 'CLAIM|ALEX_G|20260727|022' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|007' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|011' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|011' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** 'More than three taps is the most ideal' — what counts as a tap? Must price close in the zone, wick into it, or merely approach it? Over what lookback?
- **[medium]** Claim 'CLAIM|ALEX_G|20260727|029' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260727|029' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260727|031' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260727|031' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|011' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|011' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|021' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|021' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|028' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|028' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|029' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|030' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|030' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|032' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|032' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Which EMA period is used on the four-hour chart?
- **[medium]** Does 'break out of this box' require a body close, or does a wick through it suffice?
- **[medium]** How many touches qualify a level, and how is 'most touches' ranked when candidates tie?
- **[medium]** Which timeframe's lower high and lower low bound the box?
- **[medium]** Claim 'CLAIM|ALEX_G|20260727|026' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260727|026' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260727|028' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260727|028' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260727|029' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260727|029' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|011' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|011' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|037' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|037' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|038' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|041' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|043' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|043' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|044' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|044' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|046' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|046' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|048' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|049' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|049' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|050' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|050' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|053' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|053' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** How many dojis constitute 'more powerful', and does the count change the decision?
- **[medium]** At what values do the five named inputs change the decision?
- **[medium]** Is the 4-hour cross-reference required on every setup, or only when a daily wick is ambiguous?
- **[medium]** What counts as a 'shorter' take-profit, a 'very strong' confirmation, or 'a lot of' momentum?
- **[medium]** Claim 'CLAIM|ALEX_G|20260727|032' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260727|032' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|028' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|028' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|030' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|030' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|056' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|056' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|058' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|058' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|063' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|063' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|068' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|068' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|069' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|070' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|070' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|074' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|074' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|075' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|078' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|078' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|079' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|079' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|080' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|080' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|081' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|081' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|083' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|083' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|084' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Which funded-account rules constrain the risk percentage, and at what thresholds?
- **[medium]** Is the fixed percentage per trade, per month, or per market season?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|110' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|113' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|117' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|117' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Does meeting a monthly objective reduce or stop trading, and at what figure?
- **[medium]** What makes a trade 'worth the risk', in terms that could be evaluated?
- **[medium]** Is there a minimum risk-to-reward, given 1:2, 1:3 and now 1:4 have all been cited?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|046' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|046' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|049' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|049' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|068' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|068' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|074' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|074' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|125' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|125' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|126' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|126' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|128' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|128' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|136' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260728|140' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Does the 30/30/30/10 rule apply to trading profits, to all income, or to both?
- **[medium]** Is 1% a hard limit or a starting guideline?
- **[medium]** How far before the swing high should the target sit?
- **[medium]** Which moving average period, and on which timeframe?
- **[medium]** If structure classification is subjective, what is being replayed when MOGO tests it?
- **[medium]** Claim 'CLAIM|RAYNER_TEO|20260729|001' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|RAYNER_TEO|20260729|001' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|RAYNER_TEO|20260729|002' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|RAYNER_TEO|20260729|002' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|RAYNER_TEO|20260729|009' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|RAYNER_TEO|20260729|010' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|RAYNER_TEO|20260729|011' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|RAYNER_TEO|20260729|011' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|RAYNER_TEO|20260729|013' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|RAYNER_TEO|20260729|018' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|RAYNER_TEO|20260729|018' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|RAYNER_TEO|20260729|022' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|RAYNER_TEO|20260729|023' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|RAYNER_TEO|20260729|023' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|RAYNER_TEO|20260729|027' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|RAYNER_TEO|20260729|027' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|RAYNER_TEO|20260729|028' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|RAYNER_TEO|20260729|028' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|RAYNER_TEO|20260729|030' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|RAYNER_TEO|20260729|030' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|RAYNER_TEO|20260729|031' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|RAYNER_TEO|20260729|031' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|RAYNER_TEO|20260729|035' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|RAYNER_TEO|20260729|036' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|RAYNER_TEO|20260729|037' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|RAYNER_TEO|20260729|039' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|RAYNER_TEO|20260729|040' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|RAYNER_TEO|20260729|040' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|RAYNER_TEO|20260729|041' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|RAYNER_TEO|20260729|042' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|RAYNER_TEO|20260729|045' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Is the short-side mirror ever stated? All three demonstrations are longs and the phrasing is always 'right under'. The symmetric 'right above' for a short is never spoken or shown in this source.
- **[medium]** Is the confirmation specifically a bullish engulfing candle, or any rejection formation? The requirement is stated as 'a bullish engulfing Candlestick confirmation', but the demonstrations show a Morning Star (three doji plus one engulfing) and the narration also accepts 'rejection candlesticks' generally.
- **[medium]** What counts as a 'structure point' for the minimum-of-one test - any candle body close beyond the level, or a swing high/low meeting some significance test? This source does not define it.
- **[medium]** Claim 'CLAIM|ALEX_G|20260729|008' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260729|009' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260729|013' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260729|015' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260729|016' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260729|017' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260729|017' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260729|018' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260729|018' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260729|019' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260729|019' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260729|020' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260729|020' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260729|021' has no session recorded -- does this rule apply in every session or only specific ones?
- **[medium]** Claim 'CLAIM|ALEX_G|20260729|021' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260729|022' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260729|023' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[medium]** Claim 'CLAIM|ALEX_G|20260729|025' has no timeframe recorded -- does this rule apply on a specific timeframe, or all of them?
- **[low]** Claim 'CLAIM|ALEX_G|20260727|016' looks well-supported by evidence but has no paper-trading validation yet -- has it been tested live without capital risk?
- **[low]** Claim 'CLAIM|ALEX_G|20260727|016' looks well-supported by evidence but has no replay validation yet -- does it hold up against historical price action?
- **[low]** Claim 'CLAIM|ALEX_G|20260727|020' looks well-supported by evidence but has no paper-trading validation yet -- has it been tested live without capital risk?
- **[low]** Claim 'CLAIM|ALEX_G|20260727|020' looks well-supported by evidence but has no replay validation yet -- does it hold up against historical price action?
- **[low]** What percentage bands define the B / B+ setup grades?

## Knowledge gaps

| Category | Priority | Answer status |
|---|---|---|
| `entry_trigger` | **critical** | partially_answered |
| `entry_trigger` | **critical** | partially_answered |
| `entry_trigger` | **critical** | partially_answered |
| `entry_trigger` | **critical** | partially_answered |
| `entry_trigger` | **critical** | partially_answered |
| `entry_trigger` | **critical** | partially_answered |
| `entry_trigger` | **critical** | partially_answered |
| `entry_trigger` | **critical** | partially_answered |
| `entry_trigger` | **critical** | partially_answered |
| `entry_trigger` | **critical** | partially_answered |
| `entry_trigger` | **critical** | partially_answered |
| `execution_timeframe` | **critical** | partially_answered |
| `execution_timeframe` | **critical** | partially_answered |
| `execution_timeframe` | **critical** | partially_answered |
| `execution_timeframe` | **critical** | partially_answered |
| `execution_timeframe` | **critical** | partially_answered |
| `execution_timeframe` | **critical** | partially_answered |
| `execution_timeframe` | **critical** | partially_answered |
| `execution_timeframe` | **critical** | partially_answered |
| `execution_timeframe` | **critical** | partially_answered |
| `execution_timeframe` | **critical** | partially_answered |
| `risk_percentage` | **critical** | unanswered |
| `risk_percentage` | **critical** | unanswered |
| `risk_percentage` | **critical** | unanswered |
| `risk_percentage` | **critical** | unanswered |
| `risk_percentage` | **critical** | unanswered |
| `risk_percentage` | **critical** | unanswered |
| `stop_placement` | **critical** | unanswered |
| `stop_placement` | **critical** | unanswered |
| `stop_placement` | **critical** | unanswered |
| `stop_placement` | **critical** | unanswered |
| `stop_placement` | **critical** | unanswered |
| `stop_placement` | **critical** | unanswered |
| `stop_placement` | **critical** | unanswered |
| `stop_placement` | **critical** | unanswered |
| `higher_timeframe_bias` | **high** | partially_answered |
| `higher_timeframe_bias` | **high** | partially_answered |
| `higher_timeframe_bias` | **high** | partially_answered |
| `higher_timeframe_bias` | **high** | partially_answered |
| `higher_timeframe_bias` | **high** | partially_answered |
| `higher_timeframe_bias` | **high** | partially_answered |
| `higher_timeframe_bias` | **high** | partially_answered |
| `higher_timeframe_bias` | **high** | partially_answered |
| `higher_timeframe_bias` | **high** | partially_answered |
| `higher_timeframe_bias` | **high** | partially_answered |
| `higher_timeframe_bias` | **high** | partially_answered |
| `instrument` | **high** | unanswered |
| `instrument` | **high** | unanswered |
| `instrument` | **high** | unanswered |
| `instrument` | **high** | unanswered |
| `instrument` | **high** | unanswered |
| `instrument` | **high** | unanswered |
| `instrument` | **high** | unanswered |
| `instrument` | **high** | unanswered |
| `instrument` | **high** | unanswered |
| `instrument` | **high** | unanswered |
| `target_selection` | **high** | unanswered |
| `target_selection` | **high** | unanswered |
| `target_selection` | **high** | unanswered |
| `target_selection` | **high** | unanswered |
| `exception_handling` | **medium** | unanswered |
| `news_handling` | **medium** | unanswered |
| `news_handling` | **medium** | unanswered |
| `news_handling` | **medium** | unanswered |
| `news_handling` | **medium** | unanswered |
| `news_handling` | **medium** | unanswered |
| `news_handling` | **medium** | unanswered |
| `news_handling` | **medium** | unanswered |
| `news_handling` | **medium** | unanswered |
| `news_handling` | **medium** | unanswered |
| `news_handling` | **medium** | unanswered |
| `no_trade_conditions` | **medium** | unanswered |
| `no_trade_conditions` | **medium** | unanswered |
| `no_trade_conditions` | **medium** | unanswered |
| `no_trade_conditions` | **medium** | unanswered |
| `no_trade_conditions` | **medium** | unanswered |
| `session` | **medium** | unanswered |
| `session` | **medium** | unanswered |
| `session` | **medium** | unanswered |
| `session` | **medium** | unanswered |
| `session` | **medium** | unanswered |
| `session` | **medium** | unanswered |
| `session` | **medium** | unanswered |
| `session` | **medium** | unanswered |
| `session` | **medium** | unanswered |
| `session` | **medium** | unanswered |
| `trade_management` | **medium** | unanswered |
| `trade_management` | **medium** | unanswered |
| `trade_management` | **medium** | unanswered |
| `trade_management` | **medium** | unanswered |
| `volatility_handling` | **medium** | unanswered |
| `volatility_handling` | **medium** | unanswered |
| `volatility_handling` | **medium** | unanswered |
| `volatility_handling` | **medium** | unanswered |
| `volatility_handling` | **medium** | unanswered |
| `volatility_handling` | **medium** | unanswered |
| `volatility_handling` | **medium** | unanswered |
| `volatility_handling` | **medium** | unanswered |
| `volatility_handling` | **medium** | unanswered |
| `volatility_handling` | **medium** | unanswered |
| `spread_handling` | **low** | unanswered |
| `spread_handling` | **low** | unanswered |
| `spread_handling` | **low** | unanswered |
| `spread_handling` | **low** | unanswered |
| `spread_handling` | **low** | unanswered |
| `spread_handling` | **low** | unanswered |
| `spread_handling` | **low** | unanswered |
| `spread_handling` | **low** | unanswered |
| `spread_handling` | **low** | unanswered |
| `spread_handling` | **low** | unanswered |

## Knowledge Graph

Build `BUILD|20260729|003` — **2422 nodes, 5109 edges**.

| Node type | Count |
|---|---|
| `HYPOTHESIS` | 641 |
| `EVIDENCE_ITEM` | 416 |
| `CLAIM` | 341 |
| `REVIEW_QUEUE_ENTRY` | 325 |
| `EVIDENCE_QUESTION` | 281 |
| `TRANSCRIPT_SEGMENT` | 197 |
| `KNOWLEDGE_GAP` | 110 |
| `UNRESOLVED_QUESTION` | 35 |
| `CONTRADICTION_RECORD` | 16 |
| `EVIDENCE_SOURCE` | 12 |
| `INTAKE_MANIFEST` | 12 |
| `STRATEGY_BLUEPRINT` | 11 |
| `TRADER_PROFILE` | 11 |
| `OWNER_DECISION` | 6 |
| `TRADER` | 5 |
| `STRATEGY_FAMILY` | 3 |

## Integrity

| Report | FATAL | ERROR | WARNING | INFO |
|---|---|---|---|---|
| Evidence | 0 | 0 | 0 | 0 |
| Graph | 0 | 0 | 0 | 0 |

## Governance

| Decision | Type | Scope | Replay | Status |
|---|---|---|---|---|
| `DECISION|MOGO|20260725|001` | architectural | architectural | ❌ | active |
| `DECISION|MOGO|20260725|002` | acquisition | acquisition | ❌ | active |
| `DECISION|MOGO|20260727|003` | research | research_only | ❌ | active |
| `DECISION|MOGO|20260727|004` | architectural | architectural | ❌ | active |
| `DECISION|MOGO|20260727|005` | acquisition | acquisition | ❌ | active |
| `DECISION|MOGO|20260727|006` | research | research_only | ❌ | active |

**Standing constraints:** no claim promotes on a single source · contradictions are recorded, not resolved · confidence rises only via independent corroboration, replay, paper trading, or historical testing · all educators hold equal evidentiary standing · third-party material is internal-research only and must never be redistributed.

## Review cadence

Completed ingestions: **12**. Next Trader Intelligence Review due at **20** (8 more to go). See [`TRADER-INTELLIGENCE-REVIEW.md`](TRADER-INTELLIGENCE-REVIEW.md).


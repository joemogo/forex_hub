# Normalized Rule Library (DRAFT)

**MOGO-002.6 Phase 6** · **111 normalized rules** · every one at `NEEDS_REVIEW` / `NORMALIZED`.

⚠️ **No rule here is approved, implemented, replay-validated or paper-validated.** OD-1 modification 6 caps this milestone at `NEEDS_REVIEW`, enforced as a hard model error.

**41 of 111 are deterministic.** **66 carry an unresolved parameter the source never states** — preserved, never filled in.

## TIMEFRAMES — 3 rules

| Rule | Class | Req | Det | Unresolved | Statement |
|---|---|---|---|---|---|
| `KERULE|ALEX_G|003` | UNRESOLVED | Y | n | 1 blocking open question(s) | Top-down analysis uses four timeframe tiers: weekly, daily, 4-hour, and the lower timeframes. |
| `KERULE|ALEX_G|004` | UNRESOLVED | Y | n | 1 blocking open question(s) | The lower timeframes are 2-hour, 1-hour, 30-minute and 15-minute; anything below 15-minute is no |
| `KERULE|ALEX_G|057` | UNRESOLVED | Y | n | 1 blocking open question(s) | The entry-side structure point must be present on the four-hour timeframe. |

## LIQUIDITY — 2 rules

| Rule | Class | Req | Det | Unresolved | Statement |
|---|---|---|---|---|---|
| `KERULE|ALEX_G|038` | UNRESOLVED | n | n | 1 blocking open question(s) | No consistent strategy can be built on trading liquidity sweeps themselves. |
| `KERULE|ALEX_G|039` | EXPLICIT | n | Y | — | A liquidity sweep cannot be anticipated in advance; catching or avoiding one is luck, not method |

## SETUP — 21 rules

| Rule | Class | Req | Det | Unresolved | Statement |
|---|---|---|---|---|---|
| `KERULE|ALEX_G|001` | EXPLICIT | Y | Y | — | Top-down analysis is required before any trade, regardless of trading style. |
| `KERULE|ALEX_G|006` | EXPLICIT | Y | Y | — | Top-down analysis proceeds from the weekly timeframe downward through daily, 4-hour and the lowe |
| `KERULE|ALEX_G|007` | UNRESOLVED | Y | n | 1 blocking open question(s) | Each timeframe is classified bullish or bearish and the results are combined into an overall sco |
| `KERULE|ALEX_G|009` | UNRESOLVED | Y | n | 2 blocking open question(s) | Every time a new higher high forms, the higher low must be re-anchored to the preceding structur |
| `KERULE|ALEX_G|015` | EXPLICIT | Y | Y | — | The higher high always leads a bullish structure and the lower low always leads a bearish struct |
| `KERULE|ALEX_G|017` | EXPLICIT | Y | Y | — | An aligned higher-timeframe trend is not itself an entry trigger; a specific area must still be  |
| `KERULE|ALEX_G|027` | EXPLICIT | Y | Y | — | Every new lower low forces reassignment of the active lower high to the most recent turn. |
| `KERULE|ALEX_G|030` | UNRESOLVED | Y | n | 1 blocking open question(s) | The active higher low is located by tracing back from the leading high until price makes a sharp |
| `KERULE|ALEX_G|031` | EXPLICIT | Y | Y | — | The line chart is used as a visual aid to locate body-based structure points before returning to |
| `KERULE|ALEX_G|033` | UNRESOLVED | Y | n | 1 blocking open question(s) | Market structure alone is not a complete trading system; top-down analysis, an entry signal and  |
| `KERULE|ALEX_G|034` | EXPLICIT | Y | Y | — | Liquidity concentrates where price has repeatedly been rejected from the same area. |
| `KERULE|ALEX_G|035` | EXPLICIT | Y | Y | — | Higher-timeframe rejection zones are stronger and attract more liquidation than lower-timeframe  |
| `KERULE|ALEX_G|036` | EXPLICIT | Y | Y | — | A zone with only one prior rejection is materially less predictable than one with several. |
| `KERULE|ALEX_G|044` | UNRESOLVED | Y | n | 1 blocking open question(s) | No trade is taken unless at least two analysed timeframes agree on direction. Stated as an absol |
| `KERULE|ALEX_G|048` | UNRESOLVED | Y | n | 1 blocking open question(s) | Timeframe agreement is scored numerically at 10 points per aligned timeframe, and the worked exa |
| `KERULE|ALEX_G|049` | EXPLICIT | Y | Y | — | The region between the active lower high and lower low is drawn as an explicit box, and the sear |
| `KERULE|ALEX_G|063` | EXPLICIT | Y | Y | — | No trade is entered without either a rejection/doji or an engulfing candle, regardless of trade  |
| `KERULE|ALEX_G|064` | UNRESOLVED | Y | n | 1 blocking open question(s) | A daily candle that looks like a rejection must be cross-referenced against the 4-hour within th |
| `KERULE|ALEX_G|101` | EXPLICIT | Y | Y | — | Correlated pairs are compared and the one presenting the cleaner structure is preferred. NZDUSD  |
| `KERULE|ALEX_G|106` | UNRESOLVED | Y | n | 1 blocking open question(s) | Trades are taken only when judged worth the capital risked. Selectivity is presented as a gate i |
| `KERULE|ALEX_G|107` | EXPLICIT | Y | Y | — | Direction is chosen by counting the confluences available for each side and taking the side with |

## ENTRY — 27 rules

| Rule | Class | Req | Det | Unresolved | Statement |
|---|---|---|---|---|---|
| `KERULE|ALEX_G|005` | UNRESOLVED | Y | n | 2 blocking open question(s) | When lower and higher timeframes disagree, the higher timeframe takes precedence. |
| `KERULE|ALEX_G|011` | UNRESOLVED | Y | n | 2 blocking open question(s) | A break above the lower high shifts the market from bearish back to bullish. |
| `KERULE|ALEX_G|018` | UNRESOLVED | Y | n | 5 blocking open question(s) | The area of interest must lie inside the current higher high and higher low, never outside that  |
| `KERULE|ALEX_G|020` | UNRESOLVED | Y | n | 4 blocking open question(s) | Areas of interest are drawn only on the weekly and daily timeframes. |
| `KERULE|ALEX_G|021` | UNRESOLVED | Y | n | 9 blocking open question(s) | An area of interest is identified by a decent number of prior rejections or touches. |
| `KERULE|ALEX_G|022` | UNRESOLVED | Y | n | 2 blocking open question(s) | Where the weekly and daily areas of interest overlap, the resulting zone is treated as stronger. |
| `KERULE|ALEX_G|023` | UNRESOLVED | Y | n | 5 blocking open question(s) | The entry signal is a rejection candlestick at the area of interest: multiple dojis or an engulf |
| `KERULE|ALEX_G|024` | UNRESOLVED | Y | n | 4 blocking open question(s) | The entry signal may occur on any timeframe; a higher-timeframe signal is treated as stronger. |
| `KERULE|ALEX_G|025` | UNRESOLVED | Y | n | 2 blocking open question(s) | Buy when price is above support; sell when price is below resistance. |
| `KERULE|ALEX_G|032` | UNRESOLVED | Y | n | 7 blocking open question(s) | At a newly formed extreme the choice is to chase or to wait for a retracement; waiting is presen |
| `KERULE|ALEX_G|037` | UNRESOLVED | Y | n | 2 blocking open question(s) | Trade in the direction the zone has historically pushed price: buy while above it, sell while be |
| `KERULE|ALEX_G|042` | UNRESOLVED | Y | n | 4 blocking open question(s) | Named confirmation patterns demonstrated at the zone: bullish engulfing candle, morning star, bu |
| `KERULE|ALEX_G|043` | UNRESOLVED | Y | n | 2 blocking open question(s) | Entry is taken after price retraces to a discount, where prior participants liquidate and the zo |
| `KERULE|ALEX_G|046` | UNRESOLVED | Y | n | 2 blocking open question(s) | An inverted head and shoulders is used as a corroborating signal that structure has shifted from |
| `KERULE|ALEX_G|052` | UNRESOLVED | Y | n | 2 blocking open question(s) | The selected area of interest in the worked example sits at a round psychological number, offere |
| `KERULE|ALEX_G|053` | UNRESOLVED | Y | n | 2 blocking open question(s) | A candidate level is validated by looking left on the chart to confirm it has been respected his |
| `KERULE|ALEX_G|055` | UNRESOLVED | Y | n | 4 blocking open question(s) | Entry location is fixed by structure: sells are taken at a lower high and buys at a higher low. |
| `KERULE|ALEX_G|058` | UNRESOLVED | Y | n | 4 blocking open question(s) | If the first approach to the area of interest produces no lower high, no trade is taken; the req |
| `KERULE|ALEX_G|059` | UNRESOLVED | Y | n | 3 blocking open question(s) | Additional confluences named at the entry: a retest of the level, the weekly area of interest, a |
| `KERULE|ALEX_G|061` | UNRESOLVED | Y | n | 2 blocking open question(s) | A candlestick is a confirmation only once it has closed. Before close it counts as anticipation, |
| `KERULE|ALEX_G|062` | UNRESOLVED | Y | n | 3 blocking open question(s) | A rejection and an engulfing together are treated as a stronger confirmation than either alone,  |
| `KERULE|ALEX_G|065` | UNRESOLVED | Y | n | 2 blocking open question(s) | The pattern sought is: the 4-hour goes bearish into the area, then shifts bullish within the sam |
| `KERULE|ALEX_G|070` | UNRESOLVED | Y | n | 2 blocking open question(s) | Bullish confirmations are used only at support and bearish confirmations only at resistance; the |
| `KERULE|ALEX_G|072` | UNRESOLVED | Y | n | 5 blocking open question(s) | Confirmations are only acted on in the direction of the prevailing trend; they are not direction |
| `KERULE|ALEX_G|102` | UNRESOLVED | Y | n | 3 blocking open question(s) | The EMA is used as dynamic support or resistance: support while bullish and resistance while bea |
| `KERULE|ALEX_G|103` | UNRESOLVED | Y | n | 2 blocking open question(s) | The entry zone is where the EMA and a prior structure point converge on the same retracement, ra |
| `KERULE|ALEX_G|104` | UNRESOLVED | Y | n | 2 blocking open question(s) | The counter-trend leg is deliberately forgone in order to take the larger continuation leg that  |

## INVALIDATION — 9 rules

| Rule | Class | Req | Det | Unresolved | Statement |
|---|---|---|---|---|---|
| `KERULE|ALEX_G|010` | UNRESOLVED | Y | n | 1 blocking open question(s) | A break below the higher low shifts the market from bullish to bearish, establishing a new lower |
| `KERULE|ALEX_G|014` | UNRESOLVED | Y | n | 2 blocking open question(s) | Trend invalidation requires a candle BODY close beyond the structure level, not merely a wick th |
| `KERULE|ALEX_G|028` | UNRESOLVED | Y | n | 1 blocking open question(s) | Price may move freely between the active structure levels; only a body close beyond one of them  |
| `KERULE|ALEX_G|041` | UNRESOLVED | Y | n | 1 blocking open question(s) | A move against the intended direction disqualifies the setup rather than signalling a sweep to t |
| `KERULE|ALEX_G|047` | UNRESOLVED | Y | n | 1 blocking open question(s) | Once the timeframe majority is directional, trades in the opposing direction are ruled out for t |
| `KERULE|ALEX_G|050` | UNRESOLVED | Y | n | 2 blocking open question(s) | A break out of the lower-high/lower-low box flips the bias to bullish and cancels all sell setup |
| `KERULE|ALEX_G|069` | UNRESOLVED | Y | n | 1 blocking open question(s) | Away from a level the confirmation rule is declared not applicable - the setup is skipped rather |
| `KERULE|ALEX_G|073` | UNRESOLVED | Y | n | 1 blocking open question(s) | A counter-direction engulfing appearing after a valid setup does not reverse the bias; the trade |
| `KERULE|ALEX_G|108` | UNRESOLVED | Y | n | 2 blocking open question(s) | A setup was declined because price stopped roughly 10 pips short of the target level. No toleran |

## RISK — 13 rules

| Rule | Class | Req | Det | Unresolved | Statement |
|---|---|---|---|---|---|
| `KERULE|ALEX_G|084` | EXPLICIT | Y | Y | — | Risk is defined and managed as a proportion of the deposited account balance, which is the refer |
| `KERULE|ALEX_G|085` | EXPLICIT | Y | Y | — | The full account balance is never risked on a trade. |
| `KERULE|ALEX_G|086` | EXPLICIT | Y | Y | — | The account must be funded with materially more than the intended per-trade risk, so that a loss |
| `KERULE|ALEX_G|087` | UNRESOLVED | Y | n | 1 blocking open question(s) | The same percentage must be risked on every trade. Varying risk between trades is explicitly nam |
| `KERULE|ALEX_G|088` | EXPLICIT | Y | Y | — | Risk is sized as a percentage of the account, never as a fixed monetary amount. Named as the sin |
| `KERULE|ALEX_G|090` | UNRESOLVED | Y | n | 1 blocking open question(s) | The risk percentage chosen depends on account type and objective - personal, funded, or a dispos |
| `KERULE|ALEX_G|091` | EXPLICIT | Y | Y | — | Conservative risk is 0.5 to 1% of the account per trade. |
| `KERULE|ALEX_G|092` | EXPLICIT | Y | Y | — | The conservative band is prescribed for lower-timeframe traders, on the stated reasoning that th |
| `KERULE|ALEX_G|093` | EXPLICIT | Y | Y | — | The recommended risk, described as the industry standard, is 1 to 2% of the account per trade. |
| `KERULE|ALEX_G|094` | EXPLICIT | Y | Y | — | Once chosen, the risk percentage is not raised after winning trades or lowered after losing trad |
| `KERULE|ALEX_G|096` | EXPLICIT | Y | Y | — | The high-risk band is 3 to 5% of the account per trade. |
| `KERULE|ALEX_G|097` | EXPLICIT | Y | Y | — | High risk is confined to a personal or disposable flipping account, explicitly to avoid breachin |
| `KERULE|ALEX_G|099` | EXPLICIT | Y | Y | — | His own practice: one risk percentage is chosen at the start of each month and held for the whol |

## TRADE_MANAGEMENT — 8 rules

| Rule | Class | Req | Det | Unresolved | Statement |
|---|---|---|---|---|---|
| `KERULE|ALEX_G|054` | EXPLICIT | n | Y | — | No action is taken while price travels toward the area of interest; the setup is left alone unti |
| `KERULE|ALEX_G|081` | UNRESOLVED | n | n | 2 blocking open question(s) | The stated average take-profit distance is roughly 80 to 100 pips. Given as a personal average,  |
| `KERULE|ALEX_G|095` | UNRESOLVED | n | n | 2 blocking open question(s) | A 1:2 risk-to-reward ratio is used as the worked example. It is illustrative arithmetic, not sta |
| `KERULE|ALEX_G|098` | UNRESOLVED | n | n | 1 blocking open question(s) | A second worked ratio: 5% risk at 1:3 reward produces 15% on a single trade. Again illustrative, |
| `KERULE|ALEX_G|109` | EXPLICIT | n | Y | — | After missing an entry, the stated response is to set an alarm for the next pullback rather than |
| `KERULE|ALEX_G|110` | UNRESOLVED | n | n | 2 blocking open question(s) | A 1:4 risk-to-reward is described for one watchlist setup. Stated as an observation about that c |
| `KERULE|ALEX_G|112` | EXPLICIT | n | Y | — | The stated implication is that a target set in advance should be allowed to run rather than cut  |
| `KERULE|ALEX_G|114` | EXPLICIT | n | Y | — | The prescribed response is not to show open positions to others, on the reasoning that their ref |

## SESSION_RESTRICTIONS — 7 rules

| Rule | Class | Req | Det | Unresolved | Statement |
|---|---|---|---|---|---|
| `KERULE|ALEX_G|060` | UNRESOLVED | Y | n | 3 blocking open question(s) | Entry additionally waits for 'the proper session'. Which sessions qualify is not stated. |
| `KERULE|ALEX_G|075` | UNRESOLVED | Y | n | 2 blocking open question(s) | Entry timing is governed by session and day-of-week; a valid confirmation at the wrong time is n |
| `KERULE|ALEX_G|076` | UNRESOLVED | Y | n | 3 blocking open question(s) | Tradeable windows are defined by session volume, shown on an on-screen session map. The specific |
| `KERULE|ALEX_G|077` | UNRESOLVED | Y | n | 2 blocking open question(s) | A window offering only about an hour of volume followed by roughly nine hours without is rejecte |
| `KERULE|ALEX_G|078` | UNRESOLVED | Y | n | 2 blocking open question(s) | A confirmation arriving before the Sydney session is held until just before the London session - |
| `KERULE|ALEX_G|080` | UNRESOLVED | Y | n | 2 blocking open question(s) | Entries on this confirmation are restricted to Monday, Tuesday and Wednesday. |
| `KERULE|ALEX_G|100` | UNRESOLVED | Y | n | 2 blocking open question(s) | Higher risk (3-5%) is taken only in November, December, January, February and possibly March, de |

## NO_TRADE_CONDITIONS — 14 rules

| Rule | Class | Req | Det | Unresolved | Statement |
|---|---|---|---|---|---|
| `KERULE|ALEX_G|002` | EXPLICIT | n | Y | — | Trading the correct direction from the wrong area is a distinct failure mode from trading the wr |
| `KERULE|ALEX_G|012` | EXPLICIT | n | Y | — | Misidentifying the origin of a trend invalidates entry, risk-to-reward, take-profit, stop-loss a |
| `KERULE|ALEX_G|016` | EXPLICIT | n | Y | — | Predicting tops or bottoms against the higher-timeframe direction has no longevity even when it  |
| `KERULE|ALEX_G|019` | EXPLICIT | n | Y | — | An area of interest placed below the higher low will only be reached after the market has alread |
| `KERULE|ALEX_G|026` | EXPLICIT | n | Y | — | Judging trend from the visual slope of price rather than from market structure is a primary trad |
| `KERULE|ALEX_G|051` | EXPLICIT | n | Y | — | A level may be a genuine and well-respected support/resistance level and still be untradeable, b |
| `KERULE|ALEX_G|067` | EXPLICIT | n | Y | — | Rejection and engulfing candles occur throughout any chart, so the pattern alone carries no info |
| `KERULE|ALEX_G|074` | EXPLICIT | n | Y | — | Entering on a candlestick pattern without a strategy behind it is characterised as gambling rath |
| `KERULE|ALEX_G|079` | EXPLICIT | n | n | — | Waiting for the session is acknowledged to lose trades outright when price leaves the area befor |
| `KERULE|ALEX_G|083` | EXPLICIT | n | Y | — | The method is presented as conjunctive: every component must hold, and one failing component is  |
| `KERULE|ALEX_G|089` | EXPLICIT | n | Y | — | Returns of 50% per day, week or month are described as unrealistic and unsustainable, though pos |
| `KERULE|ALEX_G|105` | EXPLICIT | n | Y | — | Counter-trend trading is characterised as a beginner error he has stopped making. The phrasing ' |
| `KERULE|ALEX_G|111` | UNRESOLVED | n | n | 1 blocking open question(s) | The named core failure: a trade set to a 1:4 target is closed at 1:2 because the unrealised doll |
| `KERULE|ALEX_G|113` | EXPLICIT | n | Y | — | The attributed cause of the loss of opportunity is deferring to someone else's judgement of what |

## DISCRETIONARY_ELEMENTS — 7 rules

| Rule | Class | Req | Det | Unresolved | Statement |
|---|---|---|---|---|---|
| `KERULE|ALEX_G|008` | DISCRETIONARY | n | n | 1 blocking open question(s) | In practice Alex G stops the directional pass after the 4-hour and uses the lower timeframes for |
| `KERULE|ALEX_G|045` | DISCRETIONARY | n | n | — | A structure point that has not completed is labelled a 'potential' lower high and used in the di |
| `KERULE|ALEX_G|056` | DISCRETIONARY | n | n | 1 blocking open question(s) | A lower high that has not yet completed - a 'potential' lower high - is accepted as a valid sell |
| `KERULE|ALEX_G|066` | DISCRETIONARY | n | n | 1 blocking open question(s) | Once the 4-hour higher low is identified, the subsequent wick fill and daily engulfing are descr |
| `KERULE|ALEX_G|071` | DISCRETIONARY | n | n | — | Entry on the rejection alone is permitted; waiting for the engulfing as well is optional and lef |
| `KERULE|ALEX_G|082` | DISCRETIONARY | n | n | 1 blocking open question(s) | The day restriction is overridden when the take-profit is shorter, the confirmation is very stro |
| `KERULE|ALEX_G|115` | DISCRETIONARY | n | n | — | He states he folds the 10% discretionary tranche into investment, so his own allocation is not t |


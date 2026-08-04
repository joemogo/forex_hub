# Glossary and Confluence Library — v1

**Updated:** 2026-07-27 (ALEX_G source #1) · **Terms:** 56 across **3 educators** · **Status:** every entry carries provenance.

> **Reading rule.** Two kinds of entry appear below and must never be conflated:
> - **Evidenced** — traceable to a claim, which traces to a verbatim excerpt in a registered
>   source. Cited by claim ID.
> - **Repository-confirmed** — a fact about MOGO's own implementation (a protected constant, a
>   documented engine). True of MOGO's code; **asserts nothing about any trader's method.**
>
> There is deliberately **no third category** for "commonly understood to mean". A term MOGO has
> not ingested does not get a definition here, however well known it is. See §3.

This file is the manual precursor to `PROPOSAL-003` (Concept Registry). When that is built, these
entries become `Concept` records and the `traderTerminology` mapping in
`CROSS-STRATEGY-ANALYSIS.md` §5 becomes structured data.

---

## 1. Evidenced terms (TJR)

All from `EVSRC|TJR|20260727|001`. **All at `emerging` confidence — single source.**

### Liquidity sweep
> Price taking out a prior high or low, which fills orders in the opposite direction.

`CLAIM|TJR|20260727|007` · `definition` · emerging
**Role:** Step 1 of TJR's sequence; required on every trade (`|008`, `|006`).
**Cross-strategy:** no JVM or ALEX_G analogue. Unique to TJR in MOGO today.

### Draw on liquidity
> Prior highs and lows that price is expected to move toward. Taken from 1-hour highs/lows, 4-hour
> highs/lows, or session highs/lows.

`CLAIM|TJR|20260727|009` · `setup_requirement` · emerging
**Qualifier:** a level already swept without a reaction is *not* used (`|011`, implied rule).
**Cross-strategy:** ≈ JVM `aoi` (weight 20) ≈ ALEX_G zone. **Strongest three-way agreement.**

### Break of structure (BOS)
> To the downside: price closing underneath the most recent low within the uptrend.

`CLAIM|TJR|20260727|015` · `definition` · emerging
**Role:** one of four confirmation confluences (`|013`); only one of the four is required (`|014`).
**Cross-strategy:** ≈ JVM `msb` (weight 10) ≈ ALEX_G zone break. **Same concept, sharply different
weighting** — a mandatory gate for TJR, 18% of firing threshold for JVM.
**Note:** the upside definition is *not* stated in the source. Recorded as asymmetric rather than
mirrored by assumption.

### SMT divergence
> One index makes a higher high while the other makes a lower high; or one makes a lower low while
> the other makes a higher low.

`CLAIM|TJR|20260727|016` · `definition` · emerging
**Role:** confirmation confluence; also permitted as a *continuation* confluence when 2B is active
(`|025` — and see `XCONTRA|20260727|002`).
**Structural note:** requires **two correlated instruments**. Not expressible in MOGO's current
single-instrument model, and has no direct FX transfer (see `PROPOSAL-001` §3).

### Fair value gap (FVG)
**Not independently defined in the source.** Used throughout as one of two continuation confluences
and as the "inverse fair value gap" confirmation confluence, but never defined.
**Status:** *term used, definition absent.* Recorded as a knowledge gap rather than filled in.
→ Acquisition target `BACKLOG-002/T5`.

### Equilibrium
**Not independently defined in the source.** Used as the other continuation confluence, and in
context implies the midpoint of a measured leg — but that reading is **inferred, not stated**, so
no definition is recorded.
**Status:** *term used, definition absent.* → `BACKLOG-002/T5`.

### Continuation confluence
> Limited to equilibrium and fair value gaps.

`CLAIM|TJR|20260727|024` · `definition` · emerging
⚠️ **Contradicted** by `|025` (SMT permitted when 2B active) — `XCONTRA|20260727|002`, open.

### Confirmation confluence
> Break of structure, inverse fair value gap, SMT divergence, or a 79% Fibonacci extension closure.

`CLAIM|TJR|20260727|013` · `confirmation_rule` · emerging
**Key qualifier:** only one is required (`|014`), not all four.

### 79% extension
> A candlestick closure beyond the 79% Fibonacci extension measured from the low to the high of the
> move.

`CLAIM|TJR|20260727|017` · `definition` · emerging

### Five-minute manipulation (Step 2B)
> When the liquidity sweep occurs during pre-market or a previous session, a further five-minute
> manipulation is required before proceeding.

`CLAIM|TJR|20260727|018` · `confirmation_rule` · emerging
**Rationale:** new money at the NY open re-manipulates price (`|019`).
**Evidence quality:** the only TJR concept with a demonstrated counterfactual — skipping it would
have been stopped out (`|020`). **Highest-value replay candidate** (`RC-01`).

### Leading index / lagging index
> The leading index is the one closer to the draw on liquidity, or — in a bullish SMT — the one
> that makes the higher low. Trades are taken on the leading index, never the lagging one.

`CLAIM|TJR|20260727|005` (definition), `|004` (rule) · emerging

### New York pre-market
> Starts at 8:30.

`CLAIM|TJR|20260727|003` · `definition` · emerging
**Timezone resolved by source #2** (`EVSRC|TJR|20260727|002`): *"market opens at 9:30 a.m. Eastern
time"*. TJR's session times are quoted in **Eastern**. Linked as `contextualizes` — it clarifies the
frame without corroborating the 8:30 figure itself, so confidence is unchanged at `emerging`.

### Chart time zone
> Charts must be set to New York (Eastern) time regardless of the trader's physical location.

`CLAIM|TJR|20260727|002|…` (source #2) · `setup_requirement` · emerging
**Rationale:** *"the market lives on Eastern time. So, in turn, we have to live on Eastern time."*
**Failure mode stated:** marking session levels on a non-Eastern chart puts them at the wrong times
and makes the strategy appear not to work. **The most operationally consequential rule in source
#2**, and a prerequisite for every session-based claim in source #1.

### High / Low (structural)
> A high is a move up followed by a move down; a low is a move down followed by a move up.
> Identified as an up candle followed by a down candle (high) or a down candle followed by an up
> candle (low), marked at the highest/lowest wick of the two.

Source #2 · `definition` · emerging
**Why it matters:** source #1 built its entire draw-on-liquidity framework on "highs and lows"
without ever defining them. This fills that gap.

### Uptrend / Downtrend
> An uptrend is a series of higher highs and higher lows. A downtrend is a series of lower highs
> and lower lows. The market moves in exactly three states: uptrend, downtrend, or consolidation.

Source #2 · `definition` · emerging
**Caveat stated by the source:** trend direction alone is not a trade signal — *"trends can break,
trends can change."*
**Gap:** consolidation is named but never defined.

### Liquidity *(ALEX_G)*
> How liquid the market is at a given price point — the concentration of buy and sell orders there.
> It exists everywhere, but concentrates where price has been repeatedly rejected.

`ALEX_G` source #3 · `definition` · emerging
**Zone criteria:** more than three taps ideal; one tap materially weaker; higher timeframes stronger.
**Synonyms Alex G treats as identical:** support/resistance, supply and demand, order block, area of
interest, liquidity zone. ⚠️ This is a **five-way terminology collapse by one educator** — strong
evidence for `PROPOSAL-003`.

### Liquidity sweep — ⚠️ **the library's central disagreement**
> TJR: price taking out a prior high or low, which fills orders in the opposite direction. **Step 1
> of his method, required on every trade.**
> Alex G: a real phenomenon, but one that **cannot be anticipated or systematised** — *"there's no
> way that you can have a specific strategy to trade solely off of these sweeps."*

`XCONTRA|20260728|001` · DIRECTIONAL · **blocking** · CROSS-EDUCATOR → `RC-20`
**Partial reconciliation:** Alex G objects to *anticipating* sweeps; TJR reacts to sweeps that have
already happened. Closer than the words suggest — but that reading is MOGO's, not either
educator's, so the record stays open.

### Confirmation versus anticipation *(ALEX_G)*
> Enter only when price is already moving in the intended direction. A move against the intended
> direction disqualifies the setup rather than signalling a sweep to trade into.

`ALEX_G` source #3 · `entry_rule` / `invalidation_rule` · emerging
**Named confirmations:** bullish engulfing, morning star, bullish candle rejection, pin bar
rejection, multiple dojis.
⚠️ Directly contradicts TJR's step 2B, which treats a counter-move as a **required** manipulation.

### Institutional liquidity grab — ⚠️ **contested mechanism**
> TJR: market makers sweep highs and lows to fill large positions in the opposite direction.
> Alex G: *"There is no real hardcore evidence that this is a bank or an institution"* — *"almost a
> big hoax"*, resting on the (unsourced) claim that retail is 3% of the market.

`XCONTRA|20260728|002` · DEFINITIONAL · material · CROSS-EDUCATOR
**Empirically unresolvable by MOGO:** clustering is testable (`RC-21`), intent is not.

### Two-timeframe sync *(ALEX_G)*
> *"I do not take any trade unless we have two time frames in sync."* At least two of the weekly,
> daily and 4-hour reads must agree on direction before any trade is considered.

`ALEX_G` source #4 · `setup_requirement` · emerging → `RC-22`
**Scored:** 10 points per aligned timeframe; the worked example is graded 20.
⚠️ **The maximum of the scale is unknown** — the caption is garbled and both 30 and 40 are
derivable. A threshold without its scale is not implementable; MOGO must not choose one.
⚠️ In his own example the daily disagrees and costs nothing, so "in sync" tolerates an opposing
timeframe between two agreeing ones.

### The box *(ALEX_G)*
> The region between the active lower high and lower low (bearish) or higher high and higher low
> (bullish), drawn explicitly. **The search for an area of interest is confined to it.**

`ALEX_G` sources #1 and #4 · `setup_requirement` · emerging → `RC-23`
**Invalidation:** price leaving the box flips the bias and cancels every setup derived from it.
**The sharp corollary:** a level can be genuine, clean, well-respected support/resistance **and
still be untradeable**, because price reaching it would already have invalidated the bias. TJR has
no equivalent guard.

### Lower high / higher low as entry locations *(ALEX_G)*
> *"If you're looking to sell you need to sell at a lower high; if you're looking to buy you need to
> buy at a higher low."* The structure point must be present on the four-hour timeframe.

`ALEX_G` source #4 · `entry_rule` · emerging
**If the first approach produces no lower high, no trade is taken** — the requirement is to wait for
a break of structure that creates one.
⚠️ He also permits a *"potential"* lower high — one that has not completed — which contradicts his
own confirmation rule from source #3. `XCONTRA|20260728|003` → `RC-24`.

### "The proper session" *(ALEX_G)* — ⚠️ **named as required, never defined**
> Entry waits for "the proper session" after all structural conditions are met.

`ALEX_G` source #4 · `session_rule` · emerging
Together with *"trading at the right times"* (source #2), session timing has now been named as
necessary **twice across four sources and specified zero times.** Tracked as `BACKLOG-002/A6`. MOGO
must not supply a session list — TJR's sessions are evidenced for TJR only.

### Entry confirmation *(ALEX_G)* — the most precisely stated rule in the library
> A **closed** candlestick that is either a rejection/doji or an engulfing, occurring **at a level**,
> in the **direction of the trend**.

`ALEX_G` source #5 · `confirmation_rule` / `setup_requirement` · emerging
**The closure requirement is absolute:** *"as soon as that candlestick closes, it is a confirmation.
One second before it closes, it is an entire anticipation."* Any timeframe from 1-minute to yearly.
**The gate is absolute:** no rejection and no engulfing ⇒ no trade, regardless of how good the rest
of the setup is — restated verbatim in the summary.
**Engulfing** requires a body close beyond the prior candle; size is irrelevant, side is not.
⚠️ Body-engulfs-body vs body-closes-beyond-range is not disambiguated, and the two detectors fire on
different bars.

### Wick fill *(ALEX_G)*
> A candle that looks like a rejection but is actually a higher low forming on a lower timeframe.
> Distinguished from a true rejection only by cross-referencing the 4-hour **within the same day**.

`ALEX_G` source #5 · `definition` · emerging → `RC-25`
**The sought pattern:** 4H goes bearish into the zone → shifts bullish within the same day → retests,
which produces the daily rejection wick. The following day is claimed bullish ~70% of the time —
`performance_hypothesis`, blocked, but **the most precisely specified setup any educator in the
library has given**, and therefore the most testable.

### Session and day-of-week filter *(ALEX_G)* — the "right times" gap, downgraded not closed
> Enter only inside the high-volume session windows, and only on **Monday, Tuesday or Wednesday**.
> A confirmation arriving before a session is **held** until the session — *"that's the black and
> white rule."*

`ALEX_G` source #5 · `session_rule` · emerging → `RC-26`
**Rationale given:** an average take-profit of 80–100 pips needs enough remaining volume hours to be
reached; Thursday and Friday do not provide them.
**Overrides:** shorter take-profit, very strong confirmation, or momentum — **none quantified.**
⚠️ **The session hours themselves are shown as coloured bands on screen and never spoken.** The rule
is prescriptive and its parameters are missing. MOGO must not supply hours from TJR's material.

### Pro-trend confirmation *(ALEX_G)*
> Confirmations are acted on **only** in the direction the market is already going. They are filters,
> not direction-generating signals.

`ALEX_G` source #5 · `entry_rule` / `invalidation_rule` · emerging
**The corollary is the sharp part:** a counter-direction engulfing after a valid setup does **not**
flip the bias — the trade is skipped, not reversed. *"You simply don't just change your direction or
change your bias overnight."*
⚠️ The timeframe on which that trend is defined is not stated in this source.

### Risk per trade *(ALEX_G)* — percentage of account, never dollars
> Risk is sized as a fixed **percentage of the deposited account balance**, identical on every
> trade. Sizing in dollars is named as the single biggest mistake traders make.

`ALEX_G` source #6 · `risk_rule` · emerging · **13 risk_rule claims, the largest single-cycle
addition in any rule category**

| Band | Size | Prescribed for |
|---|---|---|
| Conservative | **0.5–1%** | Lower-timeframe traders taking 1–3 trades per day or per session |
| Standard ("industry") | **1–2%** | His general recommendation |
| High | **3–5%** | Personal or disposable accounts **only** — explicitly to avoid breaching funded-account rules |

**Stability rules:** never raised after wins or lowered after losses; one percentage chosen at the
start of each month and held all month regardless of streaks.
**Stated purpose:** a stable P&L curve is what allows capital allocators to fund a trader.

⚠️ **This is risk *sizing*, not stop *placement*.** See below.

### Stop placement — ⚠️ **the library's oldest and most consequential absence**
> Not defined in any of six Alex G sources.

**Position size = risk amount ÷ stop distance.** Source #6 supplies the first term and never the
second, so a trader following it knows to risk 1% and has no rule for converting that into a lot
size. TJR places the stop beyond the swing; that is evidenced **for TJR only**.

⚠️ **The forbidden inference.** Source #5's 80–100 pip average target and source #6's 1:2 / 1:3
worked ratios would together imply a ~27–50 pip stop. **MOGO must not make that inference** — both
ratios are illustrative arithmetic inside an argument about escalating risk, and the pip figure was
a past average, not a selection rule. Combining two descriptive statements into a prescriptive third
would be inventing a rule and attributing it to someone who did not state it.

**Consequence:** no Alex G claim can be replayed for P&L. Every candidate RC-12…RC-27 measures
trigger accuracy, reach-rate, frequency or direction.

### Seasonal risk escalation *(ALEX_G)*
> Higher risk (3–5%) is taken **only** in November, December, January, February and possibly March —
> his stated best months. June, July and August are described as slower; risk is reduced and trading
> becomes optional.

`ALEX_G` source #6 · `session_rule` / `marketCondition` · emerging → `RC-27`
⚠️ **The only claim in the library that changes position size**, and its entire basis is *"months
statistically that I've seen in my trading"* with no data shown. Testable without the missing stop
rule — count setup frequency and outcome by calendar month, controlled against unconditional
monthly volatility.

### The EMA *(ALEX_G)* — role finally stated, period still missing
> A moving average used as **dynamic support while bullish and dynamic resistance while bearish**.
> The preferred entry is where the EMA and a prior structure point converge on the same retracement.

`ALEX_G` sources #5 and #7 · `confirmation_rule` / `entry_rule` · emerging
⚠️ **Two sources now use the EMA as a load-bearing confluence and neither states its period.** Source
#7 adds the role, which is genuinely new; the parameter is still absent, so the rule cannot be
reproduced.

### Confluence counting *(ALEX_G)* — the decision rule that exists only on screen
> Direction is chosen by counting the confluences available for **each** side and taking the side
> with materially more: *"find me this many confluences here to go long — there won't be any."*

`ALEX_G` source #7 · `setup_requirement` · emerging
He states he always writes the confluences down, displays the list, and invites the group to
screenshot it — and **never reads it aloud**. The list *is* the decision rule, and it is visually
present in the source and textually absent.
⚠️ **Third visual-only artifact in three sources**, after the session volume map (#5) and the setup
grading scale (#4).

### Proximity tolerance *(ALEX_G)* — ⚠️ **behaviour without a taught rule**
> A setup was declined because price came **about 10 pips short** of the 86.000 level:
> *"I wasn't really that convinced because we were shy about, let's say, like 10 pips."*

`ALEX_G` source #7 · `invalidation_rule` · emerging · `XCONTRA|20260728|008` → `RC-28`
Every instructional source states the condition as **binary** — the confirmation must be *at* a
level, and away from one the rule is "simply not applicable". Live, it operates as **graded**.
**No source in the library supplies a tolerance. MOGO must not pick one.**

### Selectivity *(ALEX_G)*
> *"I only take trades that are worth my money."* Capital is deployed only when the expected return
> justifies it — never in order to be active. Month-to-date performance is an input: *"I've already
> made money trading this month, so I don't really need to take any trades."*

`ALEX_G` source #7 · `setup_requirement` / `behavioral_observation` · emerging
Presented as a gate **in addition to** the mechanical entry conditions, justified by an investment
analogy rather than a threshold. Counter-trend trading is dismissed outright — *"never, bro, not
anymore… that's a rookie thing."*

### Money mindset *(ALEX_G)* — percentage, never dollars
> Trade decisions must be made on **percentages of the account**, never on the dollar figure. The
> named failure: a 1:4 target closed at 1:2 because the unrealised amount equals a month's salary.

`ALEX_G` source #8 · `failure_condition` / `trade_management_rule` · emerging
**The implied rule:** a target set in advance should be allowed to run. Never stated as one.
⚠️ **The distinction the source does not draw:** it rules out cutting a target for an *emotional*
reason and says nothing about cutting for a *market* reason. Any trade-management rule needs that
line, and no source draws it.
**Related practices:** don't show open positions to anyone; keep the employment mindset and the
trading mindset separate.

### 30/30/30/10 rule *(ALEX_G)* — personal finance, **not** a trading rule
> 30% of income to residual expenses · 30% to savings · 30% to investment · 10% discretionary.

`ALEX_G` source #8 · typed `other` **so it cannot be mistaken for a trading rule** · emerging
⚠️ He states he folds the 10% into investment, so his own allocation is not the one he prescribes —
openly, so it is an exception rather than a contradiction. Second instance in two sources of practice
diverging from a stated rule, after the proximity tolerance in source #7.

### Stop placement *(RAYNER_TEO)* — ⭐ **the library's first complete stop rule**
> Place the stop at the level that **invalidates the trade's premise** — below the support the setup
> relies on. Set it objectively at **the low of the support area minus one 20-period ATR (SMA)**, and
> **never flush against the level**, because price routinely spikes just beyond before continuing.

`RAYNER_TEO` source #1 · `stop_rule` · emerging → `RC-30`
**Never tighten the stop to improve risk-to-reward** — it sits where the setup is falsified, and
exiting before that point is incoherent with the trade's premise. Improve the **entry** with a buy
limit instead.
⚠️ **Evidenced for RAYNER_TEO only.** Eight ALEX_G sources state no stop at all; borrowing this rule
across educators would fabricate a rule and attribute it to someone who never stated it.

### The three-part framework *(RAYNER_TEO)*
> **Market structure** tells you *what* to do (buy, sell, or stay out) · **Area of value** tells you
> *where* · **Entry trigger** tells you *when*.

`RAYNER_TEO` source #1 · `setup_requirement` · emerging
**The components are gated in order:** without an area of value the entry trigger is not even
evaluated. Demonstrated twice on setups skipped for exactly that reason — including one where a
valid trigger was present.
**Staying out is a decision.** When a chart is ambiguous the prescribed action is to skip it.

### Area of value *(RAYNER_TEO)*
> Support is an area where buying pressure **could** step in; resistance is an area where selling
> pressure **could**. Located with support/resistance and moving averages.

`RAYNER_TEO` source #1 · `definition` · emerging
**An area, not a line** — price may overshoot, undershoot or never touch it, and the level must be
adjusted as new price action arrives. The conditional "could" is stated deliberately: trading is
described as probabilities, never certainty.
**Stacked area:** where two independent areas of value coincide (e.g. a 50-period MA and prior
resistance-turned-support), the confluence is treated as stronger than either alone.

### Target placement *(RAYNER_TEO)*
> Set the target **just before** the nearest opposing swing high or low — never at it, and never
> beyond it merely to make risk-to-reward look acceptable.

`RAYNER_TEO` source #1 · `target_rule` · emerging
⚠️ Asymmetry worth noting: the **risk** leg in this source is mechanical (one ATR); the **reward** leg
is *"just before"* and *"be reasonable"* — undefined.

### Swing-point significance — ⚠️ **the library's most load-bearing undefined number**
> RAYNER_TEO: only **major** swing points count — the ones that "stick out like a sore thumb".
> ALEX_G: a body close beyond a level counts **regardless of size**, no minimum threshold.

`XCONTRA|20260729|001` · CONDITIONAL_SCOPE · material · **cross-educator** → `RC-29`
Same operation, opposite instruction. This parameter already gates RC-12, RC-13 and RC-19 via
RC-16, and two independent educators have now given contradictory guidance about it. **MOGO must not
pick a value** — RC-29 sweeps it and reports the sensitivity surface.

### Order block / breaker block
**Deliberately removed from TJR's method.** *"I pretty much completely removed that"* — unused for
six months, on the reasoning that price filling an FVG or equilibrium hits them anyway (`|038`).
**Status:** recorded as an *excluded* concept — MOGO knows TJR does not use these, which is itself
evidence. → Redundancy test `RC-02`.

---

## 1b. Evidenced terms (ALEX_G)

From `EVSRC|ALEX_G|20260727|001`. **All at `emerging` confidence — single source.**

### Top-down analysis
> Establishing market direction by classifying each timeframe bullish or bearish from the weekly
> downward, then combining the results into an overall score.

`ALEX_G` `|009`, `|010` · `setup_requirement` · emerging
**Stated as non-negotiable** for every trading style (`|002`).
**Cross-strategy:** ≈ JVM's `bias3`+`bias2` (40 of a 55 threshold — its largest input), but
rule-based rather than weighted. **No TJR analogue** — TJR's `higher_timeframe_bias` gap is exactly
this concept.
**Gap:** the scoring method, weighting and alignment threshold are never specified.

### Timeframe hierarchy
> Weekly (foundation), daily (structure), 4-hour, then the lower timeframes: 2h, 1h, 30m, 15m.
> Anything below 15m is "not a strong lower time frame". On conflict, the higher timeframe wins.

`ALEX_G` `|005`, `|006`, `|007` · `timeframe_rule` · emerging
**Rationale:** higher-timeframe structure takes longer to form, so it is treated as stronger (`|008`).

### Bullish / bearish market *(ALEX_G)*
> A bullish market is higher highs and higher lows; a bearish market is lower highs and lower lows.
> The two are mutually exclusive — the labels cannot be mixed.

`ALEX_G` `|012`, `|013`, `|014` · `definition` · emerging
✅ **Independently agrees with TJR** (`CLAIM|TJR|…|067`, `|068`) — same definition, different
educator, different instrument. The library's strongest cross-educator agreement.
⚠️ Confidence unchanged: trader-scoped claims never merge (`CROSS-STRATEGY-ANALYSIS.md` §6).

### Structure re-anchoring
> Every new higher high forces the higher low to move up to the preceding structure point; every
> new lower low forces a new lower high. A break below the higher low flips bullish → bearish; a
> break above the lower high flips bearish → bullish.

`ALEX_G` `|016`, `|017`, `|019` · `setup_requirement` / `invalidation_rule` · emerging
**The mechanical core of the method** — the only fully specified state machine in the library.

### Body close *(structure invalidation)*
> Trend invalidation requires a candle **body** close beyond the level, not a wick through it.

`ALEX_G` `|022` · `invalidation_rule` · emerging
✅ Agrees with TJR that a **close** is required (`CLAIM|TJR|…|015`).
⚠️ **Disagrees on which part closes** — see the contradiction below.

### Bodies versus wicks
> Highs and lows are marked at candle bodies, not wicks.

`ALEX_G` `|020` · `setup_requirement` · emerging
🔴 **`XCONTRA|20260727|003` — the library's first CROSS-EDUCATOR contradiction.** TJR marks a high
at *"the highest point of those two candlesticks"* — the wick (`CLAIM|TJR|…|065`). Same operation,
incompatible price levels, and everything downstream moves with it. → `RC-10`.

### Sequencing rule
> The higher high always leads a bullish structure; the paired higher low is always behind it in
> time. *"It is impossible to have the higher low in front of the higher high."*

`ALEX_G` `|024` · `setup_requirement` · emerging
**Unique to ALEX_G** — no analogue anywhere else in the library.

### Area of interest (AOI)
> A zone with a decent number of prior rejections, drawn **only** on the weekly and daily
> timeframes, and located **inside** the current higher high and higher low.

`ALEX_G` `|027`, `|028`, `|029` · `entry_rule` · emerging
**Stated failure mode:** an AOI below the higher low is only reached after the market has already
turned bearish, so the setup is invalid by the time price arrives (`|028`).
**Strength by overlap:** where weekly and daily zones coincide, the zone is "two areas of interest
strong" (`|030`).
**Cross-strategy:** ≈ TJR's draw on liquidity ≈ JVM `aoi` ≈ ALEX_G engine zone — but note the role
differs: TJR uses prior levels as *targets*, ALEX_G as *entry zones*.

### Rejection candlestick *(entry signal)*
> Multiple dojis, or an engulfing candle, at the area of interest.

`ALEX_G` `|031` · `entry_rule` · emerging
⚠️ **Three-way split.** ALEX_G makes candlestick patterns the entry trigger; JVM prices
`wick`+`engulf` at 35 of 55; **TJR removed pattern confluences entirely** and reports his best year
without them (`CLAIM|TJR|…|038`). → `RC-02`.
**Gap:** "multiple dojis" — how many is unspecified.

### Counter-trend retracement *(expected, not a reversal)*
> The lower timeframe must move against the higher-timeframe direction in order to deliver price
> into the area of interest. *"The market is going to have to go bearish so it can have the
> retracement to then continue going to the upside."*

`ALEX_G` `|033` · `causal_hypothesis` · emerging
**Why it matters:** it reframes an adverse lower-timeframe move as part of the setup rather than a
reason to abandon it — the mirror image of TJR's step 2B, which treats a comparable move as a
required manipulation.

---

## 2. Repository-confirmed terms (MOGO's own engines)

**These describe MOGO's implementation. They are not attributed to any trader.**

### Confluence score (JVM)
Weighted sum against a threshold: `{bias3:25, bias2:15, aoi:20, wick:15, engulf:20, session:10,
msb:10}`, firing at `ALERT_THRESHOLD: 55`.
*Source:* protected constants `WEIGHTS`, `ALERT_THRESHOLD` in `index.html`.
**Contrast:** TJR uses a conjunctive gate chain, not an additive score (`CROSS-STRATEGY-ANALYSIS`
§2). Same domain, different theory of what a setup is.

### Area of interest (`aoi`) — JVM
Prior significant price level; weight 20 of 55.
**Cross-strategy:** ≈ TJR draw on liquidity ≈ ALEX_G zone.

### Zone (ALEX_G)
Detected support/resistance region driving two setup types: **Break & Retest** and **Repeated Zone
Reaction**. *Source:* `SF|ALEX_G|SUPPORT_RESISTANCE_V1`.

### Session/Zone Engine (TJR, implemented)
Deterministic previous-session (Asian/London/New York) high/low zone construction — 9 pure
functions, 48 fixtures, shipped v12.3.0. **The only TJR component implemented in MOGO.**
*Important:* it draws zones; it generates no signals. The interaction/reaction engine, 5m BOS
confirmation, candidate generation, and entry/stop/target/risk calculation are all **not
implemented** (`SF|TJR|SESSION_ZONE_REACTION`).

---

## 3. Terms deliberately absent

MOGO does **not** define these, despite their being widely used in the trading education space and
adjacent to terms above:

**MSS / CHOCH · Supply and Demand · Premium/Discount · Displacement · Optimal Trade Entry · Judas
Swing · Killzone · Mitigation block**

No registered source defines any of them. Adding textbook definitions would create authoritative-
looking entries with no provenance, indistinguishable in the data from evidenced ones. If a term
here matters, the answer is to **acquire a source that defines it** — not to write it down.

Two of these are near-misses worth tracking: **MSS** (market structure shift) and **CHOCH** (change
of character) are commonly used near-synonymously with break of structure. If a future source uses
them alongside BOS, that is exactly the `PROPOSAL-003` F1/F2 problem arriving — same idea, different
words, or same word, different ideas — and should be recorded when it happens.

---

## 4. Maintenance

**On every ingestion:** add evidenced terms with claim IDs; move "term used, definition absent"
entries into §1 when a source defines them; record new terminology for the same concept in
`CROSS-STRATEGY-ANALYSIS.md` §5; note any §3 term that acquires evidence.

**Never:** define a term from general knowledge; merge two traders' terms without recording both;
drop a term because a trader stopped using it (removal is evidence — see order blocks).

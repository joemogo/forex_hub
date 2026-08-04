# Cross-Strategy Analysis — v9

**Updated:** 2026-07-28 (Alex G source #8 ingested) · **Strategies compared:** TJR, ALEX_G, JVM
**Evidence basis:** TJR — 69 claims from 2 sources. ALEX_G — 195 claims from 8 sources.
JVM — no external research; repository-confirmed implementation facts only.

> **v9: the library has a third educator.** RAYNER_TEO supplies the **first complete stop rule** in
> eleven sources, the **first P&L-capable replay candidate** (RC-30), and the **first cross-educator
> contradiction that three-way context makes visible** (RC-29). It also **did not move a single
> claim's confidence** — which is the finding that matters most. See §3i.

---

## 1. What could not be compared

**ICT and SMC — still no evidenced material.** Registered as a trader (`traders/ict/`) with every
field empty. I have not written ICT definitions from general knowledge and will not; doing so would
create provenance-free rules indistinguishable from evidenced ones.

**JVM — structural comparison only.** `externalResearchStatus: not_started`. Its `WEIGHTS` constant
describes *what MOGO implemented*, not what any trader teaches (`DECISION|MOGO|20260727|004`).

---

## 2. The two educators, side by side

| | **TJR** (2 sources, 69 claims) | **ALEX_G** (8 sources, 195 claims) |
|---|---|---|
| Instrument (evidenced) | US indices — S&P 500, NASDAQ | FX pairs shown (AUDCHF, GBPNZD, AUDUSD, NZDUSD); structure claimed instrument-agnostic |
| Timeframes | 5m confirmation, 1m execution | Weekly / daily / 4h directional; 2h–15m for entry |
| Higher-timeframe bias | ❌ **absent** — a critical gap | ✅ **the entire method**, and now **gated**: no trade without ≥2 timeframes aligned |
| Decision arithmetic | ❌ none stated | **10 points per aligned timeframe**; worked example graded 20 |
| Decision shape | Conjunctive gate chain (sweep → confirm → continue → enter) | Directional score → zone → confirmation candle |
| Entry zone | Draws on liquidity (**targets**) | Area of interest / liquidity zone (**entry**), ≥3 taps ideal |
| Entry trigger | 1-minute confirmation confluence | Rejection/doji **or** engulfing — **only on a closed candle**, only at a level, only pro-trend |
| Structure marked at | **Wicks** | **Bodies** |
| **Liquidity sweeps** | **The premise** — required every trade | **Cannot be systematised**; enter on confirmation instead |
| **Why price sweeps** | Market makers filling positions | **No evidence for that**; "almost a big hoax" |
| Session timing | Pre-market and session opens; NY-centric | **London/NY volume windows; wait for the session before entering** |
| Day-of-week filter | ❌ none stated | **Monday, Tuesday, Wednesday only** |
| Target | Prior draws on liquidity; ladder undefined | **~80–100 pips average** (stated as an average, not a selection rule) |
| Risk per trade | ❌ none stated | **0.5–1% / 1–2% / 3–5% of account, by account type** |
| Stop placement | Beyond the swing | ❌ **still nothing, across six sources** |

### The complementarity is the headline

**TJR's largest gap is ALEX_G's entire method, and vice versa.** TJR has no higher-timeframe bias
rule — the `higher_timeframe_bias` gap has been open since source #1. ALEX_G is *nothing but*
higher-timeframe bias, and stops before entry mechanics. TJR is nothing but entry mechanics.

They are not competing systems; they occupy adjacent layers. That is worth stating because it is
the first time MOGO's library contains two educators whose material could, in principle, compose.

---

## 3. Agreements

**A1 — Trend definition. Independent, verbatim-level agreement.**
- TJR: *"an uptrend which consists of higher highs and higher lows"* (`CLAIM|TJR|…|067`)
- ALEX_G: *"a bullish market is created of higher highs and higher lows"* (`CLAIM|ALEX_G|…|012`)
- Same for downtrend: lower highs and lower lows (`|068` / `|013`)

Two educators with different instruments, timeframes and methods define trend identically. **This is
the strongest cross-educator signal the library has ever held.** See §6 for why it did not raise
confidence.

**A2 — A close, not a touch, changes structure.**
- TJR: break of structure is *"price to close underneath the most recent low"* (`|015`)
- ALEX_G: *"We have not body candlestick closed below the higher low"* (`ALEX_G|…|022`)

Both require a **close** beyond the level. They disagree on *which part* of the candle closes
(§4/C1), but agree that a wick-through is not a break.

**A3 — Direction alone is not a trade signal.**
- TJR: *"trading is not as simple as saying, hey, we're in an uptrend. I'm just going to blind
  blindly press buy"* (`|069`)
- ALEX_G: *"You can't just enter based off of the overall trend"* (`ALEX_G|…|029`)

**A4 — Prior significant levels anchor the setup.** TJR's draws on liquidity ≈ ALEX_G's areas of
interest ≈ JVM's `aoi` (weight 20) ≈ ALEX_G engine zones. All four act on prior levels — though
TJR uses them as *targets* and ALEX_G as *entry zones*, which is a real difference in role.

---

## 3b. TJR versus Alex G on liquidity — the library's central disagreement

Alex G source #3 is entirely about liquidity, which is the foundation of TJR's entire method. The
two educators are now in direct, documented conflict on both **the premise** and **the mechanism**.

### The premise — `XCONTRA|20260728|001` · DIRECTIONAL · **blocking**

| | |
|---|---|
| **TJR** | *"My strategy is based off of liquidity sweeps"* · *"I'm looking for a liquidity sweep every single time"* |
| **Alex G** | *"There's no way that you can have a specific strategy to trade solely off of these sweeps"* — and anyone claiming otherwise *"is 100% lying to you"* |

**The first `blocking` contradiction in the library.** This is not a parameter disagreement: one
educator's whole method is the thing the other says cannot be done consistently.

**Partial reconciliation, stated honestly.** Alex G's explicit target is *anticipating* a sweep
before it happens. TJR identifies a sweep that has **already occurred**, then requires a separate
confirmation confluence before entering. On that reading they are far closer than the words suggest
— arguably TJR's step 2 *is* Alex G's confirmation. **That reading is MOGO's, not either
educator's**, which is why the record stays `blocking` and open.

Alex G also undercuts himself here: he describes his own live AUDCHF position as *"entering a trade
technically after the liquidity sweep."* Recorded as a `critical` open question.

### The mechanism — `XCONTRA|20260728|002` · DEFINITIONAL · material

| | |
|---|---|
| **TJR** | *"market makers sweep highs and lows specifically to fill large positions in the opposite direction"* — the causal engine of his framework |
| **Alex G** | *"There is no real hardcore evidence that this is a bank or an institution that has liquidated your position"* — calls it *"almost a big hoax"* |

Both are causal hypotheses about *why* price sweeps levels, and they are incompatible. Neither
educator offers evidence — but the asymmetry matters: **TJR asserts a mechanism; Alex G asserts the
absence of proof for it.** Alex G is the only source in the library to make an explicitly epistemic
argument rather than a market one.

His argument rests on an unsourced statistic — *"retail traders only make up 3% of the market"* —
recorded as `performance_hypothesis` at low quality with its own open question.

### What they nonetheless agree on

Both place the entry zone at **repeated prior rejections**; both **wait for confirmation** rather
than entering on arrival; both say **don't buy the high**. The disagreement is about what a sweep
*means* and whether it can be *systematised* — not about where opportunity sits.

### Why this is the most valuable disagreement in the library

It is **falsifiable and cheap**. Alex G's own worked example is the test: price approached one zone
seven times and swept once. If that ratio generalises, waiting for sweeps forfeits most
opportunities and TJR's premise is expensive; if sweeps cluster at session boundaries as TJR claims,
Alex G is generalising from a chart that lacks TJR's session context. **Neither needs a risk model
to settle** → `RC-20`.

---

## 3c. Alex G's scoring rule and MOGO's JVM engine have the same shape

Source #4 is the first time any educator in the library has stated **arithmetic**:

> *"it's 10 per time frame"* — `CLAIM|ALEX_G|20260728|039`
> *"I do not take any trade unless we have two time frames in sync"* — `CLAIM|ALEX_G|20260728|035`

That is a weighted sum over independent conditions plus a minimum threshold — structurally the same
decision shape as JVM's shipped `WEIGHTS` / `ALERT_THRESHOLD` pair. **This is a structural
resemblance, not evidence that JVM implements Alex G.** `DECISION|MOGO|20260727|004` governs: JVM's
constants describe what MOGO built, not what anyone teaches.

What it does change is the **shape of the question**. Until now the library held prose rules and
MOGO held numbers, with no common form. Now there is one, so a comparison is at least well-posed:

| | **JVM (shipped)** | **ALEX_G (evidenced, source #4)** |
|---|---|---|
| Inputs | 7 named conditions | 3 timeframes (weekly, daily, 4H) |
| Weights | 25 / 20 / 20 / 15 / 15 / 10 / 10 | 10 each — **uniform** |
| Threshold | 55 | "minimum of two … in sync" ⇒ 20 |
| Maximum | 115 | **unstated** — see the blocking open question below |

**Three things stop this from being actionable, and all three are in the source itself.**

1. **The maximum is unknown.** The caption is garbled — *"we were greatest a 20 towards yourself
   because it's 10 per time frame."* Four timeframes are named elsewhere (⇒ 40), but sub-4H is
   excluded from directional scoring in the same breath (⇒ 30). **MOGO must not pick one.** A
   threshold means nothing without its scale.
2. **The weights are uniform, so the score is just a count.** With 10 points each, "score ≥ 20" and
   "at least two agree" are the same rule. There is no evidence Alex G weights timeframes
   differently — despite claiming elsewhere that higher timeframes are stronger
   (`CLAIM|ALEX_G|20260727|007`, `|008`). That is a latent inconsistency, recorded, not resolved.
3. **The demonstrated example contradicts the simple reading.** Weekly bearish, daily **bullish**,
   4H bearish — and he trades bearish. So "two in sync" tolerates a disagreeing timeframe *between*
   two agreeing ones, and the opposing daily costs nothing. Whether it should is never stated.

→ `RC-22` tests the gate itself. Until it runs and the scale is resolved, **nothing here may be
ported into JVM or any MOGO engine** — that would be inventing the missing denominator.

---

## 3d. Where the two educators now stand on entry location

Source #4 supplies TJR's missing layer in a form precise enough to compare directly.

| | **TJR** | **ALEX_G (source #4)** |
|---|---|---|
| What must be true before looking for entry | A liquidity sweep has occurred | ≥2 timeframes aligned |
| Where entry is allowed | At the swept level, after confirmation | **Only at a lower high (sell) or higher low (buy)**, inside the LH/LL box |
| What disqualifies the whole setup | Sweep never happens | Price leaving the box — bias flips |
| Where the zone comes from | Prior session highs/lows, draws on liquidity | Most-touched level inside the box, validated by looking left |

**They still do not contradict here — they stack.** Alex G's gate is a *pre-filter* on direction;
TJR's sweep is a *trigger* within it. Nothing in either source forbids the composition, and nothing
in either source endorses it. **Composing them would be MOGO's invention, and is not authorized.**

The sharpest new observation is Alex G's `CLAIM|ALEX_G|20260728|042`: a level can be a genuine,
well-respected support/resistance and still be untradeable, because price reaching it would already
have invalidated the bias. **TJR has no equivalent guard.** TJR's draws on liquidity are selected by
session position, with no stated rule that invalidates a target for being on the wrong side of a
structural break. That is a real asymmetry and a candidate gap on TJR's side — recorded as such,
not as a TJR error.

---

## 3e. Alex G's method is now complete except for the stop

Source #5 supplies the two layers that had been named-but-undefined since source #2. Laid end to
end, the evidenced chain is:

| Layer | Rule | Source | Status |
|---|---|---|---|
| Direction | ≥2 of weekly/daily/4H aligned, 10 pts each | #4 | ⚠️ scale maximum unknown |
| Zone | Most-touched level **inside** the LH/LL box | #4 | ✅ stated |
| Trigger | Rejection/doji or engulfing, **closed**, at the level, pro-trend | #5 | ✅ stated precisely |
| Timing | Wait for the session; enter Mon/Tue/Wed | #5 | ⚠️ session hours shown on screen, never spoken |
| Target | ~80–100 pips (an average, not a rule) | #5 | ⚠️ descriptive |
| **Stop** | — | — | ❌ **absent from five sources** |
| **Risk per trade** | — | — | ❌ **absent from five sources** |

**The absence is no longer plausibly an oversight, and it is no longer merely an absence.** This
source names *risk-to-reward* as an input to a live decision (`CLAIM|ALEX_G|20260728|072`), refers to
"where my stop loss would have been", "more breathing room", "better stop-loss" — and never states
how the stop is placed. A method that reasons about risk-to-reward while never defining the risk
leg is **structurally incomplete at exactly the point where profitability is decided.**

Consequence for MOGO, stated plainly: **no Alex G claim can ever be replayed for P&L.** Every replay
candidate derived from his material — RC-12 through RC-26 — measures trigger accuracy, reach-rate or
directional outcome. None can produce an expectancy. That is a permanent property of the source
material, not a limitation of the replay harness.

### Where the session rule leaves the long-standing gap

The `higher_timeframe_bias` gap on TJR's side and the "right times" gap on Alex G's side have been
open since sources #1 and #2. This source **downgrades but does not close** the second one:

- ✅ Session timing is now a **prescriptive rule with a stated rationale** (target distance needs
  volume hours), not a passing mention.
- ✅ The day-of-week filter is precise and falsifiable: Monday, Tuesday, Wednesday.
- ❌ **The session windows themselves are shown as coloured bands on an on-screen map and never
  spoken.** Sydney, London and New York are named; no hours are given.

**MOGO must not supply the hours.** TJR's sessions are evidenced for TJR, on US indices; importing
them into an FX method would be inventing a rule and attributing it to Alex G.

---

## 3f. The risk-management source, and the gap it did not close

Source #6 is entirely about risk management. It moved `ALEX_G` from **0 to 13 `risk_rule` claims** in
one ingestion — the largest single-cycle change in any rule category the library has seen.

**What it supplies:**

| | |
|---|---|
| Sizing basis | A percentage of deposited account balance, never a dollar amount |
| Bands | Conservative **0.5–1%** (lower-timeframe traders, 1–3 trades/day) · Standard **1–2%** · High **3–5%** |
| Selection | By account type — personal, funded, or disposable |
| Stability | The same percentage on every trade; one percentage chosen per month and held regardless of streaks |
| Seasonal override | 3–5% only in November–March; reduced through June–August |
| Stated purpose | A stable P&L curve is what lets capital allocators fund a trader |

**What it does not supply, and this is the point:** `stop_rule` remains at **zero across six
sources.**

Risk sizing tells you *how much* to lose. Stop placement tells you *where*. **Position size = risk
amount ÷ stop distance**, and the second term is still missing. A trader following this source
knows to risk 1% and has no rule for converting that into a lot size.

### The inference MOGO must not make

Source #5 gives an average take-profit of 80–100 pips. Source #6 uses 1:2 and 1:3 ratios in worked
examples. Together those would imply a stop of roughly 27–50 pips.

**MOGO must not perform that inference.** Both ratios appear only as illustrative arithmetic inside
an argument about escalating risk after a winning streak — neither is stated as a required ratio.
The 80–100 pip figure was given as a *past average*, not a target-selection rule. Combining two
descriptive statements from two different sources into a prescriptive third would be inventing a
rule and attributing it to an educator who did not state it. Recorded as a `high`-priority open
question so the temptation is on the record rather than acted on.

### What actually changed for replay

**Nothing, for P&L.** RC-12 through RC-27 still measure trigger accuracy, reach-rate, frequency or
direction. Not one can produce an expectancy. A standing note now sits at the top of
`REPLAY-CANDIDATES.md` saying so, because a reader seeing 13 risk rules could reasonably assume
otherwise.

**One new candidate, though — RC-27.** The seasonal rule is the only claim in the library that
*changes position size*, it rests entirely on an unshown personal observation, and it is testable
**without** the missing stop rule: count setup frequency and directional outcome by calendar month,
controlled against unconditional monthly volatility.

---

## 3g. The live session — what he does that he does not teach

Source #7 is the first **live trading session** in the library: a recorded 6 a.m. call with ~70
attendees, walking four pairs. The evidence type is predominantly `demonstrated_behavior` rather
than `rule_statement`, which makes it the first material capable of testing taught rules against
practice.

**It largely corroborates the taught method** — pro-trend only (*"never, bro, not anymore… that's a
rookie thing"*), wait for the break of structure, higher low plus bullish engulfing, prior
support/resistance zones, round psychological levels, EMA retest, alarms on levels. All
same-educator, so none of it raises confidence.

**But three filters appear that no instructional source states:**

| Filter | What it does | Where it appears |
|---|---|---|
| **Proximity tolerance** | A setup declined because price came **~10 pips short** of the level | Only here |
| **Confluence counting** | Direction chosen by counting confluences on *each* side and taking the larger | Only here |
| **"Worth the risk" selectivity** | Trades taken only when judged worth the capital; month-to-date performance is an input | Only here |

### Why this matters more than a normal source

The taught rule for a level is **binary**: the confirmation must be *at* a support or resistance, and
away from one the rule is *"simply not applicable"* (`CLAIM|ALEX_G|20260728|068`, `|069`). Live, it
operates as **graded** — 10 pips short was too far, on a pair where 10 pips is small relative to
daily range. `XCONTRA|20260728|008`.

The consequence generalises past this one filter:

> **If a taught rule set systematically omits the discretionary filters its author actually uses,
> then replaying the taught rules measures something the educator does not trade.**

That is a caution on every Alex G replay candidate, and it is the first time the library has had the
evidence to state it. It is not an accusation of bad faith — these filters are the kind of judgement
that is genuinely hard to articulate. It does mean a replay result should be read as a test of *the
stated method*, not of *his trading*.

`RC-28` tests the first and cheapest of the three by measuring the tolerance curve rather than
assuming a threshold.

### Two smaller findings worth keeping

**The EMA finally has a role, and still has no period.** Sources #5 and #7 both use it as a
load-bearing confluence; #7 adds that it is support while bullish and resistance while bearish, and
that the preferred entry is where the EMA and prior structure converge. The parameter is still
missing, so it remains non-reproducible.

**A third visual-only artifact.** The written confluence list — which *is* the direction rule — is
displayed on screen, offered for screenshotting, and never read aloud. After the session volume map
(#5) and the setup grading scale (#4), a pattern is now visible: **the parameters of this educator's
rules are consistently shown rather than said.** For a transcript-based pipeline that is a
systematic blind spot, not a run of bad luck.

**And one candid admission**, recorded because the library holds several set-and-forget claims and
this is the first evidence of the failure mode: a setup he had identified in advance, with alarms
set, was missed — *"I forgot what I was doing and I wasn't able to get this."*

---

## 3h. The psychology source — and the exit rule it implies but never states

Source #8 contains **no setup, entry, structure or exit rule**. It is the first source in the library
with zero technical content, and it is extracted as psychology and personal finance rather than
method.

Its central claim is nonetheless the most operationally relevant thing said about **trade management**
in eight sources:

> A trade set to a **1:4** target is closed at **1:2** because the unrealised dollar figure equals
> what the trader normally earns in a month. *"You are now taking and closing a trade off of impulse
> emotion to the dollar amount."*

That is the first time any Alex G source has named a **specific exit failure mode**, and it implies
a rule — *a target set in advance should be allowed to run* — that has never been stated as one. It
sits alongside the `set and forget` framing without either being reconciled to the other.

**The gap it leaves open is exact and worth naming.** The source rules out cutting a target for an
**emotional** reason. It says nothing about cutting for a **market** reason — opposing structure, a
session ending, a counter-signal. Any trade-management rule MOGO ever derives needs that distinction,
and no source draws it.

### Where this fits the ALEX_G picture at ten sources

| Layer | Status after 8 ALEX_G sources |
|---|---|
| Direction | ✅ stated, quantified (⚠️ scale maximum unknown) |
| Zone | ✅ stated |
| Trigger | ✅ stated precisely |
| Timing | ✅ stated (⚠️ session hours shown, never spoken) |
| Target distance | ⚠️ a past average, not a selection rule |
| **Exit management** | ⚠️ **one failure mode named; no positive rule** |
| Risk sizing | ✅ 13 rules, three bands |
| **Stop placement** | ❌ **absent from all eight** |

**The shape has not changed since cycle 012, and eight sources is now enough to call it.** This
educator's published material is dense on *identification* and silent on *the risk leg*. Two further
sources — a live session and a psychology podcast — did not alter that, which is itself the finding.

### One thing worth flagging that is not trading knowledge

The same source presents a **$650–700 evaluation fee as convertible into a 100K funded account** and
thence into $5,000 from a single 1:2 trade, naming a specific provider — with **no pass rate, no
mention that the fee is lost on breach, and no reference to the daily-loss and drawdown rules that
source #6 said constrain risk banding.** The failure branch is simply absent.

MOGO records this as a `performance_hypothesis` blocked `critical`, and notes it here because the
library now holds **eight** unevidenced monetary claims from this channel. That density is itself a
source-quality signal, and it belongs in the acquisition weighting rather than being tallied claim
by claim.

---

## 3i. The third educator — what changed, and what pointedly did not

`RAYNER_TEO` (verified: Rayner Teo, `@tradingwithrayner`, Singapore) is a genuinely independent
educator: different channel, country and teaching style. One source, 46 claims.

### What changed: the library finally has a complete method

| Layer | ALEX_G (8 sources) | TJR (2 sources) | **RAYNER_TEO (1 source)** |
|---|---|---|---|
| Structure | ✅ HH/HL, body-close | ✅ HH/HL, wick-based | ✅ HH/HL, **major swings only** |
| Direction gate | ≥2 timeframes aligned | ❌ absent | ✅ trend = path of least resistance |
| Zone | ✅ most-touched, in the box | ✅ draws on liquidity | ✅ S/R **or** moving average |
| Trigger | ✅ closed rejection/engulfing | ✅ 1m confirmation | ✅ closed reversal candle |
| Session | ⚠️ hours shown, never spoken | ✅ pre-market / NY | ✅ **stated in GMT** |
| **Stop** | ❌ **absent from all 8** | swing-based, unquantified | ✅ **low of support − 1 ATR(20, SMA)** |
| **Size** | 0.5–1 / 1–2 / 3–5% bands | ❌ absent | ✅ **risk ÷ (stop × pip value)**, 1% |
| **Target** | ~80–100 pips (an average) | prior draws, ladder undefined | ✅ **just before the opposing swing** |

**Every leg is present in one source.** That is what makes `RC-30` the first replay candidate in the
library that can produce an **expectancy** rather than a hit-rate — the quantity eleven sources have
never once permitted MOGO to compute.

Three things about the stop rule are worth stating precisely, because they are what make it usable:
it is placed **where the trade's premise is falsified** (below the support the setup relies on); it
is set **objectively** at one 20-period ATR beyond that low; and it is **deliberately not flush**,
on the stated reasoning that price routinely spikes just past a level before continuing.

⚠️ **This is evidenced for RAYNER_TEO only, and must not be borrowed.** Eight ALEX_G sources state no
stop at all. Filling his gap with Rayner's rule would fabricate a rule and attribute it to someone
who never stated it — the same prohibition already recorded for the 80–100 pip / 1:2 inference.

### What did not change: **confidence, at all**

**All 310 claims remain `emerging`. The maximum score in the library is still 25.62 against a 45.0
threshold. Not one claim moved.**

This is worth dwelling on, because it was the point of recommendation R3. Rayner states the trend
definition in almost the same words as ALEX_G and TJR — three independent educators, the same
claim — and the library counts it as **three separate claims with one evidence item each**, because
`compute_claim_fingerprint()` includes `traderId`.

> **R3 has now been executed, and it did not do what R3 was for.** The blocker was never the number
> of educators. It is that trader-scoped fingerprints prevent cross-educator agreement from ever
> being counted — which is precisely the **D2** decision that has been open since §6. This cycle
> converts D2 from a design question into a demonstrated blocker.

### The disagreements a third voice makes visible

**`XCONTRA|20260729|001` · CONDITIONAL_SCOPE · material — which highs and lows count?**

| | |
|---|---|
| ALEX_G | A body close beyond a structure level counts **regardless of size** — no minimum threshold |
| RAYNER_TEO | Use **only major swing points**; deliberately ignore minor highs and lows or you lose the bigger picture |

Alex G's detector is maximally sensitive by design; Rayner's is deliberately filtered. **Same
operation, opposite instruction** — and it lands on the single most load-bearing undefined parameter
in the library, the one already gating RC-12, RC-13 and RC-19 through RC-16. → `RC-29`.

**`XCONTRA|20260729|002` · DEFINITIONAL · minor — why price spikes past a level.** The library now
holds **three positions** on the same phenomenon: TJR says market makers do it deliberately to fill
against retail stops; ALEX_G calls that explanation *"almost a big hoax"*; **RAYNER_TEO makes no
mechanism claim at all** and simply buffers the stop by one ATR.

Filed `minor` because declining to explain something does not logically contradict explaining it.
Recorded because it is the **only one of the three that yields a usable parameter** — Rayner sidesteps
a question the other two argue about, and gets a number out of it.

### Where three educators now agree

Agreement still raises no confidence, but it is worth recording what survives three independent
statements:

| Concept | TJR | ALEX_G | RAYNER_TEO |
|---|---|---|---|
| Trend = HH/HL and LH/LL | ✅ | ✅ | ✅ |
| A **close**, not a touch, matters | ✅ | ✅ | ✅ |
| Prior levels anchor the setup | ✅ | ✅ | ✅ |
| Trade with the trend | — | ✅ | ✅ |
| Engulfing candles as entry triggers | ✅ | ✅ | ✅ |
| ~1% risk per trade | — | ✅ (0.5–2%) | ✅ (1%) |

**Six concepts now asserted by three independent educators**, and the review template names exactly
that as "the closest thing to a validated trading principle the library can produce without replay."
It is currently invisible to the confidence engine.

### A source-quality observation worth recording

This source makes **no income claims whatsoever** — the first in eleven sources. It also
**deliberately shows a losing trade** ("this is a trade I took and it happened to me"), explicitly
admits the other examples are cherry-picked, and concedes that structure classification is
subjective and two traders may legitimately disagree.

Against a channel that produced eight unevidenced monetary claims, that difference is large enough
to belong in acquisition weighting rather than in a footnote.

---

## 4. Contradictions

**C-5 — `XCONTRA|20260728|008` · CONDITIONAL_SCOPE · material · BEHAVIOUR vs STATED RULE** *(recorded, open)*

| | |
|---|---|
| Taught (sources #3–#6) | The confirmation must be **at** a support/resistance. Away from one, *"you don't enter the trade and it is simply not applicable"* |
| Demonstrated (source #7) | A setup declined because price came **~10 pips short** of 86.000 — *"I wasn't really that convinced because we were shy about, let's say, like 10 pips"* |

The taught rule is binary; the demonstrated behaviour is graded. **No source in the library supplies
a tolerance, a maximum acceptable distance, or any rule for near-misses.**

This is the library's first contradiction between *what an educator teaches* and *what he is
recorded doing* — a category distinct from the within-source and cross-educator conflicts already
held. It is also the least adversarial: the filter is real and useful, and simply never articulated.
→ `RC-28`, which measures the tolerance curve rather than inventing a threshold.

---

**C-3 — `XCONTRA|20260728|006` · SCOPE_MISMATCH · material · WITHIN-SOURCE (ALEX_G #6)** *(recorded, open)*

Three figures from one video, which cannot describe the same trading operation:

| | |
|---|---|
| Opening | *"I make anywhere from $50 to $100,000 every single day"* |
| Body | *"8 to 10% a month … anybody can do that"*, and 50% a day/week/month is *"not going to happen"* |
| Flagship evidence | A **100K** funded account returning 27–28% over ~39 days for a **$28,000** payout |

At 8–10% per month, $50–100k per **day** implies an account in the tens of millions. The evidence
offered is a six-figure funded account. **The video's benchmark for realism and the video's opening
claim are inconsistent by roughly two orders of magnitude.**

A reconciliation is imaginable — the daily figure might be gross position movement, or refer to
accounts not described. **The source never says so.** Supplying it would be MOGO's reconciliation,
not the educator's.

This is worth its own entry rather than filing under "unsupported performance claims" because the
inconsistency is **internal and arithmetic**: it needs no external data to detect, only the source's
own numbers.

**C-4 — `XCONTRA|20260728|007` · TEMPORAL_DRIFT · minor · WITHIN-SOURCE (ALEX_G #6)** *(recorded, open)*

Four durations for one career in one video: 2½ years before making any money · profitable for about
6 years · predicting markets for about 5 years · 5½ years to work out the seasonal pattern.

Filed **minor** deliberately — casual speech rounds numbers, and inflating this would cheapen the
`material` severity. It is recorded because every performance claim in the source is anchored to
experience length, and no two of the four figures reconcile without assumptions the source does not
supply.

---

**C-1 — `XCONTRA|20260728|005` · DIRECTIONAL · material · WITHIN-SOURCE (ALEX_G #5)** *(recorded, open)*

The video's thesis, stated in the opening, repeated at 1:06, and restated in the summary:
*"entering off of a confirmation, not an anticipation."* At 6:37, in the same video:
*"that perfect higher low is where you can then **anticipate** that wick fill."*

**This is the fourth record of the same inconsistency in Alex G's material** — after
`|20260728|033` (conceding he enters on anticipation while teaching against it), `|036` (labelling an
incomplete structure point during the directional read) and `|047` / `XCONTRA|20260728|003` (the
"potential lower high"). It is the first that is **internal to a source whose entire subject is the
rule being broken.**

A reconciliation is available — that he anticipates the *setup* while still requiring a closed candle
to *enter* — and it is coherent. **He never states it.** Adopting it would be MOGO resolving a
contradiction on the educator's behalf, which `DECISION|MOGO|20260727|003` forbids. → `RC-24`.

**C-2 — `XCONTRA|20260728|004` · CONDITIONAL_SCOPE · material · WITHIN-SOURCE (ALEX_G #5)** *(recorded, open)*

At 16:56: waiting for the session sometimes loses the trade entirely — *"the trade is completely gone
from the direction, gone from the area where I was interested in taking."*
At 18:51: *"The way that I look at it is that there's no negative"* — followed by an enumeration of
three outcomes: worse entry but right direction, the loss you would have taken anyway, better entry.

**The forfeited-trade case he described himself two minutes earlier is absent from the enumeration.**
The "no negative" claim is not wrong about the three cases it lists; it is incomplete, and the
missing case is the only one with an unbounded cost. This is the cleanest example in the library of
a plausible-sounding claim contradicted by the source's own evidence → `RC-26`.

---

**C0 — `XCONTRA|20260728|003` · DIRECTIONAL · material · WITHIN-EDUCATOR (ALEX_G)** *(recorded, open)*

| | |
|---|---|
| Source #3 (liquidity) | *"Entry requires a confirmation that price is already moving in the intended direction"* — anticipation explicitly rejected (`CLAIM\|ALEX_G\|20260728\|028`) |
| Source #4 (this one) | *"you need to sell at a lower high **or a potential lower high**"* (`CLAIM\|ALEX_G\|20260728\|047`) |

A "potential" lower high is by definition one that has not completed. Selling into it *is* entering
on anticipation. The two prescriptions are opposite for the same decision.

This is the **third** record of the same inconsistency in Alex G's material: `|20260728|033` already
captures him conceding he enters on anticipation while teaching against it, and `|20260728|036`
records him labelling an incomplete structure point during the directional read. **A pattern across
three sources is no longer a slip.** It is recorded, not resolved — the sources may be separated in
time, but neither states that, and inferring it would be MOGO's reconciliation rather than the
educator's. → `RC-24`.

---

**C1 — `XCONTRA|20260727|003` · DEFINITIONAL · material · CROSS-EDUCATOR** *(recorded, open)*

| | |
|---|---|
| ALEX_G | *"I base my highs and lows to the bodies of the candlesticks"* — and demonstrates *"placing it at the body of that candlestick, not at the wick"* |
| TJR | *"We take the highest point of those two candlesticks"* — the wick |

**The library's first cross-educator contradiction.** Both describe the same operation — locating a
structure point — and prescribe incompatible price levels. Everything downstream moves with it:
where the level sits, whether a break has occurred, stop placement, risk-to-reward.

This is also the **most cleanly testable disagreement in the library**: the same price data, marked
both ways, produces measurably different break counts and different trend labels. See
`REPLAY-CANDIDATES.md` RC-10.

**C2 — Candlestick patterns as signal.** Not a formal contradiction (no shared claim), but a
three-way split worth naming:

| | Position |
|---|---|
| **TJR** | **Removed** pattern confluences six months ago; reports his best year without them (`\|038`) |
| **ALEX_G** | Patterns **are the entry trigger** — dojis and engulfing candles |
| **JVM** | Prices `wick` 15 + `engulf` 20 = **35 of a 55 threshold** |

Two of three treat candlestick patterns as primary; one deliberately discarded them. This sharpens
`RC-02` from a TJR-only question into a genuine cross-strategy one.

---

## 5. New concepts contributed by ALEX_G

Concepts with no prior analogue in the library:

| Concept | Note |
|---|---|
| **Top-down analysis** as a named, ordered procedure | Weekly → daily → 4h → LTF, each scored bullish/bearish |
| **Timeframe hierarchy with precedence** | HTF overrides LTF on conflict; below 15m not a "strong" timeframe |
| **Structure re-anchoring** | Every new HH forces a new HL; every new LL forces a new LH |
| **Area of interest must sit inside HH/HL** | With a stated failure mode for placing it outside |
| **AOI confluence by timeframe overlap** | Weekly + daily overlap = "two areas of interest strong" |
| **Sequencing rule** | The HH always leads; the paired HL is always behind it, never ahead |
| **Counter-trend retracement is expected** | The LTF *must* go against you to deliver price to the zone |

**Reinforced (already present, now independently restated):** trend definitions, close-not-touch,
direction-is-not-entry, prior levels anchor setups.

---

## 6. Why none of this raised confidence — and the design question it forces

**All 104 claims remain `emerging`.** A1 is two independent educators stating the same definition in
almost the same words, and it moved nothing.

The reason is deliberate: `compute_claim_fingerprint()` includes `traderId`, so "an uptrend is HH+HL"
scoped to TJR and the same sentence scoped to ALEX_G are **two different claims by construction**.
Trader-scoped claims never merge, which is correct — a claim about TJR's method should not silently
absorb someone else's evidence.

But it means **cross-educator agreement currently has no path to raise confidence at all.** The only
routes are same-trader corroboration or replay.

**This is now a live design question rather than a hypothetical.** `PROPOSAL-003` §4 asked whether
concepts should mediate confidence and recommended *no*, on the grounds that it would make
confidence depend on an editorial mapping. A1 is the concrete case that argues the other way: when
two independent educators define a term identically, something should register.

**Recommendation — a new `Concept`-level confidence, not a change to claim confidence.** Keep claim
confidence exactly as it is (evidence-derived, trader-scoped, unmergeable), and let the Concept
Registry carry a separate, clearly-labelled *consensus* count: "3 independent educators assert this".
That answers the multi-trader question without weakening the property POLICY-001 depends on.
**This is an owner decision — see §8.**

---

## 7. Implementation candidates arising

| Candidate | Note |
|---|---|
| **ALEX_G's method is FX-native** | Unlike TJR (indices), it needs no instrument abstraction — MOGO's pip-based risk model already fits. It is the **first ingested method expressible in MOGO's current engine.** |
| **Top-down bias ≈ JVM `bias3`+`bias2`** | JVM's dominant input (40 of 55) is multi-timeframe bias. ALEX_G's method is a *rule-based* version of the same idea. A comparison is possible on data MOGO already has. |
| **Body-vs-wick structure marking** | A single parameter with a measurable effect. Cheapest real experiment in the library (RC-10). |
| **ALEX_G engine vs Alex G's teaching** | MOGO's `SF\|ALEX_G\|SUPPORT_RESISTANCE_V1` does Break & Retest / Repeated Zone Reaction. The ingested material teaches top-down bias + AOI + rejection entry. **These are not obviously the same method** — see §8. |

---

## 8. OWNER DECISIONS REQUIRED

### D1 — Does MOGO's ALEX_G engine match what Alex G teaches?

**Problem.** MOGO runs a live paper-trading engine attributed to Alex G. The first ingested Alex G
material teaches top-down timeframe bias, areas of interest inside structure, and rejection-candle
entries. The shipped engine implements zone detection with Break & Retest and Repeated Zone Reaction
setups. **Nothing establishes that these are the same method**, and one source is not enough to
conclude they differ.

*Options:* (1) acquire more Alex G material and compare properly; (2) audit the engine against the
35 claims now on record; (3) accept the engine as MOGO-original and rename it to stop implying
attribution.

**Recommendation: (1) then (2).** One source cannot settle it, and renaming on thin evidence would
be as wrong as leaving it. *Risk of doing nothing:* MOGO trades a strategy under a name it has not
verified. *ROI:* high — this is a correctness question about live paper-trading behaviour.

### D2 — Should cross-educator consensus be counted? (see §6)

*Options:* (1) leave it — cross-educator agreement stays a documentation-level observation;
(2) add Concept-level consensus counting (recommended, §6); (3) let concepts mediate claim
confidence (rejected in PROPOSAL-003 §4 and still rejected — it would make confidence depend on an
editorial judgment).

**Recommendation: (2), built with the Concept Registry at source #3.** *ROI:* this is the mechanism
by which a multi-educator library becomes more than a pile of separate ones.

---

## 9. Terminology map (feeds `PROPOSAL-003`)

| Concept | TJR | ALEX_G | JVM | ALEX_G engine |
|---|---|---|---|---|
| Prior significant level | draw on liquidity | area of interest | `aoi` | zone |
| Structure break | break of structure (BOS) | break of HH / HL | `msb` | zone break |
| Trend | uptrend / downtrend | bullish / bearish market | multi-TF bias | — |
| Entry trigger | 1m confirmation confluence | rejection candle (doji / engulfing) | `wick`, `engulf` | retest |
| Structure point marked at | wick | body | — | — |

Five names for "prior significant level" across four systems. This table is the standing argument
for `PROPOSAL-003`.

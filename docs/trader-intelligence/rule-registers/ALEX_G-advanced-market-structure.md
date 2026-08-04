# Rule Register — Alex G, "Advanced Market Structure"

**Source:** `EVSRC|ALEX_G|20260728|001` · `https://www.youtube.com/watch?v=sZAE_lqdeno`
**Title:** *Advanced Market Structure* — **PROVISIONAL, unverified** (derived from the transcript,
which names itself *"the advanced Market structure video"* twice; the published YouTube title string
has not been verified — no network access).
**Intake:** `INTAKE|ALEX_G|20260728|001` · SHA-256 `f48d9c1c…08a6db` · 22,106 bytes · ~20:43

> **Every rule below is at `emerging` confidence and is NOT a production rule.** Zero rule
> candidates exist. Per `DECISION|MOGO|20260727|006`, this source restating Alex G source #1 is
> **not** independent confirmation.

**Legend — Status:** Explicit (stated) · Implied (shown as reasoning) · Inferred (concluded by MOGO).
**Nature:** Objective (mechanically checkable) · Discretionary (needs human judgement).

---

## A. Market-structure definitions

### A1 — Bullish structure requires a higher high and a higher low
- **Exact rule:** *"if a market is bullish a market is consisted of higher highs and higher lows it is impossible"*
- **Timestamp:** 1:48 · **Claim:** `CLAIM|ALEX_G|20260727|012` (restated, not new)
- **Status:** Explicit · **Nature:** Objective
- **Required variables:** swing high series, swing low series
- **Missing definitions:** none for the definition itself; depends on A5/C1 for how points are placed
- **Algorithmic representation:** `bullish ⇔ HH[n] > HH[n-1] ∧ HL[n] > HL[n-1]`
- **Replay feasibility:** ✅ high — deterministic once structure points are placed
- **Supporting:** Alex G #1 (`|012`); **same-educator restatement, adds no independence**
- **Independent cross-source:** TJR `CLAIM|TJR|20260727|067` states the same definition — **but
  trader-scoped claims never merge, so this does not raise confidence** (see §Confidence note)
- **Contradicting:** none
- **Confidence:** `emerging` (23.5)

### A2 — Bearish structure requires a lower low and a lower high
- **Exact rule:** *"since this has now created a new lower low this becomes the new lower low and you must need a new lower high"*
- **Timestamp:** 7:42 · **Claim:** `CLAIM|ALEX_G|20260728|002` (new — the reassignment half)
- **Status:** Explicit · **Nature:** Objective
- **Algorithmic representation:** `bearish ⇔ LL[n] < LL[n-1] ∧ LH[n] < LH[n-1]`
- **Replay feasibility:** ✅ high · **Confidence:** `emerging`

### A3 — Trend is determined by structure, not visual slope
- **Exact rule:** *"the trend is identified by the market structure without Market structure you cannot identify the trend"*
- **Timestamp:** 7:19 · **Claim:** `CLAIM|ALEX_G|20260728|004`
- **Status:** Explicit · **Nature:** Objective (as a definition of "trend")
- **Missing definitions:** none — but note this is **definitional, not empirical**: it defines trend
  as structure rather than demonstrating that structure predicts anything
- **Replay feasibility:** ⚠️ not directly testable — it is a definition. What *is* testable is the
  paired failure claim A4
- **Confidence:** `emerging`

### A4 — Judging trend from visual slope is a primary error
- **Exact rule:** *"they see the overall movement heading up… they think a market is bullish… and that cannot be further from the truth"*
- **Timestamp:** 5:35 · **Claim:** `CLAIM|ALEX_G|20260728|005` · `failure_condition`
- **Status:** Explicit · **Nature:** Objective (comparable via a slope-based baseline)
- **Algorithmic representation:** compare structure label vs sign of a linear fit / EMA slope; measure disagreement rate and forward outcome
- **Replay feasibility:** ✅ high → **RC-14**
- **Confidence:** `emerging`

### A5 — Structure exists inside consolidation and ranging conditions
- **Exact rule:** *"sure it could be an a ranging Market but inside of a ranging Market there is Market structure"*
- **Timestamp:** 9:38 · **Claim:** `CLAIM|ALEX_G|20260728|006`
- **Status:** Explicit · **Nature:** Objective
- **Missing definitions:** ⚠️ **no lower bound.** Combined with B5 (any size counts), structure is
  claimed to be identifiable at arbitrarily small scales with no minimum range width
- **Replay feasibility:** ✅ → **RC-15**
- **Confidence:** `emerging`

### A6 — The active higher low is the *last* higher low, not the lowest
- **Exact rule:** *"the last higher low is the last higher low not the highest low or the most low low"*
- **Timestamp:** 2:10 · **Claim:** `CLAIM|ALEX_G|20260728|003`
- **Status:** Explicit · **Nature:** Objective · **Replay feasibility:** ✅
- **Note:** disambiguates a real failure mode; pairs with Alex G #1's "the HH is always in front"
- **Confidence:** `emerging`

---

## B. Structure-shift rules

### B1 — A bullish market shifts bearish only on a body close below the active higher low
- **Exact rule:** *"the market will remain bullish as long as we stay in between this higher high and higher low the moment we body close above or under this line is when we will have a shift in the market"*
- **Timestamp:** 2:35 · **Claim:** `CLAIM|ALEX_G|20260727|022` (restated)
- **Status:** Explicit · **Nature:** Objective
- **Required variables:** candle open/close, active HL level
- **Algorithmic representation:** `shift ⇔ close[t] < HL_active` (body close, not low)
- **Replay feasibility:** ✅ **highest in the register** → **RC-12**
- **Contradicting:** ⚠️ TJR marks structure at wicks (`XCONTRA|20260727|003`), which changes where
  `HL_active` sits and therefore when this fires
- **Confidence:** `emerging` (23.5)

### B2 — A bearish market shifts bullish only on a body close above the active lower high
- **Exact rule:** *"the moment the body Candlestick closes above we have now shifted and now this is a new higher high"*
- **Timestamp:** 8:58 · Mirror of B1 · **Status:** Explicit · **Nature:** Objective
- **Replay feasibility:** ✅ → **RC-12** · **Confidence:** `emerging`

### B3 — Wicks alone do not confirm a shift
- **Exact rule:** *"the Wicks are just the trail of where the market went but it's not the actual Market"*
- **Timestamp:** 4:46 · **Claim:** `CLAIM|ALEX_G|20260727|020` (restated)
- **Status:** Explicit · **Nature:** Objective
- **Replay feasibility:** ✅ → **RC-13** (wick-break vs body-close comparison)
- **Contradicting:** ⚠️ **`XCONTRA|20260727|003` — cross-educator, material.** TJR places structure
  at wick extremes
- **Confidence:** `emerging` (24.8)

### B4 — A new higher high forces reassignment of the active higher low (and mirror)
- **Exact rule:** *"the moment we body close above we have then created a new higher high and we must have a new higher low"*
- **Timestamp:** 5:05 · **Claim:** `CLAIM|ALEX_G|20260727|016` (restated) + `|20260728|002` (mirror)
- **Status:** Explicit · **Nature:** ⚠️ **Discretionary in practice** — the *rule* is objective but
  the reassignment *target* is found by the snake trick (C3), which is not defined quantitatively
- **Missing definitions:** which turn qualifies; pivot strength; lookback
- **Replay feasibility:** ⚠️ **conditional** — only after a pivot definition is chosen → **RC-16**
- **Confidence:** `emerging` (25.0 — the highest score in the library)

### B5 — Any body close counts as a shift, regardless of size
- **Exact rule:** *"yes something as small as that counts as a shift of structure because the market simply did shift structure"*
- **Timestamp:** 11:08 · **Claim:** `CLAIM|ALEX_G|20260728|008`
- **Status:** Explicit · **Nature:** Objective
- **Missing definitions:** ⚠️ **This explicitly rules OUT a minimum displacement threshold** — which
  answers one question and opens another: **false breaks, noise and immediate reversals are never
  addressed.** No ATR filter, no confirmation bar, no re-entry rule
- **Replay feasibility:** ✅ → **RC-17** (sensitivity to a minimum-break threshold the source denies)
- **Confidence:** `emerging`
- **Assessment:** the single most consequential rule here. It makes the system fully mechanical *and*
  maximally noise-sensitive at the same time

### B6 — Price may move freely between the active levels
- **Exact rule:** *"this Market can do absolutely whatever it wants inside of here as long as we don't body Candlestick close above or below"*
- **Timestamp:** 8:21 · **Claim:** `CLAIM|ALEX_G|20260728|007` · Explicit · Objective
- **Replay feasibility:** ✅ · **Confidence:** `emerging`

---

## C. Structure-point placement

### C1 — Structure points are placed at candle bodies, not wick extremes
- **Exact rule:** *"higher highs and higher lows are placed at the bodies of the candlestick because this is where the market structure is"*
- **Timestamp:** 4:27 · **Status:** Explicit · **Nature:** Objective
- **Algorithmic representation:** `level = max(open, close)` for a high, `min(open, close)` for a low
- **Replay feasibility:** ✅ → **RC-13** · **Contradicting:** `XCONTRA|20260727|003` (TJR: wicks)
- **Confidence:** `emerging`

### C2 — The line chart is a visual aid for locating body-based structure
- **Exact rule:** *"if I were to come into here and I would erase the candlesticks and go to the line chart you can see that the structure is at this higher low and at this higher high"*
- **Timestamp:** 4:33 · **Claim:** `CLAIM|ALEX_G|20260728|011`
- **Status:** Explicit · **Nature:** Objective (a close-only line chart *is* the body-close series)
- **Note:** this is internally consistent — a line chart plots closes, so it is the same data as
  body-based structure. Corroborates C1 rather than being a separate technique
- **Confidence:** `emerging`

### C3 — The "snake trick" — **is it formalizable?**
- **Exact rule:** *"I like using my snake trick where I simply get this body of the snake and at the moment that the snake has a sharp turn that is the most higher low"*
- **Timestamp:** 3:01 · **Claim:** `CLAIM|ALEX_G|20260728|009`
- **Status:** Explicit · **Nature:** ⚠️ **DISCRETIONARY**
- **Required variables:** leading extreme, price path, "sharp turn"
- **Missing definitions:** what magnitude of reversal constitutes a turn; minimum bars either side;
  minimum retracement depth; behaviour when several turns qualify
- **Potential algorithmic representation:** a fractal/pivot detector — *"the most recent swing point
  of strength k preceding the leading extreme"* — where `k` is a free parameter the source never
  supplies
- **Replay feasibility:** ⚠️ **only after choosing `k`.** The result is then sensitive to that choice
  → **RC-16** exists precisely to measure that sensitivity

> **VERDICT (requested explicitly): the snake trick is NOT currently objective enough to formalize.**
> It is a teachable heuristic, not a specification. It becomes formalizable the moment a pivot
> definition is supplied — but supplying one would be **MOGO inventing a missing definition**, which
> is forbidden. The honest path is RC-16: implement it under several candidate `k` values and report
> how much the structure labelling changes. If results are stable across `k`, the vagueness is
> harmless; if not, the whole method inherits that instability.

---

## D. Range and consolidation logic

| Question asked | What the source actually says |
|---|---|
| Structure shifts in narrow ranges? | ✅ Yes — worked through a full consolidation example (Quiz 1) |
| Are very small body closes valid shifts? | ✅ **Yes, explicitly** — *"something as small as that counts"* |
| Noise handling? | ❌ **Never addressed** |
| Minimum displacement? | ❌ **Explicitly none** |
| Pivot strength? | ❌ **Never defined** (the snake trick's gap) |
| False breaks? | ❌ **Never addressed** — no re-entry, confirmation or invalidation rule |

**Flagged ambiguity:** A5 + B5 together imply structure is identifiable at arbitrarily small scale
with no lower bound and no noise filter. That is internally consistent and mechanically
implementable, but it means the method's output on low timeframes or tight ranges will be dominated
by whatever pivot definition is chosen for C3 — a parameter the source does not provide.

---

## E. Execution implications

### E1 — Do not chase a newly formed extreme; prefer a retracement
- **Exact rule:** *"should I go and chase this market… or is the market at too much of a high price… and wait for a retracement"*
- **Timestamp:** 18:36 · **Claim:** `CLAIM|ALEX_G|20260728|012`
- **Status:** Explicit · **Nature:** ⚠️ **Discretionary** — no retracement depth, measurement or
  invalidation given
- **Replay feasibility:** ⚠️ partial — testable as *entry at extreme vs entry after an X% pullback*
  swept over X → **RC-18**
- **Confidence:** `emerging`

### E2 — Market structure is only 50% of the system
- **Exact rule:** *"Market structure is only 50% of the problem now how you do that together with top analysis entry signal and trading at the the right times is where you actually make the money"*
- **Timestamp:** 20:21 · **Claim:** `CLAIM|ALEX_G|20260728|014`
- **Status:** Explicit · **Nature:** Objective as a scoping statement
- **Value:** ⭐ **the most honest statement in either Alex G source** — it explicitly bounds what
  structure alone can do, and names three further requirements
- **Missing definitions:** *"trading at the right times"* is named as a requirement and **never
  defined in either Alex G source**

### E3 — Timeframes inform stop-loss and take-profit sizing
- **Exact rule:** *"more details of it so we have a better understanding of how much more can this move go how long can we have on our stop-loss on a takeprofit"*
- **Timestamp:** 17:16 · **Claim:** `CLAIM|ALEX_G|20260728|013`
- **Status:** Implied · **Nature:** Discretionary
- **Missing definitions:** ❌ **This is the only statement about stops or targets in either Alex G
  source, and it specifies neither.** Two sources in, ALEX_G still has **zero** `stop_rule`,
  `target_rule` and `risk_rule` claims
- **Replay feasibility:** ❌ not testable as stated

**Stated relationship among entry / stop / take-profit / timeframe:** only that lower timeframes
give more "detail" for judging how far a move can run and how much room stop and target need. No
formula, ratio, or measurement. **Recorded as a gap, not a rule.**

---

## F. Evidence and unsupported claims

### F1 — The 60–75% accuracy claim ⚠️ **UNSUPPORTED**
- **Exact claim:** *"which the majority of the time is going to give you anywhere from a 60 to 75% accuracy on every single one of your trades"*
- **Timestamp:** 18:58 · **Claim:** `CLAIM|ALEX_G|20260728|015` · `performance_hypothesis`
- **Evidence quality:** `low` · **Confidence:** `emerging`
- **Missing:** sample size · date range · instrument · timeframe · trade log · definition of
  "accuracy" (win rate? direction? reaching the AOI?) · any verifiable record
- **Handling:** typed `performance_hypothesis` so it is **structurally ineligible** to become a rule
  candidate, and blocked at `critical` in the validation queue.
- ⚠️ **Must never be treated as evidence-backed.** Stated once, in passing, immediately before a
  promotional close.

### Content classification of the source

| Category | Examples |
|---|---|
| **Testable rule** | B1–B6, C1–C2, A1–A6 |
| **Discretionary technique** | C3 (snake trick), E1 (retracement) |
| **Educational explanation** | Hunter/tracks analogy, blood-pressure analogy (from source #1), elk analogy |
| **Trader preference** | Body-based marking framed as *"I don't want to get creative"* |
| **Promotional** | Closing pitch, cross-promotion of the top-down video, like/subscribe |
| **Unsupported performance** | F1 (60–75%) |

### Circular definitions and overstatements

- **Circular:** *"the trend is identified by the market structure"* + *"market structure is these
  highs and lows"* — trend is defined as structure and structure defines trend. Internally coherent
  as a **definition**, but it means A3 cannot be falsified; it asserts nothing about future price.
  Only the paired empirical claims (A4, E1) are testable.
- **Overstatement:** *"Market structure is Absolut absolutely everything in the market"* (0:57)
  versus *"Market structure is only 50% of the problem"* (20:21) — **the same source, 19 minutes
  apart.** Not recorded as a formal contradiction because the first is rhetorical framing and the
  second is the operative scoping statement, but the tension is worth noting: the video opens by
  overselling exactly what it closes by bounding.
- **Overstatement:** *"it is very easy and very straightforward"* applied to the snake trick, which
  is the one genuinely under-specified step in the method.

---

## Confidence note — why nothing moved

All 14 new claims and all 4 restatements sit at `emerging`. Two mechanisms hold the ceiling:

1. **`DECISION|MOGO|20260727|006`** — same-educator repetition shares one independence group. The
   four restatements above moved scores from 22.0 to 23.5–25.0 (the 25% same-group discount) and
   changed no state. **Without this policy they would have reached `supported` and auto-proposed
   rule candidates — which in fact happened transiently during this ingestion and was corrected.**
2. **Trader-scoped claim fingerprints** — TJR states A1 in almost identical words, but a TJR claim
   and an ALEX_G claim never merge.

**Consequence: replay validation is now the only remaining route to `supported`.**

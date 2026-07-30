# ALEX — Knowledge Gaps and Source Acquisition Plan

**Milestone:** MOGO-002.8 · **Phase 6** · **Date:** 2026-07-29
**Machine-readable:** [`alex-knowledge-gaps-and-source-plan.json`](alex-knowledge-gaps-and-source-plan.json)

> This plan names **which transcript to acquire next**, not merely that more research is needed.

---

## 1. The next acquisition target

> ### 🎯 Rank 1 — an **ALEX_G live trading session showing an order actually being placed**
>
> **Resolves:** `AXG-01` (stop buffer) · `AXG-02` (stop anchor) · `AXG-04` (session hours) · `AXG-08` (short side)
>
> **Why this one:** a stop price must be **typed into an order ticket**. That is the single context in
> which the missing buffer becomes visible, and it is the only artifact that could close **both P0
> stop gaps at once**. It also executes standing acquisition target **A2-LIVE** (`BACKLOG-002`,
> opened cycle 013), so it is not a new direction.
>
> **Search terms:** `fxalexg live trading session` · `fxalexg live trade` · `fxalexg trading live forex`
>
> **Known risk:** he may show the number on screen without speaking it — the `KEGAP-003` failure mode
> that already defeated the session hours. **This risk is real and should be expected**, which is why
> rank 2 exists.

> ### 🎯 Rank 2 — the **engulfing-candlestick video the educator points at himself**
>
> **Resolves:** `AXG-03` (confirmation requirement and pattern family)
>
> **Why this one:** it is the **only gap in this plan with a named, educator-pointed-at source.** At
> **5:33** of `EVSRC|ALEX_G|20260729|001` he says: *"you want to know more about bullish engulfing
> bearish engulfing and how you can use that effectively with break and retest **just look at this
> video right here**."*
>
> It addresses the **largest trade-eligibility divergence** the fidelity matrix found — MOGO has no
> confirmation gate at all — and the educator has **confirmed the video exists and stated its
> subject**.
>
> **⚠️ REVISED 2026-07-29 (later same day):** an acquisition attempt **failed to identify which video
> this is.** The reference is an on-screen card, and date-filtering all 200 catalogue titles against
> source #9's publish date eliminated the strongest candidate. **The target exists but is
> unresolved** — see `AXG-03` below and
> [`ALEX-AUDIT-DELTA-2026-07-29b.md`](ALEX-AUDIT-DELTA-2026-07-29b.md).
>
> **Search terms:** `fxalexg engulfing candlestick confirmation` · `fxalexg bullish bearish engulfing trend continuation`
> **Fastest resolution:** open source #9 at 5:33 and read the card.

**If only one transcript can be acquired, acquire rank 2** — *once the operator has identified it
from the on-screen card*. The original rationale (near-certain to exist, near-certain to be on-topic)
still holds for the video itself; what is no longer certain is **which** video it is. Until that is
resolved, rank 1 is the only actionable target.

---

## 2. All gaps, ranked

| ID | Gap | Evidence state | Priority | Blocks replay | Expected gain |
|---|---|---|---|---|---|
| **AXG-01** | **How far beyond the rejection structure does the stop go?** | `ABSENT_FROM_REVIEWED_SOURCES` | **P0** | **YES** | **DECISIVE** |
| **AXG-02** | **What is the stop anchored to?** (3 readings) | `AMBIGUOUS` | **P0** | **YES** | HIGH |
| **AXG-03** | **Is a candlestick confirmation required, and which patterns?** | `PARTIALLY_SUPPORTED` | **P0** | no | HIGH |
| **AXG-04** | What are the exact session hours? | `NON_DETERMINISTIC` | P1 | **YES** | MEDIUM |
| **AXG-05** | Break-even / partials / scaling / trailing — do any exist? | `ABSENT_FROM_REVIEWED_SOURCES` | P1 | **YES** | HIGH |
| **AXG-06** | How is the target chosen above the 1:2 floor? | `PARTIALLY_SUPPORTED` | P1 | no | MEDIUM |
| **AXG-07** | What makes a swing point significant? | `AMBIGUOUS` | P2 | **YES** | LOW |
| **AXG-08** | Is the short-side stop ever stated? | `ABSENT_FROM_REVIEWED_SOURCES` | P2 | no | MEDIUM |

**5 of 8 gaps block replay validity.**

---

## 3. Gap detail

### AXG-01 · The stop buffer — **P0, decisive**

**Exact unanswered question:** *How far beyond the rejection structure is the stop placed?*

**Current state:** the relationship is stated as an invariant (`AXR-020`). **No unit of any kind
appears in 9 sources** — no pips, no ATR multiple, no percentage, and no statement that it sits flush.

**Why it matters:** position size = risk ÷ stop distance. This one absence makes **all 13 educator
sizing rules non-computable** and is the only thing preventing an end-to-end educator-faithful trade
from being *expressible at all*. It is also what keeps MOGO's `stopATRBuffer = 0.25` unattributable.

**Affects:** stop placement · position sizing · replay validity · strategy fidelity
**Known source exists:** ✗ — no identified video is known to state it
**Best target:** rank 1 (live session with order entry)

### AXG-02 · The stop anchor — **P0**

**Exact unanswered question:** *What is "it" / "this point"?* Three readings are each consistent with
the words and the chart narration:
(a) the low of the final rejection/engulfing candle ·
(b) the low of the **whole** Morning Star formation ·
(c) the far boundary of the **retested zone**.

**Why it matters:** the three give **materially different stop distances on the same setup**, so every
downstream R-multiple and position size changes with the choice. It is also the point on which MOGO
and the educator quietly differ today: **MOGO anchors on (c); the educator's words most naturally read
as (a) or (b).**

**Affects:** stop placement · position sizing · replay validity
**Best target:** rank 1 — a live session would show the anchor unambiguously

### AXG-03 · The confirmation requirement — **P0, named source exists**

**Exact unanswered question:** *Is the confirmation specifically a bullish engulfing candle, or any
rejection formation?* The requirement is stated as *"a bullish engulfing Candlestick confirmation"*,
but the demonstrations show a **Morning Star** (3 doji + 1 engulfing) and the narration also accepts
*"rejection candlesticks"* generally. The bearish mirror is never stated.

**Why it matters:** **MOGO has no confirmation gate at all.** Adding or omitting it changes which
setups are eligible — the largest trade-eligibility difference this audit found.

**Known source exists:** ⚠️ **REVISED 2026-07-29 (later same day) — the referenced video could NOT be
identified.** See [`ALEX-AUDIT-DELTA-2026-07-29b.md`](ALEX-AUDIT-DELTA-2026-07-29b.md).

An acquisition attempt was made and failed on **two independent blockers**:

1. **The reference is deictic.** *"Just look at this video right here"* points at an **on-screen
   card**; the transcript records the pointing, not the target — **structurally the same failure mode
   as `AXG-02` (stop anchor) and `AXG-04` (session hours)**.
2. **All 200 catalogue titles were searched and 5 matched.** Each was channel-verified and
   date-checked against source #9's publish date (`2024-02-04`). The referenced video must predate it:

   | Candidate | Published | Verdict |
   |---|---|---|
   | `kLLMCoPb6h0` — *EVERY Candlestick Pattern YOU Need to Know* | **2024-03-03** | ❌ **postdates by 27 days** |
   | `JA4N8nlycXY` — *…$70,000 in 1 Day \| Head And Shoulders* | **2024-02-07** | ❌ postdates by 3 days |
   | `BcWxqfcjk9A` — *The ONLY confirmation YOU need…* | 2026-04-16 | ❌ postdates; already ingested as source #4 |
   | `ibgnOrk9MLo` — *6 Reversal Candlestick Patterns* | 2023-09-28 | ⚠️ date-eligible, **topic mismatch** (reversal ≠ continuation) |
   | `4Lv_SzhdyhM` — *How I Spot Forex Patterns That Print Money* | 2021-08-12 | ⚠️ date-eligible, topic too generic |

   **`kLLMCoPb6h0` looked like the obvious answer and is provably wrong** — it even has a
   *"29:12 Continuation candles"* chapter, but a video published 2024-02-04 cannot link forward to
   one published 2024-03-03. Without the date check this would have been a confident, wrong
   attribution.

**No candidate is recorded as the referenced source.** Doing so on topical proximity would be exactly
the inference this audit's governance forbids.

**To close it, one operator action:** open source #9 at **5:33**, read the on-screen card, and supply
that video's transcript. That single observation resolves what no transcript can.

**Best target:** rank 2 (unchanged in priority; target now identified as *unresolved* rather than
*known*)

### AXG-04 · Session hours — P1

**Current state:** 7 session rules are prescriptive and explicit; the hours are on an on-screen map and
never spoken. **MOGO applies no session restriction at all**, so this is a live divergence, not just a
gap.

**⚠️ A transcript of the same format cannot close this.** Closing it needs either a source that reads
the hours aloud, or an Authority-approved frame-reading method — **which is not a transcript
acquisition task and needs its own decision.**

### AXG-05 · Break-even / partials / scaling / trailing — P1

**Four domains at absolute zero across 9 sources.** Each changes realized R per trade, so **expectancy
is not computable** while they are unknown — even though MOGO's no-intervention defaults are probably
correct.

**Known source exists:** ✅ partially — source #8 self-identifies as **episode three** of a "set and
forget" podcast, so other episodes exist. A dedicated set-and-forget explainer is the natural target
and could resolve all four at once, possibly as deliberate nulls (a legitimate closure).

### AXG-06 · Target selection above the floor — P1

MOGO implements a **fixed 2R**; the educator states a **minimum**. Every trade where structure allowed
more is a divergence. Also entangled with open contradiction `XCONTRA|20260729|004`, which asks
whether 1:2 is a floor a trade may be *set at* or a level a preset target must never be *revised down
to*. **That half is an Authority ruling, not an acquisition.**

### AXG-07 · Swing-point significance — P2, low expected gain

Gates every structure rule. **Two educators give contradictory guidance about a number neither
supplies** (`XCONTRA|20260729|001`). Recorded as replay candidate RC-29. **Acquisition is unlikely to
resolve it** — this is a replay question, and replay is unauthorized.

### AXG-08 · Short-side stop — P2

MOGO trades both directions symmetrically. The educator has only ever been recorded stating the long
side, so **MOGO's short-side stop is an assumption.** A single short-trade walkthrough would settle it.

---

## 4. What acquisition cannot fix

Stated plainly so effort is not misdirected:

- **AXG-04 (session hours)** — exists as pixels, not words. Needs a frame-reading decision.
- **AXG-07 (swing significance)** — needs replay, which is unauthorized.
- **`XCONTRA|20260729|004`** (1:2 floor vs revised-down target) — both positions are already the
  educator's. **No further ALEX_G source can settle it**; it needs an Authority ruling.
- **The D2 blocker** — even a perfect acquisition leaves every claim at `emerging`, because
  same-educator sources share one independence group. **Until D2 is decided, no acquired rule can
  ever become a candidate rule.**

**That last point bounds the value of everything above.** Acquisition raises *knowledge*; it cannot
raise *confidence* under the current fingerprinting rule.

---

*Phase 6 complete. No source was acquired by this audit.*

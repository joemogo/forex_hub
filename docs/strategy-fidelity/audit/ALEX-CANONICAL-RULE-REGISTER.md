# ALEX — Canonical Rule Register (educator-derived)

**Milestone:** MOGO-002.8 · **Phases 3–4** · **Date:** 2026-07-29
**Machine-readable:** [`alex-canonical-rule-register.json`](alex-canonical-rule-register.json)

> ## ⚠️ Scope — read this before using the register
>
> This is an **audit view over the ALEX_G educator claim library**. It is **not** a specification, it
> is **not approved**, and it **does not merge** with `alex_g_sr_v1`, whose rules are MOGO's own
> (`DECISION|MOGO|20260727|004`, KEREV-B). **No rule here authorizes any code change.**
>
> Every claim cited below sits at `emerging` confidence. Under `POLICY-001` **nothing in this
> register is promotable today**, regardless of how well evidenced it is.

---

## 1. Register summary

**41 canonical rules** across the 32 domains named in the audit brief.

| | Count |
|---|---|
| `EXPLICIT` — educator states it in words | **26** |
| `ILLUSTRATIVE` — demonstrated or worked, never generalized | **5** |
| `OPINION` | 1 |
| **`UNSUPPORTED` — no rule exists in any source** | **9** |
| **Deterministic (mechanically evaluable as stated)** | **6 / 41** |
| Long-side supported | 31 / 41 |
| **Short-side supported** | **21 / 41** |
| Rules touching an open contradiction | 1 (`AXR-030`) |

**Six of forty-one rules are deterministic.** That is the register's most important number: the
educator's method is described richly and specified thinly.

## 2. Reading the classifications

- **`EXPLICIT`** — stated in words, as a rule. The educator generalizes it.
- **`ILLUSTRATIVE`** — shown once or worked through arithmetically, and **never universalized**.
  Per the audit brief, these are **not** converted into rules.
- **`UNSUPPORTED`** — the register records the *question*; no source answers it. Written as
  `[NO RULE EXISTS]`.
- **Deterministic** — could be evaluated by code exactly as stated, with no invented parameter.

## 3. The register

### 3.1 Structure, bias and setup

| ID | Domain | Rule | Class | Det. | Short side |
|---|---|---|---|---|---|
| **AXR-001** | support_and_resistance | S/R is where price held or was rejected; S/R, supply-demand and "area of interest" are **one concept under three names** | EXPLICIT | ✗ | ✓ |
| **AXR-002** | trend_definition | Downtrend = lows with lower highs between them; uptrend mirrors it | EXPLICIT | ✗ | ✓ |
| **AXR-003** | break_of_structure | A **body close** beyond a level counts as a shift, **no minimum size** | EXPLICIT | ✗ | ✓ |
| **AXR-004** | break_and_retest | Break-and-retest is a **CONTINUATION** pattern | EXPLICIT | ✗ | ✓ |
| **AXR-005** | entry_setup | A level is valid only with a **MINIMUM OF ONE structure point** | EXPLICIT | ✗ | ✓ |
| **AXR-006** | entry_setup | A retested zone **becomes** the next structure point (chains recursively) | EXPLICIT | ✓ | ✓ |
| **AXR-007** | entry_setup | Break-and-retest is **"most effective"** at a pre-existing zone | EXPLICIT | ✗ | ✓ |
| **AXR-008** | entry_setup | Zone width is **explicitly UNCONSTRAINED** — *"doesn't matter the size of the box"* | EXPLICIT | ✗ | ✓ |

**AXR-005 is a quantified minimum over an undefined unit.** "Minimum of one structure point" carries a
number, but *structure point* is never defined — so the rule is **not** deterministic despite looking
like it is. This is the single most common failure mode in the register.

**AXR-008 is an explicit NON-constraint**, and it matters disproportionately: MOGO's production rule
`ALEX_SR_008` (zone tightness) is classified `AMBIGUOUS` precisely because its source *"gives no
formula"*. The educator library now shows he doesn't merely omit a formula — **he actively declines to
impose one.**

### 3.2 Entry and confirmation

| ID | Domain | Rule | Class | Det. | Short side |
|---|---|---|---|---|---|
| **AXR-010** | entry_trigger | Structure on the HTF; **the entry signal must be taken on a lower timeframe** | EXPLICIT | ✗ | ✗ |
| **AXR-011** | candlestick_confirmation | **A bullish engulfing confirmation is REQUIRED** before a long | EXPLICIT | ✗ | ✗ |
| **AXR-012** | candlestick_confirmation | Morning Star = three doji + one bullish engulfing | **ILLUSTRATIVE** | ✗ | ✗ |
| **AXR-013** | entry_trigger | The retest ends when rejection candles appear — not timed or measured | EXPLICIT | ✗ | ✗ |
| **AXR-014** | entry_trigger | Entry is at the confirmation candle | **ILLUSTRATIVE** | ✗ | ✗ |
| **AXR-015** | invalidation | **A structurally ideal setup is NOT taken without the confirmation** | EXPLICIT | ✗ | ✗ |

**AXR-015 is the strongest single piece of evidence in the corpus** that confirmation is *binding* and
not advisory: a textbook break-and-retest was **declined on camera** because the engulfing never
appeared. It is a demonstrated negative, which is harder to explain away than a stated positive.

**AXR-012 and AXR-014 are deliberately held at `ILLUSTRATIVE`.** The three-doji count is never stated
as required, and the exact entry price within the confirmation candle is indicated on the chart and
never named. Promoting either would be inventing precision.

### 3.3 Stop placement — the register's centre of gravity

| ID | Domain | Rule | Class | Det. | Short side |
|---|---|---|---|---|---|
| **AXR-020** | stop_loss_relationship | On **every** break-and-retest trade the stop goes immediately **beyond the rejection formation** at the retest | **EXPLICIT** | ✗ | ✗ |
| **AXR-021** | stop_loss_buffer | *[NO RULE EXISTS]* — the distance between stop and structure | **UNSUPPORTED** | ✗ | ✗ |
| **AXR-022** | stop_loss_relationship | *[NO RULE EXISTS]* — the short-side placement | **UNSUPPORTED** | ✗ | ✗ |

**AXR-020** rests on `CLAIM|ALEX_G|20260729|025` — `rule_statement`, `direct_explicit`,
`extractionCertainty: certain`, explicitly universalized (*"the same thing every single time"*), plus
two same-source demonstrations at 7:52 and 8:25. **It is the only generalized stop statement in nine
sources.**

**AXR-021 is the load-bearing absence in the entire audit.** Position size = risk ÷ stop distance.
The corpus supplies the first term in three explicit percentage bands and **never supplies the
second** — so all 13 educator sizing rules are non-computable, and MOGO's `stopATRBuffer = 0.25` has
**no educator provenance whatsoever** (no ALEX_G claim in 9 sources mentions ATR at all).

### 3.4 Targets

| ID | Domain | Rule | Class | Det. | Contradiction |
|---|---|---|---|---|---|
| **AXR-030** | minimum_risk_reward | Take-profit is set to a **MINIMUM of 1:2** | EXPLICIT | ✗ | ⚠️ `XCONTRA\|20260729\|004` (material, open) |
| **AXR-031** | target_selection | *[NO RULE EXISTS]* — how the level is chosen above the floor | **UNSUPPORTED** | ✗ | — |

**AXR-030's cited evidence is a floor, not a value.** The four claims backing AXR-031 (80–100 pip
average; 1:2, 1:3, 1:4 ratios) are each annotated **illustrative** in the evidence store — distances
observed after the fact, not a selection procedure. One fragment measures 1:4 *"to previous"*
structure; it is too truncated to normalize and was not completed.

### 3.5 Risk and sizing — the strongest domain

| ID | Domain | Rule | Class | Det. |
|---|---|---|---|---|
| **AXR-040** | account_risk | Percentage of account balance, never a fixed dollar amount; **same percentage every trade** | EXPLICIT | **✓** |
| **AXR-041** | position_sizing | Three bands: conservative **0.5–1%**, recommended **1–2%**, high **3–5%** | EXPLICIT | **✓** |
| **AXR-042** | position_sizing | High band confined to personal accounts and to Nov–Mar | EXPLICIT | **✓** |
| **AXR-043** | account_risk | Never raised after wins or lowered after losses; one percentage per month | EXPLICIT | **✓** |

**Four of the register's six deterministic rules live here.** `CLAIM|ALEX_G|20260728|098` is one of
only two ALEX_G claims carrying evidence from **two distinct sources**.

**And all four are still unusable for sizing** — deterministic *as percentages*, they cannot produce a
position size without AXR-021.

### 3.6 Post-entry management, and four absolute zeros

| ID | Domain | Rule | Class |
|---|---|---|---|
| **AXR-050** | post_entry_management | A losing trade is allowed to reach its stop; loss accepted as variance | **ILLUSTRATIVE** |
| **AXR-051** | post_entry_management | No action while price travels toward the AOI | EXPLICIT |
| **AXR-052** | post_entry_management | A preset target should be allowed to run, not cut on the dollar figure | EXPLICIT |
| **AXR-053** | post_entry_management | After a missed entry, set an alarm rather than chase | ILLUSTRATIVE |
| **AXR-060** | break_even | *[NO RULE EXISTS]* | **UNSUPPORTED** |
| **AXR-061** | partial_profit | *[NO RULE EXISTS]* | **UNSUPPORTED** |
| **AXR-062** | scaling | *[NO RULE EXISTS]* | **UNSUPPORTED** |
| **AXR-063** | trailing_stops | *[NO RULE EXISTS]* | **UNSUPPORTED** |

**AXR-051 is the most-repeated claim in the corpus** — evidence from **three distinct sources**. It
still does not constitute independent corroboration (same educator, one independence group).

**AXR-050 is held at `ILLUSTRATIVE` on purpose.** It is demonstrated exactly once and never stated as
a rule. It is the best available evidence for a no-intervention default and it is **not** a rule.

**The four zeros are strengthened, not weakened, by the newest source.** Source #9 narrates three
complete trades from setup to close — precisely where a break-even move, a partial, or a trail would
naturally have been mentioned. None was.

### 3.7 Timeframes, sessions, market selection

| ID | Domain | Rule | Class | Det. |
|---|---|---|---|---|
| **AXR-070** | timeframe_relationships | HTF break-and-retest is "more respected" | EXPLICIT | ✗ |
| **AXR-071** | higher_timeframe_analysis | Four tiers: W / D / 4H / lower (2H,1H,30m,15m); **below 15m is not strong** | EXPLICIT | **✓** |
| **AXR-072** | timeframe_relationships | Day trade 4H/1H; swing D/W | EXPLICIT | ✗ |
| **AXR-080** | session_requirements | **Session and day-of-week gate entry; entries restricted to Mon–Wed** | EXPLICIT | ✗ |
| **AXR-081** | session_requirements | *[PARAMETER ABSENT]* — the exact session hours | **UNSUPPORTED** | ✗ |
| **AXR-090** | market_selection | Applies to **all** timeframes and instrument classes | EXPLICIT | ✗ |
| **AXR-091** | market_conditions | *[NO RULE EXISTS]* — any volatility/regime filter | **UNSUPPORTED** | ✗ |
| **AXR-092** | news_filters | *[NO RULE EXISTS]* | **UNSUPPORTED** | ✗ |
| **AXR-093** | liquidity | Sweeps cannot be traded alone; institutional-hunt narrative rejected | **OPINION** | ✗ |
| **AXR-100** | discretionary_judgment | Several gates are explicit judgement calls with named inputs and **no thresholds** | EXPLICIT | ✗ |

**AXR-080 vs AXR-081 is the cleanest example of the corpus's characteristic failure.** The *rule* is
prescriptive, explicit and repeated across two sources. The *parameter* is displayed on an on-screen
session map and **never spoken**. Day-of-week (Mon–Wed) **is** deterministic; the hours are not.

## 4. Domain coverage roll-up

| Coverage | Domains | Which |
|---|---|---|
| **WELL_SUPPORTED** | **4** | support_and_resistance, supply_and_demand, break_and_retest, account_risk |
| **SUPPORTED** | **5** | higher_timeframe_analysis, trend_definition, minimum_risk_reward, no_trade_conditions, examples_vs_universal_rules |
| **PARTIALLY_SUPPORTED** | **12** | market_selection, directional_bias, market_structure, entry_setup, entry_trigger, candlestick_confirmation, timeframe_relationships, stop_loss_relationship, invalidation, target_selection, position_sizing, post_entry_management |
| **AMBIGUOUS** | 1 | break_of_structure |
| **NON_DETERMINISTIC** | 1 | session_requirements |
| **DISCRETIONARY** | 2 | liquidity, discretionary_judgment |
| **ABSENT_FROM_REVIEWED_SOURCES** | **7** | stop_loss_buffer, break_even, partial_profit, scaling, trailing_stops, market_conditions, news_filters |

Per-domain *what is known / what remains unknown / does it block implementation / could another
transcript resolve it / most valuable next source* is carried in the JSON under `domainCoverage`.

**Of the 7 absent domains, 5 could plausibly be resolved by one more transcript** — the exceptions are
`stop_loss_buffer` (may simply never be spoken) and `market_conditions` (may genuinely not exist as a
concept in this method).

## 5. Examples versus universal rules — how the line was drawn

The audit brief requires demonstrations not be converted into universal rules. Applied:

| Statement | Recorded as | Why |
|---|---|---|
| *"the same thing every single time your stop-loss is right under it"* | **RULE** | Explicitly universalized |
| *"a minimum of a 1 to two risk to reward"* | **RULE** | States a floor; repeated in a generalizing sentence |
| *"you would have put your stop loss right under this point"* | Demonstration supporting AXR-020 | Chart narration, one instance |
| *"three dogee Candlestick rejections one bullish engulfing"* | **ILLUSTRATIVE** | Describes one formation; count never required |
| *"you risk 1% you got 2%"* | **ILLUSTRATIVE** | Worked arithmetic |
| *"an average of about 80 to 90 to even 100 pips"* | **ILLUSTRATIVE** | Explicitly a personal average |
| *"it's a nice one to four"* | **ILLUSTRATIVE** | Observation about one chart |
| *"I personally like using…"* | Preference within AXR-070 | Self-labelled preference |
| *"most effective at these zones"* | Comparative within AXR-007 | Not *"must"* |

**No numeric stop buffer is attributed to Alex anywhere in this register**, because no primary source
provides one.

---

*Phases 3–4 complete. Read-only over the evidence store; nothing promoted, nothing approved.*

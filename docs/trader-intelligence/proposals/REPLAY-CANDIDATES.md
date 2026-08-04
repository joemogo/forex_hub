# Replay Candidates — Structured Specifications

**Generated:** 2026-07-27 · **Source:** `EVSRC|TJR|20260727|001`
**Status:** Specifications only. **No replay has been run and none is authorized.**
**Relationship to `BACKLOG-001`:** that document prioritizes *what to test and why*; this one gives
the executable specification for each item in the charter's required format.

> **Gate:** extraction-pipeline review + an `OwnerDecision` with `replayAuthorization: true`
> (POLICY-001 currently records `false`) + licensing resolution.

> **On `UNKNOWN` fields.** Several specifications below carry `UNKNOWN — not in source` for risk or
> exit. That is the honest state: the transcript contains no risk-per-trade rule and no definition
> of the TP1–TP4 ladder. **A specification with an UNKNOWN in `risk` cannot produce a P&L result** —
> it can only produce occurrence, frequency, sequence, and excursion results. Filling those fields
> with plausible defaults would convert a knowledge gap into a fabricated backtest.

---

## RC-01 — Step 2B: pre-market sweep requires a five-minute manipulation

**Priority: 1 (highest).** The only TJR claim with a stated rule, a stated causal rationale, **and**
a demonstrated counterfactual.

| Field | Specification |
|---|---|
| **Claims** | `CLAIM\|TJR\|20260727\|018` (rule), `\|020` (failure condition), `\|019` (rationale) |
| **Instruments** | ES and NQ (S&P 500, NASDAQ) |
| **Timeframes** | 5m (structure), 1m (sequence resolution) |
| **Setup precondition** | A liquidity sweep of a prior session / 1h / 4h high or low occurring **during New York pre-market (from 08:30)**, before the 09:30 open |
| **Required confirmations** | ≥1 five-minute confirmation confluence after the sweep: break of structure, inverse FVG, SMT divergence, or 79% extension closure |
| **Variant A (control)** | Proceed directly to the continuation confluence and enter — i.e. **skip 2B** |
| **Variant B (treatment)** | Wait for a five-minute manipulation after the open, then continuation confluence, then enter |
| **Entry** | After a 1m confirmation confluence following the continuation confluence |
| **Exit** | `UNKNOWN — not in source` (TP ladder undefined). **Measure excursion, not realized P&L.** |
| **Stop** | Beyond the swing extreme the entry is taken against (`\|028`). Exact reference/buffer `UNKNOWN` — use the swing extreme itself and report sensitivity |
| **Risk** | `UNKNOWN — not in source`. No position sizing; results are per-unit excursion |
| **Invalidation** | Price closes beyond the swing that the confirmation-confluence trend was established from (`\|022`) |
| **Expected behavior** | Variant A is stopped out materially more often than Variant B |
| **Success criteria** | Over ≥30 qualifying pre-market-sweep days: Variant B shows a lower adverse-excursion rate past the stop reference than Variant A, with the difference larger than the difference between two random partitions of the same days |
| **Failure criteria** | No material difference, or Variant A superior → `|018` is not supported; `|020` reflects one selected example |
| **Data required** | ES + NQ, 1m and 5m, ≥6 months incl. April–October, with session boundaries |
| **Blockers** | Gate only. Runnable as `TRIGGER-ONLY` |

---

## RC-02 — Order block / breaker block redundancy

**Priority: 2.** Tests a *methodological* claim that transfers across strategies and asset classes.

| Field | Specification |
|---|---|
| **Claims** | `CLAIM\|TJR\|20260727\|038` |
| **Hypothesis** | Price filling an FVG or equilibrium coincidentally touches an order block / breaker block, making those confluences redundant |
| **Timeframes** | 5m |
| **Method** | For every FVG-fill and equilibrium-fill event, test whether an order block or breaker block was touched within the same event |
| **Entry/Exit/Stop/Risk** | `N/A` — a geometric coincidence test, not a trade simulation |
| **Expected behavior** | High coincidence rate |
| **Success criteria** | ≥90% coincidence substantiates the simplification |
| **Failure criteria** | <70% means a non-redundant signal was discarded |
| **Cross-strategy value** | **Directly testable against JVM.** JVM prices `wick`+`engulf` at 35 of a 55 threshold while TJR removed pattern confluences entirely. A JVM re-scoring experiment with those weights zeroed is the same question on data MOGO already has |
| **Blockers** | Gate only |

---

## RC-03 — Permissiveness of "only one confirmation confluence"

**Priority: 3.** Calibrates how much the worked examples oversell the setup's selectivity.

| Field | Specification |
|---|---|
| **Claims** | `\|013` (four confluences), `\|014` (only one required) |
| **Method** | Count qualifying setups per month under: (a) any-one-of-four, (b) all-four. Report the ratio and per-confluence hit distribution |
| **Entry/Exit/Stop/Risk** | `N/A` — frequency study |
| **Expected behavior** | (a) yields substantially more setups than (b); both demonstrated examples showed ~all four |
| **Success criteria** | Descriptive. Output is the (a):(b) ratio and per-confluence frequencies |
| **Failure criteria** | None — this cannot fail, only inform |
| **Why it matters** | If (a) yields many times more setups than (b), the literal rule is far looser than the teaching examples suggest, and every other replay result must be read against that base rate |

---

## RC-04 — Trend-intact invalidation

**Priority: 4.** The **only** invalidation rule in the entire library.

| Field | Specification |
|---|---|
| **Claims** | `\|022` |
| **Invalidation under test** | After the 5m manipulation, the setup remains valid only while price stays in the trend established by the confirmation confluence |
| **Method** | For each qualifying setup, test whether a close beyond the prior swing reliably marks failure. Measure false-invalidation rate (invalidated, then target reached anyway) |
| **Entry/Exit/Risk** | `UNKNOWN` — invalidation timing study |
| **Success criteria** | False-invalidation rate low enough that the rule is protective rather than merely early |
| **Failure criteria** | High false-invalidation → the rule exits good trades |
| **Note** | Entry rule `\|027` has **no companion invalidation in scope** — an auto-detected open question. This tests the only one that exists |

---

## RC-05 — Leading-index selection

**Priority: 5.** `BLOCKED`.

| Field | Specification |
|---|---|
| **Claims** | `\|004` (rule), `\|005` (definition) |
| **Method** | Replay identical setups on the leading vs lagging index; compare target-reach rate |
| **Expected behavior** | Leading index reaches draws more often |
| **Success criteria** | Materially higher reach rate on the leading index |
| **Blockers** | **`PROPOSAL-001` phases A–C.** Requires simultaneous modelling of two instruments with correct per-instrument quotation, which MOGO cannot express today |

---

## RC-06 — Contradiction resolution: is Step 3 mandatory?

**Priority: 6.** Resolves `XCONTRA|20260727|001` (material, open).

| Field | Specification |
|---|---|
| **Claims** | `\|023` (Step 3 required) vs `\|032` (trade taken without it) |
| **Variant A** | Step 3 mandatory — no continuation confluence, no trade |
| **Variant B** | Step 3 optional when strong draws and good R:R remain |
| **Exit / Risk** | `UNKNOWN` — compare target-reach rate rather than expectancy |
| **Success criteria** | One variant materially outperforms on reach rate |
| **Failure criteria** | No difference → the contradiction is immaterial to outcomes and can be recorded as context-dependent |
| **Hard limitation** | ⚠️ Replay can show which interpretation *performs* better. It **cannot** show which TJR actually follows. Only source material resolves that (`BACKLOG-002/T3`) |

---

## RC-07 — Contradiction resolution: continuation-confluence set under 2B

**Priority: 7.** Resolves `XCONTRA|20260727|002` (minor, open).

| Field | Specification |
|---|---|
| **Claims** | `\|024` (equilibrium + FVG only) vs `\|025` (SMT also, under 2B) |
| **Method** | After a 2B five-minute manipulation, measure how often an equilibrium or FVG is actually available. TJR's stated rationale is that neither exists in that situation — a directly checkable geometric claim |
| **Success criteria** | If availability is near zero, `\|025` is a necessary accommodation and the contradiction resolves as context-dependent |
| **Failure criteria** | If commonly available, the two claims genuinely conflict and need a source to resolve |

---

## RC-08 — Discretion gap: stated rules vs demonstrated behavior

**Priority: 8 — but read this before trusting any result above.**

| Field | Specification |
|---|---|
| **Claims** | `\|031`, `\|032`, `\|033` |
| **Method** | Replay the literal rule set against the two documented worked examples; measure deviation |
| **Expected behavior** | The literal rules do **not** reproduce his own examples |
| **Success criteria** | Deviation quantified per example |
| **Why it gates everything** | If the literal rules cannot reproduce the source's own demonstrations, then no replay of the literal rules can validate his results, and the gap is **discretion, not edge**. This calibrates the credibility of RC-01 through RC-07 |

---

## RC-10 — Bodies versus wicks: does the marking convention change the trend read? `TRIGGER-ONLY`

**Priority: 2 (raised on ingest of ALEX_G source #1).** The library's first **cross-educator**
contradiction, and the cheapest real experiment it contains.

| Field | Specification |
|---|---|
| **Contradiction** | `XCONTRA\|20260727\|003` · DEFINITIONAL · material · CROSS-EDUCATOR |
| **Claims** | `CLAIM\|ALEX_G\|20260727\|020` (bodies) vs `CLAIM\|TJR\|20260727\|065` (wicks) |
| **Instruments** | Any — the disagreement is convention-level, not market-specific. Run on both an FX pair and an index to test whether it is instrument-sensitive. |
| **Timeframes** | Weekly, daily, 4h (ALEX_G's directional set) plus 5m/1m (TJR's) |
| **Method** | Mark structure twice over identical data — once at candle bodies, once at wicks. Then compare: (a) count of identified highs/lows, (b) count of structure breaks, (c) the resulting bullish/bearish label per bar, (d) how often the two conventions disagree on the *current* trend |
| **Entry / Exit / Stop / Risk** | `N/A` — this is a labelling study, not a trade simulation |
| **Expected behavior** | Wick-marking produces more structure points and more frequent breaks; body-marking produces fewer, later trend changes |
| **Success criteria** | Descriptive and decisive: report the % of bars on which the two conventions disagree about the current trend. Anything above a few percent means this is a material fork, not a stylistic one |
| **Failure criteria** | Near-zero disagreement → the contradiction is cosmetic and can be recorded as context-dependent |
| **Why it matters** | Both educators agree a *close* beyond the level is required (`A2` in the cross-strategy analysis). They disagree only on which part of the candle closes. That is one parameter, cleanly isolated, with everything downstream depending on it — stop placement, break detection, risk-to-reward |
| **Blockers** | Gate only. Needs price data; no risk model, no TP ladder, no instrument abstraction |

---

## RC-11 — Does higher-timeframe alignment improve outcomes? `NEEDS-RISK`

**Priority: 5.** ALEX_G's central claim, and the answer to TJR's largest open gap.

| Field | Specification |
|---|---|
| **Claims** | `ALEX_G\|…\|007` (HTF overrides LTF), `\|009` (top-down order), `\|010` (overall score) |
| **Variant A** | Take entries regardless of weekly/daily/4h alignment |
| **Variant B** | Take entries only when weekly, daily and 4h agree |
| **Exit / Risk** | `UNKNOWN — not in source`. **ALEX_G's source states no stop, target or risk rule at all**, so measure target-reach and adverse excursion, not P&L |
| **Success criteria** | Variant B shows a materially better reach-rate / lower adverse excursion |
| **Cross-strategy value** | JVM already prices multi-timeframe bias at 40 of a 55 threshold — its single largest input. This tests, on data MOGO holds, whether a *rule-based* version of that idea outperforms the weighted one |
| **Blockers** | Gate + the missing risk rule for any P&L claim |

---

## RC-12 — Body-close structure-shift detection `TRIGGER-ONLY`

**Priority: 1 (joint-highest).** The single most mechanically specified rule in the entire library.

| Field | Specification |
|---|---|
| **Claims** | `CLAIM\|ALEX_G\|20260727\|022`, `\|20260728\|007` · rule register B1/B2/B6 |
| **Rule under test** | Bullish → bearish on a candle **body** close below the active higher low; bearish → bullish on a body close above the active lower high. Price inside the levels changes nothing |
| **Method** | Implement the state machine and label every bar bullish/bearish across a long history. Report shift frequency, average bars per state, and label stability |
| **Entry/Exit/Stop/Risk** | `N/A` — a labelling study |
| **Success criteria** | Deterministic, reproducible labelling with no ambiguous bars |
| **Failure criteria** | Ambiguity requiring human judgement → the rule is not as mechanical as stated |
| **Dependency** | ⚠️ Requires a pivot definition for reassignment (RC-16). Run RC-16 first or hold `k` fixed and disclose it |
| **Blockers** | Gate + price data only |

---

## RC-13 — Wick-break versus body-close comparison `TRIGGER-ONLY`

**Priority: 1 (joint-highest).** Resolves the library's only cross-educator contradiction. Supersedes
and subsumes `RC-10`.

| Field | Specification |
|---|---|
| **Contradiction** | `XCONTRA\|20260727\|003` · DEFINITIONAL · material · CROSS-EDUCATOR |
| **Claims** | ALEX_G `\|20260727\|020` (bodies) vs TJR `\|20260727\|065` (wicks) |
| **Method** | Run RC-12's state machine twice over identical data — levels at `max/min(open,close)` versus at `high/low`. Compare shift counts, shift timing, and the % of bars where the two conventions disagree on the current trend |
| **Success criteria** | Decisive either way: high disagreement ⇒ a material fork requiring an owner decision; near-zero ⇒ the contradiction is cosmetic and can be recorded as context-dependent |
| **Why it is cheap** | No risk model, no TP ladder, no instrument abstraction. One parameter, isolated |
| **Blockers** | Gate + price data only |

---

## RC-14 — Structure label versus visual slope `TRIGGER-ONLY`

| Field | Specification |
|---|---|
| **Claims** | `CLAIM\|ALEX_G\|20260728\|004` (trend is structure), `\|005` (slope is a trap) |
| **Method** | Compare the structure label against a naive slope baseline (sign of an EMA slope or linear fit). Measure disagreement rate, then forward outcome conditioned on each |
| **Success criteria** | Where they disagree, the structure label is followed by favourable movement materially more often than the slope label |
| **Failure criteria** | No difference → A4 is rhetorical rather than empirical |
| **Note** | A3 itself is a **definition** and cannot be falsified. This tests the empirical half |

---

## RC-15 — Structure classification inside ranges `TRIGGER-ONLY`

| Field | Specification |
|---|---|
| **Claims** | `\|20260728\|006` (structure exists in ranges), `\|008` (any size counts) |
| **Method** | Segment history into ranging periods (e.g. low ADX / narrow Donchian width). Apply RC-12 inside them. Report shift frequency and label half-life versus trending periods |
| **Expected behavior** | Far higher shift frequency inside ranges |
| **Success criteria** | Descriptive and decision-relevant: if labels flip every few bars inside ranges, the method is mechanically valid but operationally unusable there — which the source never warns about |
| **Why it matters** | The source insists ranges are classifiable and that arbitrarily small closes count. This measures the cost of that combination |

---

## RC-16 — Sensitivity to pivot-selection rules (the snake trick) `TRIGGER-ONLY`

**Priority: 2. Gates RC-12 and RC-13.**

| Field | Specification |
|---|---|
| **Claim** | `\|20260728\|009` — *"at the moment that the snake has a sharp turn"* |
| **Problem** | The reassignment target is found by an undefined visual heuristic. Rule register §C3 concludes it is **not currently objective enough to formalize** |
| **Method** | Implement the snake trick as an n-bar fractal/pivot detector; sweep `k ∈ {1,2,3,5,8}` and re-run RC-12. Report how much the structure labelling changes with `k` |
| **Success criteria** | Labels stable across `k` ⇒ the vagueness is harmless and any reasonable pivot definition works |
| **Failure criteria** | Labels materially unstable ⇒ **the entire method inherits that instability**, and no replay of any Alex G rule can be trusted without fixing `k` first |
| **Constraint** | ⚠️ MOGO must **not** adopt one `k` as "the" definition — that would be inventing a missing definition. Report the sensitivity; let the owner decide |

---

## RC-17 — Sensitivity to a minimum break distance / ATR threshold `TRIGGER-ONLY`

| Field | Specification |
|---|---|
| **Claim** | `\|20260728\|008` — *"something as small as that counts as a shift"* |
| **Method** | Re-run RC-12 with a minimum break filter (fixed points, and ATR-relative: 0, 0.1, 0.25, 0.5 ATR). Report shift count, whipsaw rate and label half-life at each |
| **Success criteria** | If a small threshold sharply reduces whipsaws without materially delaying real shifts, the source's explicit no-threshold stance is measurably costly |
| **Failure criteria** | No improvement ⇒ the source is right that no threshold is needed |
| **Note** | This tests a rule the source **explicitly denies needing**. That is legitimate — the claim is falsifiable and the test is the honest way to settle it |

---

## RC-18 — Retracement entry versus chasing the extreme `NEEDS-RISK`

| Field | Specification |
|---|---|
| **Claims** | `\|20260728\|012` (don't chase), plus Alex G #1's AOI rules |
| **Variant A** | Enter at the newly formed extreme |
| **Variant B** | Wait for a retracement of X, sweeping X ∈ {25%, 38.2%, 50%, 61.8%} of the last leg |
| **Exit / Risk** | ⚠️ `UNKNOWN — not in source`. **Two Alex G sources, still zero stop/target/risk rules.** Measure target-reach rate and adverse excursion, never P&L |
| **Success criteria** | Variant B shows better excursion characteristics at some X |
| **Missing definition** | The source gives no retracement depth — X is swept precisely *because* MOGO must not invent one |

---

## RC-19 — Higher-high / lower-low reassignment logic `TRIGGER-ONLY`

| Field | Specification |
|---|---|
| **Claims** | `\|20260727\|016` (new HH ⇒ new HL), `\|20260728\|002` (new LL ⇒ new LH) |
| **Method** | Verify the invariant holds mechanically over history: after every shift, exactly one structure point of each type is active, and the paired level is always behind the leading extreme in time (Alex G #1's sequencing rule) |
| **Success criteria** | Invariant never violated ⇒ the state machine is well-formed |
| **Failure criteria** | Violations ⇒ the reassignment rule is under-specified for some price paths — likely those with equal highs/lows or gaps, neither of which either source addresses |

---


> ### ⚠️ Standing constraint — now educator-specific
>
> **Eight ALEX_G sources contain zero `stop_rule` claims**, including one devoted to risk management.
> Position size = risk ÷ stop distance, so **no ALEX_G candidate (RC-12…RC-28) can produce an
> expectancy or a P&L curve.** Each measures trigger accuracy, reach-rate, frequency or direction
> only. That is a property of his published material, not of the harness.
>
> **RAYNER_TEO source #1 breaks this — for RAYNER_TEO only.** It supplies entry, a mechanical stop,
> a target and a sizing formula, which makes **RC-30 the library's first P&L-capable candidate.**
>
> ⚠️ **Do not borrow across educators.** Applying Rayner's ATR stop to an Alex G or TJR setup would
> fabricate a rule and attribute it to someone who never stated it. The constraint above still binds
> every ALEX_G candidate.

## RC-28 — What proximity to a level actually qualifies? `ZONE-ONLY`

**Priority: 1.** Tests a filter that exists **only in observed behaviour**, never in any taught rule.

| Field | Specification |
|---|---|
| **Claims** | `ALEX_G\|20260728\|136` (a setup declined because price came ~10 pips short of 86.000) vs `\|068`, `\|069` (the confirmation must be *at* a level; away from one the rule is "simply not applicable") |
| **Contradiction** | `XCONTRA\|20260728\|008` · CONDITIONAL_SCOPE · material · **behaviour vs stated rule** |
| **The problem in one line** | Every instructional source states the condition as **binary** — at the level or not applicable. The live session shows it operating as **graded** — ~10 pips short was judged too far. No source gives a tolerance |
| **Method** | For every approach to a level, record the closest approach distance, normalised (in pips **and** as a fraction of ATR, since raw pips are not comparable across pairs). Bucket by distance and measure the forward outcome of entering on a confirmation in each bucket |
| **Primary output** | The **tolerance curve**: does outcome degrade smoothly with distance, or is there a cliff? A smooth curve means the binary rule is a simplification and any threshold is arbitrary. A cliff would locate the threshold empirically |
| **Why it matters beyond this one rule** | This session revealed **at least three discretionary filters absent from all six instructional sources**: proximity tolerance, confluence counting, and "worth the risk" selectivity. If a taught rule set systematically omits the filters its author actually uses, then replaying the taught rules measures something the educator does not trade. This candidate tests the first and cheapest of the three |
| **Entry/Stop/Risk** | `UNKNOWN — not in source`. Directional outcome only |
| **Must NOT be done** | Pick a tolerance and encode it. The whole point is that the source does not supply one |
| **Blockers** | Gate + price data |

---

## RC-30 — The complete RAYNER_TEO setup, end to end `FULL-SETUP` `P&L-CAPABLE`

**Priority: 1.** ⭐ **The first replay candidate in the library that can produce an expectancy.**

| Field | Specification |
|---|---|
| **Claims** | `RAYNER_TEO\|20260729\|035` (stop invalidates the setup), `\|036` (low of support − 1 ATR), `\|037` (never flush), `\|039` (target before the swing), `\|007` (sizing formula), `\|006` (1% risk), `\|017`/`\|046` (three-part gate) |
| **Entry** | Structure (trend) **AND** area of value (S/R or MA) **AND** entry trigger (closed reversal candle), entering at the next candle's open. The three are **gated in order** — without an area of value the trigger is not evaluated |
| **Stop** | ✅ **Low of the support area minus one 20-period ATR (SMA).** Explicitly not flush against the level |
| **Target** | ✅ Just **before** the nearest opposing swing high/low — never at or beyond it |
| **Size** | ✅ `risk ÷ (stop distance × value per pip)`, risk = 1% of account |
| **Why this is different from every prior candidate** | RC-01 … RC-28 all had `UNKNOWN — not in source` in the stop field. **This one has every leg.** It can be replayed for expectancy, win rate, average R, and drawdown — the quantities the library has never once been able to compute |
| **Parameters MOGO must still not invent** | ⚠️ **Swing-point significance.** "Sticks out like a sore thumb" is the only criterion given. Sweep it and report the sensitivity surface — do not pick a value. Also sweep the MA period beyond the demonstrated 50, and the target's "just before" distance, which is the one leg he leaves discretionary |
| **What a result means, and does not** | It tests **this educator's stated method under one swing-detection parameterisation.** He states plainly that structure classification is subjective and that two traders may legitimately disagree on the same chart. Any result must be reported with the parameters it assumed, and **must not be generalised to ALEX_G or TJR**, whose setups it does not describe |
| **Blockers** | Gate + price data. Nothing else |

---

## RC-29 — What makes a swing point count? `STRUCTURE` `CROSS-EDUCATOR`

**Priority: 1.** Settles a contradiction between two educators on the parameter both leave undefined.

| Field | Specification |
|---|---|
| **Contradiction** | `XCONTRA\|20260729\|001` · CONDITIONAL_SCOPE · material · **cross-educator** |
| **Claims** | `ALEX_G\|20260728\|008` — a body close beyond a level counts **regardless of size**, no minimum threshold · vs `RAYNER_TEO\|20260729\|019` — use **only major swing points**, deliberately ignore minor highs and lows |
| **The disagreement in one line** | Alex G's rule is **maximally sensitive** by design; Rayner's is **deliberately filtered**. Same operation, opposite instruction |
| **Method** | Implement structure detection with a swing-significance parameter `k` (pivot strength, minimum displacement, or ATR fraction — run all three families). At `k = 0` the detector is Alex G's; as `k` rises it approaches Rayner's. Measure trend-label stability and forward outcome across the sweep |
| **Primary output** | The **sensitivity curve**: how much does the trend label, and the outcome of trading it, depend on `k`? If outcomes are flat across `k`, the disagreement is cosmetic. If there is a clear optimum, it is the first empirically-located parameter in the library |
| **Why it now matters more** | This parameter already gated `RC-12`, `RC-13` and `RC-19` through `RC-16`. It is the single most load-bearing undefined number in the library, and **two independent educators have now given contradictory guidance about it** — which is exactly the situation replay exists to settle |
| **Blockers** | Gate + price data |

---

## RC-27 — Is November–March materially better than June–August? `SEASONALITY`

**Priority: 2.** The only prescriptive rule in the library that changes position size, and it rests
entirely on an unshown personal observation.

| Field | Specification |
|---|---|
| **Claims** | `ALEX_G\|20260728\|117` (3–5% risk only in Nov–Mar), `\|118` (Jun–Aug slower), `\|119` (basis: "months statistically that I've seen in my trading") |
| **Why it matters more than a normal performance claim** | This one **changes his risk by a factor of three to five.** Every other seasonal remark in the library is descriptive; this one is prescriptive and compounds directly into position size |
| **Method** | Using the RC-25 setup definition, count setup **frequency** and **directional outcome** by calendar month across as many years as data allows. Report by month, not by season, so the Nov–Mar / Jun–Aug split is tested rather than assumed |
| **Controls** | Compare against the instrument's unconditional monthly volatility and range. If setups simply track volatility, the "best months" claim is a restatement of seasonal volatility and carries no method-specific information |
| **Entry/Stop/Risk** | `UNKNOWN — not in source`. Measure setup frequency and directional outcome only. **This is testable precisely because it does not need the missing stop rule** |
| **Success criteria** | A month-level effect that survives a multi-year sample and the volatility control would be the first seasonal claim in the library with support. A null result would mean a rule that multiplies risk fivefold rests on nothing |
| **Honest limit** | Even a positive result validates the *pattern*, not the *risk escalation*. Whether raising risk in better months is correct depends on drawdown, which is not derivable without the stop rule |
| **Blockers** | Gate + multi-year daily/4H price data |

---

## RC-25 — The next-day continuation setup (Alex G's 70% claim) `FULL-SETUP`

**Priority: 1.** The most precisely specified setup in the entire library, from any educator.

| Field | Specification |
|---|---|
| **Claims** | `ALEX_G\|20260728\|065` (~70% next-day continuation), `\|063` (the 4H mechanism), `\|056` (closure confirms) |
| **Setup, fully specified by the source** | (1) daily candle closes with a bullish body **and** a strong downside rejection wick; (2) within that same day the 4-hour shifted bearish → bullish; (3) the level is a support zone |
| **Measured outcome** | Was the following day a bullish push? |
| **Why this is different** | Every prior replay candidate had to be assembled from claims across sections. **This one is stated as a complete, countable conditional with a number attached.** It is the first Alex G claim that can be falsified exactly as he stated it |
| **Entry/Stop/Risk** | `UNKNOWN — not in source`. Measure the **directional outcome only**, never P&L |
| **Definitions MOGO must not invent** | "strong" rejection wick (no ratio given); "bullish push" (no magnitude given). **Sweep both** — report continuation rate across wick-ratio and push-magnitude thresholds rather than picking one. If 70% appears only at one hand-picked pair of thresholds, that is the finding |
| **Success criteria** | A continuation rate near 70% across a defensible threshold range would be the first quantitative claim in the library to survive contact with data. A rate near the base rate of "next day is up" would show the setup adds nothing — **compute that base rate first, as the control** |
| **Blockers** | Gate + daily and 4-hour price data |

---

## RC-26 — What does waiting for the session actually cost? `TIMING-ONLY`

**Priority: 1.** Tests a claim the source contradicts itself on, and needs no entry model.

| Field | Specification |
|---|---|
| **Claims** | `ALEX_G\|20260728\|087` ("there's no negative" to waiting) vs `\|082` (waiting sometimes loses the trade outright), plus `\|081`, `\|083` |
| **Contradiction** | `XCONTRA\|20260728\|004` · CONDITIONAL_SCOPE · material · within-source |
| **Method** | For every confirmation signal, record two synthetic entries: (A) at the confirmation close; (B) at the next qualifying session open. Classify each pair into four outcomes: better entry · worse entry · same-loss · **signal invalidated before the session (trade never taken)** |
| **The whole point** | Alex G's "no negative" enumeration lists three outcomes and **omits the fourth he described himself two minutes earlier.** The test measures how often the fourth occurs — which is the entire question |
| **Secondary** | Whether the Monday–Wednesday restriction (`\|083`) forfeits more than it protects, using his own stated 80–100 pip target distance (`\|084`) as the travel requirement |
| **Blockers** | Gate + intraday price data with session timestamps. **Session hours are not in the source** — see the critical open question; run the standard Sydney/London/New York definitions and report sensitivity rather than adopting one as Alex G's |

---

## RC-22 — Does the two-timeframe-sync gate improve outcomes? `TRIGGER-ONLY`

**Priority: 1.** The first *quantified* rule any educator in the library has stated, and the first
that is directly comparable to a shipped MOGO engine.

| Field | Specification |
|---|---|
| **Claims** | `ALEX_G\|20260728\|035` (no trade without ≥2 timeframes in sync), `\|039` (10 points per timeframe), `\|038` (counter-direction trades ruled out) |
| **Method** | Label weekly, daily and 4H direction by Alex G's own body-close structure rule at each bar. Bucket every subsequent entry-side signal by how many timeframes agreed (0, 1, 2, 3). Compare forward excursion by bucket |
| **Primary output** | Whether outcome improves **monotonically** with agreement count. If 2-of-3 and 3-of-3 are indistinguishable, the stated gate is doing no work beyond a coin-flip filter |
| **Secondary output** | Whether an *opposing* middle timeframe (weekly bearish, daily bullish, 4H bearish — his own worked example) performs worse than three aligned. He grades both the same; there is no evidence he should |
| **Entry/Exit/Stop/Risk** | `UNKNOWN — not in source`. **Four Alex G sources, still zero stop, target and risk rules.** Measure excursion and target-reach only, never P&L |
| **Must NOT be tested** | The 10-point scale as a *threshold system*. The maximum of the scale is unknown (30 or 40 — the caption is garbled), so any pass/fail line MOGO picks would be invented. Test the **agreement count**, which is stated unambiguously |
| **Why it matters to MOGO** | Same decision shape as JVM's `WEIGHTS` + `ALERT_THRESHOLD`. A result here is the first evidence-based input MOGO has ever had on whether uniform-weight timeframe agreement is worth its cost. **A result is not authorization to change JVM** — see `CROSS-STRATEGY-ANALYSIS.md` §3c |
| **Blockers** | Gate + multi-timeframe price data |

---

## RC-23 — Does the lower-high/lower-low box constraint beat any support/resistance level? `ZONE-ONLY`

**Priority: 2.** Tests Alex G's sharpest claim, and one TJR has no equivalent of.

| Field | Specification |
|---|---|
| **Claims** | `ALEX_G\|20260728\|040` (search confined to the box), `\|041` (a break out of the box flips bias), `\|042` (a genuine S/R level can still be untradeable), corroborating `\|20260727\|026`, `\|027` |
| **Method** | For each directional regime, enumerate (a) every well-respected S/R level, and (b) only those inside the active lower-high/lower-low box. Compare reach-rate and forward outcome of entries at each set |
| **Success criteria** | Alex G's claim is that set (b) strictly dominates and that levels outside the box are reached only *after* the bias has already flipped — which is directly countable: what fraction of out-of-box level touches occur after a body close beyond the box? |
| **Cheapness** | High. This needs no entry model at all — it is a question about **which levels get reached, and in what order** |
| **Open definition** | Whether "break out of this box" requires a body close is not restated in this source. Sources #1 and #2 require one (`ALEX_G\|20260727\|022`); run both variants and report the sensitivity rather than choosing |
| **Blockers** | Gate + price data |

---

## RC-24 — Completed lower high versus "potential" lower high `TRIGGER-ONLY`

**Priority: 2.** Settles a **within-educator** contradiction, `XCONTRA|20260728|003`.

| Field | Specification |
|---|---|
| **Claims** | `ALEX_G\|20260728\|047` (a potential lower high is a valid sell location) vs `ALEX_G\|20260728\|028` (entry requires confirmation price is already moving the intended way) |
| **Method** | At each candidate lower high, take two synthetic entries: (A) on the incomplete swing, before any confirming close; (B) only after the structure point completes. Compare adverse excursion before the favourable move |
| **Primary output** | The cost of anticipation: how much worse (A) is, and how often (A) enters on a swing that never becomes a lower high at all — the failure mode confirmation exists to prevent |
| **Success criteria** | Decisive either way, and useful either way: if (A) is materially worse, source #3's confirmation rule is the one to keep and source #4's exception should be recorded as a lapse; if the difference is small, the exception is defensible and the contradiction downgrades to `minor` |
| **Note** | This tests the **same educator against himself**, so it produces no independence-group benefit under `DECISION\|MOGO\|20260727\|006`. Its value is deciding *which of his two rules to carry forward*, not raising confidence in either |
| **Blockers** | Gate + price data |

---

## RC-20 — Sweep-then-reverse versus confirmation-on-arrival `TRIGGER-ONLY`

**Priority: 1.** Settles the library's only `blocking` contradiction, and needs no risk model.

| Field | Specification |
|---|---|
| **Contradiction** | `XCONTRA\|20260728\|001` · DIRECTIONAL · **blocking** · CROSS-EDUCATOR |
| **Claims** | ALEX_G `\|20260728\|025` (no strategy can trade sweeps) vs TJR `\|20260727\|006` (the strategy is based on sweeps) |
| **Method** | Identify repeated-rejection zones (Alex G's ≥3 taps). For every approach, classify: (a) **swept** — price traded beyond the zone extreme then reversed; (b) **held** — price rejected without sweeping. Then measure forward outcome from each, entering on a confirmation candle in both cases |
| **Primary output** | The **sweep ratio**: what fraction of approaches actually sweep. Alex G's worked example claims 1 in 7 |
| **Secondary output** | Conditional outcome — does a swept approach produce a better forward move than a held one? |
| **Entry/Exit/Stop/Risk** | `UNKNOWN — not in source`. **Three Alex G sources contain zero stop, target and risk rules.** Measure excursion and target-reach, never P&L |
| **Success criteria** | Decisive either way. Low sweep ratio ⇒ waiting for sweeps forfeits most opportunities (Alex G right). Swept approaches materially outperform ⇒ the wait is paid for (TJR right) |
| **Confound to control** | ⚠️ TJR's sweeps are **session-anchored** (pre-market, prior session highs/lows); Alex G's example is a generic weekly zone. **Segment by session context**, or the test compares two different phenomena and settles nothing |
| **Blockers** | Gate + price data only |

---

## RC-21 — Do sweeps cluster at session boundaries? `TRIGGER-ONLY`

**Priority: 2.** The confound-control for RC-20, and independently interesting.

| Field | Specification |
|---|---|
| **Claims** | TJR `\|20260727\|036` (market makers sweep to fill) vs ALEX_G `\|20260728\|022` (no evidence of deliberate liquidation) |
| **Contradiction** | `XCONTRA\|20260728\|002` · mechanism |
| **Method** | Label every zone sweep by time-of-day and session (Asian / London / NY pre-market / NY open). Test whether sweeps cluster at session opens beyond chance |
| **Success criteria** | Significant clustering ⇒ TJR's session-anchored premise has empirical support even if his *causal* explanation remains unevidenced. Uniform distribution ⇒ sweeps are noise and Alex G's scepticism is supported |
| **Important limit** | ⚠️ This can test **whether** sweeps cluster. It **cannot** test **why** — no dataset available to MOGO can establish institutional intent. The mechanism contradiction is empirically unresolvable here and should stay open |
| **Blockers** | Gate + price data with session timestamps |

---

## RC-09 — Full-sequence expectancy

**Priority: last. `BLOCKED` on three prerequisites.**

| Field | Specification |
|---|---|
| **Blockers** | Risk rule (`BACKLOG-002/T1`) · TP ladder (`T2`) · `PROPOSAL-001` |
| **Note** | This is the item everyone wants first and the evidence supports least. Running it before the prerequisites clear requires inventing a risk model and a TP ladder, then reporting the output as TJR's performance. **Do not start it "for a rough idea"** — a rough idea here is indistinguishable from a fabricated backtest |

---

## Reporting requirement

Every completed candidate must produce a `replay_result` `EvidenceItem` linked to the claim it
tested, with the replay run registered as its own `EvidenceSource` (inputs hashed: data range,
instrument, rule version, parameters — see `SPEC-provenance.md` §5). Replay evidence must form a
**distinct independence group** from transcript evidence; that is what makes POLICY-001 route (B)
meaningful. Results re-enter through the normal evidence pipeline and move confidence by the same
mechanism as any other evidence — **never by hand-editing a claim.**

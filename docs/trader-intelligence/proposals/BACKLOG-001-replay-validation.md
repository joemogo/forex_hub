# BACKLOG-001 — Replay Validation Backlog (TJR)

**Status:** Backlog only. **No replay testing has begun and none is authorized.**

> **GATE — do not start any item below until all of the following hold:**
> 1. The knowledge extraction pipeline has been reviewed and approved by the owner.
> 2. An `OwnerDecision` with `replayAuthorization: true` exists (POLICY-001 currently records `false`).
> 3. Licensing on `EVSRC|TJR|20260727|001` is resolved (currently `unknown`, critical).
>
> Items are ordered by **testability given what the transcript actually contains**, not by how
> interesting they are.

---

## What can and cannot be tested today

This distinction governs the whole backlog and is the most important thing on this page.

**Testable now (given price data):** whether a condition *occurred*, how *often*, in what
*sequence*, and whether a stated *invalidation* held. These need only OHLC data and the rule logic.

**NOT testable until further evidence exists:** anything expressed in P&L, win rate, expectancy, or
risk-adjusted return. The transcript contains **no risk-per-trade rule** and **no definition of the
TP1–TP4 ladder**. Without those two, position size and exit levels are unknown, so no P&L figure
can be produced that is not partly invented. Items below are tagged accordingly.

| Tag | Meaning |
|---|---|
| `TRIGGER-ONLY` | Produces occurrence/frequency/sequence results. Runnable once the gate clears. |
| `NEEDS-RISK` | Additionally requires the risk rule (`BACKLOG-002/T1`). |
| `NEEDS-LADDER` | Additionally requires the TP ladder definition (`BACKLOG-002/T2`). |
| `NEEDS-INSTRUMENT` | Additionally requires `PROPOSAL-001` phases A–C. |

---

## RV-01 — Does Step 2B prevent the stop-out it claims to prevent? `TRIGGER-ONLY`

**Priority: highest.** This is the single most specific, most falsifiable, and most original claim
in the entire transcript.

- **Claims:** `CLAIM|TJR|20260727|018` (2B required after a pre-market sweep),
  `CLAIM|TJR|20260727|020` (skipping 2B would have been stopped out)
- **Hypotheses:** the 2B `PROPOSED_UNVALIDATED` hypothesis; `XCONTRA` none
- **Why first:** TJR states a rule, states a causal reason, and demonstrates the counterfactual
  on camera. That combination is rare and directly replayable.
- **Method:** identify all days with a pre-market sweep of a prior session/1h/4h level, then
  compare outcomes of (a) entering on the continuation confluence without waiting for a five-minute
  manipulation, versus (b) waiting for it. Measure stop-out rate and MAE, not P&L.
- **Data:** ES + NQ, 1m and 5m, ≥6 months covering April–October (the period he cites).
- **Success criteria:** (b) shows materially fewer adverse excursions past the stated stop
  reference than (a), across ≥30 qualifying days.
- **Blockers:** none beyond the gate. Stop *reference* is known (swing extreme); stop *distance*
  is not, so measure excursion rather than realized loss.

## RV-02 — Are order blocks and breaker blocks genuinely redundant? `TRIGGER-ONLY`

- **Claim:** `CLAIM|TJR|20260727|038` — removed six months ago; rationale is that price filling an
  FVG or equilibrium hits them anyway.
- **Method:** for every FVG-fill and equilibrium-fill event, test whether an order block / breaker
  block was coincidentally touched. This is a pure geometric redundancy test.
- **Success criteria:** ≥90% coincidence would substantiate the simplification; materially less
  would mean he removed a non-redundant signal.
- **Value:** high and cheap — it validates a *simplification* decision, which is transferable to
  MOGO's own strategies regardless of asset class.

## RV-03 — How permissive is "only one confirmation confluence"? `TRIGGER-ONLY`

- **Claims:** `CLAIM|TJR|20260727|013` (four confluences), `|014` (only one required)
- **Why it matters:** both walkthroughs happened to show nearly all four confluences, but the rule
  requires one. The setup may be far more permissive in practice than the demonstrations imply.
- **Method:** count qualifying setups per month under each policy — any-one-of-four versus
  all-four — and report the frequency ratio and the per-confluence hit distribution.
- **Success criteria:** descriptive, not pass/fail. Output feeds the selection-effect question in
  the research report.

## RV-04 — Does the five-minute trend-intact invalidation hold? `TRIGGER-ONLY`

- **Claim:** `CLAIM|TJR|20260727|022` — after the 5m manipulation, the setup stays valid only while
  price stays in the confirmation-confluence trend.
- **Method:** for each qualifying setup, test whether a close beyond the prior swing reliably marks
  failure. Measure the false-invalidation rate.
- **Note:** this is the only invalidation rule in the entire library. Entry rule
  `CLAIM|TJR|20260727|027` has no companion invalidation in scope — an auto-detected open question.

## RV-05 — Does leading-index selection improve outcomes? `NEEDS-INSTRUMENT`

- **Claims:** `CLAIM|TJR|20260727|004` (trade the leading index), `|005` (definition)
- **Method:** replay identical setups taken on the leading versus the lagging index and compare
  target-reach rate.
- **Blocked by:** `PROPOSAL-001` — this requires modeling two instruments simultaneously with
  correct per-instrument quotation, which MOGO cannot currently express.

## RV-06 — Do targets at "previous draws on liquidity" get reached? `NEEDS-LADDER`

- **Claim:** `CLAIM|TJR|20260727|029`
- **Method:** measure reach-rate for each candidate draw (prior session highs/lows, 1h/4h levels,
  previous-day levels) from each qualifying entry.
- **Partial result available now:** reach-rate per level type is `TRIGGER-ONLY`. Which levels
  constitute TP1–TP4, and therefore realized expectancy, is not.

## RV-07 — Resolve contradiction `XCONTRA|20260727|001` empirically `NEEDS-LADDER`

- **Conflict:** Step 3 stated as required (`|023`) versus the trade taken when equilibrium was never
  hit (`|032`).
- **Method:** replay both interpretations — Step 3 mandatory versus Step 3 optional-when-strong-
  draws-remain — and compare. This is the pre-generated `contested` hypothesis made concrete.
- **Note:** replay can show which interpretation performs better; it **cannot** tell you what TJR
  actually does. Only additional source material can (`BACKLOG-002/T3`).

## RV-08 — Resolve contradiction `XCONTRA|20260727|002` `TRIGGER-ONLY`

- **Conflict:** continuation confluences defined as equilibrium + FVG only (`|024`) versus SMT also
  permitted when 2B is active (`|025`).
- **Method:** measure how often, after a 2B five-minute manipulation, an equilibrium or FVG is
  actually available. His stated rationale is that neither exists in that situation — a directly
  checkable geometric claim.

## RV-09 — Baseline expectancy of the full stated sequence `NEEDS-RISK` `NEEDS-LADDER` `NEEDS-INSTRUMENT`

- **The obvious item, deliberately ranked last.** Running the whole four-step sequence end to end
  and reporting P&L is what everyone wants first and what the evidence supports least.
- **Blocked by all three prerequisites.** Attempting it before they clear would require inventing a
  risk model and a TP ladder, then reporting the results of that invention as TJR's performance.
- **Do not start this item to "get a rough idea."** A rough idea here is indistinguishable from a
  fabricated backtest.

## RV-10 — Discretion gap: stated rules versus demonstrated behavior `TRIGGER-ONLY`

- **Claims:** `CLAIM|TJR|20260727|031` (restart step 2→3), `|032` (take it anyway), `|033`
  (self-described aggression)
- **Method:** replay the literal rules, then measure how far the two documented worked examples
  deviate from them.
- **Why it matters more than it looks:** if the literal rules do not reproduce his own examples,
  then no replay of the literal rules can ever validate his results, and the gap is discretion
  rather than edge. This item calibrates the credibility of every other item on this page.

---

## Data requirements (common)

- ES and NQ, 1-minute and 5-minute OHLC, timestamped in exchange time with session boundaries.
- Coverage of April 1 – October 2 (the period cited) plus a genuine out-of-sample period.
- Session-level derived data: Asian/London/New York highs and lows, previous-day levels, 1h/4h
  swing highs and lows.
- **MOGO currently has none of this** (`dataAvailability: none` for ES/NQ under `PROPOSAL-001`).
  Sourcing it is unscheduled work and is not covered by any existing milestone.

## Reporting convention

Every completed item must produce a `replay_result` `EvidenceItem` linked to the claim it tested,
so that results re-enter the evidence pipeline and can raise or lower confidence through the same
mechanism as any other evidence — never by hand-editing a claim. Under POLICY-001 route (B), this
is the only path by which these claims can legitimately exceed `emerging`.

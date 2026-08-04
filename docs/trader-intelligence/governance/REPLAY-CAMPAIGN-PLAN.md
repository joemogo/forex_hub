# MOGO-004 M1 — Replay Campaign Plan

**Status:** PLAN ONLY — **no replay has been executed or authorized by this document.**
**Yield model source:** RUN-001 (EUR_USD, 4 timeframes, observed window 2026-03-25 → 2026-08-03).

---

## 1. The yield model, and its one assumption

RUN-001 is the only calibration point that exists:

| Setup | Trades produced | Per pair per ~4-month window |
|---|---|---|
| `A_repeatedReaction` (RZR) | 16 | 16 |
| `B_breakRetest` | 8 | 8 |
| **Total** | **24** | **24** |

**Stated assumption:** EUR_USD over this window is representative of other majors. It may not be —
yield depends on volatility and structure, and a single pair-window is a weak basis. Every estimate
below inherits that uncertainty and should be treated as an order of magnitude, not a forecast.

## 2. What "enough" means

A comparison needs **two arms**, each at the minimum operational sample of 30 → **60 resolved trades
per setup type minimum**, 200 for the recommended statistical sample.

| Setup | Have | Operational target | Shortfall | Pair-windows needed |
|---|---|---|---|---|
| RZR | 16 | 60 | 44 | ~3 |
| Break & Retest | 8 | 60 | 52 | ~7 |

**Break & Retest is the binding constraint** — it yields half as many trades and is the setup with
the weaker current result. It should drive campaign design.

## 3. Campaigns, ranked by expected information gain

Ranking criterion: **resolved trades per authorized run, weighted toward the binding constraint and
toward evidence that is currently impossible to obtain.**

### C1 — Multi-pair, current engine *(highest ROI)*
**11 additional majors, same 90-day control, one run each.** Estimated yield ~264 trades (~88 B&R,
~176 RZR). Clears the operational sample for **both** setups in a single campaign, and — critically —
every package carries rule attribution, excursion timing and market context, **none of which RUN-001
has**. This is the only campaign that makes condition-level hypotheses testable at all.
*Estimated runs: 11 · Expected yield: high · Information gain: highest.*

### C2 — Extended window, EUR_USD *(highest yield per run)*
**One 365-day run on EUR_USD.** Estimated ~70–100 trades from a single authorization, and directly
comparable to RUN-001 because only the window changes. Weaker than C1 on breadth: one pair cannot
separate a pair-specific effect from a setup effect.
*Estimated runs: 1 · Expected yield: medium-high · Information gain: high.*

### C3 — Condition-stratified re-run of RUN-001
**Re-run the exact RUN-001 window on the current engine.** Yields the same 24 trades but *with*
attribution, timing and context. Zero new market coverage; converts an existing sample from
uncitable to citable at rule level.
*Estimated runs: 1 · Expected yield: low volume, high quality · Information gain: medium-high.*

### C4 — Market-condition stratification
**Trending vs ranging windows, selected by an objective pre-declared criterion.** Enables the
condition-dependence hypotheses (AXR-002 trend context, session effects). Requires C1 or C2 first —
stratifying a sample this small would produce arms of five trades.
*Estimated runs: 4–8 · Information gain: medium, and only after volume exists.*

### C5 — Additional timeframes / exotic pairs
Lowest priority. Widens surface before the core question is answered.
*Information gain: low.*

## 4. Recommended order

**C1 → C3 → C2 → C4 → C5.**

C1 first because it is the only campaign that clears the binding constraint *and* fixes the
attribution gap. C3 next because it is cheap and makes the existing 24 trades rule-level citable.
C2 for depth on the calibration pair. C4 only once arms can be populated.

## 5. Estimated campaign totals

| | Runs | Est. resolved trades | Clears operational sample? |
|---|---|---|---|
| C1 | 11 | ~264 | **Yes, both setups** |
| C1 + C3 | 12 | ~288 | Yes, plus RUN-001 made citable |
| Full C1–C4 | ~20 | ~400+ | Yes, plus stratification |

## 6. What no replay campaign can deliver

- **Live-only rules** — 4 ALEX rules run on the live paper path; no replay reaches them.
- **Rules with no evidence field** — 4 rules produce no package field at all; a schema change
  (out of MOGO-004 scope) is required before any run can observe them.
- **Independent confirmation** — replay observes one engine over one dataset. Promotion is capped at
  `REPLAY_EVIDENCE_ONLY` regardless of sample size.

## 7. Authorization required

Nothing here is authorized. Each campaign needs an explicit instruction naming pairs, windows and run
count, and each run consumes OANDA practice data retrieval.

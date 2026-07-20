# ADR-007: TJR Strategy Definition (specification gate, pre-implementation)

## Status

**DETECTION IMPLEMENTATION IN PROGRESS.** A single blanket "NOT READY" verdict is no longer
accurate: one component has shipped, and the owner's authoritative architecture process (external
to this document's own conversation record) has since cleared the next detection-only components
for implementation. This ADR records status per component rather than one all-or-nothing line:

| Component | Status |
|---|---|
| TJR Session and Zone Engine (previous Asian/London/New York high/low zones) | **IMPLEMENTED in v12.3.0** — deterministic, DST-aware, no entry/trading-rule interpretation required (see below on why this component needed none of Section B/C resolved first) |
| TJR Zone Interaction and Reaction Engine (how price interacting with a zone becomes a signal) | **APPROVED FOR IMPLEMENTATION** — not yet implemented |
| TJR five-minute BOS confirmation | **APPROVED FOR IMPLEMENTATION** — not yet implemented |
| TJR candidate analytics and grading (scoring/qualification) | **SPECIFIED** — not yet implemented |
| Manual paper approval workflow | **FUTURE GATED PHASE** — not approved for the current release |
| Automatic paper execution | **NOT APPROVED** |
| Live execution | **NOT APPROVED** (permanent boundary, ADR-004) |
| Strategy profitability | **UNVALIDATED** — no trades of any kind have ever been placed under this strategy |
| Historical replay validation | **REQUIRED before any execution automation** is approved, regardless of how the detection/entry rules are specified |

**Provenance of the approval above:** the "APPROVED FOR IMPLEMENTATION"/"SPECIFIED" rows reflect an
explicit owner instruction recording that MOGO's authoritative architecture work — conducted
outside this document's own visible conversation record — approved the Zone Interaction/Reaction
Engine, the five-minute BOS confirmation, and candidate analytics/grading for implementation. This
ADR records that approval as instructed; it does **not** itself resolve Sections B or C below.
**No Phase 2 code was written as part of recording this status** — the approval authorizes a
future implementation pass, not this one, per explicit instruction. When that pass begins, the
specific rule definitions for these components must still be supplied and reconciled against (or
used to resolve) the open questions in Section C below — this status update did not answer any of
them, and they are preserved unchanged for that purpose.

**Why Phase 1 could ship without any of this:** the Session and Zone Engine only computes a
previous session's candle-derived high/low and turns it into a body-to-wick zone — pure
calendar/timezone/OHLC arithmetic. It required none of the trading-rule concepts (liquidity
sweep definition, BOS, FVG, entry trigger, stop/target, risk controls, scoring) that Sections B
and C exist to gate.

Nothing below in Section A is a trading rule; everything that looks like a rule is explicitly a
**proposal awaiting owner approval** (Section B) or an **open question** (Section C). Sections A,
B, and C are unchanged by this status update and are preserved below for reference until the
Zone Interaction/Reaction Engine and BOS confirmation implementation pass actually begins and
either answers or supersedes each item.

This ADR does not register TJR in `STRATEGY_REGISTRY` with any entry/execution capability, create
any trading-decision storage key, write any TJR entry/confirmation/execution production code, or
touch JVM/ALEX/any protected function or constant. `TJR_SLR`'s v12.3.0 registration
(`status:'development'`, scanning/paperTrading/automation all `false`) exists only to host the
Session and Zone Engine described above — see ADR-006 for the registration framework it uses.

---

## A. Confirmed rules

**None.** No TJR trading rule — market scope, sessions, timeframes, bias, liquidity model,
structure confirmation, entry, stop, target, risk, scoring, duplicate-prevention, replay
semantics, or explainability — is confirmed anywhere in this repository or in any prior
conversation with you. The only confirmed facts are architectural, not strategic:

- TJR will be a `STRATEGY_REGISTRY` entry, per ADR-005/ADR-006's now-generalized framework.
- TJR's internal engine will not be forced into JVM's numeric-confluence shape or ALEX's
  categorical zone/touch shape (ADR-005's explicit rule) — it gets its own shape once its actual
  rules exist.
- Onboarding TJR should require, per ADR-006 §4: its own isolated state/storage, its own engine
  functions (added to `PROTECTED_FUNCTIONS` once frozen and reviewed), one Manifest/Services
  pair, one registry entry, and zero edits to the seven seams v12.2.0 generalized.

Everything else below is Section B or C.

---

## B. Proposed rules requiring owner approval

These are common, named conventions from publicly-documented "TJR"/ICT-family retail trading
education — offered here as concrete, falsifiable **starting proposals** so you have something
specific to approve, reject, or correct, not as a claim that this is what you meant by "TJR."
**None of these should be treated as decided.** Each includes the deterministic form it would take
*if* approved, purely so the gap between "an idea" and "a testable rule" is visible.

### B1. Market and pair scope
- **Proposed:** reuse MOGO's existing pair universe scoping pattern — either JVM's `SCAN_PAIRS`
  (12 majors/crosses) or ALEX's pair set, rather than inventing a third list.
- **Deterministic form if approved:** `TJR_SCAN_PAIRS = [...]`, a literal array, no per-pair
  behavioral branching unless approved otherwise.
- **Rejection code:** `pair_out_of_scope`.
- **Open in Section C:** whether TJR should scope to majors only, all 34 `ALL_PAIRS`, or a
  custom list; whether any pair gets different session/risk treatment.

### B2. Trading days and sessions
- **Proposed:** mirror JVM's Mon–Wed preference model (`isPreferredTradingDay()`) and session
  gate (`getSession()`, London/NY overlap priority) as a starting point, since both already exist,
  are tested, and are UTC-based (no DST ambiguity — `getSession()` reads `getUTCHours()`, so DST
  never needs separate handling as long as the session boundaries stay defined in UTC).
- **Deterministic form if approved:** exact copy of `getSession()`'s UTC minute-boundary logic,
  or a new TJR-specific set of boundaries if TJR's real session model differs.
- **Rejection codes:** `weekday_blocked`, `session_blocked`.
- **Open in Section C:** whether TJR trades a different session set (e.g., only the New York
  session, or only around a specific macro release time); whether a news blackout window is
  required (JVM has none enforced today — see `docs/KNOWN_ISSUES.md`'s disclosed gate gaps).

### B3. Timeframes
- **Proposed:** a three-tier model analogous to JVM's (higher-timeframe bias → structural
  zone/AOI timeframe → entry-trigger timeframe), since this is the shape both existing strategies
  already use and the shape "TJR-style" retail education commonly describes (HTF bias, a
  intermediate structure timeframe, a lower entry timeframe).
- **Deterministic form if approved:** three named constants, e.g. `TJR_BIAS_TF`, `TJR_STRUCTURE_TF`,
  `TJR_ENTRY_TF`, each a literal OANDA granularity string.
- **Open in Section C:** the actual timeframes (this proposal names a *shape*, not values —
  supplying "4H bias / 15M structure / 1M entry" here would be fabricating specifics with no
  source).

### B4. Directional bias
- **Proposed shape:** binary bullish/bearish/neutral, derived from the bias timeframe(s), no
  trade in the neutral case — the same shape JVM (`getBias()`) and ALEX both already use.
- **Open in Section C:** the exact bias-derivation rule (a single-timeframe read? multi-timeframe
  agreement, like JVM's 2-of-3? something liquidity-driven, like "which side was swept last"?).

### B5. Liquidity model
- **Proposed vocabulary** (common ICT/TJR-adjacent terms, offered only as vocabulary to
  confirm/reject, not as implemented rules): prior session/day/week high-low as external
  liquidity; equal highs/equal lows as a liquidity pool; a "sweep" as price trading through such a
  level and closing back on the other side within some bar count.
- **Nothing here is quantified.** No tolerance for "equal" highs/lows, no definition of "closing
  back," no bar-count limit exists yet — see Section C.

### B6. Market-structure confirmation
- **Proposed vocabulary:** a swing point identified via a local high/low over some lookback
  window (MOGO already has a generic `findSwingPoints(candles, lookback)` — protected, JVM-only
  today, but the *algorithm shape* could inform a TJR-specific equivalent); a "structure shift"
  as price closing beyond the most recent opposing swing point.
- **Nothing here is quantified** (lookback window, wick-vs-close requirement, minimum displacement
  size) — see Section C.

### B7. Entry model
- **Proposed vocabulary:** entry on a retracement into a fair-value-gap or order-block formed
  during the displacement leg, confirmed by a lower-timeframe candle close.
- **Nothing here is quantified** (FVG minimum size, order-block selection rule, limit vs. market
  fill, max bars after the sweep, whether a missed entry can be chased) — see Section C.

### B8–B13 (Stop loss, targets/management, risk controls, scoring, duplicate-prevention, replay
semantics): **no proposal offered.** These require numeric/behavioral specifics (buffer size,
R-multiple, max concurrent positions, daily loss limit, scoring weights, cooldown duration,
same-candle stop/target tie-break) that would be pure invention without a source. Proposing a
default here would cross into "fabricating rules to complete the document," which you explicitly
prohibited. These are listed only in Section C.

### B14. Paper-trading behavior
- **Proposed:** reuse the existing `commitPaperLedger()`-style atomic commit contract (snapshot →
  mutate → journal → guarded save → rollback-on-rejection), the same pattern JVM/ALEX both already
  use, generalized to a TJR-owned account object rather than a new transaction model.
- **Deterministic form if approved:** a `tjrAccount` object, its own guarded save function
  (`commitTjrLedger()` or a shared generalization — an implementation-time decision, not a spec
  decision), isolated from `paperAccount`/`alexGAccount` per ADR-002.
- This is the one category where a proposal is offered with high confidence, since it's an
  architectural pattern already proven twice, not a trading rule.

### B15. Explainability
- **Proposed:** follow the same funnel/rejection-reason-code pattern already established by
  `evaluateSetupFullBreakdownCore()`/`classifySetupEligibility()` (v12.1.2) — a full,
  non-short-circuiting breakdown with one primary rejection reason and machine-readable stage
  labels, ready to feed a future Decision History release.
- **Deterministic form if approved:** each rule category above gets exactly one rejection code
  (see the `Rejection code` line already given per category); no rule may share a code with
  another.

---

## C. Unknown or ambiguous rules (require your input before B can be finalized)

Every quantified value below is currently unknown — not defaulted, not guessed:

1. Exact pair list and any per-pair exceptions.
2. Exact session window(s) and whether they differ from JVM's.
3. Whether a news blackout is required, and if so, its data source.
4. The three (or more) timeframe roles and their actual values.
5. The exact bias-derivation rule and what makes a "neutral" (no-trade) state.
6. What counts as a valid liquidity level (equal-high/low tolerance in pips or %; whether
   session/day/week highs-lows all count or only some).
7. Internal vs. external liquidity distinction, if any, and whether it changes entry weighting.
8. The exact, objective sweep definition (wick-through vs. close-through; how many bars the
   close-back-inside must happen within).
9. The exact swing-point algorithm (lookback bars; strict vs. equal-high tolerance).
10. The exact structure-shift/break-of-structure definition (close-based vs. wick-based; minimum
    displacement size, in pips or ATR multiples).
11. The exact entry trigger (FVG minimum size and how staleness is defined; order-block selection
    rule if multiple exist; candle-confirmation requirement, if separate from the FVG/OB itself).
12. Limit vs. market entry, and — if limit — how long an unfilled limit order remains valid.
13. Maximum bars/time allowed between the sweep (or structure shift) and a valid entry.
14. Whether a "missed" entry (price ran past the zone without filling) may ever be chased, and if
    so, how.
15. Stop-loss placement rule and buffer (fixed pips? ATR-based? beyond the sweep wick?).
16. Minimum and maximum acceptable stop distance, if any.
17. Spread treatment in stop/target math (JVM fills at real bid/ask; does TJR need the same, and
    does spread affect stop placement itself?).
18. Target rule: fixed R-multiple, next opposing liquidity level, or something else.
19. Partial-exit rules, if any (size split, trigger price, whether MOGO's paper-account model
    even needs to support partials — it doesn't today for JVM/ALEX).
20. Break-even rule (trigger condition, exact new stop price).
21. Trailing-stop rule, if any.
22. Maximum holding time and/or forced end-of-session closure rule.
23. Risk-per-trade percentage.
24. One-position-per-pair vs. a different concurrency rule.
25. Total concurrent-position cap across all pairs.
26. Daily loss limit / circuit breaker, if any (JVM and ALEX both currently have none enforced —
    see `docs/KNOWN_ISSUES.md`).
27. Maximum trades per session/day.
28. Correlated-pair exposure restrictions, if any.
29. Whether TJR is strictly pass/fail or scored; if scored, every component and its weight, and
    the minimum qualifying threshold — none of this exists yet even as a shape.
30. Cooldown duration and same-liquidity-event re-trigger handling.
31. Re-entry rule after a stop-out or a missed target on the same setup.
32. Replay-specific tie-break for a candle that touches both stop and target (JVM's Replay
    engine has its own resolved convention — does TJR reuse it or need its own?).
33. Spread/slippage assumption for Replay fills.
34. Warm-up history requirement (minimum candles before a decision is trusted) per timeframe.
35. Whether "incomplete" (still-forming) candles are ever evaluated, or only closed ones.

Until these are resolved, no acceptance criteria in Section B can be made testable, and no
implementation can proceed without a developer silently deciding on your behalf.

## D. Explicit non-rules

Stated plainly so no future implementer assumes otherwise:

- TJR will **not** place real orders — paper-only, same permanent boundary as JVM/ALEX
  (ADR-004).
- TJR will **not** share `paperAccount`/`alexGAccount`, `journalEntries`/`alexGJournalEntries`,
  or any existing storage key — full isolation per ADR-002, no exceptions.
- TJR will **not** be forced into JVM's confluence-score shape or ALEX's zone/touch shape merely
  for symmetry (ADR-005).
- TJR will **not** be registered, wired, or given any storage key by this document — this is a
  specification artifact only.
- Nothing in Section B is authorized for implementation by virtue of appearing in this document —
  Section B items require your explicit, itemized approval (see the question list below), not a
  blanket "looks fine."

---

## Decision table (structure only — inputs are placeholders until Section C resolves)

| Bias | Liquidity sweep? | Structure shift confirmed? | Valid entry trigger formed? | Session/risk gates pass? | Outcome |
|---|---|---|---|---|---|
| Bullish | Yes (sell-side swept) | Yes | Yes | Yes | **Valid long** |
| Bearish | Yes (buy-side swept) | Yes | Yes | Yes | **Valid short** |
| Bullish | Yes | **No** | — | — | **Rejected** — `structure_not_confirmed` |
| Bullish | Yes | Yes | **No** (no retracement into a valid entry zone) | — | **Rejected** — `no_valid_entry` |
| Bullish | Yes | Yes | Yes | **No** (outside session, or risk gate fails) | **Rejected** — `session_blocked` / `risk_gate` |
| Any | Yes | Yes | Formed, but price moves past it unfilled beyond the max-bars window | — | **Expired** — `entry_window_expired` |
| Neutral (no bias) | — | — | — | — | **Rejected** — `no_bias` |

This table's *shape* (bias → sweep → structure → entry → gates → outcome) is a reasonable
pipeline order to propose, mirroring JVM's own gate-ordering discipline — but every cell's
trigger condition depends on the still-unknown definitions in Section C, so the table cannot be
turned into code yet.

## Worked hypothetical examples

All five are illustrative only — built to exercise the decision table's shape, not derived from
any confirmed TJR rule. Numeric values are placeholders (marked `[PLACEHOLDER]`) precisely so they
are not mistaken for approved specifics.

1. **Valid long (hypothetical):** Daily bias reads bullish. Price sweeps the prior session low by
   `[PLACEHOLDER: X pips]` and closes back above it within `[PLACEHOLDER: N bars]`. A structure
   shift is confirmed when price closes above the prior swing high. Price retraces into a
   `[PLACEHOLDER: FVG/order block]` formed during the displacement leg, and a lower-timeframe
   bullish confirmation candle closes inside it. Session and risk gates pass. → **Valid long**,
   entered at the confirmation candle's close, stop below the sweep wick, target at
   `[PLACEHOLDER: next external liquidity / fixed R]`.
2. **Valid short (hypothetical):** Mirror of (1) — bearish bias, buy-side sweep, structure shift
   down, retracement entry, gates pass. → **Valid short.**
3. **Liquidity sweep without structure confirmation:** Price sweeps the prior day's low, closes
   back above it, but never closes beyond the prior swing high (structure never actually shifts —
   price stays range-bound). → **Rejected**, `structure_not_confirmed`. No entry is ever
   evaluated, matching how JVM's evaluator only proceeds gate-by-gate on real passes (see the
   v12.1.2 non-short-circuiting evaluator precedent for *why* this matters for diagnostics: this
   setup should be classified precisely, not lumped into a generic rejection).
4. **Structure confirmation without valid entry retracement:** Structure shifts cleanly, but
   price never retraces into the proposed entry zone at all (it continues directly in the new
   direction) — or retraces through it without the required confirmation candle forming. →
   **Rejected**, `no_valid_entry`. Whether "continued without retracing" should instead become
   `entry_window_expired` (if some bar count elapses first) is exactly the kind of ordering
   ambiguity Section C leaves open (item 13).
5. **Otherwise-valid setup rejected by session/risk control:** Bias, sweep, structure, and entry
   all confirm cleanly — but the setup occurs outside the (currently undefined) permitted session
   window, or a risk gate (daily loss limit, max concurrent positions — both currently undefined)
   is active. → **Rejected**, `session_blocked` or `risk_gate` respectively. This example exists
   specifically to show that a technically-clean setup is not automatically a trade — the same
   principle JVM's Mon-Wed preference gate and Manual Review Eligible workflow already established
   for this codebase.

---

## Direct questions requiring your approval before any implementation

1. Which pairs should TJR scan — JVM's 12, all 34, or a different list?
2. What are TJR's actual session windows, and does it need a news blackout?
3. What are the three (or more) timeframes, and what role does each play?
4. How is directional bias derived, and what makes it "neutral"?
5. What is the objective, numeric definition of a liquidity sweep (tolerance, close-back
   requirement, bar limit)?
6. What is the objective swing-point/structure-shift algorithm (lookback, wick vs. close,
   minimum displacement)?
7. What is the exact entry trigger (FVG/order block formation and invalidation rules; candle
   confirmation requirement; limit vs. market; max bars before the entry expires; whether a
   missed entry can be chased)?
8. What is the stop-loss placement rule and buffer, and are there min/max distance limits?
9. What is the target rule (fixed R, structural, partials, break-even, trailing, max hold time,
   forced session-close)?
10. What are the risk controls (risk %, concurrency limits, daily loss limit, max trades/day,
    correlated-pair restrictions)?
11. Is TJR pass/fail or scored — and if scored, what are the components, weights, and threshold?
12. What are the cooldown and re-entry rules after a loss, a missed target, or a duplicate
    liquidity event?
13. What are the Replay-specific tie-break, spread/slippage, and warm-up history assumptions?
14. Should any of the above reuse an existing JVM/ALEX mechanism verbatim (e.g., session gate,
    ledger-commit pattern), or does TJR need its own for every item?

## Implementation-readiness verdict

**Per-component, not blanket** (see the Status table at the top — this section restates it as an
explicit READY/NOT READY/CLEARED verdict rather than a new judgment):

- **TJR Session and Zone Engine: READY — implemented in v12.3.0.** This component needed none of
  Section B/C resolved, since it contains no trading-rule interpretation (see "Why Phase 1 could
  ship" above).
- **TJR Zone Interaction and Reaction Engine and TJR five-minute BOS confirmation: CLEARED FOR A
  FUTURE IMPLEMENTATION PASS, NOT YET BUILT.** Cleared per the owner's authoritative architecture
  process (see "Provenance of the approval" above) — but **not implemented in v12.3.0**, and this
  status update performed no Phase 2 work. Before that future pass writes any code, the relevant
  open questions in Section C (at minimum questions 5–7, covering liquidity-sweep definition,
  BOS/swing-point algorithm, and entry-trigger mechanics) must still be resolved or explicitly
  superseded by whatever specified the approved architecture — this document does not yet contain
  those answers.
- **TJR candidate analytics and grading: SPECIFIED, NOT YET BUILT** — same caveat: Section B11
  (pass/fail vs. scored, weights, threshold) remains an open question this document doesn't
  answer.
- **Every remaining component (paper approval workflow, automatic paper execution, live execution,
  duplicate-prevention, replay semantics, profitability): NOT READY / NOT APPROVED**, unchanged —
  see the Status table.

The overall "canonical TJR Strategy Specification" is **still not complete** purely as a
document: Sections A, B, and C below are unchanged from this ADR's original version, and no
answer to any of the 14 direct questions has been recorded in this repository or in this
conversation. What changed is that implementation of two specific components has been cleared to
proceed by the owner's own authoritative process outside this record, once that future pass
supplies the missing rule detail — not that the questions themselves have been answered here.

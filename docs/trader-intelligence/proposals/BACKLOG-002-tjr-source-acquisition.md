# BACKLOG-002 — TJR Source Acquisition Task List

**Status:** Task list only. **No acquisition has been performed and no source has been ingested.**
**Purpose:** identify exactly what additional TJR material is needed to raise claim confidence above
`emerging` (POLICY-001 route A), and which specific gap or question each source would close.

---

## Standing constraints

**C-1 — Do not ingest before licensing is resolved.** `EVSRC|TJR|20260727|001` is
`licensingStatus: unknown` and sits in the `unresolved_licensing` queue at **critical**. Ingesting a
second transcript would multiply that exposure. **Register candidates as `storagePolicy:
METADATA_ONLY` now; do not store transcript text until licensing is settled.** Metadata-only
registration is explicitly supported by the acquisition engine and costs nothing to reverse.

**C-2 — Registration is offline and manual.** The acquisition engine has zero network capability by
design. Every candidate is registered by hand via `register_source.py` with
`discoveryMethod: MANUAL_URL` (or `PLAYLIST_URL` / `CHANNEL_URL`).

**C-3 — Same-author corroboration is weaker than it scores.** Two TJR videos create two
independence groups and can carry a claim to `supported` (44 → 45 pts). That corroborates *that he
says it consistently*, not *that it works*. See POLICY-001 §G1 — if you want same-author sources
discounted, set `EvidenceClaimLink.independenceGroup` to a per-author key at registration time.
**Decide this before the second intake, not after.**

**C-4 — Record at registration:** canonical URL, video ID, channel, publication date, duration,
`creatorName`, `claimedTraderId: TJR`, `authenticityStatus`, `contentOrigin:
THIRD_PARTY_OWNER_PROVIDED`, and `metadataConfidence: owner_provided`. The first intake has
`canonicalReference: null`, which is precisely why its licensing cannot be assessed — do not repeat
that.

---

## Priority 1 — Sources that close **critical** gaps

### T1 — Risk management material *(highest value of any item in this backlog)*

- **Closes:** `risk_percentage` gap (**critical**, currently `unanswered`); open question
  `EQ|20260727|001`; blueprint `riskLogic.missingRiskRules`; profile `riskConcepts: []` (empty)
- **Why critical:** with no risk rule, position size is unknown, so **no P&L replay is possible**
  (`BACKLOG-001/RV-09` is blocked entirely). This single gap blocks more downstream work than any
  other.
- **What to look for:** TJR content on risk per trade, position sizing, or account management. The
  first transcript points at this directly — he describes teaching *"how to dissect what your win
  percentage is and what your risk-to-reward is and how to use both of those together to be able to
  calculate a proper risk amount."* That material exists; it was withheld as mentorship content.
- **Acceptance:** a stated risk figure or formula → one `risk_rule` claim.
- **Caution:** if this only exists inside the paid mentorship, C-1 becomes sharper, not softer.
  Paid-product terms typically prohibit redistribution.

### T2 — Trade recaps (daily) *(highest value for behavioral truth)*

- **Closes:** `EQ|20260727|003` (TP1–TP4 ladder undefined); `CLAIM|…|030` corroboration;
  `BACKLOG-001/RV-06`, `RV-07`, `RV-09`; and the discretion gap (`RV-10`)
- **Why:** the transcript states he records *"trade recaps that I upload on a daily basis… telling
  you guys when I enter, when I exit, the exact P&L."* These are **demonstrated behavior on real
  trades**, not instruction — evidentially the strongest TJR material that exists.
- **Distinct value:** the two examples in the first intake are retrospective narrations of days he
  did **not** trade. Recaps are days he **did**. That difference is the entire basis for measuring
  the stated-versus-executed gap.
- **Target:** 20–30 recaps spanning winners and losers.
- **Acceptance:** `demonstrated_behavior` / `trade_example` evidence with entries, exits, and target
  placement → resolves the TP ladder and provides real discretion data.
- **Priority dimensions:** `tradeFailureInsightPotential` (12), `paperTradingLearningPotential` (8),
  `chartExampleDensity` (8).

## Priority 2 — Sources that resolve contradictions

### T3 — Material clarifying whether Step 3 is mandatory

- **Closes:** `XCONTRA|20260727|001` (**material**, `open`) — currently blocks rule candidacy for
  every affected claim
- **Why:** an open contradiction sets `contradictionStatus: open_contradiction` on any proposal,
  which blocks candidacy outright. **Replay can show which interpretation performs better; only
  source material can show which one he actually follows.**
- **What to look for:** any content restating the continuation-confluence requirement, especially
  examples where equilibrium/FVG did *not* fill.

### T4 — Material clarifying the 2B continuation-confluence set

- **Closes:** `XCONTRA|20260727|002` (`minor`, `open`); `EQ|20260727|009` (step ordering when 2B is
  active); `BACKLOG-001/RV-08`
- **What to look for:** the promised further 2B examples — *"you guys are going to see so many
  examples of this"* — which would also corroborate `CLAIM|…|018`/`|020`, the highest-value replay
  item.

## Priority 3 — Long-form sources that corroborate definitions broadly

### T5 — The 5.5-hour and 9-hour long-form videos *(named in the transcript)*

- **Closes:** corroboration for all 8 `definition` claims (`|005`, `|007`, `|015`, `|016`, `|017`,
  `|024`, plus `|003`); `higher_timeframe_bias` gap (**high**)
- **Why:** he names these explicitly — *"I have a 5 and a half hour long video. I also have a 9-hour
  long video."* Long-form instructional content has the highest `ruleExtractionPotential` (weight
  18) per source.
- **Caution:** high duration means high extraction cost. **Do not ingest whole.** Recommend
  targeted section extraction against named gaps — the segmentation model already supports partial
  intake via `transcriptCompleteness: partial`.
- **Acceptance:** ≥6 of the 8 definition claims independently corroborated → those reach `supported`.

## Priority 4 — Sources closing medium-priority behavioral gaps

### T6 — News handling and no-trade conditions

- **Closes:** `EQ|20260727|007` (what happens when high-impact news *is* present);
  `no_trade_conditions` gap; `volatility_handling` gap; corroborates `CLAIM|…|040`
- **Why:** the news check is `indirect_implied`, demonstrated exactly once, with **no stated
  consequence**. Currently one of only three inferred claims in the library.
- **What to look for:** content on trading around news, or an explicit "days I don't trade" rule.
  He was observed abstaining during a government shutdown but stated no rule (`CLAIM|…|041`).

### T7 — Stop-placement specifics

- **Closes:** `EQ|20260727|002` (exact swing reference and buffer); corroborates `CLAIM|…|028`
- **Why:** both stop excerpts are chart-relative (*"underneath this low"*). A rule cannot be coded
  from a pointing gesture.

---

## Explicitly NOT wanted

The priority profile penalizes `promotionalContentScore`, `lifestyleContentScore`, and
`genericMotivationScore`. **§24 of the first transcript is ~7,000 characters of mentorship pitch and
produced zero claims** — a useful calibration. Avoid: results/lifestyle content, motivational
material, third-party summaries of TJR (`lowAuthoritySummaryPenalty`, and they would fail
`authenticityStatus: VERIFIED_PRIMARY`), and re-uploads of already-ingested material
(`duplicationPenalty` — the duplicate detector will catch exact matches, but not a re-cut).

---

## Suggested sequencing

| Step | Action | Gate |
|---|---|---|
| 0 | Resolve licensing on the existing source | **Blocks everything below** |
| 1 | Decide the `independenceGroup` policy (C-3) | Before any second ingest |
| 2 | Register T1–T7 as `METADATA_ONLY` candidates; run `prioritize_sources.py` | None — safe now |
| 3 | Owner reviews the ranked queue and approves 2–3 for content acquisition | `OwnerDecision`, `decisionType: acquisition` |
| 4 | Ingest approved sources through the reviewed pipeline | Requires Priority-3 pipeline review complete |

---

## Scope expansion under `DECISION|MOGO|20260727|004`

Equal evidence-source standing for ICT, TJR, JVM, ALEX G, and future educators makes acquisition a
**multi-educator** activity. Two consequences reorder the priorities above.

### A second-educator source now outranks TJR source #2

Under equal standing, a **non-TJR** source is genuinely independent in a way a second TJR video is
not (POLICY-001 §G1 — same-author corroboration proves consistency, not correctness).

| Target | Closes | Priority |
|---|---|---|
| **T8 — Primary ICT source** | Corroborates 6–8 TJR *definitional* claims at once (liquidity sweep, FVG, BOS, equilibrium, order block); establishes whether TJR's framework is original or inherited | **Highest of any acquisition** |
| **T9 — Alex G primary source** | `ALEX_G.externalResearchStatus: not_started`. MOGO ships an ALEX_G engine but holds **zero evidence of what Alex G actually teaches** | High |
| **T10 — JVM source (if one exists)** | See caveat below | Low / possibly N/A |

**T8 rationale** is recorded in `traders/ict/profile.json` and `CROSS-STRATEGY-ANALYSIS.md` §7. It is
an *acquisition hypothesis*, not a finding — MOGO holds no evidence for it.

**T9 is the sharper governance point.** MOGO runs a live paper-trading engine attributed to a named
external educator, while holding no ingested material from that educator. Under equal standing,
`SF|ALEX_G|SUPPORT_RESISTANCE_V1` describes *what MOGO implemented*, not *what Alex G teaches* —
and nothing currently establishes that these agree. That gap existed before this decision; the
decision makes it visible.

**T10 caveat:** JVM carries alias `current_strategy` and is described as *"MOGO's original numeric
confluence-scoring engine"*. It may be MOGO-original with no external source to acquire. If so, that
should be recorded explicitly rather than left ambiguous — under equal standing, "MOGO's own idea"
is a legitimate provenance, but it must be *stated*, not inferred from an empty directory.

### Implementation facts are not trader evidence

Repository-confirmed facts (`WEIGHTS`, engine behaviour, shipped functions) are evidence about
**MOGO's code**. They must never be registered as evidence of an educator's method. If MOGO wants
to know what JVM or ALEX G assert, that requires real source material — exactly as it did for TJR.

## Acquisition lesson from source #2 (2026-07-27)

Source #2 (TJR Day 3 — beginner foundations) produced **23 new claims and zero confidence
movement**. It defines the vocabulary source #1 assumed (highs, lows, trends, candle anatomy) but
restates none of its strategy rules, so nothing was corroborated.

**Two distinct acquisition goals, which should be prioritised separately:**

| Goal | Prefer | Effect |
|---|---|---|
| **Raise confidence** | Sources that *restate the same rules* — strategy walkthroughs, trade recaps | Moves claims off the `emerging` floor |
| **Improve comprehension** | Foundational/curriculum material | Fills definitional gaps; adds claims, moves no confidence |

T2 (daily trade recaps) is the best-specified confidence-raising target already on this list. Later
episodes of the same beginner series will mostly serve comprehension — valuable, but they will not
lift the ceiling.

## ALEX_G acquisition targets (opened 2026-07-27 by `EVSRC|ALEX_G|20260727|001`)

Alex G is now the **highest-priority educator** in the queue: he is the only one whose method MOGO's
current FX engine could express, and the only one with an open governance question against shipped
code.

| ID | Target | Closes | Priority |
|---|---|---|---|
| **A1** | **Alex G risk / stop / target material** | The source states **no stop rule, no target rule, no risk rule at all** — a strictly larger gap than TJR's. Blocks every P&L replay of his method | **Critical** |
| **A2** | **Any second Alex G source** | The only route that currently raises confidence on his 35 claims (same-educator corroboration). Also the evidence base for D1 | **Critical** |
| **A3** | Alex G material on Break & Retest / Repeated Zone Reaction | Directly answers **D1** — whether MOGO's shipped ALEX_G engine matches what he teaches. The ingested source teaches something different-looking | **High** |
| **A4** | Alex G material defining the top-down "overall score" | The scoring step is the stated output of his whole procedure and is entirely unspecified | **High** |
| **A5** | Alex G material on support/resistance | He ends with *"when you're above support, you buy"* — a second vocabulary never reconciled with the HH/HL model he teaches | Medium |

**Note on A2 and POLICY-001 §G1.** Same-author corroboration proves consistency, not correctness —
but it is the *only* mechanism that currently moves confidence, since cross-educator agreement does
not (F27). That asymmetry is itself an argument for the Concept-consensus proposal in
`CROSS-STRATEGY-ANALYSIS.md` §8 D2.

**Confirmed by experience (cycles 006–007):** foundational content defines, strategy content
corroborates. TJR #2 added 23 claims and moved zero confidence. Alex G #1 added 35 claims and moved
zero confidence. **Three sources, no confidence movement whatsoever.** Acquisition must now target
*restatement* — a second source by the same educator covering the same rules — or replay.

## A2-LIVE — **Prioritise live sessions over instructional videos** (opened 2026-07-28, cycle 013)

**Target:** further **live session recordings** from `@fxalexg__` — the "learn and earn" / morning
breakdown format, and the playlist source #7 belongs to
(`PLi54qmfu-okqa3TmCy5Bn89fRTke7pKFF`).

**Why this now outranks further instructional videos.** Six instructional sources produced a
complete-looking rule set. **One live session produced three filters that appear in none of them** —
a proximity tolerance, a two-sided confluence count, and "worth the risk" selectivity — plus the
library's first contradiction between a stated rule and recorded behaviour.

> Instruction gives the rule set. Practice gives the filters. The library now has direct evidence
> that the second is not derivable from the first.

**What to extract from each.** Every declined setup and the reason given; every distance judgement;
every case where a mechanically-valid setup is skipped. **The skips are worth more than the entries**
— an entry confirms a rule already captured, a skip reveals a filter that is not.

⚠️ **Expect the parameters to be visual.** Three sources running, this educator's rule parameters are
**shown on screen rather than spoken**: the session volume map (#5), the setup grading scale (#4),
the written confluence list (#7). A transcript-only pipeline will keep capturing rule *shapes*
without their *numbers*. If the owner wants those numbers, transcripts are the wrong instrument and
that should be an explicit decision rather than an accumulating gap.

---

## A1-STOP — **The single highest-value acquisition target in the library** (opened 2026-07-28, cycle 012)

**Target:** any ALEX_G source that states **where the stop-loss is placed.**

**Why this outranks everything else in this document, including a second educator:**

Six Alex G sources now describe a method that is complete at every layer except one — direction,
zone, trigger, session, day-of-week, target distance, and (after source #6) risk sizing in three
banded percentages. **`stop_rule` is still 0.**

Position size = risk amount ÷ stop distance. The library has the first term and not the second, so:

- **No Alex G claim can be replayed for P&L.** RC-12 through RC-27 — sixteen candidates — measure
  trigger accuracy, reach-rate, frequency or direction. Not one can produce an expectancy.
- **One video's worth of material would unlock P&L replay for all six sources at once.** No other
  single acquisition in this document has that leverage.

**What would satisfy it.** An explicit statement of stop placement: beyond the structure point,
beyond the wick, a fixed distance, an ATR multiple — any of these. It does **not** need to be a full
strategy video; a single unambiguous sentence would close the gap.

**Search terms:** "stop loss placement", "where to put your stop loss", "lot size calculator",
"position sizing", "risk to reward setup" on `@fxalexg__`.

⚠️ **Accept the negative result if it comes.** It is entirely possible that no free Alex G source
states stop placement — the pattern across six sources is that free content stops where risk begins,
and the detail is deferred to a paid programme. **If a reasonable search finds nothing, record that
as a finding and stop looking**, rather than letting the gap sit open indefinitely as though it were
merely unsearched. That negative result is itself worth recording: it would establish that this
educator's published material cannot support a P&L-validated rule, which is a permanent constraint
on what MOGO can derive from the channel.

**What must NOT happen while this is open.** Source #5's 80–100 pip average target and source #6's
1:2 / 1:3 worked ratios together imply a ~27–50 pip stop. **That inference is forbidden** — both
ratios are illustrative arithmetic, the pip figure is a past average, and combining two descriptive
statements into a prescriptive third invents a rule and attributes it to someone who did not state
it.

---

## Expected effect on confidence

| Sources ingested | Independent groups | Best achievable state |
|---|---|---|
| 1 (today) | 1 | `emerging` (22 pts) |
| +1 corroborating | 2 | `supported` (45 pts, with one extra corroborating item) |
| +2 corroborating, several items | 3 | `strongly_supported` (75 pts) |

**Only claims a new source actually corroborates move.** A risk-management video does not raise the
SMT-divergence definition. Expect a *patchy* confidence landscape after the second intake, not a
uniform lift — which is correct behaviour, and worth anticipating so it does not read as a bug.

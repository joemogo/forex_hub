# MOGO-002.7 — Blocking-Gap Source-Acquisition Checklist

**Milestone:** MOGO-002.7 — Source Acquisition for Blocking Gaps · **Phase 1**
**Date:** 2026-07-29 · **HEAD:** `a332d04` (milestone work uncommitted)
**Scope:** `ALEX_G` educator library only — 195 claims, 244 evidence items, 8 registered sources.

> **This checklist is evidence-derived, not summary-derived.** Every count below was recomputed from
> the evidence store on disk (`docs/trader-intelligence/evidence/`), not copied from the MOGO-002.6
> package. Where this checklist disagrees with a MOGO-002.6 figure, the disagreement is stated.

---

## 0. Method

For each of the ten blocking domains named in the MOGO-002.7 brief, every `ALEX_G` evidence item was
matched against domain-specific patterns over **both** `exactExcerpt` (the verbatim source text) and
`normalizedObservation` (MOGO's interpretation), then traced through
`links/` → `claims/` to recover `claimType`, and through `metadata.annotationId` → `annotations/`
to recover the recorded open question.

Every quotation in this document is an `exactExcerpt` — verbatim educator speech with a timestamp and
a registered source. **No excerpt is paraphrased, completed, or repaired.**

**Library-wide claim-type census, recomputed** (this is the load-bearing measurement):

| `claimType` | ALEX_G | RAYNER_TEO | TJR |
|---|---|---|---|
| **`stop_rule`** | **0** | **6** | **1** |
| `risk_rule` | 13 | 4 | 0 |
| `target_rule` | 4 | 2 | 1 |
| `trade_management_rule` | 4 | 0 | 1 |
| `invalidation_rule` | 9 | 2 | 1 |
| `session_rule` | 7 | 2 | 1 |
| `entry_rule` | 20 | 5 | 1 |
| `setup_requirement` | 23 | 6 | 9 |
| `confirmation_rule` | 9 | 3 | 6 |
| `failure_condition` | 19 | 2 | 2 |
| `definition` | 15 | 8 | 20 |
| `behavioral_observation` | 26 | 5 | 9 |
| `causal_hypothesis` | 18 | 0 | 7 |
| `performance_hypothesis` | 14 | 0 | 6 |
| `exception` | 7 | 0 | 4 |
| `timeframe_rule` | 3 | 1 | 0 |
| other / `marketCondition` | 4 | 0 | 0 |

**`ALEX_G` `stop_rule` count is 0 across 8 sources.** This is now confirmed by direct census of the
claim store, independently of MOGO-002.6's reporting.

---

## 1. The checklist

Ten rows, one per blocking domain in the brief. Priority is ordered by **whether the domain blocks a
computable trade**, not by how much material is missing.

---

### BG-01 · Stop-loss placement → `KEGAP-001` / `GAP-RISK-001`

| Field | Value |
|---|---|
| **Domain** | RISK (stop placement) |
| **Exact missing question** | **Where is the stop-loss placed relative to the structure that produced the setup?** Specifically: which price is the reference (zone boundary, wick extreme, body extreme, rejection candle low/high), and what buffer — if any — is added beyond it? |
| **Why it blocks specification** | Position size = risk amount ÷ **stop distance**. The library holds the first term in three banded percentages and **not the second**. Therefore not one of the 13 `risk_rule` claims is implementable, and **no ALEX_G claim can be replayed for P&L** — every candidate measures hit-rate only. |
| **Evidence already available** | **5 evidence items mention a stop; none places one.** `EVSRC\|ALEX_G\|20260728\|001` [16:03–17:32] establishes only that the stop needs *room*: *"how much more can this move go how long can we have on our stop-loss on a takeprofit"*. `EVSRC\|ALEX_G\|20260727\|001` [14:48–16:26] establishes that a wrong trend origin *invalidates* the stop: *"they're wrong about where it's bullish from. And that completely changes"*. The remaining 3 matches are an opinion on liquidity-sweep narratives, an unsourced 3%-of-market statistic, and the phrase *"stop losing money"* — a lexical false positive. |
| **Minimum evidence to close** | **One** ALEX_G statement or on-chart demonstration that names the stop's reference price **and** its buffer. A demonstration counts only if the reference is unambiguous from the spoken words; a chart gesture with no spoken reference yields an on-screen-parameter gap of the `KEGAP-003` kind, not a closure. |
| **Minimum evidence to classify (not close)** | An explicit statement that stop placement is discretionary, per-trade, or taught elsewhere would move this to `DISCRETIONARY_BY_SOURCE` and is itself a valid, decision-unblocking outcome. |
| **Source types most likely to contain it** | (1) A **complete single-trade walkthrough** — entry through exit on one chart. (2) A **live session** where a trade is actually placed, since the stop must be typed into an order. (3) A **"set and forget"** explainer — the phrase presupposes a resting stop and target. (4) Any video whose title names stop-loss directly. |
| **Priority** | **P0 — highest in the library.** Nothing downstream computes without it. |

---

### BG-02 · Position sizing → `KEGAP-001` (dependent term)

| Field | Value |
|---|---|
| **Domain** | RISK (sizing) |
| **Exact missing question** | **None on the risk-percentage side.** The open question is entirely inherited: sizing needs stop distance, which is BG-01. |
| **Why it blocks specification** | It does not block on its own. It is blocked **transitively** by BG-01, and reporting it as an independent gap would overstate what is missing. |
| **Evidence already available** | **The richest domain in the library — 16 matching evidence items, 13 `risk_rule` claims, 11 of 13 deterministic.** Three explicit bands: conservative **0.5–1%** [6:23–7:23], recommended/industry-standard **1–2%** [7:23–8:34], high **3–5%** [8:34–9:31], the last restricted to personal accounts and to *"November December January and February and maybe March"* [10:39–11:19]. Stability rules are explicit: *"you risk the same percentage per trade"* [2:34–3:29]; *"once you pick the percentage you stick to it you don't go up or down"* [7:23–8:34]; *"risk management is percentage based system not dollar based system"* [3:29–4:35]; and his own practice of locking one percentage per month [9:33–10:39]. |
| **Minimum evidence to close** | **Nothing further on sizing.** Closes automatically when BG-01 closes. |
| **Source types** | n/a — do not spend acquisition effort here. |
| **Priority** | **P0 by dependency, P4 by acquisition need.** Listed so the Authority can see the asymmetry: MOGO knows Alex's risk *percentages* precisely and his stop *distance* not at all. |

---

### BG-03 · Take-profit methodology → new `KEGAP-005`

| Field | Value |
|---|---|
| **Domain** | EXIT / target selection |
| **Exact missing question** | **How is the take-profit level chosen for a given trade?** The library has target *distances observed after the fact* and no *selection procedure*. |
| **Why it blocks specification** | Without it, a target can only be derived from an R:R multiple — and no R:R minimum is stated as a requirement anywhere (see below). MOGO's production engine fills this with `minRR 2.0`, which has no source authority. |
| **Evidence already available** | **13 matching items, 4 `target_rule` claims — every numeric figure is explicitly recorded as illustrative.** *"an average of about 80 to 90 to even 100 pips at a time of a takerit"* [17:28–19:52, source 004] is annotated *"Given as a personal average, not as a rule for selecting a target on a given trade."* The ratios: *"with a one to two risk reward"* [7:23–8:34] — *"illustrative arithmetic, not stated as a required minimum"*; *"if you risk 5% of your account and then you get a 1 to3 risk reward ratio"* [8:34–9:31] — *"Again illustrative, not stated as a required ratio"*; *"it's a nice one to four to previous"* [7:12–7:36, source 006] — *"Stated as an observation about that chart, not as a required minimum."* One directional hint exists — the 1:4 figure is measured *"to previous"* structure — but the phrase is truncated and names no rule. |
| **Minimum evidence to close** | A statement of **what the target is measured to** (previous structural high/low, opposing zone, liquidity pool, fixed pip distance, or R multiple) as a *requirement* rather than an observation. |
| **⚠️ Anti-inference note** | Three separate ratios (1:2, 1:3, 1:4) appear across three sources, each as arithmetic. **Averaging them, or adopting the lowest as a floor, would fabricate a minimum the educator never stated.** MOGO-002.6 already recorded this; it is restated here because `minRR 2.0` in production makes the temptation concrete. |
| **Source types** | Complete trade walkthrough; live session; any video naming take-profit in the title. Same targets as BG-01 — **one good walkthrough may close BG-01 and BG-03 together.** |
| **Priority** | **P1** |

---

### BG-04 · Trade management after entry → new `KEGAP-006`

| Field | Value |
|---|---|
| **Domain** | TRADE_MANAGEMENT |
| **Exact missing question** | **Is any action ever taken on an open position, and if so, on what trigger?** |
| **Why it blocks specification** | MOGO-002.6 credits the draft with 8 TRADE_MANAGEMENT rules against production's 0, making this look like the draft's strongest addition. Re-derivation from the evidence store shows the domain is **thinner than that count implies**: only **4 claims carry `claimType: trade_management_rule`**, and of 8 matching evidence items, 5 are risk-percentage statements that also match management vocabulary, and 2 are psychology-of-income commentary. |
| **Evidence already available** | **One genuine post-entry rule, stated as the correction to a named failure:** *"i close the trade keeps on going it could have given you 15 000"* [4:37–5:23, source 007], normalized as *"a target set in advance should be allowed to run rather than cut when the unrealised figure becomes emotionally significant."* Its companion states the failure directly: *"you're not taking trades logistically based off of what the market is showing"* — closing on a dollar figure is *"impulse"*. Source 007 also self-identifies as *"episode three of the 'set and forget' podcast"*, which is the strongest available signal that the intended default is **no intervention**. |
| **Minimum evidence to close** | An explicit statement that the position is left untouched until stop or target is hit (which would **close** this domain as a deliberate null), **or** a statement of any condition under which the stop or target is moved. |
| **⚠️ Framing note** | "Set and forget" is a **channel/brand phrase appearing in a source's own self-description**, not a rule statement. It must not be promoted to a rule on that basis. It is, however, a strong acquisition signal (BG-01/03/04 all resolve inside a set-and-forget explainer). |
| **Priority** | **P1** |

---

### BG-05 · Exit methodology → `KEGAP-002`

| Field | Value |
|---|---|
| **Domain** | EXIT |
| **Exact missing question** | **Is a position ever closed on a market condition, as opposed to at a preset stop or target?** |
| **Why it blocks specification** | Exit behaviour cannot be specified from this educator at all. MOGO-002.6 recorded 0 EXIT claims. |
| **Evidence already available** | **6 items match exit vocabulary; none is an exit methodology — and the distinction matters.** The matches are: round numbers concentrating *others'* exit orders [0:50–1:45, source 002]; why a candle must be **closed** before it is read [1:44–3:05, source 004] — a confirmation rule, not an exit; an unsourced *"almost 70% chance"* next-day continuation claim [6:52–8:05]; and three items on the **cutting-a-1:4-at-1:2 failure** [4:37–5:23, source 007], which is an *anti*-exit rule. |
| **Refinement of MOGO-002.6** | MOGO-002.6 reported "EXIT: zero claims." Re-derivation **confirms zero exit rules** but shows the domain is not lexically empty — it contains a **prohibition** (do not close on a dollar figure) and no permission. That is a slightly stronger finding than absence: the only thing the library says about discretionary exit is *don't*. |
| **Minimum evidence to close** | Any statement that a trade is closed early on a market signal, **or** an explicit statement that it never is. Either resolves the domain. |
| **Source types** | Live session; trade review/recap ("how my trades did this week"); complete walkthrough. |
| **Priority** | **P1** |

---

### BG-06 · Break-even logic → new `KEGAP-007`

| Field | Value |
|---|---|
| **Domain** | TRADE_MANAGEMENT (break-even) |
| **Exact missing question** | **Is the stop ever moved to break-even, and on what trigger?** |
| **Why it blocks specification** | A break-even rule changes the risk of every trade after it fires, so a P&L replay is not faithful without knowing whether one exists. |
| **Evidence already available** | **ZERO evidence items. Not one mention of break-even in 244 ALEX_G evidence items across 8 sources.** |
| **Minimum evidence to close** | Any statement either way. Note that MOGO's own replay engine documents `never trailed or moved to break-even` as a **MOGO** choice (`APP_VERSION_LOG` v4.0), so a source statement here would either corroborate or contradict an existing MOGO-authored decision. |
| **Source types** | Live session; walkthrough; set-and-forget explainer. |
| **Priority** | **P2** |

---

### BG-07 · Partial-profit logic → new `KEGAP-008`

| Field | Value |
|---|---|
| **Domain** | TRADE_MANAGEMENT (partials) |
| **Exact missing question** | **Is any portion of a position closed before the full target?** |
| **Why it blocks specification** | Partials change realized R per trade; expectancy is not computable without knowing whether they are used. |
| **Evidence already available** | **ZERO evidence items.** No match for partial, "take some off", "take half", or "secure profit". |
| **Minimum evidence to close** | Any statement either way. |
| **Source types** | As BG-06. |
| **Priority** | **P2** |

---

### BG-08 · Scaling in or out → new `KEGAP-009`

| Field | Value |
|---|---|
| **Domain** | TRADE_MANAGEMENT (scaling) |
| **Exact missing question** | **Is a position ever added to, or reduced, after entry?** |
| **Why it blocks specification** | Scaling breaks the single-entry assumption underlying both the fixed-risk R model and every existing replay candidate. |
| **Evidence already available** | **ZERO evidence items.** One near-match is explicitly *not* about position scaling: *"what actually changed my approach to the market and was able to let me scale was risk management"* [0:28–1:14, source 005] — scaling an **account**, not a position. Recorded so a future keyword pass does not mistake it for one. |
| **Minimum evidence to close** | Any statement either way. |
| **Source types** | As BG-06. |
| **Priority** | **P3** — lowest of the management trio, because the fixed-percentage rule (*"you risk the same percentage per trade"*) makes single-entry the more probable default. **This is a probability, not a finding, and must not be recorded as one.** |

---

### BG-09 · High-impact unresolved gating conditions → `KEGAP-003`, `KEGAP-004`

| Field | Value |
|---|---|
| **Domain** | SESSION_RESTRICTIONS, SETUP, MARKET_STRUCTURE, ENTRY, INVALIDATION |
| **Exact missing question** | Four distinct ones, each gating a *required* rule: **(a)** what are the session hours? **(b)** what makes a swing point significant enough to count? **(c)** what tolerance applies to "price reached the level" — one source declined a setup because price came *"shy about"* ~10 pips short, with no stated threshold; **(d)** what is the maximum of the numeric timeframe-agreement scale (*"scored numerically at 1"* with no stated ceiling)? |
| **Why it blocks specification** | **66 of 111 normalized rules carry an unresolved parameter, and only 41 of 111 are deterministic.** Whole domains are non-deterministic end-to-end: ENTRY 27/27 unresolved, INVALIDATION 9/9, SESSION_RESTRICTIONS 7/7, TIMEFRAMES 3/3. A gating rule with an unknown threshold cannot be evaluated, so the draft cannot progress past `NEEDS_REVIEW` in those domains regardless of decisions taken elsewhere. |
| **Evidence already available** | The rules themselves are stated plainly; the parameters are not. `KEGAP-003` records that session windows are **displayed on an on-screen map** while the transcript carries only the rule. This is the library's structural finding from cycle 013, restated: for this educator the problem was never transcript quality — he shows numbers instead of saying them. |
| **Minimum evidence to close** | Either a source that **reads the parameters aloud**, or an Authority-approved method for reading parameters off the video frame. **The second is not a transcript-acquisition task** and would need its own approval; it is named here so the Authority can see that some of these gaps are not closable by more transcripts. |
| **Source types** | Course-format material (the Rayner precedent: one structured course read its parameters aloud where eight chart-annotating videos did not); any video where parameters are spoken rather than drawn. |
| **Priority** | **P1 for (a) session hours** — 7 required rules blocked by one number. **P2 for (b)–(d).** |

---

### BG-10 · Contradictions preventing a stable specification → `KEGAP-004` + register

| Field | Value |
|---|---|
| **Domain** | Cross-domain |
| **Exact missing question** | For each open contradiction: **which reading governs?** |
| **Why it blocks specification** | A normalized rule in a contradicted domain cannot be trusted while the contradiction is open. |
| **Evidence already available** | **11 contradictions in the KE register, all `resolutionStatus: OPEN`** — 1 blocking, 8 material, 2 minor. By affected category: ENTRY 3, SETUP 3, MARKET_STRUCTURE 2, UNRESOLVED_QUESTIONS 2, **RISK 1**. The single blocking one (`KECON\|20260728\|001`) is cross-educator and foundational: Alex G says no strategy can trade liquidity sweeps alone and *"anyone claiming otherwise is 100% lying to you"*; TJR's entire method is built on them. The RISK one (`KECON\|20260728\|009`, minor) is **within-educator**: 8–10%/month *"that is a fact anybody can do that"* in source 006 against *"seven twelve fifteen percent a month"* in source 008. `10 of 11` are annotated `replayCouldHelp: true`. |
| **Important scoping** | **Only 1 of 11 touches RISK, and it concerns monthly return claims, not stop placement.** No contradiction obstructs BG-01 — the stop-placement gap is pure absence, not conflict. That is a cleaner position for the Authority than a contested one. |
| **Minimum evidence to close** | For within-educator contradictions, a later source that states the rule unambiguously. For the 10 marked `replayCouldHelp`, replay — **which is not authorized and is not requested by this milestone.** |
| **Priority** | **P2**, except: do not spend acquisition effort on the cross-educator contradictions, which no ALEX_G source can settle. |

---

## 2. What this checklist changes about the MOGO-002.6 picture

Four refinements, all evidence-derived. None reverses a MOGO-002.6 conclusion.

1. **Stop placement is not merely absent — the stop is repeatedly *referenced* and never *placed*.** Alex G says the stop needs room and that a wrong trend origin invalidates it. He never says where it goes. That is a stronger, more specific finding than a zero count, and it makes `DISCRETIONARY_BY_SOURCE` a less likely eventual outcome than plain absence-from-reviewed-sources: he treats the stop as an object with a definite location he has not stated in these 8 sources.
2. **EXIT is not lexically empty; it contains a prohibition and no permission.** The only exit guidance in the library is *don't* close on a dollar figure.
3. **TRADE_MANAGEMENT is thinner than "8 rules vs 0" suggests** — 4 claims carry the management type, and one genuine post-entry rule exists.
4. **Break-even, partials and scaling are absolute zeros** — three domains with no mention at all. MOGO-002.6 did not separate these from TRADE_MANAGEMENT; they are separated here because the brief names them individually and because a zero is a different acquisition problem from a thin domain.

## 3. Acquisition efficiency conclusion

**BG-01, BG-03, BG-04, BG-05, BG-06, BG-07 and BG-08 — seven of the ten — are all most likely to be
answered by the same single artifact: one complete, narrated trade from setup to close.**

That is the acquisition target this milestone should pursue, and it is why the queue in
`MOGO-002.7-ACQUISITION-QUEUE.md` ranks a full walkthrough or live session above any topical video on
stop-losses specifically. A topical video answers one row; a walkthrough answers seven.

---

*Phase 1 complete. No source was ingested to produce this document; it reads the existing evidence
store only. The evidence store is unmodified.*

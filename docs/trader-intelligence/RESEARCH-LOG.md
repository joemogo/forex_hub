# Research Log

Append-only record of every ingestion and analysis cycle. Newest first. Each entry closes with the
charter-required ROI review.

**Never edit a past entry.** Corrections are appended as new entries citing the one they revise.

---

## 2026-07-29 · Cycle 016 — **Duplicate rejected**, and the check that should have caught it

**Type:** Rejected intake + pipeline fix · **Sources ingested: 0** · **Claims added: 0**

A transcript was supplied for `https://www.youtube.com/watch?v=sZAE_lqdeno`. That video is already
in the library as **`EVSRC|ALEX_G|20260728|001`** — *"Simplifying Advanced Market Structure in 20
Minutes"* — ingested in **cycle 008** as transcript #4.

**Nothing was ingested.** The library remains at 11 sources, 3 educators, 310 claims.

### Why the tool did not catch it

The supplied copy was the **timestamp-lines** rendering; the ingested one was the **duration-label**
rendering. Same video, same speech, **different bytes** — 22,106 vs 25,397 — and therefore a
different SHA-256. The `contentHash` duplicate check passed it straight through.

I caught it by recognising the content, which is not a control.

**What a second ingestion would have cost.** Not a confidence error — `DECISION|MOGO|20260727|006`
keys independence groups on `traderId`, so the same-educator discount would still have applied and
nothing would have crossed a threshold. The damage would have been **duplicate claims, inflated
evidence counts, and a dashboard showing corroboration that was really one video counted twice.**
Quiet, and hard to unpick later.

### Fixed — `BACKLOG-003/H27`

`ingest.py` now runs the duplicate check on **two keys**:

| Key | Catches |
|---|---|
| `contentHash` | the same **file** offered twice |
| `canonicalReference` | the same **video** offered twice in a different transcript rendering |

`_video_key()` collapses `?v=X`, `?v=X&list=Y`, `?v=X&t=90` and `youtu.be/X` to one key; non-YouTube
URLs fall back to the URL with query and fragment stripped.

**Deliberately conservative:** a missed duplicate is recoverable by `--rollback`, a false positive
would block a legitimate source, so the matcher errs toward under-matching and is a no-op when
`--url` is absent. Verified three ways — the real duplicate is rejected naming the prior source and
title, a new video id passes, and omitting `--url` does not crash.

**Residual gap, recorded not fixed:** a source ingested without a `--url` cannot be canonical-matched
later. Ten of eleven sources carry a `canonicalReference`; the exception is `EVSRC|TJR|20260727|001`,
whose upstream video identity has never been established. It stays hash-only.

The Operator Playbook's Stage 0 duplicate gate now says **always pass `--url`**, because without it
only the weaker check runs.

### ROI Review

**1. Single most valuable thing learned.** That the library's duplicate control was matching on the
wrong thing. It compared **files** when the unit of identity is the **source**. Eleven ingestions in,
the first time the two diverged, the check failed — and the reason it had held until now is that
every prior transcript happened to arrive in a consistent format.

**2. Does this improve MOGO profitability? — No.** No knowledge was added.

**3. Does this improve MOGO's reasoning? — Yes, and cheaply.** It closed a silent-corruption path.
The failure mode was not a wrong answer but a **falsely inflated** one: duplicate evidence reads as
breadth in every count the dashboard reports.

**4. Reusable pattern? — Yes: when a control exists, ask what it actually keys on.** The hash check
was never wrong about files; it was answering a different question from the one the pipeline needed.
Worth applying to the other integrity checks — several key on record ids where the meaningful
identity is a concept.

**5. This should become:** knowledge-only. No claims, no replay candidate.

**6. Single highest-ROI next action.** Unchanged from cycle 015: authorize replay and price data
(R1 — `RC-30` is fully specified and needs nothing else), and decide **D2** (R4).

**A note on the recommendation this cycle indirectly supports.** Review #1's **R2** — pause ALEX_G
acquisition — now has a second argument behind it: eight sources in, the channel is dense enough in
the library that **re-supplied material is a live risk**, and this was the first instance of it.

---

## 2026-07-29 · Cycle 015 — **Transcript #11** (RAYNER_TEO #1) — **THIRD EDUCATOR**

**Type:** Transcript ingestion · **Sources ingested:** 1 · **Source:** `EVSRC|RAYNER_TEO|20260729|001`
**Title:** *The Ultimate Forex Trading Course (For Beginners)* — **VERIFIED**
**URL:** `https://www.youtube.com/watch?v=mEyuQVy3OHc` · **Channel:** Rayner Teo (`@tradingwithrayner`)

**Input:** 150,413 bytes, 2,601 lines, ~2h10m — the largest source in the library. **Output:** 20
sections · 50 annotations · **46 new claims** · **2 new contradictions, both CROSS-EDUCATOR** · 9
authored + 31 auto open questions. Library: **11 sources · 3 educators · 310 claims · 380 evidence
items · 14 contradictions.** Graph `BUILD|20260729|001` — 2,161 nodes, 4,464 edges, zero findings.

This ingestion executes **Trader Intelligence Review #1, recommendation R3**. A new trader record
and independence group `AUTHOR|RAYNER_TEO` were created; publisher verified before extraction per
the Stage 0 gate.

### The gap that had been open since ingestion #2 is closed — for one educator

`RAYNER_TEO` supplies **6 `stop_rule` claims**, the first in eleven sources:

> Place the stop where the trade's **premise is falsified** — below the support the setup relies on.
> Set it objectively at **the low of the support area minus one 20-period ATR (SMA)**. Do **not**
> place it flush against the level, because price routinely spikes just beyond before continuing.
> **Never tighten it to improve risk-to-reward** — improve the entry with a buy limit instead.

Together with a sizing formula (`risk ÷ (stop distance × pip value)`, 1% risk) and a target rule
(just **before** the opposing swing, never at or beyond it), **every leg of a tradeable method is
present in a single source.**

That makes **`RC-30` the library's first P&L-capable replay candidate** — the first that can produce
an expectancy, a win rate, an average R and a drawdown, rather than a hit-rate. Thirty candidates in,
this is the first one whose stop field is not `UNKNOWN — not in source`.

⚠️ **Recorded prominently, in three places: this is evidenced for RAYNER_TEO only.** Eight ALEX_G
sources state no stop at all. Using Rayner's ATR rule on an Alex G or TJR setup would fabricate a
rule and attribute it to someone who never stated it — the same prohibition already standing against
the 80–100 pip / 1:2 inference. The `REPLAY-CANDIDATES.md` standing note was rewritten to be
educator-specific rather than deleted.

### The result that matters more: **R3 did not do what R3 was for**

**All 310 claims remain `emerging`. Maximum score in the library: 25.62 against a 45.0 threshold.
Not one claim moved.**

Rayner states the trend definition in almost the same words as ALEX_G and TJR. Three independent
educators, the same assertion — and the library holds **three separate claims with one evidence item
each**, because `compute_claim_fingerprint()` includes `traderId`.

> Review #1 recommended acquiring a third educator so that cross-educator consensus would become
> measurable. **It has been acquired, and consensus is still not measurable.** The blocker was never
> the educator count. It is that trader-scoped fingerprints prevent cross-educator agreement from
> being counted at all — the **D2** decision, open since cycle 007.

**Six concepts are now asserted by three independent educators**: HH/HL trend definition · a close
rather than a touch · prior levels anchor the setup · trade with the trend · engulfing candles as
entry triggers · ~1% risk per trade. The review template names exactly that as "the closest thing to
a validated trading principle the library can produce without replay." It is currently **invisible to
the confidence engine.** This cycle converts D2 from a design question into a demonstrated blocker.

### Two cross-educator contradictions, and one is the library's most useful

**`XCONTRA|20260729|001` — CONDITIONAL_SCOPE, material.** ALEX_G: a body close beyond a structure
level counts **regardless of size**, no minimum threshold. RAYNER_TEO: use **only major swing
points**, deliberately ignore minor highs and lows. Alex G's detector is maximally sensitive by
design; Rayner's is deliberately filtered.

This lands on **the single most load-bearing undefined parameter in the library** — the one already
gating RC-12, RC-13 and RC-19 through RC-16. Two independent educators have now given contradictory
guidance about a number neither of them supplies. → `RC-29`, which sweeps it and reports the
sensitivity surface rather than picking a value.

**`XCONTRA|20260729|002` — DEFINITIONAL, minor.** The library now holds **three positions** on why
price spikes past a level: TJR says market makers do it deliberately to fill against retail stops;
ALEX_G calls that *"almost a big hoax"*; RAYNER_TEO makes **no mechanism claim at all** and buffers
the stop by one ATR. Filed minor — declining to explain something does not contradict explaining it —
but recorded because **his is the only one of the three that yields a usable parameter.**

### Source quality — a marked contrast, recorded deliberately

This source makes **no income claims whatsoever**, the first in eleven sources. It **deliberately
shows a losing trade** ("this is a trade I took and it happened to me"), explicitly admits the other
examples are cherry-picked, and concedes that structure classification is **subjective** — that two
traders may legitimately classify the same chart differently and neither is wrong.

No other source in the library concedes that last point, and it has a direct replay consequence: a
mechanical implementation tests **one reading**, not "the method". `RC-30` carries that caveat.

It also reads its numeric tables **aloud** — session hours in GMT, lot sizes, pip values — which is
why it yields parameters that comparable ALEX_G sources do not. That contrast is the clearest
evidence yet for the visual-parameter finding from cycle 013: the problem was never transcripts, it
was that one particular educator shows his numbers instead of saying them.

### Engineering findings

**None.** The chaptered profile handled all 13 headings correctly on the largest source yet, and this
transcript had **no fused-URL artifact** (H26) because its URL is appended rather than prefixed.
The apply step took ~3 minutes at 2,161 nodes — worth watching, but not yet a problem.

**Regression:** 307 Python (4 known-obsolete failures) · JS and baseline verified · provenance clean
· all integrity reports at zero.

### ROI Review

**1. Single most valuable thing learned.** That executing a recommendation correctly can disprove its
premise. R3 was issued to make cross-educator consensus measurable; a third educator now agrees with
the other two on six concepts and **the confidence engine cannot see any of it.** That is a more
useful result than the corroboration R3 was hoping for, because it identifies the actual blocker.

**2. Does this improve MOGO profitability? — For the first time, `possibly`, and it is testable.**
Every prior cycle answered `No` or `Unknown` because expectancy was not computable from the material.
RC-30 changes that for one educator's method. It still requires replay authorization and price data.

**3. Does this improve MOGO's reasoning? — Yes, in the specific way the library needed.** It supplied
a worked, mechanical answer to the question eight sources had left open (where does the stop go), and
in doing so demonstrated that the gap was a property of a **particular educator's material**, not of
retail trading education generally.

**4. Reusable pattern? — Yes: prefer educators who read their numbers aloud.** Structured
course-format material yielded more usable parameters in one source than eight videos from a
chart-annotating educator. That is an acquisition criterion, not a taste preference.

**5. This should become:** **Research candidate — RC-30 first.** It is the only candidate in the
library that can produce an expectancy.

**6. Single highest-ROI next action.** Two, and R1 is now sharper than it has ever been:
- **Authorize replay and source price data (R1).** For eleven cycles this was blocked by both
  authorization *and* the absence of a stop rule. **The second blocker is now gone for one educator.**
  RC-30 is fully specified and needs nothing but price data.
- **Decide D2 (R4).** This cycle demonstrated that adding educators cannot raise confidence while
  claims stay trader-scoped. Concept-level consensus counting is the fix the library has been
  deferring since cycle 007.

---

## 2026-07-28 · Cycle 014 — **Transcript #10** (Alex G #8, psychology / money mindset)

**Type:** Transcript ingestion · **Sources ingested:** 1 · **Source:** `EVSRC|ALEX_G|20260728|007`
**Title:** *The best FOREX MONEY MINDSET psychology video PT 2* — **VERIFIED**
**URL:** `https://www.youtube.com/watch?v=lcfyxUtYVSk` · **Channel:** `fxalexg` (verified pre-extraction)

**Input:** 948 lines, ~15:00. **Output:** 16 sections · 24 annotations · **20 new claims** ·
1 same-educator restatement · **1 new contradiction** · 9 authored open questions. Library:
**10 sources · 2 educators · 264 claims · 330 evidence items · 12 contradictions.**
Graph `BUILD|20260728|009` — 1,913 nodes, 4,050 edges, zero findings.

**Confidence outcome:** **zero state changes. All 264 claims remain `emerging`.** Rule candidates: 0.

### The first source in the library with no technical content

No setup, entry, structure or exit rule. It is psychology and personal finance, and is extracted as
such — the 30/30/30/10 income rule is typed `other` specifically so it cannot be mistaken for a
trading rule.

**Its central claim is nonetheless the most operationally relevant thing said about trade management
in eight Alex G sources:** a trade set to a **1:4** target is closed at **1:2** because the
unrealised dollar figure equals a month's salary — *"you are now taking and closing a trade off of
impulse emotion to the dollar amount."*

That is the first time any source has named a **specific exit failure mode**, and it implies a rule —
*a target set in advance should be allowed to run* — that is never stated as one.

**The gap it leaves is exact.** It rules out cutting a target for an **emotional** reason and says
nothing about cutting for a **market** reason: opposing structure, a session ending, a counter-signal.
Any trade-management rule MOGO ever derives needs that distinction, and no source draws it.

### Also recorded

**`XCONTRA|20260728|009` — NUMERIC_THRESHOLD, minor.** Third overlapping monthly-return range from
this channel: source #6 said 8–10% is the realistic figure with 50% impossible; this one says
"7, 12, 15 percent a month", then "7 to 10 percent". Filed **minor** — both figures are already
blocked from promotion, so the disagreement changes nothing operationally, but the library logs
numeric drift rather than averaging it away.

**A materially incomplete product presentation.** A $650–700 evaluation fee is presented as
convertible into a 100K funded account and thence $5,000 from one 1:2 trade, naming a specific
provider — **with no pass rate, no note that the fee is lost on breach, and no reference to the
drawdown rules source #6 said constrain risk banding.** The failure branch is simply absent. Recorded
as `performance_hypothesis`, blocked `critical`, and flagged as source-quality signal rather than
trading knowledge.

**A second title/content mismatch from this channel.** Published title says "PT 2"; the content says
*"video number one official of the psychology series"* and *"episode three"*. After the $1000/day vs
$500/day mismatch in source #5. Both recorded, neither resolved.

**A second practice-diverges-from-rule instance.** He names the 30/30/30/10 rule, tells viewers to
write it down, then says he folds the 10% into investment — openly, so it is an exception rather than
a contradiction. Follows the proximity tolerance in source #7.

**`stop_rule` remains 0 after eight sources.** This one discusses 1:4 and 1:2 ratios, a $650 risk
figure and a 100K account without ever placing the stop that defines that risk.

**Regression:** 307 Python (4 known-obsolete) · 530/530 JS, 0 execution errors · zero
protected-function drift · provenance **360 checks, 0 findings** · all integrity reports at zero.

### ROI Review

**1. Single most valuable thing learned.** That a source with zero technical content can still be the
most useful one for a specific layer. Eight sources described *how to get in*; this is the first to
describe *why traders get out too early*, and it did so by naming a mechanism rather than an
exhortation.

**2. Does this improve MOGO profitability? — `No`.** No stop rule, and the exit rule is implied
rather than stated.

**3. Does this improve MOGO's reasoning? — Modestly.** It closed no gap but sharpened one: MOGO now
knows precisely which distinction any future trade-management rule must draw (emotional cut versus
market cut) and that no source draws it.

**4. Reusable pattern? — Yes: extract psychology sources for the *failure modes* they name, not the
advice they give.** "Don't be emotional" is not extractable. "A 1:4 target closed at 1:2 because the
figure equals a month's salary" is a specific, recognisable, in-principle detectable event.

**5. This should become:** knowledge-only. No replay candidate — the failure mode is about the
trader, not the market, and cannot be tested against price data.

**6. Single highest-ROI next action.** See **Trader Intelligence Review #1**, written this cycle at
the 10-ingestion trigger. Its recommendations supersede the per-cycle guidance: authorize replay
(R1), pause ALEX_G acquisition (R2), acquire a third educator (R3), revisit `PROPOSAL-003` (R4).

---

## 2026-07-28 · **TRADER INTELLIGENCE REVIEW #1** — ingestions #1–#10

**Trigger:** Standing Operating Order item 3 — one review per 10 completed transcript ingestions.
**Status:** written once, never edited. A later review may revise it by citation.

### 1. Period covered

Ingestions **#1–#10** · educators **TJR** (2 sources) and **ALEX_G** (8 sources) · 2026-07-27 to
2026-07-28 · **10 sources at period end**, 0 committed.

### 2. Corpus growth

| Metric | #1 | #10 | Δ |
|---|---|---|---|
| Sources | 1 | **10** | +9 |
| Claims | 47 | **264** | +217 |
| Evidence items | 62 | **330** | +268 |
| Segments | 24 | **164** | +140 |
| Contradictions | 2 | **12** | +10 |
| Open questions (blocking) | 14 | **214 (199)** | +200 |
| Knowledge gaps | 6 | **93** | +87 |
| Hypotheses | 21 | **499** | +478 |
| **Rule candidates** | **0** | **0** | **—** |
| **StrategyRules** | **0** | **0** | **—** |
| Graph nodes / edges | 246 / 460 | **1,913 / 4,050** | +1,667 / +3,590 |

### 3. Confidence movement — **the core metric**

| State | #1 | #10 | Δ |
|---|---|---|---|
| `emerging` | 47 | **264** | +217 |
| `supported` | 0 | **0** | — |
| `strongly_supported` | 0 | **0** | — |
| anything else | 0 | **0** | — |

**Claims that changed confidence state across ten ingestions: zero.**

**The ceiling, reported explicitly as the template requires: the maximum number of independent
groups behind any single claim is still 1.** Highest score in the library is **25.62** against a
`supported` threshold of 45.0. Evidence-count distribution: 214 claims on one item, 36 on two, 12 on
three, 2 on four — and every one of those multi-item claims is the *same educator* restating himself,
discounted to 25% by `DECISION|MOGO|20260727|006`.

**This is the single most important finding of the period.** The library has grown in breadth by a
factor of five and in depth not at all. That is the designed behaviour, not a malfunction — but ten
ingestions is enough to say plainly that **no amount of further transcript ingestion will move a
single claim to `supported`.**

### 4. Corroboration analysis

- **Corroborated by a second independent source: zero claims.** Not one, in ten ingestions.
- **Corroborated by the same author: 50 claims** (36 at two items, 12 at three, 2 at four). All
  within `AUTHOR|ALEX_G` or `AUTHOR|TJR`; all discounted; none crossed a threshold.
- **Contradicted by a new source: 12 contradictions**, and their distribution is the period's most
  interesting structural result:

| Category | Count | Note |
|---|---|---|
| Cross-educator | 3 | incl. the library's only `blocking` one |
| Within-educator, cross-source | 2 | |
| **Within-source** | **4** | found by checking a source's own numbers against each other |
| **Behaviour vs stated rule** | **1** | only detectable from live material |
| Within-trader (TJR, early) | 2 | |

- **Claims still single-source after ten ingestions: 214 of 264 (81%).** The reason is structural,
  not accidental: trader-scoped fingerprints mean two educators asserting the same thing produce two
  separate claims that never merge, and same-educator repetition shares one independence group.

### 5. Cross-strategy findings

`CROSS-STRATEGY-ANALYSIS.md` has gone v1 → **v8**. Substantive results:

- **The two educators are complementary, not competing.** TJR's largest gap (no higher-timeframe
  bias) is Alex G's entire method; Alex G stops before TJR's entry mechanics begin.
- **One `blocking` contradiction** — `XCONTRA|20260728|001`. Alex G: *"there's no way that you can
  have a specific strategy to trade solely off of these sweeps."* TJR: *"my strategy is based off of
  liquidity sweeps."* One educator's whole method is what the other says cannot be done.
- **Verbatim-level agreement on trend definition** between two educators with different instruments,
  timeframes and methods — and it raised confidence by exactly nothing, for the reasons in §3.
- **No concept is asserted by three or more independent educators**, because the library holds two.
  The template names that as the closest thing to a validated principle available without replay; it
  remains unreachable until a third educator is ingested.

### 6. Terminology and concept drift

**51 glossary terms across 2 educators.** The decisive finding: Alex G explicitly collapses **five**
terms into one referent — support/resistance, supply and demand, order block, area of interest,
liquidity zone — and does so again in a later source.

**Is deferring `PROPOSAL-003` (concept registry) still correct? — No longer clearly so.** The stated
trigger was *the first claim that means the same thing as an existing claim but does not
near-duplicate-match*. That has now happened repeatedly across the terminology collapse, and the
`RC-13` / `RC-20` contradictions both turn on whether two educators mean the same thing by a word.
**Recommendation R4 below.**

### 7. Replay queue health

| | |
|---|---|
| Candidates specified | **28** (RC-01 … RC-28) |
| Candidates **run** | **0** |
| Evidence produced by replay | **0** |

**Stated plainly, as the template requires: zero replay candidates have been run, and the blocker is
not engineering.** It is two things, neither of which is a code change:

1. `replayAuthorization` is `false` on all six `OwnerDecision` records.
2. MOGO holds no market data for any instrument.

**This is now the defining fact about the library.** Sixteen of the 28 candidates cannot produce a
P&L result even if run, because no Alex G source states stop placement — they measure trigger
accuracy, reach-rate, frequency or direction only.

### 8. Pipeline and process

**Defects found and fixed during the period:** fixture isolation (7 tests silently asserting against
production data) · provenance drift in a working transcript (caught by `--verify-provenance`) · a
rollback that deleted a prior source's claim (fixed with the `foreign` guard, which has since held
correctly twice) · path-with-space breaking three sub-tools silently · review-queue duplication ·
stale `repositoryPath` · an **ordering bug that nearly promoted two rules off same-educator
repetition** · a chaptered-transcript normalization bug that spliced non-speech into segment text.

**Defects found and still open:** `H24` (rollback leaves dangling contradiction + snapshot records),
`H26` (a URL fused onto the first timestamp is retained as speech — **four occurrences**), `H22`
(section proposer returns one section on unpunctuated captions — every ingestion has been cut by
hand).

**Manual effort per ingestion: not trending down.** Section cutting and annotation remain fully
manual. That is by design for annotation (it is the judgement step) and *not* by design for
sectioning.

**The most valuable process change of the period** was adding publisher verification as a Stage 0
gate in cycle 010 — it corrected four titles, caught an owner-supplied title that did not match, and
established educator attribution by evidence rather than inference.

### 9. Source quality assessment

| Source | Claims | Notable |
|---|---|---|
| TJR #1 (session strategy) | 47 | Densest single source; 14 open questions |
| ALEX_G #1 (top-down) | 35 | Complete directional method |
| ALEX_G #5 (entry confirmation) | 35 | **Most rule-dense**; 2 within-source contradictions |
| ALEX_G #6 (risk management) | 35 | **`risk_rule` 0 → 13**; confirmed the stop gap |
| ALEX_G #7 (live session) | 18 | **Highest value per claim** — 3 filters no instructional source states |
| ALEX_G #8 (psychology) | 20 | **Zero technical content**; named the exit failure mode |

**Acquisition conclusion, fed back into `BACKLOG-002`:** live sessions outrank instructional videos
(`A2-LIVE`). Eighteen claims from a 7-minute live call produced the library's first
behaviour-vs-rule contradiction; 35 claims from a polished 22-minute lesson produced none.

**Counter-signal on this channel:** it has now produced **eight unevidenced monetary claims** — $60k
and $50k days, $50–100k/day, 8–10%/month, 7/12/15%/month, 100K funded / $28,000, students at
$1,000–1,500/week, 70% next-day continuation, and a $650 fee presented as a route to $5,000 with the
failure branch omitted. All are blocked and none can become rule candidates, but the **density** is a
source-quality signal in its own right.

### 10. Honest negative findings — required section

1. **Ten ingestions produced zero validated knowledge.** Not one claim moved state. Judged against
   the charter's success metric this period is a **breadth success and a depth failure**, and calling
   it anything else would be dishonest.
2. **I was wrong about the environment for five cycles.** Titles were recorded PROVISIONAL on the
   stated ground that the published string could not be verified without network access. One call in
   cycle 010 disproved that and corrected four records. An unverified constraint had been propagating
   into the provenance record as though it were a fact about the world.
3. **An ordering bug nearly defeated a ratified policy.** `run_post_annotation_pipeline` ran before
   `apply_author_independence_policy`, saw pre-policy confidence, and created two rule candidates off
   same-educator repetition alone — exactly what `DECISION|MOGO|20260727|006` exists to prevent.
   Caught and reversed, but it was caught by inspection, not by a test. **There is still no
   regression test asserting that ordering.**
4. **The stop-placement gap has been open since ingestion #2 and nothing has closed it.** Eight
   sources from an educator whose method is otherwise complete, including one *devoted to risk*.
5. **Over-extraction risk, acknowledged:** 499 hypotheses and 93 knowledge gaps against 0 rule
   candidates. Most of that is auto-generated scaffolding around claims that cannot move. It is not
   wrong, but it inflates the appearance of progress and should be read with §3 in hand.
6. **The section proposer has never once produced a usable cut** (H22). Every one of ten ingestions
   was sectioned by hand.
7. **A systematic limit was identified late:** this educator's rule *parameters* are consistently
   shown on screen and never spoken — the grading scale, the session hours, the confluence list.
   Transcript ingestion structurally cannot capture them. Three occurrences before the pattern was
   named.

### 11. ROI review — across the whole period

**1. Single most valuable thing learned.** That the library's binding constraint stopped being
knowledge somewhere around ingestion #4 and has been **authorization** ever since. Everything after
that has added breadth to a corpus that cannot deepen without replay.

**2. Does this improve MOGO profitability? — `No`, and now demonstrably so for ALEX_G specifically.**
With no stop rule across eight sources, expectancy is not computable from his material even in
principle. For TJR the answer remains `Unknown` pending replay.

**3. Does this improve MOGO's reasoning? — Yes, substantially, and this is where the period's value
sits.** The library caught a policy nearly defeated by execution order; found four within-source
contradictions by arithmetic alone; produced the first behaviour-vs-rule contradiction; and
identified a structural blind spot in transcript-based ingestion. None of that required market data.

**4. Reusable patterns established.** Verify the publisher before extraction · cross-check every
quantitative claim in a source against every other one · extract the full source then check its own
summary against it · prioritise live material over instruction once the taught rules are captured ·
in live material, **the skips are worth more than the entries.**

**5. This should become:** research candidates. **Zero feature candidates**, correctly — `POLICY-001`
bars promotion, and no claim has the evidence to justify it.

**6. Single highest-ROI next action.** Unchanged for seven consecutive cycles and now supported by a
full period of data: **authorize replay and source price data.**

### 12. Recommendations

| # | Recommendation | Owner decision required |
|---|---|---|
| **R1** | **Authorize replay and acquire price data.** RC-25 first — fully specified by its source, needs only daily and 4H candles, and carries a number that either survives contact with data or does not | ✅ **Yes** — `replayAuthorization` on a new `OwnerDecision`, plus a data-source budget |
| **R2** | **Pause ALEX_G acquisition.** Eight sources have produced a complete-except-the-stop method and diminishing returns per source. Further material from this channel adds claims that cannot move | ✅ Yes — scope decision |
| **R3** | **Acquire a third educator**, so cross-educator consensus becomes measurable at all. Two educators can only ever agree or disagree; three can produce a majority | ✅ Yes — acquisition scope |
| **R4** | **Revisit `PROPOSAL-003` (concept registry).** Its deferral trigger has fired repeatedly. Without it, MOGO cannot tell whether two educators agree or merely share a word | ✅ Yes — this is the D2 decision already open |
| **R5** | **Add a regression test asserting the independence-policy ordering.** The cycle-008 near-miss was caught by inspection; nothing prevents its recurrence | ❌ No — engineering |
| **R6** | **Fix H22 (section proposer) or delete it.** Ten for ten failures; it currently provides false reassurance in the playbook | ❌ No — engineering |
| **R7** | **Record the visual-parameter limit as a standing constraint** in `SPEC-provenance.md`, so future acquisition does not keep paying for transcripts that structurally cannot carry the numbers | ❌ No — documentation |

### Standing questions

1. **Did MOGO get measurably smarter, or just bigger?** — **Bigger.** 5.6× the claims, zero
   confidence movement, zero rule candidates. The intelligence gained is in *process* — five reusable
   extraction patterns and eight pipeline defects found — not in validated trading knowledge.
2. **Highest-confidence claim, and what would validate it?** — `CLAIM|ALEX_G|20260728|011` (wait for
   a retracement rather than chase) at **25.62**, on four same-author evidence items. Only replay or
   a second educator can move it.
3. **Is any claim ready for a `RuleCandidateProposal`? — No.** Blocker: every claim sits at one
   independence group, 25.62 against a 45.0 threshold, and both non-replay routes are closed by
   ratified decision.
4. **What applies across all strategies?** — Two things. Both educators require a *close* beyond a
   level rather than a touch. And both treat prior significant levels as the anchor for a setup,
   differing only in whether the level is a target or an entry.
5. **What is the library still completely blind to?** — Stop placement · position sizing in
   instrument terms · any outcome data whatsoever · ICT and SMC (registered, zero evidence) · JVM's
   provenance (implementation-only) · every parameter this educator shows on screen rather than
   saying.

---

## 2026-07-28 · Cycle 013 — **Transcript #9** (Alex G #7, live session market breakdown)

**Type:** Transcript ingestion · **Sources ingested:** 1 · **Source:** `EVSRC|ALEX_G|20260728|006`
**Title:** *Market break down learn and earn* — **VERIFIED**
**URL:** `https://www.youtube.com/watch?v=1JMVE4Y5U7o` · **Channel:** `fxalexg` (verified pre-extraction)

**Input:** 7,924 bytes, 438 lines, ~7:40. **Output:** 13 sections · 30 annotations · **18 new
claims** · 11 same-educator restatements · **1 new contradiction** · 9 authored + 16 auto open
questions. Library: **9 sources · 2 educators · 244 claims · 306 evidence items · 11 contradictions.**
Graph `BUILD|20260728|008` — 1,723 nodes, 3,541 edges, zero findings.

**Confidence outcome:** **zero state changes. All 244 claims remain `emerging`.** Rule candidates: 0.

### The library's first live trading session, and the first behaviour-versus-rule contradiction

This is the first source that is not structured instruction: a recorded 6 a.m. call with ~70
attendees walking four pairs. The evidence is predominantly `demonstrated_behavior` rather than
`rule_statement`, which makes it the first material capable of **testing taught rules against
practice**.

Most of it corroborates the taught method — pro-trend only, break of structure, higher low plus
bullish engulfing, prior S/R zones, round numbers, EMA retest, alarms. All same-educator, so none of
it raises confidence.

**But three filters appear that no instructional source states:** a **proximity tolerance**, a
**two-sided confluence count**, and **"worth the risk" selectivity** with month-to-date performance
as an input.

**`XCONTRA|20260728|008` — CONDITIONAL_SCOPE, material.** The taught rule is binary: the confirmation
must be *at* a level, and away from one *"you don't enter the trade and it is simply not
applicable"*. Live, a setup was declined because price came **~10 pips short** of 86.000. Binary
taught, graded practised, and **no source supplies a tolerance.**

This is a new *category* of contradiction for the library — not within-source, not cross-educator,
but **stated rule versus recorded behaviour**. Its consequence generalises:

> If a taught rule set systematically omits the discretionary filters its author actually uses, then
> replaying the taught rules measures something the educator does not trade.

That is now a caution on every Alex G replay candidate. It is **not** an accusation of bad faith —
these filters are exactly the kind of judgement that is hard to articulate. It does mean a replay
result must be read as a test of *the stated method*, not of *his trading*.

### The pattern behind the pattern: parameters are shown, not said

The written confluence list — which **is** the direction rule — is displayed on screen, offered for
screenshotting, and never read aloud. That is the **third visual-only artifact in three sources**,
after the session volume map (#5) and the setup grading scale (#4).

Three in a row is no longer coincidence. **The parameters of this educator's rules are consistently
shown rather than spoken**, which for a transcript-based pipeline is a systematic blind spot rather
than a run of bad luck. Worth stating plainly because it bounds what any amount of further transcript
ingestion can achieve: more transcripts will keep yielding rule *shapes* without their *numbers*.

### Smaller findings

**The EMA finally has a role, and still has no period.** Support while bullish, resistance while
bearish; preferred entry where EMA and prior structure converge. Two sources now use it as
load-bearing and neither states the period.

**A candid admission, recorded.** A setup identified in advance, with alarms set, was missed — *"I
forgot what I was doing and I wasn't able to get this."* The library holds several set-and-forget
claims; this is the first evidence of the failure mode, and it comes from the source himself.

**A third R:R figure.** 1:4 here, after 1:2 and 1:3 in source #6 — all three offered as observations
about particular charts, none as a rule. Recorded with an explicit instruction not to average them
or take the minimum.

**`stop_rule` remains 0 after seven sources.** This one is live commentary across four pairs
discussing entries, targets and a 1:4 ratio, and never states where a stop goes. The single mention
of "the area where we could have the stop" describes where price might stop moving, not an order.

### Replay candidate added — RC-28

Measures the **tolerance curve** — closest-approach distance, normalised in pips *and* as a fraction
of ATR, bucketed against forward outcome — rather than assuming a threshold. A smooth curve would
mean the binary rule is a simplification and any threshold is arbitrary; a cliff would locate one
empirically. Explicitly forbidden: picking a tolerance and encoding it.

**Regression:** 307 Python (4 known-obsolete failures) · 530/530 JS, 0 execution errors · **zero
protected-function drift** · provenance **333 checks, 0 findings** · all integrity reports at zero.

### ROI Review

**1. Single most valuable thing learned.**
That the library had, until now, only been reading what this educator *says*. One session of watching
what he *does* produced three filters absent from six instructional sources and the first
behaviour-versus-rule contradiction. **Live sessions are a materially different evidence class**, and
the library should weight them accordingly in acquisition.

**2. Does this improve MOGO profitability? — `No`, and it adds a caution.**
Still no stop rule, so still no expectancy. Worse for the existing candidates: replaying the taught
rules may measure a method the educator does not actually trade. That does not invalidate RC-12…
RC-28, but it changes how their results must be reported.

**3. Does this improve MOGO's reasoning? — Yes, substantially.**
It introduced a contradiction category the library did not have, and it identified a **systematic**
limitation of transcript ingestion for this educator: parameters are shown rather than spoken. That
second finding bounds the whole acquisition strategy — it predicts that more transcripts will keep
producing rule shapes without numbers.

**4. Reusable pattern? — Yes: prioritise live/session material over instructional material once the
taught rules are captured.** Instruction gives the rule set; practice gives the filters. The library
now has strong evidence that the second is not derivable from the first.

**5. This should become:** **Research candidate** — RC-28. Not a feature candidate.

**6. Single highest-ROI next action.** Now three, in order:
- **Authorize replay and source price data.** Seventh cycle asking. RC-25 remains the best first test.
- **Acquire more LIVE sessions from this channel.** New this cycle, and it outranks further
  instructional videos: one session produced three previously invisible filters.
- **Acquire a stop-placement source, or record that none exists** (`BACKLOG-002/A1-STOP`).

---

## 2026-07-28 · Cycle 012 — **Transcript #8** (Alex G #6, risk management)

**Type:** Transcript ingestion · **Sources ingested:** 1 · **Source:** `EVSRC|ALEX_G|20260728|005`
**Title:** *Best Risk Management Strategy to Make Millions with Trading* — **VERIFIED**
**URL:** `https://www.youtube.com/watch?v=VzMlFZbWA0Y` · **Channel:** `fxalexg` (verified pre-extraction)

**Input:** 16,073 bytes, 738 lines, ~12:38. **Output:** 15 sections · 35 annotations · **35 new
claims** · **2 new contradictions, both within-source** · 12 authored + 4 auto open questions.
Library: **8 sources · 2 educators · 226 claims · 276 evidence items · 10 contradictions.**
Graph `BUILD|20260728|007` — 1,503 nodes, 3,011 edges, zero findings.

**Confidence outcome:** **zero state changes. All 226 claims remain `emerging`.** Rule candidates:
**0.** Only one cross-source restatement in this ingestion — this source overlaps very little with
the previous five, which is itself informative.

### The headline: the risk-management source moved `risk_rule` from 0 to 13 — and left `stop_rule` at 0

`ALEX_G` rule-type counts after this cycle: **`risk_rule` 13** (was 0), `target_rule` 3,
`session_rule` 7, **`stop_rule` 0**.

That first number is the largest single-cycle change in any rule category the library has recorded.
What it supplies is genuinely substantial: risk as a percentage of deposited balance and never a
dollar amount; three bands — conservative **0.5–1%** for lower-timeframe traders taking 1–3 trades a
day, standard **1–2%**, high **3–5%** confined to personal or disposable accounts to avoid breaching
funded-account rules; the same percentage on every trade; one percentage chosen per month and held
regardless of streaks; and a stated external purpose — a stable P&L curve is what lets capital
allocators fund a trader.

**And it still does not close the gap.** Risk sizing tells you *how much* to lose. Stop placement
tells you *where*. **Position size = risk amount ÷ stop distance**, and after six sources the second
term does not exist. A trader following this video knows to risk 1% and has no rule for turning that
into a lot size.

This is the cycle where the gap stopped being "not covered yet" and became **demonstrably
structural**: the educator devoted an entire video to risk, and the missing piece is still missing.

### The inference MOGO must not make — recorded so it stays unmade

Source #5 gives an average take-profit of 80–100 pips. This source uses 1:2 and 1:3 in worked
examples. Together those imply a stop of roughly 27–50 pips.

**MOGO must not perform that inference.** Both ratios appear only as illustrative arithmetic inside
an argument about escalating risk after a winning streak; neither is stated as required. The pip
figure was a *past average*, not a selection rule. Combining two descriptive statements from two
sources into a prescriptive third would be inventing a rule and attributing it to an educator who
never stated it. Filed as a `high`-priority open question rather than left as an unspoken temptation.

### Two contradictions, both internal and both arithmetic

**`XCONTRA|20260728|006` — SCOPE_MISMATCH, material.** Three figures from one video that cannot
describe the same operation: *"$50 to $100,000 every single day"* (opening) · *"8 to 10% a month …
anybody can do that"* and 50% a day/week/month is *"not going to happen"* (body) · a **100K** funded
account returning 27–28% over ~39 days for a **$28,000** payout (the flagship evidence). At 8–10% a
month, $50–100k per **day** implies an account in the tens of millions; the evidence offered is
six figures. **The video's own benchmark for realism and its opening claim differ by roughly two
orders of magnitude.** No external data was needed to find this — only the source's own numbers.

**`XCONTRA|20260728|007` — TEMPORAL_DRIFT, minor.** Four durations for one career in one video: 2½
years before making any money · profitable ~6 years · predicting markets ~5 years · 5½ years to work
out seasonality. Filed **minor** on purpose: casual speech rounds numbers, and inflating this would
cheapen the `material` severity that C-3 and the liquidity contradictions carry. Recorded because
every performance claim here is anchored to experience length.

### One new replay candidate — RC-27, and it is unusual

The seasonal rule — 3–5% risk **only** in November through March — is **the only claim in the
library that changes position size**, and its entire basis is *"months statistically that I've seen
in my trading"* with no data shown. It is also, unusually, **testable without the missing stop
rule**: count RC-25 setup frequency and directional outcome by calendar month, controlled against
unconditional monthly volatility.

An honest limit is written into the candidate: even a positive result validates the *pattern*, not
the *risk escalation*. Whether raising risk in better months is correct depends on drawdown, which
is not derivable without the stop rule.

### A standing note now sits at the top of `REPLAY-CANDIDATES.md`

Because a reader seeing 13 risk rules could reasonably assume P&L replay had become possible. It has
not. RC-12 through RC-27 all measure trigger accuracy, reach-rate, frequency or direction; **not one
can produce an expectancy.**

### Engineering findings

The `youtube_timestamp_lines_chaptered` profile handled all six chapter headings correctly — the
first time that profile has met a real chaptered transcript, and it worked. **H26 recurred**: the
pasted transcript again had the video URL fused onto the first words of speech, retained as text at
0:00. Second occurrence in two sources; no excerpt was taken from line 1. Recorded in
`provenance.knownArtifacts`.

**Regression:** 307 Python (4 known-obsolete failures) · 530/530 JS, 0 execution errors · **zero
protected-function drift** · provenance **300 checks, 0 findings** · all integrity reports at zero.

### ROI Review

**1. Single most valuable thing learned.**
That a gap can be *confirmed* by the very source that should have closed it. Before this cycle, "no
stop rule" was an absence across five sources on other topics — plausibly incidental. After a
dedicated risk-management video that still omits it, the absence is a property of the material.
**Negative results about source coverage are results**, and this one changes what MOGO should expect
from every future Alex G source.

**2. Does this improve MOGO profitability? — `No`, and cycle 011's answer is now confirmed rather
than provisional.** With risk sizing but no stop placement, expectancy is not computable. The
13 new risk rules are real knowledge — they constrain *how much*, which matters for any future
sizing engine — but they cannot be validated by replay, because replaying a risk rule requires the
stop rule it depends on.

**3. Does this improve MOGO's reasoning? — Yes, in a specific way: it produced the second
internal-arithmetic contradiction in two cycles.** Both were found by checking the source's own
numbers against each other, with no external data. That is now a repeatable extraction step, not a
lucky catch.

**4. Reusable pattern? — Yes: cross-check every quantitative claim in a source against every other
quantitative claim in the same source.** Income figures, account sizes, percentages, durations and
timeframes should be reconciled as a set before extraction is considered complete. Two of the last
three cycles produced a material finding this way.

**5. This should become:** **Research candidate** — RC-27. Not a feature candidate: the risk bands
are real but unimplementable without stop placement, and `POLICY-001` bars promotion regardless.

**6. Single highest-ROI next action.** Two now, and they have diverged:
- **Authorize replay and source price data** — unchanged for a sixth cycle. RC-25 remains the best
  first test.
- **Acquire an Alex G source that states stop placement, or accept that one may not exist.** This is
  now the single highest-value acquisition target in the library: it is the only missing piece in an
  otherwise complete method, and one video's worth of material would unlock P&L replay for six
  sources at once. Tracked in `BACKLOG-002`.

---

## 2026-07-28 · Cycle 011 — **Transcript #7** (Alex G #5, the entry confirmation)

**Type:** Transcript ingestion · **Sources ingested:** 1 · **Source:** `EVSRC|ALEX_G|20260728|004`
**Title:** *The ONLY confirmation YOU need to make $1000/day Trading Forex* — **VERIFIED**
**URL:** `https://www.youtube.com/watch?v=BcWxqfcjk9A` · **Channel:** `fxalexg` (verified pre-extraction)

**Input:** 29,329 bytes, 168 lines, ~21:55. **Output:** 15 sections · 42 annotations · **35 new
claims** · 7 same-educator restatements · **2 new contradictions, both WITHIN-SOURCE** · 13 authored
+ 31 auto open questions. Library: **7 sources · 2 educators · 192 claims · 241 evidence items · 8
contradictions.** Graph `BUILD|20260728|006` — 1,286 nodes, 2,498 edges, zero findings.

**Confidence outcome:** **zero state changes. All 192 claims remain `emerging`.** Rule candidates:
**0.** The publisher-verification gate added last cycle worked as intended — `author_name` came back
`fxalexg` before extraction began, so these 35 claims joined `AUTHOR|ALEX_G` knowingly rather than by
assumption.

### The cycle's headline: Alex G's method is now complete **except for the stop**

This source supplies the two layers that had been named-but-undefined since cycle 007. End to end,
the evidenced chain is now: **direction** (≥2 timeframes, source #4) → **zone** (inside the LH/LL
box, source #4) → **trigger** (closed rejection or engulfing, at a level, pro-trend — this source) →
**timing** (wait for the session; Monday–Wednesday only — this source) → **target** (~80–100 pips
average — this source) → **stop: nothing.**

**Five sources, zero `stop_rule`, zero `risk_rule`.** And this source is the one that makes the
absence structural rather than incidental: it names *risk-to-reward* as an input to a live decision
(`|20260728|072`), and refers repeatedly to "where my stop loss would have been", "more breathing
room", "better stop-loss" — while never stating how a stop is placed. **A method that reasons about
risk-to-reward without defining the risk leg is incomplete at exactly the point where profitability
is decided.**

The consequence is permanent and worth stating once, clearly: **no Alex G claim can ever be replayed
for P&L.** RC-12 through RC-26 all measure trigger accuracy, reach-rate or direction. None can
produce an expectancy. That is a property of the source material, not a limitation of the harness.

### The session gap: downgraded, not closed

*"Trading at the right times"* (source #2) and *"the proper session"* (source #4) are now a
**prescriptive rule with a stated rationale**: enter inside the high-volume windows; hold a
confirmation that arrives early until the session — *"that's the black and white rule"*; trade only
Monday, Tuesday, Wednesday, because an 80–100 pip target needs enough remaining volume hours.

**But the windows themselves are shown as coloured bands on an on-screen session map and never
spoken.** Sydney, London and New York are named; no hours are given. The rule is prescriptive and its
parameters are missing. **MOGO must not supply them** — TJR's sessions are evidenced for TJR, on US
indices, and importing them into an FX method would be inventing a rule and attributing it to
someone who did not state it.

### Two contradictions, both internal to this single source

**`XCONTRA|20260728|005` — DIRECTIONAL, material.** The video's thesis, stated in the opening,
repeated at 1:06 and restated in the summary: *"entering off of a confirmation, not an
anticipation."* At 6:37, in the same video: *"that perfect higher low is where you can then
**anticipate** that wick fill."* **Fourth record of this inconsistency across Alex G's material, and
the first internal to a source whose entire subject is the rule being broken.** A reconciliation
exists — anticipate the *setup*, require a closed candle to *enter* — and it is coherent, and he
never says it. Adopting it would be MOGO resolving a contradiction on the educator's behalf.

**`XCONTRA|20260728|004` — CONDITIONAL_SCOPE, material.** At 16:56 he states that waiting for the
session sometimes loses the trade outright — *"the trade is completely gone from the direction, gone
from the area where I was interested in taking."* At 18:51 he concludes *"there's no negative"* and
enumerates three outcomes: worse entry but right direction, the loss you would have taken anyway,
better entry. **The forfeited-trade case he described himself two minutes earlier is absent from the
enumeration.** The claim is not wrong about the cases it lists — it is incomplete, and the missing
case is the only one with an unbounded cost.

This second one is worth dwelling on. It is the cleanest example the library has produced of a
claim that **sounds like reasoning and is contradicted by the source's own evidence.** No external
data was needed to find it — only reading the whole transcript instead of the summary.

### Replay candidates added — RC-25, RC-26

**RC-25 is the most precisely specified setup any educator in the library has given.** Every prior
candidate had to be assembled from claims across sections; this one is stated as a complete,
countable conditional with a number attached: daily bullish body + strong downside rejection, after a
same-day 4H bearish→bullish shift, at support ⇒ next day bullish ~70%. Two terms are undefined
("strong" wick, "bullish push"), so the test **sweeps both thresholds and reports the surface** — and
computes the base rate of "next day is up" as the control first. If 70% appears only at one
hand-picked pair of thresholds, that is the finding.

**RC-26** measures what waiting actually costs, by classifying every signal into four outcomes —
including the one Alex G omitted.

### Engineering findings

**H26 (open).** The pasted transcript had the video URL fused onto the first timestamp, so line 1
fell through the duration-label pattern and the URL was retained as spoken text at 0:00. Same class
as H25, smaller impact — no excerpt came from line 1 — but it is the second time in two ingestions
that non-spoken chrome entered a segment as speech. Recorded in the manifest's
`provenance.knownArtifacts`. The fix must **split and record** the prefix, not strip it, or per-line
reversibility breaks.

**Regression:** 307 Python (4 known-obsolete failures) · 530/530 JS, 0 execution errors · **zero
protected-function drift** · provenance **262 checks, 0 findings** · all integrity reports at zero.

### ROI Review

**1. Single most valuable thing learned.**
That the shape of Alex G's incompleteness is diagnostic. Five sources have produced an unusually
complete method — bias, zone, trigger, timing, target — with **one hole, in the one place that
determines whether the method makes money.** That is not a random gap; free educational content
tends to stop exactly where risk begins. Recording it as a structural property rather than a
to-be-filled TODO is the correct handling, and it sets the expectation for every future source from
this channel.

**2. Does this improve MOGO profitability? — `No`, and this cycle establishes that it cannot.**
Previous cycles answered `Unknown`. This one is a firmer answer for Alex G specifically: with no stop
rule and no risk rule across five sources, expectancy is not computable from his material **even in
principle**. His claims can inform *trigger* logic; they can never justify a position-sizing or
risk decision.

**3. Does this improve MOGO's reasoning? — Yes.**
It produced the first within-source logical contradiction the library has caught — a "no negative"
claim falsified by the same speaker two minutes earlier. That is a class of error no confidence
arithmetic would ever surface, and it was found only by extracting the whole transcript rather than
its summary. The four-part summary at the end of this video omits the 4H cross-reference step
entirely; a summary-only extraction would have missed a required step **and** both contradictions.

**4. Reusable pattern? — Yes: extract the full source, then check its own summary against it.**
Where an educator summarises their own method, the delta between the body and the summary is
diagnostic — it shows which steps they treat as essential versus which they actually rely on.

**5. This should become:** **Research candidate** — RC-25 first. Not a feature candidate:
`POLICY-001` bars it, the session hours are missing, and the stop rule does not exist.

**6. Single highest-ROI next action.** Unchanged for a fifth cycle: **authorize replay and source
price data.** Seven sources, 192 claims, 26 replay candidates, zero executed. RC-25 is now the best
first test in the library — it is fully specified by the source, needs only daily and 4-hour candles,
and has a number attached that either survives contact with data or does not.

---

## 2026-07-28 · Cycle 010 — **Transcript #6** (Alex G #4, marking areas of interest)

**Type:** Transcript ingestion · **Sources ingested:** 1 · **Source:** `EVSRC|ALEX_G|20260728|003`
**Title:** *Learn How THIS Forex AOI SECRET Bought Me A $200,000 Watch* — **VERIFIED**
**URL:** `https://www.youtube.com/watch?v=urX1iWvHc5g` · **Channel:** `fxalexg` (`@fxalexg__`)

**Input:** 11,900 bytes, 79 lines, ~9:20. **Output:** 13 sections · 31 annotations · **20 new
claims** · 9 same-educator cross-source restatements · **1 new contradiction (within-educator)** ·
12 authored + 25 auto open questions. Library: **6 sources · 2 educators · 157 claims · 199 evidence
items.** Graph `BUILD|20260728|005` — 1,021 nodes, 1,958 edges, zero findings.

**Confidence outcome:** **zero state changes. All 157 claims remain `emerging`.** Rule candidates:
**0**. Nine earlier Alex G claims gained a second or third evidence item and moved 22.0 → 22.8–25.0
under the same-group discount, exactly as `DECISION|MOGO|20260727|006` intends.

### The methodological finding that outranks the content: **this environment has network access**

Every prior cycle recorded titles as PROVISIONAL on the stated ground that the published string
could not be verified offline. **That premise was wrong.** The YouTube oEmbed endpoint resolves both
title and channel, and it was used this cycle to verify all four outstanding sources:

| Source | Recorded before | Published title (verified) |
|---|---|---|
| `EVSRC\|ALEX_G\|20260727\|001` | *Why 99% of Traders Fail in Forex* (**owner-supplied**) | **Best Top Down Analysis Strategy for 2026 \| Forex Trading Guide** |
| `EVSRC\|ALEX_G\|20260728\|001` | *Advanced Market Structure* (provisional) | **Simplifying Advanced Market Structure in 20 Minutes \| Forex Trading Tutorial** |
| `EVSRC\|ALEX_G\|20260728\|002` | *Liquidity and Liquidity Sweeps* (provisional) | **How to Master Liquidity in Trading (Advanced Guide)** |
| `EVSRC\|TJR\|20260727\|002` | *TJR — Day 3* (working title) | **Path to Profitability: How to Read a Candlestick Chart** |

Two consequences worth stating plainly:

1. **One owner-supplied title did not match.** The prior title for Alex G source #1 is retained
   alongside the verified one as `ownerSuppliedTitle`, with a note. It was **not** silently
   overwritten. The video may have been retitled, or the string may refer to a different upload —
   the record says so rather than guessing.
2. **Educator attribution for this transcript was verified, not inferred.** No metadata block was
   supplied. The style suggested Alex G, but the tone did not — this source flexes $60k days and
   Richard Mille watches, while source #3 attacks guru claims epistemically. The publisher endpoint
   returning `fxalexg` for all four is what settled it. **Had it come back a different channel,
   `DECISION|MOGO|20260727|006` would have applied differently and these claims would have formed a
   separate independence group.** Attribution is not cosmetic; it is an input to confidence.

`provenanceStatus` stays `partially_verified` for all four. Publisher identity is now confirmed;
**transcript fidelity to the source audio is not** — the text is owner-pasted, not retrieved from a
caption track, and that is the property every excerpt depends on.

### New knowledge — 20 claims

Alex G's **first hard gate**: no trade unless ≥2 timeframes agree, scored at 10 points each · the
counter-direction lockout · the **box** — search confined between the active lower high and lower
low · a break out of the box flips bias and cancels every setup from it · **a genuine S/R level can
still be untradeable** because reaching it would already have invalidated the bias · bottom-up scan
by touch count · look-left validation · set-and-forget waiting · **sell only at a lower high, buy
only at a higher low**, on the 4H · the "potential" lower high exception · wait for a break of
structure if the first approach gives no lower high · inverted head and shoulders as corroboration ·
a 4H EMA and a neckline as confluences · B/B+ percentage grading · "the proper session" · $60k/$50k
day claims.

### The contradiction — `XCONTRA|20260728|003` · DIRECTIONAL · material · **within-educator**

Source #3: *"entry requires a confirmation that price is already moving in the intended direction"*,
anticipation explicitly rejected. Source #4: *"you need to sell at a lower high **or a potential
lower high**"* — and a potential lower high is by definition one that has not completed.

**This is the third record of the same inconsistency in Alex G's material** (`|20260728|033` has him
conceding he enters on anticipation while teaching against it; `|20260728|036` has him labelling an
incomplete structure point during the directional read). A pattern across three sources is no longer
a slip. Recorded, not resolved → `RC-24`.

### The structural finding — an educator finally stated arithmetic

*"It's 10 per time frame"* plus *"a minimum of two time frames in sync"* is a weighted sum over
independent conditions with a threshold — **the same decision shape as JVM's shipped `WEIGHTS` /
`ALERT_THRESHOLD`**. This is a resemblance in form, not evidence that JVM implements Alex G
(`DECISION|MOGO|20260727|004` still governs). What changes is that a comparison is now well-posed
for the first time.

**It is still not implementable, for three reasons all present in the source:** the maximum of the
scale is unknown (the caption is garbled; both 30 and 40 are derivable, and **MOGO must not pick
one**); the weights are uniform, so the "score" is just a count, despite Alex G claiming elsewhere
that higher timeframes are stronger; and his own worked example has the daily *disagreeing* and
costing nothing. `RC-22` tests the agreement count — which is stated unambiguously — and leaves the
threshold alone.

### Replay candidates added — RC-22, RC-23, RC-24

RC-22 (two-timeframe gate), RC-23 (the box constraint — needs no entry model at all), RC-24
(potential vs completed lower high, settling the within-educator contradiction). **All three need
price data and nothing else.** The library now holds 24 replay candidates and has executed none.

### Engineering findings — two pipeline defects, one fixed at the root

**H25 (fixed).** YouTube chapter headings in the `youtube_duration_label` profile were kept as
*spoken text at 0:00*, splicing non-speech into segment `rawText` and stamping four segments 0:00 —
the exact corruption the chaptered profile was written to prevent, in a profile that had never met a
chaptered transcript. No excerpt crossed a heading, so no evidence was affected — **but that was
luck, not design.** Fixed lexically in `transcript_normalize.py`; the intake was rolled back and
re-applied on the corrected normalization.

**H24 (open).** The rollback exposed that `--rollback` leaves behind the ContradictionRecord it
created — a dangling reference the validator immediately flagged as an ERROR — plus 80 snapshot
records that had to be identified by build timestamp and deleted by hand. The `foreign`-claim guard
from the earlier incident **held correctly**: 9 claims shared with earlier sources were kept and
recomputed rather than deleted.

**Regression after re-apply:** 307 Python (4 known-obsolete failures) · 530/530 JS, 0 execution
errors · **zero protected-function drift** · provenance **217 checks, 0 findings** · all three
integrity reports at zero.

### ROI Review

**1. Single most valuable thing learned.**
Not a rule — a **falsified premise about our own tooling**. Five cycles recorded provisional titles
because "this environment has no network access." One call disproved it and verified four sources,
one of which had an owner-supplied title that did not match. The lesson generalises past titles:
**an unverified constraint had been quietly propagating into the provenance record as if it were a
fact about the world.**

**2. Does this improve MOGO profitability? — `Unknown`, but the question is finally well-posed.**
Four Alex G sources still contain zero stop, target and risk rules, so P&L remains uncomputable from
his material. But this source states a decision *procedure with numbers* for the first time, and its
shape matches an engine MOGO already ships. RC-22 could yield the first evidence-based input on
whether uniform-weight timeframe agreement earns its cost. **A result there is not authorization to
change JVM.**

**3. Does this improve MOGO's reasoning? — Yes, in two distinct ways.**
It caught a normalization defect that had been silently corrupting segment text, and it demonstrated
that educator attribution is a *verifiable* input to confidence rather than a stylistic judgment —
had the channel come back different, these 20 claims would have formed a separate independence
group and the confidence arithmetic would have changed.

**4. Reusable pattern? — Yes, and it is now the standard: verify publisher metadata before
extraction.** Cheap, deterministic, and it settles educator attribution — which
`DECISION|MOGO|20260727|006` makes load-bearing — before any claim is written. To be added to the
Operator Playbook as a Stage 1 step.

**5. This should become:** **Research candidate** (RC-22/23/24). Not a feature candidate: the scale
maximum is unknown, the session rule is undefined, and `POLICY-001` bars promotion regardless.

**6. Single highest-ROI next action.** Unchanged for the fourth cycle running: **authorize replay and
source price data.** Six sources, 157 claims, 24 replay candidates, zero executed, zero confidence
movement. The library's constraint has not been knowledge for some time — it is authorization.

---

## 2026-07-28 · Cycle 009 — **Transcript #5** (Alex G #3, liquidity and liquidity sweeps)

**Type:** Transcript ingestion · **Sources ingested:** 1 · **Source:** `EVSRC|ALEX_G|20260728|002`
**Title:** *Liquidity and Liquidity Sweeps* — **PROVISIONAL / unverified** (derived from transcript
content; no metadata block was supplied and the published title is not verifiable offline)
**URL:** `https://www.youtube.com/watch?v=Rua24ytuHuY` (appended to the final transcript line)

**Input:** 15 sections cut by hand on timestamp/topic boundaries. **Output:** 24 annotations ·
**19 new claims** · 2 within-source restatements · 3 same-educator cross-source restatements ·
**2 new contradictions, both cross-educator, one `blocking`** · 6 authored + 15 auto open questions.
Library: **5 sources · 2 educators · 137 claims · 168 evidence items · 5 contradictions.**
Graph `BUILD|20260728|003` — 812 nodes, 1,542 edges, zero findings.

**Confidence outcome:** **zero state changes. All 137 claims remain `emerging`.** The three
cross-source restatements shared independence group `AUTHOR|ALEX_G` per
`DECISION|MOGO|20260727|006` and moved only within-band. Rule candidates: **0**.

**The cycle's defining result — the library's first `blocking` contradiction.**
`XCONTRA|20260728|001`: Alex G states *"there's no way that you can have a specific strategy to
trade solely off of these sweeps"* and that anyone claiming otherwise *"is 100% lying to you."* TJR
states *"my strategy is based off of liquidity sweeps."* This is not a parameter disagreement — one
educator's entire method is the thing the other says cannot be done consistently.

A **partial reconciliation exists and was recorded as such**: Alex G objects to *anticipating* a
sweep, while TJR reacts to one that has already occurred and then requires a separate confirmation.
That reading is **MOGO's, not either educator's**, so the record stays `blocking` and open rather
than being resolved by our own interpretation — per approved decision 3.

**Second contradiction, `XCONTRA|20260728|002` (mechanism, material).** TJR asserts market makers
sweep levels to fill large positions; Alex G says there is *"no real hardcore evidence"* for this
and calls it *"almost a big hoax."* Note the asymmetry: **TJR asserts a mechanism, Alex G asserts
the absence of proof for it.** Alex G is the first source in the library to argue epistemically
rather than about market behaviour — but his own argument rests on an unsourced statistic (*"retail
traders only make up 3% of the market"*), recorded as `performance_hypothesis` with its own open
question.

**Self-inconsistency recorded, not resolved.** Alex G describes his own live AUDCHF position as
*"entering a trade technically after the liquidity sweep"* — the thing he spends the video arguing
cannot be systematised. Filed as a `critical` open question against him, exactly as TJR's on-camera
deviations from his own rules were in cycle 001. **Both educators are held to the same standard.**

**Terminology finding.** Alex G explicitly collapses **five** terms into one referent —
support/resistance, supply and demand, order block, area of interest, liquidity zone. A single
educator flattening the industry's vocabulary in one breath is the strongest evidence yet for
`PROPOSAL-003` (concept registry): without it, MOGO cannot tell whether two sources agree or are
merely using different words.

**Still absent after three Alex G sources:** zero `stop_rule`, zero `target_rule`, zero `risk_rule`
claims. This is no longer plausibly an omission from one video — it is a **structural gap in his
published material**, and it means no Alex G claim can ever be replayed for P&L, only for trigger
accuracy.

**Replay candidates added: RC-20, RC-21.** RC-20 is the highest-value test the library has ever
held — it settles the only `blocking` contradiction, needs price data and nothing else, and Alex G
supplied the measurement himself (one zone, seven approaches, one sweep). RC-21 controls its main
confound (TJR's sweeps are session-anchored; Alex G's example is not) and is **explicitly bounded**:
it can test *whether* sweeps cluster, never *why*.

**Engineering findings:** none new. The reordering fix from cycle 008 held — the post-annotation
pipeline again saw post-policy confidence and proposed nothing. Section proposal again required
manual cutting (`BACKLOG-003/H22` still open).

**Regression:** 307 Python (4 known-obsolete failures) · 530/530 JS fixtures, 0 execution errors ·
**zero protected-function drift** (63 functions, 4 constants byte-identical) · provenance 183
checks, 0 findings.

### ROI Review

**1. Single most valuable thing learned.**
Not a rule — a **falsifiable disagreement**. Two educators now hold opposite positions on whether
liquidity sweeps can be traded systematically, and Alex G handed over the exact metric that settles
it: the fraction of approaches to a repeated-rejection zone that actually sweep. Four cycles
produced agreement that could not raise confidence; this cycle produced a disagreement that can.

**2. Does this improve MOGO profitability? — `Unknown`, and unusually so.**
Alex G's material contains no stop, target or risk rule in three sources, so P&L is not computable
from it in principle. But this cycle raises a **prior** question: if Alex G is right, TJR's premise
carries a real opportunity cost, and any MOGO component built on sweep-detection is expensive by
construction. That is a profitability-relevant question MOGO could not previously even pose.

**3. Does this improve MOGO's reasoning? — Yes, more than any cycle since 001.**
It is the first time the library has held **conflicting** evidence from equally-weighted educators
on a foundational premise, and the machinery handled it correctly: recorded, not resolved; typed by
severity; routed to replay; neither educator favoured. The `blocking` severity is doing real work —
it marks a disagreement that must be settled before either side can be built on.

**4. Reusable pattern? — Yes: the self-supplied falsification metric.**
Alex G argued against sweeps by counting approaches on a chart. Any educator who supports a claim
with a worked example has, by that act, specified a countable test. Worth extracting deliberately in
future ingestions rather than as a by-product.

**5. This should become:** **Research candidate** — specifically RC-20. Not a feature candidate:
`POLICY-001` bars it, and building sweep logic while the premise is `blocking` would be exactly the
mistake this cycle exists to prevent.

**6. Single highest-ROI next action.** Unchanged and now more acute: **authorize replay and source
price data.** Five sources, zero confidence movement, and the library now holds a blocking
contradiction it cannot resolve by reading more transcripts. RC-20 and RC-13 are both decisive and
both need one instrument's OHLC and nothing else.

---

## 2026-07-28 · Cycle 008 — **Transcript #4** (Alex G #2, advanced market structure)

**Type:** Transcript ingestion · **Sources ingested:** 1 · **Source:** `EVSRC|ALEX_G|20260728|001`
**Title:** *Advanced Market Structure* — **PROVISIONAL / unverified** (derived from the transcript,
which names itself twice; published title string not verifiable without network access)
**URL:** `https://www.youtube.com/watch?v=sZAE_lqdeno`

**Input:** 22,106 bytes, 1,006 lines, ~20:43. **Output:** 17 segments · 21 annotations · **14 new
claims** · **4 same-educator restatements** · 8 open questions. Library: **4 sources · 2 educators ·
118 claims · 144 evidence items.** Graph `BUILD|20260728|002` — 650 nodes, 1,214 edges, zero findings.

### F33 — The independence policy was implemented one ingestion ahead of the case that needed it

The owner directed that repetition by the same educator is not independent confirmation. Implemented
as `DECISION|MOGO|20260727|006`: `EvidenceClaimLink.independenceGroup` set to `AUTHOR|{traderId}`,
overriding the `sourceId` default the confidence engine already honours. **No engine change
required.** Backfilled across 123 existing links / 104 claims; no state changed, confirming it
tightens a ceiling rather than lowering scores.

This source then restated four Alex G #1 claims almost verbatim. Result: evidence counts rose to 2–3
sources, scores moved 22.0 → 23.5–25.0 (the 25% same-group discount), and **every claim stayed
`emerging`.** Without the policy those four would have reached `supported`.

### F34 — And it nearly failed anyway, on ordering *(severe; caught and fixed)*

`run_post_annotation_pipeline` auto-proposes a `RuleCandidateProposal` for any claim already at
`supported`. It ran **before** the independence policy, so it saw the pre-policy confidence and
**created two rule candidates at `supported` off same-educator repetition alone** — precisely what
DECISION 006 exists to prevent. The policy then pulled the claims back to `emerging`, but the
proposals persisted.

**Fixed:** the independence policy now runs before the post-annotation pipeline. Both spurious
proposals and their lifecycle events removed; two dangling review-queue entries garbage-collected.
Library is back to **0 rule candidates**.

**The lesson generalises:** a policy that adjusts confidence must run before anything that *reads*
confidence. Ordering is part of the guarantee, not an implementation detail.

### F35 — The snake trick is not formalizable as stated

The owner asked directly whether it is objective enough to formalize. **It is not.** *"At the moment
that the snake has a sharp turn"* supplies no pivot strength, minimum swing, lookback, or
tie-breaking rule. It is a teachable heuristic, not a specification.

It becomes formalizable the moment a pivot definition is chosen — but choosing one would be MOGO
inventing a missing definition. The honest path is `RC-16`: implement it under several candidate `k`
values and report how much the labelling changes. **This gates RC-12 and RC-13**, because every
structure-shift test depends on where the reassigned level sits.

### F36 — "Any size counts" is the most consequential rule in the source

*"Yes something as small as that counts as a shift of structure."* This **explicitly rules out** a
minimum displacement threshold — answering one of the questions asked, and opening another: false
breaks, noise and immediate reversals are never addressed anywhere. No ATR filter, no confirmation
bar, no re-entry rule.

Combined with "structure exists inside any range, however tight", the method is fully mechanical and
maximally noise-sensitive at the same time. `RC-15` and `RC-17` measure the cost.

### F37 — The source oversells at 0:57 and bounds itself at 20:21

*"Market structure is absolutely everything in the market"* versus *"Market structure is only 50% of
the problem… together with top analysis, entry signal and trading at the right times."* Same source,
19 minutes apart. Not recorded as a formal contradiction — the first is rhetorical framing, the
second operative — but the closing statement is **the most honest thing in either Alex G source**,
and it names a fourth requirement ("trading at the right times") that is defined nowhere.

### F38 — 60–75% accuracy: unsupported, quarantined

Stated once, in passing, immediately before the promotional close. No sample, date range, instrument,
timeframe, trade log, or definition of what "accuracy" measures. Typed `performance_hypothesis`,
which makes it **structurally ineligible** to become a rule candidate, and blocked `critical` in the
validation queue.

### F39 — Circular definition worth recording

*"The trend is identified by the market structure"* + *"market structure is these highs and lows"*.
Trend is defined as structure and structure defines trend. Internally coherent as a **definition**,
but it means the claim cannot be falsified and asserts nothing about future price. Only the paired
empirical claim — that slope-reading is a trap — is testable (`RC-14`).

### F40 — Section proposer failed on unpunctuated captions

The automatic proposer returned **a single section** for the whole transcript: it splits only on
lines ending in sentence punctuation, and these auto-captions carry almost none. Sections were cut by
hand on timestamp/topic boundaries. Recorded as `BACKLOG-003/H22`.

### Refusals (deliberate)

- **Title left provisional.** The transcript names itself *"the advanced Market structure video"*
  twice — the strongest possible in-transcript basis — but that is not the published title string.
  Marked unverified in every record.
- **Did not supply a pivot definition** for the snake trick, a retracement depth for E1, or a
  noise threshold for B5. All three are swept as parameters in replay specs instead.
- **Did not treat four verbatim restatements as corroboration** — the entire point of DECISION 006.
- **Did not record the 0:57 / 20:21 tension as a contradiction** — rhetorical framing versus an
  operative scoping statement is not a claim conflict.

### ROI Review

**1. Single most valuable thing learned.** That the guardrail worked *and* was nearly defeated by
execution order. The policy correctly prevented four restatements from promoting — then a
pre-existing pipeline step, running one line too early, promoted two of them anyway. A correct rule
applied at the wrong moment is not a guarantee.

**2. Does this improve MOGO profitability? — `Unknown`, but the testable surface grew sharply.**
Eight replay candidates added, two of them (`RC-12`, `RC-13`) needing nothing but price data — no
risk model, no TP ladder, no instrument abstraction. That is the largest increase in cheap,
decisive, runnable tests any cycle has produced.

**3. Does this improve MOGO's reasoning? — Yes.** First rule register: every rule now carries its
formalizability verdict explicitly rather than by implication. The answer for the snake trick is
"no", which is more useful than a plausible-looking implementation would have been.

**4. Reusable pattern? — Yes.** *Ask of every rule: what would I have to invent to code this?* Where
the answer is "nothing", it is a replay candidate. Where it is a parameter, sweep it. Where it is a
judgement, say so and stop.

**5. This should become:** **Replay candidates** (RC-12–RC-19) + **knowledge**. Not a feature
candidate — 118 claims, zero rule candidates, zero validated rules.

**6. Single highest-ROI next action. — Authorize replay and source price data.** Four sources in,
zero confidence movement, and both non-replay routes to `supported` are now closed by design.
`RC-13` is the best first test: it resolves the library's only cross-educator contradiction, needs
one instrument's OHLC and nothing else.

---

## 2026-07-27 · Cycle 007 — **Transcript #3: first non-TJR educator** (Alex G, top-down analysis)

**Type:** Transcript ingestion · **Sources ingested:** 1 · **Source:** `EVSRC|ALEX_G|20260727|001`
**Title:** "Why 99% of Traders Fail in Forex" · **URL:** `https://www.youtube.com/watch?v=pD1vAUMbSjw`
(both supplied and verified — the first source with complete provenance at intake)

**Input:** 38,330 bytes, 654 lines, ~33 minutes, SHA-256 `c9c4193a…674606`.
**Output:** 17 segments · 37 annotations · 35 claims · 1 cross-educator contradiction · 6 authored +
22 auto open questions. Library now: **3 sources · 2 educators · 104 claims · 123 evidence items ·
60 segments.** Graph `BUILD|20260727|014` — 517 nodes, 952 edges, zero findings.

### F26 — First cross-educator contradiction *(the headline)*

`XCONTRA|20260727|003` · DEFINITIONAL · **material** · CROSS-EDUCATOR.

- **ALEX_G:** *"I base my highs and lows to the bodies of the candlesticks"* — and demonstrates
  *"placing it at the body of that candlestick, not at the wick."*
- **TJR:** *"We take the highest point of those two candlesticks"* — the wick.

Two independent educators, same operation, incompatible price levels. Everything downstream moves
with it: where the level sits, whether a break has occurred, stop placement, risk-to-reward. Both
agree a **close** beyond the level is required — they disagree only on which part of the candle
closes. That makes it a single isolated parameter, and **the cheapest genuinely decisive experiment
in the library** (`RC-10`).

### F27 — Strongest cross-educator agreement in the library — and it moved nothing

- TJR: *"an uptrend which consists of higher highs and higher lows"*
- ALEX_G: *"a bullish market is created of higher highs and higher lows"*

Different educator, different instrument, different method, near-identical wording. **All 104 claims
remain `emerging`.**

The cause is deliberate: `compute_claim_fingerprint()` includes `traderId`, so trader-scoped claims
never merge. That is correct — a claim about TJR's method must not silently absorb someone else's
evidence — but it means **cross-educator agreement currently has no path to raise confidence at
all.**

`PROPOSAL-003` §4 previously asked whether concepts should mediate confidence and recommended *no*.
F27 is the concrete case arguing the other way. **Recommendation: a separate Concept-level consensus
count** ("3 independent educators assert this"), leaving claim confidence untouched. Raised as an
owner decision (`CROSS-STRATEGY-ANALYSIS.md` §8 D2).

### F28 — The two educators are complementary, not competing

TJR's largest open gap is `higher_timeframe_bias`. ALEX_G's method is *nothing but* higher-timeframe
bias, and stops before entry mechanics — which is all TJR provides. They occupy adjacent layers.
First time the library has held two sources that could, in principle, compose.

### F29 — Governance: does MOGO's ALEX_G engine match what Alex G teaches?

MOGO ships a live paper-trading engine attributed to Alex G doing Break & Retest / Repeated Zone
Reaction. The ingested material teaches top-down bias → AOI inside structure → rejection-candle
entry. **Nothing establishes these are the same method.** One source cannot settle it. Raised as
owner decision D1; until resolved, no Alex G-derived change should touch the shipped engine.

### F30 — First FX-native ingested method

TJR's material is US indices, inexpressible in MOGO's pip-denominated risk model without
`PROPOSAL-001`. Alex G's is forex. **First ingested strategy expressible in MOGO's current engine** —
though still 🔴, because the source states **no stop rule, no target rule and no risk rule at all**,
a strictly larger gap than TJR's.

### F31 — Three-way split on candlestick patterns

ALEX_G makes dojis/engulfing the entry trigger. JVM prices `wick`+`engulf` at 35 of a 55 threshold.
TJR removed pattern confluences entirely and reports his best year without them. Two of three treat
them as primary. `RC-02` upgrades from a TJR-only question to a cross-strategy one.

### F32 — New normalization profile, verified line by line

This transcript interleaves YouTube **chapter headings** with timestamp markers. Added
`youtube_timestamp_lines_chaptered` with structural detection. **First attempt regressed TJR#2** —
a purely structural "anything before the first timestamp is chrome" rule ate a genuine opening
sentence. Tightened to require the literal `Search in video` UI marker, and verified both prior
sources normalize byte-identically. The detector's output was printed and eyeballed: exactly 9
chapter headings, 2 chrome lines, 1 trailing URL, no real content touched.

### Refusals (deliberate)

- **No instrument claim from the title.** The video title says Forex; the *spoken* transcript never
  names an instrument or pair. Recorded as metadata, not as a claim.
- **No cross-educator evidence linking.** Attaching ALEX_G's evidence to TJR-scoped claims would
  have raised confidence and read as corroboration. It would also have conflated "TJR asserts X"
  with "X is true". Agreement is recorded in the cross-strategy analysis instead.
- **Contradiction recorded, not resolved.** Neither educator is marked correct.

### ROI Review

**1. Single most valuable thing learned.** That two independent educators prescribe incompatible
ways to mark the single most fundamental object in both their methods — a structure point. It is
material, it is isolated to one parameter, and it is testable on any price data without a risk model.

**2. Does this improve MOGO profitability? — `Unknown`, closer than before.** Nothing is validated.
But this is the first source whose method MOGO's existing FX engine could express, and `RC-10` is
the first experiment needing neither new market data, nor a risk model, nor `PROPOSAL-001`.

**3. Does this improve MOGO's reasoning? — Yes, more than any cycle so far.** The library went from
one educator to two, which is what turns it from a transcript store into a comparison. It also
surfaced a real architectural limit (F27) that only a second educator could have exposed.

**4. Reusable pattern? — Yes.** *Educators disagree most about the primitives, not the strategies.*
The disagreement is not about liquidity sweeps or areas of interest — it is about where a high *is*.
Future ingestions should look for contradictions at the definitional layer first.

**5. This should become:** **Replay candidate** (`RC-10`, `RC-11`) + **research candidate** (D1: does
the shipped engine match the teaching?). Not a feature candidate — nothing is validated.

**6. Single highest-ROI next action.** Acquire **more Alex G material** — it serves three goals at
once: same-educator corroboration (the only route that currently raises confidence), the D1
governance question about the shipped engine, and the missing risk/exit half of his method.

---

## 2026-07-27 · Cycle 006 — **Transcript #2 ingested** (TJR Day 3, beginner foundations)

**Type:** Transcript ingestion · **Sources ingested:** 1 · **Source:** `EVSRC|TJR|20260727|002`

**Input:** 36,812 bytes, 768 lines, ~41 minutes, SHA-256 `befb81e5…6cfa9d`.
**Output:** 19 segments · 24 annotations · 23 new claims · 1 cross-source link · 4 open questions.
Library now: **2 sources · 69 claims · 86 evidence items · 43 segments.** Graph
`BUILD|20260727|011` — 329 nodes, 623 edges, zero findings.

### F20 — A second source did NOT raise any confidence. This is the headline.

**All 69 claims remain `emerging`. Zero rule candidates.** The library has two independent sources
and the maximum independent-group count behind any single claim is 2 — but the one cross-source
link is `contextualizes`, which the confidence engine deliberately does not score.

That is the correct outcome, and it validates cycle 003's F10 prediction from an unexpected angle.
Source #2 is *beginner foundational* content — TradingView setup, candlestick anatomy, highs, lows,
trends — while source #1 is *strategy* content. **They operate at different levels of abstraction
and therefore barely overlap.** Two videos by the same educator corroborated essentially nothing,
not because the material is poor but because it is about different things.

**The practical lesson for acquisition:** corroboration requires sources that make *the same
claims*, not merely sources by the same author. `BACKLOG-002` should prioritise material that
restates strategy rules over material that extends the curriculum.

### F21 — Source #2 fills definitional gaps source #1 assumed

Source #1 built its entire draw-on-liquidity framework on "highs and lows" and never defined them.
Source #2 does: a high is a move up followed by a move down, identified as an up candle followed by
a down candle, marked at the higher of the two wicks. Same for lows, uptrends, downtrends, and
candlestick OHLC anatomy. These are **new claims, not corroboration** — but they make source #1's
vocabulary legible for the first time.

It also **resolves a recorded ambiguity**: the glossary flagged that `CLAIM|TJR|20260727|003`
("New York pre-market starts at 8:30") did not state a timezone. Source #2 establishes that TJR
quotes session times in **Eastern**. Linked as `contextualizes`, so confidence is unchanged.

### F22 — Most operationally consequential rule in source #2

*"we are going to set our time zone to New York time… Even if you guys are in Africa"* — with a
stated failure mode: marking session levels on a non-Eastern chart puts them at the wrong times and
makes the strategy appear not to work. **This is a prerequisite for every session-based claim in
source #1**, and it had never been recorded.

### F23 — Rollback deleted a prior source's claim *(severe; found, fixed, recovered)*

Re-running the ingestion after a path fix, `--rollback` of intake 002 removed **200 records
including `CLAIM|TJR|20260727|003`, which belonged to source 001.** Root cause: rollback deleted
every claim *touched* by the run's evidence, and the cross-source `contextualizes` link made a
source-001 claim look like one of run 002's.

**Fixed:** rollback now excludes any claim that also carries evidence from another source, keeps it,
and recomputes its confidence once this run's links are gone.
**Recovered:** the claim was rebuilt from the surviving `ManualAnnotation`
`ANNOT|INTAKE|TJR|20260727|001|004` (every field read from that record, none supplied by hand) and
its confidence recomputed from surviving links — back to `emerging`, score 22.0, exactly its
pre-#2 state. Its `created` lifecycle event had also been destroyed; it was reconstructed
**timestamped now, not backdated**, and both replacement events state plainly that they are
reconstructions, so the gap in the audit trail stays visible.

**Why this matters more than the other bugs:** the cross-source link is precisely the mechanism by
which confidence is supposed to rise. The first time it was used, rollback destroyed the claim it
pointed at. Any destructive operation must treat cross-source references as *incoming* edges it does
not own.

### F24 — `repositoryPath` went stale the moment a run completed

The intake recorded the queue path (`intake/pending/…`), but phase 2 then moves the file to
`completed/`. `--verify-provenance` caught it as a MISSING working copy. Now records the **raw
archive** path — which never moves and is the source of truth — with the original queue location
kept in `sourceMetadata.originalQueuePath`. The dashboard's pending-work counter was also rewired to
read the real queue (`intake/pending` + `processing`) rather than `imports/`.

### F25 — New normalization profile: `youtube_timestamp_lines`

Source #2 uses bare timestamp marker lines, not source #1's inline duration labels. Added as a named
profile with its own reversibility proof (every source line is exactly one of: the removed marker, or
the retained text). Auto-detected correctly; 383 marker lines removed, 1,823 characters, zero words
changed.

### Refusals (deliberate)

- **No canonical reference invented.** Title and URL were supplied as placeholders
  (`<video title>`, `<YouTube URL>`). A derived working title was used and clearly marked; the URL
  is `null` and recorded as a **high-priority blocking open question**.
- **Did not force corroboration.** The temptation was to link source #2's timezone material to
  source #1's claims as `supports` and watch confidence rise. It is `contextualizes`, because that
  is what it is.
- **Did not backdate the reconstructed lifecycle event.**

### ROI Review

**1. Single most valuable thing learned.** That two sources from the same educator can produce
almost zero corroboration when they sit at different levels of abstraction. Source count is not a
proxy for evidential strength, and the dashboard's "2 sources" would have been misleading if the
confidence ceiling weren't reported alongside it.

**2. Does this improve MOGO profitability? — `No`, directly.** No rule was validated, no confidence
rose, no trading logic changed. The timezone rule (F22) has indirect value: it is a prerequisite for
correctly *testing* every session-based claim, so it makes future replay less likely to be wrong for
a trivial reason.

**3. Does this improve MOGO's reasoning? — Yes.** Source #1's vocabulary was previously undefined
inside MOGO. Highs, lows, trends and candle anatomy are now evidenced definitions rather than
assumed terms.

**4. Reusable pattern? — Yes.** *Foundational content defines; strategy content corroborates.* When
acquiring for confidence, prefer sources that restate the same rules. When acquiring for
comprehension, prefer foundational material. They are different goals and should be separate queue
priorities.

**5. This should become:** **Knowledge only** — plus one **educational-content candidate**: the
high/low/trend definitions are directly usable in the Academy, with `emerging` confidence stated
inline.

**6. Single highest-ROI next action.** Acquire a source that **restates TJR's strategy rules** —
another strategy walkthrough or a trade recap — rather than another curriculum episode. That is what
moves claims off the `emerging` floor. `BACKLOG-002/T2` (daily trade recaps) is the best-specified
such target.

---

## 2026-07-27 · Cycle 005 — Operating environment complete; provenance drift detected

**Type:** Infrastructure cycle · **Sources ingested:** 0 (none available)

### Produced

| Artifact | Contribution |
|---|---|
| `intake/{pending,processing,completed,rejected,manifests}/` | Filesystem-visible queue; each with a real README |
| `queues/{replay,validation}/` | Structured work queues, specification-only until replay is authorized |
| `scripts/.../transcript_normalize.py` | Named normalization profiles with a reversibility contract |
| `scripts/.../ingest.py` | Two-phase CLI: prepare → (extraction) → validate/apply, plus `--status`, `--rollback`, `--verify-provenance` |
| Playbook rewritten | Whole workflow now four commands; one judgment step |

Verified by a synthetic round-trip (ingest → apply → rollback → byte-identical 250-node/475-edge
baseline), a negative test (one changed character → refused, nothing written), and a duplicate test
(re-ingesting the TJR transcript → exit 3, auto-rejected).

### F16 — Provenance drift found in production data *(the important one)*

The first run of `--verify-provenance` — and, before it existed, the CLI's phase-1 hash check —
found that the **working copy of the TJR transcript had been altered after ingestion**: source line
395, `"And I'm sure that"` → `"And I'm x that"`, 59,644 → 59,641 bytes.

**No evidence was affected.** The raw archive was untouched at `e91c5ea1…`, matching
`IntakeManifest.contentHash` and the normalization map; line 395 sits in the promotional section
that produced zero claims; no evidence item quotes it. The altered copy is quarantined in
`intake/rejected/` with a full record, and the working copy was restored from the archive.

Three things this establishes, none of which was previously demonstrated rather than merely
asserted: the raw archive genuinely is the source of truth; hashing at three independent points
genuinely detects divergence; and **a check that runs once at ingestion is not a guarantee** — gap
G-a in `SPEC-provenance.md` was real, and is now closed.

### F17 — Review queues duplicate on every ingestion

`run_post_annotation_pipeline` re-appends all 14 review queues without removing prior entries: one
unrelated ingestion took the queue from 23 → 46. After 10 ingestions each entry would appear ~11
times. Mitigated by a `gc_orphans()` pass in the CLI; root cause recorded as `BACKLOG-003/H17`.

### F18 — Rollback was incomplete, and the round-trip test is what found it

The first `--rollback` left four dangling references that failed the graph build. Found only
because the test actually rebuilt the graph afterwards rather than trusting the command's own
summary. Fixed; rollback now also removes scoped contradictions, questions, lifecycle events and
orphaned queue entries.

### F19 — A space in the repository path silently broke three sub-steps

`os.system("%s %s" % ...)` split `/Users/.../Forex Hub` at the space, so graph rebuild, integrity
validation and dashboard regeneration all failed while the ingestion reported success. Replaced
with `subprocess.run([...])`. Worth recording because the failure was **silent in the success
path** — the only reason it surfaced is that the sub-step output was being printed.

### Refusals (deliberate)

- **Did not silently repair the altered transcript.** Quarantined the altered copy as a record
  first, then restored from the archive, and documented both.
- **Did not build a parallel archive tree.** "Raw transcript archive" and "normalized transcript
  archive" already exist per-trader under `imports/{trader}/{raw,normalized}/`; duplicating them
  would create two sources of truth.
- **Did not automate extraction judgment.** The CLI automates everything around it and stops.

### ROI Review

**1. Single most valuable thing learned.** That the provenance chain works under a real, unplanned
failure. A transcript was altered on disk and the system caught it, localised the blast radius to
zero, and restored from a verified archive. That is the difference between claiming integrity and
demonstrating it.

**2. Does this improve MOGO profitability? — `No`, directly.** No knowledge extracted, no rule
validated. Indirectly, and more than the previous two cycles: ingestion #2 through #N are now
materially cheaper and harder to get wrong, so the cost of acquiring validated knowledge falls.

**3. Does this improve MOGO's reasoning? — Yes, at the meta level.** MOGO can now *check its own
memory for corruption*, which is a precondition for trusting anything downstream of it.

**4. Reusable pattern? — Yes.** *A verification that runs once is not a guarantee.* Every assertion
made at write time — reversibility, hash equality, verbatimness — needs a re-runnable equivalent.
Three of the four gaps in `SPEC-provenance.md` are still in this category.

**5. This should become:** **Knowledge only** (infrastructure).

**6. Single highest-ROI next action. — Supply Transcript #2.** The environment is complete: queue,
CLI, archives, manifests, dashboard, review cadence, rollback, provenance verification. Every step
that can be automated is automated; the only manual step is extraction judgment, which is the step
that should be manual.

---

## 2026-07-27 · Cycle 004 — Standing Operating Order; continuous-ingestion infrastructure

**Type:** Infrastructure cycle · **Sources ingested:** 0 (none available)

### Instruction

Standing Operating Order: licensing no longer blocks internal research; preserve attribution and
provenance; no redistribution or public reproduction; transcript processing is the primary workflow;
auto-update the Knowledge Dashboard after every ingestion; Trader Intelligence Review every 10
ingestions; build evidence graph, replay queue, and cross-strategy comparison automatically.

### Produced

| Artifact | Contribution |
|---|---|
| `DECISION\|MOGO\|20260727\|005` | Licensing determination: internal research permitted, redistribution prohibited, `restricted_third_party` |
| `scripts/trader_intelligence/build_knowledge_dashboard.py` | **New — read-only generator**, pure stdlib, no network, writes exactly one file |
| `KNOWLEDGE-DASHBOARD.md` | Generated live view: corpus, coverage, confidence ceiling, blockers, gaps, graph, integrity, governance, review cadence |
| `TRADER-INTELLIGENCE-REVIEW.md` | 12-section review template + 5 standing questions; triggers at every 10th ingestion |
| Playbook Stages 8b–8d | Dashboard regeneration, cadence check, and the five automatic downstream updates |

Graph rebuilt: `BUILD|20260727|004` — 250 nodes, 475 edges, zero findings.

### Note on new code

This cycle wrote the first new module since the standing "documentation only" instruction:
`build_knowledge_dashboard.py`. Justification: the order directs that the dashboard be updated
*automatically* after every ingestion, and a hand-maintained dashboard would go stale on the first
ingestion — the exact failure the stale `README.md` already demonstrated. The module is read-only
over evidence, writes one markdown file, imports no network-capable module, and cannot touch
`index.html`, any protected function, or any trading state. **`PROPOSAL-002` (the ingestion toolkit)
remains unapproved and unbuilt** — this is not a back door to it.

### Findings

**F12 — Licensing resolution changes posture, not provenance discipline.** `restricted_third_party`
rather than `permitted_third_party`: MOGO has lawful access and an internal-use determination, not
permission from a rights holder. Sources so classified stay in the `unresolved_licensing` queue at
critical, and **that entry is retained deliberately** as the machine-readable no-redistribution
marker. It should not be cleared.

**F13 — The dashboard's first run contained a real bug, caught by reading its output.** It reported
the already-ingested TJR transcript as "1 pending source" because it listed files in `imports/`
without checking them against registered intake paths. Fixed to match on recorded
`repositoryPath`/`transcriptPath`. Worth recording because the failure mode is instructive: a status
artifact that overstates outstanding work is worse than none, since it erodes trust in every other
number on the page.

**F14 — The confidence ceiling is now a first-class dashboard line.** The dashboard computes the
maximum independent-group count across all claims and states plainly that no claim can exceed
`emerging` at 1. This makes the single most misunderstood property of the system visible by default
rather than something a reader must derive.

**F15 — Four traders now registered, one with evidence.** ALEX G and JVM show
`externalResearchStatus: not_started` alongside `operational_implementation` — the governance gap
from F9, now visible on the dashboard every time anyone looks at it.

### Refusals (deliberate)

- **Did not clear the `unresolved_licensing` queue entry.** The order removed licensing as a
  *blocker*; it did not grant redistribution rights. Clearing the flag would erase the constraint
  that is still binding.
- **Did not classify sources `permitted_third_party`.** That would assert permission MOGO does not
  have.
- **Did not build the ingestion toolkit.** `PROPOSAL-002` is still unapproved; the dashboard
  generator is a distinct, explicitly-instructed artifact.
- **Did not fabricate an ingestion.** Zero source material exists; a cycle that ingests nothing gets
  an honest entry rather than manufactured activity.

### ROI Review

**1. Single most valuable thing learned.** That a status artifact can be confidently wrong on its
first run (F13). The dashboard is now the primary instrument for judging library health, so its
correctness matters more than its completeness — a number nobody trusts is worse than a number that
is absent.

**2. Does this improve MOGO profitability? — `No`, directly.** No knowledge was extracted, no rule
validated, no trading logic changed. Indirectly: the dashboard makes the *distance to profitability*
explicit — 0 rule candidates, 0 promoted rules, 2 open contradictions, ceiling at 1 source — which is
the honest denominator every future claim of progress gets measured against.

**3. Does this improve MOGO's reasoning? — Yes.** Library state moved from "derivable by reading six
documents" to "one generated page, always current". The confidence ceiling in particular is now
impossible to overlook.

**4. Reusable pattern? — Yes.** *Generate status, never maintain it by hand.* Every hand-maintained
status document in this repository has gone stale, including the front-door README. Anything
claiming to describe current state should be produced by a script that reads the records.

**5. This should become:** **Knowledge only** (infrastructure). Not a feature candidate — the
dashboard is a research surface, not a trading one, and must not enter `index.html`.

**6. Single highest-ROI next action. — Supply a transcript.** Every governance and infrastructure
obstacle is now removed: licensing determined, autonomous processing authorized, playbook validated,
dashboard automated, review cadence defined. The pipeline is complete and idle. Highest-value first
source remains a **primary ICT transcript** (would corroborate 6–8 TJR definitional claims at once);
second, **Alex G material**, which closes the F9 governance gap.

---

## 2026-07-27 · Cycle 003 — Governance ratification; ingestion resumed and blocked on input

**Type:** Governance cycle · **Sources ingested:** 0

### Instruction

Owner approved seven standing decisions and instructed: *"Resume the Trader Intelligence ingestion
pipeline."*

### Why no ingestion occurred

**There is no source material to ingest.** Verified at cycle start: 1 registered `EvidenceSource`
(TJR, complete), 0 unprocessed files in `imports/`, 0 acquisition candidates, 0 ICT/Alex G/JVM
source material. The pipeline is now fully authorized and has no input.

This is a **supply** blocker, not a permission blocker — and the distinction matters: the approvals
removed every governance obstacle that existed, so the next transcript can be processed the moment
one is supplied.

### Produced

| Artifact | Contribution |
|---|---|
| `DECISION\|MOGO\|20260727\|003` | Ratifies rules 1, 2, 3, 5, 6 as an enforceable `OwnerDecision` (`research_only`, all authorization flags false) |
| `DECISION\|MOGO\|20260727\|004` | Ratifies rule 4 — equal evidence-source standing (`architectural`) |
| `traders/ict/profile.json` | ICT registered at equal standing; every field deliberately empty |
| POLICY-001 → **RATIFIED** | Scope broadened from TJR-only to all sources |
| `BACKLOG-002` scope expansion | T8 (ICT), T9 (Alex G), T10 (JVM) added; second-educator source now outranks TJR source #2 |

Graph rebuilt: `BUILD|20260727|003` — 249 nodes, 469 edges, zero findings. `TRADER` 3→4,
`OWNER_DECISION` 2→4.

### Findings

**F8 — Chat approval is not enforceable; a decision record is.** The five rules were already
described in POLICY-001, but nothing checked them. As `OwnerDecision` records they are now subject
to `PROMOTION_WITHOUT_OWNER_AUTHORIZATION` and visible as graph nodes. This is the single concrete
thing the approvals unlocked.

**F9 — Equal standing reveals a governance gap in MOGO's own engines.** Under rule 4, a
repository-confirmed implementation fact is evidence about *MOGO's code*, not about a trader's
method. MOGO runs a live paper-trading engine attributed to Alex G while holding **zero ingested
Alex G material**. The gap pre-existed; equal standing makes it visible and gives it a name (T9).

**F10 — A second-educator source now outranks TJR source #2.** Same-author corroboration proves
consistency, not correctness. A primary ICT source is independent, would corroborate 6–8 TJR
definitional claims at once, and would establish whether TJR's framework is original or inherited.

**F11 — `replayAuthorization` deliberately left `false`.** Rule 5 establishes that replay evidence
*counts*; it does not authorize replay *execution*. Conflating the two would have granted an
authorization the owner did not give — and replay is separately blocked on ES/NQ market data MOGO
does not hold.

### Refusals (deliberate)

- **ICT's profile left entirely empty.** Every field populated only from real ingested sources, as
  for TJR. Filling `markets`/`timeframes`/`terminology` from general knowledge would create exactly
  the provenance-free data that defect D1 already demonstrates is harmful.
- **Licensing flag not cleared.** It remains `unknown` on `EVSRC|TJR|20260727|001` and critical in
  the `unresolved_licensing` queue. Authorizing autonomous *processing* is not a licensing
  resolution, and rule 2 requires provenance be preserved, not tidied.

### ROI Review

**1. Single most valuable thing learned.** That MOGO ships a live paper-trading engine named for an
external educator whose material it has never ingested. Equal-standing treatment surfaced it
immediately — the governance rule found a real gap on its first application.

**2. Does this improve MOGO profitability? — `No`, directly.** No knowledge was extracted and no
trading logic changed. Indirectly: the governance layer is what stops unvalidated single-source
rules reaching execution, which protects against losses rather than generating gains.

**3. Does this improve MOGO's reasoning? — Yes.** Constraints that lived in prose now live in
records the validator can check. The difference between "we agreed not to do this" and "the system
refuses to do this" is the difference between a convention and a guarantee.

**4. Reusable pattern? — Yes.** *Equal evidentiary standing regardless of implementation status.*
Applies to every future educator, and prevents "we already built it" from becoming an implicit
claim that it is correct.

**5. This should become:** **Knowledge only** for this cycle's output (governance records), plus a
**research candidate** for T8/T9.

**6. Single highest-ROI next action. — Supply a source.** The pipeline is authorized, documented,
validated, and idle. Highest-value first source: a **primary ICT transcript** (T8). Second: **Alex G
material** (T9), which closes the governance gap in F9. Licensing remains unresolved and applies to
both.

---

## 2026-07-27 · Cycle 002 — Cross-strategy analysis and knowledge organization

**Type:** Analysis cycle (no new source) · **Sources ingested:** 0

### Why no ingestion

The charter's core loop is *"for every transcript… extract knowledge"*. Verified state at cycle
start: **one** registered `EvidenceSource` (TJR, already fully processed), **zero** unprocessed
files in `imports/`, **zero** acquisition candidates, **zero** ICT/SMC material anywhere.

There was nothing to ingest. Rather than re-processing a completed source, this cycle extracted
value from the existing library — cross-strategy comparison, terminology, replay specification, and
implementation mapping — all of which were charter deliverables that had not yet been produced.

### Produced

| Artifact | Contribution |
|---|---|
| `CROSS-STRATEGY-ANALYSIS.md` | First three-way comparison (TJR / JVM / ALEX_G); 12 concepts mapped; 3 conflicts, 2 agreements, 6 TJR-unique concepts |
| `GLOSSARY.md` | 14 terms with per-term provenance; 8 deliberately-absent terms recorded as gaps |
| `proposals/REPLAY-CANDIDATES.md` | 9 specifications in charter format (entry/exit/risk/invalidation/confirmations/expected/success/failure/priority) |
| `proposals/MOGO-IMPLEMENTATION-CANDIDATES.md` | All 12 named engines assessed with evidence gates |
| `STANDARDS-extraction.md` §5b | Charter's 7-category classification mapped onto existing fields as a derived view |

### Findings

**F1 — TJR and JVM embody different theories of a setup.** TJR is a conjunctive gate chain (every
gate must pass); JVM is an additive weighted score (threshold 55). Not variants of one design.
Directly testable: the same data, scored both ways, produces different trade sets.

**F2 — Two systems agree a concept matters and disagree sharply on how much.** Structure break is a
mandatory gate for TJR; JVM prices `msb` at 10 of 55 (joint-lowest). Same for session (10).

**F3 — Direct conflict on candlestick patterns.** TJR removed pattern confluences six months ago and
reports his best year without them (`|038`). JVM prices `wick`+`engulf` at 35 of 55. **Testable on
data MOGO already has**, in a replay harness, touching no protected constant → `RC-02`.

**F4 — Strongest three-way agreement: prior significant levels.** TJR's draws on liquidity ≈ JVM's
`aoi` (20) ≈ ALEX_G's zones. Three unrelated approaches converge — the most robust cross-strategy
signal MOGO holds.

**F5 — TJR's largest gap is JVM's largest weight.** TJR has no higher-timeframe bias rule; JVM's
`bias3`+`bias2` = 40 of 55, its dominant input.

**F6 — TJR's vocabulary sits in the ICT lineage** (liquidity sweep, FVG, BOS, equilibrium, order
block). A primary ICT source would plausibly corroborate 6–8 definitional claims at once. **Recorded
as an acquisition hypothesis, not a finding.**

**F7 — The 7-category charter classification is derivable, not a new field.** It spans `directness`,
`evidenceType`, and `confidenceState`. Storing it separately would create a second writable
representation that could drift from its own evidence.

### Refusals (deliberate)

- **No ICT/SMC comparison performed.** MOGO holds zero evidenced ICT/SMC material. Writing
  definitions from general knowledge would create provenance-free rules indistinguishable in the
  data from evidenced ones.
- **No definitions written for FVG or equilibrium**, despite both being used throughout the TJR
  source. The source uses them without defining them; recorded as *"term used, definition absent"*.
- **No `UNKNOWN` replay field filled with a plausible default.** Specifications carrying
  `UNKNOWN — not in source` for risk or exit stay that way.

### ROI Review

**1. Single most valuable thing learned.**
That TJR and JVM disagree about *what a setup is* — a gate chain versus a scorecard — and that
their disagreement is concentrated on two concepts both systems already use (structure break,
session). This is the first cross-strategy insight MOGO has ever held, and it is testable.

**2. Does this improve MOGO profitability? — `Unknown`, trending toward Yes.**
No knowledge here has been validated, so no profitability claim is supportable. But `RC-02` is a
genuine, low-cost, near-term profitability experiment: TJR's evidence says pattern confluences are
redundant, JVM prices them at 64% of its firing threshold, and MOGO can re-score its own history to
find out. **A confirmed result would directly change a live engine's scoring.** That is the closest
this library has come to actionable.

**3. Does this improve MOGO's reasoning? — Yes, materially.**
Before this cycle MOGO held 47 isolated claims about one trader. It now holds those claims
positioned against its own two operational engines, with agreements, conflicts, and unique
contributions labelled. The glossary makes concepts nameable; the terminology table makes the
Concept Registry's necessity concrete rather than theoretical. MOGO can now say *what it knows that
its engines don't* — and, more usefully, *what its engines do that no trader in the library
supports*.

**4. Reusable pattern across strategies? — Yes, three.**
(a) *Prior significant levels* as the universal anchor — all three strategies, independently.
(b) *Structure break as a signal* — universal, weighting disputed.
(c) *Deliberate confluence reduction* — TJR's most transferable methodological claim, and the one
that transfers across asset classes because it is about method, not markets.

**5. This should become:** **Research candidate + Replay candidate.** Not knowledge-only (F3 is
actionable), not a feature candidate (nothing is validated), not archive (the library is active).

**6. Single highest-ROI next action.**
**Resolve the licensing decision on `EVSRC|TJR|20260727|001`.** It is free, requires no engineering,
and currently blocks *every* acquisition path — the ICT source (F6, highest corroboration value),
TJR source #2, and therefore the only routes past the `emerging` ceiling.

*Highest-ROI action that requires no owner decision:* specify `RC-02` in full against JVM's
historical replay data. It tests a real cross-strategy conflict, needs no new market data, no new
risk model, and no change to a protected constant.

---

## 2026-07-27 · Cycle 001 — First production knowledge ingestion (TJR)

**Type:** Transcript ingestion · **Source:** `EVSRC|TJR|20260727|001` · **Status:** awaiting owner
review, uncommitted

**Input:** 59,644 bytes, 397 lines, ~51 minutes, SHA-256 `e91c5ea1…7ccce2`.
**Output:** 24 segments · 62 evidence items · 47 claims · 62 links · 2 contradictions · 14 open
questions · 6 knowledge gaps · 21 hypotheses · 1 draft blueprint · 1 trader profile · 243 lifecycle
events. Graph: 246 nodes, 460 edges, zero integrity findings.

**Confidence outcome:** all 47 claims at `emerging`; zero rule candidates; zero `StrategyRule`s.
Single source ⇒ one independence group ⇒ 22 points against a 45-point threshold.

**Key findings:** the source is a US-index strategy despite a "forex" filename and a Wave-1 record
asserting `markets: [forex]` with zero evidence; no risk rule exists anywhere in the source; two
genuine self-contradictions; the trader deviates from his own stated rules on camera (`|031`,
`|032`, `|033`).

**Engineering findings:** five pipeline defects (D1–D5) and one real test-isolation bug — three
fixtures copied the repository tree and used the copied `evidence/` directory as scratch, which was
silently false once real data existed. Fixed. Four tests asserting "production evidence is empty"
left failing by design pending an owner decision.

**Full report:** `imports/tjr/PRE-COMMIT-RESEARCH-REPORT.md`.

### ROI Review

**1. Single most valuable thing learned.**
Step 2B — a pre-market liquidity sweep requires a further five-minute manipulation before entry.
It is the only claim in the source with a stated rule, a stated causal rationale, **and** a
demonstrated counterfactual (skipping it would have been stopped out).

**2. Does this improve MOGO profitability? — `Unknown`.**
Nothing is validated, and the source contains no risk rule and no take-profit ladder, so P&L cannot
be computed from it even in principle. The six performance claims are unverifiable by construction;
the trader himself states his published figures are inexact.

**3. Does this improve MOGO's reasoning? — Yes.**
It proved the transcript → knowledge-library pipeline end to end on real, messy input, and produced
the first evidenced external corroboration of an already-shipped MOGO component (the Session/Zone
Engine's level construction).

**4. Reusable pattern? — Yes.** Session-anchored level construction, and deliberate confluence
reduction.

**5. This should become:** **Research candidate.** Knowledge-only would waste RC-01; feature
candidate is barred by POLICY-001.

**6. Single highest-ROI next action.** Resolve licensing, then acquire a second independent source.

---

## Logging convention

Every cycle appends: date, type, sources ingested, artifacts produced, findings, deliberate
refusals, and the six-point ROI review. A cycle that produces no knowledge still gets an entry
stating why — a negative result is a result.

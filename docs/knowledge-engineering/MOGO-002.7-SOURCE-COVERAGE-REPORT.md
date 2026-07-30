# MOGO-002.7 — Source Coverage Report (v2, ingested)

**Source:** `EVSRC|ALEX_G|20260729|001` — *"This Trading Strategy Made Me $26,000 in Just 12 Hours"*
**URL:** `https://www.youtube.com/watch?v=kg-rOo9_xjU` · **Channel:** `@fxalexg__` (verified `ALEX_G`)
**Intake:** `INTAKE|ALEX_G|20260729|001` · **Ingested:** 2026-07-29 · **Acceptance:** **`ACCEPTED_PRIMARY`**
**Machine-readable:** [`MOGO-002.7-source-coverage-report.json`](MOGO-002.7-source-coverage-report.json)

> **The prior stop condition `PROVIDED_TRANSCRIPT_CANNOT_BE_FOUND_OR_RECONSTRUCTED` is RESOLVED.**
> The operator supplied the transcript; it has been ingested through the documented pipeline.
>
> **No blocking gap was closed.** Four moved to `PARTIALLY_SUPPORTED`. Three remain absolute zeros.

---

## 1. Ingestion record

| | |
|---|---|
| Raw archive | `imports/alex-g/raw/alexg-break-and-retest-26k-12-hours.raw.txt` + `.sha256` |
| SHA-256 | `7f954e14ec5cb0a6b17de28fb0e6caed6910e6cc4f2ec72c8c6cc3b3441e58d2` |
| Size / lines | 15,232 bytes · 92 lines · ~11m07s |
| Duplicate check | **none** |
| Normalization | `youtube_duration_label` — **reversible, 0 words added / removed / reordered**, 91 lines transformed, 7 chapter headings recorded as removed non-spoken |
| Segments | **13**, cut so no quotable statement spans a boundary |
| Annotations | **36** — every excerpt confirmed verbatim, fail-closed before apply |
| Claims created | **31** new + **5** supporting links |
| Contradictions | **2** (`XCONTRA|20260729|003`, `|004`) |
| Open questions | **9 authored + 18 automatic** |
| **Rule candidates** | **0** |
| Graph | `BUILD|20260729|003` — 2,422 nodes, 5,109 edges, **0 findings** |
| Integrity | evidence **0/0/0/0** · graph **0/0/0/0** · provenance **452 checks, 0 findings** |

**Rule candidates are 0 by design, not by omission.** `RuleCandidateProposal` is created only for
claims that reach `supported`; every claim here is `emerging`, because one source cannot corroborate
itself (`POLICY-001`).

## 2. ⚠️ Zero confidence movement — the third demonstration of D2

| | Before | After |
|---|---|---|
| Claims | 310 | **341** |
| `emerging` | 310 | **341** |
| Any other state | 0 | **0** |
| Max confidence score | 25.62 | **25.62** |
| **Confidence state changes** | — | **0** |

**A ninth ALEX_G source produced the single most important rule the library was missing, and moved
confidence by exactly nothing.** The independence group is `AUTHOR|ALEX_G`, identical to the other
eight, so `DECISION|MOGO|20260727|006` correctly refuses to count it as independent corroboration.

This is the **third** independent demonstration of the **D2** blocker, after the Rayner Teo cycle and
the 2,080 no-op recompute events measured in the repository-stabilization report. **The library can
now acquire a decisive rule and still be structurally unable to believe it.**

## 3. Gap coverage

| Gap | Coverage | Detail |
|---|---|---|
| **`KEGAP-001`** stop placement | **PARTIALLY ADDRESSED** | Anchor relationship and invariance now stated; buffer, anchor identity and short side still absent |
| **`KEGAP-002`** exit methodology | **PARTIALLY ADDRESSED** | Exits demonstrated at preset stop or target only, across three trades; never stated as an invariant |
| **`KEGAP-005`** take-profit selection | **PARTIALLY ADDRESSED** | A **1:2 minimum** is stated twice; selection above the floor still absent |
| **`KEGAP-006`** post-entry management | **PARTIALLY ADDRESSED** | First ALEX_G evidence of no intervention between entry and exit |
| `KEGAP-003` session hours | **NOT ADDRESSED** | This source says nothing about sessions |
| `KEGAP-004` swing significance | **NOT CLOSED — REINFORCED** | *"a minimum of one structure point"* is a quantified minimum over an **undefined unit** |
| **`KEGAP-007`** break-even | **NOT ADDRESSED** | **Still zero mentions across 9 sources** |
| **`KEGAP-008`** partial profits | **NOT ADDRESSED** | **Still zero mentions across 9 sources** |
| **`KEGAP-009`** scaling | **NOT ADDRESSED** | **Still zero mentions across 9 sources** |
| `KEGAP-010` contradictions | **MADE MORE AMBIGUOUS** | 11 → 13 open; one new is material |

**Closes: none. Partially addresses: 4. Does not address: 4. Makes more ambiguous: 2.**

**No gap is reported as closed, deliberately.** The brief warns not to claim closure because one
example was shown. Three examples were shown and one invariant stated — that moves four gaps and
closes none.

**The three absolute zeros are now more meaningful, not less.** Break-even, partials and scaling
remain unmentioned across nine sources — and this source narrates three complete trades end to end,
which is precisely where a break-even move or a partial would have been the natural thing to mention.

## 4. Every explicit and implied rule extracted

**31 claims.** Grouped by what they govern:

### Stop placement — 2 `stop_rule` claims (the library's first)
- **Invariant rule (8:59):** *"it's literally the same thing every single time your stop- loss is right under it"*
- **Demonstrated (7:52):** *"you would have put your stop loss right under this point"*

### Entry and confirmation — 2 `entry_rule`, 3 `confirmation_rule`
- **Required (7:28):** *"in order for us to take a trade trade we need to have a bullish engulfing Candlestick confirmation"*
- **Timeframe split (6:47):** *"the actual entry signal you have to go on the lower time frame"*
- Confirmation shown as a **Morning Star**: three doji rejections + one bullish engulfing (7:52)
- The retest is complete when rejection candlesticks appear — not on a timer or measurement

### Setup — 2 `setup_requirement`, 1 `invalidation_rule`
- **Quantified minimum (4:06):** *"for it to be a valid level of a break and retest you need to have a minimum of one structure point"*
- Break-and-retest is *"most effective"* at a pre-existing zone — comparative, **not** stated as mandatory
- **Binding negative (5:41):** a structurally ideal setup was **declined** because the engulfing never appeared

### Target — 1 `target_rule` (+1 supporting)
- **Stated minimum, twice (8:09, 8:59):** *"a minimum of a 1 to two risk to reward"*

### Trade management — 1 `trade_management_rule`
- **No intervention (8:25):** a losing trade is allowed to reach its stop — *"it is what it is it happens"*

### Timeframes — 4 `timeframe_rule`
- Higher timeframe is more respected (comparative, unquantified) · personal 4H/Daily for continuation,
  lower for entries · day trading → 4H/1H · swing → Daily/Weekly

### Definitions — 7
- Break-and-retest **is a continuation pattern** · **S/R = supply-and-demand = area of interest**
  ("it's all the same thing") · a retested zone **becomes the next structure point** · zone **box size
  does not matter** · downtrend = lows with lower highs · **"set and forget" names this exact procedure**
- Applies to all timeframes and all instrument classes

### Performance and marketing — 6 `performance_hypothesis`, 1 `behavioral_observation`, 1 `marketCondition`
- All at `evidenceQuality: low`. **None supports a rule.**

## 5. Examples kept distinguishable from universal rules

The brief required this explicitly. How each borderline figure was recorded:

| Figure | Recorded as | Why |
|---|---|---|
| *"a minimum of a 1 to two"* | **RULE** (`target_rule`) | The word *"minimum"* states a floor, and it is repeated in a generalising sentence |
| *"the same thing every single time"* | **RULE** (`stop_rule`, `rule_statement`) | Explicitly universalised |
| *"you risk 1% you got 2%"* | **EXAMPLE** (`performance_hypothesis`) | Worked arithmetic over the three demonstrated trades; not restated as the required risk |
| *"three dogee Candlestick rejections one bullish engulfing"* | **EXAMPLE** | Describes this instance; the three-doji count is never stated as required |
| *"9 to 12% a month"* | **EXAMPLE / claim** | Extrapolation from one week, recorded as a performance claim and contradicted |
| *"I personally like using…"* | **PREFERENCE** | Explicitly framed as personal |
| *"most effective at these zones"* | **COMPARATIVE** | Not *"must"* — so a zone is not established as mandatory |

## 6. The brief's predictions, now checked against the transcript

The previous pass refused to treat the brief's description as evidence. Now that the source is read:

| Predicted content | Verdict |
|---|---|
| Higher-timeframe break-and-retest | ✅ **Confirmed** (3:29) |
| Lower-timeframe entry confirmation | ✅ **Confirmed** (6:47) |
| Bullish **or bearish** engulfing confirmation | ⚠️ **Half confirmed.** Bullish is required (7:28). **Bearish appears only as a cross-reference to another video** — no short-side rule is stated or shown |
| Morning Star confirmation | ✅ **Confirmed** (7:52) |
| Stop placement **below or above** the rejection structure | ⚠️ **Half confirmed.** *"right under it"* is stated as invariant. **"Above" is not in the source** — the brief overstates it by one half |
| Minimum 1:2 risk-to-reward | ✅ **Confirmed**, stated twice as a minimum |
| Illustrative 1% risk examples | ✅ **Confirmed as illustrative** — 1% appears only inside worked arithmetic |

**Five of seven fully confirmed, two overstated in the same direction — both overstating the short
side.** Recorded because it validates the earlier refusal to ingest the description as evidence.

## 7. Source quality — marketing-heavy, recorded not discarded

**Five unverified monetary claims and two funnel CTAs:** $26,000 in 12 hours · "made me a millionaire"
· $37,000 live open profit · student income (lower bound unreadable) · 9–12%/month.

Classified **`ACCEPTED_PRIMARY` regardless**, because the mechanical content is genuine, specific and
demonstrated three times. But **6 of 31 claims are `performance_hypothesis` at `evidenceQuality: low`,
and not one of them supports a rule.** The assessment recorded is
**`MARKETING_HEAVY_BUT_NOT_MARKETING_DOMINANT`**.

Contrast with the `RAYNER_TEO` source ingested the same week, which made **zero** income claims — a
difference already flagged as belonging in acquisition weighting.

## 8. Transcript quality — artifacts recorded, never repaired

| Artifact | Treatment |
|---|---|
| *"breaking reetus"* (break and retest), *"set freet"* (set and forget), *"one to2 rward"*, *"dogee"* (doji) | Left verbatim in every excerpt; meaning recorded in the normalized claim |
| *"for your **Inay** and swing trades"* | **Not guessed.** "Intraday" is the obvious candidate but would conflict with the day-trading rule stated one clause earlier. Recorded as an open question |
| Student income lower bound *",000"* | **Not reconstructed as "$1,000".** Recorded as an unreadable figure |
| Chapter 1 heading absent from the paste | Recorded; chapters 2–8 present and removed as non-spoken |

## 9. Two contradictions created

- **`XCONTRA|20260729|003`** · `NUMERIC_THRESHOLD` · **minor** — a third incompatible monthly-return
  range: **9–12%** here, against **8–10%** *"that is a fact anybody can do that"* (source #6) and
  **7/12/15%** then 7–10% (source #8). Filed minor because no trading decision depends on it, but
  recorded because three incompatible ranges for one headline number bear on how this source's numeric
  claims should be weighted generally.
- **`XCONTRA|20260729|004`** · `CONDITIONAL_SCOPE` · **material** — **the consequential one.** A stated
  **1:2 minimum** target here, against source #8 naming a **1:4 cut to 1:2** as the core failure. The
  distinction between a target *set at* the floor and one *revised down to* it is never drawn, and it
  governs whether a preset target may be changed after entry.

## 10. One ingestion defect, found and corrected

The first apply produced a segment 13 whose `endTimestamp` read **`0:00`** instead of `11:07`, because
the file's trailing newline created a 92nd empty line that the normalizer stamped `0:00` and the final
section had to cover.

**Corrected properly rather than disclosed as cosmetic**, because a segment's timestamp range is
provenance data and one evidence item cited it. The run was rolled back
(`ingest.py --rollback`, 323 records), the 120 immutable snapshots the rollback deliberately leaves
behind were removed by hand as the tool instructs, the evidence store was **verified byte-count
identical to the pre-milestone baseline**, and the source was re-ingested from a 92-line file.
Segment 13 now reads **`9:57 → 11:07`**.

---

*MOGO-002.7 Phase 2 complete. Source ingested and accepted as primary. No gap closed; four advanced.*

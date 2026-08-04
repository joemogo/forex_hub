# Session Report — Alex G "Learn How THIS Forex AOI SECRET Bought Me A $200,000 Watch" (Transcript #6)

**Date:** 2026-07-28 · **Workstream:** Trader Intelligence
**Source:** `EVSRC|ALEX_G|20260728|003` · `https://www.youtube.com/watch?v=urX1iWvHc5g`
**Channel:** `fxalexg` (`@fxalexg__`) — **verified, not inferred**
**Status:** Applied, validated, awaiting owner review. **Nothing committed, tagged or pushed.**

---

## 1. Ingestion status

✅ **Complete.** `INTAKE|ALEX_G|20260728|003` at `review_required`.

| | |
|---|---|
| Raw archive | `imports/alex-g/raw/alexg-area-of-interest-markup.raw.txt` + `.sha256` (byte-verified) |
| SHA-256 / size | `c4901808…08c8a8` · 11,900 bytes · 79 lines · ~9:20 |
| Normalization | `youtube_duration_label` — 77 lines transformed, **7 chapter headings removed as non-spoken**, zero words changed, reversibility asserted per line |
| Sections | 13, cut by hand on chapter/topic boundaries |
| Graph | `BUILD\|20260728\|005` — **1,021 nodes, 1,958 edges, zero findings** |
| Integrity | Evidence **0 findings** · graph **0 findings** · provenance **217 checks, 0 findings** |
| Regression | 307 Python (4 known-obsolete failures) · 530/530 JS, 0 execution errors · **zero protected-function drift** |

## 2. Source metadata — **VERIFIED**, and it changed four other records

No metadata block was supplied with this transcript. Rather than infer the educator from style, I
resolved the publisher directly:

```
https://www.youtube.com/oembed?url=<video>&format=json
→ {"title": "Learn How THIS Forex AOI SECRET Bought Me A $200,000 Watch",
   "author_name": "fxalexg", "author_url": "https://www.youtube.com/@fxalexg__"}
```

**Every prior cycle recorded titles as PROVISIONAL on the stated ground that the published string
could not be verified without network access. That premise was wrong.** The same endpoint verified
all four outstanding sources:

| Source | Recorded before | Verified published title |
|---|---|---|
| `ALEX_G\|20260727\|001` | *Why 99% of Traders Fail in Forex* (**owner-supplied**) | **Best Top Down Analysis Strategy for 2026 \| Forex Trading Guide** |
| `ALEX_G\|20260728\|001` | *Advanced Market Structure* (provisional) | **Simplifying Advanced Market Structure in 20 Minutes \| Forex Trading Tutorial** |
| `ALEX_G\|20260728\|002` | *Liquidity and Liquidity Sweeps* (provisional) | **How to Master Liquidity in Trading (Advanced Guide)** |
| `TJR\|20260727\|002` | *TJR — Day 3* (working title) | **Path to Profitability: How to Read a Candlestick Chart** |

⚠️ **One owner-supplied title did not match.** Alex G source #1's prior title is retained as
`ownerSuppliedTitle` alongside the verified string, with a note recording that the video may have
been retitled or the string may refer to a different upload. **Not silently overwritten.**

**Why this mattered here specifically.** This transcript flexes $60k days and Richard Mille watches;
source #3 attacks guru claims epistemically. On tone alone I would not have been confident they were
the same educator. `author_name` settled it — and had it come back a different channel, these 20
claims would have formed a **separate independence group** under `DECISION|MOGO|20260727|006` and
several Alex G claims would have crossed into `supported`. Attribution is an input to confidence, not
a label.

`provenanceStatus` remains `partially_verified` for all four: publisher identity is confirmed,
**transcript fidelity to the actual audio is not** — the text is owner-pasted, not a retrieved
caption track, and that is the property every excerpt depends on.

## 3. New knowledge added — 20 new claims

**Alex G's first hard gate:** no trade unless at least two timeframes agree, scored at **10 points
per timeframe** · counter-direction trades locked out once the majority is set · **the box** — the
AOI search is confined between the active lower high and lower low · a break out of the box flips
bias and cancels every setup derived from it · **a genuine, well-respected S/R level can still be
untradeable** because price reaching it would already have invalidated the bias · bottom-up scan
ranked by touch count · look-left validation · set-and-forget while price travels · **sell only at a
lower high, buy only at a higher low**, with the structure point on the 4H · the *"potential"* lower
high exception · wait for a break of structure if the first approach gives no lower high · inverted
head and shoulders as corroboration · a 4H EMA and a head-and-shoulders neckline as confluences ·
B/B+ percentage grading · *"the proper session"* · the $60k/$50k day claims.

## 4. Reinforced — 9 same-educator cross-source restatements, 0 independent confirmations

`ALEX_G|20260727|002`, `|009`, `|010`, `|011`, `|013`, `|026`, `|028`, `|029`, `|20260728|011`.
All share independence group `AUTHOR|ALEX_G`; scores moved 22.0 → 22.8–25.0 within `emerging`.
**Zero confidence state changes. Zero rule candidates. Fifth consecutive source with no independent
confirmation.**

## 5. Contradiction — 1 new, **within-educator**

### `XCONTRA|20260728|003` · DIRECTIONAL · material

| | |
|---|---|
| Source #3 | *"Entry requires a confirmation that price is already moving in the intended direction"* — anticipation explicitly rejected (`\|20260728\|028`) |
| Source #4 | *"you need to sell at a lower high **or a potential lower high**"* (`\|20260728\|047`) |

A "potential" lower high is by definition one that has not completed — selling into it *is* entering
on anticipation.

**This is the third record of the same inconsistency in Alex G's material.** `|20260728|033` already
has him conceding he enters on anticipation while teaching against it; `|20260728|036` has him
labelling an incomplete structure point during the directional read. A pattern across three sources
is no longer a slip. Recorded, not resolved → `RC-24`.

## 6. The structural finding — an educator finally stated arithmetic

*"It's 10 per time frame"* + *"a minimum of two time frames in sync"* is a **weighted sum over
independent conditions with a threshold** — the same decision shape as JVM's shipped `WEIGHTS` /
`ALERT_THRESHOLD`.

**This is a resemblance in form, not evidence that JVM implements Alex G.**
`DECISION|MOGO|20260727|004` still governs. What changed is that the comparison is now well-posed.

**It is still not implementable, for three reasons all present in the source:**

1. **The maximum of the scale is unknown.** The caption is garbled (*"we were greatest a 20 towards
   yourself because it's 10 per time frame"*). Four timeframes are named elsewhere ⇒ 40; sub-4H is
   excluded from directional scoring in the same breath ⇒ 30. **MOGO must not pick one.**
2. **The weights are uniform**, so the "score" is only a count — despite his claim elsewhere that
   higher timeframes are stronger (`|20260727|007`, `|008`). A latent inconsistency, recorded.
3. **His own example contradicts the simple reading:** weekly bearish, daily **bullish**, 4H bearish,
   and he trades bearish. "Two in sync" tolerates a disagreeing timeframe between two agreeing ones
   at no cost. Whether it should is never stated.

## 7. Replay candidates created — 3 (RC-22, RC-23, RC-24)

| ID | Test | Needs |
|---|---|---|
| **RC-22** | Does the two-timeframe-sync gate improve outcomes, monotonically with agreement count? | multi-timeframe price data |
| **RC-23** | Does the LH/LL box constraint beat "any well-respected S/R level"? | price data — **needs no entry model at all** |
| **RC-24** | Potential vs completed lower high — settles `XCONTRA\|20260728\|003` | price data |

RC-22 explicitly tests the **agreement count**, which is stated unambiguously, and leaves the
threshold alone — testing a pass/fail line would require inventing the scale maximum.

**The library now holds 24 replay candidates and has executed none.**

## 8. Unsupported claims

**$60,000/day on gold and $50,000/day on GBP/JPY**, causally attributed to the technique being taught
and stated in the same breath as a watch purchase. No statement, date, position size, risk or record.
Typed `performance_hypothesis` — structurally ineligible to become a rule candidate — blocked
`critical`. **Must never be treated as evidence-backed.**

**Deferred to a paid product:** the B/B+ percentage grading scale, and the detail behind the
structure teaching, are both explicitly referred to a three-day bootcamp. Not derivable here and not
to be reconstructed by inference.

## 9. Missing definitions

| Gap | Consequence |
|---|---|
| **Scale maximum** for the 10-point timeframe score | A threshold without its scale is not implementable |
| **"The proper session"** | Named as required and defined nowhere — **second time across four sources** (`\|20260728\|013` "the right times"). MOGO must not supply a session list; TJR's sessions are evidenced for TJR only |
| **EMA period** | First indicator reference in any Alex G source, and unspecified — not reproducible |
| **"Break out of the box"** | Body close or wick? Sources #1/#2 require a body close; not restated here |
| **Touch count** | "Most touches" with no minimum, where source #3 gave ">3 taps ideal" |
| **Stop / target / risk** | ❌ **Four Alex G sources, still zero.** No Alex G claim can be replayed for P&L — only for trigger accuracy |

## 10. Engineering findings — two pipeline defects

### H25 — chapter headings corrupted segment text ✅ **fixed at the root**

YouTube chapter markers (`Chapter 2: TPT`) carry no duration label, fell through the
`youtube_duration_label` profile's no-timestamp branch, and were **kept as spoken text at 0:00** —
splicing non-speech into segment `rawText` and stamping four segments 0:00. This is the exact
corruption the `youtube_timestamp_lines_chaptered` profile was written to prevent, in a profile that
had never met a chaptered transcript.

No excerpt crossed a heading, so no evidence was affected — **but that was luck, not design.**

Fixed lexically in `transcript_normalize.py` (`_CHAPTER_HEADING`), carrying the running timestamp
forward so a section beginning at a heading is not stamped 0:00. Line count preserved, so
reversibility and the coverage assertion are unaffected. **The intake was rolled back and re-applied
on the corrected normalization**, and all three integrity reports came back at zero.

### H24 — `--rollback` leaves dangling records ⚠️ **open**

The rollback removed 258 records and the `foreign`-claim guard **held correctly** — 9 claims shared
with earlier sources were kept and recomputed rather than deleted. But it left the
ContradictionRecord it had created pointing at a claim it had just deleted (caught immediately as an
`INVALID_CONTRADICTION_RECORD` **ERROR** by the validator), plus 80 snapshot records that had to be
identified by build timestamp and removed by hand. Logged as `BACKLOG-003/H24`.

## 11. Files created or modified

**Created**
```
docs/trader-intelligence/intake/completed/alexg-area-of-interest-markup.txt
docs/trader-intelligence/intake/manifests/alexg-area-of-interest-markup.ingest.json
docs/trader-intelligence/imports/alex-g/raw/alexg-area-of-interest-markup.raw.txt (+ .sha256)
docs/trader-intelligence/imports/alex-g/normalized/…normalized.txt + …normalization-map.json
docs/development/logs/2026-07-28-session-alexg-area-of-interest.md
evidence/: 1 source · 1 intake · 13 segments · 31 annotations · 31 items · 20 claims · 31 links
           · 37 questions · 1 contradiction · 1 blueprint · 1 profile · 11 gaps · 52 hypotheses
```

**Modified**
```
scripts/trader_intelligence/transcript_normalize.py        (H25 fix: _CHAPTER_HEADING)
docs/trader-intelligence/evidence/sources/ (×4)            (verified titles + channel)
docs/trader-intelligence/CROSS-STRATEGY-ANALYSIS.md        (v3 → v4, new §3c, §3d, C0)
docs/trader-intelligence/GLOSSARY.md                       (+5 terms, 32 → 37)
docs/trader-intelligence/RESEARCH-LOG.md                   (cycle 010 + ROI review)
docs/trader-intelligence/OPERATOR-PLAYBOOK.md              (Stage 0 publisher verification)
docs/trader-intelligence/proposals/REPLAY-CANDIDATES.md    (RC-22, RC-23, RC-24)
docs/trader-intelligence/proposals/BACKLOG-003-pipeline-hardening.md (H24, H25)
docs/trader-intelligence/queues/validation/VALIDATION-QUEUE.md (14 → 18 entries)
docs/trader-intelligence/KNOWLEDGE-DASHBOARD.md            (regenerated)
docs/trader-intelligence/graph/build/…                     (BUILD|20260728|005)
```

**Untouched:** `index.html`, `APP_VERSION`, all 63 protected functions and 4 protected constants,
JVM, ALEX, and all trading execution logic.

## 12. Updated knowledge metrics

| Metric | Before | After | Δ |
|---|---|---|---|
| Transcripts processed | 5 | **6** | +1 |
| Educators | 2 | 2 | — |
| Claims | 137 | **157** | +20 |
| Evidence items | 168 | **199** | +31 |
| Segments | 92 | **105** | +13 |
| Open questions | 83 | **120** | +37 |
| Contradictions | 5 | **6** | +1 (first **within-educator** since cycle 001) |
| Replay candidates | 21 | **24** | +3 |
| Rule candidates | 0 | **0** | — |
| Graph nodes / edges | 812 / 1,542 | **1,021 / 1,958** | +209 / +416 |
| **Independent confirmations** | 0 | **0** | — |
| **Confidence changes** | — | **0 state changes** | — |
| Claims at `supported` or above | 0 | **0** | — |
| **Sources with verified publisher** | 0 | **5 of 6** | +5 |

---

## The finding that matters most

**An unverified constraint had been propagating into the provenance record as if it were a fact
about the world.**

Five cycles recorded PROVISIONAL titles on the stated ground that "this environment has no network
access." One call disproved it, verified four sources, and surfaced an owner-supplied title that did
not match the published one. The provenance system was working exactly as designed — it recorded the
uncertainty honestly and never invented a title — but it was recording a *self-imposed* limit as
though it were an external one.

That generalises past titles. The same question is worth asking of every "cannot be verified" in the
library: is it genuinely unverifiable, or merely unattempted? **Publisher verification is now a
Stage 0 gate in the Operator Playbook**, because `author_name` decides the educator, and under
`DECISION|MOGO|20260727|006` the educator decides the independence group — which decides confidence.

## Next recommended action

**Unchanged for a fourth cycle: authorize replay and source price data.**

Six sources, 157 claims, 24 replay candidates, **zero executed, zero confidence movement.** RC-23 is
the cheapest test the library has ever held — it needs no entry model, no risk model and no
threshold, only the order in which price reaches levels. RC-13 and RC-20 remain the most decisive.

The library's binding constraint has not been knowledge for several cycles. It is authorization:
`replayAuthorization` is `false` on all six OwnerDecisions, and MOGO holds no market data for any
instrument.

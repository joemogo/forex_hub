# Session Report — Alex G Transcript Ingestion (Transcript #3)

**Date:** 2026-07-27 · **Workstream:** Trader Intelligence
**Source:** `EVSRC|ALEX_G|20260727|001` — "Why 99% of Traders Fail in Forex"
**URL:** `https://www.youtube.com/watch?v=pD1vAUMbSjw`
**Status:** Applied, validated, awaiting owner review. **Nothing committed, tagged or pushed.**

---

## Objective

Ingest the first **non-TJR** educator through the approved workflow; compare against all prior
material; update every downstream artifact; identify new concepts, reinforced concepts,
contradictions, implementation candidates and replay candidates; promote nothing without evidence.

## Ingestion result

| | |
|---|---|
| Raw archive | `imports/alex-g/raw/alexg-why-99-percent-of-traders-fail.raw.txt` + `.sha256` |
| SHA-256 / size | `c9c4193a…674606` · 38,330 bytes · 654 lines · ~33 min |
| Normalization | `youtube_timestamp_lines_chaptered` (new profile) — 332 lines transformed, 1,939 chars removed, **zero words changed**, reversibility asserted per line |
| Sections | 17, cut on the video's own chapter boundaries |
| Extraction | 37 annotations → **35 claims** · 2 within-source corroborations · 1 cross-source contradiction |
| Open questions | 6 authored + 22 auto-detected |
| Knowledge Library | `BLUEPRINT\|ALEX_G\|20260727\|001` · `PROFILE\|ALEX_G\|20260727\|001` · 13 gaps · 22 hypotheses |
| Graph | `BUILD\|20260727\|015` — **517 nodes, 952 edges, zero findings** |
| Integrity | Evidence 0 findings · provenance 132 checks, 0 findings |
| Regression | 530/530 JS · zero protected-function drift · `index.html` untouched |

**Library totals: 3 sources · 2 educators · 104 claims · 123 evidence items · 60 segments.**

---

## New concepts (no prior analogue in the library)

Top-down analysis as a named ordered procedure · timeframe hierarchy with precedence (HTF overrides
LTF; below 15m "not strong") · structure re-anchoring (new HH forces new HL, new LL forces new LH) ·
area of interest must sit **inside** HH/HL · AOI confluence by weekly+daily overlap · sequencing rule
(the HH always leads, the paired HL is always behind) · counter-trend retracement is expected and
necessary.

## Reinforced concepts

Trend definitions (independently restated) · a **close** not a touch changes structure · direction
alone is not an entry · prior significant levels anchor the setup.

## Contradictions

**`XCONTRA|20260727|003` · DEFINITIONAL · material · CROSS-EDUCATOR — the library's first.**
Alex G marks structure at candle **bodies** (*"not at the wick"*); TJR marks a high at the **highest
wick** of the two candles forming it. Same operation, incompatible price levels, everything
downstream moves with it. Recorded, not resolved.

Both educators agree a **close** beyond the level is required — they disagree only on which part of
the candle closes. One isolated parameter.

## Implementation candidates

- **First FX-native ingested method.** Alex G's needs no instrument abstraction; MOGO's pip-based
  risk model already fits. Still 🔴 — the source states **no stop rule, no target rule and no risk
  rule at all.**
- **Top-down bias ≈ JVM `bias3`+`bias2`** (40 of a 55 threshold — JVM's largest input). A rule-based
  version of what JVM already weights.
- **Three-way split on candlestick patterns:** Alex G makes dojis/engulfing the entry trigger; JVM
  prices `wick`+`engulf` at 35/55; TJR removed them entirely. `RC-02` upgrades to a cross-strategy
  question.

## Replay candidates added

- **`RC-10` — bodies vs wicks.** Mark identical data both ways; report the % of bars where the two
  conventions disagree about the current trend. **Needs no risk model, no TP ladder, no instrument
  abstraction** — the cheapest genuinely decisive experiment in the library. Priority 2.
- **`RC-11` — does higher-timeframe alignment improve outcomes?** Alex G's central claim and the
  answer to TJR's largest gap. Blocked on the missing risk rule for any P&L result.

---

## The two findings that matter most

**1. The strongest cross-educator agreement in the library raised no confidence.**
TJR: *"an uptrend which consists of higher highs and higher lows."* Alex G: *"a bullish market is
created of higher highs and higher lows."* Different educator, instrument, timeframe, method —
near-identical wording. **All 104 claims remain `emerging`; 0 claims have 2+ supporting sources.**

The cause is deliberate: `compute_claim_fingerprint()` includes `traderId`, so trader-scoped claims
never merge. That is correct — a TJR claim must not silently absorb someone else's evidence — but it
means **cross-educator agreement has no path to raise confidence at all.** `PROPOSAL-003` §4 asked
this question and answered *no*; this is the concrete case arguing otherwise.
**Recommendation: a separate Concept-level consensus count, leaving claim confidence untouched.**

**2. The two educators are complementary, not competing.**
TJR's largest open gap is `higher_timeframe_bias`. Alex G's method is *nothing but* higher-timeframe
bias and stops before entry mechanics — which is all TJR provides. First time the library has held
two sources that could, in principle, compose.

---

## Engineering: bugs found and fixed this session

| # | Issue | Fix |
|---|---|---|
| 1 | **New profile's first detector regressed TJR#2** — a purely structural "anything before the first timestamp is chrome" rule ate a genuine opening sentence | Tightened to require the literal `Search in video` UI marker. Both prior sources re-verified byte-identical |
| 2 | **Queue move happened after dashboard regeneration**, so the dashboard reported the just-ingested transcript as still awaiting work | Move now precedes regeneration |
| 3 | **Ceiling metric counted all independence groups**, including contextual links that contribute nothing to the score — overstating how close claims were to `supported` | Now counts only `supports`/`exemplifies` groups, and reports how many claims have 2+ |
| 4 | Trader records still said `externalResearchStatus: not_started` despite 3 ingested sources | TJR and ALEX_G set to `partial`, with a note explaining why not more |

**Capabilities added:** `youtube_timestamp_lines_chaptered` normalization profile (with an
operator-facing report of every line classified non-spoken, for eyeball verification);
cross-manifest contradictions (`aClaimId` / `bClaimId`) — without which the first cross-educator
contradiction could not have been recorded.

## Deliberate refusals

- **No instrument claim from the video title.** The title says Forex; the *spoken* transcript never
  names an instrument or pair. Recorded as metadata, not as a claim.
- **No cross-educator evidence linking.** Attaching Alex G's evidence to TJR-scoped claims would
  have raised confidence and read as corroboration — and conflated "TJR asserts X" with "X is true".
- **Contradiction recorded, not resolved.** Neither educator marked correct.

---

## Owner decisions required

**D1 — Does MOGO's ALEX_G engine match what Alex G teaches?**
MOGO ships a live paper-trading engine attributed to Alex G doing Break & Retest / Repeated Zone
Reaction. The ingested material teaches top-down bias → AOI inside structure → rejection-candle
entry. **Nothing establishes these are the same method**, and one source cannot settle it.
*Recommendation:* acquire more Alex G material, then audit the engine against the 35 claims now on
record. Until then, no Alex G-derived change should touch the shipped engine.
*ROI:* high — a correctness question about live paper-trading behaviour.

**D2 — Should cross-educator consensus be counted?**
*Recommendation:* add Concept-level consensus counting with the Concept Registry; do **not** let
concepts mediate claim confidence.
*ROI:* this is the mechanism by which a multi-educator library becomes more than a pile of separate
ones.

**Still open:** the 4 obsolete tests · FX-vs-multi-asset · whether to commit.

---

## Next recommended action

**Acquire more Alex G material.** It serves three goals at once: same-educator corroboration (the
only route that currently raises confidence), the D1 governance question about the shipped engine,
and the missing risk/exit half of his method — see `BACKLOG-002` targets **A1–A5**.

**Three sources in, zero confidence movement.** Foundational content defines; strategy content
corroborates. Acquisition must now target *restatement* of rules already on record, or replay.

## Artifacts updated

`CROSS-STRATEGY-ANALYSIS.md` (v2) · `GLOSSARY.md` (28 terms, 2 educators) · `RESEARCH-LOG.md`
(cycle 007) · `KNOWLEDGE-DASHBOARD.md` · `REPLAY-CANDIDATES.md` (RC-10, RC-11) ·
`MOGO-IMPLEMENTATION-CANDIDATES.md` · `BACKLOG-002` (A1–A5) · trader records for TJR and ALEX_G ·
graph build and both integrity reports.

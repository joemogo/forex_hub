# Session Report — Alex G "Liquidity and Liquidity Sweeps" (Transcript #5)

**Date:** 2026-07-28 · **Workstream:** Trader Intelligence
**Source:** `EVSRC|ALEX_G|20260728|002` · `https://www.youtube.com/watch?v=Rua24ytuHuY`
**Status:** Applied, validated, awaiting owner review. **Nothing committed, tagged or pushed.**

---

## 1. Ingestion status

✅ **Complete.** `INTAKE|ALEX_G|20260728|002` at `review_required`.

| | |
|---|---|
| Raw archive | `imports/alex-g/raw/alexg-liquidity-and-liquidity-sweeps.raw.txt` + `.sha256` (byte-verified) |
| SHA-256 / size | `175af73d…bc39c2` · 23,870 bytes · 1,097 lines |
| Normalization | `youtube_timestamp_lines` — markers removed, **zero words changed**, reversibility asserted per line |
| Sections | 15, cut by hand on timestamp/topic boundaries (`BACKLOG-003/H22` still open) |
| Graph | `BUILD\|20260728\|003` — **812 nodes, 1,542 edges, zero findings** |
| Integrity | Evidence 0 findings · provenance **183 checks, 0 findings** |
| Regression | 307 Python (4 known-obsolete failures) · 530/530 JS · **zero protected-function drift** |

## 2. Source metadata — title **PROVISIONAL, unverified**

**`Liquidity and Liquidity Sweeps (PROVISIONAL — derived from transcript content, actual YouTube
title unverified)`**

No metadata block was supplied with this transcript. The URL was recovered from the final line of
the transcript text itself; the educator was identified from content continuity with sources #3 and
#4. The title is derived from subject matter and is **marked unverified in every record** rather
than guessed at — this environment has no network access.

## 3. New knowledge added — 19 new claims

Liquidity as order concentration at a price point · liquidity concentrates at repeatedly rejected
levels · **>3 taps ideal, 1 tap materially weaker** · higher timeframes carry stronger zones ·
round psychological numbers concentrate exits · a sweep is stop-orders being filled · **sweeps
cannot be anticipated or systematised** · enter on confirmation, not anticipation · a counter-move
disqualifies rather than signals · named confirmation patterns (engulfing, morning star, pin bar,
multiple dojis) · **no evidence institutions deliberately liquidate retail** · retail is 3% of the
market (unsourced) · don't buy the high / sell the low · the seven-approaches-one-sweep
opportunity-cost example · liquidity terminology is five interchangeable names for one thing.

## 4. Same-educator restatements — 5 (2 within-source, 3 cross-source)

All shared independence group `AUTHOR|ALEX_G` under `DECISION|MOGO|20260727|006`. Evidence counts
rose; scores moved within-band under the 25% same-group discount. **Zero confidence state changes.**

## 5. Independent cross-source confirmations — **0**

Unchanged for a fifth consecutive source. Both non-replay routes remain closed by design.

## 6. Contradictions discovered — **2 new, both cross-educator, one `blocking`**

### `XCONTRA|20260728|001` · DIRECTIONAL · **blocking** — the library's first

| | |
|---|---|
| **TJR** | *"My strategy is based off of liquidity sweeps"* |
| **Alex G** | *"There's no way that you can have a specific strategy to trade solely off of these sweeps"* — anyone claiming otherwise *"is 100% lying to you"* |

One educator's entire method is the thing the other says cannot be done consistently.

**Partial reconciliation, recorded but not applied.** Alex G objects to *anticipating* a sweep; TJR
reacts to a sweep that has already occurred and then requires a separate confirmation confluence.
On that reading they are much closer than the words suggest. **That reading is MOGO's, not either
educator's**, so the record stays `blocking` and open — per approved decision 3, contradictions are
recorded, not resolved prematurely.

### `XCONTRA|20260728|002` · DEFINITIONAL · material — the mechanism

TJR: market makers sweep levels to fill large positions. Alex G: *"there is no real hardcore
evidence that this is a bank or an institution"*, *"almost a big hoax."*

**The asymmetry matters:** TJR asserts a mechanism; Alex G asserts the absence of proof for it.
Alex G is the first source in the library to argue epistemically rather than about market
behaviour — though his own argument rests on an unsourced 3%-of-market statistic.

## 7. Replay candidates created — 2 (RC-20, RC-21)

| ID | Test | Needs |
|---|---|---|
| **RC-20** | **Sweep-then-reverse vs confirmation-on-arrival.** Measures the sweep ratio — what fraction of approaches to a repeated-rejection zone actually sweep — and conditional forward outcome | **price data only** |
| RC-21 | Do sweeps cluster at session boundaries? Controls RC-20's main confound | price data with session timestamps |

**RC-20 is the highest-value test the library has ever held.** It settles the only `blocking`
contradiction, needs no risk model, and **Alex G supplied the measurement himself** — one zone,
seven approaches, one sweep.

**RC-21 is explicitly bounded:** it can test *whether* sweeps cluster; it can **never** test *why*.
No dataset available to MOGO can establish institutional intent, so the mechanism contradiction is
empirically unresolvable here and stays open. Stated in the candidate rather than left implicit.

## 8. Unsupported claims and self-inconsistency

**Retail is 3% of the market** — no source, no date, no definition of "the market". It is the load
bearing premise of Alex G's entire scepticism argument. Typed `performance_hypothesis`, low quality,
own open question.

**Self-inconsistency, `critical`.** Alex G describes his own live AUDCHF position as *"entering a
trade technically after the liquidity sweep"* — the thing the video argues cannot be systematised.
Filed as an open question against him, exactly as TJR's on-camera deviations from his own rules were
in cycle 001. **Both educators are held to the same standard** (`DECISION|MOGO|20260727|004`).

**Rhetorical absolutism** — *"100% lying to you"* — recorded as stated, not softened.

## 9. Missing definitions

| Gap | Consequence |
|---|---|
| **"Repeatedly rejected"** | ">3 taps ideal" is the only quantification; no tolerance band, no lookback, no zone width |
| **Confirmation candle** | Five patterns named, none defined precisely enough to code |
| **Stop / target / risk** | ❌ **Three Alex G sources, still zero `stop_rule`, `target_rule`, `risk_rule` claims.** No longer plausibly an omission — a structural gap in his published material. **No Alex G claim can ever be replayed for P&L, only for trigger accuracy** |
| **Terminology** | Five terms explicitly collapsed into one referent — support/resistance, supply and demand, order block, area of interest, liquidity zone. Strongest evidence yet for `PROPOSAL-003` |

## 10. Files created or modified

**Created**
```
docs/trader-intelligence/intake/completed/alexg-liquidity-and-liquidity-sweeps.txt
docs/trader-intelligence/intake/manifests/alexg-liquidity-and-liquidity-sweeps.ingest.json
docs/trader-intelligence/imports/alex-g/raw/alexg-liquidity-and-liquidity-sweeps.raw.txt (+ .sha256)
docs/trader-intelligence/imports/alex-g/normalized/…normalized.txt + …normalization-map.json
docs/development/logs/2026-07-28-session-alexg-liquidity.md
evidence/: 1 source · 1 intake · 15 segments · 24 annotations · 24 items · 19 claims · 24 links
           · 21 questions · 2 contradictions
```

**Modified**
```
docs/trader-intelligence/CROSS-STRATEGY-ANALYSIS.md        (v2 → v3, new §3b)
docs/trader-intelligence/GLOSSARY.md                       (+4 terms, 28 → 32)
docs/trader-intelligence/RESEARCH-LOG.md                   (cycle 009 + ROI review)
docs/trader-intelligence/proposals/REPLAY-CANDIDATES.md    (RC-20, RC-21)
docs/trader-intelligence/queues/validation/VALIDATION-QUEUE.md (12 → 14 entries)
docs/trader-intelligence/KNOWLEDGE-DASHBOARD.md            (regenerated)
docs/trader-intelligence/graph/build/{nodes,edges,manifest}.json + both integrity reports
```

**Untouched:** `index.html`, `APP_VERSION`, all 63 protected functions and 4 protected constants,
JVM, ALEX, and all trading execution logic.

## 11. Updated knowledge metrics

| Metric | Before | After | Δ |
|---|---|---|---|
| Transcripts processed | 4 | **5** | +1 |
| Educators | 2 | 2 | — |
| Claims | 118 | **137** | +19 |
| Evidence items | 144 | **168** | +24 |
| Segments | 77 | **92** | +15 |
| **Contradictions** | 3 | **5** | **+2, both cross-educator** |
| **Blocking contradictions** | 0 | **1** | **+1 — first in the library** |
| Replay candidates | 19 | **21** | +2 |
| Rule candidates | 0 | **0** | — |
| Graph nodes / edges | 650 / 1,214 | **812 / 1,542** | +162 / +328 |
| **Independent confirmations** | 0 | **0** | — |
| **Confidence changes** | — | **0 state changes** | — |
| Claims at `supported` or above | 0 | **0** | — |

---

## The finding that matters most

**Five cycles produced agreement that could not raise confidence. This one produced a disagreement
that can.**

Cross-educator agreement never merges (trader-scoped fingerprints) and same-educator repetition
never corroborates (DECISION 006) — so every prior cycle's convergence was, by design, inert.
Cycle 009 is different: Alex G and TJR now hold **opposite positions on a foundational premise**,
and Alex G handed over the exact metric that settles it. Disagreement is the more actionable signal
here, because it is falsifiable and agreement was not.

There is also a governance consequence. `XCONTRA|20260728|001` is `blocking`, and it sits under the
premise of TJR's entire method. **Any future MOGO component built on sweep detection is
provisionally expensive until RC-20 runs** — that is now a recorded constraint, not an opinion.

## Next recommended action

**Unchanged, and now more acute: authorize replay and source price data.**

Five sources in, zero confidence movement, and the library holds a blocking contradiction that
cannot be resolved by reading more transcripts. `RC-20` and `RC-13` are both decisive and both need
one instrument's OHLC and nothing else.

Neither is an engineering task — `replayAuthorization` is `false` on all six OwnerDecisions, and
MOGO holds no market data for any instrument.

# Session Report — Alex G "The ONLY confirmation YOU need to make $1000/day Trading Forex" (Transcript #7)

**Date:** 2026-07-28 · **Workstream:** Trader Intelligence
**Source:** `EVSRC|ALEX_G|20260728|004` · `https://www.youtube.com/watch?v=BcWxqfcjk9A`
**Channel:** `fxalexg` (`@fxalexg__`) — **verified before extraction**
**Status:** Applied, validated, awaiting owner review. **Nothing committed, tagged or pushed.**

---

## 1. Ingestion status

✅ **Complete.** `INTAKE|ALEX_G|20260728|004` at `review_required`.

| | |
|---|---|
| Raw archive | `imports/alex-g/raw/alexg-entry-confirmation.raw.txt` + `.sha256` (byte-verified) |
| SHA-256 / size | `ac65aa88…0cbbe3` · 29,329 bytes · 168 lines · ~21:55 |
| Normalization | `youtube_duration_label` — 166 lines transformed, zero words changed, reversibility asserted per line |
| Sections | 15, cut by hand on topic boundaries |
| Graph | `BUILD\|20260728\|006` — **1,286 nodes, 2,498 edges, zero findings** |
| Integrity | Evidence **0** · graph **0** · provenance **262 checks, 0 findings** |
| Regression | 307 Python (4 known-obsolete) · 530/530 JS, 0 execution errors · **zero protected-function drift** |

## 2. Source metadata — verified at Stage 0, as the playbook now requires

The publisher-verification gate added in cycle 010 ran **before** extraction. `author_name` returned
`fxalexg` — the same channel as sources #3–#6 — so these 35 claims joined independence group
`AUTHOR|ALEX_G` knowingly rather than by assumption.

⚠️ **Title/content discrepancy recorded, not resolved.** The published title claims **$1000/day**;
the spoken content says **$500 a day**, twice. Both are recorded; MOGO does not choose between them.

⚠️ **Known artifact.** The pasted transcript had the video URL fused onto the first timestamp
(`…BcWxqfcjk9A0:000 secondsThere's a specific…`), so line 1 fell through the duration-label pattern
and the URL is retained as spoken text at 0:00. No excerpt was taken from line 1. Recorded in the
manifest's `provenance.knownArtifacts` and logged as `BACKLOG-003/H26`.

## 3. New knowledge added — 35 new claims

This is the most rule-dense source in the library.

**The trigger, stated precisely:** a confirmation is a **closed** candle — *"as soon as that
candlestick closes, it is a confirmation. One second before it closes, it is an entire
anticipation"* — that is either a rejection/doji or an engulfing, occurring **at a level**, in the
**direction of the trend**. Absolute gate: no confirmation, no trade, restated verbatim in the
summary. Engulfing requires a body close beyond the prior candle; size irrelevant, side is not.

**The wick-fill mechanism:** a daily candle that looks like a rejection may be a 4-hour higher low
forming. Cross-reference the 4H within the same day: bearish into the zone → bullish shift → retest.

**Session and day rules:** enter inside high-volume windows; hold an early confirmation until the
session — *"that's the black and white rule"*; **Monday, Tuesday, Wednesday only**, because an
80–100 pip average target needs enough remaining volume hours.

**Also:** patterns are everywhere and worthless out of context · away from a level the rule is
"simply not applicable" · pro-trend only, and a counter-signal **skips** the trade rather than
reversing it · direction persists (nearly a month on swing horizons) · entering on a candle without
a strategy is "gambling" · the extra-confirmation trade-off forfeits winners and that cost is
accepted · the ~70% next-day continuation claim · the $500/day claim.

## 4. Reinforced — 7 same-educator restatements, 0 independent confirmations

`ALEX_G|20260728|028` (confirmation not anticipation), `|030` (named patterns), `|018` (terminology
collapse), `|008` (size-agnostic), `|20260727|032` (higher timeframe stronger), and others.
All within `AUTHOR|ALEX_G`. **Zero confidence state changes. Zero rule candidates. Sixth consecutive
source with no independent confirmation.**

## 5. The headline — the method is now complete **except for the stop**

| Layer | Rule | Source | Status |
|---|---|---|---|
| Direction | ≥2 of weekly/daily/4H aligned, 10 pts each | #4 | ⚠️ scale maximum unknown |
| Zone | Most-touched level inside the LH/LL box | #4 | ✅ |
| Trigger | Closed rejection or engulfing, at a level, pro-trend | **#5** | ✅ stated precisely |
| Timing | Wait for the session; Mon/Tue/Wed only | **#5** | ⚠️ hours never spoken |
| Target | ~80–100 pips average | **#5** | ⚠️ descriptive, not a selection rule |
| **Stop** | — | — | ❌ **absent from five sources** |
| **Risk per trade** | — | — | ❌ **absent from five sources** |

**This source makes the absence structural rather than incidental.** It names risk-to-reward as an
input to a live decision and refers to *"where my stop loss would have been"*, *"more breathing
room"*, *"better stop-loss"* — and never states how a stop is placed. A method that reasons about
risk-to-reward without defining the risk leg is incomplete at exactly the point where profitability
is decided.

**Permanent consequence: no Alex G claim can ever be replayed for P&L.** RC-12 through RC-26 all
measure trigger accuracy, reach-rate or direction. None can produce an expectancy. That is a
property of the source material, not a limitation of the replay harness.

## 6. The session gap — downgraded, not closed

Open since source #2 (*"trading at the right times"*) and source #4 (*"the proper session"*), session
timing is now a **prescriptive rule with a stated rationale**, and the day filter is precise and
falsifiable.

❌ **But the windows are shown as coloured bands on an on-screen map and never spoken.** Sydney,
London and New York are named; no hours are given. **MOGO must not supply them** — TJR's sessions are
evidenced for TJR, on US indices.

## 7. Contradictions — 2 new, both **within-source**

### `XCONTRA|20260728|005` · DIRECTIONAL · material

Thesis, stated three times: *"entering off of a confirmation, not an anticipation."*
At 6:37, same video: *"that perfect higher low is where you can then **anticipate** that wick fill."*

**Fourth record of this inconsistency in Alex G's material, and the first internal to a source whose
entire subject is the rule being broken.** A reconciliation exists — anticipate the *setup*, require
a closed candle to *enter* — and he never states it, so adopting it would be MOGO resolving a
contradiction on his behalf.

### `XCONTRA|20260728|004` · CONDITIONAL_SCOPE · material

At 16:56: waiting for the session sometimes loses the trade outright — *"completely gone from the
direction, gone from the area where I was interested in taking."*
At 18:51: *"there's no negative"* — enumerating three outcomes, none of which is the forfeited trade
he had just described.

**The claim is not wrong about the cases it lists; it is incomplete, and the missing case is the only
one with an unbounded cost.** The cleanest example the library has produced of a claim that sounds
like reasoning and is falsified by the source's own evidence. No external data was needed — only
reading the whole transcript instead of the summary.

## 8. Replay candidates created — 2 (RC-25, RC-26)

| ID | Test | Needs |
|---|---|---|
| **RC-25** | The ~70% next-day continuation setup | daily + 4H price data |
| **RC-26** | What waiting for the session actually costs | intraday data with session timestamps |

**RC-25 is the best first test the library has ever held.** Every prior candidate had to be assembled
from claims across sections. This one is stated by the source as a complete, countable conditional
with a number attached. Two terms are undefined ("strong" wick, "bullish push"), so the test sweeps
both thresholds and reports the surface — and computes the base rate of "next day is up" as the
control **first**. If 70% appears only at one hand-picked pair of thresholds, that is the finding.

## 9. Unsupported claims

**~70% next-day continuation** — no sample, period, instrument or definition of "bullish push".
Ineligible as a claim; uniquely, the underlying **setup** is fully specified and therefore testable.
RC-25 tests the setup, not the number.

**$500/day** (spoken) vs **$1000/day** (published title) — neither evidenced, no capital base.

**"I've seen candlesticks in the last 5 seconds before closing completely change direction"** —
offered as the rationale for the closure rule, with no frequency.

## 10. Missing definitions

| Gap | Consequence |
|---|---|
| **Session hours** | The rule is prescriptive and its parameters are missing — `critical` |
| **Stop placement / risk per trade** | Five sources, zero. **Blocks all P&L replay permanently** |
| **Engulfing** | Body-engulfs-body or body-closes-beyond-range? Different detectors, different bars |
| **"More dojis is more powerful"** | No count, no threshold at which behaviour changes |
| **Pro-trend** | Trend defined on which timeframe? Not stated here |
| **Day-rule overrides** | "shorter" TP, "very strong" confirmation, "a lot of" momentum — three unquantified overrides make the black-and-white rule unfalsifiable in practice |
| **Discretion inputs** | Five named inputs to the second-confirmation decision, no thresholds on any |

## 11. Files created or modified

**Created**
```
docs/trader-intelligence/intake/completed/alexg-entry-confirmation.txt
docs/trader-intelligence/intake/manifests/alexg-entry-confirmation.ingest.json
docs/trader-intelligence/imports/alex-g/raw/alexg-entry-confirmation.raw.txt (+ .sha256)
docs/trader-intelligence/imports/alex-g/normalized/…normalized.txt + …normalization-map.json
docs/development/logs/2026-07-28-session-alexg-entry-confirmation.md
evidence/: 1 source · 1 intake · 15 segments · 42 annotations · 42 items · 35 claims · 42 links
           · 44 questions · 2 contradictions · 1 blueprint · 1 profile · 10 gaps · 65 hypotheses
```

**Modified**
```
docs/trader-intelligence/CROSS-STRATEGY-ANALYSIS.md        (v4 → v5, new §3e, C-1, C-2)
docs/trader-intelligence/GLOSSARY.md                       (+5 terms, 37 → 42)
docs/trader-intelligence/RESEARCH-LOG.md                   (cycle 011 + ROI review)
docs/trader-intelligence/proposals/REPLAY-CANDIDATES.md    (RC-25, RC-26)
docs/trader-intelligence/proposals/BACKLOG-003-pipeline-hardening.md (H26)
docs/trader-intelligence/queues/validation/VALIDATION-QUEUE.md (18 → 22 entries)
docs/trader-intelligence/KNOWLEDGE-DASHBOARD.md            (regenerated)
docs/trader-intelligence/graph/build/…                     (BUILD|20260728|006)
```

**Untouched:** `index.html`, `APP_VERSION`, all 63 protected functions and 4 protected constants,
JVM, ALEX, and all trading execution logic.

## 12. Updated knowledge metrics

| Metric | Before | After | Δ |
|---|---|---|---|
| Transcripts processed | 6 | **7** | +1 |
| Educators | 2 | 2 | — |
| Claims | 157 | **192** | +35 |
| Evidence items | 199 | **241** | +42 |
| Segments | 105 | **120** | +15 |
| Open questions | 120 | **164** | +44 |
| Contradictions | 6 | **8** | +2 (both within-source) |
| Replay candidates | 24 | **26** | +2 |
| Rule candidates | 0 | **0** | — |
| Graph nodes / edges | 1,021 / 1,958 | **1,286 / 2,498** | +265 / +540 |
| ALEX_G `session_rule` claims | 1 | **6** | +5 |
| ALEX_G `target_rule` claims | **0** | **1** | +1 — *first in five sources* |
| ALEX_G `stop_rule` / `risk_rule` claims | **0** | **0** | — |
| **Independent confirmations** | 0 | **0** | — |
| **Confidence changes** | — | **0 state changes** | — |
| Claims at `supported` or above | 0 | **0** | — |

---

## The finding that matters most

**The shape of the incompleteness is diagnostic.**

Five sources have now produced an unusually complete method — direction, zone, trigger, timing,
target — with exactly **one hole, in the one place that determines whether the method makes money.**
That is not a random gap. Free educational content tends to stop precisely where risk begins.

Recording it as a *structural property of the source* rather than a to-be-filled TODO is the correct
handling, and it sets the expectation for every future source from this channel: expect trigger
detail, expect no risk model, and do not let the completeness of the first four layers create the
impression that the fifth is coming.

A second, smaller finding worth keeping: **this video's own four-part summary omits the 4-hour
cross-reference step entirely.** A summary-only extraction would have missed a required step *and*
both contradictions. Where an educator summarises their own method, the delta between body and
summary is itself evidence about which steps they actually rely on.

## Next recommended action

**Unchanged for a fifth cycle: authorize replay and source price data.**

Seven sources, 192 claims, 26 replay candidates, **zero executed, zero confidence movement.**

`RC-25` is now the best first test in the library: fully specified by the source, needs only daily
and 4-hour candles, and carries a number that either survives contact with data or does not. It is a
better opening test than RC-13 or RC-20 because it requires no reconciliation between educators —
only the base rate as a control.

`replayAuthorization` is `false` on all six OwnerDecisions, and MOGO holds no market data.

# Session Report — Alex G "Market break down learn and earn" (Transcript #9)

**Date:** 2026-07-28 · **Workstream:** Trader Intelligence
**Source:** `EVSRC|ALEX_G|20260728|006` · `https://www.youtube.com/watch?v=1JMVE4Y5U7o`
**Channel:** `fxalexg` (`@fxalexg__`) — **verified before extraction**
**Status:** Applied, validated, awaiting owner review. **Nothing committed, tagged or pushed.**

---

## 1. Ingestion status

✅ **Complete.** `INTAKE|ALEX_G|20260728|006` at `review_required`.

| | |
|---|---|
| Raw archive | `imports/alex-g/raw/alexg-live-session-market-breakdown.raw.txt` + `.sha256` (byte-verified) |
| SHA-256 / size | `5bb848bb…d78466` · 7,924 bytes · 438 lines · ~7:40 |
| Normalization | `youtube_timestamp_lines` — 218 lines transformed, zero words changed, reversibility asserted per line |
| Sections | 13, cut on pair and topic boundaries |
| Graph | `BUILD\|20260728\|008` — **1,723 nodes, 3,541 edges, zero findings** |
| Integrity | Evidence **0** · graph **0** · provenance **333 checks, 0 findings** |
| Regression | 307 Python (4 known-obsolete) · 530/530 JS, 0 execution errors · **zero protected-function drift** |

## 2. A different evidence class — the library's first live session

Sources #3–#8 are structured instruction. This is a recorded **6 a.m. call with roughly 70
attendees**, walking NZDCAD, NZDUSD, GBPUSD and GBPJPY in real time. The evidence is predominantly
`demonstrated_behavior` rather than `rule_statement`, which makes it the first material in the
library capable of **testing taught rules against practice**.

## 3. What it corroborates — 11 same-educator restatements, 0 independent confirmations

Pro-trend only (*"never bro, not anymore… that's a rookie thing"*) · wait for the break of structure ·
higher low plus bullish engulfing · prior support/resistance zones · round psychological levels
(86.000) · weekly bias first · lower-timeframe structure shift reading · alarms set on levels.

All within `AUTHOR|ALEX_G`. **Zero confidence state changes. Zero rule candidates. Seventh
consecutive source with no independent confirmation.**

## 4. What it reveals — three filters that appear in no instructional source

| Filter | What it does |
|---|---|
| **Proximity tolerance** | A setup declined because price came **~10 pips short** of 86.000 |
| **Confluence counting** | Direction chosen by counting confluences on *each* side and taking the larger: *"find me this many confluences here to go long — there won't be any"* |
| **"Worth the risk" selectivity** | Trades taken only when judged worth the capital; **month-to-date performance is an input** — *"I've already made money trading this month, so I don't really need to take any trades"* |

## 5. Contradiction — `XCONTRA|20260728|008` · CONDITIONAL_SCOPE · material

**A new category for the library: stated rule versus recorded behaviour.**

| | |
|---|---|
| Taught (#3–#6) | The confirmation must be **at** a support/resistance. Away from one, *"you don't enter the trade and it is simply not applicable"* |
| Demonstrated (#7) | Declined because price was *"shy about, let's say, like 10 pips"* |

The taught rule is **binary**; the demonstrated behaviour is **graded**. No source in the library
supplies a tolerance, a maximum acceptable distance, or any rule for near-misses.

**The consequence generalises beyond this one filter:**

> If a taught rule set systematically omits the discretionary filters its author actually uses, then
> replaying the taught rules measures something the educator does not trade.

That is now a caution on every Alex G replay candidate. It is **not** an accusation of bad faith —
these filters are exactly the kind of judgement that is hard to articulate. It does mean a replay
result must be reported as a test of *the stated method*, not of *his trading*.

## 6. The pattern behind the pattern — parameters are shown, not said

The written confluence list — which **is** the direction rule — is displayed on screen, offered for
screenshotting, and **never read aloud**.

That is the **third visual-only artifact in three sources**:

| Source | Artifact shown but never spoken |
|---|---|
| #4 | The setup grading scale (B / B+ percentages) |
| #5 | The session volume map (which hours are tradeable) |
| **#7** | **The written confluence list** |

Three in a row is not coincidence. **This educator's rule parameters are consistently shown rather
than spoken** — which for a transcript-based pipeline is a *systematic* blind spot, not bad luck. It
bounds what further ingestion can achieve: more transcripts will keep producing rule **shapes**
without their **numbers**.

## 7. Smaller findings

**The EMA finally has a role, and still has no period.** Support while bullish, resistance while
bearish; the preferred entry is where the EMA and prior structure converge on the same retracement.
Two sources now use it as load-bearing and neither states the period.

**A candid admission, recorded as evidence.** A setup identified in advance, with alarms set, was
missed — *"I forgot what I was doing and I wasn't able to get this."* The library holds several
set-and-forget claims; this is the first evidence of the failure mode, and it comes from the source
himself.

**A third R:R figure.** 1:4 here, after 1:2 and 1:3 in source #6 — all three offered as observations
about particular charts, none as a rule. Recorded with an explicit instruction **not** to average
them or take the minimum.

**`stop_rule` still 0, now across seven sources.** This one is live commentary on four pairs
discussing entries, targets and a 1:4 ratio, and never states where a stop goes. The one mention of
*"the area where we could have the stop"* describes where price might stop moving, not an order.

## 8. Replay candidate created — RC-28

Measures the **tolerance curve**: closest-approach distance for every level touch, normalised in pips
*and* as a fraction of ATR (raw pips are not comparable across pairs), bucketed against forward
outcome. A smooth curve would show the binary rule is a simplification and any threshold arbitrary;
a cliff would locate one empirically.

**Explicitly forbidden:** picking a tolerance and encoding it. The point is that no source supplies
one.

## 9. Files created or modified

**Created**
```
docs/trader-intelligence/intake/completed/alexg-live-session-market-breakdown.txt
docs/trader-intelligence/intake/manifests/alexg-live-session-market-breakdown.ingest.json
docs/trader-intelligence/imports/alex-g/raw/alexg-live-session-market-breakdown.raw.txt (+ .sha256)
docs/trader-intelligence/imports/alex-g/normalized/…normalized.txt + …normalization-map.json
docs/development/logs/2026-07-28-session-alexg-live-session.md
evidence/: 1 source · 1 intake · 13 segments · 30 annotations · 30 items · 18 claims · 30 links
           · 25 questions · 1 contradiction · 1 blueprint · 1 profile · 9 gaps · 92 hypotheses
```

**Modified**
```
docs/trader-intelligence/CROSS-STRATEGY-ANALYSIS.md        (v6 → v7, new §3g, C-5)
docs/trader-intelligence/GLOSSARY.md                       (+4 terms, 45 → 49)
docs/trader-intelligence/RESEARCH-LOG.md                   (cycle 013 + ROI review)
docs/trader-intelligence/proposals/REPLAY-CANDIDATES.md    (RC-28)
docs/trader-intelligence/proposals/BACKLOG-002-tjr-source-acquisition.md (A2-LIVE)
docs/trader-intelligence/queues/validation/VALIDATION-QUEUE.md (25 → 28 entries)
docs/trader-intelligence/KNOWLEDGE-DASHBOARD.md            (regenerated)
docs/trader-intelligence/graph/build/…                     (BUILD|20260728|008)
```

**Untouched:** `index.html`, `APP_VERSION`, all 63 protected functions and 4 protected constants,
JVM, ALEX, and all trading execution logic.

## 10. Updated knowledge metrics

| Metric | Before | After | Δ |
|---|---|---|---|
| Transcripts processed | 8 | **9** | +1 |
| Educators | 2 | 2 | — |
| Claims | 226 | **244** | +18 |
| Evidence items | 276 | **306** | +30 |
| Segments | 135 | **148** | +13 |
| Open questions | 180 | **205** | +25 |
| Contradictions | 10 | **11** | +1 (**first behaviour-vs-rule**) |
| Replay candidates | 27 | **28** | +1 |
| Rule candidates | 0 | **0** | — |
| Graph nodes / edges | 1,503 / 3,011 | **1,723 / 3,541** | +220 / +530 |
| ALEX_G `stop_rule` | **0** | **0** | — (seven sources) |
| **Independent confirmations** | 0 | **0** | — |
| **Confidence changes** | — | **0 state changes** | — |
| Claims at `supported` or above | 0 | **0** | — |

---

## The finding that matters most

**The library had, until now, only been reading what this educator says.**

One session of watching what he *does* produced three filters absent from six instructional sources,
and the first contradiction between a stated rule and recorded behaviour. Live sessions are a
materially different evidence class, and acquisition should weight them accordingly — that is now
`BACKLOG-002/A2-LIVE`, and it outranks further instructional videos. The **skips are worth more than
the entries**: an entry confirms a rule already captured, a skip reveals a filter that is not.

The second finding bounds the strategy rather than extending it. **Three sources in a row have had
their key parameters shown on screen and never spoken** — the grading scale, the session map, the
confluence list. That is a systematic property of this educator's material, and it predicts that
further transcript ingestion will keep yielding rule shapes without numbers. If the owner wants those
numbers, transcripts are the wrong instrument, and that should be an explicit decision rather than an
accumulating gap.

## Next recommended action

Three now, in order:

1. **Authorize replay and source price data** — seventh cycle asking. RC-25 remains the best first
   test.
2. **Acquire more live sessions** (`BACKLOG-002/A2-LIVE`) — new this cycle, and it outranks further
   instructional material.
3. **Acquire a stop-placement source, or record that none exists** (`BACKLOG-002/A1-STOP`).

`replayAuthorization` is `false` on all six OwnerDecisions, and MOGO holds no market data.

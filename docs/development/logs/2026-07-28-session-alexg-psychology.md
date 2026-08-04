# Session Report — Alex G "The best FOREX MONEY MINDSET psychology video PT 2" (Transcript #10)

**Date:** 2026-07-28 · **Workstream:** Trader Intelligence
**Source:** `EVSRC|ALEX_G|20260728|007` · `https://www.youtube.com/watch?v=lcfyxUtYVSk`
**Channel:** `fxalexg` (`@fxalexg__`) — **verified before extraction**
**Status:** Applied, validated, awaiting owner review. **Nothing committed, tagged or pushed.**

> **This is ingestion #10.** The standing order's review trigger fired — **Trader Intelligence
> Review #1** was written this cycle and is appended to `RESEARCH-LOG.md`. See §11 below.

---

## 1. Ingestion status

✅ **Complete.** `INTAKE|ALEX_G|20260728|007` at `review_required`.

| | |
|---|---|
| Raw archive | `imports/alex-g/raw/alexg-psychology-money-mindset.raw.txt` + `.sha256` (byte-verified) |
| SHA-256 | `f48d3ff4…b80a432a` · 948 lines · ~15:00 |
| Normalization | `youtube_timestamp_lines` — 473 lines transformed, zero words changed, reversibility asserted per line |
| Sections | 16, cut by hand on topic boundaries |
| Graph | `BUILD\|20260728\|009` — **1,913 nodes, 4,050 edges, zero findings** |
| Integrity | Evidence **0** · graph **0** · provenance **360 checks, 0 findings** |
| Regression | 307 Python (4 known-obsolete) · 530/530 JS, 0 execution errors · **zero protected-function drift** |

## 2. The first source in the library with no technical content

No setup, entry, structure or exit rule. This is psychology and personal finance, and it is extracted
as such — the 30/30/30/10 income rule is typed `other` **specifically so it cannot be mistaken for a
trading rule**.

## 3. The finding — an exit failure mode, named precisely

> A trade set to a **1:4** target is closed at **1:2** because the unrealised dollar figure equals
> what the trader normally earns in a month. *"You are now taking and closing a trade off of impulse
> emotion to the dollar amount."*

**This is the first time any Alex G source has named a specific exit failure mode**, and it is the
most operationally relevant thing said about trade management across eight sources. It implies a
rule — *a target set in advance should be allowed to run* — that is never stated as one.

**The gap it leaves is exact and worth naming.** The source rules out cutting a target for an
**emotional** reason. It says nothing about cutting for a **market** reason — opposing structure, a
session ending, a counter-signal. Any trade-management rule MOGO ever derives needs that distinction,
and no source in the library draws it.

Supporting material, recorded as evidence rather than advice: the personal account of closing a
winner at ~$3k because friends urged him to, when the move ran to an estimated $10–15k; the
prescription not to show open positions to anyone; and the instruction to keep the employment and
trading mindsets separate.

## 4. Contradiction — `XCONTRA|20260728|009` · NUMERIC_THRESHOLD · **minor**

Third overlapping monthly-return range from this channel:

| Source | Figure |
|---|---|
| #6 | *"8 to 10% a month … anybody can do that"*; 50% is *"not going to happen"* |
| **#8** | *"I wanna make seven twelve fifteen percent a month"*, then *"seven ten percent"* |

Filed **minor** deliberately: both are unevidenced performance figures already blocked from
promotion, so the disagreement changes nothing operationally. Recorded because the library's practice
is to log numeric drift rather than average it away.

## 5. Recorded but not trading knowledge

**A materially incomplete product presentation.** A **$650–700 evaluation fee** is presented as
convertible into a **100K funded account** and thence **$5,000 from a single 1:2 trade**, naming a
specific provider — with **no pass rate, no mention that the fee is lost on breach, and no reference
to the daily-loss and drawdown rules that source #6 said constrain risk banding.** The failure branch
is simply absent.

Typed `performance_hypothesis`, blocked `critical`. Flagged as a **source-quality signal**: this
channel has now produced **eight** unevidenced monetary claims, and that density belongs in
acquisition weighting rather than being tallied claim by claim.

**A second title/content mismatch.** Published title says "PT 2"; content says *"video number one
official of the psychology series"* and *"episode three"*. After the $1000/day vs $500/day mismatch
in source #5.

**A second practice-diverges-from-rule instance.** He names 30/30/30/10, tells viewers to write it
down, then says he folds the 10% into investment — openly, so an exception rather than a
contradiction. Follows the proximity tolerance in source #7.

**`stop_rule` still 0 after eight sources.** This one discusses 1:4 and 1:2 ratios, a $650 risk
figure and a 100K account without ever placing the stop that defines that risk.

## 6. No replay candidate

Deliberately none. The failure mode is about the **trader**, not the market, and cannot be tested
against price data. Recording it as knowledge-only is the correct handling; manufacturing a candidate
would be padding the queue.

## 7. Files created or modified

**Created**
```
docs/trader-intelligence/intake/completed/alexg-psychology-money-mindset.txt
docs/trader-intelligence/intake/manifests/alexg-psychology-money-mindset.ingest.json
docs/trader-intelligence/imports/alex-g/raw/alexg-psychology-money-mindset.raw.txt (+ .sha256)
docs/trader-intelligence/imports/alex-g/normalized/…normalized.txt + …normalization-map.json
docs/development/logs/2026-07-28-session-alexg-psychology.md
evidence/: 1 source · 1 intake · 16 segments · 24 annotations · 24 items · 20 claims · 24 links
           · 9 questions · 1 contradiction · 1 blueprint · 1 profile · 9 gaps · 95 hypotheses
```

**Modified**
```
docs/trader-intelligence/CROSS-STRATEGY-ANALYSIS.md        (v7 → v8, new §3h)
docs/trader-intelligence/GLOSSARY.md                       (+2 terms, 49 → 51)
docs/trader-intelligence/RESEARCH-LOG.md                   (cycle 014 + **REVIEW #1**)
docs/trader-intelligence/TRADER-INTELLIGENCE-REVIEW.md     (review history, next due at 20)
docs/trader-intelligence/queues/validation/VALIDATION-QUEUE.md (28 → 30 entries)
docs/trader-intelligence/KNOWLEDGE-DASHBOARD.md            (regenerated)
docs/trader-intelligence/graph/build/…                     (BUILD|20260728|009)
```

**Untouched:** `index.html`, `APP_VERSION`, all 63 protected functions and 4 protected constants,
JVM, ALEX, and all trading execution logic.

## 8. Updated knowledge metrics

| Metric | Before | After | Δ |
|---|---|---|---|
| Transcripts processed | 9 | **10** | +1 |
| Claims | 244 | **264** | +20 |
| Evidence items | 306 | **330** | +24 |
| Segments | 148 | **164** | +16 |
| Open questions | 205 | **214** | +9 |
| Contradictions | 11 | **12** | +1 |
| Replay candidates | 28 | **28** | — (deliberately none) |
| Rule candidates | 0 | **0** | — |
| Graph nodes / edges | 1,723 / 3,541 | **1,913 / 4,050** | +190 / +509 |
| ALEX_G `stop_rule` | **0** | **0** | — (eight sources) |
| **Confidence changes** | — | **0 state changes** | — |

---

## 9. Trader Intelligence Review #1 — the headline

The 10-ingestion trigger fired. The full review is in `RESEARCH-LOG.md`; the summary judgement:

> **Breadth success, depth failure.** 47 → 264 claims across ten ingestions, and **zero confidence
> state changes, zero rule candidates, zero replays run.** The maximum number of independent groups
> behind any claim is still **1**; the highest score in the library is **25.62** against a
> `supported` threshold of 45.0.

**Zero claims were corroborated by a second independent source in ten ingestions.** Fifty were
corroborated by the same author and correctly discounted. 214 of 264 claims (81%) remain
single-source, for structural reasons rather than accidental ones.

**Seven recommendations were issued; four need an owner decision:**

| # | Recommendation |
|---|---|
| **R1** | **Authorize replay and acquire price data.** RC-25 first |
| **R2** | **Pause ALEX_G acquisition** — eight sources, diminishing returns, and the method is complete except the stop |
| **R3** | **Acquire a third educator** — two educators can only agree or disagree; three can produce a majority |
| **R4** | **Revisit `PROPOSAL-003`** (concept registry) — its deferral trigger has fired repeatedly |

Three further recommendations are engineering or documentation and need no decision: a regression
test for the independence-policy ordering (the cycle-008 near-miss was caught by inspection, not by a
test), fixing or deleting the section proposer (ten-for-ten failures), and recording the
visual-parameter limit as a standing constraint.

## 10. Next recommended action

**The review's recommendations supersede the per-cycle guidance.** In order: authorize replay and
price data (R1) · pause ALEX_G acquisition (R2) · acquire a third educator (R3) · revisit
`PROPOSAL-003` (R4).

The per-cycle refrain has been the same for seven consecutive cycles, and the review now supports it
with a full period of data: **the library's binding constraint stopped being knowledge around
ingestion #4 and has been authorization ever since.**

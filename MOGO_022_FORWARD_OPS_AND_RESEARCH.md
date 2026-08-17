# MOGO-022 — Autonomous Forward Operations & Research

Opened from the MOGO-021 closure checkpoint `09081e4` (v12.39.1, drift 0, clean, synced).
**PAPER only. Live money remains unauthorized.**

## Recovery (accepted, not re-audited)

| Check | Result |
|---|---|
| HEAD / branch | `09081e4` on `main`, 0 ahead / 0 behind `origin/mogo-main` |
| Protected drift | 0 — 63 functions + 4 constants byte-identical |
| Engine version | 12.39.1 (matches the verified build) |
| Runtime alive | storage written 2026-08-17 10:09 EDT |
| ALEX GBP/USD | position intact, entry 1.35565 |
| Auto Scan | verified current at 09:27:45 EDT; hourly timer next due ~10:27 |

MOGO-021 evidence stands. No re-audit performed.

## Research state recovered

12 sources ingested · 341 claims · 416 evidence items · 197 segments · 641 hypotheses ·
110 gaps · 16 contradictions · 281 open questions (261 blocking) · 325 review-queue entries.

**The bottleneck is not extraction — it is validation.**

| | Count |
|---|---|
| Hypotheses at `PROPOSED_UNVALIDATED` | **641 of 641** |
| Rule candidates | **0** |
| Proposals | **0** |
| StrategyRules promoted | **0** (human-only by design) |

TJR specifically: 2 sources, 69 claims (**all `emerging`**), 47 sourced hypotheses
(26 contested / 20 emerging / 1 insufficient), 27 with a non-template replay test, 6 gaps.

### Three corrections to the numbers and framing above — established by independent research

1. **"641 hypotheses" overstates the corpus ~4×.** They are **161 unique statements**; the rest are
   duplicates from repeated generator runs (e.g. `HYP|20260727|031`, `|20260728|008`, `|037`, `|076`,
   `|128` are byte-identical). The validation bottleneck is real but smaller than the headline.
2. **The "contested body-vs-wick TJR hypothesis" does not exist as framed — including in my own
   framing when opening this milestone.** TJR's corpus contains *zero* body-marking evidence and is
   unanimous for the wick (`EV|EVSRC|TJR|20260727|002|020`, `|016`; claims `|061`, `|062`, `|065`).
   The body-marking statement is **Alex G's** (`CLAIM|ALEX_G|20260727|020`), and the clash is the
   cross-educator contradiction `XCONTRA|20260727|003`. The hypotheses put Alex G's statement in the
   headline with TJR appended as contradictor, which reads as a TJR dispute. It is not resolvable by
   preferring an educator — only per strategy.
3. **The shipped TJR engine is not an implementation of TJR's stated strategy.** Verified directly:
   `resolveTjrSessionBoundaries` resolves ASIAN/LONDON/NEW_YORK via `tjrLondonLocalToUtcMs` — *Europe/
   London* — on FX pairs, while TJR trades **US indices** (`CLAIM|TJR|20260727|001`) on **New York**
   time (`|055`). **Its passing tests are therefore not evidence for TJR's claims.** Any inference
   from that engine to TJR's strategy is unsound. Recorded, not silently reconciled.

Zone construction itself was verified against source: the engine uses the **wick** for the outer edge
and the **body** for the inner edge (`index.html:19128`, `:19135`) — so "bodies *not* wicks" is a
false dichotomy; both are used, with a defined role for each. Fixtures 49–52 now pin that semantic
choice (the pre-existing 35–38 pinned only numbers), each mutation-verified to kill exactly the
mutation it targets.

### Is replay testing scientifically valid for TJR today? — Partially, and the distinction matters

- **Zone construction IS testable.** `buildTjrSessionZones` / `buildTjrHighZone` / `buildTjrLowZone` /
  `resolveTjrSessionBoundaries` are implemented and covered by `v123_tjr_phase1_session_zone_tests.js`.
- **Strategy-level replay is NOT yet valid.** The dashboard records TJR as
  `session_zone_engine_only`: there is no mechanized TJR entry rule to replay. Running a
  "TJR backtest" today would be testing an engine that does not implement the strategy.

Recording that plainly, because the honest answer bounds what MOGO-022 can legitimately conclude.

## MOGO-022 objectives (in priority order)

1. **Protect forward PAPER operation** — read-only inspection only; never disturb production state.
2. **Verify forward evidence capture** — distinguish *no valid setup* from *failed to observe*.
3. **Advance TJR research** — convert mechanically-specifiable claims into the first rule candidates;
   validate what IS mechanized against source evidence.
4. **Human-assisted research ingestion** — smallest auditable advance on the existing pipeline.
5. **Decision-difference analysis** — exercised on a real recorded disagreement.

## First results

**Rule candidates: 0 → 5** (`RCPROP|20260817|001-005`), derived through the existing
`propose_rule_candidate()` so evidence IDs, certainty distributions and contradiction status come
from recorded state rather than hand-assertion. All `proposed` / `not_reviewed`; nothing promoted.
A sixth was deliberately **excluded**: "trades taken *around* the NY open" has no window, so it is
not falsifiable and therefore not a rule candidate.

**Five new blocking gaps** (`GAP|20260817|001-005`) surfaced only by attempting mechanical
specification — the six pre-existing TJR gaps were generic template categories auto-generated
identically for ALEX_G. Critical: stop-buffer distance (undefined → position size → every
performance figure), draw-on-liquidity lookback (unbounded candidate set), and "reaction" undefined
(with real **circularity risk** — defining it would invent the strategy's core rather than extract it).

**A TJR strategy freeze is not reasonably proposable.** Entry trigger, stop distance and risk % are
all unspecified, and two of the three have zero supporting evidence.

**Decision-difference capability now exists** (`scripts/trader_intelligence/decision_difference.py`,
34 tests, mutation-verified) as a thin read-only classifier over the *existing* contradiction records
— no new schema, no parallel system. Classifying all 16 contradictions gives **15 ×
`INTERPRETATION_HYPOTHESIS`, 1 × `TIMING_DIFFERENCE`, zero `RULE_DIFFERENCE`**. That is a finding,
not a tool defect: **claims in this corpus carry essentially no stated scope**, so almost no recorded
disagreement can be attributed to anything the traders actually said.

### The literal human-vs-MOGO question is not yet computable — and this is mechanical, not opinion

Of 416 evidence items, **zero** are of type `replay_result` or `paper_trade_result`, and no
`traders/*/decisions` store exists. Until a MOGO decision has an `EvidenceSource`, only
human-vs-human disagreements can be classified. The classifier's position model is actor-agnostic,
so a MOGO-side position drops in unchanged once that source exists. **That is now the highest-value
next capability**, alongside the artifact-intake gap below.

### Structural blocker worth an owner decision (governance-adjacent, not urgent)

The claims that actually specify mechanics are typed `definition` (`|015` BOS, `|017` 79% extension,
`|057` NYSE open), which is **not** in `RULE_CANDIDATE_ELIGIBLE_CLAIM_TYPES`. The eligible
confirmation claims (`|013`, `|014`) merely *name* confluences while the mechanics live in ineligible
claims. This is a structural reason the corpus produced 0 proposals for so long.

## Governance carried forward, unchanged

G-1 protected-list scope · G-2 auto-trade eligibility age bound · G-3 paginator contradiction ·
G-4 `exitDetectedAt` fabrication. Deferred P2/P3 backlog carried forward. TJR remains RESEARCH ONLY.

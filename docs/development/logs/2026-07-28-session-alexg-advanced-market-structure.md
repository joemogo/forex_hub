# Session Report — Alex G "Advanced Market Structure" (Transcript #4)

**Date:** 2026-07-28 · **Workstream:** Trader Intelligence
**Source:** `EVSRC|ALEX_G|20260728|001` · `https://www.youtube.com/watch?v=sZAE_lqdeno`
**Status:** Applied, validated, awaiting owner review. **Nothing committed, tagged or pushed.**

---

## 1. Ingestion status

✅ **Complete.** `INTAKE|ALEX_G|20260728|001` at `review_required`.

| | |
|---|---|
| Raw archive | `imports/alex-g/raw/alexg-advanced-market-structure.raw.txt` + `.sha256` (byte-verified) |
| SHA-256 / size | `f48d9c1c…08a6db` · 22,106 bytes · 1,006 lines · ~20:43 |
| Normalization | `youtube_timestamp_lines` — 502 markers removed, 2,275 chars, **zero words changed**, reversibility asserted per line |
| Sections | 17, cut by hand on timestamp/topic boundaries (see §10, H22) |
| Graph | `BUILD\|20260728\|002` — **650 nodes, 1,214 edges, zero findings** |
| Integrity | Evidence 0 findings · provenance 156 checks, 0 findings |
| Regression | 307 Python (4 known-obsolete failures) · 530/530 JS · **zero protected-function drift** |

## 2. Source title — **PROVISIONAL, unverified**

**`Advanced Market Structure`**

The transcript names itself *"the advanced Market structure video"* at 0:01 and again at 1:12 — the
strongest possible in-transcript basis. But that is not the published YouTube title string, and this
environment has no network access. Marked `unverified_working_title` in every record and flagged in
the rule register header.

## 3. New knowledge added — 14 new claims

Market structure is instrument- and timeframe-agnostic · the active higher low is the **last** one,
not the lowest · trend is *defined by* structure · visual slope is a trap · structure exists inside
consolidation · **any body close counts as a shift regardless of size** · new LL forces LH
reassignment · price may move freely between active levels · the **snake trick** · the line chart as
a body-structure aid · don't chase an extreme, prefer a retracement · timeframes inform stop/target
sizing · **market structure is only 50% of the system** · 60–75% accuracy (unsupported).

## 4. Existing knowledge reinforced

Bullish = HH+HL · body close (not wick) shifts structure · wicks are not structure · new HH forces
HL reassignment. All four reinforced **within Alex G only**.

## 5. Same-educator restatements — 4

`CLAIM|ALEX_G|…|012`, `|020`, `|022`, `|016`. Under `DECISION|MOGO|20260727|006` these share
independence group `AUTHOR|ALEX_G`. Evidence counts rose to 2–3 sources; scores moved 22.0 →
23.5–25.0 (the 25% same-group discount); **every claim stayed `emerging`.** Without the policy all
four would have reached `supported`.

## 6. Independent cross-source confirmations — **0**

TJR states the bullish/bearish structure definitions in almost identical words
(`CLAIM|TJR|…|067`, `|068`). This is **not** counted: `compute_claim_fingerprint()` includes
`traderId`, so trader-scoped claims never merge. Recorded in the cross-strategy analysis instead.

## 7. Contradictions discovered — 0 new, 1 reinforced

No new contradictions. `XCONTRA|20260727|003` (bodies vs wicks, ALEX_G vs TJR, material,
cross-educator) is **reinforced on the Alex G side** by two further restatements.

Two tensions recorded but **deliberately not** filed as contradictions: *"market structure is
absolutely everything"* (0:57) vs *"only 50% of the problem"* (20:21) — rhetorical framing vs an
operative scoping statement; and this source's "timeframe doesn't matter" vs source #1's timeframe
hierarchy — reconcilable (reading procedure vs directional precedence), filed as an open question.

## 8. Replay candidates created — 8 (RC-12 … RC-19)

| ID | Test | Needs |
|---|---|---|
| **RC-12** | Body-close structure-shift detection | price data (gated by RC-16) |
| **RC-13** | **Wick-break vs body-close** — resolves the cross-educator contradiction | **price data only** |
| RC-14 | Structure label vs visual slope | price data |
| RC-15 | Structure classification inside ranges | price data |
| **RC-16** | **Pivot-selection sensitivity (snake trick)** — gates RC-12/RC-13 | price data |
| RC-17 | Minimum break distance / ATR threshold | price data |
| RC-18 | Retracement entry vs chasing | + risk model (absent) |
| RC-19 | HH/HL and LL/LH reassignment invariant | price data |

Six of eight need **nothing but price data** — no risk model, no TP ladder, no instrument
abstraction. Largest increase in cheap, decisive tests any cycle has produced.

## 9. Unsupported claims

**60–75% trade accuracy** (18:58). No sample size, date range, instrument, timeframe, trade log, or
definition of what "accuracy" measures. Stated once, in passing, immediately before the promotional
close. Typed `performance_hypothesis` — **structurally ineligible** to become a rule candidate —
and blocked `critical` in the validation queue. **Must never be treated as evidence-backed.**

**Circular definition:** *"trend is identified by the market structure"* + *"market structure is
these highs and lows"*. Coherent as a definition, but unfalsifiable — it asserts nothing about future
price. Only the paired empirical claim (slope-reading is a trap) is testable, via RC-14.

**Overstatements:** *"absolutely everything in the market"*; *"it is very easy and very
straightforward"* applied to the one genuinely under-specified step.

## 10. Missing definitions and unresolved assumptions

| Gap | Consequence |
|---|---|
| **Snake trick pivot strength** | ⚠️ **Verdict: NOT formalizable as stated.** No pivot strength, minimum swing, lookback or tie-break. A teachable heuristic, not a specification. Gates RC-12/RC-13 → RC-16 sweeps `k` |
| **False breaks / noise** | Never addressed. "Any size counts" explicitly rules out a threshold, so the method is fully mechanical **and** maximally noise-sensitive |
| **Retracement depth** | E1 gives no depth, measurement or invalidation → RC-18 sweeps X |
| **"Trading at the right times"** | Named as one of four requirements for profitability; **defined nowhere in either Alex G source** |
| **Stop / target / risk** | ❌ **Two Alex G sources, still zero `stop_rule`, `target_rule`, `risk_rule` claims.** Confirmed structural gap in his published material, not an omission from one video |
| **Lower bound on range size** | "Structure exists in any range, however tight" + "any size counts" ⇒ identifiable at arbitrarily small scale with no floor |

## 11. Files created or modified

**Created**
```
docs/trader-intelligence/intake/pending → completed/alexg-advanced-market-structure.txt
docs/trader-intelligence/intake/manifests/alexg-advanced-market-structure.ingest.json
docs/trader-intelligence/imports/alex-g/raw/alexg-advanced-market-structure.raw.txt (+ .sha256)
docs/trader-intelligence/imports/alex-g/normalized/alexg-advanced-market-structure.normalized.txt
docs/trader-intelligence/imports/alex-g/normalized/…normalization-map.json
docs/trader-intelligence/graph/decisions/decision-mogo-20260727-006.json
docs/trader-intelligence/rule-registers/README.md
docs/trader-intelligence/rule-registers/ALEX_G-advanced-market-structure.md
docs/trader-intelligence/queues/validation/VALIDATION-QUEUE.md
docs/development/logs/2026-07-28-session-alexg-advanced-market-structure.md
evidence/: 1 source · 1 intake · 17 segments · 21 annotations · 21 items · 14 claims · 21 links
           · 8 questions · 1 blueprint · 1 profile · 13 gaps · 29 hypotheses
```

**Modified**
```
scripts/trader_intelligence/ingest.py          (independence policy + ordering fix)
docs/trader-intelligence/RESEARCH-LOG.md       (cycle 008)
docs/trader-intelligence/proposals/REPLAY-CANDIDATES.md      (RC-12 … RC-19)
docs/trader-intelligence/proposals/BACKLOG-003-pipeline-hardening.md (H22, H23)
docs/trader-intelligence/KNOWLEDGE-DASHBOARD.md              (regenerated)
docs/trader-intelligence/graph/build/{nodes,edges,manifest}.json + both integrity reports
evidence/links/ — all 144 re-grouped by educator; all 118 claims recomputed
```

**Untouched:** `index.html`, `APP_VERSION` 12.6.0, all 63 protected functions, all trading logic.

## 12. Updated knowledge metrics

| Metric | Before | After | Δ |
|---|---|---|---|
| Transcripts processed | 3 | **4** | +1 |
| Educators | 2 | 2 | — |
| Concepts extracted (claims) | 104 | **118** | +14 |
| Objective rules (mechanically checkable) | — | **15 of 18** in this source | — |
| Discretionary rules | — | **3** (snake trick, retracement, timeframe→SL/TP) | — |
| Rules reinforced | — | **4** (same-educator only) | +4 |
| **Independent confirmations** | 0 | **0** | — |
| Same-source confirmations | 0 | **4** | +4 |
| Contradictions | 3 | **3** | 0 new, 1 reinforced |
| Replay candidates | 11 | **19** | +8 |
| Rule candidates | 0 | **0** | — |
| **Confidence changes** | — | **0 state changes.** 4 claims moved 22.0 → 23.5–25.0 within `emerging` | — |
| Claims at `supported` or above | 0 | **0** | — |

---

## The two findings that matter most

**1. The guardrail worked, and was nearly defeated by execution order.**
`DECISION|MOGO|20260727|006` correctly stopped four verbatim restatements from promoting. Then
`run_post_annotation_pipeline` — which auto-proposes rule candidates for claims at `supported` — ran
*before* the policy, saw pre-policy confidence, and **created two rule candidates off same-educator
repetition alone.** Exactly what the decision exists to prevent. Fixed by reordering; both proposals
removed; library back to 0 rule candidates. **A correct rule applied at the wrong moment is not a
guarantee.**

**2. Both non-replay routes to `supported` are now closed by design.**
Same-educator repetition doesn't corroborate (DECISION 006); cross-educator agreement doesn't merge
(trader-scoped fingerprints). **Replay is the only remaining route.** That is defensible — a trader
repeating himself and a second trader agreeing are both weaker than a test — but it means DECISION
003's "independent corroboration" route is currently unreachable in practice. Surfaced in the
validation queue for owner review; the proposed fix is Concept-level consensus counting, not
relaxing either mechanism.

## Next recommended action

**Authorize replay and source price data.** Four sources in, zero confidence movement, and the only
remaining route now requires both. `RC-13` is the best first test: it settles the library's only
cross-educator contradiction and needs one instrument's OHLC and nothing else.

Neither is an engineering task — `replayAuthorization` is `false` on all six OwnerDecisions, and MOGO
holds no market data for any instrument.

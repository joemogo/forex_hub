# MOGO Implementation Candidates — from `EVSRC|TJR|20260727|001`

**Generated:** 2026-07-27 · **Status:** Recommendations only. **Nothing here is authorized or
implemented.**

> **Constitution check.** *Evidence Before Features. Knowledge Before Automation. Validation Before
> Implementation.* Every candidate below derives from claims at **`emerging` confidence from a
> single source**. Under POLICY-001 none may be built into trading behaviour until corroborated.
> **Every entry therefore carries an evidence gate**, and most gates are currently unmet — which is
> the correct state, not a failure.

**Reading the gate column:** 🔴 blocked on evidence · 🟡 blocked on architecture · 🟢 buildable now
(because it depends on *knowledge about* the strategy, not on the strategy being true).

---

## 1. Strategy Engine 🔴

**Candidate:** a TJR sequential-gate strategy — sweep → 5m confirmation → (2B) → continuation → 1m
confirmation → entry.
**Evidence gate:** all 47 claims at `emerging`; `entryLogic.requiredConditions` is **empty**; no
risk rule exists; 2 open contradictions.
**Recommendation:** **Do not build.** The blueprint is structurally non-executable
(`productionStatus: not_applicable`) and it is honest about why. Revisit only after ≥2 independent
sources and RC-01/RC-06 results.
**Note:** the Session/Zone Engine (v12.3.0) already implements TJR's *level construction*. That was
built from repository-confirmed reasoning, not from this transcript, and this transcript
**corroborates** it (`|010`, `|009`, `|011`) — the first external evidence that an already-shipped
MOGO component matches what the trader describes. That is a real, if modest, win.

## 2. Knowledge Graph 🟢

**Candidates:** `INSTRUMENT` node type (`PROPOSAL-001`); `CONCEPT` node type (`PROPOSAL-003`);
`RAISES_QUESTION` edges from absence-questions (blocked by defect D4).
**Evidence gate:** none — graph structure is metadata, not trading behaviour.
**Recommendation:** **Highest-value 🟢 group.** These make existing knowledge queryable rather than
adding new claims. `CROSS-STRATEGY-ANALYSIS.md` §5 demonstrates the concrete need: MOGO cannot
mechanically answer *"which strategies act on prior significant levels?"* because the answer is
spelled three different ways.

## 3. Confluence Engine 🔴

**Candidate:** extend JVM's `WEIGHTS` with TJR-derived confluences (liquidity sweep, SMT, FVG,
79% extension), or add a gate-chain scoring mode alongside the additive one.
**Evidence gate:** severe. `WEIGHTS` is a **protected constant** — any change is protected-constant
drift and alters live JVM paper-trading behaviour.
**Recommendation:** **Do not modify `WEIGHTS`.** But there is a genuinely valuable, near-free
adjacent experiment: **RC-02 re-scores JVM historically with `wick`+`engulf` zeroed**, testing
TJR's simplification claim on data MOGO already has, in a replay harness, touching no constant.
That is the single best evidence-per-unit-risk item on this page.

## 4. Risk Engine 🔴🟡

**Candidate:** instrument-aware position sizing (`PROPOSAL-001`).
**Evidence gate:** TJR provides **no** risk rule — the critical gap. Architecturally, `pipSize`/
`pipValuePerLot` are protected and pip-native; index futures are point/tick-denominated.
**Recommendation:** implement `PROPOSAL-001` phases A–B (additive dispatch, FX path delegating to
the existing frozen functions) **only after** the FX-vs-multi-asset decision. **No TJR risk logic
can be built at all** until a source supplies a risk rule.

## 5. Trade Scoring 🔴

**Candidate:** score a candidate trade by how many TJR gates it satisfies.
**Evidence gate:** the gate set itself is contested (`XCONTRA|…|001` — is Step 3 mandatory?). A
score built on a contested gate set encodes an unresolved disagreement as a number.
**Recommendation:** defer until RC-06 and `BACKLOG-002/T3`.

## 6. Replay Engine 🟡

**Candidate:** support the nine specifications in `REPLAY-CANDIDATES.md`.
**Evidence gate:** none — replay *produces* evidence.
**Recommendation:** **Highest strategic value on this page**, and the intended route out of the
`emerging` ceiling (POLICY-001 route B). Blocked on: replay authorization, ES/NQ market data (MOGO
has none — `dataAvailability: none`), and `PROPOSAL-001` for RC-05/RC-09.
**Sequencing note:** RC-01 through RC-04 and RC-07/RC-08 are `TRIGGER-ONLY` and need **no** risk
model — they are runnable as soon as data and authorization exist. Do not let RC-09's blockers
delay them.

## 7. Education Engine 🟢

**Candidate:** Academy content on liquidity sweeps, session levels, structure breaks, and confluence
reduction, sourced from the glossary.
**Evidence gate:** **low — this is the key insight for this engine.** Teaching *"TJR states X, at
`emerging` confidence, unvalidated"* is honest and useful. Teaching *"X works"* is not.
**Recommendation:** **Best 🟢 candidate for user-visible value.** Existing Academy infrastructure
(`ACADEMY_LESSON_LIBRARY`, 55 modules) already supports rich content. Content must carry confidence
and provenance inline. **The most valuable lesson available is not a TJR rule at all — it is
"deliberate confluence reduction"** (`|038`): a trader removing inputs and reporting improved
results, which is a transferable methodological idea rather than a market claim.

## 8. Coaching Engine 🔴

**Candidate:** coach a user against TJR's checklist.
**Evidence gate:** coaching implies the rules are correct. They are `emerging`.
**Recommendation:** **Do not build.** The strongest reason is in the evidence itself: `|031`,
`|032`, `|033` show TJR **deviating from his own stated rules on camera**. Coaching the literal
rules would coach something their author does not do.

## 9. Trade Review 🟡

**Candidate:** annotate closed trades with which TJR gates were present.
**Evidence gate:** moderate — describing what was present is weaker than asserting it should have
been.
**Recommendation:** viable **after** the Instrument abstraction, and only as descriptive annotation
(*"a liquidity sweep preceded this entry"*), never evaluative (*"you should have waited"*).

## 10. Journal Intelligence 🟡

**Candidate:** tag journal entries with glossary concepts.
**Evidence gate:** low — tagging is descriptive.
**Recommendation:** defer to `PROPOSAL-003`; without a Concept Registry this becomes free-text
tagging that will need re-doing.

## 11. Explainability Engine 🟢

**Candidate:** surface `evidence_explain.explain_claim_by_id()` output — why a claim holds the
confidence it does, which evidence supports it, which questions block it.
**Evidence gate:** none — it explains evidence rather than asserting it.
**Recommendation:** **Strong 🟢 candidate, and the cheapest.** The service layer already exists and
is tested; what is missing is any surface. This overlaps `BACKLOG-003/H9` (review surface) — a
single standalone research surface could serve both, and would address the largest manual-effort
sink after extraction itself. **Must not be built into `index.html`** (a trading application, not a
research surface).

## 12. Alert Engine 🔴

**Candidate:** alert on TJR setup formation.
**Evidence gate:** an alert is an implicit trade recommendation.
**Recommendation:** **Do not build.** Highest-risk candidate on this page: it puts unvalidated,
single-source, internally-contradictory logic in front of a user at the moment of decision.

---

## Update — ALEX_G source #1 (2026-07-27)

**The first ingested method that is FX-native.** TJR's material is US indices, which MOGO's
pip-denominated risk model cannot express without `PROPOSAL-001`. Alex G's is forex (per the video
title), and the method — timeframe bias, zones, rejection-candle entry — needs no new instrument
machinery. **It is the first ingested strategy expressible in MOGO's current engine.**

That does *not* make it buildable. It remains 🔴: 35 claims, all `emerging`, single source, and
**the source states no stop rule, no target rule and no risk rule whatsoever** — a strictly larger
gap than TJR's, which at least specifies stop placement and targets.

| Engine | Effect of this source |
|---|---|
| **Strategy Engine** 🔴 | Method is coherent and FX-native but has no exit or risk half. Not buildable. |
| **Confluence Engine** 🔴 | ALEX_G's entry trigger (dojis, engulfing) **corroborates JVM's `wick`+`engulf`** while TJR removed those confluences. `RC-02` becomes a three-way question rather than a TJR-only one. |
| **Replay Engine** 🟡 | Two new candidates: `RC-10` (bodies vs wicks — cheapest real experiment in the library) and `RC-11` (HTF alignment). RC-10 needs no risk model. |
| **Knowledge Graph** 🟢 | First cross-educator `CONTRADICTION_RECORD`. Strengthens the case for `CONCEPT` nodes — five names now exist for "prior significant level". |
| **Education Engine** 🟢 | Trend definitions are now asserted independently by two educators. Still `emerging` each, but "two independent educators state this" is honest, useful lesson framing. |
| **Trade Review / Journal** 🟡 | Body-vs-wick marking is a single toggle with a measurable effect — a natural first annotation. |

**New governance item.** MOGO ships an ALEX_G engine doing Break & Retest / Repeated Zone Reaction.
The ingested Alex G material teaches top-down bias + AOI + rejection entry. **Whether these are the
same method is now an open question with evidence on one side and code on the other** — see
`CROSS-STRATEGY-ANALYSIS.md` §8 D1. Until it is settled, no Alex G-derived change should touch the
shipped engine.

---

## Priority summary

| Rank | Candidate | Engine | Gate | Why |
|---|---|---|---|---|
| 1 | JVM re-score with `wick`+`engulf` zeroed (RC-02) | Confluence/Replay | 🟢 data exists | Tests a cross-strategy claim on data MOGO already has, touching no constant |
| 2 | Explainability surface | Explainability | 🟢 | Service layer built and tested; only a surface is missing |
| 3 | `CONCEPT` + `INSTRUMENT` node types | Knowledge Graph | 🟢/🟡 | Makes existing knowledge queryable |
| 4 | Academy content with inline confidence | Education | 🟢 | Real user value from `emerging` knowledge, honestly framed |
| 5 | RC-01 (Step 2B) | Replay | 🟡 needs data | Highest-value single validation available |
| — | Everything else | — | 🔴 | Blocked on evidence, correctly |

**The pattern worth noticing:** every 🟢 candidate is about *understanding, explaining, or
organising* knowledge. Every 🔴 is about *acting* on it. That split is exactly what the Constitution
predicts, and it is the clearest available signal that the evidence-first sequencing is working
rather than merely being asserted.

---

## Explicitly not recommended

- Any change to `WEIGHTS`, `RULES`, `ALERT_THRESHOLD`, `RULES_ALEXG`, `pipSize`, `pipValuePerLot`,
  or any protected function.
- Any TJR-derived signal reaching live or paper execution.
- Any UI in `index.html` for research review.
- Any automated promotion of a claim to a `StrategyRule`.
- Any ICT/SMC-derived feature — **MOGO holds no ICT/SMC evidence**
  (`CROSS-STRATEGY-ANALYSIS.md` §1).

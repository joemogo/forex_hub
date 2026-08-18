# MOGO-022 — What is still required before TJR could be a defensible mechanical strategy candidate

**Status: derived, read-only. Adjudicates nothing, promotes nothing, authorises no trade.**
**Generated from the corpus by `research_understanding.eligibility()` and
`hypothesis_testability.what_is_still_required()`. Every number below is reproducible.**

---

## 0. The short answer

TJR is **BLOCKED**, on **16 blockers**, and the gap is not one of analysis effort.
It is that **the acquired corpus does not contain the information a mechanical
strategy requires**, and **no TJR trade evidence exists at all**.

**Correction, 2026-08-18.** This document previously said "the source material does
not contain the information". That was wrong in a specific and important way, and
an acquisition pass established it: it is the **acquired corpus** that lacks the
information. Free, public, primary sources that plausibly state it DO exist — the
candidate set now includes videos titled *Boot Camp Day 38: Stop Losses*, *Day 39:
Calculating Lot Size*, *Day 13: Risk Management* and *TJR's Strategy Explained*,
all registered with publisher-verified metadata (`CAND|MOGO|20260818|001`–`036`).

The distinction matters because it changes what would unblock TJR. It is not an
analysis problem and it is not an "the information was never published" problem —
it is a **content-retrieval** problem.

**Held to the same standard in the other direction:** a video *titled* "Stop
Losses" is NOT evidence that it states a mechanical stop rule. Whether these
sources state entry trigger, stop placement and risk per trade is **UNKNOWN** until
the content is actually retrieved and read. The candidates carry no authority and
close nothing; they are leads, and they are marked as such.

**What blocks retrieval, precisely:** the caption endpoint returns HTTP 200 with 0
bytes, re-confirmed 2026-08-18T15:12Z. Every priority TJR video carries an `en/asr`
track only — **no publisher-authored captions anywhere in the set** — so even a
route that worked would yield machine-generated text of unverified fidelity to the
audio. That ceiling is itself a finding: it bounds the best evidence quality
obtainable from this source without the operator supplying content another way.

Nothing in this document is a judgement about TJR's trading. It is a statement
about what the corpus can and cannot currently support.

---

## 1. Required-category status

Twelve categories are required for a mechanical reading. Three are supported.

| Category | Status |
|---|---|
| failure_condition | **SUPPORTED** |
| invalidation_rule | **SUPPORTED** |
| trade_management_rule | **SUPPORTED** |
| confirmation_rule | AMBIGUOUS |
| entry_rule | AMBIGUOUS |
| exception | AMBIGUOUS |
| session_rule | AMBIGUOUS |
| stop_rule | AMBIGUOUS |
| target_rule | AMBIGUOUS |
| setup_requirement | **CONFLICTED** |
| risk_rule | **MISSING** |
| timeframe_rule | **MISSING** |

The four hard blockers, with what each needs:

- **setup_requirement — CONFLICTED.** Needs an explicit walk-through of what
  constitutes a valid setup.
- **entry_rule — AMBIGUOUS.** Needs an explicit statement of the condition that
  triggers entry, and the timeframe it executes on.
- **stop_rule — AMBIGUOUS.** Needs an explicit statement of where the stop is placed.
- **risk_rule — MISSING.** Needs an explicit statement of risk per trade.

**A strategy cannot be mechanised while entry, stop and risk are unstated.** Those
three are not refinements; they are the minimum a position requires.

---

## 2. The eleven blocking questions

These are not open-ended research prompts. Each names a specific thing the source
does not say:

| Question | What is missing |
|---|---|
| EQ‑002 | Stop placement is only ever given chart-relatively ("underneath this low"). Which exact swing? |
| EQ‑003 | Worked examples use TP1–TP4, but how those four levels are chosen is never defined. |
| EQ‑004 | Filename says "forex session strategy"; the transcript trades US indexes. Which instruments does this apply to? |
| EQ‑007 | News is checked before the setup, but what happens when high-impact news IS present is never stated. |
| EQ‑008 | "One extra point down to hit our special little number" — the number is never defined. |
| EQ‑009 | Step ordering "can be variable" when 2B activates. The exact ordering is never given. |
| EQ‑012 | A rule claim has no timeframe recorded. |
| EQ‑013 | An entry rule has no companion invalidation rule in the same scope. |
| EQ‑016 | Consolidation is named as one of three market states but never defined. |
| EQ‑017 | The two-candle high/low rule has no minimum-size or significance filter. |
| EQ‑018 | Trends "break", but a break of trend is never defined. |

Plus one **blocking contradiction** (`XCONTRA|20260728|001`): two claims cannot both
hold without qualification, so no single mechanical reading exists. That one needs
an owner decision or scope-qualifying evidence — it is not resolvable by more study
of the same source.

---

## 3. The hypothesis backlog does not close this gap

The corpus holds **641 hypotheses**, every one with `proposedReplayTest`,
`proposedPaperTest`, `independentVariables` and `dependentVariables` populated, and
every one still `PROPOSED_UNVALIDATED`. As a table that reads like 641 experiments
awaiting execution.

Measured, it is not:

- **Only 4 of 641 test specifications are unique to a single hypothesis.** The rest
  are shared verbatim. A specification shared by 552 hypotheses does not describe an
  experiment for any one of them.
- **`dependentVariables` is the constant `["setup validity"]` on all 641** — including
  risk-rule and target-rule hypotheses, where it is not a meaningful dependent
  variable. The field carries zero information.
- **`proposedReplayTest` has 5 distinct values across 641**, selected by confidence
  tier rather than by hypothesis content.

Blockers, counted across all 641 (a hypothesis may carry more than one):

| Blocker | Count |
|---|---|
| NOT_TESTABLE_NO_EVIDENCE_POPULATION | 641 |
| NOT_TESTABLE_NON_DISCRIMINATING_TEST | 637 |
| NOT_TESTABLE_UNRESOLVED_CONTRADICTION | 59 |

**Currently testable: 0.**

### Why "no evidence population" applies to all 641

The corpus now holds 248 TradeObservations, but they are all **MOGO's own decisions**:

| Held for | Population | Count |
|---|---|---|
| `alex_g_sr_v1` | HISTORICAL (replay) | 221 |
| `alex_g_sr_v1` | FORWARD (paper closes) | 26 |
| `current_strategy` | FORWARD (paper close) | 1 |

Forward closes were recovered from browser storage and preserved, taking the
FORWARD population from 1 to 27. This does not change the conclusion below — those
are still MOGO's decisions, not TJR's — but forward analysis of MOGO's own
behaviour is now possible where it was not.

**Coverage caveat, which any forward figure must carry:** the preserved ALEX
closes are a SUBSET of that account's closed positions (39 as of the most recent
observation). The oldest closes minted no evidence package (backlog B-22 — the
evidence database was recreated from scratch on 2026-08-17), so the preserved set
begins partway through the account's history. **Forward-performance statistics
computed on this set are the performance of the preserved subset, not of the
account.**

Balances do NOT chain trade-by-trade across this set, and an equity curve built by
chaining them is wrong. The account runs up to five concurrent positions, with
`accountBalanceBefore` stamped at entry and `accountBalanceAfter` at exit, so a
trade's residual equals the summed P&L of the other trades that closed inside its
lifetime. That relation holds for all 23 records whose lifetime falls entirely
within the preserved window; the three exceptions all opened before the earliest
preserved close, which is the B-22 gap showing through rather than a discrepancy.
The most recent close (`TOBS|MOGO|20260817|026`, a clean 1R loss) reconciles
exactly with the independently-observed live balance of 9658.67, which is what
confirms the preserved set is real and current rather than stale.

Hypotheses blocked purely on missing evidence for their actor: **ALEX_G 587, TJR 47,
RAYNER_TEO 33.**

This is the distinction that matters and it is deliberately not blurred:
`alex_g_sr_v1` is *MOGO's implementation of a published method*. `ALEX_G` is a person.
Replaying the former measures whether **the implementation** exhibits a property. It
does not test whether **the trader's stated rule** holds. Counting one as evidence for
the other would be the single easiest way to manufacture a false result here.

---

## 4. What would actually unblock TJR

In order of how much each would move the position:

1. **RETRIEVAL of the candidate sources that plausibly state entry trigger, stop
   placement and risk per trade.** The leads exist and are free and public
   (`CAND|MOGO|20260818|001`–`036`); what does not exist is a route to their
   content. This is a retrieval problem, not an analysis problem and not an
   absence-of-publication problem. Whether they actually state the three rules is
   UNKNOWN until read.
2. **An owner decision on `XCONTRA|20260728|001`**, or evidence qualifying the scope of
   the two conflicting claims.
3. **TJR trade evidence** — actual observed trades, as `TradeObservation` records with
   `actor: HUMAN`. Today there are none, which is why no TJR hypothesis is testable at
   any quality. Operator screenshots are a sanctioned route (`sourceType: screenshot`),
   and the ingestion path exists and is tested.
4. **Hypothesis specifications that discriminate.** Worth doing *after* 1–3, not before:
   writing more specific test prose while no evidence exists would improve the
   appearance of the backlog and change nothing about what can be concluded.

### What deliberately was NOT done

No hypothesis was rewritten, and no test specification was regenerated. Producing
641 more specific-sounding test descriptions would have manufactured the appearance
of testability without adding a single observation — which is precisely the failure
this analysis exists to detect.

---

## 5. Reproducing this

```
python3 scripts/trader_intelligence/hypothesis_testability.py
python3 -c "import sys; sys.path.insert(0,'scripts/trader_intelligence'); \
  import research_understanding as ru; from query_evidence import EvidenceIndex; \
  print(ru.eligibility(ru.corpus_view(EvidenceIndex.load(ru.EVIDENCE_ROOT),'TJR')))"
```

Both are read-only and mutate nothing. `tests/trader_intelligence/test_hypothesis_testability.py`
covers the triage, mutation-verified 8/8.

# ALEX — Rule-to-Evidence Join & Hypothesis Testability

**Generator:** `scripts/strategy_fidelity/build_alex_rule_evidence_join.py`
**Artifact:** `docs/strategy-fidelity/audit/alex-rule-evidence-join.json` (`mogo.alex-rule-evidence-join.v1`)
**Tests:** `tests/strategy_fidelity/test_rule_evidence_join.py` · **Read-only over Evidence Packages**

---

## 1. What the join connects

```
educator rule (AXR-*)  ──[fidelity matrix: codeLocation + fidelityStatus]──▶  MOGO implementation
                       ──[FUNCTION_EVIDENCE_MAP: declared field paths]─────▶  RUN-001 packages
```

Every record keeps the three bodies of knowledge in **separate fields** — `educator{}`,
`implementation{}`, `evidence{}` — and carries `linkBasis[]`: the matrix row, the resolved code
location, the declared field paths and the observed package count. **A rule whose implementation
cannot be anchored to a package field is `UNRESOLVED`, never guessed.**

## 2. Join results — all 41 rules

| Status | Count |
|---|---|
| LINKED | **12** |
| NOT_EXERCISED | 4 (live-execution path; a replay cannot reach them) |
| NOT_IMPLEMENTED | 12 |
| UNSUPPORTED | 7 (MOGO-authored, no educator support) |
| UNRESOLVED | 6 (4 `NO_EVIDENCE_FIELD_EXISTS`, 2 `FIDELITY_STATUS_UNRESOLVED`) |

## 3. Measurable evidence, not placeholder text

Every rule now carries `measurableEvidence` computed from the packages themselves:

| Setup | Trades | W | L | Win rate | Net R | Expectancy | Mean MAE | Mean MFE |
|---|---|---|---|---|---|---|---|---|
| `A_repeatedReaction` | 16 | 5 | 11 | 31.25% | −1.00R | −0.0625R | 40.41p | 31.45p |
| `B_breakRetest` | 8 | 1 | 7 | 12.50% | −5.00R | −0.6250R | 44.86p | 29.55p |

## 4. Metric registry

A metric is defined **once** and referenced by id, so two hypotheses can never disagree about what a
measure means: `MET_WIN_RATE`, `MET_NET_R`, `MET_EXPECTANCY_R`, `MET_PROFIT_FACTOR`, `MET_MAE_PIPS`,
`MET_MFE_PIPS`. Each names the Evidence Package fields it is computed from and whether higher or
lower is better.

## 5. Hypothesis testability

The corpus's 641 hypotheses all carried the same placeholder — *"Replay historical price action with
and without this condition and compare outcomes."* No metric, no threshold, no sample size, no
falsification condition. Each ALEX rule now instead carries a hypothesis with all five:

- **metric** — `MET_EXPECTANCY_R` primary, four secondaries
- **comparison** — condition held vs did not, same strategy, engine version and dataset hash
- **threshold** — a 0.25R expectancy difference, `declaredInAdvance: true`
- **minimum sample** — **30 resolved trades per arm**, with its basis stated
- **falsification condition** — explicit: what result would REFUTE the hypothesis

| Hypothesis status | Count |
|---|---|
| NOT_APPLICABLE | 19 |
| **INSUFFICIENT_SAMPLE** | **12** |
| UNTESTED | 6 |
| NOT_TESTABLE_BY_REPLAY | 4 |
| **TESTABLE_NOW** | **0** |

**Zero hypotheses are testable today.** That is the finding, stated rather than worked around.

## 6. Two declared limits

**The minimum sample is declared, not derived** — 30 per arm, stated up front so it cannot be
rationalised downward after a result is seen. A reader can disagree with 30 only because 30 is stated.

**Replay evidence alone can never promote a rule past `REPLAY_EVIDENCE_ONLY`.** Replay observes one
engine over one dataset, and agreement with the engine is not independent confirmation.

## 7. What would make a hypothesis testable

Each carries a `shortfall`: the gap between observed resolved trades and the declared minimum. On
RUN-001 the Break & Retest arm is 8 of 30 and the RZR arm 16 of 30. Closing that needs additional
authorized replays — and they must run on the current engine, because **RUN-001 predates Unit B and
carries no `triggeredConditions`**, so condition-level comparison is impossible against it.

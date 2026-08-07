# Campaign C1 — Adjudication Report (canonical)

**Campaign:** `CAMP|ALEX|C1|2026-08-05` · **Adjudicated:** 2026-08-07T00:57:23Z
**Protocol:** `PRE_ADJUDICATION_PROTOCOL.md` v1.0 · **Milestone:** MOGO-008

**This is the single adjudication permitted by PREREG-001 §7.** It was executed mechanically. No
analyst discretion was exercised at any decision boundary, and no step deviated from the protocol.

**Outcome in one line: no rule promoted, no rule rejected, all twelve hypotheses remain
`COLLECTING`.** No inferential statistic was calculated, because the protocol forbade computing one.

---

## 1. Execution record (P1.4)

```
protocol version    1.0
protocol sha256     4ff3bd5e1dd110d0aad2132fade4a8a28bd3bab09d7492cf28bb7244dbefdad3
frozen commit       39ca46fc58e1daaaf97c8047e234415c2a05893e
frozen tag          campaign-c1-pre-adjudication-frozen -> 39ca46f (identical)
PREREG-001 sha256   16e29f645f1e1252f3d2aebc6af011ba767c47dcea4ac33969ffb34392836da1
PREREG-002 sha256   42d543c4dd7d4651694e7842379977f699d69874c3930d08e002f2cf5b6981b1
registry sha256     956b75b0ab30889cbbb3923e67a0123e1956c522cdbaa0cad0f940997ff96c6b   (input state)
engine              APP_VERSION 12.19.0
interpreter         Node v24.18.0 · Python 3.14.6
os                  Darwin 21.6.0
tracked mods at run 0
```

## 2. Step 0 — Freeze and verify inputs ✅

| | |
|---|---|
| Artifacts hashed against the frozen manifest | **33 / 33** |
| Hash failures | **0** — adjudication permitted to proceed |
| Evidence admitted | Campaign C1 only (R3) |
| `mode == "REPLAY"` filter applied | **221 campaign packages** |
| Excluded non-campaign package | `PKG\|current_strategy\|20260806\|1` (limitation B6) |

## 3. Step 1 — Trade table ✅

221 rows, sorted `runId` ascending then `packageId` ascending (P1.2). Every figure derives from
packages; the harvest `stats` blocks were not cited.

```
triggeredConditions total        1,142
triggeredConditions unsatisfied      0
```

## 4. Step 2 — Arm cardinality gate — **all twelve halt**

| Hypothesis | Scope | In scope | armA | armB | Gate reached | Metrics permitted |
|---|---|---:|---:|---:|---|---|
| `HYP\|AXR-001` | ALL_SETUPS | 221 | 221 | **0** | Step 2 | **No** |
| `HYP\|AXR-002` | ALL_SETUPS | 221 | 221 | **0** | Step 2 | **No** |
| `HYP\|AXR-003` | B_breakRetest | 86 | 86 | **0** | Step 2 | **No** |
| `HYP\|AXR-004` | B_breakRetest | 86 | 86 | **0** | Step 2 | **No** |
| `HYP\|AXR-005` | A_repeatedReaction | 135 | 135 | **0** | Step 2 | **No** |
| `HYP\|AXR-007` | ALL_SETUPS | 221 | 221 | **0** | Step 2 | **No** |
| `HYP\|AXR-030` | ALL_SETUPS | 221 | 221 | **0** | Step 2 | **No** |
| `HYP\|AXR-041` | ALL_SETUPS | 221 | 221 | **0** | Step 2 | **No** |
| `HYP\|AXR-043` | ALL_SETUPS | 221 | 221 | **0** | Step 2 | **No** |
| `HYP\|AXR-051` | ALL_SETUPS | 221 | 221 | **0** | Step 2 | **No** |
| `HYP\|AXR-071` | ALL_SETUPS | 221 | 221 | **0** | Step 2 | **No** |
| `HYP\|AXR-090` | ALL_SETUPS | 221 | 221 | **0** | Step 2 | **No** |

**Halting at Step 2: 12 / 12. Reaching Step 3: 0.**

### Steps 3–7 were not executed

| Step | Status |
|---|---|
| 3 Metrics | **Not executed** |
| 4 Intervals (Welch, BCa bootstrap) | **Not executed** — the declared seed `20260806` went unused |
| 5 Effect size | **Not executed** |
| 6 Multiplicity (Holm–Bonferroni, m=12) | **Not executed** |
| 7 Gate application (R13) | **Not executed** |

**No inferential statistic was calculated for any hypothesis.** The protocol directs that a
comparison which cannot be adjudicated must not be computed; computing one would have produced a
figure with no admissible use and every opportunity to be misread.

## 5. Why armB is empty

Not a shortfall of sample. Causality runs one way: conditions satisfied → setup qualifies → trade
created → package written. A setup failing a condition never becomes a trade. Hence **1,142 of 1,142
recorded conditions are satisfied, with zero exceptions**, `candidates` and `decisions` are empty on
all 221 packages (durable decision chains remain MOGO-003 Phase 2, memory-only), and the 128
suppression records carry no condition detail — those setups were suppressed by the portfolio
constraint, not by condition failure.

| Category | Hypotheses | Reason armB cannot be populated |
|---|---|---|
| **DEFINITIONAL** | AXR-001, AXR-090 | The condition is a definition, not a per-trade predicate |
| **CONFIGURATION_CONSTANT** | AXR-030, AXR-041, AXR-043 | The condition is fixed identically for every campaign trade |
| **QUALIFICATION_GATE** | AXR-002, 003, 004, 005, 007, 051, 071 | A setup failing the condition never becomes a trade |

## 6. Status determination (R9, R10)

**All twelve: `COLLECTING`.** None `SUPPORTED`. None `REJECTED`.

Rejection is a **positive finding** requiring both arms at or above 30 (S6). Recording rejection
because evidence is absent would mirror the prohibited practice of treating "not yet refuted" as
support (SG §7), inverted. The words *insufficient* and *inconclusive* appear in this report as prose
only; the recorded schema value is `COLLECTING` (R10).

`statusReason` follows one template for all twelve. Example (`HYP|AXR-001`):

> Campaign C1 (CAMP|ALEX|C1|2026-08-05, 221 packages, engine 12.19.0, commit 39ca46f): armA=221,
> armB=0; minimum operational sample of 30 not reached in both arms. armB is empty by construction --
> the condition is definitional rather than a per-trade predicate, so no trade can fall in armB.
> Adjudicated under PRE_ADJUDICATION_PROTOCOL v1.0 R1/R9/R10; halted at Step 2 cardinality gate; no
> metric computed. Suppression for scope ALL_SETUPS: 36.7%.

## 7. Censoring (R5)

```
campaign                      128 suppressed / 354 considered = 36.2%   [trades-created basis]
scope ALL_SETUPS              128 / 349 = 36.7%                         [packages basis]
scope A_repeatedReaction       99 / 234 = 42.3%                         [packages basis]
scope B_breakRetest            29 / 115 = 25.2%                         [packages basis]
```

**Denominator bases differ and are not interchangeable.** The campaign rate uses trades created
(226); scope rates use packages (221), because trades-created is not recorded at setup-type
granularity for the five still-open trades. **36.2% is the canonical campaign figure.**

**Censoring is differential across setup types** — 42.3% for `A_repeatedReaction` against 25.2% for
`B_breakRetest`. Had any comparison been computed across setup types it would have been biased, not
merely noisy. Recorded because R5 requires it wherever a subgroup is defined, not only where a figure
is produced.

## 8. Registry changes recorded

Twelve records, three fields each, exactly as authorized:

| Field | Change |
|---|---|
| `currentStatus` | **unchanged** — `COLLECTING` for all twelve |
| `statusReason` | set to the approved adjudication text |
| `observedResolvedTrades` | set to armA: **221** ALL_SETUPS · **86** B_breakRetest · **135** A_repeatedReaction |
| `evidenceRunIds` | extended with the eleven C1 `runId`s, preserving the existing RUN-001 entry |

Untouched: hypothesis definitions, conditions, comparison groups, thresholds, metrics, scopes,
promotion ceilings, sample bases, and every other pre-registered field. The registry schema is
unmodified and only the five allowed status values are used.

**One disclosed inconsistency.** `shortfallToOperationalSample` and `shortfallToStatisticalSample`
still hold their pre-campaign values (computed against RUN-001's 24 trades). They were **not**
updated because the authorized change set does not include them, and altering them would exceed the
approved scope. They are now stale relative to `observedResolvedTrades` and should be reconciled in a
separate reviewed change — not silently here.

## 9. Findings

**No rule promoted. No rule rejected. No strategy compared or ranked. No trading change
recommended.** The promotion ceiling remains `REPLAY_EVIDENCE_ONLY`; RZR remains suspended; no
strategy is approved for live execution.

The campaign's substantive result is a **design finding, not a data finding**: eleven runs and 221
hash-verified observations cannot adjudicate these twelve hypotheses, because the declared contrast
is unobservable by this evidence class. *A hypothesis whose condition is an engine precondition
cannot be tested by observing only that engine's outputs* — the trades where the condition failed do
not exist to be measured.

PREREG-001 §1 predicted this in advance:

> The expected outcome is `INSUFFICIENT` or `INCONCLUSIVE` for most of them. That is recorded here,
> in advance, so that reporting it later is not a disappointment to be argued around.

Reporting it is the pre-registration working, not failing. The evidence set retains full value: 221
verified packages with rule attribution, excursion timing and market context now exist where none did
before, and they remain available to any future design that can populate a contrast.

Per §7, **no additional run may be added to reach a threshold.** Extending coverage requires a
successor pre-registration, declared before those runs execute and designed so both arms are
populatable — see `PRE_ADJUDICATION_PROTOCOL.md` Part 5. **No successor pre-registration was created
by this milestone.**

## 10. Audit trail

Machine-readable: `CAMPAIGN_C1_ADJUDICATION_AUDIT.json`, containing the frozen commit and tag, all
governing-document hashes, the manifest verification result, the environment record, per-hypothesis
arm cardinalities, gate reached, metrics-permitted determination, status and `statusReason`,
suppression figures, the list of steps not executed, and
`"inferentialStatisticsCalculated": false`.

---

**Adjudication complete. Executed once, mechanically, under protocol v1.0.**

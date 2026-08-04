# MOGO-004 — Research Roadmap

**Derived from:** the hypothesis registry, evidence gap matrix, educator coverage matrix, replay
campaign plan and statistical governance policy. **No milestone below is authorized.**

---

## 1. Where the research actually stands

| Fact | Value |
|---|---|
| Structured hypotheses | **41**, all ALEX |
| SUPPORTED / REJECTED | **0 / 0** |
| COLLECTING | 12 |
| UNSUPPORTED | 19 |
| UNRESOLVED | 10 |
| Verified replay runs | **1** |
| Trade-level evidence | 24 packages, one pair, one window |
| Educators with trade evidence | **1 of 5** |

**Nothing is validated, and nothing is close.** The binding constraint is evidence volume, not
analysis capability — the analysis machinery is built and idle.

## 2. Sequenced milestones

### M2 — Real-account validation *(no authorization needed beyond a page load)*
Open Diagnostics → Ledger Reconciliation on the real ALEX and JVM accounts. Confirms the integrity
rules produce no false positive on genuine history. **Blocks interpretation of every live-paper
statistic that follows.**

### M3 — Replay campaign C1 *(needs authorization)*
11 majors, 90-day control, current engine. Clears the operational sample for both setups and produces
the first evidence carrying rule attribution, timing and context. **The single highest-value action
available.**

### M4 — First hypothesis adjudication
Run the pre-registered comparisons against C1 evidence under the governance policy: Holm–Bonferroni
across the family, intervals reported, promotion capped at `REPLAY_EVIDENCE_ONLY`. Expected outcome
is a mix of `COLLECTING` and `REJECTED`, and **`REJECTED` is a real result** — it removes a rule from
consideration permanently.

### M5 — TJR to ALEX standard
Canonical rule register → fidelity matrix with code locations → rule-to-evidence join. TJR is the only
other educator with a registered engine strategy and a meaningful corpus (69 claims, 2 sources). It
needs setup detection and replay before it can produce evidence — a larger lift than it appears.

### M6 — Evidence-schema gap decision
Four ALEX rules produce no package field (cluster assignment, reaction acceptance, setup sort order,
one unnamed location). Either extend the schema — **which is MOGO-005, not MOGO-004** — or record them
as permanently unobservable.

### M7 — Statistical readiness report
Per strategy and setup: sample, what is answerable, what is not. Explicitly permitted to conclude
*"still insufficient"*.

## 3. Educator priority, with reasons

| Rank | Educator | Why |
|---|---|---|
| **1** | **ALEX_G** | the only educator with a rule register, fidelity matrix, join, replay capability and trade evidence. Marginal cost of more evidence is near zero |
| **2** | **TJR** | registered strategy, 69 claims, 2 sources, Phase-1 session engine. Needs setup detection + replay before evidence exists |
| 3 | RAYNER_TEO | 46 claims and 31 hypotheses but **no engine strategy** — implementation cost dominates |
| 4 | ICT | profile only: **0 sources, 0 claims**. Acquisition must precede everything |
| — | **CRT** | ⚠️ **no CRT material exists in this repository** — no profile, no sources, no claims. It cannot be prioritized until acquisition happens |

## 4. Which hypotheses deserve investment

**Highest:** the 12 `COLLECTING` hypotheses — implemented, observed, and short only of sample. C1
converts them from unanswerable to adjudicable.

**Medium:** the 6 `UNSUPPORTED`-because-unobserved rules — implemented but never exercised; broader
pair coverage may exercise them.

**Low / none:** 19 `UNSUPPORTED` where MOGO does not implement the rule or the rule is MOGO-authored —
these are implementation or specification questions, not research questions. The 4 live-only and
4 no-evidence-field rules cannot be advanced by any replay.

## 5. Decisions required before M3

1. **Replay authorization** — pairs, windows, run count.
2. **Confirmation of the pre-declared thresholds** (30 operational / 100 statistical / 0.25R) *before*
   evidence is collected.
3. **Educator #2** — TJR confirmed, or acquisition of CRT material first.
4. **The stored 8899 balance** — corrected or retained as a forensic artifact.

## 6. What success looks like

At the end of MOGO-004 we should be able to say, for every ALEX rule, either *"the evidence supports
it"*, *"the evidence rejects it"*, or *"here is exactly what is still missing."* **Ending with mostly
the third answer is an acceptable outcome.** Ending with the first answer for a rule that has not
earned it is not.

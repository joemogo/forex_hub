# MOGO-002.8 — Engineering Review Package

**Milestone:** ALEX Source Coverage & Strategy Fidelity Audit · **Status:** COMPLETE, awaiting Engineering Authority review
**Date:** 2026-07-29 · **HEAD:** `a332d04` (all MOGO-002.x work uncommitted)
**Type:** Evidence and fidelity audit. **Not an implementation milestone.**

> **No production trading logic was modified. No ALEX implementation change was made. No draft rule
> was promoted. No stop buffer was authored. Replay remains unauthorized. Nothing was committed,
> pushed, deleted, renamed or moved.**

---

## 1. Executive Summary

This audit answered the six questions in the brief against repository evidence only.

**Source coverage is good and precisely bounded.** **9 ALEX_G sources**, all `ACQUIRED_AND_PROCESSED`:
226 claims, 280 evidence items, 134 segments, **452 provenance checks with 0 findings**, zero
duplicates. **No total-catalogue figure is stated anywhere in this package** — the channel listing is
JS-rendered and could not be enumerated, so any "N of M" or percentage would be a fabricated
denominator.

**The reconstructed rule register is rich in description and thin in specification.** 41 canonical
rules: 26 `EXPLICIT`, 5 `ILLUSTRATIVE`, 1 `OPINION`, **9 `UNSUPPORTED`** — and only **6 of 41 are
deterministic**. Nine domains have a rule; **seven are absent from all reviewed sources.**

**The headline fidelity result is the one that has never been measured before.** Comparing MOGO
against the *educator library* (rather than against its own specification) yields **zero
`EXACT_MATCH`**, **7 rules the educator teaches that MOGO lacks**, **6 MOGO implements differently**,
and **6 MOGO implements that the educator never taught**. The three divergences with real
trade-eligibility consequence are:

1. **MOGO has no candlestick-confirmation gate**, which the educator states as a *necessary* entry
   condition and demonstrates by **declining a textbook setup on camera** for its absence.
2. **MOGO applies no session or day-of-week restriction**, while the educator states an explicit
   Mon–Wed and session gate. MOGO computes the metadata and deliberately ignores it.
3. **MOGO requires 4+ touches; the educator states a minimum of ONE structure point.** MOGO is
   materially stricter than the source.

**A subtler finding that matters for KEREV-A:** MOGO's stop anchors on the **zone boundary**
(`setup.zoneLow`/`zoneHigh`); the educator anchors on the **rejection formation at the retest**. A
rejection wick routinely extends past the zone boundary, so **these are not the same object** even
though both read as "just beyond the structure." The surface similarity must not be read as agreement.

**Freeze readiness: `NOT_READY_BOTH`** — three source gaps *and* five implementation mismatches.
**Replay: NOT AUTHORIZED**, and this audit does not request it.

**KEREV-A: `REFRAME_KEREV_A`.** The separation the Authority proposed is **exactly what the evidence
shows** — the relationship is Alex's, the buffer is MOGO's. Two of the original four options are now
factually dead.

**One infrastructure defect reproduced and handled:** the knowledge-engineering test suite **mutated
10 repository artifacts**. Detected, documented, restored 30/30 byte-identical, reported below.

---

## 2. Repository-Truth Confirmation

| Check | Value |
|---|---|
| ALEX_G sources / claims / evidence items / segments | **9 / 226 / 280 / 134** |
| Evidence quality | high **150**, medium **101**, low **29** |
| Provenance re-verification | **452 checks, 0 findings** |
| Evidence integrity · graph integrity | **0/0/0/0** in both |
| Library claims, all traders | **341, all `emerging`** |
| Rule candidates (`evidence/proposals/`) | **0** |
| Production specification | `alex_g_sr_v1`, 13 rules, hash `a0b7641e288c1725` — **unchanged** |
| Protected functions / constants | **63 / 4, byte-identical** |
| `index.html` | **113 insertions, 0 deletions** — unchanged from MOGO-002.5; **untouched here** |
| `docs/ROADMAP.md` | **unmodified** |

`CLAUDE.md` does not exist in this repository; governance was reconstructed from `CONTRIBUTING.md`,
the nine ADRs, the six `OwnerDecision` records, `POLICY-001`, and the trader-intelligence READMEs.

## 3. Source Inventory — Phase 2

Full detail: [`ALEX-SOURCE-COVERAGE-AUDIT.md`](../strategy-fidelity/audit/ALEX-SOURCE-COVERAGE-AUDIT.md)

**9 `ACQUIRED_AND_PROCESSED`. 0 partial, 0 missing, 0 duplicate, 0 attribution-uncertain among
acquired sources.**

Two concentrations worth the Authority's attention:

- **Source #6 alone carries 13 of the corpus's 14 `risk_rule` claims.** The entire sizing layer rests
  on one 16 KB transcript. If that source were withdrawn or found unrepresentative, the layer
  collapses.
- **Source #9 is the only source containing a `stop_rule` claim.** Sources #1–#8 contain zero between
  them.

**4 identified-not-acquired targets** (3 profiles + 1 `ATTRIBUTION_UNCERTAIN` interview where the
educator speaks on a third-party channel). **7 rejected**, all third-party, all for **lineage not
quality** — including `iXjrVyTAS6M`, which is the most likely of the seven to contain the missing stop
buffer and is still unusable for attribution.

**One further target is named inside the corpus itself** — at 5:33 of source #9 the educator points
directly at a dedicated engulfing-candlestick video. See §7.

## 4. Canonical Rule Register — Phases 3–4

Full detail: [`ALEX-CANONICAL-RULE-REGISTER.md`](../strategy-fidelity/audit/ALEX-CANONICAL-RULE-REGISTER.md)

**41 rules. 6 deterministic. 9 `UNSUPPORTED`. 21 of 41 carry short-side support.**

**Domain coverage:** 4 `WELL_SUPPORTED` · 5 `SUPPORTED` · 12 `PARTIALLY_SUPPORTED` · 1 `AMBIGUOUS` ·
1 `NON_DETERMINISTIC` · 2 `DISCRETIONARY` · **7 `ABSENT_FROM_REVIEWED_SOURCES`**.

**Three structural findings:**

1. **A quantified minimum over an undefined unit is still non-deterministic.** *"Minimum of one
   structure point"* carries a number, but *structure point* is never defined. This is the corpus's
   most common failure mode.
2. **The educator sometimes states an explicit NON-constraint.** Zone width — *"doesn't matter the
   size of the box"* — is the clearest case, and it directly bears on production rule `ALEX_SR_008`,
   whose source is recorded as *"no formula given."* He does not merely omit a formula; **he declines
   to impose one**, and MOGO imposes one anyway.
3. **The rule/parameter split is the corpus's signature.** Session gating is prescriptive, explicit
   and repeated; the hours are displayed on screen and never spoken. Day-of-week **is** deterministic;
   the hours are not.

**Examples were held apart from rules throughout.** 1:2 is recorded as a stated floor; 1:3, 1:4 and
the 80–100 pip average are `ILLUSTRATIVE`; the three-doji Morning Star count is `ILLUSTRATIVE`.
**No numeric stop buffer is attributed to Alex anywhere**, because no primary source provides one.

## 5. Fidelity Matrix — Phase 5

Full detail: [`ALEX-IMPLEMENTATION-FIDELITY-MATRIX.md`](../strategy-fidelity/audit/ALEX-IMPLEMENTATION-FIDELITY-MATRIX.md)

**⚠️ Scope warning carried in the artifact itself:** this compares MOGO against the *educator
library*. `DECISION|MOGO|20260727|004` states `alex_g_sr_v1`'s rules are **MOGO's own**. Every
agreement is **convergence, not derivation**. The matrix is observational and does **not** re-specify
the strategy or resolve KEREV-B.

| Status | Count |
|---|---|
| `FUNCTIONAL_MATCH` | 8 |
| `PARTIAL_MATCH` | 6 |
| `PRESENT_BUT_DIFFERENT` | **6** |
| `MISSING_FROM_MOGO` | **7** |
| `IMPLEMENTED_WITHOUT_EDUCATOR_SUPPORT` | **6** |
| `MOGO_AUTHORED_PARAMETER` | 1 |
| `NON_IMPLEMENTABLE_DISCRETION` | 2 · `NOT_APPLICABLE` 3 · `UNRESOLVED` 2 |
| **`EXACT_MATCH`** | **0** |

**Ten MOGO-authored parameters are enumerated**, headed by `stopATRBuffer = 0.25` — which has **no
educator counterpart at all**, since no ALEX_G claim in nine sources mentions ATR.

**`riskPercent = 1.0` is the single genuinely well-aligned parameter**, sitting inside both bands the
educator names.

**Against `alex_g_sr_v1` the picture is unchanged and remains authoritative for production:** 9 MATCH,
2 APPROXIMATED, 1 AMBIGUOUS, 1 NOT_APPLICABLE, 8 EXTRA, **0 MISSING, 0 DIFFERING**. The engine is
faithful to *its own* specification and divergent from *the educator's*. **Both are true at once**,
and this package is careful never to report one as the other.

## 6. Freeze Readiness — Phase 8

Full detail: [`ALEX-STRATEGY-FREEZE-READINESS.md`](../strategy-fidelity/audit/ALEX-STRATEGY-FREEZE-READINESS.md)

# `NOT_READY_BOTH` · Replay **NOT AUTHORIZED**

**3 blocking source gaps:** stop buffer absent · four post-entry-management zeros · session hours
readable only as pixels.
**5 blocking implementation mismatches:** no confirmation gate · no session gate · fixed vs minimum
R:R · 4-touch vs 1-touch minimum · zone-width constraint against an explicit non-constraint.
**2 material governance findings:** all claims `emerging` under `POLICY-001` (**FRZ-09**), and
execution readiness `NOT_VERIFIED`.

**FRZ-09 is the one that survives perfect acquisition.** Even if every source gap closed tomorrow, the
D2 blocker still prevents promotion — **freeze readiness is gated on a governance decision, not only
on evidence.**

Also worth stating plainly: **even the most permissive plausible ruling on MOGO-authored parameters
does not reach `READY_WITH_DOCUMENTED_MOGO_PARAMETERS`**, because FRZ-02…FRZ-05 are behavioural
differences, not parameter gaps.

## 7. Gaps and the Next Acquisition — Phase 6

Full detail: [`ALEX-KNOWLEDGE-GAPS-AND-SOURCE-PLAN.md`](../strategy-fidelity/audit/ALEX-KNOWLEDGE-GAPS-AND-SOURCE-PLAN.md)

**8 gaps; 5 block replay.**

> **Rank 1 — an ALEX_G live session showing an order actually being placed.** Resolves AXG-01, -02,
> -04, -08. A stop price must be typed into a ticket. Executes standing target A2-LIVE.
> **Risk: he may show the number without speaking it — the `KEGAP-003` failure mode.**
>
> **Rank 2 — the engulfing-candlestick video the educator points at himself** at 5:33 of source #9.
> Resolves AXG-03, the largest trade-eligibility divergence. **The only gap in the plan with a named,
> educator-pointed-at source.**

**If only one can be acquired, acquire rank 2** — near-certain to exist, near-certain to be on-topic.
Rank 1 has higher value but materially higher failure risk.

**What acquisition cannot fix:** session hours (needs a frame-reading decision), swing significance
(needs replay), `XCONTRA|20260729|004` (needs an Authority ruling — both positions are already the
educator's), and **D2** (bounds the value of all acquisition: no acquired rule can become a candidate
rule while claims stay trader-scoped).

## 8. KEREV-A — Phase 7

**Recommendation: `REFRAME_KEREV_A`.** Not closed.

**The proposed separation is supported:**

| Component | Verdict |
|---|---|
| **Alex-authored:** *"stop belongs beyond the rejection structure"* | ✅ **SUPPORTED** — `CLAIM\|ALEX_G\|20260729\|025`, `rule_statement` / `direct_explicit` / `certain`, explicitly universalised, plus two demonstrations |
| **MOGO-authored:** the numerical buffer | ✅ **CONFIRMED UNSUPPORTED** — zero claims, zero ATR mentions, across 9 sources |

**Can be struck:** Option B (*accept as absent*) — factually unavailable. Option D (*cross-educator
module*) — unnecessary and would overwrite a real attribution.

**Must remain open:** the buffer distance · the anchor identity (3 readings, and **MOGO currently uses
a different anchor from the educator**) · the short-side rule (MOGO's symmetry is an assumption).

**Why not close:** two of the three parameters needed to place a stop mechanically are still absent,
and closing would license reading MOGO's 0.25 ATR as educator-supported — the exact lineage error
`KEREV|058` exists to prevent.

## 9. Test Results — Phase 9

| Command | Result |
|---|---|
| `tests/run_all.sh` | **591 / 591 fixtures**, 13 suites, **0 failures**, 0 execution errors |
| Protected-function / constant drift | **ZERO** — 63 functions, 4 constants byte-identical |
| `python3 -m unittest tests.strategy_fidelity.test_strategy_fidelity` | **63 / 63 pass** |
| `python3 -m unittest tests.knowledge_engineering.test_knowledge_engineering` | **55 / 57** — 2 known-obsolete failures |
| `tests.trader_intelligence.*` (5 modules) | **307 tests, 4 failures** — known-obsolete, unchanged |
| `ingest.py --verify-provenance` | **452 checks, 0 findings** |
| `validate_evidence.py` · `validate_graph.py` | **0 / 0 / 0 / 0** in both |
| Audit JSON validity | **5 / 5 parse** |
| Audit generator determinism | **byte-identical across two runs** |

**Known obsolete failures — 6 total, none introduced here:**

- 4 pre-existing `trader_intelligence` tests asserting *the production evidence tree is empty* (false
  since 2026-07-27).
- 2 `knowledge_engineering` tests from MOGO-002.7: `test_all_195_claims_are_inventoried`
  (`226 != 195`) and `test_delta_reports_the_unclosed_risk_gap` (`2 != 0`). The second **encoded a
  finding rather than an invariant** — it asserted the risk gap was unclosed *by asserting zero stop
  rules exist*. The gap **is** still unclosed; the mechanism is wrong.

**No production logic was changed to make any test pass.**

### ⚠️ 9.1 Infrastructure risk reproduced — the KE suite mutates repository artifacts

**`tests/knowledge_engineering/test_knowledge_engineering.py` calls `build_ke_artifacts.generate_all()`
three times (lines 305, 338, 370), and `generate_all()` writes into `docs/knowledge-engineering/`.**

Per the Phase 9 instruction, artifacts were hashed **before** the run. The run **mutated 10 of 30
files**:

```
alex-strategy-specification-v2-draft.json   candidate-rules.json
claim-inventory.json                        claim-to-rule-mapping.json
contradiction-register.json                 human-review-queue.json
knowledge-coverage.json                     normalization-decisions.json
normalized-rules.json                       specification-delta.json
```

**All 30 were restored and re-verified byte-identical (30/30).**

**Why this is a real risk, not a nuisance:** those ten files are MOGO-002.6 deliverables **awaiting
review**, and **nothing in this repository is committed**, so there is no version control to restore
from. A single routine test run by anyone — including the Authority during review — silently rewrites
them to the current 226-claim state with no warning and no way back. This was first found in
MOGO-002.7 (defect D-3) and is now **reproduced under controlled conditions.**

**Recommended fix (not applied — out of scope):** the suite should generate into a temp directory, as
the `trader_intelligence` fixtures already do.

## 10. Files Created or Changed

**Created — audit package (7 files):**
```
docs/strategy-fidelity/audit/ALEX-SOURCE-COVERAGE-AUDIT.md
docs/strategy-fidelity/audit/ALEX-CANONICAL-RULE-REGISTER.md
docs/strategy-fidelity/audit/ALEX-IMPLEMENTATION-FIDELITY-MATRIX.md
docs/strategy-fidelity/audit/ALEX-KNOWLEDGE-GAPS-AND-SOURCE-PLAN.md
docs/strategy-fidelity/audit/ALEX-STRATEGY-FREEZE-READINESS.md
docs/strategy-fidelity/audit/alex-{source-coverage-audit,canonical-rule-register,
  implementation-fidelity-matrix,knowledge-gaps-and-source-plan,strategy-freeze-readiness}.json
docs/reports/MOGO-002.8_ENGINEERING_REVIEW.md   (this file)
scripts/knowledge_engineering/build_alex_audit.py
```

**Changed by validators (disclosed, not reverted):** two `generatedAt` timestamps and two report IDs
in `evidence/reports/integrity-report.json` and `graph/reports/integrity-report.json`. `findings`
stayed `[]` and every severity count stayed 0 in both. The new values are the accurate ones.

**Restored after test mutation:** the 10 KE artifacts above, verified 30/30 byte-identical.

**Verified unmodified:** `index.html` (113/0 from MOGO-002.5) · `docs/ROADMAP.md` · the production
specification · all `alex_g_sr_v1` manifests and the MOGO-002.5 fidelity report · every
`trader-intelligence` evidence record.

**Untracked artifact impact:** 7,875 → **7,887** (+12, this package). Modified tracked files: still
**17**. The repository-stabilization risk from MOGO-002.7 is unchanged and unaddressed —
**nothing was committed, and commit boundary C1 remains unapproved.**

## 11. Engineering Authority Decisions Required

| # | Decision | Recommendation |
|---|---|---|
| **A8-1** | **KEREV-A — adopt the reframing?** May MOGO author the stop **buffer** and the **anchor reading** as explicitly-labelled MOGO parameters, or must acquisition continue first? | **Reframe as drafted.** Strike options B and D. Keep the buffer, anchor and short side open. |
| **A8-2** | **Acquire the engulfing-candlestick video** the educator points at (5:33, source #9)? | **Yes — this is the single best next acquisition.** Named source, highest certainty, closes the largest trade-eligibility divergence. |
| **A8-3** | **Acquire a live session with order entry?** | **Yes, in parallel.** Highest value, meaningful failure risk. |
| **A8-4** | **The three behavioural divergences** — no confirmation gate, no session gate, 4-touch vs 1-touch. Accept as deliberate MOGO design, or open an implementation milestone? | **Decide explicitly.** These are currently undocumented differences, not recorded decisions. Recommend **recording them as MOGO-authored divergences** rather than changing code. |
| **A8-5** | **Fix the KE test-suite mutation defect** (§9.1)? | **Yes, before review of MOGO-002.6.** Its deliverables can be destroyed by running its own tests, with no version control to recover from. |
| **A8-6** | **`XCONTRA\|20260729\|004`** — is 1:2 a floor a trade may be set at, or a level a preset target must never be revised down to? | **Rule on it.** No further ALEX_G source can settle it. |
| **A8-7** | **D2 / concept-level consensus** — unchanged, now with a fourth demonstration. | **Decide.** It bounds the value of every future acquisition. |
| **A8-8** | **Commit boundary C1** (raw source material), from MOGO-002.7. | **Approve.** 7,887 untracked files; twelve irreplaceable transcripts; no version control safety net — as §9.1 just demonstrated. |

**Still open and untouched:** OD-2…OD-7 (MOGO-002.5); KEREV-B…E (MOGO-002.6); A7-* (MOGO-002.7).

## 12. Recommended Next Action

1. **A8-2 + A8-3 — acquire.** Two named targets, one near-certain. This is the only work that moves
   the source gaps.
2. **A8-1 — reframe KEREV-A.** It is decidable now and the reframing is drafted.
3. **A8-5 — fix the test mutation defect.** It threatens artifacts that are currently under review.
4. **A8-8 — approve C1.** Independent of every research decision.

**Explicitly not recommended:** changing any ALEX trading rule to close a fidelity gap · authoring a
stop buffer · promoting any educator rule · beginning replay · treating the educator register as a
specification · merging the two bodies of knowledge.

---

*MOGO-002.8 complete. **Freeze readiness `NOT_READY_BOTH`. Replay NOT AUTHORIZED. KEREV-A
`REFRAME_KEREV_A`, still OPEN.** No production or paper-trading behaviour changed; no ALEX
implementation change; nothing committed. Stopping for Engineering Authority review.*

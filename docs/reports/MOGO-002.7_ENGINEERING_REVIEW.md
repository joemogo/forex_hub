# MOGO-002.7 — Engineering Review Package (v2, post-ingestion)

**Milestone:** Source Acquisition for Blocking Gaps · **Status:** COMPLETE, awaiting Engineering Authority review
**Date:** 2026-07-29 · **HEAD:** `a332d04` (milestone work uncommitted)
**Type:** Evidence-acquisition and decision-support. **Not an engineering implementation milestone.**

> **KEREV-A is NOT resolved.** The gap it governs moved from `ABSENT_FROM_REVIEWED_SOURCES` to
> **`PARTIALLY_SUPPORTED`**. Two of its four options are now factually unavailable.
>
> **No production trading behaviour was changed. No draft rule was promoted. Replay remains
> unauthorized. Nothing was committed.**

---

## 1. Executive Summary

The operator supplied the missing transcript, clearing the stop condition raised in v1 of this
package. The source was ingested through the documented pipeline and **the milestone's primary
objective was achieved: Alex G states a stop-placement rule.**

**`ALEX_G` `stop_rule` claims went 0 → 2**, the first in nine sources and 226 claims. The decisive
item is at **8:59**:

> *"it's literally the same thing every single time your stop- loss is right under it you have a
> minimum of a 1 to two risk to reward"*

That is a `rule_statement` with `direct_explicit` directness. *"The same thing every single time"*
**generalises** two prior chart demonstrations into an invariant — it is not an example, and it is
not discretionary guidance. The library also gained an explicit **minimum 1:2 risk-to-reward**, stated
twice, where MOGO-002.6 had recorded that no minimum R:R was stated anywhere.

**And yet KEREV-A cannot be closed, for a precise reason.** The rule states a *relationship* and
withholds two parameters:

| | Missing | Consequence |
|---|---|---|
| **STOP-UNK-1** | **The buffer distance** — no pips, no ATR, no percentage, not even "flush" | **Position size = risk ÷ stop distance, so the 15 sizing rules remain non-computable** |
| **STOP-UNK-2** | **The anchor identity** — "it" / "this point" has three readings, each giving a different stop distance | An implementation would have to choose |
| **STOP-UNK-3** | **The short side** — all three demonstrations are longs; *"right above"* is never stated | Half the rule is unstated |

**The pipeline reached the same conclusion independently.** Regenerating the educator draft placed
both stop rules into it with **`deterministic: false`** — RISK gained 2 rules and **0** deterministic
rules. The knowledge-engineering layer concluded, without being told, that the rule cannot be
evaluated mechanically.

**Two of KEREV-A's four options are now dead.** Option B (*accept as absent*) would make the record
false. Option D (*import a cross-educator stop*) is now pointless as well as prohibited. What remains
is a much smaller question than before: **may MOGO author the buffer, under an explicit
MOGO-authored label, on top of a relationship the educator genuinely stated?**

**The three absolute zeros held.** Break-even, partial profits and scaling remain at **zero mentions
across nine sources** — and this source narrates three complete trades end to end, which is exactly
where any of the three would naturally have been mentioned. That is now a much stronger negative
result than it was.

**Zero confidence movement, again.** All 341 claims remain `emerging`; max score is unchanged at
25.62. A ninth same-educator source cannot corroborate the other eight
(`DECISION|MOGO|20260727|006`). **This is the third independent demonstration of the D2 blocker: the
library just acquired the rule it most needed and is structurally unable to believe it.**

**Validation:** 591/591 JS fixtures · **zero protected-function drift** · 63/63 fidelity tests ·
**452 provenance checks, 0 findings** · evidence and graph integrity 0/0/0/0 · report generation
byte-identical across runs. **2 knowledge-engineering tests now fail** — both hardcoded
counts made obsolete by the new evidence, reported in §17 and deliberately not "fixed".

---

## 2. Repository-Truth Confirmation

| Check | Before | After |
|---|---|---|
| Registered evidence sources | 11 | **12** (ALEX_G **9**, TJR 2, RAYNER_TEO 1) |
| Library claims | 310 | **341** |
| ALEX_G claims | 195 | **226** |
| ALEX_G evidence items | 244 | **280** |
| **ALEX_G `stop_rule` claims** | **0** | **2** |
| ALEX_G `target_rule` / `trade_management_rule` | 4 / 4 | **5 / 5** |
| Confidence states | all `emerging` | **all `emerging`** |
| Max confidence score | 25.62 | **25.62** |
| Rule candidates (`evidence/proposals/`) | 0 | **0** |
| Graph | 2,161 nodes | **2,422 nodes, 5,109 edges, 0 findings** |
| Production specification | 13 rules, `a0b7641e288c1725` | **unchanged** |
| Protected functions / constants | 63 / 4 | **byte-identical** |
| `index.html` | 113 insertions, 0 deletions | **unchanged — untouched by this milestone** |

**Stop conditions:** the v1 condition `PROVIDED_TRANSCRIPT_CANNOT_BE_FOUND_OR_RECONSTRUCTED` is
**RESOLVED**. No new stop condition triggered. No schema change was required.

## 3. Blocking-Gap Acquisition Checklist

[`MOGO-002.7-BLOCKING-GAP-ACQUISITION-CHECKLIST.md`](../knowledge-engineering/MOGO-002.7-BLOCKING-GAP-ACQUISITION-CHECKLIST.md)
· recomputed post-ingestion.

| Row | Domain | Matching items | Rule-bearing types present |
|---|---|---|---|
| **BG-01** | Stop placement | 5 → **10** | none → **`stop_rule`** |
| BG-02 | Position sizing | 16 → 18 | `risk_rule`, `target_rule`, `session_rule` |
| BG-03 | Take-profit | 13 → **17** | `target_rule`, `invalidation_rule`, `trade_management_rule` |
| BG-04 | Trade management | 8 → 10 | `risk_rule` |
| BG-05 | Exit | 6 → 7 | `trade_management_rule` |
| **BG-06** | **Break-even** | **0 → 0** | — |
| **BG-07** | **Partial profits** | **0 → 0** | — |
| **BG-08** | **Scaling** | **0 → 0** | — |

## 4. Sources Reviewed

| Source | Outcome |
|---|---|
| **`kg-rOo9_xjU`** — the provided source | **INGESTED** as `EVSRC\|ALEX_G\|20260729\|001` |
| 8 pre-existing `ALEX_G` sources | Re-analysed against all ten blocking domains |
| 7 third-party videos | Channel ownership verified individually — **all rejected for lineage** |
| 1 interview featuring the educator | `ACCEPTED_SUPPORTING`, deferred pending a schema decision |

## 5. Sources Accepted

**`EVSRC|ALEX_G|20260729|001` — `ACCEPTED_PRIMARY`.**

Attribution verified (oEmbed `author_url` = `@fxalexg__`, byte-identical to registered
`EVSRC|ALEX_G|20260728|005`). Provenance complete: SHA-256
`7f954e14ec5cb0a6b17de28fb0e6caed6910e6cc4f2ec72c8c6cc3b3441e58d2`, reversible normalization with
**0 words added / removed / reordered**, 13 segments, **36 excerpts each confirmed verbatim before
apply**, 31 claims.

Accepted **despite heavy marketing content** — five unverified monetary claims and two funnel CTAs —
because the mechanical content is genuine, specific and demonstrated three times. Recorded as
**`MARKETING_HEAVY_BUT_NOT_MARKETING_DOMINANT`**: 6 of 31 claims are `performance_hypothesis` at
`evidenceQuality: low`, and **none of them supports a rule.**

## 6. Sources Rejected or Deferred

Unchanged from v1: **7 third-party reconstructions rejected for lineage, not quality.** A third
party's account of Alex's stop rule cannot establish Alex attribution — governance rules 7 and 8.
`iXjrVyTAS6M` remains the most likely of the seven to contain a stop rule and remains unusable.

Deferred: the paid course product (purchase is an owner decision) and the `Trading Nut` interview
(`EvidenceSource` cannot yet express "educator speech on a third-party channel").

## 7. Source Coverage Report

[`MOGO-002.7-SOURCE-COVERAGE-REPORT.md`](../knowledge-engineering/MOGO-002.7-SOURCE-COVERAGE-REPORT.md)

**Closes: none. Partially addresses: 4. Does not address: 4. Makes more ambiguous: 2.**

**No gap is reported as closed, deliberately** — the brief warns against claiming closure because one
example was shown. Three examples were shown and one invariant stated; that moves four gaps and closes
none.

**The brief's own predictions, now checked against the transcript:** five of seven fully confirmed;
two overstated, both in the same direction. *"Bullish **or bearish** engulfing"* — only bullish is
stated. *"Stop placement below **or above**"* — only *"under"* is stated. **The brief overstated the
short side twice**, which retroactively validates v1's refusal to treat the description as evidence.

## 8. Updated Gap States

[`MOGO-002.7-gap-states.json`](../knowledge-engineering/MOGO-002.7-gap-states.json)

| Gap | Subject | Before | **After** |
|---|---|---|---|
| **KEGAP-001** | Stop placement | `ABSENT_FROM_REVIEWED_SOURCES` | **`PARTIALLY_SUPPORTED`** |
| **KEGAP-002** | Exit methodology | `ABSENT_FROM_REVIEWED_SOURCES` | **`PARTIALLY_SUPPORTED`** |
| **KEGAP-005** | Take-profit selection | `PARTIALLY_SUPPORTED` | `PARTIALLY_SUPPORTED` (materially stronger) |
| **KEGAP-006** | Post-entry management | `PARTIALLY_SUPPORTED` | `PARTIALLY_SUPPORTED` (materially stronger) |
| KEGAP-003 | Session hours | `UNREADABLE_OR_INSUFFICIENT_TRANSCRIPT` | unchanged |
| KEGAP-004 | Swing significance | `CONTRADICTORY_SOURCE` | unchanged, **reinforced** |
| **KEGAP-007/008/009** | Break-even / partials / scaling | `ABSENT` | **`ABSENT` — still zero across 9 sources** |
| KEGAP-010 | Open contradictions | `EA_DECISION_REQUIRED` | unchanged, **11 → 13** |

**Nothing reached `SUPPORTED_BY_EXPLICIT_SOURCE`.** `ABSENT_FROM_REVIEWED_SOURCES` continues to mean
absent from the reviewed set, never "the educator has never addressed it" — written into the
artifact's `absenceSemantics` field.

**KEGAP-002 deliberately stopped at `PARTIALLY_SUPPORTED`**: exits are *demonstrated* at the preset
stop or target across three trades, and never *stated* as an invariant the way the stop rule is.

## 9. New Candidate Rules

**Zero.** `evidence/proposals/` still holds 0 records.

**This is `POLICY-001` working, not an omission.** `RuleCandidateProposal` is created only for claims
that reach `supported`; every claim from this source is `emerging` because one source cannot
corroborate itself. **The most important rule the library has ever acquired produced no candidate
rule** — which is the D2 problem stated as precisely as it can be stated.

## 10. Claims Not Promoted, and Why

| Not promoted | Why |
|---|---|
| **The stop rule → a candidate rule** | `emerging` confidence; `POLICY-001` gate |
| **"1:2" → a fixed target ratio** | Stated as a **minimum**. Reading a floor as a fixed value is a different rule that merely coincides at the boundary — and is how production's `minRR 2.0` behaves |
| **1% → the risk rule** | Appears only inside worked arithmetic; the explicit bands remain source #6's |
| **"three doji + one engulfing" → a required count** | Describes one instance; never universalised |
| **"set and forget" → a trade-management rule** | Now names a procedure rather than a podcast format, but it remains a brand label |
| **Single-entry / no-partials → stated rules** | Follow plausibly from three demonstrations. Recorded as **absence of evidence**, not as stated rules |
| **A short-side stop rule** | *"Right above"* is never stated. Not mirrored by assumption |
| **"Intraday" for the garbled *"Inay"*** | Obvious candidate, but it would conflict with the day-trading rule one clause earlier. Recorded as an open question |
| **"$1,000" for the corrupted *",000"*** | Left unreadable |

## 11. Contradictions Discovered

**2 new, both within-educator. Open contradictions 11 → 13.**

- **`XCONTRA|20260729|003`** · `NUMERIC_THRESHOLD` · **minor** — a **third** incompatible
  monthly-return range: **9–12%** here, **8–10%** *"that is a fact anybody can do that"* (source #6),
  **7/12/15%** then 7–10% (source #8). No trading decision depends on it, but three incompatible ranges
  for one headline number bear on how this source's numeric claims should be weighted.
- **`XCONTRA|20260729|004`** · `CONDITIONAL_SCOPE` · **material** — **the consequential one.** A stated
  **1:2 minimum** target here, against source #8 naming a **1:4 cut to 1:2** as the core psychological
  failure. Both cannot be applied without a rule distinguishing a target **set at** the floor from one
  **revised down to** it. **That distinction governs whether a preset target may be changed after
  entry**, so it bears on `KEGAP-006` as well as `KEGAP-005`.

**Stop placement remains uncontested across all nine sources.** Nothing anywhere disagrees with
*"right under it"* — so **KEREV-A still does not have to wait on KEREV-C.**

## 12. Stop-Placement Evidence Package (KEREV-A)

[`KEREV-A-STOP-PLACEMENT-EVIDENCE-PACKAGE.md`](../knowledge-engineering/KEREV-A-STOP-PLACEMENT-EVIDENCE-PACKAGE.md) — rewritten as v2.

All 10 stop-referencing items classified: **1 `EXPLICIT_RULE`**, **2 `EXAMPLE_DEMONSTRATED_PLACEMENT`**,
2 `INCOMPLETE`, 3 `NOT_A_STOP_STATEMENT`, 1 `TRADE_MANAGEMENT_NOT_PLACEMENT`, 1
`LEXICAL_FALSE_POSITIVE` (retained deliberately). **Discretionary guidance on placement: 0** — he says
the opposite of discretionary.

### ⚠️ Convergence analysis — the section that most needs the Authority's attention

The resemblance to MOGO's `ALEX_X_001` is now **much closer**, which makes the lineage discipline
**more** important, not less:

| | MOGO `ALEX_X_001` | Alex G, as now stated |
|---|---|---|
| Relationship | just beyond the structure | just beyond the structure |
| **Anchor** | **`setup.zoneLow` / `zoneHigh`** (zone boundary) | **the rejection formation at the retest** |
| **Buffer** | **`0.25 × ATR`** | **not stated** |
| Target | **fixed** `2.0 × risk` | **minimum** 1:2 |
| Directions | both | **long only** |

1. **The anchors are different objects.** A rejection wick can extend well beyond the zone boundary.
   Treating them as equivalent is an assumption, not a reading.
2. **The `0.25 ATR` buffer has no educator counterpart.** No ALEX_G claim in nine sources mentions ATR.
   It remains **entirely MOGO-authored**.
3. **`minRR 2.0` and "minimum 1:2" are different rules coinciding at a boundary.** An implementation
   that always targets exactly 2R does **not** implement what he stated.

**None of this makes production's rules educator-derived.** `DECISION|MOGO|20260727|004` stands, and
MOGO-002.6's convergence-not-derivation finding stands. What changed is that the *draft* can now
support a stop relationship and a 1:2 floor on its own footing.

## 13. Remaining Source Needs

| Need | Gaps | Status |
|---|---|---|
| **A source stating the stop buffer, or showing a short-side stop** | `KEGAP-001` | **The new highest-value target.** Live session with order entry is the strongest candidate |
| A "set and forget" explainer | `KEGAP-007/008/009` | The three absolute zeros are unchanged |
| Course-format material with parameters spoken | `KEGAP-003` | Licensing decision required |
| An approved frame-reading method | `KEGAP-003` | **Not a transcript-acquisition task** |
| Replay authorization + market data | `KEGAP-004`, 10 of 13 contradictions | **Deliberately out of scope** |

## 14. Ranked Acquisition Queue

[`MOGO-002.7-ACQUISITION-QUEUE.md`](../knowledge-engineering/MOGO-002.7-ACQUISITION-QUEUE.md)

Rank 1 (`kg-rOo9_xjU`) is now **`ACCEPTED_PRIMARY` / COMPLETE**. **Rank 3 — a live session showing
order entry — is promoted to the top live target**, because a stop price must be typed into a ticket
and that is the one place the buffer is likely to become visible. Ranks 2, 4 and 5 are unchanged;
rank 6 remains rejected; rank 7 remains deferred on a schema question.

## 15. Proposed Roadmap Correction

[`MOGO-002.7-PROPOSED-ROADMAP-CORRECTION.md`](MOGO-002.7-PROPOSED-ROADMAP-CORRECTION.md)

**Still NOT APPLIED. `docs/ROADMAP.md` is unmodified.** `CONTRIBUTING.md` scopes documentation
obligations to behaviour-changing releases and grants no standalone documentation-correction
authority. The draft insertion needs one wording update before application — the MOGO-002.7 bullet
should now record that the source *was* ingested and that KEREV-A moved to `PARTIALLY_SUPPORTED`
rather than reporting a stop condition.

## 16. Repository-Stabilization Recommendation

[`MOGO-002.7-REPOSITORY-STABILIZATION.md`](MOGO-002.7-REPOSITORY-STABILIZATION.md)

**Untracked files: 6,674 → 7,875** (+1,201, almost all evidence-store and lifecycle records from this
ingestion). Modified tracked files: still 17. `index.html`: still 113/0.

**The risk got worse, exactly as predicted.** RS-7 said each additional cycle makes the first commit
harder to review. One cycle added 1,201 files. **The raw transcript for `kg-rOo9_xjU` is now the
twelfth irreplaceable artifact in the tree** — and this milestone demonstrated in its own v1 that
re-acquiring a YouTube transcript can fail outright.

**Recommendation unchanged and now more urgent: approve commit boundary C1** (raw source material and
intake manifests). It touches no application code and its integrity is already verified by SHA-256
sidecars.

## 17. Test Results

| Suite | Result |
|---|---|
| `tests/run_all.sh` | **591 / 591 fixtures**, 13 suites, **0 failures** |
| Protected-function / constant drift | **ZERO** — 63 functions, 4 constants byte-identical |
| `tests/strategy_fidelity/` | **63 / 63 pass** |
| **`tests/knowledge_engineering/`** | **55 / 57 pass — 2 NEW failures, see below** |
| `tests.trader_intelligence.*` | 307 tests, **4 failures — pre-existing, unchanged** |
| Provenance re-verification | **452 checks, 0 findings** |
| Evidence / graph integrity | **0 / 0 / 0 / 0** in both |
| MOGO-002.7 report generation | **Byte-identical across two consecutive runs** |

### The 2 new knowledge-engineering failures — obsolete assertions, deliberately not fixed

```
test_all_195_claims_are_inventoried          AssertionError: 226 != 195
test_delta_reports_the_unclosed_risk_gap     AssertionError: 2 != 0
   (asserts delta["riskGap"]["draftStopPlacementRules"] == 0)
```

**Both are the exact pattern `docs/TESTING.md` already warns about** — *"prefer invariants over
emptiness… assert what must remain true rather than what merely happens to be true today."*

The second is the more interesting one. **It encoded a finding rather than an invariant**: it asserted
the risk gap was unclosed *by asserting that zero stop rules exist*. The gap **is** still unclosed —
the buffer is missing — but stop rules now exist, so the test's mechanism is wrong even though its
intent still holds. The invariant it should assert is something like *"any draft stop rule is
non-deterministic while its buffer is unresolved"*, which would pass today.

**Not fixed here.** These are now in the same class as the 4 pre-existing obsolete tests, and the
decision to rewrite or delete them is the Authority's — the same decision open since 2026-07-27.
**No production logic was changed to make any test pass.**

## 18. Known Limitations

1. **The stop rule is not implementable.** Three parameters short (STOP-UNK-1/2/3). The refreshed
   draft marks both stop rules `deterministic: false`.
2. **Zero confidence movement.** All 341 claims `emerging`. Nothing acquired here can be believed
   until D2 is resolved.
3. **One source, one educator.** Three demonstrations in one video are not independent corroboration.
4. **Domain matching remains lexical**, with the `stop_rule` type census as the independent cross-check.
5. **The short side is genuinely unknown**, not merely unstated-but-obvious. Not mirrored by assumption.
6. **The refreshed draft is not adopted** — see §19 and `refresh-002.7/README.md`.
7. **Marketing density is high** — 6 of 31 claims are low-quality performance claims.
8. **Transcript artifacts persist** (*"breaking reetus"*, *"set freet"*, *"Inay"*, *",000"*), recorded
   and never repaired.
9. **One ingestion defect occurred and was corrected** — see §20.

## 19. Engineering Authority Decisions Required

| # | Decision | Recommendation |
|---|---|---|
| **A7-2** | **KEREV-A — now: may MOGO author the stop *buffer*, under an explicit MOGO-authored label, on top of the educator's stated relationship?** Options B and D are withdrawn as unavailable. | **One more narrowly-targeted acquisition (live session with order entry), then option C with explicit labelling.** Record the relationship as the educator's and the buffer as MOGO's — they now have different provenance and must not be collapsed. |
| **A7-8** | **D2 / concept-level consensus.** Now demonstrated three times. | **Decide.** Until then no acquisition can raise confidence, and the stop rule cannot become a candidate rule no matter what else is done. |
| **A7-3** | **Approve commit boundary C1.** | **Approve.** +1,201 untracked files this cycle; a twelfth irreplaceable transcript now sits uncommitted. |
| **A7-10** | **NEW — adopt the refreshed educator draft (127 rules) or keep the 111-rule version?** | **Adopt in the milestone that resolves KEREV-A, not here**, and only together with a fix for the Markdown-reproducibility defect (§20). |
| **A7-4** | **The now-6 obsolete tests** (4 pre-existing + 2 new). | **Rewrite as invariants.** Needed for a green baseline. |
| **A7-11** | **NEW — `XCONTRA\|20260729\|004`: is 1:2 a floor a trade may be set at, or a level a preset target must never be revised down to?** | **Rule on it.** It governs whether a target may change after entry and cannot be settled by more ALEX_G sources — both positions are already his. |
| **A7-5** | Apply the roadmap correction (needs the §15 wording update). | Apply. |
| **A7-6** | `evidence/lifecycle/` retention — now **4,472** records. | Commit as-is; separate retention proposal. |
| **A7-7** | Convention for "educator speech on a third-party channel". | Decide before queue rank 7 is acquired. |
| **A7-9** | Frame-reading method for on-screen parameters. | Defer; needs its own proposal. |

**Still open and untouched:** OD-2…OD-7 (MOGO-002.5); KEREV-B…E and the review queue (MOGO-002.6,
now 67 items in the refreshed set).

## 20. Two defects found in existing tooling, reported not patched

**D-1 — MOGO-002.6's nine Markdown reports are not reproducible.** `build_ke_artifacts.py` writes
**only the twelve JSON artifacts**; it contains no Markdown writer. The nine `.md` reports must have
been produced by a step that was not retained. **Consequence: if the refreshed draft is adopted, those
reports will assert 111 rules while the JSON asserts 127.** They are consistent today only because the
JSON was restored.

**D-2 — the draft's `provenanceNote` is hardcoded** and still reads *"195 claims, 8 source artifacts"*
while describing 226 claims from 9 sources. A one-line fix, not applied because this milestone is not
authorized to change KE generator behaviour.

**D-3 — ⚠️ the knowledge-engineering test suite MUTATES repository artifacts.**
`tests/knowledge_engineering/test_knowledge_engineering.py` calls `build_ke_artifacts.generate_all()`
three times (lines 305, 338, 370), and `generate_all()` writes all twelve JSON artifacts into
`docs/knowledge-engineering/`. **Running the test suite silently rewrites the committed artifact set
from whatever is currently in the evidence store.**

This was found the hard way: MOGO-002.6's artifacts were restored byte-identical, then a routine test
run overwrote ten of them again. They have been restored a second time and re-verified **21/21
byte-identical**.

**Operational consequence the Authority should know:** anyone who runs the KE suite after this
milestone will regenerate the artifacts to the 226-claim state without being told. Until D-3 is fixed
(the suite should write to a temp directory, as the trader-intelligence fixtures already do), **the
KE artifact set cannot be trusted to survive a test run.** This is also a latent hazard for
MOGO-002.6's review: its deliverables can be altered by running its own tests.

**And one defect of this milestone's own making, corrected:** the first ingestion produced a segment 13
whose `endTimestamp` read `0:00` instead of `11:07`, because the file's trailing newline created a
92nd empty line the final section had to cover. Corrected properly rather than disclosed as cosmetic,
because a segment's timestamp range is provenance data. The run was rolled back (323 records), the 120
immutable snapshots the rollback deliberately leaves behind were removed as the tool instructs, **the
evidence store was verified byte-count identical to the pre-milestone baseline**, and the source was
re-ingested. Segment 13 now reads `9:57 → 11:07`.

## 21. Recommended Next Action

**Do not open an engineering implementation milestone.** The stop rule is not implementable and the
library cannot yet believe it.

1. **Decide A7-2 (KEREV-A).** It is now a much smaller question than it was: not *"is there a rule?"*
   but *"may MOGO supply the one missing number, labelled as MOGO's?"*
2. **Decide A7-8 (D2).** Three demonstrations should be enough. Until it is resolved, **every future
   acquisition has the same ceiling this one hit**, and no rule can ever become a candidate.
3. **Approve A7-3 (commit boundary C1).** Independent of every research decision, and the tree grew by
   1,201 files this cycle.
4. **Rule on A7-11**, which no further ALEX_G acquisition can settle.

**Explicitly not recommended:** treating KEREV-A as resolved; promoting any stop rule; reading MOGO's
zone-boundary anchor as corroborated; adopting the refreshed draft before D-1 is fixed; changing any
production behaviour; authorizing replay.

## 22. Artifact Paths

**This package**
```
docs/reports/MOGO-002.7_ENGINEERING_REVIEW.md
```

**Markdown deliverables**
```
docs/knowledge-engineering/MOGO-002.7-BLOCKING-GAP-ACQUISITION-CHECKLIST.md
docs/knowledge-engineering/MOGO-002.7-SOURCE-COVERAGE-REPORT.md          (v2, ingested)
docs/knowledge-engineering/MOGO-002.7-ACQUISITION-QUEUE.md
docs/knowledge-engineering/KEREV-A-STOP-PLACEMENT-EVIDENCE-PACKAGE.md    (v2, post-ingestion)
docs/knowledge-engineering/refresh-002.7/README.md                       (draft refresh + 2 defects)
docs/reports/MOGO-002.7-PROPOSED-ROADMAP-CORRECTION.md
docs/reports/MOGO-002.7-REPOSITORY-STABILIZATION.md
```

**Machine-readable**
```
docs/knowledge-engineering/MOGO-002.7-{blocking-gap-checklist,gap-states,
  kerev-a-stop-placement-evidence,source-coverage-report,acquisition-queue}.json
docs/knowledge-engineering/refresh-002.7/*.json                          (10 regenerated KE artifacts)
```

**Ingested source**
```
docs/trader-intelligence/imports/alex-g/raw/alexg-break-and-retest-26k-12-hours.raw.txt (+ .sha256)
docs/trader-intelligence/imports/alex-g/normalized/…normalized.txt + …normalization-map.json
docs/trader-intelligence/intake/completed/alexg-break-and-retest-26k-12-hours.txt
docs/trader-intelligence/intake/manifests/alexg-break-and-retest-26k-12-hours.ingest.json
docs/trader-intelligence/evidence/  — 1 source, 1 intake, 13 segments, 36 annotations/items/links,
                                       31 claims, 2 contradictions, 27 questions
```

**Source**
```
scripts/knowledge_engineering/build_mogo_002_7_artifacts.py
```

**Verified unmodified**
```
index.html                                              113/0 from MOGO-002.5; untouched here
docs/ROADMAP.md                                         correction proposed, not applied
docs/knowledge-engineering/  (21 MOGO-002.6 artifacts)  restored byte-identical, 21/21
docs/strategy-fidelity/manifests/alex_g_sr_v1.specification.json   13 rules, a0b7641e288c1725
```

---

*MOGO-002.7 complete. **KEREV-A remains OPEN** — stop placement advanced from absent to partially
supported and cannot be closed while the buffer is unstated. No production or paper-trading behaviour
changed; no draft rule promoted; replay unauthorized; nothing committed. Stopping for Engineering
Authority review.*

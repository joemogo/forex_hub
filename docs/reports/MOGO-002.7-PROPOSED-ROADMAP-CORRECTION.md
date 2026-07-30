# MOGO-002.7 — Proposed Roadmap Correction

**Milestone:** MOGO-002.7 Phase 8 · **Date:** 2026-07-29
**Status:** ⚠️ **PROPOSAL ONLY — NOT APPLIED.** `docs/ROADMAP.md` is unmodified.

---

## 1. Authority finding — why this was not applied

The MOGO-002.7 brief permits applying a documentation-only correction *"unless existing governance
clearly authorizes documentation-only correction without review."* **It does not.**

`CONTRIBUTING.md` §"Documentation requirements" scopes every documentation obligation to *"every
release that **changes behavior**"* — release notes, `APP_VERSION_LOG`, `TESTING.md`,
`KNOWN_ISSUES.md`, ADRs. There is **no clause authorizing a standalone documentation-only correction**
to a repository-wide normative document outside a release.

There is a narrower autonomy that does **not** cover this: standing ownership of the Trader
Intelligence workstream permits autonomous work on *that subsystem's* documentation, backlog and
structure. `docs/ROADMAP.md` is a repository-wide statement of project state spanning JVM, ALEX, the
Academy, and the v12.x release track — outside that grant.

**Conclusion: propose, do not apply.** The correction below is ready to apply verbatim on approval.

## 2. The inaccuracy

`docs/ROADMAP.md` (95 lines) describes the project purely in v12.x release-phase terms. It ends at
**Phase 2 — Strategy Expansion**, last touching v12.3.2.

**The MOGO-002.x milestone track appears nowhere in it.** This was independently detected during
MOGO-002.5 as `FIDELITY-DISC-004` — *"'MOGO-002.5' appears nowhere in `docs/ROADMAP.md` or any ADR"* —
and re-confirmed by the MOGO-002.7 bootstrap. Three completed milestones and a fourth in progress are
invisible to the document that is supposed to record where the project has been and what is planned next.

**Consequence:** a reader reconstructing project state from `ROADMAP.md` alone would conclude the
newest work is v12.3.2 strategy expansion, and would not learn that ALEX's specification has a
measured risk-fidelity gap of `0/0`, that a 111-rule educator draft exists, or that replay remains
unauthorized. The bootstrap report for this session had to reconstruct all of that from the review
packages instead.

**Not in scope of this proposal:** the six "Coming Soon" nav items, the Academy's 52 unwritten
modules, and v7.3/v7.4 — all still accurately described.

---

## 3. Proposed insertion

Insert as a new section immediately **after** the `## Release phases` block and **before**
`## Where the project has been`. **No existing line is deleted or reworded.**

---

```markdown
## The MOGO-002.x engineering-governance track

Running alongside the release phases above is a separate track of **engineering-governance
milestones**. These do not ship features and do not bump `APP_VERSION`; they establish what the
repository can truthfully claim about its own strategies. Each ends in an Engineering Review Package
under `docs/reports/` and stops for Engineering Authority review rather than shipping.

- **MOGO-002.5 — Strategy Fidelity Audit: COMPLETE (2026-07-29), awaiting review.** Built an offline
  Python auditor that compares the ALEX paper-trading engine against its own reconstructed
  specification (`RULES_ALEXG.originalAlexConcepts`, 13 rules). Result: **9 of 13 rules MATCH, zero
  are missing, zero differ** — but **risk fidelity and trade-management fidelity are both `0/0`**,
  because the specification contains no risk and no trade-management rules while the engine trades a
  full risk model (`stopATRBuffer 0.25`, `riskPercent 1.0`, `minRR 2.0`, recorded as extra
  implementation rule `ALEX_X_001`). Execution readiness is `NOT_VERIFIED`; profitability is
  `UNVALIDATED` and hard-coded so. Also added per-trade provenance stamping in `index.html`
  (113 insertions, 0 deletions, zero protected-function drift). See
  [`reports/MOGO-002.5_ENGINEERING_REVIEW.md`](reports/MOGO-002.5_ENGINEERING_REVIEW.md).
  **OD-1 was decided (approved with modification); OD-2 through OD-7 remain open.**
- **MOGO-002.6 — Knowledge Engineering & Strategy Normalization: COMPLETE (2026-07-29), awaiting
  review.** Ran the full 195-claim ALEX_G educator library through a new normalization system and
  produced `alex_g_educator_v2_draft` (111 rules), **completely separate from the production
  `alex_g_sr_v1`, which is unchanged**. The honest result is that the draft is larger but not better:
  **only 41 of 111 rules are deterministic and 66 carry a parameter the source never states.** Three
  domains are empty at source — **EXIT, stop placement, and DIRECTIONAL_BIAS**. See
  [`reports/MOGO-002.6_ENGINEERING_REVIEW.md`](reports/MOGO-002.6_ENGINEERING_REVIEW.md).
  **59 review-queue items and 5 structural decisions (KEREV-A…E) remain open.**
- **MOGO-002.7 — Source Acquisition for Blocking Gaps: ACTIVE, awaiting review.** An
  evidence-acquisition and decision-support milestone, not an implementation milestone. Precisely
  defined the ten blocking gaps, confirmed from primary source text that **`ALEX_G` has zero
  `stop_rule` claims across 195 claims and 8 sources**, and compiled the KEREV-A stop-placement
  evidence package. **The one source provided for ingestion could not be ingested** — its
  attribution was verified but its transcript is not obtainable in the current environment, so
  Phase 2 is reported as a disclosed stop condition. See
  [`reports/MOGO-002.7_ENGINEERING_REVIEW.md`](reports/MOGO-002.7_ENGINEERING_REVIEW.md).

**Current blockers across the track:**

1. **Stop placement is absent from the entire ALEX_G educator library** (`KEGAP-001` /
   `GAP-RISK-001`). Position size = risk ÷ stop distance, so none of the 13 draft risk rules is
   implementable and no ALEX_G claim can be replayed for P&L. **KEREV-A is the open decision.**
2. **Exit methodology is absent** (`KEGAP-002`); break-even, partials and scaling have **zero**
   mentions across all 8 sources.
3. **Session hours are shown on screen and never spoken** (`KEGAP-003`) — not closable by more
   transcripts of the same format.
4. **Cross-educator consensus is not countable** (decision **D2**, open since cycle 007). Three
   independent educators now agree on six concepts and **all 310 claims remain `emerging`**, because
   `compute_claim_fingerprint()` is trader-scoped.
5. **Three milestones' artifacts are uncommitted** — see the repository-stabilization recommendation.

**Replay remains deliberately unauthorized.** `replayAuthorization` is `false` on all six
`OwnerDecision` records, and MOGO holds no market data. `POLICY-001` rule 4 establishes that replay
evidence *counts* toward confidence; it does not authorize replay *execution*. Several gaps
(`KEGAP-004`, `GAP-AMBIG-001`, and 10 of 11 open contradictions) are annotated as settleable by
replay and are therefore deliberately parked, not forgotten.

**No MOGO-002.x milestone has changed any trading rule.** Across all three, `index.html` has 113
insertions and 0 deletions, and all 63 protected functions and 4 protected constants remain
byte-identical to the committed baseline.
```

---

## 4. Also proposed — one correction to an existing line

`docs/ROADMAP.md` line 10 currently opens: *"**Phase 1 — Platform Foundation: COMPLETE (v12.0.0 –
v12.1.1).**"* This remains accurate and needs no change.

However the document's framing sentence (lines 3–6) says it is *"a high-level map of where the project
has been and what's explicitly planned next"* and directs readers to `APP_VERSION_LOG` as *"the
verbatim source of record."* **That is no longer sufficient**, because the MOGO-002.x track
deliberately does not write to `APP_VERSION_LOG` (it bumps no version). Proposed addition to the
intro block:

```markdown
> Note: the **MOGO-002.x engineering-governance track** below does not appear in `APP_VERSION_LOG`,
> because those milestones deliberately do not bump `APP_VERSION`. Their source of record is the
> Engineering Review Package for each milestone under `docs/reports/`.
```

## 5. What this proposal deliberately does not do

- **Does not claim any milestone is approved.** All three are recorded as *awaiting review*, which is
  their actual state.
- **Does not present any draft rule as production.** The draft is described as separate and unchanged.
- **Does not restate fidelity numbers as validation.** `0/0` risk fidelity is given with its meaning.
- **Does not mark replay as planned-next.** It is recorded as deliberately unauthorized.
- **Does not touch** `RELEASE_NOTES.md`, `APP_VERSION_LOG`, `KNOWN_ISSUES.md`, or any ADR. If the
  Authority wants `FIDELITY-DISC-004` closed properly, that is an ADR decision (**OD-5**), not a
  roadmap edit.

## 6. Smallest decision required

> **"Apply the MOGO-002.x section to `docs/ROADMAP.md` as drafted (yes / no / with changes)."**

Applying it is a pure insertion: one new section plus one note in the intro block, no deletions and no
rewording of existing content. It can be reverted with a single revert.

---

*MOGO-002.7 Phase 8 complete. `docs/ROADMAP.md` is unmodified and remains inaccurate pending this
decision.*

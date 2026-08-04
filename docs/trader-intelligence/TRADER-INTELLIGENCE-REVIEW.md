# Trader Intelligence Review

**Cadence:** one review per **10 completed transcript ingestions**
(Standing Operating Order, 2026-07-27, item 3).
**Current state:** 10 completed ingestions — **Review #1 written 2026-07-28. Next review due at 20.**
Live counters: [`KNOWLEDGE-DASHBOARD.md`](KNOWLEDGE-DASHBOARD.md) §Review cadence.

> **What this is for.** The dashboard answers *what does MOGO know right now?* — it is regenerated
> after every ingestion and always reflects current state. This review answers a question no
> per-ingestion artifact can: *is the library getting better, and is it getting better at the right
> things?* Ten sources is roughly the point at which corroboration patterns, terminology collisions,
> and genuine cross-strategy structure become visible above the noise of any single source.
>
> A review is written **once** and then appended to `RESEARCH-LOG.md`. It is never edited afterwards;
> a later review may revise an earlier conclusion by citing it.

---

## Template

Copy this structure into a new dated section of `RESEARCH-LOG.md` when the trigger fires.

### 1. Period covered
Ingestions #N–#M · traders · date range · total sources at period end.

### 2. Corpus growth

| Metric | Start | End | Δ |
|---|---|---|---|
| Sources · Claims · Evidence items · Segments | | | |
| Contradictions (open / resolved) | | | |
| Open questions (blocking / total) | | | |
| Knowledge gaps (critical / total) | | | |
| Hypotheses · Rule candidates · StrategyRules | | | |

### 3. Confidence movement — **the core metric**

| State | Start | End | Δ |
|---|---|---|---|
| `emerging` → `supported` → `strongly_supported` … | | | |

**For every claim that moved, state why**, citing the corroborating source or replay result.
Confidence that moved without a *nameable* cause is a defect, not progress — investigate it before
publishing the review.

**Report the ceiling explicitly:** the maximum number of independent groups behind any single
claim. If that is still 1 after ten ingestions, the library has grown in breadth but not in depth,
and that is the single most important finding of the period.

### 4. Corroboration analysis
- Which claims were corroborated by a *second independent* source?
- Which were corroborated only by the *same author*? (Weaker — POLICY-001 §G1.)
- Which were **contradicted** by a new source? Contradictions between educators are the most
  valuable signal in the library — record, never resolve.
- Which claims remain single-source after ten ingestions, and why?

### 5. Cross-strategy findings
Update [`CROSS-STRATEGY-ANALYSIS.md`](CROSS-STRATEGY-ANALYSIS.md). Report new agreements, new
conflicts, newly-unique concepts, and — most valuable — **any concept that three or more independent
educators assert.** That is the closest thing to a validated trading principle the library can
produce without replay.

### 6. Terminology and concept drift
New terms; terminology collisions (same idea, different words); same word used for different ideas.
**If PROPOSAL-003 is still deferred, state explicitly whether that remains correct.** The trigger to
revisit is the first claim that means the same thing as an existing claim but does not
near-duplicate-match it.

### 7. Replay queue health
Candidates added / specified / run / producing evidence. **If zero candidates have been run, say so
plainly and name the blocker** — an unrun replay queue is the single biggest gap between "knowledge"
and "validated knowledge", and it will not close by accumulating more transcripts.

### 8. Pipeline and process
Defects found · manual effort per ingestion (trending?) · playbook or standards gaps · fixtures or
tests needing attention.

### 9. Source quality assessment
Which sources produced the most claims per hour of material? Which produced the most *blocking
questions*? Which produced almost nothing, and should that source type be deprioritized in
acquisition? Feed conclusions back into the priority weight profile.

### 10. Honest negative findings
**Required section — a review with none is under-critical.** What did not work? What was
over-extracted? Which earlier conclusion turned out wrong? Which gap has stayed open for ten
ingestions without anyone acting on it?

### 11. ROI review
The standard six points (see `RESEARCH-LOG.md` convention), assessed across the whole period rather
than one source.

### 12. Recommendations
Ranked, each with a named owner decision if one is required.

---

## Standing questions each review must answer

1. **Did MOGO get measurably smarter, or just bigger?** Claim count is growth; confidence movement
   and corroboration are intelligence. Report both, and do not let the first stand in for the second.
2. **What is the highest-confidence claim in the library, and what would it take to validate it?**
3. **Is any claim ready for a `RuleCandidateProposal`?** If none, name the specific blocker.
4. **What has been learned that applies across *all* strategies**, not just one educator?
5. **What is the library still completely blind to?**

---

## Review history

| # | Date | Period | Headline finding |
|---|---|---|---|
| **1** | 2026-07-28 | Ingestions #1–#10 | **Breadth success, depth failure.** 47 → 264 claims; **zero** confidence-state changes, zero rule candidates, zero replays run. The maximum independent-group count behind any claim is still **1**, so no amount of further transcript ingestion can move a claim to `supported`. The binding constraint stopped being knowledge around ingestion #4 and has been **authorization** ever since. Full text in [`RESEARCH-LOG.md`](RESEARCH-LOG.md). |

**Seven recommendations issued; four need an owner decision** — authorize replay + price data (R1),
pause ALEX_G acquisition (R2), acquire a third educator (R3), revisit `PROPOSAL-003` (R4).

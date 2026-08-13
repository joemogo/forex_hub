# BACKLOG-004 — Human-Assisted Research Ingestion & Decision-Difference Analysis

**Status:** Backlog. **Nothing here is implemented, authorized, designed or scheduled.**
**Recorded:** 2026-08-13, at the MOGO-020 governed answer-intake commit-readiness point.
**Milestone number:** **deliberately not assigned** — see [Placement](#placement).

**Eligible after governed research intake, standardized research-package interface, and
artifact-ingestion governance mature.**

**Scope:** the Trader Intelligence research subsystem only. No item here touches `index.html`, ALEX,
JVM, TJR authority, any protected function, or any trading authority. Recording this requirement
grants no authorization of any kind.

---

## 1. Why this is written down

The capability below was designed in conversation. Conversation is not a durable record. This
document exists so that a future milestone plan, handoff or audit can discover the requirement
**from the repository alone**, without depending on any chat history.

---

## 2. Objective

Allow the owner to contribute trading research **naturally** — the way evidence is actually
encountered — and have it flow into MOGO's existing governed research architecture without repetitive
manual re-entry.

Today every observation the owner makes outside MOGO must be hand-carried into it. That transfer is
the bottleneck, and it is pure overhead: the analysis machinery already exists and is idle
(see `../governance/RESEARCH-ROADMAP.md` §1).

### Candidate inputs

Trade screenshots · chart/setup screenshots · social-media posts · Discord discussions ·
YouTube/video material · educational material · written rules · copied commentary · trade recaps ·
winning and losing examples · reputable educator observations · **cases where a human trader trades
and MOGO does not** · **cases where MOGO identifies a trade and the human does not**.

### Long-term workflow

```
owner discovers evidence
  → external analysis (e.g. ChatGPT)
  → STANDARDIZED STRUCTURED RESEARCH PACKAGE
  → MOGO governed ingestion
  → immutable/raw preservation where practical
  → provenance + hashing
  → indexing + deduplication
  → comparison against existing knowledge
  → hypothesis generation
  → scientific testing
  → validated or rejected finding
  → research library
  → possible FUTURE strategy-development candidate, under normal governance
```

The objective is to eliminate the repetitive manual transfer step — **not** to shorten any of the
governance steps that follow it.

---

## 3. Scientific separation (non-negotiable)

```
OBSERVED FACT  ≠  INTERPRETATION  ≠  HYPOTHESIS  ≠  VALIDATED FINDING  ≠  STRATEGY RULE
```

A screenshot or a trade example is **evidence, not proof**. This mirrors the separation the evidence
store already enforces between `exactExcerpt` (what was said) and `normalizedObservation` (MOGO's
reading), and between a `ContradictionRecord`'s `rationale` (why detected) and `resolution` (what an
operator ruled).

**Research evidence must never automatically modify a frozen strategy.**

Research *ingestion* may eventually be autonomous.
**Strategy *mutation* must not be autonomous.** These are different claims and must never be
conflated because the first was granted.

---

## 4. Decision-Difference Case

A governed record for when decision systems disagree — for example ALEX takes a trade MOGO does not,
or MOGO qualifies a trade ALEX does not appear to take.

**Neither side is assumed correct.** The human is not automatically right, and neither is the
machine. The case exists to make the disagreement *studyable*, not to settle it.

### Reconstruction fields, where evidence permits

instrument · direction · approximate entry · stop · target · timestamp/session · market structure ·
AOIs · relevant candles · available market data · MOGO observations · MOGO Decision Events · frozen
rules satisfied · frozen rules **not** satisfied · what the human trader apparently observed ·
possible discretionary information outside the mechanical specification.

### Candidate research classifications

MOGO correctly rejected · market-data difference · timing difference · observation-continuity
problem · implementation defect · overly restrictive mechanical rule · incomplete methodology
reconstruction · discretionary human behaviour · unknown setup variation · insufficient evidence.

> These are **roadmap/design candidates, not schema enums to implement now.** Committing them to a
> schema before the evidence exists would freeze a vocabulary nobody has tested.

### The dataset this eventually builds

Repeated cases should accumulate into a research dataset able to address:

* what characteristics repeatedly appear in trades MOGO misses;
* whether those characteristics are already represented in the reconstruction;
* whether an existing rule is misunderstood rather than wrong;
* whether the trader uses **reproducible** discretion (as opposed to noise);
* relative performance of missed versus MOGO-qualified setups;
* whether discovered behaviour can become a mechanical hypothesis;
* whether that hypothesis survives historical, out-of-sample **and** forward-paper testing.

---

## 5. General research architecture — not ALEX-specific

This must not be built as an ALEX feature. The architecture should eventually support governed
research from **ALEX, TJR, ICT, CRT, other approved/reputable sources, owner-supplied observations,
and autonomous MOGO research** — all contributing to the **same governed research library**, while
retaining source-specific provenance and **corpus isolation**.

**Do not build separate owner / ChatGPT / MOGO knowledge systems.** Three parallel libraries would
reintroduce exactly the manual reconciliation this capability exists to remove, and would break the
corpus-isolation guarantee the existing evaluators depend on (`candidate_search.resolve_corpus`
refuses an unresolvable or ambiguous corpus rather than guessing).

---

## 6. Standardized research-package interface

A future interface must be able to represent, where applicable:

| Group | Fields |
|---|---|
| Artifact | raw artifact references · screenshots/images · preserved excerpts |
| Identity | source identity/channel · date/time · educator/trader identity · source reliability metadata |
| Attribution | corpus/strategy attribution |
| Content | observed facts · interpretations · hypotheses · uncertainty/confidence |
| Integrity | provenance · hashes · parent/derived relationships |
| Linkage | Decision-Difference Case linkage · experiment linkage · validated-finding linkage · future strategy-version linkage **where separately authorized** |

> **Do not design or implement the complete schema now.** This is a statement of required
> expressiveness, not a specification.

---

## 7. Dependencies

Implementation should wait until the relevant research architecture is mature:

| Dependency | Status at time of writing (2026-08-13) |
|---|---|
| Governed EvidenceItem/Claim handling | ✅ exists |
| EvidenceQuestion architecture | ✅ exists |
| Governed answer/adjudication intake | ✅ **MOGO-020** |
| Contradiction governance | ✅ **MOGO-020** |
| Lifecycle/audit history | ✅ exists, extended by MOGO-020 |
| Provenance / hashing | ✅ exists |
| Corpus isolation | ✅ exists |
| Deterministic reevaluation | ✅ **MOGO-020** |
| Preview / explicit-commit boundary | ✅ **MOGO-020** |
| Artifact-wrapper / research-intake governance | ❌ **not built** |
| Standardized research-package interface | ❌ **not built** |
| Safe machine-to-machine ingestion | ❌ **not built** |
| Deduplication (artifact-level) | ⚠️ partial — claim/URL-level exists; artifact-level does not |
| Source authorization controls | ⚠️ exists, but currently **2 sources, metadata-only** |

### MOGO-020's relationship to this item

> **MOGO-020 provides foundational dependencies but does not implement this future capability.**

MOGO-020 built the governed path for recording a **human decision** about evidence that is *already
in* the library — adjudicating an `EvidenceQuestion`, ruling on a `ContradictionRecord`, recording a
preserved direct-trader clarification — behind a preview/commit boundary. It built **no** ingestion
path for external artifacts, **no** research-package interface, and **no** machine-to-machine intake.

### The Lane B → Lane A finding still stands

Recorded here so it is not rediscovered the hard way. From
`MOGO_019_AUTONOMOUS_RESEARCH_UNDERSTANDING.md` §Step 5:

> Step 4 called the missing link "Lane A ingestion of a Lane B artifact," implying a small adapter.
> The code says otherwise. **Two independent blockers sit in front of that adapter:**
> (a) Lane A requires human extraction judgment **by design** — `ingest.py` refuses a manifest with
> an empty `annotations` list; *"nothing enters the evidence store until a human (or Claude) has
> reviewed the extraction judgments."* **An autonomous Lane B → Lane A loop would have to bypass a
> deliberate governance gate. That is not a missing adapter; it is a designed checkpoint.**
> (b) There is nothing worth bridging under current authorization — metadata-only acquisition yields
> documents with no teaching content and therefore zero extractable claims.

**Human semantic extraction governance remains deliberate.** Any design for this capability must
either preserve that gate or make an explicit, separately-authorized case for changing it. It must
not be quietly dissolved as an implementation detail of "automating ingestion."

---

## 8. ALEX protection

**Decision-Difference research must never silently rewrite the frozen ALEX strategy.**

The only permitted route from a research discovery to a strategy change is, in full and in order:

```
evidence
  → hypothesis
  → candidate mechanical rule
  → operator review
  → specification freeze
  → preregistration
  → historical validation
  → out-of-sample validation where applicable
  → adjudication
  → explicit promotion
  → isolated forward paper campaign
```

**No shortcuts.** This is the discipline `MOGO_012_AUTONOMOUS_OPERATIONS_PLAN.md` already names as
the one most likely to be violated under enthusiasm after a run of losing trades — and a
Decision-Difference case arriving right after a missed winner is exactly that pressure.

The existing protected-drift gate (63 functions, 4 constants, byte-compared on every canonical run)
remains the structural enforcement, but it protects only ALEX's implementation. **The procedural
guarantee above is what protects the specification**, and nothing in this item may weaken it.

---

## 9. Placement

Milestone numbering is **intentionally deferred**. Assigning a number now would imply a sequence
position that the dependency table does not support, and three of its dependencies do not exist.

**Eligible after governed research intake, standardized research-package interface, and
artifact-ingestion governance mature.**

Suggested ordering when it does become eligible:

1. artifact-wrapper / research-intake governance (the missing foundation);
2. standardized research-package interface (schema work, informed by 1);
3. safe machine-to-machine ingestion + artifact-level deduplication;
4. Decision-Difference Case as a governed record type;
5. the accumulated-dataset analyses in §4.

Steps 4–5 are the *point* of the item; steps 1–3 are what make them safe.

---

## 10. What this document does NOT do

* It authorizes nothing.
* It designs no schema.
* It assigns no milestone number.
* It changes no acquisition authorization (still **2 sources, metadata-only**).
* It changes no trading authority — TJR remains **BLOCKED / 17**, paper and live-money remain
  **NOT AUTHORIZED**.
* It does not weaken the human extraction gate.

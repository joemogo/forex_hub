# MOGO-020 — GOVERNED RESEARCH ANSWER INTAKE

## Step 1 — Read-Only Readiness Audit

**Status:** AUDIT COMPLETE · NO IMPLEMENTATION · NO PRODUCTION MUTATION
**Date:** 2026-08-13
**HEAD:** `1c4292e6ddf8eedca82284bb2ed34e7b73ab427d`
**Scope:** read-only inspection of existing architecture. No source, test, schema or Knowledge
Library data file was modified. No EvidenceQuestion answered. No contradiction resolved.

---

## 0. STARTING-STATE VERIFICATION

Every item below was verified from repository evidence, not from the MOGO-019 report's own claims.

### 0.1 Repository and git state

| Check | Expected | Observed | Verdict |
|---|---|---|---|
| Repository | MOGO / Forex Hub | `https://github.com/joemogo/forex_hub.git` | ✅ |
| Branch | `main` | `main` | ✅ |
| HEAD | `1c4292e` | `1c4292e6ddf8eedca82284bb2ed34e7b73ab427d` | ✅ |
| HEAD subject | MOGO-019 closeout | `MOGO-019 COMPLETE -- GREEN` | ✅ |
| Tag `mogo-019-complete` exists | yes | yes (annotated tag object `6e17b03…`) | ✅ |
| Tag targets HEAD | yes | `mogo-019-complete^{commit}` = `1c4292e…` | ✅ |
| Upstream | `origin/mogo-main` | `origin/mogo-main` | ✅ |
| Ahead / behind | 0 / 0 | `0  0` | ✅ |
| Untracked residue | only the IG report | only `MOGO-019-ALEX-IG-CASE-002-REPORT.md` | ✅ |

`git rev-parse mogo-019-complete` returns `6e17b030ac2b8c6c9dc31c0a77bf26c871204b25`, which is **not**
a mismatch: `mogo-019-complete` is an *annotated* tag, so that SHA is the tag object.
`git cat-file -t` reports `tag`, and `mogo-019-complete^{commit}` dereferences to `1c4292e…`.
`git tag --points-at HEAD` independently lists it. The tag targets HEAD correctly.

### 0.2 Authoritative baseline

| Baseline | Expected | Observed | Verdict |
|---|---|---|---|
| Focused MOGO-019 | 222 / 222 | **222 / 222, OK** | ✅ |
| Platform suite | 1,049 / 1,049 | **25 suites · 1,049 / 1,049 · 0 fail · 0 error** | ✅ |
| Canonical gate | 1,160 / 1,160 | **19 suites · 1,160 / 1,160 · 0 fail** | ✅ |
| Protected ALEX drift | 0 | **0** — 63 functions, 4 constants byte-identical | ✅ |
| Runtime integrity | INTEGRITY OK | `{INFO:0, WARNING:0, ERROR:0, FATAL:0}` | ✅ |
| EvidenceQuestions answered | 0 / 281 | **281 files; 0 with `answerStatus: answered`** (see §0.3c) | ✅ |
| EvidenceLinks | 416 | **416** | ✅ |
| RuleCandidateProposal records | 0 | **0** (`proposals/` empty) | ✅ |
| TJR eligibility | BLOCKED / 17 | `result=BLOCKED  blockers=17` | ✅ |
| `XCONTRA\|20260728\|001` | OPEN / BLOCKING / UNRESOLVED | `status: open`, `severity: blocking`, `resolution: null`, `reviewedAt: null` | ✅ |
| Research authorization | 2 sources, metadata-only | 2 records with `permittedOperations: ["metadata"]` (fxalexg, TJR) | ✅ |
| ALEX forward activation cutoff | `2026-08-11T02:43:57.894Z` | present and unchanged | ✅ |

Supporting Knowledge Library counts: claims 341 · items 416 · sources 12 · gaps 110 ·
lifecycle events 4,472 · annotations 416 · review-queue 325 · segments 197 · hypotheses 641 ·
contradictions 16 · profiles 11 · blueprints 11.

Campaign C1 fixtures (33 harvest/packages/rejected triples) are present and the canonical gate that
covers them passes 1,160/1,160. TJR paper trading and live-money trading remain NOT AUTHORIZED —
no authorization record grants either, and eligibility remains BLOCKED.

**Baseline verdict: MATCHES. No unexplained drift. No rebaselining performed.**

### 0.3 Two observations that do NOT change the baseline (reported, not repaired)

**(a) Pre-existing stale snapshot test outside all three declared gates.**
`tests/trader_intelligence/test_graph.py::TestRealProductionBuild::test_expected_node_and_edge_counts`
fails at HEAD: it asserts `counts["TRADER"] == 3`, but the repository now holds **5** traders
(`alex-g`, `ict`, `jvm`, `rayner-teo`, `tjr`).

This is **not** a regression and **not** a MOGO-019 defect:

* the file is unmodified at HEAD (last touched at `9903297`, long before MOGO-019);
* it is in **none** of the three declared gates — not `tests/run_all.sh` (JS-only glob), not
  `tests/run_platform_tests.sh`, not the focused MOGO-019 222;
* the substantive graph checks in the same class **pass** —
  `test_clean_build_zero_blocking_findings` reports 0 ERROR / 0 FATAL against real data.

It is a hardcoded count snapshot that later milestones (which legitimately added traders) outgrew.
The declared MOGO-019 baseline is unaffected and remains GREEN as stated. **Left untouched** —
repairing it is out of scope for a read-only audit and is not a MOGO-020 dependency. Flagged for
operator awareness only.

**(c) One EvidenceQuestion is already in a partially-answered, evidence-less state.**

The baseline claim "**0 / 281 answered**" is **correct** — no record carries
`answerStatus: "answered"`. But the full distribution is:

```
answerStatus:   {unanswered: 280, partially_answered: 1}
researchStatus: {open: 281}
resolvedAt set: 0
answerEvidenceIds populated: 0
```

`EQ|20260727|015` carries **`answerStatus: "partially_answered"` with an empty
`answerEvidenceIds`**, `researchStatus: "open"` and `resolvedAt: null`. Its `reason` field has a
second sentence appended after the original (`"| 2026-07-27: canonicalReference resolved; title
still unresolved…"`).

The file is committed at `c03f35e` ("Trader Intelligence evidence corpus and Knowledge Graph
rebuild"), is **unmodified at HEAD**, and was **not touched by this audit**. Since no code can write
`answerStatus` (§1.1), this state can only have arrived by **direct hand-editing of the JSON**.

Two consequences for MOGO-020, both material:

1. **It proves the ungoverned edit path is real.** Answer state has already been changed once
   outside any audited function, with no lifecycle event and no `actor`. This is precisely the
   behaviour MOGO-020 exists to replace.
2. **It is exactly the inconsistent state §11 must reject.** A question claiming partial answering
   while citing *no* answer evidence is unverifiable. The fail-closed rule
   "`partially_answered`/`answered` requires non-empty `answerEvidenceIds`" would refuse to create
   this record today.

**Left untouched** — repairing it is a production data mutation and is explicitly out of scope for
Step 1. It should be an explicit operator decision in a later step: either supply the answering
evidence, or revert it to `unanswered`. **Flagged, not repaired.**

**(b) `validate_evidence.py` is not read-only.**
Running it to verify integrity rewrote the tracked file
`docs/trader-intelligence/evidence/reports/integrity-report.json`. The diff was confined to
`generatedAt` and `integrityReportId`; `findings: []` and the summary were byte-identical.
**The file was reverted with `git checkout --`; the working tree is clean.** This matters for
MOGO-020: the integrity validator must be treated as a *writer*, not a probe, in any future
verification harness.

---

## 1. EvidenceQuestion MODEL

**Authoritative schema:** `docs/trader-intelligence/evidence/schema/evidence-question.schema.json`
**Constructor:** `scripts/trader_intelligence/evidence_questions.py::create_question()`
**Vocabularies:** `scripts/trader_intelligence/evidence_common.py` (lines 114–125)

| Field | Type | Notes |
|---|---|---|
| `questionId` | `^EQ\|\d{8}\|\d{3,}$` | Deterministic, date-sequenced via `next_question_id()` |
| `claimId` | `CLAIM\|…` or null | Corpus attribution path #1 |
| `evidenceIds` | `[EV\|…]` | Evidence the question was raised *from* |
| `sourceIds` | `[EVSRC\|…]` | Corpus attribution path #2 |
| `questionType` | 17-value enum | Drives Step 4 routing |
| `questionText`, `reason` | string | `reason` traces the structural trigger |
| `priority` | low/medium/high/critical | |
| `blockingStatus` | non_blocking / blocks_rule_candidate / blocks_promotion | |
| `researchStatus` | **open / researching / answered / deferred** | |
| `answerStatus` | **unanswered / partially_answered / answered** | |
| `answerEvidenceIds` | `[EV\|…]` | **Exists. Empty on all 281 records.** |
| `createdAt` / `resolvedAt` | date-time / nullable | |
| `schemaVersion` | integer ≥ 1 | |

**Identity:** `EQ|{YYYYMMDD}|{seq}`, sequence derived by scanning existing filenames
(`_next_seq`). Filenames are literal (`id.replace("|","_") + ".json"`), never hash-derived.

**Persistence:** flat JSON files under `evidence/questions/`, written through
`graph_common.atomic_write_text()` (write-temp → `fsync` → `os.replace`) and
`graph_common.pretty_json()` (sorted keys, 2-space indent, single trailing newline).
Crash-safe and git-diff-friendly.

**Validation:** hand-written Python enum membership checks in `create_question()`. The JSON Schema
files are **contract documentation, not runtime enforcement** — no `jsonschema` library is imported
anywhere in the pipeline. `additionalProperties: false` is therefore *not* machine-enforced at write
time, but it **is** the reviewed contract and must be honoured.

### 1.1 Does the architecture already support governed answer intake?

**Partially — the data model does; the write path does not.**

* ✅ `answerStatus`, `answerEvidenceIds`, `researchStatus`, `resolvedAt` **already exist** and are
  already read by consumers (`candidate_search.py` refuses answered questions;
  `research_understanding.py` filters on them; `review_queues.py` queues open ones).
* ❌ **No code anywhere writes them.** `create_question()` hardcodes
  `researchStatus="open", answerStatus="unanswered", answerEvidenceIds=[]` and there is **no update
  function**. A repository-wide search for writers of these fields returns only the constructor.

**EvidenceQuestion is currently create-only.** This is the single largest finding of the audit, and
it is good news: the *fields* MOGO-020 needs are already designed, reviewed and consumed. What is
missing is one governed transition function — not a schema, not a store, not a model.

**REUSE VERDICT: reuse the EvidenceQuestion record. Do not build an answer database.**

---

## 2. EXISTING ANSWER / ADJUDICATION TOOLING

| Capability | Exists? | Where |
|---|---|---|
| Accepted evidence | ⚠️ partial | `ReviewQueueEntry.reviewAction ∈ {approve_as_supported_claim, approve_as_inferred_claim}` — approves an *entity*, not an *answer to a question* |
| Rejected evidence | ⚠️ partial | `reviewAction = reject` → `reviewStatus = dismissed` |
| Uncertain / needs more | ✅ | `reviewAction = request_more_evidence` → stays `in_review`; also `leave_unresolved` |
| Reviewed claims | ✅ | `ReviewQueueEntry` + `EvidenceLifecycleEvent(eventType="reviewed")` |
| Human adjudication | ✅ | `review_queues.apply_review_action()` — 8 closed-enum actions, mandatory `reviewer` |
| Operator decisions | ✅ | `OwnerDecision` graph records; `authorizations/*.json` with `decisionAuthority` |
| Answer acceptance | ❌ | **Nothing links an accepted answer to an EvidenceQuestion** |
| Evidence linkage | ✅ | `EvidenceClaimLink` + `evidence_registry.link_evidence_to_claim()` |
| Review status | ✅ | `reviewStatus ∈ {open, in_review, resolved, dismissed}` |
| Resolution rationale | ✅ | `reviewNotes`, `resolution`, `ContradictionRecord.rationale` |

### 2.1 The closest existing mechanism — and why it is the right one to copy

`review_queues.apply_review_action()` (`review_queues.py:235`) already implements, in production,
the exact invariant MOGO-020 must preserve. Its docstring states it outright:

> "resolving an entry only ever changes the entry itself — it never mutates the Claim, EvidenceItem,
> or other entity the entry points at, and it never runs without an explicit human `reviewer`."

It also refuses to act on an already-settled entry (`resolved`/`dismissed`) and demands an explicit
reopen first — a working illegal-transition guard. And `propose_hypothesis` deliberately does *not*
auto-create a Hypothesis, because a hypothesis must be derived from the full claim set rather than
fabricated from one entry.

**This is the template for MOGO-020's ruling path.** It is the strongest reuse candidate in the
repository.

### 2.2 CANDIDATE EVIDENCE ≠ ACCEPTED ANSWER — already enforced

`candidate_search.py` is explicit and correct. Every result it emits is stamped
`CANDIDATE_ONLY` / `NOT_ANSWERED` / `NOT_ADJUDICATED`, and its module docstring draws the exact line:

> ANSWERS: "What governed evidence should a human review for this unanswered question?"
> DOES NOT: "Does this evidence resolve the question?"

Ranking is tiered by **governed relationship first** (`EXPLICITLY_RELATED` →
`SUPPORTS_RELATED_CLAIM` → `SAME_RULE_CATEGORY`), with lexical overlap last and no opaque score.
**Retrieval is nomination. This audit treats it as nomination and nothing more.**

---

## 3. ContradictionRecord

**Schema:** `docs/trader-intelligence/evidence/schema/contradiction-record.schema.json`
**Constructor:** `evidence_registry.py::create_contradiction()` (line 310)

| Field | Values / notes |
|---|---|
| `contradictionId` | `XCONTRA\|{YYYYMMDD}\|{seq}` |
| `claimAId`, `claimBId` | Both must exist; must differ (enforced) |
| `contradictionType` | DEFINITIONAL, NUMERIC_THRESHOLD, CONDITIONAL_SCOPE, TEMPORAL_DRIFT, DIRECTIONAL, SCOPE_MISMATCH, OTHER |
| `scopeOverlap` | **full / partial / none / unknown** |
| `severity` | cosmetic / minor / **material** / **blocking** |
| `status` | **open / resolved_by_owner / superseded / accepted_as_context_dependent** |
| `rationale` | nullable free text (detection-time reasoning) |
| `resolution` | nullable free text (**resolution-time** ruling) |
| `detectedAt` / `reviewedAt` | date-time / nullable |
| `metadata` | **open object** (`additionalProperties: true`) |

**Blocking semantics:** `severity: blocking` + `status: open` is what
`research_understanding.py` counts as a reconstruction blocker. A record stops blocking when its
**status** leaves `open` — severity need not change. This is the key lever.

**Scope semantics:** `scopeOverlap` already encodes `partial` — the field needed to narrow a
contradiction's scope rather than erase it. Cross-corpus contradictions are detected and, per Step 2
output, the **foreign claim is explicitly NOT expanded into the local corpus**.

**Mutation paths:** create-only. `create_contradiction()` writes `status: "open"` and emits a
`created` lifecycle event. **No code transitions status, sets `resolution`, or stamps `reviewedAt`.**
`query_graph.py:154` reads `status != "resolved_by_owner"` — a consumer waiting for a writer that
does not exist.

### 3.1 How an operator ruling could be represented (design space only)

All five outcomes the milestone names are **already expressible in the existing schema**:

| Operator intent | Representation | New fields? |
|---|---|---|
| Resolves it | `status → resolved_by_owner` + `resolution` + `reviewedAt` | none |
| Partially qualifies | `status → accepted_as_context_dependent` + `resolution` | none |
| Narrows scope | `scopeOverlap → partial` + `resolution` | none |
| Leaves open | `status` stays `open`; ruling recorded in lifecycle only | none |
| Makes non-blocking | `status → accepted_as_context_dependent` (stops blocking without touching `severity`) | none |

In every case `claimAId` and `claimBId` are untouched, and both underlying Claims remain
byte-identical. ADR-008 §8 already mandates this: *"Never resolved by deleting or overwriting either
claim."*

**`XCONTRA|20260728|001` was read only. It remains `open` / `blocking` / `resolution: null` /
`reviewedAt: null`. Nothing was resolved.**

---

## 4. PROVENANCE AND IDENTITY SUPPORT

| Requirement | Existing home | Machine or human? |
|---|---|---|
| Reviewer identity | `ReviewQueueEntry.reviewer` | **human** |
| Operator identity | `EvidenceLifecycleEvent.actor`; `authorizations[].decisionAuthority` (`operator:joemogollon`) | **human** |
| Trader/educator identity | `EvidenceSource.traderId` (`^[A-Z][A-Z0-9_]*$`); `EvidenceItem.speaker` | human at registration |
| Source identity | `EvidenceSource.sourceId`, `canonicalReference`, `externalReference` | human |
| Exact preserved source | **`EvidenceItem.exactExcerpt`** — "verbatim… never MOGO's interpretation" | **human** |
| MOGO's reading | `EvidenceItem.normalizedObservation` — deliberately a separate field | machine/human |
| Source channel | `EvidenceSource.externalReference` / `canonicalReference`; `metadata` | human |
| Source date/time | `EvidenceSource.sourceDate`, `acquiredAt`; `EvidenceItem.observationDate`, `start/endTimestamp` | human |
| Question asked | `EvidenceQuestion.questionText` | machine (deterministic) |
| Directness (`direct_explicit`) | **`EvidenceItem.directness`** — 7-value enum incl. `direct_explicit` | **human** |
| Extraction certainty | `EvidenceItem.extractionCertainty` | human |
| Corpus attribution | `EvidenceSource.traderId` → resolved by `candidate_search.resolve_corpus()` | machine, from governed IDs |
| Scope qualifiers | `timeframe`, `session`, `marketCondition`, `marketSymbol`, `direction` | human |
| Evidence hashes | `EvidenceItem.contentHash`, `EvidenceSource.contentHash` (`^[a-f0-9]{64}$`) | machine |
| Provenance verification | `EvidenceSource.provenanceStatus ∈ {unverified, partially_verified, verified}` | human |
| Licensing | `licensingStatus` 5-value enum | human |

**Every provenance field MOGO-020 needs already exists.** The separation the milestone demands is
already load-bearing architecture:

* `exactExcerpt` (what was said) vs `normalizedObservation` (what MOGO thinks it means);
* `directness` (how explicit) vs `evidenceQuality` (how strong) vs `extractionCertainty`
  (how sure we read it right) — three fields the schema comments explicitly forbid conflating;
* `rationale` (why detected) vs `resolution` (what was ruled).

**SOURCE FACT ≠ OPERATOR RULING is already expressible. MOGO-020 must not blur it.**

---

## 5. GRAPH / LINK UPDATE MECHANISMS

**Authoritative function:** `evidence_registry.link_evidence_to_claim()` (line 239).

Validations performed:

* `evidenceId` must exist in `items/` — else `EvidenceValidationError`;
* `claimId` must exist in `claims/` — else `EvidenceValidationError`;
* `relationshipType` ∈ 8-value enum;
* `relevanceWeight` ∈ [0,1].

`linkId = LINK|{evidenceId}|{claimId}` via `make_link_id()`, hash-truncated past 200 chars.
Deterministic, so re-linking the same pair **overwrites the same file** — file-level idempotency is
inherent.

### 5.1 Three hazards MOGO-020 must not inherit

1. **No corpus isolation on links.** `link_evidence_to_claim()` does **not** compare the evidence
   item's `sourceId → traderId` against the claim's `traderId`. Nothing today prevents linking a TJR
   evidence item to an ALEX_G claim. **This is the foreign-corpus hole**, and if MOGO-020 ever
   creates links it must close it at its own call site.
2. **Linking automatically mutates the claim.** The call ends with
   `recompute_claim_confidence()`, which **rewrites the Claim file**
   (`confidenceState`, `confidenceScore`, counts, `lastEvaluatedAt`, `updatedAt`), **rewrites every
   sibling link** (to persist `independenceGroup`), and appends a `confidence_recomputed` lifecycle
   event. Linking is *not* an inert act.
3. **Idempotency is only partial.** A repeated identical link overwrites one file cleanly, but still
   appends a **new** lifecycle event and re-runs confidence recomputation.

### 5.2 Corpus isolation that already works

`candidate_search.resolve_corpus()` is the correct, fail-closed model and is directly reusable:

* resolves the trader from **governed identifiers only** — the question's `claimId`, then its
  `sourceIds` — *never* from words in the question text;
* **0 traders → refuse** ("refusing to search a corpus that cannot be identified");
* **>1 traders → refuse** ("ambiguous corpus attribution is refused rather than resolved by picking
  one");
* results are then intersected with the corpus (`explicit &= set(corpus_items)` — "never leave the
  corpus").

**No substring matching may enter MOGO-020.** Retrieval tokenisation in `candidate_search.py` is
whole-token, stop-listed and corpus-relative; it exists for *ranking*, never for identity. Identity
resolution is by exact governed ID everywhere, and must stay that way.

---

## 6. HISTORY / IMMUTABILITY / IDEMPOTENCY

| Mechanism | Where | Reusable for MOGO-020? |
|---|---|---|
| Append-only audit events | `EvidenceLifecycleEvent` + `build_lifecycle_event()` / `write_lifecycle_event()` | ✅ **yes — with one extension** |
| Prior-state / new-state | `priorStatus` / `newStatus` on every event | ✅ yes |
| Actor attribution | `actor` (required) | ✅ yes |
| Free-text reason | `reason` | ✅ yes |
| Open metadata | `metadata` (`additionalProperties: true`) | ✅ yes |
| Immutable evidence | `EvidenceItem` never edited; corrections create a new item with `supersedesEvidenceId` | ✅ yes |
| Supersession | `correct_evidence_item()` + `_mark_evidence_superseded()` | ✅ yes |
| Atomic writes | `atomic_write_text()` — temp → fsync → rename | ✅ yes |
| Content hashing | `sha256_hex`, `content_hash_of`, `file_hash`, `canonical_json_bytes` | ✅ yes |
| Duplicate detection | `compute_claim_fingerprint()` (scope-aware), `near_duplicate_ratio()` | ✅ yes |
| Deterministic serialisation | `pretty_json()` — sorted keys, stable diffs | ✅ yes |
| Rollback | ❌ none beyond git | n/a |
| Transactions | ❌ none — multi-file writes are not atomic as a group | ⚠️ **gap** |

**4,472 lifecycle events** exist, so this machinery is proven at scale.

### 6.1 The one extension needed

`EvidenceLifecycleEvent.entityType` does **not** include `EVIDENCE_QUESTION`:

* schema enum: `EVIDENCE_SOURCE, EVIDENCE_ITEM, CLAIM, EVIDENCE_CLAIM_LINK, CONTRADICTION_RECORD`;
* `eventId` pattern hardcodes the same five;
* `evidence_common.LIFECYCLE_ENTITY_TYPES` has a **sixth**, `INTAKE_MANIFEST`, **which the schema
  never received.**

That last point is **pre-existing code/schema drift**, unrelated to MOGO-020 but directly in its
path: adding `EVIDENCE_QUESTION` to the Python constant alone would repeat the same mistake. Both
the `enum` **and** the `eventId` `pattern` must be updated together, and the existing
`INTAKE_MANIFEST` omission should be corrected in the same edit.

`build_lifecycle_event()` already guards `entityType`/`eventType` against the Python constants and
raises `EvidenceValidationError` on anything unknown — so the fail-closed check is already written.

`eventType` needs **no** new values: `reviewed`, `status_changed` and `linked` cover answer
acceptance, rejection and contradiction rulings.

---

## 7. DIRECT-TRADER CLARIFICATION SUPPORT

**Smallest governed path — reusing existing objects only:**

1. **`EvidenceSource`** — `sourceType: "note"` (or `other`), `traderId` = the educator,
   `sourceDate` = when the answer was given, `externalReference`/`canonicalReference` = the channel
   (DM, email, live stream, reply), `provenanceStatus`, `licensingStatus`, `contentHash`.
2. **`EvidenceItem`** — `exactExcerpt` = the educator's verbatim words; `speaker` = the educator;
   `directness: "direct_explicit"`; `extractionCertainty`; `observationDate`;
   `extractionMethod: "manual_owner_entry"`; `sourceLocator` = where in the exchange;
   `normalizedObservation` = MOGO's reading, kept separate.
3. **The question asked** — `EvidenceQuestion.questionText` already holds it; the link back is the
   EQ id, and `EvidenceItem.metadata` can carry `answersQuestionId` for a forward reference.
4. **Scope** — `timeframe`, `session`, `marketCondition`, `marketSymbol` on the item.
5. **Corpus** — enforced by `traderId` on the source, resolved through `resolve_corpus()`.

**No new schema is required for direct-trader clarification.** `EvidenceSource` already anticipates
non-document producers, and `sourceType` is documented as an extensible list.

### 7.1 The critical invariant

> **FREE-FORM TEXT ALONE MUST NOT BECOME AUTHORITATIVE DIRECT-TRADER EVIDENCE.**

The eventual intake path must **fail closed** when preserved source material is absent. Concretely,
`directness: "direct_explicit"` must be **refused** unless *all* of the following hold:

* `exactExcerpt` is non-empty (verbatim, not a paraphrase);
* an `EvidenceSource` exists with a non-null `traderId` **and** a channel reference;
* `sourceDate` / `observationDate` is present;
* `contentHash` is computed over the preserved material;
* `extractionMethod` is a manual, human-attributed value.

A typed-in sentence with no preserved artifact must land at
`indirect_implied` / `owner_observation` at best — **never** `direct_explicit`.

**Note:** Step 4 routes **6 EvidenceQuestions** to `DIRECT_TRADER_CLARIFICATION`
(`autonomy = HUMAN_INPUT_REQUIRED`), including `EQ|20260727|004`, `009`, `016`, `018`.
**None were sent. None will be sent by MOGO.** Routing is a recommendation, not an authorization —
`research_understanding.py` says so in its own output.

---

## 8. OPERATOR-RULING SUPPORT

| Requirement | Existing home | Status |
|---|---|---|
| Operator identity | `EvidenceLifecycleEvent.actor`; `ReviewQueueEntry.reviewer`; `decisionAuthority` | ✅ |
| Decision | `ReviewQueueEntry.reviewAction` (closed enum); `ContradictionRecord.status` | ✅ |
| Rationale | `reviewNotes`; `ContradictionRecord.resolution`; `event.reason` | ✅ |
| Target object | `entityType` + `entityId` on both event and queue entry | ✅ |
| Prior state | `event.priorStatus` | ✅ |
| Resulting state | `event.newStatus` | ✅ |
| Timestamp | `event.timestamp`; `reviewedAt`; `updatedAt` | ✅ |
| Provenance | `metadata` (open object) | ✅ |
| Immutable history | append-only `lifecycle/` | ✅ |

**Everything required to record an operator ruling already exists.** The gap is not
representational — it is that **no writer targets `EvidenceQuestion`, and no writer transitions
`ContradictionRecord.status`.**

The correct shape, following `apply_review_action()`'s precedent: an operator ruling is recorded on
the **question / contradiction / queue entry**, plus an append-only lifecycle event. It must
**never** be encoded by editing a Claim's `normalizedClaim` or an EvidenceItem's `exactExcerpt`.
Educator/source claims stay byte-identical. ADR-008 §8 already requires this.

---

## 9. REEVALUATION PATH

The existing deterministic, read-only pipeline (`scripts/trader_intelligence/`):

| Step | Entry point | Behaviour |
|---|---|---|
| Step 2 — research understanding | `research_understanding.py --trader X` | Organises existing research. Writes nothing. |
| Step 3 — reconstruction eligibility | `research_understanding.py --eligibility` | `BLOCKED / 17`. "Authorizes no reconstruction, no specification freeze, no backtest, no paper trading and no live trading." |
| Step 4 — research routing | `research_understanding.py --plan` | Routes each blocker to one of 6 actions. "A recommendation is NOT an authorization." |
| Steps 10/11 — candidate search | `candidate_search.py 'EQ\|…' [--claims]` | `CANDIDATE_ONLY` / `NOT_ANSWERED` / `NOT_ADJUDICATED`. |

**Smallest reevaluation mechanism:** all four are **already pure recomputations over current
state**. They read the Knowledge Library fresh on every invocation and cache nothing. Therefore an
accepted answer that updates `answerStatus` / `answerEvidenceIds`, or a contradiction status
transition, is **automatically reflected the next time any of them runs.**

> **MOGO-020 needs no new reevaluation engine. It needs to re-run the existing read-only commands
> and report the delta.**

### 9.1 The one live hazard — `run_post_annotation_pipeline()`

`extraction_pipeline.py:103` `run_post_annotation_pipeline()` **auto-creates
RuleCandidateProposal records**:

```python
if claim["claimType"] in evc.RULE_CANDIDATE_ELIGIBLE_CLAIM_TYPES and \
        claim["confidenceState"] in ("supported", "strongly_supported"):
    ...
    proposal = rcp.propose_rule_candidate(...)
```

This is the milestone's named prohibition, sitting in live code. The danger is a chain:

> accept answer → create `supports` link → `link_evidence_to_claim()` → `recompute_claim_confidence()`
> → `confidenceState` rises to `supported` → **if `run_post_annotation_pipeline()` is then invoked,
> a RuleCandidateProposal is created automatically.**

The path is currently dormant (0 proposals; reachable only via `ingest.py`, which is gated behind
human annotation by design). **MOGO-020 must not call `run_post_annotation_pipeline()`, directly or
transitively.** This is the single most important fail-closed boundary in the milestone.

Reevaluation must remain informational and must **not** create a RuleCandidateProposal, freeze a
strategy, start backtesting, authorize paper trading, execute a paper trade, or change live-money
authority.

---

## 10. MINIMUM SAFE STATE-TRANSITION MODEL

Built from **existing** statuses. **No new status values are proposed** — the milestone's example
vocabulary (`accepted` / `rejected` / `uncertain`) maps cleanly onto fields that already exist.

### 10.1 EvidenceQuestion

Current states: `researchStatus ∈ {open, researching, answered, deferred}` ×
`answerStatus ∈ {unanswered, partially_answered, answered}`.

| Human decision | `answerStatus` | `researchStatus` | `answerEvidenceIds` | `resolvedAt` |
|---|---|---|---|---|
| **Accepted** — this evidence answers it | `answered` | `answered` | += accepted `EV\|…` | set |
| **Rejected** — does not answer it | unchanged (`unanswered`) | unchanged | unchanged | null |
| **Uncertain** — partial / needs more | `partially_answered` | `researching` | += `EV\|…` | null |

**Missing semantics (the only real gap):** a *rejection* has nowhere to live on the record — by
design, since rejecting a candidate must not alter the question's answer state. It belongs in the
**append-only lifecycle event** (`eventType: "reviewed"`, `newStatus: "rejected_candidate"`,
`metadata.evidenceId`), so the audit trail captures it without corrupting question state.

**Legal transitions**

* `unanswered → partially_answered` (accept partial)
* `unanswered → answered` (accept full)
* `partially_answered → answered` (accept completing evidence)
* `open → researching → answered`; `open → deferred`

**Illegal transitions (must fail closed)**

* `answered → unanswered` (no silent un-answering; requires explicit supersession)
* any transition without a human `actor`
* any transition citing an `EV|…` outside the question's resolved corpus
* any transition on a nonexistent `questionId`
* `answered` **or `partially_answered`** with an empty `answerEvidenceIds` — the exact
  inconsistency `EQ|20260727|015` exhibits today (§0.3c)
* machine-authored acceptance (`actor` must be a human operator, never `pipeline`)

**Required provenance per transition:** `actor` (human), `reason`/rationale, target `questionId`,
`priorStatus`, `newStatus`, `timestamp`, and the accepted `evidenceIds`.

**Duplicate / idempotent behaviour:** re-accepting an already-accepted `EV|…` for the same question
must be a **no-op returning the existing state**, not a second append and not an error. Accepting a
*different* `EV|…` for an already-`answered` question is a **conflict** → fail closed unless the
operator explicitly supersedes.

### 10.2 ContradictionRecord

| Human ruling | `status` | Other fields |
|---|---|---|
| Resolved | `resolved_by_owner` | `resolution`, `reviewedAt` |
| Context-dependent / non-blocking | `accepted_as_context_dependent` | `resolution`, `reviewedAt` |
| Scope narrowed | (status per above) | `scopeOverlap → partial` |
| Superseded | `superseded` | `resolution` |
| Left open | `open` (unchanged) | lifecycle event only |

**Illegal:** any transition away from `open` without an operator `actor` **and** a non-empty
`resolution`; any edit to `claimAId`/`claimBId`; any edit to either underlying Claim.

**In all cases both source claims remain byte-identical.**

### 10.3 The invariant that governs the whole model

**The semantic decision is HUMAN-SUPPLIED.** No machine ranking, token overlap, tier or score may
set `answerStatus`. `candidate_search.py` nominates; a human adjudicates; MOGO records.

---

## 11. FAIL-CLOSED REQUIREMENTS

The eventual implementation must **reject**, never repair:

| # | Condition | Detection |
|---|---|---|
| 1 | Invalid / nonexistent `questionId` | `questionId not in idx.questions` → refuse |
| 2 | Missing evidence (`EV\|…` not in `items/`) | existence check, as `link_evidence_to_claim()` does |
| 3 | Wrong trader / foreign corpus | `resolve_corpus()` vs the item's `sourceId → traderId` |
| 4 | Incomplete provenance | required-field check before any write |
| 5 | Ambiguous source identity | `resolve_corpus()` raises on 0 or >1 traders |
| 6 | Direct-trader answer without preserved source | `directness=direct_explicit` ∧ empty `exactExcerpt` → refuse (§7.1) |
| 7 | Operator ruling without explicit decision | `actor` missing/non-human, or empty rationale → refuse |
| 8 | Invalid contradiction target | `contradictionId not in contradictions/` → refuse |
| 9 | Illegal state transition | transition table §10 → refuse |
| 10 | Inconsistent duplicate accepted answer | different `EV\|…` on an `answered` question → refuse |
| 11 | Hash / provenance verification failure | recomputed `contentHash` ≠ stored → refuse |
| 12 | Synthetic markers in production data | `contains_synthetic_markers()` → refuse |
| 13 | `answered`/`partially_answered` with empty `answerEvidenceIds` | consistency check (see §0.3c) |

**No auto-repair. No coercion to a nearest legal value. No silent skip.**
Precedent exists: `SearchRefused`, `EvidenceValidationError` (which carries structured findings),
and `resolve_corpus()`'s refusal-over-guessing stance.

---

## 12. SMALLEST STEP 2 — RECOMMENDATION

**REUSE FIRST · SIMPLIFY SECOND · ADD CODE LAST.**

### 12.1 Reusable unchanged (the large majority)

* `EvidenceQuestion` schema — `answerStatus`, `answerEvidenceIds`, `researchStatus`, `resolvedAt`
  already exist and are already consumed
* `ContradictionRecord` schema — all five ruling outcomes already expressible
* `EvidenceSource` / `EvidenceItem` — full provenance incl. `exactExcerpt`, `directness`, hashes
* `EvidenceLifecycleEvent` — append-only history with `actor`/`priorStatus`/`newStatus`
* `ReviewQueueEntry` + `apply_review_action()` — the human-adjudication template
* `atomic_write_text()`, `pretty_json()`, `content_hash_of()`, `text_sha256()`
* `resolve_corpus()` — fail-closed corpus resolution
* `research_understanding.py` Steps 2/3/4 — reevaluation, unchanged
* `candidate_search.py` — nomination, unchanged
* `EvidenceValidationError` — structured refusals

### 12.2 Minimal extensions required

1. **`EvidenceLifecycleEvent`: add `EVIDENCE_QUESTION` to `entityType`.** Update the schema `enum`
   **and** the `eventId` `pattern`, plus `evidence_common.LIFECYCLE_ENTITY_TYPES`. Correct the
   pre-existing `INTAKE_MANIFEST` schema omission in the same edit (§6.1).
2. **One new governed transition function** — the only genuinely new logic:
   `record_question_answer(questions_dir, lifecycle_dir, questionId, decision, evidenceIds, actor, now, rationale)`
   where `decision ∈ {accepted, rejected, uncertain}`. Enforces §11 and §10, writes the question
   record + one lifecycle event, and **creates no links and no proposals**.
3. **A contradiction ruling function** — `record_contradiction_ruling(...)`, mirroring the above.

### 12.3 What should NOT be built

* ❌ A separate answer database or `answers/` store — `answerEvidenceIds` already exists
* ❌ New status vocabularies (`accepted` / `rejected` / `uncertain` as *stored statuses*) — the
  decision is an **event**; the state is the existing enums
* ❌ Automatic `EvidenceClaimLink` creation on answer acceptance — it triggers
  `recompute_claim_confidence()` and mutates Claims (§5.1). Keep Step 2 link-free.
* ❌ **Any** call to `run_post_annotation_pipeline()` (§9.1)
* ❌ A generalized adjudication framework, workflow engine or UI
* ❌ Transcript/Instagram/ICT/CRT acquisition; any authorization widening
* ❌ Changes to ALEX, TJR authority, strategy logic, or `index.html`
* ❌ Fixing the stale `test_graph.py` snapshot (§0.3a) — unrelated; separate decision

### 12.4 Exact files likely affected by Step 2

| File | Change |
|---|---|
| `docs/trader-intelligence/evidence/schema/evidence-lifecycle-event.schema.json` | add `EVIDENCE_QUESTION` (+ `INTAKE_MANIFEST`) to `enum` and `eventId` pattern |
| `scripts/trader_intelligence/evidence_common.py` | add `EVIDENCE_QUESTION` to `LIFECYCLE_ENTITY_TYPES`; add answer-decision vocabulary constant |
| `scripts/trader_intelligence/answer_intake.py` | **NEW** — the governed intake module (both functions + CLI) |
| `tests/trader_intelligence/test_answer_intake.py` | **NEW** — fail-closed and transition tests |
| `MOGO_020_GOVERNED_RESEARCH_ANSWER_INTAKE.md` | Step 2 findings appended |

Existing modules `evidence_questions.py`, `evidence_registry.py`, `candidate_search.py`,
`research_understanding.py`, `review_queues.py` and `extraction_pipeline.py` should remain
**unmodified**. A single new module matches the one-module-per-capability pattern MOGO-019
Steps 7/8/10/11 established.

### 12.5 Tests required before ANY production mutation is permitted

**Fail-closed (all 13 conditions of §11), each asserting refusal and no write:**
invalid `questionId`; nonexistent `EV|…`; foreign-corpus evidence; unresolvable/ambiguous corpus;
incomplete provenance; `direct_explicit` without `exactExcerpt`; missing/non-human operator;
invalid `contradictionId`; every illegal transition in §10; conflicting duplicate accepted answer;
hash mismatch; synthetic markers.

**Transition correctness:** each legal transition sets exactly the expected fields; `resolvedAt` set
only on `answered`; rejection leaves question state untouched and records a lifecycle event only.

**Idempotency:** re-accepting identical evidence is a no-op; no duplicate lifecycle event.

**Isolation / non-mutation (the milestone's core guarantees):**

* accepting an answer creates **0** `RuleCandidateProposal` records;
* accepting an answer creates **0** `EvidenceClaimLink` records;
* both source Claims of a ruled contradiction are **byte-identical** before and after;
* `exactExcerpt` / `normalizedClaim` are never modified;
* no ALEX file, no `index.html`, no strategy/authority file is touched;
* protected ALEX drift remains **0**; Campaign C1 remains **33/33**.

**Fixtures only.** Per standing rule, verification must run against synthetic fixtures
(`tests/trader_intelligence/evidence/fixtures/`), never against the live Knowledge Library, and must
persist no real records.

**Regression gates before closeout:** focused suite green · platform 1,049/1,049 ·
canonical 1,160/1,160 · ALEX drift 0 · evidence integrity 0 ERROR / 0 FATAL.

---

## AUDIT SUMMARY

**The architecture is substantially ready.** MOGO-020 is smaller than it looks: the fields,
provenance model, append-only history, corpus isolation and human-adjudication template all exist
and are proven in production. EvidenceQuestion and ContradictionRecord are simply **create-only** —
consumers read answer/resolution fields that no writer ever sets.

Step 2 is therefore **one new module, one schema enum extension, and its tests** — not a new
subsystem.

**Scientific invariants — all preserved, none weakened:**

* SOURCE FACT ≠ OPERATOR RULING — `exactExcerpt` vs `normalizedObservation`; rulings live on
  questions/contradictions/events, never inside claims
* CANDIDATE EVIDENCE ≠ ACCEPTED ANSWER — `candidate_search.py` stamps `CANDIDATE_ONLY` /
  `NOT_ADJUDICATED`; acceptance stays human
* ACCEPTED ANSWER ≠ STRATEGY RULE — no proposal creation in Step 2 (§9.1)
* RESOLVED QUESTION ≠ STRATEGY VALIDATED — eligibility stays derived and informational
* RECONSTRUCTION ELIGIBLE ≠ SPECIFICATION FROZEN — unchanged
* SPECIFICATION FROZEN ≠ PAPER AUTHORIZED — unchanged

**Protections confirmed intact:** ALEX drift **0** (63 functions, 4 constants); forward activation
cutoff `2026-08-11T02:43:57.894Z` unchanged; Campaign C1 intact; TJR **RESEARCH ONLY / BLOCKED / 17
/ NOT AUTHORIZED**; live-money **NOT AUTHORIZED**; research authorization **2 sources,
metadata-only** — not widened; no acquisition of any kind performed.

**Step 1 complete. Operator authorized Step 2 on this basis.**

---
---

# STEP 2 — GOVERNED ANSWER INTAKE FOUNDATION

**Status:** IMPLEMENTED · FOUNDATION ONLY · NO LIVE RECORD PROCESSED
**Date:** 2026-08-13
**HEAD at start:** `1c4292e6ddf8eedca82284bb2ed34e7b73ab427d` (unchanged; nothing committed)

## S2.0 Starting-state verification

Repo `joemogo/forex_hub` · branch `main` · HEAD `1c4292e…` · `mogo-019-complete^{commit}` = HEAD ·
ahead/behind **0/0** · working tree contained only the Step 1 report and the pre-existing Instagram
report. Live snapshot taken before any edit: questions **281** (`answerStatus` 280 unanswered /
1 partially_answered), links **416**, proposals **0**, lifecycle **4,472**,
`XCONTRA|20260728|001` `open`/`blocking`/`resolution: null`.

Both Step 1 findings were carried forward as **findings, not repair targets**: the stale
`test_graph.py` TRADER snapshot and `EQ|20260727|015`'s inconsistent `partially_answered` state were
left exactly as found.

## S2.1 Exact files changed

| File | Change | Δ |
|---|---|---|
| `docs/trader-intelligence/evidence/schema/evidence-lifecycle-event.schema.json` | `EVIDENCE_QUESTION` added to `entityType` enum **and** `eventId` pattern | +5 / −3 (with description) |
| `scripts/trader_intelligence/evidence_common.py` | `EVIDENCE_QUESTION` in `LIFECYCLE_ENTITY_TYPES`; `ADJUDICATION_DECISIONS`, `CONTRADICTION_RULINGS`, `HUMAN_ACTOR_PATTERN`, `require_human_actor()` | +49 |
| `scripts/trader_intelligence/validate_evidence.py` | one entry in `_GENESIS_EVENT_TYPE_BY_ENTITY_TYPE` | +6 |
| `scripts/trader_intelligence/answer_intake.py` | **NEW** — the governed intake module | 540 lines |
| `tests/trader_intelligence/test_answer_intake.py` | **NEW** — focused suite | 778 lines |
| `MOGO_020_GOVERNED_RESEARCH_ANSWER_INTAKE.md` | this section | — |

**Production footprint on existing files: +57 / −3 across 3 files.** No existing module's behaviour
was changed. `evidence_questions.py`, `evidence_registry.py`, `candidate_search.py`,
`research_understanding.py`, `review_queues.py`, `extraction_pipeline.py` and
`rule_candidate_proposals.py` are **untouched**.

## S2.2 Schemas reused (no new schema, no new store)

`EvidenceQuestion` (`answerStatus`, `answerEvidenceIds`, `researchStatus`, `resolvedAt`) ·
`ContradictionRecord` (`status`, `resolution`, `reviewedAt`, `scopeOverlap`) ·
`EvidenceSource` + `EvidenceItem` (preserved source, `directness`, `speaker`, `contentHash`) ·
`EvidenceLifecycleEvent` (append-only history). **Zero new record types. Zero new directories.**

Reused code: `atomic_write_text`, `pretty_json`, `content_hash_of`, `build_lifecycle_event`,
`write_lifecycle_event`, `next_lifecycle_event_id`, `register_source`, `register_evidence_item`,
`EvidenceIndex.load`, and `candidate_search.resolve_corpus` for fail-closed corpus resolution.

## S2.3 The one lifecycle extension — and why a second line was required

Adding `EVIDENCE_QUESTION` to the lifecycle enum alone was **not sufficient**, and inspection
proved it rather than assuming it.

`validate_evidence.check_lifecycle_sequences()` requires an entity's **first** lifecycle event to be
`created`. EvidenceQuestions have never emitted a creation event — `create_question()` writes the
record and nothing else — so the first event a question can ever have is its first adjudication.
Without a genesis mapping, every adjudication produced an ERROR-level integrity finding.

**Mutation-tested, not assumed.** Removing the mapping and re-running:

```
MUTATED -> ERROR count: 1
  ERROR EQ|20260813|001 First lifecycle event for EQ|20260813|001 is 'reviewed', expected 'created'.
```

The one added line is therefore load-bearing, and a test guards it. The alternative — backdating a
synthetic `created` event onto all 281 existing questions — was rejected: it would fabricate history
that never happened.

**`INTAKE_MANIFEST` drift deliberately NOT repaired.** Step 1 §6.1 recommended fixing it in the same
edit; the Step 2 mandate said "extend only as narrowly required" and "do not repair unrelated
failures." The narrower reading won. The constant now carries an explicit comment recording the
drift as a known, unrepaired finding awaiting a separate operator decision.

## S2.4 Exact supported transitions

**EvidenceQuestion** — no new status value was invented; both targets already existed.

| Decision | `answerStatus` | `researchStatus` | `answerEvidenceIds` | `resolvedAt` | Question file |
|---|---|---|---|---|---|
| `accepted` | → `answered` | → `answered` | += cited | set | written |
| `uncertain` **with** evidence | → `partially_answered` | → `researching` | += cited | untouched | written |
| `uncertain` **without** evidence | **unchanged** | → `researching` | unchanged | untouched | written |
| `rejected` | **unchanged** | **unchanged** | **unchanged** | unchanged | **byte-identical** |

A rejection is recorded **only** in append-only history. The question file is not rewritten at all —
proven byte-for-byte by test.

`uncertain` without evidence deliberately does **not** set `partially_answered`. That would
manufacture exactly the unverifiable shape Step 1 found on `EQ|20260727|015`. A post-condition
refuses any write of `answered`/`partially_answered` with an empty `answerEvidenceIds`.

**ContradictionRecord** — every target is an existing `CONTRADICTION_STATUSES` value.

| Ruling | `status` | `resolution` | `reviewedAt` | `scopeOverlap` |
|---|---|---|---|---|
| `resolved` | `resolved_by_owner` | = rationale | set | optional |
| `scope_qualified` | `accepted_as_context_dependent` | = rationale | set | e.g. `partial` |
| `superseded` | `superseded` | = rationale | set | optional |
| `leave_open` | **`open`** (unchanged) | **stays null** | set | optional |

`leave_open` records that a human looked without making an open contradiction appear resolved.
`severity` is never rewritten — a contradiction stops blocking via **status**, not by downgrading how
serious the disagreement was.

## S2.5 Exact fail-closed conditions

All 13 Step 1 conditions are enforced and tested, each proven to write nothing:

1. invalid/unknown/empty/`None` `questionId`
2. nonexistent `evidenceId`; `accepted`/`rejected` with empty evidence
3. foreign-corpus evidence — and a **mixed batch is refused entirely**, not partially applied
4. incomplete provenance — `provenanceStatus: unverified`, or missing `directness`
5. unresolvable/ambiguous corpus (via `resolve_corpus`)
6. `direct_explicit`/`direct_demonstrated` without preserved source — `exactExcerpt`, `speaker`,
   `sourceChannel` and `sourceDate` each required, each tested against `None`/`""`/`"   "`
7. missing or non-human actor — `pipeline`, `owner`, `""`, `None`, `42`, `operator:` all refused
8. invalid `contradictionId`
9. illegal question transition (`answered` → `uncertain`)
10. illegal contradiction transition (second, different ruling on a settled record)
11. conflicting duplicate accepted answer (different evidence on an answered question)
12. hash-verification failure — recomputed exactly as `check_inconsistent_hash` does
13. unknown decision/ruling; contradiction ruling without rationale

**Human identity is structural.** `HUMAN_ACTOR_PATTERN` requires `operator:<name>` or
`reviewer:<name>`, matching the convention already used by
`docs/trader-intelligence/authorizations/*.json`. Machine actors used elsewhere in the pipeline are
bare names and therefore cannot author a semantic decision.

## S2.6 Idempotency

One mechanism, reusing the existing `content_hash_of` primitive — **no second idempotency
framework**. Each decision is fingerprinted over its full tuple (target, decision, cited evidence,
actor, rationale) and the fingerprint is stored in the lifecycle event's `metadata`.

* exact replay of **accepted** → `DUPLICATE_NOOP`, no second event, state unchanged
* exact replay of **rejected** → `DUPLICATE_NOOP`, exactly 1 event total
* exact replay of **uncertain** → `DUPLICATE_NOOP`, exactly 1 event total
* exact replay of **direct-trader clarification** → returns the *same* `evidenceId`; no second
  source/item minted (fingerprint stored on the item's `metadata`)
* exact replay of **contradiction ruling** → `DUPLICATE_NOOP`, exactly 1 `status_changed` event
* **inconsistent** duplicate (same question, different evidence) → **fails closed**

The duplicate check runs *before* the legal-prior-state check, so an identical replay is idempotent
rather than tripping the "already answered" guard it created itself.

## S2.7 The high-risk boundary — proven, not asserted

`answer_intake.py` creates **0 EvidenceClaimLink** and **0 RuleCandidateProposal**, and never
reaches `run_post_annotation_pipeline()`. Enforced three ways:

* **behavioural** — after running *all four* intake operations, `links/` and `proposals/` are empty
  and `claims/` is **byte-identical** (had anything linked evidence to a claim,
  `recompute_claim_confidence()` would have rewritten `confidenceState`/`lastEvaluatedAt`)
* **structural** — a test greps the module's executable body (docstring and comments stripped) and
  fails on any occurrence of `extraction_pipeline`, `run_post_annotation_pipeline`,
  `rule_candidate_proposals`, `propose_rule_candidate`, `link_evidence_to_claim`,
  `recompute_claim_confidence`
* **no substring matching** — the same body check fails on `.startswith(`, `.endswith(`, `.find(`,
  `difflib`, `SequenceMatcher`, `near_duplicate`, `normalize_claim_text`

A dedicated test also proves every refusal writes **absolutely nothing**: a byte-level snapshot of
all 13 evidence subdirectories is identical before and after five different refused calls.

## S2.8 A governance property worth naming

`record_direct_trader_clarification()` **does not answer the question it was collected for.** It
creates an `EvidenceSource` + `EvidenceItem` carrying the preserved material, stamped
`candidateOnly: true` and `answersQuestionId`, and stops. Promoting it to an accepted answer is a
separate, explicit `record_question_adjudication()` call by a human.

Even an answer straight from the educator's mouth does not self-promote.
**CANDIDATE EVIDENCE ≠ ACCEPTED ANSWER holds without exception.**

## S2.9 Verification results

| Gate | Result |
|---|---|
| **New `test_answer_intake.py`** | ✅ **59 / 59, OK** |
| Focused MOGO-019 (Steps 2–4, 7, 8, 10, 11) | ✅ **222 / 222, OK** |
| Canonical gate `tests/run_all.sh` | ✅ **19 suites · 1,160 / 1,160 · 0 failed · 0 errors** |
| Platform suite | ✅ **25 suites · 1,049 / 1,049 · 0 failures · 0 errors** |
| **Protected ALEX drift** | ✅ **0** — 63 functions, 4 constants byte-identical |
| Campaign C1 | ✅ intact (covered by the canonical gate) |
| Live evidence integrity | ✅ `{INFO: 0, WARNING: 0, ERROR: 0, FATAL: 0}` |
| Live EvidenceQuestions | ✅ **281**; 280 unanswered / 1 partially_answered — **unchanged** |
| `answerEvidenceIds` populated | ✅ **0** — unchanged |
| Live `EVIDENCE_QUESTION` lifecycle events | ✅ **0** — nothing was adjudicated in production |
| Live EvidenceLinks | ✅ **416** — unchanged |
| Live RuleCandidateProposals | ✅ **0** — unchanged |
| Live lifecycle events | ✅ **4,472** — unchanged |
| `XCONTRA\|20260728\|001` | ✅ `open` / `blocking` / `resolution: null` / `reviewedAt: null` — **untouched** |
| `EQ\|20260727\|015` | ✅ `partially_answered` / `open` / `answerEvidenceIds: []` — **untouched** |
| TJR eligibility | ✅ **BLOCKED / 17** |
| TJR paper trading | ✅ NOT AUTHORIZED |
| Live-money trading | ✅ NOT AUTHORIZED |
| Research authorization | ✅ 2 sources, metadata-only — not widened |

### Pre-existing failures found, reported, and NOT repaired

Three tests fail at HEAD in the Phase 1A/1B/7A evidence suites:

* `test_evidence.TestRegression.test_production_evidence_tree_is_still_genuinely_empty`
* `test_phase1b.TestKnowledgeGraphPhase1B.test_production_graph_unchanged_without_real_corpus`
* `test_phase7a.TestKnowledgeGraphPhase7A.test_production_graph_unchanged_without_real_knowledge_library`

**Proven pre-existing, not caused by Step 2:** the three tracked edits were stashed and all three
failed **identically** against the clean MOGO-019 baseline. They are the same family as the Step 1
`test_graph.py` finding — assertions written when the production evidence tree was empty, which the
real corpus (341 claims, 641 hypotheses) has since outgrown. None is in the canonical gate, the
platform suite, or the focused MOGO-019 222. **Left untouched**; repairing them is a separate
operator decision.

No gate was silently rebaselined.

## S2.10 `git status`

```
 M docs/trader-intelligence/evidence/schema/evidence-lifecycle-event.schema.json
 M scripts/trader_intelligence/evidence_common.py
 M scripts/trader_intelligence/validate_evidence.py
?? MOGO-019-ALEX-IG-CASE-002-REPORT.md
?? MOGO_020_GOVERNED_RESEARCH_ANSWER_INTAKE.md
?? scripts/trader_intelligence/answer_intake.py
?? tests/trader_intelligence/test_answer_intake.py
```

HEAD `1c4292e…`, ahead/behind **0/0**. **Nothing committed. Nothing tagged.**

## S2.11 Invariants held

* **SOURCE FACT ≠ OPERATOR RULING** — rulings live on questions/contradictions and in append-only
  history; claims and evidence items proven byte-identical after every operation
* **CANDIDATE EVIDENCE ≠ ACCEPTED ANSWER** — §S2.8; acceptance requires a separate human act
* **ACCEPTED ANSWER ≠ STRATEGY RULE** — 0 links, 0 proposals, pipeline unreachable (§S2.7)
* **RESOLVED QUESTION ≠ STRATEGY VALIDATED** — no reevaluation wiring exists; eligibility
  recomputed read-only and unchanged at BLOCKED / 17
* **RECONSTRUCTION ELIGIBLE ≠ SPECIFICATION FROZEN** — untouched
* **SPECIFICATION FROZEN ≠ PAPER AUTHORIZED** — untouched

ALEX unmodified (drift 0, forward activation cutoff `2026-08-11T02:43:57.894Z` unchanged).
TJR remains RESEARCH ONLY. No acquisition, no backtest, no paper trade, no live-money change.

**Step 2 complete. Operator accepted it as GREEN and authorized Step 3.**

---
---

# STEP 3 — DETERMINISTIC POST-INTAKE REEVALUATION

**Status:** IMPLEMENTED · FIXTURES ONLY · NO LIVE RECORD PROCESSED
**Date:** 2026-08-13
**HEAD:** `1c4292e6ddf8eedca82284bb2ed34e7b73ab427d` (unchanged; nothing committed)

## S3.0 Starting-state verification

Repo `joemogo/forex_hub` · `main` · HEAD `1c4292e…` · `mogo-019-complete^{commit}` = HEAD ·
ahead/behind **0/0**. Step 2's three tracked edits present and understood; the only other
working-tree artifact is the pre-existing Instagram report.

Step 2 baseline re-verified before any change: new tests **59/59**, focused MOGO-019 **222/222**,
canonical **1,160/1,160**, platform **1,049/1,049**, ALEX drift **0**, links **416**, proposals
**0**, TJR **BLOCKED / 17**, paper and live-money **NOT AUTHORIZED**.

## S3.1 Existing evaluators reused — no second engine

Traced before writing any code. All four are pure, read-only and were reused **unmodified**:

| Layer | Existing function | Reused |
|---|---|---|
| Step 2 research understanding | `research_understanding.corpus_view(idx, trader_id)` | ✅ |
| Step 3 reconstruction eligibility | `research_understanding.eligibility(view)` | ✅ |
| Step 4 research routing | `research_understanding.research_plan(view, result, gaps, approved_destinations)` | ✅ |
| Gap records | `research_understanding.load_gaps(evidence_root)` | ✅ |

Candidate search does **not** participate: it is a per-question retrieval tool, not a corpus-level
evaluator, and pulling it into reevaluation would have blurred nomination into assessment.

**No eligibility rule, routing rule or corpus-view rule is restated in `answer_intake.py`.** A test
asserts the orchestration body literally delegates to all four.

## S3.2 The orchestration added

One function, `answer_intake.reevaluate()`, plus a `blocker_key()` helper and a `reevaluate` CLI
subcommand — **70 lines total** inside the existing module. It loads the index, calls the four
existing evaluators in order, and returns their output plus a small derived summary
(`eligibilityStatus`, `blockerCount`, `blockerKeys`, `countsByAction`).

The semantic boundary it implements, stated in the code:

```
governed intake -> record the human decision -> READ-ONLY reevaluation
NOT: governed intake -> strategy generation
```

`research_understanding` was already in `answer_intake`'s import chain (via `candidate_search`), so
this added **no new dependency**. No event bus, no workflow engine, no job queue, no worker, no
second graph.

## S3.3 Files changed

| File | Change | Footprint |
|---|---|---|
| `scripts/trader_intelligence/answer_intake.py` | `reevaluate()`, `blocker_key()`, CLI subcommand | +82 lines (540 → 622) |
| `tests/trader_intelligence/test_answer_intake_reevaluation.py` | **NEW** focused suite | 693 lines |
| `MOGO_020_GOVERNED_RESEARCH_ANSWER_INTAKE.md` | this section | — |

**Tracked-file diff is unchanged from Step 2: +57 / −3 across the same 3 files.** Step 3 modified no
tracked file at all. `research_understanding.py` and every other existing module remain untouched.

## S3.4 Fixture scenarios

`TwoCorpusRepo` builds two isolated synthetic corpora, `SYNTHALPHA` and `SYNTHBETA`. Each has all
five REQUIRED rule categories — **read from `ru.REQUIRED_RULE_CATEGORIES` itself**, so the fixture
cannot drift from what the evaluator requires — every claim supported by `direct_explicit` evidence,
plus one non-rule `definition` claim, one unlinked in-corpus answer candidate, and exactly **one
blocking EvidenceQuestion**.

Both corpora therefore start `BLOCKED`, each for one identifiable reason, so a decision applied to
one is visible and a decision *not* applied to the other is equally visible.

**No expected eligibility outcome is hard-coded against a copy of the rules.** Every assertion reads
`eligibility()`'s own output.

## S3.5 Behaviour proven

### Accepted

One unanswered question blocks in **two** distinct ways — as a `BLOCKING_QUESTION`, and by making
its claim's category `AMBIGUOUS`:

```
before: ["BLOCKING_QUESTION|EQ|20260813|001", "REQUIRED_CATEGORY_AMBIGUOUS|entry_rule"]
after : []   -> ELIGIBLE_FOR_RECONSTRUCTION_DRAFT
```

The evaluator produced that, not the test. The understanding view stops listing the question as
unresolved, the category becomes `SUPPORTED`, and routing drops the item. With an additional
unrelated contradiction present, the question blocker clears and **the contradiction blocker
survives untouched** — the corpus stays `BLOCKED`.

### Rejected — no status inflation

`blockerKeys` identical before and after, still `BLOCKED`, category still `AMBIGUOUS`, routing item
still present. The question file is not rewritten at all.

### Uncertain — no status inflation

`blockerKeys` identical, still `BLOCKED`. The view reports the question as
`answerStatus: partially_answered` / `researchStatus: researching` — it is **still unresolved**,
because `corpus_view` filters only on `answerStatus != "answered"`. Neither rejected nor uncertain
can make a corpus eligible.

### Contradiction rulings

| Ruling | Blocker | Category | Eligibility |
|---|---|---|---|
| (before) | present | `CONFLICTED` | `BLOCKED` |
| `resolved` | cleared | `SUPPORTED` | `ELIGIBLE` |
| `scope_qualified` (`partial`) | cleared | — | `ELIGIBLE` |
| `superseded` | cleared | — | — |
| `leave_open` | **retained** | `CONFLICTED` | `BLOCKED` |

Source claims and evidence items are **byte-identical** after ruling + reevaluation. Detection-time
`rationale` and ruling-time `resolution` remain separate fields, and the ruling carries the human
operator as `actor` with `priorStatus: open` in append-only history — **SOURCE FACT ≠ OPERATOR
RULING**, verified rather than asserted.

### Direct-trader clarification does not auto-resolve

Recording a valid preserved clarification creates evidence stamped `candidateOnly: true` and
`answersQuestionId` — and reevaluation still reports `BLOCKED`, the category still `AMBIGUOUS`, and
the question still `answerStatus: unanswered`. **No blocker disappears merely because direct-trader
evidence exists.** Only the separate, explicit human acceptance of that evidence flips the corpus to
`ELIGIBLE`.

## S3.6 Idempotency

Reevaluation is strictly read-only: three consecutive runs across both corpora leave a byte-level
snapshot of all 17 subdirectories **identical**, append **zero** lifecycle events, and return equal
`eligibility` and `plan` objects. A replayed adjudication returns `DUPLICATE_NOOP` and the
subsequent reevaluation is unchanged.

## S3.7 Corpus isolation

Accepting in corpus A leaves corpus B's `blockerKeys`, `categories` and eligibility identical, and
B's question is still `unanswered` with empty `answerEvidenceIds` on disk. A ruling in A does not
move B. Citing B's evidence to answer A's question is **refused** (`foreign-corpus`), and A stays
`BLOCKED`. Every link in the repo is verified to join an evidence item and a claim owned by the
**same** trader.

## S3.8 Downstream pipeline unreachable

The full scenario — clarification → reevaluate → accept → reevaluate → rule → reevaluate — drives
corpus A all the way to `ELIGIBLE_FOR_RECONSTRUCTION_DRAFT`. **That is precisely the moment the old
pipeline would have auto-proposed a rule candidate.** It does not:

* RuleCandidateProposal count: **0**
* EvidenceLink count: **unchanged** (12 fixture links; intake and reevaluation add none)
* `claims/` **byte-identical**
* no strategy specification, no backtest artifact, no paper-trade artifact — the evidence root
  contains no directory beyond the fixture's own

Structural proof was upgraded this step. Step 2's forbidden-name check was textual and would have
tripped on `reevaluate()`'s own docstring, which legitimately says the function authorizes no
*backtesting* or *paper trading*. Step 3 replaces that with **AST analysis** — collecting every
name the module actually references (imports, bare names, attribute names) — so documentation can
never be confused with a call. `extraction_pipeline`, `run_post_annotation_pipeline`,
`rule_candidate_proposals`, `propose_rule_candidate`, `link_evidence_to_claim`,
`recompute_claim_confidence`, `strategy_blueprint`, `backtest` and `paper_trade` are all absent from
the referenced-identifier set.

The proposal pipeline was **not modified**. It remains exactly as it was, and simply unreachable.

## S3.9 Verification results

| Gate | Result |
|---|---|
| **New `test_answer_intake_reevaluation.py`** | ✅ **40 / 40, OK** |
| Step 2 `test_answer_intake.py` | ✅ **59 / 59, OK** |
| Both intake suites together | ✅ **99 / 99, OK** |
| Focused MOGO-019 | ✅ **222 / 222, OK** |
| Canonical gate | ✅ **19 suites · 1,160 / 1,160 · 0 failed · 0 errors** |
| Platform suite | ✅ **25 suites · 1,049 / 1,049 · 0 failures · 0 errors** |
| **Protected ALEX drift** | ✅ **0** — 63 functions, 4 constants |
| Campaign C1 | ✅ intact |
| Fixture integrity after full flow | ✅ 0 ERROR / 0 FATAL |
| Live evidence integrity | ✅ `{INFO: 0, WARNING: 0, ERROR: 0, FATAL: 0}` |
| Live EvidenceQuestions | ✅ **281**; 280 unanswered / 1 partially_answered — unchanged |
| Live `answerEvidenceIds` populated | ✅ **0** |
| Live `EVIDENCE_QUESTION` lifecycle events | ✅ **0** |
| Live EvidenceLinks | ✅ **416** |
| Live RuleCandidateProposals | ✅ **0** |
| Live lifecycle events | ✅ **4,472** |
| `XCONTRA\|20260728\|001` | ✅ `open` / `blocking` / `resolution: null` / `reviewedAt: null` |
| `EQ\|20260727\|015` | ✅ `partially_answered` / `open` / `[]` — untouched |
| TJR eligibility | ✅ **BLOCKED / 17** |
| TJR paper trading | ✅ NOT AUTHORIZED |
| Live-money trading | ✅ NOT AUTHORIZED |
| Research authorization | ✅ 2 sources, metadata-only — not widened |

The three pre-existing non-gated failures identified in Step 2
(`test_production_evidence_tree_is_still_genuinely_empty` and the two
`production_graph_unchanged_*` tests) remain out of scope and were not repaired. **Step 3 caused no
new failure.** Nothing was rebaselined.

## S3.10 `git status`

```
 M docs/trader-intelligence/evidence/schema/evidence-lifecycle-event.schema.json
 M scripts/trader_intelligence/evidence_common.py
 M scripts/trader_intelligence/validate_evidence.py
?? MOGO-019-ALEX-IG-CASE-002-REPORT.md
?? MOGO_020_GOVERNED_RESEARCH_ANSWER_INTAKE.md
?? scripts/trader_intelligence/answer_intake.py
?? tests/trader_intelligence/test_answer_intake.py
?? tests/trader_intelligence/test_answer_intake_reevaluation.py
```

HEAD `1c4292e…`, ahead/behind **0/0**. **Nothing committed. Nothing tagged.**

## S3.11 Invariants held

* **SOURCE FACT ≠ OPERATOR RULING** — claims and items byte-identical after every ruling;
  `rationale` and `resolution` remain distinct fields
* **CANDIDATE EVIDENCE ≠ ACCEPTED ANSWER** — a preserved direct-trader clarification clears no
  blocker until a human explicitly accepts it
* **ACCEPTED ANSWER ≠ STRATEGY RULE** — a corpus reaching `ELIGIBLE` still yields 0 proposals,
  0 links, 0 claim mutations
* **RESOLVED QUESTION ≠ STRATEGY VALIDATED** — eligibility is reported as informational; the
  evaluator's own `meaning` field says it authorizes nothing
* **RECONSTRUCTION ELIGIBLE ≠ SPECIFICATION FROZEN** — no specification path exists
* **SPECIFICATION FROZEN ≠ PAPER AUTHORIZED** — untouched

ALEX unmodified (drift 0, forward activation cutoff `2026-08-11T02:43:57.894Z` unchanged). TJR
remains RESEARCH ONLY at BLOCKED / 17. No acquisition, no specification freeze, no backtest, no
paper trade, no live-money change.

**Step 3 complete. Operator accepted it as GREEN and authorized Step 4.**

---
---

# STEP 4 — GOVERNED INTAKE PREVIEW AND COMMIT BOUNDARY

**Status:** IMPLEMENTED · FIXTURES ONLY · NO PRODUCTION RECORD PROCESSED
**Date:** 2026-08-13
**HEAD:** `1c4292e6ddf8eedca82284bb2ed34e7b73ab427d` (unchanged; nothing committed)

## S4.0 Starting-state verification

Repo `joemogo/forex_hub` · `main` · HEAD `1c4292e…` · `mogo-019-complete^{commit}` = HEAD ·
ahead/behind **0/0**. Steps 2 and 3 working-tree changes present and understood; report present;
only other artifact is the pre-existing Instagram report. Baseline re-verified: MOGO-020 **99/99**,
focused MOGO-019 **222/222**, canonical **1,160/1,160**, platform **1,049/1,049**, ALEX drift **0**,
links **416**, proposals **0**, TJR **BLOCKED / 17**.

## S4.1 Existing preview / dry-run mechanisms found

Searched before implementing.

| Pattern | Where | Verdict |
|---|---|---|
| `--dry-run` (validate, then return before writing) | `ingest.py:878`, `platform/runtime/cli.py:1000` | **Partial.** CLI-level only. Returns no machine-readable object and binds no later commit — the real write is a separate invocation with nothing tying it to what was validated. |
| **Recorded hash compared against current state, failing closed** | `ingest.py:426` — refuses when a manifest and its normalization map disagree on `sourceFileSha256` | ✅ **Directly reused as precedent.** |
| Idempotency key = SHA-256 over canonical serialization of an operation *and its declared parts*, where "a caller cannot quietly widen or narrow a key" | `platform/contracts/ids.py:571` | ✅ **Discipline reused**, not the code — the research layer must not depend on the trading platform (Step 3 §9 established this). |
| `compute_claim_fingerprint` / `content_hash_of`, and `check_normalized_fingerprint` recompute-and-compare | `evidence_common.py`, `validate_evidence.py:337` | ✅ **Reused directly** — the Knowledge Library's own hashing primitive. |
| Leases / fencing tokens | `platform/runtime/lease.py` | ❌ Not used — that is distributed task execution, not what this needs. |

**No transaction framework was created.** The preview token is a hash, computed with the primitive
the Knowledge Library already uses everywhere.

## S4.2 Implementation

Two structural changes inside the existing `answer_intake.py`:

**(a) Validation split from writing.** Each of the three `record_*` functions was refactored into
`_plan_*` (full validation + the exact state it would produce, **writes nothing**) plus a thin
`_apply_*` (writes). The public `record_*` signatures are unchanged — proven by Steps 2 and 3
remaining **99/99** green through the refactor.

`_plan_*` is now the **single authority** on whether an action is legal. `preview()` and `commit()`
both call it, so they cannot disagree.

**(b) The preview/commit boundary** — `preview()`, `commit()`, `preview_token()`, `_material_state()`,
`_prospective_index()`, `_safe_reevaluation()`, `_provenance_summary()`, and a `_PLANNERS` dispatch
table.

One behavioural correction fell out of the refactor: the duplicate-replay check now also **skips the
legal-prior-state guard**, so re-submitting an identical decision stays idempotent instead of
tripping the "already answered" rule it created itself.

## S4.3 Preview object

`preview()` returns a plain JSON-serializable dict (test-asserted) carrying:

* **the action** — `action`, `targetType`, `targetId`, `actor`, `decision`, `rationale`,
  `corpusTraderId`, `evidenceIds`
* **the state** — `currentRecord`, `proposedRecord`, `changedFields` (each `{from, to}`),
  `wouldAppendLifecycleEvent` (the exact event, including `priorStatus`/`newStatus`/`actor`)
* **provenance** — `provenanceSummary` per cited item: owning source, trader, `provenanceStatus`,
  `directness`, `extractionCertainty`, `speaker`, `exactExcerpt`, `contentHash`
* **source/ruling separation** — `sourceClaimIds`, `sourceClaimsUnchanged`
* **consequences, from the existing evaluators only** — `reevaluationBefore`, `reevaluationAfter`,
  `blockersRemoved`, `blockersRetained`, `blockersAdded`, `eligibilityBefore/After`,
  `eligibilityChanges`, `routingBefore/After`, `routingChanged`
* **the boundary** — `previewToken`, `wouldWrite`, `duplicateOfEventId`, `isAuthorization: False`,
  and `authorizes`, which states in words that no proposal, specification freeze, backtest, paper
  trading or live-money change is authorized

**The "after" state is computed against an in-memory prospective index** — `_prospective_index()`
loads a fresh `EvidenceIndex` and applies the planned change to that throwaway object. Nothing is
copied to disk, so the forecast cannot leak into stored state even in principle.

Reevaluation is wrapped in `_safe_reevaluation()`: if the evaluators refuse a corpus (e.g.
`CorpusAmbiguous` because some claim lacks a `traderId`), the preview reports
`{"available": False, "reason": …}` rather than handing the operator a traceback.

## S4.4 State binding — the preview token

```
previewToken = SHA256( previewSchemaVersion + actionFingerprint + materialStateFingerprint )
```

`materialStateFingerprint` has **fixed declared parts** (`_MATERIAL_PARTS`, asserted in code and
test) — following `ids.py`'s rule that a caller can neither widen nor narrow what a key attests to:

| Part | Contents |
|---|---|
| `action`, `targetType`, `targetId` | which governed action, on which record |
| `targetRecord` | the **whole** stored target — any field change invalidates the token |
| `corpusTraderId` | resolved corpus |
| `evidence` | per cited item: `contentHash`, `sourceId`, `directness`, `evidenceStatus` |
| `sources` | per owning source: `traderId`, `provenanceStatus` |
| `plannedIds` | the identifiers a clarification would mint |

`actionFingerprint` (from Step 2) covers target, decision, cited evidence, actor and rationale.

Deliberately **not** included: the wall clock. A preview at 10:00 and a commit at 10:05 must match;
the token binds the *decision and the reviewed state*, not the moment.

## S4.5 Commit semantics

`commit(evidence_root, action, now, previewToken, **kwargs)`:

1. **Requires a token** — missing/empty/whitespace is refused outright.
2. **Re-runs `_plan_*` from scratch** against current disk state. The preview's verdict is never
   trusted; if validation now fails (foreign corpus, tampered hash, illegal transition), commit
   fails on *that* — before the token is even compared.
3. **Recomputes the token** and refuses on any difference.
4. **Applies only the planned action**, then optionally runs the Step 3 read-only reevaluation.

Duplicate handling is checked **before** the token comparison: an exact replay of an
already-recorded decision is a no-op regardless of token staleness, because the intended effect
already exists and re-applying it is precisely what must not happen.

## S4.6 CLI

`--preview` and `--commit-token` were added to the existing `adjudicate` and `rule-contradiction`
subcommands as a **required mutually-exclusive group**. There is deliberately no bare "just write
it" form any more — the operator either previews or commits an exact previewed action:

```
$ answer_intake.py --evidence-root <fixture> adjudicate --question-id 'EQ|…' …
answer_intake.py adjudicate: error: one of the arguments --preview --commit-token is required
```

A preview prints the changed fields, the eligibility delta, blockers removed/retained, the token,
and `PREVIEW IS NOT APPROVAL. To apply, re-run with --commit-token …`. A refused commit prints
`REFUSED -- nothing was written` with the reason and exits 2, rather than a traceback. No UI, no
interactive prompt inside core logic — `preview()`/`commit()` stay pure and testable.

## S4.7 Direct-trader two-stage boundary

Preserved and now visible in the preview itself: a clarification preview reports
`answersQuestion: False`, `changedFields: {}`, `blockersRemoved: []`, and
`eligibilityBefore == eligibilityAfter`. Committing it creates candidate evidence and leaves the
question `unanswered` and the corpus `BLOCKED`.

Two separate proofs that the second stage is genuinely required: the clarification's token is
**rejected** if used to commit the acceptance, and the acceptance needs its own preview whose token
differs. Predicted `plannedSourceId`/`plannedEvidenceId` are asserted to equal what commit actually
creates.

## S4.8 Operator ruling boundary

A contradiction preview names `sourceClaimIds`, sets `sourceClaimsUnchanged: True`, and reports
`changedFields` as exactly `["resolution", "reviewedAt", "status"]` — only governed resolution
fields. After commit, `claims/` and `items/` are **byte-identical**, the detection-time `rationale`
is intact and untouched, and the operator's reasoning lives in `resolution` plus append-only
history. `leave_open` previews show the blocker retained and `resolution` still null.

## S4.9 Focused tests — `test_answer_intake_preview.py`, 53 tests

All 20 required conditions covered:

| # | Condition | Result |
|---|---|---|
| 1 | preview performs zero writes (all three actions) | ✅ byte-level snapshot identical |
| 2 | repeated identical preview is deterministic | ✅ same token, equal object |
| 3 | preview appends no lifecycle events | ✅ |
| 4 | valid preview + valid commit succeeds | ✅ committed reality matches the forecast |
| 5 | commit without token fails | ✅ incl. fabricated token |
| 6 | modified target after preview blocks commit | ✅ |
| 7 | modified evidence after preview blocks commit | ✅ |
| 8 | modified provenance / tampered hash blocks commit | ✅ two tests |
| 9 | wrong corpus after preview fails | ✅ |
| 10 | changed actor / rationale / evidence set invalidates token | ✅ three tests |
| 11 | token cannot authorize a different target | ✅ |
| 12 | token cannot authorize a different decision, or action type | ✅ two tests |
| 13 | exact duplicate commit is idempotent | ✅ |
| 14 | rejected preview mutates nothing; rejected commit writes only history | ✅ |
| 15 | uncertain preview does not falsely resolve | ✅ incl. the no-evidence shape |
| 16 | direct-trader preview/commit stays candidate-only | ✅ six tests |
| 17 | contradiction preview preserves source claims | ✅ six tests |
| 18 | prospective reevaluation creates no persistent change | ✅ |
| 19 | 0 RuleCandidateProposal | ✅ even at `ELIGIBLE` |
| 20 | 0 unintended EvidenceLinks | ✅ |

Plus: refused previews write nothing, unknown actions/tokens are refused, the token is 64-char hex,
four distinct actions produce four distinct tokens, `_MATERIAL_PARTS` is asserted against drift,
corpus B is untouched by a full flow in corpus A, and the AST check confirms the module still
references none of `extraction_pipeline`, `run_post_annotation_pipeline`, `propose_rule_candidate`,
`link_evidence_to_claim`, `recompute_claim_confidence`, `backtest` or `paper_trade`.

**One Step 3 test was updated, not weakened:** `test_reevaluation_only_calls_the_existing_evaluators`
now inspects `_reevaluate_index()`, the function the evaluator chain moved into, and additionally
asserts the public entry point routes through it. The invariant is unchanged; only its location.

## S4.10 Verification results

| Gate | Result |
|---|---|
| **New `test_answer_intake_preview.py`** | ✅ **53 / 53, OK** |
| Step 3 reevaluation suite | ✅ **40 / 40, OK** |
| Step 2 intake suite | ✅ **59 / 59, OK** |
| **All MOGO-020 suites together** | ✅ **152 / 152, OK** |
| Focused MOGO-019 | ✅ **222 / 222, OK** |
| Canonical gate | ✅ **19 suites · 1,160 / 1,160 · 0 failed · 0 errors** |
| Platform suite | ✅ **25 suites · 1,049 / 1,049 · 0 failures · 0 errors** |
| **Protected ALEX drift** | ✅ **0** — 63 functions, 4 constants |
| Campaign C1 | ✅ intact |
| Live evidence integrity | ✅ `{INFO: 0, WARNING: 0, ERROR: 0, FATAL: 0}` |
| Live EvidenceQuestions | ✅ **281**; 280 unanswered / 1 partially_answered |
| Live `answerEvidenceIds` populated | ✅ **0** |
| Live `EVIDENCE_QUESTION` lifecycle events | ✅ **0** |
| Live EvidenceLinks | ✅ **416** |
| Live RuleCandidateProposals | ✅ **0** |
| Live lifecycle events | ✅ **4,472** |
| `XCONTRA\|20260728\|001` | ✅ `open` / `blocking` / `resolution: null` / `reviewedAt: null` |
| `EQ\|20260727\|015` | ✅ `partially_answered` / `open` / `[]` — untouched |
| TJR eligibility | ✅ **BLOCKED / 17** |
| TJR paper trading | ✅ NOT AUTHORIZED |
| Live-money trading | ✅ NOT AUTHORIZED |
| Research authorization | ✅ 2 sources, metadata-only — not widened |

The three known pre-existing non-gated failures were **not repaired and not rebaselined**. Step 4
caused no new failure.

## S4.11 Files changed and footprint

| File | Change | Size |
|---|---|---|
| `scripts/trader_intelligence/answer_intake.py` | plan/apply split + preview/commit boundary + CLI | 622 → **1,099** lines |
| `tests/trader_intelligence/test_answer_intake_preview.py` | **NEW** | 604 lines |
| `tests/trader_intelligence/test_answer_intake_reevaluation.py` | 2 fixture helpers; 1 delegation test relocated | 693 → 708 |
| `MOGO_020_GOVERNED_RESEARCH_ANSWER_INTAKE.md` | this section | — |

**Tracked-file diff is still exactly Step 2's: +57 / −3 across 3 files.** Steps 3 and 4 modified no
tracked file. No new module was created; no workflow framework, approval server, background process,
queue, database, UI or transaction manager exists.

## S4.12 `git status`

```
 M docs/trader-intelligence/evidence/schema/evidence-lifecycle-event.schema.json
 M scripts/trader_intelligence/evidence_common.py
 M scripts/trader_intelligence/validate_evidence.py
?? MOGO-019-ALEX-IG-CASE-002-REPORT.md
?? MOGO_020_GOVERNED_RESEARCH_ANSWER_INTAKE.md
?? scripts/trader_intelligence/answer_intake.py
?? tests/trader_intelligence/test_answer_intake.py
?? tests/trader_intelligence/test_answer_intake_preview.py
?? tests/trader_intelligence/test_answer_intake_reevaluation.py
```

HEAD `1c4292e…`, ahead/behind **0/0**. **Nothing committed. Nothing tagged.**

## S4.13 Invariants held

* **SOURCE FACT ≠ OPERATOR RULING** — preview names the source claims and marks them unchanged;
  commit leaves `claims/` and `items/` byte-identical
* **CANDIDATE EVIDENCE ≠ ACCEPTED ANSWER** — a clarification preview reports `answersQuestion: False`
  and its token cannot commit the acceptance
* **ACCEPTED ANSWER ≠ STRATEGY RULE** — a full preview→commit flow reaching `ELIGIBLE` still yields
  0 proposals and 0 links
* **RESOLVED QUESTION ≠ STRATEGY VALIDATED** — every preview carries `isAuthorization: False` and an
  explicit statement of what it does not authorize
* **RECONSTRUCTION ELIGIBLE ≠ SPECIFICATION FROZEN** — no specification path exists
* **SPECIFICATION FROZEN ≠ PAPER AUTHORIZED** — untouched

ALEX unmodified (drift 0, cutoff `2026-08-11T02:43:57.894Z` unchanged). TJR remains RESEARCH ONLY at
BLOCKED / 17. No acquisition, no clarification sent, no Instagram material, no specification freeze,
no backtest, no paper trade, no live-money change.

**Step 4 complete. Operator accepted Steps 1–4 as GREEN and authorized the Step 5 commit gate.**

---
---

# STEP 5 — FOUNDATION READINESS AND COMMIT GATE

**Status:** AUDIT COMPLETE · NOTHING COMMITTED · NOTHING TAGGED
**Date:** 2026-08-13
**HEAD:** `1c4292e6ddf8eedca82284bb2ed34e7b73ab427d`

## VERDICT: 🟡 YELLOW — COMMIT BLOCKED BY ONE IDENTIFIED MOGO-020 ISSUE

Every authoritative gate is clean and production is untouched. **One requirement of this step could
not be confirmed**: §3 asked me to confirm there is no bare "just write it" entry point. There is
one, at the Python API level. It is small, precisely located, and cheap to close — see §S5.3.1.

## S5.0 Starting-state verification

| Check | Expected | Observed | ✓ |
|---|---|---|---|
| Repository | forex_hub | `joemogo/forex_hub.git` | ✅ |
| Branch / HEAD | `main` / `1c4292e` | `main` / `1c4292e6ddf…` | ✅ |
| `mogo-019-complete^{commit}` | = HEAD | `1c4292e6ddf…` | ✅ |
| Ahead / behind | 0 / 0 | `0  0` | ✅ |
| Step 2 tests | 59/59 | **59/59 OK** | ✅ |
| Step 3 tests | 40/40 | **40/40 OK** | ✅ |
| Step 4 tests | 53/53 | **53/53 OK** | ✅ |
| Total MOGO-020 | 152/152 | **152/152 OK** | ✅ |
| Focused MOGO-019 | 222/222 | **222/222 OK** | ✅ |
| Canonical | 1,160/1,160 | **1,160/1,160, 0 errors** | ✅ |
| Platform | 1,049/1,049 | **1,049/1,049, 0 errors** | ✅ |
| ALEX drift | 0 | **0** (63 fn, 4 const) | ✅ |
| Campaign C1 | intact | intact | ✅ |
| EvidenceLinks | 416 | **416** | ✅ |
| RuleCandidateProposal | 0 | **0** | ✅ |
| EvidenceQuestions | 281 | **281** | ✅ |
| Answer distribution | 280 unanswered / 1 partially | **280 / 1** | ✅ |
| Production EQ lifecycle events | 0 | **0** | ✅ |
| `XCONTRA\|20260728\|001` | OPEN/BLOCKING/UNRESOLVED | `open`/`blocking`/`null`/`null` | ✅ |
| TJR | BLOCKED / 17 | **BLOCKED / 17** | ✅ |
| TJR paper / live money | NOT AUTHORIZED | NOT AUTHORIZED | ✅ |
| Evidence integrity | clean | `{INFO:0, WARNING:0, ERROR:0, FATAL:0}` | ✅ |

## S5.1 Full MOGO-020 diff from MOGO-019 HEAD

### Tracked (modified) — `+57 / −3` across 3 files

| File | Classification | Δ | What |
|---|---|---|---|
| `docs/…/schema/evidence-lifecycle-event.schema.json` | **required schema support** | +5/−3 | `EVIDENCE_QUESTION` in `entityType` enum **and** `eventId` pattern |
| `scripts/trader_intelligence/evidence_common.py` | **required constants support** | +49 | `EVIDENCE_QUESTION` in `LIFECYCLE_ENTITY_TYPES`; `ADJUDICATION_DECISIONS`, `CONTRADICTION_RULINGS`, `HUMAN_ACTOR_PATTERN`, `require_human_actor()` |
| `scripts/trader_intelligence/validate_evidence.py` | **required foundation code** | +6 | one `_GENESIS_EVENT_TYPE_BY_ENTITY_TYPE` entry (mutation-proven load-bearing in Step 2) |

### Untracked (new)

| File | Classification | Lines |
|---|---|---|
| `scripts/trader_intelligence/answer_intake.py` | **required foundation code** | 1,099 |
| `tests/trader_intelligence/test_answer_intake.py` | required test coverage (Step 2) | 778 |
| `tests/trader_intelligence/test_answer_intake_reevaluation.py` | required test coverage (Step 3) | 708 |
| `tests/trader_intelligence/test_answer_intake_preview.py` | required test coverage (Step 4) | 604 |
| `MOGO_020_GOVERNED_RESEARCH_ANSWER_INTAKE.md` | milestone report | this file |
| `MOGO-019-ALEX-IG-CASE-002-REPORT.md` | **unrelated artifact** — pre-existing, not MOGO-020 | — |

**Confirmed: Steps 3 and 4 required no additional tracked production file.** The tracked diff has
been byte-for-byte identical since Step 2. All Step 3 and Step 4 production code landed inside the
single new module `answer_intake.py`.

Test-to-production ratio for the new module is **2,090 : 1,099 ≈ 1.9 : 1**.

## S5.2 Static coupling review

Two independent methods, both consistent with existing repository practice.

**(a) Transitive import closure.** Walking every intra-package import from `answer_intake` yields a
closure of **12 modules**:

```
answer_intake
  candidate_search
    query_evidence -> evidence_common -> graph_common
                      evidence_dedup
                      evidence_explain -> evidence_confidence
                      tjr_report
    research_understanding
    rule_conformance
  evidence_registry
```

`extraction_pipeline`, `rule_candidate_proposals`, `annotation_pipeline`, `ingest`,
`strategy_blueprint`, `build_graph`, `validate_acquisition` and `acquisition_common` are **all absent
from the closure**. They are not merely uncalled — they are unimportable along every path from this
module. Strategy reconstruction, specification, backtesting, paper and live execution have no module
in the closure at all.

**(b) Call-level AST inventory.** The module's *complete* external call surface:

| Module | Functions called |
|---|---|
| `evidence_registry` (`reg`) | `register_source`, `register_evidence_item` — **only these two**, both create-only |
| `research_understanding` (`ru`) | `corpus_view`, `eligibility`, `research_plan`, `load_gaps` — all read-only |
| `graph_common` (`gc`) | `atomic_write_text`, `content_hash_of`, `pretty_json` |
| `evidence_common` (`evc`) | validation + lifecycle helpers only |

Explicitly **not called**, though `evidence_registry` is in the closure and defines them:
`link_evidence_to_claim`, `recompute_claim_confidence`, `create_contradiction`, `register_claim`,
`correct_evidence_item`. This is the honest nuance: the *module* is imported (for the two
registrars), so the guarantee for these five is at the **call** level, enforced by an AST test that
fails if any of them ever appears.

`register_evidence_item` is only ever called without `supersedesEvidenceId`, so its one internal
branch that mutates another record (`_mark_evidence_superseded`) is unreachable from here.

**No unrelated module was modified.** No new defect was found in existing code.

## S5.3 Public API surface

| Callable | Purpose | R/W | Human-supplied | Validation | Persists | Lifecycle | Reevaluation | Idempotency | Fail-closed |
|---|---|---|---|---|---|---|---|---|---|
| `preview(root, action, now, …)` | Report what an action WOULD do | **read-only** | action, target, decision, actor, evidence, rationale | full `_plan_*` | **nothing** | none | prospective, in-memory | deterministic; same state → same token | all 13 Step 2 conditions + unknown action |
| `commit(root, action, now, previewToken, …)` | Perform exactly the previewed action | **write** | as above **+ token** | full `_plan_*` re-run, then token match | target record + event | 1 event | optional, after write | duplicate → `DUPLICATE_NOOP` before token check | missing/stale/foreign token; all `_plan_*` conditions |
| `reevaluate(root, traderId, …)` | Re-run Step 2/3/4 evaluators | **read-only** | trader | corpus resolution | **nothing** | none | yes | pure | `CorpusAmbiguous` surfaced |
| `blocker_key(blocker)` | Stable blocker identity | pure | — | — | — | — | — | — | — |
| `preview_token(idx, plan)` | Bind action to reviewed state | pure | — | — | — | — | — | — | — |
| `record_question_adjudication(…)` | Primitive governed writer | **write** | question, decision, reviewer, evidence | full | question + event | 1 | none | duplicate → no-op | all Step 2 conditions |
| `record_direct_trader_clarification(…)` | Primitive governed writer | **write** | question, reviewer, trader, speaker, excerpt, channel, date | full | source + item | 2 | none | fingerprint → returns existing | preserved-source gate |
| `record_contradiction_ruling(…)` | Primitive governed writer | **write** | contradiction, ruling, operator, rationale | full | contradiction + event | 1 | none | duplicate → no-op | legal prior state |

**CLI:** `adjudicate`, `rule-contradiction` (each requiring `--preview` XOR `--commit-token`), and
`reevaluate`. `--evidence-root` is required with no default.

### S5.3.1 🟡 THE ONE ISSUE — an unpreviewed public writer exists

**§3 asked me to confirm there is no bare "just write it" entry point. I cannot.**

The CLI is clean: argparse enforces a required mutually-exclusive `--preview` / `--commit-token`
group, so an operator at the terminal cannot skip review. But the three `record_*` functions remain
**public** and write without any token. Demonstrated against a fixture:

```
record_question_adjudication without preview -> APPLIED
question answerStatus now -> answered
eligibility now -> ELIGIBLE_FOR_RECONSTRUCTION_DRAFT
```

A governed answer was written, and the corpus flipped to eligible, with no preview ever run.

**Severity: moderate, not critical.** These are not unvalidated writes — every Step 2 fail-closed
condition (human actor, corpus isolation, provenance, hash verification, legal prior state,
idempotency) still applies. What is bypassed is only Step 4's *state-binding review*, i.e. the
protection against a stale operator approval. But that protection is precisely why Step 4 exists,
and "preview and commit must remain distinct" is weakened by a public path around both.

**Why it exists:** `record_*` were the Step 2 public API. Step 4 introduced `_apply_*` for
`commit()` to use, which left `record_*` used only by the Steps 2/3 test suites and any external
caller. They are effectively vestigial public surface.

**Proposed minimal remedy (not applied — this step is an audit):** rename the three to
`_record_*`, leaving them as the internal primitives they now are, and update the ~30 Step 2/3 test
call sites. No behaviour changes; `preview()`/`commit()`/`reevaluate()` become the only public
mutating surface. Estimated footprint: 3 renames plus mechanical test updates, no logic touched.

I did not apply this because Step 5 is explicitly a bounded audit and commit gate.

## S5.4 SOURCE FACT ≠ OPERATOR RULING

| Requirement | Evidence |
|---|---|
| Direct-trader clarification preserves source | `exactExcerpt`, `speaker`, `sourceChannel`, `sourceDate` all required for `direct_*`; `contentHash` computed and verified |
| Candidate-only evidence does not answer its own question | preview reports `answersQuestion: False`, `changedFields: {}`, `eligibilityBefore == eligibilityAfter`; after commit the question is still `unanswered` and the corpus `BLOCKED` |
| Human acceptance is a separate action | the clarification's token is **rejected** if used to commit the acceptance; acceptance requires its own preview with a different token |
| Operator ruling does not rewrite source claims | `claims/` and `items/` **byte-identical** after ruling + reevaluation; ruling touches exactly `["resolution", "reviewedAt", "status"]` |
| Detection reasoning survives the ruling | `rationale` (detection) intact; operator reasoning goes to `resolution` — separate fields, asserted |
| Rejected does not masquerade as fact | question file **byte-identical**; decision exists only in append-only history |
| Uncertain does not inflate status | `partially_answered`/`researching`, never `answered`; without evidence it will not even set `partially_answered` |
| Source immutability | `_validate_evidence_ids` recomputes `contentHash` exactly as `check_inconsistent_hash` does and refuses on mismatch |

## S5.5 Preview-token audit

`previewToken = SHA256(previewSchemaVersion + actionFingerprint + materialStateFingerprint)`, using
`graph_common.content_hash_of` — the Knowledge Library's own primitive. **No key infrastructure, no
secrets, no signing**; this is a state-binding digest, not an authentication credential, and it is
deliberately not treated as one.

Declared material parts (`_MATERIAL_PARTS`, asserted in code and test so they cannot drift):
`action`, `targetType`, `targetId`, `targetRecord` (**whole record**), `corpusTraderId`,
`evidence` (per item: `contentHash`, `sourceId`, `directness`, `evidenceStatus`), `sources` (per
source: `traderId`, `provenanceStatus`), `plannedIds`.

| Property | Result |
|---|---|
| Deterministic for identical reviewed state | ✅ identical token, equal preview object |
| **Wall-clock change does not invalidate** | ✅ verified across a 5-month clock jump — token STABLE |
| Material state change invalidates | ✅ target, evidence content, provenance, corpus each tested |
| Cannot be reused for a different target | ✅ |
| Cannot be reused for a different decision or action type | ✅ |
| Commit revalidates independently | ✅ `_plan_*` re-runs from disk; a tampered hash fails on hash verification *before* the token is compared |

Coverage assessment: the parts include every input to admissibility that `_plan_*` reads. Not
included, deliberately: the wall clock (would make every preview expire pointlessly) and unrelated
records elsewhere in the corpus (would make tokens fail for changes that cannot affect this action).

## S5.6 Lifecycle audit

| Aspect | Finding |
|---|---|
| `EVIDENCE_QUESTION` entity type | added to schema `enum` **and** `eventId` pattern **and** `LIFECYCLE_ENTITY_TYPES` — all three together |
| Genesis mapping | `EVIDENCE_QUESTION → "reviewed"`, because questions have never emitted a `created` event; mutation-proven load-bearing in Step 2 |
| Event ID pattern | `LCEVT\|EVIDENCE_QUESTION\|{questionId}\|{seq}` — matches the extended schema pattern |
| Sequence integrity | derived by `next_lifecycle_event_id`, which reads each event's own recorded `entityType`/`entityId` (hash-derived filenames make a filename scan impossible) |
| priorStatus / newStatus | recorded on every adjudication (`unanswered → answered`, etc.) |
| Actor identity | `require_human_actor` enforces `operator:` / `reviewer:` namespacing; machine actors refused |
| Duplicate / idempotent | `decisionFingerprint` in event metadata; replay appends nothing |
| Integrity | fixture flows and live corpus both report 0 ERROR / 0 FATAL |

**No fake historical genesis events were added.** Production lifecycle is still **4,472** events:
`CLAIM` 3,432 · `EVIDENCE_CLAIM_LINK` 507 · `EVIDENCE_ITEM` 416 · `INTAKE_MANIFEST` 85 ·
`CONTRADICTION_RECORD` 19 · `EVIDENCE_SOURCE` 13 — and **`EVIDENCE_QUESTION`: 0**. Backdating a
synthetic `created` event onto the 281 questions was explicitly rejected in Step 2.

**Pre-existing drift, now quantified:** those **85 `INTAKE_MANIFEST` events already violate the
schema's `entityType` enum and `eventId` pattern**, which never listed that type. This is
pre-existing (Step 1 §6.1), was deliberately left unrepaired under Step 2's "extend only as narrowly
required" mandate, and is recorded as a comment in `evidence_common.py`. It remains a separate
operator decision.

## S5.7 Known pre-existing findings — carried forward, not repaired

| # | Finding | Proven pre-existing | Gated? |
|---|---|---|---|
| 1 | `test_graph.py::test_expected_node_and_edge_counts` — asserts 3 TRADER nodes, repo has 5 | Step 1, file unmodified since `9903297` | ❌ in no gate |
| 2 | `test_evidence`/`test_phase1b`/`test_phase7a` — three "production tree is empty / graph unchanged" assertions | Step 2, stash-verified identical on clean MOGO-019 | ❌ in no gate |
| 3 | `EQ\|20260727\|015` — `partially_answered` with empty `answerEvidenceIds` | Step 1, committed at `c03f35e` | data, not a test |
| 4 | `INTAKE_MANIFEST` lifecycle code/schema drift (85 live events) | Step 1 §6.1 | not validated |

Re-verified this step: the evidence suites still report **exactly 3** failures, `test_graph` still
**exactly 1**. **No new failure attributable to MOGO-020.** None repaired.

## S5.8 Final foundation test battery

| Gate | Result |
|---|---|
| Step 2 `test_answer_intake.py` | ✅ **59 / 59** |
| Step 3 `test_answer_intake_reevaluation.py` | ✅ **40 / 40** |
| Step 4 `test_answer_intake_preview.py` | ✅ **53 / 53** |
| **All MOGO-020** | ✅ **152 / 152** |
| Focused MOGO-019 | ✅ **222 / 222** |
| Canonical `tests/run_all.sh` | ✅ **19 suites · 1,160 / 1,160 · 0 errors** |
| Platform | ✅ **25 suites · 1,049 / 1,049 · 0 errors** |
| Protected ALEX drift | ✅ **0** — 63 functions, 4 constants byte-identical |
| Campaign C1 | ✅ intact |
| Live evidence integrity | ✅ 0 / 0 / 0 / 0 |

Production state re-verified after the battery: 281 questions (280/1), `answerEvidenceIds` populated
**0**, links **416**, proposals **0**, lifecycle **4,472**, EQ lifecycle events **0**,
`XCONTRA|20260728|001` `open`/`blocking`/`null`/`null`, `EQ|20260727|015` untouched, TJR
**BLOCKED / 17**, paper and live-money **NOT AUTHORIZED**, research authorization **2 sources,
metadata-only**. **No silent rebaseline.**

## S5.9 Roadmap item

Searched the repository (`docs/ROADMAP.md`, `docs/trader-intelligence/governance/RESEARCH-ROADMAP.md`,
`docs/trader-intelligence/proposals/*`, all `.md`/`.json`) for
**HUMAN-ASSISTED RESEARCH INGESTION & DECISION-DIFFERENCE ANALYSIS** and for
"decision-difference" / "decision difference": **zero matches.**

> **PENDING DOCUMENTATION-ONLY ROADMAP UPDATE.**

Not implemented here, and no feature work for it entered this commit gate.

## S5.10 Commit-readiness decision

### 🟡 YELLOW — COMMIT BLOCKED BY ONE IDENTIFIED MOGO-020 ISSUE

Everything else is clean: all authoritative gates pass, production is byte-for-byte untouched,
coupling is proven absent at both import and call level, and every introduced behaviour is covered
by 152 focused tests. The block is narrow and named: **§S5.3.1, the unpreviewed public writer.**

I did not classify GREEN because §3 asked for a confirmation I cannot honestly give, and the gap is
in exactly the guarantee Step 4 was built to provide.

**Recommended path:** authorize the §S5.3.1 remedy (rename the three `record_*` to `_record_*`,
update test call sites, no logic change), re-run the battery, then commit as GREEN.

### Proposed commit scope (once unblocked)

```
docs/trader-intelligence/evidence/schema/evidence-lifecycle-event.schema.json   (modified)
scripts/trader_intelligence/evidence_common.py                                  (modified)
scripts/trader_intelligence/validate_evidence.py                                (modified)
scripts/trader_intelligence/answer_intake.py                                    (new)
tests/trader_intelligence/test_answer_intake.py                                 (new)
tests/trader_intelligence/test_answer_intake_reevaluation.py                    (new)
tests/trader_intelligence/test_answer_intake_preview.py                         (new)
MOGO_020_GOVERNED_RESEARCH_ANSWER_INTAKE.md                                     (new)
```

**Excluded:** `MOGO-019-ALEX-IG-CASE-002-REPORT.md` — unrelated pre-existing artifact, not part of
this milestone.

### Proposed commit message

```
MOGO-020 Steps 1-4: governed research answer intake foundation

Adds a governed path for recording HUMAN research decisions about
EvidenceQuestions and ContradictionRecords, with a deterministic
preview/commit boundary. Fixtures only -- no production record processed.

- EvidenceQuestion adjudication (accepted / rejected / uncertain), mapped
  onto existing question statuses; no new status invented
- Direct-trader clarification recorded as CANDIDATE evidence only; it never
  answers its own question, and fails closed without preserved source
- Operator contradiction rulings that leave both source claims byte-identical
- Read-only reevaluation reusing corpus_view/eligibility/research_plan
- Preview/commit boundary bound by a deterministic state fingerprint, so a
  stale approval cannot write against changed state

Lifecycle gains EVIDENCE_QUESTION (schema enum + eventId pattern + constants),
with "reviewed" as its genesis event -- questions have never emitted "created",
and no synthetic history was backdated onto the 281 existing records.

The proposal pipeline stays unreachable: extraction_pipeline and
rule_candidate_proposals are absent from this module's entire transitive
import closure, and link/confidence functions are never called.

Verified: MOGO-020 152/152, MOGO-019 focused 222/222, canonical 1160/1160,
platform 1049/1049, ALEX drift 0, C1 intact, evidence integrity clean.
Production unchanged: 281 questions (280 unanswered / 1 pre-existing
partially_answered), 416 links, 0 proposals, 0 EvidenceQuestion lifecycle
events, XCONTRA|20260728|001 still open/blocking/unresolved, TJR BLOCKED/17,
paper and live-money NOT AUTHORIZED.
```

### Tag recommendation

**Wait.** A `mogo-020-*` checkpoint tag should not be cut now. The foundation has never been
exercised against production data, the §S5.3.1 issue is open, and the roadmap update is pending. Tag
at final MOGO-020 completion, not at this intermediate checkpoint. A commit on `main` is a
sufficient checkpoint by itself.

## S5.11 `git status`

```
 M docs/trader-intelligence/evidence/schema/evidence-lifecycle-event.schema.json
 M scripts/trader_intelligence/evidence_common.py
 M scripts/trader_intelligence/validate_evidence.py
?? MOGO-019-ALEX-IG-CASE-002-REPORT.md
?? MOGO_020_GOVERNED_RESEARCH_ANSWER_INTAKE.md
?? scripts/trader_intelligence/answer_intake.py
?? tests/trader_intelligence/test_answer_intake.py
?? tests/trader_intelligence/test_answer_intake_preview.py
?? tests/trader_intelligence/test_answer_intake_reevaluation.py
```

HEAD `1c4292e…`, ahead/behind **0/0**. **Nothing committed. Nothing tagged. No live governed intake
performed.**

**Step 5 complete. Operator authorized the §S5.3.1 remedy — applied below.**

---
---

# STEP 5.3.1 — CLOSE THE DIRECT-WRITE BYPASS

**Status:** REMEDY APPLIED · NOTHING COMMITTED · NOTHING TAGGED
**Date:** 2026-08-13
**HEAD:** `1c4292e6ddf8eedca82284bb2ed34e7b73ab427d`

## VERDICT: 🟢 GREEN — READY TO COMMIT

## S531.0 Starting state

Repo `joemogo/forex_hub` · `main` · HEAD `1c4292e…` · `mogo-019-complete^{commit}` = HEAD ·
ahead/behind **0/0**. Steps 1–5 changes understood; Step 5's YELLOW rested solely on the
direct-write bypass; the Instagram report remains a separate unrelated artifact. No additional
unexplained issue was found.

## S531.1 The Step 5 finding

Step 5 proved that the three governed writers were **public** and would write a research decision
with no preview and no token — bypassing the entire Step 4 state-binding boundary:

```
record_question_adjudication without preview -> APPLIED
question answerStatus now -> answered
eligibility now -> ELIGIBLE_FOR_RECONSTRUCTION_DRAFT
```

## S531.2 The remedy — exactly the three renames, no logic change

| Before (public) | After (private) |
|---|---|
| `record_question_adjudication` | `_record_question_adjudication` |
| `record_direct_trader_clarification` | `_record_direct_trader_clarification` |
| `record_contradiction_ruling` | `_record_contradiction_ruling` |

Applied with a negative-lookbehind rename so an already-private name could never be double-prefixed;
verified afterwards that **zero** bare names and **zero** `__record_` doubles remain.

**No semantic logic was changed.** Every fail-closed check these functions ever performed — human
actor, corpus isolation, provenance completeness, hash verification, legal prior state, idempotency,
post-condition — is untouched and still enforced.

### Exact call sites updated — 62 across 4 files

| File | `..._question_adjudication` | `..._direct_trader_clarification` | `..._contradiction_ruling` | Total |
|---|---|---|---|---|
| `scripts/trader_intelligence/answer_intake.py` | 4 | 3 | 2 | **9** |
| `tests/trader_intelligence/test_answer_intake.py` | 13 | 6 | 19 | **38** |
| `tests/trader_intelligence/test_answer_intake_reevaluation.py` | 7 | 2 | 4 | **13** |
| `tests/trader_intelligence/test_answer_intake_preview.py` | 1 | 0 | 1 | **2** |
| | | | | **62** |

The module docstring was rewritten to describe the real public boundary
(`preview` → approval → `commit` → private writer → read-only reevaluation) and to record *why*
these three became private, so the reason survives in the code rather than only in this report.

**No existing Step 2 validation test was weakened.** All 59 still run, still against the same
writers, now under their private names — plus a new test that explicitly re-proves the private path
is still fully validated.

## S531.3 Commit is now the only public write authority

Public surface of `answer_intake` after the remedy — **6 callables, exactly one of which mutates**:

| Callable | Mutating? |
|---|---|
| `preview` | ❌ read-only |
| `commit` | ✅ **the only public writer** |
| `reevaluate` | ❌ read-only |
| `blocker_key` | ❌ pure |
| `preview_token` | ❌ pure |
| `main` | CLI — enforces `--preview` XOR `--commit-token` |

Enforced three ways in test:

* **structural** — the set of public `FunctionDef`s is asserted to be exactly those six, so adding a
  new public writer fails the suite;
* **existence** — `hasattr(ai, "record_*")` is asserted **False** and `hasattr(ai, "_record_*")`
  **True**;
* **behavioural** — calling every public read-only entry point leaves the evidence root
  byte-identical.

No new public wrapper was created. The `_record_*` functions remain callable by the fixture tests as
implementation detail, which is what §2 permits.

**The Step 5 hazard, re-run verbatim:**

```
CLOSED -- AttributeError: module 'answer_intake' has no attribute 'record_question_adjudication'
  question answerStatus -> unanswered
  eligibility          -> BLOCKED
  proposals            -> 0
```

## S531.4 CLI boundary retained

`--preview` XOR `--commit-token` remains a required mutually-exclusive argparse group. A new test
invokes `main()` with a mutating subcommand naming neither side, for both `adjudicate` and
`rule-contradiction`, and asserts `SystemExit(2)` — argparse's usage error — with the target
question still `unanswered` afterwards. Preview writes nothing; commit requires a token; stale and
tampered commits write nothing.

## S531.5 Regression coverage added — `TestNoPublicDirectWriteBypass`, 7 tests

| Test | Proves |
|---|---|
| `test_old_public_writers_no_longer_exist` | the three public names are gone; the private ones exist |
| `test_the_only_public_mutating_callables_are_commit` | public `FunctionDef` set is exactly the six above |
| `test_no_public_callable_writes_except_commit` | every public read-only path leaves the root byte-identical |
| `test_private_writers_are_still_fully_validated` | private path still refuses `pipeline` actor and foreign-corpus evidence |
| `test_supported_cli_cannot_perform_a_bare_direct_write` | argparse exits 2 for both mutating subcommands |
| `test_the_supported_path_still_works_end_to_end` | preview → commit still reaches `ELIGIBLE` |
| `test_the_supported_path_still_fails_closed_on_stale_state` | materially changed state still refuses the commit |

## S531.6 Full foundation battery

| Gate | Before 5.3.1 | After 5.3.1 |
|---|---|---|
| Step 2 `test_answer_intake.py` | 59/59 | ✅ **59 / 59** |
| Step 3 `test_answer_intake_reevaluation.py` | 40/40 | ✅ **40 / 40** |
| Step 4 + 5.3.1 `test_answer_intake_preview.py` | 53/53 | ✅ **60 / 60** (+7) |
| **Total MOGO-020** | 152/152 | ✅ **159 / 159** |
| Focused MOGO-019 | 222/222 | ✅ **222 / 222** |
| Canonical | 1,160/1,160 | ✅ **1,160 / 1,160**, 0 errors |
| Platform | 1,049/1,049 | ✅ **1,049 / 1,049**, 0 errors |
| Protected ALEX drift | 0 | ✅ **0** (63 fn, 4 const) |
| Campaign C1 | intact | ✅ intact |
| Evidence integrity | clean | ✅ 0 / 0 / 0 / 0 |

**No new failure.**

### Production state — unchanged

| Item | Value |
|---|---|
| EvidenceQuestions | **281** (280 unanswered / 1 pre-existing partially_answered) |
| `answerEvidenceIds` populated | **0** |
| EvidenceLinks | **416** |
| RuleCandidateProposal | **0** |
| Lifecycle events | **4,472** |
| Production `EVIDENCE_QUESTION` lifecycle events | **0** |
| `XCONTRA\|20260728\|001` | `open` / `blocking` / `resolution: null` / `reviewedAt: null` |
| `EQ\|20260727\|015` | `partially_answered` / `open` / `[]` — untouched |
| TJR | **BLOCKED / 17** |
| TJR paper trading | NOT AUTHORIZED |
| Live-money trading | NOT AUTHORIZED |
| ALEX | unmodified, drift 0, cutoff `2026-08-11T02:43:57.894Z` |
| Research authorization | 2 sources, metadata-only — not widened |

## S531.7 Pre-existing findings — still carried, still unrepaired

1. `test_graph.py::test_expected_node_and_edge_counts` — stale TRADER snapshot (3 vs 5), in no gate;
2. the three `test_evidence`/`test_phase1b`/`test_phase7a` "production tree is empty" assertions —
   re-verified this step as still **exactly 3**, in no gate;
3. `EQ|20260727|015` — `partially_answered` with empty `answerEvidenceIds`, committed at `c03f35e`;
4. **85 live `INTAKE_MANIFEST` lifecycle events violating the schema `entityType` enum / `eventId`
   pattern** — pre-existing code/schema drift, recorded in `evidence_common.py`.

None touched. This remedy was not expanded.

## S531.8 Diff stat

**Tracked (modified): `+57 / −3` across 3 files — unchanged since Step 2.**

```
docs/.../schema/evidence-lifecycle-event.schema.json   |  5 ++-
scripts/trader_intelligence/evidence_common.py         | 49 +++++++++++++-
scripts/trader_intelligence/validate_evidence.py       |  6 +++
3 files changed, 57 insertions(+), 3 deletions(-)
```

**Untracked (new):**

| File | Lines | Δ from Step 5 |
|---|---|---|
| `scripts/trader_intelligence/answer_intake.py` | 1,116 | +17 (docstring) |
| `tests/trader_intelligence/test_answer_intake.py` | 778 | 0 |
| `tests/trader_intelligence/test_answer_intake_reevaluation.py` | 708 | 0 |
| `tests/trader_intelligence/test_answer_intake_preview.py` | 700 | +96 (7 tests) |

Step 5.3.1's entire production footprint is **3 renames + 17 docstring lines**. No tracked file was
touched.

## S531.9 Revised commit-readiness classification

### 🟢 GREEN — READY TO COMMIT

Each §7 condition confirmed independently, not inferred from a passing suite:

| Condition | Confirmation |
|---|---|
| **No supported bare direct-write entry point** | public `FunctionDef` set is exactly `{preview, commit, reevaluate, blocker_key, preview_token, main}`; the Step 5 hazard now raises `AttributeError`; CLI exits 2 without `--preview`/`--commit-token` |
| **Preview/token binding mandatory for supported writes** | `commit()` is the sole public writer and refuses a missing, empty, fabricated or stale token |
| **Commit independently revalidates** | `_plan_*` re-runs from disk before the token is compared; a tampered hash fails on hash verification *first* |
| **Proposal/strategy/backtest/paper unreachable** | `extraction_pipeline`, `rule_candidate_proposals`, `annotation_pipeline`, `ingest`, `strategy_blueprint` absent from the entire 12-module transitive import closure; `link_evidence_to_claim`/`recompute_claim_confidence` never called; a full flow reaching `ELIGIBLE` still yields 0 proposals and 0 links |

### Proposed commit scope

```
docs/trader-intelligence/evidence/schema/evidence-lifecycle-event.schema.json   (modified)
scripts/trader_intelligence/evidence_common.py                                  (modified)
scripts/trader_intelligence/validate_evidence.py                                (modified)
scripts/trader_intelligence/answer_intake.py                                    (new)
tests/trader_intelligence/test_answer_intake.py                                 (new)
tests/trader_intelligence/test_answer_intake_reevaluation.py                    (new)
tests/trader_intelligence/test_answer_intake_preview.py                         (new)
MOGO_020_GOVERNED_RESEARCH_ANSWER_INTAKE.md                                     (new)
```

**Excluded:** `MOGO-019-ALEX-IG-CASE-002-REPORT.md` — unrelated pre-existing artifact.

### Proposed commit message

```
MOGO-020 Steps 1-5.3.1: governed research answer intake foundation

Adds a governed path for recording HUMAN research decisions about
EvidenceQuestions and ContradictionRecords, behind a deterministic
preview/commit boundary. Fixtures only -- no production record processed.

- EvidenceQuestion adjudication (accepted / rejected / uncertain), mapped
  onto existing question statuses; no new status invented
- Direct-trader clarification recorded as CANDIDATE evidence only; it never
  answers its own question, and fails closed without preserved source
- Operator contradiction rulings that leave both source claims byte-identical
- Read-only reevaluation reusing corpus_view/eligibility/research_plan
- preview() reports what an action would do and issues a token bound to the
  exact reviewed state; commit() revalidates from disk and refuses a stale
  token. commit() is the ONLY public mutating entry point -- the primitive
  writers are private, so there is no supported way to skip review.

Lifecycle gains EVIDENCE_QUESTION (schema enum + eventId pattern + constants),
with "reviewed" as its genesis event -- questions have never emitted "created",
and no synthetic history was backdated onto the 281 existing records.

The proposal pipeline stays unreachable: extraction_pipeline and
rule_candidate_proposals are absent from this module's entire transitive
import closure, and link/confidence functions are never called.

Verified: MOGO-020 159/159, MOGO-019 focused 222/222, canonical 1160/1160,
platform 1049/1049, ALEX drift 0, C1 intact, evidence integrity clean.
Production unchanged: 281 questions (280 unanswered / 1 pre-existing
partially_answered), 416 links, 0 proposals, 0 EvidenceQuestion lifecycle
events, XCONTRA|20260728|001 still open/blocking/unresolved, TJR BLOCKED/17,
paper and live-money NOT AUTHORIZED.
```

### Tag recommendation — still WAIT

Unchanged from Step 5. The foundation has never been exercised against production data and the
roadmap update is pending; a `mogo-020-*` tag belongs at final MOGO-020 completion, not at this
intermediate checkpoint. A commit on `main` is a sufficient checkpoint.

## S531.10 Roadmap

At the time of Step 5.3.1, **HUMAN-ASSISTED RESEARCH INGESTION & DECISION-DIFFERENCE ANALYSIS**
remained PENDING DOCUMENTATION-ONLY ROADMAP UPDATE. That documentation task has since been
executed — see **§S532 Roadmap Update** below. No feature work entered this remedy.

## S531.11 `git status`

```
 M docs/trader-intelligence/evidence/schema/evidence-lifecycle-event.schema.json
 M scripts/trader_intelligence/evidence_common.py
 M scripts/trader_intelligence/validate_evidence.py
?? MOGO-019-ALEX-IG-CASE-002-REPORT.md
?? MOGO_020_GOVERNED_RESEARCH_ANSWER_INTAKE.md
?? scripts/trader_intelligence/answer_intake.py
?? tests/trader_intelligence/test_answer_intake.py
?? tests/trader_intelligence/test_answer_intake_preview.py
?? tests/trader_intelligence/test_answer_intake_reevaluation.py
```

HEAD `1c4292e…`, ahead/behind **0/0**. **Nothing committed. Nothing tagged. No live governed intake
performed.**

**Step 5.3.1 complete and re-classified GREEN.**

---
---

# §S532 — DOCUMENTATION-ONLY ROADMAP UPDATE

**Status:** DOCUMENTATION ONLY · NO CODE · NO TESTS · NOTHING COMMITTED
**Date:** 2026-08-13

## S532.1 Authoritative roadmap/backlog located

Three candidates were examined:

| Candidate | Verdict |
|---|---|
| `docs/ROADMAP.md` | ❌ **release-scoped** — app versions, release phases, strategy rollout. A research-capability backlog item does not belong here. |
| `docs/trader-intelligence/governance/RESEARCH-ROADMAP.md` | ❌ **milestone-scoped** — titled "MOGO-004 — Research Roadmap", derived from the hypothesis registry and replay campaign plan. Adding a cross-milestone future capability would misattribute it to MOGO-004. |
| **`docs/trader-intelligence/proposals/`** | ✅ **the authoritative backlog.** Its `README.md` is titled "Trader Intelligence — Proposals and Backlog", indexes `BACKLOG-001/002/003` in a status table, and carries the dependency-order diagram. |

**No competing roadmap was created.** The item was filed in the existing structure, using the
existing `BACKLOG-00N` naming, document shape and trigger/dependency conventions of `BACKLOG-003`.

## S532.2 Files changed

| File | Change |
|---|---|
| `docs/trader-intelligence/proposals/BACKLOG-004-human-assisted-research-ingestion.md` | **NEW** — the requirement, 10 sections |
| `docs/trader-intelligence/proposals/README.md` | +1 index-table row; +6 lines extending the dependency-order diagram and stating why the milestone number is unassigned |
| `MOGO_020_GOVERNED_RESEARCH_ANSWER_INTAKE.md` | this section; §S531.10 updated to point here |

## S532.3 Section added

`BACKLOG-004` records, in the operator's stated terms:

1. **Why it is written down** — conversation is not a durable record; this must be discoverable from
   the repository alone
2. **Objective** — natural owner contribution flowing into governed research; all 13 candidate input
   types; the full long-term workflow, with the explicit note that the goal is removing the *manual
   transfer* step, never shortening the governance that follows
3. **Scientific separation** — `OBSERVED FACT ≠ INTERPRETATION ≠ HYPOTHESIS ≠ VALIDATED FINDING ≠
   STRATEGY RULE`; a screenshot is evidence, not proof; **ingestion may become autonomous, strategy
   mutation must not**
4. **Decision-Difference Case** — neither side assumed correct; all 16 reconstruction fields; all 10
   candidate classifications, explicitly marked *design candidates, not schema enums to implement
   now*; the 7 dataset questions
5. **General research architecture** — ALEX, TJR, ICT, CRT, approved sources, owner observations and
   autonomous MOGO research into **one** library with per-source provenance and corpus isolation; no
   separate owner/ChatGPT/MOGO knowledge systems
6. **Standardized research-package interface** — required expressiveness across artifact, identity,
   attribution, content, integrity and linkage; explicitly *not* a schema
7. **Dependencies** — a 14-row status table; **"MOGO-020 provides foundational dependencies but does
   not implement this future capability"**; and the preserved Lane B → Lane A finding, quoted from
   `MOGO_019_AUTONOMOUS_RESEARCH_UNDERSTANDING.md`, that this is *not* a simple adapter problem and
   that human semantic extraction governance is a deliberate checkpoint
8. **ALEX protection** — the full 11-step evidence → forward-paper route, "no shortcuts", and the
   note that a Decision-Difference case arriving after a missed winner is exactly the pressure under
   which this discipline gets violated
9. **Placement** — the eligibility wording, and a 5-step suggested ordering
10. **What this document does NOT do** — authorizes nothing, designs nothing, numbers nothing,
    widens no authorization, weakens no gate

## S532.4 Dependencies recorded

Governed EvidenceItem/Claim handling · EvidenceQuestion architecture · governed answer/adjudication
intake · contradiction governance · lifecycle/audit history · provenance/hashing · corpus isolation ·
deterministic reevaluation · preview/explicit-commit boundary · artifact-wrapper/research-intake
governance · standardized research-package interface · safe machine-to-machine ingestion ·
deduplication · source authorization controls.

Each carries a current status. **Three are marked ❌ not built** (artifact-wrapper governance,
research-package interface, machine-to-machine ingestion) and two ⚠️ partial — which is precisely
why the milestone number is deferred.

## S532.5 Milestone numbering

**Intentionally deferred.** Stated in the document, in the README index row, and in the README
dependency note. Assigning a number would imply a sequence position three missing dependencies do
not support. The recorded eligibility condition is:

> **Eligible after governed research intake, standardized research-package interface, and
> artifact-ingestion governance mature.**

## S532.6 Confirmations

* ✅ **No implementation occurred.** No schema, no enum, no code path, no test for this capability.
* ✅ **MOGO-020 executable and test files untouched by this task** — `answer_intake.py`,
  `test_answer_intake.py`, `test_answer_intake_reevaluation.py`, `test_answer_intake_preview.py`,
  `evidence_common.py`, `validate_evidence.py` and the lifecycle schema are byte-identical to their
  Step 5.3.1 state.
* ✅ **ALEX unchanged** — drift 0, forward activation cutoff `2026-08-11T02:43:57.894Z` unchanged.
* ✅ **TJR unchanged** — RESEARCH ONLY, BLOCKED / 17.
* ✅ **Trading authority unchanged** — paper and live-money NOT AUTHORIZED.
* ✅ **Research authorization unchanged** — 2 sources, metadata-only. Not widened.
* ✅ **No production research processed.**

## S532.7 Diff stat

```
 docs/trader-intelligence/proposals/README.md       |  9 ++++
 docs/trader-intelligence/proposals/BACKLOG-004-human-assisted-research-ingestion.md | new, 261 lines
 MOGO_020_GOVERNED_RESEARCH_ANSWER_INTAKE.md        | this section
```

Full tracked diff after this task: **4 files, +66 / −3** — the three MOGO-020 code/schema files
(**+57 / −3**, unchanged since Step 2) plus `proposals/README.md` (**+9**, documentation).

Tracked code diff remains **+57 / −3 across 3 files** — unchanged since MOGO-020 Step 2.

## S532.8 `git status`

```
 M docs/trader-intelligence/evidence/schema/evidence-lifecycle-event.schema.json
 M docs/trader-intelligence/proposals/README.md
 M scripts/trader_intelligence/evidence_common.py
 M scripts/trader_intelligence/validate_evidence.py
?? MOGO-019-ALEX-IG-CASE-002-REPORT.md
?? MOGO_020_GOVERNED_RESEARCH_ANSWER_INTAKE.md
?? docs/trader-intelligence/proposals/BACKLOG-004-human-assisted-research-ingestion.md
?? scripts/trader_intelligence/answer_intake.py
?? tests/trader_intelligence/test_answer_intake.py
?? tests/trader_intelligence/test_answer_intake_preview.py
?? tests/trader_intelligence/test_answer_intake_reevaluation.py
```

HEAD `1c4292e…`, ahead/behind **0/0**. **Nothing committed. Nothing tagged.**

The MOGO-020 commit scope proposed in §S531.9 should now additionally include
`docs/trader-intelligence/proposals/BACKLOG-004-human-assisted-research-ingestion.md` and
`docs/trader-intelligence/proposals/README.md`.

**Roadmap update complete. Checkpoint committed as `634f775c1b759405c1e0898e081825859293325e` and
pushed to `origin/mogo-main`. MOGO-020 is NOT complete — this was the foundation checkpoint only.**

---
---

# STEP 6 — FIRST CONTROLLED PRODUCTION PREVIEW

**Status:** PREVIEW ONLY · ZERO PRODUCTION MUTATION · AWAITING ONE OPERATOR DECISION
**Date:** 2026-08-13
**HEAD:** `634f775c1b759405c1e0898e081825859293325e`

## S6.0 Verification

| Check | Expected | Observed | ✓ |
|---|---|---|---|
| Repo / branch | forex_hub / `main` | ✅ | ✅ |
| HEAD | `634f775…` | `634f775c1b759405c1e0898e081825859293325e` | ✅ |
| Ahead / behind `origin/mogo-main` | 0 / 0 | `0  0` | ✅ |
| ALEX drift | 0 | **0** — 63 functions, 4 constants | ✅ |
| Campaign C1 | intact | canonical 1,160/1,160 | ✅ |
| TJR eligibility | BLOCKED / 17 | **BLOCKED / 17** | ✅ |
| EvidenceQuestions | 281 | **281** | ✅ |
| EvidenceLinks | 416 | **416** | ✅ |
| RuleCandidateProposal | 0 | **0** | ✅ |
| Production EQ lifecycle events | 0 | **0** | ✅ |

The full regression battery was not re-run: the tree is byte-identical to the committed checkpoint
(`git status` shows only the untracked Instagram report), and no code changed. ALEX drift and the
canonical gate were re-run because they are cheap relative to their value.

## S6.1 Candidate selection — 3 inspected

TJR carries **18** unresolved EvidenceQuestions. Three were inspected with the governed
candidate-evidence search (`candidate_search.py`, read-only nomination).

| Candidate | Subject | Why not / why chosen |
|---|---|---|
| `EQ\|20260727\|012` | `CLAIM\|TJR\|20260727\|002` — `session_rule`, *"Trades are always taken around the New York Stock Exchange open"* | ❌ **Rejected.** The only nominated evidence (*"I'm always trading New York Stock Exchange open"*) is about **session**, not timeframe. The question asks for a timeframe on a rule whose scope is a session; the honest answer is closer to "the question is a category artifact", which none of the three decisions expresses cleanly. A poor first exercise. |
| `EQ\|20260727\|013` | `CLAIM\|TJR\|20260727\|027` — `entry_rule`, missing invalidation | ❌ **Rejected.** `entry_rule` is a **REQUIRED** category, so the consequence is not narrow. The nominated evidence describes *entry confirmation*, not invalidation; the closest material (*"as long as we are still staying in the current trend"*, *"the five minute trend is still intact. We haven't closed underneath this low yet"*) only hints at invalidation. Genuinely uncertain, and higher-stakes. |
| **`EQ\|20260727\|014`** | `CLAIM\|TJR\|20260727\|029` — `target_rule`, *"Targets are the previous draws on liquidity in the direction of the trade"* | ✅ **Chosen.** |

`EQ|20260727|014` satisfies every constraint: unanswered · answerable from existing governed
evidence · no acquisition required · not `EQ|20260727|015` · does not depend on
`XCONTRA|20260728|001` (which concerns `CLAIM|TJR|20260727|006`) · and `target_rule` is an
**optional** category, so the consequence is exactly one blocker.

## S6.2 The proposed decision, separated

### Observed evidence — what the source actually establishes

| Evidence | Directness | Verbatim |
|---|---|---|
| `EV\|EVSRC\|TJR\|20260727\|001\|012` | `direct_explicit` | *"whether that's from 1 hour highs and lows, 4hour highs and lows, or session highs and lows, that's what I'm looking for for my draws on liquidity"* |
| `EV\|EVSRC\|TJR\|20260727\|001\|043` | `direct_demonstrated` | *"You guys can target these five minute highs right here. You can target Asia session highs right here. And then previous day highs right here."* |

Both are TJR-corpus, `partially_verified` provenance, `high` extraction certainty, hash-verified.

### Interpretation — what can reasonably be concluded

The target rule's *draws on liquidity* are drawn from **multiple explicitly named timeframes** —
1-hour, 4-hour, session, five-minute, and previous-day levels. The rule is therefore **not scoped to
a single timeframe**, and the claim's null `timeframe` is **correct rather than missing**: the
absence of one timeframe is the answer, not a gap.

### Uncertainty — what remains unsupported

* The source never states an execution timeframe on which target *evaluation* occurs.
* The source gives **no selection rule** for choosing among the candidate draws when several exist
  in the same direction. `EV|001|043` says *"you guys can target"* — permissive, not mechanical.
* `EV|001|012` describes draws on liquidity in general; it is linked to
  `CLAIM|TJR|20260727|009`, not to the subject claim. It is cited as the source's own definition of
  the term the subject claim uses — **not** as direct support for the target rule.
* Answering this question does **not** make `target_rule` mechanically specifiable. A separate,
  unraised question about target *selection* would remain open.

### Proposed human decision

**ACCEPT** `EV|EVSRC|TJR|20260727|001|012` + `EV|EVSRC|TJR|20260727|001|043` as answering
`EQ|20260727|014`, on the reading that the rule is deliberately multi-timeframe.

## S6.3 The real preview (production, read-only)

`answer_intake.preview()` run against `docs/trader-intelligence/evidence`.

```
action          : question_adjudication      target : EQ|20260727|014
actor           : operator:joemogollon       decision : accepted   (PROPOSED)
corpusTraderId  : TJR
evidenceIds     : EV|EVSRC|TJR|20260727|001|012, EV|EVSRC|TJR|20260727|001|043
wouldWrite      : True        isAuthorization : False

CHANGED FIELDS (forecast only)
  answerEvidenceIds  [] -> ['EV|...|012', 'EV|...|043']
  answerStatus       'unanswered' -> 'answered'
  researchStatus     'open' -> 'answered'
  resolvedAt         None -> '2026-08-13T18:10:15Z'

LIFECYCLE EVENT THAT WOULD BE APPENDED
  LCEVT|EVIDENCE_QUESTION|EQ|20260727|014|001
  reviewed | actor operator:joemogollon | unanswered -> answered

ELIGIBILITY EFFECT
  before  BLOCKED / 17      after  BLOCKED / 16
  eligibility status changes : False
  blockers removed : ['BLOCKING_QUESTION|EQ|20260727|014']
  blockers added   : []          retained : 16
  routing changed  : True

previewToken : fb9a965fc62eadba134d58d803aa53fed3d64709648915f2dad611a1bda859f4
```

This would be the **first `EVIDENCE_QUESTION` lifecycle event in production** — sequence `001`, with
`reviewed` as its genesis event, exactly as the Step 2 lifecycle extension designed.

## S6.4 Zero-mutation proof

A SHA-256 digest over every path+bytes under `docs/trader-intelligence/evidence/` was taken
immediately before and after the preview: **identical**.

| Item | Persisted value after preview |
|---|---|
| `EQ\|20260727\|014` | `answerStatus: unanswered` · `researchStatus: open` · `answerEvidenceIds: []` · `resolvedAt: null` — **unchanged** |
| EvidenceQuestions | **281** (280 unanswered / 1 pre-existing partially_answered) |
| EvidenceLinks | **416** |
| RuleCandidateProposal | **0** |
| Claims / items / sources | **341 / 416 / 12** — unchanged |
| Lifecycle events | **4,472**; `EVIDENCE_QUESTION` events **0** |
| `XCONTRA\|20260728\|001` | `open` / `blocking` / `resolution: null` / `reviewedAt: null` |
| Evidence integrity | `{INFO:0, WARNING:0, ERROR:0, FATAL:0}` |
| **TJR persisted eligibility** | **BLOCKED / 17** |
| `git status` | only the untracked Instagram report — **no file changed** |

**Forecast vs persisted:** the preview *forecasts* 16 blockers. Persisted state is still **17**.
Nothing about the forecast has been written, and it never will be unless a human commits it with the
token above.

No strategy, backtest, paper-trade or trading artifact was created. ALEX untouched, drift 0. TJR
authority unchanged. Research authorization unchanged at 2 sources, metadata-only.

## S6.5 Status

**Awaited exactly one operator decision on `EQ|20260727|014`. Operator responded `ACCEPT` — see
Step 7.**

---
---

# STEP 7 — FIRST GOVERNED PRODUCTION ADJUDICATION

**Status:** COMMITTED TO PRODUCTION RESEARCH STATE · ONE ADJUDICATION ONLY · NOT GIT-COMMITTED
**Date:** 2026-08-13
**HEAD:** `634f775c1b759405c1e0898e081825859293325e` (unchanged — no git commit made)

## S7.1 The operator decision

| Field | Value |
|---|---|
| **Operator** | Joe (`operator:joemogollon`) |
| **Decision** | **ACCEPT** |
| **EvidenceQuestion** | `EQ\|20260727\|014` |
| **Preview token** | `fb9a965fc62eadba134d58d803aa53fed3d64709648915f2dad611a1bda859f4` |
| **Evidence accepted** | `EV\|EVSRC\|TJR\|20260727\|001\|012` (`direct_explicit`) · `EV\|EVSRC\|TJR\|20260727\|001\|043` (`direct_demonstrated`) |

### The exact narrow finding accepted

> **TJR's liquidity-target concept is not scoped to a single timeframe.**

### What this approval explicitly does NOT establish

Recorded verbatim from the operator's authorization, because the boundary of an accepted answer
matters as much as the answer:

* no mechanical target-selection rule;
* no execution timeframe;
* no target priority;
* no target-selection criteria;
* no additional inference beyond the Step 6 preview.

## S7.2 Pre-commit state check

Material state was re-verified against the reviewed preview **before** invoking `commit()`:

| Check | Expected | Observed | ✓ |
|---|---|---|---|
| `EQ\|20260727\|014` | unanswered | `unanswered` / `open` / `[]` / `null` | ✅ |
| EvidenceLinks | 416 | **416** | ✅ |
| RuleCandidateProposal | 0 | **0** | ✅ |
| Production EQ lifecycle events | 0 | **0** | ✅ |
| TJR | BLOCKED / 17 | **BLOCKED / 17** | ✅ |
| `XCONTRA\|20260728\|001` | unchanged | `open` / `blocking` / `null` / `null` | ✅ |
| ALEX drift | 0 | **0** — 63 functions, 4 constants | ✅ |
| Campaign C1 | intact | canonical 1,160/1,160 | ✅ |

The token was **not** stale and no material reviewed state had changed, so the commit proceeded.

## S7.3 The commit

Executed through the **public `commit()` path** with the exact approved token and byte-identical
action arguments. No private writer was invoked directly.

```
outcome      : APPLIED
action       : question_adjudication
questionId   : EQ|20260727|014
decision     : accepted
evidenceIds  : ['EV|EVSRC|TJR|20260727|001|012', 'EV|EVSRC|TJR|20260727|001|043']
previewToken : fb9a965fc62eadba134d58d803aa53fed3d64709648915f2dad611a1bda859f4
```

## S7.4 Before / after

| Field | Before | After |
|---|---|---|
| `answerStatus` | `unanswered` | **`answered`** |
| `researchStatus` | `open` | **`answered`** |
| `answerEvidenceIds` | `[]` | **`['EV\|…\|012', 'EV\|…\|043']`** |
| `resolvedAt` | `null` | **`2026-08-13T18:17:18Z`** |

Every other field on the record — `questionId`, `questionText`, `questionType`, `priority`,
`reason`, `blockingStatus`, `claimId`, `evidenceIds`, `sourceIds`, `createdAt`, `schemaVersion` —
is unchanged.

## S7.5 Lifecycle event

**`LCEVT|EVIDENCE_QUESTION|EQ|20260727|014|001`** — the **first `EVIDENCE_QUESTION` lifecycle event
in production**, sequence `001`, with `reviewed` as its genesis event exactly as the Step 2
extension designed.

```
entityType : EVIDENCE_QUESTION      eventType : reviewed
actor      : operator:joemogollon
prior→new  : unanswered → answered
timestamp  : 2026-08-13T18:17:18Z
metadata   : decision=accepted
             decisionFingerprint=99eca7b20083bb362f466a4938d03a13a1c8f47eee7604437dcf5ff734ea6cdb
             evidenceIds=[EV|…|012, EV|…|043]
             corpusTraderId=TJR
             intakeSchemaVersion=mogo.governed-answer-intake.v1
```

The operator's full rationale is preserved verbatim in the event's `reason`.

## S7.6 Verified persisted effects

| Check | Expected | Observed | ✓ |
|---|---|---|---|
| `EQ\|20260727\|014` | answered | **answered** | ✅ |
| Approved evidence recorded | both IDs | both, sorted | ✅ |
| Resolved/reviewed metadata | recorded | `resolvedAt` + event | ✅ |
| EVIDENCE_QUESTION lifecycle events | exactly 1 | **1** | ✅ |
| EvidenceLinks | 416 | **416** — unchanged | ✅ |
| RuleCandidateProposal | 0 | **0** | ✅ |
| Claims | unchanged | **341**; `CLAIM\|TJR\|20260727\|029` still `timeframe: null`, `confidenceState: emerging` | ✅ |
| Source evidence | unchanged | items **416**, sources **12** | ✅ |
| `XCONTRA\|20260728\|001` | unchanged | `open` / `blocking` / `null` / `null` | ✅ |
| Deterministic reevaluation | runs | ran post-commit, `available: True` | ✅ |
| TJR blockers | 17 → 16 | **17 → 16** | ✅ |
| TJR eligibility | still BLOCKED | **BLOCKED** | ✅ |
| Strategy / backtest / paper artifact | none | **none** | ✅ |
| TJR paper trading | NOT AUTHORIZED | NOT AUTHORIZED | ✅ |
| Live-money trading | NOT AUTHORIZED | NOT AUTHORIZED | ✅ |
| ALEX drift | 0 | **0** | ✅ |
| Campaign C1 | intact | **1,160 / 1,160** | ✅ |
| Research authorization | unchanged | 3 records, still 2 metadata-only | ✅ |
| Evidence integrity | clean | `{INFO:0, WARNING:0, ERROR:0, FATAL:0}` | ✅ |

**No discrepancy between the approved preview and the persisted effect.** The forecast said
`17 → 16`, `answered`, one lifecycle event, 416 links, 0 proposals. That is exactly what happened.

**Exactly two evidence files changed:**

```
 M docs/trader-intelligence/evidence/questions/EQ_20260727_014.json
?? docs/trader-intelligence/evidence/lifecycle/4410d84db654d65b745e622e6d4f2223.json
```

Question distribution is now **279 unanswered / 1 answered / 1 pre-existing partially_answered**.
Lifecycle total **4,472 → 4,473**.

## S7.7 Idempotency

The identical approved operation was replayed with the same token:

```
outcome                 : DUPLICATE_NOOP
evidence tree unchanged : True   (SHA-256 over every path+bytes under evidence/)
lifecycle events        : 4473 -> 4473
EVIDENCE_QUESTION events: 1  ['LCEVT|EVIDENCE_QUESTION|EQ|20260727|014|001']
question still          : answered / ['EV|…|012', 'EV|…|043']
```

No duplicate adjudication, no duplicate lifecycle event, and **no alteration of legitimate persisted
state** — the replay was a true no-op, detected by `decisionFingerprint` before any write.

## S7.8 What this does and does not mean

**It means:** one of TJR's 17 research blockers is closed by governed evidence, adjudicated by a
named human, with the reasoning and the exact supporting excerpts preserved in append-only history.

**It does not mean:** TJR is closer to tradable in any operational sense. Eligibility is still
**BLOCKED**, with 16 blockers remaining — including `risk_rule` **MISSING**, `setup_requirement`
**CONFLICTED**, `entry_rule` and `stop_rule` **AMBIGUOUS**, and the blocking cross-corpus
contradiction `XCONTRA|20260728|001`. `CLAIM|TJR|20260727|029` still carries `timeframe: null`, which
is now *correct* rather than *missing*: the accepted finding is that the concept is multi-timeframe
by design.

**ACCEPTED ANSWER ≠ STRATEGY RULE** held: 0 proposals, 0 links, 0 claim mutations.

## S7.9 Status

**One production adjudication performed. Stopped.** No further EvidenceQuestion was selected or
previewed.

---

# STEP 8 — CHECKPOINT THE FIRST PRODUCTION ADJUDICATION

**Parent HEAD:** `634f775c1b759405c1e0898e081825859293325e`
**Commit message:** `MOGO-020: record first governed TJR adjudication`
**This is a transaction checkpoint, not milestone completion.**

## S8.1 This is the first successful production governed adjudication

`EQ|20260727|014` is the **first EvidenceQuestion in MOGO's production research library ever
answered through a governed path** — previewed, approved by a named human operator against a
state-bound token, committed through the public `commit()` boundary, and recorded in append-only
history. Every prior answer state in this repository arrived by direct file editing (see the Step 1
finding on `EQ|20260727|015`, which remains in its pre-existing inconsistent state and was not
touched).

`LCEVT|EVIDENCE_QUESTION|EQ|20260727|014|001` is correspondingly the first `EVIDENCE_QUESTION`
lifecycle event in production.

## S8.2 Pre-commit verification

Working tree contained **exactly** the three expected Step 7 changes and nothing else:

```
 M MOGO_020_GOVERNED_RESEARCH_ANSWER_INTAKE.md
 M docs/trader-intelligence/evidence/questions/EQ_20260727_014.json
?? docs/trader-intelligence/evidence/lifecycle/4410d84db654d65b745e622e6d4f2223.json
?? MOGO-019-ALEX-IG-CASE-002-REPORT.md          <- excluded, unrelated
```

The untracked lifecycle file was confirmed to be the correct artifact rather than a stray: its
hash-derived filename recomputes exactly from its own `eventId`
(`evidence_common.lifecycle_event_id_to_filename("LCEVT|EVIDENCE_QUESTION|EQ|20260727|014|001")`
→ `4410d84db654d65b745e622e6d4f2223.json`, **MATCH**).

| Check | Expected | Observed | ✓ |
|---|---|---|---|
| `EQ\|20260727\|014` | answered | **answered / answered** + both evidence IDs | ✅ |
| TJR | BLOCKED / 16 | **BLOCKED / 16** | ✅ |
| EvidenceLinks | 416 | **416** | ✅ |
| RuleCandidateProposal | 0 | **0** | ✅ |
| Production EQ lifecycle events | exactly 1 | **1** — `LCEVT\|EVIDENCE_QUESTION\|EQ\|20260727\|014\|001` | ✅ |
| Lifecycle total | 4,473 | **4,473** | ✅ |
| `XCONTRA\|20260728\|001` | unchanged | `open` / `blocking` / `null` / `null` | ✅ |
| ALEX drift | 0 | **0** — 63 functions, 4 constants | ✅ |
| Campaign C1 | intact | **19 suites · 1,160 / 1,160 · 0 errors** | ✅ |
| Evidence integrity | clean | `{INFO:0, WARNING:0, ERROR:0, FATAL:0}` | ✅ |
| TJR paper trading | NOT AUTHORIZED | NOT AUTHORIZED | ✅ |
| Live-money trading | NOT AUTHORIZED | NOT AUTHORIZED | ✅ |
| Research authorization | unchanged | 3 records, 2 metadata-only | ✅ |

## S8.3 Committed scope — 3 files

| File | Kind |
|---|---|
| `docs/trader-intelligence/evidence/questions/EQ_20260727_014.json` | the adjudicated EvidenceQuestion |
| `docs/trader-intelligence/evidence/lifecycle/4410d84db654d65b745e622e6d4f2223.json` | the append-only lifecycle event |
| `MOGO_020_GOVERNED_RESEARCH_ANSWER_INTAKE.md` | Steps 6–8 record |

**Excluded:** `MOGO-019-ALEX-IG-CASE-002-REPORT.md` — unrelated pre-existing artifact, still
untracked.

No code, no schema, no test, no ALEX file, no authorization file, and no other evidence record is in
this commit.

## S8.4 Status

**MOGO-020 remains ACTIVE and is NOT complete.** No `mogo-020-complete` tag and no
milestone-completion tag was created. No further EvidenceQuestion has been selected or previewed.
16 TJR blockers remain.

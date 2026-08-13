# MOGO-019 — AUTONOMOUS RESEARCH UNDERSTANDING

## STEP 1 — READINESS AUDIT (READ-ONLY)

**Nothing was implemented, modified, acquired, promoted, backtested or traded.**
**Starting checkpoint `ed3cda46602272e6439f780956ff658583d921ea` · MOGO-018 GREEN**

---

# HEADLINE FINDING

**MOGO-019 needs almost no new architecture.** The Knowledge Library already contains a live,
populated, graph-backed representation for **every** scientific object this milestone requires —
source claims, evidence items with explicit source-vs-inference classification, interpretations,
rule candidates, contradictions, ambiguities, gaps and an 18-stage owner-gated promotion ladder.

**~6,600 records and a 2,422-node / 5,109-edge graph already exist.** The correct MOGO-019 Step 2 is
therefore a **narrow vertical slice that reuses this**, not a new subsystem.

**Two genuine gaps** (§I, §M): claims carry **no `strategyFamilyId`** (all 341 are `null`), and there
is a **second, unpopulated schema family** that risks becoming a duplicate strategy identity.

---

# PART A — EXISTING KNOWLEDGE ARCHITECTURE

**Two parallel schema families exist. Only one is live.**

| Family | Location | Schemas | Records | Status |
|---|---|---|---|---|
| **LIVE** | `docs/trader-intelligence/evidence/schema/` + `graph/schema/` | 18 + 6 | **~6,600** | authoritative, graph-built |
| **DECLARED, UNPOPULATED** | `docs/trader-intelligence/schema/` | 12 | **~0** | legacy/aspirational — **do not extend** |

## A.1 The fifteen requested structures

| # | Structure | Schema (live family) | Key fields | Records | Mutability | Auth/Derived | Reusable for MOGO-019? |
|---|---|---|---|---|---|---|---|
| 1 | **Claims** | `claim.schema.json` | `claimId`, `claimType` (19-value enum), `normalizedClaim`, `normalizedFingerprint`, `claimStatus`, `confidenceState`, `traderId`, `strategyFamilyId`, evidence counters | **341** | mutable (counters re-derived) | authoritative | ✅ **directly** |
| 2 | **Evidence items** | `evidence-item.schema.json` | `evidenceId`, `sourceId`, **`directness`**, **`extractionCertainty`**, `extractionMethod`, `exactExcerpt`, `sourceLocator`, `contentHash`, `supersedesEvidenceId` | **416** | append/supersede | authoritative | ✅ **directly — this is the core** |
| 3 | **Concepts** | *no `Concept` type* — approximated by `claim.claimType` + `subjectEntityType`/`subjectEntityId` + graph nodes | — | — | — | — | ⚠️ **approximated, not explicit** |
| 4 | **Schemas** | 18 JSON-Schema files, draft 2020-12 | — | — | immutable | authoritative | ✅ |
| 5 | **Graph relations** | `graph-node/edge.schema.json`, `graph/build/` | 16 node types, `BLUEPRINT_DERIVED_FROM_CLAIM` (1,231), `CLAIM_SUPPORTS_HYPOTHESIS` (1,101), `DERIVED_FROM` (416), `SUPPORTS` (415) | **2,422 nodes / 5,109 edges** | **derived** (rebuildable) | **derived** | ✅ |
| 6 | **Source attribution** | `evidence-source.schema.json`, `BELONGS_TO_TRADER` edges | `traderId`, `canonicalReference`, `titleVerification` | 12 sources / 535 edges | authoritative | authoritative | ✅ |
| 7 | **Provenance** | `evidence-claim-link.schema.json` + `evidence-item` | `linkId`, `evidenceId`, `claimId`, `relationshipType`, `independenceGroup`, `qualityWeight`, `relevanceWeight` | **416** | authoritative | authoritative | ✅ |
| 8 | **Confidence** | `claim.confidenceState`/`confidenceScore`/`confidenceMethod`; `hypothesis.confidence` (9-value) | — | — | derived | derived | ✅ |
| 9 | **Trader identity** | `trader-profile.schema.json`, `traderId` pattern `^[A-Z][A-Z0-9_]*$` | — | 11 profiles | authoritative | authoritative | ✅ |
| 10 | **Strategy-family identity** | `strategy-families/*.json`, `SF\|<TRADER>\|<NAME>` | — | 3 families | authoritative | authoritative | ⚠️ **exists but unused on claims** |
| 11 | **Promotion/state machinery** | `graph/schema/promotion-state.schema.json` + `owner-decision.schema.json` | **18-stage linear ladder** `DISCOVERED → … → LIVE_APPROVED` | **6 OwnerDecisions; 0 records carry `promotionState`** | append-only | authoritative | ✅ **declared, unused — safest possible state** |
| 12 | **Interpretations/inferences** | `hypothesis.schema.json` | `hypothesisId`, `statement`, **`sourceClaimIds`**, `status` (5), `confidence` (9), `assumptions`, `limitations` | **641** | mutable | derived from claims | ✅ **directly** |
| 13 | **Contradictions/conflicts** | `contradiction-record.schema.json` | `claimAId`, `claimBId`, `contradictionType`, **`severity` incl. `blocking`**, `status` (4), `resolution` | **16** | mutable | derived | ✅ **directly** |
| 14 | **Candidate rules** | `rule-candidate-proposal.schema.json` | `originatingClaimIds`, `claimType` (12), **`contradictionStatus`**, **`unresolvedQuestionIds`**, `ownerReviewStatus`, `paperTradingStatus`, `replayStatus`, `supersedesProposalId` | **0 — none ever proposed** | append/supersede | derived | ✅ **directly** |
| 15 | **Mechanical strategy spec** | `strategy-blueprint.schema.json` | `entryLogic`, `exitLogic`, `riskLogic`, `contradictions`, `limitations`, `sourceLineage`, `status` | **11** (ALEX status `DRAFT_RESEARCH_ONLY`) | mutable | derived | ✅ |

**Consumers:** `scripts/trader_intelligence/{validate_evidence,evidence_registry,intake_registry,…}.py`,
the graph builder, and `evidence/reports/`. **No platform-runtime module consumes them.**

---

# PART B — RESEARCH EVIDENCE LANES

## B.1 Identifier semantics — deliberately NOT collapsed

| | **Lane A (Knowledge Library)** | **Lane B (governed acquisition)** |
|---|---|---|
| Source identity | `EVSRC\|<TRADER>\|<DATE>\|<N>` — **one piece of source material** | `SRC\|<provider>\|<12-hex>` — **one educator's channel** |
| Resource identity | *(the EVSRC is the resource)* | `resourceId` — one video, e.g. `8qwEmE1DwYw` |
| Correspondence | one EVSRC ≈ Lane B **`(sourceId, resourceId)` pair** | Lane B `sourceId` alone ≈ Lane A `traderId` |
| Content hash | SHA-256 of a stored **transcript file** | SHA-256 of **exact validated external response body bytes** |

Both lanes have a field spelled `sourceId` meaning **different things**. `research_library.py`
documents this explicitly and never mints an EVSRC identifier.

## B.2 `connector_transport.content_hash` — CONFIRMED UNCHANGED

```python
def content_hash(raw):
    """Deterministic identity of the acquired bytes. Never a timestamp."""
    return hashlib.sha256(raw).hexdigest()
```

**SHA-256 over the exact validated external response body bytes. Not reinterpreted.**

## B.3 The MOGO-018 bridge

`research_library.py` is a **derived, read-only index**: `entries()` (per-stream) and
`corpus_report()` (per-family/stream). It writes nothing, and two reads are byte-identical. It emits
`acceptedContentIdentity` + `acceptedContentIdentityBasis: RAW_EXTERNAL_RESPONSE_BYTES` — **never a
bare `contentHash`** — so Lane A's transcript hash can never be mistaken for Lane B's byte hash.

Attribution (`source-attribution.json`) is the one thing that cannot be derived; its `sourceId` is
**recomputed from `channelUrl` at load time** and refused on mismatch.

**Immutable boundary:** Lane B intake + artifacts are content-addressed and append-only;
`boundaries.PROHIBITED_WRITE_PATHS` refuses `index.html`, `evidence/`, `docs/campaigns/`,
pre-registrations, the replay record and `hypothesis-registry.json`.

---

# PART C — CURRENT ALEX RESEARCH REPRESENTATION

| Record type | ALEX_G |
|---|---|
| Evidence sources | **9** |
| Transcript segments | **134** |
| Evidence items | **280** |
| Claims | **226** |
| Knowledge gaps | **95** |
| Blueprints | **9** (`BLUEPRINT\|ALEX_G\|20260728\|004`, status **`DRAFT_RESEARCH_ONLY`**) |

1. **Artifacts exist** — 9 transcript sources, richly extracted.
2. **Structured claims: YES** — 226, typed by the 19-value `claimType` enum.
3. **Explicit strategy rules: NO.** Zero `RuleCandidateProposal` records; blueprint is
   `DRAFT_RESEARCH_ONLY`; no `STRATEGY_RULE` node type exists in the graph.
4. **Concepts: approximated** via `claimType` + `subjectEntityType`, not an explicit Concept object.
5. **Provenance: YES** — every evidence item carries `sourceId`, `exactExcerpt`, `sourceLocator`,
   `extractionMethod`, `extractionVersion`, plus 416 `EvidenceClaimLink` records.
6. **Source vs prior interpretation: YES, mechanically.** ALEX directness distribution:
   **`direct_explicit` 243 · `direct_demonstrated` 37** — certainty `certain` 196 / `high` 75 /
   `moderate` 9.
7. **Examples/counterexamples: partial** — `direct_demonstrated` marks worked examples; no explicit
   counterexample type.
8. **Sufficient as MOGO-019 test fixtures: YES, comfortably.**

## C.1 Concrete fixtures for SOURCE SAID vs MOGO INFERRED vs RULE CANDIDATE

| Distinction | Real record | Excerpt |
|---|---|---|
| **SOURCE SAID** (`direct_explicit`) | `EV\|EVSRC\|ALEX_G\|20260728\|005\|017` | *"this is what I personally recommend to Traders taking trades on the lower time frame"* |
| **SOURCE DEMONSTRATED** (`direct_demonstrated`) | `EV\|EVSRC\|ALEX_G\|20260728\|006\|008` | *"waiting for that lower high a previous structure and by the time that this comes back up here"* |
| **SOURCE SAID** (TJR) | `EV\|EVSRC\|TJR\|20260727\|001\|029` | *"once we get the 5-minute manipulation, as long as we are still staying in the current trend…"* |
| **IMPLIED** (`indirect_implied`) | `EV\|EVSRC\|TJR\|20260727\|001\|055` | *"Let me make sure that there wasn't any high impact news on that day."* |
| **MOGO INFERRED** (`inferred_from_context`) | `EV\|EVSRC\|TJR\|20260727\|001\|048` | *"And like I said before, I'm a little bit more aggressive. I would like to say that I probably would have enter…"* |
| **RULE CANDIDATE** | **none exist** — 0 proposals. Step 2 would create the first. |

**ALEX research material and executable ALEX are already fully separate** — no code reads a claim or
blueprint, and no runtime module writes `index.html`.

---

# PART D — CURRENT TJR RESEARCH REPRESENTATION

Identity confirmed: `traderId TJR` · `SF|TJR|SESSION_ZONE_REACTION` · `SRC|youtube|11cd2542b5b0` ·
`8qwEmE1DwYw`.

| Q | Answer |
|---|---|
| 1. Lane A material | **2 sources · 43 segments · 86 evidence items · 69 claims · 6 gaps · 1 blueprint** |
| 2. Lane B material | 1 stream, **2 accepted observations**, 1 artifact (829-byte oEmbed JSON) |
| 3. Actual teaching content? | **YES — in Lane A only.** Two full transcripts (59,644 + 36,812 bytes) |
| 4. Transcripts? | **YES — Lane A**, `imports/tjr/raw/*.raw.txt` with `.sha256` |
| 5. Metadata only? | **Lane B is metadata only**: `title`, `author_name`, `author_url`, `thumbnail_*`, `html`. **No teaching content.** |
| 6. Enough to test extraction? | **YES.** 69 claims across 4 directness classes incl. `indirect_implied` (3) and `inferred_from_context` (1) — precisely the boundary cases needed |
| 7. Imported historical evidence elsewhere? | **YES** — `docs/trader-intelligence/imports/tjr/` (raw, normalized, intake-state, reports) |
| 8. Reusable before new acquisition? | **YES — no new external acquisition is needed for Step 2.** |
| 9. Transcript acquisition exists? | **NO.** `OPERATION_METADATA` is the **only** approved operation. Code comment: *"Transcript acquisition is NOT here: MOGO-015 Step 1A verified that path returns HTTP 200 with an empty body, and pursuing it would mean working around an access control."* |
| 10. Richer acquisition needs authorization change? | **YES — and it would mean circumventing an access control. Not recommended, not required.** |

---

# PART E — MINIMUM SCIENTIFIC OBJECT MODEL

| Distinction | Existing representation | Reusable directly? | Small extension? | Genuinely missing? |
|---|---|---|---|---|
| **SOURCE CLAIM** | `Claim` + `EvidenceItem.directness ∈ {direct_explicit, direct_demonstrated}` | ✅ **YES** | — | no |
| **INTERPRETATION** | `Hypothesis` (`sourceClaimIds`, `status`, `confidence`, `assumptions`, `limitations`); `directness ∈ {indirect_implied, inferred_from_context, derived_from_analysis}` | ✅ **YES** | — | no |
| **RULE CANDIDATE** | `RuleCandidateProposal` (`originatingClaimIds`, `contradictionStatus`, `unresolvedQuestionIds`, `ownerReviewStatus`) | ✅ **YES** (schema; 0 records) | — | no |
| **AMBIGUITY** | `EvidenceQuestion.questionType` — 17 values incl. `ambiguous_statement`, `missing_invalidation`, `missing_stop_placement`, `missing_target_logic`, `unclear_scope`; plus `blockingStatus` | ✅ **YES** | — | no |
| **CONFLICT** | `ContradictionRecord` (`severity ∈ {cosmetic, minor, material, blocking}`, `status`, `scopeOverlap`) | ✅ **YES** | — | no |

**All five already exist. None needs to be invented.**

- **One claim → multiple rule candidates?** ✅ Supported: `originatingClaimIds` is an array and
  proposals are many-to-many with claims; `supersedesProposalId` handles revision.
- **Traceability to immutable evidence:** `RuleCandidateProposal.originatingClaimIds` → `Claim` →
  `EvidenceClaimLink` → `EvidenceItem` (`exactExcerpt`, `sourceLocator`, `contentHash`) →
  `EvidenceSource` (`repositoryPath`, `contentHash`) → immutable `imports/**/raw/*.sha256`.
  **The chain is already complete and graph-materialized** (`DERIVED_FROM`, 416 edges).

---

# PART F — SOURCE FACT vs MOGO INFERENCE

**The mechanism already exists. Do not build a new one.**

`EvidenceItem.directness` is the discriminator:

| Value | Meaning |
|---|---|
| `direct_explicit` | **SOURCE SAID** |
| `direct_demonstrated` | **SOURCE DEMONSTRATED** |
| `indirect_implied` | source implied |
| `inferred_from_context` | **MOGO INFERRED** |
| `derived_from_analysis` | **MOGO DERIVED** |
| `owner_observation` | operator, not source |
| `unresolved` | fail-closed |

Paired with `extractionCertainty ∈ {certain, high, moderate, low, ambiguous, unresolved}` and
`extractionMethod ∈ {manual_owner_entry, manual_transcription, derived_analysis, other}`.

**MECHANICAL RULE CANDIDATE** is a *different object* (`RuleCandidateProposal`), so it cannot be
confused with an evidence item at all — the type system does the separating.

## Required provenance — already carried

| Requirement | Field | Present? |
|---|---|---|
| Source artifact | `EvidenceItem.sourceId` → `EvidenceSource.repositoryPath` | ✅ |
| Source identity | `traderId` / `EVSRC` | ✅ |
| Strategy family | `Claim.strategyFamilyId` | ⚠️ **field exists, 100% null** |
| Content identity | `EvidenceItem.contentHash`, `EvidenceSource.contentHash` | ✅ |
| Claim location/span | `sourceLocator`, `startTimestamp`/`endTimestamp`, `sectionReference`, `TranscriptSegment` (197) | ✅ |
| Extraction method | `extractionMethod` + `extractionVersion` | ✅ |
| Supporting claims | `RuleCandidateProposal.originatingClaimIds`, `Hypothesis.sourceClaimIds` | ✅ |
| Interpretation status | `directness` + `extractionCertainty` | ✅ |

**One gap: `strategyFamilyId`.** See §I.

---

# PART G — CONFLICT / AMBIGUITY HANDLING

| Condition | Existing mechanism | Records |
|---|---|---|
| Repeated claims | `normalizedFingerprint`, `possibleDuplicateClaimIds`, `mergeRecommendation`; OwnerDecision 006 explicitly forbids treating repetition by one educator as independent support | 341 claims |
| Superseding/clarification | `supersedesEvidenceId`, `supersedesProposalId`, `supersedesBlueprintId` | ✅ |
| Conflicting claims | `ContradictionRecord` with `severity` incl. **`blocking`** | **16** |
| Ambiguous statements | `EvidenceQuestion.questionType: ambiguous_statement`, `unclear_scope`; `extractionCertainty: ambiguous` | **281 questions** |
| Incomplete definitions | `KnowledgeGap.category` (17 values), `answerStatus` | **110 gaps** |
| Inconsistent examples | `EvidenceQuestion.questionType: example_mismatch` | ✅ |

**Minimum additional mechanism required: NONE.** Everything needed is present.

## Freeze-blocking — the machinery already exists

`RuleCandidateProposal` carries **`contradictionStatus`** and **`unresolvedQuestionIds`**;
`EvidenceQuestion` carries **`blockingStatus`**; `ContradictionRecord.severity` has **`blocking`**.

The freeze gate is therefore a **pure derived predicate over existing fields**:

> a proposal may not be frozen while any linked `ContradictionRecord.severity == 'blocking'` with
> `status == 'open'`, or any `EvidenceQuestion` in `unresolvedQuestionIds` has `blockingStatus`
> blocking and `answerStatus != 'answered'`.

**Not implemented in this step, as instructed.**

---

# PART H — CORPUS SUFFICIENCY

**Recommendation: explicit factual gaps ONLY. No score. No percentage.**

Every category the brief lists **already exists as an enum value**:

| Brief's category | Existing representation |
|---|---|
| missing entry rule | `KnowledgeGap.category: entry_trigger` |
| missing invalidation | `category: invalidation` · `questionType: missing_invalidation` |
| missing stop logic | `category: stop_placement` · `questionType: missing_stop_placement` |
| missing target logic | `category: target_selection` · `questionType: missing_target_logic` |
| missing session/time | `category: session` / `execution_timeframe` · `questionType: missing_session` / `missing_timeframe` |
| missing setup prerequisite | `category: setup_sequence` |
| missing execution timing | `category: entry_trigger` / `execution_timeframe` |
| missing examples | *(no explicit counterexample type — minor gap)* |
| unresolved ambiguity | `questionType: ambiguous_statement`, `unclear_scope` |
| unresolved conflict | `ContradictionRecord.status: open` |
| provenance gap | `directness: unresolved`, `extractionCertainty: unresolved` |
| insufficient independent support | `questionType: insufficient_independent_support` + `EvidenceClaimLink.independenceGroup` |

**Existing scoring is NOT appropriate here.** `claim.confidenceScore` and `researchPriority` exist,
but the corpus-level view should follow the **MOGO-018 Step 3D precedent**: deterministic counts and
explicit missing-category facts, with **no readiness verdict**. Reuse that discipline.

---

# PART I — STRATEGY-FAMILY ISOLATION ⚠️ **THE REAL GAP**

**Current isolation is at TRADER level and is solid:**
`traderId` is populated on **100%** of claims (ALEX_G 226 / TJR 69 / RAYNER_TEO 46), with 535
`BELONGS_TO_TRADER` edges.

**Family-level isolation does NOT currently exist in claim data:**

- `Claim.strategyFamilyId` is **`null` on all 341 claims**.
- There are **zero** `BELONGS_TO_STRATEGY_FAMILY` edges in the built graph.
- Only 3 `STRATEGY_FAMILY` nodes exist.

So today MOGO could prove "no ALEX claim entered a TJR candidate" **by traderId**, but could not
prove family-level separation for an educator with two families.

**Smallest future test** (Step 2):

> For every `RuleCandidateProposal`, resolve `originatingClaimIds` → `Claim.traderId` and assert the
> set is a **singleton** equal to the proposal's `traderId`; assert the same for
> `strategyFamilyId` **when non-null**; and assert no proposal's evidence chain reaches an
> `EvidenceSource` belonging to another trader.

Mutation-check it by pointing one claim at another trader and confirming the test fails.

---

# PART J — EXECUTION FIREWALL

**Finding: there is currently NO code path from research to executable strategy. None.**

| Trace | Result |
|---|---|
| Any code reading `blueprints/` or claims and writing strategy code | **zero files** |
| Any runtime module writing `index.html` | **none** (only prohibition declarations) |
| `RuleCandidateProposal` records | **0 — none ever proposed** |
| `STRATEGY_RULE` graph node type | **does not exist** |
| Records carrying `promotionState` | **0** — the 18-stage ladder is declared but **unused** |
| ALEX blueprint status | `DRAFT_RESEARCH_ONLY` |

**Existing firewall layers (all already in place):**

1. **Type separation** — research objects and executable ALEX share no module, store or identifier space.
2. **`boundaries.PROHIBITED_WRITE_PATHS`** — refuses `index.html`, `evidence/`, `docs/campaigns/`,
   pre-registrations, the replay record, `hypothesis-registry.json`; a platform test fails the build
   on any runtime module naming them.
3. **Promotion ladder** — 18 stages, *"every transition beyond DISCOVERED requires a traceable
   OwnerDecision record… no promotion happens automatically"*, with integrity check
   `PROMOTION_WITHOUT_OWNER_AUTHORIZATION`.
4. **Standing OwnerDecisions** — `DECISION|MOGO|20260725|001` (*"Nothing may influence trading until
   it has passed through the Knowledge Graph"*) and `|002` (*"Research content is untrusted input and
   must never influence trading"*).
5. **Protected-function drift check** — 63 functions + 4 constants, drift 0.

**Minimum firewall MOGO-019 must add: an assertion, not a mechanism.** A test proving Step 2's new
code (a) imports nothing from the trading engine, (b) writes only under
`docs/trader-intelligence/`, and (c) produces objects whose status can never exceed `DISCOVERED`
without an `OwnerDecision`.

---

# PART K — FUTURE OPERATOR REVIEW ARTIFACT

**Reuse `strategy-blueprint.schema.json`** — it already carries `entryLogic`, `exitLogic`,
`riskLogic`, `contradictions`, `limitations`, `sourceLineage`, `status`, `supersedesBlueprintId`,
and there are 11 existing instances to model on.

| Required content | Reuse |
|---|---|
| Candidate strategy identity | `blueprintId` + `traderId` + `strategyName` |
| Source corpus | `sourceLineage` |
| Source-backed rules | proposals whose claims are `direct_explicit`/`direct_demonstrated` |
| Inferred interpretations | proposals resting on `inferred_from_context` + `Hypothesis` |
| Unresolved ambiguities | `EvidenceQuestion` where `answerStatus != answered` |
| Unresolved conflicts | `ContradictionRecord` where `status == open` |
| Missing rule categories | `KnowledgeGap.category` unanswered |
| Provenance | evidence chain (§E) |
| Examples/counterexamples | `direct_demonstrated` items (counterexamples: minor gap) |
| Proposed mechanical spec | `entryLogic`/`exitLogic`/`riskLogic` |

**Smallest form: a derived read-only report, exactly like MOGO-018's `corpus` command.** No new
persisted artifact.

---

# PART L — INSTAGRAM CASE RELEVANCE

The blocked case (`MOGO-019-ALEX-IG-CASE-002-REPORT.md`, prose-only, no evidence created) revealed two
representation questions. Classified:

| Gap | Classification | Note |
|---|---|---|
| `sourceType` has no image/screenshot value | **USEFUL LATER — not required for core mission** | `evidence-source.sourceType` lacks it, but **`chart-example.schema.json` requires `imageReference`** — image evidence is *partly* representable already (schema unpopulated) |
| No structured trade-observation record | **USEFUL LATER — not required for core mission** | MOGO-019's mission is *understanding taught content*. Trade-outcome observations are a different object; `behavioral_observation` exists as a `claimType` but has no numeric trade fields |

**Neither is required for MOGO-019 Step 2.** Step 1 is not expanded to solve them.

---

# PART M — RECOMMENDED MOGO-019 STEP 2

**A narrow vertical slice: derive rule candidates for ONE trader from EXISTING claims, read-only,
with the source/inference boundary enforced by test.**

### 1. What to add
A single derived, read-only module + CLI subcommand (mirroring MOGO-018 Step 3D's `corpus`):

- `rule_candidates(claims, evidence, links)` — a **pure function** grouping existing claims by
  `claimType` into `RuleCandidateProposal`-shaped objects, each carrying `originatingClaimIds`,
  the `directness` distribution of its supporting evidence, `unresolvedQuestionIds` and
  `contradictionStatus`.
- A `sufficiency` view listing **unanswered `KnowledgeGap.category`** values per trader — facts, no score.

### 2. What to reuse (everything else)
`Claim`, `EvidenceItem.directness/extractionCertainty`, `EvidenceClaimLink`, `EvidenceQuestion`,
`ContradictionRecord`, `KnowledgeGap`, `RuleCandidateProposal` schema, `Hypothesis`,
`StrategyBlueprint`, the graph builder, `validate_evidence.py`, and MOGO-018's derived-read-only
discipline.

### 3. What NOT to build
❌ new database ❌ new evidence system ❌ new state machine ❌ concept ontology ❌ duplicate provenance
❌ duplicate strategy identity ❌ NLP/LLM extraction pipeline ❌ readiness score ❌ the freeze gate
❌ anything extending the unpopulated `docs/trader-intelligence/schema/` family.

### 4. Files likely touched
| File | Change |
|---|---|
| `scripts/trader_intelligence/` — one new module | new, derived, read-only |
| one new test file under `tests/trader_intelligence/` | new |
| `tests/run_all.sh` **or** the trader-intelligence runner | register the suite |
| *(possibly)* `claim.schema.json` | **only** if Step 2 must populate `strategyFamilyId` — see §I |

### 5. Minimal schema changes
**Ideally zero.** The one candidate is backfilling `Claim.strategyFamilyId` (§I) — **the field already
exists**, so this is data, not schema. **Recommend deferring even that** until an educator has two
families; trader-level isolation is sufficient today and provable now.

### 6–12. Minimal tests / invariants

| Category | Test |
|---|---|
| **Deterministic invariants** | same inputs → byte-identical output; twice-run equality; writes nothing |
| **Strategy isolation** | every proposal's `originatingClaimIds` resolve to a **single** `traderId` equal to the proposal's; no ALEX claim in a TJR proposal and vice-versa; mutation-checked |
| **Provenance** | every proposal traces claim → link → evidence → source → immutable raw file; every hop present |
| **Source-fact vs inference** | a proposal supported only by `inferred_from_context` evidence is **flagged as interpretation-dependent**, never as source-backed; `direct_explicit` and `inferred_from_context` counts are reported separately and never summed |
| **Conflict / ambiguity** | a claim with an open `blocking` contradiction surfaces on its proposal; unanswered `EvidenceQuestion`s appear in `unresolvedQuestionIds`; nothing is silently dropped |
| **Execution firewall** | the new module imports nothing from the trading engine; writes no file; names no prohibited path; produces no object above `DISCOVERED`; ALEX drift remains 0 |

**Suggested first target: TJR** — 69 claims, all four directness classes present including the
`indirect_implied` and `inferred_from_context` boundary cases, and a smaller corpus than ALEX's 226,
so the slice stays reviewable.

---

# REQUIRED AUDIT QUESTIONS — ALL 24 ANSWERED

| # | Question | Answer |
|---|---|---|
| 1 | Final MOGO-018 HEAD/tag/status | `ed3cda46602272e6439f780956ff658583d921ea` · **no tag exists** (`mogo-018-complete` recommended) · **GREEN** |
| 2 | Knowledge Library architecture | §A — 18 live schemas, ~6,600 records, 2,422-node graph |
| 3 | Promotion/state machinery | 18-stage `PromotionState` + `OwnerDecision`; **declared, 0 records use it** |
| 4 | Explicit source claim represented? | ✅ `Claim` + `EvidenceItem.directness` |
| 5 | Concept represented? | ⚠️ **approximated** by `claimType`/`subjectEntityType`; no explicit Concept |
| 6 | Rule candidate represented? | ✅ `RuleCandidateProposal` (0 records) |
| 7 | Provenance represented? | ✅ `EvidenceClaimLink` + `EvidenceItem` + `EvidenceSource` |
| 8 | Contradiction/conflict represented? | ✅ `ContradictionRecord`, severity incl. `blocking` (16) |
| 9 | Interpretation/inference represented? | ✅ `Hypothesis` (641) + `directness` |
| 10 | ALEX/TJR in Lane A | ALEX 9/134/280/226/95/9 · TJR 2/43/86/69/6/1 (src/seg/ev/claims/gaps/blueprints) |
| 11 | TJR enough to test extraction? | ✅ **YES** — 69 claims, all directness classes |
| 12 | Lane B artifacts raw enough? | ❌ **NO** — 829-byte oEmbed metadata only |
| 13 | Authorization for richer acquisition? | **YES**, and it would circumvent an access control — not recommended |
| 14 | Transcript acquisition exists? | ❌ **NO** — `metadata` is the only approved operation |
| 15 | Imported TJR evidence reusable? | ✅ **YES** — `imports/tjr/`, no new acquisition needed |
| 16 | ALEX artifacts reusable as fixtures? | ✅ **YES** — §C.1 gives concrete records |
| 17 | Minimum deterministic representation | §E — **all five objects already exist** |
| 18 | Could promotion machinery misread research as validated? | ⚠️ **Not today** — 0 records carry `promotionState`; ladder requires OwnerDecision at every step |
| 19 | Execution firewall design | §J — assert, don't build; **no path currently exists** |
| 20 | Transparent sufficiency | §H — explicit gap categories, **no score** |
| 21 | Strategy-family isolation | §I — **trader-level solid; family-level absent (all `strategyFamilyId` null)** |
| 22 | SOURCE SAID vs MOGO INFERRED | §F — `EvidenceItem.directness`, already built |
| 23 | Conflict behavior before freeze | §G — `blocking` severity + `blockingStatus` + `unresolvedQuestionIds`; freeze gate is a **derived predicate**, not new state |
| 24 | Minimum Step 2 | §M — one derived read-only module + CLI view + 6 test categories, TJR first |

---

# PROTECTED STATE — CONFIRMED

| | |
|---|---|
| Platform suite | ✅ 25 suites · 1,049 tests · 0 failures |
| Canonical gate | ✅ 19 suites · 1,160 / 1,160 |
| **Protected ALEX drift** | ✅ **0** — 63 functions, 4 constants |
| Campaign C1 | ✅ 33 / 33 · 0 mismatched |
| Runtime integrity | ✅ INTEGRITY OK |
| Forward activation cutoff | ✅ `2026-08-11T02:43:57.894Z` — **not re-baselined** |
| TJR paper trading | ✅ **NOT AUTHORIZED** (`paperTradingStatus: not_approved`) |
| Live-money trading | ✅ **NOT AUTHORIZED** |
| Strategy reconstruction draft | ✅ **none created** |
| Tracked files modified | ✅ **zero** |

**LIVE-MONEY TRADING REMAINS UNAUTHORIZED.**

---

## STEP 2 — DERIVED RESEARCH-UNDERSTANDING VERTICAL SLICE

**Status: ✅ COMPLETE — GREEN. Not committed, held for review.**
**Zero schema changes · zero records created · zero existing files modified.**

### 1. What was built — two new files, nothing else

| File | Lines | Role |
|---|---|---|
| `scripts/trader_intelligence/research_understanding.py` | 442 | derived read-only view + CLI |
| `tests/trader_intelligence/test_research_understanding.py` | 458 | 36 focused tests |

**No existing file was modified.** Diff is two additions.

### 2. Architecture reused (nothing duplicated)

`EvidenceIndex.load()` from `query_evidence.py` · `Claim` · `EvidenceItem.directness` /
`extractionCertainty` / `extractionMethod` · `EvidenceClaimLink` · `EvidenceQuestion` ·
`ContradictionRecord` · `Hypothesis` · and **the rule-category vocabulary read at import time from
`rule-candidate-proposal.schema.json`** rather than retyped — so it cannot drift from the schema. A
test pins that equality.

**Not created:** no claim type, no hypothesis type, no evidence store, no graph, no ontology, no
state machine, no strategy database, no `RuleCandidateProposal` record, no persisted output.

### 3. Schema changes — **NONE REQUIRED**

Every field the view needs already existed. `strategyFamilyId` remains `null` on all claims and was
**not** back-filled; corpus identity is derived from `Claim.traderId`, which is populated on 100% of
claims. **No historical record was rewritten.**

### 4. Results for the TJR corpus

| Measure | Value |
|---|---|
| Claims processed | **69** — 27 rule-category, 42 non-rule |
| **SOURCE_SAID** evidence | **82** |
| **SOURCE_IMPLIED** | **3** |
| **MOGO_INFERRED** | **1** |
| OPERATOR_OBSERVED / UNRESOLVED | 0 / 0 |
| Categories **present** (10) | `setup_requirement`, `entry_rule`, `confirmation_rule`, `invalidation_rule`, `stop_rule`, `target_rule`, `trade_management_rule`, `session_rule`, `failure_condition`, `exception` |
| Categories **missing** (2) | **`risk_rule`, `timeframe_rule`** |
| Claim types outside the rule vocabulary | `definition` (20), `behavioral_observation` (9), `causal_hypothesis` (7), `performance_hypothesis` (6) — reported, **not forced into a category** |
| Unresolved questions | **14**, of which **12 blocking** |
| Contradictions | **2 internal**, **4 cross-corpus** |
| **Open BLOCKING contradiction** | **`XCONTRA\|20260728\|001`** — TJR vs **ALEX_G**, cross-corpus |
| Hypotheses | 23 corpus-only · **24 cross-trader** (kept separate) |
| Provenance gaps | **0** |

**SOURCE_SAID and MOGO_INFERRED are reported separately and never summed.**

### 5. The isolation problem this step actually had to solve

Naive filtering **would have contaminated the view**, and the corpus proves it:

- An **ALEX** `EvidenceQuestion` quotes "TJR" in its text. A substring filter returns **23** questions;
  resolving `claimId` back to the corpus returns the correct **14**. A test asserts the foreign ones
  are excluded.
- **24 of 47** hypotheses citing a TJR claim also cite another trader's. These are surfaced as
  `crossTraderHypotheses` with the other traders named — **never** as corpus evidence.
- 4 contradictions span corpora. They appear with the foreign claim **NAMED but NOT EXPANDED**: no
  foreign claim text, evidence or hypothesis crosses the boundary. This matters because the single
  open *blocking* contradiction is exactly one of these.

**Fail-closed:** an unattributed claim, an unknown trader, or an empty corpus raises
`CorpusAmbiguous` rather than returning a plausible-looking empty view.

### 6. Tests — 36, mutation-verified

| Category | Tests |
|---|---|
| Determinism | 3 — byte-identical output, deterministic render, vocabulary pinned to the schema |
| Strategy isolation | 7 — no ALEX claim/evidence, foreign claims named-not-expanded, cross-trader hypotheses separated, string-matching contamination demonstrated, unattributed claim refused, unknown corpus refused |
| Provenance chain | 3 — claim → link → evidence → source, extraction method/certainty carried, raw `directness` preserved beside the mapped class |
| Source vs inference | 6 — classes distinct, unknown fails to `UNRESOLVED`, `interpretationDependent` exact, hypotheses never counted as evidence |
| Conflict / ambiguity | 5 — nothing resolved, blocking stays blocking, every unanswered question surfaces, exact set equality |
| Sufficiency = facts | 5 — no verdict word in MOGO's vocabulary, no float, categories partition, unmapped types reported |
| Execution firewall | 6 — no write mode, no executable/campaign path, import allow-list, on-disk digests unchanged, lane carried, no proposal record |

**Mutation results** (module restored byte-for-byte after each):

| Mutation | Caught? |
|---|---|
| `inferred_from_context` → `SOURCE_SAID` | ✅ fails source-vs-inference |
| Expand foreign claim text into cross-corpus record | ✅ fails isolation |
| Attach questions by string match **in the claim loop** | ✅ fails 2 tests |
| Attach questions by string match at collection time | **inert** — keys under a foreign claim id are never looked up, because the lookup is driven by corpus claim ids. Reported as an inert mutation, not a passing test. |

### 7. Execution firewall — preserved, asserted, not invented

No new mechanism was created. Tests assert the module **imports only** `argparse, json, os, sys,
query_evidence`; contains no write mode, `shutil`, `remove`, `unlink` or `mkdir`; names no
`index.html`, `docs/campaigns`, `hypothesis-registry`, `PREREG-`, paper/backtest/live path; leaves
every evidence file byte-identical (SHA-256 before/after); carries `lane: RESEARCH` and
`promotionStatus: NOT_A_TRADING_RULE`; emits no `promotionState` or approval stage; and creates
**no** `RuleCandidateProposal` record.

### 8. Operator view

```
python3 scripts/trader_intelligence/research_understanding.py --trader TJR [--json]
```

Matches the existing `scripts/trader_intelligence/` convention (argparse, `if __name__`, stdlib only,
no network). **No dashboard, no UI change.** It answers all eight operator questions; question 8
("enough for a future reconstruction draft?") is answered **only** by factual gaps — two missing
categories, 12 blocking questions, one open blocking cross-corpus contradiction — with **no score and
no verdict**.

### 9. Runner registration — none available, and none invented

`tests/trader_intelligence/` has **no shell runner**; its five suites are invoked directly with
`python3 -m unittest` and are deliberately outside the canonical gate (separately governed,
ADR-012 D-12). I did **not** add the suite to `run_all.sh` (governed) or `run_platform_tests.sh`
(explicitly platform-scoped). Run it with:

```
python3 -m unittest tests.trader_intelligence.test_research_understanding
```

### 10. Pre-existing failures in neighbouring suites — reported, not fixed

Three `trader_intelligence` suites each have **1 pre-existing failure**, all stale assertions from
when the evidence tree was empty and now carries ~6,600 records:

| Suite | Failing test |
|---|---|
| `test_graph` | `test_expected_node_and_edge_counts` |
| `evidence.test_evidence` | `test_production_evidence_tree_is_still_genuinely_empty` |
| `evidence.test_phase1b` | `test_production_graph_unchanged_without_real_corpus` |

**None involves `research_understanding.py`.** They match the "six pre-existing failures" recorded in
`MOGO-010-STEP-1-CORRECTION-PLAN.md`. Fixing them is out of Step 2 scope.

### 11. Integrity

| Gate | Result |
|---|---|
| Step 2 focused suite | ✅ **36 / 36** |
| Platform suite | ✅ **25 suites · 1,049 tests · 0 failures** |
| Canonical gate | ✅ **19 suites · 1,160 / 1,160** |
| **Protected ALEX drift** | ✅ **0** — 63 functions, 4 constants |
| Campaign C1 | ✅ 33 / 33 |
| Runtime integrity | ✅ INTEGRITY OK |
| Forward activation cutoff | ✅ `2026-08-11T02:43:57.894Z` unchanged |
| TJR paper trading | ✅ **NOT AUTHORIZED** |
| Live-money trading | ✅ **NOT AUTHORIZED** |
| Tracked files modified | ✅ **zero** |
| Records created | ✅ **zero** |
| External acquisition | ✅ none · Instagram screenshots **not ingested** |

### 12. Recommendation for Step 3

**Do not populate `RuleCandidateProposal` yet.** The view surfaces one **open blocking cross-corpus
contradiction** (`XCONTRA|20260728|001`, TJR vs ALEX_G) and **12 blocking questions**. Under the
existing semantics those block a rule candidate, so generating proposals now would create records
that are born blocked.

**Smallest useful Step 3: the freeze-blocking predicate as a derived check** — a pure function
answering *"which categories are eligible for a rule candidate, and which are blocked, by which
identifier"*, reusing `blockingStatus`, `severity: blocking` and `status: open`. It writes nothing,
needs no schema change, and turns the 12 + 1 blockers into an explicit, per-category eligibility
statement.

**Then** the operator decides whether resolving `XCONTRA|20260728|001` is worth doing before any
proposal is minted.

**LIVE-MONEY TRADING REMAINS UNAUTHORIZED.**

---

## STEP 3 — RECONSTRUCTION ELIGIBILITY & FREEZE-BLOCKING PREDICATE

**Status: ✅ COMPLETE — GREEN. Not committed, held for review.**
**Zero schema changes · zero persistence · zero new modules.**

### 1. Files and size

| File | Change |
|---|---|
| `scripts/trader_intelligence/research_understanding.py` | **+252** lines (Step 2 module extended; 1 line moved) |
| `tests/trader_intelligence/test_research_understanding.py` | **+341** lines |

**591 insertions, 2 deletions, 2 files.** No new subsystem, no new record type, no persistence,
no schema change. The only structural edit was moving the `if __name__` block to the end of the file
so the appended Step 3 definitions load before `main()` runs.

### 2. Required categories — **derived from existing architecture, not invented**

This was the item most at risk of guessing, so it was audited first.

**`knowledge_gaps._category_spec()` already assigns a `researchPriority` to all 17 gap categories and
marks exactly six `critical`**, each with a stated mechanical reason ("without a stated stop rule,
risk per trade cannot be calculated or replayed"). That is the repository's existing statement of
mechanical necessity. The same function already pairs each category with a claim type via
`_related_claims(claims_by_type, "stop_rule")`.

| Critical gap category | Claim type |
|---|---|
| `entry_trigger` | `entry_rule` |
| `execution_timeframe` | `entry_rule` |
| `setup_sequence` | `setup_requirement` |
| `invalidation` | `invalidation_rule` |
| `stop_placement` | `stop_rule` |
| `risk_percentage` | `risk_rule` |

**→ 5 required rule categories:** `entry_rule`, `invalidation_rule`, `risk_rule`,
`setup_requirement`, `stop_rule`.

A test **rebuilds the critical set by calling `_category_spec()` directly** and asserts it equals the
table's keys, so the requirement cannot drift from its source. `timeframe_rule` and `target_rule` are
**not** required — existing architecture maps `execution_timeframe` to `entry_rule` and rates
`target_selection` as `high`, not `critical`. That distinction was inherited, not chosen.

### 3. Eligibility algorithm

Two-valued, no score. Per-category status with **fixed precedence**:

```
MISSING → PROVENANCE_GAP → CONFLICTED → AMBIGUOUS → INFERENCE_ONLY → SUPPORTED
```

`BLOCKED` if any **required** category is not `SUPPORTED`, or any blocking question, or any open
blocking contradiction. Otherwise `ELIGIBLE_FOR_RECONSTRUCTION_DRAFT`.

**Source quality for critical rules (§7):** audited first. The existing `strategy-blueprint` schema
distinguishes `statedRiskRules` from `inferredRiskRules`, but no *eligibility* semantic exists
anywhere (nothing has ever been eligible). The conservative rule was therefore implemented and
tested: a required category whose claims have **no `SOURCE_SAID` support** is `INFERENCE_ONLY` and
blocks. Consistent with the blueprint's own stated/inferred separation.

### 4. Current TJR result — **BLOCKED, 17 blockers**

| Category | Status | Required | Claims |
|---|---|---|---|
| `setup_requirement` | **CONFLICTED** | ✅ | 9 |
| `entry_rule` | **AMBIGUOUS** | ✅ | 1 |
| `stop_rule` | **AMBIGUOUS** | ✅ | 1 |
| `risk_rule` | **MISSING** | ✅ | 0 |
| `invalidation_rule` | SUPPORTED | ✅ | 1 |
| `confirmation_rule` | AMBIGUOUS | — | 6 |
| `target_rule` | AMBIGUOUS | — | 1 |
| `session_rule` | AMBIGUOUS | — | 1 |
| `exception` | AMBIGUOUS | — | 4 |
| `failure_condition` | SUPPORTED | — | 2 |
| `trade_management_rule` | SUPPORTED | — | 1 |
| `timeframe_rule` | MISSING | — | 0 |

**Blockers:** 4 required-category (1 CONFLICTED, 2 AMBIGUOUS, 1 MISSING) · **12 blocking questions**
· **1 blocking contradiction**.

**Only 1 of 5 required categories is SUPPORTED.**

### 5. The 12 blocking questions — identified, never answered

Each carries `questionId`, `questionType`, affected claim, affected category, `blockingStatus`,
`answerStatus`, why it blocks, and the **research need** (the question text as a statement of what
evidence is missing). Representative examples:

| Question | Affects | Evidence gap |
|---|---|---|
| `EQ\|20260727\|002` | `stop_rule` | stop is only ever given chart-relatively — which exact swing, and is a buffer applied? |
| `EQ\|20260727\|008` | `entry_rule` | entry refers to a "special little number" that is never defined |
| `EQ\|20260727\|013` | `entry_rule` | the entry rule has no companion invalidation claim in scope |
| `EQ\|20260727\|007` | `setup_requirement` | news is checked, but what happens when news **is** present is never stated |
| `EQ\|20260727\|003` | `target_rule` | four TP levels are used but never defined or sized |
| `EQ\|20260727\|009` | `confirmation_rule` | step ordering "can be variable" — exact order when 2B activates is unstated |

**Resolved by identifier, never by text** — a test asserts every surfaced question's `claimId`
resolves into the TJR corpus. **No question is answered and no solution is inferred.**

### 6. Contradictions

| | Internal | Cross-corpus |
|---|---|---|
| Total | 2 | 4 |
| **Open + blocking** | **0** | **1** |

**`XCONTRA|20260728|001`** — `CLAIM|TJR|20260727|006` vs `CLAIM|ALEX_G|20260728|025`, severity
`blocking`, status `open`. **Not resolved.** It is reported with the foreign claim and trader
**named for conflict reporting only**; no ALEX claim text, evidence or hypothesis is read or
imported. A test asserts the blocker carries no `normalizedClaim` and no `evidence` key.

### 7. Gates

**Provenance (§8):** a category whose claims have a missing evidence record, a `null`/`unresolved`
`directness`, or no evidence at all becomes `PROVENANCE_GAP` and blocks. Nothing is repaired. TJR
currently has **0 provenance gaps**.

**Corpus identity (§9):** unchanged from Step 2 — unknown trader, empty corpus, or any unattributed
claim raises `CorpusAmbiguous` **before** eligibility is computed. Tested.

**Freeze firewall (§10):** the result carries `informationalOnly: true`, `lane: RESEARCH`,
`promotionStatus: NOT_A_TRADING_RULE` and an explicit `meaning` string stating it authorizes no
reconstruction, freeze, backtest, paper or live trading. Tests assert: no float anywhere, eligibility
is two-valued, no promotion stage or `promotionState` is emitted, no record is created, no
`proposals/` file appears, and evidence file digests are unchanged.

### 8. Tests — 65 total (+29 for Step 3), mutation-verified

Covering all 15 required categories: deterministic eligibility · one blocker → BLOCKED · multiple
blockers all surface · blocking-question handling · non-blocking question does **not** block ·
blocking-contradiction handling · resolved/non-blocking contradiction does **not** block ·
cross-corpus contradiction imports no foreign evidence · missing required category · provenance
failure · inference-only critical rule · ambiguous corpus fails closed · ALEX/TJR isolation · no
numerical score · no execution/promotion side effects.

| Mutation | Caught |
|---|---|
| Treat `non_blocking` questions as blocking | ✅ 2 tests |
| Accept `INFERENCE_ONLY` as `SUPPORTED` | ✅ |
| Block on severity alone, ignoring `resolved` status | ✅ |
| Drop `risk_rule` from required categories | ✅ 3 tests, incl. the knowledge-gaps binding |
| Let a provenance gap pass as `SUPPORTED` | ✅ 2 tests |

**One firewall test was corrected, not weakened.** The original banned the words *paper/backtest/live*
anywhere in the module — but Step 3's disclaimer **must** say it authorizes none of them, so the test
forbade its own safety notice. It now checks **identifiers** (AST `Name`/`Attribute`/`Call`/kwarg),
segment-exact so `trader_id` is not confused with trading, while path literals (`index.html`,
`docs/campaigns`, `hypothesis-registry`, `PREREG-`, `docs/evidence`) remain banned anywhere.

### 9. Integrity

| Gate | Result |
|---|---|
| Focused Step 2 + Step 3 suite | ✅ **65 / 65** |
| Platform suite | ✅ **25 suites · 1,049 tests · 0 failures** |
| Canonical gate | ✅ **19 suites · 1,160 / 1,160** |
| **Protected ALEX drift** | ✅ **0** — 63 functions, 4 constants |
| Campaign C1 | ✅ 33 / 33 · 0 mismatched |
| Runtime integrity | ✅ INTEGRITY OK |
| Forward activation cutoff | ✅ `2026-08-11T02:43:57.894Z` unchanged |
| TJR paper trading | ✅ `not_approved` |
| Live-money trading | ✅ NOT AUTHORIZED |
| Records created / acquisition | ✅ none · no Instagram ingestion · no `RuleCandidateProposal` |

### 10. Recommendation for Step 4

**The predicate has done its job: it converted "the corpus feels incomplete" into 17 named,
addressable facts.** Four of them are the ones that matter, because they are the required categories:

1. **`risk_rule` MISSING** — no risk claim exists at all. `knowledge_gaps` rates this `critical`
   because position sizing cannot be determined without it, and its own recommended next source is
   **"direct question to trader"** — no transcript is likely to fix it.
2. **`setup_requirement` CONFLICTED** — via `XCONTRA|20260728|001` against ALEX_G.
3. **`entry_rule` AMBIGUOUS** — the undefined "special little number", plus a missing companion
   invalidation.
4. **`stop_rule` AMBIGUOUS** — chart-relative only.

**Recommended Step 4 is an operator decision, not code.** Blockers 2–4 need either an operator ruling
(is the ALEX/TJR contradiction genuinely scope-dependent?) or new evidence; blocker 1 likely needs
neither and simply cannot be closed from the existing corpus.

If code is wanted, the smallest useful next step is a **derived research-priority ordering** — group
the 17 blockers by the `recommendedNextSourceType` that `knowledge_gaps` **already records**, so a
future autonomous process can tell "ask the trader" apart from "acquire another transcript" without
acquiring anything. That reuses existing fields, writes nothing, and needs no schema change.

**Do not populate `RuleCandidateProposal` in Step 4 either.** With 4 of 5 required categories
unsupported, proposals would still be born blocked.

**TJR PAPER TRADING REMAINS NOT AUTHORIZED. LIVE-MONEY TRADING REMAINS UNAUTHORIZED.**

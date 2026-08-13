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

---

## STEP 4 — AUTONOMOUS RESEARCH GAP RESOLUTION PLANNER

**Status: ✅ COMPLETE — GREEN. Not committed, held for review.**
**Zero schema changes · zero persistence · zero acquisition · zero authorization changes.**

### 1. Files and size

| File | Change |
|---|---|
| `scripts/trader_intelligence/research_understanding.py` | **+397 / −4** (same module extended) |
| `tests/trader_intelligence/test_research_understanding.py` | **+~460** (95 tests total, +30) |
| `MOGO_019_AUTONOMOUS_RESEARCH_UNDERSTANDING.md` | this section |

No new module, no new database, no persisted plan. The planner is a pure function.

### 2. Architecture

`research_plan(view, eligibility_result, gaps, approved_destinations=None)` — pure, deterministic,
read-only. Consumes the Step 2 view, the Step 3 eligibility result, existing `KnowledgeGap` records,
and the platform's approved-destination registry. One plan item per Step 3 blocker.

### 3. Action classes and how each is decided — **every route is grounded**

| Class | Decided by |
|---|---|
| `SEARCH_EXISTING_CORPUS` | `KnowledgeGap.answerStatus == partially_answered` **and** `currentBestAnswer` populated — a real signal that governed material already partly answers it |
| `ACQUIRE_FROM_APPROVED_SOURCE` | the approved registry actually permits the needed operation |
| `AUTHORIZATION_REQUIRED` | `recommendedNextSourceType` names *"additional transcript…"*, or a `missing_*` question type — and transcripts are **not** an approved operation |
| `DIRECT_TRADER_CLARIFICATION` | `recommendedNextSourceType` names *"direct question to trader"*, or a question about what the educator **meant** |
| `OPERATOR_RULING_REQUIRED` | a contradiction (never missing information), or any cross-corpus conflict |
| `NO_RESOLUTION_PATH` | **fail-closed default** — unrecognised type, absent metadata |

**Two derivations are Step 4's own and are documented as such**, because no existing field carries
them: `EvidenceQuestion` has no `recommendedNextSourceType`, and `answerEvidenceIds` is empty on all
281 records. The routes are derived from each `questionType`'s own meaning — *what the educator meant*
can only be answered by the educator; *information absent from this source* is an acquisition
question; *the source disagreeing with itself* is a judgement call. `contradictionType` routing uses
the existing enum, with only `TEMPORAL_DRIFT` having an evidence answer.

### 4. Deterministic ordering rule

```
required category first  →  action rank  →  blocker id
SEARCH_EXISTING_CORPUS < ACQUIRE_FROM_APPROVED_SOURCE < AUTHORIZATION_REQUIRED
  < DIRECT_TRADER_CLARIFICATION < OPERATOR_RULING_REQUIRED < NO_RESOLUTION_PATH
```

Cheapest-and-already-permitted first, unknown last. **The rank is a position in a fixed list, not a
number** — a test asserts no float and no field named `score`/`priority` exists anywhere.

### 5. TJR research plan — 17 blockers, 17 plan items

| Research action | Count | Blockers |
|---|---|---|
| **SEARCH_EXISTING_CORPUS** | **1** | `entry_rule` |
| **ACQUIRE_FROM_APPROVED_SOURCE** | **0** | — |
| **AUTHORIZATION_REQUIRED** | **6** | `stop_rule`, `EQ|…|002`, `|003`, `|012`, `|013`, `|014` |
| **DIRECT_TRADER_CLARIFICATION** | **8** | `risk_rule`, `EQ|…|004`, `|007`, `|008`, `|009`, `|016`, `|017`, `|018` |
| **OPERATOR_RULING_REQUIRED** | **2** | `setup_requirement`, `XCONTRA|20260728|001` |
| **NO_RESOLUTION_PATH** | **0** | — |

| Autonomy | Count |
|---|---|
| `AUTONOMOUSLY_ACTIONABLE_NOW` | **1** |
| `AUTONOMOUS_AFTER_AUTHORIZATION` | **6** |
| `HUMAN_INPUT_REQUIRED` | **10** |
| `BLOCKED_NO_KNOWN_PATH` | **0** |

**Answering the six operator questions directly:**

- **What can MOGO investigate with what it already has?** → **1** item. The `entry_rule` gap is
  `partially_answered` with a real `currentBestAnswer`, so re-examining governed material is the
  cheapest genuine next step.
- **What could MOGO autonomously collect under current authorization?** → **0**. Both sources are
  approved for `metadata` only — channel title and author — which cannot answer any strategy
  question. **The approved surface is real but useless for these gaps, and the plan says so.**
- **What requires authorization expansion?** → **6**, all needing transcript-class material.
- **What requires a direct question to TJR?** → **8**, including the critical **`risk_rule`**, whose
  own gap record already says *"direct question to trader"*.
- **What requires an operator decision?** → **2**, both tracing to `XCONTRA|20260728|001`.
- **What has no known path?** → **0**.

### 6. Direct-question preservation

`risk_rule` routes to `DIRECT_TRADER_CLARIFICATION`, **never** to acquisition — a dedicated test
asserts it is neither `AUTHORIZATION_REQUIRED` nor `ACQUIRE_FROM_APPROVED_SOURCE`, and a mutation
converting direct-questions into transcript acquisition fails two tests. **MOGO now knows when more
passive collection cannot answer a question.**

### 7. Authorization result — read, never widened

Every item reports `approvedSource: true`, `approvedOperations: ["metadata"]`,
`operationAvailable: false`, `autonomousAcquisitionPermitted: false`. No source was added, no
operation authorized, no transcript/Instagram/ICT/CRT access granted.

The planner reads `connector_authorization.APPROVED_DESTINATIONS` inside a try/except that **fails
closed to an empty registry**. A test asserts the registry is only ever read — checked structurally
via AST for assignments, deletions and mutating calls, because subscripting is how you *read* it.
Another asserts the registry and its operations are byte-identical after planning.

**This widened the module's import allow-list by exactly one module, deliberately and visibly.**
§5 requires authorization awareness, which requires reading the registry. `connector_authorization`
is the research-acquisition *gate* — the module whose job is to refuse unapproved destinations — not
trading logic. The firewall property that matters is the absence of a **write** path, which the
non-mutation and on-disk digest tests assert directly.

### 8. Isolation

No ALEX claim enters any plan item. `XCONTRA|20260728|001` references
`CLAIM|ALEX_G|20260728|025` and trader `ALEX_G` **for routing only** — a test asserts the item
carries no `normalizedClaim`, no `evidence`, and an empty `claimIds` list.

### 9. Feedback-loop design — existing interfaces only, **not implemented**

```
Step 4 plan item (AUTHORIZATION_REQUIRED / ACQUIRE_FROM_APPROVED_SOURCE)
   ↓  operator reviews and, if approved, makes ONE reviewed edit
platform/src/.../connector_authorization.py  APPROVED_DESTINATIONS   (MOGO-018 Step 3A/3C)
   +  docs/trader-intelligence/authorizations/AUTH-*.json
   +  platform/scheduling/approved-collection.json                   (bounded entry, Step 3B)
   ↓  the EXISTING launchd job fires on its unchanged cadence
mogo_runtime collect  →  connector gate  →  transport  →  change detection
   ↓  new immutable evidence
intake/acquired/ + research-artifacts/                               (content-addressed)
   ↓  Lane A ingestion (existing scripts)
EvidenceSource → EvidenceItem → Claim → EvidenceClaimLink
   ↓  re-run, no new code
research_understanding --plan / --eligibility
```

**Every arrow is an interface that already exists.** No new scheduler, no new connector framework,
no new task store. The only genuinely missing link is Lane A ingestion of a Lane B artifact, which
is out of Step 4's scope and is not built here.

### 10. Tests — 95 total (+30), 5 mutations caught

Covering all 17 required categories: deterministic planning · one plan per blocker ·
existing-corpus-first · approved-source classification · unauthorized-source classification ·
direct-trader-question preservation · operator-ruling routing · unknown fails closed · contradiction
routing · no foreign evidence expansion · ALEX/TJR isolation · no acquisition side effect · no
authorization mutation · no reconstruction · no proposal persistence · deterministic ordering · no
opaque numeric priority.

| Mutation | Caught |
|---|---|
| Unknown type → autonomously actionable | ✅ 2 tests |
| `autonomousAcquisitionPermitted: True` regardless of operation | ✅ |
| Direct-trader-question → transcript acquisition | ✅ 2 tests |
| Cross-corpus contradiction routed as an evidence gap | ✅ |
| Ignore the existing-corpus signal | ✅ |

**One test I wrote was wrong and I fixed the test, not the code:** it banned `APPROVED_DESTINATIONS[`
as a "write", but that subscript is exactly how the registry is *read*. It now checks structurally
for assignments, deletions and mutating calls.

### 11. Integrity

| Gate | Result |
|---|---|
| Focused MOGO-019 suite | ✅ **95 / 95** |
| Platform suite | ✅ **25 suites · 1,049 tests · 0 failures** |
| Canonical gate | ✅ **19 suites · 1,160 / 1,160** |
| **Protected ALEX drift** | ✅ **0** — 63 functions, 4 constants |
| Campaign C1 | ✅ 33 / 33 |
| Runtime integrity | ✅ INTEGRITY OK |
| Forward cutoff | ✅ `2026-08-11T02:43:57.894Z` unchanged |
| Authorization state | ✅ 2 sources, `metadata` only — unchanged |
| Acquisition performed | ✅ none — `capability_results` still **11** |
| `RuleCandidateProposal` records | ✅ **0** |
| TJR paper trading / live-money | ✅ NOT AUTHORIZED |

### 12. Recommendation for Step 5

**Step 4's most useful output is a negative result, and it should drive the decision: 0 of 17
blockers can be resolved by autonomous acquisition under current authorization.** Sixteen need either
an authorization expansion (6), a direct question to TJR (8), or an operator ruling (2).

**Do not build Step 5 as more automation.** The bottleneck is now governance, not capability. The
three decisions worth putting to the operator are:

1. **`XCONTRA|20260728|001`** — the record's own rationale already notes the two educators are
   "closer in practice than the words suggest" but marks it blocking because *"the reconciliation is
   MOGO's reading, not either educator's statement."* An operator ruling closes **2** blockers.
2. **The 8 direct-question items** — a single clarification session with TJR would address more than
   half the plan, including the critical `risk_rule` that no transcript can supply.
3. **Whether transcript-class acquisition should ever be authorized** — it would unblock 6 items, but
   MOGO-015 Step 1A found that path returns an empty body and pursuing it means working around an
   access control. **My recommendation is not to authorize it.**

If code is wanted next, the smallest honest step is the **one missing feedback-loop link** — Lane A
ingestion of a Lane B artifact — which is a real gap and would make the loop in §9 closeable. It
needs no new authorization.

**TJR PAPER TRADING REMAINS NOT AUTHORIZED. LIVE-MONEY TRADING REMAINS UNAUTHORIZED.**

---

## STEP 5 — RESEARCH FEEDBACK-LOOP PREFLIGHT (READ-ONLY)

**Status: ✅ PREFLIGHT COMPLETE. Nothing implemented, nothing committed.**
**Bridge status: `ABSENT` — proven executably. But the gap is not the one Step 4 assumed.**

### 1. Exact Lane B producer path

| Stage | Code |
|---|---|
| Scheduler | launchd `com.mogo.research.collect` → `mogo_runtime collect` → `cli.cmd_collect` |
| Spec | `scheduled_collection.validate_collection_set()` → `build_command()` |
| Authorization | `connector_authorization.evaluate()` → `derive_destination()` |
| Transport | `connector_transport.acquire()` → `content_hash(raw)` = SHA-256 of exact response bytes |
| Capability | `capabilities/acquire_approved_source_metadata.execute()` |
| Preservation | `preserve_raw()` → `intake/acquired/<contentHash>.json` |
| Artifact | `capabilities/ingest_local_artifact.execute()` → `research-artifacts/<wrapperHash>.json`, `RART\|…` |
| Roots | `research_corpus.PRODUCTION_INTAKE_ROOT`, `PRODUCTION_ARTIFACT_ROOT` |

**Lane B terminates at `research-artifacts/` + `intake/acquired/`.** `ingest_local_artifact` is
*Lane B's own* wrapper writer — despite the name, it does **not** touch the Knowledge Library.

### 2. Exact Lane A ingestion path

`scripts/trader_intelligence/ingest.py` — **two phases, with a mandatory human step between them**:

```
PHASE 1  ingest.py <transcript> --trader TJR
   phase1(): verify → SHA-256 → duplicate-check (contentHash AND canonicalRef)
   → preserve raw → normalize → propose sections → emit DRAFT manifest
   "Registers nothing in the evidence store."

[ a researcher fills in the manifest's `annotations` array ]   ← HUMAN

PHASE 2  ingest.py --apply <manifest>
   phase2(): _validate_manifest() (every excerpt VERBATIM, fail-closed)
   → intake_registry / evidence_registry → segments → annotations
   → contradictions + questions → _build_library() → build_graph → validate → dashboard
```

Supporting modules: `evidence_registry.py`, `intake_registry.py`, `annotation_pipeline.py`,
`extraction_pipeline.py`, `evidence_questions.py`, `knowledge_gaps.py`, `build_graph.py`,
`validate_evidence.py`.

### 3. Bridge status: **ABSENT** — executable proof

| Probe | Result |
|---|---|
| `research-artifacts` / `research_artifacts` in `scripts/trader_intelligence/` | **0 hits** |
| `RART\|` in Lane A scripts **or** in any Lane A evidence record | **0 hits** |
| Lane A consuming `intake/acquired/` | **0 hits** (only unrelated `acquiredAt` field names) |
| Lane B referencing `EVSRC`, `claims/`, `evidence/sources` | **0 hits** |

The two lanes share the `docs/trader-intelligence/` **directory** and have **no executable
connection in either direction.** No adapter, import, queue, watcher, manifest, CLI path, scheduler
hook or shared identifier joins them.

### 4. ⚠️ The gap is NOT what Step 4 assumed — and this changes the recommendation

Step 4 called the missing link "Lane A ingestion of a Lane B artifact," implying a small adapter.
The code says otherwise. **Two independent blockers sit in front of that adapter:**

**(a) Lane A requires human extraction judgment, by design.** `phase1` emits `"annotations": []` and
instructs the researcher to fill it; `phase2` line 335 refuses outright:
`if not m.get("annotations"): _fail(...)`. The module docstring states the reason — *"nothing enters
the evidence store until a human (or Claude) has reviewed the extraction judgments."* **An autonomous
Lane B → Lane A loop would have to bypass a deliberate governance gate.** That is not a missing
adapter; it is a designed checkpoint.

**(b) There is nothing worth bridging under current authorization.** Lane B's only approved operation
is `metadata`. The TJR artifact is **829 bytes of oEmbed JSON** — `title`, `author_name`,
`author_url`, `thumbnail_*`. It contains **no teaching content**. `phase1` expects a transcript whose
text yields verbatim excerpts; an oEmbed document yields none. **Even with a perfect bridge, ingesting
it would create an EvidenceSource with zero extractable claims and would close zero of the 17
blockers.**

**Conclusion: the feedback loop is not blocked by a missing bridge. It is blocked by the same
authorization boundary Step 4 already identified** — metadata-only acquisition — plus a deliberate
human-review gate. Building the bridge now would produce working code with nothing useful to carry.

### 5. A third structure exists and would be the right coupling point

`docs/trader-intelligence/acquisition/` + `acquisition_common.py` + `register_source.py` define an
**18-state acquisition-candidate lifecycle**:

```
DISCOVERED → REGISTERED → METADATA_PENDING → METADATA_VERIFIED → DUPLICATE_REVIEW
→ PRIORITIZED → OWNER_REVIEW → APPROVED_FOR_ACQUISITION → ACQUISITION_IN_PROGRESS
→ ACQUIRED → APPROVED_FOR_EXTRACTION → EXTRACTION_IN_PROGRESS → EXTRACTED
→ READY_FOR_RESEARCH_INTAKE → APPROVED_FOR_RESEARCH_INTAKE
```

with `STORAGE_POLICIES = [METADATA_ONLY, REFERENCED_LOCAL_CONTENT, COMMITTED_OWNER_CONTENT]` —
**`METADATA_ONLY` is precisely what Lane B produces** — and ready-made queries
`approved_but_not_acquired()`, `acquired_but_not_extracted()`, `ready_for_research_intake()`.

**It holds 0 candidates.** Declared, designed for exactly this, never populated. **A future bridge
should drive this state machine rather than invent one.**

### 6. Provenance mapping — what survives, what has no home

| Lane B field | Lane A EvidenceSource home |
|---|---|
| `contentHash` (SHA-256 external bytes) | ✅ `contentHash` |
| `acquisition.acquiredAt` | ✅ `acquiredAt` — **exists but `evidence_registry.py:74` hard-codes `None`** |
| `acquisition.finalUrl` | ✅ `externalReference` / `canonicalReference` |
| `rawContent` bytes | ✅ `repositoryPath` (file on disk) |
| trader identity | ✅ `traderId` (supplied by operator today) |
| `acquisition.sourceId` (`SRC\|…`) | ❌ **no home** — Lane A uses `EVSRC\|` |
| `authorizationId` | ❌ **no home** |
| `connectorId` / `httpStatus` / `byteLength` | ❌ **no home** |
| `artifactId` (`RART\|…`) | ❌ **no home** |

**Five acquisition-provenance fields have nowhere to land.** `EvidenceSource.metadata` is a free-form
object and could carry them without a schema change — the same pattern
`titleVerification` already uses. **No fabricated provenance; no field invented.**

### 7. Identity, immutability, idempotency — reuse, don't rebuild

| Property | Existing mechanism |
|---|---|
| Bytes never rewritten | Lane B files are **content-addressed** (`<sha256>.json`); Lane A `phase1` re-hashes and refuses on mismatch |
| Idempotent re-ingestion | `phase1` duplicate-checks on **two** keys — `contentHash` *and* `canonicalReference` — the second added 2026-07-29 after `sZAE_lqdeno` reappeared in a different transcript rendering |
| No duplicate evidence | Same two keys; Lane B additionally returns `DUPLICATE_ALREADY_INGESTED` |
| No identity mutation | `EVSRC` ids are minted once; `supersedesEvidenceId` handles revision |
| Traceable to acquisition | would require the `metadata` carry-through in §6 |

**No new hash, no new identity scheme, no new dedupe mechanism is needed.**

### 8. Authorization boundary

A bridge must **not** imply permission to acquire richer content. Lane A ingestion should
**independently verify** that the artifact was acquired under an allowed operation — the
`acquisition.decision` block already records `permitted`, `operation`, `approvedUrl` and
`authorizationId`, so the check is a read, not a new mechanism.

**Current state is unchanged: 2 approved sources, `metadata` only; transcripts, Instagram, ICT and
CRT all unauthorized.**

### 9. Failure behaviour — all fail-closed, all existing

| Condition | Existing behaviour to reuse |
|---|---|
| Malformed artifact | `phase1` `_fail()` → non-zero exit, nothing registered |
| Hash mismatch | `phase1` re-hash + reject into `intake/rejected/` (precedent: `…ALTERED-20260727.txt`) |
| Missing source identity | `_fail` — `--trader` is required and regex-validated |
| Ambiguous trader | `_fail` — no `TraderRecord` → refuse |
| Missing authorization metadata | **new check, fail closed** (§8) |
| Already ingested | duplicate-check → reject, no new records |
| Lane A validation fails | `_validate_manifest` fail-closed before any write |
| Claim extraction fails | phase 2 aborts; `rollback(intake_id)` exists |
| Graph update fails | `build_graph` is **derived** — rebuildable, never authoritative |

**`rollback()` already exists.** No new recovery infrastructure required.

### 10. Steps 2/3/4 integration — **no modification required, proven**

Steps 2–4 read the Knowledge Library through `EvidenceIndex.load(EVIDENCE_ROOT)`, which globs
`claims/`, `items/`, `links/`, `questions/`, `contradictions/`, `gaps/`. **They consume records, not
producers.** New evidence appears automatically:

- **Step 2** — `corpus_view()` selects by `Claim.traderId`; a new TJR claim is picked up with no code change.
- **Step 3** — `eligibility()` recomputes category status from whatever claims exist.
- **Step 4** — `research_plan()` re-routes from the resulting blockers and gaps.

**The only requirement is that the bridge write `traderId` on every claim** — Step 2 raises
`CorpusAmbiguous` on any unattributed claim, so a bridge that omitted it would fail the whole view
closed rather than corrupt it. That is the existing guard doing its job.

### 11. Proposed tests (designed, NOT implemented)

Valid artifact → ingestion · exact provenance preservation · SHA-256 preservation and verification ·
duplicate ingestion idempotent (both keys) · unauthorized artifact rejected · malformed artifact
rejected · ambiguous trader rejected · no foreign-corpus contamination · Step 2 sees new evidence ·
Step 3 re-evaluates deterministically · Step 4 re-plans deterministically · no executable strategy
mutation · no trading-authorization mutation · no paper/live side effects.

Mutation targets: the authorization re-check, and the duplicate-detection keys.

### 12. Minimum implementation surface, if it were built

| | |
|---|---|
| **Files modified** | ~1 new adapter in `scripts/trader_intelligence/`; optionally `evidence_registry.py` to stop hard-coding `acquiredAt=None` |
| **Schema changes** | **None required** — acquisition provenance fits `EvidenceSource.metadata` |
| **Persistence changes** | New Lane A records only (the point); no new store |
| **New frameworks** | None — reuse `ingest.py` phase 1/2, the candidate lifecycle, `rollback()` |

### 13. Risks

1. **Bypassing the human annotation gate** would silently convert a reviewed pipeline into an
   unreviewed one. **The highest risk in this milestone.**
2. **Ingesting metadata-only artifacts** would create EvidenceSources with zero claims — corpus
   noise that closes no blocker and inflates source counts.
3. **`EVSRC` vs `SRC` collapse** — the two `sourceId` namespaces mean different things; a careless
   bridge could conflate them. Step 2 already documents why they must not merge.
4. **Populating the candidate lifecycle** without operator review would let MOGO advance its own
   acquisition states.

### 14. Recommendation

**Do not build the bridge.** It is real, correctly identified and cleanly specifiable — but under
current authorization it would carry an 829-byte metadata document into a pipeline that requires
verbatim-excerpt transcripts and human annotation, closing **zero** of the 17 blockers.

The preflight has instead produced the more useful result: **the loop is gated by governance in two
places, and both are deliberate.** Step 4's three operator decisions remain the real path forward,
unchanged. If any code is wanted next, the honest smallest item is the one-line provenance fix —
`evidence_registry.py` hard-codes `acquiredAt=None` for a field the schema defines — but that is
housekeeping, not a feedback loop.

**`XCONTRA|20260728|001` was NOT ruled on and remains `open`. No EvidenceQuestion was answered. TJR
eligibility is unchanged at BLOCKED / 17 blockers. No `risk_rule` was manufactured.**

---

## STEP 6 — HUMAN EXTRACTION GOVERNANCE AUDIT (READ-ONLY)

**Status: ✅ AUDIT COMPLETE. No code, tests, schema or records changed. Gate not altered.**

### 1. The exact human gate

| | |
|---|---|
| **Executable requirement** | `scripts/trader_intelligence/ingest.py` → `_validate_manifest()` line 335: `if not m.get("annotations"): errs.append("`annotations` is empty -- nothing to apply")` |
| **Phase 1** | `phase1()` verifies file, SHA-256, duplicate-checks, normalizes, proposes sections, emits a draft manifest with `"annotations": []`. **Registers nothing.** |
| **Phase 2** | `phase2()` runs `_validate_manifest()` first; every error is fatal before any write |
| **Documentation** | module docstring: *"nothing enters the evidence store until a human (or Claude) has reviewed the extraction judgments"* |
| **Historical rationale** | `docs/trader-intelligence/STANDARDS-extraction.md` — **Normative**, derived from `INTAKE\|TJR\|20260727\|001`: *"Two operators who classify the same sentence differently produce two different Knowledge Libraries from identical evidence. These are not stylistic preferences; they are the inputs to the engine."* |
| **Tests enforcing it** | **none found** — the gate is enforced by the executable path, not by a test |

**The rationale is determinism of downstream engine inputs, not distrust of machines per se.** That
distinction matters: it means the gate's purpose can in principle be met by anything that makes
classification reproducible.

### 2–3. What the human judges, and how much of it is mechanical

`STANDARDS-extraction.md` states **two inviolable rules**, and they fall on opposite sides of the line:

- **Rule 1 — `exactExcerpt` is verbatim, always.** The document itself says this is *"machine-enforced
  rather than trusted."* ✅ Already deterministic.
- **Rule 2 — `proposedClaim` restates; it never adds.** With worked counterexamples (adding a time
  window, inventing a stop buffer, inventing a reliability claim) and *the generalization test*:
  *"If you find yourself reasoning 'he'd obviously also do X', stop."* ❌ **Not machine-enforced.**

| Annotation field | Judgment required | Class |
|---|---|---|
| `excerpt` verbatim containment | none — substring test | **MECHANICALLY VERIFIABLE** (enforced) |
| `section` exists, `key` unique | none | **MECHANICALLY VERIFIABLE** (enforced) |
| `evidenceType`, `directness`, `extractionCertainty`, `evidenceQuality` | vocabulary membership | **MECHANICALLY VERIFIABLE**; *which* value → **SEMANTIC, OBJECTIVELY CHECKABLE** against STANDARDS §3–§5 |
| `claimType` | vocabulary membership enforced; assignment → taxonomy judgment | **SEMANTIC, OBJECTIVELY CHECKABLE** |
| `supports` / `supportsClaimId` | referential integrity | **MECHANICALLY VERIFIABLE** (enforced) |
| **`claim` (normalizedClaim)** | **Rule 2 — restates without adding** | **INTERPRETIVE** |
| which excerpt to select / where to cut sections | relevance judgment | **INTERPRETIVE** |
| `contradictions[]` | identifying incompatibility | **INTERPRETIVE** |
| `openQuestions[]` | recognising ambiguity | **INTERPRETIVE** |
| contradiction *resolution*, promotion, freeze | — | **GOVERNANCE / CONSEQUENCE-SENSITIVE** |

**The machine already validates the FORM completely. The human supplies the JUDGMENT.** No mechanical
check is currently delegated to a person.

### 4. Usable safety signals — populated, not merely defined

| Signal | Populated? |
|---|---|
| `exactExcerpt` | ✅ **366 / 366** (100%) |
| `contentHash` | ✅ **366 / 366** (100%) |
| `directness`, `extractionCertainty`, `evidenceQuality`, `evidenceType` | ✅ 100% |
| `traderId` on claims | ✅ 100% |
| `EvidenceClaimLink.relationshipType` / `independenceGroup` | ✅ 100% |
| `ContradictionRecord`, `EvidenceQuestion.blockingStatus` | ✅ populated (16 / 281) |
| **`strategyFamilyId`** | ❌ **null on all 341 claims — unusable** |
| **`answerEvidenceIds`** | ❌ **empty on all 281 questions — unusable** |
| **multi-source support** | ❌ **does not exist** — every link is one independence group (`AUTHOR\|ALEX_G`, `AUTHOR\|TJR`), so **all 295 claims are `emerging`**; POLICY-001 caps them there |

### 5. Empirical distribution (descriptive only)

| | ALEX_G (280 items) | TJR (86 items) |
|---|---|---|
| Charter **Explicit** | **269 (96.1%)** | **75 (87.2%)** |
| Implicit | 0 | 3 |
| Inferred | 0 | 1 (inside "Unknown") |
| Opinion | 4 | 1 |
| Unknown | 7 | 7 |
| certainty `certain`/`high` | 271 | 70 |
| `exactExcerpt` / `contentHash` | 100% / 100% | 100% / 100% |

**The corpus is overwhelmingly explicit** — which is what makes the question worth asking at all.

### 6. Proposed strict acceptance predicate (design only)

Eleven deterministic predicates, all fail-closed, evaluated **against SUPPORTING evidence only**
(`relationshipType ∈ {supports, exemplifies}`) — see §12 for why that distinction is load-bearing:

P1 registered governed source · P2 `contentHash` present · P3 unambiguous `traderId` ·
P4 `exactExcerpt` present · P5 supporting `EvidenceClaimLink` resolves ·
P6 Charter class **Explicit** · P7 `extractionCertainty ∈ {certain, high}` ·
P8 no open blocking `EvidenceQuestion` · P9 no open `ContradictionRecord` ·
P10 `claimType` in taxonomy · P11 deterministic validation passes.

**These are necessary. They are NOT sufficient — see §9.**

### 7. Mandatory human escalation

`inferred_from_context` / `derived_from_analysis` · `indirect_implied` on a required category ·
any open contradiction · ambiguous trader or strategy identity · missing provenance ·
novel taxonomy value · **any claim whose text is not entailed by its excerpt** · rule reconstruction ·
inferred risk rules · conflict resolution · specification freeze · paper promotion · live
authorization. **Unknown always escalates.**

### 8. Testability — deterministic vs model-based, kept apart

| Deterministic proof | Model-based verification (**NOT** proof) |
|---|---|
| excerpt containment · hash equality · identity resolution · duplicate keys · referential integrity · corpus isolation · mutation tests · ground-truth fixtures | second-pass paraphrase comparison · entailment checking · disagreement escalation |

**Model agreement is not determinism.** Two models agreeing on a paraphrase is correlated evidence,
not proof — and if the same model family produced and checked the extraction, it is **self-confirmation**.
Any future verifier must be independent by construction, and its output should gate *escalation*,
never *acceptance*.

### 9. Failure modes vs existing detection

| Failure mode | Detected today? |
|---|---|
| Hallucinated claim (no excerpt) | ✅ verbatim-substring check |
| **Faithful quote, wrong interpretation** | ❌ **Rule 2 not machine-enforced** |
| **Lost qualifier** | ❌ |
| Wrong timeframe | ⚠️ `missing_timeframe` question exists — human-authored |
| Wrong trader | ✅ `--trader` + `TraderRecord`; Step 2 `CorpusAmbiguous` |
| **Wrong strategy family** | ❌ `strategyFamilyId` null everywhere |
| Exception → general rule | ⚠️ `claimType: exception` exists; STANDARDS §2 records a **known defect** |
| Example mistaken for instruction | ⚠️ `evidenceType: trade_example / chart_example` |
| **Historical description as current rule** | ❌ no temporal-validity field |
| Contradictory evidence ignored | ✅ `ContradictionRecord` + Step 3 blocks |
| Duplicate evidence → false support | ✅ `independenceGroup` + POLICY-001 caps at `emerging` |
| **Model self-confirmation** | ❌ no independent verifier exists |

**Five of twelve are undetected, and four of those five live in the claim paraphrase.**

### 10. Autonomy tiers — defensible decomposition

| Tier | Scope | Verdict |
|---|---|---|
| **0 — Mechanical** | hash, identity, excerpt containment, dedupe, preservation | ✅ **already fully deterministic and machine-enforced today** |
| **1 — Evidence-item classification** | `directness`, `evidenceType`, certainty on an explicit excerpt | ⚠️ **arguably defensible** — bounded enums with a documented decision procedure (STANDARDS §3–§5) |
| **2 — Claim creation (paraphrase)** | Rule 2 | ❌ **not defensible deterministically** |
| **3 — Strategy reconstruction** | rules, blueprint | ❌ operator |
| **4 — Trading promotion** | paper, live | ❌ operator |

### 11. Feedback-loop relationship

A future Lane B → Lane A bridge would sit **entirely inside Tier 0**: preserve, hash, identify,
dedupe. **It would still stop at the Tier 2 boundary**, exactly as today — which is consistent with
Step 5's conclusion and means the bridge would not be blocked by this audit, nor unblocked by it.

### 12. TJR simulation (read-only, nothing approved)

| | TJR | ALEX_G |
|---|---|---|
| Claims | 69 | 226 |
| **Would pass P1–P11** | **42 (60.9%)** | **106 (46.9%)** |
| Would escalate | 27 (39.1%) | 120 (53.1%) |

Escalation drivers — TJR: certainty 12, blocking question 10, not-Explicit 8, contradiction 7.
ALEX: **blocking question 106**, contradiction 19, not-Explicit 11, certainty 7.

**I corrected my own first run.** It evaluated *all* links, including `contextualizes`. That mattered:
`CLAIM|TJR|20260727|003` ("New York pre-market starts at 8:30") looked like a Rule-2 violation
because its first-listed excerpt discusses the 9:30 open — but that link is `contextualizes`, and its
`supports` link is the verbatim sentence. **There was no defect; my check was wrong.** The predicate
must evaluate supporting relationships only, and it now does.

### **The decisive finding**

> **Only 1 of 295 claims (0.3%) is verbatim-identical to its supporting excerpt.**
> **294 involve a human paraphrase judgment that no predicate in §6 can verify.**

So even a claim passing all eleven predicates still rests on an unverified Rule-2 judgment. The
predicates gate *provenance and context*; they say nothing about whether the claim adds a threshold,
a timeframe or a condition the excerpt does not contain.

### 13. Is partial autonomous acceptance scientifically defensible?

**At Tier 0, yes — and it already is.** At Tier 1, arguably, with independent verification gating
escalation. **At Tier 2, no** — and Tier 2 is where 99.7% of the corpus actually lives, so the
practical answer today is **no meaningful reduction in human review is currently defensible.**

The one honest exception: a claim whose text is *verbatim* its excerpt requires no Rule-2 judgment at
all and could be accepted deterministically. **That describes exactly 1 of 295 claims.**

### 14. Risks

1. **Predicate false confidence** — 60.9% "would pass" invites reading the predicate as validation of
   claim content. It is not.
2. **Model self-confirmation** — the largest scientific risk, and undetected today.
3. **Automating classification would change the corpus** — `directness` drives `TraderProfile` concept
   status, gap detection and Step 3 eligibility. A reclassification is a silent re-derivation.
4. **Escalation-rate drift** — if escalation is tuned by volume rather than evidence, rigor decays
   invisibly.

### 15. Smallest recommended next implementation

**None in this direction.** Autonomy at Tier 2 is not defensible today, and Tiers 0–1 are already
machine-enforced or blocked by the same governance decisions Step 4 identified.

If a small, genuinely useful item is wanted, it is a **read-only Rule-2 conformance report**: for each
claim, show excerpt beside `normalizedClaim` and flag the mechanically checkable subset — claims
containing a number, timeframe or instrument **absent from every supporting excerpt**. That would not
approve anything; it would let a human review 295 claims by exception instead of exhaustively, and it
is exactly the check the corpus currently lacks.

**`XCONTRA|20260728|001` NOT ruled on. 0 EvidenceQuestions answered. 0 RuleCandidateProposal records.
TJR eligibility unchanged at BLOCKED / 17. Human annotation gate unchanged and not bypassed.**

---

## STEP 7 — RULE-2 CONFORMANCE / REVIEW-BY-EXCEPTION

**Status: ✅ COMPLETE — GREEN. Not committed, held for review.**
**Read-only · zero schema changes · zero persistence · approves nothing.**

### 1. Architecture and files

| File | Lines | Role |
|---|---|---|
| `scripts/trader_intelligence/rule_conformance.py` | **~430** | derived read-only analyzer + CLI |
| `tests/trader_intelligence/test_rule_conformance.py` | **~400** | 37 focused tests |

A **separate module**, not an extension of `research_understanding.py`: Rule-2 conformance is
claim-vs-excerpt lexical analysis, a different concern from corpus understanding, with its own CLI.
It reuses `EvidenceIndex.load()` and — importantly — `evidence_common._SUPPORTING_RELATIONSHIPS`
rather than redefining what "support" means.

```
python3 scripts/trader_intelligence/rule_conformance.py --trader TJR [--all] [--json]
```

### 2. What it checks, and what that is

Rule 1 (verbatim excerpt) is already machine-enforced by `ingest.py`. **Rule 2 is not.** This
analyzer does not check Rule 2 either — it checks a **deterministic shadow** of it: concrete tokens
present in the claim and absent from **every** supporting excerpt.

| Class | Detects |
|---|---|
| `REVIEW_NUMERIC` | integers, decimals, percentages (thousands separators normalized) |
| `REVIEW_TIME` | clock times, AM/PM, `M1`–`D1` timeframe tokens, minute/hour/day/session words |
| `REVIEW_INSTRUMENT` | currency pairs (closed currency-code list) and index/symbol tokens |
| `REVIEW_DIRECTION` | long/short, buy/sell, bullish/bearish, upside/downside |
| `REVIEW_QUANTIFIER` | always, never, every, only, must, exactly, all, none, any, no |

Plus fail-closed states `MISSING_SUPPORT`, `AMBIGUOUS_SUPPORT`, `PROVENANCE_FAILURE`, and
`REVIEW_MULTIPLE` when more than one class fires.

### 3. Normalization — conservative, and deliberately incomplete

Applied: case-fold · whitespace collapse · thousands separators (`1,000` → `1000`) · punctuation to
spaces · currency-pair separators (`EUR/USD` = `EUR-USD` = `EURUSD`).

**Deliberately NOT applied:** no stemming, no synonym table, **no ordinal expansion**. `first` is not
treated as `1`, and `day` is not treated as `daily`. Those are morphological/semantic judgments, not
deterministic formatting — so they are **surfaced**, and §7 below quantifies the cost. A test pins
this refusal.

A closed currency-code list prevents `_PAIR` firing on ordinary three-letter words — without it,
"the low was" would flag as an instrument.

### 4. Support semantics — the Step 6 lesson, encoded

Only `supports` and `exemplifies` are read. The corpus contains **415 `supports` and exactly 1
`contextualizes`** — and that single record is the one that misled Step 6's first pass.
`CLAIM|TJR|20260727|003` ("New York pre-market starts at 8:30") has a contextualizing excerpt about
the 9:30 open and a supporting excerpt that is the verbatim sentence. **A dedicated test asserts this
claim is `CLEAN` and that no supporting excerpt contains "9:30".** Treating `contextualizes` as
support makes it a false Rule-2 violation.

Relationships are resolved by identifier and type. An unrecognised `relationshipType` yields
`AMBIGUOUS_SUPPORT`, never `CLEAN`.

### 5. Results

| | **TJR** | **ALEX_G** |
|---|---|---|
| Total claims | **69** | **226** |
| `CLEAN_MECHANICAL_MATCH` | **40 (58.0%)** | **113 (50.0%)** |
| Needing review | **29 (42.0%)** | **113 (50.0%)** |
| `REVIEW_QUANTIFIER` | 7 | 46 |
| `REVIEW_TIME` | 10 | 10 |
| `REVIEW_NUMERIC` | 6 | 11 |
| `REVIEW_DIRECTION` | 4 | 8 |
| `REVIEW_INSTRUMENT` | 0 | 1 |
| `REVIEW_MULTIPLE` | 2 | 37 |
| `MISSING_SUPPORT` / `AMBIGUOUS_SUPPORT` / `PROVENANCE_FAILURE` | **0 / 0 / 0** | **0 / 0 / 0** |

**Discrepancy tokens by class** (a claim may contribute to several) — TJR: quantifier 8, time 12,
numeric 7, direction 4, instrument 0. ALEX: **quantifier 75**, time 31, numeric 36, direction 16,
instrument 2.

**Directness distribution** — CLEAN vs FLAGGED are nearly identical (TJR clean 40 `direct_explicit`
vs flagged 31; ALEX clean 123 vs flagged 120). **Flagging is not a proxy for weak evidence** — these
are well-sourced claims whose *paraphrase* adds a token.

### 6. Representative true positives

| Claim | Flag | Excerpt says | Claim says |
|---|---|---|---|
| `CLAIM\|ALEX_G\|20260727\|026` | `must`, `never` | *"the area of interest **should only** be found inside of the high and the low"* | *"**must** lie inside … **never** outside that range"* |
| `CLAIM\|TJR\|20260727\|004` | `never` | *"we **don't want to** take trades on the lagging index"* | *"… **never** on the lagging index"* |
| `CLAIM\|TJR\|20260727\|011` | `session` | *"if this high right here has already been pushed past…"* | *"A **session** high or low that has already been swept…"* |
| `CLAIM\|TJR\|20260727\|014` | `only`, `all` | *"We just need one to confirm"* / *"We don't need every single one"* | *"**Only** one … **all** four are not needed"* |

`ALEX_G|026` is the clearest: **`should only` → `must … never`** is a modal escalation of exactly the
kind STANDARDS §1 Rule 2 warns against. **Surfaced for review — not adjudicated here.**

### 7. False positives — measured, not estimated

Mechanically identifiable FP classes, counted over all flagged tokens:

| Class | TJR | ALEX_G |
|---|---|---|
| Numeric: MOGO `"Step N"` label (the number is a MOGO sequence label, not a source claim) | 4 | 0 |
| Numeric: ordinal word present in excerpt (`first` vs `1`) | 0 | 14 |
| Time: morphological variant (`day` vs `daily`) | 3 | 8 |
| **Total identifiable FP** | **7 / 35 (20%)** | **22 / 221 (10%)** |
| Remaining, requiring human judgment | 28 (80%) | 199 (90%) |

**"Requiring human judgment" is not the same as "true positive."** Some of the 199 will be faithful
paraphrases a reviewer clears in seconds — which is the intended output of review-by-exception, not a
defect.

### 8. What this CAN and CANNOT prove

**CAN prove:** a specific token in the claim occurs in no supporting excerpt — a lexical fact from
exact comparison after conservative normalization.

**CANNOT prove:** that any claim is faithful, correct, approved or semantically equivalent to its
evidence.

> **`CLEAN_MECHANICAL_MATCH` means EXACTLY ONE THING: no discrepancy was detectable by the checks
> implemented here. IT IS NOT APPROVAL.**

That sentence is carried in the module docstring, in the report's `cleanMeaning` field, in the CLI
footer, and asserted by three tests. **A paraphrase can violate Rule 2 using only words present in
the excerpt, and this analyzer will not see it** — a false negative class it cannot close.

The human semantic-review requirement in `ingest.py` is **unchanged and remains authoritative**.

### 9. Tests — 37, five mutations caught

Adversarial mutations of one real clean pair: changed number · changed timeframe (two forms) ·
changed instrument · inserted direction · inserted always/never/only/every/must/exactly · combined
multi-class · token present in *any* supporting excerpt not flagged.
Plus: formatting equivalence (4 pair forms, case/punctuation, thousands separators) · normalization
refusing to resolve meaning · three-letter words not mistaken for pairs · support-relationship
semantics incl. the `contextualizes` regression · fail-closed (missing/empty/malformed/unresolvable/
unknown corpus) · corpus isolation incl. foreign-trader evidence · CLEAN-is-not-approval · determinism
· firewall.

| Mutation | Caught |
|---|---|
| Treat `contextualizes` as support | ✅ 3 tests |
| Drop the quantifier check | ✅ (crashes the suite — detected, though as an error rather than a clean failure) |
| `MISSING_SUPPORT` → `CLEAN` | ✅ 2 tests |
| Skip the foreign-trader isolation check | ✅ |
| Suppress numeric extraction | ✅ 3 tests |

### 10. Firewall — proven structurally

Tests assert the module: opens no file for writing (no `"w"`/`"a"`/`remove`/`shutil`/`unlink`/
`rmtree`/`mkdir`/`setattr`); names no `index.html`, `docs/campaigns`, `hypothesis-registry`,
`PREREG-`, `proposals`, `blueprints` or `graph/build`; imports **only**
`argparse, json, os, re, sys, query_evidence, evidence_common`; contains **no** identifier segment
from {paper, backtest, live, trade, trading, order, execute, promote, promotion, freeze, approve,
resolve, answer}; leaves every evidence file byte-identical by SHA-256; and leaves contradiction
statuses, question `answerStatus` values and the empty `proposals/` directory unchanged.

### 11. Integrity

| Gate | Result |
|---|---|
| Step 7 focused suite | ✅ **37 / 37** |
| Step 2–4 suite (unchanged) | ✅ **95 / 95** |
| Platform suite | ✅ **25 suites · 1,049 tests · 0 failures** |
| Canonical gate | ✅ **19 suites · 1,160 / 1,160** |
| **Protected ALEX drift** | ✅ **0** — 63 functions, 4 constants |
| Campaign C1 | ✅ 33 / 33 |
| Runtime integrity | ✅ INTEGRITY OK |
| `XCONTRA\|20260728\|001` | ✅ **open / blocking / unresolved** |
| Questions answered · proposals | ✅ **0 of 281 · 0** |
| TJR eligibility | ✅ **BLOCKED / 17** |

### 12. Scientific interpretation

The analyzer converts an exhaustive 295-claim re-read into a **142-claim exception queue** — real
leverage, and it found a concrete modal escalation (`should only` → `must … never`) that survived
human review.

**But it does not move the Step 6 conclusion.** It closes no part of the Rule-2 gap: it cannot verify
that a CLEAN claim is faithful, and 153 CLEAN claims remain exactly as unverified as before. It is a
**review aid**, not a verification mechanism, and `CLEAN_MECHANICAL_MATCH` must never be read as
approval.

### 13. Recommendation for Step 8

**Do not extend the analyzer to reduce false positives.** The two identified classes — ordinal words
and MOGO `Step N` labels — are 10–20% of flags and cost a reviewer seconds each. Suppressing them
means adding lexical mappings that could equally hide a real addition, which trades a cheap known
cost for an unbounded unknown one.

**The honest next step is human, not code:** work the 142-claim exception queue, starting with the
**121 quantifier/modal flags** (75 ALEX + 8 TJR tokens), because modal escalation is the class most
likely to change a rule's meaning and is exactly what STANDARDS Rule 2 exists to prevent.

If code is wanted, the smallest useful item remains unchanged from Step 4: this analyzer does not
alter the fact that **0 of 17 TJR blockers are autonomously resolvable**, and the three operator
decisions are still the path forward.

**Nothing was approved, resolved, answered or promoted. The annotation gate is untouched.**

---

## STEP 8 — EXCEPTION QUEUE TRIAGE AND HUMAN-REVIEW OPTIMIZATION

**Status: ✅ COMPLETE — GREEN. Not committed, held for review.**
**Step 7 checkpoint: `9cee8095f4141e9fb01c1766cadeb75c86fde57c`**
**Read-only · zero schema changes · zero persistence · adjudicates nothing.**

### 1. Architecture and files

| File | Lines | Role |
|---|---|---|
| `scripts/trader_intelligence/exception_triage.py` | ~380 | triage + blocker impact + review packets |
| `tests/trader_intelligence/test_exception_triage.py` | ~340 | 32 focused tests |

**A composition of three existing views** — the Step 7 conformance report, the Step 2 corpus view and
the Step 3 eligibility predicate. It performs **no new analysis of the evidence**; it only asks which
already-flagged claims deserve a human's time, and in what order. `CLEAN_MECHANICAL_MATCH` keeps its
Step 7 meaning exactly.

```
python3 scripts/trader_intelligence/exception_triage.py --trader TJR [--limit N] [--json]
```

### 2. Triage classes and priority

Fixed list position, never a computed number:

```
BLOCKER_RELEVANT > CRITICAL_RULE_MEANING > MODAL_OR_QUANTIFIER_ESCALATION
  > NUMERIC_OR_TIME_CHANGE > INSTRUMENT_OR_DIRECTION_CHANGE
  > GENERAL_SEMANTIC_REVIEW > LIKELY_MECHANICAL_FALSE_POSITIVE
```

**Nothing is dropped on a guess.** A claim is downgraded only when **every** flagged token was
*demonstrated* mechanical (a MOGO `Step N` label, an ordinal word actually present in the excerpt, a
morphological variant actually present). One unexplained token keeps it in the real queue, and a
**blocker-relevant claim is never demoted at all** — three tests and two mutations pin this.

### 3. Results — 142 exceptions triaged

| | **TJR** | **ALEX_G** | **Combined** |
|---|---|---|---|
| Total claims | 69 | 226 | **295** |
| CLEAN (not approved) | 40 | 113 | **153** |
| Flagged | 29 | 113 | **142 (48.1%)** |
| **Rule-category claims** | **14** | **67** | **81** |
| **Required-category claims** | **8** | **34** | **42** |
| **Blocker-relevant** | **5** | **70** | **75** |
| Demonstrable false positives | 3 | 1 | **4** |

**Priority distribution** — TJR: blocker-relevant 5, critical-rule 9, numeric/time 6, modal 3,
instrument/direction 3, likely-FP 3. ALEX: blocker-relevant 70, critical-rule 18, modal 15,
numeric/time 7, instrument/direction 2, likely-FP 1.

Note the asymmetry: **ALEX's queue is dominated by blocker-relevant claims (70 of 113)** because
ALEX carries 106 blocking questions; TJR's is dominated by rule-meaning and numeric/time.

### 4. TJR dedicated queue (8F)

Of the 29 flagged TJR claims: **14 are rule-category**, **8 touch a required category**, **5 are
blocker-relevant**, 8 carry modal/quantifier flags, 18 carry numeric/time flags, 4
instrument/direction, and **3 are demonstrable mechanical false positives**.

**Minimum set whose review could change TJR eligibility: 9 claims** —
`|004`, `|008`, `|010`, `|011`, `|018`, `|027`, `|028`, `|055`, `|066`.

**From 69 claims to 9.** But see §5 for what that review can and cannot achieve.

### 5. The 17-blocker impact map (8G) — **the load-bearing result**

| Impact | Count |
|---|---|
| `REVIEW_CAN_RESOLVE` | **0** |
| `REVIEW_CAN_CLARIFY_BUT_NOT_RESOLVE` | **8** |
| `REVIEW_CANNOT_RESOLVE` | **9** |

| Blocker | Required | Impact | flagged/related |
|---|---|---|---|
| `REQUIRED_CATEGORY\|setup_requirement` | ✅ | CLARIFY | 5/9 |
| `REQUIRED_CATEGORY\|entry_rule` | ✅ | CLARIFY | 1/1 |
| `REQUIRED_CATEGORY\|stop_rule` | ✅ | CLARIFY | 1/1 |
| `REQUIRED_CATEGORY\|risk_rule` | ✅ | **CANNOT** — no claim exists to review | 0/0 |
| `EQ\|…\|002`, `008`, `009`, `013`, `016` | mixed | CLARIFY | 1/1 each |
| `EQ\|…\|003`, `004`, `007`, `012`, `014`, `017`, `018` | mixed | CANNOT | 0/1 each |
| **`XCONTRA\|20260728\|001`** | — | **CANNOT — operator ruling** | 0/1 |

**`REVIEW_CAN_RESOLVE` is computed, not assumed, and its emptiness is the finding.** Blockers exist
because of unanswered `EvidenceQuestion`s and open `ContradictionRecord`s. A Rule-2 review decides
whether a **paraphrase overreached**. Those are different questions — so review can establish that
MOGO's wording was faithful (or wasn't), but it cannot answer what the trader meant, settle a
disagreement between two educators, or bring a missing `risk_rule` into existence.

**Reviewing all 142 exceptions would change TJR's eligibility from BLOCKED/17 to… BLOCKED/17.**

A mutation that makes the code claim `REVIEW_CAN_RESOLVE` fails the test.

### 6. XCONTRA position (8H)

`XCONTRA|20260728|001` sits at **`REVIEW_CANNOT_RESOLVE`** with `stillRequiresOperatorRuling: true`.
No TJR claim on its side is flagged, so there is nothing for Rule-2 review to examine. **It remains
`open` / `blocking` / `resolution: null`.**

The decision that would eventually be required is an operator ruling on whether Alex G's *"there's no
way you can have a specific strategy to trade solely off of these sweeps"* and TJR's *"my strategy is
based off of liquidity sweeps"* are genuinely incompatible, or scope-dependent — the record's own
rationale already notes they are *"closer in practice than the words suggest"* while marking it
blocking because *"the reconciliation is MOGO's reading, not either educator's statement."*
**That decision was not made here.**

### 7. Human workload (8I)

| | Count | % of corpus |
|---|---|---|
| **A** — claims requiring semantic judgment originally | **295** | 100% |
| **B** — Step 7 exception count | **142** | 48.1% |
| **C** — mechanically clean (**not approved**) | **153** | 51.9% |
| **D** — demonstrable false positives | **4** | 1.4% of corpus, 2.8% of queue |
| **E** — strategy-relevant exceptions | **81** | 27.5% |
| **F** — TJR strategy-relevant exceptions | **14** | 4.7% |
| **G** — TJR blocker-impacting exceptions | **9** | 3.1% |
| **H** — minimum set able to change TJR eligibility | **0** | **0%** |

**Read H carefully.** The *minimum review set* is 9 claims, but the set capable of **changing
eligibility** is **empty**, because no blocker is review-resolvable. Reviewing those 9 improves
corpus accuracy; it does not unblock reconstruction.

**Honest accounting of what MOGO eliminated:** it reduced a 295-claim exhaustive re-read to a
142-claim ordered queue whose top 81 are strategy-relevant — roughly a **52% reduction in claims
needing a look, and a 73% reduction if only strategy-relevant ones are worked**. It eliminated **no**
semantic judgment: the 153 CLEAN claims remain exactly as unverified as before.

### 8. Review packet (8J)

Implemented as CLI output only — no UI, no persisted adjudication:

```
[1] CLAIM|TJR|20260727|004   priority=BLOCKER_RELEVANT
    STRATEGY IMPACT : claimType=setup_requirement  [RULE CATEGORY]  [REQUIRED]
    SOURCE          : "we don't want to take trades on the lagging index..."
                      (EV|EVSRC|TJR|20260727|001|005  direct_explicit/high)
    MOGO INTERPRETATION: Trades are taken on the leading index, never on the lagging index.
    WHY FLAGGED     : REVIEW_QUANTIFIER -- 'never' absent from every supporting excerpt
    HUMAN DECISION  : [ ] faithful   [ ] not faithful   [ ] uncertain / needs more evidence
```

The decision boxes are **printed, never recorded** — a test asserts no `decision`, `adjudicated`,
`approved` or `accepted` field exists anywhere in the output.

### 9. Tests — 32, four mutations caught

Determinism · fixed-rank ordering · no numeric score · CLEAN claims absent from the queue · strategy
relevance from the shared schema vocabulary · unknown claimType not treated as critical · downgrade
requires *every* token demonstrated · partly-demonstrated stays queued · blocker-relevant never
demoted · every blocker mapped once · **no blocker resolvable** · missing category has nothing to
review · contradiction still needs an operator · minimum set ⊆ queue · trader isolation · support-
relationship isolation survives composition · unknown corpus refused · firewall.

| Mutation | Caught |
|---|---|
| Downgrade on *any* demonstrated token | ✅ 2 tests |
| Demote a blocker-relevant claim | ✅ |
| Claim a blocker is `REVIEW_CAN_RESOLVE` | ✅ |
| Treat every claimType as strategy-critical | ✅ 3 tests |

**One test I wrote was wrong and I fixed the test:** it banned the identifier segment `order`, which
flagged `PRIORITY_ORDER` — sort order, not a trade order. The trading sense is already covered by
`trade`/`trading`/`execute`.

### 10. Firewall

No write mode, no `open(` at all, imports limited to
`argparse, json, os, re, sys, research_understanding, rule_conformance, query_evidence`, no trading or
adjudication identifier segment, evidence digests unchanged, `proposals/` still empty, and eligibility
reported but unchanged (**BLOCKED / 17**).

### 11. Integrity

| Gate | Result |
|---|---|
| Steps 2–4 + 7 + 8 focused | ✅ **164 / 164** (95 + 37 + 32) |
| Platform suite | ✅ **25 suites · 1,049 tests · 0 failures** |
| Canonical gate | ✅ **19 suites · 1,160 / 1,160** |
| **Protected ALEX drift** | ✅ **0** |
| Campaign C1 | ✅ 33 / 33 |
| Runtime integrity | ✅ INTEGRITY OK |
| `XCONTRA\|20260728\|001` | ✅ open / blocking / unresolved |
| Questions answered · proposals | ✅ 0 of 281 · 0 |
| TJR eligibility | ✅ BLOCKED / 17 |

### 12. Future autonomy (8K) — what MOGO can and cannot do alone

| Capability | Autonomous today? |
|---|---|
| 1. Acquire authorized material | ✅ **yes** — proven unattended at GATE-3E |
| 2. Preserve it immutably | ✅ **yes** — content-addressed, hash-verified |
| 3. Mechanically extract candidate evidence | ❌ **no** — `ingest.py` requires human annotation; Step 6 found 294/295 claims rest on a paraphrase judgment |
| 4. Run deterministic conformance checks | ✅ **yes** — Step 7 |
| 5. Prioritize exceptions | ✅ **yes** — Step 8 |
| 6. Determine what needs new evidence | ✅ **yes** — Step 4, from `recommendedNextSourceType` |
| 7. Determine what needs trader clarification | ✅ **yes** — Step 4 |
| 8. Determine what needs operator judgment | ✅ **yes** — Steps 3, 4, 8 |

**Unavoidable human judgment remains in exactly two places:**

1. **Claim creation (Rule 2)** — deciding that a paraphrase restates without adding. 294 of 295
   claims depend on it and no deterministic check can close it.
2. **Adjudication of conflicts and ambiguity** — answering an `EvidenceQuestion`, ruling on a
   contradiction, or deciding a scope distinction.

Everything *around* those two — acquisition, preservation, conformance checking, prioritization,
routing, and knowing which of the three human actions is needed — MOGO now does autonomously. **The
work MOGO has eliminated is the search for what to look at. The work it has not eliminated, and
cannot, is the judgment itself.**

### 13. Recommendation for Step 9

**Stop building analysis. The tooling has reached its useful limit for this corpus.**

Steps 3, 4, 7 and 8 have each independently converged on the same three human decisions, and Step 8
now proves the strongest form of it: **no amount of further automated analysis can change TJR's
eligibility.** Building a Step 9 analyzer would add code that cannot move the outcome.

The three decisions, unchanged since Step 4:

1. **Rule on `XCONTRA|20260728|001`** — closes 2 blockers.
2. **One clarification session with TJR** — addresses 8, including the critical `risk_rule` that no
   transcript can supply.
3. **Decide whether transcript-class acquisition is ever authorized** — unblocks 6, and I continue to
   **recommend against it** (MOGO-015 Step 1A: empty body, and pursuing it means working around an
   access control).

If review work is wanted first, the honest ordering is the **9-claim TJR minimum set**, then the
**75 blocker-relevant claims** across both corpora — with the expectation that this improves accuracy
and changes eligibility for **nothing**.

**Nothing was adjudicated, answered, resolved or promoted. The annotation gate is untouched.**

---

## STEP 9 — RESEARCH-GAP RESOLUTION PLANNER

**Status: ✅ COMPLETE — GREEN. Not committed, held for review.**
**Step 8 checkpoint: `43fb3b6721a874ec1ad9f98ecb7336e8b2c438f5`**
**Read-only audit. NO executable code added — performed with ad-hoc read-only queries over the
existing MOGO-019 tooling (`rule_conformance`, `research_understanding`, `EvidenceIndex`).**

### 1. The 17 blockers, enumerated

**A finding that shaped everything below: all 12 blocking questions carry
`answerEvidenceIds: (none)` and `evidenceIds: (none)`.** Not one question has ever been linked to
evidence. That is why a corpus search was worth doing at all.

| Blocker | Type | Category (req) | Blocking | Answer status |
|---|---|---|---|---|
| `EQ\|…\|002` | missing_stop_placement | stop_rule ✅ | rule_candidate | unanswered |
| `EQ\|…\|003` | missing_target_logic | target_rule | rule_candidate | unanswered |
| `EQ\|…\|004` | unclear_scope | definition | **promotion** | unanswered |
| `EQ\|…\|007` | unruled_exception | setup_requirement ✅ | rule_candidate | unanswered |
| `EQ\|…\|008` | ambiguous_statement | entry_rule ✅ | rule_candidate | unanswered |
| `EQ\|…\|009` | unclear_scope | confirmation_rule | rule_candidate | unanswered |
| `EQ\|…\|012` | missing_timeframe | session_rule | rule_candidate | unanswered |
| `EQ\|…\|013` | missing_invalidation | entry_rule ✅ | rule_candidate | unanswered |
| `EQ\|…\|014` | missing_timeframe | target_rule | rule_candidate | unanswered |
| `EQ\|…\|016` | unclear_scope | definition | rule_candidate | unanswered |
| `EQ\|…\|017` | unclear_scope | setup_requirement ✅ | rule_candidate | unanswered |
| `EQ\|…\|018` | implied_requirement | exception | rule_candidate | unanswered |
| `REQUIRED_CATEGORY\|setup_requirement` | CONFLICTED ✅ | — | — | — |
| `REQUIRED_CATEGORY\|entry_rule` | AMBIGUOUS ✅ | — | — | — |
| `REQUIRED_CATEGORY\|stop_rule` | AMBIGUOUS ✅ | — | — | — |
| `REQUIRED_CATEGORY\|risk_rule` | MISSING ✅ | — | — | — |
| `XCONTRA\|20260728\|001` | DIRECTIONAL | setup_requirement ✅ | blocking | open |

### 2. Existing-corpus search — **four genuine near-misses found**

Method: lexical search over the **86 TJR evidence items** (2 governed sources) to **nominate**
candidates, then I read each candidate and judged it. **The nomination is lexical; the classification
below is my reading and is labelled INTERPRETATION.** Nothing was linked, and no question was
answered. Trader isolation held throughout — only `EVSRC|TJR|…` sources were searched.

| Blocker | Classification | Evidence found |
|---|---|---|
| `EQ\|…\|018` break-of-structure | **EXISTING_EVIDENCE_CANDIDATE** | `EV\|…\|001\|020`: *"For price to break structure to the downside, we need price to close underneath the most recent low within the uptrend."* — **a structural definition already in the corpus** |
| `EQ\|…\|013` missing invalidation | **EXISTING_EVIDENCE_CANDIDATE** | `CLAIM\|TJR\|20260727\|022` **is** an `invalidation_rule` (*"the setup remains valid only while price stays in the trend…"*) at `timeframe=5m`; the entry rule `027` is `1m`. The question fires on **scope mismatch, not absence** |
| `EQ\|…\|003` TP ladder | **EXISTING_EVIDENCE_CANDIDATE** | `…\|041`, `\|042`, `\|043`: targets are *"previous draws on liquidity"* — *"five minute highs… Asia session highs… previous day highs"* |
| `EQ\|…\|009` 2B ordering | **EXISTING_EVIDENCE_CANDIDATE** | `…\|027`, `\|028`, `\|034` describe when 2B activates and what it enables |
| `EQ\|…\|012`, `\|014` timeframe | **EXISTING_EVIDENCE_NEEDS_HUMAN_REVIEW** | **9 TJR claims already carry a timeframe**; these two are structural metadata questions ("`claim.timeframe` is null"), not substantive gaps |
| `EQ\|…\|016` consolidation | **NO_EXISTING_EVIDENCE** | only *"There's uptrends, there's downtrends, and then there's consolidation."* — names it, never defines it |
| `EQ\|…\|002` stop placement | **DIRECT_TRADER_CLARIFICATION_REQUIRED** | only *"You can put your stop loss underneath this low."* — the chart-relative statement the question already cites |
| `EQ\|…\|007` news consequence | **DIRECT_TRADER_CLARIFICATION_REQUIRED** | only the single `indirect_implied` check; **no consequence stated anywhere** |
| `EQ\|…\|008` "special little number" | **DIRECT_TRADER_CLARIFICATION_REQUIRED** | 1 unrelated hit (broker price differences) |
| `EQ\|…\|017` two-candle filter | **DIRECT_TRADER_CLARIFICATION_REQUIRED** | the rule exists (*"We take the highest point of those two candlesticks"*); **no significance filter anywhere** |
| `EQ\|…\|004` forex vs indexes | **CONFLICT_REQUIRES_RULING** | **0 forex/currency hits in 86 items**, confirming the question. But this asks whether MOGO's own *intake filename* was mis-filed — an operator question about MOGO's filing, **not a TJR teaching question** |
| `risk_rule` MISSING | **NO_EXISTING_EVIDENCE** | no risk claim exists; the gap's own `recommendedNextSourceType` is *"direct question to trader"* |
| `XCONTRA\|20260728\|001` | **CONFLICT_REQUIRES_RULING** | see §5 |

**Headline: 4 of 17 blockers have candidate evidence already sitting in the governed corpus,
unlinked.** No new acquisition would be needed for those — only human semantic review.

### 3. Exact missing information (9D)

For blockers with no existing evidence, stated as the smallest answerable question:

| Blocker | Missing information |
|---|---|
| `risk_rule` | An explicit statement of how much is risked per trade (fixed %, fixed amount, or by stop distance). |
| `EQ\|…\|002` | An explicit statement of which swing the stop references and whether a buffer is applied. |
| `EQ\|…\|007` | An explicit statement of what happens when high-impact news IS present. |
| `EQ\|…\|008` | The value of the "special little number", and whether it forms part of the entry rule. |
| `EQ\|…\|016` | An explicit definition of consolidation and its identification criteria. |
| `EQ\|…\|017` | An explicit statement of any minimum-size or significance filter for a two-candle high/low. |

### 4. Source-class routing (9E) and passive-vs-direct (9F)

| Blocker | Source class | Why that class can answer it |
|---|---|---|
| `EQ\|018`, `013`, `003`, `009` | **existing governed transcript** | the material is already held; only linkage and scope judgment are missing |
| `EQ\|012`, `014` | **existing governed transcript** | 9 sibling claims already carry timeframes; this is metadata completion |
| `EQ\|002`, `007`, `008`, `016`, `017`, `risk_rule` | **direct trader Q&A** | each asks for a fact the source never states; passive material can only re-demonstrate, not define |
| `EQ\|004` | **operator ruling** | concerns MOGO's own intake filename, not TJR's teaching |
| `XCONTRA\|20260728\|001` | **operator ruling**, or an ALEX scope statement (§5) | requires reconciling two educators |

**Transcript-class acquisition is NOT recommended for any of them.** For the six direct-question
blockers, more video cannot supply a definition the trader never gave — and MOGO-015 Step 1A
established that path returns an empty body and pursuing it means working around an access control.

### 5. Proposed trader clarification questions (design only — nothing sent)

Written to avoid leading, avoid embedding MOGO's hypothesis, ask one fact at a time, and preserve
ambiguity:

1. **risk_rule** — *"When you take a trade, what determines the position size?"*
2. **`EQ|002` stop** — *"When identifying a valid setup, what determines where the stop loss is placed?"*
3. **`EQ|007` news** — *"When you check for high-impact news before a setup, what do you do if there is high-impact news that day?"*
4. **`EQ|008` number** — *"In the long entry example you mentioned price needing one extra point to reach a number you wanted. What was that number based on?"*
5. **`EQ|016` consolidation** — *"How do you identify consolidation on a chart?"*
6. **`EQ|017` filter** — *"When marking highs and lows using two candlesticks, does every such pair count, or does something make one significant?"*

Each is open-ended and single-fact. **None was sent; this is question design only.**

### 6. XCONTRA|20260728|001 — scope analysis, NOT a ruling

**FACT — what each source said:**

| | Claim | Verbatim excerpt | Directness |
|---|---|---|---|
| **ALEX_G** `CLAIM\|…\|025` (`failure_condition`) | *"No consistent strategy can be built on trading liquidity sweeps themselves."* | *"There's no way that you can have a specific strategy to trade **solely** off of these sweeps."* | direct_explicit / certain |
| **TJR** `CLAIM\|…\|006` (`setup_requirement`) | *"The strategy is based on liquidity sweeps."* | *"My strategy is **based off of** liquidity sweeps."* | direct_explicit / certain |

**FACT — also in the TJR corpus:** `CLAIM|TJR|20260727|012` (*"Step 2 requires a five-minute
confirmation confluence after the liquidity sweep"*) and `|014` (*"Only one confirmation confluence
is required"*). **TJR's documented strategy is sweep + a separate confirmation step, not sweep
alone.**

**FACT:** `contradictionType: DIRECTIONAL`, `severity: blocking`, `status: open`,
**`scopeOverlap: "unknown"`**, `resolution: null`.

**INTERPRETATION (mine, and explicitly not a ruling):** Alex's statement is scoped by the word
**"solely"**. TJR's documented method is not sweep-alone. On that reading the two statements could
both be true simultaneously under different scopes — which is why `scopeOverlap` is recorded as
`unknown` rather than `overlapping`. The contradiction record's own rationale reached the same
observation and **deliberately kept it blocking because "the reconciliation is MOGO's reading, not
either educator's statement."** I have not changed that.

**Is it truly logical?** Only if Alex's claim is read as covering sweep-plus-confirmation strategies.
The excerpt does not say that either way — **this is exactly the undetermined point.**

**Exact operator decision required:** whether Alex's "solely" scopes his objection narrowly enough
that TJR's sweep-plus-confirmation method falls outside it — i.e. set `scopeOverlap` and either
resolve as `accepted_as_context_dependent` or confirm it as a genuine conflict.

**Evidence that could remove the need for a ruling:** an explicit ALEX statement on whether his
objection extends to sweep-plus-confirmation setups. That is a **statement about Alex's scope**, so
it would have to come from the ALEX corpus — and would be an ALEX research question, not a TJR one.

### 7. Autonomous resolution potential (9H)

| Classification | Count | Blockers |
|---|---|---|
| `AUTONOMOUSLY_RESEARCHABLE_NOW` | **0** | — |
| `AUTONOMOUSLY_RESEARCHABLE_IF_SOURCE_AUTHORIZED` | **0** | — |
| **`EXISTING_EVIDENCE_NEEDS_HUMAN_REVIEW`** | **6** | `EQ\|003`, `009`, `012`, `013`, `014`, `018` |
| **`DIRECT_TRADER_INPUT_REQUIRED`** | **7** | `EQ\|002`, `007`, `008`, `016`, `017`, `risk_rule`, + `stop_rule` category |
| **`OPERATOR_RULING_REQUIRED`** | **4** | `EQ\|004`, `XCONTRA`, `setup_requirement`, `entry_rule` (secondary) |
| `NO_KNOWN_RESOLUTION_PATH` | **0** | — |

**Zero blockers are autonomously researchable, even with authorization expansion** — because the
missing information is either already held (needs review) or was never stated by the source (needs
asking). **This is a stronger result than Step 4's:** Step 4 found 6 blockers would need
authorization; Step 9's corpus search shows **more acquisition would not answer them either.**

### 8. Resolution order (9I) — ordering predicates, no score

1. **Existing evidence before acquisition** → the 6 `EXISTING_EVIDENCE_NEEDS_HUMAN_REVIEW` first; they cost only review time.
2. **High leverage first within that set** → `EQ|013` (invalidation, **required** entry_rule) and `EQ|018` (break-of-structure, feeds trend definitions) — both have concrete candidate evidence.
3. **Passive before bothering the trader** → exhaust the 6 before asking anything.
4. **Batch the trader questions** → all 6 direct questions in one session; `risk_rule` is the only one blocking a required category with no alternative path.
5. **Factual clarification before operator interpretation** → `EQ|004` (mis-filing) is cheap and independent; do it any time.
6. **Operator rulings last** → `XCONTRA` after §6's scope analysis has been read, since an ALEX scope statement could still remove the need.

### 9. Question-driven research loop (9J — design only)

```
blocker detected (Step 3)
  → SEARCH GOVERNED CORPUS FIRST (Step 9's method, currently manual)
      found candidate? → human semantic review → link evidence → re-evaluate
      not found       → state the smallest answerable question (Step 9 §3)
  → route to source class (Step 4 + Step 9 §4)
      existing transcript | approved source | direct trader Q&A | operator ruling
  → AUTHORIZATION CHECK (never widened by the loop)
      authorized?  → acquire → immutable preservation → candidate extraction
                     → deterministic checks (Step 7) → exception routing (Step 8)
                     → HUMAN annotation gate → evidence/question linkage
      not authorized → stop and report; do NOT collect around the boundary
  → re-evaluate blockers (Step 3) → repeat
STOP when: resolved · human clarification required · operator ruling required ·
           no legitimate path exists
```

**"More research" is never unlimited collection.** Every acquisition must trace to a named blocker
and a stated missing fact; a source that cannot answer the question is not collected.

### 10. Capability vs authorization vs judgment (9K)

| Gap | Type | Detail |
|---|---|---|
| **Corpus search is manual** | **CAPABILITY MISSING** | Step 9 found 4 near-misses by hand. No executable "search governed corpus for evidence relevant to this question" exists. This is the **only** missing executable capability in the whole loop. |
| Evidence↔question linkage | **HUMAN JUDGMENT** | deciding a candidate answers a question is semantic |
| Transcript acquisition | **AUTHORIZATION MISSING** — and **would not help** | §7: acquisition answers none of the 17 |
| Claim creation (Rule 2) | **HUMAN JUDGMENT** | Step 6: 294/295 claims |
| Contradiction ruling | **HUMAN JUDGMENT** | `XCONTRA` |

### 11. Integrity

| Gate | Result |
|---|---|
| Focused MOGO-019 (Steps 2–4, 7, 8) | ✅ **164 / 164** |
| Platform suite | ✅ **25 suites · 1,049 tests · 0 failures** |
| Canonical gate | ✅ **19 suites · 1,160 / 1,160** |
| **Protected ALEX drift** | ✅ **0** |
| Campaign C1 | ✅ 33 / 33 |
| Runtime integrity | ✅ INTEGRITY OK |
| `XCONTRA\|20260728\|001` | ✅ **open / blocking / resolution null — NOT ruled on** |
| Questions answered · proposals | ✅ **0 of 281 · 0** |
| TJR eligibility | ✅ **BLOCKED / 17** |
| Authorization | ✅ 2 sources, metadata only |

### 12. Smallest recommended Step 10

**A read-only "candidate evidence search" helper — the one genuinely missing executable capability.**

For a given unanswered `EvidenceQuestion`, return governed evidence items from **that trader's corpus
only** whose excerpts are lexically relevant, ranked deterministically, **nominating candidates for
human linkage and linking nothing**. Step 9 did this by hand and it found **4 of 17 blockers** with
evidence already in the corpus — the highest-yield result in the milestone so far.

It needs **no new authorization**, creates no records, and would make the §9 loop's first and cheapest
branch executable. It must nominate, never link — the evidence↔question decision stays human.

**Everything else is human:** 6 reviews, 6 trader questions, and 2 operator rulings.

**Nothing was resolved, answered, acquired, linked or ruled on.**

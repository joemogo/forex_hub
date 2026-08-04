# PROPOSAL-003 — Concept Registry

**Status:** Proposal only. **Not implemented.**
**Prior art:** Deferred by ADR-008 and re-affirmed as deferred in `EVIDENCE_INTELLIGENCE.md` §47
(*"concept values stay plain labeled strings on `TraderProfile` (a Concept Registry remains
explicitly deferred, per ADR-008)"*).
**Trigger for revisiting:** the deferral was correct at zero sources. It becomes a scaling blocker
somewhere between the second and fourth source.

---

## 1. Problem

Claims are matched by **normalized text plus scope**. `compute_claim_fingerprint()` lowercases,
collapses whitespace, strips trailing punctuation, and hashes the result with the scope tuple.
Near-duplicate detection uses `difflib` similarity at a 0.85 threshold.

That is sufficient for one source. It fails in three ways as sources accumulate:

**F1 — The same concept, different words, from the same trader.** TJR says *"liquidity sweep"*
throughout this transcript. In another video the same idea may be *"liquidity grab"*, *"stop
hunt"*, or *"taking out the highs"*. Those produce **separate claims with separate fingerprints**.
Instead of one claim reaching `supported` on two independent groups, you get two claims at
`emerging` each — the exact opposite of what the evidence justifies. **This directly undermines the
promotion path in POLICY-001.**

**F2 — The same word, different concepts, across traders.** "Equilibrium" for TJR is the 50%
retracement of a leg. Another trader may use it for a balance area or a value-area midpoint.
Nothing in the current model records that these are different, so cross-trader queries silently
conflate them.

**F3 — No cross-trader comparison is possible.** The stated goal of a multi-trader library is to
learn what is common and what is idiosyncratic. Today, TJR's "break of structure" and JVM's
"structure break" are unrelated strings. There is no way to ask *"which traders require structural
confirmation before entry?"* — the single most valuable question a multi-trader library should be
able to answer.

`difflib` at 0.85 does not solve any of these: *"liquidity sweep"* vs *"stop hunt"* has near-zero
character similarity, while *"close above the high"* vs *"close above the low"* is dangerously
similar. Lexical similarity is the wrong tool for semantic identity.

---

## 2. Proposal

A **Concept** is a named trading idea, defined once, with per-trader terminology attached. Claims
reference concepts; concepts are never inferred automatically.

### 2.1 `Concept` record

`docs/trader-intelligence/concepts/{slug}.json`

| Field | Notes |
|---|---|
| `conceptId` | `CONCEPT\|LIQUIDITY_SWEEP` |
| `canonicalName` | "Liquidity sweep" |
| `definition` | MOGO's own neutral definition, marked as MOGO-authored, not attributed to a trader |
| `conceptType` | `price_action` \| `level` \| `timing` \| `confirmation` \| `risk` \| `instrument_relation` \| `other` |
| `traderTerminology` | `[{traderId, term, evidenceIds, definitionClaimId}]` — how each trader says it |
| `relatedConceptIds`, `distinguishedFromConceptIds` | Explicit near-miss disambiguation (F2) |
| `status` | `proposed` \| `accepted` \| `merged` \| `deprecated` |
| `provenance`, `schemaVersion`, `createdAt` | Standard record conventions |

**Critical constraint: a `Concept.definition` is MOGO's editorial normalization, never evidence.**
It must never be cited as a trader's claim, and must never enter confidence scoring. Concepts are a
navigation and grouping layer over claims — not a new evidence type.

### 2.2 Claim linkage

`Claim` gains an optional additive `conceptIds: string[]`. Set at annotation time from a
`concepts: [...]` field on the ingestion manifest (PROPOSAL-002). Never auto-assigned.

### 2.3 Graph integration

Additive, mirroring how Phase 7A added its four node types:

- Node: `CONCEPT`
- Edges: `CLAIM_REFERENCES_CONCEPT`, `TRADER_USES_CONCEPT`, `CONCEPT_RELATED_TO`,
  `CONCEPT_DISTINGUISHED_FROM`

This makes F3 a graph query: *"which traders have a claim referencing `CONCEPT|BREAK_OF_STRUCTURE`
with `claimType=confirmation_rule`?"*

### 2.4 What this does **not** do

- **It does not merge claims.** Two claims referencing one concept stay two claims with their own
  evidence, scope, and confidence. Merging would destroy the scope distinctions the fingerprint
  exists to preserve.
- **It does not change confidence scoring** in phase A. See §4 for the deliberate open question.
- **It does not auto-detect concepts.** No clustering, no embeddings, no LLM. An operator asserts
  the mapping; the registry records it.

---

## 3. Expected ROI

| Capability | Today | With registry |
|---|---|---|
| Same trader, different words for one idea | Two unrelated claims | Two claims, one concept, visibly related |
| Cross-trader comparison | Impossible | A graph query |
| Terminology collision (F2) | Silent | Explicit via `distinguishedFromConceptIds` |
| Operator onboarding | Read every prior claim to match phrasing | Read the concept list |
| Blueprint readability | Free-text statements | Statements grouped by concept |

The ROI is **near-zero at one source and compounds steeply**. With one trader and one transcript
it is pure overhead. With five traders it is the difference between a library and a pile of
strings.

---

## 4. Open design question — concepts and confidence

If two claims reference the same concept and come from different sources, should they corroborate
each other for confidence purposes?

**Arguments for:** it is the natural fix for F1, and matches the intuition that a trader saying
"liquidity sweep" and "stop hunt" is saying the same thing twice.

**Arguments against:** it makes confidence depend on an **editorial** judgment (the concept
mapping) rather than purely on evidence. Today confidence is a deterministic function of stored
links; introducing concept-mediated corroboration means a mapping decision could silently promote a
claim. That is a meaningful weakening of the property POLICY-001 relies on.

**My recommendation: no, not in phase A.** Keep concepts as a navigation layer. If corroboration
is later wanted, do it explicitly through `EvidenceClaimLink.independenceGroup` — which is already
an operator-set field with a visible audit trail — rather than implicitly through concept identity.
That keeps every confidence change traceable to a link, not to a taxonomy edit.

---

## 5. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Taxonomy bikeshedding | Medium | Seed only from concepts that already appear in real claims; forbid speculative concepts |
| Concept definitions drifting into evidence | **High** | Schema-level: `definition` is MOGO-authored, never citable, never scored. Enforce with an integrity check. |
| Premature abstraction | Medium | Do not build before source #3 (see §6) |
| Operator burden per ingestion | Low | Optional field; unmapped claims behave exactly as today |
| Confidence coupling | High | Explicitly excluded in phase A (§4) |

---

## 6. OWNER DECISION REQUIRED — timing

### The problem

The registry is genuinely valuable and genuinely premature. Building it now optimizes for a scale
that does not exist; building it after twenty transcripts means retrofitting concepts across
hundreds of claims, when the cheapest moment to assign a concept is at annotation time.

### Options

**Option 1 — Build now, before the second transcript.**
*Risk:* designing a taxonomy from one trader's vocabulary; likely wrong shape.
*ROI:* low now, avoids all retrofit.

**Option 2 — Defer until source #3, then build and backfill.** ✅ **Recommended**
*Risk:* backfilling ~100–150 claims across three sources. Real but bounded, and mechanical.
*ROI:* the taxonomy gets designed against genuine vocabulary variation — including at least one
cross-trader collision — rather than guessed from one video.

**Option 3 — Defer indefinitely.**
*Risk:* F1 actively suppresses confidence (two `emerging` claims where one `supported` claim is
warranted), which directly conflicts with the promotion path. Retrofit cost grows without bound.
*ROI:* negative beyond ~3 sources.

**Option 4 — Add `conceptIds` to the schema now; populate later.**
*Risk:* near zero.
*ROI:* small but real — it means sources #2 and #3 can be tagged as they are ingested, so there is
nothing to backfill for them.

### Recommendation

**Option 2, with Option 4 folded in.** Add the optional `conceptIds` field and a `concepts` block
to the PROPOSAL-002 manifest schema now, so ingestions #2 and #3 can record concept intent as they
happen. Build the registry itself, and backfill source #1, when the third source lands.

**Concrete trigger to revisit:** the first time an ingestion produces a claim that means the same
thing as an existing claim but does not near-duplicate-match it. That is F1 becoming real, and it
should be recorded in the ingestion's report when it happens.

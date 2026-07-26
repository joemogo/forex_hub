# ADR-008: Evidence Intelligence Engine Foundation (PROGRAM-006 Phase 1A)

**Status:** Accepted, Phase 1A implemented. Storage/validation/provenance/query infrastructure
only — zero runtime, execution, or network capability.

## 1. Problem statement

MOGO's existing Trader Intelligence Framework (Wave 1, ADR-none-numbered-yet-at-the-time) and
Research Acquisition Engine (PROGRAM-004) can track a research *source* and, once real material
arrives, a `StrategyAssertion` extracted from it. That model conflates two different things: the
*document* a claim came from, and the *discrete observation* that actually supports or challenges
a proposition. A single transcript can contain one explicit rule statement, three chart examples,
two exceptions, and one contradiction of an earlier claim — treating the whole transcript as one
unit of evidence loses that structure. As MOGO's evidence producers grow beyond research
transcripts (replay observations, paper trades, winning/losing trades, execution reviews, owner
observations), a document-shaped model doesn't fit non-document sources at all: a paper trade is
not a "document," but it produces evidence exactly the same way a transcript excerpt does.

## 2. Approved evidence-centric decision

The knowledge flow is:

```
Source → Evidence → Claim → Confidence → Rule Candidate → Validated Rule → Production Strategy Rule
```

**Evidence, not the document, is the primary intelligence unit.** A `Source` is a container; an
`EvidenceItem` is one discrete, provenance-traceable observation drawn from it; a `Claim` is a
normalized proposition that zero or more evidence items support, contradict, weaken, or
contextualize; confidence is a derived, recomputable estimate of how well-supported a claim
currently is; a rule candidate is a claim (or claims) an owner has decided is worth modeling as a
`StrategyRule`; a validated rule has passed replay/shadow/paper gates; a production rule is one an
owner has explicitly promoted into `index.html`'s protected trading logic. Every arrow above is a
distinct, owner-gated step — none is automatic.

## 3. Why documents are containers, not primary knowledge units

A document conflates provenance (where did this come from) with content (what does it actually
claim). Two claims from the same transcript can have completely different evidentiary strength —
one an explicit, repeated rule statement; another an offhand, unqualified opinion. Scoring or
querying at the document level erases that distinction. Evidence-level granularity is what makes
confidence, contradiction, and duplicate detection meaningful at all.

## 4. Hybrid storage implications

Per the already-approved hybrid canonical storage policy: this repository holds transcripts (when
permitted), structured notes, extracted claims, evidence records, confidence assessments,
contradiction records, and provenance metadata — including hashes and references to externally
stored assets. It never holds original videos, audio, or large binary/PDF files. Every
`EvidenceSource` record distinguishes `storage_location_type` (`repository` vs `external`) and,
for external assets, requires a `canonical_reference` and `content_hash` even though the asset
itself lives outside version control.

## 5. Evidence immutability expectations

An `EvidenceItem`'s content (`exact_excerpt`, `normalized_observation`, `content_hash`) is never
edited in place once created. A correction creates a new `EvidenceItem` with
`supersedes_evidence_id` pointing at the one it replaces; the original is never deleted or
mutated. This mirrors the existing Trader Intelligence Framework's `StrategyAssertion`
immutability principle (Wave 1, principle #2), generalized to the new evidence layer.

## 6. Claim evolution expectations

A `Claim`'s normalized text is stable once created; if research reveals a materially different
formulation, a new `Claim` is created and linked (via a future supersession mechanism, not
implemented in Phase 1A beyond the data model supporting it) rather than editing the original.
What *does* change on an existing claim record is its derived confidence state/score/counts —
those are recomputed, not asserted, and every recomputation is itself an audit event.

## 7. Confidence is derived, not asserted as permanent truth

`Claim.confidence_score`/`confidence_state` are never manually set. They are computed from the
`EvidenceClaimLink` records attached to the claim, using the deterministic, explainable formula in
`scripts/trader_intelligence/evidence_confidence.py`. Confidence is a snapshot of current
evidentiary support, not a prediction and not a profitability claim — recomputing it after new
evidence arrives can move it in either direction, including down.

## 8. Contradictions are first-class records

A `ContradictionRecord` is never resolved by deleting or silently overwriting either side. Status
transitions (`open` → `resolved_by_owner`/`superseded`/`accepted_as_context_dependent`), but both
claims and the full rationale remain permanently queryable — the same non-negotiable principle
already established for `RuleContradiction` in Wave 1, applied here at the claim level.

## 9. Candidate rules are not production rules

A rule candidate is exactly the existing `StrategyRule` entity (see §13) at `modelingStatus:
not_modeled` or `modeled`. Nothing in this phase, or any future phase short of a separately
authorized engineering milestone, allows a claim's confidence — however high — to alter
`implementationStatus`, `validationStatus`, or any runtime trading behavior.

## 10. Owner approval remains required before production promotion

Every promotion boundary already established in PROGRAM-003 (the 12-state promotion lifecycle,
`OwnerDecision`-gated transitions) applies unchanged. The Evidence Intelligence Engine adds new
*inputs* to that pipeline; it does not relax any existing gate.

## 11. No runtime or execution coupling in Phase 1A

Identical guarantee to PROGRAM-003/004: `index.html` is never referenced by any evidence script or
artifact, verified by a permanent test. No protected function, protected constant, trading
decision, or paper/live execution path is touched.

## 12. No network capability in Phase 1A

No evidence script imports any network-capable module. Ingestion pipelines for transcripts,
replay, paper trades, or live trades are explicitly out of scope for this phase — this is storage,
validation, provenance, and query infrastructure only.

## 13. Distinguishing source / evidence / claim / interpretation / hypothesis / rule candidate / validated rule / production rule

| Term | Meaning | Entity |
|---|---|---|
| Source | The evidence-producing artifact or event (a video, a replay session, a paper trade) | `EvidenceSource` |
| Evidence | One discrete, provenance-traceable observation drawn from a source | `EvidenceItem` |
| Claim | A normalized proposition evidence can support/contradict/weaken/contextualize | `Claim` |
| Interpretation | `EvidenceItem.normalized_observation` — MOGO's reading of the raw excerpt, kept distinct from the exact excerpt itself | field on `EvidenceItem` |
| Hypothesis | An unconfirmed `Claim` at a low/tentative confidence state | `Claim` at `confidence_state ∈ {insufficient_evidence, tentative}` |
| Rule candidate | A `StrategyRule` an owner is considering modeling, referencing its originating claims | existing `StrategyRule` (additively extended, see §14) |
| Validated rule | A `StrategyRule` whose `validationStatus` has reached `replay_validated`/`shadow_validated`/`paper_approved` | existing `StrategyRule` |
| Production rule | Code inside `index.html`'s protected functions | out of scope, requires its own future milestone |

## 14. Migration and compatibility strategy

No migration is required or performed: zero real `StrategyAssertion`/`StrategyRule` instances
exist in production today (confirmed directly, PROGRAM-004 Phase 1E), so there is no existing data
to reconcile. `StrategyRule` gains exactly one new, optional, additive field —
`originatingClaimIds: string[]` (pattern `^CLAIM\|`) — so a future rule candidate can point back at
the claims that motivated it, without duplicating any of `StrategyRule`'s existing fields (evidence
linkage, confidence, trader/family/timeframe/session/market scope, and validation status already
exist there and are reused as-is). `RuleEvidence`/`RuleContradiction` (Wave 1) remain unchanged and
continue to serve rule-level evidence aggregation; `EvidenceClaimLink`/`ContradictionRecord`
(Phase 1A) operate one level down, at the claim level, and are complementary, not a replacement.

## 15. Rejected alternatives

- **Document-centric intelligence** — rejected per §3; loses evidentiary granularity and doesn't
  generalize to non-document evidence producers (replay, paper trades).
- **Direct transcript-to-rule promotion** — rejected; skips claim normalization, confidence
  assessment, and contradiction detection entirely, reintroducing the exact "invented rule" risk
  this whole framework exists to prevent.
- **Mutable evidence records** — rejected per §5; breaks auditability and silently destroys
  provenance.
- **Storing confidence only on source documents** — rejected; a document can support one strong
  claim and one weak one simultaneously, so confidence must live on the claim, not the source.
- **Silently overwriting contradictory claims** — rejected per §8; destroys the disagreement that
  is itself valuable signal (e.g. temporal strategy drift, cross-trader disagreement).

## 16. Consequences and future extensions

Positive: a real, general foundation exists for every future evidence producer named in the
program context, without having built any of their ingestion pipelines yet — confirmed by the
fact that Phase 1A's entire test suite and integrity validation pass against a genuinely empty
evidence corpus. Cost: a new schema/script surface to maintain alongside the existing Wave
1/PROGRAM-003/004 layers; mitigated by additive-only integration (§14) and full reuse of existing
canonical-JSON/hashing/atomic-write/ID conventions.

Future extensions (not implemented, explicitly out of scope for Phase 1A): transcript ingestion
connectors, replay-result evidence ingestion, paper/live-trade evidence ingestion, an
LLM-assisted (never LLM-autonomous) extraction aid, a Research Center UI, and the eventual
engineering milestone that would let a `validated rule` become a `production rule`.

## 17. Scope exclusions (Phase 1A)

No transcript ingestion, no automatic parsing, no YouTube/network access, no LLM calls, no vector
databases or embeddings, no automated rule promotion, no production strategy mutation, no replay
engine, no paper/live-trade evidence ingestion, no broker integration, no UI. This phase is
storage, validation, provenance, and query infrastructure only — it may (and, at the time of this
ADR, does) operate on a zero-evidence corpus.

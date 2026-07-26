# ADR-009: Evidence Explainability and Controlled TJR Intake Pipeline (PROGRAM-006 Phase 1B)

**Status:** Accepted, Phase 1B implemented. Explainability, traceability, controlled intake, and
review-queue infrastructure only — zero runtime, execution, or network capability. Builds
additively on ADR-008; nothing in ADR-008 is reopened.

## 1. Problem statement

ADR-008 gave MOGO a way to store evidence, link it to claims, and compute a confidence score.
It did not give MOGO a way to *explain* that score, or a controlled way to get real transcript
content into the system in the first place. A number alone ("confidence 0.74") answers nothing an
owner would actually ask — which sources, which exact words, was any of it inferred rather than
stated, what's still missing. Phase 1B closes both gaps: a deterministic explainability layer over
existing evidence, and a controlled, human-reviewed intake pipeline that can accept a real,
locally-supplied TJR transcript the moment the owner provides one, without inventing any new
architecture at that point.

## 2. Why confidence scores alone are insufficient

A confidence score is a single float. It cannot show *which* evidence produced it, whether that
evidence was an explicit rule statement or an offhand inference, whether independent sources agree
or whether it's really one source counted several ways, or what a reviewer would still need to
check before trusting it. Two claims can carry the identical score for entirely different reasons
— one from three strong independent statements, another from a single borderline item that
happened to land at the same number. An owner (or a future automated gate) making a promotion
decision needs the reasoning, not just the number.

## 3. Why every material conclusion must expose its evidence

MOGO's constitutional position — established in ADR-004 (read-only analytics) and reaffirmed in
ADR-008 §5–8 — is that nothing gets to assert trading knowledge without a traceable origin. An
explanation that can't point at the specific `EvidenceItem` records behind it is exactly as
unaccountable as a confidence score with no explanation at all; it just has more words. Every
sentence Phase 1B's explainability service produces is generated from a specific stored record and
carries that record's ID; nothing is composed from free text.

## 4. The seven-way evidence split every explanation must preserve

An explanation collapses into noise if it doesn't keep these separate:

1. **Direct evidence** — items whose `relationshipType` is `supports`/`exemplifies` and whose
   directness is `direct_explicit` or `direct_demonstrated`.
2. **Indirect evidence** — supporting items whose directness is `indirect_implied`,
   `inferred_from_context`, or `derived_from_analysis`.
3. **Inference** — the subset of (2) explicitly flagged `inferred_from_context` or
   `derived_from_analysis`; always labeled as inference in the rendered text, never presented as a
   stated rule.
4. **Assumptions** — scope fields the claim carries but no evidence item actually addresses
   (surfaced as "known scope limitations" / "missing evidence categories," §7 of the explainability
   service).
5. **Contradictory evidence** — items with `relationshipType="contradicts"`, plus any
   `ContradictionRecord` naming this claim.
6. **Contextual evidence** — items with `relationshipType` in
   `{contextualizes, qualifies, supersedes, unresolved}`.
7. **Unresolved questions** — `EvidenceQuestion` records referencing this claim (see §12 on naming).

Confusing any two of these — presenting an inference as a direct statement, or a contextual
qualifier as a contradiction — is exactly the failure mode this ADR exists to prevent.

## 5. Why explanations must be deterministic and require no LLM

Two runs against identical stored data must produce byte-identical explanation objects. This is
the same non-negotiable property `evidence_confidence.py` already has (ADR-008 §7), extended to
explanation text: `evidence_explain.py` builds every rendered sentence from a fixed set of
templates parameterized only by stored field values — sorted, deduplicated, never randomized, never
calling out to a language model. This also means an explanation is trivially reproducible and
diffable across confidence recomputations, which an LLM-authored narrative could never guarantee.

## 6. Why explanations must preserve source provenance

Every evidence line in a rendered explanation carries its source's identity and, where available,
its exact location (timestamp, line range, section) — never a bare claim of "evidence exists."
This is the traceability requirement of Deliverable 3: an owner reading an explanation should never
need to open raw JSON to find out which transcript, at which timestamp, produced a given sentence.

## 7. Why unsupported narrative generation is prohibited

`evidence_explain.py` never synthesizes a sentence that isn't a direct rendering of stored fields.
If zero evidence exists for a scope dimension, the explanation says exactly that ("no evidence for
Asia session") rather than omitting it silently or inferring an answer. This is enforced
structurally, not just by convention: `render_explanation_text()` takes the structured explanation
object as its only input and contains no free-form text generation path — every line is a template
filled from a field that itself traces to a stored record ID (verified by
`test_no_unsupported_narrative` in Deliverable 23, category K).

## 8. Why rule recommendations remain proposals

A `RuleCandidateProposal` (Deliverable 12) is explicitly **not** the `StrategyRule` extended in
ADR-008 §14 — it is a separate, lightweight, non-executable record documenting the *rationale* for
proposing that an existing or future `StrategyRule` link back to a set of claims (directness
distribution, extraction-certainty distribution, confidence state, contradiction/replay/paper
status, proposal rationale). It never sets `StrategyRule.modelingStatus`, `implementationStatus`,
`validationStatus`, or `promotionState`. A human decides, separately and explicitly, whether and
how to act on a proposal — exactly the same non-negotiable boundary ADR-008 §9–10 already
established for claims themselves, now extended one step further down the pipeline.

## 9. Why transcript ingestion must preserve source location

A `TranscriptSegment` (Deliverable 8) always carries its sequence number and, when available,
timestamps or line numbers, and its raw text is never replaced by its normalized text — both are
stored. Every `EvidenceItem` created from a segment (directly, or via a `ManualAnnotation`) keeps an
`EVIDENCE_FROM_SEGMENT` graph edge and a `sourceLocator`-equivalent reference back to the exact
segment, so "where in the source did this come from" is always answerable without re-reading the
whole transcript.

## 10. Why uncertain extractions require explicit review status

Extraction certainty (Deliverable 5) is a first-class, separately-tracked field precisely so a
low-certainty extraction can never look identical to a high-certainty one in downstream queries or
reports. Any evidence or claim created with `extractionCertainty` in `{low, ambiguous, unresolved}`
is automatically placed into the low-certainty review queue (Deliverable 14) and its explanation
surfaces that fact prominently — it is never silently treated as equivalent to a certain extraction.

## 11. Why incomplete or ambiguous statements must not become definitive rules

The extraction pipeline (Deliverable 9) and the annotation format (Deliverable 10) never
auto-approve a claim. Every claim created through this pipeline is created with
`claimStatus`/review-related metadata indicating review is required, and an `EvidenceQuestion` is
generated automatically wherever a structurally missing element is detected (no timeframe, no
invalidation, no explicit stop) rather than the pipeline guessing a default. A `RuleCandidateProposal`
built from such a claim carries its unresolved questions forward instead of hiding them.

## 12. Naming: EvidenceQuestion, not UnresolvedQuestion

The Phase 1B spec's suggested node type "UnresolvedQuestion" collides with an existing, unrelated
Wave-1 entity: `UNRESOLVED_QUESTION` (schema `unresolved-question` under
`traders/*/open-questions/*.json`, a free-form, trader-level open question with its own field
shape, already a Knowledge Graph node type). Reusing that name or schema for the narrower,
claim/evidence-scoped question this phase generates (missing timeframe, contradiction, insufficient
independent support, etc.) would either collide outright or force two incompatible schemas onto one
name. Phase 1B's new entity is instead named **`EvidenceQuestion`** (ID prefix `EQ|`, node type
`EVIDENCE_QUESTION`) — a deliberate, ordinary naming decision (explicitly not a stop-condition
matter), documented here so it isn't mistaken for the pre-existing Wave-1 concept.

## 13. Why the system must support an empty corpus

Every service in this phase (explainability, review queues, TJR report generation, all 22 new
queries) is required to behave correctly with zero real evidence, zero real transcripts, and zero
real claims — because that is the system's actual current state, and will remain so until an owner
supplies a real TJR source. "Works only once data exists" is not an acceptable design for
infrastructure whose entire purpose is to be ready before that data arrives.

## 14. Distinguishing extraction / normalization / interpretation / explanation / recommendation / promotion

| Stage | What happens | Who/what decides | Entity |
|---|---|---|---|
| Extraction | Raw transcript text is segmented and candidate evidence is *suggested* (phrase/marker detection only) | Deterministic pattern matcher, never authoritative alone | `TranscriptSegment`, non-persisted suggestion list |
| Annotation | A human confirms, corrects, or rejects a suggestion and supplies the fields a pattern matcher cannot reliably infer (directness, certainty, proposed claim) | Human researcher (or the owner) | `ManualAnnotation` |
| Normalization | Annotation-approved text becomes an immutable `EvidenceItem` and a normalized, deduplicated `Claim` | Deterministic registry code (`evidence_registry.py`, `evidence_dedup.py`) | `EvidenceItem`, `Claim` |
| Interpretation | `EvidenceItem.normalizedObservation` / `Claim.normalizedClaim` — MOGO's reading, kept distinct from the exact excerpt | Deterministic, but explicitly separate from the raw record | field on existing entities |
| Explanation | A structured, traceable account of why a claim currently sits at its confidence state | Deterministic template engine (`evidence_explain.py`), no LLM | computed output, not persisted as new canonical truth |
| Recommendation | A `RuleCandidateProposal` suggesting a claim set is ready for rule consideration | Deterministic eligibility check + explicit proposal record | `RuleCandidateProposal` |
| Promotion | A `StrategyRule`'s `modelingStatus`/`implementationStatus`/`promotionState` actually changes | A human owner, via a separate, already-existing `OwnerDecision`-gated process (ADR-008 §9–10) — never this phase | existing `StrategyRule` |

## 15. Rejected alternatives

- **Confidence-only output** — rejected per §2; a number with no reasoning is unaccountable and
  unreviewable.
- **Opaque scoring** (a black-box explanation service that can't cite its inputs) — rejected per
  §3; violates the traceability principle every other MOGO intelligence layer already follows.
- **Transcript summary as knowledge** — rejected; a summary is a lossy paraphrase, not evidence, and
  would let unreviewed narrative substitute for the actual evidence chain.
- **Direct transcript-to-production-rule conversion** — rejected; this is the exact failure mode
  ADR-008 §15 already rejected, restated here because a naive intake pipeline is the most tempting
  place to reintroduce it.
- **Silent contradiction resolution** — rejected; contradictions remain first-class, queryable
  records (ADR-008 §8) even when a rule candidate is proposed from the winning side.
- **Destructive claim merges** — rejected; deduplication only ever *recommends*, exactly as
  established in ADR-008 §7 / Deliverable 6; Phase 1B's claim-candidate generation follows the same
  rule.
- **Reusing the Wave-1 `UnresolvedQuestion` entity for evidence-layer questions** — rejected per
  §12; would collide two incompatible schemas onto one node type.
- **Treating `RuleCandidateProposal` as a new parallel rule entity that replaces `StrategyRule`** —
  rejected per §8; would reopen ADR-008 §14's already-settled decision that `StrategyRule` itself is
  the rule candidate.

## 16. Scope exclusions (Phase 1B)

No network transcript fetching, no YouTube/video downloading, no web scraping, no browser
automation, no external LLM calls, no embeddings or vector databases, no automatic natural-language
understanding claimed as complete, no autonomous rule approval, no production strategy or
paper/live-trading behavior change, no replay execution, no broker integration, no UI. The
extraction pipeline is explicitly a *controlled framework* (configured phrases/markers/annotations),
not a claim of general natural-language understanding — see Deliverable 9.

## 17. Future extensions (not implemented, explicitly out of scope for Phase 1B)

A future phase, requiring its own owner authorization, could add: an LLM-assisted (never
LLM-autonomous) extraction aid behind the same controlled-adapter boundary established here; replay
and paper/live-trade evidence ingestion pipelines (the data model already supports these evidence
types generically, per ADR-008 §4/Program context); a Research Center UI; and the eventual
milestone that defines the policy under which a `RuleCandidateProposal` with strong support may be
acted on to change a real `StrategyRule`'s promotion state.

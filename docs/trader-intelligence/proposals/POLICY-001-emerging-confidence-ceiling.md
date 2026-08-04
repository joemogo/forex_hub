# POLICY-001 — Emerging Confidence Ceiling

**Status:** ✅ **RATIFIED** 2026-07-27 as [`DECISION|MOGO|20260727|003`](../graph/decisions/decision-mogo-20260727-003.json)
(`decisionType: research`, `approvalScope: research_only`, all authorization flags `false`).
Now enforceable by `PROMOTION_WITHOUT_OWNER_AUTHORIZATION` and visible in the Knowledge Graph.

**Scope broadened at ratification.** The original directive named TJR; the ratified decision applies
the rule to **every claim from every source**, alongside
[`DECISION|MOGO|20260727|004`](../graph/decisions/decision-mogo-20260727-004.json), which
establishes equal evidence-source standing for ICT, TJR, JVM, ALEX G, and future educators.

**The five ratified rules:**
1. No strategy rule is promoted to validated knowledge on a single source.
2. All extracted information is stored as evidence with full provenance.
3. Contradictions are recorded, never resolved prematurely.
4. Confidence increases only through independent corroboration, replay validation, paper trading, or
   historical testing.
5. Autonomous transcript processing is authorized under these constraints.

**Applies to:** all 47 claims under `EVSRC|TJR|20260727|001`, and every future claim from any source.

> **`replayAuthorization` remains `false`.** Rule 4 establishes that replay evidence *counts* toward
> confidence — not that replay execution is authorized. That needs its own decision, and is
> separately gated on extraction-pipeline review and on ES/NQ market data MOGO does not hold.

---

## 1. The constraint

No claim originating from the first TJR intake may advance beyond `confidenceState: emerging`, and
no such claim may become a `RuleCandidateProposal`, a `StrategyRule`, or reach any `PromotionState`
beyond `DISCOVERED`, until **at least one** of the following exists:

- **(A)** A second, independently-registered `EvidenceSource` of TJR material that corroborates the
  claim; **or**
- **(B)** Validated replay evidence (a `replay_result` EvidenceItem produced by a real replay run)
  that corroborates the claim.

## 2. What already enforces this mechanically

Most of the constraint is structural rather than procedural, which is the reason it is worth
ratifying rather than merely remembering:

| Guard | Where | Effect |
|---|---|---|
| Confidence is **computed, never authored** | `evidence_registry.recompute_claim_confidence()` | `confidenceState` is derived from links on every write; there is no "set confidence" API |
| Independence grouping | `evidence_confidence._independence_groups()` | Groups key on `sourceId`; same-source items beyond the first are discounted to 25% weight |
| 22-points-per-group scoring | `evidence_confidence` | One source caps at ~22 pts; `supported` requires 45 — unreachable on one source (see §4) |
| Rule-candidate eligibility | `extraction_pipeline._RULE_ELIGIBLE_CONFIDENCE_STATES` | Auto-proposal fires only at `supported`/`strongly_supported` |
| Open contradictions block candidacy | `rule_candidate_proposals.propose_rule_candidate()` | Sets `contradictionStatus: open_contradiction`; TJR has 2 open |
| Promotion requires authorization | `promotion-state.schema.json` + `PROMOTION_WITHOUT_OWNER_AUTHORIZATION` | Every stage past `DISCOVERED` needs a traceable `OwnerDecision` |
| Blueprints cannot execute | `strategy-blueprint.schema.json` | `productionStatus` is a JSON Schema `const: "not_applicable"` |

**Current state satisfies the constraint with no action required:** all 47 claims are `emerging`,
zero `RuleCandidateProposal`s exist, zero `StrategyRule`s were written.

## 3. Where nothing enforces it — three honest gaps

**G1 — A second TJR video counts as fully independent.** `independenceGroup` defaults to
`sourceId`. Registering a second TJR transcript creates a second group, taking a corroborated claim
to 44 points; one further corroborating excerpt reaches 45 → `supported`. **This is consistent with
the directive as written** (option A explicitly admits additional TJR material), but the epistemics
deserve stating plainly: two videos by the same trader corroborate *that he states the rule
consistently*, not *that the rule works*. Only option (B), replay evidence, tests the latter.

*Lever if you later want same-author sources discounted:* `EvidenceClaimLink.independenceGroup` is
already an explicit, writable field that overrides the `sourceId` default. Setting it to a
per-author key (e.g. `AUTHOR|TJR`) would make all TJR material one group and cap the whole library
at `emerging` until non-TJR or replay evidence arrives. **No code change required — this is a
registration-time policy choice.** Recommend deciding this before the second intake, not after.

**G2 — Hand-editing a claim file is undetected at rest.** Confidence is recomputed on link
creation, not continuously. A directly-edited `confidenceState` would persist until the next
recompute. *Recommend verifying whether `validate_evidence.py` re-derives confidence during
integrity checks; if it does not, that is the single highest-value guard to add (see §5).*

**G3 — A human can author a `StrategyRule` by hand.** This is deliberate (ADR-008 §9–10 keeps rule
authoring outside all automation), but it means the final step of the constraint rests on
discipline rather than structure. The `PROMOTION_WITHOUT_OWNER_AUTHORIZATION` check catches an
unauthorized *promotion state*, not an unauthorized *rule file*.

## 4. Why the ceiling is arithmetic, not judgment

| Independent groups | Score | State |
|---|---|---|
| 1 (today) | 22 | **`emerging`** |
| 2 | 44 → 45.5 with one extra corroborating item | `supported` |
| 3 + several corroborating items | 75 | `strongly_supported` |

Observed distribution: 39 claims at exactly 22.00, 8 at 22.89–24.39. Reaching 45 on a single source
would require roughly sixteen further excerpts on one claim. The evidence quality is not the
limiting factor — 49 of 62 items are `direct_explicit` and 39 carry `high` extraction certainty.

## 5. Proposed enforcement (NOT implemented — requires approval)

**E1 — Integrity check `CLAIM_CONFIDENCE_NOT_RECOMPUTABLE`** in `validate_evidence.py`: recompute
each claim's confidence from its stored links and flag any mismatch with the persisted
`confidenceState`/`confidenceScore` as `ERROR`. Closes G2 permanently and is cheap.

**E2 — Integrity check `PROMOTION_BEYOND_POLICY_CEILING`**: flag any `RuleCandidateProposal` or
`StrategyRule` whose `originatingClaimIds` resolve only to single-source claims, while POLICY-001 is
active. Closes G3 structurally.

**E3 — Registration-time policy for `independenceGroup`** (see G1). A decision, not code.

## 6. The ratified `OwnerDecision` record

✅ **Written 2026-07-27** as `graph/decisions/decision-mogo-20260727-003.json`, and present in the
Knowledge Graph as an `OWNER_DECISION` node (build `BUILD|20260727|003`, 249 nodes, zero findings).
The record as filed broadens the original TJR-specific directive to all sources and folds in the
autonomous-processing authorization. The draft below is retained for comparison.

```json
{
  "decisionId": "DECISION|MOGO|20260727|003",
  "owner": "Joe Mogollon",
  "decisionDate": "2026-07-27",
  "affectedEntityIds": ["TJR", "EVSRC|TJR|20260727|001", "BLUEPRINT|TJR|20260727|001"],
  "decisionType": "research",
  "question": "May claims extracted from the first TJR transcript advance beyond 'emerging' confidence, and under what evidentiary conditions?",
  "optionsConsidered": [
    "Allow normal confidence progression as further evidence of any kind accumulates",
    "Hold all first-intake claims at 'emerging' until either a second independent TJR source or validated replay evidence corroborates them",
    "Hold all first-intake claims at 'emerging' until validated replay evidence alone corroborates them"
  ],
  "selectedOption": "Hold all first-intake claims at 'emerging' until either a second independent TJR source or validated replay evidence corroborates them",
  "rationale": "The first intake is a single source. The confidence engine already caps single-source claims at ~22 points against a 45-point 'supported' threshold, so this decision ratifies an existing structural property rather than adding a new restriction. It is recorded explicitly so that any future promotion attempt is checkable against a traceable authorization, and so the distinction between source corroboration and replay validation stays deliberate.",
  "supportingEvidenceIds": [],
  "dissentingEvidenceIds": [],
  "approvalScope": "research_only",
  "implementationAuthorization": false,
  "replayAuthorization": false,
  "shadowAuthorization": false,
  "paperAuthorization": false,
  "productionAuthorization": false,
  "liveAuthorization": false,
  "reviewDate": null,
  "expiresAt": null,
  "supersedesDecisionId": null,
  "status": "active",
  "createdAt": "2026-07-27T00:00:00Z",
  "updatedAt": "2026-07-27T00:00:00Z"
}
```

Note `replayAuthorization: false` — consistent with Priority 3, which defers replay testing until
the extraction pipeline is reviewed. Lifting the ceiling via route (B) therefore requires a
*second* decision authorizing replay.

## 7. Review triggers

This policy should be revisited when any of the following occurs: a second TJR `EvidenceSource` is
registered; replay is authorized; licensing on `EVSRC|TJR|20260727|001` is resolved; or either open
contradiction (`XCONTRA|20260727|001`, `|002`) is resolved.

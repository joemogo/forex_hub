# Provenance Specification

**Status:** Normative. Describes the chain that must hold for every extracted item, the invariants
at each hop, and how to audit them.

> **The property this guarantees.** For any statement anywhere in the Trader Intelligence system —
> a claim, a blueprint stage, a knowledge gap, a hypothesis, a graph node — it must be possible to
> mechanically walk back to the exact bytes of the source file that produced it, and to verify
> those bytes are unchanged. Nothing may exist that cannot be walked back.

---

## 1. The chain

```
StrategyRule            (none exist; the chain ends at proposals until a human authors one)
   ↑ originatingClaimIds
RuleCandidateProposal   ← blocked while any touching contradiction is open
   ↑ originatingClaimIds
Claim                   normalizedClaim + normalizedFingerprint + scope
   ↑ claimId
EvidenceClaimLink       relationshipType, relevanceWeight, independenceGroup
   ↑ evidenceId
EvidenceItem            exactExcerpt (verbatim) + contentHash + sourceLocator
   ↑ sourceLocator = "TSEG|…"                    ↑ sourceId
TranscriptSegment       rawText + textHash        EvidenceSource   contentHash
   ↑ intakeId                                        ↑ sourceId
IntakeManifest          contentHash + sourceMetadata (bytes, sha256, import timestamp)
   ↓ sourceMetadata.rawCopyPath / normalizationMapPath
normalization-map.json  per-line: sourceLine, sourceLineSha256, removed text, transform
   ↓
raw/{file}.raw.txt + .sha256   ← byte-identical copy
   ↓
{file}  the original, never modified after Stage 1
```

Derived artifacts hang off `Claim` and inherit its lineage: `StrategyBlueprint.sourceLineage`
(sourceIds / segmentIds / evidenceIds / claimIds), `TraderProfile.sourceLineage`,
`KnowledgeGap.provenance`, `Hypothesis.sourceClaimIds`.

---

## 2. Invariants

Each is stated as a property that must hold, with what enforces it today.

| # | Invariant | Enforced by |
|---|---|---|
| **P1** | The original file is never modified after Stage 1 | Convention + raw-copy hash comparison |
| **P2** | The raw copy is byte-identical to the original | Asserted at copy time; `.sha256` sidecar |
| **P3** | Normalization removes only a named artifact class and changes no word | Reversibility assertion (below) |
| **P4** | Normalization is reversible: `timestamp + removedLabel + normalizedText == source line` | Asserted per line at generation; run aborts on failure |
| **P5** | Every source line belongs to exactly one section | Coverage assertion at sectioning time |
| **P6** | `exactExcerpt` is a literal substring of its segment's `rawText` | **`register_annotation()` raises** — machine-enforced |
| **P7** | Every EvidenceItem names the segment it came from | `sourceLocator` set from `segment["segmentId"]` by `apply_annotation()` |
| **P8** | Every EvidenceItem names its source | `sourceId` required; `register_evidence_item()` rejects unknown ids |
| **P9** | Evidence cannot exist before its source | `apply_annotation()` requires the intake to have a linked `sourceId` |
| **P10** | Every Claim reaches evidence through a Link | `link_evidence_to_claim()` validates both ends exist |
| **P11** | Records are immutable; corrections supersede rather than edit | `supersedesEvidenceId` / `supersedesProposalId`; no update API |
| **P12** | Every state change is recorded | `lifecycle/` events — 243 for the first intake |
| **P13** | Confidence is derived, never authored | `recompute_claim_confidence()` on every link write |
| **P14** | Claim identity includes scope | `compute_claim_fingerprint()` hashes text **and** scope tuple |
| **P15** | Content integrity is checkable at every level | `contentHash` on source/intake/evidence; `textHash` on segments |

### Gaps in enforcement (honest accounting)

| Gap | Which invariant | Status |
|---|---|---|
| ~~G-a~~ | P1/P2 — nothing re-verifies the raw copy after ingestion day | ✅ **CLOSED** 2026-07-27: `ingest.py --verify-provenance` re-checks every raw archive, working copy, normalization map and excerpt. **Its first run found a real drift** — see below. |
| **G-b** | P13 — a hand-edited `confidenceState` persists until the next recompute | Proposed check `CLAIM_CONFIDENCE_NOT_RECOMPUTABLE` (POLICY-001 §E1) |
| **G-c** | P3/P4 — reversibility is asserted at generation time, not re-checkable later | Proposed check re-running the map against the raw copy (BACKLOG-003/H4) |
| **G-d** | P11 — immutability is a convention plus absence of an update API, not a validator | Proposed content-hash re-verification (BACKLOG-003/H4) |

G-b through G-d become material once ingestion is routine and multiple operators are involved.

> **G-a was not hypothetical.** The first run of `--verify-provenance` found that the working copy
> of the TJR transcript had been altered after ingestion — source line 395, `"And I'm sure that"` →
> `"And I'm x that"`, 59,644 → 59,641 bytes. The raw archive was untouched and still hashed to
> `e91c5ea1…`, as did `IntakeManifest.contentHash` and the normalization map, so **no evidence was
> affected**: everything derives from the archive, and line 395 sits in a promotional section that
> produced zero claims. The altered copy is quarantined in `intake/rejected/` with a full record,
> and the working copy was restored byte-identically from the archive.
>
> The lesson is the one this specification exists to make true: **the archive, not the working
> copy, is the source of truth** — and a check that is only run once is not a guarantee. Run
> `--verify-provenance` periodically, not just at ingestion.

---

## 3. Auditing a single claim

To answer *"where did this claim come from?"*:

```python
import query_evidence as qe
idx = qe.EvidenceIndex.load("docs/trader-intelligence/evidence")

claim = idx.claims["CLAIM|TJR|20260727|023"]
for link in idx.links_for_claim(claim["claimId"]):
    item = idx.items[link["evidenceId"]]
    print(link["relationshipType"], item["sourceLocator"], repr(item["exactExcerpt"]))
    seg = idx.segments[item["sourceLocator"]]
    print("  lines %s-%s @ %s" % (seg["lineStart"], seg["lineEnd"], seg["startTimestamp"]))
```

Then map segment lines back to raw lines via `normalization-map.json`, and verify the raw copy
still hashes to the value recorded in `IntakeManifest.contentHash`.

`evidence_explain.explain_claim_by_id(idx, claimId)` produces the human-readable version of the
same walk, including the confidence derivation.

---

## 4. Auditing the whole library

```bash
python3 scripts/trader_intelligence/validate_evidence.py   # zero findings expected
python3 scripts/trader_intelligence/build_graph.py         # zero ERROR/FATAL expected
```

The graph makes the chain queryable: `DERIVED_FROM` (evidence→source),
`EVIDENCE_FROM_SEGMENT` (evidence→segment), `SEGMENT_OF` (segment→intake), `SUPPORTS`
(evidence→claim), `BLUEPRINT_DERIVED_FROM_CLAIM`, `RAISES_QUESTION`, `CLAIM_SUPPORTS_HYPOTHESIS`.

**An orphan is a provenance failure, not a cosmetic issue.** A claim with no link, an evidence item
with no segment, or a segment with no intake means something entered the library outside the
pipeline.

---

## 5. Provenance for non-transcript evidence

The chain generalizes. Replay and paper-trading evidence (`replay_result`, `paper_trade_result`)
will enter as `EvidenceItem`s under their own `EvidenceSource`, with `sourceLocator` naming the
replay run rather than a segment.

**Two requirements when that arrives** (currently unbuilt — see `BACKLOG-001`):

1. A replay run must be its own `EvidenceSource` with a `contentHash` over its inputs — data range,
   instrument, rule version, parameters — so a result can never be silently re-attributed to a
   different run.
2. Replay evidence must be a **distinct independence group** from transcript evidence. This is what
   makes POLICY-001 route (B) meaningful: replay corroboration must count as genuinely independent
   of what the trader said.

---

## 6. What provenance does *not* establish

Worth stating plainly, because the chain's rigour invites over-reading:

- **Not truth.** Perfect provenance to a trader's exact words says nothing about whether the rule
  works. That is what replay validation is for.
- **Not authority.** `contentHash` proves the file has not changed since ingestion. It does not
  prove the file is an authentic recording of the person it claims, nor that it is licensed.
  Those are `authenticityStatus` and `licensingStatus`, and both are currently `unverified` /
  `unknown` for the only source in the library.
- **Not completeness.** `transcriptCompleteness: unknown` means the chain is sound over what was
  ingested, while whether anything was missing upstream remains unestablished.

---

## 7. The evidence lineage the graph can represent, and where it genuinely breaks

B-32 made `TradeObservation` a first-class graph node, so MOGO's own preserved evidence
participates in the lineage instead of sitting in a parallel store. The obvious next question is
whether the intended end-to-end chain can now be represented **without fabricating anything**.

Assessed against the target chain, link by link, as of 2026-08-19:

| link | edge | status |
|---|---|---|
| Trader/Publisher → Source Artifact | `BELONGS_TO_TRADER` | **representable** |
| Source Artifact → Evidence | `DERIVED_FROM` (`EVIDENCE_ITEM` → `EVIDENCE_SOURCE`) | **representable** |
| Evidence → Strategy/Rule Claim | `SUPPORTS` / `CONTRADICTS` / `CONTEXTUALIZES` (EvidenceClaimLink) | **representable** |
| Strategy/Rule Claim → Trade Observation | — | **BROKEN — see below** |
| Trade Observation → Outcome | `outcome` field on the observation | representable as an attribute; deliberately not a node |
| Claim → Hypothesis | `CLAIM_SUPPORTS_HYPOTHESIS` / `CLAIM_CONTRADICTS_HYPOTHESIS` | **representable** |
| Hypothesis → Supporting/Contradicting Evidence | `supportingEvidenceIds` / `contradictingEvidenceIds` | **representable** |
| Research Finding | — | not an entity; generated reports are documents by standing convention |

### 7.1 The break is epistemic, not an oversight

**No record anywhere in this corpus references an `observationId`** — measured, not assumed:
zero hits across `claims/`, `hypotheses/`, `items/`, `links/`, `gaps/` and `blueprints/`. Nothing
states that any trade was taken *because of* any claim, so no such edge can be derived.

It would be easy to manufacture one. Every observation carries `strategyId=alex_g_sr_v1`, and
`SF|ALEX_G|SUPPORT_RESISTANCE_V1` exists as a node. Joining them looks like completing the chain
and is in fact the single most damaging thing that could be done to this corpus:

> `alex_g_sr_v1` is MOGO's **implementation**. `ALEX_G` is a **person**. An observation records
> what MOGO's code did. A claim records what a human said. Linking them asserts they are the same
> subject, and lets a query walk from MOGO's own paper trades into a human trader's evidence and
> count one as evidence for the other — OBSERVED data silently answering a SOURCE_STATED question.

The ids do not match, and making them match would be inventing the relationship rather than
discovering it. The graph therefore leaves this link absent, and **absent is the correct
representation of UNKNOWN**.

### 7.2 What would close it legitimately

Only a record that *states* the attribution: MOGO recording, at trade time, which rule caused an
entry — a `claimId` or `ruleId` stamped onto the observation by the engine that took the trade.

That is a **strategy-semantic change** requiring operator governance, not a graph change, and it
is out of scope for any derivation work. Until such a record exists, the chain is whole from both
ends and open in the middle, which is an honest description of what MOGO actually knows.

### 7.3 Two consequences worth stating plainly

- A query cannot currently answer *"which trades did this trader's stated rule produce?"* for any
  human trader. That is not a graph limitation to be engineered around; it is the same absence
  recorded throughout the acquisition log — no trader in this corpus has trade-level evidence.
- `orphanSources` in the reconciliation diagnostic counts EvidenceSources no observation cites.
  These are **genuine** and must stay visible. Making the number zero by attaching edges nothing
  states would recreate, in a new form, exactly the defect B-32 removed.

### 7.4 What consistency checking cannot do, stated so nobody assumes otherwise

Five rounds of adversarial verification drove the population checks to four independent
anchors — the observation's `sourceType=` stamp, its `captureBasis=` stamp, the source's
`metadata.captureBasis`, and the source's `metadata.engineStrategyId` — each of which now
fails **closed**, reporting when it cannot evaluate rather than skipping.

> **A correction.** An earlier version of this section claimed *"every attack that edits a
> preserved record now contradicts at least one of them."* That was **false**, and round 5
> refuted it with the cheapest evasion found in the whole exercise: the engine anchor read
> `if engine and strategyId and engine != strategyId`, so **deleting one field** made it
> evaluate False and disappear. Dropping `strategyId` moved 24 replay observations into
> FORWARD with every tool green and flipped the sign of the headline forward mean-R. The
> anchor now fails closed, but the lesson is the claim itself: a blanket "nothing gets past
> this" is the sentence most likely to be wrong, and stating it discouraged exactly the test
> that would have caught it.

Three things remain outside the reach of any consistency check, and all are worth naming
plainly rather than leaving for someone to discover as a surprise:

- **A record fabricated whole.** Adding new observation files that are internally consistent
  and cite a genuine source produces a corpus that agrees with itself at every point. There is
  nothing to contradict, because nothing was contradicted. No validator can distinguish a
  fabricated import from a legitimate one by inspection.
- **A coordinated rewrite of every anchor at once.** If all four stamps and both records are
  edited to agree, the corpus is again self-consistent.
- **An observation rewritten to be wholly consistent with a DIFFERENT legitimate source.**
  This is narrower than the previous item and cheaper than it sounds, so it is listed
  separately: it needs no source edit at all. Repoint `sourceId`, rewrite both `notes` stamps,
  and set `strategyId` to the target source's `engineStrategyId` — or simply choose one of the
  7 `paper_trade` sources that already record `engineStrategyId=alex_g_sr_v1`. Every anchor
  then agrees, because every anchor asks whether the record is consistent with the source it
  *names*, and it now is.

  Closing this would require an anchor tying an observation to the specific PACKAGE it was
  minted from — the observation carries `sourceContentHash` and `sourcePackageId`, but nothing
  in the corpus maps packages to sources, and the capture artifacts that would are gitignored
  by design. It is recorded as a known limit rather than papered over.

Detection of both belongs to a different mechanism: `research_assimilation.corpus_fingerprint`
hashes each record in full together with its source record, so either change moves the
fingerprint, and the learning ledger records the transition. Git history shows exactly which
bytes moved.

The honest framing is that **consistency checks establish that the corpus does not contradict
itself; they do not establish that it is true.** Provenance for that claim rests on the
capture chain — a package hash that re-derives from preserved bytes, an import that refuses
what it cannot verify, and a ledger that records every corpus transition — not on cross-field
agreement. Cross-field agreement is what catches the accident and the casual edit, which is
the overwhelming majority of what actually goes wrong.

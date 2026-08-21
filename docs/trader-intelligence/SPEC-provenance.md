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

> **A second correction, and a bigger one.** Nine rounds of this exercise attacked *rewriting*
> records. None attacked *removing* them, and every gate was blind: deleting the 21 losing
> forward observations moved the headline forward mean R from −0.18 to **+2.01** with all three
> validators exiting 0 and the warning count unchanged. Deleting the whole corpus raised only
> orphan warnings, which deliberately do not fail. The strongest available attack was never a
> clever edit — it was `rm`. That is now an ERROR (`EVIDENCE_REMOVED`), anchored on the
> assimilation ledger's high-water mark, because evidence here is append-only by design. The
> lesson generalises past this instance: a threat model assembled by defending against the last
> attack will keep missing the category nobody has tried yet.

Three things remain outside the reach of any consistency check, and all are worth naming
plainly rather than leaving for someone to discover as a surprise:

- **A record fabricated whole.** Adding new observation files that are internally consistent
  and cite a genuine source produces a corpus that agrees with itself at every point. There is
  nothing to contradict, because nothing was contradicted. No validator can distinguish a
  fabricated import from a legitimate one by inspection.
- **A coordinated rewrite of every anchor at once.** If all four stamps and both records are
  edited to agree, the corpus is again self-consistent. **Cheaper than first stated:** it takes
  three field edits across two records — `source.sourceType`, `source.metadata.captureBasis`
  and the observation's `notes` — not "all four stamps". The fourth anchor
  (`engineStrategyId`) needs no edit at all when a `replay_observation` source is retyped *in
  place*, because all 33 replay sources already record `alex_g_sr_v1`, matching the
  observations' `strategyId`.
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

  > **Partially falsified, and worth reading before trusting the paragraph above.** That
  > sentence was true of *packages* and wrong as a general claim about identity. The corpus
  > does carry a committed, per-trade manifest: `evidence/ledger-preservation/` records the
  > PAPER account's closed trades by `tradeId`, and a preserved trade's id is the
  > observation's `sequenceId`. It is tracked in git, not gitignored — 35 of its 39 identities
  > are present in the corpus, and the 4 that are not are `AGT|TEST|` developer trades the
  > importer refuses by policy. Nothing read it for eleven rounds. It now backs
  > `PRESERVED_IDENTITY_MISSING`, and it is the only anchor that survives
  > `research_assimilation --write`, because that command cannot recompute a record of what
  > was there before.

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

### 7.5 A gate that was proposed, measured, and rejected

Adversarial verification proposed reading the assimilation ledger's fingerprint pair as a
tamper gate: an entry where `observationTotalBefore == observationTotalAfter` while
`corpusFingerprintBefore != corpusFingerprintAfter` is the same-count content-substitution
signature, already written to disk and never read. It was described as "structurally free of
false positives."

**Measured against the six real ledger entries, three carry that signature and all three are
legitimate** — the B-28 supersession fields and the B-22 mapped-field corrections both edited
records without changing the count:

```
LEARN_20260818_f151601c6333   249 -> 249   fp 836e1471 -> f151601c   SIGNATURE
LEARN_20260819_5f600e56a9f5   258 -> 258   fp 071c65e0 -> 5f600e56   SIGNATURE
LEARN_20260819_c7a53309a3d6   259 -> 259   fp 6b61f6f8 -> c7a53309   SIGNATURE
```

A legitimate edit and a laundered substitution are **structurally identical**: both change
record content without changing the count. No property of the ledger distinguishes them, so a
gate built on it would fire on half the real history and be switched off within a week.

It is recorded here rather than built, because the useful conclusion is not "the check is hard"
but **what the ledger actually is**: a forensic record of what changed, not evidence about
whether the change was legitimate. That question is answered by git history and review, which
is what §7.4 means when it says detection "belongs to a different mechanism". The distinction
matters — a false gate is worse than a documented limit, because it trains people to ignore it.

### 7.6 Append-only in aggregate is not append-only

Eleven rounds hardened the corpus against rewriting, deletion and duplication, and every gate
they produced reduced the corpus to the same two things: a **cardinality**, and a
**whole-corpus hash pinned in a file the same actor can rewrite**. None of them ever asked
*which* observations have existed.

That is why a substitution which preserves the count was invisible to all of them at once —
delete the twenty-one losing forward trades, pad with twenty-one copies of a winner, and the
count is unchanged, the forward `n` is unchanged, and the headline mean R moves from −0.18 to
+2.00. Worse, the system re-blesses it on request: `research_assimilation --write` re-stamps
`corpusFingerprint` from whatever is on disk, so the tamper is laundered by one documented
maintenance command, leaving a ledger that shows a normal append with an intact chain.

**An aggregate anchor can always be recomputed from the tampered corpus. A per-identity record
cannot, because it records what was there before.** That is the whole distinction, and it is
the one the first eleven rounds missed — not because any individual gate was wrong, but
because they were all the same shape.

The general lesson, which outlives this milestone: *a defence assembled by repairing the last
attack converges on the last attack.* Deletion, anchor relocation and laundering were each
found only after the previous repair made them the cheapest remaining move. The question worth
asking of any new gate is not "does this close the attack I just saw" but **"what does this
gate reduce the corpus to, and what is invisible to anything expressed in those terms?"**

### 7.7 What the identity anchor covers — SUPERSEDED, see 7.8

*The section below described a frozen 13.5% snapshot. The operator approved option (A) and the
anchor is now continuous at 100%. It is kept because the reasoning about coverage-versus-
mechanism is what made the fix findable, and because a superseded claim should be visible as
superseded rather than quietly rewritten.*

### 7.7.1 (historical) What the identity anchor actually covered

`PRESERVED_IDENTITY_MISSING` is real and it closes the count-preserving substitution that
defeated every aggregate anchor. Its **coverage is not the corpus**, and the difference matters
more than the mechanism:

- `evidence/ledger-preservation/` holds **one** manifest, written once, frozen at
  **2026-08-17T17:39:10Z**.
- It covers **35 of 259** observations (13.5%), and **26 of 29** in the FORWARD population.
- `preserve_paper_ledger.js` is invoked by nothing — not `forward_capture.sh`, not any test —
  so **coverage does not grow as the system runs; it decays**. Every forward close after the
  snapshot is unanchored, and two of the three already uncovered are losses.

So the guarantee is: *no trade preserved before 2026-08-17 can vanish*. It is not: *no trade
can vanish*. A gate whose coverage shrinks while the system runs is not an invariant, and it
should not be described as one.

Making it continuous is blocked on a scope decision rather than on engineering: the ledger
lives in Chrome's **Local Storage**, which — unlike IndexedDB's per-origin directories — is a
single shared store holding 136 origins of the operator's browsing. The existing checkpoint is
safe precisely because IndexedDB can be origin-scoped, and Local Storage cannot be. See
backlog **B-32.14** for the options.

And the anchor answers only one direction. It asks whether something *disappeared*; nothing
asks whether something *appeared that was never observed* — §7.4(a) — and the system will
re-bless fabricated growth on request via `research_assimilation --write`. A require-list
cannot express that. An allow-list could, and an allow-list needs the coverage above. **They
are one decision, not two.**

### 7.8 Continuous identity coverage (B-32.14, operator option A)

MOGO maintains its own append-only record of which trades have existed, inside its own
IndexedDB origin and nothing else. Chrome's shared Local Storage is never inspected, copied,
enumerated or depended upon — option (B) was declined, and with it the only route that would
have read 136 unrelated origins out of the operator's profile.

**Where the identities come from.** They were already in MOGO's origin: every evidence package
carries `sourceTradeId`, and the capture pipeline already extracts hash-verified packages from
the origin-scoped IndexedDB checkpoint. `identity_manifest.py` turns that existing stream into
a committed manifest; `forward_capture.sh` updates it on every write-mode run.

**Why it is continuous rather than decaying.** The update runs before the novelty check and
before the "nothing new" early exit, and is driven by the *full* recovered set rather than the
fresh one — the manifest records which trades EXIST in the store, not which are new to the
corpus. A quiet capture is an idempotent no-op, not a gap. Its predecessor decayed precisely
because it was written once and never again.

**Measured coverage: 259 of 259 (100%)**, backfilled deterministically from 263 preserved
capture packages carrying 263 distinct trade ids. Nothing was invented: a package with no
`sourceTradeId` is skipped rather than given a synthetic one.

**Why it is not a new single point of trust.** Each identity is stored with the `contentHash`
of the package it came from, so it can be checked against the packages instead of believed. A
trade id arriving with a *different* hash is a conflict: the first recorded value is kept and
the run exits nonzero, because absorbing the newer hash would let a rewritten package launder
itself into the manifest meant to anchor it. Its availability is enforced by the same
`CORPUS_ANCHORS` invariant as every other anchor, so removing, emptying, renaming or hollowing
it is an ERROR rather than a silent pass.

**Failure behaviour.** The write is atomic (temp-and-rename), so an interrupted run leaves the
old manifest or the new one and never half of either — a truncated manifest would read as
identities that never existed. A damaged manifest is *refused*, not silently reset: starting
fresh would erase every identity ever recorded, which is the anchor deleting itself in response
to damage. Retry after a crash converges, and reordered input produces a byte-identical file.

**What it still does not answer.** It asks whether something disappeared. It does not ask
whether something *appeared* that was never observed — §7.4(a). That needs an allow-list, which
needed this coverage first; see backlog B-32.15.


**Measured 2026-08-21 — the manifest is not a mirror of a still-readable source.** A capture
run against the live instance recovered 41 hash-verified packages, carrying 41 distinct trade
ids, all 41 already in the manifest. The manifest holds 263. So **222 of 263 identities (84%)
now exist only here**: their packages have aged out of the uncompacted WAL and are no longer
recoverable from the running instance at all. Had the identity record still been the one-off
snapshot of §7.7, those 222 would have decayed out of coverage exactly as the aggregate ledger
did. This is the property the architecture was chosen for, observed rather than argued.

(The first reading of this measurement appeared to show one live id missing from the manifest.
It was pointed at the extractor's `--out` summary index, in which `sourceTradeId` is populated
for only 6 of 42 rows, instead of the `--packages` recovery the pipeline actually consumes.
Recorded because it is the §7.6 shape again: a count read off the wrong artifact looks exactly
like a finding.)

### 7.9 Anchors pin value, not only existence (B-32.17)

Rounds 9–16 built anchors that answer *which trades existed*: the require-list (a preserved
identity cannot stop existing), the allow-list (an observation anchored by nothing was never
captured), and the availability table (a gate cannot be switched off by deleting what it reads).
Every one of them is about presence.

None asked whether the surviving record still says what the anchor says it said. So an attack
that touches no id, no hash, no count and no anchor — rewriting `pnl`, `rMultiple` and `outcome`
in place on the preserved forward losers — moved forward mean R from −0.18 to +2.00 with every
gate green and exit 0. It did not even need a hand-edited state file: `research_assimilation.py
--write`, a documented maintenance command, re-stamped the fingerprint from the tampered corpus
and appended a normal-looking ledger entry.

The evidence to contradict it was already on disk, already committed, and read by nothing.
Measured on the live corpus:

| Anchor field | Corpus field | Agreement |
|---|---|---|
| `PAPER_LEDGER_PRE_BACKFILL.pnl` | `observation.pnl` | 35 / 35 |
| `PAPER_LEDGER_PRE_BACKFILL.pair` | `instrument` (`/`→`_`) | 35 / 35 |
| `PAPER_LEDGER_PRE_BACKFILL.closedAt` | `closedAt` | 35 / 35 |
| `MOGO_IDENTITY_MANIFEST.contentHash` | `sourceContentHash` | 259 / 259 |

Exact, on every joined row, at zero false-positive cost.

**Why this is a table and not four comparisons.** The recurring shape is not "this particular
comparison is missing" — it is *an anchor recorded a value and nothing compared it*, and that
shape was already present twice before anyone looked. `ANCHOR_VALUE_BINDINGS` declares what must
agree; `ANCHOR_FIELDS_UNBOUND` declares what deliberately does not, **with the measurement that
justifies it**; and a field in neither is reported (`UNADJUDICATED_ANCHOR_FIELD`). A field added
to an anchor writer therefore forces the decision instead of defaulting to silence. Two fields
are excused today and both were measured, not assumed: `hash` disagrees with `sourceContentHash`
on 35 of 35 preserved trades because it hashes the ledger row rather than the evidence package,
so binding it would report 35 false contradictions on a clean corpus; `captureBasis` is a
property of the `EvidenceSource`, and no observation carries it.

Three escapes are closed with it. Deleting the bound field from the record is
`ANCHOR_VALUE_UNCHECKABLE` — removing a value must not be cheaper than forging it. Renaming a
bound field at the *writer* is `UNADJUDICATED_ANCHOR_FIELD`. Removing the bound fields
altogether is `ANCHOR_VALUES_UNCOMPARED`, counted over rows that actually **joined** an
observation, because a manifest holding only the 4 refused developer trades legitimately
compares nothing.

**A limit, stated rather than papered over.** `MOGO_IDENTITY_MANIFEST` carries no rollup hash,
so under the threat model these rounds use — an attacker who can write any file in the corpus —
200 hand-appended identity rows admit 200 fabricated observations, and the value bindings do not
help because the attacker writes both sides. A rollup would not close it either: whoever can
append the rows can recompute the rollup. Closing it needs a witness *outside* the corpus, and
the only ones available (git history, the operator's checkpoint directory) are themselves
writable by the same actor. **Recorded as a threat-model boundary, not built as a gate that
would look like protection without being any** — the same disposition as §7.5.

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

  > **WRONG, corrected in §7.12 (B-32.19).** The second clause is true and the first does not
  > follow from it. `EvidenceSource.repositoryPath` **is** that mapping, it is committed, and
  > `validate_evidence.py` was already opening it — to call `os.path.exists` and stop. The
  > ARTIFACTS are gitignored; the MAPPING is not, and conflating the two is what left the
  > witness unread through five rounds. The same error is in `check_no_two_observations_share_a_package`
  > and in backlog B-32.4 / B-32.10.

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

### 7.10 A record checked against itself (B-32.18)

§7.9 bound anchor values to corpus values. Every gate up to that point — existence, then
value — compares the corpus to an **external witness**, so its reach stops exactly where the
witness stops. Two consequences were live:

- `rMultiple` and `outcome` are bound by no anchor, and `rMultiple` *is* the forward-performance
  headline. Rewriting those two while leaving `pnl` untouched — so every §7.9 binding still
  agreed — moved forward mean R from −0.06 to +2.00 and the win rate from 31.4% to 100%. One run
  of `research_assimilation.py --write` cleared the single finding it raised. Exit 0.
- The **224 replay observations are recorded in no ledger at all**, so no anchor can ever cover
  them. The same tamper on that cohort was silent outright.

A trade record is heavily over-determined, and MOGO's records agree with themselves exactly:

| Derivation | Agreement |
|---|---|
| `rMultiple` == (exit − entry) / \|entry − stop\|, signed by direction | 259/259, max deviation **4.1e-07** |
| `rMultiple` == `pnl` / `riskAmount` | 38/38, max deviation 0.0054 (pnl is rounded to cents) |
| `outcome` == sign(`rMultiple`) | 259/259 |
| `outcome` == sign(`pnl`) | 38/38 |

This needs no anchor, so it covers **every** observation and applies to every future close
automatically. Forging one field is no longer enough: the price fields, the money fields and the
labels must move together and stay consistent, and the price fields are what the anchors and the
source package already constrain. Tolerances are measured, not chosen — 1e-5 sits 25× above the
worst real deviation and far below the ~1R a tamper moves.

**`required` is measured, not chosen.** A derivation is required only where every preserved
record already supports it, so requiring it costs no false positive — and a test asserts that
against the live corpus, so the flag cannot outlive the fact. This mattered: the first version
skipped a derivation whose inputs were absent, and deleting `entry` from 259 records was
completely silent. That is shape (c) — *skip when you cannot evaluate* — written into the check
whose own docstring names it. Deleting an input is now `DERIVATION_UNCHECKABLE`.

### 7.11 The anchor document, and its rows (B-32.18)

`UNADJUDICATED_ANCHOR_FIELD` was row-scoped, so an anchor **document's own** fields stayed in the
unread set — the §7.9 shape, one scope up, in the change written to fix it. That is what made
*deleting the rows you tampered* different from *deleting all of them*: the vacuity guard fires
only when nothing compares, so removing exactly the 24 rows you intended to forge was silent.

Three of the ledger's document fields are re-derivable from the rows it holds, and were read by
nothing: `closedTotal` == number of identities, `closedDeveloperTest` == rows refused by import
policy, `closedReal` == the remainder, and `ledgerRollup` == sha256 of the row hashes joined by
newline — confirmed both by re-derivation and by the writer, `scripts/preserve_paper_ledger.js`.
Nine further fields (`balance`, `openPositions`, `windowSize`, the re-mint window counts) are
excused with reasons: they are facts about the **capture**, not about the corpus, and `balance`
in particular cannot be re-derived because balances do not chain trade-by-trade.

**Honest limit, unchanged from §7.9.** A rewriter who can write any file recomputes `closedTotal`
and `ledgerRollup` as easily as they delete the rows. What this closes is the *partial* edit —
which is every attack actually demonstrated across rounds 9–17.


### 7.12 The record against the package it was minted from (B-32.19)

§7.10 said a record checked against itself needs no witness. True — and it is also the limit.
Every gate through §7.11 compares the corpus to something **the corpus also writes**: an anchor
MOGO produced, a document MOGO stamped, or the record's own arithmetic. A forgery that is
internally consistent and leaves the anchors alone therefore passes all of them.

Demonstrated: rewriting all 259 observations so each one's derived R *genuinely is* +2.0 (moving
`exitPrice` to match, so every derivation in §7.10 agrees), emptying the ledger rows, and running
`research_assimilation.py --write` reached `{'INFO': 0, 'WARNING': 0, 'ERROR': 0, 'FATAL': 0}` —
forward **and** historical mean R at 2.0, win share 1.0. The replay-only variant touched nothing
outside `observations/` and was equally silent.

**The witness was committed and read by nothing — the fifth recurrence of the shape §7.9 names in
its own words.** Each observation's `sourceContentHash` is the `contentHash` of exactly one
captured package (259 distinct hashes, zero collisions across 263 packages), and each source's
`repositoryPath` names the artifact holding it. Seven fields agree exactly:

| Observation field | Package field | Agreement |
|---|---|---|
| `entry` | `positions[0].entryPrice` | 258/258 |
| `stop` | `positions[0].originalStop` | 258/258 |
| `direction` | `positions[0].direction` | 258/258 |
| `positionSize` | `positions[0].positionSize` | 258/258 |
| `accountBalanceBefore` | `positions[0].balanceBefore` | 257/257 |
| `exitPrice` | `outcomes[0].exitPrice` | 258/258 |
| `accountBalanceAfter` | `outcomes[0].balanceAfter` | 257/257 |

This is the only witness in the system **not derived from the corpus**: the engine wrote it when
the trade closed. The full-corpus forgery above now reports 163 contradictions, and the
replay-only variant 136 — and `research_assimilation --write` cannot clear either, because it
never touches the artifacts.

**Absence is counted, not skipped.** The artifacts are perishable and gitignored by design, so
some observations legitimately have no surviving witness — 1 of 259 today. Reporting nothing
would mean deleting `evidence/` switches the gate off, which is §7.16's lesson exactly, so an
unresolvable observation raises `PACKAGE_WITNESS_UNAVAILABLE` (WARNING) carrying the count: it
says how much of the corpus is standing on its own word, and a jump in it means the witness was
removed. A contradiction is an ERROR; an artifact that exists but cannot be parsed is an ERROR.

**Scope, and why it is not a switch.** Only sources the observations actually cite are parsed —
JSON-parsing all 59 reported 12 transcripts as unreadable package files, and a false positive is
how a real gate ends up disabled. That scope is not attacker-controlled: an observation names its
own `sourceId`, and repointing it is `POPULATION_REBINDING`.

**What it still does not answer.** A package that never existed — an attacker who writes both the
observation and a matching artifact — is the §7.9 write-everything boundary, unchanged. What
this closes is every forgery that edits the corpus and leaves the captured evidence alone.

### 7.13 Absence is not silence — one layer deeper (B-32.20)

§7.12 said the witness count was the tripwire: *"an unresolvable observation is reported at
WARNING and counted rather than skipped — otherwise deleting `evidence/` would switch this gate
off… a jump in it means the witness was removed."* Deleting `evidence/` is caught, and loudly:
259 of 259 unavailable plus 46 `UNRESOLVABLE_ARTIFACT`.

**Deleting one key from inside the files was not.** `_witness_value` returned a bare `None` both
when the engine recorded nothing and when the structure could not be read at all, and the caller
skipped it. The record still counted as *witnessed*, so the counter did not move. A forged
`positionSize` — a field with no intra-record derivation, so the package is its only check —
plus `objects` stripped from all 263 packages, then laundered through
`research_assimilation.py --write`, reported **byte-identically to a pristine corpus**.

That is the round-15 lesson applied at the package level and not carried one layer down, into a
package that resolves. The repair distinguishes the two cases that `None` conflated:

| Package state | Result | Measured on the live corpus |
|---|---|---|
| `objects` absent, non-dict, or the object list not exactly one entry | `PACKAGE_WITNESS_INCOMPLETE` (ERROR) | 0 of 262 — every package has it |
| the witnessed key absent from the object | `PACKAGE_WITNESS_INCOMPLETE` (ERROR) | 0 of 262 |
| key present, value `null`, field declared non-nullable | `PACKAGE_WITNESS_INCOMPLETE` (ERROR) | 0 of 262 |
| key present, value `null`, field declared nullable | `PACKAGE_WITNESS_DEGRADED` (WARNING, counted) | 2, both on one LIVE_CLOSE package |
| the RECORD drops a field the package supplies | `PACKAGE_WITNESS_INCOMPLETE` (ERROR) | 0 — the only two records missing a witnessed field are missing it where the package has nothing either |

`nullable` is measured, not chosen, and a test asserts it against the live packages, so the flag
cannot outlive the fact. Stripping `objects` now reports **1804 errors** where it reported
nothing.

**And the collision, resolved by sort order.** `_packages_by_content_hash` used `setdefault`, so
two packages claiming one `contentHash` were silently resolved first-wins, and the docstring
leaned on *"measured: zero collisions across 263 packages"* — a corpus snapshot standing in for
an invariant, which is the oracle class CLAUDE.md names. Measurement corrected it twice over:
**25 of 262 packages do appear in more than one artifact**, because a capture run re-exports what
an earlier run wrote. Identical copies agree by definition, so only a *disagreement* is
ambiguous; reporting the duplication itself would have been 25 false positives on a clean corpus.

### 7.14 An exemption is a bypass with a reason attached (B-32.21)

§7.13 separated "the engine recorded nothing" from "this cannot be read", and excused the first
with a `nullable` flag on the witness. The flag was wrong, and wrong in the way exemptions
usually are: it took a fact about **one package** — the engine really does leave
`balanceBefore`/`balanceAfter` null on one LIVE_CLOSE capture — and turned it into a licence
covering all 262.

Those two fields have no intra-record derivation, so the package is their only check. Nulling one
key in the artifact and forging the matching field in the record was a WARNING and nothing else:
**257 records forged, zero errors.** And `accountBalanceBefore` feeds
`population_fidelity.risk_pct_of_balance`, which produces the `RISK_SIZING_AGREES` conclusion —
so this forges a scientific finding, not a cosmetic number.

Three things made it worse than an ordinary gap, and all three are the general lesson:

1. **It had no true positives.** Measured on the clean corpus, the exemption fired **zero**
   times. It excused nothing and only opened surface — because the one record whose package nulls
   those fields carries no value for them either.
2. **Its test pinned it in one direction.** Understating nullability failed; overstating it
   passed. Overstating is the direction that disables gates, and a mutation flipping
   `positionSize` to nullable took the same attack from 258 errors to zero.
3. **The counter it fell back on was a snapshot doing an invariant's job** — the class corrected
   in `_packages_by_content_hash` one commit earlier. It went 0 → 514 and stayed a WARNING.

The flag is gone. What legitimises a null is not *which field it is* but that **the record claims
nothing either** — a record cannot assert a value the engine never recorded. That is one rule,
with no list to keep, and it costs nothing: measured, the only two nulls that reach it are on the
one record carrying neither field. Nulling the witness now costs exactly what forging it costs.

**And the seventh category's own front door.** `check_record_is_internally_consistent` opened with
`stated = record.get(...); if stated is None: continue` — so deleting **both** `rMultiple` and
`outcome` skipped every derivation. 161 losing records tampered: forward mean R 0.13 → 2.00, win
rate 100%, and n fell 259 → 98 because the tampered records simply stopped counting. Absence is
not silence at the top of a check as well as inside it; all 259 preserved observations state both
fields, so requiring them costs nothing. Now 322 `RECORD_FIELD_MISSING`.

That makes three sites where this one shape has now been found: package resolution, witness
value, and the derived field itself. It is not a lesson that generalises by being written down —
each new check has to be read for it specifically.

### 7.15 The lane that stores the evidence of hardening (B-32.22)

Twenty-one adversarial rounds are not stored as prose. They are stored as **Python tests** — they
are what kills every mutation, and the reason a repaired bypass stays repaired.

`tests/run_all.sh` guards the JS lane against silent shrinkage with a per-runner count manifest,
added deliberately after a suite once ran 36 fixtures instead of 39 and nothing objected. The
Python lane had no equivalent. Its only gate was the exit code of **one** `unittest` invocation
over every module, and its module count counted *files*. So renaming `test_` to `xtest_` across a
whole module de-collected every test in it and the run still exited 0 — the sibling modules kept
the total non-zero, so even Python's own `NO TESTS RAN` sentinel never fired.

The lane holding the entire accumulated kill record was the one lane with no guard against that
record quietly shrinking, while the lane holding UI fixtures had one. The ruling that silent
shrinkage is a failure already existed; it had only been applied to the other lane first.

`tests/count_python_tests.py` collects (without running) the test count per module and checks it
against `tests/expected_python_test_counts.tsv` in **both** directions — short means tests
stopped asking, long means the count has stopped meaning anything. A module that fails to import
is reported rather than counted as the one synthetic `_FailedTest` unittest substitutes, because
a suite that cannot load reporting a plausible `1` is precisely what this exists to stop.

A test count is not live data, so pinning it is **not** the corpus-snapshot anti-pattern: it
changes only when someone edits a test file, and then deliberately, via
`tests/update_expected_counts.sh` — which now regenerates both lanes, so the two cannot drift
apart in *whether they are protected at all*.

**And the gate has its own suite**, because a mutation making `--check` always pass survived
everything until it existed. That is the sixth time in this milestone that a check was found
unwired, unasserted, or unable to fail.

### 7.16 Two false positives waiting for legitimate data

Both found by measurement rather than by attack, and both matter because a gate that cries wolf
is a gate that gets switched off:

- `population_fidelity.risk_pct_of_balance` tested truthiness where its own docstring promised
  presence ("a missing balance is not a zero balance"). A trade risking exactly **zero** silently
  vanished from the sizing distribution instead of appearing in it as 0.0% — a scientific figure
  narrowing itself without saying so. A zero *balance* stays excluded, because dividing by it is
  undefined rather than because it is falsy.
- `outcome`-from-R returned "cannot evaluate" for a genuine breakeven, so the first real 0R close
  would have been reported as `DERIVATION_UNCHECKABLE`. A breakeven trade is neither a win nor a
  loss: that is **no verdict**, which is different from being unable to look. The two are now
  distinct sentinels, and the number itself is still checked by R-from-price — so `rMultiple: 0`
  is not an escape.

Also, `research_assimilation._diff_numbers` sorted group keys with a plain `sorted()`, which
raises the moment a key is `None` — which happens for any record with no `outcome`. That raised
out of `run_integrity_checks` **before the report was written**, leaving the previous run's
`ERROR: 0` on disk for other tooling to read. Same shape as the NaN crash (§7.13's sibling),
different trigger: a diagnostic that dies leaves behind an all-clear describing a corpus that no
longer exists.

# MOGO-018 — Autonomous Research Library Expansion
## STEP 1 — READINESS AUDIT (READ-ONLY)

**Status: AUDIT ONLY. No implementation was performed or authorized.**
**PAPER TRADING ONLY — live-money trading remains unauthorized.**

---

## 1. Starting checkpoint verification

| | Verified |
|---|---|
| Repository | `origin` → `https://github.com/joemogo/forex_hub.git` |
| Branch | `main` |
| HEAD | **`b49bc1bbb7ac7de2c03937024cf47598e90dd291`** — matches expected exactly |
| Tag `mogo-017-complete` | → **`b49bc1bbb7ac7de2c03937024cf47598e90dd291`** — same commit ✅ |
| Working tree | **clean** |
| Ahead / behind `origin/mogo-main` | **0 / 0** |

Checkpoint correct. No discrepancy.

---

## 2. Existing architecture inventory — **the headline finding**

> **MOGO already has a research library. It has 7,699 files, five trader profiles, 12 committed
> schemas and its own tooling — and the governed autonomous acquisition lane built in MOGO-014→017
> is not connected to it in any way.**

Two research worlds exist side by side, sharing **zero identifiers and zero code**:

### Lane A — the Knowledge Library (MOGO-002.x · PROGRAM-006 / PROGRAM-007)

| Component | Evidence |
|---|---|
| Sources | `evidence/sources/` — **12 `EvidenceSource` records** (`EVSRC\|ALEX_G\|20260727\|001`) |
| Items | `evidence/items/` — **416 `EvidenceItem` records** |
| Claims | `evidence/claims/` — **341 claims**, each carrying `traderId` **and** `strategyFamilyId` |
| Traders | `traders/{alex-g, ict, jvm, rayner-teo, tjr}/profile.json` + `strategy-families/` |
| Schemas | **12** in `schema/`, **18** in `evidence/schema/`, **6** in `graph/schema/` |
| Also present | hypotheses, blueprints, gaps, questions, contradictions, links, lifecycle, review-queue, graph nodes/edges, promotion state, owner decisions |
| Tooling | `evidence_registry.py`, `knowledge_library_report.py`, `build_graph.py`, `review_queues.py`, `intake_registry.py`, +25 more |
| Populated by | **operator-supplied transcripts** in `imports/{alex-g, rayner-teo, tjr}/` |

### Lane B — Governed Autonomous Acquisition (MOGO-014 → MOGO-017)

| Component | Evidence |
|---|---|
| Research artifacts | `research-artifacts/` — **2 files**, content-addressed (`RART\|d4e4ec82…`) |
| Raw acquisitions | `intake/acquired/` — **1 file** |
| Identity | `SRC\|youtube\|c785970cc458` + `resourceId` |
| Machinery | connector gate, bounded transport, authorization records, scheduler, change detection |

### The disconnection, measured

```
does the platform runtime reference evidence/sources, EVSRC, traderId or strategyFamily?  NONE
do the knowledge-engineering scripts reference SRC| ids, research-artifacts or the connector?  NONE
```

Only `research_corpus.py` and two test files reference `research-artifacts/` at all.

**MOGO-018's real job is therefore a BRIDGE, not a new library.**

---

## 3. Existing reusable components

Answering the audit questions directly.

| # | Question | Finding |
|---|---|---|
| 1 | Research artifact/storage structures? | Two: Lane A's `evidence/**` (rich, 7,699 files) and Lane B's content-addressed `research-artifacts/` (2 files) |
| 2 | Structures for `sourceId` / `resourceId` / artifacts / `content_hash` / provenance / history? | **All exist — in different id spaces.** Lane A: `EvidenceSource.sourceId`, `contentHash`, `repositoryPath`, `provenanceStatus`, `licensingStatus`, `acquiredAt`. Lane B: `SRC\|…` + `resourceId`, raw byte `contentHash`, `capability_results` history, `changeDetection` block |
| 3 | How are Alex G artifacts indexed/discoverable? | **Lane A:** by file name convention + directory scan (`evidence_registry.py`). **Lane B:** content-addressed filename only — *no index at all* |
| 4 | Registry / catalog / manifest / library already present? | **YES.** `EvidenceSource` **is** the source registry; `evidence_registry.py` is the registration layer; `knowledge_library_report.py` is literally a Knowledge Library report; `graph-manifest.schema.json` is a manifest |
| 5 | Explicit strategy-family attribution today? | **Schema: YES. Data: NO.** `EvidenceSource.strategyFamilyId` and `Claim.strategyFamilyId` both exist; **every source record has `strategyFamilyId: None`**. `traderId` **is** populated: `ALEX_G` ×9, `TJR` ×2, `RAYNER_TEO` ×1 |
| 6 | Concepts/topics represented? | **Partially.** A full graph layer exists (`GraphNode`, `GraphEdge`, `PromotionState`). `EvidenceItem` carries `evidenceType`, `marketCondition`, `timeframe`, `session` — but **no concept/topic field**. Concept modelling is the graph layer's job and is unused by Lane B |

---

## 4. Gaps

1. **No bridge.** A Lane B artifact cannot say which trader or strategy family it belongs to; a Lane A `EvidenceSource` cannot point at a Lane B artifact.
2. **No index for Lane B.** Discovery is "list a content-addressed directory". At 2 files that is fine; at 200 it is not.
3. **`strategyFamilyId` is dead schema** — declared everywhere, populated nowhere.
4. **Two `contentHash` meanings.** Lane A hashes a transcript file; Lane B hashes raw external response bytes. **They must never be conflated** — MOGO-017's whole contract rests on Lane B's definition.
5. **`acquiredAt: null` in Lane A's `EvidenceSource` records** — the same provenance gap MOGO-017 Step 3 fixed in Lane B. Out of scope; noted.
6. **One global resource-id validator.** `connector_authorization._valid_video_id` (11-char YouTube alphabet) is applied to **every** source, so a non-YouTube educator cannot be added without generalizing it.

---

## 5. Source / authorization readiness (TJR · CRT · ICT)

**Not authorized in this step. Assessed only.**

| Layer | Multi-source ready? |
|---|---|
| Authorization records | ✅ **Yes.** `authorizations.resolve(connection, source_id)` is already per-source; two records already exist (`SRC\|youtube\|c785970cc458`, `SRC\|local-intake\|e6f30303d8a9`). Adding an educator = one governance-supplied record + `mogo_runtime authorize` |
| Policy gate | ✅ **Yes.** `policy.evaluate` is per-source and already denies `no_authorization_record` |
| Trader profiles | ✅ **Already exist for TJR and ICT** (`traders/tjr/`, `traders/ict/`). **CRT does not exist** and would be new |
| Connector destination registry | ⚠️ **Structurally yes, with one blocker** — see §6 |

---

## 6. Connector: multi-source without weakening anti-SSRF

**The anti-SSRF property is per-entry and therefore scales.** `APPROVED_DESTINATIONS` maps
**source identity → complete destination**, so a caller supplies a source, never a URL. Ten entries
are exactly as safe as one: there is still no argument that becomes a fetch target.

**One genuine blocker:** `_valid_video_id()` is a **global** validator — an 11-character YouTube
alphabet applied to every source. A non-YouTube resource identifier cannot pass it.

**Smallest fix (do not implement yet):** move the resource-id rule **onto the registry entry**
(e.g. `resourceIdAlphabet` / `resourceIdLength`, or a named validator key) so each approved
destination validates its own resource shape. This *narrows* the boundary rather than widening it,
because each source then constrains its own identifiers instead of sharing one loose rule.

**Adding a source must remain a visible, reviewed edit to that table in code** — never configuration,
never runtime registration. That property must be preserved and re-asserted by test.

---

## 7. Scheduler / runtime readiness

| # | Question | Finding |
|---|---|---|
| 13 | Can the runtime support multiple approved sources? | ✅ **Yes, unchanged.** Every layer is already per-source: policy, authorization, connector gate, transport, ingestion, result store, change detection |
| 14 | Current fixed scheduled command | **`approved-collection.json` is ONE spec** — one `capabilityId`, one `sourceId`, one `resourceId`. `mogo_runtime collect` reads exactly one |
| 15 | Rate limits with N sources | **The collection window IS the rate limit** — one acquisition per `(source, resource)` per window. N approved items ⇒ **at most N requests per window**, bounded by construction. Reuse as-is |
| 16 | Change detection isolated by `(sourceId, resourceId)`? | ✅ **Already isolated, and proven.** `comparison_key()` requires both; MOGO-017 Step 2C tests prove a different resource and a different source each start their own history. **No change required for multi-source** |

**Smallest bounded generalization of the fixed command (do not implement yet):** make the committed
spec a **list** of approved collection entries and have `collect` iterate them, each validated by the
existing `validate_spec()`. Preserve every current property — no URL field, unknown fields refused,
each entry re-checked against the connector registry, no caller-supplied source. The installer's
window/cadence coherence check must then apply per entry.

**Explicitly NOT recommended:** a source-discovery mechanism, a configurable source list outside the
repository, or CLI arguments naming a source.

---

## 8. Proposed minimal library / index representation

**Recommended architecture (Q7, Q8):**

> **Existing research artifacts remain IMMUTABLE, content-addressed evidence. A separate DERIVED
> index references them. The index is rebuildable from the artifacts and the runtime history, and is
> never the source of truth.**

This is the architecture the audit questions propose, and repository evidence supports it: it is
exactly how `event_index` relates to the append-only event log (`reset --rebuild-index` proves the
log is the truth), and how `capability_results` relates to the acquisition history.

**Is a new storage structure necessary (Q7)? Only barely — and it should be an INDEX, not a store.**
`EvidenceSource` already has every field required:

| Need | Existing `EvidenceSource` field |
|---|---|
| source | `sourceId` |
| strategy family | `strategyFamilyId` *(present, unused)* |
| trader | `traderId` *(populated)* |
| research artifact reference | `repositoryPath` |
| current accepted content identity | `contentHash` |
| provenance | `provenanceStatus`, `licensingStatus`, `acquiredAt`, `externalReference` |
| lifecycle | `lifecycleStatus` |
| free-form | `metadata` |

**Missing only: `resourceId`, and a link to the Lane B `RART|…` artifact and its change history.**

**Minimum auditable representation (Q9)** — one record per `(sourceId, resourceId)` stream:

```
sourceId · resourceId · traderId · strategyFamilyId[]
artifactRef (RART|…)  · acceptedContentIdentity (raw byte SHA-256)
firstObservedAt · lastObservedAt · observationCount · lastClassification
authorizationId · lane: RESEARCH · promotionStatus: NOT_A_TRADING_RULE
```

Every field above **already exists somewhere** — in `capability_results`, in the `changeDetection`
block, or on the authorization record. **The index derives them; it invents nothing.**

**Q10 — can one artifact belong to several groupings without duplicating evidence?** **Yes, and it
must.** `strategyFamilyId` should be a **list on the index entry**, not a field on the artifact. The
immutable artifact is never rewritten; grouping is a property of the derived index. That is the
whole reason the index must be separate.

---

## 9. Corpus attribution model (Q17)

Attribution must mean exactly:

> **"This research material is part of the corpus collected for this strategy family."**

and must **not** be readable as *"this strategy is valid"* or *"this material is a trading rule."*

**Mechanically enforced, reusing what exists:**

- every index entry carries `lane: RESEARCH` and `promotionStatus: NOT_A_TRADING_RULE`, exactly as
  research artifacts already do;
- the existing `promotionPath` string on every artifact already spells out the full distance from
  artifact to any forward authorization — reuse it verbatim;
- attribution lives on the **derived index**, never on the immutable artifact, so grouping can be
  corrected without touching evidence;
- a `PromotionState` schema **already exists** in the graph layer and is the repository-native place
  for anything stronger than "collected".

---

## 10. Minimum corpus-maturity foundation (Q18)

**Deterministic metadata only. No AI scoring, no subjective judgement.** Everything below is
countable from records that already exist:

| Metric | Source |
|---|---|
| distinct `(sourceId, resourceId)` streams per strategy family | index |
| accepted artifacts per family | index |
| observation count and first/last observed per stream | `capability_results` |
| change events per stream | `SourceMutationDetected` count |
| authorization coverage — streams with a valid record | `acquisition_authorizations` |
| provenance completeness — streams with non-null `acquiredAt` | acquisition record |
| *(Lane A, if bridged)* evidence items and claims per family | `evidence/items`, `evidence/claims` |

**This is a foundation for a future assessment, not an assessment.** No threshold, no verdict, no
"ready" flag — and **strategy reconstruction is explicitly not in scope.**

---

## 11. Required tests / integrity gates (Q19)

| Property | Test |
|---|---|
| Source isolation | two sources produce disjoint index entries and disjoint change history |
| Resource isolation | two resources under one source never share a stream *(already proven, MOGO-017 2C)* |
| Strategy-corpus isolation | an artifact in family A never appears in family B's corpus counts |
| No cross-corpus contamination | index rebuild is deterministic and byte-stable for unchanged input |
| Immutable evidence unchanged | committed artifacts byte-identical before/after indexing *(pattern already used in MOGO-017 Step 3)* |
| Arbitrary URLs prohibited | no URL field in any spec; unknown fields refused; unapproved source refused *(extend existing MOGO-016 fixtures)* |
| Authorization fail-closed | a source with no record still denies |
| Change detection still correct | the full MOGO-017 contract + wiring suites must stay green |
| Anti-SSRF preserved | adding N destinations does not create a caller-controlled fetch target |

Plus the standing gates: platform suite, canonical gate, protected drift, C1, legacy corpus.

---

## 12. Scientific firewall assessment

The proposed direction is **read-and-organize only**. It has **zero** impact on:

ALEX rules · ALEX parameters · the forward activation cutoff `2026-08-11T02:43:57.894Z` ·
forward paper evidence · Campaign C1 · the legacy corpus · existing research evidence ·
scheduler safety · authorization · MOGO-017 change-detection semantics.

**Research collection and organization must not automatically create hypotheses, strategy rules,
backtests, paper campaigns or trading decisions.** Note that Lane A *already contains* a
`hypotheses/` directory and a `rule-candidate-proposal` schema from earlier milestones — **MOGO-018
must not write to either**, and a test should assert that.

### Integrity baseline recorded at audit time

| Check | Result |
|---|---|
| Protected ALEX drift | ✅ **0** — 63 functions, 4 constants byte-identical |
| Campaign C1 | ✅ **33 verified · 0 mismatched** · `VERIFIED` |
| Legacy corpus | ✅ **220 re-derived · 0 mismatched** |
| Research corpus | **2 artifacts**, unchanged |
| Scheduler | six-hour cadence, `runs = 0`, window `21600` |
| Working tree | clean |

---

## 13. MUST BUILD / REUSE AS-IS / DEFER

### MUST BUILD (small)
1. **The bridge + derived index** — one record per `(sourceId, resourceId)` stream, rebuildable,
   referencing the immutable artifact. The only genuinely new artefact.
2. **A rebuild/verify command** — `library rebuild` / `library status`, mirroring
   `reset --rebuild-index`, proving the index is derived rather than authoritative.
3. **Per-entry resource-id validation** in the connector registry — required before any non-YouTube
   source. *Narrows* the boundary.
4. **Bounded multi-entry collection spec** — a list, iterated; every existing refusal preserved.

### REUSE AS-IS
`EvidenceSource` schema · `traders/*/profile.json` and `strategy-families/` · authorization records
and `authorizations.resolve` · connector gate and `APPROVED_DESTINATIONS` (plus §6 fix) ·
`connector_transport` · ingestion and dedupe · **change detection — no change required** ·
`capability_results` as acquisition history · the collection window as the rate limit · scheduler and
launchd adapter · `lane` / `promotionStatus` / `promotionPath` markers.

### DEFER
Concept/topic modelling and graph integration · corpus-maturity *verdicts* · Lane A ↔ Lane B
`contentHash` reconciliation · backfilling `acquiredAt` on Lane A sources · CRT trader profile ·
transcript acquisition (**still prohibited**) · strategy reconstruction · any promotion mechanism.

---

## 14. Recommended MOGO-018 Step 2

> **Build the bridge and the derived index for the ONE already-approved source. Add no new source.**

Deliberately excludes multi-source: it proves the library architecture against existing evidence
before widening the authorization surface. Adding TJR/CRT/ICT becomes Step 3, after the index is
proven and the §6 connector fix is in.

**Files Step 2 would likely touch, and why:**

| File | Why |
|---|---|
| `platform/src/mogo_platform/runtime/research_library.py` *(new)* | derive index entries from `capability_results` + artifacts; **pure + one read query**, mirroring `acquisition_history.py` |
| `docs/trader-intelligence/schema/research-library-entry.schema.json` *(new)* | the committed record shape, following the 12 existing schemas |
| `platform/src/mogo_platform/runtime/cli.py` | one `library` subcommand (rebuild / status) |
| `platform/src/mogo_platform/runtime/audit.py` | surface corpus counts in `status`, as change detection already is |
| `docs/trader-intelligence/traders/alex-g/strategy-families/support-resistance-v1.json` | **read-only** — the attribution target that already exists |
| `tests/platform/test_runtime_research_library.py` *(new)* | §11 properties |
| `tests/run_platform_tests.sh` | register the suite |
| `MOGO_018_…md` | report |

**Not touched:** `index.html`, ALEX, forward evidence, Campaign C1, legacy corpus, the connector
registry, the scheduler spec, existing research artifacts.

---

## 15. Risks and ambiguities requiring operator review

1. **Which library wins?** Lane A is far richer but transcript-based and operator-fed; Lane B is
   governed and autonomous. **Recommendation: Lane B artifacts become `EvidenceSource`-shaped index
   entries in Lane A's namespace** — but the id-space decision (`EVSRC|…` vs `SRC|…`) is a
   governance call, not an engineering one. **Flagged, not decided.**
2. **`strategyFamilyId` is unused everywhere.** Populating it retroactively for the 12 existing
   sources would edit committed evidence. **Recommendation: leave Lane A untouched; populate only on
   new derived index entries.**
3. **Two `contentHash` meanings** (transcript file vs raw external bytes). Conflating them would
   break MOGO-017's contract. **Recommendation: the index carries Lane B's raw byte identity under
   an unambiguous name and never overwrites Lane A's field.**
4. **CRT has no trader profile, no evidence, no `imports/` directory.** It is the least-prepared of
   the three named families.
5. **Only one resource is approved today** (`hb7ot1_szWI`). A library over one item proves the
   mechanism, not the value — expect the corpus to look trivially small until Step 3.
6. **`_valid_video_id` must be generalized before any non-YouTube source** (§6). Attempting TJR/ICT
   acquisition before that fix would fail closed at the gate — safe, but confusing if unexpected.
7. **Lane A already contains `hypotheses/` and rule-candidate schemas.** MOGO-018 must not write to
   them, and that prohibition should be a test rather than an intention.

---

## Authorization status (Step 1)

> **NO MOGO-018 IMPLEMENTATION WAS PERFORMED OR AUTHORIZED BY THE STEP 1 AUDIT.**

No product or runtime file was modified. This report was the only file written, and nothing was
committed or pushed.

**LIVE-MONEY TRADING REMAINS UNAUTHORIZED.**

---
---

# MOGO-018 STEP 2 — THE MINIMAL RESEARCH LIBRARY BRIDGE

**Status: ✅ COMPLETE. Not committed — held for review.**
**PAPER TRADING ONLY — live-money trading remains unauthorized.**

## 1. Design actually chosen — smaller than the Step 1 recommendation

Step 1 proposed a derived index **plus a `library rebuild` command plus a JSON schema file**.
Repository inspection during implementation showed a smaller solution, and it was taken:

| Step 1 proposed | Actually built | Why smaller is correct |
|---|---|---|
| index + **`rebuild`** command | **read-only `library` command** | There is nothing to rebuild. The index is computed on read from `capability_results`, so it has no persisted form to regenerate. A `rebuild` verb would have implied stored state that does not exist. |
| new **JSON schema file** | **a tested Python validator** | A schema file nothing validates against is decoration and a second source of truth. `resolve_attribution()` enforces the shape and 8 fixtures prove each refusal. |
| new **entry storage** | **no storage at all** | `entries()` is a pure read. Nothing is written, anywhere. |

**Net production code: one module (291 lines, the majority of it documentation — three public
functions: `resolve_attribution`, `entries`, `corpus_summary`), one CLI subcommand, and one
committed declaration file.**

## 2. Exact identifier mapping

Performed **before** implementation, as required. The two lanes both have a field spelled
`sourceId` and **they do not mean the same thing** — the exact trap the instruction warned about.

| Concept | Lane A (Knowledge Library) | Lane B (governed acquisition) | Bridge treatment |
|---|---|---|---|
| Educator / channel | `traderId` = `ALEX_G` | `sourceId` = `SRC\|youtube\|c785970cc458` | **mapped by declaration** — the one thing not derivable |
| One piece of material | `EvidenceSource` (`EVSRC\|ALEX_G\|20260727\|001`) | the `(sourceId, resourceId)` **pair** | bridge entry keyed on Lane B's pair |
| Strategy family | `SF\|ALEX_G\|SUPPORT_RESISTANCE_V1` | *(none)* | **reused verbatim**, as a **list** |
| Artifact | `repositoryPath` → transcript | `RART\|…` + `storedPath` | **referenced, never copied** |

**Lane B's `sourceId` is semantically closer to Lane A's `traderId` than to Lane A's `sourceId`.**
Collapsing the two `sourceId` fields because they share a name would have been exactly wrong, so the
bridge never does it and **never mints an `EVSRC|` identifier** — asserted by test.

**No ownership collision exists.** Lane B's only resource is `hb7ot1_szWI` — *"How to Start Trading
with Just $50"* — and **none of the 9 committed ALEX_G `EvidenceSource` records covers that video**.
The bridge is purely additive, so no translation had to be invented and no STOP condition was hit.

### The one thing that cannot be derived, and how it is still verified

`SRC|youtube|c785970cc458` → `ALEX_G` is knowledge, not arithmetic. It is declared in
`docs/trader-intelligence/library/source-attribution.json`.

**But the identifier itself is recomputed rather than trusted.** The declaration carries the
provider and channel URL, and `resolve_attribution()` recomputes
`ids.make_source_id(provider, channelUrl)` and **refuses the record if it disagrees**. That channel
URL is the one already committed in `alex-channel-catalogue.json` — the same record MOGO-015 used to
verify the source originally. A typo, or a channel URL swapped under an unchanged id, **fails
closed** instead of silently attributing one educator's material to another.

`traders/alex-g/profile.json` has an empty `sourceChannels: []` which would have been the natural
home — but populating it would **mutate committed Knowledge Library evidence**, which governance
decision 8 forbids. **Left untouched.**

## 3. Exact hash-semantics mapping

| | Lane A | Lane B |
|---|---|---|
| Field name | `EvidenceSource.contentHash` | `connector_transport.content_hash` |
| Hashes | a stored **transcript file** | the exact validated **external response body bytes** |
| Role | file integrity | **MOGO-017 scientific content identity** |
| Example | `c9c4193a8aeedc9a…` | `b668d4209abbf2b8…` |

**The bridge never emits a field called `contentHash`.** It emits **`acceptedContentIdentity`**
alongside an explicit **`acceptedContentIdentityBasis: RAW_EXTERNAL_RESPONSE_BYTES`** and
`acceptedContentIdentityAlgorithm: SHA-256`, so neither can be read as, or quietly substituted for,
the other. Three fixtures assert this, including one proving a committed `EvidenceSource` keeps its
own hash meaning and that the two numbers differ.

The bridge also **reuses** `change_detection.accepted_identity_from_acquisition()` rather than
restating acceptance, so the library and the detector can never disagree about what counts as
accepted content.

## 4. Files changed and why

| File | Change | Why |
|---|---|---|
| `docs/trader-intelligence/library/source-attribution.json` | **new** | the ONE undeivable fact: educator + strategy families per approved source. A visible, reviewed edit — not configuration, not runtime-supplied |
| `platform/src/mogo_platform/runtime/research_library.py` | **new** | the derived index: `resolve_attribution`, `entries`, `corpus_summary`. **No I/O, no writes, no network** |
| `platform/src/mogo_platform/runtime/cli.py` | +`library` subcommand | operator visibility; also performs the file read, so the runtime module stays I/O-free |
| `tests/platform/test_runtime_research_library.py` | **new** — 29 fixtures | the 13 required properties |
| `tests/platform/test_runtime_change_detection_contract.py` | allow-list +1 | `research_library` now legitimately imports the contract |
| `tests/run_platform_tests.sh` | +1 line | register the suite |

**Not touched:** `index.html`, ALEX, forward evidence, Campaign C1, legacy corpus, existing research
artifacts, the connector registry, the scheduler spec, authorization records, any Knowledge Library
record.

**The connector's global 11-character video-id validator was NOT generalized** — it was not required
to bridge the one approved source, and per instruction it is deferred to the source-expansion step.

## 5. Tests added — 29, all passing

| Requirement | Fixtures |
|---|---|
| 1 · approved source produces the correct reference | entry with correct source/resource/trader/family/artifact/identity |
| 2 · source and resource isolation | two resources → two entries with their own identities |
| 3 · immutable artifacts unchanged | **byte fingerprint asserted in `tearDown` of every index fixture** |
| 4 · Knowledge Library evidence unchanged | same, over `evidence/sources` + `traders/**` |
| 5 · hash semantics distinct | no bare `contentHash`; identity == external byte hash ≠ artifact hash; Lane A record intact |
| 6 · UNCHANGED creates no duplication | one entry, `acceptedObservationCount=2`, `distinctIdentities=1` |
| 7 · CHANGED updates the current reference | identity moves to B, both identities retained, **prior artifact not rewritten** |
| 8 · failure never advances library state | HTTP 500 and invalid-content cases; a stream with no accepted acquisition has **no entry** |
| 9 · attribution cannot contaminate another corpus | attribution comes ONLY from the declaration; no fallback |
| 10 · multiple groupings without duplication | `strategyFamilyIds` is a list; two families on one stream |
| 11 · arbitrary URLs prohibited | code scan: no `urlopen`/`urllib`/`socket`/`Request(`; the one URL present is used only to recompute an id |
| 12 · authorization fail-closed | the library cannot grant authorization — no `record_authorization`, no `policy.evaluate` |
| 13 · creates no trading/scientific artefact | code scan for hypothesis/backtest/blueprint/campaign/promote; `hypotheses/`, `blueprints/`, `proposals/` listings asserted unchanged |
| *(extra)* index is derived | two reads byte-identical; **no write-capable call exists in the module** |
| *(extra)* attribution is verified | 8 refusal fixtures: mismatched id, swapped URL, missing field, non-`SF\|` family, duplicate source, wrong schema |

The acquisition harness is **reused** from the MOGO-017 Step 2C suite rather than duplicated.

## 6. Proof that immutable evidence and the Knowledge Library are unchanged

- Every index fixture fingerprints **both** trees in `setUp` and asserts byte equality in `tearDown`.
- `git status` over `research-artifacts`, `intake`, `evidence`, `traders`, `schema`, `index.html`,
  `docs/campaigns` and `evidence/` is **empty**.
- The runtime module contains **zero `open()` calls** and zero write-capable calls — asserted
  structurally by AST.

## 7. Integrity results

| Gate | Result |
|---|---|
| Research library suite | ✅ **29 / 29** |
| Platform suite | ✅ **23 suites · 958 tests · 0 failures · 0 errors** |
| Canonical gate | ✅ **19 suites · 1,160 fixtures · 1,160 passed · 0 failed** |
| **Protected ALEX drift** | ✅ **0** — 63 functions, 4 constants |
| Campaign C1 | ✅ **33 verified · 0 mismatched** · `VERIFIED` |
| Legacy corpus | ✅ **220 re-derived · 0 mismatched** |
| Immutable research evidence | ✅ byte-unchanged |
| Knowledge Library evidence | ✅ byte-unchanged |
| Scheduler | ✅ six-hour cadence, spec at `21600`, **untouched** |

### Three boundary tests failed and were fixed properly — reported, not excused

1. **My firewall scans matched PROSE**, not code — the module docstring *states* "creates no
   hypothesis, rule, blueprint, backtest, campaign or trading decision", so scanning the file text
   flagged the sentences describing the firewall. **This is the same mistake I made in MOGO-017 Step
   2C**; the fix reuses that lesson (docstring-stripped AST scan) and the helper now says so.
2. **`youtube` appeared in a runtime module** — the boundary suite forbids that marker outside the
   declaration module. My docstring's identifier table was rewritten to use placeholders.
3. **`open()` in a runtime module without the path guard** — correctly flagged. Rather than add a
   guard reference, the file read moved to `cli.py`, leaving `research_library.py` **entirely
   I/O-free**. This is the same split `scheduled_collection.py` already uses.

**No guard was weakened.** The change-detection allow-list gained `research_library.py` as an
intended, reviewed entry and remains an allow-list, so a fourth consumer still breaks it.

### Observed during the step, reported honestly

The scheduler **fired naturally on its production cadence** while this work was underway (`runs = 2`),
logging `CHANGE DETECTION UNCHANGED` with exit 0 and empty stderr. Not triggered by this step —
autonomous operation continuing as designed.

## 8. Scientific firewall

Zero impact on ALEX rules, ALEX parameters, protected functions, the forward activation cutoff
`2026-08-11T02:43:57.894Z`, the forward paper campaign, Campaign C1, the legacy corpus, existing
research evidence, MOGO-017 change-detection semantics, scheduler cadence or authorization
boundaries. The live forward browser was not touched. No paper trade was forced. No source was
authorized.

**Organization is not validation.** Every entry and every corpus bucket carries `lane: RESEARCH` and
`promotionStatus: NOT_A_TRADING_RULE`, and the CLI prints that presence in a corpus is not a claim of
validity.

## 9. Live result

```
MOGO research library (DERIVED -- organization, not validation)
  entries : 1
  SRC|youtube|c785970cc458 / hb7ot1_szWI
      trader=ALEX_G  families=SF|ALEX_G|SUPPORT_RESISTANCE_V1  [ATTRIBUTED]
      artifact=RART|d4e4ec829fe80b576a1304f46405f76a
      acceptedContentIdentity=b668d4209abbf2b8... (RAW_EXTERNAL_RESPONSE_BYTES)
      accepted observations=7  distinct identities=1  last=UNCHANGED
  corpus by strategy family:
      SF|ALEX_G|SUPPORT_RESISTANCE_V1    streams=1 observations=7 identities=1
```

Every question the bridge was asked to answer, answered from authoritative existing data.

## 10. Remaining work before multi-source expansion

1. **Generalize the resource-id validator** — `_valid_video_id` is global and YouTube-shaped. Move
   the rule onto each registry entry. **Blocking for any non-YouTube source.**
2. **Multi-entry collection spec** — `approved-collection.json` is one entry; `collect` reads one.
3. **Authorization + destination + attribution per new educator** — three visible reviewed edits each.
4. **CRT has no trader profile, no evidence, no imports directory.** TJR and ICT already have profiles.
5. **`strategyFamilyIds` for TJR/ICT** — TJR has `SF|TJR|SESSION_ZONE_REACTION`; **ICT has a profile
   but no strategy family**.

## 11. Recommendation for MOGO-018 Step 3

> **Generalize the resource-id boundary and the collection spec — then authorize exactly ONE new
> educator end to end.**

In that order, because the validator is the hard blocker and is a *narrowing* change. Recommend
**TJR** first: it already has a trader profile, a strategy family, committed evidence and an
`imports/tjr/` tree, so the bridge has something real to attribute to. **ICT** second (profile
exists, strategy family does not). **CRT last** — it has nothing yet.

**Still out of scope:** transcript acquisition, concept/topic modelling, corpus-maturity verdicts,
strategy reconstruction, any promotion mechanism.

---

# ✅ STEP 2 CHECKPOINT — COMMITTED

| | |
|---|---|
| Reviewed | approved by ChatGPT/operator |
| **Checkpoint commit** | **`1c76d2b0251efa6e39905713e5114fae6b95c919`** |
| Commit message | `MOGO-018 Step 2: minimal research library bridge` |
| Pushed to | `origin/mogo-main` |
| Starting checkpoint | `b49bc1bbb7ac7de2c03937024cf47598e90dd291` (`mogo-017-complete`) |

Final pre-commit verification confirmed only the seven intended files changed, all gates green, and
immutable research evidence, Knowledge Library evidence, ALEX, Campaign C1, the legacy corpus, the
scheduler cadence and MOGO-017 change-detection semantics all unchanged.

**One report inaccuracy was found and corrected during that verification:** the module was described
as "~190 lines" when it is 291 (the estimate predated the refactor that moved file I/O to the CLI and
added the explanatory docstrings). Corrected before committing.

**LIVE-MONEY TRADING REMAINS UNAUTHORIZED.**

---
---

# MOGO-018 STEP 3A — PER-SOURCE RESOURCE-ID AUTHORIZATION BOUNDARY

**Status: ✅ COMPLETE. Not committed — held for review.**
**PAPER TRADING ONLY — live-money trading remains unauthorized.**

## 1. Starting state

HEAD `faf4ba8c50c0cc9923016d9749037f0d02d6c5df`, clean, 0 ahead / 0 behind. Verified before editing.

## 2. The old global boundary

```python
VIDEO_ID_PATTERN = "abc…XYZ0123456789-_"   # 64 chars
VIDEO_ID_LENGTH  = 11

def _valid_video_id(value):                # ONE rule, EVERY destination
    if not isinstance(value, str) or len(value) != VIDEO_ID_LENGTH:
        return False
    return all(character in VIDEO_ID_PATTERN for character in value)
```

Called from `derive_destination()` and `evaluate()`. A future non-YouTube destination would have
**inherited a rule written for someone else** — and the only way to admit it would have been to
*loosen* the shared rule, which would simultaneously loosen it for YouTube.

## 3. The new per-destination boundary

Each approved destination declares its **own** constraint:

```python
"SRC|youtube|c785970cc458": MappingProxyType({
    …
    "resourceIdAlphabet": VIDEO_ID_PATTERN,   # referenced, never retyped
    "resourceIdLength": 11,
    …
})
```

```python
def _valid_resource_id(entry, value):
    if entry is None or not hasattr(entry, "get"):        return False
    alphabet = entry.get("resourceIdAlphabet")
    length   = entry.get("resourceIdLength")
    if not isinstance(alphabet, str) or not alphabet:     return False
    if isinstance(length, bool) or not isinstance(length, int) or length <= 0:
                                                          return False
    if not isinstance(value, str) or len(value) != length: return False
    return all(character in alphabet for character in value)
```

`hasattr(entry, "get")` rather than `isinstance(entry, dict)` — registry entries are
`MappingProxyType`, which is deliberately **not** a dict.

## 4. Why this NARROWS rather than widens authorization

| | Before | After |
|---|---|---|
| A destination with **no** declared rule | inherited YouTube's rule and would fetch | **accepts nothing** |
| Admitting a differently-shaped id | required **loosening the shared rule for everyone** | requires a **new entry declaring its own rule** |
| Blast radius of a constraint edit | every destination | exactly one destination |

Nothing else moved. The destination is still **derived** from the registry, callers still supply no
URL, `requestedUrl` substitution is still refused, the scheme/host allow-list and forbidden-host
list are untouched, and `approved_source_ids()` is still exactly one entry. **No source was
authorized. No new field is caller-supplied.**

## 5. Exact files changed

| File | Change |
|---|---|
| `runtime/connector_authorization.py` | entry declares `resourceIdAlphabet` + `resourceIdLength`; `_valid_video_id(value)` → `_valid_resource_id(entry, value)`; two call sites pass the entry; `VIDEO_ID_LENGTH` removed (now per-entry); `VIDEO_ID_PATTERN` retained as YouTube's alphabet, referenced by YouTube's entry |
| `tests/platform/test_runtime_connector_authorization.py` | +14 fixtures |

**Two files. No new module, no class, no framework, no regex engine, no plugin system.** No test
referenced the old constants or validator, so nothing else needed touching.

## 6. Compatibility with the existing approved source — proved, not asserted

The old global rule is **reconstructed inside the test** and compared against the new per-entry rule
across every single-character substitution at every one of the 11 positions, every length 0–15, and
hostile shapes.

An ad-hoc sweep over **3,127 cases** (including 2,000 randomised) reported:

```
BEHAVIOUR MISMATCHES: 0
newly-accepted ids  : 0      <-- nothing previously invalid became valid
newly-rejected ids  : 0      <-- nothing previously valid became invalid
```

**The acceptance boundary for the existing source is byte-for-byte identical.**

## 7. Tests — 36 in the suite, 14 new, all passing

| Required proof | Fixture |
|---|---|
| 1 · approved source still accepts its exact valid form | permit + URL derivation |
| 2 · invalid length denied | `""`, 1, 10, 12, 64 chars |
| 3 · invalid alphabet denied | `!`, space, `/`, `.`, `%`, tab, `é` |
| 4 · unknown source denied | denied **before** any resource check |
| 5 · missing declaration fails closed | 4 shapes, all reject |
| 6 · malformed declaration fails closed | 8 shapes incl. `True`, `11.0`, `"11"`, `0`, `-1` |
| 7 · one destination's rule ≠ another's | length-6 and digits-only local declarations; the real entry unaffected |
| 8 · no caller-controlled URL accepted | 4 hostile URLs → `requested_url_does_not_match_approved_destination` |
| 9 · derivation registry-controlled | url == template.format(...); still exactly one approved source |
| 10 · existing connector tests green | all 36 pass |
| 11 · MOGO-017 behaviour unchanged | connector + transport + detection + wiring + bridge: **167 tests green** |
| *(extra)* every shipped entry declares a usable constraint | no entry can ship ruleless |
| *(extra)* non-string resource ids rejected | incl. `bytes` |

**No second real source was added.** Per-destination behaviour is proven with local test-only
declarations, so nothing was authorized to test authorization.

## 8. Integrity results

| Gate | Result |
|---|---|
| Focused connector/transport/detection/bridge | ✅ **167 / 167** |
| Platform suite | ✅ **23 suites · 972 tests · 0 failures · 0 errors** |
| Canonical gate | ✅ **19 suites · 1,160 fixtures · 1,160 passed · 0 failed** |
| **Protected ALEX drift** | ✅ **0** |
| Campaign C1 | ✅ **33 verified · 0 mismatched** · `VERIFIED` |
| Legacy corpus | ✅ **220 re-derived · 0 mismatched** |
| Immutable research evidence | ✅ unchanged (`git status docs/` empty) |
| Knowledge Library evidence | ✅ unchanged |
| Step 2 bridge | ✅ still reads correctly, unchanged output |
| Scheduler | ✅ `21600`, 4 calendar entries, spec untouched |
| `index.html` / ALEX | ✅ not modified |

**No new external acquisition was performed.** Nothing required one.

## 9. Remaining work for Step 3B

1. **Multi-entry collection spec** — `approved-collection.json` is one entry and `collect` reads
   one. Make it a list, iterate, validate each through the existing `validate_spec()`. Preserve
   every refusal; apply the installer's window/cadence coherence check per entry. The collection
   window already *is* the rate limit, so N items ⇒ at most N requests per window.
2. **Then Step 3C: authorize exactly ONE educator** — authorization record + destination entry
   (now declaring its own resource-id rule) + attribution entry. **TJR first**: it already has a
   trader profile, `SF|TJR|SESSION_ZONE_REACTION`, committed evidence and an `imports/tjr/` tree.
   ICT has a profile but **no strategy family**. CRT has nothing.

Still out of scope: transcript acquisition, concept modelling, corpus-maturity verdicts, strategy
reconstruction, promotion.

---

# ⚠️ STEP 3A NOT COMMITTED

Complete and green, but **nothing was committed or pushed** — held for ChatGPT/operator review.

**LIVE-MONEY TRADING REMAINS UNAUTHORIZED.**

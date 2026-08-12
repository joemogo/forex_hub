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

# ✅ STEP 3A CHECKPOINT — COMMITTED

| | |
|---|---|
| Reviewed | approved by ChatGPT/operator |
| **Checkpoint commit** | **`70f5bb39a38d2d00f2aa087ac5af8bf8f00a6e2a`** |
| Commit message | `MOGO-018 Step 3A: per-destination resource-id authorization boundary` |
| Pushed to | `origin/mogo-main` |
| Starting checkpoint | `faf4ba8c50c0cc9923016d9749037f0d02d6c5df` (Step 2) |

Final pre-commit verification re-ran all fifteen required checks: only the three intended files
changed; the report's factual claims were spot-checked against the running code; focused
authorization/connector/policy (138) and MOGO-017 detection plus Step 2 bridge (111) tests green;
platform 972/972; canonical 1,160/1,160; drift 0; C1 33/33; legacy corpus 220/0; immutable research
evidence and Knowledge Library evidence byte-unchanged; scheduler untouched; **no acquisition
performed** (`capability_results` still 7 rows, unchanged from the Step 2 checkpoint); **no source
authorized** (`approved_source_ids()` still one entry); and a live fail-closed sweep confirmed URL
substitution, `file://`, unapproved source, missing authorization, wrong operation and crafted
resource identifiers are each still denied with their own distinct reason.

**LIVE-MONEY TRADING REMAINS UNAUTHORIZED.**

---
---

# MOGO-018 STEP 3B — BOUNDED MULTI-ENTRY AUTONOMOUS COLLECTION

**Status: ✅ COMPLETE. Not committed — held for review.**
**PAPER TRADING ONLY — live-money trading remains unauthorized.**

## 1. Starting state

HEAD `0414920081cb65c7ea5f10e9c6581a4f4f176a84`, clean, 0 ahead / 0 behind.

## 2. Old model → new model

| | Before | After |
|---|---|---|
| Committed file | one bare entry object | `{schemaVersion, note, entries: [...]}` |
| `cmd_collect` | built one command | iterates the committed list |
| Requests per window | 1 | **at most N**, N = committed entry count |

**The entry record itself is byte-for-byte unchanged** — still
`mogo.scheduled-collection.v1`, still validated by the same `validate_spec()`.

## 3. Spec representation, and why this shape

```json
{
  "schemaVersion": "mogo.scheduled-collection-set.v1",
  "note": "...",
  "entries": [ { "schemaVersion": "mogo.scheduled-collection.v1", ... } ]
}
```

Two distinct version strings, deliberately: a **`-set.v1` document** contains
**`mogo.scheduled-collection.v1` entries**, so a reader never has to guess which schema a version
refers to, and the entry schema stays versioned independently of the document carrying it.

**This is the maximal-reuse shape.** `validate_spec()` and `build_command()` were **not modified at
all** — they operate on an entry, and an entry is exactly what it always was. The only new code is
the document wrapper.

## 4. Whole-set validation before any acquisition

`validate_collection_set(document)` validates **everything** before `cmd_collect` submits anything:

- document `schemaVersion` and no unknown document fields (a URL cannot arrive at the document level
  either);
- `entries` is a non-empty list of at most `MAX_COLLECTION_ENTRIES`;
- **every entry through the existing `validate_spec()`** — one validation path, not two;
- **no duplicated `(sourceId, resourceId)`** — two entries for one stream share an idempotency key
  inside a window, so the second would be suppressed and the schedule would silently do less than
  the file says;
- **all entries agree on `collectionWindowSeconds`** — the installer checks one window against the
  cadence, and letting entries disagree would make that check meaningless and turn a bounded
  collector into a per-source rate scheduler nobody asked for.

**One bad entry refuses the whole window.** Nothing is skipped, nothing is guessed, nothing is
normalised into validity. A committed specification that is partly wrong is one nobody has actually
reviewed, and quietly executing the valid remainder would hide that. Order is asserted structurally:
`load → build → submit`, with a test proving the source reads in that order.

## 5. The maximum-request invariant

> **One window issues AT MOST ONE acquisition per committed entry.**

N is decided **entirely by the committed file**. There is no discovery, nothing is added at runtime,
and no link inside acquired content is ever followed. `MAX_COLLECTION_ENTRIES = 25` states the
ceiling as a number rather than leaving it to the file's length — at the six-hour cadence that is 100
requests/day against public metadata endpoints, and its real job is to stop a fat-fingered file from
quietly becoming a crawler.

The existing per-stream collection window still applies unchanged, so a repeated firing inside one
window remains one request per stream.

## 6. Order, identity and observability

**Processing order is committed file order** — deterministic, and reviewable: what you read is what
runs. Asserted stable across repeated validation.

**Each result keeps its own identity.** Every entry builds its own command with its own
`(sourceId, resourceId)` and its own idempotency key, so UNCHANGED, CHANGED and duplicate
suppression all stay per-stream — one entry can never suppress, advance or contaminate another's
history. Nothing is collapsed into an identity-less aggregate; the CLI prints each stream by name.

**One scheduler invocation, one process lock, one `run_once()`.** The orchestrator already executes
queued tasks sequentially under the lock it holds, so **no batch runner, worker pool, queue or retry
framework was added** — and none is wanted. The launchd model is untouched: still one job, still
`collect`, still 00:00/06:00/12:00/18:00.

## 7. Files changed and why

| File | Change |
|---|---|
| `platform/scheduling/approved-collection.json` | one entry → a set containing that same entry, byte-identical in content |
| `runtime/scheduled_collection.py` | **+`SET_SCHEMA_VERSION`, `MAX_COLLECTION_ENTRIES`, `validate_collection_set()`**. `validate_spec()` and `build_command()` **untouched** |
| `runtime/cli.py` | `load_approved_collection_spec` → `load_approved_collection_entries`; `cmd_collect` iterates |
| `platform/scheduling/mogo_schedule.sh` | installer reads one window from the set and refuses a set whose entries disagree |
| `tests/platform/test_runtime_scheduled_collection.py` | helper reads `entries[0]`; **+18 Step 3B fixtures** |

**No new module, class, batch framework, worker pool, concurrency layer, retry framework, scheduler
or queue.**

## 8. Current production compatibility

The committed set still contains **exactly one entry**, with the same `sourceId`, `resourceId`,
`authorizationId`, capability, connector, operation and `collectionWindowSeconds: 21600`.

Proved by test: a one-entry set builds a command whose **idempotency key and window are identical**
to the one the single-entry model built. Live `collect --dry-run`:

```
COLLECT WINDOW -- 1 approved entry, at most one acquisition each
  SRC|youtube|c785970cc458 / hb7ot1_szWI  operation=metadata
      window=W|21600|82710 (21600 s)
DRY RUN -- nothing was submitted, nothing was acquired
```

Installer preflight: `schedule 00:00,06:00,12:00,18:00 (cadence 21600s) · window 21600s ·
PREFLIGHT OK`.

## 9. Tests — 81 in the suite, 18 new, all passing

All 19 required proofs covered, including: one-entry set preserves behaviour; two entries → exactly
two distinct requests; N ∈ {1,2,3,5,25} → exactly N distinct keys, never more; the cap refuses N+1;
deterministic committed order; per-entry identity preserved through to the payload; streams never
share a request identity while a repeat inside one window still does; five malformed-entry shapes
each refuse the **whole** set; missing field, malformed document, unknown document field, duplicated
stream and disagreeing windows all refused; validation provably precedes submission; installer and
launchd model unchanged; and **no second real source authorized**.

**Multi-entry behaviour is proved entirely with local test-only entries** — a second *resource* under
the already-approved source. No educator was authorized to test that the collector can iterate.

## 10. Integrity results

| Gate | Result |
|---|---|
| Focused scheduling + connector + MOGO-017 + bridge | ✅ **228 / 228** |
| Platform suite | ✅ **23 suites · 990 tests · 0 failures · 0 errors** |
| Canonical gate | ✅ **19 suites · 1,160 fixtures · 1,160 passed · 0 failed** |
| **Protected ALEX drift** | ✅ **0** |
| Campaign C1 | ✅ **33 verified · 0 mismatched** · `VERIFIED` |
| Legacy corpus | ✅ **220 re-derived · 0 mismatched** |
| Immutable research evidence + Knowledge Library | ✅ byte-unchanged |
| Step 2 bridge | ✅ unchanged output, semantics untouched |
| Scheduler | ✅ plist template unchanged, 4 calendar entries, window `21600` |
| Approved sources | ✅ **exactly one**; committed set has **exactly one entry** |
| Acquisitions performed | ✅ **none** — `capability_results` still 7 rows |

## 11. Remaining work for Step 3C

1. **Authorization record** for the new educator (`mogo_runtime authorize`).
2. **Connector destination entry** — now declaring its **own** `resourceIdAlphabet` /
   `resourceIdLength` (Step 3A), not inheriting YouTube's.
3. **Attribution entry** in `source-attribution.json`, with its `sourceId` recomputed from the
   channel URL.
4. **A second entry** in the collection set — the shape is now ready; only the approval is missing.
5. **Verify** end to end: two streams, isolated histories, per-stream change detection, and no
   strategy-corpus contamination in the bridge.

**TJR first** — it already has a trader profile, `SF|TJR|SESSION_ZONE_REACTION`, committed evidence
and an `imports/tjr/` tree. ICT has a profile but **no strategy family**. CRT has nothing.

Still out of scope: transcript acquisition, discovery, concept modelling, corpus-maturity verdicts,
strategy reconstruction, promotion.

---

# ✅ STEP 3B CHECKPOINT — COMMITTED

| | |
|---|---|
| Reviewed | approved by ChatGPT/operator |
| **Checkpoint commit** | **`38ba14c1fcc807b771ccb6499ddc6793ba63a061`** |
| Commit message | `MOGO-018 Step 3B: bounded multi-entry autonomous collection` |
| Pushed to | `origin/mogo-main` |
| Starting checkpoint | `0414920081cb65c7ea5f10e9c6581a4f4f176a84` (Step 3A) |

Final pre-commit verification re-ran all twenty required checks: only the six intended files
changed; twelve report claims were spot-checked against the running code, including that
`validate_spec` and `build_command` still carry their original signatures; Step 3B scheduling (81),
MOGO-017 acquisition/change-detection (102), Step 2 bridge (29) and Step 3A authorization (118)
suites all green; platform 990/990; canonical 1,160/1,160; drift 0; C1 33/33; legacy corpus 220/0;
immutable research evidence and Knowledge Library evidence byte-unchanged; Step 2 bridge output
unchanged; plist template unchanged with four calendar entries; the production set still holds
exactly one entry and `approved_source_ids()` exactly one source; **no acquisition performed**
(`capability_results` still 7 rows); and a live sweep confirmed a URL is refused at **both** the
document and entry level, that unapproved/unauthorized entries refuse the **whole window**, and that
the connector gate itself still fails closed.

**No source was authorized. No acquisition was performed.**

**LIVE-MONEY TRADING REMAINS UNAUTHORIZED.**

---

# MOGO-018 STEP 3C — TJR AUTHORIZED AS THE SECOND APPROVED RESEARCH SOURCE

**Status: ✅ COMPLETE. Not committed — held for review.**
**PAPER TRADING ONLY — live-money trading remains unauthorized.**

## 1. Starting state

HEAD `e3707a5a1000dcab97180c68e07da69d80795823`, clean working tree, 0 ahead / 0 behind
`origin/mogo-main`.

**One naming discrepancy, reported rather than silently accepted.** The brief specified branch
`mogo-main`; the local branch is named **`main`** and *tracks* `origin/mogo-main`. Every substantive
check passed — correct repository, exact HEAD, clean tree, 0/0 against `origin/mogo-main` — and this
is the same configuration Steps 3A and 3B were committed and pushed from. Only the local label
differs.

## 2. The TJR identity — reused, never invented

**No channel URL, channel ID, video ID, traderId or strategy family was guessed.** Every identifier
below already existed in committed repository evidence before this step.

| What | Value | Where it already existed |
|---|---|---|
| traderId | `TJR` | `docs/trader-intelligence/traders/tjr/profile.json` |
| Strategy family | `SF\|TJR\|SESSION_ZONE_REACTION` | same profile + `strategy-families/session-zone-reaction.json` |
| Channel URL | `https://www.youtube.com/@TJRTrades` | `evidence/sources/EVSRC_TJR_20260727_002.json` |
| Resource (video) ID | `8qwEmE1DwYw` | same record (`youtubeVideoId`, `canonicalReference`) |
| Derived sourceId | `SRC\|youtube\|11cd2542b5b0` | computed by `ids.make_source_id` from the channel URL |

**Why that evidence record is strong enough to authorize against.** Its `titleVerification` block
records `method: youtube_oembed`, `status: verified_publisher`, `traderAttributionConfirmed: true`
and `verifiedScope: [title, channel/author, video identity]` — the publisher was confirmed through
**the same oEmbed endpoint this connector is authorized to call**. That is the identical corroboration
pattern Alex G had in MOGO-015 Step 1A.

**What the repository does NOT contain, and was therefore NOT claimed.** There is **no `UC…` channel
ID for TJR** anywhere in the repository. Alex G's registry entry carries one; the TJR entry
**omits the field** rather than invent a value. Nothing reads `channelId`, so the omission changes no
behaviour — and an unverified identifier inside an authorization boundary would have been a real
defect. `EVSRC|TJR|20260727|001` has a null `canonicalReference` and was therefore unusable; only
`…|002` grounds a resource.

## 3. Authorization additions — four, the number Step 3B predicted

| # | File | Change |
|---|---|---|
| 1 | `docs/trader-intelligence/authorizations/AUTH-tjr-metadata.json` | **NEW.** authorizationId `3008510b-6c34-4a46-ba26-1c90bb9c728a`, `PERMITTED_PUBLIC_METADATA`, `permittedOperations: ["metadata"]`, `decisionAuthority: operator:joemogollon` |
| 2 | `platform/src/mogo_platform/runtime/connector_authorization.py` | Second `APPROVED_DESTINATIONS` entry |
| 3 | `docs/trader-intelligence/library/source-attribution.json` | TJR → `TJR` / `SF\|TJR\|SESSION_ZONE_REACTION` |
| 4 | `platform/scheduling/approved-collection.json` | Second committed collection entry |

**The Alex G registry entry was not touched.** TJR's `urlTemplate` is written out in full rather than
factored into a shared constant — refactoring would have edited the incumbent's authorization line for
no behavioural gain. A test pins the **exact derived URL for both sources**, so the duplication cannot
drift unnoticed.

**Scope note carried in the record:** the archived TJR *transcript* is `restricted_third_party`, and
this authorization does not touch it. Only the public oEmbed metadata document for the one named
resource is authorized.

## 4. Per-destination resource rule — declared, not inherited

TJR declares its own `resourceIdAlphabet` (referencing `VIDEO_ID_PATTERN`) and `resourceIdLength: 11`.
TJR is also YouTube and legitimately uses the same shape, so it **declares the same rule explicitly**.

**Two entries agreeing on a rule does not make the rule global again.** Proved by test: stripping the
declaration from a copy of the TJR entry makes TJR accept **nothing** — including its own valid
identifier — while the real Alex G entry is completely unaffected.

## 5. Production collection set: one entry → two

```
SRC|youtube|c785970cc458 / hb7ot1_szWI   idempotencyKey=e21508a5…   (unchanged)
SRC|youtube|11cd2542b5b0 / 8qwEmE1DwYw   idempotencyKey=55223bec…   (new)
```

Both in window `W|21600|82710`. **`requests_this_window <= 2`.** `MAX_COLLECTION_ENTRIES` is still
25, the window is still 21600 s, and the launchd model is unchanged: **one job, one `collect`,
00:00 / 06:00 / 12:00 / 18:00 local**. No second job, no per-source scheduler, no cadence change.

## 6. Live end-to-end proof — REAL, through the governed path

`python3 platform/mogo_runtime.py collect` against the committed two-entry production configuration.
The scheduler was **not** accelerated and launchd was **not** modified.

```
CHANGE DETECTION UNCHANGED         (prior=b668d4209abb current=b668d4209abb)   ← Alex G
CHANGE DETECTION FIRST_OBSERVATION (prior=none         current=0cc6cf59e6d1)   ← TJR
advanced=6 succeeded=2 failed=0 retried=0 released=0 deadLettered=0
```

**This single output is the isolation proof.** Alex G had **seven** prior accepted observations at
that moment. TJR's first acquisition classified `FIRST_OBSERVATION` with **`prior=none`**. Had the two
streams shared a history, it would have been reported as `CHANGED` — a fabricated mutation.

| Property | Alex G | TJR |
|---|---|---|
| Authorization | ✅ permit | ✅ permit |
| Destination derived from registry | ✅ | ✅ |
| HTTP | 200 | 200, 829 bytes |
| Validation | ✅ | ✅ |
| Immutable artifact | `RART\|d4e4ec82…` (pre-existing, unchanged) | `RART\|8aa491b0…` (new) |
| Classification | `UNCHANGED` | `FIRST_OBSERVATION` |
| Strategy family | `SF\|ALEX_G\|SUPPORT_RESISTANCE_V1` | `SF\|TJR\|SESSION_ZONE_REACTION` |

### The provider independently corroborated the reused identity

The live oEmbed body matched committed evidence on **all three** identity fields:

| Field | Live response | Committed evidence | Match |
|---|---|---|---|
| `author_url` | `https://www.youtube.com/@TJRTrades` | same | ✅ |
| `author_name` | `TJR` | same | ✅ |
| `title` | `Path to Profitability: How to Read a Candlestick Chart` | same | ✅ |

The identity was not merely *assumed* correct — YouTube confirmed it.

## 7. Library bridge — both corpora, cleanly separated

```
entries : 2
  SRC|youtube|11cd2542b5b0 / 8qwEmE1DwYw
      trader=TJR      families=SF|TJR|SESSION_ZONE_REACTION      [ATTRIBUTED]
      artifact=RART|8aa491b01b883e8d0682e038a263417d
      accepted observations=1  distinct identities=1  last=FIRST_OBSERVATION
  SRC|youtube|c785970cc458 / hb7ot1_szWI
      trader=ALEX_G   families=SF|ALEX_G|SUPPORT_RESISTANCE_V1   [ATTRIBUTED]
      artifact=RART|d4e4ec829fe80b576a1304f46405f76a
      accepted observations=8  distinct identities=1  last=UNCHANGED

  SF|ALEX_G|SUPPORT_RESISTANCE_V1    streams=1 observations=8 identities=1
  SF|TJR|SESSION_ZONE_REACTION       streams=1 observations=1 identities=1
  lane=RESEARCH  promotionStatus=NOT_A_TRADING_RULE
```

Distinct artifacts, distinct content identities, no shared counts. The bridge remains **derived and
read-only** — it persists nothing and two reads are byte-identical.

## 8. Contamination / isolation proof

Proved in **both directions**, not once and assumed symmetric:

| Property | Proof |
|---|---|
| Alex G history cannot advance TJR's | live `FIRST_OBSERVATION prior=none` + fixture |
| TJR history cannot advance Alex G's | fixture: TJR mutates, Alex G still `UNCHANGED` |
| Reverse direction | fixture: Alex G mutates → `CHANGED`, TJR still `UNCHANGED` |
| A failure never advances a neighbour | fixture: refused TJR body never becomes a baseline |
| Dedupe is per stream | same window label under a different stream is a different request |
| No artifact crosses corpora | distinct `artifactId`, `artifactPath`, `authorizationId` |
| Attribution is explicit | a channel URL swapped under an unchanged sourceId **fails closed** |
| One source cannot borrow the other's URL | refused as `requested_url_does_not_match_approved_destination` |

**These tests are not vacuous — that was verified by mutation.** Collapsing `comparison_key()` so all
streams share one identity caused exactly the three cross-stream isolation tests to fail; the file was
then restored byte-for-byte.

## 9. Hash contract preserved

`connector_transport.content_hash` remains SHA-256 over the exact validated external response body
bytes. The bridge still emits `acceptedContentIdentity` + `acceptedContentIdentityBasis`
(`RAW_EXTERNAL_RESPONSE_BYTES`) and **never** a bare `contentHash` — asserted per entry for both
sources. Lane A transcript hashes were not touched or reinterpreted.

## 10. Files changed — 8

**Production (4)**
- `docs/trader-intelligence/authorizations/AUTH-tjr-metadata.json` *(new)*
- `platform/src/mogo_platform/runtime/connector_authorization.py`
- `docs/trader-intelligence/library/source-attribution.json`
- `platform/scheduling/approved-collection.json`

**Tests (3)**
- `tests/platform/test_runtime_two_source_isolation.py` *(new, 31 tests)*
- `tests/platform/test_runtime_connector_authorization.py`
- `tests/platform/test_runtime_scheduled_collection.py`

**Runner (1)**
- `tests/run_platform_tests.sh` — registers the new suite (it has an explicit suite list; without
  this line the new tests would have run only when invoked directly, and the platform total would
  have silently under-reported)

**Generated by the live proof, not authored (2, untracked):**
`intake/acquired/0cc6cf59….json` and `research-artifacts/8aa491b0….json` — genuine new TJR research
evidence.

## 11. Tests — 32 added, all 25 required proofs covered

Five pre-existing assertions changed, and **all five were "exactly one source / one entry"
statements** — precisely the invariant this step deliberately changes. **No behavioural test broke.**

The authorization-record obligation test was strengthened rather than merely re-pointed: with one
source it could compare a tuple, so it now **reads both committed records** and proves the set they
cover equals the set of approved sources. A third destination added without a record now fails there.

| Suite | Result |
|---|---|
| `test_runtime_two_source_isolation` *(new)* | ✅ 31 |
| `test_runtime_connector_authorization` | ✅ 36 |
| `test_runtime_scheduled_collection` | ✅ 82 |
| `test_runtime_change_detection_contract` | ✅ 54 |
| `test_runtime_change_detection_wiring` | ✅ 28 |
| `test_runtime_research_library` (Step 2 bridge) | ✅ 29 |

## 12. Integrity results

| Gate | Result |
|---|---|
| Focused Step 3C suites | ✅ **280 / 280** |
| Platform suite | ✅ **24 suites · 1,022 tests · 0 failures** (was 23 · 990) |
| Canonical gate | ✅ **19 suites · 1,160 / 1,160 · 0 failed** |
| **Protected ALEX drift** | ✅ **0** — 63 functions, 4 constants byte-identical |
| Campaign C1 | ✅ **33 / 33 verified · 0 mismatched** — read from the committed `C1_INTEGRITY_ATTESTATION.json`, which the canonical gate's `run_v128_evidence_platform_tests.js` loads and evaluates; attestation byte-unchanged |
| Legacy corpus | ✅ baseline byte-unchanged; rollup `667ff4c7…` **re-derived from the 220 committed package hashes and matches** — see the honesty note below |
| Runtime integrity (`verify`) | ✅ INTEGRITY OK |
| Existing immutable Alex G evidence | ✅ byte-unchanged (no modifications under `research-artifacts/`, `intake/`) |
| Knowledge Library evidence | ✅ byte-unchanged (`evidence/`, `traders/`, `imports/` all clean) |
| Campaigns / strategy-fidelity / `index.html` | ✅ untouched |
| Scheduler cadence | ✅ unchanged, plist template unchanged |
| Approved sources | ✅ **exactly two** |
| Committed collection entries | ✅ **exactly two** |
| Forward/research contamination | ✅ **0 both directions** |

### Honesty note on the legacy-corpus figure

Earlier steps reported "220 re-derived · 0 mismatched" as an integrity result. **I could not reproduce
that check the way the phrase implies, and I am not going to restate it as though I had.** What I
actually verified:

- `docs/evidence/EVIDENCE_BASELINE.json` is **byte-unchanged** by this step.
- It records `packagesRecovered: 220`, `verified: 220`, `mismatched: 0`.
- I **re-derived** its `hashRollup` — SHA-256 over the 220 committed package hashes joined by newline
  — and it reproduces `667ff4c7…` exactly. The baseline is internally consistent.

What I did **not** do: re-verify the 220 packages against evidence on disk.
`node scripts/mogo_evidence_verify.js --scan docs/evidence` finds **zero** packages and returns
`FAIL — an empty scan is not a pass`, because the evidence packages live in an ephemeral scratchpad
outside the repository (`docs/KNOWN_ISSUES.md`, and the canonical gate's own closing note). That is a
**pre-existing environmental condition, not a regression introduced by Step 3C** — the canonical gate
never re-derived that number either, so its output contains no "220" line. A reviewer should read the
legacy-corpus row as *"the committed baseline is untouched and self-consistent"*, not as *"220
artifacts were re-checked against disk today"*.

**Two platform-boundary failures were hit and fixed properly, not suppressed.** A comment I added to
the runtime cited the TJR evidence file *by path*, which contains the literal `evidence/` — a
prohibited scientific-corpus path in any runtime module. The rule is right; the comment was wrong. It
now cites the record **by identifier** (`EVSRC|TJR|20260727|002`) and the resolvable path lives only
in the authorization record and the attribution file, which are documents rather than runtime.

## 13. Scientific firewall

Zero impact on ALEX trading rules, parameters, protected functions, strategy version, the forward
activation cutoff `2026-08-11T02:43:57.894Z`, forward paper evidence, the genuine forward paper
campaign, Campaign C1, the legacy corpus, paper-trading execution logic or live-money trading
authority. The live forward browser was **not** reloaded or restarted, **no** paper trade was forced,
staleness limits were **not** changed and the campaign was **not** re-baselined.

**Attribution is organizational only.** That TJR material sits in the TJR corpus does **not** say TJR
is profitable, validated, accepted, ready for reconstruction, ready for backtesting or ready for paper
trading. No TJR rule was interpreted, reconstructed, hypothesised, backtested or blended into ALEX,
and no MOGO-derived strategy was created.

## 14. Remaining work for ICT / CRT expansion

1. **ICT** has a trader profile but **no strategy family** — one would have to be declared and
   reviewed before attribution is possible.
2. **CRT** has **nothing**: no profile, no family, no evidence, no imports tree.
3. **Neither has a channel URL or resource ID in committed evidence.** TJR was authorizable precisely
   because `EVSRC|TJR|20260727|002` carried an oEmbed-verified channel and video id. **Authorizing
   ICT or CRT today would require guessing an external destination, which must not happen** — the
   identity must be established and reviewed first.
4. The mechanism itself needs nothing further: a third source is now four reviewed edits.

Still out of scope: transcript acquisition, discovery, concept modelling, corpus-maturity verdicts,
strategy reconstruction, promotion.

## 15. Recommendation for the next MOGO-018 step

**Do not authorize a third educator next.** The two-source configuration is one collection window old
and its most interesting behaviour — an independent `CHANGED` on one stream while the other stays
`UNCHANGED` — has been proved in fixtures but not yet observed in production. Let the committed
schedule run and confirm the invariant holds unattended.

The higher-value next step is **corpus observability**: a read-only operator view answering "what does
MOGO hold per educator, how fresh is it, and what changed" from the derived bridge. That is
low-risk, needs no new authorization, and is the natural prerequisite before the corpus grows.

**ICT and CRT remain NOT AUTHORIZED. LIVE-MONEY TRADING REMAINS UNAUTHORIZED.**

---

## 16. Step 3C evidence verification (pre-commit, operator-directed)

The two files the live proof produced were **not** added on trust. Each was proven mechanically to be
the expected Step 3C TJR acquisition output — **65 checks, all passing**.

### The three classes of evidence, kept distinct

| Class | Files | Disposition |
|---|---|---|
| **Pre-existing committed evidence** | Alex G `RART\|d4e4ec82…`, `intake/acquired/b668d420…`, all Lane A Knowledge Library records | **byte-unchanged**; not touched by this step |
| **Newly generated Step 3C autonomous TJR evidence** | `intake/acquired/0cc6cf59….json`, `research-artifacts/8aa491b0….json` | verified below, **committed** per existing precedent |
| **Derived / read-only** | `source-attribution.json` (attribution input), the library bridge index | attribution is a reviewed input; the index persists nothing |

### The two new files

| | Path |
|---|---|
| Raw acquisition record | `docs/trader-intelligence/intake/acquired/0cc6cf59e6d12fc5add7e1b9ba8ebae4610cebc69c0f00bdb75859f73c43904f.json` |
| Research artifact | `docs/trader-intelligence/research-artifacts/8aa491b01b883e8d0682e038a263417d186c144ddce2c8a99a4bc8c6fc56b107.json` |

### Verification results

| # | Check | Result |
|---|---|---|
| 1 | Exact paths identified | ✅ |
| 2 | Traced to the creating event | ✅ one `capability_results` row, idempotencyKey `55223bec…` — the key the live `collect` printed; row → `intakeRef` → `artifactId` chain intact |
| 3 | sourceId is `SRC\|youtube\|11cd2542b5b0` | ✅ in the acquisition record, the connector decision and the artifact's `claimedSourceId` |
| 4 | resourceId is `8qwEmE1DwYw` | ✅ in the acquisition row and embedded in `claimedSourceUrl` |
| 5 | Matches the committed approved destination | ✅ `approvedUrl` == `requestedUrl` == `finalUrl` == the registry-derived URL; resource id appears exactly once |
| 6 | Provenance complete | ✅ intake, acquisition and provenance key sets are **identical to the Alex G precedent** |
| 7 | Authorization present and successful | ✅ `permit` / `connector_destination_permitted`, authorizationId `3008510b-…`, HTTP 200, `failureClass: null`, redirects not followed, within byte limit |
| 8 | `acquiredAt` / `decidedAt` | ✅ **null, matching the Alex G precedent exactly** — see the note below |
| 9 | Hash semantics | ✅ intake `contentHash` == SHA-256 of the raw external bytes; artifact hash is the **wrapper** hash and correctly **differs**; both filenames equal their hashes; `artifactId` == `RART\|` + first 32 hex |
| 10 | FIRST_OBSERVATION for the TJR stream | ✅ |
| 11 | No prior accepted TJR history | ✅ `priorContentIdentity: null` |
| 12 | Does not claim or inherit Alex G history | ✅ TJR's identity matches no Alex G identity; distinct authorizationId; no Alex G identifier appears anywhere in either file |
| 13 | No ALEX logic or trading state | ✅ no `ALEX`/`fxalexg`/`SUPPORT_RESISTANCE` token; no position/order/PnL/equity/balance/backtest/campaign state |
| 14 | No credential, token, secret, key or cookie | ✅ nine secret patterns, all clean |
| 15 | Applicable integrity checks | ✅ runtime `verify` **INTEGRITY OK**; platform corpus fingerprint tests green; Lane A validator `0 ERROR / 0 FATAL` |

### Two findings reported rather than smoothed over

**1. `claimedSourceTitle` is `null` on the TJR artifact; Alex G's says `"fxalexg — channel metadata"`.**
This is correct, not a defect. The field is populated from the command payload, and
`scheduled_collection.build_command()` emits only `sourceId`, `resourceId`, `authorizationId` and
`collectionWindow` — **the scheduler deliberately supplies no title**, because a title is a claim the
scheduler cannot make. Alex G's artifact carries one only because it was minted in **MOGO-015 Step 4**
(commit `28b838f`), before the scheduled path existed, and its content has not changed since, so no
new artifact has been minted for it. **Any artifact created by the scheduled path will have a null
title.**

**2. The artifact wrapper's provenance describes the INGEST step, not the acquisition step.**
Both the TJR and the Alex G artifacts carry `acquisitionPerformed: false`,
`networkAccessPerformed: false`, `originClass: OPERATOR_SUPPLIED_LOCAL_INTAKE` and a note reading
*"MOGO did not fetch this artifact; an operator supplied it."* For an autonomously acquired artifact
that reads as inaccurate. The true network provenance lives in the `intake/acquired/` record, which is
complete and correct; the wrapper is minted by `CAP|research|ingest-local-artifact`, which stamps its
own boilerplate. **This is pre-existing and identical on the approved Alex G artifact — it is not a
Step 3C regression**, and it is flagged here as a provenance-accuracy issue for a future step rather
than silently accepted. Nothing in Step 3C depends on those three fields.

### Retention policy — precedent followed, not invented

`git ls-files` confirms the Alex G equivalents are **tracked**
(`intake/acquired/b668d420….json`, `research-artifacts/d4e4ec82….json`, `193966d9….json`), and no
`.gitignore` rule covers either new file. Repository policy therefore treats governed acquisition
evidence as **canonical repository-managed immutable evidence**, and the two new TJR files are
committed on that precedent. (By contrast, the runtime state root `platform/runtime/` **is**
gitignored and stays untracked — that boundary is unchanged.)

### One side effect I caused and reverted

Running `scripts/trader_intelligence/validate_evidence.py` as part of check 15 **rewrote a tracked
file**, `docs/trader-intelligence/evidence/reports/integrity-report.json` — only its `generatedAt` and
`integrityReportId`; `findings` stayed `[]` and the summary stayed all-zero. That is a verification
artefact, not a Step 3C change, so it was reverted with `git checkout --`. The Knowledge Library tree
is byte-unchanged.

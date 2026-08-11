# MOGO Research Acquisition System — Architecture & Implementation Readiness Report

**Session:** MOGO Research Agent — architecture review · **Date:** 2026-08-04
**Repository state at review:** `f8004fe` (MOGO-004 architecture review), branch `main`, clean tree
**Status:** **Review only. Nothing implemented. No code, schema, storage, or strategy logic modified.**

> **Scope discipline.** This report was produced by a session whose sole remit is the research
> acquisition system. It does not touch, recommend changes to, or contend for the same working files
> as any active MOGO development. The two live workstreams it must not collide with are the
> **MOGO-004 pilot replay** (browser work, `index.html`, evidence packages) and the **ALEX rule-to-
> evidence join**. Neither is referenced by anything proposed here.

---

## 0. The one-paragraph answer

MOGO does not need a research acquisition system built. **It already has one — minus exactly one
piece.** Eleven of the fourteen components named in the brief exist today as tested Python tooling
with committed schemas and a real 12-source corpus behind them. The missing piece is the
network-facing half: **Source Discovery and Source Acquisition**. That half is missing *deliberately*
— `DECISION|MOGO|20260725|002` chose a "fully offline, zero-network queue foundation, with all
connectors explicitly deferred," and a permanent test (`test_no_banned_imports_in_any_acquisition_script`)
enforces it. So the real deliverable of this report is not an architecture for a new system. It is a
**design for closing one deliberately-left gap without destroying the property that made leaving it
safe** — plus a hard finding about what can and cannot actually be retrieved, and a blunt correction
to the TJR pilot's stated objective.

---

## 1. Repository findings

### 1.1 What was read and verified

Inspected: `docs/ARCHITECTURE.md` · `docs/MOGO-004-PLAN.md` · `docs/reports/MOGO-004-ARCHITECTURE-REVIEW.md`
(Parts I–IX) · the full `docs/trader-intelligence/` tree · `README.md`, `SPEC-provenance.md`,
`OPERATOR-PLAYBOOK.md`, `STANDARDS-extraction.md`, `RESEARCH-LOG.md`, `KNOWLEDGE-DASHBOARD.md` ·
`acquisition/README.md` and all four acquisition schemas · all 18 evidence schemas · all six
`OwnerDecision` records · `BACKLOG-002-tjr-source-acquisition.md` · `docs/SECURITY.md` · `.gitignore` ·
`tests/trader_intelligence/acquisition/test_acquisition.py` · `scripts/trader_intelligence/transcript_adapters.py`.

Measured mechanically, not taken from a claim:

| Measure | Value |
|---|---|
| Tracked files | 8,347 (8,054 JSON, 143 Markdown, 58 Python) |
| Research tooling modules | **36** Python files in `scripts/trader_intelligence/` |
| Evidence schemas | 18 · acquisition schemas 4 · graph schemas 6 · Wave-1 schemas 12 |
| Knowledge Graph | 2,422 nodes · 5,109 edges |
| Registered sources / educators | **12 / 5** (ALEX_G 9, TJR 2, RAYNER_TEO 1, ICT 0, JVM 0) |
| Claims / evidence items / segments | 341 / 416 / 197 |
| Hypotheses / gaps / open questions | 641 / 110 / 281 (261 blocking) |
| Open contradictions | 16 |
| Lifecycle events recorded | 4,472 |
| Rule candidates / `StrategyRule`s promoted | **0 / 0** |
| Claims above `emerging` confidence | **0 of 341** |
| **Registered acquisition candidates** | **0** |
| Acquisition test coverage | 57 tests in one module |

### 1.2 The finding that shapes everything else

**The acquisition engine is built, tested, documented — and has never been used.**
`docs/trader-intelligence/acquisition/candidates/` contains zero files. Every one of the 12 sources in
the library entered by the owner hand-carrying a transcript into `intake/pending/`. The prioritization
engine, the 9-dimension weight profile, the duplicate detector, the 18-state lifecycle and the
deterministic queue have never scored a single real candidate.

This is not neglect. It is the direct consequence of §1.3: an acquisition queue that cannot acquire
has nothing to queue. The candidate registry is the pipeline segment immediately *downstream* of the
one capability that was never built, so it starved.

### 1.3 The gap is constitutional, not accidental

`docs/trader-intelligence/acquisition/README.md` states the boundary in normative language:

> It may not: acquire content from the network, download videos/transcripts, scrape websites, call
> external APIs, run browser automation…

`DECISION|MOGO|20260725|002` (`decisionType: acquisition`, `status: active`) selected this from three
options, rejecting *"Implement Phase 1A–1D now plus one YouTube metadata connector immediately."* The
rule is machine-enforced: `TestNoNetworkImports` bans `urllib.request`, `http.client`, `requests`,
`socket`, `yt_dlp`, `ftplib`, `smtplib` across seven named acquisition modules, and the two evidence
suites extend the same ban (plus `selenium`, `playwright`) to their own modules.

**Any design that adds network capability to those files fails a committed test and reverses a
standing owner decision.** The architecture in §3 is built around not doing that.

### 1.4 The lifecycle already has the slot cut

`acquisition-status.schema.json` defines 18 states. Three of them —
`ACQUISITION_IN_PROGRESS`, `ACQUIRED`, `ACQUISITION_FAILED` — **are unreachable today**, along with the
transition `APPROVED_FOR_ACQUISITION → ACQUISITION_IN_PROGRESS`. The state machine was designed in
anticipation of exactly this milestone and left the socket empty. Nothing in §3 invents a lifecycle;
it fills three states that already exist and are already validated by `acquisition_common.ALLOWED_TRANSITIONS`.

### 1.5 Governance already resolved the two questions that usually block acquisition

- **Licensing is not a gate.** `DECISION|MOGO|20260727|005`: licensing does not block internal
  research, extraction, or evidence storage; redistribution and public reproduction are prohibited;
  full attribution is preserved. `BACKLOG-002`'s standing constraint C-1 ("do not ingest before
  licensing is resolved") **predates and is superseded by** that decision — a live inconsistency in
  the corpus, flagged in §11 (R7).
- **Educator equality is ratified.** `DECISION|MOGO|20260727|004` — every educator is an equal
  evidence source. Acquisition is therefore a multi-educator activity by charter, not a TJR project
  that later generalizes.

### 1.6 Test baseline

`tests/run_all.sh` (JavaScript engine, 943 fixtures) is reported green at `f8004fe` and is untouched by
anything here.

The five trader-intelligence Python suites were **re-run during this review**:

```
python3 -m unittest tests.trader_intelligence.test_graph
  tests.trader_intelligence.acquisition.test_acquisition
  tests.trader_intelligence.evidence.{test_evidence,test_phase1b,test_phase7a}
→ Ran 307 tests in 260.6s — FAILED (failures=4)
```

**4 failures, down from the 6 the MOGO-004 review found** — `9903297` ("Test fixtures: scratch
evidence-tree isolation") closed a subset. Every remaining failure is the same class the review
named: assertions that the production graph contains *no* `EVIDENCE_QUESTION` / `HYPOTHESIS` nodes,
which expired the moment real data was ingested (e.g.
`test_production_graph_unchanged_without_real_knowledge_library`, failing on 773–815 legitimately
present nodes). **These are not application defects**, but a suite that fails by design will mask a
real failure. The three suites the MOGO-004 review counted but this session did not run
(`knowledge_engineering`, `strategy_fidelity`) were out of scope here; the review recorded 2 further
failures in `test_knowledge_engineering` of the same expired-count class.

**Baseline must be green before, not during, any implementation milestone** — see Step 0 in §13.

---

## 2. Existing reusable components

Mapping the brief's fourteen required components onto what exists:

| # | Required component | Status | Where it lives |
|---|---|---|---|
| 1 | Research Orchestrator | 🟡 **Partial** | `ingest.py` orchestrates intake→graph end-to-end; nothing orchestrates *acquisition* |
| 2 | **Source Discovery** | 🔴 **Absent** | — |
| 3 | **Source Acquisition** | 🔴 **Absent** | — |
| 4 | Transcript Processing | ✅ **Built** | `transcript_adapters.py` (3 formats), `transcript_normalize.py` (reversible, per-line asserted) |
| 5 | Document Processing | 🟡 **Partial** | Plain text / timestamped / JSON only. **No PDF, no HTML article, no chart image.** |
| 6 | Structured Claim Extraction | ✅ **Built** | `extraction_pipeline.py`, `annotation_pipeline.py`, `STANDARDS-extraction.md`; judgment step deliberately manual |
| 7 | Provenance Tracking | ✅ **Built, best-in-class** | `SPEC-provenance.md` — 15 invariants, 4 machine-enforced; `--verify-provenance` already caught a real drift |
| 8 | Duplicate Detection | ✅ **Built** | `detect_duplicates.py` + `ingest.py` dual-key check (`contentHash` **and** `canonicalReference`) |
| 9 | Contradiction Detection | ✅ **Built** | `contradiction-record.schema.json`, 16 open records, retained forever |
| 10 | Human Review | ✅ **Built** | `review_queues.py`, 325 entries, `OwnerDecision` gate on every authority-granting transition |
| 11 | Knowledge Packaging | ✅ **Built** | `strategy_blueprint.py`, `knowledge_library_report.py`, `build_knowledge_dashboard.py` |
| 12 | MOGO Ingestion | ✅ **Built** | `ingest.py --apply`, fail-closed `--dry-run`, `--rollback` |
| 13 | Audit Logging | ✅ **Built** | 4,472 `evidence/lifecycle/` events; `changeLog` on every candidate |
| 14 | Security | 🟡 **Partial** | Input-safety is strong (null-byte rejection, no `eval`/`exec`/`pickle`, XSS-inert storage verified by test). **Network-egress security does not exist because egress does not exist.** |
| 15 | Rate Limiting | 🔴 **Absent** | Nothing to rate-limit today |
| 16 | Research Campaign Management | 🟡 **Partial** | `governance/REPLAY-CAMPAIGN-PLAN.md` and `RESEARCH-ROADMAP.md` manage *replay* campaigns; no *acquisition* campaign entity |

**Score: 8 built, 4 partial, 3 absent (all three network-side).** The correct framing for any milestone
plan is *"connect a built system to the outside world,"* never *"build a research system."*

### 2.1 Directly reusable, no modification

`acquisition_common.py` (URL normalization, ID generation, transition validation) · the four
acquisition schemas · the 9-dimension priority profile · `register_source.py` · `detect_duplicates.py` ·
`prioritize_sources.py` · `build_research_queue.py` · `validate_acquisition.py` · the entire
evidence/graph stack downstream of `intake/pending/`.

---

## 3. Architecture proposal

### 3.1 The governing idea: the Collector is outside the wall

```
┌──── UNTRUSTED / NETWORK ZONE ────┐        ┌──── TRUSTED / OFFLINE ZONE (unchanged) ────┐
│                                  │        │                                            │
│   scripts/research_collector/    │        │   scripts/trader_intelligence/             │
│   ───────────────────────────    │        │   ─────────────────────────────            │
│   • discover.py   (network)      │        │   • register_source.py     ┐               │
│   • fetch.py      (network)      │        │   • detect_duplicates.py   │ no-network    │
│   • ratelimit.py                 │  ═══>  │   • prioritize_sources.py  │ test still    │
│   • compliance.py                │  file  │   • build_research_queue.py│ passes,       │
│                                  │  drop  │   • ingest.py              │ unmodified    │
│   Writes ONLY to:                │  only  │   • …26 more               ┘               │
│     inbox/<batch>/…              │        │                                            │
│     inbox/<batch>/acquisition-   │        │   Reads inbox/ as ordinary untrusted files  │
│       record.json                │        │   exactly as it reads intake/pending/ today │
└──────────────────────────────────┘        └────────────────────────────────────────────┘
```

**One rule makes the whole design safe:**

> **No module that can reach the network may ever write to `docs/trader-intelligence/`, and no module
> that writes there may ever import a network library.** The two sets are disjoint, enforced by two
> mirror-image tests.

The Collector's *only* output is a directory of files plus a manifest. It creates no evidence, no
claim, no candidate record, no graph node. It cannot. It has no import path to `evidence_common.py`
and no write path into the corpus. The existing `TestNoNetworkImports` continues to pass **verbatim,
with no test weakened and no owner decision reversed** — `DECISION|MOGO|20260725|002` constrained the
acquisition *queue*, and the queue stays exactly as constrained.

This is the same pattern the repository already uses successfully: the research subsystem may read
`index.html` but nothing in the application reads the research subsystem — a one-directional boundary,
test-enforced. §3.1 applies it one layer further out.

### 3.2 Components (V1)

| Component | Module | Responsibility | Network |
|---|---|---|---|
| **Campaign Manager** | `campaign.py` | Declares a dated, hashed `ResearchCampaign`: targets, gap IDs it exists to close, source budget, stopping rule, and the **negative-result condition**. Written *before* collection. | No |
| **Discovery** | `discover.py` | Enumerates candidate video IDs from a channel or playlist URL. Emits IDs only. | Yes |
| **Metadata Resolution** | `resolve.py` | Per ID, resolves authoritative title / channel / canonical author URL via the oEmbed contract. | Yes |
| **Compliance Gate** | `compliance.py` | `robots.txt` check, allowlist enforcement (only hosts named in the campaign), refusal to fetch anything not on the approved list. Fails closed. | Yes (robots only) |
| **Rate Limiter** | `ratelimit.py` | Fixed floor delay between requests, per-host concurrency of 1, per-run request cap declared in the campaign, exponential backoff on non-200. | — |
| **Acquisition Record writer** | `record.py` | Writes one `AcquisitionRecord` per attempt — success *or* failure — with request URL, HTTP status, byte count, SHA-256, retrieval timestamp, method, and tool version. | No |
| **Handoff** | `inbox/` | Byte-preserved artifact + `acquisition-record.json`. Nothing else crosses. | No |

### 3.3 What is deliberately **not** in the Collector

No headless browser. No `yt-dlp`. No audio download. No transcription. No login, cookie, or session
handling. No CAPTCHA solving. No proxy rotation, UA rotation beyond one honest static string, or any
other technique whose purpose is to appear to be a different client than it is. If a source cannot be
retrieved by an honest, rate-limited, robots-respecting GET, **the correct output is a recorded
negative result**, not a workaround. This is stated as architecture, not as a preference, because the
first workaround is the one that makes every later one arguable.

### 3.4 Human review is unchanged and remains the only path to authority

`APPROVED_FOR_ACQUISITION` and `APPROVED_FOR_RESEARCH_INTAKE` still require an active `OwnerDecision`.
The Collector runs **between** them:

```
PRIORITIZED → OWNER_REVIEW → [OwnerDecision] → APPROVED_FOR_ACQUISITION
                                                      ↓  ← Collector starts here
                                          ACQUISITION_IN_PROGRESS
                                                      ↓
                                    ACQUIRED  |  ACQUISITION_FAILED
                                                      ↓  ← Collector stops here
                                          APPROVED_FOR_EXTRACTION → … → ingest.py
```

The Collector can never move a candidate into or out of an owner-gated state. It transitions only the
three states between two owner gates, and `ACQUISITION_FAILED → APPROVED_FOR_ACQUISITION` (retry)
already requires a **fresh** `OwnerDecision` per the committed schema comment.

---

## 4. Data flow

```
 (0) CAMPAIGN DECLARED                          campaigns/CAMPAIGN-<id>.json  [dated, hashed]
        │                                       targets · gap IDs · budget · stopping rule
        ▼
 (1) DISCOVERY            discover.py ──net──►  channel/playlist URL → {videoId…}
        │                                       writes nothing to the corpus
        ▼
 (2) METADATA RESOLUTION  resolve.py  ──net──►  oEmbed per ID → title, author_name, author_url
        │
        ▼
 (3) CANDIDATE REGISTRATION                     register_source.py --from-batch <inbox/…>
        │                 (offline zone)        discoveryMethod: CHANNEL_URL | PLAYLIST_URL
        │                                       storagePolicy: METADATA_ONLY
        │                                       metadataConfidence: verified (oEmbed-resolved)
        ▼
 (4) DUPLICATE DETECTION  detect_duplicates.py  canonical video key vs. all 12 registered sources
        │                                       + all prior candidates
        ▼
 (5) PRIORITIZATION       prioritize_sources.py 9 positive dims · 5 penalty dims · deterministic
        │
        ▼
 (6) QUEUE                build_research_queue.py → queue-snapshot.json
        │
        ▼
 (7) ═══ OWNER REVIEW ═══ OwnerDecision required. Nothing proceeds without it.
        │
        ▼
 (8) CONTENT ACQUISITION  fetch.py   ──net──►  compliance gate → rate limiter → GET
        │                                      byte-preserved artifact + AcquisitionRecord
        │                                      on failure: AcquisitionRecord with reason, status
        ▼                                      ACQUISITION_FAILED — a recorded finding, not an error
 (9) HANDOFF                                   inbox/<batch>/ → intake/pending/
        │
        ▼
(10) EXISTING PIPELINE    ingest.py <file> --trader X --url …
        │                 hash · dual-key dedupe · raw archive · reversible normalize · segment
        ▼
(11) EXTRACTION (manual judgment — unchanged, deliberately not automated)
        ▼
(12) ingest.py --apply → evidence · claims · links · contradictions · questions
        ▼
(13) graph rebuild · integrity validation · dashboard · ═══ OWNER REVIEW ═══
```

**Steps 0, 1, 2 and 8 are new. Steps 3–7 and 9–13 exist and run unmodified.**

---

## 5. Evidence model

Every field the brief requires is checked against what the corpus can already store:

| Required field | Exists? | Where |
|---|---|---|
| Unique ID | ✅ | `candidateId`, `sourceId`, `intakeId` |
| Original URL | ✅ | `url` + `normalizedUrl` (candidate); `canonicalReference` (source) |
| Source platform | ✅ | `platform` enum (6 values) |
| Creator | ✅ | `creatorName`, `channelOrPublisher`, `claimedTraderId`, `verifiedTraderId` |
| Publication date | ✅ | `publicationDate` |
| Retrieval date | 🟡 | `acquiredAt` exists but is unpopulated and unverified — no acquisition ever occurred |
| **Retrieval method** | 🔴 | **Missing.** `discoveryMethod` records how it was *found*, never how it was *fetched* |
| Strategy association | ✅ | `strategyFamilyCandidates`, `strategyFamilyId` |
| Transcript source | ✅ | `transcriptReference`, `provider` (`youtube_auto_caption_copy`) |
| File hash | ✅ | `contentHash` (candidate, source, intake, evidence) + `textHash` (segment) + `.sha256` sidecars |
| Review status | ✅ | `ownerReviewStatus`, `processingStatus` |
| Approval status | ✅ | `acquisitionStatus` (18 states) + `ownerDecisionIds` |
| Citation locations | ✅ | `sourceLocator` → `TranscriptSegment` → line range → normalization map → raw byte offset |
| Credibility classification | ✅ | `authenticityStatus` (7) · `metadataConfidence` (4) · `provenanceStatus` (3) · four separate confidence dimensions |
| Duplicate relationships | ✅ | `duplicateStatus` (8) · `canonicalCandidateId` · `relatedCandidateIds` |
| Contradiction relationships | ✅ | `ContradictionRecord`, retained permanently |

**Delta required: one new schema and one populated field.** Not a new evidence model.

### 5.1 `AcquisitionRecord` — the single new entity

One record per retrieval attempt, success or failure. Immutable. Written by the Collector into
`inbox/`, copied into the corpus by `register_source.py` in the offline zone.

```jsonc
{
  "acquisitionId":     "ACQ|TJR|20260804|001",
  "candidateId":       "CAND|…",
  "campaignId":        "CAMPAIGN|TJR|20260804|001",
  "requestUrl":        "https://…",
  "retrievalMethod":   "HTTP_GET_OEMBED",   // enum, see below
  "retrievedAt":       "2026-08-04T…Z",
  "httpStatus":        200,
  "bytesReceived":     11900,
  "contentSha256":     "c4901808…",
  "contentType":       "text/plain",
  "outcome":           "SUCCESS",           // SUCCESS | EMPTY_BODY | BLOCKED | NOT_FOUND | RATE_LIMITED | REFUSED_BY_COMPLIANCE
  "complianceCheck":   { "robotsAllowed": true, "hostAllowlisted": true, "checkedAt": "…" },
  "collectorVersion":  "research_collector 0.1.0",
  "userAgentSent":     "…",
  "notes":             null
}
```

`retrievalMethod` enum (V1): `HTTP_GET_OEMBED` · `HTTP_GET_HTML` · `HTTP_GET_FILE` ·
`OWNER_SUPPLIED_FILE` · `OWNER_SUPPLIED_PASTE`. The last two exist so that **every one of the 12
existing sources can be retroactively described** rather than left as a null-provenance special case.

**Why `outcome` matters more than it looks.** `EMPTY_BODY` and `BLOCKED` are first-class successes of
the *record*, not failures of it. `BACKLOG-002`'s A1-STOP entry already establishes the principle:
*"Accept the negative result if it comes… record that as a finding and stop looking."* Today there is
nowhere to write that finding. The `AcquisitionRecord` is that place.

---

## 6. Storage layout

Two new trees. Neither overlaps any existing path, so no active session can collide with this work.

```
scripts/research_collector/            ← NEW · the only network-capable code in the repository
  README.md                              constitutional boundary, mirror of acquisition/README.md
  campaign.py  discover.py  resolve.py  fetch.py
  compliance.py  ratelimit.py  record.py

docs/trader-intelligence/acquisition/
  campaigns/                           ← NEW
    CAMPAIGN-<traderId>-<date>-<n>.json      authoritative, dated, hashed at declaration
    reports/<campaignId>-yield.json          generated
  inbox/                               ← NEW · the airlock, gitignored except manifests
    <batchId>/
      acquisition-record.json                → copied into records/ by the offline zone
      <artifact files>                       → moved to intake/pending/ by the operator
  records/                             ← NEW
    ACQ-<...>.json                           authoritative, immutable, one per attempt
  schema/
    acquisition-record.schema.json     ← NEW
    research-campaign.schema.json      ← NEW
    (4 existing schemas unchanged)
  candidates/  queue/  reports/  weights/     unchanged
```

`.gitignore` additions: `docs/trader-intelligence/acquisition/inbox/**` **except**
`acquisition-record.json`. Rationale: retrieved third-party bytes must not be committed before the
`storagePolicy` decision is made per candidate (`DECISION|MOGO|20260727|005` permits internal storage
but prohibits redistribution, and this repository's history is a distribution channel). The *record*
of the retrieval is always committed; the *content* is committed only under an explicit
`COMMITTED_OWNER_CONTENT` or `REFERENCED_LOCAL_CONTENT` decision, exactly as the existing storage
policy specifies.

---

## 7. Review workflow

Four gates. Three already exist; one is new and is the cheapest of the four.

| Gate | When | Artifact | Exists? |
|---|---|---|---|
| **G1 — Campaign approval** | Before any network request | `ResearchCampaign` + `OwnerDecision` (`decisionType: acquisition`) | **New** |
| **G2 — Acquisition approval** | Per candidate, after prioritization | `OwnerDecision` → `APPROVED_FOR_ACQUISITION` | ✅ Exists, unreachable today |
| **G3 — Intake approval** | Before evidence is created | `OwnerDecision` → `APPROVED_FOR_RESEARCH_INTAKE` | ✅ Exists |
| **G4 — Extraction judgment** | Per annotation | Manual manifest edit; `--dry-run` fail-closed | ✅ Exists |

**G1 is the only new gate and it is where the honesty lives.** A campaign declares, before any bytes
move, what it is trying to close and what would constitute failure. Without it, "we searched and found
nothing useful" is indistinguishable from "we did not search," and the corpus has no way to record the
difference. This is the acquisition-side analogue of the pre-registration file that Part IX of the
MOGO-004 review identified as the one thing that is *physically impossible to do later*.

**What the agent may never do, restated against this design:** it cannot change a strategy rule
(none exist to change — `StrategyRule` count is 0 and promotion is human-only), cannot modify replay
or paper trading (no import path, and all four replay functions are inside the 63 protected functions),
cannot approve a strategy or profitability (`performanceConfidence` cannot be inferred from source
material by rule 5 of the framework charter), cannot enable live trading, and cannot bypass review
(the three states it may transition sit strictly between two `OwnerDecision` gates).

---

## 8. Security considerations

| # | Concern | Control |
|---|---|---|
| S-1 | **Network code reaching the corpus** | Two mirror tests: no `trader_intelligence/*` module imports a network library (existing, unchanged); no `research_collector/*` module imports `evidence_common`/`graph_common` or opens a path under `docs/trader-intelligence/` other than `acquisition/inbox/` (new) |
| S-2 | **Retrieved content is untrusted input** | Already handled: null-byte rejection, no `eval`/`exec`/`pickle` anywhere in the pipeline, and a committed test proving a malicious payload is stored verbatim as inert text and never executed. Extend byte-cap and content-type allowlist at fetch time |
| S-3 | **Credential exposure** | The Collector takes **no credentials of any kind**. No API keys, no OAuth, no cookies. If a source needs authentication, it is out of scope by design, not by omission. `.gitignore` already excludes `.env` |
| S-4 | **Committing third-party content** | `inbox/**` gitignored except the record; content commits only under an explicit per-candidate `storagePolicy` (`DECISION|MOGO|20260727|005` prohibits redistribution) |
| S-5 | **Server-side abuse / rate** | Fixed floor delay, per-host concurrency 1, per-run request cap declared in the campaign and enforced fail-closed, exponential backoff, honest static UA, robots respected |
| S-6 | **Path traversal from remote-derived filenames** | Filenames are generated from `candidateId`, never from a URL, `Content-Disposition`, or page title |
| S-7 | **Silent corpus mutation** | The Collector has no write path into `docs/trader-intelligence/` outside `inbox/`; the operator physically moves files across the airlock |
| S-8 | **Non-repudiation of what was fetched** | Every attempt writes an `AcquisitionRecord` with URL, status, bytes, and hash — including refusals |

**Not addressed, stated plainly:** this design does not protect against a compromised local machine
(consistent with `SECURITY.md`'s existing threat model), and it does not verify that a retrieved
transcript is a faithful rendering of the actual audio — that remains `provenanceStatus:
partially_verified` and is a limitation of the medium, not of the tooling.

---

## 9. Version 1 scope

### 9.1 The retrieval reality — verified during this review

Three read-only probes were run against public endpoints (the oEmbed call is already documented in
`OPERATOR-PLAYBOOK.md` Stage 0 as standard operator procedure):

| Probe | Result | Consequence |
|---|---|---|
| **oEmbed** `?url=…&format=json` | **200, full payload** — title, `author_name`, `author_url` | ✅ Metadata resolution is reliable and contract-backed. This is the strongest primitive available |
| **Channel page** with browser UA | **200, 1,189,939 bytes**, 30 `videoId`s extractable | 🟡 Discovery works — but the page now uses `lockupViewModel`, not the older `videoRenderer`. Titles, publish dates and durations are **not** at the paths a 2024-era parser would look for. **The renderer schema has already changed once.** |
| **Caption endpoint** `api/timedtext` | **HTTP 200 with 0 bytes** | 🔴 **Transcript bodies are server-blocked.** Not an error to handle — a deliberate, silent refusal |

**These three results determine V1 more than any design preference.** The honest statement is:

> **MOGO can automate discovery and metadata acquisition today. It cannot automate transcript-body
> acquisition.** Transcript bytes will continue to arrive by owner-supplied paste, exactly as all 12
> existing sources did.

A V1 that promised automatic transcript collection would be a V1 that fails on contact. The
mitigation is not a workaround (§3.3) — it is to build the half that works and record the other half
as a measured constraint.

The `lockupViewModel` finding also sets the parsing rule: **extract the 11-character video ID with a
tolerant regex and nothing else from HTML; resolve every other field through oEmbed.** Video IDs are
structurally stable; renderer JSON is not. A discovery module that parses titles out of HTML will
break silently and start producing wrong educator attributions — which, under
`DECISION|MOGO|20260727|006`, silently changes the confidence arithmetic for every claim in the source.

### 9.2 V1 scope

**In:**
1. `ResearchCampaign` schema + declaration tool (offline).
2. `AcquisitionRecord` schema + writer.
3. Discovery: channel and playlist URL → video IDs.
4. Metadata resolution via oEmbed → verified title, channel, canonical author URL.
5. Compliance gate (robots + host allowlist) and rate limiter.
6. Batch registration bridge: `inbox/` → `register_source.py` as `METADATA_ONLY` candidates.
7. Retroactive `AcquisitionRecord`s for all 12 existing sources (`OWNER_SUPPLIED_*`).
8. Mirror-image boundary tests (S-1) and a fixture-only test suite — **no network in CI, ever**.

**Out of V1 (deferred, §10):** every non-YouTube platform, every content type other than metadata,
PDF/HTML/image processing, search-engine discovery, scheduling/automation, and anything requiring
authentication.

**V1 delivers:** the ability to say *"here are the 30 videos on this channel, here are their verified
titles and educator attributions, here is which are already in the library, here is the priority
ranking, and here is what closed or failed to close each declared gap"* — with a permanent, auditable
record of every request made. That is a real capability MOGO does not have today and would use on the
next acquisition cycle.

---

## 10. Deferred capabilities

Each with the specific observation that would justify revisiting it — following Part VIII/IX practice,
because a deferral without a trigger is just a wish.

| Deferred | Why it waits | Trigger |
|---|---|---|
| PDF processing | Zero PDFs referenced anywhere in the corpus | The first candidate registered with `platform: PDF` |
| HTML article extraction | Zero article sources in 12 | The first `ARTICLE_URL` candidate approved for acquisition |
| TradingView / GitHub / academic connectors | No candidate of any of these types has ever been registered | A campaign declares one as a target and the owner approves it |
| Chart-image acquisition | The corpus already records that this educator's parameters are *shown, not spoken* (`BACKLOG-002` A2-LIVE) — but images need OCR/vision, which is a different instrument entirely | The owner decides the numbers behind the visuals are worth a separate project |
| Search-engine discovery | `SEARCH_RESULTS_URL` exists as a discovery method and has never been used once. Search introduces relevance ranking — an editorial judgment — into a pipeline whose whole design keeps judgment human and explicit | Channel/playlist enumeration proves insufficient to find declared targets |
| Scheduling / continuous monitoring | Continuous acquisition against a corpus whose binding constraint is *not* volume (§11 R1) manufactures work | A campaign's stopping rule is reached and more material would demonstrably change an answer |
| Automated transcription (audio→text) | Would produce a transcript whose fidelity to the audio is machine-asserted rather than owner-asserted — a *weaker* provenance claim than today's, presented as a stronger one | Never, without an explicit owner decision on how machine transcripts are marked in `provenanceStatus` |
| Headless browser | §3.3. It is the workaround that makes every later workaround arguable | Never in this design. A different design, explicitly authorized |

---

## 11. Risks

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| **R1** | **The pilot's stated objective is unachievable as written.** Under `DECISION|MOGO|20260727|006` all TJR material shares one independence group, so **no quantity of TJR sources can raise any TJR claim above `emerging`.** This is not a prediction: cycles 006–007 ingested three sources and produced **zero confidence movement**, and the dashboard shows all 341 claims still at `emerging` | 🔴 **Highest** | Re-specify the pilot's objective (§12, §13). Deliver gap closure and testability, not confidence. **Do not let "more TJR material" be measured as success** |
| **R2** | **Automation produces volume against a constraint that is not volume.** MOGO-004's review found the binding constraint stopped being knowledge around ingestion #4. An acquisition system that works perfectly will make 641 untestable hypotheses into 900 untestable hypotheses | 🔴 High | The campaign's stopping rule and negative-result condition (G1) are the control. A campaign that closes no declared gap **stops**, and that is a success of the gate |
| **R3** | **Discovery parser breaks silently and misattributes an educator.** The renderer schema has already changed (`videoRenderer` → `lockupViewModel`). A wrong `author_name` changes the independence group and silently corrupts the confidence arithmetic | 🔴 High | IDs from HTML, everything else from oEmbed (§9.1). Parser emitting zero IDs is a **hard failure**, never an empty result |
| **R4** | **Network code drifts into the trusted zone** over time, one convenience import at a time | 🔴 High | The two mirror tests (S-1) are the entire safety property. They must be written first and must fail loudly |
| **R5** | **Scope collision with the MOGO-004 pilot replay.** Both are "MOGO research work"; only one has replay authorization | 🟠 Medium | Zero file overlap by construction (§6). Both can proceed in parallel. This work is a good use of any period during which replay authorization is withheld |
| **R6** | **Committing third-party content** into a repository that is a distribution channel, contrary to `DECISION|MOGO|20260727|005`'s redistribution prohibition | 🟠 Medium | `inbox/**` gitignored except records; content commits only under an explicit per-candidate storage policy |
| **R7** | **Live governance inconsistency.** `BACKLOG-002` C-1 says *"do not ingest before licensing is resolved"*; `DECISION|MOGO|20260727|005` says licensing does not block internal research. Both are current documents | 🟠 Medium | One-line correction to `BACKLOG-002` citing the decision. 10 minutes. Not a milestone |
| **R8** | **The negative result is never recorded**, so a searched-and-empty gap looks identical to an unsearched one, forever | 🟠 Medium | `AcquisitionRecord.outcome` + the campaign's negative-result condition. This is the specific defect the design exists to fix |
| **R9** | Rate limiting mis-set → the source blocks the requester, poisoning future acquisition | 🟠 Medium | Conservative floor, per-run cap declared in the campaign, fail-closed. Prefer slower than allowed |
| **R10** | **Python test baseline is red** — 4 of 307 failing (§1.6), all expired emptiness assertions. A suite that fails by design trains people to ignore it, and will mask the first real boundary-test failure | 🟠 Medium | Convert the 4 to invariants (not deletions, not skips) in Step 0, before the mirror tests in Step 1 are added to the same suite |

---

## 12. Acceptance criteria

**Boundaries (all must hold, no exceptions)**
1. `tests/run_all.sh` green; zero protected drift; 63 functions + 4 constants byte-identical.
2. The existing `TestNoNetworkImports` passes **unmodified** — not relaxed, not re-scoped, not skipped.
3. The new mirror test passes: no `research_collector/*` module imports the evidence/graph layer or
   writes anywhere under `docs/trader-intelligence/` except `acquisition/inbox/`.
4. Zero network access in any test. Every Collector test runs against fixtures.
5. Zero changes to `index.html`, replay, paper trading, strategy rules, thresholds, or sizing.
6. `StrategyRule` count remains 0; no claim's `confidenceState` changes as a *side effect* of tooling.
7. Python research suites green — the **4 currently-failing** emptiness assertions (§1.6) converted to
   invariants, not deleted and not skipped. This is a precondition for Step 1, because the new
   boundary tests are worthless in a suite that is already expected to fail.

**Capability**
8. A `ResearchCampaign` can be declared, is dated and hashed, and names its gap IDs, budget, stopping
   rule and negative-result condition **before** any request is made.
9. Discovery over a real channel URL yields ≥1 video ID; a zero-ID result is a hard failure, not empty.
10. Every retrieval attempt — including refusals, blocks and empty bodies — produces an
    `AcquisitionRecord` that validates against its schema.
11. Every request is robots-checked, host-allowlisted, and rate-limited, with the per-run cap enforced.
12. All 12 existing sources carry a retroactive `AcquisitionRecord`; the corpus has zero
    null-provenance retrievals.
13. `validate_acquisition.py` reports zero findings; graph rebuild `status=success`, zero ERROR/FATAL.

**Pilot (TJR) — re-specified per R1**
14. A declared campaign closes, or records as unclosable, each of its named targets.
15. The pilot reports **acquisition yield**: candidates discovered, deduplicated against the existing
    12, approved, retrieved, and the count of declared gaps each closed.
16. The pilot is explicitly permitted to conclude *"the material required to close this gap is not
    publicly available"* — and that conclusion, recorded, counts as success.

**Explicit non-criteria:** any confidence movement, any rule candidate, any promotion, any increase in
source count as an end in itself. **If a claim moves above `emerging` during this work, that is a
finding to investigate, not a win** — under `DECISION|MOGO|20260727|006` it would mean either a
genuine second educator corroborated it or something is wrong with the independence grouping.

---

## 13. Recommended milestone plan

Written in the reduction style Parts VIII–IX established, because this repository has demonstrated
that it will (correctly) cut anything that cannot justify itself.

```
STEP 0 — CORRECTIONS                                          ~1 hour
  · Fix BACKLOG-002 C-1 to cite DECISION|MOGO|20260727|005      10m
  · Convert the 4 failing emptiness assertions to invariants    45m
  → No new capability. Removes a live contradiction and gets the
    suite honest before new boundary tests are added to it.

STEP 1 — THE AIRLOCK ⭐                                    1 session
  · Two mirror boundary tests, written FIRST and seen to fail
  · AcquisitionRecord + ResearchCampaign schemas
  · Retroactive records for the 12 existing sources
  → GATE: does the existing TestNoNetworkImports still pass verbatim?
       NO  → stop. The design is wrong, not the test.
       YES → proceed.
  → Delivers real value even if STEP 2 never happens: the corpus
    gains complete retrieval provenance for the first time.

STEP 2 — DISCOVERY + METADATA                              1 session
  · discover.py (IDs only) · resolve.py (oEmbed) · compliance · ratelimit
  · Batch bridge into register_source.py as METADATA_ONLY candidates
  → GATE: run against one real channel. Do the resolved educators
    match the library's existing attributions for known videos?
       NO  → stop. Misattribution corrupts confidence silently.
       YES → proceed.

STEP 3 — TJR PILOT CAMPAIGN                                1 session
  · Declare CAMPAIGN|TJR|… BEFORE collecting (targets = BACKLOG-002
    T1 risk, T2 trade recaps, T7 stop placement — the three that
    block P&L replay)
  · Discover → resolve → dedupe → prioritize → owner review
  · Owner approves 0-3 for content acquisition
  → Output: a ranked, deduplicated, provenance-complete queue and a
    yield report. NOT more evidence.

── STOP AND REASSESS ──
Whether STEP 4 (fetch.py for content) is worth building is
answerable only after STEP 3 shows what is actually findable.
```

**Total before the first real decision point: three sessions and an hour.** No new entity beyond
two schemas. No change to any existing module's behaviour. Steps 1 and 2 each deliver standalone value
if the sequence stops there.

### 13.1 A recommendation the brief did not ask for

The brief specifies TJR for the pilot, and §13 delivers TJR. But the corpus's own analysis is
unambiguous that **TJR is not the highest-leverage target**: `BACKLOG-002` names **A1-STOP** — any
ALEX_G source stating where the stop-loss goes — *"the single highest-value acquisition target in the
library,"* because one such source would unlock P&L replay across all nine existing ALEX_G sources at
once, and ALEX_G is the only educator whose method MOGO's shipped engine can actually express.

I am not narrowing the pilot. **Run TJR as specified if the goal is to prove the acquisition machinery
on a lower-stakes target** — that is a legitimate and defensible choice, and TJR's three
replay-blocking gaps (T1/T2/T7) are real. But if the goal is maximum research value per session,
A1-STOP is the better first campaign, and the machinery is identical either way. **This is decision D5
in §15.**

---

## 14. Files that would be created or modified

**Created (13):**

| Path | Kind |
|---|---|
| `scripts/research_collector/README.md` | Constitutional boundary doc |
| `scripts/research_collector/{campaign,discover,resolve,fetch,compliance,ratelimit,record}.py` | 7 modules |
| `docs/trader-intelligence/acquisition/schema/acquisition-record.schema.json` | Schema |
| `docs/trader-intelligence/acquisition/schema/research-campaign.schema.json` | Schema |
| `docs/trader-intelligence/acquisition/{campaigns,inbox,records}/` | 3 directories (created with their first real file, per the repo's no-placeholder rule) |
| `tests/research_collector/test_collector.py` | Fixture-only suite + mirror boundary tests |

**Modified (6, all additive except the Step 0 test correction):**

| Path | Change |
|---|---|
| `.gitignore` | Ignore `acquisition/inbox/**` except `acquisition-record.json` |
| `scripts/trader_intelligence/register_source.py` | Add `--from-batch <inbox path>` (reads a local directory; **imports nothing new**) |
| `docs/trader-intelligence/acquisition/README.md` | Document the airlock and restate the unchanged no-network rule for the queue |
| `docs/trader-intelligence/proposals/BACKLOG-002-…md` | Correct C-1 to cite `DECISION|MOGO|20260727|005` |
| `docs/trader-intelligence/OPERATOR-PLAYBOOK.md` | New Stage 0.5 — campaign declaration and the inbox handoff |
| `tests/trader_intelligence/evidence/test_phase{1b,7a}.py` *(Step 0)* | Convert the 4 expired emptiness assertions to invariants — no assertion deleted or skipped |

**Explicitly not touched:** `index.html` · `regression-baseline*.{py,json}` · anything under
`tests/` other than the new suite and the Step 0 correction above · every existing
`scripts/trader_intelligence/` module except the one additive flag above · all 18 evidence schemas ·
all 6 graph schemas · the 4 existing acquisition schemas · every record in `evidence/`, `graph/`,
`traders/`, `imports/`.

---

## 15. Decisions requiring approval

| # | Decision | Why it cannot be defaulted | My recommendation |
|---|---|---|---|
| **D1** | **Authorize network capability at all**, under the airlock design (§3.1) | Reverses nothing — `DECISION|MOGO|20260725|002` constrained the *queue*, which stays constrained — but it is the first time any MOGO code makes an outbound request. That deserves an explicit `OwnerDecision`, not an inference | **Approve**, as a new `decisionType: acquisition` record that names the airlock as the binding constraint |
| **D2** | **Scope of automated retrieval**: metadata only, or metadata + content bodies | §9.1 established that transcript bodies are server-blocked. Approving "content retrieval" in the abstract approves a capability that does not work | **Metadata only in V1.** Revisit after Step 3 shows what is findable |
| **D3** | **What may be committed** from a retrieval | `DECISION|MOGO|20260727|005` permits internal storage and prohibits redistribution; this repository's history is a distribution channel | **Records always; content never, absent a per-candidate storage-policy decision** |
| **D4** | **Rate-limit floor and per-run request cap** | These are the difference between a well-behaved client and an abusive one, and they cannot be inferred from the codebase | Propose: ≥2 s floor, per-host concurrency 1, ≤50 requests per run, declared per campaign |
| **D5** | **First campaign target: TJR (as briefed) or ALEX_G A1-STOP** | §13.1. The machinery is identical; the research value is not | **Owner's call.** TJR proves the machinery on a lower-stakes target; A1-STOP has materially higher leverage |
| **D6** | **The pilot's success measure**, given R1 | If "more TJR sources" is the measure, the pilot will succeed while producing nothing. Under `DECISION|MOGO|20260727|006` confidence movement is impossible | **Gap closure and recorded negative results**, never source count and never confidence |
| **D7** | Whether the **`BACKLOG-002` C-1 correction** (R7) may be made now, ahead of approval | It is a 10-minute correction to a document that currently contradicts an active owner decision | **Yes — do it in Step 0**, or explicitly defer it |

---

## Summary

MOGO's research system is far more complete than the brief assumes. Provenance, extraction,
contradiction handling, review gating, packaging, ingestion and audit logging are all built, tested,
and carrying a real 12-source corpus. What is missing is one deliberately-excluded capability, and the
18-state lifecycle already has the socket cut for it.

The design that fits this repository is not a research platform. It is **an airlock**: a small,
network-capable Collector that lives outside the wall, whose only output is a file and a signed record
of how that file was obtained, and which cannot touch the corpus. That preserves the exact property
that made the offline decision safe, while ending the situation where a system with a 15-invariant
provenance specification cannot say how any of its 12 sources was actually retrieved.

Two findings should be weighed before any of it is approved. **Transcript bodies cannot be retrieved**
— verified, HTTP 200 with zero bytes — so a V1 promising automated transcript collection would fail on
contact. And **more TJR material cannot raise TJR confidence**, by a standing owner decision confirmed
by three ingestion cycles that moved nothing. An acquisition system built without those two facts in
front of it would be built to succeed at the wrong thing.

**Nothing has been implemented. Awaiting review and approval of D1–D7 before any work begins.**

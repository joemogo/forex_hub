# MOGO-017 — Autonomous Research Change Detection
## STEP 1 — READ-ONLY READINESS AUDIT + FORWARD PAPER-TRADING OPERATIONAL HEALTH AUDIT

**Status: AUDIT ONLY. No MOGO-017 implementation was authorized or performed by this step.**
**PAPER TRADING ONLY — live-money trading remains unauthorized.**

---

## 0. Authoritative starting state — verified, not assumed

| | Verified |
|---|---|
| Working directory | `/Users/joemogollon/Desktop/Forex Hub` |
| Repository identity | `origin` → `https://github.com/joemogo/forex_hub.git` |
| Branch | `main` (tracking `origin/mogo-main`) |
| HEAD | `b9a51c32a60dcfa019bd501f6518f14306737289` |
| HEAD == MOGO-016 closeout `b9a51c3` | ✅ **yes** |
| `git status --porcelain` | **empty — clean** before the audit began |
| Ahead / behind `origin/mogo-main` | **0 / 0** |

No discrepancy. Audit proceeded.

**What this step wrote:** this report only. No source, test, configuration, evidence, research
artifact, scheduler or browser state was modified. Analysis scripts were written to the session
scratchpad, outside the repository. The live forward browser was never touched, reloaded or
restarted; all forward evidence was read from a **preserved checkpoint copy**, never the live
profile.

---
---

# PART A — CHANGE-DETECTION READINESS

## A1. Where acquired content receives deterministic identity

**`platform/src/mogo_platform/runtime/connector_transport.py:160` — `content_hash(raw)`**

```python
def content_hash(raw):
    """Deterministic identity of the acquired bytes. Never a timestamp."""
    return hashlib.sha256(raw).hexdigest()
```

SHA-256 over the **verbatim external response bytes**, computed before any interpretation, parsing
or wrapping. Carried on `AcquisitionOutcome.contentHash` and surfaced as `result["contentHash"]`.

A **second, different** hash exists: `ingest_local_artifact.build_artifact_record()` (line 161) does
`ids.sha256_hex(raw)` over the bytes of the **wrapper file**, producing the research artifact id.
The distinction between these two is the central design question for MOGO-017 — see A6.

## A2. Where duplicate content is currently detected

**`ingest_local_artifact.find_existing(content_hash)` (line 197)** — a path existence check, because
the corpus is content-addressed: `research-artifacts/<contentHash>.json`. Result fields
`duplicateStatus` (`NEW` | `DUPLICATE_ALREADY_INGESTED`) and `ingested` (bool).

This detects *"have I ever seen these exact bytes"*. It does **not** answer *"is this different from
what this source returned last time"* — there is no per-source comparison anywhere today.

## A3. Does durable history preserve enough to compare against the prior accepted content?

**YES — and no new storage is required.** Verified by executing the query against the live runtime
index (read-only):

```sql
SELECT t.subject_source_id, r.recorded_at,
       json_extract(r.result_json,'$.contentHash')            AS content_hash,
       json_extract(r.result_json,'$.resourceId')             AS resource,
       json_extract(r.result_json,'$.ingestion.artifactId')   AS artifact
  FROM tasks t
  JOIN commands c           ON c.command_id      = t.command_id
  JOIN capability_results r ON r.idempotency_key = c.idempotency_key
 WHERE t.subject_source_id IS NOT NULL
 ORDER BY r.recorded_at
```

Actual output — the three MOGO-016 scheduler-triggered acquisitions:

```
2026-08-11T23:24:08.227Z  SRC|youtube|c785970cc458  res=hb7ot1_szWI  hash=b668d4209abbf2b8…  RART|d4e4ec82…
2026-08-11T23:26:05.413Z  SRC|youtube|c785970cc458  res=hb7ot1_szWI  hash=b668d4209abbf2b8…  RART|d4e4ec82…
2026-08-11T23:28:01.709Z  SRC|youtube|c785970cc458  res=hb7ot1_szWI  hash=b668d4209abbf2b8…  RART|d4e4ec82…
```

Everything change detection needs — **source, resource, content hash, ordering** — is already
durable. Supporting detail:

- `tasks.subject_source_id` exists as a first-class column (`schema.py`), populated by the policy
  gate from `inputRefs`.
- `capability_results` is `UNIQUE(idempotency_key)` with `result_json` + `result_hash`, and
  `result_store.lookup()` re-derives the hash and refuses a row that disagrees.
- Ordering comes from `capability_results.recorded_at` and, authoritatively, from the append-only
  event log sequence.

**Gap, minor:** `capability_results` has **no `source_id` column and no index on one**
(`idx_results_capability` is on `capability_id` only), so per-source lookup needs the join above or
a `json_extract` scan. At three rows this is irrelevant; it is named so it is a choice rather than a
surprise.

## A4. The repository-native identity of "same source"

**`sourceId`** — the `SRC|<provider>|<12-hex>` composite validated by
`ids.require_composite_id(..., "SRC", ...)`. For this milestone: `SRC|youtube|c785970cc458`.

It is the key of `connector_authorization.APPROVED_DESTINATIONS`, the key of
`authorizations.resolve()`, the `inputRefs` subject the policy gate resolves, and the
`tasks.subject_source_id` column. **One identity, already load-bearing in four places.**

**Comparison must be keyed on `(sourceId, resourceId)`, not `sourceId` alone.** The connector
acquires metadata *for one resource*; two videos under one source would otherwise be compared
against each other and register as permanent mutation.

## A5. Which identity should be compared

**`result["contentHash"]` — the raw external byte hash from `connector_transport.content_hash`.**

| Candidate | Verdict |
|---|---|
| **Raw byte hash** (`b668d420…`) | ✅ **USE THIS.** SHA-256 of exactly what the source returned, computed before interpretation. Contains no local, volatile or transport value. |
| Research artifact hash (`d4e4ec82…`) | ❌ hash of the **wrapper document**, which embeds the acquisition record. Currently stable only by accident — see A6. |
| Stored artifact path | ❌ derived from the artifact hash; inherits the same fragility. |
| Canonicalized JSON hash | ❌ would require parsing before identity, and would make MOGO blind to a byte-level change the provider considers meaningful. |

**Empirical stability evidence:** four independent acquisitions of this endpoint — one in MOGO-015
at ~18:12Z and three scheduler-triggered in MOGO-016 at 23:24/23:26/23:28Z, spanning ~5¼ hours —
all produced content hash `b668d4209abbf2b8718cea2fa84eacd3985cbb4d1fc352dd1720f64bebb92a00`.
**Byte-identical every time.** The response body carries no timestamp, nonce or request echo.

## A6. ⚠️ Volatile values — the finding that most affects MOGO-017

**The research artifact hash is deterministic today only because three provenance fields are
unpopulated. Filling them — which MOGO-016's own report recommended as a fix — would make every
scheduled acquisition register as a change.**

`acquire_approved_source_metadata.preserve_raw()` writes a wrapper document that embeds the whole
acquisition record, and `ingest.execute()` hashes **that wrapper**, not the raw bytes. Inspecting
the wrapper on disk (`intake/acquired/b668d420….json`):

```json
{ "acquisition": { "acquiredAt": null,                     ← volatile slot, unpopulated
                   "decision": { "decidedAt": null,        ← volatile slot, unpopulated
                                 "requestedUrl": null } }, ← unpopulated
  "contentHash": "b668d420…", "rawContent": "…" }
```

Why they are null — `connector_transport.acquire(request, now_iso=None, …)` (line 172) takes the
clock as an argument, and `acquire_approved_source_metadata.execute()` calls it **without one**, so
`acquiredAt` is always `None`. `decidedAt` and the decision's `requestedUrl` are likewise absent
from the request dict the capability builds.

**Consequence, stated plainly:** the artifact-level hash is stable by omission, not by design. Any
future correction that stamps a real acquisition time would produce a new artifact hash on **every
single scheduled run**, creating a permanent false-CHANGED signal and a new research artifact every
6 hours.

**Therefore MOGO-017 must compare the RAW byte hash**, which is structurally immune to this, and
must **pin that property with a test** so the provenance gap can be fixed later without breaking
change detection.

**No other volatile values participate.** Request ids, execution ids, task ids, idempotency keys,
HTTP headers and transport metadata are all outside both hashes. Response headers are never hashed
(only `contentType` and `httpStatus` are recorded as fields).

## A7. Existing event and audit conventions to reuse

- **Append-only event log** `platform/runtime/events/operational-events.jsonl`, validated by
  `contracts/event.py`, indexed into `event_index`, rebuildable (`reset --rebuild-index`).
- **Capability results** recorded under the idempotency key with hash re-derivation on read.
- **`policy_decisions`** table — the precedent for a per-decision durable record with a reason.
- **Operator views** `status` / `audit` / `failures` / `policy` — a new classification must be
  visible there rather than only in a JSON blob.
- **Derived-vs-observed discipline** (`index.html`'s `derived*` prefix): a classification restates
  what was recorded; it never re-decides it.

## A8. Does `SourceMutationDetected` already exist?

**YES — it is already an approved event type and needs no contract change.**

- `contracts/vocabulary.py:137` — `"SourceMutationDetected"` is in `EVENT_TYPES`.
- `contracts/event.py:187` — `require_member(eventType, …, vocabulary.EVENT_TYPES)`, so the event
  validates today.
- `docs/architecture/MOGO-009-CONTRACT-CATALOG.md` §I — metadata acquisition's source-mutation
  behaviour is literally specified as `SourceMutationDetected`.
- `contracts/errors.py:210` — a distinct `source_mutated` **error class** also exists
  (`retryable=False, terminal=False, routesToReview=True`).

**Two constraints found:**

1. **`source_mutated` must NOT be used as a failure class.** `registry._validate_failure_classes()`
   (line 251) *refuses at registration* any class that routes to review without a terminal path —
   governance decision B-3 — because such a task could neither retry nor reach review and would
   strand in `failed` forever. **A detected change is not a failure**, so this is the correct
   outcome anyway: change detection must be a *classification of a success*, never an error.
2. **Adding `SourceMutationDetected` to the acquisition capability's `emittedEvents` changes its
   manifest**, and `registry.register()` refuses a changed manifest under an unchanged
   `capabilityId` (a changed capability is a new version needing a new identity). So MOGO-017 must
   either bump the capability id/version or emit from the orchestrator seam. `emittedEvents` is
   declarative — it is stored but never enforced at emit time — so an undeclared emit would work
   and would be **exactly the kind of quiet inaccuracy this codebase refuses**.

## A9. Proposed semantics

Classification of one **completed, validated** acquisition for one `(sourceId, resourceId)`:

| Outcome | Condition | Result |
|---|---|---|
| **FIRST_OBSERVATION** | no prior accepted acquisition for this `(sourceId, resourceId)` | record baseline; no mutation event |
| **UNCHANGED** | `contentHash == priorContentHash` | record occurrence; **no** new artifact; no mutation event |
| **CHANGED** | `contentHash != priorContentHash` | record occurrence, emit `SourceMutationDetected` carrying prior + new hash, new artifact registered by existing dedupe |
| **ACQUISITION FAILURE** | `outcome.ok == False` | **no classification at all.** Prior accepted content is untouched. Retry/dead-letter as today. A failed fetch is not evidence of stability. |
| **VALIDATION FAILURE** | ingestion refuses (empty, oversized, non-UTF-8, malformed) | **no classification, and the baseline does NOT advance.** |
| **DUPLICATE CONTENT** | same bytes, whether same or new request identity | **UNCHANGED.** Content identity decides, request identity does not. |
| **CHANGED BYTES THAT FAIL VALIDATION** | new hash **and** validation fails | **NOT a mutation.** Record the failure; leave the baseline on the last *validated* content. Promoting unvalidated bytes to "the new truth" would let a truncated or hostile response silently become the baseline. |

**The load-bearing rule: the baseline advances only on validated, durably ingested content.**

## A10. Where comparison belongs in the lifecycle

**AFTER validated durable ingestion, inside the acquisition capability, before it returns.**

- *Before ingestion* — would classify bytes that might fail validation, letting a bad response
  become the baseline (contradicts A9).
- *During ingestion* — `ingest_local_artifact` is source-agnostic by design and is shared with the
  operator-intake path; teaching it about source history would give it a second responsibility and
  put per-source state in a capability that has none.
- **After ingestion** — the acquisition capability already holds `sourceId`, `resourceId`,
  `contentHash` and the ingestion result at line 184. Classification is a read of prior history plus
  a comparison. **The smallest correct seam.**
- *After the task* (orchestrator) — would need to re-derive source and content from the result and
  duplicates the capability's own knowledge.

## A11. Proving mutation deterministically without waiting for the source

The source has been byte-stable across four acquisitions and may never change. Determinism comes
from **testing the comparison against supplied history, not against the network**:

1. `connector_transport.acquire()` already takes an `opener` double (MOGO-015's 20 tests use it), so
   a fixed synthetic body can be returned with **zero network access**.
2. The comparison function should be **pure** — `(priorHash, newHash) → classification` — in the
   style of `policy.evaluate()` and `retry.resolve_policy()`, taking history as an argument. Every
   transition is then exhaustively testable with no process, no clock and no wait.
3. The history lookup is one SQL query against a temporary state root, which every platform suite
   already constructs.

**Sequence to prove:** FIRST → UNCHANGED (same bytes) → CHANGED (one byte differs) → UNCHANGED at
the new baseline → CHANGED back. Plus: failure does not advance the baseline; validation failure
does not advance it; a *different resource* under the same source is FIRST, not CHANGED.

## A12. Synthetic fixtures without contaminating genuine research evidence

**By construction, using the mechanism the platform already has:**

- `MOGO_RUNTIME_STATE_ROOT` points the runtime at a temp directory — every platform suite already
  does this, so synthetic history never enters the real event log or index.
- ⚠️ **`ingest_local_artifact.ARTIFACT_ROOT` and `INTAKE_ROOT` are module-level absolute paths
  derived from `__file__` and are NOT overridable.** A test that runs the *real* ingestion would
  write into the genuine research corpus. **This is the single largest contamination risk in
  MOGO-017 and must be closed before any test executes the full path** — either by making those
  roots injectable (smallest correct change) or by testing the classifier against supplied history
  without invoking ingestion.
- Synthetic content must be distinguishable: a fixture body that could never come from the approved
  source, so a stray artifact is identifiable rather than plausible.

## A13. Recording a real external mutation without changing the test design

**Yes.** The scheduled path would classify a genuine change identically to a synthetic one — same
code, same comparison. The test design proves the *mechanism*; a real mutation would be an
*observation* recorded by it. No test asserts that the source never changes, and none should.

## A14. Minimum implementation surface

| Change | Size |
|---|---|
| `runtime/change_detection.py` — pure classifier + one history query | new, small |
| `acquire_approved_source_metadata.execute()` — classify after ingestion, add fields to the result | ~15 lines |
| Emit `SourceMutationDetected` on CHANGED (already an approved event type) | small |
| Make `ingest` roots injectable **or** avoid invoking ingestion in tests | small, but **required** (A12) |
| Surface the classification in `status` / `audit` | small |
| Capability id/version bump **if** `emittedEvents` is amended (A8) | governance decision |

**No schema migration. No new storage. No contract change. No new source. No new authorization.**

## A15. Minimum new tests

Pure classifier: all seven A9 outcomes · resource-scoped keying · baseline unadvanced on
acquisition failure and on validation failure · changed-but-invalid is not a mutation.
History query: empty → FIRST · returns the *most recent validated* prior, not merely any prior ·
one source's history never leaks into another's.
Integration (temp state root, transport double, **no real corpus writes**): the five-step
FIRST→UNCHANGED→CHANGED→UNCHANGED→CHANGED sequence.
Anti-regression: **the classifier compares the RAW byte hash, and a populated `acquiredAt` does not
change the classification** — the A6 property, pinned.
Boundary: no new network client, no ALEX/forward/campaign identifier reachable.

## A16. Evidence needed to prove the capability

The five-step transition sequence with hashes shown; a real scheduled run classified UNCHANGED
end-to-end; the `SourceMutationDetected` event as recorded in the append-only log; artifact counts
before/after showing CHANGED created exactly one new artifact and UNCHANGED created none;
`verify` INTEGRITY OK; full gates.

## A17. How the design preserves everything already proven

| Property | Preserved because |
|---|---|
| Authorization | classification happens **after** a task already passed policy → authorization → connector gate. It cannot cause a fetch. |
| Scheduler safety | no change to the fixed command, the window, or `collect`. |
| Request identity | untouched — still the windowed idempotency key. |
| Content identity | **strengthened** — the raw byte hash becomes explicitly load-bearing and test-pinned. |
| Dedupe | unchanged; classification *reads* the ingestion result, it does not replace it. |
| Provenance | additive fields only. |
| Existing research artifacts | content-addressed and never rewritten; UNCHANGED writes nothing. |
| Scientific firewall | classification is a `lane: RESEARCH` observation with `promotionStatus: NOT_A_TRADING_RULE`; it creates no rule and no hypothesis. |
| ALEX / forward / C1 / legacy corpus | no code path exists from the research runtime to any of them — asserted by the platform boundary suite. |

---
---

# PART B — FORWARD PAPER-TRADING OPERATIONAL HEALTH

**Method.** The live browser was never touched. Evidence was read from the preserved checkpoint
`~/MOGO-EVIDENCE-PRESERVED/20260811T234228Z/` (taken during MOGO-016 with source rollup == copy
rollup, status VERIFIED). The MOGO-013 observation ledger was decoded using the repository's **own**
`scripts/mogo_evidence_leveldb_extract.js` primitives (`readSst`, `readWal`, Snappy, V8) — the only
adaptation being a generic deserializer, because the committed `deserializePackage()` requires
`o.packageId` and therefore discards observation records. Recovered **3,095 observation records**
(seq 1 … 3,695; the shortfall is uncompacted/overwritten values, disclosed, not hidden).

## B1–B3. Durable forward observations after the activation cutoff

| | |
|---|---|
| Activation cutoff | `2026-08-11T02:43:57.894Z` — **unchanged, not re-baselined** |
| Observations recovered | **3,095** — `EVALUATION` 2,700 · `POLL` 395 |
| **After the cutoff** | **3,095 (100%)** |
| Before the cutoff | **0** |
| Earliest observation | `2026-08-11T14:59:03.962Z` |
| **Latest observation** | **`2026-08-11T23:42:11.084Z`** |

⚠️ **A blind window exists.** The ledger begins at 14:59:03.962Z — MOGO-013's own deployment. From
the cutoff at 02:43:57.894Z to 14:59Z, roughly **12¼ hours of forward operation has no durable
observation record at all.** This is not data loss; the instrument did not yet exist. It matters
because the one decisive event of the campaign falls inside it (B11).

## B4. Instruments observed

All **12** `SCAN_PAIRS` appear in poll records:

```
GBP_USD 9 · EUR_USD 9 · GBP_JPY 9 · AUD_USD 9 · USD_JPY 9 · GBP_CHF 9
NZD_USD 9 · AUD_JPY 9 · GBP_CAD 9 · EUR_JPY 11 · USD_CAD 10 · USD_CHF 11
```

The expected monitored set is being observed in full. Evaluations span **10** pairs — `GBP_USD` and
`EUR_USD` produced no setups in the window, which is a fact about those markets, not a gap.

## B5. Has the pipeline been active recently?

**Yes.** 395 polls, **395 OK, 0 ERROR**. Last successful poll `2026-08-11T23:42:11.084Z`,
approximately 38 minutes before this audit read the checkpoint. The forward observation pipeline is
**live and healthy**.

## B6. Observation gaps and their correlation with host sleep

| Gap | Duration | Missed intervals |
|---|---|---|
| **`18:54:34.886Z` → `21:01:47.744Z`** | **127 minutes** | **126** |
| `18:51:03Z` → `18:54:34Z` | 4 min | 3 |
| ~10 others | 2 min each | 1 each |
| **Total missed** | | **145** |

**The 127-minute gap correlates exactly with the host sleep.** `pmset -g log`: Maintenance Sleep
`14:54:53 ET` (= 18:54:53Z), Wake `EC.LidOpen/UserActivity` `17:01:43 ET` (= 21:01:43Z). The ledger's
gap boundaries and the host's sleep boundaries agree **to within four seconds**. This is MOGO-013
doing exactly what it was built for, and it independently confirms the MOGO-016 host finding.

The remaining ~19 missed intervals are 1–2 minute jitter around the 60-second poll — normal browser
timer behaviour, not a defect.

## B7. Pipeline trace — what persisted evidence does and does not prove

| Boundary | Proven by durable evidence? | Evidence |
|---|---|---|
| market data → observation | ✅ **YES** | 395 POLL records, 395 OK, 12 instruments |
| observation → ALEX evaluation | ✅ **YES** | 2,700 EVALUATION records; both setup types (`A_repeatedReaction` 1,817 · `B_breakRetest` 883) |
| evaluation → qualification / rejection | ✅ **YES** | every record carries `status`, `reason`, `ruleAttribution`, `liveEvaluationFinal` |
| qualification → paper execution eligibility | ❌ **NO** | **no durable instrumentation** — see B7a |
| eligibility → paper trade opening | ❌ **NO** | same |
| trade opening → durable trade/evidence recording | ❌ **NOT EXERCISED** | 0 evidence packages, because 0 trades |

### B7a. ⚠️ The instrumentation gap — and why "0 pipeline records" proves nothing

The observation ledger defines a `PIPELINE` kind with exactly the stages needed
(`index.html:12984`, `evidenceBuildPipelineObservation`):

```js
rec.stage = o.stage || null;   // CANDIDATE | REQUESTED | REQUEST_FAILED | OPENED | CLOSED
```

It is built at `index.html:13154` from `o.pipeline`. **But neither call site of
`evidenceRecordForwardObservations` supplies a `pipeline` array** — both pass only
`{scanId, poll, statuses}` (`index.html:4936` and `index.html:4962`).

**`PIPELINE` observations recovered: 0. That is because nothing ever writes one, not because
nothing reached execution.** The decision→execution boundary *is* instrumented — via
`emitDecisionEvent` (`TRADE_OPEN_REQUESTED`, `CANDIDATE_REJECTED`, …) — but the Decision Event bus
is, in MOGO-013's own words, *"a 500-entry ring holding roughly two minutes"*. **Ephemeral.**

This is the exact defect MOGO-013 fixed for evaluations and left unfixed for execution.

## B8. Are ALEX evaluations actually occurring?

**Yes, unambiguously.** 2,700 evaluation records, all after the cutoff, across 10 pairs, covering
both ALEX setup types. The zone/setup engine is running and producing setups; ALEX is evaluating
them; each decision is recorded with its rule attribution.

## B9–B10. Why observations did not become trades — the complete distribution

```
byStatus         { "IGNORED — BEFORE ACTIVATION": 2691,
                   "IGNORED — STALE SIGNAL":         9 }
byReason         { "(none)":                       2691,
                   "SIGNAL_TOO_OLD_AT_FIRST_EVALUATION": 9 }
ruleAttribution  { "ALEX_ACTIVATION_CUTOFF":       2691,
                   "ALEX_SIGNAL_STALENESS":           9 }
derivedQualifying: 0        derivedActivationCutoffPassed=false: 2691
```

**Every single evaluation was rejected by one of exactly two frozen rules.** Nothing was rejected
for an unexpected reason, and nothing errored.

The gate ladder in `alexGEvaluatePairForLiveSetups` (`index.html:4556–4600`) is:
duplicate-signal check → **activation cutoff** (`alexGIsSetupEligibleForLiveTrading`) → **staleness**
(`alexGIsSetupSignalStale`) → … → `alexGAttemptOpenLivePosition`.

**2,691 rejections are the activation cutoff working correctly.** Setups are re-derived from
historical candles on every engine rebuild, so ALEX keeps re-discovering setups that qualified long
before activation — qualification timestamps range from **2025-12-12T22:00Z** to
**2026-08-11T06:00Z**. Refusing to trade them is the entire purpose of the cutoff.

## B11. 🔴 The decisive finding — exactly ONE setup has qualified since activation

Of 2,700 evaluations, only **9** have a qualification timestamp after the cutoff — and all nine are
**the same setup**, re-derived hourly:

| | |
|---|---|
| Pair / timeframe / type | **AUD_JPY · H1 · `A_repeatedReaction`** |
| Qualified at | **`2026-08-11T06:00:00.000Z`** — 3 h 16 m after activation |
| First durable evaluation | **`2026-08-11T14:59:15.802Z`** |
| **Age at first evaluation** | **539 minutes** |
| Staleness limit (H1) | **60 minutes** (`maxLiveSignalAgeMinutes:{H1:60,…}`, `index.html:2445`) |
| Outcome | `IGNORED — STALE SIGNAL` / `SIGNAL_TOO_OLD_AT_FIRST_EVALUATION`, `liveEvaluationFinal: true` |

Re-evaluated hourly at ages 539 → 541 → 601 → 660 → 721 → 902 → 903 → 961 → 1021 minutes. Each
rebuild is stamped as a *fresh* "first evaluation", so the recorded age only grows — the documented
MOGO-012/013 hourly re-creation behaviour, recorded faithfully.

**Why the age can never recover:** `alexGLiveSetupStatuses` is declared
`let alexGLiveSetupStatuses=[]; // … session-only` (`index.html:2195`) — **not persisted**. It is
reset on every page load, so the "decided once, PERMANENT" dedup is session-scoped; and
`alexGLiveSignalId` embeds `setupId`, which is regenerated per rebuild. Once a post-activation setup
is not caught inside its 60-minute window, **it is permanently unreachable.**

**The setup qualified at 06:00Z. It needed evaluation by 07:00Z. The durable ledger does not begin
until 14:59Z.** Whether ALEX polled and legitimately rejected it during that blind window, or
whether it was never seen fresh, **cannot be determined from durable evidence.** That is the honest
answer, and it is the single most important open question about this campaign.

## B12. Is zero genuine forward paper trades still the evidence-backed result?

**Yes.** 0 evidence packages in the forward store (independently confirmed twice: `storedPackages:
0`, `uniquePackageIds: 0`, and 0 records carrying `packageId`); 0 evaluations reaching a qualifying
state; 0 pipeline records. Nothing suggests a trade occurred and was lost.

**And zero is not surprising.** `index.html`'s own v12.9.0 release note states: *"live paper trading
yields roughly one ALEX setup per pair per week, and the entire real dataset is two July Break &
Retest losses."* At 12 pairs that is ~0.07 setups/hour; over ~21 hours of forward operation the
expectation is **≈1.4 post-activation setups**. **Exactly 1 was observed.** The base rate and the
observation agree.

## B13. Read-only inspection of the paper execution path

The ALEX forward lane does **not** use `openPaperPosition` — that is the separate JVM/current-strategy
lane. ALEX's path is:

```
alexGEvaluatePairForLiveSetups          (gate ladder)
  → alexGAttemptOpenLivePosition        (async wrapper; the ONLY await; real fetchBidAsk)
    → alexGConstructLivePosition        (PROTECTED, index.html:4278) → 'TRADE OPENED' + position
      → alexGAccount.openPositions / commitAlexGLedger
        → alexGCheckLivePositions / alexGCloseLivePosition
```

**Nothing obvious would prevent a valid signal from opening a paper trade.** Reading
`alexGConstructLivePosition`, every early return is a *specific, named* refusal —
`DUPLICATE`, `BLOCKED — INVALID DIRECTION`, `BLOCKED — EXISTING POSITION`, `BLOCKED — INVALID STOP`,
`BLOCKED — NO PIP VALUE` — and the success path returns `{status:'TRADE OPENED', position}`. No
blanket disable, no unreachable branch, no forced-false condition was found. Protected-function
drift is **0**, so this code is byte-identical to the validated baseline.

**This is code inspection, not proof of execution.** See B16.

## B14–B15. Existing automated tests of the paper execution path

**A test does drive the real protected function to a successful open** —
`tests/v126_phase2c_wave1_tests.js:549`:

```js
r = g.alexGConstructLivePosition(baseSetup({setupId:'AGS|11'}), {H1:candles20},
                                 {bid:1.10595, ask:1.10605}, cfg, 10000, {});
check('Direct real construction success ("TRADE OPENED") …',
      r.status==='TRADE OPENED' && r.reason===null && !!r.position);
```

**What it proves:** the real, unmodified, protected `alexGConstructLivePosition` returns
`TRADE OPENED` with a position object for a qualifying setup. Its sibling fixtures prove each named
rejection path.

**What it does NOT prove — and this is question 15's answer:** it calls the construction function
**directly**, with a synthetic setup. It does **not** exercise `alexGEvaluatePairForLiveSetups`'s
gate ladder, nor `alexGAttemptOpenLivePosition`'s async wrapper and real `fetchBidAsk`, nor the
subsequent `commitAlexGLedger` persistence. `tests/v_paper_trading_audit_tests.js` covers the **JVM**
lane's `openPaperPosition` and ALEX's *close* side, not ALEX's *open* orchestration.

So the *decision core* is proven against the real function; **the end-to-end ALEX
qualification→open→commit chain, in the shape the forward campaign uses, has no automated proof.**

## B16. Conclusion

> ### **B — SYSTEM APPEARS HEALTHY, BUT EVIDENCE IS INSUFFICIENT TO PROVE THE FULL DECISION→EXECUTION PATH**

**Not (A)**, because three things are unproven: the execution boundary has no durable
instrumentation (B7a); no automated test covers the ALEX open chain end-to-end (B15); and the one
post-activation setup fell inside the pre-ledger blind window (B11).

**Not (C)** — no operational problem was found. Polls are 100% OK, evaluations are occurring on both
setup types across 10 pairs, every rejection is attributable to a named frozen rule, protected drift
is 0, and zero trades is consistent with ALEX's own documented ~1 setup/pair/week base rate.

**Not (D)** — the evidence is substantial and internally consistent; it is *bounded*, not absent.

**Plain statement for the operator: nothing is broken that this audit can find, and the reason for
zero trades is fully explained by the activation cutoff plus a single stale post-activation setup.
But we cannot yet *prove* a qualifying signal would open a paper trade, because nothing durably
records that part of the path and no test exercises it end-to-end.**

## B17. Smallest safe next diagnostic steps

Ordered by value per unit of risk. **None changes ALEX rules, loosens a parameter, forces a genuine
trade, contaminates forward evidence, resets the campaign, or alters the activation cutoff.**

**D-1 — Wire the existing `PIPELINE` observation kind to the existing seam. (Highest value.)**
The schema, natural key, builder and record path already exist and are unused. Populate `pipeline:`
at the `alexGLivePollTick` seam from records the engine already produces. Purely additive,
fire-and-forget, at the same non-protected seam MOGO-013 already uses with zero drift. **This is the
change that converts (B) into (A) or (C) with real evidence** the next time a setup qualifies.

**D-2 — Add an end-to-end ALEX open fixture in the offline harness.**
Drive a *synthetic, post-cutoff, fresh* setup through the real gate ladder → `alexGConstructLivePosition`
→ ledger commit, asserting `TRADE OPENED` and one account + one journal record. Closes B15. Offline
JXA harness with stubbed storage — cannot reach real data.

**D-3 — Record ALEX's own liveness independently of the ledger's start.**
The 02:43Z–14:59Z blind window is why B11 is unanswerable. A durable per-poll marker of *when ALEX
last evaluated each pair* would make the next such question answerable.

**D-4 — Act on the MOGO-016 host reliability recommendation.**
Now evidence-backed rather than theoretical: H1 staleness is **60 minutes** and the observed sleep
gap was **127 minutes**. **A post-activation H1 setup qualifying during a sleep would be
permanently lost** — it can never be re-caught, because each hourly re-creation is stamped with a
later first-evaluation time. Smallest reversible fix: keep the machine on AC (the existing
`caffeinate -dimsu` is honoured only on AC power).

**Explicitly NOT recommended:** loosening `maxLiveSignalAgeMinutes`, changing the cutoff, forcing a
trade, or `generateTestAlexTrade` — the last writes into the **real** `alexGAccount.openPositions`
and would contaminate the forward lane.

## B18. Can the paper execution mechanism be proven safely in isolation?

**Yes — and the mechanism already exists. NOT performed in this step.**

**Safe route:** the offline JXA fixture harness (`tests/run_*_tests.js`). It exposes real production
functions as bare identifiers against stubbed `localStorage` and stubbed `fetch`, in a process with
**no access to real browser storage**. `v126_phase2c_wave1_tests.js` already proves `TRADE OPENED`
this way. Extending it to the full chain (D-2) is contamination-free **by construction**: no
IndexedDB, no evidence package written, no `alexGAccount` mutation outside the harness, and no ALEX
rule touched — the protected functions are *called*, never modified, and drift stays 0.

**Unsafe route, named so it is not chosen:** `generateTestAlexTrade` (`index.html:5053`) pushes a
`setupType:'DEV_TEST'` position into the **live** `alexGAccount.openPositions`. Although tagged, it
enters the genuine forward account and its monitors. **It must not be used for this proof.**

---
---

# INTEGRITY FINDINGS (read-only)

| Check | Result |
|---|---|
| Protected ALEX drift | ✅ **0** — all 63 protected functions and 4 protected constants byte-identical to the committed baseline; known-good hash match `True` |
| Campaign C1 | ✅ **33 / 33 verified · 0 missing · 0 mismatched · 0 unlisted** · verdict `VERIFIED`; manifest SHA-256 `c23e72e0…` unchanged |
| Legacy corpus | ✅ **220 re-derived · 0 mismatched**; rollup `667ff4c7…` matches the committed baseline |
| Research → forward contamination | ✅ **none** — `RART\|`, `SRC\|youtube`, `fxalexg`, `oembed`, `research-artifact`, `CAP\|research` each occur **0 times** in the forward campaign store |
| Forward → research contamination | ✅ **none** — no `sourceTradeId`, `PKG\|`, `openPositions`, `paperBalance` or `alexGStableHash` in any research artifact or raw acquisition |
| Research lane markers | ✅ both artifacts `lane: RESEARCH`, `promotionStatus: NOT_A_TRADING_RULE` |
| Forward evidence packages | ✅ **0** |
| Scheduler | ✅ loaded, `runs = 0` since the production reinstall, next firing at the 6-hour boundary; **not modified by this audit** |
| Repository status | ✅ clean apart from this report; HEAD `b9a51c3`; 0 ahead / 0 behind |

No destructive or state-changing check was run.

---

# UNCERTAINTIES — stated, not smoothed over

1. **The 02:43Z–14:59Z blind window.** ~12¼ hours of forward operation before MOGO-013 existed. The
   only post-activation setup (06:00Z) falls inside it. Whether it was evaluated fresh and
   legitimately rejected, or never seen, is **unknowable** from durable evidence.
2. **Observation recovery is partial** — 3,095 of ≥3,695 sequence numbers. Uncompacted/overwritten
   LevelDB values. Distributions are near-complete but not exhaustive; no recovered record
   contradicts the conclusions.
3. **Live in-page values remain unverified this session**, as in MOGO-016: the ALEX on/off toggle,
   the cutoff literal and the paper balance live in the running page and compressed storage. The
   ledger's continuing writes through 23:42Z are strong indirect evidence ALEX is ON and polling,
   but that is an inference, not a reading. *(The cutoff is corroborated in a different way: 2,691
   evaluations were rejected by `ALEX_ACTIVATION_CUTOFF`, which only happens if a cutoff is in
   force.)*
4. **`derivedQualifying: 0` is partly definitional** — it is computed as
   `!/IGNORED|BLOCKED|REJECT/i.test(status)`, and every status begins with `IGNORED`. It is
   corroborated by 0 evidence packages, not relied on alone.
5. **B7a's gap means absence of pipeline records is not evidence of absence of execution.** It is
   evidence of absent instrumentation. This audit does not claim otherwise.
6. **The external source may never change**, so CHANGED may never be observed in production. This is
   a property of the source, not a defect — hence A11's synthetic determinism.

---

# RECOMMENDED MINIMUM MOGO-017 IMPLEMENTATION PLAN

1. **Close the contamination risk first** — make `ingest_local_artifact`'s intake/artifact roots
   injectable, or design the tests not to invoke real ingestion (A12). **Nothing else starts until
   this is settled.**
2. `runtime/change_detection.py` — a **pure** classifier over `(priorHash, newHash, validated)` plus
   one history query keyed on `(sourceId, resourceId)`.
3. Call it in `acquire_approved_source_metadata.execute()` **after** validated ingestion; add
   `changeStatus`, `priorContentHash`, `priorObservedAt` to the result.
4. Emit `SourceMutationDetected` on CHANGED — already an approved event type. Resolve the
   `emittedEvents`/manifest-hash question (A8) **explicitly**, not by omission.
5. Tests per A15, including the **A6 anti-regression pin**: comparison uses the raw byte hash, and a
   populated `acquiredAt` does not change the classification.
6. Surface `changeStatus` in `status` / `audit`.
7. Full gates: platform suite, canonical gate, drift, C1, legacy corpus, forward campaign.

**Explicitly out of scope:** more sources, discovery, transcripts, strategy extraction, hypothesis
generation, rule promotion.

---

# SCIENTIFIC FIREWALL

MOGO-017 remains **RESEARCH ONLY**. Nothing found or eventually implemented for change detection may
automatically alter ALEX, alter strategy parameters, create or promote trading rules, modify
execution logic, enter the forward trading lane, modify Campaign C1, modify legacy evidence, or
authorize live-money trading.

Concern about zero paper trades is **not** permission to make ALEX trade more frequently. No
diagnostic proposed above changes a single ALEX rule, threshold or parameter. **We diagnose before
changing anything.**

**LIVE-MONEY TRADING REMAINS UNAUTHORIZED.**

---

# AUTHORIZATION STATUS (Step 1)

> **NO MOGO-017 IMPLEMENTATION WAS AUTHORIZED OR PERFORMED BY THE STEP 1 AUDIT.**

That report was the only repository change at Step 1. No source, test, configuration, evidence,
research artifact, scheduler or browser state was modified. Nothing was committed or pushed.

---
---

# MOGO-017 STEP 2A — FORWARD PAPER EXECUTION OBSERVABILITY

**Status: ✅ COMPLETE.** The forward PAPER execution lifecycle now leaves durable evidence.
**PAPER TRADING ONLY — live-money trading remains unauthorized.**

## 1. Starting repository state

| | Verified before any change |
|---|---|
| Repository | `origin` → `https://github.com/joemogo/forex_hub.git` |
| Branch / HEAD | `main` · **`b9a51c32a60dcfa019bd501f6518f14306737289`** = MOGO-016 closeout |
| Ahead / behind `origin/mogo-main` | **0 / 0** |
| Working tree | **only** the untracked Step 1 audit report (`MOGO_017_…md`); `git diff` empty — no tracked file modified |

Exactly the expected state. No unexplained change to absorb or overwrite.

## 2. The exact observability gap

MOGO-013 built the `PIPELINE` observation kind — the schema, the stage vocabulary, the natural key
and the durable write path — and then wired **nothing** to it:

- `evidenceBuildPipelineObservation()` documents `CANDIDATE | REQUESTED | REQUEST_FAILED | OPENED | CLOSED`.
- `evidenceObservationNaturalKey()` keys `PIPELINE` records.
- `evidenceRecordForwardObservations({scanId, poll, statuses, pipeline})` builds from `o.pipeline`.
- **Neither caller ever supplied `pipeline`.** Both passed `{scanId, poll, statuses}` only.

Consequence, and the reason Step 1 could not conclude better than **(B)**: the execution boundary
*was* instrumented — but only into the Decision Event bus, which MOGO-013's own comment describes
as *"a 500-entry ring holding roughly two minutes."* Ephemeral. So **zero PIPELINE records proved
nothing about execution; it proved only that nothing wrote them.**

## 3. Exact files and functions modified

`index.html` only — **130 insertions, 1 deletion**, in three functions plus one new block.

| Location | Change | Protected? |
|---|---|---|
| after `evidenceBuildPipelineObservation()` | **new** — `EVIDENCE_PIPELINE_BUFFER_MAX`, `alexGPipelineObservationBuffer`, `alexGRecordPipelineStage()`, `alexGDrainPipelineObservations()` | new code |
| `alexGAttemptOpenLivePosition()` | 6 recorder calls: CANDIDATE, REQUESTED, REQUEST_FAILED ×3, OPENED | ❌ **not protected** |
| `alexGCheckLivePositions()` | pre-loop tradeId snapshot; post-seam CLOSED emission | ❌ **not protected** |
| `alexGLivePollTick()` | supplies `pipeline:` to the existing MOGO-013 ledger call | ❌ **not protected** |

Two new test files: `tests/v017_step2a_pipeline_observability_tests.js` and its runner. Nothing else.

## 4. Why each modification is non-protected and additive

Verified against `regression-baseline.json`'s own `protectedFunctions` list (63 entries), not by
assumption:

```
alexGAttemptOpenLivePosition    PROTECTED = False   ← modified
alexGCheckLivePositions         PROTECTED = False   ← modified
alexGLivePollTick               PROTECTED = False   ← modified
alexGConstructLivePosition      PROTECTED = True    ← NOT touched (the decision itself)
alexGRecordLiveSetupStatus      PROTECTED = True    ← NOT touched
alexGIsSetupSignalStale         PROTECTED = True    ← NOT touched
alexGIsSetupEligibleForLiveTrading PROTECTED = True ← NOT touched
alexGLiveSignalId / alexGTradeId / alexGCloseLivePosition  PROTECTED = True ← NOT touched
```

**Additive means additive.** Every existing statement is byte-identical and unreordered; every
insertion is a call whose return value nothing reads. No rule, threshold, gate, entry, stop,
target, size, staleness limit or eligibility condition was read, moved or changed. The one deleted
line is the `statuses:` argument line, extended to also pass `pipeline:` — the parameter that has
existed unused since MOGO-013.

**Buffered, never inline.** The execution path is the one place where a stray `await` could sit
between a decision and its commit, so stages are pushed to a plain in-memory array and drained
**once**, by `alexGLivePollTick`'s existing seam, in its `finally` — so a tick that *throws* still
persists whatever stages it reached. The trading path never awaits an observation.

**Total by construction.** `alexGRecordPipelineStage()` wraps its entire body in `try/catch` and
returns nothing; a failure routes to the existing `evidenceRecordWriteFailure` channel. The buffer
is capped at 500 so a tick that somehow never drains cannot grow without bound.

## 5. PIPELINE semantics used — repository-native, nothing invented

All five stages come from `evidenceBuildPipelineObservation`'s own documented vocabulary. **No new
stage, no new observation kind, no new schema, no parallel evidence subsystem.**

| Stage | Emitted where | Meaning |
|---|---|---|
| `CANDIDATE` | top of `alexGAttemptOpenLivePosition`, **before** the bid/ask await | the setup cleared every eligibility gate and entered the execution path — so a candidate that dies inside `fetchBidAsk` still leaves evidence it existed |
| `REQUESTED` | paired with the existing `TRADE_OPEN_REQUESTED` event | bid/ask in hand, protected constructor not yet called |
| `REQUEST_FAILED` | DUPLICATE branch · construction-blocked branch · **ledger-commit-rejected branch** | carries the constructor's **own** `status` and `reason`, never a re-derived one |
| `OPENED` | **after `commitAlexGLedger()` returned ok** | a paper position that genuinely persisted |
| `CLOSED` | after the loop in `alexGCheckLivePositions`, at the ruling-C5 seam | a position that genuinely closed this tick |

**`OPENED` sits after the commit, not after construction — deliberately.** If the ledger rejects
the write, the position is rolled back; recording `OPENED` at construction time would durably assert
a paper trade that does not exist. Fixtures 2A.19–2A.22 exercise exactly that branch.

## 6. Identity linkage

Every stage carries `setupId` **and** `signalId`, and the execution stages additionally carry the
real `tradeId`. That closes the chain end to end:

```
EVALUATION observation (signalId, setupId)
  → CANDIDATE (same signalId, same setupId)
    → REQUESTED (same)
      → OPENED (same, plus tradeId)  ─── joins to alexGAccount.openPositions[].tradeId
        → CLOSED (same tradeId)      ─── joins to closedPositions[] and the evidence package
```

`occurredAt` for `OPENED` is the position's **own `openedAt`**, and for `CLOSED` its own
`closedAt` — not "now". Since `occurredAt` is part of the natural key, this makes those records'
keys **stable**, so a repeated emission is rejected by the UNIQUE index rather than duplicated.

## 7. Test design

New suite: **`tests/run_v017_step2a_pipeline_observability_tests.js`** — picked up automatically by
`tests/run_all.sh`.

It deliberately mirrors the harness of `v126_phase2c_wave1_tests.js`, **because that suite already
drives the real engine all the way to a genuine `TRADE OPENED`.** A synthetic-but-valid H1 candle
series runs through the real `alexGRunSetupEngine` / `alexGClassifyTouch` /
`alexGEvaluateRepeatedReaction` chain to produce an **organic** Repeated Zone Reaction setup; then
the real `alexGEvaluatePairForLiveSetups` → `alexGAttemptOpenLivePosition` → **real PROTECTED
`alexGConstructLivePosition`** → real `commitAlexGLedger` executes end to end. **The network is
stubbed at `fetch()` only** — never at an application function, never at a protected one.

## 8. Test results — **47 / 47 PASS**

| Requirement | Fixtures | Result |
|---|---|---|
| 1 · qualifying signal emits the expected progression | 2A.1–2A.9 | ✅ exactly `CANDIDATE → REQUESTED → OPENED` |
| 2 · the **real** path is exercised, not a mock | 2A.1, 2A.4, 2A.39 | ✅ a genuine position with a real `tradeId`; the protected constructor is called |
| 3 · OPENED only after confirmed successful open | 2A.4, 2A.5, 2A.20 | ✅ `tradeId` and `openedAt` match the account record |
| 4 · rejected setup does not falsely emit OPENED | 2A.10–2A.13 | ✅ a pre-activation setup records **no stage at all** |
| 5 · failed/refused execution does not emit OPENED | 2A.14–2A.22 | ✅ construction refusal **and** ledger rejection both → `REQUEST_FAILED`, no `OPENED`, account rolled back |
| 6 · duplicate/idempotent behaviour | 2A.9, 2A.23–2A.27, 2A.33 | ✅ duplicate → `REQUEST_FAILED(DUPLICATE)`, one position; drain empties; re-close records nothing |
| 7 · instrumentation failure cannot alter decisions | 2A.34–2A.38 | ✅ null/malformed/**circular** input never throws; with the buffer full the **real trade still opens** |
| 8 · protected ALEX behaviour unchanged | 2A.39–2A.42 | ✅ constructor still returns `TRADE OPENED` and its own named refusals — and calling it directly records **nothing**, proving the instrumentation is outside it |
| 9 · no writes into genuine forward evidence | 2A.43–2A.45 | ✅ no IndexedDB in-process; `localStorage` is a runner stub; **`evidencePutObservation` reached 0 times**, counted not assumed |
| 10 · no research-artifact contamination | 2A.46–2A.47, §9 | ✅ no new kind or stage invented; research corpus byte-unchanged |

The one genuinely decisive fixture pair: **2A.19–2A.22**. The position was constructed, the ledger
commit was rejected by the real `commitAlexGLedger` (via a stale known-version, exactly as a second
browser tab would cause), and the ledger recorded `REQUEST_FAILED(LEDGER_COMMIT_REJECTED)` with
**no `OPENED`** while the account rolled back to zero open positions. **`OPENED` cannot lie.**

## 9. Integrity results

| Gate | Result |
|---|---|
| Step 2A focused suite | ✅ **47 / 47 passed** |
| Canonical gate `tests/run_all.sh` | ✅ **19 suites · 1,160 fixtures · 1,160 passed · 0 failed · 0 execution errors** |
| Platform suite | ✅ **20 suites · 847 tests · 0 failures · 0 errors** |
| **Protected ALEX drift** | ✅ **0** — all 63 protected functions and 4 protected constants byte-identical |
| Campaign C1 | ✅ **33 / 33 · 0 missing · 0 mismatched · 0 unlisted** · `VERIFIED`; manifest SHA-256 `c23e72e0…` unchanged |
| Legacy corpus | ✅ **220 re-derived · 0 mismatched**; rollup `667ff4c7…` matches |
| Forward / research contamination | ✅ **none** — 2 research artifacts, 1 raw acquisition, byte-unchanged; `git status` over `docs/trader-intelligence`, `docs/campaigns`, `evidence/`, `docs/evidence`, `docs/strategy-fidelity`, `platform/` is **empty** |
| Repository changes | ✅ limited to `index.html`, two new test files, and this report |

### One failure was found, diagnosed and fixed — reported rather than smoothed over

The first canonical run came back **1,159 / 1,160 with one failure**: v128 fixture *"P2 capture is
installed AFTER the loop… capture must follow every close call"*. That fixture locates the **last
occurrence of the string `alexGCloseLivePosition`** in the function source and requires the capture
seam to come after it. My new CLOSED comment block sits below the seam and **mentioned that
function by name in prose**, so `lastIndexOf` found my comment.

**A test artifact of my wording, not an ordering regression** — every real close call is still
before the capture seam. **The fix was to reword my comment, not to weaken the fixture**, whose
intent is sound and still holds. The comment now says so explicitly, so the next person to write
there understands the constraint. Re-run: **1,160 / 1,160.**

### One pre-existing, disclosed condition, deliberately not changed

`regression-baseline-tools.py`'s `REPOSITORY_OWNED_SUITES = 17` / `REPOSITORY_OWNED_FIXTURES = 815`
and its `FIXTURE_COUNTS` table were **already stale before this milestone** (the gate reported
18 suites / 1,113 fixtures at MOGO-016). They are documentation, not enforced by the drift check,
which passed. Refreshing them means `--update`, which rewrites the whole integrity baseline
including `generatedFromAppVersion` and the protected-function hashes — out of scope for an
observability change, and exactly the kind of edit that should be its own reviewed decision.
**Left alone and disclosed. The gate now genuinely runs 19 suites / 1,160 fixtures.**

## 10. No genuine forward trade was manufactured

**Confirmed.** No genuine forward paper trade was created, forced or simulated. Every position
opened during testing exists only inside the offline JXA harness's in-memory state, in a process
with no IndexedDB and a stubbed `localStorage`. The live forward browser was **not reloaded, not
restarted and not touched**; its storage was not cleared and no existing forward observation was
modified. The genuine campaign continued writing on its own throughout (profile last written
20:06 local, by the campaign, not by this work).

## 11. ALEX rules, parameters and cutoff remain untouched

**Confirmed, and measured rather than asserted:** protected drift **0** across all 63 functions and
4 constants. No entry rule, filter, parameter, staleness limit (`maxLiveSignalAgeMinutes` H1 = 60,
unchanged) or the activation cutoff (`2026-08-11T02:43:57.894Z`, unchanged) was read, moved or
modified. The campaign was not re-baselined. `RULES_ALEXG_V11.v11Config.setupSuspensionEnabled`
remains `true` in production — the test process disables it **for that process only**, the same
disclosed pattern the v126 runner already uses, and v127 fixture K9 still asserts the production
default.

## 12. Will future genuine PIPELINE evidence distinguish candidate / request / open?

**Yes.** The next naturally occurring qualifying forward setup will durably record, in the MOGO-013
ledger and readable by exactly the method the Step 1 audit used:

- `CANDIDATE` — it entered the execution path (even if `fetchBidAsk` then failed);
- `REQUESTED` — the open was attempted against the protected constructor;
- `REQUEST_FAILED` — with the constructor's own status and reason, **or** `LEDGER_COMMIT_REJECTED`;
- `OPENED` — with the real `tradeId`, only if the paper position genuinely persisted;
- `CLOSED` — with the same `tradeId`, when it closes.

**This is what converts the Step 1 verdict from (B) into an evidence-backed (A) or (C)** the next
time a setup qualifies — no guessing required.

## 13. Remaining observability limitations

1. **Nothing is recorded until a setup passes every eligibility gate.** A setup rejected by the
   activation cutoff or staleness produces `EVALUATION` evidence (as it already did) but **no**
   PIPELINE stage — by design, because it never entered the execution path. Fixture 2A.11 pins this.
2. **The 60-minute H1 staleness exposure is unchanged and remains the live risk.** MOGO-016's host
   sleep gap was 127 minutes. A post-activation H1 setup qualifying during a sleep is still
   permanently lost. Step 2A makes that loss **visible**, not impossible. The AC-power
   recommendation stands.
3. **The pre-ledger blind window is not retroactively fixed.** Nothing can reconstruct
   02:43Z–14:59Z on 2026-08-11.
4. **A stage dropped at the 500-record buffer cap is silent to the trading path** (fixture 2A.37).
   That is the correct trade-off — never delay a trade for an observation — but it means a
   pathological tick could under-record. In practice the buffer drains every tick.
5. **No live production PIPELINE record exists yet**, and cannot until a setup genuinely qualifies.
   Step 2A proves the mechanism; only the campaign can produce the observation.
6. **`alexGLiveSetupStatuses` remains session-only** (`index.html:2195`), so the hourly
   re-creation behaviour Step 1 documented is unchanged. Out of scope here.

---

# ⚠️ WHAT STEP 2A DID **NOT** DO

> **MOGO-017 RESEARCH CHANGE DETECTION HAS NOT BEEN IMPLEMENTED BY STEP 2A.**

No `change_detection` module was written. No `SourceMutationDetected` event is emitted. No
`FIRST_OBSERVATION` / `UNCHANGED` / `CHANGED` classification exists. The acquisition capability,
the scheduler, the research authorization, the research artifacts and the connector are **entirely
untouched** by this step. Part A of this report remains a *plan*, not an implementation.

Step 2A closed a **forward paper-trading observability** gap. That is all it did.

**LIVE-MONEY TRADING REMAINS UNAUTHORIZED.**

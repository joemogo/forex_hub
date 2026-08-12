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

> **SUPERSEDED BY STEP 2C.** The two "not yet wired" assertions in this section were
> deliberately written as hard emptiness checks so that wiring them would BREAK A TEST rather
> than quietly start passing. Step 2C wired the detector and edited both, in a commit, with a
> reason. Both are now allow-lists, so a *third* consumer still breaks them. See Step 2C §2.

---
---

# MOGO-017 STEP 2B — CHANGE-DETECTION SAFETY BOUNDARY & CONTRACT

**Status: ✅ COMPLETE.** The contract is frozen as executable code and the contamination risk is
closed. **The production detector is NOT implemented and NOT wired.**
**PAPER TRADING ONLY — live-money trading remains unauthorized.**

## 1. Authoritative starting state

| | Verified before any edit |
|---|---|
| Repository | `origin` → `https://github.com/joemogo/forex_hub.git` |
| Branch / HEAD | `main` · **`d99916fc3077e8cec7def341f4a3d5ad773fcc68`** = Step 2A closeout |
| `git status --porcelain` | **empty — clean** |
| Ahead / behind `origin/mogo-main` | **0 / 0** |
| `git diff` | empty |

Exactly as expected. Nothing unexplained to absorb.

## 2. Same-source identity contract — **`(sourceId, resourceId)`**

Frozen in `runtime/change_detection.py` → `comparison_key(source_id, resource_id)`.

| Field | Where it already lives |
|---|---|
| `sourceId` | `tasks.subject_source_id` (`runtime/schema.py`); `SRC\|…` composite validated by `ids.require_composite_id`; the key of `connector_authorization.APPROVED_DESTINATIONS` and of `authorizations.resolve()` |
| `resourceId` | `capability_results.result_json.resourceId`, written by `acquire_approved_source_metadata.execute()` |
| ordering | `capability_results.recorded_at`, and authoritatively the append-only event log sequence |

**Two acquisitions belong to the same history** when both fields match — proven joinable today with
existing columns and indexes (the three-table join executed live in Step 1 §A3).

**`sourceId` alone is insufficient, and the reason is concrete:** this connector acquires metadata
**for one resource**. Two different videos under the approved channel would otherwise share a
history, and each acquisition would read as a mutation of the other. Catalog section I's metadata
row omits the resource because it addresses a *source as a whole*; this contract does not.

**No broader source abstraction was invented.** The key is returned as a **tuple**, not a joined
string, so no separator can be smuggled through an identifier to collide two streams.

## 3. Content identity contract — **the raw external byte hash**

> **SOURCE CONTENT IDENTITY = `connector_transport.content_hash(raw)` = SHA-256 over the exact
> validated external response body.**

Proven from code, not assumed:

```python
def content_hash(raw):
    """Deterministic identity of the acquired bytes. Never a timestamp."""
    return hashlib.sha256(raw).hexdigest()
```

| Question | Answer | Evidence |
|---|---|---|
| Algorithm | **SHA-256** | `hashlib.sha256(...).hexdigest()` |
| Exact response bytes? | **Yes** | `raw = response.read(max_bytes + 1)`; `content_hash(raw)` is called on that value |
| Headers participate? | **No** | `Content-Type` is read into `content_type` and recorded as a *field*; never hashed |
| Timestamps participate? | **No** | `acquiredAt` is an `AcquisitionOutcome` field, never an input to the hash |
| Request / execution ids? | **No** | idempotency key, commandId, taskId all live above the transport |
| Acquisition metadata? | **No** | `as_record()` is built *from* the outcome; the hash is computed *before* it |
| JSON re-serialization? | **No** | `json.loads(raw.decode("utf-8"))` is called **for validation only and its result is discarded** — key order and whitespace stay in the identity |
| URL / request metadata? | **No** | `requestedUrl` / `finalUrl` are recorded fields |

A static test pins this structurally: `content_hash` takes **exactly one positional argument**,
`raw`, with no `*args`, no `**kwargs` and no keyword-only arguments — so no timestamp, header, URL
or record can reach it even by a future edit.

### Why the research artifact wrapper hash is refused

`ingest.build_artifact_record()` hashes the bytes of the **wrapper document**, which embeds the
whole acquisition record — including `acquiredAt`, `decidedAt` and the decision's `requestedUrl`.
Those are `null` today **only because `acquire_approved_source_metadata.execute()` never passes a
clock** to `transport.acquire(request, now_iso=None, …)`. That is a provenance gap, not a design
guarantee.

The contract test demonstrates the trap directly: a wrapper with `acquiredAt: null` and the same
wrapper with a real timestamp hash **differently**, while the raw identity is unchanged. If anyone
fixes that gap — which MOGO-016's own report recommended — the wrapper hash would change on **every
scheduled acquisition** and every run would report a mutation. **The raw hash is immune by
construction, and the test pins it so the gap can be fixed later safely.**

Raw byte hashing **is** scientifically appropriate here, so no stop condition was triggered.

## 4. Accepted-content lifecycle boundary — **after validated durable ingestion**

Frozen in `change_detection.accepted_content_identity(acquisition_ok, ingestion_result)`, which
returns the content identity **only** when all of:

1. `acquisition_ok` — which already implies the connector gate permitted it, the final URL was the
   authorized one, the status was acceptable, the content type matched, the body was within the cap
   and the body parsed as UTF-8 JSON (all enforced in `connector_transport` *before* an ok outcome
   can exist);
2. `validationStatus == "VALID"` — ingestion's own permanent-validation rules passed;
3. `storedVerified` — the artifact was **re-read from disk and its hash re-derived**, so "stored"
   means stored rather than attempted;
4. a well-formed SHA-256 content hash is present.

**Why this boundary and not an earlier one.** A transport success is not scientific acceptance:
bytes can arrive HTTP 200 and still be refused as empty, oversized, non-UTF-8 or unstorable. If such
bytes became the baseline, one truncated or hostile response would silently redefine *what this
source says* — and the **next genuine** acquisition would be reported as a mutation, with the
corruption persisting as the new normal. Choosing the narrowest point that proves acquisition,
authorization, validation, identity, provenance **and** durable storage removes that whole class.

**`ingested` is deliberately NOT required.** A repeat acquisition of identical bytes reports
`ingested=false` / `duplicateStatus=DUPLICATE_ALREADY_INGESTED` because the artifact already exists
— the content is accepted, the *storage* was a no-op. Requiring `ingested` would make every
`UNCHANGED` observation, the normal case for a stable source, look like a failure.

## 5. Classification semantics — frozen, and closed

| Classification | Condition | Baseline |
|---|---|---|
| **`FIRST_OBSERVATION`** | accepted content exists, no prior accepted identity for this `(sourceId, resourceId)` | **establishes** it. **Not a mutation** |
| **`UNCHANGED`** | accepted identity **equals** the prior accepted identity | unchanged in value |
| **`CHANGED`** | accepted identity **differs** from the prior accepted identity | **advances**; both identities preserved for audit |
| **`ACQUISITION_FAILURE`** | `acquisition_ok` false | **must not move** |
| **`VALIDATION_FAILURE`** | acquired but not accepted | **must not move** |

`CLASSIFICATIONS` is a closed set, exactly partitioned into `BASELINE_ADVANCING` and
`BASELINE_PRESERVING` — asserted by test, so a future addition cannot land in neither or both.

**A new request identity, a new acquisition timestamp and changed transport metadata all resolve to
`UNCHANGED`**, because none of them reaches the content identity.

**`CHANGED_BYTES_THAT_FAIL_VALIDATION` is deliberately NOT a separate state.** It is
`VALIDATION_FAILURE`. The bytes never became accepted content, so **no legitimate comparison was
ever available** — naming it separately would imply a mutation was observed and then set aside. A
test pins that reading, across three distinct failure shapes.

**No unnecessary state was invented.** Five classifications, and `next_baseline()` is stated as its
own function precisely because *"a failure must not advance the baseline"* is the rule a future
caller is most likely to get wrong writing it inline.

**`CHANGED` is an observation, not a conclusion.** It means only: *previously accepted validated
content for this approved source and resource differs from newly accepted validated content.* It
authorises no interpretation, no hypothesis, no rule, no promotion, and no change to ALEX or any
trading behaviour.

**A mutation is not a failure.** `contracts/errors.py`'s `source_mutated` class is **not used** — a
test asserts it appears nowhere in the module body. `registry._validate_failure_classes()` would
refuse it anyway (it routes to review with no terminal path), but the deeper reason is semantic:
modelling a change as an execution failure would dead-letter a *successful* acquisition and lose the
very observation this milestone exists to make.

## 6. Synthetic test isolation architecture

**New module `runtime/research_corpus.py`** — one value object naming the two roots, and two ways to
get one:

```
production_corpus()            the real roots. The default. Unchanged.
sandbox_corpus(intake, arts)   test-owned roots, VALIDATED before construction.
```

**Dependency injection, not global mutation.** No mutable module state, no "current corpus" to set,
no environment variable, no context manager to forget to exit. Production callers pass nothing, so
production behaviour is unchanged **by construction rather than by convention**.

**No environment-variable backdoor, deliberately.** `MOGO_RUNTIME_STATE_ROOT` is right for runtime
state — ephemeral, git-ignored, rebuildable. The research corpus is committed scientific evidence. A
variable that can silently redirect where evidence is written is one that eventually will, including
in production. A caller wanting a different corpus must say so **in code, at the call site**. A test
asserts `os.environ`/`getenv` appear nowhere in the module.

**Fail closed, in the direction that matters.** The dangerous mistake is not "a test wrote somewhere
odd" — it is *"a test wrote into the real corpus while believing it was sandboxed."* So
`sandbox_corpus()` **refuses to construct** any corpus whose roots are, contain, or are contained by
either production root, compared through `os.path.realpath` so `..` and planted symlinks are
defeated. Both roots are validated independently, so one cannot be sandboxed while the other quietly
points at real evidence, and the two roots may not overlap each other.

**Contamination during the fixtures is therefore impossible by construction**, not by remembering.

## 7. Exact files and functions modified

| File | Change | Justification |
|---|---|---|
| `runtime/research_corpus.py` | **new** — `ResearchCorpus`, `production_corpus()`, `sandbox_corpus()`, `resolve_corpus()` | the isolation seam; pure path resolution, performs no I/O |
| `runtime/change_detection.py` | **new** — the frozen contract: `comparison_key`, `accepted_content_identity`, `classify`, `next_baseline` | pure; **imported by nothing in production**, pinned by test |
| `capabilities/ingest_local_artifact.py` | 5 seam edits (below) | the only production file touched |
| `tests/platform/test_runtime_change_detection_contract.py` | **new** — 53 tests | the contract and isolation proofs |
| `tests/run_platform_tests.sh` | +1 line registering the suite | a suite the runner does not enumerate is a suite that does not run |

**Every changed line in the production capability, justified:**

1. `+from .. import research_corpus` — the seam.
2. `INTAKE_ROOT` / `ARTIFACT_ROOT` now alias `research_corpus.PRODUCTION_*`. **Values are
   identical**; the names are retained so every existing reader, test and report keeps working. A
   test asserts they still equal the production roots.
3. `resolve_intake_path(artifact_ref, corpus=None)` — resolves against the corpus in force. The
   traversal/symlink confinement rule is applied to **whichever** corpus is active, so a sandbox is
   bounded exactly as strictly as production rather than being a hole in the check (tested with
   `../escape.json`, `/etc/passwd`, `acquired/../../x.json`).
4. `find_existing(content_hash, corpus=None)` — duplicate check against the corpus in force.
5. `execute(payload, corpus=None)` — threads the corpus to the four sites that touch a root.

**`corpus=None` resolves to production in exactly one place** (`resolve_corpus`), so no call site can
invent a different fallback. The orchestrator's `callable(payload)` dispatch is unchanged — an
optional keyword does not alter it — so **production writes exactly where it always did**.

**No test-only branch exists inside scientific production logic**, and no evidence-path validation
was weakened; the confinement rule got *stricter* coverage, not looser.

## 8. `SourceMutationDetected` — event-contract findings

| Question | Finding |
|---|---|
| Already approved? | ✅ **Yes** — present in `contracts/vocabulary.py` `EVENT_TYPES`, and `contracts/event.py` validates `eventType` against exactly that set. **No contract change needed.** |
| Required fields | the standard 14-field envelope: `eventId`, `eventType`, `eventVersion`, `workflowId`, `correlationId`, `causationId`, `producer`, `producerVersion`, `occurredAt`, `recordedAt`, `subjectRefs`, `payload`, `payloadHash`, `sequence` |
| Can it carry **prior** content identity? | ✅ yes — `payload` is free-form JSON-shaped |
| Can it carry **current** content identity? | ✅ yes — same |
| Source / resource identity | ✅ `subjectRefs` (a list of strings) plus `payload` |
| Audit / provenance identity | ✅ `producer`, `producerVersion`, `correlationId`, `causationId`, `taskId`, `policyContext` |
| Do current semantics match MOGO-017? | ✅ yes — Catalog section I already assigns metadata acquisition the `SourceMutationDetected` source-mutation behaviour |

### The manifest-hash concern from Step 1 — **resolved, and it is a non-issue**

**Emit it from the ORCHESTRATOR, not from the capability.** Established by precedent and pinned by
test: every capability manifest declares only `["TaskSucceeded","TaskFailed"]`, yet the orchestrator
already emits `PolicyEvaluated`, `AcquisitionAuthorized` and `AcquisitionDenied` — **none of which
appears in any manifest.** `emittedEvents` is stored at registration and **never consulted at emit
time**.

So emitting `SourceMutationDetected` from the orchestrator requires **no manifest edit, no
`capabilityId` bump, and no weakening of registration validation.** That is also semantically right:
the classification is a runtime observation *about a completed task*, exactly like `PolicyEvaluated`.

Emitting from the *capability* would require changing its manifest → changing its hash →
`register()` refusing it under an unchanged `capabilityId`, by design. **Step 2C should not do
that.** No production emission was added in Step 2B, and a test asserts the string appears in no
runtime module.

## 9. Focused tests — **53 / 53 PASS**

| Required proof | Fixtures |
|---|---|
| 1 · identical bytes, different request identities → identical identity | ✅ |
| 2 · volatile metadata does not alter the identity | ✅ incl. the static one-argument pin on `content_hash` |
| 3 · different bytes → different identities | ✅ incl. a single flipped byte |
| 4 · source/resource partitions streams correctly | ✅ incl. tuple-not-string, and malformed identity refused |
| 5 · acquisition failure cannot become accepted state | ✅ baseline provably unmoved |
| 6 · validation failure cannot become accepted state | ✅ |
| 7 · **changed-but-invalid** cannot become accepted state | ✅ across 3 failure shapes, and end-to-end through the real validator |
| 8 · `FIRST_OBSERVATION` is distinct from `CHANGED` | ✅ |
| 9 · synthetic writes cannot reach the genuine corpus | ✅ **the real `ingest.execute()` runs sandboxed; the genuine corpus listing is asserted byte-identical before/after** |
| 10 · production storage defaults unchanged | ✅ incl. no `os.environ` in the seam |
| 11 · isolation fails closed on an unsafe path | ✅ **7 overlapping-root shapes refused**, plus relative, empty, and self-overlapping roots |

Additional: a full `FIRST → UNCHANGED → CHANGED → failure → UNCHANGED` sequence driven through the
**real ingestion path** inside a sandbox, ending with the baseline correctly on the changed content
and **two** artifacts on disk (identical content created no second artifact).

## 10. Integrity results

| Gate | Result |
|---|---|
| Step 2B focused suite | ✅ **53 / 53** |
| Platform suite | ✅ **21 suites · 900 tests · 0 failures · 0 errors** |
| Canonical gate `tests/run_all.sh` | ✅ **19 suites · 1,160 fixtures · 1,160 passed · 0 failed** |
| **Protected ALEX drift** | ✅ **0** — 63 functions, 4 constants byte-identical |
| Campaign C1 | ✅ **33 / 33 · 0 mismatched** · `VERIFIED`; manifest SHA-256 `c23e72e0…` unchanged |
| Legacy corpus | ✅ **220 re-derived · 0 mismatched**; rollup `667ff4c7…` matches |
| Research corpus | ✅ **2 artifacts + 1 raw acquisition, byte-unchanged** — no synthetic fixture leaked in |
| Forward evidence | ✅ untouched; `index.html` **not modified at all** by Step 2B |
| Scheduler integrity | ✅ `platform/scheduling` unmodified; agent still loaded, `runs = 0` since the production install |
| Authorization integrity | ✅ `docs/trader-intelligence` unmodified — the authorization record is untouched |
| Repository changes | ✅ limited to 2 new runtime modules, 5 seam edits in one capability, 1 new test suite, 1 runner line, and this report |

No unexplained drift. Nothing stopped.

## 11. Remaining work for Step 2C

1. **The history query** — resolve the prior accepted identity for a `(sourceId, resourceId)` from
   `tasks` ⋈ `commands` ⋈ `capability_results`. Note `capability_results` has **no `source_id`
   column or index**; at current volume the join is free, and adding one should be a deliberate
   decision, not a reflex.
2. **The call site** — classify after validated ingestion in
   `acquire_approved_source_metadata.execute()`, adding `changeStatus`, `priorContentIdentity`,
   `priorObservedAt` to the result.
3. **Emit `SourceMutationDetected` from the orchestrator** on `CHANGED`, carrying prior + current
   identity and source/resource in `subjectRefs`. **Not from the capability** (§8).
4. **Thread `corpus=` through `acquire_approved_source_metadata.execute()`** so a Step 2C fixture can
   drive the whole acquire → ingest → classify chain sandboxed. Step 2B stopped at ingestion because
   that is where the contamination risk was.
5. **Surface `changeStatus` in `status` / `audit`.**
6. **Live proof** — one scheduled run classified `UNCHANGED` end to end, plus full gates.

**Still explicitly out of scope:** more sources, discovery, transcripts, strategy extraction,
hypothesis generation, rule promotion.

## 12. Scientific firewall

**RESEARCH CHANGE ≠ TRADING CHANGE.** Step 2B altered no ALEX code, no strategy parameter, no
execution logic; promoted no hypothesis; created no trading rule; entered no forward evidence; and
touched neither Campaign C1 nor the legacy corpus. `index.html` was not modified at all.

---

# ⚠️ PRODUCTION AUTONOMOUS CHANGE DETECTION IS **NOT** ENABLED

> **Step 2B froze the contract and closed the contamination risk. It did not start detecting.**

`runtime/change_detection.py` is imported by **nothing** in the running system — asserted by a test
that walks every runtime module. No `SourceMutationDetected` event is emitted from any production
path — asserted the same way. The scheduler, the acquisition capability, the connector, the research
authorization and the research artifacts are **entirely unchanged in behaviour**. The next scheduled
collection will behave exactly as it did before this step.

**LIVE-MONEY TRADING REMAINS UNAUTHORIZED.**

*(Step 2C then enabled it, deliberately and visibly. See below.)*

---
---

# MOGO-017 STEP 2C — AUTONOMOUS CHANGE DETECTOR IMPLEMENTATION

**Status: ✅ COMPLETE.** Production change detection is **wired, proven end to end, and
autonomously exercised by launchd.**
**PAPER TRADING ONLY — live-money trading remains unauthorized.**

## 1. Authoritative starting state

| | Verified before any edit |
|---|---|
| Repository | `origin` → `https://github.com/joemogo/forex_hub.git` |
| Branch / HEAD | `main` · **`0be18c1bc9717f0be0648780a92abaec22226b2e`** = Step 2B closeout |
| `git status --porcelain` / `git diff` | **empty — clean** |
| Ahead / behind `origin/mogo-main` | **0 / 0** |

## 2. Exact files and functions modified

| File | Change |
|---|---|
| `runtime/acquisition_history.py` | **new** — `prior_accepted()`, `classify_acquisition()`, `PriorAcceptedAcquisition` |
| `runtime/change_detection.py` | +2 **pure** adapters: `accepted_identity_from_acquisition()`, `classify_acquisition_result()` |
| `runtime/orchestrator.py` | +`_classify_acquisition()`; the classify→record→emit seam in the success path |
| `capabilities/acquire_approved_source_metadata.py` | `corpus=None` threaded through `execute()`, `preserve_raw()`, `acquired_root()` |
| `runtime/audit.py` | +`_change_detection_summary()`; one `status` line + recent classifications |
| `tests/platform/test_runtime_change_detection_wiring.py` | **new** — 18 fixtures |
| `tests/platform/test_runtime_change_detection_contract.py` | the two Step 2B "not yet wired" pins updated to allow-lists |
| `tests/run_platform_tests.sh` | +1 line registering the new suite |

**`index.html` was not touched.** No ALEX code, parameter, protected function, forward evidence,
Campaign C1 or legacy evidence was modified.

### The architectural decision that shaped this step

**Classification lives in the ORCHESTRATOR, not in the capability.** The execution context a
capability receives is `{attempt, taskId, leaseGeneration}` and deliberately carries **no database
handle** — so a capability physically cannot read history, and widening that boundary would be a far
larger change than this milestone permits. The orchestrator already holds the connection, already
emits the acquisition lifecycle, and is (per Step 2B §8) the correct emitter for an event that needs
no manifest declaration. Everything followed from that.

## 3. Prior accepted history lookup

`acquisition_history.prior_accepted(connection, capability_id, sourceId, resourceId,
exclude_idempotency_key)` reads `capability_results` for the acquisition capability, newest first,
and returns the first row that is **both** in the same `(sourceId, resourceId)` stream **and**
passes the Step 2B acceptance predicate.

**Ordering:** `recorded_at DESC, rowid DESC`. `recorded_at` is stamped by the orchestrator's clock,
which is guarded by a monotonic floor that **aborts rather than record a time earlier than the event
it follows** — a durable repository-native ordering, not a hopeful one. `rowid` breaks a
same-millisecond tie deterministically.

**A run never compares against itself** — `exclude_idempotency_key` omits the acquisition being
classified, because a replay may already have recorded it.

### There is no separate baseline store, and that is the design

A second store holding "the current accepted hash" would be a second source of truth that can
disagree with the history it summarises. The failure mode is nasty: a crash between recording an
acquisition and updating the baseline leaves them permanently inconsistent with nothing able to say
which is right. **Deriving the baseline from the history makes that class impossible** — the
baseline is not a value anyone maintains, it is the newest accepted row.

**Three independent reasons a failure cannot poison it:** the orchestrator records a result only for
a task that SUCCEEDED, so a failed acquisition never reaches the store; ingestion raises on empty,
oversized, non-UTF-8 or unstorable content, so a validation failure fails the task and records
nothing; and every candidate row is re-checked against the acceptance predicate anyway.

**Scalability, recorded honestly:** `capability_results` has no `source_id` column or index, so this
scans one capability's rows and filters in Python. At single-digit volume that is free, and **no
index was added** — optimising a table that fits in a cache line would be premature. If scheduled
collection ever reaches thousands of acquisitions per source, the right change is a generated column
plus an index, or a narrow projection table. It is **not** to weaken the acceptance filter.

## 4. Classifier logic

The Step 2B contract, unchanged and not duplicated. Two new **pure** adapters translate the
acquisition result shape, and they live in `change_detection.py` rather than at the call site so the
knowledge of *which hash is the scientific identity* stays in the module that defines it — a caller
reaching into the dict itself would be free to pick the wrong one.

`accepted_identity_from_acquisition()` reads the **top-level `contentHash`** (the raw external byte
hash) together with `ingestion.validationStatus` and `ingestion.storedVerified`. The nested
`ingestion` block deliberately carries no `contentHash` of its own, so there is **no ambiguity to
resolve**: the wrapper hash is not reachable from here.

## 5. Durable classification representation

The classification is written into the capability result **before** `result_store.record()`, so it
lands inside the one durable structure that already holds the acquisition — covered by that row's
verification hash, and queryable after a process restart (pinned by a test). **No second ledger.**

Recorded fields: `classification`, `reason`, `priorContentIdentity`, `currentContentIdentity`,
`contentHashAlgorithm`, `contentIdentityBasis`, `comparisonStream{sourceId,resourceId}`,
`priorAcquisitionKey`, `priorAcquisitionRecordedAt`, `contract`, `lane`, `promotionStatus`.

**Classification can never fail an acquisition.** The work is purely observational — the bytes were
already fetched, validated and durably stored before it runs — so every failure path returns rather
than raises, recording an honest `classification: "UNAVAILABLE"` with its reason. An absent field and
a field that could not be computed are different facts. Two fixtures prove the acquisition still
succeeds under a deliberately faulted classifier, **and that the degraded run still becomes the
baseline for the next one** — because the baseline is derived, not stored.

## 6. `SourceMutationDetected` emission path

Emitted by the **orchestrator**, `producer: "orchestrator"`, **only on `CHANGED`**, and only after
the acquisition it describes is durably recorded. Payload carries both identities, the stream, the
algorithm, the identity basis, the contract version, `lane: RESEARCH` and
`promotionStatus: NOT_A_TRADING_RULE`; `subjectRefs` carries source and resource.

Per Step 2B §8 this required **no manifest edit, no `capabilityId` bump and no weakening of event
registration validation** — `emittedEvents` is never consulted at emit time, and the orchestrator
already emits `PolicyEvaluated` / `AcquisitionAuthorized` / `AcquisitionDenied`, none of which
appears in any manifest. **A mutation is information about a SUCCESSFUL acquisition — never an
error, never a task failure, and `source_mutated` is not used.**

## 7. Deterministic Run A / Run B / Run C proof

Driven through the **real Orchestrator** on a temporary state root: real command contract, real
policy gate, real authorization record, real claim/lease, the real acquisition capability (connector
gate, permit derivation, transport limits, hashing, raw preservation), the real ingestion capability,
the real result store, the real event log. **Only two things are doubled** — the *socket*
(`connector_transport._opener`, so the real gate, permit, limits and validation all still run) and
the *corpus* (a Step 2B sandbox).

| Run | Request | Bytes | Classification | Prior → Current | Mutation event |
|---|---|---|---|---|---|
| **A** | R1 | A | **`FIRST_OBSERVATION`** | `null` → `hash(A)` | **0** |
| **B** | **R2 ≠ R1** | **A (identical)** | **`UNCHANGED`** | `hash(A)` → `hash(A)` | **0** |
| **C** | R3 | **B (different)** | **`CHANGED`** | `hash(A)` → `hash(B)` | **exactly 1** |

Asserted explicitly: `R1 ≠ R2` as idempotency keys while `contentHash(A) == contentHash(A)`;
`hash(A) ≠ hash(B)`; Run B's `priorAcquisitionKey` is Run A's key; the single mutation event carries
both identities, both stream fields, `producer: orchestrator`, `RAW_EXTERNAL_RESPONSE_BYTES`,
`RESEARCH` / `NOT_A_TRADING_RULE`; and the event log still parses, validates and hashes.

## 8. Failure proofs — all passing

| Proof | Result |
|---|---|
| 1 · acquisition failure (HTTP 500) | no result recorded, no classification, **no emission**; the next good run still compares against A |
| 2 · validation failure | same — unvalidated content never recorded as accepted |
| 3 · **changed bytes that FAIL validation** | **not `CHANGED`, no emission**; baseline still A, proved by a following run classifying `UNCHANGED` |
| 3b · wrong content type | refused; baseline unmoved |
| 4 · duplicate already-ingested valid content | `duplicateStatus=DUPLICATE_ALREADY_INGESTED`, `ingested=false`, still **`UNCHANGED`** |
| 5 · first accepted observation | **never** emits a mutation |
| 6 · different `resourceId`, same source | separate history — different bytes there are `FIRST_OBSERVATION`, **not** a mutation |
| 7 · different `sourceId` | separate history — no inheritance, proved at the history layer |
| 8 · a run never compares against itself | `exclude_idempotency_key` verified |

## 9. Sandbox end-to-end proof

Every fixture asserts the genuine research corpus listing is **byte-identical before and after**, in
`tearDown`, for all 18 tests. The raw acquired bytes and the research artifact both land in the
sandbox, verified by path. `sandbox_corpus()` had already refused to construct any corpus able to
reach the genuine one.

## 10. Production approved-source proof

One bounded real acquisition of the already-approved source through `mogo_runtime collect` — the
exact governed path, no arbitrary URL, no new source, no transcript access.

```
COLLECT source=SRC|youtube|c785970cc458 resource=hb7ot1_szWI operation=metadata
        window=W|21600|82708   issuedAt=2026-08-12T02:10:27.727Z
  PolicyEvaluated → AcquisitionAuthorized → TaskClaimed → TaskStarted
  CHANGE DETECTION UNCHANGED (prior=b668d4209abb current=b668d4209abb)
  TaskSucceeded → WorkflowCompleted        advanced=3 succeeded=1
```

**Observed classification: `UNCHANGED`** — HTTP 200, 794 bytes, `DUPLICATE_ALREADY_INGESTED`,
`ingested=false`, and it was still correctly `UNCHANGED` because content identity, not storage
outcome, decides. Baseline was the MOGO-016 acquisition of `2026-08-11T23:28:01.709Z`. **Zero
`SourceMutationDetected` events in the production log.**

This was observed, not assumed: the source *had* remained byte-identical. A natural `CHANGED` would
have been equally legitimate and would have been preserved and reported without altering the test
design. No interpretation of any content was performed.

## 11. Autonomous scheduler proof

The exact already-proven MOGO-016 mechanism, with the smallest temporary acceleration.

- Installed with a two-entry proof schedule; `runs = 0` before, `RunAtLoad=false`.
- **launchd fired it at 22:12:03 local**, `last exit code = 0`, **stderr empty**.
- The scheduled run traversed the complete chain and logged
  **`CHANGE DETECTION UNCHANGED (prior=b668d4209abb current=b668d4209abb)`**.

```
launchd → mogo_runtime collect → governed runtime → policy → authorization
       → connector gate → transport → validation → durable ingestion/dedupe
       → CHANGE CLASSIFICATION → audit → WorkflowCompleted
```

**Scheduler restored immediately** to the committed six-hour production cadence (00:00 / 06:00 /
12:00 / 18:00), verified loaded with `runs = 0`, and the committed spec is back to
`collectionWindowSeconds: 21600` with `git status platform/scheduling` empty. **No uncontrolled
repeated acquisitions**: two real production requests total this step.

## 12. Classification observed on the real Alex G acquisition

**`UNCHANGED`**, twice — once operator-triggered, once launchd-triggered. Content identity
`b668d4209abbf2b8718cea2fa84eacd3985cbb4d1fc352dd1720f64bebb92a00` on both sides.

## 13. Scientific firewall proof

Every occurrence of `SourceMutationDetected` in the repository, enumerated rather than assumed:

| File | Role |
|---|---|
| `contracts/vocabulary.py` | the approved-type declaration |
| `runtime/orchestrator.py` | **the one emitter** |
| `tests/platform/test_platform_envelopes.py` | pre-existing vocabulary test |
| `tests/platform/test_runtime_change_detection_{contract,wiring}.py` | these proofs |

**`index.html` — which carries ALEX and every trading path — has ZERO references.** No consumer
exists in ALEX, strategy parameters, strategy execution, forward paper evidence, Campaign C1, legacy
evidence, rule promotion, hypothesis promotion or live-money trading. **No unexpected trading-lane
consumer was found**, so no stop condition was triggered.

A test additionally scans the detector's **code** (docstrings stripped via AST, because both modules
*document* the prohibition) for `alexG`, `ALEX`, `paperAccount`, `openPaperPosition`, `Campaign`,
`tradingRule`, `hypothesis`, `promoteRule` — none present.

## 14. Integrity results

| Gate | Result |
|---|---|
| Step 2C focused suite | ✅ **18 / 18** |
| Step 2B contract suite | ✅ **55 / 55** (2 pins updated to allow-lists) |
| Platform suite | ✅ **22 suites · 919 tests · 0 failures · 0 errors** |
| Canonical gate | ✅ **19 suites · 1,160 fixtures · 1,160 passed · 0 failed** |
| **Protected ALEX drift** | ✅ **0** — 63 functions, 4 constants byte-identical |
| Campaign C1 | ✅ **33 / 33 · 0 mismatched** · `VERIFIED`; manifest `c23e72e0…` unchanged |
| Legacy corpus | ✅ **220 re-derived · 0 mismatched**; rollup `667ff4c7…` matches |
| Research corpus | ✅ **2 artifacts + 1 raw acquisition, byte-unchanged** — identical bytes correctly deduped, no synthetic fixture leaked in |
| Forward / trading lane | ✅ `index.html`, `docs/campaigns`, `evidence/`, `docs/evidence`, `docs/strategy-fidelity`, `docs/trader-intelligence` all unmodified |
| Authorization controls | ✅ unchanged; every run passed the real policy gate and authorization record |
| Scheduler controls | ✅ restored to six-hour production cadence, `runs = 0`, committed spec at 21600 |
| Dedupe behaviour | ✅ unchanged — `DUPLICATE_ALREADY_INGESTED`, no second artifact |

### Four test failures were found, diagnosed and fixed — reported, not smoothed over

1. **Two Step 2B pins broke by design.** `test_no_production_module_imports_change_detection` and
   `test_no_source_mutation_event_is_emitted_anywhere_yet` were written as hard emptiness checks
   precisely so wiring would **break a test** rather than quietly start passing. Both were rewritten
   as **allow-lists** — so a *third* consumer still breaks them — plus a new test asserting **no
   capability** imports the contract.
2. **My own test helper was wrong** — it read `record.envelope`; the event log exposes `record.event`.
   A test-harness defect, not a wiring defect.
3. **My firewall scan matched prose.** Both detector modules *document* the prohibition ("no change
   to ALEX", "promotes no hypothesis"), so a raw text scan flagged the very sentences describing the
   firewall. Fixed by stripping docstrings via AST and scanning code — and the fix is self-checked.
4. **A path literal tripped a legitimate guard.** My permitted-consumer list spelled out the package
   path, whose substring `platform/contracts` is exactly what `test_platform_boundaries` scans for
   when proving no suite reaches the retired flat directory. Fixed by building the paths from
   components — **the guard was not weakened.**

## 15. Scheduler final state

Loaded, `state = not running`, `runs = 0`, four calendar entries at **00:00 / 06:00 / 12:00 / 18:00**
local, `collectionWindowSeconds: 21600`. **Not left accelerated.**

## 16. Remaining limitations

1. **No production `CHANGED` has ever been observed** — the source has been byte-stable across six
   acquisitions since MOGO-015. `CHANGED` is proven deterministically, not in the wild, and no test
   asserts the source will ever change.
2. **The three pre-2C MOGO-016 rows carry no `changeDetection` field.** They are still valid accepted
   *history* — the acceptance predicate reads validation and storage, not the classification — but
   they are not retroactively classified, and nothing backfills them.
3. **Classification degrades to `UNAVAILABLE` rather than failing**, by design. A pathological
   classifier fault would leave a gap in the *record* while leaving the *baseline* correct.
4. **`capability_results` has no `source_id` index** — correctness first; see §3.
5. **One resource, one source.** The comparison stream is keyed for more, but only one is approved.
6. **The wrapper-hash provenance gap is still open** (`acquiredAt`/`decidedAt` null). Change
   detection is immune by construction and pinned by test, so it can now be fixed safely — but it
   has not been fixed.

## 17. Can MOGO now answer the question?

> **"Did the accepted content for this approved source/resource change since the prior accepted
> acquisition?"**

**Yes — autonomously, durably, and without an operator comparing hashes by hand.**

A scheduler-triggered acquisition classifies itself against the prior *accepted* content for its own
`(sourceId, resourceId)` stream, records the verdict inside the durable acquisition result, emits
`SourceMutationDetected` on `CHANGED` only, and surfaces the answer in `mogo_runtime status`:

```
  change detection: UNCHANGED=1
      UNCHANGED         SRC|youtube|c785970cc458/hb7ot1_szWI  b668d4209abb -> b668d4209abb  2026-08-12T02:10:27.909Z
```

---

# ⚠️ MOGO-017 WAS NOT DECLARED COMPLETE AT STEP 2C

Step 2C delivered the detector. The milestone closeout was a separate, explicitly authorized step.
*(Performed in Step 3, below.)*

**LIVE-MONEY TRADING REMAINS UNAUTHORIZED.**

---
---

# MOGO-017 STEP 3 — PROVENANCE REPAIR, OPTIMIZATION, CLOSEOUT

## 1. Starting state — with one discrepancy, reported rather than absorbed

| | Verified before any edit |
|---|---|
| Repository | `origin` → `https://github.com/joemogo/forex_hub.git` |
| Branch / HEAD | `main` · **`900b54fcbb851d134fda1c6039dacfe15012b9a8`** |
| `git status` / `git diff` | **empty — clean** |
| Ahead / behind | **0 / 0** |

⚠️ **The checkpoint in the Step 3 instruction was `900b54fcbb851d134fd1c6039dacfe15012b9a8` — 39
characters.** A SHA-1 is 40. Comparing against the actual HEAD shows a single dropped `a`
(`…134fd1c…` vs `…134fda1c…`); `git rev-parse` cannot resolve the supplied string at all
(*"Needed a single revision"*). HEAD **is** the Step 2C commit, it **is** on `origin/mogo-main`, and
the tree is clean. **A transcription slip in the instruction, not repository drift** — so this was
reported and work continued rather than stopping.

## 2. The provenance gap — root cause

| Field | Why it was null |
|---|---|
| `acquiredAt` | `connector_transport.acquire(request, now_iso=None, …)` takes the instant as a **parameter**; the capability called it **without one**, so `AcquisitionOutcome.acquiredAt` was always `None`. |
| `decidedAt` | `connector_authorization.evaluate()` reads `request.get("decidedAt")`; the capability's request dict **had no such key**. |
| `decision.requestedUrl` | **Correct as-is — left alone.** The gate compares a caller-supplied URL against the derived one to catch substitution; `None` truthfully means *"the caller named no URL"*, which is the safest state. The capability physically cannot supply it — the URL is derived **by** the gate, inside `acquire()` — and duplicating that derivation to fill a field would create the second URL source the anti-SSRF design exists to prevent. The URL is already recorded on `decision.approvedUrl` and on the result's `requestedUrl` / `finalUrl`. |

**Root cause: a dropped value, twice. Both timestamps already had a home; nobody passed them.** No
missing mechanism, no schema gap.

**No existing test relied on the nulls.** The `decidedAt` hits elsewhere in the suites are the
*authorization record's* `decidedAt` — a different field entirely.

## 3. Why the obvious fix would have been wrong — measured, not assumed

The wrapper written to `intake/acquired/<contentHash>.json` embeds the acquisition record, and
**that document's bytes are what ingestion hashes to derive the research artifact's identity.**

```
wrapper hash, acquiredAt = null            64a653a9507a120f
wrapper hash, run 1 real timestamp         c1bb457eeec9d24c
wrapper hash, run 2 real timestamp         948418488b8f4dad     ← different again
```

Writing the timestamps straight into the wrapper would mint **a new research artifact every six
hours forever**, with `duplicateStatus` reading `NEW` permanently. Change detection would have been
fine — it compares raw external bytes — but **artifact dedupe would not**, and dedupe is the
content-addressing discipline the whole research corpus rests on.

### And the second-order trap, also caught before shipping

The first repair *removed* the two keys. That changes the wrapper's **shape**, which changes its
bytes:

```
existing committed production wrapper   d4e4ec829fe80b576a1304f4
key-deleted form                        7cd5fd3740ccb7c6f339d8dc     ← would mint ONE new artifact
```

So the final repair **pins the fields to `null` rather than deleting them**, keeping the wrapper
**byte-identical to every artifact already committed**. A test now rebuilds the genuine MOGO-015
artifact under the repaired code and asserts byte equality, so this can never regress.

## 4. The repair

`capabilities/acquire_approved_source_metadata.py` only:

- **one** authoritative instant per acquisition — `clock_module.SystemClock().now_iso()`, read
  **once** and used for both fields, so the gate decision and the fetch can never disagree about
  when the same acquisition happened;
- passed as `decidedAt` in the gate request (**the gate already reads it — no gate change**) and as
  `now_iso=` to `transport.acquire` (**the transport already accepts it — no transport change**);
- `VOLATILE_PROVENANCE_FIELDS` + `stable_acquisition_record()` pin those two fields in the
  content-addressed wrapper.

**`connector_transport.content_hash` was not touched. Scientific change identity was not touched.
Dedupe semantics were not touched. No historical artifact was rehashed, rewritten or migrated.**

## 5. Optimization

A bounded review of the MOGO-017 code found **one** genuine duplication, and it was removed:

`classify_acquisition_result()` was rebuilding a **synthetic ingestion-shaped dict** purely to
re-enter `classify()` — a round trip that could only ever go wrong — and the prior-hash validation
existed in that one path only. Both entry points now share a single `compare()` core, so they cannot
drift apart. **Behaviour identical, proven by all 72 pre-existing change-detection tests passing
unchanged.**

**Everything else was left alone deliberately.** `PriorAcceptedAcquisition` is used once but makes
the orchestrator read `prior.idempotencyKey` instead of `prior[1]`. `acquisition_history._stream_of`
overlaps `comparison_key` only superficially — one is a lenient reader of stored data, the other a
validating constructor. The two test harnesses differ because they test different layers. **No
cosmetic refactor was performed.**

Two stale docstrings were corrected, because this codebase's discipline is that comments must be
true: `change_detection.py` still claimed *"nothing in the running system imports it yet"* and *"null
today only because the capability never passes a clock"* — both false after Steps 2C and 3.

## 6. Provenance proofs — 8 new fixtures, all passing

| Proof | Result |
|---|---|
| 1 · populating `acquiredAt` does not alter content identity | ✅ identity still `hash(bytes)` |
| 2 · populating `decidedAt` does not alter content identity | ✅ |
| 3 · differing provenance between runs of identical bytes | ✅ **`UNCHANGED`**, no event, **one** artifact |
| 4 · wrapper stays byte-identical across runs | ✅ and the fields are **pinned, not deleted** |
| 4b · the **committed production artifact** rebuilds byte-identically | ✅ no churn, no migration |
| 5 · historical artifacts with null provenance stay compatible | ✅ acceptance reads validation and storage, never provenance |
| 6 · valid changed bytes still `CHANGED` | ✅ exactly one event |
| 7 · invalid changed bytes still not `CHANGED` | ✅ no event, baseline held |
| 8 · `FIRST_OBSERVATION` still distinct from `CHANGED` | ✅ |

Plus: the two timestamps are asserted **equal**, proving one clock read rather than two.

## 7. Live production confirmation

One bounded acquisition of the approved source through the governed path — no new source, no
arbitrary URL, no transcript access, **scheduler cadence untouched** (the plist stayed at six hours;
only the spec's window was narrowed for one command and restored immediately).

```
CHANGE DETECTION UNCHANGED (prior=b668d4209abb current=b668d4209abb)
advanced=3 succeeded=1

acquiredAt          : 2026-08-12T02:39:58.418Z
decision.decidedAt  : 2026-08-12T02:39:58.418Z      ← same authoritative instant
classification      : UNCHANGED
ingestion           : DUPLICATE_ALREADY_INGESTED  ingested=False
```

**`git status docs/trader-intelligence` → empty.** Provenance populated, zero artifact churn, zero
mutation events, research corpus still exactly 2 artifacts + 1 raw acquisition.

## 8. Forward paper health — from persisted evidence only

**The live browser was not touched, reloaded or restarted.**

| Check | Status |
|---|---|
| Durable observation flow | ✅ **active** — WAL written at 22:40, the minute it was checked |
| Ledger growth | ✅ **2,636 record headers**, up from 2,060 at MOGO-016 |
| New polling gap | ✅ **none** — zero sleep/wake events since the 17:01 wake |
| Step 2A PIPELINE instrumentation | ✅ **installed in the repository** (8 references) |
| Natural CANDIDATE / REQUESTED / OPENED evidence | ⚠️ **none yet — and it cannot exist yet** |
| Genuine paper trades | **still zero** |

⚠️ **The running tab predates the instrumentation.** Its last page-load marker is **Aug 11 17:02**;
Step 2A landed at **19:47**. The PIPELINE wiring is in the committed file but **not in the page
currently executing**, so it will begin recording only on the next natural page load — which was
deliberately not forced. Absence of PIPELINE evidence today is therefore expected, and is **not**
evidence about the execution path.

**Zero trades is not treated as a failure.** Step 1 established the reason and nothing has changed
it: only one setup has qualified since activation, and it was already stale. No new evidence
suggests a malfunction. No trading behaviour was modified.

## 9. Scientific firewall

Every occurrence of `SourceMutationDetected`: the vocabulary declaration, `orchestrator.py` as the
**one** emitter, and three test files. **`index.html` — ALEX and every trading path — has zero
references.** No consumer in strategy parameters, execution, forward evidence, Campaign C1, legacy
evidence, rule promotion, hypothesis promotion or live-money trading.

## 10. Final MOGO-017 success audit

| # | Condition | Result |
|---|---|---|
| 1 | Unchanged accepted content → `UNCHANGED` | ✅ deterministic **and** twice in production |
| 2 | Valid changed content → `CHANGED` | ✅ with exactly one event |
| 3 | Prior/current identities preserved for audit | ✅ in the durable record and on the event |
| 4 | `FIRST_OBSERVATION` handled correctly | ✅ never emits a mutation |
| 5 | Failures never masquerade as mutations | ✅ incl. changed-but-invalid |
| 6 | Duplicate/idempotency behaviour correct | ✅ `ingested=false` still `UNCHANGED` |
| 7 | Scheduled autonomous acquisition traverses the classifier | ✅ launchd-triggered, logged |
| 8 | Research remains RESEARCH ONLY | ✅ `lane: RESEARCH`, `NOT_A_TRADING_RULE` |
| 9 | No research content in the forward trading lane | ✅ 0 forward evidence packages |
| 10 | Protected ALEX functions unchanged | ✅ **drift 0** — 63 functions, 4 constants |
| 11 | Campaign C1 intact | ✅ **33/33**, manifest hash unchanged |
| 12 | Legacy evidence intact | ✅ **220 re-derived, 0 mismatched** |
| 13 | Scheduler safety intact | ✅ six-hour cadence, `runs = 0`, spec at 21600 |
| 14 | Authorization fail-closed | ✅ every run passed the real gate and record |
| 15 | Provenance correct, or limitation justified | ✅ repaired; `requestedUrl` justified in §2 |
| 16 | All integrity gates green | ✅ below |
| 17 | Repository clean and synchronized | ✅ |

## 11. Final integrity results

| Gate | Result |
|---|---|
| Provenance + change-detection wiring suite | ✅ **28 / 28** |
| Change-detection contract suite | ✅ **55 / 55** |
| Forward PIPELINE observability suite | ✅ **47 / 47** |
| Platform suite | ✅ **22 suites · 929 tests · 0 failures · 0 errors** |
| Canonical gate | ✅ **19 suites · 1,160 fixtures · 1,160 passed · 0 failed** |
| **Protected ALEX drift** | ✅ **0** |
| Campaign C1 | ✅ **33 / 33 · 0 mismatched** · `VERIFIED` |
| Legacy corpus | ✅ **220 re-derived · 0 mismatched** |
| Research corpus | ✅ **2 artifacts + 1 raw acquisition, byte-unchanged** |
| Research ↔ forward contamination | ✅ **none, both directions** |
| Authorization | ✅ unchanged, fail-closed |
| Scheduler state | ✅ 00:00 / 06:00 / 12:00 / 18:00, `runs = 0` |

Two boundary tests failed during this step and both were **my defects, fixed rather than excused**:
a comment naming `index.html` (a prohibited literal only `boundaries.py` may contain), and the
earlier key-deletion approach. **No guard was weakened.**

## 12. MOGO-018 direction — autonomous research library (DOCUMENTED, NOT IMPLEMENTED)

MOGO research acquisition is intended to become **continuous infrastructure**. The operator should
not have to approve routine acquisition of an already-approved item.

```
AUTONOMOUS RESEARCH → governed approved-source acquisition → validation → dedupe
  → change detection → provenance → LIBRARY ORGANIZATION
  → strategy-specific corpus growth → corpus maturity assessment
  → proposed mechanical strategy specification
  → ★ OPERATOR REVIEW / FREEZE ★
  → preregistered validation
  → ★ OPERATOR PROMOTION DECISION ★
  → isolated forward paper strategy campaign
```

**Candidate families:** TJR · CRT · ICT · continued Alex G · other explicitly approved sources later.

**Strategy lanes stay isolated.** Each future strategy carries its own version, frozen rules, source
provenance, configuration identity, historical validation evidence, forward paper account, trades,
performance metrics and adjudication history. ALEX · TJR · CRT · ICT · MOGO-derived remain separate
lanes that never share an account or an evidence store.

**Routine research and library building may become autonomous. Governance remains mandatory at every
promotion boundary:** strategy specification freeze; preregistration/validation authorization;
promotion to forward paper trading; modification of a frozen forward strategy; and any future
live-money authority.

**Immediate MOGO-018 mission:** turn accumulated research artifacts into an organized,
source-attributed, per-strategy **library** — the layer between "we have artifacts" and "we can
assess corpus maturity". Not extraction, not hypotheses, not rules.

## 13. Final repository state

Clean · `0 ahead / 0 behind origin/mogo-main` · scheduler on its six-hour production cadence.

---

# ✅ MOGO-017 — COMPLETE — GREEN

## AUTONOMOUS RESEARCH CHANGE DETECTION

MOGO can now answer, autonomously and durably:

> **"Did the accepted content for this approved source/resource change since the prior accepted
> acquisition?"**

```
launchd → scheduling adapter → governed runtime → authorization → approved connector
  → bounded transport → validation → durable ingestion / dedupe
  → prior accepted content lookup → FIRST_OBSERVATION | UNCHANGED | CHANGED
  → SourceMutationDetected on CHANGED only → durable status/audit → workflow completion
```

**LIVE-MONEY TRADING REMAINS UNAUTHORIZED.**

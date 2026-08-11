# MOGO-014 — Autonomous Research Acquisition Integration
## Step 1: Repository Truth Audit (READ-ONLY)

**Date:** 2026-08-11 · **HEAD:** `8b7a49cd843f18452250401ff6e962a82f00a77e` · **Nothing implemented**
**Forward campaign:** running, untouched — ALEX ON, cutoff `2026-08-11T02:43:57.894Z`, 637 durable observations
**PAPER TRADING ONLY — live-money trading remains unauthorized**

---

## 1. Executive summary

Two beliefs going in were correct, and one assumption I had carried from earlier milestones was **wrong**. Repository evidence, not summary:

**Correct — the automation runtime is real.** 25 modules, 9,263 lines, 17 dedicated test suites covering identity, envelopes, task states, boundaries, authorization, capability, dead-letter, end-to-end, event log, lease, orchestrator, policy gate, projection, recovery, retry, review disposition, store schema. This is production-shaped infrastructure, not scaffolding.

**Correct — it cannot currently do anything.** All three registered capabilities are **pure demonstrations**: `echo`, `fail_then_succeed`, `policy_probe`.

**WRONG, and this changes the plan — no research script can acquire anything.** I previously described the research pipeline as "34 scripts covering discover→acquire→ingest". Direct evidence:

```
grep -rE "^(import|from)\s+(urllib.request|requests|httpx|http.client|socket|aiohttp)" scripts/
→  NONE
```

`acquisition_common.py` states it in its own header: *"Pure Python standard library. NO NETWORK ACCESS ANYWHERE IN THIS MODULE… Normalizing a URL never fetches it."* `transcript_normalize.py`: *"NO NETWORK ACCESS. NO LLM."* **MOGO has an acquisition *state machine*, not an acquisition *mechanism*.** The 18-state pipeline, schemas, dedupe and priority scoring are all real — they manage metadata about sources that a human supplies.

**The blocking gate is explicit, coded, and all-or-nothing.** `registry.py` refuses any effectful capability via `A5_EFFECTFUL_GATE` — four preconditions, of which **one is satisfied**:

| Gate | Satisfied | Requires |
|---|---|---|
| `policy_gate` | ✅ **True** | classification, authorization records, enforcement tests |
| `a5_result_store` | ❌ False | idempotency-keyed result store, output verification by re-hash, duplicate-effect prevention, post-execution recovery rule |
| `first_connector_authorization` | ❌ False | implementation authorization (ADR-012 D-15, *approved in principle*) |
| `acquisition_authorization_record` | ❌ False | one governance authorization record per real source — **"the mechanism exists, the records do not"** |

**The recommendation follows from that gate.** The first real capability should be **local research-artifact ingestion** — effectful, high-reuse, and requiring **no network connector at all** — and MOGO-014's first act should be a small governance amendment making the gate *per-capability* rather than global, so a capability that opens no socket is not blocked by a connector authorization it will never use.

**Nothing proposed here touches ALEX, the forward campaign, or the browser.** The work is entirely Python, entirely Lane B.

---

## 2. Repository state

| | |
|---|---|
| Branch | `main` (tracks `origin/mogo-main`) |
| HEAD | `8b7a49cd843f18452250401ff6e962a82f00a77e` — *MOGO-013: record activation results* |
| Working tree | **clean** (0 tracked modifications) |
| Sync | **0 ahead / 0 behind** |
| APP_VERSION | `12.19.0` |
| Recent tags | `campaign-c1-adjudication-complete`, `campaign-c1-pre-adjudication-frozen`, `v12.19.0`, `mogo-003-complete`, `mogo-002-complete` |
| Test commands | `tests/run_all.sh` (canonical gate) · `tests/run_platform_tests.sh` (platform only, no browser) |

**Relevant directories:** `platform/` (1.0 MB) · `scripts/trader_intelligence/` (616 KB, 34 scripts) · `scripts/knowledge_engineering/` (224 KB, 6 scripts) · `docs/trader-intelligence/` (43 MB corpus).

---

## 3. Automation runtime inventory

| Component | Module | Status |
|---|---|---|
| Capability registration | `registry.py` (443) | **IMPLEMENTED, PRODUCTION-USABLE** — manifest validation, SHA-256 of canonical form, re-registration rules, effect-class gate |
| Orchestration | `orchestrator.py` (1,616) | **IMPLEMENTED, PRODUCTION-USABLE** |
| Workers | `worker.py` (119) | **IMPLEMENTED** — thin by design |
| Durable store | `store.py` (154) + `schema.py` (464) | **IMPLEMENTED** — SQLite, append-only triggers, UNIQUE idempotency keys |
| Event logging | `event_log.py` (336) | **IMPLEMENTED, PRODUCTION-USABLE** |
| Retries | `retry.py` (334) | **IMPLEMENTED** — backoff via `_schedule_retry` |
| Leases | `lease.py` (158) | **IMPLEMENTED** |
| Authorization | `authorizations.py` (340) | **IMPLEMENTED MECHANISM, ZERO RECORDS** |
| Policy gate | `policy.py` (329) | **IMPLEMENTED, PRODUCTION-USABLE** — the one satisfied A-5 gate |
| Audit records | `audit.py` (850) | **IMPLEMENTED, PRODUCTION-USABLE** |
| Verification | `projection.py` (656) + CLI `verify` | **IMPLEMENTED** |
| Failure handling | `errors.py`, dead-letter | **IMPLEMENTED** — dedicated test suite |
| Human approval | review disposition + `authorizations.py` | **IMPLEMENTED** — authority must be `operator:`/`governance:`/`legal:`; `worker:`, `orchestrator`, `capability:`, `CAP|`, `WRK|` **refused outright** |
| **Scheduling / triggers** | — | **NOT FOUND** — only `_schedule_retry` (backoff) and SQLite triggers. Work is driven by CLI `submit` → `run` |
| **Idempotency-keyed result store** | partial | **INCOMPLETE** — `idempotency_key TEXT NOT NULL UNIQUE` exists on commands; no result store with output re-hash verification |

**Contracts layer:** `ids` (596), `command` (283), `task_states` (251), `boundaries` (244), `event` (243), `vocabulary` (220), `errors` (218).

---

## 4. Registered capability inventory

| Capability | ID | Class | Reality |
|---|---|---|---|
| `research.runtime.echo.v1` | `CAP\|research\|runtime-echo` | pure | **DEMONSTRATION** — "Prove the runtime kernel, not obtain anything." Reads no file, opens no socket, spawns no process, reads no clock, uses no randomness |
| `research.runtime.fail-then-succeed.v1` | — | pure | **DEMONSTRATION** — exercises retry/dead-letter |
| `research.policy.probe.v1` | — | pure | **DEMONSTRATION** — exercises the policy gate |

**Real effectful capabilities: ZERO.** The echo module states the prohibition explicitly: *"It does not acquire internet data, modify scientific evidence, perform replay, paper trade, live trade, modify strategies, ingest educator knowledge, or call an external model. It cannot: no such code path exists anywhere in the runtime, and the boundary tests prove it."*

---

## 5. Real research tool inventory

34 scripts in `scripts/trader_intelligence/`. Characterisation by evidence: **23 write files · 15 have a `__main__` CLI · 22 validate · 22 handle duplicates · 16 handle provenance · 9 hash · 0 access the network.**

### Strong candidates for capability wrapping

| Module | Purpose | I/O | Network | Provenance / identity | Duplicate | Callable by runtime |
|---|---|---|---|---|---|---|
| `ingest.py` | Ingestion driver; orchestrates sibling scripts via `subprocess.run([sys.executable, path])` | local files → evidence artifacts | **none** | yes | yes | **Yes** — CLI + importable |
| `evidence_registry.py` | Evidence artifact storage/registration | JSON → `docs/trader-intelligence/evidence/` | none | yes | yes | Yes |
| `validate_evidence.py` | Schema/consistency validation | evidence JSON → verdict | none | — | — | Yes |
| `evidence_dedup.py` / `detect_duplicates.py` | Duplicate detection | corpus → groups | none | — | **core purpose** | Yes |
| `graph_common.py` | **Canonical JSON, SHA-256, content hashing, atomic writes** — reused by the others | pure utility | none | **the identity primitive** | — | Yes |
| `acquisition_common.py` | 18-state acquisition machine, transitions, URL normalisation, vocabularies | pure | **explicitly none** | yes | yes | Yes |
| `register_source.py` | Register a source candidate | metadata → candidate JSON | none | yes | yes | Yes |
| `transcript_normalize.py` | Transcript normalisation | text → normalised | **explicitly none** | yes | — | Yes |
| `build_research_queue.py` / `query_research_queue.py` | Queue construction/query | corpus → queue | none | — | — | Yes |
| `hypothesis_proposals.py` / `rule_candidate_proposals.py` | Hypothesis & rule-candidate generation | evidence → proposals | none | yes | — | Yes |

**Failure behaviour:** these are CLI scripts using exit codes and exceptions; none implements retry, lease or dead-letter — which is precisely what the runtime would supply.

### Corpus state

`evidence/` **7,699 files** · `intake/` 30 (including completed ALEX transcripts) · `acquisition/` 10 (schemas, weights, empty queue/reports) · `proposals/` 10 · `queues/` 4 (READMEs + a validation queue) · `rule-registers/` 2.

**The acquisition queue is empty — `queue-snapshot.json` holds 0 items.** Infrastructure without inventory.

---

## 6. Existing automation ↔ research connection points

**Already compatible:**
- Research scripts are plain Python with `__main__` guards and importable functions → a capability can call them directly, no rewrite.
- `graph_common.sha256_hex` / `content_hash_of` / `canonical_json_bytes` supply exactly the deterministic identity the runtime's `ids.idempotency_key` needs.
- `ingest.py` already shells out via an argv list (`subprocess.run([sys.executable, path])`) — a precedent for driving sibling scripts safely.
- `authorizations.resolve(connection, source_id)` is the natural gate for "may this source be ingested?".
- Policy gate, audit, event log, retry, lease and dead-letter are all live and tested.

**Adapters required:** a capability module per research operation, translating a runtime command payload into script arguments and the script's output into a `TaskSucceeded` result — the same shape as `echo.py`, roughly 100–150 lines.

**Missing:** capability registration for anything effectful (gated); a scheduler/trigger; an idempotency-keyed result store with output re-hash; and **at least one authorization record**.

**No new framework is warranted.** The runtime supports the required workflow; the obstacles are three governance/plumbing gates, not architecture.

---

## 7. Missing minimum pieces

1. **`a5_result_store`** — idempotency-keyed result store, output verification by re-hash, duplicate-effect prevention, post-execution recovery rule.
2. **`first_connector_authorization`** — ADR-012 D-15 approved *in principle*; implementation authorization not granted.
3. **`acquisition_authorization_record`** — mechanism exists; **zero records exist**.
4. **A scheduler/trigger** — nothing fires work; CLI-driven only.
5. **A capability adapter** for the chosen research operation.

**A structural observation worth acting on.** `assert_effect_class_permitted()` refuses *any* non-default effect class while *any* of the four gates is unsatisfied. So a capability that only reads and writes local files — opening no socket — is blocked by `first_connector_authorization`, a gate about network connectors it will never use.

This is the same failure mode `platform/README.md` records historically about the `__init__.py` rule: *"an over-generalisation of a real constraint… enforced by a test, which turned a wrong rule into policy."* The README's own instruction is to **narrow such a rule to what actually causes the problem**. Making the gate per-capability is small, precedented, and reduces risk rather than weakening it.

---

## 8. Top 3 first-capability candidates

### Candidate A — Local research-artifact ingestion + evidence registration

Ingest an operator-approved artifact already present in `docs/trader-intelligence/intake/`: validate → canonical hash → duplicate check → register into the evidence corpus → audit record.

| | |
|---|---|
| Value | **High** — produces real research evidence and exercises the whole chain |
| Effort | **Low–Medium** — wraps `ingest.py` / `evidence_registry.py` / `validate_evidence.py` / `graph_common` |
| Risk | **Low** — no network, local writes into an existing versioned corpus, reversible via git |
| Auditability | **High** — every artifact hashed, git-diffable |
| Reproducibility | **High** — deterministic from local bytes |
| Reuse | **Highest** — near-total |
| Provenance | **High** — existing provenance fields |
| Idempotency | **High** — content hash is the natural key; dedupe already implemented |

### Candidate B — Acquisition-candidate registration from an operator-approved source list

Register sources into the (currently empty) acquisition queue via `register_source.py` + the 18-state machine.

Value **Medium** (metadata only — no research content) · Effort **Low** · Risk **Very low** · Auditability **High** · Reproducibility **High** · Reuse **High** · Provenance **High** · Idempotency **High** (candidate id + URL normalisation).

### Candidate C — Network acquisition of one approved source

| | |
|---|---|
| Value | **Highest long-term** — the only path to genuine autonomous discovery |
| Effort | **High** — requires the first network code in `scripts/`, a connector, secret handling |
| Risk | **Medium–High** — first external egress; robots/ToS; the known constraint that captions are server-blocked while catalogue/description retrieval works |
| Reuse | Medium — the state machine exists; the fetcher does not |
| Idempotency | Medium — remote content can change between fetches |

**Correctly deferred.** It requires all three unmet gates *and* new effectful network code simultaneously — the largest possible first step.

---

## 9. Recommended first capability

> ## Candidate A — Local research-artifact ingestion
>
> `research.ingest.local-artifact.v1`

**Why.** It is the only candidate that is genuinely effectful, reuses nearly all existing research code, produces real scientific value, and **needs no network connector** — so it can proceed under a *narrowed* effect gate without granting external egress. It exercises trigger → authorization → validation → hashing → dedupe → ingestion → durable storage → audit end to end, which is exactly the vertical slice that proves the runtime can do real work. Once it exists, Candidate C becomes an incremental change to the acquisition step rather than a leap.

---

## 10. Proposed minimum vertical slice

```
CLI trigger (mogo_runtime submit)         ← no scheduler needed for the first slice
      ↓
authorizations.resolve(sourceId)          ← REFUSE if no record; authority must be
      ↓                                      operator:/governance:/legal:
policy gate classification                ← already satisfied and tested
      ↓
read artifact from docs/trader-intelligence/intake/   ← local bytes, no network
      ↓
validate_evidence / schema validation
      ↓
graph_common.content_hash_of()            ← deterministic identity
      ↓
duplicate check against evidence corpus   ← existing dedupe
      ↓
ingest + evidence_registry write          ← the one effectful act
      ↓
result store keyed by idempotency key     ← NEW (satisfies a5_result_store)
      ↓
event log + audit record                  ← existing
      ↓
human-readable report
```

### Required behaviours

| Scenario | Required outcome |
|---|---|
| **Successful first acquisition** | Artifact validated, hashed, stored; `TaskSucceeded` with content hash; audit record; result stored under the idempotency key |
| **Duplicate second acquisition** | **No second write.** Recognised by content hash → result replayed from the store → `TaskSucceeded` marked duplicate. Counts must not inflate |
| **Transient failure** | Retry with existing backoff; each attempt event-logged; dead-letter after the configured limit |
| **Permanent validation failure** | `TaskFailed` with the validation reason; **nothing written to the corpus**; audit record retained |
| **Authorization denial** | Refused **before** any read or write; `TaskFailed` naming the missing/expired authorization; no partial state |

---

## 11. Authorization and policy model

Reuse `authorizations.py` unchanged. A record requires `authorizationId`, `sourceId`, `policyStatus`, `policyVersion`, `decisionAuthority`, `decidedAt`, `permittedOperations`; optionally retention/deletion/redistribution/model-training restrictions, `expiresAt`, supersession and audit history. Authority must be human or governance; machine prefixes are refused outright. Records are hashed and superseded rather than edited, so history cannot be rewritten.

**MOGO-014 must create the first record.** It is a governance act, not code — and per the gate's own text, *"the mechanism exists, the records do not."*

---

## 12. Provenance / identity / duplicate model

- **Identity:** `graph_common.content_hash_of()` over canonical JSON bytes — the same discipline the evidence platform uses (`mogo.evidence-canon.v1`), and the reason duplicates are detectable at all.
- **Provenance:** source id, authorization id, capability id and version, task id, timestamps, and the tool version — recorded on the artifact.
- **Duplicates:** content hash is the natural key. A repeat ingestion must be a **no-op returning the original result**, never a second artifact. This mirrors MOGO-013's `naturalKey` UNIQUE index and MOGO-011's `bySourceTradeId` unique index — an established pattern.
- **Never:** identity derived from filename, timestamp or ingestion order.

---

## 13. Failure and retry model

Reuse the existing retry, lease, dead-letter and recovery machinery — all already tested (`test_runtime_retry`, `test_runtime_dead_letter`, `test_runtime_recovery`).

**The one genuinely new piece is the A-5 recovery rule.** Crash boundary 8 — interrupted between performing the effect and recording success — is currently safe *only because every capability is pure*. An effectful capability breaks that argument, which is exactly why `a5_result_store` is gated. The slice must therefore: write the artifact **content-addressably** (so a repeat write is a no-op), record the result under the idempotency key, and on recovery re-derive the hash and compare rather than re-executing blindly.

---

## 14. Scientific firewall

**Structural separation, verified:**

1. **Different files.** Lane B lives in `platform/**`, `scripts/**`, `docs/trader-intelligence/**`. ALEX's behaviour lives in `index.html`. This slice touches no HTML.
2. **The drift gate enforces it.** 64 protected functions and 4 protected constants are byte-compared every canonical run; a Lane B change reaching ALEX would fail before commit.
3. **No write path exists.** The runtime has no code path to `index.html`, localStorage, IndexedDB, the paper account, or the observation ledger.
4. **The activation cutoff bounds the sample.** No research output can retroactively enter the running forward sample.

**Procedural rule, restated because it is the one that is not structural:** research output is a **hypothesis candidate only**. It may not become an ALEX rule, filter, threshold or parameter without traversing HYPOTHESIS → PREREGISTRATION → REPLAY/TEST → VERIFICATION → ADJUDICATION → a new strategy version → a new forward campaign.

---

## 15. Forward campaign isolation assessment

| Requirement | Needed? |
|---|---|
| Restart the forward browser | **No** |
| Clear browser storage | **No** |
| Modify the activation cutoff | **No** |
| Change the observation ledger | **No** |
| Change ALEX protected functions | **No** |
| Change ALEX configuration | **No** |

**None of the proposed work requires any of them.** It is Python executed from the shell, writing to the repository. The campaign is unaffected — during this audit it continued normally, accumulating from 609 to **637** durable observations with the cutoff intact.

---

## 16. Integrity / regression baseline — verified today, not assumed

| Baseline | Verified now |
|---|---|
| Campaign C1 | ✅ **33/33 · 0 missing · 0 mismatched · 0 unlisted** |
| Legacy corpus | ✅ **220 re-derived · 0 mismatched**, rollup matches |
| Protected-function drift | ✅ **0** — 63 functions, 4 constants |
| Platform test suite | ✅ passes (`tests/run_platform_tests.sh`, exit 0, no browser) |
| Repository | ✅ clean, 0 ahead / 0 behind |

**Commands to run after implementation:**

```bash
bash tests/run_platform_tests.sh                              # platform suites (no browser)
bash tests/run_all.sh                                         # canonical gate + drift
python3 regression-baseline-tools.py                          # protected-function drift
node scripts/mogo_evidence_verify.js --campaign-c1-attest     # Campaign C1
node scripts/mogo_evidence_leveldb_extract.js --store <preserved> --baseline verify
```

`tests/run_all.sh` uses `osascript` against `index.html` as a file and does **not** touch the running browser.

---

## 17. Files likely requiring modification

| File | Change |
|---|---|
| `platform/src/mogo_platform/runtime/registry.py` | Narrow `A5_EFFECTFUL_GATE` to be **per-capability**; mark `a5_result_store` satisfied once built |
| `platform/src/mogo_platform/runtime/capabilities/ingest_local_artifact.py` | **NEW** — the capability adapter |
| `platform/src/mogo_platform/runtime/result_store.py` *(or into `store.py`/`schema.py`)* | **NEW** — idempotency-keyed result store + output re-hash |
| `platform/src/mogo_platform/runtime/cli.py` | A submit path for the new command |
| `tests/platform/test_runtime_ingest_capability.py` | **NEW** — fixtures incl. duplicate, denial, transient and permanent failure |
| `tests/platform/test_runtime_result_store.py` | **NEW** |
| `tests/run_platform_tests.sh` | Register the new suites |
| `docs/trader-intelligence/authorizations/*.json` | **NEW** — the first authorization record(s) |
| `MOGO_014_AUTONOMOUS_RESEARCH_ACQUISITION.md` | Updated with results |

Existing research scripts should be **called, not modified**.

## 18. Files that must remain untouched

- **`index.html`** — all ALEX strategy logic, parameters, protected functions, the evidence platform and the observation ledger
- **`regression-baseline.json`**, `regression-baseline-tools.py` protected lists
- **`evidence/`** — Campaign C1's 33 artifacts
- **`docs/campaigns/C1/**`** — manifest, attestation, adjudication
- **`MOGO-013-PRE-LEDGER-EPHEMERAL-RECOVERY.json`** — hashed, immutable
- `~/MOGO-EVIDENCE-PROFILE/**` and `~/MOGO-EVIDENCE-PRESERVED/**` — the live profile and checkpoints
- `tests/v128_evidence_platform_tests.js` and the v12x suites — except to *add*, never to weaken
- The 7,699 existing evidence artifacts — new artifacts only, no rewrites

---

## 19. Risks and limitations

| Risk | Severity | Note |
|---|---|---|
| **Narrowing the effect gate is a governance change** | **Medium** | It must narrow the rule to what each capability actually needs — never disable it. Requires explicit authorization and its own tests |
| Crash boundary 8 with a real effect | Medium | The reason `a5_result_store` is gated; content-addressed writes plus a result store are the mitigation, and must be mutation-tested |
| First authorization record sets precedent | Medium | Its shape will be copied; worth getting right once |
| No scheduler | Low | The first slice is CLI-triggered; scheduling is a later, separable step |
| Research scripts lack retry/lease semantics | Low | The runtime supplies them; scripts stay unchanged |
| Corpus growth | Low | 43 MB today; ingestion adds artifacts to a versioned tree |
| **Autonomous discovery still absent afterwards** | — | Stated plainly: Candidate A ingests what a human placed. It does not make MOGO self-directed. That arrives with Candidate C |

---

## 20. Recommended MOGO-014 implementation sequence

1. **Governance — narrow the effect gate.** Make `A5_EFFECTFUL_GATE` per-capability so a non-connector capability is not blocked by connector authorization. Tests prove a network-declaring capability is still refused.
2. **Build the idempotency-keyed result store** with output verification by re-hash and the post-execution recovery rule → satisfies `a5_result_store`.
3. **Create the first acquisition authorization record** for one approved local source → satisfies `acquisition_authorization_record`.
4. **Write `research.ingest.local-artifact.v1`** as a thin adapter calling existing research scripts.
5. **Register it and run the vertical slice once**, end to end.
6. **Prove the five behaviours**: success, duplicate no-op, transient retry, permanent validation failure, authorization denial.
7. **Run the full baseline** (§16) and confirm C1, corpus, drift and the forward campaign are unchanged.
8. **Only then** consider a scheduler, and separately consider Candidate C with its own connector authorization.

Steps 1–3 are gates. Steps 4–6 are the slice. Step 7 is proof.

---

# Operator summary

**1. What autonomous research can MOGO perform today?**
**None.** The runtime executes only three pure demonstration capabilities and refuses effectful ones by design. The 34 research scripts are manual CLI tools. Nothing is scheduled and nothing fires on its own.

**2. What remains manual?**
Everything: choosing sources, obtaining content, running ingestion, validating, registering evidence, building queues, generating hypotheses. **And more than expected — no script can fetch anything.** MOGO has an acquisition state machine, not an acquisition mechanism. Every byte of research content in the repository was placed there by a human.

**3. What should we connect rather than rebuild?**
Almost everything. The runtime (orchestration, retry, lease, policy, audit, event log, verification, dead-letter) is production-shaped and tested. The research scripts already validate, hash, deduplicate and store with provenance. `authorizations.py` is a complete authorization mechanism with zero records in it. **The two halves have never been introduced to each other — that is the whole gap.** No new framework is justified.

**4. What is the single best first real autonomous capability?**
**`research.ingest.local-artifact.v1`** — ingest an operator-approved artifact already sitting in `intake/`: validate, hash, dedupe, register into the evidence corpus, audit it. Genuinely effectful, maximum reuse, **no network**, fully reproducible, and it exercises the entire chain the runtime was built for.

**5. What should we build next?**
Three small gates, then one thin adapter: **(a)** narrow the effect gate so it is per-capability rather than all-or-nothing; **(b)** build the idempotency-keyed result store with re-hash verification; **(c)** create the first authorization record; then **(d)** a ~150-line capability that calls existing scripts, and run the slice once end to end.

One caveat worth holding onto: this makes MOGO *governed and automatic*, not yet *self-directed*. It will ingest what you put in front of it. Genuine autonomous discovery needs the network connector — deliberately the second step, not the first.

---

*Read-only audit. The only repository write was this file. No code, configuration, evidence, strategy or runtime state was modified, and the forward campaign was not touched.*

---
---

# STEP 2 — IMPLEMENTATION AND LIVE PROOF

**Status: ✅ COMPLETE.** MOGO performed its first genuine governed autonomous research operation on 2026-08-11.

## Files changed

| File | Change |
|---|---|
| `platform/src/mogo_platform/runtime/result_store.py` | **NEW** — idempotency-keyed result store; `lookup()` re-derives the hash and refuses a corrupt row |
| `platform/src/mogo_platform/runtime/capabilities/ingest_local_artifact.py` | **NEW** — the effectful capability |
| `platform/src/mogo_platform/runtime/registry.py` | four A-5 conditions satisfied (each names its implementation); `unmet_a5_preconditions()` made capability-scoped; `uses_connector()` added |
| `platform/src/mogo_platform/runtime/schema.py` | `capability_results` table + index |
| `platform/src/mogo_platform/runtime/orchestrator.py` | capability registered + wired; result-store replay before dispatch; record before announcing success |
| `platform/src/mogo_platform/runtime/audit.py` | corrected a now-stale operator message claiming no effectful capability may register |
| `platform/src/mogo_platform/contracts/vocabulary.py` | `IngestLocalArtifact` added to the closed command vocabulary |
| `docs/trader-intelligence/authorizations/AUTH-alexg-risk-management.json` | **NEW** — the first authorization record |
| 5 test files | boundaries, capability, envelopes, store schema, end-to-end — updated deliberately (below) |

## Reused, not rebuilt

Orchestrator, worker, lease, retry, dead-letter, event log, audit, policy gate, `authorizations.py`, registration, projection/verify, `ids` hashing. The capability is ~250 lines and calls existing machinery. **No new framework.**

## The A-5 gate

Four enforcing conditions, each now satisfied *by an implementation named in the code*: idempotency-keyed result store, output verification by re-hash, duplicate-effect prevention (runtime replay **and** content-addressed writes — two independent mechanisms), and the boundary-8 recovery rule (look up the key rather than re-run).

**Connector gates remain UNMET and are still enforced for connector-using capabilities.** `uses_connector()` fails **closed**: an unreadable manifest is treated as connector-using. A capability naming a connector, or declaring `discover`/`metadata`/`transcript`, is still refused.

## Tests updated deliberately — narrowed, never deleted

Several boundary tests asserted "every capability is pure" and "the A-5 gate is closed". Those were correct when every capability was a demonstration; the first effectful capability makes them **wrong rules enforced by tests** — the failure mode `platform/README.md` records correcting once before. Each was **narrowed and paired with a stricter replacement**:

- purity boundary now exempts the named effectful module, which is instead governed by new `test_the_effectful_capability_reaches_nothing` — forbidding `socket`, `ssl`, `http`, `urllib`, `requests`, `httpx`, `subprocess`, `ctypes`, `random`, `secrets`, and any reference to `index.html`, `alexG`, `localStorage`, `indexedDB`, `paperAccount`;
- the A-5 test was **inverted, not deleted** — its own docstring predicted this governance moment;
- refusal machinery is proven still live by un-satisfying one condition inside the test;
- new `test_a_connector_using_capability_still_needs_the_connector_gate`.

## Live proof

**RUN 1 —** `PolicyEvaluated → queued` · `AcquisitionAuthorized` · `TaskClaimed` · `TaskStarted` · **`TaskSucceeded`** · `WorkflowCompleted`. `succeeded=1`.

Artifact `RART|193966d9f5d3e19bee2bcd81ada1454a`, hash `193966d9…4618b1`, 16,073 bytes, from `completed/alexg-risk-management.txt`, `lane: RESEARCH`, `promotionStatus: NOT_A_TRADING_RULE`, `networkAccessPerformed: false`. **Re-hash of the source bytes matches the stored hash.**

**RUN 2 —** `DUPLICATE SUPPRESSED`. **Artifacts on disk: still 1.** No second scientific artifact.

**Authorization enforced:** the first attempt was **DENIED** (`no_subject_source` → `blocked` → `awaiting_review`) because the subject source was in the payload rather than `inputRefs`. The gate refused before any effect. That denial was a real, unplanned demonstration of the gate working.

## Regression and integrity

| Check | Result |
|---|---|
| Platform suite | **0 failures** |
| Canonical gate | **0 failed** |
| Protected ALEX drift | **0** |
| Campaign C1 | **33/33 · 0 mismatched** |
| Legacy corpus | **220 re-derived · 0 mismatched** |
| Forward campaign | ALEX ON, cutoff `2026-08-11T02:43:57.894Z` **unchanged**, $10,000.00, 0/0, ledger **968** observations and rising |

## Limitations

Ingests only what a human placed in intake — **not self-directed**. No scheduler (CLI-triggered, as authorized). Network acquisition still gated. Retry/transient paths are covered by the existing suites rather than by a new ingestion-specific transient test.

## Next step

**One capability, then stop:** a scheduled trigger, or the connector authorization for network acquisition. Both are separate milestones.

---
---

# MOGO-014 — MILESTONE CLOSEOUT

**Closeout date:** 2026-08-11 · **Documentation only — no functionality added**
**Every figure below was re-verified at closeout, not carried forward from earlier sections.**

## 1. Implementation commit

`194c091cdec32bd633c9e443e1c60c3331f2a37f` — *MOGO-014: first effectful autonomous research capability*

## 2. First real capability

**`research.ingest.local-artifact.v1`** — `CAP|research|ingest-local-artifact`, `effectClass: effectful`, `operationClass: acquisition`, `acquisitionOperations: ["artifact"]`, `requiredConnectors: []`.

MOGO's first capability that is not a demonstration.

## 3. Successful real artifact

`docs/trader-intelligence/intake/completed/alexg-risk-management.txt` → **`RART|193966d9f5d3e19bee2bcd81ada1454a`**
Content hash `193966d9f5d3e19bee2bcd81ada1454ab25d649e92e1d7117cba22b5cc4618b1` · 16,073 bytes.

## 4. Confirmed behaviours

| # | Behaviour | Confirmed |
|---|---|---|
| 1 | Governed runtime performed dispatch | ✅ `TaskClaimed → TaskStarted → TaskSucceeded → WorkflowCompleted`; no operator ran the research script |
| 2 | Authorization was enforced | ✅ policy gate evaluated every task; `AcquisitionAuthorized` recorded on the permitted run |
| 3 | **Initial incorrect authorization denied BEFORE effect** | ✅ `PolicyEvaluated → blocked`, `AcquisitionDenied`, `HumanReviewRequired`, reason `no_subject_source` — **no file was read or written** |
| 4 | Corrected explicit authorization permitted execution | ✅ record `9e24aa04-c7b5-4438-acaf-c709cd8796b5`, `operator:joemogollon`, `PERMITTED_EXPLICIT_LICENSE`, operations `artifact` |
| 5 | Validation succeeded | ✅ existence, extension, UTF-8, non-empty, size within the 2 MB cap |
| 6 | Deterministic content hashing succeeded | ✅ SHA-256 of the real bytes; **independently re-derived from the source file and matched** |
| 7 | Provenance preserved | ✅ origin class, intake ref, claimed source id/title/url, authorization id, capability + version, `acquisitionPerformed: false`, `networkAccessPerformed: false`, and an explicit note that source attribution is the operator's **claim**, not verified |
| 8 | Durable result stored | ✅ artifact written content-addressed and **re-read and re-hashed after writing**; runtime result recorded under the command's idempotency key |
| 9 | Duplicate second run suppressed | ✅ `DUPLICATE SUPPRESSED` |
| 10 | **Only one scientific artifact exists** | ✅ **1** file in `research-artifacts/`, re-counted at closeout |
| 11 | Research lane / firewall preserved | ✅ `lane: RESEARCH`, `promotionStatus: NOT_A_TRADING_RULE`, and the promotion path recorded **on the artifact itself** |

## 5. Final integrity state — re-verified at closeout

| Check | Result |
|---|---|
| Platform suite | **0 failures** |
| Canonical gate | **1,113 passed · 0 failed** |
| Protected ALEX drift | **0** — 63 functions, 4 constants byte-identical |
| Campaign C1 | **33 / 33 · 0 missing · 0 mismatched · 0 unlisted** |
| Legacy corpus | **220 re-derived · 0 mismatched**, rollup matches |

## 6. Forward-campaign isolation — re-verified at closeout

| | |
|---|---|
| ALEX | **ON**, polling active |
| Activation cutoff | **`2026-08-11T02:43:57.894Z` — unchanged** |
| Paper balance | **$10,000.00**, 0 open / 0 closed |
| MOGO-014 artifact in the forward lane | **None.** Forward evidence packages: 0; the research artifact lives only in the research corpus |
| Durable observations | **977 and accumulating normally** |
| Browser reload | **None** — page continuous since `2026-08-11T14:57:16.607Z` (the MOGO-013 activation) |
| Browser storage | **Untouched** |

## 7. Limitation — stated plainly

> **MOGO is now capable of governed automatic research ingestion, but external research acquisition remains unavailable because no authorized network acquisition connector exists.**

MOGO ingests what a human places in the governed intake area. It cannot fetch. No research script imports a network client, the connector gates `first_connector_authorization` and `acquisition_authorization_record` remain **UNMET and enforced**, and `uses_connector()` fails closed. This is governed and automatic — **not self-directed**.

## 8. Recommended next milestone

### MOGO-015 — Governed External Research Acquisition

**Objective:** connect ONE bounded, explicitly authorized external research source to the MOGO-014 ingestion pipeline.

```
APPROVED SOURCE → CONNECTOR AUTHORIZATION → NETWORK ACQUISITION → SOURCE PROVENANCE
→ CONTENT HASH → VALIDATION → DUPLICATE CHECK → EXISTING RESEARCH INGESTION
→ DURABLE STORAGE → AUDIT → REPORT
```

**Reuse, do not recreate:** `research.ingest.local-artifact.v1`, the result store, the policy gate, `authorizations.py`, retry/lease/dead-letter, audit and event log. MOGO-015 should add a *connector* and let the proven ingestion path do the rest.

Prefer a known approved trading-research/educator source. **No unrestricted internet discovery.** Scheduling comes only after the bounded connector is proven, as the smallest step that lets acquisition fire without manual submission.

One constraint already on record: captions are server-blocked (HTTP 200 / 0 bytes), while `curl` with a User-Agent does yield the channel catalogue, descriptions and publish dates — so metadata acquisition is the realistic first connector target, not transcripts.

---

# MOGO-014 STATUS: COMPLETE

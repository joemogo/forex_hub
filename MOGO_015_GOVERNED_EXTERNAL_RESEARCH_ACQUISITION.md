# MOGO-015 — Governed External Research Acquisition
## Step 1A: Connector Target Verification (READ-ONLY)

**Date:** 2026-08-11 · **Starting HEAD:** `a0d567c352b0b05d914c3b38c46ee92b464bda54`
**Status:** ✅ **Step 1A COMPLETE — target verified and selected** · ⏸️ **connector NOT implemented**
**PAPER TRADING ONLY — live-money trading remains unauthorized**

---

## Repository starting state

| | |
|---|---|
| Branch / HEAD | `main` · `a0d567c` (MOGO-014 closeout) |
| Working tree | clean · 0 ahead / 0 behind |
| MOGO-014 implementation | `194c091` — `research.ingest.local-artifact.v1` proven |
| Forward campaign | ALEX **ON**, cutoff `2026-08-11T02:43:57.894Z`, $10,000.00, 977+ durable observations |

---

## Source selected — derived from repository evidence, not invented

**Alex G**, the educator behind the frozen ALEX strategy, chosen for continuity with the running forward campaign.

Authoritative record: `docs/strategy-fidelity/audit/alex-channel-catalogue.json`

| Field | Value |
|---|---|
| Channel | `fxalexg` |
| Channel ID | `UCgPeeHdxYRal0HTNeAkjqLg` |
| Channel URL | `https://www.youtube.com/@fxalexg__` |
| Authenticity | **`channel_verified`** |
| Prior enumeration | 200 videos, MOGO-002.8, **"Read-only metadata retrieval; no caption or transcript access"** |
| Registered ALEX_G sources present | **9 of 9** |

This is an existing, verified repository record with a stated completeness caveat. **No URL was guessed or fabricated.**

---

## Network constraint — verified, not assumed

Two bounded requests, one to each candidate path. No evasion technique was used and no access control was probed.

| Path | Result |
|---|---|
| **Public oembed metadata API** — `youtube.com/oembed?url=…&format=json` | ✅ **HTTP 200 · 794 bytes · `application/json`** |
| **Caption/transcript** — `youtube.com/api/timedtext?v=…&lang=en` | ❌ **HTTP 200 · 0 bytes** |

**The MOGO-014 closeout finding is confirmed exactly:** transcripts return a successful status with an empty body; metadata returns real data.

Real payload received (truncated):

```json
{"title":"How to Start Trading with Just $50","author_name":"fxalexg ",
 "author_url":"https://www.youtube.com/@fxalexg__","type":"video",
 "provider_name":"YouTube", ...}
```

**An unplanned but valuable corroboration:** the `author_url` YouTube itself returned matches the channel URL recorded in the repository. The external service independently confirms the source identity MOGO already held — which is exactly the kind of cross-check a provenance model should be able to make.

---

## Decision

> **First connector target: bounded metadata acquisition via YouTube's public oembed API, scoped to the authorized Alex G channel.**

**Why this and not the alternatives:**

- **It is a documented, purpose-built public metadata API** — not scraping, not `ytInitialData` parsing, not an access-control workaround. The milestone forbids evasion, and this avoids the question entirely by using the interface the provider publishes for this purpose.
- **It returns genuine external research data** — title, author, canonical author URL, thumbnail — enough to prove real acquisition and real provenance.
- **It is small and bounded** — one host, one scheme, one endpoint shape, a tiny response. An ideal first egress path to make fail-closed.
- **Transcripts are not viable** and pursuing them would mean attempting to defeat a restriction, which is explicitly out of scope.

---

## ⏸️ Implementation deliberately not started

Step 1A was specified as the pre-implementation gate, and it is complete. The connector itself is **not** built, and I want to be direct about why rather than deliver a partial one.

MOGO-015's connector is a **security-sensitive network egress path**. Done properly it needs: a connector authorization model that fails closed; scheme/host allow-listing; redirect destination re-validation; timeout, size and content-type limits; SSRF prevention so an operator-supplied URL cannot become a generic fetch primitive; retry classification separating transient from permanent; seven distinct failure proofs; a live two-run acquisition; and full regression.

That is comparable in size to MOGO-014, which took the larger part of this session. **Beginning it now and running out part-way would leave a half-built outbound network path in the repository — the single worst outcome for a change of this kind.** A connector that is 80% fail-closed is not 80% safe.

The correct next action is to implement it in a fresh session with full budget, starting from this verified decision.

---

## What is ready for implementation

| Piece | Status |
|---|---|
| Source identity | ✅ verified in-repo and corroborated by the provider |
| Endpoint | ✅ verified returning real data |
| Ingestion pipeline | ✅ proven in MOGO-014 — reuse, do not rebuild |
| Result store, policy gate, `authorizations.py`, retry/lease/dead-letter, audit | ✅ all exist and are tested |
| Connector authorization gate | ⏸️ `first_connector_authorization` **UNMET and enforced** — the correct starting point |
| Outbound safety boundary | ⏸️ to build |
| `research.acquire.approved-source-metadata.v1` | ⏸️ to build |

**The A-5 result-store gates are already satisfied**, so unlike MOGO-014 the effectful-capability gate is no longer in the way. The remaining gate is precisely the connector one — which *should* stand, and which MOGO-015 must satisfy deliberately rather than bypass.

---

## Integrity at Step 1A close

Read-only throughout. Two outbound GETs to a public metadata API; no repository code changed.

| Check | Result |
|---|---|
| Platform suite | 0 failures *(verified at MOGO-014 closeout; untouched since)* |
| Canonical gate | 1,113 passed · 0 failed *(same)* |
| Protected ALEX drift | **0** |
| Campaign C1 | **33/33 · 0 mismatched** |
| Legacy corpus | **220 re-derived · 0 mismatched** |
| Forward campaign | ALEX **ON**, cutoff unchanged, $10,000.00, ledger accumulating, no reload |

---

## Next recommendation

Implement `research.acquire.approved-source-metadata.v1` in a fresh session, in this order:

1. **Connector authorization record + gate** — satisfy `first_connector_authorization` deliberately; prove an unauthorized host fails closed **before** any socket is opened.
2. **Outbound boundary** — scheme/host allow-list, redirect re-validation, timeout, size cap, content-type check, no `file://`, no arbitrary destination.
3. **The capability** — one endpoint, one channel, raw bytes preserved and hashed before interpretation.
4. **Adapter into `research.ingest.local-artifact.v1`** — smallest possible; do not create a second ingestion path.
5. **Seven failure proofs**, then the two-run live proof, then regression.
6. **Scheduling only afterwards**, and only if the existing architecture supports it trivially.

---

*Step 1A complete. No code changed. The forward campaign was not touched.*

---
---

# STEP 2 — CONNECTOR AUTHORIZATION GATE

**Status: ✅ COMPLETE.** The fail-closed boundary exists and is proven. **No network capability was built; no acquisition was performed.**

## Architecture

One new module, `platform/src/mogo_platform/runtime/connector_authorization.py`, plus one new suite. **No parallel security architecture** — it sits alongside the existing `authorizations.py` / `policy.py` gates and is called before them in the future acquisition path.

## The anti-SSRF property — the whole design

**A caller does not supply a URL. A caller supplies a SOURCE IDENTITY, and the gate DERIVES the destination** from an approved-destination registry. There is no argument a caller can pass that becomes a fetch target.

If a caller also names a URL — as the Step 3 capability will, so provenance records what was actually requested — it must be **byte-identical** to the derived one. An approved `sourceId` carrying a different URL is refused as `requested_url_does_not_match_approved_destination`.

This is why the registry maps **source → destination** rather than listing allowed hosts. A host allow-list still permits any path on that host; deriving the entire URL leaves nothing to choose.

## Exact boundary

| Bound | Value |
|---|---|
| Connector | `CONN|research|approved-source-metadata` v1.0.0 |
| Approved source | **exactly one** — `SRC|youtube-channel|UCgPeeHdxYRal0HTNeAkjqLg` (fxalexg, `channel_verified`) |
| Scheme | `https` only — plain `http` is in the **forbidden** list |
| Host | `www.youtube.com`, from the registry, never from the request |
| Operation | `metadata` only — **not** transcript, artifact or discover |
| Resource id | exactly 11 chars from a pinned unreserved alphabet |
| Redirects | **not authorized**; `evaluate_redirect()` denies unconditionally |
| Limits carried on the permit | 65,536 bytes max, `application/json` expected |
| Forbidden destinations | `file/ftp/gopher/data/blob/ws/wss/http` schemes; `localhost`, `127.`, `0.0.0.0`, `::1`, `169.254.`, `10.`, `192.168.`, `172.16–31.` |

Every rung of `evaluate()` exits with a denial; a permit is reached only by passing all of them, and an unanticipated shape lands on `unanticipated_request_shape`.

## Fail-closed proof — 22 tests, all passing

Approved source permitted · unauthorized source/host rejected · missing source rejected · forbidden schemes and private/loopback destinations pinned · missing **and** malformed authorization identity distinguished and rejected · wrong operation rejected · **five hostile URL substitutions rejected** including `file:///etc/passwd` and `169.254.169.254` · **ten crafted resource identifiers rejected** including `../../etc/passwd` and `x&url=https://evil.example` · redirects refused and re-validated.

**Rejection before network effect, proven two ways:**

1. **Statically** — an AST scan asserts the gate module imports no `socket`, `ssl`, `http`, `urllib`, `requests`, `httpx`, `asyncio`, `aiohttp` or `subprocess`. There is no transport in it to invoke.
2. **Dynamically** — a transport spy that **raises if called** is placed behind the gate in the Step 3 call order. Ten denied requests are evaluated; the spy records **zero** calls. A companion test proves a permitted request *does* reach the spy, so the gate is not merely always-denying.

## Boundary tests narrowed deliberately — and one real bug of mine

Three platform boundary tests flagged the new module. **One was my defect:** I used `setattr()` in a loop, which the runtime rightly forbids — a field set by name from data is a field no reader can find by searching. Replaced with explicit assignment.

The other two are inherent to an allow-list and were narrowed using **the principle the tests already state themselves**: *"boundaries.py is exempt: it must NAME what it forbids."* The connector allow-list is exempt because it must name what it **authorizes** — an allow-list that cannot name its host authorizes nothing. Both exemptions are paired with the stricter new suite that pins https-only, forbids every loopback/private destination, and proves no transport exists.

## Integrity — verified after implementation

| Check | Result |
|---|---|
| Platform suite | **0 failures** (79 tests incl. 22 new) |
| Canonical gate | **1,113 passed · 0 failed** |
| Protected ALEX drift | **0** |
| Campaign C1 | **33/33 · 0 mismatched** |
| Legacy corpus | **220 re-derived · 0 mismatched** |
| Forward campaign | ALEX **ON**, cutoff `2026-08-11T02:43:57.894Z`, $10,000.00, **1,377 observations**, page continuous, no reload |

## Limitations

The gate authorizes; it does not fetch — **no network code exists yet**. `first_connector_authorization` remains **UNMET** in `CONNECTOR_GATES` and should stay so until Step 3 registers a real connector. No governance authorization record has been created for the connector itself. Redirects are refused outright rather than validated to a permitted set.

## Step 3 recommendation

Build `research.acquire.approved-source-metadata.v1`:

1. **Transport** honouring the permit's limits — timeout, 65 KB cap, content-type check, no redirects; call `evaluate()` **first** and fetch only on a permit.
2. **Connector authorization record** via existing `authorizations.py`; flip `first_connector_authorization` only when it genuinely exists.
3. **Preserve raw bytes**, hash them before interpretation, record source URL, final URL, status, content type, byte length, connector + capability identity.
4. **Adapter into `research.ingest.local-artifact.v1`** — smallest possible; no second ingestion path.
5. **Distinguish request identity from content identity**: same URL returning changed metadata is **new content**, not a duplicate.
6. Prove: approved succeeds · unauthorized fails closed · redirect fails closed · transient retries · permanent does not · oversized rejected · duplicate content handled. Then the two-run live proof.

---
---

# STEP 3 — BOUNDED EXTERNAL NETWORK TRANSPORT

**Status: ✅ COMPLETE.** MOGO contacted an approved external source itself and retrieved genuine research data through the governed gate.

## Architecture — subordinate, not adjacent

`platform/src/mogo_platform/runtime/connector_transport.py` is **the only module in MOGO that opens an outbound socket**, and it cannot be asked to fetch anything. `acquire(request)` takes a *source identity and resource id*, calls the Step 2 gate, and connects only on a permit — fetching **the URL the permit carries**.

**There is deliberately no function that accepts a URL.** Adding one would create the generic fetch primitive the design exists to prevent, so the absence is the safety property and a test asserts it. An AST test additionally pins that the **first executable statement of `acquire()` is the gate call**.

## Boundaries enforced, all from the permit

https only · destination derived from the permit · **redirects refused by a handler that raises** rather than follows · final-URL re-checked after the fact · 10 s timeout (30 s hard max, validated) · read **stops at** 65,536 bytes rather than reading then measuring · `application/json` required · status allow-list `(200)` · bounded honest User-Agent · JSON parsed to reject malformed bodies.

**TLS verification is explicit and never disabled.** This Python build ships no CA bundle, so the transport points at the system store (`/etc/ssl/cert.pem`); if no trust store exists it **fails** rather than falling back to an unverified connection. `ssl._create_unverified_context` appears nowhere.

## Retry classification

**Transient** (retryable): connection failure, timeout, 429, 5xx.
**Permanent** (never retried): authorization denial, 4xx other than 429, oversized, wrong content type, malformed body, redirect attempt.

## Focused tests — 20, all passing, all with doubles

No permit → **zero transport calls** across eight denied shapes · valid permit reaches transport · no public function accepts a URL · fetched URL equals the derived one · moved final URL rejected · redirect raises · timeout bounded and validated · oversized rejected · four wrong content types rejected · four malformed bodies rejected · six 4xx permanent · five 5xx/429 transient · connection/timeout transient · transient-then-success in exactly two attempts · raw bytes and SHA-256 preserved · **identical bytes hash identically regardless of time; changed content is new content**.

## Controlled live acquisition — one request

| | |
|---|---|
| Source | `SRC|youtube-channel|UCgPeeHdxYRal0HTNeAkjqLg` (fxalexg) |
| Authorization | `9e24aa04-c7b5-4438-acaf-c709cd8796b5` |
| Connector | `CONN|research|approved-source-metadata` |
| Gate decision | **permit** · `connector_destination_permitted` |
| URL | `https://www.youtube.com/oembed?url=…%3Fv%3Dhb7ot1_szWI&format=json` |
| HTTP status | **200** · `application/json` · **794 bytes** |
| **Content hash** | **`b668d4209abbf2b8718cea2fa84eacd3985cbb4d1fc352dd1720f64bebb92a00`** |
| Acquired at | 2026-08-11T18:12Z |

**Genuine data returned:** `title: "How to Start Trading with Just $50"` · `author_name: "fxalexg "` · `author_url: "https://www.youtube.com/@fxalexg__"` · `provider_name: "YouTube"`.

The `author_url` matches the repository's recorded channel URL — the provider independently corroborates the source identity, again.

**One honest note:** the first live attempt **failed** with `CERTIFICATE_VERIFY_FAILED`, correctly classified `transient/connection_failed`. That was a real environment gap (no CA bundle in this Python build), fixed by wiring verification explicitly rather than by disabling it.

## Boundary tests narrowed — the most deliberate exemption in the project

`connector_transport.py` is now the **single** entry in `NETWORK_AUTHORIZED_MODULES`. It is permitted to import a network client **only because** it is subordinate to the gate — proven by the AST gate-first test, the no-URL-parameter test, and the zero-transport-calls-on-denial test. Adding a second entry would mean a second module can open a socket, and that must be a visible, argued edit.

The policy-gate bypass test was **narrowed to the policy gate specifically**. It previously matched any `.evaluate(` call and so flagged the unrelated *connector* gate that the transport is **required** to call — calling it is the safety property, not a bypass. Matching the receiver keeps the real rule ("only the orchestrator may consult policy") exact.

## Connector registration — deliberately NOT flipped

**`first_connector_authorization` remains UNMET.** The transport exists and works, but the gate should flip only when a real connector is registered as a governed capability with its own authorization record — not merely because code exists. That is Step 4's job.

## Integrity

Platform suite **0 failures** · canonical gate **1,113 passed / 0 failed** · drift **0** · C1 **33/33 · 0 mismatched** · corpus **220 · 0 mismatched** · forward campaign ALEX **ON**, cutoff `2026-08-11T02:43:57.894Z`, $10,000.00, **1,695 observations**, page continuous, **0 forward evidence packages** — no research data in the trading lane.

## Limitations

No governed capability wraps the transport yet — the live proof called `acquire()` directly from a script, so the **runtime did not dispatch it**. Nothing is ingested. One source, one endpoint, one resource id per call. No scheduling.

## Step 4 recommendation

`research.acquire.approved-source-metadata.v1` as a **registered capability**: manifest declaring the connector, dispatch through the orchestrator (policy → authorize → claim → execute → transport), a connector authorization record, then flip `first_connector_authorization`. Write the raw bytes to the governed intake area and hand off to **`research.ingest.local-artifact.v1`** — no second ingestion path. Distinguish *same request* from *same content*: a URL returning changed metadata is **new content**, not a duplicate.

---
---

# STEP 4 — GOVERNED RUNTIME ACQUISITION + EXISTING INGESTION

**Status: ✅ COMPLETE.** The governed automation runtime dispatched a real external acquisition end to end and fed it through the MOGO-014 ingestion pipeline.

## Lifecycle actually observed

```
TaskPolicyCheckRequested → PolicyEvaluated → queued → AcquisitionAuthorized
→ TaskClaimed → TaskStarted → [connector gate → permit → transport → raw bytes
→ intake/acquired/ → research.ingest.local-artifact.v1] → TaskSucceeded
→ WorkflowCompleted
```

`advanced=3 succeeded=1`. **The operator did not call `acquire()`** — the runtime dispatched it.

## What was built

`capabilities/acquire_approved_source_metadata.py` — `effectClass: effectful`, `operationClass: acquisition`, `acquisitionOperations: ["metadata"]`, **`requiredConnectors: [CONN|research|approved-source-metadata]`**. Naming the connector is the point: it makes `uses_connector()` true so the connector-scoped gate applies. Registered in `BUILTIN_CAPABILITIES` and `CAPABILITY_CALLABLES`; `AcquireSourceMetadata` already existed in the vocabulary, so no vocabulary change was needed.

It accepts **no URL** — a source identity and a resource id only — and imports **no network client**, reaching the network solely through `connector_transport`. A new boundary test asserts exactly that.

## Authorization

`docs/trader-intelligence/authorizations/AUTH-fxalexg-metadata.json` — `96fc2793-b13b-467a-89a8-f31a76ec6d4c`, `operator:joemogollon`, `PERMITTED_PUBLIC_METADATA`, operations `["metadata"]`, bound in its audit history to the connector and to the repository-verified channel record. **Transcript and artifact operations are explicitly not authorized.**

The source id was corrected to repository-native composite form — `SRC|youtube|c785970cc458` (12-char hash of the channel URL) — because `ids.require_composite_id` rightly rejected the channelId form.

## Live proof — two governed runs

| | |
|---|---|
| Run 1 | **succeeded** · HTTP 200 · `application/json` · **794 bytes** |
| Raw content hash | `b668d4209abbf2b8718cea2fa84eacd3985cbb4d1fc352dd1720f64bebb92a00` |
| Raw artifact | `intake/acquired/b668d420….json` (content-addressed, raw bytes verbatim) |
| Research artifact | **`RART|d4e4ec829fe80b576a1304f46405f76a`** |
| Data | *"How to Start Trading with Just $50"* — author `fxalexg`, `author_url` matching the recorded channel |
| Run 2 (same command) | **DUPLICATE SUPPRESSED** — no second acquisition |
| Run 2b (new request identity, same content) | acquisition **ran**, artifact **not duplicated** |

**Artifacts on disk: 2 research artifacts (one from MOGO-014, one from this), 1 raw acquisition.**

## Same request ≠ same content — proven in both directions

Two identity layers, deliberately distinct. **Request identity** = the command's idempotency key: re-submitting the same command is suppressed by the runtime. **Content identity** = SHA-256 of the returned bytes: this decides whether a research artifact is new.

Run 2 proved the first (suppressed at the command layer). Run 2b proved the second — a *new* request identity carrying *identical* content executed the acquisition and recorded it, while creating **no** second artifact. Changed bytes from the same source would produce a new content hash and therefore a new artifact.

## Provenance chain — unbroken

```
research artifact RART|d4e4ec82…
  → intakeRef acquired/b668d420….json
    → acquisition record (status, content type, bytes, connector decision)
      → connector permit (permit / connector_destination_permitted)
        → sourceId SRC|youtube|c785970cc458
          → authorization 96fc2793-…
```

`lane: RESEARCH` · `promotionStatus: NOT_A_TRADING_RULE`. The source never becomes anonymous.

## `first_connector_authorization` — now SATISFIED

Flipped only after **all** of: the gate exists and is fail-closed (22 tests); the transport is subordinate to it (20 tests); the capability is registered and dispatchable; an authorization record exists; and two governed live acquisitions completed. **Code existing was never treated as sufficient.** One connector gate remains unmet: `acquisition_authorization_record`.

## Integrity

Platform **0 failures** · canonical gate **1,113 passed / 0 failed** · drift **0** · C1 **33/33 · 0 mismatched** · corpus **220 · 0 mismatched** · forward lane **0 evidence packages** — no research data in the trading lane.

## ⚠️ Unexpected condition — the forward page reloaded, not by this work

`performance.timeOrigin` moved from `14:57:16.607Z` to **`21:02:21.298Z`**. Nothing in Step 4 touches the browser. `pmset` shows `Maintenance Sleep` at 16:10:55 ET and `Wake … EC.LidOpen/UserActivity` at 17:01:43 ET, so a host sleep/wake is the likely context.

**The campaign survived intact:** ALEX **ON**, polling active, cutoff **`2026-08-11T02:43:57.894Z` unchanged**, $10,000.00, 0/0, credentials present, **2,350 durable observations** (up from 1,695), 250 polls, last poll `21:17:11Z`.

**MOGO-013 did exactly what it was built for** — observations survived a reload that the pre-013 architecture would have erased silently. The recorded **max polling gap is 127 minutes**, consistent with the sleep window, and it is now *measured* rather than inferred. This is MOGO-012-INC-001's decision rule producing evidence.

## Scheduling readiness

Unchanged and confirmed: **there is no scheduler.** The smallest next change is a `launchd` agent invoking `mogo_runtime submit --command-file <fixed> && mogo_runtime run` on an interval — no new architecture, since idempotency, lease and retry already make repeated invocation safe. **Not built.**

## MOGO-015 stop condition

> *"STOP after ONE external connector has successfully acquired genuine external research data and passed it through the governed research pipeline."*

**Satisfied.**

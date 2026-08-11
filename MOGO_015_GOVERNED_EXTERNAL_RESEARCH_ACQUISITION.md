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

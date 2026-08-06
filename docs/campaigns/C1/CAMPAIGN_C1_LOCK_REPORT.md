# CAMPAIGN_C1_LOCK_REPORT.md

**Campaign C1 is frozen.** Collection is complete, the evidence set is verified and backed up, and
its identity is recorded permanently. Adjudication has **not** begun.

**Locked:** 2026-08-06 · **Milestone:** MOGO-006 (administrative and forensic only)

---

## 1. Campaign identity

| | |
|---|---|
| Campaign ID | `CAMP\|ALEX\|C1\|2026-08-05` |
| Pre-registration | PREREG-002 (`42d543c4dd7d…5b6981b1`), successor to PREREG-001 |
| Strategy | `alex_g_sr_v1`, unmodified |
| Engine | `APP_VERSION` **12.19.0** on all 221 packages |
| Runs commit | `f7f0c40` |
| Administrative commits | `b71e222` (§8.7 record) · this lock commit |
| Collection / completion | 2026-08-06 / 2026-08-06 |
| Declared → executed | 11 → **11**, order preserved, no substitutions |
| `configHash` | `dbbb29b690f6692ae4d44a6833876193435ad66cc13c6e7226031e5f462c5adb` (one value) |
| `paramsHash` | `8fe841e602be86cd335c9aa6804a8f30c76c57cac229a50b349194d821c6cae5` (one value) |

Full identity, including all eleven `runId`/`datasetHash` pairs, the replay configuration and the
suppression methodology: **`CAMPAIGN_C1_IDENTITY.md`**.

## 2. Evidence inventory

| | |
|---|---|
| Primary location | `<repo>/evidence/` — git-ignored; evidence is never committed |
| Artifacts | **33** (11 runs × `PACKAGES` / `REJECTED` / `HARVEST`) |
| Total bytes | 13,575,486 |
| Campaign packages | **221** (`mode == REPLAY`) |
| Trades created / decided | 226 / 221 (5 still-open produced no package, by design) |
| Suppression records | 128, every one with a reason |
| Non-campaign packages | 1, disclosed — see limitation B6 |
| Backup | `~/Desktop/MOGO-Evidence-C1/` + `MANIFEST.txt` + receiver transcript |

Per-file manifest with SHA-256, size, timestamp, `runId`, instrument and type:
**`CAMPAIGN_C1_EVIDENCE_MANIFEST.md`**.

## 3. Verification status

| Check | Result |
|---|---|
| Package hash verification | **221 / 221 PASS**, 0 FAIL |
| Distinct `runId`s | 11 — one per run, no duplicates |
| Distinct `configHash` / `paramsHash` | **1 / 1** — both match PREREG-002 §2 |
| Engine constant | 12.19.0 across all 221 |
| ADR-011 completeness | `COMPLETE` on W/D/H4/H1, all runs |
| Gate fields | 216 / 221 populated; 5 explained nulls (B1) |
| Rejection inventory | 11 / 11 runs complete |
| Backup | 33 / 33 byte-identical |
| Repository | clean, 0 tracked modifications |
| Regression | **947 / 947**, 0 failures, zero drift |

### Archive verification chain

```
repository evidence  ──►  backup evidence      identical (33/33 SHA-256)
repository evidence  ──►  manifest document    identical (0 mismatches)
manifest             ──►  committed record     consistent (11/11 runIds, both hashes, counts)
committed record     ──►  git                  clean at b71e222
```

Every link measured, not assumed. Full certification: **`CAMPAIGN_C1_INTEGRITY_CERTIFICATE.md`**
Part A.

## 4. Known limitations

Recorded in full, and deliberately kept separate from the certified claims, in
**`CAMPAIGN_C1_INTEGRITY_CERTIFICATE.md`** Part B.

| ID | Limitation |
|---|---|
| **B1** | 5 of 221 packages carry a null excursion-timing field — the excursion was zero; not capture failures |
| **B2** | Window is discovered from run time, not chosen — no result may be called out-of-sample |
| **B3** | Informative censoring at 36.2% campaign-wide (24.2%–58.6% per run) |
| **B4** | `commitHash` null in packages (L5); satisfied externally as `f7f0c40` |
| **B5** | **Export-verification by re-import not performed (L6)** — the one unmet §8 requirement |
| **B6** | `C1-01-GBP_USD-PACKAGES.json` holds one non-campaign `LIVE_CLOSE` package — filter `mode == "REPLAY"` |
| **B7** | Immutability is **detective, not preventive** — tamper-evident, not tamper-proof |
| **B8** | Browser capture is not independently reproducible |
| **B9** | PREREG-001 gate items R4, R8, B2 and §3.4 remain open |

## 5. Outstanding PRE-REG items

| Item | Status |
|---|---|
| §8.1 `runId`, `datasetHash`, `configHash`, `paramsHash` | ✅ all four, all runs |
| §8.2 observed window + candle counts | ✅ |
| §8.3 ADR-011 completeness | ✅ |
| §8.4 engine version | ✅ 12.19.0 |
| §8.4 repository commit | ⚠️ external only (B4) |
| §8.5 hash-verified packages | ✅ 221/221 |
| §8.5 export-verified by re-import | ❌ **not performed (B5)** |
| §8.6 `alexGReplayRejected` in full | ✅ 11/11 |
| §8.7 entry in verified replay record | ✅ committed `b71e222` |
| §7 adjudication | **not begun** — permitted once, after the declared runs |

Two things need settling **before** adjudication computes anything, per `RESEARCH_READINESS.md` Q5:
how arms are formed given that `datasetHash` differs per instrument, and consequently whether the
30-resolved-per-arm floor is met.

## 6. Repository status

```
branch                  main
lock commit             (this commit)
parent                  b71e222
runs executed at        f7f0c40
tracked modifications   0
index.html              byte-identical to f7f0c40
```

Repository changes in this milestone are **documentation only**. No strategy, engine, replay logic,
protected function, protected constant, or evidence file was modified.

## 7. Regression status

```
Suites run:       17
Execution errors: 0
Fixtures run:     947
Passed:           947
Failed:           0

No drift: all 63 protected functions and 4 protected constants byte-identical.
```

## 8. Readiness for adjudication

**Ready, on authorization.**

The evidence set is complete, verified, backed up, and permanently identified. Every future
statistical conclusion drawn from Campaign C1 can be traced to the identifiers in
`CAMPAIGN_C1_IDENTITY.md` and checked against the hashes in `CAMPAIGN_C1_EVIDENCE_MANIFEST.md`.

Adjudication under PREREG-001 §7 happens **once**, and requires forming the declared arms, applying
Holm–Bonferroni across the family of 12, checking the 30-resolved-per-arm floor, and reporting the
suppression rate on every figure.

**No adjudication has begun. No statistic has been computed. No arm has been formed. No strategy
comparison has been made. No conclusion about strategy performance appears in any document produced
by this milestone.** The promotion ceiling remains `REPLAY_EVIDENCE_ONLY` and RZR remains suspended.

---

## Documents in this lock

| Document | Purpose |
|---|---|
| `CAMPAIGN_C1_IDENTITY.md` | Canonical frozen identity — the traceability anchor |
| `CAMPAIGN_C1_EVIDENCE_MANIFEST.md` | Per-artifact SHA-256, size, timestamp, runId, instrument, type |
| `CAMPAIGN_C1_INTEGRITY_CERTIFICATE.md` | Part A certified claims · Part B limitations, kept separate |
| `RESEARCH_READINESS.md` | What this evidence can and cannot support |
| `CAMPAIGN_C1_LOCK_REPORT.md` | This summary |

**Campaign C1 is frozen.**

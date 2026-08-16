# MOGO-019 — ALEX-IG-2026-CASE-002 RESEARCH INGESTION REPORT

**Status: 🛑 BLOCKED BEFORE EVIDENCE CREATION — the six screenshots are not present.**
**All work not depending on the images is complete. No evidence record was fabricated.**

**PAPER TRADING UNCHANGED · FROZEN ALEX STRATEGY UNCHANGED · LIVE-MONEY TRADING UNAUTHORIZED**

---

## 0. The blocker, stated first

The instruction was explicit on two points:

> *"Preserve the original screenshots as source evidence with provenance."*
> *"Do not rely only on manually transcribed values."*

**I cannot do either. The screenshots do not exist anywhere I can reach:**

| Searched | Result |
|---|---|
| Attached to this conversation | **none** — no images were provided |
| Repository (any `.png/.jpg/.jpeg/.heic/.webp` since 2026-08-01) | **none** |
| `~/Desktop`, `~/Downloads`, `~/Documents` (depth 3, since 2026-08-09) | **none** |
| Any `screenshot` / `inbox` / `incoming` / `instagram` directory | **none exist** |

Everything I have is the **transcription in the prompt**. Creating
`ALEX-IG-2026-CASE-002` from that alone would mint a governed evidence record whose
`sourceType` claims Instagram screenshots, carrying a `contentHash` over text I typed rather than
over source bytes I preserved. That is fabricated provenance, and it is precisely what this
codebase's own discipline forbids — MOGO-018 Step 3C refused to invent a single channel identifier on
exactly this reasoning.

**So I stopped before creating the case, and completed everything else.**

### What unblocks this

Put the six image files anywhere readable and tell me the path. Then I will hash them, preserve them
as source evidence, and reconcile the transcription in §5 against what the images actually show.

---

## 1. Files inspected

| Path | Why |
|---|---|
| `docs/trader-intelligence/evidence/schema/evidence-source.schema.json` | source-type enum, required fields |
| `docs/trader-intelligence/intake/manifests/*.ingest.json` | existing intake manifest precedent |
| `docs/trader-intelligence/{evidence,imports,intake,traders,library}/` | Lane A layout |
| `platform/src/mogo_platform/runtime/capabilities/ingest_local_artifact.py` | operator-supplied ingestion contract |
| `platform/src/mogo_platform/runtime/research_corpus.py`, `research_library.py` | Lane B corpus + derived views |
| `platform/runtime/logs/scheduled-collection.out.log`, runtime SQLite | GATE-3E verification |

## 2. Existing ingestion architecture discovered

MOGO has **two** research lanes, and this case belongs to **Lane A**:

- **Lane A — operator-supplied intake.** `imports/<trader>/raw/` (immutable original + `.sha256`) →
  `intake/manifests/*.ingest.json` → `evidence/sources/EVSRC_*.json` → claims / annotations /
  segments. This is the lane for material an operator hands to MOGO.
- **Lane B — governed autonomous acquisition (MOGO-014…018).** Registry-derived URLs, scheduled
  collection, change detection. **Not applicable**: Instagram is not an approved source, and
  authorizing it would be an authorization expansion requiring operator review.

**Lane A can already preserve a screenshot today.** `EvidenceSource` requires
`repositoryPath` + `contentHash` + `provenanceStatus`; nothing requires the bytes to be text. The
existing `.raw` + `.raw.sha256` convention works unchanged for a PNG.

**Two genuine gaps** (identified, deliberately not built — see §14):

1. **`sourceType` has no image/screenshot value.** The enum is
   `transcript · video · audio · article · book · note · strategy_document · paper_trade ·
   replay_observation · live_trade_review · journal_entry · market_observation · owner_observation ·
   generated_analysis · other`. Closest honest fit today is `live_trade_review` or `other`.
2. **No structured trade-observation record type exists.** Lane A's claim/annotation/segment shapes
   are transcript-oriented (character offsets into text). There is nowhere to put
   *instrument / direction / size / entry / observed price / P/L / account state / sequence
   membership*. **This is the real missing piece for repeated screenshot ingestion.**

## 3. Evidence imported

**NONE.** No file was written to `imports/`, `intake/`, `evidence/` or `research-artifacts/`.
See §0.

## 4. Structured observations created

**NONE persisted.** The reconstruction below is *analysis of the operator's transcription*, held in
this report only, pending the source images.

## 5. Derived calculations — independent validation of the transcription

Method: 1 displayed size unit = 1 standard lot = 100,000 base units (**hypothesis under test, and it
held in every case**). Pip = 0.0001 for all four pairs. USD-quoted pairs need no conversion;
AUDCHF settles in CHF and NZDCAD in CAD, so the implied cross rate is **solved from the displayed
P/L** rather than assumed. Tolerance: exact to the cent for USD-quoted; ±0.001 on implied FX rates.

### 5.1 FOMC sequence — EURUSD + NZDUSD (2026-06-17)

| Obs | EURUSD pips | calc P/L | shown | NZDUSD pips | calc P/L | shown | total calc | shown |
|---|---|---|---|---|---|---|---|---|
| 1 | 27.5 | 94,600.00 | 94,600.00 ✅ | 17.6 | 97,328.00 | 97,328.00 ✅ | 191,928.00 | 191,928.00 ✅ |
| 2 | 40.1 | 137,944.00 | 137,944.00 ✅ | 26.8 | 148,204.00 | 148,204.00 ✅ | 286,148.00 | 286,148.00 ✅ |
| 3 | 45.3 | 155,832.00 | 155,832.00 ✅ | 30.0 | 165,900.00 | 165,900.00 ✅ | 321,732.00 | 321,732.00 ✅ |

**Every figure matches to the cent.** Obs 1 also reconciles completely:
equity − balance = 3,355,734.74 − 3,163,806.74 = **191,928.00 = floating P/L exactly**;
free margin 3,211,623.05 ✅; margin level 2,328.57% ✅.

### 5.2 AUDCHF

Movement 0.57443 − 0.56767 = 0.00676 = **+67.6 pips** ✅ (matches the stated figure).
615 lots × 0.00676 = **415,740 CHF**; shown 511,157.83 USD ⇒ implied **CHFUSD 1.22951**
(USDCHF 0.81333) — plausible for the period. Free margin ✅, margin level 4,918.67% ✅.

### 5.3 NZDCAD (2025-12-17)

| Obs | pos1 pips | pos2 pips | implied USDCAD (pos1 / pos2) | combined shown |
|---|---|---|---|---|
| earlier | −7.8 | −8.9 | 1.37777 / 1.37777 **agree** | −47,685.75 ✅ |
| later | +18.2 | +17.1 | 1.37833 / 1.37833 **agree** | +103,240.88 ✅ |

Two independent positions solving to the **same implied rate to 5 decimals** is strong evidence the
transcription is accurate. Entry spacing 0.79623 − 0.79612 = **1.1 pips** ✅. Free margin and margin
level reconcile exactly in both observations.

### 5.4 Normalized, account-size-independent fields

| Case | floating % of balance | notional USD | exposure / equity | implied margin | implied leverage |
|---|---|---|---|---|---|
| FOMC obs1 | +6.07% | ~72.06 M | 21.5× | **0.2000%** | **~1:500** |
| AUDCHF | +14.46% | ~42.92 M | 10.1× | **0.2005%** | **~1:499** |
| NZDCAD | −1.57% | ~46.23 M | 14.3× | **0.2004%** | **~1:499** |

**All three imply 0.200% margin — 1:500 — across three instruments and two dates six months apart.**
Independent corroboration that the size unit is standard lots and that this is one consistent account.

### 5.5 Observed excursions (pips)

| Instrument | Adverse | Favorable |
|---|---|---|
| AUDCHF | **UNKNOWN** (no earlier observation) | +67.6 |
| EURUSD | **UNKNOWN** | 27.5 → 40.1 → 45.3 |
| NZDUSD | **UNKNOWN** | 17.6 → 26.8 → 30.0 |
| NZDCAD pos1 | −7.8 | +18.2 (swing 26.0) |
| NZDCAD pos2 | −8.9 | +17.1 (swing 26.0) |

## 6. Evidence anomalies — **three, not one**

Every anomaly is preserved. **No explanation is manufactured.**

| # | Case | equity − balance | visible position P/L | Unexplained |
|---|---|---|---|---|
| A1 | AUDCHF | +534,689.33 | +511,157.83 | **+23,531.50** |
| A2 | NZDCAD earlier | −51,340.62 | −47,685.75 | **−3,654.87** |
| A3 | NZDCAD later | +88,648.20 | +103,240.88 | **−14,592.68** ← the one flagged in the brief |

**A1 and A2 were not flagged in the brief and are newly surfaced here.**

**A key DERIVED constraint:** between the two NZDCAD observations the unexplained component moved
from −3,654.87 to −14,592.68 — a change of **−10,937.81** while the visible NZDCAD P/L *improved* by
~150,927. **The residual is therefore not constant**, which is inconsistent with a fixed swap or
commission alone. It is consistent with one or more *additional positions whose P/L moved* — but that
is a HYPOTHESIS requiring the images (or uncropped screenshots) to test, not a conclusion.

Balance was identical (3,273,769.20) across both NZDCAD observations ✅ — consistent with nothing
having been realised, i.e. positions still open.

## 7. Trade sequences reconstructed (analysis only — nothing persisted)

- **SEQ-A · AUDCHF** — 1 observation, single BUY, open at capture. Caption *"Can't forget the main
  trade / Yes I'm still holding."* Entry date and original stop **UNKNOWN — not inferred.**
- **SEQ-B · FOMC** — 3 sequential observations (~2:01 → ~2:05 → ~2:12), EURUSD SELL 344 + NZDUSD
  SELL 553, both open throughout, floating +191,928 → +286,148 → +321,732. Story labelled FOMC;
  **causal entry motive NOT claimed.**
- **SEQ-C · NZDCAD** — 2 observations, two simultaneous SELLs (500 @ 0.79623, 300 @ 0.79612, 1.1 pips
  apart), both open throughout, −47,685.75 → +103,240.88.

## 8. Cross-case comparisons

**Not possible. There is no prior case.** No `MOGO-019*` report, no `ALEX-IG` case, and no prior
AUDCHF Instagram evidence exists in the repository — this would be CASE-**001**, not 002. The
"previously preserved Alex/AUDCHF evidence already ingested or pending in MOGO-019" referenced in the
brief **does not exist**; please point me at it if it lives outside this repository.

Lane B holds Alex G *YouTube metadata* only (1 resource, 9 observations) — no trade content, so it
cannot corroborate any hypothesis below.

## 9. Hypotheses registered — **NOT accepted as rules**

Registered as research hypotheses only. **None is a trading rule. None may alter ALEX.**

| ID | Hypothesis | Supporting | Contradicting | Assessment |
|---|---|---|---|---|
| H1 | Large nominal exposure for modest pip moves | 3/3 cases (10–21× equity; 17.6–67.6 pips) | 0 | consistent, but **n=3 from one account** |
| H2 | Holds winners through expansion vs. fixed small TP | SEQ-B (held 27.5→45.3 pips), SEQ-A ("still holding") | 0 | **no exit observed in any case** — cannot show what he *does* at the end |
| H3 | One macro thesis via multiple correlated pairs | SEQ-B (EURUSD + NZDUSD short = USD long) | 0 | **1 example only** |
| H4 | Scales via multiple entries on one instrument | SEQ-C (500 + 300, 1.1 pips apart) | 0 | **1 example only** |
| H5 | Tolerates substantial adverse excursion | SEQ-C (−8.9 pips / −$47.7K → +$103.2K) | 0 | **1 example**; max observed adverse is only **8.9 pips** |
| H6 | Distinguishes a "main trade" from secondary trades | SEQ-A caption | 0 | **caption wording only** — 1 instance |
| H7 | Invalidation structural, not floating-$ based | *none* | *none* | **NO EVIDENCE EITHER WAY** — no stop or exit is visible in any screenshot |

**Overfitting warning, stated plainly:** H3, H4, H5 and H6 each rest on a **single** example, and H7
has **zero**. H2 cannot be evaluated at all because **no trade is observed to close**. Everything
here is one account over two dates. These counts are the honest state of the evidence.

## 10. Any code changes

**NONE.** No production code, no schema, no test, no evidence file was created or modified for
MOGO-019. The only repository change in this session was the MOGO-018 GATE-3E closure (§12), which is
independent of this case.

## 11. Tests run and results

No MOGO-019 tests were added — **there is nothing to test until evidence exists.** The eight tests
requested in the brief (provenance retention, sequence reconstruction, OBSERVED/DERIVED/HYPOTHESIS
separation, anomaly preservation, duplicate-ingestion safety) all presuppose an ingested artifact.

Repository gates were nevertheless run to prove this session changed nothing:

| Gate | Result |
|---|---|
| Platform suite | ✅ **25 suites · 1,049 tests · 0 failures · 0 errors** |
| Canonical gate | ✅ **19 suites · 1,160 / 1,160 · 0 failed** |
| Runtime integrity | ✅ `INTEGRITY OK` |

## 12. Confirmation: frozen ALEX strategy unchanged

✅ **Protected ALEX drift = 0** — all **63 protected functions and 4 protected constants** byte-identical
to the committed baseline; known-good hash match `True`. `index.html` untouched.

## 13. Confirmation: paper-trading behaviour unchanged

✅ No paper-trading code, campaign file, or forward evidence was read for mutation or written.
`docs/campaigns`, `docs/evidence` and `index.html` are byte-unchanged. The live forward browser was
**not** reloaded or restarted and **no** paper trade was forced. Campaign C1 remains 33/33.

## 14. Smallest next architectural requirement

Only if repeated screenshot ingestion is wanted — **not built in this step**:

1. **Add one `sourceType` enum value** (e.g. `screenshot`) to `evidence-source.schema.json`. One
   line. Everything else in Lane A (immutable raw + `.sha256` + manifest + `EvidenceSource`) already
   works for binary files.
2. **One new record type for trade observations** — the genuine gap. Fields: instrument, direction,
   size, entry, observed price, displayed P/L, account block, capture time, sequence id + ordinal,
   `positionStillOpen`, and an explicit `classification` of
   `OBSERVED | DERIVED | HYPOTHESIS | UNKNOWN` **per field**.

Everything else the brief's DISCOVER → … → BUILD DATASET vision needs is deferred; nothing beyond
these two is required to ingest this case.

## 15. Recommended next step

1. **Provide the six screenshots** and I will complete the ingestion as specified — that is the only
   real blocker.
2. **Confirm the case identifier.** Evidence says this is CASE-**001**, not 002; if a CASE-001 exists
   elsewhere, point me to it.
3. **Decide on the two schema additions in §14** before ingestion, so the case is stored in its final
   shape rather than migrated later.
4. **Do not act on H1–H7.** No hypothesis is close to acceptance; four rest on one example and one has
   no evidence at all.

**No strategy modification, freeze, backtest or paper activation was performed or is recommended.**

**LIVE-MONEY TRADING REMAINS UNAUTHORIZED.**

# ALEX — Source Coverage Audit

**Milestone:** MOGO-002.8 — ALEX Source Coverage & Strategy Fidelity Audit · **Phase 2**
**Date:** 2026-07-29 · **HEAD:** `a332d04` (all milestone work uncommitted)
**Machine-readable:** [`alex-source-coverage-audit.json`](alex-source-coverage-audit.json)

> Every figure below was recomputed from `docs/trader-intelligence/evidence/` at generation time.
> No count is carried over from a prior package.

---

## 1. Headline

**9 ALEX_G sources are acquired and processed. All 9 are `ACQUIRED_AND_PROCESSED`. None is partial,
missing, duplicate, or attribution-uncertain.**

| | |
|---|---|
| Sources registered | **9** |
| Claims extracted | **226** |
| Evidence items | **280** |
| Transcript segments | **134** |
| Provenance status | **9 / 9 `partially_verified`** — every source carries a content hash, a canonical URL and a byte-preserved raw archive |
| Exact duplicates | **0** |
| Distinct video IDs | **9** |
| Licensing | 9 / 9 `restricted_third_party` (internal research permitted, redistribution prohibited — `DECISION\|MOGO\|20260727\|005`) |

**Provenance re-verification passes: 452 checks, 0 findings** — every raw archive, working copy,
normalization map and excerpt verifies.

## 2. Catalogue coverage — **9 of at least 200 videos (4.5%)**

> **⚠️ SUPERSEDED SECTION — updated 2026-07-29 (later same day).** This section previously stated
> that *"there is no defensible inventory of the `@fxalexg__` channel's full catalogue, so this audit
> states no total and no percentage"*, because the listing page was JS-rendered and returned no
> titles via `WebFetch`. **That limitation has since been resolved** by fetching the channel page
> with a User-Agent and paginating the public innertube `browse` continuation. The original caution
> is retained here as a record of what changed, and the figure below now has a real denominator.
> Full detail: [`ALEX-AUDIT-DELTA-2026-07-29b.md`](ALEX-AUDIT-DELTA-2026-07-29b.md).

| | |
|---|---|
| Channel | `fxalexg` · `@fxalexg__` · channel ID **`UCgPeeHdxYRal0HTNeAkjqLg`** |
| Enumeration method | Channel-page `ytInitialData` + innertube `browse` continuation, **7 pages**, terminated naturally when no further token was returned. **Read-only metadata; no caption access.** |
| **Videos enumerated** | **200** |
| **Registered sources found in the catalogue** | **9 / 9** ✅ |
| **Ingestion coverage** | **9 of 200 — 4.5%** |
| Machine-readable | [`alex-channel-catalogue.json`](alex-channel-catalogue.json) |

**The 9/9 cross-check is what makes the catalogue trustworthy.** Every registered ALEX_G source
appears in it, so the enumeration is authentic and consistent with the repository.

**Completeness caveat, stated rather than glossed:** pagination ended naturally, but the result
**cannot be proven exhaustive** — unlisted, removed, members-only and Shorts entries may be excluded.
**Read the figure as "9 of at least 200."** The denominator is defensible, not certain.

Also unchanged: **4 further targets are identified but not acquired; 7 candidate sources were
examined and rejected.**

## 3. The nine acquired sources

| # | Source ID | Title | Claims | Rule-bearing claim types |
|---|---|---|---|---|
| 1 | `EVSRC\|ALEX_G\|20260727\|001` | Best Top Down Analysis Strategy for 2026 | **35** | entry 7, setup 7, timeframe 2, confirmation 2, invalidation 2 |
| 2 | `EVSRC\|ALEX_G\|20260728\|001` | Simplifying Advanced Market Structure in 20 Minutes | **18** | setup 7, invalidation 2, entry 1 |
| 3 | `EVSRC\|ALEX_G\|20260728\|002` | How to Master Liquidity in Trading (Advanced Guide) | **22** | entry 7, setup 3, invalidation 1 |
| 4 | `EVSRC\|ALEX_G\|20260728\|003` | Learn How THIS Forex AOI SECRET Bought Me A $200,000 Watch | **29** | entry 7, setup 6, confirmation 3, session 1, trade-mgmt 1 |
| 5 | `EVSRC\|ALEX_G\|20260728\|004` | The ONLY confirmation YOU need to make $1000/day | **40** | entry 6, **session 5**, confirmation 3, setup 3, target 1 |
| 6 | `EVSRC\|ALEX_G\|20260728\|005` | Best Risk Management Strategy to Make Millions | **35** | **risk 13**, target 2, session 1, trade-mgmt 1 |
| 7 | `EVSRC\|ALEX_G\|20260728\|006` | Market break down learn and earn | **27** | entry 6, setup 6, trade-mgmt 2, target 1 |
| 8 | `EVSRC\|ALEX_G\|20260728\|007` | The best FOREX MONEY MINDSET psychology video PT 2 | **21** | risk 1, trade-mgmt 2 |
| 9 | `EVSRC\|ALEX_G\|20260729\|001` | **This Trading Strategy Made Me $26,000 in Just 12 Hours** | **31** | **stop 2**, timeframe 4, confirmation 3, entry 2, target 1, trade-mgmt 1 |

**Source #9 is the only source in the corpus containing a `stop_rule` claim.** Sources #1–#8 contain
**zero** between them.

**Source #6 is the entire risk-management backbone** — 13 of the corpus's 14 `risk_rule` claims come
from one 16 KB transcript. That concentration is a fragility worth noting: if that single source were
withdrawn or found unrepresentative, the whole sizing layer would collapse.

## 4. Evidence quality distribution

Across all 280 ALEX_G evidence items:

| Quality | Count | Share |
|---|---|---|
| `high` | **150** | 54% |
| `medium` | **101** | 36% |
| `low` | **29** | 10% |

The `low` band is almost entirely unverifiable monetary and performance claims — $26,000/12h,
$60k/$50k days, the $200,000 watch, student income figures, monthly-return percentages. **None of
them supports a rule.** They are retained rather than discarded because
`STANDARDS-extraction.md` requires marketing content be recorded and classified, not filtered out.

## 5. Sources identified but NOT acquired

| Ref | What | Status | Why it matters |
|---|---|---|---|
| `ACQTARGET\|ALEX_G\|LIVE-SESSION-ORDER-ENTRY` | A live session where an order is actually placed | `SOURCE_IDENTIFIED_NOT_ACQUIRED` | **The single highest-value remaining target.** A stop price must be typed into a ticket — the one context where the missing buffer becomes visible |
| `ACQTARGET\|ALEX_G\|COMPLETE-WALKTHROUGH` | A complete single-trade walkthrough | `SOURCE_IDENTIFIED_NOT_ACQUIRED` | Partially superseded — source #9 delivered three worked trades |
| `ACQTARGET\|ALEX_G\|SET-AND-FORGET-EXPLAINER` | A dedicated "set and forget" episode | `SOURCE_IDENTIFIED_NOT_ACQUIRED` | Source #8 self-identifies as **episode three** of this series, so others demonstrably exist |
| `ACQCAND\|INTERVIEW\|20260729\|001` | *"How This Young Trader Claims He Made $2M…"* (Trading Nut) | **`ATTRIBUTION_UNCERTAIN`** | The educator **speaks** but the **publisher is third-party**. `EvidenceSource` has no field separating publisher from speaker, so ingesting it needs a governance decision first |

**One further target is named inside the corpus itself.** At **5:33** of source #9 the educator points
directly at another video: *"you want to know more about bullish engulfing bearish engulfing and how
you can use that effectively with break and retest just look at this video right here."* That is a
**named, educator-pointed-at source** addressing the single largest implementation divergence this
audit found. It is the highest-certainty acquisition available and is ranked accordingly in the
source plan.

## 6. Rejected sources

**7 candidates, all `REJECTED_SOURCE`, all for lineage rather than quality.** Channel ownership was
verified individually via YouTube oEmbed `author_url`; **none is `@fxalexg__`**:

`iXjrVyTAS6M` (SIR TREVOR TRADES) · `N4ipW0VlGI8` (Nick's Trade) · `R4mNrUy_azU` (Vidollar) ·
`HzVSi9ux1NU` (Revelio Trading) · `AFOp_jsm1Ak` (Chuck Index) · `kBWjkO1GCyk` (Alex Trading Reviews) ·
`rr1IBysoGYY` (MOBILE TRADING ACADEMY — unrelated to this educator entirely)

`iXjrVyTAS6M` — *"Complete Guide Of Set And Forget Strategy by FXALEXG"* — is the most likely of the
seven to actually contain the missing stop buffer, **and it is still unusable.** A third party's
account of Alex's rule cannot establish Alex attribution however accurate it may be (governance rules
7 and 8).

## 7. Duplicate and overlap analysis

**No source is `DUPLICATE_OR_REDUNDANT`.** Method: SHA-256 content hash compared at ingestion for
every source, plus `canonicalReference` (video ID) uniqueness across all 9.

Topic overlap does exist — sources #4 and #7 both narrate chart markup; #1 and #2 both cover market
structure — but each carries distinct claims and distinct timestamps. The ingestion pipeline
additionally deduplicates at claim level via `compute_claim_fingerprint()`, and **the newest source
produced 31 distinct claims with zero merges**, which is itself evidence the material was not
redundant.

## 8. What the source base can and cannot support

**Can support:** the full setup→entry chain (structure, zones, break-and-retest, confirmation),
the complete risk-percentage framework, session and day-of-week gating as *rules*, and — since
source #9 — the stop-placement *relationship*.

**Cannot support:** the stop buffer, session hours, break-even, partials, scaling, trailing stops,
target selection above the 1:2 floor, and any short-side rule. Seven of those nine are **absolute
zeros across all 9 sources**, not thin areas.

---

*Phase 2 complete. No source was modified; the evidence store is read-only to this audit.*

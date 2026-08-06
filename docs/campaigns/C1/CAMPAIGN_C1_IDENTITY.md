# Campaign C1 — Canonical Identity (FROZEN)

**This document is the canonical identity of Campaign C1.** Every statistical conclusion ever drawn
from this campaign must be traceable to the identifiers below. It is frozen: if any part proves
wrong, it stays wrong and a successor corrects it — the same rule PREREG-001 §10 applies to itself.

**Nothing here is adjudicated.** No statistic, no interpretation, no comparison, no conclusion about
strategy performance appears in this document.

---

## Campaign identifier

```
CAMP|ALEX|C1|2026-08-05
```

| Field | Value |
|---|---|
| **Campaign ID** | `CAMP\|ALEX\|C1\|2026-08-05` |
| **Pre-registration** | `PREREG-002-alex-c1-execution-2026-08-05.md` (successor to PREREG-001) |
| **Parent pre-registration** | `PREREG-001-alex-multipair-2026-08-04.md` — unedited, per its §10 |
| **PREREG-002 SHA-256** | `42d543c4dd7d4651694e7842379977f699d69874c3930d08e002f2cf5b6981b1` |
| **Strategy** | `alex_g_sr_v1` |
| **Strategy version** | `alex_g_sr_v1` · release `alex_g_sr_v1_1` · provenance `OBSERVED` |
| **Engine version** | `APP_VERSION` **12.19.0** — constant across all 221 packages |
| **Runs executed at commit** | `f7f0c408d01ffa7c5ec0dc85e41697ea6855bb78` (`f7f0c40`) |
| **Administrative commit** | `b71e222c103a0244ec6e17f5abe20b90c09b7132` (`b71e222`) — §8.7 completion record |
| **Collection date** | 2026-08-06 |
| **Completion date** | 2026-08-06 |
| **Declared runs** | 11 · executed 11 · pre-registered order preserved · no substitutions |

### Preceding commits in the identity chain

| Commit | Role |
|---|---|
| `f83a9b1` | PREREG-001 committed — precedes all observation |
| `b71f016` | v12.19.0 engine + PREREG-002 committed — precedes the first C1 run |
| `f7f0c40` | Evidence egress receiver adopted — the commit all eleven runs record |
| `b71e222` | Campaign completion record (§8.7) — administrative, post-collection |

`v12.19.0` is an annotated tag at `b71f016`, pushed to `origin`, so the ordering between the
pre-registration and the first observation is externally verifiable.

## Replay configuration — constant across all eleven runs

| Parameter | Value | Source |
|---|---|---|
| Lookback control | **90 days** | operator selection, pre-registered |
| Ambiguous candles | **`conservative`** (count as loss) | pre-registered; contributes to `paramsHash` |
| Spread mode | `none` | hardcoded, `index.html:4105` |
| Fixed spread | `0` pips | hardcoded |
| Slippage | `0` pips | hardcoded |
| Start balance | `10,000` | hardcoded |
| Mode | `REPLAY` | — |
| Data source | OANDA **practice** | — |
| Candles observed per run | W 73 · D 150 · H4 600 · H1 2220 | recorded per run |
| ADR-011 completeness | `COMPLETE` on W/D/H4/H1, all runs | recorded per run |

**The "90 days" figure is a control label, not a sample boundary.** `fetchCandlesRange` paginates
backward from run time by candle count (PREREG-001 §6, open gate item **B2**), so each run's absolute
window was discovered after the fact and spans roughly 128 calendar days. No result from this
campaign may be described as out-of-sample.

## Identity hashes

### Campaign constants — declared in advance, one value each

| Hash | Value |
|---|---|
| **`configHash`** | `dbbb29b690f6692ae4d44a6833876193435ad66cc13c6e7226031e5f462c5adb` |
| **`paramsHash`** | `8fe841e602be86cd335c9aa6804a8f30c76c57cac229a50b349194d821c6cae5` |

Both were declared in PREREG-002 §2 **before the first run**, computed offline, then confirmed
against the live engine by the C1 preflight. Both appear on **221 of 221** campaign packages with no
variation. `configHash` is SHA-256 over the canonicalized `snapshotAlexGConfig()` (the frozen
`RULES_ALEXG`); `paramsHash` is SHA-256 over the canonicalized replay parameter set above.

### Per-run identity

| Run | Instrument | runId | datasetHash |
|---|---|---|---|
| C1-01 | GBP_USD | `f230a04976d427c4b149b9f1e493600bab0d7053bfc39bf73f978e247bb8fa83` | `7f4bff4911776b826c712afdc04decc32923286272dce2276db4b23ea6c70743` |
| C1-02 | GBP_JPY | `915bc83f587de11ccc9246da0da8fcb5526acfa8869208583e3a49be44b5cf0c` | `f35395246ace9b482da97dc71f9d5a7c8b9f017609bdabeedfd8797771a43254` |
| C1-03 | AUD_USD | `88d924c0be04a5112efb94d7de3b2839e1cd176011603b1f7dd0a39b81d29f8d` | `05cccf71083eb9d9a5be0fa015e054668ce0b108898bc467f95737a8ad627c4e` |
| C1-04 | USD_JPY | `4689c3d17f806cb1d484beca183e9fc6cffceeedc286ee9a5170d9c2c2a147ff` | `ae427698faded1e9d15d9b54e9db6b68db1298c28f32446aa2af2c4e6f3d93bf` |
| C1-05 | GBP_CHF | `ff5dd403ea8d859016979c8f64167ff23034d1117e78ea138893ed0c443433c4` | `47ea41d0a6b2d7338cbe208f16c46baeba15ea1861070f62c2b6516ddfb4396a` |
| C1-06 | GBP_CAD | `ca6c0038a27b3fb96ac9b02f970c9ef340de016fd508df4c587ed649223b4fca` | `8cbd84e8ab198c9cc3425d258aff6378a99776063628accbfeb366d5cee77f6c` |
| C1-07 | NZD_USD | `80a17b22e3f86880f8e623236d49eaa6713a29e9775d05bcecaed6965bbbb465` | `65066dd9c8ca9726eeb55e7c1eedb56177570a88dbe52a50af4b8a3a4348c728` |
| C1-08 | AUD_JPY | `3b36727d569451c8eee0aeae2c8be8012b93b3bc4eace09e8182e61af9fb800b` | `9bbcdded5bc56b06a9d6de3073b1c2f77f27e3d9db2a66e4bf7ae5489d367333` |
| C1-09 | EUR_JPY | `8f70d403fae143057545cb7118965ca33f5ee508ba41bd64e98a85fb14e62597` | `f6c997ecc75553f7753c0d716017475c6acf6747a49f64811ff67f90bccd802c` |
| C1-10 | USD_CAD | `367dd27fd6b865300d42e43a83ccfe647a3d4440cb735592156817508a4aef6c` | `7ea6a7ec501598c3bacf94e705fbfc8542ede303a1d29b37bf07af4fed413bb5` |
| C1-11 | USD_CHF | `81b566549f6a5e81c6d5d7eda63c6e314d445feca6138087f891d753454b7b50` | `d7d8c65e2b2fd9129a54dfd49c97ac0e4ebc11878fea98d68f17fe0800e3c01a` |

`runId` is SHA-256 over strategyId + pair + observed range + `datasetHash` + `configHash` +
`paramsHash` — deterministic and content-derived, never random and never wall-clock. `datasetHash`
covers **every candle's OHLC across all four timeframes**, not a count/first/last fingerprint, so a
broker revising a candle mid-range is detectable.

## Suppression methodology

**Mechanism.** ALEX permits one open replay trade per pair per timeframe. A setup qualifying while a
position is already open on that pair+timeframe is suppressed and recorded in `alexGReplayRejected`
with reason `EXISTING_OPEN_TRADE_SAME_PAIR_TIMEFRAME`. Setups are processed strictly by
`qualificationTimestamp` ascending.

**Capture.** `alexGReplayRejected` (`index.html:4119`) is reassigned on every replay and never
persisted, so it was captured to disk after each run and before the next. All eleven runs have a
complete record; every record carries a reason.

**Rate definition.** `suppressed ÷ (trades created + suppressed)`, following the precedent PREREG-001
§9 set for RUN-001 (24 traded + 15 suppressed = 39 considered). The denominator is **trades created**,
not packages — a still-open trade produces no package but was still a trade.

| | |
|---|---|
| Trades created | 226 |
| Suppressed | 128 |
| Considered | 354 |
| **Campaign suppression rate** | **36.2%** (per-run range 24.2% – 58.6%) |

**This censoring is informative, not random.** It correlates with setup clustering, which correlates
with market structure. The 221 observations are a **biased draw from 354**, not a smaller unbiased
sample, and no sample size corrects it. PREREG-001 §9: *a result computed on a censored sample that
does not report the censoring is not a result.*

---

**Frozen 2026-08-06. Nothing in this document is adjudicated.**

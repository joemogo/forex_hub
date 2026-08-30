# LEAN runtime evidence record — synthetic Mode B engine smoke test

**Status: OBSERVED.** This records what a genuine QuantConnect Cloud / LEAN run returned on
2026-08-30. Every value below is either a supplied identifier or a verbatim log line.

## 1. The run

| Field | Value |
|---|---|
| Project ID | `35863117` |
| Backtest name | `Calm Yellow Pig` |
| Algorithm ID | `3fca3b003a7f8db84f343512ea9835fa` |
| LEAN version | `v2.5.0.0.18041` |
| Date observed | 2026-08-30 |
| Log | `CALM_YELLOW_PIG_2026-08-30.log` (2,314 bytes, 27 lines) |
| Log SHA-256 | `83e377e54c5dc93b83416fe023598425d2e431a4c1767a63b329d149c71b1ecd` |

Platform launch record: `Launching analysis for 3fca3b003a7f8db84f343512ea9835fa with LEAN
Engine v2.5.0.0.18041`
Platform completion record: `Algorithm Id:(3fca3b003a7f8db84f343512ea9835fa) completed in 1.83
seconds at 1k data points per second. Processing total of 983 data points.`

## 2. Result

**22/22 SMOKE-CHECK PASS. SMOKE-VERDICT PASS engine=LEAN failed=none.**

| Case | bars | state | decision | locked_at |
|---|---|---|---|---|
| SYNQUAL | 120 | LOCKED | True | 55 |
| SYNREJ | 120 | BROKEN | False | None |

Independently validated, 21 assertions over the log bytes: exactly one launch and one
completion record, both naming the same algorithm id; only ONE algorithm id anywhere; exactly
22 checks split 10/10/2; every check PASS and the string `FAIL` absent; no duplicate check
name within a case; both cases ran the identical check set; every logged check name is
declared in the committed algorithm; both GLOBAL checks present; exactly two SMOKE-CASE lines
and one verdict; outcomes equal to the committed `EXPECT` literals; and the verdict
contradicts no individual check.

## 3. What this establishes — and what it does not

**Established.** LEAN's own event-driven subscription pipeline delivered 120 synthetic bars per
case into `on_data`; the reviewed state machine consumed each exactly once, in order, with no
bar arriving before its own `EndTime`; a constructed qualifying setup produced a decision at
bar 55 and a constructed invalid setup produced none; per-case state stayed isolated and no
unexpected symbol was delivered. This is the first run in this project to establish
event-driven delivery at all — Mode A's `Creative Red Panda` ran inside LEAN but subscribed to
no feed and read embedded bars.

**NOT established.** Historical Mode B parity. Any statement about the 15 preserved cases. Any
resolution of the five Mode A break-cycle divergences. Any order execution, profitability, or
production readiness. The run placed no orders, added no broker and held nothing.

## 4. Provenance — verified vs inferred

**Verified by hash, locally:** the log above; and the reproduction inputs in the parent
directory, per `../MANIFEST.sha256` — `br_machine.py`
`29e29578c1b841b7e03a13ba58ca1692815094922adbe00b7fba387b98aaa54a`, `synthetic_bars.py`
`aa138cad8ee8428ad00dacbd50c836c7ce55a75e03ec25799951d4e502d1ea3d`.

**Verified by hash, over the network before use:** the two published fixtures, downloaded and
compared against their approved digests —
`mogo_synthetic_qualify.csv` `61e7244d421b0bcfba046913a4ed85e1563c1fbca19c71c00f2f6c4614c373d1`,
`mogo_synthetic_reject.csv` `d40b2fdbcec496dc124ea97da975c3df8321519911341ef9381a7da8261cff26`.
Served from public gist `849a3ef9d9d13d7e7d74045428fbbdb7`, revision `9e73b2341a80526530b11d4c29f6ca1cac8f312e` (revision-pinned).

**INFERRED, not verified.** The source that actually executed in the cloud was **NOT downloaded
from QuantConnect and NOT hash-compared** against the repository. Its identity rests on:

  1. the operator's reported procedure — `pbcopy < tests/lean_synthetic/main.py` from reviewed
     adapter commit `b1d46d3f89429464e6a647b465fd47075e765ebe`, pasted over `main.py`; and
  2. behavioural corroboration in the log itself: the two GLOBAL checks
     (`no_unexpected_symbols`, `case_state_isolated`) exist only in the repaired adapter, the
     22-check shape matches only the post-repair algorithm, the reported expectations match its
     `EXPECT` literals exactly, and the immediately preceding revision failed on every row with
     `set_item: (str, int)` where this run parsed all 240 bars — which the float-field repair
     in `b1d46d3` is what changed.

That is strong circumstantial agreement, **not** a hash of the executed source. Treat the
cloud-side source identity as inferred.

**Not derived:** LEAN's `983 data points` is a platform throughput counter across all
subscriptions, including internal feeds. It is not contradicted by the 240 delivered bars
(a larger figure is expected), but it was **not** reproduced from first principles here. The
per-case counts of 120 are the algorithm's own, asserted in `OnEndOfAlgorithm`.

## 5. Operator upload procedure, as reported

Three files uploaded to project `35863117`: `main.py`, `br_machine.py`, `synthetic_bars.py`.
The CSVs were **not** uploaded — LEAN fetched them over HTTPS from the pinned gist revision.
One backtest, free tier, no broker, no orders. The parity project `35636512`
(`Creative Red Panda`) was not modified.

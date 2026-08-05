# MOGO-004 Step 1 Pilot — Recovery Report & Declared Engineering Limitations

**Prepared:** 2026-08-05 · **Repository HEAD:** `bb8498f` · **Engine:** `APP_VERSION` 12.18.0
**Pilot of record:** `runId 2d5004cba59bed9cf0cbd0ea6d28b4db4baaef6e4a8fa090760234f10bc047e0`
**Pilot gate (PRE-REG-001 §6):** **PASS**

> **Supersedes `MOGO-004-STEP-1-PILOT-EXECUTION-BLOCKED.md`**, which states *"Replay runs executed:
> ZERO."* That statement was true when written and is false as a record of what happened: it was
> prepared before the operator supplied the test origin, and two replay runs executed afterwards on
> 2026-08-04. The earlier report is retained for sequence, not for its conclusions.

---

## 1. What happened

The pilot ran. Its evidence was captured to IndexedDB and never reached disk, because the browser
export path failed without producing an error. Chrome's `downloads` table for the test profile
contains **zero rows** — no download was ever registered, so nothing surfaced to the operator and the
run appeared to have produced no artifacts. The evidence was recovered intact on 2026-08-05 from the
still-running disposable profile via a local HTTP receiver.

**No data was lost from the pilot of record.** One artifact from the companion run was lost, and two
identity fields were never persisted by the engine; both are declared in §4.

## 2. Recovered artifacts

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `PILOT-PACKAGES-all.json` | 2,652,720 | `069fc63135b6dff6e58667f83a8968f808c8fa2a6aee2590729b1081e0f855d3` |
| `PILOT-HARVEST-full.json` | 121,727 | `0331776362c1c67c51f3413fdf3317200ee28a072fbe7121941c0f500f260e9b` |
| `PILOT-REJECTED-full.json` | 3,604 | `9e2662f103305b4524785a5ba2a8ee95a9975fbba20561f7a2da87fb6f4dc4b9` |

Preserved at `~/Desktop/MOGO-Evidence-PILOT/01-RECOVERED/` with the receiver transcript. A cold copy
of the source profile is preserved at `00-PROFILE-COLD-COPY/`, its IndexedDB write-ahead log
hash-verified byte-identical to the live source (`58354d28…bddf88d7`).

**Hash verification: 50 of 50 packages PASS, 0 FAIL.** Each package was independently re-canonicalized
under `mogo.evidence-canon.v1` (rules K1–K8) in a clean-room verifier and its `contentHash`
recomputed. The same verifier reproduces all 24 RUN-001 hashes, so the canonicalizer is validated
against known-good data rather than trusted.

## 3. Pilot gate — PASS

PRE-REG-001 §6 requires populated `triggeredConditions`, `timeToMFE`/`timeToMAE` and market context.

| Gate field | Run 1 `8dd5a8f1…` | **Run 2 `2d5004cb…` (pilot of record)** |
|---|---|---|
| `triggeredConditions` | 25/25 | **25/25 PASS** |
| `timeToMFE` | 25/25 | **25/25 PASS** |
| `timeToMAE` | 25/25 | **25/25 PASS** |
| `marketContexts` | 25/25 | **25/25 PASS** |
| `exitPathCandleRefs` | 25/25 | 25/25 (informational) |

RUN-001 (engine 12.9.0) scored **0/24 on all four**. The capture layer added since is doing what it
was built to do. `triggeredConditions` carry `conditionId`, `ruleId`, requirement text, observed
values, `satisfied` and `provenance` — attribution at rule level, not a boolean.

**Composition of the pilot of record:** 25 trades, 5 Win / 20 Loss, 15 `A_repeatedReaction` /
10 `B_breakRetest`, timeframes H1 19 / H4 5 / D 1. Observed window `2026-03-27T12:00Z` →
`2026-08-04T23:00Z`; candle counts W 73 / D 150 / H4 600 / H1 2220; ADR-011 completeness `COMPLETE`
on all four timeframes.

**Censoring (§9):** 8 setups suppressed, all `EXISTING_OPEN_TRADE_SAME_PAIR_TIMEFRAME`; 25 traded of
33 considered — a **24.2% suppression rate**, against RUN-001's 38.5% (15 of 39). Per §9 this rate
must accompany every figure computed on this sample.

---

## 4. Declared engineering limitations

These are recorded as limitations of the instrument, not as defects introduced by the run. Each is
disclosed here so that no figure derived from this pilot is later described as more complete than it is.

### L1 — Two runs were executed where the pre-registration declared one

PRE-REG-001 §6 declares `Runs: 1` for the pilot. Two replay runs executed on 2026-08-04, roughly two
hours apart, and both captured into the same evidence store.

**Cause — engine behaviour, not operator error.** `fetchCandlesRange` (`index.html:5937`) paginates
backward from *run time* by candle count; there is no `from`/`to` control (PRE-REG-001 §6, gate item
**B2**, open). Two runs at different wall-clock times therefore observe different absolute windows,
producing different `datasetHash` values and — because `runId` is a SHA-256 over strategyId, pair,
range, `datasetHash`, `configHash` and `paramsHash` (`index.html:13583-13586`) — different `runId`s.
Re-capture is idempotent only for an identical window, so the second run appended rather than
deduplicated.

**Materiality — none to the result.** The two runs are the same experiment observed twice:

| | Run 1 `8dd5a8f1…` | Run 2 `2d5004cb…` |
|---|---|---|
| Observed window ends | `2026-08-04T21:00Z` | `2026-08-04T23:00Z` |
| `setupId` set | 25 | 25 — **identical, 25/25 overlap** |
| Outcomes | 5 Win / 20 Loss | 5 Win / 20 Loss |
| Setup types | 15 A / 10 B | 15 A / 10 B |

Replay reproduced itself exactly across a two-hour window shift. **Run 2 is designated the pilot of
record** because it is the only run for which the §9 rejection record survives. Run 1 is retained as
a companion observation and **must not be pooled with Run 2** — the two share all 25 setups, so
combining them would double-count every trade.

**Consequence for C1:** any two runs of this campaign executed at different times are not
window-comparable by construction. This is already declared in PRE-REG-001 §6 and is restated here
because the pilot demonstrated it empirically.

### L2 — `configHash` and `paramsHash` are computed but never persisted

PRE-REG-001 §8 item 1 requires `runId`, `datasetHash`, `configHash` and `paramsHash` for every run
**without exception**. Only the first two reach the evidence package.

Both hashes are computed at `index.html:13581-13582` and returned on the run-identity object at
`:13587`. The replay capture seam has that object in hand at `:13734` and constructs the package
identity from `mode`, `runId`, `datasetHash` and `replayDateRange` only. The identity whitelist at
`:13513` carries the same four fields. Nothing else retains the run-identity object:
`runIdentity` is a local in `runAlexGReplay` (`:4048`), returned into a local `const result` in
`runAlexGReplayUI` (`:4102`), and `alexGReplayState` is reused for run control only (`:2181`) — its
`lastResult` is never assigned for ALEX.

**Consequence:** `configHash` and `paramsHash` are **unrecoverable for both pilot runs**, and will be
unrecoverable for every C1 run, unless the evidence layer is changed to persist them. A re-run cannot
recover them for these runs, because a re-run observes a different window and is therefore a
different run (see L1).

**Status: OPEN. This blocks strict §8 compliance for Campaign C1.** Resolution requires either an
additive change to the package identity, or an amendment to §8. Both are decisions for the operator.

### L3 — The rejection record is memory-only and survives exactly one run

`alexGReplayRejected` (`index.html:4119`) is reassigned on every run and is never persisted. Run 1's
rejection record was overwritten by Run 2 and is **permanently lost**, making PRE-REG-001 §9
unsatisfiable for Run 1 — which is why it cannot be the pilot of record.

**Consequence for C1:** the rejection record must be captured **after every single run, before the
next run begins**. Eleven C1 runs performed back-to-back would retain one rejection record and lose ten.

### L4 — Browser export failed silently

The export path produced no file and no error: Chrome's `downloads` table for the test profile holds
zero rows and the profile's `Preferences` contains no download keys. The operator had no signal
distinguishing "export succeeded" from "export never happened". The v12.8.0 design is correct in
refusing to mark unexported packages as exported — the gap is that silence was indistinguishable from
success. Evidence left the browser only via a local HTTP receiver built as a recovery path.

**Consequence for C1:** the receiver path, not the download path, is the supported egress until this
is addressed. Note the receiver binds IPv4 `127.0.0.1` only while the browser resolves `localhost` to
`::1`; egress must target `127.0.0.1` explicitly.

### L5 — Repository commit is not captured

PRE-REG-001 §8 item 4 requires the repository commit. Packages carry `commitHash: null` with
provenance `UNAVAILABLE`. This is satisfiable externally by recording HEAD in the run record; for
this pilot, HEAD is `bb8498f`.

### L6 — Export-verification by re-import has not been performed

PRE-REG-001 §8 item 5 requires packages be export-verified by re-import. The `export` block on all 50
packages is `{exportedAt: null, exportMechanism: null, exportFilename: null, exportVerified: null}`.
Packages were recovered by direct read, not by the export path, so no export has been verified. Per
the EXP-001 counting rule, only a verified re-import clears a package from the unexported count.

**Status: OPEN.**

---

## 5. Record status against PRE-REG-001 §8

| # | Requirement | Pilot of record |
|---|---|---|
| 1 | `runId`, `datasetHash` | ✅ |
| 1 | `configHash`, `paramsHash` | 🔴 **L2 — unrecoverable** |
| 2 | Observed absolute UTC window + candle counts | ✅ |
| 3 | ADR-011 `completenessState` per timeframe | ✅ `COMPLETE` ×4 |
| 4 | Engine `APP_VERSION` | ✅ 12.18.0 |
| 4 | Repository commit | ⚠️ L5 — external, HEAD `bb8498f` |
| 5 | Hash-verified packages | ✅ 50/50 |
| 5 | Export-verified by re-import | ⏸️ L6 — open |
| 6 | `alexGReplayRejected` in full | ✅ for Run 2 · 🔴 lost for Run 1 (L3) |
| 7 | Entry in `MOGO-003-VERIFIED-REPLAY-RECORD.md` | ⏸️ pending |

## 6. Standing constraints

- **No strategy logic was modified.** No code was modified at any point during the pilot or its recovery.
- **Campaign C1 has not begun.** See the open items in §4 (L2) and the undeclared instrument list.
- **No hypothesis has been adjudicated.** PRE-REG-001 §7 permits adjudication once, after the declared
  runs complete.
- **Promotion ceiling remains `REPLAY_EVIDENCE_ONLY`.** RZR remains suspended. No strategy is approved
  for live execution.

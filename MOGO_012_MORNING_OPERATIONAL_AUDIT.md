# MOGO-012 — Morning Operational Audit

**Audit run:** 2026-08-11 08:03–08:10 ET (12:03–12:10 UTC) · **read-only**
**Campaign:** ALEX forward paper trading, activated **2026-08-10 22:43:57 ET** (`2026-08-11T02:43:57.894Z`)
**Elapsed:** 9 h 20 m unattended · **PAPER ONLY — live-money trading not authorized**
**Overall status: 🟡 YELLOW**

---

## Executive summary

**1. Did MOGO operate unattended overnight?** Mostly. The application never crashed, never reloaded, and is scanning all 12 instruments right now with fresh data. But there is a **~6-hour window in which live evaluation did not happen**, and it cost the campaign its only genuine forward observation.

**2. Is forward-paper evidence collection trustworthy right now?** Yes, as far as it goes — every integrity control passes, and nothing false or corrupt entered the record. The weakness is **completeness, not correctness**: MOGO cannot presently prove what it did or did not evaluate overnight, because it keeps no durable log of its own polling.

**3. Did MOGO make any genuine forward trades?** No. Zero trades requested, opened, or closed.

**4. Did the first real forward evidence package appear?** **NO GENUINE FORWARD EVIDENCE PACKAGE YET.**

**5. Does anything require intervention?** Yes — one thing, and it is operational, not engineering. The Mac slept and the MOGO tab is in the background on battery. Exactly one setup qualified after activation (AUD_JPY, 06:00 UTC) and was not evaluated until 12:01 UTC — 361 minutes later — so the frozen staleness rule permanently rejected it. **The rule worked correctly. The host did not stay awake.**

This is now formally recorded as **[MOGO-012-INC-001 — Forward Observation Continuity Gap](#mogo-012-inc-001--forward-observation-continuity-gap)**, and a controlled observation period with an explicit decision rule is under way.

Nothing about the strategy, the evidence platform, or the gate is malfunctioning. No code change is recommended today.

---

## A. Forward trading state

| # | Check | Result |
|---|---|---|
| 1 | `alexGAutoTrading.enabled` | ✅ **true** — activated `2026-08-11T02:43:57.894Z` |
| 2 | Durable evidence profile active | ✅ `/Users/joemogollon/MOGO-EVIDENCE-PROFILE/profile` — the **only** `--user-data-dir` in any running Chrome |
| 3 | Pinned origin | ✅ `http://localhost:8751`, secure context, APP_VERSION 12.19.0 |
| 4 | Polling / scanning loop | ✅ **active** — timer live, `alexGLivePollingShouldRun()` true, scans observed at 12:02:35Z and 12:03:35Z (60 s cadence) |
| 5 | Broker/API session | ✅ **authenticated and functional** — credentials present, market data flowing for all 12 pairs |

**No credential loss, expiry, or interruption was observed.** Chrome has run continuously since `2026-08-10 22:34:44 ET`; the page has not reloaded (`performance.timeOrigin` = `02:34:44.594Z`, navigation type `navigate`, 572 minutes old). Credentials remain **in memory only** — no credential keys exist in `localStorage` — so a reload would require re-entry. Nothing was done to weaken that.

---

## B. Market-data health — all 12 instruments healthy

At sample time (12:05 UTC) every expected instrument reported identical, current candle state:

| Timeframe | Last close | Age | Assessment |
|---|---|---|---|
| H1 | `2026-08-11T12:00:00Z` | ~5 min | ✅ current |
| H4 | `2026-08-11T09:00:00Z` | ~185 min | ✅ normal (4 h bars) |
| D | `2026-08-10T21:00:00Z` | ~905 min | ✅ normal (daily close) |
| W | `2026-08-07T21:00:00Z` | ~5225 min | ✅ normal (weekly close) |

**Healthy:** GBP_USD, EUR_USD, GBP_JPY, AUD_USD, USD_JPY, GBP_CHF, GBP_CAD, NZD_USD, AUD_JPY, EUR_JPY, USD_CAD, USD_CHF — **12 of 12**.
**Stale:** none · **Unavailable:** none · **`DATA_UNAVAILABLE` events:** 0 · **Broker/API failures:** none observed.

GBP_USD and EUR_USD have **no tracked setups**, which is a *structure* observation, not a data fault — both carry fresh candles across all four timeframes.

---

## C. Post-activation strategy activity

Counting only setups whose **`qualificationTimestamp` ≥ activation**, so the 299 correctly-classified `CONFIG_BEFORE_ACTIVATION` setups are excluded from the forward sample.

| # | Metric | Count |
|---|---|---|
| 6 | **Post-activation setups evaluated** | **1** |
| 7 | Rejected setups | **1** |
| 8 | Qualifying setups (passed all gates) | **0** |
| 9 | Paper trade requests | **0** |
| 10 | Successful opens | **0** |
| 11 | Failed opens | **0** |
| 12 | Currently open positions | **0** |
| 13 | Closed positions | **0** |

**Rejection reasons (post-activation):** `SIGNAL_TOO_OLD_AT_FIRST_EVALUATION` × 1.
**Rule results (post-activation):** `ALEX_ACTIVATION_CUTOFF: PASS` × 1 · `ALEX_SIGNAL_STALENESS: FAIL` × 1.

For completeness, the 299 pre-activation setups were all `IGNORED — BEFORE ACTIVATION` via `ALEX_ACTIVATION_CUTOFF: FAIL` / `CONFIG_BEFORE_ACTIVATION` — the intended no-backfill behaviour, correctly refusing to import 90 days of reconstructed history into a forward sample.

**Zero qualifying setups and zero trades is a legitimate forward observation and is not, by itself, evidence of malfunction.** One partial night across 12 pairs on an H1 setup engine is an entirely plausible zero. However, the *reason* the single candidate was rejected is an operational finding — see §G.

---

## D. Paper account state

| Metric | Value |
|---|---|
| Starting balance | $10,000.00 |
| Current balance | **$10,000.00** |
| Realized P&L | **$0.00** |
| Unrealized P&L | **$0.00** (no open positions) |
| Wins / Losses | **0 / 0** |
| Realized R | **0.00** |
| Current drawdown | **0.00%** |
| Max campaign drawdown | **0.00%** |
| Open / Closed trades | **0 / 0** |
| Journal entries | **0** |

No inference about profitability is possible or attempted. The sample is empty.

---

## E. Forward evidence

| Metric | Value |
|---|---|
| Total evidence packages in `mogo_evidence` v1 | **0** |
| Legacy packages in this store | **0** (the 220-package legacy corpus lives in the preservation checkpoint, not the live store) |
| Genuine forward-paper packages | **0** |
| Evidence writes attempted | **0** |
| Successful writes | **0** |
| Write failures | **0** |
| `sourceTradeId` reconciliation issues | **0** |
| Duplicate-protection issues | **0** |
| Hash / integrity issues | **0** |

Store health: `evidenceDbUnavailableReason: null`, no storage banner, SHA-256 available, auto-export correctly **OFF**, capture idle and armed. Reconciliation over the (empty) store returns zero for every defect class.

Zero packages is **consistent and correct**: evidence is captured on trade close, and no trade opened.

---

## F. First genuine forward evidence package

# NO GENUINE FORWARD EVIDENCE PACKAGE YET

No trade opened, therefore no package could be created. No trade or synthetic package was manufactured to produce one. The full field-level integrity audit specified for this section is deferred until a real package exists.

---

## G. Operational reliability

| Problem class | Count | Severity |
|---|---|---|
| `ENGINE_ERROR` | **0** | — |
| `DATA_UNAVAILABLE` | **0** | — |
| Broker / API errors | **0 observed** | — |
| Authentication / credential failures | **0** | — |
| Application crashes | **0** — page continuous 9.5 h, no reload | — |
| Unexpected exceptions | **0 observed** | — |
| Evidence write failures | **0** | — |
| Evidence reconciliation failures | **0** | — |
| Checkpoint failures | **0** | — |
| Integrity / hash failures | **0** | — |
| **Polling / evaluation interruption** | **1 window, ~6 h** | **⚠️ Material** |

### The one real finding: a ~6-hour evaluation gap cost the only forward observation

| | |
|---|---|
| Instrument / setup | **AUD_JPY H1**, `A_repeatedReaction` |
| Qualified at | `2026-08-11T06:00:00Z` (02:00 ET) — **196 minutes after activation** |
| First evaluated at | `2026-08-11T12:01:05Z` (08:01 ET) |
| Age at first evaluation | **361 minutes** |
| Outcome | `IGNORED — STALE SIGNAL` / `SIGNAL_TOO_OLD_AT_FIRST_EVALUATION`, **final and non-retryable** |

**The staleness rule behaved exactly as designed** — an H1 signal may only be taken within one bar-period of qualification, and a 6-hour-old signal must not be traded. The defect is not in ALEX; it is that the setup was not *seen* for six hours.

**Contributing conditions, established from system evidence:**

- **The host slept.** `pmset` confirms `Clamshell Sleep` at **06:30:37 ET**, a maintenance DarkWake at 07:24:32, `Maintenance Sleep` at 07:25:02, and `Wake … due to EC.LidOpen/UserActivity` at **07:47:25 ET**. Two sleep/wake cycles since boot.
- **The tab is hidden and the machine is on battery** — `document.visibilityState: "hidden"`, `hasFocus: false`, `Using Batt (Charge:100%)`. These are precisely the conditions under which Chrome applies intensive background-timer throttling and macOS applies App Nap.
- First evaluation occurred **~14 minutes after lid-open wake**, consistent with the poller resuming only once the machine and tab became active again.

**Honest limit on this conclusion:** the confirmed sleep window (~1 h 17 m) does **not** by itself account for six hours. The gap between 06:00 and 10:30 UTC cannot be attributed with certainty, because **MOGO keeps no durable record of its own polling** (see below). The likely explanation is background throttling before sleep plus sleep itself, but that is inference, not measurement, and is labelled as such.

### Observability gap (the reason this audit could not be fully conclusive)

The Decision Event bus is **memory-only and bounded at 500 entries**. At audit time it held exactly 500 events spanning **12:01:01Z → 12:03:37Z — 2 minutes 36 seconds**. It is a live diagnostic window, not an operational log, and it cannot reconstruct an overnight period. There is presently **no durable answer to "did MOGO poll at 07:00 UTC?"**

- **Was forward evidence lost?** No evidence *package* was lost — none existed. What was lost is **one forward observation**: a candidate that would otherwise have been evaluated live and either traded or rejected on its merits. For a campaign whose product is observations, that is a real cost.
- **Does this require immediate engineering intervention?** **No.** It requires an **operational** change (keep the host awake and the tab foregrounded). A durable poll heartbeat is worth doing later, under Lane A governance — not today.

---

## MOGO-012-INC-001 — Forward Observation Continuity Gap

**Status:** OPEN — under controlled observation
**Opened:** 2026-08-11 (first formal MOGO-012 operational continuity incident)
**Classification:** **FORWARD OBSERVATION INCOMPLETENESS / OPERATIONAL CONTINUITY INCIDENT**

### Incident record

| Field | Value |
|---|---|
| Instrument | **AUD_JPY** |
| Timeframe | **H1** |
| Setup | **Repeated reaction** (`A_repeatedReaction`) |
| Setup (qualification) time | **~06:00 UTC** (`2026-08-11T06:00:00.000Z`) |
| Evaluation time | **~12:01 UTC** (`2026-08-11T12:01:05.807Z`) |
| Delay | **~361 minutes** |
| Final disposition | **`SIGNAL_TOO_OLD_AT_FIRST_EVALUATION`** — `IGNORED — STALE SIGNAL`, final and non-retryable |
| Trade requested | **NO** |
| Trade opened | **NO** |
| Evidence package created | **NO** |

### Scientific interpretation

The setup **qualified when generated**. MOGO did not observe or evaluate it in time. On finally evaluating it, **ALEX behaved correctly by rejecting the stale signal** — an H1 signal six hours past its qualification bar must not be taken.

**This incident is explicitly NOT:**

- ❌ a losing trade — no trade was requested or opened, and no capital was at risk;
- ❌ a strategy failure — the frozen ALEX rules produced the correct decision on the information available to them;
- ❌ an execution failure — nothing was submitted, so nothing failed to execute.

**It IS:** a gap in *forward observation coverage*. The cost is scientific, not financial — one market opportunity that MOGO should have evaluated live was instead evaluated too late to be actionable, and therefore contributes no forward outcome to the campaign sample.

### Causal attribution — confirmed facts vs. inference

**Confirmed by system evidence:**

- macOS sleep occurred: `Clamshell Sleep` at **06:30:37 ET**, maintenance `DarkWake` 07:24:32 ET, `Maintenance Sleep` 07:25:02 ET, `Wake … due to EC.LidOpen/UserActivity` at **07:47:25 ET** (`pmset -g log`; two sleep/wake cycles since boot).
- The application did **not** crash or reload: `performance.timeOrigin` = `2026-08-11T02:34:44.594Z`, navigation type `navigate`, Chrome process continuous since 22:34:44 ET.
- At audit time the page was `visibilityState: "hidden"`, `hasFocus: false`, and the host was on battery.
- First evaluation occurred **~14 minutes after the lid-open wake**.

**Explicitly labelled INFERENCE, not measurement:**

- **Confirmed Mac sleep explains only PART of the evaluation gap.** The confirmed sleep window is ~1 h 17 m; the observed gap is ~6 h. The interval from roughly 06:00 to 10:30 UTC is **not** accounted for by any confirmed sleep event.
- **Browser background throttling is a plausible contributing factor** — a hidden tab on battery is precisely the condition under which Chrome applies intensive timer throttling and macOS applies App Nap. This is a hypothesis consistent with the facts, not an established cause.
- **Complete root-cause reconstruction is NOT POSSIBLE**, because durable historical polling telemetry does not exist. The Decision Event bus is memory-only and bounded at 500 entries; at audit time it held **2 minutes 36 seconds** of history. There is no durable answer to "did MOGO poll at 07:00 UTC?"

**Therefore: causal attribution beyond the confirmed facts above remains explicitly labelled as inference, and no root cause is declared.**

### Controlled observation period

The operator is now running a controlled observation period. Conditions **verified by measurement** at 2026-08-11 08:26 ET:

| Condition | Verified state |
|---|---|
| Mac connected to power | ✅ `Now drawing from 'AC Power'` (battery 100%, charged) |
| macOS sleep prevented | ✅ persistent `caffeinate -dimsu` (PID 51532, started 08:25:20 ET); `PreventSystemSleep 1`, `PreventUserIdleSystemSleep 1` |
| Lid open | ✅ implied — machine awake on AC with no clamshell-sleep assertion |
| Durable MOGO profile running | ✅ `/Users/joemogollon/MOGO-EVIDENCE-PROFILE/profile` — the only `--user-data-dir` in use |
| ALEX unchanged | ✅ `enabled: true`, polling active, 300 setup statuses, $10,000.00, 0 open / 0 closed |
| **MOGO application visible** | ⚠️ **NOT CONFIRMED** — the page still reports `visibilityState: "hidden"`, `hasFocus: false` |

⚠️ **One controlled variable is not currently measurable as met.** The MOGO page reports **hidden**, which means the tab is not the active tab in its window, or the window is minimised. Since background throttling is the *leading* inferred contributor, leaving the tab hidden would fail to isolate the variable the controlled period is meant to test. Bringing the MOGO tab to the foreground of a non-minimised window would make the test conclusive. *(A Chrome window merely occluded by another application normally still reports `visible`, so this is unlikely to be simple occlusion.)*

No action was taken on this — recorded for the operator's decision.

### Decision rule for this incident

> **IF** material polling/evaluation gaps **recur** under the controlled conditions above —
> **THEN** recommend the **smallest durable polling-heartbeat / continuity mechanism** needed to establish retrospective polling completeness.
>
> **IF** they **do not recur** —
> **THEN** continue the forward campaign **without engineering interruption**.

Evaluation of this rule is deferred to the next operational audit. Nothing is implemented in the meantime: no heartbeat, no code change, no restart, no ALEX modification, and no MOGO-012-BL-001 work.

---

## H. Checkpoint / preservation status

| | |
|---|---|
| Checkpointing operational | ✅ yes |
| Most recent checkpoint | `~/MOGO-EVIDENCE-PRESERVED/20260811T024103Z` (02:41 UTC, taken at activation) |
| Durable live store | 16 KB, `UNCHANGED since the last checkpoint` (verify-only, idempotent) |
| Forward evidence existing only in the browser profile | **None — there is no forward evidence yet** |
| Evidence at risk | **None** |
| Another checkpoint warranted? | **No** — the store is byte-identical to the existing checkpoint |

No restart or reload was performed to create a checkpoint.

---

## I. Campaign C1 / legacy preservation

**Campaign C1 — re-verified this morning, not assumed:**

| | |
|---|---|
| Verified | **33 / 33** |
| Missing | **0** |
| Mismatched | **0** |
| Unlisted | **0** |
| Total bytes | **13,575,486** |
| Verdict | **VERIFIED** |
| Committed attestation file | unchanged |

**Preserved legacy corpus:** 37 files / 8.0 MB · baseline re-verified — **220 packages re-derived, 0 mismatched**, rollup matches.

Legacy packages lacking `captureOrigin` remain expected and untouched; nothing was rewritten.

---

## J. Repository state

| | |
|---|---|
| Branch | `main` |
| HEAD | `8e8a0afce7aaf639ee21e4ecb605d754f5bb321a` — *MOGO-011 Phase A: Campaign C1 integrity reaches the gate…* |
| Working tree | **clean** (tracked) |
| Ahead / behind `origin/mogo-main` | **0 / 0** |
| Unexpected uncommitted changes | **none** |
| Untracked | 35 pre-existing MOGO-010/011 report files (unchanged), plus this report |

Nothing was committed.

---

## K. Campaign C1 attestation freshness

| | |
|---|---|
| `generatedAt` | `2026-08-11T01:53:43.653Z` |
| Age at audit | **10.18 hours** |
| Limit | 24 hours |
| Verdict | ✅ **PASS** |

The attestation was **not** regenerated. Live preflight re-run read-only: **PASS, zero blockers.**

⏰ **It expires at `2026-08-12T01:53:43Z` (2026-08-11 21:53 ET).** After that, the forward-paper gate will refuse until `node scripts/mogo_evidence_verify.js --campaign-c1-attest` is re-run. This matters only if trading is toggled off and back on.

---

# SCORECARD 1 — SYSTEM HEALTH

| Component | Status |
|---|---|
| Polling loop active now | 🟢 GREEN |
| **Polling continuity overnight** | 🟡 **YELLOW** — ~6 h evaluation gap |
| Broker / API connection | 🟢 GREEN |
| Market data | 🟢 GREEN |
| Instrument coverage (12/12) | 🟢 GREEN |
| Evidence capture armed | 🟢 GREEN |
| Hashes / integrity | 🟢 GREEN |
| Reconciliation | 🟢 GREEN |
| Checkpoints | 🟢 GREEN |
| Errors (engine/data/write) | 🟢 GREEN — zero |
| Uptime / continuity | 🟢 GREEN — 9.5 h, no crash, no reload |
| **Operational observability** | 🟡 **YELLOW** — no durable poll log |
| Repository state | 🟢 GREEN |
| Campaign C1 integrity | 🟢 GREEN |

**System health: 🟡 YELLOW** — every integrity control is green; two related availability/observability items are yellow.

---

# SCORECARD 2 — FORWARD RESEARCH RESULTS

| Metric | Value |
|---|---|
| Post-activation setups evaluated | **1** |
| Rejected setups | **1** (stale signal) |
| Qualifying setups | **0** |
| Trades requested | **0** |
| Trades opened | **0** |
| Trades closed | **0** |
| Wins / Losses | **0 / 0** |
| Realized R | **0.00** |
| P&L | **$0.00** |
| Drawdown | **0.00%** |
| Evidence packages | **0** |

**Sample size: 1 post-activation setup, 0 trades, across 9.3 hours and 12 instruments.**

**Meaningful inference is premature — emphatically so.** This sample cannot support any statement about ALEX's edge, in either direction. No strategy change is recommended, and none would be legitimate on this basis.

---

## Scientific notes for the record

- The 299 pre-activation exclusions are **correct behaviour and useful data**: they confirm the activation cutoff prevents historical backfill from contaminating the forward sample.
- The single stale rejection is **also data** — it records a real market opportunity that MOGO observed too late, and it is preserved as such rather than quietly retried.
- **No trades is data.** Nothing about a zero-trade night is anomalous for an H1 structure strategy over a partial session.

---

## FUTURE HYPOTHESIS CANDIDATES

*(Recorded only. Not acted on. Any of these would require HYPOTHESIS → PREREGISTRATION → REPLAY → VERIFICATION → ADJUDICATION before affecting any strategy version.)*

- **None arising from trading results** — there are no trading results to draw from.

---

## FUTURE BACKLOG — UX / NOTIFICATIONS (not for implementation)

**MOGO-012-BL-001 — Audible notification should signal execution, not observation.**

- **Current behaviour:** MOGO plays an audible notification when it reports that it is watching / scanning / monitoring a currency pair.
- **Desired behaviour:** **No** audible notification merely for beginning to watch, monitor, scan, or evaluate a pair. The sound should fire **only on a successfully executed/opened paper trade** — ideally on *confirmed successful paper execution*, not on a trade candidate or a trade request.
- **Status:** recorded, not implemented. Must not be applied to the running campaign mid-flight.

---

## AUTOMATION REVIEW — toward a MOGO FORWARD OPERATIONS REPORT

The goal is to stop requiring a hand-driven 20-question audit each morning.

**What can be automated today, with no application change:** essentially all of it. Every number in this report except the `pmset` sleep history came from a **single read-only expression evaluated in the running page**. The smallest reliable mechanism is:

> A read-only snapshot script that attaches to the already-open MOGO tab, evaluates one expression, and writes `MOGO_FORWARD_OPS_REPORT.md` plus a JSON sibling — run on a schedule (`launchd`/cron), or on demand.

It needs **no new architecture**: no server, no database, no in-app UI, no new evidence path. It reuses the observation port already in use and is strictly read-only.

**Automatable now:** campaign status · runtime · instruments healthy vs expected · setups evaluated (pre/post activation) · rejection reasons · qualifying setups · trades requested/opened/closed · open trades · wins/losses · realized R · drawdown · P&L · evidence package count · evidence reconciliation · write failures · checkpoint state · Campaign C1 integrity and attestation freshness · repository state.

**Not reliably automatable yet — and this is the one genuine gap:** *polling failures and API failures over time.* The Decision Event bus is memory-only and holds ~2.5 minutes, so no scheduled snapshot can report what happened overnight. Closing this needs a small, durable **poll heartbeat** (e.g. last-poll timestamp per pair persisted on each tick, with a bounded rolling gap log).

**Recommended sequencing:**
1. **Phase 1 (no code, no risk):** the read-only snapshot script above. Delivers ~90% of this report automatically.
2. **Phase 2 (small Lane A change, requires governance):** durable poll heartbeat, so gaps like today's are *measured* rather than inferred.

Neither was implemented today.

---

## Lane discipline

- **Lane A (forward production observation)** — the only lane touched today, and only by reading.
- **Lane B (research)** — untouched.
- **Lane C (experimental testing)** — untouched.

No strategy rule, filter, threshold, parameter, pair treatment, activation cutoff, account state, position, rejected setup, evidence record, Campaign C1 artifact, or legacy package was modified. No trade was manufactured. No live-money execution exists or was configured.

---

# MOGO-012 OVERALL STATUS: 🟡 YELLOW

*Campaign is operating and evidence is trustworthy, but a concrete availability issue deserves attention: the host slept and the tab is background-throttled, which already cost one forward observation. Now tracked as **MOGO-012-INC-001**, OPEN under controlled observation.*

## SINGLE BEST NEXT ACTION

> **Bring the MOGO tab to the foreground of a non-minimised window, then let the controlled observation period run undisturbed.**

Power and sleep prevention are already verified in place; the tab's `visibilityState` is the one controlled variable still reporting `hidden`, and it is the variable most relevant to the leading inferred cause. Setting it makes tonight's observation conclusive either way.

No code change, no restart, no campaign interruption. The next audit applies the MOGO-012-INC-001 decision rule: gaps recur → recommend the smallest durable heartbeat; gaps do not recur → continue collecting without engineering interruption.

---

## Document history

| Revision | When | Change |
|---|---|---|
| 1 | 2026-08-11 08:10 ET | Initial morning operational audit (read-only) |
| 2 | 2026-08-11 08:30 ET | Recorded **MOGO-012-INC-001 — Forward Observation Continuity Gap**, its classification, confirmed-fact vs. inference split, verified controlled-observation conditions, and the decision rule. No code, campaign, or evidence change. |

*Read-only audit. The only repository modification is this file.*

# MOGO-012 — Autonomous Operations Plan

**Type:** planning and repository analysis · **no code changed, nothing committed, forward campaign untouched**
**Prepared:** 2026-08-11 · **Campaign state at time of analysis:** ALEX forward paper trading ON, 0 trades, 0 evidence packages
**Related:** [`MOGO_012_MORNING_OPERATIONAL_AUDIT.md`](MOGO_012_MORNING_OPERATIONAL_AUDIT.md) · MOGO-012-INC-001

---

## Plain English first

**The most important finding is not about automation. It is that MOGO is currently throwing away the science.**

Overnight, ALEX evaluated 300 setups, rejected 299 as pre-activation, and rejected one — the AUD_JPY signal in MOGO-012-INC-001 — as stale. **All 300 of those observations exist only in the memory of the open browser tab.** I verified it: `alexGLiveSetupStatuses` has no persistence path anywhere in the codebase, the persisted ALEX decision log (`alexGAutoTrading.log`) is **empty**, and the Decision Event bus holds **2 minutes 36 seconds** of history in a 500-entry memory ring.

Close that tab and the entire forward-observation record of the campaign — including the incident we formally recorded this morning — is gone permanently and unrecoverably.

Evidence packages are durable and beautifully engineered, but they are only written **on trade close**. Since MOGO has made zero trades, **the durable forward record of this campaign is currently empty**, and everything MOGO has actually observed is ephemeral.

For a campaign whose stated product is *trustworthy forward observations*, that is the gap that matters. Rejections are data. Near-misses are data. Polls are data. None of it is being kept.

**Three consequences follow.**

1. **The automated morning report cannot be built properly yet.** About half the interesting metrics have no durable source. Automating a snapshot of a memory ring would produce a report that silently loses history.
2. **MOGO-012-INC-001 cannot be resolved by inference.** Nothing records when MOGO polled, so no analysis can establish whether polling actually stopped. The decision rule needs a measurement that does not exist.
3. **A durable observation ledger fixes all three problems at once** — the science, the incident, and the report — and it is small, additive, and can be attached at a seam this codebase has already used successfully twice.

On the research side: MOGO-009→011 built a genuinely impressive governed execution runtime — store, event log, worker, orchestrator, retry, lease, policy gate, authorizations, audit, verification. It currently has **zero effectful capabilities registered**; the only three are `echo`, `fail_then_succeed`, and `policy_probe`. Separately, 34 research scripts exist and work but are run by hand. **The substrate and the work exist and are not connected to each other.**

**Recommendation:** one milestone — a **Durable Forward Observation Ledger**. It protects the campaign that is already running, and everything else becomes straightforward once it exists.

---

# PART 1 — Forward Operations Report: what can already be sourced

**Classification key:** **A** = already durably available · **B** = available only from current runtime/memory · **C** = not currently observable

| Metric | Source of truth | Class |
|---|---|---|
| Campaign enabled/disabled | `localStorage.fxhub_alexg_auto` → `alexGAutoTrading.enabled` | **A** |
| Activation timestamp | `fxhub_alexg_auto.activatedAt` | **A** |
| Polling status | `alexGLiveInterval` (timer handle, `index.html:2196`, "session-only") | **B** |
| Last known evaluation | `alexGLastEvaluatedCloseTime` (`index.html:2171`, in-memory `{}`) | **B** |
| Instrument / data health | same in-memory cursor, per pair per timeframe | **B** |
| **Setups evaluated** | `alexGLiveSetupStatuses` — **memory-only, capped at 300**, no persistence path | **B** ⚠️ |
| **Rejection reasons** | same array (`status`, `reason`, `signalAgeMinutesAtEvaluation`) | **B** ⚠️ |
| Qualifying setups | same array | **B** ⚠️ |
| Trade requests | `decisionEventLog` — memory-only, **500-entry ring ≈ 2.5 min** | **B** ⚠️ |
| Trade opens | `alexGAutoTrading.log` (persisted, 200 cap) + `alexGAccount` | **A** |
| Trade closes | `alexGAutoTrading.log` + `alexGAccount.closedPositions` + journal | **A** |
| Current positions | `fxhub_alexg_account.openPositions` | **A** |
| Paper balance | `fxhub_alexg_account.balance` | **A** |
| Wins / losses | derived from `closedPositions` / `fxhub_alexg_journal` | **A** (derived) |
| Realized R | derived from `closedPositions` | **A** (derived) |
| P&L | derived from `balance` − `startingBalance` | **A** (derived) |
| Current drawdown | derived from account state | **A** (derived) |
| **Maximum campaign drawdown** | not recorded over time; only reconstructable if every close is retained | **C** |
| Evidence package count | IndexedDB `mogo_evidence` v1 → `packages` store | **A** |
| Evidence write status | `evidenceWriteFailures` — **memory-only array** | **B** |
| `sourceTradeId` reconciliation | computable on demand from the store via `evidenceReconcileByIdentity()` | **A** (derived) |
| Evidence integrity | `contentHash` per package + `evidenceVerifyPackageHash()` | **A** |
| Checkpoint state | filesystem — `~/MOGO-EVIDENCE-PRESERVED/*/CHECKPOINT-MANIFEST.txt`, `.last-rollup` | **A** |
| Campaign C1 integrity | `docs/campaigns/C1/` + `C1_INTEGRITY_ATTESTATION.json` (committed) | **A** |
| Repository state | git | **A** |

**Tally: 14 A · 8 B · 1 C.**

**The A-class metrics are the financial ones. The B-class metrics are the scientific ones.** Everything describing *what MOGO observed and decided* — setups, rejections, qualifications, requests — is ephemeral. Everything describing *what MOGO's paper account holds* is durable.

That asymmetry is exactly backwards for a research instrument, and it is invisible while the tab stays open.

**Verified, not assumed:**

```
alexGAutoTrading.log length ......... 0        (persisted, but nothing has reached it)
alexGLiveSetupStatuses length ....... 300      (memory-only)
fxhub_alexg_auto .................... 89 bytes
fxhub_alexg_setups .................. 2 bytes  ("{}" — zone state rebuilt each poll)
fxhub_alexg_zones ................... 2 bytes  ("{}")
localStorage total .................. 13,363 bytes
decisionEventLog window ............. 2 min 36 s (500/500 entries)
```

`alexGAutoTrading.log` is empty because it is only written at the *construction* stage (`index.html:4424`), which is reached only after the activation-cutoff and staleness gates pass. Every rejection at those gates — which is every observation this campaign has made — bypasses it entirely.

---

# PART 2 — Autonomous polling continuity

## Why the forward system depends on browser execution

Every part of the live loop lives inside the page: `alexGLivePollTick()` is driven by a `setInterval` handle (`alexGLiveInterval`, `index.html:4907`), market data is fetched by page `fetch()` using in-memory credentials, the zone/setup engine reconstructs state from 90 days of candles on each tick, and evidence is written to the page's IndexedDB. There is no process outside the browser that knows the campaign exists.

## The smallest mechanism that would prove polling completeness

A **bounded, durable poll heartbeat** — one small record appended per tick:

```
{ tickId, startedAt, finishedAt, outcome: OK|PARTIAL|ERROR,
  pairsAttempted, pairsSucceeded,
  perPairLastCandleClose: { GBP_USD: <ms>, ... },
  failures: [{ pair, kind, message }] }
```

Written to the **existing IndexedDB database** (a new small store alongside `packages`/`meta`), *not* localStorage — localStorage is explicitly a quota-bounded working buffer in this architecture, and IndexedDB is already durable, already in the durable profile, and already covered by checkpointing.

A bounded ring of ~20,000 ticks is roughly two weeks at 60 s and a few megabytes. From that single record, every Part 2 question is answered by **arithmetic on stored data rather than inference**:

| Question | Derivation |
|---|---|
| Last successful poll | `max(finishedAt where outcome=OK)` |
| Expected polling interval | declared constant (60,000 ms) vs. observed median delta |
| Successful polling count | count of `outcome=OK` |
| Longest polling gap | `max(startedAt[n] − finishedAt[n−1])` |
| Missed polling intervals | `floor(gap / interval) − 1` per gap |
| API/data failures tied to gaps | join `failures[]` against the gap windows |

This is the smallest thing that turns MOGO-012-INC-001 from an argument into a measurement.

## Can Chrome background throttling materially affect the current implementation?

### CONFIRMED FACT

- Chrome throttles timers in hidden tabs. Since Chrome 88, hidden pages are subject to **intensive throttling** after ~5 minutes, which limits timer wake-ups to **once per minute**.
- The MOGO tab was — and at the time of writing still is — `document.visibilityState: "hidden"`, `hasFocus: false`.
- The host was on battery overnight and slept: `Clamshell Sleep` 06:30:37 ET → `Wake … EC.LidOpen/UserActivity` 07:47:25 ET.
- The page never reloaded (`performance.timeOrigin` continuous, 9.5 h).
- The observed AUD_JPY gap was ~361 minutes; the confirmed sleep window is ~1 h 17 m.

### ENGINEERING INFERENCE

- **Documented throttling alone should NOT have caused this gap, and this deserves emphasis because it cuts against the easy explanation.** MOGO's polling interval is already 60 s, and intensive throttling permits one wake-up per minute. A throttled-but-running timer would have evaluated AUD_JPY within roughly a minute of the 06:00 UTC candle. Throttling is therefore a *plausible aggravator*, not a sufficient cause.
- Timers do not run at all while the system is asleep, so the confirmed sleep accounts for part of the gap — but not the 06:00→10:30 UTC portion, during which the host was awake.
- Something beyond documented throttling and confirmed sleep most likely suspended or starved the loop (candidates: App Nap on a fully occluded window, Chrome tab discarding/freezing under battery + memory pressure, or a stalled `fetch` holding the tick). **None of these is established.**

### UNKNOWN

- Whether the poll loop ran at all between 06:00 and 10:30 UTC.
- Whether any fetch failed, hung, or was aborted during that window.
- Whether Chrome froze or discarded the tab.
- **All three are unknowable from the current system**, because no durable polling telemetry exists. This is not a gap in the analysis; it is a gap in the instrument.

---

# PART 3 — Browser dependence

## What would eventually be required to run without a foreground tab

Three properties are needed: a process that survives sleep/wake and lid state; execution not subject to browser background throttling; and evidence writing that does not depend on a page being open.

## The smallest reliable evolution — in order, stopping as early as the evidence allows

**Stage 0 — measure (this is the recommended milestone).** Durable observation ledger + poll heartbeat. Until gaps are measured, any architectural change is speculative. It is entirely possible that power + no-sleep + a foreground tab is sufficient, in which case Stages 1–2 are never needed.

**Stage 1 — remove the human from continuity (small, no rewrite).** A `launchd` agent that keeps the durable-profile Chrome running, relaunches it if it exits, holds a power assertion, and opens MOGO in a foregrounded window. This is configuration, not architecture. It addresses lid/sleep/restart continuity without touching a line of strategy code.

**Stage 2 — only if Stage 0 proves in-browser execution is unreliable even when awake and foregrounded.** Move *market polling and evidence capture* into a persistent local process, leaving the browser as an interface.

## Should execution move to a background process? — analysis, not a recommendation

**The case for:** a Node/Python process is immune to tab throttling, discarding, and visibility; it can be supervised by `launchd`; and it can write evidence continuously regardless of UI state.

**The case against, which is currently stronger:** every rule ALEX applies lives in `index.html`, and 64 of those functions are protected against byte-level drift. Porting them creates a **second source of truth for strategy behaviour** — precisely the failure mode this codebase has repeatedly and deliberately refused (the evidence verifier does not reimplement canonicalization; it *extracts the shipped text*). A port would invalidate the frozen-strategy guarantee of the current campaign and would demand a fresh drift-equivalence regime.

**The middle path, if Stage 2 is ever justified:** keep `index.html` as the single source of strategy truth and run it in a **headless, supervised Chrome** owned by `launchd`, with the visible browser reduced to a viewer over the same durable profile. This gains process supervision and removes tab-visibility dependence **without porting a single strategy function**. It is by a wide margin the smallest change that achieves the goal, and it preserves zero-drift.

**A full rewrite is not technically necessary and is not recommended.**

---

# PART 4 — Research automation: what exists, and the one real gap

## What already exists

**A governed execution runtime (MOGO-009 → MOGO-011), 31 Python modules** under `platform/src/mogo_platform/`: typed contracts (`event`, `command`, `ids`, `errors`, `task_states`, `vocabulary`, `boundaries`), and a runtime with `store`, `event_log`, `worker`, `orchestrator`, `registry`, `retry`, `lease`, `policy`, `authorizations`, `audit`, `projection`, `schema`, `verify`, `clock`, `cli`. This is real, tested, governed infrastructure — retry with backoff, lease-based concurrency control, a policy gate, an append-only audit log, and verification.

**A research pipeline, 34 scripts** under `scripts/trader_intelligence/`, covering essentially the whole chain: `register_source`, `prioritize_sources`, `validate_acquisition`, `acquisition_common`, `ingest`, `transcript_adapters`, `transcript_normalize`, `extraction_pipeline`, `annotation_pipeline`, `evidence_registry`, `evidence_confidence`, `evidence_dedup`, `validate_evidence`, `build_graph`, `query_graph`, `knowledge_gaps`, `build_research_queue`, **`hypothesis_proposals`**, **`rule_candidate_proposals`**, `strategy_blueprint`, `review_queues`, plus dashboards and reports. Supporting corpora live under `docs/trader-intelligence/` (acquisition, evidence, graph, intake, proposals, queues, rule-registers, schema, traders).

## Pipeline status

| Stage | State |
|---|---|
| DISCOVER | ⚠️ partial — source registration and prioritisation exist; discovery is operator-initiated |
| ACQUIRE | ⚠️ partial — acquisition + validation scripts exist; constrained externally (captions server-blocked; catalogue/description retrieval works) |
| INGEST | ✅ scripts exist and are exercised |
| FORM HYPOTHESIS | ✅ `hypothesis_proposals.py`, `rule_candidate_proposals.py`, `knowledge_gaps.py` |
| PREREGISTER | ✅ precedent exists — PREREG-001, `PRE_ADJUDICATION_PROTOCOL.md` (manual, document-driven) |
| TEST | ✅ replay engine exists in-app; Campaign C1 ran 11 verified replay runs |
| VERIFY | ✅ strong — hashes, manifests, drift gates, `mogo_evidence_verify.js`, canonical gate |
| ADJUDICATE | ✅ precedent — `CAMPAIGN_C1_ADJUDICATION_REPORT.md`, MOGO-008 |
| LEARN | ❌ no closed loop back into source prioritisation |

## The single highest-value unfinished automation capability

> **Register the first *effectful* capability in the automation runtime — a governed acquire→ingest task — and give the runtime a scheduled trigger.**

**Why this one.** The runtime's own registry states the position plainly: *"an effectful capability may be registered, and none of them exists in this build."* The only registered capabilities are `echo`, `fail_then_succeed`, and `policy_probe` — all pure demos. Meanwhile the 34 research scripts do real work but are invoked by hand, with no retry, no lease, no policy gate, no audit trail.

**MOGO has built a governed engine with nothing connected to it, and a working pipeline with no governance around it.** Joining those two — once, for one real task — converts both from potential into an autonomous loop, and every subsequent research capability becomes incremental. Nothing else in Lane B or C unlocks as much for as little.

---

# PART 5 — Parallel operating model

## Lane A — Forward observation *(running now; frozen)*

Frozen ALEX → live market → paper execution → immutable evidence.
**Artifacts:** `index.html`, the durable profile, IndexedDB `mogo_evidence`, checkpoints.
**Change policy:** frozen. Only observability additions that provably cannot alter trading behaviour, and only with drift proof.

## Lane B — Autonomous research *(dormant; infrastructure ready)*

External discovery → acquisition → ingestion → hypothesis generation.
**Artifacts:** `scripts/trader_intelligence/**`, `docs/trader-intelligence/**`, `platform/**`.
**Change policy:** free. Touches no trading code and no forward evidence.

## Lane C — Experimental science *(precedent established; manual)*

Preregistration → replay/testing → verification → adjudication → candidate strategy version.
**Artifacts:** `docs/campaigns/**`, replay engine, `evidence/`, adjudication protocol.
**Change policy:** governed by preregistration. May *read* Lane A evidence; may never write it.

## How B and C proceed without contaminating A

The isolation is already structural, and it is worth being precise about why:

1. **Different files.** Lanes B and C live in `platform/**`, `scripts/**`, `docs/**`. Lane A's behaviour lives in `index.html`. No Lane B or C change touches it.
2. **The drift gate is the enforcement mechanism.** 64 protected functions and 4 protected constants are byte-compared on every canonical-gate run. Any Lane B/C change that reached ALEX's rules would fail the gate before it could be committed.
3. **Evidence is append-only and hash-covered.** Lane C reads Lane A's packages; it cannot alter one without breaking a `contentHash` that the verifier recomputes independently.
4. **The activation cutoff protects the sample boundary.** A new strategy version cannot retroactively enter the current forward sample — it would require its own activation and therefore its own campaign.
5. **Separate execution contexts.** Lane A runs in the durable browser profile. Lanes B and C run as CLI processes. The evidence-profile launcher pins one origin and refuses any other.

**The one discipline that is procedural rather than structural:** a forward observation may generate a *hypothesis*, but must never generate a *change*. Anything learned in Lane A enters the backlog as a FUTURE HYPOTHESIS CANDIDATE and must traverse Lane C in full before it can affect any strategy version. This is the rule most likely to be violated under enthusiasm after a run of losing trades, and it is the one worth restating in every audit.

---

# PART 6 — Prioritisation

Ranked against all six stated criteria. Only five items.

### 1. Durable Forward Observation Ledger ⭐

| Criterion | Assessment |
|---|---|
| Scientific value | **Highest.** Without it the campaign's observations are unrecoverable. Rejections and near-misses are data, and they are currently discarded. |
| Automation value | **Highest.** Converts 8 B-class metrics to A-class and makes an automated report meaningful rather than a memory snapshot. |
| Reliability value | High — subsumes the INC-001 poll heartbeat and makes the decision rule measurable. |
| Trading/research value | High — creates the rejection corpus needed to ask *why* setups fail. |
| Operator time saved | High — the audit becomes a query instead of an investigation. |
| Complexity / risk | **Low.** Additive, attaches at the non-protected `alexGLivePollTick` / `alexGEvaluatePairForLiveSetups` seam — the same seam the Decision Event bus already used in v12.5.0/12.6.0 with zero drift. Writes to the existing IndexedDB. `alexGRecordLiveSetupStatus` is **protected** and must not be touched. |

### 2. MOGO Forward Operations Report (automated)

Scientific ✱ low · automation **high** · reliability moderate · operator time **highest** · complexity **very low** (a read-only snapshot script; no app change). Depends on #1 for its most valuable content.

### 3. First effectful capability + scheduler in the automation runtime

Scientific moderate · automation **highest for Lane B** · reliability moderate · research value **high** · complexity moderate (governance-bearing: registering effectful work needs the policy gate and authorization path exercised for real).

### 4. Supervised campaign continuity (`launchd` + power assertion + relaunch)

Scientific low-moderate · automation moderate · reliability **high** · operator time high · complexity **very low** (configuration, not architecture). Sequence *after* #1 so its effect is measurable.

### 5. MOGO-012-BL-001 — notification on confirmed paper execution only

Scientific none · automation none · reliability none · operator experience **high** (a scanning chime trains the operator to ignore alerts, which devalues the one alert that matters) · complexity **very low**. Deliberately ranked last: it is a real irritant, not a campaign risk, and it touches Lane A.

---

# THE SINGLE BEST NEXT ENGINEERING MILESTONE

> ## MOGO-013 — Durable Forward Observation Ledger
>
> Make MOGO's forward observations survive the tab.

**What it is.** A bounded, append-only ledger in the existing IndexedDB database capturing, per poll tick: the tick itself (start, finish, outcome, per-pair candle cursor, failures) and every setup evaluation with its decision and reason. Attached at the **non-protected** `alexGLivePollTick` / `alexGEvaluatePairForLiveSetups` seam, exactly as the Decision Event bus was, with `alexGRecordLiveSetupStatus`, `alexGIsSetupSignalStale` and `alexGRunSetupEngine` left byte-identical.

**Why this and not something else.**

- It is the only item on the list where **delay causes permanent loss**. Every hour the campaign runs without it, observations are created and destroyed. The other four lose nothing by waiting.
- It **resolves MOGO-012-INC-001** by replacing inference with measurement — the incident's own decision rule currently has no instrument to read.
- It **unblocks the automated operations report** (#2), which is largely uninteresting while half its metrics live in a 2.5-minute memory ring.
- It **makes the Lane A freeze meaningful**: a frozen strategy whose observations evaporate cannot be studied, and studying it is the entire point of freezing it.
- It is **small and precedented** — the same additive seam, the same fire-and-forget isolation, the same drift-proof discipline this codebase has already applied twice successfully.

**Explicitly in scope:** durable tick + evaluation records; bounded retention; read-only query surface; fixtures; mutation protocol; zero protected-function drift.

**Explicitly out of scope:** any change to ALEX rules, thresholds, filters, pair treatment, or the activation cutoff; any change to evidence-package schema or the forward-paper gate; MOGO-012-BL-001; the automation-runtime capability work; any move of execution out of the browser.

**Governance note.** This is a Lane A change and therefore requires explicit authorization even though it is observability-only. It should carry the full discipline the milestone series has used throughout: drift proof, canonical gate, mutation protocol, and a decision on whether the campaign continues uninterrupted during the change or is deliberately restarted with the ledger in place — noting that a restart **erases the current 300-observation memory record**, so if any of it is to be kept, it must be exported read-only *before* the change lands.

---

## Backlog — preserved, not implemented

**MOGO-012-BL-001 — Audible notification on confirmed paper execution only.**
The audible notification must fire **only after a confirmed successful paper trade execution/opening**. Watching, scanning, monitoring, or evaluating a pair must **not** trigger it. Preferably tied to confirmed execution rather than a trade candidate or trade request. *Not implemented. Not to be applied to the running campaign mid-flight.*

**MOGO-012-INC-001 — Forward Observation Continuity Gap.** OPEN, under controlled observation; decision rule recorded in the morning audit. Remediation deliberately deferred — and note that MOGO-013 is the mechanism that would let the rule be evaluated on evidence rather than argument.

---

## What this analysis did not do

No code was changed. Nothing was committed. The forward campaign was not modified, restarted, or reloaded; the paper account, Campaign C1, and the legacy corpus were untouched. Every claim about persistence above was verified by reading the repository and by read-only inspection of the running page, not inferred from documentation.

---

*Analysis only. Awaiting operator authorization.*

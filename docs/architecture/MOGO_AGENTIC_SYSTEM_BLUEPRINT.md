# MOGO Agentic Trading Intelligence — System Blueprint

**Status:** 🟡 **PROPOSED — Phase 0 architecture only. Nothing implemented. Awaiting approval.**
**Prepared:** 2026-08-04 · **Engine at writing:** `APP_VERSION` 12.18.0 · **Repository HEAD at last successful read:** `bb8498f`
**Code changed:** none · **Strategy logic changed:** none · **Campaign C1:** not begun · **Automatic execution:** not enabled

---

> # ⛔ READ THIS FIRST — EVIDENCE LIMITATION OF THIS DOCUMENT
>
> **This blueprint was written while the repository was UNREADABLE.**
>
> A macOS TCC (Privacy & Security) revocation removed this session's read access to the Desktop —
> and therefore to the entire repository — partway through the session. At the time of writing:
>
> ```
> ~/Desktop/Forex Hub/index.html      Operation not permitted
> git log                             fatal: Unable to read current working directory
> ```
>
> Files *created* by this process remain accessible, which is the only reason this document could be
> written to its intended path. **No new file could be opened to gather evidence for it.**
>
> **Consequence, stated plainly:** every repository citation in §1 comes from reads performed
> **earlier in this same session, while access still worked**. Those reads were real, and each is
> cited with a path and line number. But **§1 is a partial survey, not a repository audit.** Whole
> areas were never opened, and the honest label for those is `UNKNOWN` — used liberally and
> deliberately below.
>
> **The `UNKNOWN` entries in §1.6 are not gaps in the platform. They are gaps in *this document*.**
> Several almost certainly exist in the repository and simply could not be re-opened to confirm.
> **Do not read an `UNKNOWN` as "missing."** Resolving them is the first task of Phase 0 and the
> single highest-value correction to make to this blueprint.
>
> **§§2–10 are recommendations and contain no repository claims.** They are design proposals to be
> argued with, not findings.

---

## 0. Scope and standing constraints

This blueprint proposes governance and architecture for evolving MOGO into a multi-agent
trading-intelligence system. It **consumes** the existing platform's guarantees; it does not relax
them.

**Inherited constraints, treated as inviolable throughout:**

| Constraint | Source (verified this session) |
|---|---|
| Protected trading logic is byte-identical — 63 functions, 4 constants | `tests/run_all.sh` drift check output |
| Browser testing never touches the operator's Chrome profile | `docs/TESTING.md` → Rule 0 |
| A pre-registration is never edited; only succeeded | `PREREG-001…md` §10 |
| Replay evidence can never exceed `REPLAY_EVIDENCE_ONLY` | `PREREG-001…md` §5 |
| Live-paper and replay evidence classes are never merged | `MOGO-003-VERIFIED-REPLAY-RECORD.md` §0 |
| A browser download is an attempt, not a durability proof | `index.html:1986` (v12.8.2 log) |
| `contentHash` is integrity only — never authenticity | `index.html:12125` `EVIDENCE_HASH_SCOPE` |

**Non-negotiable for every agent proposed here:** no agent may modify strategy logic, approve a
strategy for live execution, adjudicate a pre-registered hypothesis, or delete evidence. Those are
human authorities and remain so at every phase.

---

# 1. CURRENT PLATFORM CAPABILITIES

Classification is by **what this session actually verified**, not by what the repository is believed
to contain.

Legend — **IMPL** implemented and directly verified · **PARTIAL** implemented with a stated,
verified limitation · **DOC** documented but verified as *not* implemented · **PROP** proposed only ·
**UNKNOWN** could not be verified this session.

## 1.1 Implemented — directly verified

| Capability | Evidence (verified this session) | Status |
|---|---|---|
| Deterministic replay run identity | `index.html:13560` `alexGBuildReplayRunIdentity()`; `:13583` `runId` = SHA-256 over `strategyId + pair + fromUTC + toUTC + datasetHash + configHash + paramsHash` | **IMPL** |
| Full-dataset fingerprinting | `index.html:13541` `evidenceReplayDatasetHash()` — hashes **every** OHLC in W/D/H4/H1, not a count/first/last fingerprint | **IMPL** |
| Canonicalization spec `mogo.evidence-canon.v1` | `index.html:12159+` `evidenceCanonValue`/`evidenceCanonicalize`, rules K1–K8; key sort, array-order significance, null coercion, non-finite rejection, no whitespace | **IMPL** |
| Content hashing, integrity-scoped | `index.html:12118–12140` `EVIDENCE_*` constants; `EVIDENCE_HASH_SCOPE='INTEGRITY_ONLY_NOT_AUTHENTICITY'` | **IMPL** |
| Hash excludes self and export block | `index.html:12132` `EVIDENCE_HASH_EXCLUDED_FIELDS` (6 fields) | **IMPL** |
| Evidence package schema + validator | `index.html:13301–13363` `evidenceValidatePackage()`; rejects contradictory attribution and timing emitted without `AGREES` | **IMPL** |
| Rule attribution (Unit B) | producer `index.html:12694`; into package `:13184`; fail-closed on proven contradiction (`EVIDENCE_RULE_ATTRIBUTION_MISMATCH`) | **IMPL** |
| Excursion timing (Unit C1) | `index.html:12757–12819` `evidenceRecomputeExcursionTiming()`; into outcomes `:13251` | **IMPL** |
| Market context + HTF context (C2-M1/M2) | `index.html:13718` `evidenceBuildMarketContext()`, `evidenceBuildHigherTimeframeContext()`; into package `:13729` | **IMPL** |
| Replay capture seam, non-protected | `index.html:4131` in `runAlexGReplayUI` (`:4097`), fire-and-forget in its own try/catch, after results assigned | **IMPL** |
| Import verification | `index.html:14018+` `evidenceImportPackageObject()` — rejects hash mismatch, unsupported/newer schema, duplicate-with-different-hash; never repairs or re-hashes | **IMPL** |
| Mandatory profile isolation, fail-closed | `scripts/browser_test_profile.sh` GUARDS 1, 1b, 2, 3, 4, 5 — explicit origin, denylist, temp-only root, fresh+empty profile, isolation manifest | **IMPL** |
| Offline regression + protected-drift gate | `tests/run_all.sh` — **executed this session: 17 suites, 944 fixtures, 944 passed, 0 failed, zero drift** | **IMPL** |
| Named suites | `v128_evidence_platform` (224), `v_paper_trading_audit` (115), `v127_alex_v11_release` (88), `v129_browser_isolation_guard` (27), `v130_candle_completeness_regression` (14) | **IMPL** |
| Pre-registration governance | `PREREG-001-alex-multipair-2026-08-04.md` — declared family of 12, thresholds, Holm–Bonferroni, stopping rule, ceiling; content hash recorded in its own commit message and **verified unmodified** this session | **IMPL** |
| Hypothesis registry with executable tests | `hypothesis-registry.json` — 41 hypotheses; 12 `COLLECTING`, 19 `UNSUPPORTED`, 10 `UNRESOLVED`; each carries metric, arms, `minimumOperationalSample: 30`, promotion/rejection thresholds, `promotionCeiling`, `evidenceRunIds`, `joinStatus` | **IMPL** |
| Verified replay register | `docs/MOGO-003-VERIFIED-REPLAY-RECORD.md` — RUN-001 with full identity, hashes, results, evidence-class separation rules | **IMPL** |
| Money-space honesty | `index.html:1983` (v12.9.0 log) — `pnl` recorded `UNAVAILABLE` rather than derived by subtraction; money-space flagged `DERIVED`/`LIVE_DATA_DEPENDENCY` | **IMPL** |

**Independently reproduced this session** (strongest evidence class in this document): a clean-room
port of `mogo.evidence-canon.v1` reproduced **24/24** RUN-001 `contentHash` values, and recomputed
`configHash`, `paramsHash` and `runId` to exact matches. **The identity chain is real and verifiable
by a third party.**

## 1.2 Partially implemented — verified limitation

| Capability | Limitation | Evidence |
|---|---|---|
| Export durability | A browser download is an **attempt**; a package is marked exported only after re-import byte-verification | `index.html:1986` (v12.8.2). **Reproduced live this session** — two downloads silently failed, no file on disk |
| Dataset reproducibility | `datasetHash` fingerprints the dataset but candles are **not retained** → cannot be independently recomputed | Verified: all other hashes recomputed; this one could not |
| Window control | `fetchCandlesRange` paginates **backward by candle count**; no `from`/`to`. "90 days" is a control label | `index.html:5937`; `PREREG-001` §6 gate item **B2**, open |
| Rule-level attribution coverage | Present from engine 12.11.0 onward; **absent from RUN-001** (12.9.0) and never backfilled | `MOGO-003-VERIFIED-REPLAY-RECORD.md` "RUN-001's ceiling is fixed" |
| Censoring capture | `alexGReplayRejected` populated in memory (`index.html:4119`) but **not automatically persisted**. RUN-001 has aggregates only; the Step 1 pilot lost it entirely | `PREREG-001` §9 requires it in full. **Gap has now recurred in two consecutive runs** |
| Offline test coverage of crypto/IndexedDB | JXA harness has neither `crypto.subtle` nor `indexedDB`; SHA-256 and IndexedDB are browser-verified only | `docs/TESTING.md` §"Disclosed harness limitation" |
| Protected-drift baseline currency | Drift check passes, but baseline app version is **12.5.0** vs current **12.18.0** | `tests/run_all.sh` output, this session |

## 1.3 Documented but NOT implemented — verified absent

| Item | Evidence |
|---|---|
| Durable decision chains | Every RUN-001 package declares `objects.decisions [FUTURE_WORK]`; `decisionChainRef` null | `index.html:1979` (v12.13.0 log) |
| Content-addressed candle store | Named "explicitly not implemented" | `index.html:1979`; `MOGO-004-PLAN.md` §7 |
| Untraded-candidate context | Named out of scope | `MOGO-004-PLAN.md` §7 |
| `identity.commitHash` | `UNAVAILABLE` in all 24 RUN-001 packages — no build-time commit injection | verified across all 24 packages |
| Browser verification of Units A/B/C1/C2 | *"Nothing since v12.9.0 has been exercised in a browser"* | `MOGO-004-ARCHITECTURE-REVIEW.md:112` (T1, Critical) |
| 10-item evidence-platform browser checklist | Enumerated; recorded as **unrun** | `docs/TESTING.md`; `MOGO-004-ARCHITECTURE-REVIEW.md:112` |
| File System Access API | Deliberately excluded; reserved enum never emitted | `index.html:1988` (v12.8.0 log) |

## 1.4 Proposed only

| Item | Status |
|---|---|
| `MOGO-RESEARCH-VALIDATION-STANDARD-V1.md` | **Proposed, not approved** — `PREREG-001` §11 states it "remains proposed" |
| Campaign C1 (11 majors) | Designed in `PREREG-001` §6; **blocked** behind the pilot gate |
| MOGO Recovery & Evidence Agent | Proposed 2026-08-04 in `~/MOGO-PILOT-RECOVERY-HANDOFF.md` §6; nothing implemented |
| Everything in §§2–9 of this document | Proposal |

## 1.5 Current live state — carried forward

| Fact | Status |
|---|---|
| RUN-001 | ✅ Verified, authoritative — 24 packages, all hashes independently reproduced |
| Step 1 pilot replay | ✅ **Executed 2026-08-04** — 33 setups considered, 25 trades, 8 rejected (operator-reported) |
| Pilot evidence | ⚠️ **In browser IndexedDB only** — 2.1 MB; backed up to `~/MOGO-PILOT-BACKUP/` |
| Pilot packages verified | ❌ **None** — never extracted |
| **PRE-REG-001 pilot gate** | ⬜ **NOT EVALUATED** |
| Pilot `alexGReplayRejected` | ❌ Lost from memory |
| Engine provenance for pilot | ✅ Hash-verified `49c1f005…` = committed HEAD = `APP_VERSION` 12.18.0 |

Full detail: `~/MOGO-PILOT-RECOVERY-HANDOFF.md` (relocate into `docs/reports/` when access permits).

## 1.6 UNKNOWN — could not be verified this session ⚠️

**These are limitations of this document, not findings about the platform.** Each was referenced by a
document I did read, but could not itself be opened. **Resolving this list is Phase 0's first task.**

| Item | Why it is UNKNOWN |
|---|---|
| **Engineering Constitution** | **Named in the tasking. I have never opened it. I cannot confirm its path, contents, or existence.** Treated as UNKNOWN on principle |
| ADR governance corpus | `docs/adr/ADR-011` referenced by `TESTING.md` and `index.html`; never opened. Full ADR set unenumerated |
| `docs/INCIDENTS.md` | INC-001/004/005 cited extensively via other documents; the file itself never opened |
| `docs/KNOWN_ISSUES.md` | Referenced; not opened |
| `docs/PAPER_TRADING_AUDIT.md` | Referenced (§0.1 rollback contract); not opened |
| `STATISTICAL-GOVERNANCE.md`, `RESEARCH-ROADMAP.md`, `REPLAY-CAMPAIGN-PLAN.md`, `evidence-gap-matrix.json` | Path-confirmed by grep; contents never read |
| `MOGO-003-EVIDENCE-SCHEMA-CORRECTIONS.md` | Referenced; not opened |
| `scripts/strategy_fidelity/build_research_governance.py` | Path-confirmed; not read |
| `regression-baseline-tools.py` / `regression-baseline.json` | Referenced; not read |
| Knowledge-ingestion subsystem | Named in the tasking; **no component verified**. `MOGO-RESEARCH-ACQUISITION-ARCHITECTURE.md` exists untracked but was never opened |
| TJR session engine / second-educator assets | Referenced in `MOGO-004-PLAN.md` M5; not inspected |
| Full test-suite inventory | 17 suites ran; only 6 names captured from output |
| Complete repository tree | **Never enumerated.** No `find`/`ls -R` was ever run |
| Strategy-versioning mechanism beyond ALEX | `ALEX_V11_RULE_VERSION`, `strategySpecificationVersion` seen in logs; registry not inspected |
| Broker configuration surface | Only `cfg={key,accountId,env}` (`index.html:2077`) and `apiBase()` seen |

---

# 2. TARGET AGENT ARCHITECTURE *(recommendation)*

**Design axiom:** agents **observe, propose and verify**. They do not decide what evidence means, and
they do not act on markets. Every path to a market or to strategy logic terminates at a human.

**Separation of duties is structural, not advisory.** Three separations are load-bearing:

1. **The agent that produces evidence never audits it.** Replay & Validation produces; the
   Independent Evidence Auditor verifies. Neither may perform the other's role.
2. **The agent that designs an experiment never adjudicates it.** Experiment Design writes the
   pre-registration; adjudication is human, once, after declared runs complete.
3. **The agent that finds a fault never repairs it unsupervised.** Operations & Recovery proposes;
   a human authorizes.

| Agent | Responsibility | Hard boundary |
|---|---|---|
| **MOGO System Auditor** | Read-only health across repository, evidence, identity chains, environment. Emits findings + severity | Never repairs. Never writes outside its own report directory |
| **Research Acquisition Agent** | Fetch external educator material into immutable source records with provenance | Never interprets content into rules. Never writes to the rule register |
| **Source Evaluation Agent** | Score source credibility, authority, recency, independence; detect duplication | Never rewrites a source. Its score is an input to humans, never an auto-gate |
| **Rule Intelligence Agent** | Extract candidate rules from source records into structured, testable form | Never marks a rule implemented, validated, or fidelity-confirmed |
| **Strategy Reconciliation Agent** | Join claimed rules to code locations; maintain the fidelity matrix; flag divergence | **Never modifies strategy code.** Reports divergence only |
| **Experiment Design Agent** | Draft pre-registrations: metric, arms, thresholds, sample, falsification, multiplicity | Never declares one. **Declaration is a human act creating immutable evidence** |
| **Replay & Validation Agent** | Orchestrate authorized replays; capture packages + full rejection record + identity | One run per explicit authorization. Never self-authorizes. Never adjudicates |
| **Trade Forensics Agent** | Post-hoc analysis of outcomes: excursion timing, context, loss anatomy | Never proposes a rule change. Never touches live positions |
| **Knowledge Governance Agent** | Maintain hypothesis registry, evidence-gap matrix, promotion ceilings, status transitions | Never promotes above `REPLAY_EVIDENCE_ONLY`. Never edits a pre-registration |
| **Operations & Recovery Agent** | Detect volatile-state risk; extract evidence to durable storage with verified writes | **Never deletes.** Recovery beyond extraction requires approval |
| **Independent Evidence Auditor** | Adversarial re-verification from raw bytes using an independent implementation | **Structurally forbidden from producing evidence.** Must not share code with the capture path |
| **Human Approval Authority** | Sole authority for: authorization, declaration, adjudication, promotion, code changes, execution | Not an agent. The terminal node of every privileged path |

### 2.1 The Independent Evidence Auditor deserves emphasis

Its value comes **entirely from not sharing an implementation** with the capture path. If it imports
`evidenceCanonicalize` from `index.html`, a canonicalization defect verifies itself as correct and the
audit is worthless.

This is not theoretical — it is the method that produced the strongest result in this session: a
clean-room canonicalizer reproduced 24/24 RUN-001 hashes and the full identity chain. **Independence
is the feature. Any implementation-sharing shortcut destroys it.**

---

# 3. AUTHORITY MATRIX *(recommendation)*

**A** = ALLOWED · **H** = ALLOWED WITH HUMAN APPROVAL · **P** = PROHIBITED

| Agent | Read repo | Read mkt data | Read evidence | External sources | Write research | Write evidence | Modify docs | Modify app code | Modify strategy | Run tests | Run replay | Paper trading | Broker config | Delete evidence | Live execution |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| System Auditor | **A** | P | **A** | P | P | P | P | P | P | **A** | P | P | P | **P** | **P** |
| Research Acquisition | **A** | P | P | **H** | **A** | P | P | P | P | P | P | P | P | **P** | **P** |
| Source Evaluation | **A** | P | P | P | **A** | P | P | P | P | P | P | P | P | **P** | **P** |
| Rule Intelligence | **A** | P | **A** | P | **A** | P | P | P | **P** | P | P | P | P | **P** | **P** |
| Strategy Reconciliation | **A** | P | **A** | P | **A** | P | **H** | **P** | **P** | **A** | P | P | P | **P** | **P** |
| Experiment Design | **A** | P | **A** | P | **A** | P | **H** | P | **P** | P | P | P | P | **P** | **P** |
| Replay & Validation | **A** | **A** | **A** | P | **A** | **A** | P | P | **P** | **A** | **H** | **P** | P | **P** | **P** |
| Trade Forensics | **A** | **A** | **A** | P | **A** | P | P | P | **P** | P | P | P | P | **P** | **P** |
| Knowledge Governance | **A** | P | **A** | P | **A** | P | **H** | P | **P** | P | P | P | P | **P** | **P** |
| Operations & Recovery | **A** | P | **A** | P | **A** | **H** | **H** | **H** | **P** | **A** | P | P | **H** | **P** | **P** |
| Independent Evidence Auditor | **A** | P | **A** | P | **A** | **P** | P | P | **P** | **A** | P | P | P | **P** | **P** |
| Human Approval Authority | **A** | **A** | **A** | **A** | **A** | **A** | **A** | **A** | **A** | **A** | **A** | **A** | **A** | **A** | **A** |

### 3.1 Invariants that hold across every row

1. **`Modify strategy logic` is PROHIBITED for all twelve agents.** No approval path exists. Changing
   it is a human act, subject to the protected-function drift gate.
2. **`Delete evidence` is PROHIBITED for all twelve agents — including Operations & Recovery.**
   Recovery extracts and copies; it never removes. Deletion is human-only, out-of-band.
3. **`Initiate live execution` is PROHIBITED for all twelve agents.** No agent may reach a live
   broker path under any circumstance, at any severity, with any approval.
4. **`Initiate paper trading` is PROHIBITED for all agents**, including Replay & Validation. Paper
   execution mutates a real ledger; replay does not. Conflating them is how INC-001 happened.
5. **`Write evidence artifacts` is PROHIBITED for the Independent Evidence Auditor** — by design. An
   auditor that can write evidence can launder its own findings.
6. **`Run replay` is ALLOWED WITH HUMAN APPROVAL, per run.** Not per session, not per campaign.
   Authorization is consumed by exactly one run, matching `PREREG-001` §11.
7. **`Access external sources` requires approval** — an outbound fetch is an outward-facing action
   whose target may be logged.

### 3.2 Deliberate asymmetries

- **Strategy Reconciliation may run tests but not modify code.** It proves divergence between claim
  and implementation; correcting it is human work.
- **Operations & Recovery may modify app code with approval** (recovery tooling), but **never strategy
  logic** — the one boundary its emergency posture must not soften.
- **System Auditor cannot read market data.** It audits the system, not the market. Denying it
  removes any incentive to interpret price.

---

# 4. EVIDENCE AND PROVENANCE MODEL *(recommendation)*

**Principle, inherited:** *an operator saying it happened is not evidence; the bytes are.* Extend
the existing package discipline to agent actions.

Every agent action emits an **Action Record**, hashed with a canonicalization following the same
K1–K8 rules as `mogo.evidence-canon.v1` (`index.html:12159+`), with self-referential and mutable
fields excluded from the hash — mirroring `EVIDENCE_HASH_EXCLUDED_FIELDS`.

| Required field | Content | Precedent |
|---|---|---|
| `sourceIdentity` | Origin: URL + fetch method, file path + hash, or run id | new |
| `timestamps` | `startedAtUTC`, `completedAtUTC`, ISO-8601 UTC | `createdAt` in packages |
| `contentHash` | SHA-256 over canonical form; `INTEGRITY_ONLY_NOT_AUTHENTICITY` | `index.html:12125` |
| `inputConfiguration` | Complete parameter set, verbatim | `configSnapshot` |
| `engineVersion` | `APP_VERSION` at execution | `identity.engineVersion` |
| `repositoryCommit` | Git commit; **`UNAVAILABLE` if absent — never guessed** | `identity.commitHash` (currently `UNAVAILABLE`) |
| `agentVersion` | Agent id + semantic version + own source hash | new |
| `instructions` | Prompt/instruction hash; full text where policy permits | new |
| `outputs` | Artifacts produced, each with its own hash | new |
| `validationResults` | Checks run, each with pass/fail and method | `excursionAgreement` |
| `approvalHistory` | Who approved, what, when, scope, and **what was consumed** | `PREREG-001` §11 |
| `failureState` | Explicit; **absence of failure must be asserted, not implied** | `evidenceRecordWriteFailure` |
| `provenance` | Per-field token: `OBSERVED`, `DERIVED_FROM_OBSERVED_FIELDS`, `UNAVAILABLE`, `FUTURE_WORK` | existing vocabulary |

### 4.1 Five rules, each earned by a real incident

1. **Never fabricate a value to fill a field.** `UNAVAILABLE` is a valid answer.
   *Precedent: `pnl` is not reconstructed by subtraction — arithmetic on two stored values is a
   derivation, not an observation (`index.html:1983`).*
2. **A write is not complete until its bytes are read back and re-hashed.**
   *Precedent: EXP-001, reproduced live this session — two downloads reported success, wrote nothing.*
3. **Volatile state is extracted before it is analysed.**
   *Precedent: the pilot's `alexGReplayRejected` was lost to a page unload; the run is unrepeatable.*
4. **Censoring is recorded or the result is void.**
   *Precedent: `PREREG-001` §9 — a censored figure reported without its censoring is not a result.
   Now missing in two consecutive runs.*
5. **Every claim distinguishes observation from derivation.**
   *Precedent: `realizedRProvenance: DERIVED_AT_READ_TIME` on all 24 RUN-001 outcomes.*

### 4.2 Chain of custody

```
external source ──► source record (hashed, immutable)
                          │
                          ▼
                    extracted rule ──► fidelity join ──► code location
                          │
                          ▼
                  pre-registration (immutable, git-anchored, human-declared)
                          │
                          ▼
      authorized run ──► evidence packages ──► independent re-verification
                          │                              │
                          └──────────► adjudication ◄─────┘  (human, once)
```

Every arrow carries an Action Record. **Any break makes downstream claims unciteable** — matching the
existing rule that a run enters the register only if its `runId` recomputes from its own stored inputs
(`MOGO-003-VERIFIED-REPLAY-RECORD.md` header).

---

# 5. SELF-AUDIT MODEL *(recommendation)*

Fourteen domains. Each states **what is checked**, **how**, and **what proves it** — a check whose
failure mode is silence is not a check.

| # | Domain | Method | Default severity on failure |
|---|---|---|---|
| 1 | **Repository integrity** | Protected-function/constant drift; working-tree cleanliness; HEAD recorded; **baseline currency vs `APP_VERSION`** | BLOCKING on drift; WARNING on stale baseline |
| 2 | **Application services** | Served bytes hash-match committed `index.html`; `APP_VERSION` matches expectation | **BLOCKING** |
| 3 | **Database health** | IndexedDB reachable; package count vs expected; unique-index integrity on `sourceTradeId` | DEGRADED |
| 4 | **Market-data integrity** | ADR-011 `completenessState` per timeframe; termination reason; `datasetHash` stability | DEGRADED |
| 5 | **Broker connectivity** | Reachability and auth **status only — never credential content** | WARNING |
| 6 | **Practice vs Live** | Assert `cfg.env === 'practice'`; assert `apiBase()` resolves to the practice host | **CRITICAL if Live unexpectedly** |
| 7 | **Strategy-version consistency** | `strategyId`/`strategyVersion`/`releaseVersion` agree across packages; absent versions unstamped, never inferred | BLOCKING on conflict |
| 8 | **Replay determinism** | Recompute `runId` from stored inputs; recompute `configHash`/`paramsHash` | **BLOCKING** |
| 9 | **Evidence completeness** | `completenessReport` honest; declared gaps match observed nulls; **rejection record present and complete** | BLOCKING if censoring absent |
| 10 | **Identity-chain validity** | Recompute every `contentHash` with the **independent** canonicalizer | **BLOCKING** |
| 11 | **Analytics reconciliation** | Recompute stats from packages; compare to published figures | BLOCKING on divergence |
| 12 | **Permissions and storage** | **Real write-read-delete probe** on every target path; quota headroom; unexported count | **BLOCKING** |
| 13 | **Scheduled acquisition jobs** | Last run, outcome, artifacts, **overdue detection** | WARNING |
| 14 | **Agent authorization compliance** | Every Action Record's agent/action pair checked against §3; **any PROHIBITED attempt is CRITICAL** | **CRITICAL** |

### 5.1 Three checks this session proves are mandatory

- **#2 (served bytes)** — a stale server 404'd for hours while appearing healthy. Had it served *old*
  bytes, a pilot would have been recorded under the wrong engine. Only a hash comparison catches this.
- **#12 (write probe)** — a TCC revocation was invisible until an unrelated command failed, and it
  silently destroyed two intended artifacts. **A `stat()` is not a write probe; only a real
  write-read-delete cycle is.**
- **#9 (censoring)** — now missing in two consecutive runs. It must be a **blocking** check, not a
  warning, or it will keep recurring.

---

# 6. FAILURE SEVERITY MODEL *(recommendation)*

| Level | Meaning | Permitted | **Blocked** |
|---|---|---|---|
| **INFO** | Observation, no action | everything | nothing |
| **WARNING** | Anomaly not affecting current validity | everything; must appear in every report until cleared | nothing |
| **DEGRADED** | A capability is impaired; existing evidence stays valid | read-only analysis, audit, forensics on **existing** evidence | **new evidence capture**; adjudication |
| **BLOCKING** | Trustworthiness of new or existing evidence is in doubt | audit, diagnosis, recovery **extraction**, reporting | all capture, replay, promotion, adjudication, **campaign progression** |
| **CRITICAL** | Safety/isolation boundary breached or at risk | **audit and reporting only** | everything else, including recovery writes, until a human clears it |

### 6.1 Fixed severity assignments

| Condition | Level | Why |
|---|---|---|
| Live environment detected when Practice expected | **CRITICAL** | Real-money boundary |
| Agent attempts a PROHIBITED action | **CRITICAL** | Authority model breached |
| Operator profile touched / isolation unverified | **CRITICAL** | INC-004 |
| Protected-function drift | **BLOCKING** | Trading logic changed |
| `contentHash` or `runId` mismatch | **BLOCKING** | Identity chain broken |
| Served bytes ≠ committed bytes | **BLOCKING** | Wrong engine |
| Write target not verifiably writable | **BLOCKING** | Silent evidence loss |
| Rejection record missing/incomplete | **BLOCKING** | `PREREG-001` §9 |
| Evidence in volatile storage only | **BLOCKING** | Current pilot state |
| Sample below `minimumOperationalSample` | **INFO** | `INSUFFICIENT` is a valid result, not a fault |

### 6.2 Two rules that keep the model honest

1. **Severity is never lowered to unblock work.** It is lowered only when the underlying condition is
   fixed and re-verified. *An `INSUFFICIENT` result is INFO precisely so no one is tempted to
   downgrade a real BLOCKING to keep a campaign moving.*
2. **A BLOCKING condition never auto-clears.** It requires a passing re-check plus a recorded human
   acknowledgement.

---

# 7. AGENT COMMUNICATION MODEL *(recommendation)*

Agents exchange **typed, hashed, validated artifacts** — never free prose alone. Prose may accompany a
record; it is never the record.

**Common envelope on every message:**

```json
{
  "schemaVersion": "mogo.agent-msg.v1",
  "messageId": "MSG|<agent>|<utc>|<seq>",
  "agentId": "string", "agentVersion": "semver", "agentSourceHash": "sha256",
  "createdAtUTC": "ISO-8601",
  "engineVersion": "string|null", "repositoryCommit": "string|UNAVAILABLE",
  "authorizationRef": "APPROVAL|… |null",
  "contentHash": "sha256", "contentHashCanonicalization": "mogo.evidence-canon.v1",
  "contentHashScope": "INTEGRITY_ONLY_NOT_AUTHENTICITY",
  "failureState": { "failed": false, "reason": null },
  "payloadType": "RESEARCH_REQUEST | SOURCE_RECORD | EXTRACTED_RULE | EXPERIMENT_PROPOSAL | VALIDATION_RUN | AUDIT_FINDING | RECOVERY_PROPOSAL | APPROVAL_DECISION",
  "payload": { }
}
```

### 7.1 Payload schemas

**RESEARCH_REQUEST** — `{ requestId, educator, topicScope, rationale, targetSourceTypes[], excludedSources[], maxItems, requestedBy, approvalRequired: true }`

**SOURCE_RECORD** — `{ sourceId, educator, sourceType, url|null, retrievedAtUTC, retrievalMethod, httpStatus|null, contentHash, contentBytes, title|null, publishedAtUTC|null, transcriptAvailable: bool, contentProvenance: OBSERVED|UNAVAILABLE, immutable: true }`
*Immutable once written. Corrections create a successor referencing its predecessor.*

**EXTRACTED_RULE** — `{ ruleId, sourceId, educator, claimText, claimLocation, interpretation, setupScope, conditions[{conditionId, requirement, observableFields[]}], testability: TESTABLE|UNTESTABLE_AS_STATED|REQUIRES_UNAVAILABLE_FIELD, implementationStatus: UNKNOWN, fidelityStatus: UNRESOLVED, extractionConfidence, humanReviewRequired: true }`
*`implementationStatus` and `fidelityStatus` are **never** set by this agent.*

**EXPERIMENT_PROPOSAL** — `{ proposalId, hypothesisIds[], familySize, primaryMetricId, secondaryMetricIds[], arms{armA, armB, basis}, minimumOperationalSample, recommendedStatisticalSample, promotionThreshold, rejectionThreshold, falsificationCondition, multiplicityCorrection, promotionCeiling: "REPLAY_EVIDENCE_ONLY", stoppingRule, knownLimitations[], status: "DRAFT" }`
*`DRAFT` only. Declaration is a human act producing an immutable, git-anchored document.*

**VALIDATION_RUN** — `{ runRecordId, authorizationRef, strategyId, instrument, requestedLookbackDays, ambiguousMode, runId, datasetHash, configHash, paramsHash, engineVersion, repositoryCommit, observedWindow{fromUTC,toUTC}, observedCandleCounts{}, datasetCompleteness{}, packageCount, packageHashes[], rejectionRecord{count, complete: bool, records[]}, suppressionRate, exportVerifiedByReimport: bool, identityRecomputed: bool }`
*`rejectionRecord.complete: false` ⇒ **BLOCKING**. `identityRecomputed: false` ⇒ **BLOCKING**.*

**AUDIT_FINDING** — `{ findingId, domain, severity: INFO|WARNING|DEGRADED|BLOCKING|CRITICAL, summary, detail, evidenceRefs[], reproductionCommand|null, verdict: CONFIRMED|PLAUSIBLE, recommendedAction, blocksActivities[], autoRepairable: false }`

**RECOVERY_PROPOSAL** — `{ proposalId, triggeringFindingIds[], riskAssessment, dataAtRisk, proposedActions[{action, target, reversible: bool, destructive: bool}], preActionInventory, rollbackPlan, requiresApproval: true }`
*Any `destructive: true` action is **rejected at schema level**. Deletion is never proposed by an agent.*

**APPROVAL_DECISION** — `{ approvalId, requestRef, decision: APPROVED|REJECTED|APPROVED_WITH_CONDITIONS, approvedBy, decidedAtUTC, scope, conditions[], expiresAtUTC|null, consumesOnUse: true, consumedBy|null }`
*`consumesOnUse` enforces one-authorization-one-run.*

### 7.2 Transport

Content-addressed files under a governed directory, not an in-memory bus. Rationale: durable by
default, diffable, git-anchorable, and survives the exact failure that lost this session's pilot
rejection record — **a memory-only channel is how evidence disappears.**

---

# 8. IMPLEMENTATION ROADMAP *(recommendation)*

### Phase 0 — Architecture and governance
- **Objective:** approve this blueprint; **resolve every §1.6 `UNKNOWN` by direct repository read**
- **Dependencies:** repository read access restored (currently **blocked**)
- **Deliverables:** revised blueprint with §1 completed from full evidence; ADR for the authority matrix; governed directory layout
- **Tests:** none (documentation)
- **Approval gate:** human sign-off on §3 authority matrix and §6 severity model
- **Risks:** premature agreement to a capability survey written without repository access
- **Non-goals:** no code, no agents, no schema changes

### Phase 1 — Read-only System Auditor MVP
- **Objective:** one command → JSON + Markdown health report (§9)
- **Dependencies:** Phase 0; `tests/run_all.sh`; independent canonicalizer
- **Deliverables:** auditor script; report schema; fixtures
- **Tests:** synthetic pass/fail per domain; **must detect a tampered package, a stale server, and a non-writable target**
- **Approval gate:** demonstrated on RUN-001 with zero false positives
- **Risks:** false confidence from shallow checks; scope creep into repair
- **Non-goals:** **no repairs**, no writes outside its report directory, no market data

### Phase 2 — Research Acquisition Agent
- **Objective:** immutable, provenance-complete source records
- **Dependencies:** Phase 1; approved external-access policy
- **Deliverables:** acquisition agent; source-record store; dedup
- **Tests:** hash stability; immutability; refusal on missing provenance
- **Approval gate:** human approval per acquisition target
- **Risks:** silent partial fetch; ToS exposure; duplicate ingestion inflating apparent corroboration
- **Non-goals:** no interpretation, no rule extraction

### Phase 3 — Rule Intelligence and source reconciliation
- **Objective:** structured candidate rules joined to code locations
- **Dependencies:** Phase 2; existing fidelity-matrix approach
- **Deliverables:** Rule Intelligence + Strategy Reconciliation agents; divergence report
- **Tests:** extraction determinism; **no rule may self-report as implemented**
- **Approval gate:** human review of every extracted rule before registry entry
- **Risks:** plausible-sounding misreading of an educator's claim; over-confident joins
- **Non-goals:** **no strategy code changes**; no fidelity status set by an agent

### Phase 4 — Validation orchestration
- **Objective:** authorized replays with complete, verified capture
- **Dependencies:** Phases 1–3; **the Step 1 pilot gate resolved**
- **Deliverables:** Replay & Validation Agent; automatic rejection-record capture; verified extraction
- **Tests:** identity recomputation; **refusal to run without a consumable authorization**; refusal to complete without a full rejection record
- **Approval gate:** per-run human authorization
- **Risks:** authorization reuse; capture regression; optional stopping
- **Non-goals:** no adjudication; no paper/live execution

### Phase 5 — Trade forensics
- **Objective:** excursion, context and loss anatomy over verified evidence
- **Dependencies:** Phase 4 evidence carrying timing + context
- **Deliverables:** Trade Forensics Agent; forensic report schema
- **Tests:** reproducibility from packages alone
- **Approval gate:** human review before any finding informs a proposal
- **Risks:** post-hoc narrative fitted to noise at small n
- **Non-goals:** no rule change proposals

### Phase 6 — Controlled operational recovery
- **Objective:** detect volatile-state risk; extract to durable storage with verified writes
- **Dependencies:** Phases 1–5
- **Deliverables:** Operations & Recovery Agent; write-verified extraction; pre-action inventory
- **Tests:** simulated TCC revocation, blocked download, temp reaping
- **Approval gate:** human approval for any action beyond copy-out
- **Risks:** an agent with write authority during a degraded state
- **Non-goals:** **no deletion, ever**; no automatic repair

### Phase 7 — Coordinated agent workflows
- **Objective:** multi-agent pipelines under the §7 message model
- **Dependencies:** all prior phases operating independently
- **Deliverables:** orchestrator; end-to-end provenance
- **Tests:** authority compliance under composition; **no privilege escalation via chaining**
- **Approval gate:** human approval of each workflow definition
- **Risks:** **emergent authority** — a chain of ALLOWED steps composing into an effectively PROHIBITED outcome
- **Non-goals:** no autonomous campaigns; no automatic execution

---

# 9. SYSTEM AUDITOR MVP *(recommendation)*

**Smallest useful read-only auditor. Version 1 performs no repairs.**

```
scripts/mogo_audit.sh   [--json <path>] [--markdown <path>] [--strict]
```

**Outputs:** `mogo-audit-<utc>.json` (machine-readable) and `.md` (human-readable) — same findings,
same ids, same severities.

```json
{
  "schemaVersion": "mogo.audit-report.v1",
  "auditId": "AUDIT|<utc>", "startedAtUTC": "…", "completedAtUTC": "…",
  "auditorVersion": "1.0.0", "auditorSourceHash": "sha256",
  "engineVersion": "12.18.0", "repositoryCommit": "…|UNAVAILABLE",
  "overallStatus": "HEALTHY|WARNING|DEGRADED|BLOCKED|CRITICAL",
  "blockingFindings": [], "findings": [],
  "domainsChecked": [], "domainsSkipped": [{"domain":"…","reason":"…"}],
  "recommendedNextAction": "…",
  "contentHash": "sha256"
}
```

**Version-1 domain coverage** (subset of §5, chosen for signal per unit of effort):

| Domain | Check | Severity |
|---|---|---|
| Repository integrity | protected drift; tree clean; HEAD; baseline currency | BLOCKING / WARNING |
| Identity chain | recompute every `contentHash` **independently** | BLOCKING |
| Replay determinism | recompute `runId`, `configHash`, `paramsHash` | BLOCKING |
| Evidence completeness | declared gaps vs observed; **rejection record present** | BLOCKING |
| Analytics reconciliation | recompute stats; compare to published | BLOCKING |
| Permissions & storage | **real write-read-delete probe** per target path | BLOCKING |
| Application services | served bytes vs committed (when a server is up) | BLOCKING |
| Practice vs Live | assert Practice where determinable | CRITICAL |

**Hard requirements:**
1. **No repairs. No writes outside its report directory.** Not even a "safe" fix.
2. **No network access** except an optional localhost byte-check.
3. **Never reads or emits credentials** — status only.
4. **Independent canonicalizer**, not imported from `index.html` (§2.1).
5. **Skipped domains are reported explicitly.** Silence is never counted as a pass.
6. `--strict` exits non-zero on any BLOCKING/CRITICAL, for CI.

**Definition of done:** running it against RUN-001 reproduces this session's manual result — 24/24
hashes verified, identity chain recomputed, statistics reconciled, and the **rejection-record gap
raised as BLOCKING**.

---

# 10. OPEN QUESTIONS AND RECOMMENDATIONS

**No answer is selected below where repository evidence is insufficient.**

### 10.1 Blocking — must be resolved before Phase 1

| # | Question | Why it blocks | Recommendation |
|---|---|---|---|
| Q1 | **Does an Engineering Constitution exist, and where?** It was named in the tasking; **I have never seen it.** | It may already fix authority rules this document proposes independently — risking contradiction | Locate and read before ratifying §3. **I decline to assume its contents** |
| Q2 | Repository read access is **currently revoked** (TCC). When restored? | §1 cannot be completed; no agent can be built | Restore Desktop permission, then re-run §1 as a full survey |
| Q3 | **Step 1 pilot gate is unevaluated** and evidence is unextracted | Phase 4 depends on it; the run is unrepeatable | Execute `~/MOGO-PILOT-RECOVERY-HANDOFF.md` §5 first |
| Q4 | Is the ADR corpus the governing mechanism for agent decisions? | Determines whether §3 becomes an ADR or a new instrument | Read `docs/adr/` and follow existing convention |

### 10.2 Architectural — genuine forks

| # | Question | Options | Recommendation |
|---|---|---|---|
| Q5 | Where do agents run? | in-repo scripts · external service · hybrid | **Insufficient evidence.** Depends on unknown ingestion architecture (Q9) |
| Q6 | Is the Independent Evidence Auditor a separate codebase? | shared repo, isolated module · separate repo | **Separate module minimum**, separate repo preferred — independence is its only value (§2.1) |
| Q7 | How is agent authorization enforced technically? | honour-system · pre-flight checks · capability tokens | **Insufficient evidence** on the runtime. Note: §3 is only a policy until mechanically enforced |
| Q8 | Should `identity.commitHash` be populated? | build-time injection · leave `UNAVAILABLE` | Populating it strengthens every Action Record — but it is an **evidence-platform change**, forbidden inside MOGO-004 §2. Sequence deliberately |
| Q9 | What knowledge-ingestion components already exist? | — | **UNKNOWN** (§1.6). `MOGO-RESEARCH-ACQUISITION-ARCHITECTURE.md` is untracked and unread. Resolve before Phase 2 |

### 10.3 Governance

| # | Question | Recommendation |
|---|---|---|
| Q10 | May an agent draft a pre-registration a human then declares? | Yes as `DRAFT` only. **Declaration must remain human** — its value is that it preceded the data |
| Q11 | Can agent-produced analysis ever exceed `REPLAY_EVIDENCE_ONLY`? | **No.** The ceiling is categorical (`PREREG-001` §5). Agent involvement cannot raise it |
| Q12 | Who may clear a CRITICAL? | Human Approval Authority only, with a recorded acknowledgement |
| Q13 | Retention for agent Action Records? | **Insufficient evidence** — no retention policy verified |

### 10.4 Standing recommendations

1. **Close the censoring gap before any further campaign work.** Missing in two consecutive runs;
   `PREREG-001` §9 makes every affected figure void. Cheapest, highest-value fix available.
2. **Make write-verification structural, not procedural.** EXP-001 recurred this session *because the
   engine already knows a download is unproven while the surrounding workflow did not.*
3. **Refresh the protected-drift baseline** — 12.5.0 vs current 12.18.0.
4. **Do not build agents before the auditor.** An agent fleet without independent verification
   multiplies unverified claims. §9 first, deliberately.
5. **Treat §1.6 as the roadmap's true starting point.** This blueprint's weakest section is its
   evidence survey, and it is weak for a knowable, fixable reason.

---

## Summary of standing

| | |
|---|---|
| Blueprint | 🟡 **PROPOSED** — awaiting approval |
| §1 evidence survey | ⚠️ **PARTIAL** — repository unreadable at writing; §1.6 unresolved |
| §§2–10 | Recommendations only — **no repository claims** |
| Code changed | ✅ none |
| Strategy logic changed | ✅ none |
| Campaign C1 | ✅ not begun |
| Automatic execution | ✅ not enabled |
| Phase 1 | ⏸ **awaiting explicit approval** |

---

**This document proposes a system whose central discipline is that nothing is true because an agent
said so. It would be self-refuting to assert capabilities I could not open a file to confirm — so
where the evidence was unavailable, this blueprint says `UNKNOWN` and stops. That list is the first
thing to fix, and fixing it is cheap.**

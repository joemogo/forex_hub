# MOGO-002 — Milestone Closeout Record

**Milestone:** MOGO-002 — ALEX Strategy Validation
**Date:** 2026-07-30 · **Engine:** `APP_VERSION` 12.7.1 · **Strategy:** `alex_g_sr_v1_1`
**Commit hash:** ⏸️ **PENDING — commit not created; see §12**
**Release tag:** ⏸️ **PENDING — tag not created; see §12**

> This record does not rewrite or replace any prior audit document. All MOGO-002.x review packages
> remain authoritative for their own findings.

---

## 1. Milestone purpose

Establish, from repository evidence alone, whether the ALEX paper-trading strategy does what its
specification says; what the source material can and cannot support; and what must be true before
historical replay may begin. **Validation, not optimisation** — no milestone in this track changed a
trading rule to improve a result.

## 2. Completed deliverables

| Sub-milestone | Deliverable | Outcome |
|---|---|---|
| **002.5** | Strategy Fidelity Audit | 9/13 rules MATCH, **0 missing, 0 differing**; risk & trade-management fidelity **0/0** — undefined, not unverified |
| **002.6** | Knowledge Engineering | `alex_g_educator_v2_draft`, 111 rules, separate from production; **only 41 deterministic**, 66 carry an unstated parameter |
| **002.7** | Source Acquisition | 9th ALEX_G source ingested; **first `stop_rule` claims in the corpus (0 → 2)**; 200-video channel catalogue established |
| **002.8** | Implementation Specification | Complete spec of the implemented strategy, 20 sections, from direct code reading |
| **002.8A** | Reconciliation + ALEX v1.1 release | 41 educator rules dispositioned; v1.1 released |
| **002.8B** | Setup Isolation Audit + execution gate | RZR suspended for research; B&R unchanged |
| **003** | Research & Validation Standard *(separate milestone)* | Replay readiness gate defined; ALEX assessed **NOT READY** |

## 3. ALEX v1.1 release state

| | |
|---|---|
| Strategy version | **`alex_g_sr_v1_1`** |
| Specification version | `alex_g_sr_v1` — **deliberately unchanged**; no engine parameter changed |
| Implementation version | `alex_g_sr_v1.impl.1` |
| Engine | `APP_VERSION` **12.7.1** |
| Protected drift | **ZERO** — 63 functions, 4 constants byte-identical |

**Delivered in v1.1 (12.7.0):** Monday–Wednesday entry eligibility · realized-R from actual exit
prices · chronological equity walk · current vs maximum drawdown separated · configured starting
balance · release version stamped on every new trade · four dead config keys omitted.

**Delivered in 12.7.1 (002.8B):** setup-level execution policy; two unregistered reason codes fixed.

**`RULES_ALEXG` remains a protected constant and byte-identical.** v1.1 was implemented additively via
`RULES_ALEXG_V11`, following the change-control rule written into `RULES_ALEXG` itself.

## 4. Paper-trading execution policy

| Setup | Internal ID | Status |
|---|---|---|
| **Break & Retest** | `B_breakRetest` | ✅ **ACTIVE** |
| **Repeated Zone Reaction** | `A_repeatedReaction` | ⏸️ **SUSPENDED FOR RESEARCH** |

Controlled by one boolean: `RULES_ALEXG_V11.v11Config.setupSuspensionEnabled` (default `true`).
The gate **fails open** in every ambiguous case. Suspension window recorded with
`startedAt` / `endedAt` / `authority` / `reason`.

### 4.1 Reason for suspension

A Tier 1 forward-paper observation: **18 RZR trades, 1 win / 17 losses**, with many losers showing
little favourable movement before stopping out.

### 4.2 ⚠️ This is NOT a finding that RZR is invalid

**Stated explicitly, because the distinction is the whole point of the suspension:**

- The observation is **Tier 1** evidence under the MOGO Research & Validation Standard §9 — an initial
  behavioural sample. It may justify an operational change; **it cannot support any conclusion about
  the setup's validity or expectancy.**
- The sample **could not be verified from the repository** — ALEX paper trades persist only in browser
  `localStorage`.
- The sample is **pre-v1.1**. Those are v1.0 trades; the Mon–Wed gate applied to none of them.
- A documented structural defect (§7, B1) makes one setup direction **impossible to produce**, which
  may itself bias any ALEX sample.

**The suspension is an operational hold pending Tier 2+ replay evidence, and is reversible by one
boolean.**

### 4.3 What suspension does and does not do

| | |
|---|---|
| RZR setups still detected | ✅ Yes — `alexGEvaluateRepeatedReaction` untouched and protected |
| RZR setups still classified and recorded | ✅ Yes — persisted to `fxhub_alexg_setups` |
| Rejection evidence recorded | ✅ Yes — permanent `SUSPENDED — RESEARCH HOLD` row + linked `RULE_EVALUATED`/`CANDIDATE_REJECTED` carrying `SETUP_SUSPENDED_FOR_RESEARCH` |
| **New RZR paper positions opened** | ❌ **No** — the only thing withheld |
| Existing open RZR positions | ✅ Close normally — the exit path never consults `setupType` |
| Historical RZR trades | ✅ Preserved and still counted in analytics |
| **Replay** | ✅ **Unchanged — still generates both setup types** |

**Replay is deliberately exempt.** It is research, and the only route to the Tier 2+ sample that could
retire this suspension.

## 5. Replay-readiness audit outcome

# ❌ NOT READY — BLOCKING DEFECTS EXIST

§3 gate applied to ALEX v1.1 from code: **6 PASS · 3 PARTIAL · 4 FAIL**.

**Genuinely sound and not to be rebuilt:** look-ahead validation (`alexGValidateTradeNoLookahead`),
ambiguous-candle handling, deterministic IDs (no `Math.random`), still-open handling, and the rich
analytic breakdowns. **The replay engine's logic is sound; its evidence layer is not.**

## 6. Test results

| Check | Result |
|---|---|
| `tests/run_all.sh` | **679 / 679**, 14 suites, **0 failures**, 0 execution errors |
| Protected drift | **ZERO** — 63 functions, 4 constants |
| `tests/strategy_fidelity/` | 63 / 63 |
| `tests/knowledge_engineering/` | 55 / 57 — 2 known-obsolete |
| `tests.trader_intelligence.*` | 307 tests, 4 failures — known-obsolete, pre-existing |

**6 known-obsolete failures**, all pre-existing, all asserting *the production evidence tree is empty*
(false since 2026-07-27) or hardcoded pre-ingestion counts. **No production logic was changed to make
any test pass.**

## 7. Known replay blockers → transferred to MOGO-003

| # | Blocker | Severity |
|---|---|---|
| **B1** | **Resistance-role zones structurally impossible** — documented since v4.0, verified empirically. Biases the long/short distribution of any replay with no indication in the output | **CRITICAL** |
| **B2** | No explicit date range — data is *"N days back from now"*, so a period cannot be pre-declared | **CRITICAL** |
| **B3** | No replay-run ID | **CRITICAL** |
| **B4** | Replay results are session-only and vanish on reload | **CRITICAL** |
| **B5** | Money-space math non-deterministic (`pipValuePerLot` reads live `pairData`); R-space is clean | **HIGH** |
| **B6** | Transaction costs captured with **zero effect**; candles are mid-only | **HIGH** |
| **B7** | Replay does not apply v1.1 rules — it would replay v1.0 entry behaviour | **HIGH** |
| **B8** | No commit hash on results | **MEDIUM** |

Plus 8 validation-blocking gaps (14 missing metrics, 4 of them degenerate by construction; no data
partitioning; no source-candle references).

## 8. Unresolved items transferred to MOGO-003

**Engineering:** B1–B8 above · Phase 1 (replay trustworthiness) is the next task.

**Open Engineering Authority decisions carried forward:**

| Decision | Subject |
|---|---|
| OD-2 … OD-7 | MOGO-002.5 — risk-source acceptance, dead config key, trace limitation, ADR, `PARTIAL_PROVENANCE`, `ALEX_SCORE_V2` status |
| KEREV-A | **Reframed** — may MOGO author the stop buffer and anchor reading as labelled MOGO parameters? |
| KEREV-B … E | Specification separation, contradictions, unresolved parameters, classifications |
| **D2 / R4** | **Concept-level consensus counting.** All 341 claims remain `emerging`; nothing is promotable until this is decided |
| A7-4 | The 6 known-obsolete tests — rewrite as invariants or delete |
| A8-4 | The three behavioural divergences — record as MOGO-authored, or open an implementation milestone |
| **A8-5** | **Fix the KE test-suite mutation defect** — the suite rewrites its own repository artifacts |
| XCONTRA\|20260729\|004 | Is 1:2 a floor a trade may be set at, or one a target may never be revised to? |

## 9. Defects found and fixed during MOGO-002

| Defect | Fix |
|---|---|
| `resultR` fixed at `±R`, detached from realised exits | `alexGRealizedR()` (v1.1) |
| Equity walked newest-first | Chronological walk (v1.1) |
| "Current drawdown" computed the maximum | Two separate measures (v1.1) |
| Hardcoded `10000` P&L baseline | Configured starting balance (v1.1) |
| **`CONFIG_ENTRY_DAY_NOT_ELIGIBLE` never registered** — v1.1's entry-day rejection events were **silently dropped** by `validateDecisionEvent` | Registered (12.7.1); fixtures assert retention |
| Regression suite made date-dependent by the Mon–Wed gate | Test-process clock pin; zero assertions changed |

## 10. Governance record

- **Zero protected functions or constants modified** across the entire milestone.
- **No trading rule changed to improve a result.**
- **No educator rule invented**; no numeric stop buffer attributed to Alex G.
- **No draft rule promoted** — `evidence/proposals/` remains at 0.
- **Replay never executed**; `replayAuthorization` remains `false` on all six `OwnerDecision` records.
- **Historical trades never migrated, rewritten or back-filled.**

## 11. Formal completion status

**MOGO-002 engineering work is COMPLETE and verified.** All deliverables produced; all tests passing;
zero drift.

**Formal closure additionally requires the commit and tag in §12.**

## 12. Release commit scope — Engineering Authority decision E5

**Authorised scope: Categories A + B + D only.** Working tree at closeout: 7,916 changed/untracked files.

| Class | Files | Disposition |
|---|---|---|
| **A — Approved MOGO-002 work** (code, tests, scripts) | **20** | ✅ **Committed** |
| **B — Documentation generated during MOGO-002** | **70** | ✅ **Committed** |
| **D — Mixed file** (`docs/TESTING.md`) | **1** | ✅ **Committed** — see §12.2 |
| **C — Unrelated / other milestone** | **19** | ❌ **Excluded** |
| **E — Trader Intelligence evidence corpus** | **7,807** | ❌ **Excluded — see §12.1** |
| **F — Unknown** | **0** | — |

### 12.1 ⚠️ The evidence corpus is intentionally excluded from version control

**`docs/trader-intelligence/` (7,807 files, 43 MB) is deliberately NOT under version control.**

**Reason — third-party licensing and public-repository restriction.**
`DECISION|MOGO|20260727|005` (active Owner Decision) states verbatim:

> *"Copyrighted material must not be redistributed, and no public reproduction may be generated —
> **this covers publishing the repository**, exporting raw transcripts or verbatim excerpts outside
> it…"*

and is explicit that this is **not a grant of rights**:

> *"MOGO has lawful access and an internal-use determination, **not permission from the rights
> holder**."*

The material and the exposure:

| | |
|---|---|
| Sources classified `restricted_third_party` | **11 of 12** (the 12th is `unknown`) |
| Raw third-party transcripts | **12 files, 436 KB of verbatim text** |
| Verbatim excerpts embedded in evidence records | **416 items, 38,751 characters** |
| Standing `unresolved_licensing` review entries | **12, priority `critical`, status `open`** — the decision directs that this marker *"should not be cleared"* |
| **Repository remote** | `https://github.com/joemogo/forex_hub.git` — **PUBLIC** |

Committing this material to a public repository would place verbatim third-party transcript content
one `git push` from the exact redistribution constraint (2) prohibits. **It is therefore excluded.**

### 12.2 Consequence — some audit documents reference locally-held evidence

**Several committed MOGO-002 audit documents cite claim IDs whose underlying evidence files remain
local and uncommitted.** For example `CLAIM|ALEX_G|20260729|025` — the stop-rule claim underpinning
the KEREV-A reframing — is cited in the committed audit set but its record lives only in the working
tree at `docs/trader-intelligence/evidence/claims/`.

**This is a disclosed, accepted limitation of this release, not a defect.** A reader of the committed
tree can see every conclusion and its stated basis, but cannot independently re-derive it from
committed data.

`docs/TESTING.md` is committed whole. It contains both pre-existing Trader Intelligence documentation
and this milestone's own testing additions; the two could not be separated without interactive
staging, and both are legitimate repository documentation.

### 12.3 The exclusion does not affect anything that runs

| | |
|---|---|
| Running application (`index.html`) | ✅ **Unaffected** — never reads `docs/trader-intelligence/` |
| ALEX paper trading | ✅ **Unaffected** |
| Regression suite | ✅ **Unaffected** — 679/679 with the corpus uncommitted |
| Protected-function drift | ✅ **Unaffected** — zero |

The corpus is research data consumed by offline Python tooling only. Nothing in the browser
application depends on it.

### 12.4 Evidence-corpus versioning remains a future governance decision

**Whether and how to version the corpus is deferred to a future repository-governance decision, not
resolved here.** Options on record:

- make the repository **private**, which would align with the *"private internal research"* scope the
  Owner Decision authorises, and then version it normally;
- version a licensing-safe subset (derived records only, raw transcripts and verbatim excerpts
  excluded);
- keep it permanently local with a documented backup regime.

**Standing risk while unversioned:** the 12 raw transcripts are irreplaceable — MOGO-002.7
demonstrated that YouTube caption retrieval returns HTTP 200 with 0 bytes from this environment, so
they cannot be re-acquired without the operator. **They have no version-control protection today.**

### 12.5 Release identity

| | |
|---|---|
| **Commit hash** | ⏸️ __COMMIT_SHORT__ |
| **Tag** | **`mogo-002-complete`** (annotated) |
| Branch | `main` |
| Pushed | **No** |

### 12.6 Full commit reference

__COMMIT_FULL__

---

*MOGO-002 closeout. Engineering complete and verified; formal release held pending two scope decisions.*

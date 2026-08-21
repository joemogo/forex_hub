# MOGO-022 → MOGO-023 Engineering Handoff

**Status: B-32 ACCEPTED COMPLETE at the milestone boundary. MOGO-023 has NOT begun.**

Every figure in this document was **measured directly** on 2026-08-21 (local `Fri Aug 21 18:17 EDT`)
against the working tree and runtime, not carried over from summaries. Anything that could not be
verified in this session is labelled **UNVERIFIED**. Historical context is marked as such.

---

## 1. REPOSITORY AUTHORITY

| Item | Measured value |
|---|---|
| Repository path | `/Users/joemogollon/Desktop/Forex Hub` |
| Current branch | `main` (local) |
| HEAD SHA | `b23085f03d18f9e32607b678bed653302c573aee` |
| HEAD short | `b23085f` — *B-32.26 — close the scan's own edges, and stop* |
| Remote | `origin` → `https://github.com/joemogo/forex_hub.git` |
| Upstream of local `main` | **`origin/mogo-main`** |
| Ahead / behind upstream | `0 / 0` — fully pushed |
| Working tree | **clean** (`git status --porcelain` empty) |
| Untracked files | none (`--untracked-files=all` empty) |

### ⚠ BRANCH TOPOLOGY — READ THIS BEFORE ANY GIT OPERATION

The authoritative MOGO branch on the remote is **`mogo-main`**, not `main`.

```
refs/heads/main                    abfc763   "Add files via upload"  (2026-07-16)
refs/heads/mogo-main               b23085f   <-- ALL MOGO WORK IS HERE
refs/heads/evidence-platform-v12.19 b71f016
```

`git config` explains why `git push origin main` has been writing to `mogo-main`:

```
branch.main.remote  origin
branch.main.merge   refs/heads/mogo-main
push.default        upstream
```

**`abfc763` is NOT an ancestor of HEAD** (verified with `git merge-base --is-ancestor` → false).
Remote `main` is an unrelated upload with no shared history. This is why every isolated verifier
worktree in this campaign started at `abfc763` and had to `git reset --hard` to the work commit.

**Consequence for a fresh session:** never `git checkout main` from a fresh clone expecting MOGO,
and never "fix" the divergence by merging or force-pushing `main` — that is an operator decision,
not a cleanup task.

### Commits produced during the final B-32 work (all pushed)

```
b23085f  B-32.26 -- close the scan's own edges, and stop
ca18190  B-32.25 -- an invariant scoped to the names you were looking at
91427f3  B-32.24 -- a repair is not evidence until breaking it fails something
65665c6  B-32.23 -- the write path: the code that mints what every gate later checks
00124c7  B-32.22 -- guard the lane that stores the evidence of hardening
6cc93d6  B-32.21 -- an exemption is a bypass with a reason attached
919e4e6  B-32.20 -- absence is not silence, one layer deeper
20851f0  B-32.19 -- the record against the package it was minted from
72c3539  B-32.18 -- a record checked against itself reaches where no anchor can
0b91c2b  B-32.17 -- an anchor that records a value nothing compares is not an anchor
19505b3  MOGO-022: 222 of 263 identities now exist only in the manifest
6565c86  MOGO-022: record B-32.14 / .15 / .16
4e23249  MOGO-022: close the four survivors
03fd6e1  MOGO-022: B-32.16 -- a condition an attacker controls is not a scope, it is a switch
```

Net across the last 12 commits: **+3486 / −27 lines, 21 files.**

### Changes made OUTSIDE the repository

**One, and only one:** `~/.claude/settings.json` — see §11. Fully documented, backed up, verified additive.

Also written outside the repo, by design and pre-existing: evidence checkpoints under
`~/MOGO-EVIDENCE-PRESERVED/` (read-only copies; latest `20260821T215346Z`).

---

## 2. B-32 FINAL VERDICT

**COMPLETE.** Accepted by the operator at the milestone boundary.

### Evidence against each finite completion gate

| Gate | Verdict | Evidence (measured now) |
|---|---|---|
| All gates pass | **HOLDS** | `validate_evidence` `{INFO:0, WARNING:2, ERROR:0, FATAL:0}`; `validate_graph` `{WARNING:31, ERROR:0}`; `validate_acquisition` `{all 0}`; reconcile `RECONCILED` |
| Continuous coverage — preserved **and** newly created | **HOLDS** | 259/259 observations anchored, both directions; identity step runs **before** the novelty check and both early exits, driven by the full recovered set |
| Accumulated mutations killed | **HOLDS** | Final rounds: 13/13, 8/8, 7/7, 8/8, 6/6, 11/11. Round 25 independently re-ran 16 across the campaign: 14 killed, 2 non-findings (one redundant layer whose load-bearing floor *is* pinned; one mutation of dead code) |
| No P1/P2 remains | **HOLDS** | See below |
| Recurring shapes covered by **systemic** invariants | **HOLDS** | Removing a *row* from any table fails a test — verified for `CORPUS_ANCHORS`, `ANCHOR_VALUE_BINDINGS`, `PACKAGE_WITNESSES`, `RECORD_DERIVATIONS`, `ANCHOR_DOCUMENT_BINDINGS_BY_SCHEMA`, `POSITION_MAP`, `OUTCOME_MAP`, severity partition |
| Final round finds no materially new P1/P2 **category** | **HOLDS** | Rounds 22, 23, 24 **and** 25 each found none |

### Final independent adjudication

Round 25 was convened to **adjudicate, not hunt**. Verdict: *"THE STOP CONDITION IS MET… I found
nothing that would justify another round, and I am not going to invent one."*

### Why another adversarial round is NOT required

The findings decayed monotonically across four rounds:

- **Round 21** — a full-corpus forgery reached `exit 0` (live bypass).
- **Round 24** — a defensive default *would* fail open **if its assignment were removed** (latent on next edit).
- **Round 25** — *if someone later writes a step across two lines*, the scan would not see it (hypothetical on future authorship).

Round 25's three residual findings had **no live instance in the shipped file**. They were closed
anyway in `b23085f`. Continuing past this point would be manufacturing work, which the operator's
rule explicitly forbids.

### Remaining P1/P2

**None.** The hardening backlog carries no OPEN rows. Remaining items are P3 or documented
threat-model boundaries — see §9.

---

## 3. TEST / VALIDATION AUTHORITY

### Canonical command

```bash
bash tests/run_all.sh          # full gate; exit 0 required
```

### Final measured results (last full run at HEAD, plus re-verified individually just now)

| Gate | Result |
|---|---|
| Python tests | **`Ran 1417 tests … OK`**, exit 0 |
| Python collection manifest | `IN SYNC (27 modules, 1417 tests)` |
| JS fixtures | **2386 run / 2386 passed / 0 failed**, 0 execution errors, 34 suites |
| `validate_evidence.py` | `{'INFO': 0, 'WARNING': 2, 'ERROR': 0, 'FATAL': 0}` |
| `validate_graph.py` | `{'INFO': 0, 'WARNING': 31, 'ERROR': 0, 'FATAL': 0}` |
| `validate_acquisition.py` | `{'INFO': 0, 'WARNING': 0, 'ERROR': 0, 'FATAL': 0}` |
| `observation_graph_reconcile.py` | `RECONCILED (STRUCTURE ONLY)`; `orphanCheckDisagreement 0`, `orphansTheGraphFailedToReport 0` |
| Protected-function drift | `No drift: all 63 protected functions and 4 protected constants byte-identical` (app v12.39.3) |
| Auto-mode governance | `IN SYNC (27 environment / 21 allow / 74 soft_deny)` |
| Extractor / coverage / checkpoint selftests | `SELFTEST PASS` (×3) |

### Warnings and what they mean — both are honest, neither is a defect

1. **`PACKAGE_WITNESS_UNAVAILABLE` ×1** — one observation cannot be resolved to a captured package
   because its artifact (`evidence/FWD-20260818T153216Z-PACKAGES.json`) has aged out. Capture
   artifacts are perishable and gitignored **by design**. The count is reported precisely so that a
   jump in it is visible; silence would make deleting `evidence/` a switch.
2. **`PACKAGE_WITNESS_DEGRADED` ×1** (covering 2 field comparisons) — one `LIVE_CLOSE` package
   records `balanceBefore`/`balanceAfter` as `null`, and the observation minted from it carries
   neither. Legitimate: the engine recorded no value and the importer invented none.

`validate_graph`'s 31 WARNINGs are **genuine orphan sources** (30 sources cited by no observation +
1 owner decision). These must stay visible — suppressing them was the defect B-32 fixed.

### Mutation / adversarial results

25 adversarial rounds. Final-phase mutation batches all reached 100% kill after repair. Round 25's
independent cross-campaign sample: **14/16 killed**, with both survivors adjudicated as non-findings
(`M2` a redundant witness layer whose record-derived floor is itself pinned — proven by `M13`/`M14`;
`M6` a mutation of `INTEGRITY_SEVERITIES`, which `grep` shows is dead code referenced only by its own
definition).

---

## 4. FINAL INTEGRITY ARCHITECTURE (as it actually exists at `b23085f`)

Eight gates, layered. Each was added because it caught something every prior gate missed.

### 4.1 MOGO-owned IndexedDB integrity manifest — operator **option (A)**

`docs/trader-intelligence/evidence/ledger-preservation/MOGO_IDENTITY_MANIFEST.json`
(`schemaVersion: mogo.identity-manifest.v1`)

- **Authoritative implementation:** `scripts/trader_intelligence/identity_manifest.py`
  (`load`, `identities_from_packages`, `merge`, `write`, `update_from_packages`).
- Derived **only** from `sourceTradeId` on hash-verified packages recovered from **MOGO's own
  IndexedDB origin**. Chrome shared Local Storage is **never read** (option B declined: one shared
  store holding 136 unrelated origins of personal browsing). Option C (recurring manual runs) rejected
  because coverage decays between runs.
- **Append-only.** First hash wins. A same-id/different-hash arrival is a **CONFLICT**: the recorded
  value is kept, the manifest is **not advanced**, and the run exits non-zero.
- An **absent** (`null`) `contentHash` may be filled by a later package; a **recorded** one is never
  overwritten. Filling an absent value is not taking a newer one.
- `merge` **never shrinks**: malformed rows are carried through untouched. An append-only record does
  not get to decide which of its rows were worth keeping.
- Atomic write (temp-and-rename). A damaged manifest is **refused, not reset**.

### 4.2 Continuous coverage mechanism

`scripts/forward_capture.sh` — `detect → preserve → recover → import → reconcile → assimilate`.

The identity step runs **before** the novelty check and **before both** early exits, driven by the
**full recovered set**. Therefore `manifest ⊇ imported`: a new close is recorded before it can become
an observation, and a quiet capture is an idempotent no-op rather than a gap.

### 4.3 Require-list and allow-list (both directions)

`scripts/trader_intelligence/validate_evidence.py::check_preserved_identities_still_present`

- **Require-list** — every preserved non-developer identity must still exist as an observation
  `sequenceId` → `PRESERVED_IDENTITY_MISSING` (ERROR). Catches deletion and delete-and-pad.
- **Allow-list** — every observation's `sequenceId` must appear in some manifest →
  `UNANCHORED_OBSERVATION` (ERROR). Catches fabricate-by-append. **Fails closed** on a non-string or
  absent `sequenceId`.

### 4.4 Anchor availability — one declared table

`CORPUS_ANCHORS` + `_check_preservation_anchor` + `check_corpus_anchors_are_available`
→ `CORPUS_ANCHOR_UNAVAILABLE` (ERROR).

Availability is checked **once, from a table**, so a gate cannot be disabled by removing what it
reads — nor by emptying it, renaming `identities`, making the document `null`/a list, or re-prefixing
every row `AGT|TEST|`. **Not scoped by population** (B-32.16: *a condition an attacker controls is not
a scope, it is a switch*).

### 4.5 Anchor **values**, not only existence

`ANCHOR_VALUE_BINDINGS` / `ANCHOR_FIELDS_UNBOUND` → `ANCHOR_VALUE_CONTRADICTED`,
`ANCHOR_VALUE_UNCHECKABLE`, `UNADJUDICATED_ANCHOR_FIELD`, `ANCHOR_VALUES_UNCOMPARED`.

Measured bindings, all exact today: ledger `pnl`→`pnl` (35/35), `pair`→`instrument` `/`→`_` (35/35),
`closedAt`→`closedAt` (35/35), manifest `contentHash`→`sourceContentHash` (259/259). A field in
neither table is **reported**, so a new anchor field must be adjudicated rather than joining the
unread set.

### 4.6 Anchor **document** vs its rows

`ANCHOR_DOCUMENT_BINDINGS_BY_SCHEMA` (keyed by `schemaVersion`) → `ANCHOR_DOCUMENT_CONTRADICTED`,
`ANCHOR_DOCUMENT_FIELD_MISSING`, `ANCHOR_DOCUMENT_UNCHECKABLE`, `UNADJUDICATED_ANCHOR_SCHEMA`.

`closedTotal`, `closedReal`, `closedDeveloperTest` and `ledgerRollup` (= sha256 of row hashes joined
by newline, confirmed against `scripts/preserve_paper_ledger.js`) are re-derived from the rows. Nine
capture-time fields are excused **with reasons**. Deleting a bound field is reported; iteration is over
the **union** of present and bound fields.

### 4.7 Intra-record derivability — needs no witness, so no cohort is out of reach

`RECORD_DERIVATIONS` + `_derive` → `RECORD_CONTRADICTS_ITSELF`, `DERIVATION_UNCHECKABLE`,
`RECORD_FIELD_MISSING`.

| Derivation | Required | Agreement |
|---|---|---|
| `rMultiple` from `entry`/`stop`/`exitPrice`/`direction` | yes | 259/259, max deviation **4.1e-07** |
| `outcome` from sign(`rMultiple`) | yes | 259/259 |
| `rMultiple` from `pnl`/`riskAmount` | no | 38/38 |
| `outcome` from sign(`pnl`) | no | 38/38 |

`required` is **measured** against the live corpus and asserted by a test. A genuine breakeven returns
a distinct `_NO_VERDICT` sentinel (not "uncheckable"), while R-from-price still checks the number — so
`rMultiple: 0` is not an escape.

### 4.8 The captured package — the only witness MOGO does not write

`PACKAGE_WITNESSES`, `_packages_by_content_hash`, `_witness_value`,
`check_observation_matches_its_package` → `PACKAGE_WITNESS_CONTRADICTED`,
`PACKAGE_WITNESS_INCOMPLETE`, `UNREADABLE_PACKAGE_WITNESS`, `AMBIGUOUS_PACKAGE_WITNESS`,
`PACKAGE_WITNESS_UNAVAILABLE` (WARNING), `PACKAGE_WITNESS_DEGRADED` (WARNING).

Seven fields compared: `entry`←`positions[0].entryPrice`, `stop`←`originalStop`,
`direction`, `positionSize`, `accountBalanceBefore`←`balanceBefore`,
`exitPrice`←`outcomes[0].exitPrice`, `accountBalanceAfter`←`balanceAfter`.

- Resolution is by `sourceContentHash` → package `contentHash`; artifacts located via
  `EvidenceSource.repositoryPath` (committed; the artifacts themselves are gitignored).
- A package resolving but yielding **no value** is `PACKAGE_WITNESS_INCOMPLETE`, not silence.
  A `null` is excusable **only** when the record claims nothing either.
- A duplicate `contentHash` whose contents **differ** is ambiguous; identical copies are legitimate
  (measured: 25 of 262 packages appear in more than one artifact).
- Only sources the observations **cite** are parsed (JSON-parsing all 59 reported 12 transcripts as
  unreadable — a false positive is how a real gate gets switched off).

### 4.9 Importer contracts

`scripts/trader_intelligence/import_mogo_observations.py`

- `POSITION_MAP` / `OUTCOME_MAP` are pinned **bidirectionally** against `PACKAGE_WITNESSES` by
  `tests/trader_intelligence/test_import_mogo_observations.py::TestTheImporterMintsWhatTheWitnessWillCheck`,
  plus an end-to-end test that a minted record passes its own witness. Neither table can be edited alone.
- A package with **more than one** position or outcome is **skipped with a reason**, never partially
  imported — choosing between them would be a guess about which trade the package describes.
- Developer-trade refusal (`is_developer_test_package`) reads three markers; the decision is
  **recorded at capture time** as `refusedByImportPolicy` because a manifest row has no position object.
- `sequenceId` is the package's `sourceTradeId`; `sourceContentHash` is the package `contentHash`.

### 4.10 Population / replay / forward separation (anti-contamination)

`scripts/trader_intelligence/trade_observation.py::observation_population`

- Population is **derived from `EvidenceSource.sourceType`**, never denormalised onto the record.
  `paper_trade`/`live_trade_review` → FORWARD; `replay_observation`/`generated_analysis` → HISTORICAL;
  `journal_entry` → RECONSTRUCTED. Unresolvable → **UNKNOWN, fails closed**.
- `check_observation_population_rebinding` cross-checks the `captureBasis` stamp against the source type.
- **`alex_g_sr_v1` is MOGO's implementation; `ALEX_G` is a person.** `TRADE_OBSERVATION` nodes are built
  with `traderId=None` and `strategyFamilyId=None`, and
  `validate_graph.py::check_observation_trader_isolation` runs an **unbounded undirected BFS** to prove
  no observation reaches a trader node at any hop.

### 4.11 Corpus append-only + content protections

`check_corpus_matches_recorded_state`, `check_corpus_is_append_only`,
`check_observation_source_content_unique`, `check_observation_sequence_ids_unique`,
`check_values_are_finite` → `CORPUS_CONTENT_DIVERGED`, `EVIDENCE_REMOVED`,
`LEDGER_DISAGREES_WITH_STATE`, `DUPLICATE_SEQUENCE_ID`, `DUPLICATE_SOURCE_CONTENT_HASH`,
`NON_FINITE_VALUE`, `UNSERIALISABLE_CORPUS`.

A crash must never leave a **stale all-clear** report on disk: NaN/Inf are reported, and
`corpus_fingerprint` failures are caught so the report is still written.

### 4.12 Fail-closed behaviour, generalised

- Severity is closed over the source: all **75** finding types partition into blocking /
  context-dependent / soft-by-design (`TestCorpusIntegrityFindingsAreBlocking`). A downgrade fails.
- Exit codes come from one shared `graph_common.exit_code_for` (three validators each hand-rolled it wrong).
- **Python test collection** is pinned (`tests/count_python_tests.py` + `expected_python_test_counts.tsv`),
  because 25 rounds of hardening are *stored as tests*.
- **Shell guards** are pinned (`tests/trader_intelligence/test_forward_capture_guards.py`): every
  failure-capable pipeline in `forward_capture.sh` must be `if !`-guarded (safe only because `pipefail`
  is set — also asserted) or capture `PIPESTATUS` into a variable tested **after** the capture. Every
  exit-status default **fails closed**. Proven non-vacuous by feeding the scan lines it must catch and
  must not.

### 4.13 Trust boundaries

| Trusted | Not trusted |
|---|---|
| Captured evidence packages **while their artifact survives** (engine-written, not corpus-derived) | Any single in-corpus anchor on its own |
| The identity manifest **cross-checked** against package `contentHash` | `research_assimilation --write` (it re-stamps the fingerprint from whatever is on disk) |
| Arithmetic internal to a record | Documentation claims (five of mine were falsified by measurement) |

### 4.14 Known integrity limitations

**The standing boundary (SPEC §7.9/§7.12):** an attacker who writes **both** the observation **and** a
matching capture artifact, or who rewrites every anchor consistently, is caught by no in-corpus gate.
A rollup does **not** close it — whoever can append the rows can recompute the rollup. Closing it needs
a witness outside the corpus, and the available ones (git history, the operator's checkpoint directory)
are writable by the same actor. **Documented deliberately rather than built as something that would look
like protection without being any.**

The package witness is **perishable**: coverage is 258/259 today and will decay as artifacts age out.
The count is reported so the decay is visible.

---

## 5. CURRENT EVIDENCE / OBSERVATION POPULATIONS (measured now)

| Quantity | Value |
|---|---|
| Identities in manifest | **263** |
| — requirable | **259** |
| — refused (developer test trades) | **4** (`AGT|TEST|1783897893481`, `…896514`, `…898716`, `…900066`) |
| Rows carrying a `contentHash` | **263 / 263** |
| Manifest `captureBasis` | `REPLAY_RUN 221`, `LIVE_CLOSE 29`, `HISTORICAL_BACKFILL 13` |
| Observations | **259** |
| — with a string `sequenceId` | 259 |
| — anchored in the manifest | **259 / 259** |
| — with `sourceId` | 259 |
| — with `sourceContentHash` | 259 |
| Populations | **HISTORICAL 221 · FORWARD 29 · RECONSTRUCTED 9** (zero UNKNOWN) |
| Sources | **59** — `replay_observation 33`, `paper_trade 13`, `transcript 12`, `journal_entry 1` |
| — cited by observations | 17 (42 uncited → the 30+1 genuine orphan warnings) |
| Packages recovered from the live store | **41**, `verified 41`, `mismatched 0`, `uniqueSourceTradeIds 41` |
| Manifest-only identities | **222 of 263 (84%)** — packages aged out of the WAL, recoverable nowhere else |
| Preservation ledger | 39 rows; `closedTotal 39`, `closedReal 35`, `closedDeveloperTest 4`, rollup present |

### Count reconciliations — stated, not silently smoothed

- **263 identities vs 259 observations.** Difference is exactly the **4 developer test trades**, which
  the importer refuses by policy and which are recorded with `refusedByImportPolicy: true`.
- **13 `HISTORICAL_BACKFILL` identities vs 9 RECONSTRUCTED observations.** The 4 refused developer
  trades are all `HISTORICAL_BACKFILL`. 13 − 4 = 9. Consistent.
- **41 packages in the live store vs 263 identities.** The store holds only what has not yet been
  compacted out of the WAL. All 41 are covered by the manifest; the other 222 survive **only** there.
- **Ledger 39 rows vs 35 joining observations.** The 4 non-joining rows are the same developer trades.
- **2 observations carry `strategyId: current_strategy`** (`TOBS|MOGO|20260806|025`,
  `TOBS|MOGO|20260818|001`) rather than `alex_g_sr_v1`, and **2 carry no `timeframe`**. Pre-existing,
  outside B-32's scope, not repaired. **Flagged for MOGO-023 diagnosis** — do not bulk-rewrite them.

### Instruments / timeframes observed in the corpus (evidence, not live config)

`GBP/CHF 27 · GBP/CAD 27 · USD/JPY 27 · GBP/USD 26 · EUR/JPY 25 · USD/CHF 22 · USD/CAD 22 ·
AUD/USD 22 · NZD/USD 21 · AUD/JPY 20 · GBP/JPY 16 · EUR/USD 4` — 12 instruments.
Timeframes: `H1 190 · H4 57 · D 8 · W 2 · (none) 2`.

**UNVERIFIED:** the live instance's *configured* instrument/timeframe set. The above is what the
preserved corpus contains, which is not necessarily what is currently configured. Verify with
`node scripts/mogo_observation_coverage.js --store <checkpoint>`.

---

## 6. FORWARD PAPER

### Is it running?

**Yes — with the qualification below.**

- Google Chrome is running (PID `80349`, up since Mon 08:00, 801 CPU-minutes).
- The MOGO origin store lives at
  `~/Library/Application Support/Google/Chrome/Profile 2/IndexedDB/https_joemogo.github.io_0.indexeddb.leveldb`
  and its directory **mtime is `Aug 21 18:16`** — *after* the 17:53 EDT checkpoint, i.e. the origin is
  being actively written.
- A checkpoint taken minutes ago recovered **41 hash-verified packages, 0 mismatched**.

**UNVERIFIED:** that the MOGO tab is *actively evaluating setups this minute*. CDP is **not** exposed on
`127.0.0.1:9222` in this session (that port belonged to a separate evidence-campaign Chrome, per prior
context). Liveness above is inferred from store writes, not read from the engine.

### Latest state

- Latest FORWARD close: **`2026-08-19T00:51:19.269Z`** — GBP/JPY, Loss, R = −1.0.
- Latest package `createdAt` in the live store: `2026-08-19T00:51:19.541Z`.
- **No new closes since 2026-08-19** (today is 2026-08-21). Quiet market / no qualifying setups.
  **This is a valid result. Do not manufacture trades.**
- Last capture: `0 fresh`, `0 staged-not-imported`, `4 refused`, `259 → 259 observations`,
  `corpus changed: False`, learning `J_NO_SCIENTIFIC_CHANGE`.

### Evidence B-32 did not disturb it

- Every capture run in this session was a **dry run** except where noted; all reported `0 fresh`.
- Observation count never moved: **259 → 259** at every checkpoint.
- All adversarial work ran in **isolated git worktrees** against **rsynced read-only copies** of
  `evidence/`; the operator profile was never opened by any verifier (INC-004).
- Protected-function drift check: **no drift**, 63 functions + 4 constants byte-identical.

### Restart / recovery if the process stops

MOGO is a browser application; there is no server to restart.

1. Confirm Chrome is running and the MOGO tab is open on its origin (`joemogo.github.io`), **Profile 2**.
2. If the tab was closed: reopen it. The engine rehydrates from IndexedDB — **do not clear site data**.
3. **Before anything else**, preserve: `scripts/forward_capture.sh` (dry run — writes nothing).
4. If it reports fresh closes: `scripts/forward_capture.sh --write`.
5. Verify: `python3 scripts/trader_intelligence/validate_evidence.py` → ERROR 0.

**Never** reset the account, clear journals, alter positions, or restart the engine to "fix" quiet
markets. An operator-initiated shutdown or absence is **known downtime**, recorded as such — not an
engine continuity failure to repair.

**NO LIVE-MONEY AUTHORITY EXISTS. PAPER SIMULATION ONLY.**

---

## 7. STRATEGY GOVERNANCE

Status below is derived from **evidence and protected baselines**, not from file existence.

### ALEX (`alex_g_sr_v1`) — the only strategy producing evidence

- **Implementation:** present in `index.html`; `TRADE_OBSERVATION` records: **257 of 259**.
- **Status:** **PAPER (simulated) — actively trading.** All 29 FORWARD observations are its.
- **Frozen semantics:** covered by the protected-function baseline (63 functions + 4 constants,
  `regression-baseline.json`, app v12.39.3). **No drift.** Changing these requires operator approval
  via the auto-mode governance boundary.
- **Hypothesis registry:** 41 hypotheses, **all educator `ALEX_G`** —
  `currentStatus`: `UNSUPPORTED 19 · COLLECTING 12 · UNRESOLVED 10`;
  `joinStatus`: `LINKED 12 · NOT_IMPLEMENTED 12 · UNSUPPORTED 7 · UNRESOLVED 6 · NOT_EXERCISED 4`.
  `observedResolvedTrades` total 2992. **Zero SUPPORTED. Nothing has met the promotion gate.**
- **Known deficiency:** `alex_g_sr_v1` is MOGO's *implementation* of a published method. Replaying it
  measures the implementation, **not** whether the trader's stated rule holds.

### JVM

- **Implementation:** a registration/scanning framework exists (`index.html` v12.1.0 "JVM REGISTRATION",
  described as *zero behavior change*).
- **Status: RESEARCH / STRUCTURAL ONLY.** `CROSS-STRATEGY-ANALYSIS.md`:
  `externalResearchStatus: not_started`; comparison is **structural only**.
- **Evidence produced: zero observations.** Not paper trading. Not promoted.

### TJR (`tjr_slr`)

- **Implementation:** `TJR_STRATEGY_ID='tjr_slr'`, family registered; `index.html` v12.3.0
  "TJR_SLR PHASE 1: SESSION AND ZONE ENGINE".
- **Status: RESEARCH / PHASE-1 ENGINE ONLY.** **Zero observations.** Not paper trading. Not promoted.
- Metadata authorization on file: `docs/trader-intelligence/authorizations/AUTH-tjr-metadata.json`.
- **Open research value:** TJR-vs-Alex-G on liquidity is recorded as *"the most valuable disagreement
  in the library"* (`XCONTRA|20260728|001` DIRECTIONAL/blocking, `…|002` DEFINITIONAL/material).

### `current_strategy` — anomaly, not a strategy

2 observations carry it. **Flag for MOGO-023 diagnosis**, not bulk repair.

### Promotion state, all lanes

**Nothing is promoted. Nothing is a promotion candidate.** Promotion is an operator governance boundary
requiring a full dossier (evidence, reconstructed rules, UNKNOWNs, sample size, methodology, failure
cases, contamination checks, arguments both ways).

---

## 8. B-32 ARCHITECTURAL LESSONS

### Eight recurring defect categories, in the order the system was forced to learn them

| # | Category | Round | Eliminated by |
|---|---|---|---|
| 1 | Fail-open on an attacker-controlled field | 9–12 | **Systemic** — fail-closed made a table-checked property |
| 2 | Anchor availability (delete what the gate reads) | 9–12 | **Systemic** — `CORPUS_ANCHORS` |
| 3 | Scope-condition laundering (delete what makes the gate *apply*) | 15 | **Systemic** — scope condition removed entirely |
| 4 | Aggregate-vs-identity (append-only enforced on a count) | 13 | **Systemic** — per-identity manifest |
| 5 | Existence-vs-value | 16 | **Systemic** — `ANCHOR_VALUE_BINDINGS` + bind-or-excuse |
| 6 | Intra-record derivability | 17 | **Systemic** — `RECORD_DERIVATIONS` |
| 7 | Corpus-vs-external-witness | 18 | **Systemic** — `PACKAGE_WITNESSES` ↔ importer maps |
| 8 | Absence-vs-silence, at every layer | 19–21 | **Partly systemic** — three separate sites |

**Three of these had their contradicting evidence already committed and read by nothing** — the ledger
`pnl`, the manifest `contentHash`, and the capture packages via `repositoryPath` (a field the validator
was already opening only to call `os.path.exists` on it).

### Individual patches rather than invariants

Category 8 (*absence is not silence*) was repaired at **three separate sites** — package resolution,
witness value, derived field — and each time the next round found the next site. There is still **no
single invariant** asserting "every check reports when it cannot evaluate." **This is the strongest
candidate for MOGO-023.**

### Repairs that exposed or introduced later defects

This is the most important section for the next session.

- **B-32.19's witness** → B-32.20 found `_witness_value` returned bare `None` for two different
  conditions, so stripping `objects` was silent.
- **B-32.20's `nullable` flag** → B-32.21 found it was a *bypass*: a fact about one package became a
  licence covering 262, on the two fields with no other check. It had **zero true positives**.
- **B-32.23's shell repair** → B-32.24 found it pinned by **nothing**; two neutering mutations survived.
- **B-32.24's invariant** → B-32.25 found it scoped to `[A-Z_]*RC`, missing a lowercase `rc` **four
  lines from the top of the file it scans**.
- **B-32.25's scan** → B-32.26 found three more edges (continued lines, quoted `$?`, unexamined captures).

**Pattern: five consecutive repairs landed one commit short of the shape they named.** A fix written
while looking at instance N tends to be scoped to instance N.

### Process weaknesses that caused 20+ rounds

1. **Tests that pinned bypasses as correct.** At least **four** of my own tests asserted that a hole was
   intended behaviour, enshrining it.
2. **Coverage by adjacent effect.** M11, M22 and the `nullable` survivors all passed because a
   *different* check fired. Fixtures must isolate the mechanism under test.
3. **Fixture geometry that made the mechanism unreachable.** The only short fixture had a long's stop
   geometry, so dropping `abs()` was invisible — while **all 127 real shorts** would have errored.
4. **Snapshots doing invariants' jobs.** "Measured: zero collisions across 263 packages" was a corpus
   snapshot; measurement later showed **25** legitimate duplicates.
5. **Documentation asserting properties the code did not have.** ≥6 claims of mine were falsified by
   measurement. Docs are an attack surface.
6. **Gates written but never wired**, or unable to fail — found **six times**.

### What MOGO-023 should investigate rather than blindly refactor

1. **Diagnose first.** Is there a single expressible invariant for "a check that cannot evaluate must
   report"? Measure how many current checks would violate it *before* writing code.
2. **Audit for adjacent-effect coverage**, not more tests: which existing tests still pass when their
   specific mechanism is deleted?
3. **The 2 `current_strategy` observations and 2 missing timeframes** — diagnose provenance; do not
   bulk-rewrite evidence.
4. **B-22** (forward statistics describe the preserved subset, not the account) — the oldest closes
   minted no package. Quantify the gap before claiming any forward figure.
5. **The `main` / `mogo-main` branch divergence** — an operator decision, not a cleanup task.
6. **Do not refactor `validate_evidence.py` for elegance.** It is ~2000 lines and dense, but every
   comment in it is a load-bearing record of a defect that reached `exit 0`. Rewriting it would
   discard the evidence of why each gate exists.

---

## 9. KNOWN LIMITATIONS / BACKLOG

### Integrity / security

- **[Boundary, accepted]** Write-everything adversary: an actor who writes both the observation and a
  matching artifact, or rewrites all anchors consistently, is not caught. No rollup closes it. (SPEC §7.9/§7.12)
- **[P3]** Package witness is perishable; 1 of 259 already unwitnessed. Decay is reported, not prevented.
- **[P3]** `MOGO_IDENTITY_MANIFEST` has no rollup. Deliberate — a rollup would look like protection
  without being any under the same threat model.

### Architecture

- **[P2 — top MOGO-023 candidate]** No single invariant for "a check that cannot evaluate must report."
  Repaired at three sites individually.
- **[P3]** `validate_evidence.py` is very large and dense. **Do not refactor without diagnosis first.**

### Testing

- **[P3]** Coverage-by-adjacent-effect is not systematically audited.
- **[P3]** ~22 historical suites exist only in an ephemeral scratchpad outside the repo and are **not**
  run by `run_all.sh` — a disclosed, pre-existing gap (`docs/KNOWN_ISSUES.md`, `docs/TESTING.md`).

### Runtime / operations

- **[P2]** Forward PAPER depends on a browser tab staying open. No supervision, no alerting; a closed
  tab is silent until the next capture.
- **[P3]** CDP is not currently exposed, so engine state cannot be read without operator action.
- **[P3]** Capture artifacts in `evidence/` are gitignored and perishable — import into
  `docs/trader-intelligence/evidence/` **is** the preservation mechanism.

### Research

- **[P2]** TradingView is **HIGH-VALUE / ACCESS_BLOCKED** — `ClaudeBot` is excluded by robots.txt.
  Treated as dispositive. Reconsider only via operator-supplied evidence, an authorized API, a permitted
  export, or another non-circumventing route. **Never bypass.**
- **[P3]** Human-assisted acquisition queue (HAQ-1…4) awaits optional operator artifacts. No action required.
- **[P3]** Negative results recorded in `NEGATIVE_ACQUISITION_LOG.md` (N-15…N-19); do not re-search
  without new evidence.

### Paper trading

- **[P2 — B-22]** Forward statistics describe the **preserved subset**, not the account. The oldest
  closes minted no evidence package. Every forward figure carries this caveat.
- **[P3]** Balances do **not** chain trade-by-trade — up to 5 concurrent positions; `balanceBefore` is
  stamped at entry, `balanceAfter` at exit. Any test assuming a chain is wrong.

### Strategy-specific

- **[P3]** ALEX: 41 hypotheses, **zero SUPPORTED**; 12 `NOT_IMPLEMENTED`.
- **[P3]** JVM: research-only, `externalResearchStatus: not_started`, no evidence.
- **[P3]** TJR: phase-1 engine only, no evidence, unresolved blocking contradiction with ALEX on liquidity.
- **[P3]** 2 observations carry `strategyId: current_strategy`; 2 carry no `timeframe`.

### Tooling / process

- **[P2 — operator decision]** Remote `main` (`abfc763`) is unrelated to MOGO's history; the real branch
  is `mogo-main`. Do not resolve unilaterally.
- **[P3]** The auto-mode block **decays by standing still** — each section *replaces* shipped defaults
  rather than merging. Re-run the generator after every Claude Code upgrade.

---

## 10. RUNTIME / RECOVERY

### Processes and services

| | |
|---|---|
| Google Chrome | PID `80349` (verify: `ps aux \| grep '[C]hrome'`) |
| MOGO app | Browser tab, origin `joemogo.github.io`, **Chrome "Profile 2"** |
| Servers / daemons | **None.** MOGO is a single-file browser app. |

### Paths

```
Repo          /Users/joemogollon/Desktop/Forex Hub
App           index.html                       (v12.39.3)
Live store    ~/Library/Application Support/Google/Chrome/Profile 2/IndexedDB/
                https_joemogo.github.io_0.indexeddb.leveldb
Checkpoints   ~/MOGO-EVIDENCE-PRESERVED/<UTC stamp>/     (latest 20260821T215346Z)
Raw artifacts evidence/                        (GITIGNORED, perishable, REQUIRED by the witness gate)
Corpus        docs/trader-intelligence/evidence/          (committed — this IS preservation)
Reports       docs/trader-intelligence/evidence/reports/integrity-report.json
              docs/trader-intelligence/graph/reports/integrity-report.json
Research state docs/trader-intelligence/research-state/
```

### Commands

```bash
# Health check — read-only, safe, writes nothing
scripts/forward_capture.sh

# Capture new closes (only if the dry run reports fresh evidence)
scripts/forward_capture.sh --write

# Full canonical gate — must exit 0
bash tests/run_all.sh

# Individual gates
python3 scripts/trader_intelligence/validate_evidence.py
python3 scripts/trader_intelligence/validate_graph.py
python3 scripts/trader_intelligence/observation_graph_reconcile.py
python3 scripts/trader_intelligence/research_assimilation.py     # read-only without --write
python3 tests/count_python_tests.py --check
python3 regression-baseline-tools.py
python3 scripts/auto_mode/build_auto_mode_config.py --check

# Diagnostics
node scripts/mogo_observation_coverage.js --store <checkpoint-store>
python3 scripts/trader_intelligence/forward_coverage.py
python3 scripts/trader_intelligence/identity_manifest.py --packages <file>
```

### Logs

There is no application log file. Authoritative state lives in the two `integrity-report.json` files,
`docs/trader-intelligence/research-state/`, and the capture script's stdout.

### Verifying observation resumes correctly

1. `scripts/forward_capture.sh` → `packagesRecovered > 0`, `verified == packagesRecovered`, `mismatched: 0`.
2. `node scripts/mogo_observation_coverage.js --store <checkpoint-store>` → every configured instrument observed.
3. `python3 scripts/trader_intelligence/validate_evidence.py` → `ERROR: 0`.
4. Distinguish **no trade because no setup** from **no trade because evaluation failed**. Only the second is a defect.

### Verifying paper trading resumes correctly

1. MOGO tab open on its origin, Profile 2.
2. Live store directory mtime advancing.
3. A new close appears as `fresh` in a capture dry run, and imports cleanly with `--write`.
4. Observation count increases and `research_assimilation` reports a corpus change.

### What a fresh Claude session must NOT do

- ❌ Restart MOGO, reset the account, alter positions, clear journals, or clear site data.
- ❌ Manufacture trades or loosen a rule to create activity. **Quiet markets are a valid result.**
- ❌ Run browser verification against the operator's profile or the live origin (**INC-004**) — use
  read-only file copies, and confirm the test origin with the operator every time.
- ❌ `git checkout main` from a fresh clone expecting MOGO, or "fix" the `main`/`mogo-main` divergence.
- ❌ Delete anything under `evidence/` or `~/MOGO-EVIDENCE-PRESERVED/`.
- ❌ Change protected strategy semantics, promote inference to fact, or assert live-money authority.

---

## 11. CLAUDE / TOOLING CONFIGURATION — `~/.claude/settings.json`

### What changed

The `autoMode.soft_deny` section gained **one** shipped default rule:

```
+ Unverifiable Deletion Scope [named+specifics — must name: the exact targets being deleted …]
```

### Verified diff against the backup (measured, not asserted)

```
non-autoMode keys identical : True        (theme, skipDangerousModePermissionPrompt preserved)
environment : 27 -> 27   added=0  removed=0
allow       : 21 -> 21   added=0  removed=0
soft_deny   : 73 -> 74   added=1  removed=0
```

**Zero rules removed. Zero rules reworded. The perimeter is strictly stricter.**

All **11 MOGO governance rules** remain present and intact:
`MOGO Routine Engineering`, `Read-Only Runtime Inspection`, `Evidence Preservation`,
`Evidence Processing`, `Live-Money Capability`, `Protected Strategy Semantics`,
`Inference Promotion`, `Evidence Destruction`, `Production Disturbance`,
`Local History Deletion`, `Documented Governance Boundary`.

### Why

`tests/run_all.sh` failed with
`auto-mode config HAS DRIFTED … soft_deny: 73 installed vs 74 generated; missing: Unverifiable Deletion Scope`.

Each `autoMode` section **replaces** the shipped defaults rather than merging, so every rule a newer
Claude Code ships is silently absent until the generator is re-run. `CLAUDE.md` explicitly instructs
re-running it for exactly this signal. The perimeter had decayed **by standing still** — nothing in the
repo changed.

### Backup

```
~/.claude/settings.json.pre-mogo-automode.20260821T201510Z.bak
```
(3 backups exist in total; the above is the one from this change.)

### Repository-controlled or machine-local?

**Both, by design.** The *source of truth* for MOGO's delta is repository-controlled
(`scripts/auto_mode/mogo_rules.json`); the *installed block* is **machine-local** in the user settings
file, because Claude Code reads `autoMode` only from there. `build_auto_mode_config.py --check` is what
keeps the two honest.

### What the next session must verify independently

```bash
python3 scripts/auto_mode/build_auto_mode_config.py --check    # expect: IN SYNC (27/21/74)
```
If it reports drift after a Claude Code upgrade, **diff before writing**, confirm the change is additive,
then `--write`. **If any MOGO rule would be removed or reworded, STOP and ask the operator.**

---

## 12. MOGO-023 STARTING BOUNDARY

- ✅ **B-32 is CLOSED**, accepted COMPLETE at the milestone boundary.
- ⛔ **MOGO-023 has NOT begun.** No new milestone has been started. No work beyond this handoff was performed.
- 📌 The next milestone is **Stabilization & Architectural Hardening**.
- 🔍 **Diagnosis must precede broad refactoring.** §8 lists what to investigate. `validate_evidence.py`
  is dense *because* each comment records a defect that reached `exit 0` — do not rewrite it for elegance.
- ▶️ **Forward PAPER should remain operating whenever safely possible.** Do not stop it to do engineering.
- 🔒 **Frozen strategy semantics remain protected** — 63 functions + 4 constants, operator approval required.
- 🚫 **NO LIVE-MONEY AUTHORITY EXISTS.** PAPER simulation only.

---

## 13. FRESH-SESSION VERIFICATION CHECKLIST

Verify this document against reality rather than trusting it.

```bash
cd "/Users/joemogollon/Desktop/Forex Hub"

# 1. Repository authority
git rev-parse HEAD                       # expect b23085f03d18f9e32607b678bed653302c573aee
git status --porcelain                   # expect empty
git rev-list --left-right --count @{u}...HEAD   # expect 0  0
git ls-remote --heads origin             # confirm mogo-main == HEAD; main is UNRELATED (abfc763)

# 2. Gates
bash tests/run_all.sh                    # expect exit 0
#    expect: 1417 Python tests OK; 2386 fixtures / 0 failed;
#            evidence {0,2,0,0}; graph {0,31,0,0}; acquisition {0,0,0,0};
#            no protected drift; auto-mode IN SYNC (27/21/74)

# 3. Populations
python3 - <<'PY'
import json,glob,collections,sys
sys.path.insert(0,"scripts/trader_intelligence"); import trade_observation as to
R="docs/trader-intelligence/evidence"
obs=[json.load(open(p)) for p in glob.glob(f"{R}/observations/**/*.json",recursive=True)]
srcs={s["sourceId"]:s for s in (json.load(open(p)) for p in glob.glob(f"{R}/sources/**/*.json",recursive=True))}
ids=json.load(open(f"{R}/ledger-preservation/MOGO_IDENTITY_MANIFEST.json"))["identities"]
known={i["tradeId"] for i in ids}
print("identities",len(ids),"requirable",sum(1 for i in ids if not i.get("refusedByImportPolicy")))
print("observations",len(obs),"anchored",sum(1 for o in obs if o.get("sequenceId") in known))
print("populations",dict(collections.Counter(to.observation_population(o,srcs) for o in obs)))
PY
# expect: identities 263 requirable 259 | observations 259 anchored 259
#         populations {'HISTORICAL':221,'FORWARD':29,'RECONSTRUCTED':9}

# 4. Forward PAPER (read-only; writes nothing)
scripts/forward_capture.sh
# expect: packagesRecovered==verified, mismatched 0, 4 refused, 259 -> 259

# 5. Governance perimeter
python3 scripts/auto_mode/build_auto_mode_config.py --check    # expect IN SYNC (27/21/74)
```

**Then, before any work:** read `CLAUDE.md`, `docs/trader-intelligence/SPEC-provenance.md` §7.9–§7.20,
and `POST_MOGO_021_HARDENING_BACKLOG.md` (B-32.12 → B-32.26).

**If any check disagrees with this document, trust the repository and investigate.** That rule found
every defect in this campaign.

# ALEX forward-PAPER path — read-only diagnosis

**Scope.** ALEX `B_breakRetest` live paper path only. JVM is a separate strategy with separate
enablement and is not diagnosed here. Nothing was executed in the operator's browser, no storage
was inspected, no evidence corpus was read, nothing was enabled, opened or closed.
**Paper-trading readiness: not assessed.** Nothing below establishes it.

Basis: published `612c2ff` (`codex/lean-production-emitter-v2`), cross-checked against
`origin/mogo-main` `6468dc4`.

---

## Answer

The ALEX paper-trading problem, **as far as the repository artifacts can decide it, is an
intentional gate that is currently latched shut by a stale artifact — not a code defect and not
incomplete integration.** One blocker is confirmed present in the committed artifacts today; the
remaining candidate causes are store- or runtime-derived and cannot be decided from source.

### CONFIRMED (source-proven, executed offline)

`toggleAlexGLiveTrading()` runs `evidenceForwardPaperPreflight()` on the OFF→ON transition only,
and returns without setting `alexGAutoTrading.enabled` unless `verdict.pass` is true
(`index.html:6060`). `evidenceEvaluateForwardPaperGate` adds the blocker `CAMPAIGN_C1` whenever
`facts.campaignC1Intact !== true` — an unconditional term with no exception path.

`evidenceEvaluateCampaignC1Attestation` marks `STALE_ATTESTATION` when the attestation's
`generatedAt` is more than `EVIDENCE_C1_ATTESTATION_MAX_AGE_MS` (24 h) behind the browser clock.

The committed attestation, identical on `612c2ff` and on `origin/mogo-main`, is:

```
docs/campaigns/C1/C1_INTEGRITY_ATTESTATION.json
generatedAt   2026-08-24T23:02:14.350Z      (last regenerated in f222d9d, 2026-08-24)
verdict       VERIFIED
manifestSha   c23e72e0…  == EVIDENCE_C1_MANIFEST_SHA256 pinned in index.html
```

Running the app's own two policy functions — extracted verbatim from `index.html` and executed in
a bare VM realm, not reimplemented — over that file:

```
$ node scripts/alexg_paper_activation_probe.js
attestation age    : 212.62 h (policy max 24 h)
campaign C1 intact : false
campaign C1 reasons: STALE_ATTESTATION
C1 blocks OFF->ON  : true
```

Positive control at `--at 2026-08-25T00:02:14.350Z` (1 h after generation) returns `intact: true`
with no reasons, so the refusal is attributable to age alone. **Staleness is the *only* failing
C1 condition**: attestation version, pinned manifest hash, `VERIFIED` verdict, artifact counts and
the three contradiction lists all pass.

**Consequence, stated with its two assumptions.** *If* the operator's serving origin returns this
checkout's attestation file, *and* the browser clock is roughly correct, then the OFF→ON toggle
refuses — blockers are additive, so `CAMPAIGN_C1` alone makes `pass` false regardless of how the
store-derived facts turn out. Neither assumption is verifiable from here; question (1) below
settles both at once, since the alert prints every blocker code. Under those assumptions the
refusal persists until the C1 attestation is regenerated (`scripts/mogo_evidence_verify.js`,
operator-authorized) and served, and it re-arms 24 hours after each regeneration. That is the gate working as written — MOGO-011 Phase A deliberately made
C1 integrity a hard, non-exceptable term — but its practical effect is that activation is
available only within a 24-hour window after an attestation build.

### The gate is asymmetric — this is what discriminates the two symptoms

The preflight is inside `if(turningOn)`. Turning OFF is never gated, and **an already-enabled ALEX
is never re-checked**: `alexGLivePollTick` does not consult the preflight. So:

| Operator symptom | Implicated gate | Category |
|---|---|---|
| Toggle refuses with an `⛔ EVIDENCE PREFLIGHT FAILED` alert listing `CAMPAIGN_C1` | stale attestation, confirmed above | intentional gate, currently latched |
| Toggle refuses listing `STORE_READ_UNCONFIRMED` / `MISSING_IDENTITY` / `AMBIGUOUS_IDENTITY` / `HASH_MISMATCH` / `UNCONFIRMED` / `INCOMPLETE_VERIFICATION` | evidence corpus state in operator IndexedDB | intentional gate, corpus-driven |
| Toggle refuses with `⛔ EVIDENCE PREFLIGHT ERROR` | preflight threw; fail-closed by design (M-8) | intentional gate |
| ALEX is **ON**, but no positions ever open | the per-tick chain below | undecidable from source |

### NOT DECIDABLE FROM SOURCE (needs runtime evidence)

If ALEX is already ON and still not trading, every remaining cause is a state fact, not a source
fact. Each one already leaves a durable trace, which is what makes a single operator summary
sufficient:

| Cause | Where it is already recorded |
|---|---|
| Poll not running at all | no `POLL` observation rows |
| Poll running but disabled | `POLL` row, `outcome: SKIPPED_DISABLED`, `tradingEnabled: false` |
| No new H1 bar yet for a pair | `instrumentsSkipped[].reason` absent, `currentH1Boundary <= lastEvaluatedH1` |
| Evaluation cursor dated ahead of the clock (instrument held out deliberately) | `ENGINE_ERROR` / `STATE_CURSOR_AHEAD_OF_CLOCK`, and `cursorAheadOfClock: true` on the skip record |
| Instrument never reached this tick | `instrumentsSkipped[].reason: NOT_REACHED_THIS_TICK` |
| Higher-timeframe data incomplete | `instrumentsSkipped[].incompleteTimeframes`, pipeline stage `DATA_INSUFFICIENT` |
| Setup pre-dates activation cutoff | `alexGIsSetupEligibleForLiveTrading` false — setup never reaches the attempt path |
| Setup aged past its bar-period | `alexGIsSetupSignalStale` — `signalAgeMinutesAtEvaluation` on the status record |
| Already decided under a durable identity | construction `DUPLICATE` → `CANDIDATE_REJECTED` / `STATE_SIGNAL_ALREADY_DECIDED` |
| Construction refusal (existing position, entry-day rule, price moved, sizing) | `TRADE_OPEN_FAILED` with the constructor's own `status` + `reason` |
| Risk geometry below `MIN_RISK_PIPS` | `TRADE_OPEN_FAILED` / `RISK_GEOMETRY_CONTRACT_VIOLATION` |
| Ledger commit refused | `commitAlexGLedger()` `{ok:false, reason}`; the position is rolled back |

**No defect was found in any of these paths.** Absence of a found defect is not proof of absence.

### Side effects — read before invoking anything that sounds read-only

`evidenceForwardPaperPreflight()` is **not** side-effect-free, despite the name:

- it issues a network `fetch` of the attestation from the serving origin (`cache: 'no-store'`);
- it reads every evidence package and recomputes every content hash — proportional to corpus size;
- on a store-list failure it calls `evidenceRecordWriteFailure('preflight-list', …)`, which
  **mutates** `evidenceWriteFailures`, may set a critical `evidenceStorageBanner`, calls
  `recordAlexGEngineError`, and emits a `DATA_UNAVAILABLE` decision event.

It must therefore not be invoked casually against the running instance to "just check". The probe
added here exists precisely so the C1 half can be answered without invoking it.

---

## The one runtime question that would close this

Everything above is decided except which branch the running instance is actually in. One
sanitized operator summary answers it; no raw market data, credentials, evidence files or trade
records are needed:

1. **Toggle behaviour** — with ALEX OFF, pressing the toggle: does an `⛔ EVIDENCE PREFLIGHT
   FAILED` alert appear, and which blocker `code:` lines does it list? (The codes only, not the
   detail text.)
2. **Enablement** — is ALEX currently ON or OFF, and is the ALEX panel showing an activation time?
3. **Latest refusal** — the most recent ALEX live setup status entry's `status` and `reason`
   strings, with pair/timeframe. Strings only.
4. **Ledger** — does the ALEX panel report a ledger commit failure, and if so its `reason`?

If (1) lists `CAMPAIGN_C1`, this diagnosis is complete and the action is a C1 attestation
regeneration, which is an operator governance decision, not a code change.

---

## Tooling added

`scripts/alexg_paper_activation_probe.js` — read-only. Extracts
`evidenceEvaluateCampaignC1Attestation` and `evidenceEvaluateForwardPaperGate` verbatim from
`index.html` by brace balance, executes them in a bare VM realm with the real pinned constants,
and reports whether campaign C1 would block activation and why. Refuses loudly if a declaration is
missing or non-unique, so it cannot drift into describing a policy that no longer exists. It
never evaluates the store-derived facts and never claims the preflight passes. `--at <ISO>` for a
controlled clock, `--json` for machine output.

## Limitations

- The operator's serving origin may not serve this checkout's attestation file; the browser clock
  is its own. Both are assumptions this probe cannot verify.
- Only the campaign-C1 half of the gate is evaluated offline, by construction.
- No protected strategy function or constant was read into a decision, edited, or executed against
  real data. No runtime source changed. Nothing was enabled, installed, merged or published.

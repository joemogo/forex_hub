# MOGO-004 Step 1 Pilot — Execution Blocked

**Prepared:** 2026-08-04 · **Repository HEAD:** `bb8498f` · **Engine:** `APP_VERSION` 12.18.0
**Authority received:** one replay run, `alex_g_sr_v1`, EUR_USD, PRE-REG-001 pilot parameters, current engine, isolated profile.
**Replay runs executed:** **ZERO.** **Code modified:** none. **Campaign C1:** not begun.

---

## 0. Why this is not the Step 1 Pilot Report you asked for

**The pilot did not execute.** Three preconditions are unsatisfiable by me acting alone, and each
requires you specifically. A Step 1 Pilot Report requires pilot evidence; no pilot evidence exists,
so producing one would mean inventing its contents.

Two of the three blockers are not obstacles to route around — **they are the controls written after
INC-004 destroyed your real ALEX and JVM paper-trading data.** Working around them is precisely the
failure mode they exist to prevent.

I have completed all preparatory work that does not depend on your answers (§4), and it is good news:
**the engine is verified ready.** The blockers are access and authorization, not engineering.

---

## 1. Blocker 1 — the test origin is unconfirmed 🔴

**Status: HARD STOP. Rule 0.**

`docs/TESTING.md` → Browser Testing Policy → Rule 0, and `scripts/browser_test_profile.sh` GUARD 1:

> **Inferring the origin from a config file.** The origin must be confirmed with the operator.

> `[ -n "$ORIGIN" ] || fail "--origin is required and must never be inferred from a config file (INC-004)."`

Your authorization named the strategy, the pair, the parameters and the engine. **It did not name the
origin,** and I must not choose one.

I know three things about ports, and none of them yields an answer:

| Port | Status | Source |
|---|---|---|
| `8744` | **REFUSED** — your live MOGO origin; INC-004 destroyed data here | denylist, GUARD 1b |
| `8899` | **REFUSED** — contaminated; holds INC-005 `AGT\|MANUAL-B\|1`, balance reads 10200 | denylist, GUARD 1b |
| `8743` | Named in `.claude/launch.json` — **and nothing has ever served on it** | `launch.json` `_comment` |

`launch.json` carries an explicit warning that reading an origin out of it **is the proven root cause
of INC-004**. So the one port I could "find" is the one file I am specifically forbidden to read it
from.

> **The absence of a port from the denylist proves nothing.** INC-004 happened on exactly that
> reasoning: 8744 was assumed isolated *because it differed from the port in the config file*. I will
> not repeat that inference. **I need you to name the port.**

---

## 2. Blocker 2 — no OANDA credential exists in a disposable profile 🔴

**Status: HARD STOP. Structural.**

Replay is not offline. `fetchCandlesRange` (`index.html:5937`) makes authenticated live calls:

```js
r = await fetch(url, { headers: { 'Authorization': `Bearer ${cfg.key}` … } });
```

And the credential starts empty on every fresh load (`index.html:2077`):

```js
let cfg = { key:'', accountId:'', env:'practice' };
```

`cfg.key` is populated only by the connect screen at `index.html:5769`. **Rule 0 mandates a freshly
created, verifiably empty profile** — `browser_test_profile.sh` GUARD 4 fails closed unless the
profile contains zero entries. A profile that is provably empty **provably has no OANDA token.**

So the pilot requires a credential that the mandated isolation guarantees will be absent. **This is
not a defect** — it is the correct interaction of two correct controls. It simply means the connect
step cannot happen without you.

> **I am not asking you to send me your API token, and you should not paste it into this
> conversation.** The correct resolution is that **you** enter it directly into the isolated browser
> window. I never see it, and it dies with the disposable profile.

Note also `apiBase()` (`index.html:5941`): `env` must remain `practice`
(`https://api-fxpractice.oanda.com`). The pilot is practice-data retrieval only, no writes.

---

## 3. Blocker 3 — the isolation control and the automation tooling are mutually exclusive 🔴

**Status: HARD STOP. Structural. This one is not obvious, so it is spelled out.**

The two facts collide:

1. **The mandated profile cannot be automated by me.** `browser_test_profile.sh` GUARD 3/4 creates a
   *fresh, uniquely-named, verifiably empty* `--user-data-dir` under a temp directory. A brand-new
   Chrome profile **has no extensions installed** — including the Claude-in-Chrome extension. I have
   no channel into that window.
2. **The window I *can* automate is the one I am forbidden to touch.** The Claude-in-Chrome tools
   attach to your own Chrome, where the extension lives. `TESTING.md`, *ABSOLUTELY PROHIBITED*:

   > Reusing an existing Chrome window, tab, browsing context, or MOGO session

   That is your profile. Rule 0: *"Browser testing NEVER attaches to, reuses, inspects, modifies, or
   clears the operator's Chrome profile. Ever. Under any circumstance. There is no exception, and no
   result is worth one."*

**I therefore did not call any browser tool at all — not even to list tabs.** Rule 0 names *inspects*
alongside *modifies*, and the ordinary way to "just check which Chrome is connected" would itself be
an inspection of your profile. That check is exactly the reflex INC-004 punished.

`TESTING.md` anticipates this precise situation and names the remedy:

> if a hard stop is wanted, remove the browser automation tools from the session's permitted-tool
> configuration

**Consequence: the pilot is operator-driven.** I can prepare it completely, tell you exactly what to
do, and verify every artifact afterward with the same rigour I applied to RUN-001 — but the keystrokes
in the isolated window must be yours.

---

## 4. What I verified while blocked — the engine is ready ✅

None of this required the browser, and all of it de-risks the run.

### 4.1 Full offline regression — clean

```
Suites run:       17
Fixtures run:     944
Passed:           944
Failed:           0
Execution errors: 0

Protected-function / protected-constant drift check
Known-good hash match: True
No drift: all 63 protected functions and 4 protected constants are byte-identical.
```

Engine `APP_VERSION` **12.18.0**, the current engine PRE-REG-001 §6 requires.

### 4.2 The three gate fields are wired to the REPLAY path — traced, not assumed

This was the real risk: that the capture units only ever fed the *live* path, so the pilot would fail
the gate for a structural reason. **They do not.** I traced each from its producer to the package:

| Gate field | Unit | Producer | Reaches the package via |
|---|---|---|---|
| `triggeredConditions` | B (12.11.0) | attribution mirror, `index.html:12694` | `:13184` → `qualifiedSetups[]` |
| `timeToMFE` / `timeToMAE` | C1 (12.12.0) | `evidenceRecomputeExcursionTiming`, `:12819` | `:13251` → `outcomes[]` |
| `marketContexts` | C2-M1/M2 (12.13.0/12.14.0) | `evidenceBuildMarketContext`, `:13718` | `:13729` → `objects.marketContexts` |

All three converge on `evidenceNormalizeReplayTrade(trade, run, setup, breakCycleSetupCount,
excursionTiming, marketContext)` (`:13600`), called from the replay capture loop at `:13729`. The seam
is reached from `runAlexGReplayUI` (`:4131`), which is **not** a protected function and runs
fire-and-forget after results are already assigned.

**Assessment: the gate has a genuine chance of passing.** That is the whole point of running it — and
equally, three honest ways it can still fail, which are exactly what the pilot is for:

- Excursion timing emits **only if** the recomputed MAE/MFE match the engine's stored values exactly;
  on mismatch, timing is omitted, `EXCURSION_RECOMPUTATION_MISMATCH` is flagged, and the package is
  still written.
- Unit B **fails capture closed**: a proven attribution contradiction throws
  `EVIDENCE_RULE_ATTRIBUTION_MISMATCH` and **no package is written**.
- Market context depends on `candlesByTimeframe` surviving into the seam; a `null` there yields
  `marketContext = null` silently.

None of these is knowable without a real run. **That is why the pilot exists.**

### 4.3 The rejection record is capturable in full

`runAlexGReplayUI:4119` assigns `alexGReplayRejected = result.rejected` — the full array, in memory,
after the run. PRE-REG-001 §9 requires it saved per setup with reason, and the RUN-001 gap identified
in the Step 1 Completion Report (§6) **is avoidable this time**. The extraction step is in the runbook
below and must not be skipped.

### 4.4 Isolation launcher — reviewed, fail-closed confirmed

`scripts/browser_test_profile.sh` verified sound: GUARD 1 (explicit origin), 1b (denylist 8744/8899),
2 (never inside your Chrome directory), 3 (fresh, never reused), 4 (proven empty), 5 (writes the
four-fact isolation manifest). It refuses to launch anything it cannot positively verify. **I did not
run it** — it takes the origin I do not have.

---

## 5. Gate evaluation — formally, not yet possible

The report you asked for requires these answers. Each is **UNEVALUATED**, and none may be guessed:

| Gate requirement | Status |
|---|---|
| `triggeredConditions` populated | ⬜ **UNEVALUATED** — no pilot evidence exists |
| `timeToMFE` populated | ⬜ **UNEVALUATED** |
| `timeToMAE` populated | ⬜ **UNEVALUATED** |
| Market context populated | ⬜ **UNEVALUATED** |
| New `runId` / `configHash` / `paramsHash` / `datasetHash` | ⬜ **UNEVALUATED** |
| Packages hash-verified | ⬜ **UNEVALUATED** |
| Complete `alexGReplayRejected` captured | ⬜ **UNEVALUATED** |
| **Sufficient to authorize Campaign C1** | ⬜ **NO — and not because it failed. Because it has not run.** |

**Defects found: none.** No defect in strategy logic, the evidence layer, or the engine was found —
so the clause permitting me to modify strategy logic to complete the pilot **was never triggered, and
nothing was changed.** The blockers are access and authorization.

---

## 6. Operator runbook — the pilot, ready to execute

Everything below is prepared. It needs your port, your token, and about fifteen minutes.

**Step 1 — Serve the app on a port you confirm.** From `~/Desktop/Forex Hub`:
```bash
python3 -m http.server <PORT>
```
Must not be `8744` or `8899`. Tell me the port; I will not choose it.

**Step 2 — Launch the isolated profile.** Fails closed if isolation cannot be verified:
```bash
scripts/browser_test_profile.sh --origin http://localhost:<PORT> --launch
```
It prints the isolation manifest — profile path, origin, not-operator-profile confirmation, empty
pre-clear inventory. **Keep that manifest; PRE-REG-001 §8 requires it as run evidence.**

**Step 3 — Connect (yours alone).** In the *disposable* window, enter your OANDA **practice**
credentials. Confirm the environment reads `practice`. Do not send the token to me.

**Step 4 — Run exactly one replay.** ALEX G → Replay: pair **EUR_USD**, days **90**, ambiguous mode
**conservative**. These are the PRE-REG-001 pilot parameters, and they reproduce RUN-001's
`paramsHash` — spread `none`, fixed spread `0`, slippage `0`, start balance `10,000` are hardcoded at
`index.html:4104`. Press **Run Alex G Replay** **once**. Expect ~24 trades.

**Step 5 — Capture the rejection record in full.** ⚠️ **The step RUN-001 missed.** In that window's
console, *before navigating away*:
```js
copy(JSON.stringify(alexGReplayRejected, null, 2))
```
Save as `RUN-REJECTED-full.json`. Aggregates are not acceptable — §9 requires every record.

**Step 6 — Export packages + harvest**, then save everything to a **new** directory alongside the
RUN-001 evidence — not into it. The new run has a different `runId` and must not be commingled.

**Step 7 — Tell me it is done.** I will then verify every package independently exactly as I did for
RUN-001 — clean-room canonicalization, hash verification, full identity-chain recomputation — evaluate
the gate against the pilot evidence only, and produce the Step 1 Pilot Report.

---

## 7. Decision gate — your call

**Question 1 — What is the test origin?** Required by Rule 0, cannot be inferred. Nothing proceeds
without it.

**Question 2 — How should the pilot be driven?**

- **(a) You drive it, I verify.** The runbook above. **Recommended** — fully compliant with Rule 0, no
  deviation, no new tooling. You keep sole custody of your credential.
- **(b) Grant a documented, one-time deviation** allowing browser automation against a non-operator
  profile. This needs a concrete mechanism, is a real weakening of the post-INC-004 control, and I
  would want it recorded as an amendment rather than a verbal exception.
- **(c) Defer the pilot.** Legitimate. Nothing degrades; RUN-001 stays authoritative and C1 stays
  blocked.

### Standing constraints, unchanged

- **Campaign C1 not begun** and will not be until a pilot passes its gate and you approve.
- **No code modified.** No feature implemented. No strategy logic touched.
- **No browser tool was invoked** — see §3.
- **No hypothesis adjudicated.** PRE-REG-001 §7 permits adjudication once, after the declared runs; zero have completed.
- RZR remains suspended. No strategy is approved for live execution.

---

**The engine is ready and the gate is genuinely live — it can pass or fail on the evidence. What is
missing is a port I must not guess and a credential I must never hold. Both are yours, and that is by
design: they are the two controls standing between this pilot and a repeat of INC-004.**

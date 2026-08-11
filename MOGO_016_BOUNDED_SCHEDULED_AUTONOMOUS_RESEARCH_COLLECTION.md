# MOGO-016 — Bounded Scheduled Autonomous Research Collection

**Date:** 2026-08-11 · **Starting HEAD:** `28b838fb76014dc3ff59d0a5886b5e843a8f67ca`
**PAPER TRADING ONLY — live-money trading remains unauthorized.**

---

## Starting repository state — verified, not assumed

| | |
|---|---|
| Repository | `/Users/joemogollon/Desktop/Forex Hub` |
| Branch / HEAD | `main` · `28b838f` — matches the stated MOGO-015 closeout exactly |
| Working tree | clean (`git status --porcelain` empty) |
| Sync | **0 ahead / 0 behind** `origin/mogo-main` |
| Platform suite at start | **784 tests · 0 failures · 0 errors** (19 suites) |

No legitimate difference to explain. The starting state is exactly as declared.

---

# STEP 1 — READ-ONLY SCHEDULING READINESS AUDIT

Recorded before any code or host configuration changed.

## 1. The exact command required to dispatch the approved acquisition

`research.acquire.approved-source-metadata.v1` is registered as
`CAP|research|acquire-approved-source-metadata`, accepts `AcquireSourceMetadata` v1,
and is dispatched by an envelope that must carry:

| Field | Required value | Why |
|---|---|---|
| `targetCapability` | `CAP\|research\|acquire-approved-source-metadata` | registry dispatch authority |
| `commandType` / `commandVersion` | `AcquireSourceMetadata` / `1` | manifest `compatibility` |
| `inputRefs` | **exactly one** `SRC\|…` reference | `_subject_source()` denies on zero or two |
| `payload.sourceId` | `SRC\|youtube\|c785970cc458` | the one entry in `APPROVED_DESTINATIONS` |
| `payload.resourceId` | 11 chars, pinned alphabet | substituted into the derived URL |
| `payload.authorizationId` | `96fc2793-b13b-467a-89a8-f31a76ec6d4c` | the governance record |
| `issuedBy` | `orchestrator` \| `operator:<id>` \| `workflow:<type>` | Catalog section A |

**The caller never supplies a URL.** `connector_authorization.derive_destination()` is the
only place a destination comes into existence, and it is keyed on source identity.

## 2. Command identity across repeated scheduled invocations — the decisive finding

Catalog section I pins metadata acquisition to `(sourceId, connectorVersion)`. Both parts are
**constant** for this source, so a scheduler that re-submits the identical semantic command
produces an **identical idempotency key every time** and is `DUPLICATE SUPPRESSED` at the
command layer forever after the first run.

That is correct contract behaviour — section I's duplicate rule for metadata acquisition is
literally *"return cached"* — but it means a naive fixed command file would collect **once**
and then never again. A schedule interval would be meaningless.

The distinguishing semantic input for a recurring collector is the **collection occasion**, and
the Catalog already treats a `window` as a legitimate semantic key part (`Source discovery` →
`(connectorId, query, window)`). MOGO-016 therefore composes the scheduled request identity over
a bounded **collection window** — see the architecture section below. Constitution section 11's
prohibition is on *timestamps and attempt numbers*; a window bucket is neither, and the Catalog
itself sets the precedent.

## 3. Overlap prevention — two independent guards, both pre-existing

1. **`fcntl.flock(LOCK_EX | LOCK_NB)`** on `<state root>/runtime.lock`, held for the whole run
   (`runtime/store.py`). A second concurrent runtime gets `RuntimeBusyError` → **exit code 5**.
   No corruption, no partial write, no second acquisition.
2. **launchd itself**: `man launchd.plist` on this host, `StartInterval` — *"If the job is
   running during an interval firing, that interval firing will likewise be missed."*

Nothing new was needed for overlap.

## 4. Bounded retries and failure audit — already in force

`DEFAULT_ATTEMPT_LIMIT = 3`, runtime ceiling `MAX_ATTEMPT_LIMIT = 10` (`runtime/retry.py`);
the acquisition manifest declares no override, so it inherits the bounded default. The
transport classifies transient (connection failure, timeout, 429, 5xx) from permanent
(authorization denial, other 4xx, oversized, wrong content type, malformed body, redirect) and
the capability preserves that classification verbatim. Failures land in the append-only event
log and are reported by `mogo_runtime failures` / `audit` / `policy`.

## 5. `acquisition_authorization_record` — analysed, not rationalised

**What it is.** `CONNECTOR_GATES` in `runtime/registry.py` is a **declared disclosure table**,
printed by `status` and `failures` so an operator can see what MOGO is not yet allowed to do
*without reading code*. Grep confirms its only consumers are `runtime/audit.py` (three report
builders) and the tests that pin it. **It is not an enforcement point** — enforcement of
authorization lives in `policy.py` + `authorizations.py` + `connector_authorization.py`, and
`unmet_a5_preconditions()` reads `A5_EFFECTFUL_GATE`, not this table.

**Its stated requirement:** *"one governance-supplied authorization record per real source; the
mechanism exists, the records do not."*

**The evidence:**

| Claim in the gate | Repository fact |
|---|---|
| "the mechanism exists" | ✅ `authorizations.py` — validate → append-only register → per-source `resolve()` |
| "the records do not" | ❌ **false since MOGO-015 Step 4** — `docs/trader-intelligence/authorizations/AUTH-fxalexg-metadata.json` exists |
| "per real source" | ✅ one real source is approved (`SRC\|youtube\|c785970cc458`); it has exactly one record |
| decided by a human | ✅ `decisionAuthority: operator:joemogollon`; `PROHIBITED_AUTHORITY_PREFIXES` refuses any automation identity |
| actually enforced | ✅ MOGO-015 Step 4's live acquisition passed `PolicyEvaluated → AcquisitionAuthorized`; the demo scenario proves denial without a record |

**Verdict: (d) incorrectly stale.** The gate asserts a fact that the repository disproves. The
record it says does not exist is the record that authorised MOGO's first real external
acquisition.

**It is *not* a prerequisite for unattended dispatch** — it enforces nothing, so leaving it as
`False` would not block scheduling. But shipping autonomous collection while the operator's own
gate table states something false about authorization is the worse outcome. It is corrected in
Step 2 as a **disclosure correctness fix**, with the enforcement re-proved rather than assumed,
and the gate's `requires` text rewritten so it stops describing a world that no longer exists.

## 6. Existing scheduler — none, confirmed on the host

- `launchctl list | grep -iE 'mogo|forex'` → **no jobs**.
- `~/Library/LaunchAgents/` → five unrelated third-party agents (Google, Steam, iMazing).
- No `crontab`, no in-process scheduler. `retry._schedule_retry` is backoff, not scheduling.

**launchd remains the smallest correct mechanism** and is the native one. No cron.

## 7. Sleep / wake — documented semantics plus this host's own evidence

From `man launchd.plist` on this machine:

- **`StartInterval`** — *"If the system is asleep during the time of the next scheduled interval
  firing, that interval will be missed due to shortcomings in kqueue(3)."* → **missed outright,
  no catch-up.**
- **`StartCalendarInterval`** — *"Unlike cron which skips job invocations when the computer is
  asleep, launchd will start the job the next time the computer wakes up. If multiple intervals
  transpire before the computer is woken, those events will be **coalesced into one event** upon
  wake from sleep."*

**`StartCalendarInterval` is therefore the correct choice**: it gives a deterministic wall-clock
cadence, a single catch-up run after wake, and — by the man page's own words — never a storm of
missed intervals.

**This host's actual sleep record** (`pmset -g log`), which is also the explanation of the
MOGO-015 forward-page finding:

| Time (ET) | Event |
|---|---|
| 14:51:41 | `Sleep` — Idle Sleep, **Using Batt** |
| 14:54:53 | `Sleep` — Maintenance Sleep, Using Batt |
| 16:10:55 | `Sleep` — Maintenance Sleep, Using Batt |
| **17:01:43** | `Wake` — `EC.LidOpen/UserActivity` |

14:51 → 17:01 is **130 minutes**, matching the **127-minute** maximum polling gap MOGO-013's
durable ledger recorded. The forward page's `pageLoaded` moved to `21:02:21Z` = **17:02 ET** —
one minute after the lid-open wake. The reload was caused by the wake, not by MOGO-015.

**A finding the operator should know:** a `caffeinate -dimsu` process (PID 51532) has been
running since 08:25 today holding `PreventSystemSleep`, **and the machine slept anyway** — every
sleep above is stamped `Using Batt`. macOS honours `PreventSystemSleep` on AC power; on battery
it sleeps regardless. The existing caffeine mitigation is therefore **not effective on battery**.
See the host reliability recommendation at the end.

## 8. Environment survival under launchd

| Requirement | Finding |
|---|---|
| Interpreter | platform floor is **Python ≥ 3.14** (pinned by `test_python_3_14_or_newer`). `/usr/local/bin/python3` = **3.14.6**. `/usr/bin/python3` = 3.9.6 — **would fail the floor.** The plist must name the absolute 3.14 path; launchd's default `PATH` must not be trusted. |
| TLS trust | The 3.14 build ships **no CA bundle** (`cafile=None`). `connector_transport.SYSTEM_CA_BUNDLES` points at `/etc/ssl/cert.pem`, which exists (333 KB, root-owned). Verification is explicit and never disabled. |
| Working directory | irrelevant — `mogo_runtime.py`, `paths.default_root()` and `ingest.REPO_ROOT` all resolve from `__file__`. Set anyway, for legible logs. |
| Credentials | **none.** The oEmbed endpoint is public and unauthenticated. **Nothing secret goes in the plist**, and nothing needs to. |
| Clock override | `MOGO_RUNTIME_CLOCK_OVERRIDE` must remain unset; the runtime refuses `--now` without it. |
| State root | default `<repo>/platform/runtime`, git-ignored, currently **uninitialised** — `init` is a one-time operator step. |

## 9. Evidence locations

| Evidence | Location |
|---|---|
| stdout / stderr of every scheduled run | `platform/runtime/logs/scheduled-collection.{out,err}.log` (inside the git-ignored state root) |
| Authoritative event log | `platform/runtime/events/operational-events.jsonl` (append-only) |
| Operator views | `mogo_runtime status` · `audit` · `failures` · `policy` |
| Raw acquired bytes | `docs/trader-intelligence/intake/acquired/<contentHash>.json` |
| Research artifacts | `docs/trader-intelligence/research-artifacts/<contentHash>.json` |

## Audit conclusion

Ready to implement, with **one** design decision forced by the audit (the collection window, §2)
and **one** correction owed (`acquisition_authorization_record`, §5). Everything else —
authorization, idempotency, leases, retries, audit, transport, ingestion, dedupe — is reused
unchanged.

---
---

# STEP 2 — `acquisition_authorization_record` RESOLVED

**Verdict: (d) incorrectly stale. Corrected, with the enforcement re-proved rather than assumed.**

The gate said *"the mechanism exists, the records do not."* The record it says does not exist is
`docs/trader-intelligence/authorizations/AUTH-fxalexg-metadata.json`, created at MOGO-015 Step 4,
decided by `operator:joemogollon`, and used to authorize MOGO's first real external acquisition.
The statement had been false for a whole milestone.

**What was changed:** `satisfied: False → True`, and the `requires` text rewritten from a one-off
milestone that had already happened into the standing obligation the gate actually represents —
*"one governance-supplied authorization record per real source, decided by a human or governance
role, recorded append-only and resolved by the gate before any fetch."*

**What was NOT changed: any enforcement, anywhere.** `CONNECTOR_GATES` is consumed only by
`runtime/audit.py`'s three report builders. It is a **disclosure table**, not a control. Nine tests
in the new suite prove the enforcement behind it is untouched:

- a missing record still denies (`no_authorization_record`)
- an unauthorized operation on the real record still denies (`operation_not_permitted` for
  `transcript`)
- the approved operation is still permitted — so the gate governs rather than always-denying
- the record validates under the real `authorizations.validate_record()`
- its authority is human, and no `PROHIBITED_AUTHORITY_PREFIXES` fragment appears in it
- exactly one real source is approved, and it is the one the record covers

Live confirmation during Step 6: a deliberately unauthorized source, submitted through the ordinary
`submit --command-file` path, still produced `PolicyEvaluated → blocked`, `AcquisitionDenied`,
`HumanReviewRequired → awaiting_review`. **Nothing was acquired.**

The `failures` view's closing sentence was also fixed. It previously named the gates still standing
in the way, which read as nonsense once none remained. It now says what is true in either state, and
when zero gates are unmet it says plainly that this is a disclosure table and that an unauthorized
source is still denied.

---

# STEP 3 — SCHEDULER ARCHITECTURE

```
launchd (StartCalendarInterval)
  └─ /usr/local/bin/python3  platform/mogo_runtime.py  collect
       └─ read the FIXED committed spec  platform/scheduling/approved-collection.json
          └─ scheduled_collection.validate_spec()      ← fail-closed, before a command exists
             └─ build_command()  → one governed envelope, windowed request identity
                └─ orchestrator.submit()  →  run_once()      [ONE process lock]
                   └─ policy → authorization → queue → claim → execute
                      └─ connector gate → permit → bounded transport → raw bytes
                         └─ governed intake → research.ingest.local-artifact.v1
                            └─ content hash → dedupe → durable artifact → audit
```

**Everything below `submit()` is MOGO-011/014/015 code, unchanged.** Scheduling invokes the
machinery; it does not reimplement it.

## Files added

| File | Role |
|---|---|
| `platform/scheduling/approved-collection.json` | the **FIXED approved command** — the only thing the schedule can ask for |
| `platform/scheduling/com.mogo.research.collect.plist.template` | repository-managed launchd template |
| `platform/scheduling/mogo_schedule.sh` | install · disable · status · logs · validate |
| `platform/src/mogo_platform/runtime/scheduled_collection.py` | spec validation + command builder; **no I/O, no clock, no network** |
| `tests/platform/test_runtime_scheduled_collection.py` | 63 focused tests |

`cli.py` gained one subcommand, `collect`. `ids.py` gained one declared idempotency extension.
`registry.py` and `audit.py` carry the gate correction.

## Fixed command identity — no caller-controlled destination at any layer

The spec names a **source** and a **resource**. It has **no field for a URL, host or scheme**, and
an unknown field is *refused, not ignored* — which is how one would arrive. `validate_spec()` then
re-checks the source against the connector's own `APPROVED_DESTINATIONS` and calls
`derive_destination()` to prove the destination derives, **before any command exists**.

The launchd job's arguments are the interpreter, the entry point, and the literal word `collect`.
`collect` accepts no source, URL, resource or capability argument. **There is nothing in the plist
to inject into**, and a test asserts the argument list contains none of `submit`,
`--command-file`, `http` or `youtube`.

| Field | Value |
|---|---|
| capability | `CAP\|research\|acquire-approved-source-metadata` |
| source | `SRC\|youtube\|c785970cc458` (fxalexg, `channel_verified`) |
| resource | `hb7ot1_szWI` |
| authorization | `96fc2793-b13b-467a-89a8-f31a76ec6d4c` |
| operation | `metadata` only |
| `issuedBy` | `workflow:scheduled-research-collection` — **not** `operator:`, because no human is present |

## The collection window — the one design decision the audit forced

Catalog section I keys metadata acquisition on `(sourceId, connectorVersion)`. Both are constant, so
a naive fixed command file would collect **once** and be duplicate-suppressed forever after.

The scheduled request identity is therefore composed over a bounded **collection window** —
`bucket = now_ms // (windowSeconds × 1000)`. Declared in
`ids.IDEMPOTENCY_KEY_EXTENSIONS["scheduled_metadata_acquisition"]` as
`(sourceId, resourceId, connectorVersion, collectionWindow)`.

**It is kept OUT of the Catalog transcription, in a separate named extensions table**, so the
Catalog's ten rows stay diffable against the document and every departure sits in one short,
justified list. The existing pinned test (`len == 10`, exact parts) still passes **unmodified**.

Three properties follow:

1. **Two runs in one window are the same request** — a post-wake catch-up, a duplicate firing and a
   manual kickstart all collapse into one acquisition. The source is not hammered.
2. **The next window is a new request** — collection genuinely recurs.
3. **Request identity is still not content identity** — whether an artifact is created remains
   decided by the SHA-256 of the returned bytes, in the ingestion capability, unchanged.

`resourceId` is included because Catalog section I's row addresses a *source*; ours addresses one
*resource*. Reusing that row would make two different videos collide on one key.

`collectionWindow` is a bucket, not an execution timestamp — Constitution section 11 is satisfied
rather than worked around, and the Catalog itself already treats a `window` as a legitimate semantic
key part in `source_discovery`.

---

# STEP 4 — SCHEDULE, INTERVAL AND JUSTIFICATION

## `StartCalendarInterval`, not `StartInterval`

Chosen on the man page's own words (quoted in §7 of the audit): `StartInterval` **silently drops**
every window missed during sleep; `StartCalendarInterval` starts the job on wake and **coalesces
multiple missed intervals into one event**. One catch-up run, never a storm.

## Interval: every 6 hours — 00:00, 06:00, 12:00, 18:00 local

| Input | Reasoning |
|---|---|
| Source change rate | oEmbed metadata for one published video (title, author, thumbnail) changes rarely, often never. Frequent polling buys almost nothing. |
| Request cost | one 794-byte GET. Cheap for us — which is an argument for restraint, not for volume. |
| Service etiquette | 4 requests/day against a public endpoint is unambiguously polite. An aggressive rate would be indefensible for a source that barely changes. |
| Local reliability | the observed sleep gap was **130 minutes**. A 6-hour cadence absorbs that; at most one window is affected, and `StartCalendarInterval` catches it up. |
| Evidence usefulness | change within a day is detected. Nothing scientific requires finer resolution here. |
| Duplicate avoidance | window == cadence, so each firing gets its own request identity and no firing self-suppresses. |

**The installer refuses an incoherent schedule.** A collection window wider than the cadence
guarantees some firings land in an already-collected window and silently do nothing; that
configuration is rejected at install rather than shipped. Proven in Step 6.

## Environment handling

| | |
|---|---|
| Interpreter | `/usr/local/bin/python3` (3.14.6), named absolutely and **version-checked** at install — launchd's default `PATH` would find the 3.9 system interpreter, which fails the platform floor |
| `PATH` / `LANG` | stated explicitly in the plist, never inherited |
| Working directory | repository root (paths resolve from `__file__` regardless, so this is for legible logs) |
| TLS | the 3.14 build ships no CA bundle; `connector_transport` points at `/etc/ssl/cert.pem` and **fails rather than falling back** to an unverified connection |
| Credentials | **none, and none possible** — the endpoint is public. No secret is in the plist and a test scans the plist body for `password`/`secret`/`token`/`apikey`/`bearer`/`credential` |
| `RunAtLoad` | **false** — a job that fires on install makes "the scheduler triggered this" unprovable |

## Logs and audit evidence

| Evidence | Location |
|---|---|
| stdout / stderr per run | `platform/runtime/logs/scheduled-collection.{out,err}.log` (git-ignored state root) |
| Authoritative event log | `platform/runtime/events/operational-events.jsonl` |
| Operator views | `mogo_runtime status` · `audit` · `failures` · `policy`; `mogo_schedule.sh status` / `logs` |
| Raw acquired bytes | `docs/trader-intelligence/intake/acquired/<contentHash>.json` |
| Research artifacts | `docs/trader-intelligence/research-artifacts/<contentHash>.json` |

## Enable / disable

```bash
# one-time operator setup (deliberately NOT done by the scheduled job)
python3 platform/mogo_runtime.py init
python3 platform/mogo_runtime.py authorize --file \
    docs/trader-intelligence/authorizations/AUTH-fxalexg-metadata.json

platform/scheduling/mogo_schedule.sh validate   # preflight, changes nothing
platform/scheduling/mogo_schedule.sh install    # production schedule
platform/scheduling/mogo_schedule.sh status     # loaded? last run? last exit?
platform/scheduling/mogo_schedule.sh disable    # STOP autonomous collection NOW
```

`disable` takes no arguments, is safe to run when nothing is installed, unloads the job, removes the
plist, and then **verifies** launchd no longer knows it — exiting non-zero if it still does.

The scheduled job deliberately does **not** run `init` or `authorize`. Setup is an operator act, so
a wiped state root fails visibly in the log instead of being silently recreated by an unattended job.

---

# STEP 5 — THE SCHEDULER TRIGGERED A REAL GOVERNED ACQUISITION

**The operator did not submit any acquisition.** The job was installed with `RunAtLoad=false` and
`runs = 0`, then left alone. launchd fired it.

## Proof runs — accelerated schedule

To observe more than one collection window inside the session, the agent was installed with a
**proof schedule** (19:24, 19:26, 19:28 local) and a matching 120-second collection window; the
installer's coherence rule (window ≤ cadence) was satisfied in both configurations. **The mechanism
under test is identical** — only the cadence differs. The production values (6 h / 21600 s) were
restored and reinstalled afterwards, and are what is committed.

### Run 1 — 19:24:07 local · the first autonomous collection

```
COLLECT source=SRC|youtube|c785970cc458 resource=hb7ot1_szWI operation=metadata
        window=W|120|14887422   idempotencyKey=76f9b6f4…
        issuedBy=workflow:scheduled-research-collection
  TaskPolicyCheckRequested → PolicyEvaluated (policy_check → queued)
  AcquisitionAuthorized → TaskClaimed → TaskStarted → TaskSucceeded → WorkflowCompleted
advanced=3 succeeded=1 failed=0 retried=0 released=0 deadLettered=0
```

| | |
|---|---|
| launchd | `runs = 1` · `last exit code = 0` · stderr **empty** |
| Connector decision | **permit** · `connector_destination_permitted` |
| URL (derived, never supplied) | `https://www.youtube.com/oembed?url=…%3Fv%3Dhb7ot1_szWI&format=json` |
| HTTP | **200** · `application/json` · **794 bytes** |
| Content hash | `b668d4209abbf2b8718cea2fa84eacd3985cbb4d1fc352dd1720f64bebb92a00` |
| Raw artifact | `intake/acquired/b668d420….json` |
| Ingestion | `research.ingest.local-artifact.v1` → `validationStatus: VALID`, `storedVerified: true` |
| Dedupe | **`DUPLICATE_ALREADY_INGESTED`** · `ingested: false` · artifact `RART\|d4e4ec829fe80b576a1304f46405f76a` |
| Lane | `RESEARCH` · `promotionStatus: NOT_A_TRADING_RULE` |

The source returned **byte-identical** metadata to MOGO-015's acquisition, so the content hash
matched and **no second scientific artifact was created**. That is the dedupe layer working, not a
failure to acquire — the HTTP 200 and the 794 bytes are real and were fetched by this run.

### Run 2 — 19:26:05 local · a new window, a new request, a real second acquisition

`window=W|120|14887423` · `idempotencyKey=d8363dd2…` — **different from run 1**. New command, new
workflow, new task. Full lifecycle again, `advanced=3 succeeded=1`. `runs = 2`, exit 0.

### Run 3 — 19:28:05 local · `runs = 4`, exit 0, stderr empty

## Same-window suppression — the sleep/wake protection, demonstrated live

An extra invocation at 19:26:21, inside run 2's window:

```
window=W|120|14887423   idempotencyKey=d8363dd2…      ← identical to run 2
DUPLICATE SUPPRESSED existing command=e7629128-… task=880a46f5-…
        same collection window -- no acquisition performed
```

**No socket was opened.** This is exactly what happens when launchd coalesces missed windows on
wake, or when an operator kickstarts the job: one collection occasion, one acquisition.

## Artifact accounting after four scheduler-driven invocations

| | Before | After |
|---|---|---|
| Research artifacts | 2 | **2** |
| Raw acquisitions | 1 | **1** |
| `git status docs/trader-intelligence` | clean | **clean** |

Content addressing means a repeat acquisition of unchanged bytes rewrites the same path with the
same bytes. Three real fetches produced **zero** new files and **zero** content change.

---

# STEP 6 — FAILURE PROOFS

| # | Proof | Result |
|---|---|---|
| 1 | Malformed scheduler configuration is detectable | `plutil -lint` on a truncated plist → **exit 1**, *"Encountered unexpected EOF"*. The installer lints before `mv`, so a malformed plist is never installed. |
| 2 | An incoherent schedule is refused | `validate "00:00,00:05"` with a 21600 s window → **exit 1**, naming the conflict. A schedule that would self-suppress is rejected. |
| 3 | Missing runtime executable fails visibly | wrong entry-point path → **exit 2**, `[Errno 2] No such file or directory` on stderr, captured in the launchd err log. |
| 4 | An unauthorized command/source cannot be scheduled | **6/6 refused before any command existed**: a different educator's source, a smuggled `url` field, `transcript`, a different capability, `../../etc/passwd` as resource id, a forged authorization id. |
| 5 | Overlapping invocation is safe | `collect` run against a held `runtime.lock` → **exit 5 BUSY**, no submission, no acquisition. launchd independently skips a firing while the job runs. |
| 6 | Runtime rejection remains fail-closed | an unauthorized source submitted through the **ordinary** `submit --command-file` path (bypassing the adapter entirely) → `PolicyEvaluated → blocked`, `AcquisitionDenied`, `HumanReviewRequired`. Disposed of by an audited `review --decision rejected`. |
| 7 | Scheduler failure does not corrupt research storage | `verify` → **INTEGRITY OK**; 2 research artifacts, 1 raw acquisition, unchanged. |
| 8 | Scheduler failure does not affect ALEX | `git status` over `docs/trader-intelligence`, `index.html`, `evidence/`, `docs/campaigns`, `docs/strategy-fidelity` → **empty**. |
| 9 | Duplicate content remains deduped | `DUPLICATE_ALREADY_INGESTED`, `ingested: false`, no second artifact — three times. |
| 10 | Disabling stops future autonomous submissions | `disable` → launchd: *"Could not find service … in domain for user gui: 501"*; plist removed. Re-installed afterwards. |

No test spammed the external service: **three** real requests total, all through the governed path.

---

# STEP 7 — INTEGRITY

| Gate | Result |
|---|---|
| Platform suite | **20 suites · 847 tests · 847 passed · 0 failures · 0 errors** |
| Canonical gate (`tests/run_all.sh`) | **18 suites · 1,113 fixtures · 1,113 passed · 0 failed · 0 execution errors** |
| Protected ALEX drift | **0** — 63 protected functions and 4 protected constants byte-identical |
| Campaign C1 | **33 / 33 verified · 0 missing · 0 mismatched · 0 unlisted** · verdict `VERIFIED`, manifest SHA-256 `c23e72e0…` unchanged |
| Legacy corpus | **220 re-derived · 0 mismatched**, rollup `667ff4c7…` matches the committed baseline |
| Runtime | `verify` → INTEGRITY OK; 0 dead letters, 0 retries, 0 leases held, 0 awaiting review |

## Two tests broke, exactly where the design intends them to

The gate flip broke `test_the_connector_gates_are_declared_and_only_the_policy_gate_is_met` and the
`failures`-view assertion — **which is the mechanism working.** `registry.py` states the intent
plainly: a gate is "closed by data, and opening it is loud." Both were updated to assert the new
truth by name, with the reason recorded in the test itself, and the `failures` assertion was
strengthened rather than weakened: it now requires the view to state that all gates being met does
**not** make authorization optional.

The new suite was also added to `tests/run_platform_tests.sh` — a suite the runner does not
enumerate is a suite that does not run.

---

# STEP 8 — FORWARD CAMPAIGN

**The forward browser was not reloaded, not restarted, and not interacted with.** At the operator's
direction, verification was done **read-only from disk**.

A checkpoint of the live profile was taken with `scripts/mogo_evidence_checkpoint.sh`, which copies
and never writes to the source: **source rollup == copy rollup**, status **VERIFIED** — so the store
was not torn mid-write.

| Check | Result |
|---|---|
| Campaign liveness | forward profile IndexedDB and Local Storage **actively written at 19:40–19:42 local**, minutes before the check — the campaign is running and polling |
| Durable ledger | **4.0 MB**, `recordHeadersFound: 2060` — the MOGO-013 ledger is populated and intact |
| **Forward evidence packages** | **0** — `storedPackages: 0`, `uniquePackageIds: 0`. **No research artifact entered the trading lane.** |
| New polling gap this milestone | **none** — `pmset` shows **0** sleep/wake events since the 17:01:43 lid-open wake |
| Reload this milestone | **none.** `LOG.old` in the forward IndexedDB is stamped **17:02** — the MOGO-015 reload, one minute after the 17:01:43 wake. Nothing since. |

## Stated honestly: what this route could NOT verify

The live in-page values — **the ALEX on/off toggle, the activation cutoff literal, and the paper
balance** — sit in the running page and in Snappy-compressed LevelDB SST blocks. Raw byte scanning
found **zero** matches for `2026-08-11T02:43:57.894Z`, `alex`, `10000` or `cutoff` in either store,
and it also found zero matches for `packageId`, which the corpus certainly contains — so the zero is
a limitation of the reading method, not evidence about the values.

**Those three values are therefore reported as UNVERIFIED THIS SESSION, not asserted.** They were
last verified at MOGO-015 closeout (ALEX ON, cutoff `2026-08-11T02:43:57.894Z`, $10,000.00). Nothing
in MOGO-016 touches ALEX, the cutoff, the paper account or the browser, and proof 8 shows no file in
the trading lane changed — but that is an argument from isolation, not a measurement, and it is not
offered as one.

**To close the gap without any risk**, run this in the forward tab's console and compare:

```js
({ alex: window.ALEX_ENABLED ?? '(check the UI toggle)',
   cutoff: localStorage.getItem('mogoForwardActivationCutoff'),
   balance: localStorage.getItem('mogoPaperBalance'),
   pageLoaded: new Date(performance.timeOrigin).toISOString() })
```

## The MOGO-015 sleep/reload finding — now fully explained, and it is a host problem

`pmset -g log` resolves it exactly:

| Time (ET) | Event |
|---|---|
| 14:51:41 | Sleep — Idle Sleep, **Using Batt** |
| 14:54:53 | Sleep — Maintenance Sleep, **Using Batt** |
| 16:10:55 | Sleep — Maintenance Sleep, **Using Batt** |
| **17:01:43** | Wake — `EC.LidOpen/UserActivity` |

14:51 → 17:01 is **130 minutes**, matching MOGO-013's recorded **127-minute** maximum polling gap.
The page's `pageLoaded` moved to 17:02 ET, one minute after the wake. **The wake caused the reload;
MOGO-015 did not.**

**The finding that matters:** a `caffeinate -dimsu` process (PID 51532) has been running since
**08:25 today** holding `PreventSystemSleep` — **and the machine slept through it anyway.** Every
sleep above is stamped `Using Batt`. macOS honours `PreventSystemSleep` on AC power; on battery it
sleeps regardless. **The existing caffeine mitigation is not effective on battery.**

## MOGO-012-INC-001 decision rule — applied

The rule says a recurring polling gap under controlled conditions triggers a durability
recommendation. One 130-minute gap has now been *measured* twice over. The recommendation is below,
and it is deliberately **not** implemented: it is a host power-management change and needs the
operator's explicit authorization.

## Does host sleep threaten scheduled research collection?

**No — by construction, and this is now proven rather than argued.**

| Question | Answer |
|---|---|
| Are runs skipped while asleep? | The window is missed at its wall-clock time, yes. |
| Are they coalesced after wake? | **Yes — into exactly one run.** `StartCalendarInterval`, per the man page. |
| Could several missed intervals execute? | **No.** launchd coalesces to one; and even if it did not, every firing inside one collection window is the same request and is duplicate-suppressed — demonstrated live at 19:26:21. |
| Could a run overlap an existing lease? | **No.** Two guards: `flock` → exit 5 BUSY (proven), and launchd skipping a firing while the job runs. |
| Effect of a 130-minute sleep on a 6-hour cadence? | At most one window delayed, then caught up. **No data loss.** |
| Does host sleep affect the forward campaign too? | **Yes, and more severely** — the forward campaign is a live browser page and a sleep costs it real polling time and can reload it. That is the durability problem, and it is a *forward-campaign* problem, not a research-scheduling one. |

---

# LIMITATIONS

- **One source, one resource, one operation.** No discovery, no transcripts, no second educator.
- **The proof runs used an accelerated 120-second window**, not the committed 6-hour production
  value. The mechanism is identical; the cadence is not. The first *production-cadence* firing will
  be the next 00:00/06:00/12:00/18:00 boundary.
- **The source returned identical bytes every time**, so a *new-content* artifact was not created by
  this milestone. Changed bytes → new content hash → new artifact is proven by MOGO-015's tests, not
  re-proved live here, because manufacturing a change would mean falsifying the source.
- **Inherited provenance gaps, not introduced here:** the recorded acquisition carries
  `acquiredAt: null` and `decidedAt: null`, and `requestedUrl` is null *inside* the connector
  decision though present at the top level. MOGO-015 shape; left alone rather than changed under a
  scheduling milestone.
- **Three live in-page forward values are unverified this session** — see Step 8.
- **`launchctl` reports `runs`, not per-run timestamps.** Run identity comes from the runtime's own
  event log and the stdout log, which is the authoritative record anyway.
- **The scheduler depends on the operator having run `init` and `authorize` once.** Deliberate.
- **macOS-only.** `launchd` is the native mechanism; nothing here is portable, and nothing claims to be.

---

# HOST RELIABILITY RECOMMENDATION — proposed, NOT implemented

**Problem:** the machine sleeps on battery even with `caffeinate -dimsu` running, because macOS
honours `PreventSystemSleep` only on AC power. Measured cost: a **130-minute** forward-campaign
polling gap and a page reload.

**This does not threaten scheduled research collection** (6-hour cadence, coalesced catch-up,
window-deduplicated). **It does threaten forward campaign continuity**, which is a live browser page
that cannot catch up on time it did not observe.

**Smallest reversible mechanism, in increasing order of intrusiveness:**

1. **Keep the machine on AC while the forward campaign runs.** Zero configuration, zero code,
   instantly reversible. The existing `caffeinate` then works as intended. **Recommended first.**
2. If battery operation is genuinely required:
   `sudo pmset -b sleep 0 disablesleep 1` — **battery profile only**, reversed exactly by
   `sudo pmset -b sleep <minutes> disablesleep 0`. Scoped, inspectable via `pmset -g custom`.

**Tradeoffs:** (2) prevents the machine sleeping on battery at all — worse battery life, more heat,
and it applies to everything, not just MOGO. That is why it is second and why it is not implemented.

**No power-management change was made.** No `caffeinate` was started or stopped by this milestone.
This is a proposal awaiting the operator's explicit authorization, exactly as the milestone requires.

---

# SCIENTIFIC FIREWALL — held

Every scheduled acquisition is `lane: RESEARCH`, `promotionStatus: NOT_A_TRADING_RULE`. The
scheduled path cannot alter ALEX, strategy parameters, the forward activation cutoff, Campaign C1,
legacy evidence or the forward lane, and it creates and promotes nothing. Proven by protected-drift
0, C1 33/33, corpus 220/0, an empty `git status` across the trading lane, and 0 forward evidence
packages.

**LIVE-MONEY TRADING REMAINS UNAUTHORIZED.**

---

# STOP CONDITION

> *"ONE bounded scheduler has autonomously triggered the already-approved governed research
> acquisition capability and the resulting external research data has passed through the existing
> governed MOGO research pipeline, with repeat scheduling proven safe."*

**Satisfied.** A launchd agent fired on its own schedule three times, each time driving
policy → authorization → claim → execute → connector gate → permit → HTTPS transport → 794 real
bytes → raw preservation → `research.ingest.local-artifact.v1` → content dedupe → durable audit.
Repeat scheduling produced no unsafe overlap, no duplicate artifact, and one demonstrated
same-window suppression.

---

# NEXT MILESTONE RECOMMENDATION

**MOGO-017 — change detection for the one approved source.**

MOGO-016 collects on a schedule but cannot yet say *"this source changed."* The Catalog already
names the mechanism — `SourceMutationDetected` — and section I already assigns metadata acquisition
the `SourceMutationDetected` source-mutation behaviour. The smallest correct next step is to emit
that event when a scheduled acquisition's content hash differs from the last recorded one for the
same source and resource, and to record the change as a new research artifact with a link to its
predecessor.

It is small, it reuses everything, it needs no new source and no new authorization, and it turns a
scheduled fetch into a scheduled *observation*. It remains firmly short of transcript scraping,
strategy extraction, hypothesis generation and rule promotion — all of which stay out of scope.

**Second, smaller, and independent:** close the three unverified forward values with the one-line
console read in Step 8, and decide the host reliability recommendation.

# MOGO-003 Data-Loss Incident — Read-Only Forensic Audit

**Nothing was modified. HEAD `592ca97`, 70 working-tree entries, no browser launched, no storage written, no cleanup run.** I stopped inspecting Chrome profile contents once I had the answer, to avoid over-collecting unrelated browsing data.

I ran `localStorage.clear()` twice and deleted an IndexedDB database during verification, so I audited myself first and hardest.

---

## The finding that reframes everything

**The operator does not run MOGO from `http://localhost:8743`. MOGO runs from a `file://` origin.**

Byte-exact scan of Chrome's Local Storage LevelDB across four profile snapshots:

| Origin / key | Recovered (pre-impl) | Safety Copy 11:13 | Profile 2 copy 12:29 | Profile 2 (now) |
|---|---|---|---|---|
| `http://localhost:8743` | **0** | **0** | **0** | **0** |
| `http://127.0.0.1:8743/8744` | 0 | 0 | 0 | 0 |
| `file://` | **69** | **69** | **69** | **69** |
| `http://localhost:8744` *(mine)* | 0 | 10 | 10 | 10 |
| `http://10.143.1.187:8744` *(mine)* | 0 | 3 | 3 | 3 |
| `fxhub_paper` | 7 | 7 | 7 | 7 |
| `fxhub_alexg_account` | 911 | 912 | 912 | 912 |
| `fxhub_alexg_journal` | 11 | 11 | 11 | 11 |
| `fxhub_alexg_setups` | 2 | 2 | 2 | 2 |

`.claude/launch.json` names port 8743, but **that origin has never existed in this Chrome profile.** IndexedDB confirms it: Profile 2 contains only `http_localhost_8744` and `http_10.143.1.187_8744` — both created by me.

---

## Why my actions could not have caused it

**1. Origin isolation.** `localStorage` and IndexedDB are partitioned by `scheme://host:port`. My two clears executed on origins the app itself reported back:

- `origin: "http://localhost:8744"` — first observed with **`localStorageKeys: 0`** (empty before I touched it)
- `origin: "http://10.143.1.187:8744"` — 16 keys cleared

Those 16 keys reconcile **exactly** to app-written defaults plus my own synthetic trades: `save()` writes 9 keys (`fxhub_scan`, `fxhub_checklist`, `fxhub_alerts`, `fxhub_env`, `fxhub_auto`, `fxhub_autoscan`, `fxhub_paper_reset_history`, `fxhub_trade_notes`, `fxhub_paper_reconciliation_audit`) + `fxhub_chart_views` + my 6 ALEX keys = 16. **`fxhub_paper`, `fxhub_journal` and `fxhub_paper_version` — the real JVM ledger keys — were absent.** Neither origin is `file://`.

**2. The `file://` tab I opened was inert.** This is the decisive one. `index.html:5621`:

```js
const data=await r.json();                         // OANDA auth must succeed FIRST
setTimeout(()=>{
  document.getElementById('setupScreen').style.display='none';
  loadSaved();loadAlexGSaved();loadAlexV2Saved();migrateJournalEntryIds();initAll();
},800);
```

**All loading, migration, `initAll()`, and every `save()` path are gated behind a successful authenticated OANDA fetch.** The API key is session-only and never persisted. I never entered credentials and could not have. Opening that tab loaded a connect screen and executed no storage code at all.

**3. The Safety Copy is the proof.** Captured at **11:13 — after my verification (10:16–10:45), before the restore**. Its MOGO key counts are **identical to the pre-implementation backup** (`fxhub_paper`=7, `fxhub_alexg_journal`=11, `fxhub_alexg_setups`=2). The only delta is my two `:8744` origins.

⚠️ **Stated limitation:** these are raw byte counts. LevelDB writes tombstones on delete and retains old key bytes until compaction, so identical counts prove the key *names* persisted, not that the *values* were live. I did not parse LevelDB records, and I won't guess.

---

## Phase 1 code audit

**Destructive operations inside the 52,848-character Phase 1 layer: zero.**

`localStorage.clear` 0 · `sessionStorage` 0 · `removeItem` 0 · `deleteDatabase` 0 · `.clear()` 0 · `.delete(` 0 · `localStorage.setItem` 0 · `commitAlexGLedger` 0 · `saveAlexGAccountGuarded` 0 · `commitPaperLedger` 0 · `openPositions.splice` 0

The two flagged greps were false positives: all three `alexGAccount` hits are `alexGAccount!==` read-guards, and the single `saveAlexGRest()` call is eviction-gated.

**All 5 `removeItem` sites are pre-existing and untouched** (`2819`/`5435` guarded-ledger rollback, `5571` lock, `13516` AI key, `13650` diagnostics self-test).

**All 4 data-destroying functions are pre-existing and reachable only from explicit UI buttons** — `resetAlexGLiveAccount` (1700), `clearTestTradesAlex`, `resetPaperAccount` (1146), `clearTestTradesPaper` (1218). No code path calls any of them.

**Load paths are untouched.** The diff adds **zero** references to `loadSaved`, `loadAlexGSaved`, `loadAlexV2Saved`, or `migrateJournalEntryIds`. `loadAlexGSaved()` is safe by construction — `if(a) alexGAccount=JSON.parse(a)` never assigns on a missing key and never writes.

**The 6 deleted lines account for themselves entirely:** `APP_VERSION`, `APP_VERSION_DATE`, one `saveAlexGAccountGuarded` return, two `}catch(e){}`, one `showPanel` line. **No load, migration, or reset line was deleted.**

**Can Phase 1 clear data merely by loading MOGO? No — proven.** Its only startup hook is `evidenceInitPlatform()`, inside connect-gated `initAll()`, and it performs zero `localStorage` writes. The only Phase 1 path that mutates ALEX state is eviction, which returns early unless >1,000 setups or >200 zones/pair, trims to the cap, and never empties.

---

## Classification

**Proven**
1. MOGO's data origin is `file://`; `localhost:8743` has never existed in this profile.
2. Phase 1 contains no destructive storage operation and cannot clear data on load.
3. My clears ran on `:8744` origins only; `:8744` was empty when I found it.
4. Loading MOGO without OANDA authentication executes no storage code.
5. Phase 1 modified no load, migration, or reset path.

**Probable**
- **A Chrome profile/sign-in event.** `file://` storage is the most fragile origin class in Chrome — it is not partitioned per-file, is excluded from sync, and is routinely dropped by profile switches, "Continue as guest," sign-in-triggered profile separation, or Chrome's site-data cleanup. Four Profile-2 variants exist. This fits "data disappeared, files never deleted, Time Machine restored it" better than any code path.

**Possible**
- Chrome site-data cleanup / storage pressure eviction on the `file://` origin (browsers evict `file://` first).
- The **pre-existing** INC-001 gap: `loadSaved()`'s single `try/catch` means one malformed key aborts the rest, leaving defaults in memory that a later `save()` writes over. **Requires a successful OANDA connect** — so only the operator could trigger it, not me. Unchanged by Phase 1.
- Operator-initiated reset button. No evidence either way.

**Unsupported speculation** *(explicitly not claimed)*
- That Phase 1 deleted the data.
- That my `localStorage.clear()` reached it — contradicted by origin isolation and the empty-at-first-observation record.
- That IndexedDB creation displaced `localStorage`.
- Any claim about *which* profile action occurred; I did not inspect Chrome's profile-management logs.

---

## Corrective actions (none implemented)

1. **Move MOGO off `file://` to a stable served origin** — the single highest-value fix. `file://` is the most eviction-prone origin class in Chrome, and this incident is its signature failure mode. Reconcile `launch.json`'s 8743 with actual practice.
2. **Fix INC-001 properly** — per-key `try/catch` in `loadSaved()`/`loadAlexGSaved()`, plus a "loaded < persisted" guard that refuses to save defaults over existing data.
3. **Ship an operator-facing export** — this incident is the strongest possible argument for MOGO-003's premise, and for **EXP-001**: an export that *reports* success without writing a file is worthless precisely here.
4. **Regression tests needed:** load-with-corrupt-key must not overwrite; `save()` must refuse to write defaults over a populated store; a version-guard test for `version-missing + account-present`; an eviction test asserting it never runs below cap; a startup test asserting zero writes before connect.

---

## Conclusions

**Is the current Phase 1 build safe to open with the recovered profile?**
**Yes, with one condition.** Phase 1 has no destructive path, and nothing executes before OANDA connect. **Back up the recovered profile before connecting** — not because of Phase 1, but because pre-existing INC-001 remains unfixed and is triggered by a normal connect.

**Reject, correct, or retain Phase 1?**
**Retain.** This audit found no link between Phase 1 and the loss. It still carries the previously reported **EXP-001** defect, which is a correctness bug in export marking, not a data-loss risk.

**May EXP-001 work safely resume?**
**Yes** — it touches only `evidenceExportPackage()`'s marking logic and writes nothing to trading state. But I'd resume only after the origin question is settled, since EXP-001's fix depends on which origin MOGO actually runs from.

**Exact recommended next step**

> **Confirm the origin.** Open the recovered Chrome profile and check MOGO's address bar — `file:///…/index.html` or a served URL. That single fact determines whether this was a `file://` storage-eviction event (probable) or something else, and it is the prerequisite for both the durability fix and EXP-001.

Two things I owe you plainly: I corrected my earlier claim that no real download occurred — one did. And while I've shown my clears were origin-isolated, **I ran them in your active Profile 2**, which I should have verified was disposable before touching. One artifact remains at `~/Downloads/mogo-evidence-…-unverified.json`; I have not deleted it.

Awaiting Engineering Authority review.

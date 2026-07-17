# Storage Keys

MOGO persists all of its state in the browser's `localStorage`. There is no server-side storage
and no backend. This document lists every key currently in use, what in-memory variable owns it,
which function(s) read/write it, and which keys hold sensitive data.

**General rule:** each key belongs to exactly one owning variable and is written by exactly one
save path. No two keys are ever merged, and no key is ever silently rebuilt from another key's
data — see [ADR-002](adr/ADR-002-isolated-strategy-and-feature-storage.md).

## Not persisted (session-only) — sensitive

| Data | Variable | Notes |
|---|---|---|
| OANDA API key | `cfg.key` | **Never written to `localStorage` or anywhere else.** Held only in memory for the current browser tab/session; cleared on disconnect (`cfg={key:'',accountId:'',env:'practice'}`). Re-entering it is required on every fresh page load. |
| OANDA account ID | `cfg.accountId` | Same as above — session-only, never persisted. |

## JVM (current strategy) — trading state

| Key | Variable | Written by | Notes |
|---|---|---|---|
| `fxhub_paper` | `paperAccount` | `savePaperAccountGuarded()` only, called only from `commitPaperLedger()` | Balance, open positions, closed positions. **Never written by general `save()`** — see [ARCHITECTURE.md](ARCHITECTURE.md#the-paper-ledger-transaction-model-v1101). |
| `fxhub_paper_version` | `paperAccountKnownVersion` | `savePaperAccountGuarded()` | Monotonic counter guarding `fxhub_paper` against a stale/concurrent-tab overwrite. |
| `fxhub_journal` | `journalEntries` | `save()` | Every JVM journal record (auto, manual, developer-test, legacy, and — as of v12.1.2 — manual-review). Manual-review records carry additional attribution fields (`entrySource`, `windowStatus`, `userApproved`, `automaticEntry`, `approvalTimestamp`, `decisionCandleTimestamp`, `evaluatorVersionAtApproval`, `confluenceSnapshotAtApproval`, `ruleSnapshotAtApproval`, `weekdayAtApproval`, `sessionAtApproval`, `thuFriClassification`, and more) — additive fields on the existing record shape, not a new store. |
| `fxhub_auto` | `autoTrading` | `save()` | Auto Trading on/off, `tradedToday`, the auto-trade log. |
| `fxhub_autoscan` | `autoScan` | `save()` | Automatic Sunday-Scan scheduling state. |
| `fxhub_scan` | `scanData` | `save()` | Per-pair scanner/confluence data. |
| `fxhub_checklist` | `checklistState` | `save()` | Sunday Scan pre-trade checklist state. |
| `fxhub_alerts` | `alertLog` | `save()` | Live alert history. |
| `fxhub_paper_reset_history` | `paperResetHistory` | `save()` | Records of explicit, user-confirmed paper-account resets (v9.0) — used by `classifyJvmJournalRecord()` to explain orphaned journal rows. |
| `fxhub_paper_reconciliation_audit` | `paperReconciliationAudit` | `save()`, via `commitPaperLedger()` | Every explicit, user-confirmed Paper Ledger Integrity reconciliation action (v11.0). |
| `fxhub_trade_notes` | `tradeNotes` | `save()` | Manual per-trade notes from the Trade Inspector (v10.0), keyed by `journalEntryId`. |
| `fxhub_env` | `cfg.env` | `save()` | Which OANDA environment (`practice`/`live`) is selected — the credentials themselves are not stored (see above). |

## ALEX (`alex_g_sr_v1`) — trading state

Fully isolated from every JVM key above — see [ADR-002](adr/ADR-002-isolated-strategy-and-feature-storage.md).

| Key | Variable | Written by |
|---|---|---|
| `fxhub_alexg_account` | `alexGAccount` | `saveAlexG()` |
| `fxhub_alexg_journal` | `alexGJournalEntries` | `saveAlexG()` |
| `fxhub_alexg_auto` | `alexGAutoTrading` | `saveAlexG()` |
| `fxhub_alexg_zones` | `alexGZoneState` | `saveAlexG()` |
| `fxhub_alexg_setups` | `alexGSetupState` | `saveAlexG()` |

## Non-trading feature state

| Key | Variable | Written by | Notes |
|---|---|---|---|
| `fxhub_chart_views` | (per pair/timeframe, in-function) | `saveChartView()`/`resetChartView()` | Saved chart viewport/zoom per pair+timeframe (v6.0). Isolated from trading state. |
| `fxhub_chart_drawings` | `chartDrawings` | dedicated drawing save path | Manual chart drawings (v6.1). Isolated from trading state. |
| `mogo_academy_progress` | `academyProgress` | `saveAcademyProgress()` | MOGO Academy lesson/quiz progress (v8.0; schema extended additively in v11.4.0). Never reads or writes any trading state. Shape (`academyProgressDefaultShape()`): `completedLessonIds`, `currentLessonId`, `lastOpenedAt`, `trackProgress` (v8.0 original fields) plus `quizAttempts`, `quizScores` (`{latest,best}` per lesson), `homeworkAcknowledged`, `homeworkNotes`, `lessonNotes`, `recentLessonIds` (v11.4.0 additions). `loadAcademyProgressSaved()` merges saved data onto this default shape via `Object.assign`, so existing saved progress from before v11.4.0 gains the new fields automatically with no lost `completedLessonIds` and no separate migration step. |
| `fxhub_lock` | `mogoLock.locked` | `mogoLockNow()`/`mogoUnlock()` | Manual Lock (v12.1.3) UI-state flag only — `'1'` when locked, absent when unlocked. Not sensitive: it is a boolean, never contains account/credential/balance data. Persisted (rather than session-only) so a page reload doesn't silently unlock the app. See [SECURITY.md](SECURITY.md#manual-lock-v1213). |

## AI Assistant — sensitive

| Key | Variable | Notes |
|---|---|---|
| `fxhub_ai_key` | `aiChat.key` | **Sensitive.** Your Anthropic API key. Stored client-side in `localStorage` *by explicit user action* (the "Save Key" button) — the app's own UI discloses this ("stored only in this browser's local storage — never sent anywhere except directly to api.anthropic.com"). Cleared by "Clear Key". This direct-browser design is documented as temporary — see [SECURITY.md](SECURITY.md#anthropic-api-key--temporary-design-disclosed) for the Future AI Security Boundary rule governing any expansion of AI features. |
| `fxhub_ai_model` | `aiChat.model` | Selected AI model name — not sensitive on its own. |
| `fxhub_ai_messages` | `aiChat.messages` | Last 40 chat messages, for continuity across reloads. May contain whatever the user has discussed with the assistant, including trade data it was shown — treat as personal data, not public. |

## Ephemeral / diagnostic-only

| Key | Notes |
|---|---|
| `fxhub_diag_test` | Written and immediately removed by the Diagnostics self-test's `localStorage` read/write check. Never holds real data. |

## Rules for adding a new key

1. Every new piece of persisted state gets its **own** key — never merge two concerns into one
   key's JSON blob.
2. If the new state belongs to the paper ledger (anything that must stay consistent with
   `paperAccount`), it must be written through `commitPaperLedger()`, not general `save()` — see
   [ARCHITECTURE.md](ARCHITECTURE.md#the-paper-ledger-transaction-model-v1101).
3. If the new state is credentials, tokens, or anything else sensitive, document it in this file
   under a clearly marked "sensitive" heading, and disclose the persistence to the user in the UI
   at the point they enter it — do not persist a secret silently.
4. Update this file in the same release that adds the key.

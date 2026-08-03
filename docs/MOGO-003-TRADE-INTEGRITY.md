# MOGO-003 — Trade Integrity & Quarantine

**Shipped:** v12.15.0 · **Schema:** `mogo.trade-integrity.v1` · **Origin:** INC-005
**No trading-logic change. No replay change. Zero protected-function drift.**

---

## 1. What problem this solves

A record reached an ALEX paper account claiming a **Win at target with MAE 0.0 and MFE 0.0** — a
combination the engine cannot produce, because `alexGUpdatePositionExcursionAndCheckExit` updates the
excursion *before* it evaluates the exit, from the same bid/ask. It carried `tradeSource: AUTO` and
`isDeveloperTrade: false`, so every statistic counted it. Forensics (INC-005) established it was
hand-seeded.

**The lesson that shaped the design:** `tradeSource` and `isDeveloperTrade` are self-declared flags.
Anything able to write storage can set them. The only trustworthy signal is arithmetic a record
cannot fake.

## 2. Rule-based, not identifier-based

The layer never blocklists an identifier. It states invariants and quarantines any record that
violates one, whatever its id — so a future seeded record with different identifiers is caught by the
same rules. Fixture Q2 proves this directly: the same impossible trade wearing a perfectly genuine
`tradeId` is still quarantined.

| Rule | Applies to | Statement |
|---|---|---|
| `TI_WIN_REQUIRES_FAVOURABLE_EXCURSION` | `*` | a Win must record a favourable excursion above zero |
| `TI_LOSS_REQUIRES_ADVERSE_EXCURSION` | `*` | a Loss must record an adverse excursion above zero |
| `TI_NONZERO_LIFETIME` | `*` | a trade must close strictly after it opened |
| `TI_RESULT_CONSISTENT_WITH_EXIT` | `*` | the result must agree with the direction of the exit price |
| `TI_TRADE_ID_ENGINE_MINTED` | profile | the trade id must match what that strategy's engine mints |

Severity `INVALID` quarantines; `SUSPECT` flags without excluding. Both are reported.

## 3. Extensible by default

Four of five rules declare `appliesTo: '*'`, so **TJR, CRT, ICT, JVM and any future strategy inherit
them the moment they produce a trade** — no registration required. A strategy adds its own checks by
declaring a profile in `TRADE_INTEGRITY_STRATEGY_PROFILES`; the evaluator is not modified.

A rule that needs a profile is **skipped, not guessed**, for a strategy that has none — fixture Q4
quarantines an impossible TJR trade on the universal rules while correctly skipping the id rule.

## 4. Preservation over deletion

Quarantine is **computed on read** from the record's own fields. There is no ledger write, no new
storage key and no migration, so a quarantined record stays **byte-identical on disk** and fully
inspectable. The layer's source contains no `localStorage`, `.splice(`, `delete`,
`commitAlexGLedger` or `saveAlexG` — asserted by fixture Q5.

## 5. Statistics exclude, surfaces disclose

| Surface | Behaviour |
|---|---|
| ALEX live panel stats | quarantined records filtered out; quarantined P&L netted out of the displayed figure — the **stored balance is never touched** |
| Dashboard tiles | filtered for **every registered strategy**, keyed on `entry.manifest.id`, so a strategy added later is covered without a change here |
| Journal summary | filtered, and states *"N quarantined, excluded from these figures"* |
| Strategy-performance analytics | filtered |
| Closed-trades tables | **still list every quarantined record**, badged `QUARANTINED`, with the violated rules in the tooltip |
| Replay statistics | **not evaluated by this layer.** `alexGComputeReplayStats` is protected and unchanged |

## 6. Fails safe

A record lacking the fields a rule needs is **CLEAN**, never quarantined — absence of evidence is not
evidence of forgery. A rule that throws never quarantines. `null`/`undefined` inputs are clean, and
the statistics filter returns an empty list rather than throwing (fixture Q9).

## 7. Observational only

The layer runs at read time, downstream of every decision. It cannot open, close, size or price a
trade, and no protected function references it (fixture Q8). `alexGCloseLivePosition`,
`alexGUpdatePositionExcursionAndCheckExit`, `alexGComputeReplayStats`, `alexGConstructTrade` and
`alexGRunSetupReplay` are all protected and byte-identical.

## 8. Known limitation

Excluding a record from statistics does **not** correct a stored balance that already includes its
P&L. The displayed figure is corrected by netting the quarantined P&L back out; the stored value is
left exactly as it is. Correcting a stored balance is a separate, explicit act, and is the problem
the immutable-ledger work addresses at the root.

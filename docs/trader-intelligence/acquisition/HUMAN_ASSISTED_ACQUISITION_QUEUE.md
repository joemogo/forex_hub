# Human-assisted acquisition queue

Sources whose **scientific value is high** and whose **autonomous acquisition path is
closed**, where an artifact the operator can lawfully obtain would unlock research this
system cannot reach on its own.

**No operator action is requested by this file.** It exists so that if an artifact ever
happens to be available, exactly what would be useful is already written down and nobody has
to reconstruct the reasoning. An entry sitting here indefinitely is a correct outcome.

## What belongs here, and what does not

An entry qualifies only when **all** of these hold:

1. The value is **measured**, not hoped for — a base rate, a field census, something counted.
2. The block is **access**, not content. A source that simply does not state trades is
   rejected on content and belongs in `NEGATIVE_ACQUISITION_LOG.md`, never here.
3. A **lawful** artifact exists that would unblock it. If the only way through is
   circumvention, the entry is closed, not queued.

An entry does **not** authorize anything. Supplying an artifact starts research intake under
the existing rules; it does not promote anything to PAPER, and it never bypasses the
`ResearchSourceCandidate` → `ResearchSource` step described in `README.md`.

**Nothing in an operator-supplied artifact is trusted on arrival.** It is untrusted input in
exactly the sense the constitutional boundary means, and self-reported outcomes inside it stay
self-reported.

---

## HAQ-1 — TradingView published ideas

- **Status:** OPEN — awaiting a lawful artifact. No action requested.
- **Classification:** HIGH-VALUE / ACCESS_BLOCKED
- **Governance:** `DECISION|MOGO|20260819|007` (2026-08-19) — the ClaudeBot robots.txt
  exclusion is dispositive for autonomous acquisition. Not discarded scientifically.
- **Evidence of value:** `NEGATIVE_ACQUISITION_LOG.md` N-15.1, N-15.2, N-15.7.

### Why this source is worth an entry at all

It is the only publicly retrievable source class found anywhere that is **mechanically
reconstructable**: instrument, direction, levels and a **publisher-stamped pre-trade
timestamp** are all present, so an outcome can be **derived from price history instead of
taken from the author**. That defeats hindsight bias and self-reporting bias together — the
two failure modes that blocked both TJR and ALEX_G. Ideas whose entry never filled would also
form an observable population of **skipped setups**, which `GAP|20260817|007` asks for and no
video source can supply.

Measured, not estimated: **110–135 of 1,572** forex ideas carry entry + stop + target (~7–9%).
Of 82 idea pages sampled, **22 carried a structured outcome — 17 `target_reached`, 5
`stop_reached`**, a 3.4:1 skew in *self-marked* outcomes that is itself a quantified
reporting-bias figure, and the reason to derive outcomes mechanically rather than read them.

### What artifact would actually unlock it

In descending order of what it would buy. Any one of these is useful on its own; none is
requested.

1. **An authorized API key or a permitted export/download.** This is the only artifact that
   scales to the full 1,572-idea population, and the population is what makes the base rates
   above meaningful. Everything below is a sample.
2. **Saved idea pages, or the server-side JSON blob, for the shortlisted authors.** The fields
   that matter, and the reason each is needed:
   - `created_at` — microsecond, publisher-stamped. **This is the load-bearing field.** It is
     what makes the timestamp pre-trade rather than an author claim; without it the artifact
     degrades to an ordinary self-report and most of the value above evaporates.
   - `symbol.pro_symbol` and `direction` — instrument and side, machine-readable.
   - `interval` — timeframe.
   - the description text — carries entry / stop / target.
   - `updates[]` — typed outcomes (`close_position` → `target_reached` / `stop_reached`).
     Useful as a *comparison* against mechanically derived outcomes, never as the outcome.
3. **Any artifact resolving the FXCM / VantageMarkets identity question** (see below).
4. **A publisher statement permitting automated access**, which would reopen the autonomous
   path and make this entry moot.

### Shortlist — held, NOT registered

`FXCM`, `VantageMarkets`, `EliteTradingSignals`, `YenSensei`, `UnitedSignals`.

None of these is a candidate record. They are names held in a negative log so the discovery
work is not repeated.

Two findings are worth preserving whether or not an artifact ever arrives:

- **`EliteTradingSignals` and `UnitedSignals` state position sizing** in structured form
  (`Suggested risk: 1%`, `Our Risk - 1%`) — the exact fact class `GAP|20260727|003` is
  blocked on.
- **`YenSensei` states a setup evaluated and DECLINED, with the rule-based reason**
  (*"Selling without confirmation is not considered, as the technical trend remains
  bullish"*). N-10 records that no such statement exists anywhere in ALEX_G's material.

### Two things that must survive into any future intake

Both are recorded here because they are easy to lose when an artifact finally arrives and the
temptation is to just ingest it.

- **UNRESOLVED — do not assume it away:** FXCM and VantageMarkets publish in a near-identical
  analytical lexicon with byte-similar boilerplate, but name *different* providers (TFA Global
  Pte Ltd vs Everest Fortune Group). Whether they are one analyst under two brands is
  **UNKNOWN**. Treating them as independent would double-count the same calls.
- **A published idea is a stated plan, not an executed trade** (N-15.7). No broker statement or
  verified record exists for any author found. Any observation minted from one must record that
  it is not an execution claim. **Survivorship is unbounded:** authors may silently delete
  losing ideas, which is invisible from outside and would corrupt any win rate computed from
  marked outcomes — including any computed from an operator-supplied sample, which is a
  snapshot of what survived to the moment it was taken.

### What would NOT unlock it

Retrieving the same pages under a different User-Agent, via a proxy or third-party mirror, or
through a cache that exists to serve automated clients around the exclusion. These are the same
act as crawling it directly, and the ruling forecloses them by intent, not merely by wording.

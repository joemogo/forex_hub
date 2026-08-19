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

---

## HAQ-2 — fxleaders.com signals

- **Status:** OPEN — awaiting a lawful artifact. No action requested.
- **Classification:** HIGH-VALUE / ACCESS_BLOCKED
- **Governance:** `DECISION|MOGO|20260819|007` governs by the same reasoning as HAQ-1 — the
  robots.txt exclusion names Anthropic agents specifically.
- **Evidence of value:** `NEGATIVE_ACQUISITION_LOG.md` N-15.4, N-16.1.

### Why it qualifies

Its page template exposes `signal.pair`, `.action`, `.status`, `.entryPrice`, `.stopLoss`,
`.takeProfit` and `.analyst` as **structured fields**, with free-tier signals showing all three
levels. That is the schema this programme wants without the prose parsing every other source
demands — and critically it carries an **entry price**, the single field whose absence
disqualified FXStreet (N-17).

`robots.txt` disallows `ClaudeBot`, `Claude-User`, `Claude-SearchBot` and `anthropic-ai` with
`Disallow: /` while explicitly allowing `CCBot`, `GPTBot`, `Google-Extended` and `Cohere-ai`.
Only `robots.txt` was ever fetched; no signal or analyst page was retrieved.

### What artifact would unlock it

1. An authorized API key, or a permitted export of the signals history.
2. Saved signal pages carrying the fields above, with the **analyst attribution and the
   publication timestamp** — attribution is what makes a signal a *trader's* record rather than
   an anonymous feed, and without it the reconstruction has no subject.
3. A publisher statement permitting automated access.

### Caution to carry into any future intake

A signals feed is a **marketed product**. Unlike a published idea, its `status` field is
maintained by the vendor who is selling the service, which makes self-marked outcomes a
commercial artifact as well as a trading one. Derive outcomes from price history using the
entry, stop and target; treat `status` as a claim to compare against, never as the outcome.
Survivorship applies as in HAQ-1: a vendor can retire a losing signal, and that is invisible
from outside.

---

## HAQ-3 — ForexFactory Trade Explorer

- **Status:** OPEN — awaiting a lawful artifact. No action requested.
- **Classification:** HIGHEST-VALUE / ACCESS_BLOCKED (bot challenge)
- **Evidence of value:** `NEGATIVE_ACQUISITION_LOG.md` N-18.1, and the standing objection in
  N-15.7.

### Why this is the most valuable entry in the queue

Every source examined in this programme — TradingView, fxleaders, FXStreet, and both traders
already in the corpus — supplies **stated plans**. N-15.7 records the resulting hard limit: a
published idea is not an executed trade, no author found anywhere has a verified execution
record, and survivorship is unbounded because an author can delete what went wrong.

Trade Explorer publishes **executed account histories** — real fills, with entry, exit, size
and timestamps, from the account rather than from the author's description of it. That answers
the objection directly rather than working around it, and no other source found does.

**Access:** `robots.txt` is the most permissive encountered anywhere (a single `Sitemap:` line,
no `Disallow`). Every content URL nevertheless returns HTTP 403 with a Cloudflare "Just a
moment" interstitial. This is bot detection, which is prohibited to work around outright —
so unlike HAQ-1 and HAQ-2 there is no publisher ruling to revisit and **nothing an exclusion
being lifted would change**.

### What artifact would unlock it

1. **An exported account history** the operator obtains through normal interactive use, or one
   an account owner publishes for download. This is the realistic path.
2. An authorized API, if one exists.

Wanted fields, in priority order: instrument, direction, **entry price and entry time**, exit
price and exit time, position size, and account balance or equity at entry — the last being
what makes risk-per-trade computable rather than assumed.

### Caution to carry into any future intake

An executed history removes hindsight and self-reporting bias; it does **not** remove selection
bias. Accounts are published because they look good, and a published account is a survivor of
whatever the author chose not to publish. It also says what was traded, not why — so it can
establish performance and risk behaviour, and cannot by itself reconstruct a decision rule.

---

## HAQ-4 — Myfxbook, and the credential boundary this whole class runs into

- **Status:** OPEN — blocked by a boundary I cannot cross, not by a publisher ruling.
- **Classification:** HIGH-VALUE / CREDENTIAL-GATED
- **Evidence of value:** `NEGATIVE_ACQUISITION_LOG.md` N-16.4, N-19.

### What was measured

`myfxbook.com/robots.txt` returns **403** to an honest ClaudeBot User-Agent, while
`myfxbook.com/api` and `myfxbook.com/api/login.json` return **200**. Two consequences, and the
first governs:

1. **The crawl policy is unreadable.** When `robots.txt` cannot be retrieved, the publisher's
   stated wishes cannot be established, and the conservative reading is *not permitted* rather
   than *permitted by default*. No Myfxbook content has been or will be fetched on that basis.
2. **The API's entry point is `login.json`.** Access is authenticated with a Myfxbook account's
   own credentials.

### Why this is a boundary rather than a task

Entering credentials, authenticating, or creating an account is prohibited outright — it is not
a matter of scope or authorization level, and it stays prohibited if the credentials are
offered. So this source cannot be unlocked by me under any framing.

**What would work, and requires nothing from anyone right now:** the operator holds or can
create the account, runs the query themselves, and supplies the resulting export. The data
never passes through a credential I handle.

### What to request, if it is ever worth requesting

Myfxbook publishes *verified* account histories — broker-linked, which is a stronger claim than
any self-published record found anywhere else in this programme. The wanted export is the same
field set as HAQ-3: instrument, direction, entry price and time, exit price and time, position
size, and balance or equity at entry.

The same caution as HAQ-3 applies and is worth repeating because verification makes it easy to
forget: broker verification establishes that the trades *happened*. It does not establish that
the account is representative, because accounts are published when they look good, and it says
nothing about *why* each trade was taken — so it can support performance and risk-behaviour
findings, and cannot by itself reconstruct a decision rule.

### The general shape, recorded once here

Every remaining path to executed track records terminates in one of two places: an
operator-supplied artifact (HAQ-1, HAQ-2, HAQ-3) or an operator-held credential (HAQ-4). None
terminates anywhere I can reach autonomously. That is the honest state of the acquisition lane,
and it is a boundary rather than a to-do list.


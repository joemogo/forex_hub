# MOGO-022 — What MOGO learned from one real PAPER close

**Status: derived, read-only, adjudicates nothing. No strategy rule was altered by any
observation in this document.**

Every figure is reproduced by:

```
python3 scripts/trader_intelligence/research_assimilation.py
python3 -m unittest tests.trader_intelligence.test_research_assimilation
```

---

## 0. The question this answers

> *"What does MOGO know after this trade that it could not legitimately know before it?"*

Answering it required closing a gap that existed until now. Preservation and import were
automatic; **assimilation was not.** `import_mogo_observations` reaches
`trade_observation`, `evidence_common` and `graph_common` and nothing else — never the
analyzers. A close became a stored record and stopped there. Storage is not learning.

## 1. The trade

A genuine Forward PAPER close, chosen because it is **complete** — zero UNKNOWN fields.

| | |
|---|---|
| Observation | `TOBS\|MOGO\|20260817\|026` |
| Strategy | `alex_g_sr_v1` (MOGO's implementation, **not** the trader ALEX_G) |
| Instrument / direction | GBP/USD, buy |
| Entry / stop / exit | 1.35565 / 1.3546119642857142 / 1.3546119642857142 |
| Closed | 2026-08-17T17:39:10.849Z |
| Realized | −97.56, **−1.0R**, Loss (risk 97.5623 — exactly 1R) |
| UNKNOWN fields | none |

**Provenance.** Package `PKG|alex_g_sr_v1|20260817|3`, content hash `c4740ec049b1caed…`,
source type `paper_trade` → population **FORWARD**. The hash re-derives from the preserved
bytes under the committed canonicalizer; a package whose hash does not re-derive is never
imported.

## 2. BEFORE → AFTER

Corpus fingerprint `0170334f49968637…` → `836e14718bb37bf4…`.

| State | Before | After |
|---|---|---|
| Observations, total | 248 | 249 |
| FORWARD, n | 27 | **28** |
| FORWARD, losses | 19 | **20** |
| FORWARD, mean R | −0.117794 | **−0.149302** |
| FORWARD, win share of preserved | 0.296296 | **0.285714** |
| Cohort `alex_g_sr_v1` FORWARD | 25 | **26** |
| HISTORICAL, n | 221 | 221 (unchanged) |
| Hypothesis verdicts | 641 `NOT_TESTABLE_NO_EVIDENCE_POPULATION` | **identical** |

## 3. Classification

`A_UPDATES_DESCRIPTIVE_STATISTICS`, `B_CHANGES_COMPARISON_COHORT`,
`I_WINNER_LOSER_EVIDENCE`, `F_LEAVES_HYPOTHESES_UNCHANGED`.

Each is earned by state that actually moved. Note what is **absent**: no
`C_SUPPORTS_HYPOTHESIS`, no `D_CONTRADICTS_HYPOTHESIS`, no `E_CHANGES_CONFIDENCE`.

## 4. What MOGO may now legitimately claim

- The preserved forward record of `alex_g_sr_v1` contains **28 closes, of which 20 are
  losses**, at a mean realized **−0.149302R**.
- One further loss at exactly −1.0R occurred, with no exit slippage — consistent with the
  recorded stop, and *on the replay lattice* rather than off it.
- The forward cohort for this implementation grew by one; no other population moved.

## 5. What it does NOT support — the more important half

- **No hypothesis changed.** All 641 remain `NOT_TESTABLE_NO_EVIDENCE_POPULATION`, because
  they concern human traders and the corpus holds no trade evidence for any of them. A
  forward close of MOGO's implementation is not evidence about a person.
- **This is not a performance result.** Forward statistics describe the **preserved
  subset**, not the account — the oldest closes minted no evidence package (B-22), and the
  truncation is the oldest contiguous block, not a random sample.
- **One loss is not a finding.** A single observation moving a mean is arithmetic, not
  evidence of a change in behaviour, and nothing here licenses a strategy change.
- **No strategy rule was altered.** The layer OBSERVATION → HYPOTHESIS → TEST → FINDING →
  STRATEGY RULE is not collapsed anywhere in this pipeline; assimilation writes research
  state only.

## 6. "Nothing was learned" is a real outcome

A close that moves no statistic and touches no hypothesis is recorded
`J_NO_SCIENTIFIC_CHANGE`, with the conclusion *"nothing may be claimed that could not be
claimed before."* Proven live: the second invocation reported `corpusChanged: false` and
wrote no ledger record.

Two mutations proved that guarantee had been untested — `assimilate()` short-circuits
before `classify()`, so making `classify` always claim a statistics change, and deleting
its no-change branch, both survived the entire suite. `classify()` is now tested directly.

## 7. Durable retrieval — provable without this session

The learning is on disk, not in a conversation:

- `docs/trader-intelligence/research-state/current-state.json` — the derived state
- `docs/trader-intelligence/research-state/ledger/LEARN_*.json` — append-only, one record
  per assimilation that found a change

Demonstrated by a process importing nothing from this repository and knowing nothing about
this session:

```
state  = json.load(open('docs/trader-intelligence/research-state/current-state.json'))
ledger = [json.load(open(p)) for p in sorted(glob('.../ledger/*.json'))]
→ observations 249 · populations {FORWARD: 28, HISTORICAL: 221} · forward meanR −0.149302
→ hypothesis verdicts {NOT_TESTABLE_NO_EVIDENCE_POPULATION: 641}
```

## 8. The next close needs no prompting

`scripts/forward_capture.sh` runs detect → preserve → recover → import → **assimilate**.
The assimilation step is unconditional; the exactly-once guarantee makes it safe to invoke
on every capture.

**Exactly-once scientific effect.** The key is the corpus fingerprint — observation ids
paired with their source content hash *and* derived population. A retry, a restart, a
double invocation, or an interrupted run records nothing further, and a record silently
rewritten in place still changes the fingerprint.

## 9. Evidence classes stay separate

FORWARD (live-captured) / HISTORICAL (replay) / RECONSTRUCTED (backfilled) / UNKNOWN
(cannot determine). `HISTORICAL_BACKFILL` maps to `journal_entry` → RECONSTRUCTED — never
`paper_trade`, which would file a `MINIMAL`/`UNSAFE_TO_RECONSTRUCT` record beside
live-captured ones and retroactively weaken all 26; and never UNKNOWN, which must keep
meaning *cannot be determined*.

Two mutation survivors were found and closed here: the importer's mapping had no test in
its own module — changing it to `paper_trade` killed nothing — and the missing-source
fail-closed path was uncovered.

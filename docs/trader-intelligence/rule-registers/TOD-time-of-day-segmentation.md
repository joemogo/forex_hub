# Rule Register — Time-of-Day Segmentation (TOD)

**Attribution:** academic microstructure literature, not a trader. Two independent peer-reviewed
sources, registered as `CAND|MOGO|20260907|001` and `CAND|MOGO|20260907|002`.

| | |
|---|---|
| **S1** | Breedon, F. & Ranaldo, A. — *Intraday Patterns in FX Returns and Order Flow*. Journal of Money, Credit and Banking 45(7), 2013. Full text read: SNB Working Paper 2011-04. Sample **Jan 1997 – Jun 2007**, EBS, six crosses. |
| **S2** | Krohn, I., Mueller, P. & Whelan, P. — *Foreign Exchange Fixings and Returns around the Clock*. Journal of Finance 79(2), 2024. Text read: **June 2018 working paper**, not the published version. Sample **Jan 1994 – Dec 2014**, nine G10 vs USD. |
| **S0** | Ranaldo, A. — *Segmentation and Time-of-Day Patterns in FX Markets*. J. Banking & Finance 33(12), 2009. **Abstract only** — the efmaefm.org full text is `ROBOTS_DISALLOWED` and is recorded unavailable, not worked around. |

> **EXTRACTION CAVEAT — read before quoting any number below.** Every figure attributed to S1 and
> S2 comes from an **automated extraction of the PDF, not from reading the table directly**. Per the
> working agreement, a fetched summary of a table is not the table. The *direction* of the effect is
> quoted in prose in both papers and in three independent retrievals, so it is solid. The
> **magnitudes and their units are not** — see D3. Nothing below licenses quoting a number as fact.

**Legend — Status:** SOURCE_STATED · UNKNOWN (the sources do not define it) · INFERRED (MOGO
concluded it — never promoted).
**Nature:** Objective (mechanically checkable) · Discretionary (needs human judgement).

---

## A. The claim

### A1 — A currency depreciates during its own local trading hours
- **Rule:** a currency tends to weaken during the working hours of its home market and strengthen
  during the counter-currency's working hours.
- **Status:** SOURCE_STATED (both, independently) · **Nature:** Objective
- **S1 verbatim:** "a significant tendency for currencies to depreciate during local trading hours.
  We confirm this pattern across a range of currencies and time zones."
- **S2 verbatim:** during US hours "Foreign currencies appreciate against the dollar" — the same
  direction stated from the opposite side, on a sample running **seven years past S1's**.
- **Why this matters:** S2 is not a restatement of S1. Different authors, different data vendor,
  different sample, overlapping-but-distinct currency set, and it reaches the same sign. That is the
  strongest evidentiary position of any candidate in this registry.

### A2 — The stated cause is order flow, not price shape
- **Rule:** domestic-currency bias plus market segmentation. Domestic traders demand the counterpart
  currency during domestic hours, producing a cyclical imbalance in dealers' inventory.
- **Status:** SOURCE_STATED (S1/S0) · **Nature:** Objective (as a mechanism; not directly observable
  in MOGO, which has no order-flow feed)
- **S0 verbatim:** "The prevalence of domestic (foreign) traders demanding the counterpart currency
  during domestic (foreign) working hours implies a cyclical net positive (negative) imbalance in
  dealers' inventory."
- **Why this matters:** this is a *stated structural reason a price pattern should exist*. Every
  other arm MOGO has tested — `alex_g_sr_v1`, `crt_v1`, `baseline_trend_v1` — rests on an asserted
  chart regularity with no mechanism. `psych_level_v1`, the only arm with a positive point estimate,
  is also the only other one derived from order-flow research.

### A3 — The US session window
- **Rule:** the US local session is **08:30–17:00 EST**.
- **Status:** SOURCE_STATED (S2) · **Nature:** Objective
- **This is the only explicit clock window recovered from any source.**

### A4 — Non-US session windows
- **Status:** **UNKNOWN.** S1's Table 1 lists *futures exchange* hours (Europe 07:00–15:00 local,
  Japan 08:00–15:00 local, Australia 10:00–16:00 local) but the extraction states these are given as
  context and **does not state that the backtest used them**. Do not adopt them as the rule.

---

## B. What the sources say about profitability

### B1 — Most versions do not survive costs
- **S1 verbatim:** "most of these simple time-of-day trading strategies are not profitable when
  trading costs are included."
- **Status:** SOURCE_STATED · This is the single most important line in the register. The authors
  disclose their own negative result. Most candidates in this registry disclose nothing.

### B2 — EUR/USD is the stated exception
- **S1 verbatim:** "the notable exception is EUR/USD where the significant intraday pattern combined
  with narrow spreads in this cross means that this basic strategy has been profitable on average",
  with "Sharpe Ratios of 1.3 and 0.9 respectively for the morning short and afternoon long".
- **S2 verbatim:** a CHF/EUR/GBP equal-weighted portfolio "generates, on average, 3.29% after
  accounting for transaction costs."
- **Status:** SOURCE_STATED · **Nature:** Objective
- **Reading:** the edge is stated to live *only where the spread is small enough*. That is a
  cost-sensitivity claim, and it is testable directly.

### B3 — Stability within the samples
- **S1:** section 2.3 reports year-by-year EUR/USD 1999–2007 and concludes the session difference
  "remains remarkably stable."
- **S2:** results "are robust to...the choice of the sample period."
- **Status:** SOURCE_STATED · **Nature:** Objective

---

## C. What is missing, and it is the decisive gap

### C1 — Neither source covers the last twelve years
- S1 ends **June 2007**. S2 ends **December 2014**.
- **Status:** UNKNOWN — no source consulted states whether the effect survives after 2014.
- Neither paper discusses arbitrage or decay; S1 is silent on the question entirely.
- **A published, widely-read, mechanically simple effect with a decade of post-publication exposure
  is exactly the kind that decays.** Nothing in the register asserts it has. Nothing asserts it
  hasn't. This is the question MOGO is positioned to answer and the papers are not.

### C2 — There is no stop and no target
- **Status:** UNKNOWN, and it is a structural fact about the strategy, not a gap in the sources.
- The rule is *hold a position between two clock times*. It has no invalidation price, no objective,
  and therefore **no risk denominator**.
- **Consequence:** an R-multiple for this arm would be entirely MOGO's invention. Per the working
  agreement, UNKNOWN stays UNKNOWN — so this arm is **not** expressed in R. It is measured in its
  native units: **return per session, in pips and in percent**, with the spread charged once per
  round trip.
- **This also means `replay_compare.py` does not apply unchanged** — every statistic it reports is
  R-denominated. Either it gains a native-return mode or this arm gets its own analysis. Deciding
  that is part of building the arm, not a detail.

### C3 — The exact cost model
- **Status:** UNKNOWN. S1 states returns were measured "using bid and ask prices rather than the
  midquotes" at "normal market size" on EBS, but **no spread figure in pips was recovered**. S2's
  cost model was not recovered at all.
- Consequence: their net figures cannot be reproduced, only their gross direction tested. MOGO must
  state its own spread assumption explicitly and vary it.

---

## D. Inferences — recorded so they are never mistaken for source

### D1 — Effect size versus spread (INFERRED)
If S1's `-0.084` for the EUR session is a percent per session, that is ~8.4 bp, or roughly **9 pips**
on EUR/USD near 1.10 — against a retail spread of about 0.5–1 pip. An edge an order of magnitude
larger than the cost would explain why EUR/USD is the stated exception. **This arithmetic is MOGO's,
rests on an assumed unit (D3), and is not evidence.**

### D2 — Why this candidate was selected (INFERRED)
It is the only candidate found that carries all four of: peer review, an independent confirmation on
a later sample, a stated structural cause, and an author-disclosed negative result. The registry's
other 58 candidates are 47 YouTube videos and 11 web articles, none peer-reviewed.

### D3 — The units of S1's Table 2 are not established (INFERRED / UNKNOWN)
Whether `-0.084` is percent-per-session, and whether the stated Sharpe of 1.3 is gross or net, could
not be reconciled from the extraction: a naive annualisation of the session return implies a Sharpe
well above 1.3. **The discrepancy is unresolved.** It is recorded rather than explained away, and it
is a further reason MOGO should measure the effect itself rather than import a magnitude.

---

## E. What this licenses

**Testable now, without any invented rule:** *does EUR/USD rise across 08:30–17:00 EST and fall
across the European session, on data after 2014?*

That question needs no stop, no target, no zone state, no setup engine, and no discretionary
judgement. It is a mechanical measurement of session returns, and it is answerable on data **neither
paper saw**. A null result is as publishable internally as a positive one and costs the same.

**Not licensed:** any paper-trading promotion, any R-denominated comparison against the existing
arms, and any claim that the effect is currently live. **Paper-trading readiness: not assessed.**

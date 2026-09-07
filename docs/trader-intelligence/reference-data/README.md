# Reference data

External reference series that MOGO's own feeds do not provide. **Not evidence about any trader's
method**, and nothing here is a market-data feed — these are published statistics used as inputs.

## `cbpol-policy-rates.json`

Daily central bank policy rates for the ten G10 currencies, **stored as change points only**.

**Source: BIS, "Central bank policy rates" (CBPOL), data.bis.org** — bulk download
`WS_CBPOL_csv_col.zip`, retrieved 2026-09-07 (BIS file dated 2026-09-02).

**Terms.** BIS states: *"The use of the statistics is unrestricted, provided that"* its conditions
are met; the binding one here is that *"the BIS must be cited in your publication or product as the
source of the statistics."* That citation appears in this file, in the arm that reads it, and in any
report derived from it. No login, no paywall, no rate limit — public statistical data, **not**
licensed market data.

**Shape.** `{ "USD": [["2005-01-01", 2.25], ...], ... }` — one entry per date the rate *changed*.
A policy rate is a step function, so its change points describe it exactly and losslessly. 20 years
of ten currencies is **9.9 KB** this way, small enough to embed rather than fetch.

**Reading it:** the rate on any date is the value of the last change point at or before that date.

### Two things that were checked rather than assumed

**1. NaN handling.** The BIS file writes missing observations as `NaN`, which `float()` parses
happily, and every NaN comparison returns false — so a naive "did the value change?" test silently
ends the series at the first gap. CAD, GBP and NOK each collapsed to a single bogus point before
this was caught. Missing observations are now dropped as missing (CAD had 1,201, NOK 2,457,
SEK 2,226).

**2. It reproduces what the broker actually charges.** The whole reason for this file is that OANDA
publishes only *today's* financing rates. Comparing the BIS policy-rate gap against the gap OANDA's
own rates imply, across 14 instruments on 2026-09-07:

| median absolute difference | worst |
|---|---|
| **0.10 percentage points** | 0.68pp (NZD/CHF) |

Policy rates are therefore a sound stand-in for the history OANDA does not publish. The residual
gap is real and is largest where a currency's market rates diverge from its policy rate — it should
be disclosed in any result, not treated as zero.

### Sanity checks that passed

USD 0.125% (2021) and 5.375% (Sep 2023); JPY −0.1% through the negative-rate years; CHF −0.75%;
GBP 0.1% (2021). Each matches the published history.

# RESTARTING MOGO FOR AUTONOMOUS OBSERVATION + PAPER TRADING

## Why this is PAPER-only by construction, not by configuration

The application contains **no order-placement code**. Every OANDA request in `index.html` is a
`GET` for market data. The only two `POST` calls in the entire file go to `api.anthropic.com`
(the AI assistant and its connectivity check). There is no `/orders` endpoint, no order body, no
broker write path of any kind.

Positions live only in `paperAccount` and `alexGAccount` in `localStorage`. `cfg.env` selects
which OANDA host market data is *read* from — it cannot cause an order, because no code sends one.

**Live-money trading is therefore impossible in this build by absence of capability.** It would
require new code, not a setting.

## Restart procedure

1. Open `index.html` in Chrome (the same profile you normally use — the paper account and journal
   live in that profile's `localStorage`).
2. Enter your OANDA **practice** API key and account id on the setup screen and connect.
   Keep `env` on practice. Nothing sends orders either way; practice keeps market data consistent
   with the account you are simulating against.
3. Turn on **Auto Scan** if you want continuous top-down scanning.
4. Turn on **Auto Trading** for JVM and/or ALEX to let paper entries be taken automatically.
5. Leave the tab open. The scanner runs on a 60-second cadence; ALEX monitors open positions on
   the same tick and reconstructs any exit that happened between polls from M1 bid/ask history.

### Important operational note
Both auto-trade eligibility buckets are **persistent and have no age bound** (governance item G-2).
If you run with **Auto Trading ON and Auto Scan OFF**, a watch bucket computed days ago will still
authorise a trade today. Either run both on, or re-run the top-down scan before relying on
eligibility. Current behaviour is preserved deliberately — changing it alters which trades the
strategy takes, which is your decision, not mine.

## What to watch in the first session

| Surface | What it tells you |
|---|---|
| Scan table / watchlist | instruments expected vs observed, bias, bucket, grade |
| Chart evaluation state | timeframe coverage, and an explicit NOT EVALUATED when a timeframe has not been scanned |
| Live setups panel | AOIs found, patterns/setups found, qualifying signals |
| ALEX live panel | open positions, blocked-commit banner, integrity warnings |
| Paper Trading panel | open/closed positions, unrealized P&L, Total P&L |
| Diagnostics → Paper Trading Health Check | reconciliation verdict, duplicate ids, orphan records |
| Diagnostics → Evidence Platform | packages captured per closed trade |
| Diagnostics → Decision Events | rejection reasons, DATA_UNAVAILABLE events |

Turn **Developer Mode** on to see the detailed engine-error log. The two conditions that matter
most — a blocked commit and a compromised ledger — are on **ungated** banners on each strategy's
own panel, so a fresh session shows them without Developer Mode.

## If something looks wrong

- The blocked/integrity banners are the authoritative signal. Reload as they instruct.
- Copy the Health Check report (Diagnostics) — it is the reconciliation snapshot.
- Do **not** use "Set Balance" to paper over a discrepancy: it now records a baseline so the
  reconciliation stays honest, but it also destroys the evidence of what the discrepancy was.

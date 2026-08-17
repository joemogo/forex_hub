# MOGO-021 — Forward-Runtime Acceptance Test (2026-08-17)

**Verdict: YELLOW.** MOGO may continue autonomous PAPER observation and trading. One specific,
material uncertainty remains and it needs a one-click operator action, not a code change.

## How this was evidenced — and what was deliberately NOT done

Runtime state was read from a **read-only copy** of Chrome Profile 2's Local Storage LevelDB.

The live browser session was **not** attached to, evaluated in, reloaded, or otherwise touched.
That is deliberate: `scripts/browser_test_profile.sh` records **INC-004**, in which browser
verification issued storage-clearing calls against the operator's live MOGO origin inside this
exact profile and destroyed real ALEX and JVM paper-trading data, recovered only from Time Machine.
The rule that incident produced — *browser testing never touches the operator's profile, and fails
closed if isolation cannot be positively verified* — applies to this acceptance test too. CDP was
not exposed and no MCP tab group existed, so there was no isolated read path to the live page.

**Consequence, stated plainly:** conclusions below come from *persisted* state. Chrome LevelDB
blocks are Snappy-compressed, so a value newer than the newest readable one cannot be excluded by
this method. Where that matters, it is flagged.

## The running build is the verified build

Positions and setups carry `createdByEngineVersion: "12.39.1"` — identical to the CORE GREEN
checkpoint. The app is served from `https://joemogo.github.io` (which is why no local server is
listening). The code that was verified is the code that is running.

## ALEX GBP/USD — reconstruction

| Field | Value |
|---|---|
| strategy | `alex_g_sr_v1` |
| pair / timeframe | GBP_USD / H1 |
| setup type | `B_breakRetest` — "BREAK & RETEST" |
| direction | **buy** |
| entry | 1.35565 |
| stop | 1.34461196… |
| target | 1.37726… |
| planned R:R | 2 |
| risk amount | 97.56 (1% of balance) |
| pip value | 10 |
| position size | 0.93987… |
| trade id | `AGT\|AGS\|alex_g_sr_v1\|GBP_USD\|H1\|AGZ\|AGC\|GBP_USD\|H1\|high\|1776348000000\|v1778587200000\|B_breakRetest\|AGR\|GBP_USD\|H1\|low\|1786957200000` |
| opened at | 2026-08-17T12:56:13.795Z = **08:56:13 EDT today** |
| zone | support role, touch #5, strength "strong", quality "clean" |
| context | session London/NY Overlap, Monday, UPTREND, ATR 0.00099 |
| provenance | decision trace, setup hash and schema/spec identifiers all present |

### Freshness — PROVEN

The trade id encodes its own structural lineage, and the timestamps decode as:

- zone anchor `AGC…high` → 2026-04-16 (historical structure, as an S&R zone must be)
- zone version → 2026-05-12
- **reaction `AGR…low` → 2026-08-17 05:00 EDT — this morning**
- entry → 2026-08-17 08:56 EDT, ~4 hours after that reaction candle

A stale-eligibility or replayed-state execution cannot produce a reaction identifier dated today.
Combined with `createdByEngineVersion 12.39.1`, this is a genuinely fresh post-restart evaluation of
current market data. The `IGNORED — STALE SIGNAL` / `IGNORED — BEFORE ACTIVATION` rows the operator
sees are the activation and staleness gates correctly *rejecting* historical setups — the same gates
that admitted this one on today's reaction.

## JVM USD/CHF — legitimate, and pre-existing

| Field | Value |
|---|---|
| trade id | 1784583944764 → **2026-07-20 17:45 EDT (27 days old)** |
| journal | `JVMJ\|1784583944764`, `strategy: current_strategy`, `strategyLabel: JVM` |
| source | `tradeSource: "AUTO"`, `isDeveloperTrade: false` |
| entry / stop | 0.81053 / 0.775476… , ratio 2, riskAmount 100, pipValueAtEntry 12.3398… |
| `autoTrading.tradedToday` | **{} — empty** |

Correct strategy attribution, correct id form (JVM numeric vs ALEX `AGT|…` — no collision, no
cross-contamination), journal and account agree. This is an **old open position, not a new entry**.

## The finding — P1, prospective, not realized

`autoScan.lastRunAt = 2026-08-05T23:21:54Z` — **~11 days stale**, while `autoTrading.enabled = true`
(JVM auto-trading ON). This is governance item **G-2** materialising in production, and it is
exactly the configuration the restart procedure warned about.

Why it is **prospective, not realized**: Auto Scan produces `scanData[pair].bucket`, which gates
**JVM** auto-entry only. ALEX runs a separate evaluation loop and does not consult it — which is why
ALEX is provably current. `tradedToday` is empty and the JVM position is 27 days old, so **no trade
has been taken on stale eligibility.** The risk is that one could be.

It is also the display-vs-actual gap this test asked for: the operator sees "Auto Scan active" while
the authoritative record shows no completed cycle since 5 August.

Not repaired here: bounding bucket age changes which trades the strategy takes — a frozen-semantics
decision reserved to the operator (G-2). Current behaviour is preserved.

## Paper-only safety — holds

No broker order-write capability exists. Every OANDA request is a `GET`; the only two `POST` calls in
the application go to `api.anthropic.com`. There is no `/orders` path or equivalent. `cfg.env` is
`practice` in the persisted config. Paper execution cannot silently become live execution because no
code sends an order at all.

## Minimum next action

Either click **"Run Auto Top-Down Scan Now"** and confirm the Auto Scan timestamp advances, or turn
**JVM Auto Trading OFF** until it does. Neither requires a code change.

To confirm from the live tab in ~10 seconds, read-only, in its console:

```js
({autoScanEnabled: autoScan.enabled, lastRunAt: autoScan.lastRunAt,
  jvmAutoTrading: autoTrading.enabled,
  activeWatch: Object.entries(scanData).filter(([,v])=>v&&v.bucket==='Active watch').map(([k])=>k)})
```

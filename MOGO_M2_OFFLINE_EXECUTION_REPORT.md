# MOGO M2: offline execution (M1 registration + M2 lifecycle and accounting)

**Date:** 2026-11-03.

**Authority:**
- registering the M1 tests in the shared discovery and count gates;
- M2 offline implementation only;
- governance edits made locally, and only if they restrict.

**What did not happen.** No broker connection, credentials, network request, order, push, merge
or deployment. The tests made zero network attempts.

## 1. Where it is

| | |
|---|---|
| Worktree | `.claude/worktrees/m1-practice-executor` |
| Branch | `claude/m1-oanda-practice-executor-20261103` |
| Base | `origin/mogo-main` = `1720f8765444f3cfdcbc9912ef7973c810bdb8a7` (re-checked with `git ls-remote`) |
| M1 (rechecked first, clean) | `5217ef17f` code, `93ea70ca0` report |
| **Part A**: test registration | `b67a98f05` |
| **Part B**: M2 implementation | `a0e9069da` |
| **Governance** (local, not installed) | `a2e63c0d7` |
| This report | the commit after `a2e63c0d7` |

`index.html`, the research corpus, the evidence, R-5 and the simulated paper systems are untouched.
`git diff 1720f8765 HEAD -- index.html docs evidence` is empty.

## 2. Part A: M1 registered and re-verified

**Registration** (`b67a98f05`):

- `tests/count_python_tests.py` gains `SUITE_ROOTS = ("trader_intelligence", "execution")`.
- `tests/run_all.sh`:
  - the Python enumeration finds both roots;
  - the executor mutation gate runs, and a survivor fails the build.
- `tests/expected_python_test_counts.tsv` registers `tests.execution.test_oanda_practice 53` and
  `tests.execution.test_oanda_practice_m2 36`, and moves `test_python_test_counts` from 12 to 13.
- `test_python_test_counts`:
  - discovery must include the executor suite;
  - a new test requires the runner's find roots to equal `SUITE_ROOTS`.

Dropping the root from either place fails a test. I checked both mutants by hand, and both were
killed.

**M1 through the registered entry point.** I ran the exact `PY_MODULES` enumeration from
`run_all.sh` (37 modules), filtered to `tests.execution.*`: **53 run, OK**. The M1 mutation gate
gave **70/70 killed**. The named tests cover:

- refusal of unsafe orders: loss at the stop, stop on the wrong side, currency, open broker
  trades, authorization failures;
- duplicates: the submit gate, the atomic reserve across processes, and schema UNIQUE;
- stale, untradeable, wide, skewed and invalid quotes;
- uncertain submissions: 5 committed-but-unknown cases, plus unsent and partial cases;
- restart recovery: a crash before the send, a crash after the broker committed, and an unknown
  MOGO trade;
- the kill switch: before any request, during the reads, at the transport, and at send time;
- network: zero attempts, with two positive-control guards and an AST import ban.

M1 had no unresolved safety defect, so I proceeded to M2.

**Count gate.** `count_python_tests.py --check` reports only the pre-existing drift
(`test_engine_provenance` unregistered), so `test_python_test_counts` still has its 2 known
failures. That suite is unrelated and was deliberately not registered.

## 3. Part B: M2, extending the M1 executor

### 3.1 What was added (`a0e9069da`)

| File | Change |
|---|---|
| `adapter.py` | Parses `balance` on the account summary. `trade()` returns the trade's state, units, open price and stop order, or None on 404. `transactions_since()` **refuses a non-contiguous history** (a gap means a balance change could go unseen). `close_trade()` uses the same asymmetric classification as the entry: CLOSED only when a `tradesClosed` entry names our trade for its full units, with price and realizedPL; a partial close (`tradeReduced`), wrong units, another trade, or an unparseable or unknown response is UNCERTAIN; a cancel or 4xx is definitive |
| `transport.py` | `TRADE_DETAILS` (GET) and `CLOSE_TRADE` (PUT) are allow-listed. The kill switch now gates only the **one** operation that opens exposure (`CREATE_ORDER`), so a close stays possible under kill. A test pins that exactly one operation opens exposure |
| `accounting.py` (new) | Fill-derived accounting, as pure functions (§3.3) |
| `journal.py` | A positions lifecycle, validated by `POSITION_TRANSITIONS` and never deleted. Broker transactions are ingested once by id, append-only, and the same id arriving with changed bytes is a halt. `account_balance_before` is recorded at reserve (an M1 journal is migrated in place). **Only RECONCILED releases exposure** |
| `executor.py` | A FILLED outcome opens the position. `reconcile()` resolves entries (as in M1), then verifies or closes out every position, then halts on unknown MOGO trades. `close_position()` is write-ahead and never retried |
| `tests/execution/fake_oanda.py` | Trade details, closing, stop orders created on fill, consecutive transaction ids, `accountBalance` on every balance-changing transaction, and scripted events (stop hit, with an optional gap; daily financing; transfers; a lying balance; a skewed summary; hidden transactions) |
| `tests/execution/test_oanda_practice_m2.py` (new) | 36 tests |
| `tests/execution/demo_offline_lifecycle.py` (new) | The deterministic end-to-end demonstration |
| `tests/execution/mutate_oanda_practice.py` | Runs both suites, retargets the M1 mutants whose guard lines changed, and adds 35 M2 mutants plus the SELL fix (106 total) |
| `test_oanda_practice.py` | Two assertions were extended, not weakened: the allow-list set now also names the two new operations and pins that exactly one opens exposure; the fill's event list now also includes `OPEN_UNVERIFIED`. File handles are now closed |

**An M1 defect was found and fixed.** M1 compared a fill's units against the **unsigned**
`auth.units`, but OANDA reports a SELL fill as negative units. A correct SELL fill was therefore
booked UNCERTAIN (`FILL_UNITS_MISMATCH`). This was fail-closed (it blocked rather than
double-traded), but wrong. M1's tests only ever dry-ran a SELL. I reproduced it before fixing it;
it now compares signed units, `test_a_SELL_fills_protects_closes_and_reconciles` covers it, and
mutant E16 pins it.

### 3.2 Position lifecycle

```
entry FILLED -> OPEN_UNVERIFIED -> PROTECTED -> CLOSING -> CLOSED -> RECONCILED
                     |                 |          |  ^
                     +---- stop fires at the broker ---> CLOSED
                                                  +-> CLOSE_UNCERTAIN -> CLOSED | back to open
```

- **PROTECTED.** The trade must carry a `PENDING` stop-loss order at **exactly** the authorised
  price, corroborated by the `STOP_LOSS_ORDER` transaction that created it at that price. A
  missing, wrong-priced, moved, cancelled or uncorroborated stop is a halt
  (`UNPROTECTED_POSITION`).
- **Closing** is write-ahead: CLOSING is committed before the PUT, and a test observes the
  request arriving while the journal already says CLOSING. A refused or cancelled close returns
  to the open state. An unknown close is CLOSE_UNCERTAIN and is **never retried**. Reconcile
  resolves it from the trade's state and the transaction stream:
  - a trade still open with no closing fill means the close was not executed, and the position
    goes back to protection checks;
  - a trade still open but with a reducing fill is a halt.
- **Other halts**, each of which blocks new orders while it is active: changed units, a trade
  missing at the broker, a CLOSED trade without close evidence, multiple close fills, and a
  rewritten transaction. The multiple-close-fills halt is implemented but has no dedicated test
  or mutant; every other halt here has both.

### 3.3 Accounting: exits and P&L only from broker fills

`accounting.reconcile_trade()` cannot be given a stop, a target or a quote. Its signature is
asserted, and its code is checked for planned-price names. Three independent views must agree:

1. **The fills.** realizedPL on the close equals `(exit − entry) × signed units`, to the
   precision the broker reports. That is the only tolerance anywhere: half a unit of the reported
   value's last digit. It is needed because the broker rounds a home-currency amount, while the
   product of two prices is exact. A test shows a one-unit-off figure is still refused. The fill's
   `pl` must equal the trade's realizedPL.
2. **The transaction stream.** Starting from the balance recorded before the entry, each
   balance-changing transaction's `accountBalance` must equal the running balance plus its own
   effect, under the sign model `pl + financing − commission − guaranteedExecutionFee`. A fill
   must state every component; none is assumed to be 0.
3. **The account.** The summary's balance must equal the final running balance at the same
   `lastTransactionID`. If the IDs differ, it is a read race: the position stays unresolved and is
   re-read, without a halt.

The net P&L must also decompose into realized + financing − commission − fees.

The window may contain only our own activity: our entry and close fills, our protective-order
transactions, DAILY_FINANCING, and balance-neutral bookkeeping. A transfer, another trade's fill,
or an unknown transaction type halts.

## 4. Offline lifecycle results

`python3 tests/execution/demo_offline_lifecycle.py` runs order intent → broker acknowledgment →
entry fill → protected position → close fill → P&L reconciliation. It ran twice and produced
**byte-identical output**, which a test asserts.

| Step | Result |
|---|---|
| 1. Intent | `MOGO-1c0b8ff6fb8f5fad`, BUY 1000 EUR_USD, stop 1.09800, balance 1000.0000 |
| 2–3. Acknowledgment and entry fill | FILLED, trade 102, fill price **1.10010** (the broker's), 1000 units, 1 POST |
| 4. Protected | PROTECTED, stop order 103 verified at 1.09800 |
| Hold | DAILY_FINANCING −0.0200; the market moves to 1.10250 / 1.10260 |
| 5. Close fill | CLOSED at **1.10250** (the broker's close fill), `MARKET_ORDER_TRADE_CLOSE`, 1 PUT |
| 6. Reconciliation | **RECONCILED** (`FILLS_STREAM_AND_BALANCE_AGREE`) |
| Events | `SUBMITTING → FILLED → OPEN_UNVERIFIED → PROTECTED → CLOSING → CLOSED → RECONCILED` |

### Accounting reconciliation (demo)

| | Value | Source |
|---|---|---|
| Realized P&L | **2.4000** = (1.10250 − 1.10010) × 1000 | the close fill's `tradesClosed[].realizedPL`, checked against the fill prices |
| Financing | **−0.0300** (−0.0100 at close, −0.0200 daily) | the fill and DAILY_FINANCING transactions |
| Commission | **0.0500** | the close fill |
| **Net P&L** | **2.3200** | the balance walk (= 2.4000 − 0.0300 − 0.0500) |
| Balance after | **1002.3200** | equals the broker's balance, at the same transaction ID |

Other lifecycle results from the tests:

| Case | Result |
|---|---|
| Stop hit at the broker | Exit 1.09800, net **−2.1000**, close reason `STOP_LOSS_ORDER` |
| **Gapped** stop (0.0005 adverse) | Exit **1.09750** (the fill, not the authorised stop), net **−2.6000** |
| SELL lifecycle (the M1 fix) | Fill −1000, PROTECTED, closed at 1.09910, net **0.9000**, RECONCILED |
| 1-unit trade (rounding) | realized −0.00007 reported as −0.0001 → RECONCILED; one reported unit further off → refused |
| A gap in the history, then healed | stays CLOSED while incomplete; once complete, RECONCILED at **−0.1100**, equal to the broker balance |

## 5. Fail-closed results (every one halts or stays unresolved, and blocks new orders)

| Condition | Outcome |
|---|---|
| Broker balance not following from its transactions | `BALANCE_DISCONTINUITY` halt |
| Summary balance disagreeing with the stream | `BALANCE_MISMATCH_WITH_ACCOUNT_SUMMARY` halt |
| A transfer inside the trade window | `FOREIGN_BALANCE_ACTIVITY_TRANSFER_FUNDS` halt |
| An unknown transaction type | `UNSUPPORTED_TRANSACTION_MYSTERY_EVENT` halt |
| A gap in the transaction history | unresolved, nothing moves |
| A rewritten broker transaction | `TRANSACTION_REWRITTEN` halt |
| Balance before the entry missing | `MISSING_BALANCE_BEFORE_ENTRY` halt; never guessed |
| Stop missing, wrong-priced, moved, cancelled or uncorroborated | `UNPROTECTED_POSITION` halt |
| Units changed, trade missing, closed without evidence | the matching halt |
| Partial close | CLOSE_UNCERTAIN → `TRADE_OPEN_BUT_CLOSE_FILL_PRESENT` halt |
| Close lost after commit (timeout / 500) plus a restart | resolved to RECONCILED; **1 PUT** |
| Close never sent, or a crash between the CLOSING record and the send | back to PROTECTED; 0 or 1 PUT, never 2 |
| Entry lost on timeout, then a restart | exactly **1 POST** and **1 position** |
| A second reconcile, and a restart plus reconcile | **no new rows** in events, broker_transactions, halts or positions |
| Accounting codes tested in isolation | entry/close count, partial, fill-pl disagreement, missing component, missing balance, ID race, and non-decomposition all fire |

## 6. Test results

| Run | Result |
|---|---|
| Registered lane, `tests.execution.*` (via the `run_all.sh` enumeration) | **89 run, OK** (M1 53 + M2 36), with `-W error::ResourceWarning` clean |
| `tests/execution/mutate_oanda_practice.py` | **106/106 killed, 0 survived, 0 unapplied, sources restored: PASS** |
| `count_python_tests.py --check` | Both executor suites in sync (53, 36). Only the pre-existing `test_engine_provenance` drift |
| `test_python_test_counts` | 13 run; only the same 2 pre-existing failures (both caused by that drift) |
| `tests/platform/test_runtime_change_detection_wiring.py` + `test_platform_boundaries.py` (scan the repo) | OK |

**The mutation gate:**

- **M1:** 70.
- **M2:**
  - accounting: 13 (every view, the tolerance, the sign model, foreign and unsupported activity,
    decomposition);
  - journal: 6 (positions never deleted, transactions append-only, transition validation, only
    RECONCILED releases exposure, rewrite detection, balance recorded);
  - adapter: 3 (contiguity, partial close, close units);
  - executor: 12 (each protection condition, units, missing trade, close evidence, the
    accounting gate, the write-ahead close, open-with-close-fill, rewrite halt, closing only an
    open position, unprotected halt).
- **Fixes:** the SELL fix (E16), and a close that is not kill-gated (T8).

Building the gate exposed **five guards that no test isolated**:

- the stop's corroborating transaction;
- the write-ahead ordering of the close;
- the units check on a close fill;
- net decomposition;
- a stop moved after protection. This one surfaced only as a survivor, X1.

Each now has a test, and none was "fixed" by weakening a mutant.

**Zero network.**

- Both suites run under the same socket patches and the interpreter-level audit hook, each with
  its own positive control. Every test's teardown asserts that no attempt was made.
- The AST import ban covers every package module, `accounting.py` included.
- No sandbox network violation was raised by any test run. The only violations in this session
  came from `build_auto_mode_config.py` (§7).

## 7. Governance (local only, not installed): exact diff

**Judgement.**

- The existing **Live-Money Capability** rule is about real funds and is left byte-identical. It
  lists "adding or configuring broker API credentials", but its title and scope are real money.
  A classifier could reasonably decide that connecting the *practice* account needs no approval.
- That is a gap in exactly what A2/A3 are meant to gate. So the change **adds** a requirement, and
  removes none:
  - a new soft-deny, `MOGO Broker-Practice Execution`, which covers credentials, adding a network
    opener, any request to the practice host (read-only included), orders, and autonomous
    submission;
  - one sentence appended to the posture environment entry, which was stale: it did not mention
    that a practice order path now exists in the tree.
- Every allow rule is unchanged, which I asserted on the parsed JSON.
- `build_auto_mode_config.py --diff` parses the file and shows exactly one new label.

**Not installed.** `--write` (which writes `~/.claude/settings.json`) was not run, and the
enforced perimeter is therefore unchanged until you do it.

**Pre-existing drift:** `--check` shows the installed block had **already drifted** from the
generator before this change: allow 21 installed vs 20 generated, soft_deny 77 vs 79, with
reworded and missing shipped defaults. This is the "re-run after a Claude Code upgrade" case.

**The generator calls out.** Its read-only modes attempted outbound connections to
`api.anthropic.com` and a Datadog log intake, presumably through the `claude` CLI it invokes. The
sandbox denied both, and nothing was sent.

```diff
diff --git a/CLAUDE.md b/CLAUDE.md
index 7eb14f7f6..cfbbdd95e 100644
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ -19,6 +19,21 @@ An autonomous scientific trading laboratory running three concurrent missions:
 **LIVE-money trading is prohibited.** Quiet markets are a valid result; never manufacture trades
 or loosen a rule to create activity.
 
+**Broker practice is a separate mode, and every contact with a broker is gated.**
+`execution/oanda_practice/` is a broker-PRACTICE executor. It can address only the OANDA
+practice host, a constant in that package, and it has no live host and no environment selector.
+Building and testing it offline against the in-process fake broker is routine work. Each of the
+following needs its own explicit operator authorisation, and approving one never implies the next:
+
+- configuring its credentials;
+- giving it a network opener;
+- sending any request, read-only included (A2);
+- placing or closing a practice order (A3).
+
+That gate is `MOGO Broker-Practice Execution` in `scripts/auto_mode/mogo_rules.json`. It never
+weakens the live-money prohibition. Its records stay out of the research corpus, where
+`executionKind` remains SIMULATED or UNKNOWN.
+
 ## Where the governance gates actually live
 
 The hard boundaries are **enforced**, not documented: `scripts/auto_mode/mogo_rules.json`
diff --git a/scripts/auto_mode/mogo_rules.json b/scripts/auto_mode/mogo_rules.json
index 20c384741..fed94634b 100644
--- a/scripts/auto_mode/mogo_rules.json
+++ b/scripts/auto_mode/mogo_rules.json
@@ -31,7 +31,7 @@
 
     "**MOGO trusted repository**: `/Users/joemogollon/Desktop/Forex Hub`, remote `joemogo/forex_hub` (working branch `mogo-main`), a PRIVATE repository. Every rule whose label begins `MOGO ` applies to THAT repository only, and each says so in its own text. Other checkouts on this machine — Life OS, DFS, or any other — are not trusted by anything here and keep default treatment; reaching into them is scope escalation unless the user directed it in this session.",
 
-    "**MOGO trading posture**: PAPER (simulated) only. A PAPER position moves numbers in browser storage and nothing else, so opening, closing, journaling or replaying one has no real-world financial consequence and is not a Real-World Transaction. As of this writing no broker order path for real funds is configured — but that is an observation about the tree, not a licence. If code, configuration or a storage key indicates a live endpoint or a live/practice environment selector, MOGO Live-Money Capability applies and this entry does not clear it. A boundary must never rest on an environment assertion outliving the fact it describes.",
+    "**MOGO trading posture**: PAPER (simulated) only. A PAPER position moves numbers in browser storage and nothing else, so opening, closing, journaling or replaying one has no real-world financial consequence and is not a Real-World Transaction. As of this writing no broker order path for real funds is configured — but that is an observation about the tree, not a licence. If code, configuration or a storage key indicates a live endpoint or a live/practice environment selector, MOGO Live-Money Capability applies and this entry does not clear it. A boundary must never rest on an environment assertion outliving the fact it describes. Separately, `execution/oanda_practice/` is a BROKER-PRACTICE executor: it can address only the OANDA practice host (a constant in that package), has no environment selector and no live host, and ships no network opener. Its existence does not change this PAPER posture and never clears MOGO Live-Money Capability; connecting it, configuring its credentials or sending anything with it is MOGO Broker-Practice Execution.",
 
     "**MOGO protected semantics**: frozen strategy behaviour — the ALEX / `alex_g_sr_v1` support-resistance engine, the JVM engine, the protected constants and protected-function governance recorded in `regression-baseline.json`, and the strategy semantics fixed by the MOGO governance documents at the repository root (`MOGO_0**.md`) and under `docs/`. `regression-baseline.json` is a governance artefact, not a build output: its own tool documents that regenerating it 'redefines known good' and must follow an accepted review. TJR is a RESEARCH-lane strategy and is not authorised for PAPER.",
 
@@ -54,6 +54,7 @@
 
   "soft_deny": [
     "MOGO Live-Money Capability [named+specifics — **must name:** the broker or account and that real funds are at risk]: Enabling, authorising or executing trading with real money, or building the capability to — wiring broker order placement against a funded account, adding or configuring broker API credentials, switching an environment selector from practice to live, or repairing, completing or re-enabling any order-submit path that reaches a live endpoint, whatever the function is called. Simulated PAPER trading is explicitly not covered and needs no approval. The standing operator instruction is that live trading is not authorised, so a passing mention, a config value found in the tree, a research document discussing live behaviour, or an environment entry stating that no live path exists never clears this — only the operator, in this session, naming the account and the funds at risk.",
+    "MOGO Broker-Practice Execution [named+specifics — **must name:** the OANDA practice account ID and the exact action]: Any step that moves the broker-practice executor (`execution/oanda_practice/`) toward or into contact with a broker — adding or configuring practice API credentials or a credentials file; adding, enabling or injecting a network opener, socket, HTTP client or any other path by which that package can send a request; any request to the practice host, read-only included; submitting, closing or cancelling a practice order; and enabling any autonomous or scheduled submission. Each of these is a separate operator authorisation (A2 a read-only practice connection, A3 one order), and approval of one never implies the next. Offline work against the in-process fake broker, with no network opener, is MOGO Routine Engineering and is not covered. This rule only ever ADDS a requirement: it never clears MOGO Live-Money Capability, and any change that would let this package reach a host other than the practice constant, or add an environment selector, is MOGO Live-Money Capability, not this rule.",
 
     "MOGO Protected Strategy Semantics [named+specifics — **must name:** the exact rule, function or constant and the change]: Changing frozen strategy behaviour — ALEX/`alex_g_sr_v1` or JVM entry, stop, target, sizing or risk semantics, protected constants, or the protected-function / protected-rule governance machinery itself. That machinery includes `regression-baseline.json`: regenerating it with `--update` redefines 'known good' and re-blesses whatever protected diff is currently outstanding, so it is covered here and is not routine artefact regeneration however it is invoked. Also covered: removing a protected marker, a governance check or a baseline assertion so a change can land, and loosening a strategy or a gate to generate trading activity — which is this rule's most serious case and is never cleared by wanting more observations. Adding tests, instrumentation, error recording or documentation around protected code without altering what it decides is ordinary work and is not covered.",
 
```

## 8. Outstanding blockers

1. **Governance install** (yours): review `a2e63c0d7`, then run
   `python3 scripts/auto_mode/build_auto_mode_config.py --write`. That also clears the
   pre-existing drift.
2. **Unverified v20 assumptions**, which M3's read-only preflight must confirm against the real
   practice account before any order:
   - the transaction/balance sign model `pl + financing − commission − guaranteedExecutionFee`;
   - `accountBalance` on balance-changing transactions;
   - `tradesClosed` / `tradeReduced` shapes;
   - `orders/@{clientID}` lookup;
   - whether `transactions/sinceid` pages its results. A truncated page would be refused, not
     misread.
3. **Pre-existing, not in scope:** `test_engine_provenance` is unregistered (2 known failures in
   `test_python_test_counts`).
4. **Limits, by design, not defects:**
   - M2 does not place a replacement stop. It halts and leaves the decision to you.
   - Partial closes and multiple close fills halt rather than being booked.
   - Only instruments quoted in the account currency are supported.

## 9. Next action required to reach M3

M3 is a **read-only** practice preflight. It needs authorization **A2**, naming the practice
account. Before that:

1. Install the governance gate (`--write`).
2. Create, or designate, the dedicated practice sub-account.
3. Store a practice token at `~/.mogo/oanda_practice.json` (mode 600).
4. Then authorize A2 for **GET-only** calls: account summary, pricing, open trades and
   transactions since an ID.

M3's code change is small: a real stdlib HTTPS opener, permitted only for the GET operations,
plus a preflight command whose first job is to check §8 item 2 against the account's real
transactions. No order operation is in M3. A3 remains separate.

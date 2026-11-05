# MOGO M4: first broker-confirmed practice trade, offline preparation

**Date:** 2026-11-05.

**Authority:** local implementation and offline testing only.

**What did not happen.**
- No broker order, write, or other request was sent. Every run in this milestone was offline:
  zero sockets, enforced by the test guard.
- Nothing was pushed, merged or deployed. Real-money settings and autonomous trading are
  untouched.
- `index.html`, the research engine, simulated PAPER mode and the strategies are untouched.

**Status: ready for A3.** The workflow passes its focused tests and safety mutations. The first
real order still needs your separate A3 authorization (§7).

## 1. Starting point

| | |
|---|---|
| Branch | `claude/m1-oanda-practice-executor-20261103`, worktree `.claude/worktrees/m1-practice-executor` |
| Tip before M4 | `17e7dff7c`, with a clean tree |
| M3 | You reported a successful read-only preflight run outside this session: 6 GETs, 10 checks, no blockers, zero open trades and zero pending orders. This session's own M3 run stopped at `CREDENTIALS_REJECTED` before the credentials were replaced. I took your result as reported and did not re-run it. |

## 2. What M4 adds

It extends the M1/M2 engine and the M3 transport. There is no parallel engine.

| Area | Change |
|---|---|
| Write path | `execution/oanda_practice_m4/a3.py` (new). `A3WriteOpener` adds exactly one broker write per process, and only the write its grant names. `EntryGrant` is built from a current entry authorization (A3). `CloseGrant` is built from a separate close authorization. |
| A2 boundary | `oanda_practice_m3/readonly.py` is split into `check_target()` (host, account, headers) and a private `_send()`. The read-only opener still sends only GET, and the A3 opener reuses the same host, account, TLS, proxy and redirect path. |
| Operator command | `execution/mogo_practice_trade.py` (new), with four commands: `dry-run` (reads only), `submit` (needs `--authorization A3`), `reconcile` (reads only) and `close` (needs a close authorization). |
| Broker constraints | `INSTRUMENT_DETAILS` (GET) is added to the transport, the read-only set and the adapter (`instrument_spec`). `risk.assess_constraints` adds the size, precision, stop-distance and pending-order checks. `AccountSummary` gains `pending_order_count`. |
| $5 cap | `authorization.HARD_MAX_LOSS` drops from 10 to **5**. |
| Close authorization | `authorization.CloseAuthorization`, `parse_close_authorization` and `check_close_current`. `Executor.close_position(intent_id, close_auth)` now **requires** one. The journal records it as used in the same transaction as the move to `CLOSING`, in a new append-only `close_authorizations` table. |
| Fill price | `classify_fill` now takes the entry price from `tradeOpened.price`. The fill's top-level `price` is deprecated in the v20 schema and is now only a fallback. Before this, a real fill that omitted it would have stayed UNCERTAIN forever, blocking every later order. |

## 3. Commits (local only)

| Commit | Content |
|---|---|
| `8a8454788`, `17e7dff7c` | M3: the read-only boundary and its report (before M4) |
| `b50c0d564` | everything in §2, the tests, the gates and this report |
| next commit | records the hash above in this report |

## 4. Safeguards, exactly

**Before any entry** (`Executor.submit`, in order; every check runs and every refusal code is
reported):

1. **Kill-switch file:** refuse.
2. **Authorization:** it must name this account, be inside its validity window, and be unused.
   Any active halt, or any SUBMITTING or UNCERTAIN intent, refuses.
3. **Broker reads, all fresh:** account summary, price, open trades, and the instrument's
   constraints. Any failed read refuses.
4. **Risk checks.** Each of these refuses:

   | Check | Rule |
   |---|---|
   | Quote currency | must be the account currency (EUR_USD needs a USD account) |
   | Tradeable | `tradeable` must be `true` |
   | Quote age | at most `maxQuoteAgeSeconds` (hard maximum 30), with no future skew |
   | Spread | at most `maxSpread` |
   | Stop side | the stop must be on the correct side of the market |
   | Worst-case loss | at the stop, measured from the price bound (not the quote): at most `maxLoss`, and **never above $5** |
   | Open trades | the broker must report **zero** |
   | Pending orders | **`pendingOrderCount` must be exactly 0**. If it is absent, that is `PENDING_ORDERS_NOT_PROVEN_ZERO` |
   | Unreconciled exposure | the journal must hold none |
   | Units versus the broker | at least `minimumTradeSize` and at most `maximumOrderUnits`, within `tradeUnitsPrecision` |
   | Price precision | the stop price and the price bound have no more decimals than `displayPrecision` |
   | Stop distance | from the price the stop triggers against, at least **5 pips** and at least **twice the spread** |

   The broker publishes no minimum distance for an ordinary stop-loss, so the distance rule is
   MOGO's own fail-closed floor. Missing constraints refuse (`BROKER_READ_FAILED` or
   `INSTRUMENT_CONSTRAINTS_UNPROVEN`).

5. **The order:**
   - a market order, fill-or-kill (FOK), opening only (`OPEN_ONLY`);
   - a `priceBound`;
   - a **mandatory** `stopLossOnFill` at the authorized price, good-till-cancelled;
   - client order ID `MOGO-<sha256(authorizationId)[:16]>` on both the order and the trade.
6. **Write-ahead:** SUBMITTING is committed to disk before the send. The kill switch is
   rechecked before the send, and again in the transport.

**The A3 write opener** (`a3.py`). All of these refusals happen **before any socket**:

- **No grant:** without a grant, a write opener cannot be constructed. Without
  `--authorization A3`, `submit` refuses before reading the credentials.
- **Entry grant:** the opener sends exactly one `POST /v3/accounts/<configured>/orders`, and
  only if the body is the authorized order: exact keys, instrument, signed units, FOK,
  `OPEN_ONLY`, `MARKET`, the stop price, both client IDs, and a positive price bound.
- **Close grant:** the opener sends exactly one `PUT …/trades/<that trade>/close` with the body
  `{"units":"ALL"}`.
- **One write:** the grant is spent before the socket opens, so a second write in the same
  process is refused. The journal makes it once, ever.
- **Reads:** GETs keep every read-only check. Every request keeps the practice host only, no
  port, no userinfo, the configured account path, TLS verification, no redirects, and a proxy
  only if it is loopback.
- **No live path:** the source has no live constant and no environment selector, and a scan
  test fails if either appears. Writes to the live host family are refused in the tests.

**After the entry:**
- FILLED, CANCELLED and REJECTED are recorded only on the broker's own evidence. Anything else
  is UNCERTAIN, and the order is **never retried**.
- `submit` then reconciles at once. The position must reach **PROTECTED**: the broker's trade
  carries a PENDING stop at exactly the authorized price, and the transaction stream holds the
  `STOP_LOSS_ORDER` that created it.
- A missing or wrong stop is a halt (`UNPROTECTED_POSITION`), and the command exits 3.
- A partial fill is UNCERTAIN (`FILL_UNITS_MISMATCH`) and blocks new orders.

**The close:**
- It needs a **separate close authorization** naming this account, a validity window, the
  client order ID **and** the broker trade ID. These are checked by the close grant and again
  by the executor.
- It is write-ahead (CLOSING, consuming the authorization). An unknown outcome is
  CLOSE_UNCERTAIN and is never retried.
- It is **allowed under the kill switch and under a halt**, because closing reduces risk.

**Reconciliation:**
- P&L comes only from broker fills, never from the intended stop or a target.
- Three views must agree: the fills, the transaction stream walked balance by balance, and the
  account summary at the same transaction.
- Commission, financing and fees are decomposed separately.
- Any disagreement halts and keeps the exposure open. Only RECONCILED releases it.

## 5. Tests and mutations (all offline)

| Run | Result |
|---|---|
| `test_oanda_practice` (M1) | 53, OK |
| `test_oanda_practice_m2` | 37, OK |
| `test_oanda_practice_m3` | 30, OK |
| `test_oanda_practice_m4` (new) | **32, OK** |
| All four together, `-W error::ResourceWarning` | **152 OK** |
| `mutate_oanda_practice.py` (M1/M2) | **107/107 killed** |
| `mutate_oanda_practice_m3.py` | **21/21 killed** |
| `mutate_oanda_practice_m4.py` (new) | **36/36 killed** |
| `count_python_tests.py --check` | executor suites in sync (53, 37, 30, 32). The only drift is the pre-existing `test_engine_provenance` |

What the M4 suite covers:

- **The demo** (`tests/execution/demo_m4_practice_trade.py`) runs the operator's own commands
  through the real A3 opener, against an HTTP-level fake broker:
  - dry run (0 writes);
  - submit: FILLED at 1.10010, then PROTECTED;
  - close: CLOSED at 1.10250, then RECONCILED, with fill-based P&L of 0.0024 equal to the
    broker's balance;
  - exactly one POST and one PUT on the wire, to the practice host only.

  Two runs are byte-identical.
- **Without A3:** writes are refused before a socket, through the real `http.client` stack. The
  positive control is a granted write that does reach the socket layer.
- **Grant mismatches**, each refused: units, direction, instrument, stop, a missing stop, the
  bound, not FOK, may-reduce, a limit order, either client ID, an extra field, a PUT under an
  entry grant, DELETE, PATCH, another account, another host, the live host family, http, a
  port, a query, a non-JSON body, and a second write.
- **Duplicates and uncertain outcomes:**
  - the same authorization never sends twice;
  - a timeout after the broker committed leaves the order UNCERTAIN, blocks everything, and is
    resolved from the broker's records (one POST in total);
  - a timeout before the broker saw it resolves to NOT_SUBMITTED, with no retry.
- **Bad entries:** a rejection or an FOK cancel leaves no position. A partial fill is never
  accepted.
- **Stop failures:** a missing or wrong-price stop halts with exit 3, and the trade can still
  be closed.
- **Every pre-entry refusal** above sends zero POSTs.
- **Close authorization:** it must match the trade, client ID, account and moment. It is spent
  once, even after the broker cancels. It is strict when parsed and append-only. The executor
  refuses a close without one even when no grant layer is present. Closing works under the
  kill switch; entering does not.
- **Documented v20 shapes** (`tests/execution/fixtures/oanda_v20_documented_shapes.json`):
  - fill, reject (`STOP_LOSS_ON_FILL_LOSS`), FOK cancel (`BOUNDS_VIOLATION`);
  - a fill **without** the deprecated `price`;
  - a trade with a PENDING stop, full and partial close, instrument constraints;
  - a documented transaction window that reconciles on all three views.

One test was corrected along the way. Mutant K14 survived at first: the grant layer masked the
executor's own trade-identity check. A direct executor test now kills it by assertion failure,
not by error.

**Existing tests changed, all aligned and none weakened:**
- M2's `close_position` calls now pass a close authorization.
- The operations allow-list test includes `INSTRUMENT_DETAILS` (a GET).
- The fake broker states `pendingOrderCount` and serves `instruments`.
- Three M1/M2 mutants were retargeted after the close parser duplicated their text: A1, A4
  and J10 (the append-only tuple).

## 6. Assumptions that only the first real trade can settle

These come from the v20 documentation and are encoded in the fixtures; none has been observed
on the practice account.

1. **The fill.** The `ORDER_FILL` carries `tradeOpened` with `tradeID`, signed `units` and
   `price`, and `pl`, `financing`, `commission` and `accountBalance`.
   - The trade ID is the fill transaction's ID.
   - `clientOrderID` may be absent; that is tolerated.
2. **The stop.** `stopLossOnFill` creates a `STOP_LOSS_ORDER` transaction with this `tradeID`
   and the stop price, and `GET trades/{id}` embeds `stopLossOrder` with `state: PENDING`.
   **If the real shape differs, the first trade halts as `UNPROTECTED_POSITION`, fail-closed,
   and needs a close.**
3. **The close.** The `PUT …/close` response carries an `orderFillTransaction` with
   `tradesClosed[{tradeID, units, price, realizedPL, financing}]`, and the linked stop is
   cancelled with a balance-neutral `ORDER_CANCEL`.
4. **The sign model** (`pl + financing − commission − guaranteedExecutionFee`) on a real fill.
   Whether your M3 run actually checked this on a balance-changing transaction is not in the
   result you relayed. If it wasn't, the first trade's reconciliation is its first test, and a
   mismatch halts.
5. **The stop-distance floor** (5 pips, and twice the spread) is MOGO's own, not the broker's.
   If the broker rejects the stop anyway, the order is REJECTED or CANCELLED, which is harmless:
   no position.
6. **One unit.** At 1 unit, P&L amounts are sub-cent (4 decimal places). Accounting tolerates
   half a unit of the reported precision. A larger size up to 1,000 units still fits under $5
   with a 20-pip stop. Choosing it is yours.
7. **Clock.** The quote age is measured against this machine's clock, and skew beyond 5 seconds
   refuses.

## 7. Operator sequence

Run these **in your own terminal** (no sandbox proxy, so no `--use-env-proxy`).
`--cafile /etc/ssl/cert.pem` is needed on this machine, because Homebrew Python trusts no CAs.

```
cd ~/Desktop/"Forex Hub"/.claude/worktrees/m1-practice-executor
mkdir -p ~/.mogo/practice_state && chmod 700 ~/.mogo/practice_state
```

### 1. Write the entry authorization, just before use

Base the stop on the current price, for example bid − 0.00200 for a 20-pip stop on a BUY.
Save it as `~/.mogo/order-0001.json`:

```json
{"authorizationId": "AUTH-20261105-0001", "mode": "BROKER_PRACTICE", "accountId": "<your practice account id>",
 "instrument": "EUR_USD", "direction": "BUY", "units": 1, "stopLossPrice": "<bid minus 0.00200, 5 decimals>",
 "maxSlippage": "0.00010", "maxSpread": "0.00030", "maxLoss": "5", "maxQuoteAgeSeconds": 10,
 "issuedAt": "<now, e.g. 2026-11-05T14:00:00Z>", "expiresAt": "<now + 1h>", "issuedBy": "<your name>"}
```

### 2. Dry run (reads only, under A2)

```
python3 execution/mogo_practice_trade.py dry-run --state-dir ~/.mogo/practice_state --order-authorization ~/.mogo/order-0001.json --cafile /etc/ssl/cert.pem
```

Check `worstCaseLoss`, the exact `request`, and `brokerConstraints`. Any refusal lists every
code.

### 3. Authorize A3

Send one message: *"A3: submit practice order AUTH-20261105-0001 (EUR_USD BUY 1 unit, stop
<price>) to practice account `101-***-****-001`."* Then submit, or have me submit:

```
python3 execution/mogo_practice_trade.py submit --state-dir ~/.mogo/practice_state --order-authorization ~/.mogo/order-0001.json --authorization A3 --cafile /etc/ssl/cert.pem
```

- **Exit 0:** `position.state` is `PROTECTED`. Note `position.clientOrderId` and
  `position.trade_id`.
- **Exit 1:** refused, cancelled or rejected. No position exists.
- **Exit 3:** **stop.** The outcome is uncertain or the position is unprotected. Run
  `reconcile`, then follow the emergency procedure below.

### 4. Check at any time (reads only)

```
python3 execution/mogo_practice_trade.py reconcile --state-dir ~/.mogo/practice_state --cafile /etc/ssl/cert.pem
```

### 5. Close: a separate authorization

Save `~/.mogo/close-0001.json`:

```json
{"closeAuthorizationId": "CLOSE-20261105-0001", "mode": "BROKER_PRACTICE", "accountId": "<your practice account id>",
 "clientOrderId": "<position.clientOrderId>", "tradeId": "<position.trade_id>",
 "issuedAt": "<now>", "expiresAt": "<now + 1h>", "issuedBy": "<your name>"}
```

```
python3 execution/mogo_practice_trade.py close --state-dir ~/.mogo/practice_state --close-authorization ~/.mogo/close-0001.json --cafile /etc/ssl/cert.pem
```

Exit 0 means `position.state` is `RECONCILED`, with entry, exit, realized P&L, financing,
commission, net P&L and the balance after, all from broker fills. If the broker's stop fires
first, there is nothing to close: `reconcile` books the stop's fill the same way.

### Emergency stop

1. **Stop new entries:**
   ```
   python3 execution/mogo_practice_executor.py kill --state-dir ~/.mogo/practice_state --reason "<why>"
   ```
   or `touch ~/.mogo/practice_state/KILL`. Closes still work.
2. **Flatten the trade.** Either:
   - write a close authorization and run `close` as in step 5; or
   - if MOGO itself is in doubt, close the trade in the **OANDA fxTrade Practice platform**.
3. **Record it.** Run `reconcile` afterwards. A close made in the platform is booked from its
   fill, and accounting still has to agree.
4. **Remember the stop.** The broker-side stop protects the position whatever state MOGO is in.
5. **For a total stop**, revoke the practice token in **Manage API Access**.
6. **Halts** (`status` shows them) never clear themselves. Investigate, then run
   `clear-halt --halt <seq> --by <you> --reason <why>`. Releasing the kill switch is
   `release-kill --confirm`.

**Running from this session instead:** add `--use-env-proxy` and allow
`api-fxpractice.oanda.com` for that command. Output never contains the token or the account ID.

## 8. Next action

Do steps 1 and 2 yourself, then send the A3 message in step 3. Nothing writes to the broker
until then.

# MOGO M1: offline OANDA practice-executor core

**Date:** 2026-11-03.

**Authority:** operator authorization A1, approved for offline implementation only.

**Design:** `MOGO_FIRST_PAPER_TRADE_READINESS.md` (commit `1cbb6f7e6`), §5–§7.

**What did not happen.** No broker order was placed, no account was connected, and no credentials
were used. Nothing was pushed, merged or deployed. No trading setting was changed. The tests made
zero network attempts.

## 1. Where it is

| | |
|---|---|
| Worktree | `.claude/worktrees/m1-practice-executor` |
| Branch | `claude/m1-oanda-practice-executor-20261103` |
| Base | `origin/mogo-main` = `1720f8765444f3cfdcbc9912ef7973c810bdb8a7` (`git ls-remote`, 2026-11-03) |
| Implementation commit | `5217ef17f` |
| Report commit | the next commit on the branch |
| R-5 (`claude/r5-forward-import-20261103`, `031bd605e`) | untouched |

## 2. Changed files (all new; no existing file modified)

| File | Purpose |
|---|---|
| `execution/oanda_practice/config.py` | Defines the practice host as a constant. Loads credentials from a mode-0600 file outside the repo. Refuses host, url or environment keys, and any value naming the live host family. Holds the token in a `Secret`, which cannot be printed or pickled |
| `execution/oanda_practice/transport.py` | The only place a request is formed: an operation allow-list (6 operations), shape-checked parameters, and a caller-supplied account refused. The final URL must be https on the practice host. The kill switch is re-checked on every write. The token goes only into the header. `NetworkDisabledOpener` is the default, and `RecordingOpener` serves dry runs |
| `execution/oanda_practice/adapter.py` | The `BrokerAdapter` interface, and its OANDA v20 practice implementation, which normalises results and classifies submits |
| `execution/oanda_practice/authorization.py` | A one-shot operator authorization: expiring, bound to one account, giving a deterministic client order ID, with hard ceilings |
| `execution/oanda_practice/risk.py` | Pure pre-trade checks that report every refusal code |
| `execution/oanda_practice/journal.py` | The SQLite write-ahead journal: an atomic reserve, append-only triggers, validated transitions, refusals and halts |
| `execution/oanda_practice/kill.py` | The file-based kill switch. It fails closed if its directory is missing, and releasing it needs explicit confirmation |
| `execution/oanda_practice/executor.py` | Runs the submit sequence and reconcile, and reports status |
| `execution/oanda_practice/{errors,timeutil,__init__}.py` | The failure vocabulary and RFC3339 parsing |
| `execution/mogo_practice_executor.py` | The offline CLI: `status`, `kill`, `release-kill --confirm`, `clear-halt`, `check-authorization`. It deliberately has **no `submit` command** |
| `tests/execution/fake_oanda.py` | An in-process fake of the v20 endpoints, injected as the transport's opener, with 11 scripted submit behaviours |
| `tests/execution/test_oanda_practice.py` | 53 tests |
| `tests/execution/mutate_oanda_practice.py` | The mutation gate, 70 mutants |

## 3. What the core does

**Modes stay separate.** The package's mode is `BROKER_PRACTICE` and its order tag is
`MOGO_BROKER_PRACTICE`. It contains no reference to the research corpus, the importer or
`index.html`. It refuses to keep state under the repository's `docs/` or `evidence/`. **No live
mode exists to switch to:** there is no live host constant, no selector, and no config key that
could change the host.

**Submit sequence**, in this order:

1. The kill switch is checked. If engaged, nothing is read or sent.
2. The authorization must be for the configured account, inside its validity window, and not yet
   used.
3. Any active halt, or any SUBMITTING or UNCERTAIN intent, blocks the order.
4. The broker reads (account summary, quote, open trades) must all succeed. A summary for another
   account refuses the order.
5. The risk checks run:
   - quote currency must equal the account currency;
   - the instrument must be tradeable;
   - the quote must be no older than `maxQuoteAgeSeconds` (at most 30) and no more than 5 s in the
     future;
   - the bid and ask must be valid, and the spread no wider than the limit;
   - the stop must be on the correct side, BUY and SELL;
   - the loss at the stop is computed from the **price bound**, not from the quote;
   - the broker account must have no open trades, and the journal no open exposure.
6. The request is built:
   - a `MARKET`, `FOK`, `OPEN_ONLY` order with a `priceBound`;
   - a **mandatory** `stopLossOnFill` (GTC);
   - `clientExtensions.id` and `tradeClientExtensions.id` = `MOGO-` followed by the first 16 hex
     characters of `sha256(authorizationId)`, so the same authorization always maps to the same
     order identity.
7. **A dry run stops here.** It returns the request, writes nothing to the journal, sends nothing,
   and does not consume the authorization.
8. **Write-ahead reserve.** Inside `BEGIN IMMEDIATE`, the checks are repeated and SUBMITTING is
   committed (`synchronous=FULL`) before anything is sent.
9. The kill switch is checked again. If engaged, the intent becomes `ABORTED_BEFORE_SEND`. The
   transport checks it a third time at the moment of sending.
10. The order is sent. The outcome is **FILLED** only when the broker's ORDER_FILL carries the opened
    trade, its price, its units (equal to the requested units) and a matching client ID. It is
    **CANCELLED** on an ORDER_CANCEL, and **REJECTED** on a reject transaction or a 400/401/403/404/405.
    Everything else is **UNCERTAIN**: 5xx, 429, timeouts, unparseable bodies, a create with no fill
    or cancel, a fill missing its trade, a partial fill, or a fill naming another client ID.

**Uncertainty and restart.** An UNCERTAIN or SUBMITTING intent is **never resubmitted**.
`reconcile()` resolves it from two broker sources: the order looked up by client ID, and the
transactions since the `lastTransactionID` recorded before the submit.

- **FILLED** requires the order state, exactly one fill transaction, and agreement on the trade.
- **NOT_SUBMITTED** (absent) requires the lookup to report not-found **and** no transaction to
  mention the client ID.
- A failed read, a disagreement, or a pending state leaves the intent UNCERTAIN, and new orders
  stay blocked.
- A MOGO-tagged broker trade that the journal does not know raises a **halt**. Clearing a halt
  records who cleared it and why, and the halt record itself is never edited.

**Duplicate protection** works in three layers:

- the submit gate;
- the atomic reserve, which re-checks across processes;
- the schema, where `authorization_id` and `client_order_id` are UNIQUE.

An authorization can place at most one order, ever, including after a refusal-then-retry or a crash.

**For M2.** `BrokerAdapter.close_trade()` and `transactions_for_accounting()` are declared and
refuse until M2. FILLED counts as open exposure, so M1 can never hold more than one practice trade.

## 4. Test results

| Run | Result |
|---|---|
| `python3 -m unittest tests/execution/test_oanda_practice.py` | **Ran 53, OK** |
| `python3 tests/execution/mutate_oanda_practice.py` | **70/70 killed, 0 survived, 0 unapplied, sources restored byte-identical: PASS** |
| `tests/platform/test_runtime_change_detection_wiring.py` (scans the whole repo) | Ran 28, OK |
| `tests/platform/test_platform_boundaries.py` | OK |
| `tests/count_python_tests.py --check` | Unchanged: the only drift is the pre-existing `test_engine_provenance` item. The new suite is not in that gate's scope (§6) |

The full Python lane was not re-run. No existing file changed, and the two repo-scanning gates
above were run directly.

**Zero network, shown three ways:**

1. Inside the test process, `socket.connect`, `connect_ex`, `create_connection` and `getaddrinfo`
   are replaced with recorders that raise.
2. A `sys.addaudithook` recorder captures every `socket.*` audit event, including socket creation
   at C level.
3. Every test's `tearDown` asserts that no attempt was recorded. Two positive-control tests show
   both guards really detect an attempt.

On top of that, an AST test proves that no package module imports `socket`, `ssl`, `http`,
`urllib.request`, `requests`, `asyncio` or `subprocess`.

**Coverage by readiness-report test ID:**

| ID | What is covered |
|---|---|
| T-HOST | Every operation resolves to the practice host. No source file names the live host family. Host, environment and url keys are refused. Parameter injection and unknown operations are refused. The final host assert holds even with the base URL monkeypatched. File permissions are enforced |
| T-AUTH | 15 malformed variants, unknown or missing fields, an expired authorization, a not-yet-valid one, another account, and single use |
| T-RISK / T-PRICE | Loss at the stop, stop side for BUY and SELL, currency, open broker trades, stale / untradeable / wide / future-skewed / invalid / missing-time / unparseable quotes, and a failed read on each of the three reads. Refusals are journaled and do not consume the authorization |
| T-KILL | Engaged before submit (zero requests), engaged during the reads, a direct transport write, the transport's last-moment check, a missing directory reading as engaged, and release requiring confirmation |
| T-DUP | An open fill blocks a new order, two journal connections cannot both reserve, and the schema UNIQUE refuses a direct insert |
| T-UNCERT | Five committed-but-unknown behaviours resolve to FILLED with exactly 1 POST; a fill missing its trade stays UNCERTAIN; unsent orders resolve to NOT_SUBMITTED; a partial fill is not a fill; an unreachable broker stays UNCERTAIN; absence needs both sources to agree; 4 evidence disagreements move nothing; a fill for another client ID is refused |
| Restart | A crash between reserve and send never sends; a crash after the broker committed resolves without resubmitting; an unknown MOGO broker trade halts |
| T-SECRET | Fills, rejects, timeouts and failed reads with the token's exact string: it appears in no stdout or stderr output, exception text, status output, CLI output or journal file byte. A `Secret` cannot be shown or pickled |
| T-MODE | State is refused under `docs/` and `evidence/`, and the package does not reference the corpus, the importer or the simulator |

## 5. Deterministic mock lifecycle

`test_a_fill_is_journaled_write_ahead_with_complete_broker_evidence`:

- The fake broker sees the POST while the journal already holds SUBMITTING.
- The outcome is FILLED with 1000 units at 1.10010 and a trade ID.
- The events read `SUBMITTING → FILLED`.
- The stored request carries MARKET/FOK/OPEN_ONLY, stop 1.09800, bound 1.10020, and the
  deterministic client ID on both the order and the trade.

Any deviation from the evidence the broker should provide either refuses the order or leaves it
UNCERTAIN.

## 6. Blockers and limits (none block M1)

- **Gate registration.** The new suite sits outside the registered Python lane. `run_all.sh` and
  `count_python_tests.py` only enumerate `tests/trader_intelligence`. Registering it means adding
  `tests/execution` to both, and that changes shared gate infrastructure, so it is left for your
  approval as a small separate change. Until then, run the two commands in §4.
- **Durability under power loss** (`synchronous=FULL`) is configured but not testable here.
- **Practice versus live account IDs.** Only the shape of the account ID is validated. The real
  separation rests on three things: a practice token only authenticates against the practice host,
  that host is fixed, and no live host exists in the code.
- **Assumptions about OANDA's API.** Response shapes follow the published v20 schema for the fields
  read: ORDER_FILL `clientOrderID` and `tradeOpened`, and `orders/@{clientID}` lookup. They have not
  been checked against the real practice API, and could not be offline. They are the first thing
  M3's read-only preflight confirms.
- **Stop gaps.** Loss at the stop is computed from the price bound. A stop that gaps beyond its price
  is not bounded by M1, and M2 measures it from fills.
- **Governance carry-over.** The A1b items remain your actions: a practice-only entry in
  `mogo_rules.json`, and updating the CLAUDE.md posture line.

## 7. Next action

Review `5217ef17f`, and decide on the gate registration in §6.

M2 (fill, close and accounting parsing, reconcile, and a G1 dry run reviewed by you) is also offline.
Starting it is your call: A1 was given for M1. M3, the first practice connection, needs **A2**.

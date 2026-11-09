# MOGO M3 preparation: governance install path, close-fill test, operator setup

**Date:** 2026-11-04.

**Authority:** local governance and focused test work only.

**What did not happen.**
- No credential was used and nothing connected to OANDA. No order, push, merge or deployment
  happened.
- `~/.claude/settings.json` was not modified. Its sha256 prefix `0f9e1024ac9281a0` is unchanged
  before and after every command.

## 1. State re-verified

| | |
|---|---|
| Branch | `claude/m1-oanda-practice-executor-20261103` (worktree `.claude/worktrees/m1-practice-executor`) |
| Tip before this work | `da33723d8`, with a clean tree |
| `origin/mogo-main` | `1720f8765` (`git ls-remote`), unchanged |
| Governance commit inspected | `a2e63c0d7` |

`a2e63c0d7` changes only `CLAUDE.md` (+15 lines) and `scripts/auto_mode/mogo_rules.json`
(one new soft-deny, plus one sentence appended to the MOGO posture entry). The exact diff is in
`MOGO_M2_OFFLINE_EXECUTION_REPORT.md` §7.

## 2. Would `build_auto_mode_config.py --write` stay inside the boundary? **No. Stopped.**

I compared the block that `--write` would install against the block installed now. I used the
generator's own functions, read-only.

| Section | Installed → generated | Changes |
|---|---|---|
| allow | 21 → 20 | **removes** `Scheduled-Task Fires` |
| environment | 28 → 28 | rewords `**MOGO trading posture**` (reviewed) and the shipped `**Repository visibility**` |
| soft_deny | 77 → 80 | adds `MOGO Broker-Practice Execution` (reviewed), plus the shipped `Account & Standing-Rule Changes` and `Unrequested Commit in a Connected App`; **rewords 6 shipped rules** |

How the shipped-default drift cuts:

- **Tighter:**
  - Real-World Transactions gains "transfers or crypto, placing trades, refunds or payouts";
  - Permission Grant gains document sharing;
  - Out-of-Place Publication treats "unverified" visibility as public;
  - Self-Modification adds `.claude/dev-mods/`;
  - two new soft-denies.
- **Looser:**
  - **Git Destructive** narrows to destroying *someone else's* work: "if unclear, do not
    block", and amend, rebase and force-pushing a personal branch become normal;
  - **External System Writes** adds PR comment, title and draft allowances;
  - removing **Scheduled-Task Fires** drops an allow entry whose text says that a scheduled
    prompt does *not* meet any soft-block's consent bar.

So `--write` would change protections unrelated to the practice boundary, some of them in the
loosening direction. That is the stop condition, and it was not run.

## 3. The smallest safe alternative: a delta-only install (built and rehearsed, not run on your settings)

`scripts/auto_mode/install_mogo_delta_only.py` (new):

- Changes **only MOGO-labelled entries**, and only to match `mogo_rules.json`.
- Refuses unless the set of changed labels **equals** the reviewed set: by default,
  `environment|**MOGO trading posture**` and `soft_deny|MOGO Broker-Practice Execution`.
- Asserts that every non-MOGO rule, every section's order, and every other key in the settings
  file are unchanged.
- Inserts the new rule directly after `MOGO Live-Money Capability`.
- Never calls the `claude` CLI and never reads the shipped defaults.
- Is a dry run by default. `--write` takes the generator's timestamped backup, writes, re-reads
  and verifies.

**Rehearsal.** The dry run read the real settings, which stayed byte-identical. A real `--write`
ran on a **copy** of `~/.claude/settings.json` in the session scratchpad, which has since been
deleted.

| Check | Result |
|---|---|
| Dry run against the real settings | 2 changes listed; nothing written (hash unchanged) |
| An unexpected change set (`--expect` naming only the soft-deny) | **refused**, rc 1, copy byte-identical |
| `--write` on the copy | `INSTALLED and verified: only the expected MOGO rules changed.` |
| Independent comparison of the copy before and after | allow 21 → 21, nothing changed; environment 28 → 28, only `**MOGO trading posture**` changed; soft_deny 77 → 78, only `MOGO Broker-Practice Execution` added; every other settings key identical |
| `MOGO Live-Money Capability` | byte-identical; the new rule sits immediately after it |
| `Scheduled-Task Fires` and the 6 shipped rules discussed above | untouched |

**Effective state now.** `claude auto-mode config` reports 77 soft-denies. `MOGO Live-Money
Capability` is present, and `MOGO Broker-Practice Execution` is **absent**.

**I did not install it.** The sandbox denies my writes to `~/.claude/settings.json`, and editing
it is a Self-Modification boundary, so you have to run it (§7).

**The shipped-default drift stays deferred.** Reconciling it is a separate decision for you. It
contains the loosenings listed in §2. After the delta install, `build_auto_mode_config.py --check`
will still report drift, and that is expected.

## 4. The multiple-close-fills refusal test

`test_two_close_fills_for_one_trade_halt_and_book_nothing`:

- the broker's stop fills;
- a second ORDER_FILL claiming to close the same trade is appended;
- reconcile must halt `MULTIPLE_CLOSE_FILLS <trade>`, book nothing (the position stays
  PROTECTED), and block new orders.

Mutant **X13** (removing that halt) is added to the gate. The registered count for
`test_oanda_practice_m2` goes from 36 to 37. No executor code changed.

| Run | Result |
|---|---|
| `tests.execution.*` (registered enumeration) | **90 run, OK** (53 + 37), with `-W error::ResourceWarning` clean |
| `tests/execution/mutate_oanda_practice.py` | **107/107 killed** (X13 included), sources restored: PASS |
| `count_python_tests.py --check` | executor suites in sync (53, 37); only the pre-existing `test_engine_provenance` drift |

## 5. Will M3 use only the practice host, GET and the selected account?

**In place today** (M1/M2 code, with the test and mutant that pin each property):

| Property | Where | Evidence |
|---|---|---|
| Only `https://api-fxpractice.oanda.com` | `config.PRACTICE_HOST` constant; the transport re-parses every URL and asserts https, the practice host and no port | T-HOST tests; mutant T1 (and the base-URL monkeypatch test) |
| No live host and no selector anywhere | no live constant, and config refuses host, url, env and environment keys and any value naming the live family | source scan test; C1, C2 |
| No endpoint override or fallback | callers name an operation, never a URL; parameters are shape-checked; a caller-supplied `account` is refused | T2, T3, T4 |
| The account is only the configured one | the account ID comes from the credentials file; authorizations and summaries naming another account are refused | A5, E6 |
| No network today | the default opener sends nothing; no module imports socket, http, ssl or urllib.request | AST ban; T7 |

**What M3 must add, and its acceptance criteria.** M3 is the first code with a network path,
under A2.

1. **A read-only opener.**
   - It uses the stdlib, with TLS verification on (the default context) and redirects refused.
   - It **refuses any method other than GET before opening a socket**. This is the second
     barrier. The transport's allow-list still contains `CREATE_ORDER` and `CLOSE_TRADE`, so
     GET-only must be enforced in the opener itself.
   - It is **injected only by the M3 preflight command**. `NetworkDisabledOpener` stays the
     default everywhere else, and there is still no `submit` or `close` CLI command.
2. **The preflight's allowed operations:** `ACCOUNT_SUMMARY`, `PRICING` (one instrument),
   `OPEN_TRADES`, `TRANSACTIONS_SINCE`, plus `ORDER_BY_CLIENT_ID` for a client ID that must not
   exist (to observe the 404 shape).
3. **Tests**, against fakes before any real call:
   - a POST or PUT through the M3 opener raises before any socket (mutation-tested);
   - a redirect is refused;
   - the host is still asserted.
4. **Proxy environment.** urllib honours `HTTPS_PROXY`. The opener should either pass through
   explicitly with the proxy disclosed, or disable proxies. That decision belongs in M3.

## 6. Response-shape assumptions the first read-only connection must verify

None of these has been observed on a real practice account. M3's preflight should record raw
bytes and hashes for each, and report observed versus assumed:

1. **Account summary.** The fields `id`, `currency`, `balance` (a decimal string),
   `lastTransactionID` (a string), and `openTradeCount` (an int). Confirm that the account
   currency equals the quote currency of the first instrument; EUR_USD needs a USD account.
2. **Account ID format.** It must match `NNN-NNN-NNNNN…-NNN`, the config's shape check.
3. **Pricing.** With `Accept-Datetime-Format: RFC3339`: `time` as a Z-suffixed RFC3339 string with
   up to 9 fractional digits; `tradeable` as a boolean; `bids[0].price` and `asks[0].price` as
   strings. Also measure the quote age against the local clock, to check skew.
4. **`openTrades`.** A `trades` list. Empty is the expected state for a dedicated account.
5. **`transactions/sinceid`.**
   - **Whether it pages or caps its results.** A truncated window is refused by the contiguity
     check, but a cap would make reconcile unable to finish.
   - `lastTransactionID` as a string, and transaction IDs that run contiguously.
6. **The sign model.** Check it on any existing balance-changing transactions in the account's
   history: `accountBalance` present, and balance change = `pl + financing − commission −
   guaranteedExecutionFee`. A brand-new account may have none (only `CREATE` or a funding
   transaction), in which case this stays unverified until the first trade. If so, the report
   must say so.
7. **`orders/@{clientID}`** for a non-existent ID. Check the 404 status and its
   `errorCode` / `errorMessage` shape.
8. **Not verifiable read-only** (they stay assumptions until A3): ORDER_FILL `clientOrderID` /
   `tradeOpened` / `tradesClosed`, `stopLossOrder` in trade details, and STOP_LOSS_ORDER
   transactions.

## 7. Exact operator setup

None of these steps involves pasting anything into chat.

1. **Install the reviewed governance boundary, and only that.** Run it from the worktree:
   ```
   ! cd ~/Desktop/"Forex Hub"/.claude/worktrees/m1-practice-executor && python3 scripts/auto_mode/install_mogo_delta_only.py
   ! cd ~/Desktop/"Forex Hub"/.claude/worktrees/m1-practice-executor && python3 scripts/auto_mode/install_mogo_delta_only.py --write
   ```
   Verify the effective state:
   ```
   ! claude auto-mode config | python3 -c "import json,sys; d=json.load(sys.stdin); s=d['soft_deny']; print(len(s), any(r.startswith('MOGO Broker-Practice') for r in s), any(r.startswith('MOGO Live-Money') for r in s))"
   ```
   The expected output is `78 True True`.
2. **Create or designate a dedicated OANDA practice account** (fxTrade Practice), denominated in
   USD and holding no other trades. Note its account ID.
3. **Generate a practice API token** in the OANDA practice portal. Check whether doing so revokes
   the token the browser app currently uses for prices.
4. **Write the credentials file locally**, with no echo, nothing in shell history, and no
   overwrite of an existing file. Run it in **your own terminal** (not with `!`, because the
   token prompt must not pass through this session):
   ```
   mkdir -p ~/.mogo && chmod 700 ~/.mogo
   python3 -c 'import getpass,json,os; a=input("Practice account ID: ").strip(); t=getpass.getpass("Practice token (hidden): ").strip(); p=os.path.expanduser("~/.mogo/oanda_practice.json"); fd=os.open(p, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600); os.write(fd, json.dumps({"accountId": a, "token": t}).encode()); os.close(fd); print("written", p)'
   ```
   Check it offline. This makes no network call and prints the token redacted:
   ```
   cd ~/Desktop/"Forex Hub"/.claude/worktrees/m1-practice-executor && python3 -c 'import sys; sys.path.insert(0,"execution"); from oanda_practice import config; print(config.load_config())'
   ```
   The expected output is `PracticeConfig(account_id='…', token=<redacted>)`. Only the
   `accountId` and `token` keys are accepted; host, url and environment keys are refused.

## 8. The single next action

When steps 1 to 4 are done, authorize **A2** in one message that names the practice account ID
and says: *"A2: read-only, GET-only M3 preflight against practice account `<ID>`, using
`~/.mogo/oanda_practice.json`."*

That one approval covers building the GET-only opener and preflight (§5), its offline tests, and a
single read-only run that verifies §6. It does not cover any order, close, autonomous mode, push
or deploy. A3 stays separate.

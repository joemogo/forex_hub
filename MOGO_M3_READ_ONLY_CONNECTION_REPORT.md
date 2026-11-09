# MOGO M3: read-only OANDA practice connection

**Date:** 2026-11-05.

**Authority:** A2. Read-only GET requests against the selected practice account.

**Result: STOPPED at the first GET. OANDA rejected the credentials (HTTP 401 or 403).**
- The read-only boundary is built, tested and mutation-verified.
- No response shape could be observed, so none of the M2 assumptions has been verified yet.
- No order, close, cancel, POST, PUT, push, merge or deploy happened.
- The browser app, the research engine, simulated PAPER mode and the strategies are untouched.
- The account is reported masked throughout as `101-***-****-001`. No token, header, balance,
  price or transaction id appears in this report, in the commits or in the session output.

## 1. Starting point, re-verified

| Check | Result |
|---|---|
| Branch | `claude/m1-oanda-practice-executor-20261103`; tip `f393e3e46` with a clean tree before this work |
| Governance | `claude auto-mode config` reports 78 soft-denies, with `MOGO Broker-Practice Execution` present and `MOGO Live-Money Capability` present |
| `~/.mogo` | mode `drwx------`, owned by the operator |
| `~/.mogo/oanda_practice.json` | mode `-rw-------`, keys exactly `accountId` and `token`. `load_config()` accepts it. The token has OANDA's `32hex-32hex` shape with no whitespace, quotes or `Bearer` prefix (checked locally as booleans; the token was never printed) |

## 2. The read-only boundary (new, `execution/oanda_practice_m3/`)

This package lives outside `execution/oanda_practice/` on purpose. The core package's network
import ban stays exactly as M1 and M2 proved it.

| Barrier | Where | Refuses, before any socket exists |
|---|---|---|
| 1. Read-only transport | `ReadOnlyTransport.request` | any operation outside the six GET reads (`ACCOUNT_SUMMARY`, `PRICING`, `OPEN_TRADES`, `ORDER_BY_CLIENT_ID`, `TRANSACTIONS_SINCE`, `TRADE_DETAILS`); `CREATE_ORDER` and `CLOSE_TRADE` never reach the opener; it accepts only the read-only opener |
| 2. Read-only opener | `ReadOnlyHttpsOpener.check` | any method other than `GET` (including `POST`, `PUT`, `PATCH`, `DELETE`, `HEAD`, `OPTIONS` and lower-case `get`); any body; any scheme other than `https`; any host other than `api-fxpractice.oanda.com`; any explicit port (even `:443`); userinfo; fragments; any path not under `/v3/accounts/<configured account>/`; `..` and `//` path escapes; CR/LF in headers |
| 3. Core transport (unchanged) | `tp.Transport.url_for` | operations outside the allow-list, wrong parameter shapes, a caller-supplied `account`, a final URL off the practice host |

Behaviour after the checks:

- **Redirects:** `http.client` never follows them, and any 3xx answer raises `RedirectRefused`.
  The preflight treats that as a boundary stop.
- **TLS:** the default context, so certificate and hostname verification are always on.
  `--cafile` may add a trust bundle. `verifying_context()` refuses any context that does not
  verify.
- **Proxy:** used only with `--use-env-proxy`, and only if it is http on a loopback address. It
  carries a `CONNECT` tunnel, so TLS stays end-to-end to the practice host. The proxy sees the
  host name; it does not see the request, the token or the response. `HTTPS_PROXY` is never
  read implicitly.
- **Secrecy:** no exception or report carries a URL, header, token or account id.
- **Command:** `execution/mogo_practice_preflight.py --authorization A2` is the only command that
  opens a broker socket. Without `A2` it refuses before reading the credentials.

**One narrow test change.** The M1 import ban scanned all of `execution/`. It now exempts exactly
one file, `oanda_practice_m3/readonly.py`, for exactly `http.client` and `ssl`. It also asserts
that the exemption is still in use, so a stale exemption fails. Positive controls (each turned
the ban test red):

- `readonly.py` importing `subprocess`;
- `preflight.py` importing `ssl`;
- the exemption made stale.

During this work the ban also caught the CLI importing `ssl`. The helper was moved into the
exempt file; the exemption was not widened.

## 3. Focused tests

| Run | Result |
|---|---|
| `tests.execution.test_oanda_practice_m3` | **30 OK**, `-W error::ResourceWarning` clean |
| M1 + M2 + M3 suites together | **120 OK** (53 + 37 + 30) |
| `tests/execution/mutate_oanda_practice_m3.py` | **21/21 killed**, sources restored: PASS |
| `tests/execution/mutate_oanda_practice.py` (M1/M2) | **107/107 killed**, sources restored: PASS |
| `count_python_tests.py --check` | executor suites in sync (53, 37, 30); only the pre-existing `test_engine_provenance` drift remains |

How the zero-socket proof is made:

- The socket functions are replaced by recorders that raise, and an interpreter audit hook
  records every `socket.*` event.
- Prohibited requests go through the **real** `http.client` stack and must record zero events.
- **Positive control:** a permitted GET through the same real stack does reach the socket layer.
  So the zeros are measured, not vacuous.

The M3 mutation gate kills each of these when deleted:

- GET-only, no body, practice host, configured account, path escape, header injection;
- redirect refusal, loopback-only proxy, tunnel target, TLS verification;
- the transport allow-list and the opener-type check;
- the credentials and account stops, account masking;
- the cap, currency and sign-model checks, redirect-as-boundary;
- the A2 requirement on the command.

Registration:
- `tests/expected_python_test_counts.tsv` gains `test_oanda_practice_m3 30`;
- `tests/run_all.sh` runs the M3 mutation gate after the M1/M2 gate.

## 4. Live GET attempts (all to `api-fxpractice.oanda.com`, through the loopback CONNECT tunnel)

| # | What | Outcome |
|---|---|---|
| 1 | Preflight, request 1 (`GET …/summary`) | **TLS handshake failed before any HTTP request**: `CERTIFICATE_VERIFY_FAILED`. The token was not sent |
| 2 | Diagnosis: the same GET, printing only the exception type | the same TLS failure; nothing sent |
| 3 | Diagnosis: CONNECT and TLS handshake only, no HTTP request, verified against `/etc/ssl/cert.pem` | **verified**. Subject `api-fxpractice.oanda.com`, issuer Google Trust Services WE1, SAN matches |
| 4 | Preflight with `--cafile /etc/ssl/cert.pem`, request 1 (`GET …/summary`) | **401 or 403: `CREDENTIALS_REJECTED`. Stopped. No further request** |

**About the TLS failure.** This interpreter (`/usr/local/opt/python@3.14`) loads zero CA
certificates, because Homebrew's `/usr/local/etc/openssl@3/cert.pem` is missing. That is a local
trust-store gap, not interception: attempt 3 shows the chain the tunnel delivers verifies against
the public CAs that macOS ships. Use `--cafile /etc/ssl/cert.pem` on this machine. Verification
stays on either way.

**The credential rejection.** The run only recorded that OANDA answered 401 or 403, not which
one. The preflight now records `stop_http_status`, so the next attempt will say which. The token
is well-formed, so the likely causes are:

1. **A token from the live (fxTrade) login rather than the practice login.** Tokens are specific
   to their environment.
2. **A token that has since been revoked or regenerated.** Generating a new one revokes the old.
3. **An account ID that belongs to a different OANDA user than the token** (this would be 403).

## 5. Response shapes versus the M2 assumptions

**None was observed.** Every item in `MOGO_M3_PREPARATION.md` §6 is still an assumption:

- the summary fields, account currency and open-trade count;
- the pricing time format, `tradeable` and quote age;
- `openTrades`;
- `transactions/sinceid` paging or a cap, and contiguity;
- the sign model;
- the shape of the 404 for a missing order.

The preflight that checks them is built and offline-tested against the fake, and runs in one
step once the credentials are accepted.

**Blockers for M4:**
- **Real:** the credentials (§4). Until they are accepted, nothing in M4 can start.
- **Discrepancies between observed shapes and M2's assumptions:** none known, because none could
  be observed.

## 6. Commits (local only, not pushed)

| Commit | Content |
|---|---|
| `8a8454788` | M3: the read-only GET boundary and preflight (offline-verified) |
| this commit | `--cafile` with a verifying context, `stop_http_status`, mutant R13, and this report |

## 7. The exact next step (operator)

1. **Check the token's environment.** Log in to **OANDA fxTrade Practice**, not the live login,
   and open **Manage API Access**. If the token on file may be a live token or an old one,
   generate a new practice token. That revokes the previous one; the browser app will then need
   it on its next connect.
2. **Check the account ID.** In that same practice login, confirm it is listed under that user.
3. **Replace the file** in your own terminal. The writer refuses to overwrite, so remove the old
   file first:
   ```
   rm ~/.mogo/oanda_practice.json
   python3 -c 'import getpass,json,os; a=input("Practice account ID: ").strip(); t=getpass.getpass("Practice token (hidden): ").strip(); p=os.path.expanduser("~/.mogo/oanda_practice.json"); fd=os.open(p, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600); os.write(fd, json.dumps({"accountId": a, "token": t}).encode()); os.close(fd); print("written", p)'
   ```
4. **Re-run the preflight.** Either reply *"credentials replaced; re-run the M3 preflight"* (A2
   already covers the same read-only GETs), or run it yourself in your own terminal. Without the
   sandbox proxy there, drop `--use-env-proxy`:
   ```
   cd ~/Desktop/"Forex Hub"/.claude/worktrees/m1-practice-executor && python3 execution/mogo_practice_preflight.py --authorization A2 --cafile /etc/ssl/cert.pem
   ```
   It prints a masked report. Exit 0 means every shape check passed, 1 means a check failed or
   the run stopped, and 2 means it refused before running.

M4 (any order) stays unauthorized and needs A3.

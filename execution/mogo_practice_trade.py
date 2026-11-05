#!/usr/bin/env python3
"""MOGO broker-practice M4: one practice trade, step by step, each step its own operator act.

    dry-run    --state-dir DIR --order-authorization FILE                   reads only (A2)
    submit     --state-dir DIR --order-authorization FILE --authorization A3   ONE entry, then verify protection
    reconcile  --state-dir DIR                                              reads only (A2)
    close      --state-dir DIR --close-authorization FILE                   ONE close of the named trade, then reconcile

    common: [--use-env-proxy] [--cafile PEM]

WHAT EACH COMMAND CAN SEND
  dry-run, reconcile  GET only: the read-only opener (oanda_practice_m3).
  submit              GETs, plus exactly one POST: the market order the authorization file
                      describes (oanda_practice_m4.a3.EntryGrant). Without `--authorization A3`
                      it refuses before reading the credentials.
  close               GETs, plus exactly one PUT: a full close of the trade the close
                      authorization names (CloseGrant). Allowed under the kill switch.

After `submit` fills, the command reconciles at once. The position must reach PROTECTED
(the broker holds a PENDING stop at exactly the authorized price). If it does not, a halt
is recorded and the command exits 3: close the trade (a close authorization, or the OANDA
platform) before anything else.

Exit codes: 0 done; 1 refused (nothing sent); 2 usage or not authorized; 3 operator
attention needed (halt, unprotected, or an outcome still UNCERTAIN). The output names
states, reasons, prices and P&L; it never prints the token or the account id.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from oanda_practice import adapter as ad                          # noqa: E402
from oanda_practice import authorization as authz                 # noqa: E402
from oanda_practice import config as cfg                          # noqa: E402
from oanda_practice import executor as ex                         # noqa: E402
from oanda_practice import journal as jn                          # noqa: E402
from oanda_practice import timeutil                               # noqa: E402
from oanda_practice import transport as tp                        # noqa: E402
from oanda_practice.errors import PracticeExecutionError          # noqa: E402
from oanda_practice.kill import KillSwitch                        # noqa: E402
from oanda_practice_m3.readonly import (ProxyRefused, ReadOnlyHttpsOpener,  # noqa: E402
                                        ReadOnlyTransport, verifying_context)
from oanda_practice_m4.a3 import A3WriteOpener, CloseGrant, EntryGrant   # noqa: E402


def _read(path):
    with open(path, "rb") as handle:
        return handle.read()


def _position_view(executor, intent_id):
    intent = executor.journal.intent(intent_id)
    pos = executor.journal.position(intent_id)
    view = {"clientOrderId": intent["client_order_id"] if intent else None,
            "intent": intent["state"] if intent else None, "intentReason": intent["reason"] if intent else None}
    if pos:
        view.update({k: pos[k] for k in ("trade_id", "state", "reason", "stop_order_id", "entry_price",
                                          "exit_price", "close_reason", "realized_pl", "financing",
                                          "commission", "net_pl", "balance_after")})
    view["activeHalts"] = [h["reason"] for h in executor.journal.active_halts()]
    return view


def _attention(view, want):
    return bool(view["activeHalts"]) or view.get("state") not in want or view["intent"] == jn.UNCERTAIN


def run(args, config, connection_factory=None, clock=timeutil.utc_now):
    """Run one command. Returns (exit_code, result). Injected factory and clock are for offline runs."""
    proxy = (os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")) if args.use_env_proxy else None
    net = {"proxy_url": proxy, "ssl_context": verifying_context(args.cafile),
           "connection_factory": connection_factory}
    state_dir = ex.check_state_dir(args.state_dir)
    now = clock()

    if args.command in ("dry-run", "reconcile"):
        transport = ReadOnlyTransport(config, ReadOnlyHttpsOpener(config.account_id, **net))
    elif args.command == "submit":
        auth = authz.parse_authorization(_read(args.order_authorization))
        grant = EntryGrant(auth, config, now)
        transport = tp.Transport(config, opener=A3WriteOpener(config.account_id, grant, **net),
                                 kill_switch=KillSwitch(state_dir))
    else:   # close
        close_auth = authz.parse_close_authorization(_read(args.close_authorization))
        grant = CloseGrant(close_auth, config, now)
        transport = tp.Transport(config, opener=A3WriteOpener(config.account_id, grant, **net),
                                 kill_switch=KillSwitch(state_dir))

    executor = ex.Executor(config, ad.OandaPracticeAdapter(transport), state_dir, clock=clock)
    try:
        if args.command == "dry-run":
            auth = authz.parse_authorization(_read(args.order_authorization))
            return 0, executor.submit(auth, dry_run=True)
        if args.command == "reconcile":
            report = executor.reconcile()
            return (3 if report["halted"] or report["unresolved"] else 0), report
        if args.command == "submit":
            row = executor.submit(auth)
            result = {"submit": {k: row[k] for k in ("state", "reason", "broker_trade_id", "fill_price",
                                                     "fill_units")}}
            if row["state"] == jn.FILLED:
                result["reconcile"] = executor.reconcile()
            result["position"] = _position_view(executor, auth.intent_id)
            if row["state"] in (jn.CANCELLED, jn.REJECTED):
                return 1, result
            return (3 if _attention(result["position"], (jn.PROTECTED,)) else 0), result
        # close
        intent_id = close_auth.client_order_id[len("MOGO-"):]
        pos = executor.close_position(intent_id, close_auth)
        result = {"close": {k: pos[k] for k in ("state", "reason", "exit_price", "close_reason")},
                  "reconcile": executor.reconcile(), "position": _position_view(executor, intent_id)}
        return (3 if _attention(result["position"], (jn.RECONCILED,)) else 0), result
    finally:
        executor.close()


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("dry-run", "submit", "reconcile", "close"):
        p = sub.add_parser(name)
        p.add_argument("--state-dir", required=True)
        p.add_argument("--use-env-proxy", action="store_true")
        p.add_argument("--cafile", default=None)
        if name in ("dry-run", "submit"):
            p.add_argument("--order-authorization", required=True)
        if name == "submit":
            p.add_argument("--authorization", required=True)
        if name == "close":
            p.add_argument("--close-authorization", required=True)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.command == "submit" and args.authorization != "A3":
        print(json.dumps({"stop": "NOT_AUTHORIZED", "detail": "a broker entry needs operator authorization A3"}))
        return 2
    try:
        code, result = run(args, cfg.load_config())
    except (PracticeExecutionError, ProxyRefused, OSError) as exc:
        detail = getattr(exc, "codes", None) or str(exc)
        print(json.dumps({"refused": type(exc).__name__, "detail": detail}, default=str))
        return 1
    except Exception as exc:  # noqa: BLE001 -- never print a traceback that could carry a header
        print(json.dumps({"stop": "UNEXPECTED_%s" % type(exc).__name__}))
        return 3
    print(json.dumps(result, indent=1, sort_keys=True, default=str))
    return code


if __name__ == "__main__":
    raise SystemExit(main())

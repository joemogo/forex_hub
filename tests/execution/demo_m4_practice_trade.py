#!/usr/bin/env python3
"""The first practice trade, end to end and OFFLINE, through the operator's own commands.

    dry-run -> submit (A3) -> confirmed fill -> protective stop verified at the broker
            -> close (close authorization) -> confirmed close fill -> fill-based P&L reconciled

    python3 tests/execution/demo_m4_practice_trade.py

Unlike demo_offline_lifecycle.py, this runs execution/mogo_practice_trade.py's run():
the A3 write opener, its grants, the read-only opener's host/account/TLS checks and
http.client's request path all execute. Only the connection is replaced, by
fake_oanda.FakeHttpsConnection, so no socket opens. Clock and transaction ids are
fixed, so two runs print identical output (test_oanda_practice_m4 asserts that).
"""
import datetime
import json
import os
import shutil
import sys
import tempfile
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "execution"))
sys.path.insert(0, HERE)

from oanda_practice import config as cfg          # noqa: E402
from fake_oanda import FakeOanda, https_factory   # noqa: E402
import mogo_practice_trade as trade_cli           # noqa: E402

ACCOUNT = "101-004-1234567-001"
NOW = datetime.datetime(2026, 11, 3, 12, 0, 1, tzinfo=datetime.timezone.utc)
#: The minimal first trade: the broker minimum of 1 unit, a 20-pip stop, the $5 cap.
ORDER_AUTHORIZATION = {
    "authorizationId": "AUTH-M4-DEMO-0001", "mode": "BROKER_PRACTICE", "accountId": ACCOUNT,
    "instrument": "EUR_USD", "direction": "BUY", "units": 1, "stopLossPrice": "1.09800",
    "maxSlippage": "0.00010", "maxSpread": "0.00020", "maxLoss": "5", "maxQuoteAgeSeconds": 10,
    "issuedAt": "2026-11-03T11:00:00Z", "expiresAt": "2026-11-03T18:00:00Z", "issuedBy": "operator"}
CLOSE_AUTHORIZATION = {
    "closeAuthorizationId": "CLOSE-M4-DEMO-0001", "mode": "BROKER_PRACTICE", "accountId": ACCOUNT,
    "issuedAt": "2026-11-03T11:00:00Z", "expiresAt": "2026-11-03T18:00:00Z", "issuedBy": "operator"}


def config():
    return cfg.config_from_mapping({"accountId": ACCOUNT, "token": "demo-token-not-a-credential"})


def command(broker, argv, opened=None, clock=lambda: NOW):
    args = trade_cli.build_parser().parse_args(argv)
    return trade_cli.run(args, config(), connection_factory=https_factory(broker, opened), clock=clock)


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle)
    return path


def run(work_dir, broker=None, units=1):
    """Returns (steps, broker). `work_dir` holds the state directory and the two authorization files."""
    broker = broker or FakeOanda(ACCOUNT)
    broker.close_commission, broker.close_financing = Decimal("0.0000"), Decimal("0.0000")
    state = os.path.join(work_dir, "state")
    os.makedirs(state, exist_ok=True)
    order_file = write_json(os.path.join(work_dir, "order.json"), dict(ORDER_AUTHORIZATION, units=units))
    opened, steps = [], []
    common = ["--state-dir", state]

    code, out = command(broker, ["dry-run", "--order-authorization", order_file] + common, opened)
    steps.append({"step": "1 dry-run (reads only)", "exit": code, "worstCaseLoss": out["worstCaseLoss"],
                  "request": out["request"], "brokerConstraints": out["brokerConstraints"],
                  "posts": broker.posts})

    code, out = command(broker, ["submit", "--order-authorization", order_file, "--authorization", "A3"]
                        + common, opened)
    pos = out["position"]
    steps.append({"step": "2 submit (A3): confirmed fill, stop verified", "exit": code,
                  "intent": out["submit"]["state"], "fillPrice": out["submit"]["fill_price"],
                  "fillUnits": out["submit"]["fill_units"], "position": pos["state"],
                  "stopOrderId": pos["stop_order_id"], "posts": broker.posts})

    broker.prices["EUR_USD"].update(bid="1.10250", ask="1.10260")       # the market moves
    close_file = write_json(os.path.join(work_dir, "close.json"), dict(
        CLOSE_AUTHORIZATION, clientOrderId=pos["clientOrderId"], tradeId=pos["trade_id"]))
    code, out = command(broker, ["close", "--close-authorization", close_file] + common, opened)
    pos = out["position"]
    steps.append({"step": "3 close (close authorization): confirmed close, P&L reconciled", "exit": code,
                  "position": pos["state"], "reason": pos["reason"], "entryPrice": pos["entry_price"],
                  "exitPrice": pos["exit_price"], "realizedPl": pos["realized_pl"], "netPl": pos["net_pl"],
                  "balanceAfter": pos["balance_after"], "brokerBalance": str(broker.balance),
                  "closePuts": broker.close_puts, "halts": pos["activeHalts"]})
    steps.append({"step": "wire", "connections": len(opened),
                  "writes": [(r[0], r[1].split("/")[-1]) for c in opened for r in c.requests if r[0] != "GET"],
                  "hosts": sorted({c.host for c in opened})})
    return steps, broker


def main():
    work = tempfile.mkdtemp(prefix="mogo_m4_demo_")
    try:
        print(json.dumps(run(work)[0], indent=1, default=str))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

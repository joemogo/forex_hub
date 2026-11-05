#!/usr/bin/env python3
"""One complete, deterministic, OFFLINE practice-trade lifecycle against the fake broker.

    order intent -> broker acknowledgment -> entry fill -> protected position
                 -> close fill -> P&L reconciliation

    python3 tests/execution/demo_offline_lifecycle.py

No socket, no credentials file, no real broker. The clock is fixed and the fake's
transaction ids are deterministic, so two runs produce byte-identical output
(tests/execution/test_oanda_practice_m2.py asserts exactly that).
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

from oanda_practice import adapter as ad          # noqa: E402
from oanda_practice import authorization as authz  # noqa: E402
from oanda_practice import config as cfg          # noqa: E402
from oanda_practice import executor as ex         # noqa: E402
from oanda_practice import transport as tp        # noqa: E402
from fake_oanda import FakeOanda                  # noqa: E402

ACCOUNT = "101-004-1234567-001"
NOW = datetime.datetime(2026, 11, 3, 12, 0, 1, tzinfo=datetime.timezone.utc)
AUTHORIZATION = {
    "authorizationId": "AUTH-DEMO-20261103-0001", "mode": "BROKER_PRACTICE", "accountId": ACCOUNT,
    "instrument": "EUR_USD", "direction": "BUY", "units": 1000, "stopLossPrice": "1.09800",
    "maxSlippage": "0.00010", "maxSpread": "0.00020", "maxLoss": "5", "maxQuoteAgeSeconds": 10,
    "issuedAt": "2026-11-03T11:00:00Z", "expiresAt": "2026-11-03T18:00:00Z", "issuedBy": "demo"}
#: M4: the close is its own operator act. clientOrderId and tradeId are filled from the position.
CLOSE_AUTHORIZATION = {
    "closeAuthorizationId": "CLOSE-DEMO-20261103-0001", "mode": "BROKER_PRACTICE", "accountId": ACCOUNT,
    "issuedAt": "2026-11-03T11:00:00Z", "expiresAt": "2026-11-03T18:00:00Z", "issuedBy": "demo"}


def run(state_dir, commission="0.0500", financing="-0.0100", daily="-0.0200"):
    fake = FakeOanda(ACCOUNT)
    fake.close_commission, fake.close_financing = Decimal(commission), Decimal(financing)
    config = cfg.config_from_mapping({"accountId": ACCOUNT, "token": "demo-token-not-a-credential"})
    transport = tp.Transport(config, opener=fake, kill_switch=ex.KillSwitch(state_dir))
    executor = ex.Executor(config, ad.OandaPracticeAdapter(transport), state_dir, clock=lambda: NOW)
    steps = []

    def step(name, **detail):
        steps.append(dict(step=name, **detail))

    try:
        auth = authz.parse_authorization(json.dumps(AUTHORIZATION).encode())
        step("1 order intent", clientOrderId=auth.client_order_id, units=auth.signed_units,
             stop=str(auth.stop_loss_price), balanceBefore=str(fake.balance))
        row = executor.submit(auth)
        step("2-3 broker ack + entry fill", intent=row["state"], tradeId=row["broker_trade_id"],
             fillPrice=row["fill_price"], fillUnits=row["fill_units"], posts=fake.posts)
        report = executor.reconcile()
        pos = executor.journal.position(auth.intent_id)
        step("4 protected position", position=pos["state"], stopOrderId=pos["stop_order_id"],
             reconcile=report["resolved"])
        fake.daily_financing(daily)                                  # held overnight
        fake.prices["EUR_USD"].update(bid="1.10250", ask="1.10260")  # the market moves
        close_auth = authz.parse_close_authorization(json.dumps(dict(
            CLOSE_AUTHORIZATION, clientOrderId=auth.client_order_id,
            tradeId=executor.journal.position(auth.intent_id)["trade_id"])).encode())
        pos = executor.close_position(auth.intent_id, close_auth)
        step("5 close fill", position=pos["state"], exitPrice=pos["exit_price"],
             closeReason=pos["close_reason"], closePuts=fake.close_puts)
        report = executor.reconcile()
        pos = executor.journal.position(auth.intent_id)
        step("6 P&L reconciliation", position=pos["state"], reason=pos["reason"],
             entryPrice=pos["entry_price"], exitPrice=pos["exit_price"], realizedPl=pos["realized_pl"],
             financing=pos["financing"], commission=pos["commission"], netPl=pos["net_pl"],
             balanceAfter=pos["balance_after"], brokerBalance=str(fake.balance), halts=report["halted"])
        step("journal events", events=[(e["from_state"], e["to_state"], e["reason"])
                                       for e in executor.journal.events(auth.intent_id)])
        return steps
    finally:
        executor.close()


def main():
    state_dir = tempfile.mkdtemp(prefix="mogo_practice_demo_")
    try:
        print(json.dumps(run(state_dir), indent=1))
    finally:
        shutil.rmtree(state_dir, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

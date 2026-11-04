#!/usr/bin/env python3
"""MOGO broker-practice executor: the M1 operator commands. All offline.

    python3 execution/mogo_practice_executor.py status        --state-dir DIR
    python3 execution/mogo_practice_executor.py kill          --state-dir DIR [--reason TEXT]
    python3 execution/mogo_practice_executor.py release-kill  --state-dir DIR --confirm
    python3 execution/mogo_practice_executor.py clear-halt    --state-dir DIR --halt SEQ --by WHO --reason WHY
    python3 execution/mogo_practice_executor.py check-authorization FILE

There is deliberately no `submit` command in M1. Submission needs a network
opener, which M1 does not have; it arrives with M3 under operator authorization
A2/A3. None of these commands reads credentials or contacts a broker.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from oanda_practice import authorization as authz   # noqa: E402
from oanda_practice import config as cfg            # noqa: E402
from oanda_practice import executor as ex           # noqa: E402
from oanda_practice import journal as jn            # noqa: E402
from oanda_practice.errors import PracticeExecutionError  # noqa: E402
from oanda_practice.kill import KillSwitch          # noqa: E402


def _journal(state_dir):
    real = ex.check_state_dir(state_dir)
    return real, jn.Journal(os.path.join(real, "journal.sqlite3"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("status", "kill", "release-kill", "clear-halt"):
        p = sub.add_parser(name)
        p.add_argument("--state-dir", required=True)
        if name == "kill":
            p.add_argument("--reason", default="operator")
        if name == "release-kill":
            p.add_argument("--confirm", action="store_true")
        if name == "clear-halt":
            p.add_argument("--halt", type=int, required=True)
            p.add_argument("--by", required=True)
            p.add_argument("--reason", required=True)
    p = sub.add_parser("check-authorization")
    p.add_argument("file")
    args = parser.parse_args(argv)

    try:
        if args.command == "check-authorization":
            with open(args.file, "rb") as handle:
                auth = authz.parse_authorization(handle.read())
            print(json.dumps({"valid": True, "clientOrderId": auth.client_order_id,
                              "instrument": auth.instrument, "direction": auth.direction,
                              "units": auth.units, "expiresAt": auth.data["expiresAt"]}, indent=1))
            return 0
        real = ex.check_state_dir(args.state_dir)
        kill = KillSwitch(real)
        if args.command == "kill":
            kill.engage(args.reason)
            print("kill switch ENGAGED: %s" % kill.path)
            return 0
        if args.command == "release-kill":
            if not args.confirm:
                print("refusing: release-kill requires --confirm")
                return 2
            kill.release(confirm=True)
            print("kill switch released")
            return 0
        _, journal = _journal(real)
        if args.command == "clear-halt":
            journal.clear_halt(args.halt, args.by, args.reason)
        print(json.dumps({"mode": cfg.MODE, "host": cfg.PRACTICE_HOST, "killSwitch": kill.engaged(),
                          "activeHalts": journal.active_halts(),
                          "intents": [{k: r[k] for k in ("intent_id", "state", "reason")}
                                      for r in journal.intents()]}, indent=1))
        return 0
    except (PracticeExecutionError, OSError, ValueError) as exc:
        print("refused: %s" % exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""MOGO broker-practice M3 preflight: read-only GETs against the configured practice account.

    python3 execution/mogo_practice_preflight.py --authorization A2 [--use-env-proxy] [--instrument EUR_USD]

The only command in the repository that opens a socket to the broker. It reads
~/.mogo/oanda_practice.json, sends at most seven GET requests to the practice
host for that one account, and prints a report that carries no token, no full
account id, no balance, no price and no transaction or trade id. Nothing is
written to disk. Without `--authorization A2` it refuses before reading the
credentials.

--use-env-proxy routes the requests through HTTPS_PROXY as a CONNECT tunnel,
and only when that proxy is http on a loopback address. TLS stays end-to-end to
the practice host, so the proxy sees the host name and nothing else.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from oanda_practice import config as cfg                        # noqa: E402
from oanda_practice.errors import PracticeExecutionError         # noqa: E402
from oanda_practice_m3 import preflight                          # noqa: E402
from oanda_practice_m3.readonly import (ProxyRefused, ReadOnlyHttpsOpener,  # noqa: E402
                                        ReadOnlyTransport)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--authorization", required=True)
    parser.add_argument("--use-env-proxy", action="store_true")
    parser.add_argument("--instrument", default="EUR_USD")
    args = parser.parse_args(argv)
    if args.authorization != "A2":
        print(json.dumps({"stop": "NOT_AUTHORIZED", "detail": "M3 needs operator authorization A2"}))
        return 2
    try:
        config = cfg.load_config()
        proxy = (os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")) if args.use_env_proxy else None
        opener = ReadOnlyHttpsOpener(config.account_id, proxy_url=proxy)
        transport = ReadOnlyTransport(config, opener)
        report = preflight.run(transport, config.account_id, instrument=args.instrument)
        report["via_loopback_proxy_tunnel"] = opener.uses_proxy
        report["sockets_opened"] = opener.sent
    except (PracticeExecutionError, ProxyRefused) as exc:
        print(json.dumps({"stop": type(exc).__name__, "detail": str(exc)}))
        return 2
    except Exception as exc:  # noqa: BLE001 -- never print a traceback that could carry a header
        print(json.dumps({"stop": "UNEXPECTED_%s" % type(exc).__name__}))
        return 2
    print(json.dumps(report, indent=1, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""MOGO broker-practice execution core (M1: offline).

MODE: BROKER_PRACTICE. This package is separate from research, replay and the
simulated paper engine in the browser application, and it has no live mode at all: the only
host it can address is the OANDA practice host, a constant in config.py.

M1 SCOPE. Everything needed to authorise, risk-check, journal and submit ONE
market order through a BrokerAdapter, and to resolve an uncertain outcome
without ever resubmitting. No real network path exists in M1: the default
opener refuses to send, and no module here imports socket, http or urllib.
Fill accounting, closing and balance reconciliation are M2.

See MOGO_FIRST_PAPER_TRADE_READINESS.md (1cbb6f7e6) and
MOGO_M1_OFFLINE_EXECUTOR_REPORT.md.
"""

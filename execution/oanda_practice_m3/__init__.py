"""M3: the read-only network path for the broker-practice executor (operator authorization A2).

Kept OUTSIDE execution/oanda_practice/ on purpose: that package's import ban
(no socket, ssl, http or urllib.request) stays exactly as M1/M2 proved it.
This package is the only code in the repository that can open a socket to the
broker, and everything it can send is a GET to the practice host for the
configured account.
"""

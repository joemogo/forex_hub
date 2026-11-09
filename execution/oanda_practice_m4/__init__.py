"""M4: the broker write path for the first practice trade, gated on operator authorization A3.

A2 remains GET-only (oanda_practice_m3.readonly). This package adds exactly two
writes -- one market entry, one close -- and only under a grant built from an
operator authorization. It imports no network library: the socket is opened by
the read-only opener's own send path, after this package's checks.
"""

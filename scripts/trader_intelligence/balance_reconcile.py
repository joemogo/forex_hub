"""Do the forward balance stamps reconcile once concurrent closes are accounted for?

The ledger (index.html `alexGCloseLivePosition`) applies a close's P&L to the account at the
moment it PROCESSES the close, and stamps `balanceAfter` then. `balanceBefore` is stamped at
entry. So for a record R:

    residual(R) = balanceAfter - balanceBefore - pnl
                = the summed P&L of the other closes the ledger PROCESSED inside R's lifetime.

The ordering is processing order, never market-exit order. Where the two differ is a batched
catch-up: on 2026-10-14 at 11:11Z one pass detected EUR/CHF (market exit 10-13 21:05Z) and
AUD/JPY (market exit 10-14 07:22Z) together and applied AUD/JPY first.

WHAT THE RECORD TELLS US ABOUT THE PROCESSING INSTANT
-----------------------------------------------------
* `closedAtBasis` absent or `closed_at_fallback`: `closedAt` IS the processing stamp. That holds
  for every record minted before v12.42.0, and the instant is exact.
* `closedAtBasis == "exit_detected_at"` (v12.42.0 D4 onwards): `closedAt` is the MARKET exit.
  The processing stamp is no longer carried in the package, so it is BOUNDED, not guessed:
  it lies in [closedAt, capturedAt]. Detection cannot precede the exit, and the package is
  captured by a post-tick sweep that runs after the ledger commit.

Package capture time is NOT treated as the processing instant. Its order matches processing
order only while no capture is delayed, and that is an assumption about the sweep rather than
an observation.

THE RULE, AND ITS ACCEPTED COST
-------------------------------
Each other close is classified against R's window as definitely inside, definitely outside, or
ambiguous (its interval straddles a window edge). R reconciles if its residual equals the
definite contributors plus SOME subset of the ambiguous ones, within the per-term rounding
tolerance. Where every interval is exact this reduces to the original rule.

Accepted by the operator 2026-10-20 (MOGO-RECONCILE-GATE-FIX-2026-10-20.md, G-3): inside an
ambiguous window, an error exactly equal to an ambiguous contributor's P&L (or a sum of them)
cannot be told apart from that contributor. More than MAX_AMBIGUOUS ambiguous contributors to
one record fails closed rather than searching a subset space that would explain almost anything.
"""
import datetime
import itertools

EXACT_BASES = (None, "closed_at_fallback")
BOUNDED_BASIS = "exit_detected_at"
MAX_AMBIGUOUS = 10

INSIDE, OUTSIDE, AMBIGUOUS = "INSIDE", "OUTSIDE", "AMBIGUOUS"


class UnreconcilableRecord(ValueError):
    """The record's own timing cannot be interpreted. Refused, never guessed around."""


def _instant(value):
    # Parsed, not string-compared: "...:30Z" sorts AFTER "...:30.500Z" as text.
    if not isinstance(value, str) or not value:
        raise UnreconcilableRecord("timestamp %r is not an ISO-8601 string" % (value,))
    return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))


def processing_bounds(record):
    """[lo, hi] guaranteed to contain the instant the ledger applied this close."""
    basis = record.get("closedAtBasis")
    closed = _instant(record["closedAt"])
    if basis in EXACT_BASES:
        return closed, closed
    if basis != BOUNDED_BASIS:
        raise UnreconcilableRecord("%s: unrecognised closedAtBasis %r"
                                   % (record.get("observationId"), basis))
    if not record.get("capturedAt"):
        raise UnreconcilableRecord("%s: closedAt is a market exit but no capturedAt bounds "
                                   "the processing instant" % (record.get("observationId"),))
    captured = _instant(record["capturedAt"])
    if captured < closed:
        raise UnreconcilableRecord("%s: capturedAt %s precedes the market exit %s"
                                   % (record.get("observationId"), record["capturedAt"],
                                      record["closedAt"]))
    return closed, captured


def classify(record, other):
    """Was `other`'s P&L applied inside `record`'s lifetime?"""
    opened = _instant(record["openedAt"])
    r_lo, r_hi = processing_bounds(record)
    o_lo, o_hi = processing_bounds(other)
    if o_hi <= opened or o_lo >= r_hi:
        return OUTSIDE
    if o_lo > opened and o_hi < r_lo:
        return INSIDE
    return AMBIGUOUS


def reconcile(forward, max_ambiguous=MAX_AMBIGUOUS):
    """Check every fully-covered record. Collects EVERY failure rather than stopping at the
    first, so a report says how many records disagree, not merely that one did."""
    earliest_close = min(_instant(r["closedAt"]) for r in forward)
    failures, checked, ambiguous_total = [], 0, 0
    for record in forward:
        # Only trades whose whole lifetime lies inside the preserved window can be
        # reconciled: for anything opened before the first preserved close, an UNPRESERVED
        # earlier trade may have moved the balance (backlog B-22).
        if _instant(record["openedAt"]) < earliest_close:
            continue
        residual = (record["accountBalanceAfter"]
                    - record["accountBalanceBefore"] - record["pnl"])
        definite, ambiguous = [], []
        for other in forward:
            if other is record:
                continue
            verdict = classify(record, other)
            if verdict == INSIDE:
                definite.append(other)
            elif verdict == AMBIGUOUS:
                ambiguous.append(other)
        checked += 1
        if len(ambiguous) > max_ambiguous:
            failures.append(dict(observationId=record.get("observationId"),
                                 reason="TOO_AMBIGUOUS", ambiguous=len(ambiguous)))
            continue
        ambiguous_total += len(ambiguous)
        base = sum(o["pnl"] for o in definite)
        if not _explained(residual, base, len(definite), [o["pnl"] for o in ambiguous]):
            failures.append(dict(
                observationId=record.get("observationId"), reason="UNEXPLAINED_RESIDUAL",
                residual=round(residual, 2), definite=round(base, 2),
                ambiguous=[o.get("observationId") for o in ambiguous]))
    return dict(checked=checked, failures=failures, ambiguousContributions=ambiguous_total)


def _explained(residual, base, n_definite, ambiguous_pnls):
    for k in range(len(ambiguous_pnls) + 1):
        # Each pnl is stored rounded to a cent, so a sum of k of them can drift by up to half
        # a cent per term. The tolerance scales with the number of terms rather than being
        # loosened globally.
        tolerance = 0.005 * (n_definite + k + 2)
        for subset in itertools.combinations(ambiguous_pnls, k):
            if abs(residual - base - sum(subset)) <= tolerance:
                return True
    return False

"""balance_reconcile: the delayed catch-up case, its negative controls, and the accepted cost.

THE FIXTURE is the eight LIVE_CLOSE closes preserved in the durable checkpoint
~/MOGO-EVIDENCE-PRESERVED/20261014T115219Z (extractor: 8 recovered, 8 verified), frozen here
as literals. It is NOT read from the corpus, so it never decays as the live system trades;
it is the shape of the failure, not a snapshot oracle.

On 2026-10-14 at 11:11Z one catch-up pass detected EUR/CHF (market exit 10-13 21:05Z) and
AUD/JPY (market exit 10-14 07:22Z) and the ledger applied AUD/JPY FIRST: AUD/JPY's residual
-403.23 excludes EUR/CHF, and EUR/CHF's residual -100.98 is exactly AUD/JPY's P&L. Ordered by
market exit, both records fail, each by the other's P&L.

Every negative control mutates a COPY of the fixture and names the record that must fail, so
"something failed" is never accepted as the reason a control passed.
"""
import copy
import os
import sys
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts", "trader_intelligence"))

import balance_reconcile as br            # noqa: E402

BOUNDED = "exit_detected_at"


def rec(oid, instrument, opened, closed, captured, before, after, pnl, basis):
    return {"observationId": oid, "instrument": instrument, "openedAt": opened,
            "closedAt": closed, "capturedAt": captured, "accountBalanceBefore": before,
            "accountBalanceAfter": after, "pnl": pnl, "closedAtBasis": basis}


CATCH_UP = (
    rec("20260921_1", "CAD_CHF", "2026-09-21T01:02:03.963Z", "2026-09-21T16:55:00.000Z", "2026-09-21T16:55:49.449Z", 10000, 10200, 200, BOUNDED),
    rec("20260923_1", "CAD_JPY", "2026-09-22T16:03:09.561Z", "2026-09-23T08:48:00.000Z", "2026-09-23T10:34:02.577Z", 10200, 10098, -102, BOUNDED),
    rec("20261005_1", "AUD_JPY", "2026-09-30T03:18:28.866Z", "2026-10-05T11:19:00.000Z", "2026-10-05T11:19:37.647Z", 10098, 9997.02, -100.98, BOUNDED),
    rec("20261007_1", "CAD_CHF", "2026-10-07T18:01:21.862Z", "2026-10-07T21:05:00.000Z", "2026-10-07T21:05:29.417Z", 9997.02, 9897.05, -99.97, BOUNDED),
    rec("20261008_1", "USD_JPY", "2026-10-07T21:00:32.516Z", "2026-10-08T00:46:20.195Z", "2026-10-08T00:46:20.410Z", 9997.02, 9792.7, -104.35, BOUNDED),
    rec("20261012_1", "CHF_JPY", "2026-10-12T13:01:45.722Z", "2026-10-12T14:57:00.000Z", "2026-10-12T14:57:55.875Z", 9792.7, 9694.77, -97.93, BOUNDED),
    rec("20261014_1", "AUD_JPY", "2026-09-29T17:01:53.159Z", "2026-10-14T07:22:00.000Z", "2026-10-14T11:11:25.974Z", 10098, 9593.79, -100.98, BOUNDED),
    rec("20261014_2", "EUR_CHF", "2026-10-13T05:47:28.890Z", "2026-10-13T21:05:00.000Z", "2026-10-14T11:11:26.020Z", 9694.77, 9496.84, -96.95, BOUNDED),
)
AUD_JPY, EUR_CHF = "20261014_1", "20261014_2"


def fixture():
    return copy.deepcopy(list(CATCH_UP))


def by_id(records, oid):
    return next(r for r in records if r["observationId"] == oid)


def failing(records, **kw):
    return {f["observationId"] for f in br.reconcile(records, **kw)["failures"]}


def legacy_reconcile_failures(forward):
    """The rule as it stood before 2026-10-20, verbatim in substance: contributors are the
    closes with openedAt < other.closedAt < closedAt. Kept to prove equivalence on exact
    records, so the new rule cannot have quietly changed what the old corpus verdict meant."""
    earliest = min(r["closedAt"] for r in forward)
    out = set()
    for record in forward:
        if record["openedAt"] < earliest:
            continue
        residual = record["accountBalanceAfter"] - record["accountBalanceBefore"] - record["pnl"]
        contributors = [o["pnl"] for o in forward if o is not record
                        and record["openedAt"] < o["closedAt"] < record["closedAt"]]
        if abs(residual - sum(contributors)) > 0.005 * (len(contributors) + 2):
            out.add(record["observationId"])
    return out


class TestTheDelayedCatchUpReconciles(unittest.TestCase):

    def test_positive_control_the_real_catch_up_reconciles(self):
        result = br.reconcile(fixture())
        self.assertEqual(result["failures"], [])
        self.assertEqual(result["checked"], 7, "all but the first-opened record are covered")

    def test_the_ambiguity_is_actually_exercised(self):
        # Non-vacuous: the pass above must come from the subset rule resolving real
        # ambiguity, not from a fixture in which nothing was ever uncertain.
        self.assertEqual(br.reconcile(fixture())["ambiguousContributions"], 2)

    def test_the_catch_up_pair_is_ambiguous_in_both_directions(self):
        recs = fixture()
        aud, eur = by_id(recs, AUD_JPY), by_id(recs, EUR_CHF)
        self.assertEqual(br.classify(aud, eur), br.AMBIGUOUS)
        self.assertEqual(br.classify(eur, aud), br.AMBIGUOUS)

    def test_earlier_closes_are_definitely_inside_the_long_trade(self):
        recs = fixture()
        aud = by_id(recs, AUD_JPY)
        for oid in ("20261005_1", "20261007_1", "20261008_1", "20261012_1"):
            with self.subTest(oid=oid):
                self.assertEqual(br.classify(aud, by_id(recs, oid)), br.INSIDE)

    def test_mechanism_control_market_exit_ordering_fails_both_records(self):
        """Discard the bound (treat closedAt as exact): this IS the pre-fix gate, and it must
        reproduce the original failure on exactly the two catch-up records."""
        recs = fixture()
        for r in recs:
            r["closedAtBasis"] = None
        self.assertEqual(failing(recs), {AUD_JPY, EUR_CHF})


class TestTheGateStillCatchesRealErrors(unittest.TestCase):

    def test_a_missing_close_inside_an_ambiguous_pair_is_caught(self):
        recs = fixture()
        recs.remove(by_id(recs, AUD_JPY))
        self.assertEqual(failing(recs), {EUR_CHF})

    def test_a_missing_close_inside_a_long_trade_is_caught(self):
        recs = fixture()
        recs.remove(by_id(recs, "20261012_1"))
        self.assertEqual(failing(recs), {AUD_JPY})

    def test_an_incorrect_pnl_on_the_late_close_is_caught(self):
        recs = fixture()
        by_id(recs, EUR_CHF)["pnl"] += 50.00
        self.assertIn(EUR_CHF, failing(recs))

    def test_a_five_cent_pnl_error_is_caught(self):
        recs = fixture()
        by_id(recs, "20261008_1")["pnl"] += 0.05
        self.assertEqual(failing(recs), {"20261008_1", AUD_JPY})

    def test_a_flipped_sign_is_caught(self):
        recs = fixture()
        by_id(recs, AUD_JPY)["pnl"] *= -1
        self.assertEqual(failing(recs), {AUD_JPY, EUR_CHF})

    def test_an_ordering_error_inside_the_catch_up_is_caught(self):
        # Swap which close the ledger "applied" first. AUD/JPY's new residual happens to be
        # explainable (the blind spot below); EUR/CHF's is not, and that is the catch.
        recs = fixture()
        aud, eur = by_id(recs, AUD_JPY), by_id(recs, EUR_CHF)
        aud["accountBalanceAfter"], eur["accountBalanceAfter"] = \
            eur["accountBalanceAfter"], aud["accountBalanceAfter"]
        self.assertEqual(failing(recs), {EUR_CHF})

    def test_an_ordering_error_between_exact_closes_is_caught(self):
        recs = fixture()
        by_id(recs, "20261007_1")["accountBalanceAfter"] = round(9792.70 - 99.97, 2)
        self.assertIn("20261007_1", failing(recs))


class TestTheAcceptedBlindSpotIsBounded(unittest.TestCase):
    """Operator decision 2026-10-20 (G-3): accepted, and pinned so it stays VISIBLE."""

    def test_an_error_equal_to_an_ambiguous_contributor_is_not_detected(self):
        recs = fixture()
        by_id(recs, AUD_JPY)["accountBalanceAfter"] = round(9593.79 - 96.95, 2)
        self.assertEqual(failing(recs), set(),
                         "if this now FAILS the blind spot has closed -- update the docstring "
                         "of balance_reconcile.py and the operator record, do not delete this")

    def test_an_error_five_cents_off_that_value_is_detected(self):
        recs = fixture()
        by_id(recs, AUD_JPY)["accountBalanceAfter"] = round(9593.79 - 96.90, 2)
        self.assertEqual(failing(recs), {AUD_JPY})

    def test_too_many_ambiguous_contributors_fail_closed(self):
        self.assertEqual(failing(fixture(), max_ambiguous=0), {AUD_JPY, EUR_CHF})


class TestExactRecordsKeepTheOriginalMeaning(unittest.TestCase):

    def exact(self):
        recs = fixture()
        for r in recs:
            r["closedAtBasis"] = None
        return recs

    def test_equivalent_to_the_original_rule_when_every_interval_is_exact(self):
        variants = [self.exact()]
        shifted = self.exact()
        by_id(shifted, "20261007_1")["pnl"] += 50
        variants.append(shifted)
        dropped = self.exact()
        dropped.remove(by_id(dropped, "20261012_1"))
        variants.append(dropped)
        for i, recs in enumerate(variants):
            with self.subTest(variant=i):
                self.assertEqual(failing(recs), legacy_reconcile_failures(recs))

    def test_a_record_without_a_basis_ignores_capturedAt(self):
        r = by_id(self.exact(), EUR_CHF)
        lo, hi = br.processing_bounds(r)
        self.assertEqual(lo, hi)


class TestUninterpretableTimingIsRefused(unittest.TestCase):

    def test_an_unrecognised_basis_is_refused(self):
        r = by_id(fixture(), EUR_CHF)
        r["closedAtBasis"] = "exit_candle_start"
        with self.assertRaises(br.UnreconcilableRecord):
            br.processing_bounds(r)

    def test_a_bounded_basis_without_capturedAt_is_refused(self):
        r = by_id(fixture(), EUR_CHF)
        del r["capturedAt"]
        with self.assertRaises(br.UnreconcilableRecord):
            br.processing_bounds(r)

    def test_a_capture_before_the_market_exit_is_refused(self):
        r = by_id(fixture(), EUR_CHF)
        r["capturedAt"] = "2026-10-13T21:04:59.999Z"
        with self.assertRaises(br.UnreconcilableRecord):
            br.processing_bounds(r)

    def test_timestamps_are_compared_as_instants_not_text(self):
        # As text "...:30Z" sorts AFTER "...:30.500Z"; as instants it is earlier.
        record = {"observationId": "R", "openedAt": "2026-10-01T00:00:00Z",
                  "closedAt": "2026-10-01T00:00:30.500Z", "closedAtBasis": None}
        other = {"observationId": "O", "closedAt": "2026-10-01T00:00:30Z",
                 "closedAtBasis": None}
        self.assertEqual(br.classify(record, other), br.INSIDE)


if __name__ == "__main__":
    unittest.main()

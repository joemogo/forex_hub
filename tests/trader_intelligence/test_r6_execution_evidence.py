#!/usr/bin/env python3
"""R-6: execution evidence survives import, and nothing presents a booked exit as a fill.

The defect. From v12.42.0 (D2) a candle exit that GAPS through its trigger is booked at
the trigger level, under the frozen fixed-R convention. The engine records its MODEL of
the market price beside the booking. The importer used to drop that model, so the
corpus would have shown the two 2026-10 gap losses as clean -1R fills at the stop.
EUR/CHF PKG|alex_g_sr_v1|20261014|2 opened 0.053R beyond its stop, and CAD/CHF
PKG|alex_g_sr_v1|20261007|1 opened 0.224R beyond.

The properties under test:

  * BOOKED VALUES ARE UNTOUCHED. exitPrice, pnl, rMultiple and accountBalanceAfter
    stay exactly as the simulator booked them. Nothing is re-priced to the model.
  * THE MODEL, THE QUOTE AND THE BOOKING STAY DISTINCT. Separate fields, with fixed
    roles in executionProvenance.fieldRoles.
  * UNKNOWN STAYS UNKNOWN. An absent basis, gap or quote is listed in `unknowns`;
    it is never defaulted to 0 or to "trigger_level".
  * INCONSISTENT EVIDENCE HALTS THE RUN. Each of the seven checks has its own
    refusal fixture, and every refusal test first proves its unmodified package is
    accepted (positive control).
  * NO BROKER CLAIM CAN BE WRITTEN. MOGO places no broker orders, so the validator
    refuses broker-fill and execution-verified records, and execution_verified_pnl()
    refuses to aggregate.
  * NOTHING RETROACTIVE. The new fields are not in OUTCOME_MAP, so the widening
    backfill cannot add them to preserved records.

FIXTURES. REAL_PACKAGES are verbatim EXCERPTS of the eight packages in checkpoint
~/MOGO-EVIDENCE-PRESERVED/20261014T115219Z (extraction sha256 f343e8b0...5274a). Every
value is copied unchanged, but only the fields the importer reads are kept, so the
excerpt does not re-derive its contentHash, which it carries only as a label. The
full packages are OANDA-derived capture data and stay out of the repository, like
evidence/. Set MOGO_R6_PACKAGES=<extracted packages file> to also run the mapping
over the complete original bytes (TestTheCompleteOriginalPackages). It is skipped
otherwise, and the skip is reported.
"""
import copy
import datetime
import json
import math
import os
import shutil
import sys
import tempfile
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts", "trader_intelligence"))

import import_mogo_observations as imp    # noqa: E402
import trade_observation as to            # noqa: E402

NOW = datetime.datetime(2026, 11, 2, tzinfo=datetime.timezone.utc)
SOURCE = {"sourceId": "EVSRC|MOGO|20261102|001", "sourceType": "paper_trade"}

GAP_A = "PKG|alex_g_sr_v1|20261014|2"       # EUR/CHF sell, candle_open_gap
GAP_B = "PKG|alex_g_sr_v1|20261007|1"       # CAD/CHF buy,  candle_open_gap
CONTROL = "PKG|alex_g_sr_v1|20261014|1"     # AUD/JPY sell, trigger_level, no gap
SNAPSHOT = "PKG|alex_g_sr_v1|20261008|1"    # USD/JPY buy,  live_snapshot, basis null
TARGET_WIN = "PKG|alex_g_sr_v1|20260921|1"  # CAD/CHF sell, target hit, trigger_level

REAL_PACKAGES = [{'packageId': 'PKG|alex_g_sr_v1|20261014|1',
  'contentHash': '5c82a52542e2f3ce6bb50afdcac5482f1aad4576313d37a510739736491c622f',
  'captureBasis': 'LIVE_CLOSE',
  'createdAt': '2026-10-14T11:11:25.974Z',
  'sourceTradeId': 'AGT|AGS|alex_g_sr_v1|AUD_JPY|H4|AGZ|AGC|AUD_JPY|H4|low|1786107600000|v1790240400000|B_breakRetest|AGR|AUD_JPY|H4|high|1790658000000',
  'identity': {'strategyId': 'alex_g_sr_v1', 'mode': 'LIVE_PAPER', 'engineVersion': '12.68.1'},
  'objects': {'positions': [{'instrument': 'AUD_JPY',
                             'timeframe': 'H4',
                             'direction': 'sell',
                             'entryPrice': 109.729,
                             'originalStop': 110.90892857142858,
                             'currentStop': 110.90892857142858,
                             'target': 107.36914285714285,
                             'positionSize': 0.1347805165930136,
                             'riskAmount': 100.98,
                             'entryTimestamp': '2026-09-29T17:01:53.159Z',
                             'balanceBefore': 10098,
                             'isDeveloperTrade': False,
                             'tradeSource': None}],
              'outcomes': [{'exitPrice': 110.90892857142858,
                            'exitTimestamp': '2026-10-14T07:22:00.000Z',
                            'exitTimestampBasis': 'exit_detected_at',
                            'exitCandleEnd': 1791962520000,
                            'exitDetectionSource': 'historical_candle',
                            'exitReasonCode': 'Loss',
                            'pnl': -100.98,
                            'balanceAfter': 9593.79,
                            'realizedR': -1,
                            'exitPriceBasis': 'trigger_level',
                            'exitTriggerLevel': 110.90892857142858,
                            'exitExecutablePrice': 110.90892857142858,
                            'exitGapPips': 0,
                            'exitGapR': 0,
                            'exitBid': None,
                            'exitAsk': None,
                            'exitSpreadPips': None,
                            'recordedResultR': -1}]}},
 {'packageId': 'PKG|alex_g_sr_v1|20261014|2',
  'contentHash': '205e12aa71a8ea920eb1bd0dce14569642b99cad56e1071e8eea85959dffff19',
  'captureBasis': 'LIVE_CLOSE',
  'createdAt': '2026-10-14T11:11:26.020Z',
  'sourceTradeId': 'AGT|AGS|alex_g_sr_v1|EUR_CHF|H4|AGZ|AGC|EUR_CHF|H4|low|1786107600000|v1790888400000|B_breakRetest|AGR|EUR_CHF|H4|high|1791824400000',
  'identity': {'strategyId': 'alex_g_sr_v1', 'mode': 'LIVE_PAPER', 'engineVersion': '12.69.0'},
  'objects': {'positions': [{'instrument': 'EUR_CHF',
                             'timeframe': 'H4',
                             'direction': 'sell',
                             'entryPrice': 0.93097,
                             'originalStop': 0.9334019642857143,
                             'currentStop': 0.9334019642857143,
                             'target': 0.9261060714285713,
                             'positionSize': 0.332150408587406,
                             'riskAmount': 96.94770000000001,
                             'entryTimestamp': '2026-10-13T05:47:28.890Z',
                             'balanceBefore': 9694.77,
                             'isDeveloperTrade': False,
                             'tradeSource': None}],
              'outcomes': [{'exitPrice': 0.9334019642857143,
                            'exitTimestamp': '2026-10-13T21:05:00.000Z',
                            'exitTimestampBasis': 'exit_detected_at',
                            'exitCandleEnd': 1791925500000,
                            'exitDetectionSource': 'historical_candle',
                            'exitReasonCode': 'Loss',
                            'pnl': -96.95,
                            'balanceAfter': 9496.84,
                            'realizedR': -1,
                            'exitPriceBasis': 'candle_open_gap',
                            'exitTriggerLevel': 0.9334019642857143,
                            'exitExecutablePrice': 0.93353,
                            'exitGapPips': 1.2803571428565697,
                            'exitGapR': 0.052647037227377944,
                            'exitBid': None,
                            'exitAsk': None,
                            'exitSpreadPips': None,
                            'recordedResultR': -1}]}},
 {'packageId': 'PKG|alex_g_sr_v1|20260921|1',
  'contentHash': 'c4d9e1fae778f2789b291608168f267866ee7f299d9f16dfd8113cbb4f2932da',
  'captureBasis': 'LIVE_CLOSE',
  'createdAt': '2026-09-21T16:55:49.449Z',
  'sourceTradeId': 'AGT|AGS|alex_g_sr_v1|CAD_CHF|H1|AGZ|AGC|CAD_CHF|H1|low|1789333200000|v1789711200000|B_breakRetest|AGR|CAD_CHF|H1|high|1789941600000',
  'identity': {'strategyId': 'alex_g_sr_v1', 'mode': 'LIVE_PAPER', 'engineVersion': '12.68.1'},
  'objects': {'positions': [{'instrument': 'CAD_CHF',
                             'timeframe': 'H1',
                             'direction': 'sell',
                             'entryPrice': 0.58751,
                             'originalStop': 0.5886646428571429,
                             'currentStop': 0.5886646428571429,
                             'target': 0.5852007142857141,
                             'positionSize': 0.7122548716361932,
                             'riskAmount': 100,
                             'entryTimestamp': '2026-09-21T01:02:03.963Z',
                             'balanceBefore': 10000,
                             'isDeveloperTrade': False,
                             'tradeSource': None}],
              'outcomes': [{'exitPrice': 0.5852007142857141,
                            'exitTimestamp': '2026-09-21T16:55:00.000Z',
                            'exitTimestampBasis': 'exit_detected_at',
                            'exitCandleEnd': 1790009700000,
                            'exitDetectionSource': 'historical_candle',
                            'exitReasonCode': 'Win',
                            'pnl': 200,
                            'balanceAfter': 10200,
                            'realizedR': 2,
                            'exitPriceBasis': 'trigger_level',
                            'exitTriggerLevel': 0.5852007142857141,
                            'exitExecutablePrice': 0.5852007142857141,
                            'exitGapPips': 0,
                            'exitGapR': 0,
                            'exitBid': None,
                            'exitAsk': None,
                            'exitSpreadPips': None,
                            'recordedResultR': 2}]}},
 {'packageId': 'PKG|alex_g_sr_v1|20260923|1',
  'contentHash': '938698b982855f238fc4cabc24d68123a1166b9ee29d3ce57e13018888609fa2',
  'captureBasis': 'LIVE_CLOSE',
  'createdAt': '2026-09-23T10:34:02.577Z',
  'sourceTradeId': 'AGT|AGS|alex_g_sr_v1|CAD_JPY|H1|AGZ|AGC|CAD_JPY|H1|low|1785826800000|v1789977600000|B_breakRetest|AGR|CAD_JPY|H1|high|1790082000000',
  'identity': {'strategyId': 'alex_g_sr_v1', 'mode': 'LIVE_PAPER', 'engineVersion': '12.68.1'},
  'objects': {'positions': [{'instrument': 'CAD_JPY',
                             'timeframe': 'H1',
                             'direction': 'sell',
                             'entryPrice': 111.969,
                             'originalStop': 112.09880357142858,
                             'currentStop': 112.09880357142858,
                             'target': 111.70939285714283,
                             'positionSize': 1.2382129261245414,
                             'riskAmount': 102,
                             'entryTimestamp': '2026-09-22T16:03:09.561Z',
                             'balanceBefore': 10200,
                             'isDeveloperTrade': False,
                             'tradeSource': None}],
              'outcomes': [{'exitPrice': 112.09880357142858,
                            'exitTimestamp': '2026-09-23T08:48:00.000Z',
                            'exitTimestampBasis': 'exit_detected_at',
                            'exitCandleEnd': 1790153280000,
                            'exitDetectionSource': 'historical_candle',
                            'exitReasonCode': 'Loss',
                            'pnl': -102,
                            'balanceAfter': 10098,
                            'realizedR': -1,
                            'exitPriceBasis': 'trigger_level',
                            'exitTriggerLevel': 112.09880357142858,
                            'exitExecutablePrice': 112.09880357142858,
                            'exitGapPips': 0,
                            'exitGapR': 0,
                            'exitBid': None,
                            'exitAsk': None,
                            'exitSpreadPips': None,
                            'recordedResultR': -1}]}},
 {'packageId': 'PKG|alex_g_sr_v1|20261005|1',
  'contentHash': '5e94f46457a5fae80b282cc6a59c907b8f54596d29d5b372179fe8ff794ff167',
  'captureBasis': 'LIVE_CLOSE',
  'createdAt': '2026-10-05T11:19:37.647Z',
  'sourceTradeId': 'AGT|AGS|alex_g_sr_v1|AUD_JPY|H1|AGZ|AGC|AUD_JPY|H1|low|1789142400000|v1789416000000|B_breakRetest|AGR|AUD_JPY|H1|high|1790726400000',
  'identity': {'strategyId': 'alex_g_sr_v1', 'mode': 'LIVE_PAPER', 'engineVersion': '12.68.1'},
  'objects': {'positions': [{'instrument': 'AUD_JPY',
                             'timeframe': 'H1',
                             'direction': 'sell',
                             'entryPrice': 109.227,
                             'originalStop': 110.14396428571429,
                             'currentStop': 110.14396428571429,
                             'target': 107.39307142857143,
                             'positionSize': 0.17247934621226868,
                             'riskAmount': 100.98,
                             'entryTimestamp': '2026-09-30T03:18:28.866Z',
                             'balanceBefore': 10098,
                             'isDeveloperTrade': False,
                             'tradeSource': None}],
              'outcomes': [{'exitPrice': 110.14396428571429,
                            'exitTimestamp': '2026-10-05T11:19:00.000Z',
                            'exitTimestampBasis': 'exit_detected_at',
                            'exitCandleEnd': 1791199140000,
                            'exitDetectionSource': 'historical_candle',
                            'exitReasonCode': 'Loss',
                            'pnl': -100.98,
                            'balanceAfter': 9997.02,
                            'realizedR': -1,
                            'exitPriceBasis': 'trigger_level',
                            'exitTriggerLevel': 110.14396428571429,
                            'exitExecutablePrice': 110.14396428571429,
                            'exitGapPips': 0,
                            'exitGapR': 0,
                            'exitBid': None,
                            'exitAsk': None,
                            'exitSpreadPips': None,
                            'recordedResultR': -1}]}},
 {'packageId': 'PKG|alex_g_sr_v1|20261007|1',
  'contentHash': '783724ee5978f03280c4fd976dd3354605006f2f48d3b69d09f9b65d2a5bac07',
  'captureBasis': 'LIVE_CLOSE',
  'createdAt': '2026-10-07T21:05:29.417Z',
  'sourceTradeId': 'AGT|AGS|alex_g_sr_v1|CAD_CHF|H1|AGZ|AGC|CAD_CHF|H1|high|1786525200000|v1791212400000|B_breakRetest|AGR|CAD_CHF|H1|low|1791385200000',
  'identity': {'strategyId': 'alex_g_sr_v1', 'mode': 'LIVE_PAPER', 'engineVersion': '12.69.0'},
  'objects': {'positions': [{'instrument': 'CAD_CHF',
                             'timeframe': 'H1',
                             'direction': 'buy',
                             'entryPrice': 0.5844,
                             'originalStop': 0.5833623214285714,
                             'currentStop': 0.5833623214285714,
                             'target': 0.5864753571428574,
                             'positionSize': 0.8024804591305393,
                             'riskAmount': 99.9702,
                             'entryTimestamp': '2026-10-07T18:01:21.862Z',
                             'balanceBefore': 9997.02,
                             'isDeveloperTrade': False,
                             'tradeSource': None}],
              'outcomes': [{'exitPrice': 0.5833623214285714,
                            'exitTimestamp': '2026-10-07T21:05:00.000Z',
                            'exitTimestampBasis': 'exit_detected_at',
                            'exitCandleEnd': 1791407100000,
                            'exitDetectionSource': 'historical_candle',
                            'exitReasonCode': 'Loss',
                            'pnl': -99.97,
                            'balanceAfter': 9897.05,
                            'realizedR': -1,
                            'exitPriceBasis': 'candle_open_gap',
                            'exitTriggerLevel': 0.5833623214285714,
                            'exitExecutablePrice': 0.58313,
                            'exitGapPips': 2.3232142857132487,
                            'exitGapR': 0.22388573395272718,
                            'exitBid': None,
                            'exitAsk': None,
                            'exitSpreadPips': None,
                            'recordedResultR': -1}]}},
 {'packageId': 'PKG|alex_g_sr_v1|20261008|1',
  'contentHash': '974d606cfb8fe54b5792f9db935b50b96e646df8c9337a645f8bf720afe53d04',
  'captureBasis': 'LIVE_CLOSE',
  'createdAt': '2026-10-08T00:46:20.410Z',
  'sourceTradeId': 'AGT|AGS|alex_g_sr_v1|USD_JPY|H4|AGZ|AGC|USD_JPY|H4|high|1790067600000|v1790701200000|B_breakRetest|AGR|USD_JPY|H4|low|1791363600000',
  'identity': {'strategyId': 'alex_g_sr_v1', 'mode': 'LIVE_PAPER', 'engineVersion': '12.69.0'},
  'objects': {'positions': [{'instrument': 'USD_JPY',
                             'timeframe': 'H4',
                             'direction': 'buy',
                             'entryPrice': 158.105,
                             'originalStop': 157.63939285714287,
                             'currentStop': 157.63939285714287,
                             'target': 159.03621428571424,
                             'positionSize': 0.33943935538698944,
                             'riskAmount': 99.9702,
                             'entryTimestamp': '2026-10-07T21:00:32.516Z',
                             'balanceBefore': 9997.02,
                             'isDeveloperTrade': False,
                             'tradeSource': None}],
              'outcomes': [{'exitPrice': 157.619,
                            'exitTimestamp': '2026-10-08T00:46:20.195Z',
                            'exitTimestampBasis': 'exit_detected_at',
                            'exitCandleEnd': None,
                            'exitDetectionSource': 'live_snapshot',
                            'exitReasonCode': 'Loss',
                            'pnl': -104.35,
                            'balanceAfter': 9792.7,
                            'realizedR': -1.043798,
                            'exitPriceBasis': None,
                            'exitTriggerLevel': 157.63939285714287,
                            'exitExecutablePrice': None,
                            'exitGapPips': None,
                            'exitGapR': None,
                            'exitBid': 157.619,
                            'exitAsk': 157.638,
                            'exitSpreadPips': 1.9000000000005457,
                            'recordedResultR': -1}]}},
 {'packageId': 'PKG|alex_g_sr_v1|20261012|1',
  'contentHash': '5cfce1852a1ef937b60c0760b659eea7073aab6d973f4d19b3d80cb1ef22738c',
  'captureBasis': 'LIVE_CLOSE',
  'createdAt': '2026-10-12T14:57:55.875Z',
  'sourceTradeId': 'AGT|AGS|alex_g_sr_v1|CHF_JPY|H1|AGZ|AGC|CHF_JPY|H1|high|1790568000000|v1791363600000|B_breakRetest|AGR|CHF_JPY|H1|low|1791799200000',
  'identity': {'strategyId': 'alex_g_sr_v1', 'mode': 'LIVE_PAPER', 'engineVersion': '12.69.0'},
  'objects': {'positions': [{'instrument': 'CHF_JPY',
                             'timeframe': 'H1',
                             'direction': 'buy',
                             'entryPrice': 190.438,
                             'originalStop': 190.182875,
                             'currentStop': 190.182875,
                             'target': 190.94824999999997,
                             'positionSize': 0.6089476062910517,
                             'riskAmount': 97.927,
                             'entryTimestamp': '2026-10-12T13:01:45.722Z',
                             'balanceBefore': 9792.7,
                             'isDeveloperTrade': False,
                             'tradeSource': None}],
              'outcomes': [{'exitPrice': 190.182875,
                            'exitTimestamp': '2026-10-12T14:57:00.000Z',
                            'exitTimestampBasis': 'exit_detected_at',
                            'exitCandleEnd': 1791817020000,
                            'exitDetectionSource': 'historical_candle',
                            'exitReasonCode': 'Loss',
                            'pnl': -97.93,
                            'balanceAfter': 9694.77,
                            'realizedR': -1,
                            'exitPriceBasis': 'trigger_level',
                            'exitTriggerLevel': 190.182875,
                            'exitExecutablePrice': 190.182875,
                            'exitGapPips': 0,
                            'exitGapR': 0,
                            'exitBid': None,
                            'exitAsk': None,
                            'exitSpreadPips': None,
                            'recordedResultR': -1}]}}]

BY_ID = {p["packageId"]: p for p in REAL_PACKAGES}

#: Package field -> record field. Written out HERE, independently of the importer's
#: EXECUTION_MAP, so dropping or crossing an importer entry fails a test rather than
#: changing both sides of the comparison at once.
EXPECTED_EXECUTION_FIELDS = (
    ("exitPriceBasis", "exitPriceBasis"),
    ("exitTriggerLevel", "exitTriggerLevel"),
    ("exitExecutablePrice", "exitModeledExecutablePrice"),
    ("exitGapPips", "exitGapPips"),
    ("exitGapR", "exitGapR"),
    ("exitBid", "exitQuoteBid"),
    ("exitAsk", "exitQuoteAsk"),
    ("exitSpreadPips", "exitQuoteSpreadPips"),
    ("recordedResultR", "recordedResultR"),
)
NEW_RECORD_FIELDS = tuple(r for _p, r in EXPECTED_EXECUTION_FIELDS)


def pkg(package_id):
    return copy.deepcopy(BY_ID[package_id])


def out(package):
    return package["objects"]["outcomes"][0]


def pos(package):
    return package["objects"]["positions"][0]


def mint(package):
    record, reason = imp.observation_from_package(package, NOW, {}, SOURCE)
    if record is None:
        raise AssertionError("package was skipped: %s" % reason)
    return record


def old_format(package_id=CONTROL):
    """A pre-v12.42 shape: no execution fields at all, and no identity.mode."""
    p = pkg(package_id)
    for key, _r in EXPECTED_EXECUTION_FIELDS:
        out(p).pop(key, None)
    p["identity"].pop("mode")
    return p


class TestTheFixturesAreTheRealPackages(unittest.TestCase):
    def test_the_fixture_set_is_the_eight_checkpoint_packages(self):
        self.assertEqual(len(REAL_PACKAGES), 8)
        self.assertEqual(len(BY_ID), 8)
        self.assertEqual(len({p["contentHash"] for p in REAL_PACKAGES}), 8)

    def test_exactly_the_two_named_packages_gapped(self):
        gapped = {p["packageId"] for p in REAL_PACKAGES
                  if out(p)["exitPriceBasis"] == "candle_open_gap"}
        self.assertEqual(gapped, {GAP_A, GAP_B})


class TestTheGapExitsCarryTheirEvidence(unittest.TestCase):
    def test_every_execution_field_is_carried_from_its_package_field(self):
        checked = 0
        for package in REAL_PACKAGES:
            record = mint(copy.deepcopy(package))
            for package_field, record_field in EXPECTED_EXECUTION_FIELDS:
                with self.subTest(package=package["packageId"], field=record_field):
                    value = out(package).get(package_field)
                    if value is None:
                        self.assertNotIn(record_field, record)
                        self.assertIn(record_field, record["unknowns"])
                    else:
                        self.assertEqual(record.get(record_field), value)
                        self.assertEqual(record["fieldClassification"][record_field],
                                         "DIRECTLY_OBSERVED")
                        checked += 1
        self.assertGreater(checked, 40)

    def test_both_gap_exits_record_the_engine_model_beside_the_booking(self):
        for package_id in (GAP_A, GAP_B):
            with self.subTest(package=package_id):
                p = pkg(package_id)
                record = mint(p)
                self.assertEqual(record["exitPriceBasis"], "candle_open_gap")
                self.assertEqual(record["exitModeledExecutablePrice"],
                                 out(p)["exitExecutablePrice"])
                self.assertEqual(record["exitGapPips"], out(p)["exitGapPips"])
                self.assertEqual(record["exitGapR"], out(p)["exitGapR"])
                self.assertGreater(record["exitGapR"], 0)
                self.assertEqual(record["exitTriggerLevel"], out(p)["exitTriggerLevel"])

    def test_the_booked_values_are_the_simulator_booking_not_the_model(self):
        for package_id in (GAP_A, GAP_B):
            with self.subTest(package=package_id):
                p = pkg(package_id)
                record = mint(p)
                self.assertEqual(record["exitPrice"], out(p)["exitPrice"])
                self.assertEqual(record["exitPrice"], out(p)["exitTriggerLevel"])
                self.assertNotEqual(record["exitPrice"],
                                    record["exitModeledExecutablePrice"])
                self.assertEqual(record["pnl"], out(p)["pnl"])
                self.assertEqual(record["rMultiple"], out(p)["realizedR"])
                self.assertEqual(record["rMultiple"], -1)
                self.assertEqual(record["accountBalanceAfter"], out(p)["balanceAfter"])

    def test_the_model_is_never_named_as_an_executed_price(self):
        record = mint(pkg(GAP_A))
        self.assertNotIn("exitExecutablePrice", record)
        roles = record["executionProvenance"]["fieldRoles"]
        self.assertEqual(roles["exitModeledExecutablePrice"], "ENGINE_MODELED_NOT_A_FILL")
        self.assertEqual(roles["exitGapR"], "ENGINE_MODELED_NOT_A_FILL")
        for booked in ("exitPrice", "pnl", "rMultiple", "accountBalanceAfter"):
            self.assertEqual(roles[booked], "SIMULATOR_BOOKED")

    def test_provenance_is_simulated_with_no_broker_fill(self):
        for package in REAL_PACKAGES:
            with self.subTest(package=package["packageId"]):
                prov = mint(copy.deepcopy(package))["executionProvenance"]
                self.assertEqual(prov["executionKind"], "SIMULATED")
                self.assertEqual(prov["brokerFill"], "NONE")
                self.assertIs(prov["executionVerified"], False)
                self.assertEqual(prov["outcomeBasis"], "SIMULATOR_BOOKED")
                self.assertEqual(prov["packageMode"], "LIVE_PAPER")


class TestTheControlsKeepTheirClassification(unittest.TestCase):
    def test_a_trigger_level_exit_records_a_MEASURED_zero_gap(self):
        record = mint(pkg(CONTROL))
        self.assertEqual(record["exitPriceBasis"], "trigger_level")
        self.assertEqual(record["exitGapPips"], 0)
        self.assertEqual(record["exitGapR"], 0)
        self.assertNotIn("exitGapR", record["unknowns"])
        self.assertEqual(record["exitModeledExecutablePrice"], record["exitPrice"])

    def test_no_trigger_level_exit_acquires_a_gap(self):
        trigger_exits = [p for p in REAL_PACKAGES
                         if out(p)["exitPriceBasis"] == "trigger_level"]
        self.assertEqual(len(trigger_exits), 5)
        for package in trigger_exits:
            with self.subTest(package=package["packageId"]):
                record = mint(copy.deepcopy(package))
                self.assertEqual((record["exitGapPips"], record["exitGapR"]), (0, 0))
                self.assertEqual(record["exitModeledExecutablePrice"],
                                 record["exitTriggerLevel"])

    def test_the_snapshot_exit_keeps_an_UNKNOWN_basis(self):
        p = pkg(SNAPSHOT)
        record = mint(p)
        for field in ("exitPriceBasis", "exitModeledExecutablePrice",
                      "exitGapPips", "exitGapR"):
            with self.subTest(field=field):
                self.assertNotIn(field, record)
                self.assertIn(field, record["unknowns"])
        self.assertEqual(record["exitQuoteBid"], out(p)["exitBid"])
        self.assertEqual(record["exitQuoteAsk"], out(p)["exitAsk"])
        self.assertEqual(record["exitQuoteSpreadPips"], out(p)["exitSpreadPips"])
        roles = record["executionProvenance"]["fieldRoles"]
        self.assertEqual(roles["exitQuoteBid"], "OBSERVED_QUOTE")
        # The snapshot path books at the quote, so the slippage is IN rMultiple, and
        # the ledger's fixed-R label differs from it.
        self.assertEqual(record["rMultiple"], out(p)["realizedR"])
        self.assertLess(record["rMultiple"], -1)
        self.assertEqual(record["recordedResultR"], -1)

    def test_an_old_format_package_records_every_execution_field_UNKNOWN(self):
        record = mint(old_format())
        for field in NEW_RECORD_FIELDS:
            with self.subTest(field=field):
                self.assertNotIn(field, record)
                self.assertIn(field, record["unknowns"])
        self.assertNotIn(0, [record.get(f) for f in NEW_RECORD_FIELDS])
        # And the booked values are still recorded: old format is not a refusal.
        self.assertEqual(record["pnl"], out(pkg(CONTROL))["pnl"])

    def test_a_package_with_no_mode_is_not_assumed_simulated(self):
        prov = mint(old_format())["executionProvenance"]
        self.assertEqual(prov["executionKind"], "UNKNOWN")
        self.assertEqual(prov["brokerFill"], "UNKNOWN")
        self.assertEqual(prov["outcomeBasis"], "UNKNOWN")
        self.assertEqual(prov["fieldRoles"], {})
        self.assertIsNone(prov["packageMode"])


class TestEveryRealPackageKeepsItsBookedValues(unittest.TestCase):
    def test_booked_fields_equal_the_package_on_all_eight(self):
        compared = 0
        for package in REAL_PACKAGES:
            record = mint(copy.deepcopy(package))
            for record_field, key in imp.OUTCOME_MAP:
                value = imp.map_outcome_value(record_field, out(package).get(key))
                with self.subTest(package=package["packageId"], field=record_field):
                    self.assertEqual(record.get(record_field), value)
                    compared += value is not None
            for record_field, key in imp.POSITION_MAP:
                if record_field == "instrument":
                    continue
                with self.subTest(package=package["packageId"], field=record_field):
                    self.assertEqual(record.get(record_field), pos(package).get(key))
        self.assertGreater(compared, 40)

    def test_the_booked_total_is_the_ledger_total_not_the_modelled_one(self):
        records = [mint(copy.deepcopy(p)) for p in REAL_PACKAGES]
        self.assertEqual(round(sum(r["pnl"] for r in records), 2),
                         round(sum(out(p)["pnl"] for p in REAL_PACKAGES), 2))
        self.assertEqual(round(sum(r["rMultiple"] for r in records), 6),
                         round(sum(out(p)["realizedR"] for p in REAL_PACKAGES), 6))


class TestInconsistentExecutionEvidenceIsRefused(unittest.TestCase):
    """One fixture per check. Each first proves its unmodified package is ACCEPTED."""

    def assertRefused(self, package_id, rule, mutate):
        mint(pkg(package_id))                      # positive control
        p = pkg(package_id)
        mutate(p)
        with self.assertRaises(imp.ExecutionEvidenceRefused) as caught:
            imp.observation_from_package(p, NOW, {}, SOURCE)
        self.assertIn("R6-%s " % rule, str(caught.exception))

    def test_rule1_an_unsupported_basis_is_refused(self):
        self.assertRefused(GAP_A, 1, lambda p: out(p).update(exitPriceBasis="mid_price"))

    def test_rule1_gap_evidence_without_a_basis_is_refused(self):
        self.assertRefused(GAP_A, 1, lambda p: out(p).pop("exitPriceBasis"))

    def test_rule2_a_gap_exit_missing_its_modelled_price_is_refused(self):
        self.assertRefused(GAP_B, 2, lambda p: out(p).update(exitExecutablePrice=None))

    def test_rule2_a_non_finite_gap_is_refused(self):
        self.assertRefused(GAP_B, 2, lambda p: out(p).update(exitGapR=float("nan")))

    def test_rule2_a_non_numeric_gap_is_refused(self):
        self.assertRefused(GAP_B, 2, lambda p: out(p).update(exitGapPips="2.3"))

    def test_rule2_a_gap_exit_with_no_gap_is_refused(self):
        def zero(p):
            out(p).update(exitGapPips=0, exitGapR=0,
                          exitExecutablePrice=out(p)["exitTriggerLevel"])
        self.assertRefused(GAP_A, 2, zero)

    def test_rule3_a_stop_exit_modelled_in_the_positions_favour_is_refused(self):
        def flip(p):
            o = out(p)
            o["exitExecutablePrice"] = o["exitTriggerLevel"] - (
                o["exitExecutablePrice"] - o["exitTriggerLevel"])
        self.assertRefused(GAP_A, 3, flip)

    def test_rule3_a_target_exit_modelled_short_of_the_target_is_refused(self):
        def short(p):
            make_target_gap(p, favourable=False)
        self.assertRefused(TARGET_WIN, 3, short)

    def test_rule3_a_trigger_matching_neither_stop_nor_target_is_refused(self):
        def stray(p):
            o = out(p)
            o["exitTriggerLevel"] = o["exitPrice"] = o["exitTriggerLevel"] + 0.001
            o["exitExecutablePrice"] = o["exitTriggerLevel"]
        self.assertRefused(CONTROL, 3, stray)

    def test_rule3_a_target_gap_in_the_positions_favour_is_ACCEPTED(self):
        p = pkg(TARGET_WIN)
        make_target_gap(p, favourable=True)
        record = mint(p)
        self.assertEqual(record["exitPriceBasis"], "candle_open_gap")
        self.assertEqual(record["exitPrice"], pos(p)["target"])

    def test_rule4_a_trigger_level_exit_carrying_a_gap_is_refused(self):
        self.assertRefused(CONTROL, 4, lambda p: out(p).update(exitGapPips=0.5))

    def test_rule4_a_trigger_level_exit_whose_model_differs_is_refused(self):
        self.assertRefused(CONTROL, 4, lambda p: out(p).update(
            exitExecutablePrice=out(p)["exitTriggerLevel"] + 0.01))

    def test_rule5_gap_pips_that_disagree_with_the_prices_are_refused(self):
        self.assertRefused(GAP_B, 5, lambda p: out(p).update(
            exitGapPips=out(p)["exitGapPips"] * 2))

    def test_rule5_a_gap_R_that_disagrees_with_the_prices_is_refused(self):
        self.assertRefused(GAP_A, 5, lambda p: out(p).update(
            exitGapR=out(p)["exitGapR"] * 1.01))

    def test_rule6_a_basis_on_a_snapshot_exit_is_refused(self):
        self.assertRefused(GAP_A, 6, lambda p: out(p).update(
            exitDetectionSource="live_snapshot"))

    def test_rule7_an_exit_booked_at_the_model_is_refused(self):
        self.assertRefused(GAP_B, 7, lambda p: out(p).update(
            exitPrice=out(p)["exitExecutablePrice"]))

    def test_an_unknown_mode_is_refused(self):
        self.assertRefused(GAP_A, "MODE", lambda p: p["identity"].update(mode="LIVE"))


def make_target_gap(p, favourable):
    """Turn the real target exit into a 0.5-pip candle_open_gap through its target."""
    o, position = out(p), pos(p)
    pip = 0.01 if "JPY" in position["instrument"] else 0.0001
    sign = 1 if position["direction"] == "buy" else -1
    step = 0.5 * pip * (sign if favourable else -sign)
    o["exitPriceBasis"] = "candle_open_gap"
    o["exitExecutablePrice"] = o["exitTriggerLevel"] + step
    gap_pips = abs(o["exitExecutablePrice"] - o["exitTriggerLevel"]) / pip
    risk_pips = abs(position["entryPrice"] - position["currentStop"]) / pip
    o["exitGapPips"], o["exitGapR"] = gap_pips, gap_pips / risk_pips


class TestARefusalHaltsTheWholeRun(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="mogo_r6_halt_")
        self.empty = os.path.join(self.root, "empty")
        os.makedirs(self.empty)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def convert(self, packages):
        path = os.path.join(self.root, "R6-PACKAGES.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(packages, handle)
        return imp.convert_all(package_glob=path, now=NOW, skip_imported=False,
                               observations_dir=self.empty, sources_dir=self.empty)

    def test_one_bad_package_stops_every_package_and_writes_nothing(self):
        good = [pkg(CONTROL), pkg(GAP_A)]
        records, skipped, _s = self.convert(good)         # positive control
        self.assertEqual(len(records), 2)
        self.assertEqual(skipped, [])
        bad = pkg(GAP_B)
        out(bad)["exitGapPips"] *= 2
        with self.assertRaises(imp.ExecutionEvidenceRefused):
            self.convert(good + [bad])
        self.assertEqual(os.listdir(self.empty), [])

    def test_the_refusal_cannot_be_swallowed_as_a_per_record_write_refusal(self):
        self.assertFalse(issubclass(imp.ExecutionEvidenceRefused, to.ObservationRefused))


class TestNoBrokerClaimCanBeRecorded(unittest.TestCase):
    def setUp(self):
        self.record = mint(pkg(GAP_A))
        to.validate_observation(self.record)              # positive control

    def assertInvalid(self, mutate, needle):
        record = copy.deepcopy(self.record)
        mutate(record)
        with self.assertRaises(to.ObservationRefused) as caught:
            to.validate_observation(record)
        self.assertIn(needle, str(caught.exception))

    def prov(self, **changes):
        return lambda r: r["executionProvenance"].update(changes)

    def test_a_CONFIRMED_broker_fill_is_refused(self):
        self.assertInvalid(self.prov(brokerFill="CONFIRMED"), "brokerFill")

    def test_an_execution_verified_claim_is_refused(self):
        self.assertInvalid(self.prov(executionVerified=True), "executionVerified")

    def test_a_broker_execution_kind_is_refused(self):
        self.assertInvalid(self.prov(executionKind="BROKER_EXECUTED", brokerFill="CONFIRMED"),
                           "executionKind")

    def test_a_realized_outcome_basis_is_refused(self):
        self.assertInvalid(self.prov(outcomeBasis="REALIZED_EXECUTION"), "outcomeBasis")

    def test_the_booked_exit_cannot_be_relabelled_as_a_fill(self):
        self.assertInvalid(lambda r: r["executionProvenance"]["fieldRoles"].update(
            exitPrice="BROKER_FILL"), "role is fixed")

    def test_the_model_cannot_be_relabelled_as_an_observed_quote(self):
        self.assertInvalid(lambda r: r["executionProvenance"]["fieldRoles"].update(
            exitModeledExecutablePrice="OBSERVED_QUOTE"), "role is fixed")

    def test_a_recorded_value_without_a_role_is_refused(self):
        self.assertInvalid(lambda r: r["executionProvenance"]["fieldRoles"].pop("pnl"),
                           "has no role")

    def test_an_unknown_kind_cannot_assign_roles(self):
        self.assertInvalid(self.prov(executionKind="UNKNOWN", brokerFill="UNKNOWN",
                                     outcomeBasis="UNKNOWN"), "cannot assign")

    def test_a_broker_named_field_on_a_MOGO_record_is_refused(self):
        self.assertInvalid(lambda r: r.update(brokerFillPrice=r["exitPrice"]),
                           "no broker orders")

    def test_an_extra_provenance_key_is_refused(self):
        self.assertInvalid(self.prov(brokerOrderId="12345"), "exactly the keys")

    def test_provenance_on_a_HUMAN_record_is_refused(self):
        self.assertInvalid(lambda r: r.update(actor="HUMAN"), "only for MOGO")

    def test_execution_verified_pnl_refuses_the_eight_records(self):
        records = {str(i): mint(copy.deepcopy(p)) for i, p in enumerate(REAL_PACKAGES)}
        self.assertEqual(len(records), 8)
        with self.assertRaises(to.ObservationRefused):
            to.execution_verified_pnl(records)
        with self.assertRaises(to.ObservationRefused):
            to.execution_verified_pnl({})


class TestNothingIsRetroactive(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="mogo_r6_backfill_")
        self.obs_dir = os.path.join(self.root, "observations")
        self.src_dir = os.path.join(self.root, "sources")
        os.makedirs(self.obs_dir)
        os.makedirs(self.src_dir)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_the_execution_fields_are_not_in_the_backfill_mapping(self):
        execution = {f for f, _k in imp.EXECUTION_MAP}
        self.assertEqual(execution, set(NEW_RECORD_FIELDS))
        self.assertEqual(execution & {f for f, _k in imp.OUTCOME_MAP}, set())

    def test_the_backfill_adds_no_execution_field_to_a_preserved_record(self):
        package = pkg(GAP_A)
        capture = os.path.join(self.root, "R6-BACKFILL-PACKAGES.json")
        with open(capture, "w", encoding="utf-8") as handle:
            json.dump([package], handle)
        with open(os.path.join(self.src_dir, "EVSRC_MOGO_20261102_001.json"), "w",
                  encoding="utf-8") as handle:
            json.dump({"sourceId": "EVSRC|MOGO|20261102|001", "sourceType": "paper_trade",
                       "repositoryPath": capture, "contentHash": "irrelevant"}, handle)
        record = {"observationId": "TOBS|MOGO|20261102|901",
                  "sourceId": "EVSRC|MOGO|20261102|001", "actor": "MOGO",
                  "sourcePackageId": package["packageId"],
                  "sourceContentHash": package["contentHash"],
                  "schemaVersion": to.SCHEMA_VERSION, "lane": "RESEARCH",
                  "createdAt": "2026-10-14T12:00:00Z", "extractedBy": "test-fixture",
                  "instrument": "EUR/CHF", "direction": "sell",
                  "fieldClassification": {"instrument": "DIRECTLY_OBSERVED",
                                          "direction": "DIRECTLY_OBSERVED"},
                  "unknowns": []}
        path = os.path.join(self.obs_dir, "TOBS_MOGO_20261102_901.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(record, handle)
        report = imp.backfill_mapped_fields(observations_dir=self.obs_dir,
                                            sources_dir=self.src_dir, write=True)
        self.assertEqual(report["unresolved"], [])
        with open(path, encoding="utf-8") as handle:
            written = json.load(handle)
        # Positive control: the backfill DID run on this record.
        self.assertEqual(written.get("pnl"), out(package)["pnl"])
        for field in NEW_RECORD_FIELDS + ("executionProvenance",):
            with self.subTest(field=field):
                self.assertNotIn(field, written)
                self.assertNotIn(field, written["unknowns"])


class TestThePreservedCorpusIsUntouched(unittest.TestCase):
    """REAL corpus, read-only. Relationships only: no count is pinned."""

    def test_no_preserved_record_carries_an_R6_field_and_all_still_validate(self):
        observations = to.load_observations()
        self.assertGreater(len(observations), 0)
        for observation_id, record in observations.items():
            with self.subTest(observation=observation_id):
                to.validate_observation(record)
                for field in NEW_RECORD_FIELDS + ("executionProvenance",):
                    self.assertNotIn(field, record)
                    self.assertNotIn(field, record.get("unknowns") or [])


class TestTheSchemaDocumentsTheRecord(unittest.TestCase):
    def schema(self):
        with open(os.path.join(REPO_ROOT, "docs", "trader-intelligence", "evidence",
                               "schema", "trade-observation.schema.json"),
                  encoding="utf-8") as handle:
            return json.load(handle)

    def test_every_key_a_minted_record_carries_is_a_schema_property(self):
        props = set(self.schema()["properties"])
        for package in REAL_PACKAGES + [old_format()]:
            record = mint(copy.deepcopy(package))
            with self.subTest(package=package["packageId"]):
                self.assertEqual(set(record) - props, set())

    def test_the_schema_enums_are_the_validator_constants(self):
        prov = self.schema()["properties"]["executionProvenance"]
        self.assertEqual(tuple(prov["properties"]["executionKind"]["enum"]),
                         to.EXECUTION_KINDS)
        self.assertEqual(sorted(prov["required"]), sorted(to.EXECUTION_PROVENANCE_KEYS))
        self.assertEqual(set(prov["properties"]["fieldRoles"]["additionalProperties"]["enum"]),
                         set(to.FIELD_ROLES.values()))
        basis = self.schema()["properties"]["exitPriceBasis"]["enum"]
        self.assertEqual(tuple(b for b in basis if b is not None), imp.EXIT_PRICE_BASES)


@unittest.skipUnless(os.environ.get("MOGO_R6_PACKAGES"),
                     "MOGO_R6_PACKAGES not set: complete original packages not checked")
class TestTheCompleteOriginalPackages(unittest.TestCase):
    """The same mapping over the UNTRIMMED original bytes, when supplied."""

    def test_the_originals_map_identically_to_the_excerpts(self):
        with open(os.environ["MOGO_R6_PACKAGES"], encoding="utf-8") as handle:
            originals = json.load(handle)
        self.assertEqual({p["contentHash"] for p in originals},
                         {p["contentHash"] for p in REAL_PACKAGES})
        by_hash = {p["contentHash"]: p for p in REAL_PACKAGES}
        for original in originals:
            with self.subTest(package=original["packageId"]):
                a = mint(original)
                b = mint(copy.deepcopy(by_hash[original["contentHash"]]))
                self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()

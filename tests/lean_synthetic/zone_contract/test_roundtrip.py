#!/usr/bin/env python3
"""Focused tests for the synthetic zone request contract; no production or cloud inputs."""
import copy
import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PACKAGE = os.path.dirname(HERE)
if PACKAGE not in sys.path:
    sys.path.insert(0, PACKAGE)

from br_machine import Bar, BreakRetestMachine, S_BROKEN, S_LOCKED
from zone_contract import boundary, mogo_synthetic_emitter as emitter


class TestSyntheticEmitterAndBoundary(unittest.TestCase):
    def direct_machine(self, case):
        request = emitter.emit(case)
        zone = request["zone"]
        machine = BreakRetestMachine(request["config"], zone["low"], zone["high"],
                                     zone["role"], zone["availableFromIndex"])
        for row in request["bars"]:
            machine.on_bar(Bar(row["index"], row["timestamp"], row["open"], row["high"],
                               row["low"], row["close"]))
        return machine

    def test_emitter_produces_closed_envelope_for_each_fixture(self):
        for case, expected_id in (("qualify", "SYNQUAL"), ("reject", "SYNREJ")):
            with self.subTest(case=case):
                request = emitter.emit(case)
                self.assertEqual(set(request), boundary.REQUEST_FIELDS)
                self.assertEqual(request["caseId"], expected_id)
                self.assertEqual(len(request["bars"]), 120)
                self.assertEqual(set(request["zone"]), boundary.ZONE_FIELDS)
                self.assertEqual(set(request["config"]), boundary.CONFIG_FIELDS)

    def test_canonical_emitter_output_is_deterministic(self):
        self.assertEqual(emitter.json_text("qualify"), emitter.json_text("qualify"))
        self.assertTrue(emitter.json_text("qualify").endswith("\n"))

    def test_boundary_matches_direct_machine_for_qualifying_fixture(self):
        expected = self.direct_machine("qualify")
        result = boundary.evaluate(emitter.emit("qualify"))
        self.assertEqual(result["state"], S_LOCKED)
        self.assertEqual(result["barsConsumed"], expected.bars_seen)
        self.assertEqual(result["decision"], expected.decision)

    def test_boundary_matches_direct_machine_for_rejecting_fixture(self):
        expected = self.direct_machine("reject")
        result = boundary.evaluate(emitter.emit("reject"))
        self.assertEqual(result["state"], S_BROKEN)
        self.assertEqual(result["barsConsumed"], expected.bars_seen)
        self.assertIsNone(result["decision"])
        self.assertIsNone(expected.decision)

    def test_cli_round_trip_uses_exact_json_envelope(self):
        proc = subprocess.run(
            [sys.executable, os.path.join(HERE, "boundary.py")],
            input=emitter.json_text("qualify"), text=True, capture_output=True, check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        response = json.loads(proc.stdout)
        self.assertTrue(response["ok"])
        self.assertEqual(response["response"], boundary.evaluate(emitter.emit("qualify")))

    def assert_refusal(self, mutate, code):
        request = emitter.emit("qualify")
        mutate(request)
        with self.assertRaises(boundary.Refusal) as caught:
            boundary.evaluate(request)
        self.assertEqual(caught.exception.code, code)

    def test_unknown_top_level_field_refuses(self):
        self.assert_refusal(lambda request: request.update({"surprise": True}),
                            "REFUSE_REQUEST_UNKNOWN_FIELD")

    def test_unknown_nested_field_refuses(self):
        self.assert_refusal(lambda request: request["zone"].update({"surprise": True}),
                            "REFUSE_ZONE_UNKNOWN_FIELD")

    def test_missing_required_field_refuses(self):
        self.assert_refusal(lambda request: request.pop("zone"), "REFUSE_REQUEST_MISSING_FIELD")

    def test_wrong_schema_refuses(self):
        self.assert_refusal(lambda request: request.update({"schemaVersion": "v0"}),
                            "REFUSE_SCHEMA_VERSION")

    def test_invalid_zone_range_refuses(self):
        self.assert_refusal(lambda request: request["zone"].update({"low": 101.0}),
                            "REFUSE_ZONE_RANGE")

    def test_invalid_zone_role_refuses(self):
        self.assert_refusal(lambda request: request["zone"].update({"role": "inside"}),
                            "REFUSE_ZONE_ROLE")

    def test_noncontiguous_bars_refuse(self):
        self.assert_refusal(lambda request: request["bars"][3].update({"index": 99}),
                            "REFUSE_BAR_INDEX")

    def test_malformed_ohlc_refuses(self):
        self.assert_refusal(lambda request: request["bars"][0].update({"low": 200.0}),
                            "REFUSE_BAR_OHLC")

    def test_invalid_availability_refuses(self):
        self.assert_refusal(lambda request: request["zone"].update({"availableFromIndex": 999}),
                            "REFUSE_ZONE_AVAILABILITY")

    def test_cli_refuses_non_json_with_named_result(self):
        proc = subprocess.run([sys.executable, os.path.join(HERE, "boundary.py")], input="nope",
                              text=True, capture_output=True, check=False)
        self.assertEqual(proc.returncode, 2)
        response = json.loads(proc.stdout)
        self.assertFalse(response["ok"])
        self.assertEqual(response["refusal"]["code"], "REFUSE_JSON")

    def test_cli_refuses_duplicate_json_fields(self):
        text = emitter.json_text("qualify")
        duplicate = text.replace('"schemaVersion":"mogo.lean.zone-request.v1"',
                                 '"schemaVersion":"wrong","schemaVersion":"mogo.lean.zone-request.v1"')
        proc = subprocess.run([sys.executable, os.path.join(HERE, "boundary.py")],
                              input=duplicate, text=True, capture_output=True, check=False)
        self.assertEqual(proc.returncode, 2)
        response = json.loads(proc.stdout)
        self.assertEqual(response["refusal"]["code"], "REFUSE_JSON_DUPLICATE_FIELD")

    def test_derived_nonfinite_result_refuses_instead_of_emitting_Infinity(self):
        request = emitter.emit("qualify")
        request["config"]["minRR"] = 1e308
        request["config"]["stopATRBuffer"] = 1e308
        with self.assertRaises(boundary.Refusal) as caught:
            boundary.evaluate(request)
        self.assertEqual(caught.exception.code, "REFUSE_NONFINITE_RESULT")

        proc = subprocess.run([sys.executable, os.path.join(HERE, "boundary.py")],
                              input=json.dumps(request), text=True, capture_output=True,
                              check=False)
        self.assertEqual(proc.returncode, 2)
        self.assertNotIn("Infinity", proc.stdout)
        self.assertEqual(json.loads(proc.stdout)["refusal"]["code"],
                         "REFUSE_NONFINITE_RESULT")

    def test_cli_refuses_nonstandard_nonfinite_input_number(self):
        text = emitter.json_text("qualify").replace('"minRR":2.0', '"minRR":NaN')
        proc = subprocess.run([sys.executable, os.path.join(HERE, "boundary.py")],
                              input=text, text=True, capture_output=True, check=False)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(json.loads(proc.stdout)["refusal"]["code"], "REFUSE_JSON_NUMBER")

    def test_bar_count_limit_refuses_before_evaluation(self):
        request = emitter.emit("qualify")
        request["bars"] = request["bars"] * (boundary.MAX_BARS // len(request["bars"]) + 1)
        with self.assertRaises(boundary.Refusal) as caught:
            boundary.evaluate(request)
        self.assertEqual(caught.exception.code, "REFUSE_BARS_LIMIT")

    def test_cli_request_size_limit_refuses(self):
        oversized = " " * (boundary.MAX_REQUEST_BYTES + 1)
        proc = subprocess.run([sys.executable, os.path.join(HERE, "boundary.py")],
                              input=oversized, text=True, capture_output=True, check=False)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(json.loads(proc.stdout)["refusal"]["code"], "REFUSE_REQUEST_SIZE")


if __name__ == "__main__":
    unittest.main()

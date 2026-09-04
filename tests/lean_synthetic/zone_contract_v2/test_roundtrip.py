"""V2 contract tests: closed local synthetic input only."""
import copy, json, os, subprocess, sys, unittest
HERE = os.path.dirname(os.path.realpath(__file__)); SYNTHETIC = os.path.dirname(HERE)
if SYNTHETIC not in sys.path: sys.path.insert(0, SYNTHETIC)
from zone_contract_v2 import boundary, mogo_synthetic_emitter as emitter

class TestZoneContractV2(unittest.TestCase):
    def refusal(self, mutate, code):
        request = emitter.emit("buy"); mutate(request)
        with self.assertRaises(boundary.Refusal) as caught: boundary.evaluate(request)
        self.assertEqual(caught.exception.code, code)

    def test_closed_envelope_and_deterministic_fixtures(self):
        for case in ("buy", "sell"):
            request = emitter.emit(case)
            self.assertEqual(set(request), boundary.TOP); self.assertEqual(len(request["bars"]), 120)
            self.assertEqual(emitter.json_text(case), emitter.json_text(case))

    def test_mirrored_buy_resistance_breaks_up_and_qualifies(self):
        result = boundary.evaluate(emitter.emit("buy"))
        self.assertEqual(result["decision"]["direction"], "buy")
        self.assertEqual(result["decision"]["brokenDirection"], "upThroughResistance")
        self.assertEqual(result["decision"]["breakBarIndex"], 40)

    def test_mirrored_sell_support_breaks_down_and_qualifies(self):
        result = boundary.evaluate(emitter.emit("sell"))
        self.assertEqual(result["decision"]["direction"], "sell")
        self.assertEqual(result["decision"]["brokenDirection"], "downThroughSupport")
        self.assertEqual(result["decision"]["breakBarIndex"], 40)

    def test_cli_roundtrip_uses_exact_v2_envelope(self):
        proc = subprocess.run([sys.executable, os.path.join(HERE,"boundary.py")], input=emitter.json_text("sell"), text=True, capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stderr); output = json.loads(proc.stdout)
        self.assertTrue(output["ok"]); self.assertEqual(output["response"], boundary.evaluate(emitter.emit("sell")))

    def test_direction_role_contradictions_refuse(self):
        self.refusal(lambda r:r["zone"].update({"preBreakRole":"support"}), "REFUSE_ROLE_DIRECTION")
        self.refusal(lambda r:r["breakEvent"].update({"brokenDirection":"downThroughSupport"}), "REFUSE_ROLE_DIRECTION")

    def test_break_geometry_and_setup_type_refuse(self):
        self.refusal(lambda r:r["breakEvent"]["at"].update({"index":39,"barStartTimeUtcMs":r["bars"][39]["startTimeUtcMs"],"closeTimeUtcMs":r["bars"][40]["startTimeUtcMs"]}), "REFUSE_BREAK_GEOMETRY")
        self.refusal(lambda r:r["setup"].update({"type":"reversal"}), "REFUSE_SETUP_TYPE")
        self.refusal(lambda r:r["setup"].update({"reaction":"touch"}), "REFUSE_SETUP_REACTION")

    def test_provenance_index_timestamp_and_order_contradictions_refuse(self):
        self.refusal(lambda r:r["zone"]["formedAt"].update({"barStartTimeUtcMs":1}), "REFUSE_PROVENANCE_TIMESTAMP")
        self.refusal(lambda r:r["zone"]["formedAt"].update({"closeTimeUtcMs":1}), "REFUSE_PROVENANCE_CLOSE_TIME")
        self.refusal(lambda r:r["setup"]["qualificationAt"].update({"index":40,"barStartTimeUtcMs":r["bars"][40]["startTimeUtcMs"],"closeTimeUtcMs":r["bars"][41]["startTimeUtcMs"]}), "REFUSE_PROVENANCE_ORDER")
        self.refusal(lambda r:r["setup"]["qualificationAt"].update({"index":56,"barStartTimeUtcMs":r["bars"][56]["startTimeUtcMs"],"closeTimeUtcMs":r["bars"][57]["startTimeUtcMs"]}), "REFUSE_QUALIFICATION_MISMATCH")
        self.refusal(lambda r:r["setup"]["retestAt"].update({"index":53,"barStartTimeUtcMs":r["bars"][53]["startTimeUtcMs"],"closeTimeUtcMs":r["bars"][54]["startTimeUtcMs"]}), "REFUSE_RETEST_MISMATCH")

    def test_timestamp_semantics_and_timeframe_refuse(self):
        self.refusal(lambda r:r.update({"barTimestampSemantics":"CLOSE_TIME"}), "REFUSE_TIMESTAMP_SEMANTICS")
        self.refusal(lambda r:r["identity"].update({"timeframe":"M15"}), "REFUSE_TIMEFRAME")

    def test_unknown_duplicate_nonfinite_and_resource_refuse(self):
        self.refusal(lambda r:r.update({"extra":True}), "REFUSE_REQUEST_UNKNOWN_FIELD")
        self.refusal(lambda r:r["config"].update({"minRR":float("inf")}), "REFUSE_NUMBER")
        request = emitter.emit("buy"); request["bars"] *= boundary.MAX_BARS // len(request["bars"]) + 1
        with self.assertRaises(boundary.Refusal) as caught: boundary.evaluate(request)
        self.assertEqual(caught.exception.code, "REFUSE_BARS_LIMIT")
        duplicate = emitter.json_text("buy").replace('"schemaVersion":"mogo.lean.zone-request.v2"','"schemaVersion":"x","schemaVersion":"mogo.lean.zone-request.v2"')
        proc = subprocess.run([sys.executable, os.path.join(HERE,"boundary.py")],input=duplicate,text=True,capture_output=True)
        self.assertEqual(json.loads(proc.stdout)["refusal"]["code"], "REFUSE_JSON_DUPLICATE_FIELD")

    def test_timeframe_cadence_refuses(self):
        self.refusal(lambda r:r["bars"][-1].update({"startTimeUtcMs":r["bars"][-2]["startTimeUtcMs"]+1}),
                     "REFUSE_BAR_CADENCE")

    def test_dataset_hash_shape_refuses(self):
        self.refusal(lambda r:r["dataset"]["hash"].update({"algorithm":"MD5"}),
                     "REFUSE_HASH_ALGORITHM")
        self.refusal(lambda r:r["dataset"]["hash"].update({"value":"not-a-hash"}),
                     "REFUSE_HASH_VALUE")

if __name__ == "__main__": unittest.main()

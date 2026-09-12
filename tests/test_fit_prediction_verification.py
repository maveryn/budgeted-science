"""CPU-only contract tests; no credentials, model transport or paid calls."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from budgeted_science.agents.records import RunLog, read_events
from budgeted_science.fit_prediction_verification import numerics as n
from budgeted_science.fit_prediction_verification.environment import Episode
from budgeted_science.fit_prediction_verification import experiment as e


def fixture():
    p = [.9, .065, 1.2]
    cal = n.solve(p, "calibration", "dop_tight")
    pred = n.solve(p, "prediction", "dop_tight")
    return {"id": "synthetic-test", "calibration": cal, "prediction": pred,
            "fit": {"theta": p, "rmse": 0., "result_id": "original-calibration"},
            "public": {"data": cal["values"], "claim": {"value": pred["q"], "tolerance": .03},
                       "calibration_times": n.CAL_TIMES.tolist(), "calibration_initial": n.CAL_INITIAL},
            "reference": {"q": pred["q"]}, "private": {"family": "fixture"}}


class NumericalTests(unittest.TestCase):
    def test_dynamics_expression(self):
        p = [.9, .065, 1.2]
        x, y = 12., 7.
        np.testing.assert_allclose(n.rhs(0., [x,y], p),
                                   [x*(p[0]-p[1]*y-.01*x), y*(.9*p[1]*x-p[2])])

    def test_rk_work_and_endpoints(self):
        r = n.solve([.9,.065,1.2], "prediction", "rk2_0.2")
        self.assertEqual(r["work"], 240)
        self.assertEqual(r["nodes"]["times"][-1], 24.)
        self.assertEqual(r["values"][0], list(n.PRED_INITIAL))
        self.assertEqual(r["q"], r["values"][-1][0])
        self.assertTrue(np.isfinite(r["values"]).all())

    def test_rhs_meter_matches_invocations(self):
        with patch.object(n, "rhs", wraps=n.rhs) as calls:
            r = n.solve([.9,.065,1.2], "prediction", "dop_loose")
        self.assertEqual(r["work"], calls.call_count)
        self.assertEqual(r["status"], "complete")

    def test_interrupted_work_and_no_fake_output(self):
        for method in ("dop_tight", "rk2_0.2"):
            r = n.solve([.9,.065,1.2], "prediction", method, 7)
            self.assertEqual(r["work"], 7)
            self.assertEqual(r["status"], "budget_exhausted")
            self.assertIsNone(r["q"])
            self.assertEqual(r["values"], [])
            self.assertIsNotNone(r["last_rhs_state"])

    def test_numerical_failure_retains_work(self):
        r = n.solve([1.2,.1,1.6], "prediction", "rk2_0.8")
        self.assertEqual(r["status"], "failed")
        self.assertGreater(r["work"], 0)
        self.assertIsNone(r["q"])

    def test_invalid_inputs(self):
        for p in ([1,2], [1,.08,float("nan")], [1,.08,3], [True,True,True], ["1", ".08", "1.4"]):
            with self.assertRaises(ValueError):
                n.solve(p, "prediction")
        for cap in (-1, True, 2.5):
            with self.assertRaises(ValueError):
                n.solve([1,.08,1.4], "prediction", work_limit=cap)

    def test_deterministic_outputs(self):
        a = n.solve([.9,.065,1.2], "prediction", "dop_loose")
        b = n.solve([.9,.065,1.2], "prediction", "dop_loose")
        a.pop("seconds"); b.pop("seconds")
        self.assertEqual(a,b)

    def test_fitter_injected_and_best_completed(self):
        data = np.zeros((8,2))
        calls = []
        def predictor(p):
            if len(calls) == 3:
                raise n.WorkExhausted()
            calls.append(list(p))
            return {"values": np.ones((8,2))*(4-len(calls)), "result_id": str(len(calls))}
        with patch.object(n, "solve", side_effect=AssertionError("unpaid solver")):
            out = n.fit_step([1,.08,1.4], data, predictor)
        self.assertEqual(out["status"], "budget_exhausted")
        self.assertEqual(out["best"]["result_id"], "3")
        self.assertEqual(out["best"]["theta"], calls[-1])

    def test_full_fitter_uses_injected_predictions(self):
        count = 0
        def predictor(p):
            nonlocal count
            count += 1
            if count > 2:
                raise n.WorkExhausted()
            return {"values": np.ones((8,2)), "result_id": str(count)}
        with patch.object(n, "solve", side_effect=AssertionError("unpaid solver")):
            out = n.fit_full([1,.08,1.4], np.zeros((8,2)), predictor)
        self.assertEqual(out["status"], "budget_exhausted")
        self.assertIsNotNone(out["best"])


class InterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.study = fixture()

    def episode(self, credits=4):
        return Episode(self.study, credits)

    def test_invalid_budget(self):
        for b in (-1, True, float("nan"), .0001):
            with self.assertRaises(ValueError):
                self.episode(b)

    def test_invalid_tools_uncharged(self):
        ep = self.episode()
        for name,args in (("bad",{}), ("record",{"id":"hidden-reference"}),
                          ("register_fit",{"theta":[1,.08,5]}),
                          ("predict",{"fit_id":"original-fit","method":"bad","max_work":100}),
                          ("fit_step",{"fit_id":"original-fit","method":"dop_loose","max_work":True})):
            self.assertIn("error", ep.tools.call(name,args))
        self.assertEqual(ep.spent,0)

    def test_no_private_reference_in_description(self):
        ep = self.episode()
        view = ep.tools.call("describe")
        self.assertNotIn("private", view)
        self.assertNotIn("reference", view)
        self.assertNotIn("family", json.dumps(view))
        view["fit"]["theta"][0] = 123
        self.assertNotEqual(ep.fits["original-fit"]["theta"][0],123)

    def test_original_retrieval_and_purchase_free(self):
        ep = self.episode(0)
        r = ep.tools.call("predict",{"fit_id":"original-fit","method":"dop_tight","max_work":0})
        self.assertTrue(r["reuse"])
        self.assertEqual(ep.spent,0)
        self.assertIn("record",ep.tools.call("record",{"id":"original-prediction"}))

    def test_duplicate_call_protection(self):
        ep = self.episode()
        args = {"fit_id":"original-fit","method":"dop_loose","max_work":1024}
        r = ep.tools.call("predict",args,"a")
        spent = ep.spent
        self.assertEqual(ep.tools.call("predict",args,"a"),r)
        self.assertEqual(ep.spent,spent)
        with self.assertRaises(ValueError):
            ep.tools.call("budget",{},"a")

    def test_reuse_independent_episodes(self):
        a,b = self.episode(),self.episode()
        args = {"fit_id":"original-fit","method":"dop_loose","max_work":1024}
        ra,rb = a.tools.call("predict",args),b.tools.call("predict",args)
        self.assertEqual(ra,rb)
        spent = a.spent
        a.tools.call("predict",args)
        self.assertEqual(a.spent,spent)
        self.assertEqual(b.spent,spent)

    def test_interruption_charge_and_partial_cache(self):
        ep = self.episode()
        args = {"fit_id":"original-fit","method":"dop_loose","max_work":7}
        a = ep.tools.call("predict",args)
        b = ep.tools.call("predict",args)
        self.assertEqual(a["result_id"],b["result_id"])
        self.assertEqual(ep.spent,7)
        self.assertEqual(a["status"],"budget_exhausted")
        self.assertEqual(ep.work_by_stage,{"calibration":0,"prediction":7})

    def test_failed_solve_charged_and_cached(self):
        ep = self.episode()
        fid = ep.tools.call("register_fit",{"theta":[1.2,.1,1.6]})["fit_id"]
        args = {"fit_id":fid,"method":"rk2_0.8","max_work":1024}
        first = ep.tools.call("predict",args)
        again = ep.tools.call("predict",args)
        self.assertEqual(first["status"],"failed")
        self.assertGreater(ep.spent,0)
        self.assertTrue(again["reuse"])
        self.assertEqual(ep.spent, first["charge_work"])

    def test_unaccounted_failure_reserves_cap(self):
        ep = self.episode()
        with patch.object(n,"solve",side_effect=RuntimeError("synthetic")):
            with self.assertRaises(RuntimeError):
                ep.tools.call("predict",{"fit_id":"original-fit","method":"dop_loose","max_work":17})
        self.assertEqual(ep.state,"aborted")
        self.assertEqual(ep.spent,17)

    def test_fitting_is_calibration_only_and_cap_enforced(self):
        ep = self.episode()
        fid = ep.tools.call("register_fit",{"theta":[1,.08,1.4]})["fit_id"]
        out = ep.tools.call("fit_step",{"fit_id":fid,"method":"dop_loose","max_work":300})
        self.assertEqual(out["status"],"budget_exhausted")
        self.assertEqual(ep.spent,300)
        self.assertEqual(ep.work_by_stage["prediction"],0)
        self.assertIsNotNone(out["fit"]["result_id"])
        self.assertEqual(out["fit"]["theta"],ep.runs[out["fit"]["result_id"]]["theta"])

    def test_prediction_does_not_refit(self):
        ep = self.episode()
        fid = ep.tools.call("register_fit",{"theta":[1,.08,1.4]})["fit_id"]
        with patch.object(n,"fit_full",side_effect=AssertionError("refit")), patch.object(n,"fit_step",side_effect=AssertionError("refit")):
            out = ep.tools.call("predict",{"fit_id":fid,"method":"dop_loose","max_work":1024})
        self.assertEqual(out["theta"],[1,.08,1.4])
        self.assertEqual(ep.work_by_stage["calibration"],0)

    def test_integral_fit_and_registration_no_solver(self):
        ep = self.episode()
        with patch.object(n,"solve",side_effect=AssertionError("unpaid solver")), patch.object(n,"reference",side_effect=AssertionError("reference")):
            p = e.integral_estimate(ep.tools.call("describe")["study"])
            r = ep.tools.call("register_fit",{"theta":p})
        self.assertIsNone(r["fit"]["rmse"])
        self.assertEqual(ep.spent,0)

    def test_zero_budget_free_submission(self):
        ep = self.episode(0)
        ep.tools.call("submit",{"verdict":"ACCEPT","evidence_ids":["original-prediction"],"justification":"fixture"})
        self.assertTrue(ep.evaluation()["correct"])
        with self.assertRaises(ValueError):
            ep.tools.call("budget")

    def test_invalid_evidence_does_not_close(self):
        ep = self.episode()
        self.assertIn("error",ep.tools.call("submit",{"verdict":"ACCEPT","evidence_ids":["unknown"],"justification":"x"}))
        self.assertEqual(ep.state,"active")

    def test_abstention_and_incomplete_separate(self):
        ep = self.episode()
        self.assertTrue(ep.evaluation()["incomplete"])
        ep.tools.call("submit",{"verdict":"ABSTAIN","evidence_ids":[],"justification":"uncertain"})
        v = ep.evaluation()
        self.assertTrue(v["abstained"])
        self.assertFalse(v["correct"])
        self.assertFalse(v["incomplete"])

    def test_scoring_boundary_original_claim(self):
        study = deepcopy(self.study)
        study["reference"]["q"] = 100
        study["public"]["claim"]["value"] = 103
        self.assertTrue(Episode(study,0).evaluation()["valid"])
        study["public"]["claim"]["value"] = 103.00001
        self.assertFalse(Episode(study,0).evaluation()["valid"])

    def test_log_work_totals_and_complete_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = RunLog(tmp,"test")
            ep = Episode(self.study,4,log)
            r = ep.tools.call("predict",{"fit_id":"original-fit","method":"dop_loose","max_work":1024})
            log.close()
            events,torn = read_events(log.path)
            self.assertFalse(torn)
            self.assertEqual(sum(v["charge_work"] for v in events if v["kind"] == "solver_finished"),ep.spent)
            saved = json.loads(next((log.path/"numerical").glob("*.json")).read_text())
            self.assertEqual(saved["q"],r["q"])
            self.assertEqual(len(saved["values"]),241)


class CatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.studies, cls.sweep = e.build_catalog()

    def test_catalog_counts_and_literal_values(self):
        self.assertEqual(len(self.studies),10)
        self.assertEqual(len(self.sweep),90)
        self.assertEqual(len({s["id"] for s in self.studies}),10)
        self.assertEqual(sum(Episode(s,0).evaluation()["valid"] for s in self.studies),4)
        for s in self.studies:
            self.assertEqual(s["public"]["claim"]["value"],float(format(s["prediction"]["q"],".10g")))
            self.assertEqual(s["prediction"]["status"],"complete")

    def test_reference_checks_and_recoverability(self):
        for s in self.studies:
            c = s["reference"]["checks"]
            self.assertLess(c["calibration_max_abs"],1e-6)
            self.assertLess(c["prediction_max_abs"],1e-6)
            for r in c["recovered"]:
                self.assertLess(r["relative_parameter_error"],1e-6)
                self.assertGreater(r["smallest_scaled_jacobian_singular_value"],1e-3)

    def test_admission_categories(self):
        for system in (0,1):
            rows = [s for s in self.studies if s["private"]["system_index"] == system]
            self.assertEqual({s["private"]["family"] for s in rows},{"sound","fit","prediction","both","harmless_combination"})
            for s in rows:
                error = Episode(s,0).evaluation()["relative_claim_error"]
                if s["private"]["family"] in ("fit","prediction","both"):
                    self.assertGreaterEqual(error,.036)
                else:
                    self.assertLessEqual(error,.024)


class ReportingTests(unittest.TestCase):
    def test_offline_regeneration_and_slot_integrity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = RunLog(tmp,"test")
            root.write_json("manifest.json",{"cases":[{"id":"one"}],"targets":[[1,.08,1.4]],"budgets":[4],"policies":["test"]})
            child = RunLog(root.path/"episodes","test")
            child.event("tool_request",name="budget",arguments={})
            child.write_json("result.json",{"case_id":"one","family":"fixture","budget":4,"policy":"test","seconds":1.,
                "evaluation":{"correct":True,"abstained":False,"incomplete":False,"spent":2.,"verdict":"REJECT","valid":False},
                "path":child.path.relative_to(root.path).as_posix()})
            child.close(); root.close()
            with patch.object(n,"solve",side_effect=AssertionError("rerun")), patch.object(Episode,"call",side_effect=AssertionError("tool")):
                a = e.render(root.path)
                before = (root.path/"report.md").read_bytes()
                b = e.render(root.path)
            self.assertEqual(a,b)
            self.assertEqual(before,(root.path/"report.md").read_bytes())
            self.assertEqual(a["missing_slots"],0)
            self.assertEqual(a["by_budget"]["4"]["test"]["correct"],1)
            self.assertTrue((child.path/"transcript.md").exists())
            extra = RunLog(root.path/"episodes","duplicate")
            extra.write_json("result.json",json.loads((child.path/"result.json").read_text()))
            extra.close()
            with self.assertRaises(ValueError):
                e.render(root.path)


if __name__ == "__main__":
    unittest.main()

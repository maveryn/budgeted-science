"""CPU-only shared-investigator verification adapter and logging checks."""

import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import numpy as np

from budgeted_science.agents.records import RunLog, read_events
from budgeted_science.agents import target_three_claims as existing
from budgeted_science.paired_claim_audit import adaptive_target_three_policy as policy
from budgeted_science.paired_claim_audit import adaptive_target_three_pilot as pilot
from budgeted_science.paired_claim_audit.target_three_policy import inferred_verdicts
from budgeted_science.resource_planning import environment
from budgeted_science.resource_planning.adaptive_design import Forward
from budgeted_science.resource_planning.config import harder_config


def fixture():
    """Synthetic test system, not one of the six evaluated studies."""
    config = harder_config(32)
    reported = [1., .08, 1.4]
    target = [1.04, .085, 1.45]
    original = environment._solve_low(reported, config).sample(config.working_times)
    values = environment._solve_high(target, config).sample(config.working_times)
    claims = [
        {"id":"C1","kind":"target_parameter_accuracy","scope":"fixed_target","operator":"le","threshold":.05},
        {"id":"C2","kind":"target_integral","scope":"fixed_target","operator":"ge","threshold":140.},
        {"id":"C3","kind":"target_late_recovery","scope":"fixed_target","operator":"ge","threshold":.05},
    ]
    public = {"claims":claims,"report_parameters":reported,"environment":config.public(),
              "report":"Synthetic fixture only.",
              "original":{"id":"original","fidelity":"low","step":.1,
                          "times":list(config.working_times),"values":original.tolist()}}
    labels, quantities = inferred_verdicts(public, target, values)
    truth = {c["id"]:{"verdict":labels[c["id"]],"reference_value":quantities[c["kind"]]} for c in claims}
    return {"case_id":"synthetic-fixture","study":{"version":existing.VERSION,"public":public,
        "private":{"target_parameters":target,"noise_seed":99117,"truth":truth}}}


class AdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.case = fixture()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.log = RunLog(Path(self.tmp.name),"test")
        self.episode = existing.Episode(pilot.CPUConfig(),existing.Instance(deepcopy(self.case["study"])),self.log)
        self.tools = policy.AdaptiveTools(self.call,self.case["study"]["public"],self.log.event)

    def tearDown(self):
        self.log.close()
        self.tmp.cleanup()

    def call(self,name,**args):
        return self.episode.execute(f"call-{self.episode.request_count+1}",name,json.dumps(args))

    def test_planning_algorithm_is_byte_identical(self):
        source=Path(pilot.REPO)/"shared/budgeted_science/resource_planning/adaptive_design.py"
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),pilot.PLANNING_POLICY_HASH)

    def test_original_report_is_free_available_evidence(self):
        evidence=self.tools.evidence()
        self.assertEqual(len(evidence["simulations"]),1)
        self.assertEqual(evidence["simulations"][0]["result_id"],"original")
        np.testing.assert_equal(evidence["simulations"][0]["values"],self.case["study"]["public"]["original"]["values"])
        result=self.call("simulate_low",theta=self.case["study"]["public"]["report_parameters"])
        self.assertEqual(result["charge"],0)
        self.assertEqual(self.episode.environment.status()["spent"],0)
        self.assertEqual(len(self.tools.evidence()["simulations"]),1)

    def test_no_hidden_fields_reach_adapter(self):
        material=json.dumps({"config":self.tools.public_config,"public":self.tools.public,
                             "evidence":self.tools.evidence()})
        for key in ("target_parameters","noise_seed","reference_value","truth","private"):
            self.assertNotIn('"'+key+'":',material)
        tree=ast.parse(Path(policy.__file__).read_text())
        names={n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute)}
        self.assertFalse({"evaluate","_environment","_theta_true","_solve_high","_solve_low"} & names)

    def test_submission_matches_fitted_prediction_and_old_verdict_rules(self):
        self.call("simulate_high",theta=[1.,.08,1.4])
        evidence=self.tools.evidence()
        model=Forward(evidence,self.tools.public_config)
        theta=[1.03,.083,1.43]
        point=(np.array(theta)-model.lower)/model.width
        mean,_=model.predict(point,1)
        table=(model.scale*np.exp(mean[0]*model.times)).reshape(-1,2)
        expected,q=inferred_verdicts(self.tools.public,theta,table)
        before=self.episode.environment.status()["spent"]
        with patch.object(environment,"_solve_low",side_effect=AssertionError("unpaid")), \
             patch.object(environment,"_solve_high",side_effect=AssertionError("unpaid")):
            result=self.tools.submit(theta)
        self.assertEqual(result["status"],"submitted")
        self.assertEqual(self.episode.submission["verdicts"],expected)
        self.assertEqual(self.episode.environment.status()["spent"],before)
        events,_=read_events(self.log.path)
        recorded=next(e for e in events if e["kind"]=="adaptive_audit_prediction")
        np.testing.assert_array_equal(recorded["predicted_table"],table)
        self.assertEqual(recorded["estimated_quantities"],q)

    def test_bad_fitted_trajectory_abstains_without_clipping_or_physics(self):
        with patch.object(Forward,"predict",return_value=(np.full((1,32),1e6),np.array([.1]))), \
             patch.object(environment,"_solve_high",side_effect=AssertionError("unpaid")):
            self.tools.submit([1.,.08,1.4])
        self.assertEqual(set(self.episode.submission["verdicts"].values()),{"ABSTAIN"})
        event=next(e for e in read_events(self.log.path)[0] if e["kind"]=="adaptive_audit_prediction")
        self.assertFalse(event["prediction_valid"])
        self.assertIsNone(event["predicted_table"])

    def test_same_policy_metered_full_run(self):
        inside={"value":False}
        original=self.episode.environment.dispatch
        def dispatch(name,args):
            inside["value"]=name in ("simulate_low","simulate_high")
            try:return original(name,args)
            finally:inside["value"]=False
        def guard(function):
            def wrapped(*args,**kwargs):
                self.assertTrue(inside["value"],"unmetered physical simulation")
                return function(*args,**kwargs)
            return wrapped
        with patch.object(self.episode.environment,"dispatch",side_effect=dispatch), \
             patch.object(environment,"_solve_low",side_effect=guard(environment._solve_low)), \
             patch.object(environment,"_solve_high",side_effect=guard(environment._solve_high)), \
             patch.object(self.episode.environment,"evaluate",side_effect=AssertionError("private")):
            result=policy.run_policy(self.call,self.case["study"]["public"],self.log.event,time.monotonic()+300)
        self.assertEqual(result["submission"]["status"],"submitted")
        self.assertEqual(self.episode.environment.status()["spent"],32)
        self.assertLessEqual(self.episode.request_count,60)
        events,_=read_events(self.log.path)
        purchases=[e for e in events if e["kind"]=="adaptive_design_acquired"]
        self.assertEqual(sum(e["result"]["charge"] for e in purchases),32)
        self.assertEqual(sum(e["kind"]=="adaptive_design_fit" for e in events),len(purchases)+1)
        self.assertEqual(self.episode.evaluate()["total"],3)

    def test_expired_deadline_does_not_fabricate_verdict(self):
        with self.assertRaises(TimeoutError):
            policy.run_policy(self.call,self.case["study"]["public"],self.log.event,time.monotonic()-1)
        self.assertIsNone(self.episode.submission)

    def test_duplicate_call_id_does_not_purchase_twice(self):
        args=json.dumps({"theta":[1.05,.09,1.5]})
        first=self.episode.execute("same","simulate_high",args)
        second=self.episode.execute("same","simulate_high",args)
        self.assertEqual(first,second)
        self.assertEqual(self.episode.environment.status()["spent"],8)


class HarnessTests(unittest.TestCase):
    def test_contract_rejects_changed_schema_or_science(self):
        manifest=json.loads((pilot.PREPARED/"manifest.json").read_text())
        pilot.verify_contract(manifest)
        bad=deepcopy(manifest);bad["tools_hash"]="bad"
        with self.assertRaises(ValueError):pilot.verify_contract(bad)
        bad=deepcopy(manifest)
        bad["source_hashes"]["shared/budgeted_science/resource_planning/environment.py"]="bad"
        with self.assertRaises(ValueError):pilot.verify_contract(bad)

    def test_partial_campaign_reports_unfinished_attempt(self):
        with tempfile.TemporaryDirectory() as temp:
            root=RunLog(Path(temp),"partial")
            root.write_json("manifest.json",{"cases":["a","b"],"luna_view":"fixture"})
            root.write_json("saved_comparisons.json",[])
            root.event("case_started",case_id="a");root.close()
            result=pilot.render(root.path)
            self.assertFalse(result["complete"])
            self.assertEqual(result["attempted_without_result"],["a"])
            self.assertEqual(result["unattempted_cases"],["b"])
            self.assertIn("Partial campaign",(root.path/"report.md").read_text())

    def test_original_imports_match_and_no_solver_is_called(self):
        with patch.object(environment,"_solve_high",side_effect=AssertionError("unpaid")), \
             patch.object(environment,"_solve_low",side_effect=AssertionError("unpaid")):
            cases,rows,hashes,label=pilot.read_inputs()
        self.assertEqual(len(cases),6)
        self.assertEqual(len(rows),24)
        self.assertEqual(len({r["case_id"] for r in rows}),6)
        self.assertIn("retry",label)
        self.assertTrue(hashes)

    def test_offline_render_byte_identical_and_no_execution(self):
        case=fixture()
        with tempfile.TemporaryDirectory() as temp:
            root=RunLog(Path(temp),"fixture")
            root.write_json("manifest.json",{"cases":[case["case_id"]],"luna_view":"synthetic"})
            root.write_json("saved_comparisons.json",[])
            result=pilot.run_case(case,root.path)
            self.assertTrue(result["accounting_valid"])
            root.event("case_finished",result=result);root.event("finished",unchanged=True);root.close()
            first=pilot.render(root.path)
            files=[root.path/"report.md",Path(result["path"])/"transcript.md",Path(result["path"])/"trace.md"]
            before=[p.read_bytes() for p in files]
            with patch.object(environment,"_solve_high",side_effect=AssertionError("offline")), \
                 patch.object(environment,"_solve_low",side_effect=AssertionError("offline")), \
                 patch.object(pilot,"run_policy",side_effect=AssertionError("offline")):
                self.assertEqual(first,pilot.render(root.path))
            self.assertEqual(before,[p.read_bytes() for p in files])
            self.assertTrue(first["complete"])
            self.assertEqual(first["api_expenditure_usd"],0)

    def test_incomplete_outcome_retained(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(pilot,"run_policy",side_effect=TimeoutError("fixture")):
            result=pilot.run_case(fixture(),Path(temp))
            self.assertFalse(result["evaluation"]["completed"])
            self.assertEqual(result["evaluation"]["incomplete_claims"],3)
            self.assertEqual(result["termination_reason"],"cpu_incomplete")
            self.assertTrue((Path(result["path"])/"events.jsonl").exists())

    def test_aggregate_counts_and_wrong_answer_penalty(self):
        def evaluation(correct,wrong,abstain,incomplete):
            return {"completed":incomplete==0,"total":3,"correct":correct,"wrong":wrong,
                    "abstained":abstain,"incomplete_claims":incomplete,
                    "false_acceptances":wrong,"false_rejections":0,
                    "scientific_status":{"spent":32}}
        summary=pilot.aggregate([{"method":"a","evaluation":evaluation(2,1,0,0)},
                                 {"method":"a","evaluation":evaluation(0,0,0,3)}])[0]
        self.assertEqual((summary["correct"],summary["wrong"],summary["incomplete_claims"]),(2,1,3))
        self.assertEqual(summary["utility"],0)
        self.assertEqual(summary["coverage"],.5)
        self.assertEqual(summary["credits"],64)


if __name__ == "__main__":
    unittest.main()

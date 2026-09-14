"""Offline numerical algebra, information boundary, adaptivity, and accounting."""

import ast
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import numpy as np

from budgeted_science.resource_planning import adaptive_design as policy
from budgeted_science.resource_planning import environment as env
from budgeted_science.resource_planning.config import harder_config
from budgeted_science.resource_planning.adaptive_design_pilot import (
    aggregate, render, run_case, verify_pair,
)


def fixture():
    config = harder_config(32).public()
    times = np.array(config["working_times"])
    lower = np.array(config["bounds"])[:, 0]
    width = np.diff(config["bounds"]).ravel()
    # Synthetic responses, unrelated to the hidden physical equations.
    points = np.array([[.5,.5,.5], [.25,.5,.5], [.5,.25,.5], [.5,.5,.25], [.75,.7,.8]])
    def values(point, high):
        rates = np.column_stack((.2 + .1*point[0] + .04*point[1]*np.sin(times),
                                 -.1 + .1*point[2] + .03*point[1]*np.cos(times)))
        if not high:
            rates += .01 * times[:, None] / 8
        return np.array(config["initial"]) * np.exp(rates * times[:, None])
    rows = [{"status": "success", "theta": (lower + p*width).tolist(),
             "fidelity": "high" if high else "low", "values": values(p,high).tolist(),
             "times": times.tolist(), "result_id": str(i)}
            for i, (p, high) in enumerate([(p,False) for p in points] + [(points[0], True)])]
    target = values([.4,.6,.5], True)
    observations = [{"variable": v, "time": 1., "value": target[1,j]}
                    for j,v in enumerate(("x","y"))]
    return {"simulations": rows, "observations": observations}, config


class AlgebraTests(unittest.TestCase):
    def test_optimizer_and_boundary_duplicates_get_no_extra_mass(self):
        a=np.array([.4,.3,.2]); b=a+1e-7; c=np.array([.8,.7,.6])
        points=policy.distinct_points([a,b,c,c.copy()])
        self.assertEqual(len(points),2)
        np.testing.assert_equal(points[0],a)
        evidence,config=fixture()
        design=policy.Design(evidence,config)
        for i,point in enumerate(design.points):
            self.assertTrue(all(np.linalg.norm(point-other)>=policy.SETTINGS["mode_merge_distance"]
                                for other in design.points[i+1:]))

    def test_kernel_positive_definite_and_fidelity_decomposition(self):
        x = np.random.default_rng(1).uniform(size=(8,3))
        flags = np.arange(8) % 2
        k = policy._kernel(x, flags, x, flags)
        self.assertGreater(np.linalg.eigvalsh(k).min(), 0)
        np.testing.assert_allclose(policy._kernel(x,[0]*8,x,[0]*8),
                                   policy._kernel(x,[0]*8,x,[1]*8))

    def test_gp_conditioning_matches_direct_solve(self):
        evidence, config = fixture()
        model = policy.Forward(evidence, config)
        q = np.array([[.4,.3,.2], [.7,.6,.8]])
        k = policy._kernel(model.x, model.flags, model.x, model.flags) + np.eye(len(model.x))*policy.SETTINGS["jitter"]
        cross = policy._kernel(q, [1,1], model.x, model.flags)
        mean,var = model.predict(q)
        np.testing.assert_allclose(mean, cross @ np.linalg.solve(k,model.values), atol=1e-10)
        np.testing.assert_allclose(var, np.diag(policy._kernel(q,[1,1],q,[1,1])) -
                                   np.sum(cross*np.linalg.solve(k,cross.T).T,axis=1), atol=1e-10)

    def test_full_trajectory_transformation_and_interpolation(self):
        evidence, config = fixture()
        model = policy.Forward(evidence, config)
        for row in evidence["simulations"]:
            point = (np.array(row["theta"])-model.lower)/model.width
            prediction,_ = model.predict(point,int(row["fidelity"]=="high"))
            restored = model.scale*np.exp(prediction[0]*model.times)
            np.testing.assert_allclose(restored,np.ravel(row["values"]),rtol=2e-6)

    def test_hypothetical_simulation_variance_matches_augmented_gp(self):
        evidence, config = fixture()
        model = policy.Forward(evidence, config)
        q, a = np.array([[.3,.4,.6], [.7,.8,.6]]), np.array([.4,.5,.6])
        mean,av = model.predict(a,1)
        expected = model.predict(q)[1] - model.cross(q,a,1)**2/(av[0]+policy.SETTINGS["jitter"])
        future = deepcopy(evidence)
        future["simulations"].append({"status":"success","theta":(model.lower+a*model.width).tolist(),
                                     "fidelity":"high","result_id":"fantasy","times":config["working_times"],
                                     "values":(model.scale*np.exp(mean[0]*model.times)).reshape(-1,2).tolist()})
        np.testing.assert_allclose(policy.Forward(future,config).predict(q)[1],expected,atol=1e-9)

    def test_fisher_rank_one_reduction_matches_direct_inverse(self):
        j = np.array([[[1.,2.,0.],[0.,1.,3.]]])
        variance, noise = np.array([.2]), np.array([.03,.01])
        c = policy.covariance(j,variance,noise)[0]
        q = np.array([1.,-2.,3.])
        cj = c@q
        reduction = cj@cj/(.15+q@cj)
        next_c = np.linalg.inv(np.linalg.inv(c)+np.outer(q,q)/.15)
        self.assertAlmostEqual(reduction,np.trace(c-next_c),places=12)

    def test_covariance_psd_and_reduces_with_more_precise_model(self):
        j = np.arange(12,dtype=float).reshape(2,2,3)/10
        a = policy.covariance(j,np.array([.3,.2]),np.array([.01,.02]))
        b = policy.covariance(j,np.array([.03,.02]),np.array([.01,.02]))
        self.assertTrue(np.all(np.linalg.eigvalsh(a)>0))
        self.assertTrue(np.all(np.linalg.eigvalsh(a-b)>-1e-12))

    def test_costs_affordability_and_duplicate_exclusion(self):
        evidence,config = fixture()
        design = policy.Design(evidence,config)
        actions = design.actions(32)
        self.assertEqual({(a["kind"],a.get("fidelity")) for a in actions},
                         {("simulation","low"),("simulation","high"),("observation",None)})
        for a in actions:
            self.assertAlmostEqual(a["score"],a["gain"]/a["cost"])
        self.assertTrue(all(a["cost"]<=7 for a in design.actions(7)))
        self.assertEqual(design.actions(0),[])
        used={(s["fidelity"],tuple(s["theta"])) for s in evidence["simulations"]}
        self.assertFalse(any((a.get("fidelity"),tuple(a.get("theta",[]))) in used for a in actions))

    def test_evidence_changes_fit_and_action_scores(self):
        a,config = fixture()
        b = deepcopy(a)
        b["observations"][0]["value"] *= 1.05
        da, db = policy.Design(a,config), policy.Design(b,config)
        self.assertGreater(np.linalg.norm(da.estimate-db.estimate),1e-3)
        aa,ab = da.actions(32),db.actions(32)
        self.assertNotEqual(json.dumps(aa),json.dumps(ab))
        ma={(x["variable"],x["time"]):x["score"] for x in aa if x["kind"]=="observation"}
        mb={(x["variable"],x["time"]):x["score"] for x in ab if x["kind"]=="observation"}
        self.assertGreater(max(abs(ma[k]-mb[k]) for k in ma),1e-7)

    def test_diagnostics_json_and_no_physical_calls(self):
        evidence,config = fixture()
        with patch.object(env,"_solve_low",side_effect=AssertionError("unpaid")), \
             patch.object(env,"_solve_high",side_effect=AssertionError("unpaid")), \
             patch.object(env.Episode,"_measure",side_effect=AssertionError("unpaid")):
            design = policy.Design(evidence,config)
            json.dumps(design.diagnostics(),allow_nan=False)
            json.dumps(design.actions(32),allow_nan=False)

    def test_failed_and_nonpositive_simulations_not_fitted(self):
        evidence,config = fixture()
        evidence["simulations"].append({"status":"failed","result_id":"failed"})
        bad=deepcopy(evidence["simulations"][0]); bad["result_id"]="negative"; bad["values"][0][0]=-1
        evidence["simulations"].append(bad)
        self.assertEqual(policy.Forward(evidence,config).excluded,["failed","negative"])

    def test_nonpositive_observation_is_explicit_failure(self):
        evidence,config=fixture()
        evidence["observations"][0]["value"]=-1
        with self.assertRaises(ValueError):
            policy.Design(evidence,config)


class ContractTests(unittest.TestCase):
    def test_import_boundary(self):
        tree=ast.parse(Path(policy.__file__).read_text())
        imports=[]
        for n in ast.walk(tree):
            if isinstance(n,ast.Import): imports.extend(x.name for x in n.names)
            elif isinstance(n,ast.ImportFrom): imports.append(n.module or "")
        self.assertFalse(any(any(word in name for word in ("environment","pilot","agents","pathlib","os")) for name in imports))
        names={n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute)}
        self.assertFalse({"_theta_true","_target","_episode","evaluate","_rhs"} & names)

    def test_complete_episode_paid_calls_only_and_replay(self):
        config=harder_config(32)
        e=env.Episode([1.,.08,1.4],config,noise_seed=123)
        active={"simulation":False}
        calls=[]
        class Tools:
            @property
            def public_config(self): return e.tools.public_config
            def evidence(self): return e.tools.evidence()
            def get_status(self): return e.tools.get_status()
            def submit(self,*args): return e.tools.submit(*args)
            def measure_target(self,*args):
                calls.append(("measurement",args))
                return e.tools.measure_target(*args)
            def simulate_low(self,*args): return self.simulate("low",args)
            def simulate_high(self,*args): return self.simulate("high",args)
            def simulate(self,fidelity,args):
                active["simulation"]=True
                calls.append((fidelity,args))
                try: return getattr(e.tools,"simulate_"+fidelity)(*args)
                finally: active["simulation"]=False
        def guard(original):
            def wrapped(*args,**kwargs):
                self.assertTrue(active["simulation"])
                return original(*args,**kwargs)
            return wrapped
        events=[]
        with patch.object(env,"_solve_low",side_effect=guard(env._solve_low)), \
             patch.object(env,"_solve_high",side_effect=guard(env._solve_high)), \
             patch.object(env.Episode,"evaluate",side_effect=AssertionError("private evaluator")):
            policy.run_adaptive_design(Tools(),log=lambda kind,**data:events.append((kind,data)))
        status=e.tools.get_status()
        self.assertEqual(status["spent"],32)
        self.assertEqual(status["remaining"],0)
        self.assertEqual(len(calls),len(status["ledger"]))
        self.assertEqual(sum({"low":1,"high":8,"measurement":12}[x[0]] for x in calls),32)
        self.assertEqual(sum(k=="adaptive_design_fit" for k,d in events),len(calls)+1)
        self.assertTrue(e.evaluate()["valid"])
        # Determinism of acquisitions, not just a repeated final value.
        other=env.Episode([1.,.08,1.4],config,noise_seed=123)
        policy.run_adaptive_design(other.tools)
        self.assertEqual(status["submission"],other.tools.get_status()["submission"])
        self.assertEqual(status["ledger"],other.tools.get_status()["ledger"])

    def test_deadline_does_not_submit_fallback(self):
        e=env.Episode([1.,.08,1.4],harder_config(32))
        with self.assertRaises(TimeoutError):
            policy.run_adaptive_design(e.tools,deadline=time.monotonic()-1)
        self.assertIsNone(e.tools.get_status()["submission"])

    def test_aggregate_incomplete_and_known_errors(self):
        rows=[{"method":"a","evaluation":{"valid":True,"success":True,"parameter_error":.5}},
              {"method":"a","evaluation":{"valid":True,"success":False,"parameter_error":2}},
              {"method":"a","evaluation":None}]
        g=aggregate(rows)[0]
        self.assertEqual((g["successes"],g["attempts"],g["incomplete"]),(1,3,1))
        self.assertAlmostEqual(g["mean_max_relative_error"],.0625)
        self.assertAlmostEqual(g["median_max_relative_error"],.0625)

    def test_matching_noisy_evidence_guard(self):
        evidence={"observations":[{"variable":"x","time":1,"value":3}]}
        saved=[{"case_seed":1,"method":"gpt-5.6-sol",
                "evaluation":{"scientific_status":{"observations":deepcopy(evidence["observations"])}}}]
        verify_pair(evidence,saved,1)
        evidence["observations"][0]["value"]=4
        with self.assertRaises(ValueError): verify_pair(evidence,saved,1)

    def test_saved_logs_and_offline_render_without_solver(self):
        from budgeted_science.agents.records import RunLog
        with tempfile.TemporaryDirectory() as directory:
            root=RunLog(Path(directory),"test")
            root.write_json("manifest.json",{"phase":"test"})
            root.write_json("saved_comparisons.json",[])
            result=run_case(5002,root.path)
            self.assertTrue(result["accounting_valid"])
            root.event("result",result=result);root.event("finished");root.close()
            with patch.object(env,"_solve_low",side_effect=AssertionError("offline")), \
                 patch.object(env,"_solve_high",side_effect=AssertionError("offline")), \
                 patch("budgeted_science.resource_planning.adaptive_design_pilot.run_adaptive_design",
                       side_effect=AssertionError("offline")):
                summary=render(root.path)
                self.assertEqual(summary,render(root.path))
            self.assertTrue(summary["complete"])
            self.assertTrue((Path(result["path"])/"trace.md").exists())


if __name__ == "__main__":
    unittest.main()

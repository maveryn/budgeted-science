"""CPU and fake-API checks for optional MMS tools and matched menus."""
import asyncio
from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from budgeted_science.agents import mms_alternatives as agent
from budgeted_science.agents import mms_alternatives_catalog as campaign
from budgeted_science.agents.mms_verification import MMSInstance, tool_definitions as original_tools
from budgeted_science.agents.records import RunLog, read_events
from budgeted_science.agents.verification_incremental_catalog import BatchBudget
from budgeted_science.mms_verification.alternatives import AlternativeAudit, AFFINE, iterative_solve
from budgeted_science.mms_verification.environment import Audit
from budgeted_science.mms_verification.numerics import PROBLEMS, DIAGNOSTIC, solve, errors, orders


class MMSAlternativesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases, cls.comparisons, cls.source = campaign.read_catalog(campaign.CATALOG)

    def episode(self, tmp, menu="expanded", index=0):
        case = self.cases[index]
        log = RunLog(tmp, "test")
        self.addCleanup(log.close)
        return agent.MenuEpisode(agent.MenuConfig(menu=menu),
            MMSInstance(case,self.comparisons[case["id"]],self.source),log)

    def test_affine_exactness_does_not_establish_order(self):
        for family,flavor in (("advection","upwind"),("mixed","neumann_first")):
            values = [errors(solve(PROBLEMS[family],AFFINE,n,flavor),AFFINE)["rms_error"] for n in (8,16,32)]
            self.assertLess(max(values),1e-12)
            with self.assertRaises(ValueError):
                orders(values)

    def test_iterative_solves_same_equations_including_faults(self):
        for family,flavor in (("diffusion","sound"),("advection","upwind"),("mixed","neumann_first")):
            a = solve(PROBLEMS[family],DIAGNOSTIC,16,flavor)
            b = iterative_solve(PROBLEMS[family],DIAGNOSTIC,16,flavor)
            self.assertEqual(b["status"],"complete")
            self.assertLess(b["scaled_residual"],1e-10)
            np.testing.assert_allclose(a["field"],b["field"],atol=1e-8,rtol=0)

    def test_original_tool_results_unchanged(self):
        a,b = Audit(self.cases[0],10),AlternativeAudit(self.cases[0],10)
        for i,(name,args) in enumerate((("run_mms",dict(family="diffusion",grid=8,kernel="audited")),
                                        ("run_study",dict(grid=32,kernel="independent")),("budget",{}))):
            first,second = a.call(str(i),name,**args),b.call(str(i),name,**args)
            first.get("result",{}).pop("seconds",None)
            second.get("result",{}).pop("seconds",None)
            self.assertEqual(first,second)

    def test_paid_reuse_duplicate_and_backend(self):
        backend = {}
        env = AlternativeAudit(self.cases[0],10,backend=backend)
        args = dict(family="advection",grid=16,kernel="audited")
        result = env.call("one","run_affine_mms",**args)
        self.assertEqual(env.call("one","run_affine_mms",**args),result)
        self.assertEqual(env.call("two","run_affine_mms",**args)["result"]["charge"],0)
        other = AlternativeAudit(self.cases[0],10,backend=backend)
        cached = other.call("one","run_affine_mms",**args)
        self.assertEqual(cached["result"]["origin"],"backend_cache")
        self.assertEqual(other.status()["spent"],1)
        self.assertEqual(other.call("x","crosscheck_linear_solver",result_id="run-001")["result"]["charge"],1)
        self.assertEqual(other.call("y","crosscheck_linear_solver",result_id="run-002")["result"]["charge"],0)

    def test_failed_iterative_charge_cache(self):
        backend = {}
        def broken(*args):
            raise RuntimeError("synthetic")
        env = AlternativeAudit(self.cases[0],10,backend=backend,iterative_executor=broken)
        result = env.call("a","crosscheck_linear_solver",result_id="original")
        self.assertEqual(result["result"]["status"],"failed")
        self.assertEqual(result["result"]["charge"],1)
        self.assertEqual(env.call("b","crosscheck_linear_solver",result_id="original")["result"]["charge"],0)
        other = AlternativeAudit(self.cases[0],10,backend=backend,iterative_executor=broken)
        self.assertEqual(other.call("a","crosscheck_linear_solver",result_id="original")["result"]["charge"],1)

    def test_invalid_unaffordable_no_charge(self):
        env = AlternativeAudit(self.cases[0],0)
        requests = [("run_affine_mms",dict(family="bad",grid=8,kernel="audited")),
                    ("run_affine_mms",dict(family="mixed",grid=True,kernel="audited")),
                    ("run_affine_mms",dict(family="mixed",grid=8,kernel="audited")),
                    ("crosscheck_linear_solver",dict(result_id="missing"))]
        for i,(name,args) in enumerate(requests):
            self.assertFalse(env.call(str(i),name,**args)["ok"])
        self.assertEqual(env.status()["spent"],0)
        self.assertTrue(env.call("s","submit",qoi="ABSTAIN",order="ABSTAIN",evidence_ids=[])["ok"])
        self.assertFalse(env.call("late","crosscheck_linear_solver",result_id="original")["ok"])

    def test_richardson_formula_free_no_solver_and_retrievable(self):
        env = AlternativeAudit(self.cases[0],10)
        coarse = env.call("c","run_study",grid=8,kernel="audited")["result"]
        spent = env.status()["spent"]
        with patch.object(env,"_executor",side_effect=AssertionError("unpaid solve")):
            r = env.call("r","richardson",coarse_id=coarse["id"],fine_id="original",assumed_order=2)
        fine = env.artifacts()["original"]
        self.assertAlmostEqual(r["result"]["extrapolated_q"],(4*fine["q"]-coarse["q"])/3)
        self.assertEqual(env.status()["spent"],spent)
        self.assertEqual(env.call("get","record",result_id=r["result"]["id"])["result"],r["result"])
        self.assertTrue(env.call("s","submit",qoi="ABSTAIN",order="ABSTAIN",evidence_ids=[r["result"]["id"]])["ok"])

    def test_richardson_rejects_incompatible_and_nonfinite(self):
        env = AlternativeAudit(self.cases[0],10)
        other = env.call("c","run_study",grid=8,kernel="independent")["result"]["id"]
        for i,p in enumerate((0,True,9,2)):
            self.assertFalse(env.call(str(i),"richardson",coarse_id=other,fine_id="original",assumed_order=p)["ok"])
        with self.assertRaises(ValueError):
            env.call("nan","richardson",coarse_id=other,fine_id="original",assumed_order=float("nan"))

    def test_identical_prompts_common_schemas_and_no_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b = self.episode(tmp,"original"),self.episode(tmp,"expanded")
            first = agent.prompts(a.config,a)
            second = agent.prompts(replace(b.config,api_ceiling_usd="1.45"),b)
            self.assertEqual(first,second)
            self.assertNotIn("USD 1.45",str(second))
            original = {t["name"]:t for t in original_tools()}
            expanded = {t["name"]:t for t in agent.tool_definitions(b.config)}
            self.assertTrue(all(t == expanded[n] for n,t in original.items()))
            public = json.dumps([first,expanded,b.execute("i","crosscheck_linear_solver",'{"result_id":"original"}')])
            for term in ('"private"','"category"','"flavor"','"qoi_truth"','"order_truth"','reference_q','study_aware'):
                self.assertNotIn(term,public)
            a.log.close()
            b.log.close()

    def test_extra_schemas_and_original_menu_isolation(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b = self.episode(tmp,"original"),self.episode(tmp)
            self.assertFalse(a.execute("a","crosscheck_linear_solver",'{"result_id":"original"}')["ok"])
            self.assertFalse(b.execute("b","run_affine_mms",'{"family":"advection","grid":16,"kernel":"audited","extra":1}')["ok"])
            self.assertEqual(b.environment.status()["spent"],0)
            self.assertTrue(b.execute("c","run_affine_mms",'{"family":"advection","grid":8,"kernel":"audited"}')["ok"])
            a.log.close()
            b.log.close()

    def test_frozen_limits_and_slots(self):
        for values in ({"model":"gpt-5.6-sol"},{"reasoning_effort":"low"},{"scientific_budget":20},
                       {"api_ceiling_usd":"3"},{"menu":"bad"}):
            with self.assertRaises(ValueError):
                replace(agent.MenuConfig(),**values)
        slots = campaign.slots_for(self.cases)
        self.assertEqual(len(slots),12)
        self.assertEqual(len({(s["case_id"],s["menu"]) for s in slots}),12)
        self.assertEqual([s["menu"] for s in slots[:4]],["original","expanded","expanded","original"])
        budget = BatchBudget("2")
        budget.reserve(0,Decimal(".04"),"2")
        with self.assertRaises(ValueError):
            budget.reserve(0,Decimal(".04"),"2")

    def test_full_offline_rehearsal_and_tamper_detection(self):
        with tempfile.TemporaryDirectory() as tmp, patch("budgeted_science.agents.runner.load_api_key",side_effect=AssertionError("credentials")):
            prepared = campaign.prepare(output_root=Path(tmp))
            path = asyncio.run(campaign.run_comparison(prepared,Path(tmp),mode="dry-run"))
            s = campaign.render(path)
            self.assertEqual(s["finalized"],12)
            self.assertEqual(s["menus"]["expanded"]["complete"],6)
            self.assertEqual(s["menus"]["expanded"]["extra_calls"],18)
            self.assertEqual(s["menus"]["original"]["joint_correct"],0)
            self.assertLessEqual(float(s["batch_budget"]["committed_upper_usd"]),2)
            for row in s["rows"]:
                events,torn = read_events(row["run"])
                self.assertFalse(torn)
                self.assertTrue(all(e["output"].get("ok") for e in events if e["kind"] == "tool_result"))
            with patch.object(AlternativeAudit,"call",side_effect=AssertionError("reran tool")):
                self.assertEqual(campaign.render(path),s)
            (path/"results/00.json").write_text("{}",encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"integrity"):
                campaign.render(path)


if __name__ == "__main__":
    unittest.main()

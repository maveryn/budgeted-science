from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from unittest import TestCase
from unittest.mock import patch

from budgeted_science.agents.records import RunLog
from budgeted_science.claim_verification_qoi.budget_sweep import (
    METHODS, aggregate, choose_claims, dispatch, fixed_configuration, render)
from budgeted_science.claim_verification_qoi.environment import Backend, Episode
from budgeted_science.claim_verification_qoi.numerics import config, quote, reference, solve
from budgeted_science.claim_verification_qoi.pilot import protocol, run_episode
from budgeted_science.claim_verification_qoi.policies import _quality
from budgeted_science.claim_verification_qoi.studies import QUANTITIES, make_study


def rows_fixture():
    return [{"case_id":f"{q}-{label}-{i}","physical_study_id":f"physical-{q}-{label}-{i}",
             "cohort":"development","seed":7300+i,"profile":i,"claim_valid":label,
             "claim":{"quantity":q,"tolerance":.01}}
            for q in QUANTITIES for label in (False,True) for i in range(3)]


class SelectionTests(TestCase):
    def test_twelve_balanced_claims_only_from_development(self):
        rows = rows_fixture()
        rows += [{**r,"case_id":r["case_id"]+"fresh","cohort":"fresh","seed":7400} for r in rows]
        selected = choose_claims(rows)
        self.assertEqual(len(selected),12)
        self.assertEqual(Counter((s["claim"]["quantity"],s["claim_valid"]) for s in selected),
                         Counter({(q,y):2 for q in QUANTITIES for y in (False,True)}))
        self.assertTrue(all(s["cohort"]=="development" and s["seed"] in (7300,7301,7302) for s in selected))

    def test_selection_ignores_policy_outcomes_and_severity(self):
        rows = rows_fixture()
        ids = lambda xs:[x["case_id"] for x in xs]
        expected = ids(choose_claims(rows))
        changed = [{**r,"policy_scores":{"adaptive":100000-i},"normalized_error":i/100} for i,r in enumerate(rows)]
        self.assertEqual(expected,ids(choose_claims(list(reversed(changed)))))
        self.assertEqual(expected,ids(choose_claims(rows)))

    def test_selection_does_not_modify_source_rows(self):
        rows = rows_fixture(); saved = deepcopy(rows)
        selected = choose_claims(rows); selected[0]["claim"]["tolerance"] = 999
        self.assertEqual(rows,saved)

    def test_insufficient_label_stratum_fails_without_substitution(self):
        rows = [r for r in rows_fixture() if not (r["claim"]["quantity"]=="cumulative" and r["claim_valid"])]
        with self.assertRaises(ValueError): choose_claims(rows)


class ConfigurationTests(TestCase):
    def test_all_fixed_checks_affordable_and_use_budget(self):
        for budget in (2,4):
            for q in QUANTITIES:
                for method in ("Euler","RK2"):
                    cfg = fixed_configuration(budget,q,method)
                    self.assertLessEqual(quote(cfg)["credits"],budget)
                    self.assertGreaterEqual(quote(cfg)["credits"],budget-.01)
                    self.assertEqual(cfg["method"],method)
                    self.assertAlmostEqual(round(8/cfg["dt"])*cfg["dt"],8)

    def test_proxy_not_worse_than_affordable_standard_grids(self):
        for budget in (2,4):
            for q in QUANTITIES:
                for method in ("Euler","RK2"):
                    chosen = fixed_configuration(budget,q,method)
                    for dt in (.04,.08,.16,.32):
                        for output in (.04,.08,.16,.32,1):
                            candidate = config(method,dt,output)
                            if quote(candidate)["credits"]<=budget:
                                self.assertLessEqual(_quality(chosen,q),_quality(candidate,q)+1e-15)

    def test_invalid_configuration_requests(self):
        for args in ((8,"peak_height","RK2"),(True,"peak_height","RK2"),
                     (2,"unknown","RK2"),(2,"peak_time","DOP853")):
            with self.assertRaises(ValueError): fixed_configuration(*args)

    def test_returned_configuration_cannot_corrupt_cached_selection(self):
        saved = fixed_configuration(2,"peak_time","RK2")
        changed = fixed_configuration(2,"peak_time","RK2"); changed["dt"] = 999
        self.assertEqual(fixed_configuration(2,"peak_time","RK2"),saved)


class EpisodeTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.theta = [1,.08,1.4]
        cls.original = solve(cls.theta,config("Euler",.16,.4))
        cls.ref = reference(cls.theta)

    def study(self):
        return make_study(7300,self.theta,"development",0,self.original,self.ref,"peak_height",.01,0)

    def test_each_policy_completes_within_each_budget(self):
        study = self.study()
        for budget in (2,4):
            for method in METHODS:
                ep = Episode(study,budget)
                result = dispatch(ep.tools.call,method,seed=0)
                self.assertEqual(ep.state,"submitted")
                self.assertLessEqual(ep.spent,budget)
                self.assertIn(ep.submission["verdict"],("ACCEPT","REJECT","ABSTAIN"))
                self.assertEqual(ep.evaluate()["verdict"],result["submission"]["submission"]["verdict"])
                if method.startswith("fixed_"):
                    self.assertEqual(len(ep.ledger),1)
                    self.assertEqual(ep.spent,budget)

    def test_fixed_selection_does_not_depend_on_claim_value(self):
        configurations = []
        for value in (1,10000):
            ep = Episode(self.study(),2)
            def call(name,args=None):
                response = ep.tools.call(name,args)
                if name=="describe": response["claim"]["reported"] = value
                return response
            diagnostics = dispatch(call,"fixed_rk2_budget")
            configurations.append(diagnostics["fixed_configuration"])
        self.assertEqual(configurations[0],configurations[1])

    def test_injected_runner_retains_deadline_and_actual_submission_scoring(self):
        with tempfile.TemporaryDirectory() as folder:
            result = run_episode(self.study(),"fixed_rk2_budget",0,{**protocol(),"budget":2},Backend(),folder,
                                 policy_runner=dispatch)
            self.assertFalse(result["incomplete"])
            self.assertEqual(result["spent"],2)
            self.assertEqual(result["verdict"],result["submission"]["verdict"])
            self.assertTrue((Path(result["path"])/"transcript.md").exists())

    def test_render_is_offline_and_preserves_missing_slot_status(self):
        study = self.study()
        with tempfile.TemporaryDirectory() as folder:
            log = RunLog(folder,"test-sweep")
            log.write_json("manifest.json",{"selected_claims":[{"case_id":study["case_id"],
                "claim":study["claim"],**study["private"]}],"budgets":[2,4],"methods":["fixed_rk2_budget"]})
            run_episode(study,"fixed_rk2_budget",0,{**protocol(),"budget":2},Backend(),log.path/"episodes",policy_runner=dispatch)
            log.close()
            with patch("budgeted_science.claim_verification_qoi.budget_sweep.dispatch",side_effect=AssertionError()), \
                 patch("budgeted_science.claim_verification_qoi.environment.solve",side_effect=AssertionError()):
                summary = render(log.path)
                before = (log.path/"summary.json").read_bytes()
                render(log.path)
            self.assertFalse(summary["completed"])
            self.assertEqual(summary["episodes"],1)
            self.assertEqual(summary["expected_episodes"],2)
            self.assertEqual(len(summary["missing_slots"]),1)
            self.assertEqual((log.path/"summary.json").read_bytes(),before)

    def test_aggregate_keeps_budgets_separate_and_incomplete_in_denominator(self):
        base = {"budget":2,"policy":"random","claim":{"quantity":"peak_height"},"correct":True,
            "claim_valid":True,"covered":True,"false_accept":False,"false_reject":False,"abstained":False,
            "incomplete":False,"spent":1.9,"seconds":1}
        rows = [base,{**base,"budget":4},{**base,"correct":False,"incomplete":True,"spent":None,"seconds":None}]
        results = {(s["budget"],s["scope"]):s for s in aggregate(rows)}
        self.assertEqual(results[(2,"all")]["n"],2)
        self.assertEqual(results[(2,"all")]["correct"],1)
        self.assertEqual(results[(2,"all")]["mean_credits"],1.9)
        self.assertEqual(results[(4,"all")]["n"],1)

    def test_truncated_result_preserved_and_counted_incomplete(self):
        study = self.study()
        with tempfile.TemporaryDirectory() as folder:
            log = RunLog(folder,"partial-sweep")
            log.write_json("manifest.json",{"selected_claims":[{"case_id":study["case_id"],
                "claim":study["claim"],**study["private"]}],"budgets":[2],"methods":["random"]})
            episode = RunLog(log.path/"episodes","partial")
            episode.write_json("manifest.json",{"case_id":study["case_id"],"policy":"random","budget":2})
            episode.event("work_reserved",entry={"run_id":"unfinished","work":100})
            episode.close()
            fragment = '{"incomplete_write":'
            (episode.path/"result.json").write_text(fragment,encoding="utf-8")
            log.close()
            summary = render(log.path)
            self.assertEqual((episode.path/"result.json").read_text(encoding="utf-8"),fragment)
            self.assertEqual(summary["corrupt_result_count"],1)
            self.assertEqual(summary["unknown_spending_count"],1)
            self.assertFalse(summary["completed"])
            self.assertTrue(all(s["correct"]==0 and s["incomplete"]==1 for s in summary["summaries"]))

from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
from unittest import TestCase
from unittest.mock import patch

from budgeted_science.agents.records import RunLog
from budgeted_science.claim_verification_qoi.environment import Backend
from budgeted_science.claim_verification_qoi.numerics import config, reference, solve
from budgeted_science.claim_verification_qoi.pilot import (aggregate, build_catalog, protocol,
    render, render_episode, run_episode, source_hashes, summarize, target)
from budgeted_science.claim_verification_qoi.studies import make_study


class PilotTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.theta = [1,.08,1.4]
        cls.reference = reference(cls.theta)
        cls.original = solve(cls.theta,config("Euler",.16,.4))

    def study(self):
        return make_study(7300,self.theta,"development",0,self.original,self.reference,"peak_height",.05,0)

    def test_frozen_disjoint_seeds_prices_and_no_selection(self):
        p = protocol()
        self.assertEqual(p["cohorts"]["development"],[7300,7301,7302])
        self.assertEqual(p["cohorts"]["fresh"],list(range(7400,7406)))
        self.assertEqual(p["budget"],8)
        self.assertEqual(len(p["original_profiles"]),3)
        self.assertIn("no error/label/policy-based selection",p["selection"])
        self.assertEqual(target(7300),target(7300))
        self.assertNotEqual(target(7300),target(7301))
        p["cohorts"]["fresh"] = []
        self.assertEqual(len(protocol()["cohorts"]["fresh"]),6)

    def test_source_provenance_covers_numerics_policies_and_old_rhs(self):
        hashes = source_hashes()
        for suffix in ("claim_verification_qoi/numerics.py","claim_verification_qoi/policies.py",
                       "claim_verification/numerics.py","agents/records.py"):
            self.assertTrue(any(k.endswith(suffix) for k in hashes))
        self.assertTrue(all(len(v)==64 for v in hashes.values()))

    def test_catalog_keeps_all_successful_profiles_and_matched_claims(self):
        p = protocol(); p["cohorts"]={"development":[7300]}
        with tempfile.TemporaryDirectory() as folder:
            log = RunLog(folder,"test")
            with patch("budgeted_science.claim_verification_qoi.pilot.reference",return_value=self.reference):
                studies,catalog = build_catalog(p,log)
            log.close()
        self.assertEqual(len(studies),18)
        self.assertEqual(len({s["physical_study_id"] for s in studies}),3)
        for physical in {s["physical_study_id"] for s in studies}:
            matched = [s for s in studies if s["physical_study_id"]==physical]
            self.assertEqual(len({s["run_id"] for s in matched}),1)
            self.assertEqual(len({s["case_id"] for s in matched}),6)
        self.assertEqual(catalog["failed_originals"],[])

    def test_unstable_time_omitted_without_replacement(self):
        p = protocol(); p["cohorts"]={"development":[7300]}
        ref = deepcopy(self.reference); ref.update(peak_time_eligible=False,peak_time_reason="competing_maxima")
        with tempfile.TemporaryDirectory() as folder:
            log = RunLog(folder,"test")
            with patch("budgeted_science.claim_verification_qoi.pilot.reference",return_value=ref):
                studies,catalog = build_catalog(p,log)
            log.close()
        self.assertEqual(len(studies),12)
        self.assertEqual(len(catalog["omitted_timing"]),3)
        self.assertTrue(all(s["claim"]["quantity"]!="peak_time" for s in studies))

    def test_saved_episode_and_offline_regeneration_do_not_execute(self):
        study = self.study()
        with tempfile.TemporaryDirectory() as folder:
            result = run_episode(study,"fixed_rk2",0,protocol(),Backend(),folder)
            self.assertFalse(result["incomplete"])
            self.assertEqual(result["spent"],6.01)
            self.assertEqual(result["api_expenditure"],0)
            path = Path(result["path"])
            before = (path/"transcript.md").read_bytes()
            with patch("budgeted_science.claim_verification_qoi.environment.solve",side_effect=AssertionError()), \
                 patch("budgeted_science.claim_verification_qoi.pilot.reference",side_effect=AssertionError()), \
                 patch("budgeted_science.claim_verification_qoi.policies.run_policy",side_effect=AssertionError()):
                render_episode(path)
            self.assertEqual(before,(path/"transcript.md").read_bytes())
            self.assertEqual(result["verdict"],result["submission"]["verdict"])

    def test_policy_failure_is_incomplete_not_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch("budgeted_science.claim_verification_qoi.policies.run_policy",side_effect=RuntimeError("test")):
                result = run_episode(self.study(),"adaptive",0,protocol(),Backend(),folder)
        self.assertTrue(result["incomplete"])
        self.assertFalse(result["correct"])
        self.assertIsNone(result["submission"])

    def test_deadline_after_submission_cannot_count_success(self):
        study = self.study()
        def policy(call,*args,**kwargs):
            return call("submit",{"verdict":"ACCEPT" if study["private"]["claim_valid"] else "REJECT",
                        "diagnosis":"test","evidence_ids":[],"justification":"test"})
        with tempfile.TemporaryDirectory() as folder:
            with patch("budgeted_science.claim_verification_qoi.policies.run_policy",side_effect=policy), \
                 patch("budgeted_science.claim_verification_qoi.pilot.perf_counter",side_effect=[0,0,0,301,301]):
                result = run_episode(study,"adaptive",0,protocol(),Backend(),folder)
        self.assertTrue(result["incomplete"])
        self.assertFalse(result["correct"])
        self.assertIsNotNone(result["attempted_verdict"])

    def test_unknown_costs_are_not_zero_in_means(self):
        row = {"correct":False,"claim_valid":True,"covered":False,"false_accept":False,
               "false_reject":False,"abstained":False,"incomplete":True,"spent":None,"seconds":None}
        result = summarize([row,{**row,"spent":6,"seconds":2}])
        self.assertEqual(result["mean_credits"],6)
        self.assertEqual(result["mean_seconds"],2)
        self.assertEqual(result["known_credit_count"],1)
        self.assertEqual(result["n"],2)

    def test_interrupted_episode_reservation_and_freeze_are_reported(self):
        study = self.study()
        with tempfile.TemporaryDirectory() as folder:
            log = RunLog(folder,"test")
            log.write_json("manifest.json",{"protocol":protocol()})
            log.write_json("catalog.json",{"studies":[{"case_id":study["case_id"],
                "physical_study_id":study["physical_study_id"],"claim":study["claim"],**study["private"]}],
                "failed_originals":[],"omitted_timing":[]})
            ep = RunLog(log.path/"episodes","test")
            ep.write_json("manifest.json",{"case_id":study["case_id"],"policy":"adaptive"})
            ep.event("work_reserved",entry={"run_id":"partial","work":200})
            ep.close()
            log.event("pilot_interrupted",error={"message":"source changed after freeze"})
            log.close()
            summary = render(log.path)
        self.assertEqual(summary["accounting_unknown"],1)
        self.assertFalse(summary["completion"]["completed"])
        self.assertFalse(summary["completion"]["source_freeze_verified_at_completion"])
        self.assertEqual(summary["completion"]["expected_episodes"],5)
        self.assertTrue(all(s["mean_credits"] is None for s in summary["summaries"]))

    def test_aggregate_counts_all_attempts_and_absences(self):
        base = {"correct":True,"claim_valid":True,"covered":True,"false_accept":False,
                "false_reject":False,"abstained":False,"incomplete":False,"spent":6.01,"seconds":1,
                "cohort":"fresh","policy":"fixed_rk2", "claim":{"quantity":"peak_time","tolerance":.04}}
        failed = {**base,"correct":False,"covered":False,"incomplete":True,"spent":0}
        s = summarize([base,failed])
        self.assertEqual((s["n"],s["correct"],s["incomplete"]),(2,1,1))
        catalog = {"studies":[],"failed_originals":[],"omitted_timing":[]}
        summary = aggregate([base,failed],catalog)
        self.assertEqual(summary["episodes"],2)
        self.assertTrue(all(s["n"]==2 for s in summary["summaries"]))

    def test_summary_regeneration_matches_saved_results(self):
        study = self.study()
        with tempfile.TemporaryDirectory() as folder:
            log = RunLog(folder,"pilot-test")
            catalog = {"studies":[{"case_id":study["case_id"],"physical_study_id":study["physical_study_id"],
                        "claim":study["claim"],**study["private"]}],"failed_originals":[],"omitted_timing":[]}
            log.write_json("catalog.json",catalog)
            result = run_episode(study,"fixed_rk2",0,protocol(),Backend(),log.path/"episodes")
            log.close()
            with patch("budgeted_science.claim_verification_qoi.pilot.solve",side_effect=AssertionError()):
                summary = render(log.path)
                before = (log.path/"summary.json").read_bytes()
                render(log.path)
            self.assertEqual(before,(log.path/"summary.json").read_bytes())
            self.assertEqual(summary["episodes"],1)
            self.assertEqual(summary["summaries"][0]["correct"],int(result["correct"]))

    def test_relative_run_path_renders_against_absolute_episode_paths(self):
        study = self.study()
        with tempfile.TemporaryDirectory() as folder:
            log = RunLog(folder,"relative-test")
            log.write_json("catalog.json",{"studies":[{"case_id":study["case_id"],
                "physical_study_id":study["physical_study_id"],"claim":study["claim"],**study["private"]}],
                "failed_originals":[],"omitted_timing":[]})
            run_episode(study,"fixed_rk2",0,protocol(),Backend(),log.path/"episodes")
            log.close()
            previous = Path.cwd()
            try:
                os.chdir(log.path.parent)
                result = render(log.path.name)
            finally:
                os.chdir(previous)
            self.assertEqual(result["episodes"],1)

from copy import deepcopy
import json
from unittest import TestCase
from unittest.mock import Mock, patch

from budgeted_science.claim_verification_qoi.environment import Backend, Episode
from budgeted_science.claim_verification_qoi.numerics import config, qois, reference, solve
from budgeted_science.claim_verification_qoi.studies import artifacts, assess, make_study, report, validate_study


class StudyFixture(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.theta = [1,.08,1.4]
        cls.original = solve(cls.theta,config("Euler",.16,.4,0))
        cls.ref = reference(cls.theta)

    def study(self,quantity="peak_height",tolerance=.05,format_id=0):
        return make_study(7300,self.theta,"development",0,self.original,self.ref,
                          quantity,tolerance,format_id)


class StudyTests(StudyFixture):
    def test_claim_matches_actual_rounded_output(self):
        for q,t in (("peak_height",.01),("peak_time",.04),("cumulative",.05)):
            study = self.study(q,t)
            self.assertEqual(study["claim"]["reported"],float(format(qois(self.original)[q],".10g")))
            self.assertIs(validate_study(study),study)

    def test_three_formats_preserve_all_facts_and_artifact_roles(self):
        for f in range(3):
            study = self.study(format_id=f)
            text = report(study)
            for expected in ("[0,8]","Euler","0.16","0.4","5%",f"{study['claim']['reported']:.10g}"):
                self.assertIn(expected,text)
            self.assertEqual({a["role"] for a in artifacts(study).values()},
                             {"report","solver_log","trajectory","analysis"})

    def test_opaque_ids_are_not_reproducible_from_small_seed(self):
        a,b = self.study(),self.study()
        self.assertNotEqual(a["physical_study_id"],b["physical_study_id"])
        self.assertNotEqual(a["case_id"],b["case_id"])

    def test_same_numerics_can_have_different_truth_at_different_tolerances(self):
        ref = deepcopy(self.ref)
        printed = float(format(qois(self.original)["peak_height"],".10g"))
        ref["qois"]["peak_height"] = printed/1.03
        a = make_study(7300,self.theta,"development",0,self.original,ref,"peak_height",.01,0,"pair")
        b = make_study(7300,self.theta,"development",0,self.original,ref,"peak_height",.05,0,"pair")
        self.assertFalse(a["private"]["claim_valid"])
        self.assertTrue(b["private"]["claim_valid"])
        self.assertEqual(a["run_id"],b["run_id"])
        self.assertNotEqual(a["case_id"],b["case_id"])

    def test_tampered_artifact_or_private_truth_rejected(self):
        study = self.study()
        study["claim"]["reported"] += 1
        with self.assertRaises(ValueError): validate_study(study)
        study = self.study(); study["private"]["claim_valid"] = not study["private"]["claim_valid"]
        with self.assertRaises(ValueError): validate_study(study)

    def test_ineligible_time_is_not_admitted(self):
        ref = deepcopy(self.ref); ref["peak_time_eligible"] = False
        with self.assertRaises(ValueError):
            make_study(7300,self.theta,"development",0,self.original,ref,"peak_time",.04,0)

    def test_absolute_relative_and_boundary_scoring(self):
        self.assertTrue(assess(10.5,10,"relative",.05)["claim_valid"])
        self.assertTrue(assess(2.04,2,"absolute",.04)["claim_valid"])
        self.assertFalse(assess(2.041,2,"absolute",.04)["claim_valid"])
        self.assertFalse(assess(10.50001,10,"relative",.05)["claim_valid"])
        for args in ((float("nan"),1,"relative",.1),(1,0,"relative",.1),(1,1,"absolute",0),(True,1,"relative",.1)):
            with self.assertRaises(ValueError): assess(*args)


class EpisodeTests(StudyFixture):
    def test_exact_purchase_and_free_episode_reuse(self):
        ep = Episode(self.study())
        cfg = config("RK2",.04,.04,0)
        quoted = ep.tools.call("quote_check",cfg)
        self.assertEqual(quoted["charge"],6.01)
        first = ep.tools.call("run_check",cfg,"one")
        self.assertEqual(first["charge"],6.01)
        self.assertEqual(ep.remaining,1.99)
        second = ep.tools.call("run_check",cfg,"two")
        self.assertTrue(second["episode_reuse"])
        self.assertEqual(second["charge"],0)
        self.assertEqual(ep.tools.call("quote_check",cfg)["charge"],0)

    def test_duplicate_id_does_not_repeat_purchase_and_conflict_invalid(self):
        ep = Episode(self.study()); cfg = config()
        first = ep.tools.call("run_check",cfg,"same")
        self.assertEqual(first,ep.tools.call("run_check",cfg,"same"))
        self.assertEqual(len(ep.ledger),1)
        self.assertEqual(ep.tools.call("budget",{},"same")["status"],"invalid")

    def test_invalid_and_unaffordable_do_not_execute(self):
        solver = Mock(side_effect=AssertionError("must not execute"))
        ep = Episode(self.study(),credits=1,backend=Backend(solver))
        self.assertEqual(ep.tools.call("run_check",config())["status"],"unaffordable")
        self.assertEqual(ep.tools.call("run_check",{"method":"reference"})["status"],"invalid")
        self.assertEqual(ep.tools.call("run_check",{"method":"RK2","dt":float("nan")})["status"],"invalid")
        self.assertEqual(ep.spent,0); solver.assert_not_called()

    def test_failed_work_charged_and_cached(self):
        failed = {"status":"failed","config":config(),"times":[],"values":[],
                  "work":2,"credits":.02,"rhs_evaluations":2,"output_samples":0}
        solver = Mock(return_value=failed); backend = Backend(solver)
        a,b = Episode(self.study(),backend=backend),Episode(self.study(),backend=backend)
        self.assertEqual(a.tools.call("run_check",config())["charge"],.02)
        self.assertEqual(a.tools.call("run_check",config())["charge"],0)
        self.assertEqual(b.tools.call("run_check",config())["charge"],.02)
        self.assertEqual(solver.call_count,1)

    def test_warm_backend_still_charges_equal_independent_episodes(self):
        backend = Backend(); study = self.study()
        a,b = Episode(study,backend=backend),Episode(study,backend=backend)
        ra = a.tools.call("run_check",config()); rb = b.tools.call("run_check",config())
        self.assertEqual(ra,rb)
        self.assertEqual(a.remaining,b.remaining)

    def test_public_responses_omit_private_and_internal_fields(self):
        study = self.study(); ep = Episode(study)
        values = [ep.tools.call("describe"),ep.tools.call("list_artifacts"),
                  ep.tools.call("read_run",{"run_id":study["run_id"]}),ep.tools.call("budget")]
        for response in values:
            text = json.dumps(response)
            for key in ('"theta"','"seed"','"reference"','"private"','"internal"','"claim_valid"'):
                self.assertNotIn(key,text)

    def test_read_and_recompute_need_no_solver(self):
        study = self.study(); ep = Episode(study,backend=Backend(Mock(side_effect=AssertionError())))
        for q in ("peak_height","peak_time","cumulative"):
            got = ep.tools.call("recompute_quantity",{"run_id":study["run_id"],"quantity":q})
            self.assertEqual(got["value"],qois(study["run"])[q])
        self.assertEqual(ep.spent,0)

    def test_unknown_evidence_and_abstention(self):
        ep = Episode(self.study())
        args = {"verdict":"ACCEPT","diagnosis":"test","evidence_ids":["unknown"],"justification":"test"}
        self.assertEqual(ep.tools.call("submit",args)["status"],"invalid")
        args.update(verdict="ABSTAIN",evidence_ids=[])
        self.assertEqual(ep.tools.call("submit",args)["status"],"submitted")
        score = ep.evaluate()
        self.assertTrue(score["abstained"]); self.assertFalse(score["correct"])
        self.assertFalse(score["incomplete"])
        self.assertEqual(ep.tools.call("budget")["status"],"closed")

    def test_submission_log_failure_cannot_count_correct(self):
        def log(kind,**kwargs):
            if kind=="tool_result": raise OSError("disk interrupted")
        ep = Episode(self.study(),log=log)
        args = {"verdict":"ACCEPT" if ep.study["private"]["claim_valid"] else "REJECT",
                "diagnosis":"test","evidence_ids":[],"justification":"test"}
        with self.assertRaises(OSError): ep.tools.call("submit",args)
        self.assertTrue(ep.evaluate()["incomplete"])
        self.assertFalse(ep.evaluate()["correct"])
        self.assertFalse(ep.evaluate()["covered"])
        self.assertEqual(ep.evaluate()["attempted_verdict"],args["verdict"])

    def test_reservation_log_failure_stops_before_execution(self):
        solver = Mock(side_effect=AssertionError())
        def log(kind,**kwargs):
            if kind=="work_reserved": raise OSError("disk interrupted")
        ep = Episode(self.study(),backend=Backend(solver),log=log)
        with self.assertRaises(OSError): ep.tools.call("run_check",config())
        solver.assert_not_called(); self.assertEqual(ep.spent,0)
        self.assertTrue(ep.evaluate()["incomplete"])

    def test_uncertain_execution_keeps_reservation_and_aborts(self):
        ep = Episode(self.study(),backend=Backend(Mock(side_effect=KeyboardInterrupt())))
        with self.assertRaises(KeyboardInterrupt): ep.tools.call("run_check",config())
        self.assertEqual(ep.spent,2.01)
        self.assertTrue(ep.evaluate()["incomplete"])

    def test_purchased_response_mutation_cannot_modify_original(self):
        study = self.study(); ep = Episode(study)
        response = ep.tools.call("read_run",{"run_id":study["run_id"]})
        response["values"][0][0]=999
        self.assertEqual(ep.tools.call("read_run",{"run_id":study["run_id"]})["values"][0][0],10)

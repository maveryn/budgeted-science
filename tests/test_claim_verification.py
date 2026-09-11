"""Offline numerical, public-contract, and durable-runner regression checks."""
from copy import deepcopy
from functools import lru_cache
import csv
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from budgeted_science.agents.records import read_events
from budgeted_science.claim_verification.environment import ACTIONS, Episode, summarize
from budgeted_science.claim_verification.numerics import (
    Backend, NumericalFailure, cache_key, configuration, output_grid, peak,
    reference, reported_value, rhs, solve, validate_config)
from budgeted_science.claim_verification.reporting import numeric_quotes, render_episode, render_catalog
from budgeted_science.claim_verification.runner import fixture, run_script, provenance, validate
from budgeted_science.claim_verification.studies import (
    CATEGORIES, FORMATS, commission, configuration_text, make_artifacts, make_study,
    render_report, truth_label, validate_study)
from budgeted_science.resource_planning.environment import _rhs


@lru_cache()
def examples():
    theta = (1., .08, 1.4)
    ref = reference(theta)
    good = make_study(1, theta, "sound", solve(theta, configuration()), ref, 0)
    bad = make_study(1, theta, "consequential_integration",
                     solve(theta, configuration("Euler", dt=.16)), ref, 1)
    return good, bad


@lru_cache()
def catalog():
    return commission()


class NumericalTests(unittest.TestCase):
    def test_rhs_is_existing_equations(self):
        self.assertIs(rhs, _rhs)
        np.testing.assert_allclose(rhs(0, (10, 5), (1, .08, 1.4)), [5, -3.4])

    def test_initial_conditions_and_endpoints(self):
        for method in ("Euler", "DOP853"):
            run = solve((1,.08,1.4), configuration(method, dt=.04))
            self.assertEqual(run["times"][0], 0)
            self.assertEqual(run["times"][-1], 8)
            np.testing.assert_array_equal(run["values"][0], [10,5])
            self.assertTrue(np.all(np.isfinite(run["values"])))
            self.assertTrue(np.all(np.array(run["values"]) >= 0))

    def test_reference_methods_and_searches(self):
        ref = reference((1,.08,1.4))
        self.assertAlmostEqual(ref["q"], 33.8103196939, places=8)
        self.assertLess(ref["max_relative_disagreement"], 1e-7)
        self.assertEqual({c["search_points"] for c in ref["checks"]}, {4097,8193})
        self.assertEqual({c["method"] for c in ref["checks"]}, {"DOP853","Radau"})
        self.assertFalse(ref["certified_exact"])

    def test_public_validate_command(self):
        self.assertTrue(validate()["passed"])

    def test_euler_piecewise_linear_sampling(self):
        config = configuration("Euler", dt=.16, times=[0,.08,.16,8])
        run = solve((1,.08,1.4), config)
        np.testing.assert_allclose(run["values"][1],
                                   np.mean(np.array(run["internal"]["node_values"])[:2], axis=0))

    def test_deterministic_numeric_replay(self):
        a = solve((1,.08,1.4), configuration())
        b = solve((1,.08,1.4), configuration())
        a.pop("seconds"); b.pop("seconds")
        self.assertEqual(a, b)

    def test_sampling_can_miss_peak(self):
        dense = solve((1,.08,1.4), configuration())
        sparse = solve((1,.08,1.4), configuration(times=output_grid(2,.25)))
        self.assertLess(peak(sparse)["q"], peak(dense)["q"])

    def test_output_grids_and_phase(self):
        for spacing in (.0025,.1,.25,.5,1,2,4):
            for phase in (0,.25,.5,.75):
                times = output_grid(spacing, phase)
                self.assertEqual((times[0], times[-1]), (0,8))
                self.assertTrue(all(a < b for a,b in zip(times,times[1:])))

    def test_invalid_configuration(self):
        for config in ({"method":"none"}, {"method":"Euler","dt":.3,"output_times":[0,8]},
                       {"method":"Euler","dt":True,"output_times":[0,8]},
                       {"method":"Euler","dt":.1,"output_times":[0,8,7]}):
            with self.subTest(config=config), self.assertRaises(ValueError):
                validate_config(config)

    def test_negative_numerical_trajectory_rejected(self):
        with self.assertRaises(NumericalFailure):
            solve((1.4,.12,2), configuration("Euler",dt=8))

    def test_cache_complete_configuration(self):
        c = configuration()
        a = cache_key((1,.08,1.4),c)
        self.assertNotEqual(a,cache_key((1.1,.08,1.4),c))
        self.assertNotEqual(a,cache_key((1,.08,1.4),configuration(times=[0,8])))
        self.assertNotEqual(a,cache_key((1,.08,1.4),configuration(rtol=1e-10)))

    def test_peak_includes_endpoints(self):
        run = {"status":"success","times":[0,1,8],"values":[[10,5],[9,4],[8,6]]}
        self.assertEqual(peak(run)["time"],0)
        run["values"][-1][0]=11
        self.assertEqual(peak(run)["time"],8)


class CatalogTests(unittest.TestCase):
    def test_catalog_size_and_development_scope(self):
        c = catalog()
        self.assertTrue(c["complete"])
        self.assertEqual(c["failures"],[])
        self.assertEqual(len(c["studies"]),30)
        self.assertEqual(len(c["systems"]),6)
        self.assertEqual(c["cohort"],"development")
        self.assertEqual(c["seeds"],list(range(7100,7106)))

    def test_full_sweeps_retained(self):
        for system in catalog()["systems"]:
            self.assertEqual(len(system["sweep"]),32)
            self.assertEqual(len(system["selections"]),5)
            self.assertEqual(len(system["reference"]["checks"]),4)

    def test_admission_bands(self):
        for study in catalog()["studies"]:
            p = study["private"]
            if p["category"]=="sound":
                self.assertLess(p["relative_error"],.001)
            elif p["category"].startswith("harmless"):
                self.assertGreaterEqual(p["relative_error"],.005)
                self.assertLess(p["relative_error"],.04)
            else:
                self.assertGreater(p["relative_error"],.06)
            self.assertEqual(p["claim_valid"],p["relative_error"]<=.05)

    def test_format_balance(self):
        for format_name in FORMATS:
            self.assertEqual(sum(s["format"]==format_name for s in catalog()["studies"]),10)
            for category in CATEGORIES:
                self.assertEqual(sum(s["format"]==format_name and s["private"]["category"]==category
                                     for s in catalog()["studies"]),2)

    def test_artifact_consistency_and_precision(self):
        for study in catalog()["studies"]:
            validate_study(study)
            self.assertEqual(study["reported_q"],reported_value(study["run"]))
            self.assertEqual(len(study["artifacts"]),4)
            trajectory=next(a["content"] for a in study["artifacts"].values() if a["role"]=="trajectory")
            values=list(csv.DictReader(io.StringIO(trajectory)))
            self.assertEqual(float(format(max(float(v["x"]) for v in values),".10g")),
                             study["reported_q"])

    def test_all_formats_have_same_facts(self):
        study=examples()[0]
        for index in range(3):
            text=render_report(study,index)
            for fact in (format(study["reported_q"],".10g"),"+/-5%","x(0)=10","y(0)=5",
                         "[0, 8]",configuration_text(study["run"]["config"])):
                self.assertIn(fact,text)

    def test_public_artifacts_no_private_labels(self):
        for study in catalog()["studies"]:
            public=json.dumps(study["artifacts"])
            for forbidden in (*CATEGORIES,"reference_q","claim_valid","theta","private"):
                self.assertNotIn(forbidden,public)
            self.assertNotIn(str(study["private"]["seed"]),study["case_id"])

    def test_altered_report_is_rejected(self):
        study=deepcopy(examples()[0])
        next(iter(study["artifacts"].values()))["content"]+="tampered"
        with self.assertRaises(ValueError):
            validate_study(study)

    def test_absent_category_does_not_change_selection_rule(self):
        good=deepcopy(examples()[0]["run"])
        with patch("budgeted_science.claim_verification.studies.SEEDS",(7100,)), \
             patch("budgeted_science.claim_verification.studies.Backend.get", return_value=(good,False)):
            result=commission()
        self.assertFalse(result["complete"])
        self.assertTrue(result["failures"])
        self.assertEqual(len(result["systems"]),1)


class EpisodeTests(unittest.TestCase):
    def episode(self, **kwargs):
        return Episode(examples()[1],**kwargs)

    def test_free_inspection_pagination(self):
        ep=self.episode()
        inventory=ep.tools.list_artifacts()["artifacts"]
        self.assertEqual(len(inventory),4)
        key=next(a["id"] for a in inventory if a["role"]=="trajectory")
        first=ep.tools.read_artifact(key,limit=2)
        second=ep.tools.read_artifact(key,offset=first["next_offset"],limit=2)
        self.assertNotEqual(first["content"],second["content"])
        self.assertEqual(ep.spent,0)

    def test_invalid_requests_do_not_charge(self):
        ep=self.episode()
        for name,args in [("reference",{}),("refine_integration",{"run_id":"not-purchased"}),
                          ("read_artifact",{"id":"../private/catalog.json"}),
                          ("read_artifact",{"id":next(iter(ep.artifacts)),"limit":True}),
                          ("refine_sampling",{"run_id":ep.study["run_id"],"theta":[1,2,3]})]:
            self.assertEqual(ep.tools.call(name,args)["status"],"invalid")
        self.assertEqual(ep.spent,0)

    def test_unaffordable_check_not_executed(self):
        backend=Backend(solver=lambda *_: self.fail("must not execute"))
        ep=self.episode(credits=2,backend=backend)
        self.assertEqual(ep.tools.refine_integration(ep.study["run_id"])["status"],"unaffordable")
        self.assertEqual(ep.spent,0)

    def test_rejected_requests_retain_arguments_and_results(self):
        events=[]
        ep=self.episode(log=lambda kind, **data: events.append({"kind":kind, **data}))
        requests=[("reference",{}, "unknown"), ("budget",[], "shape"),
                  ("budget",{}, ""), ("budget",{"value":float("nan")}, "nonfinite")]
        for name,args,call_id in requests:
            result=ep.tools.call(name,args,call_id)
            self.assertEqual(result["status"],"invalid")
        self.assertEqual(ep.spent,0)
        self.assertEqual([e["kind"] for e in events],["tool_call","tool_result"]*4)
        self.assertEqual(events[0]["name"],"reference")
        self.assertEqual(events[2]["arguments"],[])
        self.assertIn("nan",events[6]["malformed_request"])
        json.dumps(events,allow_nan=False)

    def test_duplicate_requests_log_exact_returned_results(self):
        events=[]
        ep=self.episode(log=lambda kind, **data: events.append({"kind":kind, **data}))
        args={"run_id":ep.study["run_id"]}
        first=ep.tools.call("refine_sampling",args,"repeat")
        second=ep.tools.call("refine_sampling",args,"repeat")
        results=[e["result"] for e in events if e["kind"]=="tool_result"]
        self.assertEqual(results,[first,second])
        self.assertEqual(first,second)
        self.assertEqual(sum(e["kind"]=="tool_call" for e in events),2)
        self.assertEqual(sum(e["kind"]=="duplicate_call" for e in events),1)
        self.assertEqual(ep.spent,2)

    def test_integration_preserves_output_times(self):
        ep=self.episode()
        original=ep.study["run_id"]
        result=ep.tools.refine_integration(original)
        self.assertEqual(result["charge"],3)
        self.assertEqual(ep.runs[result["run_id"]]["times"],ep.runs[original]["times"])
        self.assertEqual(ep.runs[result["run_id"]]["config"]["rtol"],1e-10)

    def test_sampling_preserves_integration(self):
        ep=self.episode()
        original=ep.study["run_id"]
        result=ep.tools.refine_sampling(original)
        config=ep.runs[result["run_id"]]["config"]
        self.assertEqual(config["method"],"Euler")
        self.assertEqual(config["dt"],.16)
        self.assertEqual(len(config["output_times"]),3201)
        self.assertEqual(result["charge"],2)

    def test_chained_checks_and_zero_credit_submission(self):
        ep=self.episode()
        first=ep.tools.refine_integration(ep.study["run_id"])
        second=ep.tools.refine_sampling(first["run_id"])
        self.assertEqual(ep.spent,5)
        self.assertEqual(ep.tools.recompute_peak(second["run_id"])["status"],"success")
        result=ep.tools.submit("REJECT","fixture",[second["run_id"]],"fixture")
        self.assertEqual(result["status"],"submitted")
        self.assertTrue(ep.evaluate()["correct"])

    def test_no_check_submission_and_abstention(self):
        for verdict in ("ACCEPT","REJECT","ABSTAIN"):
            ep=self.episode()
            ep.tools.submit(verdict,"fixture",[],"fixture")
            self.assertEqual(ep.spent,0)
            self.assertTrue(ep.evaluate()["valid_submission"])
            self.assertEqual(ep.evaluate()["abstained"],verdict=="ABSTAIN")

    def test_repeated_purchase_and_noop_are_free(self):
        ep=self.episode()
        first=ep.tools.refine_integration(ep.study["run_id"])
        again=ep.tools.refine_integration(ep.study["run_id"])
        noop=ep.tools.refine_integration(first["run_id"])
        self.assertEqual(first["run_id"],again["run_id"])
        self.assertEqual(again["charge"],0)
        self.assertEqual(noop["charge"],0)
        self.assertEqual(ep.spent,3)

    def test_duplicate_id_does_not_execute(self):
        ep=self.episode()
        args={"run_id":ep.study["run_id"]}
        a=ep.tools.call("refine_sampling",args,"same")
        b=ep.tools.call("refine_sampling",args,"same")
        self.assertEqual(a,b)
        self.assertEqual(ep.spent,2)
        self.assertEqual(ep.tools.call("refine_integration",args,"same")["status"],"invalid")

    def test_failed_computation_cached_and_charged(self):
        calls=[]
        def fail(*args):
            calls.append(args)
            raise NumericalFailure("test failure",{"completed_steps":1})
        ep=self.episode(backend=Backend(fail))
        first=ep.tools.refine_integration(ep.study["run_id"])
        again=ep.tools.refine_integration(ep.study["run_id"])
        self.assertEqual(first["status"],"failed")
        self.assertEqual(again["charge"],0)
        self.assertEqual(ep.spent,3)
        self.assertEqual(len(calls),1)
        self.assertNotIn("test failure",json.dumps(first))

    def test_warm_cold_and_independent_ledgers(self):
        backend=Backend()
        a=self.episode(backend=backend)
        b=self.episode(backend=backend)
        x=a.tools.refine_sampling(a.study["run_id"])
        y=b.tools.refine_sampling(b.study["run_id"])
        self.assertEqual(x["q"],y["q"])
        self.assertEqual(x["charge"],y["charge"])
        self.assertTrue(y["backend_cache_hit"])
        self.assertEqual(b.remaining,3)

    def test_compact_peak_matches_full_artifact(self):
        ep=self.episode()
        result=ep.tools.refine_integration(ep.study["run_id"])
        self.assertEqual(result["q"],max(v[0] for v in ep.runs[result["run_id"]]["values"]))
        comparison=ep.tools.compare_runs([ep.study["run_id"],result["run_id"]])
        self.assertIn("not certified",comparison["warning"])
        self.assertNotIn("claim_valid",json.dumps(comparison))

    def test_public_responses_do_not_include_truth(self):
        ep=self.episode()
        responses=[ep.tools.budget(),ep.tools.list_artifacts(),
                   ep.tools.refine_sampling(ep.study["run_id"])]
        text=json.dumps(responses)
        for forbidden in ("reference_q","claim_valid","theta","consequential","private"):
            self.assertNotIn(forbidden,text)
        self.assertEqual(set(ACTIONS),set(k for k in dir(ep.tools) if not k.startswith("_"))-{"call"})

    def test_malformed_submissions_and_unavailable_evidence(self):
        ep=self.episode()
        for args in [dict(verdict="maybe",diagnosis="x",evidence_ids=[],justification="x"),
                     dict(verdict="ACCEPT",diagnosis="",evidence_ids=[],justification="x"),
                     dict(verdict="ACCEPT",diagnosis="x",evidence_ids=["hidden"],justification="x"),
                     dict(verdict="ACCEPT",diagnosis="x",evidence_ids=[float("nan")],justification="x")]:
            self.assertEqual(ep.tools.call("submit",args)["status"],"invalid")
        self.assertEqual(ep.state,"active")

    def test_closed_episode_rejects_more_purchases(self):
        ep=self.episode()
        ep.tools.submit("ABSTAIN","fixture",[],"fixture")
        self.assertEqual(ep.tools.refine_sampling(ep.study["run_id"])["status"],"closed")
        self.assertEqual(ep.spent,0)

    def test_log_failure_does_not_continue_unlogged(self):
        def log(kind,**data):
            if kind=="charged": raise OSError("simulated disk failure")
        ep=self.episode(log=log)
        with self.assertRaises(OSError):
            ep.tools.refine_sampling(ep.study["run_id"])
        self.assertEqual(ep.state,"aborted")
        self.assertEqual(ep.spent,0)

    def test_wrong_check_does_not_fix_other_error_family(self):
        for study in catalog()["studies"]:
            category=study["private"]["category"]
            if not category.startswith("consequential"):
                continue
            ep=Episode(study)
            wrong=(ep.tools.refine_sampling if category.endswith("integration")
                   else ep.tools.refine_integration)(study["run_id"])
            error=abs(wrong["q"]-study["private"]["reference_q"])/study["private"]["reference_q"]
            self.assertGreater(error,.05)

    def test_reverse_chaining_and_original_claim_scoring(self):
        ep=self.episode()
        first=ep.tools.refine_sampling(ep.study["run_id"])
        second=ep.tools.refine_integration(first["run_id"])
        self.assertLess(abs(second["q"]-ep.study["private"]["reference_q"]),1e-3)
        ep.tools.submit("ACCEPT","fixture",[],"fixture")
        self.assertFalse(ep.evaluate()["correct"])
        self.assertEqual(ep.evaluate()["reported_q"],ep.study["reported_q"])

    def test_audits_cannot_call_reference(self):
        ep=self.episode()
        with patch("budgeted_science.claim_verification.numerics.reference",side_effect=AssertionError):
            self.assertEqual(ep.tools.refine_integration(ep.study["run_id"])["status"],"success")

    def test_interrupted_computation_retains_charge(self):
        def interrupt(*args):
            raise KeyboardInterrupt()
        ep=self.episode(backend=Backend(interrupt))
        with self.assertRaises(KeyboardInterrupt):
            ep.tools.refine_integration(ep.study["run_id"])
        self.assertEqual(ep.spent,3)
        self.assertEqual(ep.state,"aborted")

    def test_scoring_boundary_and_denominators(self):
        self.assertTrue(truth_label(105,100))
        self.assertTrue(truth_label(95,100))
        self.assertFalse(truth_label(105.00001,100))
        es=[]
        for study,verdict in [(examples()[0],"ACCEPT"),(examples()[1],"ACCEPT"),
                              (examples()[0],"ABSTAIN")]:
            ep=Episode(study)
            ep.tools.submit(verdict,"fixture",[],"fixture")
            es.append(ep.evaluate())
        ep=self.episode(); ep.abort("interrupted"); es.append(ep.evaluate())
        total=summarize(es)
        self.assertEqual(total["accuracy"],.25)
        self.assertEqual(total["coverage"],.5)
        self.assertEqual(total["false_acceptance_rate"],.5)
        self.assertEqual(total["abstentions"],1)
        self.assertEqual(total["incomplete"],1)


class RunnerTests(unittest.TestCase):
    def test_all_fixture_outcomes(self):
        with tempfile.TemporaryDirectory() as root:
            for kind in ("accept","reject","abstain","interrupted"):
                study=examples()[1 if kind=="reject" else 0]
                path=run_script(study,kind=kind,root=root)
                evaluation=json.loads((path/"private/evaluation.json").read_text())
                self.assertEqual(evaluation["incomplete"],kind=="interrupted")
                self.assertEqual(evaluation["spent"],0 if kind=="abstain" else (3 if kind=="interrupted" else 5))
                self.assertIn("not measured agent performance",(path/"report.md").read_text())
                events,_=read_events(path)
                self.assertEqual(events[-1]["api_usd"],0)

    def test_regeneration_has_no_execution_and_preserves_bytes(self):
        with tempfile.TemporaryDirectory() as root:
            path=run_script(examples()[0],root=root)
            before=[(path/n).read_bytes() for n in ("transcript.md","report.md")]
            with patch("budgeted_science.claim_verification.numerics.solve",side_effect=AssertionError), \
                 patch.object(Episode,"dispatch",side_effect=AssertionError):
                render_episode(path)
            self.assertEqual(before,[(path/n).read_bytes() for n in ("transcript.md","report.md")])

    def test_unique_run_directories(self):
        with tempfile.TemporaryDirectory() as root:
            a=run_script(examples()[0],kind="abstain",root=root)
            b=run_script(examples()[0],kind="abstain",root=root)
            self.assertNotEqual(a,b)
            self.assertTrue(a.is_dir())

    def test_response_limit_deadline_and_no_submission(self):
        with tempfile.TemporaryDirectory() as root:
            for overrides in ({"request_limit":0},{"deadline_seconds":0},{"steps":[]}):
                path=run_script(examples()[0],root=root,**overrides)
                result=json.loads((path/"private/evaluation.json").read_text())
                self.assertTrue(result["incomplete"])
                self.assertEqual(result["spent"],0)

    def test_first_submission_ends_script(self):
        study=examples()[0]
        steps=fixture("abstain",study)
        steps.append({"tool":"refine_integration","arguments":{"run_id":study["run_id"]}})
        with tempfile.TemporaryDirectory() as root:
            path=run_script(study,root=root,steps=steps)
            self.assertEqual(json.loads((path/"private/evaluation.json").read_text())["spent"],0)

    def test_torn_tail_and_no_finish_render_incomplete(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)
            (path/"events.jsonl").write_bytes(b'{"sequence":1,"kind":"assistant_message","text":"partial"}\n{"sequence":')
            result=render_episode(path)
            self.assertFalse(result["complete"])
            self.assertTrue(result["torn_tail"])
            self.assertIn("partial",(path/"transcript.md").read_text())

    def test_numeric_quotes_are_limited_not_semantic_judging(self):
        answer={"diagnosis":"run-abc Q=12.5","justification":"run-def Q=99; tolerance 5%"}
        result=numeric_quotes(answer,{"run-abc":12.5,"run-def":10})
        self.assertEqual(len(result["recognized_quotes"]),2)
        self.assertFalse(result["all_recognized_quotes_match"])
        self.assertFalse(result["semantic_grounding_scored"])

    def test_no_optional_sdk_needed(self):
        code="import sys; sys.modules['openai']=None; from budgeted_science.claim_verification.runner import provenance; print(provenance()['api_usd'])"
        result=subprocess.run([sys.executable,"-B","-c",code],capture_output=True,text=True,check=True)
        self.assertEqual(result.stdout.strip(),"0")

    def test_provenance_contains_only_required_versions(self):
        p=provenance()
        self.assertEqual(p["api_calls"],0)
        self.assertNotIn("openai",p["versions"])
        self.assertGreater(len(p["source_hashes"]),5)

    def test_synthetic_secret_redaction(self):
        with tempfile.TemporaryDirectory() as root:
            steps=[{"message":"Authorization Bearer test-secret; sk-synthetic-test-secret"}]
            path=run_script(examples()[0],root=root,steps=steps)
            logs=(path/"events.jsonl").read_text()+(path/"script.json").read_text()
            self.assertNotIn("sk-synthetic-test-secret",logs)
            self.assertNotIn("Bearer test-secret",logs)

    def test_duplicate_script_call_retains_single_charge(self):
        study=examples()[0]
        call={"tool":"refine_sampling","call_id":"same","arguments":{"run_id":study["run_id"]}}
        with tempfile.TemporaryDirectory() as root:
            path=run_script(study,root=root,steps=[call,deepcopy(call)])
            evaluation=json.loads((path/"private/evaluation.json").read_text())
            self.assertEqual(evaluation["spent"],2)
            self.assertTrue(evaluation["incomplete"])

    def test_catalog_render_uses_saved_records(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root); (path/"private").mkdir()
            (path/"private/catalog.json").write_text(json.dumps(catalog()))
            with patch("budgeted_science.claim_verification.numerics.solve",side_effect=AssertionError):
                summary=render_catalog(path)
            self.assertEqual(summary["studies"],30)
            self.assertEqual(summary["valid_claims"],18)
            self.assertEqual(summary["invalid_claims"],12)


if __name__ == "__main__":
    unittest.main()

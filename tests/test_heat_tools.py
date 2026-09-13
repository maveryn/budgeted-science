"""Costed heat contracts and credential-free Luna/Sol campaign rehearsal."""
import asyncio
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict
from decimal import Decimal
from fractions import Fraction
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from budgeted_science.agents import heat_tools as h
from budgeted_science.agents.records import RunLog, read_events
from budgeted_science.heat_workflow import costed as c
from budgeted_science.heat_workflow.experiment import public_specification
from budgeted_science.heat_workflow.numerics import Problem, Config, analysis_source, patch_mean, solve_direct


def study():
    field, info = solve_direct(Problem(), 33)
    return {"private": {"id": "fixture", "truth": {"verdict": "ACCEPT"}, "category": "PRIVATE_MARKER"},
            "public": {"artifacts": {
                "report.md": "Mean temperature 0.3122230645, within 5% of the stated quantity.",
                "intended.json": public_specification(),
                "run_config.json": {"boundaries": asdict(Problem()), "numerical": asdict(Config())},
                "solver_log.json": info, "analysis.py": analysis_source(),
                "analysis_result.json": {"reported_Q": .3122230645},
                "trajectory.json": {"T": field.tolist(), "x": np.linspace(0,1,33).tolist(), "y": np.linspace(0,1,33).tolist()}}}}


@contextmanager
def prepared(root):
    data = study()
    cases = [{**data["private"], "id": f"fixture-{i}"} for i in range(4)]
    with patch.object(h, "load_cpu", return_value=({"cases": cases}, "cpu-hash")), \
         patch.object(h, "bundle", return_value=data["public"]), \
         patch.object(h, "provenance", return_value={"source_manifest_hash": "fixture"}):
        yield h.prepare(root=root)


class NumericalTools(unittest.TestCase):
    def setUp(self):
        self.data = study()
        self.env = c.Audit(self.data["public"])

    def test_four_paid_services_and_five_inspection_control_tools(self):
        self.assertEqual(len(h.tool_definitions()), 9)
        self.assertTrue(set(c.PAID).issubset({t["name"] for t in h.tool_definitions()}))

    def test_exact_tariffs_and_oversized_grid_unaffordable(self):
        self.assertEqual(c.tariff("iterate",33,1024), 1)
        self.assertEqual(c.tariff("remesh",33,256), Fraction(1,4))
        self.assertEqual(c.tariff("solve_matrix",33), 4)
        with patch.object(c, "solve_direct", side_effect=AssertionError("must not run")):
            out = self.env.purchase("solve_matrix", {"n":65, "boundaries":asdict(Problem())})
        self.assertFalse(out["ok"])
        self.assertEqual(self.env.spent, 0)

    def test_iteration_same_boundary_and_new_work_charged(self):
        out = self.env.purchase("iterate", {"run_id":"original", "sweeps":256,"relaxation":.8})
        self.assertEqual(out["charge"], .25)
        original = np.array(self.env.record("original")["T"])
        field = np.array(self.env.record(out["id"])["T"])
        np.testing.assert_array_equal(field[[0,-1],:], original[[0,-1],:])
        np.testing.assert_array_equal(field[:,[0,-1]], original[:,[0,-1]])
        self.env.purchase("iterate", {"run_id":out["id"], "sweeps":256,"relaxation":.8})
        self.assertEqual(self.env.spent, Fraction(1,2))

    def test_remesh_from_zero_preserves_boundary(self):
        args = {"run_id":"original", "n":17, "sweeps":256, "relaxation":.8}
        out = self.env.purchase("remesh", args)
        expected,_ = c.relax(c.initial_field(Problem(),17),256,.8)
        np.testing.assert_allclose(self.env.record(out["id"])["T"],expected)
        self.assertEqual(out["boundaries"],asdict(Problem()))

    def test_matrix_and_perturbation_do_not_change_original(self):
        before = deepcopy(self.env.record("original"))
        out = self.env.purchase("perturb_boundary", {"run_id":"original", "edge":"left", "delta":.5})
        self.assertEqual(out["charge"],4)
        expected,_ = solve_direct(Problem(left=.5),33)
        np.testing.assert_allclose(self.env.record(out["id"])["T"],expected)
        self.assertEqual(before,self.env.record("original"))

    def test_free_reuse_and_independent_episode_charges(self):
        args={"n":33,"boundaries":asdict(Problem())}
        first=self.env.purchase("solve_matrix",args)
        with patch.object(c,"solve_direct",side_effect=AssertionError("reuse must not compute")):
            second=self.env.purchase("solve_matrix",args)
        self.assertEqual(first["id"],second["id"])
        self.assertEqual(second["charge"],0)
        self.assertEqual(c.Audit(self.data["public"]).purchase("solve_matrix",args)["charge"],4)

    def test_failed_execution_charged_and_cached(self):
        args={"n":33,"boundaries":asdict(Problem())}
        with patch.object(c,"solve_direct",side_effect=ArithmeticError("synthetic numerical failure")):
            out=self.env.purchase("solve_matrix",args)
        self.assertEqual(out["info"]["status"],"failed")
        self.assertEqual(self.env.spent,4)
        with patch.object(c,"solve_direct",side_effect=AssertionError("failure is cached")):
            self.assertEqual(self.env.purchase("solve_matrix",args)["charge"],0)

    def test_invalid_actions_not_charged(self):
        for name,args in [("iterate",{"run_id":"original","sweeps":1,"relaxation":.8}),
                          ("iterate",{"run_id":"original","sweeps":256,"relaxation":0}),
                          ("solve_matrix",{"n":33,"boundaries":{}}),
                          ("perturb_boundary",{"run_id":"unknown","edge":"left","delta":1})]:
            with self.assertRaises(ValueError): self.env.purchase(name,args)
        self.assertEqual(self.env.spent,0)

    def test_free_explicit_integration_can_expose_transposition(self):
        intended=self.data["public"]["artifacts"]["intended.json"]
        a=self.env.inspect("integrate_field",h.area_args("original",intended))
        b=self.env.inspect("integrate_field",h.area_args("original",intended,True))
        self.assertGreater(abs(a["area_mean"]-b["area_mean"]),.2)
        self.assertNotIn("verdict",a)
        self.assertEqual(self.env.spent,0)

    def test_record_pages_and_private_artifacts(self):
        page=self.env.inspect("record",{"run_id":"original","start_row":2,"row_count":3})
        self.assertEqual(len(page["T_rows"]),3)
        self.assertNotIn("PRIVATE_MARKER",json.dumps(page))
        with self.assertRaises(ValueError): self.env.inspect("read_artifact",{"name":"../private/study.json"})
        with self.assertRaises(ValueError): self.env.inspect("record",{"run_id":"original","start_row":-1,"row_count":3})


class AdapterTests(unittest.TestCase):
    @contextmanager
    def episode(self):
        with tempfile.TemporaryDirectory() as root:
            log=RunLog(root,"test")
            try: yield h.Episode(h.Config(),h.Instance(study()),log),log
            finally: log.close()

    def test_prompts_same_models_no_private_truth_or_code_tools(self):
        with self.episode() as (episode,log):
            self.assertEqual(h.prompts(h.Config(),episode),h.prompts(h.Config(model="gpt-5.6-sol"),episode))
            text=json.dumps(h.prompts(h.Config(),episode))
            self.assertNotIn("PRIVATE_MARKER",text)
            self.assertNotIn("0.312029",text)
            self.assertTrue(all(t["type"]=="function" for t in h.tool_definitions()))

    def test_duplicate_id_free_and_conflict_rejected(self):
        with self.episode() as (episode,log):
            args=json.dumps({"n":33,"boundaries":asdict(Problem())})
            first=episode.execute("id","solve_matrix",args)
            self.assertEqual(first,episode.execute("id","solve_matrix",args))
            self.assertFalse(episode.execute("id","budget","{}")["ok"])
            self.assertEqual(episode.environment.spent,4)

    def test_nullable_estimate_abstention_and_no_budget_requirement(self):
        with self.episode() as (episode,log):
            out=episode.execute("submit","submit",json.dumps({"verdict":"ABSTAIN","estimate":None,"evidence_ids":[],"explanation":"unknown"}))
            self.assertTrue(out["ok"])
            self.assertTrue(episode.evaluate()["completed"])
            self.assertFalse(episode.evaluate()["correct"])
            self.assertEqual(episode.environment.spent,0)

    def test_actual_verdict_scored_not_optional_estimate(self):
        with self.episode() as (episode,log):
            episode.execute("s","submit",json.dumps({"verdict":"REJECT","estimate":.312029,"evidence_ids":[],"explanation":"fixture"}))
            self.assertFalse(episode.evaluate()["correct"])

    def test_invalid_types_nonfinite_unknown_evidence(self):
        with self.episode() as (episode,log):
            for index,args in enumerate([
                {"verdict":"ACCEPT","estimate":True,"evidence_ids":[],"explanation":"x"},
                {"verdict":"ACCEPT","estimate":float("nan"),"evidence_ids":[],"explanation":"x"},
                {"verdict":"ACCEPT","estimate":None,"evidence_ids":["unbought"],"explanation":"x"}]):
                self.assertFalse(episode.execute(str(index),"submit",json.dumps(args))["ok"])
            self.assertIsNone(episode.submission)

    def test_free_submission_after_full_spending(self):
        with self.episode() as (episode,log):
            for i,left in enumerate((0,.5)):
                self.assertTrue(episode.execute(str(i),"solve_matrix",json.dumps({"n":33,"boundaries":asdict(Problem(left=left))}))["ok"])
            self.assertEqual(episode.environment.spent,8)
            self.assertTrue(episode.execute("s","submit",json.dumps({"verdict":"ACCEPT","estimate":None,"evidence_ids":[],"explanation":"fixture"}))["ok"])

    def test_cpu_comparisons_use_metered_same_interface(self):
        with tempfile.TemporaryDirectory() as root:
            result=h.cpu_policy(study(),"independent_reconstruction",root)
            self.assertTrue(result["correct"])
            self.assertAlmostEqual(result["scientific_status"]["spent"],float(Fraction(4*(17**2+33**2),33**2)))
            self.assertEqual(result["scientific_status"]["paid_calls"],2)

    def test_full_offline_campaign_and_regeneration(self):
        with tempfile.TemporaryDirectory() as root, prepared(root) as frozen:
            path=asyncio.run(h.campaign(frozen,"dry-run",root=root))
            summary=h.read_json(path/"summary.json")
            self.assertEqual(len(summary["rows"]),8)
            self.assertTrue(all(v["completed"]==4 for v in summary["models"].values()))
            for row in summary["rows"]:
                self.assertEqual(row["evaluation"]["scientific_status"]["spent"],.25)
                episode=path/row["path"]
                before=(episode/"transcript.md").read_bytes()
                with patch.object(c,"solve_direct",side_effect=AssertionError("offline render")):
                    h.regenerate(episode)
                self.assertEqual(before,(episode/"transcript.md").read_bytes())
                requests=list((episode/"api").glob("*-request.json"))
                self.assertGreater(len(requests),0)
                self.assertNotIn("PRIVATE_MARKER", "".join(p.read_text() for p in requests))
            before=(path/"summary.json").read_bytes()
            h.render_campaign(path)
            self.assertEqual(before,(path/"summary.json").read_bytes())

    def test_frozen_mutation_rejected(self):
        with tempfile.TemporaryDirectory() as root, prepared(root) as frozen:
            manifest=h.load_prepared(frozen)
            with patch.object(h,"tool_definitions",return_value=[]):
                with self.assertRaises(ValueError): h.load_prepared(frozen)
            self.assertEqual(len(manifest["slots"]),8)

    def test_live_one_shot_marker_prevents_duplicate_launch(self):
        with tempfile.TemporaryDirectory() as root, prepared(root) as frozen:
            (frozen/"live-attempt.json").touch()
            with patch.object(h,"run_episode",side_effect=AssertionError("must not launch")):
                with self.assertRaises(FileExistsError): asyncio.run(h.campaign(frozen,"live",root=root))

    def test_missing_usage_keeps_reservation_and_halts_batch(self):
        class Broken(h.Fake):
            async def stream(self,body,metadata):
                async for event in super().stream(body,metadata):
                    event["response"]["usage"]=None
                    yield event
        with tempfile.TemporaryDirectory() as root, prepared(root) as frozen:
            path=asyncio.run(h.campaign(frozen,"dry-run",root=root,gateway_factory=Broken))
            summary=h.read_json(path/"summary.json")
            self.assertEqual(len(summary["rows"]),1)
            self.assertGreater(Decimal(summary["rows"][0]["api_budget"]["committed_upper_usd"]),0)
            self.assertTrue(summary["rows"][0]["api_budget"]["unsettled_requests"])

    def test_budget_model_config_fixed(self):
        for kwargs in ({"model":"other"},{"api_ceiling_usd":"3.01"},{"reasoning_effort":"low"},{"scientific_budget":9}):
            with self.assertRaises(ValueError): h.Config(**kwargs)


if __name__ == "__main__":
    unittest.main()

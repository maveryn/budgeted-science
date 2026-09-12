"""Offline scientific contracts and matched-menu campaign regression tests."""
import asyncio
from copy import deepcopy
from dataclasses import replace
from functools import lru_cache
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from budgeted_science.claim_verification.alternatives import AlternativeEpisode, EXTRA_COSTS
from budgeted_science.claim_verification.environment import Episode
from budgeted_science.claim_verification.numerics import Backend, configuration, output_grid, reference, solve
from budgeted_science.claim_verification.studies import CATEGORIES, SEEDS, make_study
from budgeted_science.agents import verification_alternatives as agent
from budgeted_science.agents import verification_alternatives_catalog as campaign
from budgeted_science.agents.records import RunLog, digest
from budgeted_science.agents.runner import run_episode


@lru_cache()
def fixtures():
    theta = (1., .08, 1.4)
    ref = reference(theta)
    configs = [configuration(), configuration("Euler", dt=.02), configuration("Euler", dt=.16),
               configuration(times=output_grid(.5)), configuration(times=output_grid(2.))]
    runs = [solve(theta, c) for c in configs]
    return [make_study(seed, theta, category, runs[j], ref, (i+j)%3)
            for i, seed in enumerate(SEEDS) for j, category in enumerate(CATEGORIES)]


def write_fixture_catalog(path):
    studies = deepcopy(fixtures())
    catalog = {"complete": True, "studies": studies}
    log = RunLog(path, "fixture-catalog")
    log.write_json("private/catalog.json", catalog)
    log.write_json("catalog_integrity.json", {"catalog_digest": digest(catalog),
        "case_digests": {s["case_id"]: digest(s) for s in studies}})
    log.close()
    return log.path


class NumericalAlternativeTests(unittest.TestCase):
    def study(self, index=2):
        return deepcopy(fixtures()[index])

    def test_original_defaults_and_actions_unchanged(self):
        study = self.study()
        old, new = Episode(study), AlternativeEpisode(study)
        for name in ("refine_integration", "refine_sampling"):
            args = {"run_id": study["run_id"]}
            self.assertEqual(old.tools.call(name, args), new.tools.call(name, args))
        self.assertEqual(old.spent, 5)
        self.assertEqual(new.spent, 5)
        self.assertEqual(old.tools.call("tighten_integration", args)["status"], "invalid")

    def test_tightening_only_changes_integration(self):
        for index in (0, 2):
            study = self.study(index)
            episode = AlternativeEpisode(study)
            result = episode.tools.call("tighten_integration", {"run_id": study["run_id"]})
            run = episode.runs[result["run_id"]]
            old = study["run"]["config"]
            self.assertEqual(run["times"], study["run"]["times"])
            self.assertEqual(result["charge"], 1)
            if old["method"] == "Euler":
                self.assertEqual(run["config"]["dt"], old["dt"]/2)
            else:
                self.assertEqual(run["config"]["rtol"], old["rtol"]/10)
                self.assertEqual(run["config"]["atol"], old["atol"]/10)

    def test_bisection_preserves_integration_and_keeps_old_nodes(self):
        study = self.study(4)
        episode = AlternativeEpisode(study)
        result = episode.tools.call("bisect_output", {"run_id": study["run_id"]})
        run = episode.runs[result["run_id"]]
        self.assertEqual(len(run["times"]), 2*len(study["run"]["times"])-1)
        self.assertEqual(run["times"][::2], study["run"]["times"])
        np.testing.assert_array_equal(np.asarray(run["values"])[::2], study["run"]["values"])
        for key, value in study["run"]["config"].items():
            if key != "output_times":
                self.assertEqual(run["config"][key], value)

    def test_radau_preserves_output_and_matches_direct_computation(self):
        study = self.study(4)
        episode = AlternativeEpisode(study)
        result = episode.tools.call("crosscheck_integrator", {"run_id": study["run_id"]})
        run = episode.runs[result["run_id"]]
        self.assertEqual(run["times"], study["run"]["times"])
        self.assertEqual(run["config"]["method"], "Radau")
        self.assertEqual(result["charge"], 3)
        expected = solve(study["private"]["theta"], run["config"])
        np.testing.assert_array_equal(run["values"], expected["values"])

    def test_invalid_unaffordable_duplicate_and_cross_episode_cache(self):
        study = self.study()
        backend = Backend()
        episode = AlternativeEpisode(study, backend=backend)
        self.assertEqual(episode.tools.call("bisect_output", {"run_id":"unknown"})["status"], "invalid")
        self.assertEqual(episode.spent, 0)
        args = {"run_id":study["run_id"]}
        first = episode.tools.call("crosscheck_integrator", args, "a")
        self.assertEqual(episode.tools.call("crosscheck_integrator", args, "a"), first)
        self.assertEqual(episode.tools.call("crosscheck_integrator", args, "b")["charge"], 0)
        other = AlternativeEpisode(study, backend=backend)
        warm = other.tools.call("crosscheck_integrator", args)
        self.assertTrue(warm["backend_cache_hit"])
        self.assertEqual(warm["charge"], 3)
        denied = episode.tools.call("refine_integration", args)
        self.assertEqual(denied["status"], "unaffordable")
        self.assertEqual(episode.spent, 3)

    def test_failed_computation_stays_charged_and_cached(self):
        def failing(*args):
            raise RuntimeError("synthetic failure")
        study = self.study()
        episode = AlternativeEpisode(study, backend=Backend(failing))
        args = {"run_id":study["run_id"]}
        first = episode.tools.call("bisect_output", args)
        self.assertEqual(first["status"], "failed")
        self.assertEqual(episode.spent, 1)
        self.assertEqual(episode.tools.call("bisect_output", args)["charge"], 0)

    def test_radau_sampling_chain_is_valid_alternative_route(self):
        study = self.study(2)
        episode = AlternativeEpisode(study)
        a = episode.tools.call("crosscheck_integrator", {"run_id":study["run_id"]})
        b = episode.tools.call("refine_sampling", {"run_id":a["run_id"]})
        self.assertEqual(b["status"], "success")
        self.assertEqual(episode.spent, 5)
        self.assertLess(abs(b["q"]-study["private"]["reference_q"])/study["private"]["reference_q"], 1e-5)

    def test_selection_is_five_systems_independent_of_outcomes(self):
        studies = deepcopy(fixtures())
        first = campaign.select_cases(studies)
        for s in studies:
            s["private"]["claim_valid"] = not s["private"]["claim_valid"]
            s["private"]["relative_error"] = 99
        second = campaign.select_cases(list(reversed(studies)))
        self.assertEqual([s["case_id"] for s in first], [s["case_id"] for s in second])
        self.assertEqual(len({s["private"]["seed"] for s in first}), 5)


class MatchedMenuTests(unittest.TestCase):
    def create_episode(self, root, menu):
        log = RunLog(root, "fixture")
        study = deepcopy(fixtures()[0])
        instance = agent.AlternativesInstance(study, comparison={"case_id":study["case_id"],
                     "evaluation":{"verdict":"ACCEPT","correct":True,"spent":5}})
        return agent.AlternativesEpisode(agent.AlternativesConfig(menu=menu), instance, log)

    def test_prompts_identical_and_original_tool_schemas_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = self.create_episode(tmp,"original"), self.create_episode(tmp,"expanded")
            try:
                self.assertEqual(agent.prompts(a.config,a), agent.prompts(b.config,b))
                original = agent.AlternativesAdapter.tool_definitions(a.config)
                expanded = agent.AlternativesAdapter.tool_definitions(b.config)
                self.assertEqual(original, [t for t in expanded if t["name"] not in EXTRA_COSTS])
                public = json.dumps([agent.prompts(b.config,b), expanded])
                for value in ('"private"', '"theta"', '"reference_q"', '"claim_valid"', 'distractor', 'harmless'):
                    self.assertNotIn(value, public)
            finally:
                a.log.close(); b.log.close()

    def test_adapter_extra_tool_validation_and_dedup(self):
        with tempfile.TemporaryDirectory() as tmp:
            ep = self.create_episode(tmp,"expanded")
            try:
                args = json.dumps({"run_id":ep.instance.study["run_id"]})
                a = ep.execute("a","tighten_integration",args)
                self.assertTrue(a["ok"])
                self.assertEqual(ep.execute("a","tighten_integration",args),a)
                self.assertFalse(ep.execute("b","bisect_output",'{"run_id":1}')["ok"])
                self.assertEqual(ep.environment.spent,1)
            finally:
                ep.log.close()

    def test_original_menu_cannot_call_extras(self):
        with tempfile.TemporaryDirectory() as tmp:
            ep = self.create_episode(tmp,"original")
            try:
                args = json.dumps({"run_id":ep.instance.study["run_id"]})
                self.assertFalse(ep.execute("a","bisect_output",args)["ok"])
                self.assertEqual(ep.environment.spent,0)
            finally:
                ep.log.close()

    def test_frozen_config_and_resume_disabled(self):
        for values in ({"menu":"other"},{"model":"gpt-5.6-sol"},{"api_ceiling_usd":"3"},
                       {"reasoning_effort":"low"},{"scientific_budget":8}):
            with self.assertRaises(ValueError):
                replace(agent.AlternativesConfig(),**values)
        with self.assertRaises(ValueError):
            agent.AlternativesEpisode.restore()

    def test_cpu_preserves_paired_verdict_and_no_api(self):
        with tempfile.TemporaryDirectory() as tmp, patch("budgeted_science.agents.runner.load_api_key", side_effect=AssertionError("key")):
            study = deepcopy(fixtures()[2])
            rows = [campaign.cpu_episode(study,tmp,menu) for menu in ("original","expanded")]
            self.assertEqual(rows[0]["submission"],rows[1]["submission"])
            for r in rows:
                self.assertTrue(r["evaluation"]["correct"])
                self.assertEqual(r["evaluation"]["spent"],5)
                self.assertEqual(r["api_usd"],0)

    def test_offline_whole_matched_campaign_and_integrity(self):
        with tempfile.TemporaryDirectory() as tmp, patch("budgeted_science.agents.runner.load_api_key", side_effect=AssertionError("key")):
            catalog = write_fixture_catalog(tmp)
            prepared = campaign.prepare(catalog,tmp)
            studies,_,_ = campaign.load_prepared(prepared)
            self.assertEqual(len(studies),5)
            path = asyncio.run(campaign.run_comparison(prepared,tmp,mode="dry-run"))
            result = campaign.render(path)
            self.assertEqual(result["attempted_finished"],10)
            self.assertEqual(result["menus"]["original"]["attempts"],5)
            self.assertEqual(result["menus"]["expanded"]["attempts"],5)
            self.assertLess(float(result["batch_budget"]["committed_upper_usd"]),2)
            self.assertEqual(result["batch_budget"]["pending_slots"],{})
            with patch.object(Episode,"dispatch",side_effect=AssertionError("tool on replay")):
                campaign.render(path)
            before=(path/"report.md").read_bytes()
            campaign.render(path)
            self.assertEqual(before,(path/"report.md").read_bytes())
            with (path/"results/00.json").open("a",encoding="utf-8") as stream:
                stream.write(" ")
            with self.assertRaisesRegex(ValueError,"integrity"):
                campaign.render(path)


if __name__ == "__main__":
    unittest.main()

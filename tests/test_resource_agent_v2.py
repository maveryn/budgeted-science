"""Offline v2 integration checks: no real credentials or API calls."""

import asyncio
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from budgeted_science.agents.records import RunLog
from budgeted_science.agents.resource import (
    ResourceAdapter, ResourceEpisode, ResourceInstance, ResourceRunConfig,
    prompts, run_comparisons, tool_definitions)
from budgeted_science.agents.resource_fake import ResourceScriptedGateway
from budgeted_science.agents.resume import prepare_resume
from budgeted_science.agents.runner import run_episode
from budgeted_science.resource_planning.config import harder_config
from budgeted_science.resource_planning.policies import fit_evidence
from budgeted_science.resource_planning.emulator import GPSettings

REPO = Path(__file__).resolve().parents[1]
MID = [1.0, .08, 1.4]


class V2Tools(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.log = RunLog(self.tmp.name, "test")
        self.config = ResourceRunConfig(environment_version="v2", api_ceiling_usd="3.00",
                                        require_full_budget=True)
        self.instance = ResourceInstance.first_evaluation("v2")
        self.episode = ResourceEpisode(self.config, self.instance, self.log)

    def tearDown(self):
        self.log.close()
        self.tmp.cleanup()

    def call(self, name, args=None, call_id=None):
        return self.episode.execute(call_id or f"call-{len(self.episode.executed)}",
                                    name, json.dumps(args or {}))

    def test_selected_frozen_instance_and_configuration(self):
        self.assertEqual(self.instance.target_seed, 6000)
        self.assertEqual(self.instance.noise_seed, 60000)
        bounds = np.array(harder_config().bounds)
        np.testing.assert_array_equal(self.instance.theta,
            np.random.default_rng(6000).uniform(bounds[:, 0], bounds[:, 1]))
        self.assertEqual(self.episode.tools.public_config, harder_config().public())
        self.assertEqual(self.episode.budget_status()["spent"], 0)
        with self.assertRaises(ValueError):
            ResourceRunConfig(environment_version="v3")

    def test_prompt_noise_tolerance_full_budget_and_no_privileged_input(self):
        text = json.dumps(prompts(self.config, self.episode))
        for required in ("5 percent", "0.05*", "0.10 for x", "0.05 for y", "SAME noisy reading",
                         "all 40 scientific credits", "[0.6, 1.4]", "[0.8, 2.0]"):
            self.assertIn(required, text)
        for forbidden in ("noiseless", "60000", "target_seed", "noise_seed", "reference_artifact",
                          "10 percent", "0.9*", "0.01*x", *map(str, self.instance.theta)):
            self.assertNotIn(forbidden, text)
        self.assertEqual(len(tool_definitions(self.config)), 8)
        self.assertIn("noisy scalar", tool_definitions(self.config)[2]["description"])
        self.assertIn("noiseless scalar", tool_definitions()[2]["description"])

    def test_noisy_measurement_cache_dedup_and_grid(self):
        first = self.call("measure_target", {"variable": "x", "time": 4}, "measurement")
        again = self.call("measure_target", {"variable": "x", "time": 4}, "measurement")
        repeat = self.call("measure_target", {"variable": "x", "time": 4})
        self.assertEqual(first["result"]["noise_std"], .1)
        self.assertEqual(first["result"]["value"], repeat["result"]["value"])
        self.assertTrue(again["replayed_call"])
        self.assertEqual(repeat["budget_after"]["spent"], 12)
        invalid = self.call("measure_target", {"variable": "x", "time": 4.1})
        self.assertFalse(invalid["ok"])
        self.assertEqual(invalid["budget_after"]["spent"], 12)

    def test_noisy_fitter_matches_unchanged_baseline_backend(self):
        self.assertFalse(self.call("fit_purchased")["ok"])
        self.call("simulate_low", {"theta": MID})
        self.call("simulate_high", {"theta": [1.1, .09, 1.3]})
        evidence = self.episode.tools.evidence()
        with patch("budgeted_science.resource_planning.environment._solve_high", side_effect=AssertionError("unpaid solver")), \
             patch("budgeted_science.resource_planning.environment._solve_low", side_effect=AssertionError("unpaid solver")):
            fitted = self.call("fit_purchased")
            expected = fit_evidence(evidence, harder_config().public(), 0, GPSettings(), None)
        np.testing.assert_allclose(fitted["result"]["posterior_mean"], expected.estimate(), rtol=0, atol=1e-12)
        self.assertEqual(fitted["budget_after"]["spent"], 9)
        self.assertTrue(self.call("fit_purchased")["result"]["cache_hit"])

    def test_noise_stream_checkpoint_and_config_mismatch(self):
        self.call("simulate_low", {"theta": MID})
        saved = json.loads(json.dumps(self.episode.checkpoint()))
        with patch("budgeted_science.resource_planning.environment._solve_high", side_effect=AssertionError("rerun")), \
             patch("budgeted_science.resource_planning.environment._solve_low", side_effect=AssertionError("rerun")):
            restored = ResourceEpisode.restore(self.config, self.instance, self.log, None, saved)
            self.assertEqual(restored.tools.get_status(), self.episode.tools.get_status())
            self.assertEqual(restored.tools.measure_target("y", 5), self.episode.tools.measure_target("y", 5))
            with self.assertRaises(ValueError):
                ResourceEpisode.restore(self.config, replace(self.instance, noise_seed=60001), self.log, None, saved)
            with self.assertRaises(ValueError):
                ResourceEpisode.restore(ResourceRunConfig(), self.instance, self.log, None, saved)

    def test_full_budget_and_actual_submission_scoring(self):
        self.assertFalse(self.call("submit", {"theta_hat": MID})["ok"])
        # Independent scoring fixture permits early submission, without changing the live requirement.
        other_log = RunLog(self.tmp.name, "scoring")
        try:
            episode = ResourceEpisode(replace(self.config, require_full_budget=False), self.instance, other_log)
            result = episode.execute("submission", "submit", json.dumps({"theta_hat": MID}))
            self.assertTrue(result["ok"])
            expected = np.max(np.abs(np.array(MID) - self.instance.theta) / (.05 * np.array(self.instance.theta)))
            self.assertAlmostEqual(episode.evaluate()["parameter_error"], expected)
        finally:
            other_log.close()

    def test_three_baselines_use_identical_noisy_evidence_and_independent_budgets(self):
        comparisons = run_comparisons(self.config, self.instance, self.log)
        self.assertEqual(set(comparisons), {"random", "adaptive", "local"})
        for policy, result in comparisons.items():
            self.assertEqual(result["termination_reason"], "submitted", policy)
            self.assertEqual(result["scientific_status"]["spent"], 40)
            self.assertEqual(result["evaluation"]["theta_true"], list(self.instance.theta))
            observations = result["scientific_status"]["observations"]
            for initial in self.episode.initial_observations:
                match = next(r for r in observations if (r["variable"], r["time"]) == (initial["variable"], initial["time"]))
                self.assertEqual(match["value"], initial["value"])
        self.assertEqual(self.episode.budget_status()["spent"], 0)


class V2Runs(unittest.TestCase):
    def test_complete_full_budget_offline_run_and_regeneration(self):
        with tempfile.TemporaryDirectory() as temp, \
             patch.object(ResourceAdapter, "run_comparisons", return_value={}), \
             patch("budgeted_science.agents.runner.load_api_key", side_effect=AssertionError("credential read")):
            config = ResourceRunConfig(environment_version="v2", api_ceiling_usd="3.00", require_full_budget=True)
            path, reason = asyncio.run(run_episode(REPO, temp, mode="dry-run", config=config,
                instance=ResourceInstance.first_evaluation("v2"), adapter=ResourceAdapter()))
            self.assertEqual(reason, "submitted")
            data = json.loads((path / "evaluation.json").read_text())
            self.assertEqual(data["evaluation"]["spent"], 40)
            self.assertEqual(data["model_responses"], 10)
            before = {p: (path / p).read_bytes() for p in ("events.jsonl", "report.md", "transcript.md", "evaluation.json")}
            with patch("budgeted_science.resource_planning.environment._solve_high", side_effect=AssertionError("rerun")):
                ResourceAdapter.regenerate(path)
            for p, content in before.items():
                self.assertEqual(content, (path / p).read_bytes())
            self.assertIn("0.05 |target_i|", (path / "report.md").read_text())
            self.assertIn("full-budget comparison", (path / "report.md").read_text())

    def test_interrupted_v2_run_prepares_noisy_resume_with_unknown_reservation(self):
        class Interrupted(ResourceScriptedGateway):
            async def stream(self, body, metadata):
                if len(self.requests) == 2:
                    yield {"type": "response.output_text.delta", "delta": "partial v2"}
                    raise ConnectionError("offline interrupted stream")
                async for event in super().stream(body, metadata):
                    yield event
        with tempfile.TemporaryDirectory() as temp, \
             patch.object(ResourceAdapter, "run_comparisons", return_value={}), \
             patch("budgeted_science.agents.runner.load_api_key", side_effect=AssertionError("credential read")):
            config = ResourceRunConfig(environment_version="v2", api_ceiling_usd="3.00")
            path, reason = asyncio.run(run_episode(REPO, temp, mode="dry-run", config=config,
                instance=ResourceInstance.first_evaluation("v2"), adapter=ResourceAdapter(), gateway=Interrupted()))
            self.assertEqual(reason, "request_or_runner_error")
            resume = prepare_resume(path, mode="dry-run", require_full_budget=True)
            self.assertEqual(resume["config"].environment_version, "v2")
            self.assertEqual(resume["instance"].noise_seed, 60000)
            self.assertEqual(resume["saved"]["environment"]["config"], harder_config().public())
            self.assertGreater(float(resume["money"].status()["uncertain_reserved_usd"]), 0)
            self.assertIn("partial v2", (path / "transcript.md").read_text())


if __name__ == "__main__":
    unittest.main()

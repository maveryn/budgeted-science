"""Twelve-credit follow-up; numerical services and fake model only."""
import asyncio
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from budgeted_science.agents import multi_claim_audit as a
from budgeted_science.multi_claim_audit import core as c


class TwelveCreditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.study = c.build_study()

    def test_exact_configs_and_prior_defaults(self):
        for model in ("gpt-5.6-luna", "gpt-5.6-sol"):
            cfg = a.Config(model=model, scientific_budget=12)
            self.assertEqual((cfg.reasoning_effort, cfg.api_ceiling_usd), ("high", "1.00"))
        self.assertEqual(a.Config().scientific_budget, 32)
        for value in (12.0, True, 11, 13):
            with self.assertRaises(ValueError):
                a.Config(scientific_budget=value)

    def test_high_plus_four_low_and_free_reuse(self):
        env = c.Audit(self.study, budget=12)
        self.assertEqual(env.dispatch("simulate_high", {"theta": list(c.REPORT_THETA)})["charge"], 8)
        for v in (1.01, 1.02, 1.03, 1.04):
            self.assertEqual(env.dispatch("simulate_low", {"theta": [v, .08, 1.4]})["charge"], 1)
        self.assertEqual(env.status()["remaining"], 0)
        self.assertEqual(env.dispatch("simulate_low", {"theta": [1.05, .08, 1.4]})["status"], "unaffordable")
        self.assertEqual(env.dispatch("simulate_high", {"theta": list(c.REPORT_THETA)})["charge"], 0)
        self.assertEqual(env.dispatch("measure_target", {"variable": "x", "time": 4})["status"], "unaffordable")

    def test_one_measurement_exhausts_budget_without_changing_noise(self):
        twelve, twenty = c.Audit(self.study, budget=12), c.Audit(self.study, budget=20)
        first = twelve.dispatch("measure_target", {"variable": "x", "time": 4})
        matched = twenty.dispatch("measure_target", {"variable": "x", "time": 4})
        self.assertEqual(first["value"], matched["value"])
        self.assertEqual(first["noise_std"], matched["noise_std"])
        self.assertEqual((first["charge"], twelve.status()["remaining"]), (12,0))
        self.assertEqual(twelve.dispatch("simulate_low", {"theta": [1.01,.08,1.4]})["status"], "unaffordable")
        self.assertEqual(twelve.dispatch("measure_target", {"variable": "x", "time": 4})["charge"], 0)

    def test_same_fixed_control_four_correct_two_abstentions(self):
        with tempfile.TemporaryDirectory() as root:
            study = deepcopy(self.study)
            study["public"]["environment"]["budget"] = 12.0
            result = a.run_cpu(study, Path(root), a.Config(scientific_budget=12))
        self.assertEqual((result["correct"], result["wrong"], result["abstained"]), (4,0,2))
        self.assertEqual(result["scientific_status"]["spent"], 8)
        self.assertEqual(result["scientific_status"]["remaining"], 4)
        self.assertEqual(result["submission"]["verdicts"]["C5"], "ABSTAIN")
        self.assertEqual(result["submission"]["verdicts"]["C6"], "ABSTAIN")

    def test_matched_frozen_episodes_and_offline_rehearsals(self):
        with tempfile.TemporaryDirectory() as root, patch.object(a, "build_study", return_value=deepcopy(self.study)), \
             patch("budgeted_science.agents.runner.load_api_key", side_effect=AssertionError("no API key")):
            prompts = []
            for model in ("gpt-5.6-luna", "gpt-5.6-sol"):
                prepared = a.prepare(root, a.Config(model=model, scientific_budget=12))
                payload, manifest = a.load_prepared(prepared)
                self.assertEqual(manifest["configuration"]["scientific_budget"], 12)
                self.assertEqual(payload["study"]["public"]["claims"], self.study["public"]["claims"])
                prompts.append(a.read_json(prepared/"prompts.json"))
                path = asyncio.run(a.run(prepared, "dry-run", root))
                result = a.read_json(path/"evaluation.json")
                self.assertEqual(result["termination_reason"], "submitted")
                self.assertEqual(result["evaluation"]["scientific_status"]["spent"], 8)
                self.assertEqual(result["fixed_policy"]["correct"], 4)
                body = a.read_json(path/"api/generation-001-request.json")
                self.assertEqual(body["model"], model)
                before = (path/"report.md").read_bytes()
                a.regenerate(path)
                self.assertEqual(before, (path/"report.md").read_bytes())
            self.assertEqual(prompts[0], prompts[1])
            self.assertIn("within 12 shared scientific credits", prompts[0][1]["content"])


if __name__ == "__main__":
    unittest.main()

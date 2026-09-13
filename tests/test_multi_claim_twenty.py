"""Twenty-credit Luna/Sol extension; fake transport only."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from budgeted_science.agents import multi_claim_audit as a
from budgeted_science.agents.records import RunLog, digest
from budgeted_science.multi_claim_audit import core as c


class TwentyCreditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.study = c.build_study()

    def test_default_32_and_exact_twenty_configs(self):
        self.assertEqual(a.Config().scientific_budget, 32)
        for model in ("gpt-5.6-luna", "gpt-5.6-sol"):
            config = a.Config(model=model, scientific_budget=20)
            self.assertEqual(config.api_ceiling_usd, "1.00")
            self.assertEqual(config.reasoning_effort, "high")
        for budget in (True, 20.0, 19, 40):
            with self.assertRaises(ValueError):
                a.Config(scientific_budget=budget)
        with self.assertRaises(ValueError):
            a.Config(model="gpt-5.6-terra", scientific_budget=20)

    def test_same_claims_observations_and_single_budget_change(self):
        env32, env20 = c.Audit(self.study), c.Audit(self.study, budget=20)
        public20 = deepcopy(env20.public)
        public20["environment"]["budget"] = 32
        self.assertEqual(public20, env32.public)
        self.assertEqual(env20.evidence()["observations"], [
            {**r, "remaining": 20} for r in env32.evidence()["observations"]])
        for env in (env32, env20):
            env.dispatch("simulate_high", {"theta": list(c.REPORT_THETA)})
            env.dispatch("measure_target", {"variable": "x", "time": 4})
        self.assertEqual(env20.status()["spent"], 20)
        self.assertEqual(env20.status()["remaining"], 0)
        self.assertEqual(env32.status()["remaining"], 12)
        self.assertEqual(env20.dispatch("measure_target", {"variable": "y", "time": 6})["status"], "unaffordable")

    def test_fixed_control_five_correct_one_abstention(self):
        with tempfile.TemporaryDirectory() as root:
            study = deepcopy(self.study)
            study["public"]["environment"]["budget"] = 20
            result = a.run_cpu(study, Path(root), a.Config(scientific_budget=20))
        self.assertEqual((result["correct"], result["wrong"], result["abstained"]), (5,0,1))
        self.assertEqual(result["scientific_status"]["spent"], 20)
        self.assertEqual(result["submission"]["verdicts"]["C6"], "ABSTAIN")
        self.assertEqual(len(result["scientific_status"]["ledger"]), 2)

    def test_matched_prompts_across_models(self):
        with tempfile.TemporaryDirectory() as root:
            messages = []
            for model in ("gpt-5.6-luna", "gpt-5.6-sol"):
                log = RunLog(root, "test")
                try:
                    config = a.Config(model=model, scientific_budget=20)
                    episode = a.Episode(config, a.Instance(self.study), log)
                    messages.append(a.prompts(config, episode))
                    self.assertEqual(episode.environment.status()["remaining"], 20)
                finally:
                    log.close()
        self.assertEqual(messages[0], messages[1])
        self.assertIn("within 20 shared scientific credits", messages[0][1]["content"])
        self.assertNotIn("within 32 shared", messages[0][1]["content"])

    def test_prepare_dry_run_both_models_and_frozen_budget(self):
        with tempfile.TemporaryDirectory() as root, patch.object(a, "build_study", return_value=deepcopy(self.study)), \
             patch("budgeted_science.agents.runner.load_api_key", side_effect=AssertionError("no credentials")):
            frozen_prompts = []
            for model in ("gpt-5.6-luna", "gpt-5.6-sol"):
                prepared = a.prepare(root, a.Config(model=model, scientific_budget=20))
                frozen_prompts.append(a.read_json(prepared/"prompts.json"))
                path = asyncio.run(a.run(prepared, "dry-run", root))
                result = a.read_json(path/"evaluation.json")
                self.assertEqual(result["termination_reason"], "submitted")
                self.assertEqual(result["evaluation"]["scientific_status"]["spent"], 20)
                self.assertEqual(result["fixed_policy"]["correct"], 5)
                body = a.read_json(path/"api/generation-001-request.json")
                self.assertEqual(body["model"], model)
                self.assertEqual(body["reasoning"]["effort"], "high")
                before = (path/"report.md").read_bytes()
                a.regenerate(path)
                self.assertEqual(before, (path/"report.md").read_bytes())
            self.assertEqual(frozen_prompts[0], frozen_prompts[1])

    def test_historical_prompt_and_claims_preserved(self):
        # Stored original artifacts are optional on a fresh clone.
        original = a.ROOT/"demos/multi_claim_audit/runs/20260913T012059Z-live-e173e9aa7b"
        if not original.exists():
            self.skipTest("historical local run not present")
        self.assertEqual(digest(self.study), digest(a.read_json(original/"private/study.json")))
        with tempfile.TemporaryDirectory() as root:
            log = RunLog(root, "test")
            try:
                episode = a.Episode(a.Config(), a.Instance(self.study), log)
                self.assertEqual(a.prompts(a.Config(), episode), a.read_json(original/"prompts.json"))
            finally:
                log.close()


if __name__ == "__main__":
    unittest.main()

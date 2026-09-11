"""Offline checks for the opt-in joint-parameter agent episode."""

import asyncio
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from budgeted_science.agents.config import PrivateInstance, RunConfig
from budgeted_science.agents.planning import PlanningEpisode, prompts, run_fixed_policy, tool_definitions
from budgeted_science.agents.records import RunLog, read_events
from budgeted_science.agents.reporting import regenerate
from budgeted_science.agents.runner import run_episode
from budgeted_science.agents.spending import ApiBudget, ApiLimit
from budgeted_science.burgers.reference import ReferenceOracle
from budgeted_science.burgers.scoring import score_planning


REPO = Path(__file__).resolve().parents[1]


class TwoParameterAgentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.config = RunConfig(task_variant="viscosity_amplitude", max_output_tokens=32768)
        self.instance = PrivateInstance(target_amplitude=1.1)
        self.log = RunLog(Path(self.temp.name), "dry-run")
        self.addCleanup(self.log.close)
        self.episode = PlanningEpisode(self.config, self.instance, self.log)

    def call(self, name, **args):
        return self.episode.execute(f"test-{len(self.episode.executed)}", name, json.dumps(args))

    def test_schemas_and_public_prompt_omit_private_parameters(self):
        joint = {t["name"]: t for t in tool_definitions(self.config)}
        original = {t["name"]: t for t in tool_definitions()}
        self.assertEqual(set(joint), set(original))
        self.assertIn("initial_amplitude", joint["simulate"]["parameters"]["required"])
        self.assertNotIn("initial_amplitude", original["simulate"]["parameters"]["properties"])
        self.assertNotIn("initial_amplitude", joint["observe"]["parameters"]["properties"])
        text = json.dumps(prompts(self.config))
        self.assertIn("A*sin(x)", text)
        self.assertIn("1.5*A*sin(x)", text)
        self.assertIn("32768", text)
        self.assertNotIn("0.23", text)
        self.assertNotIn("1.1", text)
        self.assertNotIn("seed", text)

    def test_invalid_amplitude_and_missing_amplitude_are_uncharged(self):
        before = self.episode.ledger.status()
        for value in (.79, 1.21, True):
            result = self.call("simulate", viscosity=.2, initial_amplitude=value,
                               resolution=32, protocol="calibration")
            self.assertFalse(result["ok"])
        result = self.call("simulate", viscosity=.2, resolution=32, protocol="calibration")
        self.assertFalse(result["ok"])
        self.assertEqual(before, self.episode.ledger.status())

    def test_joint_fit_logs_every_prediction_and_uses_actual_forecast(self):
        records = [self.call("observe", sensor_id=i, replicates=1)["result"][0] for i in range(3)]
        fit = self.call("fit", record_ids=[r["record_id"] for r in records],
                        resolution=64, max_evaluations=12)["result"]
        self.assertEqual(fit["evaluations"], 12)
        self.assertEqual(fit["status"], "evaluation_limit")
        self.assertIn("initial_amplitude", fit)
        prediction = self.call("simulate", viscosity=fit["viscosity"],
                               initial_amplitude=fit["initial_amplitude"],
                               resolution=64, protocol="forecast")["result"]
        before = self.episode.ledger.status()
        full = self.call("simulation_record", result_id=prediction["result_id"])["result"]
        self.assertEqual(before, self.episode.ledger.status())
        self.assertEqual(full["initial_amplitude"], fit["initial_amplitude"])
        self.assertEqual(full["initial_amplitude"], prediction["initial_amplitude"])
        self.call("submit", profile=prediction["forecast_profile"])
        result = self.episode.evaluate()
        self.assertEqual(result["score"], score_planning(prediction["forecast_profile"], .23,
                                                       target_amplitude=1.1))
        self.assertLessEqual(result["scientific_budget"]["total_spent"], 20)
        events, _ = read_events(self.log.path)
        calls = [e for e in events if e["kind"] == "simulation_finished"]
        self.assertEqual(len(calls), 13)
        self.assertTrue(all(e["parent_call"] is not None for e in calls))

    def test_observation_deduplication_and_paired_baseline(self):
        args = json.dumps({"sensor_id": 0, "replicates": 1})
        record = self.episode.execute("same", "observe", args)
        spent = self.episode.ledger.status()
        replay = self.episode.execute("same", "observe", args)
        self.assertEqual(record["result"], replay["result"])
        self.assertEqual(spent, self.episode.ledger.status())
        baseline = run_fixed_policy(self.config, self.instance, self.log)
        self.assertEqual(spent, self.episode.ledger.status())
        self.assertAlmostEqual(baseline["score"]["normalized_profile_rmse"], .01812008957558564, places=8)
        self.assertEqual(baseline["fit"]["status"], "evaluation_limit")
        artifact = self.log.path / "observations/fixed_policy/record-000001.json"
        self.assertEqual(json.loads(artifact.read_text())["values"], list(record["result"][0]["values"]))

    def test_reference_amplitude_and_task_mismatch(self):
        expected = ReferenceOracle(.23, initial_amplitude=1.1).forecast_profile()
        np.testing.assert_array_equal(self.episode.evaluate()["reference_profile"], expected)
        with self.assertRaises(ValueError):
            PlanningEpisode(RunConfig(), self.instance, self.log)
        with self.assertRaises(ValueError):
            PrivateInstance(target_amplitude=1.3)
        self.assertEqual(RunConfig().max_output_tokens, 8192)
        with self.assertRaises(ValueError):
            RunConfig(task_variant="unknown")

    def test_larger_response_reservation_keeps_two_dollar_ceiling(self):
        ledger = ApiBudget("2")
        self.assertEqual(ledger.reserve("one", 1000, 32768), Decimal("0.66036"))
        ledger.reserve("two", 1000, 32768)
        ledger.reserve("three", 1000, 32768)
        with self.assertRaises(ApiLimit):
            ledger.reserve("four", 1000, 32768)

    def test_joint_dry_run_and_offline_regeneration(self):
        with patch("budgeted_science.agents.runner.load_api_key", side_effect=AssertionError("key read")):
            path, reason = asyncio.run(run_episode(REPO, Path(self.temp.name), mode="dry-run", config=self.config))
        self.assertEqual(reason, "submitted")
        manifest = json.loads((path / "manifest.json").read_text())
        self.assertEqual(manifest["public_configuration"]["max_output_tokens"], 32768)
        self.assertEqual(manifest["PRIVATE_harness_instance_not_agent_input"]["target_amplitude"], 1.1)
        evaluation = json.loads((path / "evaluation.json").read_text())
        self.assertIsNotNone(evaluation["evaluation"]["score"])
        request = json.loads((path / "api/generation-001-request.json").read_text())
        self.assertEqual(request["max_output_tokens"], 32768)
        self.assertEqual(request["reasoning"]["effort"], "high")
        before = (path / "events.jsonl").read_bytes()
        regenerate(path)
        self.assertEqual(before, (path / "events.jsonl").read_bytes())


if __name__ == "__main__":
    unittest.main()

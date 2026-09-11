"""CPU trial artifact and incomplete-outcome checks; never uses an API."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


_path = Path(__file__).resolve().parents[1] / "src" / "two_parameter_pilot.py"
_spec = importlib.util.spec_from_file_location("two_parameter_pilot", _path)
pilot = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pilot)


class TestTwoParameterPilot(unittest.TestCase):
    def test_reproducible_trial_artifacts_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "trial"
            result = pilot.run_trial(output)
            self.assertEqual(len(result["policies"]), 4)
            for policy in result["policies"]:
                self.assertEqual(policy["status"], "submitted")
                self.assertLessEqual(policy["credits_spent"], 20)
                detail = json.loads((output / policy["artifact"]).read_text(encoding="utf-8"))
                self.assertEqual(len(detail["submitted_profile"]), 16)
                calls = [e for e in detail["trace"] if e["action"] == "simulate"]
                self.assertEqual(len(calls), detail["fit"]["evaluations"] + 1)
                charged = sum(e["result"]["charged_credits"] for e in calls)
                self.assertAlmostEqual(charged, detail["budget"]["spent"]["compute"])
                self.assertEqual(policy["score"], detail["private_evaluation"]["score"])
            self.assertTrue((output / "report.md").is_file())
            diagnostics = json.loads((output / "diagnostics.json").read_text(encoding="utf-8"))
            self.assertTrue(diagnostics["passed"])
            with self.assertRaises(FileExistsError):
                pilot.run_trial(output)

    def test_insufficient_observation_budget_is_recorded_without_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "trial"
            result = pilot.run_trial(output, budget=3)
            for policy in result["policies"]:
                self.assertEqual(policy["status"], "incomplete")
                self.assertIsNone(policy["score"])
                self.assertLessEqual(policy["credits_spent"], 3)
            three = json.loads((output / "three_sensors_coarse_fit.json").read_text(encoding="utf-8"))
            self.assertEqual(three["termination_reason"], "acquisition_budget_exhausted")
            self.assertEqual(three["budget"]["spent"]["observation"], 2)
            self.assertEqual(three["fit"]["status"], "not_started")


if __name__ == "__main__":
    unittest.main()

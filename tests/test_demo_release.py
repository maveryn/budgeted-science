"""Portable results checks: no local run archives, credentials, or API calls."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from budgeted_science import demo_release as demo


class ReleaseTests(unittest.TestCase):
    def test_recorded_metrics(self):
        cases, results, _ = demo.load_bundle()
        self.assertEqual(len(cases["planning"]), 5)
        self.assertEqual(len(cases["verification"]), 6)
        groups = demo.summarize(results)
        self.assertEqual([g["successes"] for g in groups], [3, 3, 2, 0])
        self.assertEqual([g["correct"] for g in groups], [15, 14, 16, 10])
        self.assertEqual([round(100*g["mean_max_error"], 2) for g in groups], [18.09, 5.33, 19.43, 25.76])
        self.assertEqual([round(100*g["median_max_error"], 2) for g in groups], [3.69, 3.03, 20.92, 17.66])
        self.assertEqual([g["wrong"] for g in groups], [3, 4, 2, 6])
        self.assertEqual([g["abstained"] for g in groups], [0, 0, 0, 2])
        self.assertEqual(results["verification_luna"]["attempts"], 7)

    def test_truth_balance_and_scoring(self):
        _, results, _ = demo.load_bundle()
        self.assertEqual(demo.truth_counts(results), {
            "target_integral": {"ACCEPT": 2, "REJECT": 4},
            "target_late_recovery": {"ACCEPT": 4, "REJECT": 2},
            "target_parameter_accuracy": {"ACCEPT": 3, "REJECT": 3}})
        for row in results["planning"]:
            self.assertEqual(row["success"], max(row["relative_errors"]) <= .05)
            self.assertEqual(row["scientific_credits"], 32)
        for row in results["verification"]:
            self.assertEqual(row["correct"]+row["wrong"]+row["abstained"], 3)
            self.assertLessEqual(row["scientific_credits"], 32)
            self.assertEqual(sum(c["verdict"] == c["truth"] for c in row["claims"]), row["correct"])

    def test_portable_bundle_and_tamper_detection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for folder in ("examples/predator_prey", "results/predator_prey"):
                shutil.copytree(demo.ROOT / folder, root / folder)
            demo.load_bundle(root)
            with (root / "results/predator_prey/results.json").open("a") as stream:
                stream.write(" ")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                demo.load_bundle(root)

    def test_offline_results_command(self):
        with patch("socket.socket.connect", side_effect=AssertionError("network forbidden")), \
             patch("sys.argv", ["demo", "results"]), redirect_stdout(io.StringIO()) as out:
            self.assertEqual(demo.main(), 0)
        self.assertIn("15/18", out.getvalue())
        self.assertIn("18.09%", out.getvalue())

    def test_interfaces_and_private_separation(self):
        cases, _, _ = demo.load_bundle()
        prompts = json.loads((demo.ROOT / "results/predator_prey/prompts.json").read_text(encoding="utf-8"))
        self.assertEqual(len(prompts), 33)
        for record in prompts:
            messages = record["messages"]
            self.assertTrue(all(m["role"] in ("developer", "system", "user") for m in messages))
            text = "\n".join(m["content"] for m in messages)
            # The public scoring formula legitimately names theta_true_i.
            self.assertNotIn('"theta_true":', text)
            self.assertNotIn("noise_seed", text)
        for case in cases["verification"]:
            self.assertNotIn("truth", case["study"]["public"])
            self.assertIn("truth", case["study"]["private"])

    def test_cpu_without_historical_archives(self):
        from budgeted_science.resource_planning import adaptive_design_pilot as planning
        from budgeted_science.paired_claim_audit import adaptive_target_three_pilot as verification
        cases, results, provenance = demo.load_bundle()
        small = {**cases, "planning": cases["planning"][:1], "verification": cases["verification"][:1]}
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(demo, "load_bundle", return_value=(small, results, provenance)), \
             patch.object(planning, "read_comparisons", side_effect=AssertionError("no old archives")), \
             patch.object(verification, "read_inputs", side_effect=AssertionError("no old archives")), \
             patch("socket.socket.connect", side_effect=AssertionError("no network")), \
             redirect_stdout(io.StringIO()):
            self.assertEqual(demo.cpu(output=Path(directory)), 0)


if __name__ == "__main__":
    unittest.main()

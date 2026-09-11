"""The verifier must decide from public tool results, not private labels."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from budgeted_science.agents.records import read_events
from budgeted_science.claim_verification.fixed_baseline import fixed_two_check, run_episode
from budgeted_science.claim_verification.numerics import Backend
from budgeted_science.claim_verification.reporting import render_episode
from test_claim_verification import examples


class FixedBaselineTests(unittest.TestCase):
    def fake_tools(self, reported, refined, failed=False):
        calls = []
        def call(name, args):
            calls.append((name, args))
            if name == "list_artifacts":
                return {"artifacts": [{"id": "a", "role": "analysis", "run_id": "run-original"},
                                      {"id": "r", "role": "report", "run_id": "run-original"}]}
            if name == "read_artifact":
                return {"content": f"Result: {reported}\n" if args["id"] == "a" else "Accuracy +/-5%"}
            if name == "refine_integration":
                return {"status": "failed" if failed else "success", "run_id": "run-integrated"}
            if name == "refine_sampling":
                self.assertEqual(args["run_id"], "run-integrated")
                return {"status": "success", "q": refined, "run_id": "run-combined"}
            if name == "submit":
                return {"status": "submitted"}
            self.fail("unexpected action")
        return call, calls

    def test_verdict_depends_on_public_values(self):
        for q, expected in [(100, "ACCEPT"), (105, "ACCEPT"), (95, "ACCEPT"),
                            (105.01, "REJECT"), (94.99, "REJECT")]:
            call, calls = self.fake_tools(q, 100)
            result = fixed_two_check(call)
            self.assertEqual(calls[-1][1]["verdict"], expected)
            self.assertAlmostEqual(result["discrepancy"], abs(q - 100) / 100)

    def test_only_declared_public_actions_are_used(self):
        call, calls = self.fake_tools(110, 100)
        fixed_two_check(call)
        self.assertEqual([name for name, _ in calls],
                         ["list_artifacts", "read_artifact", "read_artifact",
                          "refine_integration", "refine_sampling", "submit"])

    def test_failed_check_abstains(self):
        call, calls = self.fake_tools(100, 100, failed=True)
        self.assertTrue(fixed_two_check(call)["check_failed"])
        self.assertEqual(calls[-1][1]["verdict"], "ABSTAIN")
        self.assertNotIn("refine_sampling", [name for name, _ in calls])

    def test_nonfinite_claim_is_not_accepted(self):
        call, calls = self.fake_tools("nan", 100)
        with self.assertRaises(ValueError):
            fixed_two_check(call)
        self.assertNotIn("submit", [name for name, _ in calls])

    def test_real_checks_are_charged_and_reference_is_unavailable(self):
        good, _ = examples()
        with tempfile.TemporaryDirectory() as root, \
             patch("budgeted_science.claim_verification.numerics.reference",
                   side_effect=AssertionError("private reference unavailable")):
            result = run_episode(good, root)
            self.assertEqual(result["evaluation"]["spent"], 5)
            self.assertEqual(result["evaluation"]["verdict"], "ACCEPT")
            events, _ = read_events(Path(result["episode_path"]))
            self.assertEqual(sum(e["kind"] == "charged" for e in events), 2)
            self.assertTrue(events[-1]["numeric_quotes"]["all_recognized_quotes_match"])

    def test_executed_failure_keeps_charge(self):
        good, _ = examples()
        def fail(*args):
            raise RuntimeError("synthetic solver failure")
        with tempfile.TemporaryDirectory() as root:
            result = run_episode(good, root, backend=Backend(fail))
            self.assertEqual(result["evaluation"]["spent"], 3)
            self.assertTrue(result["evaluation"]["abstained"])

    def test_offline_render_is_identical_and_correctly_labelled(self):
        good, _ = examples()
        with tempfile.TemporaryDirectory() as root:
            result = run_episode(good, root)
            path = Path(result["episode_path"])
            before = (path / "transcript.md").read_bytes()
            with patch("budgeted_science.claim_verification.numerics.solve", side_effect=AssertionError):
                render_episode(path)
            self.assertEqual(before, (path / "transcript.md").read_bytes())
            self.assertIn(b"Fixed two-check baseline", before)
            manifest = json.loads((path / "manifest.json").read_text())
            self.assertFalse(manifest["scripted"])
            self.assertEqual(manifest["api_usd"], 0)

    def test_deadline_is_incomplete_not_fabricated(self):
        good, _ = examples()
        ticks = iter([0, 301, 302])
        with tempfile.TemporaryDirectory() as root:
            result = run_episode(good, root, clock=lambda: next(ticks))
            self.assertTrue(result["evaluation"]["incomplete"])
            self.assertEqual(result["evaluation"]["spent"], 0)


if __name__ == "__main__":
    unittest.main()

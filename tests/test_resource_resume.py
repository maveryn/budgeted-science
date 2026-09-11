"""Resume is tested entirely offline; no real key or paid request is used."""

import asyncio
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from budgeted_science.agents.records import RunLog, read_events
from budgeted_science.agents.resource import ResourceAdapter, ResourceEpisode, ResourceInstance, ResourceRunConfig
from budgeted_science.agents.resource_fake import ResourceScriptedGateway
from budgeted_science.agents.resume import prepare_resume
from budgeted_science.agents.runner import run_episode
from budgeted_science.agents.spending import ApiBudget, AccountingUnavailable
from budgeted_science.resource_planning.checkpoint import export_episode, restore_episode
from budgeted_science.resource_planning.environment import Episode

REPO = Path(__file__).resolve().parents[1]
MID = [1.0, .08, 1.4]


class StateTests(unittest.TestCase):
    def test_low_high_target_and_ledger_round_trip_without_solver(self):
        original = Episode([1.03, .085, 1.3])
        original.tools.simulate_low(MID)
        original.tools.simulate_high([1.05, .09, 1.2])
        original.tools.measure_target("x", 3)
        saved = json.loads(json.dumps(export_episode(original)))
        with patch("budgeted_science.resource_planning.environment._solve_low", side_effect=AssertionError("solver replay")), \
             patch("budgeted_science.resource_planning.environment._solve_high", side_effect=AssertionError("reference replay")):
            restored = restore_episode(saved)
            self.assertEqual(restored.tools.get_status(), original.tools.get_status())
            self.assertEqual(restored.tools.compare_cached_candidates(), original.tools.compare_cached_candidates())
            self.assertEqual(restored.tools.simulate_low(MID)["charge"], 0)
            self.assertEqual(restored.tools.simulate_high([1.05, .09, 1.2])["charge"], 0)
            self.assertEqual(restored.tools.measure_target("x", 3)["charge"], 0)
            # A new paid observation uses restored dense coefficients, not a solve.
            value = restored.tools.measure_target("x", 5)
            expected = original.tools.measure_target("x", 5)
            self.assertEqual(value, expected)
            self.assertEqual(value["charge"], 12)
            self.assertEqual(value["status"], "success")

    def test_failed_purchase_restores_as_failed_cache(self):
        original = Episode(MID)
        with patch("budgeted_science.resource_planning.environment._solve_low", side_effect=RuntimeError("failed")):
            original.tools.simulate_low(MID)
        restored = restore_episode(export_episode(original))
        with patch("budgeted_science.resource_planning.environment._solve_low", side_effect=AssertionError("repeated failed work")):
            result = restored.tools.simulate_low(MID)
        self.assertEqual(result["charge"], 0)
        self.assertEqual(result["status"], "failed")

    def test_corrupted_state_and_pending_charge_rejected(self):
        episode = Episode(MID)
        episode.tools.simulate_low(MID)
        base = export_episode(episode)
        bad = []
        state = deepcopy(base); state["ledger"][0]["status"] = "pending"; bad.append(state)
        state = deepcopy(base); state["ledger"][0]["remaining"] = 40; bad.append(state)
        state = deepcopy(base); state["cache"][0]["baseline_values"][0][0] += 1; bad.append(state)
        state = deepcopy(base); state["version"] = 999; bad.append(state)
        for state in bad:
            with self.subTest(state=state["version"]), self.assertRaises(ValueError):
                restore_episode(state)

    def test_known_and_uncertain_api_charges_survive(self):
        ledger = ApiBudget()
        ledger.reserve("a", 1000, 32768)
        ledger.settle("a", {"input_tokens": 1000, "output_tokens": 300})
        ledger.reserve("b", 2000, 32768)
        restored = ApiBudget.restore(ledger.status(), {"b": {"input_tokens": 2000, "max_output_tokens": 32768}})
        self.assertEqual(restored.status(), ledger.status())
        self.assertGreater(restored.reserved, Decimal(".65"))
        with self.assertRaises(AccountingUnavailable):
            ApiBudget.restore(ledger.status(), {})

    def test_fitting_cache_and_call_deduplication_survive(self):
        with tempfile.TemporaryDirectory() as temp:
            log = RunLog(temp, "test")
            config, instance = ResourceRunConfig(), ResourceInstance.first_evaluation()
            episode = ResourceEpisode(config, instance, log)
            episode.execute("low", "simulate_low", json.dumps({"theta": MID}))
            original_fit = episode.execute("fit", "fit_purchased", "{}")
            state = episode.checkpoint()
            child = RunLog(temp, "test")
            restored = ResourceEpisode.restore(config, instance, child, None, state)
            self.assertEqual(restored.execute("low", "simulate_low", json.dumps({"theta": MID}))["budget_after"]["spent"], 1)
            with patch("budgeted_science.agents.resource.Calibration", side_effect=AssertionError("fit recomputed")):
                fitted = restored.execute("fit-new", "fit_purchased", "{}")
            self.assertTrue(fitted["result"]["cache_hit"])
            self.assertEqual(fitted["result"]["posterior_mean"], original_fit["result"]["posterior_mean"])
            log.close(); child.close()

    def test_full_budget_gate_changes_no_default_scoring(self):
        with tempfile.TemporaryDirectory() as temp:
            log = RunLog(temp, "test")
            episode = ResourceEpisode(ResourceRunConfig(require_full_budget=True), ResourceInstance.first_evaluation(), log)
            self.assertFalse(episode.execute("early", "submit", json.dumps({"theta_hat": MID}))["ok"])
            for i, theta1 in enumerate((.8, .9, 1., 1.1, 1.2)):
                episode.execute(f"h{i}", "simulate_high", json.dumps({"theta": [theta1, .08, 1.4]}))
            result = episode.execute("final", "submit", json.dumps({"theta_hat": MID}))
            self.assertTrue(result["ok"])
            self.assertEqual(episode.evaluate()["spent"], 40)
            log.close()


class Interrupted(ResourceScriptedGateway):
    async def stream(self, body, metadata):
        if self.requests:
            self.requests.append(deepcopy(body))
            yield {"type": "response.output_text.delta", "delta": "unfinished server attempt"}
            raise ConnectionError("synthetic overloaded provider")
        async for event in super().stream(body, metadata):
            yield event


class Continuation(ResourceScriptedGateway):
    async def stream(self, body, metadata):
        async for event in super().stream(body, metadata):
            if event["type"] == "response.completed":
                event["response"]["output"] = [{"type": "function_call", "call_id": "new-submit",
                    "name": "submit", "arguments": json.dumps({"theta_hat": MID})}]
            yield event


class FullBudgetContinuation(Continuation):
    async def stream(self, body, metadata):
        async for event in super().stream(body, metadata):
            if event["type"] == "response.completed":
                actions = [("simulate_high", {"theta": theta}) for theta in
                           ([.82, .07, 1.2], [.9, .1, 1.6], [1.1, .06, 1.3])]
                actions += [("measure_target", {"variable": "x", "time": 4})]
                actions += [("simulate_low", {"theta": theta}) for theta in
                            ([.83, .075, 1.25], [.93, .09, 1.2], [1.18, .065, 1.2])]
                actions += [("submit", {"theta_hat": MID})]
                event["response"]["output"] = [
                    {"type": "function_call", "call_id": f"continue-{i}", "name": name, "arguments": json.dumps(args)}
                    for i, (name, args) in enumerate(actions)]
            yield event


class ResumeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    async def asyncTearDown(self):
        self.tmp.cleanup()

    async def interrupted(self):
        with patch.object(ResourceAdapter, "run_comparisons", return_value={}), \
             patch("budgeted_science.agents.runner.load_api_key", side_effect=AssertionError("credential read")):
            path, reason = await run_episode(REPO, self.root, mode="dry-run", config=ResourceRunConfig(),
                instance=ResourceInstance.first_evaluation(), adapter=ResourceAdapter(), gateway=Interrupted())
        self.assertEqual(reason, "request_or_runner_error")
        return path

    async def test_checkpoint_resume_preserves_history_artifacts_money_and_original(self):
        parent = await self.interrupted()
        before = {p.relative_to(parent): p.read_bytes() for p in parent.rglob("*") if p.is_file()}
        resume = prepare_resume(parent, mode="dry-run")
        self.assertEqual(resume["responses"], 2)
        self.assertEqual(resume["saved"]["environment"]["ledger"][0]["charge"], 1)
        self.assertGreater(resume["money"].reserved, 0)
        gateway = Continuation()
        with patch("budgeted_science.resource_planning.environment._solve_low", side_effect=AssertionError("replay")), \
             patch("budgeted_science.resource_planning.environment._solve_high", side_effect=AssertionError("reference replay")), \
             patch.object(ResourceAdapter, "run_comparisons", side_effect=AssertionError("baseline rerun")), \
             patch("budgeted_science.agents.runner.load_api_key", side_effect=AssertionError("key")):
            child, reason = await run_episode(REPO, self.root, mode="dry-run", config=resume["config"],
                instance=resume["instance"], adapter=ResourceAdapter(), resume=resume, gateway=gateway)
        self.assertEqual(reason, "submitted")
        for path, value in before.items():
            self.assertEqual((parent / path).read_bytes(), value)
        self.assertTrue((parent / "resume_claim.json").is_file())
        data = json.loads((child / "evaluation.json").read_text())
        self.assertEqual(data["model_responses"], 3)
        self.assertEqual(data["evaluation"]["spent"], 1)
        self.assertEqual(data["api_budget"]["uncertain_reserved_usd"], str(resume["money"].reserved))
        self.assertGreater(data["elapsed_seconds"], resume["elapsed"])
        self.assertTrue((child / "api/generation-003-request.json").is_file())
        self.assertTrue(any(i.get("encrypted_content") for i in gateway.requests[0]["input"]))
        self.assertTrue(any(i.get("type") == "function_call_output" for i in gateway.requests[0]["input"]))
        self.assertNotIn("unfinished server attempt", json.dumps(gateway.requests))
        self.assertIn("unfinished server attempt", (child / "transcript.md").read_text())
        old = (child / "report.md").read_bytes()
        ResourceAdapter.regenerate(child)
        self.assertEqual(old, (child / "report.md").read_bytes())
        with self.assertRaisesRegex(ValueError, "already has a continuation"):
            prepare_resume(parent, mode="dry-run")
        with self.assertRaisesRegex(ValueError, "submitted"):
            prepare_resume(child, mode="dry-run")

    async def test_legacy_log_migration_requires_no_solver(self):
        parent = await self.interrupted()
        # This fixture deliberately models the pre-checkpoint format.
        (parent / "checkpoint.json").unlink()
        with patch("budgeted_science.resource_planning.environment._solve_high", side_effect=AssertionError("no solver")), \
             patch("budgeted_science.resource_planning.environment._solve_low", side_effect=AssertionError("no solver")):
            resume = prepare_resume(parent, mode="dry-run", require_full_budget=True)
        self.assertTrue(resume["config"].require_full_budget)
        self.assertIn("FULL 40-credit", resume["message"]["content"])
        self.assertEqual(len(resume["saved"]["environment"]["cache"]), 1)

    async def test_continuation_can_use_exact_remaining_budget(self):
        parent = await self.interrupted()
        resume = prepare_resume(parent, mode="dry-run", require_full_budget=True)
        with patch.object(ResourceAdapter, "run_comparisons", side_effect=AssertionError("baseline rerun")):
            child, reason = await run_episode(REPO, self.root, mode="dry-run", config=resume["config"],
                instance=resume["instance"], adapter=ResourceAdapter(), resume=resume, gateway=FullBudgetContinuation())
        self.assertEqual(reason, "submitted")
        data = json.loads((child / "evaluation.json").read_text())
        self.assertEqual(data["evaluation"]["spent"], 40)
        self.assertEqual(data["evaluation"]["remaining"], 0)
        self.assertEqual(data["model_responses"], 3)
        self.assertIn("full 40", (child / "report.md").read_text().lower().replace("all 40", "full 40"))

    async def test_original_response_and_api_limits_not_reset(self):
        parent = await self.interrupted()
        manifest_path = parent / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["public_configuration"]["max_responses"] = 2
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "limit has been exhausted"):
            prepare_resume(parent, mode="dry-run")

    async def test_authorized_ceiling_increase_preserves_usage_and_reservations(self):
        parent = await self.interrupted()
        original = prepare_resume(parent, mode="dry-run")
        resumed = prepare_resume(parent, mode="dry-run", api_ceiling_usd="3.00")
        before, after = original["money"].status(), resumed["money"].status()
        for key in ("known_cost_upper_usd", "uncertain_reserved_usd", "committed_upper_usd",
                    "measured_responses", "unsettled_requests"):
            self.assertEqual(before[key], after[key])
        self.assertEqual(after["ceiling_usd"], "3.00")
        self.assertEqual(resumed["config"].api_ceiling_usd, "3.00")
        self.assertIn("explicitly authorized", resumed["message"]["content"])
        self.assertEqual(json.loads((parent / "manifest.json").read_text())["public_configuration"]["api_ceiling_usd"], "2.00")

    async def test_ceiling_overrides_fail_closed(self):
        parent = await self.interrupted()
        for amount in ("1.00", "3.01", "NaN", "Infinity", "-1"):
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                prepare_resume(parent, mode="dry-run", api_ceiling_usd=amount)

    async def test_mode_prompt_and_unfinalized_state_fail_closed(self):
        parent = await self.interrupted()
        with self.assertRaisesRegex(ValueError, "mode cannot change"):
            prepare_resume(parent, mode="live")
        prompt = parent / "prompts.json"
        original = prompt.read_text()
        prompt.write_text("[]")
        with self.assertRaisesRegex(ValueError, "prompt or schema changed"):
            prepare_resume(parent, mode="dry-run")
        prompt.write_text(original)
        manifest = json.loads((parent / "manifest.json").read_text())
        manifest["termination_reason"] = "running"
        (parent / "manifest.json").write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "active or did not finalize"):
            prepare_resume(parent, mode="dry-run")

    async def test_corrupt_checkpoint_is_not_replayed(self):
        parent = await self.interrupted()
        path = parent / "checkpoint.json"
        saved = json.loads(path.read_text())
        saved["payload"]["environment"]["ledger"][0]["charge"] = 0
        path.write_text(json.dumps(saved))
        with self.assertRaisesRegex(ValueError, "checkpoint checksum"):
            prepare_resume(parent, mode="dry-run")


if __name__ == "__main__":
    unittest.main()

"""Offline resource-agent contracts. Never read real credentials or use the API."""

import asyncio
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import numpy as np

from budgeted_science.agents.records import RunLog, read_events, digest
from budgeted_science.agents.resource import (
    ResourceAdapter, ResourceEpisode, ResourceInstance, ResourceRunConfig, prompts, tool_definitions, run_comparisons)
from budgeted_science.agents.resource_fake import ResourceScriptedGateway
from budgeted_science.agents.runner import run_episode, replay_output_item
from budgeted_science.resource_planning.config import Config
from budgeted_science.resource_planning.emulator import Calibration, GPSettings

REPO = Path(__file__).resolve().parents[1]
MIDPOINT = [1.0, .08, 1.4]


class ToolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.log = RunLog(self.tmp.name, "test")
        self.instance = ResourceInstance.first_evaluation()
        self.episode = ResourceEpisode(ResourceRunConfig(), self.instance, self.log)

    def tearDown(self):
        self.log.close()
        self.tmp.cleanup()

    def call(self, name, args=None, call_id=None):
        return self.episode.execute(call_id or f"c-{len(self.episode.executed)}", name, json.dumps(args or {}))

    def test_defaults_fixed_api_model_limits_and_prices(self):
        config = ResourceRunConfig()
        self.assertEqual(config.max_output_tokens, 32768)
        self.assertEqual(config.public()["environment"]["costs"], {"low": 1., "high": 8., "measurement": 12.})
        for kwargs in ({"model": "other"}, {"reasoning_effort": "low"}, {"api_ceiling_usd": "2.01"},
                       {"max_responses": 31}, {"max_output_tokens": 32769}, {"deadline_seconds": 1201}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                ResourceRunConfig(**kwargs)

    def test_target_is_first_predetermined_evaluation_instance(self):
        from budgeted_science.resource_planning.experiment import target_set
        self.assertEqual(list(self.instance.theta), target_set("pilot", Config())[0]["theta"])
        self.assertFalse(np.allclose(self.instance.theta, MIDPOINT))

    def test_prompt_public_only_and_initial_zero_spend(self):
        messages = prompts(ResourceRunConfig(), self.episode)
        text = json.dumps(messages)
        for value in self.instance.theta:
            self.assertNotIn(str(value), text)
        for forbidden in ("target_seed", "2000", "reference_artifact", "0.9*", "0.01*x"):
            self.assertNotIn(forbidden, text)
        self.assertEqual(self.episode.budget_status()["spent"], 0)
        self.assertEqual(len(self.episode.initial_observations), 4)
        self.assertEqual(len(tool_definitions()), 8)

    def test_schema_errors_are_uncharged(self):
        cases = [("simulate_low", {"theta": [1, .08]}), ("simulate_high", {"theta": [True, .08, 1.4]}),
                 ("simulate_low", {"theta": [2, .08, 1.4]}), ("measure_target", {"variable": "z", "time": 2}),
                 ("measure_target", {"variable": "x", "time": 1.2}),
                 ("measure_target", {"variable": "x", "time": 0}),
                 ("measure_target", {"variable": "x", "time": 2, "theta": MIDPOINT}),
                 ("get_status", {"extra": 1}), ("submit", {"theta_hat": [1, .08, float("nan")]})]
        for name, args in cases:
            with self.subTest(name=name, args=args):
                self.assertFalse(self.call(name, args)["ok"])
        self.assertEqual(self.episode.budget_status()["spent"], 0)

    def test_duplicate_calls_and_repeated_purchases_are_free(self):
        args = {"variable": "x", "time": 2.0}
        first = self.call("measure_target", args, "same")
        again = self.call("measure_target", args, "same")
        self.assertEqual(first["result"], again["result"])
        self.assertTrue(again["replayed_call"])
        self.assertEqual(self.call("measure_target", args)["result"]["charge"], 0)
        self.assertFalse(self.call("measure_target", {"variable": "y", "time": 2}, "same")["ok"])
        self.assertEqual(self.episode.budget_status()["spent"], 12)

    def test_simulation_arrays_and_artifacts_complete(self):
        result = self.call("simulate_high", {"theta": MIDPOINT})["result"]
        self.assertEqual(np.asarray(result["values"]).shape, (16, 2))
        self.assertEqual(result["times"], list(Config().working_times))
        again = self.call("simulate_high", {"theta": MIDPOINT})["result"]
        self.assertEqual(again["charge"], 0)
        self.assertEqual(again["values"], result["values"])
        artifact = self.log.path / "numerical/agent" / (result["result_id"] + ".json")
        self.assertTrue(artifact.is_file())
        data = json.loads(artifact.read_text())
        self.assertGreater(len(data["times"]), 2)
        self.assertTrue((self.log.path / "private/agent-reference.json").is_file())

    def test_exhaustion_keeps_analysis_and_submission_available(self):
        for theta1 in (.8, .9, 1., 1.1, 1.2):
            self.assertTrue(self.call("simulate_high", {"theta": [theta1, .08, 1.4]})["ok"])
        self.assertEqual(self.episode.budget_status()["remaining"], 0)
        self.assertFalse(self.call("measure_target", {"variable": "x", "time": 2})["ok"])
        for name in ("evidence", "compare_cached_candidates", "fit_purchased"):
            self.assertTrue(self.call(name)["ok"])
        self.assertTrue(self.call("submit", {"theta_hat": MIDPOINT})["ok"])

    def test_failure_charged_and_cached(self):
        with patch("budgeted_science.resource_planning.environment._solve_low", side_effect=RuntimeError("private failure")) as solver:
            first = self.call("simulate_low", {"theta": MIDPOINT})
            second = self.call("simulate_low", {"theta": MIDPOINT})
        self.assertFalse(first["ok"])
        self.assertEqual(second["result"]["charge"], 0)
        self.assertEqual(solver.call_count, 1)
        self.assertNotIn("private failure", json.dumps(first))
        self.assertEqual(self.episode.budget_status()["spent"], 1)

    def test_fit_before_simulation_is_recoverable(self):
        self.assertFalse(self.call("fit_purchased")["ok"])
        self.assertEqual(self.episode.budget_status()["spent"], 0)

    def test_fit_matches_baseline_backend_single_and_two_fidelities(self):
        for fidelity in ("low", "high"):
            self.call("simulate_" + fidelity, {"theta": MIDPOINT})
            evidence = self.episode.tools.evidence()
            config = Config()
            reference = Calibration(evidence["simulations"], evidence["observations"], config.bounds,
                                    config.initial, config.working_times, settings=GPSettings(), seed=0)
            with patch("budgeted_science.resource_planning.environment._solve_low", side_effect=AssertionError("unpaid solver")), \
                 patch("budgeted_science.resource_planning.environment._solve_high", side_effect=AssertionError("unpaid solver")), \
                 patch.object(self.episode.environment._target, "sample", side_effect=AssertionError("unpaid target")):
                fitted = self.call("fit_purchased")
            self.assertTrue(fitted["ok"])
            np.testing.assert_allclose(fitted["result"]["posterior_mean"], reference.estimate(), atol=1e-12)
            again = self.call("fit_purchased")["result"]
            self.assertTrue(again["cache_hit"])
            self.assertEqual(again["fit_id"], fitted["result"]["fit_id"])
        self.assertEqual(len(list((self.log.path / "fitting").glob("*.json"))), 2)

    def test_high_only_fit_and_new_measurement_invalidate_cache(self):
        self.call("simulate_high", {"theta": MIDPOINT})
        first = self.call("fit_purchased")["result"]
        self.call("measure_target", {"variable": "y", "time": 4})
        second = self.call("fit_purchased")["result"]
        self.assertNotEqual(first["fit_id"], second["fit_id"])
        self.assertFalse(second["cache_hit"])
        self.assertEqual(self.episode.budget_status()["spent"], 20)

    def test_submitted_vector_not_replaced_by_fitter(self):
        self.call("simulate_low", {"theta": MIDPOINT})
        self.call("fit_purchased")
        result = self.call("submit", {"theta_hat": MIDPOINT})
        self.assertNotIn("success", result["result"])
        evaluation = self.episode.evaluate()
        self.assertEqual(evaluation["theta_hat"], MIDPOINT)
        expected = np.max(np.abs(np.array(MIDPOINT) - self.instance.theta) / (.1 * np.array(self.instance.theta)))
        self.assertAlmostEqual(evaluation["parameter_error"], expected)
        self.assertEqual(evaluation["resource_counts"], {"low": 1, "high": 0, "measurement": 0})

    def test_exact_target_submission_passes_and_score_is_private(self):
        submitted = self.call("submit", {"theta_hat": list(self.instance.theta)})
        self.assertNotIn("parameter_error", json.dumps(submitted))
        self.assertTrue(self.episode.evaluate()["success"])

    def test_deadline_rejects_work_before_purchase(self):
        self.episode.deadline = time.monotonic() - 1
        with self.assertRaises(TimeoutError):
            self.call("simulate_low", {"theta": MIDPOINT})
        self.assertEqual(self.episode.budget_status()["spent"], 0)

    def test_independent_comparisons_do_not_change_agent_evidence(self):
        before = self.episode.tools.evidence()
        results = run_comparisons(ResourceRunConfig(), self.instance, self.log)
        self.assertEqual(set(results), {"random", "adaptive"})
        for result in results.values():
            self.assertEqual(result["scientific_status"]["spent"], 40)
            self.assertTrue(result["evaluation"]["valid"])
            self.assertEqual(result["evaluation"]["theta_true"], list(self.instance.theta))
        self.assertEqual(before, self.episode.tools.evidence())


class ModifiedGateway(ResourceScriptedGateway):
    def __init__(self, change):
        super().__init__()
        self.change = change

    async def stream(self, body, metadata):
        async for event in super().stream(body, metadata):
            if event["type"] == "response.completed":
                event = deepcopy(event)
                self.change(event)
            yield event


class RunnerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    async def asyncTearDown(self):
        self.tmp.cleanup()

    async def run_it(self, gateway=None, config=None):
        with patch.object(ResourceAdapter, "run_comparisons", return_value={}), \
             patch("budgeted_science.agents.runner.load_api_key", side_effect=AssertionError("no key")):
            return await run_episode(REPO, self.tmp.name, mode="dry-run", config=config or ResourceRunConfig(),
                                     instance=ResourceInstance.first_evaluation(), adapter=ResourceAdapter(), gateway=gateway)

    async def test_complete_logs_history_and_offline_regeneration(self):
        gateway = ResourceScriptedGateway()
        path, status = await self.run_it(gateway)
        self.assertEqual(status, "submitted")
        self.assertEqual(len(gateway.requests), 5)
        events = read_events(path)[0]
        responses = [e["response"] for e in events if e["kind"] == "api_response"]
        for index in range(1, 5):
            for item in responses[index - 1]["output"]:
                self.assertIn(replay_output_item(item), gateway.requests[index]["input"])
        for request in gateway.requests:
            self.assertEqual(request["model"], "gpt-5.6-sol")
            self.assertEqual(request["reasoning"], {"effort": "high", "summary": "auto"})
            self.assertEqual(request["max_output_tokens"], 32768)
            self.assertFalse(request["store"])
            self.assertFalse(request["parallel_tool_calls"])
            self.assertNotIn("target_parameters", json.dumps(request))
            self.assertNotIn("private_reference_artifact", json.dumps(request))
        original = {name: (path / name).read_bytes() for name in ("events.jsonl", "transcript.md", "report.md", "evaluation.json")}
        with patch("budgeted_science.agents.runner.OpenAIGateway", side_effect=AssertionError("no API")), \
             patch("budgeted_science.resource_planning.environment._solve_high", side_effect=AssertionError("no rerun")):
            ResourceAdapter.regenerate(path)
        for name, content in original.items():
            self.assertEqual(content, (path / name).read_bytes())
        self.assertIn("Returned reasoning summary", (path / "transcript.md").read_text())
        self.assertIn("no LLM evaluated", (path / "report.md").read_text())
        manifest = json.loads((path / "manifest.json").read_text())
        self.assertEqual(manifest["prompt_hash"], digest(json.loads((path / "prompts.json").read_text())))

    async def test_stream_failure_preserves_partial_and_reservation(self):
        class Broken(ResourceScriptedGateway):
            async def stream(self, body, metadata):
                self.requests.append(body)
                yield {"type": "response.output_text.delta", "delta": "partial resource text"}
                raise ConnectionError("synthetic failure sk-synthetic-secret")
        gateway = Broken()
        path, reason = await self.run_it(gateway)
        self.assertEqual(reason, "request_or_runner_error")
        self.assertEqual(len(gateway.requests), 1)
        data = json.loads((path / "evaluation.json").read_text())
        self.assertGreater(Decimal(data["api_budget"]["uncertain_reserved_usd"]), 0)
        self.assertFalse(data["evaluation"]["valid"])
        self.assertIn("partial resource text", (path / "transcript.md").read_text())
        self.assertNotIn("sk-synthetic-secret", (path / "events.jsonl").read_text())

    async def test_missing_usage_no_tool_execution(self):
        path, reason = await self.run_it(ModifiedGateway(lambda e: e["response"].update(usage=None)))
        self.assertEqual(reason, "missing_or_invalid_usage")
        self.assertFalse(any(e["kind"] == "tool_requested" for e in read_events(path)[0]))

    async def test_incomplete_output_not_executed(self):
        def modify(e):
            e["type"] = "response.incomplete"
            e["response"].update(status="incomplete", incomplete_details={"reason": "max_output_tokens"})
        path, reason = await self.run_it(ModifiedGateway(modify))
        self.assertEqual(reason, "model_output_incomplete")
        self.assertFalse(json.loads((path / "evaluation.json").read_text())["evaluation"]["valid"])

    async def test_refusal_no_submission_and_wrong_model(self):
        changes = [
            (lambda e: e["response"].update(output=[]), "no_submission"),
            (lambda e: e["response"].update(model="other"), "unexpected_model_or_service_tier"),
            (lambda e: e["response"].update(output=[{"type": "message", "content": [{"type": "refusal"}]}]), "refusal")]
        for change, expected in changes:
            with self.subTest(expected=expected):
                _, reason = await self.run_it(ModifiedGateway(change))
                self.assertEqual(reason, expected)

    async def test_api_ceiling_and_response_limit(self):
        gateway = ResourceScriptedGateway()
        _, reason = await self.run_it(gateway, ResourceRunConfig(api_ceiling_usd=".01"))
        self.assertEqual(reason, "api_ceiling")
        self.assertEqual(gateway.requests, [])
        path, reason = await self.run_it(config=ResourceRunConfig(max_responses=1))
        self.assertEqual(reason, "response_limit")
        self.assertFalse(json.loads((path / "evaluation.json").read_text())["evaluation"]["valid"])

    async def test_count_failure_and_deadline(self):
        class NoCount(ResourceScriptedGateway):
            async def count(self, body, metadata):
                raise RuntimeError("count unavailable")
        _, reason = await self.run_it(NoCount())
        self.assertEqual(reason, "token_count_unavailable")
        class Slow(ResourceScriptedGateway):
            async def count(self, body, metadata):
                await asyncio.sleep(2)
        _, reason = await self.run_it(Slow(), ResourceRunConfig(deadline_seconds=.05))
        self.assertEqual(reason, "deadline")

    async def test_first_submission_stops_without_closing_generation(self):
        def change(e):
            e["response"]["output"] = [
                {"type": "function_call", "call_id": "submit", "name": "submit", "arguments": json.dumps({"theta_hat": MIDPOINT})},
                {"type": "function_call", "call_id": "unused", "name": "simulate_high", "arguments": json.dumps({"theta": MIDPOINT})}]
        path, reason = await self.run_it(ModifiedGateway(change))
        self.assertEqual(reason, "submitted")
        data = json.loads((path / "evaluation.json").read_text())
        self.assertEqual(data["evaluation"]["spent"], 0)
        self.assertEqual(data["model_responses"], 1)

    async def test_unfinished_log_can_be_rendered(self):
        log = RunLog(self.tmp.name, "dry-run")
        log.write_json("manifest.json", {"mode": "dry-run", "public_configuration": ResourceRunConfig().public()})
        log.event("interruption", reason="test interruption")
        log.close()
        ResourceAdapter.regenerate(log.path)
        self.assertIn("interrupted_without_finalization", (log.path / "report.md").read_text())


if __name__ == "__main__":
    unittest.main()

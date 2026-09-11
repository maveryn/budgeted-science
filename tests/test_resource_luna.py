"""Explicit Luna selection and accounting; all tests are offline."""

import asyncio
from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from budgeted_science.agents.records import RunLog
from budgeted_science.agents.resource import ResourceAdapter, ResourceEpisode, ResourceInstance, ResourceRunConfig, prompts, tool_definitions
from budgeted_science.agents.resource_fake import ResourceScriptedGateway
from budgeted_science.agents.resume import prepare_resume
from budgeted_science.agents.runner import run_episode
from budgeted_science.agents.spending import ApiBudget, ApiLimit, AccountingUnavailable, PRICING, pricing_for_model

REPO = Path(__file__).resolve().parents[1]


def luna_config(**kwargs):
    return ResourceRunConfig(model="gpt-5.6-luna", environment_version="v2", scientific_budget=32,
                             require_full_budget=True, api_ceiling_usd="3.00", **kwargs)


class LunaTests(unittest.TestCase):
    def test_model_selection_does_not_change_task_or_limits(self):
        config = luna_config()
        sol = replace(config, model="gpt-5.6-sol")
        self.assertEqual(config.reasoning_effort, "high")
        self.assertEqual((config.max_responses, config.max_output_tokens, config.deadline_seconds), (30, 32768, 1200))
        self.assertEqual(config.environment_config().public(), sol.environment_config().public())
        self.assertEqual(tool_definitions(config), tool_definitions(sol))
        with tempfile.TemporaryDirectory() as temp:
            log = RunLog(temp, "test")
            try:
                episode = ResourceEpisode(config, ResourceInstance.first_evaluation("v2"), log)
                self.assertEqual(prompts(config, episode), prompts(sol, episode))
            finally:
                log.close()
        for model in ("gpt-5.6", "other", "gpt-6-astra"):
            with self.assertRaises(ValueError):
                replace(config, model=model)
        with self.assertRaises(ValueError):
            replace(config, reasoning_effort="low")

    def test_luna_pricing_and_sol_backward_compatibility(self):
        luna = ApiBudget("3.00", model="gpt-5.6-luna")
        self.assertEqual(luna.reserve("a", 1000, 1000), Decimal("0.00145"))
        luna.settle("a", {"input_tokens": 1000, "output_tokens": 100,
                           "input_tokens_details": {"cached_tokens": 200},
                           "output_tokens_details": {"reasoning_tokens": 80}})
        self.assertEqual(luna.known_upper, Decimal("0.00037"))
        self.assertEqual(Decimal(luna.measured[0]["standard_cost_lower_usd"]), Decimal("0.000284"))
        sol = ApiBudget("3.00")
        self.assertEqual(sol.reserve("a", 1000, 1000), Decimal("0.025"))
        self.assertEqual(pricing_for_model("gpt-5.6-sol"), PRICING)
        self.assertEqual(pricing_for_model("gpt-5.6-luna")["output_per_million_usd"], "1.20")
        with self.assertRaises(ValueError):
            ApiBudget(model="unknown")

    def test_luna_reservation_resume_keeps_model_and_unknown_cost(self):
        ledger = ApiBudget("3.00", model="gpt-5.6-luna")
        ledger.reserve("known", 100, 100)
        ledger.settle("known", {"input_tokens": 100, "output_tokens": 50})
        ledger.reserve("unknown", 2000, 32768)
        reservations = {"unknown": {"input_tokens": 2000, "max_output_tokens": 32768}}
        self.assertEqual(ApiBudget.restore(ledger.status(), reservations).status(), ledger.status())
        with self.assertRaises(AccountingUnavailable):
            ApiBudget.restore(ledger.status(), reservations, model="gpt-5.6-sol")
        with self.assertRaises(ApiLimit):
            ApiBudget("0.001", model="gpt-5.6-luna").reserve("a", 1000, 32768)
        with self.assertRaises(ApiLimit):
            ledger.reserve("too-long", 256001, 10)
        legacy = ApiBudget().status()
        legacy.pop("model")
        self.assertEqual(ApiBudget.restore(legacy, {}).model, "gpt-5.6-sol")

    def test_offline_full_budget_luna_and_report_replay(self):
        with tempfile.TemporaryDirectory() as temp, \
             patch.object(ResourceAdapter, "run_comparisons", return_value={}), \
             patch("budgeted_science.agents.runner.load_api_key", side_effect=AssertionError("no real key")):
            gateway = ResourceScriptedGateway(require_full_budget=True)
            path, reason = asyncio.run(run_episode(REPO, temp, mode="dry-run", config=luna_config(),
                instance=ResourceInstance.first_evaluation("v2"), adapter=ResourceAdapter(), gateway=gateway))
            self.assertEqual(reason, "submitted")
            for request in gateway.requests:
                self.assertEqual(request["model"], "gpt-5.6-luna")
                self.assertEqual(request["reasoning"], {"effort": "high", "summary": "auto"})
            result = json.loads((path / "evaluation.json").read_text(encoding="utf-8"))
            manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(result["evaluation"]["spent"], 32)
            self.assertEqual(result["api_budget"]["model"], "gpt-5.6-luna")
            self.assertEqual(manifest["pricing"], pricing_for_model("gpt-5.6-luna"))
            before = (path / "report.md").read_bytes()
            ResourceAdapter.regenerate(path)
            self.assertEqual(before, (path / "report.md").read_bytes())
            self.assertIn("gpt-5.6-luna", before.decode())

    def test_interrupted_luna_resume_preserves_settings_and_prices(self):
        class Interrupted(ResourceScriptedGateway):
            async def stream(self, body, metadata):
                if self.requests:
                    yield {"type": "response.output_text.delta", "delta": "partial Luna fixture"}
                    raise ConnectionError("offline interruption")
                async for event in super().stream(body, metadata):
                    yield event
        with tempfile.TemporaryDirectory() as temp, patch.object(ResourceAdapter, "run_comparisons", return_value={}):
            path, reason = asyncio.run(run_episode(REPO, temp, mode="dry-run", config=luna_config(),
                instance=ResourceInstance.first_evaluation("v2"), adapter=ResourceAdapter(), gateway=Interrupted()))
            self.assertEqual(reason, "request_or_runner_error")
            resume = prepare_resume(path, mode="dry-run")
            self.assertEqual(resume["config"].model, "gpt-5.6-luna")
            self.assertEqual(resume["config"].scientific_budget, 32)
            self.assertEqual(resume["money"].model, "gpt-5.6-luna")
            self.assertGreater(resume["money"].reserved, 0)
            self.assertLess(resume["money"].reserved, Decimal("0.1"))


if __name__ == "__main__":
    unittest.main()

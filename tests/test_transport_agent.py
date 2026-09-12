"""Transport adapter checks; all model traffic is scripted or blocked."""

import asyncio
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from budgeted_science.agents.records import RunLog, read_events
from budgeted_science.agents.runner import run_episode
from budgeted_science.agents.transport_verification import (
    TransportConfig, TransportInstance, TransportEpisode, TransportAdapter,
    TransportGateway, prompts, regenerate, tool_definitions)
from budgeted_science.agents import transport_catalog as campaign
from budgeted_science.transport_verification import experiment as science
from budgeted_science.transport_verification import numerics
from budgeted_science.transport_verification.environment import Episode


class TransportAgentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.studies, _ = science.build_catalog()
        cls.study = cls.studies[0]
        # Synthetic imported comparisons for adapter tests, not measured performance.
        cls.comparisons = {}
        for s in cls.studies:
            e = Episode(s).evaluation()
            e.update(verdict="ACCEPT", correct=e["valid"], coverage=True, incomplete=False)
            cls.comparisons[s["id"]] = {p: {"evaluation": e} for p in science.POLICIES}

    def instance(self):
        return TransportInstance(self.study, self.comparisons[self.study["id"]])

    def test_fixed_contract_and_schema(self):
        cfg = TransportConfig()
        self.assertEqual(cfg.reasoning_effort, "high")
        self.assertEqual(cfg.max_output_tokens, 32768)
        for change in ({"model": "gpt-5.6-sol"}, {"scientific_budget": 8}, {"api_ceiling_usd": "3"}):
            with self.assertRaises(ValueError):
                replace(cfg, **change)
        tools = tool_definitions()
        self.assertEqual(len(tools), 8)
        for t in tools:
            self.assertTrue(t["strict"])
            self.assertEqual(set(t["parameters"]["required"]), set(t["parameters"]["properties"]))

    def test_prompt_no_private_truth_or_policy_recommendation(self):
        with tempfile.TemporaryDirectory() as directory:
            log = RunLog(directory, "test")
            ep = TransportEpisode(TransportConfig(), self.instance(), log)
            text = json.dumps(prompts(TransportConfig(), ep))
            for value in ("desired_valid", "private_selection", "balanced", str(self.study["reference"]["qois"]["peak"])):
                self.assertNotIn(value, text)
            self.assertIn("four", json.dumps(TransportConfig().scientific_budget).replace("4", "four"))
            self.assertIn("No shell", text)
            log.close()

    def test_charging_duplicate_invalid_and_free_submit(self):
        with tempfile.TemporaryDirectory() as directory:
            log = RunLog(directory, "test")
            ep = TransportEpisode(TransportConfig(), self.instance(), log)
            cfg = numerics.config(64, 1/256, output_dt=1/128)
            a = ep.execute("one", "run_verification", json.dumps(cfg))
            b = ep.execute("one", "run_verification", json.dumps(cfg))
            self.assertEqual(a, b)
            self.assertAlmostEqual(ep.budget_status()["spent"], 2.50390625)
            self.assertFalse(ep.execute("bad", "run_verification", '{"nx":NaN}')["ok"])
            self.assertFalse(ep.execute("two", "run_verification", json.dumps(numerics.config(64, 1/512, output_dt=1/128)))["ok"])
            result = ep.execute("three", "submit", json.dumps({"verdict": "ABSTAIN", "evidence_ids": ["original"], "justification": "test"}))
            self.assertTrue(result["ok"])
            self.assertTrue(ep.evaluate()["abstention"])
            self.assertFalse(ep.evaluate()["correct"])
            log.close()

    def test_replay_checkpoint_preserves_purchases(self):
        with tempfile.TemporaryDirectory() as directory:
            log = RunLog(directory, "test")
            ep = TransportEpisode(TransportConfig(), self.instance(), log)
            ep.execute("one", "run_verification", json.dumps(numerics.config()))
            saved = ep.checkpoint()
            self.assertEqual(saved["environment"]["spent"], ep.environment.spent)
            self.assertEqual(len(saved["environment"]["runs"]), 2)
            self.assertIn("one", saved["executed"])
            log.close()

    def test_dry_episode_uses_no_key_and_complete_offline_logs(self):
        with tempfile.TemporaryDirectory() as directory, patch("budgeted_science.agents.runner.load_api_key", side_effect=AssertionError("credentials read")):
            gateway = TransportGateway()
            path, reason = asyncio.run(run_episode(campaign.ROOT, Path(directory), mode="dry-run",
                config=TransportConfig(), instance=self.instance(), adapter=TransportAdapter(), gateway=gateway))
            self.assertEqual(reason, "submitted")
            self.assertEqual(len(gateway.requests), 2)
            self.assertTrue(any(i.get("encrypted_content") == "opaque-fixture" for i in gateway.requests[1]["input"]))
            before = (path/"transcript.md").read_bytes()
            with patch.object(numerics, "solve", side_effect=AssertionError("offline solver")):
                regenerate(path)
            self.assertEqual(before, (path/"transcript.md").read_bytes())
            events, torn = read_events(path)
            self.assertFalse(torn)
            self.assertEqual(sum(e["kind"] == "api_response" for e in events), 2)
            self.assertTrue((path/"numerical/original.json").exists())

    def test_interrupted_stream_retains_reservation(self):
        class Broken(TransportGateway):
            async def stream(self, body, metadata):
                yield {"type": "response.created", "response": {"id": "partial"}}
                raise OSError("synthetic interruption")
        with tempfile.TemporaryDirectory() as directory:
            path, reason = asyncio.run(run_episode(campaign.ROOT, Path(directory), mode="dry-run",
                config=TransportConfig(), instance=self.instance(), adapter=TransportAdapter(), gateway=Broken()))
            result = json.loads((path/"evaluation.json").read_text())
            self.assertTrue(result["evaluation"]["incomplete"])
            self.assertGreater(float(result["api_budget"]["uncertain_reserved_usd"]), 0)
            self.assertIn("partial", (path/"transcript.md").read_text())

    def test_campaign_live_gateway_override_blocked_before_access(self):
        with patch.object(campaign, "read_catalog", side_effect=AssertionError("catalog accessed")):
            with self.assertRaises(ValueError):
                asyncio.run(campaign.run_catalog(mode="live", gateway_factory=lambda i: TransportGateway()))

    def test_campaign_complete_unique_slots_and_offline_render(self):
        comparisons = deepcopy(self.comparisons)
        with tempfile.TemporaryDirectory() as directory, patch.object(campaign, "read_catalog", return_value=(self.studies, comparisons, {})), patch("budgeted_science.agents.runner.load_api_key", side_effect=AssertionError("credentials read")):
            path = asyncio.run(campaign.run_catalog(output_root=Path(directory), mode="dry-run"))
            report = (path/"report.md").read_bytes()
            with patch.object(numerics, "solve", side_effect=AssertionError("offline solver")), patch.object(campaign, "run_episode", side_effect=AssertionError("offline API")):
                summary = campaign.render(path)
            self.assertEqual(summary["attempted"], 12)
            self.assertEqual(summary["unfinalized_attempts"], 0)
            self.assertEqual(summary["overall"]["correct"], 6)
            self.assertLess(float(summary["batch_budget"]["committed_upper_usd"]), 2)
            self.assertEqual(report, (path/"report.md").read_bytes())


if __name__ == "__main__":
    unittest.main()
